"""Failing tests for check-blocks section 36 (owner order 2026-11-25, TELL 9bb87b13): the auto clear waits
until no human has typed a prompt in that pane for clear_quiet_min (default 30) minutes.
Written by the task manager before any code. Every transcript here is made up.

Run: python3 -m unittest tests.test_check_clear
"""

import datetime
import json
import os
import re
import sys
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from scripthelp import ScriptCase  # noqa: E402
import test_agent_owner_order as oo  # noqa: E402
import test_agent_autoclear as ac  # noqa: E402  (test-slim: was test_auto_clear)

NOW = ac.NOW                      # "2026-11-20 12:00", local = UTC here (TZ=UTC)
T0 = datetime.datetime(2026, 11, 20, 12, 0)


def ago(minutes):
    return T0 - datetime.timedelta(minutes=minutes)


def tell_pointer(dt):
    """A tell pointer typed into the pane by the main manager: signed, so agent-typed."""
    return oo.owner("[Fable 5.2 xhigh] TELL 1a2b3c4d: read the TELL 1a2b3c4d block at the end of agent_state.txt "
                    "and act on it", dt)


class Transcript:
    """<CLAUDE_CONFIG_DIR>/projects/<folder name of the repo>/<session>.jsonl"""

    def __init__(self, case, repo_dir):
        # the same config home the settings live in (scripthelp's default CLAUDE_CONFIG_DIR), so set_conf is read
        self.cfg = os.path.join(case.repo.base, "no-claude-config")
        self.dir = os.path.join(self.cfg, "projects", oo.folder_name(repo_dir))
        os.makedirs(self.dir, exist_ok=True)

    def write(self, lines, session="s1"):
        with open(os.path.join(self.dir, session + ".jsonl"), "w") as fh:
            fh.write("".join(json.dumps(l) + "\n" for l in lines))

    def append(self, line, session="s1"):
        with open(os.path.join(self.dir, session + ".jsonl"), "a") as fh:
            fh.write(json.dumps(line) + "\n")


# ====================================================================== C55 human-quiet


class TestHumanQuiet(ScriptCase):
    script = "agent-owner-order.sh"

    def setUp(self):
        super().setUp()
        self.t = Transcript(self, self.repo.dir)

    def quiet(self, minutes="30", session="s1"):
        return self.repo.run("agent-owner-order.sh", "human-quiet", "--session", session, "--minutes", minutes,
                             "--repo", self.repo.dir,
                             env={"CLAUDE_CONFIG_DIR": self.t.cfg, "TZ": "UTC", "AGENT_FAKE_NOW": NOW},
                             cwd=self.repo.dir)

    def test_a_human_10_minutes_ago(self):
        self.t.write([oo.owner("wait, one more thing about the board", ago(10))])
        r = self.quiet()
        self.assertEqual((r.returncode, r.stdout.strip()), (1, "typed 2026-11-20 11:50"), r.stderr)

    def test_40_minutes_ago_is_quiet(self):
        self.t.write([oo.owner("ok go", ago(40))])
        r = self.quiet()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "quiet"), r.stderr)

    def test_exactly_n_minutes_is_quiet(self):
        self.t.write([oo.owner("ok go", ago(30))])
        self.assertEqual(self.quiet().returncode, 0)

    def test_no_transcript_is_quiet(self):
        r = self.quiet()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "quiet"), r.stderr)

    def test_only_a_typed_human_prompt_counts(self):
        self.t.write([
            oo.owner("ok go", ago(40)),
            oo.notification("worker done", ago(9)),
            oo.peer("Worker B: PASS", ago(8)),
            tell_pointer(ago(7)),
            oo.owner(ac.SAVE, ago(6)),
            oo.owner("/clear", ago(5)),
            oo.owner("/goal " + ac.GOAL, ago(4)),
            oo.owner(ac.CONT, ago(4)),
            oo.meta("a hook said something", ago(3)),
            oo.tool_result("Ran 3 tests", ago(2)),
            oo.assistant("done", ago(1)),
        ])
        r = self.quiet()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "quiet"), r.stdout)

    def test_a_queued_prompt_is_a_human_too(self):
        self.t.write([oo.owner("and the board?", ago(2), source="queued")])
        self.assertEqual(self.quiet().returncode, 1)

    def test_zero_minutes_is_always_quiet(self):
        self.t.write([oo.owner("still here", ago(0))])
        self.assertEqual(self.quiet("0").returncode, 0)

    def test_another_session_does_not_count(self):
        self.t.write([oo.owner("I talk to the other pane", ago(1))], session="s2")
        self.assertEqual(self.quiet().returncode, 0)


# ====================================================================== C56 the waiter


