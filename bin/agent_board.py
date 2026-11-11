#!/usr/bin/env python3
"""agent_board.py - the table behind `agent-file.sh board` ("show todo"). Python 3.9, standard library only.

    agent_board.py --root <main repo> --state-dir <git toplevel of the cwd> --cwd <cwd>
                   --now "YYYY-MM-DD HH:MM" --lang <zh|en> --host <machine> [--self] [--watch <sec>]

Read only: it writes nothing. One file, no imports of sibling modules, so no __pycache__ is written.
Prints one GitHub markdown table (or one line "无" / "none"), then note lines.

Rows (whole repo): every line of agent_todo.txt; every human-direct line of agent_worktree.txt ("<repo> Helper");
the state lines (OWNER TODO, PARKED, WORKER) of the main repo's agent_state.txt and of every agent_worktree.txt
folder that is on this machine (a folder that is not here: a note line after the table).
Progress column: the "stage <stage>[ <i>/<m>] since <date>" field of a todo line (--self: else the "STAGE <name>:"
line of its own agent_state.txt) gives a bar by the stage weights of agent.conf (template agent.conf.default next to
this script for a missing or bad key). The parse, progress and done-by functions are plain module functions (a status
line can call them). --watch <sec>: redraw every <sec> seconds until Ctrl-C.
    agent_board.py --statusline    (stdin: Claude Code's session JSON) one status line of the tasks with a stage, or nothing;
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
from fractions import Fraction

DATE = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
FMT = "%Y-%m-%d %H:%M"
HELPER_ROLE = "task manager, human-direct"

HEAD = {
    "zh": ["任务", "内容", "状态", "进度", "位置", "估时", "已工作", "已等待", "预计完成"],
    "en": ["Task", "What", "Status", "Progress", "Where", "Est", "Work", "Wait", "Done by"],
}
STATUS = {
    "zh": {"mock": "等你：看样稿", "question": "等你：回答问题", "review": "等你：验收",
           "running": "进行中", "hold": "暂缓", "queue": "排队中", "owner": "你的待办",
           "parked": "搁置的问题"},
    "en": {"mock": "waits on you: mock check", "question": "waits on you: question",
           "review": "waits on you: review", "running": "running", "hold": "held",
           "queue": "queued", "owner": "your to-do", "parked": "parked question"},
}
# sort groups: waiting on the owner, running, held or queued, OWNER TODO, parked
G_OWNER_WAIT, G_RUNNING, G_HELD, G_OWNER_TODO, G_PARKED = 0, 1, 2, 3, 4
KIND_GROUP = {"mock": G_OWNER_WAIT, "question": G_OWNER_WAIT, "review": G_OWNER_WAIT,
              "hold": G_HELD, "queue": G_HELD}
WHAT_MAX = 60
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


def collapse(text):
    return " ".join(str(text).split())


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


def stage_progress(weights, stage):
    """Fraction 0..1 of the stage (stage = (name, i, m)), or None when the weights sum to 0 or no stage."""
    if not stage:
        return None
    total = sum(weights.values())
    if total <= 0:
        return None
    name, i, m = stage
    done = sum(weights[s] for s in STAGES[:STAGES.index(name)])
    p = Fraction(done, 1)
    if name == "workers" and m:
        p += Fraction(weights["workers"] * i, m)
    return p / total


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

    def done_by(self, est, work, stage=None):
        return done_by_text(self.lang, self.now, est, work, stage_progress(self.weights, stage), self.eta_min_pct)

    def progress_cell(self, stage):
        p = stage_progress(self.weights, stage)
        return "-" if p is None else bar_text(p)

    # -- rows

    def add(self, group, when, task, what, status, where, est="-", work="-", wait="-", done="-", progress="-"):
        """when: "YYYY-MM-DD HH:MM" or None (no date sorts last, file order)."""
        self.seq += 1
        key = (group, 0 if when else 1, when or "", self.seq)
        cells = [cell(task), cell(cut_what(what)), cell(status), progress.replace("|", "\\|"), cell(where), cell(est),
                 cell(work), cell(wait), cell(done)]
        self.rows.append((key, cells))

    # -- the todo lines

    def parse_todo(self, line):
        f = line.split(" | ")
        t = {"name": f[0].strip(), "what": f[2] if len(f) > 2 else "", "est": None,
             "opened": None, "wkind": None, "wsince": None, "wnote": "", "waited": 0,
             "machine": None, "path": None, "stage": None}
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
            m = re.match(r"stage (\S+(?: \d+/\d+)?) since %s" % DATE, x)
            if m and t["stage"] is None:
                t["stage"] = parse_stage(m.group(1))
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

    def todo_row(self, t, wt_lines, own_dir=None):
        opened = parse_time(t["opened"]) if t["opened"] else None
        wsince = parse_time(t["wsince"]) if t["wsince"] else None
        wait = t["waited"]
        if wsince is not None:
            wait += minutes(wsince, self.now)
        clock = minutes(opened, self.now)
        work = None if clock is None else max(0, clock - wait)
        kind = t["wkind"] if t["wkind"] in KIND_GROUP else None
        status = self.word(kind or "running")
        if kind and t["wnote"]:
            status += " · " + t["wnote"]
        group = KIND_GROUP.get(kind, G_RUNNING)
        if kind:
            when = t["wsince"]
        else:
            when = t["opened"]
        if t["machine"]:
            where = t["machine"] + (", " + short_path(t["path"], self.home) if t["path"] else "")
        else:
            where = self.worktree_where(t["name"], wt_lines)
            if where is None:
                where = self.where_here(own_dir) if own_dir else "-"
        self.add(group, when, t["name"], t["what"] or "-", status, where,
                 est=fmt_min(t["est"]), work=fmt_min(work), wait=fmt_min(wait),
                 done=self.done_by(t["est"], work, t["stage"]), progress=self.progress_cell(t["stage"]))

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
        """The stage of the "STAGE <name>:" line of this folder's agent_state.txt, or None."""
        found = None
        for line in read_lines(os.path.join(self.state_dir, "agent_state.txt")):
            m = re.match(r"STAGE %s: (.*?)(?: \| since %s)?\s*$" % (re.escape(name), DATE), line)
            if m:
                found = parse_stage(m.group(1))
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
                    t["stage"] = self.own_stage(name)
                self.todo_row(t, wt_lines, own_dir=folder)
                found = True
                break
        if not found and not in_root:
            line = self.own_todo_line()
            if line:
                t = self.parse_todo(line)
                if t["name"]:
                    if t["stage"] is None:
                        t["stage"] = self.own_stage(t["name"])
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

    # -- print

    def render(self):
        if not self.rows:
            out = ["无" if self.lang == "zh" else "none"]
            out += self.notes
            return "\n".join(out) + "\n"
        out = ["| " + " | ".join(HEAD[self.lang]) + " |", "|" + "---|" * len(HEAD[self.lang])]
        for _, cells in sorted(self.rows, key=lambda r: r[0]):
            out.append("| " + " | ".join(cells) + " |")
        if self.notes:
            out.append("")
            out += self.notes
        return "\n".join(out) + "\n"


def build(args, now=None):
    """One fresh Board for these args (now: "YYYY-MM-DD HH:MM", else args.now)."""
    if now is not None:
        args = argparse.Namespace(**dict(vars(args), now=now))
    board = Board(args)
    if args.self_mode:
        board.own_view()
    else:
        board.whole_repo()
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


def statusline_text(stdin_text):
    """The status line: one line "<name> <bar> <p>% <done by>" per task with a stage, joined by " · "; "" for none."""
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
    board = build(args)
    parts = []
    for _, cells in sorted(board.rows, key=lambda r: r[0][3]):
        if cells[3] == "-":
            continue
        part = "%s %s" % (cells[0], collapse(cells[3]))
        if cells[8] != "-":
            part += " " + cells[8]
        parts.append(part)
    return " · ".join(parts)


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
