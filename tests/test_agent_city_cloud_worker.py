"""Failing tests, cloud-city-1 slice 2: the City Worker, the page on
Cloudflare (requirements/city.md, "Cloud page").

  bin/agent-city-cloud.js   ONE ES module, no import lines,
                            `export default { async fetch(request, env, ctx) }`.
  env.DB           the SAME D1 database the relay writes (table city_view,
                   tests/test_agent_city_cloud_relay.py). The City Worker only
                   reads it: it never writes a row and has no route that acts.
  env.ASSETS       the static assets binding: /index.html (bin/agent-city.html
                   as it is) and /assets/... (bin/agent-city-assets).
  env.ACCESS_TEAM  the Cloudflare Access team: "myteam",
                   "myteam.cloudflareaccess.com" or the full https address.
  env.ACCESS_AUD   the audience tag of the Access application.
  env.CITY_LANG    optional, "zh" (default) or "en".
  env.CITY_ASSET_V optional, the ?v= of asset addresses (default "1").

Login (C2). Cloudflare Access stands in front of the whole address and sends
every request on with a signed token. A Worker with static assets gets no
ctx.access, so the Worker checks the token ITSELF, on EVERY request, before
it touches an asset or the database:
  token   header Cf-Access-Jwt-Assertion, else the cookie CF_Authorization
  checks  RS256 only; the signature against the team's keys
          (GET https://<team>.cloudflareaccess.com/cdn-cgi/access/certs ->
          {"keys": [JWK, ...]}, picked by "kid", kept in memory for an hour:
          not fetched again on every request. Cloudflare changes the keys
          now and then: a token whose "kid" is not in the kept list makes the
          Worker fetch the list ONCE more, but at most once a minute, so a
          flood of made-up kids costs one fetch); "aud" holds ACCESS_AUD; "iss"
          is https://<team>.cloudflareaccess.com; "exp" is in the future; an
          "email" is there.
  fail    403 {"ok": false, "error": "login required"} and NOTHING else: no
          page, no asset, no data, no database read. Also when ACCESS_TEAM or
          ACCESS_AUD is not set (never open by mistake).

Routes (GET and HEAD only; anything else 405; no /v1/... here: 404):
  GET /           the page: the Worker asks ASSETS for "/" (Cloudflare's
  GET /index.html assets answer "/" with index.html, and answer a request
                  for "/index.html" with a redirect, so never ask for that)
                  and fills the placeholders: __CITY_CLOUD__ -> 1,
                  __CITY_TOKEN__ -> empty, __CITY_LANG__ -> CITY_LANG,
                  __CITY_ASSET_V__ -> CITY_ASSET_V.
                  text/html, Cache-Control: no-cache.
  GET /api/feed?dev=<dev>&gen=<n>&after=<n>
                  200, Cache-Control: no-store:
      {"ok": true, "user": "<the login e-mail, lower case>", "now": <ms>,
       "devs": [{"dev", "label", "ts", "gen", "counts": {people, busy, wait}}, ...],
                 this user's machines, the one seen last first
       "dev":  "<the machine this reply is about; '' when the user has none>",
       "gen":  <its picture's generation, 0 when none>,
       "after": <its newest batch number>,
       "snap":  [<page message>, ...]   ONLY when the caller's gen is not the
                                        stored one (first call, a new picture,
                                        another machine),
       "events": [<page message>, ...]} with snap: every event of the picture;
                                        else those of the batches after "after".
      dev: the one asked for when this user has it, else the one seen last.
      Only rows whose user is the login e-mail are ever read (C4).
  anything else   env.ASSETS.fetch(request): the assets, untouched, but a 200
                  answer to an address with ?v=<CITY_ASSET_V> gets
                  Cache-Control: private, max-age=31536000, immutable (a phone
                  loads the models once; the local server does the same).

Run: python3 -m unittest tests.test_agent_city_cloud_worker
"""

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from nodehelp import NODE, SKIP_REASON  # noqa: E402
import cloudhelp as ch  # noqa: E402
from cloudhelp import (KEY, ME, OTHER, T0, feed, get, person, snapshot, sync,  # noqa: E402
                       tool, view)

ANN = snapshot(person("s:1", "ann-session"), name="shop")
BOB = snapshot(person("s:1", "bob-session"), name="bobs-repo")


