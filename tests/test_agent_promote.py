"""Tests of agent-promote, one class per feature."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402
import atexit  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import test_agent_checks as tcr  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))


# tests that keep the real agent-file.sh command line for check / checks gate (one per verb and exit path;
# the gate also runs for real inside every agent-promote.sh --task run)
REAL_SHELL = {
    "TestW1PromoteSeesTheTasksLines.test_lines_in_the_task_worktree_pass_the_direct_gate",
    "TestA10FastLaneProduction.test_the_main_managers_gate_brings_the_lines_promote_needs",
    "TestS4GateSaysIt.test_s4_the_gate_refuses_a_branch_cut_from_the_working_branch",
}
# tests that keep the real agent-promote.sh command line for each way it runs and each exit code
# (publish 0 and 1, the direct path 0 and 1, sync); a run with an env of its own, or in a repo that
# has a release build (its output goes to the runner's own stdout), is always real
PROMOTE_REAL = {
    "TestPromote.test_green_and_verified_goes_to_production",
    "TestPromote.test_not_verified_is_refused",
    "TestSync.test_sync_merges_production_in_and_pushes",
    "TestF1DirectPath.test_the_stored_words",
    "TestDirectToProduction.test_a_conflict_is_refused_and_cleaned_up",
}


class PromoteCase(ScriptCase):
    script = "agent-promote.sh"

    # test-slim: the Python of agent-promote.sh (a bare exec of agent_promote.py) runs in this process
    def pr(self, *args, **kw):
        key = "%s.%s" % (type(self).__name__, self._testMethodName)
        if (key in PROMOTE_REAL or kw.get("env") or set(kw) - {"env", "cwd"}
                or os.path.exists(os.path.join(self.repo.dir, "bin", "agent-release.sh"))):
            return self.repo.run("agent-promote.sh", *args, **kw)
        return self.promote_in_process(args, kw)

    def promote_in_process(self, args, kw):
        """agent_promote.main with this repo's own plugin modules: what it imports (agent_conf, agent_nightly,
        agent_state, agent_checks) is loaded from this test's plugin copy, never from another test's folder,
        and the process's modules and sys.path are put back afterwards (as the watch tests do)."""
        mine = lambda k: k.startswith("agent_") and "__inproc_" not in k
        saved = {k: sys.modules.pop(k) for k in [k for k in sys.modules if mine(k)]}
        before_path = list(sys.path)
        sys.path.insert(0, self.repo.plugin_bin)
        try:
            return self.repo.run_py("agent_promote", *args, **kw)
        finally:
            sys.path[:] = before_path
            for k in [k for k in sys.modules if mine(k)]:
                sys.modules.pop(k, None)
            sys.modules.update(saved)

    # test-slim: check and checks gate/gather are Python (agent_checks.py): run in this process with the roots
    # and clock agent-file.sh hands over; the tests named in REAL_SHELL keep the real command line.
    def af(self, *args, **kw):
        cmd = None
        if args[:1] == ("check",):
            cmd, rest = "check", args[1:]
        elif args[:2] in (("checks", "gate"), ("checks", "gather")):
            cmd, rest = args[1], args[2:]
        env = kw.get("env") or {}
        key = "%s.%s" % (type(self).__name__, self._testMethodName)
        if cmd is None or key in REAL_SHELL or env or set(kw) - {"cwd"}:
            return self.repo.run("agent-file.sh", *args, **kw)
        merged = self.repo._env(env)
        cwd = kw.get("cwd") or self.repo.cwd
        start = os.path.realpath(merged.get("CLAUDE_PROJECT_DIR") or cwd)
        roots = self.__dict__.setdefault("_roots", {})          # the main folder and top of a folder stay as they are
        if start not in roots:
            lst = subprocess.run(["git", "-C", start, "worktree", "list", "--porcelain"], capture_output=True,
                                 text=True).stdout.splitlines()
            top = subprocess.run(["git", "-C", start, "rev-parse", "--show-toplevel"], capture_output=True,
                                 text=True).stdout.strip() or start
            roots[start] = (([l.split(" ", 1)[1] for l in lst if l.startswith("worktree ")] or [start])[0], top)
        root, top = roots[start]
        now = merged.get("AGENT_FAKE_NOW") or time.strftime("%Y-%m-%d %H:%M")
        tcr.TestGate.share_level_runs(self)
        return self.repo.run_py("agent_checks", "agent_checks.py", root, top, now, cmd, *rest, env=env, cwd=cwd)

    def git(self, *args, cwd=None):
        return subprocess.run(["git", "-C", cwd or self.repo.dir] + list(args), check=True, capture_output=True,
                              text=True).stdout.strip()

    def put(self, rel, body, cwd=None):
        full = os.path.join(cwd or self.repo.dir, rel)
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w") as fh:
            fh.write(body)

    # test-slim: the set-up below (origin, working branch, one merge commit, "verified") is built once per
    # process and a test gets a copy; the origin path is the one absolute path in it (set again).
    # Rebuilt after a minute, like the seeded template, so no commit in it is older.
    _SNAP = {}

    def setUp(self):
        super().setUp()
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        self.wb = "ap-main-t"   # section 34: per person; the fixture's git user.name is t
        self.origin = os.path.join(self.repo.base, "origin.git")
        snap = self._SNAP.get("dir")
        if snap and time.time() - self._SNAP["made"] < 60 and not os.environ.get("AGENT_TEST_NO_TEMPLATE"):
            shutil.rmtree(self.repo.dir)
            shutil.copytree(os.path.join(snap, "project"), self.repo.dir, symlinks=True)
            shutil.copytree(os.path.join(snap, "origin.git"), self.origin, symlinks=True)
            shutil.copy2(os.path.join(snap, "agent-owner-order.sh"),
                         os.path.join(self.repo.plugin_bin, "agent-owner-order.sh"))
            self.git("remote", "set-url", "origin", self.origin)
            self.tip = self._SNAP["tip"]
            return
        self.git("branch", "-M", "main")
        subprocess.run(["git", "init", "-q", "--bare", self.origin], check=True, capture_output=True)
        self.git("remote", "add", "origin", self.origin)
        self.git("push", "-q", "-u", "origin", "main")
        self.git("switch", "-q", "-c", self.wb)                 # section 29: the main checkout is on it
        self.git("config", "--local", "auto-pipeline.workingbranch", self.wb)   # stored by init (section 37 F10)
        self.commit_wb({"src/a.py": "x = 2\n"}, "Merge feat-a (W8)")
        self.verified(True)
        if not os.environ.get("AGENT_TEST_NO_TEMPLATE"):
            if self._SNAP.get("dir"):
                shutil.rmtree(self._SNAP["dir"], ignore_errors=True)
            snap = tempfile.mkdtemp(prefix="promote_fixture_")
            atexit.register(shutil.rmtree, snap, True)
            shutil.copytree(self.repo.dir, os.path.join(snap, "project"), symlinks=True)
            shutil.copytree(self.origin, os.path.join(snap, "origin.git"), symlinks=True)
            shutil.copy2(os.path.join(self.repo.plugin_bin, "agent-owner-order.sh"), snap)
            self._SNAP.update(dir=snap, made=time.time(), tip=self.tip)

    def commit_wb(self, files, msg):
        for rel, body in files.items():
            self.put(rel, body)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        self.git("push", "-q", "-u", "origin", self.wb)
        self.tip = self.git("rev-parse", self.wb)

    def verified(self, ok):
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho %s\nexit %d\n"
                                   % ("'OWNER ORDER verified ~/.claude/projects/-r/s1.jsonl 2026-11-26 08:40'" if ok
                                      else "'not found'", 0 if ok else 1))

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

    # test-slim: `todo add --target production` (the owner's words verified and stored) is real the first time per
    # process for a given shape; the next run in the very same start state (empty todo file, no stored words, the
    # same verifier stub, the same arguments but the task name) replays what the first one wrote: the todo line
    # and the stored words, with the minute of now. The tests of todo add itself call the real command.
    _ADD = {}

    def todo_add_production(self, task, quote, means):
        d = self.repo.dir
        gd = self.git("rev-parse", "--path-format=absolute", "--git-common-dir")
        todo, words = os.path.join(d, "agent_todo.txt"), os.path.join(gd, "agent_owner_words.json")
        with open(os.path.join(self.repo.plugin_bin, "agent-owner-order.sh")) as fh:
            stub = fh.read()
        with open(todo) as fh:
            todo_before = fh.read()
        nm = lambda text: text.replace(task, "\0TASK\0")
        fresh = todo_before == "" and not os.path.exists(words) and self.git("status", "--short") == ""
        key = (nm(quote), nm(means), stub, os.environ.get("AGENT_TEST_NO_TEMPLATE"))
        now = time.strftime("%Y-%m-%d %H:%M")
        rec = self._ADD.get(key)
        if rec and task not in (rec["todo"] + rec["words"]).replace("\0TASK\0", "").replace("\0NOW\0", "") \
                and fresh:
            with open(todo, "w") as fh:
                fh.write(rec["todo"].replace("\0TASK\0", task).replace("\0NOW\0", now))
            with open(words, "w") as fh:
                fh.write(rec["words"].replace("\0TASK\0", task).replace("\0NOW\0", now))
            return subprocess.CompletedProcess([], 0, rec["stdout"].replace("\0TASK\0", task), "")
        r = self.repo.run("agent-file.sh", "todo", "add", task, "small", "publish " + task, "10",
                          "--target", "production", "--owner-quote", quote, "--means", means)
        if r.returncode == 0 and fresh and key not in self._ADD:
            with open(todo) as fh:
                todo_after = fh.read()
            with open(words) as fh:
                words_after = fh.read()
            import re
            m = re.search(r"opened (\d{4}-\d\d-\d\d \d\d:\d\d)", todo_after)
            if m and todo_after.count(m.group(1)) == 1 and words_after.count(m.group(1)) <= 1 and r.stderr == "" \
                    and self.git("status", "--short").split() == ["M", "agent_todo.txt"]:
                self._ADD[key] = {"todo": nm(todo_after).replace(m.group(1), "\0NOW\0"),
                                  "words": nm(words_after).replace(m.group(1), "\0NOW\0"),
                                  "stdout": nm(r.stdout)}
        return r

    def ready_direct(self, task, branch, quote=None):
        """Section 44 F1: dispatch stores the owner's words with the target; the main manager's reviewer passed."""
        import time as _t
        sys.path.insert(0, HERE)
        import test_agent_checks as _tcr
        quote = quote or "%s can go live straight after done" % task          # approval-design: his own words
        r = self.todo_add_production(task, quote, "publish %s to production" % task)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        _tcr.main_launched(self.repo.dir, task)                      # G8: within the task instance (now)
        self.git("fetch", "-q", "origin")
        sha = self.git("rev-parse", "origin/" + branch)
        for block in ("PR REVIEW", "DIFF SCAN", "BUILD", "RELATED TESTS", "MODULE TESTS", "GUARD TESTS",
                      "CORE REVIEW", "EXAMPLES TEST"):
            r = self.af("check", task, block, "pass", "--by", task + " Reviewer",
                              "--evidence", "ok", "--commit", sha)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def promote(self, *extra):
        return self.pr("--owner-quote", "yes ship it to production",
                             "--means", "publish the working branch to production", *extra)


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
        return self.pr("--task", "feat-p", "--branch", branch, *extra)

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
                          "--owner-quote", "feat-p can go live after done", "--means", "publish feat-p to production")
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
        r = self.pr("--task", "feat-c", "--branch", b)
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
        r = self.pr("--sync")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.splitlines()[0].startswith("sync: main merged into %s (" % self.wb), r.stdout)
        self.git("fetch", "-q", "origin")
        self.assertEqual(subprocess.run(["git", "-C", self.repo.dir, "merge-base", "--is-ancestor", "origin/main",
                                         "origin/" + self.wb]).returncode, 0)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), self.wb)

    def test_sync_when_already_in(self):
        r = self.pr("--sync")
        self.assertEqual(r.stdout.strip(), "sync: %s already has main" % self.wb)

    def test_sync_waits_on_a_dirty_checkout(self):
        self.production_moves()
        self.put("src/a.py", "half done\n")
        r = self.pr("--sync")
        self.assertTrue(r.stdout.strip().startswith("sync waits: "), r.stdout)
        with open(os.path.join(self.repo.dir, "src", "a.py")) as fh:
            self.assertEqual(fh.read(), "half done\n")

    def test_a_publish_syncs_first(self):
        self.production_moves()
        self.green()                                   # green on the old tip: after the sync it is not the tip
        r = self.promote()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("sync: main merged into %s" % self.wb, r.stdout)


