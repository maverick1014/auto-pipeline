"""Failing tests of board-eta: the board's finish time follows the real state of a task
(requirements/board-eta.md; owner 2026-11-27 "check and find the root causes"). Written by the task manager first.

CONTRACT

1. The watch's stage reader (bin/agent_watch.py: stage_of for a local worktree, remote_command + its parse for one on
   another machine) carries the NEWEST stage line by TIME, not by file position:
     the time of a "STAGE <name>: <stage>[ <i>/<m>] | since <date>" line is its since date; of a
     "HEARTBEAT <name>: step <n> of 7, work <m>m, <text> | <date>" or a "STEP <n> ..." line, the date after its last " | ";
     a date is "YYYY-MM-DD HH:MM" (they compare as text);
     the newest time wins; a tie goes to the later line in the file;
     a line with no date counts as the newest time seen so far (it wins over the lines before it, as today).
   The rest of the reader stays: a heartbeat of the stage the STAGE line named keeps its "<i>/<m>"; a heartbeat's
   "<m>m <text>" goes to the beat; another task's line is not carried; one remote command per sweep, under
   REMOTE_CMD_MAX for a 140-char path.
2. carry_stage never moves the todo line's stage back from a stage the main manager set itself (e2e, merge):
   while the todo line reads "stage e2e|merge since <S>", a carried line is written only when it is a STAGE line whose
   since is later than S (the task manager started a new round). A held line's beat is not carried either.
   Any other todo stage: carried as today.
3. The forecast of a fix round (bin/agent_board.py forecast_of, bin/agent_forecast.py forecast): a running todo line
   whose stage log has a report or e2e entry (built_work, as today) and whose stage is a build stage
   (brief register mock tests workers verify push) is in a fix round.
     age = work - the stage log minute of the first entry after the last report, e2e or merge entry.
     past fix rounds = for each clean history row with a built and a stages map: the sum of its build-stage minutes
       minus its built, when that is more than 0 (every lane).
     5 or more past fix rounds: left = a draw of the past rounds that are more than the age, minus the age; none more:
       1 minute (the tail's age rule); p50 and p85 as for every forecast. No tail is added.
     fewer: the todo line's " | added <m>m" field: p50 = p85 = max(1, added - age).
     neither: the tail path of the report and e2e stages (past tails over work - built_work), never the step share.
   A first round (no report or e2e entry yet): the forecast of today, unchanged (an added field changes nothing).
4. Nothing else of the board, the estimate or the watch changes (the existing test files stay green).
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_agent_forecast as tf  # noqa: E402
import test_agent_watch as tw  # noqa: E402
from test_agent_estimate import day  # noqa: E402
from test_agent_estimate_inputs import row  # noqa: E402

ENV = tw.ENV
FILLER = ["note %d: something else happened | 2026-11-25 11:0%d" % (i, i) for i in range(5)]


# ---------------------------------------------------------------- rules 1 and 2: the watch

class EtaCarryCase(tw.CarryCase):

    def carry_at(self, env, lines, todo_stage=None, since=None, on_read=None, name="alpha"):
        """The todo line of the task; with todo_stage, the main manager set that stage itself at since (a fixed
        minute); then the worktree state gets the lines and the watch runs."""
        self.todo(name)
        if todo_stage:
            self.assertOk(self.repo.run("agent-file.sh", "todo", "stage", name, todo_stage))
            path = self.repo.path("agent_todo.txt")
            with open(path) as fh:
                text = fh.read()
            text = re.sub(r"( \| stage %s since )\d{4}-\d\d-\d\d \d\d:\d\d" % todo_stage, r"\g<1>" + since, text)
            with open(path, "w") as fh:
                fh.write(text)
            self.assertIn(" | stage %s since %s" % (todo_stage, since), self.todo_line(name))
        t = self.task(name, env=env, frames=tw.moving())
        self.append_state(name, *lines)
        self.on_task_read(name, on_read or {2: "ACK %s: still here" % name})
        return t, self.text(self.run_all(max_sweeps="4"))

    def both(self, check):
        for env in (None, ENV):
            with self.subTest(env=env):
                self.setUp()
                check(env)


class TestNewestByTime(EtaCarryCase):
    """Rule 1: the newest line by its own time wins; the file position only breaks a tie."""

    def test_a_newer_stage_line_above_an_older_heartbeat_wins(self):
        def check(env):
            self.carry_at(env, ["STAGE alpha: report | since 2026-11-25 11:10"] + FILLER
                          + ["HEARTBEAT alpha: step 5 of 7, work 90m, verify run | 2026-11-25 11:08"])
            line = self.todo_line("alpha")
            self.assertIn(" | stage report since ", line)
            self.assertNotIn(" | beat ", line)
        self.both(check)

    def test_a_newer_heartbeat_below_the_stage_line_wins(self):
        def check(env):
            self.carry_at(env, ["STAGE alpha: report | since 2026-11-25 11:10"] + FILLER
                          + ["HEARTBEAT alpha: step 5 of 7, work 90m, verify run | 2026-11-25 11:12"])
            line = self.todo_line("alpha")
            self.assertIn(" | stage verify since ", line)
            self.assertIn(" | beat 90m verify run", line)
        self.both(check)

    def test_a_tie_goes_to_the_later_line(self):
        def check(env):
            self.carry_at(env, ["STAGE alpha: tests | since 2026-11-25 11:10",
                                "HEARTBEAT alpha: step 5 of 7, work 90m, verify run | 2026-11-25 11:10"])
            self.assertIn(" | stage verify since ", self.todo_line("alpha"))
        self.both(check)

    def test_the_newest_of_several_heartbeats_wins_wherever_it_is(self):
        def check(env):
            self.carry_at(env, ["HEARTBEAT alpha: step 6 of 7, work 99m, pushing | 2026-11-25 11:30",
                                "STAGE alpha: tests | since 2026-11-25 10:00",
                                "HEARTBEAT alpha: step 4 of 7, work 50m, workers run | 2026-11-25 11:00"])
            line = self.todo_line("alpha")
            self.assertIn(" | stage push since ", line)
            self.assertIn(" | beat 99m pushing", line)
        self.both(check)

    def test_a_line_with_no_date_still_wins_over_the_lines_before_it(self):
        def check(env):
            self.carry_at(env, ["STAGE alpha: tests | since 2026-11-25 11:10", "STEP 6 push: pushed the branch"])
            self.assertIn(" | stage push since ", self.todo_line("alpha"))
        self.both(check)


class TestNeverBackPastTheMainManager(EtaCarryCase):
    """Rule 2: e2e and merge are the main manager's own stages; only a newer STAGE line (a new round) moves them."""

    def test_an_older_heartbeat_keeps_e2e(self):
        def check(env):
            self.carry_at(env, ["HEARTBEAT alpha: step 5 of 7, work 90m, verify run | 2026-11-25 11:08"],
                          todo_stage="e2e", since="2026-11-25 11:13")
            line = self.todo_line("alpha")
            self.assertIn(" | stage e2e since 2026-11-25 11:13", line)
            self.assertNotIn(" | beat ", line)
        self.both(check)

    def test_an_older_report_stage_line_keeps_e2e(self):
        def check(env):
            self.carry_at(env, ["STAGE alpha: report | since 2026-11-25 11:10"],
                          todo_stage="e2e", since="2026-11-25 11:13")
            self.assertIn(" | stage e2e since 2026-11-25 11:13", self.todo_line("alpha"))
        self.both(check)

    def test_a_stage_line_of_the_same_minute_keeps_e2e(self):
        def check(env):
            self.carry_at(env, ["STAGE alpha: report | since 2026-11-25 11:13"],
                          todo_stage="e2e", since="2026-11-25 11:13")
            self.assertIn(" | stage e2e since 2026-11-25 11:13", self.todo_line("alpha"))
        self.both(check)

    def test_a_newer_stage_line_starts_a_new_round(self):
        def check(env):
            self.carry_at(env, ["HEARTBEAT alpha: step 5 of 7, work 90m, verify run | 2026-11-25 11:08",
                                "STAGE alpha: workers | since 2026-11-25 11:20"],
                          todo_stage="e2e", since="2026-11-25 11:13")
            line = self.todo_line("alpha")
            self.assertIn(" | stage workers since ", line)
            self.assertNotIn(" | stage e2e since ", line)
        self.both(check)

    def test_a_newer_heartbeat_alone_keeps_merge(self):
        def check(env):
            self.carry_at(env, ["STAGE alpha: report | since 2026-11-25 11:10",
                                "HEARTBEAT alpha: step 4 of 7, work 95m, workers run | 2026-11-25 11:30"],
                          todo_stage="merge", since="2026-11-25 11:13")
            line = self.todo_line("alpha")
            self.assertIn(" | stage merge since 2026-11-25 11:13", line)
            self.assertNotIn(" | beat ", line)
        self.both(check)

    def test_a_task_managers_own_stage_is_carried_as_today(self):
        def check(env):
            self.carry_at(env, ["STAGE alpha: verify | since 2026-11-25 11:20"],
                          todo_stage="report", since="2026-11-25 11:30")
            self.assertIn(" | stage verify since ", self.todo_line("alpha"))
        self.both(check)


