"""Failing tests, cloud-city-2 slice S2: the City Worker takes the owner's
messages and serves the conversation (requirements/city.md, "Cloud page",
step 2; approved design in agent_state.txt, mock mock/cloud-city-2-mock.html).

bin/agent-city-cloud.js. The login check stays first on every request (403
and nothing else without a good Access token). Everything of step 1 stays;
this Worker still holds no key (no TEAM_KEY, no TALK_KEY).

  The tables city_msg and city_chat: the exact lines of tests/cloudhelp.py
  (TALK_TABLES); this Worker makes them (IF NOT EXISTS) before it writes a
  message. It INSERTs only into city_msg, UPDATEs only city_msg (to say "not
  delivered"), DELETEs only old city_msg rows; it never writes city_chat or
  city_view. A read that finds no talk table yet = nothing there (no error).

  POST /api/chat/send   body {"dev", "to", "text", "cid"}
      One of the two routes that act (cloud-city-3 added POST /api/agent/add,
      tests/test_agent_city_cloud_start_worker.py). Any other method / path pair that is not
      GET or HEAD stays 405. Checked in this order, nothing is written
      before the last check passes:
        the request comes from this page: header X-City-Page: 1, Content-Type
            application/json, and an Origin header equal to the origin of
            the request's own URL                       else 403 {"ok": false, "error": "bad origin"}
        the body is at most 16 KB                        else 413
        the body is a JSON object with the keys dev, to, text, cid and NO
            other key (bounce 1, 2026-10-01: an unknown key such as "cmd" was
            ignored and the message taken; /api/agent/add refuses one too)
                                                         else 400 {"error": "body"}
        text: a string, 1..4000 characters, not only spaces   else 400 {"error": "text"}
        cid: 16..64 of A-Z a-z 0-9 _ -                   else 400 {"error": "cid"}
        to: "s:" or "gov:" + 1..120 of A-Z a-z 0-9 _ . : -    else 400 {"error": "to"}
            (so never a path, a subagent's bare id, or a guest "r:" / "rg:")
        dev: a machine of THIS login (a city_view row)   else 404 {"error": "dev"}
        this (user, cid) is already stored -> 200 with that row's state and
            why, nothing written (a repeated request never makes a second
            message and never moves the first one back)
        rate, counted on this user's city_msg rows: 30 in the last 5 minutes
            -> 429 {"error": "too fast"}; 300 in the last 24 hours ->
            429 {"error": "too many today"}
      Then ONE row: user = the login, dev, pg = to, text, at = now, and
        state 'undelivered', why 'off'       when that machine sent nothing for 150 s
        state 'undelivered', why 'talk-off'  when its counts have no talk flag (talk: 1)
        state 'sent', why ''                 else
      200 {"ok": true, "cid", "state", "why"}. Only these columns are ever
      stored; a body with any other field is refused, see above.
      This user's city_msg rows older than 7 days are deleted on a send.

  GET /api/feed   as before, plus
      every machine in "devs" has "talk": true | false (its counts' talk flag)
      with ?chat=<to>&cc=<cursor> (the open window of the machine shown):
        "chat": {"to", "cc", "rows", "msgs"}
          rows = this user's city_chat rows of that machine and window with
              id > cc, as {"k", "kind", "text", "at", "state", "why", "cid"},
              ordered by at, then id; with cc = 0 (a window just opened) the
              200 newest. "cc" = the highest id this user's rows of that
              machine and window have now (the cursor to send next; never
              lower than the one that came in).
          msgs = the messages the machine has no entry for: this user's
              city_msg rows of that machine and window in state 'sent',
              'taken' or 'undelivered' that have no city_chat row whose k is
              their cid (the machine's row for a cloud message has k = cid, and
              its answer 'queued' / 'delivered' always comes with that row, so
              those two states are never listed). The 50 newest, oldest first:
              {"cid", "text", "at" (seconds), "state", "why"}.
              A 'sent' row older than 60 s is first made 'undelivered'
              ('talk-off' when the machine's talk flag is off, else 'off'), a
              'taken' row older than 10 min 'undelivered' / 'off': one guarded
              UPDATE ... RETURNING cid each, only when there is such a row, and
              ONLY the rows that UPDATE really changed are shown as not
              delivered (a machine that took the row in between wins: a
              message shown as not delivered must never arrive later).
              COST: a poll comes every 3 s, so these reads go through the
              indexes only: city_msg by (user, dev, state), city_chat by its
              unique key (user, dev, k). Never every message of the machine,
              never every row of the window per message.
        A poll with nothing to expire writes nothing and reads few rows.
      Without chat= the feed is exactly the feed of step 1 (plus "talk").

No test talks to Cloudflare. Run: python3 -m unittest tests.test_agent_city_cloud_talk_worker
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
from cloudhelp import (ME, ORIGIN, OTHER, T0, feed, get, lay_chat, lay_msg, make_tables, send,  # noqa: E402
                       snapshot, sql, sync, view)

MSGS = "SELECT user, cid, dev, pg, text, at, state, why FROM city_msg ORDER BY at, cid"
TALK_ON = "UPDATE city_view SET counts = json_set(counts, '$.talk', 1) WHERE dev = ?"
CID = "cid-0000000000000001"


def machine(dev="mac", talk=True, now=T0, key=ch.KEY):
    """A machine of ME that sent a picture at NOW; talk=True: with the talk flag."""
    reqs = [sync(dev, view=view(1, snap=[snapshot()], label=dev), now=now, key=key)]
    if talk:
        reqs.append(sql(TALK_ON, dev))
    return reqs


def cid(n):
    return "cid-%016d" % n


@unittest.skipUnless(NODE, SKIP_REASON)
class CityCase(unittest.TestCase):
    def run_city(self, reqs, head=None, **kw):
        head = (machine() + make_tables()) if head is None else head
        out = ch.run_cloud(self, list(head) + list(reqs), **kw)
        out["responses"] = out["responses"][len(head):]
        return out

    def msgs(self, out, index=-1):
        return out["responses"][index]["body"]


class TestGate(CityCase):
    def test_no_login_no_message(self):
        out = self.run_city([send(login=None), send(login={"email": ME, "wrong_key": True}),
                             send(login={"email": ME, "exp_in": -5}), sql(MSGS)])
        for r in out["responses"][:3]:
            self.assertEqual((r["status"], r["body"], r["writes"]), (403, {"ok": False, "error": "login required"}, 0))
        self.assertEqual(self.msgs(out), [])

    def test_only_this_page_can_send(self):
        bad = [send(origin=None), send(origin="https://evil.example"), send(origin="http://cloud.test"),
               send(origin="null"), send(page=None), send(page="0"), send(ctype="text/plain"),
               send(ctype="application/x-www-form-urlencoded"), send(ctype=None)]
        out = self.run_city(bad + [sql(MSGS)])
        for r in out["responses"][:-1]:
            self.assertEqual((r["status"], r["writes"]), (403, 0), r)
            self.assertEqual(r["body"], {"ok": False, "error": "bad origin"})
        self.assertEqual(self.msgs(out), [], "a request another site could make stores nothing")

    def test_the_rest_still_acts_on_nothing(self):
        reqs = [get("/api/feed", method="POST"), get("/api/decide", method="POST"), get("/", method="PUT"),
                get("/api/chat/send", method="PUT"), get("/api/chat/send", method="DELETE"),
                get("/api/agent/open", method="POST"), get("/api/chat/send")]
        out = self.run_city(reqs)
        for r in out["responses"][:6]:
            self.assertEqual((r["status"], r["writes"]), (405, 0), r)
        self.assertIn(out["responses"][6]["status"], (404, 405), "a GET of the send address gives nothing")

    def test_no_key_in_this_worker(self):
        with open(ch.CITY, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("TEAM_KEY", src)
        self.assertNotIn("TALK_KEY", src)

    def test_it_writes_messages_only(self):
        # cloud-city-3: and start orders (city_order, tests/test_agent_city_cloud_start_worker.py); never chat or pictures
        with open(ch.CITY, encoding="utf-8") as fh:
            src = fh.read()
        for word in ("INSERT", "UPDATE", "DELETE"):
            tables = set(re.findall(r"(?is)\b%s\s+(?:OR\s+\w+\s+)?(?:INTO\s+|FROM\s+)?(city_\w+)" % word, src))
            self.assertLessEqual(tables, {"city_msg", "city_order"}, "%s touches %s" % (word, tables))


class TestBody(CityCase):
    def refused(self, req, status, error):
        out = self.run_city([req, sql(MSGS)])
        r = out["responses"][0]
        self.assertEqual((r["status"], r["writes"]), (status, 0), r)
        if error:
            self.assertEqual(r["body"].get("error"), error, r)
        self.assertEqual(self.msgs(out), [])

    def test_size(self):
        self.refused(send(body={"dev": "mac", "to": "s:tm1", "text": "x" * 17000, "cid": CID}), 413, None)

    def test_json_object(self):
        for body in ("not json", "[1, 2]", "null", '"text"'):
            self.refused(send(body=body), 400, "body")

    def test_text(self):
        for text in ("", "   \n ", "x" * 4001, 7, None, ["a"], {"a": 1}):
            self.refused(send(text=text), 400, "text")

    def test_cid(self):
        for value in ("", "short", "x" * 65, "has space 0000000000", "semi;colon0000000000", "../../etc/passwd000", 5, None):
            self.refused(send(cid=value), 400, "cid")

    def test_to_is_a_session_or_a_governor_only(self):
        for to in ("", "tm1", "a9f3", "r:dev-pc2:s:1", "rg:dev-pc2", "/bin/sh", "../../etc/passwd", "s:../../x",
                   "s:tm1 --flag", "s:tm1;rm", "gov:", "s:", "s:" + "x" * 121, "S:tm1", 5, None, ["s:tm1"]):
            self.refused(send(to=to), 400, "to")

    def test_dev_must_be_mine(self):
        self.refused(send(dev="nobody"), 404, "dev")
        self.refused(send(dev=""), 404, "dev")
        self.refused(send(dev=7), 404, "dev")

    def test_four_thousand_characters_are_fine(self):
        out = self.run_city([send(text="字" * 4000), sql(MSGS)])
        self.assertEqual(out["responses"][0]["status"], 200, out["responses"][0])
        self.assertEqual(len(self.msgs(out)[0]["text"]), 4000)


class TestStore(CityCase):
    def test_one_row_for_the_login(self):
        out = self.run_city([send(to="s:tm1", text="先跑一下测试", cid=CID, now=T0 + 3000), sql(MSGS)])
        r = out["responses"][0]
        self.assertEqual((r["status"], r["body"]), (200, {"ok": True, "cid": CID, "state": "sent", "why": ""}))
        self.assertEqual(self.msgs(out), [{"user": ME, "cid": CID, "dev": "mac", "pg": "s:tm1", "text": "先跑一下测试",
                                           "at": T0 + 3000, "state": "sent", "why": ""}])

    def test_a_governor_window_too(self):
        out = self.run_city([send(to="gov:t-7f3a.shop", cid=CID), sql(MSGS)])
        self.assertEqual(out["responses"][0]["status"], 200, out["responses"][0])
        self.assertEqual(self.msgs(out)[0]["pg"], "gov:t-7f3a.shop")

    def test_it_makes_the_tables_itself(self):
        out = self.run_city([send(cid=CID), sql("SELECT name, sql FROM sqlite_master WHERE name IN ('city_msg', 'city_chat')")],
                            head=machine())
        self.assertEqual(out["responses"][0]["status"], 200, out["responses"][0])
        made = {r["name"]: " ".join(r["sql"].split()) for r in out["responses"][1]["body"]}
        norm = lambda s: " ".join(s.replace("IF NOT EXISTS ", "").split())  # noqa: E731
        self.assertEqual(made.get("city_msg"), norm(ch.MSG_SQL))
        self.assertEqual(made.get("city_chat"), norm(ch.CHAT_SQL))

    def test_a_repeated_request_stores_nothing_new(self):
        out = self.run_city([send(text="one", cid=CID), send(text="one", cid=CID, now=T0 + 2000),
                             send(text="another text", to="s:other", cid=CID, now=T0 + 3000), sql(MSGS)])
        r = out["responses"]
        self.assertEqual([x["status"] for x in r[:3]], [200, 200, 200])
        self.assertEqual((r[1]["writes"], r[2]["writes"]), (0, 0))
        self.assertEqual(r[2]["body"], {"ok": True, "cid": CID, "state": "sent", "why": ""})
        self.assertEqual([(m["text"], m["pg"], m["at"]) for m in self.msgs(out)], [("one", "s:tm1", T0)])

    def test_a_repeat_never_moves_a_message_back(self):
        reqs = [send(cid=CID), sql("UPDATE city_msg SET state = 'taken' WHERE cid = ?", CID),
                send(cid=CID, now=T0 + 1000),
                sql("UPDATE city_msg SET state = 'undelivered', why = 'ended' WHERE cid = ?", CID),
                send(cid=CID, now=T0 + 2000), sql(MSGS)]
        out = self.run_city(reqs)
        self.assertEqual(out["responses"][2]["body"], {"ok": True, "cid": CID, "state": "taken", "why": ""})
        self.assertEqual(out["responses"][4]["body"], {"ok": True, "cid": CID, "state": "undelivered", "why": "ended"})
        self.assertEqual(len(self.msgs(out)), 1)
        self.assertEqual(self.msgs(out)[0]["state"], "undelivered")

    def test_an_unknown_key_is_refused(self):
        good = {"dev": "mac", "to": "s:tm1", "text": "hello", "cid": CID}
        for key, value in (("cmd", "rm -rf ~"), ("path", "/etc/passwd"), ("flags", ["--dangerously-skip-permissions"]),
                           ("file", "x.sh"), ("user", OTHER), ("state", "delivered"), ("at", 1), ("why", ""), ("", 1)):
            out = self.run_city([send(body=dict(good, **{key: value}), now=T0 + 500), sql("SELECT * FROM city_msg")])
            r = out["responses"][0]
            self.assertEqual((r["status"], r["body"].get("error"), r["writes"]), (400, "body", 0), key)
            self.assertEqual(self.msgs(out), [], key)

    def test_a_missing_key_is_refused(self):
        good = {"dev": "mac", "to": "s:tm1", "text": "hello", "cid": CID}
        for key in good:
            body = dict(good)
            del body[key]
            out = self.run_city([send(body=body), sql("SELECT * FROM city_msg")])
            self.assertEqual(out["responses"][0]["status"] // 100, 4, key)
            self.assertEqual(self.msgs(out), [], key)

    def test_only_the_four_columns_are_kept(self):
        out = self.run_city([send(text="hello", cid=CID, now=T0 + 500), sql("SELECT * FROM city_msg")])
        self.assertEqual(self.msgs(out), [{"user": ME, "cid": CID, "dev": "mac", "pg": "s:tm1", "text": "hello",
                                           "at": T0 + 500, "state": "sent", "why": ""}])

    def test_old_rows_leave_on_a_send(self):
        week = 7 * 24 * 3600 * 1000
        out = self.run_city([lay_msg("old-old-old-old-0001", at=T0 - week - 1, state="delivered"),
                             lay_msg("new-new-new-new-0001", at=T0 - week + 60000, state="delivered"),
                             lay_msg("oth-oth-oth-oth-0001", at=T0 - week - 1, state="delivered", user=OTHER),
                             send(cid=CID), sql("SELECT cid FROM city_msg ORDER BY cid")])
        self.assertEqual([m["cid"] for m in self.msgs(out)], [CID, "new-new-new-new-0001", "oth-oth-oth-oth-0001"])


class TestHonest(CityCase):
    def test_machine_off(self):
        out = self.run_city([send(cid=CID, now=T0 + 150001), sql(MSGS)])
        self.assertEqual(out["responses"][0]["body"], {"ok": True, "cid": CID, "state": "undelivered", "why": "off"})
        self.assertEqual((self.msgs(out)[0]["state"], self.msgs(out)[0]["why"]), ("undelivered", "off"),
                         "stored as not delivered: no machine will ever pick it up")

    def test_machine_just_seen_is_on(self):
        out = self.run_city([send(cid=CID, now=T0 + 150000)])
        self.assertEqual(out["responses"][0]["body"]["state"], "sent")

    def test_machine_does_not_take_messages(self):
        out = self.run_city([send(cid=CID), sql(MSGS)], head=machine(talk=False) + make_tables())
        self.assertEqual(out["responses"][0]["body"], {"ok": True, "cid": CID, "state": "undelivered", "why": "talk-off"})
        self.assertEqual(self.msgs(out)[0]["state"], "undelivered")

    def test_a_flag_of_zero_is_off(self):
        head = machine(talk=False) + make_tables() + [sql("UPDATE city_view SET counts = json_set(counts, '$.talk', 0)")]
        out = self.run_city([send(cid=CID)], head=head)
        self.assertEqual(out["responses"][0]["body"]["why"], "talk-off")


class TestRate(CityCase):
    def lay_many(self, n, start, step, user=ME):
        return [lay_msg("r%s-%015d" % (user[0], i), at=start + i * step, state="delivered", user=user) for i in range(n)]

    def test_thirty_in_five_minutes(self):
        reqs = self.lay_many(29, T0, 1000) + self.lay_many(40, T0, 1000, user=OTHER)
        reqs += [send(cid=cid(1), now=T0 + 60000), send(cid=cid(2), now=T0 + 61000),
                 send(cid=cid(2), now=T0 + 62000), sql("SELECT COUNT(*) AS n FROM city_msg WHERE user = ?", ME),
                 send(cid=cid(3), now=T0 + 5 * 60000 + 2000)]
        out = self.run_city(reqs)
        r = out["responses"][69:]
        self.assertEqual(r[0]["status"], 200, r[0])
        self.assertEqual((r[1]["status"], r[1]["body"], r[1]["writes"]), (429, {"ok": False, "error": "too fast"}, 0))
        self.assertEqual(r[2]["status"], 429)
        self.assertEqual(r[3]["body"][0]["n"], 30, "the other user's rows are not mine")
        self.assertEqual(r[4]["status"], 200, "five minutes later the oldest ones no longer count")

    def test_three_hundred_a_day(self):
        reqs = self.lay_many(299, T0, 4 * 60 * 1000 // 20)   # 12 s apart: never 30 in 5 minutes
        last = T0 + 299 * 12000
        reqs += [send(cid=cid(1), now=last + 20000), send(cid=cid(2), now=last + 40000),
                 send(cid=cid(3), now=T0 + 24 * 3600 * 1000 + 30000)]
        out = self.run_city(reqs)
        r = out["responses"][299:]
        self.assertEqual(r[0]["status"], 200, r[0])
        self.assertEqual((r[1]["status"], r[1]["body"], r[1]["writes"]), (429, {"ok": False, "error": "too many today"}, 0))
        self.assertEqual(r[2]["status"], 200, r[2])

    def test_a_repeat_is_never_too_fast(self):
        reqs = self.lay_many(29, T0, 1000) + [send(cid=cid(1), now=T0 + 60000), send(cid=cid(1), now=T0 + 61000)]
        out = self.run_city(reqs)
        self.assertEqual([x["status"] for x in out["responses"][29:]], [200, 200])


class TestOnlyMine(CityCase):
    def test_another_login_cannot_send_to_my_machine(self):
        out = self.run_city([send(login=OTHER, cid=CID), sql(MSGS)])
        self.assertEqual((out["responses"][0]["status"], out["responses"][0]["body"].get("error")), (404, "dev"))
        self.assertEqual(self.msgs(out), [])

    def test_another_login_never_reads_my_conversation(self):
        reqs = [lay_chat("k1", text="my secret plan"), lay_msg(CID, text="my secret order"),
                feed(login=OTHER, dev="mac", chat="s:tm1", cc=0)]
        out = self.run_city(reqs)
        body = out["responses"][-1]["body"]
        self.assertNotIn("secret", json.dumps(body))
        self.assertEqual(body["devs"], [])


class TestFeedChat(CityCase):
    def test_every_machine_says_whether_it_talks(self):
        head = machine("mac") + machine("pc2", talk=False, now=T0 + 1000) + make_tables()
        out = self.run_city([feed()], head=head)
        self.assertEqual({d["dev"]: d["talk"] for d in out["responses"][0]["body"]["devs"]}, {"mac": True, "pc2": False})

    def test_no_window_no_chat(self):
        out = self.run_city([lay_chat("k1"), feed(dev="mac", gen=1, after=0)])
        r = out["responses"][1]
        self.assertNotIn("chat", r["body"])
        self.assertEqual(r["writes"], 0)
        self.assertLessEqual(r["reads"], 4, "a poll with no window open costs what it cost in step 1")

    def test_a_window_gets_its_rows_in_the_machines_order(self):
        reqs = [lay_chat("k2", text="收到", at=20.0, kind="reply"),
                lay_chat("k1", text="先写测试", at=10.0, kind="prompt"),
                lay_chat("m1", text="go on", at=30.0, kind="owner", state="delivered", cid="m1"),
                lay_chat("x1", text="other window", to="s:other", at=5.0),
                lay_chat("y1", text="other machine", dev="pc2", at=6.0),
                lay_chat("z1", text="other user", user=OTHER, at=7.0),
                feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0)]
        out = self.run_city(reqs)
        chat = out["responses"][-1]["body"]["chat"]
        self.assertEqual(chat["to"], "s:tm1")
        self.assertEqual(chat["rows"],
                         [{"k": "k1", "kind": "prompt", "text": "先写测试", "at": 10.0, "state": "", "why": "", "cid": ""},
                          {"k": "k2", "kind": "reply", "text": "收到", "at": 20.0, "state": "", "why": "", "cid": ""},
                          {"k": "m1", "kind": "owner", "text": "go on", "at": 30.0, "state": "delivered", "why": "",
                           "cid": "m1"}])
        self.assertEqual(chat["cc"], 3)
        self.assertEqual(chat["msgs"], [])

    def test_only_what_is_new_after_the_cursor(self):
        reqs = [lay_chat("k1", at=10.0), lay_chat("k2", at=20.0),
                feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=2),
                lay_chat("k3", at=15.0),
                feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=2)]
        out = self.run_city(reqs)
        quiet, fresh = out["responses"][2]["body"]["chat"], out["responses"][4]["body"]["chat"]
        self.assertEqual((quiet["rows"], quiet["cc"]), ([], 2))
        self.assertEqual(([r["k"] for r in fresh["rows"]], fresh["cc"]), (["k3"], 3))
        self.assertEqual(out["responses"][2]["writes"], 0)
        self.assertLessEqual(out["responses"][2]["reads"], 6, "a poll of an open window with nothing new")

    def test_a_cursor_from_elsewhere_never_goes_down(self):
        out = self.run_city([lay_chat("k1"), feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=999)])
        chat = out["responses"][1]["body"]["chat"]
        self.assertEqual((chat["rows"], chat["cc"]), ([], 999))

    def test_a_new_window_gets_the_200_newest(self):
        reqs = [sql("INSERT INTO city_chat (user, dev, pg, k, kind, text, at, ts, state, why, cid) "
                    "SELECT ?, 'mac', 's:tm1', 'k' || value, 'reply', 'row ' || value, value, ?, '', '', '' "
                    "FROM json_each(?)", ME, T0, json.dumps(list(range(1, 231)))),
                feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0)]
        out = self.run_city(reqs)
        chat = out["responses"][1]["body"]["chat"]
        self.assertEqual(len(chat["rows"]), 200)
        self.assertEqual((chat["rows"][0]["k"], chat["rows"][-1]["k"], chat["cc"]), ("k31", "k230", 230))

    def test_messages_on_their_way_are_listed_until_the_machine_has_them(self):
        reqs = [lay_msg("c-sent", text="one", at=T0 + 1000), lay_msg("c-taken", text="two", at=T0 + 2000, state="taken"),
                lay_msg("c-queued", text="three", at=T0 + 3000, state="queued"),
                lay_msg("c-bare-queued", text="no row yet", at=T0 + 3100, state="queued"),
                lay_msg("c-bare-done", text="no row yet", at=T0 + 3200, state="delivered"),
                lay_msg("c-ended", text="four", at=T0 + 4000, state="undelivered", why="ended"),
                lay_msg("c-deaf", text="five", at=T0 + 4500, state="undelivered", why="not-listening"),
                lay_chat("c-deaf", kind="owner", text="five", at=45.0, state="undelivered", why="not-listening",
                         cid="c-deaf"),
                lay_msg("c-other", text="other window", to="s:other"), lay_msg("c-pc2", text="other machine", dev="pc2"),
                lay_chat("c-queued", kind="owner", text="three", at=40.0, state="queued", cid="c-queued"),
                feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0, now=T0 + 5000)]
        out = self.run_city(reqs)
        r = out["responses"][-1]
        chat = r["body"]["chat"]
        self.assertEqual(chat["msgs"],
                         [{"cid": "c-sent", "text": "one", "at": (T0 + 1000) / 1000, "state": "sent", "why": ""},
                          {"cid": "c-taken", "text": "two", "at": (T0 + 2000) / 1000, "state": "taken", "why": ""},
                          {"cid": "c-ended", "text": "four", "at": (T0 + 4000) / 1000, "state": "undelivered", "why": "ended"}])
        self.assertEqual([x["cid"] for x in chat["rows"]], ["c-queued", "c-deaf"],
                         "the machine has an entry for these two: each shows once, as the machine's own row")
        self.assertEqual(r["writes"], 0)

    def test_the_newest_fifty_messages_oldest_first(self):
        reqs = [lay_msg("c-%03d" % i, at=T0 + i, state="undelivered", why="ended") for i in range(60)]
        reqs += [feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0, now=T0 + 5000)]
        out = self.run_city(reqs)
        self.assertEqual([m["cid"] for m in out["responses"][-1]["body"]["chat"]["msgs"]],
                         ["c-%03d" % i for i in range(10, 60)])

    def test_a_poll_reads_through_the_indexes(self):
        reqs = [sql("INSERT INTO city_msg (user, cid, dev, pg, text, at, state, why) "
                    "SELECT ?, 'd' || value, 'mac', 's:tm1', 'x', ? + value, 'delivered', '' FROM json_each(?)",
                    ME, T0, json.dumps(list(range(300)))),
                sql("INSERT INTO city_chat (user, dev, pg, k, kind, text, at, ts, state, why, cid) "
                    "SELECT ?, 'mac', 's:tm1', 'd' || value, 'owner', 'x', value, ?, 'delivered', '', 'd' || value "
                    "FROM json_each(?)", ME, T0, json.dumps(list(range(200)))),
                lay_msg("c-sent", at=T0 + 1000),
                feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=200, now=T0 + 2000)]
        out = self.run_city(reqs)
        r = out["responses"][-1]
        self.assertEqual([m["cid"] for m in r["body"]["chat"]["msgs"]], ["c-sent"])
        plans = " | ".join(r["plans"])
        self.assertRegex(plans, r"city_msg_dev \(user=\? AND dev=\? AND state=\?\)",
                         "the messages of a window are found by state, not by reading every message: " + plans)
        self.assertRegex(plans, r"sqlite_autoindex_city_chat_1 \(user=\? AND dev=\? AND k=\?\)",
                         "the machine's row of a message is found by its key (k = cid): " + plans)
        self.assertNotRegex(plans, r"sqlite_autoindex_city_msg_1 \(user=\?\)(?! AND)")

    def test_only_what_the_update_changed_is_said_to_be_not_delivered(self):
        with open(ch.CITY, encoding="utf-8") as fh:
            src = " ".join(fh.read().split())
        updates = re.findall(r'UPDATE city_msg SET state = \'undelivered\'[^;]*?;', src)
        self.assertTrue(updates, "the statement that says not delivered was not found")
        for u in updates:
            self.assertIn("RETURNING", u, "show 'not delivered' only for the rows this UPDATE really changed")

    def test_sixty_seconds_and_nobody_took_it(self):
        reqs = [lay_msg("c-old", at=T0), lay_msg("c-new", at=T0 + 30000),
                feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0, now=T0 + 60000), sql(MSGS),
                feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0, now=T0 + 61000)]
        out = self.run_city(reqs)
        first = {m["cid"]: (m["state"], m["why"]) for m in out["responses"][2]["body"]["chat"]["msgs"]}
        self.assertEqual(first, {"c-old": ("undelivered", "off"), "c-new": ("sent", "")})
        stored = {m["cid"]: (m["state"], m["why"]) for m in out["responses"][3]["body"]}
        self.assertEqual(stored, first, "it is stored as not delivered, so no machine picks it up later")
        self.assertEqual(out["responses"][4]["writes"], 0, "nothing left to say: the next poll writes nothing")

    def test_the_reason_is_talk_off_when_the_machine_does_not_take_messages(self):
        head = machine(talk=False) + make_tables()
        out = self.run_city([lay_msg("c-old", at=T0), feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0, now=T0 + 60000)],
                            head=head)
        self.assertEqual(out["responses"][1]["body"]["chat"]["msgs"][0]["why"], "talk-off")

    def test_taken_and_silent_for_ten_minutes(self):
        reqs = [lay_msg("c-taken", at=T0, state="taken"), lay_msg("c-queued", at=T0, state="queued"),
                feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0, now=T0 + 599000),
                feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0, now=T0 + 600000)]
        out = self.run_city(reqs)
        early = {m["cid"]: m["state"] for m in out["responses"][2]["body"]["chat"]["msgs"]}
        late = {m["cid"]: (m["state"], m["why"]) for m in out["responses"][3]["body"]["chat"]["msgs"]}
        self.assertEqual(early, {"c-taken": "taken"})
        self.assertEqual(late, {"c-taken": ("undelivered", "off")})
        self.assertEqual(out["dump"]["city_msg"][1]["state"], "queued", "the machine holds a queued one: no time limit here")

    def test_another_machines_message_is_never_expired_by_my_window(self):
        out = self.run_city([lay_msg("c-pc2", dev="pc2", at=T0), lay_msg("c-oth", user=OTHER, at=T0),
                             feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0, now=T0 + 90000), sql(MSGS)])
        self.assertEqual({m["cid"]: m["state"] for m in self.msgs(out)}, {"c-pc2": "sent", "c-oth": "sent"})

    def test_no_talk_table_yet_is_an_empty_window(self):
        out = self.run_city([feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0)], head=machine())
        r = out["responses"][0]
        self.assertEqual(r["status"], 200, r)
        self.assertEqual(r["body"]["chat"], {"to": "s:tm1", "cc": 0, "rows": [], "msgs": []})

    def test_a_bad_window_id_is_no_window(self):
        for to in ("", "tm1", "../../x", "s:" + "x" * 121):
            out = self.run_city([feed(dev="mac", gen=1, after=0, chat=to, cc=0)])
            self.assertEqual(out["responses"][0]["status"], 200)
            self.assertNotIn("chat", out["responses"][0]["body"], to)

    def test_no_statement_reads_a_whole_talk_table(self):
        reqs = [lay_chat("k1"), lay_msg(CID), feed(dev="mac", gen=1, after=0, chat="s:tm1", cc=0, now=T0 + 70000),
                send(cid=cid(5), now=T0 + 71000)]
        out = self.run_city(reqs)
        scans = [s for s in out["full_scans"] if re.search(r"city_(msg|chat)", s["detail"]) and "CREATE" not in s["sql"]]
        self.assertEqual(scans, [])


if __name__ == "__main__":
    unittest.main()
