"""Failing tests for city-chat (requirements/city.md, "Talking"; owner,
2026-09-27): a person's window shows its session's conversation and a box
to talk to it; an idle session wakes with the owner's message; chat text
never leaves the computer.

CONTRACT, server (bin/agent_city.py, Python standard library only)

  CHAT_TEXT_MAX = 4000, CHAT_KEEP = 200.

  python3 agent_city.py say   (hook: UserPromptSubmit, Stop, SubagentStop)
    Reads the hook's JSON on stdin. Appends ONE line to <city dir>/chat.jsonl
    (city dir = AGENT_CITY_DIR, default ~/.cache/agent-city):
      {"sid": session_id, "aid": agent_id or "", "kind", "text", "at": time.time()}
      UserPromptSubmit -> kind "prompt", text = prompt
      Stop             -> kind "reply", text = last_assistant_message, aid ""
      SubagentStop     -> kind "reply", text = last_assistant_message, aid = agent_id
    Text longer than CHAT_TEXT_MAX -> its first CHAT_TEXT_MAX characters + "…".
    Writes nothing when: the text is missing or blank, the input is not a
      JSON object, <city dir>/on does not exist (city off), or
      CLAUDE_CODE_REMOTE is set (a cloud session has no page).
    Never reads transcript_path (its format is internal to Claude Code).
    chat.jsonl is private: created with mode 0600 (it holds conversation
      text), and each line goes in with ONE os.write on an O_APPEND file
      descriptor, so two sessions ending at once never interleave.
    Prints NOTHING on stdout (a UserPromptSubmit hook's stdout would go into
      the conversation). Exit 0 always, whatever happens.

  python3 agent_city.py chat-watch [--max-wait-sec N]  (Stop, async,
    asyncRewake; sessions with AGENT_ROLE -- the governor keeps gov-watch)
    Reads the hook JSON (session_id) on stdin; finds the server through
    <city dir>/on and its token (as gov-watch does); asks
    GET /api/chat/next?sid=&watcher=<random>&timeout=<= 5 until one answers
    {"state": "message", "text"}: then writes a wake note to stderr that
    carries the owner's text word for word and says it was typed in the
    city page, and exits 2 (asyncRewake wakes the session with it).
    "replaced", no server, any error, or N seconds (default 43200) without a
    message -> exit 0, nothing on stderr.
  gov-watch: GET /api/gov/next may also answer {"state": "message", "id",
    "text"} for that governor's sid (the owner's messages before questions);
    gov-watch then wakes the same way (stderr, exit 2).

  CityState(..., chat_path=None)
    Loads chat_path with load_chat() at start; delivered owner messages are
    appended to it as {"sid", "aid": "", "kind": "owner", "text", "at"}.
    feed_chat(obj): one chat.jsonl line; kinds prompt, reply, owner; bad
      lines ignored. Kept per (sid, aid), the last CHAT_KEEP. Each new entry
      goes to every page as {"type": "chat", "to": <page id>, "entry"}.
    Page ids: a subagent = its aid (as its citizen id); the governor of a
      territory = "gov:" + territory id; any other session = "s:" + sid.
    entry = {"id" (int, unique in this run), "kind", "text", "at"}, plus
      "state" for kind owner: "queued" | "delivered" | "undelivered".
    Idle: a session is idle until a line of it (aid "") with ev
      UserPromptSubmit, PreToolUse, PostToolUse or PermissionRequest makes
      it busy; its Stop makes it idle again; its SessionEnd ends it.
    chat_view(to) -> (code, body). 200 {"to", "can_send", "busy", "entries"}
      for a known session (can_send true unless it ended) or subagent
      (can_send false); 404 for anything unknown.
    chat_send(to, text, now) -> (code, body). 400 when text is not a
      non-empty string or is longer than CHAT_TEXT_MAX, or `to` is a
      subagent ({"error": "subagent"}) or another member's person ("r:" or
      "rg:"). 404 unknown or ended session. 200 {"id", "state": "queued"},
      and the queued entry goes to every page.
    chat_next(sid, watcher, timeout) -> dict. The gov_next watcher rule (a
      newer watcher for the same sid retires the older: {"state":
      "replaced"}). Only while that session is idle, the oldest queued
      owner message: {"state": "message", "id", "text"}; it becomes
      delivered (page event with the same entry id, state "delivered"),
      is logged in decisions_path as {"by": "owner", "verb": "message",
      "sid", "text", "at"}, and appended to chat_path. Else waits up to
      timeout (<= 30 s) and answers {"state": "none"}.
    A session's SessionEnd turns its queued messages "undelivered" (page
      event) and later sends answer 404.
  load_chat(path) -> the valid lines, the last CHAT_KEEP per (sid, aid), in
    file order; rewrites the file (tmp + rename) when it dropped any.
    Missing file -> [].

  Idle stop: every chat_next and gov_next call restarts the server's idle
    clock, so the server never stops while a session waits to be talked to
    (it still stops with no page and no waiting session).

  HTTP (same Host / Origin / token gate as the rest):
    GET  /api/chat?to=<id>          token -> chat_view
    POST /api/chat/send {to, text}  token and an Origin header (like
                                    /api/decide) -> chat_send
    GET  /api/chat/next?sid=&watcher=&timeout=   token -> chat_next
    serve: CityState gets chat_path=<dir>/chat.jsonl and a new line
      appended to that file reaches feed_chat (tailed like events.jsonl).

  Chat never leaves the computer: bin/agent_city_relay.py never mentions
    chat; the relay keeps its line whitelist (no "text", "prompt").

CONTRACT, hooks (hooks/hooks.json)
  UserPromptSubmit, Stop and SubagentStop each run `agent_city.py" say`
    behind the same `[ -f ".../on" ]` guard, ending `exit 0`, timeout <= 10,
    not async. Stop also runs `agent_city.py" chat-watch` only when
    AGENT_ROLE is set (`[ -n "${AGENT_ROLE:-}" ]`), "async": true,
    "asyncRewake": true. The per-tool hook (agent-city-hook.sh) never runs say.

CONTRACT, page (bin/agent-city.html) -- inside the window of city-focus
  const CHAT_STATE_ZH = {queued: '已发送', delivered: '已送达',
    undelivered: '没送到'}.
  chatHtml(entries, name, busy) -> one <li class="msg" data-kind="<kind>"
    data-id="<id>"> per entry, in order: who (prompt -> 你（终端）, owner ->
    你（页面） with CHAT_STATE_ZH of its state, reply -> name), then the
    text; everything through esc(). No entries -> <li class="msg-empty">
    还没有对话</li>. busy and a queued owner entry -> a last <li
    class="msg-wait">等它做完这一步</li>. Uses only esc and CHAT_STATE_ZH.
  chatTarget(sel) -> the chat id of a selection: {t: 'gov', terr} ->
    'gov:' + terr; {t: 'c', id} -> id; anything else (a remote person
    'rg', a building, a site, null) -> null.
  curChatTo() -> the chat id of the open window: chatTarget of `selected`,
    using the citizen's own id as the server sent it ("s:<sid>" for a
    session, the raw agent id for a subagent; never a second "s:"); a
    remote person -> null. (E2E 2026-09-27: the page asked for s:s:tm1.)
  renderDetail shows, for a chat target, <ol class="chat" id="chat"> with
    chatHtml; for a session also <form class="say" id="say"> with
    <textarea id="say-text" maxlength="4000"> and a submit button 发送; for
    a subagent no form but a line naming 组长 (talk to its lead instead).
  loadChat(to): live -> fetch('/api/chat?to=' + encodeURIComponent(to)) with
    the 'X-City-Token': TOKEN header, into the Map `chats`; a failure is
    shown (never swallowed). Demo -> no fetch.
  sendChat(to, text): live -> fetch('/api/chat/send', POST, JSON {to, text},
    'X-City-Token': TOKEN); a failure is shown in the window. Demo -> no
    fetch.
  sendChat resolves to true when the server took the message, false when
    it did not (the failure is shown in the window).
  A 'submit' listener (preventDefault) sends #say-text with sendChat and
    clears the box only when sendChat resolved true: a failed send never
    loses what the owner typed.
  case 'chat' (the page event): updates `chats`; an owner entry that turns
    delivered writes a page log line starting 你 →.

Run: python3 -m unittest tests.test_agent_city_chat </dev/null
"""

