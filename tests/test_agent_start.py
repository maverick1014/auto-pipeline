"""Failing tests for the short startup hook. Written by the task manager first.

CONTRACT. The SessionStart hook output has to fit the preview Claude Code
shows an agent, so it carries pointers, not content. A normal start on an
empty project is under 2048 bytes.

Normal start, in this order:

    ROLE: <...>
    PROJECT: <project root> | PLUGIN: <plugin root>
    RESOURCES: RAM <n>% CPU <n>% (cap <n>%) -> OK
    agent_todo.txt: <n> lines
    agent_completed.txt: <n> lines
    agent_ideas.txt: <n> lines
    agent_worktree.txt: <n> lines
      <every line of agent_worktree.txt, two spaces in front>
    agent_state.txt: <n> lines            only when the file has something
      <its first 30 lines, two spaces in front>
      (truncated, read the file)          only when it is longer than 30
    (agent_monitor.txt is no longer printed: bin/agent-monitor.sh is gone, 2026-11-24)
    RULES: read <plugin>/PRINCIPLES.md now (S8).
    QUIZ: run <plugin>/bin/agent-start.sh --quiz, then --answer. No work until PASS.

The last two lines are exactly those. No PRINCIPLES.md text and no quiz
question ever appears in the hook output, except the output section
("## E. Output", right before the RULES line; tests/test_agent_start.py).
The byte limits below are for the rest: pointer_part() drops the section.

    --quiz    prints the 44 questions and nothing else
    --answer  unchanged, still grades and still says PASS

Compaction (stdin source "compact"), nothing else at all:

    ROLE, the PROJECT/PLUGIN line, the COMPACTED line, agent_state.txt capped
    the same way, the RULES line. No RESOURCES, no counts, no QUIZ line.

Once per session (DEDUPE). A repo can carry the pack's SessionStart hook
while the machine also has the plugin on, so two copies fire for one event.
When the stdin JSON has a session_id, the real work runs once per event:

    marker   $PROJECT_GITDIR/agent_started_<session_id>   (in the git dir,
             never in the work tree)
    same session_id and same source again within AGENT_START_DEDUPE_SEC
    seconds (default 60)  -> exit 0, print nothing, write nothing
    a different session_id, or another source (compact, resume) -> runs
    two copies started at the same moment -> exactly one prints
    no session_id (a human or an agent running it by hand) -> never deduped
    a leftover lock from a killed run never silences a later run
    a repo that is not set up stays untouched: no marker either

The resource helper below is unchanged by all this.

No quiz for subagents (S9). A worker or deputy runs agent-start.sh by hand
(CLAUDE.md says so) inside its parent's session. Nothing in its environment
tells it apart from the parent: checked 2026-09-28, a worker subagent's env
is the parent's (same CLAUDE_CODE_SESSION_ID, CLAUDE_PID, AGENT_ROLE,
CLAUDE_EFFORT). What does tell: the session already passed the quiz, and a
session passes before it spawns anyone.

    --answer PASS with a session id (CLAUDE_CODE_SESSION_ID) writes the
      marker $PROJECT_GITDIR/agent_quiz_<session id>. A FAIL writes none.
      No session id -> no marker.
    a normal start whose session id (the hook's stdin session_id, else
      CLAUDE_CODE_SESSION_ID) has that marker prints QUIZ_DONE_LINE as its
      last line, in place of the quiz line
    another session, or no session id -> the quiz line, as before
    agent_quiz_* markers older than AGENT_MARKER_DAYS go with the others
"""

import json
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import BIN, ROOT, ScriptCase, ScriptRepo, pointer_part
import re  # noqa: E402
import glob  # noqa: E402
import shutil  # noqa: E402
from watchhelp import dead_pid  # noqa: E402
from watchhelp import now_text  # noqa: E402
import tempfile  # noqa: E402
import agent_conf  # noqa: E402

RULES_LINE = "RULES: read %s/PRINCIPLES.md now (S8)."
QUIZ_LINE = ("QUIZ: run %s/bin/agent-start.sh --quiz, then --answer. "
             "No work until PASS.")
QUIZ_DONE_LINE = ("QUIZ: PASS already in this session. A subagent (worker, "
                  "deputy) takes no quiz (S9). Go on with your brief.")


class StartCase(ScriptCase):
    script = "agent-start.sh"

    def start(self, *args, **kwargs):
        return self.repo.run("agent-start.sh", *args, **kwargs)

    def installed(self, entries):
        folder = os.path.join(self.repo.claude_dir(), "plugins")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "installed_plugins.json"), "w") as fh:
            json.dump({"version": 2, "plugins": {"auto-pipeline@auto-pipeline": entries}}, fh)

    def rules_line(self):
        return RULES_LINE % self.repo.plugin

    def quiz_line(self):
        return QUIZ_LINE % self.repo.plugin


class TestItFitsThePreview(StartCase):
    def test_an_empty_project_stays_under_two_kilobytes(self):
        out = pointer_part(self.assertOk(self.start()))
        self.assertLess(len(out.encode()), 2048,
                        "the hook is %d bytes, the preview cuts it"
                        % len(out.encode()))

    def test_no_principles_text(self):
        self.mark = "PLUGIN-PRINCIPLES-MARKER"
        with open(self.repo.plugin_path("PRINCIPLES.md"), "a") as fh:
            fh.write("\n%s\n" % self.mark)
        out = self.assertOk(self.start())
        self.assertNotIn(self.mark, out)
        self.assertNotIn("=== PRINCIPLES.md ===", out)

    def test_no_quiz_question(self):
        out = self.assertOk(self.start())
        self.assertNotIn("Q1.", out)
        self.assertNotIn("=== QUIZ", out)

    def test_it_points_at_both_instead(self):
        out = self.assertOk(self.start())
        lines = self.lines(out)
        self.assertEqual(lines[-2], self.rules_line())
        self.assertEqual(lines[-1], self.quiz_line())


class TestItFitsThePreviewOnARealProject(StartCase):
    """30 lines is not a size. A state file whose first 30 lines are a brief
    is 8 KB on its own, and the preview cuts it just the same. The whole
    output stays at or under 2000 bytes, always, by giving the state block
    whatever budget is left and saying so when it trims."""

    CAP = 2000

    def start(self, *args, **kwargs):
        # A session pid with no --model/--effort flags (this runner), so the
        # YOU line reads agent.conf on every machine: the longest form, the
        # one a gate runner with no claude ancestor sees. Without it the
        # runner's own claude flags shorten the line and hide a cut.
        env = dict(kwargs.pop("env", None) or {})
        env.setdefault("CLAUDE_PID", str(os.getpid()))
        return super().start(*args, env=env, **kwargs)

    def busy_project(self):
        long_line = "x" * 400
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            for i in range(4):
                fh.write("/very/long/path/to/worktree/number_%d | module_%d | "
                         "working | since 2026-09-22 10:00\n" % (i, i))
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            for i in range(60):
                fh.write("%02d %s\n" % (i, long_line))
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("alpha | big | one\n")

    def test_a_busy_project_still_fits(self):
        self.busy_project()
        out = pointer_part(self.assertOk(self.start()))
        self.assertLessEqual(len(out.encode()), self.CAP,
                             "the hook is %d bytes:\n%s"
                             % (len(out.encode()), out[:600]))

    def test_it_says_it_trimmed(self):
        self.busy_project()
        out = self.assertOk(self.start())
        self.assertIn("(truncated, read the file)", out)

    def test_the_two_pointer_lines_are_never_trimmed_away(self):
        self.busy_project()
        lines = self.lines(self.assertOk(self.start()))
        self.assertEqual(lines[-2], self.rules_line())
        self.assertEqual(lines[-1], self.quiz_line())

    def test_the_worktree_lines_survive(self):
        """They are what the main manager reads before every dispatch (W9)."""
        self.busy_project()
        out = self.assertOk(self.start())
        self.assertIn("agent_worktree.txt: 4 lines", out)
        self.assertIn("/very/long/path/to/worktree/number_3", out)

    def test_the_counts_survive(self):
        self.busy_project()
        out = self.assertOk(self.start())
        self.assertIn("agent_todo.txt: 1 lines", out)
        self.assertIn("agent_state.txt: 60 lines", out)

    def test_a_single_huge_line_does_not_break_the_cap(self):
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            fh.write("y" * 9000 + "\n")
        out = pointer_part(self.assertOk(self.start()))
        self.assertLessEqual(len(out.encode()), self.CAP,
                             "one long line blew the cap: %d bytes"
                             % len(out.encode()))
        self.assertIn("(truncated, read the file)", out)

    def test_the_compact_path_fits_too(self):
        self.busy_project()
        out = pointer_part(self.assertOk(self.start(
            stdin='{"cwd": "%s", "session_id": "s1", "source": "compact"}'
                  % self.repo.dir)))
        self.assertLessEqual(len(out.encode()), self.CAP,
                             "compact output is %d bytes" % len(out.encode()))


class TestTheRootsLine(StartCase):
    def test_it_names_both_roots(self):
        out = self.assertOk(self.start())
        self.assertIn("PROJECT: %s | PLUGIN: %s"
                      % (self.repo.dir, self.repo.plugin), out)

    def test_it_comes_second(self):
        lines = self.lines(self.assertOk(self.start()))
        self.assertTrue(lines[0].startswith("ROLE:"), lines[0])
        self.assertTrue(lines[1].startswith("PROJECT: "), lines[1])
        self.assertTrue(lines[2].startswith("RESOURCES: "), lines[2])

    def test_it_has_a_language_line(self):
        out = self.assertOk(self.start())
        lines = [l for l in self.lines(out) if l.startswith("LANGUAGE: ")]
        self.assertEqual(len(lines), 1, out)

    def test_it_follows_the_hook_cwd(self):
        other = self.repo.make_project("other")
        self.repo.git_init(other)
        # A project that is already set up, so the scope guard stays out of the
        # way and this test keeps proving the one thing it is about: the roots
        # follow the hook's cwd, not the process's.
        open(os.path.join(other, "agent_todo.txt"), "w").close()
        out = self.assertOk(self.start(
            cwd=self.repo.plugin,
            stdin='{"cwd": "%s", "source": "startup"}' % other))
        self.assertIn("PROJECT: %s | PLUGIN: %s" % (other, self.repo.plugin), out)


class TestTheCounts(StartCase):
    def test_every_task_file_gets_one_line(self):
        out = self.assertOk(self.start())
        for name in ("agent_todo.txt", "agent_completed.txt",
                     "agent_ideas.txt", "agent_worktree.txt"):
            with self.subTest(name=name):
                self.assertIn("%s: 0 lines" % name, out)

    def test_the_count_is_the_real_one(self):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("a | big | one\nb | big | two\nc | big | three\n")
        out = self.assertOk(self.start())
        self.assertIn("agent_todo.txt: 3 lines", out)

    def test_the_task_lines_themselves_are_not_printed(self):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("alpha | big | the open task\n")
        out = self.assertOk(self.start())
        self.assertNotIn("the open task", out)


class TestTheWorktreeLines(StartCase):
    LINE = "/tmp/wt_alpha | alpha | working | since 2026-09-21 10:00"

    def test_they_are_printed_in_full(self):
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            fh.write(self.LINE + "\n")
        out = self.assertOk(self.start())
        self.assertIn("agent_worktree.txt: 1 lines", out)
        self.assertIn("  " + self.LINE, out)

    def test_nothing_is_printed_when_there_are_none(self):
        out = self.assertOk(self.start())
        after = out.split("agent_worktree.txt: 0 lines")[1]
        self.assertFalse(after.strip().startswith("|"), after[:80])


class TestTheStateFile(StartCase):
    def test_a_short_one_is_printed_whole(self):
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            fh.write("STEP: 3 of 7\nNEXT: write the tests\n")
        out = self.assertOk(self.start())
        self.assertIn("agent_state.txt: 2 lines", out)
        self.assertIn("  STEP: 3 of 7", out)
        self.assertIn("  NEXT: write the tests", out)
        self.assertNotIn("(truncated, read the file)", out)

    def test_a_long_one_is_capped_at_thirty(self):
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            fh.write("".join("line %d\n" % i for i in range(1, 51)))
        out = self.assertOk(self.start())
        self.assertIn("agent_state.txt: 50 lines", out)
        self.assertIn("  line 30", out)
        self.assertNotIn("  line 31", out)
        self.assertIn("(truncated, read the file)", out)

    def test_nothing_when_there_is_no_state_file(self):
        out = self.assertOk(self.start())
        self.assertNotIn("agent_state.txt:", out)


class TestQuizFlag(StartCase):
    def test_it_prints_all_twenty_nine_questions(self):
        out = self.assertOk(self.start("--quiz"))
        for n in range(1, 30):
            with self.subTest(n=n):
                self.assertIn("Q%d." % n, out)

    def test_it_says_how_to_answer(self):
        out = self.assertOk(self.start("--quiz"))
        self.assertIn("--answer", out)

    def test_it_prints_nothing_else(self):
        out = self.assertOk(self.start("--quiz"))
        self.assertNotIn("ROLE:", out)
        self.assertNotIn("RESOURCES:", out)
        self.assertNotIn("PROJECT:", out)

    def test_it_writes_no_lock(self):
        self.assertOk(self.start("--quiz"))
        self.assertFalse(os.path.exists(self.repo.path(".git",
                                                       "agent_main.lock")))


class TestCompactPath(StartCase):
    def compact(self, **kwargs):
        return self.start(
            stdin='{"cwd": "%s", "session_id": "s1", "source": "compact"}'
                  % self.repo.dir, **kwargs)

    def test_it_says_it_was_compacted(self):
        out = self.assertOk(self.compact())
        self.assertIn("COMPACTED 1 time(s) this session", out)

    def test_it_keeps_the_roots_line(self):
        out = self.assertOk(self.compact())
        self.assertIn("PROJECT: %s | PLUGIN: %s"
                      % (self.repo.dir, self.repo.plugin), out)

    def test_it_keeps_the_rules_line(self):
        out = self.assertOk(self.compact())
        self.assertIn(self.rules_line(), out)

    def test_it_has_no_quiz_line_and_no_counts(self):
        out = self.assertOk(self.compact())
        self.assertNotIn("QUIZ:", out)
        self.assertNotIn("agent_todo.txt:", out)
        self.assertNotIn("RESOURCES:", out)

    def test_the_state_file_is_capped_the_same_way(self):
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            fh.write("".join("line %d\n" % i for i in range(1, 51)))
        out = self.assertOk(self.compact())
        self.assertIn("  line 30", out)
        self.assertNotIn("  line 31", out)
        self.assertIn("(truncated, read the file)", out)


