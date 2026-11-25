"""settings-configure: every script reads the 16 settings from Configure, nothing reads agent.conf.

Written by the task manager before any code (requirements/settings-configure.md).
Core contract: tests/test_settings_configure.py. This file: the readers and the texts.

CONTRACT
  1. No file under bin/ (except bin/agent_conf.py, which reads the old files only to
     move them), hooks/, skills/, agents/ names agent.conf, auto-pipeline.conf,
     agent.conf.default, AUTO_PIPELINE_USER_CONF (level3_paths / level4_paths are allowed again:
     owner 1A 2026-11-25, they live in the repo's agent_repo.conf) or
     board_guard, or calls `agent_conf.py effective`. bin/agent.conf.default is gone.
  2. agent-settings.sh:  (no args) or show -> the agent_conf.py show table, exit 0
                         get <key>          -> "<value> (from Configure|env|default|constant)"
                         statusline ...     -> as before (not a setting)
                         anything else      -> exit 1, one line naming
                                               /plugin -> Installed -> auto-pipeline -> Configure;
                                               nothing is written
  3. agent-start.sh: a repo is set up when agent_todo.txt (or an old agent.conf) is in it;
     it never creates agent.conf. Start text: "LANGUAGE: <language>." and
     "PERMISSION: <mode> (from Configure|default)" from Configure; one
     "SETTINGS: ..." line per bad stored value (agent_conf.warnings); the
     agent_conf.migrate lines when an old file is there; the agent_update.py sync lines
     (all roles); no "AUTO UPDATE: not set" and no "USER CONF:" line. The quiz never names
     agent.conf or auto-pipeline.conf.
  4. agent-init.sh: asks nothing, writes no agent.conf and no user file; creates the four
     task files; prints the migrate and sync lines and one line
     "settings: /plugin -> Installed -> auto-pipeline -> Configure".
  5. The launch guard: Configure todo_before_agent true (default) refuses a main manager
     launch naming no open todo task; false records only.
  6. Texts: PRINCIPLES.md names agent.conf and auto-pipeline.conf nowhere and has the
     principle "settings live only in /plugin -> Installed -> auto-pipeline -> Configure";
     README.md has one line with that path; skills/settings says the skill never changes
     a setting; skills/init asks no setting.
"""

import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase  # noqa: E402

CHANGE = "/plugin -> Installed -> auto-pipeline -> Configure"
OLD_WORDS = ("agent.conf", "auto-pipeline.conf", "AUTO_PIPELINE_USER_CONF",
             "board_guard", "agent_conf.py effective", "danger_paths")


class StartCase(ScriptCase):
    script = "agent-start.sh"

    def start(self, *args, **kwargs):
        return self.repo.run("agent-start.sh", *args, **kwargs)

    def installed(self, entries):
        folder = os.path.join(self.repo.claude_dir(), "plugins")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "installed_plugins.json"), "w") as fh:
            json.dump({"version": 2, "plugins": {"auto-pipeline@auto-pipeline": entries}}, fh)


