"""Shared test helpers (test-slim): no tests here."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import json
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = os.path.dirname(HERE)
if os.path.join(ROOT, "bin") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "bin"))
import agent_city as ac  # noqa: E402,F401


PAGE = os.path.join(ROOT, "bin", "agent-city.html")


def page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


def sim_section():
    """The page script from 'use strict' up to the 3D view comment."""
    text = page()
    m = re.search(r"<script>\s*\(\(\) => \{\s*'use strict';", text)
    if not m:
        raise AssertionError("inline script with 'use strict' not found")
    start = m.end()
    end = text.find("3D view.", start)
    if end < 0:
        raise AssertionError("the '3D view.' comment not found")
    end = text.rfind("/*", start, end)
    return "'use strict';\n" + text[start:end]


# city-office (2026-11-25): the 3D part was rebuilt from the approved prototype. The old per-person and
# per-governor draw functions became syncFigs (meshes, pose, facing), pinOv (head tags and bubbles) and govFigsHere
# (the area managers of the floor in view). Old tests that read the old names read these instead.
OFFICE_DRAW = {"updatePerson": ("syncFigs", "pinOv", "poseFig"),
               "updateGovernor": ("govFigsHere", "syncFigs", "pinOv"),
               "updateGovPool": ("govFigsHere", "syncFigs", "pinOv")}


def _function_source_one(name):
    text = page()
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


def function_source(name):
    if name in OFFICE_DRAW:
        parts = [_function_source_one(n) for n in OFFICE_DRAW[name]]
        return "\n".join(p for p in parts if p) or None
    return _function_source_one(name)


# A stub browser: every unknown name becomes a harmless "anything" (callable,
# any property, truthy), except REQUIRED names, which must be in the page.
SIM_JS = r"""
const fs = require('fs'), vm = require('vm');
const { script, driver, payload, required } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
function anything(){
  const f = function(){ return P; };
  const P = new Proxy(f, {
    get(t, k){ if (k === Symbol.toPrimitive) return () => ''; if (k === 'then') return undefined;
      if (k === 'length') return 0; if (k === Symbol.iterator) return function*(){}; return P; },
    set(){ return true; }, apply(){ return P; }, construct(){ return P; }, has(){ return true; } });
  return P;
}
const base = () => ({ console, Math, JSON, Date, Map, Set, WeakMap, Array, Object, Number, String, Boolean,
  Promise, Symbol, Error, RegExp, parseInt, parseFloat, isFinite, isNaN, Infinity, NaN, undefined,
  setTimeout: () => 0, clearTimeout(){}, setInterval: () => 0, clearInterval(){}, requestAnimationFrame(){},
  cancelAnimationFrame(){}, performance: { now: () => 0 }, document: anything(), window: anything(),
  navigator: anything(), localStorage: { getItem(){ return null; }, setItem(){}, removeItem(){} },
  location: { hash: '', protocol: 'http:', search: '', href: 'http://127.0.0.1/' },
  matchMedia: () => ({ matches: false, addEventListener(){}, addListener(){} }), addEventListener(){},
  THREE: anything(), EventSource: function(){ return anything(); }, fetch: () => new Promise(() => {}),
  devicePixelRatio: 1, innerWidth: 1200, innerHeight: 800 });
