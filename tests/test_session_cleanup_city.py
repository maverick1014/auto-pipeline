"""session-cleanup, the city side: the interior designer leaves nothing behind when it is done
(requirements/session-cleanup.md, rules 3, 4, 5, 7; the script side: tests/test_session_cleanup.py).
Written by the task manager first.

CONTRACT (bin/agent_city.py)

floor bye <repo> (cmd_floor): writes <floors>/<tid>.bye and prints "bye" as today. Then, only when
    AGENT_ROLE is "interior-designer": (a) the files of its session go: `agent-file.sh session-end
    $CLAUDE_CODE_SESSION_ID` (the plugin's own bin), run in the current folder, when the id is a valid
    one; (b) then its own pane closes: close_session($ORCA_TERMINAL_HANDLE) when that is a valid handle.
    The cleanup comes before the close (the close ends the session). Anybody else running floor bye:
    no cleanup, no close. A failure in (a) or (b) never changes the exit code 0.
A session that said bye (the .bye file, or leave_designer) never comes back: feed_line drops every
    later line of that session id (no citizen, no roster entry), so a new designer opens at once (no
    409 designer-here).
chat_next(sid, ...) of a session whose page ended answers {"state": "ended"} at once, so its
    chat-watch process ends (it gives up on any state that is not "none" or "message").
CityState.close_designer_panes(): closes (close_fn) every designer pane this city opened and still
    holds a handle for, once; cmd_serve calls it when the server stops.
chat.jsonl: when the city sees the SessionEnd of a session that has chat rows, it appends one end row
    {"sid": <sid>, "aid": "", "kind": "end", "at": <epoch seconds>}. load_chat(path, now=None) (now:
    epoch, default time.time()) drops every row of a sid whose LAST row is an end row older than
    CHAT_GONE_SEC (= HIST_GONE_SEC, 24 h) and writes the file without them; a newer end row stays
    (returned too, so the city knows when it ended). CityState drops them at load (also when no server
    ran in between) and in sweep_history(now) (every recount tick).
Fix order 9bbb819c:
    FO4: a page is ended only while the end row is that session's LAST row: a row after it (a session
        resumed with the same sid) un-ends it, also at load after a restart (chat_next is not "ended",
        chat_view can_send is True once the session is live).
    S1: every writer of chat.jsonl (the say hook, the server) goes through chat_append(path, row), which
        holds an exclusive flock on <path>.lock around its one O_APPEND write; every rewrite (load_chat's,
        the sweep's) holds the same lock from its read to its os.replace, so no live row is lost.
    S4: CHAT_IDLE_SEC = 7 days. load_chat(path, now=None, live=()) also drops every row of a sid whose last
        row is older than CHAT_IDLE_SEC and that is not in LIVE (no end row needed); CityState passes the
        sessions it brought back from the roster; sweep_history(now) drops them too, unless the session
        is live.
The designer command carries the city's home: city_home_for(floors_dir) -> None for the default
    floors folder (~/.claude/agent-city/floors) or None, else the folder that holds the floors folder;
    agent_command(..., city_home=X) puts `AGENT_CITY_HOME=X ` right before `AGENT_ROLE=`/`claude`
    (after `AGENT_CITY_DIR=`); add_designer passes city_home_for(its floors folder).
Kept on purpose: the floor design <floors>/<tid>.json and its history.
"""

import inspect
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_agent_city_data as tcd  # noqa: E402  (the module only: its tests stay in their own module)

ac = tcd.ac
ROOT = os.path.dirname(HERE)
CITY = os.path.join(ROOT, "bin", "agent_city.py")
DAY = 86400

STUB_ORCA = """#!/usr/bin/env bash
gone=$(ls "${STUB_GITDIR:-/nonexistent}" 2>/dev/null | grep -c "_d1")
{ printf 'CALL'; for a in "$@"; do printf '\\t%s'"" "$a"; done; printf '\\tmarkers=%s\\n' "$gone"; } >> "$STUB_LOG"
printf '{"ok":true,"result":{}}\\n'
"""


