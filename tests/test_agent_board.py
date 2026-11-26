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
marker OWNER TODO: (capitals, then the colon) anywhere in it; a quote mark
right before it makes it a mention. Without the colon it is only a mention
(a note about the rule is not an item: found on the real state file). The
item text is what follows the colon. A "YYYY-MM-DD[ HH:MM]" stamp at the start
of the line (after spaces or a "-" / "*" bullet) is its date.

    board            the whole repo (main manager)
    board --self     the session's own task (task manager, Helper)

Read only: writes nothing, touches nothing. Prints one GitHub markdown table
(or one line "无" / "none" when there is no row), then note lines.
Columns, in the agent.conf language (zh, else en):
    zh  任务 | 内容 | 状态 | 进度 | 位置 | 检查 | 估时 | 已工作 | 已等待 | 预计完成
    en  Task | What | Status | Progress | Where | Checks | Est | Work | Wait | Done by
    (检查 / Checks: check-blocks, the checks field; an old line "level <X>"; R8 text: tests/test_rules_text.py)
    (进度 / Progress: progress-bar, TestProgressColumn below)

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

Status (zh / en):
    running   进行中           running        (tasks, Helpers, workers)
    OWNER TODO  你的待办       your to-do
    PARKED    搁置的问题       parked question
    a wait, a queue, a hold, a line not started: board-waiting (owner 2026-11-20),
    requirements/board-waiting.md and TestWaitingRow below:
    waiting   等待 <who> · <what> · 已等 <n>     waiting <who> · <what> · waited <n>
    hold      暂缓 · <what> · 已等 <n>            hold · <what> · waited <n>
    queue     排队 · 在 <task> 之后               queue · after <task>
    not started  未开始                           not started
    (their progress, est, work, wait and done by cells are "-"; est stays on a not started row)
Sort: waiting on the owner, running, waiting on others, queued and not started, held, OWNER TODO, parked.
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
    work      from the first stage ("started", board-waiting rule 6) to now, minus the waits after it;
              no started field: clock from opened to now, minus wait, when the line has a stage,
              else "-" (task, 0 at least);
              since -> now (worker); "-" for the rest
    done by   now + est - work, as "HH:MM" today, zh "明天 HH:MM" /
              en "HH:MM tomorrow", later zh "YYYY-MM-DD HH:MM" /
              en "HH:MM on YYYY-MM-DD"; work >= est -> zh "超出 <n>m" /
              en "over by <n>m" (n = work - est, real units); with a stage
              record: TestProgressColumn below; no est -> "-"
    minutes   "45m", "1h", "1h 35m", "1d", "1d 1h" (a day or more: no minutes)
    unknown   "-"

