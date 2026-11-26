"""Failing tests of estimate-improve, part D: self-improvement (requirements/estimate-improve.md, section 5
items 12-13). Written by the task manager first. Parts A, B and C are assumed.

CONTRACT

D12 retrain every 10 finished tasks (bin/agent_estimate.py, bin/agent-file.sh).
    Due: clean tasks now >= the file's checked_tasks + RETRAIN_EVERY (10). The weekly rule goes: the check
    date is still written, never read for being due. --force skips the count, never the 30.
    Not due: "estimate retrain: not due (<N> tasks, next check at <checked + 10>)".
    A worse model is never kept: the rules that keep a new version stay as they are (on the new tasks, or
    by the rolling backtest when the method changes), and "kept v<current>" when it is not better.
    The measures: after its line (and the retrain when due) `todo done` appends one entry to the list
    "measures" of agent_estimate.txt, only when the file reads as a model (no file: nothing written):
        {"date": <today>, "tasks": <clean tasks>, "n": <scored rows>, "winner": <winner>,
         "work_bias": b, "work_spread": s, "end_bias": b, "end_spread": s, "p85": <holds %>,
         "live_small": <error>, "live_big": <error>}
    each value as the backtest's measure lines print it (numbers; null for "-"). Every save of the file
    keeps the list (retrain included). A failure never stops todo done.
D12b fix order 2 (main manager, 2026-11-26): todo done never waits for the estimator (on 182 real rows the
    backtest took about 20 s and todo done about 52 s). After its record is written, todo done queues one
    estimator run, a file in <git common dir>/agent_estimate.queue/, and starts the runner detached
    (stdin, stdout and stderr not shared with the caller) unless one runs: <git common dir>/agent_estimate.lock/
    is a directory holding the runner's pid in the file "pid"; a lock whose pid is dead is taken over. The runner
    takes the queue files oldest first, for each: the retrain when due, then one measures entry; every line it
    prints goes to <git common dir>/agent_estimate.log; it removes its lock when the queue is empty and looks once
    more (a file queued meanwhile is never lost). A second todo done while it runs only queues its file. Nothing of
    it ever changes todo done's exit code; todo done prints nothing about it and returns in under 3 seconds.
    AGENT_ESTIMATE_WAIT=1: todo done waits for that run and prints its verdict line (as before fix order 2).
D13 the slip flag (bin/agent-file.sh todo stage, bin/agent_board.py).
    todo stage on a todo line of this repo: after the stage is written, when the board's forecast of that
    line gives numbers (part C), the field " | p50 <YYYY-MM-DD HH:MM> at <YYYY-MM-DD HH:MM>" (the p50 clock
    time of the cell, the time it was asked) at the end of the line, replaced in place; no forecast: the
    line keeps whatever it had.
    The board: a running row with a forecast and that field: X = minutes from the field's p50 to the p50 of
    now (below 0 when earlier), T = minutes from the field's "at" to now; X > T -> the Status cell ends
    with " · p50 +<X>m in <T>m". Else nothing.
"""

import json
import os
import re
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from test_agent_estimate import EstimateCase, steady, version, TODAY  # noqa: E402
from test_agent_forecast import BoardForecastCase, history_lines, CELL2, NOW  # noqa: E402

NOT_DUE = re.compile(r"^estimate retrain: not due \((\d+) tasks, next check at (\d+)\)$")
MEASURE_KEYS = {"date", "tasks", "n", "winner", "work_bias", "work_spread", "end_bias", "end_spread", "p85",
                "live_small", "live_big"}


class LearnCase(EstimateCase):
    """These tests read the verdict and the measures right after todo done: they wait for the run."""

    def af(self, *args, **kwargs):
        env = {"AGENT_FAKE_NOW": kwargs.pop("now", "2026-10-05 16:00"), "AGENT_ESTIMATE_WAIT": kwargs.pop("wait", "1")}
        return self.repo.run("agent-file.sh", *args, env=env, **kwargs)

    def todo(self, name="t-new"):
        self.write("agent_todo.txt", "%s | big | one shell script | est 50m | opened 2026-10-05 15:35 | by main\n" % name)

    def done(self, name="t-new"):
        return self.assertOk(self.af("todo", "done", name, "--wait", "0",
                                     "--lane", "full", "--mock", "no", "--type", "script"))


# ---------------------------------------------------------------- D12 the cadence

