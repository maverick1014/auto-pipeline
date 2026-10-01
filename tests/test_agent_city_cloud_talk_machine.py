"""Failing tests, cloud-city-2 slice S4: the machine takes a cloud message
into its normal chat queue and sends its conversations up
(requirements/city.md, "Cloud page", step 2; approved design in agent_state.txt).

bin/agent_city.py, in the "cloud-city" block(s). Needs slice S3
(bin/agent_city_relay.py: the hub calls talk_take / talk_sent / talk_soon).

  CityState(..., cloud_seen_path=None)
  CityState.cloud_message(cid, to, text, age_ms, terrs, now) -> {"cid", "state"[, "why"]}
      One message the owner typed on the cloud page. TERRS = the territory
      ids of the repos joined to the relay it came from. It is TEXT for a
      session's normal chat queue and nothing else: the only thing it ever
      calls is chat_send(to, text, now). No part of it reaches a shell, a
      path, a flag or the server's options.
        cid seen before (this run, or in the seen file) -> never queued again:
            its entry is still in a window -> that entry's state (and why);
            the seen file says it was delivered -> "delivered";
            else -> "undelivered", why "off" (it was lost in a restart)
        text is not a string, is empty or longer than CHAT_TEXT_MAX,
        to is not a string, or does not start with "s:" or "gov:"
            (a path, a subagent's id, a guest "r:" / "rg:")   -> "undelivered", why "refused"
        age_ms over 600000 (10 min)                            -> "undelivered", why "off"
        "s:<sid>": no such session now, or it ended            -> "undelivered", why "ended"
        "s:<sid>" of a territory not in TERRS, "gov:<terr>" with terr not in
            TERRS (a repo that is not joined to that relay)    -> "undelivered", why "refused"
        more than 60 cloud messages in the last 600 s          -> "undelivered", why "flood"
        else chat_send: the entry is the local page's entry plus "cid":
            "queued", or "undelivered" / "not-listening" exactly as locally
      Every cid is written to cloud_seen_path (one JSON line, {"cid"}, mode
      0600) BEFORE anything is queued; a delivered cloud message adds a line
      {"cid", "done": 1}. Never the text. A refused, late, ended or flood
      message queues nothing, changes no window and sends no page event.
      A delivered cloud message is logged in decisions.jsonl like a local
      one, with "via": "cloud".

  CloudUploader gains (the hub's talk source):
      talk_take(host, rids, now) -> {"chat": [...], "acks": [...]} (a key is
          left out when its list is empty), or None when there is nothing
        chat: the "chat" page messages of the windows of repos JOINED to
          that relay, as rows {"k", "to", "kind", "text", "at", "state",
          "why", "cid"}: at most 20 a sync, a text cut at 8000 characters.
          k = the entry's cid when it has one, else a hash of to + kind + at
          + text (so the same entry always has the same key, also after a
          restart). The first talk sync of a run sends the windows as they
          are (the relay keeps one row per key). A change of state sends the
          row again, same k. A window of a repo that is not joined never goes.
        acks: {"cid", "state"[, "why"]} for every cloud message handed down,
          and again whenever its entry changes state (queued -> delivered).
          An ack for a message that has an entry ALWAYS rides in the same
          sync as that entry's chat row (k = cid, the same state): the cloud
          page stops listing the message the moment it is answered, and
          shows the machine's row instead.
      talk_sent(host, talk, now): talk None (relay down) or not {"state":
          "on"} -> what was just sent is sent again next time; "on" -> its
          "msgs" go to cloud_message, at most 10, only the fields cid, to,
          text, age are read.
      talk_soon(host) -> True while an ack waits to go up.
      Chat rows ride ONLY in talk: a view never holds a "chat" message
      (CLOUD_DROP stays as it is).
  serve: CityState gets cloud_seen_path=<city dir>/cloud-seen; the hub gets
      talk_file=<AGENT_CITY_HOME>/cloud-talk.

Every test uses a fake relay on 127.0.0.1 and temp folders. Never a real key.

Run: python3 -m unittest tests.test_agent_city_cloud_talk_machine </dev/null
"""

import http.client
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

