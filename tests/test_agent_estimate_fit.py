"""Failing tests of estimate-improve, part B: the model (requirements/estimate-improve.md, section 5
items 6-7). Written by the task manager first. Part A (tests/test_agent_estimate_inputs.py) is assumed:
clean rows, the label, the measure lines.

CONTRACT (bin/agent_estimate.py)

B6  The fit: a log-space fit with a slope, in place of the fixed 50/50 blend when it is better.
    fit_log(triples) -> (a, b, c) or None
        triples = (knn, guess, label) of clean rows; knn = the row's rolling estimator estimate (from the
        clean rows before it), guess = its guess (its own, else its todo est), label = its work label.
        Least squares on ln(label) = a + b ln(knn) + c ln(guess), with a ridge of FIT_RIDGE (1.0) that
        pulls b and c toward 0.5 each (the blend): minimise sum (ln label - a - b ln knn - c ln guess)^2
        + FIT_RIDGE ((b - 0.5)^2 + (c - 0.5)^2). Fewer than MIN_FIT_ROWS (30) triples: None.
    fit_log(pairs, guess=False) -> (a, b) or None: the same without a guess, ln(label) = a + b ln(knn),
        the ridge pulls b toward 1.0.
    fit_estimate(coef, knn, guess=None) -> whole minutes (half up), at least 1:
        exp(a + b ln knn + c ln guess), or exp(a + b ln knn) for a two-number coef.
    The backtest gets the row "fit" (and "big fit"), right after "blend+repo": each scored row from the
    triples of the scored rows before it (a scored row: clean, 10 or more clean rows before it, as in
    part A); fewer than 30 of them: that row's fit estimate is the blend's. No guess on the row: the no-guess fit, fewer than 30 pairs: the estimator.
    Its range: the 20th and 80th percentile of label / fit estimate of the scored rows before it (fewer than
    10: the blend's range).
    Winner (winner_of(methods, rows), the backtest rows): "fit" only when at least one scored row was really
    fitted (30 or more triples before it, row["fitted"]) and its spread (as in the measure line, 2 decimals)
    is strictly lower than the spread of the blend row, of the blend+repo row (the requirement: it must beat
    the blend) and of the winner by today's rules; else today's winner. `--tasks` rows get " fit <f> (<lo>-<hi>)" right after
    the blend+repo part.
    retrain: a first version may be "fit". A check where the winner is fit and the current version is not:
    the fit is kept only when its backtest spread is strictly lower than the spread of the current version's
    method (basis "backtest"); a current fit version and a fit winner: the current one stays
    (kept v<cur>, nothing new: the fit is made from the data at each estimate). A fit version carries
    the blend keys (weight, repo_bias, bias, span) for the fall-back and reads only with them.
    estimate with a fit version: the fit made now from the triples of every scored row (each row's knn
    from the clean rows before it, as in the backtest). --guess: the fit with a guess; else the no-guess fit. First line method "fit"
    ("estimate: <m>m work, range <lo>-<hi>m (fit v<n>, <N> past tasks)"); second line
        "fit: estimator <e>m, guess <g>m, a <a> b <b> c <c>, <n> rows"   (a, b, c with 2 decimals)
        "fit: estimator <e>m, a <a> b <b>, <n> rows"                      (no --guess)
    Fewer than 30 rows for the fit: the blend (with --guess, its line "blend: ...") or the estimator.
B7  p50 and p85 from the history of ln(actual / estimate), never from a guess:
    `estimate` prints the line "p50 <m>m, p85 <m>m (<n> past errors)" right after the first line and the
    fit / blend / guess line (when there is one), before the like lines.
    q = ln(label / estimate) of the backtest's scored rows of the method the estimate used (estimator,
    blend or blend+repo by the version's repo_bias, fit, rubric for a rubric version or no file).
    n >= 10: p50 = estimate x exp(median q), p85 = estimate x exp(85th percentile of q, linear), whole
    minutes half up, 1 <= p50 <= p85. n < 10: p50 = the estimate, p85 = the range's high end.
"""

import importlib.util
import json
import math
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import BIN  # noqa: E402
from test_agent_estimate import EstimateCase, steady, varied, day, version, alt, blend_version  # noqa: E402
from test_agent_estimate_inputs import row  # noqa: E402

