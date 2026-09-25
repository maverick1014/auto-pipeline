"""Failing tests: the chain survives a page reload (D2), and people with nothing to do act calmer
(owner, 2026-09-25; requirements/city.md on main).

CONTRACT (bin/agent-city.html, simulation section)

  D2: a page opened mid-chain shows what an open page shows. Snapshot agents carry "relay"
    (and "lead", "office"): placeAgent puts a worker with relay "lead" (done or not) at its lead's
    office waiting (问经理), never resting; a lead with relay "governor" walks to its governor
    (在问总督). Same statuses and places as the live events give.
  Calm:
    govAnim(terr, t) -> the governor figure's animation at sim time t (seconds): 'walk' while he
      strolls, else 'idle' most of the time; a small gesture at most once in a while: in any 60 s
      no more than 3 s of gesture and no gesture longer than 2 s, also while his state is
      "waiting" (no looping wave or handshake). updateGovernor() uses it.
    Idle strolls: a governor with nothing to do (no open ask of his, nobody walking to him or
      waiting at him) and a citizen that is working without a building and has had no tool event
      for a while (never sooner than 30 s of nothing to do) take a slow walk now and then, on the walk grid: to a nearby building, the rest
      place or a road, pause, come back. The governor stays near his hall and town (within 8
      tiles). governorAt(terr) / governorFigures() give where he stands now.
    A new ask of the governor, or a relay/stuck heading to him, sends him back to his hall stand
      at once. Working (building), asking, waiting and resting people keep what they do: a
      resting person stays on its seat.

Run: python3 -m unittest tests.test_agent_city_calm </dev/null
"""

import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import REQUIRED, function_source, run_sim  # noqa: E402
from test_agent_city_chain import FEATURE_REQUIRED, TA, TB, two_territory_view  # noqa: E402


def dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


CHAIN_RELOAD_DRIVER = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
const OF = A.offices[0], OC = { x: OF.x + .5, y: OF.z + .5 };
function buildLand(view){ landState(view); }
function tick(sec){ for (let i = 0; i < Math.round(sec * 10); i++) update(.1); }
const live = __payload.mode === 'live';
const L = { id: 's:L', role: 'task-manager', label: 'task-manager', task: 'city-people', stuck: false, done: false, tools: { Bash: 2 }, terr: A.id, lead: '', office: { x: OF.x, z: OF.z }, relay: live ? '' : 'governor' };
const W = { id: 'w1', role: 'worker', label: 'worker', task: 'reducer', stuck: false, done: !live, tools: { Edit: 1 }, terr: A.id, lead: 's:L', office: null, relay: live ? '' : 'lead' };
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'busy' }, { terr: B.id, state: 'idle' }], agents: [L, W] });
if (live) {
  tick(5);
  apply({ type: 'relay', id: 'w1', to: 'lead', lead: 's:L' }); apply({ type: 'done', id: 'w1' });
  tick(5);
  apply({ type: 'relay', id: 's:L', to: 'governor', lead: '' });
}
tick(35);
const w = byId('w1'), l = byId('s:L'), g = governorAt(A.id);
__out = { w: { x: w.x, y: w.y, state: w.state, status: citizenStatus(w, 1) }, l: { x: l.x, y: l.y, status: citizenStatus(l, 1) },
  g, OC };
