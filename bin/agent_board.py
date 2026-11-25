#!/usr/bin/env python3
"""agent_board.py - the table behind `agent-file.sh board` (/auto-pipeline:todo). Python 3.9, standard library only.

    agent_board.py --root <main repo> --state-dir <git toplevel of the cwd> --cwd <cwd>
                   --now "YYYY-MM-DD HH:MM" --lang <zh|en> --host <machine> [--self] [--watch <sec>]

Read only: it writes nothing. One file; the only sibling it imports is agent_watchfile.py (the watch status file, read only),
with bytecode writing off, so no __pycache__ is written.
Prints one GitHub markdown table (or one line "无" / "none"), then note lines.

Rows (whole repo): every line of agent_todo.txt; every human-direct line of agent_worktree.txt ("<repo> Helper");
the state lines (OWNER TODO, PARKED, WORKER) of the main repo's agent_state.txt and of every agent_worktree.txt
folder that is on this machine (a folder that is not here: a note line after the table).
Progress column: the "stage <stage>[ <i>/<m>] since <date>" field of a todo line (--self: else the "STAGE <name>:"
line of its own agent_state.txt) gives a bar by the stage weights of agent.conf (template agent.conf.default next to
this script for a missing or bad key). The parse, progress and done-by functions are plain module functions (a status
line can call them). --watch <sec>: redraw every <sec> seconds until Ctrl-C.
    agent_board.py --statusline    (stdin: Claude Code's session JSON) one line per todo task that runs with a stage
                                   (name, bar, stage, done by) or waits on the owner or on others; queue, hold and
                                   not started rows fold into "+N queued/held"; at most 5 lines in all, or nothing;
                                   always exit 0 (bin/agent-statusline.sh runs it)
Rows (--self): the session's own task (its todo line, else its "TODO LINE:" in its own agent_state.txt, else the
human-direct line of its folder, else one bare row) plus the state lines of its own agent_state.txt only.
"""

import argparse
import datetime
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
import unicodedata
from fractions import Fraction

WATCH_WARN = {"zh": " · 未确认 %dm", "en": " · not confirmed %dm"}
WATCH_WARN_NO_N = {"zh": " · 未确认", "en": " · not confirmed"}
ORPHAN_NOTE = {"zh": "看板可能不准：%s 有活动窗格但没有任务行", "en": "board may be wrong: %s has a live pane but no task line"}
WATCH_QUIET_DEFAULT = 15


def load_watchfile():
    """The sibling module agent_watchfile (read only), None when it cannot be loaded. No bytecode is written."""
    here = os.path.dirname(os.path.abspath(__file__))
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        if here not in sys.path:
            sys.path.insert(0, here)
        import agent_watchfile
        return agent_watchfile
    except Exception:
        return None
    finally:
        sys.dont_write_bytecode = old

DATE = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
FMT = "%Y-%m-%d %H:%M"
HELPER_ROLE = "task manager, human-direct"

HEAD = {
    "zh": ["任务", "内容", "状态", "进度", "位置", "级别", "估时", "已工作", "已等待", "预计完成"],
    "en": ["Task", "What", "Status", "Progress", "Where", "Level", "Est", "Work", "Wait", "Done by"],
}
STATUS = {
    "zh": {"running": "进行中", "owner": "你的待办", "parked": "搁置的问题", "waiting": "等待", "hold": "暂缓",
           "queue": "排队", "notstarted": "未开始", "after": "在 %s 之后", "waited": "已等 %s", "you": "你",
           "fold": "+%d 排队/暂缓"},
    "en": {"running": "running", "owner": "your to-do", "parked": "parked question", "waiting": "waiting",
           "hold": "hold", "queue": "queue", "notstarted": "not started", "after": "after %s",
           "waited": "waited %s", "you": "you", "fold": "+%d queued/held"},
}
DEFAULT_WHAT = {
    "zh": {"mock": "确认样稿或规则表", "question": "回答问题", "review": "合并前签字"},
    "en": {"mock": "check mock or rules table", "question": "answer a question", "review": "sign off before merge"},
}
# sort groups: waiting on the owner, running, waiting on others, queue and not started, hold, OWNER TODO, parked
G_OWNER_WAIT, G_RUNNING, G_OTHER_WAIT, G_QUEUE, G_HOLD, G_OWNER_TODO, G_PARKED = 0, 1, 2, 3, 4, 5, 6
OWNER_KINDS = ("mock", "question", "review")
KNOWN_KINDS = OWNER_KINDS + ("hold", "queue")
OWNER_WHO = ("you", "owner", "你")
WHAT_MAX = 60
WAIT_WHAT_COLS = 40
LINE_WHAT_COLS = 24
STAGES = ["brief", "register", "mock", "tests", "workers", "verify", "push", "report", "e2e", "merge"]
BAR_CELLS = 10
CLEAR = "\033[H\033[2J"
FOOTER = {"zh": "每 %d 秒刷新 · Ctrl-C 停止", "en": "refresh every %ds · Ctrl-C stops"}
QUOTES = "\"'`“”‘’«»「」『』"


# ---------------------------------------------------------------- small helpers


def parse_time(text):
    try:
        return datetime.datetime.strptime(text.strip(), FMT)
    except (ValueError, AttributeError):
        return None


