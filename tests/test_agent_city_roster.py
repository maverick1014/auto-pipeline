"""Failing tests: live sessions come back at once after a city server restart (city-rediscover,
owner 2026-10-01: "the agent detection is not correct, v4-plus has agents but the city cannot see them").

Bug (laptop, 2026-10-01 09:32): the city stops by itself after 30 min with no browser, so every
reopen is a restart. A restart forgot every session; an idle one stayed invisible until its next
event. v4-plus showed no governor and no task manager although both sessions were alive.
The main manager there was on old hooks (lines carry no "pid") and its lock was the old format
("<pid> <date> <time>", no sid), so it was never matched as the governor at all. And an old
agent-start.sh (the SessionStart hook of a session opened before 0.13.0) writes the lock back in
the old format on every compaction.

CONTRACT (bin/agent_city.py CityState, cmd_serve). requirements/city.md, "Data path".

  R1 The roster. CityState(..., roster_path=None). None: no roster, nothing on disk, as before.
     `serve --dir DIR` passes DIR/roster.json.
     - The file lists every live SESSION the server knows a pid for (never a subagent): what the
       snapshot needs to show it again (sid, pid, repo, role, label, task, governor or citizen, ...).
       JSON. Written with a temp file in the same folder plus os.replace; no temp file is left.
     - pid of a session = the "pid" field of its lines (digits). A governor without one (old
       hooks) = the pid in the lock it holds. A citizen without one has no known pid: it is not
       brought back (nothing proves it alive), it shows up again on its next line, as before.
     - Written only when the list or what it stores changes (a session appears, ends, takes or
       loses the seat, gets its name). An ordinary tool line never rewrites it.
     - A session that ends (SessionEnd, or a governor found dead by check_seats) leaves the file.
     - Load, in CityState.__init__, before any line: every entry whose pid is alive is shown again
       with no line read ("lines" in health() stays 0): the lock holder of its territory (same
       rule as for a line, the entry's pid standing in for the line's "pid") is the governor,
       state "idle" in the snapshot's "govs" (never "unknown"); every other one is a citizen
       "s:<sid>" with its saved role, label and task, in its territory, a lead with its office.
       An entry whose pid is dead is dropped, from the city and from the file.
       A file that is missing, unreadable or garbage = an empty roster. Never raises.
     - A restored session is the same session: its next line makes no second spawn, the
       governor's next line governs, its SessionEnd ends it, check_seats watches its pid.
     - Subagents are not in the roster. They come back on their next event (auto spawn, saved
       names from world.json), as before.

  R3 Old hooks. A session line with no "pid" is still the governor's when the lock names its sid.
     R3b Once seated, the server remembers the pid the governor was seated with (the lock's pid,
     kept in the roster). When the lock later has no sid again (an old agent-start.sh rewrote it)
     and still names that pid, the governor keeps the seat: on its own lines (no "pid"), in
     check_seats, in gov_next (pid ""), and after a restart. A lock without a sid that names
     another pid takes the seat away, as before.

Run: python3 -m unittest tests.test_agent_city_roster </dev/null
"""

import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agent_city as ac  # noqa: E402
from cityhelp import lock_file  # noqa: E402
from test_agent_city_server import ServerCase, wait_for  # noqa: E402


