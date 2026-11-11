"""Failing tests for progress-bar: stages, the progress column, done-by from progress,
the live watch. Written by the task manager first.

Owner, 2026-11-11: after a dispatch the owner cannot see how far a task manager
is or when it ends, so he waits. The board said "over est" exactly when he was
waiting (the last 3 tasks ran 20-50% over their estimate).

OWNER DECISIONS (locked, 2026-11-11):
    1 progress % is by STAGE, not by time
    2 over the estimate, done-by comes from progress: remaining = work x (1-p)/p,
      shown as a clock time like today
      (bounce 1, main manager 2026-11-11: only over the estimate, and only from
      progress_eta_min_pct on; under the estimate done-by stays est-based)
    3 shown in three places: the board, the Claude Code status line
      (tests/test_agent_statusline.py), a live-refresh watch
    4 the bar: 10 cells of full/light blocks plus a right-aligned percent,
      "███████░░░  70%"

CONTRACT

Stages, in this order: the task manager brief steps 0-7, then the main
manager's E2E and merge:
    brief register mock tests workers verify push report e2e merge
Weights: agent.conf keys (agent-settings.sh, template bin/agent.conf.default),
relative, whole numbers 0 to 100, group "progress" (with board_watch_sec):
    stage_brief=1 stage_register=1 stage_mock=4 stage_tests=20 stage_workers=40
    stage_verify=15 stage_push=2 stage_report=2 stage_e2e=10 stage_merge=5
    board_watch_sec=60 (1 to 3600)
    progress_eta_min_pct=20 (0 to 100): over the estimate, progress gives the
    done-by only from this percent of progress on
    A key missing from agent.conf, or not valid there: the template value.
Progress p of a stage = (the sum of the weights of the stages before it, plus
    stage_workers x i/m for "workers i/m") / the sum of all weights. Exact (no
    float rounding). Percent = floor(100 p), at most 99: never 100 before
    merged (todo done takes the line away). Bar = floor(percent / 10) cells "█",
    the rest "░", 10 cells; board cell = bar, one space, the percent right-
    aligned in 3 characters, "%": "████░░░░░░  46%", "░░░░░░░░░░   0%".

    agent-file.sh todo stage "<name>" <stage> [<i>/<m>]
        <i>/<m> only with workers: i of m slices done; whole numbers, m >= 1,
        0 <= i <= m.
        The todo line gets the field " | stage <stage>[ <i>/<m>] since <date>"
        (YYYY-MM-DD HH:MM). Set again: replaced in place, once. The same value
        again: the line stays as it is (since too). Every other field stays.
        In a worktree (the git toplevel of the cwd is not the main repo) it
        also writes "STAGE <name>: <stage>[ <i>/<m>] | since <date>" into that
        folder's agent_state.txt: one line per name, replaced in place, the
        same value again leaves it; every other line byte for byte.
        No todo line of that name: in a worktree -> the STAGE line only, exit 0
        (a task manager on another machine; the main manager's agent-watch.sh
        carries it to the todo line there, tests/test_agent_watch.py); in the
        main repo -> refused.
        Prints one line that starts "todo stage: <name> -> <stage>".
        Refused (one line on stderr, exit 1, nothing written): no name, no
        stage, an unknown stage, <i>/<m> with another stage, a bad <i>/<m>,
        too many arguments.

Board (agent-file.sh board), a new column after Status: zh 进度, en Progress.
    A todo line with a stage: the bar. --self: its line has no stage field ->
    the STAGE line of that name in its own agent_state.txt. Every other row "-".
Done by (board and status line). work = work so far, p = progress (exact),
"far enough" = a stage and p > 0 and 100 p >= progress_eta_min_pct:
    work <  est  -> now + (est - work), as before, stage or not
    work >= est  -> far enough: now + ceil(work x (1-p) / p)
                    else: zh "超出 <n>" / en "over by <n>", n = work - est in
                    real units ("30m", "1h 30m")
    no est       -> far enough: now + ceil(work x (1-p) / p); else "-"
    The clock words as before: "HH:MM", zh "明天 HH:MM" / en "HH:MM tomorrow",
    a later day zh "YYYY-MM-DD HH:MM" / en "HH:MM on YYYY-MM-DD".

Watch: agent-file.sh board [--self] --watch [<sec>]
    Every <sec> seconds (default board_watch_sec): "\\033[H\\033[2J" (clear),
    the board as printed, then one footer line, zh "每 <sec> 秒刷新 · Ctrl-C 停止",
    en "refresh every <sec>s · Ctrl-C stops". The clock is read again each
    frame (AGENT_FAKE_NOW wins). Ctrl-C (SIGINT to the process group): exit 0,
    no traceback. A <sec> that is not a whole number from 1: refused.

Skills: the dispatch task manager brief tells the task manager to run
    ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" <stage> at each
    step (workers with <i>/<m> after each verified slice); the merge skill tells
    the main manager e2e and merge. PRINCIPLES.md W14 names todo stage.
"""