class TestG4PublishWords(PromoteCase):
    def test_words_without_a_means_are_refused(self):
        # approval-design (section 53 A3): the main manager writes what it read from his words
        r = self.repo.run("agent-file.sh", "todo", "add", "p", "small", "x", "10", "--target", "production",
                          "--owner-quote", "p can go straight to production after done")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("--means", r.stdout + r.stderr)
        self.assertNotIn("type exactly", r.stdout + r.stderr)

    def test_stored_words_end_with_their_task(self):
        r = self.repo.run("agent-file.sh", "todo", "add", "p", "small", "x", "10", "--target", "production",
                          "--owner-quote", "p can go straight to production after done", "--means", "publish p to production")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.repo.run("agent-file.sh", "todo", "done", "p", "--work", "5", "--type", "script", "--lane", "fast")
        with open(os.path.join(self.repo.dir, "agent_todo.txt"), "a") as fh:        # by hand, the same name
            fh.write("p | small | x | est 10m | opened 2026-11-25 10:00 | target production\n")
        self.git("switch", "-q", "-c", "p", "origin/main")
        self.put("p.txt", "p\n")
        self.git("add", "p.txt")                                  # the hand line stays local
        self.git("commit", "-q", "-m", "p")
        self.git("push", "-q", "-u", "origin", "p")
        self.git("switch", "-q", self.wb)
        r = self.pr("--task", "p", "--branch", "p")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no owner words stored for p", r.stdout + r.stderr)


