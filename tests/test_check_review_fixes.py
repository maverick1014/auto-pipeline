"""Failing tests for check-blocks section 37: the CORE REVIEW findings of 2026-11-25 16:4x, one small test each.
Written by the task manager before any fix.

Run: python3 -m unittest tests.test_check_review_fixes
"""

import getpass
import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
from scripthelp import BIN, ScriptRepo  # noqa: E402
import test_check_clear as tcc  # noqa: E402
import test_check_results as tcr  # noqa: E402
import test_check_warnings as tcw  # noqa: E402
import test_agent_owner_order as oo  # noqa: E402
from test_check_init import InitCase  # noqa: E402


def only_own(cls):
    """A subclass of a test class with tests: keep only the tests written in the subclass itself."""
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


class TestF1MergeDeputyChecksTheBranch(unittest.TestCase):
    def test_the_deputy_reads_the_branch_first(self):
        text = read("agents", "merge-deputy.md")
        for phrase in ("git branch --show-current", "push the branch the main checkout is on",
                       "still on the production branch", "merges go on as before", "any other branch: FAIL"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


@only_own
class TestF2CoreReviewIsNoBuildersJob(tcr.TestGate):
    def test_a_core_review_by_the_task_manager_is_refused(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "read it")
        self.ok("check", "t", "CORE REVIEW", "pass", "--by", "t Task Manager", "--evidence", "read it")
        sys.path.insert(0, BIN)
        import agent_checks
        self.assertIn("CORE REVIEW", agent_checks.BUILDER_BLOCKS)
        r = self.gate()
        if "CORE REVIEW" in r.stdout:
            self.assertIn("CORE REVIEW: pass by the builder (t Task Manager), not accepted", r.stdout.splitlines())

    def test_r8_names_it(self):
        self.assertIn("CORE REVIEW", [x for x in rule("R8. ", "W1. ").splitlines()
                                      if "builder" in x and "PR REVIEW" in x][0])


class TestF3NoStandingPushToProduction(InitCase):
    def test_init_names_the_working_branch_never_main(self):
        out = self.init("--no-measure").stdout
        self.assertNotIn("git push origin main", out)
        self.assertNotIn("integration branch", out)
        self.assertIn('allow "Bash(git push origin ap-main-t)"', out)

    def test_w16_and_clean_up(self):
        w16 = rule("W16. ", "W17. ")
        self.assertNotIn("integration branch", w16)
        self.assertIn("working branch", w16)
        cu = read("skills", "clean-up", "SKILL.md")
        self.assertNotIn("git push origin main", cu)
        self.assertIn("push the branch the main checkout is on", cu)


class TestF4ProductionIsNeverTheWorkingBranch(unittest.TestCase):
    def test_main_as_the_setting_falls_back(self):
        repo = ScriptRepo()
        self.addCleanup(repo.cleanup)
        subprocess.run(["git", "-C", repo.dir, "branch", "-M", "main"], check=True, capture_output=True)
        repo.set_conf("working_branch", "main")
        r = subprocess.run([sys.executable, os.path.join(repo.plugin, "bin", "agent_conf.py"), "working-branch", repo.dir],
                           capture_output=True, text=True, env=repo._env(None))
        self.assertEqual(r.stdout.strip(), "ap-main-t")
        self.assertIn('working branch: "main" is the production branch; using ap-main-t', r.stderr)


class TestF6AndF7Texts(unittest.TestCase):
    def test_second_opinion_line(self):
        line = "Beyond the reviewer's PR REVIEW, a second agent's opinion only for CORE REVIEW"
        self.assertIn(line, rule("R8. ", "W1. "))
        self.assertIn(line, read("skills", "dispatch", "SKILL.md"))

    def test_merge_skill(self):
        merge = read("skills", "merge", "SKILL.md")
        self.assertNotIn("run the browser E2E", merge)
        self.assertNotIn("run the browser E2E", read("PRINCIPLES.md"))
        self.assertIn("send the reviewer and the check deputy", merge.split("\n---")[0])
        self.assertIn("No click path while FLOW CHECK or UI CHECK is planned", merge)
        for f in (merge, read("skills", "dispatch", "SKILL.md")):
            self.assertNotIn("merge main back into your branch", f)
            self.assertIn("merge its base branch back into your branch", f)


@only_own
class TestF8TheBoardIsBuiltAtMostOnceAMinute(tcw.TestWarnHook):
    def test_inside_the_minute_the_board_is_not_built(self):
        self.hook()
        marker = os.path.join(self.repo.base, "board_imported")
        with open(os.path.join(self.repo.plugin, "bin", "agent_board.py"), "a") as fh:
            fh.write("\nopen(%r, 'w').close()\n" % marker)
        self.assertEqual(self.hook(), "")                       # the same minute
        self.assertFalse(os.path.exists(marker), "the board was built again inside the minute")
        with open(self.repo.path(".git", "agent_warn_seen.json")) as fh:
            self.assertIn("checked", json.load(fh))


@only_own
class TestF9ASessionStartedInASubfolder(tcc.TestHumanQuiet):
    def test_the_session_file_is_found_in_another_project_folder(self):
        other = os.path.join(self.t.cfg, "projects", oo.folder_name(os.path.join(self.repo.dir, "sub")))
        os.makedirs(other, exist_ok=True)
        with open(os.path.join(other, "s1.jsonl"), "w") as fh:
            fh.write(json.dumps(oo.owner("wait, one more thing", tcc.ago(5))) + "\n")
        r = self.quiet()
        self.assertEqual((r.returncode, r.stdout.strip()), (1, "typed 2026-11-20 11:55"), r.stderr)


class TestF10DerivedOnlyByInitAndTheStart(unittest.TestCase):
    def setUp(self):
        self.repo = ScriptRepo()
        self.addCleanup(self.repo.cleanup)
        sys.path.insert(0, BIN)
        import agent_conf
        self.ac = agent_conf

    def stored(self):
        return subprocess.run(["git", "-C", self.repo.dir, "config", "--local", "--get", "auto-pipeline.workingbranch"],
                              capture_output=True, text=True).stdout.strip()

    def test_a_reader_stores_nothing(self):
        old = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(old)))
        os.environ.update(self.repo._env(None))
        self.assertIsNone(self.ac.working_branch(self.repo.dir))
        self.assertEqual(self.stored(), "")
        self.assertEqual(self.ac.working_branch(self.repo.dir, derive=True), "ap-main-t")
        self.assertEqual(self.stored(), "ap-main-t")
        self.assertEqual(self.ac.working_branch(self.repo.dir), "ap-main-t")

    def test_an_empty_user_name_takes_the_login_name(self):
        old = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(old)))
        os.environ.update(self.repo._env(None))
        os.environ.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
        subprocess.run(["git", "-C", self.repo.dir, "config", "--local", "--unset", "user.name"], capture_output=True)
        want = re.sub(r"[^a-z0-9-]+", "-", getpass.getuser().lower()).strip("-") or "user"
        self.assertEqual(self.ac.working_branch(self.repo.dir, derive=True), "ap-main-" + want)

    def test_the_gate_with_nothing_stored_says_so(self):
        c = tcr.TestGate("test_the_check_deputy_is_no_builder")
        c.setUp()
        self.addCleanup(c.tearDown)
        c.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        c.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "read it")
        subprocess.run(["git", "-C", c.repo.dir, "config", "--local", "--unset", "auto-pipeline.workingbranch"],
                       capture_output=True)
        r = c.gate()
        self.assertIn("note: no working branch stored in this clone: give --base origin/<working branch> "
                      "(the brief names it)", r.stdout.splitlines())

    def test_promote_with_nothing_stored_is_refused(self):
        r = self.repo.run("agent-promote.sh", "--sync")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no working branch stored in this clone: run agent-init.sh or start the main manager here",
                      r.stdout + r.stderr)


