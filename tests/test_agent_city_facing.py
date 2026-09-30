"""Failing tests for city-polish P1: walking people face where they walk (owner, 2026-09-30, screenshots of
the live city: people sometimes walk sideways or backwards -- "so weird").

Cause (task manager, reading bin/agent-city.html at e744814): the governor figures (govV and the
per-territory pool) play 'walk' while they stroll but their rotation is never set, so a strolling governor
slides sideways or backwards; a citizen turns by a fixed share per drawn frame (v.yaw += d * .25), not per
second, so on a slow or busy page it is still turning long after it started to walk the other way.

CONTRACT (bin/agent-city.html). "sim section" = the page script from 'use strict' up to the '3D view.'
comment (tests/test_agent_city_people.py run_sim drives it in node, no three.js, no DOM).

  (sim) TURN_RATE (10 .. 24): how fast a person turns, per second.
  (sim) angleDiff(a, b) -> b - a wrapped into (-PI, PI].
  (sim) turnToward(yaw, want, dt) -> the new yaw, want null/undefined -> yaw unchanged; else
        yaw + angleDiff(yaw, want) * (1 - Math.exp(-TURN_RATE * dt)): the short way round, never past want,
        the same after two steps of dt/2 as after one of dt (frame-rate independent).
  (sim) TURN_WALK_MAX (PI/4 .. PI/3): move(c, dt) first turns c.yaw toward its next point (turnToward), then
        steps only when |angleDiff(c.yaw, the step's direction)| <= TURN_WALK_MAX; otherwise it turns on the
        spot this tick. So nobody ever steps sideways or backwards. Direction = Math.atan2(dx, dz) of the
        step (x, then the second coordinate, c.y) -- the same yaw the 3D model already uses.
  (sim) Every citizen has c.yaw (newCitizen: 0). update(dt): a walker turns in move() (above); a person that
        stands turns toward faceWant(c) (turnToward(c.yaw, faceWant(c), dt)).
  (sim) faceWant(c) -> the yaw a standing person wants, or null (keep its facing): state 'building' with
        c.bld -> the building middle, atan2(c.bld.gx + .5 - c.x, c.bld.gy + .5 - c.y); 'asking' or 'heard' ->
        the governor it talks to (governorAt(c.terr), else gov); resting on a 'cafe' seat -> PI/2, on a
        'bench' -> 0; else null. Today's 3D targets, moved into the sim.
  (sim) A governor's move state (govMove entries, ensureGovMove: yaw 0) turns the same way in
        updateGovernors: toward his next point while he walks (same TURN_WALK_MAX rule: turn on the spot
        first); standing on his hall stand he turns back to 0 (today's look); standing anywhere else he keeps
        his facing. governorAt(terr) -> {x, y, yaw} (yaw = m.yaw). governorFigures() entries carry yaw too.
  3D part: updatePerson sets g.rotation.y = c.yaw and has no turn math of its own; updateGovernor sets
        govV.g.rotation.y from governorAt(govTerr).yaw (0 when there is none); updateGovPool sets
        v.g.rotation.y = fig.yaw.

Run: python3 -m unittest tests.test_agent_city_facing </dev/null
"""

import math
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import REQUIRED, function_source, plan_views, run_sim  # noqa: E402

FACE_REQUIRED = REQUIRED + ("turnToward", "angleDiff", "faceWant", "TURN_RATE", "TURN_WALK_MAX", "goTo",
                            "freeAt", "findPath", "governorFigures", "govMove")


def diff(a, b):
    d = (b - a) % (2 * math.pi)
    return d - 2 * math.pi if d > math.pi else d


UNIT_DRIVER = r"""
const cases = [];
for (const [y, w] of [[0, 1], [0, -1], [3, -3], [-3, 3], [2.9, -2.9], [0.1, 0.1], [1, 1 + 4 * Math.PI], [-6, 6]])
  cases.push({ y, w, d: angleDiff(y, w), one: turnToward(y, w, 1 / 60), half: turnToward(turnToward(y, w, 1 / 120), w, 1 / 120),
    big: turnToward(y, w, 0.1), far: turnToward(y, w, 5) });
let y = 0; for (let i = 0; i < 24; i++) y = turnToward(y, Math.PI, 1 / 60);   // 0.4 s, 180 deg
let y2 = 0; for (let i = 0; i < 6; i++) y2 = turnToward(y2, Math.PI, 1 / 60);  // 0.1 s
__out = { cases, after04: y, after01: y2, keep: turnToward(1.2, null, .1), keepU: turnToward(1.2, undefined, .1),
  RATE: TURN_RATE, MAX: TURN_WALK_MAX };
"""


