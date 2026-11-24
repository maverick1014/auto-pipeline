"""Shared fixture for the one-watcher tests (requirements/one-watcher.md).

Used by tests/test_watch_all.py (the all mode, probe, single mode additions),
tests/test_watch_tell.py (agent-file.sh tell) and tests/test_watch_board.py.

The fake orca (ALL_STUB) keeps its state under $ORCA_STUB_DIR:

    ps_fail                  `worktree ps` fails while this count is above 0
                             (one less per call): the runtime probe says plain
    lists/<env|local>.json   what `terminal list` prints: a JSON list of terminals
                             ({handle, title, worktreePath, worktreeId?, agentIdentity?});
                             --worktree path:<p> keeps those whose worktreePath is <p>
    worktrees/local.json     what `worktree list` prints (result.worktrees)
    pane/<h>/env             the machine a pane lives on (absent: this machine); a call
                             with another --environment, or none, gets terminal_not_found
    pane/<h>/exit.json       what `terminal wait --for exit` gives (result.wait);
                             absent: a timeout error
    pane/<h>/idle_timeout    `terminal wait --for tui-idle` times out (exit 1)
    screens/<h>/1..n         a TM pane: the k-th read returns frame min(k, n); a frame
                             whose first line is FAIL makes the read fail
    screens/<h>/hook.sh      bash, run with k after the k-th read of that pane
    screens/<h>/exited_from  read number k >= this: status "exited", tail []
    shell/<h>/buf            a shell pane: a send runs the text with bash (env map
                             applied) and appends "$ <text>" and its output; a read
                             returns the lines after --cursor, latestCursor = line count
    echo/<h>/buf             a TM pane that shows what is sent to it ("❯ <text>");
                             echo/<h>/drop holds a count of sends that are lost
    env/<env>/down           that machine is unreachable: every call with it fails
    env/<env>/map            lines "<from>\\t<to>": a shell command on that machine has
                             <from> replaced by <to> (the other machine's folders live
                             under the test's temp dir)

A handle with no folder at all answers like real orca for a gone pane: a JSON
error terminal_handle_stale on stdout, exit 1.
"""

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase  # noqa: E402,F401

