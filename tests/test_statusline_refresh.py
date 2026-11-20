"""Failing tests for the board-waiting scope add: the status line refresh points only at a plugin cache root.
Written by the task manager first. Rules: requirements/board-waiting.md section F (rows 11.1-11.8).

Main manager, 2026-11-20 15:2x: agent-start.sh runs `agent-settings.sh statusline refresh` at every start; refresh
pointed an ours statusLine at the bin of whatever checkout ran the start, and a throwaway checkout deleted 4 minutes
later left the status bar blank.

    config dir   CLAUDE_CONFIG_DIR, else ~/.claude;  cache = <config dir>/plugins/cache/
    target       the running root when it is under the cache, else CLAUDE_PLUGIN_ROOT when that is under the cache,
                 else none; a root with no bin/agent-statusline.sh is no target
    refresh      ours + a target -> command = "<target>/bin/agent-statusline.sh" (refreshInterval as today);
                 no target -> settings.json byte for byte the same; silent, exit 0 always
    on           (the human) writes the running root, cache or not (today)

CLAUDE_CONFIG_DIR is always a temp folder here, never the real ~/.claude.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase  # noqa: E402

FOREIGN = {"type": "command", "command": "~/.claude/buddy/statusline.sh"}


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


class TestStart(RefreshCase):
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


if __name__ == "__main__":
    unittest.main()
