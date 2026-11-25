"""state-trim: the rule text, the dispatch brief, README and the release (requirements/state-trim.md A8).

  PRINCIPLES.md S8: one terse English line per new rule, every S8 bullet at most 200 characters:
    state add (no echo >>), state trim (what stays, the day archive), the start warning
    (state_warn_lines), the auto clear (compact_clear_at, only into an empty input box), /goal
    (the GOAL: line). The old "the main manager types it into the pane" line is gone.
  PRINCIPLES.md W8: the housekeep pass trims agent_state.txt first.  W14: state lines are written
    with state add.
  skills/dispatch/SKILL.md: the brief has a GOAL: line and its STATE line says state add; the main
    manager types /goal at an idle prompt (tui-idle) after the brief and again after a QUESTION
    answer or a mock / rules answer.
  README.md: one line on state trim.  .claude-plugin/plugin.json: 0.37.0.
"""

import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def section(text, start, end):
    """Lines from the line starting with `start` up to (not incl.) the line starting with `end`."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith(start):
            inside = True
        elif inside and line.startswith(end):
            break
        if inside:
            out.append(line)
    return out


class TestPrinciples(unittest.TestCase):
    def setUp(self):
        self.text = read("PRINCIPLES.md")
        self.s8 = [l for l in section(self.text, "S8.", "S9.") if l.startswith("- ")]

    def has(self, lines, *words):
        hits = [l for l in lines if all(w in l for w in words)]
        self.assertTrue(hits, "no line with %r in:\n%s" % (words, "\n".join(lines)))

    def test_s8_lines_are_terse(self):
        for line in self.s8:
            with self.subTest(line=line[:60]):
                self.assertLessEqual(len(line), 200, line)

    def test_s8_state_add(self):
        self.has(self.s8, "agent-file.sh state add")

    def test_s8_state_trim_and_the_day_archive(self):
        self.has(self.s8, "state trim", "agent_state.trim-")

    def test_s8_the_start_warning(self):
        self.has(self.s8, "Over 300 lines (fixed)", "STATE LONG")   # settings-configure: a constant

    def test_s8_the_auto_clear(self):
        self.has(self.s8, "Compacted 2 times (fixed)", "empty")

    def test_s8_goal(self):
        self.has(self.s8, "/goal", "GOAL:")

    def test_the_old_hand_clear_line_is_gone(self):
        self.assertNotIn("the main manager types it into the pane", self.text)

    def test_w8_housekeep_trims(self):
        self.has(section(self.text, "W8.", "W9."), "housekeep", "state trim")

    def test_w14_state_add(self):
        self.has(section(self.text, "W14.", "W15."), "state add")


class TestDispatchSkill(unittest.TestCase):
    def setUp(self):
        self.text = read("skills", "dispatch", "SKILL.md")
        self.lines = self.text.splitlines()

    def test_the_brief_has_a_goal_line(self):
        goal = [l for l in self.lines if l.startswith("GOAL: task manager <name>: done when")]
        self.assertEqual(len(goal), 1, "one GOAL: line in the brief template")
        for word in ("DONE PASS", "DONE FAIL", "pushed", "QUESTION:", "MOCK READY", "CLOSE CASE", "AUTO CLEAR"):
            self.assertIn(word, goal[0])

    def test_the_brief_state_line_says_state_add(self):
        state = [l for l in self.lines if l.startswith("STATE:")]
        self.assertTrue(state)
        self.assertIn("agent-file.sh state add", state[0])

    def test_the_main_manager_types_goal_at_an_idle_prompt(self):
        hits = [l for l in self.lines if "/goal" in l and "tui-idle" in l]
        self.assertTrue(hits, "a step that waits for tui-idle and types /goal")

    def test_goal_again_after_an_answer(self):
        hits = [l for l in self.lines if "/goal" in l and "QUESTION" in l and ("mock yes" in l or "rules yes" in l)]
        self.assertTrue(hits, "a line: re-type /goal after a QUESTION answer and a mock or rules answer")


class TestReadmeAndRelease(unittest.TestCase):
    def test_readme_names_state_trim(self):
        self.assertIn("state trim", read("PRINCIPLES.md"))

    def test_release_0_37_0(self):
        data = json.loads(read(".claude-plugin", "plugin.json"))
        # board-waiting ships 0.38.0 (2026-11-20): 0.37.0 or later
        self.assertGreaterEqual(tuple(int(n) for n in data["version"].split(".")), (0, 37, 0))


if __name__ == "__main__":
    unittest.main()