const stubs = new Set();
for (let tries = 0; tries < 150; tries++) {
  const box = base();
  for (const s of stubs) box[s] = anything();
  box.__payload = payload; box.__out = null;
  vm.createContext(box);
  try {
    vm.runInContext(script + '\n;\n' + driver, box, { timeout: 60000 });
    require(`fs`).writeSync(1, JSON.stringify(box.__out)); process.exit(0);
  } catch (e) {
    const m = /^(\S+) is not defined$/.exec((e && e.message) || '');
    if (e && e.name === 'ReferenceError' && m && !required.includes(m[1]) && !stubs.has(m[1])) { stubs.add(m[1]); continue; }
    require(`fs`).writeSync(1, JSON.stringify({ fatal: String(e && e.stack || e).slice(0, 2500) })); process.exit(0);
  }
}
require(`fs`).writeSync(1, JSON.stringify({ fatal: 'too many unknown names: ' + [...stubs].join(' ') }));
"""


def run_sim(driver, payload, required=()):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "sim.js")
        data = os.path.join(tmp, "data.json")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(SIM_JS)
        with open(data, "w", encoding="utf-8") as fh:
            json.dump({"script": sim_section(), "driver": driver, "payload": payload,
                       "required": list(required)}, fh)
        result = subprocess.run([node, script, data], capture_output=True, text=True,
                                timeout=120, stdin=subprocess.DEVNULL)
    if result.returncode != 0 or not result.stdout.strip():
        raise AssertionError("sim harness failed:\n" + result.stderr[-3000:])
    out = json.loads(result.stdout)
    if isinstance(out, dict) and "fatal" in out:
        raise AssertionError("sim harness crashed: " + out["fatal"])
    return out


def plan_views():
    """city-office: one office view of one floor (was one island view per plan)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cityoffice import office_view_of
    return {"office": office_view_of(("/work/p0-0/app/.git", "app0"))}


REQUIRED = ("officeState", "governorAt", "apply", "update", "citizens", "buildings", "byId", "citizenStatus")


def inline_script():
    return "\n".join(re.findall(r"<script>(.*?)</script>", page(), re.S))


def models():
    block = re.search(r"const MODELS = \[(.*?)\];", inline_script(), re.S)
    return re.findall(r"'([a-z][a-z\-]*/[A-Za-z0-9_\-]+)'", block.group(1)) if block else []


def markup():
    """The page without its <script> and <style> blocks."""
    return re.sub(r"<script[^>]*>.*?</script>|<style>.*?</style>", "", page(), flags=re.S)


def style():
    return "\n".join(re.findall(r"<style>(.*?)</style>", page(), re.S))


def _script_function_source_one(name):
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


def script_function_source(name):
    if name in OFFICE_DRAW:
        parts = [_script_function_source_one(n) for n in OFFICE_DRAW[name]]
        return "\n".join(p for p in parts if p) or None
    return _script_function_source_one(name)


def constants_prelude():
    """Every top-level `const NAME = <number or string>;` of the script."""
    out = []
    for name, value in re.findall(r"^const ([A-Z][A-Z0-9_]*) = ([^;\n]+);\s*$", inline_script(), re.M):
        if re.fullmatch(r"(?:[\d.\s/*+\-()]|Math\.PI)+|'[^'\\]*'", value.strip()):
            out.append("var %s = %s;" % (name, value.strip()))
    # idea-city C1: the page's texts (const TEXT = {zh, en}) and i18n(key, vars), so a harness that runs a
    # page function which shows text gets the same words the page shows (LANG is a plain const above)
    lit = const_object("TEXT")
    if lit:
        out.append("var TEXT = %s;" % lit)
    src = script_function_source("i18n")
    if src:
        out.append(src)
    return "\n".join(out)


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


_ZH = {}


def text_zh():
    """idea-city C1: the page's zh texts (const TEXT = {zh, en}), {} before the page has them."""
    lit = const_object("TEXT")
    if not lit:
        return {}
    if lit not in _ZH:
        _ZH.clear()
        _ZH[lit] = (js_value(lit) or {}).get("zh", {})
    return _ZH[lit]


def zh_resolved(src):
    """idea-city C1: SRC as a reader of the zh page sees it: every i18n('key' call shows its zh text in
    place of the key, and every data-t="key" / data-t-aria="key" / data-t-title="key" attribute becomes
    the zh text / aria-label / title -- so a test that looks for a Chinese word in the page source still
    finds it after the texts moved into TEXT. Before that (no TEXT) SRC comes back unchanged."""
    zh = text_zh()
    if not zh or not src:
        return src
    q = lambda k: zh.get(k, k).replace("'", "\\'")
    src = re.sub(r"\bi18n\((['\"])([\w.\-]+)\1", lambda m: "i18n('%s'" % q(m.group(2)), src)
    src = re.sub(r'data-t-aria="([\w.\-]+)"', lambda m: 'aria-label="%s"' % zh.get(m.group(1), m.group(1)), src)
    src = re.sub(r'data-t-title="([\w.\-]+)"', lambda m: 'title="%s"' % zh.get(m.group(1), m.group(1)), src)
    return re.sub(r'\sdata-t="([\w.\-]+)"([^>]*)>', lambda m: '%s>%s' % (m.group(2), zh.get(m.group(1), m.group(1))), src)


