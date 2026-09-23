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
    agent_monitor.txt: <n> lines          only when the file has something
      <every line, two spaces in front>
    RULES: read <plugin>/PRINCIPLES.md now (S8).
    QUIZ: run <plugin>/bin/agent-start.sh --quiz, then --answer. No work until PASS.

The last two lines are exactly those. No PRINCIPLES.md text and no quiz
question ever appears in the hook output.

    --quiz    prints the 29 questions and nothing else
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

from scripthelp import ScriptCase, ScriptRepo

MONITOR_LINE = ("/tmp/wt | alpha | pane working | commit 2m ago | "
                "activity 0m ago | OK | 2026-09-21 18:00")

RULES_LINE = "RULES: read %s/PRINCIPLES.md now (S8)."
QUIZ_LINE = ("QUIZ: run %s/bin/agent-start.sh --quiz, then --answer. "
             "No work until PASS.")


class StartCase(ScriptCase):
    script = "agent-start.sh"

    def start(self, *args, **kwargs):
        return self.repo.run("agent-start.sh", *args, **kwargs)

    def rules_line(self):
        return RULES_LINE % self.repo.plugin

    def quiz_line(self):
        return QUIZ_LINE % self.repo.plugin


class TestItFitsThePreview(StartCase):
    def test_an_empty_project_stays_under_two_kilobytes(self):
        out = self.assertOk(self.start())
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

    def busy_project(self):
        long_line = "x" * 400
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            for i in range(4):
                fh.write("/very/long/path/to/worktree/number_%d | module_%d | "
                         "working | since 2026-09-22 10:00\n" % (i, i))
        with open(self.repo.path("agent_monitor.txt"), "w") as fh:
            for i in range(4):
                fh.write("/very/long/path/to/worktree/number_%d | module_%d | "
                         "pane working | commit 2m ago | activity 1m ago | OK "
                         "| 2026-09-22 10:00\n" % (i, i))
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            for i in range(60):
                fh.write("%02d %s\n" % (i, long_line))
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("alpha | big | one\n")

    def test_a_busy_project_still_fits(self):
        self.busy_project()
        out = self.assertOk(self.start())
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
        out = self.assertOk(self.start())
        self.assertLessEqual(len(out.encode()), self.CAP,
                             "one long line blew the cap: %d bytes"
                             % len(out.encode()))
        self.assertIn("(truncated, read the file)", out)

    def test_the_compact_path_fits_too(self):
        self.busy_project()
        out = self.assertOk(self.start(
            stdin='{"cwd": "%s", "session_id": "s1", "source": "compact"}'
                  % self.repo.dir))
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
        with open(os.path.join(other, "agent.conf"), "w") as fh:
            fh.write("language=en\n")
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


class TestTheMonitorFile(StartCase):
    def test_it_is_printed_when_it_has_something(self):
        with open(self.repo.path("agent_monitor.txt"), "w") as fh:
            fh.write(MONITOR_LINE + "\n")
        out = self.assertOk(self.start())
        self.assertIn("agent_monitor.txt: 1 lines", out)
        self.assertIn("  " + MONITOR_LINE, out)

    def test_nothing_when_it_is_missing(self):
        out = self.assertOk(self.start())
        self.assertNotIn("agent_monitor.txt:", out)


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
    ANSWERS = ("1A 2D 3C 4B 5D 6D 7A 8C 9A 10D 11A 12C 13D 14C 15B 16C 17C "
               "18D 19B 20A 21D 22C 23B 24D 25A 26D 27A 28B 29B")

    def test_all_right_is_a_pass(self):
        out = self.assertOk(self.start("--answer", self.ANSWERS))
        self.assertIn("29/29 PASS", out)

    def test_one_wrong_is_a_fail(self):
        result = self.start("--answer", self.ANSWERS.replace("1A", "1B"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL", result.stdout)


class TestAutoResume(StartCase):
    """The hook runs agent-resume.sh by itself for a main manager, new or
    taken over, on a real startup, when auto_resume=yes (default)."""

    def test_main_manager_startup_prints_it_and_stays_under_cap(self):
        out = self.assertOk(self.start())
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
            outs = [p.communicate(self.hook_json(sid), timeout=60) for p in procs]
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


SETUP_LINE = ("auto-pipeline: first run, created agent.conf and the task files")
POINTER_LINE = ("auto-pipeline: run /auto-pipeline:init once to see the "
                "permission block and the cloud setup line to paste")
NOT_HERE_LINE = ("auto-pipeline: not set up in this repo, "
                 "run /auto-pipeline:init to enable")

MADE_FILES = ["agent.conf", "agent_todo.txt", "agent_completed.txt",
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
        self.assertTrue(os.path.exists(self.repo.path("agent.conf")))

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
        out = self.assertOk(self.start())
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

    def test_an_existing_conf_stops_it_firing(self):
        self.repo.enable_plugin()
        with open(self.repo.path("agent.conf"), "w") as fh:
            fh.write("max_agents=9\n")
        out = self.assertOk(self.start())
        self.assertNotIn(SETUP_LINE, out)
        self.assertEqual(open(self.repo.path("agent.conf")).read(),
                         "max_agents=9\n")

    def test_the_new_conf_is_used_at_once(self):
        """language is read from the conf the same run that created it."""
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
        self.assertEqual(self.lines(out.strip()), [NOT_HERE_LINE])

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

    def test_an_agent_conf_beats_the_scope_check(self):
        """A repo set up by hand keeps working, whatever the scope is."""
        with open(self.repo.path("agent.conf"), "w") as fh:
            fh.write("language=en\n")
        out = self.assertOk(self.start())
        self.assertNotIn(NOT_HERE_LINE, out)
        self.assertIn("QUIZ:", out)

    def test_a_session_id_leaves_no_marker_either(self):
        out = self.assertOk(self.start(
            stdin='{"cwd": "%s", "session_id": "s1", "source": "startup"}'
                  % self.repo.dir))
        self.assertEqual(self.lines(out.strip()), [NOT_HERE_LINE])
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


if __name__ == "__main__":
    unittest.main()
