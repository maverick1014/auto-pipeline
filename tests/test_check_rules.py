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

NAMES = ["DIFF SCAN", "BUILD", "RELATED TESTS", "MODULE TESTS", "GUARD TESTS", "DB CHECK", "DATA CHECK",
         "CORE REVIEW", "PR REVIEW", "EXAMPLES TEST", "FLOW CHECK", "UI CHECK",
         "REAL DATA COUNT"]
ANSWERS = ("1A 2D 3C 4B 5D 6D 7C 8C 9A 10D 11C 12C 13D 14C 15D 16B 17C "
           "18D 19C 20A 21D 22C 23B 24D 25B 26D 27B 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C 38B 39B")

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
  B. x1 and x2 branch from production and each merges straight into production when done (production merged back into your working branch after each); x3 and x4 branch from your working branch and merge there; one full suite there after both are in; first check that x1 and x2 need no code only x3 or x4 brings
  C. Wait until all four are done, then merge them straight into production
  D. Branch all four from your working branch and push it to production after x1"""

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
  B. Branch from the production branch, make the smallest fix, PR review and the light related tests, get the owner's yes, merge to production (the release build runs by itself), then merge production back into the working branch
  C. Push a fix straight to production with no check
  D. Wait for the nightly run"""


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
                       "check_budget_s", "60 s", "the net", "NIGHTLY RUN", "RELEASE SMOKE",
                       # owner 1A 2026-11-25 (section 15)
                       "No task runs the full suite", "MODULE TESTS", "gates nothing", "selection miss",
                       "agent-nightly.sh", "the last nightly on that commit", "agent-nightly.sh --release-ok",
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
        extra = {"OWNER SIGN", "NIGHTLY RUN", "RELEASE RUN", "RELEASE SMOKE", "TEST RUN", "URGENT FIX", "WORKING BRANCH",   # a start line, not a block (section 41 G9)
                   # sign, net, runner
                 "DONE PASS", "DONE FAIL", "CLOSE CASE", "NEEDS HUMAN", "MOCK READY", "STALE PLUGIN",
                 "STATE LONG", "OWNER TODO", "QUESTIONS PAGE", "OWNER ORDER", "REPO TASK",   # report words
                 "GATE PASS", "GATE REFUSED", "CHECK PASS", "CHECK FAIL", "MERGE PASS", "MERGE FAIL",
                 "WATCH SIGNAL", "WATCH STALL", "WATCH LOST", "WATCH ROOM", "AUTO CLEAR",
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
        for phrase in ("RELATED TESTS", "GUARD TESTS", "MODULE TESTS", "only when its trigger fires",
                       "never re-run tests the task manager already passed", "re-run only the tests that failed"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w4)
        self.assertNotIn("Full suite only when really needed", w4)
        self.assertNotIn("FULL SUITE", w4)
        self.assertIn("No task runs the full suite", w4)

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
        # section 42 B2: no run at the merge, so no undo line; the --hard warning stays in its own words
        for phrase in ("checks gate", "after every merge", "Never `git reset --hard` in the main checkout"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w8)

    def test_w9_small_tasks_and_self_assignment(self):
        w9 = self.rule("W9. ", "W10. ")
        for phrase in ("own git worktree", "never share a checkout", "agent-file.sh next",
                       "at every wake", "needs no new question", "todo done",
                       "room under the Max memory % limit (S3)"):   # section 37 F5: room, not slots
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w9)
        self.assertNotIn("free slot under the machine caps", w9)
        self.assertNotIn("Never spawn a worktree for a small task", w9)

    def test_w15_restart_the_watch_first(self):
        w15 = self.rule("W15. ", "W16. ")
        self.assertIn("the first action is to start the watch again, then handle the signal", w15)
        self.assertIn("when there is room for a queued task (WATCH ROOM)", w15)   # section 42 S7   # section 37 F5: room, not slots
        self.assertNotIn("slot is free", w15)
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
        for name in ("PR REVIEW", "EXAMPLES TEST", "FLOW CHECK", "UI CHECK", "REAL DATA COUNT", "CORE REVIEW"):
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
        for phrase in ("checks gate", "check-deputy", "GATE REFUSED", "PR REVIEW", "FLOW CHECK", "UI CHECK"):
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
        for phrase in ("FLOW CHECK", "UI CHECK", "RELEASE SMOKE", "one at a time", "15-minute",
                       "agent-file.sh idea add",
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
        self.assertNotIn("ORIG_HEAD", text)             # section 42 B2: no test run at the merge, nothing to undo
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
        for n, text in ((6, QUIZ_Q6), (8, QUIZ_Q8), (9, QUIZ_Q9), (16, QUIZ_Q16), (23, QUIZ_Q23), (25, QUIZ_Q25), (35, QUIZ_Q35), (38, QUIZ_Q38), (39, QUIZ_Q39)):
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
                good = "38B" if wrong.startswith("38") else "39B"
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


class TestMemoryGate(unittest.TestCase):
    """Owner 2026-11-25 (TELL 076c1faf, section 24): no slots; a memory gate with a per-machine reservation
    list; CPU soft; jobs go to a connected machine first; what is sent away is cleaned up there."""

    def text(self):
        return read("PRINCIPLES.md")

    def test_s3_to_s6(self):
        s = section(self.text(), "S3. ", "S7. ")
        for phrase in ("memory in use now + the memory this run is known to need", "Load: Max memory %",
                       "measured peak MB", "never measured", "starts at once with a monitor on its memory",
                       "the newest, unmeasured one first", "records its peak MB", "tried again when there is room",
                       "Only test and build runs are stopped", "a Claude pane counts too",
                       "reservation list", "a dead pid frees its entry", "CPU", "the soft one", "the hard gate",
                       "Long but light runs just go", "agent-room.sh"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, s)

    def test_no_slots_and_no_special_machine_anywhere(self):
        for path in (("PRINCIPLES.md",), ("skills", "dispatch", "SKILL.md"), ("skills", "merge", "SKILL.md"),
                     ("agents", "merge-deputy.md"), ("agents", "fast-lane-deputy.md"), ("agents", "worker.md")):
            with self.subTest(path=path):
                text = read(*path).lower()
                for word in ("heavy-test slot", "heavy test slot", "heavy-test machine", "heavy_test_slots"):
                    self.assertNotIn(word, text)

    def test_placement(self):
        for start, end in (("W7. ", "W8. "), ("W9. ", "W10. ")):
            with self.subTest(rule=start):
                self.assertIn("connected machine first", section(self.text(), start, end))
        disp = read("skills", "dispatch", "SKILL.md")
        self.assertIn("connected machine first", disp)
        self.assertIn("agent-room.sh check", disp)

    def test_remote_cleanup(self):
        w8 = section(self.text(), "W8. ", "W9. ")
        for phrase in ("cleaned up there", "scratch clones", "temp test folders", "its reservation"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w8)
        self.assertIn("scratch clones", read("agents", "merge-deputy.md"))

    def test_s4_over_the_limit(self):
        s4 = section(self.text(), "S4. ", "S5. ")
        for phrase in ("start nothing new", "close done and idle panes first", "stop test runs before anything else",
                       "never stop a working agent", "tell the main manager", "agent-room.sh relief"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, s4)

    def test_s6_no_count_caps(self):
        s6 = section(self.text(), "S6. ", "S7. ")
        self.assertIn("No count caps", s6)
        self.assertIn("a new agent pane is admitted by the same rule", s6)
        self.assertNotIn("Max agents", self.text())
        self.assertNotIn("max_agents", read("skills", "dispatch", "SKILL.md"))

    def test_plugin_json_has_no_slot_setting(self):
        import json
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as fh:
            conf = json.load(fh)["userConfig"]
        self.assertNotIn("heavy_test_slots", conf)
        self.assertNotIn("max_agents", conf)
        self.assertEqual(len(conf), 17)   # + Reviewer model (owner 2A), Working branch, Auto clear after quiet

class TestKeepTheResultLines(unittest.TestCase):
    """Core review re-check defect A (b, c): a verified task's worktree is removed before the owner's yes
    (W8): its CHECK lines go to the main repo first; the REPORT carries them; the gate then runs on a
    scratch copy of the pushed branch."""

    def test_dispatch_step_8_gathers_first(self):
        text = read("skills", "dispatch", "SKILL.md")
        step8 = section(text, "\n8. ", "\n9. ")
        self.assertIn("agent-file.sh checks gather", step8)
        self.assertLess(step8.index("checks gather"), step8.index("remove its worktree"))

    def test_the_report_carries_the_check_lines(self):
        brief = section(read("skills", "dispatch", "SKILL.md"), "## Task manager brief", "## Cross-repo brief")
        report = [l for l in brief.splitlines() if l.startswith("REPORT:")][0]
        self.assertIn("CHECK lines", report)
        self.assertIn("indented", report)   # state add refuses a line that starts with CHECK

    def test_merge_runs_the_gate_on_a_scratch_copy_when_the_worktree_is_gone(self):
        text = read("skills", "merge", "SKILL.md")
        self.assertIn("scratch", text)
        self.assertIn("checks gather", text)

    def test_w8_says_so(self):
        w8 = section(read("PRINCIPLES.md"), "W8. ", "W9. ")
        self.assertIn("checks gather", w8)


class TestWorkingBranchRules(unittest.TestCase):
    """Owner 2026-11-25 (sections 28-29): one working-branch model for every repo."""

    def test_r1_target_from_the_request(self):
        r1 = section(read("PRINCIPLES.md"), "R1. ", "R2. ")
        for phrase in ("Merge into the target branch + cleanup", "the user's request decides",
                       "publish or merge to main", "straight into the production branch", "the deploy follows by itself",
                       "ap-main-<name>", "nothing goes to production by itself"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r1)

    def test_r8_the_model(self):
        r8 = section(read("PRINCIPLES.md"), "R8. Check blocks", "## B. Work")
        for phrase in ("Flow: Working branch", "the main checkout is switched to the working branch",
                       "never on the production branch by accident",
                       "when the last one of the batch is merged, ONE full suite runs on the working branch",
                       "per person", "ap-main-<name>", "worked out once per clone and stored", "every brief names the branch",
                       "never derives it again", "nobody else merges into it", "the sweep never deletes it",
                       "merged into the working branch at the start of a batch and again before a publish",
                       "agent-promote.sh --sync",
                       "only on the owner's approval", "only from a green commit",
                       "agent-promote.sh", "merged to production = published", "new fixer agent",
                       "never back to the builder"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r8)

    def test_w8_and_w9(self):
        w8 = section(read("PRINCIPLES.md"), "W8. ", "W9. ")
        for phrase in ("working branch", "agent-promote.sh --task", "a short-lived worktree of the production branch",
                       "production is merged back into the working branch at once"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w8)
        w9 = section(read("PRINCIPLES.md"), "W9. ", "W10. ")
        for phrase in ("branches from the production branch", "branches from the working branch", "--batch",
                       "may also wait until the working branch is tested and published",
                       "The target is per task, not per request",
                       "does an urgent task need code that only a non-urgent one brings",
                       "tell the owner at once", "never guess"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w9)

    def test_merge_deputy_merges_into_the_working_branch(self):
        text = read("agents", "merge-deputy.md")
        given = [l for l in text.splitlines() if l.startswith("Your brief gives")][0]
        self.assertIn("<working branch>", given)
        self.assertIn("git push origin <working branch>", text)
        self.assertNotIn("git push origin main", text)
        self.assertIn("agent-promote.sh --task", text)
        self.assertNotIn("--after-merge", text)

    def test_merge_skill(self):
        text = read("skills", "merge", "SKILL.md")
        for phrase in ("working branch", "new fixer agent", "never back to the builder", "agent-promote.sh"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn("working branch:", section(text, "name: <name>", "todo done arguments:"))

    def test_dispatch_and_init_skills(self):
        disp = read("skills", "dispatch", "SKILL.md")
        for phrase in ("--target production", "--batch", "--base-branch <base branch>", "publish or merge to main"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, disp)
        self.assertIn("working branch", read("skills", "init", "SKILL.md"))

class TestReviewIsTheMainCheck(unittest.TestCase):
    """Section 21 (owner and main manager, 2026-11-25; corrects section 19), for every repo on the plugin."""

    def r8(self):
        return section(read("PRINCIPLES.md"), "R8. Check blocks", "## B. Work")

    def test_r8_head(self):
        r8 = self.r8()
        head = r8[:r8.index("| Block |")]
        for phrase in ("let other agents verify the outcome of the code instead of letting test cases do it",
                       "PR REVIEW", "did not build it", "reads the diff against the approved requirement",
                       "the main check of every task", "its cost follows the diff size",
                       "only when what the user sees or does changed", "15-minute time box", "ideas file",
                       "light related tests", "a bug that a review or check finds gets a small test with its fix",
                       "The full suite is the safety net only", "URGENT FIX", "branch from the production branch",
                       "the owner's yes", "merge production back into the working branch"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, head)
        self.assertNotIn("runs the real thing once", r8)

    def test_r8_release_run_failures(self):
        r8 = self.r8()
        for phrase in ("agent-nightly.sh --failures", "test out of date", "real break",
                       "No check is deleted without a twin", "a table of these labels"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r8)

    def test_the_old_urgent_line_is_gone(self):
        self.assertNotIn("a verified owner order may move a block to right after the release", self.r8())

    def test_dispatch(self):
        text = read("skills", "dispatch", "SKILL.md")
        for phrase in ("PR REVIEW", "every task", "URGENT FIX", "branch from the production branch"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_merge_skill(self):
        text = read("skills", "merge", "SKILL.md")
        for phrase in ("URGENT FIX", "agent-promote.sh", "merge production back into the working branch",
                       "agent-nightly.sh --failures", "test out of date", "real break", "new fixer agent"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_check_deputy(self):
        # owner 2A: the PR REVIEW is the reviewer's (agents/reviewer.md); the check deputy runs FLOW and UI CHECK
        text = read("agents", "check-deputy.md")
        for phrase in ("FLOW CHECK", "UI CHECK", "15-minute", "only the approved items", "agent-file.sh idea add"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_no_retired_block_names_left(self):
        for path in (("PRINCIPLES.md",), ("skills", "dispatch", "SKILL.md"), ("skills", "merge", "SKILL.md"),
                     ("agents", "check-deputy.md"), ("agents", "fast-lane-deputy.md"), ("agents", "merge-deputy.md")):
            with self.subTest(path=path):
                text = read(*path)
                self.assertNotIn("DIFF READ", text)
                self.assertNotIn("OUTCOME CHECK", text)


class TestReviewer(unittest.TestCase):
    """Owner 2A 2026-11-25 (TELL 173d8a8b): "Models: Reviewer model" (default opus-5.5:high) runs the PR REVIEW
    of every task and the CORE REVIEW; R1 states the fixed sequence."""

    def test_the_setting(self):
        sys.path.insert(0, BIN)
        import agent_conf
        by = {x["key"]: x for x in agent_conf.SETTINGS}
        self.assertEqual((by["reviewer_model"]["title"], by["reviewer_model"]["default"]),
                         ("Models: Reviewer model", "opus-5.5:high"))
        self.assertTrue(agent_conf.validate_value("reviewer_model", "sonnet-5:high"), "a reviewer decides: floor")
        self.assertIsNone(agent_conf.validate_value("reviewer_model", "opus-5.5:high"))

    def test_the_reviewer_agent(self):
        text = read("agents", "reviewer.md")
        head = text.split("---")[1]
        self.assertIn("name: reviewer", head)
        self.assertIn("model: opus", head)
        tools = [l for l in head.splitlines() if l.startswith("tools:")][0]
        for tool in ("Read", "Grep", "Glob", "Bash"):
            self.assertIn(tool, tools)
        for tool in ("Edit", "Write"):
            self.assertNotIn(tool, tools)
        body = text.split("---", 2)[2]
        for phrase in ("Reviewer model", "PR REVIEW", "CORE REVIEW", "approved requirement", "nothing else",
                       "edge list", "no check deleted", "no secret", "agent-file.sh check", "fix order", "floor"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_r1_fixed_sequence(self):
        r1 = section(read("PRINCIPLES.md"), "R1. ", "R2. ")
        for phrase in ("builder reports done", "reviewer reads the diff against the approved requirement",
                       "check deputy only when what the user sees or does changed (15 min box)", "merge deputy",
                       "A fail at review or check goes back to the builder as a fix order", "Reviewer model"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r1)

    def test_merge_skill_sends_the_reviewer(self):
        text = read("skills", "merge", "SKILL.md")
        self.assertIn("subagent_type: reviewer", text)
        self.assertIn("reviewer_model", text)
        self.assertLess(text.index("subagent_type: reviewer"), text.index("subagent_type: check-deputy"))
