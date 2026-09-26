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

  Other members on the page (city-join-page, approved mock
  mock/city-join-mock.html). Their wire lines come back from the relay and
  go through the SAME rules as local lines: one Reducer per sender device
  (the "dev" of the sync item), fed the wire line with "proj" set to the
  last part of its "rid" (the wire line has no folder). Each event the
  Reducer emits reaches the page wrapped:
      {"type": "remote", "dev": "<sender device id>",
       "who": "<line who; the line dev when who is blank>",
       "device": "<line dev: machine name or 云端>", "rid": "<line rid>",
       "br": "<line br>", "ev": <the Reducer event>}
    - every "id" in ev becomes "r:<dev>:<id>", so it never meets a local id
    - spawn gets "terr": the LOCAL territory of that rid (the joined local
      repo with that origin; RelayHub.repo_for(rid)). A rid with no local
      repo -> the line is dropped.
    - gov gets "id": "r:<dev>:gov", "terr" as above and "present" (false on
      SessionEnd), like the local gov event
    - never a build, never into world.json, never in /health "agents"
  A new page gets, right after its snapshot and only while the hub has a
  team:
      {"type": "remote_snapshot", "me": {"who", "device"},
       "people": [ {Reducer snapshot agent + "id" prefixed, "terr", "who",
                    "device", "rid", "br", "dev"} ],
       "govs":   [ {"id", "state", "terr", "who", "device", "dev"} ],
       "teams":  [ {"host", "state", "queued"} ]}
    me: RelayHub.identity() -> {"who": git user.name of a joined repo,
    "device": the hub's label}.
  A sender device silent for --remote-ttl-sec (default 600): its people get
  "leave" and its gov "present": false (wrapped as above), then it is
  forgotten.

  A team's state goes to the page when it changes, and while it is "off" also
  when its queued count changes (at most once a second). Its type is "team":
  "relay" is taken by city-people (a question passed up the chain).
      {"type": "team", "host": "<relay host[:port]>",
       "state": "ok" | "off" | "refused" | "left", "queued": <int>}
  "off" is what the page shows as 联城断开. "left": the team was dropped
  (leave, or a new key); every person and gov of that team's devices then
  gets "leave" / "present": false.

  --join-ttl-sec S  how often the hub re-reads join files (RelayHub
                    join_ttl; default 30). Tests use a small value.

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

BIN = os.path.join(os.path.dirname(HERE), "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)
import agent_city as ac  # noqa: E402


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

    def wire(self, **kw):
        line = {"ev": "SessionStart", "sid": "t1", "aid": "", "at": "", "tool": "", "nt": "",
                "role": "worker", "desc": "", "sub": "", "klen": "", "kind": "",
                "rid": "github.com/acme/shop", "br": "feat/pay", "who": "Bo", "dev": "bo-laptop"}
        line.update(kw)
        return line

    def terr(self):
        return ac.territory_id(os.path.realpath(os.path.join(self.repo, ".git")))

    def started(self, *extra):
        self.start("--idle-sec", "60", "--relay-sec", "0.2", "--join-ttl-sec", "0.2", *extra)
        client = self.sse()
        self.add(sid="mine")
        self.assertTrue(wait_for(lambda: self.fake.sent_lines()), "nothing reached the relay")
        return client

    def test_remote_spawn_reaches_the_page(self):
        client = self.started()
        self.fake.push("dev-bo", self.wire())
        self.assertTrue(wait_for(lambda: client.events("remote")), "no remote event on the page")
        got = client.events("remote")[0]
        self.assertEqual({k: got[k] for k in ("dev", "who", "device", "rid", "br")},
                         {"dev": "dev-bo", "who": "Bo", "device": "bo-laptop",
                          "rid": "github.com/acme/shop", "br": "feat/pay"})
        ev = got["ev"]
        self.assertEqual(ev["type"], "spawn")
        self.assertEqual(ev["id"], "r:dev-bo:s:t1")
        self.assertEqual(ev["role"], "worker")
        self.assertEqual(ev["task"], "shop")
        self.assertEqual(ev["terr"], self.terr())

    def test_remote_tool_stuck_done_leave(self):
        client = self.started()
        for kw in ({}, {"ev": "PostToolUse", "tool": "Edit"},
                   {"ev": "Notification", "nt": "permission_prompt"},
                   {"ev": "Stop"}, {"ev": "SessionEnd"}):
            self.fake.push("dev-bo", self.wire(**kw))
        self.assertTrue(wait_for(lambda: any(e["ev"]["type"] == "leave"
                                             for e in client.events("remote"))))
        kinds = [e["ev"]["type"] for e in client.events("remote")]
        for k in ("spawn", "tool", "stuck", "leave"):
            self.assertIn(k, kinds)
        self.assertTrue(all(e["ev"]["id"] == "r:dev-bo:s:t1" for e in client.events("remote")))

    def test_blank_who_is_the_device(self):
        client = self.started()
        self.fake.push("dev-pc2", self.wire(who="", dev="pc2"))
        self.assertTrue(wait_for(lambda: client.events("remote")))
        self.assertEqual(client.events("remote")[0]["who"], "pc2")

    def test_remote_governor(self):
        client = self.started()
        self.fake.push("dev-ann", self.wire(role="", sid="g1", ev="UserPromptSubmit",
                                            who="Ann", dev="ann-laptop"))
        self.assertTrue(wait_for(lambda: client.events("remote")))
        got = client.events("remote")[0]
        self.assertEqual(got["who"], "Ann")
        self.assertEqual(got["ev"], {"type": "gov", "id": "r:dev-ann:gov", "state": "busy",
                                     "terr": self.terr(), "present": True})

    def test_two_devices_never_share_ids(self):
        client = self.started()
        self.fake.push("dev-a", self.wire(who="Ann", dev="ann-laptop"))
        self.fake.push("dev-b", self.wire(who="Bo", dev="bo-laptop"))
        self.assertTrue(wait_for(lambda: len(client.events("remote")) == 2))
        self.assertEqual(sorted(e["ev"]["id"] for e in client.events("remote")),
                         ["r:dev-a:s:t1", "r:dev-b:s:t1"])

    def test_unknown_repo_is_dropped(self):
        client = self.started()
        self.fake.push("dev-bo", self.wire(rid="github.com/other/thing"))
        self.fake.push("dev-bo", self.wire(sid="t2"))
        self.assertTrue(wait_for(lambda: client.events("remote")))
        time.sleep(0.5)
        self.assertEqual([e["ev"]["id"] for e in client.events("remote")], ["r:dev-bo:s:t2"])

    def test_remote_stays_out_of_the_local_city(self):
        proc = self.start("--idle-sec", "60", "--relay-sec", "0.2")
        client = self.sse()
        self.add(sid="mine")
        self.assertTrue(wait_for(lambda: self.health()["lines"] == 1))
        agents_before = self.health()["agents"]
        for i in range(3):
            self.fake.push("dev-bo", self.wire(sid="bo%d" % i, ev="PostToolUse", tool="Write",
                                               kind="script"))
        self.assertTrue(wait_for(lambda: len(client.events("remote")) >= 3))
        self.assertEqual(self.health()["agents"], agents_before)
        self.assertEqual(self.health()["lines"], 1)
        self.assertEqual(client.events("build"), [])
        proc.terminate()
        proc.wait(5)
        world = os.path.join(self.base, "cityhome", "world.json")
        if os.path.exists(world):
            with open(world) as fh:
                text = fh.read()
            self.assertNotIn("Bo", text)
            self.assertNotIn("bo0", text)

    def test_remote_snapshot_for_a_new_page(self):
        self.started()
        self.fake.push("dev-bo", self.wire())
        self.fake.push("dev-cy", self.wire(role="", sid="g1", ev="UserPromptSubmit",
                                           who="Cy", dev="cy-laptop"))
        first = self.clients[0]
        self.assertTrue(wait_for(lambda: len(first.events("remote")) == 2))
        late = self.sse()
        self.assertTrue(wait_for(lambda: late.events("remote_snapshot")))
        snap = late.events("remote_snapshot")[0]
        # me.who: the local joined repo's git user.name (relayhelp.make_repo: "Ann")
        self.assertEqual(snap["me"]["who"], "Ann")
        self.assertTrue(snap["me"]["device"])
        self.assertEqual([(p["id"], p["who"], p["device"], p["terr"], p["dev"])
                          for p in snap["people"]],
                         [("r:dev-bo:s:t1", "Bo", "bo-laptop", self.terr(), "dev-bo")])
        self.assertEqual([(g["id"], g["who"], g["state"], g["dev"]) for g in snap["govs"]],
                         [("r:dev-cy:gov", "Cy", "busy", "dev-cy")])
        self.assertEqual([(r["host"], r["state"]) for r in snap["teams"]], [(self.fake.host, "ok")])
        kinds = [m.get("type") for m in late.messages]
        self.assertLess(kinds.index("snapshot"), kinds.index("remote_snapshot"))

    def test_no_remote_snapshot_when_not_joined(self):
        os.remove(os.path.join(self.repo, ".secrets", "agent-city-relay"))
        self.start("--idle-sec", "60", "--relay-sec", "0.2")
        client = self.sse()
        time.sleep(0.8)
        self.assertEqual(client.events("remote_snapshot"), [])

    def test_silent_device_is_forgotten(self):
        client = self.started("--remote-ttl-sec", "1.5")
        self.fake.push("dev-bo", self.wire())
        self.fake.push("dev-ann", self.wire(role="", sid="g1", ev="UserPromptSubmit",
                                            who="Ann", dev="ann-laptop"))
        self.assertTrue(wait_for(lambda: len(client.events("remote")) == 2))
        gone = lambda: [e["ev"] for e in client.events("remote")
                        if e["ev"]["type"] == "leave" or e["ev"].get("present") is False]
        self.assertTrue(wait_for(lambda: len(gone()) == 2, timeout=8), "silent devices never left")
        self.assertIn({"type": "leave", "id": "r:dev-bo:s:t1"}, gone())

    def test_relay_state_events_on_change_only(self):
        client = self.started()
        ok = lambda: [e for e in client.events("team") if e["state"] == "ok"]
        self.assertTrue(wait_for(ok))
        self.assertEqual((ok()[0]["host"], ok()[0]["queued"]), (self.fake.host, 0))
        time.sleep(1.0)  # about five more syncs
        self.assertEqual(len(ok()), 1, "state is sent when it changes")
        self.fake.stop()
        off = lambda: [e for e in client.events("team") if e["state"] == "off"]
        self.assertTrue(wait_for(off), "no 联城断开 event")
        for i in range(3):
            self.add(sid="later%d" % i)
            time.sleep(0.4)
        self.assertTrue(wait_for(lambda: off()[-1]["queued"] >= 3, timeout=5),
                        "the 待发 count never reached the page")
        self.assertLessEqual(len(off()), 6, "queued updates at most once a second")

    def test_refused_state(self):
        self.fake.mode = "refuse"
        self.start("--idle-sec", "60", "--relay-sec", "0.2")
        client = self.sse()
        self.add(sid="s1")
        self.assertTrue(wait_for(lambda: any(e["state"] == "refused" and e["host"] == self.fake.host
                                             for e in client.events("team"))))

    def test_leave_removes_everyone_of_that_team(self):
        client = self.started()
        self.fake.push("dev-bo", self.wire())
        self.fake.push("dev-ann", self.wire(role="", sid="g1", ev="UserPromptSubmit",
                                            who="Ann", dev="ann-laptop"))
        self.assertTrue(wait_for(lambda: len(client.events("remote")) == 2))
        os.remove(os.path.join(self.repo, ".secrets", "agent-city-relay"))
        self.assertTrue(wait_for(lambda: any(e["state"] == "left" for e in client.events("team"))),
                        "no 'left' team event")
        evs = [e["ev"] for e in client.events("remote")]
        self.assertIn({"type": "leave", "id": "r:dev-bo:s:t1"}, evs)
        self.assertTrue(any(e.get("id") == "r:dev-ann:gov" and e.get("present") is False
                            for e in evs))

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
