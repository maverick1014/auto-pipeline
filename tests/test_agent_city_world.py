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

  Constants  CELL 22, HALF 11 (city-ux U7, owner 2026-09-28: was 26/13), R0 1.9, RMAX 8.6, L0 50, LCAP 1000000,
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
          {"cell": 22, "x0", "z0", "w", "h", "rows": [h strings of w chars],
           "territories": [{"id", "name", "plan", "terrain", "slot", "cx",
              "cz", "lines", "size", "r", "open", "plots_total",
              "plots": [{"k", "x", "z", "d"}] (open plots, world tiles),
              "buildings": [{"plot", "type", "by", "x", "z"}]}],
           "links": [{"a", "b", "gap", "kind", "cross": [[x, z], ...]}]}
          World tile (X, Z) = rows[Z - z0][X - x0]. A territory in slot
          (i, j) has its hall centre at (22 i, 22 j). Map chars:
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


def world_of(*repos):
    """repos: (identity, lines) in arrival order (city-office: lines are no longer kept)."""
    w = ac.new_world()
    for ident, _lines in repos:
        ac.add_territory(w, ident, ac.repo_name(ident))
    w["floors"] = [ident for ident, _ in repos]
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

# ---------------------------------------------------------------------------
# Size from code lines
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Shape: organic, uneven, the same every time for the same repo
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Territories on one land: slots, plans, neighbours, gaps, sea
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Buildings: type from the kind of work, in its district, permanent
# ---------------------------------------------------------------------------

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
        w["territories"]["/a/.git"]["reno_asked"] = True
        ac.save_world(self.path, w)
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ["world.json"], "temp file left behind")
        loaded, notice = ac.load_world(self.path)
        self.assertIsNone(notice)
        self.assertEqual(loaded, json.loads(json.dumps(w)))
        with open(self.path) as fh:
            self.assertEqual(json.load(fh)["v"], 1)

    def test_save_is_atomic(self):
        src = function_src(ac.save_world)
        self.assertIn("os.replace", src)
        self.assertRegex(src, r"tmp|temp|mkstemp")

    def test_missing_file_is_a_fresh_world(self):
        w, notice = ac.load_world(self.path)
        self.assertEqual(w, ac.new_world())
        self.assertIsNone(notice)
        self.assertFalse(os.path.exists(os.path.dirname(self.path)) and os.listdir(os.path.dirname(self.path)))

    def test_broken_or_unknown_file_is_moved_aside(self):
        good = world_of(("/a/.git", 10))
        cases = {"not json": b"{not json", "a list": b"[1, 2]", "future version": json.dumps(dict(good, v=2)).encode(),
                 "no version": json.dumps({"territories": {}, "order": []}).encode(),
                 "binary": b"\xff\xfe\x00junk"}
        for name, data in cases.items():
            with self.subTest(case=name):
                folder = os.path.dirname(self.path)
                shutil.rmtree(folder, ignore_errors=True)
                os.makedirs(folder)
                with open(self.path, "wb") as fh:
                    fh.write(data)
                w, notice = ac.load_world(self.path)
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


# ---------------------------------------------------------------------------
# Server: the world in the stream, in the file, across restarts
# ---------------------------------------------------------------------------

def gline(ev, sid="s1", aid="", at="", tool="", role="", repo="", kind="", proj="shop"):
    return json.dumps({"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": proj,
                       "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo,
                       "kind": kind}) + "\n"


class TestCityScriptWorld(unittest.TestCase):
    def test_start_passes_the_world_file(self):
        with open(os.path.join(BIN, "agent-city.sh")) as fh:
            text = fh.read()
        self.assertTrue(re.search(r'--world "\$CITY_HOME/world\.json"', text),
                        'agent-city.sh start must pass --world "$CITY_HOME/world.json"')


if __name__ == "__main__":
    unittest.main()
