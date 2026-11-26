#!/usr/bin/env python3
"""agent_estimate.py - the time estimator behind bin/agent-file.sh (estimate, backtest, retrain).

Read requirements/estimate.md. Python 3.9, standard library only.

    agent_estimate.py <estimate|backtest|retrain> <model file> <today> [options] < rows

rows = the table of `agent-file.sh data --what` on stdin (header row first).
model file = agent_estimate.txt in the project root (JSON). today = YYYY-MM-DD.
An estimate = agent WORK minutes. Nearest past tasks: lane pool, then likeness
(mock, type, text), the geometric mean of the k nearest, a range from the
leave-one-out errors. Training = picking k, text, type by leave-one-out error.
"""

import datetime
import json
import math
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MIN_TASKS = 30        # tasks needed for the first version
RETRAIN_EVERY = 10    # finished clean tasks between two checks
TARGET_PCT = 50       # owner target: share of tasks within 30% of the work (estimate_target_pct)
BIAS_MIN = 5          # tasks of one repo needed for its bias (estimate_bias_min)
BIG_MIN = 120         # work minutes from which a task is big (estimate_big_min)
MIN_GUESSED = 10      # tested tasks with a guess needed to move the weight or own ranges
WEIGHTS = (0.25, 0.75)
MIN_BEFORE = 10       # tasks before a task, to backtest it
MAX_CLOCK = 1440      # a clean row ran one day or less (minutes from opened to done)
MIN_TAIL = 5          # clean rows of one lane needed for the median tail of the end measure
TYPES = ("page", "server", "script", "docs", "cloud", "app", "data", "mixed")
AFTER_FACTS = ("--work", "--wait", "--clock", "--est", "--bounces", "--workers",
               "--files", "--lines", "--tests", "--adds")
MIN_FIT_ROWS = 30    # rows needed for the log fit
FIT_RIDGE = 1.0      # the ridge that pulls the fit toward the blend
BLEND_ROWS = ("estimator", "blend", "blend+repo", "fit", "rubric", "todo est")
KEYS = {"estimator": "est", "blend": "blend", "blend+repo": "repo", "fit": "fit", "rubric": "rubric"}
# k first, then text, then type, each smallest first
GRID = [(k, text, kind) for k in (3, 5, 7) for text in (0, 1) for kind in (0, 0.5)]
DEFAULT = (3, 1, 0.5)   # the setting of the like lines when there is no file
WORD = re.compile(r"[a-z0-9]{3,}")


def refuse(text):
    sys.stderr.write(text + "\n")
    sys.exit(1)


def env_int(name, default, low, high):
    raw = os.environ.get(name, "")
    if re.fullmatch(r"[0-9]+", raw or ""):
        v = int(raw)
        if low <= v <= high:
            return v
    return default


# ---------------------------------------------------------------- the data

def whole(text):
    """The whole number of a table cell, else None."""
    return int(text) if re.fullmatch(r"[0-9]+", text) else None


def read_tasks(stream):
    """The finished tasks with a whole-number work, in finish order.

    The table: repo name date type lane mock est work wait clock bounces workers files lines tests adds
    guess est0 typed built stages slices what. "work" of a task is its LABEL: built when known, else
    the work; "rawwork", "clock" and "wait" are the numbers of the row, "clean" says a learner may use it.
    """
    rows = stream.read().splitlines()[1:]
    tasks = []
    for row in rows:
        f = row.split(None, 22)
        if len(f) < 17 or not re.fullmatch(r"[0-9]+", f[7]):
            continue
        what = f[22] if len(f) > 22 and f[22] != "-" else ""
        est = int(f[6]) if re.fullmatch(r"[0-9]+", f[6]) else None
        raw = f[16] if len(f) > 16 else "-"
        own = int(raw) if re.fullmatch(r"[0-9]+", raw) and int(raw) >= 1 else None
        built = whole(f[19]) if len(f) > 19 else None
        est0 = whole(f[17]) if len(f) > 17 else None
        stages = {}
        for part in (f[20].split(",") if len(f) > 20 and f[20] != "-" else []):
            sn, _, sm = part.partition(":")
            if sn and whole(sm) is not None:
                stages[sn] = int(sm)
        rawwork, wait, clock = int(f[7]), whole(f[8]), whole(f[9])
        words = {}
        for w in WORD.findall((f[1] + " " + what).lower()):
            words[w] = words.get(w, 0) + 1
        tasks.append({
            "name": f[1], "date": f[2], "type": f[3],
            "lane": "fast" if f[4] == "fast" else "full",
            "mock": "yes" if f[5] == "yes" else "no",
            "est": est, "work": rawwork if built is None else built, "rawwork": rawwork,
            "est0": est0, "built": built, "stages": stages,
            "wait": wait, "clock": clock, "words": words, "repo": f[0],
            "clean": wait is not None and clock is not None and rawwork <= clock and clock <= MAX_CLOCK,
            "guess": own if own is not None else (est if est is not None and est >= 1 else None),      # its guess, else its todo est
            "todo": est,                                   # the est of the todo line only
        })
    tasks.sort(key=lambda t: t["date"])          # stable: the table order breaks ties
    for i, t in enumerate(tasks):
        t["pos"] = i
    return tasks


def learnable(tasks):
    """The clean rows only (clock and wait are numbers, work <= clock <= one day), numbered again."""
    out = [t for t in tasks if t["clean"]]
    for i, t in enumerate(out):
        t["pos"] = i
    return out


def half_up(x):
    return int(math.floor(x + 0.5))


def percent(part, whole):
    """A whole percent, half up."""
    return (200 * part + whole) // (2 * whole)


# ---------------------------------------------------------------- the method

