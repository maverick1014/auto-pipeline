"""Tests for the time estimator (task estimate-skill). Read requirements/estimate.md.

WHY (owner, 2026-09-30). With 30 finished tasks of time data, learn the
estimate from the data, backtest it against today's rubric, ship the better
one; every 10 new tasks learn again and keep the new version only if its
backtest error is lower. An estimate = agent WORK minutes only. No hand-made
formula: learn from the data.

CONTRACT (all through bin/agent-file.sh; the work is done by bin/agent_estimate.py,
python 3.9 standard library only)

    data --what
        The data table with one more last column, `what`: the text between
        the name and the data block. Without --what: the table as before.

    estimate --lane fast|full --mock yes|no --type <t> [--name <name>] "<what>"
        Read only. A fact known only after a task (--work --wait --clock --est
        --bounces --workers --files --lines --tests --adds) is refused: one
        line on stderr naming it, exit 1. A missing or bad --lane, --mock,
        --type, or no what: refused the same way.
        estimate: <m>m work, range <lo>-<hi>m (<estimator|rubric> v<n>, <N> past tasks)
        like <name>: <m>m work (<type>, <lane>, mock <yes|no>, <date>)     up to 3, most alike first

    backtest [--tasks]
        backtest: <N> tasks, <T> tested, each from the tasks before it
        method     tasks  error  within 30%  in range
        estimator  <T>    <e>m   <p>%        <p>%
        rubric     <T>    <e>m   <p>%        <p>%
        todo est   <T>    <e>m   <p>%        -
        winner: estimator|rubric
        (error = median absolute error, one decimal; columns split by spaces)
        --tasks: one row per tested task, before the table:
        task <name> work <w> estimator <e> (<lo>-<hi>) rubric <r>
        Fewer than 11 tasks: backtest: <N> tasks, needs at least 11

    retrain [--force]
        estimate retrain: not yet (<N> of 30 tasks)
        estimate retrain: not due (<N> tasks, next check on <YYYY-MM-DD>)
        (due once a week: 7+ days since checked_date AND 1+ new task; a file
         with no checked_date is due after 10 new tasks, once, and says
         "next check at <M>" until then)
        estimate retrain: v1 made from <N> tasks: estimator|rubric (...)
        estimate retrain: kept v<n> (on the <k> new tasks: ...)
        The first train and a check also print the backtest table before it.

    agent_estimate.txt (project root, JSON)
        {"current": 1, "checked_tasks": 30, "checked_date": "YYYY-MM-DD",
         "versions": [{"version": 1, "date": "YYYY-MM-DD", "tasks": 30,
                       "method": "estimator", "k": 3, "text": 1, "type": 0.5,
                       "backtest": {"tasks": 20,
                                    "estimator": {"error": 23.0, "within30": 40, "inrange": 60},
                                    "rubric": {"error": 26.5, "within30": 30, "inrange": 30}}}],
         "checks": [{"date": "YYYY-MM-DD", "tasks": 40, "new": 10, "current": 1,
                     "current_error": 36.5, "new_error": 0.0, "kept": 2}]}
        versions = the kept versions only. checks = every check after v1.

    todo done
        After its line is written: the retrain when due, one verdict line
        ("estimate retrain: ..."), never the table. Not due: no line. A
        failure never stops todo done.
"""

import datetime
import json
import os
import random
import re
import time
import unittest

from tests.scripthelp import ROOT, ScriptCase

NOW = "2026-10-05 16:00"
TODAY = NOW.split()[0]
KEYS = ["repo", "type", "lane", "mock", "est", "work", "wait", "clock",
        "bounces", "workers", "files", "lines", "tests", "adds"]
AFTER_FACTS = ["--work", "--wait", "--clock", "--est", "--bounces", "--workers",
               "--files", "--lines", "--tests", "--adds"]
REAL = os.path.join(ROOT, "tests", "estimate_real.txt")

FIRST_LINE = re.compile(
    r"^estimate: (\d+)m work, range (\d+)-(\d+)m \((estimator|rubric) v(\d+), (\d+) past tasks\)$")
LIKE_LINE = re.compile(
    r"^like (\S+): (\d+)m work \((\S+), (fast|full), mock (yes|no), (\d{4}-\d\d-\d\d)\)$")
TASK_ROW = re.compile(
    r"^task (\S+) work (\d+) estimator (\d+) \((\d+)-(\d+)\) rubric (\d+)$")


def row_re(label, has_range=True):
    rng = r"(\d+)%" if has_range else r"-"
    return re.compile(r"^%s\s+(\d+)\s+(\d+\.\d)m\s+(\d+)%%\s+%s\s*$" % (label, rng))


def block(**known):
    return "data " + " ".join("%s=%s" % (k, known.get(k, "-")) for k in KEYS)


