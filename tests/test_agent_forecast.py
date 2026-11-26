"""Failing tests of estimate-improve, part C: the end time (requirements/estimate-improve.md, section 5
items 8-11) and the live forecast measure of section 4. Written by the task manager first.
Parts A and B are assumed (tests/test_agent_estimate_inputs.py, tests/test_agent_estimate_fit.py).

CONTRACT

bin/agent_forecast.py (new; Python 3.9 standard library; the board, eta and the backtest all use it)

  FORECAST_MIN_ROWS = 10, ES_MIN = 0.2, DRAWS = 10000, SEED = 26.
  BUILD = (brief register mock tests workers verify push), TAIL = (report e2e merge): the stage words.

  history(root) -> rows from <root>/agent_completed.txt: clean lines only (part A's rule after fix order 1:
      clock a number, work <= clock <= 1440; the wait may be missing), each a dict
        est    est0 when a number, else est, else None
        label  built when a number, else work
        tail   work - built when built is a number, else max(0, clock - wait - work) when wait is a number,
               else None (the row teaches the work, not the tail)
        lane   "fast" or "full" (anything else: "full")
        built  built or None; stages {stage: minutes} (empty when "-"); slices [minutes]
  forecast(task, rows, draws=DRAWS, seed=SEED) -> (p50, p85) minutes still to go, or None
      task: est (minutes), work (work minutes so far), stage (None or (name, i, m), i and m None unless
            workers i/m), p (progress 0..1 from the stage weights, or None), lane, built_work (the work
            minutes at the builder's done, or None)
      The pool: the rows of the task's lane when 10 or more of them have an est and a label, else every
      such row; fewer than FORECAST_MIN_ROWS in the pool: None.
      Q = label / est of the pool rows; T = the pool rows' tails that are not None (none: every tail is 0). Each draw (random.Random(seed), uniform
      with replacement):
        stage None or a BUILD stage:
          q = a draw of Q; total = est x q. Age rule: when total <= work, q is drawn from the Q values with
          est x q > work instead; none: total = work / p when p >= ES_MIN, else 2 x work.
          Earned schedule: p >= ES_MIN -> total = max(total, work / p).
          build = max(0, total - work).
          Stage workers i/m with m - i >= 1 open slices: plan = est x stage_workers / (sum of the stage
          weights) / m; slices = the max over the open slices of plan x (an own draw of Q each);
          build = max(build, slices).
          tail = a draw of T.
        stage report: build = 0, tail = a draw of T.
        stage e2e or merge: build = 0; age = work - built_work (built_work None: 0); tail = a draw of the
          T values > age, minus age; none: a draw of T (a new round).
        left = build + tail.
      p50, p85 = the 50th and the 85th percentile (linear) of left over the draws, each rounded UP to a
      whole minute.
  slices_end(plans, ratios, draws=DRAWS, seed=SEED) -> (p50, p85): of max_j (plans[j] x a draw of ratios),
      rounded up.

The board (bin/agent_board.py): the "Done by" cell of a running row with an est and a work: the forecast
  of that row (rows = history(the project root); work, p, stage as the board counts them; built_work from
  the line's stage log, the minutes of its first report entry, else of its first e2e entry, else None;
  lane "fast" when field 2 of the todo line is "small", else "full").
  A forecast -> "<p50 clock> / <p85 clock>" (each written as the cell writes one time today: "HH:MM",
  "HH:MM tomorrow", "HH:MM on <date>", zh as today). None -> the cell of today, unchanged.
  An open wait on the owner stays apart (the Wait cell), never inside the forecast.
eta <name> (bin/agent-file.sh) with neither --step nor --work-so-far: the same numbers as that cell (one
  function, one answer):
    a forecast -> "about <p50> min of work left (85%: <p85> min), done around <t50> (85%: <t85>);
                   owner needed next: <who> about <when>"
    none       -> "about <m> min of work left, done around <t>; owner needed next: <who> about <when>"
                  with <t> the time of today's board cell and m = minutes from now to it; a cell of
                  "over by" (no time) -> refused, one line naming --step.
    <who>: "mock ready" when the what says mock (not "no mock") and the stage is none, brief, register or
    mock, at now + ceil(left x 3 / 7) (left = p50, or m); else "review" at the p50 time (or <t>).
    --wait <m>: the minutes are added to every clock time but the mock one; " and <m> min of waiting" is said
    right after the work part, as today ("about 10 min of work left and 30 min of waiting, done around ...").
  With --step or --work-so-far: today's eta, unchanged (old callers).
heartbeat "<task>" <step 0-7> "<what runs now>" (four words, no work minutes): the work is computed:
    1. a todo line of <task> in the project's agent_todo.txt: the work as the board counts it;
    2. else the line "WORK START <task> | <YYYY-MM-DD HH:MM>" of this folder's agent_state.txt: the minutes
       from it to now;
    3. else refused: one line on stderr that says no start is known and shows the five-word form.
  The five-word form (typed minutes): when 1 or 2 gives a start, the computed minutes are written and one
  line on stderr says "heartbeat: work <c>m from the start, not the typed <t>m" when they differ by more
  than 5; with no start, the typed minutes as today.
  todo stage in a work tree writes "WORK START <name> | <now>" into that folder's agent_state.txt once:
  right before the STAGE line it adds, only when the file has no WORK START line for that name.
backtest (bin/agent_estimate.py): two lines right after "measure p85":
    measure live est <= 60m: n <n> error <m>m, last two <m>m
    measure live est > 60m: n <n> error <m>m, last two <m>m
  For each scored row with a stage log (its stages key): at each stage in the order listed, the forecast
  p50 asked with est = its est0 (else est), work = the minutes of the stages before it, stage = that stage
  (no i/m), p = the stage weights before that stage / the sum of the weights, built_work = its built,
  rows = the clean rows before it (history's shape, its lane rule); actual = its work - that work.
  error = the median of |p50 - actual| over those pairs, whole minutes (half up); "last two" = the same over
  the last two stages of each row. Grouped by the row's est. n 0: "error -, last two -".
"""

