"""Failing tests: the minimum land has open plots, and a skipped build is logged
(requirements/city.md, Growth, owner 2026-09-25, main 3bec3dd).

CONTRACT (bin/agent_city.py, bin/agent-city.html)

  Minimum land (main manager 2026-09-25, owner intent "a small land so that
  it has buildings"): the first plot of EVERY district the plan defines
  (house, shop, tower, workshop, library; the first in plan order within the
  district) is open at any size, 0 lines included, so any kind of first edit
  in a tiny repo builds, on every plan. Growth beyond that unlocks in plan
  order as today.
    open_plots(plan, lines) -> sorted list of the open plot indexes: those
      first plots plus the plan-order growth prefix (_open_count).
    territory_tiles(...)["open"] = len(open_plots(...)); every open plot and
      its front road tile is on land.
    layout: a territory's "plots" lists exactly its open plots (with "k");
      "open" is their count.
    build(): the first free OPEN plot of the district, in plan order.
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


def first_of_each_district(plan):
    first = {}
    for k, (_, _, d) in enumerate(plan["plots"]):
        first.setdefault(d, k)
    return first


def ident_for(plan_id, tag):
    for i in range(500):
        ident = "/work/%s-%d/app/.git" % (tag, i)
        w = ac.new_world()
        if ac.add_territory(w, plans(), ident, "app", 0)["plan"] == plan_id:
            return ident
    raise AssertionError("no identity found for plan " + plan_id)


class TestMinimumOpenPlots(unittest.TestCase):

    def test_day_zero_opens_the_first_plot_of_every_district(self):
        for p in plans():
            with self.subTest(plan=p["id"]):
                first = first_of_each_district(p)
                self.assertEqual(ac.open_plots(p, 0), sorted(first.values()))
                t = ac.territory_tiles(p, "/day0/%s/.git" % p["id"], 0)
                self.assertEqual(t["open"], len(first))
                roads = ac._road_set(p)
                for k in first.values():
                    x, z, _ = p["plots"][k]
                    self.assertIn((x, z), t["land"])
                    front = ac._front_of_plot(roads, x, z)
                    if front is not None:
                        self.assertIn(front, t["land"])

    def test_growth_adds_in_plan_order_and_never_shrinks(self):
        for p in plans():
            prev = set()
            base = set(first_of_each_district(p).values())
            for n in (0, 3, 50, 300, 1000, 3000, 20000, ac.LCAP):
                with self.subTest(plan=p["id"], lines=n):
                    got = set(ac.open_plots(p, n))
                    prefix = set(range(ac._open_count(p, ac.radius(n))))
                    self.assertEqual(got, base | prefix)
                    self.assertTrue(prev <= got)
                    prev = got
            self.assertEqual(prev, set(range(len(p["plots"]))))

    def test_day_zero_layout_shows_one_plot_per_district(self):
        for p in plans():
            ident = ident_for(p["id"], "day0v")
            w = ac.new_world()
            ac.add_territory(w, plans(), ident, "app", 0)
            v = ac.layout(w, plans())
            t = v["territories"][0]
            with self.subTest(plan=t["plan"]):
                first = first_of_each_district(p)
                self.assertEqual(sorted(pl["k"] for pl in t["plots"]), sorted(first.values()))
                self.assertEqual(t["open"], len(first))
                for pl in t["plots"]:
                    self.assertEqual(tile(v, pl["x"], pl["z"]), "P")

    def test_any_first_edit_builds_on_every_plan(self):
        for p in plans():
            ident = ident_for(p["id"], "anykind")
            w = ac.new_world()
            ac.add_territory(w, plans(), ident, "app", 0)
            for district, kind in KIND_OF.items():
                if district not in first_of_each_district(p):
                    continue
                with self.subTest(plan=p["id"], kind=kind):
                    b = ac.build(w, plans(), ident, kind, "o-" + kind, "worker", 1.0)
                    self.assertIsNotNone(b, "a tiny repo has room for a first %s" % district)
                    self.assertEqual(b["type"], district)
                    self.assertEqual(b["plot"], first_of_each_district(p)[district])


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

    def test_first_other_edit_in_a_tiny_repo_builds_a_house(self):
        self.line("tm", tool="Read")
        self.drain()
        self.line("tm", aid="w1", kind="other")
        builds = [e for e in self.drain() if e.get("type") == "build"]
        self.assertEqual(len(builds), 1, "a tiny repo has room for the first agents")
        self.assertEqual(builds[0]["btype"], "house")

    def test_no_free_plot_is_said_not_silent(self):
        self.line("tm", tool="Read")
        self.line("tm", aid="w1", kind="other")
        self.drain()
        self.line("tm", aid="w2", kind="other")
        ev = self.drain()
        self.assertEqual([e for e in ev if e.get("type") == "build"], [])
        none = [e for e in ev if e.get("type") == "noplot"]
        self.assertEqual(len(none), 1, "the only open house plot is taken: say so")
        self.assertEqual(none[0]["id"], "w2")
        self.assertEqual(none[0]["btype"], "house")
        self.assertEqual(none[0]["terr"], ac.territory_id(REPO))

    def test_an_owner_with_a_building_is_silent(self):
        self.line("tm", tool="Read")
        self.line("tm", aid="w1", kind="other")
        self.drain()
        self.line("tm", aid="w1", kind="other")
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
