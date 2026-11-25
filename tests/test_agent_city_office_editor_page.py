"""Failing tests for city-office-2, the PAGE side of the room editor (requirements/city.md "Room editor"; owner yes on
mock/city-office-2-mock.html v2 + v3 floor materials, 2026-11-25). The server side and the exact rules:
tests/test_agent_city_office_layout.py (E1-E5). The page must give the same answers as the server, so the editor
can say "放不下" while the owner drags, and the server says the same when it saves.

The editor's look and behaviour are the mock's (its CSS and its editor code: KIND -> PIECES, checkLayout -> checkPlan,
enterArrange -> openEditor, leaveArrange -> closeEditor, renderArrBar -> renderEditor, arrRotate -> edRotate, ...,
matCanvas, makeThumbs, STYLES, pickSurface, the catalogue drag). The mock's own stand-ins are NOT ported (OVR, LAYOUT,
BY, UNDO, its fake save): the page saves through POST /api/design and the server's history.

CONTRACT (bin/agent-city.html)

G1 sim constants equal to the server's: PIECES (= LAYOUT_KINDS: {kind: {zh, walk, foot, seat (or null), min, max}}),
   FIXED_ZONES ([[zh, [x1, x2, z1, z2]], ...]), FIXED_BLOCKS ([[x1, z1, x2, z2, pad], ...]), FLOOR_MATERIALS.
G2 defaultPlan(nTm, nHelper, decor3) -> {items} equal to the server's default_layout (yaw in degrees, as in the file).
G3 checkPlan(plan) -> {ok: true} or {ok: false, i (0-based item or null), why (zh)}: the same verdict as the server's
   check_design for a v 2 design with that layout, and for a placing problem the same zh text.
G4 planOf(terr) -> the floor's v 2 design's layout when it has one, else defaultPlan(deskCount(terr), the assistant desk
   count as before, themeOf(terr).decor). seatOf / seatSpot / MEET spots / walkable / findPath all read planOf: the seats
   are the tm and helper items' seats in item order (turned with the item), the meeting spots are the 4 chairs of the
   meet item, and a desk that moved blocks its new place and frees its old one.
G5 themeOf(terr).materials -> {carpet, manager_floor, pantry_floor}, each a FLOOR_MATERIALS id; a missing or unknown one
   -> the base look's (plain, wood, tile). Data only.
G6 the 3D part (source): openEditor, closeEditor, renderEditor, edPlace, edRotate, edCopy, edRemove, edUndo, edRedo,
   edReset, edColor, edMaterial, edStyle, pickSurface, matCanvas, makeThumbs exist; markup id="edUI"; the old DIY form is
   gone (no dySave, dy-s0); STYLES has 6 presets, each with c (9 colours) and m (3 materials); matCanvas draws all 8
   materials; closeEditor posts '/api/design' with a v 2 design (layout and materials) and shows a 422's problems (their
   zh) in the editor's message line; the floor areas are drawn with the material textures.
"""

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from test_agent_city_people import run_sim, function_source  # noqa: E402

T1, T2 = "aaaa0001", "bbbb0002"
COLORS = {"accent": "#2E7D6B", "carpet": "#E4DCCB", "manager_floor": "#D9C2A0", "pantry_floor": "#EEEAE0",
          "desk": "#EFDAB5", "desk_leg": "#BBA27C", "chair": "#3E4560", "meeting_rug": "#A9BCE0", "manager_rug": "#C97B66"}


def page():
    with open(os.path.join(BIN, "agent-city.html"), encoding="utf-8") as fh:
        return fh.read()


def view(designs=None):
    return {"v": 2, "repos": [{"id": T1, "name": "shop", "here": True, "n": 0}, {"id": T2, "name": "blog", "here": True, "n": 1}],
            "floors": [T1, T2], "designs": designs or {}, "asked": [T1, T2]}


def agent(aid, role, terr, status=""):
    return {"id": aid, "role": role, "label": aid, "task": aid, "stuck": False, "waiting": False, "done": False,
            "status": status, "tools": {}, "terr": terr, "relay": "", "lead": "", "office": None, "up": "gov:" + terr}


