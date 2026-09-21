"""Helpers to run this repo's shell scripts against a throwaway git repo.

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

# Copied into the temp repo when they exist. A script still being written by
# another worker is simply skipped, so unrelated tests keep running.
COPY = [
    "agent-start.sh",
    "agent-file.sh",
    "agent-settings.sh",
    "agent-resume.sh",
    "agent-monitor.sh",
    "agent-resources.sh",
    "agent_conf.py",
    "agent.conf",
    "PRINCIPLES.md",
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

    Each item: {"path": str, "agents": [state, ...], "output_min": int,
                "is_main": bool}
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
                "lastOutputAt": now_ms - int(item.get("output_min", 0)) * 60000,
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
    """A throwaway git repo holding copies of the repo's scripts."""

    def __init__(self):
        self.dir = os.path.realpath(tempfile.mkdtemp(prefix="auto_pipeline_"))
        self.script_dir = self.dir
        self.bin = os.path.join(self.dir, "stubbin")
        self.orca_log = os.path.join(self.dir, "orca_calls.log")
        self.orca_ps = os.path.join(self.dir, "orca_ps.json")

        os.mkdir(self.bin)
        stub = os.path.join(self.bin, "orca")
        with open(stub, "w") as fh:
            fh.write(ORCA_STUB)
        os.chmod(stub, 0o755)

        for name in COPY:
            src = os.path.join(ROOT, name)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(self.dir, name))

        for name in ("agent_todo.txt", "agent_completed.txt", "agent_ideas.txt",
                     "agent_worktree.txt"):
            open(os.path.join(self.dir, name), "w").close()

        open(self.orca_log, "w").close()
        self.set_panes([])
        self.git_init(self.dir)

    # ---- fixture building ----

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
        path = os.path.join(self.dir, "wt_" + module)
        os.mkdir(path)
        if as_repo:
            self.git_init(path, commit_min_ago)
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

    def set_conf(self, key, value):
        """Write one key straight into the agent.conf the scripts read."""
        path = os.path.join(self.script_dir, "agent.conf")
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

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def detach_scripts_to_worktree(self):
        """Put the scripts in a real git worktree and leave the main repo without them.

        After this, ROOT (the main repo) and the script's own directory are two
        different places, which is how the real repo is laid out.
        """
        subprocess.run(["git", "-C", self.dir, "add", "-A"], check=True,
                       capture_output=True)
        dirty = subprocess.run(["git", "-C", self.dir, "status", "--porcelain"],
                               check=True, capture_output=True, text=True).stdout
        if dirty.strip():
            subprocess.run(["git", "-C", self.dir, "commit", "-q", "-m", "scripts"],
                           check=True, capture_output=True)
        worktree = self.dir + "_wt"
        subprocess.run(["git", "-C", self.dir, "worktree", "add", "-q",
                        "-b", "feature", worktree], check=True, capture_output=True)
        for name in COPY:
            gone = os.path.join(self.dir, name)
            if os.path.exists(gone) and name != "agent.conf":
                os.remove(gone)
        self.script_dir = os.path.realpath(worktree)
        return self.script_dir

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

    def run(self, script, *args, **kwargs):
        env = dict(os.environ)
        env["PATH"] = self.bin + os.pathsep + env["PATH"]
        env["ORCA_STUB_LOG"] = self.orca_log
        env["ORCA_STUB_PS"] = self.orca_ps
        env.pop("ORCA_STUB_SLEEP", None)
        env.pop("AGENT_ROLE", None)
        env.setdefault("AGENT_FAKE_RAM", "10")
        env.setdefault("AGENT_FAKE_CPU", "10")
        env.update(kwargs.pop("env", {}) or {})
        return subprocess.run(
            [os.path.join(self.script_dir, script)] + list(args),
            cwd=kwargs.pop("cwd", None) or self.script_dir,
            env=env, capture_output=True, text=True,
            timeout=kwargs.pop("timeout", 90),
        )

    def popen(self, script, *args, **kwargs):
        env = dict(os.environ)
        env["PATH"] = self.bin + os.pathsep + env["PATH"]
        env["ORCA_STUB_LOG"] = self.orca_log
        env["ORCA_STUB_PS"] = self.orca_ps
        env.pop("AGENT_ROLE", None)
        env.setdefault("AGENT_FAKE_RAM", "10")
        env.setdefault("AGENT_FAKE_CPU", "10")
        env.update(kwargs.pop("env", {}) or {})
        return subprocess.Popen(
            [os.path.join(self.script_dir, script)] + list(args),
            cwd=self.script_dir, env=env,
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
        shutil.rmtree(self.dir, ignore_errors=True)


class ScriptCase(unittest.TestCase):
    """Base case: one fresh temp repo per test."""

    script = None

    def setUp(self):
        if self.script and not os.path.exists(os.path.join(ROOT, self.script)):
            self.fail("%s does not exist yet. Write it." % self.script)
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