class Ctx(object):
    """The past tasks and the task being estimated, with one set of word weights.

    N and df count the past tasks plus the target (just the past tasks when
    there is no target). The weights are made once; the leave-one-out runs
    (setting pick, range) reuse them.
    """

    def __init__(self, past, target):
        self.past = past
        self.target = target
        play = list(past) + ([target] if target is not None else [])
        df = {}
        for t in play:
            for w in t["words"]:
                df[w] = df.get(w, 0) + 1
        n = len(play)
        self.idf = dict((w, math.log((n + 1.0) / (c + 1)) + 1) for w, c in df.items())
        self._vec = {}
        self._cos = {}
        self._rank = {}
        self._loo = {}
        self._pick = None

    def vec(self, t):
        v = self._vec.get(t["pos"])
        if v is None:
            raw = [(w, c * self.idf[w]) for w, c in sorted(t["words"].items())]
            norm = math.sqrt(sum(x * x for _, x in raw))
            items = [(w, x / norm) for w, x in raw] if norm else []
            v = self._vec[t["pos"]] = (items, dict(items))
        return v

    def cosine(self, a, b):
        key = (a["pos"], b["pos"])
        c = self._cos.get(key)
        if c is None:
            other = self.vec(b)[1]
            c = 0.0
            for w, x in self.vec(a)[0]:
                y = other.get(w)
                if y:
                    c += x * y
            self._cos[key] = c
        return c

    def rank(self, target, text_w, type_w):
        """The past tasks (but the target itself) most alike first, newer first on a tie."""
        key = (target["pos"], text_w, type_w)
        order = self._rank.get(key)
        if order is None:
            others = [t for t in self.past if t is not target]
            pool = [t for t in others if t["lane"] == target["lane"]] or others
            known = target["type"] != "-"
            scored = []
            for t in pool:
                like = (1 if t["mock"] == target["mock"] else 0) \
                    + type_w * (1 if known and t["type"] == target["type"] else 0)
                if text_w:
                    like = like + text_w * self.cosine(target, t)
                scored.append((-like, -t["pos"], t))
            scored.sort(key=lambda s: (s[0], s[1]))
            order = self._rank[key] = [s[2] for s in scored]
        return order

    def estimate(self, target, setting):
        """The geometric mean of the k nearest past tasks, whole minutes, at least 1."""
        k, text_w, type_w = setting
        near = self.rank(target, text_w, type_w)[:k]
        if not near:
            return None
        return geo(near)

    def loo(self, setting):
        """[(task, whole-minute estimate from all the other past tasks)]."""
        got = self._loo.get(setting)
        if got is None:
            got = self._loo[setting] = []
            for t in self.past:
                if len(self.past) > 1:
                    got.append((t, self.estimate(t, setting)))
        return got

    def pick(self):
        """The setting with the lowest median leave-one-out error (see GRID for ties)."""
        if self._pick is None:
            best, best_key = GRID[0], None
            for setting in GRID:
                errs = [abs(e - t["work"]) for t, e in self.loo(setting)]
                if not errs:
                    continue
                key = (statistics.median(errs), sum(errs))   # same count: the sum orders the means
                if best_key is None or key < best_key:
                    best, best_key = setting, key
            self._pick = best
        return self._pick

    def span(self, setting, est):
        """The range: the 20th and 80th percentile of actual / estimate, leave one out."""
        ratios = sorted(t["work"] / float(e) for t, e in self.loo(setting))
        if not ratios:
            return est, est
        low = half_up(est * percentile(ratios, 0.2))
        high = half_up(est * percentile(ratios, 0.8))
        return max(1, min(low, est)), max(high, est)


def geo(near):
    logs = sum(math.log(max(t["work"], 1)) for t in near)
    return max(1, half_up(math.exp(logs / len(near))))


def percentile(sorted_values, p):
    pos = p * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def rubric(t):
    """(middle, low, high) of today's rubric row for a task or a target."""
    if t["lane"] == "fast":
        lo, hi = 5, 15
    elif t["mock"] == "yes":
        lo, hi = 60, 90
    elif t["type"] == "script":
        lo, hi = 45, 60
    else:
        lo, hi = 90, 120
    return (lo + hi + 1) // 2, lo, hi


def ratios_of(ctx, setting):
    return sorted(t["work"] / float(e) for t, e in ctx.loo(setting))


def span_of(ratios, est):
    """(low, high) of est from sorted work / estimate ratios: 1 <= low <= est <= high."""
    if not ratios:
        return est, est
    low = half_up(est * percentile(ratios, 0.2))
    high = half_up(est * percentile(ratios, 0.8))
    return max(1, min(low, est)), max(high, est)


def estimator_row(tasks, i, done):
    """Task i estimated only from the tasks before it: (estimate, low, high, setting)."""
    row = done.get(i)
    if row is None:
        ctx = Ctx(tasks[:i], tasks[i])
        setting = ctx.pick()
        est = ctx.estimate(tasks[i], setting)
        if est is None:
            mid, lo, hi = rubric(tasks[i])
            row = (mid, lo, hi, setting)
            done[("ratios", i)] = []
        else:
            done[("ratios", i)] = ratios_of(ctx, setting)
            lo, hi = span_of(done[("ratios", i)], est)
            row = (est, lo, hi, setting)
        done[i] = row
    return row


# ---------------------------------------------------------------- the blend

def blend_est(e, g, w):
    """e^(1-w) x g^w, a whole minute, at least 1."""
    return max(1, half_up(math.exp((1 - w) * math.log(e) + w * math.log(g))))


def final_est(b, f):
    return max(1, half_up(b * f))


def weight_stats(triples, w):
    errs = [abs(blend_est(e, g, w) - work) for e, g, work in triples]
    within = sum(1 for (e, g, work), x in zip(triples, errs) if x <= 0.3 * work)
    return within, float(statistics.median(errs))


