"""Failing tests for check-blocks section 28 (owner 2026-11-25, TELL 76bfcc8f), C36: production only on the
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
        self.git("branch", "-M", "main")
        self.origin = os.path.join(self.repo.base, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", self.origin], check=True, capture_output=True)
        self.git("remote", "add", "origin", self.origin)
        self.git("push", "-q", "-u", "origin", "main")
        self.wt = os.path.join(self.repo.base, "project-ap-worktree")
        self.git("worktree", "add", "-q", "-b", "ap-worktree", self.wt, "main")
        self.put("src/a.py", "x = 2\n", cwd=self.wt)
        self.git("add", "-A", cwd=self.wt)
        self.git("commit", "-q", "-m", "Merge feat-a (W8)", cwd=self.wt)
        self.git("push", "-q", "-u", "origin", "ap-worktree", cwd=self.wt)
        self.tip = self.git("rev-parse", "ap-worktree")
        self.verified(True)

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
        os.chmod(os.path.join(self.repo.dir, "bin", "agent-release.sh"), 0o755)
        self.git("add", "bin/agent-release.sh")
        self.git("commit", "-q", "-m", "release build")
        self.git("push", "-q", "origin", "main")
        self.git("merge", "-q", "main", cwd=self.wt)                   # production merged back in
        self.git("push", "-q", "origin", "ap-worktree", cwd=self.wt)
        self.tip = self.git("rev-parse", "ap-worktree")
        return log

    def promote(self, *extra):
        return self.repo.run("agent-promote.sh", "--owner-quote", "yes ship it to production", *extra)


class TestPromote(PromoteCase):

    def test_green_and_verified_goes_to_production(self):
        self.green()
        r = self.promote()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.git("rev-parse", "origin/main"), self.tip)
        self.assertEqual(self.git("rev-parse", "main"), self.tip, "the clean main checkout follows")
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), "main")
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
        self.put("hotfix.txt", "x\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "a fix on production not merged back")
        self.git("push", "-q", "origin", "main")
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


if __name__ == "__main__":
    unittest.main()
