"""Tests for estimator v3, the blend (task estimate-blend). Read requirements/estimate.md.

WHY (owner, 2026-11-13): "for the estimate time skill, so far used until now,
got any data for you to improve?" -> shown the laptop backtest -> "can improve
also". On 178 tasks the v2 estimator is within 30% on 30% of them, the
manager's own todo est on 35%, the blend sqrt(estimator x manager guess) on
39% (error 17.6m), the blend times a per-repo bias has error 16.4m. Big tasks
(work >= 120m) are badly under-estimated: the range never goes far over 100m.

CONTRACT (all through bin/agent-file.sh; the estimator work is in bin/agent_estimate.py)

    todo add "<name>" "<size>" "<what>" [est_minutes] [by] [--guess <m>]
        --guess may stand anywhere after "todo add"; the other arguments keep
        their order. The line gets the field " | guess <m>m" right after the est
        field (no est: right after the what):
            <name> | <size> | <what> | est <e>m | guess <g>m | opened <date> | by <by>
        <m> = a whole number, 1 or more. Else, or no value: refused, one line
        on stderr naming --guess, exit 1, nothing written.

    todo done
        The data block gets one more key, the last: guess=<m> from the todo
        line's field "guess <m>m", else guess=-. Old lines (no guess key) read
        as "-".
        No --type or no --lane: one warning line on stderr, exit 0, the line
        moves as before:
            todo done: warning: no --type given (the estimator learns less from this line)
            todo done: warning: no --lane given (...)
            todo done: warning: no --type --lane given (...)

    data [--what]
        One more column, guess, after adds (before what).

    estimate --lane .. --mock .. --type .. [--name ..] [--guess <m>] "<what>"
        --guess: a whole number, 1 or more; else refused (one line naming --guess).
        Current version method "blend", with --guess:
            estimate: <m>m work, range <lo>-<hi>m (blend v<n>, <N> past tasks)
            blend: estimator <e>m, guess <g>m, weight <w>, repo <repo> x<f>
            like ...                       (as before)
          e = the estimator with the version's k, text, type (as v2)
          b = max(1, half_up(e^(1-w) x g^w))           w = the version's weight
          f = bias[<repo>] when repo_bias is true and the repo is in bias, else 1
              <repo> = the folder name of this project (the repo of the data)
          m = max(1, half_up(b x f)); lo, hi = half_up(m x span[0]), half_up(m x span[1]),
              then 1 <= lo <= m <= hi. <w> like 0.5 or 0.25, <f> two decimals.
        Current version blend, no --guess: the estimator, exactly as an
          estimator version ("estimator v<n>", the estimator's range), no blend line.
        Any other version (estimator, rubric, no file = v0) with --guess: the
          lines as without --guess, the second line being
            guess: <g>m, not used: v<n> is <estimator|rubric>

    backtest [--tasks]
        The guess of a task = its guess, else its todo est (old lines), else none.
        Rows: estimator, blend, blend+repo, rubric, todo est; then the line
            work >= <big>m: <n> tasks                  big = estimate_big_min (120)
        and the same 5 rows named "big <method>" over only those tasks; then
        "winner: ..."; the target line last. A row with 0 tasks, in both
        tables, is "<method> 0 - - -" as before. The todo est row is the est of
        the todo line only (info, as before), never the guess.
        --tasks rows:
            task <name> work <w> guess <g|-> estimator <e> (<lo>-<hi>) blend <b> (<lo>-<hi>) blend+repo <c> (<lo>-<hi>) rubric <r>
        Each task only from the tasks before it (rolling), also the weight,
        the bias and the ranges, so a row never changes when later tasks come.
        A task with no guess: blend and blend+repo are the estimator, number and
          range (so a bias alone never wins). A task with a guess:
        blend b = max(1, half_up(e^(1-w) x g^w)).
          w: from the tested tasks before it that have a guess; fewer than 10 ->
          0.5; else 0.25 or 0.75 (the one with more within 30%, a tie -> lower
          median error, then 0.25) only on a clear win over 0.5: more within 30%
          AND a lower median error. Else 0.5.
        blend+repo c = max(1, half_up(b x f)); f = median of work / b over the
          tested tasks before it of the same repo that have a guess, when there
          are at least estimate_bias_min (5) of them, else 1. The b of those
          earlier tasks is taken at this task's weight w.
        Range of blend and blend+repo: the 20th and 80th percentile of that
          method's own work / estimate over the tested tasks before it that have
          a guess, when at least 10; else the estimator's (leave-one-out) ratios;
          times the method's estimate, half up, 1 <= lo <= est <= hi.
        winner: base = estimator when its median error is strictly lower than
          the rubric's, else rubric (as before). best blend = blend+repo when it
          has more within 30% than blend, or the same and a lower median error;
          else blend. winner = the best blend when its within 30% is strictly
          higher than base's; else base.
        Target line, last (the "target 5m" line is gone):
            target within 30% <goal>%: <p>%, gap <goal - p> points
            target within 30% <goal>%: met (<p>%)
          p = the winner row's within 30%, goal = estimate_target_pct (50).

    retrain
        A new version takes the winner's method: estimator, rubric, or blend
        (winner blend or blend+repo). A blend version also keeps:
          weight     the w rule above over every tested task with a guess
          repo_bias  true when the winner is blend+repo
          bias       {repo: median work / b, 2 decimals} over the tested tasks
                     with a guess of each repo with at least estimate_bias_min
                     of them, b with this weight; {} when repo_bias is false
          span       [20th, 80th percentile of work / final estimate] over every
                     tested task with a guess, 3 decimals (final = with the
                     bias when repo_bias)
        A blend version reads only when: weight a number, 0 < weight < 1;
        repo_bias true or false; bias an object of numbers > 0; span two numbers
        > 0, the first <= the second. Else the file does not read (v0).
          backtest   also "blend" and "blend_repo": {error, within30, inrange}
        v1 verdict: estimate retrain: v1 made from <N> tasks: blend (weight <w>, repo bias on|off; ...)
        A check where the new method is blend and the current is not: the
        backtest decides (owner brief item 8): kept new only when the winner's
        within 30% is strictly higher than the row of the current's method:
            estimate retrain: kept v<n> (backtest on <T> tasks, within 30%: <winner> <a>%, <method> v<c> <b>%)
          the check gets "basis": "backtest". Every other check: the old rule on
          the new tasks (strictly lower median error), "basis": "new tasks".
        The target line follows the verdict (within 30% share of the kept version).

    agent.conf (group "estimate", after statusline_refresh_sec in the template)
        estimate_target_pct=50   (1 to 100)
        estimate_bias_min=5      (1 to 1000)
        estimate_big_min=120     (1 to 10000)
"""

