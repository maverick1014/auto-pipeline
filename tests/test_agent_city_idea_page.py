"""Failing tests for idea-city, page side (bin/agent-city.html). The server side is in
tests/test_agent_city_idea_server.py.

CONTRACT (bin/agent-city.html)

  C1 English too
    const LANG = '__CITY_LANG__';  (the server fills it in: 'en' or 'zh'; anything but 'en' is zh)
    const TEXT = { zh: {...}, en: {...} };  every text the page shows, both languages: the same keys,
      every value a non-empty string, no CJK character in any en value. Placeholders "{name}".
    function T(key, vars) -> TEXT[en or zh][key], each "{name}" replaced by vars[name]; an unknown key
      gives the key itself.
    Nowhere else in the page -- markup, style, script, demo data -- is there a CJK character (comments
      aside). The static markup gets its text from TEXT at start. document.documentElement.lang follows
      LANG ('en' or 'zh-CN').

  C2 fade only when close
    const FADE_DIST = 12 (the distance where camTarget starts drawing the view to the land middle).
    viewBlockers(el) -> an empty set whenever cam.dist > FADE_DIST: zoomed out, nothing fades.

  C5 idle is not a question
    'waiting' {id}: the citizen stays where it is (no goChain / goHall), c.waiting = true;
    'resume' {id}: c.waiting = false. A snapshot agent with waiting true starts the same way.
    citizenStatus(c) -> ['you', '等你回话'] (zh) for a waiting citizen with no live ask.
    Other members' people too (applyRemote handles 'waiting' and 'resume').

  C7 zoomed out, the land fills about 80% of the stage, centred
    landBox(view) -> {hx, hz, cx, cz}: the box of the view's non-void tiles (' ' is void) in scene
      units. Tile (X, Z) covers [X - mid.x, X - mid.x + 1] x [Z - mid.z, Z - mid.z + 1] with
      mid = {x: Math.round(view.x0 + view.w / 2), z: Math.round(view.z0 + view.h / 2)} (landState's mid).
      No land tile -> {hx: 0, hz: 0, cx: 0, cz: 0}. landState sets land = landBox(view).
    landSpread / distMax / camTarget use that box and its centre (cx, cz; missing = 0). A side under
      13 counts as 13 (a small land zooms like one fresh territory). landBox may carry more (e.g. the
      land's outline points): the fit rules below also hold for the real land tiles of a view (an L of
      territories leaves a corner of its box empty -- the land itself must be the thing centred).
    At cam.dist = distMax(), from any angle and on any stage: the whole box is on the stage (no corner
      past 95% of the half-stage), its middle within 12% of the half-stage from the stage middle, and at the worst angle it
      fills 74% to 88% of the half-stage on its tighter side.
    updateCamera keeps camera.far past the farthest land corner (then updateProjectionMatrix).

  C8 every model under its own full name
    lib holds each model under its full MODELS entry ('commercial/building-a'); the script never takes
    a bare name with split('/')[1]. ERA_LOOK, MODEL_SIZE, HEX_SINK, REST_FIT, SYS_TINT, OFFICE_OPT name
    each model by its full entry, or by a bare name only when no other pack has that name. The town
    and city shop models are commercial/, the workshop models industrial/.

  C9 the planks of every era show survive a land rebuild
    makeShowRun parents its road planks to a group that buildLand never empties (not landGroup).

  C11 a lone road stub draws nothing
    A road or track tile with no road/track/bridge neighbour (4 sides) gets no lane geometry (no round
    patch). tests/test_agent_city_land.py: such lone tiles are no longer "uncovered".

  C13 every governor talks in his own bubble
    govSay(terr, text, dur): that territory's governor says TEXT for DUR seconds (simT clock).
    govTalk(terr) -> the text his bubble shows now, or '': 等你回话… (zh) while that territory's
      governor is waiting, else his own govSay text while it lasts. Never another territory's.
    setGovState(state, terr): only the home territory (govTerr) changes govState (no terr: the home one,
      as before); govSay never adds a territory to govsByTerr (that map is who is present); case 'gov' calls
      setGovState(ev.state, ev.terr). updateGovernor and updateGovPool show govTalk(terr); no
      say(gov, ...) is left.

  C14 never an empty bubble
    personBubble(c) -> the text over citizen C now, or '' (no bubble): its question while asking,
    else its own say() text while it lasts (never while walking to the hall); '' when that text is
    empty. updatePerson shows the bubble only when personBubble(c) is not ''.

  C16 other members' people follow the chain
    applyRemote handles 'relay' and 'relay_end' like the local page does.

  C10 district name labels (approved mock mock/idea-city-labels-mock.html, owner "ok like this for now")
    systemsDecor: every knowledge sign ('roads/road-sign-street', kind 'knowledge') carries d, its
      district (house shop tower workshop library): healthy -> one sign per district with an open plot,
      low -> one (the district of the first open plot); each on the free tile nearest its district's
      plots (within 3 tiles, Chebyshev, of one of them when such a tile is free), not near the hall.
    TEXT keys district.house/.shop/.tower/.workshop/.library:
      zh 住宅区 商业街 测试区 工坊区 图书馆区, en Homes Shops Tests Workshops Library.
    landOverlays(view, signs): signs = [{x, z, d}] in world tiles (buildLand passes the district signs);
      one '.dlbl' overlay per sign (its own class, never '.lbl'), text T('district.' + d), CSS var --c =
      DCOL[d] (the colour bar); made again from scratch on every call, like the territory labels.
      With no signs argument: no '.dlbl'.
    pinLandOverlays(): each district label is pinned at its sign and carries class 'far' whenever
      cam.dist >= DIST_DEFAULT (the default view and anything further out); closer (the two zoom-in
      steps) it has no 'far'. CSS: .dlbl smaller and quieter than .lbl; .dlbl.far {opacity: 0} with an
      opacity transition, so labels fade out from the default step on.
"""

