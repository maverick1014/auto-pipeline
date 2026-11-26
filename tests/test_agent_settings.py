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
from scripthelp import ScriptRepo  # noqa: E402
from scripthelp import ROOT as ROOT_wb  # noqa: E402
from scripthelp import BIN as BIN_rf  # noqa: E402


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
        for args in (("language", "en"), ("max_usage_percent", "30"), ("--user", "permission_mode", "auto"),
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


class TestRepoConfKeys(unittest.TestCase):
    """level3_paths / level4_paths in agent_repo.conf: comma-separated globs (owner 1A 2026-11-25)."""

    def test_good_values(self):
        for value in ("", "src/core/", "src/core/,lib/money/**", "*.sql", " api/ , db/ ",
                      "core", "src/*/ledger"):
            for key in ("level3_paths", "level4_paths"):
                with self.subTest(key=key, value=value):
                    self.assertIsNone(agent_conf.validate_value(key, value))

    def test_bad_values(self):
        for value in ("/etc/", "src/../x", "a b", "api/,,db/", ",", "api/, /db"):
            for key in ("level3_paths", "level4_paths"):
                with self.subTest(key=key, value=value):
                    self.assertTrue(agent_conf.validate_value(key, value))

    def test_they_are_no_settings(self):
        for key in ("level3_paths", "level4_paths", "danger_paths"):
            with self.assertRaises(KeyError):
                agent_conf.get(key, {})


class TestNoAdhdKey(ScriptCase):
    script = "agent-settings.sh"

    def test_no_adhd_key_anywhere(self):
        import agent_conf
        self.assertNotIn("adhd", [x["key"] for x in agent_conf.SETTINGS])
        self.assertNotIn("adhd", agent_conf.CONSTANTS)

    def test_settings_does_not_know_it(self):
        result = self.repo.run("agent-settings.sh", "adhd", "off")
        self.assertNotEqual(result.returncode, 0)


class TestWorkingBranchName(unittest.TestCase):
    """Section 34 (owner 2026-11-25): per person, worked out once per clone and stored."""

    def setUp(self):
        self.repo = ScriptRepo()
        self.addCleanup(self.repo.cleanup)
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        import agent_conf
        self.ac = agent_conf

    def git(self, *args):
        return subprocess.run(["git", "-C", self.repo.dir] + list(args), capture_output=True, text=True).stdout.strip()

    def resolve(self):
        env = self.repo._env(None)
        r = subprocess.run([sys.executable, os.path.join(self.repo.plugin, "bin", "agent_conf.py"), "working-branch",
                            self.repo.dir], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_the_default_form(self):
        self.assertEqual(self.ac.WORKING_BRANCH_DEFAULT, "ap-main-<name>")

    def test_the_git_user_name_cleaned(self):
        self.git("config", "user.name", "Maverick O'Neil  Jr.")
        self.assertEqual(self.resolve(), "ap-main-maverick-o-neil-jr")

    def test_stored_once_per_clone(self):
        self.git("config", "user.name", "Maverick")
        self.assertEqual(self.resolve(), "ap-main-maverick")
        self.assertEqual(self.git("config", "--local", "--get", "auto-pipeline.workingbranch"), "ap-main-maverick")
        self.git("config", "user.name", "Somebody Else")
        self.assertEqual(self.resolve(), "ap-main-maverick", "never derived again")

    def test_a_fixed_team_name(self):
        self.repo.set_conf("working_branch", "team-main")
        self.assertEqual(self.resolve(), "team-main")


class TestQuietKey(unittest.TestCase):
    """settings-configure: "Stuck: Consider stuck after (min)" in Configure (watch_quiet_min)."""

    def test_g_the_setting_is_15_in_1_to_240(self):
        sys.path.insert(0, os.path.join(ROOT_wb, "bin"))
        import agent_conf
        by = {x["key"]: x for x in agent_conf.SETTINGS}
        field = by["watch_quiet_min"]
        self.assertEqual((field["default"], field["min"], field["max"]), (15, 1, 240))
        self.assertEqual(field["title"], "Stuck: Consider stuck after (min)")


class TestQuietKeySettings(ScriptCase):
    script = "agent-settings.sh"

    def test_g_the_board_reads_the_setting_and_the_script_never_writes_it(self):
        self.repo.set_conf("watch_quiet_min", 30)
        self.assertEqual(self.assertOk(self.repo.run("agent-settings.sh", "get", "watch_quiet_min")),
                         "30 (from Configure)\n")
        self.assertEqual(self.repo.run("agent-settings.sh", "watch_quiet_min", "30").returncode, 1)


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


class TestF4ProductionIsNeverTheWorkingBranch(unittest.TestCase):
    def test_main_as_the_setting_falls_back(self):
        repo = ScriptRepo()
        self.addCleanup(repo.cleanup)
        subprocess.run(["git", "-C", repo.dir, "branch", "-M", "main"], check=True, capture_output=True)
        repo.set_conf("working_branch", "main")
        r = subprocess.run([sys.executable, os.path.join(repo.plugin, "bin", "agent_conf.py"), "working-branch", repo.dir],
                           capture_output=True, text=True, env=repo._env(None))
        self.assertEqual(r.stdout.strip(), "ap-main-t")
        self.assertIn('working branch: "main" is the production branch; using ap-main-t', r.stderr)


class TestG4AStoredProductionNameIsNeverUsed(unittest.TestCase):
    def test_stored_main(self):
        repo = ScriptRepo()
        self.addCleanup(repo.cleanup)
        subprocess.run(["git", "-C", repo.dir, "branch", "-M", "main"], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo.dir, "config", "--local", "auto-pipeline.workingbranch", "main"], check=True)
        old = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(old)))
        os.environ.update(repo._env(None))
        sys.path.insert(0, BIN_rf)
        import agent_conf
        self.assertIsNone(agent_conf.working_branch(repo.dir))
        self.assertEqual(agent_conf.working_branch(repo.dir, derive=True), "ap-main-t")


