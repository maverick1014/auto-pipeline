"""Tests for 'close case'. The keyword hook is gone (owner 2026-11-24: human features
are skills only); the rule lives in skills/close-case/SKILL.md and PRINCIPLES.md W13.

CONTRACT. bin/agent-close-case.sh stays a UserPromptSubmit hook (hooks.json) for ONE
job: a session that was released or replaced as main manager is told once (see
tests/test_agent_main_seat.py, tests/test_agent_session_clean.py). A prompt that
contains the words "close case" prints nothing; the skill /auto-pipeline:close-case
carries the rules of every role (task manager, human-direct, main manager).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase

HOOK_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-close-case.sh'
HOOK_ENTRY = {"hooks": [{"type": "command", "command": HOOK_COMMAND, "timeout": 10}]}
MAX_BYTES = 1200
NOBODY = "999999"   # a CLAUDE_PID no lock ever names


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def dead_pid():
    """A pid that surely belongs to nobody now: a reaped child's."""
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


def section(text, start, end):
    """The text from the line starting with `start` up to the line starting with `end`."""
    lines = text.splitlines()
    begin = next(i for i, line in enumerate(lines) if line.startswith(start))
    stop = next(i for i in range(begin + 1, len(lines)) if lines[i].startswith(end))
    return "\n".join(lines[begin:stop])


def dispatch_brief():
    """The task manager brief template of the dispatch skill."""
    return section(read("skills", "dispatch", "SKILL.md"),
                   "## Task manager brief", "## Cross-repo brief")


class CloseCaseCase(ScriptCase):
    script = "agent-close-case.sh"

    def payload(self, prompt, cwd=None):
        return json.dumps({
            "session_id": "s-close",
            "transcript_path": "/tmp/none.jsonl",
            "cwd": cwd or self.repo.cwd,
            "permission_mode": "auto",
            "hook_event_name": "UserPromptSubmit",
            "prompt": prompt,
        })

    def set_lock(self, pid):
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%s 2026-09-28 10:00\n" % pid)

    def hook(self, prompt, env=None, stdin=None, cwd=None):
        """Run the hook; exit 0 and an empty stderr, always. Returns stdout."""
        result = self.repo.run("agent-close-case.sh", env=env or {},
                               stdin=self.payload(prompt, cwd) if stdin is None else stdin,
                               cwd=cwd)
        self.assertOk(result)
        self.assertEqual(result.stderr, "", result.stderr)
        return result.stdout


