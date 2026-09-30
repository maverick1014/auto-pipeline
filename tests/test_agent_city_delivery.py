"""Failing tests: an owner message from the city panel reaches its session, or says it did not
(city-roles R6, R7; owner 2026-09-30).

Bug R6 (laptop, 2026-09-30): the owner sent a message from a Helper's panel and the session never
got it; the page kept saying 已发送. The Helper (roleless, not the seat holder) ran gov-watch, which
only polled gov:<terr>, and several roleless sessions raced for gov:<terr>.
Bug R7: tests wrote rows into the owner's real ~/.claude/agent-city/decisions.jsonl (sid tm1,
"go on"): a server started without --decisions ignored AGENT_CITY_HOME.

CONTRACT (bin/agent_city.py CityState; bin/agent-city.html chatHtml; hooks.json unchanged):

  Who listens. The seat holder's gov-watch (gov_next) listens for "gov:<terr>". Every other
  session's watcher listens for its own "s:<sid>": chat-watch (AGENT_ROLE set), or gov-watch that
  got {"state": "not-main"} (roleless, not the holder; tests/test_agent_city_roles.py).
  A page counts as listened to while a watcher waits for it, for listen_grace_sec after that
  watcher's last poll ended, and for listen_grace_sec after the session's Stop (its watcher is
  starting). CityState(..., listen_grace_sec=15.0).

  Idle page: not busy (the chat idle rule), or "gov:<terr>" of a territory with no governor now.

  chat_send(to, text, now): idle and not listened to -> the entry is kept with state
  "undelivered" and "why": "not-listening"; the reply is {"id", "state": "undelivered",
  "why": "not-listening"}. Busy, or listened to -> "queued" as before; a waiting watcher gets it.
  sweep_chat(): (the server calls it every recount tick) every "queued" owner entry whose page is
  idle and not listened to becomes "undelivered", "why": "not-listening", and the page gets
  {"type": "chat", "to", "entry"}. An undelivered entry is never given to a watcher later.
  gov_next: a waiting holder that loses the seat gets {"state": "not-main"} (its gov-watch then
  listens for its own page at once), not "replaced".

  Page. chat.state.queued says 排队中 / Queued (never 已发送 / Sent: nothing was received yet).
  An owner entry "undelivered" with why "not-listening" also shows chat.why.notListening:
  它没在听，收不到 / it is not listening, it did not get this.

  R7. CityState(decisions_path=None) and `serve` without --decisions use
  $AGENT_CITY_HOME/decisions.jsonl when AGENT_CITY_HOME is set, else
  ~/.claude/agent-city/decisions.jsonl. No test ever writes the real one: every CityState a test
  makes passes decisions_path, every server a test starts has AGENT_CITY_HOME or --decisions.

Run: python3 -m unittest tests.test_agent_city_delivery </dev/null
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, os.path.join(ROOT, "bin")):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from cityhelp import Mains  # noqa: E402
from test_agent_city_page import text_zh  # noqa: E402
from test_agent_city_server import SERVER, ServerCase, wait_for  # noqa: E402

REPO = "/r/shop/.git"
GRACE = 0.3


def line(ev, sid, role="", repo=REPO):
    return {"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "Read", "nt": "", "proj": "shop",
            "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "ask": "",
            "wt": "", "file": "", "tp": "", "pid": ""}


class DeliveryCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_delivery_")
        self.mains = Mains({REPO: "g1"})
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=None,
                               chat_path=os.path.join(self.base, "chat.jsonl"),
                               count_fn=lambda i: 0, balance_fn=lambda i, r: {"kinds": {}, "files": {}, "bad": []},
                               main_fn=self.mains, listen_grace_sec=GRACE)
        self.gov_page = "gov:" + ac.territory_id(REPO)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def feed(self, *lines):
        for obj in lines:
            self.st.feed_line(obj, time.monotonic())

    def idle_session(self, sid, role=""):
        self.feed(line("UserPromptSubmit", sid, role), line("Stop", sid, role))

    def entry(self, to, entry_id):
        return next(e for e in self.st.chat_view(to)[1]["entries"] if e["id"] == entry_id)

    def wait_in_thread(self, fn):
        out = {}
        t = threading.Thread(target=lambda: out.update(r=fn()))
        t.start()
        time.sleep(0.2)
        return t, out


class TestEachRoleIsReached(DeliveryCase):
    def test_a_helper_gets_its_message(self):
        """R6: roleless, not the holder -> its own page; gov-watch fell back to chat_next."""
        self.idle_session("h1")
        self.assertEqual(self.st.gov_next("h1", REPO, "w1", 0.1), {"state": "not-main"})
        t, out = self.wait_in_thread(lambda: self.st.chat_next("h1", "w1", 3))
        code, body = self.st.chat_send("s:h1", "helper, look", 0)
        t.join(5)
        self.assertEqual((code, body["state"]), (200, "queued"))
        self.assertEqual((out["r"]["state"], out["r"]["text"]), ("message", "helper, look"))
        self.assertEqual(self.entry("s:h1", body["id"])["state"], "delivered")

    def test_the_governor_gets_its_message(self):
        self.idle_session("g1")
        t, out = self.wait_in_thread(lambda: self.st.gov_next("g1", REPO, "gw", 3))
        code, body = self.st.chat_send(self.gov_page, "governor, look", 0)
        t.join(5)
        self.assertEqual((out["r"]["state"], out["r"]["text"]), ("message", "governor, look"))

    def test_a_task_manager_gets_its_message(self):
        self.idle_session("tm1", "task-manager")
        t, out = self.wait_in_thread(lambda: self.st.chat_next("tm1", "cw", 3))
        code, body = self.st.chat_send("s:tm1", "tm, look", 0)
        t.join(5)
        self.assertEqual((out["r"]["state"], out["r"]["text"]), ("message", "tm, look"))

    def test_only_the_holder_is_given_the_governor_page(self):
        self.idle_session("g1")
        self.idle_session("h1")
        self.assertEqual(self.st.gov_next("h1", REPO, "hw", 0.1), {"state": "not-main"})
        t, out = self.wait_in_thread(lambda: self.st.chat_next("h1", "hw", 1))
        self.st.gov_next("g1", REPO, "gw", 0.1)
        self.st.chat_send(self.gov_page, "for the governor", 0)
        t.join(5)
        self.assertEqual(out["r"], {"state": "none"}, "a helper never takes the governor's message")


class TestHonestState(DeliveryCase):
    def test_idle_and_nobody_listening_is_not_delivered_at_once(self):
        self.idle_session("h1")
        time.sleep(GRACE + 0.2)
        code, body = self.st.chat_send("s:h1", "anyone?", 0)
        self.assertEqual(code, 200)
        self.assertEqual((body["state"], body.get("why")), ("undelivered", "not-listening"))
        e = self.entry("s:h1", body["id"])
        self.assertEqual((e["state"], e.get("why")), ("undelivered", "not-listening"))
        self.assertEqual(self.st.chat_next("h1", "late", 0.2), {"state": "none"},
                         "an undelivered message is never given later")

    def test_right_after_its_stop_it_still_waits(self):
        self.idle_session("h1")
        code, body = self.st.chat_send("s:h1", "just stopped", 0)
        self.assertEqual(body["state"], "queued")
        self.assertEqual(self.st.chat_next("h1", "w1", 0.5)["text"], "just stopped")

    def test_busy_waits_then_the_sweep_tells_the_truth(self):
        self.feed(line("UserPromptSubmit", "h1"))           # busy
        client = self.st.add_client()
        client.queue.get_nowait()
        code, body = self.st.chat_send("s:h1", "after your turn", 0)
        self.assertEqual(body["state"], "queued")
        time.sleep(GRACE + 0.2)
        self.st.sweep_chat()
        self.assertEqual(self.entry("s:h1", body["id"])["state"], "queued", "busy: its turn is not over")
        self.feed(line("Stop", "h1"))                       # idle, but no watcher ever comes
        time.sleep(GRACE + 0.2)
        while not client.queue.empty():
            client.queue.get_nowait()
        self.st.sweep_chat()
        e = self.entry("s:h1", body["id"])
        self.assertEqual((e["state"], e.get("why")), ("undelivered", "not-listening"))
        told = []
        while not client.queue.empty():
            raw = client.queue.get_nowait()
            if isinstance(raw, bytes) and b"data:" in raw:
                told.append(json.loads(raw.decode("utf-8").split("data:", 1)[1]))
        self.assertIn(("chat", "s:h1", "undelivered"),
                      [(m.get("type"), m.get("to"), m.get("entry", {}).get("state")) for m in told])
        self.st.remove_client(client)

    def test_a_listening_watcher_keeps_it_queued(self):
        self.idle_session("h1")
        time.sleep(GRACE + 0.2)
        self.st.chat_next("h1", "w1", 0.05)                  # a watcher just polled
        code, body = self.st.chat_send("s:h1", "you there", 0)
        self.assertEqual(body["state"], "queued")
        self.st.sweep_chat()
        self.assertEqual(self.entry("s:h1", body["id"])["state"], "queued")

    def test_no_governor_the_governor_page_says_so(self):
        self.mains.clear()                                  # nobody holds the lock
        self.feed(line("UserPromptSubmit", "h1"))           # a citizen makes the territory known
        time.sleep(GRACE + 0.2)
        code, body = self.st.chat_send(self.gov_page, "governor?", 0)
        self.assertEqual(code, 200)
        self.assertEqual((body["state"], body.get("why")), ("undelivered", "not-listening"))

    def test_a_holder_that_loses_the_seat_is_told_not_main(self):
        self.idle_session("g1")
        t, out = self.wait_in_thread(lambda: self.st.gov_next("g1", REPO, "gw", 5))
        self.mains.clear()
        self.st.check_seats(time.monotonic())
        t.join(8)
        self.assertEqual(out["r"], {"state": "not-main"})


class TestPageWords(unittest.TestCase):
    def test_queued_is_not_called_sent(self):
        zh = text_zh()
        self.assertEqual(zh.get("chat.state.queued"), "排队中")
        self.assertEqual(zh.get("chat.why.notListening"), "它没在听，收不到")

    def test_the_reason_is_shown(self):
        import test_agent_city_chat as chat_tests
        page = chat_tests.TestPageChat("test_chat_html")
        entries = [{"id": 1, "kind": "owner", "text": "x", "at": 1, "state": "undelivered", "why": "not-listening"},
                   {"id": 2, "kind": "owner", "text": "y", "at": 2, "state": "queued"}]
        html = page.html((entries, "h", False))[0]
        self.assertIn("没送到", html)
        self.assertIn("它没在听，收不到", html)
        self.assertIn("排队中", html)
        self.assertNotIn("已发送", html)


# -- R7: tests never write the owner's real decisions.jsonl ------------------

class TestDecisionsHome(unittest.TestCase):
    def test_default_follows_agent_city_home(self):
        base = tempfile.mkdtemp(prefix="city_dhome_")
        old = os.environ.get("AGENT_CITY_HOME")
        try:
            os.environ["AGENT_CITY_HOME"] = base
            st = ac.CityState(world_path=None, count_fn=lambda i: 0,
                              balance_fn=lambda i, r: {"kinds": {}, "files": {}, "bad": []})
            self.assertEqual(st.decisions_path, os.path.join(base, "decisions.jsonl"))
            del os.environ["AGENT_CITY_HOME"]
            st = ac.CityState(world_path=None, count_fn=lambda i: 0,
                              balance_fn=lambda i, r: {"kinds": {}, "files": {}, "bad": []})
            self.assertEqual(st.decisions_path, os.path.expanduser("~/.claude/agent-city/decisions.jsonl"))
        finally:
            if old is None:
                os.environ.pop("AGENT_CITY_HOME", None)
            else:
                os.environ["AGENT_CITY_HOME"] = old
            shutil.rmtree(base, ignore_errors=True)

    def test_every_test_state_names_its_decisions_file(self):
        """A CityState made by a test without decisions_path would write the owner's real file."""
        bad = []
        for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
            if os.path.basename(path) == os.path.basename(__file__):
                continue    # this file sets AGENT_CITY_HOME around its own two on purpose
            text = open(path, encoding="utf-8").read()
            for m in re.finditer(r"\b(?:ac|agent_city)\.CityState\(", text):
                call = text[m.end():m.end() + 800]
                depth, end = 1, len(call)
                for i, ch in enumerate(call):
                    depth += (ch == "(") - (ch == ")")
                    if depth == 0:
                        end = i
                        break
                if "decisions_path" not in call[:end]:
                    bad.append("%s:%d" % (os.path.basename(path), text[:m.start()].count("\n") + 1))
        self.assertEqual(bad, [], "pass decisions_path=<temp> in these")