import math
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
import test_agent_city_page as tp  # noqa: E402
import test_agent_city_land as tl  # noqa: E402

CJK = re.compile(r"[㐀-鿿＀-￯　-〿]")


def need(*names):
    for n in names:
        if tp.function_source(n) is None:
            raise AssertionError("function %s(...) not found in the page script" % n)
    return tp.page_fns(*names)


def strip_comments(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(^|[\s;{}(),])//[^\n]*", r"\1", text)


# --------------------------------------------------------------------- C1

class TestEnglishToo(unittest.TestCase):
    def text(self):
        lit = tp.const_object("TEXT")
        self.assertIsNotNone(lit, "const TEXT = { zh: {...}, en: {...} }; not found")
        return tp.js_value(lit)

    def test_lang_placeholder(self):
        self.assertIn("const LANG = '__CITY_LANG__';", tp.inline_script())

    def test_html_lang_follows(self):
        self.assertRegex(tp.inline_script(), r"documentElement\.lang\s*=")

    def test_both_languages_same_keys(self):
        t = self.text()
        self.assertEqual(set(t), {"zh", "en"})
        self.assertEqual(set(t["zh"]), set(t["en"]))
        self.assertGreater(len(t["zh"]), 50)
        for lang in ("zh", "en"):
            for k, v in t[lang].items():
                with self.subTest(lang=lang, key=k):
                    self.assertIsInstance(v, str)
                    self.assertTrue(v.strip())
        bad = [(k, v) for k, v in t["en"].items() if CJK.search(v)]
        self.assertEqual(bad[:5], [])

    def test_no_chinese_outside_text(self):
        page = tp.page()
        lit = tp.const_object("TEXT")
        self.assertIsNotNone(lit)
        rest = strip_comments(page.replace(lit, "{}", 1))
        found = [rest[max(0, m.start() - 30):m.end() + 10].replace("\n", " ") for m in CJK.finditer(rest)]
        self.assertEqual(found[:8], [], "%d CJK characters outside TEXT" % len(found))

    def test_T(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { lit, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
for (const lang of ['en', 'zh', 'fr', '__CITY_LANG__']) {
  const box = { Math, JSON, console };
  vm.createContext(box);
  vm.runInContext("var LANG = '" + lang + "'; var TEXT = " + lit + ";\n" + fns, box);
  box.TEXT.zh.__t = 'a {x} b {x}'; box.TEXT.en.__t = 'A {x} B';
  out[lang] = { t: box.T('__t', { x: 1 }), unknown: box.T('no.such.key') };
}
process.stdout.write(JSON.stringify(out));
"""
        lit = tp.const_object("TEXT")
        self.assertIsNotNone(lit)
        r = tp.run_node(js, {"lit": lit, "fns": need("T")})
        self.assertEqual(r["en"]["t"], "A 1 B")
        for lang in ("zh", "fr", "__CITY_LANG__"):
            self.assertEqual(r[lang]["t"], "a 1 b 1", lang)
        self.assertEqual(r["en"]["unknown"], "no.such.key")


# ----------------------------------------------------------------- C2, C7

CAMERA_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns, boxes, lb } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const camera = { aspect: 1, fov: 40, near: .25, far: 150, look: null, updateProjectionMatrix(){},
  position: { x: 0, y: 0, z: 0, set(x, y, z){ this.x = x; this.y = y; this.z = z; return this; } },
  lookAt(x, y, z){ this.look = typeof x === 'object' ? [x.x, x.y, x.z] : [x, y, z]; } };
const box = { Math, JSON, console, performance: { now: () => 0 }, camera, cam: { az: 0, el: .5, dist: 9, tx: 0, tz: 0 },
  W: 874, H: 710, clamp, drag: null, pinch: null, camLiftNow: 0, fadeables: [], home: { x: 0, z: 0 },
  land: { hx: 13, hz: 13, cx: 0, cz: 0 }, mid: { x: 0, z: 0 } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
box.heightAt = () => 0;
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]], dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = a => { const l = Math.hypot(...a); return a.map(v => v / l); };
// ---- C7: landBox
out.landBox = {};
if (typeof box.landBox === 'function') for (const [name, v] of Object.entries(lb)) out.landBox[name] = box.landBox(v);
// ---- C7: the fit
function shot(L, W, H, az){
  box.W = W; box.H = H; box.land = L;
  Object.assign(box.cam, { az, el: box.EL_DEFAULT, tx: .3, tz: 2.8 });
  box.cam.dist = box.distMax(); box.camLiftNow = 0;
  for (let i = 0; i < 40; i++) box.updateCamera();
  const P = [camera.position.x, camera.position.y, camera.position.z], Lk = camera.look;
  const f = norm(sub(Lk, P)), r = norm(cross(f, [0, 1, 0])), u = cross(r, f);
  const t = Math.tan(box.FOV * Math.PI / 360), a = W / H;
  let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, far = 0;
  for (const x of [L.cx - L.hx, L.cx + L.hx]) for (const z of [L.cz - L.hz, L.cz + L.hz]) for (const y of [-1.05, 0]) {
    const d = sub([x, y, z], P), zc = dot(d, f), nx = dot(d, r) / (zc * t * a), ny = dot(d, u) / (zc * t);
    x0 = Math.min(x0, nx); x1 = Math.max(x1, nx); y0 = Math.min(y0, ny); y1 = Math.max(y1, ny); far = Math.max(far, Math.hypot(...d));
  }
  return { fill: Math.max((x1 - x0) / 2, (y1 - y0) / 2), cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, edge: Math.max(-x0, x1, -y0, y1),
    far, camFar: camera.far };
}
out.fit = [];
for (const L of boxes) for (const [W, H] of [[874, 710], [358, 394], [1400, 700], [1280, 650]]) {
  const shots = []; for (let k = 0; k < 12; k++) shots.push(shot(L, W, H, k * Math.PI / 12));
  out.fit.push({ L, W, H, maxFill: Math.max(...shots.map(s => s.fill)), maxOff: Math.max(...shots.map(s => Math.max(Math.abs(s.cx), Math.abs(s.cy)))),
    maxEdge: Math.max(...shots.map(s => s.edge)), farShort: shots.filter(s => !(s.camFar >= s.far)).length });
}
// ---- C7: the fit on the REAL land (every non-void tile), not its bounding box: an L-shaped land leaves a
// corner of its box empty, and centring the box then leaves the land itself off-centre (seen headless, demo)
out.content = [];
if (typeof box.landBox === 'function') for (const [name, v] of Object.entries(lb)) {
  if (name === 'empty') continue;
  const mx = Math.round(v.x0 + v.w / 2), mz = Math.round(v.z0 + v.h / 2), pts = [];
  for (let r = 0; r < v.h; r++) for (let c = 0; c < v.w; c++) if (v.rows[r][c] !== ' ') {
    const X = v.x0 + c - mx, Z = v.z0 + r - mz;
    for (const [dx, dz] of [[0, 0], [1, 0], [0, 1], [1, 1]]) pts.push([X + dx, Z + dz]);
  }
  for (const [W, H] of [[1248, 650], [874, 710], [358, 394]]) {
    const shots = [];
    for (let k = 0; k < 12; k++) {
      box.W = W; box.H = H; box.land = box.landBox(v);
      Object.assign(box.cam, { az: k * Math.PI / 12, el: box.EL_DEFAULT, tx: .3, tz: 2.8 });
      box.cam.dist = box.distMax(); box.camLiftNow = 0;
      for (let i = 0; i < 40; i++) box.updateCamera();
      const P = [camera.position.x, camera.position.y, camera.position.z], Lk = camera.look;
      const f = norm(sub(Lk, P)), r = norm(cross(f, [0, 1, 0])), u = cross(r, f);
      const t = Math.tan(box.FOV * Math.PI / 360), a = W / H;
      let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
      for (const [x, z] of pts) for (const y of [-1.05, 0]) {
        const d = sub([x, y, z], P), zc = dot(d, f), nx = dot(d, r) / (zc * t * a), ny = dot(d, u) / (zc * t);
        x0 = Math.min(x0, nx); x1 = Math.max(x1, nx); y0 = Math.min(y0, ny); y1 = Math.max(y1, ny);
      }
      shots.push({ fill: Math.max((x1 - x0) / 2, (y1 - y0) / 2), off: Math.max(Math.abs((x0 + x1) / 2), Math.abs((y0 + y1) / 2)),
        edge: Math.max(-x0, x1, -y0, y1) });
    }
    out.content.push({ name, W, H, maxFill: Math.max(...shots.map(s => s.fill)), maxOff: Math.max(...shots.map(s => s.off)),
      maxEdge: Math.max(...shots.map(s => s.edge)) });
  }
}
// ---- C2: nothing fades once zoomed out
box.W = 874; box.H = 710; box.land = { hx: 13, hz: 13, cx: 0, cz: 0 };
box.heightAt = (x, z) => (x >= 1 && x < 3 && z >= 1 && z < 3 ? 3.2 : 0) || (Math.abs(x) < 2 && Math.abs(z) < 2 ? 3 : 0);
const blockersAt = dist => { Object.assign(box.cam, { az: Math.PI / 4, el: box.EL_DEFAULT, tx: 0, tz: 0, dist }); box.camLiftNow = 0;
  return [...box.viewBlockers(box.EL_DEFAULT)].length; };
out.fade = { near: blockersAt(9), past: blockersAt((box.FADE_DIST || 12) + .5), limit: blockersAt(box.distMax()), FADE_DIST: box.FADE_DIST };
process.stdout.write(JSON.stringify(out));
"""

_CACHE = {}


def camera_results():
    if "cam" not in _CACHE:
        fns = need("updateCamera", "camLift", "camTarget", "distMax", "viewBlockers", "landSpread", "centreHeight", "aroundH")
        extra = tp.function_source("landBox")
        fns += "\n" + (extra or "")
        boxes = [{"hx": 13, "hz": 13, "cx": 0, "cz": 0}, {"hx": 26, "hz": 13, "cx": 5, "cz": -3},
                 {"hx": 13, "hz": 26, "cx": -4, "cz": 7}, {"hx": 26, "hz": 26, "cx": -13, "cz": 0},
                 {"hx": 39, "hz": 39, "cx": 0, "cz": 0}, {"hx": 19.5, "hz": 16, "cx": 6.5, "cz": -6.5}]
        _CACHE["cam"] = tp.run_node(CAMERA_JS, {"prelude": tp.constants_prelude(), "fns": fns,
                                                "boxes": boxes, "lb": land_box_views()})
    return _CACHE["cam"]


def quadrant_view():
    rows = []
    for r in range(26):
        rows.append(("." * 26 + " " * 26) if r < 13 else " " * 52)
    return {"x0": -26, "z0": -13, "w": 52, "h": 26, "rows": rows}


def land_box_views():
    demo = ac.demo_world()
    return {"quadrant": quadrant_view(), "demo": {k: demo[k] for k in ("x0", "z0", "w", "h", "rows")},
            "empty": {"x0": 0, "z0": 0, "w": 4, "h": 4, "rows": ["    "] * 4}}


def expected_box(v):
    # JS Math.round rounds .5 up; Python round() is banker's -- do it the JS way
    mx, mz = math.floor(v["x0"] + v["w"] / 2 + .5), math.floor(v["z0"] + v["h"] / 2 + .5)
    xs = [v["x0"] + c for r in range(v["h"]) for c in range(v["w"]) if v["rows"][r][c] != " "]
    zs = [v["z0"] + r for r in range(v["h"]) for c in range(v["w"]) if v["rows"][r][c] != " "]
    if not xs:
        return {"hx": 0, "hz": 0, "cx": 0, "cz": 0}
    x0, x1, z0, z1 = min(xs) - mx, max(xs) + 1 - mx, min(zs) - mz, max(zs) + 1 - mz
    return {"hx": (x1 - x0) / 2, "hz": (z1 - z0) / 2, "cx": (x0 + x1) / 2, "cz": (z0 + z1) / 2}


class TestZoomedOutFit(unittest.TestCase):
    def test_land_box(self):
        got = camera_results()["landBox"]
        self.assertTrue(got, "function landBox(view) not found in the page script")
        for name, v in land_box_views().items():
            with self.subTest(view=name):
                want = expected_box(v)
                for k in ("hx", "hz", "cx", "cz"):
                    self.assertAlmostEqual(got[name][k], want[k], places=6, msg=k)

    def test_land_state_uses_it(self):
        self.assertRegex(tp.function_source("landState") or "", r"land = landBox\(view\)")

    def test_fills_about_80_percent_centred(self):
        for r in camera_results()["fit"]:
            with self.subTest(land=r["L"], stage=(r["W"], r["H"])):
                self.assertLessEqual(r["maxEdge"], .95, "part of the land is cut off")
                self.assertLessEqual(r["maxOff"], .12, "the land is not in the middle")
                self.assertGreaterEqual(r["maxFill"], .74, "the land is too small")
                self.assertLessEqual(r["maxFill"], .88)

    def test_the_real_land_is_centred_and_fills(self):
        # measured on every land tile of the view (the demo is an L of three territories plus sea)
        got = camera_results()["content"]
        self.assertTrue(got)
        for r in got:
            with self.subTest(view=r["name"], stage=(r["W"], r["H"])):
                self.assertLessEqual(r["maxEdge"], .95, "part of the land is cut off")
                self.assertLessEqual(r["maxOff"], .12, "the land itself is not in the middle")
                if r["name"] != "quadrant":  # 26 x 13 tiles: under one fresh territory, fitted as 13 x 13 halves
                    self.assertGreaterEqual(r["maxFill"], .74, "the land is too small")
                self.assertLessEqual(r["maxFill"], .88)

    def test_far_plane_reaches_the_land(self):
        for r in camera_results()["fit"]:
            with self.subTest(land=r["L"], stage=(r["W"], r["H"])):
                self.assertEqual(r["farShort"], 0, "the back of the land is past the camera's far plane")


class TestNoFadeZoomedOut(unittest.TestCase):
    def test_fade_dist(self):
        self.assertEqual(camera_results()["fade"]["FADE_DIST"], 12)

    def test_close_still_fades(self):
        self.assertGreater(camera_results()["fade"]["near"], 0)

    def test_zoomed_out_nothing_fades(self):
        f = camera_results()["fade"]
        self.assertEqual((f["past"], f["limit"]), (0, 0))


# --------------------------------------------------------------------- C8

def model_refs():
    ms = tp.models()
    bare = [m.split("/")[1] for m in ms]
    return set(ms) | {b for b in bare if bare.count(b) == 1}


class TestFullModelNames(unittest.TestCase):
    def test_no_bare_name_split(self):
        self.assertEqual(re.findall(r".{0,40}split\('/'\)\[1\].{0,20}", tp.inline_script()), [])

    def test_loader_keys_by_full_entry(self):
        src = tp.function_source("loadAll") or ""
        self.assertRegex(src, r"prep\(key, g\)")

    def test_every_table_names_a_real_model(self):
        refs = model_refs()
        look = tp.js_value(tp.const_object("ERA_LOOK"))
        names = []
        for era in look.values():
            names.append(era["hall"])
            for keys in era["build"].values():
                names.extend(keys)
        for table in ("MODEL_SIZE", "HEX_SINK", "REST_FIT", "SYS_TINT", "OFFICE_OPT"):
            lit = tp.const_object(table)
            if lit:
                names.extend(tp.js_value(lit).keys())
        self.assertEqual(sorted(set(n for n in names if n not in refs)), [],
                         "not a MODELS entry, or a bare name more than one pack has")

    def test_shop_is_commercial_workshop_is_industrial(self):
        look = tp.js_value(tp.const_object("ERA_LOOK"))
        for era in ("town", "city"):
            with self.subTest(era=era):
                self.assertTrue(all(k.startswith("commercial/") for k in look[era]["build"]["shop"]), look[era]["build"]["shop"])
                self.assertTrue(all(k.startswith("industrial/") for k in look[era]["build"]["workshop"]), look[era]["build"]["workshop"])


# --------------------------------------------------------------------- C9

class TestShowPlanksSurvive(unittest.TestCase):
    def test_planks_not_under_land_group(self):
        src = tp.function_source("makeShowRun") or ""
        m = re.search(r"place\('[^']*resource-planks'[^)]*parent:\s*(\w+)", src)
        self.assertIsNotNone(m, "the road planks are placed with an explicit parent")
        parent = m.group(1)
        self.assertNotEqual(parent, "landGroup")
        land = tp.function_source("buildLand") or ""
        self.assertNotRegex(land, r"\b%s\.(remove|clear)\(|\b%s\.children" % (parent, parent),
                            "buildLand must not empty the planks' group")


# -------------------------------------------------------------------- C11

LONE_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, section, view, lone } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, Map, Set, Float32Array, Float64Array, Uint8Array, Int32Array, Array, Object, Number,
  performance: { now: () => 0 }, shows: new Map(), world: { add(){}, remove(){} },
  THREE: { Group: function(){ this.children = []; this.add = function(){}; this.remove = function(){}; } } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + section, box);
const g = box.laneGeometry(view), P = g.positions;
const [lx, lz] = [lone[0] + .5, lone[1] + .5];
let near = 0;
for (let i = 0; i < P.length; i += 3) if (Math.hypot(P[i] - lx, P[i + 2] - lz) < .6) near++;
let total = P.length / 3;
process.stdout.write(JSON.stringify({ near, total }));
"""


class TestLoneStub(unittest.TestCase):
    def test_lone_road_tile_draws_nothing(self):
        v = ac.demo_world()
        rows = [list(r) for r in v["rows"]]
        spot = None
        for r in range(2, v["h"] - 2):
            for c in range(2, v["w"] - 2):
                if all(rows[r + dr][c + dc] == "." for dr in (-2, -1, 0, 1, 2) for dc in (-2, -1, 0, 1, 2)):
                    spot = (r, c)
                    break
            if spot:
                break
        self.assertIsNotNone(spot, "demo has no open grass patch")
        rows[spot[0]][spot[1]] = "r"
        view = dict(v, rows=["".join(r) for r in rows])
        section = tl.land_section()
        prelude = tl.land_prelude(section)
        m = re.search(r"^const hash2 = [^\n]+", tp.inline_script(), re.M)
        if m and "hash2" not in section:
            prelude += "\n" + m.group(0).replace("const hash2", "var hash2", 1)
        r = tp.run_node(LONE_JS, {"prelude": prelude, "section": section, "view": view,
                                  "lone": [v["x0"] + spot[1], v["z0"] + spot[0]]})
        self.assertGreater(r["total"], 0)
        self.assertEqual(r["near"], 0, "a lone road tile still draws a round patch")


# -------------------------------------------------------------------- C13

GOV_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, simT: 0, govTerr: 'a', govState: 'idle', govsByTerr: new Map(), DEMO: false,
  gov: { x: 0, y: 1.4, bubble: null, answered: 0, dispatched: 0 } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const out = {};
box.govsByTerr.set('a', { state: 'idle' }); box.govsByTerr.set('b', { state: 'idle' });
box.govSay('b', 'go', 5);
out.said = [box.govTalk('b'), box.govTalk('a')];
box.simT = 6;
out.over = box.govTalk('b');
box.govsByTerr.set('b', { state: 'waiting' });
out.waitB = [box.govTalk('b'), box.govTalk('a')];
vm.runInContext("setGovState('waiting', 'b')", box);
out.otherState = vm.runInContext('govState', box);
vm.runInContext("setGovState('waiting', 'a')", box);
out.homeState = vm.runInContext('govState', box);
box.govsByTerr.set('a', { state: 'waiting' });
out.waitA = box.govTalk('a');
vm.runInContext("setGovState('busy')", box);
out.noTerrState = vm.runInContext('govState', box);
box.govSay('c', 'hello', 5);
out.phantom = box.govsByTerr.has('c');
out.saysAnyway = box.govTalk('c');  // the demo has no presence entries at all: its governor still talks
process.stdout.write(JSON.stringify(out));
"""


class TestGovernorBubbles(unittest.TestCase):
    def results(self):
        if "gov" not in _CACHE:
            _CACHE["gov"] = tp.run_node(GOV_JS, {"prelude": tp.constants_prelude(),
                                                 "fns": need("govSay", "govTalk", "setGovState")})
        return _CACHE["gov"]

    def test_each_governor_his_own_words(self):
        r = self.results()
        self.assertEqual(r["said"], ["go", ""])
        self.assertEqual(r["over"], "")

    def test_waiting_is_per_territory(self):
        r = self.results()
        self.assertIn("等你回话", r["waitB"][0])
        self.assertEqual(r["waitB"][1], "")
        self.assertIn("等你回话", r["waitA"])

    def test_other_territory_never_moves_the_home_state(self):
        r = self.results()
        self.assertEqual(r["otherState"], "idle")
        self.assertEqual(r["homeState"], "waiting")

    def test_no_territory_means_home(self):
        self.assertEqual(self.results()["noTerrState"], "busy", "setGovState(state) with no terr is the home one, as before")

    def test_talking_never_makes_a_governor_present(self):
        self.assertFalse(self.results()["phantom"], "govsByTerr is who is present; govSay must not add to it")
        self.assertEqual(self.results()["saysAnyway"], "hello", "talk is kept apart from presence (the demo has none)")

    def test_wiring(self):
        self.assertIn("setGovState(ev.state, ev.terr)", tp.case_block("gov") or "")
        pool = tp.function_source("updateGovPool") or ""
        self.assertNotRegex(pool, r"pin\(v\.bub, sx, sy, false\)")
        self.assertIn("govTalk(", pool)
        self.assertIn("govTalk(", tp.function_source("updateGovernor") or "")
        self.assertNotRegex(tp.inline_script(), r"\bsay\(gov\s*,")


# -------------------------------------------------------------------- C14

BUB_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, simT: 5 };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const b = c => box.personBubble(Object.assign({ state: 'working', question: '', bubble: null }, c));
const out = {
  askEmpty: b({ state: 'asking', question: '' }), askQ: b({ state: 'asking', question: 'q?' }),
  talk: b({ bubble: { text: 'hi', until: 10 } }), talkEmpty: b({ bubble: { text: '', until: 10 } }),
  toHall: b({ state: 'to_hall', bubble: { text: 'hi', until: 10 } }), none: b({}),
};
box.simT = 11; out.over = b({ bubble: { text: 'hi', until: 10 } });
process.stdout.write(JSON.stringify(out));
"""


class TestNoEmptyBubble(unittest.TestCase):
    def test_person_bubble(self):
        r = tp.run_node(BUB_JS, {"prelude": tp.constants_prelude(), "fns": need("personBubble")})
        self.assertEqual(r, {"askEmpty": "", "askQ": "q?", "talk": "hi", "talkEmpty": "", "toHall": "",
                             "none": "", "over": ""})

    def test_update_person_uses_it(self):
        self.assertIn("personBubble(c)", tp.function_source("updatePerson") or "")


# --------------------------------------------------------------- C5, C16

STATUS_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, governorAt: () => ({ x: 0, y: 0 }) };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const base = { state: 'working', askKind: '', askPhase: '', relay: '' };
process.stdout.write(JSON.stringify({
  waiting: box.citizenStatus(Object.assign({}, base, { waiting: true })),
  waitingAsk: box.citizenStatus(Object.assign({}, base, { waiting: true, askKind: 'permission' })),
  plain: box.citizenStatus(base),
}));
"""