from relayhelp import hook_line, make_repo  # noqa: E402
from test_agent_city_server import wait_for  # noqa: E402
from test_agent_city_cloud_upload import UploadCase  # noqa: E402
from cityhelp import Mains  # noqa: E402
import agent_city as ac  # noqa: E402

TALK = "fake-talk-key-for-tests-0002"
REPO = "/r/shop/.git"
REPO2 = "/r/other/.git"
MARK = "MARK-talk-5c1d"


def line(ev, sid, aid="", role="", tool="Read", at="", repo=REPO):
    return {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": "shop", "role": role,
            "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}


# ------------------------------------------------------------ cloud_message

class MessageCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_talk_")
        self.chat_path = os.path.join(self.base, "chat.jsonl")
        self.decisions = os.path.join(self.base, "decisions.jsonl")
        self.seen = os.path.join(self.base, "cloud-seen")
        self.state = self.make()
        self.terr = ac.territory_id(REPO)
        self.terrs = {self.terr}
        self.now = 1_800_000_000.0

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def make(self):
        try:
            return ac.CityState(decisions_path=self.decisions, world_path=None, chat_path=self.chat_path,
                                count_fn=lambda i: 0, balance_fn=lambda i, r: {"kinds": {}, "files": {}, "bad": []},
                                main_fn=Mains({REPO: "g1"}), cloud_seen_path=self.seen)
        except TypeError as exc:
            self.fail("CityState takes no cloud_seen_path yet: %s" % exc)

    def feed(self, *lines):
        for obj in lines:
            self.state.feed_line(obj, time.monotonic())

    def team(self):
        """A governor g1 (idle), a task manager tm1 (busy), its worker a9; a session x1 in another repo (busy)."""
        self.feed(line("UserPromptSubmit", "g1"), line("Stop", "g1"),
                  line("UserPromptSubmit", "tm1", role="task-manager"),
                  line("PostToolUse", "tm1", aid="a9", at="worker", role="task-manager"),
                  line("UserPromptSubmit", "x1", role="task-manager", repo=REPO2))

    def say(self, cid, to="s:tm1", text="go on", age=1000, terrs=None, now=None):
        self.assertTrue(hasattr(self.state, "cloud_message"), "CityState.cloud_message is missing")
        self.now += 1.0
        return self.state.cloud_message(cid, to, text, age, self.terrs if terrs is None else terrs,
                                        self.now if now is None else now)

    def entries(self, to="s:tm1"):
        return self.state.chat_view(to)[1].get("entries", [])

    def all_entries(self):
        with self.state.lock:
            return sum(len(bucket) for bucket in self.state.chat.values())

    def client(self):
        c = self.state.add_client()
        while not c.queue.empty():
            c.queue.get_nowait()
        return c

    @staticmethod
    def chat_events(client):
        out = []
        while not client.queue.empty():
            raw = client.queue.get_nowait().decode("utf-8")
            if "data:" in raw:
                msg = json.loads(raw.split("data:", 1)[1])
                if msg.get("type") == "chat":
                    out.append(msg)
        return out

    def seen_lines(self):
        try:
            with open(self.seen, encoding="utf-8") as fh:
                return [json.loads(l) for l in fh if l.strip()]
        except OSError:
            return []


class TestQueued(MessageCase):
    def test_it_goes_into_the_normal_queue(self):
        self.team()
        page = self.client()
        got = self.say("cid-0001", text="请先跑测试 7731")
        self.assertEqual(got, {"cid": "cid-0001", "state": "queued"})
        entry = self.entries()[-1]
        self.assertEqual((entry["kind"], entry["text"], entry["state"], entry["cid"]),
                         ("owner", "请先跑测试 7731", "queued", "cid-0001"))
        self.assertLessEqual(set(entry), {"id", "kind", "text", "at", "state", "cid", "why"})
        events = self.chat_events(page)
        self.assertEqual([(e["to"], e["entry"]["cid"]) for e in events], [("s:tm1", "cid-0001")],
                         "the local page shows it at once, like its own message")

    def test_the_session_gets_it_like_a_local_message(self):
        self.team()
        self.say("cid-0001", text="请先跑测试 7731")
        self.feed(line("Stop", "tm1", role="task-manager"))
        got = self.state.chat_next("tm1", "w1", 2.0)
        self.assertEqual((got["state"], got["text"]), ("message", "请先跑测试 7731"))
        entry = self.entries()[-1]
        self.assertEqual((entry["state"], entry["cid"]), ("delivered", "cid-0001"))
        with open(self.decisions, encoding="utf-8") as fh:
            row = json.loads(fh.read().strip().splitlines()[-1])
        self.assertEqual((row["by"], row["verb"], row["sid"], row["text"], row.get("via")),
                         ("owner", "message", "tm1", "请先跑测试 7731", "cloud"))
        self.assertIn({"cid": "cid-0001", "done": 1}, self.seen_lines())

    def test_a_local_message_has_no_via(self):
        self.team()
        self.state.chat_send("s:tm1", "from the local page", self.now)
        self.feed(line("Stop", "tm1", role="task-manager"))
        self.state.chat_next("tm1", "w1", 2.0)
        with open(self.decisions, encoding="utf-8") as fh:
            row = json.loads(fh.read().strip().splitlines()[-1])
        self.assertNotIn("via", row)
        self.assertNotIn("cid", self.entries()[-1])

    def test_the_governor_window(self):
        self.team()
        got = self.say("cid-0002", to="gov:" + self.terr, text="hello governor")
        self.assertIn(got["state"], ("queued", "undelivered"))
        entry = self.entries("gov:" + self.terr)[-1]
        self.assertEqual((entry["text"], entry["cid"]), ("hello governor", "cid-0002"))

    def test_not_listening_is_said_as_locally(self):
        self.team()
        self.feed(line("Stop", "tm1", role="task-manager"))
        with self.state.lock:
            self.state._chat_stop_at.clear()     # long idle: nobody listens
        got = self.say("cid-0003")
        self.assertEqual(got, {"cid": "cid-0003", "state": "undelivered", "why": "not-listening"})
        entry = self.entries()[-1]
        self.assertEqual((entry["state"], entry["why"], entry["cid"]), ("undelivered", "not-listening", "cid-0003"))


class TestOnce(MessageCase):
    def test_handed_down_three_times_queued_once(self):
        self.team()
        page = self.client()
        first = self.say("cid-0001")
        again = [self.say("cid-0001"), self.say("cid-0001", text="another text")]
        self.assertEqual([first] + again, [{"cid": "cid-0001", "state": "queued"}] * 3)
        self.assertEqual([e["text"] for e in self.entries() if e["kind"] == "owner"], ["go on"])
        self.assertEqual(len(self.chat_events(page)), 1)

    def test_the_cid_is_on_disk_before_the_message_is_queued(self):
        self.team()
        order = []
        real = self.state.chat_send

        def spy(*a, **kw):
            order.append([l.get("cid") for l in self.seen_lines()])
            return real(*a, **kw)
        self.state.chat_send = spy
        self.say("cid-0001", text="secret text " + MARK)
        self.assertEqual(order, [["cid-0001"]], "cloud_message calls chat_send once, after the cid is in the seen file")
        self.assertEqual(stat.S_IMODE(os.stat(self.seen).st_mode), 0o600)
        with open(self.seen, encoding="utf-8") as fh:
            self.assertNotIn(MARK, fh.read(), "the seen file holds ids, never the text")

    def test_after_a_restart_a_seen_message_is_never_queued_again(self):
        self.team()
        self.say("cid-got")
        self.say("cid-lost")
        self.feed(line("Stop", "tm1", role="task-manager"))
        self.assertEqual(self.state.chat_next("tm1", "w1", 2.0)["state"], "message")   # the oldest one: cid-got
        self.state = self.make()      # the server was started again: the queue is gone
        self.team()
        before = self.all_entries()
        self.assertEqual(self.say("cid-got"), {"cid": "cid-got", "state": "delivered"})
        self.assertEqual(self.say("cid-lost"), {"cid": "cid-lost", "state": "undelivered", "why": "off"},
                         "queued, never delivered, lost in the restart: said so, never queued a second time")
        self.assertEqual(self.all_entries(), before)

    def test_the_state_follows_the_entry(self):
        self.team()
        self.say("cid-0001")
        self.feed(line("Stop", "tm1", role="task-manager"))
        self.state.chat_next("tm1", "w1", 2.0)
        self.assertEqual(self.say("cid-0001"), {"cid": "cid-0001", "state": "delivered"})
        self.say("cid-0002")
        self.feed(line("SessionEnd", "tm1", role="task-manager"))
        got = self.say("cid-0002")
        self.assertEqual(got["state"], "undelivered")


class TestOnlyTextToALiveSessionOfAJoinedRepo(MessageCase):
    """ADD 2 (main manager, 2026-10-01): anything else is not delivered and nothing is queued."""

    def refused(self, why, **kw):
        # one page for the whole test: the server takes four browsers at most
        page = getattr(self, "_page", None) or self.client()
        self._page = page
        self.chat_events(page)
        before = self.all_entries()
        cid = "cid-%s" % abs(hash(repr(sorted(kw.items()))))
        got = self.say(cid, **kw)
        self.assertEqual(got, {"cid": cid, "state": "undelivered", "why": why}, kw)
        self.assertEqual(self.all_entries(), before, "nothing may be queued: %r" % (kw,))
        self.assertEqual(self.chat_events(page), [], "no window may change: %r" % (kw,))
        return cid

    def test_a_to_that_is_not_a_window(self):
        self.team()
        for to in ("/bin/sh", "../../etc/passwd", "~/.ssh/id_rsa", "", "tm1", "$(rm -rf ~)", "--dangerously-skip-permissions",
                   None, 7, ["s:tm1"], {"to": "s:tm1"}):
            self.refused("refused", to=to)

    def test_a_subagent(self):
        self.team()
        self.refused("refused", to="a9")

    def test_a_guest(self):
        self.team()
        for to in ("r:dev-pc2:s:1", "rg:dev-pc2", "r:dev-pc2:gov"):
            self.refused("refused", to=to)

    def test_a_session_of_a_repo_that_is_not_joined(self):
        self.team()
        self.assertEqual(self.state.chat_view("s:x1")[0], 200, "x1 is a live session of this machine")
        self.refused("refused", to="s:x1")
        self.refused("refused", to="gov:" + ac.territory_id(REPO2))
        self.refused("refused", to="s:tm1", terrs=set())
        self.refused("refused", to="gov:" + self.terr, terrs={ac.territory_id(REPO2)})

    def test_a_session_that_is_gone(self):
        self.team()
        self.refused("ended", to="s:nobody")
        self.refused("ended", to="s:../../etc/passwd")
        self.feed(line("SessionEnd", "tm1", role="task-manager"))
        self.refused("ended", to="s:tm1")

    def test_a_text_that_is_not_text(self):
        self.team()
        for text in ("", None, 7, ["rm", "-rf"], {"cmd": "rm"}, "x" * (ac.CHAT_TEXT_MAX + 1)):
            self.refused("refused", text=text)

    def test_too_old(self):
        self.team()
        self.refused("off", age=600001)
        self.assertEqual(self.say("cid-fresh", age=600000)["state"], "queued")

    def test_a_refused_message_stays_refused(self):
        self.team()
        cid = self.refused("refused", to="s:x1")
        got = self.state.cloud_message(cid, "s:tm1", "now with a good window", 1000, self.terrs, self.now + 5)
        self.assertEqual(got["state"], "undelivered", "the answer for a cid never changes to a delivery")
        self.assertEqual([e for e in self.entries() if e["kind"] == "owner"], [])

    def test_shell_words_are_only_text(self):
        self.team()
        evil = "$(touch %s/pwned) ; rm -rf ~ && `id` | sh  --flag ../../x" % self.base
        self.assertEqual(self.say("cid-evil", text=evil)["state"], "queued")
        self.feed(line("Stop", "tm1", role="task-manager"))
        got = self.state.chat_next("tm1", "w1", 2.0)
        self.assertEqual(got["text"], evil, "the session gets the very text, nothing ran")
        self.assertFalse(os.path.exists(os.path.join(self.base, "pwned")))

    def test_the_code_never_starts_a_program_with_it(self):
        with open(os.path.join(BIN, "agent_city.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("def cloud_message(", src)
        body = src[src.index("def cloud_message("):]
        body = body[:body.index("\n    def ", 10)]
        for word in ("subprocess", "os.system", "Popen", "open_fn(", "eval(", "exec("):
            self.assertNotIn(word, body, "cloud_message must only hand text to chat_send")
        self.assertIn("chat_send(", body)


class TestFlood(MessageCase):
    def test_sixty_in_ten_minutes(self):
        self.team()
        for i in range(60):
            self.assertEqual(self.say("cid-%03d" % i)["state"], "queued", i)
        before = self.all_entries()
        self.assertEqual(self.say("cid-060"), {"cid": "cid-060", "state": "undelivered", "why": "flood"})
        self.assertEqual(self.all_entries(), before)
        later = self.state.cloud_message("cid-061", "s:tm1", "later", 1000, self.terrs, self.now + 601)
        self.assertEqual(later["state"], "queued", "ten minutes on, messages are taken again")


# ------------------------------------------------- the server, a fake relay

class TalkCase(UploadCase):
    def setUp(self):
        super().setUp()
        self.fake.talk_key = TALK
        self.talk_file = os.path.join(self.base, "cityhome", "cloud-talk")
        self.talk_on()

    def talk_on(self):
        os.makedirs(os.path.dirname(self.talk_file), exist_ok=True)
        with open(self.talk_file, "w") as fh:
            fh.write("%s %s\n" % (self.fake.host, TALK))
        os.chmod(self.talk_file, 0o600)

    def token(self):
        with open(os.path.join(self.dir, "token")) as fh:
            return fh.read().strip()

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        headers = {"X-City-Token": self.token(), "Origin": "http://127.0.0.1:%d" % self.port}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(raw or b"null")
        except ValueError:
            return resp.status, None

    def chat_line(self, obj):
        with open(os.path.join(self.dir, "chat.jsonl"), "a") as fh:
            fh.write(json.dumps(obj) + "\n")

    def session(self, sid="tm1", repo=None, busy=True):
        self.add(repo=repo, sid=sid, ev="UserPromptSubmit", role="task-manager", tool="")
        if not busy:
            self.add(repo=repo, sid=sid, ev="Stop", role="task-manager", tool="")
        self.assertTrue(wait_for(lambda: self.call("GET", "/api/chat?to=s:" + sid)[0] == 200),
                        "the session never appeared")

    def window(self, sid="tm1"):
        return self.call("GET", "/api/chat?to=s:" + sid)[1]["entries"]

    def rows(self, **want):
        return [r for r in self.fake.chat_rows() if all(r.get(k) == v for k, v in want.items())]

    def last_ack(self, cid):
        acks = self.fake.acks_of(cid)
        return acks[-1] if acks else None


class TestChatGoesUp(TalkCase):
    def test_prompts_and_replies_reach_the_relay_once(self):
        self.up()
        self.session("tm1")
        t = time.time()
        self.chat_line({"sid": "tm1", "aid": "", "kind": "prompt", "text": "先写失败的测试", "at": t})
        self.chat_line({"sid": "tm1", "aid": "", "kind": "reply", "text": "3 个测试写好了", "at": t + 1})
        self.assertTrue(wait_for(lambda: len(self.rows(to="s:tm1")) == 2, timeout=10),
                        "the chat rows never reached the relay: %r" % (self.fake.chat_rows(),))
        rows = self.rows(to="s:tm1")
        self.assertEqual([(r["kind"], r["text"]) for r in rows], [("prompt", "先写失败的测试"), ("reply", "3 个测试写好了")])
        for r in rows:
            self.assertEqual(set(r), {"k", "to", "kind", "text", "at", "state", "why", "cid"})
            self.assertTrue(r["k"])
        self.assertNotEqual(rows[0]["k"], rows[1]["k"])
        self.assertEqual(self.fake.talk_headers()[-1], TALK)
        time.sleep(1.5)
        self.assertEqual(len([r for r in self.fake.chat_log if r["to"] == "s:tm1"]), 2,
                         "a row goes up once, not with every sync")

    def test_the_view_never_holds_chat(self):
        self.up(snap_sec="0.5")
        self.session("tm1")
        self.chat_line({"sid": "tm1", "aid": "", "kind": "reply", "text": "secret " + MARK, "at": time.time()})
        self.assertTrue(wait_for(lambda: self.rows(text="secret " + MARK), timeout=10))
        time.sleep(1.2)
        views = json.dumps([v for _, v in self.fake.view_log])
        self.assertNotIn(MARK, views, "chat text rides in talk only, never in the picture")
        self.assertNotIn('"type": "chat"', views)

    def test_no_talk_file_no_chat_and_no_header(self):
        os.remove(self.talk_file)
        self.up()
        self.session("tm1")
        self.chat_line({"sid": "tm1", "aid": "", "kind": "reply", "text": "stays home " + MARK, "at": time.time()})
        self.picture()
        time.sleep(1.5)
        self.assertEqual(set(self.fake.talk_headers()), {None})
        self.assertNotIn(MARK, json.dumps(self.fake.sync_bodies()), "talk is off: chat text stays on this computer")
        self.assertNotIn("talk", [k for b in self.fake.sync_bodies() for k in b])

    def test_turned_on_while_it_runs_sends_the_window_as_it_is(self):
        os.remove(self.talk_file)
        self.up()
        self.session("tm1")
        self.chat_line({"sid": "tm1", "aid": "", "kind": "reply", "text": "said before talk was on", "at": time.time()})
        self.assertTrue(wait_for(lambda: self.window()))
        self.talk_on()
        self.assertTrue(wait_for(lambda: self.rows(text="said before talk was on"), timeout=10),
                        "cloud-talk on must work with the next sync, no restart")
        os.remove(self.talk_file)
        self.assertTrue(wait_for(lambda: self.fake.talk_headers()[-1] is None, timeout=10),
                        "cloud-talk off must work with the next sync")

    def test_a_repo_that_is_not_joined_keeps_its_chat(self):
        other = make_repo(self.base, name="private", origin="git@github.com:Acme/Private.git")
        self.up()
        self.session("tm1")
        self.session("px1", repo=other)
        t = time.time()
        self.chat_line({"sid": "px1", "aid": "", "kind": "reply", "text": "private " + MARK, "at": t})
        self.chat_line({"sid": "tm1", "aid": "", "kind": "reply", "text": "shared reply", "at": t + 1})
        self.assertTrue(wait_for(lambda: self.rows(text="shared reply"), timeout=10))
        time.sleep(1.0)
        self.assertNotIn(MARK, json.dumps(self.fake.sync_bodies()))
        self.assertEqual(self.rows(to="s:px1"), [])

    def test_a_long_reply_is_cut(self):
        self.up()
        self.session("tm1")
        self.chat_line({"sid": "tm1", "aid": "", "kind": "reply", "text": "长" * 9000, "at": time.time()})
        self.assertTrue(wait_for(lambda: self.rows(to="s:tm1"), timeout=10))
        self.assertEqual(len(self.rows(to="s:tm1")[0]["text"]), 8000)

    def test_a_message_from_the_local_page_goes_up_with_its_state(self):
        self.up()
        self.session("tm1")
        status, body = self.call("POST", "/api/chat/send", {"to": "s:tm1", "text": "from the local page"})
        self.assertEqual((status, body["state"]), (200, "queued"))
        self.assertTrue(wait_for(lambda: self.rows(text="from the local page"), timeout=10))
        row = self.rows(text="from the local page")[0]
        self.assertEqual((row["kind"], row["state"], row["cid"]), ("owner", "queued", ""))
        self.add(sid="tm1", ev="Stop", role="task-manager", tool="")
        time.sleep(0.3)
        self.assertEqual(self.call("GET", "/api/chat/next?sid=tm1&watcher=w1&timeout=5")[1]["state"], "message")
        self.assertTrue(wait_for(lambda: self.rows(text="from the local page")[0]["state"] == "delivered", timeout=10))
        self.assertEqual(len(self.rows(text="from the local page")), 1, "the same key: the relay keeps one row")
        self.assertEqual(self.rows(text="from the local page")[0]["k"], row["k"])


class TestMessageComesDown(TalkCase):
    CID = "cid-down-0000000001"

    def test_down_into_the_queue_and_the_answer_up(self):
        self.up()
        self.session("tm1")
        self.fake.say(self.CID, "s:tm1", "请先跑测试 7731", age=2000)
        self.assertTrue(wait_for(lambda: self.last_ack(self.CID), timeout=10), "no answer for the message went up")
        self.assertEqual(self.last_ack(self.CID), {"cid": self.CID, "state": "queued"})
        for _, talk in list(self.fake.talk_log):
            for ack in talk.get("acks") or []:
                if ack.get("cid") == self.CID:
                    rows = [r for r in talk.get("chat") or [] if r.get("k") == self.CID]
                    self.assertEqual([(r["state"], r["cid"]) for r in rows], [(ack["state"], self.CID)],
                                     "the answer and its chat row go up in the same sync")
        mine = [e for e in self.window() if e["kind"] == "owner"]
        self.assertEqual([(e["text"], e["state"], e["cid"]) for e in mine], [("请先跑测试 7731", "queued", self.CID)])
        self.add(sid="tm1", ev="Stop", role="task-manager", tool="")
        time.sleep(0.3)
        status, got = self.call("GET", "/api/chat/next?sid=tm1&watcher=w1&timeout=5")
        self.assertEqual((got["state"], got["text"]), ("message", "请先跑测试 7731"))
        self.assertTrue(wait_for(lambda: (self.last_ack(self.CID) or {}).get("state") == "delivered", timeout=10),
                        "delivered never went up: %r" % (self.fake.acks_of(self.CID),))
        row = self.rows(k=self.CID)
        self.assertEqual([(r["kind"], r["text"], r["state"], r["cid"]) for r in row],
                         [("owner", "请先跑测试 7731", "delivered", self.CID)])
        with open(os.path.join(self.base, "cityhome", "decisions.jsonl"), encoding="utf-8") as fh:
            last = json.loads(fh.read().strip().splitlines()[-1])
        self.assertEqual((last["text"], last.get("via")), ("请先跑测试 7731", "cloud"))

    def test_the_answer_goes_up_within_two_seconds(self):
        self.up(relay_sec="4")
        self.session("tm1")
        self.fake.say(self.CID, "s:tm1", "quick")
        self.assertTrue(wait_for(lambda: self.last_ack(self.CID), timeout=15))
        with self.fake.lock:
            syncs = [r for r in self.fake.requests if r["path"] == "/v1/sync"]
        down = [r["t"] for r in syncs if r["status"] == 200 and isinstance(r["body"], dict)]
        acked = [r["t"] for r in syncs
                 if any(a.get("cid") == self.CID for a in ((r["body"] or {}).get("talk") or {}).get("acks") or [])]
        before = max(t for t in down if t < acked[0])
        self.assertLess(acked[0] - before, 2.2, "the answer must not wait for the next 4 s sync")

    def test_handed_down_again_and_again_queued_once(self):
        self.up()
        self.session("tm1")
        self.fake.say(self.CID, "s:tm1", "only once")
        self.assertTrue(wait_for(lambda: self.last_ack(self.CID), timeout=10))
        for _ in range(3):
            self.fake.say(self.CID, "s:tm1", "only once")
            time.sleep(0.5)
        self.assertEqual(len([e for e in self.window() if e["kind"] == "owner"]), 1)
        self.assertEqual({a["state"] for a in self.fake.acks_of(self.CID)}, {"queued"})

    def test_only_text_to_a_live_session_of_a_joined_repo(self):
        other = make_repo(self.base, name="private", origin="git@github.com:Acme/Private.git")
        self.up()
        self.session("tm1")
        self.session("px1", repo=other)
        self.add(sid="tm1", aid="a9", at="worker", role="task-manager")
        bad = {"cid-bad-path-00000001": "/bin/sh", "cid-bad-rel-000000001": "../../etc/passwd",
               "cid-bad-sub-000000001": "a9", "cid-bad-guest-0000001": "r:dev-pc2:s:1",
               "cid-bad-repo-00000001": "s:px1", "cid-bad-gone-00000001": "s:nobody"}
        for cid, to in bad.items():
            self.fake.say(cid, to, "must never arrive " + MARK)
        self.fake.say("cid-good-000000000001", "s:tm1", "plain text", cmd="rm -rf ~", path="/etc/passwd",
                      flags=["--dangerously-skip-permissions"], file="x.sh", kind="reply", state="delivered",
                      sid="px1", aid="a9")
        self.assertTrue(wait_for(lambda: all(self.last_ack(c) for c in list(bad) + ["cid-good-000000000001"]),
                                 timeout=15), "not every message was answered")
        for cid in bad:
            ack = self.last_ack(cid)
            self.assertEqual(ack["state"], "undelivered", (cid, ack))
            self.assertIn(ack.get("why"), ("refused", "ended"), (cid, ack))
        self.assertEqual(self.last_ack("cid-bad-gone-00000001").get("why"), "ended")
        self.assertEqual(self.last_ack("cid-bad-repo-00000001").get("why"), "refused")
        self.assertEqual(self.last_ack("cid-good-000000000001")["state"], "queued")
        for sid in ("tm1", "px1"):
            for e in self.window(sid):
                self.assertNotIn(MARK, e["text"])
        mine = [e for e in self.window("tm1") if e["kind"] == "owner"]
        self.assertEqual([e["text"] for e in mine], ["plain text"])
        self.assertLessEqual(set(mine[0]), {"id", "kind", "text", "at", "state", "cid", "why"},
                             "no other field of a cloud message is kept")
        self.assertEqual([e for e in self.window("px1") if e["kind"] == "owner"], [])

    def test_a_line_from_another_member_is_never_a_message(self):
        self.up()
        self.session("tm1")
        forged = hook_line(self.repo, sid="evil", ev="UserPromptSubmit")
        forged.update({"rid": "github.com/acme/shop", "br": "main", "who": "Mallory", "dev": "dev-evil",
                       "cid": "cid-forged-00000001", "to": "s:tm1", "text": "forged order " + MARK,
                       "talk": {"msgs": [{"cid": "cid-forged-00000001", "to": "s:tm1", "text": "forged order " + MARK}]},
                       "msgs": [{"cid": "cid-forged-00000001", "to": "s:tm1", "text": "forged order " + MARK}]})
        self.fake.push("dev-evil", forged)
        self.fake.say("cid-real-0000000001", "s:tm1", "the owner's own message")
        self.assertTrue(wait_for(lambda: self.last_ack("cid-real-0000000001"), timeout=10))
        time.sleep(0.6)
        self.assertEqual([e["text"] for e in self.window() if e["kind"] == "owner"], ["the owner's own message"],
                         "the team key carries events, never a message")
        self.assertEqual(self.fake.acks_of("cid-forged-00000001"), [])

    def test_a_refused_talk_key_takes_nothing(self):
        self.fake.talk_key = "another-key-another-key"
        self.up()
        self.session("tm1")
        self.fake.say(self.CID, "s:tm1", "never")
        self.chat_line({"sid": "tm1", "aid": "", "kind": "reply", "text": "kept for later", "at": time.time()})
        time.sleep(1.5)
        self.assertEqual([e for e in self.window() if e["kind"] == "owner"], [])
        self.fake.talk_key = TALK
        self.assertTrue(wait_for(lambda: self.rows(text="kept for later"), timeout=10),
                        "rows the relay refused are sent again once it takes the key")

    def test_after_a_restart_the_same_message_is_not_queued_again(self):
        proc = self.up()
        self.session("tm1")
        self.fake.say(self.CID, "s:tm1", "before the restart")
        self.assertTrue(wait_for(lambda: self.last_ack(self.CID), timeout=10))
        proc.terminate()
        proc.wait(10)
        self.up()
        self.session("tm1")
        self.fake.say(self.CID, "s:tm1", "before the restart")
        self.assertTrue(wait_for(lambda: (self.last_ack(self.CID) or {}).get("state") == "undelivered", timeout=10),
                        "a message lost in a restart must be answered as not delivered: %r" % (self.fake.acks_of(self.CID),))
        self.assertEqual(self.last_ack(self.CID).get("why"), "off")
        self.assertEqual([e for e in self.window() if e["kind"] == "owner"], [])
        seen = os.path.join(self.dir, "cloud-seen")
        self.assertTrue(os.path.isfile(seen), "<city dir>/cloud-seen")
        self.assertEqual(stat.S_IMODE(os.stat(seen).st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