def seed_mac():
    """The owner's MacBook sent a picture and two event batches."""
    return [
        sync("mac", view=view(1, snap=[ANN], label="MacBook-Pro",
                              counts={"people": 1, "busy": 1, "wait": 0})),
        sync("mac", view=view(1, events=[tool("s:1")], label="MacBook-Pro"), now=T0 + 5000),
        sync("mac", view=view(1, events=[tool("s:1", "Read"), tool("s:1", "Edit")], label="MacBook-Pro"),
             now=T0 + 10000),
    ]


@unittest.skipUnless(NODE, SKIP_REASON)
class CityCase(unittest.TestCase):
    def run_city(self, requests, **kw):
        return ch.run_cloud(self, requests, **kw)

    def last(self, out):
        return out["responses"][-1]


class TestShape(unittest.TestCase):
    def src(self):
        self.assertTrue(os.path.isfile(ch.CITY), "bin/agent-city-cloud.js is missing")
        with open(ch.CITY) as fh:
            return fh.read()

    def test_one_self_contained_module(self):
        src = self.src()
        self.assertNotRegex(src, r"(?m)^\s*import\s", "no imports: one file")
        self.assertRegex(src, r"export\s+default")

    def test_it_never_writes_and_has_no_key(self):
        src = self.src()
        for word in ("INSERT", "UPDATE ", "DELETE", "CREATE TABLE", "TEAM_KEY"):
            self.assertNotIn(word, src, "the City Worker only reads city_view")


class TestNotLoggedIn(CityCase):
    PATHS = ["/", "/index.html", "/api/feed", "/assets/vendor/three.min.js",
             "/assets/characters/character-male-a.glb"]

    def assert_nothing(self, out, n):
        for r in out["responses"][-n:]:
            self.assertEqual(r["status"], 403, r)
            self.assertEqual(r["body"], {"ok": False, "error": "login required"})
            self.assertEqual((r["reads"], r["writes"]), (0, 0), "no database read without a login")
        self.assertEqual(out["assets_fetched"], [], "no asset is touched without a login")
        text = json.dumps([r["body"] for r in out["responses"][-n:]])
        for leak in ("ann-session", "MacBook-Pro", "Agent City", "three"):
            self.assertNotIn(leak, text)

    def test_no_token_gets_nothing(self):
        out = self.run_city(seed_mac() + [get(p, login=None) for p in self.PATHS])
        self.assert_nothing(out, len(self.PATHS))
        self.assertEqual(out["certs_fetches"], 0, "no token: nothing to check")

    def test_bad_tokens_get_nothing(self):
        bad = [
            {"email": ME, "aud": "another-application"},
            {"email": ME, "iss": "https://evil.cloudflareaccess.com"},
            {"email": ME, "exp_in": -10},
            {"email": ME, "wrong_key": True},
            {"email": ME, "kid": "k9"},
            {"email": ME, "alg": "none"},
            {"email": ME, "no_email": True},
        ]
        reqs = [get(p, login=b) for b in bad for p in ("/", "/api/feed", "/assets/vendor/three.min.js")]
        out = self.run_city(seed_mac() + reqs)
        self.assert_nothing(out, len(reqs))

    def test_garbage_token(self):
        reqs = [get("/api/feed", login=None, headers={"Cf-Access-Jwt-Assertion": t})
                for t in ("", "abc", "a.b.c", "e30.e30.", "..")]
        out = self.run_city(seed_mac() + reqs)
        self.assert_nothing(out, len(reqs))

    def test_access_not_set_up_is_closed(self):
        for env in ({}, {"ACCESS_TEAM": ch.TEAM}, {"ACCESS_AUD": ch.AUD},
                    {"ACCESS_TEAM": "", "ACCESS_AUD": ""}):
            out = self.run_city(seed_mac() + [get("/"), feed(), get("/assets/vendor/three.min.js")],
                                city_env=env)
            self.assert_nothing(out, 3)

    def test_a_spoofed_mail_header_is_not_a_login(self):
        out = self.run_city(seed_mac() + [
            get("/api/feed", login=None, headers={"Cf-Access-Authenticated-User-Email": ME})])
        self.assert_nothing(out, 1)