class TestF11(unittest.TestCase):
    def test_docstring(self):
        head = read("bin", "agent_conf.py").split('"""')[1]
        self.assertNotIn("16 settings", head)


class TestFloor(unittest.TestCase):
    OK_MODELS = ("fable-5.1", "fable", "fable-6", "claude-fable-5-1", "opus", "opus-5.5", "opus-5.6",
                 "opus-6", "opus-6.0", "opus-5.10", "claude-opus-5-5", "claude-opus-6",
                 "claude-opus-5-5-20261101")
    LOW_MODELS = ("opus-5", "opus-5.4", "opus-4.7", "claude-opus-4-1", "claude-opus-5-20260101",
                  "sonnet-5", "sonnet-5.5", "sonnet", "haiku-4.5", "claude-sonnet-5-5", "mystery-7", "gpt-5")

    def test_deciding_roles_at_or_above(self):
        for key in ("main_manager", "task_manager"):
            for model in self.OK_MODELS:
                for effort in ("medium", "high", "xhigh", "max"):
                    with self.subTest(key=key, value=model + ":" + effort):
                        self.assertIsNone(agent_conf.validate_value(key, model + ":" + effort))

    def test_deciding_roles_below_the_model_floor(self):
        for key in ("main_manager", "task_manager"):
            for model in self.LOW_MODELS:
                with self.subTest(key=key, model=model):
                    msg = agent_conf.validate_value(key, model + ":xhigh")
                    self.assertTrue(msg)
                    for word in ("Opus 5.5", "Fable", "medium"):
                        self.assertIn(word, msg)

    def test_deciding_roles_below_the_effort_floor(self):
        for key in ("main_manager", "task_manager"):
            for model in ("opus-5.5", "fable-5.1"):
                with self.subTest(key=key, model=model):
                    self.assertTrue(agent_conf.validate_value(key, model + ":low"))

    def test_bad_shapes_still_refused(self):
        for value in ("opus-5.5", "fable-5.1:ultra", ":high", ""):
            with self.subTest(value=value):
                self.assertTrue(agent_conf.validate_value("task_manager", value))

    def test_executing_roles_unchanged(self):
        for key in ("worker", "fast_lane_deputy", "merge_deputy"):
            for value in ("sonnet-5:low", "haiku-4.5:low", "mystery-7:medium", "opus-5.5:xhigh"):
                with self.subTest(key=key, value=value):
                    self.assertIsNone(agent_conf.validate_value(key, value))

    def test_descriptions_name_the_floor(self):
        by = {x["key"]: x for x in agent_conf.SETTINGS}
        for key in ("main_manager", "task_manager"):
            with self.subTest(key=key):
                for word in ("Opus 5.5", "Fable", "medium"):
                    self.assertIn(word, by[key]["description"])

    def test_the_shipped_defaults_and_pickers_pass(self):
        for s_ in agent_conf.SETTINGS:
            with self.subTest(key=s_["key"]):
                self.assertIsNone(agent_conf.validate_value(s_["key"], s_["default"]))
                for pick in s_.get("options", []):
                    self.assertIsNone(agent_conf.validate_value(s_["key"], pick))


# five-fixes S1: the modes `claude --help` lists; "default" is not one
FIVE = ("acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan")


class TestConfKeys(unittest.TestCase):
    def test_bypass_is_a_mode(self):
        for key in ("permission_mode",):
            with self.subTest(key=key):
                self.assertIsNone(agent_conf.validate_value(key, "bypassPermissions"))
                self.assertTrue(agent_conf.validate_value(key, "yolo"))

    def test_the_list(self):
        self.assertEqual(list(agent_conf.PERMISSION_MODES), list(FIVE))

    def test_the_picker(self):
        by = {x["key"]: x for x in agent_conf.SETTINGS}
        self.assertEqual(by["permission_mode"]["options"], list(FIVE))
        self.assertNotIn("cloud_permission_mode", by)


