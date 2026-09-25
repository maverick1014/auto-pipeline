"""Failing tests: the local city server talks to the team relay
(requirements/city.md, "Joining").

bin/agent_city.py serve gains one flag and one route, and uses
bin/agent_city_relay.py (tests/test_agent_city_relay_client.py) for the rest:

  --relay-sec S   seconds between syncs with a team relay (a float; default 5;
                  bin/agent-city.sh passes city_relay_sec from agent.conf).

  Every line read from events.jsonl is also offered to one RelayHub. A line
  from a joined repo is sent to its team; lines from other repos never
  leave the machine. The hub syncs on its own thread: a slow or dead relay
  never holds up the local city.

  Lines from other members come back as SSE events, as they are:
      {"type": "remote", "dev": "<their device id>", "line": {...wire line...}}
  They never go through the local Reducer and never into world.json: other
  members are shown live only.

  A team's state is sent to the page when it changes (not on every sync):
      {"type": "relay", "host": "<relay host[:port]>", "state": "ok" | "off" | "refused"}
  "off" is what the page shows as 联城断开.

  GET /relay -> 200, the hub's status(): {"joined": bool, "teams": [...]}.
      Never the key.

  Idle: not joined, nothing changes (the server stops after the idle time
  with no browser open, events or not). Joined (the hub has a team): every
  new line also restarts the idle clock, so a joined machine keeps sending
  while its agents work, and stops after the idle time with no browser and
  no new lines.

Every test uses a fake relay on 127.0.0.1 (tests/relayhelp.py), a temp city
dir and a temp AGENT_CITY_HOME. Never the real ~/.claude/agent-city, never a
real key.

Run: python3 -m unittest tests.test_agent_city_relay_serve
"""

import json
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from relayhelp import FAKE_KEY, FakeRelay, hook_line, join, make_repo  # noqa: E402
from test_agent_city_server import ServerCase, pid_alive, wait_for  # noqa: E402


class RelayServerCase(ServerCase):
    def setUp(self):
        super().setUp()
        self.fake = FakeRelay()
        self.repo = make_repo(self.base)

    def tearDown(self):
        self.fake.stop()
        super().tearDown()

    def start_relay(self, idle="60", relay_sec="0.2"):
        return self.start("--idle-sec", idle, "--relay-sec", relay_sec)

    def add(self, **fields):
        self.append(json.dumps(hook_line(self.repo, **fields)) + "\n")

    def relay_status(self):
        status, _, body = self.get("/relay")
        self.assertEqual(status, 200)
        return json.loads(body)


class TestNotJoined(RelayServerCase):
    def test_nothing_leaves_the_machine(self):
        self.start_relay()
        self.add(sid="s1")
        self.assertTrue(wait_for(lambda: self.health()["lines"] == 1))
        time.sleep(1.0)
        self.assertEqual(self.fake.requests, [])
        self.assertEqual(self.relay_status(), {"joined": False, "teams": []})

    def test_still_stops_on_idle_even_with_events(self):
        proc = self.start_relay(idle="1.0")
        end = time.monotonic() + 3.0
        while time.monotonic() < end and proc.poll() is None:
            self.add(sid="s1")
            time.sleep(0.3)
        self.assertTrue(wait_for(lambda: proc.poll() is not None, timeout=5),
                        "a city that is not joined stops with no browser, events or not")


