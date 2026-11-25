"""Tests of bin/agent_test_time.py: run any repo's test files one by one, N at a time, and
report seconds, peak MB and exit code per file, slowest first (the test-slim skill, step 1).

requirements/test-slim.md. One class per feature.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "bin", "agent_test_time.py")

# A fake "test file" holds: seconds to sleep, exit code, MB to allocate.
FAKE_RUNNER = (
    "import sys, time\n"
    "secs, code, mb = open(sys.argv[1]).read().split()\n"
    "block = bytearray(int(mb) * 1024 * 1024)\n"
    "for i in range(0, len(block), 4096):\n"
    "    block[i] = 1\n"
    "time.sleep(float(secs))\n"
    "print('ran', sys.argv[1])\n"
    "sys.exit(int(code))\n"
)


class TimeCase(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(TOOL):
            self.fail("bin/agent_test_time.py does not exist yet. Write it.")
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="test_time_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        os.makedirs(os.path.join(self.base, "tests", "deep"))
        with open(os.path.join(self.base, "runner.py"), "w") as fh:
            fh.write(FAKE_RUNNER)

    def fake(self, rel, secs=0.0, code=0, mb=0):
        path = os.path.join(self.base, rel)
        with open(path, "w") as fh:
            fh.write("%s %d %d\n" % (secs, code, mb))
        return rel

    def cmd(self):
        return "%s runner.py {file}" % sys.executable

    def run_tool(self, *args, timeout=120):
        return subprocess.run([sys.executable, TOOL] + list(args), cwd=self.base,
                              capture_output=True, text=True, timeout=timeout)

    def rows(self, path):
        with open(path) as fh:
            return [l.rstrip("\n").split("\t") for l in fh if l.strip() and not l.startswith("#")]


class TestOneRowPerFile(TimeCase):
    def test_each_file_runs_once_with_its_name_in_the_command(self):
        a = self.fake("tests/test_a.py", 0.2)
        b = self.fake("tests/test_b.py", 0.0)
        out = os.path.join(self.base, "times.tsv")
        r = self.run_tool("--cmd", self.cmd(), "--out", out, a, b)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = self.rows(out)
        self.assertEqual(sorted(row[-1] for row in rows), [a, b])
        self.assertEqual(len(rows), 2)

    def test_rows_are_slowest_first_with_seconds_peak_mb_exit_file(self):
        a = self.fake("tests/test_a.py", 0.0)
        b = self.fake("tests/test_b.py", 0.6)
        out = os.path.join(self.base, "times.tsv")
        self.run_tool("--cmd", self.cmd(), "--out", out, a, b)
        rows = self.rows(out)
        self.assertEqual([row[-1] for row in rows], [b, a])
        secs, mb, code = float(rows[0][0]), float(rows[0][1]), int(rows[0][2])
        self.assertGreaterEqual(secs, 0.5)
        self.assertGreaterEqual(mb, 0)
        self.assertEqual(code, 0)

    def test_a_glob_finds_files_in_sub_folders(self):
        self.fake("tests/test_a.py")
        self.fake("tests/deep/test_b.py")
        self.fake("tests/helper.py")
        out = os.path.join(self.base, "times.tsv")
        r = self.run_tool("--cmd", self.cmd(), "--files", "tests/**/test_*.py", "--out", out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(row[-1] for row in self.rows(out)),
                         ["tests/deep/test_b.py", "tests/test_a.py"])


class TestFailures(TimeCase):
    def test_a_failing_file_is_a_row_and_the_exit_is_1(self):
        bad = self.fake("tests/test_bad.py", 0.0, code=3)
        good = self.fake("tests/test_good.py", 0.0)
        out = os.path.join(self.base, "times.tsv")
        r = self.run_tool("--cmd", self.cmd(), "--out", out, bad, good)
        self.assertEqual(r.returncode, 1)
        codes = {row[-1]: int(row[2]) for row in self.rows(out)}
        self.assertEqual(codes, {bad: 3, good: 0})
        self.assertIn(bad, r.stdout)

    def test_usage_errors_exit_2(self):
        a = self.fake("tests/test_a.py")
        for args in ([a], ["--cmd", "python3 x.py", a], ["--cmd", self.cmd()], ["--nope"]):
            with self.subTest(args=args):
                r = self.run_tool(*args)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


class TestReport(TimeCase):
    def test_the_printout_names_the_slowest_and_a_summary(self):
        names = [self.fake("tests/test_%d.py" % i, 0.05 * i) for i in range(5)]
        out = os.path.join(self.base, "times.tsv")
        r = self.run_tool("--cmd", self.cmd(), "--out", out, "--top", "2", *names)
        lines = r.stdout.splitlines()
        shown = [n for n in names if any(l.endswith(n) for l in lines)]
        self.assertEqual(shown, [names[4], names[3]])
        summary = [l for l in lines if l.startswith("files ")]
        self.assertEqual(len(summary), 1, r.stdout)
        for word in ("files 5", "failed 0", "sum ", "wall "):
            self.assertIn(word, summary[0])

    def test_peak_mb_is_measured(self):
        big = self.fake("tests/test_big.py", 0.0, mb=60)
        out = os.path.join(self.base, "times.tsv")
        self.run_tool("--cmd", self.cmd(), "--out", out, big)
        self.assertGreaterEqual(float(self.rows(out)[0][1]), 50)


class TestParallel(TimeCase):
    def test_j_runs_files_side_by_side(self):
        names = [self.fake("tests/test_%d.py" % i, 0.8) for i in range(4)]
        out = os.path.join(self.base, "times.tsv")
        start = time.time()
        r = self.run_tool("--cmd", self.cmd(), "-j", "4", "--out", out, *names)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLess(time.time() - start, 2.6)

    def test_j_1_runs_one_at_a_time(self):
        names = [self.fake("tests/test_%d.py" % i, 0.4) for i in range(3)]
        out = os.path.join(self.base, "times.tsv")
        start = time.time()
        self.run_tool("--cmd", self.cmd(), "-j", "1", "--out", out, *names)
        self.assertGreaterEqual(time.time() - start, 1.2)


class TestHelp(unittest.TestCase):
    def test_help_names_the_options_and_the_load_rule(self):
        r = subprocess.run([sys.executable, TOOL, "-h"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        for word in ("--cmd", "{file}", "--files", "-j", "--out", "--top", "80%"):
            with self.subTest(word=word):
                self.assertIn(word, r.stdout)


if __name__ == "__main__":
    unittest.main()