ORDER = [
    ("language", "Basic: Language", "string", "en"),
    ("runtime", "Basic: Runtime", "string", "auto"),
    ("auto_update", "Basic: Auto update", "boolean", True),
    ("main_manager", "Models: Main manager model", "string", "opus-5.5:high"),
    ("task_manager", "Models: Task manager model", "string", "opus-5.5:high"),
    ("reviewer_model", "Models: Reviewer model", "string", "opus-5.5:high"),   # owner 2A 2026-11-25: new
    ("helper_model", "Models: Helper model", "string", "sonnet-5:medium"),
    # max_agents: gone (owner 2026-11-25, TELL bd4e87ee): no count caps, the memory rule admits a pane
    ("max_usage_percent", "Load: Max memory %", "number", 80),
    # heavy_test_slots: gone (owner 2026-11-25, TELL 076c1faf): no slots, a memory gate (tests/test_agent_room.py)
    ("permission_mode", "Permissions: Permission mode", "string", "bypassPermissions"),   # owner order 2026-11-25
    ("auto_resume", "Permissions: Auto resume", "boolean", True),
    ("todo_before_agent", "Rules: Todo before agent", "boolean", True),
    # owner 2026-11-25 (TELL 76bfcc8f): new; the name is not final: one constant (TELL 84fbcf51)
    ("working_branch", "Flow: Working branch", "string", agent_conf.WORKING_BRANCH_DEFAULT),
    ("watch_quiet_min", "Stuck: Consider stuck after (min)", "number", 15),
    ("housekeep_interval_min", "Stuck: Tidy every (min)", "number", 120),
    # owner order 2026-11-25 (TELL 9bb87b13): the auto clear waits until no human typed for this long
    ("clear_quiet_min", "Context: Auto clear after quiet (min)", "number", 30),
    ("city_port", "City: City port", "number", 4777),
    ("city_idle_min", "City: City auto close (min)", "number", 30),
    # owner 2026-11-26 (agent-files, TELL 3a14d2f4 and 50d02f90): the person's default; a repo value wins
    ("task_files", "Team: Task files in git", "string", "local"),
    ("task_take", "Team: Who may take a task", "string", "owner"),
    ("data_branch", "Team: Data branch", "string", "ap-data"),
    # owner 2026-11-26 (nightly-on-machine): a personal environment name, never in a repo file
    ("full_run_machine", "Load: Full run machine", "string", ""),
    # owner 2026-11-26 (leader-relay, TELL 2d1f9c06): empty = an approval relayed by Leader is refused
    ("leader_transcript_folder", "Approval: Leader transcript folder", "string", ""),
]


CONSTANTS = {
    "stage_brief": 1, "stage_register": 1, "stage_mock": 4, "stage_tests": 20,
    "stage_workers": 40, "stage_verify": 15, "stage_push": 2, "stage_report": 2,
    "stage_e2e": 10, "stage_merge": 5, "board_watch_sec": 60, "progress_eta_min_pct": 20,
    "statusline_refresh_sec": 60, "city_governor_wait_sec": 60, "estimate_target_pct": 50,
    "estimate_bias_min": 5, "estimate_big_min": 120, "state_keep_hours": 24,
    "state_warn_lines": 300, "state_header_lines": 40, "state_trim_auto": "on",
    "compact_clear_at": 2, "compact_clear_check_sec": 30, "cleanup_days": 14,
    "docs_keep": "", "owner_order_hours": 24, "owner_order_min_chars": 20,
    "check_budget_s": 60,   # check-blocks: BUILD and GUARD TESTS per task only under it
    "unused_pane_min": 30,  # check-blocks slice 8: the sweep closes a pane that never got a prompt, idle over it
    "nightly_hour": 22, "light_test_s": 120, "light_test_mb": 1024,   # check-blocks section 15 (owner 1A)
    "verify_box_min": 15,   # check-blocks section 19/21: the run or browser check time box
    "share_net_timeout_s": 15, "share_offline_min": 5,   # agent-files fix order 1 D: one network timeout, the offline marker
    "leader_transcript_max_mb": 200,   # leader-relay: a larger Leader transcript is refused, not read
}


CHANGE_LINE = "change: /plugin -> Installed -> auto-pipeline -> Configure"


CORE_LINE = "core paths of this repo: agent_repo.conf"   # owner 1A 2026-11-25


MOVED_BOTH = "moved level3_paths, level4_paths to agent_repo.conf (repo file, commit it)"


# A fake `claude` on PATH. Every call appends {"args", "cwd", "stdin"} to calls.jsonl.
# mode file "ok": `plugin configure <id> --values-stdin` merges the JSON into
# settings.json pluginConfigs[<id>].options (like the real one); `plugin update` exits 0.
# mode file "fail": prints "boom" on stderr, exit 1.
CLAUDE_STUB = r'''#!%(py)s
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
data = sys.stdin.read() if "--values-stdin" in sys.argv else ""
with open(os.path.join(here, "calls.jsonl"), "a") as fh:
    fh.write(json.dumps({"args": sys.argv[1:], "cwd": os.getcwd(), "stdin": data}) + "\n")
mode = open(os.path.join(here, "mode")).read().strip()
if mode != "ok":
    sys.stderr.write("boom\n"); sys.exit(1)
if sys.argv[1:3] == ["plugin", "configure"] and "--values-stdin" in sys.argv:
    cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.environ["HOME"], ".claude")
    path = os.path.join(cfg, "settings.json")
    try:
        settings = json.load(open(path))
    except Exception:
        settings = {}
    opts = settings.setdefault("pluginConfigs", {}).setdefault(sys.argv[3], {}).setdefault("options", {})
    opts.update(json.loads(data))
    json.dump(settings, open(path, "w"))
    print("Configuration saved. Restart Claude Code to apply it.")
'''


