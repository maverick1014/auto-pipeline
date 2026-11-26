"""Tests of bin/agent_estimate.py: estimate, the blend with a guess, backtest, retrain.

requirements/estimate.md. One class per feature. Older task contracts: git log -p of this file.
"""

import datetime
import json
import os
import random
import re
import time
import unittest

from tests.scripthelp import ROOT, ScriptCase
import importlib.util
from tests.scripthelp import BIN, ROOT

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
    r"^task (\S+) work (\d+) guess (?:\d+|-) estimator (\d+) \((\d+)-(\d+)\) "
    r"blend \d+ \(\d+-\d+\) blend\+repo \d+ \(\d+-\d+\) fit \d+ \(\d+-\d+\) rubric (\d+)$")   # estimate-improve B6: the fit part


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
        # estimate-improve A5: every fixture row is clean (wait 0, clock = work), else it is not learned
        rows = [line(day(i), "plain-%02d" % i, "plain work", type="server", lane="full",
                     mock="no", est=60, work=50, wait=0, clock=50) for i in range(8)]
        rows += [line(day(8 + i), "m-%d" % i, "page with mock", type="page", lane="full",
                      mock="yes", est=90, work=w, wait=0, clock=w) for i, w in enumerate((10, 40, 160))]
        self.completed(rows)
        self.model(versions=[version(k=3, text=0, type=0)])
        m, likes = self.estimate("full", "yes", "page", "some page")
        self.assertEqual(m.group(1), "40")
        self.assertEqual(sorted(l.group(1) for l in likes), ["m-0", "m-1", "m-2"])

    def test_the_text_finds_the_like_tasks(self):
        rows = [line(day(i), "cf-%d" % i, "cloudflare login page step %d" % i, type="cloud",
                     lane="full", mock="no", est=150, work=200, wait=0, clock=200) for i in range(3)]
        rows += [line(day(3 + i), "srv-%02d" % i, "server change for the relay number %d" % i,
                      type="cloud", lane="full", mock="no", est=60, work=30, wait=0, clock=30) for i in range(20)]
        self.completed(rows)
        self.model(versions=[version(k=3, text=1, type=0)])
        m, likes = self.estimate("full", "no", "cloud", "cloudflare login page step 4")
        self.assertEqual(sorted(l.group(1) for l in likes), ["cf-0", "cf-1", "cf-2"])
        self.assertEqual(m.group(1), "200")

    def test_the_name_counts_as_text(self):
        rows = [line(day(i), "quokka-%d" % i, "plain work", type="cloud", lane="full",
                     mock="no", est=150, work=200, wait=0, clock=200) for i in range(3)]
        rows += [line(day(3 + i), "srv-%02d" % i, "plain work", type="cloud", lane="full",
                      mock="no", est=60, work=30, wait=0, clock=30) for i in range(10)]
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
                         est=90, work=100, wait=0, clock=100))        # estimate-improve A5: clean rows
        rows.append(line(day(11), "late-fast", "y", type="page", lane="fast", mock="no",
                         est=15, work=4, wait=0, clock=4))
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

    def test_finish_order_is_the_date_not_the_file_order(self):
        rows = steady(14)
        self.completed([rows[-1]] + rows[:-1])
        out = self.assertOk(self.af("backtest", "--tasks"))
        self.assertEqual([TASK_ROW.match(r).group(1) for r in self.task_rows(out)],
                         ["script-10", "other-11", "fast-12", "mock-13"])

    def test_the_work_of_the_last_task_changes_only_its_own_row(self):
        data = varied(30)
        self.completed(data)
        a = self.task_rows(self.assertOk(self.af("backtest", "--tasks")))
        last = data[-1]
        work = int(re.search(r" work=(\d+) ", last).group(1))
        # estimate-improve A5: the clock grows with the work, or the row would be dirty and leave the backtest
        data[-1] = last.replace(" work=%d " % work, " work=%d " % (work * 3 + 7)).replace(
            " clock=%d " % work, " clock=%d " % (work * 3 + 7))
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

    def test_the_next_check_is_10_tasks_later(self):
        # estimate-improve D12 (2026-11-26): every 10 finished tasks, the week no longer counts
        self.completed(steady(40))
        self.model(versions=[version(k=3, text=0, type=0.5)])
        self.assertOk(self.af("retrain"))
        self.assertEqual(self.model_json()["checked_date"], TODAY)
        self.completed(steady(45))
        out = self.assertOk(self.af("retrain"))
        self.assertEqual(self.lines(out), ["estimate retrain: not due (45 tasks, next check at 50)"])

    def test_the_target_line_follows_the_table_and_the_verdict(self):
        # estimate-blend (owner brief 2026-11-13): the target is a within 30% share, the 5m line goes
        self.completed(steady(40))
        self.model(versions=[version(k=3, text=0, type=0.5)], date="2026-09-28")
        tgt = re.compile(r"^target within 30% 50%: (met \(\d+%\)|\d+%, gap \d+ points)$")
        rows = self.lines(self.assertOk(self.af("retrain")))
        self.assertEqual(len([r for r in rows if r.startswith("target within 30% ")]), 2, rows)
        self.assertFalse([r for r in rows if r.startswith("target 5m")], rows)
        self.assertRegex(rows[-1], tgt)
        self.assertRegex(rows[rows.index([r for r in rows if r.startswith("winner: ")][0]) + 1], tgt)
        self.assertRegex(self.lines(self.assertOk(self.af("backtest")))[-1], tgt)

    def test_5_new_tasks_a_week_later_are_not_due(self):
        # estimate-improve D12: the week rule went; 5 new tasks are not 10
        self.completed(steady(35))
        self.model(date="2026-09-20")
        before = self.model_text()
        out = self.assertOk(self.af("retrain"))
        self.assertEqual(self.lines(out), ["estimate retrain: not due (35 tasks, next check at 40)"])
        self.assertEqual(self.model_text(), before)

    def test_10_new_tasks_the_same_day_are_due(self):
        self.completed(steady(40))
        self.model(date=TODAY)
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertTrue(v[0].startswith("estimate retrain: kept v"), out)
        data = self.model_json()
        self.assertEqual((data["checked_tasks"], data["checked_date"]), (40, TODAY))
        self.assertEqual(data["checks"][0]["new"], 10)

    def test_no_new_task_is_not_due(self):
        self.completed(steady(30))
        self.model(date="2026-09-28")
        before = self.model_text()
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertEqual(v, ["estimate retrain: not due (30 tasks, next check at 40)"], out)
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
        before = json.loads(self.model_text())
        self.todo()
        out = self.done()
        self.assertEqual(self.verdicts(out), [])
        # estimate-improve D12: the only change is one more entry in "measures"
        after = self.model_json()
        self.assertEqual(len(after.pop("measures")), 1)
        self.assertEqual(after, dict(before, checks=before.get("checks", [])))

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

    # estimate-improve A5 (2026-11-26): 15 of these 30 old rows have no wait, so they are not learned; the
    # numbers below are the new code's, checked by the task manager against the row list (only clean rows
    # are scored, each from the clean rows before it)

    def test_the_backtest_table(self):
        out = self.assertOk(self.af("backtest"))
        self.assertTrue(self.lines(out)[0].startswith("backtest: 30 tasks, 5 tested"), out)
        t = self.table(out)
        self.assertEqual(t["estimator"].group(1, 2, 3, 4), ("5", "41.0", "20", "60"))
        self.assertEqual(t["rubric"].group(1, 2, 3, 4), ("5", "23.0", "40", "20"))
        self.assertEqual(t["todo est"].group(1, 2, 3), ("5", "28.0", "20"))
        self.assertEqual(t["winner"], "rubric")

    def test_a_task_row(self):
        rows = self.task_rows(self.assertOk(self.af("backtest", "--tasks")))
        self.assertEqual(len(rows), 5)
        row = [TASK_ROW.match(r) for r in rows if r.startswith("task city-device-join ")]
        self.assertEqual(len(row), 1, rows)
        self.assertEqual(row[0].group(2, 3, 4, 5, 6), ("43", "28", "19", "48", "53"))
        self.assertEqual(TASK_ROW.match(rows[0]).group(1), "city-login-start")

    def test_v1_waits_for_30_clean_tasks(self):
        out = self.assertOk(self.af("retrain"))
        self.assertEqual(self.verdicts(out), ["estimate retrain: not yet (15 of 30 tasks)"])
        self.assertIsNone(self.model_text())

    def test_the_like_tasks_are_clean_ones(self):
        self.model(versions=[version(k=3, text=1, type=0.5)])
        m, likes = self.estimate("full", "no", "script",
                                 "agent-city.sh: join once per computer, hooks gate on team relay, "
                                 "script change with tests", "--name", "script-change")
        self.assertEqual(m.group(1, 2, 3, 6), ("35", "22", "63", "15"))
        self.assertEqual([l.group(1) for l in likes],
                         ["city-device-join", "city-login-start", "estimate-data"])


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