"""


class TestChainSurvivesReload(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        view = two_territory_view()
        cls.live = run_sim(CHAIN_RELOAD_DRIVER, {"view": view, "ta": TA, "tb": TB, "mode": "live"}, FEATURE_REQUIRED)
        cls.snap = run_sim(CHAIN_RELOAD_DRIVER, {"view": view, "ta": TA, "tb": TB, "mode": "snap"}, FEATURE_REQUIRED)

    def test_same_statuses_live_and_after_reload(self):
        self.assertEqual(self.snap["w"]["status"], self.live["w"]["status"])
        self.assertEqual(self.snap["l"]["status"], self.live["l"]["status"])
        self.assertEqual(self.snap["l"]["status"][1], "在问总督")

    def test_the_waiting_worker_is_at_the_office_not_resting(self):
        for name, r in (("live", self.live), ("snapshot", self.snap)):
            with self.subTest(page=name):
                self.assertNotEqual(r["w"]["state"], "resting")
                self.assertLessEqual(dist(r["w"], r["OC"]), 1.6)

    def test_the_lead_is_with_the_governor(self):
        for name, r in (("live", self.live), ("snapshot", self.snap)):
            with self.subTest(page=name):
                self.assertLessEqual(dist(r["l"], r["g"]), 1.6)


CALM_DRIVER = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta);
function buildLand(view){ landState(view); }
const inside = (p, f) => Math.abs(p.x - f.x) < f.hw - 1e-6 && Math.abs(p.y - f.z) < f.hd - 1e-6;
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'idle' }], agents: [
  { id: 'w1', role: 'worker', label: 'worker', task: 'idle one', stuck: false, done: false, tools: {}, terr: A.id, lead: '', office: null, relay: '' },
  { id: 'r1', role: 'worker', label: 'worker', task: 'rests', stuck: false, done: true, tools: {}, terr: A.id, lead: '', office: null, relay: '' } ] });
for (let i = 0; i < 100; i++) update(.1);
const hall = governorAt(A.id), homeW = { x: byId('w1').x, y: byId('w1').y };
const seat = byId('r1').rest ? { x: byId('r1').rest.x, y: byId('r1').rest.y } : null;
const gTrack = [], wTrack = [], restMoves = [], bad = [];
const anims = [];
for (let i = 0; i < 2400; i++) {            // 240 s
  update(.1);
  const g = governorAt(A.id), w = byId('w1'), r = byId('r1');
  if (i % 5 === 0) { gTrack.push(g ? { x: g.x, y: g.y } : null); wTrack.push({ x: w.x, y: w.y }); }
  anims.push(govAnim(A.id, (i + 100) / 10));
  if (r && seat && r.state === 'resting' && Math.hypot(r.x - seat.x, r.y - seat.y) > .3) restMoves.push(i);
  if (i % 10 === 0 && w.path && w.path.length) for (const f of footprints()) if (inside(w, f)) { bad.push(f.key); break; }
}
// then something needs the governor: his own question
const away = governorAt(A.id);
apply({ type: 'ask', id: 'q9', agent: 'gov', terr: A.id, label: '', task: '', kind: 'question', phase: 'owner', why: 'no-governor',
  wait: 60, left: 0, tool: 'AskUserQuestion', what: 'x?', at: 1, questions: [] });
for (let i = 0; i < 120; i++) update(.1);
const back = governorAt(A.id);
// the same for a waiting governor state: no looping gesture
apply({ type: 'gov', terr: A.id, state: 'waiting', present: true });
const waitAnims = [];
for (let i = 0; i < 600; i++) { update(.1); waitAnims.push(govAnim(A.id, 400 + i / 10)); }
__out = { hall, home: homeW, gTrack, wTrack, anims, waitAnims, restMoves: restMoves.length, bad, away, back };
"""


def stops(track, start):
    """Pauses (2 s or more without moving) away from START, as distinct spots, and whether it came back."""
    spots, returned, run, far_seen = [], False, 0, False
    for i in range(1, len(track)):
        a, b = track[i - 1], track[i]
        if a is None or b is None:
            continue
        run = run + 1 if math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < .02 else 0
        if run == 4:  # 4 samples x 0.5 s = 2 s still
            d = dist(b, start)
            if d >= 1.2:
                far_seen = True
                if all(dist(b, s) >= 1.0 for s in spots):
                    spots.append(b)
            elif far_seen and d <= .6:
                returned = True
    return spots, returned


def gesture_runs(anims, dt=.1):
    runs, cur = [], 0
    for a in anims:
        if a not in ("idle", "walk"):
            cur += 1
        elif cur:
            runs.append(cur * dt)
            cur = 0
    if cur:
        runs.append(cur * dt)
    return runs


class TestCalmIdlePeople(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(CALM_DRIVER, {"view": two_territory_view(), "ta": TA}, FEATURE_REQUIRED + ("govAnim", "footprints"))

    def test_governor_strolls_and_comes_back(self):
        spots, returned = stops(self.r["gTrack"], self.r["hall"])
        self.assertGreaterEqual(len(spots), 2, "an idle governor visits at least 2 spots")
        self.assertTrue(returned, "and comes back to his hall")
        for p in self.r["gTrack"]:
            if p:
                self.assertLessEqual(dist(p, self.r["hall"]), 8.0, "he stays near his hall")

    def test_idle_citizen_strolls_and_comes_back(self):
        spots, returned = stops(self.r["wTrack"], self.r["home"])
        self.assertGreaterEqual(len(spots), 2)
        self.assertTrue(returned)
        self.assertEqual(self.r["bad"], [], "strolls follow the walk grid")

    def test_no_looping_gesture(self):
        for name in ("anims", "waitAnims"):
            with self.subTest(state=name):
                runs = gesture_runs(self.r[name])
                self.assertTrue(all(x <= 2.0 for x in runs), "no gesture longer than 2 s: %s" % runs[:5])
                window = self.r[name][-600:]
                self.assertLessEqual(sum(gesture_runs(window)), 3.0, "at most 3 s of gesture per minute")

    def test_a_question_sends_him_back_at_once(self):
        self.assertLessEqual(dist(self.r["back"], self.r["hall"]), .6)

    def test_resting_people_stay_seated(self):
        self.assertEqual(self.r["restMoves"], 0)

    def test_the_figure_uses_it(self):
        self.assertIn("govAnim(", function_source("updateGovernor") or "")


if __name__ == "__main__":
    unittest.main()
