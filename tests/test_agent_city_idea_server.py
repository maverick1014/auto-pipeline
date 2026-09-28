"""Failing tests for idea-city, server side (bin/agent_city.py, bin/agent_city_relay.py,
bin/agent-city-hook.sh, bin/agent-city.sh). The page side is in
tests/test_agent_city_idea_page.py.

CONTRACT

  C1 English too (language from agent.conf, zh default)
    serve --lang zh|en (default zh; anything else counts as zh). The page holds
    the placeholder __CITY_LANG__ (const LANG = '__CITY_LANG__'); serve replaces it
    with the language, like __CITY_TOKEN__ / __CITY_ASSET_V__.
    bin/agent-city.sh passes --lang "$language" (agent.conf key language, read like
    every other key: project agent.conf, else the plugin template).
    Text the server makes that the page shows follows --lang:
      CityState(..., lang="en"): a governor's building has by "governor" (zh: 总督);
      the world notices (dropped "dir:" territories, unreadable world.json) are
      English (load_world(path, lang="en")) -- no CJK character in them.
      agent_city_relay._default_label(lang) in a cloud session: "cloud" for en,
      "云端" for zh (default zh).

  C3 one governor per repo, for other members too
    RemoteCity keeps one Reducer per (sender device, rid), not one per device: a
    member's role-less session in a second repo is that repo's governor, not a
    citizen. A remote gov id is "r:<dev>:gov:<terr>" (terr = the local territory of
    that rid), so two repos of one device never share an id; the same holds in
    remote_snapshot "govs" and in the "present": false sent when a device is
    forgotten. Person ids stay "r:<dev>:<id>".

  C4 one set of file-kind rules: the server's
    The hook no longer classifies paths: its line has no "kind" key (16 keys,
    "file" still last). The server decides the building from "file" with
    file_kind(file, <that repo's rules.conf rules>) and this map:
      rules -> tower, beauty -> shop, infra -> workshop, knowledge -> library,
      build -> house; None (vendor, lock, binary, not code) -> no building.
    A line with a "file" ignores any "kind" it carries. A line with no "file" but
    an old hook kind (test ui script doc other) still builds by the old map (old
    events.jsonl lines). The relay wire line carries no "kind" (nobody reads it).

  C5 idle_prompt is not a question
    A citizen's Notification idle_prompt -> {"type": "waiting", "id"} once (never
    "stuck"); its next PreToolUse / PostToolUse / UserPromptSubmit ->
    {"type": "resume", "id"} first, then the usual events. permission_prompt stays
    "stuck". Reducer.snapshot() agents gain "waiting": bool. A waiting citizen never
    starts a chain relay and never becomes an ask. The governor keeps its
    "waiting" gov state as before.

  C16 the chain for other members' people
    The relay wire line keeps "ask" (the flag only, "q" or ""). RemoteCity replays
    the chain rules of the local city (CityState._process_chain) per (device, rid),
    ids wrapped "r:<dev>:<id>" and each event wrapped like any remote event:
      a subagent SubagentStop with ask "q" whose session is a task-manager citizen
        (a lead) -> {"type": "relay", "id": <worker>, "to": "lead", "lead": <lead>},
        before its "done";
      ... whose session is that repo's governor -> relay to "governor", lead "";
      a lead's PostToolUse SendMessage with ask "q" -> relay lead -> "governor";
      the governor's SendMessage -> relay_end (by "governor") for open lead and
        helper relays;
      a lead's SendMessage without ask, or its Agent/Task PreToolUse -> relay_end
        (by "lead") for its waiting workers;
      a person that leaves -> relay_end by "leave"; RELAY_TIMEOUT_SEC -> "timeout".
    The relay/relay_end events are wrapped {"type": "remote", ..., "ev": {...}}.
"""

import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
import agent_city_relay as acr  # noqa: E402
import test_agent_city_quality as tq  # noqa: E402
from test_agent_city_server import ServerCase  # noqa: E402

CJK = re.compile(r"[㐀-鿿＀-￯　-〿]")