AGENT_FAKE_NOW="YYYY-MM-DD HH:MM" replaces the clock, AGENT_FAKE_HOST the
machine name (tests). Unset: the real clock, the short host name.
"""

import contextlib
import importlib.util
import io
import os
import re
import subprocess
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase
import json  # noqa: E402
from scripthelp import ROOT  # noqa: E402
from watchhelp import dead_pid  # noqa: E402
import signal  # noqa: E402
import time  # noqa: E402

NOW = "2026-11-02 15:00"
HOST = "pc2"
# 检查 / Checks: check-blocks (2026-11-25; was 级别 / Level), R8 text: tests/test_rules_text.py
HEAD = {"zh": ["任务", "内容", "状态", "进度", "位置", "检查", "估时", "已工作", "已等待", "预计完成"],
        "en": ["Task", "What", "Status", "Progress", "Where", "Checks", "Est", "Work", "Wait", "Done by"]}
# board-waiting (2026-11-20): a wait's status is built from parts (TestWaitingRow below)
STATUS = {
    "zh": {"running": "进行中", "hold": "暂缓", "queue": "排队", "owner": "你的待办",
           "parked": "搁置的问题", "not_started": "未开始"},
    "en": {"running": "running", "hold": "hold", "queue": "queue", "owner": "your to-do",
           "parked": "parked question", "not_started": "not started"},
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

    def af(self, *args, now=NOW, cwd=None, ok=True, real=False):
        # test-slim-2: a plain `board` / `board --self` runs agent_board.py in this process (board_py); real=True
        # starts agent-file.sh itself (the shell wrapper's own tests and the end-to-end test of TestBoardShell)
        if not real and args[:1] == ("board",) and set(args[1:]) <= {"--self"}:
            result = self.board_py(*args[1:], now=now, cwd=cwd)
        else:
            result = self.repo.run("agent-file.sh", *args, cwd=cwd,
                                   env={"AGENT_FAKE_NOW": now, "AGENT_FAKE_HOST": HOST})
        if ok:
            self.assertOk(result)
        return result

    # ---- the one in-process board and status line (test-slim-2) ----
    # agent-file.sh board and agent-statusline.sh only find the roots and the language, then start
    # agent_board.py. These helpers do the same in this process: no bash, no python start, no git
    # start for the main folder. Every board and status line test in the suite goes through them.

    def py_board(self, argv, env=None, stdin="", cwd=None):
        """bin/agent_board.py main() with this argv, the test environment, stdin text and working folder."""
        mod = getattr(self.repo, "_board_module", None)
        if mod is None:
            spec = importlib.util.spec_from_file_location("agent_board__inproc_%x" % id(self),
                                                          os.path.join(self.repo.plugin_bin, "agent_board.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.repo._board_module = mod
        full_env = self.repo._env(env)
        out, err = io.StringIO(), io.StringIO()
        here = os.getcwd()
        code = 0
        with mock.patch.dict(os.environ, full_env, clear=True), \
                mock.patch.object(sys, "stdin", io.StringIO(stdin or "")), \
                mock.patch.object(sys, "argv", ["agent_board.py"] + list(argv)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            os.chdir(cwd or self.repo.cwd)
            try:
                mod.main()
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
            finally:
                os.chdir(here)
        return subprocess.CompletedProcess(["agent_board.py"] + list(argv), code, out.getvalue(), err.getvalue())

    def board_py(self, *flags, now=NOW, cwd=None):
        """What `agent-file.sh board [--self]` prints: the roots as agent-roots.sh finds them, the language
        setting (zh, else en), then agent_board.py."""
        start = cwd if cwd and os.path.isdir(cwd) else self.repo.cwd
        start = os.path.realpath(start)
        root = state = start
        if os.path.realpath(self.repo.dir) != start:
            listing = subprocess.run(["git", "-C", start, "worktree", "list", "--porcelain"],
                                     capture_output=True, text=True).stdout
            first = [l[9:] for l in listing.splitlines() if l.startswith("worktree ")][:1]
            root = first[0] if first else start
            top = subprocess.run(["git", "-C", start, "rev-parse", "--show-toplevel"],
                                 capture_output=True, text=True).stdout.strip()
            state = top or start
        env = {"AGENT_FAKE_NOW": now, "AGENT_FAKE_HOST": HOST}
        import agent_conf
        try:
            lang = agent_conf.get("language", self.repo._env(env))
        except KeyError:
            lang = "en"
        lang = "zh" if lang == "zh" else "en"
        return self.py_board(["--root", root, "--state-dir", state, "--cwd", start, "--now", now,
                              "--lang", lang, "--host", HOST] + list(flags), env=env, cwd=start)

    def statusline_py(self, stdin, env=None, cwd=None):
        """What agent-statusline.sh prints (it only starts agent_board.py --statusline)."""
        return self.py_board(["--statusline"], env=env, stdin=stdin, cwd=cwd or self.repo.base)

    def refused(self, *args, now=NOW, cwd=None):
        files = {n: self.repo.read(n) for n in ("agent_todo.txt", "agent_state.txt")}
        result = self.af(*args, now=now, cwd=cwd, ok=False)
        self.assertEqual(result.returncode, 1, (args, result.stdout, result.stderr))
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
        self.assertEqual({n: self.repo.read(n) for n in files}, files, args)
        return result

    def add(self, name, what, est=None, opened="2026-11-02 14:00", size="big", started=True):
        """A todo line. started (board-waiting rule 6, work counts from the first stage): True -> the line
        gets " | started <opened>" (a task already under way, as these tests mean); a date -> that date;
        False -> none (a task that never started)."""
        args = ["todo", "add", name, size, what] + ([str(est)] if est is not None else [])
        self.af(*args, now=opened)
        if started:
            at = opened if started is True else started
            path = self.repo.path("agent_todo.txt")
            with open(path) as fh:
                lines = fh.read().splitlines()
            with open(path, "w") as fh:
                for line in lines:
                    if line.split(" | ")[0] == name:
                        line += " | started " + at
                    fh.write(line + "\n")

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
        self.assertEqual(len(sep), len(HEAD[self.lang]))
        for c in sep:
            self.assertRegex(c, r"^:?-{3,}:?$")
        rows = []
        for line in lines[2:]:
            row = cells(line)
            self.assertEqual(len(row), len(HEAD[self.lang]), line)
            rows.append(dict(zip(HEAD["en"], row)))
        return rows

    def rows(self, *args, **kw):
        return self.table(self.board(*args, **kw))

    def row(self, rows, task=None, what=None):
        # estimate-improve scope add (owner 2026-11-26): a line with an owner field shows "<task> [<name>]"
        for r in rows:
            name = re.sub(r" \[[^\]]*\]$", "", r["Task"])
            if (task is None or r["Task"] == task or name == task) and (what is None or r["What"] == what):
                return r
        self.fail("no row task=%r what=%r in %r" % (task, what, rows))

    def st(self, key):
        return STATUS[self.lang][key]


# ---------------------------------------------------------------- todo wait


class TestBoardShell(BoardCase):
    """test-slim-2: the board tests run agent_board.py in this process (board_py). This is the end-to-end
    start: agent-file.sh board itself prints the same, in both languages, for --self and from a worktree."""

    def fixture(self):
        alpha = self.task_worktree("alpha")
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.af("todo", "stage", "alpha", "verify")
        self.add("beta", "bank recon match", 40, opened="2026-11-02 14:00")
        return alpha

    def test_the_wrapper_and_the_in_process_board_print_the_same(self):
        alpha = self.fixture()
        for lang in ("zh", "en"):
            self.repo.set_conf("language", lang)
            for args, cwd in ((("board",), None), (("board", "--self"), alpha), (("board",), alpha)):
                with self.subTest(lang=lang, args=args, cwd=cwd):
                    real = self.af(*args, cwd=cwd, real=True)
                    fast = self.af(*args, cwd=cwd)
                    self.assertTrue(real.stdout.startswith("|"), real.stdout)
                    self.assertEqual((fast.stdout, fast.stderr, fast.returncode),
                                     (real.stdout, real.stderr, real.returncode))


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
        # board-waiting: a waiting row says how long it waits; its time cells are "-"
        self.assertEqual((r["Status"], r["Work"], r["Wait"], r["Done by"]),
                         ("等待 你 · 合并前签字 · 已等 30分钟", "-", "-", "-"))

    def test_a_new_wait_closes_the_open_one(self):
        self.add("gamma", "stock lock page", 60, opened="2026-11-02 14:00")
        self.wait("gamma", "on", "mock", now="2026-11-02 14:00")
        self.wait("gamma", "on", "question", "which DB?", now="2026-11-02 14:20")
        line = self.todo_line("gamma")
        self.assertIn(" | waited 20m", line)
        self.assertIn(" | waiting question since 2026-11-02 14:20: which DB?", line)
        self.assertEqual(line.count("waiting "), 1, line)
        r = self.row(self.rows(now="2026-11-02 14:30"), task="gamma")
        # board-waiting: one run of waits since 14:00 (no work between)
        self.assertEqual(r["Status"], "等待 你 · which DB? · 已等 30分钟")
        self.assertEqual(r["Wait"], "-")
        self.assertEqual(r["Work"], "-")

    def test_held_and_queued(self):
        self.add("held-one", "font size option", 30)
        self.add("queued-one", "report export", 30)
        self.wait("held-one", "on", "hold", now="2026-11-02 14:10")
        self.wait("queued-one", "on", "queue", now="2026-11-02 14:20")
        rows = self.rows()
        self.assertEqual(self.row(rows, task="held-one")["Status"], self.st("hold") + " · 已等 50分钟")
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
        self.assertIn("PARKED: which DB for reports? | project | since 2026-11-02 14:00 | by t\n", text)
        self.assertIn("PARKED: keep the old API? | alpha | since 2026-11-02 14:30 | by t\n", text)
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
             "- OWNER TODO: sign the form\n"
             "* OWNER TODO: pay the bill\n"
             "2026-11-01 09:00 OWNER TODO: renew the domain\n"
             "decision 14:00: merged. OWNER TODO: try it on the phone\n")
    MENTIONS = ('the owner\'s own OWNER TODO items from agent_state.txt (lines containing "OWNER TODO")\n'
                'lines with "OWNER TODO" are shown\n'
                "owner todo: lowercase is not the marker\n"
                "- Table contents: every open task, the OWNER TODO items\n"
                "- OWNER TODO sign the form, no colon: only a mention\n"
                "- OWNER TODO item = line with OWNER TODO in capitals, not right after a quote mark\n"
                "OWNER TODO items from agent_state.txt\n")

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
        # progress-bar (owner 2026-11-11): over the estimate with no stage says by how much
        self.assertEqual(self.row(self.rows(), task="late")["Done by"], "超出 30m")

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
        self.assertEqual(self.row(rows, task="late")["Done by"], "over by 30m")
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
        # the board runs in this process (test-slim-2): its first import of the copy's bin/*.py would make Python
        # itself write bin/__pycache__/*.pyc into the copy; that is the interpreter, not the board, so it is off here
        with mock.patch.object(sys, "dont_write_bytecode", True):
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
        # the todo row's Task cell carries its owner bracket (scope add 2026-11-26; the test repo's git name is t)
        self.assertEqual(sorted(r["Task"] for r in rows), ["alpha", "alpha [t]", "alpha 工人 1"])
        r = self.row(rows, task="alpha", what="the login form")
        self.assertEqual((r["Status"], r["Where"], r["Work"], r["Done by"]),
                         (self.st("running"), "pc2, " + self.alpha, "1h", "超出 0m"))
        self.assertEqual(self.row(rows, what="keep the old API?")["Status"], self.st("parked"))
        self.assertIn("PARKED: keep the old API? | alpha | since", self.state_text(self.alpha))

    def test_no_todo_line_here_reads_its_todo_line_in_the_state(self):
        # board-waiting: a line with no stage is not started; its STAGE line makes it run
        self.state("Brief from the main manager: you are the task manager for \"alpha\".\n"
                   "TODO LINE: alpha | big | the login form | est 60m | opened 2026-11-02 14:30 | by main\n"
                   "STAGE alpha: brief | since 2026-11-02 14:30\n",
                   folder=self.alpha)
        r = self.row(self.rows("--self", cwd=self.alpha), task="alpha")
        self.assertEqual((r["What"], r["Est"], r["Work"], r["Done by"]),
                         ("the login form", "1h", "30m", "15:30"))

    def test_nothing_at_all_is_one_bare_row(self):
        rows = self.rows("--self", cwd=self.alpha)
        self.assertEqual(rows, [{"Task": "alpha", "What": "-", "Status": self.st("running"),
                                 "Progress": "-", "Where": "pc2, " + self.alpha, "Checks": "-", "Est": "-", "Work": "-",
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


class TestBoardLevel(BoardCase):
    """check-blocks: the column is Checks (zh 检查); an old level line shows "level <X>"."""
    lang = "en"

    def test_the_column_sits_after_where(self):
        self.assertEqual(HEAD["zh"][4:7], ["位置", "检查", "估时"])
        self.assertEqual(HEAD["en"][4:7], ["Where", "Checks", "Est"])

    def test_the_cells(self):
        self.af("todo", "add", "lv", "big", "with a level", "60", "--level", "C", now="2026-11-02 14:00")
        self.af("todo", "add", "ck", "big", "with checks", "60", "--checks", "UI CHECK,PR REVIEW",
                now="2026-11-02 14:00")
        self.add("nolv", "an old line", est=30)
        self.state("PARKED: a question | lv | since 2026-11-02 14:10")
        rows = self.rows()
        self.assertEqual(self.row(rows, task="lv")["Checks"], "level C")
        self.assertEqual(self.row(rows, task="ck")["Checks"], "PR REVIEW, UI CHECK")
        self.assertEqual(self.row(rows, task="nolv")["Checks"], "-")
        for r in rows:
            if re.sub(r" \[[^\]]*\]$", "", r["Task"]) not in ("lv", "ck", "nolv"):   # the owner bracket (scope add)
                self.assertEqual(r["Checks"], "-", r)

    def test_an_old_number_line_shows_its_type(self):
        for old, typ in (("0", "A"), ("1", "B"), ("3", "C"), ("4", "D")):
            with self.subTest(old=old):
                self.af("todo", "add", "o" + old, "big", "an old line", "60", now="2026-11-02 14:00")
                path = self.repo.path("agent_todo.txt")
                with open(path) as fh:
                    text = fh.read()
                with open(path, "w") as fh:
                    fh.write(text.replace("est 60m |", "est 60m | level %s |" % old))
                self.assertEqual(self.row(self.rows(), task="o" + old)["Checks"], "level " + typ)

    def test_zh_header(self):
        self.repo.set_conf("language", "zh")
        self.add("nolv", "an old line", est=30)
        head = [l for l in self.board().splitlines() if l.startswith("|")][0]
        self.assertEqual(cells(head), HEAD["zh"])


def status_file(repo):
    return repo.path(".git", "agent_watch.json")


def write_watch(repo, pid=None, sweep=NOW, interval=5, tasks=None, orphans=()):
    data = {"pid": os.getpid() if pid is None else pid, "started": "2026-11-02 13:00", "sweep": sweep,
            "interval_min": interval, "tasks": tasks or {}, "orphans": list(orphans)}
    with open(status_file(repo), "w") as fh:
        json.dump(data, fh)


def task_entry(path, watched=True, why="", changed=None, confirmed=None, pane="term_x"):
    return {"path": path, "env": None, "pane": pane, "shell": None, "watched": watched, "why": why,
            "signals": 0, "confirmed": confirmed, "changed": changed, "stall": None}


class WatchBoardCase(BoardCase):
    def setUp(self):
        super().setUp()
        self.alpha = self.repo.make_worktree("alpha", as_repo=False)
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:30")
        self.worktree_lines((self.alpha, "alpha", "working"))

    def watch(self, **kw):
        tasks = kw.pop("tasks", None)
        if tasks is None:
            tasks = {"alpha": task_entry(self.alpha, **{k: kw.pop(k) for k in list(kw)
                                                       if k in ("watched", "why", "changed", "confirmed")})}
        write_watch(self.repo, tasks=tasks, **kw)

    def status_of(self, task="alpha", **kw):
        return self.row(self.rows(**kw), task=task)["Status"]

    def warn(self, n):
        return " · 未确认 %dm" % n if self.lang == "zh" else " · not confirmed %dm" % n


MAIN_PID = "424242"


FIRST = "Board warning for the main manager, act in this turn:"


def warn_watch(plugin):
    return "WARN watch not running -> start it now: %s/bin/agent-watch.sh --all (Bash run_in_background)" % plugin


def warn_quiet(task, n):
    return ("WARN not confirmed %s (%dm) -> read its pane or its newest state line, then fix the record or the agent"
            % (task, n))


def warn_orphan(path):
    return "WARN pane without a task line %s -> add the todo line or close the pane" % path


GHOST = {"path": "/x/ghost", "title": "◑ ghost Task Manager", "handle": "term_g"}


class TestNextWarns(WatchBoardCase):
    lang = "en"

    def next_lines(self, now=NOW):
        return self.af("next", now=now).stdout.splitlines()

    def warns(self, lines):
        return [l for l in lines if l.startswith("WARN ")]

    def test_watch_not_running(self):
        self.assertEqual(self.warns(self.next_lines()), [warn_watch(self.repo.plugin)])

    def test_not_confirmed(self):
        self.watch(changed="2026-11-02 14:40", confirmed="2026-11-02 14:59")
        self.assertEqual(self.warns(self.next_lines()), [warn_quiet("alpha", 20)])

    def test_pane_without_a_task_line(self):
        self.watch(changed="2026-11-02 14:58", orphans=[GHOST])
        self.assertEqual(self.warns(self.next_lines()), [warn_orphan("/x/ghost")])

    def test_all_confirmed_no_warn(self):
        self.watch(changed="2026-11-02 14:58")
        self.assertEqual(self.warns(self.next_lines()), [])

    def test_warns_come_last(self):
        self.watch(changed="2026-11-02 14:40", orphans=[GHOST])
        lines = self.next_lines()
        self.assertTrue(lines[0].startswith("NEXT: "), lines)
        firsts = [i for i, l in enumerate(lines) if l.startswith("WARN ")]
        self.assertEqual(firsts, list(range(len(lines) - len(firsts), len(lines))))
        self.assertEqual(self.warns(lines), [warn_quiet("alpha", 20), warn_orphan("/x/ghost")])

    def test_plain_runtime_has_no_warn(self):
        self.repo.set_conf("runtime", "plain")
        self.assertEqual(self.warns(self.next_lines()), [])


class TestWarnHook(WatchBoardCase):
    lang = "en"
    script = "agent-board-warn.sh"

    def setUp(self):
        super().setUp()
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%s 2026-11-02 13:00 s1 term_m\n" % MAIN_PID)

    def hook(self, event="UserPromptSubmit", now=NOW, main=True):
        env = {"AGENT_FAKE_NOW": now, "AGENT_FAKE_HOST": HOST}
        env.update({"CLAUDE_PID": MAIN_PID} if main else {"CLAUDE_PID": "999999", "AGENT_ROLE": "task-manager"})
        payload = {"hook_event_name": event, "session_id": "s1", "cwd": self.repo.dir}
        if event == "UserPromptSubmit":
            payload["prompt"] = "go on"
        else:
            payload.update({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        r = self.repo.run("agent-board-warn.sh", stdin=json.dumps(payload), env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def test_a_new_warning_reaches_the_main_manager(self):
        out = self.hook()
        self.assertEqual(out.splitlines(), [FIRST, warn_watch(self.repo.plugin)])

    def test_post_tool_use_gives_additional_context(self):
        data = json.loads(self.hook("PostToolUse"))
        spec = data["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PostToolUse")
        self.assertEqual(spec["additionalContext"].splitlines(), [FIRST, warn_watch(self.repo.plugin)])

    def test_the_same_set_is_said_once(self):
        self.assertTrue(self.hook())
        self.assertEqual(self.hook(), "")
        self.assertEqual(self.hook("PostToolUse", now="2026-11-02 15:05"), "")

    def test_a_changed_set_is_said_again_at_most_once_a_minute(self):
        self.assertTrue(self.hook())
        self.watch(changed="2026-11-02 14:58", orphans=[GHOST])        # watch up: a new set
        self.assertEqual(self.hook(now=NOW), "")                       # same minute: held
        out = self.hook(now="2026-11-02 15:01")
        self.assertEqual(out.splitlines(), [FIRST, warn_orphan("/x/ghost")])

    def test_cleared_then_back_is_said_again(self):
        self.assertTrue(self.hook())
        self.watch(changed="2026-11-02 14:59")
        self.assertEqual(self.hook(now="2026-11-02 15:01"), "")
        self.watch(changed="2026-11-02 14:59", orphans=[GHOST])
        self.assertTrue(self.hook(now="2026-11-02 15:02"))

    def test_only_the_main_manager(self):
        self.assertEqual(self.hook(main=False), "")

    def test_not_a_subagent_of_the_main_manager(self):
        # core review defect 14: a deputy runs in the main manager's process; its payload has agent_id
        env = {"AGENT_FAKE_NOW": NOW, "AGENT_FAKE_HOST": HOST, "CLAUDE_PID": MAIN_PID}
        payload = {"hook_event_name": "PostToolUse", "session_id": "s1", "cwd": self.repo.dir,
                   "agent_id": "a123", "agent_type": "auto-pipeline:merge-deputy",
                   "tool_name": "Bash", "tool_input": {"command": "ls"}}
        r = self.repo.run("agent-board-warn.sh", stdin=json.dumps(payload), env=env)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertTrue(self.hook(), "the subagent's call must not use up the main manager's warning")

    def test_a_growing_quiet_time_is_the_same_warning(self):
        self.watch(changed="2026-11-02 14:40", confirmed="2026-11-02 14:59")
        self.assertEqual(self.hook().splitlines(), [FIRST, warn_quiet("alpha", 20)])
        self.assertEqual(self.hook(now="2026-11-02 15:05"), "", "only the minutes changed")

    def test_no_orca_calls(self):
        self.repo.clear_calls()
        self.hook()
        self.assertEqual(self.repo.calls(), [])

    def test_registered_for_prompts_and_tool_calls(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json")) as fh:
            hooks = json.load(fh)["hooks"]
        for event in ("UserPromptSubmit", "PostToolUse"):
            with self.subTest(event=event):
                cmds = [h["command"] for group in hooks[event] for h in group["hooks"]]
                self.assertTrue([c for c in cmds if "bin/agent-board-warn.sh" in c], cmds)


def only_own(cls):
    """A subclass of a test class with tests: keep only the tests written in the subclass itself."""
    own = set(vars(cls))
    for name in dir(cls):
        if name.startswith("test") and name not in own:
            setattr(cls, name, None)
    return cls


@only_own
class TestF8TheBoardIsBuiltAtMostOnceAMinute(TestWarnHook):
    def test_inside_the_minute_the_board_is_not_built(self):
        self.hook()
        marker = os.path.join(self.repo.base, "board_imported")
        with open(os.path.join(self.repo.plugin, "bin", "agent_board.py"), "a") as fh:
            fh.write("\nopen(%r, 'w').close()\n" % marker)
        self.assertEqual(self.hook(), "")                       # the same minute
        self.assertFalse(os.path.exists(marker), "the board was built again inside the minute")
        with open(self.repo.path(".git", "agent_warn_seen.json")) as fh:
            self.assertIn("checked", json.load(fh))


NOW_NOV20_1231 = "2026-11-20 12:31"


P = "/x/orca/workspaces/auto-pipeline/state-trim"


WHERE_ST = "maverick-pc2, " + P


ST_RUN = ("state-trim | big | State file trim + auto clear at compact_clear_at | est 70m | guess 70m | level 4 | "
          "opened 2026-11-20 11:20 | by main | on maverick-pc2 %s | started 2026-11-20 11:24 | waited 38m | "
          "stage tests since 2026-11-20 12:21" % P)


ST_REVIEW = ("state-trim | big | State file trim + auto clear at compact_clear_at | est 70m | guess 70m | level 4 | "
             "opened 2026-11-20 11:20 | by main | on maverick-pc2 %s | started 2026-11-20 11:24 | waited 38m | "
             "stage verify since 2026-11-20 12:10 | waiting review since 2026-11-20 12:26" % P)


V4 = ("v4plus-followups | small | Cross-repo asks to the v4-plus Manager | est 5m | guess 5m | "
      "opened 2026-11-16 15:46 | by main | cross v4-plus | "
      "waiting hold since 2026-11-16 15:47: 回复插件更新和同步脚本 | who v4-Manager")


PC2 = ("pc2-plugin-update | small | Update auto-pipeline user-scope plugin on pc2 | est 5m | guess 5m | "
       "opened 2026-11-17 17:21 | by main | on maverick-pc2 | cross v4-plus | waited 895m | "
       "waiting hold since 2026-11-18 08:16: pc2 空闲时更新 plugin | who v4-Manager")


UT = ("usage-track | big | Track tied repos | est 49m | guess 50m | opened 2026-11-16 17:31 | by main | "
      "waiting hold since 2026-11-16 17:31: 你说合并监控之后再做")


BW = ("board-waiting | big | Board waiting status | est 39m | guess 40m | level 3 | opened 2026-11-20 11:35 | "
      "by main | waiting queue since 2026-11-20 11:35 | after state-trim")


# pc2's real agent_todo.txt of 2026-11-20 (old lines: no who, no after, no started)
REAL = [
    "v4plus-followups | small | Cross-repo asks to the v4-plus Manager (owner 2A 4A 2026-11-16): update v4-plus "
    "project scope to plugin 0.34.1 + restart at a quiet point; consider the 15-min production sync as a plain "
    "script (agent only on failure); idle v4-plus-sync sessions pile up | est 5m | guess 5m | opened 2026-11-16 "
    "15:46 | by main | cross v4-plus | waiting hold since 2026-11-16 15:47: v4-Manager: not now, ledger rollout "
    "final suite + staging; update after owner confirms in its chat; sync script = later task for owner",
    "usage-track | big | Track tied repos (v4-plus first): housekeep prints a USAGE block per repo (plugin scope "
    "version, state file size, monitor alive, completed data gaps) at no agent cost, and flags the weekly deep "
    "audit as due (next 2026-11-23). Owner 3A 2026-11-16 | est 49m | guess 50m | opened 2026-11-16 17:31 | by "
    "main | waiting hold since 2026-11-16 17:31: owner close case 2026-11-16: after one-watcher",
    "pc2-plugin-update | small | Update auto-pipeline user-scope plugin on pc2 from 0.23.1 to 0.35.0 (owner "
    "2026-11-17) when no v4-plus task manager is working on pc2; running sessions keep their copy until restart | "
    "est 5m | guess 5m | opened 2026-11-17 17:21 | by main | on maverick-pc2 | cross v4-plus | waited 895m | "
    "waiting hold since 2026-11-18 08:16: handed to v4-Manager 2026-11-18 (owner); its todo, its quiet point",
    "one-watcher | big | One watcher for every task manager (agent-watch.sh --all, pane + remote state file, LOST "
    "on exited pane, no signature filter) + agent-file.sh tell with receipt; heartbeats to file only. Fix 3 of 3 "
    "from the v4-plus audit (ideas 123-125, 141-142). PLUS owner 2026-11-17: at main manager start or resume, "
    "rebuild every watch from agent_worktree.txt (today only agent-monitor.sh restarts) | est 114m | guess 135m | "
    "level 3 | opened 2026-11-18 08:16 | by main | waiting hold since 2026-11-18 08:16: owner close case "
    "2026-11-18: next round, run in order, one at a time on pc2",
    "owner-relay | big | OWNER ORDER relay between repo managers: sender prints the OWNER ORDER line (owner "
    "quote, repo, time); receiver runs one command that verifies the quote is a typed owner prompt in the "
    "sender's transcript (not peer, not meta, not tool_result, 24h, same machine); W12 rule + dispatch skill. "
    "Owner 3A 2026-11-20: after one-watcher. Rule text already in ~/.claude/CLAUDE.md | est 42m | guess 45m | "
    "level 3 | opened 2026-11-20 11:35 | by main",
    "comment-shape | small | agent-level.sh: a comment-only change becomes a fifth level 0 shape; R8 line + tests "
    "(owner 4A 2026-11-20, later; level 3 = full lane) | est 28m | guess 20m | level 3 | opened 2026-11-20 11:35 "
    "| by main",
]


OW, OR, CS = REAL[3], REAL[4], REAL[5]


FIXTURE_F = [V4, UT, PC2, OW, OR, CS, ST_RUN, BW]


# a running task opened long before every wait below (rule 5.0: its waits never fill the time from opened)
BASE = ("x | big | the task | est 60m | level 2 | opened 2026-11-10 09:00 | by main | "
        "started 2026-11-10 09:05 | stage tests since 2026-11-10 09:05")


DASH = {"Progress": "-", "Est": "-", "Work": "-", "Wait": "-", "Done by": "-"}


def name_col(name):
    """A status line name: 24 columns, then two spaces (today's layout)."""
    return name + " " * (24 - len(name)) + "  "


class WaitCase(BoardCase):
    lang = "zh"

    def setUp(self):
        super().setUp()
        # one-watcher (2026-11-24): a target row with no live watch gets " · 未确认 <n>m" and the status line a
        # warning line (tests/test_agent_watch.py); runtime plain has no watch, so these wait tests stay as they are
        self.repo.set_conf("runtime", "plain")

    def put(self, *lines):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def one(self, fields, base=BASE):
        """The board row of the one line base + fields."""
        self.put(base + (" | " + fields if fields else ""))
        return self.row(self.rows(now=NOW_NOV20_1231), task="x")

    def status(self, fields, base=BASE):
        return self.one(fields, base)["Status"]

    def assertDash(self, r, est="-"):
        want = dict(DASH, Est=est)
        self.assertEqual({k: r[k] for k in want}, want, r)

    def line(self, folder=None, now=NOW_NOV20_1231):
        folder = folder or self.repo.dir
        stdin = json.dumps({"session_id": "s1", "cwd": folder,
                            "workspace": {"current_dir": folder, "project_dir": folder}})
        result = self.repo.run("agent-statusline.sh", cwd=self.repo.base, stdin=stdin,
                               env={"AGENT_FAKE_NOW": now}, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result.stdout.rstrip("\n")


class TestWaitingRow(WaitCase):
    def test_1_1_mock_on_the_owner_default_what(self):
        r = self.one("waiting mock since 2026-11-20 12:21")
        self.assertEqual(r["Status"], "等待 你 · 确认样稿或规则表 · 已等 10分钟")
        self.assertDash(r)
        self.assertEqual((r["Where"], r["Checks"]), ("-", "level C"))

    def test_1_2_question_default_what(self):
        self.assertEqual(self.status("waiting question since 2026-11-20 10:21"),
                         "等待 你 · 回答问题 · 已等 2小时10分")

    def test_1_3_review_default_what_keeps_where_and_level(self):
        self.put(ST_REVIEW)
        r = self.row(self.rows(now=NOW_NOV20_1231), task="state-trim")
        self.assertEqual(r["Status"], "等待 你 · 合并前签字 · 已等 5分钟")
        self.assertDash(r)
        self.assertEqual((r["Where"], r["Checks"]), (WHERE_ST, "level D"))

    def test_1_4_a_note_wins_over_the_default(self):
        self.assertEqual(self.status("waiting mock since 2026-11-20 12:21: 看规则表 v2"),
                         "等待 你 · 看规则表 v2 · 已等 10分钟")

    def test_1_5_someone_else(self):
        r = self.one("waiting hold since 2026-11-16 15:47: 回复插件更新和同步脚本 | who v4-Manager")
        self.assertEqual(r["Status"], "等待 v4-Manager · 回复插件更新和同步脚本 · 已等 3天20小时")
        self.assertDash(r)

    def test_1_6_review_by_someone_else(self):
        self.assertEqual(self.status("waiting review since 2026-11-20 12:01 | who v4-Manager"),
                         "等待 v4-Manager · 合并前签字 · 已等 30分钟")

    def test_1_7_who_you_is_the_owner(self):
        for who in ("you", "你", "owner", "Owner", "YOU"):
            with self.subTest(who=who):
                self.assertEqual(self.status("waiting hold since 2026-11-20 12:01: 选一个方案 | who " + who),
                                 "等待 你 · 选一个方案 · 已等 30分钟")

    def test_1_8_hold_with_who_no_note(self):
        self.assertEqual(self.status("waiting hold since 2026-11-20 12:01 | who v4-Manager"),
                         "等待 v4-Manager · 已等 30分钟")

    def test_a_long_note_is_cut_to_40_columns(self):
        self.assertEqual(
            self.status("waiting mock since 2026-11-20 12:21: 回复插件更新和同步脚本回复插件更新和同步脚本"),
            "等待 你 · 回复插件更新和同步脚本回复插件更新和同… · 已等 10分钟")
        self.assertEqual(
            self.status("waiting hold since 2026-11-20 12:21: v4-Manager: not now, ledger rollout final suite "
                        "+ staging | who v4-Manager"),
            "等待 v4-Manager · v4-Manager: not now, ledger rollout… · 已等 10分钟")


class TestHoldRow(WaitCase):
    def test_2_1_hold_no_who(self):
        r = self.one("waiting hold since 2026-11-16 17:31: 你说合并监控之后再做")
        self.assertEqual(r["Status"], "暂缓 · 你说合并监控之后再做 · 已等 3天19小时")
        self.assertDash(r)
        self.assertEqual(r["Checks"], "level C")

    def test_2_2_hold_no_note(self):
        self.assertEqual(self.status("waiting hold since 2026-11-20 12:01"), "暂缓 · 已等 30分钟")

    def test_2_3_long_note(self):
        self.assertEqual(
            self.status("waiting hold since 2026-11-16 17:31: owner close case 2026-11-16: after one-watcher"),
            "暂缓 · owner close case 2026-11-16: after… · 已等 3天19小时")


class TestQueueRow(WaitCase):
    def test_3_1_queue_with_after(self):
        r = self.one("waiting queue since 2026-11-20 11:35 | after state-trim")
        self.assertEqual(r["Status"], "排队 · 在 state-trim 之后")
        self.assertDash(r)
        self.assertEqual((r["Where"], r["Checks"]), ("-", "level C"))

    def test_3_2_old_note_after_task(self):
        self.assertEqual(self.status("waiting queue since 2026-11-20 11:35: after one-watcher"),
                         "排队 · 在 one-watcher 之后")
        self.assertEqual(self.status("waiting queue since 2026-11-20 11:35: After one-watcher, then the rest"),
                         "排队 · 在 one-watcher 之后")

    def test_3_3_after_wins_over_a_note(self):
        self.assertEqual(self.status("waiting queue since 2026-11-20 11:35: slot on pc2 | after state-trim"),
                         "排队 · 在 state-trim 之后")

    def test_3_4_neither(self):
        for fields in ("waiting queue since 2026-11-20 11:35",
                       "waiting queue since 2026-11-20 11:35: slot on pc2",
                       "waiting queue since 2026-11-20 11:35: after"):
            with self.subTest(fields=fields):
                self.assertEqual(self.status(fields), "排队")


class TestWaited(WaitCase):
    def test_5_1_short_form(self):
        for since, want in (("2026-11-20 12:31", "0分钟"), ("2026-11-20 12:26", "5分钟"),
                            ("2026-11-20 10:21", "2小时10分"), ("2026-11-20 10:31", "2小时"),
                            ("2026-11-16 15:47", "3天20小时"), ("2026-11-19 12:31", "1天")):
            with self.subTest(since=since):
                self.assertEqual(self.status("waiting hold since " + since), "暂缓 · 已等 " + want)

    def test_5_0_the_run_field(self):
        self.assertEqual(
            self.status("waited 30m | waiting hold since 2026-11-20 12:01: x | who v4-Manager | "
                        "wait run since 2026-11-20 10:31"),
            "等待 v4-Manager · x · 已等 2小时")

    def test_5_0_waits_that_fill_the_time_from_opened(self):
        base = "x | big | the task | est 5m | opened 2026-11-20 10:00 | by main"
        self.assertEqual(self.status("waited 60m | waiting hold since 2026-11-20 11:00", base=base),
                         "暂缓 · 已等 2小时31分")
        self.assertEqual(self.status("waited 59m | waiting hold since 2026-11-20 11:00", base=base),
                         "暂缓 · 已等 1小时31分")

    def test_5_0_pc2_plugin_update_as_the_simulation(self):
        self.put(PC2)
        r = self.row(self.rows(now=NOW_NOV20_1231), task="pc2-plugin-update")
        self.assertEqual(r["Status"], "等待 v4-Manager · pc2 空闲时更新 plugin · 已等 2天19小时")
        self.assertEqual(r["Where"], "maverick-pc2")
        self.assertDash(r)


class TestWork(WaitCase):
    def test_6_1_state_trim(self):
        self.put(ST_RUN)
        r = self.row(self.rows(now=NOW_NOV20_1231), task="state-trim")
        self.assertEqual([r[k] for k in HEAD["en"]],
                         ["state-trim", "State file trim + auto clear at compact_clear_at", "进行中",
                          "██░░░░░░░░  20%", WHERE_ST, "level D", "1h 10m", "29m", "38m", "13:12"])

    def test_6_2_time_before_the_first_stage_is_no_work(self):
        r = self.one("", base="x | big | w | est 39m | opened 2026-11-20 11:35 | by main | "
                              "started 2026-11-20 12:21 | stage brief since 2026-11-20 12:21")
        self.assertEqual((r["Status"], r["Work"], r["Wait"], r["Done by"]), ("进行中", "10m", "0m", "13:00"))

    def test_6_2b_waits_before_the_start_do_not_count_twice(self):
        r = self.one("", base="x | big | w | est 39m | opened 2026-11-20 10:00 | by main | "
                              "started 2026-11-20 12:21 after 46m waited | waited 46m | "
                              "stage brief since 2026-11-20 12:21")
        self.assertEqual((r["Status"], r["Work"], r["Wait"], r["Done by"]), ("进行中", "10m", "46m", "13:00"))

    def test_waits_after_the_start_are_taken_off(self):
        r = self.one("", base="x | big | w | est 60m | opened 2026-11-20 10:00 | by main | "
                              "started 2026-11-20 11:31 after 20m waited | waited 50m | "
                              "stage tests since 2026-11-20 11:31")
        self.assertEqual((r["Progress"], r["Work"], r["Wait"], r["Done by"]),
                         ("██░░░░░░░░  25%", "30m", "50m", "13:01"))

    def test_6_3_not_started(self):
        self.put(OR)
        r = self.row(self.rows(now=NOW_NOV20_1231), task="owner-relay")
        self.assertEqual(r["Status"], "未开始 · 闲置 56分钟")   # idle-task-flag: added 56 minutes before now
        self.assertDash(r, est="42m")
        self.assertEqual((r["Where"], r["Checks"]), ("-", "level C"))

    def test_6_3_not_started_is_never_over_its_estimate(self):
        r = self.one("", base="x | big | w | est 30m | opened 2026-11-20 08:00 | by main")
        self.assertEqual((r["Status"], r["Work"], r["Done by"]), ("未开始 · 闲置 4小时31分", "-", "-"))   # idle-task-flag

    def test_6_4_old_line_with_a_stage_and_no_started(self):
        r = self.one("", base="x | big | w | est 60m | opened 2026-11-20 10:31 | by main | waited 30m | "
                              "stage workers since 2026-11-20 12:00")
        self.assertEqual((r["Status"], r["Progress"], r["Work"], r["Wait"], r["Done by"]),
                         ("进行中", "██████░░░░  65%", "1h 30m", "30m", "13:20"))

    def test_a_started_field_with_no_stage_field_counts(self):
        r = self.one("", base="x | big | w | est 60m | opened 2026-11-20 10:00 | by main | started 2026-11-20 12:00")
        self.assertEqual((r["Status"], r["Progress"], r["Work"], r["Done by"]), ("进行中", "-", "31m", "13:00"))

    def test_a_stray_who_field_on_a_running_line(self):
        r = self.one("who v4-Manager")
        self.assertEqual(r["Status"], "进行中")


class TestWaitEnds(WaitCase):
    def test_7_1_back_to_a_running_row(self):
        self.put(ST_REVIEW)
        self.wait("state-trim", "off", now=NOW_NOV20_1231)
        line = self.todo_line("state-trim")
        self.assertIn(" | waited 43m", line)
        self.assertIn(" | waited in stage 5m", line)
        self.assertNotIn("waiting ", line)
        r = self.row(self.rows(now=NOW_NOV20_1231), task="state-trim")
        self.assertEqual([r[k] for k in HEAD["en"][2:]],
                         ["进行中", "████████░░  80%", WHERE_ST, "level D", "1h 10m", "24m", "43m", "13:17"])


class TestWaitSort(WaitCase):
    def test_8_the_groups(self):
        b = "big | w | est 60m | level 2 | opened 2026-11-10 09:00 | by main | started 2026-11-10 09:05 | stage tests since 2026-11-10 09:05"
        self.put(
            "h-1 | " + b + " | waiting hold since 2026-11-20 08:00",
            "q-1 | " + b + " | waiting queue since 2026-11-20 11:00",
            "ns-1 | big | w | est 60m | opened 2026-11-20 10:30 | by main",
            "oth-1 | " + b + " | waiting review since 2026-11-20 11:00 | who v4-Manager",
            "oth-2 | " + b + " | waiting hold since 2026-11-20 09:30 | who someone",
            "run-b | big | w | est 60m | opened 2026-11-20 10:00 | by main | started 2026-11-20 10:00 | stage tests since 2026-11-20 10:00",
            "run-a | big | w | est 60m | opened 2026-11-20 09:00 | by main | started 2026-11-20 09:00 | stage tests since 2026-11-20 09:00",
            "om-m | " + b + " | waiting mock since 2026-11-20 12:21",
            "om-h | " + b + " | waiting hold since 2026-11-20 12:01 | who you",
            "om-q | " + b + " | waiting question since 2026-11-20 10:21",
        )
        self.state("OWNER TODO: check the phone build\n")
        self.af("park", "add", "which DB for reports?", now="2026-11-20 12:00")
        got = [r["Task"] for r in self.rows(now=NOW_NOV20_1231)]
        self.assertEqual(got, ["om-q", "om-h", "om-m", "run-a", "run-b", "oth-2", "oth-1",
                               "ns-1", "q-1", "h-1", "-", "project"])


class TestSimulation(WaitCase):
    ORDER = ["state-trim", "v4plus-followups", "pc2-plugin-update", "owner-relay", "comment-shape",
             "board-waiting", "usage-track", "one-watcher"]

    def test_the_board(self):
        self.put(*FIXTURE_F)
        rows = self.rows(now=NOW_NOV20_1231)
        self.assertEqual([r["Task"] for r in rows], self.ORDER)
        got = {r["Task"]: r for r in rows}
        self.assertEqual(got["v4plus-followups"]["Status"], "等待 v4-Manager · 回复插件更新和同步脚本 · 已等 3天20小时")
        self.assertEqual(got["pc2-plugin-update"]["Status"], "等待 v4-Manager · pc2 空闲时更新 plugin · 已等 2天19小时")
        self.assertEqual(got["board-waiting"]["Status"], "排队 · 在 state-trim 之后")
        self.assertEqual(got["usage-track"]["Status"], "暂缓 · 你说合并监控之后再做 · 已等 3天19小时")
        self.assertEqual(got["one-watcher"]["Status"], "暂缓 · owner close case 2026-11-18: next… · 已等 2天4小时")
        for name in ("owner-relay", "comment-shape"):
            self.assertEqual(got[name]["Status"], "未开始 · 闲置 56分钟")   # idle-task-flag
        self.assertEqual((got["owner-relay"]["Est"], got["comment-shape"]["Est"]), ("42m", "28m"))
        for name in ("v4plus-followups", "pc2-plugin-update", "board-waiting", "usage-track", "one-watcher"):
            self.assertDash(got[name])
        self.assertEqual(got["board-waiting"]["Checks"], "level C")
        self.assertEqual(got["state-trim"]["Done by"], "13:12")

    def test_the_status_line(self):
        self.put(*FIXTURE_F)
        self.assertEqual(self.line(), "\n".join([
            name_col("state-trim") + "██░░░░░░░░  20%  写测试  13:12",
            name_col("v4plus-followups") + "等待 v4-Manager · 已等 3天20小时",
            name_col("pc2-plugin-update") + "等待 v4-Manager · 已等 2天19小时",
            name_col("owner-relay") + "未开始 · 闲置 56分钟",   # one-watcher K: an own row while there is room
            "+4 个任务"]))

    def test_the_owner_moment(self):
        self.put(*[ST_REVIEW if l is ST_RUN else l for l in FIXTURE_F])
        rows = self.rows(now=NOW_NOV20_1231)
        top = rows[0]
        self.assertEqual([top[k] for k in HEAD["en"][:1] + HEAD["en"][2:]],
                         ["state-trim", "等待 你 · 合并前签字 · 已等 5分钟", "-", WHERE_ST, "level D", "-", "-", "-", "-"])
        self.assertEqual(self.line(), "\n".join([
            name_col("state-trim") + "等待 你 · 合并前签字 · 已等 5分钟",
            name_col("v4plus-followups") + "等待 v4-Manager · 已等 3天20小时",
            name_col("pc2-plugin-update") + "等待 v4-Manager · 已等 2天19小时",
            name_col("owner-relay") + "未开始 · 闲置 56分钟",   # one-watcher K: an own row while there is room
            "+4 个任务"]))


class TestSimulationEnglish(WaitCase):
    lang = "en"

    def test_the_words(self):
        self.put(*FIXTURE_F)
        got = {r["Task"]: r["Status"] for r in self.rows(now=NOW_NOV20_1231)}
        self.assertEqual(got, {
            "state-trim": "running",
            "v4plus-followups": "waiting v4-Manager · 回复插件更新和同步脚本 · waited 3d 20h",
            "pc2-plugin-update": "waiting v4-Manager · pc2 空闲时更新 plugin · waited 2d 19h",
            "owner-relay": "not started · idle 56m",   # idle-task-flag
            "comment-shape": "not started · idle 56m",
            "board-waiting": "queue · after state-trim",
            "usage-track": "hold · 你说合并监控之后再做 · waited 3d 19h",
            "one-watcher": "hold · owner close case 2026-11-18: next… · waited 2d 4h",
        })

    def test_the_status_line(self):
        self.put(*FIXTURE_F)
        self.assertEqual(self.line(), "\n".join([
            name_col("state-trim") + "██░░░░░░░░  20%  tests  13:12",
            name_col("v4plus-followups") + "waiting v4-Manager · waited 3d 20h",
            name_col("pc2-plugin-update") + "waiting v4-Manager · waited 2d 19h",
            name_col("owner-relay") + "not started · idle 56m",   # one-watcher K
            "+4 tasks"]))

    def test_the_owner_moment_and_defaults(self):
        self.put(*[ST_REVIEW if l is ST_RUN else l for l in FIXTURE_F])
        self.assertEqual(self.line().split("\n")[0], name_col("state-trim") + "waiting you · sign off before merge · waited 5m")
        self.assertEqual(self.status("waiting mock since 2026-11-20 12:21"),
                         "waiting you · check mock or rules table · waited 10m")
        self.assertEqual(self.status("waiting question since 2026-11-20 10:21"),
                         "waiting you · answer a question · waited 2h 10m")
        self.assertEqual(self.status("waiting hold since 2026-11-20 12:01"), "hold · waited 30m")
        self.assertEqual(self.status("waiting queue since 2026-11-20 11:35"), "queue")
        for since, want in (("2026-11-20 12:31", "0m"), ("2026-11-20 10:31", "2h"), ("2026-11-19 12:31", "1d")):
            self.assertEqual(self.status("waiting hold since " + since), "hold · waited " + want)


class TestOldLines(WaitCase):
    def test_10_pc2_real_lines_render(self):
        self.put(*REAL)
        result = self.af("board", now=NOW_NOV20_1231)
        self.assertNotIn("Traceback", result.stderr)
        got = {r["Task"]: r["Status"] for r in self.table(result.stdout)}
        self.assertEqual(got, {
            "v4plus-followups": "暂缓 · v4-Manager: not now, ledger rollout… · 已等 3天20小时",
            "usage-track": "暂缓 · owner close case 2026-11-16: after… · 已等 3天19小时",
            "pc2-plugin-update": "暂缓 · handed to v4-Manager 2026-11-18… · 已等 2天19小时",
            "one-watcher": "暂缓 · owner close case 2026-11-18: next… · 已等 2天4小时",
            "owner-relay": "未开始 · 闲置 56分钟",   # idle-task-flag
            "comment-shape": "未开始 · 闲置 56分钟",
        })
        # one-watcher K: 6 rows, 5 lines: 4 own rows by board order, the rest fold
        self.assertEqual(self.line(), "\n".join([
            name_col("owner-relay") + "未开始 · 闲置 56分钟", name_col("comment-shape") + "未开始 · 闲置 56分钟",
            name_col("v4plus-followups") + "暂缓 · 已等 3天20小时", name_col("usage-track") + "暂缓 · 已等 3天19小时",
            "+2 个任务"]))

    def test_10_odd_lines_never_crash(self):
        self.put("bare",
                 "two | fields",
                 "w | big | w | waiting hold since 2026-11-20 12:01: x | who",
                 "u | big | w | waiting queue since 2026-11-20 12:01 | after",
                 "s | big | w | started 2026-13-40 99:99 after xm waited | stage tests since 2026-11-20 12:00",
                 "r | big | w | waiting hold since 2026-11-20 12:01 | wait run since not-a-date")
        result = self.af("board", now=NOW_NOV20_1231)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(len(self.table(result.stdout)), 6)
        self.line()

    def test_10_a_wait_since_that_is_no_real_time(self):
        # verify finding (Worker 2 bounce 1): the date pattern matches, the date does not exist -> no crash,
        # the row keeps its kind and leaves the waited part out
        self.put("a | big | w | opened 2026-11-20 10:00 | by main | waiting hold since 2026-13-40 99:99: x",
                 "c | big | w | opened 2026-11-20 10:00 | by main | waiting review since 2026-02-30 10:00 | who v4-Manager")
        result = self.af("board", now=NOW_NOV20_1231)
        self.assertNotIn("Traceback", result.stderr)
        got = {r["Task"]: r["Status"] for r in self.table(result.stdout)}
        self.assertEqual(got, {"a": "暂缓 · x", "c": "等待 v4-Manager · 合并前签字"})
        # one-watcher K: the hold gets its own row; no real time -> no waited part
        self.assertEqual(self.line(), name_col("c") + "等待 v4-Manager\n" + name_col("a") + "暂缓")


class TestBoardRow(WatchBoardCase):
    def test_f3a_no_status_file_warns_from_the_started_time(self):
        self.assertEqual(self.status_of(), self.st("running") + self.warn(30))

    def test_f3_a_live_watched_task_with_a_recent_change_has_no_warning(self):
        self.watch(changed="2026-11-02 14:50", confirmed="2026-11-02 14:59")
        self.assertEqual(self.status_of(), self.st("running"))

    def test_f3c_a_quiet_file_for_15_minutes_warns_from_changed(self):
        self.watch(changed="2026-11-02 14:40", confirmed="2026-11-02 14:59")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(20))

    def test_f3c_exactly_15_minutes_warns(self):
        self.watch(changed="2026-11-02 14:45", confirmed="2026-11-02 14:59")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(15))

    def test_f3c_watch_quiet_min_from_agent_conf(self):
        self.repo.set_conf("watch_quiet_min", "30")
        self.watch(changed="2026-11-02 14:40", confirmed="2026-11-02 14:59")
        self.assertEqual(self.status_of(), self.st("running"))

    def test_f3b_not_watched_warns(self):
        self.watch(watched=False, why="no task manager pane")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(30))

    def test_f3a_a_dead_pid_warns_from_changed(self):
        self.watch(pid=dead_pid(), changed="2026-11-02 14:52", confirmed="2026-11-02 14:58")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(8))

    def test_f4_no_changed_falls_back_to_confirmed(self):
        self.watch(pid=dead_pid(), changed=None, confirmed="2026-11-02 14:48")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(12))

    def test_f4_no_started_falls_back_to_opened(self):
        beta = self.repo.make_worktree("beta", as_repo=False)
        self.add("beta", "bank recon", 60, opened="2026-11-02 14:20", started=False)
        self.worktree_lines((self.alpha, "alpha", "working"), (beta, "beta", "working"))
        idle = " · 闲置 40分钟" if self.lang == "zh" else " · idle 40m"      # idle-task-flag
        self.assertEqual(self.status_of("beta"), self.st("not_started") + idle + self.warn(40))

    def test_live_means_a_sweep_at_most_2_intervals_plus_2_minutes_old(self):
        self.watch(sweep="2026-11-02 14:48", changed="2026-11-02 14:55")
        self.assertEqual(self.status_of(), self.st("running"))
        self.watch(sweep="2026-11-02 14:47", changed="2026-11-02 14:55")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(5))

    def test_f3c_a_waiting_row_is_not_warned_for_a_quiet_file(self):
        self.wait("alpha", "on", "question", now="2026-11-02 14:35")
        self.watch(changed="2026-11-02 14:35", confirmed="2026-11-02 14:59")
        self.assertNotIn("未确认", self.status_of())

    def test_f3a_a_waiting_row_is_warned_when_no_watch_runs(self):
        self.wait("alpha", "on", "question", now="2026-11-02 14:35")
        self.assertTrue(self.status_of().endswith(self.warn(30)), self.status_of())

    def test_a_row_that_is_not_a_target_is_never_warned(self):
        self.add("beta", "bank recon", 60, opened="2026-11-02 14:00")
        self.assertEqual(self.status_of("beta"), self.st("running"))
        self.worktree_lines((self.alpha, "alpha", "done"))
        self.assertEqual(self.status_of("alpha"), self.st("running"))

    def test_a_todo_line_with_an_on_field_is_a_target(self):
        self.add("gamma", "stock page", 60, opened="2026-11-02 14:50")
        self.af("todo", "where", "gamma", "pc2", "/x/gamma")
        self.assertEqual(self.status_of("gamma"), self.st("running") + self.warn(10))

    def test_scope_add_1_plain_or_cloud_runtime_has_no_warning(self):
        for value in ("plain", "cloud"):
            with self.subTest(runtime=value):
                self.repo.set_conf("runtime", value)
                self.assertEqual(self.status_of(), self.st("running"))

    def test_f5_orphans_of_a_live_watch_are_one_note_line(self):
        self.watch(changed="2026-11-02 14:58", orphans=[{"path": "/x/ghost", "title": "◑ ghost Task Manager",
                                                         "handle": "term_g"}])
        out = self.board()
        self.assertIn("看板可能不准：/x/ghost 有活动窗格但没有任务行", out.splitlines())

    def test_f5_orphans_of_a_dead_watch_are_not_shown(self):
        self.watch(pid=dead_pid(), changed="2026-11-02 14:58",
                   orphans=[{"path": "/x/ghost", "title": "◑ ghost", "handle": "term_g"}])
        self.assertNotIn("/x/ghost", self.board())

    def test_r6_no_orca_on_this_machine_has_no_warning(self):
        # review fix R6: runtime auto in the Claude app (no orca at all): no watch can run, so no warning
        self.repo.no_orca()
        self.assertEqual(self.status_of(), self.st("running"))

    def test_f7_the_board_never_calls_orca_for_the_watch(self):
        self.watch(changed="2026-11-02 14:40", orphans=[{"path": "/x/ghost", "title": "g", "handle": "term_g"}])
        self.repo.clear_calls()
        self.board()
        self.assertEqual(self.repo.calls(), [])