def line(date, name, what, **known):
    known.setdefault("repo", "project")
    return "%s | %s | %s | %s" % (date, name, what, block(**known))


def day(i):
    return (datetime.date(2026, 8, 1) + datetime.timedelta(days=i)).isoformat()


# Four kinds of task that each always take the same time. The rubric is far
# off on every kind, so a method that learns from the data must beat it.
KINDS = [
    dict(kind="fast", type="page", lane="fast", mock="no", work=3, est=10,
         what="fix a small thing on the page"),
    dict(kind="mock", type="page", lane="full", mock="yes", work=140, est=90,
         what="new page feature with a clickable mock"),
    dict(kind="script", type="script", lane="full", mock="no", work=25, est=50,
         what="one shell script with tests"),
    dict(kind="other", type="server", lane="full", mock="no", work=60, est=100,
         what="server change across modules"),
]
# The same four kinds, each taking exactly the rubric's middle.
RUBRIC_WORK = {"fast": 10, "mock": 75, "script": 53, "other": 105}


def steady(n, start=0, works=None):
    """n tasks, the four kinds in turn, one per day."""
    rows = []
    for i in range(start, start + n):
        k = KINDS[i % 4]
        work = (works or {}).get(k["kind"], k["work"])
        rows.append(line(day(i), "%s-%02d" % (k["kind"], i), k["what"],
                         type=k["type"], lane=k["lane"], mock=k["mock"],
                         est=k["est"], work=work, wait=0, clock=work))
    return rows


def varied(n, seed=7):
    """n tasks with mixed facts, texts and works (same seed, same tasks)."""
    rnd = random.Random(seed)
    topics = ["city", "relay", "cloud", "rail", "panel", "hook", "script",
              "login", "chat", "layout", "monitor", "quiz"]
    rows = []
    for i in range(n):
        lane = "fast" if rnd.random() < 0.25 else "full"
        mock = "yes" if lane == "full" and rnd.random() < 0.4 else "no"
        kind = rnd.choice(["page", "script", "server", "cloud", "mixed"])
        words = " ".join(rnd.sample(topics, 3))
        work = rnd.randint(1, 15) if lane == "fast" else rnd.randint(20, 200)
        rows.append(line(day(i), "v%02d" % i, "%s change: %s" % (kind, words),
                         type=kind, lane=lane, mock=mock, est=rnd.choice([15, 60, 90, 150]),
                         work=work, wait=0, clock=work))
    return rows


def version(**over):
    v = {"version": 1, "date": "2026-09-01", "tasks": 30, "method": "estimator",
         "k": 3, "text": 0, "type": 0.5,
         "backtest": {"tasks": 20,
                      "estimator": {"error": 1.0, "within30": 90, "inrange": 90},
                      "rubric": {"error": 30.0, "within30": 10, "inrange": 10}}}
    v.update(over)
    return v


class EstimateCase(ScriptCase):

    def setUp(self):
        super().setUp()
        if not os.path.exists(os.path.join(ROOT, "bin", "agent_estimate.py")):
            self.fail("bin/agent_estimate.py does not exist yet. Write it.")

    def write(self, name, text):
        with open(self.repo.path(name), "w") as fh:
            fh.write(text)

    def completed(self, rows):
        self.write("agent_completed.txt", "".join(r + "\n" for r in rows))

    def model(self, current=1, checked=30, versions=None, checks=None, date=None):
        data = {"current": current, "checked_tasks": checked,
                "versions": versions or [version()], "checks": checks or []}
        if date:
            data["checked_date"] = date
        self.write("agent_estimate.txt", json.dumps(data, indent=1) + "\n")

    def model_text(self):
        return self.repo.read("agent_estimate.txt")

    def model_json(self):
        text = self.model_text()
        self.assertIsNotNone(text, "agent_estimate.txt was not written")
        return json.loads(text)

    def af(self, *args, **kwargs):
        env = {"AGENT_FAKE_NOW": kwargs.pop("now", NOW)}
        return self.repo.run("agent-file.sh", *args, env=env, **kwargs)

    def estimate(self, lane, mock, kind, what, *more):
        out = self.assertOk(self.af("estimate", "--lane", lane, "--mock", mock,
                                    "--type", kind, *more, what))
        rows = self.lines(out)
        m = FIRST_LINE.match(rows[0])
        self.assertIsNotNone(m, "first line: %r" % rows[0])
        likes = [LIKE_LINE.match(r) for r in rows[1:] if r.startswith("like ")]
        for r, l in zip([r for r in rows[1:] if r.startswith("like ")], likes):
            self.assertIsNotNone(l, "like line: %r" % r)
        return m, likes

    def table(self, out):
        rows = self.lines(out)
        found = {}
        for label, rng in (("estimator", True), ("rubric", True), ("todo est", False)):
            hits = [row_re(label, rng).match(r) for r in rows]
            hits = [h for h in hits if h]
            self.assertEqual(len(hits), 1, "one %s row in:\n%s" % (label, out))
            found[label] = hits[0]
        winner = [r for r in rows if r.startswith("winner: ")]
        self.assertEqual(len(winner), 1, out)
        found["winner"] = winner[0][len("winner: "):]
        return found

    def task_rows(self, out):
        return [r for r in self.lines(out) if r.startswith("task ")]

    def verdicts(self, out):
        return [r for r in self.lines(out) if r.startswith("estimate retrain: ")]