import importlib.util
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import BIN  # noqa: E402
import test_agent_board as tb  # noqa: E402
from test_agent_estimate import EstimateCase, day  # noqa: E402
from test_agent_estimate_inputs import row  # noqa: E402

NOW = tb.NOW            # "2026-11-02 15:00"


def load(name):
    spec = importlib.util.spec_from_file_location("%s_fc_t" % name, os.path.join(BIN, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hrow(est=60, label=60, tail=0, lane="full", built=None):
    return {"est": est, "label": label, "tail": tail, "lane": lane, "built": built, "stages": {}, "slices": []}


def task(est=60, work=0, stage=None, p=None, lane="full", built_work=None):
    return {"est": est, "work": work, "stage": stage, "p": p, "lane": lane, "built_work": built_work}


# ---------------------------------------------------------------- the function

class TestForecastFunction(unittest.TestCase):

    def setUp(self):
        self.f = load("agent_forecast")

    def test_too_little_history_is_none(self):
        self.assertIsNone(self.f.forecast(task(), [hrow()] * 9))
        self.assertIsNotNone(self.f.forecast(task(), [hrow()] * 10))
        self.assertEqual(self.f.FORECAST_MIN_ROWS, 10)

    def test_the_lane_pool(self):
        rows = [hrow(lane="fast", label=6, est=6)] * 10 + [hrow(label=120, est=60)] * 10
        self.assertEqual(self.f.forecast(task(est=10, lane="fast"), rows), (10, 10))
        self.assertEqual(self.f.forecast(task(est=10, lane="full"), rows), (20, 20))
        few = [hrow(lane="fast", label=6, est=6)] * 3 + [hrow(label=120, est=60)] * 10
        p50, _ = self.f.forecast(task(est=10, lane="fast"), few)     # 3 fast rows: every row counts
        self.assertGreater(p50, 10)

    def test_dispatch_adds_the_tail(self):
        rows = [hrow(tail=30)] * 10
        self.assertEqual(self.f.forecast(task(est=60), rows), (90, 90))

    def test_9_the_age_rule(self):
        # 18 tasks ran their est, 2 ran twice it; at 90 minutes of a 60 minute task only the 2 can be it
        rows = [hrow()] * 18 + [hrow(label=120)] * 2
        self.assertEqual(self.f.forecast(task(work=90, stage=("tests", None, None), p=0.06), rows), (30, 30))

    def test_9_earned_schedule_is_a_lower_bound(self):
        rows = [hrow()] * 20
        # at verify p 0.8 with 64 minutes done: the pace says 80 in all, more than the 60 history says
        self.assertEqual(self.f.forecast(task(work=64, stage=("verify", None, None), p=0.8), rows), (16, 16))
        # under ES_MIN it does not count
        self.assertEqual(self.f.forecast(task(work=10, stage=("tests", None, None), p=0.1), rows), (50, 50))

    def test_past_every_history_with_no_pace(self):
        rows = [hrow()] * 20
        self.assertEqual(self.f.forecast(task(work=80, stage=("tests", None, None), p=0.1), rows), (80, 80))

    def test_rows_with_no_tail_teach_the_work_only(self):
        rows = [hrow(tail=None)] * 10 + [hrow(tail=30)] * 2
        self.assertEqual(self.f.forecast(task(est=60), rows), (90, 90))
        self.assertEqual(self.f.forecast(task(est=60), [hrow(tail=None)] * 10), (60, 60))

    def test_report_has_only_the_tail(self):
        rows = [hrow(tail=20)] * 10
        self.assertEqual(self.f.forecast(task(work=70, stage=("report", None, None), p=0.83), rows), (20, 20))

    def test_the_tail_age_rule(self):
        rows = [hrow(tail=10)] * 10 + [hrow(tail=30)] * 10
        t = task(work=55, stage=("e2e", None, None), p=0.85, built_work=40)
        self.assertEqual(self.f.forecast(t, rows), (15, 15))

    def test_8_three_open_slices_end_after_one(self):
        ratios = [0.5, 0.8, 1.0, 1.25, 2.0]
        one = self.f.slices_end([20], ratios)
        three = self.f.slices_end([20, 20, 20], ratios)
        self.assertEqual(one[0], 20)
        self.assertGreater(three[0], 20)
        self.assertGreaterEqual(three[1], three[0])

    def test_open_slices_push_the_build(self):
        rows = [hrow(label=30), hrow(label=60), hrow(label=90), hrow(label=120)] * 5
        few = self.f.forecast(task(est=100, work=30, stage=("workers", 3, 4), p=0.3), rows)
        many = self.f.forecast(task(est=100, work=30, stage=("workers", 0, 4), p=0.3), rows)
        self.assertGreaterEqual(many[0], few[0])

    def test_the_same_inputs_give_the_same_numbers(self):
        rows = [hrow(label=l, tail=t) for l, t in ((30, 5), (60, 40), (90, 10), (45, 0))] * 5
        a = self.f.forecast(task(work=20, stage=("tests", None, None), p=0.1), rows)
        b = self.f.forecast(task(work=20, stage=("tests", None, None), p=0.1), rows)
        self.assertEqual(a, b)
        self.assertLess(a[0], a[1])


class TestHistory(tb.BoardCase):

    def test_clean_rows_only_and_their_parts(self):
        lines = [row(day(1), "new", "w", lane="full", est=60, est0=50, work=80, built=60, wait=0, clock=90,
                     stages="brief:5,tests:55,report:20", slices="10,20"),
                 row(day(2), "old", "w", lane="fast", est=10, work=8, wait=2, clock=15),
                 row(day(3), "dirty", "w", lane="full", est=10, work=30, wait=0, clock=9),
                 row(day(4), "nowait", "w", lane="full", est=10, work=5, clock=9)]      # fix order 1: kept
        with open(self.repo.path("agent_completed.txt"), "w") as fh:
            fh.write("\n".join(lines) + "\n")
        rows = load("agent_forecast").history(self.repo.dir)
        self.assertEqual(len(rows), 3)
        new, old, nowait = rows
        self.assertEqual((nowait["est"], nowait["label"], nowait["tail"]), (10, 5, None))
        self.assertEqual((new["est"], new["label"], new["tail"], new["lane"], new["built"]), (50, 60, 20, "full", 60))
        self.assertEqual(new["stages"], {"brief": 5, "tests": 55, "report": 20})
        self.assertEqual(new["slices"], [10, 20])
        self.assertEqual((old["est"], old["label"], old["tail"], old["lane"], old["built"]), (10, 8, 5, "fast", None))


# ---------------------------------------------------------------- the board and eta

CELL2 = re.compile(r"^(\d\d:\d\d) / (\d\d:\d\d)$")
ETA_FC = re.compile(r"^about (\d+) min of work left \(85%: (\d+) min\), done around (\d\d:\d\d) \(85%: (\d\d:\d\d)\); "
                    r"owner needed next: (mock ready|review) about (\d\d:\d\d)$")


def history_lines(n=12):
    """Old rows, full lane: est 60 = work 60, tails 20 and 40 in turn."""
    return [row(day(i), "h-%02d" % i, "plain work", lane="full", type="script", mock="no", est=60, work=60,
                wait=0, clock=80 if i % 2 == 0 else 100) for i in range(n)]


class BoardForecastCase(tb.BoardCase):
    lang = "en"

    def history(self, lines):
        with open(self.repo.path("agent_completed.txt"), "w") as fh:
            fh.write("\n".join(lines) + "\n")

    def put(self, *lines):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def verify_line(self):
        self.put("x | big | the login form | est 60m | opened 2026-11-02 14:00 | by main"
                 " | started 2026-11-02 14:10 | stage verify since 2026-11-02 14:50")


class TestBoardDoneBy(BoardForecastCase):

    def test_6_6_two_clock_times_later_than_the_old_one(self):
        self.history(history_lines())
        self.verify_line()
        r = self.row(self.rows(now=NOW), task="x")
        m = CELL2.match(r["Done by"])
        self.assertIsNotNone(m, r)
        # today's cell: now + est - work = 15:00 + 60 - 50 = 15:10
        self.assertGreater(m.group(1), "15:10")
        self.assertGreater(m.group(2), "15:10")
        self.assertLessEqual(m.group(1), m.group(2))

    def test_a_small_task_uses_the_fast_lane(self):
        fast = [row(day(20 + i), "f-%02d" % i, "fix", lane="fast", type="page", mock="no", est=10, work=10,
                    wait=0, clock=12) for i in range(12)]
        self.history(history_lines() + fast)
        self.put("s | small | fix the label | est 10m | opened 2026-11-02 14:55 | by main | started 2026-11-02 14:55")
        # fast history: 10 in all, 5 done, a tail of 2 -> 15:07 (the full lane would add 20 or 40)
        self.assertEqual(self.row(self.rows(now=NOW), task="s")["Done by"], "15:07 / 15:07")

    def test_no_history_keeps_todays_cell(self):
        self.verify_line()
        r = self.row(self.rows(now=NOW), task="x")
        self.assertEqual(r["Done by"], "15:10")

    def test_too_little_history_keeps_todays_cell(self):
        self.history(history_lines(9))
        self.verify_line()
        self.assertEqual(self.row(self.rows(now=NOW), task="x")["Done by"], "15:10")

    def test_dirty_rows_do_not_count(self):
        lines = history_lines(9) + [row(day(20), "d", "w", lane="full", est=60, work=90, wait=0, clock=9)]
        self.history(lines)
        self.verify_line()
        self.assertEqual(self.row(self.rows(now=NOW), task="x")["Done by"], "15:10")


class TestEtaIsTheBoard(BoardForecastCase):

    def test_6_7_the_same_p50(self):
        self.history(history_lines())
        self.verify_line()
        cell = CELL2.match(self.row(self.rows(now=NOW), task="x")["Done by"])
        out = self.af("eta", "x", now=NOW).stdout.strip()
        m = ETA_FC.match(out)
        self.assertIsNotNone(m, out)
        self.assertEqual((m.group(3), m.group(4)), cell.groups())
        self.assertEqual(m.group(5), "review")
        self.assertEqual(m.group(6), m.group(3))

    def test_no_history_reads_the_line_like_the_board(self):
        self.verify_line()
        out = self.af("eta", "x", now=NOW).stdout.strip()
        self.assertEqual(out, "about 10 min of work left, done around 15:10; owner needed next: review about 15:10")

    def test_a_wait_still_ahead_moves_the_clock(self):
        self.verify_line()
        out = self.af("eta", "x", "--wait", "30", now=NOW).stdout.strip()
        self.assertEqual(out, "about 10 min of work left and 30 min of waiting, done around 15:40; "
                              "owner needed next: review about 15:40")

    def test_the_old_options_keep_the_old_answer(self):
        self.verify_line()
        out = self.af("eta", "x", "--step", "5", now=NOW).stdout.strip()
        # today's rule: est x (7 - 5) / 7 = 17.1 -> 18 left
        self.assertTrue(out.startswith("about 18 min of work left, done around 15:18"), out)

    def test_over_with_no_pace_is_refused(self):
        self.put("x | big | the login form | est 30m | opened 2026-11-02 14:00 | by main | started 2026-11-02 14:00")
        r = self.af("eta", "x", now=NOW, ok=False)
        self.assertEqual(r.returncode, 1, (r.stdout, r.stderr))
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertIn("--step", r.stderr)

    def test_a_mock_task_before_its_mock(self):
        self.put("x | big | a new page, mock first | est 70m | opened 2026-11-02 14:50 | by main"
                 " | started 2026-11-02 14:50 | stage brief since 2026-11-02 14:50")
        out = self.af("eta", "x", now=NOW).stdout.strip()
        # work 10, left 60: mock ready at now + ceil(60 x 3 / 7) = 26 minutes
        self.assertEqual(out, "about 60 min of work left, done around 16:00; owner needed next: mock ready about 15:26")


# ---------------------------------------------------------------- heartbeat

HB = re.compile(r"^HEARTBEAT (\S+): step (\d) of 7, work (\d+)m, (.*) \| (\d{4}-\d\d-\d\d \d\d:\d\d)$")


class TestHeartbeatWork(BoardForecastCase):

    def last_beat(self, folder=None):
        beats = [l for l in self.state_text(folder).splitlines() if l.startswith("HEARTBEAT ")]
        self.assertTrue(beats, self.state_text(folder))
        return HB.match(beats[-1])

    def test_11_from_the_todo_line(self):
        self.verify_line()
        self.af("heartbeat", "x", "5", "verify runs", now=NOW)
        m = self.last_beat()
        self.assertEqual(m.group(1, 2, 3, 4), ("x", "5", "50", "verify runs"))

    def test_11_from_the_work_start_line_in_a_worktree(self):
        alpha = self.task_worktree("alpha")
        self.af("todo", "stage", "alpha", "brief", now="2026-11-02 14:00", cwd=alpha)
        text = self.state_text(alpha)
        self.assertIn("WORK START alpha | 2026-11-02 14:00\nSTAGE alpha: brief | since 2026-11-02 14:00\n", text)
        self.af("todo", "stage", "alpha", "tests", now="2026-11-02 14:20", cwd=alpha)
        self.assertEqual(self.state_text(alpha).count("WORK START alpha"), 1)
        self.af("heartbeat", "alpha", "3", "writing tests", now="2026-11-02 14:47", cwd=alpha)
        self.assertEqual(self.last_beat(alpha).group(3), "47")

    def test_the_typed_number_loses_to_a_known_start(self):
        self.verify_line()
        r = self.af("heartbeat", "x", "5", "24", "verify runs", now=NOW)
        self.assertEqual(self.last_beat().group(3), "50")
        self.assertIn("heartbeat: work 50m from the start, not the typed 24m", r.stderr)

    def test_a_close_typed_number_says_nothing(self):
        self.verify_line()
        r = self.af("heartbeat", "x", "5", "47", "verify runs", now=NOW)
        self.assertEqual(self.last_beat().group(3), "50")
        self.assertNotIn("typed", r.stderr)

    def test_no_start_known_typed_form_works_as_today(self):
        self.af("heartbeat", "nobody", "2", "35", "tests run", now=NOW)
        self.assertEqual(self.last_beat().group(3), "35")

    def test_no_start_known_four_word_form_is_refused(self):
        r = self.af("heartbeat", "nobody", "2", "tests run", now=NOW, ok=False)
        self.assertEqual(r.returncode, 1, (r.stdout, r.stderr))
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertNotIn("HEARTBEAT nobody", self.state_text())


# ---------------------------------------------------------------- the live measure

LIVE_S = re.compile(r"^measure live est <= 60m: n (\d+) error (\d+m|-), last two (\d+m|-)$")
LIVE_B = re.compile(r"^measure live est > 60m: n (\d+) error (\d+m|-), last two (\d+m|-)$")


def staged(n):
    """New rows: est 60, built 60, work 70 (a 10 minute tail), six stages each."""
    return [row(day(i), "s-%02d" % i, "one shell script with tests", type="script", lane="full", mock="no",
                est=60, est0=60, work=70, built=60, wait=0, clock=75,
                stages="brief:5,tests:15,workers:25,verify:15,report:5,e2e:5") for i in range(n)]


class TestLiveMeasure(EstimateCase):

    def live(self, out):
        lines = self.lines(out)
        s = [LIVE_S.match(l) for l in lines]
        b = [LIVE_B.match(l) for l in lines]
        s, b = [x for x in s if x], [x for x in b if x]
        self.assertEqual((len(s), len(b)), (1, 1), out)
        at = [i for i, l in enumerate(lines) if l.startswith("measure p85")][0]
        self.assertTrue(lines[at + 1].startswith("measure live est <= 60m"), out)
        self.assertTrue(lines[at + 2].startswith("measure live est > 60m"), out)
        return s[0], b[0]

    def test_rows_with_a_stage_log(self):
        # every stage forecast is exact but at workers (the pace 20 / 0.26 says 77 in all: 17 off) and at
        # verify (45 / 0.66 says 68.2, 34 left with the tail, rounded up: 9 off): the median is 0 (task manager,
        # worked by hand)
        self.completed(staged(20))
        s, b = self.live(self.assertOk(self.af("backtest")))
        self.assertEqual(s.groups(), ("60", "0m", "0m"))
        self.assertEqual(b.groups(), ("0", "-", "-"))

    def test_old_rows_have_none(self):
        rows = [row(day(i), "o-%02d" % i, "one shell script with tests", type="script", lane="full", mock="no",
                    est=60, work=60, wait=0, clock=70) for i in range(20)]
        self.completed(rows)
        s, b = self.live(self.assertOk(self.af("backtest")))
        self.assertEqual((s.groups(), b.groups()), (("0", "-", "-"), ("0", "-", "-")))


if __name__ == "__main__":
    unittest.main()
