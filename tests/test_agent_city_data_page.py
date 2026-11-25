"""Failing tests: city-data, the page half (owner, 2026-10-02; approved mock mock/city-data-mock.html).

requirements/city.md: Look ("A bubble never covers a name label", the person panel's history),
Growth ("Building names"), Persistence ("History"). The server half is tests/test_agent_city_data.py.

CONTRACT (bin/agent-city.html)

  D1  Building names: buildingName(b) shows the server's name (b.name) as it is. Nothing to build: the
      rule was already "b.name when it is set"; these tests keep it for the names the server makes.

  History (the server writes the lines, the page words them). Sim part, next to actLog / actTool:
  D2  const HIST_KEEP = 200.   let serverHist = false.
      ownHist(c) -> true when the page writes c's lines itself: !serverHist.
      actLog(c, text), actTool(c, step) and giveAnswer(c)'s c.qa.push add nothing when !ownHist(c).
      (No server history: the demo, an older server -> as before.)
  D3  histLine(c, line, fold): one server line into c's own stores, worded by the page:
        started  c.acts += { at, text: i18n('hist.started', { task: line.task }) }
        steps    c.acts += { at, steps: [stepText(s) of every step, a text already there left out],
                             text: steps.join(' · ') }; with FOLD and a last act that has .steps, it
                 REPLACES that act instead
        stuck    c.acts += { at, text: i18n('hist.stuck', { text: stuckText(line) }) }
        toLead / toGov / waiting / done / left   c.acts += { at, text: i18n('hist.' + k) }
        qa       c.qa += { q: stuckText(line), a: line.answer when it is a non-empty string, else
                           i18n('answer.default'), at }
      at = line.at. Any other k (or no line) adds nothing. c.acts and c.qa never hold more than
      HIST_KEEP: the oldest go.
  D4  apply 'snapshot': serverHist = ev.hist is an object. Then, for every person of this
      machine on the page, after the agents are placed: c.acts = [], c.qa = [] and every
      line of ev.hist[c.id] through histLine(c, line, false). A snapshot with no hist: serverHist = false,
      nobody's lines are touched.
      apply { type: 'hist', id, line, fold } -> histLine(byId(id), line, fold), returns that person; nobody
      with that id -> null, nothing changes.

  Labels (a bubble never covers a name label). Sim part (pure, boxes are { l, r, t, b } in screen px):
  D5  const LABEL_GAP = 6. Two boxes TOUCH when they are closer than LABEL_GAP in both directions:
      a.l < b.r + GAP && a.r > b.l - GAP && a.t < b.b + GAP && a.b > b.t - GAP.
      labelDodge(box, bubbles, others, top) -> dy (px; up is negative; 0 = stays).
        No bubble touches BOX -> 0 (another label alone never moves it).
        Else up: while the box (moved by dy) touches a bubble or one of OTHERS, dy = (the highest top of
        what it touches) - GAP - box.b; at most 8 rounds.
        No room up there (box.t + dy < top) -> down the same way: dy = (the lowest bottom of what it
        touches) + GAP - box.t.
      dodgeTargets(boxes, bubbles, top) -> [dy] for the name labels BOXES, in order. Label i dodges with
        others = the boxes before it where they END (moved by their dy) and the boxes after it where
        they are now.
      easeDodge(cur, to, dt) -> the next offset: cur + (to - cur) * min(1, dt * 10); closer than .4 px to
        TO -> exactly TO. It glides, never jumps, never passes TO.
  D6  View part:
      pin(el, x, y, show): when shown it also remembers the point: el._px = x, el._py = y.
      bubbleBoxes() -> the boxes of the head bubbles on screen: every child of ovRoot that is not hidden,
        has the class bub, qm or talkb, and is not behind the camera (el._px > -5000). The point is the
        bottom centre: { l: _px - w / 2, r: _px + w / 2, t: _py - h, b: _py }, w = el.offsetWidth,
        h = el.offsetHeight.
      nameLabels() -> the records ({ el, ... }) of every land's name label (the entries of `labels`
        without .mark; the district labels have it) and of every site sign (siteSigns.values()).
      labelTop() -> the highest y a moved label may reach: LABEL_GAP under the strip at the top of the
        map ($('#stage-top'): offsetTop + offsetHeight + LABEL_GAP), LABEL_GAP when there is no strip.
      dodgeNameLabels(dt): once a frame, after the pins. For every record of nameLabels() that is shown and
        not behind the camera (el._px > -5000): its box from _px, _py, offsetWidth, offsetHeight;
        dodgeTargets(boxes, bubbleBoxes(), labelTop()); rec.dy = easeDodge(rec.dy || 0, target, dt); and
        while rec.dy is not 0 the label is drawn rec.dy lower: el.style.transform =
        'translate(<_px>px,<_py + dy>px) translate(-50%,-100%)' (numbers with one decimal, as pin writes
        them). A bubble is never moved. A hidden label, or one behind the camera, is no obstacle and
        its dy goes back to 0.
      sync(t, dt) calls dodgeNameLabels(dt) after pinSiteSigns() and pinLandOverlays().
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from citypage import constants_prelude, script_function_source as function_source, inline_script, page_fns, run_node  # noqa: E402
from citypage import run_sim  # noqa: E402
from citypage import named_view  # noqa: E402

VM_JS = r"""
const fs = require('fs'), vm = require('vm');
const { fns, driver, payload } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { __payload: payload, __out: null, console, Math, JSON, Map, Set, Array, Object, Number, String };
vm.createContext(box);
vm.runInContext(fns + '\n;\n' + driver, box);
require(`fs`).writeSync(1, JSON.stringify(box.__out));
"""


def run_vm(fns, driver, payload=None):
    return run_node(VM_JS, {"fns": fns, "driver": driver, "payload": payload or {}})


def const_line(name):
    m = re.search(r"^const %s = ([^;\n]+);" % re.escape(name), inline_script(), re.M)
    if not m:
        raise AssertionError("const %s = ...; not found in the page script" % name)
    return m.group(1).strip()


# ---------------------------------------------------------------------------
# D1 the popup shows the server's name
# ---------------------------------------------------------------------------

NAME_DRIVER = r"""
const T = o => buildingName(Object.assign({ name: '', task: '别的任务', by: 'worker', files: ['api/other.py'], type: 'house' }, o));
__out = __payload.names.map(n => T({ name: n }));
"""

SERVER_NAMES = ["checkout 页面", "orders 测试", "deploy 脚本", "api 文档", "payment 模块", "checkout 页面 2",
                "修退款金额", "住宅区 5 号", "checkout page", "Homes no. 12", "aaaaaaaaaaaaaaaaaaaaaaa… 模块"]


# ---------------------------------------------------------------------------
# D2..D4 the history comes from the server
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# D5 where a label goes (pure)
# ---------------------------------------------------------------------------

def box(cx, bottom, w, h):
    return {"l": cx - w / 2.0, "r": cx + w / 2.0, "t": bottom - h, "b": bottom}


def touch(a, b, gap=6):
    return a["l"] < b["r"] + gap and a["r"] > b["l"] - gap and a["t"] < b["b"] + gap and a["b"] > b["t"] - gap


def moved(b, dy):
    return {"l": b["l"], "r": b["r"], "t": b["t"] + dy, "b": b["b"] + dy}


BUB = box(300, 200, 90, 26)      # 等你回话: t 174, b 200
QM = box(300, 168, 28, 28)       # the red "?" above it: t 140, b 168
LAB = box(310, 190, 100, 22)     # a land's name: t 168, b 190

DODGE_FNS = None


def dodge_fns():
    global DODGE_FNS
    if DODGE_FNS is None:
        DODGE_FNS = ("var LABEL_GAP = %s;\n" % const_line("LABEL_GAP")
                     + page_fns("labelDodge", "dodgeTargets", "easeDodge"))
    return DODGE_FNS


def dodge(b, bubbles, others=(), top=0):
    return run_vm(dodge_fns(), "__out = labelDodge(__payload.b, __payload.bubbles, __payload.others, __payload.top);",
                  {"b": b, "bubbles": list(bubbles), "others": list(others), "top": top})


# ---------------------------------------------------------------------------
# D6 the view: the real overlays
# ---------------------------------------------------------------------------

VIEW_PRELUDE = r"""
function El(cls, w, h){
  return { className: cls, classList: { contains: c => cls.split(' ').includes(c) }, hidden: true,
    offsetWidth: w, offsetHeight: h, style: {}, textContent: cls };
}
var strip = { offsetTop: 12, offsetHeight: 34 };
var $ = sel => (sel === '#stage-top' ? strip : null);
var ovRoot = { children: [] };
var labels = [], siteSigns = new Map();
function add(el){ ovRoot.children.push(el); return el; }
function at(el){ const m = /translate\((-?[\d.]+)px,\s*(-?[\d.]+)px\)/.exec(el.style.transform || ''); return m ? [Number(m[1]), Number(m[2])] : null; }
const bub = add(El('bub gov', 90, 26)), qm = add(El('qm', 28, 28)), talk = add(El('talkb', 30, 30)), tag = add(El('tagl tag', 60, 20));
const land = add(El('lbl', 100, 22)), dist = add(El('dlbl', 50, 16)), sign = add(El('lbl', 110, 22)), far = add(El('lbl', 80, 22));
labels.push({ el: land, x: 0, h: 2.1, z: 0 }, { el: dist, x: 1, h: 1.1, z: 1, mark: true }, { el: far, x: 9, h: 2.1, z: 9 });
siteSigns.set('s1', { el: sign, x: 0, z: 0, text: 'feat-a' });
function pins(){            // what sync() pins every frame, at their own (base) points
  pin(land, 310, 190, true); pin(dist, 300, 195, true); pin(sign, 295, 195, true); pin(far, 900, 400, true);
}
"""


def view_fns(*names):
    return ("var LABEL_GAP = %s;\n" % const_line("LABEL_GAP") + VIEW_PRELUDE
            + page_fns("pin", "labelDodge", "dodgeTargets", "easeDodge", "bubbleBoxes", "nameLabels", "labelTop",
                       "dodgeNameLabels", *names))


if __name__ == "__main__":
    unittest.main()
