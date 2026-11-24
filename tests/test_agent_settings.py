"""Tests for numeric agent.conf keys (heavy_test_slots, max_agents), through ./agent-settings.sh.

CONTRACT:

  agent_conf.py holds both in NUMBER_BOUNDS, HINTS and GROUPS["limits"], so
  ./agent-settings.sh accepts a good value and refuses a bad one without saving.
  (The monitor keys monitor_interval_min and stall_min are gone with the monitor, 2026-11-24.)

CONTRACT (run from a git worktree):

  Every script reads the MAIN repo's agent.conf (the first `git worktree
  list` entry), so agent-settings.sh keeps reading and writing that copy,
  never the worktree's own (git-tracked) agent.conf. Run from a worktree,
  every mode (show, set, sync) says so: the output names the full path of
  the file it used and the words "main repo". Run from the main repo the
  output is as before, no such note.
"""

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase

NEW_KEYS = {"heavy_test_slots": (1, 8), "max_agents": (1, 16)}


class SettingsCase(ScriptCase):
    script = "agent-settings.sh"

    def settings(self, *args):
        return self.repo.run("agent-settings.sh", *args)

    def conf_value(self, key):
        for line in open(self.repo.path("agent.conf")):
            if line.split("=", 1)[0].strip() == key:
                return line.split("=", 1)[1].strip()
        return None


class TestNewKeysExist(SettingsCase):
    def test_both_keys_are_in_the_repo_conf(self):
        for key in NEW_KEYS:
            with self.subTest(key=key):
                self.assertIsNotNone(self.conf_value(key),
                                     "%s is missing from agent.conf" % key)

    def test_defaults(self):
        self.assertEqual(self.conf_value("heavy_test_slots"), "1")
        self.assertEqual(self.conf_value("max_agents"), "4")

    def test_show_lists_both_keys(self):
        out = self.assertOk(self.settings())
        for key in NEW_KEYS:
            self.assertIn(key, out)