ROOT = os.path.dirname(HERE)


BIN = os.path.join(ROOT, "bin")


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def minute(delta_s=0):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() + delta_s))


class TestF1DirectPath(PromoteCase):
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
        r = self.pr("--task", b, "--branch", b, "--owner-quote", "please fix the footer typo")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("the owner's words come from the task (todo add --target production --owner-quote), "
                      "not from promote", r.stdout + r.stderr)

    def test_not_a_production_task_is_refused(self):
        b = self.branch_from_main("feat-w")
        self.repo.run("agent-file.sh", "todo", "add", b, "small", "x", "10")
        before = self.git("rev-parse", "origin/main")
        r = self.pr("--task", b, "--branch", b)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("%s is not a production task (todo add --target production)" % b, r.stdout + r.stderr)
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.git("rev-parse", "origin/main"), before)

    def test_target_production_needs_verified_words(self):
        r = self.repo.run("agent-file.sh", "todo", "add", "feat-v", "small", "x", "10", "--target", "production")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.verified(False)
        r = self.repo.run("agent-file.sh", "todo", "add", "feat-v", "small", "x", "10", "--target", "production",
                          "--owner-quote", "feat-v can go live after done", "--means", "publish feat-v to production")
        self.assertEqual(r.returncode, 1, r.stdout)
        with open(os.path.join(self.repo.dir, "agent_todo.txt")) as fh:
            self.assertNotIn("feat-v", fh.read())

    def test_no_stored_words_is_refused(self):
        b = self.branch_from_main("feat-s")
        with open(os.path.join(self.repo.dir, "agent_todo.txt"), "a") as fh:
            fh.write("%s | small | x | est 10m | opened %s | target production\n" % (b, minute(-600)))
        r = self.pr("--task", b, "--branch", b)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no owner words stored for %s" % b, r.stdout + r.stderr)

    def test_the_gate_runs_first(self):
        b = self.branch_from_main("feat-g")
        r = self.repo.run("agent-file.sh", "todo", "add", b, "small", "x", "10", "--target", "production",
                          "--owner-quote", "%s can go live after done" % b, "--means", "publish %s to production" % b)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        before = self.git("rev-parse", "origin/main")
        r = self.pr("--task", b, "--branch", b)     # no reviewer, no check lines
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("GATE REFUSED", r.stdout)
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.git("rev-parse", "origin/main"), before)

    def test_the_stored_words(self):
        b = self.branch_from_main("feat-k")
        self.ready_direct(b, b)
        gd = self.git("rev-parse", "--path-format=absolute", "--git-common-dir")
        with open(os.path.join(gd, "agent_owner_words.json")) as fh:
            rec = json.load(fh)[b]["publish"]
        self.assertEqual(rec["quote"], "%s can go live straight after done" % b)
        self.assertEqual(rec["means"], "publish %s to production" % b)
        r = self.pr("--task", b, "--branch", b)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # approval-design (section 53 A8): promote prints the stored pair
        self.assertIn('OWNER WORDS publish: "%s can go live straight after done" (typed 2026-11-26 08:40) read as: '
                      'publish %s to production' % (b, b), r.stdout.splitlines())

    def test_an_old_record_without_means_is_refused(self):
        b = self.branch_from_main("feat-o")
        self.ready_direct(b, b)
        gd = self.git("rev-parse", "--path-format=absolute", "--git-common-dir")
        with open(os.path.join(gd, "agent_owner_words.json"), "w") as fh:
            json.dump({b: {"quote": "yes, publish %s to production" % b, "time": "2026-11-25 10:00", "verified": True}}, fh)
        before = self.git("rev-parse", "origin/main")
        r = self.pr("--task", b, "--branch", b)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no owner words stored for %s" % b, r.stdout + r.stderr)
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.git("rev-parse", "origin/main"), before)

    def test_means_and_question_at_promote_task_are_refused(self):
        b = self.branch_from_main("feat-m")
        for extra in (("--means", "publish it"), ("--question", "1. publish? A. yes")):
            with self.subTest(extra=extra):
                r = self.pr("--task", b, "--branch", b, *extra)
                self.assertNotEqual(r.returncode, 0, r.stdout)


