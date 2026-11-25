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


class TestCityCommand(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="permission_setting_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.cfg = os.path.join(self.base, "cfg")
        os.makedirs(self.cfg)
        self.folder = os.path.join(self.base, "shop")
        os.makedirs(self.folder)
        patcher = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": self.cfg,
                                               "AUTO_PIPELINE_USER_CONF": os.path.join(self.base, "u.conf")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def configure(self, **options):
        with open(os.path.join(self.cfg, "settings.json"), "w") as fh:
            json.dump({"pluginConfigs": {"auto-pipeline@auto-pipeline": {"options": options}}}, fh)

    def words(self):
        return shlex.split(ac.agent_command("shop Manager", self.folder))

    def mode(self):
        words = self.words()
        return words[words.index("--permission-mode") + 1] if "--permission-mode" in words else None

    def test_nothing_set_is_bypass(self):
        self.assertEqual(self.mode(), "bypassPermissions")

    def test_the_setting_wins(self):
        self.configure(permission_mode="bypassPermissions")
        self.assertEqual(self.mode(), "bypassPermissions")

    def test_a_refused_value_falls_back_to_the_default(self):
        self.configure(permission_mode="$(touch pwned)")
        self.assertEqual(self.mode(), "bypassPermissions")
        self.assertFalse(os.path.exists(os.path.join(self.folder, "pwned")))

    def test_old_files_decide_nothing(self):
        with open(os.path.join(self.folder, "agent.conf"), "w") as fh:
            fh.write("main_manager=opus-5.5:xhigh\npermission_mode=plan\n")
        with open(os.environ["AUTO_PIPELINE_USER_CONF"], "w") as fh:
            fh.write("permission_mode=acceptEdits\n")
        self.assertEqual(self.mode(), "bypassPermissions")
        self.assertEqual(self.words()[self.words().index("--effort") + 1], "high")

    def test_the_whole_line(self):
        self.configure(permission_mode="bypassPermissions", main_manager="opus-5.5:xhigh")
        self.assertEqual(self.words(), ["claude", "--name", "shop Manager", "--model", "opus", "--effort", "xhigh",
                                        "--permission-mode", "bypassPermissions", ac.FIRST_PROMPT])

    def test_never_raises(self):
        with open(os.path.join(self.cfg, "settings.json"), "w") as fh:
            fh.write("{broken")
        self.assertEqual(self.mode(), "bypassPermissions")


class TestResume(ScriptCase):
    script = "agent-resume.sh"

    def command(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        self.repo.set_panes([])
        self.assertOk(self.repo.run("agent-resume.sh"))
        calls = self.repo.create_calls()
        self.assertEqual(len(calls), 1, calls)
        return calls[0][calls[0].index("--command") + 1]

    def test_the_setting(self):
        self.repo.set_conf("permission_mode", "acceptEdits")
        self.assertTrue(self.command().endswith("--permission-mode acceptEdits"))

    def test_an_old_user_file_decides_nothing(self):
        self.repo.set_user_conf("permission_mode=plan\n")
        self.assertTrue(self.command().endswith("--permission-mode bypassPermissions"))

    def test_nothing_set_is_bypass(self):
        self.assertTrue(self.command().endswith("--permission-mode bypassPermissions"))


class TestLaunchText(unittest.TestCase):
    def test_dispatch_reads_the_setting(self):
        text = read("skills", "dispatch", "SKILL.md")
        line = next(l for l in text.splitlines() if "**orca**" in l and "<mode>" in l)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-settings.sh get permission_mode", line)
        self.assertIn("--permission-mode <mode>", text)

    def test_w10_helper_line(self):
        line = next(l for l in read("PRINCIPLES.md").splitlines() if l.startswith("- Open a second session"))
        self.assertIn("agent-settings.sh get permission_mode", line)
        self.assertIn("--permission-mode <mode>", line)

    def test_w10_new_terminals_line(self):
        line = next(l for l in read("PRINCIPLES.md").splitlines() if l.startswith("- New terminals"))
        self.assertIn("Permission mode", line)
        self.assertNotIn(".conf", line)


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


if __name__ == "__main__":
    unittest.main()
