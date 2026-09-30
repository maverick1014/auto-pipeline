"""Failing tests for the naming rule text. Written by the task manager first.

Owner, 2026-09-30: sessions are named by role (see tests/test_agent_name.py
for the hook). The rules and skills must use the same names, because the name
is the SendMessage address.

CONTRACT.

  PRINCIPLES.md
    - one short naming rule, a single line (at most 320 characters) that
      names every role: `<repo> Manager`, `<feature> Task Manager`,
      `<repo> Helper`, `<feature> Worker <n>`, a `Deputy` and a `Merge`
      name, and says the SessionStart hook bin/agent-name.sh sets the first
      three
    - the "Talk between sessions" line (W10) says what to do when two
      sessions share a name: add the [ref] ListAgents prints
    - W12 finds the peer by `<repo> Manager`, no longer "named after the
      other repo's folder"

  skills/dispatch/SKILL.md
    - the task manager launch gives the session and the Orca tab the same
      name: claude --name "<name> Task Manager" and
      --title "<name> Task Manager" (the old --title "TM <name>" is gone)
    - fast lane: the Agent description is "<task> Deputy"
    - the task manager brief (step 4): each worker's Agent description is
      "<name> Worker <n>: <slice>"

  skills/merge/SKILL.md
    - the merge deputy's Agent description is "<name> Merge"

  skills/close-case/SKILL.md
    - the sessions that get the words close case are found by name:
      "<feature> Task Manager" or "<name> Task Manager", and "<repo> Helper"
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def section(text, start, end):
    """The text from the line starting with `start` up to the line starting with `end`."""
    lines = text.splitlines()
    begin = next(i for i, line in enumerate(lines) if line.startswith(start))
    stop = next(i for i in range(begin + 1, len(lines)) if lines[i].startswith(end))
    return "\n".join(lines[begin:stop])


class TestPrinciples(unittest.TestCase):

    def setUp(self):
        self.text = read("PRINCIPLES.md")

    def naming_lines(self):
        return [line for line in self.text.splitlines()
                if "<repo> Manager" in line and "<feature> Task Manager" in line]

    def test_one_naming_rule(self):
        self.assertEqual(len(self.naming_lines()), 1, self.naming_lines())

    def test_the_rule_names_every_role(self):
        line = self.naming_lines()[0]
        for word in ("<repo> Manager", "<feature> Task Manager", "<repo> Helper",
                     "<feature> Worker <n>", "Deputy", "Merge", "bin/agent-name.sh"):
            with self.subTest(word=word):
                self.assertIn(word, line)

    def test_the_rule_is_short(self):
        self.assertLessEqual(len(self.naming_lines()[0]), 320)

    def test_talk_between_sessions_handles_a_shared_name(self):
        line = next(l for l in self.text.splitlines()
                    if l.startswith("- Talk between sessions"))
        self.assertIn("[ref]", line)

    def test_cross_repo_peer_is_found_by_manager_name(self):
        w12 = section(self.text, "W12.", "W13.")
        self.assertNotIn("named after the other repo's folder", w12)
        self.assertIn("Manager", w12)


class TestDispatch(unittest.TestCase):

    def setUp(self):
        self.text = read("skills", "dispatch", "SKILL.md")

    def test_task_manager_session_gets_its_name(self):
        self.assertRegex(self.text, r"claude --name ['\"]<name> Task Manager['\"]")

    def test_the_orca_tab_gets_the_same_name(self):
        self.assertIn('--title "<name> Task Manager"', self.text)
        self.assertNotIn('"TM <name>"', self.text)

    def test_fast_lane_deputy_name(self):
        step2 = next(l for l in self.text.splitlines() if l.startswith("2. "))
        self.assertIn("<task> Deputy", step2)

    def test_worker_names_in_the_brief(self):
        brief = section(self.text, "## Task manager brief", "## Cross-repo brief")
        step4 = next(l for l in brief.splitlines() if l.startswith(" 4 "))
        self.assertIn("<name> Worker <n>: <slice>", step4)


class TestMerge(unittest.TestCase):

    def test_merge_deputy_name(self):
        text = read("skills", "merge", "SKILL.md")
        step4 = next(l for l in text.splitlines() if l.startswith("4. "))
        self.assertIn("<name> Merge", step4)


class TestCloseCase(unittest.TestCase):

    def test_sessions_are_found_by_name(self):
        text = section(read("skills", "close-case", "SKILL.md"), "## B.", "5.")
        self.assertTrue(re.search(r"<(feature|name)> Task Manager", text), text)
        self.assertIn("<repo> Helper", text)


if __name__ == "__main__":
    unittest.main()
