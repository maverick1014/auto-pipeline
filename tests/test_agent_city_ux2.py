"""Failing tests for city-ux2 (owner, 2026-09-29, after using 0.10.0; mock v2 mock/city-ux2-mock.html, 21b5788,
after the owner's review of v1: "the tab is too big ... when I click an agent, no need to show the middle panel
any more, directly show the message" + "the online panel should be able to collapse and expand").

CONTRACT (bin/agent-city.html). "sim section" = the page script from 'use strict' up to the '3D view.'
comment: every function named "(sim)" below lives there, needs no three.js and no DOM, and is driven
straight by these tests (tests/test_agent_city_people.py run_sim). Everything else is "3D part".

V1 a compact left rail = the team list; a click on a person = follow it + its message panel
  (sim) REPO_COLORS: at least 6 distinct '#rrggbb' colours. terrColor(terr) -> REPO_COLORS[i % length],
        i = the territory's index in map.territories; '#8D91B3' for a territory not in the map.
  (sim) railGroups() -> [{terr, name, color, rows: [{id, depth, rest}]}], in map order, one per territory
        (city-add-agent A1, owner 2026-10-01: also a territory with nobody here, rows []; before, it was left out). Rows, in this order:
        'gov:<terr>' (depth 0, rest false) first, only while that territory has a governor figure
        (governorFigures()); then that territory's rosterGroups() rows without its governor row (leads,
        each followed by its workers at depth 1, then the others); then every other member's person in
        it (c.remote, not gone; depth 0). Last, every row whose person rests (citizenStatus(c)[0] ===
        'rest') is moved to the end of its group with rest: true, the order among them kept.
        name = the territory's name, color = terrColor(terr).
  (sim) railCount(groups) -> {active, you}: active = rows that are not resting (cloud-polish Q2, 2026-10-02:
        the governor's row counts too, it is a session); you = those among them waiting on the owner (a
        citizen whose citizenStatus(c)[0] === 'you', a governor whose state is 'waiting').
  (sim) railHtml(groups, selId, closed, openRest) -> the HTML of #rail-list. selId = the selected row id
        (selKey(selected)); closed = a Set of terr ids folded by the owner; openRest = a Set of terr ids whose
        resting rows are shown. Per group:
          <section class="rail-grp" data-terr="<terr>" ...>, then the head, a button:
          <button type="button" class="grp-h" data-grp="<terr>" aria-expanded="<not closed>"> with
          <span class="rc" style="--rc:<color>">, the escaped territory name, <span class="n"> = the number
          of rows in the group (city-polish P4: everyone, the governor and resting people too), and, only while
          the group is closed and has people waiting on the owner, <span class="you"> with that number.
          While not closed: <ul class="rrows"> with one <li> per non-resting row; when the group has
          resting rows, <button type="button" class="rest-t" data-rest="<terr>" aria-expanded="true|false">
          with i18n('rail.rest', {n}); and only when openRest has terr, a second <ul class="rrows"> with the
          resting rows. A closed group shows its head only.
        A row is ONE button (no open button any more):
          <button type="button" class="rrow[ sub][ resting]" data-focus="<row id>"
          aria-current="<row id === selId>" style="--rc:<color>"> holding <span class="sdot st-<chip class>"> (the
          state dot, city-polish P4), <b> with the escaped name (the governor: i18n who.governor; a person: nameOf(c)) and
          <span class="chip <group>"> with the state words (the governor: class gov, govRowText(terr); a
          person: citizenStatus(c)). Everything escaped.
  (sim) selKey(sel) -> the rail row id of a selection: {t:'c', id} -> id; {t:'gov', terr} -> 'gov:' +
        (terr || govTerr); anything else (a building, a remote governor, null) -> null.
  (sim) let follow = null (the followed row id); FOLLOW_DIST (4 .. 7): how close a follow flies.
        followPos(id) -> [x, z] in scene coordinates (world - mid) of that person ('gov:<terr>': its
        governorFigures() entry; else the citizen, not gone), or null.
        startFollow(id): does nothing when followPos(id) is null; else follow = id and a fly
        (flyTo) to the person at Math.min(cam.dist, FOLLOW_DIST) -- never zooms out to follow -- whose end
        point keeps tracking the person while it flies (camFly.follow = id).
        stopFollow(): follow = null, and a fly started by startFollow is cancelled.
        toggleFollow(id): follow === id ? stopFollow() : startFollow(id).
        cameraStep(dt) also follows: while follow is set and no fly runs, cam.tx/tz move to followPos
        (eased at about 8 per second: k = 1 - exp(-8 dt); a sprinting person stays within 0.15 tiles of
        the middle); followPos null (gone) -> stopFollow(). It never touches cam.el, cam.dist after the
        fly, or cam.az (only the never-stop rotation turns it).
        stopFly() never ends a follow (a zoom during the fly-in just ends the fly).
  (sim) tagVisible(hover, selected, followed) -> !!(hover || selected || followed): the followed person
        shows its name tag like a selected one. updatePerson passes the follow check as the third arg.
  (sim) freeCentre(w, h, rail, win) -> [cx, cy], the middle of the map you can see, stage px.
        rail = {right} (the rail's, or its folded tab's, right edge; a computer) or null (a phone: the
        drawer is only out for a moment); win = the box {left, top, right, bottom} of the message panel,
        or its folded tab, whichever shows (a phone: the sheet, or null while folded), else null.
        x0 = rail ? rail.right : 0, x1 = w, y0 = 0, y1 = h. A win spanning the width (left <= x0 + 20 and
        right >= w - 20: the phone sheet) -> y1 = win.top; else a win on the right half (left >= w / 2)
        -> x1 = win.left; else (on the left) -> x0 = max(x0, win.right). Never a sliver: x1 - x0 < 160 ->
        x0 = 0 and x1 = w; y1 - y0 < 120 -> y1 = h.
  3D part:
    Picking a person = following it. selectPick(pk) and selectFrom(val) (every way to pick: a rail row, a
        person or head tag or bubble in the city, the find-lead button) both call afterPick() once
        `selected` is set. afterPick(): a person or governor (selKey(selected) not null) ->
        toggleFollow(selKey(selected)) (so a second click on the followed person stops following, its
        panel stays); anything else, and a tap on empty ground (selectPick(null): the panel closes) ->
        stopFollow(). It also calls setWinFolded(false) when something is selected (a pick shows the
        panel even when it was folded) and, on a phone, setRailFolded(true). renderWin() shows #win or
        #win-tab by winFolded and keeps the tab's name and badge current.
    The message panel is #win, docked right: .win right:12px, top:12px, bottom:12px, width var(--msg-w)
        (--msg-w 360 .. 400px since city-polish P2; was 300 .. 360); no two columns, no team list, no 'wide' (see test_agent_city_ux_page U5,
        U10, U11 notes); winTitle() = the person's name (nameOf; the governor: its gov.title). The
        building card, a site and the page log (动态) show in the same panel. The "?" ask panel stays.
    Folding: #rail and #win each fold to a thin tab on their edge. Markup: in the rail head
        <button type="button" class="fold" id="rail-fold" data-t-aria="fold.rail">; after the rail
        <button type="button" class="tab rail-tab" id="rail-tab" aria-controls="rail" hidden> (the count
        i18n rail.tab {n} + a <span class="you"> badge); in the window head, before #win-close,
        <button type="button" class="fold" id="win-fold" data-t-aria="fold.msg">; after #win
        <button type="button" class="tab win-tab" id="win-tab" aria-controls="win" hidden> (i18n msg.tab
        {name} + a badge with the number of new messages since it was folded). setRailFolded(v) and
        setWinFolded(v) set the state, save it in localStorage ('agent-city.railFolded',
        'agent-city.winFolded', '1' / '0', every read and write in try/catch) and redraw; the page reads
        both at start (a phone with nothing saved starts with the rail folded). The folded groups are
        saved too ('agent-city.railClosed', comma-joined terr ids). #rail-fold / #rail-tab and #win-fold /
        #win-tab click listeners call them.
    Markup inside #stage (after the canvas overlay, before .cam): <aside class="rail" id="rail"
        data-t-aria="rail.title"> with a head (data-t="rail.title", <span class="n" id="rail-n">, <span
        class="you" id="rail-you" hidden>, #rail-fold) and <div class="rail-list" id="rail-list">; the rail
        tab; <div class="follow" id="follow" role="status" hidden> with <span id="follow-t"> and <button
        type="button" id="follow-stop" data-t="follow.stop">. The #win tab after #win.
    renderRail(): railHtml(railGroups(), selKey(selected), railClosed, railRestOpen) into #rail-list only
        when it changed (lastRail); #rail-n = i18n rail.count {n: active}; #rail-you / the tab badge =
        the you count (hidden at 0); the rail or its tab shows, by railFolded. renderPanel() calls it.
    #rail-list click: [data-grp] toggles railClosed (saved); [data-rest] toggles railRestOpen;
        [data-focus] -> selectFrom(id).
    Building card: renderDetail's building branch has <button type="button" class="b-focus"
        data-focus-b="<building id>"> (i18n b.focus); the #detail click listener: stopFollow() then
        flyTo(the building's scene x/z, Math.min(cam.dist, FOLLOW_DIST)).
    Follow chip: renderFollow() (frame() calls it; touches the DOM only on change): #follow hidden
        unless follow; #follow-t = i18n follow.on {name}; left = the free centre x. #follow-stop ->
        stopFollow(). Esc (document keydown, e.key === 'Escape', only when following) -> stopFollow().
    Stops following: the same person again, empty ground, Esc, #follow-stop, the repo tags (All too),
        #zfit, a pan (panBy calls stopFollow()). Keeps it: dragBy (orbit), zoomStep, pinch/gesture/wheel
        zoom, the rotation, folding either panel.
    The map is centred on the free part: updateCamera() eases a shift toward freeCentre(W, H, the rail /
        rail tab box on a computer, the #win / #win-tab box) and sets camera.setViewOffset (so pickAt and
        toScreen stay right). The zoom buttons (.cam) sit left of the panel: a CSS rule places .cam with
        var(--msg-w) while the panel shows.
    The wheel listener also leaves wheels inside .rail alone (the list scrolls).
    renderRepos(): each repo tag gets <span class="rc" style="--rc:<terrColor>">.
    CSS: --rail-w (190 .. 230px) and --msg-w on .stage or :root; .rail position:absolute, left 12px,
        width var(--rail-w), max-height calc(100% - 24px); .proto sits right of the rail (var(--rail-w)).
        .tab is position:absolute. @media (max-width: 960px): the rail is a drawer from its tab (.rail
        full height at the left edge), .win a bottom sheet (top:auto, bottom, about half the height),
        .stage.drawer-open hides .win and .ask-panel while the rail is out.
    New TEXT keys, zh and en: rail.title, rail.count, rail.rest, rail.tab, fold.rail, fold.msg, msg.tab,
        follow.on, follow.stop, b.focus.

V2 two-finger sideways scroll moves the land the same way up/down does (unchanged from mock v1)
  (sim) wheelMove(e, h): no ctrlKey -> { pan: [deltaX * unit, -deltaY * unit] } (was -deltaX: the X axis
        went the other way from Y). ctrlKey zoom unchanged.
  (sim) panDelta(dx, dy, az, el, dist, h) -> [dtx, dtz], the look-point move panBy() makes for a pan of
        (dx, dy) px (before its clamp to the land); panBy() uses it. Composed: a wheel of (deltaX, deltaY)
        moves the land on screen the way of (+deltaX, +deltaY) -- both axes, both signs, any angle.
        No invert option; pinch stays zoom.

V3 head tags and bubbles are easy to hit
  CSS: .bub::after, .tagl::after, .qm::after, .rdev::after: content "", position absolute, inset -8px (at
        least 6 px each side, so the hit area is at least 12 px bigger than the box). .bub itself is not
        overflow:hidden (a clipped ::after takes no clicks); its ellipsis moves to an inner element.

Run: python3 -m unittest tests.test_agent_city_ux2 </dev/null
"""

