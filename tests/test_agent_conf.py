"""agent_conf.py value checks (settings-configure, 2026-11-25).

The settings live in Configure now (tests/test_settings_configure.py holds that contract).
What stays here: validate_value(key, value) -> None when good, else a message naming the
allowed values. Used for every stored Configure value and for an old value before it is
moved. load/dumps/save/GROUPS/HINTS of agent.conf are gone with agent.conf.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import agent_conf


class TestValidateNumbers(unittest.TestCase):
    CASES = [
        ("max_usage_percent", 1, 100),
    ]

    def test_bounds_are_good(self):
        for key, low, high in self.CASES:
            for value in (low, high, (low + high) // 2):
                with self.subTest(key=key, value=value):
                    self.assertIsNone(agent_conf.validate_value(key, str(value)))

    def test_outside_bounds_is_bad(self):
        for key, low, high in self.CASES:
            for value in (low - 1, high + 1, -5):
                with self.subTest(key=key, value=value):
                    self.assertTrue(agent_conf.validate_value(key, str(value)))

    def test_error_message_names_the_range(self):
        for key, low, high in self.CASES:
            with self.subTest(key=key):
                message = agent_conf.validate_value(key, "999999")
                self.assertTrue(message)
                self.assertIn(str(low), message)
                self.assertIn(str(high), message)

    def test_not_a_whole_number_is_bad(self):
        for value in ("", "abc", "4.5", "four", "4 agents", " "):
            with self.subTest(value=value):
                self.assertTrue(agent_conf.validate_value("max_usage_percent", value))


class TestValidateRoles(unittest.TestCase):
    ROLE_KEYS = [
        "main_manager",
        "task_manager",
        "helper_model",
        "interior_designer",   # city-office: a helper role, it reads the Helper model setting
    ]

    def test_every_model_setting_accepts_a_good_value(self):
        for key in self.ROLE_KEYS:
            with self.subTest(key=key):
                self.assertIsNone(agent_conf.validate_value(key, "opus-5.5:medium"))

    def test_every_effort_level_is_accepted(self):
        for effort in ("low", "medium", "high", "xhigh", "max"):
            with self.subTest(effort=effort):
                self.assertIsNone(agent_conf.validate_value("helper_model", "opus-5:" + effort))

    def test_real_model_names_are_accepted(self):
        for value in ("fable-5.1:xhigh", "opus-5:xhigh", "haiku-4.5:low", "sonnet-5:medium"):
            with self.subTest(value=value):
                self.assertIsNone(agent_conf.validate_value("helper_model", value))

    def test_bad_shapes_are_rejected(self):
        for value in (
            "",
            "sonnet-5",
            "sonnet-5:",
            ":medium",
            "sonnet-5:ultra",
            "sonnet-5:MEDIUM",
            "sonnet 5:medium",
            "sonnet-5:medium:extra",
            "medium",
        ):
            with self.subTest(value=value):
                self.assertTrue(agent_conf.validate_value("helper_model", value))

    def test_error_message_names_the_effort_levels(self):
        message = agent_conf.validate_value("helper_model", "sonnet-5:ultra")
        self.assertTrue(message)
        for effort in ("low", "medium", "high", "xhigh", "max"):
            self.assertIn(effort, message)

    def test_effort_levels_are_the_ones_claude_takes(self):
        """`claude --effort` takes these five and nothing else."""
        self.assertEqual(agent_conf.EFFORT_LEVELS,
                         ["low", "medium", "high", "xhigh", "max"])


class TestValidatePermissionMode(unittest.TestCase):
    # five-fixes S1 (2026-11-05): the modes `claude --help` (2.1.318) lists for
    # --permission-mode, for permission_mode.
    # "default" is no claude mode any more: refused, never mapped.
    MODES = ("acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan")

    def test_the_six_modes_are_accepted(self):
        for key in ("permission_mode",):
            for mode in self.MODES:
                with self.subTest(key=key, mode=mode):
                    self.assertIsNone(agent_conf.validate_value(key, mode))

    def test_anything_else_is_rejected(self):
        for key in ("permission_mode",):
            for mode in ("", "Auto", "accept_edits", "yolo", "default plan", "bypass",
                         "bypasspermissions", "BypassPermissions", "bypassPermissions ",
                         "default", "Default", "dontask", "Manual",
                         "auto; touch pwned", "bypassPermissions$(touch pwned)"):
                with self.subTest(key=key, mode=mode):
                    self.assertTrue(agent_conf.validate_value(key, mode))

    def test_error_message_names_the_six_modes(self):
        for key in ("permission_mode",):
            message = agent_conf.validate_value(key, "yolo")
            self.assertTrue(message)
            for mode in self.MODES:
                with self.subTest(key=key, mode=mode):
                    self.assertIn(mode, message)


class TestValidateLanguage(unittest.TestCase):
    def test_zh_is_accepted(self):
        self.assertIsNone(agent_conf.validate_value("language", "zh"))

    def test_english_is_rejected(self):
        self.assertTrue(agent_conf.validate_value("language", "english"))


class TestRuntimeKey(unittest.TestCase):
    """Which shape this machine runs in. auto works it out fresh every time."""

    GOOD = ["auto", "orca", "plain", "cloud"]

    def test_every_good_value_passes(self):
        for value in self.GOOD:
            with self.subTest(value=value):
                self.assertIsNone(agent_conf.validate_value("runtime", value))

    def test_a_bad_value_is_refused(self):
        for value in ("Orca", "local", "", "auto ", "banana"):
            with self.subTest(value=value):
                self.assertTrue(agent_conf.validate_value("runtime", value))

    def test_the_message_names_the_four_choices(self):
        message = agent_conf.validate_value("runtime", "banana")
        for value in self.GOOD:
            with self.subTest(value=value):
                self.assertIn(value, message)

    def test_it_has_a_description(self):
        by = {x["key"]: x for x in agent_conf.SETTINGS}
        self.assertTrue(by["runtime"]["description"].strip())


if __name__ == "__main__":
    unittest.main()