class TestBoardBeat(WatchBoardCase):
    """report-to-main-pc2: the todo line's "beat <m>m <text>" (todo beat, from the last heartbeat) follows the bar in
    the Progress cell; a new stage drops it; the same text again writes nothing; a bad text is refused."""

    def stage(self, name, *args):
        return self.assertOk(self.repo.run("agent-file.sh", "todo", "stage", name, *args))

    def beat(self, *text):
        return self.repo.run("agent-file.sh", "todo", "beat", "alpha", *text)

    def progress(self):
        return self.row(self.rows(), task="alpha")["Progress"]

    def test_the_beat_follows_the_bar(self):
        self.stage("alpha", "verify")
        before = self.progress()
        self.assertOk(self.beat("160m full suite running"))
        self.assertEqual(self.progress(), before + " 160m full suite running")

    def test_a_new_beat_replaces_the_old_in_place(self):
        self.stage("alpha", "verify")
        self.assertOk(self.beat("160m a"))
        self.assertOk(self.beat("175m b"))
        line = [l for l in self.repo.read("agent_todo.txt").splitlines() if l.startswith("alpha | ")][0]
        self.assertEqual(line.count(" | beat "), 1, line)
        self.assertTrue(line.endswith(" | beat 175m b"), line)

    def test_a_new_stage_drops_the_beat(self):
        self.stage("alpha", "verify")
        self.assertOk(self.beat("160m full suite running"))
        self.stage("alpha", "push")
        self.assertNotIn("beat", self.repo.read("agent_todo.txt"))

    def test_the_same_stage_keeps_the_beat(self):
        self.stage("alpha", "verify")
        self.assertOk(self.beat("160m full suite running"))
        self.stage("alpha", "verify")
        self.assertIn(" | beat 160m full suite running", self.repo.read("agent_todo.txt"))

    def test_refused(self):
        self.assertNotEqual(self.repo.run("agent-file.sh", "todo", "beat", "nobody", "5m x").returncode, 0)
        self.assertNotEqual(self.beat("").returncode, 0)
        self.assertNotEqual(self.beat("5m a | b").returncode, 0)
        self.assertNotIn("beat", self.repo.read("agent_todo.txt"))


