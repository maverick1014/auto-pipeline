"""Failing tests first for report-to-main-pc2 (owner 2026-11-25: "all of the tracker update should report to main repo ...
because main repo is the brain"). Module: bin/agent_watch.py (agent-watch.sh --all). Features:

A. The newest (last in the file) of {STAGE <name>: line, HEARTBEAT <name>: step <n> of 7, work <m>m, <text> line,
   STEP <n> <word>: line} in the task's agent_state.txt decides the stage the watch carries into the main repo's todo
   line (todo stage). Step 0..7 = brief register mock tests workers verify push report. The heartbeat's
   "<m>m <text>" goes to the todo line too (todo beat: field " | beat <m>m <text>"), and the board shows it after the bar.
   A local task and a task on another machine are read the same way; the other machine's command stays one call
   per sweep, under 500 chars.
B. No STALL while the pane status line counts shells or monitors ("1 shell, 1 monitor"), or the newest state line says a
   run "started" and watch_quiet_min (agent.conf, default 15) has not passed since the file last changed. A real idle
   prompt (nothing running, no new line) still stalls.
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from watchhelp import ENV, AllCase, idle, moving  # noqa: E402

STEP_NAMES = ["brief", "register", "mock", "tests", "workers", "verify", "push", "report"]
HB = "HEARTBEAT alpha: step 5 of 7, work 160m, full suite running | 2026-11-25 12:00"
HHMM = r"\d\d:\d\d"


class CarryCase(AllCase):
    def setUp(self):
        super().setUp()

    def carry(self, env=None, lines=(), on_read=None, name="alpha"):
        self.todo(name)
        t = self.task(name, env=env, frames=moving())
        self.append_state(name, *lines)
        self.on_task_read(name, on_read or {2: "ACK %s: still here" % name})
        return t, self.text(self.run_all(max_sweeps="4"))


class TestHeartbeatBeat(CarryCase):
    def test_work_minutes_and_text_are_carried(self):
        for env in (None, ENV):
            with self.subTest(env=env):
                self.setUp()
                self.carry(env, [HB])
                self.assertIn(" | beat 160m full suite running", self.todo_line("alpha"))

    def test_a_newer_heartbeat_replaces_the_beat_in_place(self):
        self.carry(None, [HB], on_read={2: "HEARTBEAT alpha: step 5 of 7, work 175m, suite done | 2026-11-25 12:15"})
        line = self.todo_line("alpha")
        self.assertEqual(line.count(" | beat "), 1, line)
        self.assertIn(" | beat 175m suite done", line)

    def test_the_board_shows_the_beat_after_the_bar(self):
        self.carry(None, [HB])
        board = self.repo.run("agent-file.sh", "board")
        self.assertIn("160m full suite running", board.stdout, board.stdout + board.stderr)

    def test_the_remote_command_is_one_call_per_sweep_under_500(self):
        t, _ = self.carry(ENV, [HB])
        sends = [c for c in self.terminal_calls("send") if self.opt(c, "--terminal") == t["shell"]]
        self.assertTrue(sends)
        for call in sends:
            self.assertLess(len(self.opt(call, "--text") or ""), 500, call)
        reads = [c for c in self.terminal_calls("read")
                 if self.opt(c, "--terminal") == t["shell"] and "--cursor" in c]
        self.assertLessEqual(len(reads), len(sends) * 20)
        tm_reads = [c for c in self.terminal_calls("read") if self.opt(c, "--terminal") == t["pane"]]
        self.assertLessEqual(len(sends), len(tm_reads))

    def test_the_remote_command_fits_paths_of_80_110_and_140_chars(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        import agent_watch
        for n in (80, 110, 140):
            with self.subTest(path=n):
                path = ("/home/maverick/orca/workspaces/" + "x" * 200)[:n - len("/agent_state.txt")]
                cmd = agent_watch.remote_command(path)
                self.assertEqual(len(path + "/agent_state.txt"), n)
                self.assertLess(len(cmd), agent_watch.REMOTE_CMD_MAX)
                print("path %d: command %d chars, headroom %d" % (n, len(cmd), agent_watch.REMOTE_CMD_MAX - 1 - len(cmd)))

    def test_a_long_path_is_watched_remotely(self):
        self.todo("alpha")
        t = self.task("alpha", env=ENV, sub="a" * 60)
        self.assertGreaterEqual(len(t["path"]), 80)
        self.append_state("alpha", HB)
        text = self.text(self.run_all(max_sweeps="3"))
        self.assertTrue(self.status()["tasks"]["alpha"]["watched"], text)
        self.assertIn(" | stage verify since ", self.todo_line("alpha"))


if __name__ == "__main__":
    unittest.main()
