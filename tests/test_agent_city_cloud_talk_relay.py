"""Failing tests, cloud-city-2 slice S1: the relay Worker carries talk
(requirements/city.md, "Cloud page", step 2; approved design in agent_state.txt,
mock mock/cloud-city-2-mock.html).

bin/agent-city-relay.js. Everything of before stays: a sync without the talk
header is answered exactly as today, and nothing below happens for it.

  New secret on the relay: TALK_KEY (the owner sets it; unset or blank = talk
  is off for every machine). A machine with talk on sends, with its usual sync:
      header  X-City-Talk: <the talk key>
      body    "talk": {"chat": [...], "acks": [...]}        (both optional)
           or "talk": {"off": true}                          (talk turned off there)

  The reply's "talk":
      no X-City-Talk header              -> no "talk" key at all; body.talk is ignored
      header, but CITY_USER or TALK_KEY is not set (or blank) -> {"state": "off"}
      header, wrong key                  -> {"state": "refused"}
      header, right key                  -> {"state": "on", "msgs": [...]}
      header, right key, {"off": true}   -> {"state": "off"}  (after the clean-up below)
  The key is compared like the team key (same length, every character). The
  team key is never a talk key. "refused" and "off": nothing of body.talk is
  read, nothing is handed down, no talk table is touched or made.

  Tables (made on a talk-on sync, these exact lines: the City Worker makes
  the same ones, see tests/cloudhelp.py TALK_TABLES):
      city_msg  (user, cid, dev, pg, text, at, state, why)   PRIMARY KEY (user, cid)
          a message the owner typed on the cloud page. ONLY the City Worker
          inserts a row; the relay has no statement that inserts into city_msg.
      city_chat (id, user, dev, pg, k, kind, text, at, ts, state, why, cid)
          UNIQUE (user, dev, k); the copy of a machine's conversations.

  ORDER inside one talk-on sync: the acks, then the chat rows, then DOWN.

  DOWN, on a talk-on sync of machine DEV (user = CITY_USER), in this order:
      1. a 'sent' row of DEV older than 60 s (now - at >= 60000)  -> 'undelivered', why 'off'
         a 'taken' row of DEV older than 10 min (>= 600000)        -> 'undelivered', why 'off'
      2. the 'sent' rows of DEV become 'taken' (oldest first)
      3. "msgs" = the 'taken' rows of DEV, oldest first, at most 10:
         {"cid", "to" (the row's pg), "text", "age" (ms since the row's at)}
         and nothing else. A taken row is handed down again on every sync until
         the machine answers for it. More than 10 waiting: the rest stay 'sent'
         for the next sync.
      Each change of state is one guarded UPDATE, so a row that became
      'undelivered' is never handed down later.
      Rows of another machine or another user are never read or changed.

  ACKS, body.talk.acks = [{"cid", "state", "why"}], at most 50 are read:
      state 'queued' | 'delivered' | 'undelivered'; anything else is skipped.
      Only a row of THIS dev in state 'taken' or 'queued' changes (so
      delivered and undelivered are final, and a 'sent' row cannot be answered).
      why is kept only when it is one of: ended, not-listening, off, refused,
      flood; else ''.

  CHAT, body.talk.chat = rows, the first 20 are read:
      {"k" (1..64 of A-Z a-z 0-9 _ - . :), "to" (1..160 chars), "kind"
      ('prompt' | 'reply' | 'owner'), "text" (a string, cut at 8000
      characters), "at" (a number, the machine's seconds), "state" ('' |
      'queued' | 'delivered' | 'undelivered'; missing = ''), "why" (as above;
      missing = ''), "cid" (a string up to 64; missing = '')}
      A bad row is skipped, the others are kept, the sync stays ok.
      One row per (user, dev, k): the same row again writes nothing; a row
      whose state or why changed keeps its place in the table once (still one
      row) and gets a NEW id, higher than every id given before (the page's
      feed asks for "id > cursor"). ts = the relay's clock.
      After storing: rows of this user older than 7 days (ts) leave, and each
      conversation (dev + pg) touched keeps its 200 newest rows (by at, then id).

  FLAG: a view stored by a talk-on sync gets "talk": 1 in its counts; a view
      stored by any other sync has no talk (or 0). A "talk" the machine puts
      in its own counts is never copied.

  OFF, {"off": true} with the right key: this dev's city_chat rows are
      deleted, its city_msg rows in 'sent', 'taken' or 'queued' become
      'undelivered' / 'talk-off', and its city_view counts lose the talk flag.

  COST: a talk sync with nothing waiting and nothing sent writes no row. A
      full one (8 lines, a view with events, 20 chat rows, 10 acks, 10
      messages down) runs at most 40 statements (the free plan allows 50 per
      request), and no statement reads a whole talk table.

No test talks to Cloudflare. Run: python3 -m unittest tests.test_agent_city_cloud_talk_relay
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
from cloudhelp import KEY, ME, OTHER, T0, TALK, TALK_ENV, lay_chat, lay_msg, make_tables, snapshot, sql, sync, view  # noqa: E402

MSGS = "SELECT cid, dev, state, why FROM city_msg ORDER BY cid"
CHATS = "SELECT id, user, dev, pg, k, kind, text, at, ts, state, why, cid FROM city_chat ORDER BY id"


def tsync(dev="mac", talk=None, now=T0, **kw):
    """A sync with the right talk key."""
    kw.setdefault("talk_key", TALK)
    return sync(dev, talk=talk, now=now, **kw)


def row(k, text="hi", to="s:tm1", kind="reply", at=1.0, **more):
    out = {"k": k, "to": to, "kind": kind, "text": text, "at": at}
    out.update(more)
    return out


@unittest.skipUnless(NODE, SKIP_REASON)
class RelayCase(unittest.TestCase):
    def run_relay(self, reqs, env=None, tables=True):
        head = make_tables() if tables else []
        out = ch.run_cloud(self, head + list(reqs), relay_env=TALK_ENV if env is None else env, city="-")
        out["responses"] = out["responses"][len(head):]
        return out

    def bodies(self, out):
        for r in out["responses"]:
            self.assertEqual(r["status"], 200, r)
        return [r["body"] for r in out["responses"]]


class TestTalkKey(RelayCase):
    def test_no_header_is_the_relay_of_before(self):
        out = self.run_relay([sync("mac", talk={"chat": [row("k1")]})], tables=False)
        body = self.bodies(out)[0]
        self.assertNotIn("talk", body)
        self.assertEqual(set(body), {"ok", "seq", "lines", "city", "gen"})
        self.assertNotIn("city_chat", out["dump"], "no talk table is made for a sync without the header")
        self.assertNotIn("city_msg", out["dump"])

    def test_right_key_is_on(self):
        out = self.run_relay([tsync()], tables=False)
        self.assertEqual(self.bodies(out)[0]["talk"], {"state": "on", "msgs": []})
        self.assertIn("city_chat", out["dump"], "a talk-on sync makes the tables")
        self.assertIn("city_msg", out["dump"])

    def test_the_tables_are_the_agreed_ones(self):
        out = self.run_relay([tsync(), sql("SELECT name, sql FROM sqlite_master WHERE name IN ('city_msg', 'city_chat')")],
                             tables=False)
        made = {r["name"]: " ".join(r["sql"].split()) for r in out["responses"][-1]["body"]}
        norm = lambda s: " ".join(s.replace("IF NOT EXISTS ", "").split())  # noqa: E731
        self.assertEqual(made.get("city_msg"), norm(ch.MSG_SQL))
        self.assertEqual(made.get("city_chat"), norm(ch.CHAT_SQL))

    def test_wrong_key_is_refused_and_nothing_happens(self):
        reqs = [lay_msg("c1"),
                sync("mac", talk={"chat": [row("k1")], "acks": [{"cid": "c1", "state": "delivered"}]},
                     talk_key="not-the-key-not-the-key-0000"),
                sql(MSGS), sql(CHATS)]
        out = self.run_relay(reqs)
        self.assertEqual(out["responses"][1]["body"]["talk"], {"state": "refused"})
        self.assertEqual(out["responses"][2]["body"], [{"cid": "c1", "dev": "mac", "state": "sent", "why": ""}])
        self.assertEqual(out["responses"][3]["body"], [])
        self.assertEqual(out["responses"][1]["writes"], 0)

    def test_the_team_key_is_not_a_talk_key(self):
        out = self.run_relay([lay_msg("c1"), sync("mac", talk_key=KEY), sql(MSGS)])
        self.assertEqual(out["responses"][1]["body"]["talk"], {"state": "refused"})
        self.assertEqual(out["responses"][2]["body"][0]["state"], "sent")

    def test_no_talk_key_on_the_relay_is_off(self):
        for env in ({"TEAM_KEY": KEY, "CITY_USER": ME}, {"TEAM_KEY": KEY, "CITY_USER": ME, "TALK_KEY": "  "},
                    {"TEAM_KEY": KEY, "TALK_KEY": TALK}):
            out = self.run_relay([lay_msg("c1"), tsync(talk={"chat": [row("k1")]}), sql(MSGS), sql(CHATS)], env=env)
            self.assertEqual(out["responses"][1]["body"]["talk"], {"state": "off"}, env)
            self.assertEqual(out["responses"][2]["body"][0]["state"], "sent")
            self.assertEqual(out["responses"][3]["body"], [])

    def test_a_blank_header_never_matches_a_blank_key(self):
        out = self.run_relay([sync("mac", talk_key="")], env={"TEAM_KEY": KEY, "CITY_USER": ME, "TALK_KEY": ""})
        talk = self.bodies(out)[0].get("talk")
        self.assertIn(talk, (None, {"state": "off"}))


class TestDown(RelayCase):
    def test_a_message_is_handed_to_its_machine(self):
        out = self.run_relay([lay_msg("c1", text="先跑测试", to="s:tm1", at=T0), tsync(now=T0 + 4000), sql(MSGS)])
        self.assertEqual(out["responses"][1]["body"]["talk"],
                         {"state": "on", "msgs": [{"cid": "c1", "to": "s:tm1", "text": "先跑测试", "age": 4000}]})
        self.assertEqual(out["responses"][2]["body"][0]["state"], "taken")

    def test_handed_down_again_until_the_machine_answers(self):
        reqs = [lay_msg("c1"), tsync(now=T0 + 1000), tsync(now=T0 + 6000),
                tsync(now=T0 + 11000, talk={"acks": [{"cid": "c1", "state": "queued"}]}),
                tsync(now=T0 + 16000), sql(MSGS),
                tsync(now=T0 + 21000, talk={"acks": [{"cid": "c1", "state": "delivered"}]}), sql(MSGS)]
        out = self.run_relay(reqs)
        r = out["responses"]
        self.assertEqual([m["cid"] for m in r[1]["body"]["talk"]["msgs"]], ["c1"])
        self.assertEqual([m["cid"] for m in r[2]["body"]["talk"]["msgs"]], ["c1"], "no answer yet: again")
        self.assertEqual(r[3]["body"]["talk"]["msgs"], [], "answered in this sync: not handed again")
        self.assertEqual(r[4]["body"]["talk"]["msgs"], [])
        self.assertEqual(r[5]["body"][0]["state"], "queued")
        self.assertEqual(r[7]["body"][0]["state"], "delivered")

    def test_only_for_the_machine_of_the_sync(self):
        out = self.run_relay([lay_msg("c1", dev="mac"), tsync(dev="pc2", now=T0 + 1000), sql(MSGS)])
        self.assertEqual(out["responses"][1]["body"]["talk"]["msgs"], [])
        self.assertEqual(out["responses"][2]["body"][0]["state"], "sent", "another machine's sync changes nothing")

    def test_another_users_row_is_never_touched(self):
        out = self.run_relay([lay_msg("c1", user=OTHER), tsync(now=T0 + 1000), tsync(now=T0 + 70000), sql(MSGS)])
        self.assertEqual(out["responses"][1]["body"]["talk"]["msgs"], [])
        self.assertEqual(out["responses"][3]["body"][0]["state"], "sent")

    def test_not_picked_up_in_60_seconds_is_not_delivered_for_good(self):
        reqs = [lay_msg("late", at=T0), lay_msg("just", at=T0 + 1000),
                tsync(now=T0 + 60000), sql(MSGS), tsync(now=T0 + 65000)]
        out = self.run_relay(reqs)
        self.assertEqual([m["cid"] for m in out["responses"][2]["body"]["talk"]["msgs"]], ["just"])
        rows = {r["cid"]: (r["state"], r["why"]) for r in out["responses"][3]["body"]}
        self.assertEqual(rows, {"late": ("undelivered", "off"), "just": ("taken", "")})
        self.assertEqual([m["cid"] for m in out["responses"][4]["body"]["talk"]["msgs"]], ["just"],
                         "an undelivered message is never handed down later")

    def test_taken_with_no_word_for_10_minutes_is_not_delivered(self):
        reqs = [lay_msg("c1", at=T0), tsync(now=T0 + 1000), tsync(now=T0 + 599000),
                tsync(now=T0 + 600000), sql(MSGS)]
        out = self.run_relay(reqs)
        self.assertEqual(len(out["responses"][2]["body"]["talk"]["msgs"]), 1)
        self.assertEqual(out["responses"][3]["body"]["talk"]["msgs"], [])
        self.assertEqual(out["responses"][4]["body"], [{"cid": "c1", "dev": "mac", "state": "undelivered", "why": "off"}])

    def test_a_queued_message_waits_as_long_as_the_session_is_busy(self):
        reqs = [lay_msg("c1", at=T0), tsync(now=T0 + 1000),
                tsync(now=T0 + 2000, talk={"acks": [{"cid": "c1", "state": "queued"}]}),
                tsync(now=T0 + 3600000), sql(MSGS)]
        out = self.run_relay(reqs)
        self.assertEqual(out["responses"][4]["body"][0]["state"], "queued", "the machine holds it: no time limit here")

    def test_at_most_ten_a_sync_oldest_first(self):
        reqs = [lay_msg("c%02d" % i, at=T0 + i) for i in range(12)]
        reqs += [tsync(now=T0 + 1000), sql(MSGS),
                 tsync(now=T0 + 2000, talk={"acks": [{"cid": "c%02d" % i, "state": "delivered"} for i in range(10)]}),
                 sql(MSGS)]
        out = self.run_relay(reqs)
        r = out["responses"]
        self.assertEqual([m["cid"] for m in r[12]["body"]["talk"]["msgs"]], ["c%02d" % i for i in range(10)])
        states = [x["state"] for x in r[13]["body"]]
        self.assertEqual(states, ["taken"] * 10 + ["sent"] * 2)
        self.assertEqual([m["cid"] for m in r[14]["body"]["talk"]["msgs"]], ["c10", "c11"])
        self.assertEqual([x["state"] for x in r[15]["body"]], ["delivered"] * 10 + ["taken"] * 2)

    def test_a_message_carries_four_fields_only(self):
        out = self.run_relay([lay_msg("c1"), tsync(now=T0 + 1)])
        self.assertEqual(set(out["responses"][1]["body"]["talk"]["msgs"][0]), {"cid", "to", "text", "age"})


class TestAcks(RelayCase):
    def answer(self, lay, ack, dev="mac", key=TALK, before=()):
        reqs = [lay] + list(before) + [sync(dev, talk={"acks": [ack]}, talk_key=key, now=T0 + 5000), sql(MSGS)]
        out = self.run_relay(reqs)
        return out["responses"][-1]["body"][0]

    def test_final_answers(self):
        got = self.answer(lay_msg("c1"), {"cid": "c1", "state": "delivered"}, before=[tsync(now=T0 + 1000)])
        self.assertEqual((got["state"], got["why"]), ("delivered", ""))
        for why in ("ended", "not-listening", "off", "refused", "flood"):
            got = self.answer(lay_msg("c1"), {"cid": "c1", "state": "undelivered", "why": why},
                              before=[tsync(now=T0 + 1000)])
            self.assertEqual((got["state"], got["why"]), ("undelivered", why))

    def test_an_unknown_reason_is_dropped(self):
        got = self.answer(lay_msg("c1"), {"cid": "c1", "state": "undelivered", "why": "<script>x</script>"},
                          before=[tsync(now=T0 + 1000)])
        self.assertEqual((got["state"], got["why"]), ("undelivered", ""))

    def test_a_row_never_taken_cannot_be_answered(self):
        got = self.answer(lay_msg("c1", dev="pc2"), {"cid": "c1", "state": "delivered"}, dev="pc2",
                          key="wrong-wrong-wrong-wrong-0000")
        self.assertEqual(got["state"], "sent")
        out = self.run_relay([lay_msg("c1", at=T0 + 4000),
                              sync("pc2", talk={"acks": [{"cid": "c1", "state": "delivered"}]}, talk_key=TALK,
                                   now=T0 + 5000), sql(MSGS)])
        self.assertEqual(out["responses"][-1]["body"][0]["state"], "sent", "another machine's answer changes nothing")

    def test_only_three_states_can_be_answered(self):
        for state in ("sent", "taken", "done", "", None, 7):
            got = self.answer(lay_msg("c1"), {"cid": "c1", "state": state}, before=[tsync(now=T0 + 1000)])
            self.assertEqual(got["state"], "taken", state)

    def test_delivered_and_undelivered_are_final(self):
        for first, second in (("delivered", "undelivered"), ("undelivered", "delivered"), ("delivered", "queued")):
            out = self.run_relay([lay_msg("c1"), tsync(now=T0 + 1000),
                                  tsync(now=T0 + 2000, talk={"acks": [{"cid": "c1", "state": first}]}),
                                  tsync(now=T0 + 3000, talk={"acks": [{"cid": "c1", "state": second}]}), sql(MSGS)])
            self.assertEqual(out["responses"][-1]["body"][0]["state"], first)

    def test_bad_acks_never_break_the_sync(self):
        acks = ["x", None, {}, {"cid": 5, "state": "delivered"}, {"cid": "nobody", "state": "delivered"}]
        out = self.run_relay([tsync(talk={"acks": acks}), tsync(talk={"acks": "nope"}), tsync(talk="nope"),
                              tsync(talk={"chat": {"k": 1}})])
        for body in self.bodies(out):
            self.assertEqual(body["talk"]["state"], "on")


class TestChat(RelayCase):
    def test_rows_are_kept_for_this_user_and_machine(self):
        rows = [row("k1", "先写测试", kind="prompt", at=10.5),
                row("k2", "收到", kind="reply", at=11.0),
                row("cid-aaaaaaaaaaaaaaaa", "go on", kind="owner", at=12.0, state="queued", cid="cid-aaaaaaaaaaaaaaaa")]
        out = self.run_relay([tsync(talk={"chat": rows}, now=T0 + 7), sql(CHATS)])
        got = out["responses"][1]["body"]
        self.assertEqual([(g["user"], g["dev"], g["pg"], g["k"], g["kind"], g["text"], g["at"], g["ts"], g["state"],
                           g["why"], g["cid"]) for g in got],
                         [(ME, "mac", "s:tm1", "k1", "prompt", "先写测试", 10.5, T0 + 7, "", "", ""),
                          (ME, "mac", "s:tm1", "k2", "reply", "收到", 11.0, T0 + 7, "", "", ""),
                          (ME, "mac", "s:tm1", "cid-aaaaaaaaaaaaaaaa", "owner", "go on", 12.0, T0 + 7, "queued", "",
                           "cid-aaaaaaaaaaaaaaaa")])

    def test_the_same_row_again_writes_nothing(self):
        rows = [row("k1"), row("k2", state="delivered", kind="owner")]
        out = self.run_relay([tsync(talk={"chat": rows}), tsync(talk={"chat": rows}, now=T0 + 5000), sql(CHATS)])
        self.assertEqual(out["responses"][1]["writes"], 0, "a sync sent twice (a lost reply) must not write again")
        self.assertEqual([g["k"] for g in out["responses"][2]["body"]], ["k1", "k2"])

    def test_a_change_of_state_updates_the_row_and_gives_a_new_id(self):
        out = self.run_relay([tsync(talk={"chat": [row("k1"), row("m1", kind="owner", state="queued"), row("k3")]}),
                              sql(CHATS),
                              tsync(talk={"chat": [row("m1", kind="owner", state="delivered")]}, now=T0 + 5000),
                              sql(CHATS)])
        before, after = out["responses"][1]["body"], out["responses"][3]["body"]
        self.assertEqual(sorted(g["k"] for g in after), ["k1", "k3", "m1"], "still one row for m1")
        m1 = [g for g in after if g["k"] == "m1"][0]
        self.assertEqual(m1["state"], "delivered")
        self.assertGreater(m1["id"], max(g["id"] for g in before), "a changed row must pass every cursor handed out")
        self.assertEqual({g["k"]: g["id"] for g in after if g["k"] != "m1"},
                         {g["k"]: g["id"] for g in before if g["k"] != "m1"}, "the rows that did not change keep their id")

    def test_bad_rows_are_skipped_the_rest_is_kept(self):
        rows = [row("ok1"), "x", None, {"k": "nokind", "to": "s:1", "text": "x", "at": 1},
                row("", "x"), row("bad key!", "x"), row("k" * 65, "x"), row("badkind", kind="note"),
                row("notext", text=7), row("noat", at="soon"), row("badto", to=""), row("longto", to="s:" + "x" * 200),
                row("badstate", state="sent"), row("badstate2", state="taken"), row("ok2", why="nonsense")]
        out = self.run_relay([tsync(talk={"chat": rows}), sql(CHATS)])
        self.assertEqual(out["responses"][0]["body"]["talk"]["state"], "on")
        got = out["responses"][1]["body"]
        self.assertEqual([g["k"] for g in got], ["ok1", "ok2"])
        self.assertEqual(got[1]["why"], "", "an unknown reason is dropped, the row is kept")

    def test_long_text_is_cut(self):
        out = self.run_relay([tsync(talk={"chat": [row("k1", "字" * 9000)]}), sql(CHATS)])
        self.assertEqual(out["responses"][1]["body"][0]["text"], "字" * 8000)

    def test_twenty_rows_a_sync(self):
        rows = [row("k%02d" % i, at=float(i)) for i in range(25)]
        out = self.run_relay([tsync(talk={"chat": rows}), sql("SELECT COUNT(*) AS n FROM city_chat")])
        self.assertEqual(out["responses"][1]["body"][0]["n"], 20)

    def test_each_machine_has_its_own_rows(self):
        out = self.run_relay([tsync("mac", talk={"chat": [row("k1", "from mac")]}),
                              tsync("pc2", talk={"chat": [row("k1", "from pc2")]}), sql(CHATS)])
        self.assertEqual([(g["dev"], g["text"]) for g in out["responses"][2]["body"]],
                         [("mac", "from mac"), ("pc2", "from pc2")])

    def test_two_hundred_rows_a_conversation(self):
        reqs = []
        for batch in range(11):
            rows = [row("k%03d" % (batch * 20 + i), at=float(batch * 20 + i)) for i in range(20)]
            reqs.append(tsync(talk={"chat": rows}, now=T0 + batch * 5000))
        reqs.insert(0, tsync(talk={"chat": [row("other", to="s:other", at=0.5)]}))
        reqs += [sql("SELECT pg, COUNT(*) AS n, MIN(at) AS first FROM city_chat GROUP BY pg ORDER BY pg")]
        out = self.run_relay(reqs)
        self.assertEqual(out["responses"][-1]["body"],
                         [{"pg": "s:other", "n": 1, "first": 0.5}, {"pg": "s:tm1", "n": 200, "first": 20.0}],
                         "220 rows in one conversation: the 20 oldest left; the other conversation is untouched")

    def test_rows_leave_after_seven_days(self):
        week = 7 * 24 * 3600 * 1000
        out = self.run_relay([tsync(talk={"chat": [row("old", to="s:a")]}, now=T0),
                              tsync(talk={"chat": [row("mid", to="s:a")]}, now=T0 + week - 1000),
                              tsync(talk={"chat": [row("new", to="s:b")]}, now=T0 + week), sql(CHATS)])
        self.assertEqual([g["k"] for g in out["responses"][-1]["body"]], ["mid", "new"])

    def test_chat_rows_never_touch_a_message(self):
        out = self.run_relay([lay_msg("c1"), tsync(talk={"chat": [row("c1", kind="owner", state="delivered", cid="c1")]},
                                                   now=T0 + 1),
                              sql(MSGS)])
        self.assertEqual(out["responses"][-1]["body"][0]["state"], "taken",
                         "only an ack answers for a message; the chat row is the history")


class TestFlag(RelayCase):
    COUNTS = "SELECT dev, counts FROM city_view ORDER BY dev"

    def test_a_talk_sync_marks_its_view(self):
        v = view(1, snap=[snapshot()])
        out = self.run_relay([tsync("mac", view=v), sync("pc2", view=view(1, snap=[snapshot()], label="pc2")),
                              sql(self.COUNTS)])
        got = {r["dev"]: json.loads(r["counts"]) for r in out["responses"][2]["body"]}
        self.assertEqual(got["mac"].get("talk"), 1)
        self.assertFalse(got["pc2"].get("talk"))

    def test_the_flag_goes_when_talk_goes(self):
        out = self.run_relay([tsync("mac", view=view(1, snap=[snapshot()])),
                              sync("mac", view=view(1), now=T0 + 60000), sql(self.COUNTS)])
        self.assertFalse(json.loads(out["responses"][2]["body"][0]["counts"]).get("talk"))

    def test_a_machine_cannot_set_the_flag_itself(self):
        v = view(1, snap=[snapshot()], counts={"people": 1, "busy": 1, "wait": 0, "talk": 1})
        for req in (sync("mac", view=v), sync("mac", view=v, talk_key="wrong-key-wrong-key-00000")):
            out = self.run_relay([req, sql(self.COUNTS)])
            self.assertEqual(out["responses"][0]["status"], 200, out["responses"][0])
            self.assertFalse(json.loads(out["responses"][1]["body"][0]["counts"]).get("talk"))


class TestOff(RelayCase):
    def test_off_cleans_this_machine_only(self):
        reqs = [tsync("mac", view=view(1, snap=[snapshot()]), talk={"chat": [row("k1"), row("k2")]}),
                tsync("pc2", talk={"chat": [row("k1")]}),
                lay_msg("c-sent"), lay_msg("c-queued", state="queued"), lay_msg("c-done", state="delivered"),
                lay_msg("c-pc2", dev="pc2"),
                tsync("mac", talk={"off": True}, now=T0 + 1000),
                sql(CHATS), sql(MSGS), sql("SELECT counts FROM city_view WHERE dev = 'mac'")]
        out = self.run_relay(reqs)
        r = out["responses"]
        self.assertEqual(r[6]["body"]["talk"], {"state": "off"})
        self.assertEqual([(g["dev"], g["k"]) for g in r[7]["body"]], [("pc2", "k1")])
        self.assertEqual({x["cid"]: (x["state"], x["why"]) for x in r[8]["body"]},
                         {"c-sent": ("undelivered", "talk-off"), "c-queued": ("undelivered", "talk-off"),
                          "c-done": ("delivered", ""), "c-pc2": ("sent", "")})
        self.assertFalse(json.loads(r[9]["body"][0]["counts"]).get("talk"))

    def test_off_needs_the_key(self):
        out = self.run_relay([tsync(talk={"chat": [row("k1")]}),
                              sync("mac", talk={"off": True}, talk_key="wrong-key-wrong-key-00000"),
                              sync("mac", talk={"off": True}), sql(CHATS)])
        self.assertEqual(len(out["responses"][-1]["body"]), 1)


class TestTeamKeyAlone(RelayCase):
    """T5 (f): the team key alone never makes a message and never reads one."""

    def test_the_relay_has_no_statement_that_makes_a_message(self):
        with open(ch.RELAY, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotRegex(src, r"(?is)INSERT\s+(OR\s+\w+\s+)?INTO\s+city_msg",
                            "only the City Worker (the owner's login) inserts a message")
        self.assertNotRegex(src, r"(?is)REPLACE\s+INTO\s+city_msg")

    def test_a_member_cannot_make_or_take_a_message(self):
        forged = {"msgs": [{"cid": "evil", "to": "s:tm1", "text": "rm -rf"}],
                  "chat": [row("evil", kind="owner", state="sent", cid="evil")],
                  "acks": [{"cid": "c1", "state": "delivered"}],
                  "send": {"dev": "mac", "to": "s:tm1", "text": "rm -rf", "cid": "evil"}}
        lines = [{"ev": "PostToolUse", "sid": "s1", "cid": "evil", "to": "s:tm1", "text": "rm -rf", "talk": forged}]
        reqs = [lay_msg("c1", dev="mac"),
                sync("mac", lines=lines, talk=forged),                  # the team key, posing as mac
                sync("pc2", lines=lines, talk=forged, now=T0 + 1000),   # the team key, its own machine
                tsync("mac", now=T0 + 2000), sql(MSGS), sql(CHATS)]
        out = self.run_relay(reqs)
        r = out["responses"]
        for body in (r[1]["body"], r[2]["body"]):
            self.assertNotIn("talk", body)
            self.assertNotIn("hello", json.dumps(body), "the owner's text never goes out without the talk key")
        self.assertEqual([m["cid"] for m in r[3]["body"]["talk"]["msgs"]], ["c1"],
                         "the real machine still gets the owner's message, and only that one")
        self.assertEqual([x["cid"] for x in r[4]["body"]], ["c1"], "no message was made")
        self.assertEqual(r[5]["body"], [], "no chat row was stored without the talk key")

    def test_a_talk_machine_cannot_make_a_message_for_another_machine_either(self):
        forged = {"chat": [row("evil", kind="owner", state="queued", cid="evil", to="s:victim")],
                  "acks": [{"cid": "evil", "state": "queued"}], "msgs": [{"cid": "evil", "to": "s:victim", "text": "x"}]}
        out = self.run_relay([tsync("pc2", talk=forged), tsync("mac", now=T0 + 1000), sql(MSGS)])
        self.assertEqual(out["responses"][1]["body"]["talk"]["msgs"], [])
        self.assertEqual(out["responses"][2]["body"], [])


class TestCost(RelayCase):
    def full(self):
        lines = [{"ev": "PostToolUse", "sid": "s1", "tool": "Bash", "rid": "github.com/o/r"}] * 8
        v1 = view(1, snap=[snapshot()])
        v2 = view(1, events=[{"type": "tool", "id": "s:1", "tool": "Bash", "name": "Bash"}] * 8)
        reqs = [tsync(view=v1, lines=lines)]
        reqs += [lay_msg("old%02d" % i, at=T0 + i) for i in range(10)]
        reqs += [tsync(now=T0 + 1000)]
        reqs += [lay_msg("new%02d" % i, at=T0 + 2000 + i) for i in range(10)]
        talk = {"chat": [row("k%02d" % i, at=float(i)) for i in range(20)],
                "acks": [{"cid": "old%02d" % i, "state": "delivered"} for i in range(10)]}
        reqs += [tsync(view=v2, lines=lines, talk=talk, now=T0 + 5000)]
        return self.run_relay(reqs)

    def test_a_full_sync_fits_the_free_plans_fifty_statements(self):
        out = self.full()
        last = out["responses"][-1]
        self.assertEqual(last["status"], 200, last)
        self.assertEqual(len(last["body"]["talk"]["msgs"]), 10)
        self.assertLessEqual(last["stmts"], 40, "%d statements in one sync (the free plan stops at 50)" % last["stmts"])

    def test_no_statement_reads_a_whole_talk_table(self):
        out = self.full()
        scans = [s for s in out["full_scans"] if re.search(r"city_(msg|chat)", s["detail"]) and "CREATE" not in s["sql"]]
        self.assertEqual(scans, [])

    def test_a_quiet_talk_sync_writes_nothing(self):
        out = self.run_relay([tsync(), tsync(now=T0 + 5000), tsync(now=T0 + 10000)])
        self.assertEqual([r["writes"] for r in out["responses"][1:]], [0, 0])
        self.assertLessEqual(out["responses"][2]["stmts"], 16)


if __name__ == "__main__":
    unittest.main()
