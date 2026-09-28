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

Every kill path ends the loop's children too. The real loop is
`trap ... TERM; while true; do sleep N & wait $!; ...; done`: a TERM to the
loop pid alone leaves its `sleep 300` running for minutes. So:
  - the test-monitor pass kills the loop and its children
  - the no-live-lock pass: a repo with its own bin/agent-monitor.sh gets
    `agent-monitor.sh stop` first (an old copy may not stop the sleep, or
    its pid file may be gone), then the loop, if still alive, and its
    children are killed; a repo without the script: loop and children killed
  - the folder-gone pass already does this (3d3b0ee)

AGENT_RELIEF_ONLY_UNDER=<folder>: relief stops only processes whose command
line or working folder lies under that folder. Unset -> everything, as
before. Every test here sets it to its own temp tree, so a test run never
stops another session's monitors or another test run's loops.

The human table's WHAT/SUGGEST (relief_what_suggest "<comm>" "<args>" ->
"WHAT|SUGGEST"): Orca itself (the app and its helpers, anything under
Orca.app/) is "Orca|human decides". A process that only has "orca" in a
path (node vite in ~/orca/workspaces/...) is not Orca.

Fake loops are started with stdin/stdout/stderr on /dev/null and in their
own process group; cleanup kills the whole group. A fake loop that inherits
the test's stdout keeps a piped run ('... | tail') open until its sleep ends.
"""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase, ROOT, children_of

REAL_SCRIPT = os.path.join(ROOT, "bin", "agent-resources.sh")

# The shape of the real monitor loop (agent-monitor.sh do_start): a TERM trap
# and a background sleep. Killing only this pid leaves the sleep behind.
LOOP = """#!/usr/bin/env bash
case "${1:-}" in stop) exit 0;; esac
trap 'exit 0' TERM
while true; do
  sleep 300 &
  wait $!