class TestClearPath(StartCase):
    def clear(self, **kwargs):
        return self.start(
            stdin='{"cwd": "%s", "session_id": "s2", "source": "clear"}'
                  % self.repo.dir, **kwargs)

    def test_it_says_cleared_and_keeps_role_and_rules(self):
        out = self.assertOk(self.clear())
        self.assertIn("ROLE:", out)
        self.assertIn(self.rules_line(), out)
        self.assertIn(
            "CLEARED. Continue from agent_state.txt, not from memory (S8).",
            out)

    def test_it_prints_the_state_block(self):
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            fh.write("STEP: 3 of 7\nNEXT: write the tests\n")
        out = self.assertOk(self.clear())
        self.assertIn("agent_state.txt: 2 lines", out)
        self.assertIn("  STEP: 3 of 7", out)

    def test_it_has_no_quiz_no_resources_no_auto_resume(self):
        out = self.assertOk(self.clear())
        self.assertNotIn("QUIZ:", out)
        self.assertNotIn("RESOURCES:", out)
        self.assertNotIn("agent_todo.txt:", out)
        self.assertNotIn("=== auto resume ===", out)

    def test_the_compact_counter_is_untouched(self):
        self.assertOk(self.clear())
        self.assertFalse(os.path.exists(
            self.repo.path(".git", "agent_compact_s2")))

    def test_a_second_clear_within_the_window_is_silent(self):
        self.assertOk(self.clear())
        out = self.assertOk(self.clear())
        self.assertEqual(out, "")


class TestResourcesHelper(StartCase):
    def helper(self, *args, **kwargs):
        return self.repo.run("agent-resources.sh", *args, **kwargs)

    def test_the_helper_file_exists(self):
        self.assertTrue(
            os.path.exists(self.repo.plugin_path("bin", "agent-resources.sh")),
            "bin/agent-resources.sh is missing")

    def test_agent_start_uses_the_fake_readings(self):
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "12",
                                            "AGENT_FAKE_CPU": "34"}))
        self.assertIn("RESOURCES: RAM 12% CPU 34% (cap 80%) -> OK", out)

    def test_over_cap_line_and_warning(self):
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "95",
                                            "AGENT_FAKE_CPU": "10"}))
        self.assertIn("RESOURCES: RAM 95% CPU 10% (cap 80%) -> OVER CAP", out)
        self.assertIn("Do not start agents", out)

    def test_cpu_over_cap_also_trips_it(self):
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "10",
                                            "AGENT_FAKE_CPU": "99"}))
        self.assertIn("-> OVER CAP", out)

    def test_cap_comes_from_agent_conf(self):
        self.repo.set_conf("max_usage_percent", "30")
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "40",
                                            "AGENT_FAKE_CPU": "10"}))
        self.assertIn("(cap 30%) -> OVER CAP", out)

    def test_exactly_at_the_cap_is_not_over(self):
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "80",
                                            "AGENT_FAKE_CPU": "80"}))
        self.assertIn("(cap 80%) -> OK", out)

    def test_the_helper_can_be_sourced_on_its_own(self):
        self.repo.write_bin_script(
            "check.sh",
            "#!/usr/bin/env bash\nset -eu\n"
                     "cd \"$(dirname \"$0\")\"\n"
                     ". ./agent-resources.sh\n"
                     "resources_line 80\n"
                     "resources_ok 80 && echo under || echo over\n")
        out = self.assertOk(self.repo.run("check.sh",
                                          env={"AGENT_FAKE_RAM": "15",
                                               "AGENT_FAKE_CPU": "25"}))
        self.assertIn("RESOURCES: RAM 15% CPU 25% (cap 80%) -> OK", out)
        self.assertIn("under", out)

    def test_the_reading_is_taken_once(self):
        """resources_read fills RAM_USED and CPU_USED. The rest reuse them.

        Reading twice costs about 1.4 seconds each time on a Mac, and the
        printed line can then disagree with the decision that follows it.
        """
        self.repo.write_bin_script(
            "check3.sh",
            "#!/usr/bin/env bash\nset -eu\n"
                     "cd \"$(dirname \"$0\")\"\n"
                     ". ./agent-resources.sh\n"
                     "resources_read\n"
                     "echo \"read: $RAM_USED $CPU_USED\"\n"
                     "AGENT_FAKE_RAM=99 AGENT_FAKE_CPU=98 resources_line 80\n")
        out = self.assertOk(self.repo.run("check3.sh",
                                          env={"AGENT_FAKE_RAM": "11",
                                               "AGENT_FAKE_CPU": "22"}))
        self.assertIn("read: 11 22", out)
        self.assertIn("RESOURCES: RAM 11% CPU 22% (cap 80%) -> OK", out,
                      "resources_line measured again instead of reusing the reading")

    def test_agent_start_reads_the_machine_once(self):
        """One reading for the line and the warning together."""
        self.repo.write_bin_script(
            "count.sh",
            "#!/usr/bin/env bash\nset -eu\n"
                     "cd \"$(dirname \"$0\")\"\n"
                     ". ./agent-resources.sh\n"
                     "resources_read\n"
                     "resources_line 80 >/dev/null\n"
                     "resources_ok 80 && echo under || echo over\n"
                     "echo \"ram=$RAM_USED\"\n")
        out = self.assertOk(self.repo.run("count.sh",
                                          env={"AGENT_FAKE_RAM": "11",
                                               "AGENT_FAKE_CPU": "22"}))
        self.assertIn("under", out)
        self.assertIn("ram=11", out)

    def test_resources_ok_fails_over_the_cap(self):
        self.repo.write_bin_script(
            "check2.sh",
            "#!/usr/bin/env bash\nset -eu\n"
                     "cd \"$(dirname \"$0\")\"\n"
                     ". ./agent-resources.sh\n"
                     "resources_ok 80 && echo under || echo over\n")
        out = self.assertOk(self.repo.run("check2.sh",
                                          env={"AGENT_FAKE_RAM": "90",
                                               "AGENT_FAKE_CPU": "10"}))
        self.assertIn("over", out)


