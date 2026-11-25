"""Failing tests for check-blocks sections 28-29 (owner 2026-11-25, TELLs 76bfcc8f, 84fbcf51), C36': production only on the
owner's verified words, only from a green commit; the release build runs right after, by itself.
Written by the task manager before any code.

    bin/agent-promote.sh --owner-quote "<words>" [--time <t>]

Run: python3 -m unittest tests.test_check_promote
"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scripthelp import ScriptCase  # noqa: E402


class PromoteCase(ScriptCase):
    script = "agent-promote.sh"

    def git(self, *args, cwd=None):
        return subprocess.run(["git", "-C", cwd or self.repo.dir] + list(args), check=True, capture_output=True,
                              text=True).stdout.strip()

    def put(self, rel, body, cwd=None):
        full = os.path.join(cwd or self.repo.dir, rel)
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w") as fh:
            fh.write(body)

    def setUp(self):
        super().setUp()
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        import agent_conf
        self.wb = "ap-main-t"   # section 34: per person; the fixture's git user.name is t
        self.git("branch", "-M", "main")
        self.origin = os.path.join(self.repo.base, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", self.origin], check=True, capture_output=True)
        self.git("remote", "add", "origin", self.origin)
        self.git("push", "-q", "-u", "origin", "main")
        self.git("switch", "-q", "-c", self.wb)                 # section 29: the main checkout is on it
        self.git("config", "--local", "auto-pipeline.workingbranch", self.wb)   # stored by init (section 37 F10)
        self.commit_wb({"src/a.py": "x = 2\n"}, "Merge feat-a (W8)")
        self.verified(True)

    def commit_wb(self, files, msg):
        for rel, body in files.items():
            self.put(rel, body)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        self.git("push", "-q", "-u", "origin", self.wb)
        self.tip = self.git("rev-parse", self.wb)

    def verified(self, ok):
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho %s\nexit %d\n"
                                   % ("verified" if ok else "'not found'", 0 if ok else 1))

    def green(self, commit=None, result="green"):
        gd = self.git("rev-parse", "--path-format=absolute", "--git-common-dir")
        with open(os.path.join(gd, "agent_nightly.json"), "w") as fh:
            json.dump({"started": "2026-11-25 15:00", "commit": commit or self.tip, "finished": "2026-11-25 15:20",
                       "result": result, "failed": []}, fh)

    def release_stub(self):
        log = os.path.join(self.repo.base, "release.log")
        self.put("bin/agent-release.sh", "#!/usr/bin/env bash\nprintf '%%s\\n' \"$@\" > %s\n" % log)
        os.chmod(os.path.join(self.repo.dir, "bin", "agent-release.sh"), 0o755)   # executable in the commit
        self.commit_wb({}, "release build")
        return log

    def ready_direct(self, task, branch, quote=None):
        """Section 44 F1: dispatch stores the owner's words with the target; the main manager's reviewer passed."""
        import time as _t
        sys.path.insert(0, HERE)
        import test_check_results as _tcr
        quote = quote or "yes, publish %s to production" % task          # section 51 H2: the exact sentence
        r = self.repo.run("agent-file.sh", "todo", "add", task, "small", "publish " + task, "10",
                          "--target", "production", "--owner-quote", quote)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        _tcr.main_launched(self.repo.dir, task)                      # G8: within the task instance (now)
        self.git("fetch", "-q", "origin")
        sha = self.git("rev-parse", "origin/" + branch)
        for block in ("PR REVIEW", "DIFF SCAN", "BUILD", "RELATED TESTS", "MODULE TESTS", "GUARD TESTS",
                      "CORE REVIEW", "EXAMPLES TEST"):
            r = self.repo.run("agent-file.sh", "check", task, block, "pass", "--by", task + " Reviewer",
                              "--evidence", "ok", "--commit", sha)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def promote(self, *extra):
        return self.repo.run("agent-promote.sh", "--owner-quote", "yes ship it to production", *extra)


class TestPromote(PromoteCase):

    def test_green_and_verified_goes_to_production(self):
        self.green()
        r = self.promote()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.git("rev-parse", "origin/main"), self.tip)
        self.assertEqual(self.git("rev-parse", "main"), self.tip, "the local production ref follows")
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), self.wb, "the checkout stays on it")
        self.assertIn("promote: main -> %s (Merge feat-a (W8))" % self.tip[:7], r.stdout.splitlines())
        self.assertIn("release: no release build in this repo", r.stdout.splitlines())

    def test_the_release_build_runs_right_after(self):
        log = self.release_stub()
        self.green()
        r = self.promote()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(log) as fh:
            self.assertEqual(fh.read().split(), ["--push"])
        self.assertIn("release: ran bin/agent-release.sh --push", r.stdout.splitlines())

    def test_not_verified_is_refused(self):
        self.green()
        self.verified(False)
        r = self.promote()
        self.assertEqual(r.returncode, 1)
        self.assertNotEqual(self.git("rev-parse", "origin/main"), self.tip)

    def test_not_green_is_refused(self):
        for st in (dict(result="red"), dict(commit="0" * 40)):
            with self.subTest(st=st):
                self.green(**st)
                r = self.promote()
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertNotEqual(self.git("rev-parse", "origin/main"), self.tip)

    def test_production_must_be_an_ancestor(self):
        self.green()
        self.git("switch", "-q", "-c", "hot", "main")
        self.put("hotfix.txt", "x\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "a fix on production not merged back")
        self.git("push", "-q", "origin", "hot:main")
        self.git("switch", "-q", self.wb)
        r = self.promote()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("merge production back into the working branch first", r.stdout + r.stderr)

    def test_production_branch_from_the_repo_file(self):
        self.git("push", "-q", "origin", "main:refs/heads/prod")
        self.put("agent_repo.conf", "production_branch=prod\n")
        self.green()
        r = self.promote()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.git("rev-parse", "origin/prod"), self.tip)


class TestDirectToProduction(PromoteCase):
    """Section 30 (a, c, e): a request that says publish or merge to main: the task branch goes straight into
    production through a short-lived worktree; the main checkout stays on the working branch; production is
    merged back into the working branch at once."""

    def task_branch(self, files, name="feat-p"):
        self.git("switch", "-q", "-c", name, "main")
        for rel, body in files.items():
            self.put(rel, body)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "work on " + name)
        self.git("push", "-q", "-u", "origin", name)
        self.git("switch", "-q", self.wb)
        return name

    def worktree_paths(self):
        return [l.split()[1] for l in self.git("worktree", "list", "--porcelain").splitlines()
                if l.startswith("worktree ")]

    def direct(self, branch, *extra):
        self.ready_direct("feat-p", branch)                          # section 44 F1: words come from the task
        return self.repo.run("agent-promote.sh", "--task", "feat-p", "--branch", branch, *extra)

    def test_straight_into_production_then_merged_back(self):
        b = self.task_branch({"src/total.py": "t = 1\n"})
        before_wt = self.worktree_paths()
        r = self.direct(b)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.git("fetch", "-q", "origin")
        self.assertIn("Merge feat-p (W8)", self.git("log", "-1", "--format=%s", "origin/main"))
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), self.wb, "the checkout never switched")
        self.assertEqual(self.worktree_paths(), before_wt, "the short-lived worktree is gone")
        self.assertEqual(subprocess.run(["git", "-C", self.repo.dir, "merge-base", "--is-ancestor", "origin/main",
                                         self.wb]).returncode, 0, "production merged back into the working branch")
        lines = r.stdout.splitlines()
        self.assertTrue(any(l.startswith("promote: feat-p -> main (") for l in lines), lines)
        self.assertIn("merged back: main -> %s" % self.wb, lines)

    def test_the_release_build_runs_after_a_direct_merge(self):
        log = self.release_stub()
        self.git("push", "-q", "origin", "%s:main" % self.wb)        # production has the build too
        b = self.task_branch({"src/total.py": "t = 1\n"})
        r = self.direct(b)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(log) as fh:
            self.assertEqual(fh.read().split(), ["--push"])

    def test_not_verified_is_refused_and_nothing_moves(self):
        # section 44 F1: the words are verified when the target is set; unverified -> no production task at all
        self.verified(False)
        b = self.task_branch({"src/total.py": "t = 1\n"})
        before = self.git("rev-parse", "origin/main")
        r = self.repo.run("agent-file.sh", "todo", "add", "feat-p", "small", "x", "10", "--target", "production",
                          "--owner-quote", "yes, publish feat-p to production")   # section 51 H2: the exact sentence
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(self.repo.run("agent-promote.sh", "--task", "feat-p", "--branch", b).returncode, 1)
        self.assertEqual(self.git("rev-parse", "origin/main"), before)

    def test_a_conflict_is_refused_and_cleaned_up(self):
        self.git("switch", "-q", "-c", "c1", "main")
        self.put("src/a.py", "conflict one\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "c1")
        self.git("push", "-q", "origin", "c1:main")
        self.git("switch", "-q", self.wb)
        b = self.task_branch({"src/a.py": "conflict two\n"}, name="feat-c")
        b = "feat-c"
        before = self.git("rev-parse", "origin/main")
        before_wt = self.worktree_paths()
        self.ready_direct("feat-c", b)
        r = self.repo.run("agent-promote.sh", "--task", "feat-c", "--branch", b)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.git("rev-parse", "origin/main"), before)
        self.assertEqual(self.worktree_paths(), before_wt)


class TestSync(PromoteCase):
    """Section 34: production is merged into the working branch at the start of a batch and before a publish."""

    def production_moves(self):
        self.git("switch", "-q", "-c", "other", "main")
        self.put("other.txt", "someone else published\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "another person's publish")
        self.git("push", "-q", "origin", "other:main")
        self.git("switch", "-q", self.wb)

    def test_sync_merges_production_in_and_pushes(self):
        self.production_moves()
        r = self.repo.run("agent-promote.sh", "--sync")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.splitlines()[0].startswith("sync: main merged into %s (" % self.wb), r.stdout)
        self.git("fetch", "-q", "origin")
        self.assertEqual(subprocess.run(["git", "-C", self.repo.dir, "merge-base", "--is-ancestor", "origin/main",
                                         "origin/" + self.wb]).returncode, 0)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), self.wb)

    def test_sync_when_already_in(self):
        r = self.repo.run("agent-promote.sh", "--sync")
        self.assertEqual(r.stdout.strip(), "sync: %s already has main" % self.wb)

    def test_sync_waits_on_a_dirty_checkout(self):
        self.production_moves()
        self.put("src/a.py", "half done\n")
        r = self.repo.run("agent-promote.sh", "--sync")
        self.assertTrue(r.stdout.strip().startswith("sync waits: "), r.stdout)
        with open(os.path.join(self.repo.dir, "src", "a.py")) as fh:
            self.assertEqual(fh.read(), "half done\n")

    def test_a_publish_syncs_first(self):
        self.production_moves()
        self.green()                                   # green on the old tip: after the sync it is not the tip
        r = self.promote()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("sync: main merged into %s" % self.wb, r.stdout)


if __name__ == "__main__":
    unittest.main()
