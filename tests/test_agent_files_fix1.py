"""agent-files FIX ORDER 1 (TELL ed9db386): the reviewers' items A-H, failing tests first.

A  A repo that still TRACKS an agent file on its code branch (not moved) behaves exactly as before this task: no data
   branch is created, nothing is committed, pushed or fetched for the agent files, no kept copy is written. The data
   branch starts only once the repo is moved: no agent file tracked AND the exact ignore line "agent_completed.txt" in
   .gitignore (written only by files move and by init of this version). agent-start.sh prints ONE line while the repo
   is not moved: the agent files are still on the code branch and `agent-file.sh files move` moves them.
B  The data branch texts say the truth: any branch may be named, the production branch too; then the files live under
   .ap-data/ on that branch, an origin is needed, a commit there can start a deploy. No "refused" in them.
C  After a sync (files sync, the pull before a decision, a push retry) that brought new finished records, the estimate
   model is trained again through the estimator's own background runner (agent-file.sh est_after_done: a queue file in
   <git common dir>/agent_estimate.queue/, one detached runner whose output goes to <git dir>/agent_estimate.log); the
   command never waits for it.
D  One network timeout constant, share_net_timeout_s = 15 in bin/agent_conf.py CONSTANTS (tests may lower it with
   AGENT_SHARE_TIMEOUT under AGENT_TESTING=1). After a network call that timed out or found no remote (no answer), no
   second network call in the same command; a marker in the git dir (agent_share_offline) makes the next writes skip
   the network for share_offline_min = 5 minutes with ONE line saying so, then they try again. A refusal is an answer:
   it is not an offline.
E  In a moved repo every write of an agent file through the scripts also refreshes its kept copy
   <git common dir>/agent-files-kept/<file> (the move's dated copies stay beside it). At the start of a command: a
   working copy that is MISSING while its kept copy exists is restored, ONE line ("restored <file> from <kept path>");
   a working copy that differs from its kept copy (changed outside the scripts) is not touched, ONE line starting
   "WARNING" that names both paths.
F  files move refuses while a merge is in progress (MERGE_HEAD exists): exit 1, "nothing moved". A missing agent file
   is said as missing ("<file>: missing").
G  agent-start.sh: an invalid repo value (task_take=everyone) is said as "not valid, the default <value> is used".
H  The refusal "belongs to <owner>" also names the current git name and the way back, in one line: set git user.name
   back to the stored name, then assign the tasks to the new name.
"""

import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT  # noqa: E402
from test_agent_files import (AGENT_FILES, LOCAL, NOW, FilesCase, OldRepoCase, PairCase, data_file, git,  # noqa: E402
                              read, tip, todo_line, tracked, write)


def git_dir(path):
    return git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()


def kept(path, name):
    return os.path.join(git_dir(path), "agent-files-kept", name)


class GitSpy:
    """A `git` first on PATH that logs every call (one line of its arguments) and runs the real git."""

    def __init__(self, repo):
        self.repo = repo
        base = repo.base
        self.dir = os.path.join(base, "gitspy")
        os.makedirs(self.dir, exist_ok=True)
        self.log = os.path.join(base, "gitspy.log")
        real = subprocess.run(["which", "git"], capture_output=True, text=True).stdout.strip()
        write(os.path.join(self.dir, "git"), '#!/bin/sh\necho "$*" >> "%s"\nexec "%s" "$@"\n' % (self.log, real))
        os.chmod(os.path.join(self.dir, "git"), 0o755)

    def env(self):
        return {"PATH": self.dir + os.pathsep + self.repo._path()}   # the stubs (orca, claude) stay first after it

    def network_calls(self):
        if not os.path.exists(self.log):
            return []
        out = []
        for line in read(self.log).splitlines():
            words = line.split()
            if "push" in words or "fetch" in words or "ls-remote" in words or "pull" in words:
                out.append(line)
        return out


# ---------------------------------------------------------------- A


