"""Failing tests for city-office-2, the SERVER side of the room editor (requirements/city.md, "Room editor" and the
Floor design table's v 2 rows; owner yes on mock/city-office-2-mock.html v2 2026-11-25 plus floor materials, v3).
The page side: tests/test_agent_city_office_editor_page.py, which also checks that the page and the server give the
same answer for the same layout.

CONTRACT (bin/agent_city.py)

E1 constants (the page has the same numbers: PIECES, FIXED_ZONES, FIXED_BLOCKS, FLOOR_MATERIALS)
  LAYOUT_KINDS = {kind: {"zh", "walk": (x1, x2, z1, z2), "foot": (x1, x2, z1, z2), "seat": (x, z) or None, "min", "max"}}
    tm     经理桌  walk (-0.75, 0.75, -0.4, 0.4)    foot (-0.75, 0.75, -0.4, 1.1)    seat (0, 0.78)  1..9
    helper 助理桌  walk (-0.6, 0.6, -0.38, 0.38)    foot (-0.6, 0.6, -0.38, 1.05)    seat (0, 0.74)  1..3
    meet   会议桌  walk (-0.95, 0.95, -0.95, 0.95)  foot (-1.6, 1.6, -1.6, 1.6)      None            1..1
    decor  摆设    walk = foot (-0.8, 0.8, -0.45, 0.45)                              None            0..8
    plant  植物    walk (-0.3, 0.3, -0.3, 0.3)      foot (-0.32, 0.32, -0.32, 0.32)  None            0..8
    Local rectangles, front toward +z; a plant's are scaled by its "s".
  FIXED_ZONES = (("电梯", (-2.85, 0.75, -7, -5.0)), ("区经理室", (1.5, 7, -7, -2.85)), ("区经理室的门口", (1.9, 3.3, -2.95, -2.15)),
                 ("茶水间", (-7, -3.3, -7, -3.3)), ("白板", (6.6, 7, 2.3, 5.7)))        each (x1, x2, z1, z2)
  FIXED_BLOCKS: the walk-grid blocks of the fixed things, (x1, z1, x2, z2, pad) each, exactly the mock's 12.
  FLOOR_MATERIALS = ("plain", "wood", "herringbone", "tile", "bigtile", "marble", "concrete", "checker")

E2 a layout
  An item: {"k": kind, "x": number, "z": number, "yaw": 0|90|180|270} (+ "id" for decor, + "s" 0.6..1.2 for a plant, optional,
  default 1). Turning by yaw degrees: local (lx, lz) -> (x + lx cos a + lz sin a, z - lx sin a + lz cos a).
  default_layout(n_tm, n_helper, decor3) -> {"items": [...]}: n_tm manager desks at x (-5.7, -3.2, -0.7) by z (-1.3, 1.6, 4.5),
    row by row; n_helper assistant desks at x 2.9 + 1.5 k, z -1.6; the meeting table at (4.6, 4.0); a plant (s 1) at
    (-3.2, 5.0) when n_tm < 7; a plant (s 0.7) at (1.3, 6.5); then for each decor3 entry that is not "none" a decor piece
    at its slot (south-west (-5.2, 6.35) yaw 180, south middle (-1.6, 6.35) yaw 180, east wall (6.45, 0.75) yaw 270).
    Every yaw 0 unless said. It always passes check_design.

E3 check_design, v 2: {"v": 2, "name", "why"?, "colors", "materials"?, "layout": {"items": [...]}}; "decor" is v 1 only.
  colors as v 1 (same 9 keys, same lightness rule). materials: a dict with exactly carpet, manager_floor, pantry_floor, each
  one of FLOOR_MATERIALS. layout: a dict with exactly "items", a list of at most 40 items.
  Item problems (field "layout.items.<n>", n from 1): a kind that is not one of the five, a missing or unknown key, x or z
    not a number (a bool is not one) or with more than 2 decimals (the editor snaps to 0.2; the default plan uses
    0.05 steps), yaw not one of 0/90/180/270, decor without a FLOOR_DECOR id,
    s out of 0.6..1.2.
  Count problems (field "layout"): fewer than min or more than max of a kind.
  Placing problems, checked only when every item is well-formed, in this order, the first one found:
    1 an item's foot leaves -6.95..6.95  -> "layout.items.<n>", zh 「<name>」出了楼层
    2 an item's foot meets a fixed zone   -> "layout.items.<n>", zh 「<name>」压到<zone>了，那里是固定的
    3 two feet meet (more than 0.02 deep) -> "layout.items.<n>" (the later one), zh 「<a>」跟「<b>」叠在一起了
    4 the walk grid (CELL 0.4, N 35, ORG -7, a cell with |centre| > 6.55 blocked, blockRect pad default 0.18): the
      FIXED_BLOCKS, then every item's walk rectangle with pad 0.1 for the meeting table and 0.12 for the rest; flood
      8-way (no corner cutting) from the free cell nearest to (-1.85, -5.7). A place is reached when its cell is free
      and flooded, or the nearest free cell is within 1.5 cells and flooded. Every seat (item order), then any of the
      meeting table's 4 chairs (1.35 from its centre at 45°, 135°, 225°, 315°), then (4.6, -4.2), then (-5.6, -5.8):
      「<name>」的座位被挡住了，从电梯走不过去 (field of that item) / 会议桌被围住了，从电梯走不过去 / 去区经理室的路被挡住了 /
      去茶水间的路被挡住了 (field "layout").
  <name>: 经理桌 <n> / 助理桌 <n> (n = its place among its kind, from 1), 会议桌, 植物, or the decor's zh name (DECOR_ZH).
  A v 1 design is checked as before.
E4 FLOOR_RULES also explains v 2: "layout", "items", every kind, "2 decimals", "yaw", "90", the counts, every fixed zone in
  English (the lift, the area manager's room and its door, the pantry, the whiteboard), "every seat", "from the lift",
  "materials" and every FLOOR_MATERIALS id.
E5 demo_world() has at least one v 2 design with materials (the demo shows the editor's result).
"""

