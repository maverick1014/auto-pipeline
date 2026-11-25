"""Failing tests for the progress-bar status line. Written by the task manager first.

Owner, 2026-11-11: the progress of every running task shows in the Claude Code
status line too (the board and the watch: tests/test_agent_board.py, TestProgressColumn, which
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
            "+N" line: VerticalCase below.
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
             board-waiting scope add (2026-11-20): only when this root (or
             CLAUDE_PLUGIN_ROOT) is under <config dir>/plugins/cache/; any other
             root leaves it (requirements/board-waiting.md F,
             RefreshCase below)
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

from scripthelp import ScriptCase  # noqa: E402
from test_agent_board import BoardCase, WaitCase  # noqa: E402
import shutil  # noqa: E402
import re  # noqa: E402
from scripthelp import ROOT  # noqa: E402

NOW = "2026-11-02 15:00"


class LineCase(BoardCase):
    script = "agent-statusline.sh"
    lang = "zh"

    def line(self, folder, cwd=None, stdin=None, now=NOW, ok=True, real=False):
        if stdin is None:
            stdin = json.dumps({"session_id": "s1", "cwd": folder,
                                "workspace": {"current_dir": folder, "project_dir": folder},
                                "model": {"id": "claude-opus-5-5", "display_name": "Opus 5.5"}})
        if real:   # test-slim-2: the real agent-statusline.sh start (the default runs agent_board.py in this process)
            result = self.repo.run("agent-statusline.sh", cwd=cwd or self.repo.base, stdin=stdin,
                                   env={"AGENT_FAKE_NOW": now}, timeout=20)
        else:
            result = self.statusline_py(stdin, env={"AGENT_FAKE_NOW": now}, cwd=cwd)
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
        self.line(self.repo.dir, real=True)
        self.assertLess(time.time() - start, 2.0)

    def test_the_wrapper_prints_what_the_in_process_run_prints(self):
        # the end-to-end start: agent-statusline.sh itself, against the same run in this process
        alpha = self.task_worktree("alpha")
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.add("beta", "bank recon match", 40, opened="2026-11-02 14:00")
        self.stage("beta", "workers", "1/2")
        for folder in (self.repo.dir, alpha):
            with self.subTest(folder=folder):
                real = self.line(folder, real=True)
                self.assertTrue(real)
                self.assertEqual(real, self.line(folder))


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
        # board-waiting scope add (2026-11-20): this plugin copy is not under the plugin cache, so refresh leaves
        # an ours statusLine as it is; the repoint from a cache root: RefreshCase below
        self.write({"statusLine": {"type": "command", "command": OURS_OLD}, "theme": "dark"})
        before = self.raw()
        self.assertOk(self.run_settings("refresh"))
        self.assertEqual(self.raw(), before)
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

    def test_no_task_file_needed(self):
        os.remove(self.repo.path("agent_todo.txt"))
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
    def test_a_main_manager_start_from_a_checkout_leaves_ours(self):
        # board-waiting scope add (2026-11-20): a start from a root that is not under the plugin cache never
        # repoints; a start from a cache root does: RefreshCase below
        self.write({"statusLine": {"type": "command", "command": OURS_OLD}, "theme": "dark"})
        self.assertOk(self.repo.run("agent-start.sh"))
        self.assertEqual(self.load()["statusLine"], {"type": "command", "command": OURS_OLD})

    def test_a_start_never_touches_a_status_line_that_is_not_ours(self):
        self.write({"statusLine": FOREIGN})
        before = self.raw()
        self.assertOk(self.repo.run("agent-start.sh"))
        self.assertEqual(self.raw(), before)


NOW_NOV20_1231 = "2026-11-20 12:31"


BW = ("board-waiting | big | Board waiting status | est 39m | guess 40m | level 3 | opened 2026-11-20 11:35 | "
      "by main | waiting queue since 2026-11-20 11:35 | after state-trim")


# pc2's real agent_todo.txt of 2026-11-20 (old lines: no who, no after, no started)
REAL = [
    "v4plus-followups | small | Cross-repo asks to the v4-plus Manager (owner 2A 4A 2026-11-16): update v4-plus "
    "project scope to plugin 0.34.1 + restart at a quiet point; consider the 15-min production sync as a plain "
    "script (agent only on failure); idle v4-plus-sync sessions pile up | est 5m | guess 5m | opened 2026-11-16 "
    "15:46 | by main | cross v4-plus | waiting hold since 2026-11-16 15:47: v4-Manager: not now, ledger rollout "
    "final suite + staging; update after owner confirms in its chat; sync script = later task for owner",
    "usage-track | big | Track tied repos (v4-plus first): housekeep prints a USAGE block per repo (plugin scope "
    "version, state file size, monitor alive, completed data gaps) at no agent cost, and flags the weekly deep "
    "audit as due (next 2026-11-23). Owner 3A 2026-11-16 | est 49m | guess 50m | opened 2026-11-16 17:31 | by "
    "main | waiting hold since 2026-11-16 17:31: owner close case 2026-11-16: after one-watcher",
    "pc2-plugin-update | small | Update auto-pipeline user-scope plugin on pc2 from 0.23.1 to 0.35.0 (owner "
    "2026-11-17) when no v4-plus task manager is working on pc2; running sessions keep their copy until restart | "
    "est 5m | guess 5m | opened 2026-11-17 17:21 | by main | on maverick-pc2 | cross v4-plus | waited 895m | "
    "waiting hold since 2026-11-18 08:16: handed to v4-Manager 2026-11-18 (owner); its todo, its quiet point",
    "one-watcher | big | One watcher for every task manager (agent-watch.sh --all, pane + remote state file, LOST "
    "on exited pane, no signature filter) + agent-file.sh tell with receipt; heartbeats to file only. Fix 3 of 3 "
    "from the v4-plus audit (ideas 123-125, 141-142). PLUS owner 2026-11-17: at main manager start or resume, "
    "rebuild every watch from agent_worktree.txt (today only agent-monitor.sh restarts) | est 114m | guess 135m | "
    "level 3 | opened 2026-11-18 08:16 | by main | waiting hold since 2026-11-18 08:16: owner close case "
    "2026-11-18: next round, run in order, one at a time on pc2",
    "owner-relay | big | OWNER ORDER relay between repo managers: sender prints the OWNER ORDER line (owner "
    "quote, repo, time); receiver runs one command that verifies the quote is a typed owner prompt in the "
    "sender's transcript (not peer, not meta, not tool_result, 24h, same machine); W12 rule + dispatch skill. "
    "Owner 3A 2026-11-20: after one-watcher. Rule text already in ~/.claude/CLAUDE.md | est 42m | guess 45m | "
    "level 3 | opened 2026-11-20 11:35 | by main",
    "comment-shape | small | agent-level.sh: a comment-only change becomes a fifth level 0 shape; R8 line + tests "
    "(owner 4A 2026-11-20, later; level 3 = full lane) | est 28m | guess 20m | level 3 | opened 2026-11-20 11:35 "
    "| by main",
]


OW, OR, CS = REAL[3], REAL[4], REAL[5]


# a running task opened long before every wait below (rule 5.0: its waits never fill the time from opened)
BASE = ("x | big | the task | est 60m | level 2 | opened 2026-11-10 09:00 | by main | "
        "started 2026-11-10 09:05 | stage tests since 2026-11-10 09:05")


def name_col(name):
    """A status line name: 24 columns, then two spaces (today's layout)."""
    return name + " " * (24 - len(name)) + "  "


class TestStatusLineWait(WaitCase):
    def running(self, n, first=1):
        return ["t%d | big | w | est 120m | opened 2026-11-20 12:%02d | by main | started 2026-11-20 12:%02d | "
                "stage tests since 2026-11-20 12:%02d" % (i, i, i, i) for i in range(first, first + n)]

    def test_9_5_more_than_five_lines_fold(self):
        self.put(*(self.running(7) + ["h | big | w | est 5m | opened 2026-11-20 10:00 | by main | "
                                      "waiting hold since 2026-11-20 11:00"]))
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual([l.split()[0] for l in lines[:4]], ["t1", "t2", "t3", "t4"])
        self.assertEqual(lines[4], "+4 排队/暂缓")

    def test_9_5_six_running_no_fold_rows(self):
        self.put(*self.running(6))
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual(lines[4], "+2 排队/暂缓")

    def test_9_6_five_lines_no_fold_line(self):
        self.put(*self.running(5))
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertNotIn("+", lines[4][:1])

    def test_9_6_nothing_prints_nothing(self):
        self.put()
        self.assertEqual(self.line(), "")

    def test_9_4_only_rows_that_fold(self):
        # one-watcher K (owner 2026-11-24): they fit, so each gets its own row, board order
        self.put(OR, CS, BW)
        self.assertEqual(self.line(), "\n".join([name_col("owner-relay") + "未开始", name_col("comment-shape") + "未开始",
                                                 name_col("board-waiting") + "排队 · 在 state-trim 之后"]))

    def test_9_7_helpers_workers_owner_todo_parked_are_not_counted(self):
        self.put(BW)
        self.state("OWNER TODO: check the phone build\n")
        self.af("park", "add", "which DB?", now=NOW_NOV20_1231)
        self.af("worker", "on", "1", "a slice", now=NOW_NOV20_1231)
        self.assertEqual(self.line(), name_col("board-waiting") + "排队 · 在 state-trim 之后")   # one-watcher K

    def test_owner_what_is_cut_to_24_columns(self):
        self.put(BASE + " | waiting mock since 2026-11-20 12:21: please check the rules table and the simulation")
        self.assertEqual(self.line(), name_col("x") + "等待 你 · please check the rules… · 已等 10分钟")

    def test_others_waits_drop_the_what(self):
        self.put(BASE + " | waiting review since 2026-11-20 12:01: plugin sign-off | who v4-Manager")
        self.assertEqual(self.line(), name_col("x") + "等待 v4-Manager · 已等 30分钟")

    def test_9_8_a_worktree_shows_its_own_row(self):
        alpha = self.task_worktree("alpha")
        self.put("alpha | big | w | est 60m | opened 2026-11-20 10:00 | by main | started 2026-11-20 10:00 | "
                 "stage mock since 2026-11-20 12:00 | waiting mock since 2026-11-20 12:21", BW)
        self.assertEqual(self.line(alpha), name_col("alpha") + "等待 你 · 确认样稿或规则表 · 已等 10分钟")
        self.put("alpha | big | w | est 60m | opened 2026-11-20 10:00 | by main | "
                 "waiting queue since 2026-11-20 11:00 | after state-trim")
        self.assertEqual(self.line(alpha), name_col("alpha") + "排队 · 在 state-trim 之后")   # one-watcher K6


ZH_WARN = "看板可能不准："


EN_WARN = "board may be wrong: "


def status_file(repo):
    return repo.path(".git", "agent_watch.json")


def write_watch(repo, pid=None, sweep=NOW, interval=5, tasks=None, orphans=()):
    data = {"pid": os.getpid() if pid is None else pid, "started": "2026-11-02 13:00", "sweep": sweep,
            "interval_min": interval, "tasks": tasks or {}, "orphans": list(orphans)}
    with open(status_file(repo), "w") as fh:
        json.dump(data, fh)


def task_entry(path, watched=True, why="", changed=None, confirmed=None, pane="term_x"):
    return {"path": path, "env": None, "pane": pane, "shell": None, "watched": watched, "why": why,
            "signals": 0, "confirmed": confirmed, "changed": changed, "stall": None}


def q(name, after=None, since="2026-11-20 11:00"):
    return "%s | big | w | est 30m | opened %s | by main | waiting queue since %s%s" % (
        name, since, since, " | after " + after if after else "")


def h(name, since="2026-11-20 12:01", note="later"):
    return "%s | big | w | est 30m | opened 2026-11-20 10:00 | by main | waiting hold since %s: %s" % (name, since, note)


def ns(name, opened="2026-11-20 11:35"):
    return "%s | big | w | est 30m | opened %s | by main" % (name, opened)


def run(name, minute):
    return ("%s | big | w | est 120m | opened 2026-11-20 12:%02d | by main | started 2026-11-20 12:%02d | "
            "stage tests since 2026-11-20 12:%02d" % (name, minute, minute, minute))




class StatusLineCase(LineCase):
    def setUp(self):
        super().setUp()
        self.alpha = self.repo.make_worktree("alpha", as_repo=False)
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.worktree_lines((self.alpha, "alpha", "working"))

    def first(self):
        return self.line(self.repo.dir).split("\n")[0]


class TestStatusLineWatch(StatusLineCase):
    def test_f6_no_live_watch_says_watch_not_running(self):
        self.assertEqual(self.first(), ZH_WARN + "看守未运行")

    def test_f6_unconfirmed_tasks_are_counted(self):
        beta = self.repo.make_worktree("beta", as_repo=False)
        self.add("beta", "bank recon", 40, opened="2026-11-02 14:00")
        self.stage("beta", "workers", "1/2")
        self.worktree_lines((self.alpha, "alpha", "working"), (beta, "beta", "working"))
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:30"),
                                      "beta": task_entry(beta, watched=False, why="no task manager pane")})
        self.assertEqual(self.first(), ZH_WARN + "2 个未确认")

    def test_f6_orphans_only(self):
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:58")},
                    orphans=[{"path": "/x/ghost", "title": "g", "handle": "term_g"}])
        self.assertEqual(self.first(), ZH_WARN + "有窗格无任务行")

    def test_f6_all_confirmed_has_no_warning_line(self):
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:58")})
        self.assertFalse(self.first().startswith(ZH_WARN), self.first())
        self.assertTrue(self.first().startswith("alpha "), self.first())

    def test_f6_the_warning_counts_in_the_5_line_limit(self):
        rows = [(self.alpha, "alpha", "working")]
        for name in ("b1", "b2", "b3", "b4", "b5"):
            path = self.repo.make_worktree(name, as_repo=False)
            self.add(name, "task " + name, 60, opened="2026-11-02 14:00")
            self.stage(name, "tests")
            rows.append((path, name, "working"))
        self.worktree_lines(*rows)
        lines = self.line(self.repo.dir).split("\n")
        self.assertLessEqual(len(lines), 5, lines)
        self.assertEqual(lines[0], ZH_WARN + "看守未运行")

    def test_scope_add_1_plain_runtime_has_no_warning_line(self):
        self.repo.set_conf("runtime", "plain")
        self.assertFalse(self.first().startswith(ZH_WARN), self.first())

    def test_r6_no_orca_on_this_machine_has_no_warning_line(self):
        self.repo.no_orca()
        self.assertFalse(self.first().startswith(ZH_WARN), self.first())

    def test_f7_the_status_line_never_calls_orca(self):
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:30")})
        self.repo.clear_calls()
        self.line(self.repo.dir)
        self.assertEqual(self.repo.calls(), [])


