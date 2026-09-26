"""Failing tests for bin/agent-cloud-pack.sh. Written by the task manager first.

WHY. A cloud session (claude.ai/code) never installs a plugin. It only reads
what is committed in the clone: CLAUDE.md, .claude/settings.json (hooks and
permission rules), .claude/skills/, .claude/agents/ and plain scripts. So the
pipeline is laid into the repo as plain files.

CONTRACT.

    bin/agent-cloud-pack.sh <repo-path> [--language xx] [--update]
    bin/agent-cloud-pack.sh -h          usage, exit 0, writes nothing
    no <repo-path>, a missing dir,
    an unknown flag                     exit 2, writes nothing
    a bad --language value              exit non-zero, message, writes nothing
    a .claude/settings.json that is
    not valid JSON                      exit non-zero, message names the file,
                                        writes nothing
    any later step that fails (agent-init.sh,
    the settings merge, ...)            exit non-zero, message names the step,
                                        no success footer

<repo-path> may be any folder inside the repo; the pack goes to its git
toplevel. The source is the folder above the script's own bin/ (the plugin, or
a plain clone of this repo). The source is never written.

What lands in the repo (PACK = .claude/auto-pipeline):

    PACK/bin/<every file of the source bin/>   same bytes, same mode, no __pycache__
    PACK/PRINCIPLES.md                          same bytes
    PACK/VERSION                                the source plugin.json version + "\\n"
    .claude/skills/<name>/SKILL.md              every source skill except init
                                                (clashes with the built-in /init,
                                                and the pack already did its work)
                                                and cloud-pack (cannot run from a
                                                packed copy)
    .claude/agents/<name>.md                    every source agent
    .claude/settings.json                       merged, see below
    CLAUDE.md                                   POINTER appended once, never overwritten
    agent.conf, agent_*.txt, .secrets/,
    AGENTS.md, .gitignore lines                 agent-init.sh run on the repo;
                                                AGENTS.md names PACK by relative path
    .gitignore                                  also PYCACHE_LINE, once

Skills and agents are packed with two text swaps, nothing else:
    ${CLAUDE_PLUGIN_ROOT}  ->  .claude/auto-pipeline
    /auto-pipeline:        ->  /

settings.json merge: every existing key is kept, the user's own hooks too.
hooks.SessionStart gets one entry running HOOK_CMD, unless a SessionStart hook
already runs .claude/auto-pipeline/bin/agent-start.sh. permissions.allow gets
the rules of the block agent-init.sh prints, after the user's own, no rule
twice. A missing settings.json is created.

--language xx sets language in agent.conf (validated), new or existing conf.

A second run without --update changes not one byte. A pack whose VERSION is
not the source version is left alone without --update, and the output says to
run --update. --update makes PACK/bin a mirror of the source bin/ and refreshes
PACK/PRINCIPLES.md, PACK/VERSION, the packed skills and agents. It never
touches agent.conf, agent_*.txt, CLAUDE.md, AGENTS.md, .gitignore, the user's
settings keys, or the user's own skills and agents.

The output ends with the one sentence a human pastes into a fresh cloud
session (ONE_SENTENCE, with the language in use), a reminder that the Claude
GitHub App must be installed on the repo, and a reminder to commit and push.

The one-sentence install itself: from a plain git clone of this repo,
`git clone <this repo> <dir>/ap && <dir>/ap/bin/agent-cloud-pack.sh . --language zh`
run inside a repo sets that repo up completely.
"""

import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from relayhelp import FAKE_KEY, FakeRelay  # noqa: E402
SCRIPT = os.path.join(ROOT, "bin", "agent-cloud-pack.sh")

PACK = os.path.join(".claude", "auto-pipeline")
HOOK_CMD = 'bash "$CLAUDE_PROJECT_DIR"/.claude/auto-pipeline/bin/agent-start.sh'

# Agent City in the cloud (requirements/city.md, "Joining": cloud sessions
# send only, no page). The pack also ships:
#   - every city event hook of the source hooks/hooks.json (the entries that
#     run agent-city-hook.sh), same event and matcher, as CITY_HOOK_CMD. Off
#     (no <city dir>/on) it costs one test -f, like the plugin's own hook.
#   - one more SessionStart hook, SEND_CMD: starts the cloud sender only when
#     the environment secret AGENT_CITY_RELAY is set; silent otherwise.
#   - never the page-side hooks (agent_city.py ask / gov-watch): a cloud
#     session has no city page and no owner at it.
# Each added once; a second pack or --update adds none twice.
CITY_HOOK_CMD = ('[ -f "${AGENT_CITY_DIR:-$HOME/.cache/agent-city}/on" ] && '
                 'bash "$CLAUDE_PROJECT_DIR"/.claude/auto-pipeline/bin/agent-city-hook.sh; exit 0')
SEND_CMD = ('[ -n "${AGENT_CITY_RELAY:-}" ] && '
            'bash "$CLAUDE_PROJECT_DIR"/.claude/auto-pipeline/bin/agent-city.sh send; exit 0')
POINTER = ("Run .claude/auto-pipeline/bin/agent-start.sh first. "
           "Follow its output. No work until the quiz says PASS.")
AGENTS_LINE = ("Run .claude/auto-pipeline/bin/agent-start.sh first. "
               "No work until the quiz says PASS.")
PYCACHE_LINE = ".claude/auto-pipeline/bin/__pycache__/"
ONE_SENTENCE = ("git clone https://github.com/maverick1014/auto-pipeline /tmp/ap"
                " && /tmp/ap/bin/agent-cloud-pack.sh . --language %s")

