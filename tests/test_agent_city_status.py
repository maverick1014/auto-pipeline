"""Failing tests for city-status: 等你 only when the agent really needs the owner.

RULE (owner, 2026-10-01; requirements/city.md, "Status")

  S1 等你 (rail, panel, the 等你回话 head bubble) only when the agent needs the
     owner: a permission prompt or a question prompt (AskUserQuestion) is
     open, or its last reply asks the owner.
  S2 A report-only turn while background work still runs = 后台在跑
     ("Working in background"): its own colour, no bubble.
  S3 Otherwise 空闲. A Notification idle_prompt changes nothing any more.
  S4 Same rule for the governor and for every session citizen (task manager,
     helper, plain session). Subagents keep their states.

CONTRACT

  1. agent_city.asks_owner(text) -> bool. True when TEXT (a session's last
     reply) asks the owner:
       - a line begins with 要你决定 or "What to decide" (a section head;
         leading spaces and the marks # * _ > - before it do not count), or
       - a line begins with QUESTION: (leading spaces allowed), or
       - its last sentence ends with ? or ？ (trailing spaces, newlines and
         closing marks * _ ` " ' ) ） 」 』 ” ’ do not count).
     Anything else, an empty text or a non-string -> False. Never raises.

  2. agent_city.background_work(tasks) -> bool. TASKS is the Stop hook
     input's "background_tasks" (Claude Code 2.1.145+: a list of
     {"id","type","status","description",...}, in-flight work only, [] when
     nothing runs). True when at least one entry is a dict whose "type" is
     not housekeeping ("dream", "auto-mode scan", "memory import"). A missing
     field (older Claude Code), a non-list or bad entries -> False.
     Not counted, by design: "session_crons" (a wake-up later is not work
     now) and async hooks (the hook input does not list them; the city's own
     watcher hooks are async hooks).

  3. `agent_city.py say` on a Stop (the session's own, no agent_id) appends
     ONE line to <city dir>/events.jsonl, also when the reply text is empty:
       {"ev":"StopNote","sid":<session_id>,"need":"1"|"","bg":"1"|""}
     need = asks_owner(last_assistant_message), bg = background_work(
     background_tasks). Flags only: never the text, never a task's command or
     description. Nothing for UserPromptSubmit or SubagentStop, nothing when
     the city is off or in a cloud session. chat.jsonl as before.

  4. Reducer. A session's status when its turn ends, the governor and a
     session citizen alike:
       StopNote need "1"            -> waiting
       StopNote bg "1" (need "")    -> background
       StopNote, both ""            -> idle
       Stop (no note: old hooks)    -> idle when the session was busy; a
                                       session already waiting, background or
                                       idle is left as it is (the note
                                       decides, whichever line comes first)
       Notification idle_prompt     -> nothing
     Governor events {"type":"gov","state"}: busy | waiting | background | idle,
     only on a change. Also waiting on PermissionRequest, on PreToolUse of
     AskUserQuestion and on Notification permission_prompt; busy again on
     PostToolUse, UserPromptSubmit, PermissionDenied or another PreToolUse.
     Citizen events {"type":"waiting"|"background"|"idle","id"}, once per
     change; its next PreToolUse, PostToolUse or UserPromptSubmit gives
     {"type":"resume","id"} first. Snapshot agents carry "status":
     "" | "waiting" | "background" | "idle", and "waiting" (status == waiting).
     A StopNote of a session the Reducer has never seen: [] and no session.
     A StopNote with an agent id: [] (subagents keep their states).

  5. CityState. A StopNote line carries no repo: it stays in its session's
     territory, the governor keeps the seat, and a never-seen session's note
     shows nobody. The snapshot gives govs[].state and agents[].status.

  6. Page (bin/agent-city.html).
       texts   status.background 后台在跑 / Working in background,
               status.idle 空闲 / Idle
       colour  violet: --bgrun-bg / --bgrun-ink (light, dark media, dark
               theme), .chip.bgrun, .pill.bgrun, .sdot.st-bgrun
       govRowStatus(terr) -> [class, text]: ['bgrun', 后台在跑] for a governor
               in background, else ['gov', the text govRowText gave before];
               govRowText(terr) = govRowStatus(terr)[1]. The rail row and the
               governor's panel pill both use it.
       govTalk(terr) -> '' in background (no bubble); 等你回话… only waiting.
       citizenStatus(c): c.waiting -> ['you', 等你回话] (as before), c.bgrun
               -> ['bgrun', 后台在跑], c.idle -> ['walk', 空闲]; an open ask
               still wins.
       apply(): 'waiting' / 'background' / 'idle' set exactly one of
               c.waiting, c.bgrun, c.idle; 'resume' clears all three; the
               person stays where it is. A snapshot agent's "status" places
               it the same way; another member's people (applyRemote) get
               the same four cases.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)

import agent_city as ac  # noqa: E402
import test_agent_city_page as tp  # noqa: E402
from test_agent_city_people import run_sim  # noqa: E402
from cityhelp import Mains  # noqa: E402

SERVER = os.path.join(ROOT, "bin", "agent_city.py")


def fn(name):
    f = getattr(ac, name, None)
    if f is None:
        raise AssertionError("bin/agent_city.py has no %s()" % name)
    return f


# ------------------------------------------------------------------ 1. S1

ASKS = [
    "Result: pass\n\n要你决定\n- 现在合并，还是等 E2E",
    "## 要你决定\n无",
    "结果：通过\n**要你决定**：现在合并吗",
    "Result: pass\nWhat changed: 2 files\nWhat to decide: merge now or wait",
    "### What to decide\n- nothing",
    "- **What to decide**: nothing",
    "QUESTION: which port should the city use",
    "Tests pass.\nQUESTION: merge now, or wait for the E2E",
    "  QUESTION: indented",
    "要现在合并吗？",
    "合并已完成。要我继续下一步吗？\n",
    "Shall I merge now?",
    "Two options are open. Which one do you want?   \n\n",
    "**Merge now?**",
    "Done with step 1. Go on with step 2 (the page)?",
    "下一步做页面，可以吗？」",
]

REPORTS = [
    "合并已经在 pc2 上开始了，11:00 左右完成。",
    "合并已经在 pc2 上开始了… 11:00 左右完成",
    "Done. 3 files changed, 12 tests pass.",
    "Why did it fail? The port was taken. Fixed now.",
    "为什么失败？端口被占用了。已经修好。",
    "See http://127.0.0.1:4777/?token=abc for the page.",
    "The line has QUESTION: in the middle, it is no question.",
    "I renamed the 要你决定 heading in the report.",
    "The report has a part named What to decide, it is empty.",
    "consignment-count-only: 4 rows counted.",
    "",
    "   \n",
]


class TestAsksOwner(unittest.TestCase):
    def test_asks(self):
        asks_owner = fn("asks_owner")
        for text in ASKS:
            with self.subTest(text=text):
                self.assertIs(asks_owner(text), True)

    def test_reports(self):
        asks_owner = fn("asks_owner")
        for text in REPORTS:
            with self.subTest(text=text):
                self.assertIs(asks_owner(text), False)

    def test_not_a_text(self):
        asks_owner = fn("asks_owner")
        for value in (None, 42, ["要你决定"], {"a": "?"}, b"ok?"):
            with self.subTest(value=value):
                self.assertIs(asks_owner(value), False)

    def test_long_reply_asks_at_the_end(self):
        asks_owner = fn("asks_owner")
        body = "一行报告。\n" * 3000
        self.assertIs(asks_owner(body), False)
        self.assertIs(asks_owner(body + "要继续吗？"), True)
        self.assertIs(asks_owner("要你决定\n" + body), True)


# ------------------------------------------------------------------ 2. S2

def task(kind, **kw):
    out = {"id": "t1", "type": kind, "status": "running", "description": "d"}
    out.update(kw)
    return out


class TestBackgroundWork(unittest.TestCase):
    def test_work_that_counts(self):
        background_work = fn("background_work")
        for kind in ("shell", "subagent", "workflow", "monitor", "MCP task", "teammate", "cloud session",
                     "some_new_type"):
            with self.subTest(kind=kind):
                self.assertIs(background_work([task(kind)]), True)

    def test_nothing_in_flight(self):
        background_work = fn("background_work")
        for value in ([], None, "", "shell", 3, {"type": "shell"}, [None, "shell", 7]):
            with self.subTest(value=value):
                self.assertIs(background_work(value), False)

    def test_housekeeping_does_not_count(self):
        background_work = fn("background_work")
        house = [task("dream"), task("auto-mode scan"), task("memory import")]
        self.assertIs(background_work(house), False)
        self.assertIs(background_work(house + [task("shell", command="sleep 60")]), True)


# --------------------------------------------------------------- 3. say

class TestSayWritesTheNote(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_status_say_")
        self.dir = os.path.join(self.base, "city")
        os.makedirs(self.dir)
        with open(os.path.join(self.dir, "on"), "w") as fh:
            fh.write("1 1\n")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def say(self, payload, **env_extra):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE"}
        env.update(AGENT_CITY_DIR=self.dir, HOME=self.base)
        env.update(env_extra)
        r = subprocess.run([sys.executable, SERVER, "say"], input=json.dumps(payload).encode("utf-8"),
                           capture_output=True, env=env, timeout=20)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, b"", b""))

    def read(self, name):
        try:
            with open(os.path.join(self.dir, name), encoding="utf-8") as fh:
                return [json.loads(x) for x in fh if x.strip()]
        except FileNotFoundError:
            return []

    def stop(self, text, tasks=None, **kw):
        payload = {"session_id": "s1", "transcript_path": "/t/s1.jsonl", "cwd": "/w",
                   "hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": text}
        if tasks is not None:
            payload["background_tasks"] = tasks
            payload["session_crons"] = []
        payload.update(kw)
        return payload

    def test_report_only(self):
        self.say(self.stop("合并已经在 pc2 上开始了，11:00 左右完成。", tasks=[]))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "", "bg": ""}])

    def test_reply_that_asks(self):
        self.say(self.stop("结果：通过\n\n要你决定\n- 现在合并吗", tasks=[]))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "1", "bg": ""}])

    def test_background_shell(self):
        self.say(self.stop("Started the build.", tasks=[task("shell", command="sleep 60")]))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "", "bg": "1"}])

    def test_asks_and_background(self):
        self.say(self.stop("Merge now?", tasks=[task("subagent", agent_type="worker")]))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "1", "bg": "1"}])

    def test_old_claude_code_has_no_task_list(self):
        self.say(self.stop("Done."))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "", "bg": ""}])

    def test_empty_reply_still_writes_the_note(self):
        self.say(self.stop("", tasks=[task("shell")]))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "", "bg": "1"}])
        self.assertEqual(self.read("chat.jsonl"), [])

    def test_flags_only(self):
        self.say(self.stop("secret reply text?", tasks=[task("shell", command="curl https://secret.example",
                                                             description="secret description")]))
        with open(os.path.join(self.dir, "events.jsonl"), encoding="utf-8") as fh:
            raw = fh.read()
        self.assertEqual(raw.count("\n"), 1)
        for leak in ("secret", "curl", "/t/s1.jsonl"):
            self.assertNotIn(leak, raw)

    def test_chat_row_as_before(self):
        self.say(self.stop("Merge now?", tasks=[]))
        rows = self.read("chat.jsonl")
        self.assertEqual([(r["sid"], r["aid"], r["kind"], r["text"]) for r in rows],
                         [("s1", "", "reply", "Merge now?")])

    def test_only_the_sessions_own_stop(self):
        self.say({"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "go?"})
        self.say({"session_id": "s1", "hook_event_name": "SubagentStop", "agent_id": "a1",
                  "last_assistant_message": "QUESTION: which?", "background_tasks": [task("shell")]})
        self.assertEqual(self.read("events.jsonl"), [])

    def test_city_off_or_cloud(self):
        self.say(self.stop("Merge now?", tasks=[]), CLAUDE_CODE_REMOTE="true")
        os.remove(os.path.join(self.dir, "on"))
        self.say(self.stop("Merge now?", tasks=[]))
        self.assertEqual(self.read("events.jsonl"), [])


# ------------------------------------------------------------ 4. Reducer

def R(ev, sid="main", aid="", at="", tool="", nt="", role="", **kw):
    line = {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": nt, "proj": "shop",
            "role": role, "desc": "", "sub": "", "q": ""}
    line.update(kw)
    return line


def note(sid, need="", bg="", **kw):
    line = {"ev": "StopNote", "sid": sid, "need": need, "bg": bg}
    line.update(kw)
    return line


def gov(state):
    return [{"type": "gov", "state": state}]


class TestGovernorStatus(unittest.TestCase):
    def setUp(self):
        self.r = ac.Reducer()
        self.t = 0.0
        self.assertEqual(self.feed(R("UserPromptSubmit")), gov("busy"))

    def feed(self, line):
        self.t += 1.0
        return self.r.feed(line, self.t)

    def state(self):
        return self.r.snapshot()["gov"]["state"]

    def test_report_only_is_idle(self):
        self.assertEqual(self.feed(R("Stop")), gov("idle"))
        self.assertEqual(self.feed(note("main")), [])
        self.assertEqual(self.state(), "idle")

    def test_note_first_then_stop(self):
        self.assertEqual(self.feed(note("main")), gov("idle"))
        self.assertEqual(self.feed(R("Stop")), [])

    def test_idle_prompt_is_not_waiting(self):
        self.feed(R("Stop"))
        self.feed(note("main"))
        self.assertEqual(self.feed(R("Notification", nt="idle_prompt")), [])
        self.assertEqual(self.state(), "idle")

    def test_idle_prompt_while_busy_changes_nothing(self):
        self.assertEqual(self.feed(R("Notification", nt="idle_prompt")), [])
        self.assertEqual(self.state(), "busy")

    def test_reply_that_asks_is_waiting(self):
        self.assertEqual(self.feed(R("Stop")), gov("idle"))
        self.assertEqual(self.feed(note("main", need="1")), gov("waiting"))
        self.assertEqual(self.feed(R("Notification", nt="idle_prompt")), [])
        self.assertEqual(self.state(), "waiting")

    def test_asking_note_first_then_stop_stays_waiting(self):
        self.assertEqual(self.feed(note("main", need="1")), gov("waiting"))
        self.assertEqual(self.feed(R("Stop")), [])
        self.assertEqual(self.state(), "waiting")

    def test_background_work(self):
        self.assertEqual(self.feed(R("Stop")), gov("idle"))
        self.assertEqual(self.feed(note("main", bg="1")), gov("background"))
        self.assertEqual(self.feed(R("Notification", nt="idle_prompt")), [])
        self.assertEqual(self.state(), "background")

    def test_background_ends_with_the_next_note(self):
        self.feed(note("main", bg="1"))
        self.feed(R("Stop"))
        # the shell ended: Claude Code wakes the session, the wake-up turn ends with nothing in flight
        self.assertEqual(self.feed(R("Stop")), [])
        self.assertEqual(self.feed(note("main")), gov("idle"))

    def test_asking_wins_over_background(self):
        self.assertEqual(self.feed(note("main", need="1", bg="1")), gov("waiting"))

    def test_next_turn_is_busy_again(self):
        for flags in ({"need": "1"}, {"bg": "1"}, {}):
            with self.subTest(flags=flags):
                self.feed(note("main", **flags))
                self.assertEqual(self.feed(R("UserPromptSubmit")), gov("busy"))

    def test_open_prompts_are_waiting(self):
        self.assertEqual(self.feed(R("PermissionRequest", tool="Bash")), gov("waiting"))
        self.assertEqual(self.feed(R("PostToolUse", tool="Bash")), gov("busy"))
        self.assertEqual(self.feed(R("PreToolUse", tool="AskUserQuestion", q="Which one?")), gov("waiting"))
        self.assertEqual(self.feed(R("PostToolUse", tool="AskUserQuestion")), gov("busy"))
        self.assertEqual(self.feed(R("Notification", nt="permission_prompt")), gov("waiting"))
        self.assertEqual(self.feed(R("PermissionDenied", tool="Bash")), gov("busy"))
        self.assertEqual(self.feed(R("PreToolUse", tool="Agent", desc="d", sub="worker")), [])

    def test_a_note_with_an_agent_id_is_ignored(self):
        self.assertEqual(self.feed(note("main", need="1", aid="a1")), [])
        self.assertEqual(self.state(), "busy")
        self.assertEqual(self.r.snapshot()["agents"], [])


class TestCitizenStatus(unittest.TestCase):
    def setUp(self):
        self.r = ac.Reducer()
        self.t = 0.0
        self.feed(R("UserPromptSubmit"))                       # the governor
        self.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Write"))
        self.feed(R("PostToolUse", sid="h1", tool="Read"))    # a helper: no role, a citizen

    def feed(self, line):
        self.t += 1.0
        return self.r.feed(line, self.t)

    def agent(self, cid):
        return [a for a in self.r.snapshot()["agents"] if a["id"] == cid][0]

    def test_working_citizen_has_no_status(self):
        a = self.agent("s:tm1")
        self.assertEqual((a["status"], a["waiting"]), ("", False))

    def test_report_only_is_idle(self):
        self.assertEqual(self.feed(R("Stop", sid="tm1", role="task-manager")), [{"type": "idle", "id": "s:tm1"}])
        self.assertEqual(self.feed(note("tm1")), [])
        a = self.agent("s:tm1")
        self.assertEqual((a["status"], a["waiting"], a["stuck"]), ("idle", False, False))

    def test_idle_prompt_is_not_waiting(self):
        self.feed(R("Stop", sid="tm1", role="task-manager"))
        self.assertEqual(self.feed(R("Notification", sid="tm1", role="task-manager", nt="idle_prompt")), [])
        self.assertEqual(self.agent("s:tm1")["status"], "idle")
        self.assertEqual(self.feed(R("Notification", sid="h1", nt="idle_prompt")), [])
        self.assertEqual(self.agent("s:h1")["status"], "")

    def test_reply_that_asks_is_waiting(self):
        self.feed(R("Stop", sid="tm1", role="task-manager"))
        self.assertEqual(self.feed(note("tm1", need="1")), [{"type": "waiting", "id": "s:tm1"}])
        self.assertEqual(self.feed(R("Stop", sid="tm1", role="task-manager")), [])
        a = self.agent("s:tm1")
        self.assertEqual((a["status"], a["waiting"], a["stuck"]), ("waiting", True, False))

    def test_background_work_then_idle(self):
        self.assertEqual(self.feed(note("h1", bg="1")), [{"type": "background", "id": "s:h1"}])
        self.assertEqual(self.feed(R("Stop", sid="h1")), [])
        a = self.agent("s:h1")
        self.assertEqual((a["status"], a["waiting"]), ("background", False))
        self.assertEqual(self.feed(R("Stop", sid="h1")), [])
        self.assertEqual(self.feed(note("h1")), [{"type": "idle", "id": "s:h1"}])
        self.assertEqual(self.agent("s:h1")["status"], "idle")

    def test_same_note_twice_is_one_event(self):
        self.assertEqual(self.feed(note("tm1", need="1")), [{"type": "waiting", "id": "s:tm1"}])
        self.assertEqual(self.feed(note("tm1", need="1")), [])

    def test_resume_comes_first(self):
        for flags in ({"need": "1"}, {"bg": "1"}, {}):
            with self.subTest(flags=flags):
                self.feed(note("tm1", **flags))
                out = self.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Edit"))
                self.assertEqual(out[0], {"type": "resume", "id": "s:tm1"})
                self.assertEqual(out[1]["type"], "tool")
                self.assertEqual(self.agent("s:tm1")["status"], "")

    def test_prompt_resumes(self):
        self.feed(note("h1"))
        self.assertEqual(self.feed(R("UserPromptSubmit", sid="h1")), [{"type": "resume", "id": "s:h1"}])

    def test_permission_prompt_is_still_stuck(self):
        out = self.feed(R("Notification", sid="tm1", role="task-manager", nt="permission_prompt"))
        self.assertEqual(out, [{"type": "stuck", "id": "s:tm1", "question": "", "tool": ""}])

    def test_never_seen_session(self):
        before = self.r.snapshot()
        self.assertEqual(self.feed(note("ghost", need="1", bg="1")), [])
        self.assertEqual(self.r.snapshot(), before)
        self.assertNotIn("ghost", self.r.sessions)

    def test_subagents_keep_their_states(self):
        self.feed(R("SubagentStart", sid="tm1", aid="w1", at="worker"))
        self.assertEqual(self.feed(note("tm1", need="1", aid="w1")), [])
        self.assertEqual(self.feed(R("Notification", sid="tm1", aid="w1", at="worker", nt="idle_prompt")), [])
        w = self.agent("w1")
        self.assertEqual((w["status"], w["waiting"], w["stuck"], w["done"]), ("", False, False, False))
        self.assertEqual(self.agent("s:tm1")["status"], "")


# ---------------------------------------------------------- 5. CityState

def drain(client):
    out = []
    while not client.queue.empty():
        out.append(json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1]))
    return out


def snapshot(st):
    client = st.add_client()
    return json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1])


class TestStatusInTheCity(unittest.TestCase):
    A = "/work/a/.git"
    B = "/work/b/.git"

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_status_")
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"),
                               plans=ac.load_plans(), count_fn=lambda i: 0,
                               balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}},
                               start_repo=self.A, main_fn=Mains({self.A: "g1", self.B: "g2"}))
        self.t = 1000.0
        self.line("UserPromptSubmit", "g1", self.A)
        self.line("UserPromptSubmit", "g2", self.B)
        self.line("PostToolUse", "tm1", self.B, role="task-manager", tool="Write")
        self.client = self.st.add_client()
        drain(self.client)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def line(self, ev, sid, repo, role="", tool="", nt=""):
        self.t += 1.0
        self.st.feed_line({"ev": ev, "sid": sid, "aid": "", "at": "", "tool": tool, "nt": nt, "proj": "p",
                           "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo,
                           "ask": "", "wt": "", "file": "", "tp": "", "pid": ""}, self.t)

    def note(self, sid, need="", bg=""):
        self.t += 1.0
        self.st.feed_line({"ev": "StopNote", "sid": sid, "need": need, "bg": bg}, self.t)

    def govs(self):
        return {g["terr"]: g["state"] for g in snapshot(self.st)["govs"]}

    def status_events(self):
        return [(e["type"], e.get("id")) for e in drain(self.client)
                if e["type"] in ("gov", "waiting", "background", "idle", "resume", "stuck", "spawn", "leave")]

    def test_a_note_stays_in_its_sessions_territory(self):
        self.line("Stop", "g2", self.B)
        self.note("g2", bg="1")
        events = [e for e in drain(self.client) if e["type"] == "gov"]
        self.assertEqual([(e["state"], e["terr"], e["present"]) for e in events],
                         [("idle", ac.territory_id(self.B), True), ("background", ac.territory_id(self.B), True)])
        self.assertEqual(self.govs(), {ac.territory_id(self.A): "busy", ac.territory_id(self.B): "background"})

    def test_the_governor_keeps_the_seat(self):
        self.note("g1", need="1")
        snap = snapshot(self.st)
        self.assertEqual({g["terr"]: g["state"] for g in snap["govs"]}[ac.territory_id(self.A)], "waiting")
        self.assertEqual([a["id"] for a in snap["agents"]], ["s:tm1"])

    def test_citizen_status_reaches_the_page(self):
        self.note("tm1", bg="1")
        self.assertEqual(self.status_events(), [("background", "s:tm1")])
        a = snapshot(self.st)["agents"][0]
        self.assertEqual((a["id"], a["status"], a["waiting"], a["terr"]),
                         ("s:tm1", "background", False, ac.territory_id(self.B)))
        self.note("tm1")
        self.assertEqual(self.status_events(), [("idle", "s:tm1")])
        self.assertEqual(snapshot(self.st)["agents"][0]["status"], "idle")

    def test_idle_prompt_changes_nothing(self):
        self.line("Stop", "g1", self.A)
        self.line("Stop", "tm1", self.B, role="task-manager")
        drain(self.client)
        self.line("Notification", "g1", self.A, nt="idle_prompt")
        self.line("Notification", "tm1", self.B, role="task-manager", nt="idle_prompt")
        self.assertEqual([e for e in drain(self.client) if e["type"] in ("gov", "waiting", "stuck", "ask")], [])
        snap = snapshot(self.st)
        self.assertEqual({g["terr"]: g["state"] for g in snap["govs"]}[ac.territory_id(self.A)], "idle")
        self.assertEqual(snap["agents"][0]["status"], "idle")

    def test_never_seen_session(self):
        before = snapshot(self.st)
        self.note("ghost", need="1", bg="1")
        self.assertEqual(drain(self.client), [])
        after = snapshot(self.st)
        self.assertEqual((after["govs"], after["agents"]), (before["govs"], before["agents"]))


# --------------------------------------------------------------- 6. Page

def need(*names):
    for n in names:
        if tp.function_source(n) is None:
            raise AssertionError("function %s(...) not found in the page script" % n)
    return tp.page_fns(*names)


GOV_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const here = new Set(['a', 'b', 'c', 'd', 'e']);
const box = { Math, JSON, console, simT: 0, govTerr: 'a', govsByTerr: new Map(),
  governorAt: terr => (here.has(terr) ? { x: 0, y: 0 } : null),
  byId: () => null, nameOf: () => '', citizenStatus: () => ['walk', ''],
  esc: s => String(s) };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
for (const [terr, state] of [['a', 'background'], ['b', 'waiting'], ['c', 'idle'], ['d', 'busy'], ['e', 'unknown']])
  box.govsByTerr.set(terr, { state });
const out = { status: {}, text: {}, talk: {} };
for (const terr of ['a', 'b', 'c', 'd', 'e', 'gone']) {
  out.status[terr] = box.govRowStatus(terr);
  out.text[terr] = box.govRowText(terr);
  out.talk[terr] = box.govTalk(terr);
}
out.row = box.railRowHtml({ id: 'gov:a', depth: 0, rest: false }, { selId: null, color: '#fff' });
out.rowWaiting = box.railRowHtml({ id: 'gov:b', depth: 0, rest: false }, { selId: null, color: '#fff' });
process.stdout.write(JSON.stringify(out));
"""

