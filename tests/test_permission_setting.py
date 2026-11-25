"""The permission mode of a new terminal comes from Configure (settings-configure, 2026-11-25).

Replaces personal-mode (2026-11-04: the machine file ~/.claude/auto-pipeline.conf won
over agent.conf). Both files are gone as sources: the "Permissions: Permission mode"
setting is user level already, so it is the machine's own value.

CONTRACT
1. bin/agent_city.py agent_command(name, folder, city_dir=None): --model/--effort from
   the Main manager model setting, --permission-mode from the Permission mode setting
   (default auto, always given). An old agent.conf or user file decides nothing. Never
   raises.
2. bin/agent-resume.sh: --permission-mode <the setting>.
3. Start text, every role: exactly one line "PERMISSION: <the agent-settings.sh get
   permission_mode output>", e.g. "PERMISSION: bypassPermissions (from default)" (owner order
   2026-11-25: the default is bypassPermissions, as since 2026-11-04),
   "PERMISSION: acceptEdits (from Configure)". No "USER CONF:" line ever.
4. skills/dispatch/SKILL.md and PRINCIPLES.md W10 take <mode> from
   `agent-settings.sh get permission_mode`; W10's "- New terminals" line names the
   Permission mode setting and no file.
"""

import json
import os
import shlex
import sys
import tempfile
import shutil
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


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
        from test_output_hook import pointer_part
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


if __name__ == "__main__":
    unittest.main()
