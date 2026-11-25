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

  function officeState(view)   the non-3D half of buildLand(view), inside the
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
  A working citizen stays on its spot (city-work-anim, owner 2026-09-29,
      replaces "walks between spots near its home while it works"): under
      0.05 tiles of path over 12 s with 6 tool events. It never shows
      "施工中" without a building (citizenStatus text).
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

from citypage import HERE, ROOT, PAGE, page, sim_section, OFFICE_DRAW, _function_source_one, function_source, SIM_JS, run_sim, plan_views, REQUIRED  # noqa: E402,F401  (test-slim: shared helpers)
sys.path.insert(0, os.path.join(ROOT, "bin"))

import agent_city as ac  # noqa: E402


# Drives the simulation section on one territory: snapshot with a present
# governor and 4 placed agents, then a live worker that builds and rests, and
# a live Bash-only session that works without a building.
P0_DRIVER = r"""
const V = __payload.view, T = V.territories[0], tid = T.id;
const PLOT = T.plots[0];
function buildLand(view){ officeState(view); }
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
tick(15); // city-work-anim: settled on its spot first -- the tool events below must not move it
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


class TestGovernorFigureP0(unittest.TestCase):

    def test_no_governor_in_snapshot_means_no_figure(self):
        view = next(iter(plan_views().values()))
        driver = r"""
const V = __payload.view, tid = V.territories[0].id;
function buildLand(view){ officeState(view); }
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
        # city-roles: g1 is the main manager of /a/.git (the governor is the lock holder only)
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"),
                               main_fn=lambda identity: (os.getpid(), "g1") if identity == "/a/.git" else None)

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
