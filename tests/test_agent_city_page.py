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
    MODELS = [...] list of '<pack>/<name>' entries (lib keys each by its full
    entry, idea-city C8); each is loaded from ASSET + entry + '.glb?v=' + ASSET_V.
    Live mode: new EventSource('/events').
    Demo mode (the mock's fake agents) when location.hash is '#demo' or the page
    is opened as a file:// URL. Live mode never runs the fake agents.
    Handles snapshot spawn tool stuck answer done leave gov, each as a
    `case '<type>'` in one switch. Knows role 'other'.
    Cheap:
      const FRAME_MS = 33        at most about 30 frames a second
      const IDLE_FRAME_MS = 100  about 10 a second when nothing moves
      const MAX_CITIZENS = 40, MAX_LOG = 40, each used (MAX_FLOATERS went with the floating tool
        names, city-work-anim bounce 1)
      static scenery drawn with THREE.InstancedMesh
    Its <script> passes `node --check`.

  Cleanup (approved mock: mock/city-ui-cleanup-mock.html). A real agent work
  view: real time only, less clutter. Page text stays Chinese (lang="zh-CN").
    Gone, markup and JS both: the intro card (#intro), the legend card
      (怎么看这座城), the credits card (素材来源), the speed buttons
      ([data-speed]), the pause button (#play and its icons/label), the drag
      hint (#hint-drag, hideHint), the separator #spawn-sep. No `speed` or
      `paused` in the script, no keydown/keyup/keypress listener.
    Kept: the status counts 干活 找区经理 休息 建成, the
      demo-only spawn control (#spawn-group; the whole toolbar is removed outside demo), the
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
      cam.dist through capZoom(want, cur, distLimit(), distMax()) (city-ux:
      DIST_MIN inside capZoom; the user's zoom-out stops at distLimit()).
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
    The right column is gone (city-focus, owner 2026-09-27): the city fills
      the page and a window opens over it on a click; see
      tests/test_agent_city_focus.py.

  Interaction (approved mock: mock/city-interact-mock.html; the server side
  is pinned in tests/test_agent_city_interact.py). Everything from Cleanup
  stays (3D city, camera).
    <meta name="city-token" content="__CITY_TOKEN__"> in <head>; the server
      swaps in its token. The script reads it from that meta tag (TOKEN).
    Handles `case 'ask'`, `case 'ask_phase'` and `case 'ask_closed'` in the
      same switch, and the snapshot's `asks` list.
    `case 'answer'`: shows ev.answer when it is a non-empty string, else
      '已回答'. Live mode never invents text: the `case 'answer'` code has no
      '批了' and no '不行'. Demo data may keep its own made-up answers.
    askLine(ev, name): top-level pure function (no DOM, no other globals) ->
      the Chinese log line for one ask / ask_phase / ask_closed event, name =
      the asker's task. Who: 区经理 (governor), 你 (owner), 终端 (terminal).
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
      offers the governor approving (no 区经理批准). Any other failure (network,
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
      are behind DEMO), and never say 问区经理 for a permission. The governor
      speaks (say(gov, ...)) and gov.answered counts only in demo or on an
      ask_closed by the governor, with its real text.
    stuckText(ev) -> the bubble over a stuck citizen: the question text, or
      要权限：<tool> for a permission; never 可以用 … 吗 or 问区经理.
    citizenStatus(c) -> [pill class, text] for the roster, from c.state and
      c.askKind ('question' | 'permission' | '') and c.askPhase ('governor' |
      'owner' | ''). Permission on the way or at the hall: 等你批. Question
      with the governor: 在问区经理; with the owner: 等你回答. Else STATE's words.
    Governor presence: `case 'governors'` (count of governors, also in the
      snapshot). Count 0 in live mode: govPillText() says 不在.
    Snapshot = live. applyAsk(c, ask): top-level; may use only stuckText.
      ask = an ask view (or null) -> sets c.askKind, c.askPhase, c.stuck and
      c.question (stuckText of the ask's tool and first question), or clears
      the ask fields for null. `case 'ask'` and `case 'snapshot'` both use it;
      the snapshot first clears every citizen's ask fields (a reconnect may
      find the ask closed), then applies each open ask to its agent. A page
      opened while a permission waits shows what an open page shows.
    citizenStatus(c, governors): with governors === 0 it never says 问区经理.
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

from citypage import ROOT, PAGE, page, inline_script, models, markup, style, OFFICE_DRAW, _script_function_source_one, script_function_source, constants_prelude, FAKE_DOM_JS, run_node, case_block, media_block, const_object, _ZH, text_zh, zh_resolved, js_value, page_fns, consts  # noqa: E402,F401  (test-slim: shared helpers)
from citypage import function_source  # noqa: E402
from citypage import run_sim  # noqa: E402
from citypage import TA  # noqa: E402
from citypage import TB  # noqa: E402
from citypage import two_territory_view  # noqa: E402
from citypage import css  # noqa: E402
from citypage import listener_block  # noqa: E402
from citypage import rule  # noqa: E402
from citypage import text_keys  # noqa: E402
from html.parser import HTMLParser  # noqa: E402
from citypage import script_function_source as function_source_ask_panel  # noqa: E402
from citypage import REQUIRED  # noqa: E402
from citypage import sim_section  # noqa: E402
from citypage import ASK_Q  # noqa: E402
from citypage import named_view  # noqa: E402
from citypage import script_function_source as function_source_chat  # noqa: E402
from citypage import script_function_source as function_source_focus  # noqa: E402
import citypage as tp  # noqa: E402
import agent_city as ac  # noqa: E402
from citypage import plan_views  # noqa: E402
from citypage import ac as ac_polish  # noqa: E402
from citypage import POLISH_A_REPO  # noqa: E402
from citypage import POLISH_TA  # noqa: E402
from citypage import media_960  # noqa: E402
from citypage import TA as PA  # noqa: E402
from citypage import TB as PB  # noqa: E402
from cityoffice import office_view  # noqa: E402
from citypage import script_function_source as function_source_talk_panel  # noqa: E402
ASSETS = os.path.join(ROOT, "bin", "agent-city-assets")


class TestDocument(unittest.TestCase):
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
        self.assertEqual(srcs, ["assets/vendor/three.min.js?v=__CITY_ASSET_V__"])   # city-office: no models to load

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
        for kind in ("snapshot", "spawn", "tool", "stuck", "answer", "done", "leave", "gov", "world", "design_bad"):
            with self.subTest(kind=kind):
                self.assertRegex(text, r"case\s+'%s'\s*:" % kind)

    def test_role_other_exists(self):
        self.assertRegex(inline_script(), r"['\"]?other['\"]?\s*:\s*\{")

        # idea-city C8: lib keys every model by its full entry; tests/test_agent_city_idea_page.py
        # checks that no table names a bare name two packs share


class TestCost(unittest.TestCase):
    def test_frame_caps(self):
        text = inline_script()
        self.assertRegex(text, r"const FRAME_MS = 33\b")
        self.assertRegex(text, r"const IDLE_FRAME_MS = 100\b")
        self.assertGreaterEqual(len(re.findall(r"\bFRAME_MS\b", text)), 2)
        self.assertGreaterEqual(len(re.findall(r"\bIDLE_FRAME_MS\b", text)), 2)

    def test_limits(self):
        text = inline_script()
        for name, value in (("MAX_CITIZENS", 40), ("MAX_LOG", 40)):
            with self.subTest(name=name):
                self.assertRegex(text, r"const %s = %d\b" % (name, value))
                self.assertGreaterEqual(len(re.findall(r"\b%s\b" % name, text)), 2,
                                        "%s is declared but never used" % name)

# ---------------------------------------------------------------------------
# Cleanup: helpers
# ---------------------------------------------------------------------------


UNIT_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
function ctx(extra){ const box = Object.assign({ Math, JSON, console, performance: { now: () => 0 }, $: () => null, setTimeout: () => 0, clearTimeout(){} }, extra); vm.createContext(box); vm.runInContext(prelude + '\n' + fns, box); return box; }

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
  const box = ctx({ cam: { az: 1, el: .7, dist: 6.5, tx: 0, tz: 0 }, drag: null, pinch: null, camTween: null, lastTouch: -Infinity, RM: false, autoRotDir: -1 });
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
  // city-ux U1: the user's zoom-out stops at distLimit() (the whole land is the All tag's job)
  if (typeof box.zoomStep === 'function') { for (let i = 0; i < 6; i++) box.zoomStep(1); out.sixOut = box.cam.dist / (typeof box.distLimit === 'function' ? box.distLimit() : box.distMax()); }
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
require(`fs`).writeSync(1, JSON.stringify(out));
"""


_CACHE = {}


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
        # city-ux2 (brief 2026-09-29): Esc stops following a person -- the one page-wide key.
        # chat-enter (2026-10-01, 04173d3): a second keydown listener serves the message box only
        # (Enter sends, Shift/Cmd/Ctrl+Enter is a new line): it leaves at once unless the key was typed
        # in #say-text. Still no keyboard shortcut for anything else (windows close by x or a tap on
        # the ground).
        text = inline_script()
        for event in ("keyup", "keypress"):
            with self.subTest(event=event):
                self.assertNotIn(event, text)
        # city-office-2: a third listener serves the room editor only (R, Delete, Ctrl/Cmd+Z): it leaves at once
        # unless the editor is open and the key was not typed into a field
        self.assertEqual(text.count("keydown"), 3, "three keydown listeners: Esc, the message box, the room editor")
        self.assertEqual(len(re.findall(r"document\.addEventListener\('keydown',", text)), 3,
                         "every keydown listener sits on document")
        bodies_all = re.findall(r"document\.addEventListener\('keydown', e => \{\n(.*?)\n\}\);", text, re.S)
        ed = [b for b in bodies_all if b.strip().startswith("if (!ED ")]
        self.assertEqual(len(ed), 1, "the editor's listener leaves first thing when the editor is closed")
        self.assertIn("INPUT|SELECT|TEXTAREA", ed[0])

        # 1. the page-wide one: Esc only
        # city-office: Esc first closes an open sheet (picker, renovation, design box), else stops following
        bodies = re.findall(r"document\.addEventListener\('keydown', e => \{\n(.*?)\n\}\);", text, re.S)
        esc = [b for b in bodies if b.strip().startswith("if (e.key !== 'Escape') return;")]
        self.assertEqual(len(esc), 1, "one listener: Esc")
        self.assertIn("stopFollow()", esc[0])
        self.assertEqual(re.findall(r"e\.key\s*[!=]==\s*'([^']+)'", esc[0]), ["Escape"], "Esc only")

        # 2. the message box's own: nothing happens for a key typed anywhere else
        box = [b for b in re.findall(r"document\.addEventListener\('keydown', e => \{\n(.*?)\n\}\);", text, re.S) if "say-text" in b]
        self.assertEqual(len(box), 1, "the message box's keydown listener")
        lines = [ln.strip() for ln in box[0].splitlines() if ln.strip()]
        self.assertEqual(lines[:2], ["const ta = e.target;", "if (!ta || ta.id !== 'say-text') return;"],
                         "it leaves first thing unless the key was typed in the message box")
        body = "\n".join(lines[2:])
        self.assertIn("sayKeyAction(e,", body, "which key does what is sayKeyAction's alone")
        self.assertEqual(re.findall(r"e\.(?:key|code|keyCode)\b", body), [], "no key of its own")
        fn = re.search(r"function sayKeyAction\(e, coarse\)\{\n(.*?)\n\}", text, re.S)
        self.assertIsNotNone(fn)
        self.assertEqual(re.findall(r"e\.key\s*[!=]==\s*'([^']+)'", fn.group(1)), ["Enter"], "Enter only")

        # and no other code looks at a pressed key
        # city-office-2: plus the room editor's own four (r, R, Delete, Backspace), only while it is open
        self.assertEqual(len(re.findall(r"\be\.key\s*[!=]==", text)), 6, "a key is read in those three places only")
        self.assertEqual(sorted(re.findall(r"e\.key\s*===\s*'([^']+)'", ed[0])), ["Backspace", "Delete", "R", "r"])


class TestKept(unittest.TestCase):
    def test_chinese_page(self):
        self.assertIn('<html lang="zh-CN">', page())

    def test_status_counts(self):
        # city-office: the counts are topCounts() (tests/test_agent_city_office_page.py TestWho), drawn by renderStats
        self.assertIn("topCounts()", script_function_source("renderStats") or "")

    def test_no_clock(self):
        self.assertNotIn('id="clock"', markup())
        self.assertNotIn('#clock', inline_script())
        self.assertNotIn('clock.now', page())
        self.assertNotIn('clock.demo', page())

    def test_live_mode_has_no_bottom_bar(self):
        self.assertRegex(inline_script(),
                         r"\} else \{\s*\$\('\.toolbar'\)\.remove\(\);\s*"
                         r"\$\('\.stage-col'\)\.classList\.add\('no-bar'\);")
        # cloud-polish (2026-10-02, bounce 1): no fixed offset any more, the stage takes what is left of the window
        # (tests/test_agent_city_cloud_polish_page.py); the script keeps the class
        self.assertNotIn('--stage-off', page())
        self.assertRegex(page(), r'\.stage\{[^}]*flex:1 1 0')

    def test_spawn_control_only_in_demo(self):
        self.assertIn('id="spawn-group"', markup())
        self.assertRegex(inline_script(),
                         r"if \(DEMO\) \{\s*\$\('#spawn'\)\.addEventListener[\s\S]*?\n\} else \{\s*"
                         r"\$\('\.toolbar'\)\.remove\(\);")

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
        for needle in ("$('#zin').addEventListener", "$('#zout').addEventListener", "pinch"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        # city-ux U3: the wheel listener sits on the stage (so a wheel over a head tag still pans)
        self.assertRegex(text, r"(?:\bstage|\$\('#stage'\))\.addEventListener\('wheel'")

    def test_phone_layout(self):
        self.assertIn('name="viewport"', page())


# ---------------------------------------------------------------------------
# Interaction: the "?" panel
# ---------------------------------------------------------------------------

ASK_LINE_JS = r"""
const fs = require('fs');
const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
eval(data.fn);
require(`fs`).writeSync(1, JSON.stringify(data.cases.map(([ev, name]) => askLine(ev, name))));
"""


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
        block = zh_resolved(case_block("answer"))
        self.assertIsNotNone(block)
        self.assertNotIn("批了", block)
        self.assertNotIn("不行", block)
        self.assertIn("已回答", block)

    def test_panel_sits_over_the_city(self):
        m = markup()
        i, stage = m.find('id="ask"'), m.find('id="stage"')
        self.assertGreater(i, 0, "no #ask panel in the markup")
        self.assertTrue(0 < stage < i, "#ask must be inside #stage, over the city")
        self.assertNotIn('<aside class="panel"', m, "no right column since city-focus")
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

    def test_decisions_go_to_the_page_endpoint_with_the_token(self):
        text = inline_script()
        self.assertRegex(text, r"fetch\(\s*'/api/decide'")
        self.assertIn("'X-City-Token'", text)
        self.assertIn("409", text)
        self.assertNotIn("/api/gov", text)
        self.assertNotIn("区经理批准", page())

    def test_owner_waiting_is_visible(self):
        self.assertIn("data-open", inline_script())
        stats = zh_resolved(script_function_source("renderStats") or "")
        self.assertIn("等你", stats)
        self.assertIn('id="next"', stats)

    def test_closed_state_words(self):
        text = zh_resolved(inline_script())
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
            if "问区经理" in line:
                self.assertIn("DEMO", line)

    def test_governor_speaks_only_its_own_answers(self):
        give = script_function_source("giveAnswer") or ""
        for line in give.splitlines():
            if "say(gov" in line or "govSay(" in line or "gov.answered" in line:
                with self.subTest(line=line.strip()):
                    self.assertIn("DEMO", line)
        closed = case_block("ask_closed") or ""
        self.assertIn("govSay(", closed)  # idea-city C13: each governor talks in his own bubble
        self.assertIn("'governor'", closed)

    def test_stuck_text_and_citizen_status(self):
        st = script_function_source("stuckText")
        cs = script_function_source("citizenStatus")
        self.assertIsNotNone(st, "function stuckText(ev) not found")
        self.assertIsNotNone(cs, "function citizenStatus(c) not found")
        state = re.search(r"^const STATE = \{.*?^\};", inline_script(), re.S | re.M)
        self.assertIsNotNone(state, "const STATE = {...}; not found")
        js = ("const fs = require('fs'); const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));\n"
              + constants_prelude() + "\n"  # idea-city C1: TEXT and i18n
              + state.group(0) + "\n" + st + "\n" + cs + "\n"
              + "require(`fs`).writeSync(1, JSON.stringify({st: data.st.map(e => stuckText(e)), "
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
        for word in ("可以用", "问区经理"):
            self.assertNotIn(word, out["st"][0])
        self.assertIn("Which port?", out["st"][1])
        texts = [pair[1] for pair in out["cs"]]
        self.assertIn("等你批", texts[0])
        self.assertIn("等你批", texts[1])
        self.assertIn("在问区经理", texts[2])
        self.assertIn("等你回答", texts[3])
        self.assertEqual(texts[4], "施工中")
        for t in texts[:2]:
            self.assertNotIn("问区经理", t)

    def test_the_waiting_chip_takes_real_clicks(self):
        stats = script_function_source("renderStats") or ""
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
        st = script_function_source("stuckText")
        cs = script_function_source("citizenStatus")
        ap = script_function_source("applyAsk")
        self.assertIsNotNone(ap, "function applyAsk(c, ask) not found")
        state = re.search(r"^const STATE = \{.*?^\};", inline_script(), re.S | re.M).group(0)
        for kind in ("ask", "snapshot"):
            with self.subTest(case=kind):
                self.assertIn("applyAsk(", case_block(kind) or "")
        js = r"""
const fs = require('fs'); const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
""" + constants_prelude() + "\n" + state + "\n" + st + "\n" + cs + "\n" + ap + r"""
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
require(`fs`).writeSync(1, JSON.stringify(out));
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
        self.assertIn("在问区经理", out[2]["snap"][1][1])
        self.assertEqual(out[3]["cleared"][1], "施工中")
        self.assertNotIn("问区经理", out[4]["noGov"][1], "no governor: never 问区经理")

    def test_governor_presence(self):
        self.assertRegex(inline_script(), r"case\s+'governors'\s*:")
        self.assertIn("不在", zh_resolved(script_function_source("govRowStatus") or ""))
        self.assertRegex(case_block("snapshot") or "", r"\.governors\b")

    def test_ask_line(self):
        fn = script_function_source("askLine")
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
        out = run_node(ASK_LINE_JS, {"fn": constants_prelude() + "\n" + fn, "cases": cases})  # + TEXT, i18n (idea-city C1)
        want = [
            ["清理构建", "要权限", "Bash", "rm -rf build/", "等你"],
            ["登录页", "问区经理", "Which port?"],
            ["登录页", "Which port?", "等你"],
            ["改文案", "区经理", "60", "等你"],
            ["改文案", "定不了"],
            ["区经理", "登录页", "4791"],
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
        fn = script_function_source("askClosedLine")
        self.assertIsNotNone(fn, "function askClosedLine(view) not found")
        esc = script_function_source("esc") or "const esc = s => String(s).replace(/[&<>\"]/g, ch => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '\"':'&quot;' }[ch]));"
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
              + constants_prelude() + "\n" + esc + "\n" + fn + "\n"
              + "require(`fs`).writeSync(1, JSON.stringify(data.map(x => askClosedLine(x).replace(/<[^>]+>/g, ''))));")
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
        self.assertIn("区经理", out[6])
        self.assertIn("晚了一步", out[6])
        self.assertIn("终端", out[7])
        self.assertIn("批准", out[7])

    def test_failures_are_said_not_swallowed(self):
        body = script_function_source("decide") or ""
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
require(`fs`).writeSync(1, JSON.stringify(out));
"""


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
require(`fs`).writeSync(1, JSON.stringify({ spots: slots.map(r => [r.x, r.y, box.tileAt(Math.floor(r.x), Math.floor(r.y)), !!box.walkable(Math.floor(r.x), Math.floor(r.y))]) }));
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
require(`fs`).writeSync(1, JSON.stringify({
  day0: box.hallDecor(t0, view),
  grown: box.hallDecor(t1, view).map(d => [d.key, d.x, d.z, ch(d.x, d.z)]),
  town: box.hallDecor(t2, view).map(d => [d.key, d.x, d.z, ch(d.x, d.z)]),
}));
"""


# ---------------------------------------------------------------------------
# Balance (requirements/city.md "Balance"; approved mock mock/city-balance-mock.html;
# server side: tests/test_agent_city_balance.py)
#
#   city-focus (owner, 2026-09-27): no 城市平衡 card, no 还差 sign, no file
#   lists; the kinds only bring their own things (systemsDecor). The retired
#   signText / balanceHtml / openBalanceKind contract lives in git history.
#   Constants  SHOW_SEC = 60, SHOW_FLIP = 52
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
require(`fs`).writeSync(1, JSON.stringify(out));
"""


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
require(`fs`).writeSync(1, JSON.stringify(out));
"""


# ---------------------------------------------------------------------------
# Balance E2E bounce (main manager, real Chrome, page open through a whole show):
# 4 "shop" labels, a stale 还差 sign next to the new one (and one visible during
# the show), and the card still saying 正在升级成镇 after the flip; a reload was
# right. The live event path added overlays instead of replacing them.
#
#   landOverlays(view): buildLand's overlays, no THREE: first removes every
#     overlay element it made before (the old labels leave the DOM), then one
#     .lbl (the territory name) per territory. No .era-sign at all (city-focus).
#     buildLand calls it.
#   pinLandOverlays(): the per-frame part: pins every label. Called every frame.
#   A page open through a whole show ends with exactly what a fresh page builds
#   from the snapshot: same labels, no leftover overlay elements.
# ---------------------------------------------------------------------------

LIVE_SHOW_JS = FAKE_DOM_JS + r"""
const fs = require('fs'), vm = require('vm');
Object.defineProperty(El.prototype, 'className', { get(){ return [...this.classList.s].join(' '); },
  set(v){ this.classList = new CL(String(v).split(/\s+/).filter(Boolean)); } });
const { prelude, fns, view0, view1 } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
function page(){
  let T = 0;
  const ov = new El('div', [], { id: 'ov' });
  const box = { Math, JSON, console, Map, Set, Array, Object, String, Number, Boolean,
    performance: { now: () => T }, document: { createElement: tag => new El(tag) },
    ovRoot: ov, $: s => (s === '#ov' ? ov : null),
    toScreen: () => [100, 100], logAt(){}, log(){}, simT: 0, needFrame: false, DEMO: false,
    labels: [], signs: [], shows: new Map(), map: { territories: [] }, govTerr: null };
  vm.createContext(box);
  vm.runInContext(prelude + '\n' + fns, box);
  const at = s => { T = s * 1000; };
  const world = v => { box.map = JSON.parse(JSON.stringify(v)); box.landOverlays(box.map); };
  const frame = () => { box.pinLandOverlays(); };
  const els = cls => ov.children.filter(e => e.classList.contains(cls));
  const seen = cls => els(cls).filter(e => !e.hidden).map(e => e.textContent).sort();
  const state = () => ({ lbl: els('lbl').map(e => e.textContent).sort(), lblSeen: seen('lbl'),
    sign: els('era-sign').length, ovCount: ov.children.length });
  return { box, at, world, frame, state };
}
const out = {};
let p = page();
p.world(view0); p.frame(); out.before = p.state();
p.box.startShow('t', 'village', 'town', 60);            // the era event...
p.world(view1); p.frame(); out.started = p.state();     // ...then the world event
p.at(10); p.frame(); out.mid = p.state();
p.at(30); p.world(view1); p.frame();                    // a recount or a build during the show
p.at(52.5); p.box.landOverlays(p.box.map); p.frame(); out.flipped = p.state();   // the flip rebuilds the land
p.at(55); p.world(view1); p.frame();
p.at(61); p.box.shows.delete('t'); p.frame(); out.after = p.state();             // the show ends
const f = page(); f.world(view1); f.frame(); out.fresh = f.state();
require(`fs`).writeSync(1, JSON.stringify(out));
"""


SIM_REQUIRED = ("apply", "officeState", "railGroups", "railHtml", "addHtml", "addIconHtml", "addState", "addAnswer", "addReason",
                "citizens", "byId", "i18n", "esc")


KEYS = ("rail.none", "add.tip", "add.plus", "add.opening", "add.openingBare", "add.cap", "add.capNums", "add.capAsk", "add.go",
        "add.cancel", "add.err", "add.retry", "add.ok", "add.errGone", "add.errFailed", "add.errLate", "add.errOther",
        "add.plain", "add.copy", "add.copied", "add.close")


# Two repos: A = auto-pipeline (a governor and one task manager), B = v4-plus (nobody online). Both are here.
DRIVER = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
A.name = 'auto-pipeline'; B.name = 'v4-plus'; A.here = true; B.here = true;
// city-office: the page reads names and here from the office view's repos; keep them in step with A and B
const sync = () => { for (const t of [A, B]) { const r = V.repos.find(x => x.id === t.id); r.name = t.name;
  if ('here' in t) r.here = t.here; else delete r.here; } };
sync();
const gB = () => railGroups().find(g => g.terr === B.id);
function buildLand(view){ officeState(view); }
const ag = (id, label, task, terr, extra) => Object.assign({ id, role: 'task-manager', label, task, stuck: false, done: false,
  tools: {}, terr, lead: '', office: null, relay: '' }, extra || {});
const snap = adding => ({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'busy' }], agents: [ag('s:tttt0001', 'city-add-agent Task Manager', 'auto-pipeline', A.id),
  ag('s:rrrr0002', 'fast-lane-deputy', '按钮颜色', A.id, { role: 'fast-lane-deputy' })], adding });
apply(snap([]));
byId('s:rrrr0002').state = 'resting';
const sec = (html, terr) => { const i = html.indexOf('<section class="rail-grp" data-terr="' + terr + '"');
  return i < 0 ? null : html.slice(i, html.indexOf('</section>', i) + 10); };
const draw = (adds, closed) => railHtml(railGroups(), null, closed || new Set(), new Set([A.id]), adds);
const out = {};
out.a = A.id; out.b = B.id;
out.groups = railGroups().map(g => ({ terr: g.terr, name: g.name, rows: g.rows.length, add: g.add }));
const plain = draw(new Map());
out.plainA = sec(plain, A.id); out.plainB = sec(plain, B.id);
out.noAdds = sec(railHtml(railGroups(), null, new Set(), new Set()), B.id);
const closed = draw(new Map(), new Set([A.id, B.id]));
out.closedA = sec(closed, A.id); out.closedB = sec(closed, B.id);
// the button's states, in B
const st = s => sec(draw(new Map([[B.id, s]])), B.id);
out.opening = st({ s: 'opening', name: 'v4-plus Manager' });
out.openingBare = st({ s: 'opening', name: '' });
out.cap = st({ s: 'cap', ram: 86, cpu: 41, max: 80 });
out.err = st({ s: 'err', why: 'Orca <b>broke</b>', retry: true });
out.errNoRetry = st({ s: 'err', why: 'gone', retry: false });
out.cmd = st({ s: 'cmd', cmd: "cd /r/v4-plus && claude --name 'v4-plus Manager' <x>" });
out.copied = st({ s: 'cmd', cmd: 'cd /r', copied: true });
out.direct = addHtml(gB(), undefined);
out.directIcon = addIconHtml(gB(), undefined);
out.closedOpening = sec(draw(new Map([[B.id, { s: 'opening', name: 'v4-plus Manager' }]]), new Set([B.id])), B.id);
// a repo that is not on this machine: the group stays, the button goes
B.here = false;
sync(); apply({ type: 'world', world: V });
out.notHere = { add: gB().add, html: sec(draw(new Map([[B.id, { s: 'opening', name: 'x' }]])), B.id) };
delete B.here;
sync(); apply({ type: 'world', world: V });
out.noFlag = gB().add;
B.here = true;
sync(); apply({ type: 'world', world: V });
// the server's answers
const ans = (code, body, before) => { addState.clear(); if (before) addState.set(B.id, before);
  addAnswer(B.id, code, body); return addState.get(B.id) || null; };
out.ans = {
  opening: ans(200, { state: 'opening', name: 'v4-plus Manager', role: 'main' }, { s: 'opening', name: '' }),
  openingAfterDone: ans(200, { state: 'opening', name: 'v4-plus Manager', role: 'main' }),
  cap: ans(200, { state: 'cap', ram: 86, cpu: 41, max: 80 }),
  plain: ans(200, { state: 'plain', name: 'v4-plus Manager', role: 'main', command: 'cd /r/v4-plus && claude' }),
  busy: ans(409, { error: 'busy' }),
  busyKeeps: ans(409, { error: 'busy' }, { s: 'opening', name: 'v4-plus Helper' }),
  gone: ans(409, { error: 'gone', folder: '/r/v4-plus' }),
  failed: ans(502, { error: 'failed', detail: 'orca: the app is not running' }),
  unknown: ans(404, { error: 'unknown' }),
  refused: ans(403, {}),
  none: ans(0, {}),
};
out.reasons = { gone: addReason({ error: 'gone', folder: '/r/v4-plus' }), failed: addReason({ error: 'failed', detail: 'orca: no' }),
  other: addReason({}), tGone: i18n('add.errGone', { folder: '/r/v4-plus' }), tFailed: i18n('add.errFailed', { detail: 'orca: no' }),
  tOther: i18n('add.errOther'), tLate: i18n('add.errLate') };
// the server's events
addState.clear();
const ev = {};
apply({ type: 'adding', terr: B.id, state: 'opening', name: 'v4-plus Manager', role: 'main' });
ev.opening = addState.get(B.id) || null;
apply({ type: 'adding', terr: B.id, state: 'done' });
ev.done = addState.has(B.id);
apply({ type: 'adding', terr: B.id, state: 'opening', name: 'v4-plus Manager', role: 'main' });
apply({ type: 'adding', terr: B.id, state: 'late' });
ev.late = addState.get(B.id) || null;
apply({ type: 'adding', terr: B.id, state: 'done' });
ev.doneKeepsErr = (addState.get(B.id) || {}).s;
addState.set(B.id, { s: 'cap', ram: 86, cpu: 41, max: 80 });
apply({ type: 'adding', terr: B.id, state: 'late' });
ev.lateKeepsCap = (addState.get(B.id) || {}).s;
// a snapshot: what is opening comes from the server, the page's own boxes stay
addState.clear();
addState.set(A.id, { s: 'opening', name: 'old' });
addState.set(B.id, { s: 'err', why: 'x', retry: false });
apply(snap([]));
ev.snapEmpty = { a: addState.has(A.id), b: (addState.get(B.id) || {}).s };
apply(snap([{ terr: A.id, name: 'auto-pipeline Helper', role: 'helper' }]));
ev.snapListed = addState.get(A.id) || null;
const noKey = snap([]); delete noKey.adding;
apply(noKey);
ev.snapNoKey = addState.has(A.id);
out.ev = ev;
out.text = {};
for (const k of __payload.keys) out.text[k] = i18n(k, { name: 'Manager', ram: 86, cpu: 41, max: 80, folder: '/r/x', detail: 'why' });
__out = out;
"""


def payload():
    return {"view": two_territory_view(), "ta": TA, "tb": TB, "keys": list(KEYS)}


class SimCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(DRIVER, payload(), SIM_REQUIRED)
        cls.a, cls.b = cls.r["a"], cls.r["b"]


def i18n_failed(why):
    """add.errFailed with the driver's detail of the 'failed' answer."""
    return why["tFailed"].replace("orca: no", "orca: the app is not running")


class TestEveryRepo(SimCase):
    def test_a_repo_with_nobody_keeps_its_group(self):
        self.assertEqual([(g["terr"], g["name"], g["rows"]) for g in self.r["groups"]],
                         [(self.b, "2F · v4-plus", 0), (self.a, "1F · auto-pipeline", 2)])   # city-office: floors top first; subagents are no rows

    def test_the_quiet_line(self):
        b = self.r["plainB"]
        self.assertIsNotNone(b, "v4-plus has no section in the rail")
        self.assertIn('<p class="rail-none">没人在线</p>', b)
        self.assertRegex(b, r'<span class="n">\s*0\s*</span>')
        self.assertNotIn("rail-none", self.r["plainA"], "auto-pipeline has people")

    def test_a_closed_group_is_its_name_row_only(self):
        for name in ("closedA", "closedB"):
            with self.subTest(group=name):
                html = self.r[name]
                self.assertIn('aria-expanded="false"', html)
                self.assertNotIn("rail-none", html)
                self.assertNotIn("data-focus", html, "no people")
                self.assertNotIn("add-line", html, "nothing to say")
                self.assertEqual(html.count("data-add="), 1, "cloud-polish Q5: the + sits on the name row, a fold keeps it")

    def test_a_closed_group_still_shows_the_words(self):
        html = self.r["closedOpening"]
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('<p class="add-line" role="status">正在打开 Manager…</p>', html, "an answer is never hidden by a fold")
        self.assertNotIn("rail-none", html)


class TestButton(SimCase):
    """cloud-polish Q5: the control is a small + at the right end of the repo name row, not a row of its own."""

    def icon(self, terr, name):
        return ('<button type="button" class="add-i" data-add="%s" title="加 agent" aria-label="加 agent · %s">＋</button>'
                % (terr, name))

    def test_every_repo_that_is_here_has_one(self):
        self.assertEqual([g["add"] for g in self.r["groups"]], [True, True])
        self.assertEqual(self.r["plainA"].count("data-add="), 1)
        self.assertEqual(self.r["plainB"].count("data-add="), 1)
        self.assertIn(self.icon(self.a, "1F · auto-pipeline"), self.r["plainA"])
        self.assertIn(self.icon(self.b, "2F · v4-plus"), self.r["plainB"])
        self.assertEqual(self.r["directIcon"], self.icon(self.b, "2F · v4-plus"))
        self.assertEqual(self.r["direct"], "", "addHtml is the row of words: nothing to say, nothing drawn")

    def test_on_the_name_row_after_the_count(self):
        a = self.r["plainA"]
        self.assertRegex(a, r'<div class="grp-row"><button type="button" class="grp-h" data-grp="%s"[^>]*>.*?<span class="n">\s*2\s*'
                            r'</span></button>%s</div>' % (self.a, re.escape(self.icon(self.a, "1F · auto-pipeline"))),
                         "the name row: the head button (dot, name, count), then the +")
        self.assertLess(a.index("data-add="), a.index("data-focus="), "before the first person")
        self.assertNotIn('class="add"', a, "no full-width button any more")
        self.assertNotIn("add-line", a, "nothing to say: no row of words")
        self.assertTrue(a.rstrip().endswith("</ul></section>"), "nothing comes after the people")
        b = self.r["plainB"]
        self.assertLess(b.index("data-add="), b.index("rail-none"))
        self.assertNotIn('class="add"', b)

    def test_the_plus_sign_is_a_text(self):
        """The full-width ＋ is a CJK character: it lives in TEXT (add.plus), never in the script itself."""
        self.assertIn("i18n('add.plus')", function_source("addIconHtml") or "")
        self.assertNotIn("＋", function_source("addIconHtml") or "")

    def test_adds_may_be_left_out(self):
        self.assertIn(self.icon(self.b, "2F · v4-plus"), self.r["noAdds"] or "")

    def test_a_repo_that_is_not_on_this_machine_has_none(self):
        self.assertIs(self.r["notHere"]["add"], False)
        html = self.r["notHere"]["html"]
        self.assertIsNotNone(html, "the group itself stays")
        self.assertIn("rail-none", html)
        self.assertIn('<div class="grp-row">', html, "the name row is the same row everywhere")
        self.assertNotIn("data-add", html)
        self.assertNotIn("add-i", html)
        self.assertNotIn("add-line", html, "and no row of words either")
        self.assertIs(self.r["noFlag"], False, "no `here` at all (demo, the cloud city) = no button")


class TestStates(SimCase):
    def test_opening(self):
        html = self.r["opening"]
        self.assertRegex(html, r'<button type="button" class="add-i" aria-disabled="true" title="加 agent" '
                               r'aria-label="加 agent · 2F · v4-plus"><span class="spin"></span></button></div>',
                         "the + shows the spinner while it opens")
        self.assertIn('<p class="add-line" role="status">正在打开 Manager…</p>', html)
        self.assertNotIn("Manager</b>", html)
        self.assertNotIn("v4-plus Manager", html, "the repo name is in the group head already")
        self.assertNotIn("data-add=", html, "one open at a time per repo: nothing to click while it opens")
        bare = self.r["openingBare"]
        self.assertIn('<p class="add-line" role="status">%s</p>' % self.r["text"]["add.openingBare"], bare)
        self.assertIn('aria-disabled="true"', bare)

    def test_over_the_cap(self):
        html = self.r["cap"]
        self.assertIn('<div class="addbox cap" role="alert">', html)
        self.assertIn(self.r["text"]["add.cap"], html)
        self.assertIn(self.r["text"]["add.capNums"], html)
        for part in ("RAM 86%", "CPU 41%", "80%"):
            self.assertIn(part, self.r["text"]["add.capNums"])
        self.assertIn(self.r["text"]["add.capAsk"], html)
        self.assertRegex(html, r'<button[^>]*data-add-go="%s"[^>]*>%s</button>' % (self.b, re.escape(self.r["text"]["add.go"])))
        self.assertRegex(html, r'<button[^>]*data-add-no="%s"[^>]*>%s</button>' % (self.b, re.escape(self.r["text"]["add.cancel"])))
        self.assertNotRegex(html, r'data-add="', "confirm or cancel, no plain add button beside them")
        self.assertRegex(html, r'<button type="button" class="add-i" aria-disabled="true"[^>]*>＋</button></div>',
                         "the + is quiet while the box asks")

    def test_error(self):
        html = self.r["err"]
        self.assertIn('<div class="addbox err" role="alert">', html)
        self.assertIn(self.r["text"]["add.err"], html)
        self.assertIn("Orca &lt;b&gt;broke&lt;/b&gt;", html, "the reason is the server's text: escaped")
        self.assertRegex(html, r'<button[^>]*data-add="%s"[^>]*>%s</button>' % (self.b, re.escape(self.r["text"]["add.retry"])))
        self.assertRegex(html, r'<button[^>]*data-add-no="%s"[^>]*>%s</button>' % (self.b, re.escape(self.r["text"]["add.ok"])))
        self.assertNotIn('class="add"', html)
        self.assertEqual(html.count('data-add="'), 1, "the retry button only: the + is quiet")
        self.assertNotRegex(self.r["errNoRetry"], r'data-add="')
        self.assertIn("data-add-no=", self.r["errNoRetry"])

    def test_no_orca(self):
        html = self.r["cmd"]
        self.assertIn('<div class="addbox cmd" role="status">', html)
        self.assertIn(self.r["text"]["add.plain"], html)
        self.assertIn("<code>cd /r/v4-plus &amp;&amp; claude --name 'v4-plus Manager' &lt;x&gt;</code>", html)
        self.assertRegex(html, r'<button[^>]*data-add-copy="%s"[^>]*>%s</button>' % (self.b, re.escape(self.r["text"]["add.copy"])))
        self.assertRegex(html, r'<button[^>]*data-add-no="%s"[^>]*>%s</button>' % (self.b, re.escape(self.r["text"]["add.close"])))
        self.assertNotRegex(html, r'data-add="')
        self.assertRegex(self.r["copied"], r'data-add-copy="%s"[^>]*>%s</button>' % (self.b, re.escape(self.r["text"]["add.copied"])))

    def test_the_words_sit_right_under_the_name_row(self):
        for name, start in (("opening", '<p class="add-line"'), ("cap", '<div class="addbox cap"'),
                            ("err", '<div class="addbox err"'), ("cmd", '<div class="addbox cmd"')):
            with self.subTest(state=name):
                html = self.r[name]
                self.assertIn("</button></div>" + start, html, "right after the name row")
                self.assertLess(html.index(start), html.index("rail-none"), "above the people (here: the quiet line)")
                self.assertEqual(html.count("add-line") + html.count('class="addbox'), 1, "ONE row of words")


class TestAnswers(SimCase):
    def test_the_three_good_answers(self):
        ans = self.r["ans"]
        self.assertEqual((ans["opening"]["s"], ans["opening"]["name"]), ("opening", "v4-plus Manager"))
        self.assertEqual([ans["cap"][k] for k in ("s", "ram", "cpu", "max")], ["cap", 86, 41, 80])
        self.assertEqual((ans["plain"]["s"], ans["plain"]["cmd"]), ("cmd", "cd /r/v4-plus && claude"))

    def test_done_before_the_answer(self):
        """A fast session: the 'done' event beats the POST answer. The click set 'opening', 'done' removed it."""
        self.assertIsNone(self.r["ans"]["openingAfterDone"], "the late answer must not bring 'opening' back")

    def test_busy_reads_as_opening(self):
        ans = self.r["ans"]
        self.assertEqual(ans["busy"]["s"], "opening")
        self.assertEqual((ans["busyKeeps"]["s"], ans["busyKeeps"]["name"]), ("opening", "v4-plus Helper"))

    def test_every_other_answer_is_an_error_line(self):
        ans, why = self.r["ans"], self.r["reasons"]
        self.assertEqual((ans["gone"]["s"], ans["gone"]["why"], bool(ans["gone"].get("retry"))), ("err", why["tGone"], False))
        self.assertEqual((ans["failed"]["s"], ans["failed"]["why"], ans["failed"].get("retry")),
                         ("err", i18n_failed(why), True))
        for name in ("unknown", "refused"):
            with self.subTest(answer=name):
                self.assertEqual((ans[name]["s"], ans[name]["why"], bool(ans[name].get("retry"))), ("err", why["tOther"], False))
        self.assertEqual((ans["none"]["s"], ans["none"]["why"], ans["none"].get("retry")), ("err", why["tOther"], True),
                         "no answer at all (the server is gone): say so, let him try again")

    def test_reasons_in_plain_words(self):
        why = self.r["reasons"]
        self.assertEqual((why["gone"], why["failed"], why["other"]), (why["tGone"], why["tFailed"], why["tOther"]))
        self.assertIn("/r/v4-plus", why["gone"])
        self.assertIn("orca: no", why["failed"])
        self.assertTrue(why["other"] and why["other"] != "add.errOther")


class TestEvents(SimCase):
    def test_opening_done_late(self):
        ev = self.r["ev"]
        self.assertEqual((ev["opening"]["s"], ev["opening"]["name"]), ("opening", "v4-plus Manager"))
        self.assertIs(ev["done"], False, "done: the button is a button again")
        self.assertEqual((ev["late"]["s"], ev["late"]["why"], bool(ev["late"].get("retry"))),
                         ("err", self.r["reasons"]["tLate"], False))
        self.assertEqual(ev["doneKeepsErr"], "err", "done only ends an opening state")
        self.assertEqual(ev["lateKeepsCap"], "cap", "late only ends an opening state")

    def test_snapshot(self):
        ev = self.r["ev"]
        self.assertEqual(ev["snapEmpty"], {"a": False, "b": "err"}, "opening comes from the server; the page's own error line stays")
        self.assertEqual((ev["snapListed"]["s"], ev["snapListed"]["name"]), ("opening", "auto-pipeline Helper"))
        self.assertIs(ev["snapNoKey"], False, "an older server sends no `adding`")


class TestWiring(unittest.TestCase):
    def test_the_request(self):
        src = function_source("addAgent")
        self.assertIsNotNone(src, "function addAgent(terr, force) not found")
        self.assertRegex(src, r"fetch\(\s*'/api/agent/add'")
        self.assertRegex(src, r"method:\s*'POST'")
        self.assertIn("'X-City-Token': TOKEN", src)
        self.assertRegex(src, r"JSON\.stringify\(\{\s*terr(:\s*terr)?,\s*force[^}]*\}\)")
        self.assertIn("addAnswer(", src)
        self.assertRegex(src, r"addAnswer\(\s*terr,\s*0,\s*\{\}\s*\)", "a failed fetch must show an error line")
        self.assertIn("'opening'", src, "the button reads opening at once, and a second click does nothing")
        self.assertIn("renderRail(", src)

    def test_the_clicks(self):
        block = listener_block(r"\$\('#rail-list'\)", "click")
        self.assertIsNotNone(block)
        for attr in ("[data-add]", "[data-add-go]", "[data-add-no]", "[data-add-copy]"):
            with self.subTest(attr=attr):
                self.assertIn(attr, block)
        self.assertRegex(block, r"addAgent\([^)]*,\s*false\)")
        self.assertRegex(block, r"addAgent\([^)]*,\s*true\)")
        self.assertIn("clipboard", block)
        self.assertIn("addState.delete(", block)

    def test_the_rail_draws_from_the_state(self):
        # city-rail-tree: railShut may follow addState (railHtml's 6th argument)
        self.assertRegex(function_source("renderRail"), r"railHtml\([^;]*\baddState\b")

    def test_css(self):
        for sel in (".rail-none", ".grp-row", ".add-i", '.add-i[aria-disabled="true"]', ".add-line", ".spin", ".addbox",
                    ".addbox.err", ".addbox.cap", ".addbox.cmd", ".mini"):
            with self.subTest(sel=sel):
                self.assertTrue(rule(sel).strip(), "no CSS rule for %s" % sel)
        self.assertIn("animation", rule(".spin"))
        reduced = [m.group(0) for m in re.finditer(r"@media \(prefers-reduced-motion:\s*reduce\)\s*\{(?:[^{}]|\{[^{}]*\})*\}", css())]
        self.assertTrue(any(".spin" in block for block in reduced), "the spinner must stop under prefers-reduced-motion")
        self.assertEqual(rule(".add").strip(), "", "the full-width button is gone, and its rules with it")
        self.assertRegex(rule(".add-i"), r"width:22px;height:22px", "a small square at the end of the name row")

    def test_texts(self):
        for key in KEYS:
            with self.subTest(key=key):
                self.assertEqual(text_keys(key), 2, "one zh and one en text")
        src = page()
        self.assertEqual(text_keys("add.btn"), 0, "the full-width button's text is gone")
        for key, zh, en in (("rail.none", "没人在线", "Nobody online"), ("add.tip", "加 agent", "Add agent"),
                            ("add.plus", "＋", "+"),
                            ("add.opening", "正在打开 {name}…", "Opening {name}…")):
            with self.subTest(key=key):
                self.assertIn("'%s': '%s'" % (key, zh), src)
                self.assertIn("'%s': '%s'" % (key, en), src)


VM_JS = r"""
const fs = require('fs'), vm = require('vm');
const { fns, driver, payload } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { __payload: payload, __out: null, console };
vm.createContext(box);
vm.runInContext(fns + '\n;\n' + driver, box);
require(`fs`).writeSync(1, JSON.stringify(box.__out));
"""


def run_vm(fns, driver, payload=None):
    return run_node(VM_JS, {"fns": fns, "driver": driver, "payload": payload or {}})


def esc_source():
    m = re.search(r"^const esc = .*$", inline_script(), re.M)
    if not m:
        raise AssertionError("const esc = ... not found in the page script")
    return "var esc" + m.group(0)[len("const esc"):]


PERM = {"id": "p1", "agent": "gov", "terr": "tA", "label": "", "task": "", "kind": "permission", "phase": "owner",
        "why": "permission", "wait": 60, "left": 0, "tool": "Bash", "what": "Bash: osascript", "at": 1000,
        "detail": {"command": "osascript -e 'tell application \"Google Chrome\"' <b>x</b>",
                   "description": "Give the owner his own tab back", "cwd": "/Users/me/repo"}}


QUESTION = {"id": "q7", "agent": "s:tm1", "terr": "tA", "label": "task-manager", "task": "cloud-polish",
            "kind": "question", "phase": "owner", "why": "pass", "wait": 60, "left": 0, "tool": "AskUserQuestion",
            "what": "left or top?", "at": 2000,
            "questions": [{"question": "left or top?", "header": "head", "multiSelect": False,
                           "options": [{"label": "left", "description": "on the map"},
                                       {"label": "top", "description": "one bar"}]}]}


class Tree(HTMLParser):
    """A tiny DOM: nodes are dicts {tag, attrs, kids, parent, text}; void tags never open a level."""

    VOID = {"input", "br", "img", "hr", "meta", "link"}

    def __init__(self, html):
        super().__init__()
        self.root = {"tag": "#root", "attrs": {}, "kids": [], "parent": None, "text": ""}
        self.cur = self.root
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "kids": [], "parent": self.cur, "text": ""}
        self.cur["kids"].append(node)
        if tag not in self.VOID:
            self.cur = node

    def handle_endtag(self, tag):
        node = self.cur
        while node is not self.root and node["tag"] != tag:
            node = node["parent"]
        if node is not self.root:
            self.cur = node["parent"]

    def handle_data(self, data):
        node = self.cur
        while node:
            node["text"] += data
            node = node["parent"]

    def all(self, node=None):
        node = node or self.root
        for kid in node["kids"]:
            yield kid
            yield from self.all(kid)

    def one(self, test, what):
        found = [n for n in self.all() if test(n)]
        if len(found) != 1:
            raise AssertionError("%s: expected one, found %d" % (what, len(found)))
        return found[0]


def has_class(node, name):
    return name in (node["attrs"].get("class") or "").split()


def inside(node, name):
    node = node["parent"]
    while node:
        if has_class(node, name):
            return True
        node = node["parent"]
    return False


LONG_CMD = "echo " + " && echo ".join("line-%04d" % i for i in range(400))


LONG_DIR = "/private/tmp/claude-502/-Users-me-repo/a8712f6d-e725-4809-9737-067022907c06/scratchpad/deep/er"


class TestPanelAskK3(unittest.TestCase):

    PRELUDE = r"""
var govTerr = 'tA';
var people = { w1: { id: 'w1' }, 's:tm1': { id: 's:tm1' }, r1: { id: 'r1', remote: { who: 'x', device: 'd' } } };
function byId(id){ return people[id] || null; }
var asks = new Map();
function put(a){ asks.set(a.id, a); }
function idOf(v){ return v ? v.id : null; }
"""

    def ask(self, driver):
        return run_vm(self.PRELUDE + page_fns("panelAsk"), driver)

    def test_a_person_with_an_ask_at_the_owner(self):
        out = self.ask(r"""
put({ id: 'a1', agent: 'w1', phase: 'owner', at: 5 });
put({ id: 'a2', agent: 's:tm1', phase: 'owner', at: 6 });
__out = [idOf(panelAsk({ t: 'c', id: 'w1' })), idOf(panelAsk({ t: 'c', id: 's:tm1' }))];
""")
        self.assertEqual(out, ["a1", "a2"], "each person's panel gets its own ask")

    def test_nothing_while_the_governor_still_decides(self):
        out = self.ask(r"""
put({ id: 'a1', agent: 'w1', phase: 'governor', at: 5 });
__out = idOf(panelAsk({ t: 'c', id: 'w1' }));
""")
        self.assertIsNone(out, "only an ask with the owner has something to answer")

    def test_the_governor_by_territory(self):
        out = self.ask(r"""
put({ id: 'gA', agent: 'gov', terr: 'tA', phase: 'owner', at: 5 });
put({ id: 'gB', agent: 'gov', terr: 'tB', phase: 'owner', at: 6 });
__out = [idOf(panelAsk({ t: 'gov', terr: 'tA' })), idOf(panelAsk({ t: 'gov', terr: 'tB' })),
         idOf(panelAsk({ t: 'gov' })), idOf(panelAsk({ t: 'gov', terr: 'tC' }))];
""")
        self.assertEqual(out, ["gA", "gB", "gA", None], "'gov' is shared: the ask's own terr picks the governor")

    def test_open_wins_over_closed_and_the_oldest_open_first(self):
        out = self.ask(r"""
put({ id: 'done', agent: 'w1', phase: 'owner', at: 1, closed: { by: 'owner', verb: 'allow' } });
const onlyClosed = idOf(panelAsk({ t: 'c', id: 'w1' }));
put({ id: 'late', agent: 'w1', phase: 'owner', at: 9 });
put({ id: 'early', agent: 'w1', phase: 'owner', at: 4 });
__out = [onlyClosed, idOf(panelAsk({ t: 'c', id: 'w1' }))];
""")
        self.assertEqual(out[0], "done", "a closed ask still in `asks` shows its result")
        self.assertEqual(out[1], "early", "an open ask wins over a closed one, the oldest open first")

    def test_nobody_gets_none(self):
        out = self.ask(r"""
put({ id: 'a2', agent: 'ghost', phase: 'owner', at: 5 });
__out = [idOf(panelAsk(null)), idOf(panelAsk({ t: 'b', id: 'w1' })), idOf(panelAsk({ t: 'c', id: 'ghost' }))];
""")
        self.assertEqual(out, [None, None, None],
                         "no selection, a building, nobody on the page")


class TestAskPickK2(unittest.TestCase):

    def test_who_owns_an_ask(self):
        out = run_vm(TestPanelAskK3.PRELUDE + page_fns("askPick"), r"""
__out = [askPick({ agent: 'gov', terr: 'tB' }), askPick({ agent: 'gov', terr: '' }), askPick({ agent: 'gov' }),
         askPick({ agent: 'w1', terr: 'tA' }), askPick({ agent: 's:tm1' }), askPick({ agent: 'ghost' })];
""")
        self.assertEqual(out[0], {"t": "gov", "terr": "tB"})
        self.assertEqual(out[1], {"t": "gov"})
        self.assertEqual(out[2], {"t": "gov"})
        self.assertEqual(out[3], {"t": "c", "id": "w1"})
        self.assertEqual(out[4], {"t": "c", "id": "s:tm1"})
        self.assertIsNone(out[5], "nobody on the page for it")


class TestAskCardHtmlK6(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        fns = (constants_prelude() + "\n" + esc_source() + "\n"
               + page_fns("askCardHtml", "askWhyLine", "askQuestionBody", "askPermissionBody", "askClosedLine",
                          "askPermissionDetail", "askPermissionActs", "askQuestionFields", "askQuestionActs",
                          "shortDir"))
        closed = dict(PERM, closed={"by": "owner", "verb": "allow", "text": "", "reason": "", "at": 1790000000000})
        cls.perm, cls.question, cls.closed = run_vm(
            fns, "__out = [askCardHtml(__payload.p), askCardHtml(__payload.q), askCardHtml(__payload.c)];",
            {"p": PERM, "q": QUESTION, "c": closed})

    def test_the_card_frame(self):
        for name, html, ask_id in (("permission", self.perm, "p1"), ("question", self.question, "q7")):
            with self.subTest(kind=name):
                tag = re.match(r"\s*<section[^>]*>", html)
                self.assertIsNotNone(tag, "the card is one <section>")
                for bit in ('class="askcard"', 'id="askcard"', 'data-ask="%s"' % ask_id):
                    self.assertIn(bit, tag.group(0))
                self.assertIn('class="askcard-h"', html)
                self.assertRegex(html, r'id="askcard-title"[^>]*tabindex="-1"|tabindex="-1"[^>]*id="askcard-title"')
                self.assertIn("等你", html, "the 等你 pill")
                self.assertIn("终端里也能答", html, "the foot line: the terminal can answer too")

    def test_a_permission_shows_the_request_and_both_buttons(self):
        h = self.perm
        self.assertIn("要权限", h)
        self.assertIn("权限只由你来批", h, "why it is with the owner")
        self.assertIn("Bash", h)
        self.assertIn("osascript -e", h, "the exact command")
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", h, "the command is text, never markup")
        self.assertNotIn("<b>x</b>", h)
        self.assertIn("Give the owner his own tab back", h, "what it said")
        self.assertIn("/Users/me/repo", h, "the folder")
        self.assertIn('data-verb="allow"', h)
        self.assertIn('data-verb="deny"', h)
        self.assertIn('id="reason"', h, "the deny reason")

    def test_a_question_shows_its_options_and_send(self):
        h = self.question
        self.assertIn("在问你", h)
        self.assertIn('id="qform"', h)
        self.assertIn("left or top?", h)
        for label in ("left", "top", "on the map", "one bar"):
            self.assertIn(label, h)
        self.assertIn("data-other", h, "the write-your-own answer")
        self.assertIn("发送回答", h)
        self.assertNotIn("data-verb", h)

    def test_a_closed_card_shows_only_the_result(self):
        h = self.closed
        tag = re.match(r"\s*<section[^>]*>", h).group(0)
        self.assertRegex(tag, r'class="askcard done"')
        self.assertIn("已关闭", h)
        self.assertIn("批准了", h)
        for gone in ("data-verb", 'id="qform"', 'id="reason"', "osascript"):
            self.assertNotIn(gone, h, "a closed card has nothing left to click")

    def test_the_new_words_are_in_both_languages(self):
        text = inline_script()
        for key in ("card.permission", "card.question"):
            self.assertEqual(len(re.findall(r"'%s': '" % re.escape(key), text)), 2, key + " in zh and en")


class TestRenderAskCardK8(unittest.TestCase):

    PRELUDE = r"""
var selected = { t: 'c', id: 'w1' }, cardAskId = null, openAskId = null;
var asks = new Map();
var current = null;
function panelAsk(sel){ return sel ? current : null; }
function askCardHtml(v){ return '<card ' + v.id + (v.closed ? ' closed' : ' open') + '>'; }
var wired = [];
function wireAskControls(root, v){ wired.push([root === slot ? 'slot' : 'other', v.id]); }
function mkSlot(){
  return { dataset: {}, style: { minHeight: 'old' }, clientWidth: 348, sets: 0, _h: '',
           get innerHTML(){ return this._h; }, set innerHTML(v){ this._h = v; this.sets++; },
           querySelector(){ return null; }, querySelectorAll(){ return []; } };
}
var fits = [];
function fitAskSlot(s){ fits.push(s === slot ? s.style.minHeight : 'other'); }
var slot = mkSlot();
function $(sel){ return sel === '#askslot' ? slot : null; }
"""

    def run_card(self, driver):
        return run_vm(self.PRELUDE + page_fns("renderAskCard"), driver)

    def test_the_card_is_written_once_and_kept_between_frames(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard(); renderAskCard(); renderAskCard();
__out = { html: slot.innerHTML, sets: slot.sets, card: cardAskId, wired };
""")
        self.assertEqual(r["html"], "<card p1 open>")
        self.assertEqual(r["sets"], 1, "a picked option or a typed reason must survive the next frames")
        self.assertEqual(r["card"], "p1")
        self.assertEqual(r["wired"], [["slot", "p1"]], "wired once, inside the slot")

    def test_a_result_redraws_the_card(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();
current.closed = { by: 'terminal', verb: 'allow' };
renderAskCard(); renderAskCard();
__out = { html: slot.innerHTML, sets: slot.sets, card: cardAskId };
""")
        self.assertEqual(r["html"], "<card p1 closed>")
        self.assertEqual(r["sets"], 2)
        self.assertEqual(r["card"], "p1", "the closed card still shows its result")

    def test_the_real_facts_replace_someone_else_was_first(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();
current.closed = { by: 'terminal', verb: 'closed' };   // a 409: only "someone else was first" is known
renderAskCard();
const after409 = slot.sets;
current.closed = { by: 'terminal', verb: 'allow' };    // ask_closed arrives with the facts
renderAskCard(); renderAskCard();
const afterFacts = slot.sets;
current.closed = { by: 'governor', verb: 'allow' };
renderAskCard();
__out = { after409, afterFacts, afterWho: slot.sets };
""")
        self.assertEqual(r, {"after409": 2, "afterFacts": 3, "afterWho": 4},
                         "bounce 1 K8b: the key carries closed.by and closed.verb")

    def test_every_call_fits_the_slot_and_a_new_card_is_measured_again(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();                       // the card is written: the old floor is cleared before the fit
slot.style.minHeight = '272px';        // (what the real fitAskSlot would leave)
renderAskCard(); renderAskCard();      // same key: nothing rewritten, the floor is kept, the fit still runs
const kept = fits.slice();
current.closed = { by: 'owner', verb: 'allow' };
renderAskCard();                       // another card (the result): measured again
__out = { kept, afterResult: fits[fits.length - 1], n: fits.length };
""")
        self.assertEqual(r["kept"], ["", "272px", "272px"], "bounce 3 K17: fitAskSlot(slot) on every call")
        self.assertEqual(r["afterResult"], "", "a newly written card clears the old floor first")
        self.assertEqual(r["n"], 4)

    def test_a_rebuilt_panel_gets_its_card_again(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();
slot = mkSlot();           // renderDetail rebuilt the panel: a fresh, empty slot
renderAskCard();
__out = { html: slot.innerHTML, sets: slot.sets };
""")
        self.assertEqual(r, {"html": "<card p1 open>", "sets": 1}, "the key lives on the slot (slot.dataset.key)")

    def test_no_ask_empties_the_slot(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();
current = null;
renderAskCard();
__out = { html: slot.innerHTML, card: cardAskId, kept: asks.has('p1') };
""")
        self.assertEqual(r["html"], "")
        self.assertIsNone(r["card"])
        self.assertTrue(r["kept"], "an OPEN ask is never dropped because another person was picked")

    def test_a_closed_view_leaves_asks_when_its_card_stops_showing(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner', closed: { by: 'owner', verb: 'deny' } }; asks.set('p1', current);
renderAskCard();
current = null;
renderAskCard();
const cardGone = asks.has('p1');
current = { id: 'p2', agent: 'w1', phase: 'owner', closed: { by: 'owner', verb: 'deny' } }; asks.set('p2', current);
openAskId = 'p2';          // the small panel shows this one too: it keeps the view
renderAskCard();
current = null;
renderAskCard();
__out = { cardGone, panelKept: asks.has('p2') };
""")
        self.assertFalse(r["cardGone"], "nothing shows the result any more: the view goes")
        self.assertTrue(r["panelKept"], "the small panel still shows it")

    def test_no_slot_no_card(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();
slot = null;               // the panel is closed, or it is a building's card
renderAskCard();
__out = { card: cardAskId, kept: asks.has('p1') };
""")
        self.assertEqual(r, {"card": None, "kept": True})


class TestAskRootK10(unittest.TestCase):

    def test_where_an_ask_shows(self):
        out = run_vm("var cardAskId = 'p1'; function $(sel){ return sel; }\n" + page_fns("askRoot"),
                     "__out = [askRoot('p1'), askRoot('q7'), askRoot(undefined)];")
        self.assertEqual(out, ["#askslot", "#ask", "#ask"])
        none = run_vm("var cardAskId = null; function $(sel){ return sel; }\n" + page_fns("askRoot"),
                      "__out = [askRoot(null), askRoot(undefined), askRoot('p1')];")
        self.assertEqual(none, ["#ask", "#ask", "#ask"], "no card: everything goes to the small panel")

    def test_failure_line_and_disabling_follow_it(self):
        for fn in ("showAskFailure", "setAskControlsDisabled"):
            with self.subTest(fn=fn):
                src = function_source_ask_panel(fn) or ""
                self.assertIn("askRoot(", src)
                self.assertNotIn("$('#ask')", src, fn + " no longer goes to the small panel only")

    def test_decide_passes_its_id_and_redraws_the_card(self):
        src = function_source_ask_panel("decide") or ""
        self.assertIn("renderAskCard(", src)
        self.assertGreaterEqual(len(re.findall(r"setAskControlsDisabled\((?:true|false),\s*id\)", src)), 3)
        self.assertGreaterEqual(len(re.findall(r"showAskFailure\([^;]*,\s*id\);", src)), 2)


class TestShowAskK11(unittest.TestCase):

    PRELUDE = r"""
var govTerr = 'tA', winFolded = false;
var selected = null;
var asks = new Map([['a1', { id: 'a1', agent: 'w1', phase: 'owner' }], ['g1', { id: 'g1', agent: 'gov', terr: 'tA', phase: 'owner' }],
                    ['x1', { id: 'x1', agent: 'ghost', phase: 'owner' }]]);
var people = { w1: { id: 'w1' } };
function byId(id){ return people[id] || null; }
var calls = [];
function selectPick(pk){ calls.push(['pick', pk]); selected = pk; winFolded = false; }
function openAsk(id){ calls.push(['dialog', id]); }
function setWinFolded(v){ calls.push(['fold', v]); winFolded = v; }
function renderPanel(){}
function renderAskCard(){}
var needFrame = false;
function $(sel){ return { focus(){ calls.push(['focus', sel]); } }; }
"""

    def run_show(self, driver):
        return run_vm(self.PRELUDE + page_fns("showAsk", "askPick", "selKey"), driver)

    def test_it_opens_the_persons_own_panel(self):
        r = self.run_show("showAsk('a1'); __out = calls;")
        self.assertIn(["pick", {"t": "c", "id": "w1"}], r)
        self.assertNotIn(["dialog", "a1"], r, "no separate dialog for a person on the page")
        self.assertIn(["focus", "#askcard-title"], r)

    def test_the_governor(self):
        r = self.run_show("showAsk('g1'); __out = calls;")
        self.assertIn(["pick", {"t": "gov", "terr": "tA"}], r)
        self.assertEqual([c for c in r if c[0] == "dialog"], [])

    def test_the_same_person_is_not_picked_twice(self):
        r = self.run_show(r"""
selected = { t: 'c', id: 'w1' }; winFolded = true;
showAsk('a1');
const first = calls.slice();
calls = []; selected = { t: 'gov' };     // the home governor, picked without a terr
showAsk('g1');
__out = { first, second: calls };
""")
        self.assertEqual([c for c in r["first"] if c[0] == "pick"], [],
                         "a second pick of the same person would stop the follow")
        self.assertIn(["fold", False], r["first"], "a folded panel opens again")
        self.assertEqual([c for c in r["second"] if c[0] == "pick"], [], "{t:'gov'} is the home governor")
        self.assertEqual([c for c in r["second"] if c[0] == "fold"], [], "an open panel is left alone")

    def test_nobody_to_pick_falls_back_to_the_small_panel(self):
        r = self.run_show("showAsk('x1'); showAsk('nope'); __out = calls;")
        self.assertEqual(r, [["dialog", "x1"]], "as before for an ask with no person; an unknown id does nothing")

    def test_only_show_ask_opens_the_small_panel(self):
        text = inline_script()
        for fn in ("showAsk", "openAsk"):
            src = function_source_ask_panel(fn)
            self.assertIsNotNone(src, "function %s(...) not found" % fn)
            text = text.replace(src, "")
        self.assertNotIn("openAsk(", text, 'the red "?" and the 等你 button call showAsk()')
        self.assertGreaterEqual(text.count("showAsk("), 2, "both of them")


class TestPanelWiringK7K9K12(unittest.TestCase):

    def test_the_slot_is_in_the_person_card_and_the_governor_card(self):
        body = function_source_ask_panel("renderDetail") or ""
        self.assertEqual(body.count('<div id="askslot"></div>'), 2, "the local person's card and the governor's card")
        self.assertIn("renderAskCard(", body, "the card follows on every call")
        person = body.index("if (c) {")
        gov = body.index("} else if (selected && selected.t === 'gov') {")
        for card in (body[person:gov], body[gov:body.index("hint.noAgents", gov)]):
            self.assertLess(card.index("p-head"), card.index("askslot"))
            self.assertLess(card.index("askslot"), card.index("hist.title"), "between the head and the history")

    def test_one_wiring_for_the_card_and_the_small_panel(self):
        src = function_source_ask_panel("wireAskControls")
        self.assertIsNotNone(src, "function wireAskControls(root, view) not found")
        self.assertNotIn("$('#", src, "looked up inside root only")
        self.assertIn("root.querySelector", src)
        self.assertIn("decide(", src)
        panel = function_source_ask_panel("renderAskPanel") or ""
        self.assertIn("wireAskControls(", panel)
        self.assertNotIn("addEventListener('submit'", panel, "the wiring moved out")

    def test_the_controls_never_scroll_away(self):
        """Bounce 2 K15: the slot is the panel's flex item, the card shrinks, only its body scrolls."""
        css = style().replace(" ", "")

        def rule(selector):
            m = re.search(r"(?:^|\})" + re.escape(selector) + r"\{([^}]*)\}", css, re.M)
            self.assertIsNotNone(m, selector + " rule")
            return m.group(1)

        for bit in ("flex:01auto", "min-height:0", "display:flex", "flex-direction:column"):
            self.assertIn(bit, rule("#askslot"))
        self.assertIn("display:none", rule("#askslot:empty"))
        card = rule(".askcard")
        for bit in ("flex:01auto", "min-height:0", "display:flex", "flex-direction:column", "overflow:hidden"):
            self.assertIn(bit, card)
        self.assertNotIn("max-height", card, "the percent cap hid the buttons (261 px of 424)")
        self.assertNotIn("%", card)
        for bit in ("flex:01auto", "min-height:0", "display:flex", "flex-direction:column"):
            self.assertIn(bit, rule(".askcard-main"))
        for bit in ("flex:01auto", "min-height:48px", "overflow:auto"):
            self.assertIn(bit, rule(".askcard-body"), "only the details scroll")
        self.assertIn("flex:none", rule(".askcard-acts"), "the controls keep their height")
        chat = rule(".detail:has(.askcard).chat")
        for bit in ("flex:110", "min-height:56px"):
            self.assertIn(bit, chat, "the card takes the free height first, the history keeps a strip")
        self.assertNotRegex(css, r"\.askcard\.cmd\{[^}]*(?:max-height|overflow)", "one scroll area, the body")

    def test_the_card_state_lives_in_the_sim_part(self):
        self.assertRegex(sim_section(), r"\bcardAskId\s*=\s*null", "declared next to openAskId")


class TestControlsAlwaysInSightK14(unittest.TestCase):
    """Bounce 2: the deny-reason box and the buttons are never inside the part that scrolls."""

    @classmethod
    def setUpClass(cls):
        fns = (constants_prelude() + "\n" + esc_source() + "\n"
               + page_fns("askCardHtml", "askWhyLine", "askQuestionBody", "askPermissionBody", "askClosedLine",
                          "askPermissionDetail", "askPermissionActs", "askQuestionFields", "askQuestionActs",
                          "shortDir"))
        long_perm = dict(PERM, repo="/Users/me/repo/.git",
                         detail={"command": LONG_CMD, "description": "x" * 300, "cwd": LONG_DIR})
        many = dict(QUESTION, questions=[dict(QUESTION["questions"][0],
                                              options=[{"label": "option %d" % i, "description": "d" * 80}
                                                       for i in range(12)])])
        out = run_vm(fns, "__out = [askCardHtml(__payload.p), askCardHtml(__payload.q), askPermissionBody(__payload.p),"
                          " askQuestionBody(__payload.q), askCardHtml(__payload.s)];",
                     {"p": long_perm, "q": many, "s": dict(PERM, repo="/Users/me/repo/.git")})
        cls.perm, cls.question, cls.dialog_perm, cls.dialog_question, cls.short_perm = out

    def parts(self, html):
        t = Tree(html)
        card = t.one(lambda n: has_class(n, "askcard"), ".askcard")
        main = t.one(lambda n: has_class(n, "askcard-main"), ".askcard-main")
        body = t.one(lambda n: has_class(n, "askcard-body"), ".askcard-body")
        acts = t.one(lambda n: has_class(n, "askcard-acts"), ".askcard-acts")
        self.assertIs(main["parent"], card, "main is a child of the card")
        self.assertEqual([k for k in main["kids"]], [body, acts], "main holds the body, then the controls, nothing else")
        tags = [k["tag"] for k in card["kids"]]
        self.assertEqual(len(card["kids"]), 3, "head, main, foot: %s" % tags)
        self.assertTrue(has_class(card["kids"][0], "askcard-h"))
        self.assertIs(card["kids"][1], main)
        self.assertTrue(has_class(card["kids"][2], "foot"))
        return t, main, body, acts

    def test_a_long_permission_keeps_its_controls_out_of_the_scroll(self):
        t, main, body, acts = self.parts(self.perm)
        self.assertEqual(main["tag"], "div")
        controls = [n for n in t.all() if n["attrs"].get("data-verb") or n["attrs"].get("id") == "reason"]
        self.assertEqual(sorted(n["attrs"].get("data-verb") or "reason" for n in controls), ["allow", "deny", "reason"])
        for n in controls:
            self.assertTrue(inside(n, "askcard-acts"), "always in sight")
            self.assertFalse(inside(n, "askcard-body"), "never in the part that scrolls")
        self.assertIn("line-0399", body["text"], "the whole long command is in the body")
        self.assertIn("权限只由你来批", body["text"], "the why line scrolls with the details")
        self.assertNotIn("line-0000", acts["text"])

    def test_a_question_with_many_options(self):
        t, main, body, acts = self.parts(self.question)
        self.assertEqual(main["tag"], "form", "the form holds both, so 发送回答 submits it")
        self.assertEqual(main["attrs"].get("id"), "qform")
        send = t.one(lambda n: n["attrs"].get("id") == "send", "#send")
        self.assertTrue(inside(send, "askcard-acts"))
        radios = [n for n in t.all() if n["attrs"].get("type") == "radio"]
        self.assertEqual(len(radios), 13, "12 options and the write-your-own one")
        for n in radios:
            self.assertTrue(inside(n, "askcard-body"), "the options scroll")
        self.assertEqual(len([n for n in t.all() if n["attrs"].get("id") == "qform"]), 1)

    def test_the_folder_is_short_with_the_full_path_on_hover(self):
        t = Tree(self.perm)
        code = t.one(lambda n: n["tag"] == "code" and n["attrs"].get("title") == LONG_DIR, "the folder <code>")
        self.assertEqual(code["text"], "…/deep/er")
        self.assertTrue(inside(code, "askcard-body"))
        t2 = Tree(self.short_perm)
        code2 = t2.one(lambda n: n["tag"] == "code" and n["attrs"].get("title") == "/Users/me/repo", "the folder <code>")
        self.assertEqual(code2["text"], "repo", "the repo's own folder is just its name")

    def test_the_small_dialog_keeps_everything_in_one_block(self):
        t = Tree(self.dialog_perm)
        self.assertEqual(len([n for n in t.all() if has_class(n, "perm")]), 1)
        verbs = sorted(n["attrs"]["data-verb"] for n in t.all() if n["attrs"].get("data-verb"))
        self.assertEqual(verbs, ["allow", "deny"])
        t.one(lambda n: n["attrs"].get("id") == "reason", "#reason")
        self.assertNotIn("askcard", self.dialog_perm)
        q = Tree(self.dialog_question)
        form = q.one(lambda n: n["attrs"].get("id") == "qform", "form#qform")
        self.assertEqual(form["tag"], "form")
        send = q.one(lambda n: n["attrs"].get("id") == "send", "#send")
        node = send
        while node and node is not form:
            node = node["parent"]
        self.assertIs(node, form, "发送回答 is inside the form")
        self.assertNotIn("askcard", self.dialog_question)


class TestShortDirK16(unittest.TestCase):

    def test_cases(self):
        repo = "/Users/me/work/auto-pipeline/.git"
        cases = [
            ["/Users/me/work/auto-pipeline", repo, "auto-pipeline"],
            ["/Users/me/work/auto-pipeline/bin/sub", repo, "auto-pipeline/bin/sub"],
            ["/Users/me/work/auto-pipeline-2/x", repo, "~/work/auto-pipeline-2/x"],
            ["/Users/me/orca/workspaces/auto-pipeline/city-ask-panel", repo, "~/orca/workspaces/auto-pipeline/city-ask-panel"],
            ["/Users/me", repo, "~"],
            ["/home/dev/src/app", "", "~/src/app"],
            ["/home/dev/src/app", None, "~/src/app"],
            [LONG_DIR, repo, "…/deep/er"],
            ["/Users/me/" + "/".join(["folder-%d" % i for i in range(8)]), repo, "…/folder-6/folder-7"],
            ["/opt/tool", repo, "/opt/tool"],
            ["", repo, ""],
        ]
        out = run_vm(page_fns("shortDir"), "__out = __payload.cases.map(c => shortDir(c[0], c[1]));", {"cases": cases})
        for case, got in zip(cases, out):
            with self.subTest(path=case[0]):
                self.assertEqual(got, case[2])


class TestCardFloorK17(unittest.TestCase):
    """Bounce 3: the card is never squeezed below its head, 48 px of details, its controls and its foot."""

    def test_the_floor(self):
        fns = constants_prelude() + "\n" + page_fns("askCardFloor")
        out = run_vm(fns, "__out = [askCardFloor(424, 200), askCardFloor(300, 30), askCardFloor(120, 0), "
                          "askCardFloor(0, 0), askCardFloor(271.6, 48), ASK_BODY_MIN];")
        self.assertEqual(out, [272, 300, 120, 0, 272, 48])
        self.assertRegex(style().replace(" ", ""), re.compile(r"(?:^|\})\.askcard-body\{[^}]*min-height:48px", re.M),
                         "ASK_BODY_MIN is the body's CSS min-height")

    PRELUDE = r"""
var reads = [];
function mk(cardH, bodyH, width){
  const slot = { style: { minHeight: '', flex: '' }, dataset: {}, clientWidth: width };
  const card = cardH === null ? null : { get offsetHeight(){ reads.push([slot.style.flex, slot.style.minHeight]); return cardH; } };
  const body = bodyH === null ? null : { offsetHeight: bodyH };
  slot.querySelector = sel => sel === '.askcard' ? card : (sel === '.askcard-body' ? body : null);
  return slot;
}
"""

    def fit(self, driver):
        return run_vm(constants_prelude() + "\n" + self.PRELUDE + page_fns("fitAskSlot", "askCardFloor"), driver)

    def test_it_measures_the_card_unsqueezed(self):
        r = self.fit(r"""
const slot = mk(424, 200, 348);
slot.style.minHeight = '26px';
slot.dataset.w = '';
fitAskSlot(slot);
__out = { min: slot.style.minHeight, flex: slot.style.flex, w: slot.dataset.w, reads };
""")
        self.assertEqual(r["min"], "272px")
        self.assertEqual(r["flex"], "", "the inline flex is taken off again")
        self.assertEqual(r["w"], "348")
        self.assertEqual(r["reads"], [["none", ""]], "measured with flex:none and no old floor: its natural height")

    def test_once_per_width(self):
        r = self.fit(r"""
const slot = mk(424, 200, 348);
fitAskSlot(slot); fitAskSlot(slot); fitAskSlot(slot);
const same = reads.length;
slot.clientWidth = 300;                // the phone turned: the text wraps differently
fitAskSlot(slot);
const turned = reads.length;
slot.style.minHeight = '';             // renderAskCard wrote another card
fitAskSlot(slot);
__out = { same, turned, again: reads.length, w: slot.dataset.w };
""")
        self.assertEqual(r, {"same": 1, "turned": 2, "again": 3, "w": "300"})

    def test_a_closed_card_and_no_card(self):
        r = self.fit(r"""
const closed = mk(96, null, 348);
fitAskSlot(closed);
const none = mk(null, null, 348);
none.style.minHeight = '272px'; none.dataset.w = '348';
fitAskSlot(none);
__out = { closed: closed.style.minHeight, none: none.style.minHeight, w: none.dataset.w };
""")
        self.assertEqual(r, {"closed": "96px", "none": "", "w": ""}, "a result card is never cut; no card, no floor")

    def test_the_sheet_grows_on_a_phone(self):
        from citypage import media_block  # noqa: E402
        block = media_block("@media (max-width: 960px)").replace(" ", "")
        m = re.search(r"\.win:has\(\.askcard\)\{([^}]*)\}", block)
        self.assertIsNotNone(m, "bounce 3 K18: .win:has(.askcard) in the first phone block")
        for bit in ("height:auto", "max-height:calc(100%-16px)"):
            self.assertIn(bit, m.group(1))
        self.assertLess(block.index(".win{"), m.start(), "after the sheet's own .win rule")


class TestKeepAskSlotK13(unittest.TestCase):
    """Bounce 1: a rebuild of the panel keeps the card's node, so nothing typed or picked is lost."""

    PRELUDE = r"""
function node(name){ return { name, swaps: [], replaceWith(o){ this.swaps.push(o.name); } }; }
function panel(fresh){ return { querySelector(sel){ return sel === '#askslot' ? fresh : null; } }; }
"""

    def test_the_old_node_goes_back(self):
        r = run_vm(self.PRELUDE + page_fns("keepAskSlot"), r"""
const fresh = node('fresh'), old = node('old');
keepAskSlot(panel(fresh), old);
const none = node('fresh2');
keepAskSlot(panel(none), null);
const same = node('same');
keepAskSlot(panel(same), same);
keepAskSlot(panel(null), node('orphan'));
__out = { swapped: fresh.swaps, none: none.swaps, same: same.swaps };
""")
        self.assertEqual(r["swapped"], ["old"], "fresh.replaceWith(old)")
        self.assertEqual(r["none"], [], "nothing to keep on a first open")
        self.assertEqual(r["same"], [], "no rebuild happened")

    def test_render_detail_keeps_it_across_a_rebuild(self):
        body = function_source_ask_panel("renderDetail") or ""
        rebuild = body.index("if (key !== lastDetailKey) {")
        self.assertRegex(body[:rebuild], r"el\.querySelector\('#askslot'\)", "the old node is taken before the rebuild")
        keep, card = body.find("keepAskSlot(el,"), body.find("renderAskCard(")
        self.assertGreater(keep, rebuild, "put back after the rebuild")
        self.assertLess(keep, card, "before renderAskCard() looks at the slot")


class TestResultThenFoldK4K5(unittest.TestCase):

    DRIVER = r"""
function buildLand(view){ officeState(view); }
let __cards = 0;
function renderAskCard(){ __cards++; }
function renderAskPanel(){}
function closeAskPanel(){ openAskId = null; }
{   // a block: the driver's own names never meet the page's
  const V = __payload.view, ask = __payload.ask;
  const idOf = v => (v ? v.id : null);
  const snap = () => apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: ask.terr }, govs: [{ terr: ask.terr, state: 'busy' }],
    governors: 1, asks: [ask], shows: [], agents: [] });
  const closeIt = () => apply({ type: 'ask_closed', id: ask.id, agent: 'gov', kind: 'question', tool: 'AskUserQuestion', what: ask.what,
    by: 'terminal', verb: 'answer', text: 'red', reason: '', at: 2000 });
  snap();
  closeIt();
  const nowhere = asks.has(ask.id);
  snap();
  cardAskId = ask.id;
  askAutoClose(50000);
  const openStays = asks.has(ask.id);
  __cards = 0;
  closeIt();
  const kept = asks.has(ask.id), v = asks.get(ask.id);
  const closed = !!(v && v.closed && v.closed.by === 'terminal' && typeof v.shownAt === 'number');
  const redrawn = __cards;
  const shown = idOf(panelAsk({ t: 'gov', terr: ask.terr }));
  askAutoClose(9999);
  const at9 = asks.has(ask.id);
  __cards = 0;
  askAutoClose(10000);
  __out = { nowhere, openStays, kept, closed, redrawn, shows: shown, at9, at10: asks.has(ask.id), folded: __cards };
}
"""

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(cls.DRIVER, {"view": named_view(), "ask": ASK_Q},
                        REQUIRED + ("askAutoClose", "ASK_CLOSE_MS", "panelAsk", "cardAskId"))

    def test_shown_nowhere_is_deleted_as_before(self):
        self.assertFalse(self.r["nowhere"])

    def test_an_open_card_never_goes_by_itself(self):
        self.assertTrue(self.r["openStays"])

    def test_a_close_keeps_the_view_while_its_card_shows(self):
        self.assertTrue(self.r["kept"], "answered in the terminal first: the card says so")
        self.assertTrue(self.r["closed"])
        self.assertGreaterEqual(self.r["redrawn"], 1, "the card is drawn again at once")
        self.assertEqual(self.r["shows"], ASK_Q["id"], "the panel still shows it, as a result")

    def test_the_result_stays_10s_then_the_card_goes(self):
        self.assertTrue(self.r["at9"])
        self.assertFalse(self.r["at10"])
        self.assertGreaterEqual(self.r["folded"], 1, "the slot is emptied")


FEATURE_REQUIRED = REQUIRED + ("rosterGroups", "restSlotsFor")


def dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


GOVFIG_DRIVER = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
function buildLand(view){ officeState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 1, asks: [], shows: [], agents: [],
  govs: [{ terr: A.id, state: 'busy' }, { terr: B.id, state: 'idle' }] });
const two = governorFigures().map(g => ({ terr: g.terr, x: g.x, y: g.y }));
apply({ type: 'gov', terr: B.id, state: 'idle', present: false });
const one = governorFigures().map(g => g.terr);
__out = { two, one, hallA: { x: A.cx + MGR_SEAT.x, y: A.cz + MGR_SEAT.z }, hallB: { x: B.cx + MGR_SEAT.x, y: B.cz + MGR_SEAT.z } };
"""


class TestGovernorFigures(unittest.TestCase):
    """One governor figure per present governor, each at its own hall (B1 drew only one)."""

    def test_one_figure_per_present_governor(self):
        r = run_sim(GOVFIG_DRIVER, {"view": two_territory_view(), "ta": TA, "tb": TB},
                    FEATURE_REQUIRED + ("governorFigures",))
        self.assertEqual(sorted(g["terr"] for g in r["two"]), sorted([TA, TB]))
        by = {g["terr"]: g for g in r["two"]}
        self.assertLessEqual(dist(by[TA], r["hallA"]), 2.5)
        self.assertLessEqual(dist(by[TB], r["hallB"]), 2.5)
        self.assertEqual(r["one"], [TA])

    def test_the_3d_draws_every_figure(self):
        self.assertIn("governorFigures(", function_source("updateGovernor") or "")


HERE = os.path.dirname(os.path.abspath(__file__))


CHAT_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, String, Array, Object };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
require(`fs`).writeSync(1, JSON.stringify(cases.map(([entries, name, busy]) => box.chatHtml(entries, name, busy))));
"""


class TestPageChat(unittest.TestCase):
    def html(self, *cases):
        esc = re.search(r"^const esc = .*;$", inline_script(), re.M)
        self.assertIsNotNone(esc, "const esc = ...; not found")
        # idea-city C1: the state words live in TEXT (chat.state.*), T() picks the language
        prelude = esc.group(0).replace("const esc", "var esc") + "\n" + constants_prelude()
        # city-ux U9: chatHtml renders text through mdLite (self-contained)
        return run_node(CHAT_JS, {"prelude": prelude, "fns": page_fns("chatHtml", optional=("mdLite",)), "cases": [list(c) for c in cases]})

    def test_state_words(self):
        zh = text_zh()  # idea-city C1
        self.assertEqual({k: zh.get("chat.state." + k) for k in ("queued", "delivered", "undelivered")},
                         {"queued": "排队中", "delivered": "已送达", "undelivered": "没送到"})

    def test_my_messages_on_the_right_in_green(self):
        page = open(os.path.join(ROOT, "bin", "agent-city.html"), encoding="utf-8").read()
        self.assertRegex(page, r'\.chat \.msg\[data-kind="owner"\],\.chat \.msg\[data-kind="prompt"\][^{]*\{align-self:flex-end;background:var\(--me-bg\)')
        self.assertEqual(len(re.findall(r"--me-bg:#", page)), 3)  # light + two dark blocks
        self.assertNotRegex(page, r'data-kind="owner"\][^{]*\{[^}]*--gov-bg')

    def test_chat_html(self):
        entries = [{"id": 1, "kind": "prompt", "text": "fix <b>it</b>", "at": 1},
                   {"id": 2, "kind": "reply", "text": "done", "at": 2},
                   {"id": 3, "kind": "owner", "text": "thanks", "at": 3, "state": "queued"}]
        html, busy, empty = self.html((entries, "worker · <x>", False), (entries, "w", True), ([], "w", False))
        self.assertEqual(re.findall(r'<li class="msg" data-kind="(\w+)" data-id="(\d+)"', html),
                         [("prompt", "1"), ("reply", "2"), ("owner", "3")])
        for word in ("你（终端）", "你（页面）", "排队中", "fix &lt;b&gt;it&lt;/b&gt;", "worker · &lt;x&gt;"):
            with self.subTest(word=word):
                self.assertIn(word, html)
        self.assertNotIn("<b>it</b>", html)
        self.assertNotIn("等它做完这一步", html, "not busy: no wait line")
        self.assertIn('<li class="msg-wait">等它做完这一步</li>', busy)
        self.assertIn('<li class="msg-empty">还没有对话</li>', empty)

    def test_chat_target(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = {}; vm.createContext(box); vm.runInContext(fns, box);
require(`fs`).writeSync(1, JSON.stringify([{ t: 'gov', terr: 't1' }, { t: 'c', id: 's:tm1' }, { t: 'c', id: 'a9' },
  { t: 'rg', id: 'r:dev:s:1' }, { t: 'b', id: 4 }, null].map(s => box.chatTarget(s))));
"""
        self.assertEqual(run_node(js, {"fns": page_fns("chatTarget")}), ["gov:t1", "s:tm1", "a9", None, None, None])

    def test_the_open_window_asks_for_the_right_id(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const people = { 's:tm1': { id: 's:tm1', lead: true }, 's:tm2': { id: 's:tm2' }, 'a9': { id: 'a9' } };
const box = { selected: null, govTerr: 't0', byId: id => people[id] };
vm.createContext(box); vm.runInContext(fns, box);
const out = [];
for (const sel of [{ t: 'c', id: 's:tm1' }, { t: 'c', id: 's:tm2' }, { t: 'c', id: 'a9' },
                   { t: 'gov', terr: 't1' }, { t: 'gov' }, null]) { box.selected = sel; out.push(box.curChatTo()); }
require(`fs`).writeSync(1, JSON.stringify(out));
"""
        out = run_node(js, {"fns": page_fns("curChatTo", "chatTarget")})
        self.assertEqual(out, ["s:tm1", "s:tm2", "a9", "gov:t1", "gov:t0", None])

    def test_the_log_names_the_person(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const people = { 's:tm1': { id: 's:tm1', label: 'task-manager', task: 'shop' }, 'a9': { id: 'a9', label: 'worker', task: 'form' } };
const box = { byId: id => people[id], nameOf: c => c.label, fullName: c => 'repo · ' + c.label + ' · ' + c.task };
vm.createContext(box); vm.runInContext(fns, box);
require(`fs`).writeSync(1, JSON.stringify(['s:tm1', 'a9', 'gov:t1', 's:gone'].map(t => box.chatDisplayName(t))));
"""
        out = run_node(js, {"fns": constants_prelude() + "\n" + page_fns("chatDisplayName")})
        # city-polish P3: the page log mixes every repo, so it names the person with its repo (fullName)
        self.assertEqual(out, ["repo · task-manager · shop", "repo · worker · form", "区经理", "s:gone"],
                         "E2E 2026-09-27: the log said 你 → tm1 instead of the name")

    def test_window_has_the_conversation_and_the_box(self):
        body = zh_resolved(function_source_chat("renderDetail") or "")  # idea-city C1
        for needle in ("chatHtml(", 'id="chat"', 'id="say"', 'id="say-text"', 'maxlength="4000"', "发送", "组长"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)

    def test_load_and_send(self):
        load = function_source_chat("loadChat") or ""
        send = function_source_chat("sendChat") or ""
        self.assertIn("'/api/chat?to=' + encodeURIComponent(", load)
        self.assertIn("'/api/chat/send'", send)
        for src, name in ((load, "loadChat"), (send, "sendChat")):
            with self.subTest(fn=name):
                self.assertIn("'X-City-Token': TOKEN", src)
                self.assertRegex(src, r"if \(DEMO\)", "demo never fetches")
                self.assertRegex(src, r"catch|\.ok", "a failure is shown, never swallowed")
        self.assertIn("'POST'", send)
        self.assertRegex(inline_script(), r"(?m)^const chats = new Map\(\);")

    def test_submit_sends(self):
        text = inline_script()
        m = re.search(r"addEventListener\('submit', e => \{(.*?)\n\}\);", text, re.S)
        self.assertIsNotNone(m, "no submit listener")
        self.assertIn("preventDefault()", m.group(1))
        self.assertIn("sendChat(", m.group(1))

    def test_a_failed_send_keeps_the_text(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { JSON, console, Promise, Error, String, Date, DEMO: false, TOKEN: 't', chats: new Map(),
  renderPanel(){}, demoSendChat(){} };
vm.createContext(box);
vm.runInContext(fns, box);
(async () => {
  box.fetch = () => Promise.reject(new Error('down'));
  const down = await box.sendChat('s:tm1', 'hi');
  box.fetch = () => Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
  const refused = await box.sendChat('s:tm1', 'hi');
  box.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({ id: 7, state: 'queued' }) });
  const took = await box.sendChat('s:tm1', 'hi');
  require(`fs`).writeSync(1, JSON.stringify([down, refused, took, (box.chats.get('s:tm1') || {}).error || '']));
})();
"""
        down, refused, took, _ = run_node(js, {"fns": constants_prelude() + "\n" + page_fns("sendChat")})
        self.assertEqual((down, refused, took), (False, False, True))
        text = inline_script()
        m = re.search(r"addEventListener\('submit', e => \{(.*?)\n\}\);", text, re.S)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(1), r"then\(\s*ok\s*=>[^\n]*if \(ok", "the box is cleared only when the send worked")

    def test_chat_event(self):
        block = zh_resolved(case_block("chat") or "")
        self.assertTrue(block, "case 'chat': not handled")
        self.assertIn("chats", block)
        self.assertIn("你 →", block)


def action(**ev):
    coarse = ev.pop("coarse", False)
    ev.setdefault("key", "Enter")
    js = function_source("sayKeyAction") + "\nconsole.log(JSON.stringify(sayKeyAction(%s, %s)));" % (
        json.dumps(ev), json.dumps(coarse))
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


class TestChatEnter(unittest.TestCase):

    def test_enter_sends_on_a_computer(self):
        self.assertEqual(action(), "send")

    def test_modified_enter_is_a_new_line(self):
        for mod in ("shiftKey", "metaKey", "ctrlKey"):
            self.assertEqual(action(**{mod: True}), "newline", mod)

    def test_composing_never_sends(self):
        self.assertEqual(action(isComposing=True), "")
        self.assertEqual(action(keyCode=229), "")
        self.assertEqual(action(isComposing=True, metaKey=True), "")

    def test_phone_enter_is_a_new_line_only_the_button_sends(self):
        self.assertEqual(action(coarse=True), "")

    def test_other_keys_are_left_alone(self):
        self.assertEqual(action(key="a"), "")

    def test_empty_text_never_sends(self):
        text = page()
        self.assertIn("ta.value.trim()", text)
        self.assertIn("if (!text.trim()) return;", text)

    def test_send_button_is_an_icon_with_a_label(self):
        text = page()
        i = text.index('class="btn say-send"')
        btn = text[i:text.index("</button>", i)]
        self.assertIn("<svg", btn)
        self.assertIn("currentColor", btn)
        self.assertIn("aria-label=", btn)
        self.assertIn("title=", btn)
        self.assertNotIn("</svg>${i18n", btn)


LINES = [
    {"k": "started", "task": "登录 API", "at": 1790000000.0},
    {"k": "steps", "at": 1790000010.0, "steps": [{"tool": "Edit", "name": "Edit", "file": "login.py"},
                                                {"tool": "Read", "name": "Read"},
                                                {"tool": "Read", "name": "Grep"}, {"tool": "Read", "name": "Glob"}]},
    {"k": "stuck", "question": "red or blue?", "tool": "AskUserQuestion", "at": 1790000020.0},
    {"k": "toLead", "at": 1790000021.0},
    {"k": "toGov", "at": 1790000022.0},
    {"k": "qa", "question": "red or blue?", "tool": "AskUserQuestion", "ok": True, "answer": "blue", "at": 1790000030.0},
    {"k": "stuck", "question": "", "tool": "Bash", "at": 1790000040.0},
    {"k": "qa", "question": "", "tool": "Bash", "ok": True, "at": 1790000041.0},
    {"k": "waiting", "at": 1790000050.0},
    {"k": "done", "at": 1790000060.0},
    {"k": "left", "at": 1790000070.0},
    {"k": "something-new", "at": 1790000080.0},
]


HIST_HEAD = r"""
const V = __payload.view, A = V.territories[0], L = __payload.lines;
function buildLand(view){ officeState(view); }
const snap = hist => { const ev = { type: 'snapshot', world: V, gov: { state: 'idle', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'idle' }],
  agents: [{ id: 'w1', role: 'worker', label: 'worker', task: '登录 API', terr: A.id, tools: {} },
           { id: 'w2', role: 'worker', label: 'worker', task: '别的', terr: A.id, tools: {} }] };
  if (hist !== undefined) ev.hist = hist; return ev; };
const texts = c => c.acts.map(a => a.text);
"""


HIST_DRIVER = HIST_HEAD + r"""
const out = { keep: HIST_KEEP, before: serverHist };
apply(snap({ w1: L, w2: [] }));
const c = byId('w1'), d = byId('w2');
out.on = serverHist; out.own = [ownHist(c)];
out.acts = texts(c); out.ats = c.acts.map(a => a.at);
out.want = [i18n('hist.started', { task: '登录 API' }),
  [stepText({ tool: 'Edit', name: 'Edit', file: 'login.py' }), stepText({ tool: 'Read', name: 'Read' }), stepText({ tool: 'Read', name: 'Grep' })].join(' · '),
  i18n('hist.stuck', { text: 'red or blue?' }), i18n('hist.toLead'), i18n('hist.toGov'),
  i18n('hist.stuck', { text: stuckText({ tool: 'Bash', question: '' }) }), i18n('hist.waiting'), i18n('hist.done'), i18n('hist.left')];
out.steps = c.acts[1].steps;
out.qa = c.qa; out.qaWant = [{ q: 'red or blue?', a: 'blue', at: 1790000030 }, { q: stuckText({ tool: 'Bash', question: '' }), a: i18n('answer.default'), at: 1790000041 }];
out.other = { acts: d.acts.length, qa: d.qa.length };
// the panel's own list is built from the same stores
out.panel = personHistory(c, []).map(x => x.k);

// live: the page's own handlers add nothing now, the server's 'hist' lines do
const n0 = c.acts.length, q0 = c.qa.length;
apply({ type: 'tool', id: 'w1', tool: 'Edit', name: 'Edit', file: 'a.py' });
apply({ type: 'stuck', id: 'w1', question: 'q?', tool: 'AskUserQuestion' });
apply({ type: 'waiting', id: 'w1' });
apply({ type: 'relay', id: 'w1', to: 'governor', lead: '' });
apply({ type: 'done', id: 'w1' });
actLog(c, 'by hand'); actTool(c, 'step by hand');
giveAnswer({ question: 'q', answer: 'a', qa: c.qa, stuck: true, state: 'asking', terr: A.id });
apply({ type: 'spawn', id: 'w3', role: 'worker', label: 'worker', task: '新来的', terr: A.id });
out.liveOwn = { acts: c.acts.length - n0, qa: c.qa.length - q0, w3: byId('w3').acts.length };

const r1 = apply({ type: 'hist', id: 'w3', line: { k: 'started', task: '新来的', at: 1790000100 }, fold: false });
apply({ type: 'hist', id: 'w3', line: { k: 'steps', at: 1790000101, steps: [{ tool: 'Edit', name: 'Edit', file: 'a.py' }] }, fold: false });
apply({ type: 'hist', id: 'w3', line: { k: 'steps', at: 1790000101, steps: [{ tool: 'Edit', name: 'Edit', file: 'a.py' }, { tool: 'Bash', name: 'Bash' }] }, fold: true });
out.w3 = texts(byId('w3')); out.w3want = [i18n('hist.started', { task: '新来的' }), [stepText({ tool: 'Edit', name: 'Edit', file: 'a.py' }), stepText({ tool: 'Bash', name: 'Bash' })].join(' · ')];
out.ret = r1 === byId('w3');
// a fold with no steps line before it is a new line; a fold after another line too
apply({ type: 'hist', id: 'w3', line: { k: 'waiting', at: 1790000102 }, fold: false });
apply({ type: 'hist', id: 'w3', line: { k: 'steps', at: 1790000103, steps: [{ tool: 'Read', name: 'Read' }] }, fold: true });
out.w3n = byId('w3').acts.length;
out.nobody = apply({ type: 'hist', id: 'ghost', line: { k: 'done', at: 1 }, fold: false });

// the cap
for (let i = 0; i < 450; i++) histLine(d, { k: i % 2 ? 'done' : 'waiting', at: 1790001000 + i }, false);
for (let i = 0; i < 450; i++) histLine(d, { k: 'qa', question: 'q' + i, tool: 'AskUserQuestion', ok: true, at: 1790002000 + i }, false);
out.cap = { acts: d.acts.length, first: d.acts[0].at, last: d.acts[d.acts.length - 1].at, qa: d.qa.length, q: d.qa[d.qa.length - 1].q };
histLine(d, null, false); histLine(d, { at: 5 }, false);
out.capSame = d.acts.length;

// a reload (a new snapshot) replaces, never doubles
apply(snap({ w1: L.slice(0, 2), w2: [] }));
out.again = { w1: byId('w1').acts.length, qa: byId('w1').qa.length, w2: byId('w2').acts.length, w3: byId('w3').acts.length };
__out = out;
"""


OLD_SERVER_DRIVER = HIST_HEAD + r"""
const out = {};
apply(snap(undefined));                       // an older server: no hist in the snapshot
out.on = serverHist;
const c = byId('w1');
out.placed = c.acts.length;
apply({ type: 'tool', id: 'w1', tool: 'Edit', name: 'Edit', file: 'a.py' });
apply({ type: 'waiting', id: 'w1' });
out.acts = texts(c); out.want = [stepText({ tool: 'Edit', name: 'Edit', file: 'a.py' }), i18n('hist.waiting')];
out.own = ownHist(c);
// the server's history comes on later (a new server after a restart): the snapshot switches it on ...
apply(snap({ w1: L.slice(0, 1), w2: [] }));
out.onLater = serverHist; out.later = texts(byId('w1'));
// ... and a snapshot with none switches it off again, the lines on the page stay
apply(snap(undefined));
out.off = serverHist; out.kept = texts(byId('w1')).length;
__out = out;
"""


HIST_NEEDS = ("apply", "byId", "officeState", "i18n", "actLog", "actTool", "giveAnswer", "personHistory", "stepText",
              "stuckText", "histLine", "ownHist", "HIST_KEEP", "serverHist")


class TestServerHistory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(HIST_DRIVER, {"view": named_view(), "lines": LINES}, HIST_NEEDS)

    def test_the_switch(self):
        r = self.r
        self.assertEqual(r["keep"], 200)
        self.assertFalse(r["before"], "off until a snapshot says the server keeps the history")
        self.assertTrue(r["on"])
        self.assertEqual(r["own"], [False], "the page writes nothing itself once the server keeps the history")

    def test_the_snapshot_fills_the_history(self):
        r = self.r
        self.assertEqual(r["acts"], r["want"], "worded by the page: the same words as the live lines")
        self.assertEqual(r["ats"][0], 1790000000, "the server's time, not the time the page opened")
        self.assertEqual(r["ats"], sorted(r["ats"]))
        self.assertEqual(len(r["steps"]), 3, "Grep and Glob say the same thing: one step")
        self.assertEqual(r["other"], {"acts": 0, "qa": 0})

    def test_questions_and_answers(self):
        self.assertEqual(self.r["qa"], self.r["qaWant"])
        self.assertEqual(self.r["panel"].count("ask"), 2, "the panel shows them as question cards")
        self.assertEqual(self.r["panel"].count("act"), len(self.r["want"]))

    def test_live_the_page_writes_nothing_itself(self):
        self.assertEqual(self.r["liveOwn"], {"acts": 0, "qa": 0, "w3": 0},
                         "with the server's history on, every line comes from the server: two tabs show the same")

    def test_live_lines_from_the_server(self):
        r = self.r
        self.assertEqual(r["w3"], r["w3want"], "a fold replaces the last steps line")
        self.assertTrue(r["ret"], "apply returns the person")
        self.assertEqual(r["w3n"], 4, "a fold with no steps line right before it is a new line")
        self.assertIsNone(r["nobody"])

    def test_the_cap(self):
        c = self.r["cap"]
        self.assertEqual((c["acts"], c["qa"]), (200, 200))
        self.assertEqual((c["first"], c["last"]), (1790001250, 1790001449), "the oldest go")
        self.assertEqual(c["q"], "q449")
        self.assertEqual(self.r["capSame"], 200, "no line, or a line with no k, adds nothing")

    def test_a_reload_replaces(self):
        self.assertEqual(self.r["again"], {"w1": 2, "qa": 0, "w2": 0, "w3": 0},
                         "the snapshot is the truth: no line twice, a person with no list has none")


class TestNoServerHistory(unittest.TestCase):

    def test_an_older_server_as_before(self):
        r = run_sim(OLD_SERVER_DRIVER, {"view": named_view(), "lines": LINES}, HIST_NEEDS)
        self.assertFalse(r["on"])
        self.assertEqual(r["placed"], 0)
        self.assertEqual(r["acts"], r["want"], "the page writes its own lines, as before")
        self.assertTrue(r["own"])
        self.assertTrue(r["onLater"])
        self.assertEqual(len(r["later"]), 1, "the server's lines replace the page's own")
        self.assertFalse(r["off"])
        self.assertEqual(r["kept"], 1)


FACE_REQUIRED = REQUIRED + ("turnToward", "angleDiff", "faceWant", "TURN_RATE", "TURN_WALK_MAX", "goTo",
                            "freeAt", "findPath", "governorFigures", "govMove")


def diff(a, b):
    d = (b - a) % (2 * math.pi)
    return d - 2 * math.pi if d > math.pi else d


UNIT_DRIVER = r"""
const cases = [];
for (const [y, w] of [[0, 1], [0, -1], [3, -3], [-3, 3], [2.9, -2.9], [0.1, 0.1], [1, 1 + 4 * Math.PI], [-6, 6]])
  cases.push({ y, w, d: angleDiff(y, w), one: turnToward(y, w, 1 / 60), half: turnToward(turnToward(y, w, 1 / 120), w, 1 / 120),
    big: turnToward(y, w, 0.1), far: turnToward(y, w, 5) });
let y = 0; for (let i = 0; i < 24; i++) y = turnToward(y, Math.PI, 1 / 60);   // 0.4 s, 180 deg
let y2 = 0; for (let i = 0; i < 6; i++) y2 = turnToward(y2, Math.PI, 1 / 60);  // 0.1 s
__out = { cases, after04: y, after01: y2, keep: turnToward(1.2, null, .1), keepU: turnToward(1.2, undefined, .1),
  RATE: TURN_RATE, MAX: TURN_WALK_MAX };
"""


class TestTurnMath(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(UNIT_DRIVER, {}, FACE_REQUIRED)

    def test_constants(self):
        self.assertTrue(10 <= self.r["RATE"] <= 24, self.r["RATE"])
        self.assertTrue(math.pi / 4 - 1e-9 <= self.r["MAX"] <= math.pi / 3 + 1e-9, self.r["MAX"])

    def test_angle_diff_wraps(self):
        for c in self.r["cases"]:
            with self.subTest(case=(c["y"], c["w"])):
                self.assertGreater(c["d"], -math.pi - 1e-9)
                self.assertLessEqual(c["d"], math.pi + 1e-9)
                self.assertAlmostEqual(c["d"], diff(c["y"], c["w"]), places=9)

    def test_short_way_round_never_past(self):
        for c in self.r["cases"]:
            with self.subTest(case=(c["y"], c["w"])):
                want = diff(c["y"], c["w"])
                for k in ("one", "big", "far"):
                    moved = c[k] - c["y"]
                    if abs(want) < 1e-12:
                        self.assertAlmostEqual(moved, 0, places=9)
                        continue
                    self.assertGreaterEqual(moved * want, -1e-12, "%s: turns the short way" % k)
                    self.assertLessEqual(abs(moved), abs(want) + 1e-9, "%s: never past the target" % k)
                self.assertAlmostEqual(diff(c["far"], c["w"]), 0, places=3, msg="5 s: there")

    def test_frame_rate_independent(self):
        for c in self.r["cases"]:
            with self.subTest(case=(c["y"], c["w"])):
                self.assertAlmostEqual(c["one"], c["half"], places=9)

    def test_fast_enough(self):
        self.assertLess(abs(diff(self.r["after04"], math.pi)), 0.05, "180 deg done in 0.4 s")
        self.assertLess(abs(diff(self.r["after01"], math.pi)), math.pi - math.radians(60), "60 deg in the first 0.1 s")

    def test_no_want_keeps_the_facing(self):
        self.assertEqual(self.r["keep"], 1.2)
        self.assertEqual(self.r["keepU"], 1.2)


GONE_FUNCTIONS = ("renderRoster", "renderBalance", "balanceHtml", "kindBar", "openBalanceKind", "signText")


def win_block():
    m = re.search(r'<div class="win" id="win"[^>]*>', markup())
    if not m:
        return None, ""
    text = markup()
    depth, i = 0, m.start()
    for tag in re.finditer(r"<(/?)div\b[^>]*>", text[m.start():]):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return m.group(0), text[m.start():m.start() + tag.end()]
    return m.group(0), text[m.start():]


STATE_JS = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, selected: null, winLog: false, lastDetailKey: 'x', lastRoster: 'x',
  needFrame: false, govTerr: 't1', renders: 0 };
box.renderPanel = () => { box.renders++; };
box.afterPick = () => {}; // city-ux2: a pick also follows + opens the panel -- tested in test_agent_city_ux2
// city-office: selectFrom goes through the page's one select(key) path (it also flies and follows); a stand-in
// with its window effect only: a key selects that person or area manager, and the log closes
box.select = key => { box.selected = !key ? null : key.slice(0, 4) === 'gov:' ? { t: 'gov', terr: key.slice(4) } : { t: 'c', id: key };
  box.winLog = false; box.renderPanel(); };
vm.createContext(box);
vm.runInContext(fns, box);
const out = {};
const snap = () => ({ state: box.winState(), selected: box.selected, renders: box.renders });
out.fresh = snap();
box.selectFrom('c7'); out.person = snap();
box.openLog(); out.log = snap();
box.selectFrom('gov:t1'); out.gov = snap();
box.closeWin(); out.closed = snap();
box.openLog(); box.closeWin(); out.logClosed = snap();
require(`fs`).writeSync(1, JSON.stringify(out));
"""


class TestGone(unittest.TestCase):
    def test_no_right_column(self):
        text = page()
        for needle in ('id="panel"', "data-card=", 'class="card-head"', 'id="roster"', 'id="balance"',
                       "agent-city-cards"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)

    def test_nothing_asks_for_a_kind(self):
        text = page()
        for word in ("还差", "城市平衡", "era-sign"):
            with self.subTest(word=word):
                self.assertNotIn(word, text)

    def test_the_old_functions_are_gone(self):
        for name in GONE_FUNCTIONS:
            with self.subTest(fn=name):
                self.assertIsNone(function_source_focus(name), name + " is still in the page")

    def test_no_side_column_in_the_css(self):
        self.assertIsNone(re.search(r"grid-template-columns:[^;}]*360px", style()),
                          "a 360px column is still in the layout")


class TestWindowMarkup(unittest.TestCase):
    def test_window_over_the_city(self):
        open_tag, block = win_block()
        self.assertIsNotNone(open_tag, '<div class="win" id="win" ...> not found')
        for attr in ('role="dialog"', 'aria-labelledby="win-title"', "hidden"):
            with self.subTest(attr=attr):
                self.assertIn(attr, open_tag)
        stage = re.search(r'id="stage"', markup())
        self.assertIsNotNone(stage)
        self.assertLess(stage.start(), markup().index('id="win"'))

    def test_window_holds_title_close_detail_and_log(self):
        _, block = win_block()
        block = zh_resolved(block)  # idea-city C1: aria-label text may come from TEXT (data-t-aria)
        self.assertIn('id="win-title"', block)
        self.assertRegex(block, r'<button type="button"[^>]*id="win-close"[^>]*aria-label="关闭"|'
                                r'<button type="button"[^>]*aria-label="关闭"[^>]*id="win-close"')
        self.assertIn('id="detail"', block)
        self.assertIn('id="log"', block)

    def test_window_css(self):
        self.assertRegex(style(), r"\.win\{[^}]*position:absolute")
        self.assertIn(".win", media_block("@media (max-width: 960px)"))

    def test_phone_city_fills_the_screen(self):
        block = media_block("@media (max-width: 960px)")
        self.assertNotIn("66vh", block)
        # cloud-polish (2026-10-02, bounce 1 D1): the stage takes what is left of the window at EVERY width now,
        # so the three rules that fill the screen are the page's base rules (before, they were in the phone
        # block only and a computer got a fixed height that ran under the screen). The phone block keeps its
        # smaller minimum and must not undo them. Seen in a browser at 390 x 844: the page is 844 px high.
        base = style()[:style().index("@media (max-width: 960px)")]
        self.assertRegex(base, r"\.stage-col\{[^}]*flex:1")
        self.assertRegex(base, r"\.stage\{[^}]*flex:1 1 0")
        self.assertRegex(base, r"\.stage canvas\{[^}]*position:absolute")
        self.assertRegex(block, r"\.stage\{[^}]*min-height:340px")
        self.assertNotRegex(block, r"\.stage(?:-col)?\{[^}]*flex:none")
        self.assertNotRegex(block, r"\.stage\{(?:[^}]*;)?height:")

    def test_log_button_in_the_top_bar(self):
        bar = re.search(r'<header class="bar"[^>]*>(.*?)</header>', zh_resolved(markup()), re.S)
        self.assertIsNotNone(bar, '<header class="bar"> not found')
        self.assertRegex(bar.group(1), r'<button type="button"[^>]*id="logbtn"[^>]*>[^<]*动态')


class TestWindowState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [n for n in ("winState", "openLog", "closeWin", "selectFrom") if function_source_focus(n) is None]
        if missing:
            raise AssertionError("not found in the page: " + ", ".join(missing))
        cls.r = run_node(STATE_JS, {"fns": page_fns("winState", "openLog", "closeWin", "selectFrom")})

    def test_closed_until_something_is_picked(self):
        self.assertIsNone(self.r["fresh"]["state"])

    def test_picking_a_person_opens_its_window(self):
        self.assertEqual(self.r["person"]["state"], "detail")
        self.assertEqual(self.r["person"]["selected"], {"t": "c", "id": "c7"})

    def test_the_log_replaces_the_detail(self):
        self.assertEqual(self.r["log"]["state"], "log")
        self.assertIsNone(self.r["log"]["selected"])
        self.assertGreater(self.r["log"]["renders"], self.r["person"]["renders"], "openLog redraws")

    def test_picking_from_the_log_shows_the_detail(self):
        self.assertEqual(self.r["gov"]["state"], "detail")
        self.assertEqual(self.r["gov"]["selected"], {"t": "gov", "terr": "t1"})

    def test_close_leaves_only_the_city(self):
        for name in ("closed", "logClosed"):
            with self.subTest(after=name):
                self.assertIsNone(self.r[name]["state"])
                self.assertIsNone(self.r[name]["selected"])

    def test_win_log_is_top_level(self):
        self.assertRegex(inline_script(), r"(?m)^let winLog = false;")


class TestWindowWiring(unittest.TestCase):
    def test_render_panel_draws_the_window_only(self):
        body = function_source_focus("renderPanel") or ""
        self.assertIn("renderWin()", body)
        for name in ("renderRoster(", "renderBalance("):
            with self.subTest(fn=name):
                self.assertNotIn(name, body)

    def test_render_win(self):
        body = zh_resolved(function_source_focus("renderWin") or "")  # idea-city C1
        self.assertTrue(body, "renderWin() not found")
        for needle in ("'#win'", "winState()", "'#detail'", "'#log'", "'#win-title'", "动态", "hidden"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)

    def test_close_and_log_buttons(self):
        text = inline_script()
        self.assertRegex(text, r"\$\('#win-close'\)\.addEventListener\('click',[^\n]*closeWin\(\)")
        self.assertRegex(text, r"\$\('#logbtn'\)\.addEventListener\('click',[^\n]*openLog\(\)")

    def test_rows_in_the_window_open_that_person(self):
        text = inline_script()
        m = re.search(r"\$\('#detail'\)\.addEventListener\('click', e => \{(.*?)\n\}\);", text, re.S)
        self.assertIsNotNone(m, "#detail click handler not found")
        self.assertIn("data-sel", m.group(1))
        self.assertIn("selectFrom(", m.group(1))
        self.assertIn("data-sel", function_source_focus("renderDetail") or "")

    def test_a_tap_on_the_city_closes_the_log(self):
        body = function_source_focus("endPointer") or ""
        # city-ux U6: the tap goes through selectPick(), the one select path (it clears winLog)
        if "selectPick(" in body:
            body = function_source_focus("selectPick") or ""
        if "select(" in body:   # city-office: selectPick -> select -> afterSelect, which clears winLog
            body = function_source_focus("afterSelect") or ""
        self.assertRegex(body, r"winLog = false|closeWin\(")


CJK = re.compile(r"[㐀-鿿＀-￯　-〿]")


def need(*names):
    for n in names:
        if tp.script_function_source(n) is None:
            raise AssertionError("function %s(...) not found in the page script" % n)
    return tp.page_fns(*names)


def strip_comments(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(^|[\s;{}(),])//[^\n]*", r"\1", text)


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
require(`fs`).writeSync(1, JSON.stringify(out));
"""


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
require(`fs`).writeSync(1, JSON.stringify(out));
"""


STATUS_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, governorAt: () => ({ x: 0, y: 0 }) };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const base = { state: 'working', askKind: '', askPhase: '', relay: '' };
require(`fs`).writeSync(1, JSON.stringify({
  waiting: box.citizenStatus(Object.assign({}, base, { waiting: true })),
  waitingAsk: box.citizenStatus(Object.assign({}, base, { waiting: true, askKind: 'permission' })),
  plain: box.citizenStatus(base),
}));
"""


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

    def test_i18n(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { lit, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
for (const lang of ['en', 'zh', 'fr', '__CITY_LANG__']) {
  const box = { Math, JSON, console };
  vm.createContext(box);
  vm.runInContext("var LANG = '" + lang + "'; var TEXT = " + lit + ";\n" + fns, box);
  box.TEXT.zh.__t = 'a {x} b {x}'; box.TEXT.en.__t = 'A {x} B';
  out[lang] = { t: box.i18n('__t', { x: 1 }), unknown: box.i18n('no.such.key') };
}
require(`fs`).writeSync(1, JSON.stringify(out));
"""
        lit = tp.const_object("TEXT")
        self.assertIsNotNone(lit)
        r = tp.run_node(js, {"lit": lit, "fns": need("i18n")})
        self.assertEqual(r["en"]["t"], "A 1 B")
        for lang in ("zh", "fr", "__CITY_LANG__"):
            self.assertEqual(r[lang]["t"], "a 1 b 1", lang)
        self.assertEqual(r["en"]["unknown"], "no.such.key")


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
        pool = tp.script_function_source("updateGovPool") or ""
        self.assertNotRegex(pool, r"pin\(v\.bub, sx, sy, false\)")
        self.assertIn("govTalk(", pool)
        self.assertIn("govTalk(", tp.script_function_source("updateGovernor") or "")
        self.assertNotRegex(tp.inline_script(), r"\bsay\(gov\s*,")


class TestNoEmptyBubble(unittest.TestCase):
    def test_person_bubble(self):
        r = tp.run_node(BUB_JS, {"prelude": tp.constants_prelude(), "fns": need("personBubble")})
        self.assertEqual(r, {"askEmpty": "", "askQ": "q?", "talk": "hi", "talkEmpty": "", "toHall": "",
                             "none": "", "over": ""})

    def test_update_person_uses_it(self):
        self.assertIn("personBubble(c)", tp.script_function_source("updatePerson") or "")


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

    def test_snapshot(self):
        self.assertIn("a.waiting", tp.script_function_source("placeAgent") or "")


class TestNameShownOnce(unittest.TestCase):

    def test_tag_roster_and_detail_use_it(self):
        for fn in ("updatePerson", "renderDetail"):  # no roster since city-focus
            with self.subTest(fn=fn):
                self.assertIn("nameOf(", function_source(fn) or "", fn + " shows names through nameOf()")
        self.assertNotIn("${c.label} · ${c.task}", function_source("updatePerson") or "")


BIN = os.path.join(ROOT, "bin")


def page_office_editor_page():
    with open(os.path.join(BIN, "agent-city.html"), encoding="utf-8") as fh:
        return fh.read()


class TestEditorSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = page_office_editor_page()

    def fn(self, name):
        src = function_source(name)
        self.assertIsNotNone(src, name + " is missing")
        return src

    def test_functions_and_markup(self):
        for n in ("openEditor", "closeEditor", "renderEditor", "edPlace", "edRotate", "edCopy", "edRemove", "edUndo", "edRedo",
                  "edReset", "edColor", "edMaterial", "edStyle", "pickSurface", "matCanvas", "makeThumbs"):
            self.fn(n)
        self.assertRegex(self.text, r'id="edUI"')
        for old in ("dySave", "dy-s0", "saveDiy"):
            self.assertNotIn(old, self.text, "the DIY form is replaced by the editor")

    def test_styles_and_materials(self):
        m = re.search(r"const STYLES\s*=\s*\[(.*?)\n\];", self.text, re.S)
        self.assertIsNotNone(m)
        self.assertEqual(len(re.findall(r"\bm\s*:\s*\{", m.group(1))), 6)
        self.assertEqual(len(re.findall(r"\bc\s*:\s*\{", m.group(1))), 6)
        mc = self.fn("matCanvas")
        for mat in ac.FLOOR_MATERIALS:
            self.assertIn("'" + mat + "'", mc)

    def test_save(self):
        src = self.fn("closeEditor")
        self.assertIn("'/api/design'", src)
        self.assertRegex(src, r"v\s*:\s*2")
        self.assertIn("layout", src)
        self.assertIn("materials", src)
        self.assertIn("problems", src)


PAGE_office_page = os.path.join(BIN, "agent-city.html")


ASSETS_office_page = os.path.join(BIN, "agent-city-assets")


def page_office_page():
    with open(PAGE_office_page, encoding="utf-8") as fh:
        return fh.read()


class TestScene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = page_office_page()
        cls.sim = sim_section()

    def fn(self, name):
        src = function_source(name)
        self.assertIsNotNone(src, name + " is missing")
        return src

    def test_scene_functions(self):
        for name in ("buildFloor", "buildOutside", "enter", "goOutside", "goFloor", "renderLift", "renderFloorSign",
                     "renderPicker", "renderDesignPop", "addPerson", "placeDecor", "select"):
            self.fn(name)

    def test_opens_outside_and_switches_at_once(self):
        self.assertRegex(self.text, r"let view\s*=\s*'outside'")
        self.assertNotIn("camTween", self.fn("goFloor"))

    def test_select_zoom_is_halved(self):
        self.assertRegex(self.fn("select"), r"Math\.min\(cam\.dist,\s*\(fitDist\(\)\s*\+\s*9\)\s*/\s*2\)")

    def test_decor_and_slots(self):
        m = re.search(r"const DECOR\s*=\s*\{(.*?)\n\};", self.text, re.S)
        self.assertIsNotNone(m)
        keys = re.findall(r"^\s{2}(\w+)\s*[:(]", m.group(1), re.M)
        self.assertEqual(sorted(set(keys)), sorted(["robot", "conveyor", "gears", "chart", "plants", "safe",
                                                    "cabinets", "printer", "bookshelf", "clock", "cashier", "goods",
                                                    "menu", "scanner", "lightbox"]))
        self.assertRegex(self.text, r"const SLOTS\s*=\s*\[\{[^\]]*\},\s*\{[^\]]*\},\s*\{[^\]]*\}\]")

    def test_avatars_are_boxes_by_role(self):
        m = re.search(r"const STYLE\s*=\s*\{(.*?)\n\};", self.text, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        for role in ("governor", "'task-manager'", "helper", "designer"):
            self.assertIn(role, body)
        self.assertNotIn("GLTFLoader", self.text)
        self.assertNotIn("SkeletonUtils", self.text)
        self.assertNotRegex(self.text, r"\.glb")
        scripts = re.findall(r'<script src="([^"]+)"', self.text)
        self.assertEqual([s.split("?")[0] for s in scripts], ["assets/vendor/three.min.js"])

    def test_assets_hold_only_three(self):
        found = []
        for dirpath, _, files in os.walk(ASSETS_office_page):
            for f in files:
                found.append(os.path.relpath(os.path.join(dirpath, f), ASSETS_office_page))
        self.assertEqual(sorted(found), ["vendor/three.min.js"])

    def test_markup(self):
        for i in ("btnPick", "lift", "floorSign", "tags", "pickBg", "dPop", "renoBg"):
            self.assertRegex(self.text, r'id="%s"' % i)
        for i in ("repos", "stage-top", "arr-btn", "arr-bar", "arr-ov", "rail-hid", "cap-hint", "empty-land"):
            self.assertNotRegex(self.text, r'id="%s"' % i)

    def test_endpoints_and_data_only(self):
        for path in ("/api/floors", "/api/design", "/api/designer", "/api/designer/leave"):
            self.assertIn("'" + path + "'", self.text)
        self.assertNotIn("/api/layout", self.text)
        self.assertNotRegex(self.text, r"\beval\(|new Function\(")
        self.assertIn("esc(", self.fn("renderFloorSign"))

    def test_no_island_code(self):
        for name in ("buildLand", "landState", "landsOf", "startShow", "syncSites", "newBuildingRecord", "buildingName"):
            self.assertIsNone(function_source(name), name + " is island code")


class TestDemo(unittest.TestCase):
    def test_demo_world_is_the_servers(self):
        import subprocess
        from citypage import const_object  # noqa: E402
        literal = const_object("DEMO_WORLD")
        self.assertIsNotNone(literal, "const DEMO_WORLD = {...}; not found")
        out = subprocess.run([sys.executable, os.path.join(BIN, "agent_city.py"), "demo-world"],
                             capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(literal), json.loads(out.stdout))
        self.assertEqual(json.loads(literal)["v"], 2)


class TestGovernorFigureP0(unittest.TestCase):

    def test_no_governor_in_snapshot_means_no_figure(self):
        view = next(iter(plan_views().values()))
        driver = r"""
const V = __payload.view, tid = V.territories[0].id;
function buildLand(view){ officeState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: tid }, govs: [], governors: 0, asks: [], shows: [], agents: [] });
__out = { g: governorAt(tid) };
"""
        self.assertIsNone(run_sim(driver, {"view": view}, REQUIRED)["g"])


WORDS_DRIVER = r"""
const V = __payload.view, ask = __payload.ask;
function buildLand(view){ officeState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: ask.terr }, govs: [{ terr: ask.terr, state: 'busy' }],
  governors: 1, asks: [], shows: [], agents: [] });
const name = askName(ask);
apply(Object.assign({ type: 'ask' }, ask));
const asked = logEntries[0].text;
apply({ type: 'ask_closed', id: ask.id, agent: 'gov', kind: 'question', tool: 'AskUserQuestion', what: ask.what,
  by: 'owner', verb: 'answer', text: 'red', reason: '', at: 2000 });
const answered = logEntries[0].text;
apply({ type: 'spawn', id: 'w1', role: 'worker', label: 'worker', task: 'slice w1', terr: ask.terr });
const other = askName({ agent: 'w1', label: 'worker', task: 'slice w1' });
apply({ type: 'tool', id: 'w1', tool: 'Other' });
apply({ type: 'tool', id: 'w1', tool: 'Edit' });
__out = { name, asked, answered, other };
"""


class TestWords(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(WORDS_DRIVER, {"view": named_view(), "ask": ASK_Q}, REQUIRED + ("askName", "logEntries"))

    def test_the_governor_is_named_with_his_territory(self):
        self.assertEqual(self.r["name"], "repoA 区经理")
        self.assertEqual(self.r["other"], "slice w1")

    def test_log_lines_name_the_asker(self):
        self.assertIn("repoA 区经理", self.r["asked"])
        self.assertNotIn("问区经理", self.r["asked"], "the governor asks the owner, not himself")
        self.assertIn("repoA 区经理", self.r["answered"])
        self.assertIn("red", self.r["answered"])

    def test_panel_title_and_why_line(self):
        self.assertIn("askName(", function_source("renderAskPanel") or "")
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, askName: v => 'repoA 区经理' };
vm.createContext(box);
vm.runInContext(fns, box);
require(`fs`).writeSync(1, JSON.stringify({
  gov: box.askWhyLine({ kind: 'question', why: 'no-governor', agent: 'gov', terr: 't' }),
  other: box.askWhyLine({ kind: 'question', why: 'no-governor', agent: 'w1', terr: 't' }) }));
"""
        out = tp.run_node(js, {"fns": tp.constants_prelude() + "\n" + tp.page_fns("askWhyLine")})
        self.assertIn("区经理定不了，交给你", out["gov"])
        self.assertNotIn("没有区经理在", out["gov"])
        self.assertIn("没有区经理在", out["other"], "a citizen's question with no governor keeps its line")

    def test_no_tool_name_floats_over_a_head(self):
        text = page()
        self.assertNotIn("floaters.push(", text, "a tool event makes no floating tag")
        self.assertNotIn("ovEl('fl')", text)


class TestUnknownGovernorAfterRestart(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_polish_")
        self.world = os.path.join(self.base, "world.json")
        self.now = 1000.0

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def state(self):
        # city-roles: g1 holds A_REPO's main manager lock (alive), so it governs and is "unknown" after a restart
        return ac_polish.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world,
                            main_fn=lambda identity: (os.getpid(), "g1") if identity == POLISH_A_REPO else None)

    def line(self, st, ev, sid, repo=POLISH_A_REPO):
        self.now += 1
        st.feed_line({"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "Read", "nt": "", "proj": "p", "role": "",
                      "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": "", "ask": ""}, self.now)

    def govs(self, st):
        return json.loads(st.add_client().queue.get_nowait().decode("utf-8").split("data:", 1)[1])["govs"]

    def test_a_known_governor_is_unknown_after_a_restart(self):
        st = self.state()
        self.line(st, "UserPromptSubmit", "g1")
        again = self.state()
        self.assertEqual(self.govs(again), [{"terr": POLISH_TA, "state": "unknown"}])
        self.line(again, "PostToolUse", "g1")
        self.assertEqual([(g["terr"], g["state"]) for g in self.govs(again)], [(POLISH_TA, "busy")])

    def test_a_governor_that_ended_is_forgotten(self):
        st = self.state()
        self.line(st, "UserPromptSubmit", "g1")
        self.line(st, "SessionEnd", "g1")
        with open(self.world, encoding="utf-8") as fh:
            self.assertNotIn(POLISH_A_REPO, json.load(fh).get("gov_seen", {}))
        self.assertEqual(self.govs(self.state()), [])

    def test_page_says_unknown_and_draws_no_figure(self):
        driver = r"""
const V = __payload.view;
function buildLand(view){ officeState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: __payload.ta }, governors: 0, asks: [], shows: [], agents: [],
  govs: [{ terr: __payload.ta, state: 'unknown' }] });
__out = { row: govRowText(__payload.ta), at: governorAt(__payload.ta) };
"""
        r = run_sim(driver, {"view": named_view(), "ta": POLISH_TA}, REQUIRED + ("govRowText",))
        self.assertEqual(r["row"], "未知")
        self.assertIsNone(r["at"])


class TestResultThenClose(unittest.TestCase):

    def test_the_panel_closes_10s_after_its_result(self):
        driver = r"""
const V = __payload.view, ask = __payload.ask;
function buildLand(view){ officeState(view); }
let closes = 0;
function closeAskPanel(){ closes++; openAskId = null; }
function renderAskPanel(){}
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: ask.terr }, govs: [{ terr: ask.terr, state: 'busy' }],
  governors: 1, asks: [ask], shows: [], agents: [] });
openAskId = ask.id;
askAutoClose(50000);
const openBefore = closes;
apply({ type: 'ask_closed', id: ask.id, agent: 'gov', kind: 'question', tool: 'AskUserQuestion', what: ask.what,
  by: 'owner', verb: 'answer', text: 'red', reason: '', at: 2000 });
askAutoClose(9999);
const at9 = closes;
askAutoClose(10000);
__out = { openBefore, at9, at10: closes, ms: ASK_CLOSE_MS };
"""
        r = run_sim(driver, {"view": named_view(), "ask": ASK_Q}, REQUIRED + ("askAutoClose", "ASK_CLOSE_MS"))
        self.assertEqual(r["ms"], 10000)
        self.assertEqual(r["openBefore"], 0, "an open, unanswered ask never closes by itself")
        self.assertEqual(r["at9"], 0, "the result line stays 10 s")
        self.assertEqual(r["at10"], 1, "then the panel closes by itself")

    def test_every_result_path_sets_the_time_and_frame_checks_it(self):
        self.assertIn("askAutoClose(", function_source("frame") or "")
        text = page()
        self.assertGreaterEqual(len(re.findall(r"shownAt\s*[:=]", text)), 2,
                                "ask_closed and the page's own decide() both stamp shownAt")


SIM_REQUIRED_rail_panel = ("apply", "officeState", "railGroups", "railHtml", "nameOf", "fullName", "shortLabel", "factsLine",
                "doingText", "citizenStatus", "newCitizen", "citizens", "byId", "terrColor")


def top_css():
    """The page CSS without its @media blocks (the computer look)."""
    c, out, i = css(), [], 0
    while True:
        j = c.find("@media", i)
        if j < 0:
            out.append(c[i:])
            return "".join(out)
        out.append(c[i:j])
        depth, k = 0, c.index("{", j)
        for k in range(k, len(c)):
            if c[k] == "{":
                depth += 1
            elif c[k] == "}":
                depth -= 1
                if depth == 0:
                    break
        i = k + 1


def top(sel):
    return rule(sel, top_css())


def flat(block):
    return (block or "").replace(" ", "").replace("\n", "")


def px(value):
    m = re.search(r"(-?\d+(?:\.\d+)?)px", value or "")
    return float(m.group(1)) if m else None


def decl(block, prop):
    """The last value of PROP in a declaration block (no spaces), or None."""
    vals = re.findall(r"(?:^|;)%s:([^;]*)" % re.escape(prop), flat(block))
    return vals[-1] if vals else None


DRIVER_rail_panel = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
A.name = 'v4-pospro'; B.name = 'v4-plus'; for (const t of [A, B]) Object.assign(V.repos.find(r => r.id === t.id), { name: t.name, here: t.here !== false });
function buildLand(view){ officeState(view); }
const ag = (id, label, task, terr, extra) => Object.assign({ id, role: 'task-manager', label, task, stuck: false, done: false,
  tools: {}, terr, lead: '', office: null, relay: '' }, extra || {});
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 2, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'busy' }, { terr: B.id, state: 'idle' }], agents: [
  ag('s:hhhh0001', 'v4-pospro Helper', 'v4-pospro', A.id),
  ag('s:pppp0002', 'session', 'v4-pospro', A.id),
  ag('s:mmmm0003', 'v4-pospro Manager', 'v4-pospro', A.id),
  ag('s:cccc0004', 'city-polish Task Manager', 'v4-pospro', A.id),
  ag('w5', 'worker', '小票打印', A.id, { role: 'worker' }),
  ag('s:rrrr0006', 'fast-lane-deputy', '按钮颜色', A.id, { role: 'fast-lane-deputy' }),
  ag('s:aaaa1111', 'session', 'v4-plus', B.id),
  ag('s:bbbb2222', 'session', 'v4-plus', B.id),
  ag('s:xxxx0007', 'v4-plus', 'v4-plus', B.id),
  ag('s:yyyy0008', 'v4-plus', '结账', B.id),
  ag('w6', 'worker', 'picker-sticky-header Worker 1: product-p', A.id, { role: 'worker' }),
  ag('w7', 'worker', 'v4-pospro Worker 2: rail', A.id, { role: 'worker' }),
  ag('w8', 'worker', 'Worker 3: api', A.id, { role: 'worker' }),
  ag('w9', 'worker', 'fix: login', A.id, { role: 'worker' }),
  ag('w10', 'worker', 'city-polish Deputy', A.id, { role: 'worker' }),
]});
byId('s:rrrr0006').state = 'resting';
byId('s:hhhh0001').waiting = true;
const rp = newCitizen('r:dev-ann:s:9', 'task-manager', 'v4-plus', B.id); rp.label = 'session'; rp.task = 'v4-plus';
rp.remote = { who: 'Ann', device: 'lap', dev: 'dev-ann', rid: 'acme/plus', br: 'b' }; citizens.push(rp);
const ids = ['s:hhhh0001', 's:pppp0002', 's:mmmm0003', 's:cccc0004', 'w5', 's:rrrr0006', 's:aaaa1111', 's:bbbb2222', 's:xxxx0007', 's:yyyy0008',
  'w6', 'w7', 'w8', 'w9', 'w10'];