class TestWaiterWaitsForTheHuman(ac.ClearCase):
    script = "agent-autoclear.sh"

    def setUp(self):
        super().setUp()
        self.repo.stub_tool("sleep", '#!/bin/bash\n[ "$1" = 30 ] && exec /bin/sleep 1\nexec /bin/sleep "$@"\n')
        self.t = Transcript(self, self.repo.dir)
        self.write_state(["ROLE: main manager", ""])

    def env(self):
        return {"AGENT_FAKE_NOW": NOW, "CLAUDE_CONFIG_DIR": self.t.cfg, "TZ": "UTC"}

    def waiting_line(self):
        return [l for l in self.state_lines() if l.startswith("AUTO CLEAR waiting: a human typed at ")]

    def start(self):
        proc = self.repo.popen("agent-autoclear.sh", ac.HANDLE, "s1", env=self.env())
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        return proc

    def test_a_human_10_minutes_ago_holds_it(self):
        self.t.write([oo.owner("let us talk about the flow", ago(10))])
        self.start()
        self.assertTrue(self.wait_for(lambda: self.waiting_line(), 15), self.state_lines())
        self.assertEqual(self.waiting_line(), [
            "AUTO CLEAR waiting: a human typed at 11:50; the clear waits for 30 quiet minutes | %s" % NOW])
        time.sleep(3)
        self.assertEqual(self.sends(), [], "nothing is typed while the human is talking")
        self.assertEqual(len(self.waiting_line()), 1, "one line per wait")

    def test_a_human_40_minutes_ago_clears_as_today(self):
        self.t.write([oo.owner("ok go", ago(40))])
        self.assertOk(self.waiter(env=self.env()))
        self.assertEqual(self.sends(), [ac.SAVE, "/clear", ac.CONT])

    def test_agents_and_notifications_do_not_hold_it(self):
        # a task manager nobody types into is cleared as today
        self.t.write([oo.notification("worker done", ago(3)), tell_pointer(ago(2)), oo.peer("PASS", ago(1))])
        self.assertOk(self.waiter(env=self.env()))
        self.assertEqual(self.sends(), [ac.SAVE, "/clear", ac.CONT])

    def test_zero_clears_without_waiting(self):
        self.repo.set_conf("clear_quiet_min", "0")
        self.t.write([oo.owner("still here", ago(1))])
        self.assertOk(self.waiter(env=self.env()))
        self.assertEqual(self.sends(), [ac.SAVE, "/clear", ac.CONT])

    def test_a_human_after_the_save_prompt_starts_it_again(self):
        self.t.write([oo.owner("ok go", ago(40))])
        human_now = json.dumps(oo.owner("no wait, I am not done", T0))
        marker = os.path.join(self.repo.base, "typed_once")
        self.stub_file("send_hook.sh",
                       '[ "$1" = %s ] && [ ! -f %s ] && { printf "%%s\\n" %s >> %s; touch %s; }\nexit 0\n'
                       % (json.dumps(ac.SAVE), marker, "'" + human_now + "'",
                          os.path.join(self.t.dir, "s1.jsonl"), marker))
        proc = self.start()
        self.assertTrue(self.wait_for(lambda: self.waiting_line(), 20), (self.sends(), self.state_lines()))
        self.assertEqual(self.sends(), [ac.SAVE], "no /clear while the human talks")
        # the talk ends: 40 minutes later the newest human prompt is old (the fake clock stands still)
        self.t.write([oo.owner("no wait, I am not done", ago(40))])
        self.assertTrue(self.wait_for(lambda: proc.poll() is not None, 30), self.sends())
        self.assertEqual(self.sends(), [ac.SAVE, ac.SAVE, "/clear", ac.CONT], "back to the save prompt first")
        self.assertEqual(self.state_lines()[-1], "AUTO CLEAR done | %s" % NOW)


# ====================================================================== C57 the LIMIT line


class TestLimitLine(ac.ClearCase):
    def setUp(self):
        super().setUp()
        self.stub_file("wait_sleep", "30")

    def test_the_line_names_the_wait(self):
        self.write_state(["ROLE: x", ""])
        self.assertOk(self.hook("compact"))
        out = self.assertOk(self.hook("compact"))
        self.assertIn(ac.LIMIT_PANE % 2, out.splitlines())

    def test_zero_keeps_the_old_line(self):
        self.repo.set_conf("clear_quiet_min", "0")
        self.write_state(["ROLE: x", ""])
        self.assertOk(self.hook("compact"))
        out = self.assertOk(self.hook("compact"))
        self.assertIn(ac.LIMIT_PANE_NO_WAIT % 2, out.splitlines())


# ====================================================================== C58 the rule


class TestRule(unittest.TestCase):
    def test_s8(self):
        with open(os.path.join(os.path.dirname(HERE), "PRINCIPLES.md")) as fh:
            text = fh.read()
        s8 = text[text.index("S8. "):text.index("S9. ")]
        for phrase in ("The auto clear fires only when no human has typed a prompt in that pane for the last N minutes",
                       '"Context: Auto clear after quiet (min)", default 30',
                       "Not a human prompt: a task notification, a tell pointer, a cross-session message, the watch "
                       "or the auto clear's own prompts",
                       "A task manager nobody types into is cleared as today"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, s8)


if __name__ == "__main__":
    unittest.main()
