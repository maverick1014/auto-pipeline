#!/usr/bin/env python3
"""Run the test files in N processes, stdlib only.

    python3 tests/run2.py                      every test file; processes = CPU cores x 80%
                                               (6 on 8 cores), fewer when memory is short
    python3 tests/run2.py -j 1                 one process (same as unittest discover)
    python3 tests/run2.py test_agent_file ...  only these files (name, with or without .py)
    python3 tests/run2.py --time [-j N]        each file in its own process, N at a time;
                                               prints file, tests, seconds (slowest first)
                                               and rewrites tests/timings.txt
    --root DIR                                 the repo whose tests/ to run (default: this one)
    --out FILE                                 --time writes here instead of tests/timings.txt

Split: the files are dealt to the processes by the seconds in tests/timings.txt,
slowest first, each to the process with the least time so far, so all end at
about the same moment. A file not in timings.txt counts as the median; a file
bigger than a third of one process's share is dealt out class by class (classes and counts from the real unittest
loader, one short subprocess; a file the loader lists but cannot split class by class runs whole; a file it cannot list at all does not run (NOT LISTED)).

Load (owner 2026-11-25): CPU stays under 80% (the default -j), and a process is
started only while memory in use + about 30 MB for it stays under 80%; else it
waits for a running one to end. No slot or lock: long light runs just go.

With no test file named (the full suite: the release run, the nightly) every process it starts gets AGENT_FULL_RUN=1; named files do not.

Plain `python3 -m unittest discover -s tests` still runs everything in one process.
Exit code: 0 when every process passed and, for each file, the tests run equal the tests
the loader discovers in it (else the line COUNT MISMATCH: discovered x, ran y in <file>),
else 1. Also 1 (one line each): a file the loader cannot list, from an exit, an exception,
a failed import or zero tests at import (NOT LISTED: <file> could not be listed: <reason>);
a file where every test that started was skipped (ALL SKIPPED: <file> ...), unless
agent_repo.conf has all_skip_ok=<file>: <reason> (no reason: ignored and said). A file that
only runs whole (load_tests, a class defined elsewhere) is named in one "count check skipped"
line; the other files are still checked. The run counts per file come from a small runner that
does what `python -m unittest` does and records each test and each skip under the file it was
named for. A red run prints the failure sections of each failed process, every line prefixed "  | ".
Folder: the run's logs live in one run2_* folder in the temp dir, removed when the run ends
(green, red, error, SIGINT, SIGTERM, SIGHUP; on a signal the test processes are stopped first).
Marker: <folder>/.run2_owner holds the pid and start time of the run; at start a run2_* folder
whose marker names a process that is gone (or another process now) is removed; any other is left.
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fasttools import direct_tools  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RAN = re.compile(r"^Ran (\d+) tests? in ([\d.]+)s", re.M)
RESULT = re.compile(r"^(OK|FAILED)\b(.*)$", re.M)


RAM_CAP = 80        # percent: memory in use + PER_PROCESS_MB must stay under it
CPU_CAP = 80        # percent of the cores: the default number of processes
PER_PROCESS_MB = 30  # one test process (measured: about 28 MB)


def default_jobs():
    return max(1, int((os.cpu_count() or 2) * CPU_CAP / 100))


def total_ram_mb():
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5).stdout
            return int(out.strip()) / 1048576
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024
    except Exception:
        return None
    return None


def room_for_one_more():
    """True when memory in use + one more test process stays under RAM_CAP."""
    used, total = ram_used_percent(), total_ram_mb()
    if used is None or not total:
        return True
    return used + 100.0 * PER_PROCESS_MB / total < RAM_CAP


def wait_for_room(limit_s=600):
    waited = 0
    while not room_for_one_more() and waited < limit_s:
        time.sleep(2)
        waited += 2


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


LISTER = r"""
import json, sys, unittest

real, sys.stdout = sys.stdout, sys.stderr   # what the files print at import is not our answer


def emit(**item):   # one JSON line per module, flushed: a lister that dies names the module it was on
    real.write(json.dumps(item) + "\n")
    real.flush()