import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402

COLORS = {"accent": "#2E7D6B", "carpet": "#E4DCCB", "manager_floor": "#D9C2A0", "pantry_floor": "#EEEAE0",
          "desk": "#EFDAB5", "desk_leg": "#BBA27C", "chair": "#3E4560", "meeting_rug": "#A9BCE0", "manager_rug": "#C97B66"}


def design(items, **kw):
    d = {"v": 2, "name": "自由摆放", "colors": dict(COLORS), "layout": {"items": items}}
    d.update(kw)
    return d


def base_items():
    return ac.default_layout(3, 1, ["none", "none", "none"])["items"]


def fields(obj):
    probs = ac.check_design(obj)
    for p in probs:
        assert p.get("zh") and p.get("en"), p
    return probs


class TestConstants(unittest.TestCase):
    def test_kinds(self):
        K = ac.LAYOUT_KINDS
        self.assertEqual(set(K), {"tm", "helper", "meet", "decor", "plant"})
        self.assertEqual((K["tm"]["zh"], tuple(K["tm"]["walk"]), tuple(K["tm"]["foot"]), tuple(K["tm"]["seat"]), K["tm"]["min"], K["tm"]["max"]),
                         ("经理桌", (-0.75, 0.75, -0.4, 0.4), (-0.75, 0.75, -0.4, 1.1), (0, 0.78), 1, 9))
        self.assertEqual((K["helper"]["min"], K["helper"]["max"], tuple(K["helper"]["seat"])), (1, 3, (0, 0.74)))
        self.assertEqual((K["meet"]["min"], K["meet"]["max"], K["meet"]["seat"]), (1, 1, None))
        self.assertEqual((K["decor"]["min"], K["decor"]["max"]), (0, 8))
        self.assertEqual((K["plant"]["min"], K["plant"]["max"]), (0, 8))

    def test_fixed(self):
        self.assertEqual([z[0] for z in ac.FIXED_ZONES], ["电梯", "区经理室", "区经理室的门口", "茶水间", "白板"])
        self.assertEqual(tuple(ac.FIXED_ZONES[0][1]), (-2.85, 0.75, -7, -5.0))
        self.assertEqual(len(ac.FIXED_BLOCKS), 12)
        self.assertEqual(ac.FLOOR_MATERIALS, ("plain", "wood", "herringbone", "tile", "bigtile", "marble", "concrete", "checker"))


