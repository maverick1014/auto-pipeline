"""Tests of tests/run2.py: a split never loses a test, and the run is checked
against what the unittest loader discovers.
"""

import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RUN2 = os.path.join(HERE, "run2.py")

HELPER = '''import unittest


class BaseCase(unittest.TestCase):
    def test_base_one(self):
        pass

    def test_base_two(self):
        pass
'''

BIG = '''import unittest

from helper_base import BaseCase


class TestInherited(BaseCase):
    pass


class TestOwnA(unittest.TestCase):
    def test_a(self):
        pass


class TestOwnB(unittest.TestCase):
    def test_b(self):
        pass
'''

SMALL = '''import unittest


class TestSmall(unittest.TestCase):
    def test_small(self):
        pass
'''

TIMINGS = "# seconds\ttests\tfile\n10.0\t5\ttest_big\n1.0\t1\ttest_small\n"


def load_run2():
    spec = importlib.util.spec_from_file_location("run2_under_test", RUN2)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSplitKeepsInheritedClasses(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="run2_test_")
        self.addCleanup(shutil.rmtree, self.root, True)
        tests = os.path.join(self.root, "tests")
        os.makedirs(tests)
        for name, text in (("helper_base.py", HELPER), ("test_big.py", BIG),
                           ("test_small.py", SMALL), ("timings.txt", TIMINGS)):
            with open(os.path.join(tests, name), "w") as fh:
                fh.write(text)

    def run_runner(self, *extra):
        return subprocess.run([sys.executable, RUN2, "--root", self.root, "-j", "2"] + list(extra),
                              capture_output=True, text=True, timeout=120)

    def test_all_tests_of_a_split_file_run(self):
        out = self.run_runner()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        # BaseCase (2, imported into test_big), TestInherited (2), A, B, small = 7
        total = sum(int(w) for line in out.stdout.splitlines() if line.startswith("process ")
                    for w in [line.split(", ")[1].split()[0]])
        self.assertEqual(total, 7, out.stdout)
        self.assertNotIn("COUNT MISMATCH", out.stdout)

    def test_the_loader_lists_the_inherited_class(self):
        run2 = load_run2()
        listing = run2.loader_listing(os.path.join(self.root, "tests"), ["test_big"])
        classes = dict(listing["test_big"])
        self.assertEqual(classes.get("TestInherited"), 2, listing)


# a file the loader cannot list exactly (load_tests: only the whole file is right)
UNLISTED = '''import unittest


def load_tests(loader, tests, pattern):
    return tests


class TestUnlisted(unittest.TestCase):
    def test_one(self):
        pass
'''

# a listable file whose run has one test more than the listing: the listing runs
# under `python -c`, the run under `python -m unittest`
MOVING = '''import sys
import unittest


class TestMoving(unittest.TestCase):
    def test_one(self):
        pass

    if sys.argv[0] != "-c":
        def test_only_in_the_run(self):
            pass
'''