done
"""

# The older fakes: one foreground sleep.
SLEEPER = "#!/usr/bin/env bash\nsleep 300\n"


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


def write_exe(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(body)
    os.chmod(path, 0o755)
    return path


def spawn(case, script, cwd=None):
    """Start `bash <script> start` the leak-free way and clean it up after.

    /dev/null for all three streams: a loop, or its sleep, that holds the
    test's stdout keeps a piped run open. Own process group: cleanup kills
    the loop and every child with one killpg, even after relief killed only
    part of it.
    """
    proc = subprocess.Popen(["bash", script, "start"], cwd=cwd,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            start_new_session=True)

    def reap():
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    case.addCleanup(reap)
    case.assertTrue(wait_until(lambda: alive(proc.pid)),
                    "fake monitor never started")
    return proc


def refuse_unscoped_relief(script):
    """relief is real: without the scope it stops every test loop and every
    lock-less monitor on the machine, other sessions' too. A script that
    does not know the scope yet is never run by a test."""
    with open(script) as fh:
        if "AGENT_RELIEF_ONLY_UNDER" not in fh.read():
            raise AssertionError(
                "%s does not know AGENT_RELIEF_ONLY_UNDER yet; not running "
                "the real relief machine-wide" % script)


def relief(scope):
    refuse_unscoped_relief(REAL_SCRIPT)
    return subprocess.run([REAL_SCRIPT, "relief"],
                          env=dict(os.environ, AGENT_FAKE_RAM="10",
                                   AGENT_FAKE_CPU="10",
                                   AGENT_RELIEF_ONLY_UNDER=scope),
                          stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=60)


def git_repo(path):
    os.makedirs(path)
    subprocess.run(["git", "init", "-q", path], check=True,
                   capture_output=True)
    for key, value in (("user.email", "t@t.t"), ("user.name", "t")):
        subprocess.run(["git", "-C", path, "config", key, value], check=True,
                       capture_output=True)
    with open(os.path.join(path, "seed.txt"), "w") as fh:
        fh.write("x\n")
    subprocess.run(["git", "-C", path, "add", "-A"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", path, "commit", "-q", "-m", "seed"],
                   check=True, capture_output=True)
    return path


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
        refuse_unscoped_relief(self.repo.script_path("agent-resources.sh"))
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
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="relief_test_"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def test_relief_kills_a_fake_test_monitor_loop(self):
        fake_monitor = write_exe(os.path.join(
            self.base, "auto_pipeline_t3st", "plugin", "bin",
            "agent-monitor.sh"), SLEEPER)
        self.proc = spawn(self, fake_monitor)

        result = relief(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("stopped 1 test monitors", result.stdout)
        # poll(), not os.kill: a killed child is a zombie (still answers
        # os.kill(pid, 0)) until this process reaps it with wait()/poll().
        self.assertTrue(wait_until(lambda: self.proc.poll() is not None),
                        "fake test monitor is still alive after relief")


class TestReliefLeavesALiveMainManagerAlone(unittest.TestCase):
    """A monitor whose repo's agent_main.lock names a live pid must survive."""

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="relief_repo_"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.repo_root = git_repo(os.path.join(self.base, "somerepo"))

        # a live main-manager lock: first field is our own (live) pid
        with open(os.path.join(self.repo_root, ".git", "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-09-24 00:00\n" % os.getpid())

        self.fake_monitor = write_exe(
            os.path.join(self.repo_root, "bin", "agent-monitor.sh"), SLEEPER)
        self.proc = spawn(self, self.fake_monitor, cwd=self.repo_root)

    def test_relief_does_not_kill_a_monitor_with_a_live_lock_owner(self):
        result = relief(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        time.sleep(1)
        self.assertTrue(alive(self.proc.pid),
                        "relief killed a monitor whose lock owner is still alive")
        self.assertNotIn("no live main manager", result.stdout)


class TestReliefStopsMonitorWhoseFolderIsGone(unittest.TestCase):
    """A monitor loop whose cwd folder was deleted (a removed E2E temp repo,
    a deleted scratchpad clone) can never be stopped with
    "agent-monitor.sh stop" -- that folder no longer exists to cd into.
    relief must kill the loop (and any child it left running) instead of
    skipping it forever.
    """

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="relief_gone_"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.repo_root = os.path.join(self.base, "somerepo")
        fake_monitor = write_exe(
            os.path.join(self.repo_root, "agent-monitor.sh"), SLEEPER)
        self.proc = spawn(self, fake_monitor, cwd=self.repo_root)
        # let bash actually get past forking its "sleep" child before we
        # pull the folder out from under it: cwd-dependent work (job
        # control, PATH lookup) mid-fork can otherwise kill bash itself,
        # which would test the wrong thing (bash dying on its own instead
        # of relief stopping a genuinely still-running orphan).
        time.sleep(1)

        # delete the folder out from under the running process
        shutil.rmtree(self.repo_root, ignore_errors=True)

    def test_relief_stops_a_monitor_whose_folder_is_gone(self):
        result = relief(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("folder gone", result.stdout)
        self.assertTrue(wait_until(lambda: self.proc.poll() is not None),
                        "monitor whose folder is gone is still alive after relief")


class ReliefLoopCase(unittest.TestCase):
    """One temp tree per test; loops shaped like the real one (LOOP)."""

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="relief_kids_"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def loop_with_child(self, script, cwd=None):
        """Start a LOOP-shaped fake; return (proc, its sleep child's pid)."""
        proc = spawn(self, script, cwd=cwd)
        self.assertTrue(wait_until(lambda: children_of(proc.pid)),
                        "the fake loop never started its sleep")
        return proc, children_of(proc.pid)[0]

    def assertAllGone(self, proc, child):
        self.assertTrue(wait_until(lambda: proc.poll() is not None),
                        "the loop is still alive after relief")
        self.assertTrue(wait_until(lambda: not alive(child)),
                        "the loop's sleep (pid %d) is still alive after "
                        "relief" % child)


class TestReliefStopsTheLoopsChildren(ReliefLoopCase):
    def test_the_test_monitor_pass_kills_the_sleep_too(self):
        script = write_exe(os.path.join(
            self.base, "auto_pipeline_k1ds", "plugin", "bin",
            "agent-monitor.sh"), LOOP)
        proc, child = self.loop_with_child(script)
        result = relief(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("stopped 1 test monitors", result.stdout)
        self.assertAllGone(proc, child)

    def test_no_lock_and_no_script_kills_the_sleep_too(self):
        repo = git_repo(os.path.join(self.base, "nolock"))
        script = write_exe(os.path.join(repo, "agent-monitor.sh"), LOOP)
        proc, child = self.loop_with_child(script, cwd=repo)
        result = relief(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no live main manager", result.stdout)
        self.assertAllGone(proc, child)

    def test_no_lock_and_a_stop_that_stops_nothing_still_ends_both(self):
        # the repo's own bin/agent-monitor.sh answers `stop` without
        # stopping anything: an old copy, or its pid file is gone
        repo = git_repo(os.path.join(self.base, "oldcopy"))
        script = write_exe(os.path.join(repo, "bin", "agent-monitor.sh"),
                           LOOP)
        proc, child = self.loop_with_child(script, cwd=repo)
        result = relief(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no live main manager", result.stdout)
        self.assertAllGone(proc, child)

    def test_a_dead_lock_owner_counts_as_no_lock(self):
        repo = git_repo(os.path.join(self.base, "deadlock"))
        gone = subprocess.Popen(["true"])
        gone.wait()
        with open(os.path.join(repo, ".git", "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-09-28 00:00\n" % gone.pid)
        script = write_exe(os.path.join(repo, "agent-monitor.sh"), LOOP)
        proc, child = self.loop_with_child(script, cwd=repo)
        result = relief(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertAllGone(proc, child)


class TestReliefStaysInsideItsScope(ReliefLoopCase):
    """AGENT_RELIEF_ONLY_UNDER: nothing outside that folder is stopped."""

    def setUp(self):
        super(TestReliefStaysInsideItsScope, self).setUp()
        self.elsewhere = os.path.realpath(
            tempfile.mkdtemp(prefix="relief_elsewhere_"))
        self.addCleanup(shutil.rmtree, self.elsewhere, ignore_errors=True)

    def test_a_test_monitor_outside_the_scope_lives(self):
        script = write_exe(os.path.join(
            self.base, "auto_pipeline_0ut", "plugin", "bin",
            "agent-monitor.sh"), LOOP)
        proc, child = self.loop_with_child(script)
        result = relief(self.elsewhere)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("stopped 0 test monitors", result.stdout)
        time.sleep(1)
        self.assertIsNone(proc.poll(), "relief stopped a loop outside its scope")
        self.assertTrue(alive(child))

    def test_a_no_lock_monitor_outside_the_scope_lives(self):
        repo = git_repo(os.path.join(self.base, "nolock"))
        script = write_exe(os.path.join(repo, "agent-monitor.sh"), LOOP)
        proc, child = self.loop_with_child(script, cwd=repo)
        result = relief(self.elsewhere)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("nolock", result.stdout)
        time.sleep(1)
        self.assertIsNone(proc.poll(), "relief stopped a loop outside its scope")
        self.assertTrue(alive(child))

    def test_a_folder_that_only_starts_with_the_scope_name_is_outside(self):
        # "under" is a path boundary, not a substring: scope_a does not
        # hold scope_abc
        scope = os.path.join(self.base, "scope_a")
        os.makedirs(scope)
        script = write_exe(os.path.join(
            self.base, "scope_abc", "auto_pipeline_pre", "plugin", "bin",
            "agent-monitor.sh"), LOOP)
        proc, child = self.loop_with_child(script)
        repo = git_repo(os.path.join(self.base, "scope_abc", "nolock"))
        orphan, orphan_child = self.loop_with_child(
            write_exe(os.path.join(repo, "agent-monitor.sh"), LOOP), cwd=repo)
        result = relief(scope)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("stopped 0 test monitors", result.stdout)
        self.assertNotIn("nolock", result.stdout)
        time.sleep(1)
        for p, kid in ((proc, child), (orphan, orphan_child)):
            self.assertIsNone(p.poll(), "relief stopped a loop outside its scope")
            self.assertTrue(alive(kid))

    def test_a_scope_holding_it_still_stops_it(self):
        script = write_exe(os.path.join(
            self.base, "auto_pipeline_1n", "plugin", "bin",
            "agent-monitor.sh"), LOOP)
        proc, child = self.loop_with_child(script)
        result = relief(self.base)
        self.assertIn("stopped 1 test monitors", result.stdout)
        self.assertAllGone(proc, child)


class TestReliefWhatSuggest(ScriptCase):
    """relief_what_suggest "<comm>" "<args>" -> "WHAT|SUGGEST"."""

    script = "agent-resources.sh"

    ORCA_APP = "/Applications/Orca.app/Contents/MacOS/Orca"
    ORCA_HELPER = ("/Applications/Orca.app/Contents/Frameworks/"
                   "Orca Helper (Renderer).app/Contents/MacOS/"
                   "Orca Helper (Renderer)")

    def what(self, comm, args):
        self.repo.write_bin_script(
            "what.sh",
            "#!/usr/bin/env bash\n"
            "cd \"$(dirname \"$0\")\"\n"
            ". ./agent-resources.sh\n"
            "pid_for_what=$$\n"
            "relief_what_suggest \"$1\" \"$2\"\n")
        return self.assertOk(self.repo.run("what.sh", comm, args)).strip()

    def test_the_orca_app_is_for_the_human(self):
        self.assertEqual(self.what(self.ORCA_APP, self.ORCA_APP),
                         "Orca|human decides")

    def test_an_orca_helper_is_for_the_human(self):
        self.assertEqual(self.what(self.ORCA_HELPER,
                                   self.ORCA_HELPER + " --type=renderer"),
                         "Orca|human decides")

    def test_orca_never_says_close_from_orca(self):
        for comm in (self.ORCA_APP, self.ORCA_HELPER):
            with self.subTest(comm=comm):
                self.assertNotIn("close from Orca if idle",
                                 self.what(comm, comm))

    def test_node_in_an_orca_workspace_is_node(self):
        args = "node /Users/me/orca/workspaces/app/node_modules/.bin/vite"
        self.assertEqual(self.what("node", args), "node vite|let it finish")

    def test_a_claude_session_is_unchanged(self):
        self.assertTrue(self.what("claude", "claude --effort xhigh")
                        .startswith("claude session "))

    def test_gradle_is_unchanged(self):
        self.assertEqual(self.what("java", "java ... GradleDaemon 8.7"),
                         "GradleDaemon|gradle --stop")


class TestOverCapNamesRelief(ScriptCase):
    script = "agent-start.sh"

    def test_over_cap_line_tells_the_agent_to_run_relief(self):
        out = self.assertOk(self.repo.run("agent-start.sh",
                                          env={"AGENT_FAKE_RAM": "90",
                                               "AGENT_FAKE_CPU": "10"}))
        self.assertIn("agent-resources.sh relief", out)


if __name__ == "__main__":
    unittest.main()
