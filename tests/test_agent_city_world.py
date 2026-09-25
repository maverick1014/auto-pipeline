"""Failing tests for the city's world: growth and persistence (requirements/city.md,
"Growth" and "Persistence"). Approved mock: mock/city-growth-mock.html (its
WORLD LAYOUT script is the reference algorithm; its <script id="city-plans">
is the plan data). The Balance section is NOT built here; only room is left.

CONTRACT (bin/agent_city.py, Python standard library only)

  Plans   bin/agent-city-plans.json == the mock's city-plans JSON, exactly,
          apart from city-people's "offices" and "rest" keys per plan.
          {"v": 1, "plans": [5 plans]}. A plan: id, terrain, name, edge (12
          radius factors, one per 30 degrees from +x, z grows south), roads
          ([x0, z0, x1, z1] inclusive, axis-aligned, local tiles), exits
          {"E","W","N","S": [x, z] or null}, sea ("S" or null), plots
          ([x, z, district] in growth order). Hall = local tiles x, z in
          {-1, 0}; plaza ring = the box -2..1 around it.
          load_plans(path=None) -> the list of plans (default: the file above).

  Constants  CELL 26, HALF 13, R0 1.9, RMAX 8.6, L0 50, LCAP 1000000,
          KIND_TYPE {test: tower, ui: shop, script: workshop, doc: library,
          other: house}, RECOUNT_SEC 300.

  Pure world functions (no files, no clock):
    fnv1a(text) -> 32-bit FNV-1a of the UTF-8 bytes.
    territory_id(identity) -> "%08x" % fnv1a(identity).
    repo_name(identity) -> ".../shop/.git" -> "shop", ".../shop.git" -> "shop",
          ".../shop" -> "shop", "dir:shop" -> "shop".
    growth(lines) -> log1p(lines / L0) / log1p(LCAP / L0), capped to 0..1.
    radius(lines) -> R0 + (RMAX - R0) * growth(lines).
    territory_tiles(plan, identity, lines) -> {"r", "g", "open", "land"}:
          land = set of local (x, z) tiles: the hall, every tile whose centre
          lies inside the organic edge (radius * the plan edge with a repo
          jitter seeded from fnv1a(identity)), the first "open" plots and
          their front road tile. open = number of plots, in plan order, whose
          running-max need fits the radius (see the mock).
    new_world() -> {"v": 1, "territories": {}, "order": []}
    add_territory(world, plans, identity, name, lines=0) -> the territory
          record, stored under world["territories"][identity] and appended
          to world["order"]; a known identity returns the stored record,
          unchanged. Record: {"name", "plan" (plan id), "slot" [i, j],
          "lines" (last count), "peak" (biggest count ever: the size uses
          it, so deleting code never shrinks a territory or strands a
          building), "buildings" [], "era": "village"} (era: room for
          Balance, not used yet). Plan: fnv1a(identity) % 5, then the next plan not in
          use; a coast plan needs a free slot with its south slot free. Slot:
          spiral order, 4-adjacent to a used slot, never south of a coast.
    build(world, plans, identity, kind, owner, by, now) -> building or None.
          type = KIND_TYPE[kind] ("" or unknown kind -> None). None when the
          owner already has a building in that territory, or when no open
          plot of that district is free. Else the first free open plot of
          that district in plan order: {"plot": k, "type", "owner", "by",
          "at": now}, appended to the territory's buildings.
    layout(world, plans) -> the view the page draws:
          {"cell": 26, "x0", "z0", "w", "h", "rows": [h strings of w chars],
           "territories": [{"id", "name", "plan", "terrain", "slot", "cx",
              "cz", "lines", "size", "r", "open", "plots_total",
              "plots": [{"k", "x", "z", "d"}] (open plots, world tiles),
              "buildings": [{"plot", "type", "by", "x", "z"}]}],
           "links": [{"a", "b", "gap", "kind", "cross": [[x, z], ...]}]}
          World tile (X, Z) = rows[Z - z0][X - x0]. A territory in slot
          (i, j) has its hall centre at (26 i, 26 j). Map chars:
            ' ' void  . wild  g territory ground  r road  t track  H hall
            P open plot  w river  k ravine  m mountain pass  f forest belt
            B bridge  b beach  s sea
          Links: every pair of 4-adjacent territories. gap by terrain pair
          (mock GAPS table, same terrain -> river); river and ravine ->
          kind "bridge", pass and forest -> "road". cross = the belt tiles
          the link road crosses ('B' for a bridge, 't' for a road).

  Persistence
    world_path() -> $AGENT_CITY_HOME/world.json, default
          ~/.claude/agent-city/world.json.
    save_world(path, world): makes the folder, writes a temp file in the
          same folder, then os.replace. Never leaves the temp file.
    load_world(path, plans) -> (world, notice). Missing file -> (new_world(),
          None). Unreadable, not JSON, not a dict, "v" != 1, or a territory
          with an unknown plan or a bad slot -> the file is renamed to
          world.json.bad-<YYYYmmdd-HHMMSS> (same bytes), (new_world(), a
          Chinese notice that names that file). Unknown extra keys are kept.

  Code lines (cheap; never the repo's tests)
    counts_as_code(path) -> False for images, 3D models, fonts, audio, video,
          archives, pdf, lock files, minified or generated files, and anything
          under vendor/, node_modules/, dist/, build/, third_party/; True for
          other text files.
    count_lines(identity) -> added lines of `git --git-dir=<identity> diff
          --numstat <empty tree> HEAD`, only rows counts_as_code keeps
          (binary rows "-" never count). Not a git dir or no commit -> 0.
          Runs git only, through subprocess.run.
    CityState(..., world_path=PATH, plans=PLANS, count_fn=FN): loads the
          world from PATH at start (.world is the dict, .notice the load
          notice or None); world_path None = memory only, never saved.
          feed_line never calls count_fn. recount(now) calls it (outside the
          lock) for each territory that had a line since its last count and
          was last counted RECOUNT_SEC or more ago (never counted in this
          run: due with its first line; a world loaded from the file counts
          nothing until a line comes; a line that arrives while counting keeps
          the territory due), stores lines and peak, returns how many it
          counted. A count
          that changes a territory sends a world event and saves the file.
          The server calls recount from a background thread about every 2 s,
          with the same clock it gives feed_line.

  Server (python3 bin/agent_city.py serve ... --world PATH)
    Default --world is world_path(). Loads it at start. The /events snapshot
    carries "world" (layout view) and, after a moved-aside file, "notice".
    A line with "repo" (the hook's git common dir; a line with no repo never
    makes one, tests/test_agent_city_land.py) makes its territory on first sight: {"type": "world", "world": view} is
    sent and the file saved at once (every change is saved at once). Spawn events and snapshot agents carry "terr"
    (territory id); the snapshot "gov" and gov events carry "terr" too.
    PostToolUse with a "kind" builds for its agent (owner = aid, or "s:" +
    sid): {"type": "build", "id" (citizen id, "gov" for the governor),
    "terr", "plot", "btype", "x", "z", "by"}; file saved. Buildings never
    leave, whatever the agent does. Stop, restart: same world, same plan per
    repo. python3 bin/agent_city.py demo-world prints the demo view (JSON)
    the page embeds for #demo.
    bin/agent-city.sh start passes --world "$AGENT_CITY_HOME/world.json"
    (default $HOME/.claude/agent-city).

  No test here touches the real ~/.claude/agent-city: every server gets
  AGENT_CITY_HOME and HOME in a temp folder.
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
MOCK = os.path.join(ROOT, "mock", "city-growth-mock.html")
PLANS_FILE = os.path.join(BIN, "agent-city-plans.json")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from test_agent_city_server import ServerCase, wait_for  # noqa: E402

TERRAINS = {"grassland", "mountain", "desert", "forest", "coast"}
TYPES = {"house", "shop", "tower", "workshop", "library"}
MAP_CHARS = set(" .grtHPwkmfBbs")
WALK = set(".grtBb")
TERR_CHARS = set("grPH")


def plans():
    return ac.load_plans()


def world_of(*repos):
    """repos: (identity, lines) in arrival order."""
    ps = plans()
    w = ac.new_world()
    for ident, lines in repos:
        ac.add_territory(w, ps, ident, ac.repo_name(ident), lines)
    return w


def ids(n, tag="r"):
    return ["/work/%s%d/app%d/.git" % (tag, i, i) for i in range(n)]


def tile(view, x, z):
    r, c = z - view["z0"], x - view["x0"]
    if 0 <= r < view["h"] and 0 <= c < view["w"]:
        return view["rows"][r][c]
    return " "


def terr_tiles(view, t):
    """Territory tiles (g r P H) inside territory t's cell."""
    out = set()
    for x in range(t["cx"] - 13, t["cx"] + 13):
        for z in range(t["cz"] - 13, t["cz"] + 13):
            if tile(view, x, z) in TERR_CHARS:
                out.add((x - t["cx"], z - t["cz"]))
    return out


