"""Failing tests: a cloud session sends its city lines to the team relay
(requirements/city.md, "Joining": "Cloud sessions: send only, no page").

A cloud session (claude.ai/code) has no city page and no .secrets/ join file.
It gets the relay from ONE environment secret:

    AGENT_CITY_RELAY="<relay address> <team key>"      (one space between)

bin/agent_city_relay.py gains:

    parse_env(value) -> {"address": str, "key": str} or None
        Exactly two whitespace-separated parts, surrounding space ignored.
        The address must pass check_address(); the key must not be empty.

    RelayHub(..., env_join=None, send_only=False)
        env_join {"address", "key"}: every line whose repo has a shared
        origin goes to that one team; no join file is read. A repo with no
        shared origin still stays local.
        send_only: tick() still syncs (sends) and still moves "after", but
        always returns [] (a cloud session shows no one).

    python3 agent_city_relay.py send --dir DIR [--relay-sec S] [--idle-sec S]
        The cloud sender. Reads AGENT_CITY_RELAY from the environment.
          not set            -> exit 1, "SEND: AGENT_CITY_RELAY is not set"
          set but malformed  -> exit 2, "SEND: AGENT_CITY_RELAY must be
                                '<address> <key>'"; the value is never printed
          DIR/on names a live pid -> exit 0, "SEND: already running"; no
                                second sender
        Otherwise: writes DIR/on as "<its pid> 0" (the hook's switch; port 0
        = no page), then tails DIR/events.jsonl from its end, offers every
        new line to RelayHub(env_join=..., send_only=True, relay_sec=S) and
        syncs on its own thread. Stops by itself after idle-sec (default
        1800) with no new line, or on SIGTERM; removes DIR/on on the way out
        when it still names its own pid. Never prints the key.

bin/agent-city.sh gains:

    ./agent-city.sh send
        What the packed cloud SessionStart hook runs when AGENT_CITY_RELAY is
        set. Not set -> "SEND: AGENT_CITY_RELAY is not set", exit 1. Over the
        resource cap -> nothing started, exit 1. Else starts the sender in the
        background (--dir $AGENT_CITY_DIR or its default, --relay-sec
        city_relay_sec, --idle-sec city_idle_min*60), waits for DIR/on and
        prints one line "CITY: sending to the team relay <host>", exit 0.
        Already running -> the same line, exit 0. Never prints the key.

End to end: the real bin/agent-city-hook.sh, fed a hook event while the
sender runs, appends a line; the sender delivers it to the relay.

Fake relay on 127.0.0.1 (tests/relayhelp.py) and temp dirs only. Never the
real ~/.claude/agent-city, never a real key.

Run: python3 -m unittest tests.test_agent_city_relay_send
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
CLIENT = os.path.join(BIN, "agent_city_relay.py")
HOOK = os.path.join(BIN, "agent-city-hook.sh")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

from relayhelp import FAKE_KEY, FakeRelay, add_worktree, hook_line, make_repo, wait_for  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402

try:
    import agent_city_relay as rl  # noqa: E402
except ImportError:
    rl = None


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class Case(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(rl, "bin/agent_city_relay.py is missing or does not import")
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_send_"))
        self.fake = FakeRelay()
        self.repo = make_repo(self.base)
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    p.kill()
            for fh in (p.stdout, p.stderr):
                if fh:
                    fh.close()
        self.fake.stop()
        shutil.rmtree(self.base, ignore_errors=True)


class TestParseEnv(Case):
    def test_good(self):
        self.assertEqual(rl.parse_env("https://r.example.workers.dev k-1"),
                         {"address": "https://r.example.workers.dev", "key": "k-1"})
        self.assertEqual(rl.parse_env("  http://127.0.0.1:8787   k-2 \n"),
                         {"address": "http://127.0.0.1:8787", "key": "k-2"})

    def test_bad(self):
        for value in (None, "", "https://r.example", "k-only", "https://r.example a b",
                      "http://relay.example.com k", "ftp://x k"):
            with self.subTest(value=value):
                self.assertIsNone(rl.parse_env(value))


class TestEnvHub(Case):
    def hub(self, **kw):
        opts = dict(relay_sec=0, dev_id="dev-cloud", label="云端", join_ttl=0, timeout=3.0,
                    env_join={"address": self.fake.url, "key": FAKE_KEY})
        opts.update(kw)
        return rl.RelayHub(**opts)

    def test_no_join_file_needed(self):
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".secrets")))
        hub = self.hub()
        self.assertTrue(hub.offer(hook_line(self.repo, sid="c1")))
        hub.tick()
        sent = self.fake.sent_lines()
        self.assertEqual([(l["sid"], l["rid"], l["dev"], l["br"]) for l in sent],
                         [("c1", "github.com/acme/shop", "云端", "main")])
        self.assertEqual(self.fake.requests[0]["auth"], "Bearer " + FAKE_KEY)

    def test_worktree_branch(self):
        wt = add_worktree(self.repo, "feature/cloud")
        hub = self.hub()
        hub.offer(hook_line(self.repo, proj=wt))
        hub.tick()
        self.assertEqual(self.fake.sent_lines()[0]["br"], "feature/cloud")

    def test_no_origin_still_local(self):
        local = make_repo(self.base, "notes", origin=None)
        hub = self.hub()
        self.assertFalse(hub.offer(hook_line(local)))
        hub.tick()
        self.assertEqual(self.fake.sent_lines(), [])

    def test_send_only_shows_no_one_but_after_moves(self):
        hub = self.hub(send_only=True)
        hub.offer(hook_line(self.repo))
        self.fake.push("dev-other", {"ev": "Stop"})
        self.assertEqual(hub.tick(), [])
        self.assertEqual(hub.tick(), [])
        self.assertEqual(self.fake.sync_bodies()[1]["after"], self.fake.seq)
        self.assertEqual(len(self.fake.sent_lines()), 1)

    def test_status(self):
        hub = self.hub()
        hub.offer(hook_line(self.repo))
        hub.tick()
        st = hub.status()
        self.assertTrue(st["joined"])
        self.assertEqual(st["teams"][0]["host"], self.fake.host)
        self.assertNotIn(FAKE_KEY, json.dumps(st))


class SenderCase(Case):
    def setUp(self):
        super().setUp()
        self.dir = os.path.join(self.base, "city")
        os.makedirs(self.dir)

    def env(self, value=None, **extra):
        env = dict(os.environ, HOME=os.path.join(self.base, "home"),
                   AGENT_CITY_DIR=self.dir, CLAUDE_CODE_REMOTE="true",
                   PYTHONDONTWRITEBYTECODE="1")
        env.pop("AGENT_CITY_RELAY", None)
        if value is not None:
            env["AGENT_CITY_RELAY"] = value
        env.update(extra)
        return env

    def good(self):
        return "%s %s" % (self.fake.url, FAKE_KEY)

    def sender(self, value, *args):
        cmd = [sys.executable, CLIENT, "send", "--dir", self.dir] + list(args or
                                                                         ["--relay-sec", "0.2"])
        proc = subprocess.Popen(cmd, env=self.env(value), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        self.procs.append(proc)
        return proc

    def on(self):
        try:
            with open(os.path.join(self.dir, "on")) as fh:
                pid, port = fh.read().split()
            return int(pid), int(port)
        except (OSError, ValueError):
            return None

    def append(self, line):
        with open(os.path.join(self.dir, "events.jsonl"), "a") as fh:
            fh.write(json.dumps(line) + "\n")


class TestSenderCli(SenderCase):
    def test_not_set(self):
        proc = subprocess.run([sys.executable, CLIENT, "send", "--dir", self.dir],
                              env=self.env(None), capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("AGENT_CITY_RELAY is not set", proc.stdout + proc.stderr)
        self.assertIsNone(self.on())

    def test_malformed_never_printed(self):
        for value in ("%s" % self.fake.url, "http://relay.example.com secret-xyz",
                      "%s a secret-xyz" % self.fake.url):
            with self.subTest(value=value):
                proc = subprocess.run([sys.executable, CLIENT, "send", "--dir", self.dir],
                                      env=self.env(value), capture_output=True, text=True,
                                      timeout=30)
                self.assertEqual(proc.returncode, 2)
                self.assertNotIn("secret-xyz", proc.stdout + proc.stderr)
                self.assertIsNone(self.on())
        self.assertEqual(self.fake.requests, [])

    def test_writes_the_switch_and_sends_new_lines(self):
        self.append(hook_line(self.repo, sid="before-start"))
        proc = self.sender(self.good())
        self.assertTrue(wait_for(lambda: self.on() == (proc.pid, 0)), "DIR/on was not written")
        self.append(hook_line(self.repo, sid="c1", q="private"))
        self.assertTrue(wait_for(lambda: self.fake.sent_lines()), "nothing reached the relay")
        sent = self.fake.sent_lines()
        self.assertEqual([l["sid"] for l in sent], ["c1"], "only lines written after the start")
        self.assertEqual(sent[0]["dev"], "云端")
        self.assertNotIn(self.base, json.dumps(self.fake.sync_bodies()))
        self.assertNotIn("private", json.dumps(self.fake.sync_bodies()))

    def test_key_never_printed(self):
        proc = self.sender(self.good())
        self.assertTrue(wait_for(lambda: self.on()))
        self.append(hook_line(self.repo))
        self.assertTrue(wait_for(lambda: self.fake.sent_lines()))
        proc.terminate()
        out, err = proc.communicate(timeout=10)
        self.assertNotIn(FAKE_KEY, out + err)
        with open(os.path.join(self.dir, "events.jsonl")) as fh:
            self.assertNotIn(FAKE_KEY, fh.read())

    def test_stops_after_idle_and_removes_the_switch(self):
        proc = self.sender(self.good(), "--relay-sec", "0.2", "--idle-sec", "1.5")
        self.assertTrue(wait_for(lambda: self.on()))
        end = time.monotonic() + 3.0
        while time.monotonic() < end:
            self.append(hook_line(self.repo))
            time.sleep(0.3)
        self.assertIsNone(proc.poll(), "stopped while lines kept coming")
        self.assertTrue(wait_for(lambda: proc.poll() is not None, timeout=6),
                        "did not stop after idle-sec with no new line")
        self.assertIsNone(self.on(), "DIR/on left behind")

    def test_sigterm_removes_the_switch(self):
        proc = self.sender(self.good())
        self.assertTrue(wait_for(lambda: self.on()))
        proc.send_signal(signal.SIGTERM)
        proc.wait(10)
        self.assertIsNone(self.on())

    def test_one_sender_only(self):
        first = self.sender(self.good())
        self.assertTrue(wait_for(lambda: self.on() == (first.pid, 0)))
        second = subprocess.run([sys.executable, CLIENT, "send", "--dir", self.dir],
                                env=self.env(self.good()), capture_output=True, text=True,
                                timeout=30)
        self.assertEqual(second.returncode, 0)
        self.assertIn("already running", second.stdout + second.stderr)
        self.assertEqual(self.on(), (first.pid, 0))

    def test_relay_down_keeps_running(self):
        self.fake.stop()
        proc = self.sender(self.good())
        self.assertTrue(wait_for(lambda: self.on()))
        self.append(hook_line(self.repo))
        time.sleep(1.0)
        self.assertIsNone(proc.poll(), "a dead relay must not stop the sender")

    def test_real_hook_end_to_end(self):
        proc = self.sender(self.good())
        self.assertTrue(wait_for(lambda: self.on() == (proc.pid, 0)))
        event = {"session_id": "cloud-s1", "hook_event_name": "PostToolUse", "cwd": self.repo,
                 "tool_name": "Bash", "tool_input": {"command": "ls"}}
        hook = subprocess.run(["bash", HOOK], input=json.dumps(event), env=self.env(self.good()),
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(hook.returncode, 0, hook.stderr)
        self.assertTrue(wait_for(lambda: self.fake.sent_lines()), "the hook's line never arrived")
        wire = self.fake.sent_lines()[0]
        self.assertEqual((wire["sid"], wire["ev"], wire["rid"], wire["br"], wire["dev"]),
                         ("cloud-s1", "PostToolUse", "github.com/acme/shop", "main", "云端"))


class TestCitySend(ScriptCase):
    """./agent-city.sh send, as the packed cloud SessionStart hook runs it."""

    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.fake = FakeRelay()
        self.addCleanup(self.fake.stop)
        self.city = os.path.join(self.repo.base, "city")
        subprocess.run(["git", "-C", self.repo.dir, "remote", "add", "origin",
                        "git@github.com:Acme/Shop.git"], check=True, capture_output=True)

    def tearDown(self):
        on = os.path.join(self.city, "on")
        if os.path.exists(on):
            try:
                with open(on) as fh:
                    os.kill(int(fh.read().split()[0]), signal.SIGTERM)
            except (OSError, ValueError, IndexError):
                pass
        super().tearDown()

    def city_send(self, value, extra=None):
        env = {"AGENT_CITY_DIR": self.city,
               "AGENT_CITY_HOME": os.path.join(self.repo.base, "cityhome"),
               "CLAUDE_CODE_REMOTE": "true"}
        if value is not None:
            env["AGENT_CITY_RELAY"] = value
        env.update(extra or {})
        result = self.repo.run("agent-city.sh", "send", env=env, timeout=30)
        return result

    def pid(self):
        with open(os.path.join(self.city, "on")) as fh:
            return int(fh.read().split()[0])

    def test_starts_the_sender(self):
        result = self.city_send("%s %s" % (self.fake.url, FAKE_KEY))
        self.assertOk(result)
        self.assertIn("CITY: sending to the team relay " + self.fake.host, result.stdout)
        self.assertNotIn(FAKE_KEY, result.stdout + result.stderr)
        pid = self.pid()
        self.assertTrue(pid_alive(pid))
        args = subprocess.run(["ps", "-o", "args=", "-p", str(pid)],
                              capture_output=True, text=True).stdout
        self.assertIn("agent_city_relay.py send", args)
        self.assertIn("--relay-sec 5", args)
        self.assertNotIn(FAKE_KEY, args, "the key must never be in argv")

    def test_twice_starts_one(self):
        value = "%s %s" % (self.fake.url, FAKE_KEY)
        self.assertOk(self.city_send(value))
        first = self.pid()
        again = self.city_send(value)
        self.assertOk(again)
        self.assertIn("CITY: sending to the team relay", again.stdout)
        self.assertEqual(self.pid(), first)

    def test_not_set(self):
        result = self.city_send(None)
        self.assertEqual(result.returncode, 1)
        self.assertIn("AGENT_CITY_RELAY is not set", result.stdout + result.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.city, "on")))

    def test_over_cap_starts_nothing(self):
        result = self.city_send("%s %s" % (self.fake.url, FAKE_KEY), {"AGENT_FAKE_RAM": "95"})
        self.assertEqual(result.returncode, 1)
        self.assertFalse(os.path.exists(os.path.join(self.city, "on")))

    def test_usage_lists_send(self):
        result = self.repo.run("agent-city.sh", "-h")
        self.assertIn("send", result.stdout)


if __name__ == "__main__":
    unittest.main()