import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
SERVER = os.path.join(BIN, "agent_city.py")
HOOKS = os.path.join(ROOT, "hooks", "hooks.json")
RELAY = os.path.join(BIN, "agent_city_relay.py")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from test_agent_city_page import (case_block, const_object, function_source, inline_script,  # noqa: E402
                                  js_value, page_fns, run_node, zh_resolved)
from test_agent_city_server import ServerCase, wait_for  # noqa: E402

REPO = "/r/shop/.git"


def line(ev, sid, aid="", role="", tool="Read", at="", repo=REPO):
    return {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": "shop", "role": role,
            "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}


# ---------------------------------------------------------------------------
# say: the hook that writes chat.jsonl
# ---------------------------------------------------------------------------

class SayCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_say_")
        self.dir = os.path.join(self.base, "city")
        os.makedirs(self.dir)
        with open(os.path.join(self.dir, "on"), "w") as fh:
            fh.write("1 1\n")
        self.chat = os.path.join(self.dir, "chat.jsonl")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def say(self, payload, **env_extra):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE"}
        env.update(AGENT_CITY_DIR=self.dir, HOME=self.base)
        env.update(env_extra)
        data = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
        if isinstance(data, str):
            data = data.encode("utf-8")
        return subprocess.run([sys.executable, SERVER, "say"], input=data, capture_output=True, env=env,
                              timeout=20)

    def lines(self):
        try:
            with open(self.chat, encoding="utf-8") as fh:
                return [json.loads(x) for x in fh if x.strip()]
        except FileNotFoundError:
            return []


class TestSay(SayCase):
    def test_prompt_reply_and_subagent_reply(self):
        r1 = self.say({"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "修一下 <b>登录</b>",
                       "transcript_path": "/nope"})
        r2 = self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "修好了"})
        r3 = self.say({"hook_event_name": "SubagentStop", "session_id": "s1", "agent_id": "a9",
                       "last_assistant_message": "slice done"})
        for r in (r1, r2, r3):
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, b"", "say must print nothing on stdout")
        got = [(x["sid"], x["aid"], x["kind"], x["text"]) for x in self.lines()]
        self.assertEqual(got, [("s1", "", "prompt", "修一下 <b>登录</b>"), ("s1", "", "reply", "修好了"),
                               ("s1", "a9", "reply", "slice done")])
        for x in self.lines():
            self.assertIsInstance(x["at"], (int, float))
            self.assertGreater(x["at"], time.time() - 60)

    def test_long_text_is_cut(self):
        self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "x" * 10000})
        text = self.lines()[0]["text"]
        self.assertEqual(text, "x" * ac.CHAT_TEXT_MAX + "…")

    def test_nothing_written(self):
        cases = {
            "blank": {"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "   "},
            "missing": {"hook_event_name": "Stop", "session_id": "s1"},
            "other event": {"hook_event_name": "PreToolUse", "session_id": "s1", "prompt": "x"},
            "no sid": {"hook_event_name": "Stop", "last_assistant_message": "x"},
        }
        for name, payload in cases.items():
            with self.subTest(case=name):
                r = self.say(payload)
                self.assertEqual((r.returncode, r.stdout), (0, b""))
        for raw in (b"", b"not json", b"[1, 2]"):
            with self.subTest(raw=raw):
                r = self.say(raw)
                self.assertEqual((r.returncode, r.stdout), (0, b""))
        self.assertEqual(self.lines(), [])

    def test_city_off_or_cloud_writes_nothing(self):
        r = self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "x"},
                     CLAUDE_CODE_REMOTE="true")
        self.assertEqual((r.returncode, r.stdout), (0, b""))
        os.remove(os.path.join(self.dir, "on"))
        r = self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "x"})
        self.assertEqual((r.returncode, r.stdout), (0, b""))
        self.assertEqual(self.lines(), [])

    def test_the_file_is_private_and_appended_in_one_write(self):
        self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "ok"})
        self.assertEqual(os.stat(self.chat).st_mode & 0o777, 0o600)
        import inspect
        src = inspect.getsource(ac._cmd_say_impl)
        self.assertIn("os.O_APPEND", src)
        self.assertIn("os.write(", src)

    def test_never_reads_the_transcript(self):
        tpath = os.path.join(self.base, "t.jsonl")
        with open(tpath, "w") as fh:
            fh.write('{"message": "SECRET-TRANSCRIPT-7731"}\n')
        self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "ok",
                  "transcript_path": tpath})
        with open(self.chat, encoding="utf-8") as fh:
            self.assertNotIn("SECRET-TRANSCRIPT-7731", fh.read())
        import inspect
        self.assertNotIn("transcript_path", inspect.getsource(ac.cmd_say))