def line(ev, sid, repo, role="", pid=""):
    obj = tcd.line_office(ev, sid, repo, role=role)
    if pid:
        obj["pid"] = pid
    return obj


def sids_in(obj):
    """Every "sid" value anywhere in OBJ."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "sid" and isinstance(v, str):
                found.append(v)
            else:
                found.extend(sids_in(v))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(sids_in(v))
    return found


class CleanCase(tcd.OfficeCase):
    def setUp(self):
        super().setUp()
        self.tid = self.known(self.shop)
        self.stub = os.path.join(self.base, "stubbin")
        os.makedirs(self.stub)
        with open(os.path.join(self.stub, "orca"), "w") as fh:
            fh.write(STUB_ORCA)
        os.chmod(os.path.join(self.stub, "orca"), 0o755)
        self.stub_log = os.path.join(self.base, "orca.log")
        open(self.stub_log, "w").close()

    def run_floor(self, *args, env=None, cwd=None, flags=True):
        full = dict(os.environ, AGENT_CITY_HOME=self.base, AGENT_RUNTIME="orca",
                    PATH=self.stub + os.pathsep + os.environ.get("PATH", ""), STUB_LOG=self.stub_log)
        for key in ("AGENT_ROLE", "ORCA_TERMINAL_HANDLE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_PROJECT_DIR"):
            full.pop(key, None)
        full.update(env or {})
        cmd = [sys.executable, CITY, "floor"] + list(args)
        if flags:
            cmd += ["--world", self.world_file, "--floors-dir", self.floors_dir]
        return subprocess.run(cmd, capture_output=True, text=True, env=full, cwd=cwd or self.base, timeout=60)

    def closes(self):
        with open(self.stub_log) as fh:
            rows = [l.rstrip("\n").split("\t") for l in fh if l.startswith("CALL")]
        return [r[1:] for r in rows if r[1:3] == ["terminal", "close"]]

    def bye_file(self):
        return os.path.join(self.floors_dir, self.tid + ".bye")

    def designer_here(self, sid="d1"):
        self.assertEqual(self.state.add_designer(self.tid, self.now)[0], 200)
        self.feed(line("UserPromptSubmit", sid, self.shop, role="interior-designer", pid=str(os.getpid())))

    def live(self, sid):
        snap = self.snapshot()
        return [a for a in snap["agents"] if a["id"] == "s:" + sid and not a.get("done")]


DESIGNER = {"AGENT_ROLE": "interior-designer", "ORCA_TERMINAL_HANDLE": "term_d-1"}


class TestByeClosesItsOwnPane(CleanCase):
    def test_the_designer_closes_its_own_pane(self):
        # requirement example: the server restarts between the designer's start and its bye (no server
        # holds the handle): the pane still closes
        r = self.run_floor("bye", "shop", env=DESIGNER)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("bye", r.stdout)
        self.assertTrue(os.path.exists(self.bye_file()))
        self.assertEqual([c[:4] for c in self.closes()], [["terminal", "close", "--terminal", "term_d-1"]])

    def test_anybody_else_closes_nothing(self):
        r = self.run_floor("bye", "shop", env={"ORCA_TERMINAL_HANDLE": "term_owner-1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(self.bye_file()))
        self.assertEqual(self.closes(), [])

    def test_a_bad_handle_closes_nothing(self):
        for bad in ("", "term x", "term_a;rm -rf x", "$(id)"):
            with self.subTest(handle=bad):
                r = self.run_floor("bye", "shop", env=dict(DESIGNER, ORCA_TERMINAL_HANDLE=bad))
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.closes(), [])

    def test_a_failed_close_still_says_bye(self):
        with open(os.path.join(self.stub, "orca"), "w") as fh:
            fh.write("#!/usr/bin/env bash\necho 'orca: no such terminal' >&2\nexit 1\n")
        r = self.run_floor("bye", "shop", env=DESIGNER)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(self.bye_file()))


class TestByeCleansTheDesignerFiles(CleanCase):
    """A real git repo the city knows, set up for the pipeline (agent_todo.txt)."""

    def setUp(self):
        super().setUp()
        self.real = os.path.join(self.base, "real")
        os.makedirs(self.real)
        subprocess.run(["git", "init", "-q", self.real], check=True)
        for name in ("agent_todo.txt", "agent_completed.txt", "agent_ideas.txt", "agent_worktree.txt"):
            open(os.path.join(self.real, name), "w").close()
        self.gitdir = os.path.realpath(os.path.join(self.real, ".git"))
        self.real_tid = self.known(self.gitdir, sid="s-real")
        for name in ("agent_started_d1", "agent_rules_d1", "agent_stale_d1", "agent_point_d1_watch",
                     "agent_quiz_other"):
            open(os.path.join(self.gitdir, name), "w").close()

    def test_bye_removes_them_before_the_pane_closes(self):
        r = self.run_floor("bye", ".", cwd=self.real,
                           env=dict(DESIGNER, CLAUDE_CODE_SESSION_ID="d1", STUB_GITDIR=self.gitdir))
        self.assertEqual(r.returncode, 0, r.stderr)
        left = sorted(n for n in os.listdir(self.gitdir) if n.startswith("agent_"))
        self.assertEqual(left, ["agent_quiz_other"])
        closes = self.closes()
        self.assertEqual(len(closes), 1, closes)
        self.assertEqual(closes[0][-1], "markers=0", "the files were gone before the close")
        self.assertTrue(os.path.exists(os.path.join(self.floors_dir, self.real_tid + ".bye")))

    def test_the_floor_design_is_kept(self):
        p = subprocess.run([sys.executable, CITY, "floor", "set", ".", "-", "--world", self.world_file,
                            "--floors-dir", self.floors_dir], input=json.dumps(tcd.GOOD), capture_output=True,
                           text=True, cwd=self.real, env=dict(os.environ, AGENT_CITY_HOME=self.base), timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        r = self.run_floor("bye", ".", cwd=self.real,
                           env=dict(DESIGNER, CLAUDE_CODE_SESSION_ID="d1", STUB_GITDIR=self.gitdir))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.floors_dir, self.real_tid + ".json")))


class TestASessionThatSaidByeNeverComesBack(CleanCase):
    def setUp(self):
        super().setUp()
        self.roster = os.path.join(self.base, "roster.json")
        self.state = self.make(roster_path=self.roster)
        self.tid = self.known(self.shop)

    def bye(self):
        os.makedirs(self.floors_dir, exist_ok=True)
        open(self.bye_file(), "w").close()
        self.state.scan_floors()

    def test_a_late_hook_line_brings_nobody_back(self):
        # requirement example: after bye, a late hook line of that session id: no citizen comes back;
        # a new designer starts (no 409)
        self.designer_here()
        self.assertTrue(self.live("d1"))
        self.bye()
        self.assertEqual(self.closed, ["term_abc-1"])
        self.assertEqual(self.live("d1"), [])
        for ev in ("Stop", "PostToolUse", "UserPromptSubmit", "Notification"):
            self.feed(line(ev, "d1", self.shop, role="interior-designer", pid=str(os.getpid())))
        self.assertEqual(self.live("d1"), [], "no citizen comes back")
        code, body = self.state.add_designer(self.tid, self.now)
        self.assertEqual((code, body.get("state")), (200, "opening"), body)

    def test_no_roster_entry_is_left(self):
        self.designer_here()
        self.bye()
        self.feed(line("Stop", "d1", self.shop, role="interior-designer", pid=str(os.getpid())))
        if os.path.exists(self.roster):
            with open(self.roster, encoding="utf-8") as fh:
                self.assertNotIn("d1", sids_in(json.load(fh)))

    def test_sent_away_by_the_owner_is_the_same(self):
        self.designer_here()
        self.assertEqual(self.state.leave_designer(self.tid), (200, {}))
        self.feed(line("Stop", "d1", self.shop, role="interior-designer", pid=str(os.getpid())))
        self.assertEqual(self.live("d1"), [])
        self.assertEqual(self.state.add_designer(self.tid, self.now)[0], 200)

    def test_another_session_is_not_touched(self):
        self.designer_here()
        self.feed(line("UserPromptSubmit", "h1", self.shop, pid=str(os.getpid())))
        self.bye()
        self.feed(line("Stop", "h1", self.shop, pid=str(os.getpid())))
        self.assertTrue(self.live("h1"))

    def test_its_chat_watch_is_told_to_end(self):
        # requirement example: no chat-watch process after bye
        self.designer_here()
        self.bye()
        t0 = time.monotonic()
        self.assertEqual(self.state.chat_next("d1", "w-1", 5.0), {"state": "ended"})
        self.assertLess(time.monotonic() - t0, 1.0, "at once, not after the poll window")

    def test_a_live_session_still_waits(self):
        self.feed(line("UserPromptSubmit", "h1", self.shop), line("Stop", "h1", self.shop))
        self.assertEqual(self.state.chat_next("h1", "w-1", 0.1), {"state": "none"})


class TestServerStopClosesItsDesignerPanes(CleanCase):
    def test_every_held_pane_closes_once(self):
        blog_tid = self.known(self.blog)
        self.assertEqual(self.state.add_designer(self.tid, self.now)[0], 200)
        self.answer = (True, "term_blog-2")
        self.assertEqual(self.state.add_designer(blog_tid, self.now)[0], 200)
        self.state.close_designer_panes()
        self.assertEqual(sorted(self.closed), ["term_abc-1", "term_blog-2"])
        self.state.close_designer_panes()
        self.assertEqual(len(self.closed), 2, "once")

    def test_a_pane_that_left_is_not_closed_again(self):
        self.designer_here()
        self.assertEqual(self.state.leave_designer(self.tid), (200, {}))
        self.state.close_designer_panes()
        self.assertEqual(self.closed, ["term_abc-1"])

    def test_the_server_calls_it_when_it_stops(self):
        self.assertIn("close_designer_panes()", inspect.getsource(ac.cmd_serve))


class TestTheDesignerCarriesTheCityHome(CleanCase):
    def test_city_home_for(self):
        default = os.path.expanduser("~/.claude/agent-city/floors")
        self.assertIsNone(ac.city_home_for(default))
        self.assertIsNone(ac.city_home_for(default + "/"))
        self.assertIsNone(ac.city_home_for(None))
        self.assertEqual(ac.city_home_for(self.floors_dir), self.base)

    def test_agent_command_puts_it_before_the_role(self):
        folder = os.path.dirname(self.shop)
        words = shlex.split(ac.agent_command("shop Designer", folder, "/tmp/city x", "interior_designer", "hi",
                                             "interior-designer", city_home="/tmp/home y"))
        self.assertEqual(words[:4], ["AGENT_CITY_DIR=/tmp/city x", "AGENT_CITY_HOME=/tmp/home y",
                                     "AGENT_ROLE=interior-designer", "claude"])
        words = shlex.split(ac.agent_command("shop Designer", folder, None, "interior_designer", "hi",
                                             "interior-designer"))
        self.assertEqual(words[:2], ["AGENT_ROLE=interior-designer", "claude"])

    def test_a_non_default_floors_folder_sees_the_bye(self):
        # requirement example: a city with a non-default floors folder: the designer's bye is seen and
        # acted on
        self.assertEqual(self.state.add_designer(self.tid, self.now)[0], 200)
        command = self.calls[0][2]
        homes = [w.split("=", 1)[1] for w in shlex.split(command) if w.startswith("AGENT_CITY_HOME=")]
        self.assertEqual(homes, [self.base], command)
        self.feed(line("UserPromptSubmit", "d1", self.shop, role="interior-designer"))
        r = self.run_floor("bye", "shop", env={"AGENT_CITY_HOME": homes[0]}, flags=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.state.scan_floors()
        self.assertEqual(self.closed, ["term_abc-1"])
        self.assertEqual(self.live("d1"), [])

    def test_the_plain_line_carries_it_too(self):
        self.kind = "plain"
        code, body = self.state.add_designer(self.tid, self.now)
        self.assertEqual((code, body["state"]), (200, "plain"))
        self.assertIn("AGENT_CITY_HOME=" + shlex.quote(self.base), body["command"])


def chat_row(sid, kind, at, text="hi"):
    row = {"sid": sid, "aid": "", "kind": kind, "at": at}
    if kind != "end":
        row["text"] = text
    return row


class ChatCase(tcd.OfficeCase):
    def setUp(self):
        super().setUp()
        self.chat = os.path.join(self.base, "chat.jsonl")

    def write_chat(self, rows):
        with open(self.chat, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

    def chat_rows(self):
        if not os.path.exists(self.chat):
            return []
        with open(self.chat, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def chat_sids(self):
        return sorted(set(r["sid"] for r in self.chat_rows()))

    def gone_page(self, st, sid):
        code, body = st.chat_view("s:" + sid)
        return code == 404 or body.get("entries") == []


class TestChatOfAnEndedSession(ChatCase):
    def test_load_drops_a_session_gone_a_day(self):
        # requirement example: chat.jsonl holds lines of a session that ended 25 h ago and of one that
        # ended 1 h ago: after a load, only the second remains
        now = 2000000000.0
        self.write_chat([chat_row("old", "prompt", now - 26 * 3600), chat_row("old", "reply", now - 26 * 3600),
                         chat_row("new", "prompt", now - 2 * 3600), chat_row("old", "end", now - 25 * 3600),
                         chat_row("new", "end", now - 3600), chat_row("live", "prompt", now - 40 * 3600)])
        rows = ac.load_chat(self.chat, now=now)
        self.assertEqual(sorted(set(r["sid"] for r in rows)), ["live", "new"])
        self.assertEqual(self.chat_sids(), ["live", "new"], "the file is written without them")
        self.assertIn({"sid": "new", "aid": "", "kind": "end", "at": now - 3600},
                      [{k: r[k] for k in ("sid", "aid", "kind", "at")} for r in rows],
                      "a fresh end row is kept, so the city knows when it ended")

    def test_a_session_that_came_back_stays(self):
        now = 2000000000.0
        self.write_chat([chat_row("back", "prompt", now - 30 * 3600), chat_row("back", "end", now - 26 * 3600),
                         chat_row("back", "prompt", now - 20 * 3600)])
        self.assertEqual(len(ac.load_chat(self.chat, now=now)), 3)

    def test_the_gone_time_is_the_history_one(self):
        self.assertEqual(ac.CHAT_GONE_SEC, ac.HIST_GONE_SEC)
        self.assertEqual(ac.CHAT_GONE_SEC, DAY)

    def test_the_city_drops_them_at_load(self):
        # also when no server ran in between: the end row was written by the last run
        now = time.time()
        self.write_chat([chat_row("old", "prompt", now - 30 * 3600), chat_row("old", "end", now - 25 * 3600),
                         chat_row("new", "prompt", now - 2 * 3600), chat_row("new", "end", now - 3600)])
        st = self.make(chat_path=self.chat)
        self.assertEqual(self.chat_sids(), ["new"])
        self.assertTrue(self.gone_page(st, "old"))

    def test_the_city_writes_the_end_row(self):
        now = time.time()
        self.write_chat([chat_row("s1", "prompt", now - 60)])
        self.state = self.make(chat_path=self.chat)
        self.feed(line("UserPromptSubmit", "s1", self.shop), line("UserPromptSubmit", "s2", self.shop))
        before = time.time()
        self.feed(line("SessionEnd", "s1", self.shop), line("SessionEnd", "s2", self.shop))
        after = time.time()
        ends = [r for r in self.chat_rows() if r.get("kind") == "end"]
        self.assertEqual([r["sid"] for r in ends], ["s1"], "a session with no chat rows writes none")
        self.assertEqual((ends[0]["aid"], set(ends[0])), ("", {"sid", "aid", "kind", "at"}))
        self.assertTrue(before - 1 <= ends[0]["at"] <= after + 1, ends[0])

    def test_the_running_city_sweeps_them_a_day_later(self):
        now = time.time()
        self.write_chat([chat_row("s1", "prompt", now - 60), chat_row("s3", "prompt", now - 60)])
        self.state = self.make(chat_path=self.chat)
        self.feed(line("UserPromptSubmit", "s1", self.shop), line("SessionEnd", "s1", self.shop))
        self.feed(line("UserPromptSubmit", "s3", self.shop))
        self.state.sweep_history(time.time() + 3600)
        self.assertEqual(self.chat_sids(), ["s1", "s3"], "an hour later it is still there")
        self.state.sweep_history(time.time() + DAY + 60)
        self.assertEqual(self.chat_sids(), ["s3"], "a live session's chat stays")
        self.assertTrue(self.gone_page(self.state, "s1"))


class TestAResumedSessionIsNotEnded(ChatCase):
    """fix order 9bbb819c FO4."""

    def test_a_row_after_the_end_row_un_ends_it_at_load(self):
        now = time.time()
        self.write_chat([chat_row("s1", "prompt", now - 3 * 3600), chat_row("s1", "end", now - 2 * 3600),
                         chat_row("s1", "prompt", now - 3600)])
        self.state = self.make(chat_path=self.chat)
        self.feed(line("UserPromptSubmit", "s1", self.shop), line("Stop", "s1", self.shop))
        self.assertEqual(self.state.chat_next("s1", "w-1", 0.1), {"state": "none"})
        code, body = self.state.chat_view("s:s1")
        self.assertEqual((code, body.get("can_send")), (200, True), body)

    def test_an_end_row_that_is_last_still_ends_it(self):
        now = time.time()
        self.write_chat([chat_row("s2", "prompt", now - 3 * 3600), chat_row("s2", "end", now - 2 * 3600)])
        self.state = self.make(chat_path=self.chat)
        self.assertEqual(self.state.chat_next("s2", "w-1", 5.0), {"state": "ended"})


class TestNoLiveRowIsLost(ChatCase):
    """fix order 9bbb819c S1: the rewrite of chat.jsonl and its writers share one lock."""

    def hold(self):
        import fcntl
        fh = open(self.chat + ".lock", "a+")
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        self.addCleanup(fh.close)
        return fh

    def release(self, fh):
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def in_thread(self, fn):
        import threading
        t = threading.Thread(target=fn, daemon=True)
        t.start()
        return t

    def test_the_writer_waits_for_the_lock(self):
        self.write_chat([])
        fh = self.hold()
        t = self.in_thread(lambda: ac.chat_append(self.chat, chat_row("w1", "prompt", time.time())))
        time.sleep(0.3)
        self.assertEqual(self.chat_sids(), [], "no write while the lock is held")
        self.release(fh)
        t.join(5)
        self.assertEqual(self.chat_sids(), ["w1"])

    def test_the_rewrite_at_load_waits_for_the_lock(self):
        now = time.time()
        self.write_chat([chat_row("old", "prompt", now - 30 * 3600), chat_row("old", "end", now - 25 * 3600)])
        fh = self.hold()
        t = self.in_thread(lambda: ac.load_chat(self.chat, now=now))
        time.sleep(0.3)
        self.assertEqual(self.chat_sids(), ["old"], "the rewrite waits")
        self.release(fh)
        t.join(5)
        self.assertEqual(self.chat_sids(), [])

    def test_the_sweep_waits_for_the_lock(self):
        now = time.time()
        self.write_chat([chat_row("s1", "prompt", now - 60)])
        self.state = self.make(chat_path=self.chat)
        self.feed(line("UserPromptSubmit", "s1", self.shop), line("SessionEnd", "s1", self.shop))
        fh = self.hold()
        t = self.in_thread(lambda: self.state.sweep_history(time.time() + DAY + 60))
        time.sleep(0.3)
        self.assertIn("s1", self.chat_sids(), "the sweep waits")
        self.release(fh)
        t.join(5)
        self.assertNotIn("s1", self.chat_sids())

    def test_the_say_hook_uses_the_one_writer(self):
        self.assertIn("chat_append(", inspect.getsource(ac._cmd_say_impl))
        self.assertIn("chat_append(", inspect.getsource(ac.CityState._append_chat_path_locked))

    def test_rows_written_during_many_sweeps_all_stay(self):
        # a second process appends while the city rewrites the file again and again
        self.write_chat([])
        self.state = self.make(chat_path=self.chat)
        n = 300
        writer = subprocess.Popen(
            [sys.executable, "-c",
             "import sys, time; sys.path.insert(0, %r); import agent_city as ac\n"
             "for i in range(%d):\n"
             "    ac.chat_append(%r, {'sid': 'live', 'aid': '', 'kind': 'prompt', 'text': 'r%%d' %% i, 'at': time.time()})\n"
             % (os.path.join(ROOT, "bin"), n, self.chat)])
        k = 0
        while writer.poll() is None and k < 200:
            sid = "gone%d" % k
            ac.chat_append(self.chat, chat_row(sid, "prompt", time.time() - 3 * DAY))
            self.state.feed_chat(chat_row(sid, "prompt", time.time() - 3 * DAY))
            self.state.feed_chat(chat_row(sid, "end", time.time() - 2 * DAY))
            self.state.sweep_history(time.time())
            k += 1
        writer.wait(60)
        self.assertEqual(writer.returncode, 0)
        self.assertGreater(k, 0, "at least one rewrite ran while the writer wrote")
        texts = [r.get("text") for r in self.chat_rows() if r["sid"] == "live"]
        self.assertEqual(len(texts), n, "every live row stays")


class TestAnIdleSessionGoesAfterAWeek(ChatCase):
    """fix order 9bbb819c S4: a session with no end row whose last row is older than 7 days, and that
    is not live, loses its chat too."""

    def test_the_idle_time_is_a_week(self):
        self.assertEqual(ac.CHAT_IDLE_SEC, 7 * DAY)

    def test_load_chat(self):
        now = 2000000000.0
        self.write_chat([chat_row("idle8", "prompt", now - 8 * DAY), chat_row("idle6", "prompt", now - 6 * DAY),
                         chat_row("live8", "prompt", now - 8 * DAY)])
        rows = ac.load_chat(self.chat, now=now, live={"live8"})
        self.assertEqual(sorted(set(r["sid"] for r in rows)), ["idle6", "live8"])
        self.assertEqual(self.chat_sids(), ["idle6", "live8"])

    def test_the_city_keeps_a_live_session_at_load(self):
        roster = os.path.join(self.base, "roster.json")
        first = self.make(roster_path=roster)
        first.feed_line(line("UserPromptSubmit", "live8", self.shop, pid=str(os.getpid())), self.now)
        self.assertTrue(os.path.exists(roster), "the live session is in the roster")
        now = time.time()
        self.write_chat([chat_row("idle8", "prompt", now - 8 * DAY), chat_row("live8", "prompt", now - 8 * DAY),
                         chat_row("idle6", "prompt", now - 6 * DAY)])
        self.make(roster_path=roster, chat_path=self.chat)
        self.assertEqual(self.chat_sids(), ["idle6", "live8"])

    def test_the_sweep_drops_an_idle_session_not_a_live_one(self):
        now = time.time()
        self.write_chat([chat_row("idle", "prompt", now - 60), chat_row("live", "prompt", now - 60)])
        self.state = self.make(chat_path=self.chat)
        self.feed(line("UserPromptSubmit", "live", self.shop))
        self.state.sweep_history(time.time() + 6 * DAY)
        self.assertEqual(self.chat_sids(), ["idle", "live"])
        self.state.sweep_history(time.time() + 8 * DAY)
        self.assertEqual(self.chat_sids(), ["live"])
        self.assertTrue(self.gone_page(self.state, "idle"))


if __name__ == "__main__":
    unittest.main()