def R(ev, sid="s", aid="", at="", tool="", nt="", role="", ask="", **kw):
    line = {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": nt, "proj": "p",
            "role": role, "desc": "", "sub": "", "q": "", "ask": ask}
    line.update(kw)
    return line


# --------------------------------------------------------------------- C1

class TestLangFlag(ServerCase):
    def test_default_is_zh(self):
        self.start()
        body = self.get("/")[2].decode("utf-8")
        self.assertNotIn("__CITY_LANG__", body)
        self.assertRegex(body, r"const LANG = 'zh'")

    def test_en(self):
        self.start("--idle-sec", "60", "--lang", "en")
        self.assertRegex(self.get("/")[2].decode("utf-8"), r"const LANG = 'en'")

    def test_unknown_counts_as_zh(self):
        self.start("--idle-sec", "60", "--lang", "fr")
        self.assertRegex(self.get("/")[2].decode("utf-8"), r"const LANG = 'zh'")


class TestLangFromConf(unittest.TestCase):
    def test_start_passes_language(self):
        with open(os.path.join(BIN, "agent-city.sh"), encoding="utf-8") as fh:
            text = fh.read()
        serve = text[text.index('"$SERVER" serve'):]
        serve = serve[:serve.index("&\n")]
        self.assertIn('--lang "$language"', serve)  # conf_read sets every agent.conf key, language too


class TestServerTextFollowsLang(tq.BuildCase):
    def test_governor_builds_by_governor_in_en(self):
        # "tm" (setUp) is already this repo's governor
        self.st.lang = "en"
        self.put("src/g.py", "x = 1\n")
        self.st.feed_line(self.line("tm", file="src/g.py"), 1000.0)
        ev = [e for e in tq.drain(self.client) if e["type"] == "build"]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["by"], "governor")

    def test_governor_builds_by_zongdu_in_zh(self):
        self.put("src/g.py", "x = 1\n")
        self.st.feed_line(self.line("tm", file="src/g.py"), 1000.0)
        ev = [e for e in tq.drain(self.client) if e["type"] == "build"]
        self.assertEqual(ev[0]["by"], "总督")

    def test_cityState_takes_lang(self):
        st = ac.CityState(decisions_path=os.path.join(self.base, "d2.jsonl"),
                          world_path=os.path.join(self.base, "w2.json"), plans=ac.load_plans(),
                          count_fn=lambda i: 0, balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}},
                          start_repo=self.ident, lang="en")
        self.assertEqual(st.lang, "en")


