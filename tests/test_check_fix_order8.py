"""Failing tests for check-blocks section 49: FIX ORDER 8 of the main manager (TELL ff975386), A10-A18.
Written by the task manager before any fix.

Run: python3 -m unittest tests.test_check_fix_order8
"""

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import test_check_promote as tp  # noqa: E402
import test_check_results as tcr  # noqa: E402


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


MERGE = ("skills", "merge", "SKILL.md")
DEPUTY = ("agents", "merge-deputy.md")


class TestA10FastLaneProduction(tp.PromoteCase):
    """A fast-lane deputy works in an Agent worktree that has no agent_worktree.txt line."""

    def test_the_main_managers_gate_brings_the_lines_promote_needs(self):
        self.git("fetch", "-q", "origin")
        wt = os.path.join(self.repo.base, "agent_wt")
        self.git("worktree", "add", "-q", "-b", "u1", wt, "origin/main")
        with open(os.path.join(wt, "fix.txt"), "w") as fh:
            fh.write("urgent\n")
        subprocess.run(["git", "-C", wt, "add", "-A"], check=True)
        subprocess.run(["git", "-C", wt, "commit", "-q", "-m", "urgent fix"], check=True)
        subprocess.run(["git", "-C", wt, "push", "-q", "-u", "origin", "u1"], check=True, capture_output=True)
        r = self.repo.run("agent-file.sh", "todo", "add", "u1", "small", "urgent fix", "10", "--target", "production",
                          "--owner-quote", "yes, publish u1 to production")   # section 51 H2: the exact sentence
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        head = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        for block in ("DIFF SCAN", "BUILD", "RELATED TESTS", "MODULE TESTS", "GUARD TESTS", "EXAMPLES TEST"):
            self.repo.run("agent-file.sh", "check", "u1", block, "pass", "--by", "u1 Deputy", "--evidence", "ok",
                          "--commit", head, cwd=wt)                     # the deputy's lines, in its worktree
        tcr.main_launched(self.repo.dir, "u1")
        for block in ("PR REVIEW", "CORE REVIEW"):
            self.repo.run("agent-file.sh", "check", "u1", block, "pass", "--by", "u1 Review", "--evidence", "ok",
                          "--commit", head)                              # the reviewer, from the main checkout
        r = self.repo.run("agent-file.sh", "checks", "gate", "u1", "--dir", wt, "--branch", "u1",
                          "--base", "origin/main")                       # /merge step 4
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.repo.run("agent-promote.sh", "--task", "u1", "--branch", "u1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_demo_has_the_third_walk(self):
        self.assertIn("walk 3: an urgent small production task", read("tests", "check_blocks_demo.sh"))


class TestA11ToA18Texts(unittest.TestCase):
    def test_a11_reviewer_and_check_deputy(self):
        rev = read("agents", "reviewer.md")
        self.assertIn("git diff <base>...<head>", rev)
        self.assertIn("no worktree needed", rev)
        self.assertIn("where the app runs", read("agents", "check-deputy.md"))

    def test_a12_three_session_values(self):
        self.assertIn("task manager | helper | fast-lane", read(*MERGE))
        self.assertIn("**a fast-lane subagent**", read(*DEPUTY))

    def test_a14_the_reviewer_model_mapping(self):
        self.assertIn("agent_conf.py cli-model", read(*MERGE))

    def test_a15_dispatch_template(self):
        step2 = [l for l in read("skills", "dispatch", "SKILL.md").splitlines() if l.startswith("2. Small task")][0]
        self.assertIn('--target production --owner-quote "yes, publish <task> to production"', step2)   # section 51 H2: the exact sentence

    def test_a16_no_diff_read(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import agent_checks
        self.assertNotIn("DIFF READ", agent_checks.BUILDER_BLOCKS)

    def test_a17_production_task_branch(self):
        dep = read(*DEPUTY)
        self.assertIn("git merge-base --is-ancestor origin/<branch> origin/<production branch>", dep)

    def test_a18_remote_gate_and_reservation(self):
        m = read(*MERGE)
        step4 = m[m.index("\n4. "):m.index("\n5. ")]
        self.assertIn("git worktree add --detach <scratch> origin/<branch>", step4)
        self.assertIn("goes by itself when its process ends", m + read(*DEPUTY))


if __name__ == "__main__":
    unittest.main()