const names = {}, full = {}, facts = {};
for (const id of ids) { names[id] = nameOf(byId(id)); full[id] = fullName(byId(id)); facts[id] = factsLine(byId(id)); }
const short = [shortLabel('v4-pospro Helper', 'v4-pospro'), shortLabel('session', 'v4-plus'), shortLabel('v4-plus', 'v4-plus'),
  shortLabel('v4-plusplus Helper', 'v4-plus'), shortLabel('auto-pipeline:worker', 'auto-pipeline'),
  shortLabel('auto-pipeline · Manager', 'auto-pipeline'), shortLabel('app/api Worker', 'app'), shortLabel('Helper', ''),
  shortLabel('auto-pipeline Manager', 'auto-pipeline'), shortLabel('', 'x')];
// doingText: a working session whose task is only the repo name shows the step alone
const d = byId('s:pppp0002'); d.path = []; d.state = 'working'; d.workKind = 'read'; d.workAt = simT; d.workSince = simT; d.step = '看文件';
const doing = [doingText(d)];
const w = byId('w5'); w.path = []; w.state = 'working'; w.workKind = 'read'; w.workAt = simT; w.workSince = simT; w.step = '看文件';
doing.push(doingText(w));
const G = railGroups();
const html = railHtml(G, null, new Set(), new Set([A.id]));
const sections = [...html.matchAll(/<section\b[^>]*>/g)].map(m => m[0]);
const heads = G.map(g => {
  const i = html.indexOf('data-grp="' + g.terr + '"');
  const m = /<span class="n">\s*(\d+)\s*<\/span>/.exec(html.slice(i));
  return { terr: g.terr, rows: g.rows.length, n: m ? +m[1] : null, color: g.color };
});
const rowDots = [...html.matchAll(/data-focus="([^"]*)"[^>]*>\s*<span class="([^"]*)"><\/span>\s*<b>([^<]*)<\/b>\s*<span class="chip ([^"]*)"/g)]
  .map(m => ({ id: m[1], dot: m[2], name: m[3], chip: m[4] }));
