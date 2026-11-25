"""Tests of bin/agent-close-case.sh: the prompt hook stays quiet; hooks.json and the skills name it.

One class per feature. Older task contracts: git log -p of this file.
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


from sharedrepo import REPO_BASE, shared_fixture  # noqa: E402


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


@shared_fixture(guard=REPO_BASE, remember_repo=True)   # one repo per class, each run once; the tests only read
class TestNoKeywordHook(CloseCaseCase):
    def test_the_script_has_no_keyword_logic(self):
        text = read("bin", "agent-close-case.sh")
        self.assertNotIn("close\\s+case", text)
        self.assertNotIn("CLOSE CASE <", text)


class TestNoKeywordHookLock(CloseCaseCase):
    """Writes the lock, so it has its own repo (no shared fixture)."""

    def test_close_case_in_a_prompt_prints_nothing(self):
        for role_env in ({"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY},
                         {"CLAUDE_PID": str(os.getpid())}, {"CLAUDE_PID": NOBODY}):
            self.set_lock(os.getpid())
            for prompt in ("close case", "CLOSE CASE alpha: finished", "please close case now"):
                with self.subTest(env=role_env, prompt=prompt):
                    self.assertEqual(self.hook(prompt, env=role_env), "")

    def test_empty_stdin_prints_nothing(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.hook("", env={"AGENT_ROLE": "task-manager"}, stdin=""), "")


class TestHooksJson(unittest.TestCase):   # reads hooks.json and skills only: no repo
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


class TestTheBriefIsQuiet(CloseCaseCase):
    """The dispatch brief explains 'close case' but never fires anything."""

    def test_the_brief_itself_prints_nothing(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.hook(dispatch_brief(), env={"AGENT_ROLE": "task-manager",
                                                          "CLAUDE_PID": NOBODY}), "")


if __name__ == "__main__":
    unittest.main()
