"""Tests of tests/run2.py: a split never loses a test, and the run is checked
against what the unittest loader discovers.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
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

if __name__ == "__main__":
    unittest.main()
