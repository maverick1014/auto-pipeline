"""Failing tests for bypass-mode (owner, 2026-11-04): every new terminal the
pipeline opens runs in bypass mode; first-time setup asks the user: all agents
bypass, or all auto. Ships to every repo. Written by the task manager, before
any code.

CONTRACT

1. bin/agent_conf.py
   PERMISSION_MODES = acceptEdits, auto, bypassPermissions, manual, dontAsk,
   plan (five-fixes S1, 2026-11-05: the list `claude --help` gives; "default"
   is refused).
   validate_value("permission_mode", v) and validate_value(
   "cloud_permission_mode", v): None for those six exactly (case and spaces
   count), else a message that names all six.
   HINTS["permission_mode"] names the six; HINTS["cloud_permission_mode"]
   says it is for a session started from the Agent City cloud page, and that
   missing or refused means auto.
   GROUPS "permission" = permission_mode, cloud_permission_mode, auto_resume,
   language, adhd.

2. bin/agent.conf.default: permission_mode=bypassPermissions (its old place);
   cloud_permission_mode=auto is the LAST line, so `agent-settings.sh sync`
   (which appends a missing key) gives an old agent.conf the same key order
   as a fresh one. sync needs no change: it adds every missing template key.

3. bin/agent_city.py
   agent_command(name, folder, city_dir=None, cloud=False) -> str.
     cloud False (local city click, the plain line): as before, the mode is
     permission_mode; missing, refused or no agent.conf -> no
     --permission-mode at all.
     cloud True (a start order from the cloud page): the mode is
     cloud_permission_mode. Missing, refused, empty, or no agent.conf at all
     -> "--permission-mode auto": always an explicit flag (no flag would let
     the user's own defaultMode decide, which may be bypass), never
     bypassPermissions unless cloud_permission_mode says exactly that.
     permission_mode never decides a cloud line. Everything else of the line
     (AGENT_CITY_DIR, --name, --model, --effort, FIRST_PROMPT, the order of
     the words, shlex.quote) is the local line's.
   CityState.add_agent(terr, now, force=False, cloud=False): cloud must be a
     bool, else (400, {"error": "bad"}) and nothing opens. The opener's line
     and the "plain" answer's command are agent_command(..., cloud=cloud).
   CityState.cloud_order(...) (signature unchanged) calls
     add_agent(terr, now, force, cloud=True), once.
   POST /api/agent/add stays "terr" and "force" only: a body with "cloud" is
     400 (only the cloud order path is a cloud start).
   Local city click, dispatch (skills/dispatch), resume (bin/agent-resume.sh)
   and a Helper (PRINCIPLES.md W10) keep permission_mode.

4. bin/agent-init.sh [--mode bypass|auto] [<dir>]
   --mode bypass -> permission_mode=bypassPermissions, --mode auto ->
     permission_mode=auto, written through bin/agent-settings.sh (its
     "saved: permission_mode=<value>" line shows), for the project being set
     up (CLAUDE_PROJECT_DIR set to that root, so a session started elsewhere
     never writes another repo's agent.conf). Only on a fresh agent.conf (the
     first-time setup): an agent.conf already there is never changed, and
     one stdout line says it was kept, its permission_mode value and how to
     change it: "<plugin>/bin/agent-settings.sh permission_mode <mode>".
   --mode with any other value, or no value: exit 2, a message on stderr,
     nothing created.
   No --mode, a fresh agent.conf and stdin a terminal: ONE question on
     stderr, starting "Permission mode for every agent:", bypass first and
     marked recommended, then auto. Answer bypass (or b) / auto (or a), any
     case. Empty, EOF or anything else -> the template default stands.
   No --mode and stdin not a terminal (a skill's Bash call, cloud-pack):
     no question, the template default stands.
   -h shows --mode.
   After the files: the project's agent.conf says
     permission_mode=bypassPermissions and $HOME/.claude/settings.json has no
     "skipDangerousModePermissionPrompt": true (file missing, broken JSON, the
     key missing or not true) -> exactly ONE stdout line that contains
     "new panes stop on the bypass warning screen" and ends with
     "skipDangerousModePermissionPrompt": true  (the line to add, with
     ~/.claude/settings.json named on the same line). No "{" or "}" on it:
     the permission block stays the only JSON. The user's settings file is
     never written, created or touched (nor ~/.claude).
   Otherwise no such line.

5. skills/init/SKILL.md: before agent-init.sh, when the project has no
   agent.conf yet, ONE question: all agents bypass or all auto, options
   "bypass (Recommended)" first, then auto. bypass -> agent-init.sh --mode
   bypass, auto -> --mode auto, no answer -> run it without --mode (template
   default). Show the skip-warning line unchanged; never write
   ~/.claude/settings.json (it names skipDangerousModePermissionPrompt).

6. Text. PRINCIPLES.md W10: the second-session launch line says
   "--permission-mode <mode>" (from permission_mode), never a literal
   "--permission-mode auto"; one line: new terminals use permission_mode,
   a session started from the cloud page uses cloud_permission_mode.
   requirements/city.md: the cloud start lines ("From the cloud page too",
   "A stolen login can open") say cloud_permission_mode. skills/dispatch keeps
   "--permission-mode <mode>" from permission_mode.
   Quiz: Q34 (rule W10), answer B (see TestQuiz34). The quiz has 36 since
   personal-mode and decider-floor.
"""