class TestF7AgentFilesNeverBlock(PromoteCase):
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
        r = self.pr("--sync")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.splitlines()[0].startswith("sync: main merged into %s (" % self.wb), r.stdout)


class TestF8PushTheCheckedSha(PromoteCase):
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
        r = self.pr("--owner-quote", "yes ship it to production",
                          "--means", "publish the working branch to production",
                          env={"PYTHONPATH": site, "F8_BIN": os.path.join(self.repo.plugin, "bin"),
                               "F8_REPO": self.repo.dir})
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.git("rev-parse", "origin/main"), checked, r.stdout + r.stderr)


class TestF9ReleaseFromThePublishedCommit(PromoteCase):
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


class TestF12OnlyItsOwnMerge(PromoteCase):
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
        r = self.pr("--sync")
        self.assertIn("a merge is in progress in", r.stdout)
        self.assertIn("(not started by this run)", r.stdout)
        self.assertTrue(os.path.exists(merge_head), "someone else's merge was aborted")


class TestF14StaleWorktrees(PromoteCase):
    def test_a_dead_runs_worktree_is_pruned(self):
        gd = self.git("rev-parse", "--path-format=absolute", "--git-common-dir")
        stale = os.path.join(gd, "agent_promote_wt_999999")
        self.git("worktree", "add", "-q", "--detach", stale, "main")
        self.pr("--sync")
        self.assertFalse(os.path.exists(stale))


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


