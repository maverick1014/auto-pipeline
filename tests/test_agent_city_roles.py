"""Failing tests: the city governor is the repo's real main manager only (city-roles, owner 2026-09-30).

Bug (laptop, 2026-09-30): the city showed "auto-pipeline 总督 busy" for a session of another repo
(E1: it sent one line with repo "", landed in the start territory and took the free seat), while
the real main manager (the lock holder) came in next and stayed a citizen (E2: a known citizen is
never promoted). The seat went to "the first session without AGENT_ROLE", not to the main manager.

CONTRACT (bin/agent_city.py CityState; bin/agent-city-hook.sh). Supersedes
tests/test_agent_city_seat.py (seat = first roleless session, freed when its holder is gone).

  The lock. bin/agent-start.sh writes <git common dir>/agent_main.lock, one line:
      "<pid> <YYYY-MM-DD> <HH:MM> <sid> <terminal>"      sid / terminal "-" when unknown
  An older lock has only "<pid> <date> <time>" (no sid).

  CityState(..., main_fn=None). main_fn(identity) -> (pid: int, sid: str) of the live lock holder
  of that territory, or None. Default: read <identity>/agent_main.lock; pid = first word (digits,
  > 0, alive: os.kill(pid, 0) does not say ProcessLookupError); sid = fourth word, "" when missing
  or "-". No file, garbage, a dead pid, identity None -> None. Never raises. Tests may pass their own.

  Holder. A session line (sid set, aid "") is the holder's when main_fn(identity) gives (pid, sid)
  and (sid != "" and the line's sid == sid) or (the line's "pid" field, digits, == pid).
  The hook adds that field: "pid" = $CLAUDE_PID when it is all digits, else "" (new last key).

  R1 seat = holder only.
    - The holder's line makes it the territory's governor, whatever its role, even when it is
      already a citizen there (its citizen "s:<sid>" leaves, a "gov" event says present True).
    - Every other session is a citizen "s:<sid>" (roleless too). No live holder -> no governor.
    - The lock changes hands -> the new holder takes the seat on its next line; the old governor
      is no longer governor (its next line makes it a citizen).
    - The governor's own line when it is no longer the holder (lock gone, or names someone else):
      it leaves the seat at once and that same line makes it a citizen.
    - check_seats(now) (the server calls it about every 2 s, next to recount): a territory whose
      governor is no longer the holder loses it without any line -- a "gov" event with present
      False for that territory; a governor whose pid is dead is ended exactly like its SessionEnd
      (its subagents leave too). Other territories are never touched.
    - Snapshot "govs": a world.json gov_seen entry shows "unknown" only while that territory has
      a live holder; else it is left out.

  R2 a line with repo "" of a sid last seen with a repo R (any line of that sid, session or
    subagent) goes to R, never to the start territory. An unknown sid with no repo keeps the old
    fallback: the start territory.

  gov_next(sid, repo, watcher, timeout, pid="") (GET /api/gov/next?...&pid=): only the holder of
    repo is a governor there. Anyone else gets {"state": "not-main"} at once, is never registered
    in .governors, never gets a governor question. python3 agent_city.py gov-watch sends
    pid = $CLAUDE_PID (digits) else os.getppid(); on "not-main" it waits for its own messages
    like chat-watch (GET /api/chat/next, then stderr + exit 2); on "message" it wakes the same way
    (the chat contract already said so).

requirements/city.md, "Data path".

Run: python3 -m unittest tests.test_agent_city_roles </dev/null
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agent_city as ac  # noqa: E402


def dead_pid():
    proc = subprocess.Popen(["sleep", "60"])
    proc.kill()
    proc.wait()
    return proc.pid


class RolesCase(unittest.TestCase):
    """CityState with real lock files: repo A (the start repo) and repo B."""

    start_repo = True

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_roles_"))
        self.world = os.path.join(self.base, "world.json")
        self.repo = os.path.join(self.base, "repoA", ".git")
        self.repo_b = os.path.join(self.base, "repoB", ".git")
        os.makedirs(self.repo)
        os.makedirs(self.repo_b)
        self.procs = []
        self.st = self.make_state()
        self.client = None

    def make_state(self, **kw):
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world,
                            plans=ac.load_plans(), count_fn=lambda i: 0,
                            balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}},
                            start_repo=self.repo if self.start_repo else None, **kw)

    def tearDown(self):
        if self.client is not None:
            self.st.remove_client(self.client)
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

    def write_lock(self, pid, sid="-", repo=None, term="-", old=False):
        path = os.path.join(self.repo if repo is None else repo, "agent_main.lock")
        with open(path, "w") as fh:
            if old:
                fh.write("%s 2026-09-30 10:00\n" % pid)
            else:
                fh.write("%s 2026-09-30 10:00 %s %s\n" % (pid, sid, term))

    def drop_lock(self, repo=None):
        os.remove(os.path.join(self.repo if repo is None else repo, "agent_main.lock"))

    def line(self, ev, sid, now=100.0, repo=None, role="", aid="", at="", tool="Read", pid=""):
        self.st.feed_line({"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "",
                           "proj": "p", "role": role, "desc": "", "sub": "", "q": "", "klen": "",
                           "repo": self.repo if repo is None else repo, "ask": "", "wt": "",
                           "file": "", "tp": "", "pid": pid}, now)

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

    def agent_ids(self):
        return {a["id"] for a in self.snapshot()["agents"]}

    def govs(self):
        return {g["terr"]: g["state"] for g in self.snapshot()["govs"]}

    def listen(self):
        """Start collecting broadcast events (after the snapshot)."""
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

    def assert_governor(self, sid, repo=None):
        self.assertEqual(self.holder(repo), sid)
        self.assertNotIn("s:" + sid, self.agent_ids())

    def assert_citizen(self, sid, repo=None):
        self.assertNotEqual(self.holder(repo), sid)
        self.assertIn("s:" + sid, self.agent_ids())


# -- the lock reader --------------------------------------------------------

class TestMainFn(RolesCase):
    def test_default_reads_pid_and_sid(self):
        p = self.live_pid()
        self.write_lock(p.pid, "sid-m", term="term_1")
        self.assertEqual(self.st.main_fn(self.repo), (p.pid, "sid-m"))

    def test_old_lock_has_no_sid(self):
        p = self.live_pid()
        self.write_lock(p.pid, old=True)
        self.assertEqual(self.st.main_fn(self.repo), (p.pid, ""))

    def test_dash_is_no_sid(self):
        p = self.live_pid()
        self.write_lock(p.pid, "-")
        self.assertEqual(self.st.main_fn(self.repo), (p.pid, ""))

    def test_nothing_live_is_none(self):
        self.assertIsNone(self.st.main_fn(self.repo))           # no lock
        self.assertIsNone(self.st.main_fn(None))
        self.write_lock(dead_pid(), "sid-m")
        self.assertIsNone(self.st.main_fn(self.repo))           # dead pid
        for garbage in ("", "\n", "abc 2026", "-5 x y z", "0 a b c"):
            with open(os.path.join(self.repo, "agent_main.lock"), "w") as fh:
                fh.write(garbage)
            with self.subTest(lock=garbage):
                self.assertIsNone(self.st.main_fn(self.repo))

    def test_a_given_main_fn_is_used(self):
        st = self.make_state(main_fn=lambda identity: (os.getpid(), "gx"))
        st.feed_line({"ev": "PostToolUse", "sid": "gx", "aid": "", "role": "", "tool": "Read",
                      "repo": self.repo}, 1.0)
        self.assertEqual(st.reducers[self.repo].gov_sid, "gx")


# -- R1: the seat is the lock holder's ---------------------------------------

class TestSeatIsTheHolder(RolesCase):
    def test_no_lock_no_governor(self):
        self.act("a")
        self.act("b")
        self.assertIsNone(self.holder())
        self.assert_citizen("a")
        self.assert_citizen("b")
        self.assertNotIn(ac.territory_id(self.repo), self.govs())

    def test_holder_by_sid(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("h")
        self.act("m")
        self.assert_governor("m")
        self.assert_citizen("h")

    def test_holder_by_pid_when_the_lock_has_no_sid(self):
        p = self.live_pid()
        self.write_lock(p.pid, old=True)
        self.act("x", pid="")
        self.act("m", pid=str(p.pid))
        self.assert_governor("m")
        self.assert_citizen("x")

    def test_a_wrong_pid_is_not_the_holder(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("x", pid=str(p.pid + 100000))
        self.assertIsNone(self.holder())
        self.assert_citizen("x")

    def test_dead_holder_is_nobody(self):
        self.write_lock(dead_pid(), "m")
        self.act("m")
        self.assertIsNone(self.holder())
        self.assert_citizen("m")

    def test_the_holder_governs_whatever_its_role(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m", role="task-manager")
        self.assert_governor("m")

    def test_a_foreign_first_session_never_takes_the_seat(self):
        """E1 + E2: a roleless session that is not the holder comes first; the holder next."""
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("foreign", repo="")        # no repo: start territory (repo A), unknown sid
        self.assertIsNone(self.holder())
        self.act("m")
        self.assert_governor("m")
        self.assert_citizen("foreign")

    def test_the_seat_follows_the_lock(self):
        """E3 / take-over: the lock moves to a known citizen; it becomes governor on its next line."""
        old, new = self.live_pid(), self.live_pid()
        self.write_lock(old.pid, "m")
        self.act("m", 100.0)
        self.act("h", 101.0)
        self.assert_governor("m")
        self.assert_citizen("h")
        self.write_lock(new.pid, "h")
        self.listen()
        self.act("h", 102.0)
        self.assert_governor("h")
        events = self.heard()
        self.assertIn("s:h", [e.get("id") for e in events if e.get("type") == "leave"])
        gov = [e for e in events if e.get("type") == "gov"]
        self.assertTrue(gov, "a seat change is always told to the page")
        self.assertIs(gov[-1].get("present"), True)
        self.assertEqual(gov[-1].get("terr"), ac.territory_id(self.repo))
        self.act("m", 103.0)
        self.assert_citizen("m")
        self.assert_governor("h")

    def test_a_released_lock_turns_the_governor_into_a_citizen_on_its_next_line(self):
        """R3: close case released the lock; the old main manager goes on typing."""
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m", 100.0)
        self.assert_governor("m")
        self.drop_lock()
        self.act("m", 101.0)
        self.assertIsNone(self.holder())
        self.assert_citizen("m")

    def test_other_territories_keep_their_governor(self):
        pa, pb = self.live_pid(), self.live_pid()
        self.write_lock(pa.pid, "ma")
        self.write_lock(pb.pid, "mb", repo=self.repo_b)
        self.act("ma")
        self.act("mb", repo=self.repo_b)
        self.drop_lock()
        self.act("ma", 101.0)
        self.assertIsNone(self.holder())
        self.assertEqual(self.holder(self.repo_b), "mb")


class TestCheckSeats(RolesCase):
    def test_a_dead_holder_leaves_without_any_line(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m", 100.0)
        self.line("SubagentStart", "m", 100.5, aid="a1", at="worker")
        self.assert_governor("m")
        self.assertIn("a1", self.agent_ids())
        self.listen()
        self.kill(p)
        self.st.check_seats(200.0)
        self.assertIsNone(self.holder())
        ids = self.agent_ids()
        self.assertNotIn("a1", ids, "a dead governor ends like its SessionEnd: its subagents leave")
        self.assertNotIn("s:m", ids)
        gov = [e for e in self.heard() if e.get("type") == "gov"]
        self.assertTrue(gov, "the page is told")
        self.assertIs(gov[-1].get("present"), False)
        self.assertEqual(gov[-1].get("terr"), ac.territory_id(self.repo))
        self.assertNotIn(ac.territory_id(self.repo), self.govs())

    def test_a_released_lock_frees_the_seat_without_any_line(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m", 100.0)
        self.listen()
        self.drop_lock()
        self.st.check_seats(200.0)
        self.assertIsNone(self.holder())
        gov = [e for e in self.heard() if e.get("type") == "gov"]
        self.assertTrue(gov and gov[-1].get("present") is False)
        self.act("m", 201.0)
        self.assert_citizen("m")

    def test_a_live_holder_keeps_the_seat(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m", 100.0)
        self.listen()
        self.st.check_seats(100000.0)       # however quiet
        self.assertEqual(self.holder(), "m")
        self.assertEqual([e for e in self.heard() if e.get("type") == "gov"], [])

    def test_other_territories_are_not_touched(self):
        pa, pb = self.live_pid(), self.live_pid()
        self.write_lock(pa.pid, "ma")
        self.write_lock(pb.pid, "mb", repo=self.repo_b)
        self.act("ma")
        self.act("mb", repo=self.repo_b)
        self.kill(pa)
        self.st.check_seats(200.0)
        self.assertIsNone(self.holder())
        self.assertEqual(self.holder(self.repo_b), "mb")

    def test_no_governor_nothing_happens(self):
        self.act("a")
        self.st.check_seats(200.0)
        self.assert_citizen("a")


class TestSeenBeforeRestart(RolesCase):
    def restart(self):
        self.st = self.make_state()

    def test_unknown_only_while_a_holder_lives(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m")
        terr = ac.territory_id(self.repo)
        self.restart()
        self.assertEqual(self.govs().get(terr), "unknown")
        self.kill(p)
        self.assertNotIn(terr, self.govs(), "no live main manager: nobody, not unknown")


# -- R2: a line with no repo stays where its session lives ------------------

class TestRepoLessLines(RolesCase):
    def test_a_known_sid_stays_in_its_territory(self):
        """E1: a session of repo B sends one line with repo ""."""
        self.act("x", 100.0, repo=self.repo_b)
        self.act("x", 101.0, repo="")
        self.assertNotIn("x", self.st.reducers[self.repo].sessions if self.repo in self.st.reducers else {})
        self.assertIn("x", self.st.reducers[self.repo_b].sessions)

    def test_a_subagent_line_teaches_the_territory_too(self):
        self.line("SubagentStart", "x", 100.0, repo=self.repo_b, aid="a1", at="worker")
        self.act("x", 101.0, repo="")
        self.assertIn("x", self.st.reducers[self.repo_b].sessions)
        self.assertNotIn("x", self.st.reducers[self.repo].sessions if self.repo in self.st.reducers else {})

    def test_an_unknown_sid_still_falls_back_to_the_start_territory(self):
        self.act("y", 100.0, repo="")
        self.assertIn("y", self.st.reducers[self.repo].sessions)

    def test_a_repo_less_line_never_takes_the_start_seat(self):
        """E1 exactly: the start territory's old governor is dead, a foreign session comes in."""
        old = self.live_pid()
        self.write_lock(old.pid, "old")
        self.act("old", 100.0)
        self.kill(old)
        self.act("foreign", 101.0, repo=self.repo_b)
        self.act("foreign", 102.0, repo="")
        self.assertNotEqual(self.holder(), "foreign")
        self.assertNotEqual(self.holder(self.repo_b), "foreign")


