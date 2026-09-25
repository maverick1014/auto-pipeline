"""Failing tests: the minimum land has open plots, and a skipped build is logged
(requirements/city.md, Growth, owner 2026-09-25, main 3bec3dd).

CONTRACT (bin/agent_city.py, bin/agent-city.html)

  MIN_OPEN = 3 (agent_city.py). territory_tiles(plan, identity, lines)["open"]
    is at least MIN_OPEN for any lines, 0 included: the first MIN_OPEN plots of
    the plan, in plan order, are open and on land, each with its front road
    tile. Past that, growth is unchanged; open never goes down as lines grow.
  layout: a 0-line territory shows exactly MIN_OPEN open plots ("P").
  Server: a PostToolUse line whose kind's district has no free open plot
    broadcasts {"type": "noplot", "id", "terr", "btype", "by"}; id is the
    builder's city id (aid, "s:<sid>", or "gov" for a governor). An owner
    that already has a building in that territory gets nothing (one building
    per owner, silent as before).
  Page: a "noplot" event adds one log line "<name> 没有空地了，先等等" (name:
    the citizen's task, else ev.by). Never silent.

Run: python3 -m unittest tests.test_agent_city_minland </dev/null
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import REQUIRED, ac, run_sim  # noqa: E402

KIND_OF = {"house": "other", "tower": "test", "shop": "ui", "workshop": "script", "library": "doc"}
REPO = "/work/tiny/app/.git"


def plans():
    return ac.load_plans()


def tile(view, x, z):
    r, c = z - view["z0"], x - view["x0"]
    if 0 <= r < view["h"] and 0 <= c < view["w"]:
        return view["rows"][r][c]
    return " "


class TestMinimumOpenPlots(unittest.TestCase):

    def test_min_open_is_three(self):
        self.assertEqual(ac.MIN_OPEN, 3)

    def test_every_plan_opens_three_on_day_zero(self):
        for i, p in enumerate(plans()):
            with self.subTest(plan=p["id"]):
                t = ac.territory_tiles(p, "/day0/%d/.git" % i, 0)
                self.assertEqual(t["open"], 3)
                roads = ac._road_set(p)
                for x, z, _ in p["plots"][:3]:
                    self.assertIn((x, z), t["land"])
                    front = ac._front_of_plot(roads, x, z)
                    if front is not None:
                        self.assertIn(front, t["land"])

    def test_open_never_below_three_and_never_shrinks(self):
        for p in plans():
            prev = 0
            for n in (0, 3, 10, 50, 300, 1000, 3000, 20000):
                with self.subTest(plan=p["id"], lines=n):
                    o = ac.territory_tiles(p, "/grow/.git", n)["open"]
                    self.assertGreaterEqual(o, 3)
                    self.assertGreaterEqual(o, prev)
                    prev = o

    def test_day_zero_layout_shows_three_plots(self):
        for i, p in enumerate(plans()):
            ident = "/day0v/%d/.git" % i
            w = ac.new_world()
            ac.add_territory(w, plans(), ident, "app", 0)
            v = ac.layout(w, plans())
            t = v["territories"][0]
            with self.subTest(plan=t["plan"]):
                self.assertEqual(len(t["plots"]), 3)
                for pl in t["plots"]:
                    self.assertEqual(tile(v, pl["x"], pl["z"]), "P")


class StateCase(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_minland_")
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"), plans=plans(),
                               count_fn=lambda i: 3, balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}})
        self.client = self.st.add_client()
        self.client.queue.get_nowait()
        self.now = 1000.0

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def line(self, sid, aid="", kind="", tool="Write", role="task-manager", ev="PostToolUse"):
        self.now += 1
        self.st.feed_line({"ev": ev, "sid": sid, "aid": aid, "at": "worker" if aid else "", "tool": tool, "nt": "",
                           "proj": "app", "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": REPO,
                           "kind": kind, "ask": ""}, self.now)

    def drain(self):
        out = []
        while not self.client.queue.empty():
            raw = self.client.queue.get_nowait()
            if isinstance(raw, bytes):
                out.append(json.loads(raw.decode("utf-8").split("data:", 1)[1]))
        return out

    def plan(self):
        pid = self.st.world["territories"][REPO]["plan"]
        return next(p for p in plans() if p["id"] == pid)


class TestTinyRepoBuilds(StateCase):

    def test_first_write_in_a_tiny_repo_builds(self):
        self.line("tm", tool="Read")
        first = self.plan()["plots"][0][2]
        self.drain()
        self.line("tm", aid="w1", kind=KIND_OF[first])
        builds = [e for e in self.drain() if e.get("type") == "build"]
        self.assertEqual(len(builds), 1, "a tiny repo has room for the first agents")
        self.assertEqual(builds[0]["btype"], first)

    def test_no_free_plot_is_said_not_silent(self):
        self.line("tm", tool="Read")
        opened = {d for _, _, d in self.plan()["plots"][:3]}
        missing = next(d for d in ("shop", "library", "workshop", "house", "tower") if d not in opened)
        self.drain()
        self.line("tm", aid="w1", kind=KIND_OF[missing])
        ev = self.drain()
        self.assertEqual([e for e in ev if e.get("type") == "build"], [])
        none = [e for e in ev if e.get("type") == "noplot"]
        self.assertEqual(len(none), 1)
        self.assertEqual(none[0]["id"], "w1")
        self.assertEqual(none[0]["btype"], missing)
        self.assertEqual(none[0]["terr"], ac.territory_id(REPO))

    def test_an_owner_with_a_building_is_silent(self):
        self.line("tm", tool="Read")
        first = self.plan()["plots"][0][2]
        self.line("tm", aid="w1", kind=KIND_OF[first])
        self.drain()
        self.line("tm", aid="w1", kind=KIND_OF[first])
        ev = self.drain()
        self.assertEqual([e for e in ev if e.get("type") in ("build", "noplot")], [])


class TestNoPlotLogged(unittest.TestCase):

    def test_page_logs_it(self):
        w = ac.new_world()
        ac.add_territory(w, plans(), REPO, "app", 0)
        view = ac.layout(w, plans())
        driver = r"""
const V = __payload.view, tid = V.territories[0].id;
function buildLand(view){ landState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: tid }, govs: [], governors: 0, asks: [], shows: [], agents: [] });
apply({ type: 'spawn', id: 'w1', role: 'worker', label: 'worker', task: 'r1', terr: tid });
const before = logEntries.length;
apply({ type: 'noplot', id: 'w1', terr: tid, btype: 'shop', by: 'worker' });
apply({ type: 'noplot', id: 'zz', terr: tid, btype: 'shop', by: 'merge-deputy' });
__out = { added: logEntries.length - before, lines: logEntries.slice(0, 2).map(e => e.text) };
"""
        out = run_sim(driver, {"view": view}, REQUIRED + ("logEntries",))
        self.assertEqual(out["added"], 2)
        self.assertIn("没有空地了", out["lines"][1])
        self.assertIn("r1", out["lines"][1])
        self.assertIn("merge-deputy", out["lines"][0])


if __name__ == "__main__":
    unittest.main()