# ---------------------------------------------------------------- data --what

class TestDataWhat(EstimateCase):

    def setUp(self):
        super().setUp()
        self.completed([line("2026-10-01", "t1", "agent-city: one rail | two panels",
                             type="page", lane="full", mock="yes", est=90, work=80)])

    def test_the_table_gets_a_last_column_what(self):
        rows = self.lines(self.assertOk(self.af("data", "--what")))
        self.assertTrue(rows[0].split()[-1] == "what", rows[0])
        self.assertTrue(rows[1].endswith("agent-city: one rail | two panels"), rows[1])

    def test_without_the_option_the_table_stays_as_it_was(self):
        rows = self.lines(self.assertOk(self.af("data")))
        self.assertEqual(rows[0].split()[-1], "adds")
        self.assertNotIn("agent-city", rows[1])


# ---------------------------------------------------------------- estimate: inputs

class TestEstimateInputs(EstimateCase):

    def setUp(self):
        super().setUp()
        self.completed(steady(12))

    def assertRefused(self, result, word):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        err = [l for l in result.stderr.splitlines() if l.strip()]
        self.assertEqual(len(err), 1, result.stderr)
        self.assertIn(word, err[0])

    def test_a_fact_known_only_after_the_task_is_refused(self):
        for opt in AFTER_FACTS:
            with self.subTest(opt=opt):
                r = self.af("estimate", "--lane", "full", "--mock", "no",
                            "--type", "script", opt, "2", "a script")
                self.assertRefused(r, opt)

    def test_lane_mock_type_and_what_are_needed(self):
        full = ["--lane", "full", "--mock", "no", "--type", "script"]
        for drop, word in ((0, "--lane"), (2, "--mock"), (4, "--type")):
            args = full[:drop] + full[drop + 2:]
            with self.subTest(missing=word):
                self.assertRefused(self.af("estimate", *(args + ["a script"])), word)
        r = self.af("estimate", *full)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")

    def test_bad_values_are_refused(self):
        for opt, bad in (("--lane", "slow"), ("--mock", "maybe"), ("--type", "banana")):
            args = {"--lane": "full", "--mock": "no", "--type": "script"}
            args[opt] = bad
            flat = [x for kv in args.items() for x in kv]
            with self.subTest(opt=opt):
                self.assertRefused(self.af("estimate", *(flat + ["a script"])), opt)

    def test_estimate_writes_nothing(self):
        before = self.repo.read("agent_completed.txt")
        self.estimate("full", "no", "script", "a script")
        self.assertIsNone(self.model_text())
        self.assertEqual(self.repo.read("agent_completed.txt"), before)
        self.model()
        text = self.model_text()
        self.estimate("full", "no", "script", "a script")
        self.assertEqual(self.model_text(), text)


# ---------------------------------------------------------------- estimate: output

class TestEstimateRubric(EstimateCase):
    """No file (v0) or a rubric version: the rubric's middle and its row."""

    def test_no_file_gives_the_rubric_row(self):
        self.completed(steady(12))
        for lane, mock, kind, mid, lo, hi in (("fast", "no", "page", 10, 5, 15),
                                              ("full", "yes", "page", 75, 60, 90),
                                              ("full", "no", "script", 53, 45, 60),
                                              ("full", "no", "server", 105, 90, 120),
                                              ("full", "no", "cloud", 105, 90, 120)):
            with self.subTest(lane=lane, mock=mock, kind=kind):
                m, likes = self.estimate(lane, mock, kind, "some task")
                self.assertEqual(m.group(1, 2, 3), (str(mid), str(lo), str(hi)))
                self.assertEqual(m.group(4, 5, 6), ("rubric", "0", "12"))
                self.assertEqual(len(likes), 3)

    def test_no_data_at_all(self):
        m, likes = self.estimate("full", "yes", "page", "a page")
        self.assertEqual(m.group(1, 4, 5, 6), ("75", "rubric", "0", "0"))
        self.assertEqual(likes, [])

    def test_a_rubric_version_gives_the_rubric(self):
        self.completed(steady(40))
        self.model(versions=[version(method="rubric")])
        m, _ = self.estimate("full", "yes", "page", "a page")
        self.assertEqual(m.group(1, 2, 3, 4, 5, 6), ("75", "60", "90", "rubric", "1", "40"))

    def test_a_file_that_does_not_read_is_no_file(self):
        self.completed(steady(12))
        self.write("agent_estimate.txt", "{ not json\n")
        m, _ = self.estimate("full", "yes", "page", "a page")
        self.assertEqual(m.group(4, 5), ("rubric", "0"))


