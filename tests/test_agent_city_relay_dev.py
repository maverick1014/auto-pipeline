"""Failing tests: the dev relay for the two-machine LAN test (city-join-page,
step 2). The owner wants a real two-machine test before any Cloudflare
account: one machine runs the relay on the local network, both machines
join it, each city page shows the other machine's agents.

bin/agent-city-relay-dev.mjs   (Node 22.5+, uses node:sqlite)
    node agent-city-relay-dev.mjs [--host H] [--port P]
    Runs bin/agent-city-relay.js, the very file the owner pastes into
    Cloudflare, behind a plain HTTP server, with an in-memory stand-in for
    D1 (node:sqlite) bound as DB and the key as TEAM_KEY. Default host
    0.0.0.0 (the LAN), default port 8787.
    The team key is the first line of stdin: never argv, never printed.
    stdout, first two lines:
        RELAY-DEV: listening on <host>:<port>
        RELAY-DEV: join with http://<this machine's LAN IPv4, or 127.0.0.1>:<port>
    Empty key -> exit 2, "RELAY-DEV: no key on stdin".
    Stops on SIGINT / SIGTERM.

bin/agent-city.sh relay-dev [port]
    Run by the person in their own terminal. Needs node with node:sqlite
    (else "RELAY-DEV: needs Node 22.5 or newer", exit 1). Asks for the team
    key with echo off (read -rs, prompt on stderr); empty -> a short reason,
    exit 1. Hands the key to the .mjs on stdin (printf, never argv) and runs
    it in the foreground until Ctrl-C. Never prints the key.

A LAN address is accepted by join: see check_address in
tests/test_agent_city_relay_client.py (http:// for private LAN IPv4).

Run: python3 -m unittest tests.test_agent_city_relay_dev
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
DEV = os.path.join(BIN, "agent-city-relay-dev.mjs")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

from relayhelp import FAKE_KEY, hook_line, join, make_repo  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402

try:
    import agent_city_relay as rl  # noqa: E402
except ImportError:
    rl = None

NODE = shutil.which("node")


def node_has_sqlite():
    if not NODE:
        return False
    r = subprocess.run([NODE, "-e", "require('node:sqlite')"], capture_output=True)
    return r.returncode == 0


@unittest.skipUnless(node_has_sqlite(), "node with node:sqlite is not installed")
class TestDevRelay(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.isfile(DEV), "bin/agent-city-relay-dev.mjs is missing")
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    p.kill()
            for fh in (p.stdin, p.stdout, p.stderr):
                if fh:
                    fh.close()

    def start(self, *args, key=FAKE_KEY):
        proc = subprocess.Popen([NODE, DEV] + list(args), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(proc)
        proc.stdin.write(key + "\n")
        proc.stdin.flush()
        first = proc.stdout.readline().strip()
        second = proc.stdout.readline().strip()
        return proc, first, second

    def local(self):
        proc, first, second = self.start("--host", "127.0.0.1", "--port", "0")
        self.assertRegex(first, r"^RELAY-DEV: listening on 127\.0\.0\.1:\d+$")
        port = first.rsplit(":", 1)[1]
        self.assertRegex(second, r"^RELAY-DEV: join with http://[\d.]+:%s$" % port)
        return proc, "http://127.0.0.1:" + port

    def test_it_is_the_real_worker(self):
        _, url = self.local()
        with urllib.request.urlopen(url + "/", timeout=5) as resp:
            self.assertEqual(json.loads(resp.read()), {"ok": True, "relay": "agent-city", "v": 1})
        self.assertEqual(rl.sync(url, "wrong", "a", 0, [])[0], "refused")
        self.assertEqual(rl.sync(url, FAKE_KEY, "a", 0, [{"ev": "Stop"}])[0], "ok")
        state, data = rl.sync(url, FAKE_KEY, "b", 0, [])
        self.assertEqual((state, [x["line"] for x in data["lines"]]), ("ok", [{"ev": "Stop"}]))

    def test_two_machines_through_it(self):
        _, url = self.local()
        base = os.path.realpath(tempfile.mkdtemp(prefix="relay_dev_"))
        self.addCleanup(shutil.rmtree, base, True)
        repo_a = make_repo(base, "a_shop", user="Maverick")
        repo_b = make_repo(base, "b_shop", user="Ann")
        join(repo_a, url)
        join(repo_b, url)
        a = rl.RelayHub(relay_sec=0, dev_id="dev-a", label="mac-mini", join_ttl=0)
        b = rl.RelayHub(relay_sec=0, dev_id="dev-b", label="ann-laptop", join_ttl=0)
        a.offer(hook_line(repo_a, sid="a1"))
        a.tick()
        b.offer(hook_line(repo_b, sid="b1"))
        got_b = b.tick()
        got_a = a.tick()
        self.assertEqual([(g["line"]["sid"], g["line"]["who"], g["line"]["dev"]) for g in got_b],
                         [("a1", "Maverick", "mac-mini")])
        self.assertEqual([(g["line"]["sid"], g["line"]["who"], g["line"]["dev"]) for g in got_a],
                         [("b1", "Ann", "ann-laptop")])

    def test_default_is_the_lan(self):
        _, first, second = self.start("--port", "0")
        self.assertRegex(first, r"^RELAY-DEV: listening on 0\.0\.0\.0:\d+$")
        self.assertTrue(second.startswith("RELAY-DEV: join with http://"))

    def test_key_never_printed(self):
        proc, _ = self.local()
        proc.terminate()
        out, err = proc.communicate(timeout=10)
        self.assertNotIn(FAKE_KEY, out + err)

    def test_no_key(self):
        proc = subprocess.run([NODE, DEV, "--port", "0"], input="\n", capture_output=True,
                              text=True, timeout=30)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("RELAY-DEV: no key on stdin", proc.stdout + proc.stderr)


@unittest.skipUnless(node_has_sqlite(), "node with node:sqlite is not installed")
class TestCityRelayDev(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    p.kill()
            for fh in (p.stdin, p.stdout, p.stderr):
                if fh:
                    fh.close()
        super().tearDown()

    def popen(self, *args):
        env = self.repo._env({"AGENT_CITY_DIR": os.path.join(self.repo.base, "city"),
                              "AGENT_CITY_HOME": os.path.join(self.repo.base, "cityhome")})
        proc = subprocess.Popen([self.repo.script_path("agent-city.sh")] + list(args),
                                cwd=self.repo.dir, env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(proc)
        return proc

    def test_runs_the_dev_relay(self):
        proc = self.popen("relay-dev", "0")
        proc.stdin.write(FAKE_KEY + "\n")
        proc.stdin.flush()
        first = proc.stdout.readline().strip()
        self.assertRegex(first, r"^RELAY-DEV: listening on 0\.0\.0\.0:\d+$")
        second = proc.stdout.readline().strip()
        self.assertTrue(second.startswith("RELAY-DEV: join with http://"))
        port = first.rsplit(":", 1)[1]
        self.assertEqual(rl.sync("http://127.0.0.1:" + port, FAKE_KEY, "a", 0, [])[0], "ok")
        args = subprocess.run(["ps", "-Ao", "args="], capture_output=True, text=True).stdout
        self.assertNotIn(FAKE_KEY, args, "the key must never be in argv")
        proc.send_signal(signal.SIGINT)
        out, err = proc.communicate(timeout=10)
        self.assertNotIn(FAKE_KEY, first + second + out + err)

    def test_empty_key(self):
        proc = self.popen("relay-dev", "0")
        out, err = proc.communicate("\n", timeout=30)
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("listening", out)

    def test_needs_node(self):
        self.repo.hide_tool("node")
        result = self.repo.run("agent-city.sh", "relay-dev", "0", stdin=FAKE_KEY + "\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RELAY-DEV: needs Node 22.5 or newer", result.stdout + result.stderr)

    def test_usage_lists_relay_dev(self):
        self.assertIn("relay-dev", self.repo.run("agent-city.sh", "-h").stdout)


if __name__ == "__main__":
    unittest.main()
