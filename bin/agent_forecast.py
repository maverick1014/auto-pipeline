#!/usr/bin/env python3
"""agent_forecast.py - the end time of a running task by Monte Carlo (requirements/estimate-improve.md, section 5C).
Python 3.9, standard library only. The board, `eta` and the backtest all call forecast(), so they give one answer.

    history(root)                              rows of the clean lines of <root>/agent_completed.txt
    forecast(task, rows, draws, seed)          (p50, p85) minutes still to go, or None (too little history)
    slices_end(plans, ratios, draws, seed)     (p50, p85) of the max over parallel slices

The rules are the docstring of tests/test_agent_forecast.py.
"""

import math
import os
import random
import re
import sys

FORECAST_MIN_ROWS = 10
ES_MIN = 0.2
DRAWS = 10000
SEED = 26
BUILD = ("brief", "register", "mock", "tests", "workers", "verify", "push")
TAIL = ("report", "e2e", "merge")
STAGES = BUILD + TAIL
MAX_CLOCK = 1440


def whole(text):
    return int(text) if text is not None and re.fullmatch(r"[0-9]+", text) else None


def fix_round(built, stages):
    """requirements/board-eta.md: the past fix round of a row = its BUILD-stage minutes minus built, when more than 0."""
    if built is None or not stages:
        return None
    f = sum(stages.get(s, 0) for s in BUILD) - built
    return f if f > 0 else None


def history(root):
    """The clean rows (clock a number, work <= clock <= 1440; the wait may be missing) of agent_completed.txt, in file order."""
    path = os.path.join(root, "agent_completed.txt")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        if " | data " not in line:
            continue
        d = {}
        for w in line.split(" | data ", 1)[1].split():
            if "=" in w:
                k, v = w.split("=", 1)
                d.setdefault(k, v)
        work, wait, clock = whole(d.get("work")), whole(d.get("wait")), whole(d.get("clock"))
        if work is None or clock is None or work > clock or (clock if wait is None else max(0, clock - wait)) > MAX_CLOCK:
            continue
        est0, est, built = whole(d.get("est0")), whole(d.get("est")), whole(d.get("built"))
        stages = {}
        raw = d.get("stages", "-")
        if raw != "-":
            for part in raw.split(","):
                name, _, m = part.partition(":")
                if name and whole(m) is not None:
                    stages[name] = whole(m)
        slices = []
        raw = d.get("slices", "-")
        if raw != "-":
            slices = [whole(x) for x in raw.split(",") if whole(x) is not None]
        rows.append({
            "est": est0 if est0 is not None else est,
            "label": built if built is not None else work,
            "tail": (max(0, work - built) if built is not None
                     else max(0, clock - wait - work) if wait is not None else None),
            "lane": "fast" if d.get("lane") == "fast" else "full",
            "built": built, "stages": stages, "slices": slices,
            "fix": fix_round(built, stages),
        })
    return rows


def stage_weights():
    """{stage: weight} from the stage_* constants of agent_conf, the way the board reads them; bad: 0."""
    here = os.path.dirname(os.path.abspath(__file__))
    weights = dict((s, 0) for s in STAGES)
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        if here not in sys.path:
            sys.path.insert(0, here)
        import agent_conf
        for s in STAGES:
            v = agent_conf.get("stage_" + s)
            weights[s] = v if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100 else 0
    except Exception:
        pass
    finally:
        sys.dont_write_bytecode = old
    return weights


def percentile(values, q):
    """The q (0..1) percentile, linear, of a sorted list."""
    n = len(values)
    if n == 1:
        return values[0]
    at = (n - 1) * q
    lo = int(math.floor(at))
    hi = min(n - 1, lo + 1)
    return values[lo] + (values[hi] - values[lo]) * (at - lo)


def up(x):
    return max(0, int(math.ceil(x - 1e-9)))


def first_over(values, edge):
    """Index of the first value of a sorted list that is more than edge (len when none)."""
    for i, v in enumerate(values):
        if v > edge:
            return i
    return len(values)


def forecast(task, rows, draws=DRAWS, seed=SEED):
    est, work = task.get("est"), task.get("work")
    if est is None or work is None:
        return None
    lane = task.get("lane") or "full"
    # requirements/board-eta.md: a task past report or e2e (built_work) and again in a BUILD stage is in a fix round
    stage = task.get("stage")
    name, i, m = stage if stage else (None, None, None)
    built_work, round_at = task.get("built_work"), task.get("round_at")
    fix = built_work is not None and name in BUILD and round_at is not None
    if fix:
        age = max(0, work - round_at)
        past = sorted(r["fix"] for r in rows if r.get("fix"))
        added = task.get("added")
        if len(past) >= 5 or added:
            if len(past) >= 5:
                k = first_over(past, age)
                rnd = random.Random(seed).random
                left = sorted(past[k + int(rnd() * (len(past) - k))] - age if k < len(past) else 1
                              for _ in range(draws))
            else:
                left = [max(1, added - age)]
            return up(percentile(left, 0.5)), up(percentile(left, 0.85))
    ok = [r for r in rows if r.get("est") and r["est"] > 0 and r.get("label") is not None]
    pool = [r for r in ok if r.get("lane") == lane]
    if len(pool) < FORECAST_MIN_ROWS:
        pool = ok
    if len(pool) < FORECAST_MIN_ROWS:
        return None
    qs = sorted(r["label"] / float(r["est"]) for r in pool)
    ts = sorted(r["tail"] for r in pool if r.get("tail") is not None) or [0]
    nq, nt = len(qs), len(ts)
    p = task.get("p")
    pace = p is not None and p >= ES_MIN
    rnd = random.Random(seed).random
    left = []
    if name in TAIL or fix:     # a fix round with too little history: the tail path, no step share
        age = max(0, work - built_work) if built_work is not None else 0
        k = first_over(ts, age)
        for _ in range(draws):
            if k < nt:
                left.append(ts[k + int(rnd() * (nt - k))] - age)
            else:
                left.append(1)      # past every past tail: due any minute, never a jump up with age
    else:
        k = first_over([est * q for q in qs], work)
        es_total = work / p if pace else None
        plan, open_slices = 0.0, 0
        if name == "workers" and m is not None and i is not None and m - i >= 1:
            weights = stage_weights()
            total_w = sum(weights.values())
            if total_w > 0:
                plan = est * weights["workers"] / float(total_w) / m
                open_slices = m - i
        for _ in range(draws):
            total = est * qs[int(rnd() * nq)]
            if total <= work:
                if k < nq:
                    total = est * qs[k + int(rnd() * (nq - k))]
                else:
                    total = work + max(1.0, est * (1 - (p or 0.0)))
            if es_total is not None:
                total = max(total, es_total)
            build = max(0.0, total - work)
            if open_slices:
                longest = 0.0
                for _s in range(open_slices):
                    longest = max(longest, plan * qs[int(rnd() * nq)])
                build = max(build, longest)
            left.append(build + ts[int(rnd() * nt)])
    left.sort()
    return up(percentile(left, 0.5)), up(percentile(left, 0.85))


def slices_end(plans, ratios, draws=DRAWS, seed=SEED):
    """(p50, p85) minutes: max over j of plans[j] x a draw of the ratios, rounded up."""
    rnd = random.Random(seed).random
    n = len(ratios)
    out = []
    for _ in range(draws):
        out.append(max(plan * ratios[int(rnd() * n)] for plan in plans))
    out.sort()
    return up(percentile(out, 0.5)), up(percentile(out, 0.85))
