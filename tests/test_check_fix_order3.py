"""Failing tests for check-blocks section 44: FIX ORDER 3 of the main manager (TELL 7a7407c8), F1-F14.
Written by the task manager before any fix.

Run: python3 -m unittest tests.test_check_fix_order3
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
import test_check_promote as tp  # noqa: E402
import test_check_results as tcr  # noqa: E402
import test_board_trust as tbt  # noqa: E402
from test_check_init import InitCase  # noqa: E402


def only_own(cls):
    own = set(vars(cls))
    for name in dir(cls):
        if name.startswith("test") and name not in own:
            setattr(cls, name, None)
    return cls


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def minute(delta_s=0):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() + delta_s))


# ====================================================================== F1 the direct path is bound to the task


class TestF1DirectPath(tp.PromoteCase):
    def branch_from_main(self, name):
        self.git("switch", "-q", "-c", name, "origin/main")
        self.put("src/total.py", "t = 1\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "work on " + name)
        self.git("push", "-q", "-u", "origin", name)
        self.git("switch", "-q", self.wb)
        return name

    def test_a_quote_at_promote_is_refused(self):
        b = self.branch_from_main("feat-q")
        r = self.repo.run("agent-promote.sh", "--task", b, "--branch", b, "--owner-quote", "please fix the footer typo")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("the owner's words come from the task (todo add --target production --owner-quote), "
                      "not from promote", r.stdout + r.stderr)

    def test_not_a_production_task_is_refused(self):
        b = self.branch_from_main("feat-w")
        self.repo.run("agent-file.sh", "todo", "add", b, "small", "x", "10")
        before = self.git("rev-parse", "origin/main")
        r = self.repo.run("agent-promote.sh", "--task", b, "--branch", b)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("%s is not a production task (todo add --target production)" % b, r.stdout + r.stderr)
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.git("rev-parse", "origin/main"), before)

    def test_target_production_needs_verified_words(self):
        r = self.repo.run("agent-file.sh", "todo", "add", "feat-v", "small", "x", "10", "--target", "production")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.verified(False)
        r = self.repo.run("agent-file.sh", "todo", "add", "feat-v", "small", "x", "10", "--target", "production",
                          "--owner-quote", "yes, publish feat-v to production")   # section 51 H2: the exact sentence
        self.assertEqual(r.returncode, 1, r.stdout)
        with open(os.path.join(self.repo.dir, "agent_todo.txt")) as fh:
            self.assertNotIn("feat-v", fh.read())

    def test_no_stored_words_is_refused(self):
        b = self.branch_from_main("feat-s")
        with open(os.path.join(self.repo.dir, "agent_todo.txt"), "a") as fh:
            fh.write("%s | small | x | est 10m | opened %s | target production\n" % (b, minute(-600)))
        r = self.repo.run("agent-promote.sh", "--task", b, "--branch", b)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no owner words stored for %s" % b, r.stdout + r.stderr)

    def test_the_gate_runs_first(self):
        b = self.branch_from_main("feat-g")
        r = self.repo.run("agent-file.sh", "todo", "add", b, "small", "x", "10", "--target", "production",
                          "--owner-quote", "yes, publish %s to production" % b)   # section 51 H2: the exact sentence
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        before = self.git("rev-parse", "origin/main")
        r = self.repo.run("agent-promote.sh", "--task", b, "--branch", b)     # no reviewer, no check lines
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("GATE REFUSED", r.stdout)
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.git("rev-parse", "origin/main"), before)

    def test_the_stored_words(self):
        b = self.branch_from_main("feat-k")
        self.ready_direct(b, b)
        gd = self.git("rev-parse", "--path-format=absolute", "--git-common-dir")
        with open(os.path.join(gd, "agent_owner_words.json")) as fh:
            self.assertEqual(json.load(fh)[b]["quote"], "yes, publish %s to production" % b)
        r = self.repo.run("agent-promote.sh", "--task", b, "--branch", b)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


# ====================================================================== F2 the reviewer is the main manager's


@only_own
class TestF2Launches(tcr.TestGate):
    def launches_file(self):
        return os.path.join(self.git("rev-parse", "--path-format=absolute", "--git-common-dir").strip(),
                            "agent_launches.jsonl")

    def set_launch(self, by, at="2000-01-01 00:00"):
        with open(self.launches_file(), "w") as fh:
            fh.write(json.dumps({"task": "t", "type": "reviewer", "by": by, "at": at}) + "\n")

    def review(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "read it")

    def test_no_launch_record_is_refused(self):
        os.remove(self.launches_file())
        self.review()
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: no reviewer launched by the main manager for t, not accepted", r.stdout.splitlines())

    def test_a_reviewer_the_builder_launched_does_not_count(self):
        self.set_launch("tm")
        self.review()
        self.assertEqual(self.gate().returncode, 1)

    def test_a_pass_older_than_the_launch_does_not_count(self):
        self.review()
        self.set_launch("main", at="2099-01-01 00:00")
        self.assertEqual(self.gate().returncode, 1)

    def test_with_the_record_it_passes(self):
        self.review()
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_the_fake_clock_only_in_tests(self):
        self.ok("check", "t", "BUILD", "pass", "--by", "tm", "--evidence", "ok",
                env={"AGENT_TESTING": "", "AGENT_FAKE_NOW": "2030-01-01 00:00"})
        last = [l for l in self.state().splitlines() if l.startswith("CHECK t BUILD")][-1]
        self.assertNotIn("2030-01-01", last)


class TestF2TheGuardWritesTheRecord(tbt.GuardCase):
    def records(self):
        gd = subprocess.run(["git", "-C", self.repo.dir, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True, check=True).stdout.strip()
        path = os.path.join(gd, "agent_launches.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def test_a_reviewer_launched_by_the_main_manager(self):
        self.make_main()
        self.put_todo("t")
        self.pre_agent("t Review", stype="auto-pipeline:reviewer")
        recs = [r for r in self.records() if r.get("task") == "t"]
        self.assertEqual([(r["type"], r["by"]) for r in recs], [("reviewer", "main")])

    def test_a_check_deputy_launched_by_a_task_manager_is_not_the_main_managers(self):
        self.put_todo("t")
        self.pre_agent("t Check", stype="auto-pipeline:check-deputy", role="task-manager")
        recs = [r for r in self.records() if r.get("task") == "t"]
        self.assertTrue(recs)
        self.assertNotEqual(recs[-1]["by"], "main")


# ====================================================================== F3 a pass is tied to a commit


@only_own
class TestF3Commits(tcr.TestGate):
    def head(self):
        return self.git("rev-parse", "HEAD").strip()

    def review(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "read it")

    def test_the_line_records_the_commit(self):
        self.review()
        last = [l for l in self.state().splitlines() if l.startswith("CHECK t PR REVIEW")][-1]
        self.assertIn("| at %s |" % self.head()[:12], last)

    def test_a_pass_on_an_older_commit_is_refused(self):
        self.review()
        self.commit_push({"app.js": "z()\n"})
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue([l for l in r.stdout.splitlines()
                         if re.match(r"^PR REVIEW: pass at \w+, not at the head \w+, not accepted$", l)], r.stdout)

    def test_a_later_merge_of_the_base_is_fine(self):
        self.review()
        self.git("checkout", "-q", "-b", "trunk", "base")
        self.commit_push({"other.js": "o()\n"})
        self.git("checkout", "-q", "feat")
        self.git("merge", "-q", "--no-ff", "-m", "Merge trunk into feat", "trunk")
        self.git("push", "-q", "origin", "feat")
        r = self.af("checks", "gate", "t", "--dir", self.repo.dir, "--base", "origin/trunk")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_dir_must_be_on_the_branch(self):
        self.review()
        self.commit_push({"app.js": "w()\n"}, push=False)                  # --dir is ahead of origin/feat
        r = self.gate("--branch", "feat")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("GATE REFUSED t: --dir is not on origin/feat", r.stdout)

    def test_a_line_without_a_commit_is_not_accepted(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:     # appended by hand, no `at`
            fh.write("CHECK t PR REVIEW: pass | by t Reviewer | read it | %s\n" % minute(60))
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: pass with no commit, not accepted", r.stdout.splitlines())

    def test_lines_before_the_task_opened_are_ignored(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("CHECK t PR REVIEW: pass | by t Reviewer | at %s | read it | 2001-01-01 00:00\n" % self.head()[:12])
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: missing", r.stdout.splitlines())


# ====================================================================== F4 decided by what is committed


class TestF4AlreadyUsesThePlugin(InitCase):
    def head(self):
        return self.git("rev-parse", "--abbrev-ref", "HEAD").strip()

    def test_a_clone_of_a_plugin_repo_is_not_switched(self):
        self.assertIn("agent_todo.txt", self.git("ls-files"))              # committed: the repo uses the plugin
        r = self.init("--no-measure")
        self.assertNotEqual(self.head(), "ap-main-t")
        self.assertTrue([l for l in r.stdout.splitlines() if l.startswith("WORKING BRANCH: ")], r.stdout)

    def test_a_new_repo_with_a_local_state_file_is_switched(self):
        tracked = [f for f in self.git("ls-files").split() if f.startswith("agent_")]
        self.git("rm", "-q", "--cached", *tracked)
        self.git("commit", "-q", "-m", "not yet a plugin repo")
        self.put({"agent_state.txt": "ROLE: main manager\n"})              # a local file decides nothing
        self.init("--no-measure")
        self.assertEqual(self.head(), "ap-main-t")


# ====================================================================== F5 a fail wins a tie


@only_own
class TestF5Tie(tcr.TestGate):
    def test_same_minute_fail_wins(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        env = {"AGENT_FAKE_NOW": minute()}
        self.ok("check", "t", "PR REVIEW", "fail", "--by", "t Reviewer", "--evidence", "broken", env=env)
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "ok", env=env)
        self.assertEqual(self.gate().returncode, 1)


# ====================================================================== F6 the remote working branch


class TestF6RemoteWorkingBranch(InitCase):
    def origin_with(self, extra_commit):
        origin = os.path.join(self.repo.base, "origin6.git")
        subprocess.run(["git", "init", "-q", "--bare", origin], check=True, capture_output=True)
        self.git("remote", "add", "origin", origin)
        other = tempfile.mkdtemp(prefix="f6_")
        self.addCleanup(subprocess.run, ["rm", "-rf", other])
        self.git("push", "-q", "origin", "HEAD:refs/heads/ap-main-t")
        subprocess.run(["git", "clone", "-q", origin, other], check=True, capture_output=True)
        if extra_commit:
            subprocess.run(["git", "-C", other, "switch", "-q", "ap-main-t"], check=True, capture_output=True)
            with open(os.path.join(other, "theirs.txt"), "w") as fh:
                fh.write("unreleased work\n")
            subprocess.run(["git", "-C", other, "add", "-A"], check=True, capture_output=True)
            subprocess.run(["git", "-C", other, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                            "-m", "unreleased"], check=True, capture_output=True)
            subprocess.run(["git", "-C", other, "push", "-q", "origin", "ap-main-t"], check=True, capture_output=True)
        return origin

    def test_tracks_the_remote_branch(self):
        self.origin_with(extra_commit=True)
        self.git("fetch", "-q", "origin")
        r = self.init("--no-measure")
        self.assertIn("working branch: tracking origin/ap-main-t", r.stdout.splitlines())
        self.assertEqual(self.git("rev-parse", "ap-main-t").strip(), self.git("rev-parse", "origin/ap-main-t").strip())

    def test_a_rejected_push_says_why(self):
        self.origin_with(extra_commit=True)
        self.git("branch", "ap-main-t")                                    # a local branch without their commit
        self.git("switch", "-q", "ap-main-t")
        self.put({"mine.txt": "mine\n"})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "mine")
        r = self.init("--no-measure")
        self.assertIn("working branch: not pushed: the remote has commits this clone does not have "
                      "(fetch and merge origin/ap-main-t first)", r.stdout.splitlines())


# ====================================================================== F7, F8, F9, F12, F14 promote


class TestF7AgentFilesNeverBlock(tp.PromoteCase):
    def test_sync_with_a_modified_agent_todo(self):
        self.assertIn("agent_todo.txt", self.git("ls-files"))
        self.git("switch", "-q", "-c", "other", "main")
        self.put("other.txt", "someone else published\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "another person's publish")
        self.git("push", "-q", "origin", "other:main")
        self.git("switch", "-q", self.wb)
        with open(os.path.join(self.repo.dir, "agent_todo.txt"), "a") as fh:
            fh.write("x | small | x | est 5m\n")                             # " M agent_todo.txt"
        r = self.repo.run("agent-promote.sh", "--sync")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.splitlines()[0].startswith("sync: main merged into %s (" % self.wb), r.stdout)


class TestF8PushTheCheckedSha(tp.PromoteCase):
    def test_a_tip_moved_after_the_check_is_not_pushed(self):
        self.green()
        checked = self.tip
        site = tempfile.mkdtemp(prefix="f8_")
        self.addCleanup(subprocess.run, ["rm", "-rf", site])
        with open(os.path.join(site, "sitecustomize.py"), "w") as fh:
            fh.write("import os, subprocess, sys\n"
                     "sys.path.insert(0, os.environ['F8_BIN'])\n"
                     "import agent_nightly\n"
                     "_ok = agent_nightly.release_ok\n"
                     "def _moved(cwd, *a, **k):\n"
                     "    rc = _ok(cwd, *a, **k)\n"
                     "    subprocess.run(['git', '-C', os.environ['F8_REPO'], 'commit', '-q', '--allow-empty', '-m',\n"
                     "                    'moved after the check'], check=True)\n"
                     "    return rc\n"
                     "agent_nightly.release_ok = _moved\n")
        r = self.repo.run("agent-promote.sh", "--owner-quote", "yes ship it to production",
                          env={"PYTHONPATH": site, "F8_BIN": os.path.join(self.repo.plugin, "bin"),
                               "F8_REPO": self.repo.dir})
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.git("rev-parse", "origin/main"), checked, r.stdout + r.stderr)


class TestF9ReleaseFromThePublishedCommit(tp.PromoteCase):
    def test_the_release_runs_at_the_published_commit_outside_the_checkout(self):
        log = os.path.join(self.repo.base, "where.log")
        self.put("bin/agent-release.sh", "#!/usr/bin/env bash\n{ pwd -P; git rev-parse HEAD; } > %s\n" % log)
        os.chmod(os.path.join(self.repo.dir, "bin", "agent-release.sh"), 0o755)
        self.commit_wb({}, "release build")
        self.green()
        r = self.promote()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(log) as fh:
            where, head = fh.read().split()
        self.assertEqual(head, self.tip)
        self.assertNotEqual(where, os.path.realpath(self.repo.dir))


class TestF12OnlyItsOwnMerge(tp.PromoteCase):
    def test_a_merge_in_progress_is_left_alone(self):
        self.git("switch", "-q", "-c", "side", "main")
        self.put("src/a.py", "side\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "side")
        self.git("switch", "-q", "-c", "other", "main")              # production moves: sync has work to do
        self.put("other.txt", "someone else published\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "another person's publish")
        self.git("push", "-q", "origin", "other:main")
        self.git("switch", "-q", self.wb)
        subprocess.run(["git", "-C", self.repo.dir, "merge", "side"], capture_output=True)   # conflicts: in progress
        gd = self.git("rev-parse", "--git-dir")
        merge_head = os.path.join(self.repo.dir, gd, "MERGE_HEAD") if not os.path.isabs(gd) else os.path.join(gd, "MERGE_HEAD")
        self.assertTrue(os.path.exists(merge_head))
        r = self.repo.run("agent-promote.sh", "--sync")
        self.assertIn("a merge is in progress in", r.stdout)
        self.assertIn("(not started by this run)", r.stdout)
        self.assertTrue(os.path.exists(merge_head), "someone else's merge was aborted")


class TestF14StaleWorktrees(tp.PromoteCase):
    def test_a_dead_runs_worktree_is_pruned(self):
        gd = self.git("rev-parse", "--path-format=absolute", "--git-common-dir")
        stale = os.path.join(gd, "agent_promote_wt_999999")
        self.git("worktree", "add", "-q", "--detach", stale, "main")
        self.repo.run("agent-promote.sh", "--sync")
        self.assertFalse(os.path.exists(stale))


# ====================================================================== F10 a string literal in code is code


class TestF10StringLiterals(unittest.TestCase):
    def level(self, files_before, files_after):
        d = tempfile.mkdtemp(prefix="f10_")
        self.addCleanup(subprocess.run, ["rm", "-rf", d])
        g = lambda *a: subprocess.run(["git", "-C", d] + list(a), check=True, capture_output=True, text=True).stdout
        g("init", "-q")
        g("config", "user.email", "t@t")
        g("config", "user.name", "t")
        for rel, body in files_before.items():
            os.makedirs(os.path.dirname(os.path.join(d, rel)) or d, exist_ok=True)
            with open(os.path.join(d, rel), "w") as fh:
                fh.write(body)
        g("add", "-A")
        g("commit", "-q", "-m", "base")
        g("tag", "base")
        for rel, body in files_after.items():
            with open(os.path.join(d, rel), "w") as fh:
                fh.write(body)
        r = subprocess.run([os.path.join(BIN, "agent-level.sh"), "check", "--base", "base"], cwd=d,
                           capture_output=True, text=True)
        return [l for l in r.stdout.splitlines() if l.startswith("FILE ")]

    def test_sql_role_and_url_strings_are_code(self):
        cases = [("app.py", 'QUERY = "SELECT * FROM users"\n', 'QUERY = "DELETE FROM users"\n'),
                 ("auth.js", "const ROLE = 'admin';\n", "const ROLE = 'guest';\n"),
                 ("api.py", 'URL = "https://api.example.com/v1"\n', 'URL = "https://evil.example.net/v1"\n')]
        for rel, before, after in cases:
            with self.subTest(file=rel):
                lines = self.level({rel: before}, {rel: after})
                self.assertTrue(lines and lines[0].startswith("FILE %s: code" % rel), lines)

    def test_a_comment_stays_text(self):
        lines = self.level({"app.py": "# list the users\nx = 1\n"}, {"app.py": "# list every user\nx = 1\n"})
        self.assertTrue(lines and lines[0].startswith("FILE app.py: text"), lines)


# ====================================================================== F11 blocks are only added


@only_own
class TestF11Removals(tcr.TestGate):
    def setUp(self):
        super().setUp()
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")

    def test_a_verified_removal_is_subtracted_by_the_gate(self):
        r = self.af("todo", "checks", "t", "--remove", "RELATED TESTS", "--owner-quote", "yes, skip RELATED TESTS for t")   # section 51 H2: the exact sentence
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.passes("DIFF SCAN", "BUILD")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "read it")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_brief_blocks_survive_drop_and_add(self):
        self.ok("todo", "add", "t2", "small", "x", "10", "--checks", "EXAMPLES TEST")
        self.ok("todo", "drop", "t2", "started again")
        self.ok("todo", "add", "t2", "small", "x", "10")
        tcr.main_launched(self.repo.dir, "t2")
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            self.ok("check", "t2", b, "pass", "--by", "tm", "--evidence", "ok")
        self.ok("check", "t2", "PR REVIEW", "pass", "--by", "t2 Reviewer", "--evidence", "ok")
        r = self.af("checks", "gate", "t2", "--dir", self.repo.dir, "--base", "base")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("EXAMPLES TEST: missing", r.stdout.splitlines())


# ====================================================================== F13 one production branch


class TestF13OneProductionBranch(unittest.TestCase):
    def test_a_master_repo(self):
        d = tempfile.mkdtemp(prefix="f13_")
        self.addCleanup(subprocess.run, ["rm", "-rf", d])
        g = lambda *a: subprocess.run(["git", "-C", d] + list(a), check=True, capture_output=True, text=True).stdout
        g("init", "-q", "-b", "master")
        g("config", "user.email", "t@t")
        g("config", "user.name", "t")
        g("commit", "-q", "--allow-empty", "-m", "base")
        g("switch", "-q", "-c", "ap-main-t")
        sys.path.insert(0, BIN)
        import agent_conf
        self.assertEqual(agent_conf.production_branch(d), "master")

    def test_everyone_uses_it(self):
        for f in ("agent_promote.py", "agent_checks.py", "agent_repo_init.py", "agent_cleanup.py", "agent_nightly.py"):
            with self.subTest(file=f):
                self.assertIn("production_branch(", read("bin", f))


if __name__ == "__main__":
    unittest.main()