class TestBoardRowEnglish(WatchBoardCase):
    lang = "en"

    def test_f3_english_words(self):
        self.assertEqual(self.status_of(), "running · not confirmed 30m")

    def test_f5_english_note(self):
        self.watch(changed="2026-11-02 14:58", orphans=[{"path": "/x/ghost", "title": "g", "handle": "term_g"}])
        self.assertIn("board may be wrong: /x/ghost has a live pane but no task line", self.board().splitlines())


STAGE_NOW = NOW   # "2026-11-02 15:00"


CLEAR = "\x1b[H\x1b[2J"


class StageCase(BoardCase):
    lang = "zh"

    def stage(self, name, *args, now=STAGE_NOW, cwd=None):
        return self.af("todo", "stage", name, *args, now=now, cwd=cwd)

    def board_row(self, name, *args, now=STAGE_NOW, cwd=None):
        return self.row(self.rows(*args, now=now, cwd=cwd), task=name)

    def progress(self, name, **kw):
        return self.board_row(name, **kw)["Progress"]

    def done_by(self, name, **kw):
        return self.board_row(name, **kw)["Done by"]


class TestProgressColumn(StageCase):
    WANT = [
        ("s-brief", ("brief",), "░░░░░░░░░░   0%"),
        ("s-register", ("register",), "░░░░░░░░░░   1%"),
        ("s-mock", ("mock",), "░░░░░░░░░░   2%"),
        ("s-tests", ("tests",), "░░░░░░░░░░   6%"),
        ("s-workers", ("workers",), "██░░░░░░░░  26%"),
        ("s-half", ("workers", "1/2"), "████░░░░░░  46%"),
        ("s-third", ("workers", "1/3"), "███░░░░░░░  39%"),
        ("s-all", ("workers", "2/2"), "██████░░░░  66%"),
        ("s-verify", ("verify",), "██████░░░░  66%"),
        ("s-push", ("push",), "████████░░  81%"),
        ("s-report", ("report",), "████████░░  83%"),
        ("s-e2e", ("e2e",), "████████░░  85%"),
        ("s-merge", ("merge",), "█████████░  95%"),
    ]

    def test_the_bar_of_every_stage(self):
        for name, args, _ in self.WANT:
            self.add(name, "task " + name, 60)
            self.stage(name, *args)
        self.add("no-stage", "a task with no stage", 60)
        rows = self.rows()
        for name, _, want in self.WANT:
            with self.subTest(task=name):
                self.assertEqual(self.row(rows, task=name)["Progress"], want)
        self.assertEqual(self.row(rows, task="no-stage")["Progress"], "-")

    def test_the_column_sits_after_status(self):
        self.add("alpha", "the login form", 60)
        self.stage("alpha", "verify")
        head = [l for l in self.board().splitlines() if l.startswith("|")][0]
        self.assertEqual(cells(head), HEAD["zh"])
        self.assertEqual(cells(head)[3], "进度")

    def test_other_rows_show_a_dash(self):
        self.add("alpha", "the login form", 60)
        self.stage("alpha", "verify")
        self.state("OWNER TODO: check the phone build\n"
                   "PARKED: keep the old API? | alpha | since 2026-11-02 14:00\n"
                   "WORKER 1: board script | since 2026-11-02 14:40\n")
        rows = self.rows()
        self.assertEqual(self.row(rows, task="alpha")["Progress"], "██████░░░░  66%")
        for what in ("check the phone build", "keep the old API?", "board script"):
            with self.subTest(what=what):
                self.assertEqual(self.row(rows, what=what)["Progress"], "-")

    def test_never_100_before_merged(self):
        # settings-configure: the weights are fixed (merge = 5), merge stage still shows 99 at most
        self.add("alpha", "the login form", 60)
        self.stage("alpha", "merge")
        self.assertLess(int(self.progress("alpha").split()[-1].rstrip("%")), 100)