class TestIdleOnThePage(unittest.TestCase):
    def test_status(self):
        prelude = tp.constants_prelude() + "\n" + "var STATE = " + tp.const_object("STATE") + ";"
        r = tp.run_node(STATUS_JS, {"prelude": prelude, "fns": need("citizenStatus")})
        self.assertEqual(r["waiting"], ["you", "等你回话"])
        self.assertEqual(r["waitingAsk"][1], "等你批")
        self.assertNotEqual(r["plain"][1], "等你回话")

    def test_waiting_stays_put(self):
        block = tp.case_block("waiting")
        self.assertIsNotNone(block, "case 'waiting' missing in apply()")
        self.assertNotRegex(block, r"goChain\(|goHall\(")
        self.assertIn("waiting = true", block)
        self.assertIn("waiting = false", tp.case_block("resume") or "")

    def test_snapshot_and_remote(self):
        self.assertIn("a.waiting", tp.function_source("placeAgent") or "")
        remote = tp.function_source("applyRemote") or ""
        for kind in ("waiting", "resume", "relay", "relay_end"):
            with self.subTest(kind=kind):
                self.assertIn("'%s'" % kind, remote)


# -------------------------------------------------------------------- C10

DLBL_JS = tp.FAKE_DOM_JS + r"""
const fs = require('fs'), vm = require('vm');
Object.defineProperty(El.prototype, 'className', { get(){ return [...this.classList.s].join(' '); },
  set(v){ this.classList = new CL(String(v).split(/\s+/).filter(Boolean)); } });
const { prelude, fns, view } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const ov = new El('div', [], { id: 'ov' });
const box = { Math, JSON, console, Map, Set, Array, Object, String, Number, Boolean,
  performance: { now: () => 0 }, document: { createElement: tag => new El(tag) },
  ovRoot: ov, $: s => (s === '#ov' ? ov : null), toScreen: () => [100, 100], logAt(){}, log(){}, simT: 0,
  needFrame: false, DEMO: false, labels: [], signs: [], shows: new Map(), map: view, govTerr: null,
  cam: { az: 0, el: .5, dist: 5, tx: 0, tz: 0 } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const els = cls => ov.children.filter(e => e.classList.contains(cls));
const out = {};
const signs = [{ x: 3, z: 4, d: 'house' }, { x: -5, z: 2, d: 'shop' }, { x: 6, z: -6, d: 'library' }];
box.landOverlays(view, signs);
out.made = { dlbl: els('dlbl').map(e => e.textContent), lbl: els('lbl').length,
  bars: els('dlbl').map(e => e.style && e.style.getPropertyValue ? e.style.getPropertyValue('--c') : (e.style || {})['--c']) };
const look = () => els('dlbl').map(e => ({ far: e.classList.contains('far'), hidden: !!e.hidden }));
box.cam.dist = 5; box.pinLandOverlays(); out.close = look();
box.cam.dist = 2.8; box.pinLandOverlays(); out.closest = look();
box.cam.dist = box.DIST_DEFAULT; box.pinLandOverlays(); out.dflt = look();
box.cam.dist = 16.2; box.pinLandOverlays(); out.far = look();
box.landOverlays(view, signs); out.again = els('dlbl').length;
box.landOverlays(view); out.none = els('dlbl').length;
process.stdout.write(JSON.stringify(out));
"""

