"""Failing test: the camera stays where the owner left it (owner bug on 6c823f4, port 4793).

Run: python3 -m unittest tests.test_agent_city_camera </dev/null
"""

import math
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import function_source, page, run_sim  # noqa: E402
from test_agent_city_chain import FEATURE_REQUIRED, TA, two_territory_view  # noqa: E402


# ---------------------------------------------------------------------------
# The camera stays where the owner left it (owner bug on 6c823f4, port 4793)
# ---------------------------------------------------------------------------
#
# Seen: after a drag to another angle the view "goes back to the original angle by itself".
# Task manager's headless check: nothing resets it (20 s after a drag, and after a server restart
# with an SSE reconnect, the dragged view stays). Cause: the never-stop rotation always turns the
# same way, so after a drag against that way it turns the view straight back over the old angle.
#
# CONTRACT (bin/agent-city.html, simulation section, no three.js):
#   cam = {az, el, dist, tx, tz}; dragBy(dx, dy) is what an orbit drag does (the pointer handler
#   calls it); cameraStep(dt) advances the camera one frame (auto-rotation, the quarter-turn tween);
#   frame() calls it. The rotation turns AUTO_ROT_SEC per turn in the direction of the owner's last
#   orbit drag (left or right), so it never turns the view back to where it was before the drag.
#   Nothing but the fit button (and the very first world) changes az/el/dist/tx/tz back: no live
#   event of any kind (snapshot, world, era, gov, governors, spawn, tool, build, relay, ask ...).

CAMERA_DRIVER = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta);
function buildLand(view){ landState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'idle' }], agents: [] });
const out = {};
for (const dir of [1, -1]) {
  dragBy(dir * 120, -60);
  const a0 = { az: cam.az, el: cam.el, dist: cam.dist, tx: cam.tx, tz: cam.tz };
  const events = [
    { type: 'snapshot', world: V, gov: { state: 'idle', terr: A.id }, governors: 1, asks: [], shows: [], govs: [{ terr: A.id, state: 'busy' }], agents: [] },
    { type: 'world', world: V }, { type: 'gov', terr: A.id, state: 'busy', present: true }, { type: 'governors', count: 1 },
    { type: 'spawn', id: 'x' + dir, role: 'worker', label: 'worker', task: 't', terr: A.id }, { type: 'tool', id: 'x' + dir, tool: 'Edit' },
    { type: 'relay', id: 'x' + dir, to: 'governor', lead: '' }, { type: 'relay_end', id: 'x' + dir, by: 'governor' },
    { type: 'done', id: 'x' + dir }, { type: 'ask', id: 'k' + dir, agent: 'gov', terr: A.id, kind: 'permission', phase: 'owner', why: 'permission', tool: 'Bash', what: 'ls', at: 1, detail: {} },
    { type: 'ask_closed', id: 'k' + dir, agent: 'gov', kind: 'permission', tool: 'Bash', what: 'ls', by: 'owner', verb: 'allow', text: '', reason: '', at: 2 } ];
  for (let s = 0; s < 600; s++) { if (s % 50 === 0 && events.length) apply(events.shift()); update(.1); cameraStep(.1); }
  out[dir] = { a0, a1: { az: cam.az, el: cam.el, dist: cam.dist, tx: cam.tx, tz: cam.tz } };
}
__out = Object.assign(out, { turn: AUTO_ROT_SEC });
"""


class TestCameraStaysWhereLeft(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(CAMERA_DRIVER, {"view": two_territory_view(), "ta": TA},
                        FEATURE_REQUIRED + ("cam", "dragBy", "cameraStep", "AUTO_ROT_SEC"))

    def test_rotation_goes_on_from_his_angle_the_way_he_dragged(self):
        step = 60 * 2 * math.pi / self.r["turn"]
        for key in ("1", "-1"):
            with self.subTest(drag=key):
                a0, a1 = self.r[key]["a0"], self.r[key]["a1"]
                moved = a1["az"] - a0["az"]
                self.assertAlmostEqual(abs(moved), step, delta=1e-6, msg="only the rotation moved it")
                # dragBy(+dx) turns az the same way as dragBy(+dx) did: never back over the old angle
                self.assertTrue(moved * (-1 if key == "1" else 1) > 0, "the rotation keeps the owner's direction")

    def test_tilt_zoom_and_target_unchanged(self):
        for key in ("1", "-1"):
            with self.subTest(drag=key):
                a0, a1 = self.r[key]["a0"], self.r[key]["a1"]
                for k in ("el", "dist", "tx", "tz"):
                    self.assertAlmostEqual(a0[k], a1[k], delta=1e-9, msg=k)

    def test_only_fit_first_world_and_start_reset(self):
        text = page()
        self.assertLessEqual(len(re.findall(r"(?<!function )\bresetCam\(\)", text)), 3,
                             "resetCam(): the first world, the fit button, the page start - nothing else")
        self.assertIn("cameraStep(", function_source("frame") or "")


if __name__ == "__main__":
    unittest.main()