KEYS3 = KEYS + ["guess"]


BLEND_LINE = re.compile(
    r"^estimate: (\d+)m work, range (\d+)-(\d+)m \(blend v(\d+), (\d+) past tasks\)$")


BLEND_WHY = re.compile(
    r"^blend: estimator (\d+)m, guess (\d+)m, weight ([0-9.]+), repo (\S+) x(\d+\.\d\d)$")


TASK_ROW3 = re.compile(
    r"^task (\S+) work (\d+) guess (\d+|-) estimator (\d+) \((\d+)-(\d+)\) "
    r"blend (\d+) \((\d+)-(\d+)\) blend\+repo (\d+) \((\d+)-(\d+)\) fit \d+ \(\d+-\d+\) rubric (\d+)$")


TARGET = re.compile(r"^target within 30% (\d+)%: (?:(\d+)%, gap (\d+) points|met \((\d+)%\))$")


WARN_TAIL = " given (the estimator learns less from this line)"


METHODS = ("estimator", "blend", "blend+repo", "rubric", "todo est")


def mrow(label, has_range=True):
    rng = r"(\d+)%" if has_range else r"-"
    return re.compile(r"^%s\s+(\d+)\s+(\d+\.\d)m\s+(\d+)%%\s+%s\s*$" % (re.escape(label), rng))


