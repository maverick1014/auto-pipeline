"""Failing tests for city-land: never an empty city, a usable empty world, and
smooth land (requirements/city.md, Growth and Quality; approved mock
mock/city-land-mock.html).

CONTRACT

  Server (bin/agent_city.py)
    CityState(..., start_repo=IDENTITY): IDENTITY is the start territory:
      the git common dir of the dir the server was started from (the same
      physical path the hook writes as "repo"), or that dir itself when it is
      no git repo (a plain folder counts too). At construction, before any
      line: add_territory for it if it is not in the world yet (a known one is
      never moved or replanned), save world.json at once, and mark it due, so
      the first recount(now) counts it. The first snapshot's world carries it;
      with no governor yet, snapshot "gov" has terr = its territory id.
      start_repo None or "" -> nothing added.
    Old data is dropped: on load every territory saved under a "dir:..."
      identity (no repo) is removed from the world and from world.json (saved
      at once), with one notice line for the page log (the snapshot's
      "notice") and one line on stderr.
    feed_line: a line with no "repo" (missing or "") never creates a
      territory and sends no world event; its people (spawn, snapshot agents,
      gov) go to the start territory (terr = its id; "" when there is none).
    Minimum size: a territory with 0 lines still has its hall and at least
      12 tiles of its own land (g H) in the layout.
    serve --start-dir DIR: CityState(start_repo=_repo_id(DIR)) (git common
      dir, else the folder's real path). No --start-dir or "" -> no start
      territory (then the page's empty-world safety net applies).
    bin/agent-city.sh start passes --start-dir with the physical path of the
      dir it was started from (pwd -P). A worktree gives its main repo's .git.

  Page (bin/agent-city.html). The land section (from the line starting
  "/* ---------- the land" to the next "/* ---------- " line) holds every
  function below and every helper they need, besides these page helpers from
  outside it: h2r, rgbOf, terrAtOf, cellTerrain, roadColor, trackColor,
  eraShown, showOf, eraLook, clamp. The test runs that section in node with
  the top-level constants, TERRAIN_LOOK, ERA_LOOK, a stub THREE.Group and a
  stub world group. Coordinates are world tiles; tile (X, Z) spans
  [X, X+1] x [Z, Z+1], its centre is (X+.5, Z+.5). Land tiles = every map
  char but ' ' (void), 'w' 's' 'B' (water) and 'k' (ravine).
    groundGeometry(view) -> {positions, colors, indices}: one mesh. The tile
      grid stays hidden logic; the look is smooth:
      - top at y 0: every flat face faces up; one vertex position = one colour
        (no seams); colour changes gradually: along any top edge at most .12
        per channel, and at most .45 per channel per tile of distance (no
        per-tile colour steps, no hard district edges).
      - smooth outline: where the top ends, the outline never turns 90 degrees
        between two axis-aligned pieces (no stair steps), less than 3% of its
        corners turn 60 degrees or more, and at most 35% of its length is
        axis-aligned.
      - follows the tiles: the centre of every g H P r t b tile is on the top;
        so is every other land tile's centre when 3 or 4 of its 4 neighbours
        are land. A void tile whose 4 neighbours are all void, and a water
        tile with 2+ water neighbours, are not under the top. 'k' centres are
        never on the top at y 0.
      - edges: side faces (not flat) face outward (toward lower land). Beside
        void or ravine a grey rock cliff down to y <= -0.8; beside water a bank
        down below the water (y <= -0.1). Every land/void, land/ravine and
        land/water tile border (land tile with 2+ land neighbours) has such a
        face within 0.9 tiles of the border's middle.
      - ravine floor: every 'k' centre is on a flat face at y <= -0.8.
      - cheap: at most 60 triangles per map tile (w * h); groundGeometry +
        waterGeometry + laneGeometry of the demo world under 700 ms in node
        (buildLand runs on every world event).
    waterGeometry(view) -> the same shape: flat, facing up, y in [-0.2, 0),
      blue; every 'w' 's' 'B' centre on it; its outline smooth (the same three
      outline rules as the ground).
    lanePaths(view) -> [{pts: [[x, z], ...]}]: smooth centre lines of the
      road ('r') and track ('t') tiles, through bridges ('B'):
      - every 'r' and 't' centre within 0.3 of a lane line;
      - every lane point within 0.75 of an 'r' 't' 'B' centre, and at least
        0.55 from every plot 'P' and hall 'H' centre;
      - smooth: inside one lane, consecutive pieces turn at most 35 degrees.
    laneGeometry(view) -> {positions, colors, indices}: ribbons along
      lanePaths, flat at 0 < y <= 0.1, facing up, round where lanes meet or
      end. Covers every lane point that is not over water; nothing over 'w' or
      's' (the bridge deck is the lane there). Narrower than a tile, wider
      than 0.4: across a straight road, the centre +- 0.2 is covered, +- 0.5
      is not. Colour: roadColor(t) on a territory's 'r' tiles (a town road
      differs from a village road), trackColor(t) on 't' tiles.
    wildDecor(view) -> [{key, x, z, ...}]: what buildLand places on the wild
      land: plants on '.', pines on 'f', rocks on 'm', one bridge on every
      'B'. Each item stays inside its own tile; plants, pines and rocks are
      jittered off the tile centre (at least 80% more than 0.08 away), so no
      rows; bridges sit exactly on the centre. buildLand places these.
    People: newCitizen puts an agent whose territory is unknown ("" or not
      in the map) on the governor's territory, else the first one.
    Empty world (a safety net only: the start dir always has a territory):
      - landReady() -> true only when map.territories is non-empty.
      - distMax() with land {hx: 0, hz: 0} equals distMax() with {hx: 13,
        hz: 13} (one fresh territory): zoom in and out keep moving.
      - updateGovernor() hides the governor (govV.g.visible false) without
        land, shows it with land. updatePerson uses landReady() too.
      - markup: <p id="empty-land" hidden> containing 还没有领地.
        showEmptyLine(view) sets its hidden = view has territories;
        buildLand calls it.
      - the first-view flag in buildLand flips only on a world with a
        territory, so the first territory that arrives later still gets the
        camera home.
    First view: case 'snapshot' sets govTerr from ev.gov.terr BEFORE
      buildLand(ev.world), so the first view is the governor's own hall.

  No test here touches the real ~/.claude/agent-city.
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
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
import test_agent_city_page as tp  # noqa: E402
from test_agent_city_server import ServerCase, wait_for  # noqa: E402
from test_agent_city_world import make_repo, gline  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402


def plans():
    return ac.load_plans()


# ---------------------------------------------------------------------------
# Server: the start repo's territory, and no territory without a repo
# ---------------------------------------------------------------------------

class TestStartTerritory(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_land_")
        self.path = os.path.join(self.base, "world.json")
        self.calls = []

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def state(self, start_repo, world=None):
        if world is not None:
            ac.save_world(self.path, world)

        def count(identity):
            self.calls.append(identity)
            return 4000
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.path,
                            plans=plans(), count_fn=count, start_repo=start_repo)

    def snapshot(self, st):
        client = st.add_client()
        raw = client.queue.get_nowait()
        text = raw.decode() if isinstance(raw, bytes) else raw
        return json.loads(text.split("data:", 1)[1].strip())

    def saved(self):
        with open(self.path) as fh:
            return json.load(fh)["territories"]

    def test_the_start_repo_is_there_at_once(self):
        st = self.state("/r/shop/.git")
        self.assertIn("/r/shop/.git", st.world["territories"])
        self.assertEqual(st.world["territories"]["/r/shop/.git"]["name"], "shop")
        self.assertIn("/r/shop/.git", self.saved(), "saved at once, before any line")
        snap = self.snapshot(st)
        self.assertEqual([t["name"] for t in snap["world"]["territories"]], ["shop"])
        self.assertEqual(snap["gov"]["terr"], ac.territory_id("/r/shop/.git"),
                         "no governor yet: the governor belongs to the start territory")

    def test_a_plain_folder_is_a_start_territory_too(self):
        st = self.state("/r/notes")
        self.assertEqual([t["name"] for t in self.snapshot(st)["world"]["territories"]], ["notes"])

    def test_the_start_repo_is_counted_first(self):
        st = self.state("/r/shop/.git")
        self.assertEqual(st.recount(1000.0), 1)
        self.assertEqual(self.calls, ["/r/shop/.git"])
        self.assertEqual(st.world["territories"]["/r/shop/.git"]["lines"], 4000)

    def test_saved_territories_stay_and_keep_their_place(self):
        w = ac.new_world()
        ac.add_territory(w, plans(), "/r/old/.git", "old", 900)
        ac.add_territory(w, plans(), "/r/shop/.git", "shop", 50)
        before = json.loads(json.dumps(w["territories"]["/r/shop/.git"]))
        st = self.state("/r/shop/.git", world=w)
        self.assertEqual(sorted(st.world["territories"]), ["/r/old/.git", "/r/shop/.git"])
        after = st.world["territories"]["/r/shop/.git"]
        self.assertEqual((after["slot"], after["plan"]), (before["slot"], before["plan"]))
        self.assertEqual(len(self.snapshot(st)["world"]["territories"]), 2)

    def test_no_start_repo_adds_nothing(self):
        for start in (None, ""):
            with self.subTest(start=start):
                st = self.state(start)
                self.assertEqual(st.world["territories"], {})
                self.assertEqual(st.recount(1000.0), 0)

    def test_old_territories_without_a_repo_are_dropped_on_load(self):
        w = ac.new_world()
        ac.add_territory(w, plans(), "dir:notes", "notes", 0)
        ac.add_territory(w, plans(), "/r/shop/.git", "shop", 50)
        st = self.state(None, world=w)
        self.assertEqual(list(st.world["territories"]), ["/r/shop/.git"])
        self.assertEqual(st.world["order"], ["/r/shop/.git"])
        self.assertEqual(list(self.saved()), ["/r/shop/.git"], "dropped from world.json at once")
        snap = self.snapshot(st)
        self.assertTrue(snap.get("notice"), "one line in the page log, never silent")
        self.assertEqual([t["name"] for t in snap["world"]["territories"]], ["shop"])

    def test_a_line_without_repo_goes_to_the_start_territory(self):
        st = self.state("/r/shop/.git")
        client = st.add_client()
        start_id = ac.territory_id("/r/shop/.git")
        for missing in (False, True):
            obj = json.loads(gline("UserPromptSubmit", sid="g1", repo="", proj="notes"))
            if missing:
                obj.pop("repo")
            st.feed_line(obj, 1000.0)
        st.feed_line(json.loads(gline("SubagentStart", sid="g1", aid="a1", at="worker", repo="", proj="notes")), 1001.0)
        self.assertEqual(list(st.world["territories"]), ["/r/shop/.git"], "old sessions (no repo) never create a territory")
        events = []
        while not client.queue.empty():
            raw = client.queue.get_nowait()
            if isinstance(raw, bytes) and raw.startswith(b"data:"):
                events.append(json.loads(raw.decode().split("data:", 1)[1].strip()))
        self.assertFalse([e for e in events if e.get("type") == "world"], "no world event for a line without repo")
        spawn = [e for e in events if e.get("type") == "spawn"]
        self.assertEqual([e["terr"] for e in spawn], [start_id], "its people stand on the start territory")
        snap = self.snapshot(st)
        self.assertEqual([(a["id"], a["terr"]) for a in snap["agents"]], [("a1", start_id)])
        self.assertEqual(snap["gov"]["terr"], start_id)

    def test_a_line_without_repo_and_no_start_territory(self):
        st = self.state(None)
        st.feed_line(json.loads(gline("SubagentStart", sid="g1", aid="a1", at="worker", repo="", proj="notes")), 1001.0)
        self.assertEqual(st.world["territories"], {})
        self.assertEqual([(a["id"], a["terr"]) for a in self.snapshot(st)["agents"]], [("a1", "")])

    def test_zero_lines_still_has_land_and_a_hall(self):
        for plan in plans():
            with self.subTest(plan=plan["id"]):
                w = ac.new_world()
                t = ac.add_territory(w, plans(), "/r/empty/.git", "empty", 0)
                t["plan"] = plan["id"]
                view = ac.layout(w, plans())
                own = sum(row.count("g") + row.count("H") for row in view["rows"])
                self.assertEqual(sum(row.count("H") for row in view["rows"]), 4, "the town hall")
                self.assertGreaterEqual(own, 12, "a small land of its own, even with 0 code lines")


class TestServeStartDir(ServerCase):
    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.base, "cityhome")
        self.world = os.path.join(self.home, "world.json")

    def serve(self, start):
        self.start("--idle-sec", "60", "--world", self.world, "--start-dir", start)
        return self.sse().messages[0]

    def test_a_repo_dir_shows_its_territory_before_any_event(self):
        repo = make_repo(os.path.join(self.base, "shop"), {"a.py": "x\n" * 30})
        snap = self.serve(os.path.join(self.base, "shop"))
        self.assertEqual([t["name"] for t in snap["world"]["territories"]], ["shop"])
        self.assertEqual(snap["gov"]["terr"], ac.territory_id(repo))
        with open(self.world) as fh:
            self.assertEqual(list(json.load(fh)["territories"]), [repo])

    def test_a_plain_folder_shows_its_territory(self):
        plain = os.path.join(self.base, "notes")
        os.makedirs(plain)
        snap = self.serve(plain)
        self.assertEqual([t["name"] for t in snap["world"]["territories"]], ["notes"])
        with open(self.world) as fh:
            self.assertEqual(list(json.load(fh)["territories"]), [os.path.realpath(plain)])

    def test_no_start_dir_shows_nothing(self):
        snap = self.serve("")
        self.assertEqual(snap["world"]["territories"], [])


class TestCityScriptStartDir(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.city = os.path.join(self.repo.base, "city")
        self.home = os.path.join(self.repo.base, "cityhome")
        self.repo.set_conf("city_port", str(tp_free_port()))

    def tearDown(self):
        on = os.path.join(self.city, "on")
        if os.path.exists(on):
            try:
                with open(on) as fh:
                    os.kill(int(fh.read().split()[0]), 15)
            except (OSError, ValueError, IndexError):
                pass
        super().tearDown()

    def city_run(self, *args, cwd=None):
        env = {"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.home}
        kw = {"env": env, "timeout": 30}
        if cwd:
            kw["cwd"] = cwd
        return self.repo.run("agent-city.sh", *args, **kw)

    def territories(self):
        path = os.path.join(self.home, "world.json")
        if not wait_for(lambda: os.path.exists(path), timeout=5):
            return {}
        with open(path) as fh:
            return json.load(fh)["territories"]

    def test_start_from_a_repo(self):
        self.assertTrue(re.search(r"--start-dir\b", open(os.path.join(BIN, "agent-city.sh")).read()),
                        "agent-city.sh start must pass --start-dir")
        result = self.city_run("start")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.territories()), [os.path.realpath(os.path.join(self.repo.dir, ".git"))])

    def test_start_from_a_worktree_gives_the_main_repo(self):
        self.repo.detach_scripts_to_worktree()
        result = self.city_run("start")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.territories()), [os.path.realpath(os.path.join(self.repo.dir, ".git"))])

    def test_start_from_a_plain_folder(self):
        plain = os.path.join(self.repo.base, "plain")
        os.makedirs(plain)
        with open(os.path.join(plain, "agent.conf"), "w") as fh:  # its own port: never the real city's 4777
            fh.write("city_port=%d\n" % tp_free_port())
        result = self.city_run("start", cwd=plain)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.territories()), [os.path.realpath(plain)])


def tp_free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ---------------------------------------------------------------------------
# Page: the land section in node
# ---------------------------------------------------------------------------

OUTSIDE_HELPERS = ("h2r", "rgbOf", "terrAtOf", "cellTerrain", "roadColor", "trackColor",
                   "eraShown", "showOf", "eraLook", "clamp")


def land_section():
    text = tp.inline_script()
    i = text.find("/* ---------- the land")
    if i < 0:
        return None
    j = text.find("/* ---------- ", i + 10)
    return text[i:j if j > 0 else len(text)]


def land_prelude(section):
    declared = set(re.findall(r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)", section, re.M))
    declared |= set(re.findall(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", section, re.M))
    lines = [ln for ln in tp.constants_prelude().split("\n")
             if ln and ln.split()[1] not in declared]
    for name in ("TERRAIN_LOOK", "ERA_LOOK"):
        if name not in declared:
            lit = tp.const_object(name)
            if lit:
                lines.append("var %s = %s;" % (name, lit))
    for name in OUTSIDE_HELPERS:
        if name in declared:
            continue
        src = tp.function_source(name)
        if src:
            lines.append(src)
        elif name == "clamp":
            m = re.search(r"^const clamp = [^\n]+", tp.inline_script(), re.M)
            if m:
                lines.append(m.group(0).replace("const clamp", "var clamp", 1))
    return "\n".join(lines)


def views():
    """demo: river + bridge, coast + sea + beach, mountain pass, a city-era road net.
    gaps: grassland (village) | desert (town) with a ravine and a bridge; forest (village) below with a forest belt."""
    pl = plans()
    w = ac.new_world()
    spec = [("/t/meadow/.git", "meadow", (0, 0), "village"), ("/t/oasis/.git", "oasis", (1, 0), "town"),
            ("/t/woods/.git", "woods", (0, 1), "village")]
    for ident, plan, slot, era in spec:
        t = ac.add_territory(w, pl, ident, ident.split("/")[2], 30000)
        t["plan"], t["slot"], t["era"] = plan, list(slot), era
        t["peak"] = t["lines"] = 30000
    return {"demo": ac.demo_world(), "gaps": ac.layout(w, pl)}


LAND_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, section, views } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, Map, Set, Float32Array, Float64Array, Uint8Array, Int32Array, Array, Object, Number,
  performance: { now: () => 0 }, shows: new Map(), world: { add(){}, remove(){} },
  THREE: { Group: function(){ this.children = []; this.add = function(){}; this.remove = function(){}; } } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + section, box);
const LAND = ch => !' wsBk'.includes(ch), WATER = ch => 'wsB'.includes(ch);
const out = {};
const key = (x, z) => Math.round(x * 1e4) + ',' + Math.round(z * 1e4);
function tris(g){
  const P = Array.from(g.positions || []), C = Array.from(g.colors || []);
  const I = g.indices && g.indices.length ? Array.from(g.indices) : P.map((_, i) => i).slice(0, P.length / 3);
  const T = [];
  for (let t = 0; t + 2 < I.length; t += 3) {
    const v = [I[t], I[t + 1], I[t + 2]].map(i => ({ x: P[3 * i], y: P[3 * i + 1], z: P[3 * i + 2], c: [C[3 * i], C[3 * i + 1], C[3 * i + 2]] }));
    const ax = v[1].x - v[0].x, ay = v[1].y - v[0].y, az = v[1].z - v[0].z, bx = v[2].x - v[0].x, by = v[2].y - v[0].y, bz = v[2].z - v[0].z;
    const n = [ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx];
    if (Math.hypot(n[0], n[1], n[2]) < 1e-9) continue; // a zero-area triangle draws nothing
    const flat = v.every(p => Math.abs(p.y - v[0].y) < 1e-6);
    T.push({ v, n, flat, y: v[0].y });
  }
  return T;
}
function inTri(px, pz, t){
  const [a, b, c] = t.v;
  const d = (b.z - c.z) * (a.x - c.x) + (c.x - b.x) * (a.z - c.z);
  if (Math.abs(d) < 1e-12) return false;
  const l1 = ((b.z - c.z) * (px - c.x) + (c.x - b.x) * (pz - c.z)) / d, l2 = ((c.z - a.z) * (px - c.x) + (a.x - c.x) * (pz - c.z)) / d, l3 = 1 - l1 - l2;
  return l1 >= -1e-6 && l2 >= -1e-6 && l3 >= -1e-6;
}
function index(T){
  const grid = new Map();
  for (const t of T) {
    const xs = t.v.map(p => p.x), zs = t.v.map(p => p.z);
    for (let X = Math.floor(Math.min(...xs)); X <= Math.floor(Math.max(...xs)); X++)
      for (let Z = Math.floor(Math.min(...zs)); Z <= Math.floor(Math.max(...zs)); Z++) {
        const k = X + ',' + Z; if (!grid.has(k)) grid.set(k, []); grid.get(k).push(t);
      }
  }
  return (x, z) => (grid.get(Math.floor(x) + ',' + Math.floor(z)) || []).some(t => inTri(x, z, t));
}
function outline(T){
  const count = new Map(), seg = new Map();
  for (const t of T) for (let i = 0; i < 3; i++) {
    const a = t.v[i], b = t.v[(i + 1) % 3], ka = key(a.x, a.z), kb = key(b.x, b.z);
    if (ka === kb) continue;
    const k = ka < kb ? ka + '|' + kb : kb + '|' + ka;
    count.set(k, (count.get(k) || 0) + 1); seg.set(k, [a, b, ka, kb]);
  }
  const adj = new Map(); let len = 0, axis = 0;
  for (const [k, n] of count) {
    if (n !== 1) continue;
    const [a, b, ka, kb] = seg.get(k), dx = b.x - a.x, dz = b.z - a.z, l = Math.hypot(dx, dz);
    len += l; if (Math.abs(dx) < 1e-6 || Math.abs(dz) < 1e-6) axis += l;
    for (const [p, q, kp] of [[a, b, ka], [b, a, kb]]) { if (!adj.has(kp)) adj.set(kp, []); adj.get(kp).push([q.x - p.x, q.z - p.z, p]); }
  }
  let corners = 0, sharp = 0, stair = 0; const stairAt = [];
  for (const [k, es] of adj) {
    if (es.length !== 2) continue;
    corners++;
    const [[ax, az], [bx, bz]] = es, la = Math.hypot(ax, az), lb = Math.hypot(bx, bz);
    const turn = Math.PI - Math.acos(Math.max(-1, Math.min(1, (ax * bx + az * bz) / (la * lb))));
    if (turn >= Math.PI / 3) sharp++;
    const axA = Math.abs(ax) < 1e-6 || Math.abs(az) < 1e-6, axB = Math.abs(bx) < 1e-6 || Math.abs(bz) < 1e-6;
    if (axA && axB && Math.abs(ax * bx + az * bz) < 1e-6 && la >= .1 && lb >= .1) { stair++; if (stairAt.length < 5) stairAt.push([es[0][2].x, es[0][2].z]); }
  }
  return { len, axisShare: len ? axis / len : 0, corners, sharpShare: corners ? sharp / corners : 0, stair, stairAt };
}
for (const [name, view] of Object.entries(views)) {
  const at = (X, Z) => { const r = Z - view.z0, c = X - view.x0; return r >= 0 && r < view.h && c >= 0 && c < view.w ? view.rows[r][c] : ' '; };
  const n4 = (X, Z, f) => [[1, 0], [-1, 0], [0, 1], [0, -1]].filter(([dx, dz]) => f(at(X + dx, Z + dz))).length;
  const tiles = [];
  for (let r = 0; r < view.h; r++) for (let c = 0; c < view.w; c++) tiles.push([view.x0 + c, view.z0 + r, view.rows[r][c]]);
  const res = {};
  // ---- ground
  let t0 = Date.now();
  const g = box.groundGeometry(view);
  box.waterGeometry(view); box.laneGeometry(view);
  res.ms = Date.now() - t0;
  const T = tris(g);
  res.tris = T.length; res.area = view.w * view.h;
  const top = T.filter(t => t.flat && Math.abs(t.y) < 1e-6), low = T.filter(t => t.flat && t.y <= -0.8), side = T.filter(t => !t.flat);
  res.down = T.filter(t => t.flat && !(t.n[1] > 0)).length;
  const col = new Map(); let seams = 0, stepMax = 0, gradMax = 0; const gradAt = [];
  for (const t of top) {
    for (const p of t.v) { const k = key(p.x, p.z), c = col.get(k); if (!c) col.set(k, p.c); else if (c.some((q, i) => Math.abs(q - p.c[i]) > 2e-3)) seams++; }
    for (let i = 0; i < 3; i++) {
      const a = t.v[i], b = t.v[(i + 1) % 3], d = Math.max(...a.c.map((q, j) => Math.abs(q - b.c[j]))), l = Math.hypot(a.x - b.x, a.z - b.z);
      stepMax = Math.max(stepMax, d);
      if (l >= .05) { const gr = d / l; if (gr > gradMax) { gradMax = gr; gradAt.splice(0, 1, [a.x, a.z]); } }
    }
  }
  res.seams = seams; res.stepMax = stepMax; res.gradMax = gradMax; res.gradAt = gradAt;
  res.outline = outline(top);
  const onTop = index(top), onLow = index(low);
  const miss = [], over = [], kTop = [], kLow = [];
  for (const [X, Z, ch] of tiles) {
    const x = X + .5, z = Z + .5;
    if ('gHPrtb'.includes(ch) || (LAND(ch) && n4(X, Z, LAND) >= 3)) { if (!onTop(x, z)) miss.push([X, Z, ch]); }
    else if ((ch === ' ' && n4(X, Z, c => !LAND(c) && c !== 'k' && !WATER(c)) === 4) || (WATER(ch) && n4(X, Z, WATER) >= 2)) { if (onTop(x, z)) over.push([X, Z, ch]); }
    if (ch === 'k') { if (onTop(x, z)) kTop.push([X, Z]); if (!onLow(x, z)) kLow.push([X, Z]); }
  }
  res.miss = miss.slice(0, 8); res.missN = miss.length; res.over = over.slice(0, 8); res.overN = over.length;
  res.kTop = kTop.length; res.kLow = kLow.slice(0, 5); res.kN = tiles.filter(t => t[2] === 'k').length;
  // side faces
  const sides = side.map(t => {
    const cx = (t.v[0].x + t.v[1].x + t.v[2].x) / 3, cz = (t.v[0].z + t.v[1].z + t.v[2].z) / 3, l = Math.hypot(t.n[0], t.n[2]) || 1;
    return { cx, cz, nx: t.n[0] / l, nz: t.n[2] / l, minY: Math.min(...t.v.map(p => p.y)), cols: t.v.map(p => p.c) };
  });
  const deep = (X, Z) => { for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) if (!LAND(at(X + dx, Z + dz))) return false; return true; };
  res.inward = sides.filter(s => deep(Math.floor(s.cx + s.nx * .6), Math.floor(s.cz + s.nz * .6))).slice(0, 5).map(s => [s.cx, s.cz]);
  const cliffs = sides.filter(s => s.minY <= -0.8), banks = sides.filter(s => s.minY <= -0.1);
  res.cliffs = cliffs.length;
  res.notGrey = cliffs.flatMap(s => s.cols).filter(c => Math.max(...c) - Math.min(...c) > .12).slice(0, 3);
  const near = (list, x, z) => list.some(s => Math.hypot(s.cx - x, s.cz - z) <= .9);
  const noCliff = [], noBank = [];
  for (const [X, Z, ch] of tiles) {
    if (!LAND(ch) || n4(X, Z, LAND) < 2) continue;
    for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const o = at(X + dx, Z + dz), mx = X + .5 + dx * .5, mz = Z + .5 + dz * .5;
      if ((o === ' ' || o === 'k') && !near(cliffs, mx, mz)) noCliff.push([X, Z, dx, dz]);
      if (WATER(o) && !near(banks, mx, mz)) noBank.push([X, Z, dx, dz]);
    }
  }
  res.noCliff = noCliff.slice(0, 5); res.noCliffN = noCliff.length; res.noBank = noBank.slice(0, 5); res.noBankN = noBank.length;
  // ---- water
  const W = tris(box.waterGeometry(view));
  const wIdx = index(W.filter(t => t.flat));
  res.water = { down: W.filter(t => !(t.flat && t.n[1] > 0)).length, badY: W.filter(t => !(t.y >= -0.2 && t.y < 0)).length,
    notBlue: W.filter(t => t.v.some(p => !(p.c[2] > p.c[0]))).length,
    miss: tiles.filter(([X, Z, ch]) => WATER(ch) && !wIdx(X + .5, Z + .5)).slice(0, 5), outline: outline(W) };
  // ---- lanes
  const paths = box.lanePaths(view);
  const pts = paths.flatMap(p => p.pts);
  const segDist = (x, z) => { let best = Infinity; for (const p of paths) for (let i = 0; i < Math.max(1, p.pts.length - 1); i++) {
    if (p.pts.length === 1) { best = Math.min(best, Math.hypot(p.pts[0][0] - x, p.pts[0][1] - z)); continue; }
    const [ax, az] = p.pts[i], [bx, bz] = p.pts[i + 1], dx = bx - ax, dz = bz - az, L = dx * dx + dz * dz;
    const u = L ? Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / L)) : 0; best = Math.min(best, Math.hypot(ax + dx * u - x, az + dz * u - z)); } return best; };
  const laneTiles = tiles.filter(t => 'rtB'.includes(t[2])), blocked = tiles.filter(t => 'PH'.includes(t[2]));
  res.lanes = { n: paths.length,
    uncovered: tiles.filter(t => 'rt'.includes(t[2]) && segDist(t[0] + .5, t[1] + .5) > .3).slice(0, 5),
    offRoad: pts.filter(([x, z]) => !laneTiles.some(t => Math.hypot(t[0] + .5 - x, t[1] + .5 - z) <= .75)).slice(0, 5),
    onPlot: pts.filter(([x, z]) => blocked.some(t => Math.hypot(t[0] + .5 - x, t[1] + .5 - z) < .55)).slice(0, 5) };
  let turnMax = 0, turnAt = null;
  for (const p of paths) {
    const q = p.pts.filter((v, i) => i === 0 || Math.hypot(v[0] - p.pts[i - 1][0], v[1] - p.pts[i - 1][1]) > 1e-6);
    for (let i = 1; i + 1 < q.length; i++) {
      const ax = q[i][0] - q[i - 1][0], az = q[i][1] - q[i - 1][1], bx = q[i + 1][0] - q[i][0], bz = q[i + 1][1] - q[i][1];
      const a = Math.acos(Math.max(-1, Math.min(1, (ax * bx + az * bz) / (Math.hypot(ax, az) * Math.hypot(bx, bz)))));
      if (a > turnMax) { turnMax = a; turnAt = q[i]; }
    }
  }
  res.lanes.turnMax = turnMax * 180 / Math.PI; res.lanes.turnAt = turnAt;
  const L = tris(box.laneGeometry(view)), lIdx = index(L.filter(t => t.flat));
  res.lanes.badFace = L.filter(t => !(t.flat && t.n[1] > 0 && t.y > 0 && t.y <= 0.1)).length;
  res.lanes.faces = L.length;
  res.lanes.notCovered = pts.filter(([x, z]) => !WATER(at(Math.floor(x), Math.floor(z))) && !lIdx(x, z)).slice(0, 5);
  res.lanes.overWater = L.filter(t => { const cx = (t.v[0].x + t.v[1].x + t.v[2].x) / 3, cz = (t.v[0].z + t.v[1].z + t.v[2].z) / 3; return 'ws'.includes(at(Math.floor(cx), Math.floor(cz))); }).length;
  // width across straight runs of r tiles (along x or along z) with no road beside them
  const R = ch => 'rtB'.includes(ch), width = [], straight = [];
  for (const [X, Z, ch] of tiles) {
    if (ch !== 'r') continue;
    for (const [ux, uz] of [[1, 0], [0, 1]]) {
      const vx = uz, vz = ux; // across the run
      if (at(X - ux, Z - uz) === 'r' && at(X + ux, Z + uz) === 'r' && !R(at(X + vx, Z + vz)) && !R(at(X - vx, Z - vz))) straight.push([X, Z]);
      if (![-2, -1, 1, 2].every(d => at(X + ux * d, Z + uz * d) === 'r')) continue;
      if ([-2, -1, 0, 1, 2].some(d => R(at(X + ux * d + vx, Z + uz * d + vz)) || R(at(X + ux * d - vx, Z + uz * d - vz)))) continue;
      const cx = X + .5, cz = Z + .5;
      width.push({ at: [X, Z], in2: lIdx(cx + vx * .2, cz + vz * .2) && lIdx(cx - vx * .2, cz - vz * .2),
        out5: lIdx(cx + vx * .499, cz + vz * .499) || lIdx(cx - vx * .499, cz - vz * .499) });
    }
  }
  res.lanes.width = width;
  // lane colour at the centre of a straight road tile, per territory
  const colAt = (x, z) => { let best = null, bd = Infinity; for (const t of L) for (const p of t.v) { const d = Math.hypot(p.x - x, p.z - z); if (d < bd) { bd = d; best = p.c; } } return best; };
  const byTerr = new Map();
  for (const [X, Z] of straight) { const t = box.cellTerrain(view, X, Z); const k = t ? t.id : ''; if (!byTerr.has(k)) byTerr.set(k, []); if (byTerr.get(k).length < 8) byTerr.get(k).push([X, Z, t]); }
  res.lanes.roadColors = [...byTerr.values()].flat().map(([X, Z, t]) => ({ terr: t && t.id, era: t && t.era, at: [X, Z], c: colAt(X + .5, Z + .5), want: box.rgbOf(box.roadColor(t)) }));
  res.lanes.trackColors = tiles.filter(t => t[2] === 't' && n4(t[0], t[1], c => c === 't') === 2).slice(0, 10).map(([X, Z]) => ({ c: colAt(X + .5, Z + .5), want: box.rgbOf(box.trackColor(box.cellTerrain(view, X, Z))) }));
  // ---- wild decoration
  const D = box.wildDecor(view);
  const inOwn = D.filter(d => { const ch = at(Math.floor(d.x), Math.floor(d.z)); return !ch || ch === ' '; }).length;
  const kinds = { f: [], m: [], '.': [], B: [] };
  for (const d of D) { const ch = at(Math.floor(d.x), Math.floor(d.z)); if (kinds[ch]) kinds[ch].push(d); }
  const off = list => list.filter(d => Math.hypot(d.x - Math.floor(d.x) - .5, d.z - Math.floor(d.z) - .5) > .08).length;
  res.decor = { n: D.length, inVoid: inOwn, pines: kinds.f.length, pinesOff: off(kinds.f), rocks: kinds.m.length, rocksOff: off(kinds.m),
    plants: kinds['.'].length, plantsOff: off(kinds['.']), bridges: kinds.B.length, bridgesOff: off(kinds.B),
    B: tiles.filter(t => t[2] === 'B').length, f: tiles.filter(t => t[2] === 'f').length };
  out[name] = res;
}
process.stdout.write(JSON.stringify(out));
"""