__out = { a: A.id, b: B.id, names, full, facts, short, doing, sections, heads, rowDots, html };
"""


def payload_rail_panel():
    return {"view": two_territory_view(), "ta": TA, "tb": TB}


C2_DRIVER = r"""
const texts = ['<task-notification>\n<task-id>b1</task-id>', '  <agent-message from="x">hi</agent-message>',
  'Another Claude session sent a message:\n<agent-message from="a2">done</agent-message>', '<teammate-message teammate_id="w">x',
  '<system-reminder>x</system-reminder>', '<command-name>/loop</command-name>', '<command-message>loop</command-message>',
  '<local-command-stdout>ok</local-command-stdout>', '<bash-input>ls</bash-input>', '<user-prompt-submit-hook>x',
  '[Request interrupted by user]', 'This session is being continued from a previous conversation that ran out of context.',
  'fix the login page', '<pasted_content id="1">notes</pasted_content> use these', 'please look at <task-notification> handling',
  'Main manager: go', '', 'x'];
const machine = texts.map(t => isMachinePrompt(t));
const E = [
  { id: 1, kind: 'prompt', text: 'fix the login page', at: 1 },
  { id: 2, kind: 'reply', text: 'fixed', at: 2 },
  { id: 3, kind: 'prompt', text: '<task-notification>\n<task-id>b1</task-id>', at: 3 },
  { id: 4, kind: 'reply', text: 'worker done, checking', at: 4 },
  { id: 5, kind: 'owner', text: 'stop for now', at: 5, state: 'delivered' },
  { id: 6, kind: 'reply', text: 'stopped', at: 6 },
  { id: 7, kind: 'prompt', text: 'Another Claude session sent a message:\n<agent-message from="m">go</agent-message>', at: 7 },
  { id: 8, kind: 'reply', text: 'ok manager', at: 8 },
];
const WRAP = '<task-notification>\n<summary>Stop hook feedback</summary>\n[agent-city] The owner typed this in the city page: hi';
const owned = markMain([
  { id: 1, kind: 'owner', text: 'hi', at: 1, state: 'delivered' },
  { id: 2, kind: 'prompt', text: WRAP, at: 2 },
  { id: 3, kind: 'reply', text: 'answer to the owner', at: 3 },
  { id: 4, kind: 'prompt', text: '<teammate-message teammate_id="w">x</teammate-message>', at: 4 },
  { id: 5, kind: 'reply', text: 'ok teammate', at: 5 },
], false).map(e => [e.id, e.main]);
const frozen = JSON.stringify(E);
const session = markMain(E, false).map(e => [e.id, e.main]);
const sub = markMain([{ id: 9, kind: 'reply', text: 'report', at: 1 }], true).map(e => e.main);
const first = markMain([{ id: 10, kind: 'reply', text: 'hello', at: 1 }], false).map(e => e.main);
const untouched = JSON.stringify(E) === frozen && !('main' in E[0]);
const c = { acts: [{ at: 0.5, text: '出门：x' }, { at: 2.5, text: '改代码 · 看文件' }], qa: [{ q: 'q?', a: 'a', at: 1.5 }], stuck: false, lead: '' };
const hist = personHistory(c, E).map(it => [it.k, it.main]);
const shown = mainOnly(personHistory(c, E)).map(it => it.k + ':' + (it.text || it.q));
const w = { acts: [], qa: [], stuck: false, lead: 's:L' };
const subHist = personHistory(w, [{ id: 11, kind: 'reply', text: 'report to lead', at: 1 }]).map(it => it.main);
const plain = mainOnly([{ k: 'x' }, { k: 'y', main: false }, { k: 'z', main: true }]).map(it => it.k);
__out = { owned, machine, session, sub, first, untouched, hist, shown, subHist, plain, starts: MACHINE_STARTS };
"""


class TestShortNames(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(DRIVER_rail_panel, payload_rail_panel(), SIM_REQUIRED_rail_panel)

    def test_short_label(self):
        self.assertEqual(self.r["short"], ["Helper", "session", "", "v4-plusplus Helper", "worker", "Manager",
                                           "api Worker", "Helper", "Manager", ""])

    def test_names_inside_the_repo(self):
        n = self.r["names"]
        self.assertEqual(n["s:hhhh0001"], "Helper")
        self.assertEqual(n["s:pppp0002"], "session", "a task that is only the repo name is dropped")
        self.assertEqual(n["s:mmmm0003"], "Manager")
        self.assertEqual(n["s:cccc0004"], "city-polish Task Manager", "a feature name is not the repo name")
        self.assertEqual(n["w5"], "worker · 小票打印")
        self.assertEqual(n["s:xxxx0007"], "v4-plus", "nothing left: the label as it is")
        self.assertEqual(n["s:yyyy0008"], "结账", "an empty label takes the task's place")

    def test_worker_names_drop_the_repeated_kind_and_feature(self):
        n, f = self.r["names"], self.r["facts"]
        self.assertEqual(n["w6"], "Worker 1 · product-p")
        self.assertEqual(n["w7"], "Worker 2 · rail", "the repo goes first, then the kind rule")
        self.assertEqual(n["w8"], "Worker 3 · api")
        self.assertEqual(n["w9"], "worker · fix: login", "no <Kind> <n>: no change")
        self.assertEqual(n["w10"], "worker · city-polish Deputy")
        self.assertEqual(f["w6"], "v4-pospro · picker-sticky-header Worker 1: product-p", "the full task in the subtitle only")
        self.assertEqual(f["w7"], "v4-pospro · Worker 2: rail", "the repo once")

    def test_twins_are_told_apart_only_inside_one_repo(self):
        n = self.r["names"]
        self.assertEqual([n["s:aaaa1111"], n["s:bbbb2222"]], ["session #1111", "session #2222"])
        self.assertEqual(n["s:pppp0002"], "session", "v4-pospro's session is in another repo: no tag")

    def test_no_name_repeats_the_repo(self):
        for cid, name in self.r["names"].items():
            if cid in ("s:xxxx0007",):
                continue
            with self.subTest(id=cid):
                self.assertNotIn("v4-pospro", name)
                self.assertNotIn("v4-plus", name)

    def test_full_name_for_the_log(self):
        f = self.r["full"]
        self.assertEqual(f["s:hhhh0001"], "v4-pospro · Helper")
        self.assertEqual(f["s:pppp0002"], "v4-pospro · session")
        self.assertEqual([f["s:aaaa1111"], f["s:bbbb2222"]], ["v4-plus · session #1111", "v4-plus · session #2222"])
        self.assertEqual(f["w5"], "v4-pospro · worker · 小票打印")
        self.assertEqual(f["s:xxxx0007"], "v4-plus", "never the repo twice")

    def test_subtitle_names_the_repo_once(self):
        f = self.r["facts"]
        self.assertEqual(f["s:hhhh0001"], "v4-pospro")
        self.assertEqual(f["s:pppp0002"], "v4-pospro")
        self.assertEqual(f["s:cccc0004"], "v4-pospro")
        self.assertEqual(f["w5"], "v4-pospro", "the task is already in the name")
        self.assertEqual(f["s:aaaa1111"], "v4-plus")

    def test_doing_line_never_shows_the_repo(self):
        self.assertEqual(self.r["doing"][0], "看文件")
        self.assertEqual(self.r["doing"][1], "小票打印 · 看文件")

    def test_rail_rows_show_the_short_name(self):
        rows = {r["id"]: r["name"] for r in self.r["rowDots"]}
        self.assertEqual(rows.get("s:hhhh0001"), "Helper")
        self.assertEqual(rows.get("s:aaaa1111"), "session #1111")
        for cid, name in rows.items():
            if cid.startswith("gov:") or cid == "s:xxxx0007":
                continue
            with self.subTest(id=cid):
                self.assertNotIn("v4-p", name)


class TestRailGroups(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(DRIVER_rail_panel, payload_rail_panel(), SIM_REQUIRED_rail_panel)

    def test_colour_on_the_section(self):
        by = {h["terr"]: h for h in self.r["heads"]}
        for sec in self.r["sections"]:
            with self.subTest(sec=sec):
                m = re.search(r'data-terr="([^"]*)"', sec)
                self.assertIsNotNone(m)
                self.assertRegex(sec, r'class="rail-grp"')
                self.assertIn('style="--rc:%s"' % by[m.group(1)]["color"], sec)


class TestNamesDrawn(unittest.TestCase):
    """The 3D part shows nameOf / fullName / factsLine where the contract says."""

    def test_short_name_everywhere_in_a_repo(self):
        for fn in ("railRowHtml", "updatePerson", "winTitle", "renderDetail", "renderFollow"):
            with self.subTest(fn=fn):
                self.assertTrue("nameOf(" in (function_source(fn) or ""), fn + " shows nameOf(c)")

    def test_log_keeps_the_full_name(self):
        self.assertTrue("fullName(" in (function_source("chatDisplayName") or ""), "chatDisplayName uses fullName(pc)")

    def test_subtitle_from_facts_line(self):
        self.assertTrue("factsLine(c)" in (function_source("renderDetail") or ""), "renderDetail's subtitle is esc(factsLine(c))")

    def test_governor_title_is_just_governor(self):
        src = function_source("winTitle") or ""
        line = next((l for l in src.splitlines() if "selected.t === 'gov'" in l), "")
        self.assertTrue("who.governor" in line and "gov.title" not in line,
                        "winTitle for the governor is i18n('who.governor'): the repo shows in the subtitle, not twice")


class TestPanelCss(unittest.TestCase):

    def test_a_bit_wider(self):
        m = re.search(r"--msg-w\s*:\s*(\d+)px", css())
        self.assertIsNotNone(m)
        self.assertTrue(360 <= int(m.group(1)) <= 400, m.group(1))

    def test_full_height(self):
        w = flat(top(".win"))
        for bit in ("right:12px", "top:12px", "bottom:12px", "width:var(--msg-w)"):
            self.assertIn(bit, w, bit)

    def test_history_takes_what_is_left_and_scrolls(self):
        c = top(".chat")
        self.assertIn(decl(c, "max-height"), (None, "none"), "no 220 px cap")
        self.assertEqual(decl(c, "min-height"), "0")
        self.assertEqual(decl(c, "overflow") or decl(c, "overflow-y"), "auto")
        f = decl(c, "flex")
        self.assertIsNotNone(f, ".chat has a flex")
        parts = f.split() if " " in (f or "") else re.findall(r"\d+(?:\.\d+)?%?|auto|none", f)
        self.assertNotEqual(parts[0], "0", "it grows to fill the panel")
        self.assertFalse(len(parts) > 1 and parts[1] == "0", "it shrinks")

    def test_box_and_send_on_one_line(self):
        s = top(".say")
        self.assertEqual(decl(s, "display"), "flex")
        self.assertNotEqual(decl(s, "flex-direction"), "column")
        t = top(".say textarea")
        self.assertTrue((decl(t, "flex") or "").startswith("1") or decl(t, "flex-grow") == "1", "the box takes the room")
        self.assertEqual(decl(t, "min-width"), "0")
        self.assertEqual(decl(t, "resize"), "none")
        for prop in ("min-height", "height"):
            v = px(decl(t, prop))
            self.assertIsNotNone(v, prop)
            self.assertLessEqual(v, 40, prop + ": one line")
        b = flat(top(".say .btn"))
        self.assertTrue("white-space:nowrap" in b or "flex:none" in b, "发送 never wraps")

    def test_new_message_chip_just_above_the_row(self):
        for where, block in (("computer", top(".newmsg")), ("phone", rule(".newmsg", media_960()) or top(".newmsg"))):
            with self.subTest(where=where):
                v = px(decl(block, "bottom"))
                self.assertIsNotNone(v)
                self.assertLessEqual(v, 80)

    def test_phone_history_never_collapses(self):
        v = px(decl(rule(".chat", media_960()), "min-height"))
        self.assertIsNotNone(v, "@media (max-width: 960px) .chat{min-height:...}")
        self.assertGreaterEqual(v, 80)


class TestMainMessages(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(C2_DRIVER, {}, ("isMachinePrompt", "markMain", "personHistory", "mainOnly", "MACHINE_STARTS"))

    def test_machine_prompts(self):
        self.assertEqual(self.r["machine"], [True] * 12 + [False] * 6)

    def test_starts_listed(self):
        for start in ("<task-notification", "<agent-message", "<teammate-message", "Another Claude session sent a message",
                      "<system-reminder", "<command-name", "<command-message", "<local-command-", "<bash-input",
                      "<user-prompt-submit-hook", "[Request interrupted",
                      "This session is being continued from a previous conversation"):
            with self.subTest(start=start):
                self.assertIn(start, self.r["starts"])

    def test_replies_follow_the_turn(self):
        self.assertEqual(self.r["session"], [[1, True], [2, True], [3, False], [4, True], [5, True], [6, True],
                                             [7, False], [8, False]])
        self.assertEqual(self.r["first"], [True], "a reply with no prompt before it shows")
        self.assertEqual(self.r["sub"], [False], "a subagent's reply is its report to its lead")
        self.assertTrue(self.r["untouched"], "markMain copies, never marks the chat store itself")

    def test_owner_reply_after_a_wrapper_prompt_is_main(self):
        self.assertEqual(self.r["owned"], [[1, True], [2, False], [3, True], [4, False], [5, False]])

    def test_history_items_carry_main(self):
        self.assertEqual(self.r["hist"], [["act", False], ["prompt", True], ["ask", True], ["reply", True],
                                          ["act", False], ["prompt", False], ["reply", True], ["owner", True],
                                          ["reply", True], ["prompt", False], ["reply", False]])
        self.assertEqual(self.r["shown"], ["prompt:fix the login page", "ask:q?", "reply:fixed", "reply:worker done, checking", "owner:stop for now",
                                           "reply:stopped"])
        self.assertEqual(self.r["subHist"], [False])
        self.assertEqual(self.r["plain"], ["x", "z"], "no main field counts as main")


class TestToggleDrawn(unittest.TestCase):

    def test_setting_is_remembered(self):
        text = re.sub(r"/\*.*?\*/", "", page(), flags=re.S)
        self.assertRegex(text, r"let\s+histAll\s*=\s*readStoredBool\(\s*'agent-city\.histAll'\s*,\s*false\s*\)")
        src = function_source("setHistAll") or ""
        self.assertTrue("writeStoredBool(" in src and "'agent-city.histAll'" in src, "setHistAll saves it")

    def test_detail_has_the_toggle_and_filters(self):
        src = function_source("renderDetail") or ""
        for bit in ('class="hist-all"', 'id="hist-all"', "aria-pressed", "hist.all", "hist.hide", "hist.onlyMech",
                    "mainOnly(", "markMain(", "histAll"):
            with self.subTest(bit=bit):
                self.assertTrue(bit in src, "renderDetail: " + bit)

    def test_click_toggles(self):
        blk = listener_block(r"(?:\$\('#detail'\)|detail|detailEl)", "click") or ""
        self.assertTrue("hist-all" in blk and "setHistAll(" in blk, "#detail click: #hist-all -> setHistAll(!histAll)")

    def test_badge_counts_what_shows(self):
        self.assertTrue("mainOnly(" in (function_source("winEntryCount") or ""), "winEntryCount counts the shown list")

    def test_texts(self):
        for key in ("hist.all", "hist.hide", "hist.onlyMech"):
            with self.subTest(key=key):
                self.assertEqual(text_keys(key), 2, key + " in zh and en")


def decl_rail_tree(block):
    return re.sub(r"\s+", "", block or "")


def margin_left(block):
    """The left margin in px a declaration block sets (margin-left, else the margin shorthand); -1 when none."""
    m = re.search(r"margin-left:(-?\d+(?:\.\d+)?)px", block)
    if m:
        return float(m.group(1))
    m = re.search(r"margin:([^;]*)", block)
    if not m:
        return -1
    vals = [float(v[:-2]) if v.endswith("px") else 0.0 for v in m.group(1).replace(",", " ").split()]
    return {1: lambda v: v[0], 2: lambda v: v[1], 3: lambda v: v[1], 4: lambda v: v[3]}.get(len(vals), lambda v: -1)(vals)


TREE_SETUP = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
const OF = A.offices[0];
function buildLand(view){ officeState(view); }
const ag = (id, role, label, terr, up, lead, office) => Object.assign({ id, role, label, task: label, stuck: false,
  done: false, tools: {}, terr, lead: lead || '', office: office || null, relay: '' }, up === undefined ? {} : { up });
const AGENTS = [
  ag('s:T1', 'task-manager', 'rail <b> Task Manager', A.id, 'gov:' + A.id),          // a lead with NO office
  ag('s:T2', 'task-manager', 'est Task Manager', A.id, 'gov:' + A.id, '', { x: OF.x, z: OF.z }),
  ag('w11', 'worker', 'w11', A.id, 's:T1', 's:T1'),
  ag('w12', 'worker', 'w12', A.id, 's:T1'),                     // up says it, no lead
  ag('w21', 'worker', 'w21', A.id, 's:T2', 's:T2'),
  ag('w22', 'worker', 'w22', A.id, undefined, 's:T2'),          // an older server: no up, the lead says it
  ag('d1', 'fast-lane-deputy', 'd1', A.id, 'gov:' + A.id),      // the governor's deputy
  ag('s:H', 'task-manager', 'app Helper', A.id, ''),            // the owner opened it: right under the repo
  ag('x1', 'worker', 'x1', A.id, ''),                           // nobody knows its parent
  ag('x2', 'worker', 'x2', A.id, 's:GONE'),                     // its parent is not here
  ag('r1', 'worker', 'r1', A.id, 's:T1', 's:T1'),               // resting
  ag('s:T3', 'task-manager', 'b Task Manager', B.id, 'gov:' + B.id),   // B has no governor
  ag('y1', 'worker', 'y1', B.id, 's:T3', 's:T3'),
];
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'busy' }], agents: AGENTS });
byId('r1').state = 'resting';
apply({ type: 'spawn', id: 'n1', role: 'worker', label: 'n1', task: 'n1', terr: B.id, up: 's:T3', lead: 's:T3', from: 's:T3' });
const rowsOf = g => g.rows.map(r => [r.id, r.depth, !!r.rest, r.up, r.kids, !!r.lost]);
/* the nesting of the drawn tree: for every data-focus, how many <ul class="kids"> it sits in */
function nest(h){
  const out = {}, stack = [], re = /<ul class="([^"]*)"|<\/ul>|data-focus="([^"]*)"/g;
  let m;
  while ((m = re.exec(h))) {
    if (m[1] !== undefined) stack.push(m[1]);
    else if (m[0] === '</ul>') stack.pop();
    else out[m[2]] = stack.filter(k => k.split(' ').includes('kids')).length;
  }
  return out;
}
const ids = h => [...h.matchAll(/data-focus="([^"]*)"/g)].map(m => m[1]);
/* one row button's own markup, from <button ... data-focus="id" to its </button> */
const rowOf = (h, id) => { const i = h.indexOf('data-focus="' + id + '"'); if (i < 0) return ''; const s = h.lastIndexOf('<button', i); return h.slice(s, h.indexOf('</button>', i) + 9); };
"""


