#!/usr/bin/env python3
"""agent_guard.py - the logic of the board-trust launch hook (rules: requirements/board-trust.md).

Reads one hook JSON on stdin. Prints exactly one line on stdout, the protocol line
agent-guard.sh maps:

    OK              silent allow
    WARN <line>     allow, <line> goes to stderr
    BLOCK <line>    <line> goes to stderr, exit 2

This script never raises and always exits 0: any error becomes
"WARN board guard: <what>; allowed".
"""

import datetime
import fcntl
import json
import os
import re
import subprocess
import sys
import time

NAME = r"[A-Za-z0-9][A-Za-z0-9._-]*"
READ_ONLY = {"Explore", "Plan", "claude-code-guide", "web-fetch", "statusline-setup"}
TYPE_KINDS = {"worker": "worker", "fast-lane-deputy": "deputy", "merge-deputy": "merge", "Explore": "explore",
              "Plan": "plan", "claude-code-guide": "guide"}
PANE_KINDS = ("tm-pane", "shell-pane", "pane", "helper-pane")
FIELD_ORDER = ("since", "pid", "by", "type", "agent", "pane", "env", "worktree")
FMT = "%Y-%m-%d %H:%M"

OK = ("OK", "")

RE_P1 = re.compile(r"^(%s)\s+Worker\s+(\d+)(?:\s*:\s*(.*))?$" % NAME, re.I | re.S)
RE_P24 = re.compile(r"^(%s)\s+(Deputy|Merge|Reviewer)\b(?:\s*:\s*(.*))?$" % NAME, re.I | re.S)
RE_BRACKET = re.compile(r"^\[[^\]]*\]\s*")
RE_T1 = re.compile(r"^(%s)\s+Task\s+Manager\b" % NAME, re.I)
RE_T3 = re.compile(r"^(%s)\s+Helper(?:\s+-\s+.*)?\s*$" % NAME, re.I | re.S)
RE_T2 = re.compile(r"^(%s)(?:\s+(.*))?$" % NAME, re.S)
RE_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


class Warn(Exception):
    pass


# ------------------------------------------------------------------ small helpers

def one_line(s):
    return " ".join(str(s).split())


def q(s):
    s = one_line(s)
    return s if len(s) <= 80 else s[:77] + "..."


def alive(pid):
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def git(cwd, *args):
    """(returncode, stdout); (None, "") when git is missing or too slow (the caller allows silently)."""
    try:
        r = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return r.returncode, r.stdout


def now_str():
    return os.environ.get("AGENT_FAKE_NOW") or time.strftime(FMT)


def parse_time(s):
    try:
        return datetime.datetime.strptime(s.strip(), FMT)
    except (ValueError, AttributeError):
        return None


def session_pid():
    v = os.environ.get("CLAUDE_PID", "").strip()
    if v:
        return int(v) if v.isdigit() and int(v) > 0 else None
    p = os.getppid()
    for _ in range(10):
        if p <= 1:
            break
        r = subprocess.run(["ps", "-o", "ppid=,comm=", "-p", str(p)], capture_output=True, text=True, timeout=2)
        parts = r.stdout.strip().split(None, 1)
        if len(parts) < 2:
            break
        if os.path.basename(parts[1].strip()) == "claude":
            return p
        if not parts[0].isdigit():
            break
        p = int(parts[0])
    return None