class TestCountCheckPerFile(unittest.TestCase):
    """One file that cannot be listed skips the count check for that file only;
    the other files are still checked, one by one."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="run2_test_")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.tests = os.path.join(self.root, "tests")
        os.makedirs(self.tests)
        self.write("test_small.py", SMALL)
        self.write("test_unlisted.py", UNLISTED)

    def write(self, name, text):
        with open(os.path.join(self.tests, name), "w") as fh:
            fh.write(text)

    def run_runner(self, *extra):
        return subprocess.run([sys.executable, RUN2, "--root", self.root] + list(extra),
                              capture_output=True, text=True, timeout=120)

    def test_the_unlisted_file_is_named_and_the_run_passes(self):
        out = self.run_runner("-j", "1")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        skipped = [l for l in out.stdout.splitlines() if "count check skipped" in l]
        self.assertEqual(len(skipped), 1, out.stdout)
        self.assertIn("test_unlisted", skipped[0])
        self.assertNotIn("test_small", skipped[0])
        self.assertNotIn("COUNT MISMATCH", out.stdout)

    def test_a_listed_file_is_still_checked(self):
        self.write("test_moving.py", MOVING)
        for jobs in ("1", "2"):
            with self.subTest(j=jobs):
                out = self.run_runner("-j", jobs)
                self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
                bad = [l for l in out.stdout.splitlines() if "COUNT MISMATCH" in l]
                self.assertTrue(bad, out.stdout)
                self.assertTrue(any("test_moving" in l for l in bad), out.stdout)
                self.assertFalse(any("test_small" in l or "test_unlisted" in l for l in bad), out.stdout)


ENV_SEEN = '''import os
import unittest


class TestSeen(unittest.TestCase):
    def test_writes_the_mark(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.txt"), "w") as fh:
            fh.write(os.environ.get("AGENT_FULL_RUN", ""))
'''


class TestFullRunMark(unittest.TestCase):
    """approval-design F (requirements/check-blocks.md section 53 F): run2 with no file named is the full suite
    (the release run and the nightly, full_cmd) and marks its processes AGENT_FULL_RUN=1, so a heavy test runs
    there and never in a task's run of named files."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="run2_test_")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.tests = os.path.join(self.root, "tests")
        os.makedirs(self.tests)
        with open(os.path.join(self.tests, "test_seen.py"), "w") as fh:
            fh.write(ENV_SEEN)
        with open(os.path.join(self.tests, "test_small.py"), "w") as fh:
            fh.write(SMALL)

    def seen(self, *extra):
        env = dict(os.environ)
        env.pop("AGENT_FULL_RUN", None)
        out = subprocess.run([sys.executable, RUN2, "--root", self.root, "-j", "1"] + list(extra),
                             capture_output=True, text=True, timeout=120, env=env)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        with open(os.path.join(self.tests, "seen.txt")) as fh:
            return fh.read()

    def test_the_full_suite_is_marked(self):
        self.assertEqual(self.seen(), "1")

    def test_named_files_are_not_marked(self):
        self.assertEqual(self.seen("test_seen"), "")
        self.assertEqual(self.seen("test_seen", "test_small"), "")

    def test_r5_a_named_run_clears_an_inherited_mark(self):
        # FIX ORDER 1 R5: a task's named run inside a full run (or a shell that kept the mark) never runs heavy tests
        env = dict(os.environ, AGENT_FULL_RUN="1")
        out = subprocess.run([sys.executable, RUN2, "--root", self.root, "-j", "1", "test_seen"],
                             capture_output=True, text=True, timeout=120, env=env)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        with open(os.path.join(self.tests, "seen.txt")) as fh:
            self.assertEqual(fh.read(), "")


class TestCountCheck(unittest.TestCase):
    def test_a_difference_prints_the_line(self):
        run2 = load_run2()
        self.assertEqual(run2.count_mismatch(7, 5), "COUNT MISMATCH: discovered 7, ran 5")

    def test_equal_counts_print_nothing(self):
        run2 = load_run2()
        self.assertIsNone(run2.count_mismatch(7, 7))