# -- gov_next: only the holder is asked ------------------------------------

class TestGovNext(RolesCase):
    def test_a_non_holder_is_told_not_main(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        out = self.st.gov_next("h", self.repo, "w1", 0.2)
        self.assertEqual(out, {"state": "not-main"})
        self.assertNotIn(self.repo, self.st.governors)

    def test_no_lock_nobody_is_main(self):
        self.assertEqual(self.st.gov_next("h", self.repo, "w1", 0.2), {"state": "not-main"})
        self.assertEqual(self.st.governors, {})

    def test_the_holder_is_registered(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        out = self.st.gov_next("m", self.repo, "w1", 0.1)
        self.assertEqual(out, {"state": "none"})
        self.assertEqual(self.st.governors[self.repo]["sid"], "m")

    def test_the_holder_by_pid(self):
        p = self.live_pid()
        self.write_lock(p.pid, old=True)
        self.assertEqual(self.st.gov_next("m", self.repo, "w1", 0.1, pid=str(p.pid)), {"state": "none"})
        self.assertEqual(self.st.governors[self.repo]["sid"], "m")

    def test_a_question_skips_a_helper(self):
        """A human-direct helper (roleless, not the holder) never answers as governor."""
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.st.gov_next("h", self.repo, "w1", 0.1)
        body, code = self.st.create_ask({"sid": "w", "aid": "a1", "at": "worker", "role": "worker",
                                         "cwd": self.base, "repo": self.repo, "tool": "AskUserQuestion",
                                         "input": {"questions": [{"question": "which?", "options": []}]}},
                                        0)
        self.assertEqual(code, 200)
        self.assertEqual(body["phase"], "owner")
        self.assertEqual(body["why"], "no-governor")



# -- the hook sends its session's pid -----------------------------------------

HOOK = os.path.join(ROOT, "bin", "agent-city-hook.sh")


class TestHookPid(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_roles_hook_")
        self.city = os.path.join(self.base, "city")
        os.mkdir(self.city)
        self.empty = os.path.join(self.base, "emptybin")
        os.mkdir(self.empty)
        with open(os.path.join(self.city, "on"), "w") as fh:
            fh.write("%d 4777\n" % os.getpid())

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def row(self, env):
        full = {"AGENT_CITY_DIR": self.city, "PATH": self.empty, "HOME": self.base}
        full.update(env)
        stdin = json.dumps({"session_id": "s1", "transcript_path": "/t.jsonl", "cwd": self.base,
                            "hook_event_name": "PostToolUse", "tool_name": "Read",
                            "tool_input": {"file_path": "/x"}}).encode("utf-8")
        subprocess.run([HOOK], input=stdin, env=full, capture_output=True, timeout=10)
        with open(os.path.join(self.city, "events.jsonl")) as fh:
            rows = [json.loads(l, object_pairs_hook=lambda kv: kv) for l in fh if l.strip()]
        os.remove(os.path.join(self.city, "events.jsonl"))
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_pid_is_the_last_key(self):
        row = self.row({"CLAUDE_PID": "4242"})
        self.assertEqual(row[-1], ("pid", "4242"))
        self.assertEqual([k for k, _ in row][-5:], ["ask", "wt", "file", "tp", "pid"])

    def test_no_or_bad_pid_is_empty(self):
        for env in ({}, {"CLAUDE_PID": ""}, {"CLAUDE_PID": "12a"}, {"CLAUDE_PID": "1 2"},
                    {"CLAUDE_PID": '1"}'}):
            with self.subTest(env=env):
                self.assertEqual(dict(self.row(env))["pid"], "")

    def test_the_relay_never_sends_it(self):
        import agent_city_relay as relay
        wire = relay.to_wire({"ev": "PostToolUse", "sid": "s1", "pid": "4242"}, {"dev": "d1"})
        self.assertNotIn("pid", json.dumps(wire))


# -- gov-watch: the holder is the governor, a helper hears its own messages --

import test_agent_city_interact as interact  # noqa: E402


class TestGovWatchRoles(interact.AskHookCase):
    def setUp(self):
        super().setUp()
        self.repo_id = os.path.realpath(self.work)      # not a git dir: _repo_id() gives the folder

    def lock(self, sid):
        with open(os.path.join(self.work, "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-09-30 10:00 %s -\n" % (os.getpid(), sid))

    def watch(self, sid, max_wait="20"):
        env = dict(os.environ, AGENT_CITY_DIR=self.dir)
        env.pop("AGENT_ROLE", None)
        env.pop("CLAUDE_PID", None)
        proc = subprocess.Popen([sys.executable, interact.SERVER, "gov-watch", "--max-wait-sec", max_wait],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env)
        proc.stdin.write(interact.stop_payload(self.work, sid))
        proc.stdin.close()
        self.hooks.append(proc)
        return proc

    def session_line(self, ev, sid):
        self.append(json.dumps({"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "", "nt": "",
                                "proj": "work", "role": "", "desc": "", "sub": "", "q": "",
                                "klen": "", "repo": self.repo_id, "ask": "", "wt": "", "file": "",
                                "tp": "", "pid": ""}) + "\n")

    def send(self, to, text):
        status, _, out = self.api("POST", "/api/chat/send", {"to": to, "text": text}, origin=self.origin)
        self.assertEqual(status, 200, out)
        return out

    def test_a_helper_is_never_asked_as_governor(self):
        self.lock("main-1")
        self.start()
        proc = self.watch("helper-1", max_wait="4")
        time.sleep(1.0)
        self.assertEqual(self.health()["governors"], 0, "a helper never shows up as a governor")
        self.assertEqual(self.view(self.ask(interact.q_body(repo=self.repo_id)))["phase"], "owner")
        code, out, err = self.finish(proc)
        self.assertEqual((code, out, err), (0, b"", b""))

    def test_a_helper_hears_its_own_message(self):
        self.lock("main-1")
        self.start()
        self.session_line("UserPromptSubmit", "helper-1")
        self.session_line("Stop", "helper-1")
        self.assertTrue(interact.wait_for(lambda: self.api("GET", "/api/chat?to=s:helper-1")[0] == 200,
                                          timeout=5), "the helper never showed up as a citizen")
        proc = self.watch("helper-1")
        self.send("s:helper-1", "hello helper")
        code, out, err = self.finish(proc)
        self.assertEqual((code, out), (2, b""))
        self.assertIn("hello helper", err.decode("utf-8"))

    def test_the_holder_hears_the_owner(self):
        self.lock("main-1")
        self.start()
        self.session_line("UserPromptSubmit", "main-1")
        self.session_line("Stop", "main-1")
        gov_page = "gov:" + ac.territory_id(self.repo_id)
        self.assertTrue(interact.wait_for(lambda: self.api("GET", "/api/chat?to=" + gov_page)[0] == 200,
                                          timeout=5), "the main manager never showed up as the governor")
        proc = self.watch("main-1")
        self.assertTrue(interact.wait_for(lambda: self.health()["governors"] == 1, timeout=5))
        self.send(gov_page, "today do A first")
        code, out, err = self.finish(proc)
        self.assertEqual((code, out), (2, b""))
        self.assertIn("today do A first", err.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
