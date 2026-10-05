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

import json
import math
import os
import re
import statistics
import sys

MIN_TASKS = 30        # tasks needed for the first version
RETRAIN_EVERY = 10    # new tasks between two checks
MIN_BEFORE = 10       # tasks before a task, to backtest it
TYPES = ("page", "server", "script", "docs", "cloud", "app", "data", "mixed")
AFTER_FACTS = ("--work", "--wait", "--clock", "--est", "--bounces", "--workers",
               "--files", "--lines", "--tests", "--adds")
# k first, then text, then type, each smallest first
GRID = [(k, text, kind) for k in (3, 5, 7) for text in (0, 1) for kind in (0, 0.5)]
DEFAULT = (3, 1, 0.5)   # the setting of the like lines when there is no file
WORD = re.compile(r"[a-z0-9]{3,}")


def refuse(text):
    sys.stderr.write(text + "\n")
    sys.exit(1)


# ---------------------------------------------------------------- the data

def read_tasks(stream):
    """The finished tasks with a whole-number work, in finish order."""
    rows = stream.read().splitlines()[1:]
    tasks = []
    for row in rows:
        f = row.split(None, 16)
        if len(f) < 16 or not re.fullmatch(r"[0-9]+", f[7]):
            continue
        what = f[16] if len(f) > 16 and f[16] != "-" else ""
        est = int(f[6]) if re.fullmatch(r"[0-9]+", f[6]) else None
        words = {}
        for w in WORD.findall((f[1] + " " + what).lower()):
            words[w] = words.get(w, 0) + 1
        tasks.append({
            "name": f[1], "date": f[2], "type": f[3],
            "lane": "fast" if f[4] == "fast" else "full",
            "mock": "yes" if f[5] == "yes" else "no",
            "est": est, "work": int(f[7]), "words": words,
        })
    tasks.sort(key=lambda t: t["date"])          # stable: the table order breaks ties
    for i, t in enumerate(tasks):
        t["pos"] = i
    return tasks


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
        else:
            lo, hi = ctx.span(setting, est)
            row = (est, lo, hi, setting)
        done[i] = row
    return row


# ---------------------------------------------------------------- backtest

def backtest(tasks):
    """None when there are fewer than 11 tasks, else the rows and the numbers per method."""
    if len(tasks) < MIN_BEFORE + 1:
        return None
    done = {}
    rows = []
    for i in range(MIN_BEFORE, len(tasks)):
        t = tasks[i]
        e, lo, hi, _ = estimator_row(tasks, i, done)
        r, rlo, rhi = rubric(t)
        rows.append({"task": t, "est": (e, lo, hi), "rubric": (r, rlo, rhi)})
    todo = [(r["task"]["work"], r["task"]["est"]) for r in rows if r["task"]["est"] is not None]
    methods = {
        "estimator": score([(r["task"]["work"], r["est"][0], r["est"][1], r["est"][2]) for r in rows]),
        "rubric": score([(r["task"]["work"], r["rubric"][0], r["rubric"][1], r["rubric"][2]) for r in rows]),
        "todo est": score([(w, e, None, None) for w, e in todo]),
    }
    winner = "estimator" if methods["estimator"]["error"] < methods["rubric"]["error"] else "rubric"
    return {"rows": rows, "methods": methods, "winner": winner, "tested": len(rows)}


def score(items):
    """items = (work, estimate, low, high); low None = no range. Numbers of one method."""
    n = len(items)
    if n == 0:
        return {"tasks": 0, "error": None, "within30": None, "inrange": None}
    errs = [abs(e - w) for w, e, _, _ in items]
    within = sum(1 for w, e, _, _ in items if abs(e - w) <= 0.3 * w)
    out = {"tasks": n, "error": round(float(statistics.median(errs)), 1),
           "within30": percent(within, n), "inrange": None}
    if items[0][2] is not None:
        out["inrange"] = percent(sum(1 for w, _, lo, hi in items if lo <= w <= hi), n)
    return out


def backtest_lines(tasks, bt, with_tasks):
    if bt is None:
        return ["backtest: %d tasks, needs at least 11" % len(tasks)]
    out = ["backtest: %d tasks, %d tested, each from the tasks before it" % (len(tasks), bt["tested"])]
    if with_tasks:
        for r in bt["rows"]:
            out.append("task %s work %d estimator %d (%d-%d) rubric %d" % (
                r["task"]["name"], r["task"]["work"], r["est"][0], r["est"][1], r["est"][2], r["rubric"][0]))
    fmt = "%-10s %-6s %-8s %-11s %s"
    out.append(fmt % ("method", "tasks", "error", "within 30%", "in range"))
    for name in ("estimator", "rubric", "todo est"):
        m = bt["methods"][name]
        if m["tasks"] == 0:
            out.append(fmt % (name, 0, "-", "-", "-"))
            continue
        out.append(fmt % (name, m["tasks"], "%.1fm" % m["error"], "%d%%" % m["within30"],
                          "-" if m["inrange"] is None else "%d%%" % m["inrange"]))
    out.append("winner: " + bt["winner"])
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
        if ver["method"] not in ("estimator", "rubric"):
            return None
        setting = (int(ver["k"]), ver["text"], ver["type"])
        if setting[0] < 1 or not all(isinstance(x, (int, float)) for x in setting[1:]):
            return None
        data.setdefault("checks", [])
        if not isinstance(data["checks"], list):
            return None
        return data, ver
    except Exception:
        return None


