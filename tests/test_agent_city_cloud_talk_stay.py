"""Failing tests, cloud-city-2 bounce 1 (laptop main manager, 2026-10-01, a
real session): a waiting session must stay reachable from the cloud page.

Found: after `agent-city stop` + `start` on the same city dir, with the
session alive and idle, (1) the machine never came back for the cloud: the
restarted server made no sync until a new hook line arrived; (2) the idle
session was deaf: its watcher had returned when the old server went away;
(3) the same with no restart by hand: the server stops itself after
city_idle_min with no browser, and with the cloud page as the only window
there is no browser.

bin/agent_city.py (and bin/agent_city_relay.py for the hub's part)

  (a) STAY UP. The server does not stop itself for being idle while BOTH hold:
      a joined relay says the cloud page is on (the uploader's "on" for at
      least one relay), and the roster holds a live session (a session whose
      pid is alive). Else the idle stop is the one of before (no browser and
      nothing new for idle seconds; a waiting watcher still keeps it up).
  (b) SYNC AT START. A server that starts with live sessions in its roster
      makes the hub know the joined repos of those sessions at once (the
      roster's repo of each restored session, the way a first hook line of
      that repo would, but with no line sent), so its first syncs carry the
      picture, and talk when the talk file has the host: the cloud sees the
      machine again within about 15 s, with no hook line. A roster with no
      live session, or a repo that is not joined: nothing is sent, as before.
  (c) THE WATCHER SURVIVES. chat-watch and gov-watch, once they have reached
      a server, keep waiting when it goes away: no endpoint, a refused
      connection, or an answer that is not 200 (a new server has a new token)
      -> wait about 2 s, read <city dir>/on and the token again, try again;
      until the max wait is over or the parent is gone. "replaced" still ends
      the watcher. With no server at all when it starts, it ends at once, as
      before. So an idle session is reachable again after a restart, with no
      typing in its terminal.

Every test uses a fake relay on 127.0.0.1 and temp folders. Never a real key.

Run: python3 -m unittest tests.test_agent_city_cloud_talk_stay </dev/null
"""

import json
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_agent_city_server import wait_for  # noqa: E402
from test_agent_city_cloud_talk_machine import TALK, TalkCase  # noqa: E402

SERVER = os.path.join(BIN, "agent_city.py")


def dead_pid():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


class StayCase(TalkCase):
    def live(self, sid="tm1", pid=None, idle=True, role="task-manager"):
        """A session whose process is alive (this test's own pid stands in for it)."""
        pid = str(os.getpid() if pid is None else pid)
        self.add(sid=sid, ev="UserPromptSubmit", role=role, tool="", pid=pid)
        if idle:
            self.add(sid=sid, ev="Stop", role=role, tool="", pid=pid)
        self.assertTrue(wait_for(lambda: self.call("GET", "/api/chat?to=s:" + sid)[0] == 200),
                        "the session never appeared")

    def roster(self):
        try:
            with open(os.path.join(self.dir, "roster.json")) as fh:
                return [s["sid"] for s in json.load(fh).get("sessions", [])]
        except (OSError, ValueError):
            return []

    def stop(self, proc):
        proc.terminate()
        proc.wait(10)

    def people_seen_since(self, index):
        out = []
        for _, v in list(self.fake.view_log)[index:]:
            for msg in v.get("snap") or []:
                if msg.get("type") == "snapshot":
                    out += [a["id"] for a in msg.get("agents") or []]
        return out


class TestSyncAtStart(StayCase):
    def test_a_restarted_server_shows_the_machine_again_with_no_new_line(self):
        proc = self.up()
        self.live("tm1")
        self.picture()
        self.assertTrue(wait_for(lambda: "tm1" in self.roster()), "the session never reached roster.json")
        self.stop(proc)
        views, requests = len(self.fake.view_log), len(self.fake.requests)
        self.up()
        self.assertTrue(wait_for(lambda: "s:tm1" in self.people_seen_since(views), timeout=15),
                        "no picture went up after the restart: the cloud page says the machine is off "
                        "(%d requests since the restart)" % (len(self.fake.requests) - requests))
        self.assertEqual(self.fake.talk_headers()[-1], TALK, "and talk is on again, so a message can come down")

    def test_a_message_reaches_the_restored_session_with_no_new_line(self):
        proc = self.up()
        self.live("tm1")
        self.picture()
        self.assertTrue(wait_for(lambda: "tm1" in self.roster()))
        self.stop(proc)
        self.up()
        cid = "cid-after-restart-01"
        self.fake.say(cid, "s:tm1", "after the restart")
        self.assertTrue(wait_for(lambda: self.last_ack(cid), timeout=15), "the message was never picked up")
        status, got = self.call("GET", "/api/chat/next?sid=tm1&watcher=w1&timeout=5")
        self.assertEqual((got["state"], got.get("text")), ("message", "after the restart"))

    def test_nothing_to_show_nothing_sent(self):
        proc = self.up()
        self.live("tm1", pid=dead_pid())      # its process is gone: not a live session
        self.picture()
        self.stop(proc)
        requests = len(self.fake.requests)
        self.up()
        time.sleep(2.5)
        self.assertEqual(len(self.fake.requests), requests, "no live session in the roster: a start sends nothing, as before")


