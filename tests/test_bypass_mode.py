"""UPDATE settings-configure (2026-11-25): the permission mode is the Configure setting
"Permissions: Permission mode" (default auto, user level). Init asks nothing and has no
--mode; its skip warning follows the setting. agent.conf, its template and sync are gone.
Items about them below are history.

Failing tests for bypass-mode (owner, 2026-11-04): every new terminal the
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
   language.

2. bin/agent.conf.default: permission_mode=bypassPermissions (its old place);
   cloud_permission_mode=auto is the LAST line, so `agent-settings.sh sync`
   (which appends a missing key) gives an old agent.conf the same key order
   as a fresh one. sync needs no change: it adds every missing template key.

3. bin/agent_city.py
   agent_command(name, folder, city_dir=None) -> str: the local city click's
     line. The mode is permission_mode; missing, refused or no agent.conf -> no
     --permission-mode at all. cloud_permission_mode never decides it (the
     city is local only; the Agent City cloud page is gone).
   POST /api/agent/add stays "terr" and "force" only.
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
   skills/dispatch keeps
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
                 "board_watch_sec", "progress_eta_min_pct",
                 "statusline_refresh_sec",   # statusline-vertical (2026-11-12)
                 "housekeep_interval_min",   # housekeep-2h (2026-11-13)
                 "estimate_target_pct", "estimate_bias_min",
                 "estimate_big_min",   # estimate-blend (2026-11-13)
                 "level3_paths", "level4_paths",   # test-levels (2026-11-20)
                 "state_keep_hours", "state_warn_lines", "state_header_lines", "state_trim_auto",
                 "compact_clear_at", "compact_clear_check_sec",   # state-trim (2026-11-20)
                 "board_guard",   # board-trust (2026-11-23)
                 "watch_quiet_min",   # one-watcher (2026-11-24)
                 "cleanup_days", "docs_keep",   # clean-up (2026-11-24)
                 "owner_order_hours", "owner_order_min_chars"]   # owner-relay (2026-11-24), appended last

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


# --------------------------------------------------------------- 3: the launch line

class LineCase(AddCase):
    def folder(self, name, conf):
        """conf: old key=value text, written into Configure (settings-configure)."""
        self.repo(name, conf)
        return os.path.join(self.base, name)

    def words(self, name, conf, **kw):
        return shlex.split(ac.agent_command("x Manager", self.folder(name, conf), **kw))


class TestLaunchLine(LineCase):
    def test_the_signature(self):
        import inspect
        params = inspect.signature(ac.agent_command).parameters
        # city-office O6: the interior designer's line takes its own model key, prompt and AGENT_ROLE
        self.assertEqual(list(params), ["name", "folder", "city_dir", "model_key", "prompt", "role"])

    def test_local_uses_permission_mode(self):
        conf = conf_text(permission_mode="bypassPermissions")
        self.assertEqual(self.words("loc", conf),
                         ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "bypassPermissions", PROMPT])

    def test_nothing_set_is_the_defaults(self):
        os.remove(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "settings.json"))
        folder = self.folder("bare", None)
        self.assertEqual(shlex.split(ac.agent_command("x Manager", folder)),
                         ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "bypassPermissions", PROMPT])

    def test_the_old_cloud_key_decides_nothing(self):
        conf = conf_text(cloud_permission_mode="bypassPermissions")
        self.assertEqual(self.words("only-cloud", conf),
                         ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "auto", PROMPT])

    def test_the_city_dir_is_kept(self):
        own = os.path.join(self.base, "my city")
        folder = self.folder("cd", conf_text(permission_mode="bypassPermissions"))
        words = shlex.split(ac.agent_command("x Manager", folder, own))
        self.assertEqual(words, ["AGENT_CITY_DIR=" + own, "claude", "--name", "x Manager"] + MODEL
                         + ["--permission-mode", "bypassPermissions", PROMPT])

    def test_both_keys_broken(self):
        conf = ("main_manager=opus-5.5:high; touch pwned\npermission_mode=bypassPermissions$(touch pwned)\n"
                "cloud_permission_mode=auto`touch pwned`\n")
        folder = self.folder("both", conf)
        command = ac.agent_command("x Manager", folder)
        self.assertEqual(shlex.split(command),
                         ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "bypassPermissions", PROMPT])
        self.assertNotIn("pwned", command)

    def test_the_shipped_default_is_bypass(self):
        # owner order 2026-11-25: the default stays bypassPermissions (as since 2026-11-04)
        os.remove(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "settings.json"))
        folder = self.folder("shipped", None)
        local = shlex.split(ac.agent_command("x Manager", folder))
        self.assertEqual(local[local.index("--permission-mode") + 1], "bypassPermissions")


class TestAddAgent(LineCase):
    CONF = conf_text(permission_mode="bypassPermissions")

    def setUp(self):
        super().setUp()
        from test_agent_city_add_agent import configure_text
        configure_text(self.CONF)
        self.known(self.shop)

    def mode(self, command):
        words = shlex.split(command)
        return words[words.index("--permission-mode") + 1]

    def test_a_local_click_is_permission_mode(self):
        code, body = self.add(self.shop)
        self.assertEqual(code, 200, body)
        self.assertEqual(self.mode(self.calls[0][2]), "bypassPermissions")



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

    def init(self, *args, **kw):
        return self.repo.run("agent-init.sh", *args, **kw)

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
                # Questions in order: permission mode, auto update, add permissions.
                # ANSWER is the first; Enter (the default) is typed for the later ones
                # so a terminal run never waits on a prompt this test does not script.
                os.write(master, (answer + "\n\n\n").encode())
            out, err = proc.communicate(timeout=60)
        finally:
            if slave is not None:
                os.close(slave)
            os.close(master)
        return proc.returncode, out, err


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

    def bypass(self):
        self.repo.set_conf("permission_mode", "bypassPermissions")

    def test_no_settings_file(self):
        self.bypass()
        out = self.assertOk(self.init())
        self.assertOneWarning(out)
        self.assertBlockStillParses(out)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude", "settings.json.bak-auto-pipeline")))

    def test_the_default_bypass_warns_too(self):
        # owner order 2026-11-25: the default is bypassPermissions, so init warns about the skip key
        self.assertOneWarning(self.assertOk(self.init()))

    def test_the_key_set_is_quiet(self):
        path = self.settings({"skipDangerousModePermissionPrompt": True, "theme": "dark"})
        self.bypass()
        before = open(path, "rb").read()
        out = self.assertOk(self.init())
        self.assertEqual(self.warn_lines(out), [])
        self.assertEqual(open(path, "rb").read(), before)

    def test_the_key_false_or_missing_warns_and_the_file_stays(self):
        for i, data in enumerate(({"skipDangerousModePermissionPrompt": False},
                                  {"skipDangerousModePermissionPrompt": "true"},
                                  {"permissions": {"allow": []}})):
            with self.subTest(data=data):
                path = self.settings(data)
                self.bypass()
                before = open(path, "rb").read()
                out = self.assertOk(self.init())
                self.assertOneWarning(out)
                self.assertEqual(open(path, "rb").read(), before, "never writes the user's settings file")

    def test_broken_json_warns(self):
        # a broken settings.json: the setting reads as its default (bypassPermissions), so it warns
        path = self.settings(raw="{not json")
        out = self.assertOk(self.init())
        self.assertOneWarning(out)
        self.assertEqual(open(path).read(), "{not json")

    def test_auto_is_quiet(self):
        self.repo.set_conf("permission_mode", "auto")
        out = self.assertOk(self.init())
        self.assertEqual(self.warn_lines(out), [])
        self.assertNotIn("skipDangerousModePermissionPrompt", out)

    def test_the_script_never_writes_home_settings(self):
        src = read("bin", "agent-init.sh")
        for bad in ("> \"$HOME/.claude", ">> \"$HOME/.claude", ">\"$HOME/.claude", "~/.claude/settings.json\" <<"):
            self.assertNotIn(bad, src)


# --------------------------------------------------------------- 5, 6: text

class TestRuleText(unittest.TestCase):
    def w10(self):
        text = read("PRINCIPLES.md")
        return text[text.index("W10. "):text.index("W11. ")]

    def test_w10_launch_line_reads_the_mode(self):
        w10 = self.w10()
        self.assertIn("--permission-mode <mode>", w10)
        self.assertNotIn("--permission-mode auto", w10)

    def test_w10_says_which_key_for_which_terminal(self):
        w10 = self.w10()
        self.assertIn("Permission mode", w10)
        self.assertNotIn("cloud_permission_mode", w10)
        self.assertNotIn("cloud page", w10)

    def test_no_literal_auto_launch_anywhere_in_the_rules(self):
        self.assertNotIn("--permission-mode auto", read("PRINCIPLES.md"))

    def test_the_local_click_line_keeps_permission_mode(self):
        text = read("requirements", "city.md")
        line = next(l for l in text.splitlines() if l.startswith("- Click → the local server opens ONE new session"))
        self.assertIn("`permission_mode`", line)


class TestQuiz34(ScriptCase):
    ANSWERS = ("1A 2D 3C 4B 5D 6D 7C 8C 9A 10D 11C 12C 13D 14C 15D 16B 17C "
               "18D 19C 20A 21D 22C 23B 24D 25C 26D 27B 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C 38A 39C")

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
        self.assertIn("Permission mode setting", options[1])
        self.assertNotIn("cloud", options[1])

    def test_34_questions(self):
        out = self.quiz()
        self.assertIn("=== QUIZ — answer all 39 before any work ===", out)
        self.assertIn('--answer "1A 2B 3C ... 39D"', out)
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", out)), 39)

    def test_b_passes(self):
        out = self.assertOk(self.repo.run("agent-start.sh", "--answer", self.ANSWERS))
        self.assertIn("QUIZ RESULT: 39/39 PASS", out)

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

    def test_the_principles_say_34(self):
        text = read("PRINCIPLES.md")
        self.assertIn("39-question quiz", text)
        self.assertNotIn("33-question quiz", text)

    def test_the_usage_lines_say_34(self):
        src = read("bin", "agent-start.sh")
        self.assertIn("print the 39 quiz questions", src)
        self.assertIn('--answer "1A 2D ... 39D"', src)
        self.assertNotIn("33B\"", src)


if __name__ == "__main__":
    unittest.main()