class TestNoKeywordHook(CloseCaseCase):
    def test_close_case_in_a_prompt_prints_nothing(self):
        for role_env in ({"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY},
                         {"CLAUDE_PID": str(os.getpid())}, {"CLAUDE_PID": NOBODY}):
            self.set_lock(os.getpid())
            for prompt in ("close case", "CLOSE CASE alpha: finished", "please close case now"):
                with self.subTest(env=role_env, prompt=prompt):
                    self.assertEqual(self.hook(prompt, env=role_env), "")

    def test_the_script_has_no_keyword_logic(self):
        text = read("bin", "agent-close-case.sh")
        self.assertNotIn("close\\s+case", text)
        self.assertNotIn("CLOSE CASE <", text)

    def test_empty_stdin_prints_nothing(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.hook("", env={"AGENT_ROLE": "task-manager"}, stdin=""), "")


class TestHooksJson(CloseCaseCase):
    def hooks(self):
        return json.loads(read("hooks", "hooks.json"))["hooks"]

    def test_user_prompt_submit_runs_it_once(self):
        self.assertEqual(self.hooks()["UserPromptSubmit"].count(HOOK_ENTRY), 1)

    def test_no_other_event_runs_it(self):
        for event, entries in self.hooks().items():
            if event != "UserPromptSubmit":
                with self.subTest(event=event):
                    self.assertNotIn("agent-close-case.sh", json.dumps(entries))

    def test_no_keyword_hooks_for_todo_and_question(self):
        text = json.dumps(self.hooks())
        for gone in ("agent-show-todo.sh", "agent-show-question.sh"):
            with self.subTest(script=gone):
                self.assertNotIn(gone, text)
                self.assertFalse(os.path.exists(os.path.join(ROOT, "bin", gone)))

    def test_the_skills_exist(self):
        for name in ("todo", "question", "close-case"):
            with self.subTest(skill=name):
                text = read("skills", name, "SKILL.md")
                self.assertRegex(text, r"(?m)^name: %s$" % name)


class TestOnePidHelper(unittest.TestCase):
    """agent-start.sh and the hook find "this session" the same way."""

    def test_agent_pid_lives_in_the_roots_helper(self):
        self.assertRegex(read("bin", "agent-roots.sh"), r"(?m)^agent_pid\(\)")

    def test_agent_start_no_longer_has_its_own_copy(self):
        self.assertNotRegex(read("bin", "agent-start.sh"), r"(?m)^agent_pid\(\)")

    def test_the_hook_uses_it(self):
        # through role_read (agent-roots.sh), which calls agent_pid: one copy
        # of the role logic, tests/test_agent_name.py
        text = read("bin", "agent-close-case.sh")
        self.assertIn("agent-roots.sh", text)
        self.assertIn("role_read", text)
        self.assertRegex(read("bin", "agent-roots.sh"),
                         r"(?ms)^role_read\(\).*?\$\(agent_pid\)")


class TestTheRule(unittest.TestCase):
    """PRINCIPLES.md W13, short lines, same style as the other rules."""

    def rule(self):
        return section(read("PRINCIPLES.md"), "W13. Close case", "W14.")

    def test_it_sits_after_w12_in_the_work_section(self):
        text = read("PRINCIPLES.md")
        self.assertLess(text.index("W12. Cross-repo"), text.index("W13. Close case"))
        self.assertLess(text.index("W13. Close case"), text.index("## C. Human"))

    def test_one_short_line_per_rule(self):
        bullets = [l for l in self.rule().splitlines() if l.startswith("- ")]
        self.assertGreaterEqual(len(bullets), 5)
        self.assertLessEqual(len(bullets), 14)   # session-clean: question, clean, release
        for line in bullets:
            with self.subTest(line=line[:40]):
                self.assertLessEqual(len(line), 200)

    def test_it_says_what_the_owner_decided(self):
        rule = self.rule()
        for phrase in ("close case", "/auto-pipeline:close-case",
                       "CLOSE CASE <name>: finished", "CLOSE CASE <name>: unfinished",
                       "WIP", "push", "next steps", "click path", "ideas", "TIME",
                       "finish first", "close now", "owner not seen", "whole repo",
                       "agent_worktree.txt", "table"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)

    def test_the_idea_rule_allows_ideas_in_the_close_case_report(self):
        w1 = section(read("PRINCIPLES.md"), "W1. ", "W2. ")
        self.assertIn("CLOSE CASE", w1)

    def test_the_quiz_still_has_twenty_nine_questions(self):
        text = read("bin", "agent-start.sh")
        # test-levels (2026-11-20): Q38 and Q39 (R8)
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", text)), 39)


class TestTheSkills(unittest.TestCase):
    def test_the_close_case_skill(self):
        text = read("skills", "close-case", "SKILL.md")
        self.assertRegex(text, r"(?m)^name: close-case$")
        self.assertRegex(text, r"(?m)^description: Run when the human or the main manager says close case")
        for phrase in ("finish first", "close now", "owner not seen", "agent_worktree.txt",
                       "${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree rm",
                       "${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add",
                       "${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh close",
                       "CronDelete", "/merge", "final table",
                       "agent_state.txt"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_close_now_keeps_the_branch(self):
        self.assertNotIn("--delete", read("skills", "close-case", "SKILL.md"))

    def test_the_merge_skill_points_at_it(self):
        text = read("skills", "merge", "SKILL.md")
        self.assertIn("CLOSE CASE", text)
        self.assertIn("/close-case", text)

    def test_the_task_manager_brief_mentions_it(self):
        brief = dispatch_brief()
        self.assertIn("close case", brief.lower())
        self.assertIn("CLOSE CASE <name>: finished", brief)
        self.assertIn("CLOSE CASE <name>: unfinished", brief)

    def test_the_readme_names_the_hook_and_the_skill(self):
        text = read("PRINCIPLES.md")
        self.assertIn("agent-close-case.sh", text)
        self.assertIn("close-case", text)


class TestTheBriefIsQuiet(CloseCaseCase):
    """The dispatch brief explains 'close case' but never fires anything."""

    def test_the_brief_itself_prints_nothing(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.hook(dispatch_brief(), env={"AGENT_ROLE": "task-manager",
                                                          "CLAUDE_PID": NOBODY}), "")


if __name__ == "__main__":
    unittest.main()