class TestStatusLineWatchEnglish(StatusLineCase):
    lang = "en"

    def test_f6_english_words(self):
        self.assertEqual(self.first(), EN_WARN + "watch not running")
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:30")})
        self.assertEqual(self.first(), EN_WARN + "1 not confirmed")
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:58")},
                    orphans=[{"path": "/x/ghost", "title": "g", "handle": "term_g"}])
        self.assertEqual(self.first(), EN_WARN + "a pane has no task line")


class TestStatusLineRows(WaitCase):
    """WaitCase: NOW 2026-11-20 12:31, runtime plain (no watch warning) unless a test says orca."""

    def test_k1_k2_a_queued_task_gets_its_own_row(self):
        self.put(q("plugin-slim", "one-watcher"))
        self.assertEqual(self.line(), name_col("plugin-slim") + "排队 · 在 one-watcher 之后")

    def test_k2_a_queue_with_no_task(self):
        self.put(q("plugin-slim"))
        self.assertEqual(self.line(), name_col("plugin-slim") + "排队")

    def test_k2_a_hold_drops_the_what(self):
        self.put(h("held", note="after the release"))
        self.assertEqual(self.line(), name_col("held") + "暂缓 · 已等 30分钟")

    def test_k2_a_hold_with_no_real_time(self):
        self.put(h("held", since="2026-13-40 99:99"))
        self.assertEqual(self.line(), name_col("held") + "暂缓")

    def test_k2_not_started(self):
        self.put(ns("fresh"))
        self.assertEqual(self.line(), name_col("fresh") + "未开始")

    def test_k3_board_order(self):
        self.put(h("held"), ns("fresh"), q("queued", "x"), run("busy", 10))
        self.assertEqual([l.split()[0] for l in self.line().split("\n")], ["busy", "queued", "fresh", "held"])

    def test_k4_rows_that_do_not_fit_fold(self):
        self.put(run("r1", 1), run("r2", 2), *[q("q%d" % i, "r1", since="2026-11-20 11:%02d" % i) for i in range(1, 6)])
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual([l.split()[0] for l in lines[:4]], ["r1", "r2", "q1", "q2"])
        self.assertEqual(lines[4], "+3 排队/暂缓")

    def test_k4_five_rows_fit_no_fold_line(self):
        self.put(run("r1", 1), q("q1", "r1"), q("q2", "r1", since="2026-11-20 11:01"), ns("n1"), h("h1"))
        lines = self.line().split("\n")
        self.assertEqual([l.split()[0] for l in lines], ["r1", "q1", "q2", "n1", "h1"])

    def test_k4_the_watch_warning_line_counts(self):
        self.repo.set_conf("runtime", "orca")
        self.repo.set_worktree_lines([("/nowhere/r1", "r1", "working")])
        self.put(run("r1", 1), q("q1", "r1"), q("q2", "r1", since="2026-11-20 11:01"), ns("n1"), h("h1"))
        lines = self.line().split("\n")
        self.assertEqual(lines[0], "看板可能不准：看守未运行")
        self.assertEqual([l.split()[0] for l in lines[1:4]], ["r1", "q1", "q2"])
        self.assertEqual(lines[4], "+2 排队/暂缓")
        self.put(run("r1", 1), q("q1", "r1"), ns("n1"), h("h1"))
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual([l.split()[0] for l in lines[1:]], ["r1", "q1", "n1", "h1"])

    def test_k5_a_running_row_with_no_stage_is_not_counted(self):
        self.put("r | big | w | est 30m | opened 2026-11-20 10:00 | by main | started 2026-11-20 10:00", q("q1", "r"))
        self.assertEqual(self.line(), name_col("q1") + "排队 · 在 r 之后")

    def test_k6_a_worktree_shows_its_own_queued_row(self):
        alpha = self.task_worktree("alpha")
        self.put(q("alpha", "state-trim"), q("other", "alpha"))
        self.assertEqual(self.line(alpha), name_col("alpha") + "排队 · 在 state-trim 之后")