class TestJoined(RelayServerCase):
    def setUp(self):
        super().setUp()
        join(self.repo, self.fake.url)

    def test_line_goes_to_the_relay(self):
        self.start_relay()
        self.add(sid="s1", desc="fix %s/api/x.py" % self.repo, q="a private question")
        self.assertTrue(wait_for(lambda: self.fake.sent_lines()), "nothing reached the relay")
        wire = self.fake.sent_lines()[0]
        self.assertEqual(wire["sid"], "s1")
        self.assertEqual(wire["rid"], "github.com/acme/shop")
        self.assertEqual(wire["desc"], "fix x.py")
        body = json.dumps(self.fake.sync_bodies())
        self.assertNotIn(self.base, body)
        self.assertNotIn("a private question", body)
        self.assertEqual(self.fake.requests[0]["auth"], "Bearer " + FAKE_KEY)

    def test_local_city_still_gets_the_line(self):
        self.start_relay()
        self.add(sid="s1")
        self.assertTrue(wait_for(lambda: self.health()["lines"] == 1))

    def test_remote_lines_reach_the_page(self):
        self.start_relay()
        client = self.sse()
        self.add(sid="mine")
        self.assertTrue(wait_for(lambda: self.fake.sent_lines()))
        theirs = {"ev": "PreToolUse", "sid": "t1", "tool": "Edit", "rid": "github.com/acme/shop",
                  "who": "Bo", "dev": "bo-laptop"}
        self.fake.push("dev-bo", theirs)
        self.assertTrue(wait_for(lambda: client.events("remote")), "no remote event on the page")
        self.assertEqual(client.events("remote")[0],
                         {"type": "remote", "dev": "dev-bo", "line": theirs})

    def test_remote_lines_stay_out_of_the_local_city(self):
        proc = self.start_relay()
        client = self.sse()
        self.add(sid="mine")
        self.assertTrue(wait_for(lambda: self.health()["lines"] == 1))
        agents_before = self.health()["agents"]
        for i in range(3):
            self.fake.push("dev-bo", {"ev": "SessionStart", "sid": "bo%d" % i, "who": "Bo",
                                      "rid": "github.com/acme/shop"})
        self.assertTrue(wait_for(lambda: len(client.events("remote")) == 3))
        self.assertEqual(self.health()["agents"], agents_before)
        self.assertEqual(self.health()["lines"], 1)
        proc.terminate()
        proc.wait(5)
        world = os.path.join(self.base, "cityhome", "world.json")
        if os.path.exists(world):
            with open(world) as fh:
                text = fh.read()
            self.assertNotIn("Bo", text)
            self.assertNotIn("bo0", text)

    def test_relay_state_events_on_change_only(self):
        self.start_relay()
        client = self.sse()
        self.add(sid="s1")
        ok = {"type": "relay", "host": self.fake.host, "state": "ok"}
        self.assertTrue(wait_for(lambda: ok in client.events("relay")))
        time.sleep(1.0)  # about five more syncs
        self.assertEqual(client.events("relay").count(ok), 1, "state is sent when it changes")
        self.fake.stop()
        off = {"type": "relay", "host": self.fake.host, "state": "off"}
        self.assertTrue(wait_for(lambda: off in client.events("relay")), "no 联城断开 event")

    def test_refused_state(self):
        self.fake.mode = "refuse"
        self.start_relay()
        client = self.sse()
        self.add(sid="s1")
        want = {"type": "relay", "host": self.fake.host, "state": "refused"}
        self.assertTrue(wait_for(lambda: want in client.events("relay")))

    def test_relay_route(self):
        self.start_relay()
        self.add(sid="s1")
        self.assertTrue(wait_for(lambda: self.fake.sent_lines()))
        self.assertTrue(wait_for(lambda: self.relay_status()["teams"][0]["state"] == "ok"))
        st = self.relay_status()
        self.assertTrue(st["joined"])
        self.assertEqual(st["teams"][0]["host"], self.fake.host)
        self.assertEqual(st["teams"][0]["rids"], ["github.com/acme/shop"])
        status, _, body = self.get("/relay")
        self.assertNotIn(FAKE_KEY.encode(), body)

    def test_slow_relay_never_holds_up_the_local_city(self):
        self.fake.delay = 4.0
        self.start_relay()
        client = self.sse()
        self.add(sid="first")
        self.assertTrue(wait_for(lambda: self.fake.requests, timeout=5))
        self.add(sid="second", ev="SessionStart")
        self.assertTrue(wait_for(lambda: self.health()["lines"] == 2, timeout=1.5),
                        "the tail loop waited for the relay")
        self.assertTrue(client.messages)

    def test_relay_down_keeps_the_local_city_working(self):
        self.fake.stop()
        self.start_relay()
        self.add(sid="s1", ev="SessionStart")
        self.assertTrue(wait_for(lambda: self.health()["lines"] == 1))
        self.assertTrue(wait_for(lambda: self.relay_status()["teams"]
                                 and self.relay_status()["teams"][0]["state"] == "off"))

    def test_joined_stays_up_while_agents_work_then_stops(self):
        proc = self.start_relay(idle="1.5")
        end = time.monotonic() + 4.0
        while time.monotonic() < end:
            self.add(sid="s1")
            time.sleep(0.3)
        self.assertIsNone(proc.poll(), "a joined city stopped while its agents were working")
        self.assertTrue(wait_for(lambda: proc.poll() is not None, timeout=6),
                        "a joined city with no browser and no new lines must still stop")
        self.assertFalse(pid_alive(proc.pid))


class TestRelaySecFlag(RelayServerCase):
    def test_default_is_five_seconds(self):
        join(self.repo, self.fake.url)
        self.start("--idle-sec", "60")
        self.add(sid="s1")
        self.assertTrue(wait_for(lambda: self.fake.requests, timeout=8))
        time.sleep(2.0)
        self.add(sid="s2")
        time.sleep(1.0)
        self.assertEqual(len(self.fake.requests), 1, "second sync came sooner than 5 s")


if __name__ == "__main__":
    unittest.main()