class TestLogin(CityCase):
    def test_header_and_cookie_both_work(self):
        out = self.run_city(seed_mac() + [feed(), feed(login={"email": ME, "via": "cookie"})])
        for r in out["responses"][-2:]:
            self.assertEqual(r["status"], 200, r)
            self.assertEqual(r["body"]["user"], ME)

    def test_team_may_be_written_three_ways(self):
        for team in (ch.TEAM, ch.TEAM + ".cloudflareaccess.com",
                     "https://%s.cloudflareaccess.com" % ch.TEAM,
                     "https://%s.cloudflareaccess.com/" % ch.TEAM):
            out = self.run_city(seed_mac() + [feed()],
                                city_env={"ACCESS_TEAM": team, "ACCESS_AUD": ch.AUD})
            self.assertEqual(self.last(out)["status"], 200, team)

    def test_keys_are_fetched_once_not_per_request(self):
        out = self.run_city(seed_mac() + [feed(), get("/"), feed(now=T0 + 60000),
                                          get("/assets/vendor/three.min.js", now=T0 + 120000)])
        self.assertEqual(out["certs_fetches"], 1)
        self.assertEqual(out["other_fetches"], [], "the Worker calls nothing but the team's keys")

    def test_keys_are_fetched_again_after_an_hour(self):
        out = self.run_city(seed_mac() + [feed(), feed(now=T0 + 3700 * 1000)])
        self.assertEqual(out["certs_fetches"], 2)

    def test_new_team_key_is_fetched_once_not_locked_out(self):
        # Cloudflare rotated the keys: the Worker holds the old list, the token is signed by the new key.
        out = self.run_city(seed_mac() + [
            feed(),                                                        # fetch 1: [k1]
            feed(login={"email": ME, "rotated": True}, now=T0 + 1000),     # unknown kid -> fetch 2: [k1, k2]
            feed(login={"email": ME, "rotated": True}, now=T0 + 2000),     # known now
            feed(login={"email": ME, "kid": "k9"}, now=T0 + 3000),         # made up: no fetch within a minute
            feed(login={"email": ME, "kid": "k8"}, now=T0 + 4000),
            feed(now=T0 + 5000)])
        self.assertEqual([r["status"] for r in out["responses"][-6:]], [200, 200, 200, 403, 403, 200])
        self.assertEqual(out["certs_fetches"], 2, "one more fetch for the new key, none for made-up kids")

    def test_unknown_kid_may_fetch_again_after_a_minute(self):
        out = self.run_city(seed_mac() + [
            feed(),
            feed(login={"email": ME, "kid": "k9"}, now=T0 + 1000),         # fetch 2
            feed(login={"email": ME, "kid": "k9"}, now=T0 + 30000),        # within the minute: none
            feed(login={"email": ME, "kid": "k9"}, now=T0 + 62000)])       # fetch 3
        self.assertEqual([r["status"] for r in out["responses"][-3:]], [403, 403, 403])
        self.assertEqual(out["certs_fetches"], 3)

    def test_mail_is_compared_in_lower_case(self):
        out = self.run_city(seed_mac() + [feed(login="Owner@Example.COM")])
        self.assertEqual(self.last(out)["body"]["user"], ME)
        self.assertEqual(self.last(out)["body"]["dev"], "mac")


