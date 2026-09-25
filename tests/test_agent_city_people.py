"""Failing tests for the city's people (requirements/city.md, Interaction and Growth).

P0 (owner, 2026-09-25, live city on main f5066f8): people do not walk.
  Seen: a task-manager session that only runs Bash/Read stands on the very
  spot the governor stands on (the two models overlap), "施工中" with no
  building, and never moves. The governor figure is drawn even when no
  governor session exists (the roster says 总督 不在).
  Cause (task manager, reproduced with a real server + headless page):
  newCitizen() gives every citizen stand = hallStand(t), the same point
  updateHome() puts the governor on; spawn "walks" to that stand (its own
  spot) and then waits in state 'building' for a build event that a
  Bash/Read-only agent never sends; placeAgent() (snapshot) puts everyone on
  that same point too. The governor figure has no "present" check. Walking
  to a plot on a real build event works (city-land did not break it).

CONTRACT (bin/agent-city.html, the inline script)

  The simulation section (from the comment "Simulation: the same event
  contract" to the comment "3D view.") runs without three.js: every test
  below runs it in node with a stub DOM, then drives it through apply(ev)
  and update(dt) only.

  function landState(view)   the non-3D half of buildLand(view), inside the
      simulation section: sets map, mid, land, clears occupied and the rest
      slots, adds the view's buildings as records, calls updateHome().
      buildLand(view) calls it first, then draws.
  function governorAt(terr)  -> {x, y} where that territory's governor
      figure stands, or null when no governor session is present there.
      The governor figure is drawn only when governorAt(its terr) is not null.
  Governor presence (server -> page):
      snapshot "govs": [{"terr", "state"}] = the governors present now
      (an empty list: none). A {"type": "gov", "terr", "state", "present"}
      event updates one; present false = that governor left.
  Every citizen has its own spot. After people settle, no two people
      (citizens and governors) stand closer than 0.45 tiles, and nobody
      stands within 0.45 of a governor.
  A working citizen walks: a citizen without a building walks between spots
      near its home while it works (tool events), at least 1 tile of path
      over 12 s with 6 tool events. It never shows "施工中" without a
      building (citizenStatus text).
  A worker that gets a build event walks to the plot and builds there
      (a building record on that plot, the worker within 1.3 tiles of the
      plot centre, state 'building'), on every terrain (5 plans).
  A done citizen walks to a rest spot and rests on it (state 'resting',
      within 0.2 of c.rest), on every terrain.

  Server: CityState snapshot "govs" lists the governor sessions present
      (0.6.0 reducer: the first session without AGENT_ROLE). A governor's
      SessionEnd broadcasts {"type": "gov", "present": false, "terr"}.

Run: python3 -m unittest tests.test_agent_city_people </dev/null
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGE = os.path.join(ROOT, "bin", "agent-city.html")
sys.path.insert(0, os.path.join(ROOT, "bin"))

import agent_city as ac  # noqa: E402


def page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


def sim_section():
    """The page script from 'use strict' up to the 3D view comment."""
    text = page()
    m = re.search(r"<script>\s*\(\(\) => \{\s*'use strict';", text)
    if not m:
        raise AssertionError("inline script with 'use strict' not found")
    start = m.end()
    end = text.find("3D view.", start)
    if end < 0:
        raise AssertionError("the '3D view.' comment not found")
    end = text.rfind("/*", start, end)
    return "'use strict';\n" + text[start:end]


def function_source(name):
    text = page()
    m = re.search(r"^(?:async\s+)?function %s\s*\(" % re.escape(name), text, re.M)
    if not m:
        return None
    i = text.index("{", m.end())
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[m.start():j + 1]
    return None


# A stub browser: every unknown name becomes a harmless "anything" (callable,
# any property, truthy), except REQUIRED names, which must be in the page.
SIM_JS = r"""
const fs = require('fs'), vm = require('vm');
const { script, driver, payload, required } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
function anything(){
  const f = function(){ return P; };
  const P = new Proxy(f, {
    get(t, k){ if (k === Symbol.toPrimitive) return () => ''; if (k === 'then') return undefined;
      if (k === 'length') return 0; if (k === Symbol.iterator) return function*(){}; return P; },
    set(){ return true; }, apply(){ return P; }, construct(){ return P; }, has(){ return true; } });
  return P;
}
const base = () => ({ console, Math, JSON, Date, Map, Set, WeakMap, Array, Object, Number, String, Boolean,
  Promise, Symbol, Error, RegExp, parseInt, parseFloat, isFinite, isNaN, Infinity, NaN, undefined,
  setTimeout: () => 0, clearTimeout(){}, setInterval: () => 0, clearInterval(){}, requestAnimationFrame(){},
  cancelAnimationFrame(){}, performance: { now: () => 0 }, document: anything(), window: anything(),
  navigator: anything(), localStorage: { getItem(){ return null; }, setItem(){}, removeItem(){} },
  location: { hash: '', protocol: 'http:', search: '', href: 'http://127.0.0.1/' },
  matchMedia: () => ({ matches: false, addEventListener(){}, addListener(){} }), addEventListener(){},
  THREE: anything(), EventSource: function(){ return anything(); }, fetch: () => new Promise(() => {}),
  devicePixelRatio: 1, innerWidth: 1200, innerHeight: 800 });