import json
import os
import pty
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_conf  # noqa: E402
import agent_city as ac  # noqa: E402
from scripthelp import ScriptCase, ScriptRepo  # noqa: E402
from test_agent_city_add_agent import AddCase, PROMPT  # noqa: E402
from test_agent_city_cloud_start_machine import OrderCase, oid  # noqa: E402

# five-fixes S1: the modes `claude --help` lists; "default" is not one
FIVE = ("acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan")
MODEL = ["--model", "opus", "--effort", "high"]
SKIP_KEY = '"skipDangerousModePermissionPrompt": true'
WARN = "new panes stop on the bypass warning screen"


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def conf_text(**keys):
    text = "main_manager=opus-5.5:high\n"
    for key, value in keys.items():
        text += "%s=%s\n" % (key, value)
    return text


# --------------------------------------------------------------- 1, 2: conf

PROGRESS_KEYS = ["stage_brief", "stage_register", "stage_mock", "stage_tests", "stage_workers",
                 "stage_verify", "stage_push", "stage_report", "stage_e2e", "stage_merge",
                 "board_watch_sec", "progress_eta_min_pct"]

class TestConfKeys(unittest.TestCase):
    def test_bypass_is_a_mode_for_both_keys(self):
        for key in ("permission_mode", "cloud_permission_mode"):
            with self.subTest(key=key):
                self.assertIsNone(agent_conf.validate_value(key, "bypassPermissions"))
                self.assertTrue(agent_conf.validate_value(key, "yolo"))

    def test_the_list(self):
        self.assertEqual(list(agent_conf.PERMISSION_MODES), list(FIVE))

    def test_hints(self):
        hint = agent_conf.HINTS.get("permission_mode", "")
        for mode in FIVE:
            with self.subTest(mode=mode):
                self.assertIn(mode, hint)
        cloud = agent_conf.HINTS.get("cloud_permission_mode", "")
        self.assertIn("cloud page", cloud)
        self.assertIn("auto", cloud)
        self.assertIn("bypassPermissions", cloud)

    def test_group(self):
        self.assertEqual(agent_conf.group_of("cloud_permission_mode"), "permission")
        self.assertEqual(dict(agent_conf.GROUPS)["permission"],
                         ["permission_mode", "cloud_permission_mode", "auto_resume", "language", "adhd"])


class TestTemplate(unittest.TestCase):
    def setUp(self):
        self.lines = read("bin", "agent.conf.default").splitlines()
        self.conf = agent_conf.load(os.path.join(BIN, "agent.conf.default"))

    def test_bypass_is_the_default_for_new_terminals(self):
        self.assertEqual(self.conf["permission_mode"], "bypassPermissions")

    def test_auto_is_the_default_for_the_cloud(self):
        self.assertEqual(self.conf["cloud_permission_mode"], "auto")

    def test_the_cloud_key_is_the_last_line(self):
        # progress-bar (2026-11-11): newer keys are appended after it, never before it,
        # so an old agent.conf still syncs into the template order
        keys = [l.split("=", 1)[0] for l in self.lines]
        after = keys[keys.index("cloud_permission_mode") + 1:]
        self.assertEqual(after, PROGRESS_KEYS)
        self.assertEqual(sum(1 for l in self.lines if l.startswith("cloud_permission_mode=")), 1)

    def test_permission_mode_keeps_its_place(self):
        keys = [l.split("=", 1)[0] for l in self.lines]
        self.assertEqual(keys[keys.index("permission_mode") - 1], "worker")
        self.assertEqual(keys[keys.index("permission_mode") + 1], "auto_resume")

    def test_valid(self):
        self.assertEqual(agent_conf.validate(self.conf), {})