PACKED_SKILLS = ["dispatch", "merge"]
NOT_PACKED_SKILLS = ["init", "cloud-pack"]
AGENT_FILES = ["fast-lane-deputy.md", "merge-deputy.md", "worker.md"]
SHELL_SCRIPTS = ["agent-start.sh", "agent-file.sh", "agent-settings.sh",
                 "agent-resume.sh", "agent-monitor.sh", "agent-init.sh",
                 "agent-runtime.sh", "agent-cloud-pack.sh"]
TASK_FILES = ["agent_todo.txt", "agent_completed.txt", "agent_ideas.txt",
              "agent_worktree.txt"]
ALLOW_RULES = [
    "Bash(git push origin --delete *)",
    "Bash(git branch -d *)",
    "Bash(git worktree remove *)",
    "Bash(git worktree prune)",
    "Bash(orca worktree rm *)",
    "Bash(orca terminal close *)",
]

SOURCE_PARTS = ["bin", "skills", "agents", "hooks", ".claude-plugin",
                "PRINCIPLES.md"]

USER_SETTINGS = {
    "model": "opus",
    "env": {"FOO": "bar"},
    "permissions": {"allow": ["Bash(ls *)"], "deny": ["Bash(rm -rf *)"]},
    "hooks": {
        "PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "echo pre"}]}],
        "SessionStart": [{"hooks": [
            {"type": "command", "command": "echo mine"}]}],
    },
}
USER_CLAUDE_MD = "# My repo\nBe nice.\n"