def pick_weight(triples):
    """(estimator, guess, work) of the earlier tested tasks with a guess -> 0.5, 0.25 or 0.75."""
    if len(triples) < MIN_GUESSED:
        return 0.5
    base = weight_stats(triples, 0.5)
    best, best_key = None, None
    for w in WEIGHTS:                    # 0.25 first: it wins a full tie
        within, err = weight_stats(triples, w)
        key = (-within, err)
        if best_key is None or key < best_key:
            best, best_key = w, key
    within, err = weight_stats(triples, best)
    if within > base[0] and err < base[1]:
        return best
    return 0.5


def bias_of(rows, repo, w, bias_min):
    """Median work / b over the rows (with a guess) of one repo, 1.0 when fewer than bias_min."""
    same = [r for r in rows if r["task"]["repo"] == repo]
    if len(same) < bias_min:
        return None
    return float(statistics.median(
        r["task"]["work"] / float(blend_est(r["est"][0], r["guess"], w)) for r in same))


def solve(a, rhs):
    """Gaussian elimination with partial pivoting; None when singular."""
    n = len(rhs)
    m = [list(a[i]) + [rhs[i]] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[piv][c]) < 1e-12:
            return None
        m[c], m[piv] = m[piv], m[c]
        for r in range(c + 1, n):
            f = m[r][c] / m[c][c]
            for j in range(c, n + 1):
                m[r][j] -= f * m[c][j]
    out = [0.0] * n
    for r in range(n - 1, -1, -1):
        out[r] = (m[r][n] - sum(m[r][j] * out[j] for j in range(r + 1, n))) / m[r][r]
    return out


def fit_log(rows, guess=True):
    """Ridge least squares in log space: (a, b, c) from (knn, guess, label), or (a, b) from (knn, label).

    The ridge pulls b and c toward 0.5 each (b toward 1.0 without a guess); a has none. None under 30 rows.
    """
    if len(rows) < MIN_FIT_ROWS:
        return None
    k = 3 if guess else 2
    a = [[0.0] * k for _ in range(k)]
    rhs = [0.0] * k
    for r in rows:
        if guess:
            x = [1.0, math.log(max(r[0], 1)), math.log(max(r[1], 1))]
        else:
            x = [1.0, math.log(max(r[0], 1))]
        y = math.log(max(r[-1], 1))
        for i in range(k):
            rhs[i] += x[i] * y
            for j in range(k):
                a[i][j] += x[i] * x[j]
    for j in range(1, k):
        a[j][j] += FIT_RIDGE
        rhs[j] += FIT_RIDGE * (0.5 if guess else 1.0)
    got = solve(a, rhs)
    return None if got is None else tuple(got)


def fit_estimate(coef, knn, guess=None):
    """exp(a + b ln knn [+ c ln guess]), whole minutes half up, at least 1."""
    z = coef[0] + coef[1] * math.log(max(knn, 1))
    if len(coef) > 2:
        z += coef[2] * math.log(max(guess, 1))
    return max(1, half_up(math.exp(max(-30.0, min(30.0, z)))))


def spread_of(rows, key):
    """The spread of ln(label / estimate) of the rows' estimates under key, 2 decimals; None without rows."""
    qs = [math.log(max(r["task"]["work"], 1) / float(max(r[key][0], 1))) for r in rows]
    return round(statistics.pstdev(qs), 2) if qs else None


def roll(tasks, bias_min):
    """Every tested task (the ones with 10 or more tasks before them) from the tasks before it only.

    Each row: task, est, rubric, guess, blend, repo (each (estimate, low, high)), weight, factor.
    """
    done = {}
    rows = []
    for i in range(MIN_BEFORE, len(tasks)):
        t = tasks[i]
        e, lo, hi, _ = estimator_row(tasks, i, done)
        row = {"task": t, "est": (e, lo, hi), "rubric": rubric(t), "guess": t["guess"],
               "weight": None, "factor": 1.0}
        g = t["guess"]
        if g is None:
            row["blend"] = row["repo"] = (e, lo, hi)
        else:
            prior = [r for r in rows if r["guess"] is not None]
            w = pick_weight([(r["est"][0], r["guess"], r["task"]["work"]) for r in prior])
            b = blend_est(e, g, w)
            f = bias_of(prior, t["repo"], w, bias_min)
            f = 1.0 if f is None else f
            c = final_est(b, f)
            ratios = done[("ratios", i)]
            rb = rc = ratios
            if len(prior) >= MIN_GUESSED:
                rb = sorted(r["task"]["work"] / float(r["blend"][0]) for r in prior)
                rc = sorted(r["task"]["work"] / float(r["repo"][0]) for r in prior)
            row["blend"] = (b,) + span_of(rb, b)
            row["repo"] = (c,) + span_of(rc, c)
            row["weight"], row["factor"] = w, f
        row["fit"] = fit_row(rows, row, e)
        rows.append(row)
    return rows


def fit_row(rows, row, e):
    """The fit estimate (est, low, high) of a row from the scored rows before it only."""
    g = row["guess"]
    if g is not None:
        coef = fit_log([(r["est"][0], r["guess"], r["task"]["work"]) for r in rows if r["guess"] is not None])
        f = row["blend"][0] if coef is None else fit_estimate(coef, e, g)
        row["fitted"] = coef is not None
    else:
        coef = fit_log([(r["est"][0], r["task"]["work"]) for r in rows], guess=False)
        f = e if coef is None else fit_estimate(coef, e)
        row["fitted"] = coef is not None
    if len(rows) < MIN_GUESSED:
        return (f,) + tuple(row["blend"][1:])
    return (f,) + span_of(sorted(r["task"]["work"] / float(r["fit"][0]) for r in rows), f)


# ---------------------------------------------------------------- backtest