const stubs = new Set();
for (let tries = 0; tries < 150; tries++) {
  const box = base();
  for (const s of stubs) box[s] = anything();
  box.__payload = payload; box.__out = null;
  vm.createContext(box);
  try {
    vm.runInContext(script + '\n;\n' + driver, box, { timeout: 60000 });
    process.stdout.write(JSON.stringify(box.__out)); process.exit(0);
  } catch (e) {
    const m = /^(\S+) is not defined$/.exec((e && e.message) || '');
    if (e && e.name === 'ReferenceError' && m && !required.includes(m[1]) && !stubs.has(m[1])) { stubs.add(m[1]); continue; }
    process.stdout.write(JSON.stringify({ fatal: String(e && e.stack || e).slice(0, 2500) })); process.exit(0);
  }
}
process.stdout.write(JSON.stringify({ fatal: 'too many unknown names: ' + [...stubs].join(' ') }));
"""


def run_sim(driver, payload, required=()):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "sim.js")
        data = os.path.join(tmp, "data.json")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(SIM_JS)
        with open(data, "w", encoding="utf-8") as fh:
            json.dump({"script": sim_section(), "driver": driver, "payload": payload,
                       "required": list(required)}, fh)
        result = subprocess.run([node, script, data], capture_output=True, text=True,
                                timeout=120, stdin=subprocess.DEVNULL)
    if result.returncode != 0 or not result.stdout.strip():
        raise AssertionError("sim harness failed:\n" + result.stderr[-3000:])
    out = json.loads(result.stdout)
    if isinstance(out, dict) and "fatal" in out:
        raise AssertionError("sim harness crashed: " + out["fatal"])
    return out


def plan_views():
    """One world view per plan (terrain): a single territory, big enough to open plots."""
    plans = ac.load_plans()
    views = {}
    for i in range(400):
        ident = "/work/p0-%d/app/.git" % i
        w = ac.new_world()
        t = ac.add_territory(w, plans, ident, "app%d" % i, 6000)
        t["peak"] = t["lines"] = 6000
        plan = t["plan"]
        if plan in views:
            continue
        views[plan] = ac.layout(w, plans)
        if len(views) == len(plans):
            break
    return views


# Drives the simulation section on one territory: snapshot with a present
# governor and 4 placed agents, then a live worker that builds and rests, and
# a live Bash-only session that works without a building.
P0_DRIVER = r"""
const V = __payload.view, T = V.territories[0], tid = T.id;
const PLOT = T.plots[0];
function buildLand(view){ landState(view); }
const trace = {};
function tick(sec){
  for (let i = 0; i < Math.round(sec * 10); i++) {
    const before = citizens.map(c => [c.id, c.x, c.y]);
    update(.1);
    for (const [id, x, y] of before) { const c = byId(id); if (c) trace[id] = (trace[id] || 0) + Math.hypot(c.x - x, c.y - y); }
  }
}
function spots(){
  // standing people only: strollers (city-people calm) may pass each other while walking
  const out = citizens.filter(c => !c.gone && !(c.path && c.path.length)).map(c => ({ id: c.id, x: c.x, y: c.y, state: c.state }));
  const g = governorAt(tid);
  if (g) out.push({ id: 'gov', x: g.x, y: g.y, state: 'gov' });
  return out;
}
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: tid }, govs: [{ terr: tid, state: 'busy' }],
  governors: 1, asks: [], shows: [], agents: [
    { id: 's:tm', role: 'task-manager', label: 'task-manager', task: 'repo', stuck: false, done: false, tools: { Bash: 3 }, terr: tid },
    { id: 'a1', role: 'worker', label: 'worker', task: 'x', stuck: false, done: false, tools: { Edit: 2 }, terr: tid },
    { id: 'a2', role: 'worker', label: 'worker', task: 'y', stuck: false, done: true, tools: { Edit: 2 }, terr: tid },
    { id: 'a3', role: 'fast-lane-deputy', label: 'fast-lane-deputy', task: 'z', stuck: false, done: false, tools: { Read: 1 }, terr: tid } ] });
