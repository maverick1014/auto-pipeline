"""Failing tests for city-tier, the server (requirements/city.md, "Tiers"; owner, 2026-10-02: "v4-plus
is a very huge project, it should look like Shanghai, a first-tier city"; approved mock
mock/city-tier-mock.html, "mock yes" 2026-10-02 17:07 with the five recommended picks: lines 800k / 200k /
20k, hand-written code only, re-lay once with 3 x 3 and 2 x 2 cells, a pearl tower drawn in code, the level
only on the hall card). The page: tests/test_agent_city_tier_page.py.

No test here touches the owner's world.json: every CityState gets a file in a temp folder.

CONTRACT, server (bin/agent_city.py, Python standard library only)

  COUNTING (decision 2: hand-written code only)
    counts_as_code(path) also says False for generated Dart (a name ending ".g.dart" or ".freezed.dart")
      and for anything under a folder whose name ends with "_unzipped" (a design bundle). Docs and l10n
      still count there (the 5 kinds keep their library).
    counts_for_size(path) -> counts_as_code(path), and not a doc (".md", ".mdx", ".rst", ".adoc", any
      case), not under a folder named "l10n", not an ".arb" file.
    count_lines(identity) counts the rows counts_for_size keeps (README.md no longer counts).

  LEVELS
    TIER_LINES = (800000, 200000, 20000)
    tier_of(lines) -> 1 from 800,000, 2 from 200,000, 3 from 20,000, else 0.
    TIER_CELLS = {0: 1, 1: 3, 2: 2, 3: 1}: a land's square is TIER_CELLS[tier] x TIER_CELLS[tier] cells.
    TIER_SHIFT = {1: 4, 2: 2}: in a big square the town (its hall) sits this many tiles west of the
      square's middle (the city grows east of it, as in the mock).
    COUNT_RULE = 2

  THE RECORD (world.json; "v" stays 1, a file without the new keys loads as before)
    "count": COUNT_RULE once the territory was counted by this rule. add_territory() gives every new
      record "count": COUNT_RULE (it is only ever counted this way).
    "tier": 0..3, the level the land is drawn at (missing = 0).
    "cells": 1..3, the size of its square (missing = 1). "slot" is the square's north-west cell.
    world["tiers"]: true once the island was re-laid (missing = not yet).

  CityState.recount(now)
    A count_fn answer of None = could not count (the repo is not on this machine): nothing of that
      territory changes.
    A record without "count": COUNT_RULE: lines = peak = the new count (once: the old peak was counted
      the old way), then "count": COUNT_RULE. After that peak = max(peak, lines), as before.
    After ALL of one recount's counts are in, the levels: every counted territory (shown or hidden) whose
      tier_of(peak) is above its "tier":
        any of them needs a bigger square and world["tiers"] is not set -> re_lay(world, plans) (below)
          runs once for the whole island, world["tiers"] = True, and no show for anybody in this count;
        its new square is bigger, world["tiers"] set -> grow_land(world, plans, identity, cells); placed:
          "tier" and "cells" set, and the level-up show; not placed (no room): nothing changes, the next
          count tries again;
        the same square -> "tier" set, and the level-up show.
      The level-up show is an era show (Balance): t["show"] = {"from": era, "to": era, "start": ...,
        "tier": [old tier, new tier]} (era as it is after this count; an era change in the same count is
        the same one show); with a page open, the broadcast {"type": "era", "terr", "from", "to", "left":
        SHOW_SEC, "tier": [old, new]}; the snapshot's "shows" carry "tier" for such a show.
      Never a step down (the peak never shrinks after the new count, and a "tier" is never lowered).
    The world is saved and the pages get the new world when anything of it changed.

  re_lay(world, plans)  (pure; changes WORLD in place)
    Every SHOWN territory: "cells" = TIER_CELLS[tier_of(peak)] and "tier" = tier_of(peak) when it was
      counted by COUNT_RULE, else it keeps "tier" (missing 0) and takes 1 cell. Then the squares are
      placed again, one by one: by cells (big first), then peak (big first), then world order.
      The first: its square around the grid's middle cell: slot (-(cells // 2), -(cells // 2)).
      Each next: the free place nearest the first one's middle (distance between the squares' middles;
      a tie: the smaller j, then the smaller i) where its square is inside the grid (-4..4 both ways),
      free, touches a placed square (4 sides), is not on a cell just south of a placed coast square
      (the row j + cells under it), and, when its own plan has sea, has no placed square on the row
      just south of it. No place at all (the grid is full): it keeps its slot and 1 cell.
    Hidden territories keep their slot and get their "cells"/"tier" the same way (placed when shown
      again). The order, names, buildings and everything else stay.

  grow_land(world, plans, identity, cells) -> True when placed (pure; changes WORLD in place)
    The square of CELLS that holds the land's old square, inside the grid, free of the other shown
    squares and keeping the coast rule, nearest the old middle (tie: smaller j, then i); else the free
    place touching another shown square nearest the old middle; else False and nothing changes. Nobody
    else moves. A hidden land: "cells" is set, its slot stays (placed when shown again), True.

  layout(world, plans): a territory's view also carries
    "tier": its record's tier (0 when missing), "cells": its record's cells (1 when missing),
    "slot": its square's north-west cell,
    "cx", "cz": the hall: cx = i * CELL + (cells - 1) * CELL // 2 - TIER_SHIFT.get(tier, 0),
      cz = j * CELL + (cells - 1) * CELL // 2.
    "bg": the background buildings, in the plan's growth order (what fills first, first):
      [x, z, w, d, h, zone] each, world coordinates (x, z the middle; w, d the footprint; h the height,
      all in tiles, at most 2 decimals). zone: tier 1 "fill" (the town's free lots), "bund", "cbd",
      "mid", "res", "ind", "park" (a park block: w = d = the block, h = 0, its trees are the page's);
      tier 2 "fill", "cbd", "mid", "res", "ind", "park"; tier 3 "main", "fill", "edge"; tier 0: [] (a
      small town stays as before).
    "rings": tier 1 [{"kind": "elev", "pts": [[x, z], ...]}] (+ {"kind": "outer"} once its growth in its
      level is 0.5 or more); tier 2 [{"kind": "ring", ...}]; else []. Points inside the square.
    "mark": tier 1 [x, z], the landmark tower's spot (east of the river); else None.
    In "rows": a built block or lot of a background building is "u" (not walkable, never a road, a
      plot, an office, the rest place, the hall or a bridge); tier 1's river is "w" with a "B" bridge where
      the town's east road crosses it. Every background building stands on "u" tiles only.
    Land: tier 1 about 25 to 28 tiles around its middle, tier 2 about 17 to 20, tier 3 about 9 to 10 (one
      cell). A big land's tiles stay inside its square (its sea rows south of it on a coast plan).
    Links: every two squares that touch get a link, and a person can walk from either hall to the other
      (".grtBbH" tiles).
    Caps: buildings ("park" not counted) per land BG_CAP = {1: 480, 2: 170, 3: 60}; the whole view
      BG_TOTAL = 900. A cut drops from the end of a list (what fills last goes first); over the total,
      the longest list loses its last entry first (a tie: the later land in the view).

  set_layout(lands) and add_territory(): the rule on squares. A square must be inside the grid; two
    squares never share a cell (409 "taken", also for a square that leaves the grid); no square on the
    row just south of a coast square (409 "sea"). A land shown again keeps its slot when its square fits
    there, else the first free place its square fits. A new repo never takes a cell of a square or the
    sea row south of a coast square.

  demo_world(): its v4-plus (1,000,000 lines) is a tier-1 city (3 cells), pos-lite (20,000) tier 3.

  THE CLOUD: cloud_world() keeps "tier", "cells", "bg", "rings", "mark" (no names in them); the cloud
    picture of the owner's real island (the seven repos below) stays under CLOUD_VIEW_MAX_BYTES.
"""