class RosterCase(unittest.TestCase):
    """CityState with a roster file, real lock files and real pids. restart() = a new CityState
    on the same world.json and roster.json, the old one thrown away: a server restart."""

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_roster_"))
        self.world = os.path.join(self.base, "world.json")
        self.city_dir = os.path.join(self.base, "city")
        os.makedirs(self.city_dir)
        self.roster = os.path.join(self.city_dir, "roster.json")
        self.repo = os.path.join(self.base, "repoA", ".git")
        self.repo_b = os.path.join(self.base, "repoB", ".git")
        os.makedirs(self.repo)
        os.makedirs(self.repo_b)
        self.procs = []
        self.client = None
        self.st = self.make_state()

    def make_state(self, **kw):
        kw.setdefault("roster_path", self.roster)
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world,
                            plans=ac.load_plans(), count_fn=lambda i: 0,
                            balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}},
                            start_repo=self.repo, **kw)

    def restart(self):
        if self.client is not None:
            self.st.remove_client(self.client)
            self.client = None
        self.st = self.make_state()

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
                p.wait()
        shutil.rmtree(self.base, ignore_errors=True)

    # -- helpers ---------------------------------------------------------

    def live(self):
        """A live process: a stand-in session."""
        proc = subprocess.Popen(["sleep", "120"])
        self.procs.append(proc)
        return proc

    def kill(self, proc):
        proc.kill()
        proc.wait()

    def write_lock(self, pid, sid="-", repo=None, old=False):
        path = os.path.join(self.repo if repo is None else repo, "agent_main.lock")
        with open(path, "w") as fh:
            if old:
                fh.write("%s 2026-09-30 20:03\n" % pid)
            else:
                fh.write("%s 2026-09-30 20:03 %s -\n" % (pid, sid))

    def drop_lock(self, repo=None):
        os.remove(os.path.join(self.repo if repo is None else repo, "agent_main.lock"))

    def line(self, ev, sid, now=100.0, repo=None, role="", tool="Read", pid=None, aid="", at=""):
        """pid None: an old hook's line, it has no "pid" key at all."""
        obj = {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": "p",
               "role": role, "desc": "", "sub": "", "q": "", "klen": "",
               "repo": self.repo if repo is None else repo, "ask": "", "wt": "", "file": "", "tp": ""}
        if pid is not None:
            obj["pid"] = str(pid)
        self.st.feed_line(obj, now)

    def act(self, sid, now=100.0, **kw):
        self.line("PostToolUse", sid, now, **kw)

    def holder(self, repo=None):
        reducer = self.st.reducers.get(self.repo if repo is None else repo)
        return None if reducer is None else reducer.gov_sid

    def snapshot(self):
        client = self.st.add_client()
        try:
            data = client.queue.get_nowait().decode("utf-8")
        finally:
            self.st.remove_client(client)
        return json.loads(data.split("data:", 1)[1])

    def agents(self):
        return {a["id"]: a for a in self.snapshot()["agents"]}

    def govs(self):
        return [(g["terr"], g["state"]) for g in self.snapshot()["govs"]]

    def terr(self, repo=None):
        return ac.territory_id(self.repo if repo is None else repo)

    def roster_text(self):
        with open(self.roster, encoding="utf-8") as fh:
            return fh.read()

    def listen(self):
        self.client = self.st.add_client()
        self.client.queue.get_nowait()  # the snapshot

    def heard(self):
        out = []
        while True:
            try:
                raw = self.client.queue.get_nowait()
            except queue.Empty:
                return out
            if not isinstance(raw, bytes):
                continue
            text = raw.decode("utf-8")
            if "data:" in text:
                out.append(json.loads(text.split("data:", 1)[1]))

    def a_governor(self, sid="sid-gov", repo=None, with_pid=True):
        """A live main manager: holds the lock by sid, has acted, is idle now."""
        proc = self.live()
        self.write_lock(proc.pid, sid, repo=repo)
        self.act(sid, repo=repo, pid=proc.pid if with_pid else None)
        self.line("Stop", sid, repo=repo, pid=proc.pid if with_pid else None)
        self.assertEqual(self.holder(repo), sid)
        return proc

    def a_citizen(self, sid="sid-tm", role="task-manager", repo=None):
        """A live session that is not the main manager, idle now."""
        proc = self.live()
        self.act(sid, repo=repo, role=role, pid=proc.pid)
        self.line("Stop", sid, repo=repo, role=role, pid=proc.pid)
        self.assertIn("s:" + sid, self.agents())
        return proc


# -- R1: live sessions come back with no line --------------------------------