def gblock(**known):
    return "data " + " ".join("%s=%s" % (k, known.get(k, "-")) for k in KEYS3)


def gline(date, name, what, **known):
    """A finished line of the new shape: the data block ends with guess=."""
    known.setdefault("repo", "project")
    return "%s | %s | %s | %s" % (date, name, what, gblock(**known))


def alt(n, a, b, mode="guess", start=0):
    """n tasks that look the same (same facts, same text, names with no word),
    work a, b, a, b ... The estimator cannot tell them apart; the guess can.
    mode guess: guess = work, no est. est: an old line, est = work. none: no guess, no est."""
    rows = []
    for i in range(start, start + n):
        w = a if i % 2 == 0 else b
        if mode == "guess":
            rows.append(gline(day(i), "t-%02d" % i, "plain work", type="server", lane="full",
                              mock="no", work=w, wait=0, clock=w, guess=w))
        elif mode == "est":
            rows.append(line(day(i), "t-%02d" % i, "plain work", type="server", lane="full",
                             mock="no", est=w, work=w, wait=0, clock=w))
        else:
            rows.append(line(day(i), "t-%02d" % i, "plain work", type="server", lane="full",
                             mock="no", work=w, wait=0, clock=w))
    return rows


def two_repos(n):
    """Even: repo project, work 50, guess 50. Odd: repo shop, work 100, guess 50.
    Same facts and text, so only a per-repo bias can fix the shop tasks."""
    rows = []
    for i in range(n):
        repo, w = ("project", 50) if i % 2 == 0 else ("shop", 100)
        rows.append(gline(day(i), "r-%02d" % i, "plain work", repo=repo, type="server",
                          lane="full", mock="no", work=w, wait=0, clock=w, guess=50))
    return rows


def blend_version(**over):
    v = version(method="blend", k=3, text=0, type=0.5, weight=0.5, repo_bias=False,
                bias={}, span=[0.8, 1.5])
    v.update(over)
    return v


class BlendCase(EstimateCase):

    def est(self, *args):
        """estimate, raw lines."""
        return self.lines(self.assertOk(self.af("estimate", *args)))

    def rows3(self, out):
        rows = [r for r in self.lines(out) if r.startswith("task ")]
        got = [TASK_ROW3.match(r) for r in rows]
        for r, m in zip(rows, got):
            self.assertIsNotNone(m, "task row: %r" % r)
        return got

    def table3(self, out, prefix=""):
        rows = self.lines(out)
        found = {}
        for label in METHODS:
            want = mrow(prefix + label, label != "todo est")
            zero = re.compile(r"^%s\s+(0)\s+(-)\s+(-)\s+(-)\s*$" % re.escape(prefix + label))
            hits = [m for m in (want.match(r) or zero.match(r) for r in rows) if m]
            self.assertEqual(len(hits), 1, "one %r row in:\n%s" % (prefix + label, out))
            found[label] = hits[0]
        return found

    def zero_rows(self, out):
        return [r for r in self.lines(out) if re.match(r"^big .+\s0\s+-\s+-\s+-\s*$", r)]

    def winner(self, out):
        w = [r for r in self.lines(out) if r.startswith("winner: ")]
        self.assertEqual(len(w), 1, out)
        return w[0][len("winner: "):]