TREE_DRIVER = TREE_SETUP + r"""
const G = railGroups();
const none = new Set();
const h0 = railHtml(G, 'w21', none, none);
const h0b = railHtml(G, 'w21', none, none, undefined, new Set());
byId('w12').waiting = true;
const G1 = railGroups();
const h1 = railHtml(G1, null, none, none, undefined, new Set(['s:T1']));
const h2 = railHtml(G1, null, none, none, undefined, new Set(['gov:' + A.id]));
const h3 = railHtml(G1, null, none, new Set([A.id]), undefined, none);
const cnt = railCount(G1);
byId('w12').waiting = false;
const fresh = newCitizen('zz', 'worker', 't', A.id);
__out = { a: A.id, b: B.id, terrs: map.territories.map(t => t.id),
  groups: G.map(g => ({ terr: g.terr, rows: rowsOf(g) })),
  ups: { T1: byId('s:T1').up, w12: byId('w12').up, w22: byId('w22').up, n1: byId('n1').up,
         fresh: fresh.up },
  h0, h0b, h1, h2, h3, ids0: ids(h0), ids1: ids(h1), ids2: ids(h2), ids3: ids(h3), nest0: nest(h0), nest3: nest(h3),
  rowT1shut: rowOf(h1, 's:T1'), rowGovShut: rowOf(h2, 'gov:' + A.id), rowT1open: rowOf(h0, 's:T1'),
  rowX1: rowOf(h0, 'x1'), rowX2: rowOf(h0, 'x2'), rowH: rowOf(h0, 's:H'), rowW11: rowOf(h0, 'w11'), rowD1: rowOf(h0, 'd1'),
  cnt, lost: i18n('rail.lost'), fold: i18n('rail.fold'), unfold: i18n('rail.unfold') };
"""


