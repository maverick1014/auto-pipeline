"""Failing tests: city-data, the page half (owner, 2026-10-02; approved mock mock/city-data-mock.html).

requirements/city.md: Look ("A bubble never covers a name label", the person panel's history),
Growth ("Building names"), Persistence ("History"). The server half is tests/test_agent_city_data.py.

CONTRACT (bin/agent-city.html)

  D1  Building names: buildingName(b) shows the server's name (b.name) as it is. Nothing to build: the
      rule was already "b.name when it is set"; these tests keep it for the names the server makes.

  History (the server writes the lines, the page words them). Sim part, next to actLog / actTool:
  D2  const HIST_KEEP = 200.   let serverHist = false.
      ownHist(c) -> true when the page writes c's lines itself: !serverHist || !!c.remote.
      actLog(c, text), actTool(c, step) and giveAnswer(c)'s c.qa.push add nothing when !ownHist(c).
      (No server history: the demo, the cloud page, an older server, other members' people -> as before.)
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
  D4  apply 'snapshot': serverHist = !CLOUD && ev.hist is an object. Then, for every person of this
      machine on the page (not c.remote), after the agents are placed: c.acts = [], c.qa = [] and every
      line of ev.hist[c.id] through histLine(c, line, false). A snapshot with no hist: serverHist = false,
      nobody's lines are touched.
      apply { type: 'hist', id, line, fold } -> histLine(byId(id), line, fold), returns that person; nobody
      with that id (or another member's person) -> null, nothing changes.

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

from test_agent_city_page import constants_prelude, function_source, inline_script, page_fns, run_node  # noqa: E402
from test_agent_city_people import run_sim  # noqa: E402
from test_agent_city_polish import named_view  # noqa: E402

VM_JS = r"""
const fs = require('fs'), vm = require('vm');
const { fns, driver, payload } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { __payload: payload, __out: null, console, Math, JSON, Map, Set, Array, Object, Number, String };
vm.createContext(box);
vm.runInContext(fns + '\n;\n' + driver, box);
process.stdout.write(JSON.stringify(box.__out));
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


class TestServerNameShown(unittest.TestCase):

    def test_the_servers_name_as_it_is(self):
        out = run_sim(NAME_DRIVER, {"names": SERVER_NAMES}, ("buildingName",))
        self.assertEqual(out, SERVER_NAMES, "never the task, the files or the type word when the server named it")


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
function buildLand(view){ landState(view); }
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
out.on = serverHist; out.own = [ownHist(c), ownHist({ remote: { who: 'x', device: 'd' } })];
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

REMOTE_DRIVER = HIST_HEAD + r"""
apply(snap({ w1: [], w2: [] }));
const r = { id: 'r:dev:x1', remote: { who: 'x', device: 'dev' }, acts: [], qa: [] };
actLog(r, 'theirs'); actTool(r, 'step');
const me = byId('w1'); actLog(me, 'mine');
__out = { on: serverHist, remote: r.acts.map(a => a.text), mine: me.acts.length };
"""

