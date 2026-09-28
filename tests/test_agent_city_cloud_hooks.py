"""Failing tests: bin/agent-city.sh cloud-hooks (requirements/city.md, "Joining").

WHY. A claude.ai cloud session opened on several repos at once starts above
them (e.g. /home/user, not a repo). Claude Code then loads no repo's
.claude/settings.json, so the cloud pack's SessionStart sender and city
hooks never run, no matter how many of the repos carry the pack. The fix is
one level up: user-level settings ($HOME/.claude/settings.json), written by
the environment's own Setup script (pasted by the owner) before Claude Code
even starts.

CONTRACT

  ./agent-city.sh cloud-hooks
    1. Copies every regular file of this script's own bin/ (this plugin
       copy's bin/, skip __pycache__) to $AGENT_CITY_HOME/bin (default
       $HOME/.claude/agent-city/bin), same bytes and mode. Idempotent.
    2. Merges into $HOME/.claude/settings.json (created if missing; every
       existing key and hook kept):
         - one SessionStart hook that starts the sender when
           AGENT_CITY_RELAY is set
         - one hook per hooks/hooks.json entry that runs agent-city-hook.sh,
           same event and matcher
       Each added command first checks the session is not already inside a
       repo carrying the project-level cloud pack
       (.claude/auto-pipeline/bin/agent-city-hook.sh under
       $CLAUDE_PROJECT_DIR) -- that repo's own project hooks send instead,
       so nothing is ever sent twice.
       Compares by exact command string: a second run changes not one byte.
    3. Settings that are not valid JSON: exit 2, one stderr line naming the
       file, the file is left untouched.
    4. Never prints AGENT_CITY_RELAY or the key it carries.
    5. Does not need AGENT_CITY_RELAY set. Does not start the sender.

Run: python3 -m unittest tests.test_agent_city_cloud_hooks
"""

import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase  # noqa: E402

REAL_HOOKS_JSON = os.path.join(ROOT, "hooks", "hooks.json")


def city_hook_events():
    """(event, matcher) pairs hooks/hooks.json wires to agent-city-hook.sh."""
    with open(REAL_HOOKS_JSON) as fh:
        hooks = json.load(fh)["hooks"]
    pairs = []
    for event, entries in hooks.items():
        for entry in entries:
            if any("agent-city-hook.sh" in h.get("command", "")
                   for h in entry.get("hooks", [])):
                pairs.append((event, entry.get("matcher")))
    return pairs


class CloudHooksCase(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        # hooks/hooks.json is not on ScriptRepo's COPY_PLUGIN list (only
        # PRINCIPLES.md is): the script reads it from $PLUGIN_ROOT/hooks/,
        # so the temp plugin copy needs its own.
        dst = self.repo.plugin_path("hooks", "hooks.json")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(REAL_HOOKS_JSON, dst)
        self.home = self.repo.fake_home()
        self.settings_path = os.path.join(self.home, ".claude", "settings.json")
        self.city_home = os.path.join(self.home, ".claude", "agent-city")

    def run_cloud_hooks(self, env=None):
        return self.repo.run("agent-city.sh", "cloud-hooks", env=env, timeout=30)

    def send_cmd(self, city_home=None):
        home = city_home or self.city_home
        return ('[ -n "${AGENT_CITY_RELAY:-}" ] && '
                '[ ! -f "${CLAUDE_PROJECT_DIR:-/nonexistent}/.claude/auto-pipeline'
                '/bin/agent-city-hook.sh" ] && '
                'bash "%s/bin/agent-city.sh" send; exit 0') % home

    def city_hook_cmd(self, city_home=None):
        home = city_home or self.city_home
        return ('[ -f "${AGENT_CITY_DIR:-$HOME/.cache/agent-city}/on" ] && '
                '[ ! -f "${CLAUDE_PROJECT_DIR:-/nonexistent}/.claude/auto-pipeline'
                '/bin/agent-city-hook.sh" ] && '
                'bash "%s/bin/agent-city-hook.sh"; exit 0') % home

    def read_settings(self):
        with open(self.settings_path) as fh:
            return json.load(fh)


class TestFreshHome(CloudHooksCase):
    def test_exit_zero(self):
        result = self.run_cloud_hooks()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bin_is_copied(self):
        self.run_cloud_hooks()
        dst = os.path.join(self.city_home, "bin", "agent-city.sh")
        self.assertTrue(os.path.isfile(dst))
        with open(dst, "rb") as a, \
             open(self.repo.plugin_path("bin", "agent-city.sh"), "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_bin_copy_skips_pycache(self):
        pycache = self.repo.plugin_path("bin", "__pycache__")
        os.makedirs(pycache, exist_ok=True)
        with open(os.path.join(pycache, "junk.pyc"), "w") as fh:
            fh.write("x")
        self.run_cloud_hooks()
        self.assertFalse(
            os.path.exists(os.path.join(self.city_home, "bin", "__pycache__")))

    def test_settings_created_with_send_hook(self):
        self.run_cloud_hooks()
        data = self.read_settings()
        cmds = [h.get("command") for entry in data["hooks"]["SessionStart"]
                for h in entry.get("hooks", [])]
        self.assertIn(self.send_cmd(), cmds)

    def test_settings_gets_one_city_hook_per_hooks_json_entry(self):
        self.run_cloud_hooks()
        data = self.read_settings()
        expect_cmd = self.city_hook_cmd()
        for event, matcher in city_hook_events():
            entries = data["hooks"].get(event, [])
            found = [e for e in entries if e.get("matcher") == matcher
                     and any(h.get("command") == expect_cmd
                             for h in e.get("hooks", []))]
            self.assertEqual(
                len(found), 1,
                "missing/duplicate city hook for %s matcher=%r: %r"
                % (event, matcher, entries))

    def test_never_needs_the_relay_secret(self):
        result = self.run_cloud_hooks(env={"AGENT_CITY_RELAY": ""})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_never_starts_the_sender(self):
        self.run_cloud_hooks()
        self.assertFalse(os.path.exists(os.path.join(self.city_home, "on")))
        # AGENT_CITY_DIR default ($HOME/.cache/agent-city) untouched too.
        self.assertFalse(
            os.path.exists(os.path.join(self.home, ".cache", "agent-city", "on")))


class TestIdempotent(CloudHooksCase):
    def test_second_run_is_byte_identical(self):
        self.run_cloud_hooks()
        with open(self.settings_path, "rb") as fh:
            before = fh.read()
        result = self.run_cloud_hooks()
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(self.settings_path, "rb") as fh:
            after = fh.read()
        self.assertEqual(before, after)

    def test_second_run_says_already_there(self):
        self.run_cloud_hooks()
        result = self.run_cloud_hooks()
        self.assertIn("already there", result.stdout)


class TestKeepsExisting(CloudHooksCase):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
        self.existing = {
            "permissions": {"allow": ["Bash(echo:*)"]},
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "echo mine"}]}
                ]
            },
        }
        with open(self.settings_path, "w") as fh:
            json.dump(self.existing, fh)

    def test_existing_key_and_hook_survive(self):
        self.run_cloud_hooks()
        data = self.read_settings()
        self.assertEqual(data["permissions"]["allow"], ["Bash(echo:*)"])
        stop_cmds = [h.get("command") for entry in data["hooks"]["Stop"]
                     for h in entry.get("hooks", [])]
        self.assertIn("echo mine", stop_cmds)

    def test_new_hooks_still_added(self):
        self.run_cloud_hooks()
        data = self.read_settings()
        cmds = [h.get("command") for entry in data["hooks"]["SessionStart"]
                for h in entry.get("hooks", [])]
        self.assertIn(self.send_cmd(), cmds)


