"""Failing tests of estimate-improve, part A: the inputs (requirements/estimate-improve.md, section 5
items 1-5) and the fixed measure of section 4 in `backtest`. Written by the task manager first.

CONTRACT

A1  todo done: the work label is measured, never typed.
    W (the waits) = the line's closed waits (" | waited <m>m", 0 when none) + an open wait
      (" | waiting <kind> since <t>") up to now; --wait <m> given: W = the larger of the two.
      The data block's wait = W; no time on the line at all: the typed --wait, else "-".
    before = <n> of " | started <t> after <n>m waited" (0 when there is no " after ").
    work = minutes(started, now) - max(0, W - before) when the line has a started field;
           else clock - W when it has an opened time; never below 0;
           else (no time on the line) the typed --work, else "-".
    typed = the --work given, else "-". The typed number is kept, never the label.
    A typed --work over the clock: one warning line on stderr
      "todo done: warning: --work <t>m is more than the clock <c>m; work <w>m is stored, the typed number
       is kept as typed=<t>"  (one line), exit 0, the line moves as usual.
A2  The stage log.
    todo stage with a NEW value (a new stage, or a new i/m) adds the entry "<value> <m>" to the field
    " | stage log <entry>, <entry>, ..." (", " between entries); m = the work minutes at now, counted as
    in A1 (the first stage: 0). The field sits right before the started field, else right before the
    stage field. The same value again writes nothing.
    todo done writes into the data block:
      stages=<stage>:<m>,...  the work minutes of each stage: from its entry to the next entry of another
                              stage (the last one: to the done work), in the order first met; a stage met
                              twice is summed
      slices=<m>,...          for each "workers <i>/<n>" entry whose i is new and >= 1, in order: its
                              minutes minus the minutes of the first workers entry
      built=<m>               the minutes of the first report entry, else of the first e2e entry, else "-"
      no stage log: stages=- slices=- built=-
A3  todo est keeps the first estimate.
    todo est <name> +<m>: est = old + m; " | est0 <old>m" right after est when the line has none;
      " | added <a>m" right after est0 = the sum of every +<m> so far.
    todo est <name> <m>: est = m; " | est0 <old>m" when the line has none; added stays.
    No old est: no est0. The printed line stays "todo est: <name> <old>m -> <new>m".
    todo done: est0 = the est0 field, else est; added = the added field, else "-".
A4  todo add: an est equal to --guess is refused unless --why "<reason>" is given; --why writes the field
    " | why <reason>" right after guess. Refused: one line on stderr that names --why, exit 1, nothing
    written. --why with an empty value, " | " or a line break: refused.
A5  Clean rows (bin/agent_estimate.py).
    A row is clean when clock and wait are numbers, work <= clock and clock <= 1440 (one day).
    The label a learner learns = built when the row has it, else work.
    Only clean rows are neighbours (like lines), pick the setting, make the ranges, the weight and the
    bias. The backtest scores only clean rows, each from the clean rows before it (10 or more).
The data block, in this order (todo done, backfill):
    repo type lane mock est work wait clock bounces workers files lines tests adds guess level
    typed est0 added built stages slices
`data --what`: the columns est0 typed built stages slices right after guess, before what.
`data` without --what is unchanged.

M   The measure of section 4, in `backtest`: one block of lines right before the "winner:" line, opened by:
      measure: <n> clean rows scored, by <winner>
      measure work: n <n> bias <+x.xx> spread <x.xx>
      measure work est < <big>m: n <n> bias <+x.xx> spread <x.xx>
      measure work est >= <big>m: n <n> bias <+x.xx> spread <x.xx>
      measure end: n <n> bias <+x.xx> spread <x.xx>
      measure p85: n <n> holds <p>%
    q = ln(label / estimate) per scored row, the estimate of the winner's method; bias = the median of q,
    spread = the population standard deviation of q; n 0: "bias - spread -". The groups go by the
    ESTIMATE (big = estimate_big_min, 120).
    end: actual = clock - wait; its estimate = the winner's estimate + the median tail of the clean rows
    before it of the same lane (tail = clock - wait - label, at least 0; fewer than 5 such rows: tail 0).
    p85: the statement = estimate x exp(the 85th percentile, linear, of q of the scored rows before it, same
    method); a row with fewer than 10 scored rows before it makes no statement and is not counted;
    holds = label <= statement; n 0: "holds -".
"""