const govFirst = governorAt(tid);
tick(20);
const settled = spots();
apply({ type: 'spawn', id: 'w9', role: 'worker', label: 'worker', task: 'build', terr: tid });
tick(4);
apply({ type: 'build', id: 'w9', terr: tid, plot: PLOT.k, btype: 'tower', x: PLOT.x, z: PLOT.z, by: 'worker' });
tick(45);
const w9 = byId('w9');
const bld = buildings.find(b => b.terr === tid && b.plot === PLOT.k);
const built = { state: w9.state, x: w9.x, y: w9.y, plotX: PLOT.x + .5, plotZ: PLOT.z + .5, building: !!bld };
apply({ type: 'done', id: 'w9' });
tick(45);
const rested = { state: w9.state, x: w9.x, y: w9.y, rest: w9.rest ? { x: w9.rest.x, y: w9.rest.y } : null };
apply({ type: 'spawn', id: 's:tm2', role: 'task-manager', label: 'task-manager', task: 'other', terr: tid });
tick(3);
const walkedBefore = trace['s:tm2'] || 0;
for (let i = 0; i < 6; i++) { apply({ type: 'tool', id: 's:tm2', tool: i % 2 ? 'Read' : 'Bash' }); tick(2); }
tick(8);
const tm2 = byId('s:tm2');
const worked = { walked: (trace['s:tm2'] || 0) - walkedBefore, status: citizenStatus(tm2, 1), hasBld: !!tm2.bld };
const final = spots();
apply({ type: 'gov', terr: tid, state: 'idle', present: false });
const govGone = governorAt(tid);
__out = { govFirst, settled, built, rested, worked, final, govGone };
"""

REQUIRED = ("landState", "governorAt", "apply", "update", "citizens", "buildings", "byId", "citizenStatus")


class TestPeopleWalkP0(unittest.TestCase):
    """P0: people do not walk / stand on the governor (owner, 2026-09-25)."""

    @classmethod
    def setUpClass(cls):
        cls.results = {}
        for plan, view in plan_views().items():
            cls.results[plan] = run_sim(P0_DRIVER, {"view": view}, REQUIRED)

    def far_apart(self, people, what):
        for i, a in enumerate(people):
            for b in people[i + 1:]:
                d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
                self.assertGreaterEqual(d, 0.45, "%s: %s and %s stand on the same spot (%.2f apart)"
                                        % (what, a["id"], b["id"], d))

    def test_five_terrains_are_covered(self):
        self.assertEqual(len(self.results), 5)

    def test_governor_present_stands_at_its_hall(self):
        for plan, r in self.results.items():
            with self.subTest(plan=plan):
                self.assertIsNotNone(r["govFirst"], "a present governor has a spot")

    def test_placed_people_never_share_a_spot(self):
        for plan, r in self.results.items():
            with self.subTest(plan=plan):
                self.far_apart(r["settled"], plan + " after the snapshot")

    def test_worker_walks_to_its_plot_and_builds(self):
        for plan, r in self.results.items():
            with self.subTest(plan=plan):
                b = r["built"]
                self.assertTrue(b["building"], "a building record on the plot")
                self.assertEqual(b["state"], "building")
                self.assertLessEqual(math.hypot(b["x"] - b["plotX"], b["y"] - b["plotZ"]), 1.3,
                                     "the worker stands at its plot")

    def test_done_worker_walks_to_a_rest_spot(self):
        for plan, r in self.results.items():
            with self.subTest(plan=plan):
                s = r["rested"]
                self.assertEqual(s["state"], "resting")
                self.assertIsNotNone(s["rest"])
                self.assertLess(math.hypot(s["x"] - s["rest"]["x"], s["y"] - s["rest"]["y"]), 0.2)

    def test_working_citizen_without_a_building_walks(self):
        for plan, r in self.results.items():
            with self.subTest(plan=plan):
                w = r["worked"]
                self.assertFalse(w["hasBld"])
                self.assertGreaterEqual(w["walked"], 1.0, "moves while it works")
                self.assertNotEqual(w["status"][1], "施工中", "no 施工中 without a building")

    def test_everyone_apart_at_the_end(self):
        for plan, r in self.results.items():
            with self.subTest(plan=plan):
                people = [p for p in r["final"] if p["state"] != "leaving"]
                self.far_apart(people, plan + " at the end")

    def test_governor_that_left_is_not_drawn(self):
        for plan, r in self.results.items():
            with self.subTest(plan=plan):
                self.assertIsNone(r["govGone"])


class TestGovernorFigureP0(unittest.TestCase):

    def test_figure_follows_governor_at(self):
        src = function_source("updateGovernor")
        self.assertIsNotNone(src, "updateGovernor() still draws the figure")
        self.assertIn("governorAt(", src, "the figure is shown only where a governor is present")

    def test_build_land_calls_land_state(self):
        src = function_source("buildLand")
        self.assertIsNotNone(src)
        self.assertIn("landState(", src)

    def test_no_governor_in_snapshot_means_no_figure(self):
        view = next(iter(plan_views().values()))
        driver = r"""