def method_scores(rows):
    def of(key):
        return score([(r["task"]["work"], r[key][0], r[key][1], r[key][2]) for r in rows])
    out = {"estimator": of("est"), "blend": of("blend"), "blend+repo": of("repo"), "fit": of("fit"),
           "rubric": score([(r["task"]["work"], r["rubric"][0], r["rubric"][1], r["rubric"][2]) for r in rows]),
           "todo est": score([(r["task"]["work"], r["task"]["todo"], None, None)
                              for r in rows if r["task"]["todo"] is not None])}
    return out


def pick_winner(m):
    base = "estimator" if m["estimator"]["error"] < m["rubric"]["error"] else "rubric"
    b, c = m["blend"], m["blend+repo"]
    best = "blend+repo" if (c["n_within"], -c["error"]) > (b["n_within"], -b["error"]) else "blend"
    return best if m[best]["n_within"] > m[base]["n_within"] else base


def winner_of(m, rows):
    """Today's winner, but "fit" when its spread is strictly lower than that winner's."""
    win = pick_winner(m)
    if not any(r["fitted"] for r in rows):       # no row was really fitted: the fit is only the blend
        return win
    fit = spread_of(rows, "fit")
    others = [spread_of(rows, KEYS[k]) for k in ("blend", "blend+repo", win)]
    if fit is not None and all(o is not None and fit < o for o in others):
        return "fit"
    return win


def backtest(tasks, bias_min=BIAS_MIN, big_min=BIG_MIN):
    """None when there are fewer than 11 tasks, else the rows and the numbers per method."""
    if len(tasks) < MIN_BEFORE + 1:
        return None
    rows = roll(tasks, bias_min)
    big = [r for r in rows if r["task"]["work"] >= big_min]
    methods = method_scores(rows)
    return {"rows": rows, "methods": methods, "winner": winner_of(methods, rows), "tested": len(rows),
            "big": big, "big_methods": method_scores(big), "big_min": big_min}


def score(items):
    """items = (work, estimate, low, high); low None = no range. Numbers of one method."""
    n = len(items)
    if n == 0:
        return {"tasks": 0, "error": None, "within30": None, "inrange": None, "n_within": 0}
    errs = [abs(e - w) for w, e, _, _ in items]
    within = sum(1 for w, e, _, _ in items if abs(e - w) <= 0.3 * w)
    out = {"tasks": n, "error": round(float(statistics.median(errs)), 1),
           "within30": percent(within, n), "inrange": None, "n_within": within}
    if items[0][2] is not None:
        out["inrange"] = percent(sum(1 for w, _, lo, hi in items if lo <= w <= hi), n)
    return out


def target_line(p, goal):
    if p is None:
        return []
    if p >= goal:
        return ["target within 30%% %d%%: met (%d%%)" % (goal, p)]
    return ["target within 30%% %d%%: %d%%, gap %d points" % (goal, p, goal - p)]


def measure_part(qs):
    """(n, bias, spread) of the ln(label / estimate) values: the median and the population standard deviation."""
    if not qs:
        return 0, None, None
    return len(qs), float(statistics.median(qs)), statistics.pstdev(qs)


def measure_text(name, qs):
    n, bias, spread = measure_part(qs)
    if n == 0:
        return "%s: n 0 bias - spread -" % name
    return "%s: n %d bias %+.2f spread %.2f" % (name, n, round(bias, 2) + 0.0, round(spread, 2) + 0.0)


def measure_lines(tasks, bt):
    """The measure of the requirement's section 4, from the winner's estimate of every scored row."""
    key = KEYS.get(bt["winner"], "est")
    rows = bt["rows"]
    ests = [r[key][0] for r in rows]
    qs = [math.log(max(r["task"]["work"], 1) / float(max(e, 1))) for r, e in zip(rows, ests)]
    big = bt["big_min"]
    small_q = [q for q, e in zip(qs, ests) if e < big]
    big_q = [q for q, e in zip(qs, ests) if e >= big]
    end_q = []
    for r, e in zip(rows, ests):
        t = r["task"]
        tails = [max(0, p["clock"] - p["wait"] - p["work"]) for p in tasks[:t["pos"]] if p["lane"] == t["lane"]]
        tail = int(statistics.median(tails)) if len(tails) >= MIN_TAIL else 0
        actual = max(t["clock"] - t["wait"], 1)
        end_q.append(math.log(actual / float(max(e + tail, 1))))
    held = counted = 0
    for j in range(MIN_BEFORE, len(qs)):
        counted += 1
        if qs[j] <= percentile(sorted(qs[:j]), 0.85) + 1e-9:
            held += 1
    return ["measure: %d clean rows scored, by %s" % (len(rows), bt["winner"]),
            measure_text("measure work", qs),
            measure_text("measure work est < %dm" % big, small_q),
            measure_text("measure work est >= %dm" % big, big_q),
            measure_text("measure end", end_q),
            "measure p85: n %d holds %s" % (counted, "%d%%" % percent(held, counted) if counted else "-")] \
        + live_lines(tasks, rows)


def live_pairs(tasks, t):
    """[(est, |p50 - actual|)] of one row with a stage log: the forecast asked at each stage, from the rows before it."""
    import agent_forecast as fc
    est = t["est0"] if t["est0"] is not None else t["est"]
    if not t["stages"] or est is None:
        return []
    weights = fc.stage_weights()
    total_w = sum(weights.values())
    hist = []
    for p in tasks[:t["pos"]]:
        pe = p["est0"] if p["est0"] is not None else p["est"]
        built = p["built"]
        hist.append({"est": pe, "label": p["work"], "lane": p["lane"], "built": built,
                     "tail": max(0, p["rawwork"] - built) if built is not None
                     else max(0, p["clock"] - p["wait"] - p["rawwork"])})
    out = []
    done = 0
    before = 0
    for name, m in t["stages"].items():
        pace = before / float(total_w) if total_w > 0 else None
        got = fc.forecast({"est": est, "work": done, "stage": (name, None, None), "p": pace,
                           "lane": t["lane"], "built_work": t["built"]}, hist)
        if got is not None:
            out.append((est, abs(got[0] - (t["rawwork"] - done))))
        done += m
        before += weights.get(name, 0)
    return out


