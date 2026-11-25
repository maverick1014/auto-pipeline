"""Tests of tests/sharedrepo.py: the shared_fixture guard.

A test body that writes into the guarded folder and THEN makes a new (not yet
remembered) call must fail that test, not leak into the baseline.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sharedrepo import shared_fixture  # noqa: E402


class FakeRepo:
    def __init__(self, base):
        self.base = base
        self.starts = 0

    def run(self, script, *args, **kwargs):
        self.starts += 1
        return (script, args, self.starts)


def build_case():
    @shared_fixture(guard="base", remember_repo=True)
    class Fixture(unittest.TestCase):
        def setUp(self):
            self.base = tempfile.mkdtemp(prefix="sharedrepo_test_")
            self.addCleanup(shutil.rmtree, self.base, True)
            self.repo = FakeRepo(self.base)

        def test_a_only_calls(self):
            self.repo.run("tool", "one")

        def test_b_writes_then_makes_a_new_call(self):
            with open(os.path.join(self.base, "leak.txt"), "w") as fh:
                fh.write("state")
            self.repo.run("tool", "two")

        def test_c_only_calls_again(self):
            self.repo.run("tool", "one")
            self.repo.run("tool", "three")

    return Fixture


def run_case(case):
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(case)
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    return result, stream.getvalue()


class TestGuardCatchesAWriteBeforeANewCall(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result, cls.text = run_case(build_case())
        cls.failed = {t.id().rsplit(".", 1)[1]: msg for t, msg in cls.result.failures}

    def test_the_writing_test_fails_with_the_path(self):
        self.assertIn("test_b_writes_then_makes_a_new_call", self.failed, self.text)
        self.assertIn("leak.txt", self.failed["test_b_writes_then_makes_a_new_call"])
        self.assertIn("changed the shared fixture", self.failed["test_b_writes_then_makes_a_new_call"])

    def test_a_test_that_only_makes_calls_passes(self):
        self.assertNotIn("test_a_only_calls", self.failed)
        self.assertNotIn("test_c_only_calls_again", self.failed)

    def test_the_write_does_not_fail_the_next_test(self):
        self.assertEqual(list(self.failed), ["test_b_writes_then_makes_a_new_call"], self.text)
        self.assertEqual(self.result.errors, [])


if __name__ == "__main__":
    unittest.main()