class TestComesBack(RosterCase):
    def test_a_citizen_is_back_at_once(self):
        self.a_citizen("sid-tm")
        before = self.agents()["s:sid-tm"]
        self.restart()
        self.assertIn("s:sid-tm", self.agents(), "an idle task manager vanished with the restart")
        after = self.agents()["s:sid-tm"]
        for key in ("id", "role", "label", "task", "terr"):
            self.assertEqual(after[key], before[key], key)
        self.assertEqual(after["role"], "task-manager")
        self.assertEqual(after["terr"], self.terr())
        self.assertFalse(after["done"])

    def test_no_line_was_read_for_it(self):
        self.a_citizen("sid-tm")
        self.restart()
        health = self.st.health()
        self.assertEqual(health["lines"], 0)
        self.assertEqual(health["agents"], 1)

    def test_a_lead_has_its_office_again(self):
        self.a_citizen("sid-tm")
        before = self.agents()["s:sid-tm"]
        self.assertIsNotNone(before.get("office"), "fixture: a task manager is a lead with an office")
        self.restart()
        self.assertIsNotNone(self.agents()["s:sid-tm"].get("office"))

    def test_the_governor_is_back_idle_not_unknown(self):
        self.a_governor("sid-gov")
        self.restart()
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.assertEqual(self.holder(), "sid-gov")
        self.assertNotIn("s:sid-gov", self.agents())

    def test_governor_and_citizens_together(self):
        self.a_governor("sid-gov")
        self.a_citizen("sid-tm")
        self.a_citizen("sid-helper", role="")
        self.restart()
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.assertEqual(set(self.agents()), {"s:sid-tm", "s:sid-helper"})

    def test_each_one_in_its_own_territory(self):
        self.a_governor("sid-gov-a")
        self.a_governor("sid-gov-b", repo=self.repo_b)
        self.a_citizen("sid-tm-b", repo=self.repo_b)
        self.restart()
        self.assertEqual(sorted(self.govs()), sorted([(self.terr(), "idle"), (self.terr(self.repo_b), "idle")]))
        self.assertEqual(self.holder(self.repo_b), "sid-gov-b")
        self.assertEqual(self.agents()["s:sid-tm-b"]["terr"], self.terr(self.repo_b))

    def test_a_second_restart_keeps_them(self):
        self.a_governor("sid-gov")
        self.a_citizen("sid-tm")
        self.restart()
        self.restart()
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.assertIn("s:sid-tm", self.agents())

    def test_subagents_are_not_in_the_roster(self):
        tm = self.a_citizen("sid-tm")
        self.line("SubagentStart", "sid-tm", aid="agent-w1", at="worker", role="task-manager", pid=tm.pid)
        self.assertIn("agent-w1", self.agents())
        self.restart()
        self.assertEqual(set(self.agents()), {"s:sid-tm"}, "sessions first; a subagent comes back on its next event")
        self.line("PostToolUse", "sid-tm", aid="agent-w1", at="worker", role="task-manager", pid=tm.pid)
        self.assertIn("agent-w1", self.agents())


# -- R1: a restored session is the same session -------------------------------

class TestSameSession(RosterCase):
    def test_a_citizens_next_line_makes_no_second_spawn(self):
        tm = self.a_citizen("sid-tm")
        self.restart()
        self.listen()
        self.act("sid-tm", role="task-manager", pid=tm.pid)
        types = [e["type"] for e in self.heard()]
        self.assertNotIn("spawn", types)
        self.assertIn("tool", types)
        self.assertEqual(set(self.agents()), {"s:sid-tm"})

    def test_the_governors_next_line_governs(self):
        gov = self.a_governor("sid-gov")
        self.restart()
        self.listen()
        self.line("UserPromptSubmit", "sid-gov", pid=gov.pid)
        events = self.heard()
        self.assertNotIn("spawn", [e["type"] for e in events])
        busy = [e for e in events if e["type"] == "gov"]
        self.assertEqual([(e["state"], e["terr"], e.get("present")) for e in busy],
                         [("busy", self.terr(), True)])
        self.assertEqual(self.holder(), "sid-gov")

    def test_session_end_ends_it_for_good(self):
        tm = self.a_citizen("sid-tm")
        self.restart()
        self.line("SessionEnd", "sid-tm", role="task-manager", pid=tm.pid)
        self.assertEqual(self.agents(), {})
        self.assertNotIn("sid-tm", self.roster_text())
        self.restart()
        self.assertEqual(self.agents(), {}, "its process still runs, but the session said it ended")

    def test_a_restored_governor_that_dies_is_ended_by_check_seats(self):
        gov = self.a_governor("sid-gov")
        self.restart()
        self.listen()
        self.kill(gov)
        self.st.check_seats(200.0)
        gone = [e for e in self.heard() if e["type"] == "gov"]
        self.assertEqual([(e["terr"], e.get("present")) for e in gone], [(self.terr(), False)])
        self.assertIsNone(self.holder())
        self.assertNotIn("sid-gov", self.roster_text())