# ---------------------------------------------------------------------------
# hooks.json
# ---------------------------------------------------------------------------

def hook_entries(event):
    with open(HOOKS) as fh:
        data = json.load(fh)["hooks"]
    return [h for group in data.get(event, []) for h in group.get("hooks", [])]


class TestHookWiring(unittest.TestCase):
    def test_say_runs_on_prompt_and_turn_end(self):
        for event in ("UserPromptSubmit", "Stop", "SubagentStop"):
            with self.subTest(event=event):
                says = [h for h in hook_entries(event) if 'agent_city.py" say' in h.get("command", "")]
                self.assertEqual(len(says), 1)
                h = says[0]
                self.assertIn('/on" ]', h["command"])
                self.assertTrue(h["command"].rstrip().endswith("exit 0"))
                self.assertLessEqual(h.get("timeout", 60), 10)
                self.assertFalse(h.get("async"))

    def test_chat_watch_for_sessions_with_a_role(self):
        watches = [h for h in hook_entries("Stop") if 'agent_city.py" chat-watch' in h.get("command", "")]
        self.assertEqual(len(watches), 1)
        h = watches[0]
        self.assertIn('[ -n "${AGENT_ROLE:-}" ]', h["command"])
        self.assertIs(h.get("async"), True)
        self.assertIs(h.get("asyncRewake"), True)

    def test_per_tool_hook_never_says(self):
        for event in ("PreToolUse", "PostToolUse"):
            for h in hook_entries(event):
                self.assertNotIn(" say", h.get("command", ""))