class TestSync(ScriptCase):
    """4: the existing sync path adds the new key to an existing agent.conf."""

    script = "agent-settings.sh"

    def conf(self):
        return open(self.repo.path("agent.conf")).read()

    def test_sync_adds_the_cloud_key_and_keeps_every_line(self):
        with open(self.repo.path("agent.conf"), "w") as fh:
            fh.write("max_agents=4\npermission_mode=acceptEdits\nlanguage=zh\n")
        before = self.conf()
        out = self.assertOk(self.repo.run("agent-settings.sh", "sync"))
        self.assertIn("added cloud_permission_mode=auto", out)
        after = self.conf()
        self.assertTrue(after.startswith(before), "the lines already there stay byte for byte")
        conf = agent_conf.load(self.repo.path("agent.conf"))
        self.assertEqual(conf["cloud_permission_mode"], "auto")
        self.assertEqual(conf["permission_mode"], "acceptEdits", "sync never changes a value already there")

    def test_a_synced_conf_has_the_fresh_key_order(self):
        template = agent_conf.load(self.repo.plugin_path("bin", "agent.conf.default"))
        # a conf written before bypass-mode: every key before cloud_permission_mode
        # (the keys after it are newer still, tests/test_agent_progress.py)
        keys = list(template)
        old = {k: template[k] for k in keys[:keys.index("cloud_permission_mode")]}
        with open(self.repo.path("agent.conf"), "w") as fh:
            fh.write(agent_conf.dumps(old))
        self.assertOk(self.repo.run("agent-settings.sh", "sync"))
        self.assertEqual(list(agent_conf.load(self.repo.path("agent.conf"))), list(template))

    def test_the_setting_is_validated(self):
        result = self.repo.run("agent-settings.sh", "cloud_permission_mode", "bypassPermissions")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("saved: cloud_permission_mode=bypassPermissions", result.stdout)
        for bad in ("yolo", "bypass", "auto;id"):
            with self.subTest(value=bad):
                result = self.repo.run("agent-settings.sh", "cloud_permission_mode", bad)
                self.assertNotEqual(result.returncode, 0)
        self.assertEqual(agent_conf.load(self.repo.path("agent.conf"))["cloud_permission_mode"],
                         "bypassPermissions")


# --------------------------------------------------------------- 3: the launch line

class LineCase(AddCase):
    def folder(self, name, conf):
        self.repo(name, conf)
        return os.path.join(self.base, name)

    def words(self, name, conf, **kw):
        return shlex.split(ac.agent_command("x Manager", self.folder(name, conf), **kw))


