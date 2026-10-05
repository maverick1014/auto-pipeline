"""Failing tests for city-tier, the page (requirements/city.md, "Tiers", and the Arrange and Look lines it
changed; approved mock mock/city-tier-mock.html, "mock yes" 2026-10-02 17:07). The server lays the city out
and sends it in the world view (tests/test_agent_city_tier.py has the view's shape: per territory "tier",
"cells", "slot" = the square's north-west cell, "bg" = [[x, z, w, d, h, zone], ...], "rings", "mark"); the
page only draws it. Port the mock's look (its 3D part: buildWorld, landmark('pearl'), the night switch); its
own city generator (genCity) is NOT ported: the server's "bg" list replaces it.

CONTRACT (bin/agent-city.html). "sim section" = the page script from 'use strict' up to the '3D view.'
comment, driven in node (tests/test_agent_city_people.py run_sim). Everything else is "3D part", checked on
its source here and looked at in a browser by the task manager.

T1 a big land's square (sim)
  terrAtOf(view, X, Z) -> the terrain of the territory whose SQUARE holds tile (X, Z), else 'grassland'.
  cellTerrain(view, X, Z) -> that territory, else null. A square: cells (i .. i + cells - 1, j .. j + cells
    - 1) from its slot [i, j]; cell (a, b) holds the tiles a * cell - cell / 2 .. a * cell + cell / 2 - 1
    (cell = view.cell; cells missing = 1). (Replaces the old 26-tile cell guess.)
  terrMid(view, t) -> [x, z]: the middle of t's square in tile coordinates:
    [slot[0] * cell + (cells - 1) * cell / 2, slot[1] * cell + (cells - 1) * cell / 2]. One cell: its cx, cz.
  repoTags(view): x, z = terrMid minus the view's middle (as before for one cell: t.cx, t.cz minus it).
  zoomCells(view) -> the biggest "cells" of the view's territories (1 when none says).
  3D part: distLimit() never closer than spanDist(cell * zoomCells(map) * 1.15, W, H) (and never past
    distMax(), as before); a repo tag flies to its tag at Math.min(spanDist(cell * (cells > 1 ? cells *
    1.15 : 1), W, H), distLimit()): the whole big city in view.

T2 arranging squares (sim; requirements "Arrange")
  landsOf(view): every land also carries cells (t.cells, 1 when missing).
  landsOk(lands): every square inside the grid (-4..4), no two squares share a cell, no square on the row
    just south of a sea land's square (cells (i .. i + cells - 1, j + cells)).
  landPlace(lands, id, cell) -> [i, j]: where land ID's square goes for a drop on the free CELL: the
    squares that hold CELL, inside the grid, free of the other lands, keeping the sea rule both ways and
    touching (4 sides) another land; the one whose middle is nearest CELL's middle (a tie: the smaller j,
    then the smaller i); null when none. One cell: CELL itself when allowed.
  landMove(lands, id, cell) -> the request rows for a drop of land ID on CELL:
    CELL on another land B of the same cells -> [{id, slot: B.slot}, {id: B.id, slot: ID's slot}] (swap)
      when landsOk holds after it, else null;
    CELL on a land of another size -> the string 'size' (the bar says i18n('arr.errSize'); nothing is sent);
    CELL free -> [{id, slot: landPlace(...)}], null when landPlace is null;
    null when ID is no land of the list or CELL is a cell of ID's own square.
  landFree(lands, id) -> the free cells [[i, j], ...] a drop of land ID may land on: no square holds it and
    landMove(lands, id, cell) gives rows. id null -> as before (the free cells a one-cell land could take).
  The drag's footprint shows the whole square the land would take (3D part: arrOver uses landPlace).
  Words: arr.errSize (zh 大小不一样，不能对换).

T3 the hall card (sim + 3D part; decision 5: the level shows only there)
  tierWord(t) -> i18n('tier.' + t.tier) for tier 1..3, else i18n('era.' + (t.era || 'village')).
  linesText(n) -> zh: under 10,000 n.toLocaleString('en-US') + ' 行'; from 10,000 (n / 10000) to one
    decimal, a trailing '.0' dropped, + ' 万行' (1117407 -> '111.7 万行', 20000 -> '2 万行'); en:
    n.toLocaleString('en-US') + ' lines'.
  hallLine(t) -> tierWord(t) + ' · ' + linesText(t.lines || 0).
  Words (zh and en, each key once per language): tier.1 一线城市 / Tier-1 city, tier.2 二线城市 / Tier-2 city,
    tier.3 三线城市 / Tier-3 city, log.tierUp ({name} 升级为{tier}).
  3D part: a town hall is pickable as {t: 'hall', terr: <territory id>}; a click opens the panel's short
    card (like a building's): title = the repo's name, the one line hallLine(t), and the 看看它 / Show it
    button. tierWord( is called nowhere but hallLine; hallLine nowhere but the panel: never on a repo tag,
    the rail, a name plate or a land label.

T4 background buildings (sim + 3D part)
  BG_FAR (sim const, 100): bgFar(dist) -> dist > BG_FAR: far away the buildings are simple boxes.
  bgFor(t, phone) -> the entries to draw: t.bg (missing -> []); phone -> its first Math.ceil(n / 2);
    [] while a level-up show of t runs and has not flipped yet (same flip time as eraShown).
  bgModel(b, tier) -> a model key of MODELS for entry B: "cbd" a commercial skyscraper; "mid", "bund", and
    "fill" of tier 1 or 2 a commercial building; "main", "fill" of tier 3 and "edge" and "res" a suburban
    house; "ind" an industrial building; "park" null (trees). The same entry always gets the same key.
  3D part: drawBg(view) builds them with the land (buildLand calls it): one InstancedMesh per model key
    (instanced(), scaled to w, h, d), plus one far set of plain boxes; bgFar(cam.dist) shows one set and
    hides the other. No shadow (castShadow false), never in pickables, no click. Parks get trees.
  The landmark: pearlTower() (3D part): three pink spheres (SphereGeometry) on grey columns
    (CylinderGeometry) and a spire (ConeGeometry), about 17 tall, at t.mark; buildLand places it.
  Rings: drawRings(t): "elev" an elevated deck on pillars, "ring" / "outer" a flat road; lamps along them.
  Night: cityNight(on) (3D part), called by applyTheme(): on = the page's dark mode: background buildings
    of tier 1 and 2 show lit windows (emissive), ring lamps on, the landmark's spheres glow; off: none.

T5 a level up (sim)
  apply() of {"type": "era", "terr", "from", "to", "left", "tier": [old, new]}: shows.get(terr).tier is
    [old, new]; the page log says i18n('log.tierUp', {name, tier: i18n('tier.' + new)}) (instead of the era
    line) when left is the whole show. A snapshot's "shows" entry with "tier" starts the same show.

T6 the demo: DEMO_WORLD is `agent_city.py demo-world` (tests/test_agent_city_page.py compares them); its
  v4-plus is a tier-1 city.
"""