class Home:
    """A throwaway HOME with its own .claude dir; env() is what a script sees."""

    def __init__(self):
        self.base = tempfile.mkdtemp(prefix="settings_configure_")
        self.home = os.path.join(self.base, "home")
        self.cfg = os.path.join(self.home, ".claude")
        os.makedirs(os.path.join(self.cfg, "plugins"))
        self.repo = os.path.join(self.base, "repo")
        os.makedirs(self.repo)
        self.stub = os.path.join(self.base, "stubbin")
        os.makedirs(self.stub)
        path = os.path.join(self.stub, "claude")
        with open(path, "w") as fh:
            fh.write(CLAUDE_STUB % {"py": sys.executable})
        os.chmod(path, 0o755)
        self.claude_mode("ok")

    def close(self):
        shutil.rmtree(self.base, True)

    def claude_mode(self, mode):
        with open(os.path.join(self.stub, "mode"), "w") as fh:
            fh.write(mode)

    def calls(self):
        path = os.path.join(self.stub, "calls.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("CLAUDE_PLUGIN_OPTION_")
               and k not in ("CLAUDE_CONFIG_DIR", "AUTO_PIPELINE_USER_CONF")}
        env["HOME"] = self.home
        env["PATH"] = self.stub + os.pathsep + env.get("PATH", "/usr/bin:/bin")
        env.update(extra)
        return env

    def options(self):
        try:
            with open(os.path.join(self.cfg, "settings.json")) as fh:
                return json.load(fh)["pluginConfigs"]["auto-pipeline@auto-pipeline"]["options"]
        except Exception:
            return {}

    def configure(self, options, plugin_id="auto-pipeline@auto-pipeline", other=None):
        data = {"theme": "dark", "pluginConfigs": {plugin_id: {"options": options}}}
        if other:
            data["pluginConfigs"].update(other)
        with open(os.path.join(self.cfg, "settings.json"), "w") as fh:
            json.dump(data, fh)

    def write(self, rel, text):
        path = os.path.join(self.base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
        return path

    def installed(self, entries):
        with open(os.path.join(self.cfg, "plugins", "installed_plugins.json"), "w") as fh:
            json.dump({"version": 2, "plugins": {
                "auto-pipeline@auto-pipeline": entries,
                "other@other": [{"scope": "project", "projectPath": self.repo, "version": "0.1.0"}],
            }}, fh)


def run_cli(args, env, script="agent_conf.py"):
    return subprocess.run([sys.executable, os.path.join(BIN, script)] + args,
                          capture_output=True, text=True, env=env, timeout=30)


class TestSchema(unittest.TestCase):
    def test_plugin_id(self):
        self.assertEqual(agent_conf.PLUGIN_ID, "auto-pipeline@auto-pipeline")

    def test_sixteen_settings_in_the_brief_order(self):
        got = [(s["key"], s["title"], s["type"], s["default"]) for s in agent_conf.SETTINGS]
        self.assertEqual(got, ORDER)

    def test_every_setting_has_a_plain_description(self):
        for s in agent_conf.SETTINGS:
            self.assertTrue(s["description"].strip(), s["key"])
            self.assertLessEqual(len(s["description"]), 200, s["key"])

    def test_pickers(self):
        by = {s["key"]: s for s in agent_conf.SETTINGS}
        self.assertEqual(by["runtime"]["options"], ["auto", "orca", "plain", "cloud"])
        self.assertIn("auto", by["permission_mode"]["options"])
        self.assertIn("bypassPermissions", by["permission_mode"]["options"])
        for key in ("main_manager", "task_manager"):
            opts = by[key]["options"]
            self.assertEqual(opts[0], "opus-5.5:high", key)
            self.assertIn("opus-5.5:xhigh", opts, key)
            for spec in opts:
                self.assertIsNone(agent_conf.validate_value("main_manager", spec), spec)
        self.assertEqual(by["helper_model"]["options"][0], "sonnet-5:medium")

    def test_number_bounds(self):
        by = {s["key"]: s for s in agent_conf.SETTINGS}
        self.assertEqual((by["max_usage_percent"]["min"], by["max_usage_percent"]["max"]), (1, 100))
        self.assertEqual((by["housekeep_interval_min"]["min"], by["housekeep_interval_min"]["max"]), (0, 1440))
        self.assertEqual((by["city_port"]["min"], by["city_port"]["max"]), (1024, 65535))
        self.assertEqual((by["clear_quiet_min"]["min"], by["clear_quiet_min"]["max"]), (0, 1440))

    def test_plugin_json_user_config_is_built_from_settings(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest["userConfig"], agent_conf.user_config())
        self.assertEqual(list(manifest["userConfig"]), [k for k, _, _, _ in ORDER])

    def test_user_config_uses_only_fields_claude_code_knows(self):
        known = {"type", "title", "description", "default", "options", "min", "max"}
        for key, field in agent_conf.user_config().items():
            self.assertLessEqual(set(field), known, key)
            if "options" in field:
                self.assertEqual(field["type"], "string", key)
                self.assertIn(field["default"], field["options"], key)
            if "min" in field:
                self.assertEqual(field["type"], "number", key)

    def test_constants(self):
        self.assertEqual(agent_conf.CONSTANTS, CONSTANTS)

    def test_no_constant_is_a_setting(self):
        keys = {s["key"] for s in agent_conf.SETTINGS}
        self.assertFalse(keys & set(agent_conf.CONSTANTS))

    def test_template_file_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(BIN, "agent.conf.default")))

    def test_repo_has_no_agent_conf(self):
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "agent.conf"],
                             capture_output=True, text=True).stdout
        self.assertEqual(out.strip(), "")