def read_conf(main):
    """(mode, state_keep_hours): mode "on" when the todo_before_agent setting is true, else "record" (never
    block); state_keep_hours is the fixed constant. Any error: ("record", 24.0). MAIN is kept for old callers."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        old = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            if here not in sys.path:
                sys.path.insert(0, here)
            import agent_conf
        finally:
            sys.dont_write_bytecode = old
        hours = 24.0
        try:
            value = float(agent_conf.get("state_keep_hours"))
            if value > 0:
                hours = value
        except Exception:
            pass
        return ("on" if agent_conf.get("todo_before_agent") is True else "record"), hours
    except Exception:
        return "record", 24.0


def read_todo(main):
    """(set of open task names, None) or (None, why)."""
    try:
        with open(os.path.join(main, "agent_todo.txt"), encoding="utf-8", errors="replace") as fh:
            names = set()
            for line in fh:
                first = line.split(" | ", 1)[0].strip()
                if first:
                    names.add(first)
            return names, None
    except OSError as e:
        return None, e.strerror or type(e).__name__


# ------------------------------------------------------------------ the Bash command parse

RE_HEREDOC = re.compile(r"<<(-?)[ \t]*(?:'([^'\n]*)'|\"([^\"\n]*)\"|([A-Za-z_][A-Za-z0-9_]*))")


def cut_heredocs(s):
    """The text without heredoc bodies and their terminator lines (cut before any quote is read)."""
    if "<<" not in s:
        return s
    lines = s.split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        pending = []
        for m in RE_HEREDOC.finditer(line):
            if line[max(0, m.start() - 1):m.start()] == "<":
                continue
            pending.append((m.group(1) == "-", m.group(2) if m.group(2) is not None else
                            (m.group(3) if m.group(3) is not None else m.group(4))))
        for strip, delim in pending:
            while i < len(lines):
                body = lines[i].rstrip("\r")
                i += 1
                if (body.lstrip("\t") if strip else body) == delim:
                    break
    return "\n".join(out)


def split_commands(s):
    """Simple commands of a shell text: lists of words, quotes removed. Heredoc bodies, comments and
    quoted text never start a command; a command starts after ; & && || | ( $( ` and newline."""
    s = cut_heredocs(s)
    cmds, words = [], []
    cur = [None]
    i, n = 0, len(s)

    def endword():
        if cur[0] is not None:
            words.append(cur[0])
            cur[0] = None

    def endcmd():
        if words:
            cmds.append(list(words))
            del words[:]

    def add(t):
        cur[0] = (cur[0] or "") + t

    while i < n:
        c = s[i]
        if c == "\\":
            if i + 1 < n:
                if s[i + 1] != "\n":
                    add(s[i + 1])
                i += 2
            else:
                i += 1
            continue
        if c == "'":
            j = s.find("'", i + 1)
            if j < 0:
                j = n
            add(s[i + 1:j])
            cur[0] = cur[0] or ""
            i = j + 1
            continue
        if c == '"':
            j, buf = i + 1, []
            while j < n and s[j] != '"':
                if s[j] == "\\" and j + 1 < n and s[j + 1] in '"\\$`\n':
                    if s[j + 1] != "\n":
                        buf.append(s[j + 1])
                    j += 2
                    continue
                buf.append(s[j])
                j += 1
            add("".join(buf))
            cur[0] = cur[0] or ""
            i = j + 1
            continue
        if c in " \t\r":
            endword()
            i += 1
            continue
        if c == "\n":
            endword()
            endcmd()
            i += 1
            continue
        if c == "#" and cur[0] is None:
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "$" and s[i + 1:i + 2] == "(":
            endword()
            endcmd()
            i += 2
            continue
        if c in ";&|()`":
            if c == "&" and i > 0 and s[i - 1] in "<>":
                add(c)
                i += 1
                continue
            endword()
            endcmd()
            i += 1
            continue
        add(c)
        i += 1
    endword()
    endcmd()
    return cmds


def opt_values(words, keys):
    out = {}
    k = 0
    while k < len(words):
        w = words[k]
        if w.startswith("--"):
            name, eq, val = w[2:].partition("=")
            if name in keys:
                if eq:
                    out[name] = val
                elif k + 1 < len(words):
                    out[name] = words[k + 1]
                    k += 1
        k += 1
    return out


SKIP_WORDS = ("env", "time", "then", "do", "else", "{", "!")
OPS = {("terminal", "create"): "create", ("terminal", "close"): "close",
       ("worktree", "create"): "wt_create", ("worktree", "rm"): "wt_rm",
       ("terminal", "send"): "send", ("orchestration", "send"): "send"}


RE_VAR = re.compile(r"\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)\})")


def expand_vars(v, env):
    """v with $NAME / ${NAME} replaced from env (plain literal values only). A name not in env stays as it is."""
    return RE_VAR.sub(lambda m: env.get(m.group(1) or m.group(2), m.group(0)), v)


def bash_launches(command):
    """[(op, opts)] of every orca launch command in a Bash text, in order.
    op: create | close | wt_create | wt_rm. A worktree value with $NAME is expanded from an earlier
    NAME=value / export NAME=value of the same text; if it cannot be, it keeps its `$`."""
    found = []
    env = {}
    for words in split_commands(command):
        aw = words[1:] if words[0] == "export" else words
        if all(RE_ASSIGN.match(x) for x in aw):
            for x in aw:
                name, _, val = x.partition("=")
                if val and not re.search(r"[$`]", val):
                    env[name] = val
                else:
                    env.pop(name, None)
            continue
        k = 0
        while k < len(words) and (RE_ASSIGN.match(words[k]) or words[k] in SKIP_WORDS):
            k += 1
        w = words[k:]
        if len(w) >= 3 and os.path.basename(w[0]) == "agent-runtime.sh" and w[1] == "close":
            found.append(("close", {"terminal": w[2]}))   # the runtime script's close is a pane close
            continue
        if len(w) < 3 or os.path.basename(w[0]) != "orca":
            continue
        pair = (w[1], w[2])
        if pair in OPS:
            opts = opt_values(w[3:], ("title", "command", "environment", "worktree", "terminal", "name", "text", "body"))
            if "worktree" in opts and "$" in opts["worktree"]:
                opts["worktree"] = expand_vars(opts["worktree"], env)
            found.append((OPS[pair], opts))
    return found


POINTS = {
    "dispatch": ("Dispatch: route it by rules/routing.md (W9); its blocks (--checks) by rules/checks.md (R8). "
                 "The hook only points."),
    "merge": ("Merge: the gate by rules/checks.md (R8); the merge and the cleanup by rules/worktrees.md (W8). "
              "The hook only points."),
    "push": "Push: a push that is denied: rules/traps.md (W16). The hook only points.",
}
POINT_AGENTS = {"fast-lane-deputy": "dispatch", "merge-deputy": "merge", "reviewer": "merge",
                "check-deputy": "merge"}
_POINT = {"moment": None, "ctx": None, "sid": ""}


def git_subcommand(args):
    """The git subcommand of the words after `git` (global options skipped)."""
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return a
    return ""


def bash_moment(command, ops):
    """dispatch | merge | push | None for a Bash text (the first one found, in command order)."""
    if any(op == "create" for op, _ in ops):
        return "dispatch"
    for words in split_commands(command):
        k = 0
        while k < len(words) and (RE_ASSIGN.match(words[k]) or words[k] in SKIP_WORDS):
            k += 1
        w = words[k:]
        if not w:
            continue
        if os.path.basename(w[0]) in ("bash", "sh") and len(w) > 1:
            w = w[1:]
        name = os.path.basename(w[0])
        rest = w[1:]
        if name == "agent-file.sh":
            for a, b in zip(rest, rest[1:]):
                if (a, b) == ("todo", "add"):
                    return "dispatch"
                if (a, b) == ("checks", "gate"):
                    return "merge"
        elif name == "agent-promote.sh" and "--task" in rest:
            return "merge"
        elif name == "git" and git_subcommand(rest) == "push":
            return "push"
    return None


def point_line(ctx):
    """The pointer line of this call, or None (already given in this session, or no session id and no marker)."""
    moment = _POINT["moment"]
    if not moment or ctx is None:
        return None
    sid = re.sub(r"[^A-Za-z0-9_.-]", "_", _POINT["sid"])
    if sid:
        path = os.path.join(ctx["common"], "agent_point_%s_%s" % (sid, moment))
        if os.path.exists(path):
            return None
        try:
            with open(path, "w") as fh:
                fh.write(ctx["now"] + "\n")
        except OSError:
            return None
    return POINTS[moment]


def pane_title(opts):
    t = opts.get("title")
    if t is None or not t.strip():
        m = re.search(r"--name(?:=|\s+)(?:'([^']*)'|\"([^\"]*)\"|(\S+))", opts.get("command", ""))
        t = (m.group(1) or m.group(2) or m.group(3) or "") if m else ""
    return t.strip()


def path_value(v):
    return v[5:] if v.startswith("path:") else v


# ------------------------------------------------------------------ record lines

def parse_launch(line):
    if not line.startswith("LAUNCH "):
        return None
    head, sep, rest = line[7:].rstrip("\n").partition(": ")
    if not sep:
        return None
    parts = rest.split(" | ")
    if len(parts) < 3:
        return None
    d = {"key": head, "kind": parts[0], "title": parts[2],
         "task": parts[1][5:] if parts[1].startswith("task ") else parts[1]}
    for p in parts[3:]:
        k, _, v = p.partition(" ")
        d[k] = v
    return d


def build_launch(d):
    parts = ["%s" % d["kind"], "task %s" % d["task"], d["title"]]
    for k in FIELD_ORDER:
        if d.get(k) not in (None, ""):
            parts.append("%s %s" % (k, d[k]))
    for k in d:
        if k not in FIELD_ORDER and k not in ("key", "kind", "task", "title") and d[k] not in (None, ""):
            parts.append("%s %s" % (k, d[k]))
    return "LAUNCH %s: %s\n" % (d["key"], " | ".join(parts))


def clean_title(t):
    t = " ".join(str(t).split())
    t = t.replace(" | ", " / ")
    t = t.strip(" |")
    return t or "-"


def should_prune(d, now, keep_hours):
    kind = d.get("kind", "")
    pid = d.get("pid", "")
    since, nw = parse_time(d.get("since", "")), parse_time(now)
    dead = pid.isdigit() and not alive(int(pid))
    if kind in PANE_KINDS:
        # a pane outlives the session that opened it: pruned only when the session is dead and the line is old
        if dead and since and nw and (nw - since).total_seconds() > keep_hours * 3600:
            return True
    elif dead:
        return True
    if not d.get("agent") and not d.get("pane"):
        if since and nw and (nw - since).total_seconds() > 120:
            return True
    return False


def prune(lines, ctx):
    out = []
    for line in lines:
        d = parse_launch(line)
        if d is not None and should_prune(d, ctx["now"], ctx["keep"]):
            continue
        out.append(line)
    return out


# ------------------------------------------------------------------ the state file, under a lock

class Busy(Exception):
    pass


def sig(path):
    try:
        st = os.stat(path)
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def read_lines(path):
    try:
        with open(path, encoding="utf-8", errors="surrogateescape", newline="") as fh:
            return fh.read().splitlines(True)
    except FileNotFoundError:
        return []


def with_newline(lines):
    """The lines, the last one ended by a newline."""
    if lines and not lines[-1].endswith("\n"):
        lines = lines[:-1] + [lines[-1] + "\n"]
    return lines


def rewrite(ctx, path, compute):
    for _ in range(3):
        before = sig(path)
        new = compute(read_lines(path))
        if new is None:
            return
        data = "".join(new)
        for tmpdir in (ctx["gitdir"], os.path.dirname(path)):
            tmp = os.path.join(tmpdir, "agent_state.guard.%d.tmp" % os.getpid())
            try:
                with open(tmp, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
                    fh.write(data)
                try:
                    os.chmod(tmp, os.stat(path).st_mode & 0o7777)
                except OSError:
                    pass
                if sig(path) != before:
                    break
                os.replace(tmp, path)
                return
            except OSError:
                continue  # e.g. across devices: try the folder itself
            finally:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
    raise Warn("state file changed while writing")


class StateLock:
    """The flock `state add` / `state trim` take: <git dir>/agent_state.lock. 2 s, then Busy."""

    def __init__(self, gitdir):
        self.path = os.path.join(gitdir, "agent_state.lock")
        self.fd = None

    def __enter__(self):
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        deadline = time.time() + 2.0
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.time() >= deadline:
                    os.close(self.fd)
                    self.fd = None
                    raise Busy()
                time.sleep(0.05)

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
        return False


def add_record(ctx, line):
    """Append one record (one per key); prune on the way."""
    path = os.path.join(ctx["folder"], "agent_state.txt")
    key = parse_launch(line)["key"]
    with StateLock(ctx["gitdir"]):
        lines = read_lines(path)
        for old in lines:
            d = parse_launch(old)
            if d is not None and d["key"] == key:
                return
        pruned = prune(lines, ctx)
        if len(pruned) == len(lines):
            with open(path, "a", encoding="utf-8", errors="surrogateescape", newline="") as fh:
                if lines and not lines[-1].endswith("\n"):
                    fh.write("\n")
                fh.write(line)
        else:
            rewrite(ctx, path, lambda ls: with_newline(prune(ls, ctx)) + [line])


def edit_records(ctx, mutate):
    """mutate(list of lines) -> new list or None (no change). Edits and removals only."""
    path = os.path.join(ctx["folder"], "agent_state.txt")
    if mutate(read_lines(path)) is None:
        return False
    with StateLock(ctx["gitdir"]):
        def compute(lines):
            new = mutate(lines)
            return None if new is None else prune(new, ctx)
        rewrite(ctx, path, compute)
    return True


def mut_set(match, **fields):
    def mutate(lines):
        out, hit = [], False
        for line in lines:
            d = parse_launch(line)
            if d is not None and match(d):
                d.update(fields)
                line = build_launch(d)
                hit = True
            out.append(line)
        return out if hit else None
    return mutate


def mut_remove(match):
    def mutate(lines):
        out = [line for line in lines if not (parse_launch(line) and match(parse_launch(line)))]
        return out if len(out) != len(lines) else None
    return mutate


# ------------------------------------------------------------------ roles and own task

def own_task(ctx):
    main, folder = ctx["main"], ctx["folder"]
    try:
        with open(os.path.join(main, "agent_worktree.txt"), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = [p.strip() for p in line.split(" | ")]
                if len(parts) >= 2 and parts[0] and os.path.realpath(parts[0]) == os.path.realpath(folder):
                    if parts[1] and not parts[1].startswith("task manager"):
                        return parts[1]
    except OSError:
        pass
    try:
        with open(os.path.join(folder, "agent_state.txt"), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"\s*TODO LINE:\s*([^|]*?)\s*\|", line)
                if m and m.group(1):
                    return m.group(1)
    except OSError:
        pass
    return os.path.basename(folder.rstrip("/"))


def find_role(payload, ctx):
    if payload.get("agent_id") and payload.get("hook_event_name") in ("PreToolUse", "PostToolUse"):
        return "free"
    if os.environ.get("AGENT_ROLE") == "task-manager":
        return "tm"
    try:
        with open(os.path.join(ctx["common"], "agent_main.lock"), encoding="utf-8", errors="replace") as fh:
            first = fh.readline().split()
        if first and first[0].isdigit() and ctx["pid"] is not None and int(first[0]) == ctx["pid"] \
                and alive(int(first[0])):
            return "main"
    except OSError:
        pass
    return "free"


# ------------------------------------------------------------------ decisions

class Decision:
    def __init__(self, kind, task, title, block=None, warn=None):
        self.kind, self.task, self.title, self.block, self.warn = kind, task, title, block, warn


def base_type(stype):
    return (stype or "general-purpose").split(":")[-1]


def parse_desc(desc):
    """P1-P4: (task, kind, title) or None."""
    d = desc.strip()
    m = RE_P1.match(d)
    if m:
        return m.group(1), "worker %s" % m.group(2), (m.group(3) or "").strip() or d
    m = RE_P24.match(d)
    if m:
        return m.group(1), {"deputy": "deputy", "merge": "merge", "reviewer": "reviewer"}[m.group(2).lower()], \
            (m.group(3) or "").strip() or d
    return None


def not_open_msg(desc, task):
    return ('board guard: "%s" names %s, which is not an open todo task. Run agent-file.sh todo add "%s" ... '
            'first, then launch again.' % (q(desc), task, task))


def first_word(text):
    t = text.strip()
    w = re.split(r"[\s:]", t, 1)[0] if t else ""
    return w.rstrip(",.;:)")


def quiet_todo(ctx):
    opens, _ = read_todo(ctx["main"])
    return opens or set()


def share_module():
    here = os.path.dirname(os.path.abspath(__file__))
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        if here not in sys.path:
            sys.path.insert(0, here)
        import agent_share
        return agent_share
    finally:
        sys.dont_write_bytecode = old


def share_pull(main):
    """A shared todo: the newest data first (quiet, short timeout, a failure = the local file)."""
    try:
        share_module().pull(main)
    except Exception:
        pass


def work_block(ctx, task):
    """"board guard: <text>" when this person may not work the task of a shared todo, else None."""
    try:
        agent_share = share_module()
        text = agent_share.may_work(ctx["main"], agent_share.todo_line(ctx["main"], task))
    except Exception:
        return None
    return "board guard: %s" % text if text else None


def decide_agent(ctx, desc, stype):
    base = base_type(stype)
    kind_t = TYPE_KINDS.get(base, "agent")
    pd = parse_desc(desc)
    first = first_word(desc)
    role = ctx["role"]
    if role == "tm":
        # rule 4: never blocked. A name counts only when it is the own task or an open todo task of the main
        # repo; any other name is a role label: own task, kind and title from the pattern.
        own = own_task(ctx)
        opens = quiet_todo(ctx)
        if pd:
            return Decision(pd[1], pd[0] if (pd[0] == own or pd[0] in opens) else own, pd[2])
        return Decision(kind_t, first if (first == own or first in opens) else own, desc)
    if role == "main":
        share_pull(ctx["main"])
    opens, why = read_todo(ctx["main"])
    if role == "free":
        if pd:
            return Decision(pd[1], pd[0], pd[2])
        if opens is not None and first in opens:
            return Decision(kind_t, first, desc)
        return Decision(kind_t, os.path.basename(ctx["folder"].rstrip("/")), desc)
    # main
    folder_name = os.path.basename(ctx["main"].rstrip("/"))
    if opens is None:
        warn = "board guard: cannot read agent_todo.txt (%s); allowed" % why
        if pd:
            return Decision(pd[1], pd[0], pd[2], warn=warn)
        return Decision(kind_t, folder_name, desc, warn=warn)
    ro = base in READ_ONLY
    if pd:
        if pd[0] in opens:
            return Decision(pd[1], pd[0], pd[2], block=work_block(ctx, pd[0]))
        if not ro:
            return Decision(pd[1], pd[0], pd[2], block=not_open_msg(desc, pd[0]))
    elif first in opens:
        return Decision(kind_t, first, desc, block=work_block(ctx, first))
    if ro:
        return Decision(kind_t, "%s Manager" % folder_name, desc)
    return Decision(kind_t, "%s Manager" % folder_name, desc,
                    block='board guard: "%s" names no open todo task, and a %s agent can write files. Start the '
                          'description with an open task ("<task> Worker <n>: ...") or run agent-file.sh todo add '
                          'first.' % (q(desc), base))


def parse_title(title):
    """(kind, task, source) source: T1 T2 T3 T4 or None."""
    m = RE_BRACKET.match(title)
    rest = title[m.end():] if m else title
    m1 = RE_T1.match(rest)
    if m1:
        return "tm-pane", m1.group(1), "T1"
    m3 = RE_T3.match(rest)
    if m3:
        return "helper-pane", "%s Helper" % m3.group(1), "T3"
    if m:
        m2 = RE_T2.match(rest)
        if m2:
            return ("shell-pane" if "shell" in (m2.group(2) or "").lower() else "pane"), m2.group(1), "T2"
        return "pane", None, None
    word = first_word(rest)
    return "pane", word or None, "T4"


def decide_pane(ctx, title):
    kind, task, src = parse_title(title)
    role = ctx["role"]
    folder_name = os.path.basename(ctx["folder"].rstrip("/"))
    main_name = os.path.basename(ctx["main"].rstrip("/"))
    unknown = "$" in title or "`" in title  # a shell variable or substitution: the real title is not known
    if src == "T3":
        return Decision(kind, task, title)
    if role == "tm":
        own = own_task(ctx)
        if src in ("T1", "T2") and (task == own or task in quiet_todo(ctx)):
            return Decision(kind, task, title)
        return Decision(kind, own, title)
    if role == "main":
        share_pull(ctx["main"])
    opens, why = read_todo(ctx["main"])
    if role == "free":
        if src in ("T1", "T2"):
            return Decision(kind, task, title)
        if src == "T4" and opens is not None and task in opens:
            return Decision(kind, task, title)
        return Decision("pane" if src != "T1" else kind, folder_name, title)
    # main
    if opens is None:
        warn = "board guard: cannot read agent_todo.txt (%s); allowed" % why
        if src in ("T1", "T2"):
            return Decision(kind, task, title, warn=warn)
        return Decision("pane", folder_name, title, warn=warn)
    if src in ("T1", "T2"):
        if task in opens:
            return Decision(kind, task, title, block=work_block(ctx, task))
        if unknown:
            return Decision(kind, task, title)
        return Decision(kind, task, title, block='board guard: pane "%s" names %s, which is not an open todo task. '
                        'Run agent-file.sh todo add "%s" ... first.' % (q(title), task, task))
    if src == "T4" and task in opens:
        return Decision("pane", task, title, block=work_block(ctx, task))
    if unknown:
        return Decision("pane", "%s Manager" % main_name, title)
    return Decision("pane", folder_name, title,
                    block='board guard: pane "%s" names no open todo task. Title it "<task> ..." or run '
                          'agent-file.sh todo add first.' % q(title))


def decide_worktree(ctx, name):
    if ctx["role"] != "main" or not name:
        return Decision("", "", "")
    opens, why = read_todo(ctx["main"])
    if opens is None:
        return Decision("", "", "", warn="board guard: cannot read agent_todo.txt (%s); allowed" % why)
    if name in opens:
        return Decision("", "", "")
    return Decision("", "", "", block='board guard: worktree "%s" is not an open todo task. Run agent-file.sh todo '
                                      'add "%s" ... first.' % (q(name), name))


# ------------------------------------------------------------------ the events

def make_context(payload):
    cwd = payload.get("cwd") or os.getcwd()
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()
    rc, out = git(cwd, "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-dir", "--git-common-dir")
    if rc != 0:
        return None
    lines = out.split("\n")
    if len(lines) < 3 or not lines[0]:
        return None
    folder, gitdir, common = lines[0], lines[1], lines[2]
    rc, out = git(cwd, "worktree", "list", "--porcelain")
    main = None
    if rc == 0:
        for line in out.split("\n"):
            if line.startswith("worktree "):
                main = line[9:]
                break
    if not main or not os.path.isfile(os.path.join(main, "agent_todo.txt")):
        return None
    mode, keep = read_conf(main)
    ctx = {"folder": folder, "gitdir": gitdir, "common": common, "main": main, "mode": mode,
           "keep": keep, "now": now_str(), "pid": session_pid()}
    ctx["role"] = find_role(payload, ctx)
    return ctx


def model_header(ctx, text, transcript):
    """(block, note) of model-floor (requirements/model-floor.md): an order's header must be the sender's current
    model and effort, and a main manager under the floor needs the owner's MODEL OK."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        old = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            if here not in sys.path:
                sys.path.insert(0, here)
            import agent_model
        finally:
            sys.dont_write_bytecode = old
        block, note = agent_model.header_verdict(text, transcript)
        if not block and note is None and agent_model.HEADER.match(text or ""):
            block = agent_model.below_floor_verdict(ctx["common"], transcript, ctx["role"])
        return block, note
    except Exception:
        return None, None


def key_of(tid, n):
    """The record key of the n-th (1-based) create of one Bash call."""
    tid = tid or "toolu_none_%d" % int(time.time())
    return tid if n == 1 else "%s#%d" % (tid, n)


def handle(payload):
    ev = payload.get("hook_event_name")
    tool = payload.get("tool_name")
    tin = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    tid = payload.get("tool_use_id") or ""
    ops = []
    kind = None
    if ev in ("PreToolUse", "PostToolUse"):
        if tool in ("Agent", "Task"):
            kind = "agent"
            if ev == "PreToolUse":
                _POINT["moment"] = POINT_AGENTS.get(base_type(str(tin.get("subagent_type") or "")))
        elif tool == "Bash":
            command = str(tin.get("command") or "")
            ops = bash_launches(command)
            if ev == "PreToolUse":
                _POINT["moment"] = bash_moment(command, ops)
            if not ops and not _POINT["moment"]:
                return OK
            kind = "bash"
        else:
            return OK
    elif ev not in ("SubagentStart", "SubagentStop"):
        return OK

    ctx = make_context(payload)
    if ctx is None:
        return OK
    _POINT["ctx"] = ctx
    _POINT["sid"] = str(payload.get("session_id") or "")
    quiet = ctx["role"] == "free"

    if ev == "PreToolUse":
        if ctx["pid"] is None:  # unknown session: no record, never main
            return OK
        note = None
        if not payload.get("agent_id"):   # a subagent's own model is not in the settings: not checked
            texts = [str(tin.get("prompt") or "")] if kind == "agent" else [
                o.get("text") or o.get("body") or "" for op, o in ops if op == "send"]
            for text in texts:
                block, note = model_header(ctx, text, payload.get('transcript_path'))
                if block:
                    return ("BLOCK", block)
        if kind == "bash" and not any(op in ("create", "wt_create") for op, _ in ops):
            return ("WARN", note) if note else OK
        if kind == "bash":
            items, n = [], 0
            for op, opts in ops:
                if op == "wt_create":
                    items.append((decide_worktree(ctx, opts.get("name", "")), None))
                elif op == "create":
                    n += 1
                    d = decide_pane(ctx, pane_title(opts))
                    extra = {}
                    if opts.get("environment"):
                        extra["env"] = opts["environment"]
                    if opts.get("worktree") and "$" not in opts["worktree"]:
                        extra["worktree"] = path_value(opts["worktree"])
                    items.append((d, (key_of(tid, n), extra)))
            return finish(ctx, items, quiet)
        desc = str(tin.get("description") or "")
        stype = str(tin.get("subagent_type") or "") or "general-purpose"
        d = decide_agent(ctx, desc, stype)
        res = finish(ctx, [(d, (key_of(tid, 1), {"type": stype}))], quiet)
        return ("WARN", note) if note and res == OK else res

    if ev == "PostToolUse":
        if not tid:
            return OK
        if kind == "agent":
            resp = payload.get("tool_response")
            if not isinstance(resp, dict) or not resp.get("status"):
                return OK
            aid = str(resp.get("agentId") or "")
            if resp.get("status") == "completed":
                run_edit(ctx, mut_remove(lambda d: d["key"] == tid or (aid != "" and d.get("agent") == aid)))
                return OK
            if not aid:
                return OK

            def mutate(lines):
                out, hit = [], False
                for line in lines:
                    d = parse_launch(line)
                    if d is not None:
                        if d["key"] == tid:
                            d["agent"] = aid
                            line = build_launch(d)
                            hit = True
                        elif d.get("agent") == aid:
                            d.pop("agent")
                            line = build_launch(d)
                            hit = True
                    out.append(line)
                return out if hit else None
            run_edit(ctx, mutate)
            return OK
        resp = payload.get("tool_response")
        text = resp.get("stdout") if isinstance(resp, dict) else resp
        text = text if isinstance(text, str) else json.dumps(text)
        handles = re.findall(r'"handle"\s*:\s*"([^"]+)"', text) or re.findall(r"term_[\w-]+", text)
        paths = [m.rsplit("::", 1)[-1] for m in re.findall(r'"worktreeId"\s*:\s*"([^"]+)"', text)] or \
            re.findall(r'"path"\s*:\s*"([^"]+)"', text)
        n = 0
        for op, opts in ops:
            if op == "create":
                n += 1
                f = {}
                if n <= len(handles):
                    f["pane"] = handles[n - 1]
                if "$" in opts.get("worktree", "") and n <= len(paths) and paths[n - 1] and "$" not in paths[n - 1]:
                    f["worktree"] = path_value(paths[n - 1])
                if f:
                    run_edit(ctx, mut_set(lambda d, k=key_of(tid, n): d["key"] == k, **f))
            elif op == "close":
                h = opts.get("terminal", "")
                if h:
                    run_edit(ctx, mut_remove(lambda d, h=h: d.get("pane") == h))
            elif op == "wt_rm":
                w = path_value(opts.get("worktree", ""))
                if w and "$" not in w:
                    run_edit(ctx, mut_remove(lambda d, w=w: d.get("worktree") == w))
        return OK

    if ev == "SubagentStart":
        aid = str(payload.get("agent_id") or "")
        atype = base_type(str(payload.get("agent_type") or ""))
        pid = ctx["pid"]
        if not aid or pid is None:
            return OK

        def mutate(lines):
            for idx in range(len(lines)):  # the OLDEST unlinked record of this session and type
                d = parse_launch(lines[idx])
                if d is None or d.get("agent") or d.get("kind") in PANE_KINDS:
                    continue
                if d.get("pid") != str(pid) or base_type(d.get("type", "")) != atype:
                    continue
                d["agent"] = aid
                out = list(lines)
                out[idx] = build_launch(d)
                return out
            return None
        if not run_edit(ctx, mutate):
            for c in other_folders(ctx):
                if run_edit(c, mutate):
                    break
        return OK

    if ev == "SubagentStop":
        aid = str(payload.get("agent_id") or "")
        if aid:
            gone = mut_remove(lambda d: d.get("agent") == aid)
            if not run_edit(ctx, gone):
                for c in other_folders(ctx):
                    if run_edit(c, gone):
                        break
        return OK
    return OK


def run_edit(ctx, mutate):
    """Post-side edits: failures here never block; a busy lock is a WARN (silent for the free role)."""
    try:
        return edit_records(ctx, mutate)
    except Busy:
        if ctx["role"] != "free":
            raise Warn("board guard: state file busy; allowed")
    return False


def other_folders(ctx):
    """Contexts of every other worktree of the repo. A subagent started with isolation worktree runs with its cwd in
    a fresh worktree, but its LAUNCH record sits in the launching session's folder (rule 1, 3): look there too."""
    out = []
    rc, text = git(ctx["folder"], "worktree", "list", "--porcelain")
    if rc != 0:
        return out
    for line in text.split("\n"):
        if not line.startswith("worktree "):
            continue
        folder = line[9:]
        if folder == ctx["folder"] or not os.path.isfile(os.path.join(folder, "agent_state.txt")):
            continue
        rc, gd = git(folder, "rev-parse", "--path-format=absolute", "--git-dir")
        if rc == 0 and gd:
            c = dict(ctx)
            c["folder"], c["gitdir"] = folder, gd.split("\n")[0]
            out.append(c)
    return out


def write_launch_record(ctx, task, stype):
    """F2: a durable line per reviewer / check-deputy launch in <git common dir>/agent_launches.jsonl."""
    base = base_type(stype)
    if base not in ("reviewer", "check-deputy"):
        return
    rec = {"task": task, "type": base, "by": ctx["role"], "at": ctx["now"]}
    try:
        with open(os.path.join(ctx["common"], "agent_launches.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def finish(ctx, items, quiet):
    """items: [(Decision, (key, extra) or None)]. Block (whole call) or record, then the protocol line."""
    if ctx["mode"] == "on":
        for d, _ in items:
            if d.block:
                return ("BLOCK", d.block)
    warn = next((d.warn for d, _ in items if d.warn), None)
    for d, rec in items:
        if rec is None:
            continue
        key, extra = rec
        fields = {"key": key, "kind": d.kind, "task": d.task, "title": clean_title(d.title), "since": ctx["now"],
                  "pid": str(ctx["pid"]), "by": ctx["role"]}
        fields.update(extra)
        write_launch_record(ctx, d.task, fields.get("type", ""))
        try:
            add_record(ctx, build_launch(fields))
        except Busy:
            if not quiet and not warn:
                warn = "board guard: state file busy; allowed"
            break
    if warn and not quiet:
        return ("WARN", warn)
    return OK


def run(raw):
    try:
        payload = json.loads(raw)
    except ValueError:
        return ("WARN", "board guard: bad hook JSON; allowed")
    if not isinstance(payload, dict):
        return ("WARN", "board guard: bad hook JSON; allowed")
    _POINT.update(moment=None, ctx=None, sid="")
    res = handle(payload)
    if res[0] == "BLOCK":
        return res
    line = point_line(_POINT["ctx"])
    return res + (line,) if line else res


def main():
    try:
        raw = sys.stdin.read()
        got = run(raw)
        status, text = got[0], got[1]
        point = got[2] if len(got) > 2 else ""
    except Warn as e:
        point = ""
        status, text = "WARN", str(e) if str(e).startswith("board guard:") else "board guard: %s; allowed" % e
    except Exception as e:  # never raise
        point = ""
        what = one_line("%s %s" % (type(e).__name__, e))[:60]
        status, text = "WARN", "board guard: %s; allowed" % what
    line = status if not text else "%s %s" % (status, one_line(text))
    try:
        sys.stdout.write(("POINT %s\n" % one_line(point) if point else "") + line + "\n")
        sys.stdout.flush()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
