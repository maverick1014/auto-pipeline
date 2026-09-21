"""Failing tests for agent-monitor.sh (rule S1). Written by the task manager, before any code.

CONTRACT the worker must implement in agent-monitor.sh (repo root, executable):

    ./agent-monitor.sh start    start the background loop
    ./agent-monitor.sh stop     stop it
    ./agent-monitor.sh status   pid and the time of the last sweep
    ./agent-monitor.sh once     one sweep, then print the file
    ./agent-monitor.sh -h       usage, exit 0
    anything else               usage, exit 2

One sweep reads every line of agent_worktree.txt (main repo) and writes
agent_monitor.txt (main repo), one line per worktree line, in file order:

    <path> | <module> | pane <state> | commit <n>m ago | output <n>m ago | OK or STALL | <time>

  pane <state>   from `orca worktree ps --json`: the first agent's state, or
                 "none" when the worktree is missing from the JSON or has no agent
  commit <n>m    whole minutes since the newest commit in that path,
                 or "commit none" when the path is not a git repo
  output <n>m    whole minutes since lastOutputAt for that worktree in the JSON,
                 or "output none" when the worktree is missing from the JSON
  <time>         "%Y-%m-%d %H:%M"

Three signals. A signal is fresh when:
    pane    state is "working"
    commit  age is under stall_min minutes
    output  age is under stall_min minutes
All three quiet -> STALL. Any one fresh -> OK.
"none" always counts as quiet.

stall_min and monitor_interval_min come from agent.conf (default 10 and 5).

The file is written atomically: a temp file next to it, then mv. A reader never
sees a half-written file, and no temp file is left behind.

`start` writes the loop's pid to <shared git dir>/agent_monitor.pid and sweeps
every monitor_interval_min minutes. A pid file whose process is gone counts as
not running.
"""

import os
import re
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase

LINE_RE = re.compile(
    r"^(?P<path>[^|]+) \| (?P<module>[^|]+) \| pane (?P<pane>\S+) \| "
    r"commit (?P<commit>\d+m ago|none) \| output (?P<output>\d+m ago|none) \| "
    r"(?P<verdict>OK|STALL) \| \d{4}-\d\d-\d\d \d\d:\d\d$"
)


class MonitorCase(ScriptCase):
    script = "agent-monitor.sh"

    def monitor(self, *args, **kwargs):
        return self.repo.run("agent-monitor.sh", *args, **kwargs)

    def sweep(self, **kwargs):
        self.assertOk(self.monitor("once", **kwargs))
        text = self.repo.read("agent_monitor.txt")
        self.assertIsNotNone(text, "agent_monitor.txt was not written")
        return [l for l in text.splitlines() if l.strip()]

    def parsed(self, **kwargs):
        rows = []
        for line in self.sweep(**kwargs):
            match = LINE_RE.match(line)
            self.assertIsNotNone(match, "bad line shape: %r" % line)
            rows.append(match.groupdict())
        return rows

    def one_worktree(self, module="alpha", commit_min_ago=0, panes=None,
                     output_min=0, status="working", in_json=True):
        path = self.repo.make_worktree(module, commit_min_ago=commit_min_ago)
        self.repo.set_worktree_lines([(path, module, status)])
        if in_json:
            self.repo.set_panes([{"path": path, "agents": panes or [],
                                  "output_min": output_min}])
        else:
            self.repo.set_panes([])
        return path


class TestSweepFile(MonitorCase):
    def test_one_line_per_worktree_line(self):
        paths = [self.repo.make_worktree("m%d" % i) for i in range(3)]
        self.repo.set_worktree_lines([(p, "m%d" % i, "working")
                                      for i, p in enumerate(paths)])
        self.repo.set_panes([{"path": p, "agents": ["working"]} for p in paths])
        rows = self.parsed()
        self.assertEqual([r["path"] for r in rows], paths)

    def test_line_shape(self):
        path = self.one_worktree(panes=["working"])
        rows = self.parsed()
        self.assertEqual(rows[0]["path"], path)
        self.assertEqual(rows[0]["module"], "alpha")
        self.assertEqual(rows[0]["pane"], "working")

    def test_module_comes_from_the_worktree_file(self):
        self.one_worktree(module="pospro", panes=["working"])
        self.assertEqual(self.parsed()[0]["module"], "pospro")

    def test_file_lives_in_the_main_repo(self):
        self.one_worktree(panes=["working"])
        self.sweep()
        self.assertTrue(os.path.exists(self.repo.path("agent_monitor.txt")))

    def test_empty_worktree_file_writes_an_empty_monitor_file(self):
        out = self.assertOk(self.monitor("once"))
        self.assertIn("(no live worktrees)", out)
        self.assertEqual(self.repo.read("agent_monitor.txt").strip(), "")

    def test_once_prints_what_it_wrote(self):
        self.one_worktree(panes=["working"])
        out = self.assertOk(self.monitor("once"))
        for line in self.repo.read("agent_monitor.txt").splitlines():
            self.assertIn(line, out)

    def test_a_sweep_replaces_the_old_file(self):
        with open(self.repo.path("agent_monitor.txt"), "w") as fh:
            fh.write("stale line from before\n")
        self.one_worktree(panes=["working"])
        text = self.repo.read("agent_monitor.txt")
        self.sweep()
        text = self.repo.read("agent_monitor.txt")
        self.assertNotIn("stale line from before", text)


