"""Failing tests for bin/agent-city.html and bin/agent-city-assets/.

The page is the approved 3D mock (mock/agent-city-3d-mock.html) turned into
the real thing: it reads live agent events from the city server. Every 3D
model is a ready-made CC0 Kenney model; nothing is modelled by hand. These
tests pin what a screenshot cannot show: it runs offline, stays cheap, and
speaks the server's event names. The main manager drives it in a headless
browser for the rest.

CONTRACT

  bin/agent-city.html
    A full HTML document (<!doctype html>) with <title>Agent City</title>.
    <link rel="icon" href="data:,"> so the browser never asks for /favicon.ico.
    Fully offline: no http:// or https:// URL anywhere (no web fonts, no CDN).
    Loads three.js and its loaders from the server, in this order, each URL
    versioned (Balance: the server fills in __CITY_ASSET_V__):
      <script src="assets/vendor/three.min.js?v=__CITY_ASSET_V__">
      <script src="assets/vendor/GLTFLoader.js?v=__CITY_ASSET_V__">
      <script src="assets/vendor/SkeletonUtils.js?v=__CITY_ASSET_V__">
    const ASSET = 'assets/', const ASSET_V = '__CITY_ASSET_V__' and a const
    MODELS = [...] list of '<pack>/<name>' entries (names unique across
    packs); each is loaded from ASSET + entry + '.glb?v=' + ASSET_V.
    Live mode: new EventSource('/events').
    Demo mode (the mock's fake agents) when location.hash is '#demo' or the page
    is opened as a file:// URL. Live mode never runs the fake agents.
    Handles snapshot spawn tool stuck answer done leave gov, each as a
    `case '<type>'` in one switch. Knows role 'other'.
    Cheap:
      const FRAME_MS = 33        at most about 30 frames a second
      const IDLE_FRAME_MS = 100  about 10 a second when nothing moves
      const MAX_CITIZENS = 40, MAX_LOG = 40, MAX_FLOATERS = 80, each used
      static scenery drawn with THREE.InstancedMesh
    Its <script> passes `node --check`.

  Cleanup (approved mock: mock/city-ui-cleanup-mock.html). A real agent work
  view: real time only, less clutter. Page text stays Chinese (lang="zh-CN").
    Gone, markup and JS both: the intro card (#intro), the legend card
      (怎么看这座城), the credits card (素材来源), the speed buttons
      ([data-speed]), the pause button (#play and its icons/label), the drag
      hint (#hint-drag, hideHint), the separator #spawn-sep. No `speed` or
      `paused` in the script, no keydown/keyup/keypress listener.
    Kept: the status counts 干活 找总督 休息 建成, the clock (#clock), the
      demo-only spawn control (#spawn-group, hidden outside demo), the
      demo-only detail buttons (data-act stuck/done/leave behind DEMO ?), the
      four camera buttons #zin #zout #rot #zfit and nothing else there, the
      one-column layout under @media (max-width: 960px).
    People walk at 1/3 of the old speed: move(c, dt) goes 1.9/3 per second,
      2.3/3 in state 'to_hall' (the sprint). anim(v, name, once) sets the
      action's time scale to 1/3 for 'walk' and 'sprint' and back to 1 for any
      other clip, so feet match the ground. Pets (petAnim, updatePets with
      .45 * dt) unchanged.
    No frame around the city: no .stage rule sets a border, a border-radius
      or the var(--sky) background; the land sits on the page.
    Camera: new THREE.PerspectiveCamera(FOV, ...) with const FOV = 40, no
      OrthographicCamera. cam = {az, el, dist, tx, tz} in scene coordinates.
      Growth: the world group is moved so the middle of the land's map is
      scene (0, 0); top-level `let land = {hx, hz}` = half the map's width
      and height in tiles (w / 2, h / 2), set whenever the world changes;
      top-level `let home = {x, z}` = scene position of the town hall the
      default view looks at (the governor's territory, else the first).
      Constants: EL_MIN = 15°, EL_MAX = 60°, EL_DEFAULT = 30° (radians,
      Math.PI allowed), DIST_MIN <= 3.5 (street level), DIST_DEFAULT,
      TARGET_Y, CAM_CLEAR, LIFT_MAX = 10°, FADE_OPACITY = .3.
      distMax(): the zoom-out limit for the stage size W x H and the current
      tilt, the same from every angle az (so auto-rotation never changes it).
      At distMax() the whole land (scene x -hx..hx, z -hz..hz, y
      -1.05..0) stays fully inside the stage from every angle, sits in the
      middle, and a square land fills about 80% of it on its tighter side
      at the widest angle (.7 to .9). May use only W, H, cam.el, FOV,
      DIST_MIN, land, Math, clamp, and the helpers landSpread (or
      islandSpread) and centreHeight if present. updateCamera() keeps
      cam.dist <= distMax(); tilting while fully zoomed out stays fully out.
      camTarget() -> [x, y, z]: the point the camera looks at: (tx,
      TARGET_Y, tz) up to dist 12, then drawn smoothly to the land's middle
      (x 0, z 0, at the height that centres the land), reached at
      distMax().
      resetCam(): tilt 30°, target within 3.5 of home, dist <= 14,
      phone (W < 560) not closer than wide.
      updateCamera(): camera on the sphere around camTarget(), at dist, tilt camLift(), direction az (x = tx + dist cos(el)
      sin(az), z = tz + dist cos(el) cos(az)); lookAt the target. It may raise
      the camera, never let it sit below heightAt(x, z) + 0.1 within 0.25 of
      its position, or below the ground. heightAt(x, z) = top of whatever
      stands on that scene tile (0 on open ground); the test replaces it with
      a stub. updateCamera may call only heightAt, camLift, camTarget,
      distMax, aroundH, clamp and Math.
      camLift(): the tilt used this frame = cam.el + camLiftNow (a top-level
      `let camLiftNow = 0`). The lift wanted is what clears the tallest thing
      between target and camera, capped at LIFT_MAX, and 0 while drag or
      pinch is set; camLiftNow eases toward it (at most about a fifth of the
      way per frame), so the view never jumps.
      viewBlockers(el) -> Set of scene tile keys 'x,z' (Math.floor) whose
      heightAt stands above the view line from camTarget() to the camera at
      tilt el (samples from 0.6 out to the camera).
      fadeables: top-level array of {g, tiles}: every town hall and its
      flag (its four scene tiles, pushed in buildLand), every building (its
      tile, pushed in makeBuilding). Buildings are permanent: no
      removeBuilding.
      applyFade(blocked): every mesh under a fadeable whose tiles meet
      blocked gets a cached faded clone of its own material (transparent,
      opacity x FADE_OPACITY, depthWrite false, same clippingPlanes array,
      userData.fadeSrc = the source; the cache, if any, is a top-level
      WeakMap named fadedMats); others get their source back. Never
      changes a shared material, never fades twice. frame() calls
      applyFade(viewBlockers(cam.el + camLiftNow)) after updateCamera().
      Drag up/down: cam.el = clamp(..., EL_MIN, EL_MAX). +/−, wheel, pinch:
      cam.dist clamped with DIST_MIN, distMax() on the same line.
      toScreen() hides points behind the camera (projected z > 1).
      Depth: PerspectiveCamera(FOV, 1, near, far) with number literals,
      near >= 0.2, far <= 200, far/near <= 1000. The edge cliff blocks share
      a plane with path and river floors: instanced('cliff_block_rock', ...,
      { ..., behind: true }) and instanced() gives such meshes a cloned
      material with polygonOffset = true, polygonOffsetFactor >= 1.
      busy() is true while auto-rotation turns the camera (so live mode with
      zero agents runs at FRAME_MS like demo); false only under reduced
      motion with nothing else moving.
      autoRotate(now, dt), called from frame(), turns only cam.az, one full
      turn per 300 s, and never stops (owner 2026-09-25, replaces the pause
      on touch): clicks, drags, pinch/zoom, panels and the "?" panel do not
      pause it; a drag adds to the angle while it keeps turning. Nothing
      under RM (reduced motion). No button for it.
    Right column <aside class="panel" id="panel"> holds exactly four cards,
      default order detail, balance, citizens, log (Balance added 城市平衡):
        <section class="card" data-card="detail|balance|citizens|log">
          <h2 class="card-head"><button type="button" aria-expanded="true"
            aria-controls="<body id>">… 详情 | 城市平衡 | 市民 | 动态 …</button></h2>
          one element with class card-body: #detail, #balance, #roster, #log
        </section>
      The 详情 header is static markup; the script never writes an <h2>.
      Click a header: the card gets/loses class `collapsed` (CSS hides its
      .card-body), the button's aria-expanded follows. Drag a header with
      pointer events (6 px threshold, .card-head has touch-action:none): the
      card moves among the panel's cards by comparing the pointer's Y with the
      other cards' midpoints (getBoundingClientRect/offsetTop); it never leaves
      #panel; the click that ends a drag does not toggle.
      Order and collapsed state saved on every change and restored on load:
      localStorage key 'agent-city-cards' = JSON {order: [...], collapsed:
      [...]}. Unknown names ignored, missing cards keep default order. Every
      localStorage access inside try/catch; the page works when storage throws.
      This code is its own section: a comment line starting
      `/* ---------- right column` up to the next `/* ----------` line. It
      may use $, clamp and CARD_KEY from outside; the test runs it in node
      with a small fake DOM.

  Interaction (approved mock: mock/city-interact-mock.html; the server side
  is pinned in tests/test_agent_city_interact.py). Everything from Cleanup
  stays (3D city, cards, camera).
    <meta name="city-token" content="__CITY_TOKEN__"> in <head>; the server
      swaps in its token. The script reads it from that meta tag (TOKEN).
    Handles `case 'ask'`, `case 'ask_phase'` and `case 'ask_closed'` in the
      same switch, and the snapshot's `asks` list.
    `case 'answer'`: shows ev.answer when it is a non-empty string, else
      '已回答'. Live mode never invents text: the `case 'answer'` code has no
      '批了' and no '不行'. Demo data may keep its own made-up answers.
    askLine(ev, name): top-level pure function (no DOM, no other globals) ->
      the Chinese log line for one ask / ask_phase / ask_closed event, name =
      the asker's task. Who: 总督 (governor), 你 (owner), 终端 (terminal).
      Always the real text; '已回答' when an answer's text is "". A deny
      without a reason shows no 理由：.
    The "?" panel: <div class="ask-panel" id="ask" role="dialog"
      aria-labelledby="ask-title" hidden>, inside #stage (over the city),
      never inside the right column. Question: the exact questions and
      options, a free text per question, 发送回答. Permission: tool, command
      or path, the agent's own description, folder; 批准 and 拒绝, an optional
      reason. .btn.ok and .btn.no: white-space:nowrap and a min-width. After
      a close from any side the form is gone and a .closed line says who and
      when; another side first: 晚了一步.
    Decisions: fetch('/api/decide') POST, JSON, header 'X-City-Token'. A 409
      shows the closed state. The page never calls /api/gov/ and never
      offers the governor approving (no 总督批准). Any other failure (network,
      400, 403) is said in the panel, never swallowed.
    askClosedLine(view): top-level; may use only esc; view.closed = {by,
      verb, text, reason, at}. Verb closed (the terminal took it, or a 409
      whose details are not known yet) is neutral: never 批准, 拒绝 or 回答.
      Quotes around real text are “ ” as in the rest of the page.
    A red "?" (.qm button with data-open) above an agent whose ask is with
      the owner. renderStats adds <button id="next"> 等你 <n>, which opens the
      oldest. Phone: the @media (max-width: 960px) block has an .ask-panel rule.
    No CSS selector starts with a bare .ask: the older .bub.ask, .pill.ask and
      `.log .ask` rules (red bubble, pill, log line) stay exactly as they are.
    One record per ask in live mode: the log lines for questions and
      permissions come from ask / ask_phase / ask_closed only. The live
      `case 'stuck'` and `case 'answer'` write no log line (their log calls
      are behind DEMO), and never say 问总督 for a permission. The governor
      speaks (say(gov, ...)) and gov.answered counts only in demo or on an
      ask_closed by the governor, with its real text.
    stuckText(ev) -> the bubble over a stuck citizen: the question text, or
      要权限：<tool> for a permission; never 可以用 … 吗 or 问总督.
    citizenStatus(c) -> [pill class, text] for the roster, from c.state and
      c.askKind ('question' | 'permission' | '') and c.askPhase ('governor' |
      'owner' | ''). Permission on the way or at the hall: 等你批. Question
      with the governor: 在问总督; with the owner: 等你回答. Else STATE's words.
    Governor presence: `case 'governors'` (count of governors, also in the
      snapshot). Count 0 in live mode: govPillText() says 不在.
    Snapshot = live. applyAsk(c, ask): top-level; may use only stuckText.
      ask = an ask view (or null) -> sets c.askKind, c.askPhase, c.stuck and
      c.question (stuckText of the ask's tool and first question), or clears
      the ask fields for null. `case 'ask'` and `case 'snapshot'` both use it;
      the snapshot first clears every citizen's ask fields (a reconnect may
      find the ask closed), then applies each open ask to its agent. A page
      opened while a permission waits shows what an open page shows.
    citizenStatus(c, governors): with governors === 0 it never says 问总督.
    The 等你 N chip takes real mouse clicks: no CSS rule that can match the
      chip (its tag, classes, id) outside :disabled, nor one matching its
      ancestors (header.bar, #stats.stats), sets pointer-events:none.
      (A class shared with the 3D countdown chip once did.)

  Growth (approved mock: mock/city-growth-mock.html; the world itself is
  pinned in tests/test_agent_city_world.py). The fixed 12 x 12 island is
  gone (no PLOTS, GX1, BRIDGE_X, demolishOldest, removeBuilding): the page
  draws the world view the server sends.
    Handles `case 'world'` (ev.world: a new view, redraw the land) and
      `case 'build'` (ev.terr, ev.plot, ev.btype, ev.x, ev.z, ev.by, ev.id:
      the agent walks to world tile (ev.x, ev.z) and builds a ev.btype
      there) in the same switch; the snapshot's world and notice (a notice
      goes to the page log). `case 'spawn'` puts the agent in ev.terr.
    const DEMO_WORLD = <the JSON printed by python3 bin/agent_city.py
      demo-world>, exactly: #demo draws it, same look as live.
    let map = the current view. tileAt(x, z) -> its char at world tile
      (x, z), ' ' outside. walkable(x, z): true for . g r t B b when the
      tile is not in `occupied` (Map 'x,z' -> building) or `blocked` (Set);
      false for void, river, ravine, pass, forest belt, sea, hall and plots.
      findPath(sx, sz, tx, tz) as before, on world tiles: over a river only
      by a bridge.
    const BUILD_MODELS = {house, shop, tower, workshop, library}: each a
      non-empty list of model names (the part after '/') from MODELS.
    const TYPE_ZH = {house:'住宅', shop:'商店', tower:'测试塔',
      workshop:'工坊', library:'图书馆'}.
    const TERRAIN_LOOK = {grassland, mountain, desert, forest, coast}: each
      {ground: '#rrggbb', path: '#rrggbb', plants: [model names from
      MODELS]}. Desert plants include a cactus, mountain a pine, coast a
      palm; coast paths are sand (not the grassland path colour); desert
      ground is not grassland ground. Terrain changes the look only.
    MODELS has a bridge, a river piece and a rock or cliff (gaps).
    buildLand() places a town hall ('building-j') for every territory.
  E2E bounce (real Chrome, 2026-09-24): the first page drew floating tiles.
    Ground, water and roads: one smooth ground mesh, smooth water, smooth
      lanes (city-land replaced the exact 1 x 1 tile squares): the contract
      is in tests/test_agent_city_land.py.
    No Kenney cliff_block model at all (brown earth sides).
    Every .glb loads without GLTFLoader warnings: no KHR_texture_transform
      (bake the transform into the UVs, or use a model without it).
    Zoom: zoomStep(k) (k = +1 out, -1 in) is what #zout, #zin call; from
      the default view, 6 steps out reach distMax() on a land of 5
      territories. At the zoom-out limit the lift is 0 (tall buildings by
      the middle must not tilt the view off the land).
    buildLand() calls updateHome(): ⛶ looks at a town hall, never at the
      empty middle of the land. home = the square just south of that hall
      (1.5 to 3 tiles in front of its centre), so the hall itself never
      stands in the view line and fades.
  Second E2E pass (headless screenshots): the ground did not show at all.
    First view: when the first world arrives the camera goes home
      (resetCam()) unless the user already moved it; live and demo both
      open on a town hall, never on the empty middle. Only the first: a
      one-time flag (if (!flag ...) { flag = true; resetCam(); }), so a
      later world never snaps the camera back.
    Day 0 is bare: hallDecor(t, view) -> the decorations around territory
      t's hall as [{key, x, z}] (world tiles): [] while t.open is 0 (no
      plot yet); later a fountain and lamps, each on a 'g' tile (never a
      road, plot or the hall). buildLand places exactly these; pets and
      other life come only to a territory with open plots.
    restSlotsFor(t) -> the rest spots near territory t's town hall ({x, y,
      pose, by}, world tiles), each on a walkable tile: never on a plot, the
      hall, water or the void, so nobody rests inside a building. At least 3
      when the tiles around the hall allow it.

  bin/agent-city-assets/
    vendor/three.min.js, vendor/GLTFLoader.js, vendor/SkeletonUtils.js
      (three.js r128, MIT, the licence header kept)
    <pack>/<name>.glb for every MODELS entry, and nothing unused
    <pack>/Textures/*.png for every texture those models name
    <pack>/License.txt for every pack, each saying CC0
    Everything together at most 8 MB (Balance raised it from 6 MB to 7 MB,
    city-people to 8 MB for the KayKit packs).
"""

import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "bin", "agent-city.html")
ASSETS = os.path.join(ROOT, "bin", "agent-city-assets")


def page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


def inline_script():
    return "\n".join(re.findall(r"<script>(.*?)</script>", page(), re.S))


def models():
    block = re.search(r"const MODELS = \[(.*?)\];", inline_script(), re.S)
    return re.findall(r"'([a-z][a-z\-]*/[A-Za-z0-9_\-]+)'", block.group(1)) if block else []


def glb_images(path):
    with open(path, "rb") as fh:
        data = fh.read()
    length = struct.unpack("<I", data[12:16])[0]
    doc = json.loads(data[20:20 + length])
    return [img["uri"] for img in doc.get("images", []) if "uri" in img]