import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from test_agent_city_people import function_source, page, run_sim  # noqa: E402

SIM_REQUIRED = ("apply", "landState", "i18n", "TEXT", "shows", "terrAtOf", "cellTerrain", "terrMid", "repoTags",
                "zoomCells", "landsOf", "landsOk", "landMove", "landFree", "landPlace", "tierWord", "linesText",
                "hallLine", "BG_FAR", "bgFar", "bgFor", "bgModel")
CELL = 22


def terr(tid, name, slot, cells=1, tier=0, terrain="grassland", **more):
    shift = {1: 4, 2: 2}.get(tier, 0)
    t = {"id": tid, "name": name, "slot": list(slot), "cells": cells, "tier": tier, "terrain": terrain,
         "cx": slot[0] * CELL + (cells - 1) * CELL // 2 - shift, "cz": slot[1] * CELL + (cells - 1) * CELL // 2,
         "lines": 1000, "era": "town", "sea": False, "plan": "meadow", "plots": [], "buildings": [],
         "offices": [], "sites": [], "rest": None, "bg": [], "rings": [], "mark": None}
    t.update(more)
    return t


def island_view():
    """A tier-1 desert city at [-1, -1] (3 x 3), a tier-2 coast city at [2, -1] (2 x 2), a forest town at [0, 2]."""
    ts = [terr("aaaaaaaa", "big", [-1, -1], 3, 1, "desert", lines=1117407, era="city"),
          terr("bbbbbbbb", "mid", [2, -1], 2, 2, "coast", lines=465653, era="city", sea=True),
          terr("cccccccc", "small", [0, 2], 1, 0, "forest", lines=8500, era="town")]
    x0, z0 = -1 * CELL - 11, -1 * CELL - 11
    x1, z1 = 3 * CELL + 10, 2 * CELL + 10
    w, h = x1 - x0 + 1, z1 - z0 + 1
    return {"cell": CELL, "x0": x0, "z0": z0, "w": w, "h": h, "rows": [" " * w] * h, "territories": ts, "links": []}


