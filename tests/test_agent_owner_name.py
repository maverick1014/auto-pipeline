"""Failing tests of the estimate-improve scope add (TELL a8f43288, owner 2026-11-26): "for each of the
record beside we add a bracket to write the owner name or the people who make this changes".
Written by the task manager first. Built exactly this, nothing more (assign, take and who may work a task
belong to the task agent-files, which reads these two fields).

CONTRACT

N1  The name (fix order 1, main manager 2026-11-26: names like "Maverick" and "King Lun" stay as written):
    agent_conf.user_name(repo) = git config user.name of the clone (the folder the command runs in),
    trimmed, case and spaces kept; a "|" or a line break in it becomes a space; empty -> the login name;
    still empty -> "user". agent_conf.same_person(a, b): true when the cleaned forms are equal (lower case,
    every run of characters other than a-z and 0-9 one "-", no "-" at the ends), so an old stored
    "maverick" is "Maverick". The working branch keeps the cleaned form (its <name> is unchanged).
N2  todo add writes the field " | owner <name>" right after the " | by <who>" field, the name raw (the field
    ends at the next " | "). The by field stays as it is.
N3  todo done writes "by=<name>" (the name of the clone that runs todo done), raw, as the LAST key of the data
    block (after slices); every reader of the block reads by= to the end of the line (bash dload and dkey,
    show, backfill --force keeps it whole). backfill writes by=- when the line had no by (it never guesses).
N4  The board: the Task cell of a todo row whose line has an owner field is "<task> [<name>]"; no field: the
    task alone. `show` prints " [<name>]" at the end of each todo line with an owner field and of each
    completed line with a by=<name> that is not "-"; the files themselves never change.
N5  Old lines without the fields keep working everywhere (board, show, todo done, todo stage, eta, data,
    estimate); an unknown field on a todo line never makes a parser fail.
The two formats (for the task agent-files): todo line field "owner <name>"; data block key "by=<name>".
"""

import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_agent_board as tb  # noqa: E402
from scripthelp import BIN  # noqa: E402

NOW = tb.NOW


class OwnerCase(tb.BoardCase):
    lang = "en"

    def git_name(self, name):
        subprocess.run(["git", "-C", self.repo.dir, "config", "user.name", name], check=True, capture_output=True)

    def completed_lines(self):
        return [l for l in (self.repo.read("agent_completed.txt") or "").splitlines() if l]

    def put(self, *lines):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))


class TestTheName(OwnerCase):

    def conf(self):
        sys.path.insert(0, BIN)
        import importlib
        import agent_conf
        return importlib.reload(agent_conf)

    def test_n1_the_name_as_written(self):
        self.git_name("King Lun")
        self.assertEqual(self.conf().user_name(self.repo.dir), "King Lun")
        self.git_name("  Mei  Ling ")
        self.assertEqual(self.conf().user_name(self.repo.dir), "Mei  Ling")
        self.git_name("a|b")
        self.assertEqual(self.conf().user_name(self.repo.dir), "a b")

    def test_n1_no_git_name_takes_the_login(self):
        self.git_name("")
        import getpass
        self.assertEqual(self.conf().user_name(self.repo.dir), getpass.getuser().strip() or "user")

    def test_n1_same_person(self):
        c = self.conf()
        self.assertTrue(c.same_person("maverick", "Maverick"))
        self.assertTrue(c.same_person("King Lun", "king-lun"))
        self.assertFalse(c.same_person("King Lun", "King"))
        self.assertFalse(c.same_person("", "user"))

    def test_n1_the_working_branch_keeps_the_cleaned_name(self):
        self.git_name("King Lun")
        c = self.conf()
        self.assertIn("king-lun", c.working_branch(self.repo.dir, derive=True))


class TestTodoAddOwner(OwnerCase):

    def test_n2_the_field_after_by(self):
        self.git_name("Mei Ling")
        self.af("todo", "add", "x", "big", "the thing", "60", now=NOW)
        self.assertTrue(self.todo_line("x").endswith(" | opened 2026-11-02 15:00 | by main | owner Mei Ling"),
                        self.todo_line("x"))

    def test_n2_a_peer_by_stays(self):
        self.af("todo", "add", "x", "big", "the thing", "60", "v4-pospro", now=NOW)
        self.assertTrue(self.todo_line("x").endswith(" | by v4-pospro | owner t"), self.todo_line("x"))