_CACHE = {}


def land_results():
    if "land" not in _CACHE:
        section = land_section()
        if section is None:
            raise AssertionError("no land section (/* ---------- the land ...) in the page script")
        for name in ("groundGeometry", "waterGeometry", "lanePaths", "laneGeometry"):
            if not re.search(r"^function %s\s*\(" % name, section, re.M):
                raise AssertionError("function %s(view) not found in the land section" % name)
        prelude = land_prelude(section)
        # city-people: wildDecor (and its hash2) moved to the simulation section so footprints() can
        # block walking around plants (tests/test_agent_city_walk.py); take it from there when needed
        if not re.search(r"^function wildDecor\s*\(", section, re.M):
            src = tp.function_source("wildDecor")
            if src is None:
                raise AssertionError("function wildDecor(view) not found in the page script")
            m = re.search(r"^const hash2 = [^\n]+", tp.inline_script(), re.M)
            extra = [m.group(0).replace("const hash2", "var hash2", 1)] if m and "hash2" not in section else []
            prelude = "\n".join([prelude] + extra + [src])
        _CACHE["land"] = tp.run_node(LAND_JS, {"prelude": prelude, "section": section, "views": views()})
    return _CACHE["land"]


VIEWS = ("demo", "gaps")


class TestSmoothGround(unittest.TestCase):
    def each(self):
        return [(name, land_results()[name]) for name in VIEWS]

    def test_one_seamless_top_facing_up(self):
        for name, r in self.each():
            with self.subTest(view=name):
                self.assertEqual(r["down"], 0, "flat faces pointing down")
                self.assertEqual(r["seams"], 0, "one vertex position has two colours: a seam / a per-tile colour step")

    def test_no_per_tile_colour_steps(self):
        for name, r in self.each():
            with self.subTest(view=name):
                self.assertLessEqual(r["stepMax"], .12, "a hard colour step along a top edge")
                self.assertLessEqual(r["gradMax"], .45, "colour jumps too fast near %s: not a smooth blend" % r["gradAt"])

    def test_the_outline_is_a_smooth_curve(self):
        for name, r in self.each():
            with self.subTest(view=name):
                o = r["outline"]
                self.assertGreater(o["len"], 20)
                self.assertEqual(o["stair"], 0, "stair-step corners at %s" % o["stairAt"])
                self.assertLess(o["sharpShare"], .03, "too many sharp corners on the outline")
                self.assertLessEqual(o["axisShare"], .35, "the outline runs along the tile grid")

    def test_the_land_follows_the_tiles(self):
        for name, r in self.each():
            with self.subTest(view=name):
                self.assertEqual(r["missN"], 0, "land tile centres not on the ground: %s" % r["miss"])
                self.assertEqual(r["overN"], 0, "ground over open void or water: %s" % r["over"])

    def test_cliffs_and_banks_follow_the_curve(self):
        for name, r in self.each():
            with self.subTest(view=name):
                self.assertGreater(r["cliffs"], 10)
                self.assertEqual(r["inward"], [], "a side face looks into the land")
                self.assertEqual(r["notGrey"], [], "the cliff is grey rock, never brown earth")
                self.assertEqual(r["noCliffN"], 0, "no cliff at the land's edge near %s" % r["noCliff"])
                self.assertEqual(r["noBankN"], 0, "no bank where land meets water near %s" % r["noBank"])

    def test_the_ravine_has_a_floor(self):
        r = land_results()["gaps"]
        self.assertGreater(r["kN"], 0, "test view has no ravine")
        self.assertEqual(r["kTop"], 0, "the ravine is open, not covered by the ground")
        self.assertEqual(r["kLow"], [], "ravine tiles with no floor")

    def test_cheap_enough(self):
        for name, r in self.each():
            with self.subTest(view=name):
                self.assertLessEqual(r["tris"], 60 * r["area"], "too many triangles for the frame budget")
                self.assertLess(r["ms"], 700, "ground + water + lanes must build fast: buildLand runs on every world event")