class TestA5PromoteUsage(unittest.TestCase):
    def test_usage(self):
        head = read("bin", "agent-promote.sh").split("\nset ")[0]
        line = [l for l in head.splitlines() if "--task" in l][0]
        self.assertNotIn("--owner-quote", line)


class TestW1PromoteSeesTheTasksLines(PromoteCase):
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
                          "--owner-quote", "p1 can go live after done", "--means", "publish p1 to production")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.repo.dir, "agent_worktree.txt"), "a") as fh:
            fh.write("%s | p1 | final | since %s\n" % (wt, _t.strftime("%Y-%m-%d %H:%M")))
        tcr.main_launched(self.repo.dir, "p1")                       # G8: within the task instance (now)
        head = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        for block in ("PR REVIEW", "DIFF SCAN", "BUILD", "RELATED TESTS", "MODULE TESTS", "GUARD TESTS", "CORE REVIEW",
                      "EXAMPLES TEST"):
            r = self.af("check", "p1", block, "pass", "--by", "p1 Review", "--evidence", "ok",
                              "--commit", head, cwd=wt)                     # written in the task's worktree
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.pr("--task", "p1", "--branch", "p1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_results_file_for_a_remote_task(self):
        self.assertIn("--results <file>", read("bin", "agent-promote.sh").split("\nset ")[0])
        prod = [l for l in read("skills", "merge", "SKILL.md").splitlines() if "agent-promote.sh --task" in l][0]
        self.assertIn("--results", prod)


class TestA10FastLaneProduction(PromoteCase):
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
                          "--owner-quote", "the urgent fix can go live after done", "--means", "publish u1 to production")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        head = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        for block in ("DIFF SCAN", "BUILD", "RELATED TESTS", "MODULE TESTS", "GUARD TESTS", "EXAMPLES TEST"):
            self.af("check", "u1", block, "pass", "--by", "u1 Deputy", "--evidence", "ok",
                          "--commit", head, cwd=wt)                     # the deputy's lines, in its worktree
        tcr.main_launched(self.repo.dir, "u1")
        for block in ("PR REVIEW", "CORE REVIEW"):
            self.af("check", "u1", block, "pass", "--by", "u1 Review", "--evidence", "ok",
                          "--commit", head)                              # the reviewer, from the main checkout
        r = self.af("checks", "gate", "u1", "--dir", wt, "--branch", "u1",
                          "--base", "origin/main")                       # /merge step 4
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.pr("--task", "u1", "--branch", "u1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_demo_has_the_third_walk(self):
        self.assertIn("walk 3: an urgent small production task", read("tests", "check_blocks_demo.sh"))


class TestG10PublishWords(PromoteCase):
    """approval-design (section 53): the tool reads no meaning. It verifies his words and stores them with what the
    main manager read; whether "publish it next week" is a yes now is the main manager's reading (the R8 cases)."""

    def add(self, words, *extra):
        return self.repo.run("agent-file.sh", "todo", "add", "p", "small", "x", "10", "--target", "production",
                             "--owner-quote", words, *extra)

    def test_no_means_is_refused_whatever_the_words(self):
        for words in ("2. need to publish direct after done", "这个功能做完直接发布到正式环境", "fix the total and publish it"):
            with self.subTest(words=words):
                r = self.add(words)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("--means", r.stdout + r.stderr)

    def test_natural_words_with_the_means_are_stored(self):
        for words in ("2. need to publish direct after done", "这个功能做完直接发布到正式环境", "after done direct merge"):
            with self.subTest(words=words):
                r = self.add(words, "--means", "publish p to production")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.repo.run("agent-file.sh", "todo", "drop", "p", "next word")

    def test_the_sentence_helpers_are_gone(self):
        for name in ("publish_sentence", "skip_sentence", "approval_key"):
            with self.subTest(name=name):
                self.assertNotIn("def %s(" % name, read("bin", "agent_conf.py"))


class TestApprovalPublish(PromoteCase):
    """Section 53 A3, A8: the working branch publish takes --means and prints the pair."""

    def test_no_means_is_refused_and_nothing_moves(self):
        self.green()
        r = self.pr("--owner-quote", "yes ship it to production")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("--means", r.stdout + r.stderr)
        self.assertNotEqual(self.git("rev-parse", "origin/main"), self.tip)

    def test_the_pair_is_printed(self):
        self.green()
        r = self.promote()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('OWNER WORDS publish %s: "yes ship it to production" (typed 2026-11-26 08:40) read as: '
                      'publish the working branch to production' % self.wb, r.stdout.splitlines())

    def test_a_short_answer_goes_to_verify_with_its_question(self):
        log = os.path.join(self.repo.base, "verify.log")
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\nprintf '%%s\\n' \"$@\" > %s\n"
                                   "echo 'OWNER ORDER verified ~/.claude/projects/-r/s1.jsonl 2026-11-26 08:40'\n" % log)
        self.green()
        q = "1. Publish the working branch now? A. yes B. wait"
        r = self.pr("--owner-quote", "1A", "--question", q,
                          "--means", "publish the working branch to production")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(log) as fh:
            args = fh.read().split("\n")
        self.assertEqual(args[args.index("--question") + 1], q)
        self.assertIn('| question: "%s"' % q, r.stdout)