class TestFeed(CityCase):
    def test_first_call_gets_the_picture_and_all_its_events(self):
        out = self.run_city(seed_mac() + [feed(now=T0 + 11000)])
        r = self.last(out)
        self.assertEqual(r["status"], 200)
        self.assertIn("no-store", r["headers"].get("cache-control", ""))
        b = r["body"]
        self.assertEqual((b["ok"], b["user"], b["now"]), (True, ME, T0 + 11000))
        self.assertEqual(b["devs"], [{"dev": "mac", "label": "MacBook-Pro", "ts": T0 + 10000, "gen": 1,
                                      "counts": {"people": 1, "busy": 1, "wait": 0}}])
        self.assertEqual((b["dev"], b["gen"], b["after"]), ("mac", 1, 2))
        self.assertEqual(b["snap"], [ANN])
        self.assertEqual(b["events"], [tool("s:1"), tool("s:1", "Read"), tool("s:1", "Edit")])

    def test_next_call_gets_only_new_events(self):
        out = self.run_city(seed_mac() + [feed(dev="mac", gen=1, after=1), feed(dev="mac", gen=1, after=2)])
        a, b = out["responses"][-2]["body"], out["responses"][-1]["body"]
        self.assertNotIn("snap", a)
        self.assertEqual(a["events"], [tool("s:1", "Read"), tool("s:1", "Edit")])
        self.assertEqual(a["after"], 2)
        self.assertNotIn("snap", b)
        self.assertEqual((b["events"], b["after"]), ([], 2))

    def test_a_new_picture_is_sent_whole(self):
        out = self.run_city(seed_mac() + [
            sync("mac", view=view(2, snap=[BOB], label="MacBook-Pro"), now=T0 + 60000),
            feed(dev="mac", gen=1, after=2, now=T0 + 61000)])
        b = self.last(out)["body"]
        self.assertEqual((b["gen"], b["after"], b["snap"], b["events"]), (2, 0, [BOB], []))

    def test_machines_newest_first_and_default_is_the_newest(self):
        out = self.run_city(seed_mac() + [
            sync("pc2", view=view(4, snap=[BOB], label="maverick-pc2",
                                  counts={"people": 2, "busy": 1, "wait": 1}), now=T0 + 20000),
            feed(now=T0 + 21000), feed(dev="mac", now=T0 + 21000),
            feed(dev="gone", now=T0 + 21000)])
        newest, mac, gone = [r["body"] for r in out["responses"][-3:]]
        self.assertEqual([d["dev"] for d in newest["devs"]], ["pc2", "mac"])
        self.assertEqual(newest["devs"][0]["counts"], {"people": 2, "busy": 1, "wait": 1})
        self.assertEqual((newest["dev"], newest["gen"], newest["snap"]), ("pc2", 4, [BOB]))
        self.assertEqual((mac["dev"], mac["snap"]), ("mac", [ANN]))
        self.assertEqual(gone["dev"], "pc2", "an unknown machine falls back to the one seen last")

    def test_no_machine_yet(self):
        out = self.run_city([sync("mac"), feed()])
        b = self.last(out)["body"]
        self.assertEqual((b["ok"], b["devs"], b["dev"], b["gen"], b["after"], b["events"]),
                         (True, [], "", 0, 0, []))
        self.assertNotIn("snap", b)

    def test_no_table_yet_is_an_empty_city_not_an_error(self):
        # The relay never ran (or the cloud is off): no city_view table.
        out = self.run_city([feed()])
        self.assertEqual(self.last(out)["status"], 200)
        self.assertEqual(self.last(out)["body"]["devs"], [])

    def test_bad_numbers_mean_first_call(self):
        out = self.run_city(seed_mac() + [get("/api/feed?dev=mac&gen=x&after=-3")])
        self.assertEqual(self.last(out)["body"]["snap"], [ANN])

    def test_reads_no_whole_table_and_never_writes(self):
        out = self.run_city(seed_mac() + [feed(), feed(dev="mac", gen=1, after=2), get("/")])
        scans = [s for s in out["full_scans"] if "city_view" in s["sql"] and "CREATE" not in s["sql"]]
        self.assertEqual(scans, [])
        for r in out["responses"][-3:]:
            self.assertEqual(r["writes"], 0)
        self.assertLessEqual(out["responses"][-2]["reads"], 3, "a poll reads this user's few rows")


class TestOnlyYourOwnRows(CityCase):
    def test_another_user_sees_nothing_of_the_owner(self):
        out = self.run_city(seed_mac() + [feed(login=OTHER), feed(login=OTHER, dev="mac", gen=1, after=0)])
        for r in out["responses"][-2:]:
            b = r["body"]
            self.assertEqual((b["user"], b["devs"], b["dev"]), (OTHER, [], ""))
            text = json.dumps(b)
            for leak in ("ann-session", "MacBook-Pro", "shop", ME):
                self.assertNotIn(leak, text)

    def test_two_users_two_cities(self):
        # Step 4 shape: every row carries its user; a login reads only its own rows,
        # also when another user's machine has the same dev id.
        other_relay = {"TEAM_KEY": KEY, "CITY_USER": OTHER}
        out = ch.run_cloud(self, [sync("mac", view=view(9, snap=[BOB], label="bob-mac")),
                                  feed(login=OTHER), feed(login=ME)], relay_env=other_relay)
        self.assertEqual({r["user"] for r in out["dump"]["city_view"]}, {OTHER})
        bob, me = [r["body"] for r in out["responses"][-2:]]
        self.assertEqual((bob["dev"], bob["snap"]), ("mac", [BOB]))
        self.assertEqual((me["devs"], me["dev"]), ([], ""), "the same dev id under another user is not yours")