def js_value(literal):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not installed")
    result = subprocess.run([node, "-e", "require(`fs`).writeSync(1, JSON.stringify(%s))" % literal],
                            capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise AssertionError(result.stderr[-2000:])
    return json.loads(result.stdout)


def page_fns(*names, optional=()):
    fns = []
    for name in names:
        src = script_function_source(name)
        if src is None:
            raise AssertionError("function %s(...) not found in the page script" % name)
        fns.append(src)
    for name in optional:
        src = script_function_source(name)
        if src:
            fns.append(src)
    # cloud-city-1: some page functions return early when CLOUD (the page on Cloudflare,
    # view only). A harness runs the LOCAL page's functions, where CLOUD is false.
    # The page's random is `let rand = Math.random` (seedable); a harness gets the unseeded one.
    return "var CLOUD = false;\nvar rand = Math.random;\n" + "\n".join(fns)


def consts(*names):
    out = []
    for name in names:
        lit = const_object(name)
        if lit is None:
            raise AssertionError("const %s = {...}; not found in the page script" % name)
        out.append("var %s = %s;" % (name, lit))
    return "\n".join(out)


def listener_block(target_regex, event):
    """Every `<target>.addEventListener('<event>', ...)` call in the page, each up to its matching ')',
    joined (None when there is none)."""
    text, out = page(), []
    for m in re.finditer(r"(?<![\w$])%s\.addEventListener\(\s*'%s'" % (target_regex, re.escape(event)), text):
        depth = 0
        for j in range(m.start() + m.group(0).index("addEventListener(") + len("addEventListener"), len(text)):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    out.append(text[m.start():j + 1])
                    break
    return "\n".join(out) if out else None


def css():
    text = page()
    return re.sub(r"/\*.*?\*/", "", text[text.index("<style>"):text.index("</style>")], flags=re.S)


def media_960():
    c = css()
    i = c.index("@media (max-width: 960px)")
    depth = 0
    for j in range(c.index("{", i), len(c)):
        if c[j] == "{":
            depth += 1
        elif c[j] == "}":
            depth -= 1
            if depth == 0:
                return c[i:j + 1]
    return ""


def rule(sel, text=None):
    """Every declaration block whose selector list names exactly this selector, joined."""
    text = css() if text is None else text
    out = []
    for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", text):
        if sel in [x.strip() for x in m.group(1).split(",")]:
            out.append(m.group(2))
    return ";".join(out)


def text_keys(key):
    return len(re.findall(r"'%s'\s*:" % re.escape(key), page()))


A_REPO, B_REPO = "/work/fa/app/.git", "/work/fb/app/.git"


TA, TB = ac.territory_id(A_REPO), ac.territory_id(B_REPO)


def two_territory_view():
    """city-office: A and B as two floors (A 1F, B 2F) of the office view."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cityoffice import office_view_of
    return office_view_of((A_REPO, "app"), (B_REPO, "app"))


POLISH_A_REPO, POLISH_B_REPO = "/work/repoA/.git", "/work/repoB/.git"


POLISH_TA, POLISH_TB = ac.territory_id(POLISH_A_REPO), ac.territory_id(POLISH_B_REPO)


def named_view():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cityoffice import office_view_of
    return office_view_of((POLISH_A_REPO, "repoA"), (POLISH_B_REPO, "repoB"))


ASK_Q = {"id": "q1", "agent": "gov", "terr": POLISH_TA, "label": "", "task": "", "repo": POLISH_A_REPO, "kind": "question",
         "phase": "owner", "why": "no-governor", "wait": 60, "left": 0, "tool": "AskUserQuestion",
         "what": "red or blue?", "at": 1000,
         "questions": [{"question": "red or blue?", "header": "c", "multiSelect": False,
                        "options": [{"label": "red", "description": ""}, {"label": "blue", "description": ""}]}]}