# ---------------------------------------------------------------- rule 3: the forecast of a fix round

def fix_rows(rounds):
    """One clean full-lane row per fix round f: built 40 (5 brief + 5 tests + 20 workers + 10 verify), then f more
    workers minutes, then report 5, e2e 10, merge 1."""
    out = []
    for i, f in enumerate(rounds):
        work = 40 + f + 16
        out.append(row(day(40 + i), "fx-%02d" % i, "fix round", lane="full", type="script", mock="no", est=60,
                       work=work, wait=0, clock=work + 10, built=40,
                       stages="brief:5,tests:5,workers:%d,verify:10,report:5,e2e:10,merge:1" % (20 + f)))
    return out


# work 171 at NOW (started 12:09, no wait); built_work 120 (the first report); the fix round began at push 129: age 42
FIX_LOG = "brief 0, tests 10, workers 30, verify 90, push 110, report 120, e2e 123, push 129, workers 168"
FIRST_LOG = "brief 0, tests 10, workers 30"


class FixCase(tf.BoardForecastCase):

    def line(self, log, extra="", est=135, stage="workers since 2026-11-02 14:57"):
        self.put("x | big | the login form | est %dm%s | opened 2026-11-02 12:00 | by main | stage log %s"
                 " | started 2026-11-02 12:09 | stage %s" % (est, extra, log, stage))

    def done_by(self):
        return self.row(self.rows(now=tf.NOW), task="x")["Done by"]

    def clocks(self):
        cell = self.done_by()
        m = tf.CELL2.match(cell)
        self.assertIsNotNone(m, cell)
        return m.group(1), m.group(2)