# -- R1: dead ones are dropped -------------------------------------------------

class TestDeadAreDropped(RosterCase):
    def test_a_dead_citizen_is_gone(self):
        self.a_citizen("sid-keep")
        dead = self.a_citizen("sid-dead")
        self.kill(dead)
        self.restart()
        self.assertEqual(set(self.agents()), {"s:sid-keep"})
        self.assertNotIn("sid-dead", self.roster_text(), "a dropped entry leaves the file too")
        self.assertIn("sid-keep", self.roster_text())

    def test_a_dead_governor_is_gone(self):
        gov = self.a_governor("sid-gov")
        self.a_citizen("sid-tm")
        self.kill(gov)
        self.restart()
        self.assertEqual(self.govs(), [], "a dead main manager is nobody, not idle and not unknown")
        self.assertIsNone(self.holder())
        self.assertEqual(set(self.agents()), {"s:sid-tm"})

    def test_ended_before_the_restart_stays_gone(self):
        tm = self.a_citizen("sid-tm")
        self.line("SessionEnd", "sid-tm", role="task-manager", pid=tm.pid)
        self.assertNotIn("sid-tm", self.roster_text())
        self.restart()
        self.assertEqual(self.agents(), {})

    def test_a_citizen_with_no_known_pid_is_not_brought_back(self):
        self.act("sid-oldhook", role="task-manager")          # no "pid" key: an old hook
        self.assertIn("s:sid-oldhook", self.agents())
        self.restart()
        self.assertEqual(self.agents(), {}, "nothing proves it alive: it shows up on its next line")
        self.act("sid-oldhook", role="task-manager")
        self.assertIn("s:sid-oldhook", self.agents())

    def test_a_garbage_roster_is_an_empty_one(self):
        for garbage in ("", "not json", "[1, 2", '{"sessions": 7}', '{"sessions": [3, null, {"sid": 5}]}',
                        '[{"sid": "x", "pid": "abc", "repo": 1}]'):
            with self.subTest(roster=garbage):
                with open(self.roster, "w") as fh:
                    fh.write(garbage)
                self.restart()                                  # never raises
                self.assertEqual(self.agents(), {})
                self.assertEqual(self.govs(), [])
        tm = self.a_citizen("sid-tm")                           # and the next write is a good file
        json.loads(self.roster_text())
        self.restart()
        self.assertIn("s:sid-tm", self.agents())
        self.assertIsNotNone(tm)

    def test_no_roster_path_no_file(self):
        self.st = self.make_state(roster_path=None)
        self.a_citizen("sid-tm")
        self.assertEqual(os.listdir(self.city_dir), [])
        self.st = self.make_state(roster_path=None)
        self.assertEqual(self.agents(), {})


# -- R1: the seat at load follows the lock, like on a line ---------------------