class TestClassSeconds(unittest.TestCase):
    """test-slim-3: a big file is dealt out class by class; its classes cost what was
    measured for them (rows "<seconds> <tests> <file>.<Class>" in timings.txt, written by
    --time), not the file's seconds shared out by test count (one class of start costs
    5 s a test, another 0.1 s). A class with no row keeps the old share."""

    def test_the_split_uses_the_measured_class_seconds(self):
        run2 = load_run2()
        listing = {"test_big": [("TestFast", 9), ("TestSlow", 1)], "test_x": None, "test_y": None}
        timings = {"test_big": 90.0, "test_big.TestSlow": 80.0, "test_big.TestFast": 10.0,
                   "test_x": 30.0, "test_y": 30.0}
        groups = run2.split(["test_big", "test_x", "test_y"], timings, 2, listing)
        self.assertEqual(groups, [(["test_big.TestSlow"], 80.0),
                                  (["test_x", "test_y", "test_big.TestFast"], 70.0)])

    def test_without_class_rows_the_share_follows_the_test_count(self):
        run2 = load_run2()
        listing = {"test_big": [("TestFast", 9), ("TestSlow", 1)], "test_x": None, "test_y": None}
        groups = run2.split(["test_big", "test_x", "test_y"], {"test_big": 90.0, "test_x": 30.0,
                                                               "test_y": 30.0}, 2, listing)
        self.assertEqual(groups, [(["test_big.TestFast"], 81.0),
                                  (["test_x", "test_y", "test_big.TestSlow"], 69.0)])

    def test_time_writes_a_row_per_class(self):
        root = tempfile.mkdtemp(prefix="run2_test_")
        self.addCleanup(shutil.rmtree, root, True)
        tests = os.path.join(root, "tests")
        os.makedirs(tests)
        for name, text in (("helper_base.py", HELPER), ("test_big.py", BIG), ("test_small.py", SMALL)):
            with open(os.path.join(tests, name), "w") as fh:
                fh.write(text)
        out_file = os.path.join(root, "t.txt")
        done = subprocess.run([sys.executable, RUN2, "--root", root, "-j", "2", "--time", "--out", out_file],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        rows = {}
        with open(out_file) as fh:
            for line in fh:
                if line.strip() and not line.startswith("#"):
                    secs, n, name = line.rstrip("\n").split("\t")
                    rows[name] = int(n)
        self.assertEqual(rows, {"test_big": 6, "test_small": 1, "test_big.BaseCase": 2,
                                "test_big.TestInherited": 2, "test_big.TestOwnA": 1,
                                "test_big.TestOwnB": 1, "test_small.TestSmall": 1})
        timings = load_run2().read_timings(out_file)
        self.assertEqual(sorted(timings), sorted(rows))


class TestDirectTools(unittest.TestCase):
    """test-slim-3 (tests/fasttools.py): on macOS the test run finds git and python3
    without the xcrun shim: the very binaries the shim would start; elsewhere,
    or with AGENT_TEST_SHIMS=1, nothing changes."""

    def call(self, env_extra, code):
        env = {k: v for k, v in os.environ.items()
               if k not in ("AGENT_TEST_TOOLS", "PYTHONPYCACHEPREFIX")}
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                      if "agent_test_tools_" not in p)
        env.update(env_extra)
        script = ("import json, os, shutil, sys; sys.path.insert(0, %r)\n"
                  "from fasttools import direct_tools\n%s" % (HERE, code))
        done = subprocess.run([sys.executable, "-c", script], env=env,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def test_the_same_binaries_without_the_shim(self):
        if sys.platform != "darwin":
            # no xcrun shims: nothing changes
            out = self.call({}, "print(json.dumps([direct_tools(), os.environ.get('AGENT_TEST_TOOLS'),"
                                " os.environ.get('PYTHONPYCACHEPREFIX')]))")
            self.assertEqual(__import__("json").loads(out), [None, None, None])
            return
        out = self.call({}, "folder = direct_tools()\n"
                            "print(json.dumps([folder, os.environ['PATH'].split(os.pathsep)[0],"
                            " shutil.which('git'), shutil.which('python3'),"
                            " os.environ.get('PYTHONPYCACHEPREFIX'), direct_tools(),"
                            " os.path.realpath(shutil.which('git')), os.path.realpath(shutil.which('python3'))]))")
        folder, first, git, py, prefix, again, git_real, py_real = __import__("json").loads(out)
        self.assertIsNone(again, "a second call changes nothing")
        for name, found, found_real in (("git", git, git_real), ("python3", py, py_real)):
            shim = shutil.which(name) == "/usr/bin/" + name or found.startswith(folder or "-")
            if not shim:
                continue
            self.assertEqual(first, folder)
            self.assertEqual(found, os.path.join(folder, name))
            real = subprocess.run(["xcrun", "--find", name], capture_output=True, text=True).stdout.strip()
            self.assertEqual(found_real, os.path.realpath(real))
        if getattr(sys, "pycache_prefix", None):
            self.assertEqual(prefix, os.path.join(folder, "pycache"))

    def test_the_old_way_on_request(self):
        out = self.call({"AGENT_TEST_SHIMS": "1"},
                        "print(json.dumps([direct_tools(), os.environ.get('AGENT_TEST_TOOLS'),"
                        " os.environ.get('PYTHONPYCACHEPREFIX')]))")
        self.assertEqual(__import__("json").loads(out), [None, None, None])


# ------------------------------------------------------------------ runner-integrity
# requirements/runner-integrity.md: a run is never green for a file that did not really run,
# and run2 leaves no run2_* folder of its own behind. Fixture files live under temp folders,
# never in tests/; every run gets an empty TMPDIR of the test's own, so run2 makes and sweeps
# its folders there and nowhere else.

MARKER = ".run2_owner"   # in run2's folder: {"pid": <run2's pid>, "start": <that process's start time>}

EXITS = "import sys\nsys.exit(0)\n"
OS_EXIT = "import os\nos._exit(0)\n"
RAISES = "raise RuntimeError('broken at import')\n"
IMPORTS_MISSING = "import no_such_module_runner_integrity\n"
NO_TESTS = "import unittest\n"

SKIPPED = '''import unittest


class TestSkipped(unittest.TestCase):
    @unittest.skip("later")
    def test_later(self):
        pass
'''

HALF_SKIPPED = '''import unittest


class TestHalf(unittest.TestCase):
    @unittest.skip("later")
    def test_later(self):
        pass

    def test_now(self):
        pass
'''

# two classes, every test skipped; the timings make run2 deal it out class by class (-j 2)
BIG_SKIPPED = '''import unittest


@unittest.skip("later")
class TestSkipA(unittest.TestCase):
    def test_a(self):
        pass


@unittest.skip("later")
class TestSkipB(unittest.TestCase):
    def test_b(self):
        pass
'''
BIG_SKIPPED_TIMINGS = "# seconds\ttests\tfile\n10.0\t2\ttest_bigskip\n1.0\t1\ttest_small\n"

FAILING = '''import unittest


class TestFailing(unittest.TestCase):
    def test_fail(self):
        self.assertEqual(1, 2, "runner-integrity-detail")
'''

# writes its pid to tests/started (atomically), then sleeps far longer than any test waits
SLOW = '''import os
import time
import unittest


class TestSlow(unittest.TestCase):
    def test_slow(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "started.tmp"), "w") as fh:
            fh.write(str(os.getpid()))
        os.replace(os.path.join(here, "started.tmp"), os.path.join(here, "started"))
        time.sleep(90)
'''


def fixture_root(case, files):
    """A repo root under a temp folder: tests/<name> per file; agent_repo.conf at the root."""
    root = tempfile.mkdtemp(prefix="r2fix_")
    case.addCleanup(shutil.rmtree, root, True)
    os.makedirs(os.path.join(root, "tests"))
    for name, text in files.items():
        path = os.path.join(root, name) if name == "agent_repo.conf" else os.path.join(root, "tests", name)
        with open(path, "w") as fh:
            fh.write(text)
    return root


def own_tmp(case):
    tmp = tempfile.mkdtemp(prefix="r2tmp_")
    case.addCleanup(shutil.rmtree, tmp, True)
    return tmp


def run2_env(tmp, own_tools=False):
    env = dict(os.environ)
    env.pop("AGENT_FULL_RUN", None)
    env["TMPDIR"] = tmp
    if own_tools:
        # as from a plain shell: run2 makes its own fasttools folder (macOS), in this TMPDIR
        for k in ("AGENT_TEST_TOOLS", "PYTHONPYCACHEPREFIX"):
            env.pop(k, None)
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                      if "agent_test_tools_" not in p)
    return env