class TestFixRoundForecast(FixCase):

    def test_five_past_fix_rounds_give_tens_of_minutes_not_hundreds(self):
        # rounds over the age 42: 50 60 75 90 -> 8..48 minutes left; today's step share said hundreds
        self.history(tf.history_lines() + fix_rows([30, 50, 60, 75, 90]))
        self.line(FIX_LOG)
        p50, p85 = self.clocks()
        self.assertGreaterEqual(p50, "15:08")
        self.assertLessEqual(p50, p85)
        self.assertLessEqual(p85, "15:48")

    def test_past_every_fix_round_is_due_any_minute(self):
        self.history(tf.history_lines() + fix_rows([10, 15, 20, 25, 30]))
        self.line(FIX_LOG)
        self.assertEqual(self.done_by(), "15:01 / 15:01")

    def test_rows_with_no_fix_round_do_not_count(self):
        # four real rounds and five rows whose build ended at built: too little, so the added minutes decide
        self.history(tf.history_lines() + fix_rows([50, 60, 75, 90]) + fix_rows([0, 0, 0, 0, 0]))
        self.line(FIX_LOG, extra=" | est0 105m | added 30m", est=165)
        # added 30, age 42 -> 1
        self.assertEqual(self.done_by(), "15:01 / 15:01")

    def test_too_little_fix_history_uses_the_added_minutes(self):
        self.history(tf.history_lines() + fix_rows([50, 60, 75, 90]))
        self.line(FIX_LOG, extra=" | est0 135m | added 50m", est=185)
        # added 50, age 42 -> 8 minutes
        self.assertEqual(self.done_by(), "15:08 / 15:08")

    def test_the_added_minutes_need_no_history(self):
        self.line(FIX_LOG, extra=" | est0 135m | added 60m", est=195)
        self.assertEqual(self.done_by(), "15:18 / 15:18")

    def test_no_fix_history_and_no_added_minutes_use_the_tail_age_rule(self):
        # history_lines: tails 20 and 40; age since built 171 - 120 = 51 is past them all -> due any minute
        self.history(tf.history_lines())
        self.line(FIX_LOG)
        self.assertEqual(self.done_by(), "15:01 / 15:01")

    def test_a_fix_round_in_verify_is_a_fix_round_too(self):
        self.history(tf.history_lines() + fix_rows([50, 60, 75, 90]))
        self.line(FIX_LOG + ", verify 170", extra=" | est0 135m | added 50m", est=185,
                  stage="verify since 2026-11-02 14:59")
        self.assertEqual(self.done_by(), "15:08 / 15:08")

    def test_the_round_starts_after_the_last_tail_entry(self):
        # a second fix round: report 150, e2e 152, workers 160 -> age 11; added 30 -> 19 minutes
        log = "brief 0, tests 10, workers 30, verify 90, report 120, e2e 123, workers 129, report 150, e2e 152, workers 160"
        self.line(log, extra=" | est0 135m | added 30m", est=165)
        self.assertEqual(self.done_by(), "15:19 / 15:19")

    def test_eta_says_the_same_numbers(self):
        self.line(FIX_LOG, extra=" | est0 135m | added 50m", est=185)
        out = self.af("eta", "x", now=tf.NOW).stdout.strip()
        m = tf.ETA_FC.match(out)
        self.assertIsNotNone(m, out)
        self.assertEqual((m.group(1), m.group(2), m.group(3), m.group(4)), ("8", "8", "15:08", "15:08"))


class TestFirstRoundAsToday(FixCase):

    def test_a_first_round_ignores_the_added_minutes(self):
        self.history(tf.history_lines() + fix_rows([30, 50, 60, 75, 90]))
        self.line(FIRST_LOG)
        today = self.done_by()
        self.line(FIRST_LOG, extra=" | est0 105m | added 30m")
        self.assertEqual(self.done_by(), today)
        self.assertIsNotNone(tf.CELL2.match(today), today)

    def test_the_report_stage_keeps_the_tail_rule(self):
        self.history(tf.history_lines())
        self.line("brief 0, tests 10, workers 30, verify 90, report 120", extra=" | est0 105m | added 30m",
                  stage="report since 2026-11-02 14:00")
        # report: the tail age rule of today (age 51 past every tail of 20 and 40), the added minutes unused
        self.assertEqual(self.done_by(), "15:01 / 15:01")


if __name__ == "__main__":
    unittest.main()
