"""Failing tests for check-blocks section 45: FIX ORDER 4 of the main manager (TELL fe33c244), A1-A9.
Written by the task manager before any fix.

Run: python3 -m unittest tests.test_check_fix_order4
"""

import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import test_check_results as tcr  # noqa: E402


def only_own(cls):
    own = set(vars(cls))
    for name in dir(cls):
        if name.startswith("test") and name not in own:
            setattr(cls, name, None)
    return cls


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def rule(start, end):
    text = read("PRINCIPLES.md")
    return text[text.index(start):text.index(end)]


# ====================================================================== A1 a line written from another checkout


@only_own
class TestA1AnotherCheckout(tcr.TestGate):
    """The reviewer's shell sits in the main checkout (the working branch); the task is in its own worktree."""

    def setUp(self):
        super().setUp()
        self.wt = os.path.join(self.repo.base, "task_wt")
        self.git("worktree", "add", "-q", "-b", "feat2", self.wt, "feat")
        self.commit_push({"app.js": "w()\n"}, cwd=self.wt)
        self.head = self.git("rev-parse", "HEAD", cwd=self.wt).strip()
        self.git("checkout", "-q", "base")                       # the main checkout is elsewhere

    def gate_wt(self):
        return self.af("checks", "gate", "t", "--dir", self.wt, "--base", "base", "--branch", "feat2")

    def lines_from_the_main_checkout(self, *extra):
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            self.ok("check", "t", b, "pass", "--by", "tm", "--evidence", "ok", *extra)
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Review", "--evidence", "read it", *extra)

    def test_without_commit_it_is_refused_and_names_both(self):
        self.lines_from_the_main_checkout()
        r = self.gate_wt()
        self.assertEqual(r.returncode, 1, r.stdout)
        base = self.git("rev-parse", "HEAD").strip()
        self.assertIn("PR REVIEW: pass at %s, not at the head %s, not accepted" % (base[:12], self.head[:12]),
                      r.stdout.splitlines())

    def test_with_commit_it_passes(self):
        self.lines_from_the_main_checkout("--commit", self.head)
        r = self.gate_wt()
        self.assertEqual(r.returncode, 0, r.stdout)


class TestA1Texts(unittest.TestCase):
    def test_reviewer_and_check_deputy_pass_the_commit(self):
        for f in (("agents", "reviewer.md"), ("agents", "check-deputy.md")):
            with self.subTest(file=f[1]):
                line = [l for l in read(*f).splitlines() if "agent-file.sh check" in l][0]
                self.assertIn("--commit <head>", line)

    def test_merge_gives_the_head(self):
        self.assertIn("head: <sha>", read("skills", "merge", "SKILL.md"))

    def test_r8(self):
        self.assertIn("pass --commit <the head they looked at>", rule("R8. ", "W1. "))


# ====================================================================== A2-A9 texts


class TestA2FastLaneBrief(unittest.TestCase):
    def test_dispatch_and_deputy(self):
        step2 = [l for l in read("skills", "dispatch", "SKILL.md").splitlines() if l.startswith("2. Small task")][0]
        for field in ("target:", "base:", "working branch:", "production branch:"):
            with self.subTest(field=field):
                self.assertIn(field, step2)
        dep = read("agents", "fast-lane-deputy.md")
        self.assertIn("`base:`", dep)
        self.assertIn("never derive", dep)


class TestA3FastLaneClickPath(unittest.TestCase):
    def test_report(self):
        report = read("agents", "fast-lane-deputy.md").split("Report (H3)")[1]
        self.assertIn("click path when FLOW CHECK or UI CHECK is planned", report)


class TestA4CreateThenReserve(unittest.TestCase):
    def test_dispatch(self):
        d = read("skills", "dispatch", "SKILL.md")
        self.assertNotIn("before `orca terminal create`", d.lower())
        self.assertLess(d.index("orca terminal create"), d.index("agent-room.sh reserve-pane"))


class TestA5PromoteUsage(unittest.TestCase):
    def test_usage(self):
        head = read("bin", "agent-promote.sh").split("\nset ")[0]
        line = [l for l in head.splitlines() if "--task" in l][0]
        self.assertNotIn("--owner-quote", line)