class TestEstimateLearned(EstimateCase):

    def test_it_learns_each_kind_from_the_data(self):
        self.completed(steady(40))
        self.model()
        for lane, mock, kind, want in (("fast", "no", "page", 3), ("full", "yes", "page", 140),
                                       ("full", "no", "script", 25), ("full", "no", "server", 60)):
            with self.subTest(kind=kind, mock=mock):
                m, likes = self.estimate(lane, mock, kind, "some task")
                self.assertEqual(m.group(1, 2, 3), (str(want),) * 3)
                self.assertEqual(m.group(4, 5, 6), ("estimator", "1", "40"))
                self.assertEqual([l.group(2) for l in likes], [str(want)] * 3)

    def test_the_like_lines_are_the_newest_on_a_tie(self):
        self.completed(steady(40))
        self.model()
        _, likes = self.estimate("full", "yes", "page", "some task")
        self.assertEqual([l.group(1) for l in likes], ["mock-37", "mock-33", "mock-29"])
        self.assertEqual(likes[0].group(3, 4, 5, 6), ("page", "full", "yes", day(37)))

    def test_the_estimate_is_the_geometric_mean_of_the_neighbours(self):
        rows = [line(day(i), "plain-%02d" % i, "plain work", type="server", lane="full",
                     mock="no", est=60, work=50) for i in range(8)]
        rows += [line(day(8 + i), "m-%d" % i, "page with mock", type="page", lane="full",
                      mock="yes", est=90, work=w) for i, w in enumerate((10, 40, 160))]
        self.completed(rows)
        self.model(versions=[version(k=3, text=0, type=0)])
        m, likes = self.estimate("full", "yes", "page", "some page")
        self.assertEqual(m.group(1), "40")
        self.assertEqual(sorted(l.group(1) for l in likes), ["m-0", "m-1", "m-2"])

    def test_the_text_finds_the_like_tasks(self):
        rows = [line(day(i), "cf-%d" % i, "cloudflare login page step %d" % i, type="cloud",
                     lane="full", mock="no", est=150, work=200) for i in range(3)]
        rows += [line(day(3 + i), "srv-%02d" % i, "server change for the relay number %d" % i,
                      type="cloud", lane="full", mock="no", est=60, work=30) for i in range(20)]
        self.completed(rows)
        self.model(versions=[version(k=3, text=1, type=0)])
        m, likes = self.estimate("full", "no", "cloud", "cloudflare login page step 4")
        self.assertEqual(sorted(l.group(1) for l in likes), ["cf-0", "cf-1", "cf-2"])
        self.assertEqual(m.group(1), "200")

    def test_the_name_counts_as_text(self):
        rows = [line(day(i), "quokka-%d" % i, "plain work", type="cloud", lane="full",
                     mock="no", est=150, work=200) for i in range(3)]
        rows += [line(day(3 + i), "srv-%02d" % i, "plain work", type="cloud", lane="full",
                      mock="no", est=60, work=30) for i in range(10)]
        self.completed(rows)
        self.model(versions=[version(k=3, text=1, type=0)])
        _, likes = self.estimate("full", "no", "cloud", "plain work", "--name", "quokka-9")
        self.assertEqual(sorted(l.group(1) for l in likes), ["quokka-0", "quokka-1", "quokka-2"])

    def test_the_pool_is_the_same_lane(self):
        rows = steady(40)
        rows.append(line(day(41), "big-fix", "fix a small thing on the page", type="page",
                         lane="full", mock="no", est=90, work=300))
        self.completed(rows)
        self.model(versions=[version(k=3, text=1, type=0.5)])
        _, likes = self.estimate("fast", "no", "page", "fix a small thing on the page")
        self.assertTrue(all(l.group(4) == "fast" for l in likes), [l.group(0) for l in likes])

    def test_no_task_of_that_lane_takes_every_task(self):
        self.completed([r for r in steady(40) if " lane=fast " not in r])
        self.model()
        m, likes = self.estimate("fast", "no", "page", "a fix")
        self.assertEqual(len(likes), 3)
        self.assertTrue(all(l.group(4) == "full" for l in likes))

    def test_the_range_holds_the_estimate(self):
        self.completed(varied(40))
        self.model(versions=[version(k=5, text=1, type=0.5)])
        for lane, mock, kind in (("fast", "no", "page"), ("full", "yes", "page"),
                                 ("full", "no", "script")):
            with self.subTest(lane=lane, mock=mock):
                m, _ = self.estimate(lane, mock, kind, "city relay change")
                est, lo, hi = int(m.group(1)), int(m.group(2)), int(m.group(3))
                self.assertTrue(1 <= lo <= est <= hi, m.group(0))
                self.assertLess(lo, hi, m.group(0))

    def test_only_lines_with_a_work_number_count(self):
        rows = steady(12)
        rows.append("2026-09-30 | old | legacy line | est 180m actual 1240m")
        rows.append(line("2026-09-30", "nowork", "x", type="page", lane="full", mock="yes", est=60))
        rows.append("2026-09-30 | gone | x | est 60m actual - | dropped: no")
        self.completed(rows)
        m, _ = self.estimate("full", "yes", "page", "a page")
        self.assertEqual(m.group(6), "12")