class TestStatusLineRowsEnglish(WaitCase):
    lang = "en"

    def test_k2_english_words(self):
        self.put(q("plugin-slim", "one-watcher"), h("held"), ns("fresh"))
        self.assertEqual(self.line(), "\n".join([name_col("plugin-slim") + "queue · after one-watcher",
                                                 name_col("fresh") + "not started",
                                                 name_col("held") + "hold · waited 30m"]))


BIN = os.path.join(os.path.dirname(HERE), "bin")


def dw(text):
    import agent_board
    return agent_board.display_width(text)


def owner(name, since="2026-11-20 12:20", note=""):
    return "%s | big | w | est 30m | opened 2026-11-20 10:00 | by main | waiting mock since %s%s" % (
        name, since, ": " + note if note else "")


def plain(name):
    """Running, no stage."""
    return "%s | big | w | est 30m | opened 2026-11-20 10:00 | by main | started 2026-11-20 10:05" % name


def eight():
    return [owner("city-office-2"), run("settings-configure", 5), run("plugin-scope-sync", 10), plain("dev-docs"),
            q("check-blocks", "settings-configure", "2026-11-20 11:00"),
            q("report-to-main-pc2", "settings-configure", "2026-11-20 11:01"),
            h("mode-match"), ns("fresh-one")]


NAMES8 = ["city-office-2", "settings-configure", "plugin-scope-sync", "dev-docs", "check-blocks",
          "report-to-main-pc2", "mode-match", "fresh-one"]