class TestPublishRecord(PromoteCase):
    """FIX ORDER 1 R4 (TELL cdacc0c5): the words that moved production stay on record in agent_state.txt."""

    def state(self):
        path = os.path.join(self.repo.dir, "agent_state.txt")
        return open(path, encoding="utf-8").read() if os.path.exists(path) else ""

    def test_r4_the_working_branch_publish_is_stored(self):
        self.green()
        r = self.promote()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        want = ('OWNER WORDS publish %s -> main %s: "yes ship it to production" (typed 2026-11-26 08:40) read as: '
                'publish the working branch to production | ' % (self.wb, self.tip[:7]))
        self.assertTrue(any(l.startswith(want) for l in self.state().splitlines()), self.state())

    def test_r4_a_refused_publish_stores_nothing(self):
        self.green(result="red")
        self.assertEqual(self.promote().returncode, 1)
        self.assertNotIn("OWNER WORDS", self.state())

    def test_r4_a_direct_publish_is_stored_too(self):
        # the task's own record ends at todo done; this line stays
        b = TestF1DirectPath.branch_from_main(self, "feat-r")
        self.ready_direct(b, b)
        r = self.pr("--task", b, "--branch", b)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.git("fetch", "-q", "origin")
        sha = self.git("rev-parse", "origin/main")[:7]
        want = 'OWNER WORDS publish %s -> main %s: "%s can go live straight after done" (typed 2026-11-26 08:40) ' \
               'read as: publish %s to production | ' % (b, sha, b, b)
        self.assertTrue(any(l.startswith(want) for l in self.state().splitlines()), self.state())

    def test_r3_a_relayed_publish_is_verified_in_the_sender_repo(self):
        log = os.path.join(self.repo.base, "verify.log")
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\nprintf '%%s\\n' \"$@\" > %s\n"
                                   "echo 'OWNER ORDER verified ~/.claude/projects/-r/s1.jsonl 2026-11-26 08:40'\n" % log)
        sys.path.insert(0, HERE)
        import test_agent_checks as _tcr
        sender = _tcr.sender_repo(self.repo.base)          # FIX ORDER 2 S3: a repo with a main manager lock
        self.green()
        r = self.promote("--relayed-from", sender)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(log) as fh:
            args = fh.read().split("\n")
        self.assertEqual(args[args.index("--repo") + 1], sender)
        self.assertIn("| relayed from %s" % sender, r.stdout)


