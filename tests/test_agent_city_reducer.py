"""Failing tests for the Reducer in bin/agent_city.py.

The Reducer turns hook lines (written by bin/agent-city-hook.sh) into city
events the page animates. It is pure: no files, no clock, no network.

CONTRACT

  Reducer(max_agents=40, done_ttl=600)
    .feed(raw, now) -> list of city events (dicts), in order
    .snapshot()     -> {"gov": {"state": str},
                        "agents": [{"id","role","label","task","stuck","done",
                                    "tools": {"Edit","Write","Bash","Read","Other"}}]}

  raw is one hook line: keys ev sid aid at tool nt proj role desc sub q.
  Anything that is not a dict, or has no "ev", gives [] and never raises.
  Non-string values count as "".

  Memory stays bounded, whatever comes in:
    .pending   dict sid -> list of queued (sub, desc), at most 20 per session
    .sessions  dict sid -> what the reducer knows about that session;
               SessionEnd forgets it

  City events, exactly these keys:
    {"type":"spawn",  "id","role","label","task"}
    {"type":"tool",   "id","tool"}          tool in Edit Write Bash Read Other
    {"type":"stuck",  "id","question","tool"}
    {"type":"answer", "id","ok"}            ok is True or False
    {"type":"done",   "id"}
    {"type":"leave",  "id"}
    {"type":"gov",    "state"}              busy | waiting | idle

  Who is who
    subagent        id = aid. role = at when at is task-manager, worker,
                    fast-lane-deputy or merge-deputy, else "other".
                    label = at (max 30 chars).
    session main    no aid. id = "s:" + sid.
      governor      the first session with role "" is the governor. Its main
                    agent is never a citizen, it only sends gov events.
                    Governor gone (SessionEnd) -> the next role-less session
                    that shows up becomes governor.
      citizen       role != "" -> role as above, label = role.
                    role == "" but a governor already exists -> role
                    "task-manager", label "session".
                    task = proj, or the label when proj is "".

  Rules
    Agent/Task PreToolUse (desc, sub) waits in a queue for its session.
    SubagentStart takes the first queued item with sub == at, else the first
    with sub == "", else task = at. task max 40 chars.
    Any event from an unknown subagent spawns it first (it started before
    the city did). SubagentStop from an unknown one is ignored.
    PostToolUse -> tool, sorted: Edit MultiEdit NotebookEdit -> Edit,
      Write -> Write, Bash -> Bash, Read Grep Glob LS WebFetch WebSearch -> Read,
      everything else -> Other.
    PermissionRequest -> stuck (question "", tool = tool).
    AskUserQuestion PreToolUse -> stuck (question = q, max 60 chars).
    Notification permission_prompt or idle_prompt from a citizen session -> stuck.
    Already stuck -> no second stuck event.
    Stuck, then any PostToolUse or UserPromptSubmit from it -> answer ok True
      first, then the rest. PermissionDenied -> answer ok False.
    SubagentStop -> done. Anything from a done agent is ignored.
    Governor: PostToolUse / PreToolUse / UserPromptSubmit -> busy,
      Notification permission_prompt / idle_prompt -> waiting, Stop -> idle.
      A gov event is sent only when the state changes.
    SessionEnd -> done (if not yet) and leave for the session's citizen and
      every subagent of that session; for the governor session: gov idle.
    More than max_agents alive -> the oldest (by last event) leave.
    Done longer than done_ttl seconds -> leave on the next feed.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import agent_city  # noqa: E402

EVENT_KEYS = {
    "spawn": {"type", "id", "role", "label", "task"},
    "tool": {"type", "id", "tool"},
    "stuck": {"type", "id", "question", "tool"},
    "answer": {"type", "id", "ok"},
    "done": {"type", "id"},
    "leave": {"type", "id"},
    "gov": {"type", "state"},
}


def R(ev, sid="s1", aid="", at="", tool="", nt="", proj="shop", role="", desc="", sub="", q=""):
    return {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": nt,
            "proj": proj, "role": role, "desc": desc, "sub": sub, "q": q}


class Case(unittest.TestCase):
    def setUp(self):
        self.r = agent_city.Reducer()
        self.t = 1000.0
        self.all = []

    def feed(self, raw, dt=1.0):
        self.t += dt
        out = self.r.feed(raw, self.t)
        self.assertIsInstance(out, list)
        for event in out:
            self.assertIn(event.get("type"), EVENT_KEYS, event)
            self.assertEqual(set(event), EVENT_KEYS[event["type"]], event)
        self.all.extend(out)
        return out

    def types(self, events):
        return [e["type"] for e in events]

    def govern(self, sid="s1"):
        """Make sid the governor session."""
        self.feed(R("UserPromptSubmit", sid=sid))

    def spawn(self, aid="a1", at="worker", sid="s1"):
        return self.feed(R("SubagentStart", sid=sid, aid=aid, at=at))


class TestSpawn(Case):
    def test_agent_description_names_the_task(self):
        self.govern()
        self.assertEqual(self.feed(R("PreToolUse", tool="Agent", desc="设置页表单", sub="worker")), [])
        out = self.spawn()
        self.assertEqual(out, [{"type": "spawn", "id": "a1", "role": "worker",
                                "label": "worker", "task": "设置页表单"}])

    def test_no_description_task_is_the_type(self):
        out = self.spawn(at="merge-deputy")
        self.assertEqual(out[0]["task"], "merge-deputy")
        self.assertEqual(out[0]["role"], "merge-deputy")

    def test_queue_matches_by_type_then_blank_then_nothing(self):
        self.feed(R("PreToolUse", tool="Agent", desc="tests", sub="task-manager"))
        self.feed(R("PreToolUse", tool="Task", desc="look around", sub=""))
        self.feed(R("PreToolUse", tool="Agent", desc="form", sub="worker"))
        self.assertEqual(self.spawn("a1", "worker")[0]["task"], "form")
        self.assertEqual(self.spawn("a2", "Explore")[0]["task"], "look around")
        self.assertEqual(self.spawn("a3", "task-manager")[0]["task"], "tests")
        self.assertEqual(self.spawn("a4", "worker")[0]["task"], "worker")

    def test_queue_is_per_session(self):
        self.feed(R("PreToolUse", sid="s2", tool="Agent", desc="other session", sub="worker"))
        self.assertEqual(self.spawn("a1", "worker", sid="s1")[0]["task"], "worker")

    def test_unknown_types_are_other(self):
        for aid, at in (("a1", "Explore"), ("a2", "general-purpose"), ("a3", "Plan")):
            with self.subTest(at=at):
                out = self.spawn(aid, at)
                self.assertEqual(out[0]["role"], "other")
                self.assertEqual(out[0]["label"], at)

    def test_the_four_pipeline_roles(self):
        for i, at in enumerate(("task-manager", "worker", "fast-lane-deputy", "merge-deputy")):
            with self.subTest(at=at):
                self.assertEqual(self.spawn("a%d" % i, at)[0]["role"], at)

    def test_long_names_are_cut(self):
        self.feed(R("PreToolUse", tool="Agent", desc="x" * 100, sub=""))
        out = self.spawn("a1", "y" * 100)
        self.assertLessEqual(len(out[0]["task"]), 40)
        self.assertLessEqual(len(out[0]["label"]), 30)

    def test_unknown_subagent_is_spawned_before_its_first_tool(self):
        out = self.feed(R("PostToolUse", aid="a9", at="worker", tool="Edit"))
        self.assertEqual(self.types(out), ["spawn", "tool"])
        self.assertEqual(out[0]["id"], "a9")

    def test_second_start_for_the_same_agent_does_not_spawn_twice(self):
        self.spawn()
        self.assertEqual(self.spawn(), [])


class TestTools(Case):
    def test_tool_kinds(self):
        self.spawn()
        cases = {"Edit": "Edit", "MultiEdit": "Edit", "NotebookEdit": "Edit", "Write": "Write",
                 "Bash": "Bash", "Read": "Read", "Grep": "Read", "Glob": "Read", "LS": "Read",
                 "WebFetch": "Read", "WebSearch": "Read", "TodoWrite": "Other",
                 "mcp__github__create_pull_request": "Other", "Agent": "Other"}
        for tool, kind in cases.items():
            with self.subTest(tool=tool):
                out = self.feed(R("PostToolUse", aid="a1", at="worker", tool=tool))
                self.assertEqual(out, [{"type": "tool", "id": "a1", "tool": kind}])

    def test_pre_tool_use_of_a_normal_tool_says_nothing(self):
        self.spawn()
        self.assertEqual(self.feed(R("PreToolUse", aid="a1", at="worker", tool="Agent",
                                     desc="nested", sub="worker")), [])

    def test_snapshot_counts_tools(self):
        self.spawn()
        for tool in ("Edit", "Edit", "Bash", "Grep"):
            self.feed(R("PostToolUse", aid="a1", at="worker", tool=tool))
        agent = self.r.snapshot()["agents"][0]
        self.assertEqual(agent["tools"], {"Edit": 2, "Write": 0, "Bash": 1, "Read": 1, "Other": 0})


class TestStuck(Case):
    def test_permission_request_then_the_tool_runs(self):
        self.spawn()
        out = self.feed(R("PermissionRequest", aid="a1", at="worker", tool="Bash"))
        self.assertEqual(out, [{"type": "stuck", "id": "a1", "question": "", "tool": "Bash"}])
        out = self.feed(R("PostToolUse", aid="a1", at="worker", tool="Bash"))
        self.assertEqual(out, [{"type": "answer", "id": "a1", "ok": True},
                               {"type": "tool", "id": "a1", "tool": "Bash"}])

    def test_permission_denied(self):
        self.spawn()
        self.feed(R("PermissionRequest", aid="a1", at="worker", tool="Bash"))
        out = self.feed(R("PermissionDenied", aid="a1", at="worker", tool="Bash"))
        self.assertEqual(out, [{"type": "answer", "id": "a1", "ok": False}])
        self.assertFalse(self.r.snapshot()["agents"][0]["stuck"])

    def test_ask_user_question(self):
        self.spawn()
        out = self.feed(R("PreToolUse", aid="a1", at="worker", tool="AskUserQuestion", q="API 路径用哪个？"))
        self.assertEqual(out, [{"type": "stuck", "id": "a1", "question": "API 路径用哪个？",
                                "tool": "AskUserQuestion"}])
        out = self.feed(R("PostToolUse", aid="a1", at="worker", tool="AskUserQuestion"))
        self.assertEqual(self.types(out), ["answer", "tool"])

    def test_long_question_is_cut(self):
        self.spawn()
        out = self.feed(R("PreToolUse", aid="a1", at="worker", tool="AskUserQuestion", q="q" * 200))
        self.assertLessEqual(len(out[0]["question"]), 60)

    def test_no_second_stuck_while_stuck(self):
        self.spawn()
        self.feed(R("PermissionRequest", aid="a1", at="worker", tool="Bash"))
        self.assertEqual(self.feed(R("PermissionRequest", aid="a1", at="worker", tool="Bash")), [])

    def test_snapshot_shows_stuck(self):
        self.spawn()
        self.feed(R("PermissionRequest", aid="a1", at="worker", tool="Bash"))
        self.assertTrue(self.r.snapshot()["agents"][0]["stuck"])


class TestDone(Case):
    def test_subagent_stop_is_done(self):
        self.spawn()
        self.assertEqual(self.feed(R("SubagentStop", aid="a1", at="worker")),
                         [{"type": "done", "id": "a1"}])

    def test_second_stop_and_later_tools_are_ignored(self):
        self.spawn()
        self.feed(R("SubagentStop", aid="a1", at="worker"))
        self.assertEqual(self.feed(R("SubagentStop", aid="a1", at="worker")), [])
        self.assertEqual(self.feed(R("PostToolUse", aid="a1", at="worker", tool="Edit")), [])

    def test_stop_from_an_unknown_agent_is_ignored(self):
        self.assertEqual(self.feed(R("SubagentStop", aid="zz", at="worker")), [])

    def test_done_agents_leave_after_the_ttl(self):
        self.r = agent_city.Reducer(done_ttl=60)
        self.spawn()
        self.feed(R("SubagentStop", aid="a1", at="worker"))
        self.assertEqual(self.feed(R("Stop", sid="s9", role="worker"), dt=30), [
            {"type": "spawn", "id": "s:s9", "role": "worker", "label": "worker", "task": "shop"}])
        out = self.feed(R("Stop", sid="s9", role="worker"), dt=40)
        self.assertIn({"type": "leave", "id": "a1"}, out)
        self.assertEqual([a["id"] for a in self.r.snapshot()["agents"]], ["s:s9"])


class TestSessions(Case):
    def test_first_plain_session_is_the_governor(self):
        out = self.feed(R("UserPromptSubmit", sid="main"))
        self.assertEqual(out, [{"type": "gov", "state": "busy"}])
        self.assertEqual(self.r.snapshot()["agents"], [])

    def test_governor_states_change_only_on_change(self):
        self.govern("main")
        self.assertEqual(self.feed(R("PostToolUse", sid="main", tool="Read")), [])
        self.assertEqual(self.feed(R("Notification", sid="main", nt="idle_prompt")),
                         [{"type": "gov", "state": "waiting"}])
        self.assertEqual(self.feed(R("Notification", sid="main", nt="permission_prompt")), [])
        self.assertEqual(self.feed(R("PreToolUse", sid="main", tool="Agent", desc="d", sub="worker")),
                         [{"type": "gov", "state": "busy"}])
        self.assertEqual(self.feed(R("Stop", sid="main")), [{"type": "gov", "state": "idle"}])
        self.assertEqual(self.r.snapshot()["gov"], {"state": "idle"})

    def test_other_notifications_do_nothing(self):
        self.govern("main")
        self.assertEqual(self.feed(R("Notification", sid="main", nt="auth_success")), [])

    def test_session_with_a_role_is_a_citizen(self):
        self.govern("main")
        out = self.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Write", proj="shop-wt"))
        self.assertEqual(out, [
            {"type": "spawn", "id": "s:tm1", "role": "task-manager", "label": "task-manager", "task": "shop-wt"},
            {"type": "tool", "id": "s:tm1", "tool": "Write"}])

    def test_second_plain_session_is_a_task_manager_citizen(self):
        self.govern("main")
        out = self.feed(R("UserPromptSubmit", sid="other", proj=""))
        self.assertEqual(out, [{"type": "spawn", "id": "s:other", "role": "task-manager",
                                "label": "session", "task": "session"}])

    def test_citizen_session_gets_stuck_and_answered(self):
        self.govern("main")
        self.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Write"))
        out = self.feed(R("Notification", sid="tm1", role="task-manager", nt="permission_prompt"))
        self.assertEqual(out, [{"type": "stuck", "id": "s:tm1", "question": "", "tool": ""}])
        out = self.feed(R("UserPromptSubmit", sid="tm1", role="task-manager"))
        self.assertEqual(out, [{"type": "answer", "id": "s:tm1", "ok": True}])

    def test_citizen_session_stop_is_not_done(self):
        self.govern("main")
        self.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Write"))
        self.assertEqual(self.feed(R("Stop", sid="tm1", role="task-manager")), [])

    def test_session_end_sends_everyone_home(self):
        self.govern("main")
        self.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Write"))
        self.feed(R("SubagentStart", sid="tm1", aid="w1", at="worker"))
        self.feed(R("SubagentStart", sid="main", aid="w2", at="worker"))
        out = self.feed(R("SessionEnd", sid="tm1", role="task-manager"))
        self.assertIn({"type": "done", "id": "s:tm1"}, out)
        self.assertIn({"type": "leave", "id": "s:tm1"}, out)
        self.assertIn({"type": "done", "id": "w1"}, out)
        self.assertIn({"type": "leave", "id": "w1"}, out)
        self.assertNotIn("w2", [e.get("id") for e in out])
        self.assertEqual([a["id"] for a in self.r.snapshot()["agents"]], ["w2"])

    def test_governor_session_end_frees_the_seat(self):
        self.govern("main")
        self.feed(R("SubagentStart", sid="main", aid="w2", at="worker"))
        out = self.feed(R("SessionEnd", sid="main"))
        self.assertIn({"type": "gov", "state": "idle"}, out)
        self.assertIn({"type": "leave", "id": "w2"}, out)
        self.assertEqual(self.feed(R("UserPromptSubmit", sid="new")), [{"type": "gov", "state": "busy"}])


class TestBounds(Case):
    def test_oldest_leave_past_the_cap(self):
        self.r = agent_city.Reducer(max_agents=40)
        for i in range(60):
            self.spawn("a%d" % i)
        leaves = [e["id"] for e in self.all if e["type"] == "leave"]
        self.assertEqual(leaves, ["a%d" % i for i in range(20)])
        self.assertEqual(len(self.r.snapshot()["agents"]), 40)

    def test_a_busy_old_agent_is_kept(self):
        self.r = agent_city.Reducer(max_agents=3)
        self.spawn("a0")
        self.spawn("a1")
        self.spawn("a2")
        self.feed(R("PostToolUse", aid="a0", at="worker", tool="Edit"))
        self.spawn("a3")
        self.assertIn({"type": "leave", "id": "a1"}, self.all)
        self.assertNotIn({"type": "leave", "id": "a0"}, self.all)

    def test_queue_does_not_grow_forever(self):
        for i in range(5000):
            self.r.feed(R("PreToolUse", tool="Agent", desc="d%d" % i, sub="nobody"), float(i))
        self.assertLessEqual(len(json.dumps(self.r.snapshot())), 2000)
        self.assertLess(sum(len(q) for q in self.r.pending.values()), 100)

    def test_many_sessions_do_not_pile_up(self):
        for i in range(500):
            self.r.feed(R("SessionEnd", sid="s%d" % i, role="worker"), float(i))
        self.assertLess(len(self.r.sessions), 50)


class TestSafety(Case):
    def test_garbage_gives_nothing(self):
        for raw in (None, 3, "x", [], {}, {"sid": "s1"}, {"ev": None}, {"ev": "PostToolUse", "aid": 5}):
            with self.subTest(raw=raw):
                self.assertEqual(self.r.feed(raw, 1.0), [])

    def test_unknown_event_gives_nothing(self):
        self.assertEqual(self.feed(R("FileChanged")), [])

    def test_extra_raw_keys_never_leak(self):
        raw = R("PreToolUse", tool="Agent", desc="d", sub="worker")
        raw["secret"] = "SECRET_X"
        self.feed(raw)
        raw = R("SubagentStart", aid="a1", at="worker")
        raw["prompt"] = "SECRET_Y"
        self.feed(raw)
        text = json.dumps(self.all) + json.dumps(self.r.snapshot())
        self.assertNotIn("SECRET", text)

    def test_snapshot_shape(self):
        self.spawn()
        snap = self.r.snapshot()
        self.assertEqual(set(snap), {"gov", "agents"})
        self.assertEqual(set(snap["agents"][0]),
                         {"id", "role", "label", "task", "stuck", "done", "tools"})
        json.dumps(snap)


if __name__ == "__main__":
    unittest.main()