import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402

PLANS = ac.load_plans()
PLAN = {p["id"]: p for p in PLANS}
WALK = set(".grtBbH")

# The owner's real island (laptop world.json, 2026-10-02) and the hand-written counts (mock, measured
# 2026-10-02; the four not measured keep their old count).
OWNER = (
    ("v4-plus", "oasis", 2035139, 1117407),
    ("v4-pospro", "harbor", 1270679, 465653),
    ("plus-3", "harbor", 223146, 223146),
    ("auto-pipeline", "ridge", 96279, 94097),
    ("pospro", "woods", 78973, 78973),
    ("plus-api", "woods", 68220, 68220),
    ("poslite", "meadow", 45921, 45921),
)
OLD_SLOTS = ([0, 0], [1, 0], [0, 1], [-1, 0], [0, -1], [1, -1], [-1, 1])   # the coast lands (v4-pospro, plus-3) have the cell south free


def need(test, name, obj=ac):
    fn = getattr(obj, name, None)
    if fn is None:
        test.fail("%s is missing" % name)
    return fn


def const(test, name):
    if not hasattr(ac, name):
        test.fail("agent_city.%s is missing" % name)
    return getattr(ac, name)


def record(name, plan, slot, lines=400, **more):
    rec = {"name": name, "plan": plan, "slot": list(slot), "lines": lines, "peak": lines, "buildings": [],
           "era": "city" if lines >= 20000 else "village", "balance": {}, "rules_bad": [], "offices": {},
           "rest": False}
    rec.update(more)
    return rec


def ident(name):
    return "/r/%s/.git" % name


def owner_world(counted=False):
    """The owner's seven repos as one-cell lands in their old places (world.json before this change)."""
    world = {"v": 1, "territories": {}, "order": []}
    for (name, plan, old, new), slot in zip(OWNER, OLD_SLOTS):
        more = {"count": 2} if counted else {}
        world["territories"][ident(name)] = record(name, plan, slot, new if counted else old, **more)
        world["order"].append(ident(name))
    return world


def big(name, plan, slot, tier, lines, **more):
    cells = {0: 1, 1: 3, 2: 2, 3: 1}[tier]
    return record(name, plan, slot, lines, tier=tier, cells=cells, count=2, **more)


def world_of(*recs):
    world = {"v": 1, "territories": {}, "order": [], "tiers": True}
    for rec in recs:
        world["territories"][ident(rec["name"])] = rec
        world["order"].append(ident(rec["name"]))
    return world


def square(slot, cells):
    return {(slot[0] + a, slot[1] + b) for a in range(cells) for b in range(cells)}


def squares(world, shown_only=True):
    out = {}
    for i in world["order"]:
        t = world["territories"][i]
        if shown_only and t.get("hidden"):
            continue
        out[t["name"]] = square(t["slot"], t.get("cells", 1))
    return out


def touches(a, b):
    return any((i + di, j + dj) in b for i, j in a for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def middle(slot, cells):
    return (slot[0] + (cells - 1) / 2.0, slot[1] + (cells - 1) / 2.0)


class View:
    """Tile lookups on one layout() answer."""

    def __init__(self, view):
        self.v = view
        self.by_name = {t["name"]: t for t in view["territories"]}

    def tile(self, x, z):
        r, c = z - self.v["z0"], x - self.v["x0"]
        if 0 <= r < self.v["h"] and 0 <= c < self.v["w"]:
            return self.v["rows"][r][c]
        return " "

    def box(self, t):
        cell, half = self.v["cell"], ac.HALF
        i, j = t["slot"]
        s = t.get("cells", 1)
        return (i * cell - half, (i + s - 1) * cell + half - 1, j * cell - half, (j + s - 1) * cell + half - 1)

    def tiles(self, t, chars):
        x0, x1, z0, z1 = self.box(t)
        return [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) if self.tile(x, z) in chars]

    def reach(self, start, goal_fn):
        seen = {start}
        q = deque([start])
        while q:
            x, z = q.popleft()
            if goal_fn(x, z):
                return True
            for a, b in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                if (a, b) not in seen and self.tile(a, b) in WALK:
                    seen.add((a, b))
                    q.append((a, b))
        return False