def live_lines(tasks, rows):
    """The two "measure live" lines: the median error in minutes of the live forecast, est <= 60m and est > 60m."""
    small, big, small2, big2 = [], [], [], []
    for r in rows:
        pairs = live_pairs(tasks, r["task"])
        for k, (e, err) in enumerate(pairs):
            (small if e <= 60 else big).append(err)
            if k >= len(pairs) - 2:
                (small2 if e <= 60 else big2).append(err)

    def med(v):
        return "%dm" % half_up(statistics.median(v)) if v else "-"
    return ["measure live est <= 60m: n %d error %s, last two %s" % (len(small), med(small), med(small2)),
            "measure live est > 60m: n %d error %s, last two %s" % (len(big), med(big), med(big2))]


def backtest_lines(tasks, bt, with_tasks, goal=TARGET_PCT, total=None, measure=False):
    if bt is None:
        return ["backtest: %d tasks, needs at least 11" % (len(tasks) if total is None else total)]
    out = ["backtest: %d tasks, %d tested, each from the tasks before it" % (
        len(tasks) if total is None else total, bt["tested"])]
    if with_tasks:
        for r in bt["rows"]:
            out.append("task %s work %d guess %s estimator %d (%d-%d) blend %d (%d-%d) "
                       "blend+repo %d (%d-%d) fit %d (%d-%d) rubric %d" % (
                           (r["task"]["name"], r["task"]["work"],
                            "-" if r["guess"] is None else r["guess"]) + r["est"] + r["blend"]
                           + r["repo"] + r["fit"] + (r["rubric"][0],)))
    fmt = "%-10s %-6s %-8s %-11s %s"
    out.append(fmt % ("method", "tasks", "error", "within 30%", "in range"))

    def table(prefix, methods):
        for name in BLEND_ROWS:
            m = methods[name]
            if m["tasks"] == 0:
                out.append(fmt % (prefix + name, 0, "-", "-", "-"))
                continue
            out.append(fmt % (prefix + name, m["tasks"], "%.1fm" % m["error"], "%d%%" % m["within30"],
                              "-" if m["inrange"] is None else "%d%%" % m["inrange"]))
    table("", bt["methods"])
    out.append("work >= %dm: %d tasks" % (bt["big_min"], len(bt["big"])))
    table("big ", bt["big_methods"])
    if measure:
        out.extend(measure_lines(tasks, bt))
    out.append("winner: " + bt["winner"])
    out.extend(target_line(bt["methods"][bt["winner"]]["within30"], goal))
    return out


# ---------------------------------------------------------------- the file

def read_model(path):
    """(whole file, current version) or None when it does not read."""
    try:
        with open(path) as fh:
            data = json.load(fh)
        current, checked = data["current"], data["checked_tasks"]
        if isinstance(current, bool) or isinstance(checked, bool):
            return None
        if not isinstance(current, int) or not isinstance(checked, int):
            return None
        versions = data["versions"]
        ver = [v for v in versions if v["version"] == current][0]
        if ver["method"] not in ("estimator", "rubric", "blend", "fit"):
            return None
        if ver["method"] in ("blend", "fit") and not blend_reads(ver):
            return None
        setting = (int(ver["k"]), ver["text"], ver["type"])
        if setting[0] < 1 or not all(isinstance(x, (int, float)) for x in setting[1:]):
            return None
        data.setdefault("checks", [])
        if "checked_date" in data and not isinstance(data["checked_date"], str):
            return None
        if not isinstance(data["checks"], list):
            return None
        return data, ver
    except Exception:
        return None


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def blend_reads(ver):
    """A blend version reads only with a weight in (0, 1), repo_bias true/false, a bias map, a span."""
    w, bias, span = ver["weight"], ver["bias"], ver["span"]
    return (is_num(w) and 0 < w < 1 and isinstance(ver["repo_bias"], bool)
            and isinstance(bias, dict) and all(is_num(x) and x > 0 for x in bias.values())
            and isinstance(span, list) and len(span) == 2 and all(is_num(x) and x > 0 for x in span)
            and span[0] <= span[1])


