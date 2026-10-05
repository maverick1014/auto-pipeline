"""Failing tests, cloud-city-3 slice W5: the cloud page starts an agent
(requirements/city.md, "Cloud page", "Start"; approved mock
mock/cloud-city-3-mock.html, screens add / fail / cap / phone / talk).

bin/agent-city.html stays ONE file. The local page and the demo stay exactly
as they are (tests/test_agent_city_add_agent_page.py still passes untouched).

  railGroups(): on the cloud page (CLOUD true) a group's `add` is true only
      when its territory says here === true (the picture now carries it) AND
      cloudStartOn(cloudLive.feed). On the local page: as before.
  addHtml(group, st): no longer '' on the cloud page. The states it draws
      (st.s), the same boxes as the mock:
        (cloud-polish Q5, 2026-10-02: the control is the small + on the repo name
        row, addIconHtml, and addHtml is the one row of words under it; see
        tests/test_agent_city_add_agent_page.py A2. The + shows a spinner for
        sent / opening and a tick for done.)
        none      '' (the + alone)
        sent      <p class="add-line" role="status" title="<add.cloud.sentTip>">add.cloud.sent 在路上…</p>
        opening   <p class="add-line" role="status">: on the cloud page add.cloud.opening
                  那台电脑正在打开 {name}… (the name without the repo, as before;
                  no name: add.cloud.openingBare); on the local page as before
        done      <div class="addbox ok" role="status">add.cloud.done 已打开 {name} · 小人马上出现</div>
        cap       as before; on the cloud page its title is add.cloud.cap 那台电脑有点忙
        err       as before (st.why is the reason, escaped; a retry button only when st.retry)
        cmd       as before (the local page only)
  addAgent(terr, force): on the cloud page it hands over to cloudAdd and
      returns BEFORE the local fetch: `if (CLOUD) return cloudAdd(terr, force);`
      The local page's request is unchanged (token header, {terr, force}).

  Pure helpers (between `/* cloud-city: pure */` and `/* end cloud-city: pure */`):
    cloudStartOn(feed) -> true when the machine shown (feed.dev's row of
        feed.devs) has start === true and is not stale (cloudStale with
        feed.now). No feed, no such machine -> false.
    cloudStartNote(feed) -> why there is no add-agent button for the machine
        shown, a text key or '': 'cloud.start.needTalk' when its talk is not
        true, else 'cloud.start.off' when its start is not true, else ''. No
        feed, no machine or a stale one -> '' (the offline notice says it).
    cloudOrderView(orders, now, hidden) -> a Map terr -> the state of that
        repo's button, from the feed's "orders" [{oid, terr, force, at, ts,
        state, why, info}]: for each terr its NEWEST order (the largest at)
        decides, and nothing else:
          sent, taken  -> {s: 'sent', oid}
          opening      -> {s: 'opening', oid, name: info.name or ''}
          opened       -> {s: 'done', oid, name} while now - ts < CLOUD_ADD_DONE_MS
                          (15000); after that no entry (the button is back)
          cap          -> {s: 'cap', oid, ram, cpu, max} (from info)
          failed       -> {s: 'err', oid, why: cloudOrderWhy(order), retry: false}
        An order whose oid is in HIDDEN (a Set: the owner pressed 知道了 or
        取消) gives no entry. Anything that is not an order is skipped.
    cloudOrderWhy(order) -> the reason in plain words (text): the key
        add.cloud.why.<x> for its why: off, start-off -> startOff, no-orca ->
        noOrca, gone, orca (with {detail}: info.detail), late, busy, flood,
        silent, restart, refused; anything else -> add.cloud.why.other.
    cloudAddAnswer(code, body) -> the state to show for the answer of POST
        /api/agent/add: 200 -> what cloudOrderView would show for that one
        order ({s, oid, ...}; an opened one shows 'done'); 409 busy -> {s:
        'sent', oid: body.oid}; 429 "too many this hour" -> {s: 'err', why:
        add.cloud.tooMany with {min}: body.wait in whole minutes, rounded up,
        at least 1}; 429 "too many today" -> add.cloud.tooManyDay; 403 ->
        cloud.login; anything else (no answer = code 0) -> add.cloud.noAnswer.
        An err has retry: false.

  cloudAdd(terr, force) (in the cloud script): nothing while that repo
      already reads sent or opening (one order at a time per repo); else the
      button reads sent at once (addState, with the new oid), and ONE
        fetch('/api/agent/add', {method: 'POST', credentials: 'same-origin',
              headers: {'Content-Type': 'application/json', 'X-City-Page': '1'},
              body: JSON.stringify({dev, terr, oid})})          (the confirm: {dev, terr, oid, force: true})
      dev = the machine shown (cloudLive.feed.dev), oid = cloudCid(). Never a
      token header, never another key in the body. The answer goes through
      cloudAddAnswer; a request that got NO answer (the network failed, or a
      5xx) is sent again with the SAME oid, CLOUD_SEND_TRIES requests in all.
      After every feed the buttons follow cloudOrderView(feed.orders, ...).
  The machine row: a machine with start shows a second chip, cloud.start.on 可开 agent.
  The rail's foot: cloudStartNote's text for the machine shown (the command
      shown as code), instead of the old chip "＋ 加 agent · 以后开放"
      (cloud.later.add is gone; cloud.later.ask and cloud.later.demo stay).
  CSS: .addbox.ok.
  TEXT, zh and en: see KEYS below.

Run: python3 -m unittest tests.test_agent_city_cloud_start_page </dev/null
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import test_agent_city_people as people  # noqa: E402
from test_agent_city_people import function_source, page  # noqa: E402
from test_agent_city_chain import TA, TB, two_territory_view  # noqa: E402
from test_agent_city_ux_page import css  # noqa: E402
import test_agent_city_page as tp  # noqa: E402

START = "/* cloud-city: pure */"
END = "/* end cloud-city: pure */"
T0 = 1_800_000_000_000
REQUIRED = ("apply", "landState", "railGroups", "railHtml", "addHtml", "addState", "cloudLive", "i18n", "esc",
            "cloudStartOn", "cloudStartNote", "cloudOrderView", "cloudOrderWhy", "cloudAddAnswer", "cloudAdd",
            "cloudCid", "cloudStale")

WHY = {"off": "off", "start-off": "startOff", "no-orca": "noOrca", "gone": "gone", "orca": "orca", "late": "late",
       "busy": "busy", "flood": "flood", "silent": "silent", "restart": "restart", "refused": "refused"}
KEYS = ["add.cloud.sent", "add.cloud.opening", "add.cloud.openingBare", "add.cloud.done", "add.cloud.cap",
        "add.cloud.tooMany", "add.cloud.tooManyDay", "add.cloud.noAnswer", "add.cloud.why.other",
        "cloud.start.on", "cloud.start.off", "cloud.start.needTalk"] + ["add.cloud.why." + k for k in WHY.values()]


def pure_section():
    text = tp.inline_script()
    return text[text.index(START) + len(START):text.index(END)]


def run_page(driver, payload, cloud=True, required=REQUIRED):
    """The page's simulation part + its cloud pure helpers + cloudAdd, as the cloud page (CLOUD true) or the local one."""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not installed")
    script = people.sim_section()
    flag = "const CLOUD = '__CITY_CLOUD__' === '1';"
    if flag not in script:
        raise AssertionError("the CLOUD constant moved: %s" % flag)
    script = script.replace(flag, "const CLOUD = %s;" % ("true" if cloud else "false"))
    script += "\n" + pure_section() + "\n" + (function_source("cloudAdd") or "")
    with tempfile.TemporaryDirectory() as tmp:
        js = os.path.join(tmp, "sim.js")
        data = os.path.join(tmp, "data.json")
        with open(js, "w", encoding="utf-8") as fh:
            fh.write(people.SIM_JS)
        with open(data, "w", encoding="utf-8") as fh:
            json.dump({"script": script, "driver": driver, "payload": payload, "required": list(required)}, fh)
        result = subprocess.run([node, js, data], capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    if result.returncode != 0 or not result.stdout.strip():
        raise AssertionError("sim harness failed:\n" + result.stderr[-3000:])
    out = json.loads(result.stdout)
    if isinstance(out, dict) and "fatal" in out:
        raise AssertionError("sim harness crashed: " + out["fatal"])
    return out


# A = auto-pipeline: its folder is on the machine shown (here). B = v4-plus: joined, but on another machine.
DRIVER = r"""
var seed = 7;
var crypto = { getRandomValues(a) { for (let i = 0; i < a.length; i++) { seed = (seed * 1103515245 + 12345) & 0x7fffffff; a[i] = seed & 255; } return a; } };
const calls = [];
fetch = function (url, opt) { calls.push({ url, opt }); return new Promise(() => {}); };
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
A.name = 'auto-pipeline'; B.name = 'v4-plus'; A.here = true; B.here = false;
function buildLand(view){ landState(view); }
const ag = (id, label, task, terr) => ({ id, role: 'task-manager', label, task, stuck: false, done: false,
  tools: {}, terr, lead: '', office: null, relay: '' });
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'busy' }], agents: [ag('s:tttt0001', 'checkout Task Manager', 'auto-pipeline', A.id)] });
const NOW = __payload.now;
const mkFeed = (start, ago, talk) => ({ ok: true, user: 'o@example.com', now: NOW, dev: 'mac', orders: [],
  devs: [{ dev: 'mac', label: 'MacBook-Pro', ts: NOW - (ago || 1000), counts: { people: 1, busy: 1, wait: 0 },
           talk: talk !== false, start },
         { dev: 'pc2', label: 'pc2', ts: NOW - 2000, counts: { people: 0, busy: 0, wait: 0 }, talk: true, start: true }] });
const sec = (html, terr) => { const i = html.indexOf('<section class="rail-grp" data-terr="' + terr + '"');
  return i < 0 ? null : html.slice(i, html.indexOf('</section>', i) + 10); };
const draw = adds => railHtml(railGroups(), null, new Set(), new Set(), adds);
const adds = () => railGroups().map(g => g.add);
const out = { a: A.id, b: B.id, cloud: CLOUD };
cloudLive.feed = null; out.noFeed = adds();
cloudLive.feed = mkFeed(false); out.startOff = adds();
cloudLive.feed = mkFeed(true, 200000); out.stale = adds();
cloudLive.feed = mkFeed(undefined); out.noFlag = adds();
cloudLive.feed = mkFeed(true); out.on = adds();
delete A.here; apply({ type: 'world', world: V }); out.noHere = adds();
A.here = true; apply({ type: 'world', world: V });
const st = s => sec(draw(new Map([[A.id, s]])), A.id);
out.plain = sec(draw(new Map()), A.id);
out.plainB = sec(draw(new Map()), B.id);
out.sent = st({ s: 'sent', oid: 'o1' });
out.opening = st({ s: 'opening', oid: 'o1', name: 'auto-pipeline Helper' });
out.openingBare = st({ s: 'opening', oid: 'o1', name: '' });
out.done = st({ s: 'done', oid: 'o1', name: 'auto-pipeline Helper' });
out.cap = st({ s: 'cap', oid: 'o1', ram: 86, cpu: 41, max: 80 });
out.err = st({ s: 'err', oid: 'o1', why: 'Orca <b>broke</b>', retry: false });
out.evil = st({ s: 'done', oid: 'o1', name: '<img src=x onerror=1>' }) + st({ s: 'opening', oid: 'o1', name: '<img src=x onerror=1>' });
if (__payload.pure) {
  out.startOn = [cloudStartOn(null), cloudStartOn({}), cloudStartOn(mkFeed(true)), cloudStartOn(mkFeed(false)),
    cloudStartOn(mkFeed(1)), cloudStartOn(mkFeed(true, 200000)), cloudStartOn(Object.assign(mkFeed(true), { dev: 'gone' })),
    cloudStartOn(Object.assign(mkFeed(false), { dev: 'pc2' }))];
  out.note = [cloudStartNote(null), cloudStartNote(mkFeed(true)), cloudStartNote(mkFeed(false)), cloudStartNote(mkFeed(false, 1000, false)),
    cloudStartNote(mkFeed(true, 1000, false)), cloudStartNote(mkFeed(false, 200000)), cloudStartNote(Object.assign(mkFeed(false), { dev: 'gone' }))];
  const O = (oid, terr, state, more) => Object.assign({ oid, terr, force: false, at: NOW - 5000, ts: NOW - 4000, state, why: '', info: {} }, more || {});
  const view = (orders, hidden) => [...cloudOrderView(orders, NOW, hidden || new Set())];
  out.view = {
    none: view([]), junk: view([null, 5, 'x', {}, { oid: 'o', terr: 't' }]), notArray: view(undefined),
    sent: view([O('o1', 't1', 'sent')]), taken: view([O('o1', 't1', 'taken')]),
    opening: view([O('o1', 't1', 'opening', { info: { name: 'shop Manager', role: 'main' } })]),
    openingNoName: view([O('o1', 't1', 'opening')]),
    opened: view([O('o1', 't1', 'opened', { info: { name: 'shop Manager', role: 'main' }, ts: NOW - 14000 })]),
    openedLongAgo: view([O('o1', 't1', 'opened', { info: { name: 'shop Manager' }, ts: NOW - 15000 })]),
    cap: view([O('o1', 't1', 'cap', { info: { ram: 86, cpu: 41, max: 80 } })]),
    failed: view([O('o1', 't1', 'failed', { why: 'gone' })]),
    newestWins: view([O('o1', 't1', 'failed', { why: 'late', at: NOW - 90000 }), O('o2', 't1', 'sent', { at: NOW - 2000 }),
                      O('o3', 't2', 'opening', { at: NOW - 3000 })]),
    newestWinsAnyOrder: view([O('o2', 't1', 'sent', { at: NOW - 2000 }), O('o1', 't1', 'failed', { why: 'late', at: NOW - 90000 })]),
    hidden: view([O('o1', 't1', 'failed', { why: 'gone' }), O('o2', 't2', 'cap', { info: { ram: 1, cpu: 2, max: 3 } })], new Set(['o1'])),
    hiddenNewest: view([O('o1', 't1', 'opened', { at: NOW - 90000, ts: NOW - 80000 }), O('o2', 't1', 'failed', { why: 'gone', at: NOW - 2000 })], new Set(['o2'])),
    unknownState: view([O('o1', 't1', 'weird')]),
  };
  out.why = {};
  for (const w of __payload.whys) out.why[w] = cloudOrderWhy(O('o1', 't1', 'failed', { why: w, info: { detail: 'orca: <no>' } }));
  out.whyNoInfo = cloudOrderWhy({ state: 'failed', why: 'orca' });
  out.answer = {
    sent: cloudAddAnswer(200, { ok: true, oid: 'o1', state: 'sent', why: '', info: {} }),
    off: cloudAddAnswer(200, { ok: true, oid: 'o1', state: 'failed', why: 'off', info: {} }),
    startOff: cloudAddAnswer(200, { ok: true, oid: 'o1', state: 'failed', why: 'start-off', info: {} }),
    repeatOpening: cloudAddAnswer(200, { ok: true, oid: 'o1', state: 'opening', why: '', info: { name: 'shop Manager' } }),
    busy: cloudAddAnswer(409, { ok: false, error: 'busy', oid: 'o0' }),
    hour: cloudAddAnswer(429, { ok: false, error: 'too many this hour', wait: 1081 }),
    hourSoon: cloudAddAnswer(429, { ok: false, error: 'too many this hour', wait: 3 }),
    day: cloudAddAnswer(429, { ok: false, error: 'too many today' }),
    login: cloudAddAnswer(403, { ok: false, error: 'login required' }),
    none: cloudAddAnswer(0, {}), server: cloudAddAnswer(500, null), bad: cloudAddAnswer(400, { ok: false, error: 'terr' }),
  };
  out.text = {};
  for (const k of __payload.keys) out.text[k] = i18n(k, { name: 'Manager', min: 19, detail: 'why' });
  // one click: the button reads "on its way" at once and ONE request goes out
  addState.clear();
  cloudLive.feed = mkFeed(true);
  cloudAdd(A.id, false);
  out.click = { state: addState.get(A.id) || null, calls: calls.map(c => ({ url: c.url, opt: c.opt })) };
  cloudAdd(A.id, false); cloudAdd(A.id, true);
  out.click.again = calls.length;
  addState.set(A.id, { s: 'opening', oid: 'o1', name: 'x' });
  cloudAdd(A.id, false);
  out.click.whileOpening = calls.length;
  addState.set(A.id, { s: 'cap', oid: 'o1', ram: 86, cpu: 41, max: 80 });
  cloudAdd(A.id, true);
  out.click.confirm = { state: addState.get(A.id) || null, call: calls[calls.length - 1], n: calls.length };
}
__out = out;
"""


def payload(pure=True):
    return {"view": two_territory_view(), "ta": TA, "tb": TB, "now": T0, "pure": pure, "keys": KEYS,
            "whys": list(WHY) + ["talk-off", "", "<b>x</b>"]}


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class CloudCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_page(DRIVER, payload())
        cls.a, cls.b = cls.r["a"], cls.r["b"]

    def button(self, terr):
        return ('<button type="button" class="add-i" data-add="%s" title="加 agent" aria-label="加 agent · auto-pipeline">＋</button>'
                % terr)


class TestWhoGetsTheButton(CloudCase):
    def test_it_runs_as_the_cloud_page(self):
        self.assertIs(self.r["cloud"], True)

    def test_a_repo_on_that_machine_with_start_on(self):
        self.assertEqual(self.r["on"], [True, False], "auto-pipeline is here; v4-plus lives on another machine")
        self.assertIn("</button>" + self.button(self.a) + "</div>", self.r["plain"], "the + ends the repo name row")
        self.assertNotIn("add-line", self.r["plain"])
        self.assertNotIn("data-add", self.r["plainB"])
        self.assertNotIn("add-i", self.r["plainB"])

    def test_no_button_when_the_machine_does_not_take_orders(self):
        for name in ("noFeed", "startOff", "stale", "noFlag", "noHere"):
            self.assertEqual(self.r[name], [False, False], name)

    def test_the_local_page_is_as_before(self):
        r = run_page(DRIVER, payload(pure=False), cloud=False,
                     required=("apply", "landState", "railGroups", "railHtml", "addHtml", "addState", "i18n", "esc"))
        self.assertIs(r["cloud"], False)
        for name in ("noFeed", "startOff", "stale", "noFlag", "on"):
            self.assertEqual(r[name], [True, False], "%s: the local button never looks at a feed" % name)
        self.assertIn(self.button(self.a), r["plain"])
        self.assertIn("正在打开 Helper…", r["opening"])
        self.assertNotIn("那台电脑", r["opening"])
        self.assertIn("<b>电脑有点忙</b>", r["cap"])


class TestStates(CloudCase):
    def test_on_its_way(self):
        html = self.r["sent"]
        self.assertIn('<p class="add-line" role="status" title="已存到云端，等那台电脑来取">在路上…</p>', html)
        self.assertRegex(html, r'<button type="button" class="add-i" aria-disabled="true"[^>]*><span class="spin"></span></button></div>')
        self.assertEqual(html.count("data-add="), 0, "nothing to click while the order is on its way")

    def test_opening_on_the_machine(self):
        self.assertIn('<p class="add-line" role="status">那台电脑正在打开 Helper…</p>', self.r["opening"])
        self.assertRegex(self.r["opening"], r'class="add-i" aria-disabled="true"[^>]*><span class="spin"></span></button></div>')
        self.assertIn('<p class="add-line" role="status">那台电脑正在打开…</p>', self.r["openingBare"])

    def test_opened(self):
        self.assertIn('<div class="addbox ok" role="status">已打开 Helper · 小人马上出现</div>', self.r["done"])
        self.assertNotIn("data-add=", self.r["done"], "the button comes back when the box goes")
        self.assertIn('<span class="add-i ok" aria-hidden="true">✓</span></div>', self.r["done"], "the + is a tick meanwhile")

    def test_over_the_cap(self):
        html = self.r["cap"]
        self.assertIn('<div class="addbox cap" role="alert"><b>那台电脑有点忙</b>', html)
        self.assertIn('<span class="nums">RAM 86% · CPU 41%（上限 80%）</span>', html)
        self.assertIn("还要打开吗？", html)
        self.assertIn('<button type="button" class="mini main" data-add-go="%s">还是打开</button>' % self.a, html)
        self.assertIn('<button type="button" class="mini" data-add-no="%s">取消</button>' % self.a, html)

    def test_not_opened(self):
        html = self.r["err"]
        self.assertIn('<div class="addbox err" role="alert"><b>没打开：</b>Orca &lt;b&gt;broke&lt;/b&gt;', html)
        self.assertIn('data-add-no="%s">知道了</button>' % self.a, html)
        self.assertNotIn("再试", html, "a new click is a new order: no retry button for an order that failed")

    def test_a_name_from_the_feed_is_escaped(self):
        self.assertNotIn("<img", self.r["evil"])

    def test_css(self):
        self.assertRegex(css(), r"\.addbox\.ok\s*\{")


class TestPure(CloudCase):
    def test_start_on(self):
        self.assertEqual(self.r["startOn"], [False, False, True, False, False, False, False, True])

    def test_the_note(self):
        self.assertEqual(self.r["note"], ["", "", "cloud.start.off", "cloud.start.needTalk", "cloud.start.needTalk", "", ""])

    def view(self, name):
        return {terr: st for terr, st in self.r["view"][name]}

    def test_nothing(self):
        for name in ("none", "junk", "notArray", "unknownState", "openedLongAgo"):
            self.assertEqual(self.r["view"][name], [], name)

    def test_one_state_each(self):
        self.assertEqual(self.view("sent"), {"t1": {"s": "sent", "oid": "o1"}})
        self.assertEqual(self.view("taken"), {"t1": {"s": "sent", "oid": "o1"}})
        self.assertEqual(self.view("opening"), {"t1": {"s": "opening", "oid": "o1", "name": "shop Manager"}})
        self.assertEqual(self.view("openingNoName"), {"t1": {"s": "opening", "oid": "o1", "name": ""}})
        self.assertEqual(self.view("opened"), {"t1": {"s": "done", "oid": "o1", "name": "shop Manager"}})
        self.assertEqual(self.view("cap"), {"t1": {"s": "cap", "oid": "o1", "ram": 86, "cpu": 41, "max": 80}})
        self.assertEqual(self.view("failed"), {"t1": {"s": "err", "oid": "o1", "why": self.r["why"]["gone"], "retry": False}})

    def test_the_newest_order_of_a_repo_decides(self):
        want = {"t1": {"s": "sent", "oid": "o2"}, "t2": {"s": "opening", "oid": "o3", "name": ""}}
        self.assertEqual(self.view("newestWins"), want)
        self.assertEqual(self.view("newestWinsAnyOrder"), {"t1": {"s": "sent", "oid": "o2"}})

    def test_a_hidden_order_shows_nothing(self):
        self.assertEqual(self.view("hidden"), {"t2": {"s": "cap", "oid": "o2", "ram": 1, "cpu": 2, "max": 3}})
        self.assertEqual(self.view("hiddenNewest"), {}, "the newest one is hidden: an older one does not come back")

    def test_every_reason_has_its_own_words(self):
        why = self.r["why"]
        for code, key in WHY.items():
            want = self.r["text"]["add.cloud.why." + key]
            if code == "orca":
                self.assertEqual(why[code], "Orca 没能开出终端：orca: <no>", "the detail goes in as text; addHtml escapes it")
            else:
                self.assertEqual(why[code], want, code)
        self.assertEqual(len(set(why[c] for c in WHY)), len(WHY))
        for code in ("talk-off", "", "<b>x</b>"):
            self.assertEqual(why[code], self.r["text"]["add.cloud.why.other"], code)
        self.assertIn("Orca", self.r["whyNoInfo"])

    def test_the_answer_of_the_order(self):
        a = self.r["answer"]
        t = self.r["text"]
        self.assertEqual(a["sent"], {"s": "sent", "oid": "o1"})
        self.assertEqual(a["off"], {"s": "err", "oid": "o1", "why": t["add.cloud.why.off"], "retry": False})
        self.assertEqual(a["startOff"]["why"], t["add.cloud.why.startOff"])
        self.assertEqual(a["repeatOpening"], {"s": "opening", "oid": "o1", "name": "shop Manager"})
        self.assertEqual(a["busy"], {"s": "sent", "oid": "o0"}, "that repo already has an order on its way: show that one")
        self.assertEqual((a["hour"]["s"], a["hour"]["why"], a["hour"]["retry"]), ("err", t["add.cloud.tooMany"], False))
        self.assertIn("19", a["hour"]["why"], "1081 s = 19 minutes, rounded up")
        self.assertRegex(a["hourSoon"]["why"], r"(?<!\d)1 ?分钟", "3 s: at least one minute is said")
        self.assertEqual(a["day"]["why"], t["add.cloud.tooManyDay"])
        self.assertEqual((a["login"]["s"], a["login"]["retry"]), ("err", False))
        for name in ("none", "server", "bad"):
            self.assertEqual((a[name]["s"], a[name]["why"], a[name]["retry"]), ("err", t["add.cloud.noAnswer"], False), name)


class TestOneClickOneOrder(CloudCase):
    def test_the_button_reads_on_its_way_at_once(self):
        st = self.r["click"]["state"]
        self.assertEqual(st["s"], "sent")
        self.assertRegex(st["oid"], r"^[A-Za-z0-9_-]{16,64}$")

    def test_one_request_with_the_order_and_nothing_else(self):
        calls = self.r["click"]["calls"]
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["url"], "/api/agent/add")
        opt = call["opt"]
        self.assertEqual(opt["method"], "POST")
        self.assertEqual(opt["headers"], {"Content-Type": "application/json", "X-City-Page": "1"},
                         "the page header, JSON, and no token of the local page")
        body = json.loads(opt["body"])
        self.assertEqual(body, {"dev": "mac", "terr": self.a, "oid": self.r["click"]["state"]["oid"]},
                         "a territory id and the click's id: no path, name, model, flag or text")

    def test_a_double_click_is_one_order(self):
        self.assertEqual(self.r["click"]["again"], 1)
        self.assertEqual(self.r["click"]["whileOpening"], 1)

    def test_the_confirm_is_a_second_order(self):
        c = self.r["click"]["confirm"]
        self.assertEqual(c["n"], 2)
        body = json.loads(c["call"]["opt"]["body"])
        self.assertEqual(set(body), {"dev", "terr", "oid", "force"})
        self.assertIs(body["force"], True)
        self.assertNotEqual(body["oid"], self.r["click"]["state"]["oid"], "a new id")
        self.assertEqual(c["state"]["s"], "sent")


