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


class TestCountCheck(unittest.TestCase):
    def test_a_difference_prints_the_line(self):
        run2 = load_run2()
        self.assertEqual(run2.count_mismatch(7, 5), "COUNT MISMATCH: discovered 7, ran 5")

    def test_equal_counts_print_nothing(self):
        run2 = load_run2()
        self.assertIsNone(run2.count_mismatch(7, 7))


if __name__ == "__main__":
    unittest.main()