DRIVER = r"""
const P = __payload, out = {};
const V = P.view;
// T1
out.terr = P.tiles.map(([x, z]) => terrAtOf(V, x, z));
out.cellT = P.tiles.map(([x, z]) => { const t = cellTerrain(V, x, z); return t ? t.id : null; });
out.mid = V.territories.map(t => terrMid(V, t));
out.tags = repoTags(V).map(t => [t.id, t.x, t.z]);
out.zoom = [zoomCells(V), zoomCells({ territories: [{ id: 'x' }] }), zoomCells({ territories: [] })];
// T2
const L = landsOf(V);
out.lands = L;
out.ok = P.okCases.map(c => landsOk(c));
out.place = P.placeCases.map(([id, cell]) => landPlace(P.lands, id, cell));
out.move = P.moveCases.map(([id, cell]) => landMove(P.lands, id, cell));
out.free = P.freeCases.map(id => landFree(P.lands, id));
// T3
out.word = V.territories.map(t => tierWord(t));
out.word3 = tierWord({ tier: 3, era: 'city' });
out.wordVillage = tierWord({ tier: 0 });
out.lines = [0, 999, 8500, 9999, 10000, 20000, 465653, 1117407, 2035139].map(n => linesText(n));
out.hall = V.territories.map(t => hallLine(t));
out.keys = { zh: Object.keys(TEXT.zh || {}), en: Object.keys(TEXT.en || {}) };
out.tierEn = [TEXT.en && TEXT.en['tier.1'], TEXT.en && TEXT.en['tier.2'], TEXT.en && TEXT.en['tier.3']];
out.errSize = i18n('arr.errSize');
// T4
out.far = [BG_FAR, bgFar(BG_FAR - 1), bgFar(BG_FAR + 1)];
const T1 = Object.assign({}, V.territories[0], { bg: P.bg });
out.bgAll = bgFor(T1, false).length;
out.bgPhone = bgFor(T1, true);
out.bgNone = bgFor(V.territories[2], false);
out.models = P.bg.map(b => bgModel(b, 1)).concat(P.bg3.map(b => bgModel(b, 3)));
out.modelsAgain = P.bg.map(b => bgModel(b, 1));
// T5: a level up
apply({ type: 'era', terr: 'bbbbbbbb', from: 'city', to: 'city', left: 60, tier: [2, 1] });
const s = shows.get('bbbbbbbb');
out.showTier = s ? s.tier : null;
out.bgDuringShow = bgFor(Object.assign({}, V.territories[1], { bg: P.bg }), false).length;
__out = out;
"""