class TestANotMovedRepoBehavesAsBefore(OldRepoCase):
    def setUp(self):
        super().setUp()
        self.make_remote()
        self.spy = GitSpy(self.repo)

    def af_spy(self, *args):
        return self.af(*args, env=self.spy.env())

    def test_no_data_branch_and_no_network(self):
        sha = git(self.dir, "rev-parse", "HEAD").strip()
        self.af_spy("todo", "add", "t", "small", "the t task", "30")
        self.af_spy("idea", "add", "an idea")
        self.af_spy("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.af_spy("board")
        self.assertEqual(git(self.bare, "branch", "--list", "ap-data").strip(), "")
        self.assertEqual(tip(self.dir), "")
        self.assertEqual(self.spy.network_calls(), [])
        self.assertEqual(git(self.dir, "rev-parse", "HEAD").strip(), sha)
        self.assertFalse(os.path.exists(kept(self.dir, "agent_todo.txt")))

    def test_the_start_says_it_is_not_moved_and_how(self):
        out = self.repo.run("agent-start.sh").stdout
        said = [l for l in out.splitlines() if "files move" in l]
        self.assertEqual(len(said), 1, out)
        self.assertIn("code branch", said[0])

    def test_after_the_move_the_data_branch_works(self):
        self.af("files", "move")
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.af("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.assertIn("| t |", data_file(self.bare, "agent_completed.txt") or "")
        self.assertEqual([l for l in self.repo.run("agent-start.sh").stdout.splitlines() if "files move" in l], [])


class TestAFreshRepoNeedsNoMove(FilesCase):
    def test_init_of_this_version_is_moved_already(self):
        self.commit_all()
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.af("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.assertIn("| t |", data_file(self.dir, "agent_completed.txt") or "")
        self.assertEqual([l for l in self.repo.run("agent-start.sh").stdout.splitlines() if "files move" in l], [])

    def test_an_old_repo_without_the_ignore_line_is_not_moved(self):
        self.commit_all()
        path = os.path.join(self.dir, ".gitignore")
        write(path, "".join(l + "\n" for l in read(path).splitlines() if l != "agent_completed.txt"))
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.af("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.assertEqual(tip(self.dir), "")


# ---------------------------------------------------------------- B


class TestBTheTextsSayTheTruth(unittest.TestCase):
    def check(self, text, where):
        self.assertNotIn("refused", text.lower(), where)
        self.assertIn(".ap-data/", text, where)
        self.assertIn("deploy", text, where)

    def test_plugin_json(self):
        import json
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as fh:
            self.check(json.load(fh)["userConfig"]["data_branch"]["description"], "plugin.json")

    def test_the_settings_table(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import agent_conf
        row = [s for s in agent_conf.SETTINGS if s["key"] == "data_branch"][0]
        self.check(row["description"], "agent_conf.py")

    def test_agent_share_says_no_refusal_for_now(self):
        self.assertNotIn("refused for now", read(os.path.join(ROOT, "bin", "agent_share.py")))


# ---------------------------------------------------------------- C


class TestCASyncThatBringsRecordsRetrains(PairCase):
    def test_the_estimator_runner_is_started(self):
        log = os.path.join(git_dir(self.b), "agent_estimate.log")
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.af("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.assertFalse(os.path.exists(log), "King Lun's clone ran the estimator before")
        began = time.time()
        self.sync(self.b)
        self.assertLess(time.time() - began, 30)
        for _ in range(100):
            if os.path.exists(log):
                break
            time.sleep(0.1)
        self.assertTrue(os.path.exists(log), "no estimator run after a sync that brought a finished record")

    def test_a_sync_that_brings_no_record_starts_none(self):
        self.af("idea", "add", "only an idea")
        self.sync(self.b)
        time.sleep(1)
        self.assertFalse(os.path.exists(os.path.join(git_dir(self.b), "agent_estimate.log")))


# ---------------------------------------------------------------- D


class TestDAHangingRemoteCostsOneTimeout(FilesCase):
    def setUp(self):
        super().setUp()
        self.commit_all()
        self.make_remote()
        self.af("files", "set", "task_files", "ideas")
        for key in ("uploadpack", "receivepack"):
            git(self.dir, "config", "remote.origin.%s" % key, "sleep 60; git-%s" % key.replace("pack", "-pack"))
        self.env = {"AGENT_SHARE_TIMEOUT": "3"}

    def test_the_constant_is_15_seconds(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import agent_conf
        self.assertEqual(agent_conf.CONSTANTS.get("share_net_timeout_s"), 15)
        self.assertEqual(agent_conf.CONSTANTS.get("share_offline_min"), 5)

    def test_one_timeout_then_the_network_is_skipped(self):
        began = time.time()
        r1 = self.af("idea", "add", "first", env=self.env)
        self.assertLess(time.time() - began, 3 + 2, r1.stdout + r1.stderr)
        self.assertTrue(os.path.exists(os.path.join(git_dir(self.dir), "agent_share_offline")))
        began = time.time()
        r2 = self.af("idea", "add", "second", env=self.env)
        self.assertLess(time.time() - began, 2, r2.stdout + r2.stderr)
        said = [l for l in (r2.stdout + r2.stderr).splitlines() if "ap-data" in l]
        self.assertEqual(len(said), 1, r2.stdout + r2.stderr)
        self.assertIn("second", data_file(self.dir, "agent_ideas.txt") or "", "the commit must still be made")

    def test_after_five_minutes_it_tries_again(self):
        self.af("idea", "add", "first", env=self.env)
        marker = os.path.join(git_dir(self.dir), "agent_share_offline")
        old = time.time() - 6 * 60
        os.utime(marker, (old, old))
        for key in ("uploadpack", "receivepack"):
            git(self.dir, "config", "--unset", "remote.origin.%s" % key)
        self.af("idea", "add", "second", env=self.env)
        self.assertIn("second", data_file(self.bare, "agent_ideas.txt") or "")
        self.assertFalse(os.path.exists(marker))


# ---------------------------------------------------------------- E


class TestEKeptCopies(FilesCase):
    def setUp(self):
        super().setUp()
        self.commit_all()

    def test_a_write_refreshes_the_kept_copy(self):
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.assertEqual(read(kept(self.dir, "agent_todo.txt")), read(os.path.join(self.dir, "agent_todo.txt")))
        self.af("idea", "add", "an idea")
        self.assertEqual(read(kept(self.dir, "agent_ideas.txt")), read(os.path.join(self.dir, "agent_ideas.txt")))

    def test_a_missing_working_copy_is_restored(self):
        self.af("todo", "add", "t", "small", "the t task", "30")
        before = read(os.path.join(self.dir, "agent_todo.txt"))
        git(self.dir, "clean", "-fdxq", "-e", "stubbin")
        self.assertFalse(os.path.exists(os.path.join(self.dir, "agent_todo.txt")))
        r = self.af("idea", "list")
        said = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith("restored agent_todo.txt")]
        self.assertEqual(len(said), 1, r.stdout + r.stderr)
        self.assertEqual(read(os.path.join(self.dir, "agent_todo.txt")), before)

    def test_a_copy_changed_outside_is_left_alone_with_one_warning(self):
        self.af("todo", "add", "t", "small", "the t task", "30")
        with open(os.path.join(self.dir, "agent_todo.txt"), "a") as fh:
            fh.write("by hand | small | edited outside | opened 2026-11-26 09:00 | by main\n")
        changed = read(os.path.join(self.dir, "agent_todo.txt"))
        r = self.af("idea", "list")
        said = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith("WARNING")]
        self.assertEqual(len(said), 1, r.stdout + r.stderr)
        self.assertIn(os.path.join(self.dir, "agent_todo.txt"), said[0])
        self.assertIn(kept(self.dir, "agent_todo.txt"), said[0])
        self.assertEqual(read(os.path.join(self.dir, "agent_todo.txt")), changed)


# ---------------------------------------------------------------- F


class TestFTheMoveRefusesAMergeAndSaysMissing(OldRepoCase):
    def test_a_merge_in_progress_is_refused(self):
        git(self.dir, "checkout", "-q", "-b", "side")
        write(os.path.join(self.dir, "seed.txt"), "side\n")
        git(self.dir, "commit", "-qam", "side")
        git(self.dir, "checkout", "-q", "-")
        write(os.path.join(self.dir, "seed.txt"), "main\n")
        git(self.dir, "commit", "-qam", "main")
        subprocess.run(["git", "-C", self.dir, "merge", "-q", "side"], capture_output=True)
        self.assertTrue(os.path.exists(os.path.join(git_dir(self.dir), "MERGE_HEAD")))
        sha = git(self.dir, "rev-parse", "HEAD").strip()
        r = self.af("files", "move", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("nothing moved", r.stdout + r.stderr)
        self.assertEqual(git(self.dir, "rev-parse", "HEAD").strip(), sha)
        self.assertTrue(tracked(self.dir, "agent_todo.txt"))

    def test_a_merge_where_only_agent_files_conflict_is_refused(self):
        # the reviewer's case: the move must not commit such a merge under its own message
        git(self.dir, "checkout", "-q", "-b", "side")
        with open(os.path.join(self.dir, "agent_todo.txt"), "a") as fh:
            fh.write(todo_line("side-task") + "\n")
        git(self.dir, "commit", "-qam", "side todo")
        git(self.dir, "checkout", "-q", "-")
        with open(os.path.join(self.dir, "agent_todo.txt"), "a") as fh:
            fh.write(todo_line("main-task") + "\n")
        git(self.dir, "commit", "-qam", "main todo")
        subprocess.run(["git", "-C", self.dir, "merge", "-q", "side"], capture_output=True)
        self.assertTrue(os.path.exists(os.path.join(git_dir(self.dir), "MERGE_HEAD")))
        sha = git(self.dir, "rev-parse", "HEAD").strip()
        r = self.af("files", "move", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("nothing moved", r.stdout + r.stderr)
        self.assertEqual(git(self.dir, "rev-parse", "HEAD").strip(), sha)
        self.assertTrue(os.path.exists(os.path.join(git_dir(self.dir), "MERGE_HEAD")))

    def test_a_missing_file_is_said_missing(self):
        git(self.dir, "rm", "-q", "--cached", "agent_estimate.txt")
        os.remove(os.path.join(self.dir, "agent_estimate.txt"))
        git(self.dir, "commit", "-qm", "no estimate")
        out = self.af("files", "move").stdout
        line = [l for l in out.splitlines() if l.startswith("agent_estimate.txt:")][0]
        self.assertIn("missing", line)


# ---------------------------------------------------------------- G


class TestGAnInvalidRepoValueIsSaid(FilesCase):
    def test_the_start_names_the_default(self):
        self.commit_all()
        path = os.path.join(self.dir, "agent_repo.conf")
        write(path, read(path) + "task_take=everyone\n")
        out = self.repo.run("agent-start.sh").stdout
        said = [l for l in out.splitlines() if "task_take" in l]
        self.assertEqual(len(said), 1, out)
        self.assertIn("not valid, the default owner is used", said[0])
        self.assertNotIn("the repo value counts", said[0])


# ---------------------------------------------------------------- H


class TestHTheWayBackAfterANameChange(PairCase):
    def test_the_refusal_names_both_names_and_the_way_back(self):
        self.put_line(todo_line("t", owner="Maverick"))
        git(self.dir, "config", "user.name", "Maverick Lee")
        r = self.af("todo", "stage", "t", "brief", ok=False)
        self.assertEqual(r.returncode, 1)
        line = [l for l in r.stderr.splitlines() if "belongs to Maverick" in l]
        self.assertEqual(len(line), 1, r.stderr)
        self.assertIn("Maverick Lee", line[0])
        self.assertIn("git user.name", line[0])
        self.assertIn("assign", line[0])


if __name__ == "__main__":
    unittest.main()