class TestDocument(unittest.TestCase):
    def test_it_exists(self):
        self.assertTrue(os.path.exists(PAGE), "bin/agent-city.html is missing")

    def test_full_document_with_title(self):
        text = page()
        self.assertTrue(text.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn("<title>Agent City</title>", text)

    def test_no_favicon_request(self):
        self.assertIn('<link rel="icon" href="data:,">', page())

    def test_fully_offline(self):
        self.assertEqual(re.findall(r"https?://[^\s\"')<]+", page()), [])

    def test_vendor_scripts_in_order(self):
        srcs = re.findall(r'<script src="([^"]+)"', page())
        self.assertEqual(srcs, ["assets/vendor/three.min.js?v=__CITY_ASSET_V__",
                                "assets/vendor/GLTFLoader.js?v=__CITY_ASSET_V__",
                                "assets/vendor/SkeletonUtils.js?v=__CITY_ASSET_V__"])

    def test_script_parses(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(inline_script())
            path = fh.name
        try:
            result = subprocess.run([node, "--check", path], capture_output=True, text=True)
        finally:
            os.remove(path)
        self.assertEqual(result.returncode, 0, result.stderr)


class TestModes(unittest.TestCase):
    def test_live_mode_uses_the_event_stream(self):
        self.assertRegex(inline_script(), r"new EventSource\(\s*['\"]/events['\"]\s*\)")

    def test_demo_mode_is_behind_the_hash_or_a_file_url(self):
        text = inline_script()
        self.assertIn("'#demo'", text)
        self.assertIn("'file:'", text)

    def test_every_message_type_is_handled(self):
        text = inline_script()
        for kind in ("snapshot", "spawn", "tool", "stuck", "answer", "done", "leave", "gov", "world", "build"):
            with self.subTest(kind=kind):
                self.assertRegex(text, r"case\s+'%s'\s*:" % kind)

    def test_role_other_exists(self):
        self.assertRegex(inline_script(), r"['\"]?other['\"]?\s*:\s*\{")

    def test_assets_come_from_the_server(self):
        text = inline_script()
        self.assertIn("const ASSET = 'assets/'", text)
        self.assertIn("const ASSET_V = '__CITY_ASSET_V__'", text)
        self.assertRegex(function_source("loadAll") or "", r"ASSET \+ key \+ '\.glb\?v=' \+ ASSET_V")
        self.assertRegex(function_source("loadTex") or "", r"ASSET \+ path \+ '\?v=' \+ ASSET_V")
        self.assertGreater(len(models()), 20)
        names = [m.split("/")[1] for m in models()]
        self.assertEqual(sorted(set(n for n in names if names.count(n) > 1)), ["building-a", "building-b"],
                         "a model is found by its name alone: new names must be unique (commercial/industrial "
                         "building-a/-b were already shared before Balance)")


class TestCost(unittest.TestCase):
    def test_frame_caps(self):
        text = inline_script()
        self.assertRegex(text, r"const FRAME_MS = 33\b")
        self.assertRegex(text, r"const IDLE_FRAME_MS = 100\b")
        self.assertGreaterEqual(len(re.findall(r"\bFRAME_MS\b", text)), 2)
        self.assertGreaterEqual(len(re.findall(r"\bIDLE_FRAME_MS\b", text)), 2)

    def test_limits(self):
        text = inline_script()
        for name, value in (("MAX_CITIZENS", 40), ("MAX_LOG", 40), ("MAX_FLOATERS", 80)):
            with self.subTest(name=name):
                self.assertRegex(text, r"const %s = %d\b" % (name, value))
                self.assertGreaterEqual(len(re.findall(r"\b%s\b" % name, text)), 2,
                                        "%s is declared but never used" % name)

    def test_static_scenery_is_instanced(self):
        self.assertIn("new THREE.InstancedMesh", inline_script())


class TestAssets(unittest.TestCase):
    def test_vendor_scripts_are_three_r128_with_licence(self):
        for name in ("three.min.js", "GLTFLoader.js", "SkeletonUtils.js"):
            with self.subTest(name=name):
                path = os.path.join(ASSETS, "vendor", name)
                self.assertTrue(os.path.exists(path), path)
        with open(os.path.join(ASSETS, "vendor", "three.min.js"), encoding="utf-8") as fh:
            head = fh.read(400)
        self.assertIn("SPDX-License-Identifier: MIT", head)

    def test_every_model_is_there(self):
        for entry in models():
            with self.subTest(entry=entry):
                self.assertTrue(os.path.exists(os.path.join(ASSETS, entry + ".glb")))

    def test_no_unused_model(self):
        wanted = {e + ".glb" for e in models()}
        found = set()
        for folder, _, files in os.walk(ASSETS):
            for name in files:
                if name.endswith(".glb"):
                    found.add(os.path.relpath(os.path.join(folder, name), ASSETS))
        self.assertEqual(found - wanted, set())

    def test_every_texture_a_model_names_is_there(self):
        for entry in models():
            path = os.path.join(ASSETS, entry + ".glb")
            if not os.path.exists(path):
                continue
            for uri in glb_images(path):
                with self.subTest(entry=entry, uri=uri):
                    self.assertTrue(os.path.exists(os.path.join(os.path.dirname(path), uri)))

    def test_every_pack_has_its_cc0_licence(self):
        packs = {e.split("/")[0] for e in models()}
        self.assertTrue(packs)
        for pack in packs:
            with self.subTest(pack=pack):
                path = os.path.join(ASSETS, pack, "License.txt")
                self.assertTrue(os.path.exists(path), path)
                with open(path, encoding="utf-8", errors="replace") as fh:
                    self.assertIn("CC0", fh.read())

    def test_no_model_needs_an_unsupported_extension(self):
        """E2E bounce G5: 35 GLTFLoader warnings (KHR_texture_transform, custom UV sets)."""
        for folder, _, files in os.walk(ASSETS):
            for name in files:
                if not name.endswith(".glb"):
                    continue
                path = os.path.join(folder, name)
                with open(path, "rb") as fh:
                    data = fh.read()
                length = struct.unpack("<I", data[12:16])[0]
                doc = data[20:20 + length].decode("utf-8")
                with self.subTest(model=os.path.relpath(path, ASSETS)):
                    self.assertNotIn("KHR_texture_transform", doc)

    def test_size_budget(self):
        total = sum(os.path.getsize(os.path.join(folder, name))
                    for folder, _, files in os.walk(ASSETS) for name in files)
        self.assertLessEqual(total, 8 * 1024 * 1024, "assets are %.1f MB" % (total / 1048576))


# ---------------------------------------------------------------------------
# Cleanup: helpers
# ---------------------------------------------------------------------------

def markup():
    """The page without its <script> and <style> blocks."""
    return re.sub(r"<script[^>]*>.*?</script>|<style>.*?</style>", "", page(), flags=re.S)


def style():
    return "\n".join(re.findall(r"<style>(.*?)</style>", page(), re.S))


def function_source(name):
    """Source of the top-level `function name(...) {...}` in the inline script."""
    text = inline_script()
    m = re.search(r"^(?:async\s+)?function %s\s*\(" % re.escape(name), text, re.M)
    if not m:
        return None
    i = text.index("{", m.end())
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[m.start():j + 1]
    return None


def cards_section():
    """The right-column section: from its header comment to the next one."""
    text = inline_script()
    i = text.find("/* ---------- right column")
    if i < 0:
        return None
    j = text.find("/* ----------", i + 10)
    return text[i:j if j > 0 else len(text)]


def constants_prelude():
    """Every top-level `const NAME = <number or string>;` of the script."""
    out = []
    for name, value in re.findall(r"^const ([A-Z][A-Z0-9_]*) = ([^;\n]+);\s*$", inline_script(), re.M):
        if re.fullmatch(r"(?:[\d.\s/*+\-()]|Math\.PI)+|'[^'\\]*'", value.strip()):
            out.append("var %s = %s;" % (name, value.strip()))
    return "\n".join(out)


def cards():
    """[(name, inner html)] of the <section class="card" data-card=...> blocks."""
    return re.findall(r'<section class="card"[^>]*\bdata-card="([\w-]+)"[^>]*>(.*?)</section>',
                      markup(), re.S)


FAKE_DOM_JS = r"""
class CL {
  constructor(list){ this.s = new Set(list || []); }
  add(...c){ c.forEach(x => this.s.add(x)); }
  remove(...c){ c.forEach(x => this.s.delete(x)); }
  contains(c){ return this.s.has(c); }
  toggle(c, on){ if (on === undefined) on = !this.s.has(c); if (on) this.s.add(c); else this.s.delete(c); return !!on; }
}
const camel = s => s.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
function compound(el, c, root){
  if (c === ':scope') return el === root;
  const m = c.match(/^([a-z0-9]+)?((?:[.#][\w-]+|\[[^\]]+\])*)$/i);
  if (!m) throw new Error('fake DOM cannot parse selector part: ' + c);
  if (m[1] && el.tagName !== m[1].toUpperCase()) return false;
  for (const p of (m[2].match(/[.#][\w-]+|\[[^\]]+\]/g) || [])) {
    if (p[0] === '.') { if (!el.classList.contains(p.slice(1))) return false; }
    else if (p[0] === '#') { if (el.getAttribute('id') !== p.slice(1)) return false; }
    else {
      const a = p.slice(1, -1).match(/^([\w-]+)(?:="?([^"]*)"?)?$/);
      const v = el.getAttribute(a[1]);
      if (v === null || (a[2] !== undefined && v !== a[2])) return false;
    }
  }
  return true;
}
function parse(sel){
  const parts = [], toks = sel.trim().replace(/\s*>\s*/g, ' > ').split(/\s+/);
  let comb = null;
  for (const t of toks) { if (t === '>') { comb = '>'; continue; } parts.push({ comb: parts.length ? (comb || ' ') : null, c: t }); comb = null; }
  return parts;
}
function chain(el, parts, root){
  const k = parts.length - 1;
  if (!el.getAttribute || !compound(el, parts[k].c, root)) return false;
  if (k === 0) return true;
  const rest = parts.slice(0, k);
  if (parts[k].comb === '>') return !!el.parentNode && chain(el.parentNode, rest, root);
  for (let a = el.parentNode; a; a = a.parentNode) if (chain(a, rest, root)) return true;
  return false;
}
const matchAny = (el, sel, root) => sel.split(',').some(s => chain(el, parse(s), root));
class El {
  constructor(tag, cls, attrs){
    this.tagName = tag.toUpperCase(); this.classList = new CL(cls); this.attrs = Object.assign({}, attrs || {});
    this.dataset = {}; this.style = {}; this.children = []; this.parentNode = null; this.listeners = {}; this.textContent = ''; this._h = 30;
  }
  get parentElement(){ return this.parentNode; }
  get childNodes(){ return this.children; }
  get className(){ return [...this.classList.s].join(' '); }
  get id(){ return this.getAttribute('id') || ''; }
  setAttribute(k, v){ if (k.startsWith('data-')) this.dataset[camel(k.slice(5))] = String(v); else this.attrs[k] = String(v); }
  getAttribute(k){ if (k.startsWith('data-')) { const v = this.dataset[camel(k.slice(5))]; return v === undefined ? null : v; } return k in this.attrs ? this.attrs[k] : null; }
  hasAttribute(k){ return this.getAttribute(k) !== null; }
  removeAttribute(k){ if (k.startsWith('data-')) delete this.dataset[camel(k.slice(5))]; else delete this.attrs[k]; }
  append(...xs){ xs.forEach(x => this.insertBefore(x, null)); }
  prepend(...xs){ xs.reverse().forEach(x => this.insertBefore(x, this.children[0] || null)); }
  appendChild(x){ return this.insertBefore(x, null); }
  insertBefore(x, ref){
    if (ref && ref.parentNode !== this) throw new Error('insertBefore: ref is not a child');
    if (x.parentNode) x.parentNode._drop(x);
    if (ref) this.children.splice(this.children.indexOf(ref), 0, x); else this.children.push(x);
    x.parentNode = this; return x;
  }
  before(x){ this.parentNode.insertBefore(x, this); }
  after(x){ this.parentNode.insertBefore(x, this.nextElementSibling); }
  _drop(x){ const i = this.children.indexOf(x); if (i >= 0) this.children.splice(i, 1); x.parentNode = null; }
  remove(){ if (this.parentNode) this.parentNode._drop(this); }
  get firstElementChild(){ return this.children[0] || null; }
  get lastElementChild(){ return this.children[this.children.length - 1] || null; }
  get nextElementSibling(){ const p = this.parentNode; return p ? p.children[p.children.indexOf(this) + 1] || null : null; }
  get previousElementSibling(){ const p = this.parentNode; return p ? p.children[p.children.indexOf(this) - 1] || null : null; }
  get nextSibling(){ return this.nextElementSibling; }
  get previousSibling(){ return this.previousElementSibling; }
  matches(sel){ return matchAny(this, sel, this); }
  closest(sel){ for (let e = this; e && e.getAttribute; e = e.parentNode) if (matchAny(e, sel, e)) return e; return null; }
  querySelectorAll(sel){ const out = [], walk = e => { for (const c of e.children) { if (matchAny(c, sel, this)) out.push(c); walk(c); } }; walk(this); return out; }
  querySelector(sel){ return this.querySelectorAll(sel)[0] || null; }
  getElementById(id){ return this.querySelector('#' + id); }
  contains(x){ for (let e = x; e; e = e.parentNode) if (e === this) return true; return false; }
  addEventListener(t, fn){ (this.listeners[t] = this.listeners[t] || []).push(fn); }
  removeEventListener(t, fn){ const l = this.listeners[t] || []; const i = l.indexOf(fn); if (i >= 0) l.splice(i, 1); }
  setPointerCapture(){} releasePointerCapture(){} hasPointerCapture(){ return false; } focus(){} blur(){}
  get offsetHeight(){ return this._h; }
  get offsetWidth(){ return 360; }
  get offsetTop(){ const p = this.parentNode; if (!p) return 0; if (p.getAttribute('id') === 'panel') return 1000 + p.children.indexOf(this) * 110; return p.offsetTop; }
  get offsetLeft(){ return 1100; }
  get scrollTop(){ return 0; } set scrollTop(v){}
  getBoundingClientRect(){ const t = this.offsetTop - 1000 + 100, h = this._h; return { top: t, bottom: t + h, y: t, height: h, left: 1100, right: 1460, x: 1100, width: 360 }; }
}
"""

HARNESS_JS = FAKE_DOM_JS + r"""
const fs = require('fs'), vm = require('vm');
const { prelude, section } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const KEY = 'agent-city-cards';
const tick = () => new Promise(r => setTimeout(r, 5));

function world(stored, mode){
  const doc = new El('html'), body = new El('body'), stage = new El('div', ['stage'], { id: 'stage' });
  doc.appendChild(body); body.appendChild(stage);
  const panel = new El('aside', ['panel'], { id: 'panel' }); body.appendChild(panel);
  for (const [name, zh, bodyId, tag] of [['detail', '详情', 'detail', 'div'], ['citizens', '市民', 'roster', 'ul'], ['log', '动态', 'log', 'ol']]) {
    const sec = new El('section', ['card']); sec.setAttribute('data-card', name); sec._h = 100;
    const h2 = new El('h2', ['card-head']);
    const btn = new El('button', [], { type: 'button', 'aria-expanded': 'true', 'aria-controls': bodyId }); btn.textContent = zh;
    h2.appendChild(btn); sec.appendChild(h2); sec.appendChild(new El(tag, ['card-body'], { id: bodyId }));
    panel.appendChild(sec);
  }
  const mem = {}; if (stored !== undefined) mem[KEY] = stored;
  const store = {
    getItem(k){ if (mode === 'getthrow') throw new Error('SecurityError'); return k in mem ? mem[k] : null; },
    setItem(k, v){ if (mode === 'setthrow') throw new Error('QuotaExceededError'); mem[k] = String(v); },
    removeItem(k){ delete mem[k]; }, clear(){ for (const k in mem) delete mem[k]; },
  };
  const errors = [], winL = {};
  const box = {
    console, setTimeout, clearTimeout, JSON, Math, Map, Set, Array, Object, String, Number, Boolean, Error, Promise,
    performance: { now: () => Date.now() },
    requestAnimationFrame: fn => setTimeout(() => fn(Date.now()), 0), cancelAnimationFrame: clearTimeout,
    CSS: { escape: s => String(s) }, RM: false,
    $: s => doc.querySelector(s), clamp: (v, a, b) => Math.max(a, Math.min(b, v)),
    addEventListener(t, fn){ (winL[t] = winL[t] || []).push(fn); }, removeEventListener(t, fn){ const l = winL[t] || []; const i = l.indexOf(fn); if (i >= 0) l.splice(i, 1); },
    innerWidth: 1500, innerHeight: 900,
  };
  doc.body = body; doc.documentElement = doc;
  box.document = doc; box.window = box;
  Object.defineProperty(box, 'localStorage', { get(){ if (mode === 'throw') throw new Error('SecurityError: storage is off'); return store; } });
  vm.createContext(box);
  try { vm.runInContext(prelude + '\n' + section, box); } catch (e) { errors.push('load: ' + e.message); }
  const card = n => panel.children.find(c => c.getAttribute('data-card') === n);
  const btn = n => card(n).querySelector('button');
  function fire(type, target, y, x){
    const ev = { type, target, clientX: x === undefined ? 1200 : x, clientY: y, pageX: x === undefined ? 1200 : x, pageY: y,
      pointerId: 7, pointerType: 'mouse', isPrimary: true, button: 0, buttons: type === 'pointerup' || type === 'click' ? 0 : 1,
      detail: 1, defaultPrevented: false, _stop: false,
      preventDefault(){ this.defaultPrevented = true; }, stopPropagation(){ this._stop = true; }, stopImmediatePropagation(){ this._stop = true; } };
    const path = []; for (let e = target; e; e = e.parentNode) path.push(e);
    for (const node of path.concat([{ listeners: winL }])) {
      for (const fn of (node.listeners[type] || []).slice()) {
        ev.currentTarget = node;
        try { fn.call(node, ev); } catch (e) { errors.push(type + ': ' + e.message); }
      }
      if (ev._stop) break;
    }
  }
  const click = n => { const b = btn(n), y = b.getBoundingClientRect().top + 10; fire('pointerdown', b, y); fire('pointerup', b, y); fire('click', b, y); };
  async function drag(n, ys, x){
    const b = btn(n); let y = b.getBoundingClientRect().top + 10;
    fire('pointerdown', b, y); await tick();
    for (const to of ys) { fire('pointermove', b, to, x); y = to; await tick(); }
    fire('pointerup', b, y, x); fire('click', b, y, x);
  }
  const state = () => ({
    order: panel.children.map(c => c.getAttribute('data-card')),
    collapsed: panel.children.filter(c => c.classList.contains('collapsed')).map(c => c.getAttribute('data-card')),
    expanded: Object.fromEntries(panel.children.map(c => [c.getAttribute('data-card'), c.querySelector('button').getAttribute('aria-expanded')])),
    offset: panel.children.filter(c => ['transform', 'top', 'translate'].some(k => c.style[k] && !/^(none|0(px)?|translateY\(0(px)?\))$/.test(c.style[k]))).map(c => c.getAttribute('data-card')),
    inPanel: panel.children.length === 3 && stage.children.length === 0 && body.children.length === 2,
    stored: mem[KEY] === undefined ? null : mem[KEY],
    errors: errors.slice(),
  });
  return { click, drag, state, tick };
}

(async () => {
  const out = {};
  let w = world();
  out.fresh = w.state();
  w.click('citizens'); await w.tick(); out.collapsed = w.state();
  w.click('citizens'); await w.tick(); out.reopened = w.state();
  await w.drag('log', [225, 215, 190, 160, 130, 100, 70, 40, 15]); out.dragged = w.state();
  await w.tick(); w.click('log'); await w.tick(); out.clickAfterDrag = w.state();
  await w.drag('detail', [300, 600, 1200, 5000], 3000); out.farDrag = w.state();

  w = world(); await w.drag('log', [310, 290, 270, 250]); out.midDrop = w.state();

  w = world(JSON.stringify({ order: ['log', 'detail', 'bogus'], collapsed: ['citizens', 'nope'] })); out.restored = w.state();
  w = world('{not json'); out.garbage = w.state();
  w = world('[1,2]'); out.wrongShape1 = w.state();
  w = world(JSON.stringify({ order: 'log', collapsed: 5 })); out.wrongShape2 = w.state();

  w = world(undefined, 'throw'); out.throwLoad = w.state();
  w.click('detail'); await w.tick(); out.throwClick = w.state();
  await w.drag('log', [225, 190, 150, 110, 70, 30, 10]); out.throwDrag = w.state();

  w = world(undefined, 'setthrow'); w.click('log'); await w.tick(); out.setThrow = w.state();
  w = world(undefined, 'getthrow'); out.getThrow = w.state();
  process.stdout.write(JSON.stringify(out));
})().catch(e => { process.stdout.write(JSON.stringify({ fatal: String(e && e.stack || e) })); });
"""

UNIT_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
function ctx(extra){ const box = Object.assign({ Math, JSON, console, performance: { now: () => 0 } }, extra); vm.createContext(box); vm.runInContext(prelude + '\n' + fns, box); return box; }

// walking
{
  const box = ctx({ onArrive(){} });
  out.walk = {};
  for (const state of ['to_plot', 'back', 'to_rest', 'leaving', 'to_hall']) {
    const c = { x: 0, y: 0, path: [[10, 0]], state, walkT: 0, stateT: 0 };
    box.move(c, 1);
    out.walk[state] = c.x;
  }
}
// animation time scale
function fakeMixer(){
  const actions = new Map();
  return { timeScale: 1, actions, clipAction(clip){
    if (!actions.has(clip.name)) {
      const a = { clip, timeScale: 1, weight: 1, loop: null, clampWhenFinished: false };
      for (const m of ['reset', 'play', 'stop', 'fadeIn', 'fadeOut', 'crossFadeFrom', 'crossFadeTo', 'setEffectiveWeight', 'startAt', 'halt', 'warp', 'stopWarping', 'stopFading'])
        a[m] = function(){ return this; };
      a.setLoop = function(l){ this.loop = l; return this; };
      a.setEffectiveTimeScale = function(t){ this.timeScale = t; return this; };
      a.getEffectiveTimeScale = function(){ return this.timeScale; };
      a.setDuration = function(d){ this.timeScale = this.clip.duration / d; return this; };
      actions.set(clip.name, a);
    }
    return actions.get(clip.name);
  } };
}
const THREE = { LoopOnce: 2200, LoopRepeat: 2201, LoopPingPong: 2202,
  AnimationClip: { findByName: (clips, name) => clips.find(c => c.name === name) || null } };
const clips = ['walk', 'sprint', 'idle', 'interact-right', 'emote-yes', 'jump', 'sit', 'eat', 'interact-left'].map(name => ({ name, duration: 1 }));
{
  const box = ctx({ THREE, lib: { k: { clips } } });
  const v = { key: 'k', mixer: fakeMixer(), cur: null, action: null };
  out.anim = [];
  for (const name of ['walk', 'interact-right', 'sprint', 'idle', 'walk', 'emote-yes', 'sprint', 'sit']) {
    box.anim(v, name, name === 'emote-yes');
    out.anim.push([name, v.mixer.clipAction({ name, duration: 1 }).timeScale * v.mixer.timeScale]);
  }
  const p = { key: 'k', mixer: fakeMixer(), cur: null, action: null };
  out.pet = [];
  for (const name of ['walk', 'eat', 'walk']) {
    box.petAnim(p, name);
    out.pet.push([name, p.mixer.clipAction({ name, duration: 1 }).timeScale * p.mixer.timeScale]);
  }
}
// camera: default view and limits
{
  const box = ctx({ cam: { az: 0, el: 0, dist: 1, tx: -5, tz: -5 }, W: 1200, H: 800, home: { x: 4, z: -3 }, land: { hx: 13, hz: 13 } });
  box.resetCam(); out.viewWide = Object.assign({}, box.cam);
  box.W = 400; box.H = 440; box.resetCam(); out.viewPhone = Object.assign({}, box.cam);
  out.consts = { FOV: box.FOV, EL_MIN: box.EL_MIN, EL_MAX: box.EL_MAX, DIST_MIN: box.DIST_MIN, LIFT_MAX: box.LIFT_MAX, FADE_OPACITY: box.FADE_OPACITY };
}
// camera pose: orbits the target at the user's tilt; never inside the ground or a building
{
  const camera = { aspect: 1, fov: 40, look: null, updateProjectionMatrix(){},
    position: { x: 0, y: 0, z: 0, set(x, y, z){ this.x = x; this.y = y; this.z = z; return this; } },
    lookAt(x, y, z){ this.look = typeof x === 'object' ? [x.x, x.y, x.z] : [x, y, z]; } };
  const box = ctx({ camera, cam: { az: 0, el: .5, dist: 9, tx: 0, tz: 0 }, W: 1200, H: 800,
    clamp: (v, a, b) => Math.max(a, Math.min(b, v)), drag: null, pinch: null, camLiftNow: 0, fadeables: [] });
  let ground = () => 0;
  box.heightAt = (x, z) => ground(x, z);
  const pose = (c) => { Object.assign(box.cam, c); box.updateCamera(); const p = camera.position; return { x: p.x, y: p.y, z: p.z, look: camera.look.slice() }; };
  out.orbit = [];
  for (const el of [box.EL_MIN, 30 * Math.PI / 180, box.EL_MAX]) for (const az of [0, 1, 2.5, 4, 5.5]) {
    const c = { az, el, dist: 9, tx: 1, tz: -2 }, p = pose(c);
    const hx = p.x - c.tx, hz = p.z - c.tz, hor = Math.hypot(hx, hz);
    out.orbit.push({ el, az, tilt: Math.atan2(p.y - p.look[1], hor), dir: Math.atan2(hx, hz),
      dist: Math.hypot(hor, p.y - p.look[1]), look: [p.look[0], p.look[2]], want: [c.tx, c.tz] });
  }
  const tower = (x, z) => (x >= 1 && x < 3 && z >= 1 && z < 3 ? 3.2 : 0) || (x >= -2 && x < -1 && z >= 3 && z < 4 ? 1.6 : 0) || (x >= -4 && x < -3 && z >= -1 && z < 0 ? 2.4 : 0);
  ground = tower;
  out.clip = []; out.poses = 0;
  const near = (x, z) => { let h = 0; for (const [dx, dz] of [[0, 0], [.25, 0], [-.25, 0], [0, .25], [0, -.25]]) h = Math.max(h, tower(x + dx, z + dz)); return h; };
  for (const [tx, tz] of [[0, 0], [.5, 2], [3.5, 3.5], [-1.5, 2.6], [2, .4], [-3.5, .3]])
    for (const el of [box.EL_MIN, 30 * Math.PI / 180, box.EL_MAX])
      for (const dist of [box.DIST_MIN, 4, 9])
        for (let i = 0; i < 16; i++) {
          const az = i * Math.PI / 8, p = pose({ az, el, dist, tx, tz });
          out.poses++;
          if (!(p.y > .3) || p.y < near(p.x, p.z) + .1) out.clip.push({ tx, tz, el, dist, az, y: p.y, top: near(p.x, p.z) });
        }
  out.clip = out.clip.slice(0, 5);
}
// auto-rotation
{
  const box = ctx({ cam: { az: 1, el: .7, dist: 6.5, tx: 0, tz: 0 }, drag: null, pinch: null, camTween: null, lastTouch: -Infinity, RM: false });
  const turn = (now, dt, setup) => { box.cam.az = 1; box.drag = null; box.pinch = null; box.camTween = null; box.lastTouch = -Infinity; box.RM = false; Object.assign(box, setup || {}); box.autoRotate(now, dt); return box.cam.az - 1; };
  out.rot = {
    idle: turn(100000, 1),
    touched5s: turn(100000, 1, { lastTouch: 95000 }),
    touched11s: turn(100000, 1, { lastTouch: 89000 }),
    dragging: turn(100000, 1, { drag: { x: 0, y: 0, moved: true } }),
    pinching: turn(100000, 1, { pinch: { d: 100, z: 1 } }),
    reduced: turn(100000, 1, { RM: true }),
  };
  out.rot.keeps = [box.cam.el, box.cam.dist];
}
// lift: small, eased, never while dragging
function fakeCamera(){
  return { aspect: 1, fov: 40, look: null, updateProjectionMatrix(){},
    position: { x: 0, y: 0, z: 0, set(x, y, z){ this.x = x; this.y = y; this.z = z; return this; } },
    lookAt(x, y, z){ this.look = typeof x === 'object' ? [x.x, x.y, x.z] : [x, y, z]; } };
}
const clampFn = (v, a, b) => Math.max(a, Math.min(b, v));
{
  const camera = fakeCamera();
  const box = ctx({ camera, cam: { az: 0, el: .5, dist: 9, tx: 0, tz: 0 }, W: 1200, H: 800, clamp: clampFn,
    drag: null, pinch: null, camLiftNow: 0, fadeables: [] });
  let ground = () => 0;
  box.heightAt = (x, z) => ground(x, z);
  const tower = (x, z) => (x >= 1 && x < 3 && z >= 1 && z < 3 ? 3.2 : 0);
  const tilt = () => { const p = camera.position, l = camera.look; return Math.atan2(p.y - l[1], Math.hypot(p.x - l[0], p.z - l[2])); };
  const base = () => ({ az: Math.PI / 4, el: box.EL_DEFAULT, dist: 9, tx: 0, tz: 0 });
  const run = (n, c, setup) => { Object.assign(box.cam, c); Object.assign(box, { drag: null, pinch: null }, setup || {}); for (let i = 0; i < n; i++) box.updateCamera(); return tilt(); };
  run(80, base());
  ground = tower;
  out.lift = { el: box.EL_DEFAULT, elMin: box.EL_MIN, liftMax: box.LIFT_MAX };
  out.lift.firstFrame = run(1, base());
  out.lift.settled = run(120, base());
  out.lift.dragging = run(120, base(), { drag: { x: 0, y: 0, moved: true } });
  out.lift.pinching = run(120, base(), { pinch: { d: 100, z: 9 } });
  out.lift.userLow = run(120, Object.assign(base(), { el: box.EL_MIN }));
  Object.assign(box.cam, base());
  out.blockers = {
    front: [...box.viewBlockers(box.EL_DEFAULT + box.LIFT_MAX)],
    steep: [...box.viewBlockers(1.4)],
  };
  Object.assign(box.cam, base(), { az: Math.PI / 4 + Math.PI });
  out.blockers.behind = [...box.viewBlockers(box.EL_DEFAULT)];
  ground = () => 0;
  Object.assign(box.cam, base());
  out.blockers.flat = [...box.viewBlockers(box.EL_DEFAULT)];
}
// fade: cached clones, shared materials untouched, restore
{
  const box = ctx({ fadeables: [], FADE_OPACITY: .3, fadedMats: new WeakMap() });
  const plane = { constant: 1 };
  const mat = () => { const m = { opacity: 1, transparent: false, depthWrite: true, clippingPlanes: [plane], userData: {} };
    m.clone = function(){ const c = Object.assign({}, this); c.userData = {}; c.clippingPlanes = this.clippingPlanes ? this.clippingPlanes.map(q => Object.assign({}, q)) : null; return c; };
    return m; };
  const shared = mat();
  const mesh = () => ({ isMesh: true, material: shared });
  const group = meshes => ({ isMesh: false, traverse(fn){ fn(this); meshes.forEach(fn); } });
  const a1 = mesh(), a2 = mesh(), b1 = mesh();
  box.fadeables.push({ g: group([a1, a2]), tiles: ['1,1', '1,2'] }, { g: group([b1]), tiles: ['5,5'] });
  box.applyFade(new Set(['1,2']));
  out.fade = {
    faded: a1.material !== shared && a2.material !== shared,
    opacity: a1.material.opacity, transparent: a1.material.transparent, depthWrite: a1.material.depthWrite,
    otherUntouched: b1.material === shared,
    sharedUntouched: shared.opacity === 1 && shared.transparent === false && shared.depthWrite === true,
    planesShared: !!(a1.material.clippingPlanes && a1.material.clippingPlanes[0] === plane),
  };
  box.applyFade(new Set(['1,2']));
  out.fade.opacityAgain = a1.material.opacity;
  box.applyFade(new Set());
  out.fade.restored = a1.material === shared && a2.material === shared && b1.material === shared;
}
// zoom out: the whole land fills the stage, sits in the middle, the same from every angle
{
  const camera = fakeCamera();
  const box = ctx({ camera, cam: { az: 0, el: .5, dist: 9, tx: 0, tz: 0 }, W: 874, H: 710, clamp: clampFn,
    drag: null, pinch: null, camLiftNow: 0, fadeables: [], land: { hx: 13, hz: 13 }, home: { x: 0, z: 0 } });
  box.heightAt = () => 0;
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]], dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const norm = a => { const l = Math.hypot(...a); return a.map(v => v / l); };
  const fit = (W, H, az, el, hx, hz) => {
    box.W = W; box.H = H; box.land = { hx, hz };
    Object.assign(box.cam, { az, el: el === undefined ? box.EL_DEFAULT : el, tx: .3, tz: 2.8 });
    box.cam.dist = box.distMax();
    for (let i = 0; i < 40; i++) box.updateCamera();
    const P = [camera.position.x, camera.position.y, camera.position.z], L = camera.look;
    const f = norm(sub(L, P)), r = norm(cross(f, [0, 1, 0])), u = cross(r, f);
    const t = Math.tan(box.FOV * Math.PI / 360), a = W / H;
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    for (const x of [-hx, hx]) for (const z of [-hz, hz]) for (const y of [-1.05, 0]) {
      const d = sub([x, y, z], P), zc = dot(d, f), nx = dot(d, r) / (zc * t * a), ny = dot(d, u) / (zc * t);
      x0 = Math.min(x0, nx); x1 = Math.max(x1, nx); y0 = Math.min(y0, ny); y1 = Math.max(y1, ny);
    }
    const dm = box.cam.dist;
    box.cam.az = az + 1.3; box.W = W * (1 + 1e-9); const dm2 = box.distMax(); box.cam.az = az; box.W = W;
    return { dist: dm, sameFromAnyAngle: Math.abs(dm2 - dm) < 1e-3, look: [L[0], L[2]], w: (x1 - x0) / 2, h: (y1 - y0) / 2,
      cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, edge: Math.max(-x0, x1, -y0, y1) };
  };
  const d = Math.PI / 180;
  const one = [13, 13];
  out.zoomOut = {};
  for (const [name, W, H, az, el] of [['wide', 874, 710, Math.PI / 4], ['phone', 358, 394, Math.PI / 4], ['wideSide', 874, 710, 0],
    ['broad', 1400, 700, Math.PI / 4], ['wideSteep', 874, 710, Math.PI / 4, 60 * d], ['wideLow', 874, 710, Math.PI / 4, 15 * d],
    ['broadSteep', 1400, 700, Math.PI / 4, 60 * d], ['phoneSide', 358, 394, 0, 45 * d]])
    out.zoomOut[name] = fit(W, H, az, el, one[0], one[1]);
  // lands of several territories (half sizes of real layouts: 2 repos side by side or stacked,
  // 3 in an L, a coast with its sea, 5 in a plus; and a 3:1 strip as the extreme): never cut off
  // from any angle, always centred
  out.zoomLands = [];
  for (const [hx, hz] of [[26, 13], [13, 26], [26, 26], [13, 17], [39, 39], [39, 30], [13, 39]])
    for (const [W, H] of [[874, 710], [358, 394], [1400, 700]])
      for (let k = 0; k < 12; k++) {
        const z = fit(W, H, k * Math.PI / 12, undefined, hx, hz);
        out.zoomLands.push({ hx, hz, W, H, az: k * 15, edge: z.edge, cx: z.cx, cy: z.cy, fill: Math.max(z.w, z.h), same: z.sameFromAnyAngle });
      }
  // tilting while fully zoomed out stays fully out; zooming past the limit is clamped
  // six steps out from the default view reach the limit on a land of five territories
  box.W = 874; box.H = 710; box.land = { hx: 39, hz: 39 }; box.home = { x: 0, z: 0 };
  box.camChanged = () => {};
  box.resetCam();
  if (typeof box.zoomStep === 'function') { for (let i = 0; i < 6; i++) box.zoomStep(1); out.sixOut = box.cam.dist / box.distMax(); }
  else out.sixOut = null;
  // at the limit, tall things by the middle must not lift the view off the land
  box.heightAt = (x, z) => (Math.abs(x) < 3 && Math.abs(z) < 3 ? 4 : 0);
  out.liftAtLimit = [];
  for (const [W, H, hx, hz] of [[874, 710, 26, 26], [874, 710, 39, 39], [358, 394, 26, 13]]) {
    box.camLiftNow = 0;
    const z = fit(W, H, Math.PI / 5, undefined, hx, hz);
    for (let i = 0; i < 60; i++) box.updateCamera();
    const again = fit(W, H, Math.PI / 5, undefined, hx, hz);
    out.liftAtLimit.push({ W, H, hx, hz, lift: box.camLiftNow, edge: again.edge, cx: again.cx, cy: again.cy });
  }
  box.heightAt = () => 0; box.camLiftNow = 0;
  box.W = 874; box.H = 710; box.land = { hx: 13, hz: 13 };
  Object.assign(box.cam, { az: 1, el: box.EL_DEFAULT, tx: 0, tz: 0 }); box.cam.dist = box.distMax() * 3; box.updateCamera();
  out.clamped = box.cam.dist <= box.distMax() + 1e-9;
  box.W = 874; box.H = 710;
  Object.assign(box.cam, { az: 1, el: box.EL_DEFAULT, tx: 1, tz: -2, dist: 9 });
  out.targetNear = box.camTarget();
  box.cam.dist = 12; out.target12 = box.camTarget();
  out.targetY = box.TARGET_Y;
}
// frame rate: auto-rotation counts as motion, so live with zero agents is not throttled
{
  const box = ctx({ cam: { az: 0, el: .5, dist: 9, tx: 0, tz: 0 }, drag: null, pinch: null, camTween: null, lastTouch: -Infinity, RM: false,
    floaters: [], citizens: [], needFrame: false, performance: { now: () => 100000 } });
  const busy = setup => { Object.assign(box, { drag: null, pinch: null, camTween: null, lastTouch: -Infinity, RM: false }, setup || {}); return !!box.busy(); };
  out.busy = { rotating: busy(), touched: busy({ lastTouch: 95000 }), reduced: busy({ RM: true }) };
}
process.stdout.write(JSON.stringify(out));
"""


def run_node(js, payload):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "harness.js")
        data = os.path.join(tmp, "data.json")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(js)
        with open(data, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        result = subprocess.run([node, script, data], capture_output=True, text=True,
                                timeout=60, stdin=subprocess.DEVNULL)
    if result.returncode != 0 or not result.stdout.strip():
        raise AssertionError("node harness failed:\n" + result.stderr[-3000:])
    return json.loads(result.stdout)


_CACHE = {}


def unit_results():
    if "unit" not in _CACHE:
        fns = []
        for name in ("move", "anim", "petAnim", "resetCam", "autoRotate", "updateCamera", "busy",
                     "camLift", "camTarget", "distMax", "viewBlockers", "applyFade"):
            src = function_source(name)
            if src is None:
                raise AssertionError("function %s(...) not found in the page script" % name)
            fns.append(src)
        for name in ("aroundH", "autoRotating", "fadedOf", "islandSpread", "landSpread", "centreHeight", "zoomStep"):
            src = function_source(name)
            if src is not None:
                fns.append(src)
        _CACHE["unit"] = run_node(UNIT_JS, {"prelude": constants_prelude(), "fns": "\n".join(fns)})
    return _CACHE["unit"]


def card_results():
    if "cards" not in _CACHE:
        section = cards_section()
        if section is None:
            raise AssertionError("no `/* ---------- right column` section in the page script")
        _CACHE["cards"] = run_node(HARNESS_JS, {"prelude": constants_prelude(), "section": section})
        if "fatal" in _CACHE["cards"]:
            raise AssertionError("card harness crashed: " + _CACHE["cards"]["fatal"])
    return _CACHE["cards"]


# ---------------------------------------------------------------------------
# Cleanup: tests
# ---------------------------------------------------------------------------

class TestRemoved(unittest.TestCase):
    def test_no_intro_card(self):
        self.assertNotIn('id="intro"', page())
        self.assertNotIn("#intro", inline_script())

    def test_no_legend_card(self):
        self.assertNotIn("怎么看这座城", page())
        self.assertNotIn('class="legend"', page())
        self.assertNotIn(">Legend<", page())

    def test_no_credits_card(self):
        self.assertNotIn("素材来源", page())
        self.assertNotIn(">Credits<", page())

    def test_no_speed_buttons(self):
        self.assertNotIn("data-speed", page())
        self.assertIsNone(re.search(r"\b\d×", markup()), "a speed label is still on the page")

    def test_no_pause_button(self):
        for needle in ('id="play"', "icon-pause", "icon-play", "play-label", "#play"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, page())

    def test_no_drag_hint(self):
        self.assertNotIn("hint-drag", page())
        self.assertNotIn("hideHint", inline_script())

    def test_no_empty_separator(self):
        self.assertNotIn("spawn-sep", page())

    def test_real_time_only(self):
        text = inline_script()
        self.assertIsNone(re.search(r"\bspeed\b", text), "`speed` is still in the script")
        self.assertIsNone(re.search(r"\bpaused\b", text), "`paused` is still in the script")
        self.assertNotIn("dtScaled", text)

    def test_no_keyboard_shortcuts(self):
        for event in ("keydown", "keyup", "keypress"):
            with self.subTest(event=event):
                self.assertNotIn(event, inline_script())


class TestKept(unittest.TestCase):
    def test_chinese_page(self):
        self.assertIn('<html lang="zh-CN">', page())

    def test_status_counts(self):
        body = function_source("renderStats") or ""
        for label in ("干活", "找总督", "休息", "建成"):
            with self.subTest(label=label):
                self.assertIn(label, body)

    def test_clock(self):
        self.assertIn('id="clock"', markup())
        self.assertIn("$('#clock')", inline_script())

    def test_spawn_control_only_in_demo(self):
        self.assertIn('id="spawn-group"', markup())
        self.assertRegex(inline_script(),
                         r"if \(DEMO\) \{\s*\$\('#spawn'\)\.addEventListener[\s\S]*?\n\} else \{\s*"
                         r"\$\('#spawn-group'\)\.hidden = true;")

    def test_detail_buttons_only_in_demo(self):
        text = inline_script()
        for act in ("stuck", "done", "leave"):
            with self.subTest(act=act):
                self.assertEqual(text.count('data-act="%s"' % act), 1)
        self.assertRegex(text, r"\$\{DEMO \? `\s*<div class=\"d-actions\">")

    def test_camera_buttons_unchanged(self):
        block = re.search(r'<div class="cam">(.*?)</div>', markup(), re.S)
        self.assertIsNotNone(block)
        self.assertEqual(re.findall(r'<button[^>]*\bid="(\w+)"', block.group(1)), ["zin", "zout", "rot", "zfit"])
        self.assertEqual(block.group(1).count("<button"), 4)

    def test_zoom_still_works(self):
        text = inline_script()
        for needle in ("$('#zin').addEventListener", "$('#zout').addEventListener",
                       "canvas.addEventListener('wheel'", "pinch"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_phone_layout(self):
        self.assertIn('name="viewport"', page())
        self.assertRegex(style(), r"@media \(max-width: ?960px\)\s*\{[^@]*?\.layout\{grid-template-columns:minmax\(0,1fr\)\}")


class TestWalkSpeed(unittest.TestCase):
    def test_walk_is_a_third(self):
        walk = unit_results()["walk"]
        for state in ("to_plot", "back", "to_rest", "leaving"):
            with self.subTest(state=state):
                self.assertAlmostEqual(walk[state], 1.9 / 3, delta=0.03)

    def test_sprint_to_city_hall_is_a_third(self):
        self.assertAlmostEqual(unit_results()["walk"]["to_hall"], 2.3 / 3, delta=0.03)

    def test_old_speeds_are_gone(self):
        self.assertNotIn("2.3 : 1.9", inline_script())

    def test_walk_animation_slowed_to_match(self):
        for name, scale in unit_results()["anim"]:
            with self.subTest(clip=name):
                want = 1 / 3 if name in ("walk", "sprint") else 1
                self.assertAlmostEqual(scale, want, delta=0.02)

    def test_pets_unchanged(self):
        for name, scale in unit_results()["pet"]:
            with self.subTest(clip=name):
                self.assertAlmostEqual(scale, 1, delta=0.001)
        self.assertIn(".45 * dt", function_source("updatePets") or "")


class TestNoFrame(unittest.TestCase):
    def test_no_frame_around_the_city(self):
        rules = re.findall(r"(?<![\w-])\.stage\{([^}]*)\}", style())
        self.assertTrue(rules)
        for rule in rules:
            with self.subTest(rule=rule):
                self.assertNotRegex(rule, r"border(-radius)?\s*:\s*(?!0\b|none\b)")
                self.assertNotIn("var(--sky)", rule, "the city must blend into the page, no box")


class TestSmoothAndSteady(unittest.TestCase):
    def test_live_is_as_smooth_as_demo_while_rotating(self):
        self.assertTrue(unit_results()["busy"]["rotating"],
                        "with zero agents the auto-rotating camera must get the full frame rate")

    def test_still_cheap_when_nothing_moves(self):
        b = unit_results()["busy"]
        self.assertTrue(b["touched"], "a touch never pauses the rotation (owner 2026-09-25)")
        self.assertFalse(b["reduced"], "reduced motion: no rotation, idle rate")

    def test_no_brown_earth_block_sides(self):
        """E2E bounce G3: the owner said no to brown earth blocks twice."""
        self.assertFalse([m for m in models() if "cliff_block" in m], "cliff_block models are brown earth cubes")
        self.assertNotIn("cliff_block", inline_script())

    def test_depth_range_is_tight(self):
        m = re.search(r"new THREE\.PerspectiveCamera\(\s*\w+,\s*[\w.]+,\s*([\d.]+),\s*([\d.]+)\s*\)", inline_script())
        self.assertIsNotNone(m, "PerspectiveCamera(FOV, aspect, near, far) with number literals for near and far")
        near, far = float(m.group(1)), float(m.group(2))
        self.assertGreaterEqual(near, 0.2)
        self.assertLessEqual(far, 200)
        self.assertLessEqual(far / near, 1000)


class TestLiftAndFade(unittest.TestCase):
    """E2E bounce: the lift jumped to a near top-down view and overrode the user's tilt."""

    def test_lift_is_at_most_10_degrees(self):
        l = unit_results()["lift"]
        self.assertAlmostEqual(unit_results()["consts"]["LIFT_MAX"], 0.1745, delta=0.01)
        self.assertLessEqual(l["settled"] - l["el"], 0.1745 + 0.01)
        self.assertGreater(l["settled"] - l["el"], 0.12, "a small lift still helps when a building is in the way")

    def test_lift_never_jumps(self):
        l = unit_results()["lift"]
        self.assertLessEqual(l["firstFrame"] - l["el"], 0.0524, "at most about 3 degrees in one frame")

    def test_no_lift_while_the_user_drags_or_pinches(self):
        l = unit_results()["lift"]
        self.assertAlmostEqual(l["dragging"], l["el"], delta=0.01)
        self.assertAlmostEqual(l["pinching"], l["el"], delta=0.01)

    def test_user_low_tilt_stays_low(self):
        l = unit_results()["lift"]
        self.assertLessEqual(l["userLow"], l["elMin"] + 0.1745 + 0.01)

    def test_blockers_are_the_tiles_in_the_way(self):
        b = unit_results()["blockers"]
        self.assertTrue(set(b["front"]) & {"1,1", "1,2", "2,1", "2,2"}, b["front"])
        self.assertTrue(set(b["front"]) <= {"1,1", "1,2", "2,1", "2,2"}, b["front"])
        self.assertEqual(b["steep"], [])
        self.assertEqual(b["behind"], [])
        self.assertEqual(b["flat"], [])

    def test_fade_uses_cached_clones_and_restores(self):
        f = unit_results()["fade"]
        self.assertTrue(f["faded"])
        self.assertAlmostEqual(f["opacity"], 0.3, delta=0.05)
        self.assertTrue(f["transparent"])
        self.assertFalse(f["depthWrite"])
        self.assertTrue(f["otherUntouched"])
        self.assertTrue(f["sharedUntouched"], "a shared material was changed")
        self.assertTrue(f["planesShared"], "a faded building under construction must keep its moving clip plane")
        self.assertAlmostEqual(f["opacityAgain"], 0.3, delta=0.05, msg="faded twice")
        self.assertTrue(f["restored"])

    def test_fade_opacity(self):
        self.assertAlmostEqual(unit_results()["consts"]["FADE_OPACITY"], 0.3, delta=0.05)

    def test_hall_and_buildings_can_fade(self):
        self.assertRegex(function_source("buildLand") or "", r"fadeables\.push\(")
        self.assertRegex(function_source("makeBuilding") or "", r"fadeables\.push\(")
        self.assertIsNone(function_source("removeBuilding"), "buildings are permanent")

    def test_frame_fades_what_blocks_the_view(self):
        self.assertRegex(function_source("frame") or "", r"applyFade\(viewBlockers\(cam\.el \+ camLiftNow\)\)")