def run_run2(root, tmp, *extra):
    cmd = [sys.executable, RUN2] + (["--root", root] if root else []) + list(extra)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=run2_env(tmp))


def left(tmp):
    """The run2_* entries in a TMPDIR."""
    return sorted(n for n in os.listdir(tmp) if n.startswith("run2_"))


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for(path, limit_s=30):
    end = time.time() + limit_s
    while time.time() < end:
        if os.path.exists(path):
            with open(path) as fh:
                return fh.read()
        time.sleep(0.05)
    raise AssertionError("never appeared: %s" % path)


def start_slow_run(case, tmp, own_tools=False):
    """(Popen of run2 on one slow test, the slow test's pid), once that test runs."""
    root = fixture_root(case, {"test_slow.py": SLOW})
    proc = subprocess.Popen([sys.executable, RUN2, "--root", root, "-j", "1"], env=run2_env(tmp, own_tools),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            start_new_session=True)

    def stop():
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
        proc.communicate(timeout=30)
    case.addCleanup(stop)
    test_pid = int(wait_for(os.path.join(root, "tests", "started")))
    case.addCleanup(lambda: alive(test_pid) and os.kill(test_pid, signal.SIGKILL))
    return proc, test_pid


class TestNotListedIsRed(unittest.TestCase):
    """Rule 1: a file the loader cannot list (any exit, exception or zero test ids at import)
    makes the run RED with one line naming the file and the reason; the other files are still
    listed as before."""

    CASES = (("test_exits", EXITS, r"exit"),
             ("test_osexit", OS_EXIT, r"exit"),
             ("test_raises", RAISES, r"RuntimeError"),
             ("test_missing", IMPORTS_MISSING, r"ModuleNotFoundError|No module named"),
             ("test_empty", NO_TESTS, r"no tests"))

    def test_each_kind_is_red_with_one_line_and_its_reason(self):
        for name, text, why in self.CASES:
            for jobs in ("1", "2"):
                with self.subTest(file=name, j=jobs):
                    root = fixture_root(self, {name + ".py": text, "test_small.py": SMALL})
                    out = run_run2(root, own_tmp(self), "-j", jobs)
                    self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
                    lines = [l for l in out.stdout.splitlines() if "could not be listed" in l]
                    self.assertEqual(len(lines), 1, out.stdout)
                    head = "NOT LISTED: %s could not be listed: " % name
                    self.assertTrue(lines[0].startswith(head), lines[0])
                    self.assertRegex(lines[0][len(head):], re.compile(why, re.I))

    def test_a_sys_exit_file_alone_in_its_process_is_red(self):
        # the hole the reviews found: alone in its process the run printed "count check skipped" and exit 0
        root = fixture_root(self, {"test_exits.py": EXITS})
        out = run_run2(root, own_tmp(self))
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("NOT LISTED: test_exits could not be listed: ", out.stdout)

    def test_a_listable_suite_has_no_such_line_and_stays_green(self):
        root = fixture_root(self, {"helper_base.py": HELPER, "test_big.py": BIG, "test_small.py": SMALL})
        for jobs in ("1", "2"):
            with self.subTest(j=jobs):
                out = run_run2(root, own_tmp(self), "-j", jobs)
                self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
                self.assertNotIn("could not be listed", out.stdout)
                self.assertNotIn("ALL SKIPPED", out.stdout)