def save_model(path, data):
    """Atomic: a temp file beside it, then os.replace."""
    out = {"current": data["current"], "checked_tasks": data["checked_tasks"],
           "versions": data["versions"], "checks": data["checks"]}
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        with open(tmp, "w") as fh:
            fh.write(json.dumps(out, indent=1) + "\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


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
        if a in ("--lane", "--mock", "--type", "--name"):
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
        label, method, setting = "v0", "rubric", DEFAULT
    else:
        ver = model[1]
        label, method, setting = "v%d" % ver["version"], ver["method"], setting_of(ver)

    ctx = Ctx(tasks, target)
    near = ctx.rank(target, setting[1], setting[2])
    mid, lo, hi = rubric(target)
    if method == "estimator" and tasks:
        mid = ctx.estimate(target, setting)
        lo, hi = ctx.span(setting, mid)
    else:
        method = "rubric"
    print("estimate: %dm work, range %d-%dm (%s %s, %d past tasks)" % (mid, lo, hi, method, label, len(tasks)))
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
    for ln in backtest_lines(tasks, backtest(tasks), with_tasks):
        print(ln)
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
    if model is not None:
        due_at = model[0]["checked_tasks"] + RETRAIN_EVERY
        if n < due_at and not force:
            if not auto:
                print("estimate retrain: not due (%d tasks, next check at %d)" % (n, due_at))
            return 0

    bt = backtest(tasks)
    ctx = Ctx(tasks, None)
    setting = ctx.pick()
    method = bt["winner"]
    new = {"version": 1 if model is None else max(v["version"] for v in model[0]["versions"]) + 1,
           "date": today, "tasks": n, "method": method,
           "k": setting[0], "text": setting[1], "type": setting[2],
           "backtest": {"tasks": bt["tested"],
                        "estimator": {"error": bt["methods"]["estimator"]["error"],
                                      "within30": bt["methods"]["estimator"]["within30"],
                                      "inrange": bt["methods"]["estimator"]["inrange"]},
                        "rubric": {"error": bt["methods"]["rubric"]["error"],
                                   "within30": bt["methods"]["rubric"]["within30"],
                                   "inrange": bt["methods"]["rubric"]["inrange"]}}}
    if not auto:
        for ln in backtest_lines(tasks, bt, False):
            print(ln)
    est_err, rub_err = bt["methods"]["estimator"]["error"], bt["methods"]["rubric"]["error"]

    if model is None:
        save_model(model_path, {"current": 1, "checked_tasks": n, "versions": [new], "checks": []})
        if method == "estimator":
            detail = "k %s, text %s, type %s; error %.1fm against the rubric's %.1fm on %d tasks" % (
                setting[0], setting[1], setting[2], est_err, rub_err, bt["tested"])
        else:
            detail = "error %.1fm against the estimator's %.1fm on %d tasks" % (rub_err, est_err, bt["tested"])
        print("estimate retrain: v1 made from %d tasks: %s (%s)" % (n, method, detail))
        return 0

    data, cur = model
    new_count = max(0, n - data["checked_tasks"])      # the newest, in finish order, since the last check
    positions = list(range(n - new_count, n))
    done = {}
    cur_errs, new_errs = [], []
    for p in positions:
        w = tasks[p]["work"]
        if cur["method"] == "estimator":
            c = Ctx(tasks[:p], tasks[p]).estimate(tasks[p], setting_of(cur))
            c = rubric(tasks[p])[0] if c is None else c
        else:
            c = rubric(tasks[p])[0]
        cur_errs.append(abs(c - w))
        e = estimator_row(tasks, p, done)[0] if method == "estimator" else rubric(tasks[p])[0]
        new_errs.append(abs(e - w))
    cur_err = round(float(statistics.median(cur_errs)), 1) if cur_errs else None
    new_err = round(float(statistics.median(new_errs)), 1) if new_errs else None
    keep_new = cur_err is not None and new_err < cur_err
    kept = new["version"] if keep_new else cur["version"]
    if keep_new:
        data["versions"].append(new)
        data["current"] = new["version"]
    data["checked_tasks"] = n
    data["checks"].append({"date": today, "tasks": n, "new": len(positions), "current": cur["version"],
                           "current_error": cur_err, "new_error": new_err, "kept": kept})
    save_model(model_path, data)
    if cur_err is None:
        text = "nothing to compare"
    else:
        text = "current v%d error %.1fm, new %s error %.1fm" % (cur["version"], cur_err, method, new_err)
    print("estimate retrain: kept v%d (on the %d new tasks: %s)" % (kept, len(positions), text))
    return 0


def main(argv):
    if len(argv) < 4 or argv[1] not in ("estimate", "backtest", "retrain"):
        sys.stderr.write("usage: agent_estimate.py <estimate|backtest|retrain> <model file> <today> [options] < rows\n")
        return 2
    cmd, model_path, today, args = argv[1], argv[2], argv[3], argv[4:]
    tasks = read_tasks(sys.stdin)
    if cmd == "estimate":
        return cmd_estimate(tasks, model_path, args)
    if cmd == "backtest":
        return cmd_backtest(tasks, args)
    return cmd_retrain(tasks, model_path, today, args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
