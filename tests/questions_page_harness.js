// questions_page_harness.js - runs the inline script of a page written by
// `agent-file.sh questions --page` in node, on a small stub DOM, with a fake
// `window.claude.use`. Used by tests/test_agent_questions.py (TestPageInNode).
// Not a browser check: the main manager still opens the page in a browser.
//
//   node questions_page_harness.js <page.html> '<scenario JSON>'
//
// Scenario: {"db": "on" | "off" | "ro",          off = use("db") resolves null
//            "saved": {"<id>": {pick, option, note, answeredAt}},   docs already in answers/
//            "actions": [["pick", n, "A"], ["note", n, "text"], ["all-rec"], ["clear"],
//                        ["copy"], ["blur", n]]}
// Prints one JSON object: count (text of #count), done (numbers of the cards
// with class "done"), checked ({n: letter} of aria-checked="true" options),
// disabled (true when the first option button is disabled), writesOnLoad,
// writes ([{op: "set"|"delete", id, body}]), nodb and ro (the banners shown),
// copy (the #copybox value), h1, toast.
//
// The stub DOM has: document.getElementById / createElement / createTextNode /
// querySelector / querySelectorAll (simple selectors: tag, #id, .class,
// [attr] and [attr="v"], compounds of those, and descendant chains),
// title, documentElement.lang, body; on elements: appendChild, append,
// insertBefore, replaceChild, removeChild, remove, children, firstChild,
// lastChild, parentNode, textContent, innerHTML = "" (clearing only), id,
// className, classList (add, remove, toggle, contains), setAttribute,
// getAttribute, removeAttribute, hasAttribute, dataset, hidden, disabled,
// value, type, placeholder, readOnly, title, style, focus, select, blur,
// addEventListener, onclick, scrollIntoView; window.scrollTo, window.claude (and a
// bare claude), setTimeout, clearTimeout, setInterval, clearInterval on a virtual
// clock (1 s per step), document.execCommand("copy") -> true,
// navigator without clipboard, no localStorage.
"use strict";
const fs = require("fs");

const html = fs.readFileSync(process.argv[2], "utf8");
const scenario = JSON.parse(process.argv[3] || "{}");

// ---- the page's own parts
const jsonBlocks = {};
html.replace(/<script type="application\/json" id="([^"]+)">([\s\S]*?)<\/script>/g, (_, id, t) => { jsonBlocks[id] = t; });
const scripts = [];
html.replace(/<script>([\s\S]*?)<\/script>/g, (_, t) => { scripts.push(t); });
const staticIds = new Set();
html.replace(/\sid="([^"]+)"/g, (_, id) => { staticIds.add(id); });