class TestQuizStillWorks(StartCase):
    ANSWERS = ("1A 2D 3C 4B 5D 6D 7C 8C 9A 10D 11C 12C 13D 14C 15D 16B 17C "
               "18D 19C 20A 21D 22C 23B 24D 25B 26D 27B 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C 38B 39B 40B 41C 42A 43D 44B")   # check-blocks: Q38 is a blocks question now

    def test_all_right_is_a_pass(self):
        out = self.assertOk(self.start("--answer", self.ANSWERS))
        self.assertIn("44/44 PASS", out)

    def test_one_wrong_is_a_fail(self):
        result = self.start("--answer", self.ANSWERS.replace("1A", "1B"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL", result.stdout)


class TestNoQuizForSubagents(StartCase):
    ANSWERS = TestQuizStillWorks.ANSWERS

    def sid(self, sid="sess-1", **more):
        env = {"CLAUDE_CODE_SESSION_ID": sid, "AGENT_ROLE": "task-manager"}
        env.update(more)
        return env

    def quiz_marker(self, sid="sess-1"):
        return self.repo.path(".git", "agent_quiz_%s" % sid)

    def pass_quiz(self, sid="sess-1"):
        out = self.assertOk(self.start("--answer", self.ANSWERS,
                                       env=self.sid(sid)))
        self.assertIn("44/44 PASS", out)

    def test_a_pass_writes_the_session_marker(self):
        self.pass_quiz()
        self.assertTrue(os.path.exists(self.quiz_marker()))

    def test_a_run_by_hand_after_the_pass_skips_the_quiz_line(self):
        self.pass_quiz()
        lines = self.lines(self.assertOk(self.start(env=self.sid())))
        self.assertNotIn(self.quiz_line(), lines)
        self.assertEqual(lines[-1], QUIZ_DONE_LINE)
        self.assertEqual(lines[-2], self.rules_line())

    def test_the_hook_session_id_counts_too(self):
        self.pass_quiz("sess-9")
        stdin = json.dumps({"cwd": self.repo.dir, "session_id": "sess-9",
                            "source": "resume"})
        out = self.assertOk(self.start(stdin=stdin,
                                       env={"AGENT_ROLE": "task-manager"}))
        self.assertEqual(self.lines(out)[-1], QUIZ_DONE_LINE)

    def test_another_session_still_gets_the_quiz(self):
        self.pass_quiz("sess-1")
        lines = self.lines(self.assertOk(self.start(env=self.sid("sess-2"))))
        self.assertEqual(lines[-1], self.quiz_line())

    def test_no_session_id_still_gets_the_quiz(self):
        self.pass_quiz("sess-1")
        out = self.assertOk(self.start(env={"AGENT_ROLE": "task-manager"}))
        self.assertEqual(self.lines(out)[-1], self.quiz_line())

    def test_a_fail_writes_no_marker(self):
        result = self.start("--answer", self.ANSWERS.replace("1A", "1B"),
                            env=self.sid())
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(self.quiz_marker()))
        lines = self.lines(self.assertOk(self.start(env=self.sid())))
        self.assertEqual(lines[-1], self.quiz_line())

    def test_a_pass_with_no_session_id_writes_no_marker(self):
        self.assertOk(self.start("--answer", self.ANSWERS))
        left = [n for n in os.listdir(self.repo.path(".git"))
                if n.startswith("agent_quiz_")]
        self.assertEqual(left, [])

    def test_the_pass_output_is_unchanged(self):
        out = self.assertOk(self.start("--answer", self.ANSWERS,
                                       env=self.sid()))
        self.assertEqual(self.lines(out),
                         ["QUIZ RESULT: 44/44 PASS", "You may start work."])

    def test_it_still_fits_the_cap(self):
        self.pass_quiz()
        out = pointer_part(self.assertOk(self.start(env=self.sid())))
        self.assertLessEqual(len(out.encode()), 2000)

    def test_an_old_quiz_marker_is_cleaned_at_startup(self):
        old = self.quiz_marker("old-sess")
        with open(old, "w") as fh:
            fh.write("pass\n")
        when = time.time() - 8 * 86400
        os.utime(old, (when, when))
        stdin = json.dumps({"cwd": self.repo.dir, "session_id": "cur-q",
                            "source": "startup"})
        self.assertOk(self.start(stdin=stdin,
                                 env={"AGENT_ROLE": "task-manager"}))
        self.assertFalse(os.path.exists(old))


class TestAutoResume(StartCase):
    """The hook runs agent-resume.sh by itself for a main manager, new or
    taken over, on a real startup, when auto_resume=yes (default)."""

    def test_main_manager_startup_prints_it_and_stays_under_cap(self):
        out = pointer_part(self.assertOk(self.start()))
        self.assertIn("=== auto resume ===", out)
        self.assertLessEqual(len(out.encode()), 2000,
                             "hook is %d bytes" % len(out.encode()))

    def test_it_comes_before_rules_and_quiz(self):
        out = self.assertOk(self.start())
        lines = self.lines(out)
        resume_idx = next(i for i, l in enumerate(lines)
                          if l == "=== auto resume ===")
        rules_idx = lines.index(self.rules_line())
        quiz_idx = lines.index(self.quiz_line())
        self.assertLess(resume_idx, rules_idx)
        self.assertLess(rules_idx, quiz_idx)

    def test_spawned_role_does_not_print_it(self):
        out = self.assertOk(self.start(env={"AGENT_ROLE": "task-manager"}))
        self.assertNotIn("=== auto resume ===", out)

    def test_auto_resume_no_does_not_print_it(self):
        self.repo.set_conf("auto_resume", "no")
        out = self.assertOk(self.start())
        self.assertNotIn("=== auto resume ===", out)

    def test_compact_path_does_not_print_it(self):
        out = self.assertOk(self.start(
            stdin='{"cwd": "%s", "session_id": "s1", "source": "compact"}'
                  % self.repo.dir))
        self.assertNotIn("=== auto resume ===", out)


class TestGitignore(unittest.TestCase):
    def test_agent_monitor_txt_is_ignored(self):
        root = os.path.dirname(HERE)
        with open(os.path.join(root, ".gitignore")) as fh:
            lines = [l.strip() for l in fh]
        self.assertIn("agent_monitor.txt", lines)

    def test_the_half_written_sweep_file_is_ignored_too(self):
        """A sweep killed mid-write leaves agent_monitor.txt.tmp.<pid> behind."""
        root = os.path.dirname(HERE)
        with open(os.path.join(root, ".gitignore")) as fh:
            lines = [l.strip() for l in fh]
        self.assertIn("agent_monitor.txt.tmp.*", lines)


def tree(root):
    """Every file under root, .git included, with its bytes."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in dirnames:
            out[os.path.relpath(os.path.join(dirpath, name), root) + "/"] = "dir"
        for name in filenames:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                out[os.path.relpath(full, root)] = fh.read()
    return out


class TestOncePerSession(StartCase):
    """Two SessionStart hooks, one session: the work runs once."""

    def hook_json(self, sid, source="startup"):
        return json.dumps({"cwd": self.repo.dir, "session_id": sid,
                           "source": source})

    def hook(self, sid, source="startup", env=None):
        env = dict(env or {})
        env.setdefault("AGENT_ROLE", "task-manager")
        return self.start(stdin=self.hook_json(sid, source), env=env)

    def marker(self, sid):
        return self.repo.path(".git", "agent_started_%s" % sid)

    def test_the_first_run_prints_as_usual(self):
        self.assertIn("QUIZ:", self.assertOk(self.hook("s1")))

    def test_the_same_session_again_prints_nothing(self):
        self.assertOk(self.hook("s1"))
        result = self.hook("s1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_the_same_session_again_writes_nothing(self):
        self.assertOk(self.hook("s1"))
        before = tree(self.repo.dir)
        self.assertOk(self.hook("s1"))
        self.assertEqual(tree(self.repo.dir), before)

    def test_a_different_session_runs(self):
        self.assertOk(self.hook("s1"))
        self.assertIn("QUIZ:", self.assertOk(self.hook("s2")))

    def test_the_marker_lives_in_the_git_dir(self):
        self.assertOk(self.hook("s1"))
        self.assertTrue(os.path.exists(self.marker("s1")))
        self.assertFalse(os.path.exists(self.repo.path("agent_started_s1")))

    def test_no_session_id_is_never_deduped(self):
        env = {"AGENT_ROLE": "task-manager"}
        self.assertIn("QUIZ:", self.assertOk(self.start(env=env)))
        self.assertIn("QUIZ:", self.assertOk(self.start(env=env)))

    def test_two_copies_started_together_print_once(self):
        self.repo.set_conf("auto_resume", "no")
        for round_no in range(3):
            sid = "together-%d" % round_no
            procs = [subprocess.Popen(
                [self.repo.script_path("agent-start.sh")],
                cwd=self.repo.dir, env=self.repo._env({}),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True) for _ in range(2)]
            # both get their stdin at once, as Claude Code gives it to two
            # hooks; feeding copy 2 only after copy 1 ends would let its
            # `read -t 1` time out whenever a start takes over a second
            for p in procs:
                p.stdin.write(self.hook_json(sid))
                p.stdin.close()
            outs = [(p.stdout.read(), p.stderr.read()) for p in procs]
            for p in procs:
                p.wait(timeout=60)
                p.stdout.close()
                p.stderr.close()
            with self.subTest(round=round_no):
                self.assertEqual([p.returncode for p in procs], [0, 0],
                                 [o[1] for o in outs])
                printed = [o[0] for o in outs if o[0].strip()]
                self.assertEqual(len(printed), 1, outs)
                self.assertIn("QUIZ:", printed[0])

    def test_compaction_after_startup_still_prints(self):
        self.assertOk(self.hook("s1"))
        out = self.assertOk(self.hook("s1", "compact"))
        self.assertIn("COMPACTED 1 time(s) this session", out)

    def test_two_hooks_on_one_compaction_count_it_once(self):
        self.assertOk(self.hook("s1", "compact"))
        self.assertEqual(self.hook("s1", "compact").stdout, "")
        with open(self.repo.path(".git", "agent_compact_s1")) as fh:
            self.assertEqual(fh.read().strip(), "1")

    def test_a_later_compaction_counts_again(self):
        env = {"AGENT_START_DEDUPE_SEC": "0"}
        self.assertOk(self.hook("s1", "compact", env=env))
        out = self.assertOk(self.hook("s1", "compact", env=env))
        self.assertIn("COMPACTED 2 time(s) this session", out)

    def test_a_resumed_session_prints_again(self):
        self.assertOk(self.hook("s1"))
        self.assertIn("QUIZ:", self.assertOk(self.hook("s1", "resume")))

    # GNU coreutils stat, the one a Linux cloud VM has: -f takes no value
    # (it means "file system"), so `stat -f %m x` treats %m as a file name,
    # prints the file-system block of x and exits 1. -c <fmt> is the format.
    GNU_STAT = """#!/usr/bin/env bash
if [ "$1" = "-c" ]; then
  shift 2
  exec python3 -c 'import os,sys; print(int(os.stat(sys.argv[1]).st_mtime))' "$1"
fi
if [ "$1" = "-f" ]; then
  shift; rc=0
  for a in "$@"; do
    if [ -e "$a" ]; then printf '  File: "%s"\\n    ID: 0 Namelen: 255 Type: ext2/ext3\\n' "$a"
    else echo "stat: cannot read file system information for '$a'" >&2; rc=1; fi
  done
  exit $rc
fi
exec /usr/bin/stat "$@"
"""

    def lock(self, sid, age_sec, removable=True):
        path = self.repo.path(".git", "agent_started_%s.lock" % sid)
        os.mkdir(path)
        if not removable:
            with open(os.path.join(path, "held"), "w") as fh:
                fh.write("x\\n")
        when = time.time() - age_sec
        os.utime(path, (when, when))
        return path

    def test_a_stale_lock_on_linux_stat_never_breaks_the_hook(self):
        self.repo.stub_tool("stat", self.GNU_STAT)
        self.lock("s7", 3600)
        began = time.time()
        result = self.hook("s7")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("QUIZ:", result.stdout)
        self.assertLess(time.time() - began, 10)

    def test_a_busy_lock_on_linux_stat_never_breaks_the_hook(self):
        self.repo.stub_tool("stat", self.GNU_STAT)
        self.lock("s8", 0)
        began = time.time()
        result = self.hook("s8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("QUIZ:", result.stdout)
        self.assertLess(time.time() - began, 10)

    def test_a_lock_that_cannot_be_removed_never_hangs_the_hook(self):
        self.lock("s6", 3600, removable=False)
        began = time.time()
        result = self.hook("s6")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("QUIZ:", result.stdout)
        self.assertLess(time.time() - began, 10)

    def test_a_leftover_lock_never_silences_the_hook(self):
        for name in os.listdir(self.repo.path(".git")):
            self.assertFalse(name.startswith("agent_started_"))
        stale = self.repo.path(".git", "agent_started_s9.lock")
        os.mkdir(stale)
        old = time.time() - 3600
        os.utime(stale, (old, old))
        began = time.time()
        out = self.assertOk(self.hook("s9"))
        self.assertIn("QUIZ:", out)
        self.assertLess(time.time() - began, 10)


class TestMarkerCleanup(StartCase):
    """Startup drops stale agent_started_*/agent_compact_* markers so the
    git dir doesn't collect them forever (AGENT_MARKER_DAYS, default 7)."""

    def hook_json(self, sid, source="startup"):
        return json.dumps({"cwd": self.repo.dir, "session_id": sid,
                           "source": source})

    def hook(self, sid, source="startup", env=None):
        env = dict(env or {})
        env.setdefault("AGENT_ROLE", "task-manager")
        return self.start(stdin=self.hook_json(sid, source), env=env)

    def marker(self, name):
        return self.repo.path(".git", name)

    def age(self, path, days):
        when = time.time() - days * 86400
        os.utime(path, (when, when))

    def touch_marker(self, name, days):
        path = self.marker(name)
        with open(path, "w") as fh:
            fh.write("startup 0\n")
        self.age(path, days)
        return path

    def test_an_old_marker_is_removed_at_startup(self):
        old = self.touch_marker("agent_started_old-sid", 8)
        self.assertOk(self.hook("cur-a"))
        self.assertFalse(os.path.exists(old))

    def test_a_one_day_old_marker_survives(self):
        recent = self.touch_marker("agent_started_recent-sid", 1)
        self.assertOk(self.hook("cur-b"))
        self.assertTrue(os.path.exists(recent))

    def test_the_current_sessions_own_marker_survives_even_when_old(self):
        # agent_compact_<sid> for the SID this very run uses is not touched
        # by a startup run, so it stays exactly as old as we leave it; it
        # must still be excluded from deletion by name.
        own = self.touch_marker("agent_compact_cur-c", 8)
        self.assertOk(self.hook("cur-c"))
        self.assertTrue(os.path.exists(own))

    def test_a_compact_run_removes_nothing(self):
        old = self.touch_marker("agent_started_old2-sid", 8)
        self.assertOk(self.hook("cur-d", "compact"))
        self.assertTrue(os.path.exists(old))


SETUP_LINE = ("auto-pipeline: first run, created the task files")   # settings-configure: no agent.conf
POINTER_LINE = ("auto-pipeline: run /auto-pipeline:init once to see the "
                "permission block and the cloud setup line to paste")
NOT_HERE_LINE = ("auto-pipeline: not set up in this repo, "
                 "run /auto-pipeline:init to enable")

MADE_FILES = ["agent_todo.txt", "agent_completed.txt",
              "agent_ideas.txt", "agent_worktree.txt", "AGENTS.md", ".secrets"]


class BareProjectCase(ScriptCase):
    """A project that has never been set up.

    Scope matters. A user-scope install puts this plugin in every repo the
    owner opens, and those repos must stay untouched. Only a repo that turns
    the plugin on itself, in its own .claude/settings.json or
    .claude/settings.local.json, gets set up without being asked.
    """

    script = "agent-start.sh"

    def setUp(self):
        if not os.path.exists(os.path.join(
                os.path.dirname(HERE), "bin", "agent-start.sh")):
            self.fail("bin/agent-start.sh does not exist yet. Write it.")
        self.repo = ScriptRepo(init_project=False)
        self.addCleanup(self.repo.cleanup)
        open(self.repo.orca_log, "w").close()
        self.repo.set_panes([])
        self.repo.git_init(self.repo.dir)

    def start(self, *args, **kwargs):
        kwargs.setdefault("env", {})
        # Keep the hook honest but quiet: a spawned role never auto-resumes,
        # so no background monitor is left behind by a setup test.
        kwargs["env"].setdefault("AGENT_ROLE", "task-manager")
        return self.repo.run("agent-start.sh", *args, **kwargs)

    def names(self):
        return sorted(n for n in os.listdir(self.repo.dir)
                      if n not in (".git", "stubbin", "seed.txt"))


class TestFirstRunInAnEnabledRepo(BareProjectCase):
    def test_it_creates_every_file(self):
        self.repo.enable_plugin()
        self.assertOk(self.start())
        for name in MADE_FILES:
            with self.subTest(name=name):
                self.assertTrue(
                    os.path.exists(os.path.join(self.repo.dir, name)),
                    "%s is missing" % name)

    def test_settings_local_json_counts_too(self):
        self.repo.enable_plugin(local=True)
        self.assertOk(self.start())
        self.assertTrue(os.path.exists(self.repo.path("agent_todo.txt")))
        self.assertFalse(os.path.exists(self.repo.path("agent.conf")))

    def test_it_says_what_it_did(self):
        self.repo.enable_plugin()
        out = self.assertOk(self.start())
        self.assertIn(SETUP_LINE, out)

    def test_it_points_at_the_init_skill_for_the_two_blocks(self):
        self.repo.enable_plugin()
        out = self.assertOk(self.start())
        self.assertIn(POINTER_LINE, out)

    def test_the_two_lines_come_first(self):
        self.repo.enable_plugin()
        out = self.assertOk(self.start())
        self.assertEqual(self.lines(out)[:2], [SETUP_LINE, POINTER_LINE])

    def test_the_normal_output_still_follows(self):
        self.repo.enable_plugin()
        out = self.assertOk(self.start())
        self.assertIn("RESOURCES:", out)
        self.assertIn("agent_todo.txt: 0 lines", out)
        self.assertIn("QUIZ:", out)

    def test_it_still_fits_the_preview(self):
        self.repo.enable_plugin()
        out = pointer_part(self.assertOk(self.start()))
        self.assertLessEqual(len(out.encode()), 2000, out)

    def test_the_second_run_is_quiet(self):
        self.repo.enable_plugin()
        self.assertOk(self.start())
        out = self.assertOk(self.start())
        self.assertNotIn(SETUP_LINE, out)
        self.assertNotIn(POINTER_LINE, out)

    def test_the_second_run_changes_nothing(self):
        self.repo.enable_plugin()
        self.assertOk(self.start())
        before = {n: open(self.repo.path(n)).read()
                  for n in MADE_FILES if os.path.isfile(self.repo.path(n))}
        self.assertOk(self.start())
        after = {n: open(self.repo.path(n)).read()
                 for n in MADE_FILES if os.path.isfile(self.repo.path(n))}
        self.assertEqual(after, before)

    def test_an_existing_task_file_stops_it_firing(self):
        self.repo.enable_plugin()
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("alpha | big | keep\n")
        out = self.assertOk(self.start())
        self.assertNotIn(SETUP_LINE, out)
        self.assertEqual(open(self.repo.path("agent_todo.txt")).read(), "alpha | big | keep\n")

    def test_the_new_conf_is_used_at_once(self):
        """language: a hook's CLAUDE_PLUGIN_OPTION_LANGUAGE counts when Configure has none."""
        self.repo.enable_plugin()
        out = self.assertOk(self.start(
            env={"CLAUDE_PLUGIN_OPTION_LANGUAGE": "zh"}))
        self.assertIn("LANGUAGE: zh", out)


class TestUserScopeLeavesTheRepoAlone(BareProjectCase):
    """The owner opens some other repo. Nothing may appear in it."""

    def test_it_says_the_repo_is_not_set_up(self):
        self.assertIn(NOT_HERE_LINE, self.assertOk(self.start()))

    def test_that_is_the_only_line(self):
        out = self.assertOk(self.start())
        self.assertEqual(self.lines(pointer_part(out).strip()), [NOT_HERE_LINE])

    def test_it_exits_zero(self):
        self.assertEqual(self.start().returncode, 0)

    def test_it_creates_no_file(self):
        self.assertOk(self.start())
        self.assertEqual(self.names(), [])

    def test_it_writes_no_lock(self):
        self.repo.run("agent-start.sh")
        self.assertFalse(os.path.exists(
            os.path.join(self.repo.dir, ".git", "agent_main.lock")))

    def test_it_starts_no_monitor(self):
        self.repo.run("agent-start.sh")
        self.assertFalse(os.path.exists(
            os.path.join(self.repo.dir, ".git", "agent_monitor.pid")))

    def test_it_prints_no_quiz_line(self):
        self.assertNotIn("QUIZ:", self.assertOk(self.start()))

    def test_it_prints_no_resources_line(self):
        self.assertNotIn("RESOURCES:", self.assertOk(self.start()))

    def test_a_settings_file_without_this_plugin_does_not_count(self):
        folder = os.path.join(self.repo.dir, ".claude")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "settings.json"), "w") as fh:
            fh.write('{"enabledPlugins": {"something-else@market": true}}')
        self.assertIn(NOT_HERE_LINE, self.assertOk(self.start()))

    def test_a_task_file_beats_the_scope_check(self):
        """A repo set up by hand keeps working, whatever the scope is (settings-configure:
        agent_todo.txt is the set-up mark, agent.conf is gone)."""
        open(self.repo.path("agent_todo.txt"), "w").close()
        out = self.assertOk(self.start())
        self.assertNotIn(NOT_HERE_LINE, out)
        self.assertIn("QUIZ:", out)

    def test_a_session_id_leaves_no_marker_either(self):
        out = self.assertOk(self.start(
            stdin='{"cwd": "%s", "session_id": "s1", "source": "startup"}'
                  % self.repo.dir))
        self.assertEqual(self.lines(pointer_part(out).strip()), [NOT_HERE_LINE])
        left = [n for n in os.listdir(os.path.join(self.repo.dir, ".git"))
                if n.startswith("agent_started_")]
        self.assertEqual(left, [])

    def test_the_quiz_still_works_with_no_setup(self):
        """--quiz and --answer never touch the project at all."""
        out = self.assertOk(self.repo.run("agent-start.sh", "--quiz"))
        self.assertIn("Q1.", out)
        self.assertEqual(self.names(), [])


