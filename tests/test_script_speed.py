"""script-speed (requirements/script-speed.md): agent-start.sh, agent-file.sh (todo verbs, tell) and
agent-resume.sh do the same work with fewer process starts.

Every test COUNTS the processes one call starts (tests/proccount.py), it never times them, so it does
not flake on a busy machine. The way (main manager, 2026-11-27): no port to Python; the cheapest
changes first (each value asked once, plain text work in bash without a pipe, back-to-back python3
calls merged into one), measured after each slice, stopped when the time targets were met. The time
a call in the tests (8 related files, run2 -j 6, pc2, back to back): agent-start.sh 0.934 -> 0.358 s
(target 0.5), agent-file.sh todo 0.247 -> 0.137 s (0.2), agent-resume.sh 0.798 -> 0.373 s (0.4).

The caps are the counts the change reached (2026-11-27, pc2): python3 exact, all starts + 2 (a ps or
sysctl fallback on another machine). A cap is never above today's count. A change that starts more
processes raises the cap here, with its reason.

| Call | python3 before -> cap | all starts before -> reached (cap) |
|---|---|---|
| agent-start.sh, main manager by hand | 27 -> 5 | 157 -> 43 (45) |
| agent-start.sh, main manager from the hook | 28 -> 6 | 157 -> 46 (48) |
| agent-start.sh, task manager | 7 -> 1 | 65 -> 11 (13) |
| agent-start.sh, second session | 11 -> 1 | 142 -> 23 (25) |
| agent-start.sh --quiz | 0 -> 0 | 24 -> 6 (8) |
| agent-start.sh --rules | 0 -> 0 | 28 -> 6 (8) |
| agent-start.sh --answer, pass and fail (shasum 15 -> 0: one hashlib pass) | 0 -> 1 | 115 -> 6 (8) |
| agent-resume.sh, main manager | 9 -> 3 | 48 -> 17 (19) |
| agent-file.sh todo add (with and without --checks) | 2-3 -> 1 | 19-21 -> 8 (10) |
| agent-file.sh todo stage (with and without a slice) | 3 -> 2 | 31 -> 9 (11) |
| agent-file.sh todo done, the cleanup sweep due | 15 -> 6 | 167 -> 45 (47) |
| agent-file.sh todo done, no such line | 0 -> 0 | 12 -> 5 (7) |
| agent-file.sh tell, local, reads back | 2 -> 1 | 21 -> 10 = 5 + 5 orca (7 + its orca calls) |

Every call: no git command line twice ("git asked once per value"; before: up to 6 repeats a call).

The tell read-back (rule 3): today it waits up to 20 x 0.5 s for the block's hash line. Tests shorten
it only with AGENT_TELL_READBACK_S (seconds, default 10); real use never sets it.
"""

import json
import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scripthelp import ScriptCase  # noqa: E402
import proccount as pc  # noqa: E402
from watchhelp import ENV, AllCase, sha8  # noqa: E402

NOBODY = "999999"   # a CLAUDE_PID no lock names and no process has
TASK = {"AGENT_ROLE": "task-manager"}
TASK_ANSWERS = "1A 2D 5D 7C 8D 10C 13B 15D 20B 21B 23B 26C 27B 33B 36B"
SIG = "[Opus 5.5 xhigh]"
NOW = "2026-11-02 14:00"


class Counts:
    """Mixin: count_starts on the repo, then counted() runs one call and returns (result, starts).

    The machine is quiet: a pgrep stub finds no other agent process. Without it the cleanup sweep's
    leftover check (agent-resources.sh stop-leftovers) runs a second pgrep and an lsof, awk and ps
    for every watch some other test left running, so the count would follow the machine, not the
    call. The stub is still counted; the leftover logic has its own tests (test_agent_resources,
    test_agent_cleanup)."""

    def count_on(self):
        self.repo.stub_tool("pgrep", "#!/bin/bash\nexit 1\n")
        self.log = pc.count_starts(self.repo)

    def counted(self, script, *args, **kwargs):
        pc.reset_starts(self.log)
        result = self.repo.run(script, *args, **kwargs)
        return result, pc.read_starts(self.log)

    def assertStarts(self, starts, total, python3=1, hashes=None):
        text = pc.summary(starts)
        self.assertLessEqual(len(pc.names(starts, "python3")), python3,
                             "more python3 starts than %d\n%s" % (python3, text))
        self.assertEqual(pc.repeated(starts, "git"), [], "git asked twice for one value\n" + text)
        if hashes is not None:
            n = len(pc.names(starts, "shasum")) + len(pc.names(starts, "sha256sum"))
            self.assertLessEqual(n, hashes, "more hash starts than %d\n%s" % (hashes, text))
        self.assertLessEqual(len(starts), total, "more process starts than %d\n%s" % (total, text))