class TestA6OneMeaning(unittest.TestCase):
    def test_deputy(self):
        dep = read("agents", "merge-deputy.md")
        self.assertNotIn("is not your job", dep)
        desc = [l for l in dep.splitlines() if l.startswith("description:")][0]
        self.assertNotIn("test command", desc)                    # B2: no test run at the merge
        self.assertIn("merged by `agent-promote.sh --task` (not by you)", dep)


class TestA7WatchRoom(unittest.TestCase):
    def test_dispatch_signals(self):
        self.assertIn("WATCH ROOM", read("skills", "dispatch", "SKILL.md"))


class TestA8Reviewer(unittest.TestCase):
    def test_tree_and_merge(self):
        tree = read("PRINCIPLES.md").split("## F. Map")[1]
        self.assertNotIn("Reviewer (Opus 5.5, high)", tree)
        self.assertIn("Reviewer model setting", tree)
        m = read("skills", "merge", "SKILL.md")
        self.assertIn("the model and the effort of the Reviewer model setting", m)


class TestA9NoSecondYes(unittest.TestCase):
    def test_three_places(self):
        for text in (rule("R8. ", "W1. "), read("skills", "dispatch", "SKILL.md"), read("skills", "merge", "SKILL.md")):
            self.assertNotIn("the owner's yes", text)
        self.assertIn("his verified words at dispatch that name the publish are his final yes", rule("R8. ", "W1. "))


import test_check_promote as tp  # noqa: E402


class TestW1PromoteSeesTheTasksLines(tp.PromoteCase):
    """Found by the walk: the deputy's and reviewer's lines live in the task's worktree, not in the main repo."""

    def test_lines_in_the_task_worktree_pass_the_direct_gate(self):
        import time as _t
        self.git("fetch", "-q", "origin")
        wt = os.path.join(self.repo.base, "wt_p1")
        self.git("worktree", "add", "-q", "-b", "p1", wt, "origin/main")
        with open(os.path.join(wt, "fix.txt"), "w") as fh:
            fh.write("fix\n")
        subprocess.run(["git", "-C", wt, "add", "-A"], check=True)
        subprocess.run(["git", "-C", wt, "commit", "-q", "-m", "urgent fix"], check=True)
        subprocess.run(["git", "-C", wt, "push", "-q", "-u", "origin", "p1"], check=True, capture_output=True)
        r = self.repo.run("agent-file.sh", "todo", "add", "p1", "small", "publish p1", "10", "--target", "production",
                          "--owner-quote", "fix it and publish it")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.repo.dir, "agent_worktree.txt"), "a") as fh:
            fh.write("%s | p1 | final | since %s\n" % (wt, _t.strftime("%Y-%m-%d %H:%M")))
        tcr.main_launched(self.repo.dir, "p1", at=_t.strftime("%Y-%m-%d %H:%M", _t.localtime(_t.time() - 120)))
        head = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        for block in ("PR REVIEW", "DIFF SCAN", "BUILD", "RELATED TESTS", "MODULE TESTS", "GUARD TESTS", "CORE REVIEW",
                      "EXAMPLES TEST"):
            r = self.repo.run("agent-file.sh", "check", "p1", block, "pass", "--by", "p1 Review", "--evidence", "ok",
                              "--commit", head, cwd=wt)                     # written in the task's worktree
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.repo.run("agent-promote.sh", "--task", "p1", "--branch", "p1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_results_file_for_a_remote_task(self):
        self.assertIn("--results <file>", read("bin", "agent-promote.sh").split("\nset ")[0])
        prod = [l for l in read("skills", "merge", "SKILL.md").splitlines() if "agent-promote.sh --task" in l][0]
        self.assertIn("--results", prod)


class TestWalks(unittest.TestCase):
    def test_the_demo_walks_both_flows(self):
        demo = read("tests", "check_blocks_demo.sh")
        self.assertIn("walk 1: a small task from dispatch to todo done", demo)
        self.assertIn("walk 2: a task with target production", demo)
        self.assertGreaterEqual(demo.count("--commit"), 2)


if __name__ == "__main__":
    unittest.main()