// ---- stub DOM
class El {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase(); this.nodeType = tag === "#text" ? 3 : 1;
    this.children = []; this.attrs = {}; this.parentNode = null; this._text = "";
    this.listeners = {}; this.hidden = false; this.disabled = false; this.value = "";
    this.style = {}; this.type = ""; this.placeholder = ""; this.readOnly = false; this.title = "";
    const self = this;
    this.classList = {
      add(...c) { c.forEach(x => { if (!self.classes().includes(x)) self.className = (self.className + " " + x).trim(); }); },
      remove(...c) { self.className = self.classes().filter(x => !c.includes(x)).join(" "); },
      toggle(c, on) { const has = self.classes().includes(c); const want = on === undefined ? !has : !!on; want ? this.add(c) : this.remove(c); return want; },
      contains(c) { return self.classes().includes(c); },
    };
    this.dataset = new Proxy({}, {
      get: (_, k) => self.attrs["data-" + String(k).replace(/[A-Z]/g, m => "-" + m.toLowerCase())],
      set: (_, k, v) => { self.attrs["data-" + String(k).replace(/[A-Z]/g, m => "-" + m.toLowerCase())] = String(v); return true; },
    });
  }
  get className() { return this.attrs["class"] || ""; }
  set className(v) { this.attrs["class"] = String(v); }
  get id() { return this.attrs.id || ""; }
  set id(v) { this.attrs.id = String(v); }
  classes() { return this.className.split(/\s+/).filter(Boolean); }
  get firstChild() { return this.children[0] || null; }
  get lastChild() { return this.children[this.children.length - 1] || null; }
  _adopt(c) { if (typeof c === "string") c = doc.createTextNode(c); if (c.parentNode) c.parentNode.removeChild(c); c.parentNode = this; return c; }
  appendChild(c) { c = this._adopt(c); this.children.push(c); return c; }
  append(...cs) { cs.forEach(c => this.appendChild(c)); }
  insertBefore(c, ref) { c = this._adopt(c); const i = ref ? this.children.indexOf(ref) : -1; if (i < 0) this.children.push(c); else this.children.splice(i, 0, c); return c; }
  replaceChild(n, o) { const i = this.children.indexOf(o); n = this._adopt(n); if (i >= 0) { this.children[i] = n; o.parentNode = null; } return o; }
  removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); c.parentNode = null; return c; }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  set textContent(t) { this.children.forEach(c => { c.parentNode = null; }); this.children = []; this._text = String(t == null ? "" : t); }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(""); }
  set innerHTML(h) { if (String(h) !== "") throw new Error("stub DOM: innerHTML may only be cleared"); this.textContent = ""; }
  get innerHTML() { return ""; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  hasAttribute(k) { return k in this.attrs; }
  addEventListener(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); }
  removeEventListener(ev, fn) { this.listeners[ev] = (this.listeners[ev] || []).filter(f => f !== fn); }
  set onclick(fn) { this.addEventListener("click", fn); }
  fire(ev) { const e = { type: ev, target: this, currentTarget: this, preventDefault() {}, stopPropagation() {} }; (this.listeners[ev] || []).slice().forEach(f => f.call(this, e)); }
  focus() {} blur() { this.fire("blur"); } select() {} scrollIntoView() {} click() { if (!this.disabled) this.fire("click"); }
  all() { return [this].concat(...this.children.map(c => c.all())); }
  matches(sel) { return matchChain(this, parseChain(sel)); }
  querySelectorAll(sel) { return queryAll(this, sel); }
  querySelector(sel) { return queryAll(this, sel)[0] || null; }
  closest(sel) { for (let n = this; n && n.nodeType === 1; n = n.parentNode) if (n.matches && n.matches(sel)) return n; return null; }
}
function parseCompound(s) {
  const out = { tag: null, id: null, cls: [], attrs: [] };
  const re = /^([a-zA-Z][\w-]*|\*)|#([\w-]+)|\.([\w-]+)|\[([\w-]+)(?:="((?:[^"\\]|\\.)*)")?\]/g;
  let m, used = 0;
  while ((m = re.exec(s)) !== null) {
    if (m.index !== used) throw new Error("stub DOM: selector not supported: " + s);
    used = re.lastIndex;
    if (m[1]) out.tag = m[1] === "*" ? null : m[1].toUpperCase();
    else if (m[2]) out.id = m[2];
    else if (m[3]) out.cls.push(m[3]);
    else out.attrs.push([m[4], m[5] === undefined ? null : m[5].replace(/\\(.)/g, "$1")]);
    if (m[0] === "") break;
  }
  if (used !== s.length) throw new Error("stub DOM: selector not supported: " + s);
  return out;
}
function parseChain(sel) { return sel.trim().split(/\s+/).map(parseCompound); }
function matchOne(el, c) {
  if (el.nodeType !== 1) return false;
  if (c.tag && el.tagName !== c.tag) return false;
  if (c.id && el.id !== c.id) return false;
  if (c.cls.some(x => !el.classes().includes(x))) return false;
  return c.attrs.every(([k, v]) => v === null ? k in el.attrs : el.attrs[k] === v);
}
function matchChain(el, chain) {
  if (!matchOne(el, chain[chain.length - 1])) return false;
  let i = chain.length - 2, n = el.parentNode;
  while (i >= 0 && n) { if (n.nodeType === 1 && matchOne(n, chain[i])) i--; n = n.parentNode; }
  return i < 0;
}
function queryAll(root, sel) {
  const chains = sel.split(",").map(parseChain);
  return root.all().filter(n => n !== root && chains.some(ch => matchChain(n, ch)));
}

const doc = {
  title: "", documentElement: { lang: "" }, readyState: "complete",
  createElement: t => new El(String(t).toLowerCase()),
  createTextNode: t => { const n = new El("#text"); n._text = String(t); return n; },
  execCommand: () => true,
  addEventListener: () => {},
};
doc.body = new El("body");
doc.getElementById = id => {
  if (jsonBlocks[id] !== undefined) return { textContent: jsonBlocks[id] };
  return doc.body.all().find(n => n.id === id) || null;
};
doc.querySelector = sel => doc.body.querySelector(sel);
doc.querySelectorAll = sel => doc.body.querySelectorAll(sel);
// every element the page's own markup names by id exists, empty, under body
staticIds.forEach(id => { if (jsonBlocks[id] !== undefined) return; const e = new El("div"); e.id = id; doc.body.appendChild(e); });

// ---- timers: a virtual clock; each step (the load, then each action) moves it on by STEP ms,
// so a 700 ms typing pause runs inside one step and a 3 s "click again" window spans two
const STEP = 1000;
const timers = [];
let timerSeq = 0, clock = 0;
function setT(fn, ms) { const id = ++timerSeq; timers.push({ id, fn, due: clock + Math.max(0, Number(ms) || 0) }); return id; }
function clearT(id) { const i = timers.findIndex(t => t.id === id); if (i >= 0) timers.splice(i, 1); }
async function drain() {
  const target = clock + STEP;
  for (let round = 0; round < 80; round++) {
    await new Promise(r => setImmediate(r));
    timers.sort((a, b) => a.due - b.due || a.id - b.id);
    if (timers.length && timers[0].due <= target) { const t = timers.shift(); clock = Math.max(clock, t.due); t.fn(); }
  }
  clock = target;
}