class TestEveryTenTasks(LearnCase):

    def test_9_new_tasks_are_not_due_whatever_the_date(self):
        self.completed(steady(39))
        self.model(checked=30, date="2026-08-01")        # two months ago: the week no longer matters
        out = self.assertOk(self.af("retrain"))
        self.assertEqual(self.lines(out), ["estimate retrain: not due (39 tasks, next check at 40)"])

    def test_10_new_tasks_are_due_the_next_day(self):
        self.completed(steady(40))
        self.model(checked=30, date=TODAY)               # checked today: the 10 tasks still make it due
        out = self.assertOk(self.af("retrain"))
        self.assertTrue([l for l in self.lines(out) if l.startswith("estimate retrain: kept v")], out)
        data = self.model_json()
        self.assertEqual((data["checked_tasks"], data["checked_date"]), (40, TODAY))
        self.assertEqual(len(data["checks"]), 1)

    def test_force_skips_the_count(self):
        self.completed(steady(31))
        self.model(checked=30, date=TODAY)
        out = self.assertOk(self.af("retrain", "--force"))
        self.assertTrue([l for l in self.lines(out) if l.startswith("estimate retrain: kept v")], out)

    def test_6_9_the_10th_todo_done_retrains_and_keeps_no_worse_model(self):
        # an exact estimator: the new version is no better on the new tasks, so v1 stays
        self.completed(steady(39))
        self.model(checked=30, date=TODAY)
        self.todo()
        v = [l for l in self.lines(self.done()) if l.startswith("estimate retrain: ")]
        self.assertEqual(len(v), 1, v)
        self.assertTrue(v[0].startswith("estimate retrain: kept v1 "), v[0])
        data = self.model_json()
        self.assertEqual((data["current"], data["checked_tasks"]), (1, 40))

    def test_the_9th_todo_done_says_nothing(self):
        self.completed(steady(38))
        self.model(checked=30, date=TODAY)
        self.todo()
        self.assertEqual([l for l in self.lines(self.done()) if l.startswith("estimate retrain: ")], [])
        self.assertEqual(self.model_json()["checked_tasks"], 30)


# ---------------------------------------------------------------- D12 the measures

class TestMeasuresKept(LearnCase):

    def backtest_measure(self):
        out = self.assertOk(self.af("backtest"))
        line = [l for l in self.lines(out) if l.startswith("measure work: ")][0]
        m = re.match(r"^measure work: n (\d+) bias (\S+) spread (\S+)$", line)
        return int(m.group(1)), float(m.group(2)), float(m.group(3))

    def test_each_todo_done_appends_one_entry(self):
        self.completed(steady(34))
        self.model(checked=30, date=TODAY)
        for i in range(2):
            self.todo("t-%d" % i)
            self.done("t-%d" % i)
        data = self.model_json()
        self.assertEqual(len(data["measures"]), 2, data)
        last = data["measures"][-1]
        self.assertEqual(set(last), MEASURE_KEYS)
        self.assertEqual((last["date"], last["tasks"]), (TODAY, 36))
        n, bias, spread = self.backtest_measure()
        self.assertEqual((last["n"], last["work_bias"], last["work_spread"]), (n, bias, spread))
        self.assertIsNone(last["live_big"])

    def test_a_retrain_keeps_the_list(self):
        self.completed(steady(39))
        self.model(checked=30, date=TODAY)
        data = self.model_json()
        data["measures"] = [{"date": "2026-10-01", "tasks": 30, "n": 20, "winner": "estimator", "work_bias": 0.0,
                             "work_spread": 0.1, "end_bias": 0.0, "end_spread": 0.1, "p85": 100,
                             "live_small": None, "live_big": None}]
        self.write("agent_estimate.txt", json.dumps(data))
        self.todo()
        self.done()                                       # the 40th: a retrain and an entry
        data = self.model_json()
        self.assertEqual(len(data["checks"]), 1)
        self.assertEqual([m["date"] for m in data["measures"]], ["2026-10-01", TODAY])

    def test_no_model_file_writes_none(self):
        self.completed(steady(20))
        self.todo()
        self.done()
        self.assertIsNone(self.model_text())

    def test_a_bad_measure_never_stops_todo_done(self):
        # under 30 clean tasks no v1 is made, so the file that does not read stays as it is
        self.completed(steady(20))
        self.write("agent_estimate.txt", "{not json")
        self.todo()
        out = self.done()
        self.assertIn("todo done: t-new", out)
        self.assertEqual(self.model_text(), "{not json")


# ---------------------------------------------------------------- D12b the background run