FIRST = re.compile(r"^estimate: (\d+)m work, range (\d+)-(\d+)m \((estimator|rubric|blend|fit) v(\d+), (\d+) past tasks\)$")
P_LINE = re.compile(r"^p50 (\d+)m, p85 (\d+)m \((\d+) past errors\)$")
FIT_G = re.compile(r"^fit: estimator (\d+)m, guess (\d+)m, a (-?\d+\.\d\d) b (-?\d+\.\d\d) c (-?\d+\.\d\d), (\d+) rows$")
FIT_N = re.compile(r"^fit: estimator (\d+)m, a (-?\d+\.\d\d) b (-?\d+\.\d\d), (\d+) rows$")
FIT_ROW = re.compile(r"^fit\s+(\d+)\s+(\d+\.\d)m\s+(\d+)%\s+(\d+)%\s*$")
SPREAD = re.compile(r"^measure work: n (\d+) bias \S+ spread (\d+\.\d\d)$")


def load():
    spec = importlib.util.spec_from_file_location("agent_estimate_fit_t", os.path.join(BIN, "agent_estimate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def two_sizes(n):
    """(knn, guess, label): small tasks ran their knn number, big ones twice it."""
    noise = [0.8, 1.25, 1.0, 0.9, 1.1, 1.2, 0.85]
    out = []
    for i in range(n):
        if i % 2 == 0:
            knn = 10 + (i * 7) % 21              # 10..30
            label = knn
        else:
            knn = 120 + (i * 13) % 131           # 120..250
            label = 2 * knn
        out.append((knn, max(1, round(knn * noise[i % len(noise)])), label))
    return out


def fit_version(**over):
    v = blend_version(method="fit")
    v.update(over)
    return v


# ---------------------------------------------------------------- B6 the fit itself

class TestFitFunction(unittest.TestCase):

    def setUp(self):
        self.m = load()

    def test_6_4_it_undoes_the_compression(self):
        coef = self.m.fit_log(two_sizes(40))
        self.assertIsNotNone(coef)
        self.assertEqual(len(coef), 3)
        big = self.m.fit_estimate(coef, 200, 200)
        small = self.m.fit_estimate(coef, 15, 15)
        self.assertGreater(big, 200 * 1.3, coef)
        self.assertLessEqual(abs(small - 15), 0.3 * 15, (small, coef))

    def test_fewer_than_30_rows_is_no_fit(self):
        self.assertIsNone(self.m.fit_log(two_sizes(29)))
        self.assertIsNotNone(self.m.fit_log(two_sizes(30)))
        self.assertEqual(self.m.MIN_FIT_ROWS, 30)

    def test_the_ridge_pulls_toward_the_blend(self):
        # every row the same: no information, so b and c stay at the blend's 0.5 and a explains the level
        same = [(50, 50, 50)] * 30
        a, b, c = self.m.fit_log(same)
        self.assertAlmostEqual(b, 0.5, places=6)
        self.assertAlmostEqual(c, 0.5, places=6)
        self.assertEqual(self.m.fit_estimate((a, b, c), 50, 50), 50)

    def test_the_no_guess_fit(self):
        pairs = [(k, l) for k, _, l in two_sizes(40)]
        coef = self.m.fit_log(pairs, guess=False)
        self.assertEqual(len(coef), 2)
        self.assertGreater(self.m.fit_estimate(coef, 200), 260)
        self.assertGreaterEqual(self.m.fit_estimate(coef, 1), 1)
        self.assertIsNone(self.m.fit_log(pairs[:29], guess=False))

    def test_a_guess_that_knows_better_wins_the_weight(self):
        # the label is the guess and the knn never moves: c goes to about 1 (the ridge keeps it a hair
        # under: 198 with a reference run), b stays at the ridge's 0.5 (a takes the level)
        rows = [(60, g, g) for g in (10, 200) * 20]
        a, b, c = self.m.fit_log(rows)
        self.assertGreater(c, 0.9)
        self.assertAlmostEqual(b, 0.5, places=6)
        self.assertLessEqual(abs(self.m.fit_estimate((a, b, c), 60, 200) - 200), 5)


# ---------------------------------------------------------------- B6 the backtest and the winner

def fake_rows(rubric, blend, fit, repo=None, est=200, work=100):
    """Backtest rows of 10 tasks of work 100, the estimates of each method given as a list (or one number)."""
    def col(v, i):
        x = v[i] if isinstance(v, list) else v
        return (x, x, x)
    rows = []
    for i in range(10):
        rows.append({"task": {"work": work, "todo": None, "name": "t%d" % i}, "est": col(est, i),
                     "blend": col(blend, i), "repo": col(blend if repo is None else repo, i),
                     "fit": col(fit, i), "rubric": col(rubric, i), "fitted": True})
    return rows


class TestWinnerRule(unittest.TestCase):
    """Today's winner here is the rubric (60% within 30%); its spread is 0.54."""

    def setUp(self):
        self.m = load()
        self.rubric = [100] * 6 + [300] * 4

    def winner(self, rows):
        return self.m.winner_of(self.m.method_scores(rows), rows)

    def test_a_fit_between_the_blend_and_the_winner_does_not_win(self):
        # the blend is steady (spread 0.00), the fit wobbles a little (0.08): it beats the rubric, not the blend
        rows = fake_rows(self.rubric, 140, [120] * 5 + [140] * 5)
        self.assertEqual(self.winner(rows), "rubric")

    def test_a_fit_equal_to_the_blend_does_not_win(self):
        self.assertEqual(self.winner(fake_rows(self.rubric, 140, 100)), "rubric")

    def test_a_fit_below_both_wins(self):
        rows = fake_rows(self.rubric, [70] * 5 + [140] * 5, [120] * 5 + [140] * 5, repo=[60] * 5 + [150] * 5)
        self.assertEqual(self.winner(rows), "fit")

    def test_no_fitted_row_no_fit(self):
        rows = fake_rows(self.rubric, [70] * 5 + [140] * 5, 100)
        for r in rows:
            r["fitted"] = False
        self.assertEqual(self.winner(rows), "rubric")


class TestFitInBacktest(EstimateCase):

    def fit_row(self, out):
        hits = [FIT_ROW.match(l) for l in self.lines(out)]
        hits = [h for h in hits if h]
        self.assertEqual(len(hits), 1, out)
        return hits[0]

    def test_the_row_and_its_place(self):
        self.completed(alt(60, 10, 200))
        out = self.assertOk(self.af("backtest"))
        lines = self.lines(out)
        self.fit_row(out)
        at = [i for i, l in enumerate(lines) if l.startswith("blend+repo ")][0]
        self.assertTrue(lines[at + 1].startswith("fit "), lines)
        self.assertTrue([l for l in lines if l.startswith("big fit")], out)

    def test_a_guess_the_knn_cannot_see_makes_the_fit_win(self):
        # same text, works 10 and 200 in turn, the guess is right: the blend sits halfway, the fit learns c = 1
        self.completed(alt(60, 10, 200))
        out = self.assertOk(self.af("backtest"))
        self.assertIn("winner: fit", self.lines(out))
        self.assertIn("measure: 50 clean rows scored, by fit", self.lines(out))

    def test_too_few_rows_the_fit_is_the_blend(self):
        self.completed(alt(30, 10, 200))      # 20 scored rows, none has 30 rows before it
        out = self.assertOk(self.af("backtest", "--tasks"))
        for r in self.task_rows(out):
            m = re.search(r" blend (\d+) \(\d+-\d+\) blend\+repo \d+ \(\d+-\d+\) fit (\d+) \(\d+-\d+\) ", r)
            self.assertIsNotNone(m, r)
            self.assertEqual(m.group(1), m.group(2), r)
        self.assertNotIn("winner: fit", self.lines(out))

    def test_an_exact_estimator_keeps_its_win(self):
        self.completed(steady(60))
        out = self.assertOk(self.af("backtest"))
        self.assertNotIn("winner: fit", self.lines(out))


class TestFitRetrain(EstimateCase):

    def test_a_first_version_can_be_a_fit(self):
        self.completed(alt(60, 10, 200))
        self.assertOk(self.af("retrain"))
        data = self.model_json()
        ver = [v for v in data["versions"] if v["version"] == data["current"]][0]
        self.assertEqual(ver["method"], "fit")
        for key in ("weight", "repo_bias", "bias", "span"):
            self.assertIn(key, ver)

    def test_a_blend_version_moves_to_the_fit_on_a_lower_spread(self):
        self.completed(alt(60, 10, 200))
        self.model(current=1, checked=50, versions=[blend_version()], date="2026-09-01")
        out = self.assertOk(self.af("retrain", "--force"))
        data = self.model_json()
        self.assertEqual(data["current"], 2, out)
        self.assertEqual(data["versions"][-1]["method"], "fit")
        self.assertEqual(data["checks"][-1]["basis"], "backtest")

    def test_a_fit_version_stays(self):
        self.completed(alt(60, 10, 200))
        self.model(current=1, checked=50, versions=[fit_version()], date="2026-09-01")
        out = self.assertOk(self.af("retrain", "--force"))
        self.assertIn("estimate retrain: kept v1", out)
        self.assertEqual(self.model_json()["current"], 1)

    def test_a_fit_version_without_blend_keys_does_not_read(self):
        bad = fit_version()
        del bad["weight"]
        self.completed(steady(40))
        self.model(versions=[bad])
        rows = self.lines(self.assertOk(self.af("estimate", "--lane", "full", "--mock", "no", "--type", "script",
                                                "one shell script with tests")))
        self.assertIn("(rubric v0, ", rows[0])


# ---------------------------------------------------------------- B6 + B7 the estimate command

class TestEstimateWithFit(EstimateCase):

    def run_est(self, *more, what="plain work"):
        out = self.assertOk(self.af("estimate", "--lane", "full", "--mock", "no", "--type", "server", *more, what))
        return self.lines(out)

    def test_a_fit_version_uses_the_fit(self):
        self.completed(alt(60, 10, 200))
        self.model(versions=[fit_version()])
        rows = self.run_est("--guess", "200")
        m = FIRST.match(rows[0])
        self.assertIsNotNone(m, rows)
        self.assertEqual(m.group(4, 5, 6), ("fit", "1", "60"))
        f = FIT_G.match(rows[1])
        self.assertIsNotNone(f, rows)
        self.assertEqual(f.group(2), "200")
        self.assertGreater(float(f.group(5)), 0.9)        # c: the guess knows
        self.assertGreater(int(m.group(1)), 150)          # the blend would say about 60
        self.assertIsNotNone(P_LINE.match(rows[2]), rows)
        self.assertTrue(all(r.startswith("like ") for r in rows[3:]), rows)

    def test_no_guess_uses_the_fit_without_one(self):
        self.completed(alt(60, 10, 200))
        self.model(versions=[fit_version()])
        rows = self.run_est()
        self.assertIsNotNone(FIT_N.match(rows[1]), rows)
        self.assertIsNotNone(P_LINE.match(rows[2]), rows)

    def test_fewer_than_30_rows_falls_back_to_the_blend(self):
        self.completed(alt(25, 10, 200))
        self.model(versions=[fit_version()])
        rows = self.run_est("--guess", "200")
        self.assertTrue(rows[1].startswith("blend: estimator "), rows)
        self.assertIsNotNone(P_LINE.match(rows[2]), rows)


class TestP50P85(EstimateCase):

    def p_line(self, rows):
        hits = [P_LINE.match(r) for r in rows]
        hits = [h for h in hits if h]
        self.assertEqual(len(hits), 1, rows)
        return hits[0]

    def test_6_5_the_line_and_its_place(self):
        self.completed(steady(40))
        self.model(versions=[version()])
        out = self.assertOk(self.af("estimate", "--lane", "full", "--mock", "no", "--type", "script",
                                    "one shell script with tests"))
        rows = self.lines(out)
        p = P_LINE.match(rows[1])
        self.assertIsNotNone(p, rows)
        self.assertEqual(p.group(3), "30")             # the 30 scored rows of the estimator
        e = int(FIRST.match(rows[0]).group(1))
        self.assertLessEqual(int(p.group(1)), int(p.group(2)))
        self.assertGreaterEqual(int(p.group(2)), e)

    def test_after_the_guess_line(self):
        self.completed(steady(40))
        self.model(versions=[version()])
        rows = self.lines(self.assertOk(self.af("estimate", "--lane", "full", "--mock", "no", "--type", "script",
                                                "--guess", "35", "one shell script with tests")))
        self.assertEqual(rows[1], "guess: 35m, not used: v1 is estimator")
        self.assertIsNotNone(P_LINE.match(rows[2]), rows)

    def test_a_steady_overrun_moves_p50_up(self):
        # every task ran twice the rubric middle: p50 = 2 x the rubric estimate, from the history
        rows = []
        for i in range(30):
            rows.append(row(day(i), "s-%02d" % i, "one shell script with tests", type="script", lane="full",
                            mock="no", work=106, wait=0, clock=106))
        self.completed(rows)
        out = self.assertOk(self.af("estimate", "--lane", "full", "--mock", "no", "--type", "script",
                                    "one shell script with tests"))
        lines = self.lines(out)
        self.assertIn("(rubric v0, 30 past tasks)", lines[0])
        p = self.p_line(lines)
        self.assertEqual((p.group(1), p.group(2), p.group(3)), ("106", "106", "20"))

    def test_too_few_errors_take_the_range(self):
        self.completed(steady(15))                     # 5 scored rows
        self.model(versions=[version()])
        out = self.assertOk(self.af("estimate", "--lane", "full", "--mock", "no", "--type", "script",
                                    "one shell script with tests"))
        rows = self.lines(out)
        m = FIRST.match(rows[0])
        p = self.p_line(rows)
        self.assertEqual((p.group(1), p.group(2), p.group(3)), (m.group(1), m.group(3), "5"))

    def test_6_5_the_p85_statement_holds_80_to_90_percent(self):
        self.completed(varied(80, seed=3))
        out = self.assertOk(self.af("backtest"))
        hits = [re.match(r"^measure p85: n (\d+) holds (\d+)%$", l) for l in self.lines(out)]
        hits = [h for h in hits if h]
        self.assertEqual(len(hits), 1, out)
        self.assertGreaterEqual(int(hits[0].group(2)), 80, out)
        self.assertLessEqual(int(hits[0].group(2)), 90, out)


if __name__ == "__main__":
    unittest.main()