class CountCase(Counts, ScriptCase):
    def setUp(self):
        super().setUp()
        self.count_on()


class TestStartCounts(CountCase):
    script = "agent-start.sh"

    def hook(self, source="startup"):
        return json.dumps({"session_id": "sid-speed", "transcript_path": "/tmp/x.jsonl", "cwd": self.repo.cwd,
                           "hook_event_name": "SessionStart", "source": source})

    def test_main_manager_by_hand(self):
        r, starts = self.counted("agent-start.sh", env={"CLAUDE_PID": NOBODY})
        self.assertOk(r)
        self.assertIn("ROLE: main manager", r.stdout)
        self.assertStarts(starts, 45, python3=5)

    def test_main_manager_from_the_hook(self):
        r, starts = self.counted("agent-start.sh", env={"CLAUDE_PID": NOBODY}, stdin=self.hook())
        self.assertOk(r)
        self.assertIn("ROLE: main manager", r.stdout)
        self.assertStarts(starts, 48, python3=6)

    def test_task_manager(self):
        r, starts = self.counted("agent-start.sh", env=TASK)
        self.assertOk(r)
        self.assertIn("ROLE: task-manager", r.stdout)
        self.assertStarts(starts, 13, python3=1)

    def test_second_session(self):
        live = subprocess.Popen(["sleep", "120"])
        self.addCleanup(live.wait)
        self.addCleanup(live.kill)
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-11-27 08:00 sid-other -\n" % live.pid)
        r, starts = self.counted("agent-start.sh", env={"CLAUDE_PID": NOBODY})
        self.assertOk(r)
        self.assertIn("ROLE: task manager, human-direct", r.stdout)
        self.assertStarts(starts, 25, python3=1)

    def test_quiz(self):
        r, starts = self.counted("agent-start.sh", "--quiz", env=TASK)
        self.assertOk(r)
        self.assertIn("=== QUIZ (task manager) — answer all 15 before any work ===", r.stdout)
        self.assertStarts(starts, 8, python3=0)

    def test_rules(self):
        r, starts = self.counted("agent-start.sh", "--rules", env=TASK)
        self.assertOk(r)
        self.assertIn("# PRINCIPLES", r.stdout)
        self.assertStarts(starts, 8, python3=0)

    def test_answer_all_right_is_one_hash_pass(self):
        r, starts = self.counted("agent-start.sh", "--answer", TASK_ANSWERS, env=TASK)
        self.assertOk(r)
        self.assertEqual(r.stdout, "QUIZ RESULT: 15/15 PASS\nYou may start work.\n")
        self.assertStarts(starts, 8, python3=1, hashes=0)

    def test_answer_one_wrong_is_one_hash_pass_and_todays_text(self):
        r, starts = self.counted("agent-start.sh", "--answer", "1B" + TASK_ANSWERS[2:], env=TASK)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "QUIZ RESULT: 14/15 FAIL\nQ1: re-read PRINCIPLES.md\n"
                                   "Re-read those files, then answer again.\n")
        self.assertStarts(starts, 8, python3=1, hashes=0)


class TestResumeCounts(CountCase):
    script = "agent-resume.sh"

    def test_main_manager(self):
        r, starts = self.counted("agent-resume.sh", env={"CLAUDE_PID": NOBODY})
        self.assertOk(r)
        self.assertStarts(starts, 19, python3=3)


class TestTodoCounts(CountCase):
    script = "agent-file.sh"

    def test_add(self):
        r, starts = self.counted("agent-file.sh", "todo", "add", "x", "small", "do a thing", "10")
        self.assertOk(r)
        self.assertIn("x | small | do a thing", self.repo.read("agent_todo.txt"))
        self.assertStarts(starts, 10)

    def test_add_with_checks(self):
        r, starts = self.counted("agent-file.sh", "todo", "add", "y", "big", "do b", "60",
                                 "--checks", "UI CHECK,PR REVIEW")
        self.assertOk(r)
        self.assertIn("checks PR REVIEW, UI CHECK", self.repo.read("agent_todo.txt"))
        self.assertStarts(starts, 10)

    def test_stage(self):
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add", "x", "small", "do a thing", "10"))
        r, starts = self.counted("agent-file.sh", "todo", "stage", "x", "tests")
        self.assertOk(r)
        self.assertStarts(starts, 11, python3=2)

    def test_stage_with_a_slice(self):
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add", "x", "small", "do a thing", "10"))
        r, starts = self.counted("agent-file.sh", "todo", "stage", "x", "workers", "1/2")
        self.assertOk(r)
        self.assertStarts(starts, 11, python3=2)

    def test_done_with_the_cleanup_sweep_due(self):
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add", "x", "small", "do a thing", "10"))
        r, starts = self.counted("agent-file.sh", "todo", "done", "x")
        self.assertOk(r)
        self.assertIn("todo done: x", r.stdout)
        self.assertIn(" | x | ", self.repo.read("agent_completed.txt"))
        self.assertStarts(starts, 47, python3=6)

    def test_done_no_such_line(self):
        r, starts = self.counted("agent-file.sh", "todo", "done", "nope")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("no todo line named: nope", r.stdout + r.stderr)
        self.assertStarts(starts, 7, python3=0)


