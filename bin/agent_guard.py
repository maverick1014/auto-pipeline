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
    r = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True, timeout=2)
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
    if v.isdigit():
        return int(v)
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


def read_conf_mode(main):
    mode = "on"
    try:
        with open(os.path.join(main, "agent.conf"), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                k, eq, v = line.partition("=")
                if eq and k.strip() == "board_guard":
                    mode = v.strip().strip("\"'").lower()
    except OSError:
        pass
    return mode if mode in ("record", "off") else "on"


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

def split_commands(s):
    """Simple commands of a shell text: lists of words, quotes removed. Heredoc bodies, comments and
    quoted text never start a command; a command starts after ; & && || | ( $( ` and newline."""
    cmds, words = [], []
    cur = [None]
    heredocs = []
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
            for delim, strip in heredocs:
                while i < n:
                    j = s.find("\n", i)
                    line = s[i:n if j < 0 else j]
                    i = n if j < 0 else j + 1
                    if (line.lstrip("\t") if strip else line).rstrip("\r") == delim:
                        break
            del heredocs[:]
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
        if c == "<" and s.startswith("<<", i) and not s.startswith("<<<", i):
            j = i + 2
            strip = False
            if s[j:j + 1] == "-":
                strip = True
                j += 1
            while j < n and s[j] in " \t":
                j += 1
            if j < n and s[j] in "'\"":
                e = s.find(s[j], j + 1)
                e = n if e < 0 else e
                delim, j = s[j + 1:e], e + 1
            else:
                m = re.match(r"[^\s;&|()<>]+", s[j:])
                delim = m.group(0) if m else ""
                j += len(delim)
            heredocs.append((delim, strip))
            endword()
            i = j
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


def bash_launch(command):
    """(op, opts) of the first orca launch command in a Bash text, else None.
    op: create | close | wt_create | wt_rm."""
    for words in split_commands(command):
        k = 0
        while k < len(words) and RE_ASSIGN.match(words[k]):
            k += 1
        w = words[k:]
        if len(w) < 3 or w[0] != "orca":
            continue
        pair = (w[1], w[2])
        ops = {("terminal", "create"): "create", ("terminal", "close"): "close",
               ("worktree", "create"): "wt_create", ("worktree", "rm"): "wt_rm"}
        if pair in ops:
            return ops[pair], opt_values(w[3:], ("title", "command", "environment", "worktree", "terminal", "name"))
    return None


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


def should_prune(d, now):
    kind = d.get("kind", "")
    pid = d.get("pid", "")
    if kind not in PANE_KINDS and pid.isdigit() and not alive(int(pid)):
        return True
    if not d.get("agent") and not d.get("pane"):
        since, nw = parse_time(d.get("since", "")), parse_time(now)
        if since and nw and (nw - since).total_seconds() > 120:
            return True
    return False


def prune(lines, now):
    out = []
    for line in lines:
        d = parse_launch(line)
        if d is not None and should_prune(d, now):
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


def rewrite(path, compute):
    for _ in range(3):
        before = sig(path)
        new = compute(read_lines(path))
        if new is None:
            return
        tmp = "%s.guard.%d.tmp" % (path, os.getpid())
        try:
            with open(tmp, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
                fh.write("".join(new))
            try:
                os.chmod(tmp, os.stat(path).st_mode & 0o7777)
            except OSError:
                pass
            if sig(path) != before:
                continue
            os.replace(tmp, path)
            return
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    raise Warn("state file changed while writing")


class StateLock:
    def __init__(self, gitdir):
        self.path = os.path.join(gitdir, "agent_guard.lock")
        self.held = False

    def __enter__(self):
        deadline = time.time() + 2.0
        while True:
            try:
                os.mkdir(self.path)
                self.held = True
                return self
            except FileExistsError:
                try:
                    if time.time() - os.stat(self.path).st_mtime > 10:
                        os.rmdir(self.path)
                        continue
                except OSError:
                    pass
            if time.time() >= deadline:
                raise Busy()
            time.sleep(0.05)

    def __exit__(self, *exc):
        if self.held:
            try:
                os.rmdir(self.path)
            except OSError:
                pass
        return False


def add_record(ctx, line):
    path = os.path.join(ctx["folder"], "agent_state.txt")
    with StateLock(ctx["gitdir"]):
        lines = read_lines(path)
        pruned = prune(lines, ctx["now"])
        if len(pruned) == len(lines):
            with open(path, "a", encoding="utf-8", errors="surrogateescape", newline="") as fh:
                if lines and not lines[-1].endswith("\n"):
                    fh.write("\n")
                fh.write(line)
        else:
            rewrite(path, lambda ls: prune(ls, ctx["now"]) + [line])


def edit_records(ctx, mutate):
    """mutate(list of lines) -> new list or None (no change). Edits and removals only."""
    path = os.path.join(ctx["folder"], "agent_state.txt")
    if mutate(read_lines(path)) is None:
        return
    with StateLock(ctx["gitdir"]):
        def compute(lines):
            new = mutate(lines)
            return None if new is None else prune(new, ctx["now"])
        rewrite(path, compute)


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


def decide_agent(ctx, desc, stype):
    base = base_type(stype)
    kind_t = TYPE_KINDS.get(base, "agent")
    pd = parse_desc(desc)
    first = re.split(r"[\s:]", desc.strip(), 1)[0] if desc.strip() else ""
    role = ctx["role"]
    if role == "tm":
        own = own_task(ctx)
        if pd and pd[0] != own:
            return Decision(pd[1], pd[0], pd[2], block='board guard: you are the %s task manager; "%s" names task '
                            '%s. Launch only for %s.' % (own, q(desc), pd[0], own))
        if pd:
            return Decision(pd[1], pd[0], pd[2])
        return Decision(kind_t, own, desc)
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
            return Decision(pd[1], pd[0], pd[2])
        if not ro:
            return Decision(pd[1], pd[0], pd[2], block=not_open_msg(desc, pd[0]))
    elif first in opens:
        return Decision(kind_t, first, desc)
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
    word = re.split(r"[\s:]", rest.strip(), 1)[0] if rest.strip() else ""
    return "pane", word or None, "T4"


def decide_pane(ctx, title):
    kind, task, src = parse_title(title)
    role = ctx["role"]
    folder_name = os.path.basename(ctx["folder"].rstrip("/"))
    if src == "T3":
        return Decision(kind, task, title)
    if role == "tm":
        own = own_task(ctx)
        if src in ("T1", "T2") and task != own:
            return Decision(kind, task, title, block='board guard: you are the %s task manager; "%s" names task '
                            '%s. Launch only for %s.' % (own, q(title), task, own))
        return Decision(kind, own, title)
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
            return Decision(kind, task, title)
        return Decision(kind, task, title, block='board guard: pane "%s" names %s, which is not an open todo task. '
                        'Run agent-file.sh todo add "%s" ... first.' % (q(title), task, task))
    if src == "T4" and task in opens:
        return Decision("pane", task, title)
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
    if not main or not os.path.isfile(os.path.join(main, "agent.conf")):
        return None
    mode = read_conf_mode(main)
    if mode == "off":
        return None
    ctx = {"folder": folder, "gitdir": gitdir, "common": common, "main": main, "mode": mode,
           "now": now_str(), "pid": session_pid()}
    ctx["role"] = find_role(payload, ctx)
    return ctx


def handle(payload):
    ev = payload.get("hook_event_name")
    tool = payload.get("tool_name")
    tin = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    tid = payload.get("tool_use_id") or ""
    op, opts = None, {}
    kind = None
    if ev in ("PreToolUse", "PostToolUse"):
        if tool in ("Agent", "Task"):
            kind = "agent"
        elif tool == "Bash":
            found = bash_launch(str(tin.get("command") or ""))
            if not found:
                return OK
            op, opts = found
            kind = "bash"
        else:
            return OK
    elif ev not in ("SubagentStart", "SubagentStop"):
        return OK

    ctx = make_context(payload)
    if ctx is None:
        return OK
    quiet = ctx["role"] == "free"

    if ev == "PreToolUse":
        if kind == "bash" and op in ("close", "wt_rm"):
            return OK
        if kind == "bash" and op == "wt_create":
            d = decide_worktree(ctx, opts.get("name", ""))
            return finish(ctx, d, None, quiet)
        if kind == "bash":
            d = decide_pane(ctx, pane_title(opts))
            extra = {}
            if opts.get("environment"):
                extra["env"] = opts["environment"]
            if opts.get("worktree"):
                extra["worktree"] = path_value(opts["worktree"])
            return finish(ctx, d, (tid, extra, None), quiet)
        desc = str(tin.get("description") or "")
        stype = str(tin.get("subagent_type") or "") or "general-purpose"
        d = decide_agent(ctx, desc, stype)
        extra = {"type": stype}
        if payload.get("agent_id"):
            pass
        return finish(ctx, d, (tid, extra, None), quiet)

    if ev == "PostToolUse":
        if not tid:
            return OK
        if kind == "agent":
            resp = payload.get("tool_response")
            status = resp.get("status") if isinstance(resp, dict) else None
            if not status:
                return OK
            if status == "async_launched":
                aid = resp.get("agentId")
                if not aid:
                    return OK
                aid = str(aid)

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
            else:
                run_edit(ctx, mut_remove(lambda d: d["key"] == tid))
            return OK
        if op == "create":
            resp = payload.get("tool_response")
            text = resp.get("stdout") if isinstance(resp, dict) else resp
            text = text if isinstance(text, str) else json.dumps(text)
            m = re.search(r'"handle"\s*:\s*"([^"]+)"', text) or re.search(r"term_[\w-]+", text)
            if not m:
                return OK
            handle_ = m.group(1) if m.re.groups else m.group(0)
            run_edit(ctx, mut_set(lambda d: d["key"] == tid, pane=handle_))
            return OK
        if op == "close":
            h = opts.get("terminal", "")
            if h:
                run_edit(ctx, mut_remove(lambda d: d.get("pane") == h))
            return OK
        if op == "wt_rm":
            p = path_value(opts.get("worktree", ""))
            if p:
                run_edit(ctx, mut_remove(lambda d: d.get("worktree") == p))
            return OK
        return OK

    if ev == "SubagentStart":
        aid = str(payload.get("agent_id") or "")
        atype = base_type(str(payload.get("agent_type") or ""))
        if not aid:
            return OK
        pid = ctx["pid"]

        def mutate(lines):
            pick = None
            for idx in range(len(lines) - 1, -1, -1):
                d = parse_launch(lines[idx])
                if d is None or d.get("agent") or d.get("kind") in PANE_KINDS:
                    continue
                if pid is not None and d.get("pid") != str(pid):
                    continue
                if base_type(d.get("type", "")) != atype:
                    continue
                pick = idx
                break
            if pick is None:
                return None
            d = parse_launch(lines[pick])
            d["agent"] = aid
            out = list(lines)
            out[pick] = build_launch(d)
            return out
        run_edit(ctx, mutate)
        return OK

    if ev == "SubagentStop":
        aid = str(payload.get("agent_id") or "")
        if aid:
            run_edit(ctx, mut_remove(lambda d: d.get("agent") == aid))
        return OK
    return OK


def run_edit(ctx, mutate):
    """Post-side edits: failures here never block; they surface as a WARN through Warn."""
    try:
        edit_records(ctx, mutate)
    except Busy:
        if ctx["role"] != "free":
            raise Warn("board guard: state file busy; allowed")


def finish(ctx, d, rec, quiet):
    """Block or record, then the protocol line."""
    if d.block and ctx["mode"] == "on":
        return ("BLOCK", d.block)
    warn = d.warn
    if rec is not None:
        tid, extra, _ = rec
        fields = {"key": tid or "toolu_none_%d" % int(time.time()), "kind": d.kind, "task": d.task,
                  "title": clean_title(d.title), "since": ctx["now"],
                  "pid": str(ctx["pid"] if ctx["pid"] is not None else 0), "by": ctx["role"]}
        fields.update(extra)
        try:
            add_record(ctx, build_launch(fields))
        except Busy:
            if not quiet and not warn:
                warn = "board guard: state file busy; allowed"
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
    return handle(payload)


def main():
    try:
        raw = sys.stdin.read()
        status, text = run(raw)
    except Warn as e:
        status, text = "WARN", str(e) if str(e).startswith("board guard:") else "board guard: %s; allowed" % e
    except Exception as e:  # never raise
        what = one_line("%s %s" % (type(e).__name__, e))[:60]
        status, text = "WARN", "board guard: %s; allowed" % what
    line = status if not text else "%s %s" % (status, one_line(text))
    try:
        sys.stdout.write(line + "\n")
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
