#!/usr/bin/env python3
"""agent_watch.py - the all mode of bin/agent-watch.sh (requirements/one-watcher.md, rows A, B).

    python3 agent_watch.py --all [--interval-min 5] [--max <n>]

One watcher for every task manager (TM) of this repo: it re-reads the targets (agent_worktree.txt,
agent_todo.txt) every sweep, reads each TM pane and its agent_state.txt (local: the file; another
machine: one short command through the task's shell pane), prints one sweep line, then one WATCH line
per event and exits 0. The TM pane is only read, never sent to.
After each sweep, for the main manager only (no AGENT_ROLE, a live main-manager lock), it runs
bin/agent-housekeep.sh --apply when housekeep_interval_min minutes (the setting, 0 = off, default 120)
have passed since <git dir>/agent_housekeep.last.

The functions that find a task's targets and panes (read_targets, locate, resolve_tm, resolve_shell,
orca) are plain module functions on a Ctx, so another command (tell) can reuse them.

Env: AGENT_WATCH_INTERVAL_S  seconds between sweeps, wins over --interval-min.
"""

import datetime
import fcntl
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

WAKE = re.compile(r"^(\[[^\]]*\] )?(DONE (PASS|FAIL)|CLOSE CASE|QUESTION:|MOCK READY)")
ANSWER = re.compile(r"^ *(\[[^\]]*\] +)?ANSWER:")
TELL_LINE = re.compile(r"^TELL [0-9a-f]{8} ")
LOGIN_TEXTS = ("Please run /login", "OAuth token has expired", "Invalid API key", "API Error: 401")
GONE_CODES = ("terminal_handle_stale", "terminal_not_found")
BOX_CHARS = " \t\u2502\u2503\u256d\u256e\u2570\u256f\u2500\u250c\u2510\u2514\u2518\u251c\u2524\u2551\u2550\u2554\u2557\u255a\u255d"
DEFAULT_MAX = 20
LAST_CUT = 100
REMOTE_CMD_MAX = 500        # the one remote read command: shorter than this or the task is not watched (R1)


# ---------------------------------------------------------------- small helpers


def out(text=""):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def hhmm():
    """The time from `date` (a test stubs it)."""
    try:
        r = subprocess.run(["date", "+%H:%M"], capture_output=True, text=True, timeout=10)
        v = r.stdout.strip()
        if r.returncode == 0 and re.match(r"^\d\d:\d\d$", v):
            return v
    except (OSError, subprocess.SubprocessError):
        pass
    return time.strftime("%H:%M")