# ---------------------------------------------------------------- backtest

class TestBacktest(EstimateCase):

    def test_the_rubric_and_todo_est_by_hand(self):
        rows = steady(10)
        rows.append(line(day(10), "late-mock", "x", type="page", lane="full", mock="yes",
                         est=90, work=100))
        rows.append(line(day(11), "late-fast", "y", type="page", lane="fast", mock="no",
                         est=15, work=4))
        self.completed(rows)
        out = self.assertOk(self.af("backtest"))
        self.assertTrue(self.lines(out)[0].startswith("backtest: 12 tasks, 2 tested"), out)
        t = self.table(out)
        # rubric 75 vs 100 -> 25 (within 30%: yes, in 60-90: no); 10 vs 4 -> 6 (no, no)
        self.assertEqual(t["rubric"].group(1, 2, 3, 4), ("2", "15.5", "50", "0"))
        # est 90 vs 100 -> 10 (yes); 15 vs 4 -> 11 (no)
        self.assertEqual(t["todo est"].group(1, 2, 3), ("2", "10.5", "50"))

    def test_a_steady_history_beats_the_rubric(self):
        self.completed(steady(40))
        t = self.table(self.assertOk(self.af("backtest")))
        self.assertEqual(t["estimator"].group(1), "30")
        self.assertLessEqual(float(t["estimator"].group(2)), 5.0)
        self.assertGreaterEqual(float(t["rubric"].group(2)), 20.0)
        self.assertEqual(t["winner"], "estimator")

    def test_a_tie_goes_to_the_rubric(self):
        self.completed(steady(30, works=RUBRIC_WORK))
        t = self.table(self.assertOk(self.af("backtest")))
        self.assertEqual(t["rubric"].group(2), "0.0")
        self.assertEqual(t["winner"], "rubric")

    def test_fewer_than_11_tasks(self):
        self.completed(steady(10))
        out = self.assertOk(self.af("backtest"))
        self.assertEqual(self.lines(out), ["backtest: 10 tasks, needs at least 11"])

    def test_one_row_per_tested_task_in_finish_order(self):
        self.completed(steady(14))
        rows = self.task_rows(self.assertOk(self.af("backtest", "--tasks")))
        self.assertEqual([TASK_ROW.match(r).group(1) for r in rows],
                         ["script-10", "other-11", "fast-12", "mock-13"])

    def test_finish_order_is_the_date_not_the_file_order(self):
        rows = steady(14)
        self.completed([rows[-1]] + rows[:-1])
        out = self.assertOk(self.af("backtest", "--tasks"))
        self.assertEqual([TASK_ROW.match(r).group(1) for r in self.task_rows(out)],
                         ["script-10", "other-11", "fast-12", "mock-13"])

    def test_a_row_never_changes_when_later_tasks_come(self):
        data = varied(40)
        self.completed(data[:30])
        first = self.task_rows(self.assertOk(self.af("backtest", "--tasks")))
        self.completed(data)
        later = self.task_rows(self.assertOk(self.af("backtest", "--tasks")))
        self.assertEqual(len(first), 20)
        self.assertEqual(later[:20], first)

    def test_the_work_of_the_last_task_changes_only_its_own_row(self):
        data = varied(30)
        self.completed(data)
        a = self.task_rows(self.assertOk(self.af("backtest", "--tasks")))
        last = data[-1]
        work = int(re.search(r" work=(\d+) ", last).group(1))
        data[-1] = last.replace(" work=%d " % work, " work=%d " % (work * 3 + 7))
        self.completed(data)
        b = self.task_rows(self.assertOk(self.af("backtest", "--tasks")))
        self.assertEqual(a[:-1], b[:-1])
        self.assertNotEqual(a[-1], b[-1])

    def test_backtest_writes_nothing(self):
        self.completed(steady(30))
        self.assertOk(self.af("backtest"))
        self.assertIsNone(self.model_text())


# ---------------------------------------------------------------- retrain

