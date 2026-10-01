"""Failing test, cloud-city-1 slice 6 (C7): what one working day costs on
Cloudflare's free plan, measured on the real Worker code (tests/cloud_harness.mjs).

Free plan, per day: 100,000 Worker requests (both Workers together), D1
100,000 rows written and 5,000,000 rows read; D1 storage 5 GB.

The day (DAY below; change it and run this file to see another day):
    3 machines, each city server up 12 h (a sync every 5 s, lines or not),
    6 of those hours busy: lines in every sync, a view with events in every
    sync, a new picture every minute; the other 6 h quiet: a sign of life a
    minute. The cloud page open 8 h, a feed request every 3 s.

Measured per request: D1 rows written (changed rows) and rows read (rows
handed back). Real D1 also counts one more written row per index a statement
touches, and a deleted row is a written row too. A batch of lines (the relay
of before: table relay_batch, one index on ts, deleted after 300 s) so costs
4 written rows: insert 2, delete 2. A view costs 1 (its row is written in
place; a new picture replaces the row). The numbers are an estimate; the test
keeps this heavy day under 80% of every free limit. Most of the written rows
are the relay's lines, as before the cloud page: the view adds a quarter.

cloud-city-2 (talk), the same day with talk on on every machine: 600 session
turns (each one prompt and one reply: two chat rows up, with a busy sync) and
100 messages typed on the cloud page (each: one send request, one row; the
machine picks it up; one early sync says queued and brings its chat row; one
early sync says delivered and changes that row), a window open on the page all
day. A talk row is counted three times (its table has two indexes). Talk must
stay small: under 10% of the free rows, and no new request but the sends and
the early syncs. A talk sync with nothing to carry writes nothing; a poll of an
open window writes nothing.

cloud-city-3 (start), the same day with starting on on every machine: 20
agents started from the cloud page (each: one add request, one row; the
machine takes it; one early sync says opening, one says opened), and every
machine keeps its server up the OTHER 12 hours of the day with nobody there
(a sync every 15 s, a sign of life a minute). An order row is counted twice
(its table has one index). A start sync with nothing to carry writes nothing;
a poll that lists orders writes nothing. Starting must stay small: under 5%
of the free rows and under 10% of the free requests.

The numbers this file prints are the ones requirements/city.md ("Cloud page",
the cost line) and skills/city/setup.md (its last line) must say.

    python3 tests/test_agent_city_cloud_cost.py     prints the numbers

Run: python3 -m unittest tests.test_agent_city_cloud_cost
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
from cloudhelp import T0, TALK, TALK_ENV, TERR, add, feed, person, send, snapshot, sync, tool, view  # noqa: E402

ROOT = os.path.dirname(HERE)
REQ = os.path.join(ROOT, "requirements", "city.md")
SETUP = os.path.join(ROOT, "skills", "city", "setup.md")

FREE = {"requests": 100_000, "rows_written": 100_000, "rows_read": 5_000_000}
DAY = {"machines": 3, "up_hours": 12, "busy_hours": 6, "page_hours": 8,
       "sync_sec": 5, "snap_sec": 60, "poll_sec": 3, "people": 6, "events_per_sync": 8,
       "turns": 600, "cloud_msgs": 100,
       "orders": 20, "idle_hours": 12, "slow_sec": 15}
TALK_ROW_FACTOR = 3     # a talk row and its two index entries
ORDER_ROW_FACTOR = 2    # an order row and its one index entry


def sample(case):
    """One of each kind of request, on a store that already holds three machines."""
    people = [person("s:%d" % i, "session %d" % i) for i in range(DAY["people"])]
    snap = [snapshot(*people)]
    events = [tool("s:1")] * DAY["events_per_sync"]
    lines = [{"ev": "PostToolUse", "sid": "s1", "tool": "Bash", "rid": "github.com/o/r"}] * DAY["events_per_sync"]
    warm = []
    for i, dev in enumerate(("mac", "pc2", "cloud")):
        warm.append(sync(dev, lines, view=view(1, snap=snap, label=dev), now=T0 + i, talk_key=TALK))
    cid = "cid-cost-00000000001"
    turn = [{"k": "p1", "to": "s:1", "kind": "prompt", "text": "x" * 200, "at": 100.0},
            {"k": "r1", "to": "s:1", "kind": "reply", "text": "y" * 2000, "at": 130.0}]
    mine = {"k": cid, "to": "s:1", "kind": "owner", "text": "z" * 80, "at": 140.0, "state": "queued", "cid": cid}
    t = T0 + 130000
    u = t + 40000
    oid = "oid-cost-00000000001"
    opening = {"oid": oid, "state": "opening", "info": {"name": "shop Manager", "role": "main"}}
    reqs = warm + [
        sync("mac", lines, view=view(1, events=events), now=T0 + 5000),      # busy sync
        sync("mac", lines, view=view(2, snap=snap), now=T0 + 60000),         # busy sync with a new picture
        sync("mac", now=T0 + 65000),                                         # quiet sync
        sync("mac", view=view(2), now=T0 + 120000),                          # quiet sync, sign of life
        feed(dev="mac", gen=2, after=0, now=T0 + 121000),                    # a poll, nothing new
        feed(now=T0 + 122000),                                               # a first load
        # cloud-city-2: talk
        sync("mac", view=view(2), now=t, talk_key=TALK),                                           # the flag goes up
        sync("mac", lines, view=view(2, events=events), now=t + 5000, talk_key=TALK, talk={"chat": turn}),   # a turn
        sync("mac", now=t + 10000, talk_key=TALK),                                                 # a quiet talk sync
        send(dev="mac", to="s:1", text="z" * 80, cid=cid, now=t + 11000),                          # the owner types
        sync("mac", now=t + 15000, talk_key=TALK),                                                 # picked up
        sync("mac", now=t + 16000, talk_key=TALK, talk={"acks": [{"cid": cid, "state": "queued"}], "chat": [mine]}),
        sync("mac", now=t + 30000, talk_key=TALK,
             talk={"acks": [{"cid": cid, "state": "delivered"}], "chat": [dict(mine, state="delivered")]}),
        feed(dev="mac", gen=2, after=1, chat="s:1", cc=99, now=t + 31000),                         # a poll, a window open
        # cloud-city-3: start
        sync("mac", view=view(2), now=u, talk_key=TALK, talk={"start": {}}),                       # the start flag goes up
        sync("mac", now=u + 5000, talk_key=TALK, talk={"start": {}}),                              # a quiet start sync
        add(dev="mac", terr=TERR, oid=oid, now=u + 6000),                                          # the owner clicks
        sync("mac", now=u + 10000, talk_key=TALK, talk={"start": {}}),                             # taken
        sync("mac", now=u + 11000, talk_key=TALK, talk={"start": {"acks": [dict(opening)]}}),      # the terminal opens
        sync("mac", now=u + 20000, talk_key=TALK, talk={"start": {"acks": [dict(opening, state="opened")]}}),
        feed(dev="mac", gen=2, after=1, now=u + 21000),                                            # a poll that lists the order
    ]
    out = ch.run_cloud(case, reqs, relay_env=TALK_ENV)
    names = ["busy", "busy_snap", "quiet", "life", "poll", "load",
             "flag", "turn", "quiet_talk", "send", "take", "queued", "done", "poll_chat",
             "start_flag", "quiet_start", "order", "take_order", "opening", "opened", "poll_orders"]
    got = {}
    for name, r in zip(names, out["responses"][len(warm):]):
        case.assertEqual(r["status"], 200, (name, r))
        got[name] = {"writes": r["writes"], "reads": r["reads"]}
    got["bytes"] = sum(len(json.dumps(row)) for rows in out["dump"].values() for row in rows)
    return got


def day_cost(s):
    d = DAY
    per_h = 3600 // d["sync_sec"]
    busy = d["busy_hours"] * per_h
    quiet = (d["up_hours"] - d["busy_hours"]) * per_h
    snaps = d["busy_hours"] * 3600 // d["snap_sec"]
    lives = (d["up_hours"] - d["busy_hours"]) * 60
    polls = d["page_hours"] * 3600 // d["poll_sec"]
    m = d["machines"]
    # rows written, with the index and delete factor (see the docstring)
    view_w = 1
    line_w = (s["busy"]["writes"] - view_w) * 4     # the relay_batch part of a busy sync
    w = m * (busy * (line_w + view_w) + snaps * s["busy_snap"]["writes"] * 0 + lives * s["life"]["writes"])
    r = m * (busy * s["busy"]["reads"] + quiet * s["quiet"]["reads"]) + polls * s["poll"]["reads"]
    # cloud-city-2: talk. A turn's chat rows ride a busy sync (what that sync writes beyond a busy
    # sync of before); a message = the send, the pick-up and two early syncs.
    turn_w = max(0, s["turn"]["writes"] - s["busy"]["writes"])
    msg_w = s["send"]["writes"] + s["take"]["writes"] + s["queued"]["writes"] + s["done"]["writes"]
    talk_w = TALK_ROW_FACTOR * (d["turns"] * turn_w + d["cloud_msgs"] * msg_w)
    talk_req = d["cloud_msgs"] * 3
    r += polls * max(0, s["poll_chat"]["reads"] - s["poll"]["reads"]) + d["cloud_msgs"] * 20
    # cloud-city-3: start. An order = the add, the pick-up and two early syncs. A machine with starting on
    # stays up with nobody there: a slow sync, and a sign of life a minute.
    order_w = ORDER_ROW_FACTOR * d["orders"] * (s["order"]["writes"] + s["take_order"]["writes"]
                                                + s["opening"]["writes"] + s["opened"]["writes"])
    idle = d["idle_hours"] * 3600 // d["slow_sec"]
    idle_lives = d["idle_hours"] * 60
    start_w = order_w + m * idle_lives * s["life"]["writes"]
    start_req = d["orders"] * 3 + m * idle
    r += m * idle * s["quiet_start"]["reads"] + polls * max(0, s["poll_orders"]["reads"] - s["poll"]["reads"])
    return {"requests": m * (busy + quiet) + polls + talk_req + start_req,
            "rows_written": w + talk_w + start_w, "rows_read": r, "stored_bytes": s["bytes"],
            "rows_written_by_lines": m * busy * line_w, "rows_written_by_views": m * (busy * view_w + lives),
            "rows_written_by_talk": talk_w, "requests_by_talk": talk_req,
            "rows_written_by_start": start_w, "requests_by_start": start_req}


@unittest.skipUnless(NODE, SKIP_REASON)
class TestCost(unittest.TestCase):
    def test_a_heavy_working_day_fits_the_free_plan(self):
        cost = day_cost(sample(self))
        for key, limit in FREE.items():
            self.assertLess(cost[key], limit * 0.8, "%s: %d of %d a day" % (key, cost[key], limit))
        self.assertLess(cost["rows_written_by_views"], cost["rows_written_by_lines"] / 2,
                        "the cloud page must stay the small part of the written rows")
        self.assertLess(cost["stored_bytes"], 5 * 1024 * 1024, "D1 holds megabytes at most, of 5 GB")

    def test_a_poll_is_cheap(self):
        s = sample(self)
        self.assertEqual(s["poll"]["writes"], 0)
        self.assertLessEqual(s["poll"]["reads"], 4)
        self.assertLessEqual(s["life"]["writes"], 1)
        self.assertEqual(s["quiet"]["writes"], 0, "a quiet sync writes nothing, as before")

    def test_talk_stays_small(self):
        s = sample(self)
        self.assertEqual(s["quiet_talk"]["writes"], 0, "a talk sync with nothing to carry writes nothing")
        self.assertEqual(s["poll_chat"]["writes"], 0, "a poll of an open window writes nothing")
        self.assertLessEqual(s["poll_chat"]["reads"], 6)
        self.assertEqual(s["turn"]["writes"] - s["busy"]["writes"], 2, "a turn = two chat rows, nothing more")
        self.assertEqual(s["send"]["writes"], 1, "a message = one row")
        self.assertLessEqual(s["take"]["writes"], 1)
        self.assertLessEqual(s["queued"]["writes"], 2, "the answer and the chat row")
        self.assertLessEqual(s["done"]["writes"], 3, "the answer and the changed chat row")
        cost = day_cost(s)
        self.assertLess(cost["rows_written_by_talk"], FREE["rows_written"] * 0.10,
                        "talk: %d rows a day" % cost["rows_written_by_talk"])
        self.assertLessEqual(cost["requests_by_talk"], DAY["cloud_msgs"] * 3)

    def test_start_stays_small(self):
        s = sample(self)
        self.assertEqual(s["quiet_start"]["writes"], 0, "a start sync with nothing to carry writes nothing")
        self.assertEqual(s["poll_orders"]["writes"], 0, "a poll that lists an order writes nothing")
        self.assertLessEqual(s["poll_orders"]["reads"], 6)
        self.assertEqual(s["order"]["writes"], 1, "an order = one row")
        self.assertLessEqual(s["take_order"]["writes"], 1)
        self.assertLessEqual(s["opening"]["writes"], 1)
        self.assertLessEqual(s["opened"]["writes"], 1)
        cost = day_cost(s)
        self.assertLess(cost["rows_written_by_start"], FREE["rows_written"] * 0.05,
                        "start: %d rows a day" % cost["rows_written_by_start"])
        self.assertLess(cost["requests_by_start"], FREE["requests"] * 0.10,
                        "start: %d requests a day" % cost["requests_by_start"])

    def numbers(self, text, pattern):
        m = re.search(pattern, text)
        self.assertTrue(m, "the cost line was not found: %s" % pattern)
        return [int(x.replace(",", "")) for x in m.groups()]

    def test_the_requirement_says_these_numbers(self):
        cost = day_cost(sample(self))
        with open(REQ, encoding="utf-8") as fh:
            req = fh.read()
        got = self.numbers(req, r"is about ([\d,]+) requests \((\d+)%\) and about ([\d,]+) rows written \((\d+)%\)")
        self.assertAlmostEqual(got[0], cost["requests"], delta=300, msg="requests a day: %d" % cost["requests"])
        self.assertEqual(got[1], round(100 * cost["requests"] / FREE["requests"]))
        self.assertAlmostEqual(got[2], cost["rows_written"], delta=300, msg="rows a day: %d" % cost["rows_written"])
        self.assertEqual(got[3], round(100 * cost["rows_written"] / FREE["rows_written"]))
        talk = self.numbers(req, r"talk adds about ([\d,]+)")
        self.assertAlmostEqual(talk[0], cost["rows_written_by_talk"], delta=300,
                               msg="talk rows a day: %d" % cost["rows_written_by_talk"])
        start = self.numbers(req, r"starting adds about ([\d,]+) requests and about ([\d,]+) rows")
        self.assertAlmostEqual(start[0], cost["requests_by_start"], delta=300,
                               msg="start requests a day: %d" % cost["requests_by_start"])
        self.assertAlmostEqual(start[1], cost["rows_written_by_start"], delta=300,
                               msg="start rows a day: %d" % cost["rows_written_by_start"])

    def test_the_setup_steps_say_these_numbers(self):
        cost = day_cost(sample(self))
        with open(SETUP, encoding="utf-8") as fh:
            text = fh.read()
        got = self.numbers(text, r"uses about ([\d,]+) requests and about ([\d,]+) written rows")
        self.assertAlmostEqual(got[0], cost["requests"], delta=600)
        self.assertAlmostEqual(got[1], cost["rows_written"], delta=600)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "-m":
        unittest.main()
    else:
        class _Case(unittest.TestCase):
            def runTest(self):
                pass
        s = sample(_Case())
        cost = day_cost(s)
        print("per request:", json.dumps(s))
        for key, limit in FREE.items():
            print("%-13s %7d of %9d a day (%.0f%%)" % (key, cost[key], limit, 100.0 * cost[key] / limit))
        print("stored        %d bytes of 5 GB" % cost["stored_bytes"])
        print("rows written: %d by lines (the relay of before), %d by views (the cloud page), %d by talk"
              % (cost["rows_written_by_lines"], cost["rows_written_by_views"], cost["rows_written_by_talk"]))
        print("requests: %d of them by talk (sends and early syncs)" % cost["requests_by_talk"])
        print("start: %d requests (orders, early syncs, the idle hours at 15 s) and %d rows (orders, signs of life)"
              % (cost["requests_by_start"], cost["rows_written_by_start"]))
