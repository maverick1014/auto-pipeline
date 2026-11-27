"""board-fast-lane (requirements/board-fast-lane.md): the board shows a fast-lane task while its deputy works.
One test per example of the requirement; now = 2026-11-27 12:00."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_agent_guard as tg  # noqa: E402
import test_session_cleanup as ts  # noqa: E402

NOW = "2026-11-27 12:00"
DEPUTY = "auto-pipeline:fast-lane-deputy"
OPEN_LINE = "board-fast-lane | small | fix the board | est 40m | level 2 | opened 2026-11-27 11:30 | by main"


class TestFirstStage(tg.GuardCase):
    def setUp(self):
        super().setUp()
        self.make_main()

    def put(self, line=OPEN_LINE):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write(line + "\n")

    def todo_line(self):
        return self.repo.read("agent_todo.txt").splitlines()[0]

    def test_example_1_deputy_launch_writes_started_and_the_first_stage(self):
        self.put()
        self.assertAllowed(self.pre_agent("board-fast-lane Deputy", DEPUTY, now=NOW))
        line = self.todo_line()
        self.assertIn("| started %s" % NOW, line)
        self.assertIn("| stage brief since %s" % NOW, line)

    def test_example_1_a_line_with_a_stage_is_not_touched(self):
        line = OPEN_LINE + " | started 2026-11-27 11:40 | stage tests since 2026-11-27 11:50"
        self.put(line)
        self.assertAllowed(self.pre_agent("board-fast-lane Deputy", DEPUTY, now=NOW))
        self.assertEqual(self.todo_line(), line)

    def test_example_1_a_worker_launch_does_not_stage(self):
        self.put()
        self.assertAllowed(self.pre_agent("board-fast-lane Worker 1: x", "auto-pipeline:worker", now=NOW))
        self.assertEqual(self.todo_line(), OPEN_LINE)


class TestSendMessageIsALaunch(tg.GuardCase):
    def setUp(self):
        super().setUp()
        self.make_main()
        self.put_todo("board-fast-lane")

    def send(self, to, **kw):
        return self.hook({"hook_event_name": "PreToolUse", "tool_name": "SendMessage",
                          "tool_input": {"to": to, "message": "fix round"}, "tool_use_id": self.tid()},
                         now=NOW, **kw)

    def launch_and_stop(self):
        r = self.pre_agent("board-fast-lane Deputy", DEPUTY, now=NOW)
        self.post_agent(r.tid, "a1", desc="board-fast-lane Deputy", stype=DEPUTY, now=NOW)
        self.sub("SubagentStop", "a1", DEPUTY, now=NOW)
        self.assertEqual(self.launches(), [])

    def test_example_2_message_to_a_known_deputy_writes_a_record_stop_removes_it(self):
        self.launch_and_stop()
        self.assertAllowed(self.send("a1"))
        f = self.one_launch()
        self.assertEqual((f["kind"], f["task"], f["agent"], f["since"]), ("deputy", "board-fast-lane", "a1", NOW))
        self.assertTrue(self.status_of(self.rows(now=NOW), "board-fast-lane").endswith(" · 1 代理"))
        self.sub("SubagentStop", "a1", DEPUTY, now=NOW)
        self.assertEqual(self.launches(), [])

    def test_example_2_message_to_an_unknown_id_writes_nothing(self):
        self.launch_and_stop()
        self.assertAllowed(self.send("zz9"))
        self.assertEqual(self.launches(), [])

    def test_example_2_a_task_that_is_no_longer_open_writes_nothing(self):
        self.launch_and_stop()
        self.put_todo("other-task")
        self.assertAllowed(self.send("a1"))
        self.assertEqual(self.launches(), [])


class TestDeadHelperWithoutSession(ts.EndCase):
    def test_example_3_old_line_with_no_pid_and_no_session(self):
        old = "/x/wt | task manager, human-direct | task: (ask the human) | since 2026-11-26 09:00"
        fresh = "/y/wt | task manager, human-direct | task: (ask the human) | since 2026-11-27 11:00"
        live = ts.helper_line("/z/wt", "s1", pid=self.live_pid())
        self.set_lines([old, fresh, live])
        out = self.assertOk(self.end("--dead", env={"AGENT_FAKE_NOW": NOW}))
        self.assertEqual(self.lines(), [old, fresh, live])   # flagged, never removed
        self.assertIn("flag: human-direct line /x/wt: no pid, no session id, 27h old: close it with agent-file.sh worktree rm", out)


if __name__ == "__main__":
    unittest.main()
