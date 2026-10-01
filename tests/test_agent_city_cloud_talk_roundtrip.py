"""Failing tests, cloud-city-2: the two Workers together, a message down and
its answer up (requirements/city.md, "Cloud page", step 2). Needs slices S1
(bin/agent-city-relay.js) and S2 (bin/agent-city-cloud.js); each has its own
test file, this one checks that they fit.

    the page  POST /api/chat/send  ->  city_msg 'sent'
    the machine's sync (talk key)  ->  msgs, 'taken'
    its next sync: acks + chat     ->  'queued' / 'delivered', and the row in city_chat
    the page  GET /api/feed?chat=  ->  on its way, then the machine's own row, once

No test talks to Cloudflare. Run: python3 -m unittest tests.test_agent_city_cloud_talk_roundtrip
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
from cloudhelp import KEY, ME, T0, TALK, TALK_ENV, feed, send, snapshot, sql, sync, view  # noqa: E402

CID = "cid-roundtrip-000001"


def tsync(dev="mac", now=T0, **kw):
    return sync(dev, talk_key=TALK, now=now, **kw)


def window(now, cc=0):
    return feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=cc, now=now)


@unittest.skipUnless(NODE, SKIP_REASON)
class TestRoundTrip(unittest.TestCase):
    def run_both(self, reqs):
        return ch.run_cloud(self, reqs, relay_env=TALK_ENV)

    def test_both_workers_make_the_same_tables(self):
        for path in (ch.RELAY, ch.CITY):
            with open(path, encoding="utf-8") as fh:
                src = " ".join(fh.read().split())
            for line in ch.TALK_TABLES:
                self.assertIn(" ".join(line.split()), src, "%s: this exact line is missing: %s" % (os.path.basename(path), line[:60]))

    def test_down_and_up(self):
        up = view(1, snap=[snapshot()])
        reqs = [
            tsync(view=up, now=T0),                                                        # 0 the machine, talk on
            feed(now=T0 + 500),                                                            # 1
            send(text="先跑一下测试", cid=CID, now=T0 + 1000),                               # 2 the owner types
            window(T0 + 2000),                                                             # 3 on its way
            tsync(now=T0 + 5000),                                                          # 4 the machine asks
            send(text="先跑一下测试", cid=CID, now=T0 + 5500),                               # 5 the page sends it again
            window(T0 + 6000),                                                             # 6 still on its way
            tsync(now=T0 + 6000, talk={"acks": [{"cid": CID, "state": "queued"}],          # 7 the session is busy
                                       "chat": [{"k": CID, "to": "s:tm1", "kind": "owner", "text": "先跑一下测试",
                                                 "at": 100.0, "state": "queued", "cid": CID}]}),
            window(T0 + 7000),                                                             # 8 queued, once
            tsync(now=T0 + 20000, talk={"acks": [{"cid": CID, "state": "delivered"}],      # 9 delivered + the reply
                                        "chat": [{"k": CID, "to": "s:tm1", "kind": "owner", "text": "先跑一下测试",
                                                  "at": 100.0, "state": "delivered", "cid": CID},
                                                 {"k": "r1", "to": "s:tm1", "kind": "reply", "text": "测试都过了",
                                                  "at": 130.0}]}),
            window(T0 + 21000),                                                            # 10 the first load again
            sql("SELECT COUNT(*) AS n FROM city_msg"),                                     # 11
        ]
        out = self.run_both(reqs)
        r = out["responses"]
        for i, x in enumerate(r):
            self.assertEqual(x["status"], 200, (i, x))
        self.assertIs(r[1]["body"]["devs"][0]["talk"], True)
        self.assertEqual(r[2]["body"], {"ok": True, "cid": CID, "state": "sent", "why": ""})
        self.assertEqual([(m["cid"], m["state"]) for m in r[3]["body"]["chat"]["msgs"]], [(CID, "sent")])
        self.assertEqual(r[4]["body"]["talk"]["msgs"], [{"cid": CID, "to": "s:tm1", "text": "先跑一下测试", "age": 4000}])
        self.assertEqual(r[5]["body"]["state"], "taken", "a repeated send never moves it back to sent")
        self.assertEqual([(m["cid"], m["state"]) for m in r[6]["body"]["chat"]["msgs"]], [(CID, "taken")])
        self.assertEqual(r[7]["body"]["talk"]["msgs"], [], "answered: not handed down again")
        chat = r[8]["body"]["chat"]
        self.assertEqual((chat["msgs"], [(x["k"], x["state"]) for x in chat["rows"]]), ([], [(CID, "queued")]))
        chat = r[10]["body"]["chat"]
        self.assertEqual(chat["msgs"], [])
        self.assertEqual([(x["kind"], x["text"], x["state"]) for x in chat["rows"]],
                         [("owner", "先跑一下测试", "delivered"), ("reply", "测试都过了", "")])
        self.assertEqual(r[11]["body"][0]["n"], 1, "one message, however often it was sent and handed down")

    def test_a_poll_after_the_cursor_sees_the_change_of_state(self):
        row = {"k": CID, "to": "s:tm1", "kind": "owner", "text": "go", "at": 100.0, "state": "queued", "cid": CID}
        reqs = [tsync(view=view(1, snap=[snapshot()])), send(text="go", cid=CID, now=T0 + 1000), tsync(now=T0 + 2000),
                tsync(now=T0 + 3000, talk={"acks": [{"cid": CID, "state": "queued"}], "chat": [row]}),
                window(T0 + 4000),
                tsync(now=T0 + 9000, talk={"acks": [{"cid": CID, "state": "delivered"}],
                                           "chat": [dict(row, state="delivered")]})]
        out = self.run_both(reqs)
        cc = out["responses"][4]["body"]["chat"]["cc"]
        self.assertGreater(cc, 0)
        out = self.run_both(reqs + [window(T0 + 10000, cc=cc)])
        chat = out["responses"][-1]["body"]["chat"]
        self.assertEqual([(x["k"], x["state"]) for x in chat["rows"]], [(CID, "delivered")])
        self.assertGreater(chat["cc"], cc)

    def test_the_machine_is_off_so_the_page_says_so(self):
        reqs = [tsync(view=view(1, snap=[snapshot()])), send(cid=CID, now=T0 + 1000),
                window(T0 + 61000), tsync(now=T0 + 400000), window(T0 + 401000)]
        out = self.run_both(reqs)
        r = out["responses"]
        self.assertEqual([(m["state"], m["why"]) for m in r[2]["body"]["chat"]["msgs"]], [("undelivered", "off")])
        self.assertEqual(r[3]["body"]["talk"]["msgs"], [], "back online later: it is not delivered after all")
        self.assertEqual([(m["state"], m["why"]) for m in r[4]["body"]["chat"]["msgs"]], [("undelivered", "off")])

    def test_talk_off_on_the_machine_shows_on_the_page(self):
        reqs = [tsync(view=view(1, snap=[snapshot()])), send(cid=CID, now=T0 + 1000),
                tsync(now=T0 + 2000, talk={"off": True}), window(T0 + 3000),
                sync("mac", view=view(1), now=T0 + 4000), feed(now=T0 + 5000),
                send(cid="cid-roundtrip-000002", now=T0 + 6000)]
        out = self.run_both(reqs)
        r = out["responses"]
        self.assertEqual([(m["state"], m["why"]) for m in r[3]["body"]["chat"]["msgs"]], [("undelivered", "talk-off")])
        self.assertIs(r[5]["body"]["devs"][0]["talk"], False)
        self.assertEqual((r[6]["body"]["state"], r[6]["body"]["why"]), ("undelivered", "talk-off"))

    def test_the_team_key_alone_gets_nothing_and_makes_nothing(self):
        reqs = [tsync(view=view(1, snap=[snapshot()])), send(text="secret order", cid=CID, now=T0 + 1000),
                sync("mac", now=T0 + 2000, talk={"acks": [{"cid": CID, "state": "delivered"}]}),
                sync("mac", now=T0 + 3000, talk_key=KEY), window(T0 + 4000), tsync(now=T0 + 5000)]
        out = self.run_both(reqs)
        r = out["responses"]
        self.assertNotIn("secret order", repr(r[2]["body"]) + repr(r[3]["body"]))
        self.assertEqual([(m["cid"], m["state"]) for m in r[4]["body"]["chat"]["msgs"]], [(CID, "sent")])
        self.assertEqual([m["text"] for m in r[5]["body"]["talk"]["msgs"]], ["secret order"])


DEV = os.path.join(ch.BIN, "agent-city-cloud-dev.mjs")


@unittest.skipUnless(NODE, SKIP_REASON)
class TestDevRunnerTalks(unittest.TestCase):
    """bin/agent-city-cloud-dev.mjs (slice S6), for the E2E on a laptop:

      node agent-city-cloud-dev.mjs --user <e-mail> --talk [--port P]
        --talk: the SECOND line of stdin is the talk key (the relay's
        TALK_KEY; never argv, never printed). Without --talk the relay has no
        TALK_KEY, as before. --talk and no second line -> exit 2.
      A POST to the City Worker (/api/chat/send) goes through with its
      method, headers and body; the token of --user is added as before.
    """

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

    def machine(self, port, talk=None, talk_key=TALK, with_view=False):
        body = {"dev": "mac", "after": 0, "lines": []}
        if with_view:
            body["view"] = view(1, snap=[snapshot()], label="MacBook-Pro")
        if talk is not None:
            body["talk"] = talk
        headers = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
        if talk_key:
            headers["X-City-Talk"] = talk_key
        return self.http(port, "/v1/sync", "POST", body, headers)

    def page_send(self, port, text, cid, origin=None):
        headers = {"Content-Type": "application/json", "X-City-Page": "1",
                   "Origin": origin or "http://127.0.0.1:%d" % port}
        return self.http(port, "/api/chat/send", "POST", {"dev": "mac", "to": "s:tm1", "text": text, "cid": cid}, headers)

    def test_a_message_goes_down_and_its_answer_comes_up(self):
        proc, port, first = self.start("--talk")
        self.assertTrue(port, "first line was: %r" % first)
        status, body = self.machine(port, with_view=True)
        self.assertEqual((status, body["talk"]), (200, {"state": "on", "msgs": []}))
        status, body = self.page_send(port, "先跑一下测试", CID)
        self.assertEqual((status, body.get("state")), (200, "sent"), body)
        status, body = self.machine(port)
        self.assertEqual([m["text"] for m in body["talk"]["msgs"]], ["先跑一下测试"])
        row = {"k": CID, "to": "s:tm1", "kind": "owner", "text": "先跑一下测试", "at": 100.0, "state": "delivered", "cid": CID}
        self.machine(port, talk={"acks": [{"cid": CID, "state": "delivered"}], "chat": [row]})
        status, body = self.http(port, "/api/feed?dev=mac&gen=1&after=0&chat=s%3Atm1&cc=0")
        self.assertEqual(status, 200)
        self.assertEqual([(r["text"], r["state"]) for r in body["chat"]["rows"]], [("先跑一下测试", "delivered")])
        self.assertEqual(body["chat"]["msgs"], [])

    def test_another_site_cannot_send(self):
        proc, port, first = self.start("--talk")
        self.machine(port, with_view=True)
        status, body = self.page_send(port, "x", CID, origin="https://evil.example")
        self.assertEqual(status, 403)

    def test_without_talk_the_relay_has_no_talk_key(self):
        proc, port, first = self.start(lines=(KEY,))
        self.assertTrue(port, "first line was: %r" % first)
        status, body = self.machine(port, with_view=True)
        self.assertEqual((status, body["talk"]), (200, {"state": "off"}))

    def test_talk_needs_its_key(self):
        proc, port, first = self.start("--talk", lines=(KEY,))
        proc.wait(10)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn(KEY, proc.stderr.read())


if __name__ == "__main__":
    unittest.main()
