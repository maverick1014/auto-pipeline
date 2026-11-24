"""Owner rule (PRINCIPLES R5): agent_completed.txt is never deleted, trimmed or
cleaned, except on an explicit owner order. The clean-up files table, the
clean-up sweep and the housekeep pass must leave its bytes alone."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from test_agent_cleanfiles import FilesCase, NOW

DONE_LINES = [
    "2026-01-02 | old-task | an old finished task | data repo=x work=5",
    "2026-02-03 | dropped-task | dropped long ago | est 10m actual - | dropped: x",
    "2026-11-20 | recent-task | a recent one | data repo=x work=7",
    "2026-11-20 | dup-idea | same text | data repo=x work=7",
    "2026-11-20 | dup-idea | same text | data repo=x work=7",
]


class TestCompletedKept(FilesCase):

    def plant(self):
        self.set_file("agent_completed.txt", DONE_LINES)
        self.write("notes.md")
        self.write("mock/old-task-mock.html")
        self.commit_all()
        self.set_file("agent_ideas.txt", ["same idea", "same idea"])
        self.set_file("agent_todo.txt", [
            "quiet | big | something | est 30m | opened 2026-11-01 08:00 | by main"])
        return self.bytes()

    def bytes(self):
        with open(self.p("agent_completed.txt"), "rb") as fh:
            return fh.read()

    def test_files_table_never_lists_it_and_removal_keeps_it(self):
        before = self.plant()
        out = self.dry()
        self.assertNotIn("agent_completed", out)
        self.assertEqual(self.bytes(), before)
        self.assertOk(self.yes("all"))
        # closing a stale todo may append a dropped line; no line goes
        self.assertTrue(self.bytes().startswith(before))

    def test_sweep_and_housekeep_keep_it(self):
        before = self.plant()
        for script, args in (("agent-cleanup.sh", ["--apply"]),
                             ("agent-cleanup.sh", []),
                             ("agent-housekeep.sh", ["--apply"]),
                             ("agent-housekeep.sh", [])):
            with self.subTest(script=script, args=args):
                self.repo.run(script, *args, env={"AGENT_FAKE_NOW": NOW})
                self.assertEqual(self.bytes(), before)

    def test_line_removal_table_never_names_it(self):
        bin_dir = os.path.join(os.path.dirname(HERE), "bin")
        with open(os.path.join(bin_dir, "agent_cleanfiles.py")) as fh:
            src = fh.read()
        start = src.index("LINE_FILES")
        self.assertNotIn("completed", src[start:src.index("}", start)])


if __name__ == "__main__":
    unittest.main()