class TestRetrainFirst(EstimateCase):

    def test_not_yet_under_30_tasks(self):
        self.completed(steady(29))
        for args in ((), ("--force",)):
            with self.subTest(args=args):
                out = self.assertOk(self.af("retrain", *args))
                self.assertEqual(self.verdicts(out), ["estimate retrain: not yet (29 of 30 tasks)"])
                self.assertIsNone(self.model_text())

    def test_v1_estimator_when_it_wins(self):
        self.completed(steady(30))
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertEqual(len(v), 1, out)
        self.assertTrue(v[0].startswith("estimate retrain: v1 made from 30 tasks: estimator"), v[0])
        t = self.table(out)
        data = self.model_json()
        self.assertEqual((data["current"], data["checked_tasks"], data["checks"]), (1, 30, []))
        self.assertEqual(len(data["versions"]), 1)
        ver = data["versions"][0]
        self.assertEqual((ver["version"], ver["date"], ver["tasks"], ver["method"]),
                         (1, TODAY, 30, "estimator"))
        self.assertIn(ver["k"], (3, 5, 7))
        self.assertIn(ver["text"], (0, 1))
        self.assertIn(ver["type"], (0, 0.5))
        bt = ver["backtest"]
        self.assertEqual(bt["tasks"], 20)
        self.assertEqual(bt["estimator"], {"error": float(t["estimator"].group(2)),
                                           "within30": int(t["estimator"].group(3)),
                                           "inrange": int(t["estimator"].group(4))})
        self.assertEqual(bt["rubric"], {"error": float(t["rubric"].group(2)),
                                        "within30": int(t["rubric"].group(3)),
                                        "inrange": int(t["rubric"].group(4))})

    def test_v1_rubric_when_the_rubric_wins(self):
        self.completed(steady(30, works=RUBRIC_WORK))
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertTrue(v[0].startswith("estimate retrain: v1 made from 30 tasks: rubric"), v)
        self.assertEqual(self.model_json()["versions"][0]["method"], "rubric")
        m, _ = self.estimate("full", "yes", "page", "a page")
        self.assertEqual(m.group(1, 4, 5), ("75", "rubric", "1"))

    def test_after_v1_the_estimate_uses_it(self):
        self.completed(steady(30))
        self.assertOk(self.af("retrain"))
        m, _ = self.estimate("full", "yes", "page", "new page feature with a clickable mock")
        self.assertEqual(m.group(1, 4, 5), ("140", "estimator", "1"))

    def test_the_file_is_json_and_nothing_is_left_beside_it(self):
        self.completed(steady(30))
        self.assertOk(self.af("retrain"))
        json.loads(self.model_text())
        left = [f for f in os.listdir(self.repo.dir) if f.startswith("agent_estimate") and
                f != "agent_estimate.txt"]
        self.assertEqual(left, [])


