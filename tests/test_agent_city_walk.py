"""Failing tests: people never walk through models (owner report 2026-09-25;
requirements/city.md, Growth: "People never walk through models: buildings,
halls, trees, rocks, lamps, fountains, cars and tables block their footprint;
paths go around, and people re-route when something new is built").

CONTRACT (bin/agent-city.html, the simulation section, runs in node)

  function footprints() -> [{key, x, z, hw, hd}]: every model standing on
    the land now, as an axis-aligned box in world tiles (centre x, z; half
    width hw along x, half depth hd along z), the model's size as placed, no
    margin: each territory's hall, every building record (rising or done),
    wildDecor plants, pines and rocks (not the bridge deck: people cross
    it), hallDecor lamps, systemsDecor items (police, cars, library, towers,
    fountain, trees, ...), restDecor items except benches and chairs (people
    sit on them), officeDecor items. People and pets are not in it. Models
    are not loaded in node: the page keeps each model's placed size itself.
  Walk grid: WALK_SUB (at least 2) cells per tile. function freeAt(x, z) ->
    whether the world point is on a free cell: its tile is walkable (".grtBb",
    no building, plot or office on it) and the cell centre is outside every
    footprint grown by WALK_MARGIN (at least 0.05). landState(view) and every
    change of the footprints (a new building record, a world event) rebuild
    it.
  findPath(sx, sz, tx, tz) -> [[x, z], ...] world points (the last one the
    target) over free cells, cheapest first: roads, tracks and bridges cost
    least, territory ground a little more, wild land most; null when there
    is no way. Straight legs between points never cross a footprint.
  People: a moving person (path not empty) is never inside a footprint.
    Every place a person stands (home, office front, plot stand, hall stand,
    waiting spot) is free; a resting person sits on a rest seat.
  Re-route: when the footprints change, every walker whose remaining path
    crosses a new footprint gets a new path at once.

Run: python3 -m unittest tests.test_agent_city_walk </dev/null
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import REQUIRED, ac, run_sim  # noqa: E402

WALK_REQUIRED = REQUIRED + ("footprints", "freeAt", "findPath")
KINDS = ("build", "rules", "beauty", "knowledge", "infra")
ERAS = ("village", "town", "city")


def tile(view, x, z):
    r, c = z - view["z0"], x - view["x0"]
    if 0 <= r < view["h"] and 0 <= c < view["w"]:
        return view["rows"][r][c]
    return " "


def plan_view(plan_id, era):
    """One grown territory of PLAN_ID in ERA: buildings of every kind, every
    kind healthy (systems decor), a rest place and one lead's office."""
    plans = ac.load_plans()
    for i in range(500):
        ident = "/work/walk-%s-%d/app/.git" % (plan_id, i)
        w = ac.new_world()
        t = ac.add_territory(w, plans, ident, "app", 20000)
        if t["plan"] == plan_id:
            break
    t["lines"] = t["peak"] = 20000
    t["era"] = era
    t["balance"] = {k: {"state": "healthy", "value": 1, "n": 1, "text": ""} for k in KINDS}
    for k in ("other", "ui", "test", "script", "doc", "other", "ui"):
        ac.build(w, plans, ident, k, "o-%s-%d" % (k, len(t["buildings"])), "worker", 1.0)
    view = ac.layout(w, plans)
    tv = view["territories"][0]
    tv["era"] = era
    tv["balance"] = t["balance"]
    plots = {(p["x"], p["z"]) for p in tv["plots"]}

    def free(x, z):
        return tile(view, x, z) == "g" and (x, z) not in plots and not (
            -2 <= x - tv["cx"] <= 1 and -2 <= z - tv["cz"] <= 1)

    rest = office = None
    for r in range(3, 10):
        for dz in range(-r, r + 1):
            for dx in range(-r, r + 1):
                x, z = tv["cx"] + dx, tv["cz"] + dz
                if rest is None and all(free(x + a, z + b) for a in (0, 1) for b in (0, 1)):
                    rest = (x, z)
    for r in range(3, 10):
        for dz in range(-r, r + 1):
            for dx in range(-r, r + 1):
                x, z = tv["cx"] + dx, tv["cz"] + dz
                if office is None and free(x, z) and max(abs(x - rest[0]), abs(z - rest[1])) >= 3 \
                        and any(tile(view, x + a, z + b) in "grtB" for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    office = (x, z)
    tv.setdefault("rest", None)
    tv.setdefault("offices", [])
    tv["rest"] = {"x": rest[0], "z": rest[1]}
    tv["offices"] = [{"lead": "s:L", "x": office[0], "z": office[1]}]
    return view


WALK_DRIVER = r"""
const V = __payload.view, T = V.territories[0], tid = T.id;
function buildLand(view){ landState(view); }
const inside = (p, f) => Math.abs(p.x - f.x) < f.hw - 1e-6 && Math.abs(p.y - f.z) < f.hd - 1e-6;
const bad = [], standBad = [];
function check(label){
  const fps = footprints();
  for (const c of citizens) {
    if (c.gone || !c.path || !c.path.length) continue;
    for (const f of fps) if (inside(c, f)) { bad.push([label, c.id, c.state, f.key, +c.x.toFixed(2), +c.y.toFixed(2)]); break; }
  }
}
function tick(sec, label){ for (let i = 0; i < Math.round(sec * 10); i++) { update(.1); if (bad.length < 12) check(label); } }
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: tid }, govs: [{ terr: tid, state: 'busy' }], governors: 1,
  asks: [], shows: [], agents: [
  { id: 's:L', role: 'task-manager', label: 'task-manager', task: 'lead', stuck: false, done: false, tools: { Bash: 1 }, terr: tid, lead: '', office: { x: T.offices[0].x, z: T.offices[0].z }, relay: '' },
  { id: 'w1', role: 'worker', label: 'worker', task: 'a', stuck: false, done: false, tools: {}, terr: tid, lead: 's:L', office: null, relay: '' },
  { id: 'w2', role: 'worker', label: 'worker', task: 'b', stuck: false, done: false, tools: {}, terr: tid, lead: 's:L', office: null, relay: '' },
  { id: 'w3', role: 'worker', label: 'worker', task: 'c', stuck: false, done: false, tools: {}, terr: tid, lead: 's:L', office: null, relay: '' },
  { id: 'd1', role: 'fast-lane-deputy', label: 'fast-lane-deputy', task: 'd', stuck: false, done: false, tools: {}, terr: tid, lead: '', office: null, relay: '' },
  { id: 'r1', role: 'worker', label: 'worker', task: 'e', stuck: false, done: true, tools: {}, terr: tid, lead: '', office: null, relay: '' } ] });
const fps0 = footprints();
tick(20, 'settle');
const taken = new Set((T.buildings || []).map(b => b.plot));
const openPlots = (T.plots || []).filter(p => !taken.has(p.k)).slice(0, 3);
openPlots.forEach((p, i) => apply({ type: 'build', id: 'w' + (i + 1), terr: tid, plot: p.k, btype: p.d, x: p.x, z: p.z, by: 'worker' }));
tick(40, 'build');
for (let i = 0; i < 6; i++) { apply({ type: 'tool', id: 'd1', tool: 'Bash' }); tick(2, 'work'); }
apply({ type: 'relay', id: 'w1', to: 'lead', lead: 's:L' }); apply({ type: 'done', id: 'w1' });
tick(20, 'relay');
apply({ type: 'relay', id: 's:L', to: 'governor', lead: '' });
tick(35, 'lead');
apply({ type: 'relay_end', id: 's:L', by: 'governor' }); apply({ type: 'relay_end', id: 'w1', by: 'governor' });
apply({ type: 'done', id: 'w2' }); apply({ type: 'done', id: 'w3' });
tick(45, 'rest');
for (const c of citizens) {
  if (c.gone || (c.path && c.path.length) || c.state === 'resting' || c.state === 'leaving') continue;
  for (const f of footprints()) if (inside(c, f)) { standBad.push([c.id, c.state, f.key]); break; }
}
// random paths between free points
let seed = 7; const lcg = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const fps = footprints(), pathBad = []; let found = 0, tries = 0;
const pts = [];
for (let r = 0; r < V.h; r++) for (let c = 0; c < V.w; c++) {
  const x = V.x0 + c + .5, z = V.z0 + r + .5;
  if (Math.hypot(x - T.cx, z - T.cz) < 9 && freeAt(x, z)) pts.push([x, z]);
}
for (let k = 0; k < 40 && pts.length > 1; k++) {
  const a = pts[Math.floor(lcg() * pts.length)], b = pts[Math.floor(lcg() * pts.length)];
  tries++;
  const p = findPath(a[0], a[1], b[0], b[1]);
  if (!p) continue;
  found++;
  let prev = a;
  for (const q of p) {
    const n = Math.max(1, Math.ceil(Math.hypot(q[0] - prev[0], q[1] - prev[1]) / .05));
    for (let i = 0; i <= n; i++) {
      const pt = { x: prev[0] + (q[0] - prev[0]) * i / n, y: prev[1] + (q[1] - prev[1]) * i / n };
      for (const f of fps) if (inside(pt, f)) { if (pathBad.length < 8) pathBad.push([a, b, f.key, +pt.x.toFixed(2), +pt.y.toFixed(2)]); }
    }
    prev = q;
  }
}
const hall = fps0.filter(f => Math.abs(f.x - (T.cx - .5)) < 1.2 && Math.abs(f.z - (T.cz - .5)) < 1.2);
__out = { n: fps0.length, keys: [...new Set(fps0.map(f => f.key))], small: fps0.filter(f => !(f.hw >= .1 && f.hd >= .1)).length,
  hallHalf: hall.length ? Math.max(...hall.map(f => Math.min(f.hw, f.hd))) : 0,
  buildings: footprints().length - fps0.length, bad, standBad, pathBad, found, tries, points: pts.length };
"""


class TestWalkAroundModels(unittest.TestCase):
    """5 plans x 3 eras, one run each."""

    @classmethod
    def setUpClass(cls):
        cls.r = {}
        for plan in ac.load_plans():
            for era in ERAS:
                cls.r[(plan["id"], era)] = run_sim(WALK_DRIVER, {"view": plan_view(plan["id"], era)}, WALK_REQUIRED)

    def test_every_model_has_a_footprint(self):
        for key, r in self.r.items():
            with self.subTest(case=key):
                self.assertGreater(r["n"], 20)
                self.assertEqual(r["small"], 0, "a footprint smaller than 0.1 tile")
                self.assertGreaterEqual(r["hallHalf"], .7, "the hall blocks its 2x2 tiles")
                self.assertGreater(r["buildings"], 0, "a new building adds its footprint")

    def test_nobody_walks_through_a_model(self):
        for key, r in self.r.items():
            with self.subTest(case=key):
                self.assertEqual(r["bad"], [], "moving people inside a footprint")

    def test_nobody_stands_in_a_model(self):
        for key, r in self.r.items():
            with self.subTest(case=key):
                self.assertEqual(r["standBad"], [])

    def test_paths_go_around(self):
        for key, r in self.r.items():
            with self.subTest(case=key):
                self.assertGreater(r["points"], 30, "free walk points around the hall")
                self.assertGreaterEqual(r["found"], r["tries"] * .7, "most free points reach each other")
                self.assertEqual(r["pathBad"], [])


REROUTE_DRIVER = r"""
const V = __payload.view, T = V.territories[0], tid = T.id;
function buildLand(view){ landState(view); }
const inside = (p, f) => Math.abs(p.x - f.x) < f.hw - 1e-6 && Math.abs(p.y - f.z) < f.hd - 1e-6;
const V0 = JSON.parse(JSON.stringify(V)); const rest = V0.territories[0].rest; V0.territories[0].rest = null;
apply({ type: 'snapshot', world: V0, gov: { state: 'busy', terr: tid }, govs: [{ terr: tid, state: 'busy' }], governors: 1,
  asks: [], shows: [], agents: [] });
apply({ type: 'spawn', id: 'w', role: 'worker', label: 'worker', task: 'walker', terr: tid });
for (let i = 0; i < 30; i++) update(.1);
const c = byId('w');
// send it right across the rest area, then open the rest place under its feet
c.x = rest.x - .5; c.y = rest.z + .5; c.path = [];
goTo(c, { x: rest.x + 2.5, y: rest.z + .5 }, 'back');
const crossed = c.path.some(([x, z]) => x >= rest.x && x < rest.x + 2 && z >= rest.z && z < rest.z + 2);
update(.1);
apply({ type: 'world', world: V });
const fps = footprints().filter(f => Math.abs(f.x - (rest.x + 1)) < 1.6 && Math.abs(f.z - (rest.z + 1)) < 1.6);
const bad = [];
for (let i = 0; i < 200; i++) { update(.1); for (const f of fps) if (c.path.length && inside(c, f)) { bad.push([f.key, +c.x.toFixed(2), +c.y.toFixed(2)]); break; } }
__out = { newFootprints: fps.length, bad, crossed };
"""

ROADS_DRIVER = r"""
const rows = ['rrrrrrr', 'r.....r', 'r.....r', 'rrrrrrr'];
const V = { cell: 26, x0: 0, z0: 0, w: 7, h: 4, rows, territories: [], links: [] };
function buildLand(view){ landState(view); }
landState(V);
const p = findPath(.5, 1.5, 6.5, 1.5);
__out = { p, wild: p ? p.filter(([x, z]) => rows[Math.floor(z)][Math.floor(x)] === '.').length : -1 };
"""


class TestRerouteAndRoads(unittest.TestCase):

    def test_walkers_reroute_around_something_new(self):
        r = run_sim(REROUTE_DRIVER, {"view": plan_view("meadow", "town")}, WALK_REQUIRED + ("goTo",))
        self.assertTrue(r["crossed"], "before: the way runs over the empty rest area")
        self.assertGreater(r["newFootprints"], 0, "the rest place brings models")
        self.assertEqual(r["bad"], [])

    def test_roads_before_wild_land(self):
        r = run_sim(ROADS_DRIVER, {}, WALK_REQUIRED)
        self.assertIsNotNone(r["p"])
        self.assertEqual(r["wild"], 0, "a short road detour beats cutting through wild land")


if __name__ == "__main__":
    unittest.main()