def bg_rect_tiles(b):
    x, z, w, d = b[0], b[1], b[2], b[3]
    e = 1e-6
    return [(tx, tz) for tx in range(math.floor(x - w / 2 + e), math.floor(x + w / 2 - e) + 1)
            for tz in range(math.floor(z - d / 2 + e), math.floor(z + d / 2 - e) + 1)]


def buildings(t):
    return [b for b in t.get("bg") or [] if b[5] != "park"]


# ---------------------------------------------------------------------------
# counting: hand-written code only
# ---------------------------------------------------------------------------

class TestCounting(unittest.TestCase):
    def test_generated_and_bundles_never_count(self):
        for path in ("lib/models/user.g.dart", "lib/state/cart.freezed.dart", "lib/db/schema.G.DART",
                     "design/home_unzipped/index.html", "a/screens_unzipped/x/y.js"):
            with self.subTest(path=path):
                self.assertFalse(ac.counts_as_code(path))
        for path in ("lib/main.dart", "README.md", "lib/l10n/app_en.arb", "docs/guide.md", "lib/gdart.dart"):
            with self.subTest(path=path):
                self.assertTrue(ac.counts_as_code(path), "the 5 kinds still see it")

    def test_size_counts_hand_written_code_only(self):
        fn = need(self, "counts_for_size")
        no = ["README.md", "docs/a.MD", "x.mdx", "guide.rst", "book.adoc", "lib/l10n/intl_en.arb",
              "lib/l10n/app_localizations.dart", "res/app_zh.arb", "lib/a.g.dart", "x/y_unzipped/z.ts",
              "img/logo.png", "vendor/a.py", "yarn.lock"]
        yes = ["src/app.py", "lib/main.dart", "web/page.tsx", "Makefile", "db/schema.sql", "config.yml",
               "bin/run.sh", "lib/l10n_helper.dart", "notes.txt"]
        for path in no:
            with self.subTest(path=path):
                self.assertFalse(fn(path))
        for path in yes:
            with self.subTest(path=path):
                self.assertTrue(fn(path))


# ---------------------------------------------------------------------------
# levels
# ---------------------------------------------------------------------------

