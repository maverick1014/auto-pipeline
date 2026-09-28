"""Failing tests for city-ux U7 (owner, 2026-09-28): "the gap between repos is too big, reduce it a bit;
the island for each repo is too big; with multiple repos it gets hard". Approved direction: mock
mock/city-ux-mock.html (U7 before / after); main manager 2026-09-28: the layout code in bin/agent_city.py
may change.

CONTRACT (bin/agent_city.py; the rest of tests/test_agent_city_world.py still holds, with CELL 22):

  CELL 22, HALF 11 (was 26 / 13): territories sit 22 tiles apart, hall centre at (22 i, 22 j). The five
  hand-made plans stay as they are (bin/agent-city-plans.json unchanged): their plots, offices and rest
  places all lie in the content box -8..7 (local tiles, x and z). layout() keeps every territory road
  ('r') inside that box: a plan road or exit past it is cut back to the box edge (the exit trunk then
  starts there), so a road never runs into the gap belt of the neighbour.
  Nothing else moves: same repo -> same plan, slot, shape (territory_tiles is untouched), same order.
  The outer edge, the gap belts and the coast stay organic, and a smaller cell must not eat the towns:
    - of the town tiles territory_tiles() gives inside the content box, at most 1% are drawn as void or
      sea (today, at 26: about 0.65%);
    - at most 2% of the open plots touch void or sea (today: about 1.4%).
  (Scale the outer-edge trim and the corner cut to the smaller cell as needed; the gap belt bend may
  stay -2..2: at HALF 11 it never reaches the box.)
  The page's DEMO_WORLD is the new `demo-world` output (tests/test_agent_city_page.py pins that).

Run: python3 -m unittest tests.test_agent_city_ux_layout </dev/null
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))

import agent_city as ac  # noqa: E402

BOX = range(-8, 8)
PLANS = ac.load_plans()
PLAN = {p["id"]: p for p in PLANS}


def world(n, tag, lines):
    w = ac.new_world()
    for k in range(n):
        t = ac.add_territory(w, PLANS, "/r/%s%d/.git" % (tag, k), "r%d" % k, lines)
        t["lines"] = t["peak"] = lines
    return w


def tile(v, x, z):
    r, c = z - v["z0"], x - v["x0"]
    return v["rows"][r][c] if 0 <= r < v["h"] and 0 <= c < v["w"] else " "


def sweep():
    for n in (1, 2, 3, 4, 6, 8):
        for tag in range(10):
            for lines in (0, 3000, 10 ** 6):
                w = world(n, "t%d_" % tag, lines)
                yield w, ac.layout(w, PLANS), lines


class TestTighterLayout(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.views = list(sweep())

    def test_cell(self):
        self.assertEqual((ac.CELL, ac.HALF), (22, 11))
        for w, v, _ in self.views[:40]:
            self.assertEqual(v["cell"], 22)
            for t in v["territories"]:
                self.assertEqual((t["cx"], t["cz"]), (22 * t["slot"][0], 22 * t["slot"][1]))

    def test_plan_content_fits_the_box(self):
        for p in PLANS:
            with self.subTest(plan=p["id"]):
                pts = [(x, z) for x, z, _ in p["plots"]] + [tuple(p["rest"])]
                pts += [tuple(o) for o in (p["offices"].values() if isinstance(p["offices"], dict) else p["offices"])]
                for x, z in pts:
                    self.assertIn(x, BOX)
                    self.assertIn(z, BOX)

    def test_roads_stay_in_the_box(self):
        for w, v, _ in self.views:
            for t in v["territories"]:
                for dx in range(-11, 11):
                    for dz in range(-11, 11):
                        if tile(v, t["cx"] + dx, t["cz"] + dz) == "r":
                            self.assertTrue(dx in BOX and dz in BOX,
                                            "road at local %s in %s" % ((dx, dz), t["plan"]))

    def test_towns_are_not_eaten(self):
        total = cut = 0
        for w, v, lines in self.views:
            ident = {ac.territory_id(i): i for i in w["territories"]}
            for t in v["territories"]:
                for x, z in ac.territory_tiles(PLAN[t["plan"]], ident[t["id"]], lines)["land"]:
                    if x in BOX and z in BOX:
                        total += 1
                        if tile(v, t["cx"] + x, t["cz"] + z) in " s":
                            cut += 1
        self.assertGreater(total, 10000)
        self.assertLessEqual(cut / total, .01, "%d of %d town tiles cut" % (cut, total))

    def test_plots_stay_on_land(self):
        total = bad = 0
        for w, v, _ in self.views:
            for t in v["territories"]:
                for p in t["plots"]:
                    total += 1
                    nb = [tile(v, p["x"] + a, p["z"] + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))]
                    if any(c in " s" for c in nb):
                        bad += 1
        self.assertLessEqual(bad / total, .02, "%d of %d plots touch void or sea" % (bad, total))

    def test_same_repo_same_place_and_shape(self):
        a, b = world(6, "same", 3000), world(6, "same", 3000)
        self.assertEqual(ac.layout(a, PLANS), ac.layout(b, PLANS))
        for ident, t in a["territories"].items():
            self.assertEqual((t["plan"], t["slot"]), (b["territories"][ident]["plan"], b["territories"][ident]["slot"]))

    def test_six_repos_take_less_room(self):
        _, v, _ = next(x for x in self.views if len(x[1]["territories"]) == 6)
        xs = [t["slot"][0] for t in v["territories"]]
        zs = [t["slot"][1] for t in v["territories"]]
        self.assertLessEqual(v["w"], (max(xs) - min(xs) + 1) * 22)
        self.assertLessEqual(v["h"], (max(zs) - min(zs) + 1) * 22 + ac.SEA_ROWS)


if __name__ == "__main__":
    unittest.main()