import math
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_agent_board as tb  # noqa: E402  (helpers only)
from test_agent_estimate import EstimateCase, steady, day, version  # noqa: E402

KEYS = ["repo", "type", "lane", "mock", "est", "work", "wait", "clock", "bounces", "workers", "files",
        "lines", "tests", "adds", "guess", "level", "typed", "est0", "added", "built", "stages", "slices",
        "by"]   # the scope add of 2026-11-26: the name of the clone that ran todo done (tests/test_agent_owner_name.py)
NOW = "2026-10-01 20:30"


def block(**known):
    return "data " + " ".join("%s=%s" % (k, known.get(k, "-")) for k in KEYS)


def row(date, name, what, **known):
    known.setdefault("repo", "project")
    return "%s | %s | %s | %s" % (date, name, what, block(**known))


def data_of(line):
    """{key: value} of a completed line's data block."""
    return dict(w.split("=", 1) for w in line.split(" | data ", 1)[1].split())


class InputCase(tb.BoardCase):
    lang = "en"

    def done_line(self, name):
        hits = [l for l in (self.repo.read("agent_completed.txt") or "").splitlines() if " | %s | " % name in l]
        self.assertEqual(len(hits), 1, self.repo.read("agent_completed.txt"))
        return hits[0]

    def put(self, *lines):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))


# ---------------------------------------------------------------- A1 the work label

class TestDoneWorkIsMeasured(InputCase):

    def test_6_1_typed_work_over_the_clock_stores_the_clock_and_warns(self):
        self.put("t | small | fix the label | est 10m | opened 2026-10-01 20:21 | by main")
        r = self.af("todo", "done", "t", "--work", "20", "--lane", "fast", "--type", "page", "--mock", "no",
                    now=NOW)
        d = data_of(self.done_line("t"))
        self.assertEqual((d["work"], d["typed"], d["clock"], d["wait"]), ("9", "20", "9", "0"))
        warn = [l for l in r.stderr.splitlines() if l.startswith("todo done: warning: --work")]
        self.assertEqual(warn, ["todo done: warning: --work 20m is more than the clock 9m; work 9m is stored, "
                                "the typed number is kept as typed=20"], r.stderr)

    def test_from_started_minus_the_waits_after_it(self):
        self.put("t | big | w | est 60m | opened 2026-11-02 10:00 | by main | waited 30m"
                 " | started 2026-11-02 10:10 after 10m waited | stage verify since 2026-11-02 11:00")
        self.af("todo", "done", "t", "--work", "40", now="2026-11-02 12:00")
        d = data_of(self.done_line("t"))
        self.assertEqual((d["work"], d["typed"], d["wait"], d["clock"]), ("90", "40", "30", "120"))

    def test_an_open_wait_counts_up_to_now(self):
        self.put("t | big | w | est 60m | opened 2026-11-02 10:00 | by main | started 2026-11-02 10:00"
                 " | stage verify since 2026-11-02 11:00 | waiting review since 2026-11-02 11:40")
        self.af("todo", "done", "t", now="2026-11-02 12:00")
        d = data_of(self.done_line("t"))
        self.assertEqual((d["work"], d["typed"], d["wait"]), ("100", "-", "20"))

    def test_a_bigger_typed_wait_wins(self):
        self.put("t | big | w | est 60m | opened 2026-11-02 10:00 | by main | waited 10m"
                 " | started 2026-11-02 10:00 | stage verify since 2026-11-02 11:00")
        self.af("todo", "done", "t", "--wait", "30", now="2026-11-02 12:00")
        d = data_of(self.done_line("t"))
        self.assertEqual((d["work"], d["wait"]), ("90", "30"))

    def test_no_started_field_counts_from_opened(self):
        self.put("t | small | w | est 30m | opened 2026-11-02 10:00 | by main | waited 15m")
        r = self.af("todo", "done", "t", "--work", "50", now="2026-11-02 11:00")
        d = data_of(self.done_line("t"))
        self.assertEqual((d["work"], d["typed"], d["wait"], d["clock"]), ("45", "50", "15", "60"))
        self.assertNotIn("is more than the clock", r.stderr)

    def test_never_below_zero(self):
        self.put("t | small | w | est 30m | opened 2026-11-02 10:00 | by main | waited 90m")
        self.af("todo", "done", "t", now="2026-11-02 11:00")
        self.assertEqual(data_of(self.done_line("t"))["work"], "0")

    def test_no_time_on_the_line_keeps_the_typed_work(self):
        self.put("t2 | small | a thing | by main")
        self.af("todo", "done", "t2", "--work", "5", now=NOW)
        d = data_of(self.done_line("t2"))
        self.assertEqual((d["work"], d["typed"]), ("5", "5"))

    def test_the_whole_block_in_order(self):
        self.put("t | small | fix the label | est 10m | opened 2026-10-01 20:00 | by main")
        self.af("todo", "done", "t", "--work", "12", "--lane", "fast", "--type", "page", "--mock", "no", now=NOW)
        self.assertEqual(self.done_line("t"), "2026-10-01 | t | fix the label | " + block(
            repo="project", type="page", lane="fast", mock="no", est=10, work=30, wait=0, clock=30,
            typed=12, est0=10, by="t"))