def save_model(path, data):
    """Atomic: a temp file beside it, then os.replace."""
    out = {"current": data["current"], "checked_tasks": data["checked_tasks"],
           "versions": data["versions"], "checks": data["checks"]}
    if isinstance(data.get("measures"), list):
        out["measures"] = data["measures"]
    if data.get("checked_date"):
        out["checked_date"] = data["checked_date"]
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        with open(tmp, "w") as fh:
            fh.write(json.dumps(out, indent=1) + "\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def day(text):
    try:
        return datetime.date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def setting_of(ver):
    return (int(ver["k"]), ver["text"], ver["type"])


# ---------------------------------------------------------------- commands

def cmd_estimate(tasks, model_path, args):
    vals, words = {}, []
    i = 0
    while i < len(args):
        a = args[i]
        if a in AFTER_FACTS:
            refuse("estimate: %s is known only after the task, so it is not an input" % a)
        if a in ("--lane", "--mock", "--type", "--name", "--guess"):
            if i + 1 >= len(args):
                refuse("estimate: %s needs a value" % a)
            vals[a] = args[i + 1]
            i += 2
        elif a.startswith("--"):
            refuse("estimate: unknown option: %s" % a)
        else:
            words.append(a)
            i += 1
    for opt, allowed in (("--lane", ("fast", "full")), ("--mock", ("yes", "no")), ("--type", TYPES)):
        if opt not in vals:
            refuse("estimate: %s is needed (one of: %s)" % (opt, " ".join(allowed)))
        if vals[opt] not in allowed:
            refuse("estimate: %s is one of: %s (got: %s)" % (opt, " ".join(allowed), vals[opt]))
    guess = None
    if "--guess" in vals:
        if not re.fullmatch(r"[0-9]+", vals["--guess"]) or int(vals["--guess"]) < 1:
            refuse("estimate: --guess is a whole number of minutes, 1 or more (got: %s)" % vals["--guess"])
        guess = int(vals["--guess"])
    what = " ".join(words).strip()
    if not what:
        refuse("estimate: the what text is needed (one line, in quotes, last)")
    name = vals.get("--name", "")
    target = {"name": name, "date": "-", "type": vals["--type"], "lane": vals["--lane"],
              "mock": vals["--mock"], "est": None, "work": 0, "pos": len(tasks), "words": {}}
    for w in WORD.findall((name + " " + what).lower()):
        target["words"][w] = target["words"].get(w, 0) + 1

    model = read_model(model_path)
    if model is None:
        label, method, setting, ver = "v0", "rubric", DEFAULT, None
    else:
        ver = model[1]
        label, method, setting = "v%d" % ver["version"], ver["method"], setting_of(ver)

    bt = backtest(tasks, env_int("AGENT_ESTIMATE_BIAS_MIN", BIAS_MIN, 1, 1000))
    rows = bt["rows"] if bt else []
    ctx = Ctx(tasks, target)
    near = ctx.rank(target, setting[1], setting[2])
    mid, lo, hi = rubric(target)
    why = None
    key = "rubric"
    if method in ("estimator", "blend", "fit") and tasks:
        mid = ctx.estimate(target, setting)
        lo, hi = ctx.span(setting, mid)
        key = "est"
        if method == "fit":
            knn = mid
            if guess is not None:
                triples = [(r["est"][0], r["guess"], r["task"]["work"]) for r in rows if r["guess"] is not None]
                coef = fit_log(triples)
                if coef is not None:
                    mid = fit_estimate(coef, knn, guess)
                    why = "fit: estimator %dm, guess %dm, a %.2f b %.2f c %.2f, %d rows" % (
                        knn, guess, coef[0], coef[1], coef[2], len(triples))
            else:
                pairs = [(r["est"][0], r["task"]["work"]) for r in rows]
                coef = fit_log(pairs, guess=False)
                if coef is not None:
                    mid = fit_estimate(coef, knn)
                    why = "fit: estimator %dm, a %.2f b %.2f, %d rows" % (knn, coef[0], coef[1], len(pairs))
            if coef is not None:
                lo, hi = span_of(sorted(r["task"]["work"] / float(r["fit"][0]) for r in rows), mid)
                key = "fit"
            else:
                method = "blend"                 # fewer than 30 rows: the blend, or the estimator
        if method == "blend" and guess is not None:
            repo = os.environ.get("AGENT_ESTIMATE_REPO") or os.path.basename(os.getcwd())
            w = float(ver["weight"])
            b = blend_est(mid, guess, w)
            f = float(ver["bias"][repo]) if ver["repo_bias"] and repo in ver["bias"] else 1.0
            why = "blend: estimator %dm, guess %dm, weight %g, repo %s x%.2f" % (mid, guess, w, repo, f)
            mid = final_est(b, f)
            lo, hi = half_up(mid * ver["span"][0]), half_up(mid * ver["span"][1])
            lo, hi = max(1, min(lo, mid)), max(hi, mid)
            key = "repo" if ver["repo_bias"] else "blend"
        else:
            method = "estimator" if method == "blend" else method
    else:
        method = "rubric"
    print("estimate: %dm work, range %d-%dm (%s %s, %d past tasks)" % (mid, lo, hi, method, label, len(tasks)))
    if why:
        print(why)
    elif guess is not None:
        print("guess: %dm, not used: %s is %s" % (guess, label, method))
    qs = sorted(math.log(max(r["task"]["work"], 1) / float(max(r[key][0], 1))) for r in rows)
    if len(qs) >= MIN_BEFORE:
        p50 = max(1, half_up(mid * math.exp(statistics.median(qs))))
        p85 = max(p50, half_up(mid * math.exp(percentile(qs, 0.85))))
    else:
        p50, p85 = mid, hi
    print("p50 %dm, p85 %dm (%d past errors)" % (p50, p85, len(qs)))
    for t in near[:3]:
        print("like %s: %dm work (%s, %s, mock %s, %s)" % (t["name"], t["work"], t["type"], t["lane"], t["mock"], t["date"]))
    return 0


def cmd_backtest(tasks, args):
    with_tasks = False
    for a in args:
        if a == "--tasks":
            with_tasks = True
        else:
            refuse("backtest: unknown option: %s" % a)
    total = len(tasks)
    tasks = learnable(tasks)
    bt = backtest(tasks, env_int("AGENT_ESTIMATE_BIAS_MIN", BIAS_MIN, 1, 1000),
                  env_int("AGENT_ESTIMATE_BIG_MIN", BIG_MIN, 1, 10000))
    for ln in backtest_lines(tasks, bt, with_tasks, env_int("AGENT_ESTIMATE_TARGET_PCT", TARGET_PCT, 1, 100),
                             total=total, measure=True):
        print(ln)
    return 0


def measure_entry(tasks, bt, today):
    """One entry of the list "measures": the numbers of the backtest's measure lines, as they print."""
    lines = measure_lines(tasks, bt)

    def line(prefix):
        return [l for l in lines if l.startswith(prefix)][0]

    def num(text):
        return None if text == "-" else float(text)
    w = re.match(r"^measure work: n (\d+) bias (\S+) spread (\S+)$", line("measure work: ")).groups()
    e = re.match(r"^measure end: n (\d+) bias (\S+) spread (\S+)$", line("measure end: ")).groups()
    p = re.match(r"^measure p85: n (\d+) holds (\S+)$", line("measure p85: ")).groups()
    ls = re.match(r"^measure live est <= \d+m: n \d+ error (\S+?)(?:,|$)", line("measure live est <=")).group(1)
    lb = re.match(r"^measure live est > \d+m: n \d+ error (\S+?)(?:,|$)", line("measure live est >")).group(1)

    def minutes(text):
        return None if text == "-" else int(text.rstrip("m"))
    return {"date": today, "tasks": len(tasks), "n": int(w[0]), "winner": bt["winner"],
            "work_bias": num(w[1]), "work_spread": num(w[2]), "end_bias": num(e[1]), "end_spread": num(e[2]),
            "p85": None if p[1] == "-" else int(p[1].rstrip("%")), "live_small": minutes(ls), "live_big": minutes(lb)}


def cmd_measure(tasks, model_path, today):
    """Appends one measures entry to a model file that reads; no file, no entry."""
    model = read_model(model_path)
    if model is None:
        return 0
    data = model[0]
    if "measures" in data and not isinstance(data["measures"], list):
        return 0
    bt = backtest(tasks, env_int("AGENT_ESTIMATE_BIAS_MIN", BIAS_MIN, 1, 1000),
                  env_int("AGENT_ESTIMATE_BIG_MIN", BIG_MIN, 1, 10000))
    if bt is None or not bt["rows"]:
        return 0
    data.setdefault("measures", []).append(measure_entry(tasks, bt, today))
    save_model(model_path, data)
    return 0


def cmd_retrain(tasks, model_path, today, args):
    force = auto = False
    for a in args:
        if a == "--force":
            force = True
        elif a == "--auto":
            auto = True
        else:
            refuse("retrain: unknown option: %s" % a)
    n = len(tasks)
    model = read_model(model_path)
    if n < MIN_TASKS:
        if not auto:
            print("estimate retrain: not yet (%d of %d tasks)" % (n, MIN_TASKS))
        return 0
    if model is not None and not force:
        due_at = model[0]["checked_tasks"] + RETRAIN_EVERY
        if n < due_at:
            if not auto:
                print("estimate retrain: not due (%d tasks, next check at %d)" % (n, due_at))
            return 0

    bias_min = env_int("AGENT_ESTIMATE_BIAS_MIN", BIAS_MIN, 1, 1000)
    goal = env_int("AGENT_ESTIMATE_TARGET_PCT", TARGET_PCT, 1, 100)
    bt = backtest(tasks, bias_min, env_int("AGENT_ESTIMATE_BIG_MIN", BIG_MIN, 1, 10000))
    ctx = Ctx(tasks, None)
    setting = ctx.pick()
    winner = bt["winner"]
    method = "blend" if winner.startswith("blend") else winner
    ms = bt["methods"]

    def numbers(m):
        return {"error": m["error"], "within30": m["within30"], "inrange": m["inrange"]}
    new = {"version": 1 if model is None else max(v["version"] for v in model[0]["versions"]) + 1,
           "date": today, "tasks": n, "method": method,
           "k": setting[0], "text": setting[1], "type": setting[2],
           "backtest": {"tasks": bt["tested"], "estimator": numbers(ms["estimator"]),
                        "rubric": numbers(ms["rubric"]), "blend": numbers(ms["blend"]),
                        "blend_repo": numbers(ms["blend+repo"])}}
    if method in ("blend", "fit"):
        repo_on = winner == "blend+repo"
        if method == "fit":
            b, c = ms["blend"], ms["blend+repo"]
            repo_on = (c["n_within"], -c["error"]) > (b["n_within"], -b["error"]) if b["tasks"] else False
        new.update(blend_params(bt["rows"], repo_on, bias_min))
    if not auto:
        for ln in backtest_lines(tasks, bt, False, goal):
            print(ln)
    est_err, rub_err = ms["estimator"]["error"], ms["rubric"]["error"]

    if model is None:
        save_model(model_path, {"current": 1, "checked_tasks": n, "checked_date": today,
                                "versions": [new], "checks": []})
        if method == "estimator":
            detail = "k %s, text %s, type %s; error %.1fm against the rubric's %.1fm on %d tasks" % (
                setting[0], setting[1], setting[2], est_err, rub_err, bt["tested"])
        elif method == "fit":
            base = "estimator" if ms["estimator"]["error"] < ms["rubric"]["error"] else "rubric"
            detail = "spread %.2f against the %s's %.2f on %d tasks" % (
                spread_of(bt["rows"], "fit"), base, spread_of(bt["rows"], KEYS[base]), bt["tested"])
        elif method == "blend":
            base = "estimator" if ms["estimator"]["error"] < ms["rubric"]["error"] else "rubric"
            detail = "within 30%% %d%% against the %s's %d%% on %d tasks" % (
                ms[winner]["within30"], base, ms[base]["within30"], bt["tested"])
            detail = "weight %g, repo bias %s; %s" % (new["weight"], "on" if new["repo_bias"] else "off", detail)
        else:
            detail = "error %.1fm against the estimator's %.1fm on %d tasks" % (rub_err, est_err, bt["tested"])
        print("estimate retrain: v1 made from %d tasks: %s (%s)" % (n, method, detail))
        for ln in target_line(ms[winner]["within30"], goal):
            print(ln)
        return 0

    data, cur = model
    new_count = max(0, n - data["checked_tasks"])      # the newest, in finish order, since the last check
    positions = list(range(n - new_count, n))
    if method == "fit" and cur["method"] == "fit":
        keep_new, basis = False, "backtest"
        cur_err = new_err = ms["fit"]["error"]
        text = "the fit is made from the data at each estimate, nothing new"
    elif method == "fit":
        cname = cur["method"] if cur["method"] != "blend" else ("blend+repo" if cur["repo_bias"] else "blend")
        new_sp, cur_sp = spread_of(bt["rows"], "fit"), spread_of(bt["rows"], KEYS[cname])
        keep_new = new_sp < cur_sp
        basis, cur_err, new_err = "backtest", ms[cname]["error"], ms["fit"]["error"]
        text = "backtest on %d tasks, spread: fit %.2f, %s v%d %.2f" % (
            bt["tested"], new_sp, cur["method"], cur["version"], cur_sp)
    elif method == "blend" and cur["method"] != "blend":
        # the backtest decides: the winner's within 30% against the row of the current method
        row = ms[cur["method"]]
        keep_new = ms[winner]["n_within"] > row["n_within"]
        basis, cur_err, new_err = "backtest", row["error"], ms[winner]["error"]
        text = "backtest on %d tasks, within 30%%: %s %d%%, %s v%d %d%%" % (
            bt["tested"], winner, ms[winner]["within30"], cur["method"], cur["version"], row["within30"])
    else:
        done = {}
        cur_errs, new_errs = [], []
        for p in positions:
            t = tasks[p]
            w = t["work"]
            c = current_estimate(tasks, p, cur, bt["rows"])
            cur_errs.append(abs(c - w))
            if method == "rubric":
                e = rubric(t)[0]
            elif p < MIN_BEFORE:
                e = estimator_row(tasks, p, done)[0]
            else:
                r = bt["rows"][p - MIN_BEFORE]
                e = r["repo"][0] if winner == "blend+repo" else r["blend"][0] if method == "blend" else r["est"][0]
            new_errs.append(abs(e - w))
        cur_err = round(float(statistics.median(cur_errs)), 1) if cur_errs else None
        new_err = round(float(statistics.median(new_errs)), 1) if new_errs else None
        keep_new = cur_err is not None and new_err < cur_err
        basis = "new tasks"
        if cur_err is None:
            text = "nothing to compare"
        else:
            text = "current v%d error %.1fm, new %s error %.1fm" % (cur["version"], cur_err, method, new_err)
        text = "on the %d new tasks: %s" % (len(positions), text)
    kept = new["version"] if keep_new else cur["version"]
    if keep_new:
        data["versions"].append(new)
        data["current"] = new["version"]
    data["checked_tasks"] = n
    data["checked_date"] = today
    data["checks"].append({"date": today, "tasks": n, "new": len(positions), "current": cur["version"],
                           "current_error": cur_err, "new_error": new_err, "kept": kept, "basis": basis})
    save_model(model_path, data)
    print("estimate retrain: kept v%d (%s)" % (kept, text))
    if keep_new:
        shown = ms[winner]
    elif cur["method"] == "fit":
        shown = ms["fit"]
    elif cur["method"] == "blend":
        shown = ms["blend+repo" if cur["repo_bias"] else "blend"]
    else:
        shown = ms[cur["method"]]
    for ln in target_line(shown["within30"], goal):
        print(ln)
    return 0


def blend_params(rows, repo_bias, bias_min):
    """weight, repo_bias, bias, span of a new blend version from every tested task with a guess."""
    guessed = [r for r in rows if r["guess"] is not None]
    w = pick_weight([(r["est"][0], r["guess"], r["task"]["work"]) for r in guessed])
    bias = {}
    if repo_bias:
        for repo in sorted(set(r["task"]["repo"] for r in guessed)):
            f = bias_of(guessed, repo, w, bias_min)
            if f is not None:
                bias[repo] = max(0.01, round(f, 2))
    ratios = sorted(r["task"]["work"] / float(final_est(blend_est(r["est"][0], r["guess"], w),
                                                       bias.get(r["task"]["repo"], 1.0)))
                    for r in guessed)
    span = [0.001, 0.001]
    if ratios:
        span = [max(0.001, round(percentile(ratios, 0.2), 3)), max(0.001, round(percentile(ratios, 0.8), 3))]
    return {"weight": w, "repo_bias": bool(repo_bias), "bias": bias, "span": span}


def current_estimate(tasks, p, cur, rows=None):
    """The current version's whole-minute estimate of task p, from the tasks before it."""
    t = tasks[p]
    if cur["method"] == "rubric":
        return rubric(t)[0]
    if cur["method"] == "fit" and rows and p >= MIN_BEFORE:
        return rows[p - MIN_BEFORE]["fit"][0]
    c = Ctx(tasks[:p], t).estimate(t, setting_of(cur))
    if c is None:
        return rubric(t)[0]
    if cur["method"] in ("blend", "fit") and t["guess"] is not None:
        f = float(cur["bias"].get(t["repo"], 1.0)) if cur["repo_bias"] else 1.0
        c = final_est(blend_est(c, t["guess"], float(cur["weight"])), f)
    return c


def main(argv):
    if len(argv) < 4 or argv[1] not in ("estimate", "backtest", "retrain", "measure"):
        sys.stderr.write("usage: agent_estimate.py <estimate|backtest|retrain> <model file> <today> [options] < rows\n")
        return 2
    cmd, model_path, today, args = argv[1], argv[2], argv[3], argv[4:]
    tasks = read_tasks(sys.stdin)
    if cmd == "backtest":
        return cmd_backtest(tasks, args)      # counts every row, scores the clean ones
    tasks = learnable(tasks)
    if cmd == "estimate":
        return cmd_estimate(tasks, model_path, args)
    if cmd == "measure":
        return cmd_measure(tasks, model_path, today)
    return cmd_retrain(tasks, model_path, today, args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
