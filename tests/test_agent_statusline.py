"""Failing tests for the progress-bar status line. Written by the task manager first.

Owner, 2026-11-11: the progress of every running task shows in the Claude Code
status line too (the board and the watch: tests/test_agent_progress.py, which
also holds the stages, weights, bar and done-by rules used here).

CONTRACT

    bin/agent-statusline.sh   the statusLine command of Claude Code
        Reads the session JSON on stdin: workspace.current_dir, else cwd; stdin
        empty or not JSON -> $PWD. Prints one line, or nothing at all. Always
        exit 0, never an error text on stdout.
        The repo = the main worktree (git) of that folder; its agent.conf gives
        the language and the stage weights; AGENT_FAKE_NOW replaces the clock.
        The folder is the main repo -> every open todo line that has a stage,
            in agent_todo.txt order.
        Another worktree -> its own task only, found like `board --self`: its
            todo line (name = the folder name), else the TODO LINE: of its own
            agent_state.txt; the stage from the line, else its STAGE line.
        One line per task (statusline-vertical, 2026-11-12): name, bar,
            percent, stage, done by; the columns, the 5-line limit and the
            "+N" line: tests/test_statusline_vertical.py.
        No task with a stage, no agent.conf, not a git repo -> nothing.
        Fast: it refreshes often; one run takes well under 2 seconds.

    agent-settings.sh statusline on|off|refresh   (works with no agent.conf)
        The file: $CLAUDE_CONFIG_DIR/settings.json, else $HOME/.claude/settings.json.
        Ours = a statusLine whose command holds "/bin/agent-statusline.sh".
        on   no statusLine -> statusLine = {"type": "command",
                 "command": "\\"<plugin root>/bin/agent-statusline.sh\\"",
                 "refreshInterval": <statusline_refresh_sec>}; every
                 other key kept; the file and its folder made when missing
             ours -> pointed at this plugin root
             not ours -> refused: exit 1, one stderr line that says it is not
                 ours and stays as it is; the file byte for byte the same
        off  ours -> the statusLine key goes, every other key kept
             none -> exit 0, nothing changes
             not ours -> refused (exit 1, one stderr line), the file the same
        refresh  ours, pointing at another plugin root -> pointed at this one;
             anything else -> nothing changes; exit 0 always
        A file that is not valid JSON: on and off refused (exit 1), refresh
        exit 0; the file stays the same.
    agent-start.sh, at a main manager start, runs the refresh: after a plugin
        update an installed status line follows the new plugin folder.
"""

import json
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_agent_board as tb  # noqa: E402  (the module only)
from scripthelp import ScriptCase  # noqa: E402

NOW = tb.NOW   # "2026-11-02 15:00"


