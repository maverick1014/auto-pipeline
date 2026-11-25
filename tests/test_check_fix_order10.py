"""Failing tests for check-blocks section 51: FIX ORDER 10 of the main manager (TELL 11cc1b2b), H1-H9.
Written by the task manager before any fix. (H2's own tests live in tests/test_check_fix_order9.py and
tests/test_check_fix_order6.py, where the word-list tests were turned into exact-sentence tests.)

Run: python3 -m unittest tests.test_check_fix_order10
"""

import json
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import test_agent_autoclear as ac  # noqa: E402
import test_check_fix_order2 as fo2  # noqa: E402
import test_check_fix_order6 as fo6  # noqa: E402

only_own = fo2.only_own
wait_until = fo2.wait_until


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def rule(start, end):
    text = read("PRINCIPLES.md")
    return text[text.index(start):text.index(end)]


# ====================================================================== H1 the sign and the data checks at the head


@only_own
class TestH1AtTheHead(fo6.Gate):
    def test_an_owner_sign_on_an_earlier_commit_is_refused(self):
        self.ok("todo", "checks", "t", "OWNER SIGN")
        self.all_pass_but()
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes merge it")   # signs c1
        self.commit_push({"app.js": "z()\n"})                                       # c2 changes more
        self.all_pass_but()
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue([l for l in r.stdout.splitlines() if l.startswith("OWNER SIGN: pass at ")], r.stdout)

    def test_a_db_check_on_an_earlier_commit_is_refused(self):
        self.ok("todo", "checks", "t", "DB CHECK")
        self.all_pass_but()
        self.ok("check", "t", "DB CHECK", "pass", "--by", "t Check", "--evidence", "migration ran")
        self.commit_push({"app.js": "z()\n"})
        self.all_pass_but()
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue([l for l in r.stdout.splitlines() if l.startswith("DB CHECK: pass at ")], r.stdout)

    def test_the_documented_sign_command_passes_the_head(self):
        line = [l for l in read("skills", "dispatch", "SKILL.md").splitlines()
                if "OWNER SIGN" in l and "agent-file.sh check" in l][0]
        self.assertIn("--commit <head>", line)


# ====================================================================== H2 texts


class TestH2Texts(unittest.TestCase):
    def test_dispatch_shows_the_sentence(self):
        d = read("skills", "dispatch", "SKILL.md")
        self.assertIn('yes, publish <task> to production', d)
        self.assertIn("yes, skip <BLOCK> for <task>", read("PRINCIPLES.md") + d)

    def test_the_open_design_section(self):
        req = read("requirements", "check-blocks.md")
        self.assertIn("## 52. Approval design, open for the owner", req)


# ====================================================================== H3-H5 texts


class TestH3ToH5(unittest.TestCase):
    def test_h3_the_fixer_is_a_normal_task(self):
        m = read("skills", "merge", "SKILL.md")
        line = [l for l in m.splitlines() if "fixer" in l][0]
        for phrase in ("todo add", "target", "base", "PR REVIEW", "gate", "agent-nightly.sh --start"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, line)

    def test_h4_where_the_app_runs(self):
        self.assertIn("where the app runs:", read("skills", "merge", "SKILL.md"))

    def test_h5_the_local_branch_before_minus_d(self):
        self.assertIn("git merge-base --is-ancestor <branch> origin/<production branch>", read("agents", "merge-deputy.md"))


# ====================================================================== H6 a cap on the rounds


class TestH6Cap(ac.ClearCase):
    script = "agent-autoclear.sh"

    def test_a_pane_that_never_settles_gets_a_line(self):
        self.repo.stub_tool("sleep", '#!/bin/bash\n[ "$1" = 30 ] && exec /bin/sleep 1\nexec /bin/sleep "$@"\n')
        self.write_state(["ROLE: x", ""])
        self.stub_file("wait_sleep", "3")                     # every turn takes 3 s: the pane never settles
        proc = self.repo.popen("agent-autoclear.sh", ac.HANDLE, "s1", "--spawned", env={"AGENT_FAKE_NOW": ac.NOW})
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        line = "AUTO CLEAR waiting: the pane did not settle in 3 rounds; trying again later"
        self.assertTrue(wait_until(lambda: any(l.startswith(line) for l in self.state_lines()), 40),
                        self.state_lines())
        proc.terminate()


# ====================================================================== H7-H9 the room


class TestH7ToH9(fo2.Room):
    def test_h7_never_below_550(self):
        with open(os.path.join(self.gitdir(), "agent_test_weights.json"), "w") as fh:
            json.dump({"pane_recent": [1, 1, 1, 1]}, fh)
        p = self.sleeper()
        self.room("measure-pane", str(p.pid))
        with open(os.path.join(self.gitdir(), "agent_test_weights.json")) as fh:
            self.assertEqual(json.load(fh)["pane"], "0 s 550 MB")

    def test_h8_a_pending_key_that_exists_is_refused(self):
        self.assertEqual(self.room("reserve-pane", "--pending", "task-a", "550").returncode, 0)
        r = self.room("reserve-pane", "--pending", "task-a", "550")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(self.room("list").stdout.count("task-a"), 1)
        self.assertIn("reserve-pane --pending <task name>", read("skills", "dispatch", "SKILL.md"))

    def test_h9_the_usage(self):
        head = read("bin", "agent-room.sh").split("\nexec ")[0]          # the usage comment of the script
        for phrase in ("reserve-pane --pending", "reserve-pane --name", "release-pane"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, head)
        r = self.repo.run("agent-room.sh", "frobnicate", env=self.env())   # a wrong command prints this script's usage
        out = r.stdout + r.stderr
        self.assertIn("agent-room.sh", out)
        self.assertNotIn("agent-nightly.sh --start", out)
        self.assertIn("reserve-pane --pending", out)


if __name__ == "__main__":
    unittest.main()
