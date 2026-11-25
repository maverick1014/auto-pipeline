#!/usr/bin/env python3
"""Run the test files in N processes (default 4), stdlib only.

    python3 tests/run2.py                      every test file, 4 processes (2 when RAM use
                                               is over 80%)
    python3 tests/run2.py -j 1                 one process (same as unittest discover)
    python3 tests/run2.py test_agent_file ...  only these files (name, with or without .py)
    python3 tests/run2.py --time [-j N]        each file in its own process, N at a time;
                                               prints file, tests, seconds (slowest first)
                                               and rewrites tests/timings.txt
    --root DIR                                 the repo whose tests/ to run (default: this one)
    --out FILE                                 --time writes here instead of tests/timings.txt

Split: the files are dealt to the processes by the seconds in tests/timings.txt,
slowest first, each to the process with the least time so far, so both end at
about the same moment. A file not in timings.txt counts as the median.

Plain `python3 -m unittest discover -s tests` still runs everything in one process.
Exit code: 0 when every process passed, else 1.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
RAN = re.compile(r"^Ran (\d+) tests? in ([\d.]+)s", re.M)
RESULT = re.compile(r"^(OK|FAILED)\b(.*)$", re.M)


RAM_CAP = 80   # percent; the pipeline's usage cap (max_usage_percent default)


def ram_used_percent():
    """RAM in use, percent, or None when it cannot be read (then -j 4)."""
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r"free percentage:\s*(\d+)%", out)
            return 100 - int(m.group(1)) if m else None
        with open("/proc/meminfo") as fh:
            info = dict(line.split(":", 1) for line in fh)
        total = int(info["MemTotal"].split()[0])
        avail = int(info["MemAvailable"].split()[0])
        return round(100 * (total - avail) / total)
    except Exception:
        return None


def test_files(tests_dir, only):
    names = sorted(n[:-3] for n in os.listdir(tests_dir)
                   if n.startswith("test_") and n.endswith(".py"))
    if not only:
        return names
    want = [o[:-3] if o.endswith(".py") else o for o in only]
    want = [os.path.basename(w) for w in want]
    missing = [w for w in want if w not in names]
    if missing:
        sys.exit("no such test file: %s" % ", ".join(missing))
    return want


def read_timings(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                try:
                    out[parts[2]] = float(parts[0])
                except ValueError:
                    pass
    return out


def test_classes(tests_dir, module):
    """(class name, number of test methods) of the classes defined in a test file."""
    import ast
    with open(os.path.join(tests_dir, module + ".py")) as fh:
        tree = ast.parse(fh.read())
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}

    def count(c, seen=()):
        own = sum(1 for m in c.body if isinstance(m, ast.FunctionDef) and m.name.startswith("test"))
        for b in c.bases:
            name = getattr(b, "id", None)
            if name in classes and name not in seen:
                own += count(classes[name], seen + (name,))
        return own

    return [(name, count(c)) for name, c in classes.items() if count(c)]


def split(names, timings, n, tests_dir=None):
    known = sorted(timings[k] for k in names if k in timings)
    default = known[len(known) // 2] if known else 1.0
    cost = {k: timings.get(k, default) for k in names}
    # a file bigger than a third of one process's share is dealt out class by class
    share = sum(cost.values()) / max(1, n)
    if tests_dir and n > 1:
        for name in list(names):
            if cost[name] > share / 3:
                classes = test_classes(tests_dir, name)
                total = sum(c for _, c in classes)
                if len(classes) > 1 and total:
                    for cname, c in classes:
                        cost["%s.%s" % (name, cname)] = cost[name] * c / total
                    del cost[name]
    names = list(cost)
    groups = [[] for _ in range(n)]
    totals = [0.0] * n
    for name in sorted(names, key=lambda k: -cost[k]):
        i = totals.index(min(totals))
        groups[i].append(name)
        totals[i] += cost[name]
    return [(g, t) for g, t in zip(groups, totals) if g]


def run_unittest(tests_dir, modules, log_path):
    start = time.time()
    with open(log_path, "w") as log:
        # cwd = the repo root, tests/ on the path: both `import scripthelp` and
        # `from tests.scripthelp import ...` work, as under `unittest discover -s tests`
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([tests_dir] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p])
        code = subprocess.call([sys.executable, "-m", "unittest"] + modules,
                               cwd=os.path.dirname(tests_dir), env=env,
                               stdout=log, stderr=subprocess.STDOUT)
    with open(log_path) as fh:
        text = fh.read()
    return code, time.time() - start, text


def summary(text):
    ran = RAN.findall(text)
    res = RESULT.findall(text)
    tests = int(ran[-1][0]) if ran else 0
    verdict = (res[-1][0] + res[-1][1]).strip() if res else "NO RESULT"
    return tests, verdict


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("-j", type=int, default=None,
                    help="processes; default 4 when RAM use is under the cap (80%%), else 2")
    ap.add_argument("--time", action="store_true")
    ap.add_argument("--root")
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.j is None:
        used = ram_used_percent()
        args.j = 4 if used is None or used < RAM_CAP else 2
    tests_dir = os.path.join(os.path.abspath(args.root), "tests") if args.root else HERE
    names = test_files(tests_dir, args.files)
    logs = tempfile.mkdtemp(prefix="run2_")
    start = time.time()

    if args.time:
        def one(name):
            code, secs, text = run_unittest(tests_dir, [name], os.path.join(logs, name + ".log"))
            tests, verdict = summary(text)
            return name, code, secs, tests, verdict

        with ThreadPoolExecutor(max_workers=max(1, args.j)) as pool:
            rows = list(pool.map(one, names))
        rows.sort(key=lambda r: -r[2])
        out = args.out or os.path.join(tests_dir, "timings.txt")
        with open(out, "w") as fh:
            fh.write("# seconds\ttests\tfile (python3 tests/run2.py --time -j %d, %s)\n"
                     % (args.j, time.strftime("%Y-%m-%d %H:%M")))
            for name, code, secs, tests, verdict in rows:
                fh.write("%.1f\t%d\t%s\n" % (secs, tests, name))
        bad = [r for r in rows if r[1] != 0]
        for name, code, secs, tests, verdict in rows:
            print("%7.1f  %5d  %s%s" % (secs, tests, name, "" if code == 0 else "  " + verdict))
        print("files %d  tests %d  sum of file seconds %.0f  wall %.0f s  (-j %d)  -> %s"
              % (len(rows), sum(r[3] for r in rows), sum(r[2] for r in rows),
                 time.time() - start, args.j, out))
        for name, code, secs, tests, verdict in bad:
            print("FAILED %s: see %s" % (name, os.path.join(logs, name + ".log")))
        return 1 if bad else 0

    groups = split(names, read_timings(os.path.join(tests_dir, "timings.txt")), max(1, args.j), tests_dir)

    def go(i_group):
        i, (mods, est) = i_group
        return i, mods, est, run_unittest(tests_dir, mods, os.path.join(logs, "group%d.log" % (i + 1)))

    with ThreadPoolExecutor(max_workers=len(groups)) as pool:
        results = list(pool.map(go, enumerate(groups)))
    failed = False
    for i, mods, est, (code, secs, text) in results:
        tests, verdict = summary(text)
        print("process %d: %d files or classes, %d tests, %.0f s (planned %.0f s): %s"
              % (i + 1, len(mods), tests, secs, est, verdict))
        if code != 0:
            failed = True
            print("  log: %s" % os.path.join(logs, "group%d.log" % (i + 1)))
            for block in re.findall(r"^(?:FAIL|ERROR): .*$", text, re.M):
                print("  " + block)
    print("wall %.0f s, %d processes" % (time.time() - start, len(groups)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
