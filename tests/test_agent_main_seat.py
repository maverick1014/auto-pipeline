"""Failing tests: one clear main manager per repo (city-roles R3, R4; owner 2026-09-30).

Bug (E3, v4-pospro): the old main manager got "close case", finished, and stayed alive holding
agent_main.lock. The owner opened a new session; agent-start.sh said "second"; it became
"v4-pospro Helper". The owner believed there was no main manager.

CONTRACT (bin/agent-roots.sh role_read, bin/agent-start.sh, bin/agent-close-case.sh,
skills/close-case/SKILL.md). "this session" = $CLAUDE_PID, else the first claude ancestor.

  Lock <git common dir>/agent_main.lock, one line written by agent-start.sh (role main, takeover,
  --take-over):  "<pid> <YYYY-MM-DD> <HH:MM> <sid> <terminal>"
      sid       the hook's stdin session_id, else $CLAUDE_CODE_SESSION_ID, else "-"
      terminal  $ORCA_TERMINAL_HANDLE, else "-"
  An old lock "<pid> <date> <time>" is still read; "since" stays "<date> <time>".

  R4 second session (a live main manager holds the lock, not this session): the ROLE line names it
      ROLE: task manager, human-direct (W10). Main manager already running: pid <pid>
      ("<repo> Manager", terminal <terminal>), since <date> <time>.
  (", terminal <terminal>" only when the lock has one, never "-"), and a line on how to take over,
  only when the human asks:  <plugin>/bin/agent-start.sh --take-over

  agent-start.sh --take-over   refused (exit 1, lock untouched) for a spawned agent (AGENT_ROLE).
      The lock is already this session's -> says so, exit 0, lock untouched. Except (city-rediscover,
      2026-10-01: an old lock "<pid> <date> <time>" hid a live main manager from the city, and
      "Nothing changed" left it so): when this session knows its sid and the lock has none or
      another one, or knows its terminal and the lock has none, the line is rewritten: same pid,
      same "<date> <time>", this session's sid, this session's terminal (else the lock's own, else
      "-"). It then says "Already the main manager (lock: pid <pid>). Lock line updated: ..." and
      never "Nothing changed". The holder never changes, the closed list is not touched.
      Else: the lock becomes this session's (line above); the old holder, when there was one,
      becomes "closed" (below); this session's own human-direct line in agent_worktree.txt goes;
      prints "ROLE: main manager" and the rename hint "/rename <repo> Manager". Exit 0.
  agent-start.sh --release     only the lock holder (exit 1 and the holder's pid otherwise,
      lock untouched). The lock goes, this session becomes "closed", prints "RELEASED". Exit 0.
      Run as the very last step of a whole-repo close case (skills/close-case/SKILL.md).

  closed session = a session released by --release or replaced by --take-over, while it does
  not hold the lock (a later --take-over by it makes it main again). role_read: role "closed".
      agent-start.sh (any source: startup, compact, clear, by hand) never writes the lock for it
      and never says "ROLE: main manager"; it says it is no longer the main manager.
      A new session in the repo is main again at once (no lock -> main), never "Helper".
      agent-close-case.sh (UserPromptSubmit), on its first prompt after that, any prompt: tells it
      once "no longer the main manager", who is main now (pid) when someone is, and
      --take-over only if the human asks, and that its name may still say Manager: ask the human
      once for /rename <repo> Helper (E2E 2026-09-30: the closed one still showed as "<repo> Manager"
      in the city). Every later prompt: nothing (the "close case" words
      keep their own text). Other sessions: nothing. This told-once mark is the only file the
      hook ever writes.

  BOUNCE 1 (main manager, laptop E2E): an agent running --take-over is denied by auto mode (right),
  and an agent's --release can be denied too. So both seat moves are typed by the HUMAN, in that
  session, never run by an agent. Every text that offers one gives the exact line and says the agent
  never runs it itself ("never run it yourself"):
      ! <plugin>/bin/agent-start.sh --take-over      second-session start text, closed notice and
                                                     closed ROLE text, RELEASED output, PRINCIPLES W10
      ! <plugin>/bin/agent-start.sh --release        whole-repo close-case hook text (main manager),
                                                     skills/close-case part B (the final table ends
                                                     with it, for the human), PRINCIPLES W13
  The "!" prefix runs it in the session's own shell ($CLAUDE_PID, $CLAUDE_CODE_SESSION_ID set).

Run: python3 -m unittest tests.test_agent_main_seat </dev/null
"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase  # noqa: E402

NOBODY = "999999"   # a CLAUDE_PID no lock names and no process has


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


class SeatCase(ScriptCase):
    script = "agent-start.sh"

    def setUp(self):
        super().setUp()
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
                p.wait()
        super().tearDown()

    def live(self):
        """A live pid that is not this test process: a stand-in session."""
        proc = subprocess.Popen(["sleep", "120"])
        self.procs.append(proc)
        return proc.pid

    @property
    def lock_path(self):
        return self.repo.path(".git", "agent_main.lock")

    def lock_words(self):
        if not os.path.exists(self.lock_path):
            return None
        with open(self.lock_path) as fh:
            return fh.read().split()

    def set_lock(self, text):
        with open(self.lock_path, "w") as fh:
            fh.write(text)

    def start(self, *args, pid=NOBODY, sid=None, source=None, env=None, cwd=None):
        full = {"CLAUDE_PID": str(pid)}
        full.update(env or {})
        stdin = None
        if source is not None:
            stdin = json.dumps({"session_id": sid or "sid-hook", "transcript_path": "/tmp/x.jsonl",
                                "cwd": cwd or self.repo.cwd, "hook_event_name": "SessionStart",
                                "source": source})
        elif sid is not None:
            full["CLAUDE_CODE_SESSION_ID"] = sid
        return self.repo.run("agent-start.sh", *args, env=full, stdin=stdin, cwd=cwd)

    def prompt(self, text="next task please", pid=NOBODY):
        stdin = json.dumps({"session_id": "s-prompt", "transcript_path": "/tmp/x.jsonl",
                            "cwd": self.repo.cwd, "permission_mode": "auto",
                            "hook_event_name": "UserPromptSubmit", "prompt": text})
        result = self.repo.run("agent-close-case.sh", env={"CLAUDE_PID": str(pid)}, stdin=stdin)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def become_main(self, pid, sid="sid-main"):
        out = self.assertOk(self.start(pid=pid, sid=sid))
        self.assertIn("ROLE: main manager", out)
        return out


# -- the lock line -----------------------------------------------------------

class TestLockLine(SeatCase):
    def test_hook_start_records_sid_and_terminal(self):
        self.assertOk(self.start(pid=4242, source="startup", sid="sid-hook-1",
                                 env={"ORCA_TERMINAL_HANDLE": "term_main-1"}))
        words = self.lock_words()
        self.assertEqual(words[0], "4242")
        self.assertRegex(words[1], r"^\d{4}-\d\d-\d\d$")
        self.assertRegex(words[2], r"^\d\d:\d\d$")
        self.assertEqual(words[3:], ["sid-hook-1", "term_main-1"])

    def test_by_hand_the_sid_comes_from_the_env(self):
        self.assertOk(self.start(pid=4242, sid="sid-env-1"))
        self.assertEqual(self.lock_words()[3:], ["sid-env-1", "-"])

    def test_unknown_sid_is_a_dash(self):
        self.assertOk(self.start(pid=4242))
        self.assertEqual(self.lock_words()[3:], ["-", "-"])

    def test_clear_keeps_the_lock_with_the_new_sid(self):
        self.assertOk(self.start(pid=4242, source="startup", sid="sid-before"))
        self.assertOk(self.start(pid=4242, source="clear", sid="sid-after"))
        self.assertEqual(self.lock_words()[0], "4242")
        self.assertEqual(self.lock_words()[3], "sid-after")


# -- R4: the second session knows who is main, and how to take over --------

class TestSecondSession(SeatCase):
    def test_names_the_live_main_manager(self):
        main = self.live()
        self.set_lock("%d 2026-09-30 10:00 sid-m term_main-7\n" % main)
        out = self.assertOk(self.start())
        self.assertIn("ROLE: task manager, human-direct", out)
        self.assertIn('Main manager already running: pid %d ("project Manager", terminal term_main-7), '
                      'since 2026-09-30 10:00.' % main, out)
        self.assertIn("%s/bin/agent-start.sh --take-over" % self.repo.plugin, out)
        self.assertIn("human asks", out)

    def test_an_old_lock_still_works(self):
        main = self.live()
        self.set_lock("%d 2026-09-30 10:00\n" % main)
        out = self.assertOk(self.start())
        self.assertIn('pid %d ("project Manager"), since 2026-09-30 10:00.' % main, out)
        self.assertIn("--take-over", out)

    def test_no_terminal_is_not_printed_as_a_dash(self):
        main = self.live()
        self.set_lock("%d 2026-09-30 10:00 sid-m -\n" % main)
        out = self.assertOk(self.start())
        self.assertIn('pid %d ("project Manager"), since 2026-09-30 10:00.' % main, out)


class TestTakeOver(SeatCase):
    def test_moves_the_lock_here(self):
        old = self.live()
        self.set_lock("%d 2026-09-30 10:00 sid-old term_old\n" % old)
        result = self.start("--take-over", pid=5151, sid="sid-new",
                            env={"ORCA_TERMINAL_HANDLE": "term_new"})
        out = self.assertOk(result)
        self.assertIn("ROLE: main manager", out)
        self.assertIn("/rename project Manager", out)
        words = self.lock_words()
        self.assertEqual(words[0], "5151")
        self.assertEqual(words[3:], ["sid-new", "term_new"])

    def test_never_for_a_spawned_agent(self):
        old = self.live()
        text = "%d 2026-09-30 10:00 sid-old -\n" % old
        self.set_lock(text)
        result = self.start("--take-over", pid=5151, env={"AGENT_ROLE": "task-manager"})
        self.assertEqual(result.returncode, 1)
        with open(self.lock_path) as fh:
            self.assertEqual(fh.read(), text)

    def test_already_main_changes_nothing(self):
        text = "%d 2026-09-30 10:00 sid-me -\n" % os.getpid()
        self.set_lock(text)
        out = self.assertOk(self.start("--take-over", pid=os.getpid()))
        self.assertIn("already", out.lower())
        with open(self.lock_path) as fh:
            self.assertEqual(fh.read(), text)

    def test_its_own_human_direct_line_goes(self):
        old = self.live()
        self.set_lock("%d 2026-09-30 10:00 sid-old -\n" % old)
        self.assertOk(self.start(pid=5151))
        self.assertIn("human-direct", self.repo.read("agent_worktree.txt"))
        self.assertOk(self.start("--take-over", pid=5151))
        self.assertNotIn("human-direct", self.repo.read("agent_worktree.txt"))

    def test_the_old_main_manager_is_told_once(self):
        old = self.live()
        self.set_lock("%d 2026-09-30 10:00 sid-old -\n" % old)
        self.assertOk(self.start("--take-over", pid=5151))
        first = self.prompt(pid=old)
        self.assertIn("no longer the main manager", first)
        self.assertIn("pid 5151", first)
        self.assertEqual(self.prompt(pid=old), "")

    def test_the_old_main_manager_never_takes_the_lock_back_by_itself(self):
        old = self.live()
        self.set_lock("%d 2026-09-30 10:00 sid-old -\n" % old)
        self.assertOk(self.start("--take-over", pid=5151))
        for source in ("compact", "clear"):
            with self.subTest(source=source):
                out = self.assertOk(self.start(pid=old, source=source, sid="sid-old-" + source))
                self.assertNotIn("ROLE: main manager", out)
                self.assertIn("no longer the main manager", out)
                self.assertEqual(self.lock_words()[0], "5151")


# -- city-rediscover R2: the holder's own old lock line gets its sid and terminal --

class TestLockUpgrade(SeatCase):
    OLD = "%d 2026-09-30 20:03\n"

    def closed_exists(self):
        return os.path.exists(self.repo.path(".git", "agent_main.closed"))

    def test_take_over_by_the_holder_fills_an_old_lock(self):
        me = self.live()
        self.set_lock(self.OLD % me)
        out = self.assertOk(self.start("--take-over", pid=me, sid="sid-me",
                                       env={"ORCA_TERMINAL_HANDLE": "term_me"}))
        self.assertIn("Already the main manager (lock: pid %d)." % me, out)
        self.assertIn("updated", out.lower())
        self.assertNotIn("Nothing changed", out)
        self.assertEqual(self.lock_words(), [str(me), "2026-09-30", "20:03", "sid-me", "term_me"])
        self.assertFalse(self.closed_exists(), "nobody was replaced")

    def test_a_dash_sid_is_filled_too(self):
        me = self.live()
        self.set_lock("%d 2026-09-30 20:03 - -\n" % me)
        self.assertOk(self.start("--take-over", pid=me, sid="sid-me"))
        self.assertEqual(self.lock_words(), [str(me), "2026-09-30", "20:03", "sid-me", "-"])

    def test_a_stale_sid_is_replaced(self):
        me = self.live()
        self.set_lock("%d 2026-09-30 20:03 sid-before-clear term_me\n" % me)
        out = self.assertOk(self.start("--take-over", pid=me, sid="sid-me"))
        self.assertNotIn("Nothing changed", out)
        self.assertEqual(self.lock_words(), [str(me), "2026-09-30", "20:03", "sid-me", "term_me"],
                         "the terminal the lock already had stays")

    def test_a_missing_terminal_is_filled(self):
        me = self.live()
        self.set_lock("%d 2026-09-30 20:03 sid-me -\n" % me)
        self.assertOk(self.start("--take-over", pid=me, sid="sid-me", env={"ORCA_TERMINAL_HANDLE": "term_me"}))
        self.assertEqual(self.lock_words()[3:], ["sid-me", "term_me"])

    def test_nothing_known_changes_nothing(self):
        me = self.live()
        self.set_lock(self.OLD % me)
        out = self.assertOk(self.start("--take-over", pid=me))          # no sid, no terminal
        self.assertIn("Nothing changed", out)
        with open(self.lock_path) as fh:
            self.assertEqual(fh.read(), self.OLD % me)

    def test_a_complete_lock_changes_nothing(self):
        me = self.live()
        text = "%d 2026-09-30 20:03 sid-me term_me\n" % me
        self.set_lock(text)
        out = self.assertOk(self.start("--take-over", pid=me, sid="sid-me",
                                       env={"ORCA_TERMINAL_HANDLE": "term_me"}))
        self.assertIn("Nothing changed", out)
        with open(self.lock_path) as fh:
            self.assertEqual(fh.read(), text)

    def test_a_plain_start_by_the_holder_fills_an_old_lock(self):
        me = self.live()
        self.set_lock(self.OLD % me)
        out = self.assertOk(self.start(pid=me, sid="sid-me", env={"ORCA_TERMINAL_HANDLE": "term_me"}))
        self.assertIn("ROLE: main manager (lock: pid %d)" % me, out)
        words = self.lock_words()
        self.assertEqual(words[0], str(me))
        self.assertEqual(words[3:], ["sid-me", "term_me"])

    def test_the_holders_hook_start_fills_an_old_lock(self):
        me = self.live()
        for source in ("startup", "resume", "compact", "clear"):
            with self.subTest(source=source):
                self.set_lock(self.OLD % me)
                self.assertOk(self.start(pid=me, source=source, sid="sid-" + source))
                self.assertEqual(self.lock_words()[0], str(me))
                self.assertEqual(self.lock_words()[3], "sid-" + source)

    def test_another_session_never_touches_an_old_lock(self):
        main = self.live()
        self.set_lock(self.OLD % main)
        for args in ((), ("--release",)):
            with self.subTest(args=args):
                self.start(*args, pid=5151, sid="sid-other", env={"ORCA_TERMINAL_HANDLE": "term_other"})
                with open(self.lock_path) as fh:
                    self.assertEqual(fh.read(), self.OLD % main)


# -- R3: a whole-repo close case frees the seat -----------------------------

class TestRelease(SeatCase):
    def test_the_holder_releases(self):
        me = self.live()
        self.become_main(me)
        out = self.assertOk(self.start("--release", pid=me))
        self.assertIn("RELEASED", out)
        self.assertIsNone(self.lock_words())

    def test_only_the_holder(self):
        main = self.live()
        text = "%d 2026-09-30 10:00 sid-m -\n" % main
        self.set_lock(text)
        result = self.start("--release", pid=5151)
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(main), result.stdout + result.stderr)
        with open(self.lock_path) as fh:
            self.assertEqual(fh.read(), text)

    def test_the_next_new_session_is_main_not_helper(self):
        """E3: close case finished, the owner opens a new session."""
        me = self.live()
        self.become_main(me)
        self.assertOk(self.start("--release", pid=me))
        out = self.assertOk(self.start(pid=6161, source="startup", sid="sid-next"))
        self.assertIn("ROLE: main manager", out)
        self.assertNotIn("human-direct", out)
        self.assertEqual(self.lock_words()[0], "6161")

    def test_the_released_session_never_takes_the_lock_back_by_itself(self):
        me = self.live()
        self.become_main(me)
        self.assertOk(self.start("--release", pid=me))
        for source in ("compact", "clear", None):
            with self.subTest(source=source):
                out = self.assertOk(self.start(pid=me, source=source, sid="sid-again-%s" % source))
                self.assertNotIn("ROLE: main manager", out)
                self.assertIn("no longer the main manager", out)
                self.assertIsNone(self.lock_words())

    def test_the_released_session_is_told_once(self):
        me = self.live()
        self.become_main(me)
        self.assertOk(self.start("--release", pid=me))
        first = self.prompt(pid=me)
        self.assertIn("no longer the main manager", first)
        self.assertIn("--take-over", first)
        self.assertIn("/rename project Helper", first)
        self.assertEqual(self.prompt(pid=me), "")

    def test_told_names_the_new_main_manager(self):
        me = self.live()
        self.become_main(me)
        self.assertOk(self.start("--release", pid=me))
        self.become_main(os.getpid(), sid="sid-new-main")
        first = self.prompt(pid=me)
        self.assertIn("no longer the main manager", first)
        self.assertIn("pid %d" % os.getpid(), first)

    def test_other_sessions_are_not_told(self):
        me = self.live()
        self.become_main(me)
        self.assertOk(self.start("--release", pid=me))
        self.assertEqual(self.prompt(pid=7171), "")

    def test_later_prompts_are_quiet(self):
        me = self.live()
        self.become_main(me)
        self.assertOk(self.start("--release", pid=me))
        self.prompt(pid=me)
        self.assertEqual(self.prompt("hello", pid=me), "")

    def test_it_can_take_over_again_when_the_human_asks(self):
        me = self.live()
        self.become_main(me)
        self.assertOk(self.start("--release", pid=me))
        out = self.assertOk(self.start("--take-over", pid=me, sid="sid-back"))
        self.assertIn("ROLE: main manager", out)
        self.assertEqual(self.lock_words()[0], str(me))
        out = self.assertOk(self.start(pid=me, source="compact", sid="sid-back"))
        self.assertIn("ROLE: main manager", out)


# -- the words the agents read ------------------------------------------------

class TestTheTexts(SeatCase):
    def test_whole_repo_close_case_ends_with_the_release(self):
        text = read("skills", "close-case", "SKILL.md")
        part_b = text[text.index("## B."):]
        self.assertIn("agent-start.sh --release", part_b)
        self.assertGreater(part_b.index("--release"), part_b.index("final table"),
                           "the seat is freed at the very end")

    def test_the_main_close_case_hook_says_release(self):
        self.set_lock("%d 2026-09-30 10:00 sid-me -\n" % os.getpid())
        out = self.prompt("close case", pid=os.getpid())
        self.assertIn("whole repo", out)
        self.assertIn("--release", out)
        self.assertLessEqual(len(out.encode()), 1200)

    def test_principles_say_it(self):
        text = read("PRINCIPLES.md")
        w10 = text[text.index("W10."):text.index("W11.")]
        w13 = text[text.index("W13."):text.index("## C.")]
        self.assertIn("--take-over", w10)
        self.assertIn("--release", w13)

    def test_city_requirement_says_it(self):
        text = read("requirements", "city.md")
        data_path = text[text.index("## Data path"):text.index("## Look")]
        self.assertIn("agent_main.lock", data_path)
        self.assertNotIn("Session without `AGENT_ROLE` = governor", data_path)


class TestTheHumanTypesIt(SeatCase):
    """BOUNCE 1: never an agent command; the human types the exact ! line."""

    def take_over_line(self):
        return "! %s/bin/agent-start.sh --take-over" % self.repo.plugin

    def release_line(self):
        return "! %s/bin/agent-start.sh --release" % self.repo.plugin

    def test_the_second_session_gets_the_line(self):
        self.set_lock("%d 2026-09-30 10:00 sid-m -\n" % self.live())
        out = self.assertOk(self.start())
        self.assertIn(self.take_over_line(), out)
        self.assertIn("never run it yourself", out)

    def test_the_closed_notice_and_role_get_the_line(self):
        me = self.live()
        self.become_main(me)
        released = self.assertOk(self.start("--release", pid=me))
        self.assertIn(self.take_over_line(), released)
        notice = self.prompt(pid=me)
        role = self.assertOk(self.start(pid=me, source="compact", sid="sid-c"))
        for text in (notice, role):
            with self.subTest(text=text[:30]):
                self.assertIn(self.take_over_line(), text)
                self.assertIn("never run it yourself", text)

    def test_the_whole_repo_close_case_gives_the_release_line(self):
        self.set_lock("%d 2026-09-30 10:00 sid-me -\n" % os.getpid())
        out = self.prompt("close case", pid=os.getpid())
        self.assertIn(self.release_line(), out)
        self.assertIn("never run it yourself", out)
        self.assertLessEqual(len(out.encode()), 1200)

    def test_the_skill_never_runs_it(self):
        part_b = read("skills", "close-case", "SKILL.md").split("## B.", 1)[1]
        self.assertIn("! ${CLAUDE_PLUGIN_ROOT}/bin/agent-start.sh --release", part_b)
        self.assertIn("never run it yourself", part_b)
        self.assertNotIn("run `${CLAUDE_PLUGIN_ROOT}/bin/agent-start.sh --release`", part_b)

    def test_the_principles_say_the_human_types_it(self):
        text = read("PRINCIPLES.md")
        w10 = text[text.index("W10."):text.index("W11.")]
        w13 = text[text.index("W13."):text.index("## C.")]
        self.assertIn("`! agent-start.sh --take-over`", w10)
        self.assertIn("`! agent-start.sh --release`", w13)
        for rule in (w10, w13):
            self.assertIn("never runs it", rule)


if __name__ == "__main__":
    unittest.main()