class TestTodoDoneInTheBackground(LearnCase):

    def git_dir(self, *parts):
        return os.path.join(self.repo.dir, ".git", *parts)

    def settle(self, timeout=240):
        """Wait until the runner is gone and the queue is empty."""
        end = time.time() + timeout
        while time.time() < end:
            q = self.git_dir("agent_estimate.queue")
            if not os.path.isdir(self.git_dir("agent_estimate.lock")) and (not os.path.isdir(q) or not os.listdir(q)):
                return
            time.sleep(0.5)
        self.fail("the estimator run did not end in %d s" % timeout)

    def log(self):
        path = self.git_dir("agent_estimate.log")
        return open(path).read() if os.path.exists(path) else ""

    def quick_done(self, name):
        start = time.time()
        out = self.assertOk(self.af("todo", "done", name, "--wait", "0", "--lane", "full", "--mock", "no",
                                    "--type", "script", wait=""))
        return out, time.time() - start

    def test_todo_done_does_not_wait_for_the_backtest(self):
        self.completed(steady(120))
        self.model(checked=120, date=TODAY)
        self.todo()
        out, took = self.quick_done("t-new")
        self.assertLess(took, 3.0, out)
        self.assertIn("todo done: t-new", out)
        self.assertEqual([l for l in self.lines(out) if l.startswith("estimate retrain")], [])
        self.settle()
        self.assertEqual(len(self.model_json()["measures"]), 1)
        self.assertNotIn("Traceback", self.log())

    def test_two_todo_done_in_a_row_lose_nothing(self):
        self.completed(steady(120))
        self.model(checked=120, date=TODAY)
        self.write("agent_todo.txt", "".join(
            "t-%d | big | one shell script | est 50m | opened 2026-10-05 15:35 | by main\n" % i for i in range(2)))
        self.quick_done("t-0")
        self.quick_done("t-1")
        done = [l for l in self.repo.read("agent_completed.txt").splitlines() if " | t-0 | " in l or " | t-1 | " in l]
        self.assertEqual(len(done), 2)
        self.settle()
        self.assertEqual(len(self.model_json()["measures"]), 2)
        self.assertNotIn("Traceback", self.log())

    def test_a_dead_runner_lock_is_taken_over(self):
        self.completed(steady(40))
        self.model(checked=40, date=TODAY)
        os.makedirs(self.git_dir("agent_estimate.lock"))
        with open(self.git_dir("agent_estimate.lock", "pid"), "w") as fh:
            fh.write("999999\n")
        self.todo()
        self.quick_done("t-new")
        self.settle()
        self.assertEqual(len(self.model_json()["measures"]), 1)

    def test_the_due_retrain_runs_in_the_background_too(self):
        self.completed(steady(39))
        self.model(checked=30, date=TODAY)
        self.todo()
        self.quick_done("t-new")
        self.settle()
        self.assertEqual(self.model_json()["checked_tasks"], 40)
        self.assertIn("estimate retrain: kept v1", self.log())


# ---------------------------------------------------------------- D13 the slip flag

class TestSlipFlag(BoardForecastCase):

    def line_with(self, field):
        self.put("x | big | the login form | est 60m | opened 2026-11-02 14:00 | by main"
                 " | started 2026-11-02 14:10 | stage verify since 2026-11-02 14:50" + field)

    def status(self):
        return self.row(self.rows(now=NOW), task="x")["Status"]

    def test_13_a_slip_faster_than_the_clock_is_flagged(self):
        self.history(history_lines())
        self.line_with(" | p50 2026-11-02 15:00 at 2026-11-02 14:50")
        cell = CELL2.match(self.row(self.rows(now=NOW), task="x")["Done by"])
        x = (int(cell.group(1)[:2]) * 60 + int(cell.group(1)[3:])) - 15 * 60
        self.assertGreater(x, 10)
        self.assertTrue(self.status().endswith(" · p50 +%dm in 10m" % x), self.status())

    def test_an_earlier_p50_is_no_slip(self):
        self.history(history_lines())
        self.line_with(" | p50 2026-11-02 16:30 at 2026-11-02 14:50")
        self.assertNotIn("p50", self.status())

    def test_a_slip_slower_than_the_clock_is_no_flag(self):
        self.history(history_lines())
        self.line_with(" | p50 2026-11-02 15:30 at 2026-11-02 14:00")
        self.assertNotIn("p50", self.status())

    def test_no_history_no_flag(self):
        self.line_with(" | p50 2026-11-02 15:00 at 2026-11-02 14:50")
        self.assertNotIn("p50", self.status())

    def test_todo_stage_records_the_p50(self):
        self.history(history_lines())
        self.put("x | big | the login form | est 60m | opened 2026-11-02 14:00 | by main"
                 " | started 2026-11-02 14:10 | stage tests since 2026-11-02 14:30")
        self.af("todo", "stage", "x", "verify", now=NOW)
        line = self.todo_line("x")
        m = re.search(r" \| p50 (2026-11-02 (\d\d:\d\d)) at 2026-11-02 15:00$", line)
        self.assertIsNotNone(m, line)
        cell = CELL2.match(self.row(self.rows(now=NOW), task="x")["Done by"])
        self.assertEqual(m.group(2), cell.group(1))
        self.af("todo", "stage", "x", "push", now="2026-11-02 15:05")
        line = self.todo_line("x")
        self.assertEqual(line.count(" | p50 "), 1, line)
        self.assertTrue(line.endswith(" at 2026-11-02 15:05"), line)

    def test_no_history_no_field(self):
        self.put("x | big | the login form | est 60m | opened 2026-11-02 14:00 | by main"
                 " | started 2026-11-02 14:10 | stage tests since 2026-11-02 14:30")
        self.af("todo", "stage", "x", "verify", now=NOW)
        self.assertNotIn(" | p50 ", self.todo_line("x"))


if __name__ == "__main__":
    unittest.main()