SIGNS_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const N = 12, rows = [], plots = [];
const DIST = (x, z) => (x >= 4 ? (z >= 4 ? 'house' : z <= -4 ? 'shop' : '') : x <= -4 ? (z >= 4 ? 'tower' : z <= -4 ? 'workshop' : 'library') : '');
for (let z = -N; z <= N; z++) {
  let row = '';
  for (let x = -N; x <= N; x++) {
    let c = Math.hypot(x + .5, z + .5) > 11.2 ? '.' : 'g';
    if (c === 'g' && (x === 2 || z === 2 || Math.abs(x) === 7 || Math.abs(z) === 7)) c = 'r';
    if (c === 'g' && (x === 8 || x === -8 || z === 8 || z === -8) && DIST(x, z)) { c = 'P'; plots.push({ x, z, d: DIST(x, z) }); }
    if ((x === -1 || x === 0) && (z === -1 || z === 0)) c = 'H';
    row += c;
  }
  rows.push(row);
}
const view = { cell: 26, x0: -N, z0: -N, w: 2 * N + 1, h: 2 * N + 1, rows, territories: [], links: [] };
const box = { Math, JSON, console, occupied: new Map(), blocked: new Set(), map: view, shows: new Map(), performance: { now: () => 0 } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const out = { plots };
for (const [name, t] of Object.entries(cases)) {
  t.plots = plots;
  view.territories = [t];
  out[name] = box.systemsDecor(t, view).filter(i => i.kind === 'knowledge' && i.key === 'roads/road-sign-street');
}
process.stdout.write(JSON.stringify(out));
"""


class TestDistrictLabels(unittest.TestCase):
    NAMES = {"zh": {"house": "住宅区", "shop": "商业街", "tower": "测试区", "workshop": "工坊区", "library": "图书馆区"},
             "en": {"house": "Homes", "shop": "Shops", "tower": "Tests", "workshop": "Workshops", "library": "Library"}}

    def test_names_both_languages(self):
        t = tp.js_value(tp.const_object("TEXT"))
        for lang, names in self.NAMES.items():
            for d, name in names.items():
                with self.subTest(lang=lang, d=d):
                    self.assertEqual(t[lang].get("district." + d), name)

    def overlays(self):
        if "dlbl" not in _CACHE:
            view = {"territories": [{"id": "t", "name": "shop", "cx": 0, "cz": 0, "size": .4, "era": "town"}]}
            fns = need("landOverlays", "pinLandOverlays", "ovEl", "setText", "pin")
            fns += "\n" + tp.page_fns(optional=("eraShown", "terrOf", "showOf"))
            prelude = tp.constants_prelude() + "\n" + tp.consts("DCOL")
            _CACHE["dlbl"] = tp.run_node(DLBL_JS, {"prelude": prelude, "fns": fns, "view": view})
        return _CACHE["dlbl"]

    def test_one_label_per_sign(self):
        r = self.overlays()
        self.assertEqual(r["made"]["dlbl"], ["住宅区", "商业街", "图书馆区"])
        self.assertEqual(r["made"]["lbl"], 1, "the territory label stays one .lbl")
        self.assertEqual(r["again"], 3, "labels multiplied on a rebuild")
        self.assertEqual(r["none"], 0)

    def test_colour_bar(self):
        dcol = tp.js_value(tp.const_object("DCOL"))
        self.assertEqual([c.strip() if c else c for c in self.overlays()["made"]["bars"]],
                         [dcol["house"], dcol["shop"], dcol["library"]])

    def test_close_only(self):
        r = self.overlays()
        for name in ("close", "closest"):
            with self.subTest(zoom=name):
                self.assertEqual(r[name], [{"far": False, "hidden": False}] * 3)
        for name in ("dflt", "far"):
            with self.subTest(zoom=name):
                self.assertTrue(all(x["far"] for x in r[name]), r[name])

    def test_style(self):
        css = tp.style()
        rule = re.search(r"\.dlbl\s*\{([^}]*)\}", css)
        self.assertIsNotNone(rule, ".dlbl style missing")
        size = re.search(r"(\d+(?:\.\d+)?)px", re.search(r"font:[^;]*", rule.group(1)).group(0) if "font:" in rule.group(1) else rule.group(1))
        self.assertIsNotNone(size)
        self.assertLess(float(size.group(1)), 12, "quieter than the 12px territory label")
        self.assertIn("transition", rule.group(1))
        self.assertIn("opacity", rule.group(1))
        self.assertRegex(css, r"\.dlbl\.far\s*\{[^}]*opacity:\s*0")

    def test_buildland_passes_signs(self):
        self.assertRegex(tp.function_source("buildLand") or "", r"landOverlays\(view,\s*\w+")

    def signs(self):
        if "signs" not in _CACHE:
            def terr(state):
                bal = {k: {"state": "healthy" if k == "build" else "missing", "value": 1, "n": 1, "text": ""}
                       for k in tp.KINDS}
                bal["knowledge"] = {"state": state, "value": 1, "n": 1, "text": ""}
                return {"id": "t", "name": "shop", "cx": 0, "cz": 0, "open": 8, "size": .7, "lines": 9000,
                        "era": "town", "terrain": "grassland", "balance": bal, "next": [], "buildings": []}
            fns = tp.page_fns("systemsDecor", "hallDecor",
                              optional=("tileAt", "walkable", "eraShown", "showOf", "eraLook", "frontOf", "sr", "terrOf"))
            prelude = tp.constants_prelude() + "\n" + tp.consts("ERA_LOOK")
            _CACHE["signs"] = tp.run_node(SIGNS_JS, {"prelude": prelude, "fns": fns,
                                                     "cases": {"healthy": terr("healthy"), "low": terr("low")}})
        return _CACHE["signs"]

    def test_one_sign_per_district_at_its_district(self):
        r = self.signs()
        plots = r["plots"]
        want = sorted({p["d"] for p in plots})
        self.assertEqual(sorted(str(s.get("d")) for s in r["healthy"]), want)
        for s in r["healthy"]:
            with self.subTest(d=s.get("d")):
                near = min(max(abs(p["x"] + .5 - s["x"]), abs(p["z"] + .5 - s["z"])) for p in plots if p["d"] == s["d"])
                self.assertLessEqual(near, 3.5, "the sign is not at its district")

    def test_low_has_one(self):
        r = self.signs()
        self.assertEqual([s.get("d") for s in r["low"]], [r["plots"][0]["d"]])


if __name__ == "__main__":
    unittest.main()
