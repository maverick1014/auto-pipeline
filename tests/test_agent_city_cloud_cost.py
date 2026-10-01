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

    python3 tests/test_agent_city_cloud_cost.py     prints the numbers

Run: python3 -m unittest tests.test_agent_city_cloud_cost
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
from cloudhelp import T0, feed, person, snapshot, sync, tool, view  # noqa: E402

FREE = {"requests": 100_000, "rows_written": 100_000, "rows_read": 5_000_000}
DAY = {"machines": 3, "up_hours": 12, "busy_hours": 6, "page_hours": 8,
       "sync_sec": 5, "snap_sec": 60, "poll_sec": 3, "people": 6, "events_per_sync": 8}


def sample(case):
    """One of each kind of request, on a store that already holds three machines."""
    people = [person("s:%d" % i, "session %d" % i) for i in range(DAY["people"])]
    snap = [snapshot(*people)]
    events = [tool("s:1")] * DAY["events_per_sync"]
    lines = [{"ev": "PostToolUse", "sid": "s1", "tool": "Bash", "rid": "github.com/o/r"}] * DAY["events_per_sync"]
    warm = []
    for i, dev in enumerate(("mac", "pc2", "cloud")):
        warm.append(sync(dev, lines, view=view(1, snap=snap, label=dev), now=T0 + i))
    reqs = warm + [
        sync("mac", lines, view=view(1, events=events), now=T0 + 5000),      # busy sync
        sync("mac", lines, view=view(2, snap=snap), now=T0 + 60000),         # busy sync with a new picture
        sync("mac", now=T0 + 65000),                                         # quiet sync
        sync("mac", view=view(2), now=T0 + 120000),                          # quiet sync, sign of life
        feed(dev="mac", gen=2, after=0, now=T0 + 121000),                    # a poll, nothing new
        feed(now=T0 + 122000),                                               # a first load
    ]
    out = ch.run_cloud(case, reqs)
    names = ["busy", "busy_snap", "quiet", "life", "poll", "load"]
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
    return {"requests": m * (busy + quiet) + polls,
            "rows_written": w, "rows_read": r, "stored_bytes": s["bytes"],
            "rows_written_by_lines": m * busy * line_w, "rows_written_by_views": m * (busy * view_w + lives)}


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
        print("rows written: %d by lines (the relay of before), %d by views (the cloud page)"
              % (cost["rows_written_by_lines"], cost["rows_written_by_views"]))
