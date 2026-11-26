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


class TestCountCheck(unittest.TestCase):
    def test_a_difference_prints_the_line(self):
        run2 = load_run2()
        self.assertEqual(run2.count_mismatch(7, 5), "COUNT MISMATCH: discovered 7, ran 5")

    def test_equal_counts_print_nothing(self):
        run2 = load_run2()
        self.assertIsNone(run2.count_mismatch(7, 7))


if __name__ == "__main__":
    unittest.main()