class TestDefault(unittest.TestCase):
    def test_shape(self):
        items = ac.default_layout(4, 2, ["robot", "none", "plants"])["items"]
        tm = [(i["x"], i["z"]) for i in items if i["k"] == "tm"]
        self.assertEqual(tm, [(-5.7, -1.3), (-3.2, -1.3), (-0.7, -1.3), (-5.7, 1.6)])
        self.assertEqual([(i["x"], i["z"]) for i in items if i["k"] == "helper"], [(2.9, -1.6), (4.4, -1.6)])
        self.assertEqual([(i["x"], i["z"]) for i in items if i["k"] == "meet"], [(4.6, 4.0)])
        self.assertEqual([(i["x"], i["z"], i.get("s", 1)) for i in items if i["k"] == "plant"], [(-3.2, 5.0, 1), (1.3, 6.5, 0.7)])
        self.assertEqual([(i["id"], i["x"], i["z"], i["yaw"]) for i in items if i["k"] == "decor"],
                         [("robot", -5.2, 6.35, 180), ("plants", 6.45, 0.75, 270)])
        self.assertTrue(all(i["yaw"] == 0 for i in items if i["k"] != "decor"))

    def test_no_plant_with_seven_desks(self):
        items = ac.default_layout(7, 1, ["none"] * 3)["items"]
        self.assertEqual(len([i for i in items if i["k"] == "plant"]), 1)

    def test_every_default_passes(self):
        for n_tm in range(1, 10):
            for n_h in (1, 2, 3):
                d = design(ac.default_layout(n_tm, n_h, ["robot", "conveyor", "gears"])["items"])
                self.assertEqual(ac.check_design(d), [], (n_tm, n_h))


class TestV2Shape(unittest.TestCase):
    def test_good(self):
        self.assertEqual(fields(design(base_items())), [])
        self.assertEqual(fields(design(base_items(), why="自己摆的",
                                       materials={"carpet": "wood", "manager_floor": "herringbone", "pantry_floor": "checker"})), [])

    def test_v1_still_works_and_decor_is_v1_only(self):
        v1 = {"v": 1, "name": "老版", "colors": dict(COLORS), "decor": ["robot", "none", "plants"]}
        self.assertEqual(fields(v1), [])
        bad = design(base_items(), decor=["robot", "none", "none"])
        self.assertIn("decor", [p["field"] for p in fields(bad)])
        v1_layout = dict(v1, layout={"items": base_items()})
        self.assertIn("layout", [p["field"] for p in fields(v1_layout)])

    def test_materials(self):
        f = [p["field"] for p in fields(design(base_items(), materials={"carpet": "lava", "manager_floor": "wood", "pantry_floor": "tile"}))]
        self.assertIn("materials.carpet", f)
        f = [p["field"] for p in fields(design(base_items(), materials={"carpet": "wood"}))]
        self.assertTrue(any(x.startswith("materials") for x in f))

    def test_item_shape(self):
        items = base_items()
        items[0] = {"k": "sofa", "x": 0, "z": 0, "yaw": 0}
        items[1] = dict(items[1], x=True)
        items[2] = dict(items[2], z=0.123)
        items[3] = dict(items[3], yaw=45)
        items.append({"k": "decor", "x": 0, "z": 2.0, "yaw": 0})
        items.append({"k": "plant", "x": 2.0, "z": 3.0, "yaw": 0, "s": 2})
        items.append({"k": "plant", "x": 2.0, "z": 3.6, "yaw": 0, "colour": "red"})
        f = {p["field"] for p in fields(design(items))}
        for n in (1, 2, 3, 4, len(items) - 2, len(items) - 1, len(items)):
            self.assertIn("layout.items.%d" % n, f)

    def test_layout_shape(self):
        for lay in (None, [], {"items": "x"}, {"items": [], "extra": 1}, {"items": [{"k": "tm"}] * 41}):
            self.assertTrue([p for p in fields(dict(design([]), layout=lay)) if p["field"].startswith("layout")], lay)

    def test_counts(self):
        def count_problem(items):
            return [p for p in fields(design(items)) if p["field"] == "layout"]
        items = [i for i in base_items() if i["k"] != "helper"]
        self.assertTrue(count_problem(items), "no assistant desk")
        items = [i for i in base_items() if i["k"] != "meet"]
        self.assertTrue(count_problem(items), "no meeting table")
        items = base_items() + [{"k": "decor", "id": "robot", "x": -6.0 + 0.0, "z": 0.0, "yaw": 0}] * 9
        self.assertTrue(count_problem(items), "9 decor")


