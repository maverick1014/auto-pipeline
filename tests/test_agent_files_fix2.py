"""agent-files FIX ORDER 2 (TELL 0d802116), failing tests first.

1  A kept copy is never lost by an outside change. When a working copy differs from its kept copy at the start of a
   WRITE command, before anything is written the old kept copy is saved beside it as
   <git common dir>/agent-files-kept/<file>.before-<YYYYmmdd-HHMMSS>[-<n>] (a unique name), and ONE line starting
   "WARNING" names the working copy, the saved copy and the command that puts it back:
   `agent-file.sh files restore <file>`. The write then goes on on the working copy as now (no silent restore).
   A read-only command (idea list, board, show, ...) only warns: no saved copy. A normal write saves none.
   `files restore <file>` puts the newest saved copy back as the working copy and the kept copy (and, for a file in
   git, commits it like any write), ONE line "restored <file> from <saved path>"; no saved copy: exit 1, one line.
   Each time a copy is saved, that file's saved copies older than 7 days are swept, except the newest 5, which stay.
2  agent-start.sh: a data_branch value git does not accept as a branch name ("my branch") is said as
   "not valid, the default ap-data is used", like the other two settings.
"""

import glob
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from test_agent_files import FilesCase, git, read, todo_line, write  # noqa: E402


def git_dir(path):
    return git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()


class KeptCase(FilesCase):
    def build(self):
        super().build()
        self.commit_all()
        self.todo = os.path.join(self.dir, "agent_todo.txt")
        self.kept_dir = os.path.join(git_dir(self.dir), "agent-files-kept")

    def saved(self, name="agent_todo.txt"):
        return sorted(glob.glob(os.path.join(self.kept_dir, name + ".before-*")))

    def lines_of(self, r, start):
        return [l for l in (r.stdout + r.stderr).splitlines() if l.startswith(start)]

    def overwrite(self):
        """What a checkout of an old branch does to the working copy."""
        write(self.todo, "stale | from old branch\n")


class TestTheReviewersRun(KeptCase):
    def test_e1_and_e2_survive_and_come_back(self):
        self.af("todo", "add", "e1", "small", "the e1 task", "30")
        self.af("todo", "add", "e2", "small", "the e2 task", "30")
        self.overwrite()
        r = self.af("todo", "add", "e3", "small", "the e3 task", "30")
        warn = self.lines_of(r, "WARNING")
        self.assertEqual(len(warn), 1, r.stdout + r.stderr)
        saved = self.saved()
        self.assertEqual(len(saved), 1)
        self.assertIn(self.todo, warn[0])
        self.assertIn(saved[0], warn[0])
        self.assertIn("files restore agent_todo.txt", warn[0])
        text = read(saved[0])
        self.assertIn("e1 | ", text)
        self.assertIn("e2 | ", text)
        self.assertIn("e3 | ", read(self.todo), "the write goes on on the working copy")
        r = self.af("files", "restore", "agent_todo.txt")
        self.assertEqual(len(self.lines_of(r, "restored agent_todo.txt from")), 1, r.stdout + r.stderr)
        back = read(self.todo)
        self.assertIn("e1 | ", back)
        self.assertIn("e2 | ", back)
        self.assertEqual(read(os.path.join(self.kept_dir, "agent_todo.txt")), back)
        r = self.af("idea", "list")
        self.assertEqual(self.lines_of(r, "WARNING"), [], "after the restore the copies agree")

    def test_two_outside_changes_in_a_row_keep_two_saved_copies(self):
        self.af("todo", "add", "e1", "small", "the e1 task", "30")
        self.overwrite()
        self.af("todo", "add", "e2", "small", "the e2 task", "30")
        write(self.todo, "stale again | from another old branch\n")
        self.af("todo", "add", "e3", "small", "the e3 task", "30")
        self.assertEqual(len(self.saved()), 2)

    def test_a_normal_write_saves_nothing(self):
        self.af("todo", "add", "e1", "small", "the e1 task", "30")
        self.af("todo", "add", "e2", "small", "the e2 task", "30")
        self.af("todo", "stage", "e1", "brief")
        self.assertEqual(self.saved(), [])

    def test_a_read_only_command_only_warns(self):
        self.af("todo", "add", "e1", "small", "the e1 task", "30")
        self.overwrite()
        r = self.af("idea", "list")
        self.assertEqual(len(self.lines_of(r, "WARNING")), 1, r.stdout + r.stderr)
        self.assertEqual(self.saved(), [])
        self.assertEqual(read(self.todo), "stale | from old branch\n")

    def test_restore_with_nothing_saved_is_refused(self):
        self.af("todo", "add", "e1", "small", "the e1 task", "30")
        r = self.af("files", "restore", "agent_todo.txt", ok=False)
        self.assertEqual(r.returncode, 1)


class TestTheSavedCopiesAreSwept(KeptCase):
    def test_old_copies_go_the_newest_five_stay(self):
        self.af("todo", "add", "e1", "small", "the e1 task", "30")
        old = time.time() - 9 * 86400
        names = []
        for n in range(7):
            p = os.path.join(self.kept_dir, "agent_todo.txt.before-2026010%d-100000" % (n + 1))
            write(p, todo_line("old%d" % n) + "\n")
            os.utime(p, (old + n * 60, old + n * 60))
            names.append(p)
        young = os.path.join(self.kept_dir, "agent_ideas.txt.before-20260101-100000")
        write(young, "an idea | 2026-01-01 10:00 | by Maverick\n")
        os.utime(young, (old, old))
        self.overwrite()
        self.af("todo", "add", "e2", "small", "the e2 task", "30")
        left = self.saved()
        self.assertEqual(len(left), 5, left)
        for p in names[:3]:
            self.assertNotIn(p, left)
        for p in names[3:]:
            self.assertIn(p, left)
        self.assertTrue(os.path.exists(young), "another file's copies are swept only when that file saves one")

    def test_young_copies_are_never_swept(self):
        self.af("todo", "add", "e1", "small", "the e1 task", "30")
        for n in range(6):
            write(os.path.join(self.kept_dir, "agent_todo.txt.before-2026112%d-100000" % n), "x\n")
        self.overwrite()
        self.af("todo", "add", "e2", "small", "the e2 task", "30")
        self.assertEqual(len(self.saved()), 7)


class TestAnInvalidDataBranchIsSaid(FilesCase):
    def test_the_start_names_the_default(self):
        self.commit_all()
        path = os.path.join(self.dir, "agent_repo.conf")
        write(path, read(path) + "data_branch=my branch\n")
        out = self.repo.run("agent-start.sh").stdout
        said = [l for l in out.splitlines() if "data_branch" in l]
        self.assertEqual(len(said), 1, out)
        self.assertIn("not valid, the default ap-data is used", said[0])
        self.assertNotIn("the repo value counts", said[0])


if __name__ == "__main__":
    unittest.main()