class TestLaunchLine(LineCase):
    def test_the_signature(self):
        import inspect
        params = inspect.signature(ac.agent_command).parameters
        self.assertEqual(list(params), ["name", "folder", "city_dir", "cloud"])
        self.assertIs(params["cloud"].default, False)

    def test_local_uses_permission_mode(self):
        conf = conf_text(permission_mode="bypassPermissions", cloud_permission_mode="auto")
        self.assertEqual(self.words("loc", conf),
                         ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "bypassPermissions", PROMPT])

    def test_cloud_uses_cloud_permission_mode(self):
        conf = conf_text(permission_mode="bypassPermissions", cloud_permission_mode="auto")
        self.assertEqual(self.words("cl", conf, cloud=True),
                         ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "auto", PROMPT])

    def test_cloud_may_be_set_to_any_mode(self):
        for mode in FIVE:
            with self.subTest(mode=mode):
                conf = conf_text(permission_mode="plan", cloud_permission_mode=mode)
                words = self.words("cm-" + mode, conf, cloud=True)
                self.assertEqual(words[words.index("--permission-mode") + 1], mode)

    def test_cloud_key_missing_is_auto_never_bypass(self):
        conf = conf_text(permission_mode="bypassPermissions")
        self.assertEqual(self.words("miss", conf, cloud=True),
                         ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "auto", PROMPT])

    def test_cloud_key_refused_is_auto(self):
        for i, bad in enumerate(("yolo", "Bypass", "bypass", "", "bypassPermissions!", "default")):
            with self.subTest(value=bad):
                conf = conf_text(permission_mode="bypassPermissions", cloud_permission_mode=bad)
                words = self.words("bad%d" % i, conf, cloud=True)
                self.assertEqual(words, ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "auto", PROMPT])

    def test_no_agent_conf_at_all(self):
        folder = self.folder("bare", None)
        self.assertEqual(shlex.split(ac.agent_command("x Manager", folder, cloud=True)),
                         ["claude", "--name", "x Manager", "--permission-mode", "auto", PROMPT],
                         "no conf on a cloud start: still an explicit auto")
        self.assertEqual(shlex.split(ac.agent_command("x Manager", folder)), ["claude", "--name", "x Manager", PROMPT],
                         "the local line is unchanged")

    def test_an_unreadable_conf_is_auto_on_the_cloud(self):
        folder = self.folder("dir", None)
        os.makedirs(os.path.join(folder, "agent.conf"))      # a directory: load() raises
        self.assertEqual(shlex.split(ac.agent_command("x Manager", folder, cloud=True)),
                         ["claude", "--name", "x Manager", "--permission-mode", "auto", PROMPT])

    def test_the_cloud_key_never_decides_a_local_line(self):
        conf = conf_text(cloud_permission_mode="bypassPermissions")
        self.assertEqual(self.words("only-cloud", conf), ["claude", "--name", "x Manager"] + MODEL + [PROMPT])

    def test_the_city_dir_is_kept_on_the_cloud_line(self):
        own = os.path.join(self.base, "my city")
        folder = self.folder("cd", conf_text(permission_mode="bypassPermissions"))
        words = shlex.split(ac.agent_command("x Manager", folder, own, cloud=True))
        self.assertEqual(words, ["AGENT_CITY_DIR=" + own, "claude", "--name", "x Manager"] + MODEL
                         + ["--permission-mode", "auto", PROMPT])

    def test_the_cloud_key_cannot_break_the_line(self):
        cases = {
            "subshell": "auto$(touch pwned)",
            "and": "bypassPermissions && touch pwned",
            "semi": "auto; touch pwned",
            "tick": "`touch pwned`",
            "pipe": "bypassPermissions|touch pwned",
            "nl": "bypassPermissions\\ntouch pwned",
        }
        for name, value in cases.items():
            with self.subTest(case=name):
                conf = conf_text(permission_mode="bypassPermissions") + "cloud_permission_mode=%s\n" % value
                command = ac.agent_command("x Manager", self.folder("inj-" + name, conf), cloud=True)
                self.assertEqual(shlex.split(command),
                                 ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "auto", PROMPT])
                self.assertNotIn("pwned", command)

    def test_both_keys_broken(self):
        conf = ("main_manager=opus-5.5:high; touch pwned\npermission_mode=bypassPermissions$(touch pwned)\n"
                "cloud_permission_mode=auto`touch pwned`\n")
        folder = self.folder("both", conf)
        self.assertEqual(shlex.split(ac.agent_command("x Manager", folder, cloud=True)),
                         ["claude", "--name", "x Manager", "--permission-mode", "auto", PROMPT])
        self.assertEqual(shlex.split(ac.agent_command("x Manager", folder)), ["claude", "--name", "x Manager", PROMPT])

    def test_the_shipped_template(self):
        folder = self.folder("shipped", read("bin", "agent.conf.default"))
        local = shlex.split(ac.agent_command("x Manager", folder))
        cloud = shlex.split(ac.agent_command("x Manager", folder, cloud=True))
        self.assertEqual(local[local.index("--permission-mode") + 1], "bypassPermissions")
        self.assertEqual(cloud[cloud.index("--permission-mode") + 1], "auto")
        self.assertEqual([w for w in local if w != "bypassPermissions"], [w for w in cloud if w != "auto"],
                         "only the mode differs")


class TestAddAgent(LineCase):
    CONF = conf_text(permission_mode="bypassPermissions", cloud_permission_mode="acceptEdits")

    def setUp(self):
        super().setUp()
        with open(os.path.join(self.base, "shop", "agent.conf"), "w") as fh:
            fh.write(self.CONF)
        self.known(self.shop)

    def mode(self, command):
        words = shlex.split(command)
        return words[words.index("--permission-mode") + 1]

    def test_a_local_click_is_permission_mode(self):
        code, body = self.add(self.shop)
        self.assertEqual(code, 200, body)
        self.assertEqual(self.mode(self.calls[0][2]), "bypassPermissions")

    def test_a_cloud_start_is_cloud_permission_mode(self):
        code, body = self.add(self.shop, cloud=True)
        self.assertEqual(code, 200, body)
        self.assertEqual(self.calls[0][2], ac.agent_command("shop Manager", os.path.join(self.base, "shop"), None,
                                                            cloud=True))
        self.assertEqual(self.mode(self.calls[0][2]), "acceptEdits")

    def test_cloud_is_a_bool(self):
        tid = ac.territory_id(self.shop)
        for bad in ("yes", 1, 0, None, "true", [True]):
            with self.subTest(cloud=bad):
                self.assertEqual(self.state.add_agent(tid, self.now, cloud=bad), (400, {"error": "bad"}))
        self.assertEqual(self.calls, [])

    def test_plain_gives_the_cloud_line_too(self):
        self.kind = "plain"
        code, body = self.add(self.shop, cloud=True)
        self.assertEqual((code, body.get("state")), (200, "plain"))
        self.assertEqual(self.mode(body["command"]), "acceptEdits")
        self.assertEqual(self.calls, [])


