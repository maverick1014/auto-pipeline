"""Helpers to run this plugin's shell scripts against a throwaway project.

Two roots, always separate in a test, because that is how the plugin is used:

    PLUGIN root   the folder above bin/. Holds PRINCIPLES.md, bin/, the quiz,
                  agent_conf.py, the agent.conf template. Read only.
    PROJECT root  the repo being worked on. Holds agent.conf, the four
                  agent_*.txt, agent_monitor.txt, .secrets/ and the lock.

`ScriptRepo.plugin` is the first, `ScriptRepo.dir` the second. A script is
always started by its absolute path inside the plugin, with the working
directory somewhere in the project, so every test proves the two-root rule.

No test ever calls the real orca. A stub named `orca` is put first on PATH and
prints canned JSON. Every call it receives is logged, one tab-separated line
per call, so a test can assert on the exact arguments.

Stub environment (set by run()):
    ORCA_STUB_LOG    file the stub appends its calls to
    ORCA_STUB_PS     file holding the JSON that `orca worktree ps --json` prints
    ORCA_STUB_SLEEP  seconds the stub waits before printing (slow-call tests)
"""

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")

# Copied into the temp plugin's bin/ when they exist. A script still being
# written by another worker is simply skipped, so unrelated tests keep running.
COPY_BIN = [
    "agent-start.sh",
    "agent-file.sh",
    "agent-settings.sh",
    "agent-resume.sh",
    "agent-monitor.sh",
    "agent-resources.sh",
    "agent-init.sh",
    "agent-roots.sh",
    "agent_conf.py",
    "agent.conf.default",
]

# Copied into the temp plugin's root.
COPY_PLUGIN = [
    "PRINCIPLES.md",
]

# Per-project files. agent.conf is seeded from the repo's own one so a test
# starts from the real defaults.
PROJECT_TXT = [
    "agent_todo.txt",
    "agent_completed.txt",
    "agent_ideas.txt",
    "agent_worktree.txt",
]

ORCA_STUB = r"""#!/usr/bin/env bash
# Test stub for orca. Never talks to the real app.
{ printf 'CALL'; for a in "$@"; do printf '\t%s' "$a"; done; printf '\n'; } >> "$ORCA_STUB_LOG"
[ -n "${ORCA_STUB_SLEEP:-}" ] && sleep "$ORCA_STUB_SLEEP"
case "${1:-} ${2:-}" in
  "worktree ps") cat "$ORCA_STUB_PS";;
  *) printf '{"ok":true,"result":{}}\n';;
esac
"""


def ps_json(worktrees):
    """Build the JSON `orca worktree ps --json` prints.

    Each item: {"path": str, "agents": [state, ...], "activity_min": int,
                "is_main": bool}

    lastActivityAt is the third signal: it moves only when the agent really
    does something. lastOutputAt is always fresh here on purpose, because a
    Claude Code pane redraws its screen every few seconds even when nobody is
    working. Real Orca behaves the same way, so a monitor that reads
    lastOutputAt never sees a quiet pane.
    """
    now_ms = int(time.time() * 1000)
    rows = []
    for item in worktrees:
        states = item.get("agents", [])
        rows.append(
            {
                "path": item["path"],
                "isMainWorktree": bool(item.get("is_main", False)),
                "displayName": item.get("module", os.path.basename(item["path"])),
                "lastActivityAt": now_ms - int(item.get("activity_min", 0)) * 60000,
                "lastOutputAt": now_ms,
                "liveTerminalCount": item.get("terminals", len(states)),
                "status": states[0] if states else "none",
                "agents": [
                    {"paneKey": "pane-%d" % i, "state": s, "agentType": "claude"}
                    for i, s in enumerate(states)
                ],
            }
        )
    return {"ok": True, "result": {"worktrees": rows}}