PAYLOAD = None


def payload_rail_tree():
    global PAYLOAD
    if PAYLOAD is None:
        PAYLOAD = {"view": two_territory_view(), "ta": PA, "tb": PB}
    return PAYLOAD


REQ = ("apply", "officeState", "railGroups", "railHtml", "railCount", "byId", "newCitizen", "i18n", "citizens")


class TestPageKeepsUpP1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(TREE_DRIVER, payload_rail_tree(), REQ)

    def test_snapshot_and_spawn_keep_up(self):
        u = self.r["ups"]
        self.assertEqual(u["T1"], "gov:" + self.r["a"], "placeAgent keeps a.up")
        self.assertEqual(u["w12"], "s:T1")
        self.assertEqual(u["w22"], "", "no up from the server: ''")
        self.assertEqual(u["n1"], "s:T3", "a live spawn keeps ev.up")
        self.assertEqual(u["fresh"], "", "newCitizen starts with up ''")

    def test_demo_spawn_carries_up(self):
        src = function_source("spawnDemo") or ""
        self.assertRegex(src, r"\bup\s*:", "spawnDemo's spawn event carries up")


class TestWiringP4(unittest.TestCase):

    def test_shut_is_remembered(self):
        p = page()
        self.assertRegex(p, r"let railShut\s*=\s*new Set\(")
        self.assertIn("agent-city.railShut", p)
        src = function_source("saveRailShut") or ""
        self.assertIn("localStorage.setItem", src)
        self.assertIn("try", src)
        i = p.index("let railShut")
        near = p[i:i + 600]
        self.assertIn("localStorage.getItem('agent-city.railShut')", near)
        self.assertIn("try", near)

    def test_render_passes_it(self):
        self.assertRegex(function_source("renderRail") or "", r"railHtml\([^;]*\brailShut\)")

    def test_arrow_click(self):
        block = listener_block(r"\$\('#rail-list'\)", "click") or ""
        self.assertRegex(block, r"data-tw|dataset\.tw")
        self.assertIn("railShut", block)
        self.assertIn("saveRailShut()", block)
        self.assertIn("renderRail()", block)
        tw = block.find("tw"), block.find("data-focus")
        self.assertTrue(0 <= tw[0] < tw[1], "the arrow is handled before a row's data-focus")

    def test_words(self):
        for key in ("rail.lost", "rail.fold", "rail.unfold"):
            self.assertEqual(text_keys(key), 2, key + ": zh and en")
        p = page()
        self.assertIn("'rail.lost': '上级不明'", p)
        self.assertIn("'rail.fold': '收起'", p)
        self.assertIn("'rail.unfold': '展开'", p)