# ---------------------------------------------------------------- A2 the stage log

class TestStageLog(InputCase):

    def stage(self, name, *args, now):
        self.af("todo", "stage", name, *args, now=now)

    def test_the_field_and_its_place(self):
        self.add("x", "the task", 60, opened="2026-11-02 10:00", started=False)
        self.stage("x", "brief", now="2026-11-02 10:00")
        self.assertIn(" | stage log brief 0 | started 2026-11-02 10:00 | stage brief since 2026-11-02 10:00",
                      self.todo_line("x"))
        self.stage("x", "tests", now="2026-11-02 10:10")
        self.stage("x", "tests", now="2026-11-02 10:12")      # the same value: nothing written
        self.stage("x", "workers", "0/2", now="2026-11-02 10:20")
        self.assertIn(" | stage log brief 0, tests 10, workers 0/2 20 | started 2026-11-02 10:00 | stage workers 0/2",
                      self.todo_line("x"))

    def test_an_old_line_with_a_started_field_gets_it_before_started(self):
        self.put("x | big | w | est 60m | opened 2026-11-02 09:00 | by main | started 2026-11-02 09:30"
                 " | stage tests since 2026-11-02 09:30")
        self.stage("x", "verify", now="2026-11-02 10:00")
        self.assertIn(" | by main | stage log verify 30 | started 2026-11-02 09:30 | stage verify since",
                      self.todo_line("x"))

    def test_waits_are_not_work_minutes(self):
        self.add("x", "the task", 60, opened="2026-11-02 10:00", started=False)
        self.stage("x", "brief", now="2026-11-02 10:00")
        self.wait("x", "on", "question", now="2026-11-02 10:05")
        self.wait("x", "off", now="2026-11-02 10:25")
        self.stage("x", "tests", now="2026-11-02 10:30")
        self.assertIn(" | stage log brief 0, tests 10 | ", self.todo_line("x"))

    def test_done_writes_stages_slices_and_built(self):
        self.add("x", "the task", 60, opened="2026-11-02 10:00", started=False)
        for value, at in ((("brief",), "10:00"), (("tests",), "10:10"), (("workers", "0/2"), "10:20"),
                          (("workers", "1/2"), "10:35"), (("workers", "2/2"), "10:50"), (("verify",), "10:55")):
            self.stage("x", *value, now="2026-11-02 " + at)
        self.wait("x", "on", "review", now="2026-11-02 11:00")
        self.wait("x", "off", now="2026-11-02 11:20")
        for value, at in ((("report",), "11:25"), (("e2e",), "11:30"), (("merge",), "11:40")):
            self.stage("x", *value, now="2026-11-02 " + at)
        self.af("todo", "done", "x", "--lane", "full", "--type", "script", "--mock", "no", now="2026-11-02 11:45")
        d = data_of(self.done_line("x"))
        self.assertEqual(d["work"], "85")
        self.assertEqual(d["stages"], "brief:10,tests:10,workers:35,verify:10,report:5,e2e:10,merge:5")
        self.assertEqual(d["slices"], "15,30")
        self.assertEqual(d["built"], "65")

    def test_a_stage_met_twice_is_summed(self):
        self.add("x", "the task", 60, opened="2026-11-02 10:00", started=False)
        for s, at in (("brief", "10:00"), ("tests", "10:10"), ("verify", "10:30"), ("tests", "10:40"),
                      ("verify", "10:50")):
            self.stage("x", s, now="2026-11-02 " + at)
        self.af("todo", "done", "x", now="2026-11-02 11:00")
        d = data_of(self.done_line("x"))
        self.assertEqual((d["stages"], d["slices"], d["built"], d["work"]),
                         ("brief:10,tests:30,verify:20", "-", "-", "60"))

    def test_e2e_is_built_when_there_was_no_report(self):
        self.add("x", "the task", 60, opened="2026-11-02 10:00", started=False)
        for s, at in (("brief", "10:00"), ("verify", "10:20"), ("e2e", "10:40")):
            self.stage("x", s, now="2026-11-02 " + at)
        self.af("todo", "done", "x", now="2026-11-02 10:50")
        d = data_of(self.done_line("x"))
        self.assertEqual((d["built"], d["stages"]), ("40", "brief:20,verify:20,e2e:10"))

    def test_no_stage_log_gives_dashes(self):
        self.put("t | small | w | est 30m | opened 2026-11-02 10:00 | by main")
        self.af("todo", "done", "t", now="2026-11-02 10:20")
        d = data_of(self.done_line("t"))
        self.assertEqual((d["stages"], d["slices"], d["built"]), ("-", "-", "-"))