def payload():
    view = island_view()
    big_tiles = [(x, z) for x in (-33, -12, 0, 11, 32) for z in (-33, 0, 32)]
    mid_tiles = [(33, -33), (54, -12), (43, 0), (65, 10), (33, 10)]
    small_tiles = [(-11, 33), (10, 54), (0, 44)]
    none_tiles = [(-34, 0), (77, 0), (11, 33), (33, 33)]
    tiles = big_tiles + mid_tiles + small_tiles + none_tiles
    lands = [{"id": "aaaaaaaa", "name": "big", "slot": [-1, -1], "sea": False, "cells": 3},
             {"id": "bbbbbbbb", "name": "mid", "slot": [2, -1], "sea": True, "cells": 2},
             {"id": "cccccccc", "name": "small", "slot": [0, 2], "sea": False, "cells": 1},
             {"id": "dddddddd", "name": "dot", "slot": [-2, 0], "sea": False, "cells": 1}]
    ok_cases = [lands,
                [dict(lands[0]), dict(lands[2], slot=[1, 1])],                 # a one-cell land inside the big square
                [dict(lands[0], slot=[2, 2])],                                 # the big square leaves the grid (2..4 fits)
                [dict(lands[0], slot=[3, 0])],                                 # 3..5 leaves the grid
                [dict(lands[1]), dict(lands[2], slot=[3, 1])],                 # on the sea row of the coast square
                [dict(lands[1]), dict(lands[2], slot=[3, 2])],                 # two rows south: fine
                [dict(lands[1], slot=[0, 0]), dict(lands[2], slot=[1, 2])]]    # the coast square with a land on its sea row
    place_cases = [["cccccccc", [1, 2]],     # a one-cell land: the cell itself
                   ["bbbbbbbb", [-3, 1]],    # (-4, 0) and (-3, 1) both hold it and touch, a tie: the smaller j
                   ["aaaaaaaa", [4, 4]],     # only (2, 2) holds it inside the grid, and it touches no land
                   ["dddddddd", [-2, 1]],
                   ["bbbbbbbb", [2, 2]],     # (2, 1) and (1, 2) tie: the smaller j; (2, 2) touches nobody
                   ["bbbbbbbb", [-2, -2]]]   # every 2 x 2 holding it: big's cell, its sea row on a land, or no touch
    move_cases = [["cccccccc", [1, 2]],       # free cell next to small's own: a one-cell move
                  ["dddddddd", [0, 2]],       # onto small (same size): swap
                  ["cccccccc", [0, 0]],       # onto the big square (another size): 'size'
                  ["aaaaaaaa", [0, 0]],       # a cell of its own square
                  ["zzzzzzzz", [1, 1]],       # no such land
                  ["bbbbbbbb", [-3, 1]]]      # a free cell: the coast square goes where it covers it
    bg = [[1.5, 2.5, 1.3, 1.3, 2.4, "mid"], [5.5, 2.5, 2.1, 2.1, 9.0, "cbd"], [7.5, 9.5, 1.2, 1.2, 1.5, "res"],
          [0.5, 0.5, 0.86, 0.86, 2.0, "fill"], [3.5, 3.5, 1.05, 1.15, 1.7, "bund"], [9.5, 9.5, 2.8, 1.25, 0.9, "ind"],
          [12.5, 12.5, 3.0, 3.0, 0, "park"]]
    bg3 = [[0.5, 0.5, 0.86, 0.86, 2.3, "main"], [1.5, 0.5, 0.8, 0.8, 1.2, "fill"], [4.5, 4.5, 0.72, 0.72, 0.8, "edge"]]
    return {"view": view, "tiles": tiles, "lands": lands, "okCases": ok_cases, "placeCases": place_cases,
            "moveCases": move_cases, "freeCases": ["cccccccc", "aaaaaaaa", None], "bg": bg, "bg3": bg3,
            "nBig": len(big_tiles), "nMid": len(mid_tiles), "nSmall": len(small_tiles)}


def square(slot, cells):
    return {(slot[0] + a, slot[1] + b) for a in range(cells) for b in range(cells)}


def ref_ok(lands):
    held = set()
    for l in lands:
        sq = square(l["slot"], l.get("cells", 1))
        if any(abs(i) > 4 or abs(j) > 4 for i, j in sq) or sq & held:
            return False
        held |= sq
    for l in lands:
        if l["sea"]:
            s = l.get("cells", 1)
            if {(l["slot"][0] + a, l["slot"][1] + s) for a in range(s)} & held:
                return False
    return True


class SimCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = payload()
        cls.r = run_sim(DRIVER, cls.p, SIM_REQUIRED)