class WideCase(WaitCase):
    def line(self, width=None, folder=None, now=NOW_NOV20_1231):
        folder = folder or self.repo.dir
        stdin = json.dumps({"session_id": "s1", "cwd": folder,
                            "workspace": {"current_dir": folder, "project_dir": folder}})
        env = {"AGENT_FAKE_NOW": now}
        if width is not None:
            env["AGENT_STATUSLINE_WIDTH"] = str(width)
        result = self.statusline_py(stdin, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result.stdout.rstrip("\n")

    def bars(self, lines):
        """Display column of every "│" per line."""
        return [[dw(l[:i]) for i, c in enumerate(l) if c == "│"] for l in lines]

    def names_in(self, text, names):
        return [n for n in names if n in text]


class TestColumns(WideCase):
    def test_200_wide_three_columns(self):
        self.put(*eight())
        lines = self.line(200).split("\n")
        self.assertEqual(lines[0], "看板 8 个任务 · 1 个等你")
        body = lines[1:]
        self.assertEqual(len(body), 3, body)
        self.assertTrue(all(l.count("│") == 2 for l in body[:2]), body)
        self.assertEqual(len(self.names_in("\n".join(body), NAMES8)), 8)
        self.assertNotIn("排队/暂缓", "\n".join(lines))
        self.assertTrue(all(dw(l) <= 200 for l in lines))
        # the owner wait first, down the first column
        self.assertTrue(body[0].startswith("city-office-2"), body[0])
        self.assertIn(body[1].split()[0], ["dev-docs", "settings-configure", "plugin-scope-sync"])
        # aligned
        full = self.bars(body[:2])
        self.assertEqual(full[0], full[1])

    def test_120_wide_two_columns(self):
        self.put(*eight())
        lines = self.line(120).split("\n")
        self.assertEqual(lines[0], "看板 8 个任务 · 1 个等你")
        body = lines[1:]
        self.assertEqual(len(body), 4, body)
        self.assertTrue(all(l.count("│") == 1 for l in body), body)
        self.assertEqual(len(self.names_in("\n".join(body), NAMES8)), 8)
        self.assertEqual(len({tuple(b) for b in self.bars(body)}), 1)
        self.assertTrue(all(dw(l) <= 120 for l in lines))

    def test_70_wide_one_column_with_a_fold(self):
        self.put(*eight())
        lines = self.line(70).split("\n")
        self.assertEqual(lines[0], "看板 8 个任务 · 1 个等你")
        self.assertEqual(len(lines), 5, lines)
        self.assertNotIn("│", "\n".join(lines))
        self.assertTrue(lines[1].startswith("city-office-2"), lines[1])
        self.assertEqual(lines[4], "+5 排队/暂缓")
        self.assertTrue(all(dw(l) <= 70 for l in lines))

    def test_70_wide_a_few_tasks_all_shown(self):
        self.put(*eight()[:4])
        lines = self.line(70).split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertNotIn("排队/暂缓", "\n".join(lines))
        self.assertEqual(len(self.names_in("\n".join(lines), NAMES8[:4])), 4)

    def test_unknown_width_is_todays_one_column(self):
        self.put(*eight())
        for width in (None, 0):
            lines = self.line(width).split("\n")
            self.assertEqual(len(lines), 5, lines)
            self.assertNotIn("│", "\n".join(lines))
            self.assertFalse(lines[0].startswith("看板 "), lines[0])
            self.assertEqual(lines[-1], "+3 排队/暂缓")  # the run without a stage was never a line

    def test_three_columns_start_at_140(self):
        self.put(*eight())
        self.assertTrue(all(l.count("│") == 2 for l in self.line(140).split("\n")[1:3]))
        self.assertTrue(all(l.count("│") == 1 for l in self.line(139).split("\n")[1:]))

    def test_two_columns_start_at_93(self):
        self.put(*eight())
        self.assertTrue(all(l.count("│") == 1 for l in self.line(93).split("\n")[1:]))
        self.assertNotIn("│", self.line(92))

    def test_english_count_line(self):
        self.repo.set_conf("language", "en")
        self.put(*eight())
        self.assertEqual(self.line(200).split("\n")[0], "board 8 tasks · 1 waiting on you")

    def test_one_task_and_none_waiting(self):
        self.put(run("solo", 1))
        self.assertEqual(self.line(200).split("\n")[0], "看板 1 个任务")


class TestChineseCells(WideCase):
    def test_a_long_chinese_cell_is_cut_and_the_bars_stay(self):
        long = "确认这个很长很长很长很长很长很长很长很长很长很长很长很长的样稿说明"
        self.put(owner("alpha-task", note=long), run("beta", 3), q("gamma", "beta"), ns("delta"))
        lines = self.line(120).split("\n")
        body = lines[1:]
        self.assertIn("…", "\n".join(body))
        self.assertEqual(len({tuple(b) for b in self.bars(body)}), 1, body)
        self.assertTrue(all(dw(l) <= 120 for l in lines))

    def test_a_cjk_character_counts_two(self):
        self.put(owner("名字", note="好"), run("beta", 3), q("gamma", "beta"), ns("delta"))
        body = self.line(120).split("\n")[1:]
        self.assertEqual(len({tuple(b) for b in self.bars(body)}), 1, body)


class TestFold(WideCase):
    def many(self, n):
        return [q("t%02d" % i, "x", "2026-11-20 11:%02d" % i) for i in range(n)]

    def test_twelve_cells_fit_in_four_lines(self):
        self.put(*self.many(12))
        lines = self.line(200).split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertNotIn("排队/暂缓", "\n".join(lines))
        self.assertEqual(len(self.names_in("\n".join(lines), ["t%02d" % i for i in range(12)])), 12)

    def test_more_than_the_cells_fold_the_rest(self):
        self.put(*self.many(14))
        lines = self.line(200).split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual(lines[0], "看板 14 个任务")
        self.assertEqual(lines[4], "+5 排队/暂缓")
        self.assertEqual(len(self.names_in("\n".join(lines[1:4]), ["t%02d" % i for i in range(14)])), 9)


class TestOrder(WideCase):
    def test_owner_then_running_then_queued_then_not_started(self):
        self.put(ns("n1"), h("h1"), q("q1", "r1"), plain("r0"), run("r1", 2), owner("o1"))
        body = self.line(70).split("\n")[1:]
        self.assertEqual([l.split()[0] for l in body[:3]], ["o1", "r0", "r1"])
        self.assertEqual(self.line(70).split("\n")[-1], "+3 排队/暂缓")
        wide = self.line(200).split("\n")[1:]
        order = [l.split("│")[0].split()[0] for l in wide]
        self.assertEqual(order, ["o1", "r0"])  # two rows of three columns
        flat = " ".join(" ".join(l.split("│")) for l in wide).split()
        self.assertLess(flat.index("q1"), flat.index("n1"))


class TestHelper(WideCase):
    def pane(self, task):
        self.state("LAUNCH k1: helper-pane | task %s | talk | since 2026-11-20 12:00 | pid %d | by helper"
                   % (task, os.getpid()))

    def helper(self):
        self.repo.set_worktree_lines([(self.repo.dir, "task manager, human-direct", "task: Owner Talk")])

    def test_the_pane_keeper_todo_is_not_a_second_row(self):
        self.put(plain("keeper"), run("real", 3))
        self.helper()
        self.pane("keeper")
        text = self.line(200)
        self.assertNotIn("keeper", text)
        self.assertIn("Helper", text)
        self.assertEqual(text.count("Helper"), 1)
        self.assertEqual(text.split("\n")[0], "看板 2 个任务")

    def test_without_a_pane_record_it_stays(self):
        self.put(plain("keeper"), run("real", 3))
        self.helper()
        text = self.line(200)
        self.assertIn("keeper", text)
        self.assertEqual(text.split("\n")[0], "看板 3 个任务")

    def test_without_a_helper_row_it_stays(self):
        self.put(plain("keeper"), run("real", 3))
        self.pane("keeper")
        self.assertIn("keeper", self.line(200))

    def test_a_todo_with_a_stage_stays(self):
        self.put(run("keeper", 3))
        self.helper()
        self.pane("keeper")
        self.assertIn("keeper", self.line(200))


class TestUnconfirmed(WideCase):
    def test_the_line_names_the_tasks(self):
        self.repo.set_conf("runtime", "orca")
        a1 = self.repo.make_worktree("a1", as_repo=False)
        a2 = self.repo.make_worktree("a2", as_repo=False)
        a3 = self.repo.make_worktree("a3", as_repo=False)
        self.put(run("a1", 1), run("a2", 2), run("a3", 3))
        self.repo.set_worktree_lines([(a1, "a1", "working"), (a2, "a2", "working"), (a3, "a3", "working")])
        write_watch(self.repo, sweep=NOW_NOV20_1231, tasks={
            "a1": task_entry(a1, watched=False, why="no pane"),
            "a2": task_entry(a2, watched=False, why="no pane"),
            "a3": task_entry(a3, changed="2026-11-20 12:30", confirmed="2026-11-20 12:30")})
        lines = self.line(200).split("\n")
        self.assertEqual(lines[0], "看板 3 个任务")
        self.assertEqual(lines[1], "看板可能不准：未确认 a1, a2")
        self.assertEqual(len(lines), 3, lines)  # the count, the warning, one row of three cells

    def test_english(self):
        self.repo.set_conf("language", "en")
        self.repo.set_conf("runtime", "orca")
        a1 = self.repo.make_worktree("a1", as_repo=False)
        self.put(run("a1", 1))
        self.repo.set_worktree_lines([(a1, "a1", "working")])
        write_watch(self.repo, sweep=NOW_NOV20_1231, tasks={"a1": task_entry(a1, watched=False, why="no pane")})
        self.assertEqual(self.line(200).split("\n")[1], "board may be wrong: not confirmed a1")

    def test_the_budget_stays_five_with_the_warning(self):
        self.repo.set_conf("runtime", "orca")
        a1 = self.repo.make_worktree("a1", as_repo=False)
        self.put(run("a1", 1), *[q("q%02d" % i, "a1", "2026-11-20 11:%02d" % i) for i in range(12)])
        self.repo.set_worktree_lines([(a1, "a1", "working")])
        write_watch(self.repo, sweep=NOW_NOV20_1231, tasks={"a1": task_entry(a1, watched=False, why="no pane")})
        lines = self.line(200).split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual(lines[1], "看板可能不准：未确认 a1")
        self.assertEqual(lines[4], "+7 排队/暂缓")  # 13 tasks, 2 cell lines of 3 = 6 shown
        self.assertEqual(lines[2].count("│"), 2)


class TestWidthReading(unittest.TestCase):
    def width(self, env):
        import agent_board
        return agent_board.terminal_width(env)

    def test_the_override_wins(self):
        self.assertEqual(self.width({"AGENT_STATUSLINE_WIDTH": "150", "COLUMNS": "80"}), 150)

    def test_zero_means_unknown_and_stops_the_search(self):
        self.assertIsNone(self.width({"AGENT_STATUSLINE_WIDTH": "0", "COLUMNS": "80"}))

    def test_columns(self):
        self.assertEqual(self.width({"COLUMNS": "132"}), 132)

    def test_junk_columns_fall_through(self):
        # no tty in the test run: nothing else answers, or the real terminal does; either way no crash
        self.assertTrue(self.width({"COLUMNS": "abc"}) is None or self.width({"COLUMNS": "abc"}) > 0)

    def test_the_tty_window_size(self):
        import fcntl
        import pty
        import struct
        import termios
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 117, 0, 0))

        def ctty():
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        code = "import sys; sys.path.insert(0, %r); import agent_board; print(agent_board.terminal_width({}))" % BIN
        out = subprocess.run([sys.executable, "-c", code], stdin=slave, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True, preexec_fn=ctty, text=True, timeout=20)
        os.close(master)
        os.close(slave)
        self.assertEqual(out.stdout.strip(), "117", out.stderr)


