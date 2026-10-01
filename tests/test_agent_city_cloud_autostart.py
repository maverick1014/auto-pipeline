"""Failing tests, cloud-city-1 slice 3b: the check line and the auto-start
(requirements/city.md, "Cloud page"; owner, 2026-10-01: he never has to type
`agent-city start` for the cloud page).

The marker: <AGENT_CITY_HOME>/cloud (default ~/.claude/agent-city/cloud) holds
the relay hosts that said the cloud page is on (bin/agent_city_relay.py
read_cloud / set_cloud, the `cloud` command; tests/test_agent_city_cloud_upload.py).

  ./agent-city.sh status
      Inside a joined repo, after the TEAM line, one line:
          CLOUD: on <relay host>     the marker names this repo's relay host
          CLOUD: off                 it does not
      Outside a repo: one "CLOUD: on <host>" per joined relay host the marker
      names (each host once), else one "CLOUD: off" when a repo is joined.
      Not joined: no CLOUD line at all (nothing changes for a machine that
      never joined). status never talks to the relay and never prints the key.

  ./agent-city.sh autostart
      What the SessionStart hook runs. It prints nothing, always exits 0 and
      comes back at once (the work goes on in the background; a slow or dead
      relay never holds up a session start). In order:
        1. a city server is already running (DIR/on names a live pid) -> nothing
        2. a cloud session (CLAUDE_CODE_REMOTE is set)                -> nothing
        3. this folder's repo is not joined (no .secrets/agent-city-relay
           in its main repo), or it is not in a repo                  -> nothing, no network
        4. the marker names this repo's relay host                    -> start
        5. no marker: one quiet sync to that relay (the `cloud --probe`
           command). The reply says the cloud is on -> the marker is written,
           start. It says off, or no answer                           -> nothing
      start = today's start, with the machine's joined list
      (--joined-list <AGENT_CITY_HOME>/joined-repos.txt): same port rule
      (AGENT_CITY_PORT, city_port), same idle rule (city_idle_min), same RAM
      rule (over the cap it still starts). No browser is opened.

  hooks/hooks.json, SessionStart: one more hook,
      [ -f "<home>/cloud" ] || [ -s "<home>/joined-repos.txt" ]  then
      "${CLAUDE_PLUGIN_ROOT}"/bin/agent-city.sh autostart, and always exit 0,
      where <home> is ${AGENT_CITY_HOME:-$HOME/.claude/agent-city}. A machine
      that never joined pays two file tests and nothing else. It has a
      timeout of at most 10 seconds.

Every test uses a fake relay on 127.0.0.1, a temp city dir, a temp
AGENT_CITY_HOME and a free port. Never the real city, never a real key.

Run: python3 -m unittest tests.test_agent_city_cloud_autostart
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

from relayhelp import FAKE_KEY, wait_for  # noqa: E402
from scripthelp import args_of  # noqa: E402
from test_agent_city_join import JoinCase, free_port  # noqa: E402
import agent_city_relay as rl  # noqa: E402


def cloud_lines(text):
    return [l.strip() for l in text.splitlines() if l.strip().startswith("CLOUD:")]


class CloudCase(JoinCase):
    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.repo.base, "cityhome")
        self.marker = os.path.join(self.home, "cloud")
        self.port = free_port()
        self.open_log = os.path.join(self.repo.base, "open.log")
        for name in ("open", "xdg-open"):
            stub = os.path.join(self.repo.bin, name)
            with open(stub, "w") as fh:
                fh.write("#!/bin/sh\necho \"$@\" >> '%s'\n" % self.open_log)
            os.chmod(stub, 0o755)

    def city_run(self, *args, stdin=None, cwd=None, extra=None):
        env = {"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.home,
               "AGENT_CITY_PORT": str(self.port)}
        env.update(extra or {})
        return self.repo.run("agent-city.sh", *args, env=env, stdin=stdin, cwd=cwd, timeout=30)

    def mark(self, host=None, on=True):
        self.assertTrue(hasattr(rl, "set_cloud"), "agent_city_relay.set_cloud is missing")
        rl.set_cloud(self.marker, host or self.fake.host, on)

    def pid(self):
        try:
            with open(os.path.join(self.city, "on")) as fh:
                pid = int(fh.read().split()[0])
            os.kill(pid, 0)
            return pid
        except (OSError, ValueError, IndexError):
            return None

    def autostart(self, **kw):
        t0 = time.monotonic()
        result = self.city_run("autostart", **kw)
        took = time.monotonic() - t0
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "", "autostart prints nothing")
        self.assertLess(took, 3.0, "autostart must come back at once (%.1f s)" % took)
        return result

    def assert_never_starts(self, wait=2.0):
        time.sleep(wait)
        self.assertIsNone(self.pid(), "a city server was started")


class TestStatusLine(CloudCase):
    def test_not_joined_has_no_cloud_line(self):
        result = self.city_run("status")
        self.assertOk(result)
        self.assertEqual(cloud_lines(result.stdout), [])

    def test_joined_cloud_off(self):
        self.assertOk(self.join())
        before = len(self.fake.requests)
        result = self.city_run("status")
        self.assertOk(result)
        self.assertEqual(cloud_lines(result.stdout), ["CLOUD: off"])
        self.assertIn("TEAM: joined " + self.fake.host, result.stdout)
        self.assertEqual(len(self.fake.requests), before, "status never talks to the relay")

    def test_joined_cloud_on(self):
        self.assertOk(self.join())
        self.mark()
        result = self.city_run("status")
        self.assertEqual(cloud_lines(result.stdout), ["CLOUD: on " + self.fake.host])
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        self.assertLess(lines.index("TEAM: joined " + self.fake.host),
                        lines.index("CLOUD: on " + self.fake.host), "the CLOUD line comes after the TEAM line")
        self.assert_no_key(result)

    def test_marker_of_another_relay_is_not_this_repo(self):
        self.assertOk(self.join())
        self.mark("other-relay.example")
        self.assertEqual(cloud_lines(self.city_run("status").stdout), ["CLOUD: off"])

    def test_join_writes_the_marker_when_the_cloud_is_on(self):
        self.fake.city = True
        self.assertOk(self.join())
        self.assertEqual(rl.read_cloud(self.marker), [self.fake.host])
        self.assertEqual(cloud_lines(self.city_run("status").stdout), ["CLOUD: on " + self.fake.host])

    def test_outside_a_repo(self):
        self.assertOk(self.join())
        outside = tempfile.mkdtemp(prefix="city_out_", dir=self.repo.base)
        self.assertEqual(cloud_lines(self.city_run("status", cwd=outside).stdout), ["CLOUD: off"])
        self.mark()
        self.assertEqual(cloud_lines(self.city_run("status", cwd=outside).stdout),
                         ["CLOUD: on " + self.fake.host])


class TestAutostart(CloudCase):
    def test_marker_on_starts_the_server(self):
        self.assertOk(self.join())
        self.mark()
        self.autostart()
        pid = wait_for(self.pid, timeout=10)
        self.assertTrue(pid, "joined and the cloud is on: the city server must come up by itself")
        args = args_of(pid)
        self.assertIn("serve", args)
        self.assertIn("--joined-list %s" % os.path.join(self.home, "joined-repos.txt"), args)
        self.assertIn("--port %d" % self.port, args)
        self.assertIn("--idle-min", args)
        self.assertFalse(os.path.exists(self.open_log), "no browser is opened")

    def test_marker_on_needs_no_relay(self):
        self.assertOk(self.join())
        self.mark()
        self.fake.mode = "error"
        self.autostart()
        self.assertTrue(wait_for(self.pid, timeout=10), "the marker says on: no probe is needed")

    def test_no_marker_probes_once_and_starts(self):
        self.assertOk(self.join())
        self.fake.city = True
        if os.path.exists(self.marker):
            os.remove(self.marker)     # as on a machine that joined before the cloud page existed
        self.autostart()
        self.assertTrue(wait_for(self.pid, timeout=10), "the relay says the cloud is on: start")
        self.assertEqual(rl.read_cloud(self.marker), [self.fake.host])
        self.assertFalse(os.path.exists(self.open_log))

    def test_cloud_off_starts_nothing(self):
        self.assertOk(self.join())
        before = len(self.fake.requests)
        self.autostart()
        self.assert_never_starts()
        self.assertEqual(len(self.fake.requests) - before, 1, "one quiet question to the relay, no more")
        self.assertEqual(rl.read_cloud(self.marker), [])

    def test_relay_down_starts_nothing_and_does_not_wait(self):
        self.assertOk(self.join())
        self.fake.delay = 4
        self.autostart()          # must come back at once all the same
        self.fake.delay = 0
        self.fake.mode = "error"
        self.autostart()
        self.assert_never_starts(wait=1.5)

    def test_not_joined_does_nothing_at_all(self):
        self.fake.city = True
        self.mark()               # a marker alone never starts a repo that did not join
        self.autostart()
        self.assert_never_starts()
        self.assertEqual(self.fake.requests, [])

    def test_outside_a_repo_does_nothing(self):
        self.assertOk(self.join())
        self.mark()
        outside = tempfile.mkdtemp(prefix="city_out_", dir=self.repo.base)
        self.autostart(cwd=outside)
        self.assert_never_starts()

    def test_cloud_session_does_nothing(self):
        self.assertOk(self.join())
        self.mark()
        before = len(self.fake.requests)
        self.autostart(extra={"CLAUDE_CODE_REMOTE": "true"})
        self.assert_never_starts()
        self.assertEqual(len(self.fake.requests), before)

    def test_already_running_stays_the_same_server(self):
        self.assertOk(self.join())
        self.mark()
        self.autostart()
        pid = wait_for(self.pid, timeout=10)
        self.assertTrue(pid)
        self.autostart()
        time.sleep(1.0)
        self.assertEqual(self.pid(), pid)
        others = subprocess.run(["pgrep", "-f", "serve --dir %s" % self.city],
                                capture_output=True, text=True).stdout.split()
        self.assertEqual(others, [str(pid)], "exactly one server for this city dir")

    def test_from_a_worktree(self):
        self.assertOk(self.join())
        self.mark()
        wt = self.repo.detach_scripts_to_worktree()
        self.autostart(cwd=wt)
        self.assertTrue(wait_for(self.pid, timeout=10), "the join file sits in the main repo")

    def test_key_never_shows(self):
        self.assertOk(self.join())
        self.fake.city = True
        result = self.autostart()
        self.assert_no_key(result)
        pid = wait_for(self.pid, timeout=10)
        self.assertNotIn(FAKE_KEY, args_of(pid) if pid else "")


class TestHookLine(unittest.TestCase):
    def command(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json")) as fh:
            entries = json.load(fh)["hooks"]["SessionStart"]
        hooks = [h for e in entries for h in e.get("hooks", []) if "autostart" in h.get("command", "")]
        self.assertEqual(len(hooks), 1, "one SessionStart hook runs agent-city.sh autostart")
        return hooks[0]

    def test_shape(self):
        hook = self.command()
        cmd = hook["command"]
        self.assertEqual(hook.get("type"), "command")
        self.assertIn("${AGENT_CITY_HOME:-$HOME/.claude/agent-city}", cmd)
        self.assertIn("agent-city.sh", cmd)
        self.assertTrue(cmd.rstrip().endswith("exit 0"), "a session start never fails on the city")
        self.assertLessEqual(hook.get("timeout", 999), 10)

    def test_the_other_session_start_hooks_stay(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json")) as fh:
            entries = json.load(fh)["hooks"]["SessionStart"]
        cmds = [h.get("command", "") for e in entries for h in e.get("hooks", [])]
        self.assertTrue([c for c in cmds if c.rstrip().endswith("agent-start.sh")])
        self.assertTrue([c for c in cmds if "agent-name.sh" in c])

    def run_hook(self, files, stub_exit=0):
        base = tempfile.mkdtemp(prefix="city_hook_")
        self.addCleanup(lambda: __import__("shutil").rmtree(base, ignore_errors=True))
        home = os.path.join(base, "home")
        plugin = os.path.join(base, "plugin")
        os.makedirs(home)
        os.makedirs(os.path.join(plugin, "bin"))
        log = os.path.join(base, "calls.log")
        with open(os.path.join(plugin, "bin", "agent-city.sh"), "w") as fh:
            fh.write("#!/bin/sh\necho \"$@\" >> '%s'\nexit %d\n" % (log, stub_exit))
        os.chmod(os.path.join(plugin, "bin", "agent-city.sh"), 0o755)
        for name, text in files.items():
            with open(os.path.join(home, name), "w") as fh:
                fh.write(text)
        env = dict(os.environ, AGENT_CITY_HOME=home, CLAUDE_PLUGIN_ROOT=plugin)
        proc = subprocess.run(["bash", "-c", self.command()["command"]], env=env,
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        calls = wait_for(lambda: os.path.exists(log) and open(log).read().split("\n"), timeout=1.5) or []
        return [c for c in calls if c]

    def test_never_joined_runs_nothing(self):
        self.assertEqual(self.run_hook({}), [])
        self.assertEqual(self.run_hook({"joined-repos.txt": ""}), [], "an empty list is not joined")

    def test_marker_runs_autostart(self):
        self.assertEqual(self.run_hook({"cloud": "relay.example\n"}), ["autostart"])

    def test_joined_list_runs_autostart(self):
        self.assertEqual(self.run_hook({"joined-repos.txt": "/some/repo\n"}), ["autostart"])

    def test_a_failing_autostart_still_exits_0(self):
        self.assertEqual(self.run_hook({"cloud": "relay.example\n"}, stub_exit=7), ["autostart"])


if __name__ == "__main__":
    unittest.main()