# ---------------------------------------------------------------------------
# CityState: the conversation, sending, delivery
# ---------------------------------------------------------------------------

class ChatCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_chat_")
        self.chat_path = os.path.join(self.base, "chat.jsonl")
        self.decisions = os.path.join(self.base, "decisions.jsonl")
        self.state = self.make()
        self.gov_id = "gov:" + ac.territory_id(REPO)

    def make(self):
        return ac.CityState(decisions_path=self.decisions, world_path=None, chat_path=self.chat_path,
                            count_fn=lambda i: 0, balance_fn=lambda i, r: {"kinds": {}, "files": {}, "bad": []})

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def feed(self, *lines):
        for obj in lines:
            self.state.feed_line(obj, time.monotonic())

    def team(self):
        """A governor g1 (idle), a task manager tm1 (busy), its worker a9."""
        self.feed(line("UserPromptSubmit", "g1"), line("Stop", "g1"),
                  line("UserPromptSubmit", "tm1", role="task-manager"),
                  line("PostToolUse", "tm1", aid="a9", at="worker", role="task-manager"))

    def client(self):
        c = self.state.add_client()
        while not c.queue.empty():
            c.queue.get_nowait()
        return c

    @staticmethod
    def events(client, kind="chat"):
        out = []
        while not client.queue.empty():
            raw = client.queue.get_nowait().decode("utf-8")
            if "data:" not in raw:
                continue
            msg = json.loads(raw.split("data:", 1)[1])
            if msg.get("type") == kind:
                out.append(msg)
        return out


class TestConversation(ChatCase):
    def test_lines_reach_the_right_window(self):
        self.team()
        c = self.client()
        self.state.feed_chat({"sid": "g1", "aid": "", "kind": "prompt", "text": "hi", "at": 1.0})
        self.state.feed_chat({"sid": "tm1", "aid": "", "kind": "reply", "text": "ok", "at": 2.0})
        self.state.feed_chat({"sid": "tm1", "aid": "a9", "kind": "reply", "text": "slice", "at": 3.0})
        events = self.events(c)
        got = [(e["to"], e["entry"]["kind"], e["entry"]["text"]) for e in events]
        self.assertEqual(got, [(self.gov_id, "prompt", "hi"), ("s:tm1", "reply", "ok"), ("a9", "reply", "slice")])
        ids = [e["entry"]["id"] for e in events]
        self.assertEqual(len(set(ids)), 3, "every entry has its own id")

    def test_view(self):
        self.team()
        self.state.feed_chat({"sid": "tm1", "aid": "", "kind": "prompt", "text": "go", "at": 1.0})
        code, body = self.state.chat_view("s:tm1")
        self.assertEqual(code, 200)
        self.assertEqual((body["to"], body["can_send"], body["busy"]), ("s:tm1", True, True))
        self.assertEqual([(e["kind"], e["text"]) for e in body["entries"]], [("prompt", "go")])
        code, body = self.state.chat_view(self.gov_id)
        self.assertEqual((code, body["can_send"], body["busy"]), (200, True, False))
        code, body = self.state.chat_view("a9")
        self.assertEqual((code, body["can_send"]), (200, False))
        self.assertEqual(self.state.chat_view("s:nobody")[0], 404)

    def test_bad_lines_are_ignored(self):
        self.team()
        for bad in ({"sid": "tm1", "kind": "reply"}, {"sid": "tm1", "kind": "shout", "text": "x"},
                    {"kind": "reply", "text": "x"}, {"sid": "tm1", "kind": "reply", "text": 5}):
            self.state.feed_chat(bad)
        self.assertEqual(self.state.chat_view("s:tm1")[1]["entries"], [])

    def test_only_the_last_chat_keep(self):
        self.team()
        for i in range(ac.CHAT_KEEP + 5):
            self.state.feed_chat({"sid": "tm1", "aid": "", "kind": "reply", "text": str(i), "at": float(i)})
        entries = self.state.chat_view("s:tm1")[1]["entries"]
        self.assertEqual(len(entries), ac.CHAT_KEEP)
        self.assertEqual(entries[-1]["text"], str(ac.CHAT_KEEP + 4))