# ---------------------------------------------------------------- A3 est0 and added

class TestEstKeepsTheFirst(InputCase):

    def test_6_3_plus_minutes(self):
        self.put("x | big | w | est 80m | opened 2026-11-02 10:00 | by main")
        out = self.af("todo", "est", "x", "+40").stdout
        self.assertEqual(out.strip(), "todo est: x 80m -> 120m")
        self.assertIn(" | est 120m | est0 80m | added 40m | opened ", self.todo_line("x"))
        self.af("todo", "est", "x", "+10")
        self.assertIn(" | est 130m | est0 80m | added 50m | opened ", self.todo_line("x"))
        self.af("todo", "est", "x", "100")
        self.assertIn(" | est 100m | est0 80m | added 50m | opened ", self.todo_line("x"))
        self.af("todo", "done", "x", now="2026-11-02 11:00")
        d = data_of(self.done_line("x"))
        self.assertEqual((d["est"], d["est0"], d["added"]), ("100", "80", "50"))

    def test_a_plain_change_keeps_the_first_once(self):
        self.put("x | big | w | est 80m | guess 90m | opened 2026-11-02 10:00 | by main")
        self.af("todo", "est", "x", "60")
        self.assertIn(" | est 60m | est0 80m | guess 90m | ", self.todo_line("x"))
        self.af("todo", "est", "x", "70")
        line = self.todo_line("x")
        self.assertIn(" | est 70m | est0 80m | guess 90m | ", line)
        self.assertNotIn("added", line)

    def test_done_without_changes(self):
        self.put("x | big | w | est 80m | opened 2026-11-02 10:00 | by main")
        self.af("todo", "done", "x", now="2026-11-02 11:00")
        d = data_of(self.done_line("x"))
        self.assertEqual((d["est"], d["est0"], d["added"]), ("80", "80", "-"))


# ---------------------------------------------------------------- A4 est equal to the guess