class TestAllSkippedIsRed(unittest.TestCase):
    """Rule 2: a file where every test was skipped makes the run RED, naming the file, unless
    agent_repo.conf lists it in all_skip_ok with its reason (one all_skip_ok=<file>: <reason>
    line per file)."""

    def red(self, out, name):
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        lines = [l for l in out.stdout.splitlines() if l.startswith("ALL SKIPPED: ")]
        self.assertEqual(len(lines), 1, out.stdout)
        self.assertTrue(lines[0].startswith("ALL SKIPPED: %s" % name), lines[0])
        self.assertNotRegex(lines[0], r"^\s*(?:FAIL|ERROR): ")   # the nightly never reads it as a test

    def test_full_run_and_named_run_are_red(self):
        for extra in ((), ("test_skipped", "test_small")):
            with self.subTest(named=bool(extra)):
                root = fixture_root(self, {"test_skipped.py": SKIPPED, "test_small.py": SMALL})
                self.red(run_run2(root, own_tmp(self), "-j", "1", *extra), "test_skipped")

    def test_a_file_dealt_out_class_by_class_counts_as_one_file(self):
        root = fixture_root(self, {"test_bigskip.py": BIG_SKIPPED, "test_small.py": SMALL,
                                   "timings.txt": BIG_SKIPPED_TIMINGS})
        out = run_run2(root, own_tmp(self), "-j", "2")
        self.assertEqual(len([l for l in out.stdout.splitlines() if l.startswith("process ")]), 2, out.stdout)
        self.red(out, "test_bigskip")

    def test_one_test_run_is_enough(self):
        root = fixture_root(self, {"test_half.py": HALF_SKIPPED, "test_small.py": SMALL})
        out = run_run2(root, own_tmp(self), "-j", "1")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertNotIn("ALL SKIPPED", out.stdout)

    def test_listed_in_all_skip_ok_with_a_reason_is_green(self):
        for entry in ("test_skipped", "test_skipped.py", "tests/test_skipped.py"):
            with self.subTest(entry=entry):
                conf = "version=1\nall_skip_ok=%s: needs a tool this machine lacks\n" % entry
                root = fixture_root(self, {"test_skipped.py": SKIPPED, "test_small.py": SMALL,
                                           "agent_repo.conf": conf})
                out = run_run2(root, own_tmp(self), "-j", "1")
                self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
                self.assertNotIn("ALL SKIPPED", out.stdout)

    def test_an_entry_without_a_reason_is_ignored_and_said(self):
        for line in ("all_skip_ok=test_skipped", "all_skip_ok=test_skipped:   "):
            with self.subTest(line=line):
                root = fixture_root(self, {"test_skipped.py": SKIPPED, "test_small.py": SMALL,
                                           "agent_repo.conf": "version=1\n%s\n" % line})
                out = run_run2(root, own_tmp(self), "-j", "1")
                self.red(out, "test_skipped")
                said = [l for l in out.stdout.splitlines() if "all_skip_ok" in l and "no reason" in l]
                self.assertEqual(len(said), 1, out.stdout)
                self.assertIn("test_skipped", said[0])


