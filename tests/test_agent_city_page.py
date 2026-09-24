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
    Loads three.js and its loaders from the server, in this order:
      <script src="assets/vendor/three.min.js">
      <script src="assets/vendor/GLTFLoader.js">
      <script src="assets/vendor/SkeletonUtils.js">
    const ASSET = 'assets/' and a const MODELS = [...] list of '<pack>/<name>'
    entries; each is loaded from ASSET + entry + '.glb'.
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
      or the var(--sky) background; the island sits on the page.
    Camera: new THREE.PerspectiveCamera(FOV, ...) with const FOV = 40, no
      OrthographicCamera. cam = {az, el, dist, tx, tz} in scene coordinates
      (world group offset -6, -5; the town hall centre is scene 0, 1).
      Constants: EL_MIN = 15°, EL_MAX = 60°, EL_DEFAULT = 30° (radians,
      Math.PI allowed), DIST_MIN <= 3.5 (street level), DIST_DEFAULT,
      TARGET_Y, CAM_CLEAR, LIFT_MAX = 10°, FADE_OPACITY = .3.
      distMax(): the zoom-out limit for the stage size W x H and the current
      tilt, the same from every angle az (so auto-rotation never changes it).
      At distMax() the whole island (scene x -6..6, z -7..7, y -1.05..0)
      stays fully inside the stage, fills about 80% of it on its tighter
      side at the widest angle (.7 to .9), and sits in the middle. May use
      only W, H, cam.el, FOV, DIST_MIN, Math, clamp, and the helpers
      islandSpread and centreHeight if present. updateCamera() keeps
      cam.dist <= distMax(); tilting while fully zoomed out stays fully out.
      camTarget() -> [x, y, z]: the point the camera looks at: (tx,
      TARGET_Y, tz) up to dist 12, then drawn smoothly to the island's middle
      (x 0, z 0, at the height that centres the island), reached at
      distMax().
      resetCam(): tilt 30°, target within 3.5 of the town hall, dist <= 14,
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
      fadeables: top-level array of {g, tiles}: the town hall and its flag
      (tiles '-1,0' '0,0' '-1,1' '0,1', pushed in buildIsland), every
      building (its tile, pushed in makeBuilding, removed in removeBuilding).
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
      zero agents runs at FRAME_MS like demo); false when nothing moves,
      within 10 s of a touch, or under reduced motion.
      autoRotate(now, dt), called from frame(), turns only cam.az, one full
      turn per 300 s; it does nothing when RM (reduced motion), while drag or
      pinch is set, or within 10 s (10000 ms) of lastTouch. lastTouch =
      performance.now() in camChanged and in the canvas pointerdown handler.
      No button for it.
    Right column <aside class="panel" id="panel"> holds exactly three cards,
      default order detail, citizens, log:
        <section class="card" data-card="detail|citizens|log">
          <h2 class="card-head"><button type="button" aria-expanded="true"
            aria-controls="<body id>">… 详情 | 市民 | 动态 …</button></h2>
          one element with class card-body: #detail, #roster, #log
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
    The "?" panel: <div class="ask" id="ask" role="dialog"
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
      oldest. Phone: the @media (max-width: 960px) block has an .ask rule.

  bin/agent-city-assets/
    vendor/three.min.js, vendor/GLTFLoader.js, vendor/SkeletonUtils.js
      (three.js r128, MIT, the licence header kept)
    <pack>/<name>.glb for every MODELS entry, and nothing unused
    <pack>/Textures/*.png for every texture those models name
    <pack>/License.txt for every pack, each saying CC0
    Everything together at most 6 MB.
"""

import json
import os
import re
import shutil
import struct
import subprocess
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
    return re.findall(r"'([a-z]+/[A-Za-z0-9_\-]+)'", block.group(1)) if block else []


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
        self.assertEqual(srcs, ["assets/vendor/three.min.js", "assets/vendor/GLTFLoader.js",
                                "assets/vendor/SkeletonUtils.js"])

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
        for kind in ("snapshot", "spawn", "tool", "stuck", "answer", "done", "leave", "gov"):
            with self.subTest(kind=kind):
                self.assertRegex(text, r"case\s+'%s'\s*:" % kind)

    def test_role_other_exists(self):
        self.assertRegex(inline_script(), r"['\"]?other['\"]?\s*:\s*\{")

    def test_assets_come_from_the_server(self):
        self.assertIn("const ASSET = 'assets/'", inline_script())
        self.assertGreater(len(models()), 20)


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

    def test_size_budget(self):
        total = sum(os.path.getsize(os.path.join(folder, name))
                    for folder, _, files in os.walk(ASSETS) for name in files)
        self.assertLessEqual(total, 6 * 1024 * 1024, "assets are %.1f MB" % (total / 1048576))


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
  const box = ctx({ cam: { az: 0, el: 0, dist: 1, tx: -5, tz: -5 }, W: 1200, H: 800 });
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
// zoom out: the whole island fills about 80% of the stage and sits in the middle
{
  const camera = fakeCamera();
  const box = ctx({ camera, cam: { az: 0, el: .5, dist: 9, tx: 0, tz: 0 }, W: 874, H: 710, clamp: clampFn,
    drag: null, pinch: null, camLiftNow: 0, fadeables: [] });
  box.heightAt = () => 0;
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]], dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const norm = a => { const l = Math.hypot(...a); return a.map(v => v / l); };
  const fit = (W, H, az, el) => {
    box.W = W; box.H = H;
    Object.assign(box.cam, { az, el: el === undefined ? box.EL_DEFAULT : el, tx: .3, tz: 2.8 });
    box.cam.dist = box.distMax();
    for (let i = 0; i < 40; i++) box.updateCamera();
    const P = [camera.position.x, camera.position.y, camera.position.z], L = camera.look;
    const f = norm(sub(L, P)), r = norm(cross(f, [0, 1, 0])), u = cross(r, f);
    const t = Math.tan(box.FOV * Math.PI / 360), a = W / H;
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    for (const x of [-6, 6]) for (const z of [-7, 7]) for (const y of [-1.05, 0]) {
      const d = sub([x, y, z], P), zc = dot(d, f), nx = dot(d, r) / (zc * t * a), ny = dot(d, u) / (zc * t);
      x0 = Math.min(x0, nx); x1 = Math.max(x1, nx); y0 = Math.min(y0, ny); y1 = Math.max(y1, ny);
    }
    const dm = box.cam.dist;
    box.cam.az = az + 1.3; box.W = W * (1 + 1e-9); const dm2 = box.distMax(); box.cam.az = az; box.W = W;
    return { dist: dm, sameFromAnyAngle: Math.abs(dm2 - dm) < 1e-3, look: [L[0], L[2]], w: (x1 - x0) / 2, h: (y1 - y0) / 2,
      cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, edge: Math.max(-x0, x1, -y0, y1) };
  };
  const d = Math.PI / 180;
  out.zoomOut = { wide: fit(874, 710, Math.PI / 4), phone: fit(358, 394, Math.PI / 4), wideSide: fit(874, 710, 0),
    broad: fit(1400, 700, Math.PI / 4), wideSteep: fit(874, 710, Math.PI / 4, 60 * d), wideLow: fit(874, 710, Math.PI / 4, 15 * d),
    broadSteep: fit(1400, 700, Math.PI / 4, 60 * d), phoneSide: fit(358, 394, 0, 45 * d) };
  // tilting while fully zoomed out stays fully out; zooming past the limit is clamped
  box.W = 874; box.H = 710;
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
        for name in ("aroundH", "autoRotating", "fadedOf", "islandSpread", "centreHeight"):
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
        self.assertFalse(b["touched"], "right after a touch, with nothing moving, idle rate is fine")
        self.assertFalse(b["reduced"], "reduced motion: no rotation, idle rate")

    def test_edge_cliff_tops_sit_behind_path_and_river_floors(self):
        text = inline_script()
        self.assertRegex(text, r"instanced\('cliff_block_rock'[^\n]*\bbehind: true")
        body = function_source("instanced") or ""
        self.assertRegex(body, r"o\.behind")
        self.assertRegex(body, r"polygonOffset = true")
        factor = re.search(r"polygonOffsetFactor = ([\d.]+)", body)
        self.assertIsNotNone(factor)
        self.assertGreaterEqual(float(factor.group(1)), 1)

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
        self.assertRegex(function_source("buildIsland") or "", r"fadeables\.push\(")
        self.assertIn("'-1,0'", function_source("buildIsland") or "")
        self.assertRegex(function_source("makeBuilding") or "", r"fadeables\.push\(")
        self.assertIn("fadeables", function_source("removeBuilding") or "")

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
                self.assertLessEqual(((v["tx"] - 0) ** 2 + (v["tz"] - 1) ** 2) ** .5, 3.5,
                                     "look at the town hall (scene 0, 1)")
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
        for needle in ("$('#zin')", "$('#zout')", "canvas.addEventListener('wheel'"):
            with self.subTest(control=needle):
                line = next(l for l in text.splitlines() if needle in l)
                self.assertIn("DIST_MIN, distMax()", line)
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

    def test_auto_rotation_waits_10s_after_a_touch(self):
        rot = unit_results()["rot"]
        self.assertEqual(rot["touched5s"], 0)
        self.assertNotEqual(rot["touched11s"], 0)

    def test_auto_rotation_stops_while_dragging_or_zooming(self):
        rot = unit_results()["rot"]
        self.assertEqual(rot["dragging"], 0)
        self.assertEqual(rot["pinching"], 0)

    def test_no_auto_rotation_for_reduced_motion(self):
        self.assertEqual(unit_results()["rot"]["reduced"], 0)

    def test_frame_calls_auto_rotate(self):
        self.assertRegex(function_source("frame") or "", r"\bautoRotate\(")

    def test_touch_and_zoom_reset_the_timer(self):
        text = inline_script()
        cam_changed = re.search(r"const camChanged = \([^)]*\) => \{[^}]*\}", text)
        self.assertIsNotNone(cam_changed, "camChanged not found")
        self.assertRegex(cam_changed.group(0), r"lastTouch = performance\.now\(\)")
        down = re.search(r"canvas\.addEventListener\('pointerdown', e => \{(.*?)\n\}\);", text, re.S)
        self.assertIsNotNone(down, "canvas pointerdown handler not found")
        self.assertRegex(down.group(1), r"lastTouch = performance\.now\(\)")


class TestCardsMarkup(unittest.TestCase):
    def test_three_cards_in_default_order(self):
        panel = re.search(r'<aside class="panel" id="panel"[^>]*>(.*?)</aside>', markup(), re.S)
        self.assertIsNotNone(panel, '<aside class="panel" id="panel"> not found')
        self.assertEqual(re.findall(r'data-card="([\w-]+)"', panel.group(1)), ["detail", "citizens", "log"])
        self.assertEqual(panel.group(1).count("<section"), 3)

    def test_each_card_has_a_toggle_header_and_one_body(self):
        want = {"detail": ("详情", "detail"), "citizens": ("市民", "roster"), "log": ("动态", "log")}
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
        for attr in ('class="ask"', 'role="dialog"', 'aria-labelledby="ask-title"', "hidden"):
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
        self.assertIn(".ask", media_block("@media (max-width: 960px)"))

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


if __name__ == "__main__":
    unittest.main()