class TellCountCase(Counts, AllCase):
    def setUp(self):
        super().setUp()
        self.t = self.task("alpha", echo=True, git=True)
        self.count_on()

    def tell(self, task, msg, env=None):
        run_env = {"AGENT_RUNTIME": "orca", "AGENT_FAKE_NOW": NOW, "AGENT_TELL_ECHO_S": "1"}
        run_env.update(env or {})
        return self.counted("agent-file.sh", "tell", task, msg, env=run_env, timeout=90, cwd=self.repo.dir)

    def sends_to(self, handle):
        return [c for c in self.terminal_calls("send") if self.opt(c, "--terminal") == handle]

    def reads_of(self, handle):
        return [c for c in self.terminal_calls("read") if self.opt(c, "--terminal") == handle]


class TestTellCounts(TellCountCase):
    def test_local_tell_is_one_python3(self):
        r, starts = self.tell("alpha", SIG + " hello")
        self.assertOk(r)
        self.assertIn("TELL OK alpha %s" % sha8(SIG + " hello"), r.stdout)
        # the orca calls are the pane's own (read, wait, send, read back); the rest is the script
        orca = len(pc.names(starts, "orca"))
        self.assertStarts(starts, 7 + orca)


class TestTellReadBack(TellCountCase):
    """Rule 3: a block that reads back returns at once; one that never does fails with today's line
    after today's wait. Tests shorten the wait only with AGENT_TELL_READBACK_S."""

    def test_remote_block_that_reads_back_at_once_is_one_read(self):
        rem = self.task("rem", env=ENV, echo=True)
        r, _ = self.tell("rem", SIG + " hello")
        self.assertOk(r)
        self.assertIn("TELL OK rem %s" % sha8(SIG + " hello"), r.stdout)
        # one read for the cursor before the hash line, one read that finds it: no wait loop
        self.assertLessEqual(len(self.reads_of(rem["shell"])), 2, self.reads_of(rem["shell"]))

    def test_remote_block_that_never_reads_back_uses_the_setting(self):
        rem = self.task("rem", env=ENV, echo=True)
        os.remove(rem["state"])
        os.symlink("/dev/null", rem["state"])
        s = sha8(SIG + " hello")
        r, _ = self.tell("rem", SIG + " hello", env={"AGENT_TELL_READBACK_S": "1"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("TELL FAIL rem %s: file check" % s, r.stdout + r.stderr)
        self.assertEqual(self.sends_to(rem["pane"]), [])
        # two tries of the write, each: one cursor read, then 1 s of reads at 0.5 s = 2
        self.assertEqual(len(self.reads_of(rem["shell"])), 2 * (1 + 2), self.reads_of(rem["shell"]))

    def test_the_default_wait_is_todays_20_reads_half_a_second_apart(self):
        rem = self.task("rem", env=ENV, echo=True)
        os.remove(rem["state"])
        os.symlink("/dev/null", rem["state"])
        s = sha8(SIG + " hello")
        env = {"AGENT_RUNTIME": "orca", "AGENT_FAKE_NOW": NOW, "AGENT_TELL_ECHO_S": "1"}
        with mock.patch("time.sleep") as slept:
            r = self.repo.run_py("agent_watch", "tell", self.repo.dir, NOW, "rem", SIG + " hello", env=env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("TELL FAIL rem %s: file check" % s, r.stdout + r.stderr)
        waits = [c.args[0] for c in slept.call_args_list if c.args and c.args[0] == 0.5]
        self.assertEqual(len(waits), 2 * 20, slept.call_args_list)
        self.assertEqual(len(self.reads_of(rem["shell"])), 2 * (1 + 20), self.reads_of(rem["shell"]))


if __name__ == "__main__":
    unittest.main()