import math
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import function_source, page, run_sim, sim_section  # noqa: E402
from test_agent_city_chain import TA, TB, two_territory_view  # noqa: E402
from test_agent_city_ux_page import css, listener_block, media_960, rule, text_keys  # noqa: E402

FOV = 40


def sim_has(name):
    return re.search(r"(?:function\s+%s\s*\(|(?:const|let)\s+%s\s*=)" % (re.escape(name), re.escape(name)),
                     sim_section()) is not None


def px(value):
    m = re.search(r"(-?\d+(?:\.\d+)?)px", value or "")
    return float(m.group(1)) if m else None


SNAPSHOT = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
const OF = A.offices[0];
function buildLand(view){ landState(view); }
const ag = (id, role, task, terr, lead, office) => ({ id, role, label: role, task, stuck: false, done: false, tools: {},
  terr, lead: lead || '', office: office || null, relay: '' });
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'busy' }], agents: [
  ag('s:L', 'task-manager', 'city <b>', A.id, '', { x: OF.x, z: OF.z }),
  ag('w1', 'worker', 'rail', A.id, 's:L'),
  ag('w2', 'worker', 'nap', A.id, 's:L'),
  ag('f1', 'fast-lane-deputy', 'typo', A.id),
  ag('y1', 'worker', 'far', B.id),
  ag('y2', 'worker', 'sleepy', B.id),
]});
byId('w2').state = 'resting'; byId('y2').state = 'resting';
const rp = newCitizen('r:dev-ann:s:9', 'worker', 'ann task', A.id);
rp.remote = { who: 'Ann', device: 'lap', dev: 'dev-ann', rid: 'acme/shop', br: 'b' }; citizens.push(rp);
"""

PAYLOAD = None


def payload():
    global PAYLOAD
    if PAYLOAD is None:
        PAYLOAD = {"view": two_territory_view(), "ta": TA, "tb": TB}
    return PAYLOAD


# ---------------------------------------------------------------------------
# V1: the rail data
# ---------------------------------------------------------------------------

RAIL_DRIVER = SNAPSHOT + r"""
const G = railGroups();
const ids = h => [...h.matchAll(/data-focus="([^"]*)"/g)].map(m => m[1]);
const cur = h => [...h.matchAll(/<button\b[^>]*>/g)].map(m => m[0]).filter(t => /aria-current="true"/.test(t))
  .map(t => (/data-focus="([^"]*)"/.exec(t) || [])[1]);
