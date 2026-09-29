"""Failing tests: the governor seat frees when its holder is gone (ideas-soon S1, owner-approved 2026-09-29).

Bug: a territory's seat (its Reducer's gov_sid) is only freed by the holder's SessionEnd. A main
manager that crashed never sends one, so a new main session in the same repo shows as a citizen
("s:<sid>") forever.

CONTRACT (bin/agent_city.py, CityState.feed_line; the Reducer stays repo-blind)

  Signals the server really has:
    pid  - the line's "repo" field is the git common dir; <repo>/agent_main.lock is the main
           manager lock bin/agent-start.sh writes: "<pid> <date>". While the seat holder A acts
           (every line of A's session), the server reads that lock and keeps its pid as A's pid
           ONLY when that pid is alive at read time (os.kill(pid, 0)); a later line of A reads it
           again (the lock may be written after A's first line). A missing, empty, garbage or
           unreadable lock, or a pid that is dead at read time, gives no pid; never an error.
    time - the feed_line "now" of A's last line.

  When a line of a roleless session B (no aid, sid set, role "") comes in, B not yet known to the
  territory's Reducer, and the seat is held by another sid A, the server first asks: is A gone?
    - A's pid is known: gone when that pid is dead now. Alive -> not gone, however quiet A is.
    - no pid known for A: gone when A's last line is more than GOV_FRESH_SEC (15 min) old.
  A gone -> the server ends A exactly as a SessionEnd line of A in that territory would (A's
  subagents leave, a "gov" event with present False, world.json gov_seen, gov/next routing for
  A's sid forgotten), then feeds B's line: B takes the seat at once.
  A not gone -> nothing changes: B is a citizen "s:B" (a human-direct second session).
  A line with a role never ends A. Other territories are never touched.
  A that acts again after it was judged gone is a new session: a citizen "s:A"; B keeps the seat.

requirements/city.md, "Data path": the seat frees when its holder is gone.

Run: python3 -m unittest tests.test_agent_city_seat </dev/null
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))

import agent_city as ac  # noqa: E402

FRESH = ac.GOV_FRESH_SEC


def dead_pid():
    proc = subprocess.Popen(["sleep", "60"])
    proc.kill()
    proc.wait()
    return proc.pid


class SeatCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_seat_")
        self.world = os.path.join(self.base, "world.json")
        self.repo = os.path.join(self.base, "repoA", ".git")
        os.makedirs(self.repo)
        self.lock = os.path.join(self.repo, "agent_main.lock")
        self.terr = ac.territory_id(self.repo)
        self.procs = []
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world,
                               plans=ac.load_plans(), count_fn=lambda i: 0,
                               balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}})

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
                p.wait()
        shutil.rmtree(self.base, ignore_errors=True)

    # -- helpers ---------------------------------------------------------

    def live_pid(self):
        proc = subprocess.Popen(["sleep", "60"])
        self.procs.append(proc)
        return proc

    def kill(self, proc):
        proc.kill()
        proc.wait()

    def write_lock(self, text):
        with open(self.lock, "w") as fh:
            fh.write(text)

    def line(self, ev, sid, now, repo=None, role="", aid="", at="", tool="Read"):
        self.st.feed_line({"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": "p",
                           "role": role, "desc": "", "sub": "", "q": "", "klen": "",
                           "repo": self.repo if repo is None else repo, "ask": "", "wt": "", "file": ""}, now)

    def holder(self, repo=None):
        return self.st.reducers[self.repo if repo is None else repo].gov_sid

    def snapshot(self):
        client = self.st.add_client()
        try:
            data = client.queue.get_nowait().decode("utf-8")
        finally:
            self.st.remove_client(client)
        return json.loads(data.split("data:", 1)[1])

    def agent_ids(self):
        return {a["id"] for a in self.snapshot()["agents"]}

    def assert_governor(self, sid):
        self.assertEqual(self.holder(), sid)
        self.assertNotIn("s:" + sid, self.agent_ids())

    def assert_citizen(self, sid, holder):
        self.assertEqual(self.holder(), holder)
        self.assertIn("s:" + sid, self.agent_ids())


class TestWithLock(SeatCase):
    def test_dead_holder_frees_the_seat_at_once(self):
        a = self.live_pid()
        self.write_lock("%d 2026-09-29 09:00\n" % a.pid)
        self.line("UserPromptSubmit", "A", 1000.0)
        self.line("PostToolUse", "A", 1001.0)
        self.kill(a)
        self.line("UserPromptSubmit", "B", 1002.0)
        self.assert_governor("B")
        self.assertEqual([(g["terr"], g["state"]) for g in self.snapshot()["govs"]], [(self.terr, "busy")])

    def test_takeover_after_a_crash(self):
        # the real case: A crashed, B's agent-start saw a dead lock and wrote its own live pid
        a = self.live_pid()
        self.write_lock("%d 2026-09-29 09:00\n" % a.pid)
        self.line("UserPromptSubmit", "A", 1000.0)
        self.line("PostToolUse", "A", 1001.0)
        self.kill(a)
        self.write_lock("%d 2026-09-29 09:05\n" % os.getpid())
        self.line("UserPromptSubmit", "B", 1002.0)
        self.assert_governor("B")

    def test_live_holder_keeps_the_seat_however_quiet(self):
        self.write_lock("%d 2026-09-29 09:00\n" % os.getpid())
        self.line("UserPromptSubmit", "A", 1000.0)
        self.line("UserPromptSubmit", "B", 1000.0 + 3 * 3600)
        self.assert_citizen("B", holder="A")

    def test_the_lock_is_read_again_on_later_lines(self):
        self.write_lock("%d 2026-09-29 08:00\n" % dead_pid())   # old main manager, before A's agent-start
        self.line("UserPromptSubmit", "A", 1000.0)
        self.write_lock("%d 2026-09-29 09:00\n" % os.getpid())  # A's agent-start wrote its pid
        self.line("PostToolUse", "A", 1001.0)
        self.line("UserPromptSubmit", "B", 1001.0 + 3 * 3600)
        self.assert_citizen("B", holder="A")

    def test_a_pid_dead_at_read_is_never_kept(self):
        # the lock names someone long gone: A has no pid, so only time can free the seat
        self.write_lock("%d 2026-09-29 08:00\n" % dead_pid())
        self.line("UserPromptSubmit", "A", 1000.0)
        self.line("UserPromptSubmit", "B", 1005.0)
        self.assert_citizen("B", holder="A")

    def test_the_gone_holder_is_ended_like_a_session_end(self):
        a = self.live_pid()
        self.write_lock("%d 2026-09-29 09:00\n" % a.pid)
        self.line("UserPromptSubmit", "A", 1000.0)
        self.line("SubagentStart", "A", 1001.0, aid="w1", at="auto-pipeline:worker")
        self.st.gov_next("A", self.repo, "watch-A", 0)
        self.assertIn("w1", self.agent_ids())
        self.kill(a)
        client = self.st.add_client()
        client.queue.get_nowait()  # the snapshot
        self.line("UserPromptSubmit", "B", 1002.0)
        events = []
        while not client.queue.empty():
            events.append(json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1]))
        self.st.remove_client(client)
        self.assert_governor("B")
        self.assertNotIn("w1", self.agent_ids())
        self.assertNotIn("A", [g["sid"] for g in self.st.governors.values()])
        govs = [(e.get("terr"), e.get("present")) for e in events if e.get("type") == "gov"]
        self.assertIn((self.terr, False), govs)
        self.assertEqual(govs[-1], (self.terr, True))
        self.assertLess(govs.index((self.terr, False)), len(govs) - 1)
        with open(self.world, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh).get("gov_seen", {}).get(self.repo), "B")

    def test_the_old_holder_back_is_a_citizen(self):
        a = self.live_pid()
        self.write_lock("%d 2026-09-29 09:00\n" % a.pid)
        self.line("UserPromptSubmit", "A", 1000.0)
        self.kill(a)
        self.line("UserPromptSubmit", "B", 1001.0)
        self.line("PostToolUse", "A", 1002.0)
        self.assert_citizen("A", holder="B")

    def test_a_line_with_a_role_never_ends_the_holder(self):
        a = self.live_pid()
        self.write_lock("%d 2026-09-29 09:00\n" % a.pid)
        self.line("UserPromptSubmit", "A", 1000.0)
        self.kill(a)
        self.line("UserPromptSubmit", "T", 1000.0 + FRESH + 60, role="task-manager")
        self.assert_citizen("T", holder="A")

    def test_other_territories_are_not_touched(self):
        a = self.live_pid()
        self.write_lock("%d 2026-09-29 09:00\n" % a.pid)
        self.line("UserPromptSubmit", "A", 1000.0)
        self.kill(a)
        other = os.path.join(self.base, "repoB", ".git")
        os.makedirs(other)
        self.line("UserPromptSubmit", "B", 1001.0, repo=other)
        self.assertEqual(self.holder(), "A")
        self.assertEqual(self.holder(other), "B")


class TestWithoutLock(SeatCase):
    def test_silent_holder_frees_after_fresh_window(self):
        self.line("UserPromptSubmit", "A", 1000.0)
        self.line("UserPromptSubmit", "B", 1000.0 + FRESH + 1)
        self.assert_governor("B")

    def test_the_last_line_counts_not_the_first(self):
        self.line("UserPromptSubmit", "A", 1000.0)
        self.line("PostToolUse", "A", 1800.0)
        self.line("UserPromptSubmit", "B", 1800.0 + FRESH - 1)
        self.assert_citizen("B", holder="A")

    def test_a_repo_path_that_does_not_exist(self):
        repo = "/work/no-such-repo-%d/.git" % os.getpid()
        self.line("UserPromptSubmit", "A", 1000.0, repo=repo)
        self.line("UserPromptSubmit", "B", 1000.0 + 60, repo=repo)
        self.assertEqual(self.holder(repo), "A")
        self.line("UserPromptSubmit", "C", 1000.0 + FRESH + 1, repo=repo)
        self.assertEqual(self.holder(repo), "C")

    def test_a_bad_lock_never_breaks_the_server(self):
        # pid 0 and negative pids name process groups, not a session: never a pid
        for n, text in enumerate(["", "garbage\n", "-5 x\n", "0 x\n", "99999999999999999999999 x\n",
                                  "12ab 2026\n", "\x00\xff\n"]):
            with self.subTest(lock=text):
                repo = os.path.join(self.base, "bad%d" % n, ".git")
                os.makedirs(repo)
                with open(os.path.join(repo, "agent_main.lock"), "w") as fh:
                    fh.write(text)
                self.line("UserPromptSubmit", "A", 1000.0, repo=repo)
                self.line("UserPromptSubmit", "B", 1060.0, repo=repo)
                self.assertEqual(self.holder(repo), "A")
                self.line("UserPromptSubmit", "C", 1000.0 + FRESH + 1, repo=repo)
                self.assertEqual(self.holder(repo), "C")

    def test_an_unreadable_lock_falls_back_to_time(self):
        if os.geteuid() == 0:
            self.skipTest("root reads any file")
        self.write_lock("%d 2026-09-29 09:00\n" % os.getpid())
        os.chmod(self.lock, 0)
        self.line("UserPromptSubmit", "A", 1000.0)
        self.line("UserPromptSubmit", "B", 1000.0 + FRESH + 1)
        self.assert_governor("B")


class TestUnchanged(SeatCase):
    def test_session_end_still_frees_the_seat(self):
        self.write_lock("%d 2026-09-29 09:00\n" % os.getpid())
        self.line("UserPromptSubmit", "A", 1000.0)
        self.line("SessionEnd", "A", 1001.0)
        self.line("UserPromptSubmit", "B", 1002.0)
        self.assert_governor("B")


if __name__ == "__main__":
    unittest.main()