def straight_run(view):
    """Longest run of rows (or columns) whose first land tile from one side is
    in the same place: a straight piece of the land's outer edge."""
    best = 0
    rows, w, h = view["rows"], view["w"], view["h"]
    for n, m, get in ((h, w, lambda i, k: rows[i][k]), (w, h, lambda i, k: rows[k][i])):
        for side in (0, 1):
            prev, run = None, 0
            for i in range(n):
                v = None
                for k in range(m):
                    kk = m - 1 - k if side else k
                    if get(i, kk) != " ":
                        v = kk
                        break
                if v is not None and v == prev:
                    run += 1
                    best = max(best, run)
                else:
                    run = 1
                prev = v
    return best


# ---------------------------------------------------------------------------
# Plans: the five hand-made town plans from the approved mock
# ---------------------------------------------------------------------------

class TestPlans(unittest.TestCase):
    def test_plans_file_is_the_approved_mock_data(self):
        with open(MOCK, encoding="utf-8") as fh:
            m = re.search(r'<script type="application/json" id="city-plans">(.*?)</script>', fh.read(), re.S)
        self.assertIsNotNone(m)
        with open(PLANS_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        # city-people adds each plan's "offices" and "rest" spots (tests/test_agent_city_chain.py)
        for plan in data["plans"]:
            plan.pop("offices", None)
            plan.pop("rest", None)
        self.assertEqual(data, json.loads(m.group(1)))

    def test_five_plans_one_per_terrain(self):
        ps = plans()
        self.assertEqual(len(ps), 5)
        self.assertEqual({p["terrain"] for p in ps}, TERRAINS)
        self.assertEqual(len({p["id"] for p in ps}), 5)

    def test_every_plan_is_complete(self):
        for p in plans():
            with self.subTest(plan=p["id"]):
                self.assertEqual(len(p["edge"]), 12)
                self.assertTrue(all(0.8 <= e <= 1.2 for e in p["edge"]))
                roads = set()
                for x0, z0, x1, z1 in p["roads"]:
                    self.assertTrue(x0 == x1 or z0 == z1, "roads are straight")
                    for x in range(min(x0, x1), max(x0, x1) + 1):
                        for z in range(min(z0, z1), max(z0, z1) + 1):
                            self.assertTrue(-13 <= x < 13 and -13 <= z < 13)
                            roads.add((x, z))
                for d, ex in p["exits"].items():
                    if ex is None:
                        self.assertEqual((p["terrain"], d), ("coast", "S"), "only the coast has no south exit")
                    else:
                        self.assertIn(tuple(ex), roads, "exit %s is on a road" % d)
                self.assertEqual(p["sea"], "S" if p["terrain"] == "coast" else None)
                self.assertGreaterEqual(len(p["plots"]), 30)
                spots = [(x, z) for x, z, _ in p["plots"]]
                self.assertEqual(len(spots), len(set(spots)), "two plots on one tile")
                for x, z, d in p["plots"]:
                    self.assertIn(d, TYPES)
                    self.assertNotIn((x, z), roads)
                    self.assertFalse(-2 <= x <= 1 and -2 <= z <= 1, "no plot on the hall or its plaza")
                    self.assertTrue({(x, z + 1), (x + 1, z), (x - 1, z), (x, z - 1)} & roads, "a plot fronts a road")
                for d in TYPES:
                    self.assertGreaterEqual(sum(1 for q in p["plots"] if q[2] == d), 4, "district %s" % d)

    def test_every_plot_opens_by_the_cap(self):
        for p in plans():
            with self.subTest(plan=p["id"]):
                self.assertEqual(ac.territory_tiles(p, "/x/.git", ac.LCAP)["open"], len(p["plots"]))


# ---------------------------------------------------------------------------
# Size from code lines
# ---------------------------------------------------------------------------

class TestSize(unittest.TestCase):
    def test_constants(self):
        self.assertEqual((ac.CELL, ac.HALF), (26, 13))
        self.assertEqual((ac.R0, ac.RMAX, ac.L0, ac.LCAP), (1.9, 8.6, 50, 1000000))
        self.assertEqual(ac.KIND_TYPE, {"test": "tower", "ui": "shop", "script": "workshop",
                                        "doc": "library", "other": "house"})
        self.assertEqual(ac.RECOUNT_SEC, 300)

    def test_log_scale_and_capped(self):
        self.assertEqual(ac.growth(0), 0)
        self.assertEqual(ac.growth(-5), 0)
        self.assertAlmostEqual(ac.growth(500), math.log1p(10) / math.log1p(20000), places=9)
        self.assertEqual(ac.growth(1000000), 1)
        self.assertEqual(ac.growth(5000000), 1)
        self.assertAlmostEqual(ac.radius(0), 1.9)
        self.assertAlmostEqual(ac.radius(10 ** 7), 8.6)
        seq = [ac.growth(n) for n in (0, 10, 100, 1000, 10000, 100000, 250000, 1000000)]
        self.assertEqual(seq, sorted(seq))
        self.assertEqual(len(set(seq)), len(seq), "smooth: every step grows")

    def test_big_repos_still_differ(self):
        """Mock review: 250k and 1M lines must not look the same."""
        p = plans()[0]
        a = ac.territory_tiles(p, "/x/.git", 250000)["land"]
        b = ac.territory_tiles(p, "/x/.git", 1000000)["land"]
        self.assertGreater(len(b), len(a) * 1.1)

    def test_day_zero_is_a_tiny_town_hall_and_one_plot_per_district(self):
        # city-people (requirements 3bec3dd + main manager): the minimum land opens the first plot of every
        # district so any first edit can build; no building on day 0 (tests/test_agent_city_minland.py)
        for i, p in enumerate(plans()):
            with self.subTest(plan=p["id"]):
                districts = len({d for _, _, d in p["plots"]})
                t = ac.territory_tiles(p, "/day0/%d/.git" % i, 0)
                self.assertEqual(t["open"], districts)
                self.assertTrue({(-1, -1), (0, -1), (-1, 0), (0, 0)} <= t["land"])
                w = world_of(("/day0/%d/.git" % i, 0))
                v = ac.layout(w, plans())
                chars = [tile(v, x, z) for x in range(-13, 13) for z in range(-13, 13)]
                self.assertEqual(chars.count("P"), districts, "one open plot per district")
                self.assertEqual(v["territories"][0]["buildings"], [], "no building on day 0")

    def test_growth_adds_land_at_the_edge_and_keeps_the_old_land(self):
        p = plans()[1]
        prev = None
        for n in (0, 50, 500, 5000, 50000, 250000, 1000000):
            land = ac.territory_tiles(p, "/grow/.git", n)["land"]
            if prev is not None:
                self.assertTrue(prev <= land, "land never shrinks or moves")
                self.assertGreater(len(land), len(prev))
            prev = land


# ---------------------------------------------------------------------------
# Shape: organic, uneven, the same every time for the same repo
# ---------------------------------------------------------------------------

class TestShape(unittest.TestCase):
    def test_never_a_square(self):
        for i, p in enumerate(plans()):
            for n in (5000, 1000000):
                with self.subTest(plan=p["id"], lines=n):
                    land = ac.territory_tiles(p, "/shape/%d/.git" % i, n)["land"]
                    xs = [x for x, _ in land]
                    zs = [z for _, z in land]
                    box = (max(xs) - min(xs) + 1) * (max(zs) - min(zs) + 1)
                    self.assertLess(len(land) / box, 0.88, "fills its bounding box like a rectangle")
                    widths = {sum(1 for x, z in land if z == row) for row in set(zs)}
                    self.assertGreaterEqual(len(widths), 4, "row widths all alike")

    def test_same_repo_same_shape(self):
        p = plans()[2]
        self.assertEqual(ac.territory_tiles(p, "/a/.git", 20000)["land"],
                         ac.territory_tiles(p, "/a/.git", 20000)["land"])
        v1 = ac.layout(world_of(("/a/.git", 20000), ("/b/.git", 300)), plans())
        v2 = ac.layout(world_of(("/a/.git", 20000), ("/b/.git", 300)), plans())
        self.assertEqual(v1, v2)

    def test_other_repo_other_shape(self):
        p = plans()[2]
        shapes = {frozenset(ac.territory_tiles(p, i, 20000)["land"]) for i in ids(4, "s")}
        self.assertEqual(len(shapes), 4)

    def test_ids_and_names(self):
        self.assertEqual(ac.fnv1a(""), 0x811c9dc5)
        self.assertEqual(ac.fnv1a("a"), 0xe40c292c)
        self.assertEqual(ac.territory_id("a"), "e40c292c")
        self.assertEqual(ac.repo_name("/home/u/code/shop/.git"), "shop")
        self.assertEqual(ac.repo_name("/srv/git/shop.git"), "shop")
        self.assertEqual(ac.repo_name("/srv/git/shop"), "shop")
        self.assertEqual(ac.repo_name("dir:notes"), "notes")


# ---------------------------------------------------------------------------
# Territories on one land: slots, plans, neighbours, gaps, sea
# ---------------------------------------------------------------------------

class TestLand(unittest.TestCase):
    def test_first_repo_in_the_middle_next_ones_beside_it(self):
        w = world_of(*[(i, 1000) for i in ids(6)])
        slots = [tuple(w["territories"][i]["slot"]) for i in w["order"]]
        self.assertEqual(slots[0], (0, 0))
        self.assertEqual(len(set(slots)), 6)
        for k, s in enumerate(slots[1:], 1):
            self.assertTrue(any(abs(s[0] - o[0]) + abs(s[1] - o[1]) == 1 for o in slots[:k]),
                            "slot %s touches no earlier territory" % (s,))

    def test_plan_from_the_identity_and_all_five_before_a_repeat(self):
        ps = plans()
        for n in range(20):
            ident = "/pick/%d/.git" % n
            w = world_of((ident, 0))
            want = ps[ac.fnv1a(ident) % 5]["id"]
            self.assertEqual(w["territories"][ident]["plan"], want)
        w = world_of(*[(i, 0) for i in ids(5, "p")])
        self.assertEqual(len({t["plan"] for t in w["territories"].values()}), 5)

    def test_known_repo_is_not_moved_or_replanned(self):
        ps = plans()
        w = world_of(*[(i, 0) for i in ids(3)])
        before = json.loads(json.dumps(w))
        again = ac.add_territory(w, ps, ids(3)[1], "other name", 99999)
        self.assertEqual(again["slot"], before["territories"][ids(3)[1]]["slot"])
        self.assertEqual(again["plan"], before["territories"][ids(3)[1]]["plan"])
        self.assertEqual(w["order"], before["order"])

    def test_record_leaves_room_for_balance(self):
        w = world_of(("/x/.git", 10))
        t = w["territories"]["/x/.git"]
        self.assertLessEqual({"name", "plan", "slot", "lines", "peak", "buildings", "era"}, set(t))
        self.assertEqual((t["lines"], t["peak"]), (10, 10))
        self.assertEqual(t["era"], "village")
        self.assertEqual(w["v"], 1)

    def test_map_shape_and_alphabet(self):
        v = ac.layout(world_of(*[(i, 3000 * (k + 1)) for k, i in enumerate(ids(4))]), plans())
        self.assertEqual(v["cell"], 26)
        self.assertEqual(len(v["rows"]), v["h"])
        for row in v["rows"]:
            self.assertEqual(len(row), v["w"])
            self.assertLessEqual(set(row), MAP_CHARS)

    def test_halls_where_the_slots_say(self):
        w = world_of(*[(i, 2000) for i in ids(4)])
        v = ac.layout(w, plans())
        self.assertEqual(len(v["territories"]), 4)
        for t in v["territories"]:
            self.assertEqual((t["cx"], t["cz"]), (26 * t["slot"][0], 26 * t["slot"][1]))
            for x in (t["cx"] - 1, t["cx"]):
                for z in (t["cz"] - 1, t["cz"]):
                    self.assertEqual(tile(v, x, z), "H")

    def test_one_land_every_hall_reachable_on_foot(self):
        for n in (2, 3, 6):
            with self.subTest(repos=n):
                v = ac.layout(world_of(*[(i, 1500 * (k + 1)) for k, i in enumerate(ids(n, "walk%d" % n))]), plans())
                halls = [(t["cx"], t["cz"]) for t in v["territories"]]
                start = (halls[0][0], halls[0][1] + 1)
                seen, todo = {start}, [start]
                while todo:
                    x, z = todo.pop()
                    for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                        if (nx, nz) not in seen and tile(v, nx, nz) in WALK:
                            seen.add((nx, nz))
                            todo.append((nx, nz))
                for hx, hz in halls[1:]:
                    near = {(hx + a, hz + b) for a in (-2, -1, 0, 1) for b in (-2, -1, 0, 1)}
                    self.assertTrue(near & seen, "hall %s cannot be reached on foot" % ((hx, hz),))

    def test_neighbours_split_by_a_gap_and_joined_by_a_bridge_or_road(self):
        GAP = {"river": "w", "ravine": "k", "pass": "m", "forest": "f"}
        seen = set()
        for tag in range(6):
            v = ac.layout(world_of(*[(i, 800) for i in ids(6, "gap%d" % tag)]), plans())
            by = {t["id"]: t for t in v["territories"]}
            pairs = {frozenset((a["id"], b["id"])) for a in v["territories"] for b in v["territories"]
                     if abs(a["slot"][0] - b["slot"][0]) + abs(a["slot"][1] - b["slot"][1]) == 1}
            self.assertEqual({frozenset((l["a"], l["b"])) for l in v["links"]}, pairs)
            for l in v["links"]:
                terr = sorted((by[l["a"]]["terrain"], by[l["b"]]["terrain"]))
                self.assertEqual(l["gap"], ac.gap_of(*terr))
                self.assertEqual(l["kind"], "bridge" if l["gap"] in ("river", "ravine") else "road")
                self.assertTrue(l["cross"], "the link road never crosses the gap")
                want = "B" if l["kind"] == "bridge" else "t"
                for x, z in l["cross"]:
                    self.assertEqual(tile(v, x, z), want)
                chars = "".join(v["rows"])
                self.assertIn(GAP[l["gap"]], chars)
                seen.add(l["gap"])
        self.assertEqual(ac.gap_of("grassland", "grassland"), "river")
        self.assertEqual(ac.gap_of("mountain", "grassland"), ac.gap_of("grassland", "mountain"))
        self.assertTrue({"river", "ravine", "pass", "forest"} & seen)

    def test_gap_belts_bend(self):
        GAP = {"river": "w", "ravine": "k", "pass": "m", "forest": "f"}
        v = ac.layout(world_of(*[(i, 800) for i in ids(3, "bend")]), plans())
        by = {t["id"]: t for t in v["territories"]}
        for l in v["links"]:
            a, b = by[l["a"]], by[l["b"]]
            ch = GAP[l["gap"]]
            across = a["slot"][1] == b["slot"][1]
            spots = set()
            for along in range(-9, 10):
                if across:
                    line, at = 13 + 26 * min(a["slot"][0], b["slot"][0]), a["cz"] + along
                    hits = [d for d in range(-4, 4) if tile(v, line + d, at) == ch]
                else:
                    line, at = 13 + 26 * min(a["slot"][1], b["slot"][1]), a["cx"] + along
                    hits = [d for d in range(-4, 4) if tile(v, at, line + d) == ch]
                if hits:
                    spots.add(min(hits))
            with self.subTest(link=l["gap"]):
                self.assertGreaterEqual(len(spots), 2, "the gap belt is one straight line")

    def test_outer_edge_is_never_a_long_straight_line(self):
        for n in (1, 3, 6):
            for tag in range(8):
                with self.subTest(repos=n, ids=tag):
                    v = ac.layout(world_of(*[(i, 1000 * (k + 1)) for k, i in enumerate(ids(n, "edge%d" % tag))]), plans())
                    self.assertLessEqual(straight_run(v), 6)

    def test_sea_only_by_the_coast(self):
        ps = plans()
        coast = next(p for p in ps if p["terrain"] == "coast")
        found = False
        for tag in range(12):
            w = world_of(*[(i, 500) for i in ids(6, "sea%d" % tag)])
            v = ac.layout(w, ps)
            coasts = [t for t in v["territories"] if t["plan"] == coast["id"]]
            slots = {tuple(t["slot"]) for t in v["territories"]}
            for t in coasts:
                self.assertNotIn((t["slot"][0], t["slot"][1] + 1), slots, "somebody lives in the sea")
            for r, row in enumerate(v["rows"]):
                for c, ch in enumerate(row):
                    if ch == "s":
                        found = True
                        x, z = v["x0"] + c, v["z0"] + r
                        self.assertTrue(any(abs(x - t["cx"]) <= 13 and t["cz"] - 13 <= z <= t["cz"] + 13 + 9
                                            for t in coasts), "sea away from any coast at %s" % ((x, z),))
        self.assertTrue(found, "no coast in 12 lands of 6 repos")
        no_coast = [i for i in ("/nc/%d/.git" % n for n in range(40)) if ps[ac.fnv1a(i) % 5]["terrain"] != "coast"][:1]
        v = ac.layout(world_of((no_coast[0], 1000)), ps)
        self.assertNotIn("s", "".join(v["rows"]))

    def test_nothing_off_plan(self):
        ps = {p["id"]: p for p in plans()}
        w = world_of(*[(i, 20000) for i in ids(3, "plan")])
        for ident in w["order"]:
            for k in ("ui", "test", "other", "doc", "script"):
                ac.build(w, list(ps.values()), ident, k, "o-" + k, "worker", 1.0)
        v = ac.layout(w, list(ps.values()))
        for t in v["territories"]:
            plan = ps[t["plan"]]
            # city-people: open plots are the view's "plots" (not always a plan-order prefix)
            spots = {(p["x"], p["z"]) for p in t["plots"]}
            self.assertEqual(len(spots), t["open"])
            ps_tiles = {(x, z) for x in range(t["cx"] - 13, t["cx"] + 13) for z in range(t["cz"] - 13, t["cz"] + 13)
                        if tile(v, x, z) == "P"}
            self.assertEqual(ps_tiles, spots)
            self.assertEqual({(p["x"], p["z"]) for p in t["plots"]}, spots)
            for b in t["buildings"]:
                self.assertIn((b["x"], b["z"]), spots)
                self.assertEqual(plan["plots"][b["plot"]][2], b["type"])


# ---------------------------------------------------------------------------
# Buildings: type from the kind of work, in its district, permanent
# ---------------------------------------------------------------------------

class TestBuild(unittest.TestCase):
    def setUp(self):
        self.ps = plans()
        self.id = "/b/.git"
        self.w = world_of((self.id, 1000000))
        self.plan = next(p for p in self.ps if p["id"] == self.w["territories"][self.id]["plan"])

    def test_kind_picks_the_type_and_its_district(self):
        for kind, typ in ac.KIND_TYPE.items():
            with self.subTest(kind=kind):
                b = ac.build(self.w, self.ps, self.id, kind, "own-" + kind, "worker", 5.0)
                self.assertEqual(b["type"], typ)
                self.assertEqual(self.plan["plots"][b["plot"]][2], typ)
                first = next(k for k, q in enumerate(self.plan["plots"]) if q[2] == typ)
                self.assertEqual(b["plot"], first, "the first plot of the district in plan order")
                self.assertEqual((b["owner"], b["by"], b["at"]), ("own-" + kind, "worker", 5.0))

    def test_one_building_per_agent(self):
        self.assertIsNotNone(ac.build(self.w, self.ps, self.id, "ui", "a1", "worker", 1.0))
        self.assertIsNone(ac.build(self.w, self.ps, self.id, "test", "a1", "worker", 2.0))
        self.assertEqual(len(self.w["territories"][self.id]["buildings"]), 1)

    def test_next_agent_takes_the_next_free_plot(self):
        a = ac.build(self.w, self.ps, self.id, "other", "a1", "w", 1.0)
        b = ac.build(self.w, self.ps, self.id, "other", "a2", "w", 1.0)
        self.assertNotEqual(a["plot"], b["plot"])
        self.assertLess(a["plot"], b["plot"])

    def test_full_district_builds_nothing(self):
        n = sum(1 for q in self.plan["plots"] if q[2] == "library")
        for i in range(n):
            self.assertIsNotNone(ac.build(self.w, self.ps, self.id, "doc", "d%d" % i, "w", 1.0))
        self.assertIsNone(ac.build(self.w, self.ps, self.id, "doc", "late", "w", 1.0))

    def test_day_zero_has_one_plot_per_district(self):
        # city-people (requirements 3bec3dd + main manager): any first edit builds, a second of the same
        # district waits for growth (tests/test_agent_city_minland.py)
        w = world_of(("/new/.git", 0))
        plan = next(p for p in self.ps if p["id"] == w["territories"]["/new/.git"]["plan"])
        districts = {d for _, _, d in plan["plots"]}
        for kind, district in ac.KIND_TYPE.items():
            if district not in districts:
                continue
            self.assertIsNotNone(ac.build(w, self.ps, "/new/.git", kind, "x-" + kind, "w", 1.0))
            self.assertIsNone(ac.build(w, self.ps, "/new/.git", kind, "y-" + kind, "w", 1.0))

    def test_no_kind_no_building(self):
        self.assertIsNone(ac.build(self.w, self.ps, self.id, "", "a1", "w", 1.0))
        self.assertIsNone(ac.build(self.w, self.ps, self.id, "bogus", "a1", "w", 1.0))
        self.assertIsNone(ac.build(self.w, self.ps, "/unknown/.git", "ui", "a1", "w", 1.0))


# ---------------------------------------------------------------------------
# Persistence: world.json
# ---------------------------------------------------------------------------

class TestWorldFile(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_world_")
        self.path = os.path.join(self.base, "home", "agent-city", "world.json")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_path_follows_agent_city_home(self):
        old = os.environ.get("AGENT_CITY_HOME")
        try:
            os.environ["AGENT_CITY_HOME"] = os.path.join(self.base, "h")
            self.assertEqual(ac.world_path(), os.path.join(self.base, "h", "world.json"))
            del os.environ["AGENT_CITY_HOME"]
            self.assertEqual(ac.world_path(), os.path.expanduser("~/.claude/agent-city/world.json"))
        finally:
            if old is None:
                os.environ.pop("AGENT_CITY_HOME", None)
            else:
                os.environ["AGENT_CITY_HOME"] = old

    def test_save_then_load_is_the_same_world(self):
        w = world_of(("/a/.git", 12000), ("/b/.git", 40))
        ac.build(w, plans(), "/a/.git", "ui", "a1", "worker", 3.0)
        w["territories"]["/a/.git"]["future_field"] = {"kept": True}
        ac.save_world(self.path, w)
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ["world.json"], "temp file left behind")
        loaded, notice = ac.load_world(self.path, plans())
        self.assertIsNone(notice)
        self.assertEqual(loaded, json.loads(json.dumps(w)))
        with open(self.path) as fh:
            self.assertEqual(json.load(fh)["v"], 1)

    def test_save_is_atomic(self):
        src = function_src(ac.save_world)
        self.assertIn("os.replace", src)
        self.assertRegex(src, r"tmp|temp|mkstemp")

    def test_missing_file_is_a_fresh_world(self):
        w, notice = ac.load_world(self.path, plans())
        self.assertEqual(w, ac.new_world())
        self.assertIsNone(notice)
        self.assertFalse(os.path.exists(os.path.dirname(self.path)) and os.listdir(os.path.dirname(self.path)))

    def test_broken_or_unknown_file_is_moved_aside(self):
        good = world_of(("/a/.git", 10))
        bad_slot = json.loads(json.dumps(good))
        bad_slot["territories"]["/a/.git"]["slot"] = "x"
        bad_plan = json.loads(json.dumps(good))
        bad_plan["territories"]["/a/.git"]["plan"] = "atlantis"
        cases = {"not json": b"{not json", "a list": b"[1, 2]", "future version": json.dumps(dict(good, v=2)).encode(),
                 "no version": json.dumps({"territories": {}, "order": []}).encode(),
                 "bad slot": json.dumps(bad_slot).encode(), "unknown plan": json.dumps(bad_plan).encode(),
                 "binary": b"\xff\xfe\x00junk"}
        for name, data in cases.items():
            with self.subTest(case=name):
                folder = os.path.dirname(self.path)
                shutil.rmtree(folder, ignore_errors=True)
                os.makedirs(folder)
                with open(self.path, "wb") as fh:
                    fh.write(data)
                w, notice = ac.load_world(self.path, plans())
                self.assertEqual(w, ac.new_world())
                aside = [f for f in os.listdir(folder) if f.startswith("world.json.bad-")]
                self.assertEqual(len(aside), 1)
                self.assertRegex(aside[0], r"^world\.json\.bad-\d{8}-\d{6}$")
                with open(os.path.join(folder, aside[0]), "rb") as fh:
                    self.assertEqual(fh.read(), data)
                self.assertFalse(os.path.exists(self.path))
                self.assertIsInstance(notice, str)
                self.assertIn(aside[0], notice)
                self.assertRegex(notice, r"[一-鿿]", "the page log is Chinese")


def function_src(fn):
    import inspect
    return inspect.getsource(fn)


# ---------------------------------------------------------------------------
# Code lines: what counts, cheap, cached
# ---------------------------------------------------------------------------

def git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    return subprocess.run(["git", "-C", cwd] + list(args), check=True, capture_output=True, text=True,
                          env=env, stdin=subprocess.DEVNULL).stdout.strip()


def make_repo(base, files):
    os.makedirs(base, exist_ok=True)
    git(base, "init", "-q", "-b", "main")
    for rel, content in files.items():
        path = os.path.join(base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(content if isinstance(content, bytes) else content.encode())
    git(base, "add", "-A")
    git(base, "commit", "-q", "-m", "init")
    return os.path.realpath(os.path.join(base, ".git"))


class TestLines(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_lines_")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_what_counts(self):
        yes = ["src/app.py", "lib/x.ts", "README.md", "bin/run.sh", "tests/test_a.py", "ui/page.html",
               "Makefile", "db/schema.sql", "config.yml"]
        no = ["img/logo.png", "a.jpg", "b.gif", "icon.ico", "photo.webp", "art.svg", "m/model.glb", "m/scene.gltf",
              "m/x.obj", "m/y.fbx", "f/font.woff2", "f/font.ttf", "s/a.mp3", "v/a.mp4", "d/doc.pdf", "a.zip",
              "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Cargo.lock", "poetry.lock", "Gemfile.lock",
              "go.sum", "composer.lock", "js/app.min.js", "css/site.min.css", "vendor/lib/a.py",
              "node_modules/x/index.js", "dist/bundle.js", "build/out.c", "third_party/z.c", "a/b/vendor/c.go",
              "gen/a.pb.go", "x_pb2.py", "a.generated.ts"]
        for path in yes:
            with self.subTest(path=path):
                self.assertTrue(ac.counts_as_code(path))
        for path in no:
            with self.subTest(path=path):
                self.assertFalse(ac.counts_as_code(path))

    def test_counts_committed_code_lines_only(self):
        ident = make_repo(os.path.join(self.base, "shop"), {
            "src/a.py": "a\nb\nc\n", "src/b.js": "x\n" * 10, "README.md": "# hi\n\ntext\n",
            "logo.png": b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4, "package-lock.json": "{\n}\n" * 50,
            "vendor/v.py": "v\n" * 99, "blob.bin": b"\x00\x01\x02" * 100})
        self.assertEqual(ac.count_lines(ident), 16)
        with open(os.path.join(self.base, "shop", "src", "c.py"), "w") as fh:
            fh.write("not committed\n" * 7)
        self.assertEqual(ac.count_lines(ident), 16, "only what HEAD holds")

    def test_worktree_counts_the_main_repo(self):
        ident = make_repo(os.path.join(self.base, "main"), {"a.py": "1\n2\n"})
        wt = os.path.join(self.base, "wt")
        git(os.path.join(self.base, "main"), "worktree", "add", "-q", "-b", "side", wt)
        with open(os.path.join(wt, "b.py"), "w") as fh:
            fh.write("x\n" * 5)
        git(wt, "add", "b.py")
        git(wt, "commit", "-q", "-m", "side work")
        self.assertEqual(ac.count_lines(ident), 2, "the territory is the main repo's HEAD")

    def test_not_git_or_empty_is_zero(self):
        self.assertEqual(ac.count_lines(os.path.join(self.base, "nothing", ".git")), 0)
        self.assertEqual(ac.count_lines("dir:notes"), 0)
        empty = os.path.join(self.base, "empty")
        os.makedirs(empty)
        git(empty, "init", "-q")
        self.assertEqual(ac.count_lines(os.path.realpath(os.path.join(empty, ".git"))), 0)

    def test_runs_git_only(self):
        ident = make_repo(os.path.join(self.base, "r"), {"a.py": "1\n"})
        calls = []
        real = subprocess.run

        def spy(args, *a, **kw):
            calls.append(list(args))
            return real(args, *a, **kw)

        ac.subprocess.run = spy
        try:
            ac.count_lines(ident)
        finally:
            ac.subprocess.run = real
        self.assertTrue(calls)
        for c in calls:
            self.assertEqual(os.path.basename(c[0]), "git", c)
            self.assertNotIn("test", " ".join(c[1:]).replace(ident, ""), c)


class TestRecount(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_recount_")
        self.path = os.path.join(self.base, "world.json")
        self.calls = []
        self.slow = 0.0

        def count(identity):
            self.calls.append(identity)
            time.sleep(self.slow)
            return {"/a/.git": 12000, "/b/.git": 300}.get(identity, 0)

        self.state = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                                  world_path=self.path, plans=plans(), count_fn=count)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def feed(self, repo, now, ev="PostToolUse", sid="s1"):
        self.state.feed_line({"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "Read", "nt": "",
                              "proj": "p", "role": "worker", "desc": "", "sub": "", "q": "", "klen": "",
                              "repo": repo, "kind": ""}, now)

    def test_feed_never_counts(self):
        self.slow = 2.0
        t0 = time.monotonic()
        for i in range(5):
            self.feed("/a/.git", 1000.0 + i)
        self.assertLess(time.monotonic() - t0, 0.5)
        self.assertEqual(self.calls, [])

    def test_counts_active_repos_at_most_every_300_s(self):
        self.feed("/a/.git", 1000.0)
        self.feed("/b/.git", 1000.0)
        self.assertEqual(self.state.recount(1001.0), 2)
        self.assertEqual(sorted(self.calls), ["/a/.git", "/b/.git"])
        self.assertEqual(self.state.world["territories"]["/a/.git"]["lines"], 12000)
        self.feed("/a/.git", 1010.0)
        self.assertEqual(self.state.recount(1100.0), 0, "counted less than 300 s ago")
        self.assertEqual(self.state.recount(1302.0), 1, "active again and 300 s passed")
        self.assertEqual(self.calls[-1], "/a/.git")
        self.assertEqual(self.state.recount(1700.0), 0, "no activity since the last count")

    def test_a_restart_counts_nothing_until_there_is_activity(self):
        ac.save_world(self.path, world_of(("/a/.git", 500), ("/b/.git", 40)))
        st = ac.CityState(decisions_path=os.path.join(self.base, "d3.jsonl"), world_path=self.path,
                          plans=plans(), count_fn=lambda i: self.calls.append(i) or 7)
        self.assertEqual(st.recount(5000.0), 0, "loaded from world.json, no line yet: nothing to count")
        self.assertEqual(self.calls, [])
        st.feed_line({"ev": "UserPromptSubmit", "sid": "x", "repo": "/b/.git", "proj": "b"}, 5001.0)
        self.assertEqual(st.recount(5002.0), 1)
        self.assertEqual(self.calls, ["/b/.git"])

    def test_a_line_during_a_count_keeps_the_repo_due(self):
        during = []

        def count(identity):
            self.calls.append(identity)
            if not during:
                during.append(1)
                self.feed(identity, 1001.5)
            return 12000

        self.state.count_fn = count
        self.feed("/a/.git", 1000.0)
        self.assertEqual(self.state.recount(1001.0), 1)
        self.assertEqual(self.state.recount(1302.0), 1, "the line that came in while counting was lost")

    def test_deleting_code_never_shrinks_the_territory(self):
        self.feed("/a/.git", 1000.0)
        self.state.recount(1001.0)
        t = self.state.world["territories"]["/a/.git"]
        self.assertEqual((t["lines"], t["peak"]), (12000, 12000))
        self.state.world["territories"]["/a/.git"]["peak"] = 50000
        self.feed("/a/.git", 1400.0)
        self.state.recount(1400.0)
        self.assertEqual((t["lines"], t["peak"]), (12000, 50000))
        view = ac.layout(self.state.world, plans())
        self.assertAlmostEqual(view["territories"][0]["size"], ac.growth(50000))
        self.assertEqual(view["territories"][0]["lines"], 12000)

    def test_memory_only_without_a_path(self):
        st = ac.CityState(decisions_path=os.path.join(self.base, "d2.jsonl"), plans=plans())
        st.feed_line({"ev": "UserPromptSubmit", "sid": "x", "repo": "/m/.git", "proj": "m"}, 5.0)
        self.assertIn("/m/.git", st.world["territories"])
        self.assertEqual(sorted(os.listdir(self.base)), [])


# ---------------------------------------------------------------------------
# Server: the world in the stream, in the file, across restarts
# ---------------------------------------------------------------------------

def gline(ev, sid="s1", aid="", at="", tool="", role="", repo="", kind="", proj="shop"):
    return json.dumps({"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": proj,
                       "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo,
                       "kind": kind}) + "\n"


class WorldServerCase(ServerCase):
    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.base, "cityhome")
        self.world = os.path.join(self.home, "world.json")
        self.repo_a = make_repo(os.path.join(self.base, "big"), {"src/%d.py" % i: "x\n" * 400 for i in range(25)})
        self.repo_b = make_repo(os.path.join(self.base, "small"), {"a.py": "x\n" * 30})

    def start(self, *extra, wait=True):
        return super().start(*(list(extra) or ["--idle-sec", "60", "--world", self.world]), wait=wait)

    def world_file(self):
        with open(self.world) as fh:
            return json.load(fh)

    def snap(self):
        client = self.sse()
        return client, client.messages[0]


class TestServerWorld(WorldServerCase):
    def test_snapshot_carries_the_world(self):
        self.start()
        client, snap = self.snap()
        self.assertEqual(snap["type"], "snapshot")
        self.assertIn("world", snap)
        self.assertEqual(snap["world"]["territories"], [])
        self.assertNotIn("notice", snap)

    def test_a_new_repo_makes_its_territory(self):
        self.start()
        client, _ = self.snap()
        self.append(gline("UserPromptSubmit", sid="g1", repo=self.repo_a))
        ev = wait_for(lambda: client.events("world"))
        self.assertTrue(ev)
        terr = ev[-1]["world"]["territories"]
        self.assertEqual([t["name"] for t in terr], ["big"])
        self.assertEqual(terr[0]["id"], ac.territory_id(self.repo_a))
        self.assertTrue(wait_for(lambda: os.path.exists(self.world)))
        self.assertIn(self.repo_a, self.world_file()["territories"])

    def test_code_lines_size_the_territory(self):
        self.start()
        client, _ = self.snap()
        self.append(gline("UserPromptSubmit", sid="g1", repo=self.repo_a))
        self.append(gline("UserPromptSubmit", sid="c1", role="worker", repo=self.repo_b))
        got = wait_for(lambda: [e for e in client.events("world")
                                if {t["lines"] for t in e["world"]["territories"]} == {10000, 30}], timeout=20)
        self.assertTrue(got, "lines were never counted")
        terr = {t["name"]: t for t in got[-1]["world"]["territories"]}
        self.assertGreater(terr["big"]["size"], terr["small"]["size"])
        self.assertEqual(len(got[-1]["world"]["links"]), 1)

    def test_spawn_and_snapshot_agents_carry_their_territory(self):
        self.start()
        client, _ = self.snap()
        self.append(gline("UserPromptSubmit", sid="g1", repo=self.repo_a))
        self.append(gline("SubagentStart", sid="g1", aid="a1", at="worker", repo=self.repo_b))
        spawn = wait_for(lambda: client.events("spawn"))
        self.assertEqual(spawn[0]["terr"], ac.territory_id(self.repo_b))
        gov = wait_for(lambda: client.events("gov"))
        self.assertEqual(gov[0]["terr"], ac.territory_id(self.repo_a))
        _, snap = self.snap()
        self.assertEqual(snap["agents"][0]["terr"], ac.territory_id(self.repo_b))
        self.assertEqual(snap["gov"]["terr"], ac.territory_id(self.repo_a))

    def test_a_line_without_repo_makes_no_territory(self):
        """Owner 2026-09-25: old data is dropped; no "dir:" + proj fallback any more."""
        self.start()
        client, _ = self.snap()
        self.append(gline("UserPromptSubmit", sid="g1", repo="", proj="notes"))
        self.assertTrue(wait_for(lambda: client.events("gov")), "the line was read")
        time.sleep(0.5)
        self.assertEqual(client.events("world"), [])
        _, snap = self.snap()
        self.assertEqual(snap["world"]["territories"], [])

    def test_an_edit_builds_in_its_district_and_stays(self):
        seed = world_of((self.repo_a, 1000000))
        ac.save_world(self.world, seed)
        self.start()
        client, _ = self.snap()
        self.append(gline("SubagentStart", sid="g1", aid="a1", at="worker", repo=self.repo_a))
        self.append(gline("PostToolUse", sid="g1", aid="a1", at="worker", tool="Edit", repo=self.repo_a, kind="ui"))
        b = wait_for(lambda: client.events("build"))
        self.assertTrue(b, "no build event")
        b = b[0]
        self.assertEqual((b["id"], b["terr"], b["btype"], b["by"]), ("a1", ac.territory_id(self.repo_a), "shop", "worker"))
        plan = next(p for p in plans() if p["id"] == seed["territories"][self.repo_a]["plan"])
        self.assertEqual(plan["plots"][b["plot"]][2], "shop")
        self.assertEqual((b["x"], b["z"]), (plan["plots"][b["plot"]][0], plan["plots"][b["plot"]][1]))
        self.append(gline("PostToolUse", sid="g1", aid="a1", at="worker", tool="Write", repo=self.repo_a, kind="test"))
        self.append(gline("SubagentStop", sid="g1", aid="a1", at="worker", repo=self.repo_a))
        self.append(gline("SessionEnd", sid="g1", repo=self.repo_a))
        self.assertTrue(wait_for(lambda: client.events("leave")))
        time.sleep(0.5)
        self.assertEqual(len(client.events("build")), 1, "one building per agent")
        saved = self.world_file()["territories"][self.repo_a]["buildings"]
        self.assertEqual([(x["plot"], x["type"], x["owner"]) for x in saved], [(b["plot"], "shop", "a1")])
        _, snap = self.snap()
        built = snap["world"]["territories"][0]["buildings"]
        self.assertEqual([(x["plot"], x["type"]) for x in built], [(b["plot"], "shop")], "the agent left, its building stays")

    def test_governor_edits_build_too(self):
        ac.save_world(self.world, world_of((self.repo_a, 1000000)))
        self.start()
        client, _ = self.snap()
        self.append(gline("UserPromptSubmit", sid="g1", repo=self.repo_a))
        self.append(gline("PostToolUse", sid="g1", tool="Edit", repo=self.repo_a, kind="doc"))
        b = wait_for(lambda: client.events("build"))
        self.assertTrue(b)
        self.assertEqual((b[0]["id"], b[0]["btype"]), ("gov", "library"))

    def test_restart_is_the_same_city(self):
        self.start()
        client, _ = self.snap()
        self.append(gline("UserPromptSubmit", sid="g1", repo=self.repo_a))
        self.append(gline("UserPromptSubmit", sid="c1", role="worker", repo=self.repo_b))
        self.assertTrue(wait_for(lambda: [e for e in client.events("world")
                                          if {t["lines"] for t in e["world"]["territories"]} == {10000, 30}], timeout=20))
        _, before = self.snap()
        plans_before = {k: v["plan"] for k, v in self.world_file()["territories"].items()}
        for p in self.procs:
            p.terminate()
            p.wait(5)
        for c in self.clients:
            c.close()
        self.clients = []
        self.start()
        _, after = self.snap()
        self.assertEqual(after["world"]["rows"], before["world"]["rows"])
        self.assertEqual([(t["id"], t["plan"], t["slot"]) for t in after["world"]["territories"]],
                         [(t["id"], t["plan"], t["slot"]) for t in before["world"]["territories"]])
        self.assertEqual({k: v["plan"] for k, v in self.world_file()["territories"].items()}, plans_before,
                         "a restart never re-picks a plan")

    def test_broken_world_file_is_moved_aside_and_said(self):
        os.makedirs(self.home)
        with open(self.world, "w") as fh:
            fh.write("{broken")
        self.start()
        _, snap = self.snap()
        aside = [f for f in os.listdir(self.home) if f.startswith("world.json.bad-")]
        self.assertEqual(len(aside), 1)
        self.assertIn(aside[0], snap.get("notice", ""))
        self.assertEqual(snap["world"]["territories"], [])

    def test_default_world_path_is_under_agent_city_home(self):
        proc = subprocess.Popen([sys.executable, os.path.join(BIN, "agent_city.py"), "serve", "--dir", self.dir,
                                 "--port", "0", "--idle-sec", "60"],
                                env=dict(os.environ, AGENT_CITY_HOME=self.home, HOME=self.base),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(proc)
        self.assertTrue(wait_for(lambda: (self.on() or (0,))[0] == proc.pid))
        self.append(gline("UserPromptSubmit", sid="g1", repo=self.repo_a))
        self.assertTrue(wait_for(lambda: os.path.exists(self.world)), "world.json not under AGENT_CITY_HOME")


class TestDemoWorld(unittest.TestCase):
    def test_demo_world_command(self):
        home = tempfile.mkdtemp(prefix="city_demo_")
        try:
            out = subprocess.run([sys.executable, os.path.join(BIN, "agent_city.py"), "demo-world"],
                                 capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
                                 env=dict(os.environ, AGENT_CITY_HOME=home, HOME=home))
            self.assertEqual(os.listdir(home), [], "demo-world reads and writes no file")
        finally:
            shutil.rmtree(home, ignore_errors=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        view = json.loads(out.stdout)
        self.assertGreaterEqual(len(view["territories"]), 3)
        self.assertTrue(any(l["kind"] == "bridge" for l in view["links"]))
        self.assertTrue(any(t["buildings"] for t in view["territories"]))
        sizes = sorted(t["size"] for t in view["territories"])
        self.assertLess(sizes[0], 0.3)
        self.assertGreater(sizes[-1], 0.7)


class TestCityScriptWorld(unittest.TestCase):
    def test_start_passes_the_world_file(self):
        with open(os.path.join(BIN, "agent-city.sh")) as fh:
            text = fh.read()
        self.assertTrue(re.search(r'--world "\$CITY_HOME/world\.json"', text),
                        'agent-city.sh start must pass --world "$CITY_HOME/world.json"')


if __name__ == "__main__":
    unittest.main()