class TestGet(unittest.TestCase):
    def setUp(self):
        self.h = Home()

    def tearDown(self):
        self.h.close()

    def test_nothing_set_gives_every_default(self):
        env = self.h.env()
        for key, _, _, default in ORDER:
            self.assertEqual(agent_conf.get(key, env), default, key)
            self.assertEqual(agent_conf.source(key, env), "default", key)

    def test_configure_value_wins(self):
        self.h.configure({"language": "zh", "max_usage_percent": 60, "auto_resume": False})
        env = self.h.env()
        self.assertEqual(agent_conf.get("language", env), "zh")
        self.assertEqual(agent_conf.get("max_usage_percent", env), 60)
        self.assertIs(agent_conf.get("auto_resume", env), False)
        self.assertEqual(agent_conf.source("language", env), "Configure")

    def test_numbers_and_booleans_stored_as_text(self):
        self.h.configure({"max_usage_percent": "60", "auto_update": "false", "todo_before_agent": "true"})
        env = self.h.env()
        self.assertEqual(agent_conf.get("max_usage_percent", env), 60)
        self.assertIs(agent_conf.get("auto_update", env), False)
        self.assertIs(agent_conf.get("todo_before_agent", env), True)

    def test_claude_config_dir_is_used(self):
        other = os.path.join(self.h.base, "cfg2")
        os.makedirs(other)
        with open(os.path.join(other, "settings.json"), "w") as fh:
            json.dump({"pluginConfigs": {"auto-pipeline@auto-pipeline": {"options": {"city_port": 5000}}}}, fh)
        self.h.configure({"city_port": 6000})
        self.assertEqual(agent_conf.get("city_port", self.h.env(CLAUDE_CONFIG_DIR=other)), 5000)

    def test_env_option_when_configure_has_none(self):
        env = self.h.env(CLAUDE_PLUGIN_OPTION_LANGUAGE="ms", CLAUDE_PLUGIN_OPTION_MAX_USAGE_PERCENT="30")
        self.assertEqual(agent_conf.get("language", env), "ms")
        self.assertEqual(agent_conf.get("max_usage_percent", env), 30)
        self.assertEqual(agent_conf.source("language", env), "env")

    def test_file_beats_env(self):
        self.h.configure({"max_usage_percent": 60})
        env = self.h.env(CLAUDE_PLUGIN_OPTION_MAX_USAGE_PERCENT="40")
        self.assertEqual(agent_conf.get("max_usage_percent", env), 60)

    def test_other_plugins_options_are_not_read(self):
        self.h.configure({}, other={"x@y": {"options": {"language": "zh"}}})
        self.assertEqual(agent_conf.get("language", self.h.env()), "en")

    def test_bad_settings_json_gives_defaults_and_a_warning(self):
        with open(os.path.join(self.h.cfg, "settings.json"), "w") as fh:
            fh.write("{not json")
        env = self.h.env()
        self.assertEqual(agent_conf.get("max_usage_percent", env), 80)
        self.assertTrue(any("settings.json" in w for w in agent_conf.warnings(env)))

    def test_out_of_range_gives_default_and_warning(self):
        self.h.configure({"max_usage_percent": 400})
        env = self.h.env()
        self.assertEqual(agent_conf.get("max_usage_percent", env), 80)
        self.assertEqual(agent_conf.source("max_usage_percent", env), "default")
        lines = agent_conf.warnings(env)
        self.assertEqual(len(lines), 1)
        self.assertIn("max_usage_percent=400", lines[0])
        self.assertIn("1-100", lines[0])
        self.assertIn("default 80", lines[0])

    def test_bad_picker_value_gives_default(self):
        self.h.configure({"runtime": "docker", "permission_mode": "yolo"})
        env = self.h.env()
        self.assertEqual(agent_conf.get("runtime", env), "auto")
        self.assertEqual(agent_conf.get("permission_mode", env), "bypassPermissions")
        self.assertEqual(len(agent_conf.warnings(env)), 2)

    def test_manager_below_the_decider_floor_is_refused(self):
        self.h.configure({"main_manager": "sonnet-5:high", "task_manager": "opus-5.5:low"})
        env = self.h.env()
        self.assertEqual(agent_conf.get("main_manager", env), "opus-5.5:high")
        self.assertEqual(agent_conf.get("task_manager", env), "opus-5.5:high")
        self.assertEqual(len(agent_conf.warnings(env)), 2)

    def test_manager_value_outside_the_picker_but_above_the_floor_is_kept(self):
        self.h.configure({"main_manager": "fable-5.2:max"})
        self.assertEqual(agent_conf.get("main_manager", self.h.env()), "fable-5.2:max")

    def test_helper_model_drives_the_three_helper_roles(self):
        self.h.configure({"helper_model": "sonnet-5:high"})
        env = self.h.env()
        for role in ("fast_lane_deputy", "merge_deputy", "worker"):
            self.assertEqual(agent_conf.get(role, env), "sonnet-5:high", role)
        self.assertEqual(agent_conf.get("main_manager", env), "opus-5.5:high")

    def test_bad_language_and_bad_paths(self):
        self.h.configure({"language": "Chinese"})
        self.assertEqual(agent_conf.get("language", self.h.env()), "en")

    def test_danger_paths_is_no_setting_any_more(self):
        # owner 1A 2026-11-25: core paths are facts of one repo (agent_repo.conf), not a user setting
        self.h.configure({"danger_paths": "src/"})
        with self.assertRaises(KeyError):
            agent_conf.get("danger_paths", self.h.env())
        self.assertNotIn("danger_paths", agent_conf.user_config())

    def test_constant_keys(self):
        env = self.h.env(CLAUDE_PLUGIN_OPTION_STAGE_TESTS="99")
        for key, value in CONSTANTS.items():
            self.assertEqual(agent_conf.get(key, env), value, key)
            self.assertEqual(agent_conf.source(key, env), "constant", key)

    def test_unknown_key(self):
        with self.assertRaises(KeyError):
            agent_conf.get("level3_paths", self.h.env())

    def test_old_files_are_never_read_for_a_value(self):
        with open(os.path.join(self.h.repo, "agent.conf"), "w") as fh:
            fh.write("language=zh\nmax_usage_percent=90\n")
        user = self.h.write("home/.claude/auto-pipeline.conf", "permission_mode=bypassPermissions\n")
        old_cwd = os.getcwd()
        os.chdir(self.h.repo)
        try:
            env = self.h.env(AUTO_PIPELINE_USER_CONF=user)
            self.assertEqual(agent_conf.get("language", env), "en")
            self.assertEqual(agent_conf.get("max_usage_percent", env), 80)
            self.assertEqual(agent_conf.get("permission_mode", env), "bypassPermissions")   # the default, not the old file's
        finally:
            os.chdir(old_cwd)

    def test_text(self):
        self.assertEqual(agent_conf.text(True), "on")
        self.assertEqual(agent_conf.text(False), "off")
        self.assertEqual(agent_conf.text(4), "4")
        self.assertEqual(agent_conf.text("zh"), "zh")