HIST_NEEDS = ("apply", "byId", "landState", "i18n", "actLog", "actTool", "giveAnswer", "personHistory", "stepText",
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
        self.assertEqual(r["own"], [False, True], "the page writes only other members' people itself")

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

    def test_other_members_people_keep_the_pages_own_lines(self):
        r = run_sim(REMOTE_DRIVER, {"view": named_view(), "lines": LINES}, HIST_NEEDS)
        self.assertTrue(r["on"])
        self.assertEqual(r["remote"], ["theirs", "step"])
        self.assertEqual(r["mine"], 0)

    def test_the_cloud_page_never_switches_it_on(self):
        src = inline_script()
        m = re.search(r"serverHist\s*=\s*([^;]+);", src[src.index("case 'snapshot'"):])
        self.assertIsNotNone(m, "the snapshot case sets serverHist")
        self.assertIn("!CLOUD", m.group(1), "the cloud picture carries no hist; the cloud page keeps its own lines")


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


class TestLabelDodge(unittest.TestCase):

    def test_the_gap(self):
        self.assertEqual(const_line("LABEL_GAP"), "6")

    def test_nothing_touches(self):
        self.assertEqual(dodge(LAB, []), 0)
        self.assertEqual(dodge(LAB, [box(600, 200, 90, 26)]), 0, "a bubble far to the side")
        self.assertEqual(dodge(LAB, [box(300, 100, 90, 26)]), 0, "a bubble well above")
        self.assertEqual(dodge(LAB, [], [box(310, 185, 80, 22)]), 0, "another label alone never moves it")

    def test_up_just_clear_of_the_bubble(self):
        dy = dodge(LAB, [BUB])
        self.assertEqual(dy, 174 - 6 - 190, "the label's bottom ends 6 px above the bubble's top")
        self.assertFalse(touch(moved(LAB, dy), BUB))

    def test_closer_than_the_gap_counts(self):
        near = box(310, 171, 100, 22)            # 3 px above the bubble, not on it
        self.assertEqual(dodge(near, [BUB]), 174 - 6 - 171)
        clear = box(310, 168, 100, 22)           # exactly the gap away
        self.assertEqual(dodge(clear, [BUB]), 0)

    def test_clear_of_the_whole_stack(self):
        dy = dodge(LAB, [BUB, QM])
        self.assertEqual(dy, 140 - 6 - 190, "above the ? that stands on the bubble")
        for b in (BUB, QM):
            self.assertFalse(touch(moved(LAB, dy), b))

    def test_never_onto_another_label(self):
        other = box(300, 160, 120, 22)           # a site sign right above the bubble: t 138, b 160
        dy = dodge(LAB, [BUB], [other])
        self.assertEqual(dy, 138 - 6 - 190)
        self.assertFalse(touch(moved(LAB, dy), other))
        self.assertFalse(touch(moved(LAB, dy), BUB))

    def test_no_room_above_goes_under(self):
        dy = dodge(LAB, [BUB, QM], top=120)      # up would put its top at 112: above the limit
        self.assertEqual(dy, 200 + 6 - 168, "its top ends 6 px under the bubble's bottom")
        self.assertFalse(touch(moved(LAB, dy), BUB))
        self.assertEqual(dodge(LAB, [BUB, QM], top=112), 140 - 6 - 190, "it just fits: up")

    def test_under_clears_what_is_there_too(self):
        under = box(310, 230, 100, 22)           # another label just under the bubble: t 208, b 230
        dy = dodge(LAB, [BUB], [under], top=150)
        self.assertEqual(dy, 230 + 6 - 168)


class TestDodgeTargets(unittest.TestCase):

    def targets(self, boxes, bubbles, top=0):
        return run_vm(dodge_fns(), "__out = dodgeTargets(__payload.boxes, __payload.bubbles, __payload.top);",
                      {"boxes": boxes, "bubbles": bubbles, "top": top})

    def test_only_touched_labels_move(self):
        far = box(900, 400, 80, 22)
        out = self.targets([LAB, far], [BUB, QM])
        self.assertEqual(out, [140 - 6 - 190, 0])
        self.assertEqual(self.targets([LAB, far], []), [0, 0])
        self.assertEqual(self.targets([], [BUB]), [])

    def test_two_labels_at_one_bubble_end_apart(self):
        sign = box(295, 195, 110, 22)            # a site sign on the same bubble
        boxes = [LAB, sign]
        out = self.targets(boxes, [BUB, QM])
        ends = [moved(b, dy) for b, dy in zip(boxes, out)]
        self.assertTrue(all(dy < 0 for dy in out), out)
        self.assertFalse(touch(ends[0], ends[1]), "a moved label never lands on another name label")
        for e in ends:
            for b in (BUB, QM):
                self.assertFalse(touch(e, b))

    def test_a_label_that_stays_is_an_obstacle(self):
        stays = box(300, 130, 120, 22)           # above the "?", touched by no bubble: t 108, b 130
        out = self.targets([LAB, stays], [BUB, QM])
        self.assertEqual(out[1], 0)
        self.assertEqual(out[0], 108 - 6 - 190, "the first label goes above the one that stays")
        out2 = self.targets([stays, LAB], [BUB, QM])
        self.assertEqual(out2, [0, 108 - 6 - 190], "the order of the labels does not change that")


class TestEaseDodge(unittest.TestCase):

    def ease(self, driver, payload=None):
        return run_vm(dodge_fns(), driver, payload)

    def test_it_glides(self):
        out = self.ease(r"""
let v = 0; const steps = [];
for (let i = 0; i < 240; i++) { v = easeDodge(v, -56, 1 / 60); steps.push(v); }
__out = { first: steps[0], steps, same: easeDodge(-56, -56, 1 / 60), zero: easeDodge(0, 0, 1 / 60) };
""")
        self.assertAlmostEqual(out["first"], -56 / 6.0, places=4, msg="one frame: a sixth of the way (dt * 10)")
        steps = out["steps"]
        self.assertTrue(all(a >= b for a, b in zip(steps, steps[1:])), "never back")
        self.assertTrue(all(s >= -56 for s in steps), "never past the target")
        self.assertEqual(steps[-1], -56, "it arrives exactly")
        self.assertLess(steps.index(-56), 60, "within a second")
        self.assertEqual(out["same"], -56)
        self.assertEqual(out["zero"], 0)

    def test_back_and_a_slow_frame(self):
        out = self.ease("__out = [easeDodge(-56, 0, 1 / 60), easeDodge(0, 38, .5), easeDodge(-0.3, 0, 1 / 60), easeDodge(10, 10.2, 0.001)];")
        self.assertAlmostEqual(out[0], -56 + 56 / 6.0, places=4)
        self.assertEqual(out[1], 38, "a long frame goes straight there, never past it")
        self.assertEqual(out[2], 0, "closer than .4 px: there")
        self.assertEqual(out[3], 10.2)


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


class TestLabelsOnThePage(unittest.TestCase):

    def run_view(self, driver):
        return run_vm(view_fns(), driver)

    def test_pin_remembers_the_point(self):
        out = self.run_view(r"""
pin(bub, 300, 200.26, true);
const shown = { px: bub._px, py: bub._py, hidden: bub.hidden, tr: bub.style.transform };
pin(bub, 5, 6, false);
__out = { shown, hidden: bub.hidden };
""")
        self.assertEqual((out["shown"]["px"], out["shown"]["py"]), (300, 200.26))
        self.assertFalse(out["shown"]["hidden"])
        self.assertEqual(out["shown"]["tr"], "translate(300.0px,200.3px) translate(-50%,-100%)", "the transform as before")
        self.assertTrue(out["hidden"])

    def test_the_bubbles_and_the_labels(self):
        out = self.run_view(r"""
pin(bub, 300, 200, true); pin(qm, 300, 168, true); pin(talk, -9999, -9999, true); pin(tag, 300, 240, true); pins();
const one = bubbleBoxes();
pin(talk, 420, 150, true); pin(qm, 0, 0, false);
__out = { one, two: bubbleBoxes(), names: nameLabels().map(r => r.el === land ? 'land' : r.el === sign ? 'sign' : r.el === far ? 'far' : '?'),
  top: labelTop(), noStrip: (strip = null, labelTop()) };
""")
        self.assertEqual(out["one"], [BUB, QM], "bottom centre boxes; a name tag is no bubble; behind the camera is not on screen")
        self.assertEqual(out["two"], [BUB, box(420, 150, 30, 30)], "a hidden one is out, the small talk bubble counts")
        self.assertEqual(sorted(out["names"]), ["far", "land", "sign"], "land names and site signs, never a district label")
        self.assertEqual(out["top"], 12 + 34 + 6)
        self.assertEqual(out["noStrip"], 6)

    def test_the_label_moves_the_bubble_stays(self):
        out = self.run_view(r"""
pin(bub, 300, 200, true); pin(qm, 300, 168, true); pins();
const before = { bub: bub.style.transform, qm: qm.style.transform, dist: dist.style.transform, far: far.style.transform };
dodgeNameLabels(1);                       // a long frame: straight to the target
__out = { land: at(land), sign: at(sign), same: before.bub === bub.style.transform && before.qm === qm.style.transform,
  dist: dist.style.transform === before.dist, far: far.style.transform === before.far,
  base: [land._px, land._py], w: [land.offsetWidth, sign.offsetWidth] };
""")
        self.assertTrue(out["same"], "the bubble wins: it is never moved")
        self.assertTrue(out["dist"], "the small district label stays")
        self.assertTrue(out["far"], "a label nothing touches stays")
        self.assertEqual(out["base"], [310, 190], "the label's own point is kept: it goes back there")
        land = moved(LAB, out["land"][1] - 190)
        sign = moved(box(295, 195, 110, 22), out["sign"][1] - 195)
        self.assertEqual(out["land"][0], 310)
        self.assertEqual(out["sign"][0], 295)
        for b in (BUB, QM):
            self.assertFalse(touch(land, b), "the land's name is clear of the bubbles")
            self.assertFalse(touch(sign, b), "the site sign too")
        self.assertFalse(touch(land, sign), "and they do not land on each other")
        self.assertGreaterEqual(min(land["t"], sign["t"]), 12 + 34 + 6, "never under the strip at the top")

    def test_it_glides_there_and_back(self):
        out = self.run_view(r"""
const frame = () => { pin(land, 310, 190, true); pin(far, 900, 400, true); dodgeNameLabels(1 / 60); };   // no site sign here
pin(bub, 300, 200, true);
frame();
const one = at(land)[1];
for (let i = 0; i < 120; i++) frame();
const there = at(land)[1];
pin(bub, 0, 0, false);                   // the bubble goes away
frame();
const backOne = at(land)[1];
for (let i = 0; i < 120; i++) frame();
__out = { one, there, backOne, back: at(land)[1] };
""")
        self.assertTrue(190 > out["one"] > 168, "one frame: a part of the way, never a jump (%r)" % out["one"])
        self.assertEqual(out["there"], 174 - 6, "the label's point ends 6 px above the bubble")
        self.assertTrue(168 < out["backOne"] < 190, "it glides back too")
        self.assertEqual(out["back"], 190, "nothing touches it: back at its own point")

    def test_behind_the_camera_and_hidden(self):
        out = self.run_view(r"""
pin(bub, -9999, -9999, true); pin(land, -9999, -9999, true); pin(sign, 0, 0, false); pin(far, 900, 400, true);
dodgeNameLabels(1);
const a = at(land);
pin(bub, 300, 200, true); pin(land, 310, 190, true); pin(sign, 0, 0, false);
dodgeNameLabels(1);
__out = { a, land: at(land)[1], signHidden: sign.hidden };
""")
        self.assertEqual(out["a"], [-9999, -9999], "both behind the camera: nothing to dodge")
        self.assertEqual(out["land"], 174 - 6, "a hidden sign is no obstacle: straight above the bubble")
        self.assertTrue(out["signHidden"], "a hidden label stays hidden")

    def test_no_room_above_goes_under(self):
        out = self.run_view(r"""
pin(bub, 300, 80, true); pin(land, 310, 76, true);        // right under the strip: up would end above 52
dodgeNameLabels(1);
__out = at(land)[1];
""")
        self.assertEqual(out, 80 + 6 + 22, "its top 6 px under the bubble")

    def test_called_every_frame_after_the_pins(self):
        src = function_source("sync")
        self.assertIsNotNone(src)
        i, j, k = src.find("pinSiteSigns()"), src.find("pinLandOverlays()"), src.find("dodgeNameLabels(dt)")
        self.assertTrue(i >= 0 and j >= 0)
        self.assertGreater(k, max(i, j), "the labels are moved after every overlay was pinned")


if __name__ == "__main__":
    unittest.main()