class TestTodoDoneBy(OwnerCase):

    def test_n3_the_last_key(self):
        self.git_name("Mei Ling")
        self.put("x | big | w | est 60m | opened 2026-11-02 14:00 | by main | owner someone-else")
        self.af("todo", "done", "x", now=NOW)
        line = self.completed_lines()[-1]
        self.assertTrue(line.endswith(" slices=- by=Mei Ling"), line)

    def test_n3_an_old_line_without_owner(self):
        self.put("x | big | w | est 60m | opened 2026-11-02 14:00 | by main")
        self.af("todo", "done", "x", now=NOW)
        self.assertTrue(self.completed_lines()[-1].endswith(" by=t"), self.completed_lines())

    def test_n3_backfill_never_guesses(self):
        with open(self.repo.path("agent_completed.txt"), "w") as fh:
            fh.write("2026-10-01 | old | did it, work 30m | est 40m actual 50m\n")
        self.af("backfill", now=NOW)
        self.assertTrue(self.completed_lines()[-1].endswith(" by=-"), self.completed_lines())


class TestBoardAndShow(OwnerCase):

    def test_n4_the_board_task_cell(self):
        self.put("x | big | the login form | est 60m | opened 2026-11-02 14:00 | by main | owner mei-ling"
                 " | started 2026-11-02 14:10 | stage tests since 2026-11-02 14:30",
                 "y | big | an old line | est 60m | opened 2026-11-02 14:00 | by main"
                 " | started 2026-11-02 14:10 | stage tests since 2026-11-02 14:30")
        rows = self.table(self.board(now=NOW))
        tasks = sorted(r["Task"] for r in rows)
        self.assertEqual(tasks, ["x [mei-ling]", "y"])

    def test_n4_show(self):
        self.put("x | big | w | est 60m | opened 2026-11-02 14:00 | by main | owner mei-ling",
                 "y | big | old | est 60m | opened 2026-11-02 14:00 | by main")
        with open(self.repo.path("agent_completed.txt"), "w") as fh:
            fh.write("2026-11-01 | a | w | data repo=project type=- lane=- mock=- est=5 work=5 wait=0 clock=5"
                     " bounces=- workers=- files=- lines=- tests=- adds=- guess=- level=- typed=- est0=5 added=-"
                     " built=- stages=- slices=- by=mei-ling\n"
                     "2026-11-01 | b | w | data repo=project est=5 work=5 by=-\n"
                     "2026-11-01 | c | w | est 5m actual 5m\n")
        before = (self.repo.read("agent_todo.txt"), self.repo.read("agent_completed.txt"))
        out = self.af("show", now=NOW).stdout.splitlines()
        self.assertIn("x | big | w | est 60m | opened 2026-11-02 14:00 | by main | owner mei-ling [mei-ling]", out)
        self.assertIn("y | big | old | est 60m | opened 2026-11-02 14:00 | by main", out)
        self.assertTrue([l for l in out if l.startswith("2026-11-01 | a | ") and l.endswith(" by=mei-ling [mei-ling]")], out)
        self.assertIn("2026-11-01 | b | w | data repo=project est=5 work=5 by=-", out)
        self.assertIn("2026-11-01 | c | w | est 5m actual 5m", out)
        self.assertEqual((self.repo.read("agent_todo.txt"), self.repo.read("agent_completed.txt")), before)


class TestRoundTrip(OwnerCase):

    def test_a_name_with_a_space_end_to_end(self):
        self.git_name("King Lun")
        self.af("todo", "add", "x", "big", "the thing", "60", now="2026-11-02 14:00")
        self.assertTrue(self.todo_line("x").endswith(" | by main | owner King Lun"), self.todo_line("x"))
        self.af("todo", "stage", "x", "tests", now="2026-11-02 14:10")
        self.assertEqual([r["Task"] for r in self.table(self.board(now=NOW))], ["x [King Lun]"])
        self.af("todo", "done", "x", now=NOW)
        line = self.completed_lines()[-1]
        self.assertTrue(line.endswith(" by=King Lun"), line)
        out = self.af("show", now=NOW).stdout.splitlines()
        self.assertIn(line + " [King Lun]", out)
        # a reader of the block: backfill --force of one fact keeps the whole name
        self.af("backfill", "x", "--force", "--bounces", "2", now=NOW)
        again = self.completed_lines()[-1]
        self.assertTrue(again.endswith(" by=King Lun"), again)
        self.assertIn(" bounces=2 ", again)
        self.af("data", now=NOW)


class TestOldAndUnknownFields(OwnerCase):

    def test_n5_an_unknown_field_breaks_nothing(self):
        self.put("x | big | the login form | est 60m | opened 2026-11-02 14:00 | by main | colour blue"
                 " | owner t | started 2026-11-02 14:10 | stage tests since 2026-11-02 14:30 | mood fine")
        self.assertEqual(sorted(r["Task"] for r in self.table(self.board(now=NOW))), ["x [t]"])
        self.af("todo", "stage", "x", "verify", now=NOW)
        self.assertIn("work left", self.af("eta", "x", "--step", "5", now=NOW).stdout)
        self.af("todo", "done", "x", now=NOW)
        self.assertIn(" by=t", self.completed_lines()[-1])
        self.af("data", now=NOW)
        self.af("estimate", "--lane", "full", "--mock", "no", "--type", "script", "a thing", now=NOW)


if __name__ == "__main__":
    unittest.main()
