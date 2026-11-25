"""Failing tests for check-blocks, slices 3, 5, 6: the rule text, skills, agents, quiz and
board follow the ONE table. Written by the task manager before any code.

Rules: requirements/check-blocks.md sections 2, 4, 7, 9 C5, 11, 12.
Owner order 2026-11-25: "keep the result into the principle so that others new agent and repo
installed this plugin all follow the most correct rules". Brief: never a rule line that the
table of blocks does not back.

Run: python3 -m unittest tests.test_check_rules
"""

import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from scripthelp import BIN, ScriptCase  # noqa: E402

NAMES = ["DIFF SCAN", "BUILD", "RELATED TESTS", "GUARD TESTS", "DB CHECK", "DATA CHECK",
         "FULL SUITE", "CORE REVIEW", "DIFF READ", "EXAMPLES TEST", "FLOW CHECK", "UI CHECK",
         "REAL DATA COUNT"]
ANSWERS = ("1A 2D 3C 4B 5D 6D 7C 8C 9A 10D 11C 12C 13D 14C 15D 16B 17C "
           "18D 19C 20A 21D 22C 23B 24D 25C 26D 27B 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C 38B 39C")

QUIZ_Q6 = """Q6. You are one of four agents. You changed files under api/auth/. Which tests do you run?
  A. The full suite
  B. Tests for all of api/
  C. None; the manager runs them
  D. The tests agent-level.sh lists under RELATED TESTS (they import or name the changed files)"""

QUIZ_Q16 = """Q16. A small logic task (one function, about 30 minutes) needs a new test. Who does it?
  A. A task manager in a new worktree, because it needs a test
  B. One subagent in its own worktree: it writes the example tests, runs its blocks, pushes a branch
  C. The main manager itself
  D. Nobody: skip the test, it is small"""

QUIZ_Q25 = """Q25. A big task takes the full flow. The order is:
  A. Worktree, workers build, failing tests, verify, merge
  B. Failing tests, worktree, mock, workers build, merge
  C. Todo line + estimate, mock if UI, worktree + task manager, failing tests, workers build, verify, push, acceptance blocks, merge + cleanup, todo done
  D. Mock, workers build, todo line, acceptance blocks, merge"""

QUIZ_Q38 = """Q38. A diff only changes one locale value. agent-level.sh check prints BLOCKS: DIFF SCAN, RELATED TESTS, GUARD TESTS; dispatch planned DIFF READ. What runs?
  A. The full suite once
  B. Those three blocks and a DIFF READ by someone who did not write it, nothing else
  C. Lint, type-check, UI CHECK and FLOW CHECK as well
  D. Nothing: it is only text"""

QUIZ_Q39 = """Q39. The merge gate prints "GATE REFUSED t: DIFF READ missing". The owner is asleep. You:
  A. Take DIFF READ off the todo line and merge
  B. Merge: it is only a diff read
  C. Have someone who did not build it read the diff and write its pass line (agent-file.sh check), then run the gate again; a block goes only on a verified owner order
  D. Write the pass line yourself as the builder"""


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def section(text, start, end):
    begin = text.index(start)
    return text[begin:text.index(end, begin + len(start))]