class LineCase(tb.BoardCase):
    script = "agent-statusline.sh"
    lang = "zh"

    def line(self, folder, cwd=None, stdin=None, now=NOW, ok=True):
        if stdin is None:
            stdin = json.dumps({"session_id": "s1", "cwd": folder,
                                "workspace": {"current_dir": folder, "project_dir": folder},
                                "model": {"id": "claude-opus-5-5", "display_name": "Opus 5.5"}})
        result = self.repo.run("agent-statusline.sh", cwd=cwd or self.repo.base, stdin=stdin,
                               env={"AGENT_FAKE_NOW": now}, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.rstrip("\n")

    def stage(self, name, *args, now=NOW, cwd=None):
        self.af("todo", "stage", name, *args, now=now, cwd=cwd)


class TestStatusLine(LineCase):
    def test_the_main_repo_shows_every_task_with_a_stage(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.add("gamma", "no stage yet", 60)
        self.add("beta", "bank recon match", 40, opened="2026-11-02 14:00")
        self.stage("beta", "workers", "1/2")
        self.assertEqual(self.line(self.repo.dir), "\n".join([
            "alpha                     ██████░░░░  66%  验证        16:00",
            "beta                      ████░░░░░░  46%  写代码 1/2  16:11"]))

    def test_a_worktree_shows_its_own_task_only(self):
        alpha = self.task_worktree("alpha")
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.add("beta", "bank recon match", 40, opened="2026-11-02 14:00")
        self.stage("beta", "workers", "1/2")
        self.assertEqual(self.line(alpha), "alpha                     ██████░░░░  66%  验证  16:00")
        sub = os.path.join(alpha, "sub")
        os.mkdir(sub)
        self.assertEqual(self.line(sub), "alpha                     ██████░░░░  66%  验证  16:00")

    def test_a_task_manager_on_another_machine_reads_its_own_state(self):
        alpha = self.task_worktree("alpha")
        self.state("TODO LINE: alpha | big | the login form | est 60m | opened 2026-11-02 14:30 | by main\n",
                   folder=alpha)
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:50", cwd=alpha)
        self.assertEqual(self.line(alpha), "alpha                     ████░░░░░░  46%  写代码 1/2  15:30")

    def test_no_done_by_is_left_out(self):
        self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
        self.stage("alpha", "brief")
        self.assertEqual(self.line(self.repo.dir), "alpha                     ░░░░░░░░░░   0%  简报")

    def test_nothing_with_a_stage_prints_nothing(self):
        self.assertEqual(self.line(self.repo.dir), "")
        self.add("alpha", "the login form", 60)
        self.assertEqual(self.line(self.repo.dir), "")

    def test_not_a_repo_prints_nothing(self):
        plain = self.repo.make_project("plain")
        self.assertEqual(self.line(plain), "")

    def test_bad_stdin_reads_the_working_folder(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.assertEqual(self.line(None, cwd=self.repo.dir, stdin="not json"),
                         "alpha                     ██████░░░░  66%  验证  16:00")
        self.assertEqual(self.line(None, cwd=self.repo.dir, stdin=""),
                         "alpha                     ██████░░░░  66%  验证  16:00")

    def test_it_is_fast(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        start = time.time()
        self.line(self.repo.dir)
        self.assertLess(time.time() - start, 2.0)


class TestStatusLineEnglish(LineCase):
    lang = "en"

    def test_tomorrow_and_over(self):
        self.add("night", "finishes after midnight", 30, opened="2026-11-02 22:30")
        self.stage("night", "verify", now="2026-11-02 23:30")
        self.assertEqual(self.line(self.repo.dir, now="2026-11-02 23:30"),
                         "night                     ██████░░░░  66%  verify  00:01 tomorrow")


# ---------------------------------------------------------------- install


OURS_OLD = '"/old/plugin/0.29.0/bin/agent-statusline.sh"'
FOREIGN = {"type": "command", "command": "~/.claude/buddy/statusline.sh"}


class InstallCase(ScriptCase):
    script = "agent-settings.sh"

    def setUp(self):
        super().setUp()
        self.home = self.repo.fake_home()
        self.settings = os.path.join(self.home, ".claude", "settings.json")
        self.ours = {"type": "command",
                     "command": '"%s/bin/agent-statusline.sh"' % self.repo.plugin,
                     "refreshInterval": 60}

    def write(self, data=None, raw=None):
        os.makedirs(os.path.dirname(self.settings), exist_ok=True)
        with open(self.settings, "w") as fh:
            fh.write(raw if raw is not None else json.dumps(data, indent=2) + "\n")

    def raw(self):
        with open(self.settings, "rb") as fh:
            return fh.read()

    def load(self):
        with open(self.settings) as fh:
            return json.load(fh)

    def run_settings(self, *args, env=None):
        return self.repo.run("agent-settings.sh", "statusline", *args, env=env, timeout=30)

    def refused(self, *args):
        before = self.raw()
        result = self.run_settings(*args)
        self.assertEqual(result.returncode, 1, (result.stdout, result.stderr))
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
        self.assertEqual(self.raw(), before)
        return result


class TestInstall(InstallCase):
    def test_on_writes_ours_and_keeps_the_rest(self):
        self.write({"theme": "dark", "model": "opus", "hooks": {"Stop": []}})
        self.assertOk(self.run_settings("on"))
        data = self.load()
        self.assertEqual(data["statusLine"], self.ours)
        self.assertEqual((data["theme"], data["model"], data["hooks"]), ("dark", "opus", {"Stop": []}))

    def test_on_makes_the_file(self):
        self.assertFalse(os.path.exists(os.path.dirname(self.settings)))
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load(), {"statusLine": self.ours})

    def test_on_refuses_a_status_line_that_is_not_ours(self):
        self.write({"statusLine": FOREIGN, "theme": "dark"})
        result = self.refused("on")
        self.assertIn("not ours", result.stderr)

    def test_on_again_points_ours_at_this_plugin(self):
        self.write({"statusLine": {"type": "command", "command": OURS_OLD}})
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load()["statusLine"], self.ours)

    def test_off_takes_ours_away_only(self):
        self.write({"statusLine": self.ours, "theme": "dark"})
        self.assertOk(self.run_settings("off"))
        self.assertEqual(self.load(), {"theme": "dark"})

    def test_off_refuses_a_status_line_that_is_not_ours(self):
        self.write({"statusLine": FOREIGN})
        self.refused("off")

    def test_off_with_none_changes_nothing(self):
        self.write({"theme": "dark"})
        before = self.raw()
        self.assertOk(self.run_settings("off"))
        self.assertEqual(self.raw(), before)

    def test_refresh(self):
        self.write({"statusLine": {"type": "command", "command": OURS_OLD}, "theme": "dark"})
        self.assertOk(self.run_settings("refresh"))
        self.assertEqual(self.load(), {"statusLine": self.ours, "theme": "dark"})
        for data in ({"statusLine": FOREIGN}, {"theme": "dark"}):
            with self.subTest(data=data):
                self.write(data)
                before = self.raw()
                self.assertOk(self.run_settings("refresh"))
                self.assertEqual(self.raw(), before)

    def test_refresh_with_no_file_makes_none(self):
        self.assertOk(self.run_settings("refresh"))
        self.assertFalse(os.path.exists(self.settings))

    def test_not_json(self):
        self.write(raw="{ not json\n")
        self.refused("on")
        self.refused("off")
        before = self.raw()
        self.assertOk(self.run_settings("refresh"))
        self.assertEqual(self.raw(), before)

    def test_an_unknown_word_is_refused(self):
        self.write({"theme": "dark"})
        before = self.raw()
        result = self.run_settings("maybe")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.raw(), before)

    def test_claude_config_dir_wins(self):
        cfg = os.path.join(self.repo.base, "cfg")
        self.assertOk(self.run_settings("on", env={"CLAUDE_CONFIG_DIR": cfg}))
        with open(os.path.join(cfg, "settings.json")) as fh:
            self.assertEqual(json.load(fh), {"statusLine": self.ours})
        self.assertFalse(os.path.exists(self.settings))

    def test_no_agent_conf_needed(self):
        os.remove(self.repo.path("agent.conf"))
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load()["statusLine"], self.ours)

    def test_the_installed_command_runs(self):
        self.assertOk(self.run_settings("on"))
        command = self.load()["statusLine"]["command"]
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add", "alpha", "big", "the login form", "60",
                                    env={"AGENT_FAKE_NOW": "2026-11-02 14:00"}))
        self.assertOk(self.repo.run("agent-file.sh", "todo", "stage", "alpha", "verify",
                                    env={"AGENT_FAKE_NOW": "2026-11-02 14:30"}))
        stdin = json.dumps({"cwd": self.repo.dir, "workspace": {"current_dir": self.repo.dir}})
        env = self.repo._env({"AGENT_FAKE_NOW": "2026-11-02 15:00"})
        result = subprocess.run(["/bin/sh", "-c", command], input=stdin, capture_output=True,
                                text=True, env=env, cwd=self.repo.base, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        # verify since 14:30, est 60: 30 minutes in a 9-minute share -> stops at 80%
        self.assertRegex(result.stdout, r"^alpha +████████░░  80%  ")


class TestInstallWords(InstallCase):
    """Bounce 1 (task manager, 2026-11-11): a human runs on and off, so a success
    says one line on stdout that names the file (on: "statusline on: <file>",
    off: "statusline off: <file>"); refresh stays silent. Text that is not ASCII
    in settings.json stays as it was written (no \\u escapes)."""

    def test_on_and_off_say_one_line(self):
        self.write({"theme": "dark"})
        out = self.assertOk(self.run_settings("on"))
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        self.assertIn("statusline on", out)
        self.assertIn(self.settings, out)
        out = self.assertOk(self.run_settings("off"))
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        self.assertIn("statusline off", out)
        self.assertIn(self.settings, out)

    def test_refresh_is_silent(self):
        self.write({"statusLine": {"type": "command", "command": OURS_OLD}})
        result = self.run_settings("refresh")
        self.assertOk(result)
        self.assertEqual(result.stdout + result.stderr, "")

    def test_text_that_is_not_ascii_stays(self):
        self.write(raw='{\n  "note": "中文 设置"\n}\n')
        self.assertOk(self.run_settings("on"))
        text = self.raw().decode("utf-8")
        self.assertIn('"note": "中文 设置"', text)
        self.assertNotIn("\\u", text)
        self.assertOk(self.run_settings("off"))
        self.assertIn('"note": "中文 设置"', self.raw().decode("utf-8"))


class TestStartRefreshes(InstallCase):
    def test_a_main_manager_start_points_ours_at_this_plugin(self):
        self.write({"statusLine": {"type": "command", "command": OURS_OLD}, "theme": "dark"})
        self.assertOk(self.repo.run("agent-start.sh"))
        self.assertEqual(self.load(), {"statusLine": self.ours, "theme": "dark"})

    def test_a_start_never_touches_a_status_line_that_is_not_ours(self):
        self.write({"statusLine": FOREIGN})
        before = self.raw()
        self.assertOk(self.repo.run("agent-start.sh"))
        self.assertEqual(self.raw(), before)


if __name__ == "__main__":
    unittest.main()