class TestZoomOut(unittest.TestCase):
    """E2E bounce: fully zoomed out the island took a third of the stage, upper left."""

    def test_island_fills_about_80_percent(self):
        for name in ("wide", "phone", "broad", "wideSteep", "wideLow", "broadSteep"):
            with self.subTest(stage=name):
                z = unit_results()["zoomOut"][name]
                self.assertGreaterEqual(max(z["w"], z["h"]), 0.7)
                self.assertLessEqual(max(z["w"], z["h"]), 0.9)

    def test_whole_island_stays_inside(self):
        for name, z in unit_results()["zoomOut"].items():
            with self.subTest(stage=name):
                self.assertLessEqual(z["edge"], 0.98, "part of the island is cut off")

    def test_limit_is_the_same_from_every_angle(self):
        for name, z in unit_results()["zoomOut"].items():
            with self.subTest(stage=name):
                self.assertTrue(z["sameFromAnyAngle"], "auto-rotation would change the zoom")

    def test_a_land_of_many_territories_is_never_cut_off(self):
        for z in unit_results()["zoomLands"]:
            with self.subTest(land=(z["hx"], z["hz"]), stage=(z["W"], z["H"]), az=z["az"]):
                self.assertLessEqual(z["edge"], 0.98, "part of the land is cut off")
                self.assertLessEqual(abs(z["cx"]), 0.1)
                self.assertLessEqual(abs(z["cy"]), 0.1)
                self.assertTrue(z["same"], "auto-rotation would change the zoom")
                # One zoom for every angle (auto-rotation never zooms), so a long land seen
                # end-on fills less of the stage; it must still be clearly there.
                low = 0.3 if max(z["hx"], z["hz"]) >= 3 * min(z["hx"], z["hz"]) else 0.35
                self.assertGreaterEqual(z["fill"], low, "the land is lost in the middle of the stage")

    def test_six_steps_out_show_the_whole_land(self):
        """E2E bounce G6: 6 x minus in #demo still cut the land off."""
        six = unit_results()["sixOut"]
        self.assertIsNotNone(six, "function zoomStep(k) not found")
        self.assertAlmostEqual(six, 1.0, delta=1e-6)

    def test_no_lift_at_the_zoom_out_limit(self):
        for z in unit_results()["liftAtLimit"]:
            with self.subTest(land=(z["hx"], z["hz"]), stage=(z["W"], z["H"])):
                self.assertLessEqual(abs(z["lift"]), 0.005)
                self.assertLessEqual(z["edge"], 0.98)
                self.assertLessEqual(abs(z["cx"]), 0.1)
                self.assertLessEqual(abs(z["cy"]), 0.1)

    def test_zoom_past_the_limit_is_clamped(self):
        self.assertTrue(unit_results()["clamped"])

    def test_island_sits_in_the_middle(self):
        for name, z in unit_results()["zoomOut"].items():
            with self.subTest(stage=name):
                self.assertLessEqual(abs(z["cx"]), 0.1)
                self.assertLessEqual(abs(z["cy"]), 0.1)

    def test_zoomed_out_view_aims_at_the_island_centre(self):
        for name in unit_results()["zoomOut"]:
            with self.subTest(stage=name):
                look = unit_results()["zoomOut"][name]["look"]
                self.assertAlmostEqual(look[0], 0, delta=0.05)
                self.assertAlmostEqual(look[1], 0, delta=0.05)

    def test_close_views_keep_the_users_target(self):
        r = unit_results()
        self.assertEqual(r["targetNear"], [1, r["targetY"], -2])
        self.assertAlmostEqual(r["target12"][0], 1, delta=0.01)
        self.assertAlmostEqual(r["target12"][1], r["targetY"], delta=0.01)
        self.assertAlmostEqual(r["target12"][2], -2, delta=0.01)

    def test_tilting_while_fully_zoomed_out_stays_out(self):
        self.assertRegex(inline_script(), r"const out = cam\.dist >= distMax\(\)[^\n]*cam\.el = clamp\([^\n]*if \(out\) cam\.dist = distMax\(\)")