class TestHeaders(unittest.TestCase):
    def test_the_script_comment_names_the_width(self):
        with open(os.path.join(os.path.dirname(HERE), "bin", "agent-statusline.sh"), encoding="utf-8") as fh:
            self.assertIn("column", fh.read())


def cmd_of(root):
    return '"%s/bin/agent-statusline.sh"' % root


class RefreshCase(ScriptCase):
    script = "agent-settings.sh"

    def setUp(self):
        super().setUp()
        self.cfg = os.path.join(self.repo.base, "cfg")
        self.cache = os.path.join(self.cfg, "plugins", "cache", "auto-pipeline", "auto-pipeline")
        self.cached = os.path.realpath(self.make_cached("0.38.0"))
        self.other = os.path.realpath(self.repo.plugin)        # a checkout-like folder, not under the cache
        self.settings = os.path.join(self.cfg, "settings.json")
        self.gone = os.path.join(self.cache, "0.37.0")           # a cache root that was removed

    def make_cached(self, version):
        path = os.path.join(self.cache, version)
        shutil.copytree(self.repo.plugin, path)
        return path

    def env(self, plugin_root=""):
        return {"CLAUDE_CONFIG_DIR": self.cfg, "CLAUDE_PLUGIN_ROOT": plugin_root}

    def run_at(self, root, *args, plugin_root="", script="agent-settings.sh", ok=True):
        argv = [os.path.join(root, "bin", script)] + (["statusline"] + list(args) if script == "agent-settings.sh"
                                                      else list(args))
        result = subprocess.run(argv, cwd=self.repo.dir, env=self.repo._env(self.env(plugin_root)),
                                capture_output=True, text=True, input="", timeout=90)
        if ok:
            self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
        return result

    def write(self, data=None, raw=None):
        os.makedirs(self.cfg, exist_ok=True)
        with open(self.settings, "w") as fh:
            fh.write(raw if raw is not None else json.dumps(data, indent=2) + "\n")

    def raw(self):
        with open(self.settings, "rb") as fh:
            return fh.read()

    def load(self):
        with open(self.settings) as fh:
            return json.load(fh)

    def ours_at(self, root, interval=True):
        sl = {"type": "command", "command": cmd_of(root)}
        if interval:
            sl["refreshInterval"] = 60
        return sl

    def assertSame(self, root, *args, plugin_root=""):
        before = self.raw()
        result = self.run_at(root, *args, plugin_root=plugin_root)
        self.assertEqual(self.raw(), before)
        self.assertEqual(result.stdout + result.stderr, "")


class TestRefresh(RefreshCase):
    def test_11_1_a_cache_root_repoints_ours(self):
        self.write({"statusLine": self.ours_at(self.other, interval=False), "theme": "dark"})
        result = self.run_at(self.cached, "refresh")
        self.assertEqual(result.stdout + result.stderr, "")
        self.assertEqual(self.load(), {"statusLine": self.ours_at(self.cached), "theme": "dark"})

    def test_11_2_another_root_leaves_it(self):
        self.write({"statusLine": self.ours_at(self.cached), "theme": "dark"})
        self.assertSame(self.other, "refresh")

    def test_11_2_a_temp_root_with_a_missing_script_has_nothing_to_heal_to(self):
        self.write({"statusLine": self.ours_at(self.gone)})
        self.assertSame(self.other, "refresh")

    def test_11_2_a_git_worktree_root_leaves_it(self):
        wt = os.path.join(self.repo.base, "wt")
        shutil.copytree(self.repo.plugin, wt)
        subprocess.run(["git", "init", "-q", wt], check=True, capture_output=True)
        self.write({"statusLine": self.ours_at(self.cached)})
        self.assertSame(os.path.realpath(wt), "refresh")

    def test_11_3_claude_plugin_root_under_the_cache(self):
        self.write({"statusLine": self.ours_at(self.other)})
        self.run_at(self.other, "refresh", plugin_root=self.cached)
        self.assertEqual(self.load()["statusLine"], self.ours_at(self.cached))

    def test_11_3_claude_plugin_root_not_under_the_cache(self):
        self.write({"statusLine": self.ours_at(self.cached)})
        elsewhere = os.path.join(self.repo.base, "elsewhere")
        shutil.copytree(self.repo.plugin, elsewhere)
        self.assertSame(self.other, "refresh", plugin_root=elsewhere)

    def test_a_cache_folder_with_no_status_line_script_is_no_target(self):
        empty = os.path.join(self.cache, "0.39.0")
        os.makedirs(os.path.join(empty, "bin"))
        self.write({"statusLine": self.ours_at(self.cached)})
        self.assertSame(self.other, "refresh", plugin_root=empty)

    def test_11_4_self_heal(self):
        self.write({"statusLine": self.ours_at(self.gone), "theme": "dark"})
        self.run_at(self.cached, "refresh")
        self.assertEqual(self.load(), {"statusLine": self.ours_at(self.cached), "theme": "dark"})
        self.write({"statusLine": self.ours_at(self.gone)})
        self.run_at(self.other, "refresh", plugin_root=self.cached)
        self.assertEqual(self.load()["statusLine"], self.ours_at(self.cached))

    def test_11_6_not_ours_no_file_not_json(self):
        self.write({"statusLine": FOREIGN})
        self.assertSame(self.cached, "refresh")
        self.write(raw="{ not json\n")
        self.assertSame(self.cached, "refresh")
        os.remove(self.settings)
        self.run_at(self.cached, "refresh")
        self.assertFalse(os.path.exists(self.settings))


class TestOn(RefreshCase):
    def test_11_5_on_writes_the_running_root_cache_or_not(self):
        self.write({"theme": "dark"})
        self.run_at(self.other, "on")
        self.assertEqual(self.load(), {"statusLine": self.ours_at(self.other), "theme": "dark"})
        self.run_at(self.cached, "on")
        self.assertEqual(self.load()["statusLine"], self.ours_at(self.cached))