def walk(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            yield from walk(t)
        else:
            yield t


def one_line(text):
    return " ".join(str(text).split())[:300]


for name in sys.argv[1:]:
    try:
        suite = unittest.defaultTestLoader.loadTestsFromName(name)
        mod = sys.modules.get(name)   # none when the import failed
        counts, failed = {}, None
        whole = hasattr(mod, "load_tests")   # load_tests: only the whole file is right
        for t in walk(suite):
            cls = type(t)
            if cls.__name__ == "_FailedTest":
                exc = getattr(t, "_exception", None)
                last = [l for l in str(exc).splitlines() if l.strip()][-1:]   # the traceback's last line names the exception
                failed = "import failed: %s" % one_line(last[0] if last else type(exc).__name__)
                break
            if getattr(mod, cls.__name__, None) is not cls:
                whole = True
            counts[cls.__name__] = counts.get(cls.__name__, 0) + 1
        if failed:
            emit(module=name, failed=failed)
        elif not counts:
            emit(module=name, failed="no tests found at import")
        elif whole:
            emit(module=name, whole=True)
        else:
            emit(module=name, classes=sorted(counts.items()))
    except SystemExit as e:
        emit(module=name, failed="sys.exit(%s) at import" % one_line(e.code))
    except BaseException as e:
        emit(module=name, failed="%s: %s at import" % (type(e).__name__, one_line(e)))
"""


def unittest_env(tests_dir):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([tests_dir] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p])
    return env


def list_modules(tests_dir, modules):
    """({module: [(class, tests)] or None}, {module: reason}). None with no reason: the
    module runs whole (load_tests, or a class defined elsewhere). None with a reason: it
    could not be listed (exit, exception, failed import, no tests, or the lister itself
    failed). A lister that dies on a module is restarted on the modules after it."""
    out = {m: None for m in modules}
    reasons = {}
    todo = list(modules)
    while todo:
        died, whole_failure, text = None, None, ""
        try:
            done = subprocess.run([sys.executable, "-c", LISTER] + todo,
                                  cwd=os.path.dirname(tests_dir), env=unittest_env(tests_dir),
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  universal_newlines=True, timeout=300)
            text = done.stdout or ""
            died = "the import ended the process (exit %s)" % done.returncode
        except subprocess.TimeoutExpired as e:
            text = e.stdout or ""
            if isinstance(text, bytes):
                text = text.decode("utf-8", "replace")
            whole_failure = "the lister timed out after 300 s"
        except Exception as e:
            whole_failure = "the lister failed: %s: %s" % (type(e).__name__, e)
        got = set()
        for line in text.splitlines():
            try:
                item = json.loads(line)
                m = item["module"]
            except (ValueError, KeyError, TypeError):
                continue
            if m not in todo or m in got:
                continue
            got.add(m)
            if item.get("failed"):
                reasons[m] = item["failed"]
            elif item.get("classes"):
                out[m] = [(c, n) for c, n in item["classes"]]
        todo = [m for m in todo if m not in got]
        if todo and whole_failure:
            for m in todo:
                reasons[m] = whole_failure
            break
        if todo:
            reasons[todo[0]] = died
            todo = todo[1:]
    return out, reasons


def loader_listing(tests_dir, modules, reasons=None):
    """{module: [(class name, tests)] or None}: what the real unittest loader finds,
    from a short subprocess with the cwd and PYTHONPATH of run_unittest. None for a
    module that cannot be listed exactly (then it runs whole, never split). With a dict
    as `reasons`, it is filled with {module: why} for a module that could not be listed
    at all."""
    out, why = list_modules(tests_dir, modules)
    if reasons is not None:
        reasons.update(why)
    return out


def all_skip_ok(root):
    """{file name: reason} from the all_skip_ok= lines of <root>/agent_repo.conf. An
    entry with no reason is not honoured and is said in one line."""
    ok = {}
    try:
        with open(os.path.join(root, "agent_repo.conf")) as fh:
            lines = fh.read().splitlines()
    except OSError:
        return ok
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() != "all_skip_ok":
            continue
        entry, _, reason = value.strip().partition(":")
        name = os.path.basename(entry.strip())
        if name.endswith(".py"):
            name = name[:-3]
        if not reason.strip():
            print("all_skip_ok: %s has no reason, ignored" % (entry.strip() or line))
        else:
            ok[name] = reason.strip()
    return ok


def proc_start(pid):
    """The start time of a process as `ps` says it (a string), or None."""
    try:
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True,
                             text=True, timeout=10).stdout.strip()
    except Exception:
        return None
    return out or None


MARKER = ".run2_owner"


def remove_stale_folders():
    """Remove run2_* folders in the temp dir that a dead run2 left: a real folder with a
    marker (pid, start time) whose process is gone or is another process now. Nothing
    else is touched."""
    base = tempfile.gettempdir()
    try:
        entries = os.listdir(base)
    except OSError:
        return
    for entry in entries:
        path = os.path.join(base, entry)
        if not entry.startswith("run2_") or os.path.islink(path) or not os.path.isdir(path):
            continue
        try:
            with open(os.path.join(path, MARKER)) as fh:
                mark = json.load(fh)
            pid, start = mark["pid"], mark["start"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if type(pid) is not int or pid <= 0 or not isinstance(start, str) or not start.strip():
            continue
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            shutil.rmtree(path, ignore_errors=True)
            continue
        except OSError:
            pass   # the process exists (not ours to signal): compare the start time
        now = proc_start(pid)
        if now is not None and now != start:
            shutil.rmtree(path, ignore_errors=True)


def failure_lines(text):
    """The failure sections of a unittest log (each block from its "=====" line with
    FAIL:/ERROR: through its traceback), every line prefixed "  | "; with none, the last
    40 lines of the log."""
    lines = text.splitlines()
    out, inside = [], False
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if line.startswith("=" * 10):
            inside = bool(re.match(r"(FAIL|ERROR): ", nxt))
        elif inside and line.startswith("-" * 10) and nxt.startswith("Ran "):
            inside = False
        if inside:
            out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return ["  | " + l for l in (out or lines[-40:])]


PER_PROCESS_LINES, TOTAL_LINES = 60, 300


def capped(lines, left):
    """The lines to print: at most PER_PROCESS_LINES and what is left of the run's budget
    (left[0], reduced here); when some are not shown, one line says how many."""
    shown = lines[:max(0, min(PER_PROCESS_LINES, left[0]))]
    left[0] -= len(shown)
    if len(shown) < len(lines):
        shown.append("  | ... %d more lines cut" % (len(lines) - len(shown)))
    return shown


# the test processes now running, and whether a stop signal came: no new process after it
CHILDREN, CHILDREN_LOCK, STOPPING = set(), threading.Lock(), [False]
LOGS = [None]
TOOLS = [None]   # the agent_test_tools_* folder this process made (its atexit does not run on a signal)


def stop_children():
    with CHILDREN_LOCK:
        STOPPING[0] = True
        procs = list(CHILDREN)
    for p in procs:
        try:
            p.terminate()
        except OSError:
            pass
    end = time.time() + 2
    for p in procs:
        try:
            p.wait(max(0.01, end - time.time()))
        except subprocess.TimeoutExpired:
            try:
                p.kill()
            except OSError:
                pass
        except Exception:
            pass


def on_signal(sig, frame):
    stop_children()
    for folder in (LOGS[0], TOOLS[0]):
        if folder:
            shutil.rmtree(folder, ignore_errors=True)
    signal.signal(sig, signal.SIG_DFL)
    os.kill(os.getpid(), sig)


def count_mismatch(discovered, ran):
    if discovered == ran:
        return None
    return "COUNT MISMATCH: discovered %d, ran %d" % (discovered, ran)


def split(names, timings, n, listing=None):
    known = sorted(timings[k] for k in names if k in timings)
    default = known[len(known) // 2] if known else 1.0
    cost = {k: timings.get(k, default) for k in names}
    # a file bigger than a third of one process's share is dealt out class by class
    share = sum(cost.values()) / max(1, n)
    if listing and n > 1:
        for name in list(names):
            if cost[name] > share / 3:
                classes = listing.get(name) or []
                total = sum(c for _, c in classes)
                if len(classes) > 1 and total:
                    for cname, c in classes:
                        key = "%s.%s" % (name, cname)
                        # test-slim-3: the class's own measured seconds (a --time row), else its share by tests
                        cost[key] = timings[key] if key in timings else cost[name] * c / total
                    del cost[name]
    names = list(cost)
    groups = [[] for _ in range(n)]
    totals = [0.0] * n
    for name in sorted(names, key=lambda k: -cost[k]):
        i = totals.index(min(totals))
        groups[i].append(name)
        totals[i] += cost[name]
    return [(g, t) for g, t in zip(groups, totals) if g]


RUNNER = r"""
import json, os, sys, time, unittest

def walk(suite):
    if not isinstance(suite, unittest.TestSuite):
        yield suite
        return
    for t in suite:
        yield from walk(t)

sys.path.insert(0, os.getcwd())   # as `python -m unittest` has it
suite, owner, counts, skips = unittest.TestSuite(), {}, {}, {}
for name in sys.argv[1:]:
    part = unittest.defaultTestLoader.loadTestsFromName(name)
    for t in walk(part):
        owner[id(t)] = name
    suite.addTest(part)

secs, last = {}, [time.perf_counter()]   # "<file>.<Class>": [seconds, tests]; set-up between two tests counts for the next


class Result(unittest.TextTestResult):
    def startTest(self, test):
        name = owner.get(id(test), "?")
        counts[name] = counts.get(name, 0) + 1
        super().startTest(test)

    def addSkip(self, test, reason):
        if id(test) in owner:
            skips[owner[id(test)]] = skips.get(owner[id(test)], 0) + 1
        super().addSkip(test, reason)

    def stopTest(self, test):
        super().stopTest(test)
        now = time.perf_counter()
        key = "%s.%s" % (owner.get(id(test), "?").split(".")[0], type(test).__name__)
        row = secs.setdefault(key, [0.0, 0])
        row[0] += now - last[0]
        row[1] += 1
        last[0] = now

res = unittest.TextTestRunner(resultclass=Result).run(suite)
with open(os.environ["RUN2_COUNTS"], "w") as fh:
    json.dump(counts, fh)
with open(os.environ["RUN2_COUNTS"] + ".secs", "w") as fh:
    json.dump(secs, fh)
with open(os.environ["RUN2_COUNTS"] + ".skips", "w") as fh:
    json.dump(skips, fh)
sys.exit(0 if res.wasSuccessful() else 1)
"""


def run_unittest(tests_dir, modules, log_path):
    """(exit code, seconds, output, {module or module.Class: tests run}, {file.Class: [seconds, tests]},
    {module or module.Class: tests skipped}). No new process once a stop signal came."""
    start = time.time()
    runner, counts_path = log_path + ".runner.py", log_path + ".counts"
    # one locked section: the stop check, every file made in the folder, and the start; once
    # stop_children set STOPPING (under this lock) no thread can put a file in the folder
    with CHILDREN_LOCK:
        if STOPPING[0]:
            raise RuntimeError("stopped")
        with open(runner, "w") as fh:
            fh.write(RUNNER)
        # cwd = the repo root, tests/ on the path: both `import scripthelp` and
        # `from tests.scripthelp import ...` work, as under `unittest discover -s tests`
        env = unittest_env(tests_dir)
        env["RUN2_COUNTS"] = counts_path
        with open(log_path, "w") as log:
            proc = subprocess.Popen([sys.executable, runner] + modules,
                                    cwd=os.path.dirname(tests_dir), env=env,
                                    stdout=log, stderr=subprocess.STDOUT)
        CHILDREN.add(proc)
    try:
        code = proc.wait()
    finally:
        with CHILDREN_LOCK:
            CHILDREN.discard(proc)
    with open(log_path) as fh:
        text = fh.read()
    side = []
    for suffix in ("", ".secs", ".skips"):
        try:
            with open(counts_path + suffix) as fh:
                side.append(json.load(fh))
        except (OSError, ValueError):
            side.append({})
    return code, time.time() - start, text, side[0], side[1], side[2]


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
                    help="processes; default CPU cores x 80%% (memory permitting)")
    ap.add_argument("--time", action="store_true")
    ap.add_argument("--root")
    ap.add_argument("--out")
    args = ap.parse_args()
    TOOLS[0] = direct_tools()   # test-slim-3: git and python3 without the macOS xcrun shim, for every process started
    if not args.files:
        os.environ["AGENT_FULL_RUN"] = "1"
    else:
        os.environ.pop("AGENT_FULL_RUN", None)

    if args.j is None:
        args.j = default_jobs()
    tests_dir = os.path.join(os.path.abspath(args.root), "tests") if args.root else HERE
    root = os.path.dirname(tests_dir)
    names = test_files(tests_dir, args.files)
    old = {}
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        old[sig] = signal.signal(sig, on_signal)
    remove_stale_folders()
    logs = tempfile.mkdtemp(prefix="run2_")
    LOGS[0] = logs
    try:
        with open(os.path.join(logs, MARKER), "w") as fh:
            json.dump({"pid": os.getpid(), "start": proc_start(os.getpid()) or ""}, fh)
        return run_all(args, tests_dir, root, names, logs)
    finally:
        shutil.rmtree(logs, ignore_errors=True)
        LOGS[0] = None
        for sig, handler in old.items():
            signal.signal(sig, handler)


def run_all(args, tests_dir, root, names, logs):
    start = time.time()

    if args.time:
        texts = {}

        def one(name):
            wait_for_room()
            code, secs, text, counts, class_secs, _skips = run_unittest(tests_dir, [name], os.path.join(logs, name + ".log"))
            texts[name] = text
            tests, verdict = summary(text)
            return name, code, secs, tests, verdict, class_secs

        with ThreadPoolExecutor(max_workers=max(1, args.j)) as pool:
            rows = list(pool.map(one, names))
        rows.sort(key=lambda r: -r[2])
        out = args.out or os.path.join(tests_dir, "timings.txt")
        with open(out, "w") as fh:
            fh.write("# seconds\ttests\tfile (python3 tests/run2.py --time -j %d, %s)\n"
                     % (args.j, time.strftime("%Y-%m-%d %H:%M")))
            for name, code, secs, tests, verdict, _classes in rows:
                fh.write("%.1f\t%d\t%s\n" % (secs, tests, name))
            # test-slim-3: one row per class, so split() deals a big file by measured seconds
            fh.write("# classes: seconds\ttests\t<file>.<Class>\n")
            classes = [(s, n, key) for r in rows for key, (s, n) in r[5].items()]
            for s, n, key in sorted(classes, key=lambda c: (-c[0], c[2])):
                fh.write("%.1f\t%d\t%s\n" % (s, n, key))
        bad = [r for r in rows if r[1] != 0]
        budget = [TOTAL_LINES]
        for name, code, secs, tests, verdict, _classes in rows:
            print("%7.1f  %5d  %s%s" % (secs, tests, name, "" if code == 0 else "  " + verdict))
        print("files %d  tests %d  sum of file seconds %.0f  wall %.0f s  (-j %d)  -> %s"
              % (len(rows), sum(r[3] for r in rows), sum(r[2] for r in rows),
                 time.time() - start, args.j, out))
        for name, code, secs, tests, verdict, _classes in bad:
            print("FAILED %s" % name)
            for line in capped(failure_lines(texts.get(name, "")), budget):
                print(line)
        return 1 if bad else 0

    ok_files = all_skip_ok(root)
    reasons = {}
    listing = loader_listing(tests_dir, names, reasons)
    runnable = [n for n in names if n not in reasons]
    groups = split(runnable, read_timings(os.path.join(tests_dir, "timings.txt")), max(1, args.j), listing)

    def go(i_group):
        i, (mods, est) = i_group
        time.sleep(0.2 * i)   # start one by one, so each start sees the memory of the last
        wait_for_room()
        return i, mods, est, run_unittest(tests_dir, mods, os.path.join(logs, "group%d.log" % (i + 1)))

    results = []
    if groups:
        with ThreadPoolExecutor(max_workers=len(groups)) as pool:
            results = list(pool.map(go, enumerate(groups)))
    failed = False
    budget = [TOTAL_LINES]
    ran_by_file, skipped_by_file = {}, {}
    for i, mods, est, (code, secs, text, counts, _class_secs, skips) in results:
        tests, verdict = summary(text)
        for item, n in counts.items():
            ran_by_file[item.split(".")[0]] = ran_by_file.get(item.split(".")[0], 0) + n
        for item, n in skips.items():
            skipped_by_file[item.split(".")[0]] = skipped_by_file.get(item.split(".")[0], 0) + n
        print("process %d: %d files or classes, %d tests, %.0f s (planned %.0f s): %s"
              % (i + 1, len(mods), tests, secs, est, verdict))
        if code != 0:
            failed = True
            for block in re.findall(r"^(?:FAIL|ERROR): .*$", text, re.M):
                print("  " + block)
            for line in capped(failure_lines(text), budget):
                print(line)
    print("wall %.0f s, %d processes (-j %d)" % (time.time() - start, len(groups), args.j))
    for n in names:
        if n in reasons:
            print("NOT LISTED: %s could not be listed: %s" % (n, reasons[n]))
            failed = True
    unlisted = [n for n in runnable if listing.get(n) is None]
    if unlisted:
        print("count check skipped: the loader could not list %s" % ", ".join(unlisted))
    for n in runnable:
        if listing.get(n) is not None:
            line = count_mismatch(sum(c for _, c in listing[n]), ran_by_file.get(n, 0))
            if line:
                print("%s in %s" % (line, n))
                failed = True
    for n in runnable:
        ran = ran_by_file.get(n, 0)
        if ran > 0 and skipped_by_file.get(n, 0) == ran and n not in ok_files:
            print("ALL SKIPPED: %s: %d of %d tests skipped, none ran (if that is right: "
                  "all_skip_ok=%s: <reason> in agent_repo.conf)" % (n, ran, ran, n))
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
