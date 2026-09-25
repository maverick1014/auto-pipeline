"""Failing tests for bin/agent-city-relay.js, the team relay (requirements/city.md,
"Joining" and "Relay setup").

The relay is one Cloudflare Worker per team, on the team owner's own free
Cloudflare account. It holds the last few minutes of city lines, never a
history, and hands each joined machine the lines the other machines sent.

Shape (one file, so a person can paste it into the Cloudflare dashboard):

  bin/agent-city-relay.js  one ES module, no import lines,
                           `export default { async fetch(request, env, ctx) }`.
  env.TEAM_KEY             the team key, a Cloudflare secret.
  env.DB                   a D1 database binding. The Worker creates its own
                           table(s) on first use (CREATE TABLE IF NOT EXISTS);
                           the person never types SQL.

Routes:

  GET  /          no key needed. 200 {"ok": true, "relay": "agent-city", "v": 1}
                  So a person can open the address in a browser and see it is up.
  POST /v1/sync   header  Authorization: Bearer <TEAM_KEY>
                  body    {"dev": "<device id, 1..64 chars>",
                           "after": <int, the last seq this device saw, 0 = none>,
                           "lines": [<object>, ...]}
                  200     {"ok": true, "seq": <latest seq the relay has>,
                           "lines": [{"seq": n, "dev": "<sender>", "line": {...}}, ...]}
                  Returns the lines with seq > after that were sent by OTHER
                  devices in the last 300 seconds, oldest first, at most 500
                  (the newest 500). A device never gets its own lines back.
                  "seq" is the newest seq the relay holds, own lines included,
                  so the next "after" moves past them.
  401             missing or wrong key: {"ok": false, "error": ...}. Nothing stored.
  500             env.TEAM_KEY not set: {"ok": false, "error": "... TEAM_KEY ..."}.
  400             body not JSON, "lines" not a list, a line not an object,
                  "dev" missing, empty or longer than 64, "after" not a number.
  413             more than 200 lines, or a body over 256 KB.
  405             /v1/sync with any method but POST.
  404             any other path.

Cost (Cloudflare's free plan counts D1 rows written AND rows read): one sync
with lines writes ONE row for the whole batch, a sync with no lines writes
nothing, and rows older than 300 seconds are deleted, so the store never
grows into a history. No statement reads a whole table: every lookup, the
newest seq and the delete go through an index (the harness checks each
statement's SQLite query plan). The key is never echoed in any response.

seq never goes back, not even after every row aged out and was deleted: a
device that last saw seq N must get every line sent after that.

Real D1 runs exec() line by line; the harness does too. A CREATE TABLE
written over several lines goes through prepare().

Run: python3 -m unittest tests.test_agent_city_relay_worker
"""

import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(ROOT, "bin", "agent-city-relay.js")
HARNESS = os.path.join(HERE, "relay_harness.mjs")
NODE = shutil.which("node")

KEY = "test-team-key-not-real-0001"
T0 = 1_800_000_000_000  # a fixed clock, ms


def auth(key=KEY):
    return {"Authorization": "Bearer " + key, "Content-Type": "application/json"}


def sync(dev, lines=(), after=0, now=T0, key=KEY):
    return {"method": "POST", "path": "/v1/sync", "headers": auth(key),
            "body": {"dev": dev, "after": after, "lines": list(lines)}, "now": now}


def ev(n):
    return {"ev": "PostToolUse", "sid": "s%d" % n, "tool": "Bash", "rid": "github.com/o/r"}