class TestTexts(CloudCase):
    def test_both_languages(self):
        t = tp.js_value(tp.const_object("TEXT") or "null") or {}
        for key in KEYS:
            for lang in ("zh", "en"):
                self.assertTrue(t.get(lang, {}).get(key), "%s has no %s text" % (key, lang))
        zh = t["zh"]
        want = {"add.cloud.sent": "在路上…", "add.cloud.opening": "那台电脑正在打开 {name}…",
                "add.cloud.done": "已打开 {name} · 小人马上出现", "add.cloud.cap": "那台电脑有点忙",
                "cloud.start.on": "可开 agent", "add.cloud.why.orca": "Orca 没能开出终端：{detail}"}
        for key, text in want.items():
            self.assertEqual(zh[key], text, key)
        self.assertIn("那台电脑没开", zh["add.cloud.why.off"])
        self.assertIn("以后也不会再开", zh["add.cloud.why.off"])
        self.assertIn("那台电脑不能自己开终端", zh["add.cloud.why.noOrca"])
        self.assertIn("{detail}", zh["add.cloud.why.orca"])
        self.assertIn("60 秒", zh["add.cloud.why.late"])
        self.assertRegex(zh["add.cloud.why.flood"], r"一小时.*10 个", "the machine's own cap: 10 opens an hour")
        self.assertIn("不认这个仓库", zh["add.cloud.why.refused"])
        self.assertIn("3 分钟", zh["add.cloud.why.silent"])
        self.assertIn("{min}", zh["add.cloud.tooMany"])
        for lang in ("zh", "en"):
            self.assertIn("agent-city cloud-start on", t[lang]["cloud.start.off"])
            self.assertIn("agent-city cloud-start on", t[lang]["add.cloud.why.startOff"])
            self.assertIn("agent-city cloud-talk on", t[lang]["cloud.start.needTalk"])
            self.assertIn("agent-city cloud-start on", t[lang]["cloud.start.needTalk"])

    def test_later_no_longer_names_the_add_button(self):
        t = tp.js_value(tp.const_object("TEXT") or "null") or {}
        for lang in ("zh", "en"):
            self.assertNotIn("cloud.later.add", t.get(lang, {}))
        self.assertNotIn("cloud.later.add", tp.inline_script())
        for key in ("cloud.later.ask", "cloud.later.demo"):
            self.assertIn("以后开放", t["zh"][key], "approve and the demo tools are still later")