# ============================================================ PR REVIEW findings (section 37, P1-P8)

import test_check_promote as tp  # noqa: E402
import test_agent_cleanup as tc  # noqa: E402


class TestP1P2P3P6Promote(tp.PromoteCase):
    def task_from(self, base, name="feat-p", body="t = 1\n"):
        self.git("switch", "-q", "-c", name, base)
        self.put("src/total.py", body)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "work on " + name)
        self.git("push", "-q", "-u", "origin", name)
        self.git("switch", "-q", self.wb)
        return name

    def direct(self, branch):
        return self.repo.run("agent-promote.sh", "--task", branch, "--branch", branch, "--owner-quote", "publish it")

    def test_p1_the_release_runs_on_a_production_commit(self):
        # like agent-release.sh: it refuses a commit that is not on the local production branch
        log = os.path.join(self.repo.base, "release.log")
        self.put("bin/agent-release.sh", "#!/usr/bin/env bash\ngit merge-base --is-ancestor HEAD refs/heads/main "
                 "|| { echo 'not on main: release only from main'; exit 1; }\necho ok > %s\n" % log)
        os.chmod(os.path.join(self.repo.dir, "bin", "agent-release.sh"), 0o755)
        self.commit_wb({}, "release build")
        self.git("push", "-q", "origin", "%s:main" % self.wb)
        b = self.task_from("origin/main")
        r = self.direct(b)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.exists(log), r.stdout)

    def test_p2_unpublished_working_branch_commits_are_refused(self):
        b = self.task_from(self.wb, name="feat-u")        # branched from the working branch by mistake
        before = self.git("rev-parse", "origin/main")
        r = self.direct(b)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("feat-u carries commits of %s that are not in main: branch it from main" % self.wb, r.stdout)
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.git("rev-parse", "origin/main"), before)

    def test_p2_the_urgent_deputy_starts_from_production(self):
        for f in (read("agents", "fast-lane-deputy.md"), read("skills", "dispatch", "SKILL.md")):
            self.assertIn("git switch -c <branch> origin/<production branch>", f)

    def test_p3_local_production_only_fast_forwards(self):
        self.git("switch", "-q", "main")
        self.put("stuck.txt", "a merge that never got pushed\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "local only")
        stuck = self.git("rev-parse", "HEAD")
        self.git("switch", "-q", self.wb)
        self.green()
        r = self.promote()
        self.assertEqual(subprocess.run(["git", "-C", self.repo.dir, "merge-base", "--is-ancestor", stuck, "main"]
                                        ).returncode, 0, "local main never moves backward")
        self.assertIn("local main not moved: not a fast-forward", r.stdout)

    def test_p6_another_promote_worktree_stays(self):
        gd = self.git("rev-parse", "--path-format=absolute", "--git-common-dir")
        other = os.path.join(gd, "agent_promote_wt")
        self.git("worktree", "add", "-q", "--detach", other, "main")
        b = self.task_from("origin/main")
        r = self.direct(b)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isdir(other), "a promote never removes a worktree it did not make")