import os
import signal
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
BIN = os.path.join(os.path.dirname(HERE), "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import test_agent_board as tb  # noqa: E402  (the module only: its tests stay in their own module)
from scripthelp import ROOT  # noqa: E402

NOW = tb.NOW   # "2026-11-02 15:00"
STAGES = ["brief", "register", "mock", "tests", "workers", "verify", "push", "report", "e2e", "merge"]
DEFAULTS = {"stage_brief": "1", "stage_register": "1", "stage_mock": "4", "stage_tests": "20",
            "stage_workers": "40", "stage_verify": "15", "stage_push": "2", "stage_report": "2",
            "stage_e2e": "10", "stage_merge": "5", "board_watch_sec": "60",
            "progress_eta_min_pct": "20"}
BOUNDS = {"board_watch_sec": (1, 3600)}   # every other key: (0, 100)
CLEAR = "\x1b[H\x1b[2J"


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class StageCase(tb.BoardCase):
    lang = "zh"

    def stage(self, name, *args, now=NOW, cwd=None):
        return self.af("todo", "stage", name, *args, now=now, cwd=cwd)

    def board_row(self, name, *args, now=NOW, cwd=None):
        return self.row(self.rows(*args, now=now, cwd=cwd), task=name)

    def progress(self, name, **kw):
        return self.board_row(name, **kw)["Progress"]

    def done_by(self, name, **kw):
        return self.board_row(name, **kw)["Done by"]


# ---------------------------------------------------------------- todo stage


class TestStageRecord(StageCase):
    def test_the_field_on_the_todo_line(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        before = self.todo_line("alpha")
        out = self.stage("alpha", "tests", now="2026-11-02 14:10").stdout
        line = self.todo_line("alpha")
        self.assertTrue(line.startswith(before), line)
        self.assertTrue(line.endswith(" | stage tests since 2026-11-02 14:10"), line)
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        self.assertTrue(out.startswith("todo stage: alpha -> tests"), out)

    def test_set_again_is_replaced_in_place_once(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "tests", now="2026-11-02 14:10")
        self.af("todo", "where", "alpha", "pc2", "/x/alpha")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:30")
        line = self.todo_line("alpha")
        self.assertEqual(line.count(" | stage "), 1, line)
        self.assertIn(" | stage workers 1/2 since 2026-11-02 14:30 | on pc2 /x/alpha", line)

    def test_the_same_value_again_keeps_the_line(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:10")
        before = self.todo_line("alpha")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:40")
        self.assertEqual(self.todo_line("alpha"), before)
        self.stage("alpha", "workers", "2/2", now="2026-11-02 14:50")
        self.assertIn(" | stage workers 2/2 since 2026-11-02 14:50", self.todo_line("alpha"))

    def test_wait_where_eta_and_done_still_read_the_line(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 13:00")
        self.stage("alpha", "verify", now="2026-11-02 13:30")
        self.wait("alpha", "on", "review", now="2026-11-02 14:00")
        self.af("todo", "where", "alpha", "pc2", "/x/alpha")
        line = self.todo_line("alpha")
        self.assertIn(" | stage verify since 2026-11-02 13:30", line)
        self.assertIn(" | waiting review since 2026-11-02 14:00", line)
        self.wait("alpha", "off", now="2026-11-02 14:20")
        self.assertIn(" | stage verify since 2026-11-02 13:30", self.todo_line("alpha"))
        self.assertIn("work left", self.af("eta", "alpha", "--step", "5").stdout)
        self.af("todo", "done", "alpha", "--work", "70")
        done = self.repo.read("agent_completed.txt")
        self.assertIn(" | alpha | the login form | data ", done)
        self.assertIn(" est=120 ", done)
        self.assertIsNone(self.todo_line("alpha"))

    def test_every_stage_word_is_taken(self):
        self.add("alpha", "the login form", 60)
        for word in STAGES:
            with self.subTest(stage=word):
                self.stage("alpha", word)
                self.assertIn(" | stage %s since " % word, self.todo_line("alpha"))

    def test_refusals(self):
        self.add("alpha", "the login form", 60)
        self.stage("alpha", "tests", now="2026-11-02 14:10")
        for args in (("todo", "stage"),
                     ("todo", "stage", "alpha"),
                     ("todo", "stage", "nobody", "tests"),
                     ("todo", "stage", "alpha", "coffee"),
                     ("todo", "stage", "alpha", "Tests"),
                     ("todo", "stage", "alpha", "tests", "1/2"),
                     ("todo", "stage", "alpha", "workers", "3/2"),
                     ("todo", "stage", "alpha", "workers", "0/0"),
                     ("todo", "stage", "alpha", "workers", "a/b"),
                     ("todo", "stage", "alpha", "workers", "1"),
                     ("todo", "stage", "alpha", "workers", "-1/2"),
                     ("todo", "stage", "alpha", "workers", "1/2", "extra")):
            with self.subTest(args=args):
                self.refused(*args)


class TestStageInWorktree(StageCase):
    def setUp(self):
        super().setUp()
        self.alpha = self.task_worktree("alpha")

    def test_the_stage_line_in_its_own_state(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:30", cwd=self.alpha)
        self.assertIn(" | stage workers 1/2 since 2026-11-02 14:30", self.todo_line("alpha"))
        self.assertIn("STAGE alpha: workers 1/2 | since 2026-11-02 14:30\n", self.state_text(self.alpha))
        self.assertNotIn("STAGE ", self.state_text())

    def test_one_stage_line_replaced_in_place(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.state("brief line one\nHEARTBEAT alpha: step 3 of 7\n", folder=self.alpha)
        self.stage("alpha", "tests", now="2026-11-02 14:10", cwd=self.alpha)
        self.state("a line after\n", folder=self.alpha)
        self.stage("alpha", "verify", now="2026-11-02 14:50", cwd=self.alpha)
        self.assertEqual(self.state_text(self.alpha),
                         "brief line one\nHEARTBEAT alpha: step 3 of 7\n"
                         "STAGE alpha: verify | since 2026-11-02 14:50\n"
                         "a line after\n")
        self.stage("alpha", "verify", now="2026-11-02 14:55", cwd=self.alpha)
        self.assertIn("STAGE alpha: verify | since 2026-11-02 14:50\n", self.state_text(self.alpha))

    def test_no_todo_line_here_writes_the_stage_line_only(self):
        """A task manager on another machine: its todo line is on the laptop."""
        before = self.repo.read("agent_todo.txt")
        result = self.stage("alpha", "tests", now="2026-11-02 14:10", cwd=self.alpha)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.repo.read("agent_todo.txt"), before)
        self.assertIn("STAGE alpha: tests | since 2026-11-02 14:10\n", self.state_text(self.alpha))

    def test_in_the_main_repo_no_stage_line(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "e2e", now="2026-11-02 14:10")
        self.assertIn(" | stage e2e since 2026-11-02 14:10", self.todo_line("alpha"))
        self.assertNotIn("STAGE ", self.state_text())


# ---------------------------------------------------------------- the column


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
        self.assertEqual(tb.cells(head), tb.HEAD["zh"])
        self.assertEqual(tb.cells(head)[3], "进度")

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

    def test_the_weights_come_from_agent_conf(self):
        self.repo.set_conf("stage_workers", "80")
        self.add("alpha", "the login form", 60)
        self.stage("alpha", "verify")
        # (1 + 1 + 4 + 20 + 80) / 140 = 75.7 %
        self.assertEqual(self.progress("alpha"), "███████░░░  75%")

    def test_a_bad_weight_is_the_template_value(self):
        self.repo.set_conf("stage_workers", "lots")
        self.add("alpha", "the login form", 60)
        self.stage("alpha", "verify")
        self.assertEqual(self.progress("alpha"), "██████░░░░  66%")

    def test_never_100_before_merged(self):
        self.repo.set_conf("stage_merge", "0")
        self.add("alpha", "the login form", 60)
        self.stage("alpha", "merge")
        self.assertEqual(self.progress("alpha"), "█████████░  99%")


class TestProgressColumnEnglish(StageCase):
    lang = "en"

    def test_the_header(self):
        self.add("alpha", "the login form", 60)
        self.stage("alpha", "tests")
        head = [l for l in self.board().splitlines() if l.startswith("|")][0]
        self.assertEqual(tb.cells(head)[3], "Progress")
        self.assertEqual(self.progress("alpha"), "░░░░░░░░░░   6%")


# ---------------------------------------------------------------- done by


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

    def test_the_minimum_comes_from_agent_conf(self):
        # workers p = 26/100: at 26 progress counts (60 x 74/26 = 170.8 -> 171 -> 17:51), at 27 not
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "workers")
        self.assertEqual(self.done_by("alpha"), "17:51")
        self.repo.set_conf("progress_eta_min_pct", "26")
        self.assertEqual(self.done_by("alpha"), "17:51")
        self.repo.set_conf("progress_eta_min_pct", "27")
        self.assertEqual(self.done_by("alpha"), "超出 20m")
        self.repo.set_conf("progress_eta_min_pct", "lots")   # bad -> the template value, 20
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
        self.stage("alpha", "verify", now="2026-11-02 23:00")
        self.assertEqual(self.done_by("alpha", now="2026-11-02 23:30"), "明天 00:01")


class TestDoneByEnglish(StageCase):
    lang = "en"

    def test_words(self):
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.add("beta", "bank recon match", 40, opened="2026-11-02 14:00")
        self.add("night", "finishes after midnight", 30, opened="2026-11-02 22:30")
        self.stage("night", "verify")
        rows = self.rows()
        self.assertEqual(self.row(rows, task="alpha")["Done by"], "15:31")
        self.assertEqual(self.row(rows, task="beta")["Done by"], "over by 20m")
        self.assertEqual(self.done_by("night", now="2026-11-02 23:30"), "00:01 tomorrow")


# ---------------------------------------------------------------- --self


class TestSelfStage(StageCase):
    def setUp(self):
        super().setUp()
        self.alpha = self.task_worktree("alpha")

    def test_its_todo_line_without_a_stage_reads_its_stage_line(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.state("STAGE alpha: verify | since 2026-11-02 14:50\n", folder=self.alpha)
        r = self.board_row("alpha", "--self", cwd=self.alpha)
        self.assertEqual((r["Progress"], r["Done by"]), ("██████░░░░  66%", "16:00"))

    def test_on_another_machine_its_todo_line_and_stage_come_from_its_state(self):
        self.state("TODO LINE: alpha | big | the login form | est 60m | opened 2026-11-02 14:30 | by main\n",
                   folder=self.alpha)
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:50", cwd=self.alpha)
        r = self.board_row("alpha", "--self", cwd=self.alpha)
        # work 30 < est 60: the estimate, 15:30
        self.assertEqual((r["Progress"], r["Done by"]), ("████░░░░░░  46%", "15:30"))


# ---------------------------------------------------------------- the watch


class TestWatch(StageCase):
    def popen(self, *args, cwd=None):
        env = self.repo._env({"AGENT_FAKE_NOW": NOW, "AGENT_FAKE_HOST": tb.HOST})
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
        self.assertIn("| alpha | the login form | 进行中 | ██████░░░░  66% |", first)
        self.assertIn("每 1 秒刷新 · Ctrl-C 停止", first.strip().splitlines()[-1])

    def test_the_default_comes_from_agent_conf(self):
        self.repo.set_conf("board_watch_sec", "7")
        code, out, err = self.ctrl_c(self.popen("--watch"), 1.5)
        self.assertEqual(code, 0, err)
        self.assertEqual(out.count(CLEAR), 1, out)
        self.assertIn("每 7 秒刷新 · Ctrl-C 停止", out)
        self.assertIn("无", out)

    def test_self_watch(self):
        alpha = self.task_worktree("alpha")
        self.add("alpha", "the login form", 60)
        self.add("beta", "bank recon match", 60)
        code, out, err = self.ctrl_c(self.popen("--self", "--watch", "1", cwd=alpha), 1.5)
        self.assertEqual(code, 0, err)
        self.assertIn("| alpha |", out)
        self.assertNotIn("| beta |", out)

    def test_refusals(self):
        for args in (("--watch", "0"), ("--watch", "-3"), ("--watch", "abc"),
                     ("--watch", "1.5"), ("--watch", "1", "2")):
            with self.subTest(args=args):
                result = self.repo.run("agent-file.sh", "board", *args, timeout=15,
                                       env={"AGENT_FAKE_NOW": NOW, "AGENT_FAKE_HOST": tb.HOST})
                self.assertEqual(result.returncode, 1, (result.stdout, result.stderr))
                self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)


class TestWatchEnglish(TestWatch):
    lang = "en"

    def test_frames_then_ctrl_c_stops_cleanly(self):
        self.add("alpha", "the login form", 60)
        code, out, err = self.ctrl_c(self.popen("--watch", "1"), 1.5)
        self.assertEqual(code, 0, err)
        self.assertIn("refresh every 1s · Ctrl-C stops", out)

    def test_the_default_comes_from_agent_conf(self):
        self.repo.set_conf("board_watch_sec", "7")
        code, out, err = self.ctrl_c(self.popen("--watch"), 1.5)
        self.assertEqual(code, 0, err)
        self.assertIn("refresh every 7s · Ctrl-C stops", out)


# ---------------------------------------------------------------- config


class TestConfKeys(unittest.TestCase):
    def setUp(self):
        import agent_conf
        self.ac = agent_conf

    def test_bounds(self):
        for key in DEFAULTS:
            with self.subTest(key=key):
                want = BOUNDS.get(key, (0, 100))
                self.assertEqual(self.ac.NUMBER_BOUNDS.get(key), want)

    def test_template_defaults(self):
        conf = self.ac.load(os.path.join(ROOT, "bin", "agent.conf.default"))
        for key, value in DEFAULTS.items():
            with self.subTest(key=key):
                self.assertEqual(conf.get(key), value)
        self.assertEqual(self.ac.validate(conf), {})

    def test_hints_and_group(self):
        self.assertIn(("progress", list(DEFAULTS)), self.ac.GROUPS)
        for key in DEFAULTS:
            with self.subTest(key=key):
                self.assertTrue(self.ac.HINTS.get(key, "").strip())
                self.assertEqual(self.ac.group_of(key), "progress")


class TestSettingsWritesWeights(tb.BoardCase):
    script = "agent-settings.sh"

    def test_set_and_refuse(self):
        ok = self.repo.run("agent-settings.sh", "stage_workers", "50")
        self.assertOk(ok)
        self.assertIn("stage_workers=50\n", self.repo.read("agent.conf"))
        bad = self.repo.run("agent-settings.sh", "stage_workers", "101")
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("stage_workers=50\n", self.repo.read("agent.conf"))


# ---------------------------------------------------------------- skills


def brief_block(text):
    start = text.index("## Task manager brief")
    end = text.index("## Cross-repo brief")
    return text[start:end]


class TestSkills(unittest.TestCase):
    CMD = '${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" '

    def test_the_brief_names_every_task_manager_stage(self):
        block = brief_block(read("skills", "dispatch", "SKILL.md"))
        for word in STAGES[:8]:
            with self.subTest(stage=word):
                self.assertIn(self.CMD + word, block)
        self.assertIn(self.CMD + "workers <i>/<m>", block)

    def test_the_merge_skill_names_e2e_and_merge(self):
        text = read("skills", "merge", "SKILL.md")
        self.assertIn(self.CMD + "e2e", text)
        self.assertIn(self.CMD + "merge", text)
        self.assertLess(text.index(self.CMD + "e2e"), text.index(self.CMD + "merge"))

    def test_principles_show_todo_names_the_stage_record(self):
        text = read("PRINCIPLES.md")
        w14 = text[text.index("W14. Show todo"):text.index("W15. Watch")]
        self.assertIn("todo stage", w14)
        self.assertIn("progress", w14.lower())


if __name__ == "__main__":
    unittest.main()