class TestSquares(SimCase):
    def test_terrain_by_square(self):
        p = self.p
        want = (["desert"] * p["nBig"] + ["coast"] * p["nMid"] + ["forest"] * p["nSmall"]
                + ["grassland"] * (len(p["tiles"]) - p["nBig"] - p["nMid"] - p["nSmall"]))
        self.assertEqual(self.r["terr"], want)
        ids = (["aaaaaaaa"] * p["nBig"] + ["bbbbbbbb"] * p["nMid"] + ["cccccccc"] * p["nSmall"]
               + [None] * (len(p["tiles"]) - p["nBig"] - p["nMid"] - p["nSmall"]))
        self.assertEqual(self.r["cellT"], ids)

    def test_middle_of_the_square(self):
        self.assertEqual(self.r["mid"], [[0, 0], [55, -11], [0, 44]])
        v = self.p["view"]
        mx, mz = round(v["x0"] + v["w"] / 2), round(v["z0"] + v["h"] / 2)
        self.assertEqual(self.r["tags"], [["aaaaaaaa", 0 - mx, 0 - mz], ["bbbbbbbb", 55 - mx, -11 - mz],
                                          ["cccccccc", 0 - mx, 44 - mz]])

    def test_zoom_cells(self):
        self.assertEqual(self.r["zoom"], [3, 1, 1])

    def test_distance_rules_in_the_source(self):
        src = function_source("distLimit") or ""
        self.assertIn("zoomCells(", src)
        self.assertIn("1.15", src)
        text = page()
        i = text.find("$('#repos').addEventListener('click'")
        self.assertGreater(i, 0)
        block = text[i:text.find("});", i)]
        self.assertIn("cells", block)
        self.assertIn("1.15", block)


class TestArrange(SimCase):
    def test_lands_carry_cells(self):
        self.assertEqual([l.get("cells") for l in self.r["lands"]], [3, 2, 1])

    def test_ok(self):
        self.assertEqual(self.r["ok"], [ref_ok(c) for c in self.p["okCases"]])
        self.assertEqual(self.r["ok"], [True, False, True, False, False, True, False])

    def test_place(self):
        self.assertEqual(self.r["place"], [[1, 2], [-4, 0], None, [-2, 1], [2, 1], None])

    def test_move(self):
        m = self.r["move"]
        self.assertEqual(m[0], [{"id": "cccccccc", "slot": [1, 2]}])
        self.assertEqual(m[1], [{"id": "dddddddd", "slot": [0, 2]}, {"id": "cccccccc", "slot": [-2, 0]}])
        self.assertEqual(m[2], "size")
        self.assertIsNone(m[3])
        self.assertIsNone(m[4])
        self.assertEqual(m[5], [{"id": "bbbbbbbb", "slot": [-4, 0]}])

    def test_free(self):
        small, big, anyone = self.r["free"]
        held = set().union(*[square(l["slot"], l["cells"]) for l in self.p["lands"]])
        for cells in (small, big, anyone):
            for c in cells:
                self.assertNotIn(tuple(c), held)
        self.assertIn([1, 2], small)
        self.assertNotIn([4, 4], big)
        self.assertTrue(big, "the big square has somewhere to go")

    def test_words(self):
        self.assertEqual(self.r["errSize"], "大小不一样，不能对换")
        self.assertIn("arr.errSize", self.r["keys"]["en"])

    def test_drag_shows_the_square(self):
        src = function_source("arrOver") or ""
        self.assertIn("landPlace(", src)


class TestHallCard(SimCase):
    def test_words(self):
        self.assertEqual(self.r["word"], ["一线城市", "二线城市", "镇"])
        self.assertEqual(self.r["word3"], "三线城市")
        self.assertEqual(self.r["wordVillage"], "村")
        self.assertEqual(self.r["tierEn"], ["Tier-1 city", "Tier-2 city", "Tier-3 city"])
        for k in ("tier.1", "tier.2", "tier.3", "log.tierUp", "arr.errSize"):
            self.assertEqual(self.r["keys"]["zh"].count(k), 1, k)
            self.assertEqual(self.r["keys"]["en"].count(k), 1, k)

    def test_lines(self):
        self.assertEqual(self.r["lines"], ["0 行", "999 行", "8,500 行", "9,999 行", "1 万行", "2 万行", "46.6 万行",
                                           "111.7 万行", "203.5 万行"])

    def test_hall_line(self):
        self.assertEqual(self.r["hall"], ["一线城市 · 111.7 万行", "二线城市 · 46.6 万行", "镇 · 8,500 行"])

    def test_only_on_the_hall_card(self):
        text = page()
        calls = [m.start() for m in re.finditer(r"\btierWord\(", text)]
        defs = [m.start() for m in re.finditer(r"function tierWord\(", text)]
        hall = function_source("hallLine") or ""
        self.assertTrue(hall)
        self.assertEqual(len(calls) - len(defs), hall.count("tierWord("), "tierWord is used by hallLine only")
        uses = [m.start() for m in re.finditer(r"\bhallLine\(", text)]
        self.assertGreaterEqual(len(uses), 2, "defined and used by the panel")
        for name in ("renderRepos", "renderRail", "arrDraw", "pinLandOverlays"):
            src = function_source(name) or ""
            self.assertNotIn("hallLine(", src, name)
            self.assertNotIn("tier.", src, name)

    def test_the_hall_is_pickable(self):
        text = page()
        self.assertRegex(text, r"userData\.pick\s*=\s*\{\s*t\s*:\s*'hall'")
        self.assertRegex(text, r"selected\.t === 'hall'")