class TestAddGuessRule(InputCase):

    def test_6_2_est_equal_to_the_guess_is_refused(self):
        self.put("keep | big | other | est 10m | opened 2026-11-02 10:00 | by main")
        before = self.repo.read("agent_todo.txt")
        r = self.af("todo", "add", "x", "big", "the thing", "120", "--guess", "120", ok=False)
        self.assertEqual(r.returncode, 1, (r.stdout, r.stderr))
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertIn("--why", r.stderr)
        self.assertEqual(self.repo.read("agent_todo.txt"), before)

    def test_why_lets_it_through_and_is_kept(self):
        self.af("todo", "add", "x", "big", "the thing", "120", "--guess", "120", "--why", "same as a twin task")
        self.assertIn(" | est 120m | guess 120m | why same as a twin task | opened ", self.todo_line("x"))

    def test_the_estimate_number_needs_no_why(self):
        self.af("todo", "add", "x", "big", "the thing", "48", "--guess", "120")
        line = self.todo_line("x")
        self.assertIn(" | est 48m | guess 120m | opened ", line)
        self.assertNotIn(" | why ", line)

    def test_a_bad_why_is_refused(self):
        for why in ("", "a | b", "a\nb"):
            with self.subTest(why=why):
                r = self.af("todo", "add", "x", "big", "w", "120", "--guess", "120", "--why", why, ok=False)
                self.assertEqual(r.returncode, 1, (r.stdout, r.stderr))
                self.assertIsNone(self.todo_line("x"))


# ---------------------------------------------------------------- A5 clean rows

def clean_rows(n=12):
    return steady(n)


class TestCleanRows(EstimateCase):
    """The dirty rows have names with no word in them (d-40): their text is the target's own, so they
    would be the nearest tasks if they were learned."""

    def setUp(self):
        super().setUp()
        self.model(versions=[version()])          # an estimator version: k 3, text 0, type 0.5

    def dirty(self, name, i, **facts):
        base = dict(type="page", lane="fast", mock="no", est=10, work=500, wait=0, clock=600)
        base.update(facts)
        return row(day(i), name, "fix a small thing on the page", **base)

    def test_6_1_a_row_with_work_over_clock_is_never_learned(self):
        self.completed(clean_rows() + [self.dirty("d-40", 40, clock=9)])
        m, likes = self.estimate("fast", "no", "page", "fix a small thing on the page")
        self.assertNotIn("d-40", [l.group(1) for l in likes])
        self.assertEqual(m.group(1), "3")

    def test_a_row_over_one_day_or_with_no_wait_is_never_learned(self):
        self.completed(clean_rows() + [self.dirty("d-40", 40, clock=1441),
                                       self.dirty("d-41", 41, wait="-")])
        m, likes = self.estimate("fast", "no", "page", "fix a small thing on the page")
        names = [l.group(1) for l in likes]
        self.assertNotIn("d-40", names)
        self.assertNotIn("d-41", names)
        self.assertEqual(m.group(1), "3")

    def test_one_day_is_still_clean(self):
        self.completed(clean_rows() + [self.dirty("d-40", 40, work=500, clock=1440)])
        m, likes = self.estimate("fast", "no", "page", "fix a small thing on the page")
        self.assertIn("d-40", [l.group(1) for l in likes])
        self.assertNotEqual(m.group(1), "3")

    def test_the_backtest_scores_only_clean_rows(self):
        rows = steady(24)
        rows.insert(15, self.dirty("dirty-row", 15, clock=9))
        self.completed(rows)
        out = self.assertOk(self.af("backtest", "--tasks"))
        names = [r.split()[1] for r in self.task_rows(out)]
        self.assertNotIn("dirty-row", names)
        self.assertEqual(len(names), 14, out)      # 24 clean rows, the first 10 only teach
        self.assertIn("backtest: 25 tasks, 14 tested", out)

    def test_the_label_is_built_when_known(self):
        rows = [row(day(i), "b-%02d" % i, "one shell script with tests", type="script", lane="full", mock="no",
                    est=50, work=80, built=30, wait=0, clock=100) for i in range(12)]
        self.completed(rows)
        m, likes = self.estimate("full", "no", "script", "one shell script with tests")
        self.assertEqual(m.group(1), "30")


class TestDataWhatColumns(EstimateCase):

    def test_the_new_columns_come_before_what(self):
        self.completed([row(day(1), "a", "the what text", type="script", lane="full", mock="no", est=50, work=40,
                            wait=0, clock=60, guess=45, typed=55, est0=40, built=30,
                            stages="brief:5,tests:35", slices="10,20")])
        lines = [l.split() for l in self.lines(self.assertOk(self.af("data", "--what"))) if l.strip()]
        self.assertEqual(lines[0][-7:], ["guess", "est0", "typed", "built", "stages", "slices", "what"])
        self.assertEqual(lines[1][-9:], ["45", "40", "55", "30", "brief:5,tests:35", "10,20", "the", "what", "text"])

    def test_plain_data_is_unchanged(self):
        self.completed([row(day(1), "a", "the what text", type="script", lane="full", mock="no", est=50, work=40,
                            wait=0, clock=60, guess=45, est0=40)])
        lines = [l.split() for l in self.lines(self.assertOk(self.af("data"))) if l.strip()]
        self.assertEqual(lines[0][-2:], ["adds", "guess"])
        self.assertEqual(lines[1][-1], "45")