class TestPageAndAssets(CityCase):
    def test_page_placeholders(self):
        out = self.run_city([get("/")])
        r = self.last(out)
        self.assertEqual(r["status"], 200)
        self.assertIn("text/html", r["headers"].get("content-type", ""))
        self.assertIn("no-cache", r["headers"].get("cache-control", ""))
        html = r["body"]
        self.assertNotRegex(html, r"__CITY_[A-Z_]+__", "every placeholder is filled")
        self.assertIn("const CLOUD = '1' === '1'", html)
        self.assertIn("const LANG = 'zh'", html)
        self.assertIn('content=""', html, "no control token on the cloud page")
        self.assertIn("three.min.js?v=1", html)
        self.assertEqual(out["assets_fetched"], ["/"], "ask the assets for /, never for /index.html")

    def test_language_and_asset_version(self):
        env = dict(ch.CITY_ENV, CITY_LANG="en", CITY_ASSET_V="0.15.0")
        html = self.last(self.run_city([get("/")], city_env=env))["body"]
        self.assertIn("const LANG = 'en'", html)
        self.assertIn("three.min.js?v=0.15.0", html)

    def test_index_html_is_the_same_page(self):
        out = self.run_city([get("/index.html")])
        self.assertNotRegex(self.last(out)["body"], r"__CITY_[A-Z_]+__")
        self.assertEqual(out["assets_fetched"], ["/"])

    def test_assets_pass_through(self):
        out = self.run_city([get("/assets/vendor/three.min.js?v=1"),
                             get("/assets/characters/character-male-a.glb"),
                             get("/assets/none.glb")])
        a, b, c = out["responses"]
        self.assertEqual((a["status"], a["body"]), (200, "/* three */"))
        self.assertEqual((b["status"], b["body"]), (200, "glb-bytes"))
        self.assertEqual(c["status"], 404)
        self.assertEqual([r["reads"] for r in out["responses"]], [0, 0, 0], "an asset never reads the database")

    def test_versioned_assets_are_cached_by_the_browser(self):
        env = dict(ch.CITY_ENV, CITY_ASSET_V="0.15.0")
        out = self.run_city([get("/assets/vendor/three.min.js?v=0.15.0"),
                             get("/assets/vendor/three.min.js?v=0.14.0"),
                             get("/assets/vendor/three.min.js"),
                             get("/assets/none.glb?v=0.15.0")], city_env=env)
        fresh, old, bare, missing = out["responses"]
        cc = fresh["headers"].get("cache-control", "")
        for word in ("private", "max-age=31536000", "immutable"):
            self.assertIn(word, cc)
        self.assertEqual(fresh["body"], "/* three */")
        for r in (old, bare, missing):
            self.assertNotIn("immutable", r["headers"].get("cache-control", ""))


class TestViewOnly(CityCase):
    def test_nothing_acts(self):
        reqs = [get("/api/feed", method="POST"), get("/api/decide", method="POST"),
                get("/api/chat/send", method="POST"), get("/", method="PUT"),
                get("/api/feed", method="DELETE")]
        out = self.run_city(seed_mac() + reqs)
        for r in out["responses"][-len(reqs):]:
            self.assertEqual(r["status"], 405, r)
            self.assertEqual(r["writes"], 0)

    def test_no_relay_and_no_local_routes_here(self):
        reqs = [get("/v1/sync"), get("/api/chat?to=s:1"), get("/api/asks"), get("/events"),
                get("/health"), get("/relay")]
        out = self.run_city(seed_mac() + reqs)
        for r in out["responses"][-len(reqs):]:
            self.assertEqual(r["status"], 404, r)
            self.assertNotIn("ann-session", json.dumps(r["body"]))


DEV = os.path.join(ch.BIN, "agent-city-cloud-dev.mjs")


