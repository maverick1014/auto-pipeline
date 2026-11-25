"""Failing tests for check-blocks section 35 (TELL 74d06893): two board bugs the owner saw.
Written by the task manager before any code.

Run: python3 -m unittest tests.test_check_board
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from scripthelp import BIN, ScriptCase  # noqa: E402
import test_agent_board as tb  # noqa: E402
import test_watch_tell as tw  # noqa: E402
from watchhelp import sha8  # noqa: E402


class TestNewestValidLine(unittest.TestCase):
    """C50: a malformed newest heartbeat must not hide the valid STAGE line before it."""

    def run_remote(self, lines):
        sys.path.insert(0, BIN)
        import agent_watch
        d = tempfile.mkdtemp(prefix="cb_remote_")
        self.addCleanup(subprocess.run, ["rm", "-rf", d])
        with open(os.path.join(d, "agent_state.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))
        out = subprocess.run(["bash", "-c", agent_watch.remote_command(d)], capture_output=True, text=True).stdout
        m = re.search(r"FSIG \S* \S+ \S* [01] (.*)\|", out)
        self.assertTrue(m, out)
        return m.group(1)

    def test_a_malformed_heartbeat_is_skipped(self):
        got = self.run_remote(["STAGE test-slim: workers | since 2026-11-25 12:00",
                               "HEARTBEAT step 4. building the slim pack"])
        self.assertTrue(got.startswith("STAGE test-slim: workers"), got)

    def test_a_valid_heartbeat_wins_when_newest(self):
        got = self.run_remote(["STAGE test-slim: tests | since 2026-11-25 12:00",
                               "HEARTBEAT test-slim: step 4 of 7, work 40m, workers 1 of 2 | 2026-11-25 13:00"])
        self.assertTrue(got.startswith("HEARTBEAT test-slim: step 4 of 7"), got)


class TestHeartbeatCommand(ScriptCase):
    """C51: the task manager writes its heartbeat with one command, so the form cannot be typed wrong."""
    script = "agent-file.sh"

    def state(self):
        p = os.path.join(self.repo.dir, "agent_state.txt")
        return open(p).read() if os.path.exists(p) else ""

    def test_the_line(self):
        r = self.repo.run("agent-file.sh", "heartbeat", "test-slim", "4", "35", "workers 2 of 3 running")
        self.assertEqual(r.returncode, 0, r.stderr)
        last = self.state().strip().splitlines()[-1]
        self.assertRegex(last, r"^HEARTBEAT test-slim: step 4 of 7, work 35m, workers 2 of 3 running \| "
                               r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_refusals(self):
        for args in (("t", "8", "35", "x"), ("t", "4", "ten", "x"), ("t", "4", "35", ""), ("t", "4")):
            with self.subTest(args=args):
                before = self.state()
                r = self.repo.run("agent-file.sh", "heartbeat", *args)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertEqual(self.state(), before)

    def test_the_brief_names_it(self):
        with open(os.path.join(os.path.dirname(HERE), "skills", "dispatch", "SKILL.md")) as fh:
            brief = fh.read()
        line = [l for l in brief.splitlines() if l.startswith("HEARTBEAT:")][0]
        self.assertIn("agent-file.sh heartbeat", line)


class TestAddedWork(tb.BoardCase):
    """C52: added work raises the estimate; the bar never falls back to 0."""
    lang = "en"

    def test_plus_minutes(self):
        self.add("t", "a running task", est=60, opened="2026-11-02 13:00")
        self.af("todo", "stage", "t", "workers", now="2026-11-02 14:00")
        before = self.row(self.rows(), task="t")["Progress"]
        r = self.af("todo", "est", "t", "+120", now="2026-11-02 14:30")
        self.assertIn("todo est: t 60m -> 180m", r.stdout)
        line = [l for l in self.repo.read("agent_todo.txt").splitlines() if l.startswith("t | ")][0]
        self.assertIn("est 180m", line)
        self.assertIn("stage workers", line)
        after = self.row(self.rows(), task="t")["Progress"]
        pct = int(re.search(r"(\d+)%", after).group(1))
        self.assertGreater(pct, 0, (before, after))
        self.assertGreaterEqual(pct, int(re.search(r"(\d+)%", before).group(1)) // 2)


class TestTellReminder(tw.TellCase):
    """C53: the tell text reminds the main manager to add minutes when the message adds work."""

    def test_the_line_before_tell_ok(self):
        msg = tw.SIG + " one more section for you"
        r = self.tell("alpha", msg)
        self.assertOk(r)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(lines[-1], "TELL OK alpha %s" % sha8(msg))
        self.assertEqual(lines[-2], 'if this message adds work: agent-file.sh todo est "alpha" +<minutes>')