class TestCssP5(unittest.TestCase):

    def test_wider_rail(self):
        m = re.search(r"--rail-w\s*:\s*(\d+)px", css())
        self.assertIsNotNone(m)
        self.assertTrue(290 <= int(m.group(1)) <= 310, "about 300px (owner pick B): " + m.group(1))

    def test_phone_drawer(self):
        self.assertIn("width:min(300px,84%)", decl_rail_tree(rule(".rail", media_960())))

    def test_names_wrap_to_two_lines(self):
        b = decl_rail_tree(rule(".rrow b"))
        for bit in ("display:-webkit-box", "-webkit-line-clamp:2", "-webkit-box-orient:vertical", "overflow:hidden"):
            self.assertIn(bit, b, bit)
        self.assertNotIn("white-space:nowrap", b)
        self.assertNotIn("text-overflow:ellipsis;white-space:nowrap", b)

    def test_indent_and_guide_line(self):
        c = css()
        # every block whose selector ends with the .kids list itself (".kids", "ul.kids", ".tree .kids", ...)
        kids = ";".join(decl_rail_tree(b) for s, b in re.findall(r"([^{}]*)\{([^{}]*)\}", c)
                        if any(re.search(r"\.kids$", x.strip()) for x in s.split(",")))
        self.assertIn("list-style:none", kids)
        self.assertTrue(4 <= margin_left(kids) <= 16, "indent per level: " + kids)
        before = [b for s, b in re.findall(r"([^{}]*)\{([^{}]*)\}", c) if ".kids" in s and "::before" in s]
        after = [b for s, b in re.findall(r"([^{}]*)\{([^{}]*)\}", c) if ".kids" in s and "::after" in s]
        self.assertTrue(any("border-top" in b for b in before), "the elbow into each child")
        self.assertTrue(any("border-left" in b for b in after), "the line down from the parent")

    def test_arrow(self):
        self.assertRegex(decl_rail_tree(rule(".tw")), r"width:\d+px")
        turned = decl_rail_tree(rule('.tw[aria-expanded="false"]'))
        self.assertRegex(turned, r"rotate|transform")
        self.assertIn("visibility:hidden", decl_rail_tree(rule(".tw.leaf")))

    def test_tags_and_no_old_indent(self):
        self.assertTrue(rule(".more"), ".more")
        self.assertTrue(rule(".who"), ".who")
        self.assertNotIn("padding-left", decl_rail_tree(rule(".rrow.sub")), "the indent comes from the nesting now")


PAGE_DRIVER = r"""
citizens.length = 0;
const mk = (id, label, task, extra) => Object.assign({ id, label, task, gone: false }, extra || {});
citizens.push(mk('s:aaaa1111', 'session', 'v4-plus'), mk('s:bbbb2222', 'session', 'v4-plus'),
              mk('s:cccc3333', 'plus-manager', 'v4-plus'), mk('w9', 'worker', 'Slice A'));
const twins = [nameOf(citizens[0]), nameOf(citizens[1]), nameOf(citizens[2]), nameOf(citizens[3])];
apply({ type: 'label', id: 's:bbbb2222', label: 'consignment' });
const renamed = [nameOf(citizens[0]), nameOf(citizens[1]), citizens[1].label];
apply({ type: 'label', id: 'nobody', label: 'x' });
citizens.push(mk('s:dddd4444', 'plus-manager', 'v4-plus', { gone: true }));
const goneIgnored = nameOf(citizens[2]);
__out = { twins, renamed, goneIgnored };
"""


