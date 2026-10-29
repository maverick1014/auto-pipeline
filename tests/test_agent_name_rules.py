"""Failing tests for the naming rule text. Written by the task manager first.

Owner, 2026-09-30: sessions are named by role (see tests/test_agent_name.py
for the hook). The rules and skills must use the same names, because the name
is the SendMessage address.

CONTRACT.

  PRINCIPLES.md
    - one short naming rule, a single line (at most 320 characters) that
      names every role: `<repo> Manager`, `<feature> Task Manager`,
      `<repo> Helper`, `<feature> Worker <n>`, a `Deputy` and a `Merge`
      name, and says the SessionStart hook bin/agent-name.sh shows the first
      three, and that the SendMessage address follows only after
      `claude --name`, `/rename` or a resume (live check, see
      tests/test_agent_name.py)
    - the "Talk between sessions" line (W10) says what to do when two
      sessions share a name (add the [ref] ListAgents prints) and when the
      name is not listed (the row named after its folder, `<folder>-<xx>`)
    - the W10 line that opens a second session names it: --name '<repo> Helper'
    - W12 finds the peer by `<repo> Manager`, or its `-<xx>` folder row, no
      longer "named after the other repo's folder"

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
      or its folder row "<repo>-<xx>"

  Helper task (owner, 2026-10-28; the hook and the command are in
  tests/test_agent_name.py):
    - the PRINCIPLES naming line shows the Helper as `<repo> Helper - <Task Name>`
    - exactly one PRINCIPLES line names `helper-task "<Task Name>"`: when (a new
      or switched task, a plain question too, even before the quiz PASS;
      E2E 2026-10-29), the words (2-4 English words, Title Case, the work,
      not the role), how (the exact full-path command, alone, from the project
      folder, never cd, never chain it; E2E 2026-10-29), and that the name
      shows from the human's next prompt. At most 400 characters
    - the close-case skill finds the Helper as `<repo> Helper - <Task Name>`
    - the closed-session hint (bin/agent-roots.sh) gives the /rename with the
      task too: `/rename <repo> Helper - <Task Name>`
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

    def test_the_rule_shows_the_helper_task(self):
        self.assertIn("<repo> Helper - <Task Name>", self.naming_lines()[0])

    def test_one_helper_task_rule(self):
        lines = [l for l in self.text.splitlines() if "helper-task" in l]
        self.assertEqual(len(lines), 1, lines)
        line = lines[0]
        for word in ('helper-task "<Task Name>"', "<repo> Helper - <Task Name>",
                     "2-4 English words", "Title Case",
                     "next prompt", "the work, not the role", "full-path", "alone",
                     "project folder", "never cd", "never chain",
                     "a plain question too", "before the quiz PASS"):
            with self.subTest(word=word):
                self.assertIn(word, line)
        self.assertLessEqual(len(line), 400)

    def test_the_rule_says_when_the_name_is_the_address(self):
        line = self.naming_lines()[0]
        for word in ("--name", "/rename", "resume"):
            with self.subTest(word=word):
                self.assertIn(word, line)

    def talk_line(self):
        return next(l for l in self.text.splitlines()
                    if l.startswith("- Talk between sessions"))

    def test_talk_between_sessions_handles_a_shared_name(self):
        self.assertIn("[ref]", self.talk_line())

    def test_talk_between_sessions_falls_back_to_the_folder_row(self):
        self.assertIn("<folder>-<xx>", self.talk_line())

    def test_the_second_session_is_opened_with_its_name(self):
        line = next(l for l in self.text.splitlines()
                    if l.startswith("- Open a second session"))
        self.assertIn("--name '<repo> Helper'", line)

    def test_cross_repo_peer_is_found_by_manager_name(self):
        w12 = section(self.text, "W12.", "W13.")
        self.assertNotIn("named after the other repo's folder", w12)
        self.assertIn("Manager", w12)
        self.assertIn("-<xx>", w12)


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
        self.assertIn("<repo>-<xx>", text)

    def test_the_helper_is_found_by_its_task_name(self):
        text = section(read("skills", "close-case", "SKILL.md"), "## B.", "5.")
        self.assertIn("<repo> Helper - <Task Name>", text)


class TestNoOldHelperFormat(unittest.TestCase):
    """Owner change, 2026-10-29: "<repo> Helper - <Task Name>". The old form
    "<repo> Helper <Task Name>" is gone from every rule text and script."""

    FILES = (("PRINCIPLES.md",), ("README.md",), ("skills", "close-case", "SKILL.md"),
             ("bin", "agent-start.sh"), ("bin", "agent-roots.sh"),
             ("bin", "agent-file.sh"), ("bin", "agent-name.sh"))

    def test_no_old_form_left(self):
        for parts in self.FILES:
            with self.subTest(file="/".join(parts)):
                self.assertNotIn("Helper <Task Name>", read(*parts))


class TestClosedHint(unittest.TestCase):

    def test_the_rename_hint_gives_the_task_form(self):
        line = next(l for l in read("bin", "agent-roots.sh").splitlines()
                    if "ask the human once to type /rename" in l)
        self.assertIn("Helper - <Task Name>", line)


if __name__ == "__main__":
    unittest.main()
