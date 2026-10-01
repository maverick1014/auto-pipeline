"""The words agents read about time (task estimate-data, E7).

WHY (owner, 2026-09-30). An estimate means AGENT WORK minutes only. Waiting
(mock gate, owner question or review, hold, suite slot) is reported apart and
never counted as work. The main manager passes both numbers and the task
facts to `agent-file.sh todo done`. A time question from the human gets a
duration AND a clock time, and when he is needed next.

CONTRACT (terse English, one line per rule; phrases are matched, not sentences)

PRINCIPLES.md
    W11 Time   every rule one "- " line. It says: the estimate is agent work
               only; the waits by name (mock gate, owner question, review,
               hold, suite slot) are not work; the done report line is
               `TIME: est <n>m, actual <n>m, wait <n>m` (never "human <n>m");
               the main manager passes work, wait and the facts to
               `todo done`; a time question from the human gets a duration
               AND a clock time and when he is needed next, from
               `bin/agent-file.sh eta`.
    R5         the done line carries one `data` block written by
               agent-file.sh; the keys are named: repo, type, lane, mock, est,
               work, wait, clock, bounces, workers, files, lines, tests, adds.
    W8         the deputy's `todo done` carries the facts and `--merge`.

skills/dispatch/SKILL.md
    step 1     the estimate is agent work only (waits are not in it).
    step 2     a fast-lane task is closed with `todo done ... --lane fast`.
    brief      REPORT ends with `TIME: est <n>m, actual <n>m, wait <n>m` and
               one `FACTS:` line: type, lane, mock, bounces, workers, tests,
               scope adds. HEARTBEAT carries `work <m>m`.
    time question   `agent-file.sh eta`, duration AND clock time, needed next.

skills/merge/SKILL.md
    step 1     a done report with no TIME line (work and wait apart) bounces.
    brief      the deputy gets the `todo done` arguments: --work --wait
               --bounces --workers --mock --lane --type --tests --adds.

skills/close-case/SKILL.md
    the CLOSE CASE report keeps work and wait apart (TIME: est, actual, wait);
    close now writes "work so far" and the wait on the todo line that stays.

agents/merge-deputy.md
    the brief value "todo done arguments"; step 7 adds `--merge <merge hash>`.

bin/agent-close-case.sh
    the hook's report line says `wait <n>m`, never `human <n>m`.

README.md
    the command list shows `agent-file.sh time`, `data`, `eta`.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TIME_LINE = "TIME: est <n>m, actual <n>m, wait <n>m"
DATA_KEYS = ["repo", "type", "lane", "mock", "est", "work", "wait", "clock",
             "bounces", "workers", "files", "lines", "tests", "adds"]
DONE_FACTS = ["--work", "--wait", "--bounces", "--workers", "--mock", "--lane",
              "--type", "--tests", "--adds"]


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def section(text, start, end):
    """The text from the line that starts with `start` up to `end`."""
    a = text.index(start)
    return text[a:text.index(end, a)]


class TestPrinciplesTime(unittest.TestCase):

    def w11(self):
        return section(read("PRINCIPLES.md"), "W11. Time", "W12.")

    def test_every_w11_rule_is_one_dash_line(self):
        lines = [l for l in self.w11().splitlines()[1:] if l.strip()]
        self.assertGreaterEqual(len(lines), 6)
        for line in lines:
            with self.subTest(line=line):
                self.assertTrue(line.startswith("- "), line)

    def test_w11_no_rule_line_is_long(self):
        for line in self.w11().splitlines():
            with self.subTest(line=line):
                self.assertLessEqual(len(line), 170, line)

    def test_w11_the_estimate_is_agent_work_only(self):
        self.assertRegex(self.w11().lower(), r"estimate = agent work")

    def test_w11_names_the_waits(self):
        text = self.w11().lower()
        for wait in ("mock gate", "owner question", "review", "hold", "suite slot"):
            with self.subTest(wait=wait):
                self.assertIn(wait, text)

    def test_w11_has_the_new_time_line(self):
        self.assertIn(TIME_LINE, self.w11())

    def test_w11_says_actual_is_agent_work(self):
        self.assertRegex(self.w11().lower(), r"actual = agent work")

    def test_the_old_human_minutes_are_gone(self):
        self.assertNotIn("human <n>m", read("PRINCIPLES.md"))

    def test_w11_the_main_manager_passes_the_numbers_to_todo_done(self):
        text = self.w11()
        self.assertIn("todo done", text)
        self.assertIn("main manager", text.lower())

    def test_w11_keeps_the_two_times_rule_on_work(self):
        self.assertRegex(self.w11(), r"(?i)work over 2× estimate")

    def test_w11_a_time_question_gets_a_duration_and_a_clock_time(self):
        text = self.w11().lower()
        for phrase in ("time question", "duration", "clock time", "needed next",
                       "agent-file.sh eta"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_w11_still_points_at_the_time_table(self):
        self.assertIn("bin/agent-file.sh time", self.w11())

    def test_r5_names_the_data_block_and_its_keys(self):
        r5 = section(read("PRINCIPLES.md"), "R5. Task files", "R6.")
        self.assertIn("`data`", r5)
        for key in DATA_KEYS:
            with self.subTest(key=key):
                self.assertRegex(r5, r"\b%s\b" % key)

    def test_r5_no_longer_says_est_slash_actual(self):
        r5 = section(read("PRINCIPLES.md"), "R5. Task files", "R6.")
        self.assertNotIn("est/actual", r5)

    def test_w8_the_deputy_passes_the_facts_and_the_merge_commit(self):
        w8 = section(read("PRINCIPLES.md"), "W8. Merge and cleanup", "W9.")
        self.assertIn("todo done", w8)
        self.assertIn("--merge", w8)
        self.assertIn("facts", w8.lower())


class TestDispatchSkill(unittest.TestCase):

    def text(self):
        return read("skills", "dispatch", "SKILL.md")

    def brief(self):
        return section(self.text(), "## Task manager brief", "## Cross-repo brief")

    def test_step_1_the_estimate_is_agent_work_only(self):
        step1 = section(self.text(), "\n1. ", "\n2. ")
        self.assertIn("agent work only", step1.lower())
        self.assertIn("wait", step1.lower())

    def test_step_1_still_reads_the_time_table(self):
        step1 = section(self.text(), "\n1. ", "\n2. ")
        self.assertIn("agent-file.sh time", step1)

    def test_a_fast_lane_task_is_closed_with_its_work_minutes(self):
        step2 = section(self.text(), "\n2. ", "\n3. ")
        self.assertIn("todo done", step2)
        self.assertIn("--lane fast", step2)
        self.assertIn("--work", step2)

    def test_the_brief_report_has_the_new_time_line(self):
        self.assertIn(TIME_LINE, self.brief())

    def test_the_old_human_minutes_are_gone(self):
        self.assertNotIn("human <n>m", self.text())

    def test_the_brief_says_what_counts_as_wait(self):
        report = [l for l in self.brief().splitlines() if l.startswith("REPORT:")][0]
        for phrase in ("agent work only", "mock gate", "suite slot"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, report.lower())

    def test_the_brief_report_has_a_facts_line(self):
        brief = self.brief()
        self.assertIn("FACTS:", brief)
        facts = brief[brief.index("FACTS:"):].splitlines()[0]
        for word in ("type", "lane", "mock", "bounces", "workers", "tests",
                     "scope adds"):
            with self.subTest(word=word):
                self.assertIn(word, facts)

    def test_the_brief_names_the_types(self):
        brief = self.brief()
        for kind in ("page", "server", "script", "docs", "cloud", "app", "data",
                     "mixed"):
            with self.subTest(type=kind):
                self.assertRegex(brief, r"\b%s\b" % kind)

    def test_the_heartbeat_carries_the_work_minutes(self):
        beat = [l for l in self.brief().splitlines() if l.startswith("HEARTBEAT:")][0]
        self.assertIn("step <n> of 7", beat)
        self.assertIn("work <m>m", beat)

    def test_the_heartbeat_still_starts_the_old_way(self):
        # the city reads "HEARTBEAT <name>: step <n>"
        self.assertIn('"HEARTBEAT <name>: step <n> of 7, ', self.brief())

    def test_a_time_question_is_answered_with_the_eta_line(self):
        text = self.text()
        self.assertIn("agent-file.sh eta", text)
        low = text.lower()
        for phrase in ("time question", "clock time", "needed next",
                       "--step", "--work-so-far"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, low)

    def test_the_eta_call_uses_the_plugin_root(self):
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh eta", self.text())


class TestMergeSkill(unittest.TestCase):

    def text(self):
        return read("skills", "merge", "SKILL.md")

    def test_a_report_with_no_time_line_bounces(self):
        step1 = section(self.text(), "\n1. ", "\n2. ")
        self.assertIn("TIME", step1)
        self.assertIn("wait", step1.lower())

    def test_the_deputy_brief_carries_the_todo_done_arguments(self):
        text = self.text()
        self.assertIn("todo done arguments:", text)
        line = text[text.index("todo done arguments:"):].splitlines()[0]
        for fact in DONE_FACTS:
            with self.subTest(fact=fact):
                self.assertIn(fact, line)

    def test_the_brief_no_longer_says_five_values(self):
        self.assertNotIn("all five values", self.text())

    def test_it_says_where_the_numbers_come_from(self):
        text = self.text()
        self.assertIn("FACTS", text)
        self.assertRegex(text, r"(?i)actual = agent work|agent work only")


class TestCloseCaseSkill(unittest.TestCase):

    def text(self):
        return read("skills", "close-case", "SKILL.md")

    def test_the_report_keeps_work_and_wait_apart(self):
        text = self.text()
        self.assertIn("TIME", text)
        self.assertRegex(text.lower(), r"work and wait apart")

    def test_close_now_keeps_the_work_so_far_on_the_todo_line(self):
        part = section(self.text(), "**close now**", "\n3. ")
        self.assertIn("work so far", part.lower())
        self.assertIn("wait", part.lower())

    def test_close_now_still_keeps_the_todo_line_open(self):
        part = section(self.text(), "**close now**", "\n3. ")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add", part)

    def test_no_old_human_minutes(self):
        self.assertNotIn("human <n>m", self.text())


class TestMergeDeputy(unittest.TestCase):

    def text(self):
        return read("agents", "merge-deputy.md")

    def test_the_brief_gives_the_todo_done_arguments(self):
        line = [l for l in self.text().splitlines() if l.startswith("Your brief gives")][0]
        self.assertIn("<todo done arguments>", line)

    def test_step_7_passes_them_and_the_merge_commit(self):
        step7 = [l for l in self.text().splitlines() if l.startswith("7. ")][0]
        self.assertIn('agent-file.sh todo done "<name>"', step7)
        self.assertIn("<todo done arguments>", step7)
        self.assertIn("--merge", step7)

    def test_step_7_still_removes_the_worktree_line(self):
        step7 = [l for l in self.text().splitlines() if l.startswith("7. ")][0]
        self.assertIn('agent-file.sh worktree rm "<worktree path>"', step7)


class TestCloseCaseHook(unittest.TestCase):

    def test_the_hook_asks_for_wait_not_human_minutes(self):
        text = read("bin", "agent-close-case.sh")
        self.assertIn("TIME: est <n>m, actual <n>m, wait <n>m", text)
        self.assertNotIn("human <n>m", text)


class TestReadme(unittest.TestCase):

    def test_the_command_list_shows_the_time_commands(self):
        text = read("README.md")
        for command in ("bin/agent-file.sh time", "bin/agent-file.sh data",
                        "bin/agent-file.sh eta"):
            with self.subTest(command=command):
                self.assertIn(command, text)

    def test_the_time_line_no_longer_says_estimate_vs_actual(self):
        self.assertNotIn("estimate vs actual", read("README.md"))

    def test_the_files_table_says_the_completed_file_is_data_too(self):
        row = [l for l in read("README.md").splitlines()
               if l.startswith("| `agent_completed.txt`")][0]
        self.assertRegex(row.lower(), r"data")


if __name__ == "__main__":
    unittest.main()