ALL_STUB = r'''#!/usr/bin/env python3
"""Fake orca for the one-watcher tests. Never talks to the real app."""
import json, os, subprocess, sys

args = sys.argv[1:]
with open(os.environ["ORCA_STUB_LOG"], "a") as fh:
    fh.write("CALL" + "".join("\t" + a for a in args) + "\n")


def opt(name):
    for i, a in enumerate(args[:-1]):
        if a == name:
            return args[i + 1]
    return None


def out(obj, code=0):
    print(json.dumps(obj))
    sys.exit(code)


def err(code):
    out({"ok": False, "error": {"code": code, "message": code}}, 1)


def rd(path, default=None):
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return default


D = os.environ["ORCA_STUB_DIR"]
env = opt("--environment") or ""
term = opt("--terminal") or ""
verb = " ".join(args[:2])
if env and os.path.exists(os.path.join(D, "env", env, "down")):
    sys.stderr.write("orca: environment %s is not reachable\n" % env)
    sys.exit(1)
if verb == "worktree ps":
    f = os.path.join(D, "ps_fail")
    n = int((rd(f, "0") or "0").strip() or 0)
    if n > 0:
        with open(f, "w") as fh:
            fh.write(str(n - 1))
        sys.stderr.write("orca: not running\n")
        sys.exit(1)
    sys.stdout.write(rd(os.environ["ORCA_STUB_PS"], '{"ok":true,"result":{"worktrees":[]}}'))
    sys.exit(0)
if verb == "worktree list":
    ws = json.loads(rd(os.path.join(D, "worktrees", (env or "local") + ".json"), "[]"))
    out({"ok": True, "result": {"worktrees": ws}})
if verb == "terminal list":
    terms = json.loads(rd(os.path.join(D, "lists", (env or "local") + ".json"), "[]"))
    wt = opt("--worktree")
    if wt:
        p = wt[5:] if wt.startswith("path:") else wt
        terms = [t for t in terms if t.get("worktreePath") == p]
    out({"ok": True, "result": {"terminals": terms, "totalCount": len(terms), "truncated": False}})
if not verb.startswith("terminal"):
    out({"ok": True, "result": {}})

screens = os.path.join(D, "screens", term)
shell = os.path.join(D, "shell", term)
echo = os.path.join(D, "echo", term)
pane = os.path.join(D, "pane", term)
if not term or not any(os.path.isdir(x) for x in (screens, shell, echo)):
    err("terminal_handle_stale")
if (rd(os.path.join(pane, "env"), "") or "").strip() != env:
    err("terminal_not_found")


def term_json(tail, cursor, status="running"):
    return {"ok": True, "result": {"terminal": {
        "handle": term, "status": status, "tail": tail,
        "latestCursor": str(cursor), "nextCursor": str(cursor), "source": "screen"}}}


def buf_read(folder):
    lines = (rd(os.path.join(folder, "buf"), "") or "").splitlines()
    cursor = opt("--cursor")
    out(term_json(lines[int(cursor):] if cursor else lines[-40:], len(lines)))


if verb == "terminal wait":
    cond = opt("--for")
    if cond == "exit":
        w = rd(os.path.join(pane, "exit.json"))
        if w is None:
            err("timeout")
        out({"ok": True, "result": {"wait": json.loads(w)}})
    if os.path.exists(os.path.join(pane, "idle_timeout")):
        err("timeout")
    out({"ok": True, "result": {"wait": {"condition": cond, "satisfied": True}}})

if verb == "terminal read" and os.path.isdir(screens):
    cf = os.path.join(screens, "count")
    n = int((rd(cf, "0") or "0").strip() or 0) + 1
    with open(cf, "w") as fh:
        fh.write(str(n))
    frames = sorted(int(x) for x in os.listdir(screens) if x.isdigit())
    hook = os.path.join(screens, "hook.sh")
    if os.path.exists(hook):
        subprocess.run(["bash", hook, str(n)])
    ex = rd(os.path.join(screens, "exited_from"))
    if ex is not None and n >= int(ex.strip()):
        out(term_json([], n, "exited"))
    frame = rd(os.path.join(screens, str(min(n, frames[-1])))) if frames else ""
    if frame.startswith("FAIL"):
        sys.stderr.write("orca: terminal read failed\n")
        sys.exit(1)
    out(term_json(frame.splitlines(), n))
if verb == "terminal read" and os.path.isdir(shell):
    buf_read(shell)
if verb == "terminal read" and os.path.isdir(echo):
    buf_read(echo)
if verb == "terminal send" and os.path.isdir(shell):
    sent = opt("--text") or ""
    text = sent
    if env:
        for row in (rd(os.path.join(D, "env", env, "map"), "") or "").splitlines():
            a, _, b = row.partition("\t")
            if a:
                text = text.replace(a, b)
    run = subprocess.run(["bash", "-c", text], capture_output=True, text=True)
    with open(os.path.join(shell, "buf"), "a") as fh:
        fh.write("$ " + sent + "\n" + run.stdout + run.stderr)
    out({"ok": True, "result": {}})
if verb == "terminal send" and os.path.isdir(echo):
    df = os.path.join(echo, "drop")
    n = int((rd(df, "0") or "0").strip() or 0)
    if n > 0:
        with open(df, "w") as fh:
            fh.write(str(n - 1))
    else:
        with open(os.path.join(echo, "buf"), "a") as fh:
            fh.write("\u276f " + (opt("--text") or "") + "\n")
    out({"ok": True, "result": {}})
out({"ok": True, "result": {}})
'''

ENV = "maverick-pc2"
SINCE = "2026-11-24 08:00"

STATE_HEAD = (
    "[Opus 5.5 xhigh] Brief from the main manager: you are the task manager for \"feat\".\n"
    "REPORT: append under \"=== REPORT ===\" here. First line \"DONE PASS feat\".\n"
    "ASK: append \"QUESTION: ...\" here.\n"
)

SWEEP = re.compile(r"^\d\d:\d\d sweep: ")
WAKE_WORDS = ("DONE PASS", "DONE FAIL", "CLOSE CASE", "QUESTION:", "MOCK READY")
LOGIN_TEXTS = ("Please run /login", "OAuth token has expired", "Invalid API key", "API Error: 401")
EXITED = {"condition": "exit", "satisfied": True, "status": "exited", "exitCode": 0,
          "exitCause": {"kind": "operator_close"}}


def frame(n, extra=()):
    """A busy Claude Code screen that moves: the ✻ line changes with n."""
    return ([
        "⏺ Bash(python3 -m unittest tests.test_x)",
        "  ⎿  Ran 4 tests in 0.%ds" % n,
        "",
    ] + list(extra) + [
        "✻ Working… (%ds · esc to interrupt)" % (10 + n),
        "",
        "❯ ",
        "  ⏵⏵ bypass permissions on (shift+tab to cycle)",
    ])


STILL = frame(0)


def idle(n=0):
    """A Claude Code screen at its input prompt: no "esc to interrupt", a ❯ line inside the box."""
    return [
        "⏺ Done for now%s." % ("" if not n else " (%d)" % n),
        "",
        "╭──────────────────────────╮",
        "│ ❯                        │",
        "╰──────────────────────────╯",
        "  ⏵⏵ bypass permissions on (shift+tab to cycle)",
    ]