class TestSeatAtLoad(RosterCase):
    def test_a_released_lock_makes_the_old_governor_a_citizen(self):
        self.a_governor("sid-gov")
        self.drop_lock()
        self.restart()
        self.assertEqual(self.govs(), [])
        self.assertIsNone(self.holder())
        self.assertIn("s:sid-gov", self.agents(), "alive and not the main manager: a citizen")

    def test_a_lock_that_moved_seats_the_new_holder(self):
        self.a_governor("sid-old")
        new = self.a_citizen("sid-new", role="")
        self.write_lock(new.pid, "sid-new")                     # take-over while the server was down
        self.restart()
        self.assertEqual(self.holder(), "sid-new")
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.assertEqual(set(self.agents()), {"s:sid-old"})

    def test_an_old_lock_seats_the_session_with_that_pid(self):
        proc = self.live()
        self.write_lock(proc.pid, old=True)
        self.act("sid-gov", pid=proc.pid)                        # new hooks: matched by the line's pid
        self.assertEqual(self.holder(), "sid-gov")
        self.restart()
        self.assertEqual(self.holder(), "sid-gov")
        self.assertEqual(self.govs(), [(self.terr(), "idle")])


# -- R1: the file ------------------------------------------------------------

class TestTheFile(RosterCase):
    def test_it_names_every_live_session(self):
        self.a_governor("sid-gov")
        self.a_citizen("sid-tm")
        json.loads(self.roster_text())
        self.assertIn("sid-gov", self.roster_text())
        self.assertIn("sid-tm", self.roster_text())

    def test_no_temp_file_is_left(self):
        self.a_governor("sid-gov")
        tm = self.a_citizen("sid-tm")
        self.line("SessionEnd", "sid-tm", role="task-manager", pid=tm.pid)
        self.assertEqual(os.listdir(self.city_dir), ["roster.json"])

    def test_a_tool_line_never_rewrites_it(self):
        gov = self.a_governor("sid-gov")
        tm = self.a_citizen("sid-tm")
        before = os.stat(self.roster)
        text = self.roster_text()
        for i in range(30):
            self.line("PreToolUse", "sid-tm", 101.0 + i, role="task-manager", pid=tm.pid, tool="Edit")
            self.act("sid-tm", 101.5 + i, role="task-manager", pid=tm.pid, tool="Edit")
            self.act("sid-gov", 101.7 + i, pid=gov.pid, tool="Bash")
        after = os.stat(self.roster)
        self.assertEqual((after.st_ino, after.st_mtime_ns), (before.st_ino, before.st_mtime_ns),
                         "the roster was written again for a plain tool line")
        self.assertEqual(self.roster_text(), text)

    def test_a_roster_that_cannot_be_written_never_stops_the_city(self):
        self.st = self.make_state(roster_path=os.path.join(self.base, "no", "such", "dir", "roster.json"))
        self.a_citizen("sid-tm")                                # no exception
        self.assertIn("s:sid-tm", self.agents())


# -- R3: old hooks (no "pid" on the line) --------------------------------------

class TestOldHooks(RosterCase):
    def test_the_locks_sid_makes_it_the_governor(self):
        self.a_governor("sid-gov", with_pid=False)
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.assertNotIn("s:sid-gov", self.agents())

    def test_it_comes_back_after_a_restart(self):
        self.a_governor("sid-gov", with_pid=False)             # its pid: the lock's
        self.restart()
        self.assertEqual(self.holder(), "sid-gov")
        self.assertEqual(self.govs(), [(self.terr(), "idle")])

    def test_dead_it_does_not_come_back(self):
        gov = self.a_governor("sid-gov", with_pid=False)
        self.kill(gov)
        self.restart()
        self.assertEqual(self.govs(), [])
        self.assertEqual(self.agents(), {})