import importlib.util
import json
import os
import re
import unittest

from tests.scripthelp import BIN, ROOT
from tests.test_agent_estimate import (KEYS, NOW, TODAY, EstimateCase, day, line, steady,
                                       varied, version)

KEYS3 = KEYS + ["guess"]

BLEND_LINE = re.compile(
    r"^estimate: (\d+)m work, range (\d+)-(\d+)m \(blend v(\d+), (\d+) past tasks\)$")
BLEND_WHY = re.compile(
    r"^blend: estimator (\d+)m, guess (\d+)m, weight ([0-9.]+), repo (\S+) x(\d+\.\d\d)$")
TASK_ROW3 = re.compile(
    r"^task (\S+) work (\d+) guess (\d+|-) estimator (\d+) \((\d+)-(\d+)\) "
    r"blend (\d+) \((\d+)-(\d+)\) blend\+repo (\d+) \((\d+)-(\d+)\) rubric (\d+)$")
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


# ---------------------------------------------------------------- todo add / todo done

class TestTodoGuess(BlendCase):

    def todo_text(self):
        return self.repo.read("agent_todo.txt")

    def test_todo_add_keeps_the_guess_after_est(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70", "--guess", "35"))
        self.assertEqual(self.todo_text(),
                         "t1 | big | build it | est 70m | guess 35m | opened %s | by main\n" % NOW)

    def test_the_guess_may_stand_anywhere(self):
        for args in (("--guess", "35", "t1", "big", "build it", "70"),
                     ("t1", "--guess", "35", "big", "build it", "70"),
                     ("t1", "big", "build it", "70", "--guess", "35")):
            with self.subTest(args=args):
                self.write("agent_todo.txt", "")
                self.assertOk(self.af("todo", "add", *args))
                self.assertEqual(self.todo_text(),
                                 "t1 | big | build it | est 70m | guess 35m | opened %s | by main\n" % NOW)

    def test_by_still_works(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70", "laptop", "--guess", "35"))
        self.assertEqual(self.todo_text(),
                         "t1 | big | build it | est 70m | guess 35m | opened %s | by laptop\n" % NOW)

    def test_a_guess_with_no_est(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "--guess", "35"))
        self.assertEqual(self.todo_text(),
                         "t1 | big | build it | guess 35m | opened %s | by main\n" % NOW)

    def test_no_guess_is_the_line_as_before(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70"))
        self.assertEqual(self.todo_text(), "t1 | big | build it | est 70m | opened %s | by main\n" % NOW)

    def test_a_bad_guess_is_refused(self):
        self.write("agent_todo.txt", "keep | big | x | est 5m | opened %s | by main\n" % NOW)
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
        self.write("agent_todo.txt", "t1 | big | build it | est 70m | guess 35m | opened 2026-10-05 15:00 | by main\n")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertEqual(self.done_line(), "%s | t1 | build it | %s" % (TODAY, gblock(
            repo="project", type="script", lane="full", est=70, work=60, clock=60, guess=35)))

    def test_todo_done_with_no_guess_writes_a_dash(self):
        self.write("agent_todo.txt", "t1 | big | build it | est 70m | opened 2026-10-05 15:00 | by main\n")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertTrue(self.done_line().endswith(" adds=- guess=-"), self.done_line())

    def test_a_guess_word_in_the_what_is_not_the_guess(self):
        self.write("agent_todo.txt", "t1 | big | guess 99m is a word here | est 70m | opened 2026-10-05 15:00 | by main\n")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertTrue(self.done_line().endswith(" guess=-"), self.done_line())

    def test_the_warning_names_the_missing_facts(self):
        for opts, want in ((("--type", "script", "--lane", "full"), None),
                           (("--lane", "full"), "todo done: warning: no --type" + WARN_TAIL),
                           (("--type", "script"), "todo done: warning: no --lane" + WARN_TAIL),
                           ((), "todo done: warning: no --type --lane" + WARN_TAIL)):
            with self.subTest(opts=opts):
                self.write("agent_todo.txt", "t1 | big | build it | est 70m | opened 2026-10-05 15:00 | by main\n")
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
        rows = [r.split() for r in self.lines(self.assertOk(self.af("data", "--what")))]
        self.assertEqual(rows[0][-3:], ["adds", "guess", "what"])
        self.assertEqual(rows[1][-4:], ["35", "has", "a", "guess"])
        self.assertEqual(rows[2][-5:], ["-", "an", "old", "data", "line"])


# ---------------------------------------------------------------- estimate --guess

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


# ---------------------------------------------------------------- backtest

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

    def test_the_big_line_follows_the_config(self):
        self.completed(steady(40))
        self.repo.set_conf("estimate_big_min", "50")
        rows = self.lines(self.assertOk(self.af("backtest")))
        self.assertIn("work >= 50m: 15 tasks", rows)
        self.repo.set_conf("estimate_big_min", "500")
        out = self.assertOk(self.af("backtest"))
        self.assertIn("work >= 500m: 0 tasks", self.lines(out))
        self.assertEqual(len(self.zero_rows(out)), 5, out)

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

    def test_the_bias_count_follows_the_config(self):
        self.completed(two_repos(40))
        self.repo.set_conf("estimate_bias_min", "3")
        shop = [m for m in self.rows3(self.assertOk(self.af("backtest", "--tasks"))) if m.group(2) == "100"]
        self.assertEqual([m.group(10) == m.group(7) for m in shop][:4], [True, True, True, False])
        self.repo.set_conf("estimate_bias_min", "1000")
        out = self.assertOk(self.af("backtest", "--tasks"))
        for m in self.rows3(out):
            self.assertEqual(m.group(10), m.group(7), m.group(0))
        self.assertNotEqual(self.winner(out), "blend+repo")

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
        self.repo.set_conf("estimate_target_pct", "1")
        self.assertEqual(self.lines(self.assertOk(self.af("backtest")))[-1],
                         "target within 30% 1%: met ({}%)".format(p) if p >= 1 else
                         "target within 30% 1%: 0%, gap 1 points")
        self.repo.set_conf("estimate_target_pct", "100")
        last = self.lines(self.assertOk(self.af("backtest")))[-1]
        self.assertEqual(last, "target within 30% 100%: met (100%)" if p == 100 else
                         "target within 30% 100%: {}%, gap {} points".format(p, 100 - p))


# ---------------------------------------------------------------- retrain

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


# ---------------------------------------------------------------- config

def load_conf_module():
    spec = importlib.util.spec_from_file_location("agent_conf_blend", os.path.join(BIN, "agent_conf.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEstimateConf(unittest.TestCase):

    KEYS = {"estimate_target_pct": ("50", 1, 100), "estimate_bias_min": ("5", 1, 1000),
            "estimate_big_min": ("120", 1, 10000)}

    def setUp(self):
        self.ac = load_conf_module()

    def test_bounds_hints_and_group(self):
        for key, (_, low, high) in self.KEYS.items():
            with self.subTest(key=key):
                self.assertIsNone(self.ac.validate_value(key, str(low)))
                self.assertIsNone(self.ac.validate_value(key, str(high)))
                self.assertTrue(self.ac.validate_value(key, str(low - 1)))
                self.assertTrue(self.ac.validate_value(key, str(high + 1)))
                self.assertTrue(self.ac.HINTS.get(key, "").strip())
                self.assertEqual(self.ac.group_of(key), "estimate")
        self.assertEqual(dict(self.ac.GROUPS)["estimate"],
                         ["estimate_target_pct", "estimate_bias_min", "estimate_big_min"])

    def test_template_defaults_after_the_status_line_key(self):
        with open(os.path.join(BIN, "agent.conf.default")) as fh:
            keys = [l.split("=", 1)[0] for l in fh.read().splitlines() if "=" in l]
        conf = self.ac.load(os.path.join(BIN, "agent.conf.default"))
        for key, (default, _, _) in self.KEYS.items():
            self.assertEqual(conf.get(key), default, key)
        at = keys.index("statusline_refresh_sec")
        self.assertEqual(keys[at + 1:at + 4], ["estimate_target_pct", "estimate_bias_min", "estimate_big_min"])


# ---------------------------------------------------------------- wired in

def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def section(text, start, end):
    a = text.index(start)
    return text[a:text.index(end, a)]


class TestWiredInBlend(unittest.TestCase):

    def test_the_dispatch_step_writes_the_guess_first(self):
        skill = read("skills", "dispatch", "SKILL.md")
        step1 = section(skill, "\n1. ", "\n2. ")
        self.assertIn("--guess", step1)
        self.assertLess(step1.index("guess"), step1.index("agent-file.sh estimate"), step1)
        add = [l for l in skill.splitlines() if "agent-file.sh todo add" in l]
        self.assertTrue(add, "the skill shows the todo add line")
        self.assertTrue(all("--guess" in l for l in add), add)

    def test_the_time_rules_name_the_guess(self):
        w11 = section(read("PRINCIPLES.md"), "W11. Time", "W12.")
        self.assertIn("--guess", w11)

    def test_the_readme_and_the_usage_name_the_guess(self):
        self.assertIn("--guess", read("README.md"))
        head = read("bin", "agent-file.sh").split("\nset -eu")[0]
        for word in ("--guess", "guess=", "warning"):
            with self.subTest(word=word):
                self.assertIn(word, head)

    def test_the_release(self):
        ver = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        self.assertGreaterEqual(tuple(int(x) for x in ver.split(".")), (0, 34, 0))


if __name__ == "__main__":
    unittest.main()
