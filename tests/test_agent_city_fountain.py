"""Failing tests for city-polish P5: the fountain's water flickers (owner screenshot, 2026-09-30).

Cause (task manager, headless frames of the demo, v4-plus): fantasy/fountain-round.glb has its pool floor at
y 0, the very plane of the ground it stands on; under the see-through water (material "Water", alpha .6, .14
above the floor) the floor and the ground fight for the same depth, so the pool shows light-cyan (ground) and
mid-blue (floor) stripes that move every frame. The cliff blocks had the same kind of fight with path and
river floors and got polygonOffset through instanced(..., { behind: true }); the fountain needs the other sign:
its floor must always win over the ground.

CONTRACT (bin/agent-city.html, 3D part)
  FRONT_KEYS: a Set of model keys whose floor lies on the ground and shows -- at least 'fantasy/fountain-round'.
  place(key, x, z, o) and instanced(key, items, o) with o.front: every mesh they make gets a cloned material
      (never the shared one of lib[key]) with polygonOffset = true, polygonOffsetFactor <= -1 and
      polygonOffsetUnits <= -1 (pulled toward the camera).
  buildLand passes front: true for every key in FRONT_KEYS, in both the systemsDecor loop and the restDecor
      loop (the fountain is a beauty item in a town/city, and the city rest place's centre piece).
  Headless proof (task manager): the same crop of the demo fountain over several frames shows one steady
      water colour after the fix.

Run: python3 -m unittest tests.test_agent_city_fountain </dev/null
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import function_source, page  # noqa: E402


def code():
    return re.sub(r"/\*.*?\*/", "", page(), flags=re.S)


class TestFountainFloorWins(unittest.TestCase):

    def test_front_keys_hold_the_fountain(self):
        m = re.search(r"const\s+FRONT_KEYS\s*=\s*new\s+Set\(\s*\[([^\]]*)\]\s*\)", code())
        self.assertIsNotNone(m, "const FRONT_KEYS = new Set([...])")
        self.assertIn("'fantasy/fountain-round'", m.group(1))

    def offset_ok(self, src, name):
        self.assertTrue("o.front" in src, name + " reads o.front")
        self.assertTrue(".clone()" in src, name + ": a cloned material, never the shared one")
        self.assertRegex(src, r"polygonOffset\s*[=:]\s*true", name)
        f = re.search(r"polygonOffsetFactor\s*[=:]\s*(-?\d+(?:\.\d+)?)", src[src.index("o.front"):] if "o.front" in src else "")
        u = re.search(r"polygonOffsetUnits\s*[=:]\s*(-?\d+(?:\.\d+)?)", src[src.index("o.front"):] if "o.front" in src else "")
        self.assertIsNotNone(f, name + ": polygonOffsetFactor for front")
        self.assertIsNotNone(u, name + ": polygonOffsetUnits for front")
        self.assertLessEqual(float(f.group(1)), -1, name + ": pulled toward the camera")
        self.assertLessEqual(float(u.group(1)), -1, name)

    def test_instanced_pulls_front_meshes_forward(self):
        self.offset_ok(function_source("instanced") or "", "instanced()")

    def test_place_pulls_front_meshes_forward(self):
        self.offset_ok(function_source("place") or "", "place()")

    def test_behind_is_kept(self):
        src = function_source("instanced") or ""
        self.assertIn("o.behind", src, "the cliff blocks keep their own offset")

    def test_build_land_passes_front_in_both_loops(self):
        src = function_source("buildLand") or ""
        i, j = src.find("systemsDecor"), src.find("restDecor(t)")
        self.assertGreater(i, -1)
        self.assertGreater(j, -1)
        self.assertGreaterEqual(src.count("FRONT_KEYS"), 2, "the systems loop and the rest loop both ask FRONT_KEYS")
        k = src.find("officeDecor(t)")
        rest_loop = src[j:k if k > j else len(src)]
        self.assertIn("FRONT_KEYS", rest_loop, "the rest place's fountain")
        self.assertIn("FRONT_KEYS", src[src.find("const sysBy"):j], "the beauty fountain")


if __name__ == "__main__":
    unittest.main()