class TestAcceptsGoodValues(SettingsCase):
    def test_saves_a_good_value(self):
        for key, (low, high) in NEW_KEYS.items():
            for value in (low, (low + high) // 2, high):
                with self.subTest(key=key, value=value):
                    result = self.settings(key, str(value))
                    self.assertEqual(result.returncode, 0,
                                     result.stdout + result.stderr)
                    self.assertIn("saved: %s=%s" % (key, value), result.stdout)
                    self.assertEqual(self.conf_value(key), str(value))


class TestRejectsBadValues(SettingsCase):
    def test_zero_is_refused_and_nothing_is_saved(self):
        for key in NEW_KEYS:
            with self.subTest(key=key):
                before = self.conf_value(key)
                result = self.settings(key, "0")
                self.assertNotEqual(result.returncode, 0,
                                    "0 was accepted for %s" % key)
                self.assertEqual(self.conf_value(key), before,
                                 "agent.conf changed although the value was bad")

    def test_over_the_top_bound_is_refused(self):
        for key, (_, high) in NEW_KEYS.items():
            with self.subTest(key=key):
                result = self.settings(key, str(high + 1))
                self.assertNotEqual(result.returncode, 0)

    def test_words_are_refused(self):
        for key in NEW_KEYS:
            with self.subTest(key=key):
                self.assertNotEqual(self.settings(key, "soon").returncode, 0)

    def test_the_message_names_the_range(self):
        result = self.settings("max_agents", "0")
        message = result.stdout + result.stderr
        self.assertIn("1", message)
        self.assertIn("16", message)


class TestKeyOrder(SettingsCase):
    def test_the_new_keys_sit_with_the_other_limits(self):
        keys = [line.split("=", 1)[0].strip()
                for line in open(self.repo.path("agent.conf")) if "=" in line]
        self.assertEqual(
            keys[:3],
            ["max_usage_percent", "heavy_test_slots", "max_agents"],
        )

    def test_saving_keeps_the_order(self):
        before = [line.split("=", 1)[0].strip()
                  for line in open(self.repo.path("agent.conf")) if "=" in line]
        self.assertOk(self.settings("max_agents", "5"))
        after = [line.split("=", 1)[0].strip()
                 for line in open(self.repo.path("agent.conf")) if "=" in line]
        self.assertEqual(before, after)


class TestSync(SettingsCase):
    def test_sync_adds_only_the_missing_keys_with_the_template_value(self):
        before_slots = self.conf_value("heavy_test_slots")
        self.repo.unset_conf("max_agents")
        self.repo.unset_conf("housekeep_interval_min")
        before = open(self.repo.path("agent.conf")).read()
        out = self.assertOk(self.settings("sync"))
        self.assertIn("added max_agents=4", out)
        self.assertIn("added housekeep_interval_min=120", out)
        self.assertEqual(self.conf_value("max_agents"), "4")
        self.assertEqual(self.conf_value("housekeep_interval_min"), "120")
        # every line that was already there stays byte-identical, in place
        after = open(self.repo.path("agent.conf")).read()
        self.assertTrue(after.startswith(before))
        self.assertEqual(self.conf_value("heavy_test_slots"), before_slots)

    def test_sync_twice_is_idempotent(self):
        self.repo.unset_conf("max_agents")
        self.assertOk(self.settings("sync"))
        after_first = open(self.repo.path("agent.conf")).read()
        out = self.assertOk(self.settings("sync"))
        self.assertEqual(out.strip(), "agent.conf is up to date")
        after_second = open(self.repo.path("agent.conf")).read()
        self.assertEqual(after_first, after_second)

    def test_nothing_missing_prints_up_to_date(self):
        # a conf with every template key (this repo's own agent.conf may lag
        # one key behind the template: it is the main manager's to sync)
        import shutil
        shutil.copy2(self.repo.plugin_path("bin", "agent.conf.default"), self.repo.path("agent.conf"))
        out = self.assertOk(self.settings("sync"))
        self.assertEqual(out.strip(), "agent.conf is up to date")


class TestSetvOnMissingKey(SettingsCase):
    def test_setv_appends_a_missing_known_key(self):
        self.repo.unset_conf("max_agents")
        result = self.settings("max_agents", "5")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("saved: max_agents=5", result.stdout)
        self.assertEqual(self.conf_value("max_agents"), "5")

    def test_setv_on_a_missing_known_key_still_validates(self):
        self.repo.unset_conf("max_agents")
        result = self.settings("max_agents", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(self.conf_value("max_agents"))

    def test_setv_on_an_unknown_key_still_refuses(self):
        result = self.settings("no_such_key", "x")
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(self.conf_value("no_such_key"))


class TestFromAWorktree(SettingsCase):
    def setUp(self):
        super(TestFromAWorktree, self).setUp()
        self.wt = os.path.join(self.repo.base, "wt_feature")
        subprocess.run(["git", "-C", self.repo.dir, "worktree", "add", "-q",
                        "-b", "feature", self.wt],
                       check=True, capture_output=True)
        self.main_conf = os.path.join(os.path.realpath(self.repo.dir),
                                      "agent.conf")
        self.wt_conf = os.path.join(self.wt, "agent.conf")
        self.assertTrue(os.path.exists(self.wt_conf),
                        "the worktree should carry its own tracked agent.conf")
        with open(self.wt_conf) as fh:
            self.wt_before = fh.read()

    def from_wt(self, *args):
        return self.repo.run("agent-settings.sh", *args, cwd=self.wt)

    def test_set_writes_the_main_copy_only(self):
        self.assertOk(self.from_wt("worker", "sonnet-5:high"))
        self.assertEqual(self.conf_value("worker"), "sonnet-5:high")
        with open(self.wt_conf) as fh:
            self.assertEqual(fh.read(), self.wt_before)

    def test_set_names_the_main_copy(self):
        out = self.assertOk(self.from_wt("worker", "sonnet-5:high"))
        self.assertIn(self.main_conf, out)
        self.assertIn("main repo", out)

    def test_show_names_the_main_copy(self):
        out = self.assertOk(self.from_wt())
        self.assertIn(self.main_conf, out)
        self.assertIn("main repo", out)

    def test_sync_names_the_main_copy(self):
        out = self.assertOk(self.from_wt("sync"))
        self.assertIn(self.main_conf, out)
        self.assertIn("main repo", out)

    def test_from_the_main_repo_there_is_no_note(self):
        for args in ((), ("worker", "sonnet-5:high"), ("sync",)):
            with self.subTest(args=args):
                out = self.assertOk(self.settings(*args))
                self.assertNotIn("main repo", out)


if __name__ == "__main__":
    unittest.main()