def moving(n=40, extra_at=None, extra=()):
    return [frame(i, extra if i == extra_at else ()) for i in range(1, n + 1)]


def sh_quote(text):
    return "'" + text.replace("'", "'\\''") + "'"


def sha8(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def now_text(minutes_ago=0):
    t = datetime.datetime.now() - datetime.timedelta(minutes=minutes_ago)
    return t.strftime("%Y-%m-%d %H:%M")


def dead_pid():
    """A pid that answers no kill -0 (a child that has already ended)."""
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


class AllCase(ScriptCase):
    """One main repo (the project), its task worktrees, the fake orca."""

    script = "agent-watch.sh"

    def setUp(self):
        super().setUp()
        self.repo.stub_tool("orca", ALL_STUB)
        self.d = self.repo.orca_dir
        self.status_path = self.repo.path(".git", "agent_watch.json")
        self.rows = []      # agent_worktree.txt rows: (path, name, status)
        self.tasks = {}     # name -> {"path", "real", "state", "env", "pane", "shell"}

    # ---- the fake orca ----

    def folder(self, *parts):
        full = os.path.join(self.d, *parts)
        os.makedirs(full, exist_ok=True)
        return full

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)

    def pane_env(self, handle, env):
        if env:
            self.write(os.path.join(self.folder("pane", handle), "env"), env)

    def screens(self, handle, frames, env=None):
        folder = self.folder("screens", handle)
        for name in os.listdir(folder):
            if name.isdigit() or name == "count":
                os.remove(os.path.join(folder, name))
        for i, lines in enumerate(frames, 1):
            self.write(os.path.join(folder, str(i)), "\n".join(lines) + "\n")
        self.pane_env(handle, env)

    def reset_reads(self, handle):
        count = os.path.join(self.d, "screens", handle, "count")
        if os.path.exists(count):
            os.remove(count)

    def hook(self, handle, body):
        """Bash run after each read of that TM pane, $1 = read number."""
        self.write(os.path.join(self.folder("screens", handle), "hook.sh"), body)

    def on_read(self, handle, path, mapping):
        """{read number: line} appended to the file at path after that read."""
        self.hook(handle, "".join('[ "$1" = "%d" ] && printf "%%s\\n" %s >> %s\n'
                                  % (k, sh_quote(line), sh_quote(path))
                                  for k, line in sorted(mapping.items())))

    def exited(self, handle, from_read=2, cause=True):
        self.write(os.path.join(self.folder("screens", handle), "exited_from"), str(from_read))
        if cause:
            self.write(os.path.join(self.folder("pane", handle), "exit.json"), json.dumps(EXITED))

    def shell_pane(self, handle, env=None):
        self.write(os.path.join(self.folder("shell", handle), "buf"), "Last login: Mon Nov 23 16:00:00\n$ \n")
        self.pane_env(handle, env)

    def echo_pane(self, handle, env=None, drop=0):
        folder = self.folder("echo", handle)
        self.write(os.path.join(folder, "buf"), "⏺ Working on step 4.\n\n❯ \n")
        if drop:
            self.write(os.path.join(folder, "drop"), str(drop))
        self.pane_env(handle, env)

    def echo_buf(self, handle):
        with open(os.path.join(self.d, "echo", handle, "buf")) as fh:
            return fh.read()

    def terminals(self, items, env=None):
        self.write(os.path.join(self.folder("lists"), (env or "local") + ".json"), json.dumps(items))

    def worktree_list(self, items):
        self.write(os.path.join(self.folder("worktrees"), "local.json"), json.dumps(items))

    def map_env(self, env):
        """The other machine's folder /remote/<env> lives at <base>/remote/<env> here."""
        real = os.path.join(self.repo.base, "remote", env)
        os.makedirs(real, exist_ok=True)
        self.write(os.path.join(self.folder("env", env), "map"), "/remote/%s\t%s\n" % (env, real))
        return real

    def ps_fail(self, n):
        self.write(os.path.join(self.d, "ps_fail"), str(n))

    # ---- the project's files ----

    def write_rows(self):
        self.repo.set_worktree_lines(self.rows)

    def launch(self, kind, task, handle, env=None, title=None, since=SINCE, pid=None, key=None):
        line = "LAUNCH %s: %s | task %s | %s | since %s | pid %d | by main | pane %s" % (
            key or "toolu_%s_%s" % (kind.replace("-", ""), handle), kind, task,
            title or ("%s Task Manager" % task if kind == "tm-pane" else "%s shell" % task),
            since, pid or os.getpid(), handle)
        if env:
            line += " | env %s" % env
        with open(self.repo.path("agent_state.txt"), "a") as fh:
            fh.write(line + "\n")

    def task(self, name, status="working", env=None, pane=None, shell=None, launch=True,
             frames=None, git=False, row=True, echo=False):
        """A task worktree with its agent_state.txt, its agent_worktree.txt row, its TM pane
        (a screens pane, or an echo pane with echo=True) and its LAUNCH record.
        env: the TM runs on that machine; its folder is /remote/<env>/wt_<name> there."""
        pane = pane or "term_" + name
        if env:
            real_root = self.map_env(env)
            path = "/remote/%s/wt_%s" % (env, name)
            real = os.path.join(real_root, "wt_" + name)
            shell = shell or "sh_" + name
        else:
            path = real = os.path.join(self.repo.base, "wt_" + name)
        os.makedirs(real, exist_ok=True)
        if git and not os.path.isdir(os.path.join(real, ".git")):
            self.repo.git_init(real)
        state = os.path.join(real, "agent_state.txt")
        with open(state, "w") as fh:
            fh.write(STATE_HEAD.replace("feat", name))
        if row:
            self.rows.append((path, name, status))
            self.write_rows()
        if echo:
            self.echo_pane(pane, env)
        else:
            self.screens(pane, frames or moving(), env)
        if env:
            self.shell_pane(shell, env)
        if launch:
            self.launch("tm-pane", name, pane, env)
            if env:
                self.launch("shell-pane", name, shell, env)
        t = {"path": path, "real": real, "state": state, "env": env, "pane": pane, "shell": shell}
        self.tasks[name] = t
        return t

    def append_state(self, name, *lines):
        with open(self.tasks[name]["state"], "a") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def state_text(self, name):
        with open(self.tasks[name]["state"]) as fh:
            return fh.read()

    def on_task_read(self, name, mapping):
        t = self.tasks[name]
        self.on_read(t["pane"], t["state"], mapping)

    def todo(self, name, *where):
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add", name, "big", "the %s task" % name, "60"))
        if where:
            self.assertOk(self.repo.run("agent-file.sh", "todo", "where", name, *where))

    def todo_line(self, name):
        for line in (self.repo.read("agent_todo.txt") or "").splitlines():
            if line.split(" | ")[0] == name:
                return line
        return None

    def write_status(self, data):
        self.write(self.status_path, json.dumps(data))

    def status(self):
        with open(self.status_path) as fh:
            return json.load(fh)

    # ---- running ----

    def run_all(self, *extra, env=None, max_sweeps="6", timeout=90, ok=True):
        args = ["--all"] + (["--max", max_sweeps] if max_sweeps else []) + list(extra)
        run_env = {"AGENT_RUNTIME": "orca", "AGENT_WATCH_INTERVAL_S": "0", "AGENT_WATCH_RETRY_S": "0"}
        run_env.update(env or {})
        result = self.repo.run("agent-watch.sh", *args, env=run_env, timeout=timeout, cwd=self.repo.dir)
        self.assertNoSendToTm()
        if ok:
            self.assertOk(result)
        return result

    def text(self, result):
        return result.stdout + result.stderr

    def watch_lines(self, text):
        return [l for l in self.lines(text) if l.startswith("WATCH ")]

    def one_watch(self, text):
        hits = self.watch_lines(text)
        self.assertEqual(len(hits), 1, "want one WATCH line:\n" + text)
        return hits[0]

    def after(self, text, watch_line):
        lines = self.lines(text)
        i = lines.index(watch_line)
        rest = []
        for l in lines[i + 1:]:
            if l.startswith("WATCH "):
                break
            rest.append(l)
        return rest

    def sweeps(self, text):
        return [l for l in self.lines(text) if SWEEP.match(l)]

    # ---- what orca saw ----

    def terminal_calls(self, verb):
        return [c for c in self.repo.calls() if c[:2] == ["terminal", verb]]

    def opt(self, call, name):
        return call[call.index(name) + 1] if name in call else None

    def tm_handles(self):
        out = set()
        for kind in ("screens", "echo"):
            folder = os.path.join(self.d, kind)
            if os.path.isdir(folder):
                out.update(os.listdir(folder))
        return out

    def assertNoSendToTm(self, allowed=()):
        """B17: a TM pane is only read. tell (allowed) is the one sender of a pointer line."""
        tms = self.tm_handles() - set(allowed)
        for call in self.terminal_calls("send"):
            self.assertNotIn(self.opt(call, "--terminal"), tms, "sent to a TM pane: %r" % call)
