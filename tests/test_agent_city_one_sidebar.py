"""city-one-sidebar (requirements/city-one-sidebar.md, owner 2026-11-27) -- examples test, page bin/agent-city.html.

Item 2: a click on a person never moves or zooms the camera; the whole office stays in view. The person is marked
and their details open as today; zoom stays the user's own (the zoom buttons, the wheel, pinch).

  C1 desktop (1440 wide), the whole-floor view, click a person: same zoom, same look point, 3 s of frames later too;
     the person is selected, the window opens (afterSelect).
  C2 phone (390 wide): the same.
  C3 zoomed in and panned by hand, then click a person: the view stays at that zoom and that spot.
  C4 the same person clicked again: nothing moves, the person stays selected.
  C5 close (select nobody): nothing moved.
  C6 the area manager (gov:<floor>) clicked: nothing moves.
  C7 a rail row of a person on another floor: that floor shows at its whole-floor view (as the lift does), never
     zoomed or panned onto the person.
  C8 the selected person walks to another floor: the view stays on this floor (no camera follows anybody).

The driver runs the page's own select, stopFollow, stepCamMove, watchFollow and updateCamera (function_source) in node
with stand-ins for the scene: a floor is a set of people at (x, z) on it, goFloor shows a floor at its whole-floor view.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from citypage import function_source  # noqa: E402

PAGE_FUNCS = ("select", "stopFollow", "stepCamMove", "watchFollow", "updateCamera", "fitDist")

DRIVER = r"""
const fs = require('fs'), vm = require('vm');
const { fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
for (const c of cases) {
  const box = { Math, JSON, console, performance: { now: () => 0 }, RM: false,
    W: c.W, H: c.H, view: 'inside', cur: 'f1', follow: null, selected: null, camMove: null,
    viewShiftX: 0, viewShiftY: 0, railBoxNow: null, winBoxNow: null, liftBoxNow: null,
    cam: { az: -.62, el: .86, dist: 21, tx: 0, ty: 0, tz: .3, wantDist: null },
    camera: { position: { set(){} }, lookAt(){}, updateMatrixWorld(){}, aspect: 1, setViewOffset(){}, clearViewOffset(){},
      updateProjectionMatrix(){} },
    calls: [] };
  // who is where: f1 has p1 and p3, f2 has p2; the area manager of f1 stands by the door
  box.people = { p1: { at: 'f1', inLift: null, x: 4, z: -3 }, p3: { at: 'f1', inLift: null, x: -5, z: 2.5 },
    p2: { at: 'f2', inLift: null, x: 3, z: 4 }, 'gov:f1': { at: 'f1', inLift: null, x: -2, z: 5 } };
  box.rowPos = id => box.people[id] ? Object.assign({}, box.people[id]) : null;
  box.byId = id => box.people[id] ? { id } : null;
  box.isDrawn = () => true;
  box.selKey = s => !s ? null : s.t === 'c' ? s.id : s.t === 'gov' ? 'gov:' + s.terr : null;
  box.afterSelect = () => { box.calls.push(['afterSelect', box.selKey(box.selected)]); };
  box.enter = (at, cb) => { box.calls.push(['enter', at]); box.view = 'inside'; box.cur = at; if (cb) cb(); };
  // the page's goFloor: clearFigs(); buildFloor(); resetView(); cam.dist = cam.wantDist; cam.wantDist = null -- the whole floor
  box.goFloor = at => { box.calls.push(['goFloor', at]); box.cur = at;
    Object.assign(box.cam, { az: -.62, el: .86, tx: 0, ty: 0, tz: .3 }); box.cam.dist = box.fitDist(); box.cam.wantDist = null;
    box.follow = null; };
  box.refreshPanelBoxes = () => {};
  box.freeCentre = (W, H) => [W / 2, H / 2];
  vm.createContext(box);
  vm.runInContext(fns, box);
  const cam = box.cam;
  const snap = () => ({ dist: cam.dist, wantDist: cam.wantDist, tx: cam.tx, ty: cam.ty, tz: cam.tz, az: cam.az, el: cam.el });
  const frames = n => { for (let i = 0; i < n; i++) { box.watchFollow(); box.updateCamera(1 / 60); } };
  cam.dist = box.fitDist();                                  // the whole-floor view of this width
  if (c.hand) Object.assign(cam, c.hand);                    // the user's own zoom and pan
  frames(10);
  const before = snap(), r = { before, cur0: box.cur };
  for (const step of c.steps) {
    if (step[0] === 'select') box.select(step[1]);
    else if (step[0] === 'walk') box.people[step[1]] = Object.assign(box.people[step[1]], step[2]);
    else if (step[0] === 'frames') frames(step[1]);
  }
  r.after = snap(); r.fit = box.fitDist(); r.selected = box.selected; r.follow = box.follow; r.cur = box.cur;
  r.calls = box.calls;
  out[c.name] = r;
}
require('fs').writeSync(1, JSON.stringify(out));
"""

DESK = {"W": 1440, "H": 713}
PHONE = {"W": 358, "H": 714}   # a 390-wide phone: the stage is 358 x 714 (tests/test_agent_city_desks.py)
CASES = [
    dict(name="C1", steps=[["select", "p1"], ["frames", 180]], **DESK),
    dict(name="C2", steps=[["select", "p1"], ["frames", 180]], **PHONE),
    dict(name="C3", hand={"dist": 9, "tx": 1.5, "tz": -2}, steps=[["select", "p1"], ["frames", 180]], **DESK),
    dict(name="C3phone", hand={"dist": 12, "tx": -1, "tz": 1}, steps=[["select", "p3"], ["frames", 180]], **PHONE),
    dict(name="C4", steps=[["select", "p1"], ["frames", 60], ["select", "p1"], ["frames", 120]], **DESK),
    dict(name="C5", steps=[["select", "p1"], ["frames", 60], ["select", None], ["frames", 120]], **DESK),
    dict(name="C6", steps=[["select", "gov:f1"], ["frames", 180]], **DESK),
    dict(name="C7", hand={"dist": 9, "tx": 2, "tz": 2}, steps=[["select", "p2"], ["frames", 180]], **DESK),
    dict(name="C8", steps=[["select", "p1"], ["frames", 30], ["walk", "p1", {"at": "f2", "x": 1, "z": 1}],
                           ["frames", 150]], **DESK),
]


def run_cases():
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not installed")
    srcs = []
    for name in PAGE_FUNCS:
        src = function_source(name)
        if src is None:
            raise AssertionError("the page has no function %s" % name)
        srcs.append(src)
    with tempfile.TemporaryDirectory() as tmp:
        script, data = os.path.join(tmp, "drv.js"), os.path.join(tmp, "data.json")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(DRIVER)
        with open(data, "w", encoding="utf-8") as fh:
            json.dump({"fns": "\n".join(srcs), "cases": CASES}, fh)
        res = subprocess.run([node, script, data], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    if res.returncode != 0 or not res.stdout.strip():
        raise AssertionError("driver failed:\n" + res.stderr[-3000:])
    return json.loads(res.stdout)


class TestAClickKeepsTheView(unittest.TestCase):
    """Item 2: the camera stays where it was -- same zoom, same look point -- whatever was clicked."""

    @classmethod
    def setUpClass(cls):
        cls.out = run_cases()

    def assert_view_kept(self, name, ref=None):
        r = self.out[name]
        ref = ref or r["before"]
        for k in ("dist", "tx", "ty", "tz", "az", "el"):
            with self.subTest(case=name, key=k):
                self.assertAlmostEqual(r["after"][k], ref[k], places=6,
                                       msg="%s: cam.%s moved %s -> %s" % (name, k, ref[k], r["after"][k]))
        self.assertIsNone(r["after"]["wantDist"], "%s: no zoom is still on its way" % name)
        self.assertIsNone(r["follow"], "%s: the camera follows nobody" % name)

    def test_c1_desktop_click(self):
        self.assert_view_kept("C1")
        self.assertEqual(self.out["C1"]["selected"], {"t": "c", "id": "p1"})
        self.assertIn(["afterSelect", "p1"], self.out["C1"]["calls"], "the window opens as today")

    def test_c2_phone_click(self):
        self.assert_view_kept("C2")
        self.assertAlmostEqual(self.out["C2"]["after"]["dist"], self.out["C2"]["fit"], places=6,
                               msg="the phone keeps its whole-floor distance")
        self.assertEqual(self.out["C2"]["selected"], {"t": "c", "id": "p1"})

    def test_c3_hand_zoom_is_kept(self):
        self.assert_view_kept("C3")
        self.assertAlmostEqual(self.out["C3"]["after"]["dist"], 9, places=6)
        self.assert_view_kept("C3phone")
        self.assertAlmostEqual(self.out["C3phone"]["after"]["dist"], 12, places=6)

    def test_c4_same_person_again(self):
        self.assert_view_kept("C4")
        self.assertEqual(self.out["C4"]["selected"], {"t": "c", "id": "p1"}, "a second click keeps the person selected")

    def test_c5_close_moves_nothing(self):
        self.assert_view_kept("C5")
        self.assertIsNone(self.out["C5"]["selected"])

    def test_c6_area_manager(self):
        self.assert_view_kept("C6")
        self.assertEqual(self.out["C6"]["selected"], {"t": "gov", "terr": "f1"})

    def test_c7_other_floor_shows_whole_floor(self):
        r = self.out["C7"]
        self.assertIn(["goFloor", "f2"], r["calls"], "a row of another floor shows that floor, as the lift does")
        self.assertEqual(r["cur"], "f2")
        whole = {"dist": r["fit"], "tx": 0, "ty": 0, "tz": .3, "az": -.62, "el": .86}
        self.assert_view_kept("C7", ref=whole)
        self.assertEqual(r["selected"], {"t": "c", "id": "p2"})

    def test_c8_no_camera_goes_after_a_walker(self):
        r = self.out["C8"]
        self.assertEqual([c for c in r["calls"] if c[0] == "goFloor"], [], "the view stays on this floor")
        self.assertEqual(r["cur"], "f1")
        self.assert_view_kept("C8")


class TestSelectHasNoCameraWords(unittest.TestCase):
    """Item 2 (replaces city-office's 'select zoom is halved', mock v5): select() itself sets no zoom, no look point
    and no follow; a floor change it asks for goes through goFloor / enter (their whole-floor view)."""

    def test_select_sets_no_camera(self):
        src = function_source("select")
        self.assertIsNotNone(src)
        self.assertNotRegex(src, r"cam\.(wantDist|dist|tx|ty|tz|az|el)\s*=(?!=)", "select() never zooms or pans")
        self.assertNotRegex(src, r"\bfollow\s*=(?!=)(?!\s*null\b)", "select() locks the camera onto nobody")


if __name__ == "__main__":
    unittest.main()