class TestSmoothWater(unittest.TestCase):
    def test_water_is_smooth_and_covers_every_water_tile(self):
        for name in VIEWS:
            with self.subTest(view=name):
                w = land_results()[name]["water"]
                self.assertEqual((w["down"], w["badY"], w["notBlue"]), (0, 0, 0))
                self.assertEqual(w["miss"], [], "water tiles with no water")
                if name == "demo":
                    self.assertEqual(w["outline"]["stair"], 0, "stair steps at %s" % w["outline"]["stairAt"])
                    self.assertLess(w["outline"]["sharpShare"], .03)
                    self.assertLessEqual(w["outline"]["axisShare"], .35)


class TestLanes(unittest.TestCase):
    def each(self):
        return [(name, land_results()[name]["lanes"]) for name in VIEWS]

    def test_lanes_follow_the_roads_and_tracks(self):
        for name, l in self.each():
            with self.subTest(view=name):
                self.assertGreater(l["n"], 0)
                self.assertEqual(l["uncovered"], [], "road/track tiles with no lane")
                self.assertEqual(l["offRoad"], [], "a lane wanders off the roads")
                self.assertEqual(l["onPlot"], [], "a lane runs over a plot or the hall")

    def test_lanes_curve_smoothly(self):
        for name, l in self.each():
            with self.subTest(view=name):
                self.assertLessEqual(l["turnMax"], 35, "a sharp turn inside one lane at %s" % l["turnAt"])

    def test_ribbons_are_drawn_flat_above_the_ground(self):
        for name, l in self.each():
            with self.subTest(view=name):
                self.assertGreater(l["faces"], 0)
                self.assertEqual(l["badFace"], 0, "lane faces must be flat, face up, at 0 < y <= 0.1")
                self.assertEqual(l["notCovered"], [], "lane points with no ribbon")
                self.assertEqual(l["overWater"], 0, "a lane drawn over the water")

    def test_a_lane_is_narrower_than_a_tile(self):
        widths = [w for name in VIEWS for w in land_results()[name]["lanes"]["width"]]
        self.assertGreater(len(widths), 10, "no straight road runs found in the test views")
        for w in widths:
            with self.subTest(at=w["at"]):
                self.assertTrue(w["in2"], "centre +- 0.2 must be on the lane")
                self.assertFalse(w["out5"], "the lane fills the whole tile: that is a row of tiles again")

    def test_lane_colours_follow_era_and_infra(self):
        rows = land_results()["gaps"]["lanes"]["roadColors"] + land_results()["demo"]["lanes"]["roadColors"]
        self.assertTrue(rows)
        eras = set()
        for row in rows:
            with self.subTest(terr=row["terr"], era=row["era"], at=row["at"]):
                self.assertLessEqual(max(abs(a - b) for a, b in zip(row["c"], row["want"])), .06,
                                     "a road lane takes roadColor(t)")
                eras.add((row["era"], tuple(round(v, 2) for v in row["c"])))
        self.assertGreater(len({e for e, _ in eras}), 1, "test views need roads of two eras")
        tracks = land_results()["demo"]["lanes"]["trackColors"]
        self.assertTrue(tracks)
        for row in tracks:
            self.assertLessEqual(max(abs(a - b) for a, b in zip(row["c"], row["want"])), .06, "a track lane takes trackColor(t)")
        src = land_section() or ""
        self.assertTrue("roadColor(" in src, "lanes use roadColor")
        self.assertTrue("trackColor(" in src, "lanes use trackColor")

    def test_build_land_draws_the_lanes(self):
        src = tp.function_source("buildLand") or ""
        for name in ("laneGeometry(", "groundGeometry(", "waterGeometry("):
            self.assertTrue(name in src, "buildLand must call " + name)