def now_text():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def parse_time(text):
    try:
        return datetime.datetime.strptime((text or "")[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError, TypeError):
        return False
    return True


def read_text(path):
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    except OSError:
        return None


def norm(path):
    try:
        return os.path.realpath(path)
    except (OSError, ValueError):
        return path


def under(path, root):
    if not path or not root:
        return False
    for p in {path, norm(path)}:
        for r in {root, norm(root)}:
            if p == r or p.startswith(r.rstrip("/") + "/"):
                return True
    return False


def same_path(a, b):
    return bool(a) and bool(b) and (a == b or norm(a) == norm(b))


def run_git(args, cwd):
    try:
        r = subprocess.run(["git", "-C", cwd] + args, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout if r.returncode == 0 else ""


class ShellLock:
    """R16: one fcntl lock per shell pane, <git common dir>/agent_shell_<handle>.lock. Waits up to 120 s,
    then goes on without it (a hung holder must not stop the watch)."""

    def __init__(self, gitdir, handle):
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", handle or "none")
        self.gitdir, self.path, self.fh = gitdir, os.path.join(gitdir, "agent_shell_%s.lock" % safe), None

    def __enter__(self):
        try:
            os.makedirs(self.gitdir, exist_ok=True)
            self.fh = open(self.path, "a")
        except OSError:
            return self
        deadline = time.time() + 120
        while True:
            try:
                fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.time() > deadline:
                    break
                time.sleep(0.1)
        return self

    def __exit__(self, *exc):
        if self.fh:
            self.fh.close()
        return False


# ---------------------------------------------------------------- orca


class Reply:
    def __init__(self, ok, data=None, err="", code=""):
        self.ok, self.data, self.err, self.code = ok, data, err, code

    def result(self):
        if isinstance(self.data, dict) and isinstance(self.data.get("result"), dict):
            return self.data["result"]
        return {}


def orca(args, timeout=60):
    """One orca call -> Reply. err: the error code/message from the JSON on stdout, else stderr,
    else "<what> exit <rc>"."""
    what = "orca " + " ".join(args[:2])
    try:
        p = subprocess.run(["orca"] + list(args), capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return Reply(False, err="orca: not found")
    except subprocess.TimeoutExpired:
        return Reply(False, err="orca: %s timed out" % " ".join(args[:2]))
    except OSError as e:
        return Reply(False, err="orca: %s" % e)
    data = None
    try:
        data = json.loads(p.stdout)
    except ValueError:
        pass
    if p.returncode == 0 and isinstance(data, dict) and data.get("ok") is not False:
        return Reply(True, data)
    code = msg = ""
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        code = str(data["error"].get("code") or "")
        msg = code or str(data["error"].get("message") or "")
    if not msg:
        msg = " ".join(p.stderr.split())[:300]
    if not msg:
        msg = "%s exit %d" % (what, p.returncode)
    return Reply(False, data, msg, code)


def env_args(env):
    return ["--environment", env] if env else []


def term_read(env, handle, cursor=None):
    args = ["terminal", "read"] + env_args(env) + ["--terminal", handle]
    if cursor:
        args += ["--cursor", cursor]
    return orca(args + ["--json"])


def terminal_of(reply):
    t = reply.result().get("terminal")
    return t if isinstance(t, dict) else None


def tail_of(term):
    tail = term.get("tail")
    if isinstance(tail, str):
        return tail.split("\n")
    return [str(x) for x in (tail or [])]


def exit_cause_text(env, handle):
    """B11: "(<kind>, exit <code>)" from `terminal wait --for exit`, or "(cause unknown)"."""
    r = orca(["terminal", "wait"] + env_args(env) + ["--terminal", handle, "--for", "exit",
                                                      "--timeout-ms", "2000", "--json"], timeout=30)
    if r.ok:
        w = r.result().get("wait")
        if isinstance(w, dict) and isinstance(w.get("exitCause"), dict) and w["exitCause"].get("kind"):
            code = w.get("exitCode")
            return "(%s, exit %s)" % (w["exitCause"]["kind"], "?" if code is None else code)
    return "(cause unknown)"


# ---------------------------------------------------------------- the project


class Ctx:
    def __init__(self, cwd=None):
        start = os.environ.get("CLAUDE_PROJECT_DIR") or cwd or os.getcwd()
        if not os.path.isdir(start):
            start = os.getcwd()
        self.cwd = norm(start)
        main = ""
        for line in run_git(["worktree", "list", "--porcelain"], self.cwd).splitlines():
            if line.startswith("worktree "):
                main = line[9:].strip()
                break
        self.main = main or self.cwd
        gd = run_git(["rev-parse", "--path-format=absolute", "--git-common-dir"], self.cwd).strip()
        self.gitdir = gd or os.path.join(self.main, ".auto-pipeline")
        self.status_path = os.path.join(self.gitdir, "agent_watch.json")

    def file(self, name):
        return os.path.join(self.main, name)

    def git_worktrees(self):
        paths = []
        for line in run_git(["worktree", "list", "--porcelain"], self.main).splitlines():
            if line.startswith("worktree "):
                paths.append(line[9:].strip())
        return paths


def read_lines(path):
    text = read_text(path)
    return [l.rstrip("\r") for l in text.split("\n")] if text else []


class Target:
    def __init__(self, name, path, machine=""):
        self.name, self.path, self.machine = name, path, machine


def read_targets(ctx):
    """A1: [Target] in order: worktree lines (working, final), then todo lines with an `on` field."""
    todo_on = {}
    todo_names = []
    for line in read_lines(ctx.file("agent_todo.txt")):
        parts = line.split(" | ")
        name = parts[0].strip()
        if not name or name.startswith("#"):
            continue
        todo_names.append(name)
        for f in parts[3:]:
            if f.startswith("on "):
                machine, _, path = f[3:].strip().partition(" ")
                if name not in todo_on:
                    todo_on[name] = (machine.strip(), path.strip())
                break
    targets, wt_names = [], set()
    for line in read_lines(ctx.file("agent_worktree.txt")):
        parts = [p.strip() for p in line.split(" | ")]
        if len(parts) < 3 or not parts[0] or not parts[1]:
            continue
        path, name, status = parts[0], parts[1], parts[2]
        if name.startswith("task manager, human-direct") or name in wt_names:
            continue
        wt_names.add(name)
        if status in ("working", "final"):
            targets.append(Target(name, path, todo_on.get(name, ("", ""))[0]))
    for name in todo_names:
        if name in wt_names or name not in todo_on:
            continue
        machine, path = todo_on[name]
        if machine and path:
            wt_names.add(name)
            targets.append(Target(name, path, machine))
    return targets


def launch_records(ctx, task):
    """The LAUNCH records of a task from the main repo's agent_state.txt, oldest first by `since`."""
    recs = []
    for i, line in enumerate(read_lines(ctx.file("agent_state.txt"))):
        if not line.startswith("LAUNCH "):
            continue
        key, sep, rest = line[7:].partition(": ")
        parts = rest.split(" | ")
        if not sep or len(parts) < 3:
            continue
        if not parts[1].startswith("task ") or parts[1][5:].strip() != task:
            continue
        rec = {"kind": parts[0].strip(), "since": "", "pid": None, "pane": "", "env": "", "i": i}
        for f in parts[3:]:
            k, _, v = f.strip().partition(" ")
            if k in ("since", "pane", "env"):
                rec[k] = v.strip()
            elif k == "pid" and v.strip().isdigit():
                rec["pid"] = int(v.strip())
        recs.append(rec)
    recs.sort(key=lambda r: (r["since"], r["i"]))
    return recs


def list_terminals(env, path):
    r = orca(["terminal", "list"] + env_args(env) + ["--worktree", "path:" + path, "--json"])
    if not r.ok:
        return []
    terms = r.result().get("terminals")
    if not isinstance(terms, list):
        return []
    return [t for t in terms if isinstance(t, dict) and t.get("handle")
            and t.get("connected") is not False and t.get("orphaned") is not True]


def locate(ctx, target):
    """A3: ("", None) local, (env, None) remote, (None, why) not watched."""
    if os.path.isdir(target.path):
        return "", None
    recs = [r for r in launch_records(ctx, target.name)
            if r["kind"] == "tm-pane" and r["env"] and r["pid"] and pid_alive(r["pid"])]
    env = recs[-1]["env"] if recs else target.machine
    if not env:
        return None, "folder not here and no machine known"
    return env, None


def resolve_tm(ctx, target, env, skip=()):
    """A4: the TM pane handle or None. Newest live tm-pane record, else the terminal list."""
    recs = [r for r in launch_records(ctx, target.name)
            if r["kind"] == "tm-pane" and r["env"] == (env or "") and r["pane"] and r["pane"] not in skip
            and r["pid"] and pid_alive(r["pid"])]
    if recs:
        return recs[-1]["pane"]
    terms = [t for t in list_terminals(env, target.path) if t["handle"] not in skip]
    for t in terms:
        if "Task Manager" in str(t.get("title") or ""):
            return t["handle"]
    claude = [t for t in terms if t.get("agentIdentity") == "claude"]
    if len(claude) == 1:
        return claude[0]["handle"]
    return helper_pane(ctx, target, env, skip)


def task_slug(text):
    """A Helper's task name as a todo name: lower case, runs of other characters -> "-"."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def helper_pane(ctx, target, env, skip=()):
    """A task with no task manager pane, named by a human-direct Helper's "task: <Task Name>" line: the live pane
    of that Helper (its title holds "Helper - <Task Name>") among the terminals of the Helper's own folder."""
    if env:
        return None
    for line in read_lines(ctx.file("agent_worktree.txt")):
        parts = [p.strip() for p in line.split(" | ")]
        if len(parts) < 3 or not parts[0] or not parts[1].startswith("task manager, human-direct"):
            continue
        if not parts[2].startswith("task:"):
            continue
        task = parts[2][5:].strip()
        if not task or task_slug(task) != target.name:
            continue
        for t in list_terminals("", parts[0]):
            if t["handle"] not in skip and "Helper - %s" % task in str(t.get("title") or ""):
                return t["handle"]
    return None


def resolve_shell(ctx, target, env, tm_handle="", skip=()):
    """A5: the shell pane handle (remote only) or None."""
    recs = [r for r in launch_records(ctx, target.name)
            if r["kind"] == "shell-pane" and r["env"] == env and r["pane"] and r["pane"] not in skip]
    if recs:
        return recs[-1]["pane"]
    cands = [t for t in list_terminals(env, target.path)
             if not t.get("agentIdentity") and t["handle"] not in skip and t["handle"] != tm_handle]
    for t in cands:
        if str(t.get("title") or "") == "%s shell" % target.name:
            return t["handle"]
    for t in cands:
        if "shell" in str(t.get("title") or "").lower():
            return t["handle"]
    return cands[0]["handle"] if cands else None


def no_shell_why(env, target):
    return ('no shell pane on %s; open one: orca terminal create --environment %s --worktree path:%s '
            '--title "%s shell"' % (env, env, target.path, target.name))


# ---------------------------------------------------------------- reading the state file


def scan_state(text):
    """(n wake lines, line count, last wake line, waiting 0|1|2, every wake line)."""
    n, last, w, wakes = 0, "", 0, []
    lines = text.split("\n")
    count = len(lines) - (1 if lines and lines[-1] == "" else 0)
    for line in lines[:count]:
        line = line.rstrip("\r")
        m = WAKE.match(line)
        if m:
            n += 1
            last = line
            wakes.append(line)
            w = 1 if m.group(2)[0] in "QM" else 2
        elif TELL_LINE.match(line):
            w = 0
        elif ANSWER.match(line):
            if w == 1:
                w = 0
    return n, count, last, w, wakes


STEP_STAGES = ["brief", "register", "mock", "tests", "workers", "verify", "push", "report"]
HEARTBEAT_LINE = re.compile(r"^HEARTBEAT (\S+): step ([0-7]) of 7, work (\d+)m, (.*?)(?: \| .*)?$")
STEP_LINE = re.compile(r"^STEP ([0-7])\b")


def progress_of_line(line, name):
    """(stage, beat) of one state line, or None when it says nothing about this task's stage.
    STAGE <name>: <stage>[ <i>/<m>] | since ...; HEARTBEAT <name>: step <n> of 7, work <m>m, <text> [| date]
    (beat "<m>m <text>"); STEP <n> <word>: ... (n = 0..7: brief register mock tests workers verify push report)."""
    line = line.rstrip("\r")
    prefix = "STAGE %s: " % name
    if line.startswith(prefix):
        return re.sub(r" \| since.*", "", line[len(prefix):]), ""
    m = HEARTBEAT_LINE.match(line)
    if m and m.group(1) == name:
        return STEP_STAGES[int(m.group(2))], ("%sm %s" % (m.group(3), m.group(4))).strip()
    m = STEP_LINE.match(line)
    if m:
        return STEP_STAGES[int(m.group(1))], ""
    return None


def stage_of(text, name):
    """(stage, beat) of the newest (last) STAGE, HEARTBEAT or STEP line of this task; ("", "") when none."""
    value, full = ("", ""), ""
    for line in text.split("\n"):
        got = progress_of_line(line, name)
        if got:
            if line.startswith("STAGE "):
                full = got[0]
            elif full.split()[:1] == [got[0]]:
                got = (full, got[1])        # a heartbeat of the stage the STAGE line named keeps its "<i>/<m>"
            value = got
    return value


def remote_command(path):
    """The one short command: FSIG <n> <lines> <waiting> <1 when the newest such line says "started"> <newest
    VALID STAGE|HEARTBEAT|STEP line (a malformed one is skipped, C50)>|<last wake line> FEND (R1: no task name in it; Python picks the task's own stage). Under 500 chars or the task is not watched
    (R1: a send is cut only near 4 KB (W16), the tell chunks are 300; a path of 140 chars must fit)."""
    return ("awk -F' [|] ' '/^([[][^]]*[]] )?(DONE (PASS|FAIL)|CLOSE CASE|QUESTION:|MOCK READY)/"
            "{n++;l=$0;w=/^([[][^]]*[]] )?[QM]/?1:2}/^TELL |^ *([[][^]]*[]] +)?ANSWER:/{if(w==1||/^T/)w=0}"
            "/^(STAGE [^ ]+: |HEARTBEAT [^ ]+: step [0-7] of 7, work [0-9]+m, |STEP [0-7] )/{v=substr($1,1,99);t=/tarted/}"
            "END{print \"FSIG\",n,NR,w,t+0,v \"|\" substr(l,1,%d),\"FEND\"}' %s"
            % (LAST_CUT, shlex.quote(path + "/agent_state.txt")))


FSIG = re.compile(r"^FSIG (\d*) (\d+) (\d*) ([01]) (.*) FEND$")


class Obs:
    """One read cycle of a target."""

    def __init__(self, kind, err="", lines=None):
        self.kind, self.err, self.lines = kind, err, lines or []
        self.fn = self.fl = self.w = 0
        self.last = self.stage = self.beat = ""
        self.started = False
        self.wakes = []
        self.exited = False


# ---------------------------------------------------------------- the engine


class Task:
    def __init__(self, target):
        self.name, self.path, self.machine = target.name, target.path, target.machine
        self.env = ""
        self.pane = self.shell = ""
        self.listed_pane = self.listed_shell = ""
        self.gone = set()
        self.watched, self.why = False, ""
        self.based = False
        self.base = None            # reported wake line count
        self.last = None            # last wake line seen (R13)
        self.lost = set()           # pane handles already reported LOST (R3)
        self.prev_ok, self.prev_screen, self.prev_fp = False, "", None
        self.same = self.idle = self.fails = 0
        self.laststage = self.lastbeat = ""
        self.confirmed = self.changed = ""
        self.stall_reason, self.stall_screen, self.stall_fp = "", "", None
        self.urgent = False


class Engine:
    def __init__(self, ctx, interval_s, interval_min, max_sweeps):
        self.ctx, self.iv, self.interval_min, self.max = ctx, interval_s, interval_min, max_sweeps
        self.tasks = {}
        self.saved = {}
        self.started = now_text()
        self.sweep_time = self.started
        self.printed_why = {}
        self.orphans = []
        self.orphans_printed = set()
        self.repo_id = ""
        self.slots = []

    # ---- status file

    def load_status(self):
        text = read_text(self.ctx.status_path)
        try:
            data = json.loads(text) if text else {}
        except ValueError:
            data = {}
        return data if isinstance(data, dict) else {}

    def write_status(self):
        tasks = {}
        for name, t in self.tasks.items():
            stall = ""
            if t.stall_reason:
                stall = t.stall_reason + "\n" + t.stall_screen
            old = self.saved.get(name) or {}
            tasks[name] = {
                "path": t.path, "env": t.env, "pane": t.pane, "shell": t.shell, "watched": t.watched,
                "why": t.why,
                "signals": t.base if t.base is not None else (old.get("signals")
                                                              if isinstance(old.get("signals"), int) else None),
                "last": t.last if t.last is not None else old.get("last"),
                "confirmed": t.confirmed or old.get("confirmed") or "",
                "changed": t.changed or old.get("changed") or "", "stall": stall,
                "stall_file": list(t.stall_fp) if t.stall_fp else None,
                "lines": t.prev_fp[1] if t.prev_fp else old.get("lines"),
                "lost": sorted(t.lost),
            }
        data = {"pid": os.getpid(), "started": self.started, "sweep": self.sweep_time,
                "interval_min": self.interval_min, "tasks": tasks, "orphans": self.orphans,
                "slots": list(self.slots)}
        self.dump_status(data)

    def dump_status(self, data):
        try:
            os.makedirs(self.ctx.gitdir, exist_ok=True)
            tmp = "%s.tmp.%d" % (self.ctx.status_path, os.getpid())
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.ctx.status_path)
        except OSError as e:
            out("%s watch: cannot write %s: %s" % (hhmm(), self.ctx.status_path, e))

    # ---- B15

    def replace_older(self):
        st = self.load_status()
        pid = st.get("pid")
        if not isinstance(pid, int) or pid == os.getpid() or not pid_alive(pid):
            return
        last = parse_time(st.get("sweep"))
        try:
            im = float(st.get("interval_min") or 5)
        except (TypeError, ValueError):
            im = 5.0
        if last is None or (datetime.datetime.now() - last).total_seconds() > (2 * im + 2) * 60:
            return
        try:
            args = subprocess.run(["ps", "-o", "args=", "-p", str(pid)], capture_output=True, text=True,
                                  timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            return
        if ("agent-watch" in args or "agent_watch" in args) and "--all" in args:
            st["pid"] = os.getpid()          # R9: the replaced watch reads who replaced it
            self.dump_status(st)
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                return
            out("watch --all: replaced pid %d" % pid)
            time.sleep(0.3)

    # ---- targets

    def refresh(self, t):
        """A3-A5: where the task is and its panes. Sets env, pane, shell, watched, why."""
        ctx = self.ctx
        env, why = locate(ctx, t)
        if why:
            self.mark(t, "", "", "", False, why)
            return
        t.env = env
        if env:
            n = len(remote_command(t.path))
            if n >= REMOTE_CMD_MAX:
                self.mark(t, env, "", "", False, "read command too long (%d chars)" % n)
                return
        pane = resolve_tm_cached(ctx, t, env)
        if not pane:
            self.mark(t, env, "", "", False, "no task manager pane")
            return
        shell = ""
        if env:
            shell = resolve_shell_cached(ctx, t, env, pane)
            if not shell:
                self.mark(t, env, pane, "", False, no_shell_why(env, t))
                return
        self.mark(t, env, pane, shell, True, "")

    def mark(self, t, env, pane, shell, watched, why):
        t.env, t.pane, t.shell, t.watched, t.why = env, pane, shell, watched, why
        if watched:
            self.printed_why.pop(t.name, None)
        elif self.printed_why.get(t.name) != why:
            self.printed_why[t.name] = why
            out("%s watch: %s not watched: %s" % (hhmm(), t.name, why))

    def prepare(self, initial):
        """Re-read the targets; baseline every new watched one. Returns the tasks baselined now."""
        targets = read_targets(self.ctx)
        names = [x.name for x in targets]
        for name in list(self.tasks):
            if name not in names:
                del self.tasks[name]
                self.saved.pop(name, None)
                self.printed_why.pop(name, None)
        ordered = {}
        fresh = []
        for x in targets:
            t = self.tasks.get(x.name)
            if t is None:
                t = Task(x)
                t.lost = set((self.saved.get(x.name) or {}).get("lost") or [])
            else:
                t.path, t.machine = x.path, x.machine
            ordered[x.name] = t
        self.tasks = ordered
        for t in self.tasks.values():
            self.refresh(t)
            if t.watched and not t.based:
                self.baseline(t)
                if not initial:
                    out("%s watch: + %s" % (hhmm(), t.name))
                    fresh.append(t.name)
        return fresh

    # ---- reading

    def read_tm(self, t):
        """The TM pane read with A6: -> (Reply, terminal dict or None)."""
        for attempt in (0, 1):
            r = term_read(t.env, t.pane)
            if r.ok:
                term = terminal_of(r)
                return r, term
            if r.code in GONE_CODES and attempt == 0:
                t.gone.add(t.pane)
                t.listed_pane = ""
                new = resolve_tm(self.ctx, t, t.env, t.gone)
                if new and new != t.pane:
                    t.pane = new
                    continue
            return r, None
        return r, None

    def shell_exchange(self, t, cmd):
        """Send cmd through the shell pane under its lock, read the answer with --cursor
        -> (FSIG match or None, err). A shell pane that is gone or not running is resolved once more (A6, R10)."""
        r = None
        for attempt in (0, 1):
            with ShellLock(self.ctx.gitdir, t.shell):
                r = term_read(t.env, t.shell)
                term = terminal_of(r) if r.ok else None
                status = (term or {}).get("status")
                bad = (not r.ok and r.code in GONE_CODES) or (r.ok and status is not None and status != "running")
                if not bad:
                    if not r.ok:
                        return None, r.err
                    return self.shell_send_read(t, cmd, r)
            if attempt == 0:
                t.gone.add(t.shell)
                t.listed_shell = ""
                new = resolve_shell(self.ctx, t, t.env, t.pane, t.gone)
                if new and new != t.shell:
                    t.shell = new
                    continue
            break
        return None, r.err if not r.ok else "shell pane exited"

    def shell_send_read(self, t, cmd, r):
        cursor = str((terminal_of(r) or {}).get("latestCursor") or "")
        if not cursor:
            return None, "no latestCursor in the shell pane read"
        s = orca(["terminal", "send"] + env_args(t.env) + ["--terminal", t.shell, "--text", cmd, "--enter",
                                                           "--json"])
        if not s.ok:
            return None, s.err
        for _ in range(20):
            a = term_read(t.env, t.shell, cursor)
            if not a.ok:
                return None, a.err
            hit = None
            for line in tail_of(terminal_of(a) or {}):
                m = FSIG.match(line.replace("\r", ""))
                if m:
                    hit = m
            if hit:
                return hit, ""
            time.sleep(0.5)
        return None, "no FSIG marker line in the shell pane"

    def observe(self, t):
        """One read cycle. R3: an exited pane still gets its state file read (o.exited)."""
        r, term = self.read_tm(t)
        if not r.ok:
            return Obs("fail", r.err)
        if term is None:
            return Obs("fail", "no result.terminal in the TM pane read")
        lines = tail_of(term)
        status = term.get("status")
        exited = status is not None and status != "running"
        o = Obs("ok", lines=lines)
        o.exited = exited
        if not t.env:
            f = os.path.join(t.path, "agent_state.txt")
            text = read_text(f)
            if text is None:
                return Obs("exited", lines=lines) if exited else Obs("fail", "cannot read %s" % f, lines)
            o.fn, o.fl, o.last, o.w, o.wakes = scan_state(text)
            o.stage, o.beat = stage_of(text, t.name)
            body = [l for l in text.split("\n") if l.strip()]
            o.started = bool(body) and "tarted" in body[-1]
            return o
        hit, err = self.shell_exchange(t, remote_command(t.path))
        if hit is None:
            return Obs("exited", lines=lines) if exited else Obs("fail", err, lines)
        o.fn, o.fl, o.w = int(hit.group(1) or 0), int(hit.group(2)), int(hit.group(3) or 0)
        o.started = hit.group(4) == "1"
        v, _, o.last = hit.group(5).partition("|")
        o.stage, o.beat = progress_of_line(v, t.name) or ("", "")
        return o

    def run_todo(self, args):
        """agent-file.sh todo <args> in the main repo -> (ok, first line of the message)."""
        cmd = [os.path.join(HERE, "agent-file.sh"), "todo"] + args
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=self.ctx.main, timeout=60,
                               stdin=subprocess.DEVNULL)
            ok, msg = r.returncode == 0, (r.stderr or r.stdout)
        except (OSError, subprocess.SubprocessError) as e:
            ok, msg = False, str(e)
        return ok, (msg.strip().splitlines() or [""])[0][:150]

    def carry_stage(self, t, stage, beat=""):
        """The newest STAGE, HEARTBEAT or STEP line of the task goes into the main repo's todo line (the main repo
        is the brain): its stage by todo stage, a heartbeat's "<m>m <text>" by todo beat."""
        if stage and stage != t.laststage:
            old = t.laststage.split()
            # a heartbeat knows only the stage word: it keeps the carried "workers <i>/<m>"
            keep = len(old) == 2 and stage == old[0]
            if not keep:
                t.laststage, t.lastbeat = stage, ""
                ok, msg = self.run_todo(["stage", t.name] + stage.split()[:2])
                if ok:
                    out("%s stage %s: %s" % (hhmm(), t.name, stage))
                else:
                    out("%s stage %s: not carried (%s)" % (hhmm(), t.name, msg))
        if beat and beat != t.lastbeat:
            t.lastbeat = beat
            ok, msg = self.run_todo(["beat", t.name, beat])
            if ok:
                out("%s beat %s: %s" % (hhmm(), t.name, beat))
            else:
                out("%s beat %s: not carried (%s)" % (hhmm(), t.name, msg))

    def baseline(self, t):
        """The first read of a task: file signals already there are the baseline (B5, R2, R13)."""
        t.based = True
        saved = self.saved.get(t.name) or {}
        o = self.observe(t)
        sig = saved.get("signals")
        if o.kind == "exited" or (o.kind == "ok" and o.exited):
            if t.pane not in t.lost:
                t.urgent = True
        if o.kind != "ok":
            if isinstance(sig, int):
                t.base = sig
                if isinstance(saved.get("last"), str):
                    t.last = saved["last"]
            self.load_stall(t, saved)
            return
        self.carry_stage(t, o.stage, o.beat)
        if isinstance(sig, int):
            if o.fn < sig:
                t.base, t.last = o.fn, o.last
            else:
                t.base = sig
                t.last = saved["last"] if isinstance(saved.get("last"), str) else o.last
        else:
            t.base, t.last = o.fn, o.last
        if o.fn > t.base or (o.fn == t.base and o.last[:LAST_CUT] != (t.last or "")[:LAST_CUT]):
            t.urgent = True
        screen = "\n".join(o.lines)
        t.prev_ok, t.prev_screen, t.prev_fp = True, screen, (o.fn, o.fl)
        t.confirmed = now_text()
        t.changed = ""
        if saved.get("changed") and saved.get("lines") == o.fl:
            t.changed = saved["changed"]
        elif not t.env:
            try:
                m = os.path.getmtime(os.path.join(t.path, "agent_state.txt"))
                t.changed = datetime.datetime.fromtimestamp(m).strftime("%Y-%m-%d %H:%M")
            except OSError:
                pass
        if not t.changed:
            t.changed = t.confirmed
        self.load_stall(t, saved)
        if t.stall_reason and not stall_held(t, screen, t.prev_fp):
            t.stall_reason = ""

    def load_stall(self, t, saved):
        s = saved.get("stall")
        if isinstance(s, str) and s:
            t.stall_reason, _, t.stall_screen = s.partition("\n")
            sf = saved.get("stall_file")
            t.stall_fp = tuple(sf) if isinstance(sf, list) and len(sf) == 2 else None

    # ---- one sweep

    def lost(self, t, events):
        """R3: LOST once per pane handle."""
        if t.pane not in t.lost:
            t.lost.add(t.pane)
            events.append(("WATCH LOST %s: pane exited %s" % (t.name, exit_cause_text(t.env, t.pane)), None))
        return "lost"

    def evaluate(self, t, o, events):
        """Folds one Obs into the task; returns the state word of the sweep line."""
        if o.kind == "exited":
            return self.lost(t, events)
        if o.kind == "fail":
            t.fails += 1
            if t.fails >= 3:
                events.append(("WATCH LOST %s: %s" % (t.name, o.err), None))
            return "fail %d/3" % t.fails
        t.fails = 0
        self.carry_stage(t, o.stage, o.beat)
        now = now_text()
        t.confirmed = now
        screen = "\n".join(o.lines)
        fp = (o.fn, o.fl)
        if t.prev_fp is not None and fp != t.prev_fp:
            t.changed = now
        elif not t.changed:
            t.changed = now
        file_same = t.prev_ok and fp == t.prev_fp
        shells = shells_running(screen) or self.run_started(t, o, now)
        if file_same and screen == t.prev_screen and not shells:
            t.same += 1
        else:
            t.same = 0
        idle_prompt = is_idle_prompt(o.lines)
        t.idle = t.idle + 1 if (idle_prompt and file_same and not shells) else 0
        t.prev_ok, t.prev_screen, t.prev_fp = True, screen, fp
        waiting = o.w > 0
        held_reason = ""
        if t.stall_reason:
            if stall_held(t, screen, fp):
                held_reason = t.stall_reason
            else:
                t.stall_reason = ""
        # wake lines (B5, R12, R13)
        fired, note = [], ""
        if t.base is None or o.fn < t.base:
            t.base, t.last = o.fn, o.last
        elif o.fn > t.base:
            k = o.fn - t.base
            if o.wakes:
                fired = o.wakes[t.base:o.fn]
            else:
                fired = [o.last]
                if k > 1:
                    note = "+%d earlier new wake line%s: read agent_state.txt" % (k - 1, "" if k == 2 else "s")
            t.base, t.last = o.fn, o.last
        elif t.last is not None and o.last[:LAST_CUT] != t.last[:LAST_CUT]:
            fired = [o.last]
            t.last = o.last
        else:
            t.last = o.last
        for i, line in enumerate(fired):
            ev = list(o.lines[-15:])
            if note and i == len(fired) - 1:
                ev = [note] + ev
            events.append(("WATCH SIGNAL %s: %s" % (t.name, line), ev))
        if o.exited:
            return self.lost(t, events)
        if not fired:
            reason = ""
            if login_expired(o.lines):
                reason = "login expired"
            elif not waiting:
                if idle_prompt and t.idle >= 2:
                    reason = "idle prompt"
                elif t.same >= 3:
                    reason = "no change"
            if reason and reason != held_reason:
                t.stall_reason, t.stall_screen, t.stall_fp = reason, screen, fp
                events.append(("WATCH STALL %s: %s" % (t.name, reason), o.lines[-15:]))
        if waiting:
            return "waiting"
        if t.idle > 0:
            return "idle %d" % t.idle
        if t.same > 0:
            return "same %d" % t.same
        return "ok"

    def run_started(self, t, o, now):
        """The newest state line says a background run started, and the file has not been quiet for watch_quiet_min
        yet: the manager waits for its own run, not stalled."""
        if not o.started:
            return False
        since = parse_time(t.changed)
        here = parse_time(now)
        return since is not None and here is not None and (here - since).total_seconds() / 60 < quiet_limit()

    def one_sweep(self):
        fresh = self.prepare(False)
        events, states = [], []
        for t in self.tasks.values():
            if not t.watched:
                states.append((t.name, "not watched"))
            elif t.name in fresh:
                states.append((t.name, "ok"))
            else:
                states.append((t.name, self.evaluate(t, self.observe(t), events)))
        self.scan_orphans()
        self.check_slots(events)
        self.sweep_time = now_text()
        out("%s sweep: %s" % (hhmm(), ", ".join("%s %s" % s for s in states) or "no targets"))
        self.write_status()
        for line, evidence in events:
            out(line)
            for l in evidence or []:
                out(l)
        return events

    # ---- the slot wake: a queued task that `agent-file.sh next` would start, said once

    def queued_names(self):
        """The names of the open todo lines with an open queue wait."""
        names = []
        for line in read_lines(self.ctx.file("agent_todo.txt")):
            parts = line.split(" | ")
            if parts[0].strip() and any(f.startswith("waiting queue ") or f == "waiting queue" for f in parts[3:]):
                names.append(parts[0].strip())
        return names

    def check_slots(self, events):
        try:
            queued = self.queued_names()
            self.slots = [n for n in self.slots if n in queued]
            if not queued:
                return
            script = os.path.join(HERE, "agent-file.sh")
            r = subprocess.run([script, "next"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, universal_newlines=True, cwd=self.ctx.main, timeout=60)
            if r.returncode != 0:
                return
            for line in r.stdout.splitlines():
                if not line.startswith("START "):
                    continue
                name = line[6:].split(" | ")[0].strip()
                if name in queued and name not in self.slots:
                    self.slots.append(name)
                    events.append(("WATCH SLOT %s: can start (run agent-file.sh next)" % name, None))
        except Exception:
            return

    # ---- B16

    def scan_orphans(self):
        ctx = self.ctx
        r = orca(["terminal", "list", "--json"])
        if not r.ok:
            return
        terms = [t for t in (r.result().get("terminals") or []) if isinstance(t, dict)
                 and t.get("connected") is not False and t.get("orphaned") is not True]
        if not self.repo_id:
            for t in terms:
                wid = str(t.get("worktreeId") or "")
                if same_path(t.get("worktreePath"), ctx.main) and "::" in wid:
                    self.repo_id = wid.split("::")[0]
                    break
        if not self.repo_id:
            w = orca(["worktree", "list", "--json"])
            if w.ok:
                for e in (w.result().get("worktrees") or []):
                    if isinstance(e, dict) and same_path(e.get("path"), ctx.main) and e.get("repoId"):
                        self.repo_id = str(e["repoId"])
                        break
        mine_paths = ctx.git_worktrees() + [ctx.main]
        known = set()
        for line in read_lines(ctx.file("agent_worktree.txt")):
            p = line.split(" | ")[0].strip()
            if p:
                known.add(p)
                known.add(norm(p))
        for line in read_lines(ctx.file("agent_todo.txt")):
            for f in line.split(" | ")[3:]:
                if f.startswith("on "):
                    p = f[3:].strip().partition(" ")[2].strip()
                    if p:
                        known.add(p)
                        known.add(norm(p))
        found = []
        for t in terms:
            path = str(t.get("worktreePath") or "")
            wid = str(t.get("worktreeId") or "")
            mine = bool(self.repo_id) and wid.startswith(self.repo_id + "::")
            mine = mine or any(under(path, m) for m in mine_paths)
            if not mine or t.get("agentIdentity") != "claude" or not path:
                continue
            if same_path(path, ctx.main) or path in known or norm(path) in known:
                continue
            found.append({"path": path, "title": str(t.get("title") or ""), "handle": str(t.get("handle") or "")})
        self.orphans = found
        for o in found:
            if o["path"] not in self.orphans_printed:
                self.orphans_printed.add(o["path"])
                out("%s watch: live pane with no task line: %s (%s)" % (hhmm(), o["path"], o["title"]))

    # ---- main loop

    def run(self):
        self.replace_older()
        status = self.load_status()
        self.saved = {k: v for k, v in (status.get("tasks") or {}).items() if isinstance(v, dict)}
        if isinstance(status.get("slots"), list):
            self.slots = [n for n in status["slots"] if isinstance(n, str)]
        signal.signal(signal.SIGTERM, self.on_term)
        out("%s watch --all: start (pid %d), every %s min" % (hhmm(), os.getpid(), fmt_num(self.interval_min)))
        self.prepare(True)
        urgent = any(t.urgent for t in self.tasks.values())
        self.sweep_time = now_text()
        self.write_status()
        n = 0
        next_at = time.time() + self.iv
        while True:
            if not (urgent and n == 0):
                time.sleep(max(0.0, next_at - time.time()))      # R8: a fixed cadence
            next_at = max(next_at + self.iv, time.time())
            n += 1
            events = self.one_sweep()
            self.housekeep_round()
            if events:
                return 0
            if n >= self.max:
                out("WATCH MAX all")
                return 0

    # ---- housekeep timer (W8): the main manager's pass every housekeep_interval_min minutes

    def hk_interval(self):
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            if here not in sys.path:
                sys.path.insert(0, here)
            import agent_conf
            return int(agent_conf.get("housekeep_interval_min"))
        except Exception:
            return 120

    def housekeep_round(self):
        """Runs agent-housekeep.sh --apply when it is due. Never raises, never ends the watch. Main manager only:
        no AGENT_ROLE, and the main-manager lock names a live pid (that pid is the CLAUDE_PID the pass checks)."""
        try:
            n = self.hk_interval()
            if n <= 0 or os.environ.get("AGENT_ROLE"):
                return
            lock = (read_text(os.path.join(self.ctx.gitdir, "agent_main.lock")) or "").split()
            if not lock or not lock[0].isdigit() or not pid_alive(int(lock[0])):
                return
            last = (read_text(os.path.join(self.ctx.gitdir, "agent_housekeep.last")) or "").split()
            if last and last[0].isdigit() and time.time() - int(last[0]) < n * 60:
                return
            script = os.path.join(HERE, "agent-housekeep.sh")
            if not os.access(script, os.X_OK):
                return
            env = dict(os.environ, CLAUDE_PID=lock[0], CLAUDE_PROJECT_DIR=self.ctx.main)
            env.pop("AGENT_ROLE", None)
            subprocess.run([script, "--apply"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, env=env, cwd=self.ctx.main, timeout=900)
        except Exception:
            return

    def on_term(self, signum, frame):
        """R9: a newer --all replaced this one (it wrote its pid into the status file first)."""
        pid = self.load_status().get("pid")
        if isinstance(pid, int) and pid != os.getpid() and pid_alive(pid) and is_all_watch(pid):
            out("WATCH REPLACED all: a newer watch runs (pid %d); do not restart" % pid)
            os._exit(0)
        os._exit(143)


def is_all_watch(pid):
    try:
        args = subprocess.run(["ps", "-o", "args=", "-p", str(pid)], capture_output=True, text=True,
                              timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return ("agent-watch" in args or "agent_watch" in args) and "--all" in args


def stall_held(t, screen, fp):
    """R4: an idle-prompt or login stall is held by (reason, file) only; a no-change stall also by the screen."""
    if fp != t.stall_fp:
        return False
    return t.stall_reason in ("idle prompt", "login expired") or screen == t.stall_screen


def login_expired(lines):
    """R22, R22b: on a screen that is not busy, in the 10 lines above the input prompt line (the last line
    starting with a prompt, box chars ignored), else in the last 10 lines."""
    if any("esc to interrupt" in l for l in lines):
        return False
    region = lines[-10:]
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].lstrip(BOX_CHARS).startswith("\u276f"):
            region = lines[max(0, i - 10):i]
            break
    return any(w in l for l in region for w in LOGIN_TEXTS)


def fmt_num(x):
    return str(int(x)) if float(x) == int(x) else str(x)


def quiet_limit():
    """watch_quiet_min (a setting, default 15; the board's "not confirmed" uses it too)."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import agent_conf
        v = agent_conf.get("watch_quiet_min")
        return v if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 240 else 15
    except Exception:
        return 15


def shells_running(screen):
    """B6, B7: something still runs in the background: `shell still running`, `<n> shells still running`,
    `Waiting for <n> background agent(s) to finish`, or an agents-panel row of a running subagent
    (`  ◯ <type>  <task>  2m 45s · ...`). The bare `⏺ main` row shows on idle panes too: not busy."""
    return ("shell still running" in screen
            or re.search(r"\b\d+ shells? still running", screen) is not None
            or re.search(r"(?m)\b[1-9]\d* (?:shells?|monitors?)\b", "\n".join(screen.split("\n")[-6:])) is not None
            or re.search(r"Waiting for \d+ background agents? to finish", screen) is not None
            or re.search(r"(?m)^ +[\u25ef\u25d0\u25d1\u25d2\u25d3\u2800-\u28ff] +\S.*\b\d+s\b", screen) is not None)


def is_idle_prompt(lines):
    """The idle prompt: no line with `esc to interrupt`, a line starting with a prompt (box chars ignored)."""
    if any("esc to interrupt" in l for l in lines):
        return False
    return any(l.lstrip(BOX_CHARS).startswith("\u276f") for l in lines)


def resolve_tm_cached(ctx, t, env):
    """The TM pane of a task: a LAUNCH record first, else the listed one (kept until it is gone). R3b: a pane
    reported LOST counts as gone; it is the answer only when nothing else is found."""
    skip = t.gone | t.lost
    recs = [r for r in launch_records(ctx, t.name)
            if r["kind"] == "tm-pane" and r["env"] == (env or "") and r["pane"] and r["pane"] not in skip
            and r["pid"] and pid_alive(r["pid"])]
    if recs:
        return recs[-1]["pane"]
    if t.listed_pane and t.listed_pane not in skip:
        return t.listed_pane
    t.listed_pane = resolve_tm(ctx, t, env, skip) or ""
    if t.listed_pane:
        return t.listed_pane
    if t.lost:
        return resolve_tm(ctx, t, env, t.gone) or ""
    return ""


def resolve_shell_cached(ctx, t, env, tm_handle):
    recs = [r for r in launch_records(ctx, t.name)
            if r["kind"] == "shell-pane" and r["env"] == env and r["pane"] and r["pane"] not in t.gone]
    if recs:
        return recs[-1]["pane"]
    if t.listed_shell and t.listed_shell not in t.gone:
        return t.listed_shell
    t.listed_shell = resolve_shell(ctx, t, env, tm_handle, t.gone) or ""
    return t.listed_shell


# ---------------------------------------------------------------- tell (rows D1-D8)

TELL_CHUNK = 300
TELL_HASH = re.compile(r"^TSIG ([0-9a-f]{64}) TEND$")
SIGNATURE = re.compile(r"^(\[[^\[\]\n]*\]) ")


def tell_signature(msg):
    """D1: (signature, text after it) or None. The signature is a bracket group of two words or more."""
    m = SIGNATURE.match(msg)
    if not m or len(m.group(1)[1:-1].split()) < 2 or not msg[m.end():].strip():
        return None
    return m.group(1), msg[m.end():]


def tell_block(sha, sig, when, body):
    lines = ["  " + l if l else "" for l in body.split("\n")]
    return "TELL %s %s | %s\n%s\nEND TELL %s\n\n" % (sha, sig, when, "\n".join(lines), sha)


def pane_gone(env, pane):
    """R15: the pane read says gone, or its status is not running."""
    r = term_read(env, pane)
    if not r.ok:
        return r.code in GONE_CODES
    status = (terminal_of(r) or {}).get("status")
    return status is not None and status != "running"


def tell_resolve(ctx, task):
    """D2: (path, env, pane, shell, "") or (None, ..., why). The status file first, else A3-A5."""
    try:
        with open(ctx.status_path, "rb") as fh:
            data = json.loads(fh.read().decode("utf-8", "replace"))
    except (OSError, ValueError):
        data = {}
    entry = ((data.get("tasks") if isinstance(data, dict) else None) or {}).get(task)
    if isinstance(entry, dict) and entry.get("pane") and entry.get("path"):
        path, env, pane = str(entry["path"]), str(entry.get("env") or ""), str(entry["pane"])
        target = Target(task, path, env)
        shell = str(entry.get("shell") or "")
        if pane_gone(env, pane):                        # R15: a gone or exited pane: A3-A5 once more
            target = next((t for t in read_targets(ctx) if t.name == task), target)
            env2, why = locate(ctx, target)
            if env2 is None:
                return None, "", "", "", why
            if env2 != env:
                env, shell = env2, ""
            pane = resolve_tm(ctx, target, env, skip=(pane,))
            if not pane:
                return None, "", "", "", "no task manager pane"
            path = target.path
    else:
        target = next((t for t in read_targets(ctx) if t.name == task), None)
        if target is None:
            return None, "", "", "", "no worktree line or open todo `on` line for it"
        path = target.path
        env, why = locate(ctx, target)
        if env is None:
            return None, "", "", "", why
        pane, shell = resolve_tm(ctx, target, env), ""
        if not pane:
            return None, "", "", "", "no task manager pane"
    if env and shell and pane_gone(env, shell):         # R15b: the same for the shell pane
        shell = resolve_shell(ctx, target, env, pane, skip=(shell,)) or ""
        if not shell:
            return None, "", "", "", no_shell_why(env, target)
    if env and not shell:
        shell = resolve_shell(ctx, target, env, pane) or ""
        if not shell:
            return None, "", "", "", no_shell_why(env, target)
    return path, env, pane, shell, ""


def tell_write_local(path, block):
    """D5, D6: one append under the state lock, then the end of the file read back. True when it matches."""
    import agent_state
    data = block.encode("utf-8")
    f = os.path.join(path, "agent_state.txt")
    with agent_state.Lock(path):
        try:
            with open(f, "rb") as fh:
                old = fh.read()
        except OSError:
            old = b""
        prefix = b"\n" if old and not old.endswith(b"\n") else b""
        with open(f, "ab") as fh:
            fh.write(prefix + data)
        try:
            with open(f, "rb") as fh:
                return fh.read()[-len(data):] == data
        except OSError:
            return False


def shell_send(env, shell, cmd):
    return orca(["terminal", "send"] + env_args(env) + ["--terminal", shell, "--text", cmd, "--enter", "--json"])


def tell_write_remote(env, shell, path, block, sha, gitdir=None):
    """D5, D6: base64 chunks into a temp file, one command decodes and appends, one command prints the
    sha256 of the block's length at the end of the file. All under the shell pane's lock (R16). (ok, why)."""
    with ShellLock(gitdir or ".", shell):
        return tell_write_remote_locked(env, shell, path, block, sha)


def tell_write_remote_locked(env, shell, path, block, sha):
    import base64
    import hashlib
    data = block.encode("utf-8")
    b64 = base64.b64encode(data).decode("ascii")
    tmp = "/tmp/.agent_tell_%s.b64" % sha
    f = shlex.quote(path + "/agent_state.txt")
    for i in range(0, len(b64), TELL_CHUNK):
        r = shell_send(env, shell, "printf %%s %s %s %s" % (b64[i:i + TELL_CHUNK], ">" if i == 0 else ">>", tmp))
        if not r.ok:
            return False, "shell pane: " + r.err
    cmd = ('F=%s; [ ! -s "$F" ] || [ -z "$(tail -c 1 "$F")" ] || echo >> "$F"; '
           '{ base64 -d < %s 2>/dev/null || base64 -D < %s; } >> "$F"; rm -f %s' % (f, tmp, tmp, tmp))
    r = shell_send(env, shell, cmd)
    if not r.ok:
        return False, "shell pane: " + r.err
    rd = term_read(env, shell)
    cursor = str((terminal_of(rd) or {}).get("latestCursor") or "") if rd.ok else ""
    if not cursor:
        return False, "no latestCursor in the shell pane read"
    r = shell_send(env, shell, 'echo TSIG $(tail -c %d %s | (sha256sum 2>/dev/null || shasum -a 256) | cut -c1-64) TEND'
                   % (len(data), f))
    if not r.ok:
        return False, "shell pane: " + r.err
    want = hashlib.sha256(data).hexdigest()
    seen_other = False
    for _ in range(20):
        a = term_read(env, shell, cursor)
        if not a.ok:
            return False, a.err
        for line in tail_of(terminal_of(a) or {}):
            m = TELL_HASH.match(line.replace("\r", "").strip())
            if m:
                if m.group(1) == want:
                    return True, ""
                seen_other = True
        time.sleep(0.5)
    return False, "hash differs" if seen_other else "no answer from the shell pane"


def pointer_seen(env, pane, sha, cursor=None):
    r = term_read(env, pane, cursor or None)
    return r.ok and any(("TELL " + sha) in l for l in tail_of(terminal_of(r) or {}))


def tell_pointer(env, pane, sha, sig, cursor, echo_s):
    """D7, D8, R23: the pointer already on the full screen (a first send) -> no second send. tui-idle wait
    (a failure still goes on), one send, then look for TELL <sha8> in the --cursor read and the full screen."""
    if cursor and pointer_seen(env, pane, sha):
        return True
    orca(["terminal", "wait"] + env_args(env) + ["--terminal", pane, "--for", "tui-idle", "--timeout-ms",
                                                 "120000", "--json"], timeout=150)
    text = "%s TELL %s: read the TELL %s block at the end of agent_state.txt and act on it" % (sig, sha, sha)
    if not shell_send(env, pane, text).ok:
        return False
    deadline = time.time() + echo_s
    while True:
        if (cursor and pointer_seen(env, pane, sha, cursor)) or pointer_seen(env, pane, sha):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.3)


def tell_main(argv):
    if len(argv) != 4:
        sys.stderr.write("usage: agent_watch.py tell <main repo> <now> <task> <msg>\n")
        return 2
    root, when, task, msg = argv
    parts = tell_signature(msg)
    if parts is None:
        sys.stderr.write("tell: the message must start with [<model> <effort>]\n")
        return 1
    sig, body = parts
    ctx = Ctx(root)
    path, env, pane, shell, why = tell_resolve(ctx, task)
    if path is None:
        sys.stderr.write("tell: no pane for %s: %s\n" % (task, why))
        return 1
    import hashlib
    sha = hashlib.sha256(msg.encode("utf-8", "surrogateescape")).hexdigest()[:8]
    block = tell_block(sha, sig, (when or now_text())[:16], body)
    for _ in range(2):
        if env:
            ok, _why = tell_write_remote(env, shell, path, block, sha, ctx.gitdir)
        else:
            ok = tell_write_local(path, block)
        if ok:
            break
    else:
        out("TELL FAIL %s %s: file check" % (task, sha))
        return 1
    try:
        echo_s = float(os.environ.get("AGENT_TELL_ECHO_S") or 10)
    except ValueError:
        echo_s = 10.0
    r = term_read(env, pane)
    cursor = str((terminal_of(r) or {}).get("latestCursor") or "") if r.ok else ""
    for _ in range(2):
        if tell_pointer(env, pane, sha, sig, cursor, echo_s):
            out("TELL OK %s %s" % (task, sha))
            return 0
    out("TELL FAIL %s %s: pointer not seen (block is in the file)" % (task, sha))
    return 1


def usage(msg=""):
    sys.stderr.write("usage: agent_watch.py --all [--interval-min 5] [--max <n>]\n")
    if msg:
        sys.stderr.write("agent_watch.py: %s\n" % msg)
    return 2


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if argv and argv[0] == "tell":
        return tell_main(argv[1:])
    mode_all, minutes, max_sweeps = False, 5.0, DEFAULT_MAX
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--all":
            mode_all = True
            i += 1
        elif a in ("--interval-min", "--max") and i + 1 < len(argv):
            try:
                if a == "--max":
                    max_sweeps = int(argv[i + 1])
                else:
                    minutes = float(argv[i + 1])
                    if not minutes > 0 or minutes == float("inf"):
                        raise ValueError
            except ValueError:
                return usage("%s must be a number%s" % (a, " above 0" if a == "--interval-min" else ""))
            i += 2
        else:
            return usage("unknown argument: %s" % a)
    if not mode_all:
        return usage("missing --all")
    iv = minutes * 60
    env_iv = os.environ.get("AGENT_WATCH_INTERVAL_S")
    if env_iv not in (None, ""):
        try:
            iv = float(env_iv)
            minutes = iv / 60
        except ValueError:
            pass
    ctx = Ctx()
    return Engine(ctx, iv, round(minutes, 3), max_sweeps).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