SNAP = r"""
function snap(v, agents){ apply({ type: 'snapshot', world: v, agents: agents || [], govs: [], gov: { state: 'idle', terr: v.floors[0] },
  asks: [], governors: 0, adding: [], hist: {} }); }
"""


def sim(driver, payload, required=("officeState", "apply", "citizens")):
    return run_sim(SNAP + driver, payload, required=required)


def base_items():
    return ac.default_layout(3, 1, ["none", "none", "none"])["items"]


def cases():
    """Layouts with the server's verdict: (name, items, first layout problem zh or None)."""
    out = []
    def add(name, items):
        probs = [p for p in ac.check_design({"v": 2, "name": "x", "colors": COLORS, "layout": {"items": items}})
                 if p["field"].startswith("layout")]
        out.append((name, items, probs[0]["zh"] if probs else None))
    add("default", base_items())
    it = base_items(); it[0] = dict(it[0], x=6.8, z=0.0); add("out", it)
    it = base_items(); it[0] = dict(it[0], x=-1.0, z=-5.6); add("lift", it)
    it = base_items(); it[1] = dict(it[1], x=it[0]["x"] + 0.4, z=it[0]["z"]); add("overlap", it)
    it = base_items(); it[0] = {"k": "tm", "x": -6.2, "z": 5.6, "yaw": 0}; it.append({"k": "decor", "id": "safe", "x": -4.8, "z": 6.1, "yaw": 90}); add("boxed", it)
    it = [dict(i, yaw=90) if i["k"] == "tm" else i for i in base_items()]; add("turned", it)
    it = base_items() + [{"k": "plant", "x": -5.7, "z": -0.6, "yaw": 0}]; add("plant on chair", it)
    it = base_items() + [{"k": "decor", "id": "cashier", "x": 0.4, "z": 2.8, "yaw": 180}]; add("free decor", it)
    return out


class TestSameAsServer(unittest.TestCase):
    def test_constants(self):
        out = sim("__out = { P: PIECES, Z: FIXED_ZONES, B: FIXED_BLOCKS, M: FLOOR_MATERIALS };", {},
                  required=("PIECES", "FIXED_ZONES", "FIXED_BLOCKS", "FLOOR_MATERIALS"))
        server = {k: {"zh": v["zh"], "walk": list(v["walk"]), "foot": list(v["foot"]),
                      "seat": list(v["seat"]) if v["seat"] else None, "min": v["min"], "max": v["max"]}
                  for k, v in ac.LAYOUT_KINDS.items()}
        self.assertEqual(out["P"], server)
        self.assertEqual(out["Z"], [[z, list(r)] for z, r in ac.FIXED_ZONES])
        self.assertEqual(out["B"], [list(b) for b in ac.FIXED_BLOCKS])
        self.assertEqual(out["M"], list(ac.FLOOR_MATERIALS))

    def test_default_plan(self):
        args = [(3, 1, ["none"] * 3), (7, 3, ["robot", "conveyor", "gears"]), (1, 2, ["none", "plants", "none"])]
        out = sim("__out = __payload.args.map(a => defaultPlan(a[0], a[1], a[2]));", {"args": args}, required=("defaultPlan",))
        self.assertEqual(out, [ac.default_layout(*a) for a in args])

    def test_check_plan(self):
        cs = cases()
        out = sim("__out = __payload.cases.map(c => checkPlan({ items: c[1] }));", {"cases": cs}, required=("checkPlan",))
        for (name, _, why), got in zip(cs, out):
            with self.subTest(case=name):
                self.assertEqual(got["ok"], why is None, got)
                if why:
                    self.assertEqual(got["why"], why)
        self.assertTrue(any(c[2] for c in cs) and any(c[2] is None for c in cs), "the cases cover both verdicts")


