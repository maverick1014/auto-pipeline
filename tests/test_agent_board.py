"""Failing tests for 'show todo', the board and its records. Written by the task manager first.

Owner, 2026-11-02: one table of everything open, sorted, with times that come
from the files, never guessed. What is not recorded yet gets a record.

CONTRACT (bin/agent-file.sh; the table itself may be drawn by bin/agent_board.py)

Records on the todo line (agent_todo.txt, main repo, one atomic write each;
every other field of the line stays where it is):

    todo wait <name> on <kind> ["<note>"]
        kind: mock | question | review   (waits on the owner)
              hold | queue                (held, queued)
        field " | waiting <kind> since <YYYY-MM-DD HH:MM>" (+ ": <note>")
        already waiting -> that wait is closed first (added to waited)
    todo wait <name> off
        closes the open wait: field " | waited <m>m" = the sum of every
        closed wait, the "waiting" field goes
    todo where <name> <machine> [<worktree path>]
        field " | on <machine>[ <path>]", replaced when set again
    Refused, one line on stderr, exit 1, nothing written: no todo line of
    that name, a kind not in the list, off when not waiting, no on|off,
    a machine with a space, " | " inside a note or a path.
    todo done, eta and the rest still read such a line (est, what, opened).

Records in agent_state.txt of the session's own folder (the git toplevel of
the cwd, like agent_state.txt itself):

    park add "<question>" [<task>]  -> "PARKED: <question> | <task> | since <date>"
                                        task defaults to that folder's name
    park list                         -> the PARKED lines, numbered "1. ..."
    park rm <n>                       -> removes the n-th PARKED line
    worker on <n> "<slice>"           -> "WORKER <n>: <slice> | since <date>"
                                        (replaces worker <n>)
    worker off <n>                    -> removes it
    Refused (exit 1, one stderr line, nothing written): empty text, " | "
    inside it, n not a whole number from 1, no such n.

OWNER TODO items are written by hand: a line of an agent_state.txt with the
capitals OWNER TODO at the start of its text (after spaces, a "-" or "*"
bullet, or a "YYYY-MM-DD[ HH:MM]" stamp) or followed by ":"; a quote mark
right before it makes it a mention. The item text is what follows the marker
(and its ":"). A leading stamp is its date.

    board            the whole repo (main manager)
    board --self     the session's own task (task manager, Helper)

Read only: writes nothing, touches nothing. Prints one GitHub markdown table
(or one line "无" / "none" when there is no row), then note lines.
Columns, in the agent.conf language (zh, else en):
    zh  任务 | 内容 | 状态 | 位置 | 估时 | 已工作 | 已等待 | 预计完成
    en  Task | What | Status | Where | Est | Work | Wait | Done by

Rows, whole repo:
    every todo line          task, what (field 3), status from its waiting field
    every human-direct line  "<repo> Helper", what = its "task: <Task Name>"
    the state lines          OWNER TODO, PARKED, WORKER of the main repo's
                             agent_state.txt and of every agent_worktree.txt
                             folder that is on this machine; a folder that is
                             not here -> a note line after the table
                             (zh "不在本机，未读：<path>", en "not on this machine,
                             not read: <path>")
Rows, --self (name = the folder name of the git toplevel of the cwd):
    its todo line from the main repo, else its "TODO LINE: <todo line>" in
    its own agent_state.txt, else the human-direct line of its folder, else
    one bare row (what "-"); plus the state lines of its own agent_state.txt
    only. In the main repo folder itself (a Helper with no worktree) that
    file is the main manager's: no state lines then.

Status (zh / en), a todo wait note after " · ":
    mock      等你：看样稿     waits on you: mock check
    question  等你：回答问题   waits on you: question
    review    等你：验收       waits on you: review
    running   进行中           running        (tasks, Helpers, workers)
    hold      暂缓             held
    queue     排队中           queued
    OWNER TODO  你的待办       your to-do
    PARKED    搁置的问题       parked question
Sort: waiting on the owner, running, held or queued, OWNER TODO, parked.
Oldest first in a group: a waiting row by when its wait began, the rest by
when they began (opened, since, the stamp); no date -> last, file order.

Cells:
    what      white space collapsed; over 60 characters -> cut at a word end,
              "…" added, 60 at most; "|" written as "\\|"
    where     "<machine>, <path>" ("~" for $HOME): the todo where record;
              else the agent_worktree.txt line whose module or folder name is
              the task -> this machine when that folder is here, else the
              path alone; --self -> this machine and its own folder; a state
              line -> this machine and that folder; else "-"
    est       from "est <n>m"
    wait      waited + the open wait up to now (task); since -> now (parked);
              stamp -> now (OWNER TODO)
    work      clock from opened to now, minus wait, 0 at least (task);
              since -> now (worker); "-" for the rest
    done by   now + est - work, as "HH:MM" today, zh "明天 HH:MM" /
              en "HH:MM tomorrow", later zh "YYYY-MM-DD HH:MM" /
              en "HH:MM on YYYY-MM-DD"; work >= est -> zh "超出估时" /
              en "over est"; no est -> "-"
    minutes   "45m", "1h", "1h 35m", "1d", "1d 1h" (a day or more: no minutes)
    unknown   "-"

AGENT_FAKE_NOW="YYYY-MM-DD HH:MM" replaces the clock, AGENT_FAKE_HOST the
machine name (tests). Unset: the real clock, the short host name.
"""

