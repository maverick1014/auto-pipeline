"""Failing tests, cloud-city-3: the two Workers together, an order down and
its state up (requirements/city.md, "Cloud page", "Start"). Needs slices W1
(bin/agent-city-relay.js) and W2 (bin/agent-city-cloud.js); each has its own
test file, this one checks that they fit.

    the page  POST /api/agent/add      ->  city_order 'sent'
    the machine's sync (talk + start)  ->  orders, 'taken'
    its next syncs: start.acks         ->  'opening', then 'opened'
    the page  GET /api/feed            ->  on its way, opening on the machine, opened

The dev runner (bin/agent-city-cloud-dev.mjs) needs no change: a POST to the
City Worker goes through whole, and --talk gives the relay its TALK_KEY.

No test talks to Cloudflare. Run: python3 -m unittest tests.test_agent_city_cloud_start_roundtrip
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from nodehelp import NODE, SKIP_REASON  # noqa: E402
import cloudhelp as ch  # noqa: E402
from cloudhelp import KEY, ME, T0, TALK, TALK_ENV, TERR, add, feed, send, snapshot, sql, sync, view  # noqa: E402

OID = "oid-roundtrip-000001"
OID2 = "oid-roundtrip-000002"
INFO = {"name": "shop Manager", "role": "main"}


def ssync(dev="mac", now=T0, start=None, **kw):
    return sync(dev, talk_key=TALK, now=now, talk={"start": {} if start is None else start}, **kw)


def tsync(dev="mac", now=T0, **kw):
    return sync(dev, talk_key=TALK, now=now, **kw)


def poll(now):
    return feed(dev="mac", gen=1, after=0, now=now)


def states(body):
    return [(o["oid"], o["state"], o["why"]) for o in body["orders"]]


@unittest.skipUnless(NODE, SKIP_REASON)
class TestRoundTrip(unittest.TestCase):
    def run_both(self, reqs):
        return ch.run_cloud(self, reqs, relay_env=TALK_ENV)

    def test_both_workers_make_the_same_table(self):
        for path in (ch.RELAY, ch.CITY):
            with open(path, encoding="utf-8") as fh:
                src = " ".join(fh.read().split())
            for line in ch.START_TABLES:
                self.assertIn(" ".join(line.split()), src, "%s: this exact line is missing: %s" % (os.path.basename(path), line[:60]))

    def test_down_and_up(self):
        up = view(1, snap=[snapshot()])
        reqs = [
            ssync(view=up, now=T0),                                                        # 0 the machine, talk + start on
            feed(now=T0 + 500),                                                            # 1
            add(oid=OID, now=T0 + 1000),                                                   # 2 the owner clicks
            poll(T0 + 2000),                                                               # 3 on its way
            add(oid=OID2, now=T0 + 2500),                                                  # 4 a double click (a new id)
            ssync(now=T0 + 5000),                                                          # 5 the machine asks
            add(oid=OID, now=T0 + 5500),                                                   # 6 the same request again
            poll(T0 + 6000),                                                               # 7 still on its way (taken)
            ssync(now=T0 + 6000, start={"acks": [{"oid": OID, "state": "opening", "info": INFO}]}),   # 8 the terminal opens
            poll(T0 + 7000),                                                               # 9 opening on the machine
            ssync(now=T0 + 20000, start={"acks": [{"oid": OID, "state": "opened", "info": INFO}]}),   # 10 its first line came
            poll(T0 + 21000),                                                              # 11 opened
            sql("SELECT COUNT(*) AS n FROM city_order"),                                   # 12
            add(oid=OID2, now=T0 + 22000),                                                 # 13 the repo is free again
        ]
        out = self.run_both(reqs)
        r = out["responses"]
        for i, x in enumerate(r):
            if i != 4:
                self.assertEqual(x["status"], 200, (i, x))
        self.assertEqual((r[1]["body"]["devs"][0]["talk"], r[1]["body"]["devs"][0]["start"]), (True, True))
        self.assertEqual(r[2]["body"], {"ok": True, "oid": OID, "state": "sent", "why": "", "info": {}})
        self.assertEqual(states(r[3]["body"]), [(OID, "sent", "")])
        self.assertEqual((r[4]["status"], r[4]["body"]), (409, {"ok": False, "error": "busy", "oid": OID}))
        self.assertEqual(r[5]["body"]["talk"]["start"], {"state": "on", "orders": [{"oid": OID, "terr": TERR, "force": False, "age": 4000}]})
        self.assertEqual(r[6]["body"]["state"], "taken", "a repeated request never moves it back to sent")
        self.assertEqual(states(r[7]["body"]), [(OID, "taken", "")])
        self.assertEqual(r[8]["body"]["talk"]["start"]["orders"], [], "answered: not handed down again")
        got = r[9]["body"]["orders"][0]
        self.assertEqual((got["state"], got["info"]), ("opening", INFO))
        got = r[11]["body"]["orders"][0]
        self.assertEqual((got["state"], got["info"], got["ts"]), ("opened", INFO, T0 + 20000))
        self.assertEqual(r[12]["body"][0]["n"], 1, "one order, however often it was clicked, sent and handed down")
        self.assertEqual(r[13]["body"]["state"], "sent")

    def test_the_machine_is_off_so_the_page_says_so_and_it_never_opens_later(self):
        reqs = [ssync(view=view(1, snap=[snapshot()])), add(oid=OID, now=T0 + 1000),
                poll(T0 + 61000), ssync(now=T0 + 400000), poll(T0 + 401000)]
        out = self.run_both(reqs)
        r = out["responses"]
        self.assertEqual(states(r[2]["body"]), [(OID, "failed", "off")])
        self.assertEqual(r[3]["body"]["talk"]["start"]["orders"], [], "back online later: it is not opened after all")
        self.assertEqual(states(r[4]["body"]), [(OID, "failed", "off")])

    def test_the_relay_expires_it_too_when_no_page_is_open(self):
        reqs = [ssync(view=view(1, snap=[snapshot()])), add(oid=OID, now=T0 + 1000), ssync(now=T0 + 400000),
                sql("SELECT state, why FROM city_order")]
        out = self.run_both(reqs)
        self.assertEqual(out["responses"][2]["body"]["talk"]["start"]["orders"], [])
        self.assertEqual(out["responses"][3]["body"], [{"state": "failed", "why": "off"}])

    def test_start_off_on_the_machine_shows_on_the_page(self):
        reqs = [ssync(view=view(1, snap=[snapshot()])), add(oid=OID, now=T0 + 1000),
                ssync(now=T0 + 2000, start={"off": True}), poll(T0 + 3000),
                tsync(view=view(1), now=T0 + 4000), feed(now=T0 + 5000),
                add(oid=OID2, now=T0 + 6000),
                send(text="still talking", cid="cid-roundtrip-000009", now=T0 + 7000)]
        out = self.run_both(reqs)
        r = out["responses"]
        self.assertEqual(states(r[3]["body"]), [(OID, "failed", "start-off")])
        dev = r[5]["body"]["devs"][0]
        self.assertEqual((dev["talk"], dev["start"]), (True, False), "talking stays on while starting is off")
        self.assertEqual((r[6]["body"]["state"], r[6]["body"]["why"]), ("failed", "start-off"))
        self.assertEqual(r[7]["body"]["state"], "sent", "a message still goes")

    def test_talk_on_is_not_start_on(self):
        reqs = [tsync(view=view(1, snap=[snapshot()])), add(oid=OID, now=T0 + 1000), tsync(now=T0 + 2000),
                sync("mac", now=T0 + 3000, talk_key=TALK, talk={"acks": [], "chat": []}), poll(T0 + 4000)]
        out = self.run_both(reqs)
        r = out["responses"]
        self.assertEqual((r[1]["body"]["state"], r[1]["body"]["why"]), ("failed", "start-off"))
        for i in (2, 3):
            self.assertNotIn("start", r[i]["body"]["talk"], "a talk sync without start never gets an order")
        self.assertEqual(states(r[4]["body"]), [(OID, "failed", "start-off")])

    def test_the_cap_and_the_owners_yes(self):
        cap = {"ram": 86, "cpu": 41, "max": 80}
        reqs = [ssync(view=view(1, snap=[snapshot()])), add(oid=OID, now=T0 + 1000), ssync(now=T0 + 2000),
                ssync(now=T0 + 3000, start={"acks": [{"oid": OID, "state": "cap", "info": cap}]}),
                poll(T0 + 4000),
                add(oid=OID2, force=True, now=T0 + 5000), ssync(now=T0 + 6000)]
        out = self.run_both(reqs)
        r = out["responses"]
        got = r[4]["body"]["orders"][0]
        self.assertEqual((got["state"], got["info"]), ("cap", cap))
        self.assertEqual(r[5]["body"]["state"], "sent", "cap is final: the yes is a second order")
        self.assertEqual(r[6]["body"]["talk"]["start"]["orders"], [{"oid": OID2, "terr": TERR, "force": True, "age": 1000}])

    def test_the_team_key_alone_places_takes_and_fakes_nothing(self):
        reqs = [ssync(view=view(1, snap=[snapshot()])), add(oid=OID, now=T0 + 1000),
                sync("mac", now=T0 + 2000, talk={"start": {"acks": [{"oid": OID, "state": "opened"}]}}),      # no talk key
                sync("mac", now=T0 + 3000, talk_key=KEY, talk={"start": {}}),                                 # the team key as one
                sync("evil", now=T0 + 3500, talk={"start": {}},
                     lines=[{"ev": "x", "rid": "github.com/o/r", "oid": "oid-forged-000000001", "terr": TERR,
                             "orders": [{"oid": "oid-forged-000000001", "terr": TERR, "force": True, "age": 0}]}]),
                poll(T0 + 4000), ssync(now=T0 + 5000), sql("SELECT oid FROM city_order")]
        out = self.run_both(reqs)
        r = out["responses"]
        for i in (2, 3, 4):
            self.assertNotIn("orders", repr(r[i]["body"].get("talk")), i)
        self.assertEqual(states(r[5]["body"]), [(OID, "sent", "")], "nobody took it, nobody answered for it")
        self.assertEqual([o["oid"] for o in r[6]["body"]["talk"]["start"]["orders"]], [OID])
        self.assertEqual(r[7]["body"], [{"oid": OID}], "a line of another member never becomes an order")

    def test_another_machine_cannot_take_or_answer_it(self):
        reqs = [ssync("mac", view=view(1, snap=[snapshot()])), ssync("pc2", view=view(1, snap=[snapshot()], label="pc2")),
                add(dev="mac", oid=OID, now=T0 + 1000),
                ssync("pc2", now=T0 + 2000, start={"acks": [{"oid": OID, "state": "opened"}]}),
                ssync("mac", now=T0 + 3000)]
        out = self.run_both(reqs)
        r = out["responses"]
        self.assertEqual(r[3]["body"]["talk"]["start"]["orders"], [])
        self.assertEqual([o["oid"] for o in r[4]["body"]["talk"]["start"]["orders"]], [OID])


DEV = os.path.join(ch.BIN, "agent-city-cloud-dev.mjs")


@unittest.skipUnless(NODE, SKIP_REASON)
class TestDevRunnerStarts(unittest.TestCase):
    """bin/agent-city-cloud-dev.mjs --talk, for the E2E on a laptop: an order goes down and its state comes up."""

    def setUp(self):
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(5)
                except Exception:
                    p.kill()
            for stream in (p.stdout, p.stderr, p.stdin):
                if stream:
                    stream.close()

    def start(self, *args, lines=(KEY, TALK)):
        import subprocess
        proc = subprocess.Popen([NODE, DEV, "--port", "0", "--user", ME] + list(args), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(proc)
        try:
            proc.stdin.write("".join(l + "\n" for l in lines))
            proc.stdin.flush()
            proc.stdin.close()
        except OSError:
            pass
        first = proc.stdout.readline()
        m = re.match(r"CLOUD-DEV: listening on 127\.0\.0\.1:(\d+)", first)
        return proc, (int(m.group(1)) if m else None), first

    def http(self, port, path, method="GET", body=None, headers=None):
        import http.client
        import json
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        data = json.dumps(body) if body is not None else None
        conn.request(method, path, body=data, headers=headers or {})
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(raw)
        except ValueError:
            return resp.status, raw

    def machine(self, port, start=None, with_view=False):
        body = {"dev": "mac", "after": 0, "lines": [], "talk": {"start": {} if start is None else start}}
        if with_view:
            body["view"] = view(1, snap=[snapshot()], label="MacBook-Pro")
        headers = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json", "X-City-Talk": TALK}
        return self.http(port, "/v1/sync", "POST", body, headers)

    def page_add(self, port, oid, origin=None, **more):
        headers = {"Content-Type": "application/json", "X-City-Page": "1",
                   "Origin": origin or "http://127.0.0.1:%d" % port}
        body = {"dev": "mac", "terr": TERR, "oid": oid}
        body.update(more)
        return self.http(port, "/api/agent/add", "POST", body, headers)

    def test_an_order_goes_down_and_its_state_comes_up(self):
        proc, port, first = self.start("--talk")
        self.assertTrue(port, "first line was: %r" % first)
        status, body = self.machine(port, with_view=True)
        self.assertEqual((status, body["talk"].get("start")), (200, {"state": "on", "orders": []}))
        status, body = self.page_add(port, OID)
        self.assertEqual((status, body.get("state")), (200, "sent"), body)
        status, body = self.machine(port)
        self.assertEqual([(o["oid"], o["terr"], o["force"]) for o in body["talk"]["start"]["orders"]], [(OID, TERR, False)])
        self.machine(port, start={"acks": [{"oid": OID, "state": "opened", "info": INFO}]})
        status, body = self.http(port, "/api/feed?dev=mac&gen=1&after=0")
        self.assertEqual(status, 200)
        self.assertEqual([(o["oid"], o["state"], o["info"]) for o in body["orders"]], [(OID, "opened", INFO)])
        self.assertIs(body["devs"][0]["start"], True)

    def test_another_site_cannot_order(self):
        proc, port, first = self.start("--talk")
        self.machine(port, with_view=True)
        status, body = self.page_add(port, OID, origin="https://evil.example")
        self.assertEqual(status, 403)

    def test_an_unknown_key_is_refused(self):
        proc, port, first = self.start("--talk")
        self.machine(port, with_view=True)
        status, body = self.page_add(port, OID, command="touch /tmp/pwned")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