class TestCamera(unittest.TestCase):
    def test_perspective_not_god_view(self):
        text = inline_script()
        self.assertNotIn("OrthographicCamera", text)
        self.assertRegex(text, r"new THREE\.PerspectiveCamera\(\s*(FOV|40)\b")
        self.assertAlmostEqual(unit_results()["consts"]["FOV"], 40, delta=5)

    def test_default_view_is_close_to_the_town_hall(self):
        r = unit_results()
        for key in ("viewWide", "viewPhone"):
            with self.subTest(view=key):
                v = r[key]
                self.assertAlmostEqual(v["el"], 0.5236, delta=0.06, msg="tilt about 30 degrees")
                self.assertLessEqual(((v["tx"] - 4) ** 2 + (v["tz"] + 3) ** 2) ** .5, 3.5,
                                     "look at the home town hall (the test puts it at scene 4, -3)")
                self.assertGreaterEqual(v["dist"], r["consts"]["DIST_MIN"])
                self.assertLessEqual(v["dist"], 14, "close enough to see people")
        self.assertLessEqual(r["viewWide"]["dist"], r["viewPhone"]["dist"])

    def test_tilt_range(self):
        c = unit_results()["consts"]
        self.assertAlmostEqual(c["EL_MIN"], 0.2618, delta=0.035)
        self.assertAlmostEqual(c["EL_MAX"], 1.0472, delta=0.05)
        self.assertRegex(inline_script(), r"cam\.el = clamp\([^;]*EL_MIN, EL_MAX\)")

    def test_zoom_from_street_level_to_the_whole_island(self):
        c = unit_results()["consts"]
        self.assertLessEqual(c["DIST_MIN"], 3.5)
        text = inline_script()
        self.assertNotIn("DIST_MAX", text)
        step = function_source("zoomStep") or ""
        for needle in ("$('#zin')", "$('#zout')", "canvas.addEventListener('wheel'"):
            with self.subTest(control=needle):
                line = next(l for l in text.splitlines() if needle in l)
                self.assertTrue("DIST_MIN, distMax()" in line or ("zoomStep(" in line and "DIST_MIN, distMax()" in step), line)
        self.assertRegex(text, r"pinch\.z[^;\n]*DIST_MIN, distMax\(\)")

    def test_camera_orbits_the_target_at_the_users_tilt(self):
        import math
        for o in unit_results()["orbit"]:
            with self.subTest(el=round(o["el"], 3), az=o["az"]):
                self.assertAlmostEqual(o["tilt"], o["el"], delta=0.01)
                self.assertAlmostEqual(o["dist"], 9, delta=0.05)
                self.assertAlmostEqual(math.remainder(o["dir"] - o["az"], 2 * math.pi), 0, delta=0.01)
                self.assertAlmostEqual(o["look"][0], o["want"][0], delta=0.01)
                self.assertAlmostEqual(o["look"][1], o["want"][1], delta=0.01)

    def test_never_clips_into_ground_or_buildings(self):
        r = unit_results()
        self.assertGreater(r["poses"], 800)
        self.assertEqual(r["clip"], [])

    def test_overlays_hide_behind_the_camera(self):
        self.assertRegex(function_source("toScreen") or "", r"\.z\s*>=?\s*1\b")

    def test_auto_rotation_keeps_tilt_and_zoom(self):
        self.assertEqual(unit_results()["rot"]["keeps"], [0.7, 6.5])

    def test_auto_rotation_one_turn_per_five_minutes(self):
        per_second = abs(unit_results()["rot"]["idle"])
        self.assertAlmostEqual(per_second, 2 * 3.141592653589793 / 300, delta=0.003)

    def test_auto_rotation_never_waits_after_a_touch(self):
        rot = unit_results()["rot"]
        self.assertNotEqual(rot["idle"], 0)
        self.assertAlmostEqual(rot["touched5s"], rot["idle"], delta=1e-9)
        self.assertAlmostEqual(rot["touched11s"], rot["idle"], delta=1e-9)

    def test_auto_rotation_keeps_turning_while_dragging_or_zooming(self):
        rot = unit_results()["rot"]
        self.assertAlmostEqual(rot["dragging"], rot["idle"], delta=1e-9)
        self.assertAlmostEqual(rot["pinching"], rot["idle"], delta=1e-9)

    def test_no_auto_rotation_for_reduced_motion(self):
        self.assertEqual(unit_results()["rot"]["reduced"], 0)

    def test_frame_calls_auto_rotate(self):
        self.assertRegex(function_source("frame") or "", r"\bautoRotate\(")

    def test_no_pause_timer_left(self):
        text = inline_script()
        self.assertFalse("AUTO_ROT_IDLE_MS" in text, "no resume-after-10s timer any more")
        src = function_source("autoRotating") or function_source("autoRotate") or ""
        self.assertNotIn("drag", src, "a drag never pauses the rotation")
        self.assertNotIn("pinch", src, "zoom never pauses the rotation")