class TestRetrainCheck(EstimateCase):

    def test_an_undated_file_is_not_due_before_10_new_tasks(self):
        self.completed(steady(39))
        self.model()
        before = self.model_text()
        out = self.assertOk(self.af("retrain"))
        self.assertEqual(self.lines(out), ["estimate retrain: not due (39 tasks, next check at 40)"])
        self.assertEqual(self.model_text(), before)

    def test_a_better_new_version_is_kept(self):
        self.completed(steady(40))
        self.model(versions=[version(method="rubric")])
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertEqual(len(v), 1, out)
        self.assertTrue(v[0].startswith("estimate retrain: kept v2 (on the 10 new tasks: "), v[0])
        data = self.model_json()
        self.assertEqual((data["current"], data["checked_tasks"]), (2, 40))
        self.assertEqual([x["version"] for x in data["versions"]], [1, 2])
        self.assertEqual(data["versions"][1]["method"], "estimator")
        self.assertEqual((data["versions"][1]["tasks"], data["versions"][1]["date"]), (40, TODAY))
        self.assertEqual(len(data["checks"]), 1)
        c = data["checks"][0]
        self.assertEqual((c["date"], c["tasks"], c["new"], c["current"], c["kept"]),
                         (TODAY, 40, 10, 1, 2))
        self.assertEqual(data["checked_date"], TODAY)
        # the rubric on the 10 newest: 28 45 7 65 28 45 7 65 28 45 -> median 36.5
        self.assertEqual(c["current_error"], 36.5)
        self.assertLess(c["new_error"], c["current_error"])

    def test_no_better_keeps_the_current_version(self):
        self.completed(steady(40))
        self.model(versions=[version(k=3, text=0, type=0.5)])
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertTrue(v[0].startswith("estimate retrain: kept v1 (on the 10 new tasks: "), v[0])
        data = self.model_json()
        self.assertEqual((data["current"], data["checked_tasks"]), (1, 40))
        self.assertEqual([x["version"] for x in data["versions"]], [1])
        c = data["checks"][0]
        self.assertEqual((c["tasks"], c["new"], c["current"], c["kept"]), (40, 10, 1, 1))
        self.assertEqual(c["current_error"], 0.0)

    def test_the_next_check_is_7_days_later(self):
        self.completed(steady(40))
        self.model(versions=[version(k=3, text=0, type=0.5)])
        self.assertOk(self.af("retrain"))
        self.assertEqual(self.model_json()["checked_date"], TODAY)
        self.completed(steady(45))
        out = self.assertOk(self.af("retrain"))
        self.assertEqual(self.lines(out), ["estimate retrain: not due (45 tasks, next check on 2026-10-12)"])

    def test_the_target_line_follows_the_table_and_the_verdict(self):
        self.completed(steady(40))
        self.model(versions=[version(k=3, text=0, type=0.5)], date="2026-09-28")
        tgt = re.compile(r"target 5m: (met|error \d+\.\dm, gap \d+\.\dm)$")
        rows = self.lines(self.assertOk(self.af("retrain")))
        self.assertEqual(len([r for r in rows if r.startswith("target 5m: ")]), 2, rows)
        self.assertRegex(rows[-1], tgt)
        self.assertRegex(rows[rows.index([r for r in rows if r.startswith("winner: ")][0]) + 1], tgt)
        self.assertRegex(self.lines(self.assertOk(self.af("backtest")))[-1], tgt)

    def test_6_days_is_not_due(self):
        self.completed(steady(35))
        self.model(date="2026-09-29")
        before = self.model_text()
        out = self.assertOk(self.af("retrain"))
        self.assertEqual(self.lines(out), ["estimate retrain: not due (35 tasks, next check on 2026-10-06)"])
        self.assertEqual(self.model_text(), before)

    def test_7_days_and_1_new_task_is_due(self):
        self.completed(steady(31))
        self.model(date="2026-09-28")
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertTrue(v[0].startswith("estimate retrain: kept v"), out)
        data = self.model_json()
        self.assertEqual((data["checked_tasks"], data["checked_date"]), (31, TODAY))
        self.assertEqual(data["checks"][0]["new"], 1)

    def test_7_days_and_no_new_task_is_not_due(self):
        self.completed(steady(30))
        self.model(date="2026-09-28")
        before = self.model_text()
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertEqual(len(v), 1, out)
        self.assertTrue(v[0].startswith("estimate retrain: not due (30 tasks, next check on %s" % TODAY), v[0])
        self.assertEqual(self.model_text(), before)

    def test_force_checks_when_not_due(self):
        self.completed(steady(33))
        self.model()
        out = self.assertOk(self.af("retrain", "--force"))
        self.assertTrue(self.verdicts(out)[0].startswith("estimate retrain: kept v"), out)
        data = self.model_json()
        self.assertEqual(data["checked_tasks"], 33)
        self.assertEqual(data["checks"][0]["new"], 3)


# ---------------------------------------------------------------- todo done runs it

class TestTodoDoneRetrains(EstimateCase):

    def todo(self, name="t-new"):
        self.write("agent_todo.txt", "%s | big | one shell script | est 50m | opened 2026-10-05 15:00 | by main\n" % name)

    def done(self, name="t-new"):
        return self.assertOk(self.af("todo", "done", name, "--work", "25", "--wait", "0",
                                     "--lane", "full", "--mock", "no", "--type", "script"))

    def test_the_30th_task_makes_v1(self):
        self.completed(steady(29))
        self.todo()
        out = self.done()
        self.assertIn("todo done: t-new", out)
        v = self.verdicts(out)
        self.assertEqual(len(v), 1, out)
        self.assertTrue(v[0].startswith("estimate retrain: v1 made from 30 tasks: "), v[0])
        self.assertNotIn("winner:", out)
        self.assertEqual(self.model_json()["current"], 1)

    def test_not_due_says_nothing(self):
        self.completed(steady(30))
        self.model()
        before = self.model_text()
        self.todo()
        out = self.done()
        self.assertEqual(self.verdicts(out), [])
        self.assertEqual(self.model_text(), before)

    def test_the_10th_new_task_checks_an_undated_file(self):
        self.completed(steady(39))
        self.model(versions=[version(k=3, text=0, type=0.5)])
        self.todo()
        v = self.verdicts(self.done())
        self.assertEqual(len(v), 1)
        self.assertTrue(v[0].startswith("estimate retrain: kept v"), v[0])
        self.assertEqual(self.model_json()["checked_tasks"], 40)

    def test_a_failure_never_stops_todo_done(self):
        self.completed(steady(29))
        self.todo()
        self.repo.write_bin_script("agent_estimate.py", "import sys\nsys.exit('boom')\n")
        out = self.done()
        self.assertIn("todo done: t-new", out)
        self.assertIn(" | t-new | ", self.repo.read("agent_completed.txt"))
        self.assertEqual(self.repo.read("agent_todo.txt").strip(), "")


# ---------------------------------------------------------------- the real 30 tasks