class TestNoticesFollowLang(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_lang_")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_unreadable_world_notice_en(self):
        path = os.path.join(self.base, "world.json")
        with open(path, "w") as fh:
            fh.write("{not json")
        _world, notice = ac.load_world(path, lang="en")
        self.assertTrue(notice)
        self.assertIsNone(CJK.search(notice), notice)

    def test_unreadable_world_notice_zh_default(self):
        path = os.path.join(self.base, "world.json")
        with open(path, "w") as fh:
            fh.write("{not json")
        _world, notice = ac.load_world(path)
        self.assertIsNotNone(CJK.search(notice), notice)

    def test_cloud_label(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_REMOTE": "1"}):
            self.assertEqual(acr._default_label("en"), "cloud")
            self.assertEqual(acr._default_label("zh"), "云端")
            self.assertEqual(acr._default_label(), "云端")


# --------------------------------------------------------------------- C4

class TestServerDecidesTheBuilding(tq.BuildCase):
    def built(self, rel, kind="", aid="w1", text="x = 1\n"):
        self.put(rel, text)
        self.st.feed_line(self.line("tm", aid=aid, kind=kind, file=rel), 1000.0)
        ev = [e for e in tq.drain(self.client) if e["type"] == "build"]
        return ev[0]["btype"] if ev else None

    def test_server_kinds_map_to_buildings(self):
        table = [("tests/test_a.py", "tower"), ("web/app.css", "shop"), ("ci.yml", "workshop"),
                 ("docs/guide.md", "library"), ("bin/agent_city.py", "house")]
        for n, (rel, btype) in enumerate(table):
            with self.subTest(path=rel):
                self.assertEqual(self.built(rel, aid="w%d" % n), btype)

    def test_the_line_kind_is_ignored_when_a_file_is_there(self):
        self.assertEqual(self.built("src/a.py", kind="test"), "house")

    def test_not_code_builds_nothing(self):
        self.assertIsNone(self.built("node_modules/x/index.js", aid="w1"))
        self.assertIsNone(self.built("notes.txt", aid="w2"))

    def test_repo_rules_decide(self):
        rules = os.path.join(self.base, "rules", ac.repo_name(self.ident) + ".conf")
        os.makedirs(os.path.dirname(rules), exist_ok=True)
        with open(rules, "w") as fh:
            fh.write("src/checks/*.py = rules\n")
        self.assertEqual(self.built("src/checks/c.py"), "tower")

    def test_an_old_line_with_only_a_kind_still_builds(self):
        self.st.feed_line(self.line("tm", aid="w1", kind="ui", file=""), 1000.0)
        ev = [e for e in tq.drain(self.client) if e["type"] == "build"]
        self.assertEqual([e["btype"] for e in ev], ["shop"])


class TestWireHasNoKind(unittest.TestCase):
    def test_kind_dropped_ask_kept(self):
        self.assertNotIn("kind", acr._KEPT_LINE_FIELDS)
        self.assertIn("ask", acr._KEPT_LINE_FIELDS)
        wire = acr.to_wire(dict(R("SubagentStop", aid="a1", at="worker", ask="q"), kind="test"),
                           {"rid": "r", "br": "b", "who": "w", "dev": "d"})
        self.assertNotIn("kind", wire)
        self.assertEqual(wire["ask"], "q")


class TestHookHasNoPathRules(unittest.TestCase):
    def test_no_classify_path(self):
        with open(os.path.join(BIN, "agent-city-hook.sh"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("classify_path", text)
        self.assertNotIn('"kind":', text)


# --------------------------------------------------------------------- C5

class TestIdleIsNotAQuestion(unittest.TestCase):
    def setUp(self):
        self.r = ac.Reducer()
        self.r.feed(R("UserPromptSubmit", sid="main"), 1.0)
        self.r.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Write"), 1.0)

    def test_idle_prompt_is_waiting_once(self):
        out = self.r.feed(R("Notification", sid="tm1", role="task-manager", nt="idle_prompt"), 2.0)
        self.assertEqual(out, [{"type": "waiting", "id": "s:tm1"}])
        self.assertEqual(self.r.feed(R("Notification", sid="tm1", role="task-manager", nt="idle_prompt"), 3.0), [])
        a = [a for a in self.r.snapshot()["agents"] if a["id"] == "s:tm1"][0]
        self.assertEqual((a["waiting"], a["stuck"]), (True, False))

    def test_resume_comes_first(self):
        self.r.feed(R("Notification", sid="tm1", role="task-manager", nt="idle_prompt"), 2.0)
        out = self.r.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Edit"), 3.0)
        self.assertEqual(out, [{"type": "resume", "id": "s:tm1"}, {"type": "tool", "id": "s:tm1", "tool": "Edit"}])
        a = [a for a in self.r.snapshot()["agents"] if a["id"] == "s:tm1"][0]
        self.assertFalse(a["waiting"])

    def test_prompt_resumes(self):
        self.r.feed(R("Notification", sid="tm1", role="task-manager", nt="idle_prompt"), 2.0)
        self.assertEqual(self.r.feed(R("UserPromptSubmit", sid="tm1", role="task-manager"), 3.0),
                         [{"type": "resume", "id": "s:tm1"}])

    def test_permission_prompt_is_still_stuck(self):
        out = self.r.feed(R("Notification", sid="tm1", role="task-manager", nt="permission_prompt"), 2.0)
        self.assertEqual(out, [{"type": "stuck", "id": "s:tm1", "question": "", "tool": ""}])

    def test_governor_unchanged(self):
        self.assertEqual(self.r.feed(R("Notification", sid="main", nt="idle_prompt"), 2.0),
                         [{"type": "gov", "state": "waiting"}])

    def test_every_snapshot_agent_has_waiting(self):
        for a in self.r.snapshot()["agents"]:
            self.assertIn("waiting", a)


class TestIdleInTheCity(tq.BuildCase):
    def test_no_relay_no_ask_no_stuck(self):
        self.st.feed_line(dict(self.line("tm1"), role="task-manager", tool="Write", file=""), 1000.0)
        tq.drain(self.client)
        self.st.feed_line(dict(self.line("tm1"), ev="Notification", nt="idle_prompt", role="task-manager",
                               tool="", file=""), 1001.0)
        types = [e["type"] for e in tq.drain(self.client)]
        self.assertIn("waiting", types)
        for bad in ("stuck", "relay", "ask"):
            self.assertNotIn(bad, types)


# ----------------------------------------------------------------- C3, C16

class StubHub:
    def __init__(self, repos):
        self.repos = repos
        self.items = []

    def push(self, dev, line):
        self.items.append({"dev": dev, "line": line})

    def tick(self):
        out, self.items = self.items, []
        return out

    def repo_for(self, rid):
        return self.repos.get(rid)

    def joined(self):
        return True

    def status(self):
        return {"joined": True, "teams": [{"host": "relay.example", "state": "ok", "queued": 0,
                                            "rids": list(self.repos)}]}

    def identity(self):
        return {"who": "me", "device": "mac"}


class RemoteCase(unittest.TestCase):
    RIDS = {"github.com/acme/shop": "/code/shop/.git", "github.com/acme/pay": "/code/pay/.git"}

    def setUp(self):
        self.hub = StubHub(self.RIDS)
        self.rc = ac.RemoteCity(self.hub, remote_ttl_sec=600.0)
        self.now = 100.0

    def terr(self, rid):
        return ac.territory_id(self.RIDS[rid])

    def send(self, dev="dev-bo", rid="github.com/acme/shop", **line):
        wire = {"ev": "", "sid": "", "aid": "", "at": "", "tool": "", "nt": "", "role": "", "desc": "",
                "sub": "", "klen": "", "ask": "", "rid": rid, "br": "main", "who": "Bo", "dev": "bo-mac"}
        wire.update(line)
        self.hub.push(dev, wire)
        self.now += 1
        return [e for e in self.rc.poll(self.now) if e["type"] == "remote"]

    def inner(self, events, etype):
        return [e["ev"] for e in events if e["ev"].get("type") == etype]


class TestRemoteGovernorPerRepo(RemoteCase):
    def test_two_repos_two_governors(self):
        a = self.inner(self.send(ev="UserPromptSubmit", sid="m1"), "gov")
        b = self.send(rid="github.com/acme/pay", ev="UserPromptSubmit", sid="m2")
        self.assertEqual(self.inner(b, "spawn"), [], "the second repo's main session is not a citizen")
        b = self.inner(b, "gov")
        shop, pay = self.terr("github.com/acme/shop"), self.terr("github.com/acme/pay")
        self.assertEqual([(g["id"], g["terr"]) for g in a], [("r:dev-bo:gov:" + shop, shop)])
        self.assertEqual([(g["id"], g["terr"]) for g in b], [("r:dev-bo:gov:" + pay, pay)])
        snap = self.rc.snapshot_event()
        self.assertEqual(sorted(g["id"] for g in snap["govs"]),
                         sorted(["r:dev-bo:gov:" + shop, "r:dev-bo:gov:" + pay]))

    def test_second_session_in_the_same_repo_is_a_citizen(self):
        self.send(ev="UserPromptSubmit", sid="m1")
        spawn = self.inner(self.send(ev="UserPromptSubmit", sid="m3"), "spawn")
        self.assertEqual([s["id"] for s in spawn], ["r:dev-bo:s:m3"])

    def test_forgotten_device_ends_both_governors(self):
        self.send(ev="UserPromptSubmit", sid="m1")
        self.send(rid="github.com/acme/pay", ev="UserPromptSubmit", sid="m2")
        gone = [e for e in self.rc.poll(self.now + 601) if e["type"] == "remote"]
        ended = sorted(g["id"] for g in self.inner(gone, "gov") if g.get("present") is False)
        self.assertEqual(len(ended), 2)
        self.assertEqual(self.rc.snapshot_event()["govs"], [])


class TestRemoteChain(RemoteCase):
    def setUp(self):
        super().setUp()
        self.send(ev="UserPromptSubmit", sid="gov")                       # the governor
        self.send(ev="PostToolUse", sid="tm", role="task-manager", tool="Read")  # a lead
        self.send(ev="SubagentStart", sid="tm", aid="w1", at="worker")    # its worker

    def test_worker_question_goes_to_its_lead_before_done(self):
        out = self.send(ev="SubagentStop", sid="tm", aid="w1", at="worker", ask="q")
        types = [e["ev"]["type"] for e in out]
        self.assertIn("relay", types)
        self.assertLess(types.index("relay"), types.index("done"))
        self.assertEqual(self.inner(out, "relay"), [{"type": "relay", "id": "r:dev-bo:w1", "to": "lead",
                                                     "lead": "r:dev-bo:s:tm"}])

    def test_lead_asks_the_governor_then_the_governor_answers(self):
        out = self.send(ev="PostToolUse", sid="tm", role="task-manager", tool="SendMessage", ask="q")
        self.assertEqual(self.inner(out, "relay"), [{"type": "relay", "id": "r:dev-bo:s:tm", "to": "governor",
                                                     "lead": ""}])
        out = self.send(ev="PostToolUse", sid="gov", tool="SendMessage")
        self.assertEqual(self.inner(out, "relay_end"), [{"type": "relay_end", "id": "r:dev-bo:s:tm",
                                                         "by": "governor"}])

    def test_governor_helper_question(self):
        self.send(ev="SubagentStart", sid="gov", aid="h1", at="Explore")
        out = self.send(ev="SubagentStop", sid="gov", aid="h1", at="Explore", ask="q")
        self.assertEqual(self.inner(out, "relay"), [{"type": "relay", "id": "r:dev-bo:h1", "to": "governor",
                                                     "lead": ""}])

    def test_lead_answers_its_worker(self):
        self.send(ev="SubagentStop", sid="tm", aid="w1", at="worker", ask="q")
        out = self.send(ev="PostToolUse", sid="tm", role="task-manager", tool="SendMessage")
        self.assertEqual(self.inner(out, "relay_end"), [{"type": "relay_end", "id": "r:dev-bo:w1", "by": "lead"}])

    def test_lead_leaving_closes_its_relay(self):
        self.send(ev="PostToolUse", sid="tm", role="task-manager", tool="SendMessage", ask="q")
        out = self.send(ev="SessionEnd", sid="tm", role="task-manager")
        self.assertIn({"type": "relay_end", "id": "r:dev-bo:s:tm", "by": "leave"}, self.inner(out, "relay_end"))

    def test_timeout(self):
        self.send(ev="PostToolUse", sid="tm", role="task-manager", tool="SendMessage", ask="q")
        self.now += ac.RELAY_TIMEOUT_SEC + 1
        out = self.send(ev="PostToolUse", sid="tm", role="task-manager", tool="Read")
        self.assertIn({"type": "relay_end", "id": "r:dev-bo:s:tm", "by": "timeout"}, self.inner(out, "relay_end"))

    def test_events_are_wrapped(self):
        out = self.send(ev="SubagentStop", sid="tm", aid="w1", at="worker", ask="q")
        relay = [e for e in out if e["ev"]["type"] == "relay"][0]
        self.assertEqual({k: relay[k] for k in ("type", "dev", "who", "rid")},
                         {"type": "remote", "dev": "dev-bo", "who": "Bo", "rid": "github.com/acme/shop"})


if __name__ == "__main__":
    unittest.main()
