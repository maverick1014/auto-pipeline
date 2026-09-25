"""Failing tests: people keep their names (owner report 2026-09-25, live city
after a server restart: a worker shown as "auto-pipeline:worker ·
auto-pipeline:worker", detail "auto-pipeline:worker · 帮手").

Cause: the Agent PreToolUse (desc + subagent_type) came before the restart and
was lost; the worker's next line auto-spawned it with label = task = its
agent type, which carries the plugin prefix, so the role was also unknown
("other", 帮手).

CONTRACT (bin/agent_city.py, bin/agent-city.html)

  bare_type(value) -> the text after the last ":" ("auto-pipeline:worker" ->
    "worker"; "worker" -> "worker"; "" -> ""): anything before is a plugin
    name. The server uses it for every role and label it takes from an agent
    type (SubagentStart/auto-spawn "at", the queued "sub", ask views, build
    "by"). So "auto-pipeline:worker" is role "worker", label "worker".
  Names survive a restart: world.json keeps "names": {citizen id: {"label",
    "task"}} for live citizens spawned with a task; written with the world
    when a citizen spawns, removed when it leaves, at most 200 (oldest
    dropped). A new server on the same world.json that sees a line from a
    known live id spawns it with the saved label and task. A world.json
    without "names" loads as before.
  Page: nameOf(c) -> c.label, or "<label> · <task>" when the task is not empty
    and differs from the label: never the same text twice. The person tag,
    the roster and the detail card use it.

Run: python3 -m unittest tests.test_agent_city_names </dev/null
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import REQUIRED, ac, function_source, run_sim  # noqa: E402

REPO = "/work/names/app/.git"
TYPE = "auto-pipeline:worker"
DESC = "Slice A: city server and hook"


class TestBareType(unittest.TestCase):

    def test_plugin_prefix_goes(self):
        self.assertEqual(ac.bare_type("auto-pipeline:worker"), "worker")
        self.assertEqual(ac.bare_type("a:b:merge-deputy"), "merge-deputy")
        self.assertEqual(ac.bare_type("worker"), "worker")
        self.assertEqual(ac.bare_type(""), "")


class NamesCase(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_names_")
        self.world = os.path.join(self.base, "world.json")
        self.now = 1000.0
        self.st = self.state()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def state(self, done_ttl=600):
        st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world,
                          plans=ac.load_plans(), count_fn=lambda i: 0,
                          balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}}, done_ttl=done_ttl)
        self.client = st.add_client()
        self.client.queue.get_nowait()
        return st

    def line(self, st, ev, aid="", at="", tool="", sub="", desc="", dt=1.0):
        self.now += dt
        st.feed_line({"ev": ev, "sid": "tm", "aid": aid, "at": at, "tool": tool, "nt": "", "proj": "app",
                      "role": "task-manager", "desc": desc, "sub": sub, "q": "", "klen": "", "repo": REPO,
                      "kind": "", "ask": ""}, self.now)

    def spawns(self):
        out = []
        while not self.client.queue.empty():
            raw = self.client.queue.get_nowait()
            if isinstance(raw, bytes):
                e = json.loads(raw.decode("utf-8").split("data:", 1)[1])
                if e.get("type") == "spawn":
                    out.append(e)
        return out

    def hire(self, st, aid, desc=DESC):
        self.line(st, "PreToolUse", tool="Agent", sub=TYPE, desc=desc)
        self.line(st, "SubagentStart", aid=aid, at=TYPE)

    def saved(self):
        with open(self.world, encoding="utf-8") as fh:
            return json.load(fh).get("names", {})


class TestTypesWithoutPlugin(NamesCase):

    def test_spawn_role_and_label_are_bare(self):
        self.hire(self.st, "w1")
        s = [e for e in self.spawns() if e["id"] == "w1"][0]
        self.assertEqual(s["role"], "worker")
        self.assertEqual(s["label"], "worker")
        self.assertEqual(s["task"], DESC)

    def test_auto_spawn_is_bare_too(self):
        self.line(self.st, "PostToolUse", aid="w7", at=TYPE, tool="Read")
        s = [e for e in self.spawns() if e["id"] == "w7"][0]
        self.assertEqual((s["role"], s["label"]), ("worker", "worker"))
        self.assertNotIn(":", s["task"])


class TestNamesSurviveRestart(NamesCase):

    def test_restart_keeps_label_and_task(self):
        self.hire(self.st, "w1")
        self.assertEqual(self.saved().get("w1"), {"label": "worker", "task": DESC})
        again = self.state()
        self.line(again, "PostToolUse", aid="w1", at=TYPE, tool="Read")
        s = [e for e in self.spawns() if e["id"] == "w1"][0]
        self.assertEqual((s["label"], s["task"]), ("worker", DESC))

    def test_a_citizen_that_left_is_forgotten(self):
        st = self.state(done_ttl=5)
        self.hire(st, "w1")
        self.line(st, "SubagentStop", aid="w1", at=TYPE)
        self.line(st, "PostToolUse", tool="Read", dt=10.0)
        self.assertNotIn("w1", self.saved())

    def test_at_most_200(self):
        for i in range(230):
            self.hire(self.st, "w%d" % i, desc="task %d" % i)
        names = self.saved()
        self.assertLessEqual(len(names), 200)
        self.assertIn("w229", names)
        self.assertNotIn("w0", names)

    def test_old_world_without_names_loads(self):
        w = ac.new_world()
        ac.add_territory(w, ac.load_plans(), REPO, "app", 0)
        ac.save_world(self.world, w)
        st = self.state()
        self.line(st, "PostToolUse", aid="w3", at=TYPE, tool="Read")
        self.assertEqual([e["label"] for e in self.spawns() if e["id"] == "w3"], ["worker"])
        self.assertEqual([n for n in os.listdir(self.base) if ".bad-" in n], [])


class TestNameShownOnce(unittest.TestCase):

    def test_name_of(self):
        driver = r"""
__out = [nameOf({ label: 'worker', task: 'worker' }), nameOf({ label: 'worker', task: '' }),
         nameOf({ label: 'worker', task: 'Slice A' }), nameOf({ label: 'task-manager', task: 'city-people' })];
"""
        out = run_sim(driver, {}, REQUIRED + ("nameOf",))
        self.assertEqual(out, ["worker", "worker", "worker · Slice A", "task-manager · city-people"])

    def test_tag_roster_and_detail_use_it(self):
        for fn in ("updatePerson", "renderRoster", "renderDetail"):
            with self.subTest(fn=fn):
                self.assertIn("nameOf(", function_source(fn) or "", fn + " shows names through nameOf()")
        self.assertNotIn("${c.label} · ${c.task}", function_source("updatePerson") or "")


if __name__ == "__main__":
    unittest.main()
