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


# ---------------------------------------------------------------- todo add / todo done


# ---------------------------------------------------------------- estimate --guess


# ---------------------------------------------------------------- backtest


# ---------------------------------------------------------------- retrain


# ---------------------------------------------------------------- config


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
        self.assertIn("--guess", read("PRINCIPLES.md"))
        head = read("bin", "agent-file.sh").split("\nset -eu")[0]
        for word in ("--guess", "guess=", "warning"):
            with self.subTest(word=word):
                self.assertIn(word, head)

    def test_the_release(self):
        ver = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        self.assertGreaterEqual(tuple(int(x) for x in ver.split(".")), (0, 34, 0))


if __name__ == "__main__":
    unittest.main()
