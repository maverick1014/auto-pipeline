"""Failing tests for idea-city, server side (bin/agent_city.py,
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
  C4 one set of file-kind rules: the server's
    The hook no longer classifies paths: its line has no "kind" key (16 keys,
    "file" still last). The server decides the building from "file" with
    file_kind(file, <that repo's rules.conf rules>) and this map:
      rules -> tower, beauty -> shop, infra -> workshop, knowledge -> library,
      build -> house; None (vendor, lock, binary, not code) -> no building.
    A line with a "file" ignores any "kind" it carries. A line with no "file" but
    an old hook kind (test ui script doc other) still builds by the old map (old
    events.jsonl lines).

  C5 idle_prompt is not a question (changed by city-status, 2026-10-01:
     tests/test_agent_city_status.py)
    A Notification idle_prompt changes nothing: no event, for a citizen and
    for the governor. A citizen is "waiting" ({"type": "waiting", "id"}, never
    "stuck") only when its last reply asks the owner (a StopNote line with
    need "1"); its next PreToolUse / PostToolUse / UserPromptSubmit ->
    {"type": "resume", "id"} first, then the usual events. permission_prompt stays
    "stuck". Reducer.snapshot() agents carry "waiting": bool. A waiting citizen never
    starts a chain relay and never becomes an ask.

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


class TestHookHasNoPathRules(unittest.TestCase):
    def test_no_classify_path(self):
        with open(os.path.join(BIN, "agent-city-hook.sh"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("classify_path", text)
        self.assertNotIn('"kind":', text)


# --------------------------------------------------------------------- C5

NOTE = {"ev": "StopNote", "sid": "tm1", "need": "1", "bg": ""}


class TestIdleIsNotAQuestion(unittest.TestCase):
    def setUp(self):
        self.r = ac.Reducer()
        self.r.feed(R("UserPromptSubmit", sid="main"), 1.0)
        self.r.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Write"), 1.0)

    def test_idle_prompt_is_nothing(self):
        self.assertEqual(self.r.feed(R("Notification", sid="tm1", role="task-manager", nt="idle_prompt"), 2.0), [])
        a = [a for a in self.r.snapshot()["agents"] if a["id"] == "s:tm1"][0]
        self.assertEqual((a["waiting"], a["stuck"]), (False, False))

    def test_a_reply_that_asks_is_waiting_once(self):
        self.assertEqual(self.r.feed(dict(NOTE), 2.0), [{"type": "waiting", "id": "s:tm1"}])
        self.assertEqual(self.r.feed(dict(NOTE), 3.0), [])
        a = [a for a in self.r.snapshot()["agents"] if a["id"] == "s:tm1"][0]
        self.assertEqual((a["waiting"], a["stuck"]), (True, False))

    def test_resume_comes_first(self):
        self.r.feed(dict(NOTE), 2.0)
        out = self.r.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Edit"), 3.0)
        self.assertEqual(out, [{"type": "resume", "id": "s:tm1"}, {"type": "tool", "id": "s:tm1", "tool": "Edit", "name": "Edit"}])
        a = [a for a in self.r.snapshot()["agents"] if a["id"] == "s:tm1"][0]
        self.assertFalse(a["waiting"])

    def test_prompt_resumes(self):
        self.r.feed(dict(NOTE), 2.0)
        self.assertEqual(self.r.feed(R("UserPromptSubmit", sid="tm1", role="task-manager"), 3.0),
                         [{"type": "resume", "id": "s:tm1"}])

    def test_permission_prompt_is_still_stuck(self):
        out = self.r.feed(R("Notification", sid="tm1", role="task-manager", nt="permission_prompt"), 2.0)
        self.assertEqual(out, [{"type": "stuck", "id": "s:tm1", "question": "", "tool": ""}])

    def test_governor_idle_prompt_is_nothing(self):
        self.assertEqual(self.r.feed(R("Notification", sid="main", nt="idle_prompt"), 2.0), [])
        self.assertEqual(self.r.snapshot()["gov"], {"state": "busy"})

    def test_every_snapshot_agent_has_waiting(self):
        for a in self.r.snapshot()["agents"]:
            self.assertIn("waiting", a)


class TestIdleInTheCity(tq.BuildCase):
    def test_idle_prompt_no_event_at_all(self):
        self.st.feed_line(dict(self.line("tm1"), role="task-manager", tool="Write", file=""), 1000.0)
        tq.drain(self.client)
        self.st.feed_line(dict(self.line("tm1"), ev="Notification", nt="idle_prompt", role="task-manager",
                               tool="", file=""), 1001.0)
        types = [e["type"] for e in tq.drain(self.client)]
        for bad in ("waiting", "stuck", "relay", "ask"):
            self.assertNotIn(bad, types)

    def test_waiting_no_relay_no_ask_no_stuck(self):
        self.st.feed_line(dict(self.line("tm1"), role="task-manager", tool="Write", file=""), 1000.0)
        tq.drain(self.client)
        self.st.feed_line(dict(NOTE), 1001.0)
        types = [e["type"] for e in tq.drain(self.client)]
        self.assertIn("waiting", types)
        for bad in ("stuck", "relay", "ask"):
            self.assertNotIn(bad, types)


if __name__ == "__main__":
    unittest.main()