class TestWiring(unittest.TestCase):
    def fn(self, name):
        src = function_source(name)
        self.assertTrue(src, "function %s is missing" % name)
        return src

    def cloud_script(self):
        text = tp.inline_script()
        return text[text.index("/* cloud-city: script"):text.index("/* end cloud-city: script */")]

    def test_add_agent_hands_over_before_the_local_fetch(self):
        src = self.fn("addAgent")
        head = src[:src.index("fetch(")]
        self.assertRegex(head, r"if \(CLOUD\) return cloudAdd\(terr, force\);")
        self.assertIn("X-City-Token", src[src.index("fetch("):], "the local page's request is unchanged")

    def test_add_html_no_longer_hides_on_the_cloud_page(self):
        self.assertNotRegex(self.fn("addHtml"), r"if \(CLOUD\) return '';")

    def test_cloud_add_lives_in_the_cloud_script(self):
        block = self.cloud_script()
        self.assertIn("function cloudAdd(", block)
        src = self.fn("cloudAdd")
        self.assertIn("cloudCid()", src)
        self.assertNotIn("X-City-Token", src)
        self.assertNotIn("TOKEN", src)
        self.assertIn("CLOUD_SEND_TRIES", block, "no answer: the same order again, the same id")
        self.assertIn("cloudAddAnswer(", block)

    def test_the_buttons_follow_the_feed(self):
        block = self.cloud_script()
        self.assertIn("cloudOrderView(", block)
        self.assertRegex(block, r"\.orders\b")

    def test_the_machine_row_says_who_starts(self):
        src = self.fn("cloudRenderRow")
        self.assertIn("cloud.start.on", src)
        self.assertRegex(src, r"\.start === true")

    def test_the_note_at_the_rails_foot(self):
        block = self.cloud_script()
        self.assertIn("cloudStartNote(", block)
        self.assertNotIn("cloud.later.add", self.fn("cloudSetup"), "the old chip in the rail (＋ 加 agent · 以后开放) is gone")

    def test_only_known_addresses(self):
        urls = set(re.findall(r"fetch\(\s*'([^']+)'", tp.inline_script()))
        self.assertLessEqual(urls, {"/api/chat?to=", "/api/chat/send", "/api/decide", "/api/agent/add",
                                    "/api/layout"})   # city-layout: the local page's arrange mode; the cloud page never opens it (arrEnter)


if __name__ == "__main__":
    unittest.main()