class TestInvalidJson(CloudHooksCase):
    def test_exit_two_file_untouched(self):
        os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
        with open(self.settings_path, "w") as fh:
            fh.write("{not json")
        result = self.run_cloud_hooks()
        self.assertEqual(result.returncode, 2)
        self.assertIn(self.settings_path, result.stderr)
        with open(self.settings_path) as fh:
            self.assertEqual(fh.read(), "{not json")


class TestKeyNeverPrinted(CloudHooksCase):
    def test_secret_not_in_output(self):
        result = self.run_cloud_hooks(
            env={"AGENT_CITY_RELAY": "http://x.invalid SECRETKEY123"})
        self.assertNotIn("SECRETKEY123", result.stdout)
        self.assertNotIn("SECRETKEY123", result.stderr)


class TestGuard(CloudHooksCase):
    """The written hook commands stand down when a project-level pack
    already covers this session's cwd, so nothing is ever sent twice."""

    def setUp(self):
        super().setUp()
        self.run_cloud_hooks()
        self.data = self.read_settings()
        self.city_dir = os.path.join(self.repo.base, "livecity")
        os.makedirs(self.city_dir, exist_ok=True)
        with open(os.path.join(self.city_dir, "on"), "w") as fh:
            fh.write("%s 4777\n" % os.getpid())
        self.events = os.path.join(self.city_dir, "events.jsonl")

    def pretooluse_cmd(self):
        for entry in self.data["hooks"]["PreToolUse"]:
            for h in entry.get("hooks", []):
                if "agent-city-hook.sh" in h.get("command", ""):
                    return h["command"]
        self.fail("no PreToolUse city hook written")

    def run_hook_command(self, project_dir):
        env = dict(os.environ)
        env["AGENT_CITY_DIR"] = self.city_dir
        env["CLAUDE_PROJECT_DIR"] = project_dir
        env["PATH"] = os.environ.get("PATH", "")
        return subprocess.run(
            ["bash", "-c", self.pretooluse_cmd()],
            input='{"hook_event_name":"PreToolUse"}',
            env=env, capture_output=True, text=True, timeout=20)

    def test_project_pack_present_sends_nothing(self):
        packed = os.path.join(self.repo.base, "packed_repo")
        os.makedirs(os.path.join(packed, ".claude", "auto-pipeline", "bin"),
                    exist_ok=True)
        with open(os.path.join(packed, ".claude", "auto-pipeline", "bin",
                                "agent-city-hook.sh"), "w") as fh:
            fh.write("#!/usr/bin/env bash\nexit 0\n")
        result = self.run_hook_command(packed)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(os.path.exists(self.events))

    def test_no_project_pack_sends_one_line(self):
        bare = os.path.join(self.repo.base, "bare_repo")
        os.makedirs(bare, exist_ok=True)
        result = self.run_hook_command(bare)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.path.exists(self.events))
        with open(self.events) as fh:
            lines = [l for l in fh if l.strip()]
        self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