class TestCli(unittest.TestCase):
    def setUp(self):
        self.h = Home()

    def tearDown(self):
        self.h.close()

    def test_get_prints_the_text_value(self):
        self.h.configure({"language": "zh", "auto_resume": False})
        env = self.h.env()
        self.assertEqual(run_cli(["get", "language"], env).stdout, "zh\n")
        self.assertEqual(run_cli(["get", "auto_resume"], env).stdout, "off\n")
        self.assertEqual(run_cli(["get", "max_usage_percent"], env).stdout, "80\n")
        self.assertEqual(run_cli(["get", "worker"], env).stdout, "sonnet-5:medium\n")
        self.assertEqual(run_cli(["get", "stage_tests"], env).stdout, "20\n")

    def test_get_unknown_key_exits_2(self):
        res = run_cli(["get", "nope"], self.h.env())
        self.assertEqual(res.returncode, 2)
        self.assertEqual(res.stdout, "")
        self.assertIn("nope", res.stderr)

    def test_show_is_a_table_by_group_with_the_change_line_last(self):
        self.h.configure({"language": "zh"})
        res = run_cli(["show"], self.h.env())
        self.assertEqual(res.returncode, 0, res.stderr)
        lines = res.stdout.rstrip("\n").splitlines()
        self.assertEqual(lines[-2:], [CHANGE_LINE, CORE_LINE])
        body = res.stdout
        self.assertNotIn("Danger paths", body)
        for group in ("Basic", "Models", "Load", "Permissions", "Rules", "Stuck", "City"):
            self.assertIn(group, body)
        last = -1
        for _, title, _, _ in ORDER:
            name = title.split(": ", 1)[1]
            pos = body.find(name)
            self.assertGreater(pos, last, name)
            last = pos
        zh_line = [l for l in lines if "Language" in l][0]
        self.assertIn("zh", zh_line)
        self.assertIn("*", zh_line)  # not the default
        port_line = [l for l in lines if "City port" in l][0]
        self.assertNotIn("*", port_line)
        self.assertNotIn("stage_tests", body)

    def test_show_names_a_bad_stored_value(self):
        self.h.configure({"max_usage_percent": 999})
        res = run_cli(["show"], self.h.env())
        self.assertIn("max_usage_percent=999", res.stdout)

    def test_show_never_writes(self):
        self.h.configure({"language": "zh"})
        path = os.path.join(self.h.cfg, "settings.json")
        before = open(path).read()
        run_cli(["show"], self.h.env())
        self.assertEqual(open(path).read(), before)
        self.assertEqual(sorted(os.listdir(self.h.cfg)), ["plugins", "settings.json"])


class TestRepoPathsFile(unittest.TestCase):
    """owner 1A 2026-11-25: agent_repo.conf at the main repo root holds level3_paths and level4_paths."""

    def setUp(self):
        self.h = Home()

    def tearDown(self):
        self.h.close()

    def write(self, text):
        with open(os.path.join(self.h.repo, "agent_repo.conf"), "w") as fh:
            fh.write(text)

    def test_no_file_is_built_ins_only(self):
        self.assertEqual(agent_conf.repo_paths(self.h.repo), ({}, []))

    def test_both_keys(self):
        self.write("# core paths of this repo\nlevel3_paths=PRINCIPLES.md,skills/\nlevel4_paths=.claude-plugin/,hooks/\n")
        self.assertEqual(agent_conf.repo_paths(self.h.repo),
                         ({"level3_paths": "PRINCIPLES.md,skills/", "level4_paths": ".claude-plugin/,hooks/"}, []))

    def test_an_empty_value_and_other_keys(self):
        self.write("level3_paths=\nlanguage=zh\n")
        values, warnings = agent_conf.repo_paths(self.h.repo)
        self.assertEqual(values.get("level3_paths", ""), "")
        self.assertNotIn("language", values)

    def test_a_bad_glob_list_is_left_out_and_said(self):
        self.write("level3_paths=/etc/,src/\nlevel4_paths=db/\n")
        values, warnings = agent_conf.repo_paths(self.h.repo)
        self.assertEqual(values, {"level4_paths": "db/"})
        self.assertEqual(len(warnings), 1, warnings)
        self.assertTrue(warnings[0].startswith("SETTINGS: level3_paths=/etc/,src/ in agent_repo.conf"), warnings)

    def test_never_raises(self):
        os.mkdir(os.path.join(self.h.repo, "agent_repo.conf"))
        values, warnings = agent_conf.repo_paths(self.h.repo)
        self.assertEqual(values, {})