class TestStayUp(StayCase):
    def running(self, proc, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if proc.poll() is not None:
                return False
            time.sleep(0.2)
        return True

    def test_cloud_on_and_a_live_session_keep_the_server_up(self):
        proc = self.up(idle="2")
        self.live("tm1")
        self.picture()
        self.assertTrue(self.running(proc, 6.0),
                        "the server stopped itself: a waiting session can no longer be reached from the phone")
        self.assertEqual(self.health()["clients"], 0, "no browser was open")

    def test_cloud_off_stops_as_before(self):
        self.fake.city = False
        proc = self.up(idle="2")
        self.live("tm1")
        self.assertFalse(self.running(proc, 8.0), "the cloud page is off: the idle stop is the one of before")

    def test_no_live_session_stops_as_before(self):
        proc = self.up(idle="2")
        self.live("tm1", pid=dead_pid())
        self.assertFalse(self.running(proc, 8.0), "its process is gone: nothing to stay up for")

    def test_a_session_that_ended_lets_it_stop(self):
        proc = self.up(idle="2")
        self.live("tm1")
        self.picture()
        self.assertTrue(self.running(proc, 3.5))
        self.add(sid="tm1", ev="SessionEnd", role="task-manager", tool="", pid=str(os.getpid()))
        self.assertFalse(self.running(proc, 9.0), "the last live session ended: the server may stop")


class TestWatcherSurvives(StayCase):
    def watch(self, command="chat-watch", sid="tm1", wait="40", role="task-manager", cwd=None):
        env = dict(os.environ, AGENT_CITY_DIR=self.dir, AGENT_CITY_HOME=os.path.join(self.base, "cityhome"))
        env.pop("AGENT_ROLE", None)
        env.pop("CLAUDE_PID", None)
        if role:
            env["AGENT_ROLE"] = role
        path = os.path.join(self.base, "hook-%s.json" % sid)
        with open(path, "w") as fh:
            json.dump({"hook_event_name": "Stop", "session_id": sid, "cwd": cwd or self.repo}, fh)
        with open(path, "rb") as stdin:
            proc = subprocess.Popen([sys.executable, SERVER, command, "--max-wait-sec", wait],
                                    stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        self.procs.append(proc)
        return proc

    def restart_and_talk(self, command, sid, role):
        server = self.up()
        self.live(sid, role=role)
        self.assertTrue(wait_for(lambda: sid in self.roster()))
        watcher = self.watch(command, sid=sid, role=role)
        time.sleep(1.5)
        self.assertIsNone(watcher.poll(), "the watcher ended before anything happened")
        self.stop(server)
        time.sleep(1.5)
        self.assertIsNone(watcher.poll(), "the watcher gave up when the server went away: the session is deaf now")
        self.up()
        time.sleep(4.0)       # one retry (about 2 s) and its first poll on the new server
        self.assertIsNone(watcher.poll())
        status, body = self.call("POST", "/api/chat/send", {"to": "s:" + sid, "text": "are you still there 4417"})
        self.assertEqual((status, body.get("state")), (200, "queued"),
                         "the new server must see the watcher listening: %r" % (body,))
        out, err = watcher.communicate(timeout=20)
        self.assertEqual(watcher.returncode, 2, err)
        self.assertIn("are you still there 4417", err.decode())

    def test_chat_watch_outlives_a_restart(self):
        self.restart_and_talk("chat-watch", "tm1", "task-manager")

    def test_gov_watch_outlives_a_restart(self):
        # a session with no role runs gov-watch; not the main manager here, so it waits for its own messages
        self.restart_and_talk("gov-watch", "h1", "")

    def test_the_max_wait_still_ends_it(self):
        server = self.up()
        self.live("tm1")
        watcher = self.watch(wait="5")
        time.sleep(1.0)
        self.stop(server)
        out, err = watcher.communicate(timeout=15)
        self.assertEqual((watcher.returncode, err), (0, b""), "max wait over with no server: it ends quietly")

    def test_no_server_at_the_start_ends_at_once(self):
        os.makedirs(self.dir, exist_ok=True)
        t0 = time.monotonic()
        watcher = self.watch(wait="30")
        out, err = watcher.communicate(timeout=15)
        self.assertEqual((watcher.returncode, err), (0, b""))
        self.assertLess(time.monotonic() - t0, 5.0, "city off: no waiting, as before")


if __name__ == "__main__":
    unittest.main()