class TestOldLockAgain(RosterCase):
    """R3b: the session's own old agent-start.sh wrote "<pid> <date> <time>" again (a compaction)."""

    def seat_then_old_lock(self):
        gov = self.a_governor("sid-gov", with_pid=False)
        self.write_lock(gov.pid, old=True)
        return gov

    def test_its_next_line_keeps_the_seat(self):
        self.seat_then_old_lock()
        self.listen()
        self.act("sid-gov")
        self.assertEqual(self.holder(), "sid-gov")
        self.assertNotIn("s:sid-gov", self.agents())
        self.assertEqual([e for e in self.heard() if e["type"] == "gov" and e.get("present") is False], [])

    def test_check_seats_keeps_the_seat(self):
        self.seat_then_old_lock()
        self.listen()
        self.st.check_seats(200.0)
        self.assertEqual(self.holder(), "sid-gov")
        self.assertEqual([e for e in self.heard() if e["type"] == "gov"], [])

    def test_gov_next_still_knows_it(self):
        self.seat_then_old_lock()
        reply = self.st.gov_next("sid-gov", self.repo, "w1", 0.0, pid="")
        self.assertNotEqual(reply.get("state"), "not-main")

    def test_it_comes_back_after_a_restart(self):
        self.seat_then_old_lock()
        self.restart()
        self.assertEqual(self.holder(), "sid-gov")
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.act("sid-gov")                                     # and its line still governs
        self.assertEqual(self.holder(), "sid-gov")
        self.assertNotIn("s:sid-gov", self.agents())

    def test_an_old_lock_of_another_pid_takes_the_seat_away(self):
        self.a_governor("sid-gov", with_pid=False)
        other = self.live()
        self.write_lock(other.pid, old=True)
        self.act("sid-gov")
        self.assertIsNone(self.holder())
        self.assertIn("s:sid-gov", self.agents())

    def test_another_session_never_gets_the_seat_from_an_old_lock(self):
        self.seat_then_old_lock()
        self.act("sid-other")                                   # no pid either: not the holder
        self.assertEqual(self.holder(), "sid-gov")
        self.assertIn("s:sid-other", self.agents())


# -- the real server: stop, start, look ----------------------------------------

def hook_line(ev, sid, repo, pid, role=""):
    return json.dumps({"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "Read", "nt": "", "proj": "shop",
                       "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "ask": "",
                       "wt": "", "file": "", "tp": "", "pid": str(pid)}) + "\n"


class TestServerRestart(ServerCase):
    def setUp(self):
        super().setUp()
        self.repo = os.path.join(os.path.realpath(self.base), "shop", ".git")
        os.makedirs(self.repo)
        self.sessions = []

    def tearDown(self):
        for p in self.sessions:
            if p.poll() is None:
                p.kill()
                p.wait()
        super().tearDown()

    def live(self):
        proc = subprocess.Popen(["sleep", "120"])
        self.sessions.append(proc)
        return proc

    def stop(self, proc):
        proc.send_signal(signal.SIGTERM)
        proc.wait(10)
        self.assertIsNone(self.on(), "DIR/on is gone with the server")

    def first_run(self):
        """A main manager and a task manager, both seen, both idle; then the server stops."""
        self.gov, self.tm = self.live(), self.live()
        lock_file(self.repo, "sid-gov", pid=self.gov.pid)
        server = self.start()
        for sid, proc, role in (("sid-gov", self.gov, ""), ("sid-tm", self.tm, "task-manager")):
            self.append(hook_line("PostToolUse", sid, self.repo, proc.pid, role))
            self.append(hook_line("Stop", sid, self.repo, proc.pid, role))
        self.assertTrue(wait_for(lambda: self.health()["lines"] == 4), "the 4 lines were never read")
        self.assertTrue(os.path.exists(os.path.join(self.dir, "roster.json")), "serve keeps DIR/roster.json")
        self.stop(server)

    def look(self):
        return self.sse().messages[0]

    def test_both_are_shown_at_once_with_no_new_event(self):
        self.first_run()
        self.start()
        snap = self.look()
        self.assertEqual([(g["terr"], g["state"]) for g in snap["govs"]], [(ac.territory_id(self.repo), "idle")])
        self.assertEqual([(a["id"], a["role"], a["terr"]) for a in snap["agents"]],
                         [("s:sid-tm", "task-manager", ac.territory_id(self.repo))])
        self.assertEqual(self.health()["lines"], 0, "nothing new was read: they came from the roster")

    def test_a_killed_session_is_gone_after_the_restart(self):
        self.first_run()
        self.tm.kill()
        self.tm.wait()
        self.start()
        snap = self.look()
        self.assertEqual(snap["agents"], [])
        self.assertEqual([g["state"] for g in snap["govs"]], ["idle"], "the main manager is still there")


if __name__ == "__main__":
    unittest.main()
