"""Tests for bin/agent-file.sh `todo add`'s optional 5th argument (by).

CONTRACT (W12, PRINCIPLES.md):
    agent-file.sh todo add "<name>" "<size>" "<what>" [est_minutes] [by]

    - No 5th arg -> line ends "| by main" (AGENT_ROLE defaults to "main").
    - A 5th arg (e.g. a peer repo name) -> line ends "| by <that arg>".
    - `todo done` still finds and moves the line either way.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase


def todo_text(repo):
    with open(os.path.join(repo.dir, "agent_todo.txt")) as fh:
        return fh.read()


def completed_text(repo):
    with open(os.path.join(repo.dir, "agent_completed.txt")) as fh:
        return fh.read()


class TestTodoAddBy(ScriptCase):
    script = "agent-file.sh"

    def test_default_by_is_main(self):
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add",
                                    "fix-typo", "small", "one line", "10"))
        self.assertIn("| by main", todo_text(self.repo))

    def test_fifth_arg_sets_by(self):
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add",
                                    "cross-repo-task", "big", "one line",
                                    "30", "v4-pospro"))
        self.assertIn("| by v4-pospro", todo_text(self.repo))
        self.assertNotIn("| by main", todo_text(self.repo))

    def test_todo_done_moves_a_default_by_line(self):
        self.repo.run("agent-file.sh", "todo", "add", "a", "small", "x", "5")
        self.assertOk(self.repo.run("agent-file.sh", "todo", "done", "a"))
        self.assertNotIn("a |", todo_text(self.repo))
        self.assertIn("a |", completed_text(self.repo))

    def test_todo_done_moves_a_peer_by_line(self):
        self.repo.run("agent-file.sh", "todo", "add", "b", "big", "y", "20",
                      "v4-plus")
        self.assertOk(self.repo.run("agent-file.sh", "todo", "done", "b"))
        self.assertNotIn("b |", todo_text(self.repo))
        self.assertIn("b |", completed_text(self.repo))


if __name__ == "__main__":
    unittest.main()
