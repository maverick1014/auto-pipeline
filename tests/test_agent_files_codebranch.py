"""agent-files: the data branch on a branch that holds code, e.g. "main" (owner 2026-11-26, TELL 50d02f90).

"if the user want it be main also can ya". The local working copies (git-ignored in the checkout) and the copies on
that branch must never fight: a pull, a merge of production into the working branch, a new worktree, a second clone.

Layout on a code branch (bin/agent_share.py, the one place function):
  - the files in git live under the folder ".ap-data/" of that branch (".ap-data/agent_completed.txt", ...), never at
    the root, so a merge of that branch never touches the git-ignored working copies at the root of a checkout
  - a data commit is built on the remote tip (origin/<branch>, fetched): the remote tip's tree with only ".ap-data/"
    replaced. The local branch (refs/heads/<branch>) is never moved and no checkout's HEAD or index moves, so a code
    commit that is not pushed yet is never published by a data push. The commit not pushed yet is kept under
    refs/auto-pipeline/ and pushed by the next write ("<sha>:refs/heads/<branch>")
  - a push refused because the remote moved: fetch, build the data commit again on the new tip (data merged by the
    rules of the sync), push again. Any other failure: one line, the work goes on (as for ap-data)
  - the sync reads origin/<branch>:.ap-data/<file> as theirs
  - no origin remote: refused with one line ("needs an origin"), the files stay on the default ap-data
  - `files set data_branch <the production branch>` says once that a commit on the production branch can start a
    deploy in that repo (one line with "deploy")
A branch of its own (only agent files, or not there yet) keeps the layout of ap-data: the files at the root.
"""

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from test_agent_files import (AGENT_FILES, FilesCase, data_file, git, head, porcelain, read, tip,  # noqa: E402
                              tracked, write)

DIR = ".ap-data/"


class CodeBranchCase(FilesCase):
    """Maverick's clone with an origin; the data branch is the code branch itself (main here)."""

    def setUp(self):
        super().setUp()
        git(self.dir, "config", "user.email", "maverick@example.invalid")
        self.commit_all()
        self.make_remote()
        self.set_out = self.af("files", "set", "data_branch", self.branch).stdout
        git(self.dir, "push", "-q")

    def remote(self, name):
        return data_file(self.bare, DIR + name, ref=self.branch)

    def finish(self, task, cwd=None):
        self.af("todo", "add", task, "small", "the %s task" % task, "30", cwd=cwd)
        self.af("todo", "done", task, "--work", "5", "--type", "script", "--lane", "fast", cwd=cwd)


class TestTheSetSaysItCanDeploy(CodeBranchCase):
    def test_one_line_names_the_deploy(self):
        self.assertEqual(self.conf().get("data_branch"), self.branch)
        said = [l for l in self.set_out.splitlines() if "deploy" in l]
        self.assertEqual(len(said), 1, self.set_out)

    def test_show_names_the_branch(self):
        self.assertIn("place=%s" % self.branch, self.af("files", "show").stdout)


class TestAWriteLandsUnderTheDataFolder(CodeBranchCase):
    def test_the_record_reaches_origin_and_the_checkout_does_not_move(self):
        sha, local = head(self.dir), tip(self.dir, "refs/heads/" + self.branch)
        self.finish("t")
        self.assertIn("| t |", self.remote("agent_completed.txt") or "")
        self.assertIsNone(data_file(self.bare, "agent_completed.txt", ref=self.branch), "a file at the root")
        self.assertEqual(head(self.dir), sha)
        self.assertEqual(tip(self.dir, "refs/heads/" + self.branch), local)
        self.assertEqual(porcelain(self.dir).strip(), "", porcelain(self.dir))
        self.assertEqual(tip(self.dir, "ap-data"), "")

    def test_an_unpushed_code_commit_is_never_published(self):
        with open(os.path.join(self.dir, "seed.txt"), "a") as fh:
            fh.write("code not pushed yet\n")
        git(self.dir, "commit", "-q", "-am", "code not pushed yet")
        code = head(self.dir)
        self.finish("t")
        log = git(self.bare, "log", "--format=%H", self.branch).split()
        self.assertNotIn(code, log)
        self.assertIn("| t |", self.remote("agent_completed.txt") or "")