class TestRealData(EstimateCase):
    """The 30 real tasks of this repo as of 2026-10-05 (tests/estimate_real.txt)."""

    def setUp(self):
        super().setUp()
        with open(REAL) as fh:
            self.write("agent_completed.txt", fh.read())

    def test_the_backtest_table(self):
        out = self.assertOk(self.af("backtest"))
        self.assertTrue(self.lines(out)[0].startswith("backtest: 30 tasks, 20 tested"), out)
        t = self.table(out)
        self.assertEqual(t["estimator"].group(1, 2, 3, 4), ("20", "23.0", "40", "60"))
        self.assertEqual(t["rubric"].group(1, 2, 3, 4), ("20", "26.5", "30", "30"))
        self.assertEqual(t["todo est"].group(1, 2, 3), ("20", "26.0", "25"))
        self.assertEqual(t["winner"], "estimator")

    def test_a_task_row(self):
        rows = self.task_rows(self.assertOk(self.af("backtest", "--tasks")))
        self.assertEqual(len(rows), 20)
        self.assertIn("task city-device-join work 43 estimator 28 (18-57) rubric 53", rows)
        self.assertEqual(TASK_ROW.match(rows[0]).group(1), "msg-sides")

    def test_v1_and_three_example_tasks(self):
        out = self.assertOk(self.af("retrain"))
        self.assertTrue(self.verdicts(out)[0].startswith(
            "estimate retrain: v1 made from 30 tasks: estimator"), out)
        ver = self.model_json()["versions"][0]
        self.assertEqual((ver["k"], ver["text"], ver["type"]), (3, 1, 0.5))
        m, likes = self.estimate("fast", "no", "page", "agent-city: fix a typo in the rail label",
                                 "--name", "fix-typo")
        self.assertEqual(m.group(1, 2, 3), ("5", "3", "8"))
        m, likes = self.estimate("full", "yes", "page",
                                 "agent-city: a new 3D page feature with a mock first",
                                 "--name", "city-3d-feature")
        self.assertEqual(m.group(1, 2, 3), ("111", "74", "182"))
        m, likes = self.estimate("full", "no", "script",
                                 "agent-city.sh: join once per computer, hooks gate on team relay, "
                                 "script change with tests", "--name", "script-change")
        self.assertEqual(m.group(1, 2, 3), ("27", "18", "44"))
        self.assertEqual([l.group(1) for l in likes],
                         ["city-device-join", "city-login-start", "session-clean"])


# ---------------------------------------------------------------- speed

class TestSpeed(EstimateCase):

    def test_60_tasks(self):
        self.completed(varied(60))
        t0 = time.monotonic()
        self.assertOk(self.af("retrain"))
        retrain_s = time.monotonic() - t0
        t0 = time.monotonic()
        self.estimate("full", "yes", "page", "city relay change")
        estimate_s = time.monotonic() - t0
        self.assertLess(retrain_s, 30, "retrain took %.1f s" % retrain_s)
        self.assertLess(estimate_s, 5, "estimate took %.1f s" % estimate_s)


# ---------------------------------------------------------------- wired in

def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def section(text, start, end):
    a = text.index(start)
    return text[a:text.index(end, a)]


class TestWiredIn(unittest.TestCase):

    def test_the_dispatch_estimate_step_runs_the_estimator(self):
        step1 = section(read("skills", "dispatch", "SKILL.md"), "\n1. ", "\n2. ")
        for word in ("${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh estimate", "--lane", "--mock",
                     "--type", "agent-file.sh time", "range", "like"):
            with self.subTest(word=word):
                self.assertIn(word, step1)

    def test_the_rubric_numbers_left_the_skill(self):
        step1 = section(read("skills", "dispatch", "SKILL.md"), "\n1. ", "\n2. ")
        for old in ("45 to 60", "60 to 90", "90 to 120", "5 to 15"):
            with self.subTest(old=old):
                self.assertNotIn(old, step1)

    def test_the_time_rules_name_the_estimator(self):
        w11 = section(read("PRINCIPLES.md"), "W11. Time", "W12.")
        self.assertIn("bin/agent-file.sh estimate", w11)
        self.assertIn("bin/agent-file.sh time", w11)
        self.assertNotIn("pick a rubric row", w11)

    def test_the_readme_lists_it(self):
        text = read("README.md")
        for word in ("bin/agent-file.sh estimate", "bin/agent-file.sh backtest",
                     "bin/agent-file.sh retrain", "bin/agent_estimate.py", "`agent_estimate.txt`"):
            with self.subTest(word=word):
                self.assertIn(word, text)

    def test_the_usage_of_agent_file_names_the_new_commands(self):
        head = read("bin", "agent-file.sh").split("\nset -eu")[0]
        for word in ("agent-file.sh estimate", "agent-file.sh backtest",
                     "agent-file.sh retrain", "data [--what]"):
            with self.subTest(word=word):
                self.assertTrue(word in head, "the usage block does not name: " + word)


if __name__ == "__main__":
    unittest.main()