class TestPageShowsTheName(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = run_sim(PAGE_DRIVER, {}, REQUIRED + ("nameOf",))

    def test_same_names_get_a_short_tell_apart_tag(self):
        self.assertEqual(self.out["twins"], ["session · v4-plus #1111", "session · v4-plus #2222",
                                             "plus-manager · v4-plus", "worker · Slice A"])

    def test_a_label_event_renames_and_the_tag_goes(self):
        self.assertEqual(self.out["renamed"], ["session · v4-plus", "consignment · v4-plus",
                                               "consignment"])

    def test_gone_people_do_not_count(self):
        self.assertEqual(self.out["goneIgnored"], "plus-manager · v4-plus")


GOV_JS_status = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const here = new Set(['a', 'b', 'c', 'd', 'e']);
const box = { Math, JSON, console, simT: 0, govTerr: 'a', govsByTerr: new Map(),
  governorAt: terr => (here.has(terr) ? { x: 0, y: 0 } : null),
  byId: () => null, nameOf: () => '', citizenStatus: () => ['walk', ''],
  esc: s => String(s) };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
for (const [terr, state] of [['a', 'background'], ['b', 'waiting'], ['c', 'idle'], ['d', 'busy'], ['e', 'unknown']])
  box.govsByTerr.set(terr, { state });
const out = { status: {}, text: {}, talk: {} };
for (const terr of ['a', 'b', 'c', 'd', 'e', 'gone']) {
  out.status[terr] = box.govRowStatus(terr);
  out.text[terr] = box.govRowText(terr);
  out.talk[terr] = box.govTalk(terr);
}
out.row = box.railRowHtml({ id: 'gov:a', depth: 0, rest: false }, { selId: null, color: '#fff' });
out.rowWaiting = box.railRowHtml({ id: 'gov:b', depth: 0, rest: false }, { selId: null, color: '#fff' });
require(`fs`).writeSync(1, JSON.stringify(out));
"""


CITIZEN_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, governorAt: () => ({ x: 0, y: 0 }) };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const base = { state: 'working', askKind: '', askPhase: '', relay: '' };
const s = extra => box.citizenStatus(Object.assign({}, base, extra));
require(`fs`).writeSync(1, JSON.stringify({
  waiting: s({ waiting: true }), bgrun: s({ bgrun: true }), idle: s({ idle: true }), plain: s({}),
  idleAsk: s({ idle: true, askKind: 'permission' }),
  bgrunAsk: s({ bgrun: true, askKind: 'question', askPhase: 'owner' }),
}));
"""


SIM_DRIVER = r"""
const V = __payload.view, T = V.territories[0], tid = T.id;
function buildLand(view){ officeState(view); }
const agent = (id, extra) => Object.assign({ id, role: 'task-manager', label: 'task-manager', task: id,
  stuck: false, done: false, waiting: false, status: '', tools: {}, terr: tid }, extra);
apply({ type: 'snapshot', world: V, gov: { state: 'background', terr: tid }, govs: [{ terr: tid, state: 'background' }],
  governors: 1, asks: [], shows: [], agents: [agent('s:a'), agent('s:b', { status: 'background' }),
    agent('s:c', { status: 'idle' }), agent('s:d', { status: 'waiting', waiting: true })] });
const st = id => citizenStatus(byId(id), 1);
const out = { snap: [st('s:a'), st('s:b'), st('s:c'), st('s:d')], govSnap: [govRowStatus(tid), govTalk(tid)] };
const a = byId('s:a'), at = [a.x, a.y];
const step = type => { apply({ type, id: 's:a' }); return st('s:a'); };
out.steps = ['background', 'idle', 'waiting', 'resume', 'idle', 'background', 'resume'].map(step);
out.moved = Math.hypot(a.x - at[0], a.y - at[1]) + (a.path ? a.path.length : 0);
apply({ type: 'gov', terr: tid, state: 'waiting', present: true });
out.govWaiting = [govRowStatus(tid), govTalk(tid)];
apply({ type: 'gov', terr: tid, state: 'background', present: true });
out.govBg = [govRowStatus(tid), govTalk(tid)];
__out = out;
"""


SIM_REQUIRED_status = ("officeState", "governorAt", "apply", "citizens", "byId", "citizenStatus", "govRowStatus", "govTalk")


def sim_results():
    if "sim" not in _CACHE:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from cityoffice import office_view_of
        _CACHE["sim"] = run_sim(SIM_DRIVER, {"view": office_view_of(("/work/status/app/.git", "app"))}, SIM_REQUIRED_status)
    return _CACHE["sim"]


def gov_results():
    # test-slim: its own key; "gov" is the governor-bubbles result of another class
    if "gov_status" not in _CACHE:
        _CACHE["gov_status"] = tp.run_node(GOV_JS_status, {
            "prelude": tp.constants_prelude(),
            "fns": need("govRowStatus", "govRowText", "govSay", "govTalk", "railRowHtml")})
    return _CACHE["gov_status"]


class TestPageGovernor(unittest.TestCase):
    def test_background_has_its_own_class(self):
        self.assertEqual(gov_results()["status"]["a"], ["bgrun", "后台在跑"])

    def test_other_states_as_before(self):
        r = gov_results()["status"]
        self.assertEqual([r["b"], r["c"], r["d"], r["e"], r["gone"]],
                         [["gov", "等你"], ["gov", "空闲"], ["gov", "在忙"], ["gov", "未知"], ["gov", "不在"]])

    def test_row_text_is_the_status_text(self):
        r = gov_results()
        for terr, pair in r["status"].items():
            with self.subTest(terr=terr):
                self.assertEqual(r["text"][terr], pair[1])

    def test_bubble_only_when_waiting(self):
        r = gov_results()["talk"]
        self.assertEqual(r["b"], "等你回话…")
        for terr in ("a", "c", "d", "e", "gone"):
            with self.subTest(terr=terr):
                self.assertEqual(r[terr], "")

    def test_rail_row(self):
        r = gov_results()
        self.assertIn('class="sdot st-bgrun"', r["row"])
        self.assertIn('class="chip bgrun">后台在跑<', r["row"])
        self.assertIn('class="sdot st-gov"', r["rowWaiting"])
        self.assertIn('class="chip gov">等你<', r["rowWaiting"])

    def test_panel_pill_uses_it_too(self):
        script = tp.inline_script()
        self.assertNotIn('<span class="pill gov">${govRowText(', script)
        self.assertGreaterEqual(len(re.findall(r"govRowStatus\(", script)), 3,
                                "govRowStatus(): its definition, the rail row and the governor panel")


class TestPageCitizen(unittest.TestCase):
    def results(self):
        if "citizen" not in _CACHE:
            prelude = tp.constants_prelude() + "\n" + "var STATE = " + tp.const_object("STATE") + ";"
            _CACHE["citizen"] = tp.run_node(CITIZEN_JS, {"prelude": prelude, "fns": need("citizenStatus")})
        return _CACHE["citizen"]

    def test_status(self):
        r = self.results()
        self.assertEqual(r["waiting"], ["you", "等你回话"])
        self.assertEqual(r["bgrun"], ["bgrun", "后台在跑"])
        self.assertEqual(r["idle"], ["walk", "空闲"])
        self.assertNotIn(r["plain"][1], ("等你回话", "后台在跑", "空闲"))

    def test_an_open_ask_wins(self):
        r = self.results()
        self.assertEqual(r["idleAsk"], ["you", "等你批"])
        self.assertEqual(r["bgrunAsk"], ["you", "等你回答"])

    def test_events_move_a_person_between_states(self):
        r = sim_results()
        plain = r["snap"][0]
        self.assertNotIn(plain[1], ("等你回话", "后台在跑", "空闲"))
        self.assertEqual(r["steps"], [["bgrun", "后台在跑"], ["walk", "空闲"], ["you", "等你回话"], plain,
                                      ["walk", "空闲"], ["bgrun", "后台在跑"], plain])
        self.assertEqual(r["moved"], 0, "a status event never sends the person anywhere")

    def test_snapshot_places_the_same_way(self):
        r = sim_results()
        self.assertEqual(r["snap"][1:], [["bgrun", "后台在跑"], ["walk", "空闲"], ["you", "等你回话"]])

    def test_governor_events_and_snapshot(self):
        r = sim_results()
        self.assertEqual(r["govSnap"], [["bgrun", "后台在跑"], ""])
        self.assertEqual(r["govWaiting"], [["gov", "等你"], "等你回话…"])
        self.assertEqual(r["govBg"], [["bgrun", "后台在跑"], ""])


STEP_KEYS = {
    "step.edit": ("改 {file}", "Editing {file}"), "step.write": ("写 {file}", "Writing {file}"),
    "step.editAny": ("改代码", "Editing code"), "step.writeAny": ("写代码", "Writing code"),
    "step.read": ("看文件", "Reading files"), "step.search": ("找代码", "Searching code"),
    "step.web": ("查资料", "Looking things up"), "step.bash": ("跑命令", "Running a command"),
    "step.send": ("派出：{desc}", "Sending out: {desc}"), "step.sendAny": ("派出帮手", "Sending a helper"),
    "step.plan": ("排计划", "Planning"), "step.message": ("发消息", "Sending a message"),
    "step.other": ("忙着", "Busy"),
}


LONG_FILE = "a_really_long_file_name_for_tests.py"


LONG_DESC = "一二三四五六七八九十一二三四五六七八九十一二"


LONG_TASK = "一个非常长的任务名字超过十四个字"


STEP_CASES = [
    ({"tool": "Edit", "name": "Edit", "file": "checkout.py"}, "改 checkout.py"),
    ({"tool": "Edit", "name": "MultiEdit", "file": "a.py"}, "改 a.py"),
    ({"tool": "Edit", "name": "NotebookEdit", "file": "nb.ipynb"}, "改 nb.ipynb"),
    ({"tool": "Write", "name": "Write", "file": "README.md"}, "写 README.md"),
    ({"tool": "Edit", "name": "Edit", "file": "src/pay/checkout.py"}, "改 checkout.py"),
    ({"tool": "Edit", "name": "Edit", "file": LONG_FILE}, "改 " + LONG_FILE[:23] + "…"),
    ({"tool": "Edit", "name": "Edit"}, "改代码"),
    ({"tool": "Write", "name": "Write"}, "写代码"),
    ({"tool": "Read", "name": "Read"}, "看文件"),
    ({"tool": "Read", "name": "Grep"}, "找代码"),
    ({"tool": "Read", "name": "Glob"}, "找代码"),
    ({"tool": "Read", "name": "LS"}, "找代码"),
    ({"tool": "Read", "name": "WebFetch"}, "查资料"),
    ({"tool": "Read", "name": "WebSearch"}, "查资料"),
    ({"tool": "Bash", "name": "Bash"}, "跑命令"),
    ({"tool": "Other", "name": "Agent", "desc": "设置页表单"}, "派出：设置页表单"),
    ({"tool": "Other", "name": "Task", "desc": LONG_DESC}, "派出：" + LONG_DESC[:19] + "…"),
    ({"tool": "Other", "name": "Agent"}, "派出帮手"),
    ({"tool": "Other", "name": "TodoWrite"}, "排计划"),
    ({"tool": "Other", "name": "SendMessage"}, "发消息"),
    ({"tool": "Other", "name": "mcp__github__create_pull_request"}, "忙着"),
    ({"tool": "Edit"}, "改代码"),
    ({"tool": "Write"}, "写代码"),
    ({"tool": "Read"}, "看文件"),
    ({"tool": "Bash"}, "跑命令"),
    ({"tool": "Other"}, "忙着"),
]


STEPS_DRIVER = r"""
const V = __payload.view, T = V.territories[0], tid = T.id;
function buildLand(view){ officeState(view); }
function tick(sec){ for (let i = 0; i < Math.round(sec * 10); i++) update(.1); }
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: tid }, govs: [{ terr: tid, state: 'busy' }],
  governors: 1, asks: [], shows: [], agents: [] });
const out = {};
out.steps = __payload.cases.map(ev => stepText(Object.assign({ type: 'tool', id: 'x' }, ev)));
out.en = Object.fromEntries(__payload.keys.map(k => [k, (TEXT.en || {})[k]]));
out.zh = Object.fromEntries(__payload.keys.map(k => [k, (TEXT.zh || {})[k]]));

// a live worker: the head line while it acts, nothing in the pause
apply({ type: 'spawn', id: 'w1', role: 'worker', label: 'worker', task: '写结账测试', terr: tid });
tick(20);
const w1 = byId('w1');
out.before = doingText(w1);
apply({ type: 'tool', id: 'w1', tool: 'Edit', name: 'Edit', file: 'checkout.py' });
out.step = w1.step;
out.doing = doingText(w1);
tick(7);
out.paused = doingText(w1);
apply({ type: 'tool', id: 'w1', tool: 'Bash', name: 'Bash' });
out.doingBash = doingText(w1);

// a long task is cut; a task that is just the label is left out
apply({ type: 'spawn', id: 'w2', role: 'worker', label: 'worker', task: __payload.longTask, terr: tid });
apply({ type: 'spawn', id: 'w3', role: 'worker', label: 'worker', task: 'worker', terr: tid });
tick(20);
apply({ type: 'tool', id: 'w2', tool: 'Read', name: 'Read' });
apply({ type: 'tool', id: 'w3', tool: 'Read', name: 'Grep' });
out.longTask = doingText(byId('w2'));
out.labelTask = doingText(byId('w3'));

// the history line: plain-words steps, the last 3 distinct, never a tool name or a count
const h = byId('w3');
h.acts = [];
for (const ev of [{ tool: 'Edit', name: 'Edit', file: 'a.py' }, { tool: 'Edit', name: 'Edit', file: 'a.py' },
                  { tool: 'Read', name: 'Read' }, { tool: 'Bash', name: 'Bash' }, { tool: 'Read', name: 'Grep' }])
  apply(Object.assign({ type: 'tool', id: 'w3' }, ev));
out.hist = h.acts.map(a => a.text);

__out = out;
"""


STEPS_REQUIRED = REQUIRED + ("stepText", "doingText", "workAction", "TEXT")


class TestPlainWordsOnThePage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        plan, view = sorted(plan_views().items())[0]
        cls.r = run_sim(STEPS_DRIVER, {"view": view, "cases": [c for c, _ in STEP_CASES], "keys": list(STEP_KEYS),
                                       "longTask": LONG_TASK}, STEPS_REQUIRED)

    def test_every_tool_in_plain_words(self):
        for (ev, want), got in zip(STEP_CASES, self.r["steps"]):
            with self.subTest(ev=ev):
                self.assertEqual(got, want)

    def test_words_in_both_languages(self):
        for key, (zh, en) in STEP_KEYS.items():
            with self.subTest(key=key):
                self.assertEqual(self.r["zh"][key], zh)
                self.assertEqual(self.r["en"][key], en)
                self.assertEqual(text_keys(key), 2)

    def test_head_says_task_and_step_while_it_works(self):
        self.assertEqual(self.r["before"], "", "no tool event yet: nothing over the head")
        self.assertEqual(self.r["step"], "改 checkout.py")
        self.assertEqual(self.r["doing"], "写结账测试 · 改 checkout.py")
        self.assertEqual(self.r["paused"], "", "the short pause: nothing over the head")
        self.assertEqual(self.r["doingBash"], "写结账测试 · 跑命令")

    def test_long_task_is_cut_and_a_label_task_is_left_out(self):
        self.assertEqual(self.r["longTask"], LONG_TASK[:13] + "… · 看文件")
        self.assertEqual(self.r["labelTask"], "找代码")

    def test_history_says_steps_not_tool_counts(self):
        self.assertEqual(self.r["hist"], ["看文件 · 跑命令 · 找代码"],
                         "one line for tools in a row, its last 3 plain-words steps")
        for line in self.r["hist"]:
            with self.subTest(line=line):
                self.assertNotRegex(line, r"×|\bx\d|Edit|Read|Bash|Write|Grep")


class TestHeadLine3D(unittest.TestCase):
    def test_update_person_pins_the_doing_line(self):
        up = function_source("updatePerson") or ""
        self.assertIn("doingText(", up)
        self.assertRegex(page(), r"\.doing\{", "a .doing CSS rule")

    def test_panel_pill_follows_the_work(self):
        rd = function_source("renderDetail") or ""
        tail = rd[rd.index("lastChatTo = chatTo;"):] if "lastChatTo = chatTo;" in rd else ""
        # cloud-polish Q3 (2026-10-02): the per-call refresh is refreshHeadPill(el, selected), for a governor too
        self.assertIn("refreshHeadPill(", tail, "after the rebuild part, every call refreshes the pill")
        self.assertIn(".p-head .pill", function_source("refreshHeadPill") or "")
        self.assertIn("citizenStatus(", function_source("headPill") or "")


MIN_GAP, WALK_GAP, TALK_NEAR, HANDOVER_SEC, TALK_SEC, TRIP = .45, .3, 1.2, 2.6, 2.0, 4.0


ACROSS_DESK = 2.4   # city-office: the area manager sits at his desk; who talks to him stands across it (MGR_VISIT)


EPS = 1e-6


TALK_REQUIRED = REQUIRED + ("talkOf", "govTalkOf", "HANDOVER_SEC", "TALK_SEC", "MIN_GAP", "angleDiff", "hallStand",
                            "findPath", "freeAt", "waitStand", "goTo", "leave", "govMove", "simT")


PRELUDE = r"""
function buildLand(view){ officeState(view); }
{   // the driver lives in its own block: a new name in the page never clashes with a name here
let seed = 20261001; Math.random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;   // same scene every run
const V = __payload.view; officeState(V); const T = map.territories[0], tid = T.id, GOV = 'gov:' + tid;
const AG = (id, role, extra) => Object.assign({ id, role, label: role, task: 't-' + id, stuck: false, done: false, tools: {},
  terr: tid, lead: '', office: null, relay: '' }, extra || {});
const CAST = () => [AG('s:L', 'task-manager'),
  AG('w1', 'worker', { lead: 's:L' }), AG('w2', 'worker', { lead: 's:L' }), AG('w3', 'worker', { lead: 's:L' }),
  AG('s:H', 'task-manager'), AG('d1', 'fast-lane-deputy')];
const g = () => governorAt(tid);
const P = id => id === GOV ? g() : byId(id);
const D = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const faces = (a, b) => Math.abs(angleDiff(a.yaw, Math.atan2(b.x - a.x, b.y - a.y))) < .3;
const walking = c => !!(c && c.path && c.path.length);
const govWalking = () => { const m = govMove.get(tid); return !!(m && m.path && m.path.length); };
const tk = id => { const t = id === GOV ? govTalkOf(tid) : (byId(id) ? talkOf(byId(id)) : null);
  return t ? { kind: t.kind, with: t.with, speaking: !!t.speaking, icon: t.icon || '' } : null; };
const at = id => { const p = P(id); return p ? { x: p.x, y: p.y } : null; };
const st = c => citizenStatus(c, 1);
const r3 = v => +(+v).toFixed(3);
const stackBad = [];
// T2: standing people (and the governor) are never closer than MIN_GAP, at every tick of every scene
function checkGaps(label){
  // city-office: subagents are never drawn (Office, Who is shown), so only the people you see can stack
  const ps = citizens.filter(c => !c.gone && !isSub(c) && c.state !== 'resting' && c.state !== 'leaving' && !c.inLift)
    .map(c => ({ id: c.id, x: c.x, y: c.y, walk: walking(c) }));
  const gv = g(); if (gv) ps.push({ id: GOV, x: gv.x, y: gv.y, walk: govWalking() });
  for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) {
    if (ps[i].walk || ps[j].walk) continue;
    const d = D(ps[i], ps[j]);
    if (d < MIN_GAP - 1e-6 && stackBad.length < 12) stackBad.push([label, ps[i].id, ps[j].id, r3(d)]);
  }
}
function tick(sec, label, each){
  for (let i = 0; i < Math.round(sec * 10); i++) {
    for (const c of citizens) c.toolAt = simT;              // nobody takes an idle stroll in these scenes
    const m = govMove.get(tid); if (m) m.idleSince = simT;  // the governor neither
    update(.1); checkGaps(label || ''); if (each) each();
  }
}
function until(cond, max, label, each){ let t = 0; while (!cond() && t < max) { tick(.1, label, each); t += .1; } return +t.toFixed(1); }
function start(){
  apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: tid }, govs: [{ terr: tid, state: 'busy' }], governors: 1,
    asks: [], shows: [], agents: CAST() });
  tick(1, 'start');
}
// the point at fraction f of the way `from` -> path (a list of [x, y])
function along(path, from, f){
  const pts = [[from.x, from.y]].concat(path), seg = []; let len = 0;
  for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(d); len += d; }
  let t = len * f;
  for (let i = 0; i < seg.length; i++) {
    if (t <= seg[i]) { const k = seg[i] ? t / seg[i] : 0; return { x: pts[i][0] + (pts[i + 1][0] - pts[i][0]) * k, y: pts[i][1] + (pts[i + 1][1] - pts[i][1]) * k }; }
    t -= seg[i];
  }
  const e = pts[pts.length - 1]; return { x: e[0], y: e[1] };
}
function put(c, p){ c.x = p.x; c.y = p.y; c.home = { x: p.x, y: p.y }; c.stand = c.home; c.path = []; c.state = 'working'; }
// two points 3 to 4 apart with open ground between and around them, away from everybody: [A, B] or null
function openWay(){
  const ring = p => [0, 1, 2, 3, 4, 5, 6, 7].every(i => freeAt(p.x + Math.cos(i * Math.PI / 4) * .6, p.y + Math.sin(i * Math.PI / 4) * .6));
  const clear = p => freeAt(p.x, p.y) && ring(p) && citizens.every(c => D(c, p) > 1.1) && D(g(), p) > 1.1;
  for (let r = 0; r < V.h; r++) for (let c = 0; c < V.w; c++) {
    const A = { x: V.x0 + c + .5, y: V.z0 + r + .5 };
    if (Math.hypot(A.x - T.cx, A.y - T.cz) > 9 || !clear(A)) continue;
    for (const [dx, dy] of [[4, 0], [0, 4], [3, 0], [0, 3], [2.5, 2.5], [2.5, -2.5]]) {
      const B = { x: A.x + dx, y: A.y + dy }; let ok = true;
      for (let k = 0; k <= 16 && ok; k++) ok = clear({ x: A.x + dx * k / 16, y: A.y + dy * k / 16 });
      if (ok && findPath(A.x, A.y, B.x, B.y)) return [A, B];
    }
  }
  return null;
}
const out = {};
"""


SCENES = {}


# T1: one worker from its lead, a deputy and a task manager from the governor, a helper's own subagent, 5 at once
SCENES["spawn"] = r"""
start();
const L = byId('s:L'), H = byId('s:H');
out.snapTalk = ['s:L', 'w1', 's:H', GOV].map(tk);
const L0 = at('s:L');
apply({ type: 'spawn', id: 'w9', role: 'worker', label: 'worker', task: 'page', terr: tid, lead: 's:L', office: null, from: 's:L' });
const n = byId('w9'), n0 = at('w9');
out.one = { state0: n.state, d0: D(n, L), talkNew0: tk('w9'), talkLead0: tk('s:L') };
tick(.8, 'handover');
out.one.face = [faces(n, L), faces(L, n)];
tick(HANDOVER_SEC * .8 - .8, 'handover');
out.one.reply = [tk('w9'), tk('s:L')]; out.one.stateMid = n.state; out.one.movedMid = D(n, n0); out.one.leadMoved = D(L, L0);
tick(HANDOVER_SEC * .2 + .4, 'handover-end');
out.one.after = { state: n.state, talks: [tk('w9'), tk('s:L')] };
out.one.t = until(() => n.state === 'working' && !walking(n), 30, 'to-spot');
out.one.end = { state: n.state, home: D(n, n.home) };

const G0 = at(GOV);
apply({ type: 'spawn', id: 'd9', role: 'fast-lane-deputy', label: 'fast-lane-deputy', task: 'msg-sides Deputy', terr: tid, lead: '', office: null, from: GOV });
const d9 = byId('d9');
out.gov = { state0: d9.state, d0: D(d9, g()), talkGov0: tk(GOV), talkNew0: tk('d9') };
tick(.8, 'gov-handover');
out.gov.face = [faces(d9, g()), faces(g(), d9)]; out.gov.govMoved = D(g(), G0);
tick(HANDOVER_SEC, 'gov-handover-end');
out.gov.after = { state: d9.state, talkGov: tk(GOV) };

apply({ type: 'spawn', id: 's:N', role: 'task-manager', label: 'city-rail Task Manager', task: 'app', terr: tid, lead: '', office: null, from: GOV });
out.tm = { state0: byId('s:N').state, d0: D(byId('s:N'), g()), talkGov0: tk(GOV) };
apply({ type: 'spawn', id: 'h1', role: 'other', label: 'Explore', task: 'survey', terr: tid, lead: '', office: null, from: 's:H' });
out.sub = { state0: byId('h1').state, d0: D(byId('h1'), H), talkH0: tk('s:H') };
tick(HANDOVER_SEC + .6, 'two-handovers');
out.tm.after = byId('s:N').state; out.sub.after = byId('h1').state;
until(() => citizens.every(c => !walking(c)), 30, 'settle');

const five = ['k1', 'k2', 'k3', 'k4', 'k5'];
for (const id of five) apply({ type: 'spawn', id, role: 'worker', label: 'worker', task: id, terr: tid, lead: 's:L', office: null, from: 's:L' });
let minPair = 9;
for (let i = 0; i < 5; i++) for (let j = i + 1; j < 5; j++) minPair = Math.min(minPair, D(byId(five[i]), byId(five[j])));
out.five = { states0: five.map(id => byId(id).state), d0: five.map(id => r3(D(byId(id), L))), minPair0: minPair, talkLead0: tk('s:L') };
tick(HANDOVER_SEC * .8, 'five');
out.five.talkLeadLate = tk('s:L'); out.five.statesMid = five.map(id => byId(id).state);
tick(HANDOVER_SEC * .2 + .5, 'five-end');
out.five.after = { states: five.map(id => byId(id).state), talkLead: tk('s:L') };
out.five.t = until(() => five.every(id => byId(id).state === 'working' && !walking(byId(id))), 45, 'five-walk');
out.five.end = five.map(id => byId(id).state);
out.stackBad = stackBad;
__out = out;
}
"""


# T1 + T2: nobody sent it -> as before, but never on the governor or on each other
SCENES["nosender"] = r"""
start();
apply({ type: 'spawn', id: 'p1', role: 'worker', label: 'worker', task: 'a', terr: tid });
apply({ type: 'spawn', id: 'p2', role: 'worker', label: 'worker', task: 'b', terr: tid, from: '' });
apply({ type: 'spawn', id: 'p3', role: 'worker', label: 'worker', task: 'c', terr: tid, from: 'nobody' });
const ids = ['p1', 'p2', 'p3'], ps = ids.map(byId);
let minPair = 9;
for (let i = 0; i < 3; i++) for (let j = i + 1; j < 3; j++) minPair = Math.min(minPair, D(ps[i], ps[j]));
out.states = ps.map(c => c.state); out.talks = ids.map(tk); out.dGov = ps.map(c => r3(D(c, g()))); out.minPair = minPair;
out.govTalk = tk(GOV);
tick(.5, 'spawned');
until(() => ps.every(c => c.state === 'working' && !walking(c)), 40, 'walk');
out.end = ps.map(c => c.state);
apply({ type: 'gov', terr: tid, state: 'idle', present: false });
apply({ type: 'spawn', id: 'p4', role: 'worker', label: 'worker', task: 'd', terr: tid, from: GOV });
out.noGov = { state: byId('p4').state, talk: tk('p4') };
tick(1, 'no-gov');
out.stackBad = stackBad;
__out = out;
}
"""


# T3: a message, far apart -> the sender walks over, they talk, it walks back; close by; not recognised
SCENES["talk"] = r"""
start();
const L = byId('s:L'), H = byId('s:H');
out.far0 = D(H, L);
const H0 = at('s:H'), L0 = at('s:L'), sH = st(H), sL = st(L);
apply({ type: 'talk', from: 's:H', to: 's:L', terr: tid });
out.go = { state: H.state, walking: walking(H), talks: [tk('s:H'), tk('s:L')], status: [st(H), st(L)], before: [sH, sL] };
out.trip = until(() => !walking(H) && H.state === 'talking', 14, 'walk-over');
out.arrive = { state: H.state, d: D(H, L), talks: [tk('s:H'), tk('s:L')], status: [st(H), st(L)], leadMoved: D(L, L0) };
tick(.8, 'talk'); out.face = [faces(H, L), faces(L, H)];
tick(TALK_SEC * .8 - .8, 'talk'); out.reply = [tk('s:H'), tk('s:L')];
tick(TALK_SEC * .2 + .4, 'talk-end');
out.after = { state: H.state, walking: walking(H), talks: [tk('s:H'), tk('s:L')], leadState: L.state, leadMoved: D(L, L0) };
out.backT = until(() => !walking(H) && (H.state === 'working' || H.state === 'building'), 30, 'walk-back');
out.end = { state: H.state, home: D(H, H0) };

const w1 = byId('w1');
put(w1, waitStand({ x: L.x, y: L.y }, citizens.filter(c => c !== w1 && c !== L).map(c => ({ x: c.x, y: c.y }))));
tick(.5, 'near-settle');
const w0 = at('w1');
apply({ type: 'talk', from: 'w1', to: 's:L', terr: tid });
out.near = { d: D(w1, L), walking: walking(w1), talks: [tk('w1'), tk('s:L')] };
tick(.8, 'near'); out.near.face = [faces(w1, L), faces(L, w1)]; out.near.moved = D(w1, w0);
tick(TALK_SEC + .5, 'near-end');
out.near.after = { talks: [tk('w1'), tk('s:L')], moved: D(w1, w0) };
tick(1, 'near-after'); out.near.after.state = w1.state;

const d1 = byId('d1'), d0 = at('d1'), ds = d1.state;
apply({ type: 'talk', from: 'd1', to: '', terr: tid });
out.lost = { talk: tk('d1'), walking: walking(d1), state: d1.state, state0: ds };
tick(TALK_SEC * .5, 'lost'); out.lost.mid = tk('d1'); out.lost.moved = D(d1, d0);
tick(TALK_SEC * .5 + .4, 'lost'); out.lost.after = tk('d1');
apply({ type: 'talk', from: 'd1', to: 'nobody', terr: tid });
out.lost2 = { talk: tk('d1'), walking: walking(d1) };
tick(TALK_SEC + .4, 'lost2');
apply({ type: 'talk', from: 'nobody', to: 's:L', terr: tid });
tick(.3, 'no-sender'); out.noSender = [tk('s:L'), citizens.filter(c => walking(c)).length];
out.stackBad = stackBad;
__out = out;
}
"""


# T3: the governor as the other one, and as the sender; anyone who needs him calls him back
SCENES["gov"] = r"""
start();
const L = byId('s:L'), H = byId('s:H'), hs = hallStand(T);
const H0 = at('s:H');
apply({ type: 'talk', from: 's:H', to: GOV, terr: tid });
out.toGov = { state: H.state };
out.toGov.trip = until(() => !walking(H) && H.state === 'talking', 14, 'to-gov');
out.toGov.arrive = { d: D(H, g()), talks: [tk('s:H'), tk(GOV)], govAtHall: D(g(), hs) };
tick(.8, 'to-gov'); out.toGov.face = [faces(H, g()), faces(g(), H)];
tick(TALK_SEC + .3, 'to-gov'); out.toGov.after = [tk('s:H'), tk(GOV)];
until(() => !walking(H) && H.state === 'working', 30, 'back'); out.toGov.home = D(H, H0);

out.far0 = D(g(), L);
const L0 = at('s:L');
apply({ type: 'talk', from: GOV, to: 's:L', terr: tid });
out.fromGov = { talk0: tk(GOV) };
out.fromGov.trip = until(() => !!tk(GOV), 16, 'gov-walks');
out.fromGov.arrive = { d: D(g(), L), talks: [tk(GOV), tk('s:L')], leadMoved: D(L, L0), walking: govWalking() };
tick(.8, 'gov-talk'); out.fromGov.face = [faces(g(), L), faces(L, g())];
tick(TALK_SEC + .3, 'gov-talk'); out.fromGov.after = [tk(GOV), tk('s:L')];
out.fromGov.backT = until(() => D(g(), hs) < .05 && !govWalking(), 30, 'gov-back');
out.fromGov.home = D(g(), hs);

apply({ type: 'talk', from: GOV, to: 's:L', terr: tid });
tick(1.2, 'gov-leaves'); out.cut = { away: D(g(), hs) };
apply({ type: 'relay', id: 'w1', to: 'governor', lead: '' });
let talkedToL = 0;
out.cut.t = until(() => byId('w1').state === 'asking', 30, 'summon', () => { const t = tk(GOV); if (t && t.with === 's:L') talkedToL++; });
out.cut.w1 = byId('w1').state; out.cut.govHome = D(g(), hs); out.cut.talkedToL = talkedToL; out.cut.talkL = tk('s:L');
out.stackBad = stackBad;
__out = out;
}
"""


# T3: one talk per person at a time; over TALK_WAIT_MAX waiting -> no walk
SCENES["queue"] = r"""
start();
const L = byId('s:L');
apply({ type: 'talk', from: 'w1', to: 's:L', terr: tid });
apply({ type: 'talk', from: 'w2', to: 's:L', terr: tid });
let both = 0; const seen = {}, withL = {};
tick(40, 'queue', () => {
  const a = tk('w1'), b = tk('w2'), l = tk('s:L');
  if (a && b && a.with === 's:L' && b.with === 's:L') both++;
  if (a && a.with === 's:L') seen.w1 = 1; if (b && b.with === 's:L') seen.w2 = 1; if (l) withL[l.with] = 1;
});
out.two = { both, seen: Object.keys(seen).sort(), withL: Object.keys(withL).sort(), talkL: tk('s:L'),
  home: ['w1', 'w2'].map(id => r3(D(byId(id), byId(id).home))), states: ['w1', 'w2'].map(id => byId(id).state) };

const five = ['w1', 'w2', 'w3', 's:H', 'd1'], pos0 = five.map(at);
for (const id of five) apply({ type: 'talk', from: id, to: 's:L', terr: tid });
out.over = { last0: tk('d1'), lastWalking: walking(byId('d1')) };
let moved = 0; const got = {};
tick(70, 'over', () => {
  moved = Math.max(moved, D(byId('d1'), pos0[4]));
  for (const id of five) { const t = tk(id); if (t && t.with === 's:L') got[id] = 1; }
});
out.over.lastMoved = moved; out.over.got = Object.keys(got).sort(); out.over.talkL = tk('s:L');
out.over.home = five.map((id, i) => r3(D(byId(id), pos0[i])));
out.stackBad = stackBad;
__out = out;
}
"""


# T3: a real status change ends the talk at once (one change per run: __payload.change)
SCENES["status"] = r"""
start();
const L = byId('s:L'), H = byId('s:H'), ch = __payload.change;
const H0 = at('s:H');
out.words = { bg: i18n('status.background'), idle: i18n('status.idle') };
if (ch === 'handover-stuck') {
  apply({ type: 'spawn', id: 'w9', role: 'worker', label: 'worker', task: 'page', terr: tid, lead: 's:L', office: null, from: 's:L' });
  tick(.5, 'handover');
  apply({ type: 'stuck', id: 'w9', tool: 'AskUserQuestion', question: 'which port?' });
  out.now = { state: byId('w9').state, talks: [tk('w9'), tk('s:L')] };
} else {
  apply({ type: 'talk', from: 's:H', to: 's:L', terr: tid });
  if (ch === 'waiting-walker') tick(1, 'walk-over');
  else { out.trip = until(() => !walking(H) && H.state === 'talking', 14, 'walk-over'); tick(.5, 'talk'); }
  out.before = { state: H.state, talks: [tk('s:H'), tk('s:L')] };
  if (ch === 'waiting-walker') apply({ type: 'waiting', id: 's:H' });
  if (ch === 'waiting-other') apply({ type: 'waiting', id: 's:L' });
  if (ch === 'stuck-sender') apply({ type: 'stuck', id: 's:H', tool: 'AskUserQuestion', question: 'which port?' });
  if (ch === 'relay-other') apply({ type: 'relay', id: 's:L', to: 'governor', lead: '' });
  if (ch === 'done-sender') apply({ type: 'done', id: 's:H' });
  if (ch === 'background-other') apply({ type: 'background', id: 's:L' });
  if (ch === 'idle-sender') apply({ type: 'idle', id: 's:H' });
  out.now = { stateH: H.state, stateL: L.state, talks: [tk('s:H'), tk('s:L')], status: [st(H), st(L)] };
  let later = 0;
  tick(45, 'after', () => { if (tk('s:L') && ch !== 'background-other' && ch !== 'idle-sender') later++; });
  out.end = { stateH: H.state, stateL: L.state, home: D(H, H0), talkedLater: later, walking: walking(H) };
}
out.stackBad = stackBad;
__out = out;
}
"""


# T3: a question passed up, and the answer coming back
SCENES["relay"] = r"""
start();
const L = byId('s:L'), w1 = byId('w1');
apply({ type: 'relay', id: 'w1', to: 'lead', lead: 's:L' });
out.walkTalk = tk('w1');
out.t1 = until(() => w1.state === 'at_lead', 30, 'to-lead'); tick(.1, 'at-lead');
out.ask = { talks: [tk('w1'), tk('s:L')], d: D(w1, L) };
tick(.8, 'ask'); out.ask.face = [faces(w1, L), faces(L, w1)];
tick(TALK_SEC + .3, 'ask-end'); out.ask.after = { talks: [tk('w1'), tk('s:L')], state: w1.state, face: faces(w1, L) };
const wAt = at('w1');
apply({ type: 'relay_end', id: 'w1', by: 'lead' });
out.answer = { relay: w1.relay, talks: [tk('w1'), tk('s:L')], walking: walking(w1) };
tick(TALK_SEC * .5, 'answer'); out.answer.mid = { moved: D(w1, wAt), talkL: tk('s:L'), face: [faces(w1, L), faces(L, w1)] };
tick(TALK_SEC * .5 + .4, 'answer-end'); out.answer.after = { talks: [tk('w1'), tk('s:L')] };
until(() => !walking(w1) && w1.state === 'working', 30, 'back'); out.answer.end = { state: w1.state, home: D(w1, w1.home) };

apply({ type: 'relay', id: 's:L', to: 'governor', lead: '' });
out.t2 = until(() => L.state === 'asking', 40, 'to-hall'); tick(.1, 'asking');
out.gask = { talks: [tk('s:L'), tk(GOV)], d: D(L, g()) };
tick(.8, 'gov-ask'); out.gask.face = [faces(L, g()), faces(g(), L)];
tick(TALK_SEC + .3, 'gov-ask-end'); out.gask.after = { talks: [tk('s:L'), tk(GOV)], state: L.state };
const lAt = at('s:L');
apply({ type: 'relay_end', id: 's:L', by: 'governor' });
out.ganswer = { talks: [tk('s:L'), tk(GOV)], walking: walking(L) };
tick(TALK_SEC * .5, 'gov-answer'); out.ganswer.mid = { moved: D(L, lAt), talkG: tk(GOV), face: faces(g(), L) };
tick(TALK_SEC * .5 + .4, 'gov-answer-end'); out.ganswer.after = { talkG: tk(GOV) };
until(() => !walking(L) && (L.state === 'working' || L.state === 'building'), 40, 'lead-back'); out.ganswer.end = L.state;

const w2 = byId('w2'), w3 = byId('w3');
apply({ type: 'relay', id: 'w2', to: 'lead', lead: 's:L' });
until(() => w2.state === 'at_lead', 30, 'w2'); tick(TALK_SEC + .5, 'w2-waits');
apply({ type: 'relay_end', id: 'w2', by: 'timeout' });
out.timeout = { talks: [tk('w2'), tk('s:L')], state: w2.state };
tick(.3, 'timeout'); out.timeout.talksSoon = [tk('w2'), tk('s:L')];
apply({ type: 'relay', id: 'w3', to: 'lead', lead: 's:L' });
tick(.2, 'w3-leaves'); out.onTheWay = { state0: w3.state };
apply({ type: 'relay_end', id: 'w3', by: 'lead' });
out.onTheWay.state = w3.state; out.onTheWay.talks = [tk('w3'), tk('s:L')];
tick(.3, 'w3-back'); out.onTheWay.talksSoon = [tk('w3'), tk('s:L')];
out.stackBad = stackBad;
__out = out;
}
"""


# T3: the owner answered an ask -> the governor tells the one who asked
SCENES["heard"] = r"""
start();
const H = byId('s:H');
apply({ type: 'stuck', id: 's:H', tool: 'AskUserQuestion', question: 'which port?' });
out.t = until(() => H.state === 'asking', 30, 'to-hall');
apply({ type: 'answer', id: 's:H', answer: '4791' });
out.t2 = until(() => H.state === 'heard', 6, 'answer');
tick(.3, 'heard'); out.heard = { state: H.state, talks: [tk('s:H'), tk(GOV)] };
tick(.6, 'heard'); out.face = [faces(H, g()), faces(g(), H)]; out.state = H.state;
out.stackBad = stackBad;
__out = out;
}
"""


# T2: a walker walks around a person who stands on its way
SCENES["around"] = r"""
start();
const H = byId('s:H'), b = byId('d1');
const way = openWay();
out.open = !!way;
if (way) {
  const [A, B] = way, M = { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2 };
  put(H, A); H.home = { x: B.x, y: B.y }; H.stand = H.home; put(b, M);
  tick(.3, 'placed');
  goTo(H, H.home, 'back');
  let minD = 9;
  out.t = until(() => !walking(H) && H.state === 'working', 25, 'around', () => { minD = Math.min(minD, D(H, b)); });
  out.around = { minD, state: H.state, arrived: D(H, B), blockerMoved: D(b, M) };
}
out.stackBad = stackBad;
__out = out;
}
"""


# T2: two walkers head-on on the same way do not walk through each other
SCENES["headon"] = r"""
start();
const H = byId('s:H'), b = byId('d1');
const way = openWay();
out.open = !!way;
if (way) {
  const [A, B] = way;
  put(H, A); H.home = { x: B.x, y: B.y }; H.stand = H.home; put(b, B); b.home = { x: A.x, y: A.y }; b.stand = b.home;
  tick(.3, 'placed');
  goTo(H, H.home, 'back'); goTo(b, b.home, 'back');
  let minD = 9, bothWalked = 0;
  out.t = until(() => !walking(H) && !walking(b) && H.state === 'working' && b.state === 'working', 30, 'head-on',
    () => { if (walking(H) && walking(b)) bothWalked++; minD = Math.min(minD, D(H, b)); });
  out.headOn = { minD, bothWalked, arrived: [D(H, B), D(b, A)] };
}
out.stackBad = stackBad;
__out = out;
}
"""


# T2: a person who leaves does not stand on the governor
SCENES["leave"] = r"""
start();
const d = byId('d1');
leave(d);
let minD = 9, stood = 0;
tick(30, 'leave', () => { if (!d.gone && d.state === 'leaving' && !walking(d)) { stood++; minD = Math.min(minD, D(d, g())); } });
out.leave = { minD, stood, gone: !!d.gone };
out.stackBad = stackBad;
__out = out;
}
"""


class SimCase_talk(unittest.TestCase):
    """Runs one scene of the page simulation on a grown territory (a lead with an office, its three
    workers, a helper session, a deputy, the governor at his hall)."""

    scene = ""
    payload = {}
    _view = None

    @classmethod
    def view(cls):
        if SimCase_talk._view is None:
            SimCase_talk._view = office_view("app")
        return SimCase_talk._view

    @classmethod
    def run_scene(cls, name, **payload):
        return run_sim(PRELUDE + SCENES[name], dict(payload, view=cls.view()), TALK_REQUIRED)

    @classmethod
    def setUpClass(cls):
        if cls.scene:
            cls.r = cls.run_scene(cls.scene, **cls.payload)

    def talk(self, got, kind, other, speaking, icon=None):
        self.assertIsNotNone(got, "in a talk")
        self.assertEqual((got["kind"], got["with"], got["speaking"]), (kind, other, speaking))
        if icon is not None:
            self.assertEqual(got["icon"], icon)
        if not speaking:
            self.assertEqual(got["icon"], "", "only the one who speaks has a bubble")

    def beside(self, d, far=TALK_NEAR):
        self.assertGreaterEqual(d, MIN_GAP - EPS, "never on the other one's spot")
        self.assertLessEqual(d, far + EPS, "next to it")

    def no_stack(self):
        self.assertEqual(self.r["stackBad"], [], "standing people closer than %.2f: [scene, a, b, distance]" % MIN_GAP)


class TestNewAgentAppearsNextToItsSenderT1(SimCase_talk):
    scene = "spawn"

    def test_snapshot_people_get_no_hand_over(self):
        self.assertEqual(self.r["snapTalk"], [None, None, None, None])

    def test_a_worker_appears_next_to_its_lead(self):
        one = self.r["one"]
        self.assertEqual(one["state0"], "handover")
        self.beside(one["d0"])

    def test_the_task_is_handed_over_face_to_face(self):
        one = self.r["one"]
        self.talk(one["talkLead0"], "handover", "w9", True, "📋")
        self.talk(one["talkNew0"], "handover", "s:L", False)
        self.assertEqual(one["face"], [True, True], "the new one and its lead face each other")
        self.assertEqual(one["stateMid"], "handover")
        self.assertLess(one["movedMid"], .01, "the new one stands still during the hand-over")
        self.assertLess(one["leadMoved"], .01, "the sender stays where it is")

    def test_the_new_one_answers_at_the_end(self):
        new, lead = self.r["one"]["reply"]
        self.talk(new, "handover", "s:L", True, "👌")
        self.talk(lead, "handover", "w9", False)

    def test_then_it_walks_to_its_own_spot(self):
        one = self.r["one"]
        self.assertIn(one["after"]["state"], ("to_plot", "working", "building"))
        self.assertEqual(one["after"]["talks"], [None, None], "the hand-over is over after HANDOVER_SEC")
        self.assertEqual(one["end"]["state"], "working")
        self.assertLess(one["end"]["home"], .05, "it ends on its own spot")

    def test_a_task_manager_sent_by_the_governor(self):
        tm = self.r["tm"]
        self.assertEqual(tm["state0"], "handover")
        self.beside(tm["d0"], ACROSS_DESK)
        self.assertEqual(tm["talkGov0"]["kind"], "handover")
        self.assertNotEqual(tm["after"], "handover")

    def test_a_subagent_of_a_plain_session(self):
        sub = self.r["sub"]
        self.assertEqual(sub["state0"], "handover")
        self.beside(sub["d0"])
        self.talk(sub["talkH0"], "handover", "h1", True, "📋")
        self.assertNotEqual(sub["after"], "handover")

    def test_five_at_once_get_one_hand_over(self):
        five = self.r["five"]
        self.assertEqual(five["talkLead0"]["kind"], "handover")
        self.assertTrue(five["talkLead0"]["speaking"])
        self.assertEqual(five["statesMid"], ["handover"] * 5)
        self.assertIsNotNone(five["talkLeadLate"])
        self.assertTrue(five["talkLeadLate"]["speaking"], "to several new ones the sender speaks all the time")
        self.assertNotIn("handover", five["after"]["states"])
        self.assertIsNone(five["after"]["talkLead"])
        self.assertEqual(five["end"], ["working"] * 5, "each one reaches its own spot")

    def test_nobody_stacks(self):
        self.no_stack()


class TestNoSenderT1T2(SimCase_talk):
    scene = "nosender"

    def test_without_a_sender_it_spawns_as_before(self):
        self.assertEqual(self.r["states"], ["spawn"] * 3)
        self.assertEqual(self.r["talks"], [None] * 3)
        self.assertIsNone(self.r["govTalk"])
        self.assertEqual(self.r["end"], ["working"] * 3)

    def test_a_governor_who_is_away_sends_nobody(self):
        self.assertEqual(self.r["noGov"], {"state": "spawn", "talk": None})

    def test_nobody_stacks(self):
        self.no_stack()


class TestMessageTalkT3(SimCase_talk):
    scene = "talk"

    def test_setup_is_far_apart(self):
        self.assertGreater(self.r["far0"], TALK_NEAR + .5, "the scene needs the helper far from the lead")

    def test_the_sender_walks_over(self):
        go = self.r["go"]
        self.assertEqual(go["state"], "to_talk")
        self.assertTrue(go["walking"])
        self.assertEqual(go["talks"], [None, None], "no bubble while it walks over")
        self.assertLessEqual(self.r["trip"], TRIP + 2, "there in about TALK_TRIP_MAX_SEC")

    def test_they_talk_face_to_face(self):
        arrive = self.r["arrive"]
        self.assertEqual(arrive["state"], "talking")
        self.beside(arrive["d"])
        self.talk(arrive["talks"][0], "msg", "s:L", True, "💬")
        self.talk(arrive["talks"][1], "msg", "s:H", False)
        self.assertEqual(self.r["face"], [True, True])
        self.assertLess(arrive["leadMoved"], .01, "the other one stays on its spot")

    def test_the_other_one_answers(self):
        sender, other = self.r["reply"]
        self.talk(other, "msg", "s:H", True, "👌")
        self.talk(sender, "msg", "s:L", False)

    def test_then_both_go_back_to_what_they_did(self):
        after, end = self.r["after"], self.r["end"]
        self.assertEqual(after["talks"], [None, None])
        self.assertEqual((after["state"], after["walking"]), ("back", True), "the sender walks back")
        self.assertIn(after["leadState"], ("working", "building"))
        self.assertLess(after["leadMoved"], .01)
        self.assertIn(end["state"], ("working", "building"))
        self.assertLess(end["home"], .05, "the sender ends on its own spot")

    def test_a_talk_never_changes_the_status(self):
        before = self.r["go"]["before"]
        self.assertEqual(self.r["go"]["status"], before, "walking over: both read as before")
        self.assertEqual(self.r["arrive"]["status"], before, "talking: both read as before")

    def test_close_by_nobody_walks(self):
        near = self.r["near"]
        self.assertLessEqual(near["d"], TALK_NEAR)
        self.assertFalse(near["walking"])
        self.talk(near["talks"][0], "msg", "s:L", True, "💬")
        self.talk(near["talks"][1], "msg", "w1", False)
        self.assertEqual(near["face"], [True, True], "both turn to face each other")
        self.assertLess(near["moved"], .01)
        self.assertEqual(near["after"]["talks"], [None, None])
        self.assertLess(near["after"]["moved"], .01)
        self.assertIn(near["after"]["state"], ("working", "building"))

    def test_recipient_not_recognised_the_bubble_on_its_own_spot(self):
        lost = self.r["lost"]
        self.talk(lost["talk"], "msg", "", True, "💬")
        self.assertFalse(lost["walking"])
        self.assertEqual(lost["state"], lost["state0"], "its state does not change")
        self.talk(lost["mid"], "msg", "", True, "💬")
        self.assertLess(lost["moved"], .01)
        self.assertIsNone(lost["after"], "gone after TALK_SEC")
        self.talk(self.r["lost2"]["talk"], "msg", "", True, "💬")
        self.assertFalse(self.r["lost2"]["walking"])

    def test_unknown_sender_does_nothing(self):
        self.assertEqual(self.r["noSender"], [None, 0])

    def test_nobody_stacks(self):
        self.no_stack()


class TestGovernorTalksT3(SimCase_talk):
    scene = "gov"

    def gid(self):
        return "gov:" + self.view()["floors"][0]

    def test_a_message_to_the_governor(self):
        to = self.r["toGov"]
        self.assertEqual(to["state"], "to_talk")
        self.assertLessEqual(to["trip"], TRIP + 2)
        self.beside(to["arrive"]["d"], ACROSS_DESK)
        self.assertLess(to["arrive"]["govAtHall"], .05, "the governor is at his hall stand for it")
        self.talk(to["arrive"]["talks"][0], "msg", self.gid(), True, "💬")
        self.talk(to["arrive"]["talks"][1], "msg", "s:H", False)
        self.assertEqual(to["face"], [True, True])
        self.assertEqual(to["after"], [None, None])
        self.assertLess(to["home"], .05)

    def test_the_governor_walks_over_with_his_message(self):
        fg = self.r["fromGov"]
        self.assertGreater(self.r["far0"], TALK_NEAR + .5, "the scene needs the lead far from the hall")
        self.assertIsNone(fg["talk0"], "no bubble while he walks over")
        self.assertLessEqual(fg["trip"], TRIP + 2.5)
        self.beside(fg["arrive"]["d"], ACROSS_DESK)
        self.assertFalse(fg["arrive"]["walking"])
        self.talk(fg["arrive"]["talks"][0], "msg", "s:L", True, "💬")
        self.talk(fg["arrive"]["talks"][1], "msg", self.gid(), False)
        self.assertLess(fg["arrive"]["leadMoved"], .01)
        self.assertEqual(fg["face"], [True, True])
        self.assertEqual(fg["after"], [None, None])

    def test_then_he_goes_back_to_his_hall(self):
        self.assertLess(self.r["fromGov"]["home"], .05)

    def test_someone_who_needs_him_calls_him_back(self):
        cut = self.r["cut"]
        self.assertGreater(cut["away"], .3, "the scene needs him on his way")
        self.assertEqual(cut["w1"], "asking")
        self.assertLess(cut["govHome"], .05, "he is back at his hall stand when the asker arrives")
        self.assertEqual(cut["talkedToL"], 0, "the talk he walked to is dropped")
        self.assertIsNone(cut["talkL"])

    def test_nobody_stacks(self):
        self.no_stack()


class TestOneTalkAtATimeT3(SimCase_talk):
    scene = "queue"

    def test_two_messages_for_one_person_take_turns(self):
        two = self.r["two"]
        self.assertEqual(two["both"], 0, "never two talks with one person at the same time")
        self.assertEqual(two["seen"], ["w1", "w2"], "both get their talk")
        self.assertEqual(two["withL"], ["w1", "w2"])
        self.assertIsNone(two["talkL"])
        self.assertEqual(two["states"], ["working", "working"])
        for d in two["home"]:
            self.assertLess(d, .05, "both end on their own spots")

    def test_over_three_waiting_the_next_one_does_not_walk(self):
        over = self.r["over"]
        self.talk(over["last0"], "msg", "", True, "💬")
        self.assertFalse(over["lastWalking"])
        self.assertLess(over["lastMoved"], .01, "the fifth sender never leaves its spot")
        self.assertEqual(over["got"], ["s:H", "w1", "w2", "w3"], "the first four get their talk, in line")
        self.assertIsNone(over["talkL"])
        for d in over["home"]:
            self.assertLess(d, .05, "everybody ends where it started")

    def test_nobody_stacks(self):
        self.no_stack()


class TestStatusAlwaysWinsT3(SimCase_talk):
    """A talk never hides or delays a real status change."""

    def change(self, name):
        self.r = self.run_scene("status", change=name)
        return self.r

    def test_waiting_while_it_walks_over(self):
        r = self.change("waiting-walker")
        self.assertEqual(r["before"]["state"], "to_talk")
        self.assertEqual(r["now"]["status"][0][0], "you", "等你回话 shows at once")
        self.assertEqual(r["now"]["talks"], [None, None])
        self.assertNotEqual(r["now"]["stateH"], "to_talk", "it stops walking over at once")
        self.assertEqual(r["end"]["talkedLater"], 0, "the talk never happens")
        self.assertLess(r["end"]["home"], .05, "it is back on its own spot")
        self.no_stack()

    def test_waiting_of_the_other_one_ends_the_talk(self):
        r = self.change("waiting-other")
        self.assertIsNotNone(r["before"]["talks"][1], "the scene needs the talk running")
        self.assertEqual(r["now"]["status"][1][0], "you", "等你回话 shows at once")
        self.assertEqual(r["now"]["talks"], [None, None], "the talk ends for both at once")
        self.assertEqual(r["now"]["stateH"], "back", "the sender walks back at once")
        self.assertLess(r["end"]["home"], .05)

    def test_a_stuck_sender_heads_up_the_chain_at_once(self):
        r = self.change("stuck-sender")
        self.assertEqual(r["now"]["stateH"], "to_hall")
        self.assertEqual(r["now"]["talks"], [None, None])
        self.assertEqual(r["end"]["stateH"], "asking")

    def test_a_relay_of_the_other_one_ends_the_talk(self):
        r = self.change("relay-other")
        self.assertEqual(r["now"]["stateL"], "to_hall")
        self.assertEqual(r["now"]["talks"], [None, None])
        self.assertEqual(r["now"]["stateH"], "back")
        self.assertLess(r["end"]["home"], .05)

    def test_done_ends_the_talk_and_it_rests(self):
        r = self.change("done-sender")
        self.assertEqual(r["now"]["talks"], [None, None])
        self.assertIn(r["end"]["stateH"], ("finishing", "to_rest", "resting"))

    def test_background_shows_at_once(self):
        r = self.change("background-other")
        self.assertEqual(r["now"]["status"][1], ["bgrun", r["words"]["bg"]])

    def test_idle_shows_at_once(self):
        r = self.change("idle-sender")
        self.assertEqual(r["now"]["status"][0], ["walk", r["words"]["idle"]])

    def test_a_stuck_newcomer_leaves_the_hand_over_at_once(self):
        r = self.change("handover-stuck")
        self.assertEqual(r["now"]["state"], "to_lead")
        self.assertEqual(r["now"]["talks"], [None, None])


class TestQuestionAndAnswerT3(SimCase_talk):
    scene = "relay"

    def gid(self):
        return "gov:" + self.view()["floors"][0]

    def test_a_worker_asks_its_lead_face_to_face(self):
        ask = self.r["ask"]
        self.assertIsNone(self.r["walkTalk"], "no bubble while it walks")
        self.beside(ask["d"])
        self.talk(ask["talks"][0], "ask", "s:L", True, "❓")
        self.talk(ask["talks"][1], "ask", "w1", False)
        self.assertEqual(ask["face"], [True, True])
        self.assertEqual(ask["after"]["talks"], [None, None], "the talk is short")
        self.assertEqual(ask["after"]["state"], "at_lead", "it keeps waiting there")
        self.assertTrue(ask["after"]["face"], "and keeps facing its lead")

    def test_the_lead_answers_before_it_walks_back(self):
        ans = self.r["answer"]
        self.assertEqual(ans["relay"], "", "the status follows at once")
        self.talk(ans["talks"][1], "answer", "w1", True, "✅")
        self.talk(ans["talks"][0], "answer", "s:L", False)
        self.assertFalse(ans["walking"])
        self.assertLess(ans["mid"]["moved"], .01, "it listens first")
        self.assertEqual(ans["mid"]["face"], [True, True])
        self.assertEqual(ans["after"]["talks"], [None, None])
        self.assertEqual(ans["end"]["state"], "working")
        self.assertLess(ans["end"]["home"], .05)

    def test_a_lead_asks_the_governor_face_to_face(self):
        ask = self.r["gask"]
        self.beside(ask["d"], ACROSS_DESK)
        self.talk(ask["talks"][0], "ask", self.gid(), True, "❓")
        self.talk(ask["talks"][1], "ask", "s:L", False)
        self.assertEqual(ask["face"], [True, True], "the governor turns to the one who asks")
        self.assertEqual(ask["after"]["talks"], [None, None])
        self.assertEqual(ask["after"]["state"], "asking")

    def test_the_governor_answers_before_it_walks_back(self):
        ans = self.r["ganswer"]
        self.talk(ans["talks"][1], "answer", "s:L", True, "✅")
        self.talk(ans["talks"][0], "answer", self.gid(), False)
        self.assertFalse(ans["walking"])
        self.assertLess(ans["mid"]["moved"], .01)
        self.assertTrue(ans["mid"]["face"])
        self.assertIsNone(ans["after"]["talkG"])
        self.assertIn(ans["end"], ("working", "building"))

    def test_no_answer_no_talk(self):
        self.assertEqual(self.r["timeout"]["talks"], [None, None])
        self.assertEqual(self.r["timeout"]["talksSoon"], [None, None])
        self.assertEqual(self.r["timeout"]["state"], "back", "a timeout sends it straight back")

    def test_answered_on_the_way_no_talk(self):
        way = self.r["onTheWay"]
        self.assertEqual(way["state0"], "to_lead")
        self.assertEqual(way["state"], "back")
        self.assertEqual(way["talks"], [None, None])
        self.assertEqual(way["talksSoon"], [None, None])

    def test_nobody_stacks(self):
        self.no_stack()


class TestOwnerAnswerT3(SimCase_talk):
    scene = "heard"

    def test_the_governor_tells_the_one_who_asked(self):
        gid = "gov:" + self.view()["floors"][0]
        self.assertEqual(self.r["heard"]["state"], "heard")
        self.talk(self.r["heard"]["talks"][1], "answer", "s:H", True, "✅")
        self.talk(self.r["heard"]["talks"][0], "answer", gid, False)
        self.assertEqual(self.r["face"], [True, True])
        self.no_stack()


class TestWalkersKeepAGapT2(SimCase_talk):

    def test_a_leaving_person_never_stands_on_the_governor(self):
        r = self.r = self.run_scene("leave")
        self.assertGreater(r["leave"]["stood"], 0, "the scene needs it standing at the hall")
        self.assertGreaterEqual(r["leave"]["minD"], MIN_GAP - EPS)


class TestTalkLookT3(unittest.TestCase):
    """The 3D part cannot run here: the bubble and the gesture are wired to talkOf / govTalkOf."""

    def three_d(self):
        text = page()
        return text[text.index("3D view."):]

    def test_css_has_the_talk_bubble(self):
        self.assertRegex(page(), r"\.talkb\s*\{[^}]*border", "a .talkb rule for the small talk bubble")

    def test_each_person_has_a_talk_bubble(self):
        self.assertIn("talkb", function_source("ensureOv") or "", "ensureOv makes the bubble element")
        self.assertIn("talkOf(", function_source("updatePerson") or "", "updatePerson shows it from talkOf(c)")

    def test_the_governor_has_one_too(self):
        self.assertIn("govTalkOf(", self.three_d(), "the governor's bubble comes from govTalkOf(terr)")

    def test_the_speaker_gestures(self):
        self.assertIn(".speaking", self.three_d(), "the one who speaks plays a talk gesture")

    def test_no_chat_text_in_the_bubble(self):
        for fn in ("talkOf", "govTalkOf"):
            src = function_source(fn) or ""
            self.assertTrue(src, fn + " exists")
            for word in ("entries", "last_assistant_message", ".text"):
                self.assertNotIn(word, src, "the bubble is an icon, never chat text")

    def test_no_letter_mode(self):
        self.assertNotIn("letter", (function_source("talkOf") or "") + (function_source("govTalkOf") or ""))


class TestDemoShowsItT1T3(unittest.TestCase):
    """#demo plays hand-overs and talks, so the look can be checked without real sessions."""

    def test_only_where_the_demo_draws_a_governor(self):
        # owner-side check 2026-10-01 (headless #demo): a new person in v4-plus / pos-lite stood beside an
        # empty hall and answered 👌 to nobody; the demo draws one governor, in govTerr (governorFigures)
        self.assertRegex(function_source("spawnDemo") or "", r"from:\s*terr === govTerr \? 'gov:'\s*\+\s*terr : ''")

    def test_demo_people_talk_now_and_then(self):
        src = function_source("demoTalkTick") or ""
        self.assertTrue(src, "function demoTalkTick(dt) exists")
        self.assertRegex(src, r"type:\s*'talk'")
        self.assertRegex(src, r"emit\(|apply\(", "through the same path as a live event")
        self.assertRegex(function_source("update") or "", r"if \(DEMO\)[^\n]*demoTalkTick\(dt\)")
        m = re.search(r"^const DEMO_TALK_SEC = ([\d.]+);", page(), re.M)
        self.assertIsNotNone(m, "const DEMO_TALK_SEC = <seconds>;")
        self.assertTrue(6 <= float(m.group(1)) <= 15)


ERR = "对话没加载出来，等会儿再打开看看。"


class TestSubagentPanelHasNoRedLineT4(unittest.TestCase):

    def fail_text(self, cases):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = {}; vm.createContext(box); vm.runInContext(fns, box);
require(`fs`).writeSync(1, JSON.stringify(cases.map(c => box.chatFailText(c[0], c[1]))));
"""
        return run_node(js, {"fns": constants_prelude() + "\n" + page_fns("chatFailText"), "cases": cases})

    def test_a_subagent_never_gets_the_red_line(self):
        out = self.fail_text([["a9f3c2", {"error": ERR}], ["w1", {"error": ERR, "entries": []}],
                              ["agent-77", {"error": "x"}]])
        self.assertEqual(out, ["", "", ""], "a subagent has no chat of its own: read-only note only")

    def test_a_session_still_shows_a_failed_load(self):
        out = self.fail_text([["s:tm1", {"error": ERR}], ["gov:t1", {"error": ERR}]])
        self.assertEqual(out, [ERR, ERR], "a failure is shown in a session's window, never swallowed")

    def test_no_error_no_line(self):
        out = self.fail_text([["s:tm1", {"entries": []}], ["s:tm1", None], ["w1", None], ["gov:t1", {"error": ""}]])
        self.assertEqual(out, ["", "", "", ""])

    def test_the_panel_uses_it_in_both_places(self):
        body = function_source_talk_panel("renderDetail") or ""
        self.assertGreaterEqual(body.count("chatFailText("), 2,
                                "chatSectionHtml and the per-call #chat-fail refresh both ask chatFailText")
        self.assertNotIn("box.error ? '' : ' hidden'", body, "the red line no longer follows box.error alone")
        self.assertNotIn("fail.hidden = !box.error", body, "the refresh no longer follows box.error alone")
        self.assertIn("hint.readOnlySub", body, "the read-only note stays")
        self.assertIn("btn.findLead", body, "the way to its lead stays")


class TestLabelDropsTheRepeatedKindT5(unittest.TestCase):

    def names(self, pairs):
        driver = r"""
__out = __payload.pairs.map(p => nameOf({ id: 'x1', label: p[0], task: p[1] }));
"""
        return run_sim(driver, {"pairs": pairs}, REQUIRED + ("nameOf",))

    def test_the_owner_case(self):
        self.assertEqual(self.names([["fast-lane-deputy", "msg-sides Deputy"]]), ["msg-sides Deputy"],
                         "owner screenshot: 'fast-lane-deputy · msg-sides Deputy' repeats the kind")

    def test_the_kinds_last_word_in_the_name(self):
        out = self.names([["fast-lane-deputy", "msg-sides deputy"], ["fast-lane-deputy", "Deputy for the rail"],
                          ["merge-deputy", "city-status Deputy"], ["worker", "the login Worker"],
                          ["worker", "worker: api"]])
        self.assertEqual(out, ["msg-sides deputy", "Deputy for the rail", "city-status Deputy", "the login Worker",
                               "worker: api"])

    def test_the_names_last_word_is_a_word_of_the_kind(self):
        self.assertEqual(self.names([["merge-deputy", "city-status Merge"], ["merge-deputy", "city-status merge"]]),
                         ["city-status Merge", "city-status merge"])

    def test_a_name_that_does_not_say_the_kind_keeps_it(self):
        out = self.names([["fast-lane-deputy", "按钮颜色"], ["worker", "city-polish Deputy"],
                          ["worker", "coworker list"], ["fast-lane-deputy", "fast checkout"],
                          ["fast-lane-deputy", "deputyship notes"], ["Explore", "Survey city page"]])
        self.assertEqual(out, ["fast-lane-deputy · 按钮颜色", "worker · city-polish Deputy", "worker · coworker list",
                               "fast-lane-deputy · fast checkout", "fast-lane-deputy · deputyship notes",
                               "Explore · Survey city page"])

    def test_old_rules_stay(self):
        out = self.names([["worker", "worker"], ["worker", ""], ["worker", "Slice A"],
                          ["worker", "city-talk Worker 2: page"], ["task-manager", "city-people"]])
        self.assertEqual(out, ["worker", "worker", "worker · Slice A", "Worker 2 · page", "task-manager · city-people"])


FREE_DRIVER = r"""
__out = [
  freeCentre(1200, 800, { right: 236 }, null),
  freeCentre(1200, 800, null, null),
  freeCentre(1200, 800, { right: 236 }, { left: 858, top: 12, right: 1188, bottom: 788 }),
  freeCentre(1200, 800, { right: 40 }, { left: 1168, top: 12, right: 1200, bottom: 200 }),
  freeCentre(1200, 800, { right: 236 }, { left: 300, top: 12, right: 1188, bottom: 788 }),
  freeCentre(1200, 800, { right: 700 }, { left: 800, top: 12, right: 1188, bottom: 788 }),
  freeCentre(400, 700, null, { left: 6, top: 390, right: 394, bottom: 694 }),
  freeCentre(400, 700, null, { left: 6, top: 80, right: 394, bottom: 694 }),
];
"""


class TestFreeCentre(unittest.TestCase):

    def test_values(self):
        r = run_sim(FREE_DRIVER, {}, ("freeCentre",))
        self.assertEqual(r, [[718, 400], [600, 400], [547, 400], [604, 400], [600, 400], [600, 400], [200, 195], [200, 350]])


class TestRailMarkup(unittest.TestCase):

    def test_markup_inside_the_stage(self):
        p = page()
        stage, tb = p.index('id="stage"'), p.index('class="toolbar"')
        for bit in ('<aside class="rail" id="rail"', 'id="rail-list"', 'id="rail-n"', 'id="rail-you"', 'id="rail-fold"',
                    'id="rail-tab"', 'id="follow"', 'id="follow-t"', 'id="follow-stop"', 'id="win-fold"', 'id="win-tab"'):
            self.assertIn(bit, p, bit)
            self.assertTrue(stage < p.index(bit) < tb, bit + " inside #stage")
        self.assertRegex(p, r'<div class="follow" id="follow" role="status"[^>]*hidden')
        self.assertRegex(p, r'<button type="button" class="tab rail-tab" id="rail-tab" aria-controls="rail"[^>]*hidden')
        self.assertRegex(p, r'<button type="button" class="tab win-tab" id="win-tab" aria-controls="win"[^>]*hidden')
        self.assertLess(p.index('id="win-fold"'), p.index('id="win-close"'), "fold, then close")
        self.assertNotIn('id="rail-btn"', p, "the rail tab is the phone drawer button too")

    def test_text_keys(self):
        for k in ("rail.title", "rail.count", "rail.rest", "rail.tab", "fold.rail", "fold.msg", "msg.tab",
                  "follow.on", "follow.stop", "b.focus"):
            self.assertEqual(text_keys(k), 2, k + " in zh and en")


class TestRailWiring(unittest.TestCase):

    def test_render_rail(self):
        src = function_source("renderRail") or ""
        for bit in ("railGroups(", "railHtml(", "railCount(", "selKey(", "railClosed", "railRestOpen", "lastRail",
                    "rail.count", "railFolded"):
            self.assertIn(bit, src, bit)
        self.assertIn("renderRail(", function_source("renderPanel") or "")

    def test_rail_clicks(self):
        block = listener_block(r"\$\('#rail-list'\)", "click") or ""
        for bit in ("data-grp", "data-rest", "data-focus", "selectFrom(", "railClosed", "railRestOpen"):
            self.assertIn(bit, block, bit)

    def test_folds_are_remembered(self):
        p = page()
        for key in ("agent-city.railFolded", "agent-city.winFolded", "agent-city.railClosed"):
            self.assertIn(key, p, key)
        for name in ("setRailFolded", "setWinFolded"):
            src = function_source(name) or ""
            self.assertTrue(src, name)
            # the storage may sit in a small helper it calls (e.g. writeStoredBool)
            for callee in set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", src)) - {name}:
                src += function_source(callee) or ""
            self.assertIn("localStorage", src, name)
            self.assertIn("try", src, name + ": storage can throw")
        for sel, fn in (("#rail-fold", "setRailFolded("), ("#rail-tab", "setRailFolded("), ("#win-fold", "setWinFolded("),
                        ("#win-tab", "setWinFolded(")):
            self.assertIn(fn, listener_block(r"\$\('%s'\)" % sel, "click") or "", sel)

    def test_panel_is_one_person(self):
        self.assertNotRegex(function_source("renderWin") or "", r"'wide'", "no wide window")
        self.assertIn("win-tab", function_source("renderWin") or "", "renderWin keeps the tab current")
        src = function_source("renderDetail") or ""
        self.assertNotIn("teamListHtml(", src)
        self.assertNotIn("gov-side", src)

    def test_chip(self):
        src = function_source("renderFollow") or ""
        self.assertIn("follow.on", src)
        self.assertIn("freeCentre(", src)
        self.assertIn("renderFollow(", function_source("frame") or "")
        self.assertIn("stopFollow()", listener_block(r"\$\('#follow-stop'\)", "click") or "")

    def test_view_offset(self):
        src = function_source("updateCamera") or ""
        self.assertIn("freeCentre(", src)
        self.assertIn("setViewOffset(", src)


class TestRailCss(unittest.TestCase):

    def test_phone(self):
        m = media_960()
        for bit in (".rail", ".win", ".drawer-open"):
            self.assertIn(bit, m, bit)
        w = rule(".win", m).replace(" ", "")
        self.assertIn("top:auto", w, "a bottom sheet")
        self.assertIn(".ask-panel", m[m.index(".drawer-open"):] if ".drawer-open" in m else "")


class TestHitArea(unittest.TestCase):

    def test_after_boxes(self):
        c = css()
        for sel in (".bub::after", ".tagl::after", ".qm::after"):
            body = rule(sel, c).replace(" ", "")
            self.assertIn("content:", body, sel)
            self.assertIn("position:absolute", body, sel)
            m = re.search(r"inset:-(\d+(?:\.\d+)?)px", body)
            self.assertIsNotNone(m, sel + " inset:-Npx")
            self.assertGreaterEqual(float(m.group(1)), 6, sel)

    def test_bubble_not_clipped(self):
        self.assertNotIn("overflow:hidden", rule(".bub").replace(" ", ""), "a clipped ::after takes no clicks")


def sim_has(name):
    return re.search(r"(?:function\s+%s\s*\(|(?:const|let)\s+%s\s*=)" % (re.escape(name), re.escape(name)),
                     sim_section()) is not None


INPUT_DRIVER = r"""
const out = { tap: TAP_PX, k: WHEEL_ZOOM };
out.drag = [isDrag(0, 0, TAP_PX - .5, 0), isDrag(0, 0, 0, TAP_PX), isDrag(10, 10, 13, 14), isDrag(0, 0, 30, 0)];
const W = (dx, dy, mode, ctrl) => wheelMove({ deltaX: dx, deltaY: dy, deltaMode: mode, ctrlKey: ctrl }, 900);
out.pan = [W(0, 10, 0, false), W(-6, 4, 0, false), W(0, 3, 1, false), W(2, 1, 2, false)];
out.zoom = [W(0, -10, 0, true), W(0, 20, 0, true), W(0, 40, 0, true), W(0, 1000, 0, true), W(0, -1000, 0, true), W(0, 2, 1, true)];
__out = out;
"""


U6_DRIVER = r"""
const el = { dataset: {} }, el2 = { dataset: {} };
tagPick(el, 'c', 'abc'); tagPick(el2, 'gov');
const cands = [{ pick: { t: 'c', id: 'a' }, x: 100, y: 100 }, { pick: { t: 'c', id: 'b' }, x: 130, y: 100 }, { pick: { t: 'gov' }, x: 400, y: 400 }];
__out = { el: el.dataset, el2: el2.dataset, px: PICK_PX,
  picks: [pickOfTag('c', 'x1'), pickOfTag('rg', 'r1'), pickOfTag('gov', 'T'), pickOfTag('gov', ''), pickOfTag('b', '3'), pickOfTag('', '')],
  near: [nearestPick(112, 100, cands, 28), nearestPick(118, 100, cands, 28), nearestPick(100, 140, cands, 28),
    nearestPick(380, 400, cands, 28), nearestPick(250, 250, cands, 28), nearestPick(0, 0, [], 28)] };
"""


def gov_branch():
    src = function_source("renderDetail") or ""
    i = src.find("selected.t === 'gov') {")
    j = src.find("} else if (!DEMO && citizens.length === 0)", i)
    return src[i:j] if i >= 0 and j > i else ""


CHAT_DRIVER = r"""
const md = s => mdLite(s);
__out = { stick: CHAT_STICK_PX,
  scroll: [chatScroll(null, { height: 900, client: 300 }), chatScroll(null, { height: 200, client: 300 }),
    chatScroll({ top: 570, height: 900, client: 300 }, { height: 1000, client: 300 }),
    chatScroll({ top: 100, height: 900, client: 300 }, { height: 1000, client: 300 }),
    chatScroll({ top: 100, height: 900, client: 300 }, { height: 900, client: 300 })],
  md: {
    comment: md('<!-- buddy: idle, no action -->hello'), open: md('hi <!-- never closed'),
    script: md('<script>alert(1)</script>'), bold: md('**bold** text'), code: md('run `ls -la` now'),
    fence: md('```\n**x** <b>\n```'), ul: md('- a\n- b'), ol: md('1. a\n2. b'),
    table: md('| a | b |\n|---|---|\n| 1 | 2 |'), paras: md('one\n\ntwo'),
    img: md('**<img src=x onerror=alert(1)>**'), link: md('[x](javascript:alert(1))'), quote: md('say "hi" & bye') } };
"""


U10_DRIVER = r"""
const V = __payload.view, A = V.territories[0];
function buildLand(view){ officeState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'idle' }], agents: [] });
apply({ type: 'spawn', id: 'x1', role: 'worker', label: 'worker', task: '登录 API', terr: A.id });
const c = byId('x1'), out = { fresh: Array.isArray(c.acts) };
out.n0 = c.acts.length;
for (const t of ['Edit', 'Edit', 'Read']) apply({ type: 'tool', id: 'x1', tool: t });
out.afterTools = c.acts.map(a => a.text);
apply({ type: 'stuck', id: 'x1', question: '支付超时要不要自动重试？' });
apply({ type: 'tool', id: 'x1', tool: 'Bash' });
apply({ type: 'relay', id: 'x1', to: 'governor', lead: '' });
apply({ type: 'waiting', id: 'x1' });
apply({ type: 'done', id: 'x1' });
apply({ type: 'leave', id: 'x1' });
out.acts = c.acts.map(a => a.text);
out.atOk = c.acts.every(a => typeof a.at === 'number' && a.at > 1.6e9);
out.want = [i18n('hist.started', { task: '登录 API' }), '改代码 · 看文件', i18n('hist.stuck', { text: '支付超时要不要自动重试？' }),
  '跑命令', i18n('hist.toGov'), i18n('hist.waiting'), i18n('hist.done'), i18n('hist.left')];