class ScriptRepo:
    """A throwaway plugin copy plus a throwaway project git repo."""

    def __init__(self, init_project=True):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="auto_pipeline_"))
        self.plugin = os.path.join(self.base, "plugin")
        self.plugin_bin = os.path.join(self.plugin, "bin")
        self.dir = os.path.join(self.base, "project")
        self.cwd = self.dir

        self.bin = os.path.join(self.dir, "stubbin")
        self.orca_log = os.path.join(self.base, "orca_calls.log")
        self.orca_ps = os.path.join(self.base, "orca_ps.json")

        os.makedirs(self.plugin_bin)
        os.makedirs(self.dir)
        os.mkdir(self.bin)

        stub = os.path.join(self.bin, "orca")
        with open(stub, "w") as fh:
            fh.write(ORCA_STUB)
        os.chmod(stub, 0o755)

        for name in COPY_BIN:
            src = os.path.join(BIN, name)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(self.plugin_bin, name))
        for name in COPY_PLUGIN:
            src = os.path.join(ROOT, name)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(self.plugin, name))

        if init_project:
            self.seed_project()

    # ---- fixture building ----

    def seed_project(self):
        """Give the project the per-project files a running pipeline has."""
        src = os.path.join(ROOT, "agent.conf")
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(self.dir, "agent.conf"))
        for name in PROJECT_TXT:
            open(os.path.join(self.dir, name), "w").close()
        open(self.orca_log, "w").close()
        self.set_panes([])
        self.git_init(self.dir)

    def git_init(self, path, commit_min_ago=0):
        subprocess.run(["git", "init", "-q", path], check=True,
                       capture_output=True)
        for key, value in (("user.email", "t@t.t"), ("user.name", "t")):
            subprocess.run(["git", "-C", path, "config", key, value], check=True,
                           capture_output=True)
        self.commit(path, commit_min_ago)

    def commit(self, path, minutes_ago=0):
        """Add one commit dated `minutes_ago` minutes in the past."""
        with open(os.path.join(path, "seed.txt"), "a") as fh:
            fh.write("x\n")
        when = time.strftime("%Y-%m-%dT%H:%M:%S",
                             time.localtime(time.time() - minutes_ago * 60))
        env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
        subprocess.run(["git", "-C", path, "add", "-A"], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", path, "commit", "-q", "-m", "seed"],
                       check=True, capture_output=True, env=env)

    def make_worktree(self, module, commit_min_ago=0, as_repo=True):
        """Create a directory that stands in for a live worktree."""
        path = os.path.join(self.base, "wt_" + module)
        os.mkdir(path)
        if as_repo:
            self.git_init(path, commit_min_ago)
        return path

    def make_project(self, name="other"):
        """A second, empty project directory. Not a git repo yet."""
        path = os.path.join(self.base, name)
        os.mkdir(path)
        return path

    def set_worktree_lines(self, lines):
        """lines: list of (path, module, status)."""
        text = "".join(
            "%s | %s | %s | since 2026-09-21 10:00\n" % row for row in lines
        )
        with open(os.path.join(self.dir, "agent_worktree.txt"), "w") as fh:
            fh.write(text)

    def set_panes(self, worktrees):
        with open(self.orca_ps, "w") as fh:
            json.dump(ps_json(worktrees), fh)

    def set_conf(self, key, value, path=None):
        """Write one key straight into the project's agent.conf."""
        path = path or os.path.join(self.dir, "agent.conf")
        rows, found = [], False
        with open(path) as fh:
            for line in fh:
                if line.split("=", 1)[0].strip() == key:
                    rows.append("%s=%s\n" % (key, value))
                    found = True
                else:
                    rows.append(line)
        if not found:
            rows.append("%s=%s\n" % (key, value))
        with open(path, "w") as fh:
            fh.writelines(rows)

    def write_bin_script(self, name, body):
        """Drop a throwaway script next to the plugin's own scripts."""
        full = os.path.join(self.plugin_bin, name)
        with open(full, "w") as fh:
            fh.write(body)
        os.chmod(full, 0o755)
        return full

    def path(self, *parts):
        """A path inside the PROJECT."""
        return os.path.join(self.dir, *parts)

    def plugin_path(self, *parts):
        """A path inside the PLUGIN."""
        return os.path.join(self.plugin, *parts)

    def detach_scripts_to_worktree(self):
        """Run from a git worktree of the project instead of its main repo.

        The scripts are never in the project at all, so the only thing left to
        prove is that a script started from a worktree still writes the shared
        files into the project's main repo.
        """
        subprocess.run(["git", "-C", self.dir, "add", "-A"], check=True,
                       capture_output=True)
        dirty = subprocess.run(["git", "-C", self.dir, "status", "--porcelain"],
                               check=True, capture_output=True, text=True).stdout
        if dirty.strip():
            subprocess.run(["git", "-C", self.dir, "commit", "-q", "-m", "seed2"],
                           check=True, capture_output=True)
        worktree = self.dir + "_wt"
        subprocess.run(["git", "-C", self.dir, "worktree", "add", "-q",
                        "-b", "feature", worktree], check=True, capture_output=True)
        self.cwd = os.path.realpath(worktree)
        return self.cwd

    def stub_orca_down(self):
        """Make the stub fail the way orca does when the app is not running."""
        with open(os.path.join(self.bin, "orca"), "w") as fh:
            fh.write("#!/usr/bin/env bash\n"
                     "{ printf 'CALL'; for a in \"$@\"; do printf '\\t%s' \"$a\"; done; "
                     "printf '\\n'; } >> \"$ORCA_STUB_LOG\"\n"
                     "echo 'orca: daemon not running' >&2\n"
                     "exit 1\n")
        os.chmod(os.path.join(self.bin, "orca"), 0o755)

    def stub_orca_reads_stdin(self):
        """A stub that drains stdin, the way a real command can."""
        with open(os.path.join(self.bin, "orca"), "w") as fh:
            fh.write("#!/usr/bin/env bash\n"
                     "{ printf 'CALL'; for a in \"$@\"; do printf '\\t%s' \"$a\"; done; "
                     "printf '\\n'; } >> \"$ORCA_STUB_LOG\"\n"
                     "case \"${1:-} ${2:-}\" in\n"
                     "  \"worktree ps\") cat \"$ORCA_STUB_PS\";;\n"
                     "  *) cat >/dev/null 2>&1 || true; "
                     "printf '{\"ok\":true,\"result\":{}}\\n';;\n"
                     "esac\n")
        os.chmod(os.path.join(self.bin, "orca"), 0o755)

    def read(self, name):
        full = self.path(name)
        if not os.path.exists(full):
            return None
        with open(full) as fh:
            return fh.read()

    # ---- running ----

    def script_path(self, script):
        """Absolute path of a script: the plugin's bin/ first, else the project."""
        in_bin = os.path.join(self.plugin_bin, script)
        if os.path.exists(in_bin):
            return in_bin
        return os.path.join(self.dir, script)

    def _env(self, extra):
        env = dict(os.environ)
        env["PATH"] = self.bin + os.pathsep + env["PATH"]
        env["ORCA_STUB_LOG"] = self.orca_log
        env["ORCA_STUB_PS"] = self.orca_ps
        env.pop("ORCA_STUB_SLEEP", None)
        env.pop("AGENT_ROLE", None)
        env.pop("CLAUDE_PROJECT_DIR", None)
        env.setdefault("AGENT_FAKE_RAM", "10")
        env.setdefault("AGENT_FAKE_CPU", "10")
        env.update(extra or {})
        return env

    def run(self, script, *args, **kwargs):
        env = self._env(kwargs.pop("env", None))
        stdin = kwargs.pop("stdin", None)
        return subprocess.run(
            [self.script_path(script)] + list(args),
            cwd=kwargs.pop("cwd", None) or self.cwd,
            env=env, capture_output=True, text=True,
            input=stdin if stdin is not None else "",
            timeout=kwargs.pop("timeout", 90),
        )

    def popen(self, script, *args, **kwargs):
        env = self._env(kwargs.pop("env", None))
        return subprocess.Popen(
            [self.script_path(script)] + list(args),
            cwd=kwargs.pop("cwd", None) or self.cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

    # ---- what the stub saw ----

    def calls(self):
        with open(self.orca_log) as fh:
            rows = [line.rstrip("\n").split("\t") for line in fh if line.strip()]
        return [row[1:] for row in rows if row and row[0] == "CALL"]

    def create_calls(self):
        return [c for c in self.calls() if c[:2] == ["terminal", "create"]]

    def clear_calls(self):
        open(self.orca_log, "w").close()

    # ---- teardown ----

    def kill_monitor(self):
        for gitdir in (self.path(".git"),):
            pid_file = os.path.join(gitdir, "agent_monitor.pid")
            if not os.path.exists(pid_file):
                continue
            try:
                with open(pid_file) as fh:
                    pid = int(fh.read().split()[0])
                os.kill(pid, signal.SIGTERM)
            except (ValueError, IndexError, OSError):
                pass
            try:
                os.remove(pid_file)
            except OSError:
                pass

    def cleanup(self):
        self.kill_monitor()
        shutil.rmtree(self.base, ignore_errors=True)


class ScriptCase(unittest.TestCase):
    """Base case: one fresh plugin copy and one fresh project per test."""

    script = None

    def setUp(self):
        if self.script and not os.path.exists(os.path.join(BIN, self.script)):
            self.fail("bin/%s does not exist yet. Write it." % self.script)
        self.repo = ScriptRepo()
        self.addCleanup(self.repo.cleanup)

    def assertOk(self, result):
        self.assertEqual(
            result.returncode, 0,
            "exit %d\nSTDOUT:\n%s\nSTDERR:\n%s"
            % (result.returncode, result.stdout, result.stderr),
        )
        return result.stdout

    def lines(self, text):
        return [line.rstrip() for line in text.splitlines()]