class TestCloudOrder(OrderCase):
    def setUp(self):
        super().setUp()
        self.folder = os.path.dirname(self.shop)
        self.write("main_manager=opus-5.5:high\npermission_mode=bypassPermissions\n")

    def write(self, text):
        with open(os.path.join(self.folder, "agent.conf"), "w") as fh:
            fh.write(text)

    def mode(self):
        words = shlex.split(self.calls[-1][2])
        return words[words.index("--permission-mode") + 1]

    def test_no_cloud_key_opens_in_auto(self):
        self.assertEqual(self.order(oid(1))["state"], "opening")
        self.assertEqual(self.mode(), "auto", "the cloud page never opens a bypass session by default")

    def test_the_owner_may_set_bypass_for_the_cloud(self):
        self.write("main_manager=opus-5.5:high\npermission_mode=auto\ncloud_permission_mode=bypassPermissions\n")
        self.assertEqual(self.order(oid(1))["state"], "opening")
        self.assertEqual(self.mode(), "bypassPermissions")

    def test_a_refused_cloud_key_is_auto(self):
        self.write("permission_mode=bypassPermissions\ncloud_permission_mode=bypassPermissions;id\n")
        self.order(oid(1))
        self.assertEqual(self.mode(), "auto")
        self.assertNotIn(";id", self.calls[-1][2])

    def test_the_local_button_on_the_same_repo_keeps_permission_mode(self):
        self.order(oid(1))
        self.state.add_agent(self.terr, self.now + ac.ADD_WAIT_SEC + 5)
        self.assertEqual(len(self.calls), 2, self.calls)
        modes = [shlex.split(c[2])[shlex.split(c[2]).index("--permission-mode") + 1] for c in self.calls]
        self.assertEqual(modes, ["auto", "bypassPermissions"])


class TestHttpNeverACloudStart(unittest.TestCase):
    def test_the_local_route_takes_no_cloud_key(self):
        """POST /api/agent/add: terr and force only (the existing key check); "cloud" is not one of them."""
        import inspect
        src = inspect.getsource(ac.CityHandler._api_agent_add)
        self.assertIn('("terr", "force")', src)
        self.assertNotIn("cloud", src)


# --------------------------------------------------------------- 4: init