class TestStart(StartCase):
    def test_a_repo_with_task_files_and_no_agent_conf_is_set_up(self):
        out = self.assertOk(self.start())
        self.assertNotIn("not set up", out)
        self.assertIn("LANGUAGE: en", out)
        self.assertFalse(os.path.exists(self.repo.path("agent.conf")))

    def test_language_and_permission_come_from_configure(self):
        self.repo.set_conf("language", "zh")
        self.repo.set_conf("permission_mode", "bypassPermissions")
        out = self.assertOk(self.start())
        self.assertIn("LANGUAGE: zh", out)
        self.assertIn("PERMISSION: bypassPermissions (from Configure)", out)

    def test_an_old_user_file_does_not_decide_the_mode(self):
        self.repo.set_user_conf("permission_mode=bypassPermissions\n")
        out = self.assertOk(self.start())
        perm = [l for l in self.lines(out) if l.startswith("PERMISSION:")]
        self.assertEqual(len(perm), 1, out)
        self.assertNotIn("auto-pipeline.conf", perm[0])

    def test_no_old_settings_lines(self):
        out = self.assertOk(self.start())
        self.assertNotIn("AUTO UPDATE: not set", out)
        self.assertNotIn("USER CONF:", out)
        self.assertNotIn("agent.conf", out)

    def test_a_bad_stored_value_is_said(self):
        self.repo.set_conf("max_agents", 99)
        out = self.assertOk(self.start())
        self.assertTrue([l for l in self.lines(out) if l.startswith("SETTINGS:") and "max_agents=99" in l], out)

    def test_an_old_agent_conf_is_moved_once(self):
        self.repo.set_old_conf("language=zh\nmax_agents=6\n")
        out = self.assertOk(self.start())
        self.assertIn("moved language=zh from", out)
        calls = [c for c in self.repo.claude_calls() if c["args"][:2] == ["plugin", "configure"]]
        self.assertEqual(len(calls), 1, self.repo.claude_calls())
        out2 = self.assertOk(self.start())
        self.assertNotIn("moved language=zh", out2)

    def test_the_moved_values_count_in_the_same_start(self):
        # E2E 2026-11-25: the start that moves an old file already runs on the moved values.
        # The fixture's claude stub only logs, so stand in for Claude Code's own write.
        self.repo.set_old_conf("language=zh\n")
        self.repo.stub_tool("claude", "#!%s\nimport json, os, sys\n"
                            "data = sys.stdin.read()\n"
                            "p = os.path.join(os.environ['CLAUDE_CONFIG_DIR'], 'settings.json')\n"
                            "os.makedirs(os.path.dirname(p), exist_ok=True)\n"
                            "d = json.load(open(p)) if os.path.exists(p) else {}\n"
                            "d.setdefault('pluginConfigs', {}).setdefault(sys.argv[3], {}).setdefault('options', {})"
                            ".update(json.loads(data) if data else {})\n"
                            "json.dump(d, open(p, 'w'))\n" % sys.executable)
        out = self.assertOk(self.start())
        self.assertIn("moved language=zh from", out)
        self.assertIn("LANGUAGE: zh", out)

    def test_a_stale_scope_of_this_folder_is_updated(self):
        here = os.path.realpath(self.repo.dir)
        self.installed([{"scope": "user", "version": "0.44.0"},
                        {"scope": "project", "projectPath": here, "version": "0.43.0"}])
        out = self.assertOk(self.start())
        self.assertIn("updated project %s: 0.43.0 -> 0.44.0, restart to apply" % here, out)
        calls = [c for c in self.repo.claude_calls() if c["args"][:2] == ["plugin", "update"]]
        self.assertEqual(len(calls), 1)
        self.assertNotIn("OLD PLUGIN:", out)

    def test_the_quiz_never_names_an_old_settings_file(self):
        out = self.assertOk(self.start("--quiz"))
        self.assertNotIn("agent.conf", out)
        self.assertNotIn("auto-pipeline.conf", out)

    def test_take_over_in_a_set_up_repo_is_not_refused_as_not_set_up(self):
        r = self.start("--release")
        self.assertNotIn("not set up", r.stdout + r.stderr)


class TestInit(ScriptCase):
    script = "agent-init.sh"

    def init(self, *args):
        return self.repo.run("agent-init.sh", self.repo.dir, *args, stdin="")

    def test_init_writes_no_settings_file_and_asks_nothing(self):
        for name in ("agent_todo.txt", "agent_completed.txt", "agent_ideas.txt", "agent_worktree.txt"):
            path = self.repo.path(name)
            if os.path.exists(path):
                os.remove(path)
        r = self.init()
        self.assertOk(r)
        self.assertFalse(os.path.exists(self.repo.path("agent.conf")))
        self.assertFalse(os.path.exists(self.repo.user_conf))
        self.assertFalse(os.path.exists(os.path.join(self.repo.claude_dir(), "settings.json")))
        for name in ("agent_todo.txt", "agent_completed.txt", "agent_ideas.txt", "agent_worktree.txt"):
            self.assertTrue(os.path.exists(self.repo.path(name)), name)
        self.assertNotIn("?", "\n".join(l for l in r.stdout.splitlines() if "auto_update" in l or "language" in l.lower()))
        self.assertIn("settings: " + CHANGE, r.stdout)

    def test_init_moves_an_old_agent_conf(self):
        self.repo.set_old_conf("language=zh\n")
        r = self.init()
        self.assertOk(r)
        self.assertIn("moved language=zh from", r.stdout)


if __name__ == "__main__":
    unittest.main()