class TestSending(ChatCase):
    def test_send_rules(self):
        self.team()
        self.assertEqual(self.state.chat_send("s:tm1", "", 0)[0], 400)
        self.assertEqual(self.state.chat_send("s:tm1", 5, 0)[0], 400)
        self.assertEqual(self.state.chat_send("s:tm1", "x" * (ac.CHAT_TEXT_MAX + 1), 0)[0], 400)
        code, body = self.state.chat_send("a9", "hi", 0)
        self.assertEqual((code, body), (400, {"error": "subagent"}))
        self.assertEqual(self.state.chat_send("r:dev:s:1", "hi", 0)[0], 400)
        self.assertEqual(self.state.chat_send("rg:x", "hi", 0)[0], 400)
        self.assertEqual(self.state.chat_send("s:nobody", "hi", 0)[0], 404)

    def test_queued_then_delivered_when_idle(self):
        self.team()
        c = self.client()
        code, body = self.state.chat_send("s:tm1", "先停一下，改用 B 方案", 100.0)
        self.assertEqual((code, body["state"]), (200, "queued"))
        msg_id = body["id"]
        queued = self.events(c)
        self.assertEqual([(e["to"], e["entry"]["kind"], e["entry"]["state"]) for e in queued],
                         [("s:tm1", "owner", "queued")])
        self.assertEqual(self.state.chat_next("tm1", "w1", 0), {"state": "none"}, "busy: it waits")
        self.feed(line("Stop", "tm1", role="task-manager"))
        got = self.state.chat_next("tm1", "w1", 0)
        self.assertEqual((got["state"], got["id"], got["text"]), ("message", msg_id, "先停一下，改用 B 方案"))
        done = self.events(c)
        self.assertEqual([(e["entry"]["id"], e["entry"]["state"]) for e in done], [(msg_id, "delivered")])
        self.assertEqual(self.state.chat_next("tm1", "w1", 0), {"state": "none"}, "delivered once")
        with open(self.decisions) as fh:
            last = json.loads(fh.read().strip().splitlines()[-1])
        self.assertEqual((last["by"], last["verb"], last["sid"], last["text"]),
                         ("owner", "message", "tm1", "先停一下，改用 B 方案"))
        with open(self.chat_path) as fh:
            kept = [json.loads(x) for x in fh if x.strip()]
        self.assertEqual([(x["sid"], x["kind"], x["text"]) for x in kept],
                         [("tm1", "owner", "先停一下，改用 B 方案")])

    def test_newer_watcher_wins(self):
        self.team()
        self.feed(line("Stop", "tm1", role="task-manager"))
        self.assertEqual(self.state.chat_next("tm1", "w1", 0), {"state": "none"})
        self.assertEqual(self.state.chat_next("tm1", "w2", 0), {"state": "none"})
        self.assertEqual(self.state.chat_next("tm1", "w1", 0), {"state": "replaced"})

    def test_session_end_turns_queued_undelivered(self):
        self.team()
        c = self.client()
        _, body = self.state.chat_send("s:tm1", "hello", 0)
        self.events(c)
        self.feed(line("SessionEnd", "tm1", role="task-manager"))
        self.assertEqual([(e["entry"]["id"], e["entry"]["state"]) for e in self.events(c)],
                         [(body["id"], "undelivered")])
        self.assertEqual(self.state.chat_send("s:tm1", "again", 0)[0], 404)

    def test_the_governor_gets_messages_through_gov_next(self):
        self.team()
        _, body = self.state.chat_send(self.gov_id, "总督，今天先做 A", 0)
        got = self.state.gov_next("g1", REPO, "gw1", 0)
        self.assertEqual((got["state"], got["id"], got["text"]), ("message", body["id"], "总督，今天先做 A"))

    def test_delivered_messages_survive_a_restart(self):
        self.team()
        self.state.feed_chat({"sid": "tm1", "aid": "", "kind": "prompt", "text": "go", "at": 1.0})
        with open(self.chat_path, "a") as fh:
            fh.write(json.dumps({"sid": "tm1", "aid": "", "kind": "prompt", "text": "go", "at": 1.0}) + "\n")
        self.feed(line("Stop", "tm1", role="task-manager"))
        self.state.chat_send("s:tm1", "hello", 0)
        self.state.chat_next("tm1", "w1", 0)
        again = self.make()
        again.feed_line(line("UserPromptSubmit", "tm1", role="task-manager"), time.monotonic())
        texts = [(e["kind"], e["text"]) for e in again.chat_view("s:tm1")[1]["entries"]]
        self.assertEqual(texts, [("prompt", "go"), ("owner", "hello")])


class TestLoadChat(unittest.TestCase):
    def test_keeps_the_last_per_key_and_rewrites(self):
        base = tempfile.mkdtemp(prefix="city_loadchat_")
        try:
            path = os.path.join(base, "chat.jsonl")
            with open(path, "w") as fh:
                for i in range(ac.CHAT_KEEP + 3):
                    fh.write(json.dumps({"sid": "s1", "aid": "", "kind": "reply", "text": str(i), "at": i}) + "\n")
                fh.write("garbage\n")
                fh.write(json.dumps({"sid": "s2", "aid": "", "kind": "prompt", "text": "p", "at": 1}) + "\n")
            got = ac.load_chat(path)
            self.assertEqual(len([x for x in got if x["sid"] == "s1"]), ac.CHAT_KEEP)
            self.assertEqual(got[0]["text"], "3")
            self.assertEqual(got[-1]["sid"], "s2")
            with open(path) as fh:
                self.assertEqual(len([x for x in fh if x.strip()]), ac.CHAT_KEEP + 1)
            self.assertEqual(ac.load_chat(os.path.join(base, "none.jsonl")), [])
        finally:
            shutil.rmtree(base, ignore_errors=True)