LONG = """import unittest


class TestLong(unittest.TestCase):
    def test_long(self):
        self.fail("\\n".join("line-%03d" % i for i in range(1, 201)))
"""

NIGHTLY_RED = """import unittest


class TestRed(unittest.TestCase):
    def test_fail(self):
        self.fail("FAIL: test_fake (test_trap.TestFake)\\nERROR: test_fake2 (test_trap.TestFake)")

    def test_error(self):
        raise RuntimeError("ERROR: test_fake3 (test_trap.TestFake)")

    def test_sub(self):
        for i in (1, 2, 3):
            with self.subTest(i=i):
                self.assertEqual(i, 1)

    def test_ok(self):
        pass
"""

# what run2 printed for NIGHTLY_RED before runner-integrity (origin/ap-main-maverick 78b565f, -j 1),
# the log path made neutral; the trap line test_fake2 comes from the old run2 too
OLD_RED_OUTPUT = """process 1: 1 files or classes, 4 tests, 0 s (planned 1 s): FAILED (failures=3, errors=1)
  log: <folder>/run2_old/group1.log
  ERROR: test_error (test_red.TestRed)
  FAIL: test_fail (test_red.TestRed)
  ERROR: test_fake2 (test_trap.TestFake)
  FAIL: test_sub (test_red.TestRed) (i=2)
  FAIL: test_sub (test_red.TestRed) (i=3)
wall 0 s, 1 processes (-j 1)
"""

CUT = re.compile(r"^  \| \.\.\. (\d+) more lines cut$")