class TestProgressColumnEnglish(StageCase):
    lang = "en"

    def test_the_header(self):
        self.add("alpha", "the login form", 60)
        self.stage("alpha", "tests")
        head = [l for l in self.board().splitlines() if l.startswith("|")][0]
        self.assertEqual(cells(head)[3], "Progress")
        self.assertEqual(self.progress("alpha"), "░░░░░░░░░░   6%")


class TestDoneBy(StageCase):
    def test_over_the_estimate_comes_from_progress(self):
        # work 60 > est 40; verify p = 66/100: 60 x 34/66 = 30.9 -> 31 minutes
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.assertEqual(self.done_by("alpha"), "15:31")

    def test_under_the_estimate_it_is_the_estimate(self):
        # bounce 1: work 30 < est 120 -> 16:30, even where progress would say 22:50 (tests)
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:30")
        self.stage("alpha", "tests")
        self.assertEqual(self.done_by("alpha"), "16:30")
        # the main manager's evidence: a 60m task, register at 14:02, board at 14:03 and 14:20
        self.add("beta", "bank recon match", 60, opened="2026-11-02 14:02")
        self.stage("beta", "register", now="2026-11-02 14:02")
        self.assertEqual(self.done_by("beta", now="2026-11-02 14:03"), "15:02")
        self.assertEqual(self.done_by("beta", now="2026-11-02 14:20"), "15:02")

    def test_under_the_estimate_the_estimate_is_later(self):
        # work 60 < est 120: est says 16:00; verify says 15:31
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.assertEqual(self.done_by("alpha"), "16:00")

    def test_no_estimate_with_a_stage(self):
        # workers 1/2 p = 46/100: 60 x 54/46 = 70.4 -> 71 minutes
        self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
        self.stage("alpha", "workers", "1/2")
        self.assertEqual(self.done_by("alpha"), "16:11")

    def test_the_wait_is_not_work(self):
        # clock 80, waited 20 -> work 60 > est 40; verify -> 31 minutes
        self.add("alpha", "the login form", 40, opened="2026-11-02 13:40")
        self.wait("alpha", "on", "question", now="2026-11-02 14:00")
        self.wait("alpha", "off", now="2026-11-02 14:20")
        self.stage("alpha", "verify")
        self.assertEqual(self.done_by("alpha"), "15:31")

    def test_no_progress_yet_over_the_estimate(self):
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "brief")
        self.assertEqual(self.done_by("alpha"), "超出 20m")

    def test_over_the_estimate_below_the_minimum_progress(self):
        # tests p = 6/100 < 20/100 -> no progress clock yet
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "tests")
        self.assertEqual(self.done_by("alpha"), "超出 20m")

    def test_the_minimum_is_the_fixed_20(self):
        # workers p = 26/100 is above the fixed 20: progress counts (60 x 74/26 = 170.8 -> 171 -> 17:51)
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "workers")
        self.assertEqual(self.done_by("alpha"), "17:51")

    def test_no_estimate_below_the_minimum_progress(self):
        self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
        self.stage("alpha", "tests")
        self.assertEqual(self.done_by("alpha"), "-")

    def test_no_stage_over_by_real_units(self):
        self.add("alpha", "the login form", 30, opened="2026-11-02 13:00")
        self.assertEqual(self.done_by("alpha"), "超出 1h 30m")

    def test_no_stage_under_the_estimate_as_before(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.assertEqual(self.done_by("alpha"), "16:00")

    def test_tomorrow(self):
        # work 60 > est 30, verify -> 31 minutes after 23:30
        self.add("alpha", "the login form", 30, opened="2026-11-02 22:30")
        self.stage("alpha", "verify", now="2026-11-02 23:30")
        self.assertEqual(self.done_by("alpha", now="2026-11-02 23:30"), "明天 00:01")


class TestDoneByEnglish(StageCase):
    lang = "en"

    def test_words(self):
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.add("beta", "bank recon match", 40, opened="2026-11-02 14:00")
        self.add("night", "finishes after midnight", 30, opened="2026-11-02 22:30")
        self.stage("night", "verify", now="2026-11-02 23:30")
        rows = self.rows()
        self.assertEqual(self.row(rows, task="alpha")["Done by"], "15:31")
        self.assertEqual(self.row(rows, task="beta")["Done by"], "over by 20m")
        self.assertEqual(self.done_by("night", now="2026-11-02 23:30"), "00:01 tomorrow")


class TestWatch(StageCase):
    def popen(self, *args, cwd=None):
        env = self.repo._env({"AGENT_FAKE_NOW": STAGE_NOW, "AGENT_FAKE_HOST": HOST})
        return subprocess.Popen([self.repo.script_path("agent-file.sh"), "board"] + list(args),
                                cwd=cwd or self.repo.cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True)

    def ctrl_c(self, proc, after):
        time.sleep(after)
        try:
            os.killpg(proc.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            out, err = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, err = proc.communicate()
            self.fail("the watch did not stop on Ctrl-C")
        return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    def test_frames_then_ctrl_c_stops_cleanly(self):
        self.add("alpha", "the login form", 60)
        self.stage("alpha", "verify")
        code, out, err = self.ctrl_c(self.popen("--watch", "1"), 3.2)
        self.assertEqual(code, 0, err)
        self.assertNotIn("Traceback", err)
        frames = out.split(CLEAR)
        self.assertEqual(frames[0], "", "the output starts with the clear")
        self.assertGreaterEqual(len(frames) - 1, 2, out)
        first = frames[1]
        self.assertIn("| alpha [t] | the login form | 进行中 | ██████░░░░  66% |", first)   # the owner bracket
        self.assertIn("每 1 秒刷新 · Ctrl-C 停止", first.strip().splitlines()[-1])

    def test_the_default_is_the_fixed_60(self):
        code, out, err = self.ctrl_c(self.popen("--watch"), 1.5)
        self.assertEqual(code, 0, err)
        self.assertEqual(out.count(CLEAR), 1, out)
        self.assertIn("每 60 秒刷新 · Ctrl-C 停止", out)
        self.assertIn("无", out)

    def test_self_watch(self):
        alpha = self.task_worktree("alpha")
        self.add("alpha", "the login form", 60)
        self.add("beta", "bank recon match", 60)
        code, out, err = self.ctrl_c(self.popen("--self", "--watch", "1", cwd=alpha), 1.5)
        self.assertEqual(code, 0, err)
        self.assertIn("| alpha [t] |", out)          # the owner bracket (scope add 2026-11-26)
        self.assertNotIn("| beta", out)

    def test_refusals(self):
        for args in (("--watch", "0"), ("--watch", "-3"), ("--watch", "abc"),
                     ("--watch", "1.5"), ("--watch", "1", "2")):
            with self.subTest(args=args):
                result = self.repo.run("agent-file.sh", "board", *args, timeout=15,
                                       env={"AGENT_FAKE_NOW": STAGE_NOW, "AGENT_FAKE_HOST": HOST})
                self.assertEqual(result.returncode, 1, (result.stdout, result.stderr))
                self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)


class TestWatchEnglish(TestWatch):
    lang = "en"

    def test_frames_then_ctrl_c_stops_cleanly(self):
        self.add("alpha", "the login form", 60)
        code, out, err = self.ctrl_c(self.popen("--watch", "1"), 1.5)
        self.assertEqual(code, 0, err)
        self.assertIn("refresh every 1s · Ctrl-C stops", out)

    def test_the_default_is_the_fixed_60(self):
        code, out, err = self.ctrl_c(self.popen("--watch"), 1.5)
        self.assertEqual(code, 0, err)
        self.assertIn("refresh every 60s · Ctrl-C stops", out)


class TestAddedWork(BoardCase):
    """C52: added work raises the estimate; the bar never falls back to 0."""
    lang = "en"

    def test_plus_minutes(self):
        self.add("t", "a running task", est=60, opened="2026-11-02 13:00")
        self.af("todo", "stage", "t", "workers", now="2026-11-02 14:00")
        before = self.row(self.rows(), task="t")["Progress"]
        r = self.af("todo", "est", "t", "+120", now="2026-11-02 14:30")
        self.assertIn("todo est: t 60m -> 180m", r.stdout)
        line = [l for l in self.repo.read("agent_todo.txt").splitlines() if l.startswith("t | ")][0]
        self.assertIn("est 180m", line)
        self.assertIn("stage workers", line)
        after = self.row(self.rows(), task="t")["Progress"]
        pct = int(re.search(r"(\d+)%", after).group(1))
        self.assertGreater(pct, 0, (before, after))
        self.assertGreaterEqual(pct, int(re.search(r"(\d+)%", before).group(1)) // 2)


class TestOneRowPerTask(BoardCase):
    """board-one-row (owner, 2026-11-26: "why deputy also appear at there. deputy no need to show ya, if not
    confusing"): an agent or pane launched under a task that has a todo row is no row of its own; its task's row
    says it: status running + " · N 代理", work and place filled in when the task has none."""
    lang = "zh"
    ONE = " · 1 代理"
    TWO = " · 2 代理"

    def launch(self, kind, task, since="2026-11-02 14:30", pid=None, agent="a1", pane=None, key=None, folder=None):
        line = "LAUNCH %s: %s | task %s | title of %s | since %s | pid %d | by main" % (
            key or "k_%s_%s_%s" % (kind.replace(" ", ""), task, since[-5:].replace(":", "")), kind, task, kind,
            since, pid or os.getpid())
        if agent:
            line += " | agent " + agent
        if pane:
            line += " | pane " + pane
        self.state(line, folder=folder)

    def mark(self, n):
        if self.lang == "zh":
            return " · %d 代理" % n
        return " · %d agent%s" % (n, "" if n == 1 else "s")

    def test_a_deputy_and_no_stage_is_one_running_row(self):
        self.add("t", "the task", 20, started=False)
        self.launch("deputy", "t", since="2026-11-02 14:30")
        rows = self.rows()
        self.assertEqual([r["Task"] for r in rows], ["t [t]"], rows)
        r = rows[0]
        self.assertEqual(r["Status"], self.st("running") + self.mark(1))
        self.assertEqual(r["Work"], "30m")                       # the deputy's minutes: 14:30 -> 15:00
        self.assertEqual(r["Where"], "pc2, " + self.repo.dir)    # the deputy's place
        self.assertEqual(r["Est"], "20m")

    def test_a_task_manager_pane_and_two_workers_is_one_row_and_two_agents(self):
        self.add("t", "the task", 60, opened="2026-11-02 14:00")           # started: its own work is 1h
        self.launch("tm-pane", "t", since="2026-11-02 14:59", agent=None)  # a pane: not counted, no row
        self.launch("worker 1", "t", since="2026-11-02 14:20")
        self.launch("worker 2", "t", since="2026-11-02 14:40")
        rows = self.rows()
        self.assertEqual([r["Task"] for r in rows], ["t [t]"], rows)
        self.assertEqual(rows[0]["Status"], self.st("running") + self.mark(2))
        self.assertEqual(rows[0]["Work"], "1h")                  # the task's own work, not a worker's

    def test_a_merge_deputy_and_a_reviewer_at_once_are_two_agents_on_one_row(self):
        self.add("t", "the task", 20, started=False)
        self.launch("merge", "t", since="2026-11-02 14:50")
        self.launch("reviewer", "t", since="2026-11-02 14:40")
        rows = self.rows()
        self.assertEqual([r["Task"] for r in rows], ["t [t]"], rows)
        self.assertEqual(rows[0]["Status"], self.st("running") + self.mark(2))
        self.assertEqual(rows[0]["Work"], "20m")                 # the oldest live agent: 14:40

    def test_every_agent_kind_and_a_pane_kind_is_folded(self):
        self.add("t", "the task", 20, started=False)
        kinds = ("deputy", "merge", "reviewer", "explore", "plan", "guide", "agent")
        for i, kind in enumerate(kinds):
            self.launch(kind, "t", since="2026-11-02 14:5%d" % i)
        for kind in ("shell-pane", "pane", "helper-pane"):
            self.launch(kind, "t", since="2026-11-02 14:59", agent=None, key="k_" + kind)
        rows = self.rows()
        self.assertEqual([r["Task"] for r in rows], ["t [t]"], rows)
        self.assertEqual(rows[0]["Status"], self.st("running") + self.mark(len(kinds)))

    def test_a_finished_agent_adds_nothing(self):
        self.add("t", "the task", 20, started=False, opened="2026-11-02 14:55")   # idle-task-flag: not idle
        self.launch("deputy", "t", pid=dead_pid())
        rows = self.rows()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual((rows[0]["Status"], rows[0]["Work"], rows[0]["Where"]),
                         (self.st("not_started"), "-", "-"))

    def test_a_live_and_a_finished_agent_count_one(self):
        self.add("t", "the task", 20, started=False)
        self.launch("deputy", "t", pid=dead_pid(), key="k_dead")
        self.launch("reviewer", "t", since="2026-11-02 14:45")
        rows = self.rows()
        self.assertEqual((len(rows), rows[0]["Status"], rows[0]["Work"]),
                         (1, self.st("running") + self.mark(1), "15m"))

    def test_an_agent_without_a_todo_row_keeps_its_own_row(self):
        self.add("t", "the task", 20, started=False, opened="2026-11-02 14:55")   # idle-task-flag: not idle
        self.launch("deputy", "ghost", since="2026-11-02 14:30")
        self.launch("tm-pane", "ghost", since="2026-11-02 14:59", agent=None)
        rows = self.rows()
        tasks = sorted(r["Task"] for r in rows)
        word = {"zh": ("副手", "窗格"), "en": ("deputy", "pane")}[self.lang]
        self.assertEqual(tasks, sorted(["t [t]", "ghost " + word[0], "ghost " + word[1]]), rows)
        self.assertEqual(self.row(rows, task="t")["Status"], self.st("not_started"))
        self.assertEqual(self.row(rows, task="ghost " + word[0])["Work"], "30m")

    def test_a_task_with_no_agent_is_unchanged(self):
        self.add("t", "the task", 20, started=False, opened="2026-11-02 14:55")   # idle-task-flag: not idle
        r = self.rows()[0]
        self.assertEqual((r["Status"], r["Work"], r["Where"]), (self.st("not_started"), "-", "-"))

    def test_its_own_place_and_work_win(self):
        self.add("t", "the task", 60, opened="2026-11-02 14:00")
        self.af("todo", "where", "t", "box9", "/srv/t")
        self.launch("deputy", "t", since="2026-11-02 14:50")
        r = self.rows()[0]
        self.assertEqual((r["Work"], r["Where"]), ("1h", "box9, /srv/t"))

    def test_a_wait_keeps_its_status_and_gets_the_mark(self):
        self.add("t", "the task", 20, started=False)
        self.wait("t", "on", "review")
        self.launch("reviewer", "t", since="2026-11-02 14:45")
        rows = self.rows()
        self.assertEqual(len(rows), 1, rows)
        self.assertTrue(rows[0]["Status"].endswith(self.mark(1)), rows)
        self.assertNotIn(self.st("running"), rows[0]["Status"])

    def test_the_order_of_the_rows_holds(self):
        self.add("a", "first", 20, opened="2026-11-02 13:00", started=False)
        self.add("b", "second", 20, opened="2026-11-02 13:10")
        self.launch("deputy", "a", since="2026-11-02 14:30")
        self.state("OWNER TODO: check the phone build\n")
        names = [re.sub(r" \[[^\]]*\]$", "", r["Task"]) for r in self.rows()]
        self.assertEqual(names, ["a", "b", "-"])

    def test_self_view_folds_the_workers_too(self):
        alpha = self.task_worktree("alpha")
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.worktree_lines((alpha, "alpha", "working"))
        self.launch("worker 1", "alpha", since="2026-11-02 14:20", folder=alpha)
        self.launch("tm-pane", "alpha", since="2026-11-02 14:59", agent=None, folder=alpha)
        rows = self.rows("--self", cwd=alpha)
        self.assertEqual([r["Task"] for r in rows], ["alpha [t]"], rows)
        # the watch's "not confirmed" warning of a task worktree may sit before the mark; the mark ends the cell
        self.assertTrue(rows[0]["Status"].startswith(self.st("running")), rows)
        self.assertTrue(rows[0]["Status"].endswith(self.mark(1)), rows)

    # ---- follow-ups of the review (main manager): the status line says running too; a live pane alone is someone working

    def line(self, width):
        env = {"AGENT_FAKE_NOW": NOW, "AGENT_FAKE_HOST": HOST, "AGENT_STATUSLINE_WIDTH": str(width)}
        res = self.statusline_py(json.dumps({"cwd": self.repo.dir}), env=env, cwd=self.repo.dir)
        return res.stdout

    def test_status_line_reads_running_with_a_live_agent_at_every_width(self):
        self.add("t", "the task", 20, started=False)
        self.launch("deputy", "t", since="2026-11-02 14:30")
        for width in (0, 70, 200):
            text = self.line(width)
            self.assertIn(self.st("running") + self.mark(1), text, (width, text))
            self.assertNotIn(self.st("not_started"), text, (width, text))

    def test_status_line_without_an_agent_still_reads_not_started(self):
        self.add("t", "the task", 20, started=False)
        for width in (0, 70, 200):
            text = self.line(width)
            self.assertIn(self.st("not_started"), text, (width, text))
            self.assertNotIn(self.st("running"), text, (width, text))

    def test_a_pane_alone_is_running_with_no_count_on_the_board(self):
        self.add("t", "the task", 20, started=False)
        self.launch("tm-pane", "t", since="2026-11-02 14:58", agent=None)    # a pane with no handle: 2 minutes of life
        rows = self.rows()
        self.assertEqual(len(rows), 1, rows)
        r = rows[0]
        self.assertEqual((r["Status"], r["Work"], r["Where"]), (self.st("running"), "2m", "pc2, " + self.repo.dir))

    def test_a_pane_alone_keeps_the_tasks_own_work_and_place(self):
        self.add("t", "the task", 60, opened="2026-11-02 14:00")
        self.af("todo", "where", "t", "box9", "/srv/t")
        self.launch("tm-pane", "t", since="2026-11-02 14:58", agent=None)
        r = self.rows()[0]
        # the watch's "not confirmed" warning may follow the word; no agent mark ever
        self.assertTrue(r["Status"].startswith(self.st("running")) and "代理" not in r["Status"]
                        and "agent" not in r["Status"], r)
        self.assertEqual((r["Work"], r["Where"]), ("1h", "box9, /srv/t"))

    def test_a_pane_alone_is_running_in_the_status_line_with_no_count(self):
        self.add("t", "the task", 20, started=False)
        self.launch("tm-pane", "t", since="2026-11-02 14:45", agent=None)
        for width in (0, 70, 200):
            text = self.line(width)
            self.assertIn(self.st("running"), text, (width, text))
            self.assertNotIn(self.st("not_started"), text, (width, text))
            self.assertNotIn("代理", text)
            self.assertNotIn("agent", text)

    def test_with_an_agent_and_a_pane_the_agents_minutes_count(self):
        self.add("t", "the task", 20, started=False)
        self.launch("tm-pane", "t", since="2026-11-02 14:59", agent=None)
        self.launch("deputy", "t", since="2026-11-02 14:40")
        r = self.rows()[0]
        self.assertEqual((r["Status"], r["Work"]), (self.st("running") + self.mark(1), "20m"))


class TestOneRowPerTaskEnglish(TestOneRowPerTask):
    lang = "en"
    ONE = " · 1 agent"
    TWO = " · 2 agents"


if __name__ == "__main__":
    unittest.main()