class TestTurnMath(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(UNIT_DRIVER, {}, FACE_REQUIRED)

    def test_constants(self):
        self.assertTrue(10 <= self.r["RATE"] <= 24, self.r["RATE"])
        self.assertTrue(math.pi / 4 - 1e-9 <= self.r["MAX"] <= math.pi / 3 + 1e-9, self.r["MAX"])

    def test_angle_diff_wraps(self):
        for c in self.r["cases"]:
            with self.subTest(case=(c["y"], c["w"])):
                self.assertGreater(c["d"], -math.pi - 1e-9)
                self.assertLessEqual(c["d"], math.pi + 1e-9)
                self.assertAlmostEqual(c["d"], diff(c["y"], c["w"]), places=9)

    def test_short_way_round_never_past(self):
        for c in self.r["cases"]:
            with self.subTest(case=(c["y"], c["w"])):
                want = diff(c["y"], c["w"])
                for k in ("one", "big", "far"):
                    moved = c[k] - c["y"]
                    if abs(want) < 1e-12:
                        self.assertAlmostEqual(moved, 0, places=9)
                        continue
                    self.assertGreaterEqual(moved * want, -1e-12, "%s: turns the short way" % k)
                    self.assertLessEqual(abs(moved), abs(want) + 1e-9, "%s: never past the target" % k)
                self.assertAlmostEqual(diff(c["far"], c["w"]), 0, places=3, msg="5 s: there")

    def test_frame_rate_independent(self):
        for c in self.r["cases"]:
            with self.subTest(case=(c["y"], c["w"])):
                self.assertAlmostEqual(c["one"], c["half"], places=9)

    def test_fast_enough(self):
        self.assertLess(abs(diff(self.r["after04"], math.pi)), 0.05, "180 deg done in 0.4 s")
        self.assertLess(abs(diff(self.r["after01"], math.pi)), math.pi - math.radians(60), "60 deg in the first 0.1 s")

    def test_no_want_keeps_the_facing(self):
        self.assertEqual(self.r["keep"], 1.2)
        self.assertEqual(self.r["keepU"], 1.2)


JUDGE = r"""
// every step is judged here (the harness pipe holds 64 KB, not every step): n steps; off60 = steps more than
// 60 deg off the facing; late = steps 0.35 s or more into a leg, off8 = those more than 8 deg off; first 5 of each kept.
function summary(){ return { n: 0, off60: 0, late: 0, off8: 0, ex60: [], ex8: [] }; }
function offBy(dx, dz, yaw){ let d = (yaw - Math.atan2(dx, dz)) % (2 * Math.PI); if (d > Math.PI) d -= 2 * Math.PI; if (d < -Math.PI) d += 2 * Math.PI; return Math.abs(d); }
function judge(S, dx, dz, yaw, legT, who){
  const off = offBy(dx, dz, yaw); S.n++;
  if (!(off <= Math.PI / 3 + 1e-6)) { S.off60++; if (S.ex60.length < 5) S.ex60.push([who, +off.toFixed(3), +legT.toFixed(2)]); }
  if (legT >= 0.35) { S.late++; if (!(off <= 8 * Math.PI / 180)) { S.off8++; if (S.ex8.length < 5) S.ex8.push([who, +off.toFixed(3), +legT.toFixed(2)]); } }
}
"""


# Citizens walk between random free points (several at once, at a real frame step and at 0.1 s); every
# tick records what each did: the step it took (dx, dz), its yaw after the tick, and how long it has
# been on its current leg (the same next point). A builder then stands at its plot.
WALK_DRIVER = (r"""
const V = __payload.view, T = V.territories[0], tid = T.id, DT = __payload.dt;
function buildLand(view){ landState(view); }
__JUDGE__
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: tid }, govs: [{ terr: tid, state: 'busy' }], governors: 1,
  asks: [], shows: [], agents: [] });
const ids = ['w1', 'w2', 'w3'];
for (const id of ids) apply({ type: 'spawn', id, role: 'worker', label: 'worker', task: id, terr: tid });
for (let i = 0; i < Math.round(3 / DT); i++) update(DT);
let seed = 11; const lcg = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const pts = [];
for (let r = 0; r < V.h; r++) for (let c = 0; c < V.w; c++) {
  const x = V.x0 + c + .5, z = V.z0 + r + .5;
  if (Math.hypot(x - T.cx, z - T.cz) < 8 && freeAt(x, z)) pts.push([x, z]);
}
const steps = summary(), legT = {}, legKey = {};
let walks = 0;
for (let round = 0; round < 6; round++) {
  for (const id of ids) {
    const c = byId(id), p = pts[Math.floor(lcg() * pts.length)];
    goTo(c, { x: p[0], y: p[1] }, 'back'); walks++;
  }
  for (let i = 0; i < Math.round(14 / DT); i++) {
    const before = ids.map(id => { const c = byId(id); return [c.x, c.y, c.path.length ? c.path[0][0] + ',' + c.path[0][1] : '']; });
    update(DT);
    ids.forEach((id, k) => {
      const c = byId(id), [x0, y0, key] = before[k];
      if (key !== legKey[id]) { legKey[id] = key; legT[id] = 0; }
      legT[id] += DT;
      const dx = c.x - x0, dz = c.y - y0;
      if (key && Math.hypot(dx, dz) > 1e-4) judge(steps, dx, dz, c.yaw, legT[id], id);
    });
  }
}
// a builder at its plot faces the building
const taken = new Set((T.buildings || []).map(b => b.plot));
const plot = (T.plots || []).find(p => !taken.has(p.k));
apply({ type: 'build', id: 'w1', terr: tid, plot: plot.k, btype: plot.d, x: plot.x, z: plot.z, by: 'worker' });
for (let i = 0; i < Math.round(30 / DT); i++) { update(DT); if (byId('w1').state === 'building' && !byId('w1').path.length) break; }
for (let i = 0; i < Math.round(1 / DT); i++) update(DT);
const b = byId('w1');
const want = b.bld ? Math.atan2(b.bld.gx + .5 - b.x, b.bld.gy + .5 - b.y) : null;
__out = { steps, walks, yaw0: typeof byId('w2').yaw, build: { state: b.state, hasBld: !!b.bld, yaw: b.yaw, want, faceWant: faceWant(b) },
  standNull: faceWant(Object.assign({}, byId('w3'), { state: 'working', bld: null, path: [] })) };
""").replace("__JUDGE__", JUDGE)


class TestCitizensFaceWhereTheyWalk(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        views = plan_views()
        cls.view = views[sorted(views)[0]]
        cls.runs = {dt: run_sim(WALK_DRIVER, {"view": cls.view, "dt": dt}, FACE_REQUIRED) for dt in (1 / 30, 0.1)}

    def test_they_really_walk(self):
        for dt, r in self.runs.items():
            with self.subTest(dt=dt):
                self.assertGreater(r["steps"]["n"], 200, "enough walking to judge")
                self.assertEqual(r["yaw0"], "number", "every citizen has c.yaw")

    def test_never_a_step_sideways_or_backwards(self):
        for dt, r in self.runs.items():
            with self.subTest(dt=dt):
                s = r["steps"]
                self.assertEqual(s["off60"], 0, "%d of %d steps more than 60 deg off, e.g. %s" % (s["off60"], s["n"], s["ex60"]))

    def test_faces_the_way_once_on_a_leg(self):
        for dt, r in self.runs.items():
            with self.subTest(dt=dt):
                s = r["steps"]
                self.assertGreater(s["late"], 50)
                self.assertEqual(s["off8"], 0, "%d of %d steps 0.35 s into a leg more than 8 deg off, e.g. %s"
                                 % (s["off8"], s["late"], s["ex8"]))

    def test_a_builder_faces_its_building(self):
        for dt, r in self.runs.items():
            with self.subTest(dt=dt):
                b = r["build"]
                self.assertEqual(b["state"], "building")
                self.assertTrue(b["hasBld"])
                self.assertAlmostEqual(b["faceWant"], b["want"], places=6)
                self.assertLess(abs(diff(b["yaw"], b["want"])), 0.05, "faces the work after 1 s")

    def test_nothing_to_face_keeps_the_facing(self):
        self.assertIsNone(self.runs[0.1]["standNull"])


# A present governor with nothing to do strolls after IDLE_STROLL_SEC; every tick records his step and yaw.
GOV_DRIVER = (r"""
const V = __payload.view, T = V.territories[0], tid = T.id, DT = 1 / 30;
function buildLand(view){ landState(view); }
__JUDGE__
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: tid }, govs: [{ terr: tid, state: 'idle' }], governors: 1,
  asks: [], shows: [], agents: [] });
const steps = summary(), legT = { t: 0, k: '' };
let figMatch = true, atMatch = true, moved = 0;
for (let i = 0; i < Math.round(120 / DT); i++) {
  const m0 = govMove.get(tid), x0 = m0 ? m0.x : 0, y0 = m0 ? m0.y : 0, key = m0 && m0.path.length ? m0.path[0].join(',') : '';
  update(DT);
  const m = govMove.get(tid); if (!m) continue;
  if (key !== legT.k) { legT.k = key; legT.t = 0; } legT.t += DT;
  const dx = m.x - x0, dz = m.y - y0;
  if (key && Math.hypot(dx, dz) > 1e-4) { judge(steps, dx, dz, m.yaw, legT.t, 'gov'); moved += Math.hypot(dx, dz); }
  const f = governorFigures().find(g => g.terr === tid), a = governorAt(tid);
  if (!f || typeof m.yaw !== 'number' || f.yaw !== m.yaw) figMatch = false;
  if (!a || typeof m.yaw !== 'number' || a.yaw !== m.yaw) atMatch = false;
}
const m = govMove.get(tid);
__out = { steps, moved, figMatch, atMatch, end: m ? { yaw: m.yaw, phase: m.phase, path: m.path.length } : null };
""").replace("__JUDGE__", JUDGE)


class TestGovernorFacesWhereHeWalks(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        views = plan_views()
        cls.r = run_sim(GOV_DRIVER, {"view": views[sorted(views)[0]]}, FACE_REQUIRED)

    def test_he_strolls(self):
        self.assertGreater(self.r["moved"], 1.0, "an idle governor strolls within 120 s")

    def test_never_a_step_sideways_or_backwards(self):
        s = self.r["steps"]
        self.assertEqual(s["off60"], 0, "%d of %d steps more than 60 deg off, e.g. %s" % (s["off60"], s["n"], s["ex60"]))

    def test_faces_the_way_once_on_a_leg(self):
        s = self.r["steps"]
        self.assertGreater(s["late"], 10)
        self.assertEqual(s["off8"], 0, "%d of %d steps more than 8 deg off, e.g. %s" % (s["off8"], s["late"], s["ex8"]))

    def test_figures_and_governor_at_carry_the_yaw(self):
        self.assertTrue(self.r["figMatch"], "governorFigures() entries carry m.yaw")
        self.assertTrue(self.r["atMatch"], "governorAt() carries m.yaw")


class TestDrawnFromTheSim(unittest.TestCase):
    """The 3D part only copies the sim's facing onto the models."""

    def test_person(self):
        src = function_source("updatePerson") or ""
        self.assertRegex(src, r"\.rotation\.y\s*=\s*c\.yaw\b")
        self.assertNotIn("atan2(", src, "no turn math of its own")
        self.assertNotRegex(src, r"v\.yaw\s*\+=", "no per-frame share")

    def test_home_governor(self):
        self.assertRegex(function_source("updateGovernor") or "", r"govV\.g\.rotation\.y\s*=")

    def test_pool_governors(self):
        self.assertRegex(function_source("updateGovPool") or "", r"v\.g\.rotation\.y\s*=\s*fig\.yaw\b")

    def test_move_turns_before_it_steps(self):
        src = function_source("move") or ""
        self.assertIn("turnToward(", src)
        self.assertIn("TURN_WALK_MAX", src)
        gsrc = function_source("updateGovernors") or ""
        self.assertIn("turnToward(", gsrc)
        self.assertIn("TURN_WALK_MAX", gsrc)


if __name__ == "__main__":
    unittest.main()
