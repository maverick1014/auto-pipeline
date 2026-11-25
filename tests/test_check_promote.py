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
        self.wb = agent_conf.WORKING_BRANCH_DEFAULT
        self.git("branch", "-M", "main")
        self.origin = os.path.join(self.repo.base, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", self.origin], check=True, capture_output=True)
        self.git("remote", "add", "origin", self.origin)
        self.git("push", "-q", "-u", "origin", "main")
        self.git("switch", "-q", "-c", self.wb)                 # section 29: the main checkout is on it
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
        self.commit_wb({"bin/agent-release.sh": "#!/usr/bin/env bash\nprintf '%%s\\n' \"$@\" > %s\n" % log},
                       "release build")
        os.chmod(os.path.join(self.repo.dir, "bin", "agent-release.sh"), 0o755)
        return log

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


if __name__ == "__main__":
    unittest.main()