out.keys = ['hist.started', 'hist.stuck', 'hist.toLead', 'hist.toGov', 'hist.waiting', 'hist.done', 'hist.left', 'hist.title', 'hist.empty', 'chat.task'].map(k => i18n(k, { task: 'T', text: 'X' }));
for (let i = 0; i < 200; i++) actLog(c, 'line ' + i);
out.cap = { n: c.acts.length, keep: ACT_KEEP, last: c.acts[c.acts.length - 1].text, first: c.acts[0].text };
const q = { question: 'q?', answer: 'a!', qa: [], stuck: true, state: 'asking', terr: A.id };
giveAnswer(q);
out.qa = q.qa.map(x => ({ q: x.q, a: x.a, at: typeof x.at === 'number' && x.at > 1.6e9 }));
const p = { acts: [{ at: 10, text: 'a' }, { at: 30, text: 'b' }], qa: [{ q: 'q1', a: 'a1', at: 20 }], stuck: true, question: 'q2' };
out.hist = personHistory(p, [{ kind: 'prompt', text: 't', at: 5 }, { kind: 'reply', text: 'r', at: 25 }, { kind: 'owner', text: 'o', at: 30, state: 'delivered' }])
  .map(x => x.k + ':' + (x.k === 'ask' ? x.q + (x.a === null ? ':open' : ':' + x.a) : x.text));
p.stuck = false;
out.hist2 = personHistory(p, []).map(x => x.k);
out.html = historyHtml([{ k: 'act', at: 1727500000, text: '<b>x</b>' }, { k: 'ask', q: '<q>', a: null, at: 2 },
  { k: 'ask', q: 'q', a: 'a<i>', at: 3 }, { k: 'reply', text: '**bold**', at: 4 }], 'worker', false);
out.empty = historyHtml([], 'w', false);
out.labels = { ask: i18n('label.ask'), answer: i18n('label.answer'), waiting: i18n('label.awaitingAnswer'), empty: i18n('hist.empty') };
__out = out;
"""


def citizen_branch():
    src = function_source("renderDetail") or ""
    i = src.find("if (c) {")
    j = src.find("} else if (selected && selected.t === 'gov') {", i)
    return src[i:j] if i >= 0 and j > i else ""


class TestTapAndTrackpad(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(INPUT_DRIVER, {}, ("TAP_PX", "isDrag", "WHEEL_ZOOM", "wheelMove"))

    def test_tap_threshold(self):
        self.assertTrue(6 <= self.r["tap"] <= 12, self.r["tap"])
        self.assertEqual(self.r["drag"], [False, True, False, True])

    def test_two_finger_swipe_pans_with_the_fingers(self):
        p = self.r["pan"]
        for got, want in zip(p, [[0, -10], [-6, -4], [0, -48], [1800, -900]]):  # city-ux2 V2: X no longer negated
            self.assertIn("pan", got)
            self.assertNotIn("zoom", got)
            self.assertAlmostEqual(got["pan"][0], want[0], places=9)
            self.assertAlmostEqual(got["pan"][1], want[1], places=9)

    def test_pinch_zooms_proportionally_without_jumps(self):
        z = [x.get("zoom") for x in self.r["zoom"]]
        self.assertEqual(self.r["k"], .01)
        self.assertAlmostEqual(z[0], math.exp(-.1), places=9, msg="pinch out (deltaY < 0) zooms in: a smaller distance")
        self.assertAlmostEqual(z[1], math.exp(.2), places=9)
        self.assertAlmostEqual(z[2], z[1] ** 2, places=9, msg="twice the fingers, twice the zoom (in log)")
        self.assertAlmostEqual(z[3], math.exp(.5), places=9, msg="one event never jumps: clamped")
        self.assertAlmostEqual(z[4], math.exp(-.5), places=9)
        self.assertAlmostEqual(z[5], math.exp(.32), places=9, msg="deltaMode 1 = 16 px a line")
        for x in self.r["zoom"]:
            self.assertNotIn("pan", x)


class TestTagPicks(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(U6_DRIVER, {}, ("tagPick", "pickOfTag", "PICK_PX", "nearestPick"))

    def test_tag_pick(self):
        self.assertEqual(self.r["el"], {"pickT": "c", "pickId": "abc"})
        self.assertEqual(self.r["el2"], {"pickT": "gov", "pickId": ""})

    def test_pick_of_tag(self):
        self.assertEqual(self.r["picks"], [{"t": "c", "id": "x1"}, None, {"t": "gov", "terr": "T"},
                                           {"t": "gov"}, None, None])

    def test_nearest_pick(self):
        self.assertTrue(20 <= self.r["px"] <= 40, self.r["px"])
        self.assertEqual(self.r["near"], [{"t": "c", "id": "a"}, {"t": "c", "id": "b"}, None, {"t": "gov"}, None, None])


class TestGovernorWindow(unittest.TestCase):

    def test_explainer_and_counters_gone(self):
        text = page()
        for key in ("gov.presentNote", "dt.dispatched", "dt.answered"):
            self.assertEqual(text_keys(key), 0, key)
        self.assertNotIn("总督就是你正在聊的主对话", text)
        self.assertNotIn("The governor is the main conversation you are talking to", text)
        self.assertEqual(text_keys("gov.awayNote"), 2, "the away note stays")
        branch = gov_branch()
        self.assertTrue(branch, "renderDetail's governor branch not found")
        self.assertNotIn("d-tools", branch)
        self.assertNotIn("presentNote", branch)

    def test_one_column_no_team_list(self):
        # city-ux2 v2 (owner 2026-09-29): the window is the right-docked message panel for one person;
        # the rail is the team list, so no second list and no two-column window any more.
        branch = gov_branch()
        self.assertIn('class="p-head"', branch)
        self.assertIn("chatSectionHtml(", branch, "the conversation")
        for gone in ("gov-side", "teamListHtml(", "gov-cols"):
            self.assertNotIn(gone, branch, gone)
        self.assertNotRegex(function_source("renderWin") or "", r"classList\.toggle\(\s*'wide'", "no wide window")


class TestChatLog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(CHAT_DRIVER, {}, ("CHAT_STICK_PX", "chatScroll", "mdLite"))

    def test_chat_scroll(self):
        self.assertEqual(self.r["stick"], 40)
        self.assertEqual(self.r["scroll"], [{"top": 600, "chip": False}, {"top": 0, "chip": False},
                                            {"top": 700, "chip": False}, {"top": 100, "chip": True},
                                            {"top": 100, "chip": False}])

    def test_comments_are_hidden(self):
        m = self.r["md"]
        self.assertNotIn("buddy", m["comment"])
        self.assertIn("hello", m["comment"])
        self.assertNotIn("never closed", m["open"])
        self.assertIn("hi", m["open"])

    def test_no_raw_html_ever(self):
        m = self.r["md"]
        self.assertNotIn("<script", m["script"])
        self.assertIn("&lt;script&gt;", m["script"])
        self.assertNotIn("<img", m["img"])
        self.assertIn("&lt;img", m["img"])
        self.assertNotIn("<a", m["link"])
        self.assertNotIn("href", m["link"])
        self.assertIn("&amp;", m["quote"])
        self.assertIn("&quot;hi&quot;", m["quote"])

    def test_simple_markdown(self):
        m = self.r["md"]
        self.assertRegex(m["bold"], r"<(b|strong)>bold</(b|strong)>")
        self.assertIn("<code>ls -la</code>", m["code"])
        self.assertIn("<pre><code>", m["fence"])
        self.assertIn("**x** &lt;b&gt;", m["fence"], "nothing formatted inside a fence")
        self.assertRegex(m["ul"], r"<ul><li>a</li><li>b</li></ul>")
        self.assertRegex(m["ol"], r"<ol><li>a</li><li>b</li></ol>")
        self.assertIn("<table", m["table"])
        self.assertIn("<th>a</th>", m["table"])
        self.assertIn("<td>2</td>", m["table"])
        self.assertNotIn("---", m["table"])
        self.assertEqual(len(re.findall(r"<p>", m["paras"])), 2)


class TestChatWiring(unittest.TestCase):

    def test_chat_uses_mdlite(self):
        src = function_source("chatHtml") or ""
        self.assertIn("mdLite(", src)
        self.assertIn('class="md"', src)
        self.assertTrue(sim_has("mdLite"), "mdLite lives in the sim section (no three.js, no DOM)")
        self.assertTrue(rule(".md table") or rule(".md th"), "CSS for markdown tables")
        self.assertTrue(rule(".md code") or rule(".md pre"), "CSS for markdown code")

    def test_no_forced_jump_to_the_bottom(self):
        src = function_source("renderDetail") or ""
        self.assertIn("chatScroll(", src)
        self.assertNotRegex(src, r"ol\.innerHTML\s*=\s*html;\s*ol\.scrollTop\s*=\s*ol\.scrollHeight",
                            "the old unconditional jump to the bottom is gone")

    def test_chip_and_place_survive_refreshes(self):
        """Headless E2E: the chip showed for one refresh and was hidden by the next; a rebuilt card (the person's
        state changed) threw the owner back to the bottom. The chip stays until clicked or the owner is back at
        the bottom; a rebuild of the SAME chat keeps its scroll place (prev = the state saved before the rebuild)."""
        src = function_source("renderDetail") or ""
        self.assertNotRegex(src, r"hidden\s*=\s*!\s*res\.chip", "a later refresh must not hide the chip again")
        self.assertNotRegex(src, r"rebuilt\s*\?\s*null", "a rebuild of the same chat keeps its place")

    def test_new_messages_chip(self):
        for key in ("chat.new",):
            self.assertEqual(text_keys(key), 2, key)
        self.assertIn('class="newmsg"', page())
        self.assertTrue(rule(".newmsg"), "CSS for the chip")


class TestPersonHistory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(U10_DRIVER, {"view": two_territory_view()},
                        ("apply", "byId", "officeState", "i18n", "actLog", "actTool", "ACT_KEEP", "personHistory",
                         "historyHtml", "giveAnswer"))

    def test_activity_lines_from_live_events(self):
        self.assertTrue(self.r["fresh"], "newCitizen gives c.acts = []")
        self.assertEqual(self.r["n0"], 1, "spawn -> one started line")
        self.assertEqual(self.r["afterTools"], self.r["want"][:2], "tools in a row share one line")
        self.assertEqual(self.r["acts"], self.r["want"])
        self.assertTrue(self.r["atOk"], "every line has at = Date.now() / 1000")

    def test_texts_exist(self):
        for got in self.r["keys"]:
            self.assertFalse(got.startswith(("hist.", "hint.", "chat.")), "missing TEXT key: " + got)

    def test_capped(self):
        c = self.r["cap"]
        self.assertEqual(c["keep"], 60)
        self.assertEqual(c["n"], 60)
        self.assertEqual(c["last"], "line 199")
        self.assertEqual(c["first"], "line 140")

    def test_answers_are_dated(self):
        self.assertEqual(self.r["qa"], [{"q": "q?", "a": "a!", "at": True}])

    def test_one_history_oldest_first(self):
        self.assertEqual(self.r["hist"], ["prompt:t", "act:a", "ask:q1:a1", "reply:r", "act:b", "owner:o", "ask:q2:open"])
        self.assertEqual(self.r["hist2"], ["act", "ask", "act"])

    def test_history_rows(self):
        h, L = self.r["html"], self.r["labels"]
        self.assertIn('<li class="act">', h)
        self.assertIn("<time>", h)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", h)
        self.assertNotIn("<b>x</b>", h)
        self.assertEqual(h.count('<li class="qa"'), 2)
        self.assertIn("&lt;q&gt;", h)
        self.assertIn(L["waiting"], h)
        self.assertIn("a&lt;i&gt;", h)
        self.assertIn('class="msg"', h)
        self.assertRegex(h, r"<(b|strong)>bold</(b|strong)>")
        self.assertIn("msg-empty", self.r["empty"])
        self.assertIn(L["empty"], self.r["empty"])


class TestPersonWindow(unittest.TestCase):

    def test_citizen_one_column(self):
        # city-ux2 v2: the message panel shows only this person -- head, history, reply box / read-only
        b = citizen_branch()
        self.assertTrue(b, "renderDetail's citizen branch not found")
        self.assertIn('class="p-head"', b)
        self.assertIn("hist.title", b)
        for gone in ("gov-side", "teamListHtml(", "gov-cols"):
            self.assertNotIn(gone, b, gone)
        src = function_source("renderDetail") or ""
        self.assertIn("personHistory(", src)
        self.assertIn("historyHtml(", src)
        self.assertNotIn("teamListHtml(", src, "no team list anywhere in the panel")

    def test_history_list_is_refreshed(self):
        src = function_source("renderDetail") or ""
        tail = src[src.rfind("if (chatTo)"):] if "if (chatTo)" in src else src
        self.assertIn("historyHtml(", tail, "the per-call refresh keeps the history current")


class TestTeamWindowHead(unittest.TestCase):

    def test_title_is_the_person(self):
        # city-ux2 v2: the message panel is one person's, so its title is that person, not the team
        src = function_source("winTitle") or ""
        self.assertNotIn("team.title", src)
        self.assertIn("nameOf(", src)

    def test_governor_head_facts(self):
        branch = gov_branch()
        i = branch.find('class="p-head"')
        self.assertGreater(i, 0)
        head = branch[i:branch.find("hist.title", i) if "hist.title" in branch[i:] else i + 1500]
        self.assertIn("gov.ownTag", head, "repo · main manager · 主对话 under the name")
        # city-status: the list row takes class + words from govRowStatus (govRowText is its text)
        self.assertRegex(head, r"govRow(Status|Text)\(", "the same state words as its list row")


class TestNoToolCounters(unittest.TestCase):

    def test_gone(self):
        src = function_source("renderDetail") or ""
        self.assertNotIn("d-tools", src)
        self.assertNotRegex(src, r"\[\s*'Edit'\s*,\s*'Write'\s*,\s*'Bash'\s*,\s*'Read'\s*\]")


if __name__ == "__main__":
    unittest.main()