class TestLevels(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(const(self, "TIER_LINES"), (800000, 200000, 20000))
        tier_of = need(self, "tier_of")
        for n, want in ((0, 0), (19999, 0), (20000, 3), (199999, 3), (200000, 2), (799999, 2),
                        (800000, 1), (5000000, 1)):
            with self.subTest(n=n):
                self.assertEqual(tier_of(n), want)

    def test_cells_and_shift(self):
        self.assertEqual(const(self, "TIER_CELLS"), {0: 1, 1: 3, 2: 2, 3: 1})
        self.assertEqual(const(self, "TIER_SHIFT"), {1: 4, 2: 2})
        self.assertEqual(const(self, "COUNT_RULE"), 2)

    def test_owner_repos(self):
        tier_of = need(self, "tier_of")
        got = {name: tier_of(new) for name, _, _, new in OWNER}
        self.assertEqual(got, {"v4-plus": 1, "v4-pospro": 2, "plus-3": 2, "auto-pipeline": 3, "pospro": 3,
                               "plus-api": 3, "poslite": 3})

    def test_a_new_record_is_counted_by_the_new_rule(self):
        world = ac.new_world()
        t = ac.add_territory(world, PLANS, "/x/.git", "x", 10)
        self.assertEqual(t.get("count"), 2)


# ---------------------------------------------------------------------------
# re_lay and grow_land (pure)
# ---------------------------------------------------------------------------

class TestReLay(unittest.TestCase):
    def relaid(self):
        world = owner_world(counted=True)
        need(self, "re_lay")(world, PLANS)
        return world

    def check_rule(self, world, touch=True):
        sq = squares(world)
        held = {}
        for name, cells in sq.items():
            for c in cells:
                self.assertTrue(-4 <= c[0] <= 4 and -4 <= c[1] <= 4, "%s leaves the grid" % name)
                self.assertNotIn(c, held, "%s and %s share a cell" % (name, held.get(c)))
                held[c] = name
        for name, cells in sq.items():
            others = set().union(*[v for k, v in sq.items() if k != name]) if len(sq) > 1 else set()
            if touch and len(sq) > 1:
                self.assertTrue(touches(cells, others), "%s touches no land" % name)
        for i in world["order"]:
            t = world["territories"][i]
            if t.get("hidden") or not PLAN[t["plan"]]["sea"]:
                continue
            s = t.get("cells", 1)
            sea_row = {(t["slot"][0] + a, t["slot"][1] + s) for a in range(s)}
            self.assertFalse(sea_row & set(held), "%s's sea is taken" % t["name"])

    def test_sizes_by_level(self):
        world = self.relaid()
        got = {t["name"]: (t["tier"], t["cells"]) for t in world["territories"].values()}
        self.assertEqual(got, {"v4-plus": (1, 3), "v4-pospro": (2, 2), "plus-3": (2, 2), "auto-pipeline": (3, 1),
                               "pospro": (3, 1), "plus-api": (3, 1), "poslite": (3, 1)})

    def test_the_biggest_in_the_middle(self):
        world = self.relaid()
        self.assertEqual(world["territories"][ident("v4-plus")]["slot"], [-1, -1])
        self.check_rule(world)

    def test_the_two_tier_2_cities_are_next_to_the_big_one(self):
        world = self.relaid()
        sq = squares(world)
        for name in ("v4-pospro", "plus-3"):
            self.assertTrue(touches(sq[name], sq["v4-plus"]), name)

    def test_same_world_same_island(self):
        a, b = self.relaid(), self.relaid()
        self.assertEqual({k: v["slot"] for k, v in a["territories"].items()},
                         {k: v["slot"] for k, v in b["territories"].items()})

    def test_not_counted_by_the_new_rule_stays_one_cell(self):
        world = owner_world(counted=False)
        world["territories"][ident("v4-plus")].update(lines=1117407, peak=1117407, count=2)
        need(self, "re_lay")(world, PLANS)
        pospro = world["territories"][ident("v4-pospro")]
        self.assertEqual(pospro.get("cells", 1), 1, "its 1.27M lines were counted the old way")
        self.assertEqual(pospro.get("tier", 0), 0)
        self.assertEqual(world["territories"][ident("v4-plus")]["cells"], 3)
        self.check_rule(world)

    def test_hidden_keeps_its_slot(self):
        world = owner_world(counted=True)
        world["territories"][ident("pospro")]["hidden"] = True
        need(self, "re_lay")(world, PLANS)
        self.assertEqual(world["territories"][ident("pospro")]["slot"], [0, -1])
        self.check_rule(world)

    def test_everything_else_stays(self):
        world = owner_world(counted=True)
        world["territories"][ident("v4-plus")]["buildings"] = [{"plot": 0, "type": "house", "by": "w"}]
        before = json.loads(json.dumps(world))
        need(self, "re_lay")(world, PLANS)
        self.assertEqual(world["order"], before["order"])
        for i, t in world["territories"].items():
            for k in ("name", "plan", "lines", "peak", "buildings", "era"):
                self.assertEqual(t[k], before["territories"][i][k])


class TestGrow(unittest.TestCase):
    def island(self):
        world = owner_world(counted=True)
        need(self, "re_lay")(world, PLANS)
        world["tiers"] = True
        return world

    def test_grows_on_the_owner_island(self):
        world = self.island()
        t = world["territories"][ident("plus-api")]
        before = {k: list(v["slot"]) for k, v in world["territories"].items() if k != ident("plus-api")}
        self.assertTrue(need(self, "grow_land")(world, PLANS, ident("plus-api"), 2))
        self.assertEqual(t["cells"], 2)
        self.assertEqual({k: v["slot"] for k, v in world["territories"].items() if k != ident("plus-api")}, before,
                         "nobody else moves")
        TestReLay.check_rule(self, world)

    def test_in_place_when_there_is_room(self):
        world = world_of(big("a", "meadow", [0, 0], 3, 50000), big("b", "ridge", [1, 0], 3, 50000))
        self.assertTrue(need(self, "grow_land")(world, PLANS, ident("a"), 2))
        a = world["territories"][ident("a")]
        self.assertIn((0, 0), square(a["slot"], 2), "the new square holds the old cell")
        self.assertEqual(a["cells"], 2)
        self.assertEqual(world["territories"][ident("b")]["slot"], [1, 0])
        TestReLay.check_rule(self, world)

    def test_moves_when_boxed_in(self):
        # a at the middle, boxed in on all four sides and the corners by one-cell lands
        recs = [big("a", "meadow", [0, 0], 3, 50000)]
        k = 0
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                if (i, j) != (0, 0):
                    recs.append(big("n%d" % k, "ridge" if k % 2 else "woods", [i, j], 3, 30000))
                    k += 1
        world = world_of(*recs)
        before = {k2: list(v["slot"]) for k2, v in world["territories"].items() if k2 != ident("a")}
        self.assertTrue(need(self, "grow_land")(world, PLANS, ident("a"), 2))
        a = world["territories"][ident("a")]
        self.assertNotIn((0, 0), square(a["slot"], 2), "it moved out")
        self.assertEqual({k2: v["slot"] for k2, v in world["territories"].items() if k2 != ident("a")}, before)
        TestReLay.check_rule(self, world)

    def test_no_room_no_change(self):
        recs = [big("c%d_%d" % (i, j), "ridge", [i, j], 3, 30000) for i in range(-4, 5) for j in range(-4, 5)]
        world = world_of(*recs)
        before = json.loads(json.dumps(world))
        self.assertFalse(need(self, "grow_land")(world, PLANS, ident("c0_0"), 2))
        self.assertEqual(world, before)


# ---------------------------------------------------------------------------
# CityState: the new count once, the re-lay once, a level up later
# ---------------------------------------------------------------------------

class Case(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_tier_"))
        self.path = os.path.join(self.base, "home", "world.json")
        self.counts = {}
        self.now = 1000.0

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def make(self, world):
        ac.save_world(self.path, world)
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.path, plans=PLANS,
                            count_fn=lambda i: self.counts.get(i, None),
                            balance_fn=lambda i, r: {"kinds": {}, "files": {}, "bad": []})

    def feed(self, st, *names):
        for name in names:
            self.now += 1
            st.feed_line({"ev": "PostToolUse", "sid": "s-" + name, "aid": "", "at": "", "tool": "Read", "nt": "",
                          "proj": name, "role": "worker", "desc": "", "sub": "", "q": "", "klen": "",
                          "repo": ident(name), "kind": ""}, self.now)

    def count_all(self, st, names):
        self.feed(st, *names)
        self.now += 400
        st.recount(self.now)

    def rec(self, st, name):
        return st.world["territories"][ident(name)]

    def file(self):
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def drain(client):
        out = []
        while not client.queue.empty():
            raw = client.queue.get_nowait()
            if not isinstance(raw, (bytes, str)):
                continue
            text = raw.decode() if isinstance(raw, bytes) else raw
            for part in text.split("\n"):
                if part.startswith("data:"):
                    try:
                        out.append(json.loads(part[5:].strip()))
                    except ValueError:
                        pass
        return out


class TestNewCountOnce(Case):
    def test_the_old_peak_is_replaced_once(self):
        st = self.make(owner_world())
        self.counts[ident("v4-pospro")] = 465653
        self.count_all(st, ["v4-pospro"])
        t = self.rec(st, "v4-pospro")
        self.assertEqual((t["lines"], t["peak"], t.get("count")), (465653, 465653, 2))
        self.counts[ident("v4-pospro")] = 400000
        self.count_all(st, ["v4-pospro"])
        self.assertEqual((t["lines"], t["peak"]), (400000, 465653), "after the new count the peak never shrinks")

    def test_not_on_this_machine_keeps_its_count(self):
        st = self.make(owner_world())
        self.count_all(st, ["plus-3"])            # count_fn answers None
        t = self.rec(st, "plus-3")
        self.assertEqual((t["lines"], t["peak"]), (223146, 223146))
        self.assertNotEqual(t.get("count"), 2)
        self.assertEqual(t.get("cells", 1), 1)


class TestReLayOnce(Case):
    def counted_owner(self, st):
        for name, _, _, new in OWNER:
            self.counts[ident(name)] = new
        self.count_all(st, [n for n, _, _, _ in OWNER])

    def test_the_first_big_city_re_lays_the_island(self):
        st = self.make(owner_world())
        client = st.add_client()
        self.drain(client)
        self.counted_owner(st)
        self.assertTrue(st.world.get("tiers"))
        self.assertEqual(self.rec(st, "v4-plus")["slot"], [-1, -1])
        self.assertEqual(self.rec(st, "v4-plus")["cells"], 3)
        self.assertEqual(self.rec(st, "v4-pospro")["cells"], 2)
        TestReLay.check_rule(self, st.world)
        events = self.drain(client)
        self.assertFalse([e for e in events if e.get("type") == "era"], "no show for the re-lay")
        self.assertFalse(any(t.get("show") for t in st.world["territories"].values()))
        self.assertTrue(self.file().get("tiers"), "recorded in world.json")
        self.assertEqual(self.file()["territories"][ident("v4-plus")]["slot"], [-1, -1])

    def test_never_again(self):
        st = self.make(owner_world())
        self.counted_owner(st)
        code, body = st.set_layout([{"id": ac.territory_id(ident("poslite")), "slot": [3, 3]}])
        if code != 200:  # [3, 3] may not touch; find a free touching cell the page would offer
            held = set().union(*squares(st.world).values())
            free = [(i, j) for i in range(-4, 5) for j in range(-4, 5) if (i, j) not in held
                    and any((i + a, j + b) in held for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
            for cell in free:
                code, body = st.set_layout([{"id": ac.territory_id(ident("poslite")), "slot": list(cell)}])
                if code == 200:
                    break
        self.assertEqual(code, 200, body)
        moved = list(self.rec(st, "poslite")["slot"])
        self.counts[ident("plus-api")] = 70000
        self.count_all(st, ["plus-api", "v4-plus"])
        self.assertEqual(self.rec(st, "poslite")["slot"], moved, "the owner's arrangement is kept")
        st2 = self.make(json.loads(json.dumps(st.world)))
        self.counts[ident("v4-plus")] = 1200000
        self.count_all(st2, ["v4-plus"])
        self.assertEqual(st2.world["territories"][ident("poslite")]["slot"], moved)

    def test_only_small_repos_no_re_lay(self):
        world = owner_world()
        for name in ("v4-plus", "v4-pospro", "plus-3"):
            world["territories"].pop(ident(name))
            world["order"].remove(ident(name))
        st = self.make(world)
        before = {k: list(v["slot"]) for k, v in st.world["territories"].items()}
        for name, _, _, new in OWNER[3:]:
            self.counts[ident(name)] = new
        self.count_all(st, [n for n, _, _, _ in OWNER[3:]])
        self.assertEqual({k: v["slot"] for k, v in st.world["territories"].items()}, before)
        self.assertFalse(st.world.get("tiers"))
        self.assertEqual(self.rec(st, "poslite").get("tier"), 3)


class TestLevelUp(Case):
    def island(self):
        world = owner_world(counted=True)
        need(self, "re_lay")(world, PLANS)
        world["tiers"] = True
        return world

    def test_a_level_up_is_a_show(self):
        st = self.make(self.island())
        client = st.add_client()
        self.drain(client)
        self.counts[ident("plus-api")] = 250000
        self.count_all(st, ["plus-api"])
        t = self.rec(st, "plus-api")
        self.assertEqual((t["tier"], t["cells"]), (2, 2))
        self.assertEqual(t["show"].get("tier"), [3, 2])
        eras = [e for e in self.drain(client) if e.get("type") == "era"]
        self.assertEqual(len(eras), 1)
        self.assertEqual(eras[0]["tier"], [3, 2])
        self.assertEqual(eras[0]["terr"], ac.territory_id(ident("plus-api")))
        self.assertEqual(eras[0]["left"], ac.SHOW_SEC)
        with st.lock:
            snap = st._snapshot_locked()
        if snap is not None:
            mine = [s for s in snap["shows"] if s["terr"] == ac.territory_id(ident("plus-api"))]
            self.assertEqual(mine[0]["tier"], [3, 2])
        TestReLay.check_rule(self, st.world)

    def test_small_to_tier_3_keeps_its_cell(self):
        world = self.island()
        t = world["territories"][ident("poslite")]
        t.update(lines=15000, peak=15000, tier=0, cells=1, era="town")
        st = self.make(world)
        slot = list(self.rec(st, "poslite")["slot"])
        self.counts[ident("poslite")] = 21000
        self.count_all(st, ["poslite"])
        t = self.rec(st, "poslite")
        self.assertEqual((t["tier"], t.get("cells", 1), t["slot"]), (3, 1, slot))
        self.assertEqual(t["show"]["tier"], [0, 3])

    def test_never_a_step_down(self):
        st = self.make(self.island())
        self.counts[ident("v4-plus")] = 100
        self.count_all(st, ["v4-plus"])
        t = self.rec(st, "v4-plus")
        self.assertEqual((t["tier"], t["cells"], t["peak"]), (1, 3, 1117407))


# ---------------------------------------------------------------------------
# layout(): the big lands
# ---------------------------------------------------------------------------

def one(rec):
    return View(ac.layout(world_of(rec), PLANS))


class TestLayoutBig(unittest.TestCase):
    def test_view_keys_and_hall(self):
        for rec, shift in ((big("v4-plus", "oasis", [-1, -1], 1, 1117407), 4),
                           (big("v4-pospro", "harbor", [1, -1], 2, 465653), 2),
                           (big("poslite", "meadow", [0, 2], 3, 45921), 0),
                           (record("tiny", "ridge", [2, 2], 300), 0)):
            with self.subTest(name=rec["name"]):
                v = one(rec)
                t = v.by_name[rec["name"]]
                cells = rec.get("cells", 1)
                i, j = rec["slot"]
                self.assertEqual(t.get("tier"), rec.get("tier", 0))
                self.assertEqual(t.get("cells"), cells)
                self.assertEqual(t["slot"], rec["slot"])
                self.assertEqual(t["cx"], i * ac.CELL + (cells - 1) * ac.CELL // 2 - shift)
                self.assertEqual(t["cz"], j * ac.CELL + (cells - 1) * ac.CELL // 2)
                for x in (t["cx"] - 1, t["cx"]):
                    for z in (t["cz"] - 1, t["cz"]):
                        self.assertEqual(v.tile(x, z), "H")

    def test_land_size_by_level(self):
        sizes = {}
        for rec in (big("a", "oasis", [-1, -1], 1, 800000), big("b", "oasis", [-1, -1], 2, 200000),
                    big("c", "oasis", [0, 0], 3, 20000), record("d", "oasis", [0, 0], 19999)):
            v = one(rec)
            t = v.by_name[rec["name"]]
            sizes[rec["name"]] = len(v.tiles(t, "grPHurtB"))
        self.assertGreater(sizes["a"], 1400)
        self.assertGreater(sizes["b"], 650)
        self.assertGreater(sizes["a"], 1.5 * sizes["b"])
        self.assertGreater(sizes["b"], 2 * sizes["c"])
        self.assertGreater(sizes["c"], sizes["d"])

    def test_inside_its_square(self):
        rec = big("v4-pospro", "harbor", [0, 0], 2, 465653)
        v = one(rec)
        t = v.by_name["v4-pospro"]
        x0, x1, z0, z1 = v.box(t)
        for r, row in enumerate(v.v["rows"]):
            for c, ch in enumerate(row):
                if ch in "grPHu":
                    x, z = v.v["x0"] + c, v.v["z0"] + r
                    self.assertTrue(x0 <= x <= x1 and z0 <= z <= z1, (ch, x, z))

    def test_tier_1_river_bridge_and_landmark(self):
        rec = big("v4-plus", "oasis", [-1, -1], 1, 1117407)
        v = one(rec)
        t = v.by_name["v4-plus"]
        cx, cz = t["cx"], t["cz"]
        for z in range(cz - 15, cz + 16):
            self.assertTrue(any(v.tile(x, z) == "w" for x in range(cx + 8, cx + 21)), "the river at row %d" % z)
        ez = PLAN["oasis"]["exits"]["E"][1]
        self.assertTrue(any(v.tile(x, cz + ez) == "B" for x in range(cx + 8, cx + 21)), "the bridge on the east road")
        self.assertTrue(v.reach((cx, cz), lambda x, z: x > cx + 18 and v.tile(x, z) in "rg"),
                        "the hall reaches the far bank")
        mark = t.get("mark")
        self.assertIsInstance(mark, list)
        river_x = max(x for x in range(cx + 8, cx + 21) if v.tile(x, int(math.floor(mark[1]))) == "w")
        self.assertGreater(mark[0], river_x)
        self.assertEqual(v.tile(int(math.floor(mark[0])), int(math.floor(mark[1]))), "u")
        for b in buildings(t):
            self.assertGreater(math.hypot(b[0] - mark[0], b[1] - mark[1]), 1.5, "the landmark stands alone")

    def test_rings(self):
        t1 = one(big("a", "oasis", [-1, -1], 1, 800000)).by_name["a"]
        t1g = one(big("a", "oasis", [-1, -1], 1, 3200000)).by_name["a"]
        t2 = one(big("b", "meadow", [-1, -1], 2, 300000)).by_name["b"]
        t3 = one(big("c", "meadow", [0, 0], 3, 50000)).by_name["c"]
        self.assertEqual([r["kind"] for r in t1["rings"]], ["elev"])
        self.assertEqual(sorted(r["kind"] for r in t1g["rings"]), ["elev", "outer"])
        self.assertEqual([r["kind"] for r in t2["rings"]], ["ring"])
        self.assertEqual(t3.get("rings"), [])
        self.assertIsNone(t2.get("mark"))
        self.assertIsNone(t3.get("mark"))

    def test_background_on_u_tiles_only(self):
        for rec in (big("a", "oasis", [-1, -1], 1, 1117407), big("b", "harbor", [-1, -1], 2, 465653),
                    big("c", "ridge", [0, 0], 3, 94097)):
            with self.subTest(name=rec["name"]):
                v = one(rec)
                t = v.by_name[rec["name"]]
                self.assertTrue(t["bg"])
                for b in t["bg"]:
                    self.assertEqual(len(b), 6)
                    for x, z in bg_rect_tiles(b):
                        self.assertEqual(v.tile(x, z), "u", (b, x, z))

    def test_background_never_on_the_town(self):
        for rec in (big("a", "oasis", [-1, -1], 1, 3200000), big("b", "harbor", [-1, -1], 2, 790000),
                    big("c", "ridge", [0, 0], 3, 190000)):
            with self.subTest(name=rec["name"]):
                v = one(rec)
                t = v.by_name[rec["name"]]
                plan = PLAN[rec["plan"]]
                ox, oz = t["cx"], t["cz"]
                spots = [(x, z) for x, z, _ in plan["plots"]] + [tuple(o) for o in plan["offices"]]
                rx, rz = plan["rest"]
                spots += [(rx + a, rz + b) for a in (0, 1) for b in (0, 1)]
                spots += [(a, b) for a in (-1, 0) for b in (-1, 0)]
                for x, z in spots:
                    self.assertNotEqual(v.tile(ox + x, oz + z), "u", (x, z))

    def test_zones_heights_and_order(self):
        t1 = one(big("a", "oasis", [-1, -1], 1, 800000)).by_name["a"]
        t2 = one(big("b", "oasis", [-1, -1], 2, 790000)).by_name["b"]
        t3 = one(big("c", "oasis", [0, 0], 3, 199999)).by_name["c"]
        z1, z2, z3 = ({b[5] for b in t["bg"]} for t in (t1, t2, t3))
        self.assertTrue({"fill", "bund", "cbd", "mid", "res"} <= z1, z1)
        self.assertTrue({"fill", "cbd", "mid"} <= z2, z2)
        self.assertTrue({"main", "fill", "edge"} <= z3, z3)
        self.assertFalse(z3 & {"cbd", "bund", "mid", "res", "ind", "park"})
        top = lambda t: max(b[4] for b in buildings(t))  # noqa: E731
        self.assertGreater(top(t1), top(t2))
        self.assertGreater(top(t2), top(t3))

        def first(t, zone):
            return min(k for k, b in enumerate(t["bg"]) if b[5] == zone)
        self.assertLess(first(t1, "fill"), first(t1, "bund"))
        self.assertLess(first(t1, "bund"), first(t1, "cbd"))
        self.assertLess(first(t1, "cbd"), first(t1, "mid"))
        self.assertLess(first(t1, "mid"), first(t1, "res"))
        self.assertLess(first(t2, "fill"), first(t2, "cbd"))
        self.assertLess(first(t2, "cbd"), first(t2, "mid"))
        self.assertLess(first(t3, "main"), first(t3, "fill"))
        self.assertLess(first(t3, "fill"), first(t3, "edge"))

    def test_more_lines_more_city(self):
        for tier, lo, hi, slot in ((1, 800000, 3000000, [-1, -1]), (2, 200000, 790000, [-1, -1]),
                                   (3, 20000, 190000, [0, 0])):
            with self.subTest(tier=tier):
                a = one(big("a", "meadow", slot, tier, lo)).by_name["a"]
                b = one(big("a", "meadow", slot, tier, hi)).by_name["a"]
                self.assertGreaterEqual(len(buildings(b)), len(buildings(a)))
                self.assertGreater(len(buildings(b)) + sum(x[4] for x in buildings(b)),
                                   len(buildings(a)) + sum(x[4] for x in buildings(a)))

    def test_small_town_as_before(self):
        v = one(record("tiny", "meadow", [0, 0], 15000))
        t = v.by_name["tiny"]
        self.assertEqual(t.get("bg"), [])
        self.assertEqual(t.get("rings"), [])
        self.assertIsNone(t.get("mark"))
        self.assertFalse(v.tiles(t, "u"))

    def test_caps(self):
        caps = const(self, "BG_CAP")
        self.assertEqual(caps, {1: 480, 2: 170, 3: 60})
        self.assertEqual(const(self, "BG_TOTAL"), 900)
        for rec in (big("a", "oasis", [-1, -1], 1, 5000000), big("b", "oasis", [-1, -1], 2, 799999),
                    big("c", "oasis", [0, 0], 3, 199999)):
            t = one(rec).by_name[rec["name"]]
            self.assertLessEqual(len(buildings(t)), caps[rec["tier"]])

    def test_a_cut_drops_from_the_end(self):
        rec = big("a", "oasis", [-1, -1], 1, 3000000)
        full = one(rec).by_name["a"]["bg"]
        old = dict(ac.BG_CAP)
        try:
            ac.BG_CAP[1] = 40
            cut = one(rec).by_name["a"]["bg"]
        finally:
            ac.BG_CAP.clear()
            ac.BG_CAP.update(old)
        self.assertEqual(len([b for b in cut if b[5] != "park"]), 40)
        self.assertEqual(cut, full[:len(cut)])

    def test_the_page_total(self):
        world = world_of(big("a", "oasis", [-4, -1], 1, 5000000), big("b", "meadow", [-1, -1], 1, 5000000),
                         big("c", "ridge", [2, -1], 1, 5000000))
        view = ac.layout(world, PLANS)
        old = ac.BG_TOTAL
        try:
            ac.BG_TOTAL = 10 ** 6
            whole = {t["name"]: t["bg"] for t in ac.layout(world, PLANS)["territories"]}
        finally:
            ac.BG_TOTAL = old
        total = sum(len(buildings(t)) for t in view["territories"])
        self.assertGreater(sum(len([b for b in v if b[5] != "park"]) for v in whole.values()), 900)
        self.assertLessEqual(total, 900)
        self.assertGreater(total, 850)
        for t in view["territories"]:
            self.assertEqual(t["bg"], whole[t["name"]][:len(t["bg"])], "a prefix of its own list")

    def test_same_world_same_city(self):
        rec = big("a", "oasis", [-1, -1], 1, 1117407)
        self.assertEqual(ac.layout(world_of(rec), PLANS), ac.layout(world_of(json.loads(json.dumps(rec))), PLANS))


class TestLayoutIsland(unittest.TestCase):
    def owner(self):
        world = owner_world(counted=True)
        need(self, "re_lay")(world, PLANS)
        world["tiers"] = True
        return world

    def test_no_square_overlaps_and_all_touch(self):
        world = self.owner()
        TestReLay.check_rule(self, world)
        v = View(ac.layout(world, PLANS))
        self.assertEqual(len(v.v["territories"]), 7)

    def test_every_neighbour_is_reachable(self):
        world = self.owner()
        view = ac.layout(world, PLANS)
        v = View(view)
        by_id = {t["id"]: t for t in view["territories"]}
        sq = squares(world)
        pairs = {(a, b) for a in sq for b in sq if a < b and touches(sq[a], sq[b])}
        linked = {tuple(sorted((by_id[l["a"]]["name"], by_id[l["b"]]["name"]))) for l in view["links"]}
        self.assertEqual(linked, pairs)
        for a, b in sorted(pairs):
            ta, tb = v.by_name[a], v.by_name[b]
            with self.subTest(a=a, b=b):
                self.assertTrue(v.reach((ta["cx"], ta["cz"]), lambda x, z: (x, z) == (tb["cx"], tb["cz"])))

    def test_big_coast_city_has_its_sea(self):
        world = self.owner()
        view = ac.layout(world, PLANS)
        v = View(view)
        t = v.by_name["v4-pospro"]
        x0, x1, z0, z1 = v.box(t)
        sea = [(x, z) for x in range(x0, x1 + 1) for z in range(z1 - 4, z1 + ac.SEA_ROWS + 1) if v.tile(x, z) == "s"]
        self.assertGreater(len(sea), 40)

    def test_the_big_city_stands_out(self):
        world = self.owner()
        v = View(ac.layout(world, PLANS))
        land = {n: len(v.tiles(t, "grPHurtB")) for n, t in v.by_name.items()}
        top = {n: max([b[4] for b in buildings(t)] or [0]) for n, t in v.by_name.items()}
        others = [n for n in land if n != "v4-plus"]
        self.assertTrue(all(land["v4-plus"] > 1.5 * land[n] for n in others), land)
        self.assertTrue(all(top["v4-plus"] > top[n] for n in others), top)

    def test_the_cloud_picture_fits(self):
        base = os.path.realpath(tempfile.mkdtemp(prefix="city_tier_cloud_"))
        try:
            path = os.path.join(base, "world.json")
            ac.save_world(path, self.owner())
            st = ac.CityState(decisions_path=os.path.join(base, "d.jsonl"), world_path=path, plans=PLANS,
                              count_fn=lambda i: None, balance_fn=lambda i, r: {"kinds": {}, "files": {}, "bad": []})
            world = st.cloud_world([ident(n) for n, _, _, _ in OWNER])
            names = {t["name"]: t for t in world["territories"]}
            self.assertEqual(names["v4-plus"]["tier"], 1)
            self.assertTrue(names["v4-plus"]["bg"])
            self.assertTrue(names["v4-plus"]["rings"])
            self.assertTrue(names["v4-plus"]["mark"])
            snap = {"type": "snapshot", "world": world}
            clean = ac.cloud_clean(snap)
            self.assertIsNotNone(clean)
            t = {x["name"]: x for x in clean["world"]["territories"]}["v4-plus"]
            for key in ("tier", "cells", "bg", "rings", "mark"):
                self.assertIn(key, t)
            self.assertLess(len(json.dumps(clean["world"]).encode()), ac.CLOUD_VIEW_MAX_BYTES * 0.8)
        finally:
            shutil.rmtree(base, ignore_errors=True)


# ---------------------------------------------------------------------------
# the arrangement on squares
# ---------------------------------------------------------------------------

class TestArrangeSquares(Case):
    def island(self):
        world = owner_world(counted=True)
        need(self, "re_lay")(world, PLANS)
        world["tiers"] = True
        return world

    def tid(self, name):
        return ac.territory_id(ident(name))

    def test_a_square_must_stay_inside(self):
        st = self.make(self.island())
        code, body = st.set_layout([{"id": self.tid("v4-plus"), "slot": [3, 3]}])
        self.assertEqual((code, body), (409, {"error": "taken"}))
        self.assertEqual(self.rec(st, "v4-plus")["slot"], [-1, -1])

    def test_no_cell_of_a_square_is_free(self):
        st = self.make(self.island())
        code, body = st.set_layout([{"id": self.tid("poslite"), "slot": [1, 1]}])   # inside v4-plus
        self.assertEqual((code, body), (409, {"error": "taken"}))

    def test_the_sea_row_of_a_big_coast_city(self):
        st = self.make(self.island())
        t = self.rec(st, "v4-pospro")
        sea_cell = [t["slot"][0] + 1, t["slot"][1] + 2]
        held = set().union(*squares(st.world).values())
        if tuple(sea_cell) in held:
            self.skipTest("the sea row is held by the re-lay rule, see TestReLay")
        code, body = st.set_layout([{"id": self.tid("poslite"), "slot": sea_cell}])
        self.assertEqual((code, body), (409, {"error": "sea"}))

    def test_a_big_city_moves_whole(self):
        st = self.make(self.island())
        held = squares(st.world)
        others = set().union(*[v for k, v in held.items() if k != "plus-3"])
        cells = len(held["plus-3"]) ** 0.5
        want = None
        for i in range(-4, 4):
            for j in range(-4, 4):
                sq = square([i, j], int(cells))
                if sq & others or not touches(sq, others) or sq == held["plus-3"]:
                    continue
                want = [i, j]
                break
            if want:
                break
        self.assertIsNotNone(want)
        code, body = st.set_layout([{"id": self.tid("plus-3"), "slot": want}])
        if code == 409 and body == {"error": "sea"}:
            self.skipTest("that place breaks the coast rule")
        self.assertEqual(code, 200, body)
        self.assertEqual(self.rec(st, "plus-3")["slot"], want)
        self.assertEqual(self.rec(st, "plus-3")["cells"], 2)

    def test_shown_again_where_its_square_fits(self):
        world = self.island()
        world["territories"][ident("plus-3")]["hidden"] = True
        st = self.make(world)
        old = list(self.rec(st, "plus-3")["slot"])
        # put a small land on one cell of its old square
        code, _ = st.set_layout([{"id": self.tid("poslite"), "slot": [old[0] + 1, old[1] + 1]}])
        if code != 200:
            self.skipTest("that cell does not touch a land in this island")
        code, body = st.set_layout([{"id": self.tid("plus-3"), "hidden": False}])
        self.assertEqual(code, 200, body)
        self.assertEqual(self.rec(st, "plus-3")["cells"], 2)
        TestReLay.check_rule(self, st.world, touch=False)

    def test_a_new_repo_never_lands_in_a_square(self):
        world = self.island()
        for k in range(12):
            t = ac.add_territory(world, PLANS, "/new/%d/.git" % k, "n%d" % k, 0)
            self.assertEqual(t.get("cells", 1), 1)
        TestReLay.check_rule(self, world)


class TestDemo(unittest.TestCase):
    def test_the_demo_shows_the_levels(self):
        view = ac.demo_world()
        by = {t["name"]: t for t in view["territories"]}
        self.assertEqual((by["v4-plus"]["tier"], by["v4-plus"]["cells"]), (1, 3))
        self.assertEqual(by["pos-lite"]["tier"], 3)
        self.assertEqual(by["auto-pipeline"]["tier"], 0)
        self.assertTrue(by["v4-plus"]["bg"])
        self.assertTrue(by["v4-plus"]["mark"])


if __name__ == "__main__":
    unittest.main()