const shut = new Set(), none = new Set();
const plain = railHtml(G, 'w1', shut, none), open = railHtml(G, null, shut, new Set([A.id]));
byId('y1').waiting = true;
const closedB = railHtml(railGroups(), null, new Set([B.id]), none);
const cnt1 = railCount(railGroups());
byId('y1').waiting = false;
const cnt0 = railCount(G);
byId('y1').gone = true; byId('y2').gone = true;
const noB = railGroups().map(g => [g.terr, g.rows.length]);
__out = { a: A.id, b: B.id, terrs: map.territories.map(t => t.id), colors: REPO_COLORS,
  cA: terrColor(A.id), cB: terrColor(B.id), cX: terrColor('nope'),
  groups: G.map(g => ({ terr: g.terr, name: g.name, color: g.color, rows: g.rows.map(r => [r.id, r.depth, !!r.rest]) })),
  names: [A.name, B.name], plain, open, closedB,
  plainIds: ids(plain), openIds: ids(open), closedIds: ids(closedB), cur: cur(plain), curNone: cur(open),
  restA: i18n('rail.rest', { n: 1 }), cnt0, cnt1, noB,
  keys: [selKey({ t: 'c', id: 'w1' }), selKey({ t: 'gov', terr: B.id }), selKey({ t: 'gov' }), selKey({ t: 'b', id: 'x' }),
         selKey({ t: 'rg', id: 'q' }), selKey(null)], home: govTerr };