def table_rows():
    r = subprocess.run([sys.executable, os.path.join(BIN, "agent_blocks.py"), "table"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise AssertionError("agent_blocks.py table failed: %s" % r.stderr)
    return r.stdout.splitlines()


LEVEL_WORDS = re.compile(r"(?i)(\brisk types?\b|\btype [A-D]\b|\b[A-D] = (?:text|ui|logic|danger)\b|--level\b|"
                         r"\btodo level\b|--declared\b|\bRAISE\b|REQUIRED TYPE|\blevel [0-4]\b|\(R8 check)")


# ---------------------------------------------------------------- PRINCIPLES.md


class TestPrinciplesR8(unittest.TestCase):

    def r8(self):
        return section(read("PRINCIPLES.md"), "R8. Check blocks", "## B. Work")

    def test_r8_is_check_blocks_in_its_place(self):
        text = read("PRINCIPLES.md")
        order = [text.index(h) for h in ("R7. Worktree file", "R8. Check blocks", "## B. Work")]
        self.assertEqual(order, sorted(order))
        self.assertNotIn("R8. Risk types", text)
        self.assertEqual(text.count("\nR8. "), 1)

    def test_r8_holds_the_one_table_exactly(self):
        rows = table_rows()
        lines = self.r8().splitlines()
        i = lines.index(rows[0])
        self.assertEqual(lines[i:i + len(rows)], rows)

    def test_the_table_is_in_principles_only_once(self):
        self.assertEqual(read("PRINCIPLES.md").count(table_rows()[0]), 1)

    def test_r8_says_the_owner_goal_and_the_process(self):
        r8 = self.r8()
        for phrase in ("only do the necessary thing when needed", "No levels", "bin/agent_blocks.py",
                       "agent-level.sh check", "todo add", "--checks", "only added",
                       "verified owner order", "--remove", "--owner-quote", "agent-file.sh check",
                       "checks gate", "no pass line", "OWNER SIGN", "not the builder",
                       "check_budget_s", "60 s", "the net", "NIGHTLY SUITE", "RELEASE SMOKE",
                       "agent_repo.conf", "edge add", "which example would have shown it",
                       "Refactor", "Urgent fix", "Rollback", "Research only",
                       "skipped with one printed line", "second agent's opinion only for CORE REVIEW",
                       "copies its defaults from the released", "every changed default"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r8)

    def test_r8_lines_are_short_bullets_or_table_rows(self):
        for line in self.r8().rstrip().splitlines()[1:]:
            with self.subTest(line=line[:50]):
                if not line.strip() or line.startswith("|"):
                    continue
                self.assertTrue(line.startswith("- ") or line.startswith("  - "), line)
                self.assertLessEqual(len(line), 220)

    def test_every_block_name_in_principles_is_in_the_table(self):
        # never a rule line that the table of blocks does not back
        text = read("PRINCIPLES.md").split("## Notice")[0]
        found = set(re.findall(r"\b([A-Z]{2,}(?: [A-Z]{2,})+)\b", text))
        extra = {"OWNER SIGN", "NIGHTLY SUITE", "RELEASE SMOKE",          # the sign and the net, agent_blocks.py
                 "DONE PASS", "DONE FAIL", "CLOSE CASE", "NEEDS HUMAN", "MOCK READY", "STALE PLUGIN",
                 "STATE LONG", "OWNER TODO", "QUESTIONS PAGE", "OWNER ORDER", "REPO TASK",   # report words
                 "GATE PASS", "GATE REFUSED", "CHECK PASS", "CHECK FAIL", "MERGE PASS", "MERGE FAIL",
                 "WATCH SIGNAL", "WATCH STALL", "WATCH LOST", "WATCH SLOT", "AUTO CLEAR",
                 "MODE MISMATCH"}                                               # mode-match, W16
        unknown = sorted(n for n in found if n not in NAMES and n not in extra)
        self.assertEqual(unknown, [], "names in PRINCIPLES.md that are no block: %s" % unknown)


class TestPrinciplesOtherRules(unittest.TestCase):

    def text(self):
        return read("PRINCIPLES.md")

    def rule(self, start, end):
        return section(self.text(), start, end)

    def test_no_level_words_left_in_the_rules(self):
        body = self.text().split("## Notice")[0]
        self.assertEqual(LEVEL_WORDS.findall(body), [])

    def test_r1_lane_by_size_checks_by_triggers(self):
        r1 = self.rule("R1. ", "R2. ")
        for phrase in ("small task = one subagent", "own git worktree", "over 2 hours", "task manager",
                       "Which checks run follows the triggers only (R8)",
                       "A small logic task never opens a task manager just because it needs a test",
                       "past 2x its estimate", "second slice", "goes on from its branch"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r1)
        self.assertNotIn("TDD", r1)

    def test_w4_tests_follow_the_blocks(self):
        w4 = self.rule("W4. ", "W5. ")
        for phrase in ("RELATED TESTS", "GUARD TESTS", "FULL SUITE", "only when its trigger fires",
                       "never re-run tests the task manager already passed", "re-run only the tests that failed"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w4)
        self.assertNotIn("Full suite only when really needed", w4)

    def test_w5_the_check_deputy_drives_the_browser(self):
        w5 = self.rule("W5. ", "W6. ")
        for phrase in ("check deputy", "one at a time", "FLOW CHECK", "UI CHECK", "never verify their own work"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w5)
        self.assertNotIn("Main manager only", w5)

    def test_w6_roles(self):
        w6 = self.rule("W6. ", "W7. ")
        for phrase in ("Check deputy", "agents/check-deputy.md", "verdict with evidence",
                       "The main manager stays free for the human", "runs no long check itself",
                       "own git worktree", "pushes a branch"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w6)

    def test_w8_merge_gate_and_cleanup(self):
        w8 = self.rule("W8. ", "W9. ")
        for phrase in ("checks gate", "after every merge", "git reset --merge ORIG_HEAD", "never --hard"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w8)

    def test_w9_small_tasks_and_self_assignment(self):
        w9 = self.rule("W9. ", "W10. ")
        for phrase in ("own git worktree", "never share a checkout", "agent-file.sh next",
                       "at every wake", "needs no new question", "todo done", "slot"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w9)
        self.assertNotIn("Never spawn a worktree for a small task", w9)

    def test_w15_restart_the_watch_first(self):
        w15 = self.rule("W15. ", "W16. ")
        self.assertIn("the first action is to start the watch again, then handle the signal", w15)
        self.assertIn("a slot is free", w15)
        self.assertIn("board warning", w15)

    def test_the_map_names_the_new_pieces(self):
        f = self.text().split("## F. Map")[1]
        for phrase in ("bin/agent_blocks.py", "bin/agent-level.sh", "Check deputy", "agent_repo.conf",
                       "39-question quiz", "agent-file.sh next", "checks gate"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, f)


# ---------------------------------------------------------------- skills and agents


class TestDispatchSkill(unittest.TestCase):

    def text(self):
        return read("skills", "dispatch", "SKILL.md")

    def test_no_level_words(self):
        self.assertEqual(LEVEL_WORDS.findall(self.text()), [])

    def test_it_picks_the_brief_blocks(self):
        text = self.text()
        for name in ("DIFF READ", "EXAMPLES TEST", "FLOW CHECK", "UI CHECK", "REAL DATA COUNT", "CORE REVIEW"):
            self.assertIn(name, text)
        adds = [l for l in text.splitlines() if "agent-file.sh todo add" in l]
        self.assertTrue(adds)
        for l in adds:
            self.assertIn("--checks", l)

    def test_the_brief_runs_the_blocks_never_full_suite_once(self):
        brief = section(self.text(), "## Task manager brief", "## Cross-repo brief")
        self.assertTrue([l for l in brief.splitlines() if l.startswith("CHECKS:")], brief)
        self.assertFalse([l for l in brief.splitlines() if l.startswith("LEVEL:")])
        self.assertIn("run the blocks of the task", brief)
        self.assertNotIn("Full suite once", brief)
        self.assertNotIn("Full suite twice", brief)

    def test_next_at_every_wake(self):
        self.assertIn("agent-file.sh next", self.text())

    def test_small_task_subagent_in_its_own_worktree(self):
        step2 = section(self.text(), "\n2. ", "\n3. ")
        for phrase in ('isolation: "worktree"', "--builder", "EXAMPLES TEST", "merge-deputy"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, step2)

    def test_default_pane_of_orca_worktree_create(self):
        # slice 8 (c): use the default agent pane for the brief or close it, never a second one
        text = self.text()
        self.assertIn("default", text)
        self.assertIn("never open a second", text)

    def test_requirement_defaults_from_the_released_template(self):
        text = self.text()
        self.assertIn("released template", text)
        self.assertIn("every changed default", text)


class TestMergeSkill(unittest.TestCase):

    def text(self):
        return read("skills", "merge", "SKILL.md")

    def test_no_level_words(self):
        self.assertEqual(LEVEL_WORDS.findall(self.text()), [])

    def test_gate_and_check_deputy(self):
        text = self.text()
        for phrase in ("checks gate", "check-deputy", "GATE REFUSED", "FLOW CHECK", "UI CHECK", "DIFF READ"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertLess(text.index("checks gate"), text.index("merge-deputy"))

    def test_the_deputy_brief_has_no_level(self):
        block = section(self.text(), "name: <name>", "todo done arguments:")
        self.assertNotIn("level:", block)
        self.assertIn("session:", block)
        self.assertIn("machine:", block)


class TestAgents(unittest.TestCase):

    def test_check_deputy(self):
        text = read("agents", "check-deputy.md")
        head = text.split("---")[1]
        self.assertIn("name: check-deputy", head)
        self.assertIn("model: sonnet", head)
        tools = [l for l in head.splitlines() if l.startswith("tools:")][0]
        for tool in ("Read", "Grep", "Glob", "Bash", "mcp__claude-in-chrome__"):
            self.assertIn(tool, tools)
        self.assertNotIn("Edit", tools)
        self.assertNotIn("Write", tools)
        body = text.split("---", 2)[2]
        for phrase in ("DIFF READ", "FLOW CHECK", "UI CHECK", "RELEASE SMOKE", "one at a time",
                       "agent-file.sh check", "CHECK PASS", "CHECK FAIL", "never edit", "floor"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_fast_lane_deputy(self):
        text = read("agents", "fast-lane-deputy.md")
        self.assertEqual(LEVEL_WORDS.findall(text), [])
        for phrase in ("own git worktree", "EXAMPLES TEST", "example tests first", "agent-level.sh check",
                       "agent-file.sh check", "push", "2x its estimate", "second slice"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertNotIn("No worktree, no TDD", text)

    def test_merge_deputy(self):
        text = read("agents", "merge-deputy.md")
        self.assertEqual(LEVEL_WORDS.findall(text), [])
        self.assertIn("checks gate", text)
        self.assertLess(text.index("checks gate"), text.index("git merge --no-ff"))
        self.assertIn("git reset --merge ORIG_HEAD", text)
        self.assertNotIn("reset --hard", text)
        given = [l for l in text.splitlines() if l.startswith("Your brief gives")][0]
        self.assertNotIn("<level>", given)
        self.assertIn("<session>", given)
        self.assertIn("<machine>", given)

    def test_worker_adds_an_edge_after_a_fix(self):
        self.assertIn("agent-file.sh edge add", read("agents", "worker.md"))


# ---------------------------------------------------------------- the quiz


class TestQuiz(ScriptCase):
    script = "agent-start.sh"

    def quiz(self):
        return self.assertOk(self.repo.run("agent-start.sh", "--quiz"))

    def question(self, out, n):
        i = out.index("Q%d. " % n)
        return "\n".join(out[i:].splitlines()[:5])

    def test_the_changed_questions(self):
        out = self.quiz()
        for n, text in ((6, QUIZ_Q6), (16, QUIZ_Q16), (25, QUIZ_Q25), (38, QUIZ_Q38), (39, QUIZ_Q39)):
            with self.subTest(q=n):
                self.assertEqual(self.question(out, n), text)

    def test_no_level_words_in_the_quiz(self):
        self.assertEqual(LEVEL_WORDS.findall(self.quiz()), [])

    def test_still_39_and_the_new_key_passes(self):
        out = self.quiz()
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", out)), 39)
        r = self.repo.run("agent-start.sh", "--answer", ANSWERS)
        self.assertIn("QUIZ RESULT: 39/39 PASS", r.stdout)

    def test_a_wrong_block_answer_names_r8(self):
        for wrong in ("38A", "38C", "39A", "39D"):
            with self.subTest(wrong=wrong):
                good = "38B" if wrong.startswith("38") else "39C"
                r = self.repo.run("agent-start.sh", "--answer", ANSWERS.replace(good, wrong))
                self.assertEqual(r.returncode, 1)
                self.assertIn("Q%s(R8)" % wrong[:2], r.stdout)

    def test_every_block_named_in_the_quiz_is_in_the_table(self):
        found = set(re.findall(r"\b([A-Z]{2,}(?: [A-Z]{2,})+)\b", self.quiz()))
        extra = {"GATE REFUSED", "CLOSE CASE", "DONE PASS", "DONE FAIL"}
        self.assertEqual(sorted(n for n in found if n not in NAMES and n not in extra), [])


# ---------------------------------------------------------------- this repo's facts and the board


class TestThisRepo(unittest.TestCase):

    def conf(self):
        out = {}
        for line in read("agent_repo.conf").splitlines():
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out.setdefault(k, v)
        return out

    def test_version_1_with_the_test_commands(self):
        c = self.conf()
        self.assertEqual(c["version"], "1")
        self.assertEqual(c["related_cmd"], "python3 -m unittest {modules}")
        self.assertEqual(c["full_cmd"], "python3 -m unittest discover -s tests -t .")
        self.assertTrue(c["build_cmd"].startswith("python3 -m compileall -q"))
        self.assertIn("tests/test_plugin_layout.py", c["guard_tests"].split(","))

    def test_core_paths_are_permission_and_owner_orders_not_rule_text(self):
        core = self.conf()["core_paths"].split(",")
        for path in ("bin/agent_guard.py", "bin/agent_owner_order.py", "hooks/", ".claude-plugin/"):
            self.assertIn(path, core)
        for path in ("PRINCIPLES.md", "skills/", "agents/"):
            self.assertNotIn(path, core)
        self.assertNotIn("level3_paths", self.conf())
        self.assertNotIn("level4_paths", self.conf())


if __name__ == "__main__":
    unittest.main()


class TestAgentFileHeader(unittest.TestCase):
    """Kick-off answer 4: --level and todo level still work for old callers; no doc names them as
    the way to work. The usage header of agent-file.sh says so on every line that names them."""

    def header(self):
        lines = []
        for line in read("bin", "agent-file.sh").splitlines():
            if not line.startswith("#"):
                break
            lines.append(line)
        return lines

    def test_level_lines_say_old_callers_only(self):
        hits = [l for l in self.header() if "--level" in l or "todo level" in l]
        self.assertTrue(hits)
        for l in hits:
            with self.subTest(line=l[:60]):
                self.assertIn("old callers", l)
                self.assertNotIn("risk type", l)

    def test_the_header_names_the_blocks_commands(self):
        text = "\n".join(self.header())
        for cmd in ("--checks", "todo checks", "todo est", "checks gate", "agent-file.sh next", "edge add",
                    "agent-file.sh check "):
            with self.subTest(cmd=cmd):
                self.assertIn(cmd, text)