class InitCase(ScriptCase):
    def setUp(self):
        self.repo = ScriptRepo(init_project=False)
        self.addCleanup(self.repo.cleanup)
        self.project = self.repo.dir
        self.repo.git_init(self.project)
        self.home = self.repo.fake_home()
        # auto-update: the user has chosen already, so init asks only the
        # permission question these tests drive
        self.repo.set_user_conf("auto_update=on\n")

    def init(self, *args, **kw):
        return self.repo.run("agent-init.sh", *args, **kw)

    def conf(self, root=None):
        return agent_conf.load(os.path.join(root or self.project, "agent.conf"))

    def settings(self, data=None, raw=None):
        os.makedirs(os.path.join(self.home, ".claude"), exist_ok=True)
        path = os.path.join(self.home, ".claude", "settings.json")
        with open(path, "w") as fh:
            fh.write(raw if raw is not None else json.dumps(data, indent=2) + "\n")
        return path

    def warn_lines(self, out):
        return [l for l in out.splitlines() if WARN in l]

    def tty(self, answer, *args):
        """Run agent-init.sh with stdin a terminal; ANSWER is typed into it."""
        master, slave = pty.openpty()
        try:
            proc = subprocess.Popen([self.repo.script_path("agent-init.sh")] + list(args), cwd=self.project,
                                    env=self.repo._env(None), stdin=slave, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            os.close(slave)
            slave = None
            if answer is not None:
                os.write(master, answer.encode())
            out, err = proc.communicate(timeout=60)
        finally:
            if slave is not None:
                os.close(slave)
            os.close(master)
        return proc.returncode, out, err


class TestInitMode(InitCase):
    def test_bypass(self):
        out = self.assertOk(self.init("--mode", "bypass"))
        self.assertEqual(self.conf()["permission_mode"], "bypassPermissions")
        self.assertIn("saved: permission_mode=bypassPermissions", out, "written through agent-settings.sh")

    def test_auto(self):
        out = self.assertOk(self.init("--mode", "auto"))
        self.assertEqual(self.conf()["permission_mode"], "auto")
        self.assertIn("saved: permission_mode=auto", out)

    def test_only_permission_mode_changes(self):
        self.assertOk(self.init("--mode", "auto"))
        template = agent_conf.load(self.repo.plugin_path("bin", "agent.conf.default"))
        conf = self.conf()
        self.assertEqual(list(conf), list(template))
        for key, value in template.items():
            if key != "permission_mode":
                with self.subTest(key=key):
                    self.assertEqual(conf[key], value)
        self.assertEqual(conf["cloud_permission_mode"], "auto")

    def test_a_directory_argument(self):
        other = os.path.join(self.repo.base, "other")
        os.makedirs(other)
        self.repo.git_init(other)
        self.assertOk(self.init("--mode", "auto", other))
        self.assertEqual(self.conf(other)["permission_mode"], "auto")
        self.assertFalse(os.path.exists(os.path.join(self.project, "agent.conf")))

    def test_the_project_dir_of_the_session_is_not_the_target(self):
        """A session started in another repo sets CLAUDE_PROJECT_DIR; the setting goes to the repo being set up."""
        elsewhere = os.path.join(self.repo.base, "elsewhere")
        os.makedirs(elsewhere)
        self.repo.git_init(elsewhere)
        with open(os.path.join(elsewhere, "agent.conf"), "w") as fh:
            fh.write("permission_mode=plan\n")
        target = os.path.join(self.repo.base, "target")
        os.makedirs(target)
        self.repo.git_init(target)
        self.assertOk(self.init("--mode", "auto", target, env={"CLAUDE_PROJECT_DIR": elsewhere}))
        self.assertEqual(self.conf(target)["permission_mode"], "auto")
        self.assertEqual(open(os.path.join(elsewhere, "agent.conf")).read(), "permission_mode=plan\n")

    def test_no_mode_and_no_terminal_is_the_template_default(self):
        result = self.init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.conf()["permission_mode"], "bypassPermissions")
        self.assertNotIn("Permission mode for every agent:", result.stdout + result.stderr, "no question without a terminal")

    def test_a_bad_mode_makes_nothing(self):
        for args in (("--mode", "yolo"), ("--mode", "bypassPermissions!"), ("--mode",), ("--mode", "")):
            with self.subTest(args=args):
                result = self.init(*args)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertTrue(result.stderr.strip())
                self.assertFalse(os.path.exists(os.path.join(self.project, "agent.conf")))
                self.assertFalse(os.path.exists(os.path.join(self.project, "AGENTS.md")))

    def test_a_kept_conf_is_never_changed(self):
        path = os.path.join(self.project, "agent.conf")
        with open(path, "w") as fh:
            fh.write("# mine\nmax_agents=9\npermission_mode=plan\n")
        out = self.assertOk(self.init("--mode", "bypass"))
        self.assertEqual(open(path).read(), "# mine\nmax_agents=9\npermission_mode=plan\n")
        lines = [l for l in out.splitlines() if "permission_mode" in l and "kept" in l]
        self.assertEqual(len(lines), 1, out)
        self.assertIn("plan", lines[0])
        self.assertIn("agent-settings.sh permission_mode", lines[0])
        self.assertNotIn("saved:", out)

    def test_twice_changes_nothing(self):
        self.assertOk(self.init("--mode", "auto"))
        first = open(os.path.join(self.project, "agent.conf")).read()
        self.assertOk(self.init("--mode", "bypass"))
        self.assertEqual(open(os.path.join(self.project, "agent.conf")).read(), first)

    def test_help_names_the_option(self):
        out = self.assertOk(self.init("-h"))
        self.assertIn("--mode bypass", out)
        self.assertIn("auto", out)


class TestInitQuestion(InitCase):
    def test_the_question_on_a_terminal(self):
        code, out, err = self.tty("auto\n")
        self.assertEqual(code, 0, out + err)
        q = [l for l in (err + out).splitlines() if "Permission mode for every agent:" in l]
        self.assertEqual(len(q), 1, err + out)
        self.assertLess(q[0].index("bypass"), q[0].index("auto"), "bypass first")
        self.assertIn("recommended", q[0].lower())
        self.assertEqual(self.conf()["permission_mode"], "auto")

    def test_the_answers(self):
        for answer, mode in (("bypass\n", "bypassPermissions"), ("b\n", "bypassPermissions"),
                             ("AUTO\n", "auto"), ("a\n", "auto"), ("\n", "bypassPermissions"),
                             ("maybe\n", "bypassPermissions"), ("\x04", "bypassPermissions")):
            with self.subTest(answer=answer):
                path = os.path.join(self.project, "agent.conf")
                if os.path.exists(path):
                    os.remove(path)
                code, out, err = self.tty(answer)
                self.assertEqual(code, 0, out + err)
                self.assertEqual(self.conf()["permission_mode"], mode)

    def test_no_question_when_the_conf_is_kept(self):
        with open(os.path.join(self.project, "agent.conf"), "w") as fh:
            fh.write("permission_mode=plan\n")
        code, out, err = self.tty("auto\n")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("Permission mode for every agent:", out + err)
        self.assertEqual(open(os.path.join(self.project, "agent.conf")).read(), "permission_mode=plan\n")

    def test_no_question_when_the_mode_is_given(self):
        code, out, err = self.tty("bypass\n", "--mode", "auto")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("Permission mode for every agent:", out + err)
        self.assertEqual(self.conf()["permission_mode"], "auto")