class TestCardsMarkup(unittest.TestCase):
    def test_four_cards_in_default_order(self):
        panel = re.search(r'<aside class="panel" id="panel"[^>]*>(.*?)</aside>', markup(), re.S)
        self.assertIsNotNone(panel, '<aside class="panel" id="panel"> not found')
        self.assertEqual(re.findall(r'data-card="([\w-]+)"', panel.group(1)), ["detail", "balance", "citizens", "log"])
        self.assertEqual(panel.group(1).count("<section"), 4)

    def test_each_card_has_a_toggle_header_and_one_body(self):
        want = {"detail": ("详情", "detail"), "balance": ("城市平衡", "balance"), "citizens": ("市民", "roster"),
                "log": ("动态", "log")}
        found = dict(cards())
        self.assertEqual(sorted(found), sorted(want))
        for name, (zh, body_id) in want.items():
            with self.subTest(card=name):
                inner = found[name]
                head = re.search(r'<h2 class="card-head">\s*<button type="button"([^>]*)>(.*?)</button>\s*</h2>', inner, re.S)
                self.assertIsNotNone(head, "header button missing")
                self.assertIn('aria-expanded="true"', head.group(1))
                self.assertIn('aria-controls="%s"' % body_id, head.group(1))
                self.assertIn(zh, head.group(2))
                self.assertEqual(len(re.findall(r'class="[^"]*\bcard-body\b', inner)), 1)
                self.assertRegex(inner, r'<[a-z]+ class="[^"]*\bcard-body\b[^"]*" id="%s"' % body_id)
                self.assertLess(inner.index("card-head"), inner.index('id="%s"' % body_id))

    def test_detail_header_is_static(self):
        self.assertNotIn("<h2", inline_script())

    def test_collapsed_card_hides_its_body(self):
        self.assertRegex(style(), r"\.card\.collapsed \.card-body\{display:none")

    def test_header_takes_touch_for_dragging(self):
        self.assertRegex(style(), r"\.card-head\{[^}]*touch-action:none")


class TestCardsBehaviour(unittest.TestCase):
    """The right-column section run in node against a fake DOM."""

    def test_default_state(self):
        r = card_results()["fresh"]
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["order"], ["detail", "citizens", "log"])
        self.assertEqual(r["collapsed"], [])

    def test_click_header_collapses_and_reopens(self):
        r = card_results()
        self.assertEqual(r["collapsed"]["collapsed"], ["citizens"])
        self.assertEqual(r["collapsed"]["expanded"]["citizens"], "false")
        self.assertEqual(r["collapsed"]["expanded"]["detail"], "true")
        self.assertEqual(r["reopened"]["collapsed"], [])
        self.assertEqual(r["reopened"]["expanded"]["citizens"], "true")
        self.assertEqual(r["reopened"]["errors"], [])

    def test_collapse_is_saved(self):
        r = card_results()
        self.assertEqual(json.loads(r["collapsed"]["stored"])["collapsed"], ["citizens"])
        self.assertEqual(json.loads(r["reopened"]["stored"])["collapsed"], [])

    def test_drag_header_reorders(self):
        r = card_results()["dragged"]
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["order"], ["log", "detail", "citizens"])
        self.assertEqual(r["collapsed"], [], "the click that ends a drag must not toggle")
        self.assertEqual(r["offset"], [], "a dropped card must sit in its slot, no leftover offset")
        self.assertEqual(json.loads(r["stored"])["order"], ["log", "detail", "citizens"])

    def test_card_dropped_mid_column_sits_in_its_slot(self):
        r = card_results()["midDrop"]
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["order"], ["detail", "log", "citizens"])
        self.assertEqual(r["offset"], [], "a dropped card must sit in its slot, no leftover offset")
        self.assertEqual(r["collapsed"], [])

    def test_plain_click_after_a_drag_still_toggles(self):
        r = card_results()["clickAfterDrag"]
        self.assertEqual(r["collapsed"], ["log"])

    def test_drag_never_leaves_the_column(self):
        r = card_results()["farDrag"]
        self.assertEqual(r["errors"], [])
        self.assertTrue(r["inPanel"], "a card left the right column")
        self.assertEqual(r["order"][-1], "detail")
        self.assertEqual(sorted(r["order"]), ["citizens", "detail", "log"])

    def test_restores_saved_order_and_collapse(self):
        r = card_results()["restored"]
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["order"], ["log", "detail", "citizens"])
        self.assertEqual(r["collapsed"], ["citizens"])
        self.assertEqual(r["expanded"], {"log": "true", "detail": "true", "citizens": "false"})

    def test_bad_saved_data_is_ignored(self):
        results = card_results()
        for case in ("garbage", "wrongShape1", "wrongShape2"):
            with self.subTest(case=case):
                r = results[case]
                self.assertEqual(r["errors"], [])
                self.assertEqual(r["order"], ["detail", "citizens", "log"])
                self.assertEqual(r["collapsed"], [])

    def test_works_when_storage_throws(self):
        results = card_results()
        self.assertEqual(results["throwLoad"]["errors"], [])
        self.assertEqual(results["throwLoad"]["order"], ["detail", "citizens", "log"])
        self.assertEqual(results["throwClick"]["collapsed"], ["detail"])
        self.assertEqual(results["throwClick"]["errors"], [])
        self.assertEqual(results["throwDrag"]["order"], ["log", "detail", "citizens"])
        self.assertEqual(results["throwDrag"]["errors"], [])
        for case in ("setThrow", "getThrow"):
            with self.subTest(case=case):
                self.assertEqual(results[case]["errors"], [])
        self.assertEqual(results["setThrow"]["collapsed"], ["log"])

    def test_every_storage_access_is_guarded(self):
        text = inline_script()
        hits = [m.start() for m in re.finditer(r"localStorage", text)]
        self.assertGreaterEqual(len(hits), 2, "order and collapse are not stored")
        for at in hits:
            before = text[:at]
            opened = max(before.rfind("try {"), before.rfind("try{"))
            with self.subTest(line=text[at - 60:at + 40].strip()):
                self.assertNotEqual(opened, -1, "localStorage used outside try")
                self.assertNotIn("catch", before[opened:], "localStorage used outside try")
                self.assertLess(at - opened, 300)

    def test_storage_key(self):
        self.assertIn("'agent-city-cards'", inline_script())


# ---------------------------------------------------------------------------
# Interaction: the "?" panel
# ---------------------------------------------------------------------------

ASK_LINE_JS = r"""
const fs = require('fs');
const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
eval(data.fn);
process.stdout.write(JSON.stringify(data.cases.map(([ev, name]) => askLine(ev, name))));
"""


def case_block(kind):
    """The code of `case '<kind>':` up to the next case or the end of the switch."""
    text = inline_script()
    m = re.search(r"case\s+'%s'\s*:" % kind, text)
    if not m:
        return None
    rest = text[m.end():]
    n = re.search(r"\bcase\s+'|\bdefault\s*:", rest)
    return rest[:n.start() if n else len(rest)]


def media_block(query):
    text = style()
    i = text.find(query)
    if i < 0:
        return ""
    j = text.index("{", i)
    depth = 0
    for k in range(j, len(text)):
        depth += text[k] == "{"
        depth -= text[k] == "}"
        if depth == 0:
            return text[j:k + 1]
    return ""


class TestInteraction(unittest.TestCase):
    def test_token_meta_tag(self):
        head = page().split("</head>")[0]
        self.assertIn('<meta name="city-token" content="__CITY_TOKEN__">', head)
        self.assertRegex(inline_script(), r"meta\[name=[\"']?city-token")

    def test_ask_messages_are_handled(self):
        text = inline_script()
        for kind in ("ask", "ask_phase", "ask_closed"):
            with self.subTest(kind=kind):
                self.assertRegex(text, r"case\s+'%s'\s*:" % kind)
        self.assertRegex(case_block("snapshot") or "", r"\.asks\b")

    def test_live_answers_are_never_invented(self):
        block = case_block("answer")
        self.assertIsNotNone(block)
        self.assertNotIn("批了", block)
        self.assertNotIn("不行", block)
        self.assertIn("已回答", block)

    def test_panel_sits_over_the_city(self):
        m = markup()
        i, stage, aside = m.find('id="ask"'), m.find('id="stage"'), m.find('<aside class="panel"')
        self.assertGreater(i, 0, "no #ask panel in the markup")
        self.assertTrue(stage < i < aside, "#ask must be inside #stage, not the right column")
        tag = re.search(r"<div[^>]*id=\"ask\"[^>]*>", m).group(0)
        for attr in ('class="ask-panel"', 'role="dialog"', 'aria-labelledby="ask-title"', "hidden"):
            with self.subTest(attr=attr):
                self.assertIn(attr, tag)

    def test_buttons_never_wrap(self):
        css = style().replace(" ", "")
        for sel in (".btn.ok", ".btn.no"):
            with self.subTest(sel=sel):
                rules = re.findall(r"([^{}]*)\{([^{}]*)\}", css)
                body = "".join(b for s, b in rules if sel in s)
                self.assertIn("white-space:nowrap", body)
                self.assertIn("min-width", body)

    def test_phone_layout_has_the_panel(self):
        self.assertIn(".ask-panel", media_block("@media (max-width: 960px)"))

    def test_decisions_go_to_the_page_endpoint_with_the_token(self):
        text = inline_script()
        self.assertRegex(text, r"fetch\(\s*'/api/decide'")
        self.assertIn("'X-City-Token'", text)
        self.assertIn("409", text)
        self.assertNotIn("/api/gov", text)
        self.assertNotIn("总督批准", page())

    def test_owner_waiting_is_visible(self):
        self.assertIn("data-open", inline_script())
        stats = function_source("renderStats") or ""
        self.assertIn("等你", stats)
        self.assertIn('id="next"', stats)

    def test_closed_state_words(self):
        text = inline_script()
        self.assertIn("晚了一步", text)
        self.assertIn("closed", text)

    def test_no_bare_ask_selector(self):
        css = re.sub(r"/\*.*?\*/", "", style(), flags=re.S)
        bad = []
        for sel_list in re.findall(r"([^{}@]+)\{", css):
            for sel in sel_list.split(","):
                first = re.split(r"[\s>+~]+", sel.strip())[0] if sel.strip() else ""
                if re.fullmatch(r"\.ask(:[\w-]+(\([^)]*\))?)*", first):
                    bad.append(sel.strip())
        self.assertEqual(bad, [], "a bare .ask selector also hits the old red bubble, pill and log spans")
        compact = css.replace(" ", "")
        for old in (".bub.ask{border-color:#E4476F}", ".pill.ask{background:var(--ask-bg);color:var(--ask-ink)}",
                    ".log.ask{color:var(--ask-ink)}"):
            with self.subTest(rule=old):
                self.assertIn(old, compact)

    def test_live_stuck_and_answer_write_no_log_line(self):
        for kind in ("stuck", "answer"):
            block = case_block(kind) or ""
            with self.subTest(kind=kind):
                self.assertTrue(block, "no case '%s'" % kind)
                for line in block.splitlines():
                    if "log(" in line:
                        self.assertIn("DEMO", line, "live mode logs asks through ask events only")
        stuck = case_block("stuck") or ""
        for line in stuck.splitlines():
            if "问总督" in line:
                self.assertIn("DEMO", line)

    def test_governor_speaks_only_its_own_answers(self):
        give = function_source("giveAnswer") or ""
        for line in give.splitlines():
            if "say(gov" in line or "gov.answered" in line:
                with self.subTest(line=line.strip()):
                    self.assertIn("DEMO", line)
        closed = case_block("ask_closed") or ""
        self.assertIn("say(gov", closed)
        self.assertIn("'governor'", closed)

    def test_stuck_text_and_citizen_status(self):
        st = function_source("stuckText")
        cs = function_source("citizenStatus")
        self.assertIsNotNone(st, "function stuckText(ev) not found")
        self.assertIsNotNone(cs, "function citizenStatus(c) not found")
        state = re.search(r"^const STATE = \{.*?^\};", inline_script(), re.S | re.M)
        self.assertIsNotNone(state, "const STATE = {...}; not found")
        js = ("const fs = require('fs'); const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));\n"
              + state.group(0) + "\n" + st + "\n" + cs + "\n"
              + "process.stdout.write(JSON.stringify({st: data.st.map(e => stuckText(e)), "
              + "cs: data.cs.map(c => citizenStatus(c))}));")
        out = run_node(js, {
            "st": [{"type": "stuck", "tool": "Bash", "question": ""},
                   {"type": "stuck", "tool": "AskUserQuestion", "question": "Which port?"}],
            "cs": [{"state": "to_hall", "askKind": "permission", "askPhase": "owner"},
                   {"state": "asking", "askKind": "permission", "askPhase": "owner"},
                   {"state": "asking", "askKind": "question", "askPhase": "governor"},
                   {"state": "asking", "askKind": "question", "askPhase": "owner"},
                   {"state": "building", "askKind": "", "askPhase": ""}],
        })
        self.assertIn("要权限", out["st"][0])
        self.assertIn("Bash", out["st"][0])
        for word in ("可以用", "问总督"):
            self.assertNotIn(word, out["st"][0])
        self.assertIn("Which port?", out["st"][1])
        texts = [pair[1] for pair in out["cs"]]
        self.assertIn("等你批", texts[0])
        self.assertIn("等你批", texts[1])
        self.assertIn("在问总督", texts[2])
        self.assertIn("等你回答", texts[3])
        self.assertEqual(texts[4], "施工中")
        for t in texts[:2]:
            self.assertNotIn("问总督", t)

    def test_the_waiting_chip_takes_real_clicks(self):
        stats = function_source("renderStats") or ""
        m = re.search(r'<button class="([^"]+)"[^>]*id="next"', stats)
        self.assertIsNotNone(m, 'renderStats must render <button class="..." ... id="next">')
        chip = ("button", set(m.group(1).split()), "next")
        head = re.search(r'<header class="([^"]+)"', markup())
        stats_div = re.search(r'<div class="([^"]+)" id="stats"', markup())
        self.assertIsNotNone(stats_div, '<div class="stats" id="stats"> not found')
        chain = [chip, ("div", set(stats_div.group(1).split()), "stats")]
        if head:
            chain.append(("header", set(head.group(1).split()), ""))
        css = re.sub(r"/\*.*?\*/", "", style(), flags=re.S)
        hits = []
        for sel_list, body in re.findall(r"([^{}@]+)\{([^{}]*)\}", css):
            if not re.search(r"pointer-events\s*:\s*none", body):
                continue
            for sel in sel_list.split(","):
                sel = sel.strip()
                if not sel:
                    continue
                last = re.split(r"[\s>+~]+", sel)[-1]
                mm = re.fullmatch(r"([a-z]+)?((?:[.#][\w-]+|::?[\w-]+(?:\([^)]*\))?|\[[^\]]*\])*)", last)
                if not mm or not (mm.group(1) or mm.group(2)):
                    continue
                parts = re.findall(r"[.#][\w-]+|::?[\w-]+(?:\([^)]*\))?|\[[^\]]*\]", mm.group(2))
                if ":disabled" in parts:
                    continue
                for tag, classes, ident in chain:
                    if mm.group(1) and mm.group(1) != tag:
                        continue
                    if all((p[0] != "." or p[1:] in classes) and (p[0] != "#" or p[1:] == ident)
                           for p in parts):
                        hits.append("%s -> %s" % (sel, tag))
        self.assertEqual(hits, [], "pointer-events:none reaches the 等你 N chip, so a real click does nothing")

    def test_snapshot_shows_what_live_events_show(self):
        st = function_source("stuckText")
        cs = function_source("citizenStatus")
        ap = function_source("applyAsk")
        self.assertIsNotNone(ap, "function applyAsk(c, ask) not found")
        state = re.search(r"^const STATE = \{.*?^\};", inline_script(), re.S | re.M).group(0)
        for kind in ("ask", "snapshot"):
            with self.subTest(case=kind):
                self.assertIn("applyAsk(", case_block(kind) or "")
        js = r"""
const fs = require('fs'); const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
""" + state + "\n" + st + "\n" + cs + "\n" + ap + r"""
const out = [];
for (const ask of data.asks) {
  // live: the reducer's stuck event first (as it arrives), then the ask event
  const live = { state: 'asking', stuck: false, question: '', askKind: '', askPhase: '' };
  live.stuck = true; live.question = stuckText({ tool: ask.tool, question: ask.kind === 'question' ? ask.questions[0].question : '' });
  applyAsk(live, ask);
  // snapshot: the reducer only says "stuck"; the open ask comes in the asks list
  const snap = { state: 'asking', stuck: true, question: '需要你看一下', askKind: 'permission', askPhase: 'owner' };
  applyAsk(snap, null);
  applyAsk(snap, ask);
  const g = ask.phase === 'governor' ? 1 : 0;
  out.push({ live: [live.question, citizenStatus(live, g)], snap: [snap.question, citizenStatus(snap, g)] });
}
const cleared = { state: 'building', stuck: false, question: '', askKind: 'permission', askPhase: 'owner' };
applyAsk(cleared, null);
out.push({ cleared: citizenStatus(cleared, 1) });
const noGov = { state: 'asking', stuck: true, question: '需要你看一下', askKind: '', askPhase: '' };
out.push({ noGov: citizenStatus(noGov, 0) });
process.stdout.write(JSON.stringify(out));
"""
        asks = [
            {"id": "a1", "agent": "s:x", "kind": "permission", "phase": "owner", "why": "permission",
             "tool": "Bash", "what": "touch chip.txt"},
            {"id": "a2", "agent": "s:x", "kind": "question", "phase": "owner", "why": "no-governor",
             "tool": "AskUserQuestion", "what": "Which port?", "questions": [{"question": "Which port?"}]},
            {"id": "a3", "agent": "s:x", "kind": "question", "phase": "governor", "why": "",
             "tool": "AskUserQuestion", "what": "Which port?", "questions": [{"question": "Which port?"}]},
        ]
        out = run_node(js, {"asks": asks})
        for i, row in enumerate(out[:3]):
            with self.subTest(ask=asks[i]["id"]):
                self.assertEqual(row["snap"], row["live"], "a fresh page must show what an open page shows")
        self.assertEqual(out[0]["snap"][0], "要权限：Bash")
        self.assertIn("等你批", out[0]["snap"][1][1])
        self.assertEqual(out[1]["snap"][0], "Which port?")
        self.assertIn("等你回答", out[1]["snap"][1][1])
        self.assertIn("在问总督", out[2]["snap"][1][1])
        self.assertEqual(out[3]["cleared"][1], "施工中")
        self.assertNotIn("问总督", out[4]["noGov"][1], "no governor: never 问总督")

    def test_governor_presence(self):
        self.assertRegex(inline_script(), r"case\s+'governors'\s*:")
        self.assertIn("不在", function_source("govPillText") or "")
        self.assertRegex(case_block("snapshot") or "", r"\.governors\b")

    def test_ask_line(self):
        fn = function_source("askLine")
        self.assertIsNotNone(fn, "function askLine(ev, name) not found")
        cases = [
            [{"type": "ask", "kind": "permission", "phase": "owner", "why": "permission",
              "tool": "Bash", "what": "rm -rf build/"}, "清理构建"],
            [{"type": "ask", "kind": "question", "phase": "governor", "why": "",
              "tool": "AskUserQuestion", "what": "Which port?"}, "登录页"],
            [{"type": "ask", "kind": "question", "phase": "owner", "why": "no-governor",
              "tool": "AskUserQuestion", "what": "Which port?"}, "登录页"],
            [{"type": "ask_phase", "kind": "question", "phase": "owner", "why": "timeout", "wait": 60}, "改文案"],
            [{"type": "ask_phase", "kind": "question", "phase": "owner", "why": "pass", "wait": 60}, "改文案"],
            [{"type": "ask_closed", "kind": "question", "by": "governor", "verb": "answer", "text": "4791",
              "tool": "AskUserQuestion", "what": "Which port?", "reason": ""}, "登录页"],
            [{"type": "ask_closed", "kind": "permission", "by": "owner", "verb": "allow", "text": "",
              "tool": "Bash", "what": "rm -rf build/", "reason": ""}, "清理构建"],
            [{"type": "ask_closed", "kind": "permission", "by": "owner", "verb": "deny", "text": "",
              "tool": "Write", "what": "/etc/hosts", "reason": "不许改系统文件"}, "改文案"],
            [{"type": "ask_closed", "kind": "permission", "by": "owner", "verb": "deny", "text": "",
              "tool": "Write", "what": "/etc/hosts", "reason": ""}, "改文案"],
            [{"type": "ask_closed", "kind": "permission", "by": "terminal", "verb": "allow", "text": "",
              "tool": "Bash", "what": "npm test", "reason": ""}, "加测试依赖"],
            [{"type": "ask_closed", "kind": "question", "by": "terminal", "verb": "answer", "text": "",
              "tool": "AskUserQuestion", "what": "Which port?", "reason": ""}, "登录页"],
            [{"type": "ask_closed", "kind": "permission", "by": "terminal", "verb": "closed", "text": "",
              "tool": "Bash", "what": "npm test", "reason": ""}, "加测试依赖"],
        ]
        out = run_node(ASK_LINE_JS, {"fn": fn, "cases": cases})
        want = [
            ["清理构建", "要权限", "Bash", "rm -rf build/", "等你"],
            ["登录页", "问总督", "Which port?"],
            ["登录页", "Which port?", "等你"],
            ["改文案", "总督", "60", "等你"],
            ["改文案", "定不了"],
            ["总督", "登录页", "4791"],
            ["你", "批准", "清理构建", "rm -rf build/"],
            ["你", "拒绝", "改文案", "/etc/hosts", "不许改系统文件"],
            ["你", "拒绝", "改文案", "/etc/hosts"],
            ["终端", "批准", "加测试依赖", "npm test"],
            ["终端", "已回答", "登录页"],
            ["终端", "加测试依赖", "npm test"],
        ]
        for i, (line, parts) in enumerate(zip(out, want)):
            with self.subTest(case=i, line=line):
                self.assertIsInstance(line, str)
                for part in parts:
                    self.assertIn(part, line)
                self.assertNotIn("批了", line)
        self.assertNotIn("理由：", out[8], "a deny without a reason must not show one")
        self.assertNotIn("你", out[9])
        self.assertIn("“4791”", out[5], "real text goes in “ ” like the rest of the page")
        for word in ("批准", "拒绝", "回答"):
            self.assertNotIn(word, out[11], "closed in the terminal is not an approval, denial or answer")

    def test_closed_line(self):
        fn = function_source("askClosedLine")
        self.assertIsNotNone(fn, "function askClosedLine(view) not found")
        esc = function_source("esc") or "const esc = s => String(s).replace(/[&<>\"]/g, ch => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '\"':'&quot;' }[ch]));"
        at = 1790000000000
        def v(kind, by, verb, text="", reason=""):
            return {"id": "a1", "kind": kind, "tool": "Bash", "what": "npm test",
                    "closed": {"by": by, "verb": verb, "text": text, "reason": reason, "at": at}}
        cases = [
            v("permission", "terminal", "closed"),
            v("question", "terminal", "closed"),
            v("permission", "owner", "closed"),
            v("permission", "owner", "allow"),
            v("permission", "owner", "deny", reason="keep dist/"),
            v("question", "owner", "answer", text="4791"),
            v("question", "governor", "answer", text="4791"),
            v("permission", "terminal", "allow"),
        ]
        js = ("const fs = require('fs'); const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));\n"
              + esc + "\n" + fn + "\n"
              + "process.stdout.write(JSON.stringify(data.map(x => askClosedLine(x).replace(/<[^>]+>/g, ''))));")
        out = run_node(js, cases)
        for i in (0, 1, 2):
            for word in ("批准", "拒绝", "回答"):
                with self.subTest(case=i, word=word):
                    self.assertNotIn(word, out[i])
        self.assertIn("终端", out[0])
        self.assertIn("晚了一步", out[0])
        self.assertIn("批准", out[3])
        self.assertNotIn("晚了一步", out[3])
        self.assertIn("keep dist/", out[4])
        self.assertIn("“4791”", out[5])
        self.assertIn("总督", out[6])
        self.assertIn("晚了一步", out[6])
        self.assertIn("终端", out[7])
        self.assertIn("批准", out[7])

    def test_failures_are_said_not_swallowed(self):
        body = function_source("decide") or ""
        self.assertTrue(body, "function decide(...) not found")
        self.assertNotRegex(body, r"catch\s*\(\s*\w*\s*\)\s*\{\s*(/\*.*?\*/)?\s*\}",
                            "a failed decision must be shown in the panel")
        self.assertRegex(body, r"\.ok\b|status\s*[!<>]=?", "non-409 errors must be handled too")