@unittest.skipUnless(NODE, SKIP_REASON)
class TestDevRunner(unittest.TestCase):
    """bin/agent-city-cloud-dev.mjs: both Workers on one local port, for the
    E2E on a laptop. No Cloudflare account, nothing leaves the machine.

      node agent-city-cloud-dev.mjs --user <e-mail> [--host H] [--port P] [--no-login]
        The team key is the first line of stdin (never argv, never printed).
        Default host 127.0.0.1 (the login is simulated: never the LAN by
        default), default port 8788; --port 0 = any free port.
        stdout, first two lines:
          CLOUD-DEV: listening on <host>:<port>
          CLOUD-DEV: page http://<host>:<port>/  relay http://<host>:<port>
        /v1/...     -> bin/agent-city-relay.js   (TEAM_KEY = the key, CITY_USER = --user)
        the rest    -> bin/agent-city-cloud.js, as if Cloudflare Access had let
                       --user in: the runner signs a token for it with its own
                       key pair and answers the Worker's certs fetch itself.
                       --no-login: no token is added (everything is 403).
        ASSETS: / (and /index.html) = bin/agent-city.html, /assets/<p> =
        bin/agent-city-assets/<p> (never a path outside it).
        No --user -> exit 2. Empty key -> exit 2. Stops on SIGINT / SIGTERM.
    """

    def setUp(self):
        self.procs = []
        self.assertTrue(os.path.isfile(DEV), "bin/agent-city-cloud-dev.mjs is missing")

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(5)
                except Exception:
                    p.kill()
            for s in (p.stdout, p.stderr, p.stdin):
                if s:
                    s.close()

    def start(self, *args, key=KEY):
        import subprocess
        proc = subprocess.Popen([NODE, DEV, "--port", "0"] + list(args), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(proc)
        try:
            proc.stdin.write(key + "\n")
            proc.stdin.flush()
        except OSError:
            pass  # it already ended (no --user)
        first = proc.stdout.readline()
        second = proc.stdout.readline()
        return proc, first, second

    def http(self, port, path, method="GET", body=None, headers=None):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp.status, data

    def port_of(self, first):
        m = re.match(r"CLOUD-DEV: listening on 127\.0\.0\.1:(\d+)\s*$", first)
        self.assertTrue(m, "first line was: %r" % first)
        return int(m.group(1))

    def push(self, port, v):
        body = json.dumps({"dev": "mac", "after": 0, "lines": [], "view": v})
        return self.http(port, "/v1/sync", "POST", body,
                         {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})

    def test_page_feed_and_assets_for_the_user(self):
        proc, first, second = self.start("--user", ME)
        port = self.port_of(first)
        self.assertEqual(second.strip(),
                         "CLOUD-DEV: page http://127.0.0.1:%d/  relay http://127.0.0.1:%d" % (port, port))
        status, data = self.push(port, view(1, snap=[ANN], label="MacBook-Pro"))
        self.assertEqual(status, 200)
        self.assertIs(json.loads(data)["city"], True)
        status, data = self.http(port, "/api/feed")
        self.assertEqual(status, 200)
        body = json.loads(data)
        self.assertEqual((body["user"], body["dev"], body["snap"]), (ME, "mac", [ANN]))
        status, page = self.http(port, "/")
        self.assertEqual(status, 200)
        self.assertIn(b"<title>Agent City</title>", page)
        self.assertNotIn(b"__CITY_", page)
        status, js = self.http(port, "/assets/vendor/three.min.js")
        self.assertEqual(status, 200)
        self.assertGreater(len(js), 100000, "the real three.js from bin/agent-city-assets")
        self.assertEqual(self.http(port, "/assets/../agent_city.py")[0], 404)
        self.assertEqual(self.http(port, "/assets/%2e%2e/agent_city.py")[0], 404)

    def test_no_login_serves_nothing(self):
        proc, first, _ = self.start("--user", ME, "--no-login")
        port = self.port_of(first)
        self.assertEqual(self.push(port, view(1, snap=[ANN]))[0], 200, "machines still sync with the key")
        for path in ("/", "/api/feed", "/assets/vendor/three.min.js"):
            status, data = self.http(port, path)
            self.assertEqual(status, 403, path)
            self.assertNotIn(b"ann-session", data)

    def test_wrong_key_cannot_push(self):
        proc, first, _ = self.start("--user", ME)
        port = self.port_of(first)
        body = json.dumps({"dev": "mac", "after": 0, "lines": [], "view": view(1, snap=[ANN])})
        status, _ = self.http(port, "/v1/sync", "POST", body,
                              {"Authorization": "Bearer nope", "Content-Type": "application/json"})
        self.assertEqual(status, 401)

    def test_needs_a_user_and_a_key(self):
        proc, _, _ = self.start()
        self.assertEqual(proc.wait(10), 2)
        proc, _, _ = self.start("--user", ME, key="")
        self.assertEqual(proc.wait(10), 2)

    def test_key_is_never_printed(self):
        proc, first, second = self.start("--user", ME)
        self.assertNotIn(KEY, first + second)


if __name__ == "__main__":
    unittest.main()