def minutes(a, b):
    """Whole minutes from a to b (b - a), never below 0; None when either is unknown."""
    if a is None or b is None:
        return None
    return max(0, int((b - a).total_seconds() // 60))


def fmt_min(n):
    if n is None:
        return "-"
    if n >= 1440:
        d, h = divmod(n // 60, 24)
        return "%dd %dh" % (d, h) if h else "%dd" % d
    if n >= 60:
        h, m = divmod(n, 60)
        return "%dh %dm" % (h, m) if m else "%dh" % h
    return "%dm" % n


def fmt_waited(lang, n):
    """The short waited time: zh 5分钟 / 2小时10分 / 3天20小时, en fmt_min."""
    if lang != "zh":
        return fmt_min(n)
    if n >= 1440:
        d, h = divmod(n // 60, 24)
        return "%d天%d小时" % (d, h) if h else "%d天" % d
    if n >= 60:
        h, m = divmod(n, 60)
        return "%d小时%d分" % (h, m) if m else "%d小时" % h
    return "%d分钟" % n


def collapse(text):
    return " ".join(str(text).split())


def char_width(ch):
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def display_width(text):
    return sum(char_width(c) for c in text)


def cut_cols(text, cols):
    """text (white space collapsed) cut to cols display columns: longer keeps at most cols-1 columns, then back to the
    last space when the next character is not a space, and "…"."""
    s = collapse(text)
    if display_width(s) <= cols:
        return s
    kept, used = "", 0
    for ch in s:
        if used + char_width(ch) > cols - 1:
            break
        kept, used = kept + ch, used + char_width(ch)
    if s[len(kept)] != " ":
        i = kept.rfind(" ")
        if i > 0:
            kept = kept[:i]
    return kept.rstrip() + "…"


def cut_what(text):
    s = collapse(text)
    if len(s) <= WHAT_MAX:
        return s
    limit = WHAT_MAX - 1
    kept = s[:limit]
    if s[limit] != " ":
        i = kept.rfind(" ")
        if i > 0:
            kept = kept[:i]
    return kept.rstrip() + "…"


def cell(text):
    return collapse(text).replace("|", "\\|") or "-"


def short_path(path, home):
    if home and home != "/" and (path == home or path.startswith(home.rstrip("/") + "/")):
        return "~" + path[len(home.rstrip("/")):]
    return path


def read_lines(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return []


# ---------------------------------------------------------------- stages, progress, done by (plain functions)


def conf_numbers(path):
    """key -> value text of a key=value file (the last line of a key wins); {} when unreadable."""
    out = {}
    for line in read_lines(path):
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def read_weights(root):
    """{stage: whole number 0-100}: <root>/agent.conf, a missing or bad key from the template next to this script;
    a key missing or bad in both: weight 0."""
    mine = conf_numbers(os.path.join(root, "agent.conf"))
    template = conf_numbers(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.conf.default"))
    weights = {}
    for stage in STAGES:
        key = "stage_" + stage
        for source in (mine, template):
            v = source.get(key, "")
            if re.match(r"^\d+$", v) and len(v) <= 9 and int(v) <= 100:
                weights[stage] = int(v)
                break
        else:
            weights[stage] = 0
    return weights


def read_eta_min_pct(root):
    """progress_eta_min_pct (whole number 0-100): <root>/agent.conf, else the template; missing or bad in both: 0."""
    mine = conf_numbers(os.path.join(root, "agent.conf"))
    template = conf_numbers(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.conf.default"))
    for source in (mine, template):
        v = source.get("progress_eta_min_pct", "")
        if re.match(r"^\d+$", v) and len(v) <= 9 and int(v) <= 100:
            return int(v)
    return 0


def parse_stage(text):
    """(stage, i, m) from "<stage>[ <i>/<m>]"; None when it is no known stage."""
    m = re.match(r"^(\w+)(?: (\d+)/(\d+))?$", text.strip())
    if not m or m.group(1) not in STAGES:
        return None
    if m.group(2) is None:
        return (m.group(1), None, None)
    if m.group(1) != "workers" or int(m.group(3)) < 1 or int(m.group(2)) > int(m.group(3)):
        return None
    return (m.group(1), int(m.group(2)), int(m.group(3)))


def stage_progress(weights, stage, est=None, since=None, now=None, waited=0, wsince=None):
    """Fraction 0..1 of the stage (stage = (name, i, m)), or None when the weights sum to 0 or no stage.

    Inside the stage it grows with time: share = est x weight / total minutes; t = minutes from since (a datetime)
    to now (an open wait, wsince, stops the clock) minus waited; the time part stops one percent point below the
    next stage's start. workers i/m: the larger of the slices and the time part."""
    if not stage:
        return None
    total = sum(weights.values())
    if total <= 0:
        return None
    name, i, m = stage
    before = sum(weights[s] for s in STAGES[:STAGES.index(name)])
    start = Fraction(before, total)
    end = start + Fraction(weights[name], total)
    p_t = start
    if est and weights[name] > 0 and since is not None and now is not None:
        stop = now
        if wsince is not None:
            stop = max(since, wsince)
        t = max(0, (minutes(since, stop) or 0) - (waited or 0))
        share = Fraction(est * weights[name], total)
        p_t = start + (end - start) * min(Fraction(1), Fraction(t) / share)
        cap = Fraction(math.ceil(end * 100) - 1, 100)
        p_t = max(start, min(p_t, cap))
    if name == "workers" and m:
        return max(start + (end - start) * Fraction(i, m), p_t)
    return p_t


def percent_of(p):
    return min(99, math.floor(p * 100))


def bar_text(p):
    """The progress cell: 10 cells of full and light blocks, a space, the percent right-aligned in 3, "%"."""
    pct = percent_of(p)
    full = pct // 10
    return "%s%s %3d%%" % ("█" * full, "░" * (BAR_CELLS - full), pct)


def clock_text(lang, now, when):
    clock = when.strftime("%H:%M")
    day = when.date()
    today = now.date()
    if day == today:
        return clock
    if day == today + datetime.timedelta(days=1):
        return ("明天 " + clock) if lang == "zh" else (clock + " tomorrow")
    stamp = when.strftime("%Y-%m-%d")
    return ("%s %s" % (stamp, clock)) if lang == "zh" else ("%s on %s" % (clock, stamp))


def done_by_text(lang, now, est, work, p, min_pct=0):
    """Done by: est / work in minutes (None = unknown), p = Fraction of progress or None.

    Far enough = a stage, p > 0 and 100 p >= min_pct (progress_eta_min_pct)."""
    if work is None:
        return "-"
    if est is not None and work < est:
        return clock_text(lang, now, now + datetime.timedelta(minutes=est - work))
    if p is not None and p > 0 and p * 100 >= min_pct:
        ahead = math.ceil(Fraction(work) * (1 - p) / p)
        return clock_text(lang, now, now + datetime.timedelta(minutes=ahead))
    if est is None:
        return "-"
    return ("超出 " if lang == "zh" else "over by ") + fmt_min(work - est)


# ---------------------------------------------------------------- LAUNCH records (written by the guard hook)

AGENT_KINDS = ("deputy", "merge", "reviewer", "explore", "plan", "guide", "agent")
PANE_KINDS = ("tm-pane", "shell-pane", "pane", "helper-pane")
KIND_WORD = {
    "zh": {"worker": "工人", "deputy": "副手", "merge": "合并", "reviewer": "审查", "explore": "探查", "plan": "规划",
           "guide": "指南", "agent": "代理", "pane": "窗格"},
    "en": {"worker": "worker", "deputy": "deputy", "merge": "merge", "reviewer": "reviewer", "explore": "explore",
           "plan": "plan", "guide": "guide", "agent": "agent", "pane": "pane"},
}
LAUNCH_STALE_MIN = 2
ORCA_TIMEOUT = 5


def parse_launch(line):
    """The record of one LAUNCH line as a dict, or None for a broken line."""
    try:
        if not line.startswith("LAUNCH "):
            return None
        key, sep, rest = line[7:].partition(": ")
        if not sep or not key.strip():
            return None
        parts = rest.split(" | ")
        if len(parts) < 6:
            return None
        kind = parts[0].strip()
        num = None
        m = re.match(r"worker (\d+)$", kind)
        if m:
            num, word = int(m.group(1)), "worker"
        elif kind == "worker":
            word = "worker"
        elif kind in AGENT_KINDS:
            word = kind
        elif kind in PANE_KINDS:
            word = "pane"
        else:
            return None
        if not parts[1].startswith("task ") or not parts[1][5:].strip():
            return None
        rec = {"key": key.strip(), "kind": kind, "word": word, "num": num, "is_pane": kind in PANE_KINDS,
               "task": parts[1][5:].strip(), "title": parts[2].strip() or "-"}
        for x in parts[3:]:
            k, _, v = x.strip().partition(" ")
            if k and k not in rec:
                rec.setdefault("f_" + k, v.strip())
        since = rec.get("f_since")
        if not since or not re.match(r"%s$" % DATE, since) or parse_time(since) is None:
            return None
        if not re.match(r"\d+$", rec.get("f_pid", "")) or not rec.get("f_by"):
            return None
        rec["since"], rec["pid"] = since, int(rec["f_pid"])
        rec["agent"], rec["pane"], rec["env"] = rec.get("f_agent"), rec.get("f_pane"), rec.get("f_env")
        return rec
    except Exception:
        return None


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except (ProcessLookupError, OverflowError, ValueError, OSError):
        return False
    return True


def guard_off(root):
    """board_guard=off in the main repo's agent.conf (the last such line; any other value is on)."""
    value = "on"
    for line in read_lines(os.path.join(root, "agent.conf")):
        k, sep, v = line.partition("=")
        if sep and k.strip() == "board_guard":
            value = v.split("#")[0].strip()
    return value == "off"


def launch_records(folder):
    return [r for r in (parse_launch(l) for l in read_lines(os.path.join(folder, "agent_state.txt"))) if r]


def finished_tasks(root):
    """Task names in agent_completed.txt that are not open in agent_todo.txt (a task done after its agent's LAUNCH
    line was left behind). A reopened name stays visible."""
    def names(name, col):
        out = set()
        for line in read_lines(os.path.join(root, name)):
            f = line.split(" | ")
            if len(f) > col and f[col].strip():
                out.add(f[col].strip())
        return out
    return names("agent_completed.txt", 1) - names("agent_todo.txt", 0)


def launch_young(rec, now):
    age = minutes(parse_time(rec["since"]), now)
    return age is not None and age <= LAUNCH_STALE_MIN


def agent_visible(rec, now):
    """An agent-kind record: pid alive, and linked to an agent or at most 2 minutes old."""
    return pid_alive(rec["pid"]) and (bool(rec["agent"]) or launch_young(rec, now))


def terminal_handles(env):
    """The set of pane handles orca lists (for env, else the local one), None when orca cannot say."""
    cmd = ["orca", "terminal", "list", "--json"] + (["--environment", env] if env else [])
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True,
                             timeout=ORCA_TIMEOUT, stdin=subprocess.DEVNULL)
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout)
        res = data["result"]
        terms = res["terminals"]
        if not isinstance(terms, list) or res.get("truncated"):
            return None
        total = res.get("totalCount")
        if isinstance(total, int) and total > len(terms):
            return None
        scope = res.get("hostScope")
        if isinstance(scope, dict) and scope.get("omittedHostIds"):
            return None
        return {t.get("handle") for t in terms if isinstance(t, dict)}
    except Exception:
        return None


def pane_visible(rec, now, listed):
    """A pane-kind record: a dead pid does not hide it; no handle: 2 minutes; a handle: it must be in the orca
    list (listed(env) -> set or None; None = orca cannot answer fully: shown while the session pid lives)."""
    if not rec["pane"]:
        return launch_young(rec, now)
    handles = listed(rec["env"])
    if handles is None:
        return pid_alive(rec["pid"])
    return rec["pane"] in handles


# ---------------------------------------------------------------- the board


class Board:
    def __init__(self, args):
        self.root = os.path.normpath(args.root)
        self.state_dir = os.path.normpath(args.state_dir)
        self.cwd = args.cwd
        self.now = parse_time(args.now) or datetime.datetime.now().replace(second=0, microsecond=0)
        self.lang = "zh" if args.lang == "zh" else "en"
        self.host = args.host
        self.self_mode = args.self_mode
        self.home = os.path.expanduser("~")
        self.words = STATUS[self.lang]
        self.weights = read_weights(self.root)
        self.eta_min_pct = read_eta_min_pct(self.root)
        self.rows = []
        self.notes = []
        self.seq = 0
        self.records = []       # (folder, record) of every LAUNCH line read
        self.hand_workers = {}  # label -> row of a hand WORKER line
        self.unconfirmed = 0    # target rows that got the "not confirmed" warning
        self.watch_setup()

    # -- the watch (F3-F7): the status file is only read, orca is never called

    def watch_setup(self):
        self.w_on = False        # warnings apply (a watch can run here)
        self.w_live = False
        self.w_names = set()     # names of the targets (A1)
        self.w_tasks = {}
        self.w_orphans = []
        self.w_quiet = WATCH_QUIET_DEFAULT
        self.w_target_count = 0
        wf = load_watchfile()
        if wf is None:
            return
        try:
            if wf.no_watch_runtime(self.root):
                return
            found = wf.targets(self.root)
            status = wf.read_status(self.root)
            self.w_live = wf.live(status, self.now)
            self.w_tasks = wf.tasks_of(status)
            self.w_names = set(t["name"] for t in found)
            self.w_target_count = len(found)
            if self.w_live:
                orphans = status.get("orphans")
                for o in orphans if isinstance(orphans, list) else []:
                    if isinstance(o, dict) and isinstance(o.get("path"), str) and o["path"]:
                        self.w_orphans.append(o["path"])
            v = conf_numbers(os.path.join(self.root, "agent.conf")).get("watch_quiet_min", "")
            if re.match(r"^\d{1,3}$", v) and 1 <= int(v) <= 240:
                self.w_quiet = int(v)
            self.w_on = True
        except Exception:
            self.w_on = False

    def watch_warn(self, t, group):
        """The F3 warning for a todo row ("" for none)."""
        if not self.w_on or t["name"] not in self.w_names:
            return ""
        entry = self.w_tasks.get(t["name"])
        entry = entry if isinstance(entry, dict) else {}
        since = None
        for src in (entry.get("changed"), entry.get("confirmed"), t["started"], t["opened"]):
            since = parse_time(src) if isinstance(src, str) else None
            if since is not None:
                break
        n = minutes(since, self.now)
        if not self.w_live or entry.get("watched") is False:
            warn = True
        else:
            warn = group == G_RUNNING and n is not None and n >= self.w_quiet
        if not warn:
            return ""
        self.unconfirmed += 1
        return (WATCH_WARN[self.lang] % n) if n is not None else WATCH_WARN_NO_N[self.lang]

    # -- words

    def word(self, key):
        return self.words[key]

    def where_here(self, path):
        return "%s, %s" % (self.host, short_path(path, self.home))

    def where_path(self, path):
        """This machine and the path when the folder is here, else the path alone."""
        if os.path.isdir(path):
            return self.where_here(path)
        return short_path(path, self.home)

    def progress_of(self, t):
        wsince = parse_time(t["wsince"]) if t["wsince"] else None
        return stage_progress(self.weights, t["stage"], t["est"], parse_time(t["since"]) if t["since"] else None,
                              self.now, t["wis"], wsince)

    # -- rows

    def add(self, group, when, task, what, status, where, est="-", work="-", wait="-", done="-", progress="-",
            info=None, level="-"):
        """when: "YYYY-MM-DD HH:MM" or None (no date sorts last, file order)."""
        self.seq += 1
        key = (group, 0 if when else 1, when or "", self.seq)
        cells = [cell(task), cell(cut_what(what)), cell(status), progress.replace("|", "\\|"), cell(where), cell(level), cell(est),
                 cell(work), cell(wait), cell(done)]
        self.rows.append((key, cells, info))

    # -- the todo lines

    def parse_todo(self, line):
        f = line.split(" | ")
        t = {"name": f[0].strip(), "what": f[2] if len(f) > 2 else "", "est": None,
             "opened": None, "wkind": None, "wsince": None, "wnote": "", "waited": 0,
             "machine": None, "path": None, "stage": None, "since": None, "wis": 0, "level": None,
             "who": None, "after": None, "wrun": None, "started": None, "swaited": 0}
        for x in f[3:]:
            m = re.match(r"est (\d+)m$", x)
            if m and t["est"] is None:
                t["est"] = int(m.group(1))
                continue
            m = re.match(r"opened (%s)" % DATE, x)
            if m and t["opened"] is None:
                t["opened"] = m.group(1)
                continue
            m = re.match(r"waiting (\S+) since (%s)(?:: (.*))?$" % DATE, x)
            if m and t["wkind"] is None:
                t["wkind"], t["wsince"], t["wnote"] = m.group(1), m.group(2), m.group(3) or ""
                continue
            m = re.match(r"stage (\S+(?: \d+/\d+)?) since (%s)" % DATE, x)
            if m and t["stage"] is None:
                t["stage"] = parse_stage(m.group(1))
                t["since"] = m.group(2)
                continue
            m = re.match(r"who (.*)$", x)
            if m and t["who"] is None:
                if m.group(1).strip():
                    t["who"] = m.group(1).strip()
                continue
            m = re.match(r"after (.*)$", x)
            if m and t["after"] is None:
                if m.group(1).strip():
                    t["after"] = m.group(1).strip()
                continue
            m = re.match(r"wait run since (%s)$" % DATE, x.strip())
            if m and t["wrun"] is None and parse_time(m.group(1)):
                t["wrun"] = m.group(1)
                continue
            m = re.match(r"started (%s)(?: after (\d+)m waited)?$" % DATE, x.strip())
            if m and t["started"] is None and parse_time(m.group(1)):
                t["started"], t["swaited"] = m.group(1), int(m.group(2) or 0)
                continue
            m = re.match(r"level (\d+|[A-D])$", x)
            if m and t["level"] is None:
                # a type letter; an old number reads as 0=A 1=B 2,3=C 4=D (R8)
                v = m.group(1)
                t["level"] = v if v.isalpha() else ("ABCCD" + "D" * 20)[int(v)]
                continue
            m = re.match(r"waited in stage (\d+)m$", x)
            if m:
                t["wis"] = int(m.group(1))
                continue
            m = re.match(r"waited (\d+)m$", x)
            if m:
                t["waited"] = int(m.group(1))
                continue
            m = re.match(r"on (\S+)(?: (.*))?$", x)
            if m and t["machine"] is None:
                t["machine"], t["path"] = m.group(1), (m.group(2) or "").strip()
        return t

    def worktree_where(self, task, wt_lines):
        for f in wt_lines:
            if len(f) >= 2 and f[1] != HELPER_ROLE and (f[1] == task or os.path.basename(f[0].rstrip("/")) == task):
                return self.where_path(f[0])
        return None

    def waited_minutes(self, t):
        """Minutes of the open wait run, None when its start is unknown (rule 5.0): from the open wait's since, or from opened when the closed waits
        fill all the time before it, else from the "wait run since" field."""
        s = parse_time(t["wsince"])
        opened = parse_time(t["opened"]) if t["opened"] else None
        start = s
        if opened is not None and s is not None and t["waited"] >= minutes(opened, s):
            start = opened
        elif t["wrun"]:
            start = parse_time(t["wrun"]) or s
        return minutes(start, self.now)

    def wait_text(self, t, kind, owner, cols):
        """The Status cell of a waiting or hold row; cols = display columns of the what part (None: no what part)."""
        w = self.words
        n = self.waited_minutes(t)
        note = collapse(t["wnote"])
        what = note or DEFAULT_WHAT[self.lang].get(kind, "")
        parts = []
        if t["who"] or kind in OWNER_KINDS:
            parts.append("%s %s" % (w["waiting"], w["you"] if owner else t["who"]))
        else:
            parts.append(w["hold"])
        if what and cols is not None:
            parts.append(cut_cols(what, cols))
        if n is not None:
            parts.append(w["waited"] % fmt_waited(self.lang, n))
        return " · ".join(parts)

    def queue_text(self, t):
        w = self.words
        task = t["after"]
        if not task:
            m = re.match(r"after\s+(\S+)", collapse(t["wnote"]), re.IGNORECASE)
            task = m.group(1).rstrip(",;:.") if m else ""
        return w["queue"] + (" · " + w["after"] % task if task else "")

    def todo_row(self, t, wt_lines, own_dir=None):
        opened = parse_time(t["opened"]) if t["opened"] else None
        started = parse_time(t["started"]) if t["started"] else None
        wsince = parse_time(t["wsince"]) if t["wsince"] else None
        wait = t["waited"]
        if wsince is not None:
            wait += minutes(wsince, self.now)
        kind = t["wkind"] if t["wkind"] in KNOWN_KINDS else None
        who = t["who"]
        owner = bool(kind in OWNER_KINDS and not who) or bool(who and who.lower() in OWNER_WHO)
        info = None
        dash = False
        est = fmt_min(t["est"])
        work, done, progress = "-", "-", "-"
        if kind == "queue":
            group, when, dash = G_QUEUE, t["wsince"], True
            status = self.queue_text(t)
            info = {"type": "short", "name": t["name"], "text": status}
        elif kind:
            group = G_OWNER_WAIT if owner else (G_OTHER_WAIT if who else G_HOLD)
            when, dash = t["wsince"], True
            status = self.wait_text(t, kind, owner, WAIT_WHAT_COLS)
            if group == G_OWNER_WAIT:
                info = {"type": "wait", "name": t["name"], "text": self.wait_text(t, kind, owner, LINE_WHAT_COLS)}
            elif group == G_OTHER_WAIT:
                info = {"type": "wait", "name": t["name"], "text": self.wait_text(t, kind, owner, None)}
            else:
                info = {"type": "short", "name": t["name"], "text": self.wait_text(t, kind, owner, None)}
        elif t["since"] is None and started is None:
            group, when = G_QUEUE, t["opened"]
            status = self.word("notstarted")
            wait = None
            info = {"type": "short", "name": t["name"], "text": status}
        else:
            group, when = G_RUNNING, t["opened"]
            status = self.word("running")
        if dash or wait is None:
            wait_cell = "-"
            if dash:
                est = "-"
        else:
            if started is not None:
                work = max(0, minutes(started, self.now) - (wait - t["swaited"]))
            else:
                clock = minutes(opened, self.now)
                work = None if clock is None else max(0, clock - wait)
            p = self.progress_of(t)
            done = done_by_text(self.lang, self.now, t["est"], work, p, self.eta_min_pct)
            work = fmt_min(work)
            wait_cell = fmt_min(wait)
            progress = "-" if p is None else bar_text(p)
            if p is not None:
                info = {"type": "run", "name": t["name"], "stage": t["stage"], "bar": progress, "done": done}
        status += self.watch_warn(t, group)
        if t["machine"]:
            where = t["machine"] + (", " + short_path(t["path"], self.home) if t["path"] else "")
        else:
            where = self.worktree_where(t["name"], wt_lines)
            if where is None:
                where = self.where_here(own_dir) if own_dir else "-"
        self.add(group, when, t["name"], t["what"] or "-", status, where,
                 est=est, work=work, wait=wait_cell, done=done, progress=progress,
                 level="-" if t["level"] is None else t["level"], info=info)

    def helper_row(self, f):
        what = "-"
        if len(f) > 2 and f[2].startswith("task:"):
            what = f[2][5:].strip() or "-"
        since = None
        if len(f) > 3:
            m = re.match(r"since (%s)" % DATE, f[3])
            since = m.group(1) if m else None
        task = "%s Helper" % os.path.basename(self.root)
        self.add(G_RUNNING, since, task, what, self.word("running"), self.where_path(f[0]))

    # -- the state lines

    def state_rows(self, folder):
        """OWNER TODO, PARKED and WORKER lines of <folder>/agent_state.txt."""
        name = os.path.basename(folder.rstrip("/")) or folder
        where = self.where_here(folder)
        for line in read_lines(os.path.join(folder, "agent_state.txt")):
            m = re.match(r"PARKED: (.*)$", line)
            if m:
                parts = m.group(1).split(" | ")
                since = None
                for x in parts[1:]:
                    mm = re.match(r"since (%s)" % DATE, x)
                    if mm:
                        since = mm.group(1)
                task = parts[1].strip() if len(parts) > 1 and not parts[1].startswith("since ") else name
                wait = fmt_min(minutes(parse_time(since), self.now)) if since else "-"
                self.add(G_PARKED, since, task or name, parts[0], self.word("parked"), where, wait=wait)
                continue
            m = re.match(r"WORKER (\d+): (.*)$", line)
            if m:
                parts = m.group(2).split(" | ")
                since = None
                for x in parts[1:]:
                    mm = re.match(r"since (%s)" % DATE, x)
                    if mm:
                        since = mm.group(1)
                label = ("%s 工人 %s" if self.lang == "zh" else "%s worker %s") % (name, int(m.group(1)))
                work = fmt_min(minutes(parse_time(since), self.now)) if since else "-"
                self.add(G_RUNNING, since, label, parts[0], self.word("running"), where, work=work)
                self.hand_workers[label] = self.rows[-1]
                continue
            rec = parse_launch(line)
            if rec:
                self.records.append((folder, rec))
                continue
            item = self.owner_item(line)
            if item:
                text, stamp = item
                wait = fmt_min(minutes(parse_time(stamp), self.now)) if stamp else "-"
                self.add(G_OWNER_TODO, stamp, "-", text, self.word("owner"), "-", wait=wait)

    @staticmethod
    def owner_item(line):
        """(item text, stamp or None) when the line holds the marker "OWNER TODO:", else None.

        Capitals and the colon, anywhere in the line, not right after a quote mark. Without the colon it is a
        mention. The item text is what follows the colon. A "YYYY-MM-DD[ HH:MM]" stamp at the start of the line
        (after spaces or a "-" / "*" bullet) is its date.
        """
        m = re.search(r"(?<![%s])OWNER TODO:(.*)$" % re.escape(QUOTES), line)
        if not m or not m.group(1).strip():
            return None
        stamp = None
        d = re.match(r"\s*(?:[-*]\s+)?(\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}))?\s", line)
        if d:
            stamp = "%s %s" % (d.group(1), d.group(2) or "00:00")
        return m.group(1).strip(), stamp

    def own_stage(self, name):
        """(stage, since text or None) of the "STAGE <name>:" line of this folder's agent_state.txt, or None."""
        found = None
        for line in read_lines(os.path.join(self.state_dir, "agent_state.txt")):
            m = re.match(r"STAGE %s: (.*?)(?: \| since (%s))?\s*$" % (re.escape(name), DATE), line)
            if m:
                stage = parse_stage(m.group(1))
                found = (stage, m.group(2)) if stage else None
        return found

    def own_todo_line(self):
        found = None
        for line in read_lines(os.path.join(self.state_dir, "agent_state.txt")):
            m = re.match(r"\s*TODO LINE: (.*)$", line)
            if m:
                found = m.group(1)
        return found

    # -- the two views

    def whole_repo(self):
        wt_lines = [l.split(" | ") for l in read_lines(os.path.join(self.root, "agent_worktree.txt")) if l.strip()]
        for line in read_lines(os.path.join(self.root, "agent_todo.txt")):
            if not line.strip():
                continue
            t = self.parse_todo(line)
            if t["name"]:
                self.todo_row(t, wt_lines)
        for f in wt_lines:
            if len(f) >= 2 and f[1] == HELPER_ROLE:
                self.helper_row(f)
        seen = set()
        for folder in [self.root] + [f[0] for f in wt_lines if f and f[0]]:
            norm = os.path.normpath(folder)
            if not os.path.isdir(norm):
                if norm not in seen:
                    self.notes.append(("不在本机，未读：%s" if self.lang == "zh" else
                                       "not on this machine, not read: %s") % folder)
                seen.add(norm)
                continue
            real = os.path.realpath(norm)
            if real in seen:
                continue
            seen.add(real)
            self.state_rows(norm)
        if self.w_on and self.w_live:
            for path in self.w_orphans:
                self.notes.append(ORPHAN_NOTE[self.lang] % path)

    def own_view(self):
        folder = self.state_dir
        name = os.path.basename(folder.rstrip("/")) or folder
        in_root = os.path.realpath(folder) == os.path.realpath(self.root)
        wt_lines = [l.split(" | ") for l in read_lines(os.path.join(self.root, "agent_worktree.txt")) if l.strip()]
        found = False
        for line in read_lines(os.path.join(self.root, "agent_todo.txt")):
            if not line.strip():
                continue
            t = self.parse_todo(line)
            if t["name"] == name:
                if t["stage"] is None:
                    t["stage"], t["since"] = self.own_stage(name) or (None, None)
                self.todo_row(t, wt_lines, own_dir=folder)
                found = True
                break
        if not found and not in_root:
            line = self.own_todo_line()
            if line:
                t = self.parse_todo(line)
                if t["name"]:
                    if t["stage"] is None:
                        t["stage"], t["since"] = self.own_stage(t["name"]) or (None, None)
                    self.todo_row(t, wt_lines, own_dir=folder)
                    found = True
        if not found:
            here = {os.path.realpath(folder), os.path.realpath(self.cwd)}
            for f in wt_lines:
                if len(f) >= 2 and f[1] == HELPER_ROLE and os.path.realpath(f[0]) in here:
                    self.helper_row(f)
                    found = True
                    break
        if not found:
            self.add(G_RUNNING, None, name, "-", self.word("running"), self.where_here(folder))
        if not in_root:
            self.state_rows(folder)

    # -- the LAUNCH records

    def add_launches(self):
        """One row per visible record, right under its task's row; a hand WORKER row of the same label goes."""
        if guard_off(self.root):
            return
        now = self.now
        cache = {}

        def listed(env):
            if env not in cache:
                cache[env] = terminal_handles(env)
            return cache[env]

        parents = {}
        for row in self.rows:
            parents.setdefault(row[1][0], row)
        words = KIND_WORD[self.lang]
        kids = {}
        finished = finished_tasks(self.root)
        for folder, rec in self.records:
            if rec["is_pane"]:
                if not pane_visible(rec, now, listed):
                    continue
            elif not agent_visible(rec, now) or rec["task"] in finished:
                continue
            label = "%s %s" % (rec["task"], words[rec["word"]])
            if rec["num"] is not None:
                label += " %d" % rec["num"]
            hand = self.hand_workers.get(label)
            if hand is not None and hand in self.rows:
                self.rows.remove(hand)
            work = fmt_min(minutes(parse_time(rec["since"]), now))
            cells = [cell(label), cell(cut_what(rec["title"])), cell(self.word("running")), "-",
                     cell(self.where_here(folder)), "-", "-", cell(work), "-", "-"]
            kids.setdefault(rec["task"], []).append((rec["since"], label, cells))
        for task, items in kids.items():
            parent = parents.get(task)
            for i, (since, label, cells) in enumerate(sorted(items, key=lambda x: x[0])):
                if parent is not None and parent in self.rows:
                    group, flag, when, seq = parent[0]
                    key = (group, flag, when, seq + (i + 1) / 100000.0)
                else:
                    self.seq += 1
                    key = (G_RUNNING, 0, since, self.seq)
                self.rows.append((key, cells, None))

    # -- print

    def render(self):
        if not self.rows:
            out = ["无" if self.lang == "zh" else "none"]
            out += self.notes
            return "\n".join(out) + "\n"
        out = ["| " + " | ".join(HEAD[self.lang]) + " |", "|" + "---|" * len(HEAD[self.lang])]
        for _, cells, _info in sorted(self.rows, key=lambda r: r[0]):
            out.append("| " + " | ".join(cells) + " |")
        if self.notes:
            out.append("")
            out += self.notes
        return "\n".join(out) + "\n"


def build(args, now=None, records=True):
    """One fresh Board for these args (now: "YYYY-MM-DD HH:MM", else args.now). records=False: no LAUNCH rows (and
    no orca call)."""
    if now is not None:
        args = argparse.Namespace(**dict(vars(args), now=now))
    board = Board(args)
    if args.self_mode:
        board.own_view()
    else:
        board.whole_repo()
    if records:
        board.add_launches()
    return board


def clock_now():
    """AGENT_FAKE_NOW when set, else the machine clock."""
    return os.environ.get("AGENT_FAKE_NOW") or datetime.datetime.now().strftime(FMT)


def watch(args, sec):
    def stop(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGINT, stop)
    try:
        while True:
            board = build(args, clock_now())
            sys.stdout.write(CLEAR + board.render() + FOOTER[board.lang] % sec + "\n")
            sys.stdout.flush()
            time.sleep(sec)
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    return 0


def git_out(folder, *cmd):
    out = subprocess.run(["git", "-C", folder] + list(cmd), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         universal_newlines=True, timeout=5)
    return out.stdout if out.returncode == 0 else ""


WATCH_LINE = {
    "zh": {"off": "看板可能不准：看守未运行", "count": "看板可能不准：%d 个未确认", "orphan": "看板可能不准：有窗格无任务行"},
    "en": {"off": "board may be wrong: watch not running", "count": "board may be wrong: %d not confirmed",
           "orphan": "board may be wrong: a pane has no task line"},
}


def watch_status_line(board):
    """F6: the warning first line of the status line, "" for none."""
    if not board.w_on:
        return ""
    words = WATCH_LINE[board.lang]
    if not board.w_live:
        return words["off"] if board.w_target_count else ""
    if board.unconfirmed:
        return words["count"] % board.unconfirmed
    return words["orphan"] if board.w_orphans else ""


ZH_STAGE = {"brief": "简报", "register": "登记", "mock": "样稿", "tests": "写测试", "workers": "写代码",
            "verify": "验证", "push": "推送", "report": "报告", "e2e": "浏览器验收", "merge": "合并"}
NAME_COLS = 24
STATUS_LINES = 5


def fit(text, cols):
    """text padded with spaces to cols display columns; longer: its first cols-1 columns and "…"."""
    if display_width(text) <= cols:
        return text + " " * (cols - display_width(text))
    kept, used = "", 0
    for ch in text:
        if used + char_width(ch) > cols - 1:
            break
        kept, used = kept + ch, used + char_width(ch)
    return kept + "…" + " " * (cols - 1 - used)


def statusline_text(stdin_text):
    """The status line: todo rows only, the board's order: a run with a stage (name, bar, stage, done by), a wait on
    the owner or on others; queue, hold and not started rows fold into "+N queued/held"; at most 5 lines in all;
    "" for none."""
    folder = None
    try:
        data = json.loads(stdin_text)
        if isinstance(data, dict):
            ws = data.get("workspace")
            for v in ((ws or {}).get("current_dir") if isinstance(ws, dict) else None, data.get("cwd")):
                if isinstance(v, str) and v and os.path.isdir(v):
                    folder = v
                    break
    except ValueError:
        pass
    folder = folder or os.getcwd()
    top = git_out(folder, "rev-parse", "--show-toplevel").strip()
    main = next((l[9:] for l in git_out(folder, "worktree", "list", "--porcelain").splitlines()
                 if l.startswith("worktree ")), "")
    if not top or not main or not os.path.isfile(os.path.join(main, "agent.conf")):
        return ""
    lang = "zh" if conf_numbers(os.path.join(main, "agent.conf")).get("language") == "zh" else "en"
    own = os.path.realpath(top) != os.path.realpath(main)
    args = argparse.Namespace(root=main, state_dir=top, cwd=folder, now=clock_now(), lang=lang, host="-",
                              self_mode=own)
    board = build(args, records=False)
    zh = lang == "zh"
    lines = []
    for _, cells, info in sorted(board.rows, key=lambda r: r[0]):
        if info is None:
            continue
        if info["type"] in ("wait", "short"):
            lines.append((info["type"], info["name"], info["text"]))
        else:
            stage, i, m = info["stage"]
            word = ZH_STAGE[stage] if zh else stage
            if i is not None:
                word += " %d/%d" % (i, m)
            lines.append(("run", info["name"], word, info["bar"], info["done"]))
    warn = "" if own else watch_status_line(board)
    room = STATUS_LINES - (1 if warn else 0)
    cands = lines
    shown = cands if len(cands) <= room else cands[:room - 1]
    counts = {}
    if not guard_off(main):
        now = parse_time(args.now)
        finished = finished_tasks(main)
        for r in launch_records(top):
            if not r["is_pane"] and agent_visible(r, now) and r["task"] not in finished:
                counts[r["task"]] = counts.get(r["task"], 0) + 1

    def tail(name):
        n = counts.get(name, 0)
        if not n:
            return ""
        return " · " + ("%d 代理" % n if zh else "%d agent%s" % (n, "" if n == 1 else "s"))

    wide = max([display_width(l[2]) for l in shown if l[0] == "run"] or [0])
    out = []
    for l in shown:
        if l[0] == "run":
            _, name, word, bar, done = l
            row = "  ".join([fit(name, NAME_COLS), bar, word + " " * (wide - display_width(word))])
            if done != "-":
                row += "  " + done
        else:
            row = fit(l[1], NAME_COLS) + "  " + l[2]
        out.append(row.rstrip() + tail(l[1]))
    rest = len(cands) - len(shown)
    if rest:
        out.append(STATUS[lang]["fold"] % rest)
    if warn:
        out.insert(0, warn)
    return "\n".join(out)


def statusline():
    try:
        try:
            text = "" if sys.stdin.isatty() else sys.stdin.read()
        except (OSError, ValueError):
            text = ""
        line = statusline_text(text)
        if line:
            sys.stdout.write(line + "\n")
    except Exception:
        pass
    return 0


def main():
    if "--statusline" in sys.argv[1:]:
        sys.exit(statusline())
    p = argparse.ArgumentParser(prog="agent_board.py")
    p.add_argument("--root", required=True)
    p.add_argument("--state-dir", required=True)
    p.add_argument("--cwd", required=True)
    p.add_argument("--now", required=True)
    p.add_argument("--lang", default="en")
    p.add_argument("--host", default="-")
    p.add_argument("--self", dest="self_mode", action="store_true")
    p.add_argument("--watch", type=int, default=None, metavar="SEC")
    args = p.parse_args()
    if args.watch is not None:
        if args.watch < 1:
            p.error("--watch takes a whole number of seconds from 1")
        sys.exit(watch(args, args.watch))
    sys.stdout.write(build(args).render())


if __name__ == "__main__":
    main()