# ---------------------------------------------------------------------------
# The live server: HTTP and the chat.jsonl tail; chat-watch
# ---------------------------------------------------------------------------

class ChatServerCase(ServerCase):
    def token(self):
        with open(os.path.join(self.dir, "token")) as fh:
            return fh.read().strip()

    def call(self, method, path, body=None, token=True, origin=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        headers = {}
        if token:
            headers["X-City-Token"] = self.token()
        if origin:
            headers["Origin"] = "http://127.0.0.1:%d" % self.port
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

    def tm_session(self, sid="tm1"):
        ev = {"ev": "UserPromptSubmit", "sid": sid, "aid": "", "at": "", "tool": "", "nt": "", "proj": "shop",
              "role": "task-manager", "desc": "", "sub": "", "q": "", "klen": "", "repo": REPO, "kind": ""}
        self.append(json.dumps(ev) + "\n")
        ev["ev"] = "Stop"
        self.append(json.dumps(ev) + "\n")


class TestChatHttp(ChatServerCase):
    def test_view_send_and_next(self):
        self.start()
        self.tm_session()
        self.chat_line({"sid": "tm1", "aid": "", "kind": "reply", "text": "hello from tm1", "at": time.time()})
        self.assertTrue(wait_for(lambda: self.call("GET", "/api/chat?to=s:tm1")[0] == 200
                                 and self.call("GET", "/api/chat?to=s:tm1")[1]["entries"]),
                        "the chat.jsonl line never reached the server")
        status, body = self.call("GET", "/api/chat?to=s:tm1")
        self.assertEqual([e["text"] for e in body["entries"]], ["hello from tm1"])
        status, body = self.call("POST", "/api/chat/send", {"to": "s:tm1", "text": "go on"})
        self.assertEqual((status, body["state"]), (200, "queued"))
        status, got = self.call("GET", "/api/chat/next?sid=tm1&watcher=w1&timeout=2")
        self.assertEqual((status, got["state"], got["text"]), (200, "message", "go on"))

    def test_gates(self):
        self.start()
        self.tm_session()
        self.assertEqual(self.call("GET", "/api/chat?to=s:tm1", token=False)[0], 403)
        self.assertEqual(self.call("POST", "/api/chat/send", {"to": "s:tm1", "text": "x"}, token=False)[0], 403)
        self.assertEqual(self.call("POST", "/api/chat/send", {"to": "s:tm1", "text": "x"}, origin=False)[0], 403)
        self.assertEqual(self.call("GET", "/api/chat/next?sid=tm1&watcher=w&timeout=0", token=False)[0], 403)


class TestWaitingSessionsKeepTheCityUp(ChatServerCase):
    def test_a_waiting_session_keeps_the_server_up(self):
        proc = self.start("--idle-sec", "2")
        self.tm_session()
        env = dict(os.environ, AGENT_CITY_DIR=self.dir, AGENT_ROLE="task-manager",
                   AGENT_CITY_HOME=os.path.join(self.base, "cityhome"))
        path = os.path.join(self.base, "hook-idle.json")
        with open(path, "w") as fh:
            json.dump({"hook_event_name": "Stop", "session_id": "tm1"}, fh)
        with open(path, "rb") as stdin:
            watcher = subprocess.Popen([sys.executable, SERVER, "chat-watch", "--max-wait-sec", "7"],
                                       stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        time.sleep(5)
        self.assertIsNone(proc.poll(), "the server stopped while a session waited to be talked to")
        watcher.communicate(timeout=30)
        self.assertTrue(wait_for(lambda: proc.poll() is not None, timeout=20),
                        "no page and no waiting session: the server must still stop by itself")

    def test_delivered_owner_lines_are_private_too(self):
        base = tempfile.mkdtemp(prefix="city_chatmode_")
        try:
            path = os.path.join(base, "chat.jsonl")
            st = ac.CityState(decisions_path=os.path.join(base, "d.jsonl"), world_path=None, chat_path=path,
                              count_fn=lambda i: 0, balance_fn=lambda i, r: {"kinds": {}, "files": {}, "bad": []})
            st.feed_line(line("UserPromptSubmit", "tm1", role="task-manager"), time.monotonic())
            st.feed_line(line("Stop", "tm1", role="task-manager"), time.monotonic())
            st.chat_send("s:tm1", "hi", 0)
            self.assertEqual(st.chat_next("tm1", "w1", 0)["state"], "message")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        finally:
            shutil.rmtree(base, ignore_errors=True)


class TestChatWatch(ChatServerCase):
    def watch(self, sid="tm1", wait="3"):
        # The hook input comes from a file: closing a stdin PIPE by hand and
        # then calling communicate() raises "flush of closed file" on 3.11.
        env = dict(os.environ, AGENT_CITY_DIR=self.dir, AGENT_ROLE="task-manager",
                   AGENT_CITY_HOME=os.path.join(self.base, "cityhome"))
        path = os.path.join(self.base, "hook-%s.json" % sid)
        with open(path, "w") as fh:
            json.dump({"hook_event_name": "Stop", "session_id": sid}, fh)
        with open(path, "rb") as stdin:
            return subprocess.Popen([sys.executable, SERVER, "chat-watch", "--max-wait-sec", wait],
                                    stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

    def test_wakes_the_session_with_the_owner_text(self):
        self.start()
        self.tm_session()
        self.assertTrue(wait_for(lambda: self.call("GET", "/api/chat?to=s:tm1")[0] == 200))
        proc = self.watch(wait="20")
        time.sleep(0.5)
        self.call("POST", "/api/chat/send", {"to": "s:tm1", "text": "请先跑一下测试 7731"})
        out, err = proc.communicate(timeout=25)
        self.assertEqual(proc.returncode, 2, err)
        self.assertIn("请先跑一下测试 7731", err.decode())
        self.assertIn("city page", err.decode())

    def test_no_message_no_wake(self):
        self.start()
        self.tm_session()
        proc = self.watch(wait="2")
        out, err = proc.communicate(timeout=20)
        self.assertEqual((proc.returncode, err), (0, b""))

    def test_no_server_no_wake(self):
        os.makedirs(self.dir, exist_ok=True)
        proc = self.watch(wait="2")
        out, err = proc.communicate(timeout=20)
        self.assertEqual((proc.returncode, err), (0, b""))


# ---------------------------------------------------------------------------
# Chat never leaves the computer
# ---------------------------------------------------------------------------

class TestStaysHome(unittest.TestCase):
    def test_relay_never_touches_chat(self):
        with open(RELAY, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("chat", src.lower())
        import agent_city_relay as rl
        for key in ("text", "prompt", "last_assistant_message"):
            self.assertNotIn(key, rl._KEPT_LINE_FIELDS)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

CHAT_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, String, Array, Object };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
process.stdout.write(JSON.stringify(cases.map(([entries, name, busy]) => box.chatHtml(entries, name, busy))));
"""


class TestPageChat(unittest.TestCase):
    def html(self, *cases):
        esc = re.search(r"^const esc = .*;$", inline_script(), re.M)
        self.assertIsNotNone(esc, "const esc = ...; not found")
        lit = const_object("CHAT_STATE_ZH")
        self.assertIsNotNone(lit, "const CHAT_STATE_ZH = {...}; not found")
        prelude = esc.group(0).replace("const esc", "var esc") + "\nvar CHAT_STATE_ZH = %s;" % lit
        return run_node(CHAT_JS, {"prelude": prelude, "fns": page_fns("chatHtml"), "cases": [list(c) for c in cases]})

    def test_state_words(self):
        self.assertEqual(js_value(const_object("CHAT_STATE_ZH") or "null"),
                         {"queued": "已发送", "delivered": "已送达", "undelivered": "没送到"})

    def test_chat_html(self):
        entries = [{"id": 1, "kind": "prompt", "text": "fix <b>it</b>", "at": 1},
                   {"id": 2, "kind": "reply", "text": "done", "at": 2},
                   {"id": 3, "kind": "owner", "text": "thanks", "at": 3, "state": "queued"}]
        html, busy, empty = self.html((entries, "worker · <x>", False), (entries, "w", True), ([], "w", False))
        self.assertEqual(re.findall(r'<li class="msg" data-kind="(\w+)" data-id="(\d+)"', html),
                         [("prompt", "1"), ("reply", "2"), ("owner", "3")])
        for word in ("你（终端）", "你（页面）", "已发送", "fix &lt;b&gt;it&lt;/b&gt;", "worker · &lt;x&gt;"):
            with self.subTest(word=word):
                self.assertIn(word, html)
        self.assertNotIn("<b>it</b>", html)
        self.assertNotIn("等它做完这一步", html, "not busy: no wait line")
        self.assertIn('<li class="msg-wait">等它做完这一步</li>', busy)
        self.assertIn('<li class="msg-empty">还没有对话</li>', empty)

    def test_chat_target(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = {}; vm.createContext(box); vm.runInContext(fns, box);
process.stdout.write(JSON.stringify([{ t: 'gov', terr: 't1' }, { t: 'c', id: 's:tm1' }, { t: 'c', id: 'a9' },
  { t: 'rg', id: 'r:dev:s:1' }, { t: 'b', id: 4 }, null].map(s => box.chatTarget(s))));
"""
        self.assertEqual(run_node(js, {"fns": page_fns("chatTarget")}), ["gov:t1", "s:tm1", "a9", None, None, None])

    def test_the_open_window_asks_for_the_right_id(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const people = { 's:tm1': { id: 's:tm1', lead: true }, 's:tm2': { id: 's:tm2' }, 'a9': { id: 'a9' },
  'r:dev:s:1': { id: 'r:dev:s:1', remote: { who: 'Ann' } } };
const box = { selected: null, govTerr: 't0', byId: id => people[id] };
vm.createContext(box); vm.runInContext(fns, box);
const out = [];
for (const sel of [{ t: 'c', id: 's:tm1' }, { t: 'c', id: 's:tm2' }, { t: 'c', id: 'a9' }, { t: 'c', id: 'r:dev:s:1' },
                   { t: 'gov', terr: 't1' }, { t: 'gov' }, null]) { box.selected = sel; out.push(box.curChatTo()); }
process.stdout.write(JSON.stringify(out));
"""
        out = run_node(js, {"fns": page_fns("curChatTo", "chatTarget")})
        self.assertEqual(out, ["s:tm1", "s:tm2", "a9", None, "gov:t1", "gov:t0", None])

    def test_the_log_names_the_person(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const people = { 's:tm1': { id: 's:tm1', label: 'task-manager', task: 'shop' }, 'a9': { id: 'a9', label: 'worker', task: 'form' } };
const box = { byId: id => people[id], nameOf: c => c.label + ' · ' + c.task };
vm.createContext(box); vm.runInContext(fns, box);
process.stdout.write(JSON.stringify(['s:tm1', 'a9', 'gov:t1', 's:gone'].map(t => box.chatDisplayName(t))));
"""
        out = run_node(js, {"fns": page_fns("chatDisplayName")})
        self.assertEqual(out, ["task-manager · shop", "worker · form", "总督", "s:gone"],
                         "E2E 2026-09-27: the log said 你 → tm1 instead of the name")

    def test_window_has_the_conversation_and_the_box(self):
        body = function_source("renderDetail") or ""
        for needle in ("chatHtml(", 'id="chat"', 'id="say"', 'id="say-text"', 'maxlength="4000"', "发送", "组长"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)

    def test_load_and_send(self):
        load = function_source("loadChat") or ""
        send = function_source("sendChat") or ""
        self.assertIn("'/api/chat?to=' + encodeURIComponent(", load)
        self.assertIn("'/api/chat/send'", send)
        for src, name in ((load, "loadChat"), (send, "sendChat")):
            with self.subTest(fn=name):
                self.assertIn("'X-City-Token': TOKEN", src)
                self.assertRegex(src, r"if \(DEMO\)", "demo never fetches")
                self.assertRegex(src, r"catch|\.ok", "a failure is shown, never swallowed")
        self.assertIn("'POST'", send)
        self.assertRegex(inline_script(), r"(?m)^const chats = new Map\(\);")

    def test_submit_sends(self):
        text = inline_script()
        m = re.search(r"addEventListener\('submit', e => \{(.*?)\n\}\);", text, re.S)
        self.assertIsNotNone(m, "no submit listener")
        self.assertIn("preventDefault()", m.group(1))
        self.assertIn("sendChat(", m.group(1))

    def test_a_failed_send_keeps_the_text(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { JSON, console, Promise, Error, String, Date, DEMO: false, TOKEN: 't', chats: new Map(),
  renderPanel(){}, demoSendChat(){} };
vm.createContext(box);
vm.runInContext(fns, box);
(async () => {
  box.fetch = () => Promise.reject(new Error('down'));
  const down = await box.sendChat('s:tm1', 'hi');
  box.fetch = () => Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
  const refused = await box.sendChat('s:tm1', 'hi');
  box.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({ id: 7, state: 'queued' }) });
  const took = await box.sendChat('s:tm1', 'hi');
  process.stdout.write(JSON.stringify([down, refused, took, (box.chats.get('s:tm1') || {}).error || '']));
})();
"""
        down, refused, took, _ = run_node(js, {"fns": page_fns("sendChat")})
        self.assertEqual((down, refused, took), (False, False, True))
        text = inline_script()
        m = re.search(r"addEventListener\('submit', e => \{(.*?)\n\}\);", text, re.S)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(1), r"then\(\s*ok\s*=>[^\n]*if \(ok", "the box is cleared only when the send worked")

    def test_chat_event(self):
        block = zh_resolved(case_block("chat") or "")
        self.assertTrue(block, "case 'chat': not handled")
        self.assertIn("chats", block)
        self.assertIn("你 →", block)


if __name__ == "__main__":
    unittest.main()