class TestAConfWrittenBeforeRuntimeExisted(StartCase):
    def test_the_hook_still_prints_its_normal_output(self):
        self.repo.unset_conf("runtime")
        out = self.assertOk(self.start(env={"AGENT_ROLE": "task-manager"}))
        self.assertIn("RESOURCES:", out)
        self.assertIn("QUIZ:", out)

    def test_it_does_not_try_to_set_the_project_up_again(self):
        self.repo.unset_conf("runtime")
        out = self.assertOk(self.start(env={"AGENT_ROLE": "task-manager"}))
        self.assertNotIn("first run", out)
        self.assertNotIn("not set up in this repo", out)


NAMES = ["DIFF SCAN", "BUILD", "RELATED TESTS", "MODULE TESTS", "GUARD TESTS", "DB CHECK", "DATA CHECK",
         "CORE REVIEW", "PR REVIEW", "EXAMPLES TEST", "FLOW CHECK", "UI CHECK",
         "REAL DATA COUNT"]


ANSWERS = ("1A 2D 3C 4B 5D 6D 7C 8C 9A 10D 11C 12C 13D 14C 15D 16B 17C "
           "18D 19C 20A 21D 22C 23B 24D 25B 26D 27B 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C 38B 39B 40B 41C 42A 43D 44B")


QUIZ_Q6 = """Q6. You are one of four agents. You changed files under api/auth/. Which tests do you run?
  A. The full suite
  B. Tests for all of api/
  C. None; the manager runs them
  D. The tests agent-level.sh lists under RELATED TESTS (they import or name the changed files)"""


QUIZ_Q8 = """Q8. Memory in use plus what a new agent pane needs would pass the Max memory % limit. You need a new sub-agent.
  A. Start it: it is only one
  B. Start it with a smaller model
  C. Start nothing new: close done and idle panes and stop test runs first, never a working agent; still over: tell the main manager
  D. Ask the human"""


QUIZ_Q9 = """Q9. You want to start a test run. Memory in use now plus what this run is known to need would pass the Max memory % limit. You:
  A. Wait: agent-room.sh says no until the sum fits under the limit (a never measured run starts at once under a memory monitor)
  B. Start it anyway: it is only one run
  C. Take a heavy-test slot and start it
  D. Skip your tests"""


QUIZ_Q16 = """Q16. A small logic task (one function, about 30 minutes) needs a new test. Who does it?
  A. A task manager in a new worktree, because it needs a test
  B. One subagent in its own worktree: it writes the example tests, runs its blocks, pushes a branch
  C. The main manager itself
  D. Nobody: skip the test, it is small"""


QUIZ_Q23 = """Q23. One request has x1, x2, x3, x4; x1 and x2 are urgent ("after done direct merge"). You:
  A. Merge all four into your working branch, run the full suite, then publish them together
  B. Read his words as a yes for x1 and x2: they get target production with his words and what you read (--means); x1 and x2 branch from production and each merges straight into production when done (production merged back into your working branch after each); x3 and x4 branch from your working branch and merge there; one full suite there after both are in; first check that x1 and x2 need no code only x3 or x4 brings
  C. Wait until all four are done, then merge them straight into production
  D. Ask him to type a fixed sentence for x1 and x2 first"""


QUIZ_Q25 = """Q25. The owner writes: "fix the export total and publish it". Two other tasks of a batch run for your working branch (ap-main-<name>). Where does this task merge?
  A. Into your working branch, and it waits for the batch
  B. Straight into the production branch once its own checks pass (merged in a short-lived worktree of production), the deploy follows by itself, then production is merged back into your working branch at once
  C. Into the main checkout after switching it to the production branch
  D. Nowhere until the nightly run is green"""


QUIZ_Q35 = """Q35. Before a release the full suite runs once on the working branch, and two tests fail. The tasks that caused them are merged and their builders are idle. You:
  A. Send each failure back to the agent that built it
  B. Give the failures to a new fixer agent (a fast-lane deputy or a task manager, by size); the release waits until that run is green
  C. Release now and fix the tests later
  D. Mark the two tests skipped and release"""


QUIZ_Q38 = """Q38. A diff only changes one locale value. agent-level.sh check prints BLOCKS: PR REVIEW, DIFF SCAN, RELATED TESTS, GUARD TESTS. What runs?
  A. The full suite once
  B. Those blocks: an agent that did not build it reviews the diff against the approved requirement, the light tests run, nothing else
  C. Lint, type-check, a UI CHECK and the heavy tests as well
  D. Nothing: it is only text"""


QUIZ_Q39 = """Q39. Production is broken and the owner wants it fixed now. You:
  A. Fix it on the working branch and wait for the next promote
  B. Branch from the production branch, make the smallest fix, PR review and the light related tests, merge to production with his words from dispatch that you read as the publish (stored with --means; no second yes; the release build runs by itself), then merge production back into the working branch
  C. Push a fix straight to production with no check
  D. Wait for the nightly run"""


# approval-design (requirements/check-blocks.md section 53 D, owner 2026-11-26): the agent reads his words
QUIZ_Q7 = """Q7. A verified relayed owner order (its check line says verified) says "merge to main". The sender meets the decider floor. The task touches production.
  A. Ask the owner again
  B. Ask the sender to confirm
  C. Merge: you read his verified words as his yes for that merge; store them with what you read (--means), no second yes
  D. Refuse: production needs a fixed sentence"""


QUIZ_Q40 = """Q40. The owner gave tasks 1 to 4, then writes "2. need to publish direct after done. others wait for me review". You:
  A. Ask him to type a fixed sentence for task 2
  B. Task 2 gets target production with his words and what you read (--means "publish task 2 to production"); tasks 1, 3 and 4 go to the working branch and wait for his review
  C. Publish all four straight after done
  D. Hold all four until he reviews them, then ask about task 2 again"""


QUIZ_Q41 = """Q41. Open tasks: the invoice export, the login page, the stock report. The owner writes "the login one can go live right after it is done". You:
  A. Ask him which task he means
  B. Ask him for the task id
  C. Only the login page task fits: target production with his words and what you read (--means); no question
  D. Wait until he names the task exactly"""


QUIZ_Q42 = """Q42. Two open tasks: "fix the sales report total" and "fix the sales report export". The owner writes "publish the sales report fix after done". You:
  A. Check first (the todo lines, the requirement docs, what he said before); still unsure: one question that names both tasks, then decide
  B. Pick the first one
  C. Publish both
  D. Ask him three questions to be sure"""


QUIZ_Q43 = """Q43. About a finished task the owner writes "publish it next week". You:
  A. Publish it now: he said publish
  B. Store it as his yes and publish at once
  C. Ask him to type a fixed sentence
  D. Not a yes now (a later time): the task stays on the working branch; nothing is published by itself"""


QUIZ_Q44 = """Q44. You doubt whether two tasks touch the same code. A quick check (read the files, a trial merge) can settle it. You:
  A. Queue the second task until the first is merged
  B. Check, then decide: no queue and no question
  C. Ask the owner
  D. Run both and hope"""


LEVEL_WORDS = re.compile(r"(?i)(\brisk types?\b|(?-i:\btype [A-D]\b)|\b[A-D] = (?:text|ui|logic|danger)\b|--level\b|"
                         r"\btodo level\b|--declared\b|\bRAISE\b|REQUIRED TYPE|\blevel [0-4]\b|\(R8 check)")


class TestQuiz(ScriptCase):
    script = "agent-start.sh"

    def quiz(self):
        return self.assertOk(self.repo.run("agent-start.sh", "--quiz"))

    def question(self, out, n):
        i = out.index("Q%d. " % n)
        return "\n".join(out[i:].splitlines()[:5])

    def test_the_changed_questions(self):
        out = self.quiz()
        for n, text in ((6, QUIZ_Q6), (7, QUIZ_Q7), (8, QUIZ_Q8), (9, QUIZ_Q9), (16, QUIZ_Q16), (23, QUIZ_Q23), (25, QUIZ_Q25), (35, QUIZ_Q35), (38, QUIZ_Q38), (39, QUIZ_Q39),
                        (40, QUIZ_Q40), (41, QUIZ_Q41), (42, QUIZ_Q42), (43, QUIZ_Q43), (44, QUIZ_Q44)):
            with self.subTest(q=n):
                self.assertEqual(self.question(out, n), text)

    def test_no_level_words_in_the_quiz(self):
        self.assertEqual(LEVEL_WORDS.findall(self.quiz()), [])

    def test_44_and_the_new_key_passes(self):
        out = self.quiz()
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", out)), 44)
        r = self.repo.run("agent-start.sh", "--answer", ANSWERS)
        self.assertIn("QUIZ RESULT: 44/44 PASS", r.stdout)

    def test_the_approval_questions_name_their_rule(self):
        # approval-design (section 53 D): the cases live in R8, the quick check in P1
        for good, code in (("40B", "R8"), ("41C", "R8"), ("42A", "R8"), ("43D", "R8"), ("44B", "P1")):
            for letter in "ABCD":
                wrong = good[:-1] + letter
                if wrong == good:
                    continue
                with self.subTest(wrong=wrong):
                    r = self.repo.run("agent-start.sh", "--answer", ANSWERS.replace(good, wrong))
                    self.assertEqual(r.returncode, 1)
                    self.assertIn("Q%s(%s)" % (good[:-1], code), r.stdout)

    def test_no_fixed_sentence_is_the_right_answer(self):
        out = self.quiz()
        self.assertNotIn("yes, publish", out)
        self.assertNotIn("yes, skip", out)
        self.assertIn("--means", self.question(out, 23))

    def test_a_wrong_block_answer_names_r8(self):
        for wrong in ("38A", "38C", "39A", "39D"):
            with self.subTest(wrong=wrong):
                good = "38B" if wrong.startswith("38") else "39B"
                r = self.repo.run("agent-start.sh", "--answer", ANSWERS.replace(good, wrong))
                self.assertEqual(r.returncode, 1)
                self.assertIn("Q%s(R8)" % wrong[:2], r.stdout)

    def test_every_block_named_in_the_quiz_is_in_the_table(self):
        found = set(re.findall(r"\b([A-Z]{2,}(?: [A-Z]{2,})+)\b", self.quiz()))
        extra = {"GATE REFUSED", "CLOSE CASE", "DONE PASS", "DONE FAIL"}
        self.assertEqual(sorted(n for n in found if n not in NAMES and n not in extra), [])


HEADING = "## E. Output"


RULES_PREFIX = "RULES: read "


MEASURED_LIMIT = 10000


POINTER_CAP = 2000


WHOLE_CAP = 5000


FIXTURE = """# PRINCIPLES

- TOP-MARK the top lines

## D. Auto setup

D-MARK a rule

## E. Output

E-MARK-1 first rule
- E-MARK-2 second rule


## Notice

NOTICE-MARK the license
"""


FIXTURE_BLOCK = HEADING + "\n\nE-MARK-1 first rule\n- E-MARK-2 second rule\n"


FIXTURE_E_LAST = """# PRINCIPLES

## D. Auto setup

D-MARK a rule

## E. Output

E-MARK-1 first rule
- E-MARK-2 last rule in the file
"""


class OutputCase(ScriptCase):
    script = "agent-start.sh"

    def setUp(self):
        super().setUp()
        self.write_principles(FIXTURE)

    def write_principles(self, text):
        with open(self.repo.plugin_path("PRINCIPLES.md"), "w") as fh:
            fh.write(text)

    def start(self, stdin=None, role="task-manager"):
        env = {"AGENT_ROLE": role} if role else {}
        return self.assertOk(self.repo.run("agent-start.sh", stdin=stdin, env=env))

    def hook(self, source, sid="s-out"):
        return self.start(stdin=json.dumps(
            {"cwd": self.repo.dir, "session_id": sid, "source": source}))

    def assert_block_before_rules(self, out):
        lines = out.splitlines()
        rules = [i for i, l in enumerate(lines) if l.startswith(RULES_PREFIX)]
        self.assertTrue(rules, out)
        before = "\n".join(lines[:rules[0]]) + "\n"
        self.assertTrue(before.endswith("\n" + FIXTURE_BLOCK) or before == FIXTURE_BLOCK,
                        "the section is not right before the RULES line:\n" + out)

    def assert_no_block(self, out):
        self.assertNotIn(HEADING, out)
        self.assertNotIn("E-MARK", out)


class TestAnInitializedRepo(OutputCase):
    def test_the_section_comes_right_before_the_rules_line(self):
        self.assert_block_before_rules(self.start())

    def test_rules_and_quiz_stay_the_last_two_lines(self):
        lines = self.lines(self.start())
        self.assertTrue(lines[-2].startswith(RULES_PREFIX), lines[-2])
        self.assertTrue(lines[-1].startswith("QUIZ: "), lines[-1])

    def test_nothing_else_of_principles(self):
        out = self.start()
        for mark in ("TOP-MARK", "D-MARK", "NOTICE-MARK", "## D.", "## Notice"):
            with self.subTest(mark=mark):
                self.assertNotIn(mark, out)

    def test_printed_once(self):
        self.assertEqual(self.start().count(HEADING), 1)

    def test_a_main_manager_gets_it_too(self):
        self.assert_block_before_rules(self.start(role=None))

    def test_the_last_section_of_the_file_is_printed_to_the_end(self):
        self.write_principles(FIXTURE_E_LAST)
        out = self.start()
        self.assertIn("- E-MARK-2 last rule in the file\n" + RULES_PREFIX, out)
        self.assertNotIn("D-MARK", out)


class TestCompactAndClear(OutputCase):
    def test_compact_prints_it(self):
        self.assert_block_before_rules(self.hook("compact"))

    def test_clear_prints_it(self):
        self.assert_block_before_rules(self.hook("clear"))

    def test_compact_has_no_quiz_still(self):
        self.assertNotIn("QUIZ:", self.hook("compact"))


class TestNoSection(OutputCase):
    def test_principles_without_section_e_prints_nothing_extra(self):
        self.write_principles("# PRINCIPLES\n\n## D. Auto setup\n\nD-MARK\n")
        out = self.start()
        self.assert_no_block(out)
        lines = self.lines(out)
        self.assertTrue(lines[-2].startswith(RULES_PREFIX))
        self.assertTrue(lines[-1].startswith("QUIZ: "))


