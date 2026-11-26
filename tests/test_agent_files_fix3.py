"""agent-files FIX ORDER 3 (TELL 09887a36), failing tests first.

`agent-file.sh files restore <file> [<saved name> | --list]`:
  - before it replaces the working copy, it saves the CURRENT working copy as a new saved copy
    (<git common dir>/agent-files-kept/<file>.before-<YYYYmmdd-HHMMSS>[-<n>]) and names that copy in its output, so a
    restore can be undone by a second restore; then the chosen copy becomes the working copy and the kept copy
  - no name: the newest saved copy (by mtime) that existed BEFORE this call
  - <saved name>: that saved copy (its file name in agent-files-kept, e.g. agent_todo.txt.before-20261126-101500)
  - --list: the saved copies of <file>, newest first, one per line: "<saved name> <n> lines"; nothing is changed
  - a restore never deletes a saved copy (its own save does not sweep)
"""

import glob
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from test_agent_files import FilesCase, git, read, write  # noqa: E402


def git_dir(path):
    return git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()


class RestoreCase(FilesCase):
    def setUp(self):
        super().setUp()
        self.commit_all()
        self.todo = os.path.join(self.dir, "agent_todo.txt")
        self.kept_dir = os.path.join(git_dir(self.dir), "agent-files-kept")

    def add(self, task):
        self.af("todo", "add", task, "small", "the %s task" % task, "30")

    def saved(self):
        """The saved copies of agent_todo.txt, newest first (by mtime)."""
        paths = glob.glob(os.path.join(self.kept_dir, "agent_todo.txt.before-*"))
        return sorted(paths, key=os.path.getmtime, reverse=True)

    def tasks(self):
        return [l.split(" | ", 1)[0] for l in read(self.todo).splitlines()]

    def reviewers_run(self):
        """e1, e2, an outside overwrite, then e3 and e4 added."""
        self.add("e1")
        self.add("e2")
        write(self.todo, "stale | from old branch\n")
        self.add("e3")
        time.sleep(1.1)   # a later mtime than the first saved copy
        self.add("e4")


class TestARestoreCanBeUndone(RestoreCase):
    def test_the_reviewers_run(self):
        self.reviewers_run()
        before = set(self.saved())
        self.assertEqual(len(before), 1)
        time.sleep(1.1)
        r = self.af("files", "restore", "agent_todo.txt")
        self.assertEqual(self.tasks(), ["e1", "e2"])
        new = [p for p in self.saved() if p not in before]
        self.assertEqual(len(new), 1, "the restore must save the current working copy first")
        self.assertIn(os.path.basename(new[0]), r.stdout + r.stderr)
        text = read(new[0])
        self.assertIn("e3 | ", text)
        self.assertIn("e4 | ", text)
        self.assertTrue(before <= set(self.saved()), "a restore never deletes a saved copy")
        time.sleep(1.1)
        self.af("files", "restore", "agent_todo.txt")
        self.assertIn("e3", self.tasks())
        self.assertIn("e4", self.tasks())
        self.assertEqual(len(self.saved()), 3)

    def test_an_older_copy_is_picked_by_name(self):
        self.reviewers_run()
        first = self.saved()[-1]
        time.sleep(1.1)
        self.af("files", "restore", "agent_todo.txt")
        time.sleep(1.1)
        self.af("files", "restore", "agent_todo.txt")
        self.assertIn("e3", self.tasks())
        time.sleep(1.1)
        r = self.af("files", "restore", "agent_todo.txt", os.path.basename(first))
        self.assertEqual(self.tasks(), ["e1", "e2"])
        self.assertIn("restored agent_todo.txt from", r.stdout + r.stderr)

    def test_an_unknown_name_is_refused(self):
        self.reviewers_run()
        before = read(self.todo)
        r = self.af("files", "restore", "agent_todo.txt", "agent_todo.txt.before-19990101-000000", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(read(self.todo), before)

    def test_the_list(self):
        self.reviewers_run()
        time.sleep(1.1)
        self.af("files", "restore", "agent_todo.txt")
        before = read(self.todo)
        out = self.af("files", "restore", "agent_todo.txt", "--list").stdout
        rows = [l.split() for l in out.splitlines() if l.startswith("agent_todo.txt.before-")]
        self.assertEqual([r[0] for r in rows], [os.path.basename(p) for p in self.saved()])
        for row, path in zip(rows, self.saved()):
            n = len(read(path).splitlines())
            self.assertEqual(row[1:3], [str(n), "lines"], row)
        self.assertEqual(read(self.todo), before, "--list changes nothing")


if __name__ == "__main__":
    unittest.main()
