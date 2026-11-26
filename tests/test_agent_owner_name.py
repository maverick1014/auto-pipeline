"""Failing tests of the estimate-improve scope add (TELL a8f43288, owner 2026-11-26): "for each of the
record beside we add a bracket to write the owner name or the people who make this changes".
Written by the task manager first. Built exactly this, nothing more (assign, take and who may work a task
belong to the task agent-files, which reads these two fields).

CONTRACT

N1  The name: git config user.name of the clone (the folder the command runs in), the same source and the
    same cleaning as the <name> of the working branch (bin/agent_conf.py working_branch): lower case, every run
    of characters other than a-z and 0-9 one "-", no "-" at the ends; empty -> the login name cleaned the same
    way; still empty -> "user". One function for both: agent_conf.user_name(repo).
N2  todo add writes the field " | owner <name>" right after the " | by <who>" field. The by field stays as it is.
N3  todo done writes "by=<name>" (the name of the clone that runs todo done) as the LAST key of the data block
    (after slices). backfill writes by=- when the line had no by (it never guesses a name).
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

    def test_n1_cleaned_like_the_working_branch(self):
        self.git_name("Niagawan Mave")
        self.assertEqual(self.conf().user_name(self.repo.dir), "niagawan-mave")
        self.git_name("  A.B__c  ")
        self.assertEqual(self.conf().user_name(self.repo.dir), "a-b-c")

    def test_n1_no_git_name_takes_the_login(self):
        self.git_name("")
        import getpass
        login = re.sub(r"[^a-z0-9]+", "-", getpass.getuser().lower()).strip("-") or "user"
        self.assertEqual(self.conf().user_name(self.repo.dir), login)


class TestTodoAddOwner(OwnerCase):

    def test_n2_the_field_after_by(self):
        self.git_name("Niagawan Mave")
        self.af("todo", "add", "x", "big", "the thing", "60", now=NOW)
        self.assertTrue(self.todo_line("x").endswith(" | opened 2026-11-02 15:00 | by main | owner niagawan-mave"),
                        self.todo_line("x"))

    def test_n2_a_peer_by_stays(self):
        self.af("todo", "add", "x", "big", "the thing", "60", "v4-pospro", now=NOW)
        self.assertTrue(self.todo_line("x").endswith(" | by v4-pospro | owner t"), self.todo_line("x"))


class TestTodoDoneBy(OwnerCase):

    def test_n3_the_last_key(self):
        self.git_name("Niagawan Mave")
        self.put("x | big | w | est 60m | opened 2026-11-02 14:00 | by main | owner someone-else")
        self.af("todo", "done", "x", now=NOW)
        line = self.completed_lines()[-1]
        self.assertTrue(line.endswith(" slices=- by=niagawan-mave"), line)

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
        self.put("x | big | the login form | est 60m | opened 2026-11-02 14:00 | by main | owner niagawan-mave"
                 " | started 2026-11-02 14:10 | stage tests since 2026-11-02 14:30",
                 "y | big | an old line | est 60m | opened 2026-11-02 14:00 | by main"
                 " | started 2026-11-02 14:10 | stage tests since 2026-11-02 14:30")
        rows = self.table(self.board(now=NOW))
        tasks = sorted(r["Task"] for r in rows)
        self.assertEqual(tasks, ["x [niagawan-mave]", "y"])

    def test_n4_show(self):
        self.put("x | big | w | est 60m | opened 2026-11-02 14:00 | by main | owner niagawan-mave",
                 "y | big | old | est 60m | opened 2026-11-02 14:00 | by main")
        with open(self.repo.path("agent_completed.txt"), "w") as fh:
            fh.write("2026-11-01 | a | w | data repo=project type=- lane=- mock=- est=5 work=5 wait=0 clock=5"
                     " bounces=- workers=- files=- lines=- tests=- adds=- guess=- level=- typed=- est0=5 added=-"
                     " built=- stages=- slices=- by=niagawan-mave\n"
                     "2026-11-01 | b | w | data repo=project est=5 work=5 by=-\n"
                     "2026-11-01 | c | w | est 5m actual 5m\n")
        before = (self.repo.read("agent_todo.txt"), self.repo.read("agent_completed.txt"))
        out = self.af("show", now=NOW).stdout.splitlines()
        self.assertIn("x | big | w | est 60m | opened 2026-11-02 14:00 | by main | owner niagawan-mave [niagawan-mave]", out)
        self.assertIn("y | big | old | est 60m | opened 2026-11-02 14:00 | by main", out)
        self.assertTrue([l for l in out if l.startswith("2026-11-01 | a | ") and l.endswith(" by=niagawan-mave [niagawan-mave]")], out)
        self.assertIn("2026-11-01 | b | w | data repo=project est=5 work=5 by=-", out)
        self.assertIn("2026-11-01 | c | w | est 5m actual 5m", out)
        self.assertEqual((self.repo.read("agent_todo.txt"), self.repo.read("agent_completed.txt")), before)


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