def load_conf_module():
    spec = importlib.util.spec_from_file_location("agent_conf_blend", os.path.join(BIN, "agent_conf.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTodoGuess(BlendCase):

    def todo_text(self):
        return self.repo.read("agent_todo.txt")

    def test_todo_add_keeps_the_guess_after_est(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70", "--guess", "35"))
        self.assertEqual(self.todo_text(),
                         "t1 | big | build it | est 70m | guess 35m | opened %s | by main | owner t\n" % NOW)

    def test_the_guess_may_stand_anywhere(self):
        for args in (("--guess", "35", "t1", "big", "build it", "70"),
                     ("t1", "--guess", "35", "big", "build it", "70"),
                     ("t1", "big", "build it", "70", "--guess", "35")):
            with self.subTest(args=args):
                self.write("agent_todo.txt", "")
                self.assertOk(self.af("todo", "add", *args))
                self.assertEqual(self.todo_text(),
                                 "t1 | big | build it | est 70m | guess 35m | opened %s | by main | owner t\n" % NOW)

    def test_by_still_works(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70", "laptop", "--guess", "35"))
        self.assertEqual(self.todo_text(),
                         "t1 | big | build it | est 70m | guess 35m | opened %s | by laptop | owner t\n" % NOW)

    def test_a_guess_with_no_est(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "--guess", "35"))
        self.assertEqual(self.todo_text(),
                         "t1 | big | build it | guess 35m | opened %s | by main | owner t\n" % NOW)

    def test_no_guess_is_the_line_as_before(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70"))
        self.assertEqual(self.todo_text(), "t1 | big | build it | est 70m | opened %s | by main | owner t\n" % NOW)

    def test_a_bad_guess_is_refused(self):
        self.write("agent_todo.txt", "keep | big | x | est 5m | opened %s | by main | owner t\n" % NOW)
        before = self.todo_text()
        for bad in (("--guess", "0"), ("--guess", "abc"), ("--guess", "-3"), ("--guess", "1.5"),
                    ("--guess",)):
            with self.subTest(bad=bad):
                r = self.af("todo", "add", "t1", "big", "build it", "70", *bad)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                err = [l for l in r.stderr.splitlines() if l.strip()]
                self.assertEqual(len(err), 1, r.stderr)
                self.assertIn("--guess", err[0])
                self.assertEqual(self.todo_text(), before)

    def done_line(self):
        rows = [l for l in self.repo.read("agent_completed.txt").splitlines() if l.strip()]
        self.assertEqual(len(rows), 1, rows)
        return rows[0]

    def test_todo_done_writes_the_guess_last(self):
        self.write("agent_todo.txt", "t1 | big | build it | est 70m | guess 35m | opened 2026-10-05 15:00 | by main | owner t\n")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        # test-levels (2026-11-20): level= follows guess=; estimate-improve (2026-11-26): six keys follow level,
        # and the work is measured (wait 0, clock 60), the typed 60 kept as typed=
        self.assertEqual(self.done_line(), "%s | t1 | build it | %s level=- typed=60 est0=70 added=- built=- "
                         "stages=- slices=- by=t" % (TODAY, gblock(
                             repo="project", type="script", lane="full", est=70, work=60, wait=0, clock=60,
                             guess=35)))

    def test_todo_done_with_no_guess_writes_a_dash(self):
        self.write("agent_todo.txt", "t1 | big | build it | est 70m | opened 2026-10-05 15:00 | by main | owner t\n")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertIn(" adds=- guess=- level=- typed=", self.done_line())

    def test_a_guess_word_in_the_what_is_not_the_guess(self):
        self.write("agent_todo.txt", "t1 | big | guess 99m is a word here | est 70m | opened 2026-10-05 15:00 | by main | owner t\n")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertIn(" guess=- level=- typed=", self.done_line())

    def test_the_warning_names_the_missing_facts(self):
        for opts, want in ((("--type", "script", "--lane", "full"), None),
                           (("--lane", "full"), "todo done: warning: no --type" + WARN_TAIL),
                           (("--type", "script"), "todo done: warning: no --lane" + WARN_TAIL),
                           ((), "todo done: warning: no --type --lane" + WARN_TAIL)):
            with self.subTest(opts=opts):
                self.write("agent_todo.txt", "t1 | big | build it | est 70m | opened 2026-10-05 15:00 | by main | owner t\n")
                self.write("agent_completed.txt", "")
                r = self.af("todo", "done", "t1", "--work", "60", *opts)
                self.assertOk(r)
                self.assertIn("todo done: t1", r.stdout)
                self.assertNotIn("warning", r.stdout)
                warn = [l for l in r.stderr.splitlines() if "warning" in l]
                self.assertEqual(warn, [want] if want else [], r.stderr)
                self.assertIn(" | t1 | build it | ", self.done_line())
                self.assertEqual(self.todo_text().strip(), "")


class TestDataGuess(BlendCase):

    def setUp(self):
        super().setUp()
        self.completed([
            gline("2026-10-01", "new-one", "has a guess", type="script", lane="full", mock="no",
                  est=70, work=60, guess=35),
            line("2026-10-02", "old-one", "an old data line", type="page", lane="fast", mock="no",
                 est=10, work=4),
        ])

    def test_the_table_has_a_guess_column_after_adds(self):
        rows = [r.split() for r in self.lines(self.assertOk(self.af("data")))]
        self.assertEqual(rows[0][-2:], ["adds", "guess"])
        self.assertEqual(rows[1][-1], "35")
        self.assertEqual(rows[2][-1], "-")

    def test_with_what_the_guess_comes_before_what(self):
        # estimate-improve: est0 typed built stages slices come between guess and what (data --what only)
        rows = [r.split() for r in self.lines(self.assertOk(self.af("data", "--what")))]
        self.assertEqual(rows[0][-8:], ["adds", "guess", "est0", "typed", "built", "stages", "slices", "what"])
        self.assertEqual(rows[1][-9:], ["35", "-", "-", "-", "-", "-", "has", "a", "guess"])
        self.assertEqual(rows[2][-10:], ["-", "-", "-", "-", "-", "-", "an", "old", "data", "line"])


class TestEstimateGuessInputs(BlendCase):

    def setUp(self):
        super().setUp()
        self.completed(steady(40))

    def test_a_bad_guess_is_refused(self):
        for bad in (("--guess", "0"), ("--guess", "x"), ("--guess", "-1"), ("--guess", "2.5")):
            with self.subTest(bad=bad):
                r = self.af("estimate", "--lane", "full", "--mock", "no", "--type", "script",
                            *(bad + ("a script",)))
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertEqual(r.stdout, "")
                err = [l for l in r.stderr.splitlines() if l.strip()]
                self.assertEqual(len(err), 1, r.stderr)
                self.assertIn("--guess", err[0])
        r = self.af("estimate", "--lane", "full", "--mock", "no", "--type", "script", "a script", "--guess")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertIn("--guess", r.stderr)

    def test_no_file_says_the_guess_is_not_used(self):
        rows = self.est("--lane", "full", "--mock", "yes", "--type", "page", "--guess", "35", "a page")
        self.assertEqual(rows[0], "estimate: 75m work, range 60-90m (rubric v0, 40 past tasks)")
        self.assertEqual(rows[1], "guess: 35m, not used: v0 is rubric")
        self.assertEqual(len([r for r in rows if r.startswith("like ")]), 3)

    def test_an_estimator_version_says_the_guess_is_not_used(self):
        self.model()
        plain = self.est("--lane", "full", "--mock", "yes", "--type", "page", "a page")
        rows = self.est("--lane", "full", "--mock", "yes", "--type", "page", "--guess", "35", "a page")
        self.assertEqual(rows[0], plain[0])
        self.assertEqual(rows[0], "estimate: 140m work, range 140-140m (estimator v1, 40 past tasks)")
        self.assertEqual(rows[1], "guess: 35m, not used: v1 is estimator")
        self.assertEqual(rows[2:], plain[1:])

    def test_a_rubric_version_says_the_guess_is_not_used(self):
        self.model(versions=[version(method="rubric")])
        rows = self.est("--lane", "full", "--mock", "yes", "--type", "page", "--guess", "35", "a page")
        self.assertEqual(rows[1], "guess: 35m, not used: v1 is rubric")

    def test_estimate_with_a_guess_writes_nothing(self):
        self.model(versions=[blend_version()])
        before = (self.model_text(), self.repo.read("agent_completed.txt"))
        self.est("--lane", "full", "--mock", "yes", "--type", "page", "--guess", "35", "a page")
        self.assertEqual((self.model_text(), self.repo.read("agent_completed.txt")), before)


class TestEstimateBlendVersion(BlendCase):
    """A blend version, hand made. steady(40): the estimator says 140 for the mock kind."""

    MOCK = ("--lane", "full", "--mock", "yes", "--type", "page")
    WHAT = "new page feature with a clickable mock"

    def setUp(self):
        super().setUp()
        self.completed(steady(40))

    def blend(self, guess, **over):
        self.model(versions=[blend_version(**over)])
        rows = self.est(*(self.MOCK + ("--guess", str(guess), self.WHAT)))
        m = BLEND_LINE.match(rows[0])
        self.assertIsNotNone(m, rows[0])
        why = BLEND_WHY.match(rows[1])
        self.assertIsNotNone(why, rows[1])
        return m, why, rows

    def test_the_geometric_mean_of_estimator_and_guess(self):
        m, why, rows = self.blend(35)
        self.assertEqual(rows[0], "estimate: 70m work, range 56-105m (blend v1, 40 past tasks)")
        self.assertEqual(rows[1], "blend: estimator 140m, guess 35m, weight 0.5, repo project x1.00")
        self.assertEqual(len([r for r in rows if r.startswith("like ")]), 3)

    def test_the_weight_of_the_version(self):
        m, why, _ = self.blend(35, weight=0.25)
        # 140^0.75 x 35^0.25 = 98.99
        self.assertEqual(m.group(1, 2, 3), ("99", "79", "149"))
        self.assertEqual(why.group(3), "0.25")

    def test_the_repo_bias_of_this_repo(self):
        m, why, rows = self.blend(35, repo_bias=True, bias={"project": 1.5, "shop": 0.5})
        self.assertEqual(m.group(1, 2, 3), ("105", "84", "158"))
        self.assertEqual(rows[1], "blend: estimator 140m, guess 35m, weight 0.5, repo project x1.50")

    def test_a_repo_not_in_the_bias_gets_none(self):
        m, why, _ = self.blend(35, repo_bias=True, bias={"shop": 0.5})
        self.assertEqual((m.group(1), why.group(4, 5)), ("70", ("project", "1.00")))

    def test_bias_off_ignores_the_map(self):
        m, why, _ = self.blend(35, repo_bias=False, bias={"project": 1.5})
        self.assertEqual((m.group(1), why.group(5)), ("70", "1.00"))

    def test_the_range_grows_with_the_blend(self):
        m, _, _ = self.blend(600, span=[0.7, 1.6])
        # sqrt(140 x 600) = 289.8
        self.assertEqual(m.group(1, 2, 3), ("290", "203", "464"))

    def test_no_guess_is_the_estimator_of_the_version(self):
        self.model(versions=[blend_version()])
        rows = self.est(*(self.MOCK + (self.WHAT,)))
        self.assertEqual(rows[0], "estimate: 140m work, range 140-140m (estimator v1, 40 past tasks)")
        self.assertFalse([r for r in rows if r.startswith("blend:") or r.startswith("guess:")], rows)

    def test_a_blend_version_that_does_not_read_is_no_file(self):
        for bad in (dict(weight="x"), dict(weight=0), dict(weight=1.5), dict(span=[1.5]),
                    dict(span=[2.0, 1.0]), dict(bias=[1, 2]), dict(bias={"project": "x"}),
                    dict(repo_bias="yes")):
            with self.subTest(bad=bad):
                self.model(versions=[blend_version(**bad)])
                rows = self.est(*(self.MOCK + ("--guess", "35", self.WHAT)))
                self.assertTrue(rows[0].endswith("(rubric v0, 40 past tasks)"), rows[0])

    def test_a_blend_version_with_no_weight_does_not_read(self):
        v = blend_version()
        del v["weight"]
        self.model(versions=[v])
        rows = self.est(*(self.MOCK + ("--guess", "35", self.WHAT)))
        self.assertTrue(rows[0].endswith("(rubric v0, 40 past tasks)"), rows[0])


class TestBacktestBlend(BlendCase):

    def test_the_rows_the_big_rows_the_winner_and_the_target_last(self):
        self.completed(steady(40))
        out = self.assertOk(self.af("backtest"))
        rows = self.lines(out)
        self.assertTrue(rows[0].startswith("backtest: 40 tasks, 30 tested"), out)
        t = self.table3(out)
        big = self.table3(out, "big ")
        for name in METHODS[:-1]:
            self.assertEqual(t[name].group(1), "30", name)
        self.assertIn("work >= 120m: 7 tasks", rows)
        for name in METHODS:
            self.assertEqual(big[name].group(1), "7", name)
        order = [rows.index(r) for r in rows if r.startswith(("method ", "work >= ", "winner: "))]
        self.assertEqual(order, sorted(order))
        self.assertTrue(rows[-2].startswith("winner: "), rows)
        self.assertRegex(rows[-1], TARGET)
        self.assertFalse([r for r in rows if r.startswith("target 5m")], out)

    def test_no_guess_the_blend_is_the_estimator(self):
        self.completed(alt(30, 50, 100, "none"))
        out = self.assertOk(self.af("backtest", "--tasks"))
        for m in self.rows3(out):
            self.assertEqual(m.group(3), "-")
            self.assertEqual(m.group(7, 8, 9), m.group(4, 5, 6), m.group(0))
            self.assertEqual(m.group(10, 11, 12), m.group(4, 5, 6), m.group(0))
        t = self.table3(out)
        for name in ("blend", "blend+repo"):
            self.assertEqual(t[name].group(1, 2, 3, 4), t["estimator"].group(1, 2, 3, 4), name)
        self.assertNotIn("blend", self.winner(out))

    def test_the_blend_wins_when_the_guess_knows_more(self):
        self.completed(alt(30, 50, 100, "guess"))
        out = self.assertOk(self.af("backtest", "--tasks"))
        t = self.table3(out)
        self.assertEqual(t["estimator"].group(3), "0")
        self.assertEqual(t["blend"].group(3), "100")
        self.assertIn(self.winner(out), ("blend", "blend+repo"))
        self.assertEqual(self.lines(out)[-1], "target within 30% 50%: met (100%)")
        for m in self.rows3(out):
            self.assertEqual(m.group(3), m.group(2))

    def test_an_old_line_gives_its_todo_est_as_the_guess(self):
        self.completed(alt(30, 50, 100, "est"))
        old = self.rows3(self.assertOk(self.af("backtest", "--tasks")))
        self.completed(alt(30, 50, 100, "guess"))
        new = self.rows3(self.assertOk(self.af("backtest", "--tasks")))
        self.assertEqual([m.group(0) for m in old], [m.group(0) for m in new])

    def test_no_est_anywhere_the_todo_est_rows_are_empty(self):
        self.completed(alt(30, 50, 100, "guess"))
        rows = self.lines(self.assertOk(self.af("backtest")))
        self.assertTrue([r for r in rows if re.match(r"^todo est\s+0\s+-\s+-\s+-\s*$", r)], rows)
        self.assertTrue([r for r in rows if re.match(r"^big todo est\s+0\s+-\s+-\s+-\s*$", r)], rows)

    def test_a_todo_est_of_0_is_no_guess(self):
        # bounce 2 (task manager): log(0) must never be reached; an est of 0 is no guess
        rows = alt(30, 50, 100, "est")
        rows[20] = rows[20].replace(" est=50 ", " est=0 ")
        self.completed(rows)
        got = self.rows3(self.assertOk(self.af("backtest", "--tasks")))
        self.assertEqual(got[10].group(1, 3), ("t-20", "-"))
        self.assertEqual(got[10].group(7, 8, 9), got[10].group(4, 5, 6))

    def test_the_guess_goes_before_the_todo_est(self):
        rows = [r.replace(" est=-", " est=999") for r in alt(30, 50, 100, "guess")]
        self.completed(rows)
        for m in self.rows3(self.assertOk(self.af("backtest", "--tasks"))):
            self.assertEqual(m.group(3), m.group(2))

    def test_every_range_holds_its_estimate(self):
        self.completed(varied(40))
        for m in self.rows3(self.assertOk(self.af("backtest", "--tasks"))):
            for est, lo, hi in ((4, 5, 6), (7, 8, 9), (10, 11, 12)):
                e, l, h = int(m.group(est)), int(m.group(lo)), int(m.group(hi))
                self.assertTrue(1 <= l <= e <= h, m.group(0))

    def test_a_row_never_changes_when_later_tasks_come(self):
        data = varied(45)
        self.completed(data[:32])
        first = [m.group(0) for m in self.rows3(self.assertOk(self.af("backtest", "--tasks")))]
        self.completed(data)
        later = [m.group(0) for m in self.rows3(self.assertOk(self.af("backtest", "--tasks")))]
        self.assertEqual(len(first), 22)
        self.assertEqual(later[:22], first)

    def test_the_repo_bias_needs_5_earlier_tasks_of_that_repo(self):
        self.completed(two_repos(40))
        out = self.assertOk(self.af("backtest", "--tasks"))
        shop = [m for m in self.rows3(out) if m.group(2) == "100"]
        same = [m.group(10) == m.group(7) for m in shop]
        self.assertEqual(same, [True] * 5 + [False] * (len(shop) - 5))
        self.assertTrue(all(int(m.group(10)) > int(m.group(7)) for m in shop[5:]))
        t = self.table3(out)
        self.assertGreater(int(t["blend+repo"].group(3)), int(t["blend"].group(3)))
        self.assertEqual(self.winner(out), "blend+repo")

    def test_the_target_is_the_winner_row_against_the_config(self):
        self.completed(varied(40))
        out = self.assertOk(self.af("backtest"))
        t = self.table3(out)
        p = int(t[self.winner(out)].group(3))
        m = TARGET.match(self.lines(out)[-1])
        self.assertIsNotNone(m, out)
        self.assertEqual(m.group(1), "50")
        if p >= 50:
            self.assertEqual(m.group(4), str(p))
        else:
            self.assertEqual((m.group(2), m.group(3)), (str(p), str(50 - p)))


class TestRetrainBlend(BlendCase):

    def v1(self):
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertEqual(len(v), 1, out)
        return out, v[0], self.model_json()["versions"][0]

    def test_v1_is_a_blend_when_it_wins(self):
        self.completed(alt(30, 50, 100, "guess"))
        out, verdict, ver = self.v1()
        self.assertTrue(verdict.startswith("estimate retrain: v1 made from 30 tasks: blend (weight 0.5, repo bias "),
                        verdict)
        self.assertEqual((ver["method"], ver["weight"]), ("blend", 0.5))
        self.assertIsInstance(ver["repo_bias"], bool)
        self.assertIsInstance(ver["bias"], dict)
        if not ver["repo_bias"]:
            self.assertEqual(ver["bias"], {})
        lo, hi = ver["span"]
        self.assertLessEqual(lo, hi)
        self.assertIn(ver["k"], (3, 5, 7))
        t = self.table3(out)
        for key, label in (("blend", "blend"), ("blend_repo", "blend+repo"),
                           ("estimator", "estimator"), ("rubric", "rubric")):
            self.assertEqual(ver["backtest"][key], {"error": float(t[label].group(2)),
                                                    "within30": int(t[label].group(3)),
                                                    "inrange": int(t[label].group(4))}, key)
        self.assertRegex(self.lines(out)[-1], TARGET)

    def test_then_the_estimate_uses_the_blend(self):
        self.completed(alt(30, 50, 100, "guess"))
        self.v1()
        rows = self.est("--lane", "full", "--mock", "no", "--type", "server", "--guess", "50", "plain work")
        m = BLEND_LINE.match(rows[0])
        self.assertIsNotNone(m, rows)
        self.assertEqual(m.group(4, 5), ("1", "30"))
        self.assertIsNotNone(BLEND_WHY.match(rows[1]), rows)

    def test_the_weight_moves_only_on_a_clear_win(self):
        self.completed(alt(40, 30, 100, "guess"))
        _, verdict, ver = self.v1()
        self.assertEqual((ver["method"], ver["weight"]), ("blend", 0.75), verdict)
        self.assertTrue(verdict.startswith("estimate retrain: v1 made from 40 tasks: blend (weight 0.75, "),
                        verdict)

    def test_the_repo_bias_is_kept_when_it_wins(self):
        self.completed(two_repos(40))
        _, verdict, ver = self.v1()
        self.assertIn("repo bias on", verdict)
        self.assertEqual((ver["method"], ver["repo_bias"]), ("blend", True))
        self.assertEqual(sorted(ver["bias"]), ["project", "shop"])
        self.assertGreater(ver["bias"]["shop"], 1.5)
        self.assertLess(ver["bias"]["project"], 1.0)
        self.assertEqual(ver["bias"]["shop"], round(ver["bias"]["shop"], 2))
        rows = self.est("--lane", "full", "--mock", "no", "--type", "server", "--guess", "50", "plain work")
        self.assertEqual(BLEND_WHY.match(rows[1]).group(4, 5), ("project", "%.2f" % ver["bias"]["project"]))

    def test_no_guess_no_blend(self):
        self.completed(alt(30, 50, 100, "none"))
        _, verdict, ver = self.v1()
        self.assertIn(ver["method"], ("estimator", "rubric"))
        self.assertNotIn("weight", ver)

    def check_model(self):
        self.model(current=2, checked=30, date="2026-09-28",
                   versions=[version(), version(version=2, date="2026-09-20")])

    def test_a_check_switches_to_the_blend_when_its_backtest_beats_the_current(self):
        self.completed(alt(40, 50, 100, "guess"))
        self.check_model()
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertEqual(len(v), 1, out)
        m = re.match(r"^estimate retrain: kept v3 \(backtest on 30 tasks, within 30%: "
                     r"(blend|blend\+repo) (\d+)%, estimator v2 (\d+)%\)$", v[0])
        self.assertIsNotNone(m, v[0])
        self.assertGreater(int(m.group(2)), int(m.group(3)))
        data = self.model_json()
        self.assertEqual((data["current"], data["checked_tasks"], data["checked_date"]), (3, 40, TODAY))
        self.assertEqual([x["version"] for x in data["versions"]], [1, 2, 3])
        self.assertEqual(data["versions"][2]["method"], "blend")
        c = data["checks"][-1]
        self.assertEqual((c["current"], c["kept"], c["new"], c["basis"]), (2, 3, 10, "backtest"))
        self.assertRegex(self.lines(out)[-1], TARGET)

    def test_a_check_with_no_blend_win_keeps_the_old_rule(self):
        self.completed(steady(40))
        self.model(current=1, checked=30, date="2026-09-28", versions=[version(k=3, text=0, type=0.5)])
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertTrue(v[0].startswith("estimate retrain: kept v1 (on the 10 new tasks: "), v[0])
        data = self.model_json()
        self.assertEqual([x["method"] for x in data["versions"]], ["estimator"])
        self.assertEqual(data["checks"][-1]["basis"], "new tasks")

    def test_a_blend_version_is_checked_on_the_new_tasks(self):
        self.completed(alt(40, 50, 100, "guess"))
        self.model(current=1, checked=30, date="2026-09-28", versions=[blend_version(span=[0.8, 1.3])])
        out = self.assertOk(self.af("retrain"))
        v = self.verdicts(out)
        self.assertTrue(v[0].startswith("estimate retrain: kept v"), v[0])
        self.assertIn("on the 10 new tasks: current v1 error ", v[0])
        self.assertEqual(self.model_json()["checks"][-1]["basis"], "new tasks")


class TestEstimateConf(unittest.TestCase):
    """settings-configure: the estimator numbers are fixed constants."""

    def test_the_constants(self):
        ac = load_conf_module()
        self.assertEqual((ac.CONSTANTS["estimate_target_pct"], ac.CONSTANTS["estimate_bias_min"],
                          ac.CONSTANTS["estimate_big_min"]), (50, 5, 120))


if __name__ == "__main__":
    unittest.main()