class TestRedOutputCap(unittest.TestCase):
    """Main manager's answer 2 (TELL 386d601f): a red run prints each failed process's failure
    blocks inline, prefixed "  | ", at most 60 lines per failed process and 300 in total, then
    one line "  | ... <n> more lines cut" when cut; the nightly reads the same names as before."""

    def sections(self, stdout, head):
        """[(detail lines, cut count or None)] per section that starts with a line matching head."""
        out = []
        for line in stdout.splitlines():
            if re.match(head, line):
                out.append([[], None])
            elif out and line.startswith("  | "):
                m = CUT.match(line)
                if m:
                    self.assertIsNone(out[-1][1], "one cut line per failed process")
                    out[-1][1] = int(m.group(1))
                else:
                    self.assertIsNone(out[-1][1], "no detail line after the cut line")
                    out[-1][0].append(line)
        return [(d, c) for d, c in out]

    def check_one(self, detail, cut):
        self.assertTrue(detail, "the failure is shown")
        self.assertLessEqual(len(detail), 60, detail)
        shown = [l for l in detail if re.search(r"line-\d{3}$", l)]
        self.assertTrue(shown, detail)
        self.assertEqual(cut, 200 - len(shown), detail[-3:])

    def test_one_long_traceback_is_cut_at_60(self):
        root = fixture_root(self, {"test_long.py": LONG})
        out = run_run2(root, own_tmp(self), "-j", "1")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("  FAIL: test_long (test_long.TestLong)", out.stdout.splitlines())
        [(detail, cut)] = self.sections(out.stdout, r"^process \d+: ")
        self.check_one(detail, cut)

    def test_time_mode_has_the_same_cap(self):
        root = fixture_root(self, {"test_long.py": LONG})
        out = run_run2(root, own_tmp(self), "--time", "-j", "1", "--out", os.path.join(root, "t.txt"))
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        [(detail, cut)] = self.sections(out.stdout, r"^FAILED test_long$")
        self.check_one(detail, cut)

    def test_all_processes_together_show_at_most_300(self):
        files = dict(("test_long%d.py" % i, LONG) for i in range(1, 7))
        out = run_run2(fixture_root(self, files), own_tmp(self), "-j", "6")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        parts = self.sections(out.stdout, r"^process \d+: ")
        self.assertEqual(len(parts), 6, out.stdout)
        self.assertLessEqual(sum(len(d) for d, _ in parts), 300)
        self.assertTrue(all(len(d) <= 60 for d, _ in parts))
        whole = [len(d) + (c or 0) for d, c in parts]
        self.assertEqual(len(set(whole)), 1, "every cut says how many lines went: %s" % whole)
        self.assertTrue(all(c for _, c in parts), "every long block was cut")

    def test_the_nightly_reads_the_same_names_as_before(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        try:
            import agent_nightly
        finally:
            sys.path.pop(0)
        out = run_run2(fixture_root(self, {"test_red.py": NIGHTLY_RED}), own_tmp(self), "-j", "1")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        old = agent_nightly.failed_tests(OLD_RED_OUTPUT)
        self.assertEqual(len(old), 5, old)
        self.assertEqual(agent_nightly.failed_tests(out.stdout), old)
        self.assertIn("  | ", out.stdout)   # the new detail is there and adds no name


class TestThisRepoAllSkipOk(unittest.TestCase):
    """runner-integrity decision 1A: test_check_blocks_demo's one test runs only in the full run
    (AGENT_FULL_RUN=1, which run2 clears for named files), so a named run of it skips everything;
    this repo lists it in all_skip_ok with that reason, and a task that names it stays green."""

    def test_a_named_run_of_the_full_run_only_demo_is_green(self):
        out = run_run2(None, own_tmp(self), "-j", "1", "test_check_blocks_demo")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertNotIn("ALL SKIPPED", out.stdout)
        self.assertNotIn("no reason", out.stdout)


class TestNoFolderLeft(unittest.TestCase):
    """Rule 3: run2 removes its own temp folder when it ends: green, red, error or a stop
    (SIGINT, and SIGTERM as the test-run monitor sends). A red run still shows what failed,
    since its log folder is gone; the FAIL line and the exit codes stay as today (rule 5)."""

    def gone(self, tmp, out_text):
        self.assertEqual(left(tmp), [], out_text)
        for t in {tmp, os.path.realpath(tmp)}:
            self.assertNotIn(os.path.join(t, "run2_"), out_text, "a printed path into the removed folder")

    def test_green_run(self):
        tmp = own_tmp(self)
        out = run_run2(fixture_root(self, {"test_small.py": SMALL}), tmp, "-j", "1")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.gone(tmp, out.stdout + out.stderr)

    def test_red_run_shows_the_failure_inline(self):
        tmp = own_tmp(self)
        out = run_run2(fixture_root(self, {"test_failing.py": FAILING, "test_small.py": SMALL}), tmp, "-j", "1")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertRegex(out.stdout, re.compile(r"^  FAIL: test_fail \(test_failing\.TestFailing\)$", re.M))
        self.assertIn("runner-integrity-detail", out.stdout)
        # the detail lines never look like a FAIL/ERROR line to the nightly
        detail = [l for l in out.stdout.splitlines() if "runner-integrity-detail" in l]
        self.assertFalse([l for l in detail if re.match(r"^\s*(?:FAIL|ERROR): ", l)], detail)
        self.gone(tmp, out.stdout + out.stderr)

    def test_time_runs_green_and_red(self):
        for files, code in (({"test_small.py": SMALL}, 0), ({"test_failing.py": FAILING}, 1)):
            with self.subTest(code=code):
                tmp = own_tmp(self)
                root = fixture_root(self, files)
                out = run_run2(root, tmp, "--time", "-j", "1", "--out", os.path.join(root, "t.txt"))
                self.assertEqual(out.returncode, code, out.stdout + out.stderr)
                if code:
                    self.assertIn("runner-integrity-detail", out.stdout)
                self.gone(tmp, out.stdout + out.stderr)

    def test_an_error_inside_run2(self):
        tmp = own_tmp(self)
        root = fixture_root(self, {"test_small.py": SMALL})
        script = ("import importlib.util, sys\n"
                  "spec = importlib.util.spec_from_file_location('run2_err', %r)\n"
                  "mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)\n"
                  "def broken(*a, **k):\n    raise RuntimeError('broken inside run2')\n"
                  "mod.loader_listing = broken\nmod.split = broken\n"
                  "sys.argv = ['run2.py', '--root', %r, '-j', '1']\n"
                  "sys.exit(mod.main())\n" % (RUN2, root))
        out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                             timeout=120, env=run2_env(tmp))
        self.assertNotEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("broken inside run2", out.stderr)
        self.gone(tmp, out.stdout + out.stderr)

    def test_once_a_stop_came_no_process_puts_a_file_in_the_folder(self):
        # verify finding: a group starting while the signal lands wrote its runner and log into the
        # folder after the folder was removed, which left an unmarked run2_* folder for good
        run2 = load_run2()
        root = fixture_root(self, {"test_small.py": SMALL})
        folder = own_tmp(self)
        run2.STOPPING[0] = True
        with self.assertRaises(Exception):
            run2.run_unittest(os.path.join(root, "tests"), ["test_small"], os.path.join(folder, "group1.log"))
        self.assertEqual(os.listdir(folder), [])

    def test_a_stopped_run_leaves_no_folder_and_no_test_process(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=sig.name):
                tmp = own_tmp(self)
                proc, test_pid = start_slow_run(self, tmp, own_tools=True)
                self.assertEqual(len(left(tmp)), 1, "run2 makes one folder")
                os.kill(proc.pid, sig)            # run2 alone, not its group: it stops its own test processes
                text, _ = proc.communicate(timeout=20)   # the slow test sleeps 90 s: waiting for it fails here
                self.assertNotEqual(proc.returncode, 0, text)
                self.gone(tmp, text)
                # verify finding: a re-sent signal skips atexit, so fasttools' folder (macOS) stayed
                self.assertEqual([n for n in os.listdir(tmp) if n.startswith("agent_test_tools_")], [])
                end = time.time() + 5
                while alive(test_pid) and time.time() < end:
                    time.sleep(0.05)
                self.assertFalse(alive(test_pid), "the test process outlived the stopped run")


