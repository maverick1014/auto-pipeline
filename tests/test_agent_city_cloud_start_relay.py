"""Failing tests, cloud-city-3 slice W1: the relay Worker carries start orders
(requirements/city.md, "Cloud page", "Start"; approved design D1-D16 in
agent_state.txt and in commit 9c8479d; mock mock/cloud-city-3-mock.html).

bin/agent-city-relay.js. Everything of before stays: a sync whose talk has no
"start" key is answered exactly as today (cloud-city-2), and nothing below
happens for it. No new secret: start rides the talk of a talk-on sync (the
right X-City-Talk key), and no third path is built.

  A machine with starting on adds to the talk of its usual sync:
      "talk": {..., "start": {"acks": [...]}}        (acks optional; {} is fine)
   or "talk": {..., "start": {"off": true}}          (starting turned off there)

  The reply's talk, for a talk-on sync:
      no "start" key in talk (or it is not an object) -> exactly the talk of
          before, {"state": "on", "msgs": [...]}: no "start" key, and no order
          table is made, read or changed
      "start": {...}             -> talk gains "start": {"state": "on", "orders": [...]}
      "start": {"off": true}     -> talk gains "start": {"state": "off"} (after the clean-up below)
  A sync that is not talk-on (no header, a wrong key, no TALK_KEY, no
  CITY_USER), or a talk {"off": true}: body.talk.start is never read.
  The team key alone can never take an order, answer for one or set the flag.

  Table (made on a start sync, these exact lines: the City Worker makes the
  same ones, see tests/cloudhelp.py START_TABLES):
      city_order (user, oid, dev, terr, force, at, ts, state, why, info)   PRIMARY KEY (user, oid)
          one click on the cloud page's add-agent button. ONLY the City
          Worker inserts a row; the relay has no statement that inserts into
          city_order. at = placed (ms), ts = last change of state (ms).
      index city_order_dev ON city_order (user, dev, state)

  States of a row: sent -> taken -> opening -> opened | cap | failed (why).
  opened, cap and failed are final.

  ORDER inside one start sync: the acks first, then DOWN.

  ACKS, start.acks = [{"oid", "state", "why", "info"}], the first 20 are read:
      state 'opening' | 'opened' | 'cap' | 'failed'; anything else is skipped
      (so a machine can never put a row back to 'sent' or 'taken').
      Only a row of THIS user and THIS dev in state 'taken' or 'opening'
      changes, and only when the answer says something new; ts = now then.
      why is kept only when it is one of: no-orca, gone, orca, late, busy,
      flood, restart, refused, off; else ''.
      info: an object; only these keys are kept, anything else is dropped:
      name (a string, cut at 80 characters), role ('main' | 'helper'), ram,
      cpu, max (whole numbers), detail (a string, cut at 200 characters). It
      is stored as JSON text ("{}" when nothing is kept or it is no object).
      A bad ack is skipped, the others are kept, the sync stays ok.

  DOWN, on a start sync of machine DEV (user = CITY_USER), in this order:
      1. a 'sent' row of DEV with now - at >= 60000      -> 'failed', why 'off'
         a 'taken' or 'opening' row of DEV with now - ts >= 180000 -> 'failed', why 'silent'
         (both set ts = now)
      2. the oldest 'sent' rows of DEV become 'taken' (ts = now), so that at
         most 3 rows of DEV are 'taken' at once
      3. "orders" = the 'taken' rows of DEV, oldest first, at most 3:
         {"oid", "terr", "force" (true | false), "age" (ms since the row's at)}
         and nothing else. A taken row is handed down again on every start
         sync until the machine answers for it.
      Each change of state is one guarded UPDATE, so a row that became
      'failed' is never handed down later. Rows of another machine or another
      user are never read or changed.

  FLAG: a view stored by a start sync (not off) gets "start": 1 in its counts
      (next to "talk": 1); a view stored by any other sync has no start. A
      "start" the machine puts in its own counts is never copied.

  OFF, start {"off": true}: this dev's city_order rows in 'sent' or 'taken'
      become 'failed' / 'start-off' (an 'opening' row is left: its terminal
      is opening), and its city_view counts lose the start flag. A second off
      writes nothing. Talk stays on.

  COST: a start sync with nothing waiting and no acks writes no row. A full
      one (8 lines, a view with events, 20 chat rows, 10 chat acks, 10
      messages down, 3 order acks, 3 orders down) runs at most 40 statements
      (the free plan allows 50 per request), and no statement reads the whole
      order table.

No test talks to Cloudflare. Run: python3 -m unittest tests.test_agent_city_cloud_start_relay
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
from cloudhelp import (KEY, ME, OTHER, T0, TALK, TALK_ENV, TERR, lay_msg, lay_order, make_order_table,  # noqa: E402
                       make_tables, snapshot, sql, sync, view)

ORDERS = "SELECT oid, dev, state, why, info, ts FROM city_order ORDER BY oid"
COUNTS = "SELECT dev, counts FROM city_view ORDER BY dev"


def ssync(dev="mac", start=None, now=T0, talk=None, **kw):
    """A talk-on sync that carries start (START None = {})."""
    kw.setdefault("talk_key", TALK)
    body = dict(talk or {})
    body["start"] = {} if start is None else start
    return sync(dev, talk=body, now=now, **kw)


def tsync(dev="mac", talk=None, now=T0, **kw):
    """A talk-on sync WITHOUT start."""
    kw.setdefault("talk_key", TALK)
    return sync(dev, talk=talk, now=now, **kw)


def oid(n):
    return "oid-%016d" % n


@unittest.skipUnless(NODE, SKIP_REASON)
class RelayCase(unittest.TestCase):
    def run_relay(self, reqs, env=None, tables=True):
        head = (make_tables() + make_order_table()) if tables else []
        out = ch.run_cloud(self, head + list(reqs), relay_env=TALK_ENV if env is None else env, city="-")
        out["responses"] = out["responses"][len(head):]
        return out

    def bodies(self, out):
        for r in out["responses"]:
            self.assertEqual(r["status"], 200, r)
        return [r["body"] for r in out["responses"]]

    def rows(self, out, index=-1):
        return {r["oid"]: r for r in out["responses"][index]["body"]}


class TestStartRidesTalk(RelayCase):
    def test_talk_without_start_is_the_talk_of_before(self):
        out = self.run_relay([lay_order(oid(1)), tsync(), tsync(talk={"acks": []}), sql(ORDERS)])
        b = self.bodies(out)
        self.assertEqual(b[1]["talk"], {"state": "on", "msgs": []})
        self.assertEqual(b[2]["talk"], {"state": "on", "msgs": []})
        self.assertEqual(self.rows(out)[oid(1)]["state"], "sent", "no start in the talk: no order is taken")

    def test_no_order_table_is_made_without_start(self):
        out = self.run_relay([tsync()], tables=False)
        self.assertNotIn("city_order", out["dump"])

    def test_start_is_answered_and_makes_the_table(self):
        out = self.run_relay([ssync(), sql("SELECT name, sql FROM sqlite_master WHERE name LIKE 'city_order%' ORDER BY name")],
                             tables=False)
        self.assertEqual(self.bodies(out)[0]["talk"], {"state": "on", "msgs": [], "start": {"state": "on", "orders": []}})
        made = {r["name"]: " ".join(r["sql"].split()) for r in out["responses"][-1]["body"]}
        norm = lambda s: " ".join(s.replace("IF NOT EXISTS ", "").split())  # noqa: E731
        self.assertEqual(made.get("city_order"), norm(ch.ORDER_SQL))
        self.assertEqual(made.get("city_order_dev"), norm(ch.ORDER_INDEX_SQL))

    def test_the_source_holds_the_agreed_lines(self):
        with open(ch.RELAY, encoding="utf-8") as fh:
            src = " ".join(fh.read().split())
        for line in ch.START_TABLES:
            self.assertIn(" ".join(line.split()), src, "this exact line is missing: %s" % line[:60])

    def test_the_relay_never_makes_an_order(self):
        with open(ch.RELAY, encoding="utf-8") as fh:
            src = fh.read()
        self.assertEqual(re.findall(r"(?is)\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+city_order", src), [],
                         "only the City Worker inserts into city_order")

    def test_without_the_talk_key_start_is_never_read(self):
        take = [lay_order(oid(1))]
        for req in (sync("mac", talk={"start": {}}),                                   # no header: the team key alone
                    sync("mac", talk={"start": {}}, talk_key=KEY),                     # the team key as a talk key
                    sync("mac", talk={"start": {}}, talk_key="wrong-key-wrong-key-0000")):
            out = self.run_relay(take + [req, sql(ORDERS)])
            body = out["responses"][1]["body"]
            self.assertNotIn("start", body.get("talk") or {}, body)
            self.assertNotIn("orders", json.dumps(body))
            self.assertEqual(self.rows(out)[oid(1)]["state"], "sent")

    def test_no_talk_key_on_the_relay_no_start(self):
        out = self.run_relay([lay_order(oid(1)), ssync(), sql(ORDERS)], env=ch.RELAY_ENV)
        self.assertEqual(out["responses"][1]["body"]["talk"], {"state": "off"})
        self.assertEqual(self.rows(out)[oid(1)]["state"], "sent")

    def test_talk_off_does_not_read_start(self):
        out = self.run_relay([lay_order(oid(1)), tsync(talk={"off": True, "start": {}}), sql(ORDERS)])
        self.assertEqual(out["responses"][1]["body"]["talk"], {"state": "off"})
        self.assertEqual(self.rows(out)[oid(1)]["state"], "sent")

    def test_a_start_that_is_not_an_object_is_no_start(self):
        for bad in (True, "on", 1, [1], None):
            out = self.run_relay([lay_order(oid(1)), tsync(talk={"start": bad}), sql(ORDERS)])
            self.assertEqual(out["responses"][1]["body"]["talk"], {"state": "on", "msgs": []}, bad)
            self.assertEqual(self.rows(out)[oid(1)]["state"], "sent")


class TestDown(RelayCase):
    def test_an_order_is_taken_and_handed_down(self):
        out = self.run_relay([lay_order(oid(1), at=T0, force=0), ssync(now=T0 + 4000), sql(ORDERS)])
        orders = self.bodies(out)[1]["talk"]["start"]["orders"]
        self.assertEqual(orders, [{"oid": oid(1), "terr": TERR, "force": False, "age": 4000}])
        row = self.rows(out)[oid(1)]
        self.assertEqual((row["state"], row["ts"]), ("taken", T0 + 4000))

    def test_force_is_a_bool(self):
        out = self.run_relay([lay_order(oid(1), force=1), ssync(now=T0 + 1000)])
        self.assertIs(out["responses"][1]["body"]["talk"]["start"]["orders"][0]["force"], True)

    def test_only_these_four_fields_go_down(self):
        out = self.run_relay([lay_order(oid(1), info='{"name": "x"}', why="orca"), ssync(now=T0 + 1000)])
        order = out["responses"][1]["body"]["talk"]["start"]["orders"][0]
        self.assertEqual(set(order), {"oid", "terr", "force", "age"})

    def test_handed_down_again_until_answered(self):
        out = self.run_relay([lay_order(oid(1)), ssync(now=T0 + 1000), ssync(now=T0 + 6000),
                              ssync(now=T0 + 11000, start={"acks": [{"oid": oid(1), "state": "opening",
                                                                     "info": {"name": "shop Manager", "role": "main"}}]}),
                              ssync(now=T0 + 16000), sql(ORDERS)])
        b = self.bodies(out)
        self.assertEqual([o["oid"] for o in b[1]["talk"]["start"]["orders"]], [oid(1)])
        self.assertEqual([(o["oid"], o["age"]) for o in b[2]["talk"]["start"]["orders"]], [(oid(1), 6000)])
        self.assertEqual(b[3]["talk"]["start"]["orders"], [], "answered: not handed down again")
        self.assertEqual(b[4]["talk"]["start"]["orders"], [])
        self.assertEqual(self.rows(out)[oid(1)]["state"], "opening")

    def test_three_at_once_the_rest_wait(self):
        lay = [lay_order(oid(i), terr="0000000%d" % i, at=T0 + i) for i in range(1, 6)]
        out = self.run_relay(lay + [ssync(now=T0 + 1000), sql(ORDERS),
                                    ssync(now=T0 + 2000, start={"acks": [{"oid": oid(1), "state": "failed", "why": "gone"}]}),
                                    sql(ORDERS)])
        b = out["responses"]
        self.assertEqual([o["oid"] for o in b[5]["body"]["talk"]["start"]["orders"]], [oid(1), oid(2), oid(3)])
        self.assertEqual([r["state"] for r in b[6]["body"]], ["taken"] * 3 + ["sent"] * 2)
        self.assertEqual([o["oid"] for o in b[7]["body"]["talk"]["start"]["orders"]], [oid(2), oid(3), oid(4)],
                         "one was answered: the next oldest is taken")
        self.assertEqual([r["state"] for r in b[8]["body"]], ["failed", "taken", "taken", "taken", "sent"])

    def test_not_taken_in_sixty_seconds_is_never_handed_down(self):
        out = self.run_relay([lay_order(oid(1), at=T0), ssync(now=T0 + 60000), ssync(now=T0 + 400000), sql(ORDERS)])
        b = self.bodies(out)
        self.assertEqual(b[1]["talk"]["start"]["orders"], [])
        self.assertEqual(b[2]["talk"]["start"]["orders"], [], "the machine is back much later: the order stays dead")
        row = self.rows(out)[oid(1)]
        self.assertEqual((row["state"], row["why"]), ("failed", "off"))

    def test_just_in_time_is_taken(self):
        out = self.run_relay([lay_order(oid(1), at=T0), ssync(now=T0 + 59000)])
        self.assertEqual([o["oid"] for o in out["responses"][1]["body"]["talk"]["start"]["orders"]], [oid(1)])

    def test_taken_or_opening_with_no_word_for_three_minutes_is_silent(self):
        lay = [lay_order(oid(1), state="taken", at=T0, ts=T0 + 1000),
               lay_order(oid(2), state="opening", at=T0, ts=T0 + 2000, terr="00000002"),
               lay_order(oid(3), state="opening", at=T0, ts=T0 + 100000, terr="00000003")]
        out = self.run_relay(lay + [ssync(now=T0 + 182000), sql(ORDERS)])
        rows = self.rows(out)
        self.assertEqual([(rows[oid(i)]["state"], rows[oid(i)]["why"]) for i in (1, 2, 3)],
                         [("failed", "silent"), ("failed", "silent"), ("opening", "")])
        self.assertEqual(out["responses"][3]["body"]["talk"]["start"]["orders"], [])

    def test_another_machine_and_another_user_are_left_alone(self):
        lay = [lay_order(oid(1), dev="pc2"), lay_order(oid(2), user=OTHER), lay_order(oid(3))]
        out = self.run_relay(lay + [ssync("mac", now=T0 + 1000), sql(ORDERS)])
        self.assertEqual([o["oid"] for o in out["responses"][3]["body"]["talk"]["start"]["orders"]], [oid(3)])
        rows = self.rows(out)
        self.assertEqual((rows[oid(1)]["state"], rows[oid(2)]["state"]), ("sent", "sent"))


class TestAcks(RelayCase):
    def taken(self, n=1, **kw):
        return lay_order(oid(n), state="taken", ts=T0, **kw)

    def ack(self, reqs, acks, now=T0 + 5000):
        out = self.run_relay(list(reqs) + [ssync(now=now, start={"acks": acks}), sql(ORDERS)])
        self.assertEqual(out["responses"][-2]["status"], 200, out["responses"][-2])
        return out

    def test_opening_then_opened(self):
        info = {"name": "shop Manager", "role": "main"}
        out = self.ack([self.taken()], [{"oid": oid(1), "state": "opening", "info": info}])
        row = self.rows(out)[oid(1)]
        self.assertEqual((row["state"], row["why"], json.loads(row["info"]), row["ts"]), ("opening", "", info, T0 + 5000))
        out = self.run_relay([self.taken(),
                              ssync(now=T0 + 5000, start={"acks": [{"oid": oid(1), "state": "opening", "info": info}]}),
                              ssync(now=T0 + 9000, start={"acks": [{"oid": oid(1), "state": "opened", "info": info}]}),
                              sql(ORDERS)])
        row = self.rows(out)[oid(1)]
        self.assertEqual((row["state"], row["ts"]), ("opened", T0 + 9000))

    def test_cap_carries_the_numbers(self):
        out = self.ack([self.taken()], [{"oid": oid(1), "state": "cap", "info": {"ram": 86, "cpu": 41, "max": 80}}])
        row = self.rows(out)[oid(1)]
        self.assertEqual((row["state"], json.loads(row["info"])), ("cap", {"ram": 86, "cpu": 41, "max": 80}))

    def test_failed_keeps_a_known_reason_only(self):
        for why in ("no-orca", "gone", "orca", "late", "busy", "flood", "restart", "refused", "off"):
            out = self.ack([self.taken()], [{"oid": oid(1), "state": "failed", "why": why}])
            row = self.rows(out)[oid(1)]
            self.assertEqual((row["state"], row["why"]), ("failed", why))
        for why in ("silent", "start-off", "<b>x</b>", "rm -rf", 7, None):
            out = self.ack([self.taken()], [{"oid": oid(1), "state": "failed", "why": why}])
            row = self.rows(out)[oid(1)]
            self.assertEqual((row["state"], row["why"]), ("failed", ""), why)

    def test_final_states_never_change(self):
        for final in ("opened", "cap", "failed"):
            out = self.ack([lay_order(oid(1), state=final, why="gone" if final == "failed" else "", ts=T0)],
                           [{"oid": oid(1), "state": "opening"}, {"oid": oid(1), "state": "opened"},
                            {"oid": oid(1), "state": "failed", "why": "late"}])
            row = self.rows(out)[oid(1)]
            self.assertEqual((row["state"], row["ts"]), (final, T0), final)

    def test_a_sent_row_cannot_be_answered(self):
        out = self.ack([lay_order(oid(1), at=T0 + 4990)], [{"oid": oid(1), "state": "opened"}])
        self.assertEqual(self.rows(out)[oid(1)]["state"], "taken", "the ack came first and changed nothing; then it was taken")

    def test_a_machine_cannot_put_a_row_back(self):
        for state in ("sent", "taken", "", "delivered", "queued", None, 3):
            out = self.ack([lay_order(oid(1), state="opening", ts=T0)], [{"oid": oid(1), "state": state}])
            self.assertEqual(self.rows(out)[oid(1)]["state"], "opening", state)

    def test_another_machines_row_cannot_be_answered(self):
        out = self.ack([self.taken(dev="pc2"), lay_order(oid(2), state="taken", ts=T0, user=OTHER)],
                       [{"oid": oid(1), "state": "opened"}, {"oid": oid(2), "state": "opened"}])
        rows = self.rows(out)
        self.assertEqual((rows[oid(1)]["state"], rows[oid(2)]["state"]), ("taken", "taken"))

    def test_info_keeps_only_the_known_keys(self):
        info = {"name": "n" * 200, "role": "task-manager", "ram": 86, "cpu": "41", "max": 80.5, "detail": "d" * 500,
                "command": "claude --dangerously-skip-permissions", "folder": "/Users/owner/secret", "path": "/etc"}
        out = self.ack([self.taken()], [{"oid": oid(1), "state": "failed", "why": "orca", "info": info}])
        kept = json.loads(self.rows(out)[oid(1)]["info"])
        self.assertEqual(kept, {"name": "n" * 80, "ram": 86, "detail": "d" * 200})
        for bad in ("text", ["x"], 5, None):
            out = self.ack([self.taken()], [{"oid": oid(1), "state": "opening", "info": bad}])
            self.assertEqual(self.rows(out)[oid(1)]["info"], "{}", bad)

    def test_the_same_answer_again_writes_nothing(self):
        info = {"name": "shop Manager", "role": "main"}
        ack = {"oid": oid(1), "state": "opening", "info": info}
        out = self.run_relay([self.taken(), ssync(now=T0 + 5000, start={"acks": [ack]}),
                              ssync(now=T0 + 6000, start={"acks": [ack]}), sql(ORDERS)])
        self.assertEqual(out["responses"][2]["writes"], 0)
        self.assertEqual(self.rows(out)[oid(1)]["ts"], T0 + 5000)

    def test_a_bad_ack_is_skipped_and_the_rest_kept(self):
        acks = ["x", None, {"state": "opened"}, {"oid": 5, "state": "opened"}, {"oid": "x" * 70, "state": "opened"},
                {"oid": oid(1), "state": "opened"}]
        out = self.ack([self.taken()], acks)
        self.assertEqual(self.rows(out)[oid(1)]["state"], "opened")

    def test_only_the_first_twenty_acks_are_read(self):
        lay = [lay_order(oid(i), state="taken", ts=T0, terr="%08x" % i) for i in range(1, 26)]
        out = self.ack(lay, [{"oid": oid(i), "state": "opened"} for i in range(1, 26)])
        rows = self.rows(out)
        self.assertEqual(sum(1 for r in rows.values() if r["state"] == "opened"), 20)

    def test_acks_come_before_down(self):
        out = self.run_relay([self.taken(1), lay_order(oid(2), terr="00000002", at=T0 + 10),
                              ssync(now=T0 + 3000, start={"acks": [{"oid": oid(1), "state": "opening"}]})])
        self.assertEqual([o["oid"] for o in out["responses"][2]["body"]["talk"]["start"]["orders"]], [oid(2)])


class TestFlag(RelayCase):
    def counts(self, out, index=-1):
        return {r["dev"]: json.loads(r["counts"]) for r in out["responses"][index]["body"]}

    def test_a_start_sync_marks_its_view(self):
        v = view(1, snap=[snapshot()])
        out = self.run_relay([ssync("mac", view=v), tsync("pc2", view=view(1, snap=[snapshot()], label="pc2")),
                              sync("old", view=view(1, snap=[snapshot()], label="old")), sql(COUNTS)])
        got = self.counts(out)
        self.assertEqual((got["mac"].get("talk"), got["mac"].get("start")), (1, 1))
        self.assertEqual(got["pc2"].get("talk"), 1)
        self.assertFalse(got["pc2"].get("start"), "talk on, start off: two flags")
        self.assertFalse(got["old"].get("start"))

    def test_the_flag_goes_with_the_next_view_without_start(self):
        out = self.run_relay([ssync("mac", view=view(1, snap=[snapshot()])),
                              tsync("mac", view=view(1), now=T0 + 60000), sql(COUNTS)])
        got = self.counts(out)["mac"]
        self.assertEqual(got.get("talk"), 1)
        self.assertFalse(got.get("start"))

    def test_a_machine_cannot_set_the_flag_itself(self):
        v = view(1, snap=[snapshot()], counts={"people": 1, "busy": 1, "wait": 0, "start": 1})
        for req in (sync("mac", view=v), tsync("mac", view=v), sync("mac", view=v, talk={"start": {}}),
                    sync("mac", view=v, talk={"start": {}}, talk_key="wrong-key-wrong-key-00000")):
            out = self.run_relay([req, sql(COUNTS)])
            self.assertEqual(out["responses"][0]["status"], 200, out["responses"][0])
            self.assertFalse(self.counts(out)["mac"].get("start"))


class TestOff(RelayCase):
    def test_off_fails_what_waits_and_drops_the_flag(self):
        reqs = [ssync("mac", view=view(1, snap=[snapshot()])), ssync("pc2", view=view(1, snap=[snapshot()], label="pc2")),
                lay_order(oid(1)), lay_order(oid(2), state="taken", ts=T0, terr="00000002"),
                lay_order(oid(3), state="opening", ts=T0, terr="00000003"),
                lay_order(oid(4), state="opened", ts=T0, terr="00000004"), lay_order(oid(5), dev="pc2"),
                lay_msg("c-sent"),
                ssync("mac", start={"off": True}, now=T0 + 1000), sql(ORDERS), sql(COUNTS),
                sql("SELECT state FROM city_msg WHERE cid = 'c-sent'"),
                ssync("mac", start={"off": True}, now=T0 + 2000)]
        out = self.run_relay(reqs)
        r = out["responses"]
        self.assertEqual(r[8]["body"]["talk"]["start"], {"state": "off"})
        self.assertEqual(r[8]["body"]["talk"]["state"], "on", "talk stays on")
        rows = {x["oid"]: (x["state"], x["why"]) for x in r[9]["body"]}
        self.assertEqual(rows, {oid(1): ("failed", "start-off"), oid(2): ("failed", "start-off"),
                                oid(3): ("opening", ""), oid(4): ("opened", ""), oid(5): ("sent", "")})
        counts = {x["dev"]: json.loads(x["counts"]) for x in r[10]["body"]}
        self.assertFalse(counts["mac"].get("start"))
        self.assertEqual(counts["mac"].get("talk"), 1)
        self.assertEqual(counts["pc2"].get("start"), 1)
        self.assertEqual(r[11]["body"][0]["state"], "taken", "the messages go on: only starting is off")
        self.assertEqual(r[12]["writes"], 0, "a second off writes nothing")

    def test_off_hands_nothing_down(self):
        out = self.run_relay([lay_order(oid(1)), ssync(start={"off": True}, now=T0 + 1000)])
        self.assertNotIn("orders", out["responses"][1]["body"]["talk"]["start"])


class TestCost(RelayCase):
    def full(self):
        lines = [{"ev": "PostToolUse", "sid": "s1", "tool": "Bash", "rid": "github.com/o/r"}] * 8
        v1 = view(1, snap=[snapshot()])
        v2 = view(1, events=[{"type": "tool", "id": "s:1", "tool": "Bash", "name": "Bash"}] * 8)
        reqs = [ssync(view=v1, lines=lines)]
        reqs += [lay_msg("old%02d" % i, at=T0 + i) for i in range(10)]
        reqs += [lay_order(oid(i), terr="%08x" % i, at=T0 + i) for i in range(1, 4)]
        reqs += [ssync(now=T0 + 1000)]
        reqs += [lay_msg("new%02d" % i, at=T0 + 2000 + i) for i in range(10)]
        reqs += [lay_order(oid(i), terr="%08x" % i, at=T0 + 2000 + i) for i in range(4, 7)]
        chat = [{"k": "k%02d" % i, "to": "s:tm1", "kind": "reply", "text": "hi", "at": float(i)} for i in range(20)]
        talk = {"chat": chat, "acks": [{"cid": "old%02d" % i, "state": "delivered"} for i in range(10)]}
        start = {"acks": [{"oid": oid(i), "state": "opening", "info": {"name": "shop Manager", "role": "main"}}
                          for i in range(1, 4)]}
        reqs += [ssync(view=v2, lines=lines, talk=talk, start=start, now=T0 + 5000)]
        return self.run_relay(reqs)

    def test_a_full_sync_fits_the_free_plans_fifty_statements(self):
        out = self.full()
        last = out["responses"][-1]
        self.assertEqual(last["status"], 200, last)
        self.assertEqual(len(last["body"]["talk"]["msgs"]), 10)
        self.assertEqual(len(last["body"]["talk"]["start"]["orders"]), 3)
        self.assertLessEqual(last["stmts"], 40, "%d statements in one sync (the free plan stops at 50)" % last["stmts"])

    def test_no_statement_reads_the_whole_order_table(self):
        out = self.full()
        scans = [s for s in out["full_scans"] if "city_order" in s["detail"] and "CREATE" not in s["sql"]]
        self.assertEqual(scans, [])

    def test_a_quiet_start_sync_writes_nothing(self):
        out = self.run_relay([ssync(), ssync(now=T0 + 5000), ssync(now=T0 + 10000)])
        self.assertEqual([r["writes"] for r in out["responses"][1:]], [0, 0])
        self.assertLessEqual(out["responses"][2]["stmts"], 22)

    def test_a_talk_sync_without_start_costs_what_it_cost(self):
        out = self.run_relay([tsync(), tsync(now=T0 + 5000)])
        self.assertLessEqual(out["responses"][1]["stmts"], 16, "start off: not one more statement")


if __name__ == "__main__":
    unittest.main()