class TestSkipWarning(InitCase):
    def assertOneWarning(self, out):
        lines = self.warn_lines(out)
        self.assertEqual(len(lines), 1, out)
        self.assertTrue(lines[0].rstrip().endswith(SKIP_KEY), lines[0])
        self.assertIn("~/.claude/settings.json", lines[0])
        self.assertNotIn("{", lines[0])
        self.assertNotIn("}", lines[0])

    def assertBlockStillParses(self, out):
        block = json.loads(out[out.index("{"):out.rindex("}") + 1])
        self.assertIn("permissions", block)

    def test_no_settings_file(self):
        out = self.assertOk(self.init("--mode", "bypass"))
        self.assertOneWarning(out)
        self.assertBlockStillParses(out)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude")), "never creates the user's settings")

    def test_the_template_default_warns_too(self):
        self.assertOneWarning(self.assertOk(self.init()))

    def test_the_key_set_is_quiet(self):
        path = self.settings({"skipDangerousModePermissionPrompt": True, "theme": "dark"})
        before = open(path, "rb").read()
        out = self.assertOk(self.init("--mode", "bypass"))
        self.assertEqual(self.warn_lines(out), [])
        self.assertEqual(open(path, "rb").read(), before)

    def test_the_key_false_or_missing_warns_and_the_file_stays(self):
        for i, data in enumerate(({"skipDangerousModePermissionPrompt": False},
                                  {"skipDangerousModePermissionPrompt": "true"},
                                  {"permissions": {"allow": []}})):
            with self.subTest(data=data):
                path = self.settings(data)
                before = open(path, "rb").read()
                os.remove(os.path.join(self.project, "agent.conf")) if i else None
                out = self.assertOk(self.init("--mode", "bypass"))
                self.assertOneWarning(out)
                self.assertEqual(open(path, "rb").read(), before, "never writes the user's settings file")

    def test_broken_json_warns(self):
        path = self.settings(raw="{not json")
        out = self.assertOk(self.init("--mode", "bypass"))
        self.assertOneWarning(out)
        self.assertEqual(open(path).read(), "{not json")

    def test_auto_is_quiet(self):
        out = self.assertOk(self.init("--mode", "auto"))
        self.assertEqual(self.warn_lines(out), [])
        self.assertNotIn("skipDangerousModePermissionPrompt", out)

    def test_a_kept_bypass_conf_warns(self):
        with open(os.path.join(self.project, "agent.conf"), "w") as fh:
            fh.write("permission_mode=bypassPermissions\n")
        self.assertOneWarning(self.assertOk(self.init()))

    def test_a_kept_auto_conf_is_quiet(self):
        with open(os.path.join(self.project, "agent.conf"), "w") as fh:
            fh.write("permission_mode=auto\n")
        self.assertEqual(self.warn_lines(self.assertOk(self.init())), [])

    def test_the_script_never_writes_home_settings(self):
        src = read("bin", "agent-init.sh")
        for bad in ("> \"$HOME/.claude", ">> \"$HOME/.claude", ">\"$HOME/.claude", "~/.claude/settings.json\" <<"):
            self.assertNotIn(bad, src)


# --------------------------------------------------------------- 5, 6: text

class TestInitSkill(unittest.TestCase):
    def setUp(self):
        self.text = read("skills", "init", "SKILL.md")

    def test_one_question_bypass_first(self):
        self.assertIn("bypass (Recommended)", self.text)
        self.assertLess(self.text.index("bypass (Recommended)"), self.text.index("--mode bypass"))
        self.assertIn("--mode auto", self.text)
        self.assertIn("without --mode", self.text)
        self.assertIn("agent.conf", self.text)

    def test_the_question_comes_before_the_run(self):
        first_run = self.text.index("agent-init.sh")
        self.assertLess(self.text.index("bypass (Recommended)"), self.text.index("--mode bypass"))
        self.assertLess(self.text.index("bypass (Recommended)"), self.text.index("agent-init.sh --mode"))
        self.assertGreaterEqual(first_run, 0)

    def test_the_skip_warning(self):
        self.assertIn("skipDangerousModePermissionPrompt", self.text)
        self.assertIn("~/.claude/settings.json", self.text)
        self.assertRegex(self.text, r"[Nn]ever write")


