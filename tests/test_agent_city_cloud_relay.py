"""Failing tests, cloud-city-1 slice 1: the relay keeps each machine's city
picture for the cloud page (requirements/city.md, "Cloud page").

bin/agent-city-relay.js stays ONE file with no import lines (a person pastes
it into the Cloudflare dashboard). Everything it did before stays as it was
(tests/test_agent_city_relay_worker.py still passes, unchanged).

New, all inside POST /v1/sync (same team key, no new route):

  env.CITY_USER   a plain variable: the owner's e-mail. Unset or blank = the
                  cloud page is off: a "view" in the body is ignored, nothing
                  is stored, the reply is exactly today's {"ok","seq","lines"}.
                  Set = the cloud page is on. EVERY sync reply then also has
                      "city": true, "gen": <the generation of the picture the
                                            relay holds for this dev; 0 = none>
                  also a sync with no view (a machine asks "is the cloud on?").

  body.view       optional. One machine's picture, ready for the page:
      {"label":  "<device tag people see, 1..64 chars>",
       "gen":    <int >= 1; the sender raises it with every new picture>,
       "counts": {"people": n, "busy": n, "wait": n}   (whole numbers >= 0),
       "snap":   [<page message>, ...]   optional: a NEW picture (the page's
                                          snapshot message, then maybe more),
       "events": [<page message>, ...]}  optional: what happened after the
                                          picture, in order; at most 500

  Stored in ONE table, one row per user + machine (the free plan counts D1
  rows written, so a sync writes at most ONE row for a view):
      city_view (user, dev, label, ts, gen, n, counts, snap, events,
                 PRIMARY KEY (user, dev))
      user   = CITY_USER, trimmed, lower case. Every row has it (step 4:
               each user reads only his own rows).
      ts     = when this machine last sent a view (ms)
      n      = how many event batches this picture has (0 right after a snap)
      snap   = the JSON text of view.snap
      events = the batches of this picture, one line each, in order:
               {"n": <1, 2, ...>, "e": [<page message>, ...]}

  Rules:
    snap given       -> the row of (user, dev) is replaced: label, ts, gen,
                        counts, snap, n = 0, events empty. Events sent in
                        the same view become batch 1.
    events, no snap  -> only when the stored gen equals view.gen: n + 1, the
                        batch is appended, label, ts and counts are updated.
                        Another gen, or no row: nothing is stored (the reply's
                        "gen" tells the sender to send a new picture).
    neither          -> a sign of life: ts, label, counts updated when the
                        stored gen equals view.gen; else nothing.
    old machines     -> when a snap is stored, this user's rows not seen for
                        24 hours are deleted (never on other syncs).
  400  view is not an object; label missing, empty or over 64; gen not a whole
       number >= 1; counts missing or not three whole numbers >= 0; snap or
       events not a list of objects. Nothing is stored, the lines neither.
  413  more than 500 events.
  No statement reads a whole table. The key and the e-mail are never echoed.

Run: python3 -m unittest tests.test_agent_city_cloud_relay
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from nodehelp import NODE, SKIP_REASON  # noqa: E402
import cloudhelp as ch  # noqa: E402
from cloudhelp import KEY, ME, T0, person, snapshot, sync, tool, view  # noqa: E402

DAY = 24 * 3600 * 1000


@unittest.skipUnless(NODE, SKIP_REASON)
class CloudRelayCase(unittest.TestCase):
    def run_relay(self, requests, env=None):
        return ch.run_cloud(self, requests, relay_env=env, city="-")

    def rows(self, out):
        return out["dump"].get("city_view", [])

    def row(self, out, dev):
        hits = [r for r in self.rows(out) if r["dev"] == dev]
        self.assertEqual(len(hits), 1, "one row per user + machine: %r" % self.rows(out))
        return hits[0]

    def batches(self, row):
        return [json.loads(line) for line in row["events"].splitlines() if line.strip()]


class TestShape(unittest.TestCase):
    def test_still_one_file_without_imports(self):
        with open(ch.RELAY) as fh:
            src = fh.read()
        self.assertNotRegex(src, r"(?m)^\s*import\s", "the relay is pasted into the dashboard: no imports")
        self.assertIn("CITY_USER", src)
        self.assertIn("city_view", src)

    def test_create_table_is_one_line_per_statement(self):
        # Real D1 runs exec() line by line.
        with open(ch.RELAY) as fh:
            src = fh.read()
        line = [l for l in src.splitlines() if "CREATE TABLE IF NOT EXISTS city_view" in l]
        self.assertEqual(len(line), 1, "one CREATE TABLE line for city_view")
        self.assertIn("PRIMARY KEY (user, dev)", line[0])


class TestCloudOff(CloudRelayCase):
    def test_no_city_user_is_exactly_today(self):
        out = self.run_relay(
            [sync("a", [{"ev": "PostToolUse", "sid": "s1"}],
                  view=view(1, snap=[snapshot(person("s:1", "one"))])),
             sync("b")],
            env={"TEAM_KEY": KEY})
        self.assertEqual([r["status"] for r in out["responses"]], [200, 200])
        self.assertEqual(set(out["responses"][0]["body"]), {"ok", "seq", "lines"})
        self.assertEqual(set(out["responses"][1]["body"]), {"ok", "seq", "lines"})
        self.assertEqual(len(out["responses"][1]["body"]["lines"]), 1, "lines still flow")
        self.assertEqual(self.rows(out), [], "the cloud is off: no picture is kept")

    def test_blank_city_user_is_off(self):
        out = self.run_relay([sync("a", view=view(1, snap=[snapshot()]))],
                             env={"TEAM_KEY": KEY, "CITY_USER": "   "})
        self.assertNotIn("city", out["responses"][0]["body"])
        self.assertEqual(self.rows(out), [])


class TestCloudOn(CloudRelayCase):
    def test_every_reply_says_city_on(self):
        out = self.run_relay([sync("a"), sync("a", [{"ev": "Stop", "sid": "s1"}])])
        for r in out["responses"]:
            self.assertEqual(r["status"], 200)
            self.assertIs(r["body"]["city"], True)
            self.assertEqual(r["body"]["gen"], 0, "no picture yet")
        self.assertEqual(self.rows(out), [], "a sync with no view stores no picture")

    def test_a_picture_is_stored_under_the_user(self):
        snap = [snapshot(person("s:1", "cloud-city-1 Task Manager"))]
        out = self.run_relay([sync("a", view=view(3, snap=snap, label="MacBook-Pro",
                                                  counts={"people": 1, "busy": 1, "wait": 0}))],
                             env={"TEAM_KEY": KEY, "CITY_USER": "  Owner@Example.com "})
        body = out["responses"][0]["body"]
        self.assertEqual((body["city"], body["gen"]), (True, 3))
        row = self.row(out, "a")
        self.assertEqual(row["user"], "owner@example.com", "trimmed, lower case")
        self.assertEqual((row["label"], row["gen"], row["n"], row["ts"]), ("MacBook-Pro", 3, 0, T0))
        self.assertEqual(json.loads(row["snap"]), snap)
        self.assertEqual(json.loads(row["counts"]), {"people": 1, "busy": 1, "wait": 0})
        self.assertEqual(self.batches(row), [])

    def test_events_are_appended_as_batches(self):
        out = self.run_relay([
            sync("a", view=view(1, snap=[snapshot(person("s:1", "one"))])),
            sync("a", view=view(1, events=[tool("s:1"), tool("s:1", "Read")]), now=T0 + 5000),
            sync("a", view=view(1, events=[tool("s:1", "Edit")],
                                counts={"people": 1, "busy": 0, "wait": 1}), now=T0 + 10000),
        ])
        self.assertEqual([r["body"]["gen"] for r in out["responses"]], [1, 1, 1])
        row = self.row(out, "a")
        self.assertEqual((row["n"], row["ts"]), (2, T0 + 10000))
        self.assertEqual(self.batches(row), [
            {"n": 1, "e": [tool("s:1"), tool("s:1", "Read")]},
            {"n": 2, "e": [tool("s:1", "Edit")]}])
        self.assertEqual(json.loads(row["counts"])["wait"], 1, "counts follow the newest view")

    def test_snap_with_events_in_one_view(self):
        out = self.run_relay([sync("a", view=view(1, snap=[snapshot()], events=[tool("s:1")]))])
        row = self.row(out, "a")
        self.assertEqual(row["n"], 1)
        self.assertEqual(self.batches(row), [{"n": 1, "e": [tool("s:1")]}])

    def test_a_new_picture_replaces_the_old_one(self):
        out = self.run_relay([
            sync("a", view=view(1, snap=[snapshot(person("s:1", "one"))], events=[tool("s:1")])),
            sync("a", view=view(2, snap=[snapshot(person("s:2", "two"))]), now=T0 + 60000),
        ])
        row = self.row(out, "a")
        self.assertEqual((row["gen"], row["n"]), (2, 0))
        self.assertEqual(self.batches(row), [], "the old picture's events are gone")
        self.assertIn("two", row["snap"])
        self.assertNotIn("one", row["snap"])

    def test_events_of_another_gen_are_not_stored(self):
        out = self.run_relay([
            sync("a", view=view(1, snap=[snapshot()])),
            sync("a", view=view(2, events=[tool("s:1")]), now=T0 + 5000),
            sync("b", view=view(1, events=[tool("s:9")]), now=T0 + 5000),
        ])
        self.assertEqual(out["responses"][1]["body"]["gen"], 1,
                         "the reply names the gen the relay holds, so the sender sends a new picture")
        self.assertEqual(out["responses"][2]["body"]["gen"], 0, "no picture for dev b")
        row = self.row(out, "a")
        self.assertEqual((row["gen"], row["n"], row["ts"]), (1, 0, T0))
        self.assertEqual([r["dev"] for r in self.rows(out)], ["a"])

    def test_sign_of_life_updates_ts_only(self):
        out = self.run_relay([
            sync("a", view=view(1, snap=[snapshot()], label="mac")),
            sync("a", view=view(1, label="mac", counts={"people": 0, "busy": 0, "wait": 0}),
                 now=T0 + 60000),
        ])
        row = self.row(out, "a")
        self.assertEqual((row["ts"], row["n"]), (T0 + 60000, 0))
        self.assertEqual(json.loads(row["counts"])["people"], 0)

    def test_one_machine_never_touches_another(self):
        out = self.run_relay([
            sync("a", view=view(1, snap=[snapshot(person("s:1", "on a"))], label="mac")),
            sync("b", view=view(7, snap=[snapshot(person("s:1", "on b"))], label="pc2")),
            sync("a", view=view(1, events=[tool("s:1")]), now=T0 + 5000),
        ])
        self.assertEqual({r["dev"]: (r["label"], r["gen"], r["n"]) for r in self.rows(out)},
                         {"a": ("mac", 1, 1), "b": ("pc2", 7, 0)})

    def test_lines_and_view_in_one_sync(self):
        out = self.run_relay([
            sync("a", [{"ev": "Stop", "sid": "s1"}], view=view(1, snap=[snapshot()])),
            sync("b"),
        ])
        self.assertEqual(len(out["responses"][1]["body"]["lines"]), 1, "the lines went through as before")
        self.assertEqual(len(self.rows(out)), 1)
        for line in out["responses"][1]["body"]["lines"]:
            self.assertNotIn("view", json.dumps(line), "a picture is never handed to other machines")


class TestCost(CloudRelayCase):
    def test_a_view_writes_at_most_one_row(self):
        out = self.run_relay([
            sync("a", view=view(1, snap=[snapshot()])),          # first sync also creates the tables
            sync("a", view=view(1, events=[tool("s:1")]), now=T0 + 5000),
            sync("a", view=view(1), now=T0 + 10000),
            sync("a", view=view(2, snap=[snapshot()]), now=T0 + 60000),
            sync("a", now=T0 + 65000),
        ])
        self.assertEqual([r["writes"] for r in out["responses"]], [1, 1, 1, 1, 0])

    def test_no_full_table_scan(self):
        out = self.run_relay([
            sync("a", [{"ev": "Stop", "sid": "s1"}], view=view(1, snap=[snapshot()])),
            sync("a", view=view(1, events=[tool("s:1")]), now=T0 + 5000),
            sync("b", view=view(1, snap=[snapshot()]), now=T0 + 6000),
            sync("a", view=view(2, snap=[snapshot()]), now=T0 + 2 * DAY),
        ])
        scans = [s for s in out["full_scans"] if "city_view" in s["sql"] and "CREATE" not in s["sql"]]
        self.assertEqual(scans, [], "every city_view statement goes through its key")

    def test_a_machine_not_seen_for_a_day_is_dropped_with_a_snap(self):
        out = self.run_relay([
            sync("old", view=view(1, snap=[snapshot()], label="old-mac")),
            sync("a", view=view(1, snap=[snapshot()]), now=T0 + DAY - 1000),
            sync("a", view=view(1, events=[tool("s:1")]), now=T0 + DAY + 1000),
        ])
        self.assertEqual(sorted(r["dev"] for r in self.rows(out)), ["a", "old"],
                         "a sync without a snap never cleans up")
        out = self.run_relay([
            sync("old", view=view(1, snap=[snapshot()], label="old-mac")),
            sync("a", view=view(1, snap=[snapshot()]), now=T0 + DAY + 1000),
        ])
        self.assertEqual([r["dev"] for r in self.rows(out)], ["a"])


class TestBadView(CloudRelayCase):
    def bad(self, v, status=400):
        out = self.run_relay([sync("a", [{"ev": "Stop", "sid": "s1"}], view=v), sync("b")])
        self.assertEqual(out["responses"][0]["status"], status, v)
        self.assertIs(out["responses"][0]["body"]["ok"], False)
        self.assertEqual(self.rows(out), [])
        self.assertEqual(out["responses"][1]["body"]["lines"], [], "a refused sync stores no lines")

    def test_view_must_be_an_object(self):
        self.bad("picture")
        self.bad([1, 2])

    def test_label(self):
        self.bad(view(1, snap=[snapshot()], label=""))
        self.bad(view(1, snap=[snapshot()], label="x" * 65))
        v = view(1, snap=[snapshot()])
        del v["label"]
        self.bad(v)

    def test_gen(self):
        for gen in (0, -1, 1.5, "1", None):
            self.bad(view(gen, snap=[snapshot()]))

    def test_counts(self):
        self.bad(view(1, counts={"people": 1, "busy": 1}))
        self.bad(view(1, counts={"people": 1, "busy": -1, "wait": 0}))
        self.bad(view(1, counts="3"))

    def test_snap_and_events_are_lists_of_objects(self):
        self.bad(view(1, snap={"type": "snapshot"}))
        self.bad(view(1, snap=["x"]))
        self.bad(view(1, snap=[snapshot()], events=[1]))

    def test_too_many_events(self):
        self.bad(view(1, snap=[snapshot()], events=[tool("s:1")] * 501), status=413)


class TestNoLeak(CloudRelayCase):
    def test_wrong_key_stores_nothing(self):
        out = self.run_relay([sync("a", view=view(1, snap=[snapshot()]), key="wrong")])
        self.assertEqual(out["responses"][0]["status"], 401)
        self.assertEqual(self.rows(out), [])

    def test_key_and_mail_are_never_echoed(self):
        out = self.run_relay([
            sync("a", view=view(1, snap=[snapshot()])),
            sync("a", view="bad"),
            {"to": "relay", "method": "GET", "path": "/", "now": T0},
        ])
        text = json.dumps([r["body"] for r in out["responses"]])
        self.assertNotIn(KEY, text)
        self.assertNotIn(ME, text)
        self.assertEqual(out["responses"][2]["body"], {"ok": True, "relay": "agent-city", "v": 1},
                         "GET / is as before")


if __name__ == "__main__":
    unittest.main()