class TestARepoNotSetUp(unittest.TestCase):
    """User-scope install, a repo that never turned the plugin on: the hint
    line, then the section. Still nothing written."""

    def setUp(self):
        self.repo = ScriptRepo(init_project=False)
        self.addCleanup(self.repo.cleanup)
        open(self.repo.orca_log, "w").close()
        self.repo.set_panes([])
        self.repo.git_init(self.repo.dir)
        with open(self.repo.plugin_path("PRINCIPLES.md"), "w") as fh:
            fh.write(FIXTURE)

    def start(self, stdin=None):
        result = self.repo.run("agent-start.sh", stdin=stdin,
                               env={"AGENT_ROLE": "task-manager"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def names(self):
        return sorted(n for n in os.listdir(self.repo.dir)
                      if n not in (".git", "stubbin", "seed.txt"))

    def test_hint_then_section(self):
        self.assertEqual(self.start(), NOT_HERE_LINE + "\n" + FIXTURE_BLOCK)

    def test_with_a_session_id_too(self):
        out = self.start(stdin=json.dumps(
            {"cwd": self.repo.dir, "session_id": "s1", "source": "startup"}))
        self.assertEqual(out, NOT_HERE_LINE + "\n" + FIXTURE_BLOCK)
        left = [n for n in os.listdir(os.path.join(self.repo.dir, ".git"))
                if n.startswith("agent_started_")]
        self.assertEqual(left, [])

    def test_nothing_is_written(self):
        self.start()
        self.assertEqual(self.names(), [])

    def test_the_real_section_fits(self):
        os.remove(self.repo.plugin_path("PRINCIPLES.md"))
        import shutil
        shutil.copy2(os.path.join(ROOT, "PRINCIPLES.md"),
                     self.repo.plugin_path("PRINCIPLES.md"))
        out = self.start()
        self.assertTrue(out.startswith(NOT_HERE_LINE + "\n"), out[:300])
        self.assertLessEqual(len(out.encode()), WHOLE_CAP)


class TestTheRealSizeOnABusyProject(ScriptCase):
    """The real PRINCIPLES.md (whatever section E holds today) on a busy
    project: the pointer part keeps its 2000 bytes, the whole stays at or
    under 5000, under the measured 10,000-byte limit."""

    script = "agent-start.sh"

    def setUp(self):
        super().setUp()
        long_line = "x" * 400
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            for i in range(4):
                fh.write("/very/long/path/to/worktree/number_%d | module_%d | "
                         "working | since 2026-09-22 10:00\n" % (i, i))
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            for i in range(60):
                fh.write("%02d %s\n" % (i, long_line))

    def check(self, out):
        size = len(out.encode())
        self.assertLessEqual(len(pointer_part(out).encode()), POINTER_CAP)
        self.assertLessEqual(size, WHOLE_CAP, "hook is %d bytes" % size)
        self.assertLess(size, MEASURED_LIMIT)

    def test_normal_start(self):
        self.check(self.assertOk(self.repo.run("agent-start.sh")))

    def test_compact(self):
        self.check(self.assertOk(self.repo.run(
            "agent-start.sh",
            stdin=json.dumps({"cwd": self.repo.dir, "session_id": "s2",
                              "source": "compact"}))))


NOBODY = "999999"   # a CLAUDE_PID no lock names and no process has


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
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


class TestTheTexts(SeatCase):
    def test_whole_repo_close_case_ends_with_the_release(self):
        text = read("skills", "close-case", "SKILL.md")
        part_b = text[text.index("## B."):]
        self.assertIn("agent-close-case.sh --release-line", part_b)
        self.assertGreater(part_b.index("--release"), part_b.index("final table"),
                           "release is named after the final table, as the other choice")

    def test_the_close_case_script_gives_the_release_line(self):
        result = self.repo.run("agent-close-case.sh", "--release-line", env={"CLAUDE_PID": NOBODY})
        self.assertOk(result)
        self.assertIn("--release", result.stdout)

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
        result = self.repo.run("agent-close-case.sh", "--release-line", env={"CLAUDE_PID": str(os.getpid())})
        self.assertOk(result)
        self.assertEqual(result.stdout.splitlines(), [self.release_line()])
        text = read("skills", "close-case", "SKILL.md")
        self.assertIn("never run it yourself", text)

    def test_the_skill_never_runs_it(self):
        part_b = read("skills", "close-case", "SKILL.md").split("## B.", 1)[1]
        rows = [line for line in part_b.splitlines() if "--release" in line]
        self.assertEqual(len(rows), 1, "one line, the other choice (tests/test_agent_start.py)")
        self.assertIn("never run it yourself", rows[0])
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-start.sh --release", part_b)

    def test_the_principles_say_the_human_types_it(self):
        text = read("PRINCIPLES.md")
        w10 = text[text.index("W10."):text.index("W11.")]
        w13 = text[text.index("W13."):text.index("## C.")]
        self.assertIn("`! agent-start.sh --take-over`", w10)
        self.assertIn("`! agent-start.sh --release`", w13)
        for rule in (w10, w13):
            self.assertIn("never runs it", rule)


ARCHIVE_RE = re.compile(r"^agent_state\.\d{4}-\d\d-\d\d-\d{6}\.txt$")


CLEAR_LINE = 'orca terminal send --terminal %s --text "/clear" --enter'


class CleanCase(SeatCase):
    """A main manager that holds the lock by a lock line, with nothing else running."""

    OLD = "OLD STATE of the closed case\ndecision: ship it\nhandle term_task-9\n"

    def main(self, term="term_main-1", sid="sid-before"):
        me = self.live()
        self.set_lock("%d 2026-10-01 09:00 %s %s\n" % (me, sid, term or "-"))
        return me

    def clean(self, *carry, pid, kind="orca", env=None):
        full = {}
        if kind:
            full["AGENT_RUNTIME"] = kind
        full.update(env or {})
        return self.start("--clean", *carry, pid=pid, env=full)

    @property
    def state_path(self):
        return self.repo.path("agent_state.txt")

    def write_state(self, text=None):
        with open(self.state_path, "w") as fh:
            fh.write(self.OLD if text is None else text)

    def state_lines(self):
        with open(self.state_path) as fh:
            return [line.rstrip("\n") for line in fh if line.strip()]

    def archives(self):
        names = [os.path.basename(p) for p in glob.glob(self.repo.path("agent_state.*.txt"))]
        return sorted(names)

    def lock_text(self):
        with open(self.lock_path) as fh:
            return fh.read()

    def write_todo(self, *rows):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("".join(row + "\n" for row in rows))

    def next_lines(self, out):
        return [line for line in out.splitlines() if line.startswith("NEXT")]


class TestOnlyTheMainManager(CleanCase):
    def assertRefused(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout + result.stderr)
        self.assertEqual(self.archives(), [])
        with open(self.state_path) as fh:
            self.assertEqual(fh.read(), self.OLD)

    def test_a_second_session_is_refused(self):
        main = self.main()
        self.write_state()
        before = self.lock_text()
        result = self.clean(pid=5151)
        self.assertRefused(result)
        self.assertIn(str(main), result.stdout + result.stderr)
        self.assertEqual(self.lock_text(), before)

    def test_a_spawned_agent_is_refused(self):
        me = self.main()
        self.write_state()
        self.assertRefused(self.clean(pid=me, env={"AGENT_ROLE": "task-manager"}))

    def test_no_lock_is_refused_and_no_lock_is_written(self):
        self.write_state()
        self.assertRefused(self.clean(pid=5151))
        self.assertIsNone(self.lock_words())

    def test_a_released_session_is_refused(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.start("--release", pid=me))
        self.assertRefused(self.clean(pid=me))
        self.assertIsNone(self.lock_words())


class TestLeftRunning(CleanCase):
    def assertStopped(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("LEFT RUNNING:", result.stdout)
        refused = [l for l in result.stdout.splitlines() if l.startswith("REFUSED")]
        self.assertEqual(len(refused), 1, result.stdout)
        self.assertIn("Nothing changed", refused[0])
        self.assertEqual(self.next_lines(result.stdout), [])
        self.assertEqual(self.archives(), [])
        with open(self.state_path) as fh:
            self.assertEqual(fh.read(), self.OLD)

    def test_a_live_worktree_line_stops_it(self):
        me = self.main()
        self.write_state()
        self.repo.set_worktree_lines([("/tmp/wt/alpha", "alpha", "working")])
        result = self.clean(pid=me)
        self.assertStopped(result)
        left = [l for l in result.stdout.splitlines() if l.startswith("LEFT RUNNING:")]
        self.assertEqual(len(left), 1, result.stdout)
        self.assertIn("/tmp/wt/alpha", left[0])
        self.assertIn("alpha", left[0])
        self.assertIn("agent-file.sh worktree rm", left[0])

    def test_every_left_thing_gets_its_own_line(self):
        me = self.main()
        self.write_state()
        self.repo.set_worktree_lines([("/tmp/wt/alpha", "alpha", "working"),
                                      ("/tmp/wt/beta", "beta", "idle")])
        result = self.clean(pid=me)
        self.assertStopped(result)
        left = [l for l in result.stdout.splitlines() if l.startswith("LEFT RUNNING:")]
        self.assertEqual(len(left), 2, result.stdout)

    def test_after_the_stop_the_same_command_goes_through(self):
        me = self.main()
        self.write_state()
        self.repo.set_worktree_lines([("/tmp/wt/alpha", "alpha", "working")])
        self.assertStopped(self.clean(pid=me))
        self.repo.set_worktree_lines([])
        self.assertOk(self.clean(pid=me))
        self.assertEqual(len(self.archives()), 1)

    def test_crons_are_named_because_a_script_cannot_see_them(self):
        me = self.main()
        self.write_state()
        out = self.assertOk(self.clean(pid=me))
        check = [l for l in out.splitlines() if l.startswith("CHECK")]
        self.assertEqual(len(check), 1, out)
        self.assertIn("CronList", check[0])


class TestTheArchive(CleanCase):
    def test_the_old_state_moves_next_to_it_same_bytes(self):
        me = self.main()
        self.write_state()
        out = self.assertOk(self.clean(pid=me))
        names = self.archives()
        self.assertEqual(len(names), 1, names)
        self.assertRegex(names[0], ARCHIVE_RE)
        with open(self.repo.path(names[0])) as fh:
            self.assertEqual(fh.read(), self.OLD)
        self.assertIn(names[0], out)

    def test_the_archive_is_git_ignored_and_no_tracked_file_changes(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        name = self.archives()[0]
        ignored = subprocess.run(["git", "-C", self.repo.dir, "check-ignore", "-q", name])
        self.assertEqual(ignored.returncode, 0, "%s is not ignored" % name)
        self.assertFalse(os.path.exists(self.repo.path(".gitignore")))
        status = subprocess.run(["git", "-C", self.repo.dir, "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        self.assertNotIn("agent_state.2", status)

    def test_the_exclude_line_is_added_once(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        self.assertOk(self.clean(pid=me))
        with open(self.repo.path(".git", "info", "exclude")) as fh:
            rows = [line.strip() for line in fh]
        self.assertEqual(rows.count("agent_state.*.txt"), 1, rows)

    def test_the_newest_five_stay(self):
        me = self.main()
        self.write_state()
        old = ["agent_state.2026-09-0%d-100000.txt" % day for day in range(1, 7)]
        for name in old:
            with open(self.repo.path(name), "w") as fh:
                fh.write(name + "\n")
        self.assertOk(self.clean(pid=me))
        names = self.archives()
        self.assertEqual(len(names), 5, names)
        self.assertEqual(names[:4], old[2:], "the two oldest go, the rest stay")
        with open(self.repo.path(names[4])) as fh:
            self.assertEqual(fh.read(), self.OLD)

    def test_no_state_file_means_no_archive(self):
        me = self.main()
        out = self.assertOk(self.clean(pid=me))
        self.assertEqual(self.archives(), [])
        self.assertIn("PREVIOUS: case closed", "\n".join(self.state_lines()))
        self.assertRegex(self.state_lines()[2], r"^PREVIOUS: case closed \d{4}-\d\d-\d\d, archive none$")
        self.assertEqual(len(self.next_lines(out)), 1)

    def test_a_second_clean_never_overwrites_the_first_archive(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me, env={}))
        first = self.archives()
        self.assertOk(self.clean(pid=me))
        names = self.archives()
        self.assertEqual(len(names), 2, names)
        with open(self.repo.path(first[0])) as fh:
            self.assertEqual(fh.read(), self.OLD)
        other = [n for n in names if n != first[0]][0]
        with open(self.repo.path(other)) as fh:
            self.assertTrue(fh.read().startswith("ROLE: main manager"))


class TestTheFreshState(CleanCase):
    def test_exactly_the_five_lines_and_the_carry(self):
        me = self.main()
        self.write_state()
        self.write_todo("alpha | big | build the alpha thing; next: tests | est 30m",
                        "beta-two | small | fix the beta label | est 10m")
        self.assertOk(self.clean("decide: keep the old logo?",
                                 "owner: answer the pricing question", pid=me))
        lines = self.state_lines()
        self.assertEqual(lines[0], 'ROLE: main manager of "project" (lock: pid %d). '
                                   'Same seat, clean session.' % me)
        self.assertRegex(lines[1], r"^DATE: \d{4}-\d\d-\d\d \d\d:\d\d$")
        archive = self.archives()[0]
        self.assertRegex(lines[2], r"^PREVIOUS: case closed \d{4}-\d\d-\d\d, archive %s$"
                         % re.escape(archive))
        self.assertEqual(lines[2].split()[3].rstrip(","), archive[len("agent_state."):][:10],
                         "the closed date is the day of the archive")
        self.assertEqual(lines[3], "TODO open (2): alpha, beta-two")
        self.assertEqual(lines[4:], ["CARRY: decide: keep the old logo?",
                                     "CARRY: owner: answer the pricing question"])

    def test_nothing_of_the_old_state_stays(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        text = "\n".join(self.state_lines())
        self.assertNotIn("OLD STATE", text)
        self.assertNotIn("term_task-9", text)

    def test_no_todo_and_no_carry(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        lines = self.state_lines()
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual(lines[3], "TODO open (0): none")
        self.assertEqual(lines[4], "CARRY: none")

    def test_a_carry_with_a_newline_stays_one_line(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean("first half\nsecond half", pid=me))
        self.assertEqual(self.state_lines()[4:], ["CARRY: first half second half"])

    def test_the_lock_and_the_closed_list_are_untouched(self):
        me = self.main()
        self.write_state()
        before = self.lock_text()
        self.assertOk(self.clean(pid=me))
        self.assertEqual(self.lock_text(), before)
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_main.closed")))

    def test_it_prints_no_start_output(self):
        me = self.main()
        self.write_state()
        out = self.assertOk(self.clean(pid=me))
        for word in ("QUIZ", "RESOURCES", "auto resume", "RULES:"):
            with self.subTest(word=word):
                self.assertNotIn(word, out)


class TestTheNextLine(CleanCase):
    def one_next(self, out):
        lines = self.next_lines(out)
        self.assertEqual(len(lines), 1, out)
        return lines[0]

    def sends(self):
        return [c for c in self.repo.calls() if c[:2] == ["terminal", "send"]]

    def test_orca_gets_the_exact_line_with_the_handle_of_the_lock(self):
        me = self.main(term="term_main-1")
        self.write_state()
        out = self.assertOk(self.clean(pid=me, kind="orca"))
        line = self.one_next(out)
        self.assertIn(CLEAR_LINE % "term_main-1", line)
        self.assertIn("last action", line)
        self.assertIn("human", out[out.index("NEXT"):], "what to do when it is not cleared")

    def test_the_command_never_types_it_itself(self):
        me = self.main(term="term_main-1")
        self.write_state()
        self.assertOk(self.clean(pid=me, kind="orca"))
        self.assertEqual(self.sends(), [])

    def test_orca_takes_the_handle_of_the_session_when_the_lock_has_none(self):
        me = self.main(term=None)
        self.write_state()
        out = self.assertOk(self.clean(pid=me, kind="orca",
                                       env={"ORCA_TERMINAL_HANDLE": "term_env-4"}))
        self.assertIn(CLEAR_LINE % "term_env-4", self.one_next(out))

    def test_orca_is_found_by_the_runtime_probe(self):
        self.repo.set_conf("runtime", "auto")
        me = self.main(term="term_main-1")
        self.write_state()
        out = self.assertOk(self.clean(pid=me, kind=None))
        self.assertIn(CLEAR_LINE % "term_main-1", self.one_next(out))

    def test_plain_and_cloud_ask_the_human(self):
        for kind in ("plain", "cloud"):
            with self.subTest(kind=kind):
                me = self.main(term="term_main-1")
                self.write_state()
                line = self.one_next(self.assertOk(self.clean(pid=me, kind=kind)))
                self.assertIn("/clear", line)
                self.assertIn("human", line)
                self.assertNotIn("orca terminal send", line)

    def test_no_orca_on_the_machine_asks_the_human(self):
        self.repo.set_conf("runtime", "auto")
        self.repo.no_orca()
        me = self.main(term="term_main-1")
        self.write_state()
        line = self.one_next(self.assertOk(self.clean(pid=me, kind=None)))
        self.assertIn("human", line)
        self.assertNotIn("orca terminal send", line)

    def test_orca_with_no_handle_asks_the_human(self):
        me = self.main(term=None)
        self.write_state()
        line = self.one_next(self.assertOk(self.clean(pid=me, kind="orca")))
        self.assertIn("/clear", line)
        self.assertIn("human", line)
        self.assertNotIn("orca terminal send", line)


class TestAfterTheClear(CleanCase):
    """The start hook on source "clear": the same main manager, the fresh state."""

    def cleared(self, me):
        return self.assertOk(self.start(pid=me, source="clear", sid="sid-after",
                                        env={"ORCA_TERMINAL_HANDLE": "term_main-1"}))

    def test_the_same_pid_holds_the_lock(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean("decide: keep the old logo?", pid=me))
        self.cleared(me)
        words = self.lock_words()
        self.assertEqual(words[0], str(me))
        self.assertEqual(words[3:], ["sid-after", "term_main-1"])
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_main.closed")))

    def test_the_start_text_says_main_manager_and_shows_the_fresh_state(self):
        me = self.main()
        self.write_state()
        self.write_todo("alpha | big | build the alpha thing | est 30m")
        self.assertOk(self.clean("decide: keep the old logo?", pid=me))
        out = self.cleared(me)
        self.assertIn("ROLE: main manager (lock: pid %d)" % me, out)
        self.assertIn("CLEARED.", out)
        self.assertIn("agent_state.txt: 5 lines", out)
        for line in self.state_lines():
            with self.subTest(line=line[:30]):
                self.assertIn("  " + line, out)
        self.assertIn("  CARRY: decide: keep the old logo?", out)
        for never in ("is dead", "human-direct", "Helper", "no longer the main manager",
                      "QUIZ:", "OLD STATE", "(truncated"):
            with self.subTest(never=never):
                self.assertNotIn(never, out)

    def test_no_second_seat_and_no_helper_line(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        self.cleared(me)
        self.assertNotIn("human-direct", self.repo.read("agent_worktree.txt"))

    def test_a_new_session_is_still_the_helper(self):
        """The seat was never given up: nobody has to find the main manager again."""
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        self.cleared(me)
        out = self.assertOk(self.start(pid=NOBODY, source="startup", sid="sid-new"))
        self.assertIn("ROLE: task manager, human-direct", out)
        self.assertIn("Main manager already running: pid %d" % me, out)
        self.assertEqual(self.lock_words()[0], str(me))


class TestTheReleasePathIsThePluginInstalledNow(CleanCase):
    """K4: a session started on 0.14.0 printed a 0.14.0 path while 0.18.0 was installed."""

    def cache(self, *versions, bare=()):
        folder = os.path.join(self.repo.base, "cache", "auto-pipeline", "auto-pipeline")
        os.makedirs(folder)
        for version in versions:
            shutil.copytree(self.repo.plugin, os.path.join(folder, version))
        for name in bare:
            os.makedirs(os.path.join(folder, name))
        return folder

    def release_lines(self, plugin_root):
        self.set_lock("%d 2026-10-01 09:00 sid-me -\n" % os.getpid())
        result = subprocess.run([os.path.join(plugin_root, "bin", "agent-close-case.sh"), "--release-line"],
                                input="", env=self.repo._env({"CLAUDE_PID": str(os.getpid())}),
                                cwd=self.repo.cwd, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return [l for l in result.stdout.splitlines() if "--release" in l]

    def test_an_old_session_prints_the_newest_installed_path(self):
        folder = self.cache("0.14.0", "0.18.0")
        self.assertEqual(self.release_lines(os.path.join(folder, "0.14.0")),
                         ["! %s/0.18.0/bin/agent-start.sh --release" % folder])

    def test_versions_compare_number_by_number(self):
        folder = self.cache("0.9.0", "0.14.0")
        self.assertEqual(self.release_lines(os.path.join(folder, "0.9.0")),
                         ["! %s/0.14.0/bin/agent-start.sh --release" % folder])

    def test_the_newest_prints_itself(self):
        folder = self.cache("0.9.0", "0.14.0", "0.18.0")
        self.assertEqual(self.release_lines(os.path.join(folder, "0.18.0")),
                         ["! %s/0.18.0/bin/agent-start.sh --release" % folder])

    def test_a_folder_without_the_script_or_not_a_version_never_wins(self):
        folder = self.cache("0.14.0", bare=("0.20.0", "zz-backup"))
        self.assertEqual(self.release_lines(os.path.join(folder, "0.14.0")),
                         ["! %s/0.14.0/bin/agent-start.sh --release" % folder])

    def test_a_plugin_outside_a_version_folder_prints_itself(self):
        os.makedirs(os.path.join(self.repo.base, "9.9.9", "bin"))
        with open(os.path.join(self.repo.base, "9.9.9", "bin", "agent-start.sh"), "w") as fh:
            fh.write("#!/bin/sh\n")
        self.assertEqual(self.release_lines(self.repo.plugin),
                         ["! %s/bin/agent-start.sh --release" % self.repo.plugin])


class TestTheScriptHeader(unittest.TestCase):
    def header(self):
        return "\n".join(read("bin", "agent-start.sh").splitlines()[:20])

    def test_the_usage_block_lists_clean(self):
        self.assertIn("--clean", self.header())

    def test_release_is_no_longer_called_the_last_step(self):
        self.assertNotIn("last step", self.header())


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class TestCleanKeepsFivePerKind(CleanCase):
    def test_five_copies_and_five_day_files_stay(self):
        me = self.main()
        self.write_state()
        copies = ["agent_state.2026-09-0%d-100000.txt" % d for d in range(1, 7)]
        days = ["agent_state.trim-2026-09-0%d.txt" % d for d in range(1, 8)]
        for name in copies + days:
            write(self.repo.path(name), name + "\n")
        self.assertOk(self.clean(pid=me))
        left_days = sorted(os.path.basename(p) for p in glob.glob(self.repo.path("agent_state.trim-*.txt")))
        self.assertEqual(left_days, days[2:])
        left_copies = [n for n in self.archives() if not n.startswith("agent_state.trim-")]
        self.assertEqual(len(left_copies), 5, left_copies)
        self.assertEqual(left_copies[:4], copies[2:])

    def test_day_files_alone_are_not_pruned_by_copies(self):
        me = self.main()
        self.write_state()
        days = ["agent_state.trim-2026-09-0%d.txt" % d for d in range(1, 4)]
        for name in days:
            write(self.repo.path(name), name + "\n")
        self.assertOk(self.clean(pid=me))
        left_days = sorted(os.path.basename(p) for p in glob.glob(self.repo.path("agent_state.trim-*.txt")))
        self.assertEqual(left_days, days)

    def test_the_fresh_header_ends_with_a_blank_line(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        with open(self.state_path) as fh:
            self.assertTrue(fh.read().endswith("CARRY: none\n\n"))


class TestStartMovesNothing(unittest.TestCase):
    """Section 33 (owner 2026-11-25): a repo that already uses the plugin: the start creates the working
    branch and never switches the checkout; the line repeats until the main manager has switched."""

    def setUp(self):
        self.repo = ScriptRepo()
        self.addCleanup(self.repo.cleanup)
        subprocess.run(["git", "-C", self.repo.dir, "branch", "-M", "main"], check=True, capture_output=True)
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        import agent_conf
        self.wb = "ap-main-t"   # section 34: the fixture's git user.name is t

    def start(self, **env):
        e = {"CLAUDE_PID": str(os.getpid())}
        e.update(env)
        return self.repo.run("agent-start.sh", stdin='{"cwd": "%s", "source": "startup"}' % self.repo.dir, env=e)

    def head(self):
        return subprocess.run(["git", "-C", self.repo.dir, "rev-parse", "--abbrev-ref", "HEAD"],
                              capture_output=True, text=True).stdout.strip()

    def has_branch(self, b):
        return bool(subprocess.run(["git", "-C", self.repo.dir, "branch", "--list", b],
                                   capture_output=True, text=True).stdout.strip())

    def line(self, out):
        return [l for l in out.splitlines() if l.startswith("WORKING BRANCH:")]

    def test_creates_does_not_switch(self):
        r = self.start()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.has_branch(self.wb))
        self.assertEqual(self.head(), "main", "the start never switches the checkout")
        self.assertEqual(self.line(r.stdout), [
            "WORKING BRANCH: created %s from main; switch the main checkout to %s at a quiet point "
            "(no uncommitted work, no merge running): git switch %s" % (self.wb, self.wb, self.wb)])

    def test_the_line_repeats_until_switched(self):
        self.start()
        r = self.start()
        self.assertEqual(self.line(r.stdout), [
            "WORKING BRANCH: switch the main checkout to %s at a quiet point (no uncommitted work, no merge "
            "running): git switch %s" % (self.wb, self.wb)])
        subprocess.run(["git", "-C", self.repo.dir, "switch", "-q", self.wb], check=True, capture_output=True)
        self.assertEqual(self.line(self.start().stdout), [])

    def test_a_spawned_agent_creates_nothing(self):
        r = self.start(AGENT_ROLE="task-manager")
        self.assertFalse(self.has_branch(self.wb))
        self.assertEqual(self.line(r.stdout), [])


NOW = "2026-11-02 15:00"


def status_file(repo):
    return repo.path(".git", "agent_watch.json")


def write_watch(repo, pid=None, sweep=NOW, interval=5, tasks=None, orphans=()):
    data = {"pid": os.getpid() if pid is None else pid, "started": "2026-11-02 13:00", "sweep": sweep,
            "interval_min": interval, "tasks": tasks or {}, "orphans": list(orphans)}
    with open(status_file(repo), "w") as fh:
        json.dump(data, fh)


class StartResumeCase(ScriptCase):
    script = "agent-start.sh"

    def setUp(self):
        super().setUp()
        self.repo.set_conf("auto_resume", "no")

    def start(self, **env):
        run_env = {"AGENT_RUNTIME": "orca", "CLAUDE_PID": str(os.getpid())}
        run_env.update(env)
        return self.assertOk(self.repo.run("agent-start.sh", env=run_env))

    def resume(self, **env):
        run_env = {"AGENT_RUNTIME": "orca"}
        run_env.update(env)
        return self.assertOk(self.repo.run("agent-resume.sh", env=run_env))

    def watch_lines(self, out):
        return [l for l in self.lines(out) if l.startswith("WATCH: ")]

    def not_running(self, n, names):
        return ("WATCH: not running, %d tasks to watch (%s). Start it now with Bash run_in_background, "
                "timeout 7200000: %s/bin/agent-watch.sh --all" % (n, names, self.repo.plugin))

    def targets(self):
        self.repo.set_worktree_lines([("/nowhere/alpha", "alpha", "working"), ("/nowhere/beta", "beta", "final"),
                                      ("/nowhere/gamma", "gamma", "done")])


class TestStartLine(StartResumeCase):
    def test_f2_no_watch_prints_the_command(self):
        self.targets()
        self.assertEqual(self.watch_lines(self.start()), [self.not_running(2, "alpha, beta")])

    def test_f2_a_todo_on_line_is_a_target_too(self):
        self.targets()
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add", "far", "big", "far task", "60"))
        self.assertOk(self.repo.run("agent-file.sh", "todo", "where", "far", "pc2", "/x/far"))
        self.assertEqual(self.watch_lines(self.start()), [self.not_running(3, "alpha, beta, far")])

    def test_f1_a_live_watch_is_named(self):
        self.targets()
        sweep = now_text(1)
        write_watch(self.repo, sweep=sweep, tasks={"alpha": {}, "beta": {}})
        self.assertEqual(self.watch_lines(self.start()),
                         ["WATCH: running (pid %d), 2 tasks, last sweep %s" % (os.getpid(), sweep[11:16])])

    def test_f2_a_dead_watch_is_not_running(self):
        self.targets()
        write_watch(self.repo, pid=dead_pid(), sweep=now_text(1), tasks={"alpha": {}, "beta": {}})
        self.assertEqual(self.watch_lines(self.start()), [self.not_running(2, "alpha, beta")])

    def test_f2_no_targets_no_line(self):
        self.repo.set_worktree_lines([("/nowhere/gamma", "gamma", "done")])
        self.assertEqual(self.watch_lines(self.start()), [])

    def test_f2_plain_or_cloud_no_line(self):
        self.targets()
        for kind in ("plain", "cloud"):
            with self.subTest(kind=kind):
                self.assertEqual(self.watch_lines(self.start(AGENT_RUNTIME=kind)), [])

    def test_a_spawned_task_manager_gets_no_line(self):
        self.targets()
        self.assertEqual(self.watch_lines(self.start(AGENT_ROLE="task-manager")), [])

    def test_r5_a_takeover_always_gets_the_start_command(self):
        # review fix R5: a watch left by the dead main manager wakes no one; the new one replaces it (B15)
        self.targets()
        write_watch(self.repo, sweep=now_text(1), tasks={"alpha": {}, "beta": {}})
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-11-24 08:00 - -\n" % dead_pid())
        out = self.start()
        self.assertIn("ROLE: main manager. Previous main manager", out)
        lines = self.watch_lines(out)
        self.assertEqual(len(lines), 1, out)
        self.assertTrue(lines[0].startswith("WATCH: running (pid %d) for the previous main manager" % os.getpid()),
                        lines[0])
        self.assertTrue(lines[0].endswith("Start it now with Bash run_in_background, timeout 7200000: "
                                          "%s/bin/agent-watch.sh --all" % self.repo.plugin), lines[0])

    def test_with_auto_resume_still_one_line(self):
        self.repo.set_conf("auto_resume", "yes")
        self.targets()
        self.assertEqual(len(self.watch_lines(self.start())), 1)


class TestResumeLine(StartResumeCase):
    script = "agent-resume.sh"

    def test_f2_no_watch_prints_the_command(self):
        self.targets()
        self.assertEqual(self.watch_lines(self.resume()), [self.not_running(2, "alpha, beta")])

    def test_f1_a_live_watch_is_named(self):
        self.targets()
        sweep = now_text(1)
        write_watch(self.repo, sweep=sweep, tasks={"alpha": {}, "beta": {}})
        self.assertEqual(self.watch_lines(self.resume()),
                         ["WATCH: running (pid %d), 2 tasks, last sweep %s" % (os.getpid(), sweep[11:16])])

    def test_f2_plain_no_line(self):
        self.targets()
        self.assertEqual(self.watch_lines(self.resume(AGENT_RUNTIME="plain")), [])

    def test_f2_no_targets_no_line(self):
        self.assertEqual(self.watch_lines(self.resume()), [])


class TestStartRoleLine(ScriptCase):
    script = "agent-start.sh"

    def test_e3_the_task_manager_role_line_says_report_into_agent_state(self):
        out = self.assertOk(self.repo.run("agent-start.sh", env={"AGENT_ROLE": "task-manager"}))
        role = next(l for l in self.lines(out) if l.startswith("ROLE: "))
        self.assertIn("agent_state.txt", role)
        self.assertIn("watch", role)
        self.assertNotIn("SendMessage", role)


class TestTheQuiz(ScriptCase):
    """W8 changed, and the quiz covers W8: question 32, answer C."""

    script = "agent-start.sh"
    ANSWERS = ("1A 2D 3C 4B 5D 6D 7C 8C 9A 10D 11C 12C 13D 14C 15D 16B 17C "
               "18D 19C 20A 21D 22C 23B 24D 25B 26D 27B 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C 38B 39B 40B 41C 42A 43D 44B")   # check-blocks: Q38 is a blocks question now

    def quiz(self):
        return self.assertOk(self.repo.run("agent-start.sh", "--quiz"))

    def test_question_32_is_the_sweep(self):
        out = self.quiz()
        q = out[out.index("Q32. "):]
        self.assertIn("last open task", q)
        options = [l.strip() for l in q.splitlines()[1:5]]
        self.assertEqual([o[:2] for o in options], ["A.", "B.", "C.", "D."])
        self.assertIn("agent-cleanup.sh", options[2])
        self.assertIn("table", options[2])

    def test_the_quiz_says_34(self):
        out = self.quiz()
        self.assertIn("=== QUIZ — answer all 44 before any work ===", out)
        self.assertIn('--answer "1A 2B 3C ... 44D"', out)

    def test_c_passes(self):
        out = self.assertOk(self.repo.run("agent-start.sh", "--answer",
                                          self.ANSWERS))
        self.assertIn("QUIZ RESULT: 44/44 PASS", out)

    def test_another_letter_fails_and_names_w8(self):
        for wrong in ("32A", "32B", "32D"):
            with self.subTest(wrong=wrong):
                result = self.repo.run("agent-start.sh", "--answer",
                                       self.ANSWERS.replace("32C", wrong))
                self.assertEqual(result.returncode, 1)
                self.assertIn("Q32(W8)", result.stdout)


class TestStartLineRefusesDefault(ScriptCase):
    script = "agent-start.sh"

    def test_default_shows_as_auto(self):
        self.repo.set_conf("permission_mode", "default")
        out = self.assertOk(self.repo.run("agent-start.sh", env={"AGENT_ROLE": "task-manager"}))
        lines = [l for l in out.splitlines() if l.startswith("PERMISSION:")]
        self.assertEqual(lines, ["PERMISSION: bypassPermissions (from default)"])


class TestStartPermissionLine(ScriptCase):
    script = "agent-start.sh"

    def start(self, env=None):
        env = dict(env or {})
        env.setdefault("AGENT_ROLE", "task-manager")
        return self.assertOk(self.repo.run("agent-start.sh", env=env))

    def lines_with(self, out, prefix):
        return [l for l in out.splitlines() if l.startswith(prefix)]

    def test_from_configure(self):
        self.repo.set_conf("permission_mode", "acceptEdits")
        self.assertEqual(self.lines_with(self.start(), "PERMISSION:"),
                         ["PERMISSION: acceptEdits (from Configure)"])

    def test_not_set(self):
        self.assertEqual(self.lines_with(self.start(), "PERMISSION:"),
                         ["PERMISSION: bypassPermissions (from default)"])

    def test_the_main_manager_gets_it_too(self):
        out = self.assertOk(self.repo.run("agent-start.sh"))
        self.assertEqual(len(self.lines_with(out, "PERMISSION:")), 1)

    def test_no_user_conf_line(self):
        self.repo.set_user_conf("permission_mode=yolo\n")
        self.assertEqual(self.lines_with(self.start(), "USER CONF:"), [])

    def test_still_under_the_cap(self):
        from scripthelp import pointer_part
        out = pointer_part(self.start())
        self.assertLessEqual(len(out.encode()), 2000)


class TestModeMatchNotice(ScriptCase):
    """mode-match (2026-11-25): one start line when this session's mode (hook stdin
    "permission_mode") differs from the Permission mode setting; else nothing."""
    script = "agent-start.sh"

    def start(self, mode="auto", lang=None, setting=None, sid="mm-1"):
        if lang:
            self.repo.set_conf("language", lang)
        if setting:
            self.repo.set_conf("permission_mode", setting)
        payload = {"session_id": sid, "source": "startup", "cwd": self.repo.cwd}
        if mode is not None:
            payload["permission_mode"] = mode
        out = self.assertOk(self.repo.run("agent-start.sh", stdin=json.dumps(payload),
                                          env={"AGENT_ROLE": "task-manager"}))
        return [l for l in out.splitlines() if l.startswith("MODE MISMATCH:")]

    def test_differ_en(self):
        lines = self.start("auto", "en")
        self.assertEqual(len(lines), 1, lines)
        line = lines[0]
        for word in ("auto", "bypassPermissions", "approval",
                     "claude --permission-mode bypassPermissions",
                     "/plugin -> auto-pipeline -> Configure", "Permission mode"):
            self.assertIn(word, line)

    def test_differ_zh(self):
        lines = self.start("plan", "zh", setting="acceptEdits")
        self.assertEqual(len(lines), 1, lines)
        line = lines[0]
        for word in ("plan", "acceptEdits", "批准", "claude --permission-mode acceptEdits",
                     "/plugin -> auto-pipeline -> Configure", "Permission mode"):
            self.assertIn(word, line)

    def test_equal_prints_nothing(self):
        self.assertEqual(self.start("bypassPermissions"), [])
        self.assertEqual(self.start("acceptEdits", setting="acceptEdits", sid="mm-2"), [])

    def test_mode_missing_prints_nothing(self):
        self.assertEqual(self.start(None), [])

    def test_setting_unreadable_prints_nothing(self):
        path = os.path.join(self.repo.plugin_bin, "agent-settings.sh")
        with open(path, "w") as fh:
            fh.write("#!/usr/bin/env bash\nexit 1\n")
        os.chmod(path, 0o755)
        self.assertEqual(self.start("auto", sid="mm-3"), [])

    def test_one_principles_line(self):
        w16 = [l for l in read("PRINCIPLES.md").splitlines() if "MODE MISMATCH" in l]
        self.assertEqual(len(w16), 1)
        self.assertLessEqual(len(w16[0]), 200, w16[0])
        self.assertIn("held because permission modes differ", read("PRINCIPLES.md"))


class TestStart(StartCase):
    def test_a_repo_with_task_files_and_no_agent_conf_is_set_up(self):
        out = self.assertOk(self.start())
        self.assertNotIn("not set up", out)
        self.assertIn("LANGUAGE: en", out)
        self.assertFalse(os.path.exists(self.repo.path("agent.conf")))

    def test_language_and_permission_come_from_configure(self):
        self.repo.set_conf("language", "zh")
        self.repo.set_conf("permission_mode", "bypassPermissions")
        out = self.assertOk(self.start())
        self.assertIn("LANGUAGE: zh", out)
        self.assertIn("PERMISSION: bypassPermissions (from Configure)", out)

    def test_an_old_user_file_does_not_decide_the_mode(self):
        self.repo.set_user_conf("permission_mode=bypassPermissions\n")
        out = self.assertOk(self.start())
        perm = [l for l in self.lines(out) if l.startswith("PERMISSION:")]
        self.assertEqual(len(perm), 1, out)
        self.assertNotIn("auto-pipeline.conf", perm[0])

    def test_no_old_settings_lines(self):
        out = self.assertOk(self.start())
        self.assertNotIn("AUTO UPDATE: not set", out)
        self.assertNotIn("USER CONF:", out)
        self.assertNotIn("agent.conf", out)

    def test_a_bad_stored_value_is_said(self):
        self.repo.set_conf("max_usage_percent", 999)
        out = self.assertOk(self.start())
        self.assertTrue([l for l in self.lines(out) if l.startswith("SETTINGS:") and "max_usage_percent=999" in l], out)

    def test_an_old_agent_conf_is_moved_once(self):
        self.repo.set_old_conf("language=zh\nmax_usage_percent=60\n")
        out = self.assertOk(self.start())
        self.assertIn("moved language=zh from", out)
        calls = [c for c in self.repo.claude_calls() if c["args"][:2] == ["plugin", "configure"]]
        self.assertEqual(len(calls), 1, self.repo.claude_calls())
        out2 = self.assertOk(self.start())
        self.assertNotIn("moved language=zh", out2)

    def test_the_moved_values_count_in_the_same_start(self):
        # E2E 2026-11-25: the start that moves an old file already runs on the moved values.
        # The fixture's claude stub only logs, so stand in for Claude Code's own write.
        self.repo.set_old_conf("language=zh\n")
        self.repo.stub_tool("claude", "#!%s\nimport json, os, sys\n"
                            "data = sys.stdin.read()\n"
                            "p = os.path.join(os.environ['CLAUDE_CONFIG_DIR'], 'settings.json')\n"
                            "os.makedirs(os.path.dirname(p), exist_ok=True)\n"
                            "d = json.load(open(p)) if os.path.exists(p) else {}\n"
                            "d.setdefault('pluginConfigs', {}).setdefault(sys.argv[3], {}).setdefault('options', {})"
                            ".update(json.loads(data) if data else {})\n"
                            "json.dump(d, open(p, 'w'))\n" % sys.executable)
        out = self.assertOk(self.start())
        self.assertIn("moved language=zh from", out)
        self.assertIn("LANGUAGE: zh", out)

    def test_a_stale_scope_of_this_folder_is_updated(self):
        here = os.path.realpath(self.repo.dir)
        self.installed([{"scope": "user", "version": "0.44.0"},
                        {"scope": "project", "projectPath": here, "version": "0.43.0"}])
        out = self.assertOk(self.start())
        self.assertIn("updated project %s: 0.43.0 -> 0.44.0, restart to apply" % here, out)
        calls = [c for c in self.repo.claude_calls() if c["args"][:2] == ["plugin", "update"]]
        self.assertEqual(len(calls), 1)
        self.assertNotIn("OLD PLUGIN:", out)

    def test_the_quiz_never_names_an_old_settings_file(self):
        out = self.assertOk(self.start("--quiz"))
        self.assertNotIn("agent.conf", out)
        self.assertNotIn("auto-pipeline.conf", out)

    def test_take_over_in_a_set_up_repo_is_not_refused_as_not_set_up(self):
        r = self.start("--release")
        self.assertNotIn("not set up", r.stdout + r.stderr)


_EMPTY_CFG = tempfile.mkdtemp(prefix="decider_floor_cfg_")


def you(args=(), env=None, settings=None, conf=None, role="task_manager"):
    """CONF: Configure options for the role keys (settings-configure), written into a
    throwaway Claude config dir; nothing set -> the setting defaults."""
    cfg = tempfile.mkdtemp(dir=_EMPTY_CFG)
    if conf:
        options = {}
        for key, value in conf.items():
            options["helper_model" if key in ("worker", "fast_lane_deputy", "merge_deputy") else key] = value
        with open(os.path.join(cfg, "settings.json"), "w") as fh:
            json.dump({"pluginConfigs": {"auto-pipeline@auto-pipeline": {"options": options}}}, fh)
    full = dict(env or {})
    full["CLAUDE_CONFIG_DIR"] = cfg
    return agent_conf.you_line(list(args), full, settings, {}, role)


MODEL_SETTINGS = {"claude-opus-5": {"effortLevel": "high"},
                  "claude-opus-5-5": {"effortLevel": "xhigh"},
                  "claude-sonnet-5-5": {"effortLevel": "medium"},
                  "claude-sonnet-5": {"effortLevel": "low"}}


class FakeClaude:
    """A live process whose argv carries the given flags, for CLAUDE_PID."""

    def __init__(self, *flags):
        self.proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"] + list(flags))

    def stop(self):
        self.proc.kill()
        self.proc.wait()


class TestConfigureRefuse(ScriptCase):
    """settings-configure: a manager model below the floor stored in Configure is refused,
    the default is used, and the start text says so (one SETTINGS: line)."""
    script = "agent-start.sh"

    def test_below_the_floor_falls_back_and_is_said(self):
        self.repo.set_conf("task_manager", "sonnet-5:high")
        env = {"CLAUDE_CONFIG_DIR": self.repo.claude_dir()}
        self.assertEqual(agent_conf.get("task_manager", env), "opus-5.5:high")
        out = self.assertOk(self.repo.run("agent-start.sh", env={"AGENT_ROLE": "task-manager"}))
        lines = [l for l in out.splitlines() if l.startswith("SETTINGS:") and "task_manager" in l]
        self.assertEqual(len(lines), 1, out)

    def test_at_the_floor_is_kept(self):
        self.repo.set_conf("task_manager", "fable-5.1:medium")
        self.repo.set_conf("worker", "sonnet-5:low")
        env = {"CLAUDE_CONFIG_DIR": self.repo.claude_dir()}
        self.assertEqual(agent_conf.get("task_manager", env), "fable-5.1:medium")
        self.assertEqual(agent_conf.get("worker", env), "sonnet-5:low")


class TestYouLine(unittest.TestCase):
    def test_flags(self):
        self.assertEqual(you(["claude", "--name", "x Task Manager", "--model", "opus", "--effort", "xhigh",
                              "--permission-mode", "bypassPermissions"]),
                         "YOU: opus xhigh (model: flag, effort: flag)")

    def test_equals_form(self):
        self.assertEqual(you(["claude", "--model=sonnet", "--effort=low"]),
                         "YOU: sonnet low (model: flag, effort: flag)")

    def test_env(self):
        self.assertEqual(you(["claude"], {"ANTHROPIC_MODEL": "claude-opus-5-5", "CLAUDE_CODE_EFFORT_LEVEL": "high"}),
                         "YOU: claude-opus-5-5 high (model: env, effort: env)")

    def test_flag_beats_env_and_settings(self):
        self.assertEqual(you(["claude", "--model", "fable", "--effort", "max"],
                             {"ANTHROPIC_MODEL": "opus", "CLAUDE_CODE_EFFORT_LEVEL": "low"},
                             {"model": "sonnet", "effortLevel": "low"}),
                         "YOU: fable max (model: flag, effort: flag)")

    def test_env_beats_settings(self):
        self.assertEqual(you(["claude"], {"ANTHROPIC_MODEL": "opus"}, {"model": "sonnet", "effortLevel": "high"}),
                         "YOU: opus high (model: env, effort: settings.json)")

    def test_settings_alias_takes_the_newest_family_entry(self):
        self.assertEqual(you(["claude", "--dangerously-skip-permissions"], {},
                             {"model": "opus", "modelSettings": MODEL_SETTINGS}),
                         "YOU: opus xhigh (model: settings.json, effort: settings.json)")
        self.assertEqual(you(["claude"], {}, {"model": "sonnet[1m]", "modelSettings": MODEL_SETTINGS}),
                         "YOU: sonnet[1m] medium (model: settings.json, effort: settings.json)")

    def test_settings_exact_entry(self):
        self.assertEqual(you(["claude", "--model", "claude-opus-5"], {}, {"modelSettings": MODEL_SETTINGS}),
                         "YOU: claude-opus-5 high (model: flag, effort: settings.json)")

    def test_model_entry_beats_the_plain_effort_level(self):
        self.assertEqual(you(["claude"], {}, {"model": "opus", "effortLevel": "low",
                                              "modelSettings": MODEL_SETTINGS}),
                         "YOU: opus xhigh (model: settings.json, effort: settings.json)")

    def test_plain_effort_level(self):
        self.assertEqual(you(["claude"], {}, {"model": "sonnet", "effortLevel": "max"}),
                         "YOU: sonnet max (model: settings.json, effort: settings.json)")

    def test_the_setting_last_and_marked(self):
        conf = {"task_manager": "opus-5.5:xhigh", "main_manager": "fable-5.1:high"}
        self.assertEqual(you(["claude", "--dangerously-skip-permissions"], {}, {}, conf, "main_manager"),
                         "YOU: fable-5.1 high (model: Configure main_manager, effort: Configure main_manager)")
        self.assertEqual(you(["claude", "--effort", "max"], {}, None, conf, "task_manager"),
                         "YOU: opus-5.5 max (model: Configure task_manager, effort: flag)")

    def test_nothing_set_is_the_default_and_marked(self):
        self.assertEqual(you(["claude"]),
                         "YOU: opus-5.5 high (model: default task_manager, effort: default task_manager)")
        self.assertEqual(you(["claude"], {}, None, {"task_manager": "opus"}),
                         "YOU: opus-5.5 high (model: default task_manager, effort: default task_manager)")

    def test_empty_and_junk_count_as_not_set(self):
        self.assertEqual(you(["claude"], {"ANTHROPIC_MODEL": "", "CLAUDE_CODE_EFFORT_LEVEL": ""},
                             ["not", "a", "dict"], {"task_manager": "opus-5.5:xhigh"}),
                         "YOU: opus-5.5 xhigh (model: Configure task_manager, effort: Configure task_manager)")
        self.assertEqual(you(["claude"], {}, {"model": "", "effortLevel": "", "modelSettings": {"x": 1}}),
                         "YOU: opus-5.5 high (model: default task_manager, effort: default task_manager)")
        self.assertEqual(you(["claude"], {}, {"model": "opus", "modelSettings": {"claude-opus-5-5": "xhigh"}}),
                         "YOU: opus high (model: settings.json, effort: default task_manager)")


class TestYouCli(ScriptCase):
    def cli(self, pid, role="task_manager", env=None):
        e = self.repo._env(env)
        return subprocess.run([sys.executable, os.path.join(BIN, "agent_conf.py"), "you", role,
                               str(pid)],
                              capture_output=True, text=True, env=e, timeout=30)

    def fake(self, *flags):
        f = FakeClaude(*flags)
        self.addCleanup(f.stop)
        return f.proc.pid

    def test_flags_of_the_process(self):
        r = self.cli(self.fake("--model", "opus", "--effort", "xhigh"))
        self.assertEqual((r.returncode, r.stdout), (0, "YOU: opus xhigh (model: flag, effort: flag)\n"))

    def test_settings_of_the_home(self):
        home = self.repo.fake_home()
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "settings.json"), "w") as fh:
            fh.write('{"model": "opus", "modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}}')
        r = self.cli(self.fake())
        self.assertEqual(r.stdout, "YOU: opus xhigh (model: settings.json, effort: settings.json)\n")

    def test_claude_config_dir(self):
        cfg = os.path.join(self.repo.base, "cfg")
        os.makedirs(cfg)
        with open(os.path.join(cfg, "settings.json"), "w") as fh:
            fh.write('{"model": "fable", "effortLevel": "high"}')
        self.repo.fake_home()
        r = self.cli(self.fake(), env={"CLAUDE_CONFIG_DIR": cfg})
        self.assertEqual(r.stdout, "YOU: fable high (model: settings.json, effort: settings.json)\n")

    def test_the_setting_and_broken_settings(self):
        home = self.repo.fake_home()
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "settings.json"), "w") as fh:
            fh.write("{broken")
        # a broken settings.json: Configure cannot be read either, so the setting default
        r = self.cli(self.fake(), role="main_manager")
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.stdout, "YOU: opus-5.5 high (model: default main_manager, "
                                   "effort: default main_manager)\n")

    def test_a_dead_pid(self):
        f = FakeClaude()
        pid = f.proc.pid
        f.stop()
        self.repo.fake_home()
        self.repo.set_conf("task_manager", "opus-5.5:high")
        r = self.cli(pid)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "YOU: opus-5.5 high (model: Configure task_manager, "
                                   "effort: Configure task_manager)\n")


class TestStartYou(ScriptCase):
    script = "agent-start.sh"

    def you_lines(self, env):
        out = self.assertOk(self.repo.run("agent-start.sh", env=env))
        return [l for l in out.splitlines() if l.startswith("YOU: ")]

    def fake(self, *flags):
        f = FakeClaude(*flags)
        self.addCleanup(f.stop)
        return str(f.proc.pid)

    def test_spawned_task_manager_with_flags(self):
        self.repo.fake_home()
        lines = self.you_lines({"AGENT_ROLE": "task-manager",
                                "CLAUDE_PID": self.fake("--model", "opus", "--effort", "xhigh")})
        self.assertEqual(lines, ["YOU: opus xhigh (model: flag, effort: flag)"])

    def test_spawned_task_manager_falls_back_to_its_role(self):
        self.repo.fake_home()
        self.repo.set_conf("task_manager", "opus-5.5:xhigh")
        lines = self.you_lines({"AGENT_ROLE": "task-manager", "CLAUDE_PID": self.fake()})
        self.assertEqual(lines, ["YOU: opus-5.5 xhigh (model: Configure task_manager, "
                                 "effort: Configure task_manager)"])

    def test_main_manager_falls_back_to_main_manager(self):
        self.repo.fake_home()
        self.repo.set_conf("main_manager", "fable-5.1:xhigh")
        lines = self.you_lines({"CLAUDE_PID": self.fake("--dangerously-skip-permissions")})
        self.assertEqual(lines, ["YOU: fable-5.1 xhigh (model: Configure main_manager, "
                                 "effort: Configure main_manager)"])

    def test_settings_json_of_the_home(self):
        home = self.repo.fake_home()
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "settings.json"), "w") as fh:
            fh.write('{"model": "opus", "effortLevel": "high"}')
        lines = self.you_lines({"AGENT_ROLE": "task-manager", "CLAUDE_PID": self.fake()})
        self.assertEqual(lines, ["YOU: opus high (model: settings.json, effort: settings.json)"])


class TestQuiz36(ScriptCase):
    def quiz(self):
        return self.assertOk(self.repo.run("agent-start.sh", "--quiz"))

    def question(self, out, n):
        q = out[out.index("Q%d. " % n):]
        lines = q.splitlines()
        options = [l.strip() for l in lines[1:5]]
        self.assertEqual([o[:2] for o in options], ["A.", "B.", "C.", "D."])
        return lines[0], options

    def test_36_questions(self):
        out = self.quiz()
        self.assertIn("=== QUIZ — answer all 44 before any work ===", out)
        self.assertIn('--answer "1A 2B 3C ... 44D"', out)
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", out)), 44)

    def test_q35_is_the_release_run(self):
        # check-blocks 2026-11-25 (owner 1A): Q35 asks who fixes a failing release run (Max agents is gone)
        head, options = self.question(self.quiz(), 35)
        self.assertIn("full suite runs once on the working branch", head)
        self.assertIn("new fixer agent", options[1])

    def test_q36_is_the_floor(self):
        head, options = self.question(self.quiz(), 36)
        self.assertIn("[Sonnet 5 medium]", head)
        self.assertIn("do not act", options[2].lower())
        self.assertIn("human", options[2])

    def test_all_pass(self):
        out = self.assertOk(self.repo.run("agent-start.sh", "--answer", ANSWERS))
        self.assertIn("QUIZ RESULT: 44/44 PASS", out)

    def test_wrong_letters_name_the_rule(self):
        for good, rule_code, wrongs in (("35B", "R8", ("35A", "35C", "35D")),   # the release run (R8), check-blocks section 27
                                        ("36C", "W17", ("36A", "36B", "36D"))):
            for wrong in wrongs:
                with self.subTest(wrong=wrong):
                    r = self.repo.run("agent-start.sh", "--answer", ANSWERS.replace(good, wrong))
                    self.assertEqual(r.returncode, 1)
                    self.assertIn("Q%s(%s)" % (good[:2], rule_code), r.stdout)

    def test_the_old_34_answers_no_longer_pass(self):
        r = self.repo.run("agent-start.sh", "--answer", ANSWERS[:-8])
        self.assertEqual(r.returncode, 1)

    def test_usage_and_readme_say_36(self):
        src = read("bin", "agent-start.sh")
        self.assertIn("print the 44 quiz questions", src)
        self.assertIn('--answer "1A 2D ... 44D"', src)
        self.assertIn("44-question quiz", read("PRINCIPLES.md"))


class TestQuiz34(ScriptCase):
    ANSWERS = ("1A 2D 3C 4B 5D 6D 7C 8C 9A 10D 11C 12C 13D 14C 15D 16B 17C "
               "18D 19C 20A 21D 22C 23B 24D 25B 26D 27B 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C 38B 39B 40B 41C 42A 43D 44B")   # check-blocks: Q38 is a blocks question now

    def quiz(self):
        return self.assertOk(self.repo.run("agent-start.sh", "--quiz"))

    def test_question_34_is_the_launch_mode(self):
        out = self.quiz()
        q = out[out.index("Q34. "):]
        head = q.splitlines()[0]
        self.assertIn("new terminal", head)
        self.assertIn("--permission-mode", head)
        options = [l.strip() for l in q.splitlines()[1:5]]
        self.assertEqual([o[:2] for o in options], ["A.", "B.", "C.", "D."])
        self.assertIn("Permission mode setting", options[1])
        self.assertNotIn("cloud", options[1])

    def test_34_questions(self):
        out = self.quiz()
        self.assertIn("=== QUIZ — answer all 44 before any work ===", out)
        self.assertIn('--answer "1A 2B 3C ... 44D"', out)
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", out)), 44)

    def test_b_passes(self):
        out = self.assertOk(self.repo.run("agent-start.sh", "--answer", self.ANSWERS))
        self.assertIn("QUIZ RESULT: 44/44 PASS", out)

    def test_another_letter_fails_and_names_w10(self):
        for wrong in ("34A", "34C", "34D"):
            with self.subTest(wrong=wrong):
                result = self.repo.run("agent-start.sh", "--answer", self.ANSWERS.replace("34B", wrong))
                self.assertEqual(result.returncode, 1)
                self.assertIn("Q34(W10)", result.stdout)

    def test_the_old_33_answers_no_longer_pass(self):
        result = self.repo.run("agent-start.sh", "--answer", self.ANSWERS.replace(" 34B", ""))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Q34(W10)", result.stdout)

    def test_the_principles_say_34(self):
        text = read("PRINCIPLES.md")
        self.assertIn("44-question quiz", text)
        self.assertNotIn("33-question quiz", text)

    def test_the_usage_lines_say_34(self):
        src = read("bin", "agent-start.sh")
        self.assertIn("print the 44 quiz questions", src)
        self.assertIn('--answer "1A 2D ... 44D"', src)
        self.assertNotIn("33B\"", src)


if __name__ == "__main__":
    unittest.main()