def transform(text):
    return (text.replace("${CLAUDE_PLUGIN_ROOT}", ".claude/auto-pipeline")
                .replace("/auto-pipeline:", "/"))


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def read_text(path):
    with open(path) as fh:
        return fh.read()


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def conf_dict(path):
    out = {}
    for line in read_text(path).splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def snapshot(root):
    """Every file and folder under root, with bytes and mode. .git and
    __pycache__ are left out."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in (".git", "__pycache__"))
        for name in dirnames:
            out[os.path.relpath(os.path.join(dirpath, name), root) + "/"] = "dir"
        for name in filenames:
            full = os.path.join(dirpath, name)
            out[os.path.relpath(full, root)] = (
                read_bytes(full), stat.S_IMODE(os.lstat(full).st_mode))
    return out


def git(path, *args):
    return subprocess.run(["git", "-C", path] + list(args), check=True,
                          capture_output=True, text=True).stdout


def git_init(path):
    subprocess.run(["git", "init", "-q", path], check=True, capture_output=True)
    git(path, "config", "user.email", "t@t.t")
    git(path, "config", "user.name", "t")
    write_text(os.path.join(path, "seed.txt"), "x\n")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "seed")


def session_start_commands(settings):
    out = []
    for entry in settings.get("hooks", {}).get("SessionStart", []):
        for hook in entry.get("hooks", []):
            out.append(hook.get("command", ""))
    return out


class PackCase(unittest.TestCase):
    """A throwaway copy of this plugin as the source, and a throwaway repo
    that already has settings of its own and a CLAUDE.md."""

    def setUp(self):
        if not os.path.exists(SCRIPT):
            self.fail("bin/agent-cloud-pack.sh does not exist yet. Write it.")
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="cloud_pack_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.home = os.path.join(self.base, "home")
        os.makedirs(self.home)
        self.src = self.make_source()
        self.target = os.path.join(self.base, "target")
        os.makedirs(self.target)
        git_init(self.target)
        write_text(self.t(".claude", "settings.json"),
                   json.dumps(USER_SETTINGS, indent=2) + "\n")
        write_text(self.t("CLAUDE.md"), USER_CLAUDE_MD)

    # ---- fixture ----

    def make_source(self):
        src = os.path.join(self.base, "src")
        os.makedirs(src)
        for part in SOURCE_PARTS:
            full = os.path.join(ROOT, part)
            if os.path.isdir(full):
                shutil.copytree(full, os.path.join(src, part),
                                ignore=shutil.ignore_patterns("__pycache__",
                                                              "*.pyc"))
            elif os.path.exists(full):
                shutil.copy2(full, os.path.join(src, part))
        return src

    def source_version(self):
        with open(os.path.join(self.src, ".claude-plugin", "plugin.json")) as fh:
            return json.load(fh)["version"]

    def set_source_version(self, version):
        path = os.path.join(self.src, ".claude-plugin", "plugin.json")
        with open(path) as fh:
            data = json.load(fh)
        data["version"] = version
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)

    def s(self, *parts):
        return os.path.join(self.src, *parts)

    def t(self, *parts):
        return os.path.join(self.target, *parts)

    def p(self, *parts):
        return os.path.join(self.target, PACK, *parts)

    def env(self, extra=None):
        env = dict(os.environ)
        for key in list(env):
            if key.startswith("CLAUDE_PLUGIN_OPTION_"):
                env.pop(key)
        for key in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "AGENT_ROLE",
                    "CLAUDE_CODE_REMOTE", "AGENT_RUNTIME",
                    "AGENT_START_DEDUPE_SEC", "PYTHONDONTWRITEBYTECODE"):
            env.pop(key, None)
        env["HOME"] = self.home
        env["AGENT_FAKE_RAM"] = "10"
        env["AGENT_FAKE_CPU"] = "10"
        env.update(extra or {})
        return env

    # ---- running ----

    def pack(self, *args, target=None, cwd=None):
        target = self.target if target is None else target
        argv = [self.s("bin", "agent-cloud-pack.sh")]
        if target != "":
            argv.append(target)
        return subprocess.run(argv + list(args), cwd=cwd or self.base,
                              env=self.env(), capture_output=True, text=True,
                              input="", timeout=120)

    def packed(self, script, *args, env=None, cwd=None, stdin=""):
        return subprocess.run([self.p("bin", script)] + list(args),
                              cwd=cwd or self.target, env=self.env(env),
                              capture_output=True, text=True, input=stdin,
                              timeout=90)

    def assertOk(self, result):
        self.assertEqual(
            result.returncode, 0,
            "exit %d\nSTDOUT:\n%s\nSTDERR:\n%s"
            % (result.returncode, result.stdout, result.stderr))
        return result.stdout

    def settings(self):
        with open(self.t(".claude", "settings.json")) as fh:
            return json.load(fh)


# ---------------------------------------------------------------------------


class TestEveryFileLands(PackCase):
    def setUp(self):
        super().setUp()
        self.src_before = snapshot(self.src)
        self.out = self.assertOk(self.pack("--language", "zh"))

    def src_bin_files(self):
        return sorted(n for n in os.listdir(self.s("bin"))
                      if os.path.isfile(self.s("bin", n)))

    def test_bin_is_copied_whole(self):
        for name in self.src_bin_files():
            with self.subTest(name=name):
                self.assertTrue(os.path.isfile(self.p("bin", name)),
                                "%s/bin/%s is missing" % (PACK, name))
                self.assertEqual(read_bytes(self.p("bin", name)),
                                 read_bytes(self.s("bin", name)))

    def test_bin_keeps_every_mode(self):
        for name in self.src_bin_files():
            with self.subTest(name=name):
                self.assertEqual(
                    stat.S_IMODE(os.stat(self.p("bin", name)).st_mode),
                    stat.S_IMODE(os.stat(self.s("bin", name)).st_mode))

    def test_the_shell_scripts_are_executable(self):
        for name in SHELL_SCRIPTS:
            with self.subTest(name=name):
                self.assertTrue(os.access(self.p("bin", name), os.X_OK))

    def test_nothing_else_is_in_the_packed_bin(self):
        packed = sorted(n for n in os.listdir(self.p("bin"))
                        if n != "__pycache__")
        self.assertEqual(packed, self.src_bin_files())

    def test_principles_is_copied(self):
        self.assertEqual(read_bytes(self.p("PRINCIPLES.md")),
                         read_bytes(self.s("PRINCIPLES.md")))

    def test_the_version_marker_is_the_source_version(self):
        self.assertEqual(read_text(self.p("VERSION")),
                         self.source_version() + "\n")

    def test_the_skills_land_as_project_skills(self):
        for name in PACKED_SKILLS:
            with self.subTest(name=name):
                self.assertEqual(
                    read_text(self.t(".claude", "skills", name, "SKILL.md")),
                    transform(read_text(self.s("skills", name, "SKILL.md"))))

    def test_init_and_cloud_pack_are_not_packed(self):
        for name in NOT_PACKED_SKILLS:
            with self.subTest(name=name):
                self.assertFalse(os.path.exists(
                    self.t(".claude", "skills", name)))

    def test_the_agents_land(self):
        for name in AGENT_FILES:
            with self.subTest(name=name):
                self.assertEqual(
                    read_text(self.t(".claude", "agents", name)),
                    transform(read_text(self.s("agents", name))))

    def test_no_plugin_root_variable_is_left(self):
        for folder in ("skills", "agents"):
            for dirpath, _, names in os.walk(self.t(".claude", folder)):
                for name in names:
                    with self.subTest(file=os.path.join(dirpath, name)):
                        text = read_text(os.path.join(dirpath, name))
                        self.assertNotIn("CLAUDE_PLUGIN_ROOT", text)

    def test_packed_text_points_into_the_pack(self):
        text = read_text(self.t(".claude", "skills", "dispatch", "SKILL.md"))
        self.assertIn(".claude/auto-pipeline/bin/agent-file.sh", text)

    def test_nothing_lands_where_it_must_not(self):
        self.assertFalse(os.path.exists(self.t(".auto-pipeline")),
                         ".auto-pipeline/ is the no-git state fallback")
        self.assertFalse(os.path.exists(self.t("bin")))
        self.assertFalse(os.path.exists(self.t("PRINCIPLES.md")))
        self.assertFalse(os.path.exists(self.t(".claude", "auto-pipeline",
                                               "skills")))

    def test_the_source_is_never_written(self):
        self.assertEqual(snapshot(self.src), self.src_before)

    def test_the_task_files_are_made(self):
        for name in TASK_FILES + ["agent.conf", "AGENTS.md"]:
            with self.subTest(name=name):
                self.assertTrue(os.path.isfile(self.t(name)))
        self.assertTrue(os.path.isdir(self.t(".secrets")))

    def test_agents_md_names_the_pack_by_relative_path(self):
        text = read_text(self.t("AGENTS.md"))
        self.assertIn(AGENTS_LINE, text)
        self.assertNotIn(self.target, text)

    def test_gitignore_keeps_pycache_out_once(self):
        lines = read_text(self.t(".gitignore")).splitlines()
        self.assertEqual(lines.count(PYCACHE_LINE), 1)
        self.assertIn(".secrets/", lines)


class TestSettingsMerge(PackCase):
    def test_every_existing_key_is_kept(self):
        self.assertOk(self.pack())
        data = self.settings()
        self.assertEqual(data["model"], "opus")
        self.assertEqual(data["env"], {"FOO": "bar"})
        self.assertEqual(data["permissions"]["deny"], ["Bash(rm -rf *)"])
        user_pre = USER_SETTINGS["hooks"]["PreToolUse"]
        self.assertEqual(data["hooks"]["PreToolUse"][:len(user_pre)], user_pre,
                         "the user's own hooks stay first, unchanged")

    def test_exactly_one_hook_runs_agent_start(self):
        self.assertOk(self.pack())
        cmds = session_start_commands(self.settings())
        self.assertEqual([c for c in cmds if "agent-start.sh" in c], [HOOK_CMD])

    def test_the_users_own_session_start_hook_is_kept(self):
        self.assertOk(self.pack())
        self.assertIn("echo mine", session_start_commands(self.settings()))

    def test_the_rules_come_after_the_users_own(self):
        self.assertOk(self.pack())
        allow = self.settings()["permissions"]["allow"]
        self.assertEqual(allow, ["Bash(ls *)"] + ALLOW_RULES)

    def test_a_rule_already_there_is_not_added_twice(self):
        data = json.loads(json.dumps(USER_SETTINGS))
        data["permissions"]["allow"].append("Bash(git branch -d *)")
        write_text(self.t(".claude", "settings.json"), json.dumps(data))
        self.assertOk(self.pack())
        allow = self.settings()["permissions"]["allow"]
        self.assertEqual(allow.count("Bash(git branch -d *)"), 1)
        for rule in ALLOW_RULES:
            with self.subTest(rule=rule):
                self.assertIn(rule, allow)

    def test_a_hook_already_there_in_another_form_is_not_added_again(self):
        data = json.loads(json.dumps(USER_SETTINGS))
        data["hooks"]["SessionStart"].append({"hooks": [{
            "type": "command",
            "command": '"$CLAUDE_PROJECT_DIR/.claude/auto-pipeline/bin/agent-start.sh"'}]})
        write_text(self.t(".claude", "settings.json"), json.dumps(data))
        self.assertOk(self.pack())
        cmds = session_start_commands(self.settings())
        self.assertEqual(len([c for c in cmds if "agent-start.sh" in c]), 1)

    def test_a_repo_with_no_settings_gets_one(self):
        os.remove(self.t(".claude", "settings.json"))
        self.assertOk(self.pack())
        data = self.settings()
        self.assertEqual(session_start_commands(data), [HOOK_CMD, SEND_CMD])
        self.assertEqual(data["permissions"]["allow"], ALLOW_RULES)

    def test_broken_settings_stop_the_pack_and_nothing_is_written(self):
        write_text(self.t(".claude", "settings.json"), "{not json")
        before = snapshot(self.target)
        result = self.pack("--language", "zh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("settings.json", result.stdout + result.stderr)
        self.assertEqual(snapshot(self.target), before)


def city_entries(hooks_json_path):
    """[(event, matcher or None)] of every source hook entry that runs
    agent-city-hook.sh."""
    with open(hooks_json_path) as fh:
        hooks = json.load(fh)["hooks"]
    out = []
    for event, entries in hooks.items():
        for entry in entries:
            if any("agent-city-hook.sh" in h.get("command", "") for h in entry.get("hooks", [])):
                out.append((event, entry.get("matcher")))
    return out


def commands_for(settings, event, matcher):
    return [h.get("command") for entry in settings.get("hooks", {}).get(event, [])
            if entry.get("matcher") == matcher for h in entry.get("hooks", [])]


class TestCityHooks(PackCase):
    def setUp(self):
        super().setUp()
        self.assertOk(self.pack())
        self.wanted = city_entries(self.s("hooks", "hooks.json"))
        self.assertTrue(self.wanted, "the source has no city hooks?")

    def test_every_city_event_hook_is_packed(self):
        data = self.settings()
        for event, matcher in self.wanted:
            with self.subTest(event=event, matcher=matcher):
                self.assertEqual(commands_for(data, event, matcher).count(CITY_HOOK_CMD), 1)

    def test_no_page_hooks_in_the_cloud(self):
        text = json.dumps(self.settings())
        self.assertNotIn("agent_city.py", text)

    def test_the_sender_hook(self):
        self.assertEqual(session_start_commands(self.settings()).count(SEND_CMD), 1)

    def test_nothing_twice_after_a_second_pack_and_an_update(self):
        self.assertOk(self.pack())
        self.assertOk(self.pack("--update"))
        data = self.settings()
        for event, matcher in self.wanted:
            with self.subTest(event=event):
                self.assertEqual(commands_for(data, event, matcher).count(CITY_HOOK_CMD), 1)
        self.assertEqual(session_start_commands(data).count(SEND_CMD), 1)

    def test_update_adds_them_to_an_older_pack(self):
        data = self.settings()
        for event in list(data["hooks"]):
            data["hooks"][event] = [e for e in data["hooks"][event]
                                    if not any("agent-city" in h.get("command", "")
                                               for h in e.get("hooks", []))]
        write_text(self.t(".claude", "settings.json"), json.dumps(data, indent=2) + "\n")
        self.assertOk(self.pack("--update"))
        data = self.settings()
        self.assertEqual(session_start_commands(data).count(SEND_CMD), 1)
        for event, matcher in self.wanted:
            with self.subTest(event=event):
                self.assertEqual(commands_for(data, event, matcher).count(CITY_HOOK_CMD), 1)

    def run_cmd(self, cmd, extra=None, stdin=""):
        env = {"CLAUDE_PROJECT_DIR": self.target,
               "AGENT_CITY_DIR": os.path.join(self.base, "city")}
        env.update(extra or {})
        full = self.env(env)
        if "AGENT_CITY_RELAY" not in (extra or {}):
            full.pop("AGENT_CITY_RELAY", None)
        return subprocess.run(["bash", "-c", cmd], cwd=self.target, env=full,
                              capture_output=True, text=True, input=stdin, timeout=60)

    def test_city_hook_is_free_and_silent_when_off(self):
        event = json.dumps({"session_id": "s", "hook_event_name": "PostToolUse",
                            "cwd": self.target, "tool_name": "Bash"})
        result = self.run_cmd(CITY_HOOK_CMD, stdin=event)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertFalse(os.path.exists(os.path.join(self.base, "city")))

    def test_sender_hook_is_silent_without_the_secret(self):
        result = self.run_cmd(SEND_CMD)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertFalse(os.path.exists(os.path.join(self.base, "city", "on")))


class TestCityInTheCloud(PackCase):
    """End to end, the way a cloud session runs it: a packed repo, no plugin,
    CLAUDE_CODE_REMOTE set, AGENT_CITY_RELAY as the environment secret, the
    default city dir under a fresh $HOME. The packed SessionStart hook
    (SEND_CMD) starts the sender; the packed city hook (CITY_HOOK_CMD) writes
    the event; the sender delivers it to the team relay (a fake one on
    127.0.0.1, tests/relayhelp.py) as 云端, with the repo id and branch."""

    def setUp(self):
        super().setUp()
        self.key = FAKE_KEY
        self.fake = FakeRelay()
        self.addCleanup(self.fake.stop)
        git(self.target, "remote", "add", "origin", "git@github.com:Acme/Shop.git")
        self.assertOk(self.pack())
        self.city = os.path.join(self.home, ".cache", "agent-city")
        self.addCleanup(self.stop_sender)

    def stop_sender(self):
        try:
            with open(os.path.join(self.city, "on")) as fh:
                os.kill(int(fh.read().split()[0]), signal.SIGTERM)
        except (OSError, ValueError, IndexError):
            pass

    def cloud_env(self):
        env = self.env({"CLAUDE_PROJECT_DIR": self.target, "CLAUDE_CODE_REMOTE": "true",
                        "AGENT_CITY_RELAY": "%s %s" % (self.fake.url, self.key)})
        env.pop("AGENT_CITY_DIR", None)
        return env

    def run_cmd(self, cmd, stdin=""):
        return subprocess.run(["bash", "-c", cmd], cwd=self.target, env=self.cloud_env(),
                              capture_output=True, text=True, input=stdin, timeout=60)

    def wait(self, check, timeout=10.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if check():
                return True
            time.sleep(0.1)
        return bool(check())

    def test_a_cloud_session_sends_its_events(self):
        started = self.run_cmd(SEND_CMD)
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn("CITY: sending to the team relay " + self.fake.host, started.stdout)
        self.assertNotIn(self.key, started.stdout + started.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.city, "on")))

        event = {"session_id": "cloud-1", "hook_event_name": "PostToolUse", "cwd": self.target,
                 "tool_name": "Bash", "tool_input": {"command": "ls"}}
        hook = self.run_cmd(CITY_HOOK_CMD, stdin=json.dumps(event))
        self.assertEqual((hook.returncode, hook.stdout), (0, ""), hook.stderr)

        # the city_relay_sec default is 5 s: the first sync is at once, the next within ~5 s
        self.assertTrue(self.wait(lambda: self.fake.sent_lines(), timeout=15),
                        "the cloud session's event never reached the relay")
        wire = self.fake.sent_lines()[0]
        branch = git(self.target, "rev-parse", "--abbrev-ref", "HEAD").strip()
        self.assertEqual((wire["sid"], wire["rid"], wire["dev"], wire["br"]),
                         ("cloud-1", "github.com/acme/shop", "云端", branch))
        self.assertNotIn(self.target, json.dumps(self.fake.sync_bodies()))

    def test_the_second_session_start_keeps_one_sender(self):
        self.assertEqual(self.run_cmd(SEND_CMD).returncode, 0)
        with open(os.path.join(self.city, "on")) as fh:
            first = fh.read()
        again = self.run_cmd(SEND_CMD)
        self.assertEqual(again.returncode, 0, again.stderr)
        with open(os.path.join(self.city, "on")) as fh:
            self.assertEqual(fh.read(), first)


class TestClaudeMd(PackCase):
    def test_the_pointer_is_appended_after_the_users_text(self):
        self.assertOk(self.pack())
        self.assertEqual(read_text(self.t("CLAUDE.md")),
                         USER_CLAUDE_MD + POINTER + "\n")

    def test_a_missing_claude_md_is_created_with_the_pointer(self):
        os.remove(self.t("CLAUDE.md"))
        self.assertOk(self.pack())
        self.assertEqual(read_text(self.t("CLAUDE.md")), POINTER + "\n")

    def test_no_final_newline_still_gives_the_pointer_its_own_line(self):
        write_text(self.t("CLAUDE.md"), "Be nice.")
        self.assertOk(self.pack())
        self.assertEqual(read_text(self.t("CLAUDE.md")),
                         "Be nice.\n" + POINTER + "\n")

    def test_a_claude_md_that_has_the_line_is_kept(self):
        text = "top\n" + POINTER + "\nbottom\n"
        write_text(self.t("CLAUDE.md"), text)
        self.assertOk(self.pack())
        self.assertEqual(read_text(self.t("CLAUDE.md")), text)


class TestLanguage(PackCase):
    def default_conf(self):
        return conf_dict(self.s("bin", "agent.conf.default"))

    def test_language_is_set(self):
        self.assertOk(self.pack("--language", "zh"))
        self.assertEqual(conf_dict(self.t("agent.conf"))["language"], "zh")

    def test_every_other_key_is_the_template(self):
        self.assertOk(self.pack("--language", "zh"))
        conf = conf_dict(self.t("agent.conf"))
        want = self.default_conf()
        want["language"] = "zh"
        self.assertEqual(conf, want)

    def test_no_flag_keeps_the_template_language(self):
        self.assertOk(self.pack())
        self.assertEqual(conf_dict(self.t("agent.conf"))["language"],
                         self.default_conf()["language"])

    def test_an_existing_conf_gets_the_language_and_keeps_the_rest(self):
        text = read_text(self.s("bin", "agent.conf.default"))
        text = re.sub(r"(?m)^max_agents=.*$", "max_agents=2", text)
        write_text(self.t("agent.conf"), text)
        self.assertOk(self.pack("--language", "zh"))
        conf = conf_dict(self.t("agent.conf"))
        self.assertEqual(conf["language"], "zh")
        self.assertEqual(conf["max_agents"], "2")

    def test_a_bad_language_is_refused_and_nothing_is_written(self):
        before = snapshot(self.target)
        result = self.pack("--language", "Chinese!")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("language", (result.stdout + result.stderr).lower())
        self.assertEqual(snapshot(self.target), before)


class TestIdempotent(PackCase):
    def test_a_second_run_changes_not_one_byte(self):
        self.assertOk(self.pack("--language", "zh"))
        before = snapshot(self.target)
        self.assertOk(self.pack("--language", "zh"))
        self.assertEqual(snapshot(self.target), before)

    def test_a_second_run_without_the_flag_changes_nothing_either(self):
        self.assertOk(self.pack("--language", "zh"))
        before = snapshot(self.target)
        self.assertOk(self.pack())
        self.assertEqual(snapshot(self.target), before)

    def test_an_older_pack_is_left_alone_without_update(self):
        self.assertOk(self.pack("--language", "zh"))
        before = snapshot(self.target)
        self.set_source_version("9.9.9")
        with open(self.s("bin", "agent-start.sh"), "a") as fh:
            fh.write("# newer\n")
        out = self.assertOk(self.pack())
        self.assertEqual(snapshot(self.target), before)
        self.assertIn("--update", out)


class TestUpdate(PackCase):
    def setUp(self):
        super().setUp()
        # a script that the next source version drops
        write_text(self.s("bin", "agent-old.sh"), "#!/usr/bin/env bash\n")
        os.chmod(self.s("bin", "agent-old.sh"), 0o755)
        self.assertOk(self.pack("--language", "zh"))

        # the human keeps working in the repo
        text =re.sub(r"(?m)^max_agents=.*$", "max_agents=2",
                      read_text(self.t("agent.conf")))
        write_text(self.t("agent.conf"), text)
        write_text(self.t("agent_todo.txt"), "a task\n")
        with open(self.t("CLAUDE.md"), "a") as fh:
            fh.write("More.\n")
        data = self.settings()
        data["theme"] = "dark"
        write_text(self.t(".claude", "settings.json"),
                   json.dumps(data, indent=2) + "\n")
        write_text(self.t(".claude", "skills", "mine", "SKILL.md"),
                   "---\nname: mine\ndescription: mine\n---\nmine\n")
        write_text(self.t(".claude", "agents", "mine.md"), "mine\n")
        self.user_files = {name: read_bytes(self.t(name)) for name in (
            "agent.conf", "agent_todo.txt", "CLAUDE.md", "AGENTS.md",
            ".gitignore", os.path.join(".claude", "settings.json"),
            os.path.join(".claude", "skills", "mine", "SKILL.md"),
            os.path.join(".claude", "agents", "mine.md"))}

        # a newer source
        self.set_source_version("9.9.9")
        os.remove(self.s("bin", "agent-old.sh"))
        write_text(self.s("bin", "agent-new.sh"), "#!/usr/bin/env bash\n")
        os.chmod(self.s("bin", "agent-new.sh"), 0o755)
        for parts in (("bin", "agent-start.sh"), ("PRINCIPLES.md",),
                      ("skills", "dispatch", "SKILL.md"),
                      ("agents", "worker.md")):
            with open(self.s(*parts), "a") as fh:
                fh.write("\n# newer ${CLAUDE_PLUGIN_ROOT}/bin/x\n")

        self.out = self.assertOk(self.pack("--update"))

    def test_bin_is_refreshed(self):
        self.assertEqual(read_bytes(self.p("bin", "agent-start.sh")),
                         read_bytes(self.s("bin", "agent-start.sh")))

    def test_a_new_script_arrives_executable(self):
        self.assertTrue(os.access(self.p("bin", "agent-new.sh"), os.X_OK))

    def test_a_script_the_source_dropped_is_gone(self):
        self.assertFalse(os.path.exists(self.p("bin", "agent-old.sh")))

    def test_principles_is_refreshed(self):
        self.assertEqual(read_bytes(self.p("PRINCIPLES.md")),
                         read_bytes(self.s("PRINCIPLES.md")))

    def test_skills_and_agents_are_refreshed(self):
        self.assertEqual(
            read_text(self.t(".claude", "skills", "dispatch", "SKILL.md")),
            transform(read_text(self.s("skills", "dispatch", "SKILL.md"))))
        self.assertEqual(
            read_text(self.t(".claude", "agents", "worker.md")),
            transform(read_text(self.s("agents", "worker.md"))))

    def test_the_version_marker_moves(self):
        self.assertEqual(read_text(self.p("VERSION")), "9.9.9\n")

    def test_the_users_files_are_untouched(self):
        for name, before in self.user_files.items():
            with self.subTest(name=name):
                self.assertEqual(read_bytes(self.t(name)), before)

    def test_a_second_update_changes_nothing(self):
        before = snapshot(self.target)
        self.assertOk(self.pack("--update"))
        self.assertEqual(snapshot(self.target), before)


class TestRunsFromThePack(PackCase):
    def setUp(self):
        super().setUp()
        self.assertOk(self.pack("--language", "zh"))
        self.pack_root = os.path.join(self.target, PACK)

    def test_agent_start_prints_role_roots_rules_and_quiz(self):
        out = self.assertOk(self.packed(
            "agent-start.sh",
            env={"CLAUDE_PROJECT_DIR": self.target,
                 "AGENT_ROLE": "task-manager"}))
        self.assertIn("ROLE:", out)
        self.assertIn("PROJECT: %s | PLUGIN: %s"
                      % (self.target, self.pack_root), out)
        self.assertIn("RULES: read %s/PRINCIPLES.md now (S8)."
                      % self.pack_root, out)
        self.assertIn("QUIZ: run %s/bin/agent-start.sh --quiz, then --answer."
                      % self.pack_root, out)
        self.assertIn("LANGUAGE: zh", out)
        self.assertNotIn("not set up", out)

    def test_the_settings_hook_runs_as_written(self):
        cmd = [c for c in session_start_commands(self.settings())
               if "agent-start.sh" in c][0]
        result = subprocess.run(
            ["bash", "-c", cmd], cwd=self.base,
            env=self.env({"CLAUDE_PROJECT_DIR": self.target,
                          "AGENT_ROLE": "task-manager"}),
            input=json.dumps({"cwd": self.target, "session_id": "pack-1",
                              "source": "startup"}),
            capture_output=True, text=True, timeout=90)
        out = self.assertOk(result)
        self.assertIn("PLUGIN: %s" % self.pack_root, out)
        self.assertIn("QUIZ:", out)

    def test_the_quiz_runs_from_the_pack(self):
        out = self.assertOk(self.packed("agent-start.sh", "--quiz"))
        self.assertIn("Q29.", out)

    def test_the_settings_script_runs_from_the_pack(self):
        self.assertOk(self.packed("agent-settings.sh", "language", "en"))
        self.assertEqual(conf_dict(self.t("agent.conf"))["language"], "en")

    def test_the_file_script_runs_from_the_pack(self):
        self.assertOk(self.packed("agent-file.sh", "idea", "add", "packed"))
        self.assertIn("packed", read_text(self.t("agent_ideas.txt")))

    def test_the_runtime_script_runs_from_the_pack(self):
        out = self.assertOk(self.packed("agent-runtime.sh", "kind",
                                        env={"AGENT_RUNTIME": "plain"}))
        self.assertEqual(out.strip(), "plain")

    def test_pycache_never_shows_in_git_status(self):
        self.assertOk(self.packed("agent-settings.sh", "language", "en"))
        status = git(self.target, "status", "--porcelain",
                     "--untracked-files=all")
        self.assertNotIn("__pycache__", status)


class TestTheOutput(PackCase):
    def test_it_prints_the_one_sentence_cloud_install(self):
        out = self.assertOk(self.pack("--language", "zh"))
        self.assertIn(ONE_SENTENCE % "zh", out)

    def test_the_sentence_carries_the_language_in_use(self):
        out = self.assertOk(self.pack("--language", "ms"))
        self.assertIn(ONE_SENTENCE % "ms", out)

    def test_it_reminds_about_the_github_app(self):
        out = self.assertOk(self.pack("--language", "zh"))
        self.assertIn("Claude GitHub App", out)

    def test_it_never_asks_the_human_to_paste_what_it_already_merged(self):
        out = self.assertOk(self.pack("--language", "zh"))
        self.assertNotIn("Paste that permission block", out)
        self.assertNotIn("a human must paste it", out)

    def test_it_still_passes_on_the_cloud_browser_hint(self):
        out = self.assertOk(self.pack("--language", "zh"))
        self.assertIn("agent-runtime.sh browser prints none", out)

    def test_each_file_line_names_the_real_repo_path(self):
        out = self.assertOk(self.pack("--language", "zh"))
        self.assertIn("created: .claude/auto-pipeline/bin/agent-start.sh", out)
        self.assertIn("created: .claude/auto-pipeline/PRINCIPLES.md", out)
        self.assertIn("created: .claude/skills/dispatch/SKILL.md", out)
        self.assertIn("created: .claude/agents/worker.md", out)

    def test_it_says_to_commit_and_push(self):
        lowered = self.assertOk(self.pack("--language", "zh")).lower()
        self.assertIn("commit", lowered)
        self.assertIn("push", lowered)


class TestUsage(PackCase):
    def test_help_exits_zero_and_writes_nothing(self):
        before = snapshot(self.target)
        result = subprocess.run([self.s("bin", "agent-cloud-pack.sh"), "-h"],
                                cwd=self.target, env=self.env(),
                                capture_output=True, text=True, input="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--update", result.stdout)
        self.assertEqual(snapshot(self.target), before)

    def test_no_repo_path_exits_two(self):
        before = snapshot(self.target)
        result = self.pack(target="", cwd=self.target)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(snapshot(self.target), before)

    def test_a_missing_directory_exits_two(self):
        result = self.pack(target=os.path.join(self.base, "nope"))
        self.assertEqual(result.returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.base, "nope")))

    def test_an_unknown_flag_exits_two(self):
        before = snapshot(self.target)
        result = self.pack("--bogus")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(snapshot(self.target), before)

    def test_a_subdirectory_packs_the_repo_root(self):
        os.makedirs(self.t("sub"))
        self.assertOk(self.pack(target=self.t("sub")))
        self.assertTrue(os.path.isfile(self.p("bin", "agent-start.sh")))
        self.assertFalse(os.path.exists(self.t("sub", ".claude")))


class TestFailsLoudly(PackCase):
    """A step that fails mid-way stops the pack with a non-zero exit, and the
    success footer (the one-sentence install) is never printed after it."""

    def test_a_failing_init_step_stops_the_pack(self):
        os.makedirs(self.t("AGENTS.md"))   # agent-init.sh cannot write its line
        result = self.pack("--language", "zh")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(ONE_SENTENCE % "zh", result.stdout)
        self.assertIn("agent-init.sh", result.stdout + result.stderr)

    def test_a_failing_settings_merge_stops_the_pack(self):
        write_text(self.t(".claude", "settings.json"), '{"hooks": ["x"]}\n')
        result = self.pack("--language", "zh")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(ONE_SENTENCE % "zh", result.stdout)
        self.assertIn("settings.json", result.stdout + result.stderr)


class TestOneSentenceInstall(PackCase):
    """The acceptance test: a plain clone of this repo, one line, done."""

    def setUp(self):
        super().setUp()
        self.stage = os.path.join(self.base, "stage")
        os.makedirs(self.stage)
        listed = subprocess.run(
            ["git", "-C", ROOT, "ls-files", "-co", "--exclude-standard"],
            check=True, capture_output=True, text=True).stdout.splitlines()
        for rel in listed:
            full = os.path.join(ROOT, rel)
            if not os.path.isfile(full) or "__pycache__" in rel:
                continue
            dest = os.path.join(self.stage, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(full, dest)
        subprocess.run(["git", "init", "-q", self.stage], check=True,
                       capture_output=True)
        git(self.stage, "config", "user.email", "t@t.t")
        git(self.stage, "config", "user.name", "t")
        git(self.stage, "add", "-A")
        git(self.stage, "commit", "-q", "-m", "stage")
        ap = os.path.join(self.base, "ap")
        line = "git clone -q %s %s && %s/bin/agent-cloud-pack.sh . --language zh" % (
            self.stage, ap, ap)
        self.result = subprocess.run(["bash", "-c", line], cwd=self.target,
                                     env=self.env(), capture_output=True,
                                     text=True, input="", timeout=180)

    def test_it_sets_the_repo_up(self):
        self.assertOk(self.result)
        self.assertTrue(os.access(self.p("bin", "agent-start.sh"), os.X_OK))
        self.assertTrue(os.path.isfile(self.p("PRINCIPLES.md")))
        self.assertTrue(os.path.isfile(
            self.t(".claude", "skills", "dispatch", "SKILL.md")))
        self.assertTrue(os.path.isfile(self.t(".claude", "agents", "worker.md")))
        self.assertEqual(conf_dict(self.t("agent.conf"))["language"], "zh")
        self.assertIn(POINTER, read_text(self.t("CLAUDE.md")))
        cmds = session_start_commands(self.settings())
        self.assertEqual([c for c in cmds if "agent-start.sh" in c], [HOOK_CMD])

    def test_the_packed_hook_then_runs(self):
        self.assertOk(self.result)
        result = subprocess.run(
            ["bash", "-c", HOOK_CMD], cwd=self.base,
            env=self.env({"CLAUDE_PROJECT_DIR": self.target,
                          "AGENT_ROLE": "task-manager"}),
            input="", capture_output=True, text=True, timeout=90)
        out = self.assertOk(result)
        self.assertIn("PLUGIN: %s" % os.path.join(self.target, PACK), out)
        self.assertIn("QUIZ:", out)


class TestConfSync(PackCase):
    """agent.conf written before a template key existed gains it via --update
    (conf-sync), and only via --update."""

    def setUp(self):
        super().setUp()
        self.assertOk(self.pack("--language", "zh"))
        # a repo whose agent.conf predates a template key that later arrives
        text = "\n".join(line for line in
                          read_text(self.t("agent.conf")).splitlines()
                          if not line.startswith("stall_min="))
        write_text(self.t("agent.conf"), text + "\n")
        self.set_source_version("9.9.9")
        with open(self.s("bin", "agent.conf.default"), "a") as fh:
            fh.write("stall_min=10\n")

    def test_update_adds_the_missing_template_key(self):
        out = self.assertOk(self.pack("--update"))
        self.assertIn("added stall_min=10", out)
        self.assertEqual(conf_dict(self.t("agent.conf"))["stall_min"], "10")

    def test_plain_run_does_not_add_it(self):
        # without --update the pack is left alone anyway (older VERSION), but
        # prove sync itself never runs by checking the key stays missing
        self.pack()
        self.assertNotIn("stall_min", conf_dict(self.t("agent.conf")))


if __name__ == "__main__":
    unittest.main()
