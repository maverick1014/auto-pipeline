"""Failing tests for five-fixes (main manager brief, 2026-11-05): five bug
fixes from agent_ideas.txt. S1, S2, S3 are here. S4 (a flaky wait) is a
test-only change in tests/test_agent_city_server.py; S5 (the city walk) is in
tests/test_agent_city_walk.py. Written by the task manager, before any code.

CONTRACT

S1. bin/agent_conf.py: the permission modes are the ones `claude --help`
  lists for --permission-mode (claude 2.1.318, 2026-11-05):
    PERMISSION_MODES = ["acceptEdits", "auto", "bypassPermissions",
                        "manual", "dontAsk", "plan"]      (that order)
  "default" is no claude mode any more.
  validate_value("permission_mode" | "cloud_permission_mode", v): None for
    those six exactly (case and spaces count); anything else, "default"
    too, a message that names all six. "default" is refused, never mapped
    to another mode.
  HINTS["permission_mode"] and HINTS["cloud_permission_mode"] name the six
    and never the word "default".
  Every launcher reads the mode through agent_conf.effective() (it only
  returns a value validate_value accepts), so a refused value never reaches
  a --permission-mode flag:
    agent_city.agent_command: permission_mode=default -> no flag on a local
      line; cloud_permission_mode=default -> "--permission-mode auto".
    bin/agent-resume.sh: permission_mode=default -> "--permission-mode auto".
    bin/agent-settings.sh get permission_mode (dispatch, a Helper): default
      -> "auto (default)".
    bin/agent-start.sh: "PERMISSION: auto (default), ..." for default.
  bin/agent-settings.sh permission_mode default, and --user permission_mode
    default: exit 1, "not saved", the six named, nothing written.
  A user-file permission_mode=default is ignored (read_user_conf lists it).
  manual and dontAsk reach a launch line like any other mode.
  Every mode in PERMISSION_MODES is one the installed claude lists (skipped
    when no claude is on PATH).

S2. bin/agent_conf.py: a model with the context suffix "[1m]"
  Role value shape (every role key): model-name, then optionally exactly
    "[1m]", then ":effort". A broken suffix ("[1m", "[]", "[1m]x",
    "[1m][1m]", "[", " [1m]") is refused like any bad shape.
  Decider floor (main_manager, task_manager): the suffix is ignored, the
    floor itself is unchanged. opus-5.5[1m], claude-opus-5-5[1m],
    fable-5.1[1m], fable[1m], opus[1m] ... pass; sonnet, haiku, opus-5.4,
    opus-5 with the suffix are refused with the floor message; effort low is
    still refused.
  cli_model keeps the suffix (model-suffix, 2026-11-05; it was dropped in
    0.30.2): "opus-5.5[1m]:xhigh" -> "opus[1m]",
    "claude-opus-5-5[1m]:high" -> "claude-opus-5-5[1m]". Without the suffix:
    unchanged. `agent_conf.py cli-model <spec>` says the same. Every launch
    line quotes the model word, so zsh never reads "[1m]" as a glob
    (tests/test_model_suffix.py).
  bin/agent-settings.sh saves task_manager=opus-5.5[1m]:xhigh and refuses
    sonnet-5[1m]:high.

S3. bin/agent_update.py apply_auto_update(on, cdir): the backup
  "<file>.bak-auto-pipeline" is written only when none exists. After any
  number of on/off flips it holds the file as it was before the first flip,
  byte for byte; a backup already there (an earlier run) is never
  overwritten. The status line still names the backup path.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_conf  # noqa: E402
import agent_city as ac  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402

MODES = ["acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan"]
MODE_KEYS = ("permission_mode", "cloud_permission_mode")
ENV = "AUTO_PIPELINE_USER_CONF"


class TmpCase(unittest.TestCase):
    """A temp folder, and a user file that is never the real ~/.claude one."""

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="five_fixes_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.user = os.path.join(self.base, "u", "auto-pipeline.conf")
        patcher = mock.patch.dict(os.environ, {ENV: self.user})
        patcher.start()
        self.addCleanup(patcher.stop)

    def folder(self, name, conf):
        path = os.path.join(self.base, name)
        os.makedirs(path)
        with open(os.path.join(path, "agent.conf"), "w") as fh:
            fh.write(conf)
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


# ===================================================================== S1

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

    def test_hints(self):
        for key in MODE_KEYS:
            hint = agent_conf.HINTS[key]
            with self.subTest(key=key):
                self.assertNotIn("default", hint)
                for mode in MODES:
                    self.assertIn(mode, hint)

    def test_the_shipped_confs_pass(self):
        for path in (os.path.join(ROOT, "agent.conf"), os.path.join(BIN, "agent.conf.default")):
            with self.subTest(path=path):
                self.assertEqual(agent_conf.validate(agent_conf.load(path)), {})


class TestEffectiveRefusesDefault(TmpCase):
    def test_agent_conf_default_is_not_set(self):
        for key in MODE_KEYS:
            with self.subTest(key=key):
                self.assertEqual(agent_conf.effective(key, {key: "default"}), (None, None))

    def test_user_file_default_is_ignored(self):
        self.write_user("permission_mode=default\ncloud_permission_mode=default\n")
        values, ignored = agent_conf.read_user_conf()
        self.assertEqual(values, {})
        self.assertEqual(ignored, ["permission_mode=default", "cloud_permission_mode=default"])
        self.assertEqual(agent_conf.effective("permission_mode", {"permission_mode": "plan"}),
                         ("plan", "agent.conf"), "a refused user value falls back to agent.conf")

    def test_the_new_modes_are_effective(self):
        self.write_user("permission_mode=manual\n")
        self.assertEqual(agent_conf.effective("permission_mode", {})[0], "manual")
        self.assertEqual(agent_conf.effective("cloud_permission_mode", {"cloud_permission_mode": "dontAsk"}),
                         ("dontAsk", "agent.conf"))


class TestCityLine(TmpCase):
    CONF = "main_manager=opus-5.5:high\n"

    def words(self, conf, cloud=False):
        folder = self.folder("f%d" % len(os.listdir(self.base)), self.CONF + conf)
        return shlex.split(ac.agent_command("x Manager", folder, cloud=cloud))

    def test_default_never_reaches_a_local_line(self):
        words = self.words("permission_mode=default\n")
        self.assertNotIn("--permission-mode", words)
        self.assertNotIn("default", words)

    def test_default_on_the_cloud_is_auto(self):
        words = self.words("permission_mode=bypassPermissions\ncloud_permission_mode=default\n", cloud=True)
        self.assertEqual(flag(words, "--permission-mode"), "auto")

    def test_a_user_file_default_never_reaches_a_line(self):
        self.write_user("permission_mode=default\ncloud_permission_mode=default\n")
        self.assertEqual(flag(self.words("permission_mode=plan\n"), "--permission-mode"), "plan")
        self.assertEqual(flag(self.words("permission_mode=plan\n", cloud=True), "--permission-mode"), "auto")

    def test_manual_and_dont_ask_reach_the_line(self):
        self.assertEqual(flag(self.words("permission_mode=manual\n"), "--permission-mode"), "manual")
        self.assertEqual(flag(self.words("cloud_permission_mode=dontAsk\n", cloud=True), "--permission-mode"),
                         "dontAsk")


class TestScriptsRefuseDefault(ScriptCase):
    script = "agent-settings.sh"

    def settings(self, *args):
        return self.repo.run("agent-settings.sh", *args)

    def test_saving_default_is_refused(self):
        for key in MODE_KEYS:
            with self.subTest(key=key):
                before = text(self.repo.path("agent.conf"))
                r = self.settings(key, "default")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("not saved", r.stdout + r.stderr)
                for mode in MODES:
                    self.assertIn(mode, r.stdout + r.stderr)
                self.assertEqual(text(self.repo.path("agent.conf")), before)

    def test_saving_default_in_the_user_file_is_refused(self):
        self.repo.set_user_conf("permission_mode=auto\n")
        r = self.settings("--user", "permission_mode", "default")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("not saved", r.stdout + r.stderr)
        with open(self.repo.user_conf) as fh:
            self.assertEqual(fh.read(), "permission_mode=auto\n")

    def test_the_new_modes_are_saved(self):
        self.assertOk(self.settings("permission_mode", "manual"))
        self.assertOk(self.settings("cloud_permission_mode", "dontAsk"))
        conf = agent_conf.load(self.repo.path("agent.conf"))
        self.assertEqual((conf["permission_mode"], conf["cloud_permission_mode"]), ("manual", "dontAsk"))

    def test_get_never_prints_default(self):
        """dispatch and a Helper read the mode with `agent-settings.sh get`."""
        self.repo.set_conf("permission_mode", "default")
        self.repo.set_conf("cloud_permission_mode", "default")
        self.assertEqual(self.assertOk(self.settings("get", "permission_mode")), "auto (default)\n")
        self.assertEqual(self.assertOk(self.settings("get", "cloud_permission_mode")), "auto (default)\n")
        self.repo.set_conf("permission_mode", "manual")
        self.assertEqual(self.assertOk(self.settings("get", "permission_mode")), "manual (from agent.conf)\n")


class TestResumeRefusesDefault(ScriptCase):
    script = "agent-resume.sh"

    def command(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        self.repo.set_panes([])
        self.assertOk(self.repo.run("agent-resume.sh"))
        calls = self.repo.create_calls()
        self.assertEqual(len(calls), 1, calls)
        return calls[0][calls[0].index("--command") + 1]

    def test_default_relaunches_in_auto(self):
        self.repo.set_conf("permission_mode", "default")
        command = self.command()
        self.assertTrue(command.endswith("--permission-mode auto"), command)
        self.assertNotIn("default", command)

    def test_dont_ask_reaches_the_relaunch(self):
        self.repo.set_conf("permission_mode", "dontAsk")
        self.assertTrue(self.command().endswith("--permission-mode dontAsk"))


class TestStartLineRefusesDefault(ScriptCase):
    script = "agent-start.sh"

    def test_default_shows_as_auto(self):
        self.repo.set_conf("permission_mode", "default")
        self.repo.set_conf("cloud_permission_mode", "default")
        out = self.assertOk(self.repo.run("agent-start.sh", env={"AGENT_ROLE": "task-manager"}))
        lines = [l for l in out.splitlines() if l.startswith("PERMISSION:")]
        self.assertEqual(lines, ["PERMISSION: auto (default), cloud page auto (default)"])


# ===================================================================== S2

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


class TestCliModelKeepsTheSuffix(unittest.TestCase):
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


class TestSettingsWithTheSuffix(ScriptCase):
    script = "agent-settings.sh"

    def test_saved_and_refused(self):
        self.assertOk(self.repo.run("agent-settings.sh", "task_manager", "opus-5.5[1m]:xhigh"))
        self.assertOk(self.repo.run("agent-settings.sh", "main_manager", "claude-opus-5-5[1m]:high"))
        before = text(self.repo.path("agent.conf"))
        r = self.repo.run("agent-settings.sh", "task_manager", "sonnet-5[1m]:high")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Opus 5.5", r.stdout + r.stderr)
        self.assertEqual(text(self.repo.path("agent.conf")), before)
        conf = agent_conf.load(self.repo.path("agent.conf"))
        self.assertEqual((conf["task_manager"], conf["main_manager"]),
                         ("opus-5.5[1m]:xhigh", "claude-opus-5-5[1m]:high"))


# ===================================================================== S3

SETTINGS = {
    "model": "opus",
    "extraKnownMarketplaces": {
        "auto-pipeline": {"source": {"source": "github", "repo": "maverick1014/auto-pipeline"}},
    },
}
KNOWN = {"auto-pipeline": {"source": {"source": "github", "repo": "maverick1014/auto-pipeline"},
                           "installLocation": "/x/auto-pipeline"}}
BAK = ".bak-auto-pipeline"


class TestFirstBackupIsKept(TmpCase):
    def setUp(self):
        super().setUp()
        import agent_update
        self.u = agent_update
        self.cdir = os.path.join(self.base, "home", ".claude")
        self.s = self.write(os.path.join(self.cdir, "settings.json"), SETTINGS)
        self.k = self.write(os.path.join(self.cdir, "plugins", "known_marketplaces.json"), KNOWN)

    def write(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(json.dumps(data, indent=4) + "\n")   # the user's own style, not ours
        return path

    def read(self, path):
        with open(path, "rb") as fh:
            return fh.read()

    def test_many_flips_keep_the_original(self):
        originals = {p: self.read(p) for p in (self.s, self.k)}
        for on in (False, True, False, True, False):
            self.u.apply_auto_update(on, self.cdir)
            for path, raw in originals.items():
                with self.subTest(flip=on, path=path):
                    self.assertEqual(self.read(path + BAK), raw, "the backup is the file before the first flip")
        self.assertIs(json.loads(self.read(self.s))["extraKnownMarketplaces"]["auto-pipeline"]["autoUpdate"], False)
        self.assertIs(json.loads(self.read(self.k))["auto-pipeline"]["autoUpdate"], False)

    def test_an_old_backup_is_never_overwritten(self):
        for path in (self.s, self.k):
            with open(path + BAK, "wb") as fh:
                fh.write(b"older backup\n")
        lines = self.u.apply_auto_update(False, self.cdir)
        for path in (self.s, self.k):
            with self.subTest(path=path):
                self.assertEqual(self.read(path + BAK), b"older backup\n")
        self.assertIs(json.loads(self.read(self.s))["extraKnownMarketplaces"]["auto-pipeline"]["autoUpdate"], False)
        self.assertTrue(any(self.s + BAK in line for line in lines), lines)

    def test_the_first_flip_still_writes_the_backup(self):
        raw = self.read(self.s)
        lines = self.u.apply_auto_update(False, self.cdir)
        self.assertEqual(self.read(self.s + BAK), raw)
        self.assertTrue(any("autoUpdate set to false" in l and self.s + BAK in l for l in lines), lines)


if __name__ == "__main__":
    unittest.main()