class TestBackground(SimCase):
    def test_far(self):
        self.assertEqual(self.r["far"], [100, False, True])

    def test_for_the_device(self):
        self.assertEqual(self.r["bgAll"], len(self.p["bg"]))
        self.assertEqual(self.r["bgPhone"], self.p["bg"][:4])
        self.assertEqual(self.r["bgNone"], [])

    def test_models(self):
        text = page()
        m = re.search(r"const MODELS = \[(.*?)\];", text, re.S)
        self.assertIsNotNone(m)
        models = set(re.findall(r"'([^']+)'", m.group(1)))
        got = self.r["models"]
        # bg (tier 1): mid, cbd, res, fill, bund, ind, park; bg3 (tier 3): main, fill, edge
        packs = ["commercial", "commercial", "suburban", "commercial", "commercial", "industrial", None,
                 "suburban", "suburban", "suburban"]
        self.assertEqual(len(got), len(packs))
        for k, (key, pack) in enumerate(zip(got, packs)):
            with self.subTest(k=k):
                if pack is None:
                    self.assertIsNone(key)
                    continue
                self.assertIn(key, models)
                self.assertEqual(key.split("/")[0], pack)
        self.assertIn("skyscraper", got[1])
        self.assertNotIn("skyscraper", got[0])
        self.assertEqual(self.r["models"][:len(self.p["bg"])], self.r["modelsAgain"])

    def test_drawn_with_the_land(self):
        draw = function_source("drawBg") or ""
        self.assertTrue(draw, "drawBg is missing")
        self.assertIn("bgFor(", draw)
        self.assertIn("bgModel(", draw)
        self.assertRegex(draw, r"instanced\(|InstancedMesh")
        self.assertRegex(draw, r"shadow\s*:\s*false|castShadow\s*=\s*false")
        self.assertNotIn("pickables.push", draw)
        land = function_source("buildLand") or ""
        self.assertIn("drawBg(", land)
        self.assertIn("pearlTower(", land)
        self.assertIn("drawRings(", land)
        self.assertIn("bgFar(", page())

    def test_pearl_tower(self):
        src = function_source("pearlTower") or ""
        self.assertTrue(src, "pearlTower is missing")
        self.assertGreaterEqual(src.count("SphereGeometry"), 1)
        self.assertIn("CylinderGeometry", src)
        self.assertIn("ConeGeometry", src)

    def test_rings(self):
        src = function_source("drawRings") or ""
        self.assertTrue(src, "drawRings is missing")
        self.assertIn("elev", src)

    def test_night(self):
        src = function_source("cityNight") or ""
        self.assertTrue(src, "cityNight is missing")
        self.assertIn("emissive", src)
        self.assertIn("cityNight(", function_source("applyTheme") or "")


class TestLevelUp(SimCase):
    def test_the_show_knows_the_level(self):
        self.assertEqual(self.r["showTier"], [2, 1])
        self.assertEqual(self.r["bgDuringShow"], 0, "the new buildings stand only once the show flips")

    def test_the_log_line(self):
        src = page()
        self.assertIn("log.tierUp", src)


class TestDemo(unittest.TestCase):
    def test_demo_world_has_a_big_city(self):
        out = subprocess.run([sys.executable, os.path.join(BIN, "agent_city.py"), "demo-world"],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        view = json.loads(out.stdout)
        by = {t["name"]: t for t in view["territories"]}
        self.assertEqual(by["v4-plus"].get("tier"), 1)
        text = page()
        self.assertIn('"tier": 1', text[text.find("const DEMO_WORLD"):text.find("const DEMO_WORLD") + 400000])


if __name__ == "__main__":
    unittest.main()