class TestStartRefresh(RefreshCase):
    def start(self, root):
        result = self.run_at(root, script="agent-start.sh", ok=False)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def test_11_7_a_start_from_another_root_leaves_it(self):
        self.write({"statusLine": self.ours_at(self.cached), "theme": "dark"})
        self.start(self.other)
        self.assertEqual(self.load()["statusLine"], self.ours_at(self.cached))

    def test_11_8_a_start_from_a_cache_root_repoints_it(self):
        self.write({"statusLine": self.ours_at(self.gone), "theme": "dark"})
        self.start(self.cached)
        self.assertEqual(self.load()["statusLine"], self.ours_at(self.cached))


ZH = {"brief": "简报", "register": "登记", "mock": "样稿", "tests": "写测试", "workers": "写代码",
      "verify": "验证", "push": "推送", "report": "报告", "e2e": "浏览器验收", "merge": "合并"}


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class VerticalCase(BoardCase):
    lang = "zh"

    def stage(self, name, *args, now=NOW, cwd=None):
        return self.af("todo", "stage", name, *args, now=now, cwd=cwd)

    def board_row(self, name, *args, now=NOW, cwd=None):
        return self.row(self.rows(*args, now=now, cwd=cwd), task=name)

    def progress(self, name, **kw):
        return self.board_row(name, **kw)["Progress"]

    def done_by(self, name, **kw):
        return self.board_row(name, **kw)["Done by"]

    def frozen(self, stage, since, now, wsince, est=60):
        """The bar of agent_board.stage_progress with an open wait (a waiting row shows "-" on the board)."""
        if BIN not in sys.path:
            sys.path.insert(0, BIN)
        import agent_board
        t = agent_board.parse_time
        p = agent_board.stage_progress(agent_board.read_weights(self.repo.dir), (stage, None, None), est,
                                       t(since), t(now), 0, t(wsince))
        return agent_board.bar_text(p)

    def clear_todo(self):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("")

    @staticmethod
    def stage_col(line):
        """The stage column of a one-task status line: the text after "%  ", up to two spaces or the end."""
        m = re.search(r"%  (.+?)(?:  |$)", line)
        assert m, line
        return m.group(1).strip()

    def line(self, folder=None, now=NOW):
        folder = folder or self.repo.dir
        stdin = json.dumps({"session_id": "s1", "cwd": folder,
                            "workspace": {"current_dir": folder, "project_dir": folder}})
        result = self.statusline_py(stdin, env={"AGENT_FAKE_NOW": now})
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.rstrip("\n")


class TestStageSince(VerticalCase):
    def test_a_new_slice_keeps_the_since(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "workers", now="2026-11-02 14:10")
        self.stage("alpha", "workers", "1/3", now="2026-11-02 14:30")
        self.assertIn(" | stage workers 1/3 since 2026-11-02 14:10", self.todo_line("alpha"))
        self.stage("alpha", "workers", "2/3", now="2026-11-02 14:40")
        line = self.todo_line("alpha")
        self.assertIn(" | stage workers 2/3 since 2026-11-02 14:10", line)
        self.assertEqual(line.count(" | stage "), 1, line)
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.assertIn(" | stage verify since 2026-11-02 14:50", self.todo_line("alpha"))

    def test_the_stage_line_keeps_it_too(self):
        alpha = self.task_worktree("alpha")
        self.stage("alpha", "workers", now="2026-11-02 14:10", cwd=alpha)
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:30", cwd=alpha)
        self.assertIn("STAGE alpha: workers 1/2 | since 2026-11-02 14:10\n", self.state_text(alpha))
        self.stage("alpha", "verify", now="2026-11-02 14:50", cwd=alpha)
        self.assertIn("STAGE alpha: verify | since 2026-11-02 14:50\n", self.state_text(alpha))