# ---------------------------------------------------------------------------
# Growth: the page draws the server's world
# ---------------------------------------------------------------------------

GROWTH_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const view = { cell: 26, x0: -3, z0: -2, w: 7, h: 5, rows: [
  '..w....',
  '..w.gg.',
  '..B.gH.',
  '..w....',
  ' .w..s ' ], territories: [], links: [] };
const box = Object.assign({ Math, JSON, console, occupied: new Map(), blocked: new Set(), map: view });
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const out = {};
out.tiles = [[-3, -2], [-1, -2], [-1, 0], [2, 0], [0, -10], [3, 2], [-3, 2], [2, 2], [1, -1]].map(([x, z]) => box.tileAt(x, z));
out.walk = [[-3, -2], [-1, -2], [-1, 0], [2, 0], [0, -10], [2, 2], [1, -1], [0, 1]].map(([x, z]) => !!box.walkable(x, z));
box.occupied.set('0,-1', { id: 1 });
out.walkOccupied = !!box.walkable(0, -1);
box.occupied.clear();
box.blocked.add('0,-1');
out.walkBlocked = !!box.walkable(0, -1);
box.blocked.clear();
const p = box.findPath(-1.5, -1.5, 0.5, -1.5);
out.path = p;
out.pathUsesBridge = !!(p && p.some(([x, z]) => Math.floor(x) === -1 && Math.floor(z) === 0)); // a point on the bridge tile (city-people: finer walk grid)
box.map = Object.assign({}, view, { rows: view.rows.map(r => r.replace('B', 'w')) });
out.noBridge = box.findPath(-1.5, -1.5, 0.5, -1.5);
process.stdout.write(JSON.stringify(out));
"""


def growth_results():
    """city-people: findPath now walks a fine grid built from every model's footprint, so this runs the
    whole simulation section (tests/test_agent_city_people.py run_sim), not a hand-picked function list."""
    if "growth" not in _CACHE:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import test_agent_city_people as tpp
        driver = r"""
const view = { cell: 26, x0: -3, z0: -2, w: 7, h: 5, rows: [
  '..w....',
  '..w.gg.',
  '..B.gH.',
  '..w....',
  ' .w..s ' ], territories: [], links: [] };
landState(view);
const out = {};
out.tiles = [[-3, -2], [-1, -2], [-1, 0], [2, 0], [0, -10], [3, 2], [-3, 2], [2, 2], [1, -1]].map(([x, z]) => tileAt(x, z));
out.walk = [[-3, -2], [-1, -2], [-1, 0], [2, 0], [0, -10], [2, 2], [1, -1], [0, 1]].map(([x, z]) => !!walkable(x, z));
occupied.set('0,-1', { id: 1 });
out.walkOccupied = !!walkable(0, -1);
occupied.clear();
blocked.add('0,-1');
out.walkBlocked = !!walkable(0, -1);
blocked.clear();
landState(view);
const p = findPath(-1.5, -1.5, 0.5, -1.5);
out.path = p;
// the straight legs of the path (start first): they cross the river on the bridge tile, never on water
const legs = p ? [[-1.5, -1.5]].concat(p) : [];
const onTile = [];
for (let i = 1; i < legs.length; i++) {
  const [ax, az] = legs[i - 1], [bx, bz] = legs[i], n = Math.max(1, Math.ceil(Math.hypot(bx - ax, bz - az) / .05));
  for (let k = 0; k <= n; k++) onTile.push(tileAt(Math.floor(ax + (bx - ax) * k / n), Math.floor(az + (bz - az) * k / n)));
}
out.pathUsesBridge = onTile.includes('B') && !onTile.includes('w');
landState(Object.assign({}, view, { rows: view.rows.map(r => r.replace('B', 'w')) }));
out.noBridge = findPath(-1.5, -1.5, 0.5, -1.5);
__out = out;
"""
        _CACHE["growth"] = tpp.run_sim(driver, {}, ("landState", "tileAt", "walkable", "findPath", "occupied", "blocked"))
    return _CACHE["growth"]


def const_object(name):
    """The JSON-like literal of `const NAME = {...};` (keys may be bare words)."""
    text = inline_script()
    m = re.search(r"^const %s = " % re.escape(name), text, re.M)
    if not m:
        return None
    i = m.end()
    depth = 0
    for j in range(i, len(text)):
        if text[j] in "{[":
            depth += 1
        elif text[j] in "}]":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    return None


def js_value(literal):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not installed")
    result = subprocess.run([node, "-e", "process.stdout.write(JSON.stringify(%s))" % literal],
                            capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise AssertionError(result.stderr[-2000:])
    return json.loads(result.stdout)


REST_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
// a territory whose hall sits at (0, 0), plots (P) on some tiles right beside the plaza
const rows = [
  '.........',
  '..ggggg..',
  '..ggrgg..',
  '..gHHgg..',
  '..gHHgg..',
  '.PggrgPP.',
  '..PgPgg..',
  '..ggPg...',
  '.........' ];
const view = { cell: 26, x0: -4, z0: -4, w: 9, h: 9, rows, territories: [{ id: 't1', cx: 0, cz: 0 }], links: [] };
const box = Object.assign({ Math, JSON, console, occupied: new Map(), blocked: new Set(), map: view, restSlotsByTerr: new Map(), homeSlotsByTerr: new Map() });
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const slots = box.restSlotsFor(view.territories[0]);
process.stdout.write(JSON.stringify({ spots: slots.map(r => [r.x, r.y, box.tileAt(Math.floor(r.x), Math.floor(r.y)), !!box.walkable(Math.floor(r.x), Math.floor(r.y))]) }));
"""


DECOR_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const rows = [
  '.........',
  '..ggggg..',
  '..ggrgg..',
  '..gHHgg..',
  '..gHHgg..',
  '.PggrgPP.',
  '..PgPgg..',
  '..ggPg...',
  '.........' ];
const view = { cell: 26, x0: -4, z0: -4, w: 9, h: 9, rows, territories: [], links: [] };
const box = Object.assign({ Math, JSON, console, occupied: new Map(), blocked: new Set(), map: view });
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const ch = (x, z) => { const r = Math.floor(z) - view.z0, c = Math.floor(x) - view.x0; return r >= 0 && r < view.h && c >= 0 && c < view.w ? rows[r][c] : ' '; };
const t0 = { id: 't', cx: 0, cz: 0, open: 0, size: 0 }, t1 = { id: 't', cx: 0, cz: 0, open: 6, size: .4 };
const t2 = { id: 't', cx: 0, cz: 0, open: 6, size: .4, era: 'town' };
process.stdout.write(JSON.stringify({
  day0: box.hallDecor(t0, view),
  grown: box.hallDecor(t1, view).map(d => [d.key, d.x, d.z, ch(d.x, d.z)]),
  town: box.hallDecor(t2, view).map(d => [d.key, d.x, d.z, ch(d.x, d.z)]),
}));
"""


class TestOneLand(unittest.TestCase):
    """E2E bounce G1-G4 (the ground itself: tests/test_agent_city_land.py)."""

    def test_the_first_view_is_a_town_hall(self):
        text = inline_script()
        snap = re.search(r"case 'snapshot':(.*?)(?=case '\w+':)", text, re.S).group(1)
        self.assertTrue("resetCam()" in snap or "resetCam()" in (function_source("buildLand") or ""),
                        "the first world must put the camera home (resetCam), not leave it on the land's middle")
        body = snap + (function_source("buildLand") or "")
        once = re.search(r"if \(!(\w+)[^\n]*?\)\s*\{\s*\1 = true;\s*resetCam\(\);", body) or \
            re.search(r"if \(!(\w+)[^\n]*?\)\s*\{\s*resetCam\(\);\s*\1 = true;", body)
        self.assertIsNotNone(once, "only the FIRST world goes home: a later world (a new territory, a recount) "
                                   "must not snap the camera back or stop the auto-rotation's turn")

    def test_day_zero_is_bare(self):
        rest_off = const_object("REST_OFF")
        src = function_source("hallDecor")
        self.assertIsNotNone(src, "function hallDecor(t, view) not found")
        fns = [src]
        for name in ("tileAt", "walkable"):
            if function_source(name):
                fns.append(function_source(name))
        for name in ("eraShown", "showOf"):
            if function_source(name):
                fns.append(function_source(name))
        out = run_node(DECOR_JS, {"prelude": constants_prelude() + "\nvar shows = new Map();", "fns": "\n".join(fns)})
        self.assertEqual(out["day0"], [], "day 0: nothing but the town hall")
        self.assertEqual(out["grown"], [], "Balance: a village has no lamps, and the fountain comes from beauty only")
        self.assertTrue(out["town"], "a town gets its lamps")
        for key, x, z, ch in out["town"]:
            with self.subTest(decor=key):
                self.assertEqual(ch, "g", "%s stands on %r at %s" % (key, ch, (x, z)))
                self.assertNotIn("fountain", key, "the fountain is beauty's (systemsDecor), never hallDecor's")
        self.assertIn("hallDecor(", function_source("buildLand") or "")
        self.assertNotRegex(function_source("buildLand") or "", r"place\('fountain-round', t\.cx")

    def test_home_is_the_square_in_front_of_the_hall(self):
        """Final screenshots: with home on the hall's own centre the hall stood in the view line and faded."""
        src = function_source("updateHome")
        self.assertIsNotNone(src)
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const t = { id: 't', cx: 26, cz: -26, open: 3 };
const box = { Math, JSON, console, map: { territories: [t] }, mid: { x: 13, z: -13 }, govTerr: null, gov: {}, home: null,
  terrOf: id => (id === 't' ? t : null), hallStand: () => ({ x: 26, y: -24 }) };
vm.createContext(box);
vm.runInContext(fns + '\nupdateHome();', box);
process.stdout.write(JSON.stringify({ home: box.home }));
"""
        out = run_node(js, {"fns": src})
        home = out["home"]
        self.assertLessEqual(abs(home["x"] - (26 - 13)), 0.5)
        self.assertGreaterEqual(home["z"] - (-26 + 13), 1.5, "look at the square south of the hall, not into it")
        self.assertLessEqual(home["z"] - (-26 + 13), 3.0)

    def test_the_home_view_is_a_town_hall(self):
        self.assertRegex(function_source("buildLand") or "", r"updateHome\(\)")


class TestGrowthPage(unittest.TestCase):
    def test_nobody_rests_inside_a_building(self):
        # city-people: rest spots now depend on homes, the governor's stand and the walk grid, so this runs
        # the whole simulation section (tests/test_agent_city_people.py run_sim) on the same small territory
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import test_agent_city_people as tpp
        driver = r"""
const rows = [
  '.........',
  '..ggggg..',
  '..ggrgg..',
  '..gHHgg..',
  '..gHHgg..',
  '.PggrgPP.',
  '..PgPgg..',
  '..ggPg...',
  '.........' ];
const view = { cell: 26, x0: -4, z0: -4, w: 9, h: 9, rows, links: [],
  territories: [{ id: 't1', cx: 0, cz: 0, slot: [0, 0], terrain: 'grassland', era: 'village', plots: [], buildings: [] }] };