class TestServerDecisionsHome(ServerCase):
    def test_a_server_without_decisions_writes_under_agent_city_home(self):
        fake_home = os.path.join(self.base, "fakehome")
        os.makedirs(fake_home)
        city_home = os.path.join(self.base, "cityhome")
        env = dict(os.environ, HOME=fake_home, AGENT_CITY_HOME=city_home)
        proc = subprocess.Popen([sys.executable, SERVER, "serve", "--dir", self.dir, "--port", "0",
                                 "--idle-sec", "60"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=env, cwd=self.base)
        self.procs.append(proc)
        self.assertTrue(wait_for(lambda: (self.on() or (0,))[0] == proc.pid), "the server never came up")
        token = open(os.path.join(self.dir, "token")).read().strip()
        for ev in ("UserPromptSubmit", "Stop"):
            self.append(json.dumps(dict(line(ev, "tm1", "task-manager"), repo="")) + "\n")
        import http.client

        def call(method, path, body=None):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
            headers = {"X-City-Token": token, "Origin": "http://127.0.0.1:%d" % self.port}
            data = json.dumps(body).encode() if body is not None else None
            if data:
                headers["Content-Type"] = "application/json"
            conn.request(method, path, body=data, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            conn.close()
            return resp.status, json.loads(raw or b"null")

        self.assertTrue(wait_for(lambda: call("GET", "/api/chat?to=s:tm1")[0] == 200), "tm1 never showed up")
        waiter = {}
        t = threading.Thread(target=lambda: waiter.update(r=call("GET", "/api/chat/next?sid=tm1&watcher=w&timeout=5")))
        t.start()
        time.sleep(0.3)
        call("POST", "/api/chat/send", {"to": "s:tm1", "text": "home check"})
        t.join(10)
        self.assertEqual(waiter["r"][1].get("text"), "home check")
        self.assertTrue(wait_for(lambda: os.path.exists(os.path.join(city_home, "decisions.jsonl"))))
        self.assertFalse(os.path.exists(os.path.join(fake_home, ".claude")), "nothing under HOME")


if __name__ == "__main__":
    unittest.main()