class TestPlacing(unittest.TestCase):
    def one(self, items):
        probs = [p for p in fields(design(items)) if p["field"].startswith("layout")]
        self.assertEqual(len(probs), 1, probs)
        return probs[0]

    def test_out_of_the_floor(self):
        items = base_items()
        items[0] = dict(items[0], x=6.8, z=0.0)
        p = self.one(items)
        self.assertEqual((p["field"], p["zh"]), ("layout.items.1", "「经理桌 1」出了楼层"))

    def test_on_the_lift(self):
        items = base_items()
        items[0] = dict(items[0], x=-1.0, z=-5.6)
        p = self.one(items)
        self.assertEqual(p["zh"], "「经理桌 1」压到电梯了，那里是固定的")

    def test_overlap(self):
        items = base_items()
        items[1] = dict(items[1], x=items[0]["x"] + 0.4, z=items[0]["z"])
        p = self.one(items)
        self.assertEqual((p["field"], p["zh"]), ("layout.items.2", "「经理桌 2」跟「经理桌 1」叠在一起了"))

    def test_a_boxed_seat(self):
        items = base_items()
        items[0] = {"k": "tm", "x": -6.2, "z": 5.6, "yaw": 0}
        self.assertEqual(fields(design(items)), [], "the desk alone in the corner is fine")
        items.append({"k": "decor", "id": "safe", "x": -4.8, "z": 6.1, "yaw": 90})
        p = self.one(items)
        self.assertEqual((p["field"], p["zh"]), ("layout.items.1", "「经理桌 1」的座位被挡住了，从电梯走不过去"))
        items[-1] = dict(items[-1], x=-4.6)
        self.assertEqual(fields(design(items)), [], "0.2 further: a path again")

    def test_turned_desks(self):
        items = base_items()
        for i in items:
            if i["k"] == "tm":
                i["yaw"] = 90
        self.assertEqual(fields(design(items)), [], "turned desks in the open office still fit")

    def test_a_plant_on_a_chair_is_an_overlap(self):
        items = base_items()
        seat_z = items[0]["z"] + 0.78
        items.append({"k": "plant", "x": items[0]["x"], "z": round(round(seat_z / 0.2) * 0.2, 2), "yaw": 0})
        p = self.one(items)
        self.assertIn("叠在一起", p["zh"])


class TestRulesAndDemo(unittest.TestCase):
    def test_rules_text(self):
        t = ac.FLOOR_RULES
        for word in ("layout", "items", "tm", "helper", "meet", "decor", "plant", "2 decimals", "yaw", "90", "1 to 9", "1 to 3",
                     "lift", "area manager's room", "door", "pantry", "whiteboard", "every seat", "from the lift", "materials") + ac.FLOOR_MATERIALS:
            self.assertIn(word, t)

    def test_demo_has_a_v2_design(self):
        w = ac.demo_world()
        v2 = [d for d in w["designs"].values() if d.get("v") == 2]
        self.assertTrue(v2)
        for d in v2:
            self.assertEqual(ac.check_design(d), [])
            self.assertIn("materials", d)


if __name__ == "__main__":
    unittest.main()