landState(view);
const slots = restSlotsFor(view.territories[0]);
__out = { spots: slots.map(r => [r.x, r.y, tileAt(Math.floor(r.x), Math.floor(r.y)), !!walkable(Math.floor(r.x), Math.floor(r.y))]) };
"""
        out = tpp.run_sim(driver, {}, ("landState", "restSlotsFor", "tileAt", "walkable"))
        self.assertGreaterEqual(len(out["spots"]), 3, out)
        for x, z, ch, ok in out["spots"]:
            with self.subTest(spot=(x, z)):
                self.assertTrue(ok, "a rest spot on %r at %s" % (ch, (x, z)))

    def test_old_fixed_island_is_gone(self):
        text = inline_script()
        for name in ("const PLOTS", "const GX1", "const BRIDGE_X", "function demolishOldest", "function removeBuilding",
                     "function buildIsland"):
            with self.subTest(name=name):
                self.assertNotIn(name, text)

    def test_land_and_home_are_top_level(self):
        text = inline_script()
        self.assertRegex(text, r"(?m)^let land = \{", "let land = {hx, hz}")
        self.assertRegex(text, r"(?m)^let home = \{")
        self.assertRegex(text, r"(?m)^let map = ")

    def test_demo_world_is_the_servers(self):
        literal = const_object("DEMO_WORLD")
        self.assertIsNotNone(literal, "const DEMO_WORLD = {...}; not found")
        out = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "agent_city.py"), "demo-world"],
                             capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(literal), json.loads(out.stdout))

    def test_tiles_walking_and_bridges(self):
        g = growth_results()
        self.assertEqual(g["tiles"], [".", "w", "B", "H", " ", " ", " ", "s", "g"])
        self.assertEqual(g["walk"], [True, False, True, False, False, False, True, True])
        self.assertFalse(g["walkOccupied"])
        self.assertFalse(g["walkBlocked"])
        self.assertTrue(g["path"], "no way over the river")
        self.assertTrue(g["pathUsesBridge"], "the way over the river is the bridge")
        self.assertIsNone(g["noBridge"], "walked through a river")

    def test_building_models_per_type(self):
        look = js_value(const_object("ERA_LOOK") or "null")
        self.assertIsInstance(look, dict, "Balance: const ERA_LOOK = {village, town, city} replaces BUILD_MODELS")
        names = {m.split("/")[1] for m in models()}
        for era in ("village", "town", "city"):
            b = look[era]["build"]
            self.assertEqual(set(b), {"house", "shop", "tower", "workshop", "library"})
            for typ, keys in b.items():
                with self.subTest(era=era, type=typ):
                    self.assertTrue(keys)
                    self.assertLessEqual(set(keys), names)

    def test_type_names_in_chinese(self):
        self.assertEqual(js_value(const_object("TYPE_ZH") or "null"),
                         {"house": "住宅", "shop": "商店", "tower": "测试塔", "workshop": "工坊", "library": "图书馆"})

    def test_terrain_changes_the_look(self):
        look = js_value(const_object("TERRAIN_LOOK") or "null")
        self.assertIsInstance(look, dict)
        self.assertEqual(set(look), {"grassland", "mountain", "desert", "forest", "coast"})
        names = {m.split("/")[1] for m in models()}
        for t, v in look.items():
            with self.subTest(terrain=t):
                self.assertRegex(v["ground"], r"^#[0-9A-Fa-f]{6}$")
                self.assertRegex(v.get("wild", ""), r"^#[0-9A-Fa-f]{6}$", "wild land has its own colour")
                self.assertNotEqual(v["wild"].lower(), v["ground"].lower(), "claimed land must read apart from wild land")
                self.assertRegex(v["path"], r"^#[0-9A-Fa-f]{6}$")
                self.assertTrue(v["plants"])
                self.assertLessEqual(set(v["plants"]), names)
        self.assertTrue(any("cactus" in n for n in look["desert"]["plants"]))
        self.assertTrue(any("pine" in n for n in look["mountain"]["plants"]))
        self.assertTrue(any("palm" in n for n in look["coast"]["plants"]))
        self.assertNotEqual(look["coast"]["path"].lower(), look["grassland"]["path"].lower())
        self.assertNotEqual(look["desert"]["ground"].lower(), look["grassland"]["ground"].lower())

    def test_gap_models(self):
        names = " ".join(models())
        self.assertIn("bridge", names)
        self.assertRegex(names, r"rock")

    def test_world_and_build_events_drive_the_page(self):
        text = inline_script()
        build = re.search(r"case 'build':(.*?)(?=case '\w+':)", text, re.S)
        self.assertIsNotNone(build)
        for key in ("ev.x", "ev.z", "ev.btype"):
            self.assertIn(key, build.group(1))
        spawn = re.search(r"case 'spawn':(.*?)(?=case '\w+':)", text, re.S)
        self.assertIn("ev.terr", spawn.group(1))
        snap = re.search(r"case 'snapshot':(.*?)(?=case '\w+':)", text, re.S)
        self.assertIn(".world", snap.group(1))
        self.assertIn(".notice", snap.group(1))

    def test_a_town_hall_for_every_territory(self):
        body = function_source("buildLand") or ""
        self.assertRegex(body, r"eraLook\(|ERA_LOOK\[", "the hall model follows the era (Balance)")
        self.assertRegex(body, r"for \(const \w+ of [\w.]*territories\)")


# ---------------------------------------------------------------------------
# Balance (requirements/city.md "Balance"; approved mock mock/city-balance-mock.html;
# server side: tests/test_agent_city_balance.py)
#
#   Constants  KIND_ZH {build 建设, rules 规则, beauty 美化, knowledge 知识, infra 基建}
#              STATE_ZH {healthy 健康, low 偏低, missing 没有, na 不适用}
#              ERA_ZH {village 村, town 镇, city 城}; SHOW_SEC = 60, SHOW_FLIP = 52
#   ERA_LOOK = {village|town|city: {build: {house, shop, tower, workshop, library:
#     [model names]}, hall: model name, road: '#hex', lamps: bool}}. Village =
#     wood, town = brick, city = towers: the three eras' house lists share no
#     model; city's tower list has a skyscraper; lamps only town and city.
#     eraLook(t) = ERA_LOOK[eraShown(t)].
#   roadColor(t): village -> TERRAIN_LOOK[t.terrain].path, town and city ->
#     ERA_LOOK[era].road (all three differ). laneGeometry colours the lanes
#     on 'r' tiles with it (tests/test_agent_city_land.py).
#   hallDecor(t, view): [] on day 0 and in a village; lamps ('lantern') in a
#     town or city, on 'g' tiles. Never a fountain (that is beauty's).
#   signText(t) -> '' on day 0 (no lines), in the city era, with no "next", or
#     while t's era show runs; else '还差：' + t.next.join('、'). Drawn as an
#     overlay (.era-sign) in front of each town hall.
#   balanceHtml(t, open, terrs) -> the 城市平衡 card body (#balance):
#     era line (时代 <ERA_ZH> -> next era, with the sign text; 已经是城 in the
#     city era), then <li class="kind" data-kind=K data-state=S> for the 5
#     kinds in KINDS order, each with a <button type="button"
#     aria-expanded> showing KIND_ZH, a bar, STATE_ZH and t.balance[K].text.
#     t.balance {} -> every kind data-state="missing" with 还没数过.
#     open = {kind, files, total, rules, error} opens that kind: its paths
#     (escaped), 还有 N 个 when total > files.length, and the fix hint naming
#     the rules file (分错了？ ... = none); files null -> 正在拿文件列表…;
#     error -> 文件列表拿不到： + error (never silent). t.rules_note shown.
#     terrs [{id, name}] with more than one -> a button per territory
#     (data-bterr=id, aria-pressed on the shown one).
#   openBalanceKind(kind): live -> fetch('/api/balance?terr=' + id + '&kind='
#     + kind) with the X-City-Token header; a failure is shown in the card.
#     Demo -> no fetch, 演示：没有真实文件.
#   systemsDecor(t, view) -> [{key ('<pack>/<name>' in MODELS), x, z, kind}]:
#     [] on day 0 (t.open 0) or with no balance; nothing for a missing or na
#     kind (absent, never broken: no cones, no cracks); every item on its own
#     'g' tile, none on a hallDecor tile. rules: signposts and a police
#     station, traffic lights too when healthy; beauty: flowers, and a park
#     and the fountain ('fantasy/fountain-round') when healthy; knowledge: a
#     library and district name signs; infra: a water tower, and a power
#     plant when healthy. A healthy kind never has fewer items than low.
#   trackColor(t): TRACK_COLOR, paved (another colour) when infra is healthy.
#   Era show: case 'era' -> startShow(ev.terr, ev.from, ev.to, ev.left);
#     the snapshot starts each of ev.shows with left > 0. startShow only
#     records {from, to, end: performance.now() + left*1000} in the Map
#     `shows` and asks for a frame. eraShown(t): t's show running and less
#     than SHOW_FLIP s in -> from, else t.era (village by default). The flip
#     is one moment: every building, road and lamp of t changes together.
#     showPlan(t, view, to) -> {builders, targets: [{x, z, what}]}: every
#     building of t (what 'building'), every 2nd road tile of t ('road'),
#     the lamps of the new era ('lamp', none for a village); builders =
#     clamp(ceil(targets / 3), 6, 24). Builders are not citizens: never in
#     the roster or the top counts.
# ---------------------------------------------------------------------------

KINDS = ["build", "rules", "beauty", "knowledge", "infra"]


def balance_card_results():
    if "bcards" not in _CACHE:
        section = cards_section()
        if section is None:
            raise AssertionError("no `/* ---------- right column` section in the page script")
        js = HARNESS_JS.replace(
            "[['detail', '详情', 'detail', 'div'], ['citizens', '市民', 'roster', 'ul'], ['log', '动态', 'log', 'ol']]",
            "[['detail', '详情', 'detail', 'div'], ['balance', '城市平衡', 'balance', 'div'], "
            "['citizens', '市民', 'roster', 'ul'], ['log', '动态', 'log', 'ol']]")
        js = js.replace("inPanel: panel.children.length === 3", "inPanel: panel.children.length === 4")
        start = js.index("(async () => {")
        js = js[:start] + r"""(async () => {
  const out = {};
  let w = world();
  out.fresh = w.state();
  w.click('balance'); await w.tick(); out.collapsed = w.state();
  w = world(JSON.stringify({ order: ['log', 'detail', 'citizens'], collapsed: ['log'] })); out.oldSave = w.state();
  w = world(JSON.stringify({ order: ['balance', 'log', 'detail', 'citizens'], collapsed: ['balance'] })); out.restored = w.state();
  w = world(); await w.drag('balance', [100, 60, 30, 10, 0]); out.dragged = w.state();
  process.stdout.write(JSON.stringify(out));
})().catch(e => { process.stdout.write(JSON.stringify({ fatal: String(e && e.stack || e) })); });
"""
        _CACHE["bcards"] = run_node(js, {"prelude": constants_prelude(), "section": section})
        if "fatal" in _CACHE["bcards"]:
            raise AssertionError("card harness crashed: " + _CACHE["bcards"]["fatal"])
    return _CACHE["bcards"]


def page_fns(*names, optional=()):
    fns = []
    for name in names:
        src = function_source(name)
        if src is None:
            raise AssertionError("function %s(...) not found in the page script" % name)
        fns.append(src)
    for name in optional:
        src = function_source(name)
        if src:
            fns.append(src)
    return "\n".join(fns)


def consts(*names):
    out = []
    for name in names:
        lit = const_object(name)
        if lit is None:
            raise AssertionError("const %s = {...}; not found in the page script" % name)
        out.append("var %s = %s;" % (name, lit))
    return "\n".join(out)


BAL = {"build": {"state": "healthy", "value": 4200, "n": 12, "text": "4,200 行代码"},
       "rules": {"state": "missing", "value": 0, "n": 0, "text": "还没有"},
       "beauty": {"state": "low", "value": 1, "n": 2, "text": "1 个组件，平均复用 1.0 次"},
       "knowledge": {"state": "na", "value": 0, "n": 0, "text": "这个仓库不用这一类"},
       "infra": {"state": "healthy", "value": 8, "n": 8, "text": "8 个文件"}}

CARD_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, DEMO: false, shows: new Map(), performance: { now: () => 0 }, map: { territories: [] } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
process.stdout.write(JSON.stringify(cases.map(([t, open, terrs]) => box.balanceHtml(t, open, terrs))));
"""


class TestBalanceCard(unittest.TestCase):
    def test_markup(self):
        found = dict(cards())
        self.assertIn("balance", found)
        inner = found["balance"]
        self.assertIn("城市平衡", inner)
        self.assertRegex(inner, r'<svg class="grip"', "same grip as the other cards")
        self.assertRegex(inner, r'<[a-z]+ class="[^"]*\bcard-body\b[^"]*" id="balance"')

    def test_same_collapse_drag_and_memory_as_the_other_cards(self):
        r = balance_card_results()
        self.assertEqual(r["fresh"]["errors"], [])
        self.assertEqual(r["fresh"]["order"], ["detail", "balance", "citizens", "log"])
        self.assertEqual(r["collapsed"]["collapsed"], ["balance"])
        self.assertEqual(json.loads(r["collapsed"]["stored"])["collapsed"], ["balance"])
        self.assertEqual(r["oldSave"]["order"], ["log", "detail", "citizens", "balance"],
                         "a browser that saved the 3-card order still gets the new card")
        self.assertEqual(r["oldSave"]["collapsed"], ["log"])
        self.assertEqual(r["restored"]["order"], ["balance", "log", "detail", "citizens"])
        self.assertEqual(r["restored"]["collapsed"], ["balance"])
        self.assertEqual(r["dragged"]["order"][0], "balance")
        self.assertEqual(r["dragged"]["errors"], [])

    def test_names_in_chinese(self):
        self.assertEqual(js_value(const_object("KIND_ZH") or "null"),
                         {"build": "建设", "rules": "规则", "beauty": "美化", "knowledge": "知识", "infra": "基建"})
        self.assertEqual(js_value(const_object("STATE_ZH") or "null"),
                         {"healthy": "健康", "low": "偏低", "missing": "没有", "na": "不适用"})
        self.assertEqual(js_value(const_object("ERA_ZH") or "null"), {"village": "村", "town": "镇", "city": "城"})

    def card(self, *cases):
        fns = page_fns("balanceHtml", optional=("signText", "eraShown", "showOf", "kindBar", "barOf"))
        esc = re.search(r"^const esc = .*;$", inline_script(), re.M)
        prelude = constants_prelude() + "\n" + consts("KIND_ZH", "STATE_ZH", "ERA_ZH") + "\n" + \
            (esc.group(0).replace("const esc", "var esc") if esc else "")
        return run_node(CARD_JS, {"prelude": prelude, "fns": fns, "cases": [list(c) for c in cases]})

    def test_one_bar_per_kind(self):
        t = {"id": "t1", "name": "shop", "era": "village", "lines": 4200, "open": 6, "balance": BAL,
             "next": ["规则"], "rules_note": ""}
        html = self.card((t, None, [{"id": "t1", "name": "shop"}]))[0]
        self.assertEqual(re.findall(r'data-kind="(\w+)"', html), KINDS)
        self.assertEqual(re.findall(r'data-state="(\w+)"', html), ["healthy", "missing", "low", "na", "healthy"])
        for word in ("建设", "规则", "美化", "知识", "基建", "健康", "没有", "偏低", "不适用", "4,200 行代码",
                     "1 个组件，平均复用 1.0 次", "村", "还差：规则"):
            with self.subTest(word=word):
                self.assertIn(word, html)
        self.assertNotIn('class="files', html, "no list until a kind is clicked")
        self.assertEqual(len(re.findall(r'<button type="button"[^>]*aria-expanded="false"', html)), 5)
        self.assertNotIn("data-bterr", html, "one territory: no picker")

    def test_a_clicked_kind_lists_its_files(self):
        t = {"id": "t1", "name": "shop", "era": "town", "lines": 9000, "open": 6, "balance": BAL,
             "next": ["规模", "美化"], "rules_note": ""}
        opened = {"kind": "infra", "files": [".github/workflows/ci.yml", "scripts/<b>x</b>.sh"], "total": 7,
                  "rules": "/Users/me/.claude/agent-city/rules/shop.conf", "error": ""}
        loading = dict(opened, files=None)
        failed = dict(opened, files=None, error="HTTP 403")
        html, wait, err = self.card((t, opened, []), (t, loading, []), (t, failed, []))
        self.assertIn(".github/workflows/ci.yml", html)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)
        self.assertNotIn("<b>x</b>", html)
        self.assertIn("还有 5 个", html)
        self.assertIn("rules/shop.conf", html)
        self.assertIn("分错了", html)
        self.assertIn("= none", html)
        self.assertRegex(html, r'data-kind="infra"[^>]*>\s*<button type="button"[^>]*aria-expanded="true"')
        self.assertIn("正在拿文件列表", wait)
        self.assertIn("文件列表拿不到：HTTP 403", err)

    def test_before_the_first_count(self):
        t = {"id": "t1", "name": "shop", "era": "village", "lines": 0, "open": 0, "balance": {}, "next": [],
             "rules_note": ""}
        html = self.card((t, None, []))[0]
        self.assertEqual(re.findall(r'data-state="(\w+)"', html), ["missing"] * 5)
        self.assertIn("还没数过", html)
        self.assertNotIn("还差", html, "day 0 is clean")

    def test_city_rules_note_and_territory_picker(self):
        t = {"id": "t2", "name": "big", "era": "city", "lines": 90000, "open": 30, "balance": BAL, "next": [],
             "rules_note": "big.conf 第 3 行看不懂，已跳过"}
        html = self.card((t, None, [{"id": "t1", "name": "shop"}, {"id": "t2", "name": "big"}]))[0]
        self.assertIn("已经是城", html)
        self.assertNotIn("还差", html)
        self.assertIn("big.conf 第 3 行看不懂", html)
        self.assertEqual(re.findall(r'data-bterr="(\w+)"', html), ["t1", "t2"])
        self.assertRegex(html, r'data-bterr="t2"[^>]*aria-pressed="true"|aria-pressed="true"[^>]*data-bterr="t2"')

    def test_clicking_a_kind_asks_the_server(self):
        src = function_source("openBalanceKind")
        self.assertIsNotNone(src, "function openBalanceKind(kind) not found")
        self.assertIn("'/api/balance?terr='", src)
        self.assertIn("'X-City-Token': TOKEN", src)
        self.assertIn("encodeURIComponent", src)
        self.assertRegex(src, r"if \(DEMO\)[^;]*", "demo mode never fetches")
        self.assertIn("演示：没有真实文件", inline_script())
        self.assertRegex(src, r"catch|\.ok", "a failed fetch is shown, never swallowed")


SIGN_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, shows: new Map(), performance: { now: () => 1000 } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const out = cases.map(t => box.signText(t));
box.shows.set('t9', { from: 'village', to: 'town', end: 1000 + 30000 });
out.push(box.signText({ id: 't9', era: 'town', lines: 5000, next: ['规模'] }));
process.stdout.write(JSON.stringify(out));
"""


class TestEraLook(unittest.TestCase):
    def test_sign_text(self):
        cases = [{"id": "a", "era": "village", "lines": 4200, "next": ["规则"]},
                 {"id": "b", "era": "town", "lines": 9000, "next": ["规模", "美化"]},
                 {"id": "c", "era": "village", "lines": 0, "next": ["规模"]},
                 {"id": "d", "era": "city", "lines": 90000, "next": []},
                 {"id": "e", "era": "town", "lines": 9000, "next": []}]
        out = run_node(SIGN_JS, {"prelude": constants_prelude(),
                                 "fns": page_fns("signText", optional=("eraShown", "showOf")), "cases": cases})
        self.assertEqual(out, ["还差：规则", "还差：规模、美化", "", "", "", ""],
                         "no sign on day 0, in the city, with nothing needed, or during the show")
        self.assertIn(".era-sign", style())
        self.assertIn("era-sign", inline_script())

    def test_era_look(self):
        look = js_value(const_object("ERA_LOOK") or "null")
        self.assertIsInstance(look, dict)
        self.assertEqual(set(look), {"village", "town", "city"})
        names = {m.split("/")[1] for m in models()}
        houses = {}
        for era, v in look.items():
            with self.subTest(era=era):
                self.assertIn(v["hall"], names)
                self.assertRegex(v["road"], r"^#[0-9A-Fa-f]{6}$")
                self.assertIs(v["lamps"], era != "village")
                houses[era] = set(v["build"]["house"])
        self.assertFalse(houses["village"] & houses["town"], "village is wood, town is brick: other models")
        self.assertFalse(houses["town"] & houses["city"])
        self.assertFalse(houses["village"] & houses["city"])
        self.assertTrue(any("skyscraper" in k for k in look["city"]["build"]["tower"]))
        self.assertNotEqual(look["town"]["road"].lower(), look["city"]["road"].lower())
        self.assertNotEqual(look["village"]["hall"], look["city"]["hall"])

    def test_road_colour_follows_the_era(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, shows: new Map(), performance: { now: () => 0 } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
process.stdout.write(JSON.stringify(['village', 'town', 'city', undefined].map(era => box.roadColor({ id: 'x', terrain: 'coast', era }))));
"""
        prelude = constants_prelude() + "\n" + consts("TERRAIN_LOOK", "ERA_LOOK")
        out = run_node(js, {"prelude": prelude, "fns": page_fns("roadColor", optional=("eraShown", "showOf", "eraLook"))})
        look = js_value(const_object("ERA_LOOK"))
        terrain = js_value(const_object("TERRAIN_LOOK"))
        self.assertEqual([c.lower() for c in out],
                         [terrain["coast"]["path"].lower(), look["town"]["road"].lower(),
                          look["city"]["road"].lower(), terrain["coast"]["path"].lower()])
        self.assertTrue("roadColor(" in (function_source("laneGeometry") or ""), "laneGeometry colours roads with roadColor")

    def test_versioned_assets_and_the_hall(self):
        self.assertIn("function eraLook(", inline_script())
        self.assertIn("function eraShown(", inline_script())