CITIZEN_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, governorAt: () => ({ x: 0, y: 0 }) };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const base = { state: 'working', askKind: '', askPhase: '', relay: '' };
const s = extra => box.citizenStatus(Object.assign({}, base, extra));
process.stdout.write(JSON.stringify({
  waiting: s({ waiting: true }), bgrun: s({ bgrun: true }), idle: s({ idle: true }), plain: s({}),
  idleAsk: s({ idle: true, askKind: 'permission' }),
  bgrunAsk: s({ bgrun: true, askKind: 'question', askPhase: 'owner' }),
}));
"""

SIM_DRIVER = r"""
const V = __payload.view, T = V.territories[0], tid = T.id;
function buildLand(view){ landState(view); }
const agent = (id, extra) => Object.assign({ id, role: 'task-manager', label: 'task-manager', task: id,
  stuck: false, done: false, waiting: false, status: '', tools: {}, terr: tid }, extra);
apply({ type: 'snapshot', world: V, gov: { state: 'background', terr: tid }, govs: [{ terr: tid, state: 'background' }],
  governors: 1, asks: [], shows: [], agents: [agent('s:a'), agent('s:b', { status: 'background' }),
    agent('s:c', { status: 'idle' }), agent('s:d', { status: 'waiting', waiting: true })] });