// ---- fake capabilities
const writes = [];
const store = Object.assign({}, scenario.saved || {});
function later(v) { return new Promise(r => setImmediate(() => r(v))); }
const fakeDb = {
  collection(name) {
    if (name !== "answers") throw new Error("harness: only the answers collection is expected, got " + name);
    return {
      get: () => later({ docs: Object.keys(store).map(id => ({ id, exists: true, data: () => store[id], metadata: { fromCache: false, hasPendingWrites: false } })), size: Object.keys(store).length, empty: !Object.keys(store).length }),
      doc: id => ({
        id, path: "answers/" + id,
        get: () => later({ id, exists: id in store, data: () => store[id] }),
        set: body => later(null).then(() => {
          writes.push({ op: "set", id, body: JSON.parse(JSON.stringify(body)) });
          if (scenario.db === "ro") { const e = new Error("no write"); e.code = "invalid_argument"; throw e; }
          store[id] = body;
        }),
        update: body => later(null).then(() => { writes.push({ op: "update", id, body }); store[id] = Object.assign({}, store[id], body); }),
        delete: () => later(null).then(() => { writes.push({ op: "delete", id }); delete store[id]; }),
      }),
    };
  },
};
const fakeUser = { can: () => later(scenario.db !== "ro"), isOwner: () => later(true), canEdit: () => later(scenario.db !== "ro"), id: () => later("u1") };
const claude = { use: name => later(scenario.db === "off" ? null : name === "db" ? fakeDb : name === "user" ? fakeUser : null) };

const win = { claude, scrollTo() {}, addEventListener() {}, setTimeout: setT, clearTimeout: clearT, setInterval: setT, clearInterval: clearT, location: { href: "about:blank" } };
win.window = win; win.document = doc;
const nav = {};

// ---- run
const cards = () => doc.body.all().filter(n => n.nodeType === 1 && /^q\d+$/.test(n.id));
const card = n => cards().find(c => c.id === "q" + n);
const optButton = (n, letter) => card(n).all().find(x => x.classes && x.classes().includes("opt") && x.children[0] && x.children[0].textContent === letter);
const visible = id => { const e = doc.getElementById(id); return !!e && !e.hidden; };

(async () => {
  const fn = new Function("window", "document", "navigator", "claude", "setTimeout", "clearTimeout", "setInterval", "clearInterval", "localStorage", scripts.join("\n;\n"));
  fn(win, doc, nav, claude, setT, clearT, setT, clearT, undefined);
  await drain();
  const writesOnLoad = writes.length;
  for (const a of scenario.actions || []) {
    if (a[0] === "pick") optButton(a[1], a[2]).click();
    else if (a[0] === "note") { const ta = card(a[1]).all().find(x => x.tagName === "TEXTAREA"); ta.value = a[2]; ta.fire("input"); }
    else if (a[0] === "blur") { const ta = card(a[1]).all().find(x => x.tagName === "TEXTAREA"); ta.fire("blur"); }
    else if (a[0] === "all-rec") doc.getElementById("all-rec").click();
    else if (a[0] === "clear") doc.getElementById("clear").click();
    else if (a[0] === "copy") doc.getElementById("copy").click();
    await drain();
  }
  const checked = {};
  cards().forEach(c => {
    const on = c.all().find(x => x.classes && x.classes().includes("opt") && x.getAttribute("aria-checked") === "true");
    if (on) checked[c.id.slice(1)] = on.children[0].textContent;
  });
  const first = cards()[0] && cards()[0].all().find(x => x.classes && x.classes().includes("opt"));
  const box = doc.getElementById("copybox");
  console.log(JSON.stringify({
    count: doc.getElementById("count") ? doc.getElementById("count").textContent : null,
    done: cards().filter(c => c.classes().includes("done")).map(c => Number(c.id.slice(1))),
    cards: cards().length,
    checked, disabled: first ? !!first.disabled : null,
    writesOnLoad, writes: writes.slice(writesOnLoad),
    nodb: visible("b-nodb"), ro: visible("b-ro"),
    copy: box ? box.value : null,
    h1: doc.getElementById("h1") ? doc.getElementById("h1").textContent : null,
    toast: doc.getElementById("toast") ? doc.getElementById("toast").textContent : null,
  }));
})().catch(e => { console.error("HARNESS FAIL " + (e && e.stack || e)); process.exit(1); });
