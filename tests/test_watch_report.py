"""Failing tests first for report-to-main-pc2 (owner 2026-11-25: "all of the tracker update should report to main repo ...
because main repo is the brain"). Module: bin/agent_watch.py (agent-watch.sh --all). Features:

A. The newest (last in the file) of {STAGE <name>: line, HEARTBEAT <name>: step <n> of 7, work <m>m, <text> line,
   STEP <n> <word>: line} in the task's agent_state.txt decides the stage the watch carries into the main repo's todo
   line (todo stage). Step 0..7 = brief register mock tests workers verify push report. The heartbeat's
   "<m>m <text>" goes to the todo line too (todo beat: field " | beat <m>m <text>"), and the board shows it after the bar.
   A local task and a task on another machine are read the same way; the other machine's command stays one call
   per sweep, under 400 chars.
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


class TestNewestLineDecidesTheStage(CarryCase):
    def test_a_heartbeat_newer_than_the_last_stage_line_wins(self):
        for env in (None, ENV):
            with self.subTest(env=env):
                self.setUp()
                self.carry(env, ["STAGE alpha: tests | since 2026-11-25 09:00", HB])
                self.assertIn(" | stage verify since ", self.todo_line("alpha"))

    def test_an_older_heartbeat_does_not_win(self):
        for env in (None, ENV):
            with self.subTest(env=env):
                self.setUp()
                self.carry(env, [HB, "STAGE alpha: push | since 2026-11-25 12:05"])
                line = self.todo_line("alpha")
                self.assertIn(" | stage push since ", line)
                self.assertNotIn(" | beat ", line)

    def test_a_step_line_is_a_stage_too(self):
        self.carry(None, ["STAGE alpha: tests | since 2026-11-25 09:00", "STEP 6 push: pushed the branch"])
        self.assertIn(" | stage push since ", self.todo_line("alpha"))

    def test_step_numbers_map_to_the_stage_names(self):
        for n, name in enumerate(STEP_NAMES):
            with self.subTest(step=n):
                self.setUp()
                self.carry(None, ["HEARTBEAT alpha: step %d of 7, work 5m, x | 2026-11-25 12:00" % n])
                self.assertIn(" | stage %s since " % name, self.todo_line("alpha"))

    def test_another_tasks_heartbeat_is_not_carried(self):
        self.carry(None, ["HEARTBEAT beta: step 5 of 7, work 9m, x | 2026-11-25 12:00"])
        self.assertNotIn(" | stage ", self.todo_line("alpha"))

    def test_a_heartbeat_of_the_same_stage_keeps_the_workers_fraction(self):
        self.carry(None, ["STAGE alpha: workers 1/2 | since 2026-11-25 09:00",
                          "HEARTBEAT alpha: step 4 of 7, work 30m, workers run | 2026-11-25 09:30"])
        line = self.todo_line("alpha")
        self.assertIn(" | stage workers 1/2 since ", line)
        self.assertIn(" | beat 30m workers run", line)

    def test_the_printed_line_names_the_stage(self):
        _, text = self.carry(None, [HB])
        self.assertTrue([l for l in self.lines(text) if re.match(r"^%s stage alpha: verify$" % HHMM, l)], text)
        self.assertTrue([l for l in self.lines(text) if re.match(r"^%s beat alpha: 160m full suite running$" % HHMM, l)], text)


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

    def test_the_remote_command_is_one_call_per_sweep_under_400(self):
        t, _ = self.carry(ENV, [HB])
        sends = [c for c in self.terminal_calls("send") if self.opt(c, "--terminal") == t["shell"]]
        self.assertTrue(sends)
        for call in sends:
            self.assertLess(len(self.opt(call, "--text") or ""), 400, call)
        reads = [c for c in self.terminal_calls("read")
                 if self.opt(c, "--terminal") == t["shell"] and "--cursor" in c]
        self.assertLessEqual(len(reads), len(sends) * 20)
        tm_reads = [c for c in self.terminal_calls("read") if self.opt(c, "--terminal") == t["pane"]]
        self.assertLessEqual(len(sends), len(tm_reads))

    def test_the_remote_command_stays_short_for_a_long_path(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        import agent_watch
        path = "/home/maverick/projects/v4-plus/.claude/worktrees/" + "x" * 30
        self.assertLess(len(agent_watch.remote_command(path)), 400)


class TestRunningWorkIsNotAStall(AllCase):
    STALL = "WATCH STALL alpha: idle prompt"

    def test_idle_prompt_with_a_shell_and_a_monitor_count_is_not_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["  ⏵⏵ bypass permissions on · 1 shell, 1 monitor"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_idle_prompt_with_only_a_shell_count_is_not_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["  1 shell"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_idle_prompt_with_a_zero_count_is_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["  0 shells"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), self.STALL)

    def test_a_started_line_holds_the_stall(self):
        for env in (None, ENV):
            with self.subTest(env=env):
                self.setUp()
                self.task("alpha", env=env, frames=[idle(0)])
                self.append_state("alpha", "STEP 5 verify: full suite started on pc2, about 30m")
                self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_a_started_line_holds_only_for_watch_quiet_min(self):
        t = self.task("alpha", frames=[idle(0)])
        self.append_state("alpha", "STEP 5 verify: full suite started on pc2, about 30m")
        old = os.path.getmtime(t["state"]) - 3600
        os.utime(t["state"], (old, old))
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), self.STALL)

    def test_a_real_idle_prompt_still_stalls(self):
        for env in (None, ENV):
            with self.subTest(env=env):
                self.setUp()
                self.task("alpha", env=env, frames=[idle(0)])
                self.append_state("alpha", "STEP 5 verify: suite finished, 0 failures")
                self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), self.STALL)


class TestPrinciplesText(unittest.TestCase):
    def w15(self):
        with open(os.path.join(os.path.dirname(HERE), "PRINCIPLES.md")) as fh:
            text = fh.read()
        return text[text.index("W15. Watch"):text.index("W16.")].splitlines()

    def test_the_stage_from_the_newest_heartbeat_line(self):
        hits = [l for l in self.w15() if "HEARTBEAT step" in l and "STAGE line" in l and "main repo" in l]
        self.assertEqual(len(hits), 1, self.w15())
        self.assertLess(len(hits[0]), 200)

    def test_a_manager_waiting_for_its_own_run_is_not_a_stall(self):
        hits = [l for l in self.w15() if "not a stall" in l and "watch_quiet_min" in l and "started" in l]
        self.assertEqual(len(hits), 1, self.w15())
        self.assertLess(len(hits[0]), 200)


if __name__ == "__main__":
    unittest.main()