import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase

NOW = "2026-11-02 15:00"
HOST = "pc2"
HEAD = {"zh": ["任务", "内容", "状态", "位置", "估时", "已工作", "已等待", "预计完成"],
        "en": ["Task", "What", "Status", "Where", "Est", "Work", "Wait", "Done by"]}
STATUS = {
    "zh": {"mock": "等你：看样稿", "question": "等你：回答问题", "review": "等你：验收",
           "running": "进行中", "hold": "暂缓", "queue": "排队中", "owner": "你的待办",
           "parked": "搁置的问题"},
    "en": {"mock": "waits on you: mock check", "question": "waits on you: question",
           "review": "waits on you: review", "running": "running", "hold": "held",
           "queue": "queued", "owner": "your to-do", "parked": "parked question"},
}


def cells(line):
    inner = line.strip()
    assert inner.startswith("|") and inner.endswith("|"), line
    return [c.strip() for c in re.split(r"(?<!\\)\|", inner[1:-1])]


class BoardCase(ScriptCase):
    script = "agent-file.sh"
    lang = "zh"

    def setUp(self):
        super().setUp()
        self.repo.set_conf("language", self.lang)

    # ---- running agent-file.sh ----

    def af(self, *args, now=NOW, cwd=None, ok=True):
        result = self.repo.run("agent-file.sh", *args, cwd=cwd,
                               env={"AGENT_FAKE_NOW": now, "AGENT_FAKE_HOST": HOST})
        if ok:
            self.assertOk(result)
        return result

    def refused(self, *args, now=NOW, cwd=None):
        files = {n: self.repo.read(n) for n in ("agent_todo.txt", "agent_state.txt")}
        result = self.af(*args, now=now, cwd=cwd, ok=False)
        self.assertEqual(result.returncode, 1, (args, result.stdout, result.stderr))
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
        self.assertEqual({n: self.repo.read(n) for n in files}, files, args)
        return result

    def add(self, name, what, est=None, opened="2026-11-02 14:00", size="big"):
        args = ["todo", "add", name, size, what] + ([str(est)] if est is not None else [])
        self.af(*args, now=opened)

    def wait(self, name, *rest, now=NOW):
        self.af("todo", "wait", name, *rest, now=now)

    def todo_line(self, name):
        for line in (self.repo.read("agent_todo.txt") or "").splitlines():
            if line.split(" | ")[0] == name:
                return line
        return None

    def state(self, text, folder=None):
        with open(os.path.join(folder or self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write(text if text.endswith("\n") else text + "\n")

    def state_text(self, folder=None):
        full = os.path.join(folder or self.repo.dir, "agent_state.txt")
        if not os.path.exists(full):
            return ""
        with open(full) as fh:
            return fh.read()

    def worktree_lines(self, *rows):
        self.repo.set_worktree_lines(list(rows))

    def task_worktree(self, name):
        """A real git worktree of the project, its folder named after the task."""
        subprocess.run(["git", "-C", self.repo.dir, "add", "-A"], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", self.repo.dir, "commit", "-q", "-m", "seed2",
                        "--allow-empty"], check=True, capture_output=True)
        path = os.path.join(self.repo.base, name)
        subprocess.run(["git", "-C", self.repo.dir, "worktree", "add", "-q", "-b",
                        name, path], check=True, capture_output=True)
        return os.path.realpath(path)

    # ---- reading the board ----

    def board(self, *args, now=NOW, cwd=None):
        return self.af("board", *args, now=now, cwd=cwd).stdout

    def table(self, out):
        lines = [l for l in out.splitlines() if l.startswith("|")]
        self.assertGreaterEqual(len(lines), 2, out)
        head = cells(lines[0])
        self.assertEqual(head, HEAD[self.lang])
        sep = cells(lines[1])
        self.assertEqual(len(sep), 8)
        for c in sep:
            self.assertRegex(c, r"^:?-{3,}:?$")
        rows = []
        for line in lines[2:]:
            row = cells(line)
            self.assertEqual(len(row), 8, line)
            rows.append(dict(zip(HEAD["en"], row)))
        return rows

    def rows(self, *args, **kw):
        return self.table(self.board(*args, **kw))

    def row(self, rows, task=None, what=None):
        for r in rows:
            if (task is None or r["Task"] == task) and (what is None or r["What"] == what):
                return r
        self.fail("no row task=%r what=%r in %r" % (task, what, rows))

    def st(self, key):
        return STATUS[self.lang][key]


# ---------------------------------------------------------------- todo wait


class TestTodoWait(BoardCase):
    def test_on_then_off_sums_the_wait(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 13:00")
        self.wait("alpha", "on", "mock", now="2026-11-02 13:30")
        self.wait("alpha", "off", now="2026-11-02 13:50")
        line = self.todo_line("alpha")
        self.assertIn(" | waited 20m", line)
        self.assertNotIn("waiting ", line)
        self.wait("alpha", "on", "question", now="2026-11-02 14:00")
        self.wait("alpha", "off", now="2026-11-02 14:05")
        line = self.todo_line("alpha")
        self.assertEqual(line.count(" | waited "), 1, line)
        self.assertIn(" | waited 25m", line)
        r = self.row(self.rows(), task="alpha")
        self.assertEqual((r["What"], r["Status"], r["Est"], r["Work"], r["Wait"], r["Done by"]),
                         ("the login form", self.st("running"), "2h", "1h 35m", "25m", "15:25"))

    def test_a_wait_still_open_counts_up_to_now(self):
        self.add("beta", "bank recon match", 60, opened="2026-11-02 14:00")
        self.wait("beta", "on", "review", now="2026-11-02 14:30")
        self.assertIn(" | waiting review since 2026-11-02 14:30", self.todo_line("beta"))
        r = self.row(self.rows(), task="beta")
        self.assertEqual((r["Status"], r["Work"], r["Wait"], r["Done by"]),
                         (self.st("review"), "30m", "30m", "15:30"))

    def test_a_new_wait_closes_the_open_one(self):
        self.add("gamma", "stock lock page", 60, opened="2026-11-02 14:00")
        self.wait("gamma", "on", "mock", now="2026-11-02 14:00")
        self.wait("gamma", "on", "question", "which DB?", now="2026-11-02 14:20")
        line = self.todo_line("gamma")
        self.assertIn(" | waited 20m", line)
        self.assertIn(" | waiting question since 2026-11-02 14:20: which DB?", line)
        self.assertEqual(line.count("waiting "), 1, line)
        r = self.row(self.rows(now="2026-11-02 14:30"), task="gamma")
        self.assertEqual(r["Status"], self.st("question") + " · which DB?")
        self.assertEqual(r["Wait"], "30m")
        self.assertEqual(r["Work"], "0m")

    def test_held_and_queued(self):
        self.add("held-one", "font size option", 30)
        self.add("queued-one", "report export", 30)
        self.wait("held-one", "on", "hold", now="2026-11-02 14:10")
        self.wait("queued-one", "on", "queue", now="2026-11-02 14:20")
        rows = self.rows()
        self.assertEqual(self.row(rows, task="held-one")["Status"], self.st("hold"))
        self.assertEqual(self.row(rows, task="queued-one")["Status"], self.st("queue"))

    def test_the_other_fields_stay(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 13:00")
        before = self.todo_line("alpha")
        self.wait("alpha", "on", "mock", now="2026-11-02 13:30")
        self.assertTrue(self.todo_line("alpha").startswith(before), self.todo_line("alpha"))

    def test_refusals(self):
        self.add("alpha", "the login form", 60)
        for args in (("todo", "wait", "nobody", "on", "mock"),
                     ("todo", "wait", "alpha", "on", "coffee"),
                     ("todo", "wait", "alpha", "off"),
                     ("todo", "wait", "alpha", "maybe"),
                     ("todo", "wait", "alpha", "on", "question", "a | b")):
            with self.subTest(args=args):
                self.refused(*args)

    def test_todo_done_and_eta_still_read_the_line(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 13:00")
        self.wait("alpha", "on", "mock", now="2026-11-02 13:30")
        self.wait("alpha", "off", now="2026-11-02 13:50")
        self.af("todo", "where", "alpha", "pc2", "/x/alpha")
        self.wait("alpha", "on", "review", now="2026-11-02 14:00")
        out = self.af("eta", "alpha", "--step", "3").stdout
        self.assertIn("work left", out)
        self.af("todo", "done", "alpha", "--work", "70")
        done = self.repo.read("agent_completed.txt")
        self.assertIn(" | alpha | the login form | data ", done)
        self.assertIn(" est=120 ", done)
        self.assertIsNone(self.todo_line("alpha"))


# ---------------------------------------------------------------- todo where


class TestTodoWhere(BoardCase):
    def test_machine_and_worktree(self):
        self.add("alpha", "the login form", 60)
        self.af("todo", "where", "alpha", "laptop", "/Users/x/orca/alpha")
        self.assertEqual(self.row(self.rows(), task="alpha")["Where"],
                         "laptop, /Users/x/orca/alpha")
        home = os.path.expanduser("~")
        self.af("todo", "where", "alpha", "pc2", home + "/orca/alpha")
        self.assertEqual(self.todo_line("alpha").count(" | on "), 1, self.todo_line("alpha"))
        self.assertEqual(self.row(self.rows(), task="alpha")["Where"], "pc2, ~/orca/alpha")

    def test_machine_only(self):
        self.add("alpha", "the login form", 60)
        self.af("todo", "where", "alpha", "pc2")
        self.assertEqual(self.row(self.rows(), task="alpha")["Where"], "pc2")

    def test_refusals(self):
        self.add("alpha", "the login form", 60)
        for args in (("todo", "where", "nobody", "pc2"),
                     ("todo", "where", "alpha"),
                     ("todo", "where", "alpha", "my laptop"),
                     ("todo", "where", "alpha", "pc2", "/a | b")):
            with self.subTest(args=args):
                self.refused(*args)

    def test_from_agent_worktree_txt_when_not_recorded(self):
        here = self.repo.make_worktree("alpha", as_repo=False)
        self.add("alpha", "the login form", 60)
        self.add("beta", "bank recon match", 60)
        self.add("gamma", "stock lock page", 60)
        self.worktree_lines((here, "alpha", "working"),
                            ("/nowhere/beta", "beta", "working"))
        rows = self.rows()
        self.assertEqual(self.row(rows, task="alpha")["Where"], "pc2, " + here)
        self.assertEqual(self.row(rows, task="beta")["Where"], "/nowhere/beta")
        self.assertEqual(self.row(rows, task="gamma")["Where"], "-")


# ---------------------------------------------------------------- park, worker


class TestPark(BoardCase):
    def test_add_list_rm(self):
        self.af("park", "add", "which DB for reports?", now="2026-11-02 14:00")
        self.af("park", "add", "keep the old API?", "alpha", now="2026-11-02 14:30")
        text = self.state_text()
        self.assertIn("PARKED: which DB for reports? | project | since 2026-11-02 14:00\n", text)
        self.assertIn("PARKED: keep the old API? | alpha | since 2026-11-02 14:30\n", text)
        listed = self.af("park", "list").stdout
        self.assertRegex(listed, r"(?m)^1\. .*which DB for reports\?")
        self.assertRegex(listed, r"(?m)^2\. .*keep the old API\?")
        rows = self.rows()
        r = self.row(rows, what="which DB for reports?")
        self.assertEqual((r["Task"], r["Status"], r["Wait"], r["Where"]),
                         ("project", self.st("parked"), "1h", "pc2, " + self.repo.dir))
        self.assertEqual(self.row(rows, what="keep the old API?")["Task"], "alpha")
        self.af("park", "rm", "1")
        text = self.state_text()
        self.assertNotIn("which DB", text)
        self.assertIn("keep the old API?", text)

    def test_other_lines_of_the_state_stay(self):
        self.state("Brief from the main manager: you are the task manager.\nSTEP 3 done.")
        self.af("park", "add", "which DB?")
        self.af("park", "rm", "1")
        self.assertEqual(self.state_text(),
                         "Brief from the main manager: you are the task manager.\nSTEP 3 done.\n")

    def test_refusals(self):
        self.af("park", "add", "which DB?")
        for args in (("park", "add", ""), ("park", "add", "a | b"), ("park", "rm", "9"),
                     ("park", "rm", "x"), ("park", "rm", "0")):
            with self.subTest(args=args):
                self.refused(*args)

    def test_list_when_empty(self):
        result = self.af("park", "list")
        self.assertEqual(result.returncode, 0)


class TestWorker(BoardCase):
    def test_on_off(self):
        self.af("worker", "on", "1", "hook script", now="2026-11-02 14:30")
        self.assertIn("WORKER 1: hook script | since 2026-11-02 14:30\n", self.state_text())
        r = self.row(self.rows(), task="project 工人 1")
        self.assertEqual((r["What"], r["Status"], r["Work"], r["Where"]),
                         ("hook script", self.st("running"), "30m", "pc2, " + self.repo.dir))
        self.af("worker", "on", "1", "board script", now="2026-11-02 14:40")
        self.assertEqual(self.state_text().count("WORKER 1:"), 1)
        self.assertIn("WORKER 1: board script | since 2026-11-02 14:40", self.state_text())
        self.af("worker", "off", "1")
        self.assertNotIn("WORKER 1", self.state_text())

    def test_refusals(self):
        self.af("worker", "on", "1", "hook script")
        for args in (("worker", "off", "2"), ("worker", "on", "x", "slice"),
                     ("worker", "on", "0", "slice"), ("worker", "on", "2"),
                     ("worker", "on", "2", "a | b"), ("worker", "maybe", "1")):
            with self.subTest(args=args):
                self.refused(*args)


class TestWorkerEnglish(BoardCase):
    lang = "en"

    def test_the_worker_row_in_english(self):
        self.af("worker", "on", "2", "board script", now="2026-11-02 14:30")
        self.assertEqual(self.row(self.rows(), task="project worker 2")["Status"], "running")


# ---------------------------------------------------------------- OWNER TODO


class TestOwnerTodo(BoardCase):
    ITEMS = ("OWNER TODO: check the phone build\n"
             "- OWNER TODO sign the form\n"
             "* OWNER TODO: pay the bill\n"
             "2026-11-01 09:00 OWNER TODO: renew the domain\n"
             "decision 14:00: merged. OWNER TODO: try it on the phone\n")
    MENTIONS = ('the owner\'s own OWNER TODO items from agent_state.txt (lines containing "OWNER TODO")\n'
                'lines with "OWNER TODO" are shown\n'
                "owner todo: lowercase is not the marker\n"
                "- Table contents: every open task, the OWNER TODO items\n")

    def test_items_and_mentions(self):
        self.state(self.MENTIONS + self.ITEMS)
        rows = [r for r in self.rows() if r["Status"] == self.st("owner")]
        self.assertEqual(sorted(r["What"] for r in rows),
                         sorted(["check the phone build", "sign the form", "pay the bill",
                                 "renew the domain", "try it on the phone"]))
        dated = self.row(rows, what="renew the domain")
        self.assertEqual((dated["Task"], dated["Where"], dated["Wait"], dated["Est"],
                          dated["Work"], dated["Done by"]),
                         ("-", "-", "1d 6h", "-", "-", "-"))
        self.assertEqual(self.row(rows, what="check the phone build")["Wait"], "-")


# ---------------------------------------------------------------- order


class TestSort(BoardCase):
    def test_the_groups_and_oldest_first(self):
        self.add("run-new", "the newer running task", 600, opened="2026-11-02 12:00")
        self.add("run-old", "the older running task", 600, opened="2026-11-02 10:00")
        self.add("mock-late", "waits on a mock since two", 600, opened="2026-11-02 09:00")
        self.wait("mock-late", "on", "mock", now="2026-11-02 14:00")
        self.add("review-early", "waits on a review since one", 600, opened="2026-11-02 11:00")
        self.wait("review-early", "on", "review", now="2026-11-02 13:00")
        self.add("held", "held behind a final stage", 600, opened="2026-11-02 08:00")
        self.wait("held", "on", "hold", now="2026-11-02 14:30")
        self.add("queued", "waits for a slot", 600, opened="2026-11-02 09:00")
        self.wait("queued", "on", "queue", now="2026-11-02 13:30")
        self.state("OWNER TODO: check the phone build\n"
                   "2026-11-01 09:00 OWNER TODO: renew the domain\n")
        self.af("park", "add", "which DB for reports?", now="2026-11-02 12:00")
        self.af("park", "add", "keep the old API?", now="2026-11-02 11:00")
        self.af("worker", "on", "1", "a worker slice", now="2026-11-02 11:30")
        got = [r["What"] for r in self.rows()]
        self.assertEqual(got, [
            "waits on a review since one", "waits on a mock since two",
            "the older running task", "a worker slice", "the newer running task",
            "waits for a slot", "held behind a final stage",
            "renew the domain", "check the phone build",
            "keep the old API?", "which DB for reports?"])

    def test_a_helper_runs_too(self):
        here = self.repo.make_worktree("helper", as_repo=False)
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            fh.write("%s | task manager, human-direct | task: Stock Lock Page | "
                     "since 2026-11-02 13:00\n" % here)
        r = self.row(self.rows(), task="project Helper")
        self.assertEqual((r["What"], r["Status"], r["Where"], r["Work"]),
                         ("Stock Lock Page", self.st("running"), "pc2, " + here, "-"))


# ---------------------------------------------------------------- cells


class TestCells(BoardCase):
    def test_no_estimate(self):
        self.add("noest", "a task with no estimate", None, opened="2026-11-02 14:00")
        r = self.row(self.rows(), task="noest")
        self.assertEqual((r["Est"], r["Work"], r["Wait"], r["Done by"]), ("-", "1h", "0m", "-"))

    def test_over_the_estimate(self):
        self.add("late", "a task past its estimate", 30, opened="2026-11-02 14:00")
        self.assertEqual(self.row(self.rows(), task="late")["Done by"], "超出估时")

    def test_done_tomorrow_and_later(self):
        self.add("night", "finishes after midnight", 60, opened="2026-11-02 23:20")
        self.add("long", "a long one", 3000, opened="2026-11-02 23:50")
        rows = self.rows(now="2026-11-02 23:50")
        self.assertEqual(self.row(rows, task="night")["Done by"], "明天 00:20")
        self.assertEqual(self.row(rows, task="long")["Done by"], "2026-11-05 01:50")

    def test_minutes_read_as_real_units(self):
        for name, est, want in (("a", 45, "45m"), ("b", 60, "1h"), ("c", 95, "1h 35m"),
                                ("d", 1440, "1d"), ("e", 1530, "1d 1h")):
            self.add(name, "task " + name, est, opened=NOW)
        rows = self.rows()
        for name, est, want in (("a", 45, "45m"), ("b", 60, "1h"), ("c", 95, "1h 35m"),
                                ("d", 1440, "1d"), ("e", 1530, "1d 1h")):
            with self.subTest(est=est):
                self.assertEqual(self.row(rows, task=name)["Est"], want)
                self.assertEqual(self.row(rows, task=name)["Work"], "0m")

    def test_a_long_what_is_cut_at_a_word(self):
        long_what = ("owner: main manager at start and when the last task closes cleans "
                     "its own repo's unused worktrees and branches on both machines")
        self.add("long", long_what, 60)
        what = self.row(self.rows(), task="long")["What"]
        self.assertLessEqual(len(what), 60)
        self.assertTrue(what.endswith("…"), what)
        self.assertTrue(long_what.startswith(what[:-1].rstrip()), what)
        self.assertTrue(long_what[len(what[:-1].rstrip())] == " ", what)

    def test_a_pipe_is_escaped(self):
        self.add("pipe", "read a|b from the file", 60)
        out = self.board()
        self.assertIn("read a\\|b from the file", out)
        self.assertEqual(self.row(self.table(out), task="pipe")["What"], "read a\\|b from the file")

    def test_nothing_open(self):
        self.assertEqual(self.board().strip(), "无")

    def test_unknown_option_is_refused(self):
        self.refused("board", "--everything")


class TestCellsEnglish(BoardCase):
    lang = "en"

    def test_headers_and_words(self):
        self.add("late", "a task past its estimate", 30, opened="2026-11-02 14:00")
        self.add("night", "finishes after midnight", 60, opened="2026-11-02 14:50")
        self.add("long", "a long one", 3000, opened="2026-11-02 15:00")
        rows = self.rows(now="2026-11-02 15:00")
        self.assertEqual(self.row(rows, task="late")["Done by"], "over est")
        self.assertEqual(self.row(rows, task="night")["Done by"], "15:50")
        self.assertEqual(self.row(rows, task="long")["Done by"], "17:00 on 2026-11-04")
        rows = self.rows(now="2026-11-02 23:59")
        self.assertEqual(self.row(rows, task="long")["Done by"], "17:00 on 2026-11-04")

    def test_tomorrow(self):
        self.add("night", "finishes after midnight", 60, opened="2026-11-02 23:20")
        self.assertEqual(self.row(self.rows(now="2026-11-02 23:50"), task="night")["Done by"],
                         "00:20 tomorrow")

    def test_nothing_open(self):
        self.assertEqual(self.board().strip(), "none")


class TestOtherLanguageIsEnglish(BoardCase):
    lang = "en"

    def test_fr(self):
        self.repo.set_conf("language", "fr")
        self.add("alpha", "the login form", 60)
        self.table(self.board())   # en headers


# ---------------------------------------------------------------- the whole repo


class TestWholeRepo(BoardCase):
    def test_local_worktrees_are_read_and_far_ones_noted(self):
        alpha = self.repo.make_worktree("alpha", as_repo=False)
        self.state("PARKED: keep the old API? | alpha | since 2026-11-02 14:00\n"
                   "WORKER 2: board script | since 2026-11-02 14:40\n", folder=alpha)
        self.add("alpha", "the login form", 60)
        self.add("beta", "bank recon match", 60)
        self.worktree_lines((alpha, "alpha", "working"), ("/nowhere/beta", "beta", "working"))
        out = self.board()
        rows = self.table(out)
        r = self.row(rows, what="keep the old API?")
        self.assertEqual((r["Task"], r["Status"], r["Where"]),
                         ("alpha", self.st("parked"), "pc2, " + alpha))
        w = self.row(rows, task="wt_alpha 工人 2")
        self.assertEqual((w["What"], w["Work"]), ("board script", "20m"))
        self.assertIn("不在本机，未读：/nowhere/beta", out.splitlines()[-1])

    def test_run_from_a_worktree_it_still_reads_the_main_repo(self):
        wt = self.repo.detach_scripts_to_worktree()
        self.add("alpha", "the login form", 60)
        self.assertEqual(self.row(self.rows(cwd=wt), task="alpha")["What"], "the login form")

    def test_it_writes_nothing(self):
        alpha = self.task_worktree("alpha")
        self.add("alpha", "the login form", 60)
        self.wait("alpha", "on", "mock", now="2026-11-02 14:30")
        self.state("OWNER TODO: check the phone build")
        self.state("WORKER 1: hook | since 2026-11-02 14:00", folder=alpha)

        def snapshot():
            rows = []
            for dirpath, _, names in os.walk(self.repo.base):
                for name in names:
                    full = os.path.join(dirpath, name)
                    st = os.stat(full)
                    rows.append((full, st.st_size, st.st_mtime_ns))
            return sorted(rows)
        before = snapshot()
        self.board()
        self.board("--self", cwd=alpha)
        self.assertEqual(snapshot(), before)


# ---------------------------------------------------------------- --self


class TestSelf(BoardCase):
    def setUp(self):
        super().setUp()
        self.alpha = self.task_worktree("alpha")

    def test_its_own_task_and_workers_only(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.add("beta", "bank recon match", 60)
        self.state("OWNER TODO: check the phone build\n"
                   "PARKED: main's own question | project | since 2026-11-02 14:00\n")
        self.af("worker", "on", "1", "hook script", now="2026-11-02 14:30", cwd=self.alpha)
        self.af("park", "add", "keep the old API?", now="2026-11-02 14:40", cwd=self.alpha)
        rows = self.rows("--self", cwd=self.alpha)
        self.assertEqual(sorted(r["Task"] for r in rows), ["alpha", "alpha", "alpha 工人 1"])
        r = self.row(rows, task="alpha", what="the login form")
        self.assertEqual((r["Status"], r["Where"], r["Work"], r["Done by"]),
                         (self.st("running"), "pc2, " + self.alpha, "1h", "超出估时"))
        self.assertEqual(self.row(rows, what="keep the old API?")["Status"], self.st("parked"))
        self.assertIn("PARKED: keep the old API? | alpha | since", self.state_text(self.alpha))

    def test_no_todo_line_here_reads_its_todo_line_in_the_state(self):
        self.state("Brief from the main manager: you are the task manager for \"alpha\".\n"
                   "TODO LINE: alpha | big | the login form | est 60m | opened 2026-11-02 14:30 | by main\n",
                   folder=self.alpha)
        r = self.row(self.rows("--self", cwd=self.alpha), task="alpha")
        self.assertEqual((r["What"], r["Est"], r["Work"], r["Done by"]),
                         ("the login form", "1h", "30m", "15:30"))

    def test_nothing_at_all_is_one_bare_row(self):
        rows = self.rows("--self", cwd=self.alpha)
        self.assertEqual(rows, [{"Task": "alpha", "What": "-", "Status": self.st("running"),
                                 "Where": "pc2, " + self.alpha, "Est": "-", "Work": "-",
                                 "Wait": "-", "Done by": "-"}])

    def test_a_helper_in_the_main_repo_never_shows_the_main_state(self):
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            fh.write("%s | task manager, human-direct | task: Stock Lock Page | "
                     "since 2026-11-02 13:00\n" % self.repo.dir)
        self.state("OWNER TODO: check the phone build\n"
                   "PARKED: main's own question | project | since 2026-11-02 14:00\n"
                   "WORKER 3: main's worker | since 2026-11-02 14:00\n")
        rows = self.rows("--self", cwd=self.repo.dir)
        self.assertEqual([(r["Task"], r["What"]) for r in rows],
                         [("project Helper", "Stock Lock Page")])


if __name__ == "__main__":
    unittest.main()