class TestPlanOnTheFloor(unittest.TestCase):
    def test_plan_of_and_seats(self):
        items = base_items()
        items[0] = {"k": "tm", "x": -6.2, "z": 5.6, "yaw": 90}
        items[1] = {"k": "tm", "x": 0.4, "z": 2.8, "yaw": 180}
        meet = next(i for i in items if i["k"] == "meet")
        meet.update(x=-2.8, z=3.0)
        d2 = {"v": 2, "name": "自由", "colors": COLORS, "layout": {"items": items},
              "materials": {"carpet": "wood", "manager_floor": "marble", "pantry_floor": "lava"}}
        self.assertEqual([p for p in ac.check_design(dict(d2, materials={"carpet": "wood", "manager_floor": "marble", "pantry_floor": "checker"}))], [])
        out = sim("""
snap(__payload.view, __payload.agents);
const t1 = __payload.t1, t2 = __payload.t2;
const c0 = byId('s:a'), c1 = byId('s:b');
const loc = s => [Math.round(s.x * 100) / 100, Math.round(s.y * 100) / 100];
__out = { plan: planOf(t1).items.length, def: planOf(t2).items.filter(i => i.k === 'tm').length,
          s0: loc(seatOf(c0)), s1: loc(seatOf(c1)), meet: MEET.length,
          oldFree: walkable(-5.7, -1.3), newBlocked: walkable(-6.2, 5.6),
          mats: themeOf(t1).materials, matsDefault: themeOf(t2).materials };
""", {"view": view({T1: d2}), "t1": T1, "t2": T2,
      "agents": [agent("s:a", "task-manager", T1), agent("s:b", "task-manager", T1), agent("s:c", "task-manager", T2)]},
            required=("planOf", "seatOf", "walkable", "themeOf", "byId"))
        self.assertEqual(out["plan"], len(items))
        self.assertEqual(out["def"], 2, "no v 2 design: the default plan, one desk more than managers")
        # desk 1 turned 90: its seat is at local (0, 0.78) -> (x + 0.78, z)
        self.assertEqual(out["s0"], [round(-6.2 + 0.78, 2), 5.6])
        # desk 2 turned 180: (x, z - 0.78)
        self.assertEqual(out["s1"], [0.4, round(2.8 - 0.78, 2)])
        self.assertTrue(out["oldFree"], "the old desk place is free")
        self.assertFalse(out["newBlocked"], "the desk's new place blocks")
        self.assertEqual(out["mats"], {"carpet": "wood", "manager_floor": "marble", "pantry_floor": "tile"}, "unknown -> base")
        self.assertEqual(out["matsDefault"], {"carpet": "plain", "manager_floor": "wood", "pantry_floor": "tile"})


class TestEditorSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = page()

    def fn(self, name):
        src = function_source(name)
        self.assertIsNotNone(src, name + " is missing")
        return src

    def test_functions_and_markup(self):
        for n in ("openEditor", "closeEditor", "renderEditor", "edPlace", "edRotate", "edCopy", "edRemove", "edUndo", "edRedo",
                  "edReset", "edColor", "edMaterial", "edStyle", "pickSurface", "matCanvas", "makeThumbs"):
            self.fn(n)
        self.assertRegex(self.text, r'id="edUI"')
        for old in ("dySave", "dy-s0", "saveDiy"):
            self.assertNotIn(old, self.text, "the DIY form is replaced by the editor")

    def test_styles_and_materials(self):
        m = re.search(r"const STYLES\s*=\s*\[(.*?)\n\];", self.text, re.S)
        self.assertIsNotNone(m)
        self.assertEqual(len(re.findall(r"\bm\s*:\s*\{", m.group(1))), 6)
        self.assertEqual(len(re.findall(r"\bc\s*:\s*\{", m.group(1))), 6)
        mc = self.fn("matCanvas")
        for mat in ac.FLOOR_MATERIALS:
            self.assertIn("'" + mat + "'", mc)

    def test_save(self):
        src = self.fn("closeEditor")
        self.assertIn("'/api/design'", src)
        self.assertRegex(src, r"v\s*:\s*2")
        self.assertIn("layout", src)
        self.assertIn("materials", src)
        self.assertIn("problems", src)


if __name__ == "__main__":
    unittest.main()