class TestWaitedInStage(VerticalCase):
    def test_a_closed_wait_inside_the_stage(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.wait("alpha", "on", "question", now="2026-11-02 14:52")
        self.wait("alpha", "off", now="2026-11-02 14:58")
        line = self.todo_line("alpha")
        self.assertIn(" | waited 6m", line)
        self.assertIn(" | waited in stage 6m", line)
        self.assertEqual(line.count("waited in stage"), 1, line)
        self.assertIn(" | stage verify since 2026-11-02 14:50", line)

    def test_two_waits_add_up(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:30")
        self.wait("alpha", "on", "question", now="2026-11-02 14:32")
        self.wait("alpha", "on", "review", now="2026-11-02 14:35")   # closes the first: 3m
        self.wait("alpha", "off", now="2026-11-02 14:40")             # 5m
        line = self.todo_line("alpha")
        self.assertIn(" | waited 8m", line)
        self.assertIn(" | waited in stage 8m", line)
        self.assertEqual(line.count("waited in stage"), 1, line)

    def test_only_the_part_inside_the_stage(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "tests", now="2026-11-02 14:30")
        self.wait("alpha", "on", "hold", now="2026-11-02 14:40")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.wait("alpha", "off", now="2026-11-02 14:56")
        line = self.todo_line("alpha")
        self.assertIn(" | waited 16m", line)
        self.assertIn(" | waited in stage 6m", line)

    def test_a_new_stage_drops_it(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.wait("alpha", "on", "question", now="2026-11-02 14:52")
        self.wait("alpha", "off", now="2026-11-02 14:58")
        self.stage("alpha", "push", now="2026-11-02 15:00")
        line = self.todo_line("alpha")
        self.assertNotIn("waited in stage", line)
        self.assertIn(" | waited 6m", line)

    def test_a_new_slice_keeps_it(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "workers", now="2026-11-02 14:10")
        self.wait("alpha", "on", "queue", now="2026-11-02 14:20")
        self.wait("alpha", "off", now="2026-11-02 14:24")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:40")
        self.assertIn(" | waited in stage 4m", self.todo_line("alpha"))

    def test_no_stage_no_field(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.wait("alpha", "on", "mock", now="2026-11-02 14:10")
        self.wait("alpha", "off", now="2026-11-02 14:30")
        line = self.todo_line("alpha")
        self.assertIn(" | waited 20m", line)
        self.assertNotIn("waited in stage", line)

    def test_done_still_reads_the_line(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.wait("alpha", "on", "question", now="2026-11-02 14:52")
        self.wait("alpha", "off", now="2026-11-02 14:58")
        self.assertIn("work left", self.af("eta", "alpha", "--step", "5").stdout)
        self.af("todo", "done", "alpha", "--work", "50")
        self.assertIn(" | alpha | the login form | data ", self.repo.read("agent_completed.txt"))
        self.assertIsNone(self.todo_line("alpha"))


class TestGrowth(VerticalCase):
    def test_it_grows_with_time_in_the_stage(self):
        # est 60, verify share 9m; 3 minutes in -> 66 + 15 x 3/9 = 71
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:57")
        self.assertEqual(self.progress("alpha"), "███████░░░  71%")
        self.assertEqual(self.progress("alpha", now="2026-11-02 14:57"), "██████░░░░  66%")

    def test_it_stops_below_the_next_stage(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:00")
        self.assertEqual(self.progress("alpha"), "████████░░  80%")
        self.assertEqual(self.progress("alpha", now="2026-11-02 23:00"), "████████░░  80%")
        self.stage("alpha", "push", now="2026-11-02 15:00")
        self.assertEqual(self.progress("alpha"), "████████░░  81%")

    def test_an_open_wait_freezes_it(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:54")
        self.wait("alpha", "on", "question", now="2026-11-02 14:57")
        # board-waiting: a waiting row shows "-" for progress; the function still stops the clock
        self.assertEqual(self.progress("alpha"), "-")
        self.assertEqual(self.frozen("verify", "2026-11-02 14:54", "2026-11-02 15:30", "2026-11-02 14:57"),
                         "███████░░░  71%")

    def test_a_wait_opened_before_the_stage_freezes_it_at_the_start(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "tests", now="2026-11-02 14:30")
        self.wait("alpha", "on", "hold", now="2026-11-02 14:40")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        # board-waiting: a held row shows "-" for progress; the function still stops the clock
        self.assertEqual(self.progress("alpha"), "-")
        self.assertEqual(self.frozen("verify", "2026-11-02 14:50", NOW, "2026-11-02 14:40"), "██████░░░░  66%")

    def test_a_closed_wait_is_taken_off(self):
        # 10 minutes in verify, 6 of them waited -> 4/9 -> 72.6
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.wait("alpha", "on", "question", now="2026-11-02 14:52")
        self.wait("alpha", "off", now="2026-11-02 14:58")
        self.assertEqual(self.progress("alpha"), "███████░░░  72%")

    def test_workers_the_larger_of_slices_and_time(self):
        # est 60, workers share 24m
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "workers", now="2026-11-02 14:50")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:55")
        self.assertEqual(self.progress("alpha"), "████░░░░░░  46%")                         # 10/24 < 1/2
        self.assertEqual(self.progress("alpha", now="2026-11-02 15:08"), "█████░░░░░  56%")  # 18/24
        self.assertEqual(self.progress("alpha", now="2026-11-02 16:00"), "██████░░░░  65%")  # time capped
        self.stage("alpha", "workers", "2/2", now="2026-11-02 16:00")
        self.assertEqual(self.progress("alpha", now="2026-11-02 16:00"), "██████░░░░  66%")  # slices reach the end

    def test_no_estimate_no_time_part(self):
        self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:00")
        self.assertEqual(self.progress("alpha"), "██████░░░░  66%")

    def test_self_reads_the_since_of_its_stage_line(self):
        # est 120, verify share 18m; 10 minutes in -> 66 + 15 x 10/18 = 74.3
        alpha = self.task_worktree("alpha")
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.state("STAGE alpha: verify | since 2026-11-02 14:50\n", folder=alpha)
        r = self.board_row("alpha", "--self", cwd=alpha)
        self.assertEqual((r["Progress"], r["Done by"]), ("███████░░░  74%", "16:00"))

    def test_self_on_another_machine(self):
        alpha = self.task_worktree("alpha")
        self.state("TODO LINE: alpha | big | the login form | est 60m | opened 2026-11-02 14:00 | by main\n",
                   folder=alpha)
        self.stage("alpha", "verify", now="2026-11-02 14:57", cwd=alpha)
        self.assertEqual(self.board_row("alpha", "--self", cwd=alpha)["Progress"], "███████░░░  71%")


class TestGrowthDoneBy(VerticalCase):
    def test_over_the_estimate_uses_the_grown_progress(self):
        # work 60 > est 40; verify share 6m, 3 in -> p = 73.5/100: 60 x 26.5/73.5 = 21.6 -> 22
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:57")
        r = self.board_row("alpha")
        self.assertEqual((r["Progress"], r["Done by"]), ("███████░░░  73%", "15:22"))

    def test_the_minimum_percent_uses_the_grown_progress(self):
        # tests share 8m: 5 in -> 18.5 < 20 -> over; 7 in -> 23.5: 60 x 76.5/23.5 = 195.3 -> 196
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "tests", now="2026-11-02 14:55")
        self.assertEqual(self.done_by("alpha"), "超出 20m")
        self.add("beta", "bank recon match", 40, opened="2026-11-02 14:00")
        self.stage("beta", "tests", now="2026-11-02 14:53")
        self.assertEqual(self.done_by("beta"), "18:16")

    def test_capped(self):
        # verify capped (80%): 60 x 20/80 = 15
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:00")
        self.assertEqual(self.done_by("alpha"), "15:15")

    def test_under_the_estimate_still_the_estimate(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.assertEqual(self.done_by("alpha"), "16:00")


class TestVertical(VerticalCase):
    def test_the_owner_look(self):
        self.add("pospro-device", "device page", 120, opened="2026-11-02 14:00")
        self.stage("pospro-device", "verify", now=NOW)
        self.add("doc-follows-invoice-edit", "doc follows invoice", 120, opened="2026-11-02 14:00")
        self.stage("doc-follows-invoice-edit", "verify", now="2026-11-02 14:57")
        self.add("release-train-1112", "release train", 120, opened="2026-11-02 14:30")
        self.stage("release-train-1112", "workers", "1/3", now=NOW)
        self.assertEqual(self.line(), "\n".join([
            "pospro-device             ██████░░░░  66%  验证        16:00",
            "doc-follows-invoice-edit  ██████░░░░  68%  验证        16:00",
            "release-train-1112        ███░░░░░░░  39%  写代码 1/3  16:30",
        ]))

    def test_one_task(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.assertEqual(self.line(), "alpha                     ██████░░░░  66%  验证  16:00")

    def test_no_done_by_and_no_trailing_space(self):
        self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
        self.stage("alpha", "brief")
        self.assertEqual(self.line(), "alpha                     ░░░░░░░░░░   0%  简报")

    def test_a_long_name_is_cut(self):
        name = "a-really-long-task-name-for-the-cut"
        self.add(name, "long", 120, opened="2026-11-02 14:00")
        self.stage(name, "verify")
        self.assertEqual(self.line(), "a-really-long-task-name…  ██████░░░░  66%  验证  16:00")

    def test_every_stage_word(self):
        for stage, word in ZH.items():
            with self.subTest(stage=stage):
                self.clear_todo()
                self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
                self.stage("alpha", stage)
                self.assertEqual(self.stage_col(self.line()), word)

    def test_workers_with_and_without_slices(self):
        self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
        self.stage("alpha", "workers")
        self.assertEqual(self.stage_col(self.line()), "写代码")
        self.stage("alpha", "workers", "2/5")
        self.assertEqual(self.stage_col(self.line()), "写代码 2/5")

    def test_six_or_more_tasks_show_five_and_the_rest(self):
        for i in range(1, 8):
            self.add("t%d" % i, "task %d" % i, 120, opened="2026-11-02 14:%02d" % i)
            self.stage("t%d" % i, "tests")
        lines = self.line().split("\n")
        # board-waiting: 5 lines in all, the "+N" line counted
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual([l.split()[0] for l in lines[:4]], ["t1", "t2", "t3", "t4"])
        self.assertEqual(lines[4], "+3 排队/暂缓")

    def test_five_tasks_no_extra_line(self):
        for i in range(1, 6):
            self.add("t%d" % i, "task %d" % i, 120, opened="2026-11-02 14:%02d" % i)
            self.stage("t%d" % i, "tests")
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)

    def test_the_board_order(self):
        # waiting on the owner first, then running, then held; oldest first in a group
        self.add("held", "held one", 120, opened="2026-11-02 14:01")
        self.stage("held", "tests")
        self.wait("held", "on", "hold", now="2026-11-02 14:30")
        self.add("run-late", "running late", 120, opened="2026-11-02 14:20")
        self.stage("run-late", "tests")
        self.add("run-early", "running early", 120, opened="2026-11-02 14:10")
        self.stage("run-early", "tests")
        self.add("mock-wait", "waits on the mock", 120, opened="2026-11-02 14:40")
        self.stage("mock-wait", "mock")
        self.wait("mock-wait", "on", "mock", now="2026-11-02 14:45")
        self.add("no-stage", "not shown", 120, opened="2026-11-02 14:00")
        lines = self.line().split("\n")
        # one-watcher K (owner 2026-11-24): the held row gets its own row while there is room; a running row
        # with no stage is still not counted
        self.assertEqual([l.split()[0] for l in lines], ["mock-wait", "run-early", "run-late", "held"])
        self.assertEqual(lines[3], "held" + " " * 22 + "暂缓 · 已等 30分钟")

    def test_the_line_grows_with_time(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:57")
        self.assertIn("███████░░░  71%", self.line())
        self.assertIn("████████░░  80%", self.line(now="2026-11-02 15:30"))

    def test_nothing_with_a_stage_prints_nothing(self):
        self.add("alpha", "the login form", 60)
        self.assertEqual(self.line(), "")

    def test_the_header_comment(self):
        text = read("bin", "agent-statusline.sh")
        head = "\n".join(l for l in text.splitlines() if l.startswith("#"))
        self.assertIn("one line per task", head)
        self.assertNotIn("one line with the progress bar", head)
        self.assertNotIn("prints one line or nothing", head)


class TestVerticalEnglish(VerticalCase):
    lang = "en"

    def test_words_and_more(self):
        for i in range(1, 7):
            self.add("t%d" % i, "task %d" % i, 120, opened="2026-11-02 14:%02d" % i)
        self.stage("t1", "workers", "1/3")
        for i in range(2, 7):
            self.stage("t%d" % i, "e2e")
        lines = self.line().split("\n")
        # board-waiting: 5 lines in all, the "+N" line counted
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual(lines[0], "t1                        ███░░░░░░░  39%  workers 1/3  16:01")
        self.assertEqual(lines[1], "t2                        ████████░░  85%  e2e          16:02")
        self.assertEqual(lines[4], "+2 queued/held")

    def test_every_stage_word(self):
        for stage in ZH:
            with self.subTest(stage=stage):
                self.clear_todo()
                self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
                self.stage("alpha", stage)
                self.assertEqual(self.stage_col(self.line()), stage)


class IntervalCase(ScriptCase):
    script = "agent-settings.sh"

    def setUp(self):
        super().setUp()
        self.home = self.repo.fake_home()
        self.settings = os.path.join(self.home, ".claude", "settings.json")
        self.cmd = '"%s/bin/agent-statusline.sh"' % self.repo.plugin

    def ours(self, n=60):
        return {"type": "command", "command": self.cmd, "refreshInterval": n}

    def write(self, data):
        os.makedirs(os.path.dirname(self.settings), exist_ok=True)
        with open(self.settings, "w") as fh:
            fh.write(json.dumps(data, indent=2) + "\n")

    def raw(self):
        with open(self.settings, "rb") as fh:
            return fh.read()

    def load(self):
        with open(self.settings) as fh:
            return json.load(fh)

    def run_settings(self, *args):
        return self.repo.run("agent-settings.sh", "statusline", *args, timeout=30)


class TestRefreshInterval(IntervalCase):
    def test_on_writes_the_fixed_60(self):
        # settings-configure: statusline_refresh_sec is a fixed constant (60)
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load(), {"statusLine": self.ours(60)})

    def test_no_task_file(self):
        os.remove(self.repo.path("agent_todo.txt"))
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load()["statusLine"], self.ours(60))

    def test_on_again_with_nothing_to_change_keeps_the_file(self):
        self.write({"statusLine": self.ours(60), "theme": "dark"})
        before = self.raw()
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.raw(), before)

    def test_on_adds_it_to_an_install_from_before(self):
        # bounce 1 (task manager): ours, same command, no refreshInterval -> on must still add it
        self.write({"statusLine": {"type": "command", "command": self.cmd}, "theme": "dark"})
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load(), {"statusLine": self.ours(60), "theme": "dark"})

    # board-waiting scope add (2026-11-20): refresh repoints only from a root under <config dir>/plugins/cache/
    # (requirements/board-waiting.md F); these two run refresh from a copy of the plugin in the cache
    def refresh_from_the_cache(self):
        root = os.path.join(self.home, ".claude", "plugins", "cache", "auto-pipeline", "auto-pipeline", "0.38.0")
        shutil.copytree(self.repo.plugin, root)
        root = os.path.realpath(root)
        self.cmd = '"%s/bin/agent-statusline.sh"' % root
        return subprocess.run([os.path.join(root, "bin", "agent-settings.sh"), "statusline", "refresh"],
                              cwd=self.repo.dir, env=self.repo._env({"CLAUDE_PLUGIN_ROOT": ""}),
                              capture_output=True, text=True, input="", timeout=30)

    def test_refresh_adds_it_to_ours(self):
        root = os.path.realpath(os.path.join(self.home, ".claude", "plugins", "cache", "auto-pipeline",
                                             "auto-pipeline", "0.38.0"))
        self.write({"statusLine": {"type": "command", "command": '"%s/bin/agent-statusline.sh"' % root},
                    "theme": "dark"})
        result = self.refresh_from_the_cache()
        self.assertOk(result)
        self.assertEqual(result.stdout + result.stderr, "")
        self.assertEqual(self.load(), {"statusLine": self.ours(60), "theme": "dark"})

    def test_refresh_points_and_sets(self):
        self.write({"statusLine": {"type": "command", "command": OURS_OLD, "refreshInterval": 30}})
        self.assertOk(self.refresh_from_the_cache())
        self.assertEqual(self.load(), {"statusLine": self.ours(60)})

    def test_refresh_from_a_checkout_changes_nothing(self):
        self.write({"statusLine": {"type": "command", "command": OURS_OLD, "refreshInterval": 60}})
        before = self.raw()
        self.assertOk(self.run_settings("refresh"))
        self.assertEqual(self.raw(), before)

    def test_refresh_with_nothing_to_change_keeps_the_file(self):
        self.write({"statusLine": self.ours(60), "theme": "dark"})
        before = self.raw()
        self.assertOk(self.run_settings("refresh"))
        self.assertEqual(self.raw(), before)

    def test_refresh_never_touches_a_foreign_one(self):
        self.write({"statusLine": FOREIGN})
        before = self.raw()
        self.assertOk(self.run_settings("refresh"))
        self.assertEqual(self.raw(), before)

    def test_off_takes_it_all_away(self):
        self.write({"statusLine": self.ours(60), "theme": "dark"})
        self.assertOk(self.run_settings("off"))
        self.assertEqual(self.load(), {"theme": "dark"})


class TestRefreshKey(unittest.TestCase):
    def setUp(self):
        import agent_conf
        self.ac = agent_conf

    def test_the_fixed_constant(self):
        self.assertEqual(self.ac.CONSTANTS["statusline_refresh_sec"], 60)


class TestModelAndRelease(unittest.TestCase):
    def test_the_template_main_manager(self):
        import agent_conf
        env = {"CLAUDE_CONFIG_DIR": os.path.join(ROOT, "tests", "no-such-config-dir")}
        self.assertEqual(agent_conf.get("main_manager", env), "opus-5.5:high")
        self.assertEqual(agent_conf.get("task_manager", env), "opus-5.5:high")
        for role in ("worker", "fast_lane_deputy", "merge_deputy"):
            self.assertEqual(agent_conf.get(role, env), "sonnet-5:medium")

    def test_the_rule_text(self):
        text = read("PRINCIPLES.md")
        w6 = text[text.index("W6. Roles"):text.index("W7. ")]
        # out of date on main b4392c7: check-blocks (f1e3995, models by setting) names the
        # setting in W6 instead of a fixed model; the pin follows the rule text
        self.assertIn('- Main manager (the "Main manager model" setting) = the main chat.', w6)
        self.assertNotIn("Fable 5.1", w6)

    def test_the_version(self):
        version = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        self.assertGreaterEqual(tuple(int(n) for n in version.split(".")), (0, 32, 0))


if __name__ == "__main__":
    unittest.main()