# ---------------------------------------------------------------- M the measure in backtest

NUM = r"[+-]\d+\.\d\d"
M_HEAD = re.compile(r"^measure: (\d+) clean rows scored, by (\S+)$")
M_WORK = re.compile(r"^measure work: n (\d+) bias (%s|-) spread (\d+\.\d\d|-)$" % NUM)
M_SMALL = re.compile(r"^measure work est < 120m: n (\d+) bias (%s|-) spread (\d+\.\d\d|-)$" % NUM)
M_BIG = re.compile(r"^measure work est >= 120m: n (\d+) bias (%s|-) spread (\d+\.\d\d|-)$" % NUM)
M_END = re.compile(r"^measure end: n (\d+) bias (%s|-) spread (\d+\.\d\d|-)$" % NUM)
M_P85 = re.compile(r"^measure p85: n (\d+) holds (\d+%|-)$")


def tailed(n, tail):
    """steady() rows whose clock is work + tail (wait 0)."""
    out = []
    for r in steady(n):
        d = data_of(r)
        out.append(r.replace(" clock=%s " % d["clock"], " clock=%d " % (int(d["work"]) + tail)))
    return out


class TestMeasureLines(EstimateCase):

    def measures(self, out):
        lines = self.lines(out)
        found = {}
        for key, rx in (("head", M_HEAD), ("work", M_WORK), ("small", M_SMALL), ("big", M_BIG),
                        ("end", M_END), ("p85", M_P85)):
            hits = [rx.match(l) for l in lines]
            hits = [h for h in hits if h]
            self.assertEqual(len(hits), 1, "one %s line in:\n%s" % (key, out))
            found[key] = hits[0]
        # the measure lines are one block that ends right before "winner:"; these six open it, in order
        # (part C adds its live lines after the p85 line)
        order = [i for i, l in enumerate(lines) if l.startswith("measure")]
        winner = [i for i, l in enumerate(lines) if l.startswith("winner: ")]
        self.assertEqual(order, list(range(order[0], winner[0])), out)
        self.assertEqual([lines[i].split(":")[0].split(" n ")[0] for i in order[:6]],
                         ["measure", "measure work", "measure work est < 120m", "measure work est >= 120m",
                          "measure end", "measure p85"], out)
        return found

    def test_a_steady_history(self):
        # numbers checked with a reference run of the same rules (task manager, 2026-11-26)
        self.completed(steady(40))
        m = self.measures(self.assertOk(self.af("backtest")))
        self.assertEqual(m["head"].groups(), ("30", "estimator"))
        self.assertEqual(m["work"].groups(), ("30", "+0.00", "0.18"))
        self.assertEqual(m["small"].groups(), ("24", "+0.00", "0.20"))
        self.assertEqual(m["big"].groups(), ("6", "+0.00", "0.00"))     # the mock kind: estimate 140 >= 120
        self.assertEqual(m["p85"].groups(), ("20", "100%"))
        self.assertEqual(m["end"].groups(), ("30", "+0.00", "0.18"))     # no tail: the end is the work

    def test_the_end_adds_the_tail(self):
        self.completed(tailed(40, 30))
        m = self.measures(self.assertOk(self.af("backtest")))
        self.assertEqual(m["work"].groups(), ("30", "+0.00", "0.18"))
        # without the tail every end would run 30m over its estimate: the bias would be above 0
        self.assertEqual(m["end"].groups(), ("30", "+0.00", "0.61"))

    def test_no_clean_row_scored(self):
        self.completed(steady(8))
        out = self.assertOk(self.af("backtest"))
        self.assertIn("needs at least 11", out)
        self.assertFalse([l for l in self.lines(out) if l.startswith("measure")], out)


if __name__ == "__main__":
    unittest.main()
