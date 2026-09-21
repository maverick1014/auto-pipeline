"""Failing tests for the two new agent.conf keys, through ./agent-settings.sh.

CONTRACT:

  agent.conf gains two keys, in the "limits" group, right after max_agents:

      monitor_interval_min=5      how often the monitor sweeps. 1 to 60
      stall_min=10                how long all three signals may stay quiet. 1 to 120

  agent_conf.py gets both in NUMBER_BOUNDS, HINTS and GROUPS["limits"], so
  ./agent-settings.sh accepts a good value and refuses a bad one without saving.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase

NEW_KEYS = {"monitor_interval_min": (1, 60), "stall_min": (1, 120)}


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
        self.assertEqual(self.conf_value("monitor_interval_min"), "5")
        self.assertEqual(self.conf_value("stall_min"), "10")

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
        result = self.settings("stall_min", "0")
        message = result.stdout + result.stderr
        self.assertIn("1", message)
        self.assertIn("120", message)


class TestKeyOrder(SettingsCase):
    def test_the_new_keys_sit_with_the_other_limits(self):
        keys = [line.split("=", 1)[0].strip()
                for line in open(self.repo.path("agent.conf")) if "=" in line]
        self.assertEqual(
            keys[:5],
            ["max_usage_percent", "heavy_test_slots", "max_agents",
             "monitor_interval_min", "stall_min"],
        )

    def test_saving_keeps_the_order(self):
        before = [line.split("=", 1)[0].strip()
                  for line in open(self.repo.path("agent.conf")) if "=" in line]
        self.assertOk(self.settings("stall_min", "20"))
        after = [line.split("=", 1)[0].strip()
                 for line in open(self.repo.path("agent.conf")) if "=" in line]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
