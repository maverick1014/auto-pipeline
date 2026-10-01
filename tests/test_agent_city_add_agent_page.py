"""Failing tests for city-add-agent, the page (owner, 2026-10-01; approved mock
mock/city-add-agent-mock.html, efa3deb, approved as shown). The server side:
tests/test_agent_city_add_agent.py (its docstring has the answers and events
this page reads).

CONTRACT (bin/agent-city.html). "sim section" = the page script from 'use strict' up to the '3D view.'
comment: every name marked (sim) lives there and is driven in node (tests/test_agent_city_people.py run_sim).
Everything else is "3D part", checked on its source and its CSS.

A1 the rail lists every repo
  (sim) railGroups(): one group per territory of the map, in map order, ALSO a territory with no row at all
      (rows: []; before, it was left out). Every group carries add: true when its territory's view says
      here === true (the server: its folder is on this machine), else false. Demo and the cloud city have
      no "here": no button there.
  (sim) railHtml(groups, selId, closed, openRest, adds): an open group with no row shows one quiet line
      <p class="rail-none"> + i18n('rail.none') where the rows would be (its head count reads 0). A closed
      group shows its head only, as before: no line, no button.

A2 one button at the bottom of every repo group that is here
  (sim) railHtml: the LAST thing inside an open group's <section> whose add is true is addHtml(group,
      adds.get(group.terr)) (after the rows and after the resting people). A group whose add is false gets
      nothing. `adds` = a Map terr -> the button's state; left out = no state anywhere.
  (sim) addHtml(group, st) -> the button, or what stands in for it:
      no st          <button type="button" class="add" data-add="<terr>"> + i18n('add.btn')
      st.s 'opening' the same button with aria-disabled="true", a <span class="spin"></span> and
                     i18n('add.opening', {name}) -- name = st.name without the repo name ("v4-plus Manager"
                     reads "Manager", shortLabel) -- or i18n('add.openingBare') while the name is not known
      st.s 'cap'     <div class="addbox cap" role="alert">: i18n('add.cap'), i18n('add.capNums', {ram, cpu,
                     max}), i18n('add.capAsk'), a button data-add-go="<terr>" (i18n('add.go')) and a button
                     data-add-no="<terr>" (i18n('add.cancel'))
      st.s 'err'     <div class="addbox err" role="alert">: i18n('add.err') + st.why, a button
                     data-add="<terr>" (i18n('add.retry')) only when st.retry, and a button
                     data-add-no="<terr>" (i18n('add.ok'))
      st.s 'cmd'     <div class="addbox cmd" role="status">: i18n('add.plain'), <code> + st.cmd + </code>, a
                     button data-add-copy="<terr>" (i18n('add.copy'), or i18n('add.copied') once st.copied)
                     and a button data-add-no="<terr>" (i18n('add.close'))
      Every text from the server (name, why, cmd) goes through esc(). 'cap', 'err' and 'cmd' show no
      .add button of their own (only the retry one, when st.retry).

A4 / A5 / A6 the button's states
  (sim) addState: a Map terr -> st, the one the rail draws from.
  (sim) addReason(body) -> the reason in plain words: error 'gone' -> i18n('add.errGone', {folder}),
      'failed' -> i18n('add.errFailed', {detail}), anything else -> i18n('add.errOther').
  (sim) addAnswer(terr, code, body): the server's answer to POST /api/agent/add -> addState:
      200 state 'opening' -> {s: 'opening', name}, only while the state still is 'opening' (the click set
                             it): when it is gone, the server's 'done' event came before this answer (a
                             fast session) and nothing is set -- the button must not read opening for ever
      200 state 'cap'     -> {s: 'cap', ram, cpu, max}
      200 state 'plain'   -> {s: 'cmd', cmd: body.command}
      409 error 'busy'    -> {s: 'opening', name: ''} unless it already is opening (kept as it is)
      anything else (409 gone, 502 failed, 403, 404, no answer = code 0) -> {s: 'err', why: addReason(body),
      retry: true only for 'failed' and for no answer}. Never silent.
  (sim) apply(): case 'adding' -- state 'opening' -> {s: 'opening', name: ev.name}; 'done' -> the state is
      removed, only when it is 'opening'; 'late' -> {s: 'err', why: i18n('add.errLate'), retry: false}, only
      when it is 'opening'. case 'snapshot' -- every 'opening' state is dropped, then each {terr, name} of
      ev.adding (may be missing) is 'opening'; 'cap', 'err' and 'cmd' states stay (they are this page's own).
  3D part: addAgent(terr, force): nothing while that repo's state is 'opening'; else sets {s: 'opening',
      name: ''} at once, redraws the rail, then fetch('/api/agent/add', {method: 'POST', headers with
      'Content-Type' and 'X-City-Token': TOKEN, body: JSON.stringify({terr, force})}) -> addAnswer(terr,
      status, body) and a redraw; a failed fetch -> addAnswer(terr, 0, {}).
      The #rail-list click listener: [data-add] -> addAgent(terr, false); [data-add-go] -> addAgent(terr,
      true); [data-add-no] -> the state is removed; [data-add-copy] -> navigator.clipboard.writeText(st.cmd)
      (a failure is ignored) and st.copied = true; each redraws the rail. renderRail() passes addState to
      railHtml, and redraws when an 'adding' event comes.
  CSS (the mock's): .rail-none, .add, .add[aria-disabled="true"], .spin (an animation, stopped under
      prefers-reduced-motion), .addbox, .addbox.err, .addbox.cap, .addbox.cmd, .mini.
  TEXT, zh and en: rail.none 没人在线 / Nobody online; add.btn ＋ 加 agent / + Add agent; add.opening
      正在打开 {name}… / Opening {name}…; add.openingBare; add.cap; add.capNums (holds {ram}, {cpu}, {max});
      add.capAsk; add.go; add.cancel; add.err; add.retry; add.ok; add.errGone (holds {folder});
      add.errFailed (holds {detail}); add.errLate; add.errOther; add.plain; add.copy; add.copied; add.close.

Run: python3 -m unittest tests.test_agent_city_add_agent_page </dev/null
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import function_source, page, run_sim  # noqa: E402
from test_agent_city_chain import TA, TB, two_territory_view  # noqa: E402
from test_agent_city_ux_page import css, listener_block, rule, text_keys  # noqa: E402

SIM_REQUIRED = ("apply", "landState", "railGroups", "railHtml", "addHtml", "addState", "addAnswer", "addReason",
                "citizens", "byId", "i18n", "esc")

KEYS = ("rail.none", "add.btn", "add.opening", "add.openingBare", "add.cap", "add.capNums", "add.capAsk", "add.go",
        "add.cancel", "add.err", "add.retry", "add.ok", "add.errGone", "add.errFailed", "add.errLate", "add.errOther",
        "add.plain", "add.copy", "add.copied", "add.close")

# Two repos: A = auto-pipeline (a governor and one task manager), B = v4-plus (nobody online). Both are here.
DRIVER = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
A.name = 'auto-pipeline'; B.name = 'v4-plus'; A.here = true; B.here = true;
function buildLand(view){ landState(view); }
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
out.direct = addHtml(railGroups()[1], undefined);
// a repo that is not on this machine: the group stays, the button goes
B.here = false;
apply({ type: 'world', world: V });
out.notHere = { add: railGroups()[1].add, html: sec(draw(new Map([[B.id, { s: 'opening', name: 'x' }]])), B.id) };
delete B.here;
apply({ type: 'world', world: V });
out.noFlag = railGroups()[1].add;
B.here = true;
apply({ type: 'world', world: V });
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


# ---------------------------------------------------------------------------
# A1: every repo has a group
# ---------------------------------------------------------------------------

class TestEveryRepo(SimCase):
    def test_a_repo_with_nobody_keeps_its_group(self):
        self.assertEqual([(g["terr"], g["name"], g["rows"]) for g in self.r["groups"]],
                         [(self.a, "auto-pipeline", 3), (self.b, "v4-plus", 0)])

    def test_the_quiet_line(self):
        b = self.r["plainB"]
        self.assertIsNotNone(b, "v4-plus has no section in the rail")
        self.assertIn('<p class="rail-none">没人在线</p>', b)
        self.assertRegex(b, r'<span class="n">\s*0\s*</span>')
        self.assertNotIn("rail-none", self.r["plainA"], "auto-pipeline has people")

    def test_a_closed_group_is_its_head_only(self):
        for name in ("closedA", "closedB"):
            with self.subTest(group=name):
                html = self.r[name]
                self.assertIn('aria-expanded="false"', html)
                self.assertNotIn("rail-none", html)
                self.assertNotIn("data-add", html)


# ---------------------------------------------------------------------------
# A2: the button
# ---------------------------------------------------------------------------

class TestButton(SimCase):
    def button(self, terr):
        return '<button type="button" class="add" data-add="%s">＋ 加 agent</button>' % terr

    def test_every_repo_that_is_here_has_one(self):
        self.assertEqual([g["add"] for g in self.r["groups"]], [True, True])
        self.assertEqual(self.r["plainA"].count("data-add="), 1)
        self.assertEqual(self.r["plainB"].count("data-add="), 1)
        self.assertIn(self.button(self.a), self.r["plainA"])
        self.assertIn(self.button(self.b), self.r["plainB"])
        self.assertEqual(self.r["direct"], self.button(self.b))

    def test_at_the_bottom_of_the_group(self):
        a = self.r["plainA"]
        self.assertTrue(a.rstrip().endswith(self.button(self.a) + "</section>"),
                        "the button is the last thing in the group, after the resting people")
        self.assertLess(a.rindex("data-focus="), a.index("data-add="))
        self.assertLess(a.index("data-rest="), a.index("data-add="))
        b = self.r["plainB"]
        self.assertLess(b.index("rail-none"), b.index("data-add="))

    def test_adds_may_be_left_out(self):
        self.assertIn(self.button(self.b), self.r["noAdds"] or "")

    def test_a_repo_that_is_not_on_this_machine_has_none(self):
        self.assertIs(self.r["notHere"]["add"], False)
        html = self.r["notHere"]["html"]
        self.assertIsNotNone(html, "the group itself stays")
        self.assertIn("rail-none", html)
        self.assertNotIn("data-add", html)
        self.assertNotIn('class="add"', html)
        self.assertIs(self.r["noFlag"], False, "no `here` at all (demo, the cloud city) = no button")


# ---------------------------------------------------------------------------
# A4 / A5 / A6: what stands in for the button
# ---------------------------------------------------------------------------

class TestStates(SimCase):
    def test_opening(self):
        html = self.r["opening"]
        self.assertRegex(html, r'<button type="button" class="add" data-add="%s" aria-disabled="true">' % self.b)
        self.assertIn('<span class="spin"></span>', html)
        self.assertIn("正在打开 Manager…", html)
        self.assertNotIn("v4-plus Manager", html, "the repo name is in the group head already")
        self.assertEqual(html.count("data-add="), 1)
        bare = self.r["openingBare"]
        self.assertIn(self.r["text"]["add.openingBare"], bare)
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

    def test_error(self):
        html = self.r["err"]
        self.assertIn('<div class="addbox err" role="alert">', html)
        self.assertIn(self.r["text"]["add.err"], html)
        self.assertIn("Orca &lt;b&gt;broke&lt;/b&gt;", html, "the reason is the server's text: escaped")
        self.assertRegex(html, r'<button[^>]*data-add="%s"[^>]*>%s</button>' % (self.b, re.escape(self.r["text"]["add.retry"])))
        self.assertRegex(html, r'<button[^>]*data-add-no="%s"[^>]*>%s</button>' % (self.b, re.escape(self.r["text"]["add.ok"])))
        self.assertNotIn('class="add"', html)
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

    def test_the_state_is_the_last_thing_in_the_group(self):
        for name in ("cap", "err", "cmd"):
            with self.subTest(state=name):
                self.assertTrue(self.r[name].rstrip().endswith("</div></section>"))


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


def i18n_failed(why):
    """add.errFailed with the driver's detail of the 'failed' answer."""
    return why["tFailed"].replace("orca: no", "orca: the app is not running")


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