class TestWildDecor(unittest.TestCase):
    def test_no_rows_of_trees(self):
        for name in VIEWS:
            with self.subTest(view=name):
                d = land_results()[name]["decor"]
                self.assertEqual(d["inVoid"], 0, "decoration outside the land")
                self.assertEqual(d["bridges"], d["B"], "one bridge per bridge tile")
                self.assertEqual(d["bridgesOff"], 0, "bridges sit on the tile centre")
                for kind in ("pines", "rocks", "plants"):
                    if d[kind]:
                        self.assertGreaterEqual(d[kind + "Off"], .8 * d[kind], "%s stand in rows on the tile centres" % kind)
        self.assertGreater(land_results()["gaps"]["decor"]["pines"], 0, "the forest belt has pines")
        self.assertTrue("wildDecor(" in (tp.function_source("buildLand") or ""), "buildLand must call wildDecor(")


# ---------------------------------------------------------------------------
# Page: empty world and first view
# ---------------------------------------------------------------------------

EMPTY_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
const box = { Math, JSON, console, performance: { now: () => 0 }, cam: { az: .7, el: 30 * Math.PI / 180, dist: 9, tx: 0, tz: 0 },
  W: 1200, H: 800, land: { hx: 13, hz: 13 }, map: { territories: [] }, camChanged(){}, clamp: (v, a, b) => Math.max(a, Math.min(b, v)) };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
