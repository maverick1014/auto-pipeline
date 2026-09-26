"""Failing tests: bin/agent-city.sh join | leave | status, and the relay
interval it passes to the server (requirements/city.md, "Joining").

  ./agent-city.sh join
      Run by the person, in their own terminal, inside the repo (main repo
      or any of its worktrees). Joining is per repo.
      1. Refuses, before asking anything, when:
           the repo has no origin remote, or its origin is a local path
           or file:// (not shared, stays local)   (message names "origin")
           .secrets/ is not git-ignored    (message names ".secrets")
      2. Asks for the relay address, then the team key with echo off
         (read -rs). Prompts go to stderr.
      3. Hands the key to `python3 agent_city_relay.py join --address A
         --file F` on stdin (never argv), which tests the relay and writes
         <main repo root>/.secrets/agent-city-relay (mode 0600) only when
         the relay says ok.
      4. Prints "JOINED: <rid> -> <relay host>" and exits 0.
      Bad address, empty key, relay refused or unreachable: a short reason,
      nothing saved, exit 1. The key never appears in stdout or stderr.

  ./agent-city.sh leave
      Deletes <main repo root>/.secrets/agent-city-relay. "LEFT: ..." and
      exit 0, also when it was not joined.

  ./agent-city.sh status
      Keeps its CITY line, and adds one TEAM line for this repo:
      "TEAM: not joined" or "TEAM: joined <relay host>". Never the key.

  ./agent-city.sh start
      Passes --relay-sec <city_relay_sec> (agent.conf, default 5) to serve.

  The usage text lists join and leave.

Never the real ~/.claude/agent-city (AGENT_CITY_HOME is a temp dir), never a
real key, never a real relay (tests/relayhelp.py FakeRelay on 127.0.0.1).

Run: python3 -m unittest tests.test_agent_city_join
"""

import os
import signal
import socket
import stat
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from relayhelp import FAKE_KEY, FakeRelay, wait_for  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402


def closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class JoinCase(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.fake = FakeRelay()
        self.addCleanup(self.fake.stop)
        self.city = os.path.join(self.repo.base, "city")
        self.git("remote", "add", "origin", "git@github.com:Acme/Shop.git")
        with open(self.repo.path(".gitignore"), "w") as fh:
            fh.write(".secrets/\n")

    def tearDown(self):
        on = os.path.join(self.city, "on")
        if os.path.exists(on):
            try:
                with open(on) as fh:
                    os.kill(int(fh.read().split()[0]), signal.SIGTERM)
            except (OSError, ValueError, IndexError):
                pass
        super().tearDown()

    def git(self, *args, cwd=None):
        return subprocess.run(["git", "-C", cwd or self.repo.dir] + list(args),
                              check=True, capture_output=True, text=True).stdout

    def city_run(self, *args, stdin=None, cwd=None):
        env = {"AGENT_CITY_DIR": self.city,
               "AGENT_CITY_HOME": os.path.join(self.repo.base, "cityhome")}
        return self.repo.run("agent-city.sh", *args, env=env, stdin=stdin, cwd=cwd, timeout=30)

    def join(self, address=None, key=FAKE_KEY, cwd=None):
        address = self.fake.url if address is None else address
        return self.city_run("join", stdin="%s\n%s\n" % (address, key), cwd=cwd)

    @property
    def secret(self):
        return self.repo.path(".secrets", "agent-city-relay")

    def read_secret(self):
        with open(self.secret) as fh:
            rows = dict(l.strip().split("=", 1) for l in fh if "=" in l)
        return {k.strip(): v.strip() for k, v in rows.items()}

    def assert_no_key(self, result, key=FAKE_KEY):
        self.assertNotIn(key, result.stdout + result.stderr)

    def assert_refused(self, result, word=None):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(os.path.exists(self.secret), "nothing may be saved")
        if word:
            self.assertIn(word, result.stdout + result.stderr)


class TestJoin(JoinCase):
    def test_join_saves_the_file_0600(self):
        result = self.join()
        self.assertOk(result)
        self.assertIn("JOINED: github.com/acme/shop -> " + self.fake.host, result.stdout)
        self.assertEqual(self.read_secret(), {"address": self.fake.url, "key": FAKE_KEY})
        self.assertEqual(stat.S_IMODE(os.stat(self.secret).st_mode), 0o600)
        self.assert_no_key(result)

    def test_join_tested_the_relay_first(self):
        self.assertOk(self.join())
        self.assertEqual(len(self.fake.sync_bodies()), 1)
        self.assertEqual(self.fake.requests[0]["auth"], "Bearer " + FAKE_KEY)

    def test_join_from_a_worktree_saves_in_the_main_repo(self):
        wt = self.repo.detach_scripts_to_worktree()
        self.assertOk(self.join(cwd=wt))
        self.assertTrue(os.path.exists(self.secret))
        self.assertFalse(os.path.exists(os.path.join(wt, ".secrets", "agent-city-relay")))

    def test_refused_key(self):
        result = self.join(key="not-the-team-key")
        self.assert_refused(result, "refused")
        self.assert_no_key(result, "not-the-team-key")

    def test_relay_down(self):
        result = self.join(address="http://127.0.0.1:%d" % closed_port())
        self.assert_refused(result, "cannot reach")
        self.assert_no_key(result)

    def test_bad_address(self):
        self.assert_refused(self.join(address="http://relay.example.com"))
        self.assert_refused(self.join(address=""))
        self.assertEqual(self.fake.requests, [])

    def test_empty_key(self):
        self.assert_refused(self.join(key=""))
        self.assertEqual(self.fake.requests, [])

    def test_no_origin(self):
        self.git("remote", "remove", "origin")
        result = self.join()
        self.assert_refused(result, "origin")
        self.assertEqual(self.fake.requests, [])

    def test_local_path_origin_stays_local(self):
        for url in ("/Users/ann/repos/shop.git", "file:///Users/ann/shop.git"):
            with self.subTest(url=url):
                self.git("remote", "set-url", "origin", url)
                result = self.join()
                self.assert_refused(result, "origin")
                self.assertEqual(self.fake.requests, [])

    def test_secrets_not_ignored(self):
        os.remove(self.repo.path(".gitignore"))
        result = self.join()
        self.assert_refused(result, ".secrets")
        self.assertEqual(self.fake.requests, [])
        self.assert_no_key(result)


class TestLeaveAndStatus(JoinCase):
    def test_leave(self):
        self.assertOk(self.join())
        result = self.city_run("leave")
        self.assertOk(result)
        self.assertIn("LEFT", result.stdout)
        self.assertFalse(os.path.exists(self.secret))
        again = self.city_run("leave")
        self.assertOk(again)
        self.assertIn("LEFT", again.stdout)

    def test_status_team_line(self):
        result = self.city_run("status")
        self.assertOk(result)
        self.assertIn("CITY: not running", result.stdout)
        self.assertIn("TEAM: not joined", result.stdout)
        self.assertOk(self.join())
        result = self.city_run("status")
        self.assertIn("TEAM: joined " + self.fake.host, result.stdout)
        self.assert_no_key(result)

    def test_usage_lists_join_and_leave(self):
        result = self.city_run("-h")
        self.assertOk(result)
        self.assertIn("join", result.stdout)
        self.assertIn("leave", result.stdout)


class TestStartPassesRelaySec(JoinCase):
    def test_relay_sec_from_agent_conf(self):
        self.repo.set_conf("city_port", str(free_port()))
        self.repo.set_conf("city_relay_sec", "7")
        self.assertOk(self.city_run("start"))
        with open(os.path.join(self.city, "on")) as fh:
            pid = fh.read().split()[0]
        args = subprocess.run(["ps", "-o", "args=", "-p", pid],
                              capture_output=True, text=True).stdout
        self.assertIn("--relay-sec 7", args)

    def test_relay_sec_default_when_missing(self):
        self.repo.set_conf("city_port", str(free_port()))
        self.repo.unset_conf("city_relay_sec")
        self.assertOk(self.city_run("start"))
        with open(os.path.join(self.city, "on")) as fh:
            pid = fh.read().split()[0]
        self.assertTrue(wait_for(lambda: subprocess.run(
            ["ps", "-o", "args=", "-p", pid], capture_output=True, text=True).stdout))
        args = subprocess.run(["ps", "-o", "args=", "-p", pid],
                              capture_output=True, text=True).stdout
        self.assertIn("--relay-sec 5", args)


if __name__ == "__main__":
    unittest.main()
