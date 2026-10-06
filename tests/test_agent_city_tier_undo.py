"""city-tier was undone (requirements/city.md, "Growth"). A world.json that the
tier version wrote must still load in this server: no error, no moved-aside
file, the buildings kept, and every land takes one cell again.

The tier file: top-level "tiers": true; per land "tier", "cells", "count"; the
slots of the big lands spread out (a 3x3 or 2x2 square of cells).
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402

TERR_CHARS = set("grPH")


def tier_world():
    """Three lands as the tier version saved them: a 3x3 land, a 2x2 land, a
    small one. Slots are spread out so the squares do not overlap."""
    ps = ac.load_plans()
    w = ac.new_world()
    for ident, lines in (("/a/big/.git", 40), ("/b/mid/.git", 40), ("/c/small/.git", 40)):
        ac.add_territory(w, ps, ident, ac.repo_name(ident), lines)
    ac.build(w, ps, "/a/big/.git", "ui", "a1", "worker", 1.0)
    ac.build(w, ps, "/b/mid/.git", "test", "b1", "worker", 2.0)
    shape = {"/a/big/.git": ([0, 0], 3, 3, 90000),
             "/b/mid/.git": ([4, 0], 2, 2, 20000),
             "/c/small/.git": ([7, 0], 1, 1, 300)}
    for ident, (slot, cells, tier, count) in shape.items():
        t = w["territories"][ident]
        t["slot"] = slot
        t["tier"] = tier
        t["cells"] = cells
        t["count"] = count
    w["tiers"] = True
    return json.loads(json.dumps(w))


class TestTierWorldLoads(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_tier_undo_")
        self.path = os.path.join(self.base, "world.json")
        self.world = tier_world()
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.world, fh)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_loads_without_error_and_keeps_its_buildings(self):
        loaded, notice = ac.load_world(self.path, ac.load_plans())
        self.assertIsNone(notice)
        self.assertEqual(os.listdir(self.base), ["world.json"], "the file was moved aside")
        self.assertEqual(sorted(loaded["territories"]), sorted(self.world["territories"]))
        for ident, t in self.world["territories"].items():
            self.assertEqual(loaded["territories"][ident]["buildings"], t["buildings"])
        self.assertEqual(len(loaded["territories"]["/a/big/.git"]["buildings"]), 1)
        self.assertEqual(len(loaded["territories"]["/b/mid/.git"]["buildings"]), 1)

    def test_every_land_takes_one_cell(self):
        loaded, _ = ac.load_world(self.path, ac.load_plans())
        view = ac.layout(loaded, ac.load_plans())
        self.assertEqual(len(view["territories"]), 3)
        for t in view["territories"]:
            tiles = set()
            for x in range(view["x0"], view["x0"] + view["w"]):
                for z in range(view["z0"], view["z0"] + view["h"]):
                    if view["rows"][z - view["z0"]][x - view["x0"]] in TERR_CHARS \
                            and abs(x - t["cx"]) < 13 and abs(z - t["cz"]) < 13:
                        tiles.add((x, z))
            self.assertTrue(tiles, t["name"])
            for x, z in tiles:
                self.assertTrue(abs(x - t["cx"]) <= 11 and abs(z - t["cz"]) <= 11,
                                "%s reaches outside its one cell at %s" % (t["name"], (x, z)))

    def test_a_city_state_starts_on_the_tier_file(self):
        state = ac.CityState(world_path=self.path, plans=ac.load_plans(),
                             decisions_path=os.path.join(self.base, "decisions.jsonl"))
        self.assertIsNone(state.notice)
        self.assertEqual(sorted(state.world["territories"]), sorted(self.world["territories"]))


if __name__ == "__main__":
    unittest.main()