out.full = box.distMax();
box.land = { hx: 0, hz: 0 };
out.empty = box.distMax();
box.cam.dist = box.DIST_DEFAULT;
const d0 = box.cam.dist; box.zoomStep(1); out.zoomOut = box.cam.dist > d0;
const d1 = box.cam.dist; box.zoomStep(-1); box.zoomStep(-1); out.zoomIn = box.cam.dist < d1;
for (let i = 0; i < 30; i++) box.zoomStep(1);
out.maxDist = box.cam.dist;
for (let i = 0; i < 30; i++) box.zoomStep(-1);
out.minDist = box.cam.dist;
out.ready = [box.landReady()];
box.map = { territories: [{ id: 't', cx: 0, cz: 0 }] };
out.ready.push(box.landReady());
box.map = {};
out.ready.push(box.landReady());
// the governor
const gv = { g: { visible: true, position: { y: 0, set(){} } }, sel: { visible: false } };
const el = () => ({ setAttribute(){}, removeAttribute(){}, hidden: true, style: {} });
// city-people P0: the figure shows only where a governor session is present (governorAt)
Object.assign(box, { govsByTerr: new Map([['t', { state: 'idle' }]]), govTerr: 't',
  terrOf: id => (box.map.territories || []).find(t => t.id === id), hallStand: t => ({ x: t.cx, y: t.cz + 1.4 }) });