class TestS4GateSaysIt(PromoteCase):
    """FIX ORDER 2 S4: after todo target, a branch that still carries working-branch commits is refused by the gate
    with the same line promote prints."""

    def test_s4_the_gate_refuses_a_branch_cut_from_the_working_branch(self):
        self.git("switch", "-q", "-c", "feat-l", self.wb)
        self.put("src/footer.py", "f = 2\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "fix the footer")
        self.git("push", "-q", "-u", "origin", "feat-l")
        self.git("switch", "-q", self.wb)
        self.ready_direct("feat-l", "feat-l")
        wt = os.path.join(self.repo.base, "wt-feat-l")
        self.git("worktree", "add", "-q", wt, "feat-l")
        r = self.af("checks", "gate", "feat-l", "--dir", wt, "--branch", "feat-l", "--base", "origin/main")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("feat-l carries commits of %s that are not in main" % self.wb, r.stdout)
        self.assertNotIn("GATE PASS", r.stdout)

    def test_s4_a_branch_from_production_still_passes(self):
        b = TestF1DirectPath.branch_from_main(self, "feat-n")
        self.ready_direct(b, b)
        wt = os.path.join(self.repo.base, "wt-feat-n")
        self.git("worktree", "add", "-q", wt, b)
        r = self.af("checks", "gate", b, "--dir", wt, "--branch", b, "--base", "origin/main")
        self.assertNotIn("carries commits of", r.stdout)


class TestT5NothingToPublish(PromoteCase):
    """TELL 60aacfae T5: a branch with no commit of its own on top of production publishes nothing, so the gate and
    promote refuse it (a cherry-pick that failed silently must not look published)."""

    def empty_branch(self, name):
        self.git("fetch", "-q", "origin")
        self.git("branch", "-q", name, "origin/main")
        self.git("push", "-q", "-u", "origin", name)
        return name

    def state(self):
        path = os.path.join(self.repo.dir, "agent_state.txt")
        return open(path, encoding="utf-8").read() if os.path.exists(path) else ""

    def test_t5_promote_refuses_and_stores_nothing(self):
        b = self.empty_branch("feat-e")
        self.ready_direct(b, b)
        before = self.git("rev-parse", "origin/main")
        r = self.pr("--task", b, "--branch", b)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("nothing to publish: feat-e has no commit on top of main", r.stdout + r.stderr)
        self.assertNotIn("promote: feat-e -> main", r.stdout)
        self.assertNotIn("OWNER WORDS publish feat-e ->", self.state())
        self.git("fetch", "-q", "origin")
        self.assertEqual(self.git("rev-parse", "origin/main"), before)

    def test_t5_the_gate_refuses_it_too(self):
        b = self.empty_branch("feat-f")
        self.ready_direct(b, b)
        wt = os.path.join(self.repo.base, "wt-feat-f")
        self.git("worktree", "add", "-q", wt, b)
        r = self.af("checks", "gate", b, "--dir", wt, "--branch", b, "--base", "origin/main")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("nothing to publish: feat-f has no commit on top of", r.stdout)
        self.assertNotIn("GATE PASS", r.stdout)


class TestG15Gather(PromoteCase):
    def test_a_missing_worktree_is_named(self):
        self.git("fetch", "-q", "origin")
        self.git("switch", "-q", "-c", "g1", "origin/main")
        self.put("g.txt", "g\n")
        self.git("add", "g.txt")
        self.git("commit", "-q", "-m", "g1")
        self.git("push", "-q", "-u", "origin", "g1")
        self.git("switch", "-q", self.wb)
        self.ready_direct("g1", "g1")
        with open(os.path.join(self.repo.dir, "agent_worktree.txt"), "a") as fh:
            fh.write("/no/such/folder | g1 | final | since 2026-11-25 19:00\n")
        r = self.pr("--task", "g1", "--branch", "g1")
        self.assertIn("gather: skipped /no/such/folder: missing", r.stdout)


class TestP1P2P3P6Promote(PromoteCase):
    def task_from(self, base, name="feat-p", body="t = 1\n"):
        self.git("switch", "-q", "-c", name, base)
        self.put("src/total.py", body)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "work on " + name)
        self.git("push", "-q", "-u", "origin", name)
        self.git("switch", "-q", self.wb)
        return name

    def direct(self, branch):
        self.ready_direct(branch, branch)                            # section 44 F1
        return self.pr("--task", branch, "--branch", branch)

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