"""


class TestRailData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(RAIL_DRIVER, payload(), ("apply", "landState", "railGroups", "railHtml", "railCount", "selKey",
                                                 "terrColor", "REPO_COLORS", "newCitizen", "citizens", "byId"))

    def test_repo_colours(self):
        cols = self.r["colors"]
        self.assertGreaterEqual(len(cols), 6)
        self.assertEqual(len(set(c.lower() for c in cols)), len(cols), "distinct")
        for c in cols:
            self.assertRegex(c, r"^#[0-9A-Fa-f]{6}$")
        terrs = self.r["terrs"]
        self.assertEqual(self.r["cA"], cols[terrs.index(self.r["a"]) % len(cols)])
        self.assertEqual(self.r["cB"], cols[terrs.index(self.r["b"]) % len(cols)])
        self.assertNotEqual(self.r["cA"], self.r["cB"])
        self.assertEqual(self.r["cX"].upper(), "#8D91B3")

    def test_groups_in_map_order_with_team_order_and_rest_last(self):
        g = {x["terr"]: x for x in self.r["groups"]}
        order = [x["terr"] for x in self.r["groups"]]
        self.assertEqual(order, [t for t in self.r["terrs"] if t in g], "map order")
        a = g[self.r["a"]]
        self.assertEqual(a["rows"], [["gov:" + self.r["a"], 0, False], ["s:L", 0, False], ["w1", 1, False],
                                     ["f1", 0, False], ["r:dev-ann:s:9", 0, False], ["w2", 1, True]])
        self.assertEqual(a["color"], self.r["cA"])
        b = g[self.r["b"]]
        self.assertEqual(b["rows"], [["y1", 0, False], ["y2", 0, True]], "no governor row while B has no governor")
        self.assertEqual([a["name"], b["name"]], self.r["names"])

    def test_empty_territory_keeps_its_group(self):
        """city-add-agent A1 (owner, 2026-10-01) replaces "a territory with nobody here is left out"."""
        self.assertEqual([g[0] for g in self.r["noB"]], [self.r["a"], self.r["b"]])
        self.assertEqual(self.r["noB"][1][1], 0, "B has nobody: its group stays, with no rows")

    def test_counts(self):
        # cloud-polish Q2 (2026-10-02): a governor is a session, its row counts (tests/test_agent_city_cloud_polish.py)
        self.assertEqual(self.r["cnt0"], {"active": 6, "you": 0}, "gov s:L w1 f1 remote y1")
        self.assertEqual(self.r["cnt1"], {"active": 6, "you": 1})

    def test_sel_key(self):
        a, b = self.r["a"], self.r["b"]
        self.assertEqual(self.r["keys"], ["w1", "gov:" + b, "gov:" + self.r["home"], None, None, None])

    def test_rows_are_single_buttons(self):
        a = self.r["a"]
        self.assertEqual(self.r["plainIds"], ["gov:" + a, "s:L", "w1", "f1", "r:dev-ann:s:9", "y1"], "resting rows folded")
        self.assertEqual(self.r["openIds"], ["gov:" + a, "s:L", "w1", "f1", "r:dev-ann:s:9", "w2", "y1"])
        self.assertEqual(self.r["cur"], ["w1"], "the selected row")
        self.assertEqual(self.r["curNone"], [])
        h = self.r["plain"]
        self.assertNotIn("data-open", h, "no open buttons any more")
        self.assertNotIn("ropen", h)
        self.assertRegex(h, r'<button type="button" class="rrow[^"]*" data-focus="w1"')
        self.assertRegex(h, r'class="rrow sub[^"]*" data-focus="w1"', "a worker under its lead")
        self.assertIn('class="sdot st-gov"', h)  # city-polish P4: the dot has the state colour
        self.assertIn('class="chip gov"', h)
        self.assertIn("--rc:%s" % self.r["cA"], h)
        self.assertNotIn("city <b>", h, "escaped")
        self.assertIn("city &lt;b&gt;", h)
        self.assertIn("resting", self.r["open"])

    def test_group_heads(self):
        a, b = self.r["a"], self.r["b"]
        h = self.r["plain"]
        self.assertRegex(h, r'<section class="rail-grp" data-terr="%s"' % re.escape(a))
        self.assertRegex(h, r'<button type="button" class="grp-h" data-grp="%s" aria-expanded="true"' % re.escape(a))
        self.assertRegex(h, r'data-grp="%s"[^>]*>[\s\S]*?<span class="n">\s*6\s*</span>' % re.escape(a),
                         "A: everyone -- gov s:L w1 f1 remote w2 (city-polish P4)")
        self.assertRegex(h, r'data-rest="%s"[^>]*aria-expanded="false"|aria-expanded="false"[^>]*data-rest="%s"' % (re.escape(a), re.escape(a)))
        self.assertRegex(self.r["open"], r'data-rest="%s"[^>]*aria-expanded="true"|aria-expanded="true"[^>]*data-rest="%s"' % (re.escape(a), re.escape(a)))
        self.assertIn(self.r["restA"], h)

    def test_closed_group_shows_its_head_only(self):
        b = self.r["b"]
        h = self.r["closedB"]
        self.assertRegex(h, r'data-grp="%s" aria-expanded="false"' % re.escape(b))
        self.assertNotIn("y1", self.r["closedIds"], "B's rows are folded away")
        self.assertIn("r:dev-ann:s:9", self.r["closedIds"], "A stays open")
        sec = h[h.index('data-terr="%s"' % b):]
        self.assertRegex(sec, r'<span class="you">\s*1\s*</span>', "a closed group still shows who waits on you")
        self.assertNotIn('data-rest="%s"' % b, sec)


# ---------------------------------------------------------------------------
# V1: follow
# ---------------------------------------------------------------------------

FOLLOW_DRIVER = SNAPSHOT + r"""
const out = {};
cam.dist = 20; cam.el = EL_DEFAULT;
const el0 = cam.el, az0 = cam.az, c = byId('w1');
startFollow('w1');
out.start = { follow, fly: !!camFly, flyFollow: camFly && camFly.follow };
for (let i = 0; i < 120; i++) { c.x += .012; cameraStep(1 / 60); }  // 0.72 tiles a second: a sprint
const P = followPos('w1');
out.after = { tx: cam.tx, tz: cam.tz, px: P[0], pz: P[1], dist: cam.dist, el: cam.el, el0, daz: cam.az - az0, fly: !!camFly };
out.pos = { p: P, want: [c.x - mid.x, c.y - mid.z] };
cam.dist = 3.1;
for (let i = 0; i < 30; i++) { c.x += .012; cameraStep(1 / 60); }
out.zoomKeep = { follow, dist: cam.dist };
toggleFollow('w1'); out.toggleOff = follow;
toggleFollow('w1'); out.toggleOn = follow;
startFollow('gov:' + A.id); out.gov = { follow, pos: followPos('gov:' + A.id) };
stopFollow(); out.stopped = { follow, fly: camFly };
startFollow('y1'); byId('y1').gone = true; cameraStep(1 / 60); out.gone = follow;
startFollow('nobody'); out.unknown = follow;
out.nullPos = [followPos('nobody'), followPos('gov:' + B.id)];
cam.dist = 3; startFollow('f1'); for (let i = 0; i < 90; i++) cameraStep(1 / 60); out.closer = cam.dist;
stopFollow(); cam.dist = 20; startFollow('f1'); stopFly(); out.stopFlyKeeps = follow;
out.FD = FOLLOW_DIST; out.AUTO = AUTO_ROT_SEC; out.dir = autoRotDir; out.RM = RM;
out.tags = [tagVisible(false, false, true), tagVisible(false, false, false), tagVisible(false, true), tagVisible(true, false)];
__out = out;
"""


class TestFollow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(FOLLOW_DRIVER, payload(), ("apply", "landState", "startFollow", "stopFollow", "toggleFollow",
                                                   "followPos", "FOLLOW_DIST", "cameraStep", "flyTo", "stopFly",
                                                   "tagVisible", "cam", "byId", "newCitizen", "citizens"))

    def test_start_flies_and_follows(self):
        r = self.r
        self.assertTrue(4 <= r["FD"] <= 7, r["FD"])
        self.assertEqual(r["start"], {"follow": "w1", "fly": True, "flyFollow": "w1"})
        a = r["after"]
        self.assertFalse(a["fly"], "the fly is over after 2 s")
        self.assertLess(abs(a["tx"] - a["px"]), .15, "centred on the walking person")
        self.assertLess(abs(a["tz"] - a["pz"]), .15)
        self.assertAlmostEqual(a["dist"], r["FD"], places=6, msg="flew in to FOLLOW_DIST")
        self.assertEqual(a["el"], a["el0"], "never touches the owner's tilt")

    def test_rotation_untouched(self):
        a, r = self.r["after"], self.r
        want = 0 if r["RM"] else r["dir"] * 2 * 2 * math.pi / r["AUTO"]
        self.assertAlmostEqual(a["daz"], want, places=6, msg="only the never-stop rotation turns cam.az")

    def test_follow_pos_is_scene(self):
        p = self.r["pos"]
        self.assertAlmostEqual(p["p"][0], p["want"][0], places=9)
        self.assertAlmostEqual(p["p"][1], p["want"][1], places=9)
        self.assertEqual(self.r["nullPos"], [None, None], "unknown person / no governor figure")

    def test_zoom_and_toggle(self):
        r = self.r
        self.assertEqual(r["zoomKeep"], {"follow": "w1", "dist": 3.1}, "a zoom keeps the follow and its distance")
        self.assertIsNone(r["toggleOff"])
        self.assertEqual(r["toggleOn"], "w1")
        self.assertEqual(r["gov"]["follow"], "gov:" + payload()["ta"])
        self.assertIsNotNone(r["gov"]["pos"])

    def test_stops(self):
        r = self.r
        self.assertEqual(r["stopped"], {"follow": None, "fly": None})
        self.assertIsNone(r["gone"], "the person left: the follow ends by itself")
        self.assertIsNone(r["unknown"])
        self.assertEqual(r["stopFlyKeeps"], "f1", "stopFly (a zoom) never ends the follow")

    def test_never_zooms_out_to_follow(self):
        self.assertAlmostEqual(self.r["closer"], 3, places=6)

    def test_followed_tag_shows(self):
        self.assertEqual(self.r["tags"], [True, False, True, True])


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


# ---------------------------------------------------------------------------
# V1: the 3D part
# ---------------------------------------------------------------------------

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

    def test_pick_is_follow(self):
        for name in ("selectPick", "selectFrom"):
            self.assertIn("afterPick()", function_source(name) or "", name)
        src = function_source("afterPick") or ""
        for bit in ("toggleFollow(", "selKey(", "stopFollow()", "setWinFolded(false)", "setRailFolded(true)"):
            self.assertIn(bit, src, "afterPick: " + bit)

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

    def test_building_focus(self):
        block = listener_block(r"\$\('#detail'\)", "click") or ""
        for bit in ("data-focus-b", "stopFollow()", "flyTo(", "FOLLOW_DIST"):
            self.assertIn(bit, block, bit)
        self.assertIn("data-focus-b", function_source("renderDetail") or "")
        self.assertIn("b.focus", function_source("renderDetail") or "")

    def test_chip(self):
        src = function_source("renderFollow") or ""
        self.assertIn("follow.on", src)
        self.assertIn("freeCentre(", src)
        self.assertIn("renderFollow(", function_source("frame") or "")
        self.assertIn("stopFollow()", listener_block(r"\$\('#follow-stop'\)", "click") or "")

    def test_esc(self):
        block = listener_block(r"document", "keydown") or ""
        self.assertIn("Escape", block)
        self.assertIn("stopFollow()", block)

    def test_what_stops_and_what_keeps(self):
        self.assertIn("stopFollow()", function_source("panBy") or "")
        self.assertIn("stopFollow()", listener_block(r"\$\('#repos'\)", "click") or "")
        self.assertIn("stopFollow()", listener_block(r"\$\('#zfit'\)", "click") or "")
        for name in ("dragBy", "zoomStep", "stopFly", "setRailFolded", "setWinFolded"):
            src = function_source(name) or ""
            self.assertNotIn("stopFollow", src, name + " keeps the follow")
            self.assertNotIn("follow = null", src, name + " keeps the follow")

    def test_view_offset(self):
        src = function_source("updateCamera") or ""
        self.assertIn("freeCentre(", src)
        self.assertIn("setViewOffset(", src)

    def test_follow_tag_and_wheel(self):
        self.assertRegex(function_source("updatePerson") or "", r"tagVisible\([^;]*follow", "the followed person's tag shows")
        self.assertIn(".rail", listener_block(r"(?:stage|\$\('#stage'\))", "wheel") or "")
        self.assertIn("terrColor(", function_source("renderRepos") or "")


class TestRailCss(unittest.TestCase):

    def test_computer(self):
        c = css()
        m = re.search(r"--rail-w\s*:\s*(\d+)px", c)
        self.assertIsNotNone(m, "--rail-w")
        self.assertTrue(190 <= int(m.group(1)) <= 230, "compact: " + m.group(1))
        m = re.search(r"--msg-w\s*:\s*(\d+)px", c)
        self.assertIsNotNone(m, "--msg-w")
        self.assertTrue(360 <= int(m.group(1)) <= 400, m.group(1))  # city-polish P2: about 380
        r = rule(".rail").replace(" ", "")
        for bit in ("position:absolute", "width:var(--rail-w)", "max-height:calc(100%-24px)"):
            self.assertIn(bit, r, bit)
        w = rule(".win").replace(" ", "")
        for bit in ("right:12px", "top:12px", "bottom:12px", "width:var(--msg-w)"):
            self.assertIn(bit, w, ".win docked right: " + bit)
        self.assertNotIn("left:12px", w)
        self.assertEqual(rule(".win.wide"), "", "no wide window")
        self.assertIn("position:absolute", rule(".tab").replace(" ", ""))
        self.assertIn("var(--rail-w", rule(".proto"), "the live/demo chip sits right of the rail")
        self.assertRegex(c, r"\.cam\b[^{]*\{[^}]*var\(--msg-w", "the zoom buttons move left of the panel")

    def test_phone(self):
        m = media_960()
        for bit in (".rail", ".win", ".drawer-open"):
            self.assertIn(bit, m, bit)
        w = rule(".win", m).replace(" ", "")
        self.assertIn("top:auto", w, "a bottom sheet")
        self.assertIn(".ask-panel", m[m.index(".drawer-open"):] if ".drawer-open" in m else "")


# ---------------------------------------------------------------------------
# V2: sideways two-finger scroll
# ---------------------------------------------------------------------------

V2_DRIVER = r"""
const cases = [];
for (const az of [0, .7, 2.2, -1.3, 3.5]) for (const el of [EL_MIN, EL_DEFAULT, EL_MAX]) for (const [dx, dy] of [[30, 0], [-30, 0], [0, 30], [0, -30], [24, -18]]) {
  const m = wheelMove({ deltaX: dx, deltaY: dy, deltaMode: 0, ctrlKey: false }, 900);
  cases.push({ az, el, dx, dy, pan: m.pan, d: panDelta(m.pan[0], m.pan[1], az, el, 12, 900) });
}
const z = wheelMove({ deltaX: 30, deltaY: 10, deltaMode: 0, ctrlKey: true }, 900);
__out = { cases, z, TY: TARGET_Y };
"""


def project(cam_t, az, el, dist, point, w=1200, h=900, ty=.4):
    tx, tz = cam_t
    ce = math.cos(el)
    cpos = (tx + dist * ce * math.sin(az), ty + dist * math.sin(el), tz + dist * ce * math.cos(az))

    def sub(a, b):
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    def norm(a):
        n = math.sqrt(dot(a, a))
        return (a[0] / n, a[1] / n, a[2] / n)

    f = norm(sub((tx, ty, tz), cpos))
    r = norm(cross(f, (0, 1, 0)))
    u = cross(r, f)
    v = sub(point, cpos)
    k = (h / 2) / math.tan(math.radians(FOV) / 2)
    return (w / 2 + dot(v, r) / dot(v, f) * k, h / 2 - dot(v, u) / dot(v, f) * k)


class TestSidewaysScroll(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(V2_DRIVER, {}, ("wheelMove", "panDelta", "EL_MIN", "EL_MAX", "EL_DEFAULT", "TARGET_Y"))

    def test_pan_values(self):
        for c in self.r["cases"]:
            self.assertAlmostEqual(c["pan"][0], c["dx"], places=9, msg="deltaX in, same sign out")
            self.assertAlmostEqual(c["pan"][1], -c["dy"], places=9, msg="deltaY as before")
        self.assertIn("zoom", self.r["z"])
        self.assertNotIn("pan", self.r["z"])

    def test_land_moves_the_way_of_the_scroll_on_both_axes(self):
        ty = self.r["TY"]
        for c in self.r["cases"]:
            az, el, dx, dy = c["az"], c["el"], c["dx"], c["dy"]
            pt = (0, ty, 0)
            x0, y0 = project((0, 0), az, el, 12, pt, ty=ty)
            x1, y1 = project((c["d"][0], c["d"][1]), az, el, 12, pt, ty=ty)
            sx, sy = x1 - x0, y1 - y0
            label = "az %.1f el %.2f delta (%d, %d) -> land (%.1f, %.1f)" % (az, el, dx, dy, sx, sy)
            if dx:
                self.assertEqual(sx > 0, dx > 0, label)
                self.assertTrue(.6 * abs(dx) <= abs(sx) <= 1.4 * abs(dx), label)
            else:
                self.assertLess(abs(sx), 1.5, label)
            if dy:
                self.assertEqual(sy > 0, dy > 0, label)
                self.assertTrue(.6 * abs(dy) <= abs(sy) <= 1.4 * abs(dy), label)
            else:
                self.assertLess(abs(sy), 1.5, label)

    def test_pan_by_uses_it(self):
        self.assertIn("panDelta(", function_source("panBy") or "")
        self.assertTrue(sim_has("panDelta"))


# ---------------------------------------------------------------------------
# V3: bigger hit areas
# ---------------------------------------------------------------------------

class TestHitArea(unittest.TestCase):

    def test_after_boxes(self):
        c = css()
        for sel in (".bub::after", ".tagl::after", ".qm::after", ".rdev::after"):
            body = rule(sel, c).replace(" ", "")
            self.assertIn("content:", body, sel)
            self.assertIn("position:absolute", body, sel)
            m = re.search(r"inset:-(\d+(?:\.\d+)?)px", body)
            self.assertIsNotNone(m, sel + " inset:-Npx")
            self.assertGreaterEqual(float(m.group(1)), 6, sel)

    def test_bubble_not_clipped(self):
        self.assertNotIn("overflow:hidden", rule(".bub").replace(" ", ""), "a clipped ::after takes no clicks")


if __name__ == "__main__":
    unittest.main()