class TestAPullNeverFights(CodeBranchCase):
    def test_a_pull_is_clean_and_keeps_the_working_copies(self):
        self.finish("t")
        before = {n: read(os.path.join(self.dir, n)) for n in AGENT_FILES if os.path.exists(os.path.join(self.dir, n))}
        r = subprocess.run(["git", "-C", self.dir, "pull", "-q", "--no-rebase", "--no-edit"], capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(porcelain(self.dir).strip(), "", porcelain(self.dir))
        self.assertEqual({n: read(os.path.join(self.dir, n)) for n in before}, before)
        self.assertEqual(read(os.path.join(self.dir, DIR + "agent_completed.txt")),
                         read(os.path.join(self.dir, "agent_completed.txt")))

    def test_a_pull_with_a_local_code_commit_merges_clean_and_pushes(self):
        with open(os.path.join(self.dir, "seed.txt"), "a") as fh:
            fh.write("local code\n")
        git(self.dir, "commit", "-q", "-am", "local code")
        self.finish("t")
        r = subprocess.run(["git", "-C", self.dir, "pull", "-q", "--no-rebase", "--no-edit"], capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        git(self.dir, "push", "-q")
        self.assertEqual(porcelain(self.dir).strip(), "", porcelain(self.dir))
        self.finish("t2")
        self.assertIn("| t2 |", self.remote("agent_completed.txt") or "")
        self.assertIn("local code", git(self.bare, "show", "%s:seed.txt" % self.branch))


class TestAMergeOfProductionIntoTheWorkingBranchNeverFights(CodeBranchCase):
    def test_merges_both_ways_are_clean(self):
        git(self.dir, "checkout", "-q", "-b", "ap-main-maverick")
        self.finish("t")
        for round_ in (1, 2):
            git(self.dir, "fetch", "-q", "origin")
            r = subprocess.run(["git", "-C", self.dir, "merge", "-q", "--no-edit", "origin/" + self.branch],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(porcelain(self.dir).strip(), "", porcelain(self.dir))
            self.assertIn("| t |", read(os.path.join(self.dir, "agent_completed.txt")))
            self.finish("t%d" % round_)
        with open(os.path.join(self.dir, "feature.txt"), "w") as fh:
            fh.write("a feature\n")
        git(self.dir, "add", "feature.txt")
        git(self.dir, "commit", "-q", "-m", "a feature")
        git(self.dir, "checkout", "-q", self.branch)
        git(self.dir, "pull", "-q", "--no-rebase", "--no-edit")
        r = subprocess.run(["git", "-C", self.dir, "merge", "-q", "--no-edit", "ap-main-maverick"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(porcelain(self.dir).strip(), "", porcelain(self.dir))
        git(self.dir, "push", "-q")
        done = self.remote("agent_completed.txt") or ""
        for task in ("t", "t1", "t2"):
            self.assertIn("| %s |" % task, done)


class TestANewWorktreeAndASecondClone(CodeBranchCase):
    def test_a_new_worktree_has_no_working_copy_at_the_root(self):
        self.finish("t")
        git(self.dir, "pull", "-q", "--no-rebase", "--no-edit")
        wt = os.path.join(self.repo.base, "wt_new")
        git(self.dir, "worktree", "add", "-q", "-b", "new-task", wt)
        for name in AGENT_FILES:
            self.assertFalse(os.path.exists(os.path.join(wt, name)), name)
        self.assertEqual(porcelain(wt).strip(), "", porcelain(wt))

    def test_a_second_clone_reads_and_writes_the_same_files(self):
        self.finish("t")
        b = os.path.join(self.repo.base, "kinglun")
        subprocess.run(["git", "clone", "-q", self.bare, b], check=True, capture_output=True)
        git(b, "config", "user.name", "King Lun")
        git(b, "config", "user.email", "kinglun@example.invalid")
        self.af("files", "move", cwd=b)
        self.assertIn("| t |", read(os.path.join(b, "agent_completed.txt")))
        for name in AGENT_FILES:
            self.assertFalse(tracked(b, name), name)
        self.finish("his", cwd=b)
        self.finish("hers")
        self.af("files", "sync")
        self.af("files", "sync", cwd=b)
        for path in (self.dir, b):
            done = read(os.path.join(path, "agent_completed.txt"))
            for task in ("t", "his", "hers"):
                self.assertIn("| %s |" % task, done)
        done = self.remote("agent_completed.txt") or ""
        self.assertIn("| his |", done)
        self.assertIn("| hers |", done)


class TestAFailedPushOnACodeBranch(CodeBranchCase):
    def test_the_next_write_pushes_both_and_never_blocks(self):
        hook = os.path.join(self.bare, "hooks", "pre-receive")
        write(hook, "#!/bin/sh\necho 'protected branch' >&2\nexit 1\n")
        os.chmod(hook, 0o755)
        self.af("todo", "add", "t", "small", "the t task", "30")
        r = self.af("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.assertEqual(len([l for l in (r.stdout + r.stderr).splitlines() if "not pushed" in l]), 1,
                         r.stdout + r.stderr)
        os.remove(hook)
        self.finish("t2")
        done = self.remote("agent_completed.txt") or ""
        self.assertIn("| t |", done)
        self.assertIn("| t2 |", done)


class TestNoOriginNoCodeBranch(FilesCase):
    def test_a_code_branch_needs_an_origin(self):
        self.commit_all()
        code = git(self.dir, "symbolic-ref", "--short", "HEAD").strip()
        r = self.af("files", "set", "data_branch", code, ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("origin", r.stderr)
        self.assertNotIn("data_branch", self.conf())


if __name__ == "__main__":
    unittest.main()