class TestP4P5P8Init(InitCase):
    def head(self):
        return self.git("rev-parse", "--abbrev-ref", "HEAD").strip()

    def test_p4_a_repo_that_uses_the_plugin_is_not_switched(self):
        self.put({"agent_state.txt": "ROLE: main manager\n"})
        r = self.init("--no-measure")
        self.assertNotEqual(self.head(), "ap-main-t")
        self.assertTrue([l for l in r.stdout.splitlines() if l.startswith("WORKING BRANCH: ")
                         and "at a quiet point" in l], r.stdout)

    def test_p5_no_branch_step(self):
        r = self.init("--no-measure", "--no-branch")
        self.assertFalse([l for l in r.stdout.splitlines() if l.startswith(("working branch:", "checkout:"))])
        self.assertEqual(self.git("branch", "--list", "ap-main-t").strip(), "")

    def test_p5_the_start_and_cloud_pack_pass_it(self):
        self.assertIn('agent-init.sh" --no-measure --no-branch', read("bin", "agent-start.sh"))
        self.assertIn("--no-branch", read("bin", "agent-cloud-pack.sh"))

    def test_p8_a_failed_push_says_so(self):
        self.git("remote", "add", "origin", os.path.join(self.repo.base, "nowhere.git"))
        r = self.init("--no-measure")
        self.assertTrue([l for l in r.stdout.splitlines() if l.startswith("working branch: not pushed: ")], r.stdout)


class TestP7MergedIntoTheWorkingBranch(tc.CleanupCase):
    def test_a_branch_merged_into_the_working_branch_is_swept(self):
        d = self.repo.dir
        tc.git(d, "switch", "-q", "-c", "ap-main-t", "main")
        tc.git(d, "push", "-q", "origin", "ap-main-t")
        tc.git(d, "config", "--local", "auto-pipeline.workingbranch", "ap-main-t")
        tc.git(d, "switch", "-q", "-c", "feat/x")
        self.commit_in(d, "x.txt")
        tc.git(d, "push", "-q", "origin", "feat/x")
        tc.git(d, "switch", "-q", "ap-main-t")
        tc.git(d, "merge", "-q", "--no-ff", "-m", "Merge feat/x (W8)", "feat/x")
        tc.git(d, "push", "-q", "origin", "ap-main-t")
        out = self.ok("--apply")
        self.assertIn("removed: branch feat/x (local, origin)", self.lines(out), out)
        self.assertNotIn("merge it into main", out)


class TestP8LostTwin(unittest.TestCase):
    """The twin of test_risk_levels.test_this_repo_has_its_file (removed with the levels)."""

    def test_this_repo_has_its_file(self):
        tracked = subprocess.run(["git", "-C", ROOT, "ls-files", "agent_repo.conf"], capture_output=True,
                                 text=True).stdout.strip()
        self.assertEqual(tracked, "agent_repo.conf")
        core = [l for l in read("agent_repo.conf").splitlines() if l.startswith("core_paths=")][0]
        for p in ("hooks/", ".claude-plugin/", "bin/agent_conf.py", "bin/agent_owner_order.py"):
            self.assertIn(p, core.split("=", 1)[1].split(","))


class TestAfterDoneFailAndLost(unittest.TestCase):
    """Section 38 (owner order 16:4x, TELL 10b4d922): what the main manager does after DONE FAIL and LOST."""

    def test_w15(self):
        w15 = rule("W15. ", "W16. ")
        lines = w15.splitlines()
        for phrase in ("DONE FAIL → the main manager reviews the report, then sends the task manager a fix order "
                       "(where, what is seen, what is expected, evidence). Never merged, never closed silently",
                       "LOST (the watch cannot reach a machine or a pane) → wait one more sweep; still lost → tell the "
                       "owner in one line with the machine and the task",
                       "Never redispatch a LOST task on another machine by itself"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w15)
        signals = [i for i, l in enumerate(lines) if "wake the main manager" in l and "LOST" in l][0]
        self.assertTrue(lines[signals + 1].startswith("- DONE FAIL → "), lines[signals + 1])


class TestF11(unittest.TestCase):
    def test_docstring(self):
        head = read("bin", "agent_conf.py").split('"""')[1]
        self.assertNotIn("16 settings", head)


if __name__ == "__main__":
    unittest.main()