const st = id => citizenStatus(byId(id), 1);
const out = { snap: [st('s:a'), st('s:b'), st('s:c'), st('s:d')], govSnap: [govRowStatus(tid), govTalk(tid)] };
const a = byId('s:a'), at = [a.x, a.y];
const step = type => { apply({ type, id: 's:a' }); return st('s:a'); };
out.steps = ['background', 'idle', 'waiting', 'resume', 'idle', 'background', 'resume'].map(step);
out.moved = Math.hypot(a.x - at[0], a.y - at[1]) + (a.path ? a.path.length : 0);
apply({ type: 'gov', terr: tid, state: 'waiting', present: true });
out.govWaiting = [govRowStatus(tid), govTalk(tid)];
apply({ type: 'gov', terr: tid, state: 'background', present: true });
out.govBg = [govRowStatus(tid), govTalk(tid)];
__out = out;
"""

SIM_REQUIRED = ("landState", "governorAt", "apply", "citizens", "byId", "citizenStatus", "govRowStatus", "govTalk")

_CACHE = {}


def sim_results():
    if "sim" not in _CACHE:
        plans = ac.load_plans()
        world = ac.new_world()
        terr = ac.add_territory(world, plans, "/work/status/app/.git", "app", 6000)
        terr["peak"] = terr["lines"] = 6000
        _CACHE["sim"] = run_sim(SIM_DRIVER, {"view": ac.layout(world, plans)}, SIM_REQUIRED)
    return _CACHE["sim"]


def texts():
    if "texts" not in _CACHE:
        _CACHE["texts"] = tp.js_value(tp.const_object("TEXT"))
    return _CACHE["texts"]


def gov_results():
    if "gov" not in _CACHE:
        _CACHE["gov"] = tp.run_node(GOV_JS, {
            "prelude": tp.constants_prelude(),
            "fns": need("govRowStatus", "govRowText", "govSay", "govTalk", "railRowHtml")})
    return _CACHE["gov"]


class TestPageTexts(unittest.TestCase):
    def test_words(self):
        t = texts()
        self.assertEqual((t["zh"].get("status.background"), t["en"].get("status.background")),
                         ("后台在跑", "Working in background"))
        self.assertEqual((t["zh"].get("status.idle"), t["en"].get("status.idle")), ("空闲", "Idle"))

    def test_waiting_words_stay(self):
        t = texts()
        self.assertEqual((t["zh"]["status.waiting"], t["zh"]["status.waiting_reply"]), ("等你", "等你回话"))


class TestPageGovernor(unittest.TestCase):
    def test_background_has_its_own_class(self):
        self.assertEqual(gov_results()["status"]["a"], ["bgrun", "后台在跑"])

    def test_other_states_as_before(self):
        r = gov_results()["status"]
        self.assertEqual([r["b"], r["c"], r["d"], r["e"], r["gone"]],
                         [["gov", "等你"], ["gov", "空闲"], ["gov", "在忙"], ["gov", "未知"], ["gov", "不在"]])

    def test_row_text_is_the_status_text(self):
        r = gov_results()
        for terr, pair in r["status"].items():
            with self.subTest(terr=terr):
                self.assertEqual(r["text"][terr], pair[1])

    def test_bubble_only_when_waiting(self):
        r = gov_results()["talk"]
        self.assertEqual(r["b"], "等你回话…")
        for terr in ("a", "c", "d", "e", "gone"):
            with self.subTest(terr=terr):
                self.assertEqual(r[terr], "")

    def test_rail_row(self):
        r = gov_results()
        self.assertIn('class="sdot st-bgrun"', r["row"])
        self.assertIn('class="chip bgrun">后台在跑<', r["row"])
        self.assertIn('class="sdot st-gov"', r["rowWaiting"])
        self.assertIn('class="chip gov">等你<', r["rowWaiting"])

    def test_panel_pill_uses_it_too(self):
        script = tp.inline_script()
        self.assertNotIn('<span class="pill gov">${govRowText(', script)
        self.assertGreaterEqual(len(re.findall(r"govRowStatus\(", script)), 3,
                                "govRowStatus(): its definition, the rail row and the governor panel")


class TestPageCitizen(unittest.TestCase):
    def results(self):
        if "citizen" not in _CACHE:
            prelude = tp.constants_prelude() + "\n" + "var STATE = " + tp.const_object("STATE") + ";"
            _CACHE["citizen"] = tp.run_node(CITIZEN_JS, {"prelude": prelude, "fns": need("citizenStatus")})
        return _CACHE["citizen"]

    def test_status(self):
        r = self.results()
        self.assertEqual(r["waiting"], ["you", "等你回话"])
        self.assertEqual(r["bgrun"], ["bgrun", "后台在跑"])
        self.assertEqual(r["idle"], ["walk", "空闲"])
        self.assertNotIn(r["plain"][1], ("等你回话", "后台在跑", "空闲"))

    def test_an_open_ask_wins(self):
        r = self.results()
        self.assertEqual(r["idleAsk"], ["you", "等你批"])
        self.assertEqual(r["bgrunAsk"], ["you", "等你回答"])

    def test_events_move_a_person_between_states(self):
        r = sim_results()
        plain = r["snap"][0]
        self.assertNotIn(plain[1], ("等你回话", "后台在跑", "空闲"))
        self.assertEqual(r["steps"], [["bgrun", "后台在跑"], ["walk", "空闲"], ["you", "等你回话"], plain,
                                      ["walk", "空闲"], ["bgrun", "后台在跑"], plain])
        self.assertEqual(r["moved"], 0, "a status event never sends the person anywhere")

    def test_snapshot_places_the_same_way(self):
        r = sim_results()
        self.assertEqual(r["snap"][1:], [["bgrun", "后台在跑"], ["walk", "空闲"], ["you", "等你回话"]])

    def test_governor_events_and_snapshot(self):
        r = sim_results()
        self.assertEqual(r["govSnap"], [["bgrun", "后台在跑"], ""])
        self.assertEqual(r["govWaiting"], [["gov", "等你"], "等你回话…"])
        self.assertEqual(r["govBg"], [["bgrun", "后台在跑"], ""])

    def test_another_members_people_get_the_same_cases(self):
        remote = tp.function_source("applyRemote") or ""
        for kind in ("waiting", "background", "idle", "resume"):
            with self.subTest(kind=kind):
                self.assertIn("'%s'" % kind, remote)
        for flag in ("bgrun", "idle"):
            with self.subTest(flag=flag):
                self.assertRegex(remote, r"\.%s\b" % flag)


class TestPageColour(unittest.TestCase):
    def test_violet_in_every_theme(self):
        style = tp.style()
        for var in ("--bgrun-bg", "--bgrun-ink"):
            with self.subTest(var=var):
                self.assertEqual(len(re.findall(re.escape(var) + r"\s*:\s*#[0-9A-Fa-f]{6}", style)), 3,
                                 "%s is set for light, the dark media query and the dark theme" % var)

    def test_chip_pill_and_dot(self):
        style = tp.style()
        for selector in (r"\.chip\.bgrun", r"\.pill\.bgrun"):
            with self.subTest(selector=selector):
                self.assertRegex(style, selector + r"\{background:var\(--bgrun-bg\);color:var\(--bgrun-ink\)\}")
        self.assertRegex(style, r"\.sdot\.st-bgrun\{background:#[0-9A-Fa-f]{6}\}")

    def test_not_an_existing_colour(self):
        style = tp.style()
        m = re.search(r":root\{.*?--bgrun-bg\s*:\s*(#[0-9A-Fa-f]{6}).*?--bgrun-ink\s*:\s*(#[0-9A-Fa-f]{6})", style, re.S)
        self.assertIsNotNone(m, "--bgrun-bg and --bgrun-ink in :root")
        taken = {"#E1ECFF", "#3160B5", "#FFE1E8", "#C2345A", "#DAF5E8", "#1E8657", "#EDEFF7", "#5F6488",
                 "#FFF0C7", "#8A6000"}
        self.assertNotIn(m.group(1).upper(), taken)
        self.assertNotIn(m.group(2).upper(), taken)


# ------------------------------------------------------- requirements

class TestRequirementLines(unittest.TestCase):
    def test_status_section(self):
        with open(os.path.join(ROOT, "requirements", "city.md"), encoding="utf-8") as fh:
            text = fh.read()
        m = re.search(r"^## Status\n(.*?)(?=^## )", text, re.M | re.S)
        self.assertIsNotNone(m, "requirements/city.md has a Status section")
        body = m.group(1)
        for word in ("等你", "后台在跑", "空闲", "要你决定", "What to decide", "QUESTION:", "background_tasks",
                     "idle_prompt", "StopNote"):
            with self.subTest(word=word):
                self.assertIn(word, body)


if __name__ == "__main__":
    unittest.main()