class TestMigration(unittest.TestCase):
    def setUp(self):
        self.h = Home()
        self.user = os.path.join(self.h.cfg, "auto-pipeline.conf")
        self.conf = os.path.join(os.path.realpath(self.h.repo), "agent.conf")

    def tearDown(self):
        self.h.close()

    def migrate(self, **extra):
        return agent_conf.migrate(self.h.repo, self.h.env(**extra))

    def old_conf(self, text):
        with open(os.path.join(self.h.repo, "agent.conf"), "w") as fh:
            fh.write(text)

    def configure_calls(self):
        return [c for c in self.h.calls() if c["args"][:2] == ["plugin", "configure"]]

    def test_no_old_files_no_lines_no_call(self):
        self.assertEqual(self.migrate(), [])
        self.assertEqual(self.h.calls(), [])

    def test_differing_values_are_moved_with_the_official_command(self):
        self.old_conf("language=zh\nmax_usage_percent=60\nauto_resume=no\nboard_guard=record\n"
                      "worker=sonnet-5:high\nfast_lane_deputy=sonnet-5:high\nmerge_deputy=sonnet-5:high\n")
        out = self.migrate()
        calls = self.configure_calls()
        self.assertEqual(len(calls), 1, self.h.calls())
        self.assertEqual(calls[0]["args"], ["plugin", "configure", "auto-pipeline@auto-pipeline", "--values-stdin"])
        self.assertEqual(json.loads(calls[0]["stdin"]), {
            "language": "zh", "max_usage_percent": "60", "auto_resume": "false",
            "todo_before_agent": "false", "helper_model": "sonnet-5:high"})
        self.assertEqual(self.h.options()["language"], "zh")
        self.assertIn("moved language=zh from %s to Configure" % self.conf, out)
        self.assertIn("moved max_usage_percent=60 from %s to Configure" % self.conf, out)
        self.assertIn("moved auto_resume=false from %s to Configure" % self.conf, out)
        self.assertTrue(out[0].startswith("SETTINGS MOVED: %s" % self.conf), out)
        self.assertIn("not read any more", out[0])

    def test_values_equal_to_the_default_are_not_moved(self):
        self.old_conf("language=en\nmax_usage_percent=80\nboard_guard=on\nauto_resume=yes\n")
        out = self.migrate()
        self.assertEqual(self.configure_calls(), [])
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith("SETTINGS MOVED:"))

    def test_a_value_the_human_set_is_never_overwritten(self):
        self.old_conf("language=zh\nmax_usage_percent=60\ncity_port=4777\n")
        self.h.configure({"language": "ms", "city_port": 5000})
        out = self.migrate()
        self.assertEqual(json.loads(self.configure_calls()[0]["stdin"]), {"max_usage_percent": "60"})
        self.assertEqual(self.h.options()["language"], "ms")
        self.assertIn("kept language=ms in Configure, skipped language=zh from %s" % self.conf, out)
        self.assertFalse([l for l in out if "city_port" in l], out)  # old value = default, nothing to say

    def test_same_value_already_in_configure_says_nothing(self):
        self.old_conf("language=zh\n")
        self.h.configure({"language": "zh"})
        out = self.migrate()
        self.assertEqual(self.configure_calls(), [])
        self.assertFalse([l for l in out if "language" in l], out)

    # owner 1A 2026-11-25: the old level paths go into the repo's own agent_repo.conf, never Configure
    def repo_conf(self):
        path = os.path.join(self.h.repo, "agent_repo.conf")
        return open(path).read() if os.path.exists(path) else None

    def test_level_paths_move_into_agent_repo_conf(self):
        self.old_conf("level3_paths=src/money/\nlevel4_paths=db/,hooks/\nlanguage=zh\n")
        out = self.migrate()
        self.assertEqual(self.repo_conf(), "level3_paths=src/money/\nlevel4_paths=db/,hooks/\n")
        self.assertIn(MOVED_BOTH, out)
        payload = json.loads(self.configure_calls()[0]["stdin"])
        self.assertEqual(payload, {"language": "zh"})
        for key in ("level3_paths", "level4_paths", "danger_paths"):
            self.assertNotIn(key, self.h.options())

    def test_only_the_keys_there_are_moved(self):
        self.old_conf("level4_paths=db/\n")
        out = self.migrate()
        self.assertEqual(self.repo_conf(), "level4_paths=db/\n")
        self.assertIn("moved level4_paths to agent_repo.conf (repo file, commit it)", out)
        self.assertEqual(self.configure_calls(), [])

    def test_empty_level_paths_are_not_moved(self):
        self.old_conf("level3_paths=\nlevel4_paths=\n")
        out = self.migrate()
        self.assertIsNone(self.repo_conf())
        self.assertFalse([l for l in out if "agent_repo.conf" in l], out)

    def test_a_key_already_in_agent_repo_conf_is_never_overwritten(self):
        with open(os.path.join(self.h.repo, "agent_repo.conf"), "w") as fh:
            fh.write("# core paths\nlevel4_paths=infra/\n")
        self.old_conf("level3_paths=src/money/\nlevel4_paths=db/\n")
        out = self.migrate()
        text = self.repo_conf()
        self.assertIn("level4_paths=infra/\n", text)
        self.assertNotIn("db/", text)
        self.assertIn("level3_paths=src/money/\n", text)
        self.assertTrue(text.startswith("# core paths\n"), text)
        self.assertIn("moved level3_paths to agent_repo.conf (repo file, commit it)", out)
        self.assertTrue([l for l in out if l.startswith("kept level4_paths=infra/ in agent_repo.conf")], out)

    def test_the_level_move_happens_once(self):
        self.old_conf("level3_paths=src/money/\n")
        self.migrate()
        os.remove(os.path.join(self.h.repo, "agent_repo.conf"))
        self.assertEqual(self.migrate(), [])
        self.assertIsNone(self.repo_conf())

    def test_once_the_same_file_is_quiet(self):
        self.old_conf("language=zh\n")
        self.assertTrue(self.migrate())
        self.assertEqual(self.migrate(), [])
        self.assertEqual(len(self.configure_calls()), 1)
        marker = os.path.join(self.h.cfg, "auto-pipeline-migrated.json")
        with open(marker) as fh:
            self.assertIn(self.conf, json.load(fh))

    def test_a_changed_old_file_is_read_again(self):
        self.old_conf("language=zh\n")
        self.migrate()
        self.old_conf("language=zh\nmax_usage_percent=70\n")
        out = self.migrate()
        self.assertIn("moved max_usage_percent=70 from %s to Configure" % self.conf, out)

    def test_a_failed_write_prints_the_exact_command_and_tries_again(self):
        self.old_conf("language=zh\n")
        self.h.claude_mode("fail")
        out = "\n".join(self.migrate())
        self.assertIn("SETTINGS MOVE FAILED:", out)
        self.assertIn("boom", out)
        self.assertIn("claude plugin configure auto-pipeline@auto-pipeline --values-stdin <<< '{\"language\": \"zh\"}'", out)
        self.assertNotIn("moved language", out)
        self.assertFalse(os.path.exists(os.path.join(self.h.cfg, "auto-pipeline-migrated.json")))
        self.h.claude_mode("ok")
        self.assertIn("moved language=zh from %s to Configure" % self.conf, self.migrate())

    def test_no_claude_on_path_is_said(self):
        self.old_conf("language=zh\n")
        out = "\n".join(self.migrate(PATH="/nonexistent"))
        self.assertIn("SETTINGS MOVE FAILED:", out)
        self.assertIn("--values-stdin", out)

    def test_a_changed_constant_is_named_as_fixed(self):
        self.old_conf("stage_tests=33\nstate_keep_hours=24\n")
        out = self.migrate()
        self.assertIn("fixed: stage_tests=33 in %s is now fixed at 20" % self.conf, out)
        self.assertFalse([l for l in out if "state_keep_hours" in l], out)
        self.assertEqual(self.configure_calls(), [])

    def test_an_unknown_key_is_named_as_dropped(self):
        self.old_conf("adhd=off\n")
        out = self.migrate()
        self.assertIn("dropped: adhd=off in %s is not a setting any more" % self.conf, out)

    def test_the_user_file_moves_too_and_wins_for_its_keys(self):
        self.old_conf("permission_mode=acceptEdits\n")
        with open(self.user, "w") as fh:
            fh.write("permission_mode=plan\nauto_update=off\n")   # plan: not the default (bypassPermissions)
        out = "\n".join(self.migrate())
        payload = {}
        for call in self.configure_calls():
            payload.update(json.loads(call["stdin"]))
        self.assertEqual(payload, {"permission_mode": "plan", "auto_update": "false"})
        self.assertIn("auto-pipeline.conf", out)

    def test_the_user_file_path_can_come_from_the_env(self):
        other = self.h.write("elsewhere/u.conf", "permission_mode=plan\n")
        self.migrate(AUTO_PIPELINE_USER_CONF=other)
        self.assertEqual(self.h.options().get("permission_mode"), "plan")

    def test_a_user_file_bypass_is_the_default_and_not_moved(self):
        # owner order 2026-11-25: bypassPermissions is the default, so nothing to write
        with open(self.user, "w") as fh:
            fh.write("permission_mode=bypassPermissions\n")
        self.migrate()
        self.assertEqual(self.configure_calls(), [])

    def test_retired_settings_are_ignored_not_moved(self):
        # check-blocks (owner 2026-11-25): Max agents and Heavy test slot/time are gone; an old value is
        # ignored, never moved, never an error (pc2 printed "plugin has no options heavy_test_slots")
        self.old_conf("max_agents=6\nheavy_test_slots=3\nlanguage=zh\n")
        out = "\n".join(self.migrate())
        self.assertEqual(json.loads(self.configure_calls()[0]["stdin"]), {"language": "zh"})
        self.assertNotIn("max_agents", out)
        self.assertNotIn("heavy_test_slots", out)
        self.assertNotIn("FAILED", out)

    def test_a_bad_old_value_is_not_moved(self):
        self.old_conf("max_usage_percent=999\nlanguage=zh\n")
        out = "\n".join(self.migrate())
        self.assertEqual(json.loads(self.configure_calls()[0]["stdin"]), {"language": "zh"})
        self.assertIn("max_usage_percent=999", out)

    def test_unreadable_old_file_is_said(self):
        os.mkdir(os.path.join(self.h.repo, "agent.conf"))
        out = "\n".join(self.migrate())
        self.assertIn("SETTINGS MOVED:", out)
        self.assertIn("cannot read", out)

    def test_the_old_file_is_never_changed(self):
        self.old_conf("language=zh\n")
        self.migrate()
        self.assertEqual(open(os.path.join(self.h.repo, "agent.conf")).read(), "language=zh\n")

    def test_cli(self):
        self.old_conf("language=zh\n")
        res = run_cli(["migrate", self.h.repo], self.h.env())
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("moved language=zh", res.stdout)


if __name__ == "__main__":
    unittest.main()