@unittest.skipUnless(NODE, "node is not installed")
class RelayCase(unittest.TestCase):
    def run_relay(self, requests, env=None):
        if env is None:
            env = {"TEAM_KEY": KEY}
        self.assertTrue(os.path.isfile(WORKER), "bin/agent-city-relay.js is missing")
        proc = subprocess.run(
            [NODE, HARNESS, WORKER, "run"],
            input=json.dumps({"env": env, "requests": requests}),
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        for r in out["responses"]:
            self.assertNotEqual(r["status"], -1, "the Worker threw: %s" % r["body"])
        return out

    def statuses(self, out):
        return [r["status"] for r in out["responses"]]


class TestShape(unittest.TestCase):
    def test_one_self_contained_module(self):
        self.assertTrue(os.path.isfile(WORKER), "bin/agent-city-relay.js is missing")
        with open(WORKER) as fh:
            text = fh.read()
        lines = [l.strip() for l in text.splitlines()]
        self.assertFalse([l for l in lines if l.startswith("import ")],
                         "a pasted Worker cannot import other files")
        self.assertIn("export default", text)
        self.assertIn("TEAM_KEY", text)
        self.assertIn("CREATE TABLE IF NOT EXISTS", text)


class TestRoot(RelayCase):
    def test_root_says_relay_without_a_key(self):
        out = self.run_relay([{"method": "GET", "path": "/"}])
        r = out["responses"][0]
        self.assertEqual(r["status"], 200)
        self.assertEqual(r["body"], {"ok": True, "relay": "agent-city", "v": 1})

    def test_unknown_path_is_404(self):
        out = self.run_relay([{"method": "GET", "path": "/v1/nope"},
                              {"method": "GET", "path": "/admin", "headers": auth()}])
        self.assertEqual(self.statuses(out), [404, 404])

    def test_sync_is_post_only(self):
        out = self.run_relay([{"method": "GET", "path": "/v1/sync", "headers": auth()},
                              {"method": "PUT", "path": "/v1/sync", "headers": auth(),
                               "body": {"dev": "a", "after": 0, "lines": []}}])
        self.assertEqual(self.statuses(out), [405, 405])


class TestKey(RelayCase):
    def test_missing_key_is_401_and_nothing_stored(self):
        no_auth = sync("A", [ev(1)])
        no_auth["headers"] = {"Content-Type": "application/json"}
        out = self.run_relay([no_auth, sync("B")])
        self.assertEqual(self.statuses(out), [401, 200])
        self.assertIs(out["responses"][0]["body"]["ok"], False)
        self.assertEqual(out["responses"][1]["body"]["lines"], [])
        self.assertEqual(out["rows_total"], 0)

    def test_wrong_key_is_401(self):
        out = self.run_relay([sync("A", [ev(1)], key="wrong"),
                              sync("A", [ev(1)], key=KEY + "x"),
                              sync("A", [ev(1)], key=KEY[:-1]),
                              sync("A", [ev(1)], key="")])
        self.assertEqual(self.statuses(out), [401, 401, 401, 401])
        self.assertEqual(out["rows_total"], 0)

    def test_not_bearer_is_401(self):
        req = sync("A", [ev(1)])
        req["headers"] = {"Authorization": KEY, "Content-Type": "application/json"}
        out = self.run_relay([req])
        self.assertEqual(self.statuses(out), [401])

    def test_no_team_key_set_is_500_and_says_so(self):
        out = self.run_relay([sync("A", [ev(1)], key="anything")], env={})
        r = out["responses"][0]
        self.assertEqual(r["status"], 500)
        self.assertIs(r["body"]["ok"], False)
        self.assertIn("TEAM_KEY", r["body"]["error"])

    def test_key_never_echoed(self):
        out = self.run_relay([sync("A", [ev(1)]), sync("B"),
                              sync("A", key=KEY + "x"), {"method": "GET", "path": "/"}])
        self.assertNotIn(KEY, json.dumps(out["responses"]))


class TestSync(RelayCase):
    def test_lines_reach_other_devices_only(self):
        out = self.run_relay([sync("A", [ev(1), ev(2)]), sync("B"), sync("A")])
        a1, b, a2 = out["responses"]
        self.assertEqual([r["status"] for r in (a1, b, a2)], [200, 200, 200])
        self.assertIs(a1["body"]["ok"], True)
        got = b["body"]["lines"]
        self.assertEqual([x["line"] for x in got], [ev(1), ev(2)])
        self.assertEqual({x["dev"] for x in got}, {"A"})
        self.assertTrue(all(isinstance(x["seq"], int) and x["seq"] > 0 for x in got))
        self.assertEqual(a2["body"]["lines"], [], "a device never gets its own lines back")
        self.assertEqual(b["body"]["seq"], max(x["seq"] for x in got))
        self.assertEqual(a2["body"]["seq"], b["body"]["seq"])

    def test_after_returns_only_newer_lines(self):
        first = self.run_relay([sync("A", [ev(1)]), sync("B")])
        seq1 = first["responses"][1]["body"]["seq"]
        out = self.run_relay([sync("A", [ev(1)]), sync("B"),
                              sync("A", [ev(2)], now=T0 + 1000),
                              sync("B", after=seq1, now=T0 + 2000)])
        last = out["responses"][3]["body"]
        self.assertEqual([x["line"] for x in last["lines"]], [ev(2)])
        self.assertGreater(last["seq"], seq1)

    def test_seq_moves_past_own_lines(self):
        out = self.run_relay([sync("A", [ev(1)]), sync("A", [ev(2)], now=T0 + 10)])
        s1 = out["responses"][0]["body"]["seq"]
        s2 = out["responses"][1]["body"]["seq"]
        self.assertGreater(s1, 0)
        self.assertGreater(s2, s1)

    def test_three_devices(self):
        out = self.run_relay([sync("A", [ev(1)]), sync("B", [ev(2)], now=T0 + 1),
                              sync("C", now=T0 + 2)])
        got = out["responses"][2]["body"]["lines"]
        self.assertEqual([(x["dev"], x["line"]) for x in got], [("A", ev(1)), ("B", ev(2))])

    def test_empty_sync_writes_nothing(self):
        out = self.run_relay([sync("A"), sync("B"), sync("A")])
        self.assertEqual(self.statuses(out), [200, 200, 200])
        self.assertEqual(out["rows_total"], 0)
        self.assertEqual(out["responses"][0]["body"]["seq"], 0)

    def test_one_row_per_batch(self):
        out = self.run_relay([sync("A", [ev(i) for i in range(50)])])
        self.assertEqual(self.statuses(out), [200])
        self.assertEqual(out["rows_total"], 1, "one D1 row per sync, not one per line")


class TestWindow(RelayCase):
    def test_lines_older_than_300s_are_not_handed_out(self):
        out = self.run_relay([sync("A", [ev(1)], now=T0),
                              sync("B", now=T0 + 299_000),
                              sync("C", now=T0 + 301_000)])
        self.assertEqual([x["line"] for x in out["responses"][1]["body"]["lines"]], [ev(1)])
        self.assertEqual(out["responses"][2]["body"]["lines"], [])

    def test_old_rows_are_deleted(self):
        out = self.run_relay([sync("A", [ev(1)], now=T0),
                              sync("A", [ev(2)], now=T0 + 100_000),
                              sync("A", [ev(3)], now=T0 + 400_000)])
        self.assertEqual(self.statuses(out), [200, 200, 200])
        self.assertEqual(out["rows_total"], 1, "rows past the window are deleted, no history")

    def test_new_joiner_gets_newest_500(self):
        reqs = [sync("A", [{"n": b * 200 + i} for i in range(200)], now=T0 + b) for b in range(3)]
        reqs.append(sync("B", now=T0 + 10))
        out = self.run_relay(reqs)
        got = [x["line"]["n"] for x in out["responses"][3]["body"]["lines"]]
        self.assertEqual(got, list(range(100, 600)))
        self.assertEqual(out["responses"][3]["body"]["seq"], out["responses"][2]["body"]["seq"])


class TestCost(RelayCase):
    def test_no_statement_reads_a_whole_table(self):
        reqs = [sync("A", [ev(1), ev(2)], now=T0), sync("B", now=T0 + 1),
                sync("B", [ev(3)], now=T0 + 2), sync("A", after=2, now=T0 + 3),
                sync("C", now=T0 + 350_000), sync("A", [ev(4)], now=T0 + 360_000),
                sync("B", after=3, now=T0 + 361_000)]
        out = self.run_relay(reqs)
        self.assertEqual(set(self.statuses(out)), {200})
        self.assertEqual(out["full_scans"], [], "every lookup must use an index")


class TestSeqNeverGoesBack(RelayCase):
    def test_after_the_store_emptied(self):
        out = self.run_relay([
            sync("A", [ev(1), ev(2), ev(3)], now=T0),
            sync("B", now=T0 + 1_000),                # B has seen up to here
            sync("C", now=T0 + 350_000),              # an empty sync; every row has aged out
            sync("A", [ev(4)], now=T0 + 360_000),     # a new line after the store emptied
        ])
        seen = out["responses"][1]["body"]["seq"]
        later = self.run_relay([
            sync("A", [ev(1), ev(2), ev(3)], now=T0),
            sync("B", now=T0 + 1_000),
            sync("C", now=T0 + 350_000),
            sync("A", [ev(4)], now=T0 + 360_000),
            sync("B", after=seen, now=T0 + 361_000),
        ])
        got = later["responses"][4]["body"]
        self.assertEqual([x["line"] for x in got["lines"]], [ev(4)],
                         "a line sent after the store emptied was lost")
        self.assertGreater(got["seq"], seen)
        self.assertGreater(out["responses"][3]["body"]["seq"], seen)


class TestBadInput(RelayCase):
    def bad(self, body, want=400):
        req = sync("A")
        req["body"] = body
        out = self.run_relay([req, sync("B")])
        self.assertEqual(out["responses"][0]["status"], want, body if len(str(body)) < 200 else "big")
        self.assertIs(out["responses"][0]["body"]["ok"], False)
        self.assertEqual(out["rows_total"], 0)

    def test_not_json(self):
        self.bad("{nope")

    def test_lines_not_a_list(self):
        self.bad({"dev": "A", "after": 0, "lines": {"a": 1}})

    def test_line_not_an_object(self):
        self.bad({"dev": "A", "after": 0, "lines": [ev(1), "text"]})
        self.bad({"dev": "A", "after": 0, "lines": [[1, 2]]})

    def test_dev_missing_empty_or_long(self):
        self.bad({"after": 0, "lines": []})
        self.bad({"dev": "", "after": 0, "lines": []})
        self.bad({"dev": "x" * 65, "after": 0, "lines": []})
        self.bad({"dev": 7, "after": 0, "lines": []})

    def test_after_not_a_number(self):
        self.bad({"dev": "A", "after": "5", "lines": []})

    def test_too_many_lines(self):
        self.bad({"dev": "A", "after": 0, "lines": [ev(i) for i in range(201)]}, want=413)

    def test_body_too_big(self):
        self.bad({"dev": "A", "after": 0, "lines": [{"pad": "x" * 2000} for _ in range(150)]},
                 want=413)

    def test_exactly_200_lines_is_fine(self):
        out = self.run_relay([sync("A", [ev(i) for i in range(200)])])
        self.assertEqual(self.statuses(out), [200])


if __name__ == "__main__":
    unittest.main()
