"""Tests of bin/agent-settings.sh and agent_conf.py: validation, permission modes, model words,
the YOU line, launch lines, the settings script.

requirements/settings-configure.md. One class per feature. Older task contracts: git log -p of this file.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import agent_conf
import json
import re
import shlex
import shutil
import subprocess
import tempfile
from unittest import mock
import agent_city as ac  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402
import stat
import test_agent_board as tb  # noqa: E402  (the module only: its tests stay in their own module)


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


MODES = ["acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan"]


MODE_KEYS = ("permission_mode",)


ENV = "AUTO_PIPELINE_USER_CONF"


class TmpCase(unittest.TestCase):
    """A temp folder, and a user file that is never the real ~/.claude one."""

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="five_fixes_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.user = os.path.join(self.base, "u", "auto-pipeline.conf")
        self.cfg = os.path.join(self.base, "cfg")
        patcher = mock.patch.dict(os.environ, {ENV: self.user, "CLAUDE_CONFIG_DIR": self.cfg})
        patcher.start()
        self.addCleanup(patcher.stop)

    def folder(self, name, conf):
        """settings-configure: CONF (old key=value text) goes into Configure (user level)."""
        from cityhelp import configure_text  # noqa: E402
        path = os.path.join(self.base, name)
        os.makedirs(path)
        configure_text(conf)
        return path

    def write_user(self, text):
        os.makedirs(os.path.dirname(self.user), exist_ok=True)
        with open(self.user, "w") as fh:
            fh.write(text)


def text(path):
    with open(path) as fh:
        return fh.read()


def flag(words, name):
    return words[words.index(name) + 1] if name in words else None


def claude_modes():
    """The --permission-mode choices of the installed claude, or None."""
    exe = shutil.which("claude")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=60,
                             stdin=subprocess.DEVNULL).stdout
    except Exception:
        return None
    m = re.search(r"--permission-mode\b.*?\(choices:(.*?)\)", out, re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


class TestModeList(unittest.TestCase):
    def test_the_list_is_the_cli_list(self):
        self.assertEqual(list(agent_conf.PERMISSION_MODES), MODES)

    def test_the_installed_claude_takes_every_mode(self):
        cli = claude_modes()
        if cli is None:
            self.skipTest("no claude on PATH")
        self.assertTrue(cli, "could not read the --permission-mode choices from `claude --help`")
        for mode in agent_conf.PERMISSION_MODES:
            with self.subTest(mode=mode):
                self.assertIn(mode, cli, "agent_conf would let a launcher pass a mode claude refuses")

    def test_the_six_are_accepted(self):
        for key in MODE_KEYS:
            for mode in MODES:
                with self.subTest(key=key, mode=mode):
                    self.assertIsNone(agent_conf.validate_value(key, mode))

    def test_default_is_refused_with_the_valid_list(self):
        for key in MODE_KEYS:
            with self.subTest(key=key):
                msg = agent_conf.validate_value(key, "default")
                self.assertTrue(msg, "default must be refused, never mapped")
                for mode in MODES:
                    self.assertIn(mode, msg)

    def test_near_misses_are_refused(self):
        for key in MODE_KEYS:
            for bad in ("Default", "default ", "manual ", "Manual", "dontask", "DontAsk", "dont_ask"):
                with self.subTest(key=key, value=bad):
                    self.assertTrue(agent_conf.validate_value(key, bad))

    def test_the_picker(self):
        by = {x["key"]: x for x in agent_conf.SETTINGS}
        self.assertEqual(by["permission_mode"]["options"], list(MODES))
        self.assertNotIn("default", by["permission_mode"]["options"])


class TestEffectiveRefusesDefault(TmpCase):
    """settings-configure: a stored "default" is refused, the setting default (auto) is used."""

    def configure(self, **options):
        os.makedirs(self.cfg, exist_ok=True)
        with open(os.path.join(self.cfg, "settings.json"), "w") as fh:
            json.dump({"pluginConfigs": {"auto-pipeline@auto-pipeline": {"options": options}}}, fh)

    def test_a_stored_default_is_not_set(self):
        self.configure(permission_mode="default")
        self.assertEqual(agent_conf.get("permission_mode"), "bypassPermissions")
        self.assertEqual(agent_conf.source("permission_mode"), "default")

    def test_an_old_user_file_is_ignored(self):
        self.write_user("permission_mode=manual\n")
        self.configure(permission_mode="plan")
        self.assertEqual(agent_conf.get("permission_mode"), "plan")

    def test_the_new_modes_are_effective(self):
        for mode in ("manual", "dontAsk"):
            with self.subTest(mode=mode):
                self.configure(permission_mode=mode)
                self.assertEqual(agent_conf.get("permission_mode"), mode)


class TestScriptsRefuseDefault(ScriptCase):
    script = "agent-settings.sh"

    def settings(self, *args):
        return self.repo.run("agent-settings.sh", *args)

    def test_the_script_never_saves(self):
        for args in (("permission_mode", "default"), ("permission_mode", "manual"),
                     ("--user", "permission_mode", "default")):
            with self.subTest(args=args):
                self.assertEqual(self.settings(*args).returncode, 1)
        self.assertFalse(os.path.exists(self.repo.path("agent.conf")))

    def test_get_never_prints_default(self):
        """dispatch and a Helper read the mode with `agent-settings.sh get`."""
        self.repo.set_conf("permission_mode", "default")
        self.assertEqual(self.assertOk(self.settings("get", "permission_mode")), "bypassPermissions (from default)\n")
        self.repo.set_conf("permission_mode", "manual")
        self.assertEqual(self.assertOk(self.settings("get", "permission_mode")), "manual (from Configure)\n")


class TestContextSuffix(unittest.TestCase):
    DECIDERS = ("main_manager", "task_manager")
    OK = ("opus-5.5[1m]", "claude-opus-5-5[1m]", "fable-5.1[1m]", "fable[1m]", "opus[1m]",
          "claude-fable-5-1[1m]", "opus-6[1m]", "opus-5.10[1m]", "claude-opus-5-5-20261101[1m]")
    LOW = ("sonnet-5[1m]", "sonnet[1m]", "sonnet-5.5[1m]", "claude-sonnet-5-5[1m]", "haiku-4.5[1m]",
           "opus-5[1m]", "opus-5.4[1m]", "claude-opus-4-1[1m]", "claude-opus-5-20260101[1m]", "mystery-7[1m]")
    BROKEN = ("opus-5.5[1m", "opus-5.5[]", "opus-5.5[1m]x", "opus-5.5[1m][1m]", "opus-5.5[",
              "opus-5.5 [1m]", "[1m]", "opus-5.5]")

    def test_deciders_take_the_suffix(self):
        for key in self.DECIDERS:
            for model in self.OK:
                for effort in ("medium", "xhigh", "max"):
                    with self.subTest(key=key, value=model + ":" + effort):
                        self.assertIsNone(agent_conf.validate_value(key, model + ":" + effort))

    def test_the_floor_is_unchanged_with_the_suffix(self):
        for key in self.DECIDERS:
            for model in self.LOW:
                with self.subTest(key=key, model=model):
                    self.assertEqual(agent_conf.validate_value(key, model + ":xhigh"), agent_conf.FLOOR_MESSAGE)
            with self.subTest(key=key, effort="low"):
                self.assertTrue(agent_conf.validate_value(key, "opus-5.5[1m]:low"))

    def test_executing_roles_take_the_suffix(self):
        for key in ("worker", "fast_lane_deputy", "merge_deputy"):
            for value in ("sonnet-5[1m]:medium", "haiku-4.5[1m]:low", "opus-5.5[1m]:high"):
                with self.subTest(key=key, value=value):
                    self.assertIsNone(agent_conf.validate_value(key, value))

    def test_a_broken_suffix_is_a_bad_shape(self):
        for key in agent_conf.ROLE_KEYS:
            for model in self.BROKEN:
                with self.subTest(key=key, model=model):
                    msg = agent_conf.validate_value(key, model + ":high")
                    self.assertTrue(msg)
                    self.assertNotEqual(msg, agent_conf.FLOOR_MESSAGE, "a broken suffix is a shape error")

    def test_the_old_values_are_unchanged(self):
        self.assertIsNone(agent_conf.validate_value("task_manager", "opus-5.5:xhigh"))
        self.assertIsNone(agent_conf.validate_value("main_manager", "fable-5.1:xhigh"))
        self.assertEqual(agent_conf.validate_value("task_manager", "opus-5.4:xhigh"), agent_conf.FLOOR_MESSAGE)
        self.assertEqual(agent_conf.validate_value("task_manager", "sonnet-5:xhigh"), agent_conf.FLOOR_MESSAGE)


class TestCliModelKeepsTheSuffixFlag(unittest.TestCase):
    TABLE = (("opus-5.5[1m]:xhigh", "opus[1m]"), ("opus-5.5[1m]", "opus[1m]"), ("fable-5.1[1m]:high", "fable[1m]"),
             ("fable[1m]", "fable[1m]"), ("opus[1m]:max", "opus[1m]"), ("sonnet-5[1m]:medium", "sonnet[1m]"),
             ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]"), ("claude-fable-5-1[1m]", "claude-fable-5-1[1m]"),
             ("mystery-7[1m]:high", "mystery-7[1m]"),
             ("opus-5.5:xhigh", "opus"), ("claude-opus-5-5:high", "claude-opus-5-5"))

    def test_the_rule(self):
        for spec, want in self.TABLE:
            with self.subTest(spec=spec):
                self.assertEqual(agent_conf.cli_model(spec), want)

    def test_the_command_line_says_the_same(self):
        for spec, want in self.TABLE:
            with self.subTest(spec=spec):
                done = subprocess.run([sys.executable, os.path.join(BIN, "agent_conf.py"), "cli-model", spec],
                                      capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
                self.assertEqual((done.returncode, done.stdout), (0, want + "\n"))


class TestSettingsWithTheSuffix(ScriptCase):
    script = "agent-settings.sh"

    def test_kept_and_refused(self):
        self.repo.set_conf("task_manager", "opus-5.5[1m]:xhigh")
        self.repo.set_conf("main_manager", "claude-opus-5-5[1m]:high")
        get = lambda key: self.assertOk(self.repo.run("agent-settings.sh", "get", key))
        self.assertEqual(get("task_manager"), "opus-5.5[1m]:xhigh (from Configure)\n")
        self.assertEqual(get("main_manager"), "claude-opus-5-5[1m]:high (from Configure)\n")
        self.repo.set_conf("task_manager", "sonnet-5[1m]:high")
        self.assertEqual(get("task_manager"), "opus-5.5:high (from default)\n")


class TestCityLine(TmpCase):
    CONF = "main_manager=opus-5.5:high\n"

    def words(self, conf):
        folder = self.folder("f%d" % len(os.listdir(self.base)), self.CONF + conf)
        return shlex.split(ac.agent_command("x Manager", folder))

    def test_default_never_reaches_a_local_line(self):
        words = self.words("permission_mode=default\n")
        self.assertEqual(flag(words, "--permission-mode"), "bypassPermissions")
        self.assertNotIn("default", words)

    def test_a_user_file_never_reaches_a_line(self):
        self.write_user("permission_mode=default\n")
        self.assertEqual(flag(self.words("permission_mode=plan\n"), "--permission-mode"), "plan")

    def test_manual_and_dont_ask_reach_the_line(self):
        self.assertEqual(flag(self.words("permission_mode=manual\n"), "--permission-mode"), "manual")
        self.assertEqual(flag(self.words("permission_mode=dontAsk\n"), "--permission-mode"), "dontAsk")


class TestCityLineWithTheSuffix(TmpCase):
    def test_the_model_word_keeps_the_suffix_quoted(self):
        for spec, want in (("opus-5.5[1m]:high", "opus[1m]"), ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]")):
            with self.subTest(spec=spec):
                folder = self.folder("s%d" % len(os.listdir(self.base)),
                                     "main_manager=%s\npermission_mode=auto\n" % spec)
                line = ac.agent_command("x Manager", folder)
                words = shlex.split(line)
                self.assertEqual((flag(words, "--model"), flag(words, "--effort")), (want, "high"))
                self.assertIn("--model '%s'" % want, line)


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


CHANGE = "/plugin -> Installed -> auto-pipeline -> Configure"


OLD_WORDS = ("agent.conf", "auto-pipeline.conf", "AUTO_PIPELINE_USER_CONF",
             "board_guard", "agent_conf.py effective", "danger_paths")


class SettingsCase(ScriptCase):
    script = "agent-settings.sh"

    def settings(self, *args):
        return self.repo.run("agent-settings.sh", *args)

    def stored(self):
        path = os.path.join(self.repo.claude_dir(), "settings.json")
        if not os.path.exists(path):
            return None
        return open(path).read()


class TestSettingsScript(SettingsCase):
    def test_no_args_is_the_table(self):
        self.repo.set_conf("language", "zh")
        out = self.assertOk(self.settings())
        lines = out.rstrip("\n").splitlines()
        self.assertIn("Language", out)
        self.assertIn("zh", out)
        self.assertEqual(lines[-2:], ["change: " + CHANGE, "core paths of this repo: agent_repo.conf"])
        self.assertNotIn("Danger paths", out)

    def test_show_is_the_same_table(self):
        self.assertEqual(self.settings("show").stdout, self.settings().stdout)

    def test_get(self):
        self.assertEqual(self.assertOk(self.settings("get", "language")), "en (from default)\n")
        self.repo.set_conf("language", "zh")
        self.assertEqual(self.assertOk(self.settings("get", "language")), "zh (from Configure)\n")
        self.assertEqual(self.assertOk(self.settings("get", "permission_mode")), "bypassPermissions (from default)\n")
        self.assertEqual(self.assertOk(self.settings("get", "stage_tests")), "20 (from constant)\n")

    def test_get_an_unknown_key_fails(self):
        r = self.settings("get", "level3_paths")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")

    def test_every_change_path_is_refused_and_writes_nothing(self):
        self.repo.set_conf("language", "zh")
        before = self.stored()
        for args in (("language", "en"), ("max_agents", "3"), ("--user", "permission_mode", "auto"),
                     ("menu",), ("sync",), ("set", "language", "en")):
            with self.subTest(args=args):
                r = self.settings(*args)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(CHANGE, r.stdout + r.stderr)
                self.assertEqual(self.stored(), before)
        self.assertFalse(os.path.exists(self.repo.path("agent.conf")))
        self.assertFalse(os.path.exists(self.repo.user_conf))

    def test_help_names_only_show_get_statusline(self):
        out = self.settings("--help").stdout
        self.assertIn("get <key>", out)
        self.assertIn("statusline", out)
        self.assertNotIn("--user", out)
        self.assertNotIn("sync", out)


class TestNothingReadsTheOldFiles(unittest.TestCase):
    def files(self):
        for top in ("bin", "hooks", "skills", "agents"):
            for folder, _, names in os.walk(os.path.join(ROOT, top)):
                if "node_modules" in folder or "/vendor" in folder:
                    continue
                for name in names:
                    if name.endswith((".png", ".jpg", ".glb", ".gltf", ".bin", ".woff", ".woff2")):
                        continue
                    if name in ("GLTFLoader.js", "three.module.js", "three.min.js"):
                        continue
                    yield os.path.join(folder, name)

    def test_no_reader_names_an_old_settings_word(self):
        hits = []
        for path in self.files():
            rel = os.path.relpath(path, ROOT)
            if rel == os.path.join("bin", "agent_conf.py"):
                continue
            try:
                text = open(path, encoding="utf-8").read()
            except Exception:
                continue
            for word in OLD_WORDS:
                if word in text:
                    hits.append("%s: %s" % (rel, word))
        self.assertEqual(hits, [])

    def test_the_template_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "bin", "agent.conf.default")))


HERE = os.path.dirname(os.path.abspath(__file__))


ZSH = shutil.which("zsh")


class ZshRun:
    """Run a launch line in a real zsh (no rc files) with a fake `claude` first
    on PATH that prints each argument on its own line, then ROLE=$AGENT_ROLE."""

    def __init__(self, base):
        self.bin = os.path.join(base, "fakebin")
        os.makedirs(self.bin, exist_ok=True)
        exe = os.path.join(self.bin, "claude")
        with open(exe, "w") as fh:
            fh.write('#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done\nprintf "ROLE=%s\\n" "$AGENT_ROLE"\n')
        os.chmod(exe, os.stat(exe).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def __call__(self, line):
        env = dict(os.environ)
        env["PATH"] = self.bin + os.pathsep + env.get("PATH", "")
        env.pop("AGENT_ROLE", None)
        done = subprocess.run([ZSH, "-f", "-c", line], capture_output=True, text=True, env=env,
                              timeout=30, stdin=subprocess.DEVNULL)
        return done.returncode, done.stdout.splitlines(), done.stderr


def you(args=(), env=None, settings=None, conf=None, role="task_manager"):
    return agent_conf.you_line(list(args), dict(env or {}), settings, dict(conf or {}), role)


MODEL_SETTINGS = {"claude-opus-5": {"effortLevel": "high"},
                  "claude-opus-5-5": {"effortLevel": "xhigh"},
                  "claude-sonnet-5-5": {"effortLevel": "medium"}}


class TestCliModelKeepsTheSuffix(unittest.TestCase):
    TABLE = (("opus-5.5[1m]:xhigh", "opus[1m]"), ("opus-5.5[1m]", "opus[1m]"),
             ("fable-5.1[1m]:high", "fable[1m]"), ("fable[1m]", "fable[1m]"), ("opus[1m]:max", "opus[1m]"),
             ("sonnet-5[1m]:medium", "sonnet[1m]"), ("haiku-4.5[1m]:low", "haiku[1m]"),
             ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]"), ("claude-opus-5-5[1m]", "claude-opus-5-5[1m]"),
             ("claude-fable-5-1[1m]", "claude-fable-5-1[1m]"), ("mystery-7[1m]:high", "mystery-7[1m]"),
             ("opus-5.5:xhigh", "opus"), ("fable-5.1", "fable"), ("claude-opus-5-5:high", "claude-opus-5-5"),
             ("mystery-7:high", "mystery-7"))

    def test_the_rule(self):
        for spec, want in self.TABLE:
            with self.subTest(spec=spec):
                self.assertEqual(agent_conf.cli_model(spec), want)

    def test_the_command_line_says_the_same(self):
        for spec, want in self.TABLE:
            with self.subTest(spec=spec):
                done = subprocess.run([sys.executable, os.path.join(BIN, "agent_conf.py"), "cli-model", spec],
                                      capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
                self.assertEqual((done.returncode, done.stdout), (0, want + "\n"), done.stderr)

    def test_every_accepted_output_is_a_form_the_cli_takes(self):
        """Only the forms the CLI evidence accepted: <family>[1m] or claude-...[1m]."""
        accepted = re.compile(r"^(opus|sonnet|haiku|fable)(\[1m\])?$|^claude-[a-z0-9-]+(\[1m\])?$")
        for spec in ("opus-5.5[1m]:xhigh", "fable-5.1[1m]:xhigh", "claude-opus-5-5[1m]:xhigh",
                     "claude-fable-5-1[1m]:max", "opus[1m]:high"):
            with self.subTest(spec=spec):
                self.assertRegex(agent_conf.cli_model(spec), accepted)


class TestCityLineRunsInZsh(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="model_suffix_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        patcher = mock.patch.dict(os.environ, {ENV: os.path.join(self.base, "u", "auto-pipeline.conf"),
                                               "CLAUDE_CONFIG_DIR": os.path.join(self.base, "cfg")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def line(self, spec):
        # settings-configure: the Main manager model setting (Configure), user level
        from cityhelp import configure_text  # noqa: E402
        folder = os.path.join(self.base, "f%d" % len(os.listdir(self.base)))
        os.makedirs(folder)
        configure_text("main_manager=%s\npermission_mode=auto\n" % spec)
        return ac.agent_command("x Manager", folder)

    def test_the_model_word_keeps_the_suffix(self):
        for spec, want in (("opus-5.5[1m]:high", "opus[1m]"), ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]"),
                           ("fable-5.1[1m]:xhigh", "fable[1m]")):
            with self.subTest(spec=spec):
                words = shlex.split(self.line(spec))
                self.assertEqual(flag(words, "--model"), want)

    @unittest.skipUnless(ZSH, "no zsh on PATH")
    def test_zsh_runs_the_line_without_a_glob_error(self):
        run = ZshRun(self.base)
        for spec, want in (("opus-5.5[1m]:high", "opus[1m]"), ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]")):
            with self.subTest(spec=spec):
                line = self.line(spec)
                code, out, err = run(line)
                self.assertNotIn("no matches found", err)
                self.assertEqual(code, 0, err)
                self.assertEqual(out[:-1], shlex.split(line)[1:])
                self.assertEqual(flag(out, "--model"), want)


class TestYouLineWithTheSuffix(unittest.TestCase):
    def test_flags_show_the_suffix(self):
        self.assertEqual(you(["claude", "--model", "opus[1m]", "--effort", "xhigh"]),
                         "YOU: opus[1m] xhigh (model: flag, effort: flag)")
        self.assertEqual(you(["claude", "--model=claude-opus-5-5[1m]", "--effort=high"]),
                         "YOU: claude-opus-5-5[1m] high (model: flag, effort: flag)")

    def test_the_full_id_effort_ignores_the_suffix(self):
        self.assertEqual(you(["claude", "--model", "claude-opus-5-5[1m]"], {}, {"modelSettings": MODEL_SETTINGS}),
                         "YOU: claude-opus-5-5[1m] xhigh (model: flag, effort: settings.json)")

    def test_an_exact_suffixed_entry_wins(self):
        table = dict(MODEL_SETTINGS, **{"claude-opus-5-5[1m]": {"effortLevel": "max"}})
        self.assertEqual(you(["claude", "--model", "claude-opus-5-5[1m]"], {}, {"modelSettings": table}),
                         "YOU: claude-opus-5-5[1m] max (model: flag, effort: settings.json)")

    def test_the_family_word_effort_ignores_the_suffix(self):
        self.assertEqual(you(["claude", "--model", "opus[1m]"], {}, {"modelSettings": MODEL_SETTINGS}),
                         "YOU: opus[1m] xhigh (model: flag, effort: settings.json)")


class TestYouCliWithTheSuffix(ScriptCase):
    def test_a_real_process(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)",
                                 "--model", "opus[1m]", "--effort", "xhigh"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        r = subprocess.run([sys.executable, os.path.join(BIN, "agent_conf.py"), "you", "task_manager",
                            str(proc.pid)],
                           capture_output=True, text=True, env=self.repo._env(None), timeout=30)
        self.assertEqual((r.returncode, r.stdout), (0, "YOU: opus[1m] xhigh (model: flag, effort: flag)\n"))


class TestSettingsWritesWeights(tb.BoardCase):
    script = "agent-settings.sh"

    def test_set_is_refused(self):
        r = self.repo.run("agent-settings.sh", "stage_workers", "50")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(self.repo.path("agent.conf")))


if __name__ == "__main__":
    unittest.main()