const V = __payload.view, tid = V.territories[0].id;
function buildLand(view){ landState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: tid }, govs: [], governors: 0, asks: [], shows: [], agents: [] });
__out = { g: governorAt(tid) };
"""
        self.assertIsNone(run_sim(driver, {"view": view}, REQUIRED)["g"])


def feed(st, ev, sid, repo, role="", aid="", tool="Read"):
    st.feed_line({"ev": ev, "sid": sid, "aid": aid, "at": "", "tool": tool, "nt": "", "proj": "p",
                  "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}, 1000.0)


def snapshot(st):
    client = st.add_client()
    return json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1])


class TestGovernorPresenceServerP0(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_people_")
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"),
                               plans=ac.load_plans(), count_fn=lambda i: 0,
                               balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}})

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_no_governor_session_lists_none(self):
        feed(self.st, "PostToolUse", "tm", "/a/.git", role="task-manager")
        self.assertEqual(snapshot(self.st)["govs"], [])

    def test_governor_session_is_listed_with_its_territory(self):
        feed(self.st, "UserPromptSubmit", "g1", "/a/.git")
        govs = snapshot(self.st)["govs"]
        self.assertEqual([g["terr"] for g in govs], [ac.territory_id("/a/.git")])
        self.assertIn("state", govs[0])

    def test_governor_leaving_is_broadcast(self):
        feed(self.st, "UserPromptSubmit", "g1", "/a/.git")
        client = self.st.add_client()
        client.queue.get_nowait()
        feed(self.st, "SessionEnd", "g1", "/a/.git")
        msgs = []
        while not client.queue.empty():
            msgs.append(json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1]))
        gone = [m for m in msgs if m.get("type") == "gov" and m.get("present") is False]
        self.assertTrue(gone, "a gov event with present false")
        self.assertEqual(gone[0]["terr"], ac.territory_id("/a/.git"))
        self.assertEqual(snapshot(self.st)["govs"], [])


if __name__ == "__main__":
    unittest.main()