# ---------------------------------------------------------------------------
# the 3D part: the click, the request, the look, the words
# ---------------------------------------------------------------------------

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
        self.assertRegex(function_source("renderRail"), r"railHtml\([^;]*addState\)")

    def test_css(self):
        for sel in (".rail-none", ".add", '.add[aria-disabled="true"]', ".spin", ".addbox", ".addbox.err", ".addbox.cap",
                    ".addbox.cmd", ".mini"):
            with self.subTest(sel=sel):
                self.assertTrue(rule(sel).strip(), "no CSS rule for %s" % sel)
        self.assertIn("animation", rule(".spin"))
        reduced = [m.group(0) for m in re.finditer(r"@media \(prefers-reduced-motion:\s*reduce\)\s*\{(?:[^{}]|\{[^{}]*\})*\}", css())]
        self.assertTrue(any(".spin" in block for block in reduced), "the spinner must stop under prefers-reduced-motion")
        self.assertIn("dashed", rule(".add"), "the mock's quiet dashed button")

    def test_texts(self):
        for key in KEYS:
            with self.subTest(key=key):
                self.assertEqual(text_keys(key), 2, "one zh and one en text")
        src = page()
        for key, zh, en in (("rail.none", "没人在线", "Nobody online"), ("add.btn", "＋ 加 agent", "+ Add agent"),
                            ("add.opening", "正在打开 {name}…", "Opening {name}…")):
            with self.subTest(key=key):
                self.assertIn("'%s': '%s'" % (key, zh), src)
                self.assertIn("'%s': '%s'" % (key, en), src)


if __name__ == "__main__":
    unittest.main()