class TestSignals(MonitorCase):
    def test_pane_state_comes_from_the_json(self):
        for state in ("working", "done", "permission"):
            with self.subTest(state=state):
                self.one_worktree(module="s" + state, panes=[state])
                self.assertEqual(self.parsed()[0]["pane"], state)

    def test_pane_none_when_the_worktree_is_not_in_the_json(self):
        self.one_worktree(in_json=False)
        self.assertEqual(self.parsed()[0]["pane"], "none")

    def test_pane_none_when_the_worktree_has_no_agent(self):
        self.one_worktree(panes=[])
        self.assertEqual(self.parsed()[0]["pane"], "none")

    def test_commit_age_in_whole_minutes(self):
        self.one_worktree(commit_min_ago=25, panes=["working"])
        self.assertEqual(self.parsed()[0]["commit"], "25m ago")

    def test_fresh_commit_reads_zero_minutes(self):
        self.one_worktree(commit_min_ago=0, panes=["working"])
        self.assertEqual(self.parsed()[0]["commit"], "0m ago")

    def test_commit_none_when_the_path_is_not_a_git_repo(self):
        path = self.repo.make_worktree("plain", as_repo=False)
        self.repo.set_worktree_lines([(path, "plain", "working")])
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        self.assertEqual(self.parsed()[0]["commit"], "none")

    def test_output_age_in_whole_minutes(self):
        self.one_worktree(panes=["working"], output_min=17)
        self.assertEqual(self.parsed()[0]["output"], "17m ago")

    def test_output_none_when_the_worktree_is_not_in_the_json(self):
        self.one_worktree(in_json=False)
        self.assertEqual(self.parsed()[0]["output"], "none")


class TestVerdict(MonitorCase):
    def test_stall_when_all_three_are_quiet(self):
        self.repo.set_conf("stall_min", "10")
        self.one_worktree(commit_min_ago=30, panes=[], output_min=30,
                          in_json=True)
        self.assertEqual(self.parsed()[0]["verdict"], "STALL")

    def test_ok_when_the_pane_is_working(self):
        self.repo.set_conf("stall_min", "10")
        self.one_worktree(commit_min_ago=30, panes=["working"], output_min=30)
        self.assertEqual(self.parsed()[0]["verdict"], "OK")

    def test_ok_when_the_commit_is_fresh(self):
        self.repo.set_conf("stall_min", "10")
        self.one_worktree(commit_min_ago=0, panes=["done"], output_min=30)
        self.assertEqual(self.parsed()[0]["verdict"], "OK")

    def test_ok_when_the_output_is_fresh(self):
        self.repo.set_conf("stall_min", "10")
        self.one_worktree(commit_min_ago=30, panes=["done"], output_min=0)
        self.assertEqual(self.parsed()[0]["verdict"], "OK")

    def test_a_waiting_pane_is_not_fresh(self):
        self.repo.set_conf("stall_min", "10")
        self.one_worktree(commit_min_ago=30, panes=["permission"], output_min=30)
        self.assertEqual(self.parsed()[0]["verdict"], "STALL")

    def test_stall_min_comes_from_agent_conf(self):
        self.repo.set_conf("stall_min", "60")
        self.one_worktree(commit_min_ago=30, panes=[], output_min=30)
        self.assertEqual(self.parsed()[0]["verdict"], "OK")
        self.repo.set_conf("stall_min", "10")
        self.assertEqual(self.parsed()[0]["verdict"], "STALL")

    def test_the_boundary_minute_is_a_stall(self):
        self.repo.set_conf("stall_min", "10")
        self.one_worktree(commit_min_ago=10, panes=[], output_min=10)
        self.assertEqual(self.parsed()[0]["verdict"], "STALL")

    def test_one_minute_under_the_bound_is_ok(self):
        self.repo.set_conf("stall_min", "10")
        self.one_worktree(commit_min_ago=9, panes=[], output_min=9)
        self.assertEqual(self.parsed()[0]["verdict"], "OK")

    def test_default_stall_min_is_ten(self):
        path = self.repo.make_worktree("nodefault", commit_min_ago=30)
        self.repo.set_worktree_lines([(path, "nodefault", "working")])
        self.repo.set_panes([{"path": path, "agents": [], "output_min": 30}])
        conf = self.repo.path("agent.conf")
        text = "".join(l for l in open(conf)
                       if not l.startswith("stall_min="))
        open(conf, "w").write(text)
        self.assertEqual(self.parsed()[0]["verdict"], "STALL")