SYS_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
// one territory, hall at (-1..0, -1..0); roads x = 2 and z = 2 and a ring at 6; plots beside the roads
const N = 10, rows = [];
for (let z = -N; z <= N; z++) {
  let row = '';
  for (let x = -N; x <= N; x++) {
    const d = Math.hypot(x + .5, z + .5);
    let c = d > 9.2 ? '.' : 'g';
    if (c === 'g' && (x === 2 || z === 2 || Math.abs(x) === 6 || Math.abs(z) === 6)) c = 'r';
    if (c === 'g' && (x === 3 || x === 1 || z === 3 || z === 1) && (x + z) % 3 === 0) c = 'P';
    if ((x === -1 || x === 0) && (z === -1 || z === 0)) c = 'H';
    row += c;
  }
  rows.push(row);
}
const view = { cell: 26, x0: -N, z0: -N, w: 2 * N + 1, h: 2 * N + 1, rows, territories: [], links: [] };
const box = { Math, JSON, console, occupied: new Map(), blocked: new Set(), map: view, shows: new Map(), performance: { now: () => 0 } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const ch = (x, z) => { const r = Math.floor(z) - view.z0, c = Math.floor(x) - view.x0; return r >= 0 && r < view.h && c >= 0 && c < view.w ? rows[r][c] : ' '; };
const out = {};
for (const [name, t] of Object.entries(cases)) {
  view.territories = [t];
  const items = box.systemsDecor(t, view);
  const hall = box.hallDecor(t, view).map(d => Math.floor(d.x) + ',' + Math.floor(d.z));
  out[name] = items.map(d => ({ key: d.key, kind: d.kind, ch: ch(d.x, d.z), tile: Math.floor(d.x) + ',' + Math.floor(d.z), onHall: hall.includes(Math.floor(d.x) + ',' + Math.floor(d.z)) }));
}
process.stdout.write(JSON.stringify(out));
"""


def systems_results():
    if "sys" not in _CACHE:
        def terr(**states):
            bal = {k: {"state": "missing", "value": 0, "n": 0, "text": "还没有"} for k in KINDS}
            for k, st in states.items():
                bal[k] = {"state": st, "value": 1, "n": 1, "text": ""}
            return {"id": "t", "name": "shop", "cx": 0, "cz": 0, "open": 8, "size": .6, "lines": 9000,
                    "era": "town", "terrain": "grassland", "balance": bal, "next": [], "buildings": []}
        cases = {"day0": dict(terr(build="healthy", rules="healthy"), open=0, lines=0),
                 "none": terr(), "nobalance": dict(terr(), balance={})}
        for k in KINDS[1:]:
            cases[k + "_low"] = terr(build="healthy", **{k: "low"})
            cases[k + "_healthy"] = terr(build="healthy", **{k: "healthy"})
            cases[k + "_na"] = terr(build="healthy", **{k: "na"})
        cases["all"] = terr(**{k: "healthy" for k in KINDS})
        fns = page_fns("systemsDecor", "hallDecor",
                       optional=("tileAt", "walkable", "eraShown", "showOf", "eraLook", "frontOf", "sr", "terrOf"))
        prelude = constants_prelude() + "\n" + consts("ERA_LOOK")
        _CACHE["sys"] = run_node(SYS_JS, {"prelude": prelude, "fns": fns, "cases": cases})
    return _CACHE["sys"]


class TestSystems(unittest.TestCase):
    def test_day_zero_and_missing_kinds_add_nothing(self):
        r = systems_results()
        self.assertEqual(r["day0"], [], "day 0 is clean empty land")
        self.assertEqual(r["none"], [], "a missing kind is absent")
        self.assertEqual(r["nobalance"], [])
        for k in KINDS[1:]:
            with self.subTest(kind=k):
                self.assertEqual(r[k + "_na"], [], "not applicable is absent too")

    def test_each_kind_brings_only_its_own_things(self):
        r = systems_results()
        for k in KINDS[1:]:
            for level in ("low", "healthy"):
                with self.subTest(kind=k, level=level):
                    items = r["%s_%s" % (k, level)]
                    self.assertTrue(items, "%s %s shows nothing" % (k, level))
                    self.assertEqual({d["kind"] for d in items}, {k})
            with self.subTest(kind=k, compare=True):
                self.assertGreaterEqual(len(r[k + "_healthy"]), len(r[k + "_low"]))
        self.assertGreater(len(r["rules_healthy"]), len(r["rules_low"]), "traffic lights come when rules is healthy")
        self.assertIn("fantasy/fountain-round", {d["key"] for d in r["beauty_healthy"]})
        self.assertNotIn("fantasy/fountain-round", {d["key"] for d in r["beauty_low"]})

    def test_every_thing_stands_on_its_own_ground_tile(self):
        r = systems_results()
        wanted = set(models())
        for name, items in r.items():
            tiles = [d["tile"] for d in items]
            with self.subTest(case=name):
                self.assertEqual(len(tiles), len(set(tiles)), "two things on one tile")
                for d in items:
                    self.assertEqual(d["ch"], "g", "%s on %r" % (d["key"], d["ch"]))
                    self.assertFalse(d["onHall"], "%s on a lamp's tile" % d["key"])
                    self.assertIn(d["key"], wanted, "%s is not a loaded model" % d["key"])

    def test_nothing_broken_ever(self):
        text = inline_script()
        body = function_source("systemsDecor") or ""
        for word in ("cone", "crack", "broken", "ruin"):
            with self.subTest(word=word):
                self.assertNotIn(word, body.lower())

    def test_paved_track_with_healthy_infra(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const t = st => ({ id: 't', balance: { infra: { state: st } } });
process.stdout.write(JSON.stringify([box.trackColor(t('healthy')), box.trackColor(t('low')), box.trackColor({ id: 'x', balance: {} }), box.TRACK_COLOR]));
"""
        out = run_node(js, {"prelude": constants_prelude(), "fns": page_fns("trackColor")})
        self.assertNotEqual(out[0].lower(), out[3].lower())
        self.assertEqual(out[1], out[3])
        self.assertEqual(out[2], out[3])


SHOW_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns, t, view } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let T = 0;
const box = { Math, JSON, console, shows: new Map(), performance: { now: () => T }, needFrame: false, DEMO: false,
  map: view, occupied: new Map(), blocked: new Set(), logAt(){}, dirty: {} };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const out = {};
const at = s => { T = s * 1000; return box.eraShown(t); };
box.startShow('t', 'village', 'town', 60);
out.frame = box.needFrame;
out.full = [at(0), at(10), at(51.5), at(52.5), at(61), at(300)];
T = 0; box.shows.clear();
box.startShow('t', 'village', 'town', 20);
out.joined = [at(0), at(11.5), at(12.5)];
const p = box.showPlan(t, view, 'town');
out.plan = { builders: p.builders, targets: p.targets.map(g => [g.what, g.x, g.z]) };
const pv = box.showPlan(Object.assign({}, t, { buildings: [] }), view, 'village');
out.village = pv.targets.filter(g => g.what === 'lamp').length;
process.stdout.write(JSON.stringify(out));
"""


class TestEraShow(unittest.TestCase):
    def test_constants_and_events(self):
        text = inline_script()
        self.assertRegex(text, r"const SHOW_SEC = 60\b")
        self.assertRegex(text, r"const SHOW_FLIP = 52\b")
        era = case_block("era")
        self.assertIsNotNone(era, "case 'era': not handled")
        self.assertRegex(era, r"startShow\(ev\.terr, ev\.from, ev\.to, ev\.left\)")
        snap = case_block("snapshot") or ""
        self.assertIn(".shows", snap)
        self.assertIn("startShow(", snap)
        self.assertRegex(snap, r"left > 0", "a finished show is never replayed")

    def show(self):
        if "show" not in _CACHE:
            rows = ["..........",
                    ".gggggggg.",
                    ".grrrrrrg.",
                    ".grgHHgrg.",
                    ".grgHHgrg.",
                    ".grPggPrg.",
                    ".grrrrrrg.",
                    ".gggggggg.",
                    ".........."]
            view = {"cell": 26, "x0": -4, "z0": -4, "w": 10, "h": 9, "rows": rows, "territories": [], "links": []}
            t = {"id": "t", "name": "shop", "cx": 0, "cz": 0, "open": 2, "size": .3, "lines": 3000, "era": "town",
                 "terrain": "grassland", "balance": {}, "next": [],
                 "buildings": [{"plot": 0, "type": "house", "by": "w", "x": -1, "z": 1},
                               {"plot": 1, "type": "shop", "by": "w", "x": 2, "z": 1}]}
            view["territories"] = [t]
            fns = page_fns("startShow", "eraShown", "showPlan", "hallDecor",
                           optional=("showOf", "tileAt", "walkable", "eraLook", "sr"))
            prelude = constants_prelude() + "\n" + consts("ERA_LOOK")
            _CACHE["show"] = run_node(SHOW_JS, {"prelude": prelude, "fns": fns, "t": t, "view": view})
        return _CACHE["show"]

    def test_the_flip_is_one_moment_after_52_s(self):
        r = self.show()
        self.assertTrue(r["frame"], "startShow asks for a frame")
        self.assertEqual(r["full"], ["village", "village", "village", "town", "town", "town"])
        self.assertEqual(r["joined"], ["village", "village", "town"], "a page opened 40 s in flips 12 s later")

    def test_builders_visit_every_building_road_and_lamp(self):
        plan = self.show()["plan"]
        whats = [w for w, _, _ in plan["targets"]]
        spots = [(x, z) for w, x, z in plan["targets"] if w == "building"]
        self.assertEqual(len(spots), 2, "one visit per building")
        for bx, bz in ((-1, 1), (2, 1)):
            with self.subTest(building=(bx, bz)):
                self.assertTrue(any(abs(x - bx - .5) <= 1.5 and abs(z - bz - .5) <= 1.5 for x, z in spots),
                                "no builder goes to the building at %s" % ((bx, bz),))
        self.assertGreaterEqual(whats.count("road"), 5)
        self.assertGreaterEqual(whats.count("lamp"), 1, "a town gets lamps: the builders put them up")
        self.assertEqual(plan["builders"], max(6, min(24, math.ceil(len(whats) / 3))))
        self.assertEqual(self.show()["village"], 0)

    def test_builders_are_not_citizens(self):
        for name in ("startShow", "showPlan"):
            body = function_source(name) or ""
            with self.subTest(fn=name):
                for word in ("newCitizen(", "citizens.set(", "spawnDemo("):
                    self.assertNotIn(word, body)


# ---------------------------------------------------------------------------
# Balance E2E bounce (main manager, real Chrome, page open through a whole show):
# 4 "shop" labels, a stale 还差 sign next to the new one (and one visible during
# the show), and the card still saying 正在升级成镇 after the flip; a reload was
# right. The live event path added overlays instead of replacing them.
#
#   landOverlays(view): buildLand's overlays, no THREE: first removes every
#     overlay element it made before (the old labels and signs leave the DOM),
#     then one .lbl (the territory name) and one .era-sign per territory.
#     buildLand calls it.
#   pinLandOverlays(): the per-frame part: pins every label, and every sign with
#     setText(signText(t)), hidden while that text is ''. Called every frame.
#   renderBalance(): its cache key includes what balanceHtml reads that changes
#     with time, eraShown(t) and signText(t), so the card changes by itself at
#     the flip and again when the show ends (renderPanel runs it often).
#   A page open through a whole show ends with exactly what a fresh page builds
#   from the snapshot: same labels, same signs, same card.
# ---------------------------------------------------------------------------

LIVE_SHOW_JS = FAKE_DOM_JS + r"""
const fs = require('fs'), vm = require('vm');
Object.defineProperty(El.prototype, 'className', { get(){ return [...this.classList.s].join(' '); },
  set(v){ this.classList = new CL(String(v).split(/\s+/).filter(Boolean)); } });
const { prelude, fns, view0, view1 } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
function page(){
  let T = 0;
  const ov = new El('div', [], { id: 'ov' }), card = new El('div', ['card-body'], { id: 'balance' });
  Object.defineProperty(card, 'innerHTML', { get(){ return this._html || ''; }, set(v){ this._html = String(v); } });
  const box = { Math, JSON, console, Map, Set, Array, Object, String, Number, Boolean,
    performance: { now: () => T }, document: { createElement: tag => new El(tag) },
    ovRoot: ov, $: s => (s === '#balance' ? card : s === '#ov' ? ov : null),
    toScreen: () => [100, 100], logAt(){}, log(){}, simT: 0, needFrame: false, DEMO: false,
    labels: [], signs: [], shows: new Map(), map: { territories: [] },
    balanceTerr: null, govTerr: null, balanceOpen: null, lastBalanceKey: '' };
  vm.createContext(box);
  vm.runInContext(prelude + '\n' + fns, box);
  const at = s => { T = s * 1000; };
  const world = v => { box.map = JSON.parse(JSON.stringify(v)); box.landOverlays(box.map); box.lastBalanceKey = ''; box.renderBalance(); };
  const frame = () => { box.pinLandOverlays(); box.renderBalance(); };
  const els = cls => ov.children.filter(e => e.classList.contains(cls));
  const seen = cls => els(cls).filter(e => !e.hidden).map(e => e.textContent).sort();
  const state = () => ({ lbl: els('lbl').map(e => e.textContent).sort(), lblSeen: seen('lbl'),
    sign: els('era-sign').length, signSeen: seen('era-sign'), ovCount: ov.children.length, card: card.innerHTML });
  return { box, at, world, frame, state };
}
const out = {};
let p = page();
p.world(view0); p.frame(); out.before = p.state();
p.box.startShow('t', 'village', 'town', 60);            // the era event...
p.world(view1); p.frame(); out.started = p.state();     // ...then the world event with the new balance
p.at(10); p.frame(); out.mid = p.state();
p.at(30); p.world(view1); p.frame();                    // a recount or a build during the show
p.at(52.5); p.box.landOverlays(p.box.map); p.frame(); out.flipped = p.state();   // the flip rebuilds the land
p.at(55); p.world(view1); p.frame();
p.at(61); p.box.shows.delete('t'); p.frame(); out.after = p.state();             // the show ends
const f = page(); f.world(view1); f.frame(); out.fresh = f.state();
process.stdout.write(JSON.stringify(out));
"""


def live_show_results():
    if "liveshow" not in _CACHE:
        def terr(tid, name, era, states, nxt, lines):
            bal = {k: {"state": s, "value": 1, "n": 0 if s == "missing" else 3,
                       "text": "还没有" if s == "missing" else "x"} for k, s in zip(KINDS, states)}
            return {"id": tid, "name": name, "era": era, "lines": lines, "open": 6, "size": .4, "cx": 0, "cz": 0,
                    "terrain": "grassland", "balance": bal, "next": nxt, "rules_note": "", "buildings": []}
        other = terr("u", "big", "city", ["healthy"] * 5, [], 40000)
        other.update(cx=26)
        view0 = {"territories": [terr("t", "shop", "village", ["healthy", "missing", "low", "low", "low"], ["规则"], 2200),
                                 other]}
        view1 = {"territories": [terr("t", "shop", "town", ["healthy", "low", "low", "low", "low"],
                                      ["规模", "规则", "美化"], 2200), other]}
        fns = page_fns("landOverlays", "pinLandOverlays", "signText", "eraShown", "startShow", "renderBalance",
                       "balanceHtml", "currentBalanceTerr", "terrOf", "ovEl", "setText", "pin",
                       optional=("showOf", "eraLook", "kindBar", "barOf"))
        esc = re.search(r"^const esc = .*;$", inline_script(), re.M)
        prelude = constants_prelude() + "\n" + consts("KIND_ZH", "STATE_ZH", "ERA_ZH", "ERA_LOOK") + "\n" + \
            (esc.group(0).replace("const esc", "var esc") if esc else "")
        _CACHE["liveshow"] = run_node(LIVE_SHOW_JS, {"prelude": prelude, "fns": fns, "view0": view0, "view1": view1})
    return _CACHE["liveshow"]


class TestLiveShowMatchesFreshPage(unittest.TestCase):
    def test_buildland_uses_the_overlay_functions(self):
        self.assertIn("landOverlays(", function_source("buildLand") or "")
        self.assertNotRegex(function_source("buildLand") or "", r"ovEl\(", "buildLand makes overlays only through landOverlays")
        text = inline_script()
        self.assertGreaterEqual(len(re.findall(r"pinLandOverlays\(\)", text)), 2, "defined and called every frame")

    def test_before_the_show(self):
        r = live_show_results()["before"]
        self.assertEqual(r["lbl"], ["big", "shop"])
        self.assertEqual(r["signSeen"], ["还差：规则"])

    def test_during_the_show_no_sign_and_the_card_says_upgrading(self):
        r = live_show_results()
        for name in ("started", "mid"):
            with self.subTest(moment=name):
                self.assertEqual(r[name]["signSeen"], [], "no 还差 sign while the show runs")
                self.assertEqual(r[name]["lbl"], ["big", "shop"], "one label per territory")
                self.assertIn("正在升级成镇", r[name]["card"])

    def test_after_the_flip_the_card_is_the_new_era(self):
        r = live_show_results()["flipped"]
        self.assertNotIn("正在升级", r["card"], "the card follows the flip by itself")
        self.assertEqual(r["lbl"], ["big", "shop"])

    def test_an_open_page_ends_like_a_fresh_page(self):
        r = live_show_results()
        after, fresh = r["after"], r["fresh"]
        self.assertEqual(after["lbl"], fresh["lbl"], "labels multiplied on the open page")
        self.assertEqual(after["sign"], fresh["sign"], "old sign elements left in the page")
        self.assertEqual(after["signSeen"], fresh["signSeen"])
        self.assertEqual(fresh["signSeen"], ["还差：规模、规则、美化"])
        self.assertEqual(after["ovCount"], fresh["ovCount"], "leftover overlay elements")
        self.assertEqual(after["card"], fresh["card"])

if __name__ == "__main__":
    unittest.main()
