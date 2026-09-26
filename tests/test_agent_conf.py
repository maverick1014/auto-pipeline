"""Failing tests for agent_conf.py. Written by the task manager, before any code.

CONTRACT the worker must implement in agent_conf.py (module at repo root):

    load(path)                -> dict, key -> value (str). Insertion order = file order.
    dumps(conf)               -> str, the whole file text. Same order. Ends with "\n".
    save(conf, path)          -> None. Writes dumps(conf) to path.
    validate(conf)            -> dict, key -> error message (str). Empty dict = all good.
    validate_value(key, val)  -> error message (str), or None when the value is good.
    HINTS                     -> dict, known key -> one short plain-English hint.
    hint_for(key)             -> str, never empty, also for an unknown key.
    GROUPS                    -> list of (group_name, [key, ...]) in display order.
    group_of(key)             -> group name, or "other" for an unknown key.

Rules:
  - Unknown keys are kept, in place, and are always valid.
  - Blank lines and lines starting with "#" are skipped by load().
  - A line is split on the FIRST "=" only. Key and value are stripped.
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import agent_conf


REAL_KEYS = [
    "max_usage_percent",
    "heavy_test_slots",
    "max_agents",
    "monitor_interval_min",
    "stall_min",
    "main_manager",
    "fast_lane_deputy",
    "merge_deputy",
    "task_manager",
    "worker",
    "permission_mode",
    "auto_resume",
    "language",
    "runtime",
    "city_port",
    "city_idle_min",
    "city_governor_wait_sec",
    "city_relay_sec",
]

GOOD_CONF_TEXT = (
    "max_usage_percent=80\n"
    "heavy_test_slots=1\n"
    "max_agents=4\n"
    "monitor_interval_min=5\n"
    "stall_min=10\n"
    "main_manager=fable-5.1:xhigh\n"
    "fast_lane_deputy=sonnet-5:medium\n"
    "merge_deputy=sonnet-5:medium\n"
    "task_manager=opus-5:xhigh\n"
    "worker=sonnet-5:medium\n"
    "permission_mode=auto\n"
    "auto_resume=yes\n"
    "language=en\n"
    "runtime=auto\n"
    "city_port=4777\n"
    "city_idle_min=30\n"
    "city_governor_wait_sec=60\n"
    "city_relay_sec=5\n"
)


def write_tmp(text):
    fd, path = tempfile.mkstemp(prefix="agent_conf_", suffix=".conf")
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    return path


class TempConfCase(unittest.TestCase):
    def setUp(self):
        self.paths = []

    def tearDown(self):
        for path in self.paths:
            if os.path.exists(path):
                os.unlink(path)

    def make(self, text):
        path = write_tmp(text)
        self.paths.append(path)
        return path


class TestLoad(TempConfCase):
    def test_reads_every_key_and_value(self):
        conf = agent_conf.load(self.make(GOOD_CONF_TEXT))
        self.assertEqual(conf["max_usage_percent"], "80")
        self.assertEqual(conf["max_agents"], "4")
        self.assertEqual(conf["main_manager"], "fable-5.1:xhigh")
        self.assertEqual(conf["permission_mode"], "auto")

    def test_keeps_file_order(self):
        conf = agent_conf.load(self.make(GOOD_CONF_TEXT))
        self.assertEqual(list(conf.keys()), REAL_KEYS)

    def test_keeps_unknown_keys_in_place(self):
        text = "max_agents=4\nsome_new_key=hello world\npermission_mode=auto\n"
        conf = agent_conf.load(self.make(text))
        self.assertEqual(list(conf.keys()), ["max_agents", "some_new_key", "permission_mode"])
        self.assertEqual(conf["some_new_key"], "hello world")

    def test_strips_spaces_around_key_and_value(self):
        conf = agent_conf.load(self.make("  max_agents  =   4   \n"))
        self.assertEqual(conf["max_agents"], "4")

    def test_splits_on_first_equals_only(self):
        conf = agent_conf.load(self.make("note=a=b=c\n"))
        self.assertEqual(conf["note"], "a=b=c")

    def test_skips_blank_lines_and_comments(self):
        text = "# a comment\n\nmax_agents=4\n\n#another=1\npermission_mode=auto\n"
        conf = agent_conf.load(self.make(text))
        self.assertEqual(list(conf.keys()), ["max_agents", "permission_mode"])

    def test_empty_value_is_kept(self):
        conf = agent_conf.load(self.make("max_agents=\n"))
        self.assertEqual(conf["max_agents"], "")


class TestDumpsAndSave(TempConfCase):
    def test_round_trip_is_byte_identical(self):
        path = self.make(GOOD_CONF_TEXT)
        conf = agent_conf.load(path)
        self.assertEqual(agent_conf.dumps(conf), GOOD_CONF_TEXT)

    def test_dumps_ends_with_one_newline(self):
        out = agent_conf.dumps({"max_agents": "4"})
        self.assertEqual(out, "max_agents=4\n")

    def test_save_then_load_keeps_order_and_unknown_keys(self):
        path = self.make("max_agents=4\nmy_extra=keep me\npermission_mode=auto\n")
        conf = agent_conf.load(path)
        conf["max_agents"] = "9"
        agent_conf.save(conf, path)
        again = agent_conf.load(path)
        self.assertEqual(list(again.keys()), ["max_agents", "my_extra", "permission_mode"])
        self.assertEqual(again["max_agents"], "9")
        self.assertEqual(again["my_extra"], "keep me")


class TestValidateNumbers(unittest.TestCase):
    CASES = [
        ("max_usage_percent", 1, 100),
        ("heavy_test_slots", 1, 8),
        ("max_agents", 1, 16),
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
                self.assertTrue(agent_conf.validate_value("max_agents", value))


class TestValidateRoles(unittest.TestCase):
    ROLE_KEYS = [
        "main_manager",
        "fast_lane_deputy",
        "merge_deputy",
        "task_manager",
        "worker",
    ]

    def test_all_six_role_keys_accept_a_good_value(self):
        for key in self.ROLE_KEYS:
            with self.subTest(key=key):
                self.assertIsNone(agent_conf.validate_value(key, "sonnet-5:medium"))

    def test_every_effort_level_is_accepted(self):
        for effort in ("low", "medium", "high", "xhigh", "max"):
            with self.subTest(effort=effort):
                self.assertIsNone(agent_conf.validate_value("worker", "opus-5:" + effort))

    def test_real_model_names_are_accepted(self):
        for value in ("fable-5.1:xhigh", "opus-5:xhigh", "haiku-4.5:low", "sonnet-5:medium"):
            with self.subTest(value=value):
                self.assertIsNone(agent_conf.validate_value("main_manager", value))

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
                self.assertTrue(agent_conf.validate_value("worker", value))

    def test_error_message_names_the_effort_levels(self):
        message = agent_conf.validate_value("worker", "sonnet-5:ultra")
        self.assertTrue(message)
        for effort in ("low", "medium", "high", "xhigh", "max"):
            self.assertIn(effort, message)

    def test_effort_levels_are_the_ones_claude_takes(self):
        """`claude --effort` takes these five and nothing else."""
        self.assertEqual(agent_conf.EFFORT_LEVELS,
                         ["low", "medium", "high", "xhigh", "max"])


class TestValidatePermissionMode(unittest.TestCase):
    def test_the_four_modes_are_accepted(self):
        for mode in ("default", "acceptEdits", "auto", "plan"):
            with self.subTest(mode=mode):
                self.assertIsNone(agent_conf.validate_value("permission_mode", mode))

    def test_anything_else_is_rejected(self):
        for mode in ("", "Auto", "accept_edits", "yolo", "default plan"):
            with self.subTest(mode=mode):
                self.assertTrue(agent_conf.validate_value("permission_mode", mode))

    def test_error_message_names_the_four_modes(self):
        message = agent_conf.validate_value("permission_mode", "yolo")
        self.assertTrue(message)
        for mode in ("default", "acceptEdits", "auto", "plan"):
            self.assertIn(mode, message)


class TestValidateAutoResume(unittest.TestCase):
    def test_yes_is_accepted(self):
        self.assertIsNone(agent_conf.validate_value("auto_resume", "yes"))

    def test_no_is_accepted(self):
        self.assertIsNone(agent_conf.validate_value("auto_resume", "no"))

    def test_maybe_is_rejected(self):
        self.assertTrue(agent_conf.validate_value("auto_resume", "maybe"))


class TestValidateLanguage(unittest.TestCase):
    def test_zh_is_accepted(self):
        self.assertIsNone(agent_conf.validate_value("language", "zh"))

    def test_english_is_rejected(self):
        self.assertTrue(agent_conf.validate_value("language", "english"))


class TestValidateUnknownKey(unittest.TestCase):
    def test_unknown_key_is_always_good(self):
        for value in ("", "anything at all", "99999"):
            with self.subTest(value=value):
                self.assertIsNone(agent_conf.validate_value("some_new_key", value))


class TestValidateWholeConf(TempConfCase):
    def test_the_real_default_conf_has_no_errors(self):
        conf = agent_conf.load(self.make(GOOD_CONF_TEXT))
        self.assertEqual(agent_conf.validate(conf), {})

    def test_one_error_per_bad_key(self):
        conf = agent_conf.load(self.make(GOOD_CONF_TEXT))
        conf["max_agents"] = "99"
        conf["permission_mode"] = "yolo"
        errors = agent_conf.validate(conf)
        self.assertEqual(sorted(errors.keys()), ["max_agents", "permission_mode"])
        for message in errors.values():
            self.assertTrue(message)

    def test_repo_agent_conf_is_valid(self):
        conf = agent_conf.load(os.path.join(ROOT, "agent.conf"))
        self.assertEqual(agent_conf.validate(conf), {})
        self.assertEqual(list(conf.keys()), REAL_KEYS)


class TestHints(unittest.TestCase):
    def test_every_real_key_has_a_hint(self):
        for key in REAL_KEYS:
            with self.subTest(key=key):
                self.assertTrue(agent_conf.HINTS.get(key, "").strip())

    def test_hint_for_unknown_key_is_not_empty(self):
        self.assertTrue(agent_conf.hint_for("some_new_key").strip())

    def test_hint_for_known_key_matches_hints(self):
        self.assertEqual(agent_conf.hint_for("max_agents"), agent_conf.HINTS["max_agents"])


class TestMonitorBounds(unittest.TestCase):
    """The two keys the monitor and the resume script read (S1, S2)."""

    BOUNDS = {"monitor_interval_min": (1, 60), "stall_min": (1, 120)}

    def test_both_keys_are_numbers_with_bounds(self):
        for key, bounds in self.BOUNDS.items():
            with self.subTest(key=key):
                self.assertEqual(agent_conf.NUMBER_BOUNDS.get(key), bounds)

    def test_good_values_pass(self):
        for key, (low, high) in self.BOUNDS.items():
            for value in (low, (low + high) // 2, high):
                with self.subTest(key=key, value=value):
                    self.assertIsNone(agent_conf.validate_value(key, str(value)))

    def test_zero_is_refused(self):
        for key in self.BOUNDS:
            with self.subTest(key=key):
                self.assertTrue(agent_conf.validate_value(key, "0"))

    def test_over_the_top_bound_is_refused(self):
        for key, (_, high) in self.BOUNDS.items():
            with self.subTest(key=key):
                self.assertTrue(agent_conf.validate_value(key, str(high + 1)))

    def test_error_message_names_the_range(self):
        for key, (low, high) in self.BOUNDS.items():
            with self.subTest(key=key):
                message = agent_conf.validate_value(key, "0")
                self.assertIn(str(low), message)
                self.assertIn(str(high), message)

    def test_both_keys_sit_in_the_limits_group(self):
        for key in self.BOUNDS:
            with self.subTest(key=key):
                self.assertEqual(agent_conf.group_of(key), "limits")


class TestGroups(unittest.TestCase):
    def test_group_order_and_membership(self):
        self.assertEqual(
            agent_conf.GROUPS,
            [
                (
                    "limits",
                    [
                        "max_usage_percent",
                        "heavy_test_slots",
                        "max_agents",
                        "monitor_interval_min",
                        "stall_min",
                    ],
                ),
                (
                    "roles",
                    [
                        "main_manager",
                        "fast_lane_deputy",
                        "merge_deputy",
                        "task_manager",
                        "worker",
                    ],
                ),
                ("permission", ["permission_mode", "auto_resume", "language"]),
                ("runtime", ["runtime"]),
                ("city", ["city_port", "city_idle_min", "city_governor_wait_sec",
                          "city_relay_sec"]),
            ],
        )

    def test_every_real_key_sits_in_a_group(self):
        placed = [key for _, keys in agent_conf.GROUPS for key in keys]
        self.assertEqual(sorted(placed), sorted(REAL_KEYS))

    def test_group_of_known_and_unknown(self):
        self.assertEqual(agent_conf.group_of("max_agents"), "limits")
        self.assertEqual(agent_conf.group_of("worker"), "roles")
        self.assertEqual(agent_conf.group_of("permission_mode"), "permission")
        self.assertEqual(agent_conf.group_of("some_new_key"), "other")


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

    def test_it_has_a_hint(self):
        self.assertTrue(agent_conf.HINTS.get("runtime", "").strip())

    def test_it_sits_in_its_own_group(self):
        self.assertEqual(agent_conf.group_of("runtime"), "runtime")



class TestCityKeys(unittest.TestCase):
    """The keys bin/agent-city.sh reads: where the city listens, how long it
    lives with no browser open before it quits by itself, and how long the
    governor has to answer an agent's question before the owner gets it."""

    BOUNDS = {"city_port": (1024, 65535), "city_idle_min": (1, 240),
              "city_governor_wait_sec": (5, 3600), "city_relay_sec": (2, 60)}

    def test_bounds(self):
        for key, bounds in self.BOUNDS.items():
            with self.subTest(key=key):
                self.assertEqual(agent_conf.NUMBER_BOUNDS.get(key), bounds)

    def test_edges_pass_and_outside_fails(self):
        for key, (low, high) in self.BOUNDS.items():
            with self.subTest(key=key):
                self.assertIsNone(agent_conf.validate_value(key, str(low)))
                self.assertIsNone(agent_conf.validate_value(key, str(high)))
                self.assertTrue(agent_conf.validate_value(key, str(low - 1)))
                self.assertTrue(agent_conf.validate_value(key, str(high + 1)))

    def test_hints_and_group(self):
        for key in self.BOUNDS:
            with self.subTest(key=key):
                self.assertTrue(agent_conf.HINTS.get(key, "").strip())
                self.assertEqual(agent_conf.group_of(key), "city")

    def test_template_defaults(self):
        conf = agent_conf.load(os.path.join(ROOT, "bin", "agent.conf.default"))
        self.assertEqual(conf.get("city_port"), "4777")
        self.assertEqual(conf.get("city_idle_min"), "30")
        self.assertEqual(conf.get("city_governor_wait_sec"), "60")
        self.assertEqual(conf.get("city_relay_sec"), "5")

    def test_no_switch_for_the_governor_approving(self):
        # Owner decision 2026-09-24: permission requests are the owner's only.
        conf = agent_conf.load(os.path.join(ROOT, "bin", "agent.conf.default"))
        self.assertNotIn("city_governor_approves", conf)
        self.assertNotIn("city_governor_approves", agent_conf.HINTS)


if __name__ == "__main__":
    unittest.main()