Object.assign(box, { govV: gv, gov: { x: 0, y: 0, bubble: null }, DEMO: false, govState: 'idle', simT: 0, selected: null,
  anim(){}, toScreen: () => [0, 0], setText(){}, pin(){}, openAskFor: () => null, govBub: el(), govQm: el(), govTag: el() });
box.map = { territories: [] }; box.updateGovernor(); out.govEmpty = gv.g.visible;
box.map = { territories: [{ id: 't', cx: 0, cz: 0 }] }; box.updateGovernor(); out.govLand = gv.g.visible;
// the empty line
const line = { hidden: false };
box.$ = sel => (sel === '#empty-land' ? line : null);
box.showEmptyLine({ territories: [] }); out.lineEmpty = line.hidden;
box.showEmptyLine({ territories: [{ id: 't' }] }); out.lineLand = line.hidden;
process.stdout.write(JSON.stringify(out));
"""


class TestEmptyWorld(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fns = tp.page_fns("distMax", "zoomStep", "landReady", "updateGovernor", "showEmptyLine", "governorAt",
                          optional=("landSpread", "centreHeight", "islandSpread"))
        cls.out = tp.run_node(EMPTY_JS, {"prelude": tp.constants_prelude(), "fns": fns})

    def test_zoom_keeps_working_with_no_land(self):
        o = self.out
        self.assertAlmostEqual(o["empty"], o["full"], delta=1e-6, msg="an empty world zooms like one fresh territory")
        self.assertTrue(o["zoomOut"], "zoom out does not move")
        self.assertTrue(o["zoomIn"], "zoom in does not move")
        self.assertGreater(o["maxDist"], 15)
        self.assertLess(o["maxDist"], 80)
        self.assertLessEqual(o["minDist"], 3.5)

    def test_land_ready(self):
        self.assertEqual(self.out["ready"], [False, True, False])

    def test_no_governor_floating_in_the_void(self):
        self.assertIs(self.out["govEmpty"], False)
        self.assertIs(self.out["govLand"], True)
        self.assertTrue("landReady()" in (tp.function_source("updatePerson") or ""), "people never float in the void either")

    def test_one_line_says_there_is_no_territory_yet(self):
        m = re.search(r"<p\b[^>]*\bid=\"empty-land\"[^>]*>(.*?)</p>", tp.markup(), re.S)
        self.assertIsNotNone(m, '<p id="empty-land"> not found')
        self.assertIn("hidden", m.group(0).split(">")[0])
        self.assertIn("还没有领地", m.group(1))
        self.assertIs(self.out["lineEmpty"], False)
        self.assertIs(self.out["lineLand"], True)
        self.assertTrue("showEmptyLine(" in (tp.function_source("buildLand") or ""), "buildLand must call showEmptyLine(")

    def test_first_view_waits_for_a_territory(self):
        src = tp.function_source("buildLand") or ""
        line = next((ln for ln in src.split("\n") if "resetCam()" in ln), "")
        self.assertTrue(line, "buildLand must still send the first world home (resetCam)")
        self.assertRegex(line, r"territories\.length|landReady\(\)",
                         "the first-view flag must wait for a world with a territory")


NEWCIT_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, ROLES: { worker: { color: '#ffffff' } }, SKIN: ['#f1c6a0'], pick: a => a[0],
  hallStand: t => ({ x: t.cx, y: t.cz + 1.4 }),
  map: { territories: [{ id: 'a', cx: 0, cz: 0 }, { id: 'b', cx: 26, cz: 0 }] }, govTerr: 'b' };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const out = [box.newCitizen('c1', 'worker', '', 'a').x, box.newCitizen('c2', 'worker', '', '').x, box.newCitizen('c3', 'worker', '', 'zz').x];
box.govTerr = null;
out.push(box.newCitizen('c4', 'worker', '', '').x);
process.stdout.write(JSON.stringify(out));
"""


class TestFirstView(unittest.TestCase):
    def test_people_without_a_known_territory_stand_on_land(self):
        out = tp.run_node(NEWCIT_JS, {"prelude": tp.constants_prelude(), "fns": tp.page_fns("newCitizen", "terrOf")})
        self.assertEqual(out, [0, 26, 26, 0], "own territory; else the governor's; else the first")

    def test_the_governors_hall_before_the_land_is_built(self):
        snap = tp.case_block("snapshot") or ""
        i, j = snap.find("govTerr = ev.gov.terr"), snap.find("buildLand(ev.world)")
        self.assertGreaterEqual(i, 0)
        self.assertGreaterEqual(j, 0)
        self.assertLess(i, j, "govTerr must be set before buildLand, so the first view is the governor's hall")


if __name__ == "__main__":
    unittest.main()
