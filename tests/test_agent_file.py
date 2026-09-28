"""Tests for bin/agent-file.sh `todo add`'s optional 5th argument (by).

CONTRACT (W12, PRINCIPLES.md):
    agent-file.sh todo add "<name>" "<size>" "<what>" [est_minutes] [by]

    - No 5th arg -> line ends "| by main" (AGENT_ROLE defaults to "main").
    - A 5th arg (e.g. a peer repo name) -> line ends "| by <that arg>".
    - `todo done` still finds and moves the line either way.

CONTRACT (todo drop):
    agent-file.sh todo drop "<name>" "<reason>"

    A todo that is no longer needed. The line leaves agent_todo.txt and is
    appended to agent_completed.txt as

        <date> | <name> | <what> | est <n>m actual - | dropped: <reason>

    (est "-" when the todo had none). Never the opened->now minutes: a drop
    is not work, and those minutes would skew `time`.
    `time` skips dropped lines.
    Unknown name -> exit 1, "no todo line named: <name>" on stderr.
    No reason -> usage, exit 2, nothing moves.
    The usage text lists `todo drop`.
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


class TestTodoDrop(ScriptCase):
    script = "agent-file.sh"

    def add(self, name="old-task", est="15"):
        args = ["todo", "add", name, "small", "a thing we no longer need"]
        if est:
            args.append(est)
        self.assertOk(self.repo.run("agent-file.sh", *args))

    def drop(self, *args):
        return self.repo.run("agent-file.sh", "todo", "drop", *args)

    def test_the_line_leaves_the_todo_file(self):
        self.add()
        self.assertOk(self.drop("old-task", "moot after the plugin update"))
        self.assertNotIn("old-task |", todo_text(self.repo))

    def test_the_line_lands_in_completed_with_actual_dash_and_the_reason(self):
        self.add()
        self.assertOk(self.drop("old-task", "moot after the plugin update"))
        lines = [l for l in completed_text(self.repo).splitlines()
                 if "| old-task |" in l]
        self.assertEqual(len(lines), 1, completed_text(self.repo))
        self.assertRegex(
            lines[0],
            r"^\d{4}-\d\d-\d\d \| old-task \| a thing we no longer need \| "
            r"est 15m actual - \| dropped: moot after the plugin update$")

    def test_a_todo_with_no_estimate_drops_with_est_dash(self):
        self.add(est=None)
        self.assertOk(self.drop("old-task", "not needed"))
        self.assertIn("| est - actual - | dropped: not needed",
                      completed_text(self.repo))

    def test_it_says_what_it_did(self):
        self.add()
        out = self.assertOk(self.drop("old-task", "not needed"))
        self.assertIn("todo dropped: old-task", out)

    def test_an_unknown_name_fails_and_changes_nothing(self):
        self.add()
        before = (todo_text(self.repo), completed_text(self.repo))
        result = self.drop("no-such-task", "why")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no todo line named: no-such-task", result.stderr)
        self.assertEqual((todo_text(self.repo), completed_text(self.repo)),
                         before)

    def test_no_reason_is_usage_and_changes_nothing(self):
        self.add()
        result = self.drop("old-task")
        self.assertEqual(result.returncode, 2)
        self.assertIn("old-task |", todo_text(self.repo))
        self.assertNotIn("old-task", completed_text(self.repo))

    def test_the_other_todo_lines_stay(self):
        self.add("keep-me")
        self.add("old-task")
        self.assertOk(self.drop("old-task", "not needed"))
        self.assertIn("keep-me |", todo_text(self.repo))

    def test_time_skips_a_dropped_line(self):
        self.add("real-work")
        self.assertOk(self.repo.run("agent-file.sh", "todo", "done",
                                    "real-work"))
        self.add("old-task")
        self.assertOk(self.drop("old-task", "not needed"))
        out = self.assertOk(self.repo.run("agent-file.sh", "time"))
        self.assertIn("real-work", out)
        self.assertNotIn("old-task", out)

    def test_usage_lists_todo_drop(self):
        result = self.repo.run("agent-file.sh")
        self.assertEqual(result.returncode, 2)
        self.assertIn("todo drop", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
