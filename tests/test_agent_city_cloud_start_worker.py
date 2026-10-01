"""Failing tests, cloud-city-3 slice W2: the City Worker takes the owner's
start orders and serves their state (requirements/city.md, "Cloud page",
"Start"; approved design D1-D16 in agent_state.txt and in commit 9c8479d).

bin/agent-city-cloud.js. The login check stays first on every request (403
and nothing else without a good Access token). Everything of steps 1 and 2
stays; this Worker still holds no key (no TEAM_KEY, no TALK_KEY).

  The table city_order: the exact lines of tests/cloudhelp.py (START_TABLES);
  this Worker makes it (IF NOT EXISTS) before it writes an order. It INSERTs
  only into city_msg and city_order, UPDATEs and DELETEs only those two; it
  never writes city_chat or city_view. A read that finds no order table yet =
  nothing there (no error).

  POST /api/agent/add   body {"dev", "terr", "oid"} or {"dev", "terr", "oid", "force"}
      The second route that acts. Any other method / path pair that is not
      GET or HEAD stays 405. Checked in this order, nothing is written before
      the last check passes:
        the request comes from this page: header X-City-Page: 1, Content-Type
            application/json, and an Origin header equal to the origin of
            the request's own URL                       else 403 {"ok": false, "error": "bad origin"}
        the body is at most 1 KB (1024 bytes)            else 413
        the body is a JSON object with the keys dev, terr, oid, and maybe
            force, and NO other key                      else 400 {"error": "body"}
        terr: exactly 8 of 0-9 a-f (a territory id, never a path or a name)   else 400 {"error": "terr"}
        oid: 16..64 of A-Z a-z 0-9 _ -                   else 400 {"error": "oid"}
        force: missing, true or false                    else 400 {"error": "force"}
        dev: a machine of THIS login (a city_view row)   else 404 {"error": "dev"}
        this (user, oid) is already stored -> 200 with that row's state, why
            and info, nothing written (a repeated request never makes a
            second order and never moves the first one back)
        this user already has an order for the same dev and terr in state
            'sent', 'taken' or 'opening' -> 409 {"ok": false, "error": "busy",
            "oid": <that order's oid>}, nothing written (one order at a time
            per repo: a double click opens one session)
        caps, counted on this user's city_order rows (every order counts, a
            confirm and a failed one too): 10 in the last hour -> 429
            {"ok": false, "error": "too many this hour", "wait": <whole
            seconds until the oldest of those 10 is an hour old, at least 1>};
            40 in the last 24 hours -> 429 {"ok": false, "error": "too many today"}
      Then ONE row: user = the login, oid, dev, terr, force 0 | 1, at = ts =
        now, info '{}', and
        state 'failed', why 'off'        when that machine sent nothing for 150 s
        state 'failed', why 'start-off'  when its counts have no start flag (start: 1)
        state 'sent', why ''             else
      200 {"ok": true, "oid", "state", "why", "info": {}}.
      This user's city_order rows older than 7 days are deleted on an add.

  GET /api/feed   as before, plus
      every machine in "devs" has "start": true | false (its counts' start flag)
      when a machine is shown: "orders" = this user's city_order rows of that
        machine placed in the last 10 minutes (now - at < 600000), oldest
        first, the 20 newest at most:
          {"oid", "terr", "force" (true | false), "at" (ms), "ts" (ms), "state", "why", "info" (an object)}
        Before they are listed: a 'sent' row with now - at >= 60000 is made
        'failed' ('start-off' when the machine's start flag is off, else
        'off'); a 'taken' or 'opening' row with now - ts >= 180000 is made
        'failed' / 'silent'. Both set ts = now. One guarded UPDATE ... RETURNING oid
        each, only when there is such a row, and ONLY the rows that UPDATE
        really changed are shown as failed (a machine that answered in
        between wins).
        No order table yet -> "orders": []. A poll with nothing to expire
        writes nothing; no statement reads the whole order table.
      no machine at all: no "orders" key (the feed of step 1).

No test talks to Cloudflare. Run: python3 -m unittest tests.test_agent_city_cloud_start_worker
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
from cloudhelp import (ME, OTHER, T0, TERR, add, feed, get, lay_order, make_order_table, make_tables,  # noqa: E402
                       snapshot, sql, sync, view)

ORDERS = "SELECT user, oid, dev, terr, force, at, ts, state, why, info FROM city_order ORDER BY at, oid"
FLAGS_ON = "UPDATE city_view SET counts = json_set(counts, '$.talk', 1, '$.start', 1) WHERE dev = ?"
TALK_ONLY = "UPDATE city_view SET counts = json_set(counts, '$.talk', 1) WHERE dev = ?"
OID = "oid-0000000000000001"
HOUR = 3600 * 1000


def machine(dev="mac", start=True, now=T0, key=ch.KEY):
    """A machine of ME that sent a picture at NOW; start=True: with the talk and start flags."""
    return [sync(dev, view=view(1, snap=[snapshot()], label=dev), now=now, key=key),
            sql(FLAGS_ON if start else TALK_ONLY, dev)]


def oid(n):
    return "oid-%016d" % n


@unittest.skipUnless(NODE, SKIP_REASON)
class CityCase(unittest.TestCase):
    def run_city(self, reqs, head=None, **kw):
        head = (machine() + make_tables() + make_order_table()) if head is None else head
        out = ch.run_cloud(self, list(head) + list(reqs), **kw)
        out["responses"] = out["responses"][len(head):]
        return out

    def orders(self, out, index=-1):
        return out["responses"][index]["body"]


class TestGate(CityCase):
    def test_no_login_no_order(self):
        out = self.run_city([add(login=None), add(login={"email": ME, "wrong_key": True}),
                             add(login={"email": ME, "exp_in": -5}), sql(ORDERS)])
        for r in out["responses"][:3]:
            self.assertEqual((r["status"], r["body"], r["writes"]), (403, {"ok": False, "error": "login required"}, 0))
        self.assertEqual(self.orders(out), [])

    def test_only_this_page_can_order(self):
        bad = [add(origin=None), add(origin="https://evil.example"), add(origin="http://cloud.test"),
               add(origin="null"), add(page=None), add(page="0"), add(ctype="text/plain"),
               add(ctype="application/x-www-form-urlencoded"), add(ctype=None)]
        out = self.run_city(bad + [sql(ORDERS)])
        for r in out["responses"][:-1]:
            self.assertEqual((r["status"], r["writes"]), (403, 0), r)
            self.assertEqual(r["body"], {"ok": False, "error": "bad origin"})
        self.assertEqual(self.orders(out), [], "a request another site could make stores nothing")

    def test_the_rest_still_acts_on_nothing(self):
        reqs = [get("/api/feed", method="POST"), get("/api/decide", method="POST"), get("/", method="PUT"),
                get("/api/agent/add", method="PUT"), get("/api/agent/add", method="DELETE"),
                get("/api/agent/open", method="POST"), get("/api/agent", method="POST"), get("/api/agent/add")]
        out = self.run_city(reqs + [sql(ORDERS)])
        for r in out["responses"][:7]:
            self.assertEqual((r["status"], r["writes"]), (405, 0), r)
        self.assertIn(out["responses"][7]["status"], (404, 405), "a GET of the order address gives nothing")
        self.assertEqual(self.orders(out), [])

    def test_no_key_in_this_worker(self):
        with open(ch.CITY, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("TEAM_KEY", src)
        self.assertNotIn("TALK_KEY", src)

    def test_it_writes_messages_and_orders_only(self):
        with open(ch.CITY, encoding="utf-8") as fh:
            src = fh.read()
        for word in ("INSERT", "UPDATE", "DELETE"):
            tables = set(re.findall(r"(?is)\b%s\s+(?:OR\s+\w+\s+)?(?:INTO\s+|FROM\s+)?(city_\w+)" % word, src))
            self.assertLessEqual(tables, {"city_msg", "city_order"}, "%s touches %s" % (word, tables))
        self.assertIn("city_order", set(re.findall(r"(?is)\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+(city_\w+)", src)))

    def test_the_source_holds_the_agreed_lines(self):
        with open(ch.CITY, encoding="utf-8") as fh:
            src = " ".join(fh.read().split())
        for line in ch.START_TABLES:
            self.assertIn(" ".join(line.split()), src, "this exact line is missing: %s" % line[:60])


class TestBody(CityCase):
    def refused(self, req, status, error):
        out = self.run_city([req, sql(ORDERS)])
        r = out["responses"][0]
        self.assertEqual((r["status"], r["writes"]), (status, 0), r)
        if error:
            self.assertEqual(r["body"].get("error"), error, r)
        self.assertEqual(self.orders(out), [])

    def test_size(self):
        self.refused(add(body={"dev": "mac", "terr": TERR, "oid": OID + "x" * 1100}), 413, None)

    def test_json_object(self):
        for body in ("not json", "[1, 2]", "null", '"text"'):
            self.refused(add(body=body), 400, "body")

    def test_an_unknown_key_is_refused(self):
        good = {"dev": "mac", "terr": TERR, "oid": OID}
        for key, value in (("cmd", "rm -rf ~"), ("path", "/etc/passwd"), ("folder", "/Users/owner"),
                           ("name", "x'; touch pwned; '"), ("role", "task-manager"), ("model", "opus"),
                           ("flags", ["--dangerously-skip-permissions"]), ("command", "touch pwned"),
                           ("text", "do this"), ("user", OTHER), ("state", "opened"), ("at", 1), ("", 1)):
            self.refused(add(body=dict(good, **{key: value})), 400, "body")

    def test_a_missing_key_is_refused(self):
        good = {"dev": "mac", "terr": TERR, "oid": OID}
        for key in good:
            body = dict(good)
            del body[key]
            out = self.run_city([add(body=body), sql(ORDERS)])
            self.assertEqual(out["responses"][0]["status"] // 100, 4, key)
            self.assertEqual(self.orders(out), [], key)

    def test_terr_is_a_territory_id_only(self):
        for terr in ("", "0a1b2c3", "0a1b2c3d4", "0A1B2C3D", "g0000000", "/bin/sh0", "../../..", "shop", "0a1b 2c3",
                     "0a1b2c3d\n", 5, None, ["0a1b2c3d"], {"id": TERR}):
            self.refused(add(terr=terr), 400, "terr")

    def test_oid(self):
        for value in ("", "short", "x" * 65, "has space 0000000000", "semi;colon0000000000", "../../etc/passwd000", 5, None):
            self.refused(add(oid=value), 400, "oid")

    def test_force_is_a_bool(self):
        for value in ("yes", 1, 0, "true", None, [True]):
            self.refused(add(body={"dev": "mac", "terr": TERR, "oid": OID, "force": value}), 400, "force")

    def test_dev_must_be_mine(self):
        self.refused(add(dev="nobody"), 404, "dev")
        self.refused(add(dev=""), 404, "dev")
        self.refused(add(dev=7), 404, "dev")

    def test_another_users_machine_is_not_mine(self):
        out = self.run_city([add(login=OTHER), sql(ORDERS)])
        self.assertEqual((out["responses"][0]["status"], out["responses"][0]["body"].get("error")), (404, "dev"))
        self.assertEqual(self.orders(out), [])


class TestStore(CityCase):
    def test_one_row_for_the_login(self):
        out = self.run_city([add(oid=OID, now=T0 + 3000), sql(ORDERS)])
        r = out["responses"][0]
        self.assertEqual((r["status"], r["body"]), (200, {"ok": True, "oid": OID, "state": "sent", "why": "", "info": {}}))
        self.assertEqual(self.orders(out), [{"user": ME, "oid": OID, "dev": "mac", "terr": TERR, "force": 0,
                                             "at": T0 + 3000, "ts": T0 + 3000, "state": "sent", "why": "", "info": "{}"}])

    def test_force_is_stored(self):
        out = self.run_city([add(oid=oid(1), force=True), add(oid=oid(2), force=False, terr="00000002"), sql(ORDERS)])
        self.assertEqual([x["status"] for x in out["responses"][:2]], [200, 200])
        self.assertEqual({o["oid"]: o["force"] for o in self.orders(out)}, {oid(1): 1, oid(2): 0})

    def test_it_makes_the_table_itself(self):
        out = self.run_city([add(oid=OID), sql("SELECT name, sql FROM sqlite_master WHERE name LIKE 'city_order%' ORDER BY name")],
                            head=machine())
        self.assertEqual(out["responses"][0]["status"], 200, out["responses"][0])
        made = {r["name"]: " ".join(r["sql"].split()) for r in out["responses"][1]["body"]}
        norm = lambda s: " ".join(s.replace("IF NOT EXISTS ", "").split())  # noqa: E731
        self.assertEqual(made.get("city_order"), norm(ch.ORDER_SQL))
        self.assertEqual(made.get("city_order_dev"), norm(ch.ORDER_INDEX_SQL))

    def test_a_repeated_request_stores_nothing_new(self):
        out = self.run_city([add(oid=OID), add(oid=OID, now=T0 + 2000),
                             add(oid=OID, terr="00000009", force=True, now=T0 + 3000), sql(ORDERS)])
        r = out["responses"]
        self.assertEqual([x["status"] for x in r[:3]], [200, 200, 200])
        self.assertEqual((r[1]["writes"], r[2]["writes"]), (0, 0))
        self.assertEqual(r[2]["body"], {"ok": True, "oid": OID, "state": "sent", "why": "", "info": {}})
        self.assertEqual([(o["terr"], o["force"], o["at"]) for o in self.orders(out)], [(TERR, 0, T0)])

    def test_a_repeat_says_what_became_of_the_first(self):
        info = '{"name": "shop Manager", "role": "main"}'
        reqs = [add(oid=OID), sql("UPDATE city_order SET state = 'opening', info = ? WHERE oid = ?", info, OID),
                add(oid=OID, now=T0 + 1000),
                sql("UPDATE city_order SET state = 'failed', why = 'late' WHERE oid = ?", OID),
                add(oid=OID, now=T0 + 2000), sql(ORDERS)]
        out = self.run_city(reqs)
        self.assertEqual(out["responses"][2]["body"],
                         {"ok": True, "oid": OID, "state": "opening", "why": "", "info": json.loads(info)})
        self.assertEqual(out["responses"][4]["body"]["state"], "failed")
        self.assertEqual(out["responses"][4]["body"]["why"], "late")
        self.assertEqual(len(self.orders(out)), 1)

    def test_old_rows_leave_on_an_add(self):
        week = 7 * 24 * 3600 * 1000
        out = self.run_city([lay_order("old-old-old-old-0001", at=T0 - week - 1, state="opened", terr="00000001"),
                             lay_order("new-new-new-new-0001", at=T0 - week + 60000, state="opened", terr="00000002"),
                             lay_order("oth-oth-oth-oth-0001", at=T0 - week - 1, state="opened", user=OTHER),
                             add(oid=OID), sql("SELECT oid FROM city_order ORDER BY oid")])
        self.assertEqual([o["oid"] for o in self.orders(out)], ["new-new-new-new-0001", OID, "oth-oth-oth-oth-0001"])


class TestOnePerRepo(CityCase):
    def test_a_second_order_for_the_same_repo_is_busy(self):
        for state in ("sent", "taken", "opening"):
            out = self.run_city([lay_order(oid(1), state=state), add(oid=oid(2), now=T0 + 2000), sql(ORDERS)])
            r = out["responses"][1]
            self.assertEqual((r["status"], r["body"], r["writes"]),
                             (409, {"ok": False, "error": "busy", "oid": oid(1)}, 0), state)
            self.assertEqual(len(self.orders(out)), 1)

    def test_a_finished_order_frees_the_repo(self):
        for state, why in (("opened", ""), ("cap", ""), ("failed", "late")):
            out = self.run_city([lay_order(oid(1), state=state, why=why), add(oid=oid(2), now=T0 + 2000)])
            self.assertEqual(out["responses"][1]["status"], 200, state)

    def test_another_repo_or_machine_is_not_held_up(self):
        head = machine() + machine("pc2") + make_tables() + make_order_table()
        out = self.run_city([lay_order(oid(1)), add(oid=oid(2), terr="00000002", now=T0 + 1000),
                             add(oid=oid(3), dev="pc2", now=T0 + 2000)], head=head)
        self.assertEqual([r["status"] for r in out["responses"][1:]], [200, 200])

    def test_another_users_order_does_not_hold_mine(self):
        out = self.run_city([lay_order(oid(1), user=OTHER), add(oid=oid(2), now=T0 + 1000)])
        self.assertEqual(out["responses"][1]["status"], 200)

    def test_the_confirm_after_cap_is_a_second_order(self):
        out = self.run_city([lay_order(oid(1), state="cap", info='{"ram": 86, "cpu": 41, "max": 80}'),
                             add(oid=oid(2), force=True, now=T0 + 4000), sql(ORDERS)])
        self.assertEqual(out["responses"][1]["body"]["state"], "sent")
        rows = {o["oid"]: (o["state"], o["force"]) for o in self.orders(out)}
        self.assertEqual(rows, {oid(1): ("cap", 0), oid(2): ("sent", 1)})


class TestHonest(CityCase):
    def test_machine_off(self):
        out = self.run_city([add(oid=OID, now=T0 + 150001), sql(ORDERS)])
        self.assertEqual(out["responses"][0]["body"], {"ok": True, "oid": OID, "state": "failed", "why": "off", "info": {}})
        self.assertEqual((self.orders(out)[0]["state"], self.orders(out)[0]["why"]), ("failed", "off"),
                         "stored as not opened: no machine will ever take it")

    def test_machine_just_seen_is_on(self):
        out = self.run_city([add(oid=OID, now=T0 + 150000)])
        self.assertEqual(out["responses"][0]["body"]["state"], "sent")

    def test_machine_does_not_take_orders(self):
        head = machine(start=False) + make_tables() + make_order_table()
        out = self.run_city([add(oid=OID), sql(ORDERS)], head=head)
        self.assertEqual(out["responses"][0]["body"], {"ok": True, "oid": OID, "state": "failed", "why": "start-off", "info": {}})
        self.assertEqual(self.orders(out)[0]["state"], "failed", "talk on is not start on")

    def test_a_flag_of_zero_is_off(self):
        head = machine(start=False) + make_tables() + make_order_table() + \
            [sql("UPDATE city_view SET counts = json_set(counts, '$.start', 0)")]
        out = self.run_city([add(oid=OID)], head=head)
        self.assertEqual(out["responses"][0]["body"]["why"], "start-off")


class TestCaps(CityCase):
    def lay_many(self, n, start, step, user=ME):
        return [lay_order("r%s-%015d" % (user[0], i), at=start + i * step, state="opened", terr="%08x" % i, user=user)
                for i in range(n)]

    def test_ten_an_hour(self):
        reqs = self.lay_many(9, T0, 60000) + self.lay_many(20, T0, 1000, user=OTHER)
        reqs += [add(oid=oid(1), terr="000000a1", now=T0 + 10 * 60000),            # the 10th
                 add(oid=oid(2), terr="000000a2", now=T0 + 11 * 60000),            # the 11th: no
                 add(oid=oid(2), terr="000000a2", now=T0 + 12 * 60000),
                 sql("SELECT COUNT(*) AS n FROM city_order WHERE user = ?", ME),
                 add(oid=oid(3), terr="000000a3", now=T0 + HOUR + 1000)]            # the first one is an hour old
        out = self.run_city(reqs)
        r = out["responses"][29:]
        self.assertEqual(r[0]["status"], 200, r[0])
        self.assertEqual((r[1]["status"], r[1]["writes"]), (429, 0), r[1])
        self.assertEqual(r[1]["body"], {"ok": False, "error": "too many this hour", "wait": 49 * 60})
        self.assertEqual(r[2]["status"], 429)
        self.assertEqual(r[3]["body"][0]["n"], 10, "the other user's rows are not mine; a refused order stores nothing")
        self.assertEqual(r[4]["status"], 200, "an hour later the oldest one no longer counts")

    def test_a_failed_order_and_a_confirm_count_too(self):
        reqs = [lay_order("f-%015d" % i, at=T0 + i, state="failed", why="gone", terr="%08x" % i) for i in range(5)]
        reqs += [lay_order("c-%015d" % i, at=T0 + 100 + i, state="cap", terr="%08x" % (50 + i)) for i in range(5)]
        reqs += [add(oid=oid(1), force=True, now=T0 + 5000)]
        out = self.run_city(reqs)
        self.assertEqual(out["responses"][10]["status"], 429)

    def test_forty_a_day(self):
        reqs = self.lay_many(39, T0, 7 * 60000)          # 7 minutes apart: never 10 in an hour
        last = T0 + 39 * 7 * 60000
        reqs += [add(oid=oid(1), terr="000000a1", now=last + 7 * 60000), add(oid=oid(2), terr="000000a2", now=last + 14 * 60000),
                 add(oid=oid(3), terr="000000a3", now=T0 + 24 * HOUR + 8 * 60000)]
        out = self.run_city(reqs)
        r = out["responses"][39:]
        self.assertEqual(r[0]["status"], 200, r[0])
        self.assertEqual((r[1]["status"], r[1]["body"], r[1]["writes"]), (429, {"ok": False, "error": "too many today"}, 0))
        self.assertEqual(r[2]["status"], 200, r[2])

    def test_a_repeat_is_never_too_many(self):
        reqs = self.lay_many(9, T0, 60000) + [add(oid=oid(1), terr="000000a1", now=T0 + 10 * 60000),
                                              add(oid=oid(1), terr="000000a1", now=T0 + 11 * 60000)]
        out = self.run_city(reqs)
        self.assertEqual([r["status"] for r in out["responses"][9:]], [200, 200])


class TestFeed(CityCase):
    def test_every_machine_says_whether_it_starts(self):
        head = machine("mac") + machine("pc2", start=False, now=T0 - 1000) + \
            [sync("old", view=view(1, snap=[snapshot()], label="old"), now=T0 - 2000)]
        out = self.run_city([feed()], head=head)
        devs = {d["dev"]: (d["talk"], d["start"]) for d in out["responses"][0]["body"]["devs"]}
        self.assertEqual(devs, {"mac": (True, True), "pc2": (True, False), "old": (False, False)})

    def test_no_table_yet_is_no_orders(self):
        out = self.run_city([feed()], head=machine())
        r = out["responses"][0]
        self.assertEqual((r["status"], r["body"]["orders"], r["writes"]), (200, [], 0))

    def test_no_machine_no_orders_key(self):
        out = self.run_city([feed()], head=[])
        self.assertNotIn("orders", out["responses"][0]["body"])

    def test_the_orders_of_the_machine_shown(self):
        info = '{"name": "shop Manager", "role": "main"}'
        head = machine("mac") + machine("pc2", now=T0 - 1000) + make_tables() + make_order_table()
        lay = [lay_order(oid(1), at=T0, state="opened", ts=T0 + 9000, info=info),
               lay_order(oid(2), at=T0 + 20000, terr="00000002", force=1, state="taken", ts=T0 + 25000),
               lay_order(oid(3), dev="pc2", at=T0 + 1000), lay_order(oid(4), user=OTHER, at=T0 + 1000)]
        out = self.run_city(lay + [feed(dev="mac", now=T0 + 30000), feed(dev="pc2", now=T0 + 30000)], head=head)
        r = out["responses"]
        self.assertEqual(r[4]["body"]["orders"], [
            {"oid": oid(1), "terr": TERR, "force": False, "at": T0, "ts": T0 + 9000, "state": "opened", "why": "",
             "info": json.loads(info)},
            {"oid": oid(2), "terr": "00000002", "force": True, "at": T0 + 20000, "ts": T0 + 25000, "state": "taken",
             "why": "", "info": {}}])
        self.assertEqual([o["oid"] for o in r[5]["body"]["orders"]], [oid(3)])
        self.assertEqual((r[4]["writes"], r[5]["writes"]), (0, 0))

    def test_ten_minutes_and_the_twenty_newest(self):
        lay = [lay_order(oid(i), at=T0 + i * 1000, state="failed", why="gone", terr="%08x" % i) for i in range(30)]
        out = self.run_city(lay + [feed(now=T0 + 40000), feed(now=T0 + 600000 + 25500)])
        r = out["responses"]
        self.assertEqual([o["oid"] for o in r[30]["body"]["orders"]], [oid(i) for i in range(10, 30)])
        self.assertEqual([o["oid"] for o in r[31]["body"]["orders"]], [oid(i) for i in range(26, 30)],
                         "an order placed more than 10 minutes ago is no longer listed")

    def test_broken_info_is_an_empty_object(self):
        out = self.run_city([lay_order(oid(1), state="opened", info="not json"),
                             lay_order(oid(2), state="opened", info="[1]", terr="00000002"), feed(now=T0 + 1000)])
        self.assertEqual([o["info"] for o in out["responses"][2]["body"]["orders"]], [{}, {}])

    def test_not_taken_in_sixty_seconds_is_not_opened(self):
        out = self.run_city([lay_order(oid(1), at=T0), feed(now=T0 + 59000), feed(now=T0 + 60000),
                             feed(now=T0 + 61000), sql(ORDERS)])
        r = out["responses"]
        self.assertEqual(r[1]["body"]["orders"][0]["state"], "sent")
        self.assertEqual(r[1]["writes"], 0)
        got = r[2]["body"]["orders"][0]
        self.assertEqual((got["state"], got["why"], got["ts"]), ("failed", "off", T0 + 60000))
        self.assertEqual(r[3]["writes"], 0, "expired once")
        row = self.orders(out)[0]
        self.assertEqual((row["state"], row["why"]), ("failed", "off"), "stored: no machine takes it later")

    def test_a_machine_with_start_off_says_so(self):
        head = machine(start=False) + make_tables() + make_order_table()
        out = self.run_city([lay_order(oid(1), at=T0), feed(now=T0 + 60000)], head=head)
        got = out["responses"][1]["body"]["orders"][0]
        self.assertEqual((got["state"], got["why"]), ("failed", "start-off"))

    def test_no_word_for_three_minutes_is_silent(self):
        lay = [lay_order(oid(1), state="taken", at=T0, ts=T0 + 1000),
               lay_order(oid(2), state="opening", at=T0, ts=T0 + 2000, terr="00000002"),
               lay_order(oid(3), state="opening", at=T0, ts=T0 + 100000, terr="00000003")]
        out = self.run_city(lay + [feed(now=T0 + 182000), sql(ORDERS)])
        got = {o["oid"]: (o["state"], o["why"]) for o in out["responses"][3]["body"]["orders"]}
        self.assertEqual(got, {oid(1): ("failed", "silent"), oid(2): ("failed", "silent"), oid(3): ("opening", "")})
        rows = {o["oid"]: o["state"] for o in self.orders(out)}
        self.assertEqual(rows, {oid(1): "failed", oid(2): "failed", oid(3): "opening"})

    def test_the_machine_that_took_it_in_between_wins(self):
        with open(ch.CITY, encoding="utf-8") as fh:
            src = fh.read()
        self.assertRegex(src, r"(?is)UPDATE\s+city_order\s+SET[^;]*?RETURNING\s+oid",
                         "the expiry is a guarded UPDATE ... RETURNING oid: only the rows it changed are shown as failed")

    def test_a_poll_is_cheap(self):
        lay = [lay_order(oid(i), at=T0 - 3 * HOUR + i, state="opened", terr="%08x" % i) for i in range(30)]
        out = self.run_city(lay + [lay_order(oid(99), at=T0, state="opening", ts=T0), feed(now=T0 + 3000)])
        r = out["responses"][-1]
        self.assertEqual(r["writes"], 0)
        self.assertLessEqual(r["reads"], 6, "a poll reads this machine's few rows")
        scans = [s for s in out["full_scans"] if "city_order" in s["detail"] and "CREATE" not in s["sql"]]
        self.assertEqual(scans, [], "no statement reads the whole order table")

    def test_another_users_orders_are_never_shown(self):
        out = self.run_city([lay_order(oid(1), state="opened"), feed(login=OTHER, now=T0 + 1000)])
        body = out["responses"][1]["body"]
        self.assertNotIn(oid(1), json.dumps(body))


if __name__ == "__main__":
    unittest.main()