class TestStaleFolders(unittest.TestCase):
    """Rule 4: at start run2 removes an old run2_* folder only when a marker inside names a pid
    and start time and that process no longer runs; no marker, an unreadable one, one without a
    start time or a live process: never touched. Links and plain files are never touched."""

    def plant(self, tmp, name, marker=None, raw=None):
        path = os.path.join(tmp, name)
        os.makedirs(path)
        with open(os.path.join(path, "group1.log"), "w") as fh:
            fh.write("kept?\n")
        if marker is not None:
            with open(os.path.join(path, MARKER), "w") as fh:
                json.dump(marker, fh)
        if raw is not None:
            with open(os.path.join(path, MARKER), "w") as fh:
                fh.write(raw)
        return path

    def test_only_folders_of_dead_runs_go(self):
        tmp = own_tmp(self)
        live, _test_pid = start_slow_run(self, tmp)
        [own] = left(tmp)
        with open(os.path.join(tmp, own, MARKER)) as fh:
            mark = json.load(fh)
        self.assertEqual(mark.get("pid"), live.pid, mark)
        self.assertTrue(mark.get("start"), mark)
        start = mark["start"]
        other = start + 1 if isinstance(start, (int, float)) else str(start) + " (another process)"
        gone_proc = subprocess.Popen([sys.executable, "-c", "pass"])
        gone_proc.wait()
        dead = gone_proc.pid
        outside = own_tmp(self)
        self.plant(outside, "target", {"pid": dead, "start": start})

        self.plant(tmp, "run2_dead", {"pid": dead, "start": start})
        self.plant(tmp, "run2_reused", {"pid": live.pid, "start": other})   # the pid now names another process
        self.plant(tmp, "run2_twin", dict(mark))                             # a live run: same pid, same start
        self.plant(tmp, "run2_nomarker")
        self.plant(tmp, "run2_garbled", raw="not json\n")
        self.plant(tmp, "run2_nostart", {"pid": dead})
        with open(os.path.join(tmp, "run2_file"), "w") as fh:
            fh.write("a file, not a folder\n")
        os.symlink(os.path.join(outside, "target"), os.path.join(tmp, "run2_link"))

        out = run_run2(fixture_root(self, {"test_small.py": SMALL}), tmp, "-j", "1")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(left(tmp), sorted([own, "run2_twin", "run2_nomarker", "run2_garbled",
                                            "run2_nostart", "run2_file", "run2_link"]), out.stdout)
        self.assertTrue(os.path.exists(os.path.join(outside, "target", "group1.log")))
        self.assertTrue(os.path.exists(os.path.join(tmp, "run2_nomarker", "group1.log")))

        os.kill(live.pid, signal.SIGINT)
        text, _ = live.communicate(timeout=20)
        self.assertNotIn(own, left(tmp), text)


if __name__ == "__main__":
    unittest.main()