class TestG6ReleaseWhileProductionIsCheckedOut(PromoteCase):
    def test_the_release_says_why_it_did_not_run(self):
        log = os.path.join(self.repo.base, "release.log")
        self.put("bin/agent-release.sh", "#!/usr/bin/env bash\necho ran > %s\n" % log)
        os.chmod(os.path.join(self.repo.dir, "bin", "agent-release.sh"), 0o755)
        self.commit_wb({}, "release build")
        self.git("push", "-q", "origin", "%s:main" % self.wb)
        self.git("switch", "-q", "main")                         # not switched yet (section 33)
        self.git("merge", "-q", "--ff-only", "origin/main")
        self.git("switch", "-q", "-c", "feat-r", "origin/main")
        self.put("src/r.py", "r = 1\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "urgent")
        self.git("push", "-q", "-u", "origin", "feat-r")
        self.git("switch", "-q", "main")
        self.ready_direct("feat-r", "feat-r")                        # section 44 F1
        r = self.pr("--task", "feat-r", "--branch", "feat-r")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertFalse(os.path.exists(log))
        self.assertIn("release: not run: local main is checked out in %s; switch that checkout to the working branch "
                      "(section 33 of requirements/check-blocks.md), then run bin/agent-release.sh --push" % os.path.realpath(self.repo.dir),
                      [l.replace(self.repo.dir, os.path.realpath(self.repo.dir)) for l in r.stdout.splitlines()])