class TestRuleText(unittest.TestCase):
    def w10(self):
        text = read("PRINCIPLES.md")
        return text[text.index("W10. "):text.index("W11. ")]

    def test_w10_launch_line_reads_the_mode(self):
        w10 = self.w10()
        self.assertIn("--permission-mode <mode>", w10)
        self.assertNotIn("--permission-mode auto", w10)

    def test_w10_says_which_key_for_which_terminal(self):
        lines = [l for l in self.w10().splitlines() if "cloud_permission_mode" in l]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("`permission_mode`", lines[0])
        self.assertIn("cloud page", lines[0])

    def test_no_literal_auto_launch_anywhere_in_the_rules(self):
        self.assertNotIn("--permission-mode auto", read("PRINCIPLES.md"))

    def test_dispatch_reads_the_mode(self):
        text = read("skills", "dispatch", "SKILL.md")
        self.assertIn("`<mode>` from `permission_mode`", text)
        self.assertIn("--permission-mode <mode>", text)
        self.assertNotIn("--permission-mode auto", text)

    def test_city_requirements_cloud_start_lines(self):
        text = read("requirements", "city.md")
        for start in ("- From the cloud page too", "- A stolen login can open"):
            with self.subTest(line=start):
                line = next(l for l in text.splitlines() if l.startswith(start))
                self.assertIn("cloud_permission_mode", line)
        stolen = next(l for l in text.splitlines() if l.startswith("- A stolen login can open"))
        self.assertNotIn("own `permission_mode`", stolen)

    def test_the_local_click_line_keeps_permission_mode(self):
        text = read("requirements", "city.md")
        line = next(l for l in text.splitlines() if l.startswith("- Click → the local server opens ONE new session"))
        self.assertIn("`permission_mode`", line)


class TestQuiz34(ScriptCase):
    ANSWERS = ("1A 2D 3C 4B 5D 6D 7A 8C 9A 10D 11A 12C 13D 14C 15B 16C 17C "
               "18D 19B 20A 21D 22C 23B 24D 25A 26D 27A 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C")

    def quiz(self):
        return self.assertOk(self.repo.run("agent-start.sh", "--quiz"))

    def test_question_34_is_the_launch_mode(self):
        out = self.quiz()
        q = out[out.index("Q34. "):]
        head = q.splitlines()[0]
        self.assertIn("new terminal", head)
        self.assertIn("--permission-mode", head)
        options = [l.strip() for l in q.splitlines()[1:5]]
        self.assertEqual([o[:2] for o in options], ["A.", "B.", "C.", "D."])
        self.assertIn("permission_mode from agent.conf", options[1])
        self.assertIn("cloud_permission_mode", options[1])
        self.assertIn("cloud page", options[1])

    def test_34_questions(self):
        out = self.quiz()
        self.assertIn("=== QUIZ — answer all 37 before any work ===", out)
        self.assertIn('--answer "1A 2B 3C ... 37D"', out)
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", out)), 37)

    def test_b_passes(self):
        out = self.assertOk(self.repo.run("agent-start.sh", "--answer", self.ANSWERS))
        self.assertIn("QUIZ RESULT: 37/37 PASS", out)

    def test_another_letter_fails_and_names_w10(self):
        for wrong in ("34A", "34C", "34D"):
            with self.subTest(wrong=wrong):
                result = self.repo.run("agent-start.sh", "--answer", self.ANSWERS.replace("34B", wrong))
                self.assertEqual(result.returncode, 1)
                self.assertIn("Q34(W10)", result.stdout)

    def test_the_old_33_answers_no_longer_pass(self):
        result = self.repo.run("agent-start.sh", "--answer", self.ANSWERS.replace(" 34B", ""))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Q34(W10)", result.stdout)

    def test_the_readme_says_34(self):
        text = read("README.md")
        self.assertIn("37-question quiz", text)
        self.assertNotIn("33-question quiz", text)

    def test_the_usage_lines_say_34(self):
        src = read("bin", "agent-start.sh")
        self.assertIn("print the 37 quiz questions", src)
        self.assertIn('--answer "1A 2D ... 37C"', src)
        self.assertNotIn("33B\"", src)


if __name__ == "__main__":
    unittest.main()
