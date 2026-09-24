"""Tests for bin/agent-resources.sh: the readers (already covered indirectly
by test_agent_start.py) plus the `relief` verb (S4).

relief only runs when the file is executed directly with the one argument
`relief` (guarded by `[ "${BASH_SOURCE[0]}" = "$0" ]`). Sourcing it must keep
defining functions and running nothing, exactly as before.

relief stops only two kinds of process:
  a. every "auto_pipeline_*/plugin/bin/agent-monitor.sh" process -- a monitor
     loop a test run left behind
  b. any other "agent-monitor.sh start" process whose repo has no live main
     manager (agent_main.lock missing, or its pid is dead)

Everything else just gets listed, never killed, in one table for the human.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase, ROOT

REAL_SCRIPT = os.path.join(ROOT, "bin", "agent-resources.sh")


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def wait_until(fn, timeout=8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if fn():
            return True
        time.sleep(0.1)
    return fn()


class TestSourcing(ScriptCase):
    script = "agent-resources.sh"

    def test_sourcing_defines_resources_ok_and_runs_nothing(self):
        self.repo.write_bin_script(
            "check.sh",
            "#!/usr/bin/env bash\nset -eu\n"
            "cd \"$(dirname \"$0\")\"\n"
            ". ./agent-resources.sh\n"
            "type resources_ok >/dev/null 2>&1 && echo has_resources_ok\n")
        out = self.assertOk(self.repo.run("check.sh",
                                          env={"AGENT_FAKE_RAM": "10",
                                               "AGENT_FAKE_CPU": "10"}))
        self.assertIn("has_resources_ok", out)
        self.assertNotIn("PROCESS | MB | CPU% | WHAT | SUGGEST", out)
        self.assertNotIn("stopped", out)

    def test_executing_with_no_argument_prints_usage_and_fails(self):
        result = self.repo.run("agent-resources.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage", (result.stdout + result.stderr).lower())


class TestReliefTable(ScriptCase):
    script = "agent-resources.sh"

    def test_relief_prints_the_human_table_and_the_resources_line(self):
        result = self.repo.run("agent-resources.sh", "relief",
                               env={"AGENT_FAKE_RAM": "10",
                                    "AGENT_FAKE_CPU": "10"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PROCESS | MB | CPU% | WHAT | SUGGEST", result.stdout)
        self.assertIn("RESOURCES: RAM 10% CPU 10% (cap 80%) -> OK",
                      result.stdout)
        self.assertIn("stopped 0 test monitors", result.stdout)


class TestReliefKillsTestMonitors(unittest.TestCase):
    """Uses the real installed script, not the copied plugin, so the fake
    process can sit at a literal auto_pipeline_*/plugin/bin/agent-monitor.sh
    path of our own choosing.
    """

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="relief_test_")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.proc = None
        self.addCleanup(self._kill_leftover)

    def _kill_leftover(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def test_relief_kills_a_fake_test_monitor_loop(self):
        fake_dir = os.path.join(self.base, "auto_pipeline_t3st", "plugin", "bin")
        os.makedirs(fake_dir)
        fake_monitor = os.path.join(fake_dir, "agent-monitor.sh")
        with open(fake_monitor, "w") as fh:
            fh.write("#!/usr/bin/env bash\nsleep 300\n")
        os.chmod(fake_monitor, 0o755)

        self.proc = subprocess.Popen(["bash", fake_monitor, "start"])
        self.assertTrue(wait_until(lambda: alive(self.proc.pid)),
                        "fake monitor never started")

        result = subprocess.run([REAL_SCRIPT, "relief"],
                                env=dict(os.environ, AGENT_FAKE_RAM="10",
                                         AGENT_FAKE_CPU="10"),
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("stopped 1 test monitors", result.stdout)
        # poll(), not os.kill: a killed child is a zombie (still answers
        # os.kill(pid, 0)) until this process reaps it with wait()/poll().
        self.assertTrue(wait_until(lambda: self.proc.poll() is not None),
                        "fake test monitor is still alive after relief")


class TestReliefLeavesALiveMainManagerAlone(unittest.TestCase):
    """A monitor whose repo's agent_main.lock names a live pid must survive."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="relief_repo_")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.repo_root = os.path.join(self.base, "somerepo")
        os.makedirs(self.repo_root)
        subprocess.run(["git", "init", "-q", self.repo_root], check=True,
                       capture_output=True)
        for key, value in (("user.email", "t@t.t"), ("user.name", "t")):
            subprocess.run(["git", "-C", self.repo_root, "config", key, value],
                           check=True, capture_output=True)
        with open(os.path.join(self.repo_root, "seed.txt"), "w") as fh:
            fh.write("x\n")
        subprocess.run(["git", "-C", self.repo_root, "add", "-A"], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", self.repo_root, "commit", "-q", "-m", "seed"],
                       check=True, capture_output=True)

        # a live main-manager lock: first field is our own (live) pid
        with open(os.path.join(self.repo_root, ".git", "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-09-24 00:00\n" % os.getpid())

        bin_dir = os.path.join(self.repo_root, "bin")
        os.makedirs(bin_dir)
        fake_monitor = os.path.join(bin_dir, "agent-monitor.sh")
        with open(fake_monitor, "w") as fh:
            fh.write("#!/usr/bin/env bash\nsleep 300\n")
        os.chmod(fake_monitor, 0o755)
        self.fake_monitor = fake_monitor

        self.proc = subprocess.Popen(["bash", fake_monitor, "start"],
                                     cwd=self.repo_root)
        self.addCleanup(self._kill_leftover)
        self.assertTrue(wait_until(lambda: alive(self.proc.pid)),
                        "fake monitor never started")

    def _kill_leftover(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def test_relief_does_not_kill_a_monitor_with_a_live_lock_owner(self):
        result = subprocess.run([REAL_SCRIPT, "relief"],
                                env=dict(os.environ, AGENT_FAKE_RAM="10",
                                         AGENT_FAKE_CPU="10"),
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        time.sleep(1)
        self.assertTrue(alive(self.proc.pid),
                        "relief killed a monitor whose lock owner is still alive")
        self.assertNotIn("no live main manager", result.stdout)


class TestOverCapNamesRelief(ScriptCase):
    script = "agent-start.sh"

    def test_over_cap_line_tells_the_agent_to_run_relief(self):
        out = self.assertOk(self.repo.run("agent-start.sh",
                                          env={"AGENT_FAKE_RAM": "90",
                                               "AGENT_FAKE_CPU": "10"}))
        self.assertIn("agent-resources.sh relief", out)


if __name__ == "__main__":
    unittest.main()