class TestAtomicWrite(MonitorCase):
    def test_no_temp_file_is_left_behind(self):
        self.one_worktree(panes=["working"])
        self.sweep()
        left = [n for n in os.listdir(self.repo.dir)
                if n.startswith("agent_monitor.txt") and n != "agent_monitor.txt"]
        self.assertEqual(left, [])

    def test_the_file_is_replaced_not_truncated(self):
        """tmp + mv gives the target a new inode. Writing in place does not."""
        self.one_worktree(panes=["working"])
        self.sweep()
        first = os.stat(self.repo.path("agent_monitor.txt")).st_ino
        self.sweep()
        second = os.stat(self.repo.path("agent_monitor.txt")).st_ino
        self.assertNotEqual(first, second,
                            "agent_monitor.txt was written in place, not moved")

    def test_a_reader_never_sees_a_half_written_file(self):
        old = "OLD | old | pane none | commit none | output none | OK | 2026-01-01 00:00\n"
        with open(self.repo.path("agent_monitor.txt"), "w") as fh:
            fh.write(old)
        self.one_worktree(panes=["working"])
        proc = self.repo.popen("agent-monitor.sh", "once",
                               env={"ORCA_STUB_SLEEP": "2"})
        seen = set()
        deadline = time.time() + 8
        while proc.poll() is None and time.time() < deadline:
            try:
                with open(self.repo.path("agent_monitor.txt")) as fh:
                    seen.add(fh.read())
            except OSError:
                pass
            time.sleep(0.05)
        proc.wait(timeout=10)
        new = self.repo.read("agent_monitor.txt")
        seen.add(new)
        self.assertNotIn("", seen, "the file was empty at some point")
        for text in seen:
            self.assertIn(text, (old, new),
                          "a reader saw a file that is neither old nor new:\n%r" % text)


class TestLifecycle(MonitorCase):
    def pid_file(self):
        return self.repo.path(".git", "agent_monitor.pid")

    def test_status_before_start(self):
        out = self.assertOk(self.monitor("status"))
        self.assertIn("monitor: not running", out)

    def test_start_writes_a_pid_file_in_the_shared_git_dir(self):
        out = self.assertOk(self.monitor("start"))
        self.assertRegex(out, r"monitor: started \(pid \d+\)")
        self.assertTrue(os.path.exists(self.pid_file()))
        pid = int(open(self.pid_file()).read().split()[0])
        os.kill(pid, 0)

    def test_start_twice_says_already_running(self):
        self.assertOk(self.monitor("start"))
        out = self.assertOk(self.monitor("start"))
        self.assertRegex(out, r"monitor: already running \(pid \d+\)")

    def test_status_after_start_shows_the_pid_and_the_last_sweep(self):
        self.one_worktree(panes=["working"])
        self.assertOk(self.monitor("start"))
        deadline = time.time() + 10
        while not os.path.exists(self.repo.path("agent_monitor.txt")) \
                and time.time() < deadline:
            time.sleep(0.1)
        out = self.assertOk(self.monitor("status"))
        self.assertRegex(out, r"monitor: running \(pid \d+\)")
        self.assertRegex(out, r"last sweep: \d{4}-\d\d-\d\d \d\d:\d\d")

    def test_start_sweeps_straight_away(self):
        self.one_worktree(panes=["working"])
        self.assertOk(self.monitor("start"))
        deadline = time.time() + 10
        while not os.path.exists(self.repo.path("agent_monitor.txt")) \
                and time.time() < deadline:
            time.sleep(0.1)
        self.assertTrue(os.path.exists(self.repo.path("agent_monitor.txt")))

    def test_stop_kills_the_loop(self):
        self.assertOk(self.monitor("start"))
        pid = int(open(self.pid_file()).read().split()[0])
        out = self.assertOk(self.monitor("stop"))
        self.assertIn("monitor: stopped", out)
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.1)
        else:
            self.fail("pid %d is still alive after stop" % pid)
        self.assertFalse(os.path.exists(self.pid_file()))

    def test_stop_when_not_running_says_so(self):
        out = self.assertOk(self.monitor("stop"))
        self.assertIn("monitor: not running", out)

    def test_a_dead_pid_file_counts_as_not_running(self):
        os.makedirs(self.repo.path(".git"), exist_ok=True)
        with open(self.pid_file(), "w") as fh:
            fh.write("999999\n")
        out = self.assertOk(self.monitor("status"))
        self.assertIn("monitor: not running", out)
        out = self.assertOk(self.monitor("start"))
        self.assertRegex(out, r"monitor: started \(pid \d+\)")

    def test_start_says_the_interval(self):
        self.repo.set_conf("monitor_interval_min", "7")
        out = self.assertOk(self.monitor("start"))
        self.assertIn("7 minutes", out)


class TestUsage(MonitorCase):
    def test_help_exits_zero(self):
        result = self.monitor("-h")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agent-monitor.sh", result.stdout)

    def test_no_argument_exits_two(self):
        self.assertEqual(self.monitor().returncode, 2)

    def test_unknown_argument_exits_two(self):
        self.assertEqual(self.monitor("wat").returncode, 2)

    def test_runs_from_any_directory(self):
        self.one_worktree(panes=["working"])
        out = self.assertOk(self.repo.run("agent-monitor.sh", "once",
                                          cwd=self.repo.bin))
        self.assertIn("pane working", out)


if __name__ == "__main__":
    unittest.main()
