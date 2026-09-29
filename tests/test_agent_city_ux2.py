"""Failing tests for city-ux2 (owner, 2026-09-29, after using 0.10.0; mock mock/city-ux2-mock.html).

CONTRACT (bin/agent-city.html). "sim section" = the page script from 'use strict' up to the '3D view.'
comment: every function named "(sim)" below lives there, needs no three.js and no DOM, and is driven
straight by these tests (tests/test_agent_city_people.py run_sim). Everything else is "3D part".

V1 the left rail: every person here now, click = the camera follows that person
  (sim) REPO_COLORS: at least 6 distinct '#rrggbb' colours. terrColor(terr) -> REPO_COLORS[i % length],
        i = the territory's index in map.territories; '#8D91B3' for a territory not in the map.
  (sim) railGroups() -> [{terr, name, color, rows: [{id, depth, rest}]}], in map order, one per territory
        that has at least one row (a territory with nobody here is left out). Rows, in this order:
        'gov:<terr>' (depth 0, rest false) first, only while that territory has a governor figure
        (governorFigures()); then that territory's rosterGroups() rows without its governor row (leads,
        each followed by its workers at depth 1, then the others); then every other member's person in
        it (c.remote, not gone; depth 0). Last, every row whose person rests (citizenStatus(c)[0] ===
        'rest') is moved to the end of its group with rest: true, the order among them kept.
        name = the territory's name, color = terrColor(terr).
  (sim) railCount(groups) -> {active, you}: active = rows that are neither the governor nor resting;
        you = those among them whose citizenStatus(c)[0] === 'you' (waiting on the owner).
  (sim) railHtml(groups, followId, openRest) -> the HTML of #rail-list; openRest is a Set of terr ids
        whose resting rows are shown. Per group:
          <section class="rail-grp" data-terr="<terr>"> with a head <div class="grp-h"> holding
          <span class="rc" style="--rc:<color>">, the escaped territory name and <span class="n"> = the
          number of active rows (not the governor, not resting);
          <ul class="rrows"> with one row per non-resting row;
          when the group has resting rows: <button type="button" class="rest-t" data-rest="<terr>"
          aria-expanded="true|false"> with i18n('rail.rest', {n}); and only when openRest has terr, a
          second <ul class="rrows"> with the resting rows.
        A row: <li class="rrow[ sub][ resting]" style="--rc:<color>"> holding
          <button type="button" class="rfocus" data-focus="<row id>" aria-pressed="<row id === followId>"
          aria-label="<i18n row.focusAria {name}>"> with the escaped name (the governor: i18n who.governor;
          a person: nameOf(c)) and <span class="pill <group>"> (the governor: class gov, govRowText(terr);
          a person: citizenStatus(c)), then <button type="button" class="ropen" data-open="<row id>"
          aria-label="<i18n row.openAria {name}>"> with i18n row.open. Everything escaped.
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
        the middle); followPos null (gone) -> stopFollow(). It never
        touches cam.el, cam.dist after the fly, or cam.az (only the never-stop rotation turns it).
        stopFly() never ends a follow (a zoom during the fly-in just ends the fly).
  (sim) tagVisible(hover, selected, followed) -> !!(hover || selected || followed): the followed person
        shows its name tag like a selected one. updatePerson passes the follow check as the third arg.
  (sim) freeCentre(w, h, rail, win) -> [cx, cy], the middle of the city you can see, stage px.
        rail = {right} (the rail's right edge, a computer) or null (phone: a drawer covers nothing for
        long); win = the open team window's box {left, top, right, bottom}, passed only while following,
        else null. x0 = rail ? rail.right : 0, x1 = w, y0 = 0, y1 = h. A window spanning the width (left
        <= x0 + 20 and right >= w - 20: the phone sheet) -> y1 = win.top; else a window at the left
        (left <= x0 + 20) -> x0 = win.right. Never a sliver: x1 - x0 < 160 -> x0 back to the rail's edge
        (or 0); y1 - y0 < 120 -> y1 = h.
  3D part:
    Markup inside #stage (after the canvas, before .cam): <aside class="rail" id="rail"
        data-t-aria="rail.title"> with a head (data-t="rail.title" text, <span class="n" id="rail-n">)
        and <div class="rail-list" id="rail-list">; <button type="button" class="rail-btn" id="rail-btn"
        aria-controls="rail" aria-expanded="false"> (the phone drawer button); <div class="follow"
        id="follow" role="status" hidden> with <span id="follow-t"> and <button type="button"
        id="follow-stop" data-t="follow.stop">.
    renderRail(): railHtml(railGroups(), follow, railRestOpen) into #rail-list only when it changed
        (lastRail); #rail-n = i18n rail.count {n: active}; #rail-btn text = i18n rail.drawer {n}, plus the
        'you' count when > 0. renderPanel() calls it; so do startFollow/stopFollow (the pressed row).
    setRail(open): the phone drawer -- class "open" on #rail, aria-expanded on #rail-btn, class
        "drawer-open" on #stage. #rail-btn click toggles it. selectPick() and selectFrom() call
        setRail(false) (a window never opens under the drawer).
    #rail-list click: [data-rest] toggles railRestOpen; [data-focus] -> toggleFollow(id) + setRail(false);
        [data-open] -> selectFrom(id) (the same window a head-tag click opens) + setRail(false).
    Team window: teamListHtml() rows get, after the row button, <button type="button" class="tfocus"
        data-follow="<row id>" aria-pressed="<row id === follow>" aria-label="<i18n team.focus>">;
        the #detail click listener: [data-follow] -> toggleFollow(id), the selection stays.
    Building window: renderDetail's building branch has <button type="button" class="b-focus"
        data-focus-b="<building id>"> (i18n b.focus); the #detail click listener: stopFollow() then
        flyTo(the building's scene x/z, Math.min(cam.dist, FOLLOW_DIST)).
    Follow chip: renderFollow() (frame() calls it; touches the DOM only on change): #follow hidden
        unless follow; #follow-t = i18n follow.on {name}; left = the free centre x. #follow-stop click ->
        stopFollow().
    Stops following: a second click on the row, Esc (document keydown, e.key === 'Escape', only
        stopFollow), #follow-stop, the repo tags (All too), #zfit, and a pan (panBy calls stopFollow()).
        Keeps following: dragBy (orbit), zoomStep, pinch/gesture/wheel zoom, the rotation, the window.
    The view is centred on the free part: updateCamera() eases a shift toward freeCentre(W, H, the
        rail's box on a computer, the #win box while following) and sets camera.setViewOffset (so pickAt
        and toScreen stay right).
    The wheel listener also leaves wheels inside .rail alone (the list scrolls).
    renderRepos(): each repo tag gets <span class="rc" style="--rc:<terrColor>">.
    CSS: --rail-w (the rail's width) on .stage or :root; .rail position:absolute, left 12px; .win and
        .proto sit right of it (their left uses var(--rail-w)); .rail-btn display:none on a computer.
        @media (max-width: 960px): .rail is a drawer (off screen until .rail.open), .rail-btn shows,
        .stage.drawer-open hides .win and .ask-panel.
    New TEXT keys, zh and en: rail.title, rail.count, rail.rest, rail.drawer, row.open, row.openAria,
        row.focusAria, follow.on, follow.stop, team.focus, b.focus.

V2 two-finger sideways scroll moves the land the same way up/down does
  (sim) wheelMove(e, h): no ctrlKey -> { pan: [deltaX * unit, -deltaY * unit] } (was -deltaX: the X axis
        went the other way from Y). ctrlKey zoom unchanged.
  (sim) panDelta(dx, dy, az, el, dist, h) -> [dtx, dtz], the look-point move panBy() makes for a pan of
        (dx, dy) px (before its clamp to the land); panBy() uses it. Composed: a wheel of (deltaX, deltaY)
        moves the land on screen the way of (+deltaX, +deltaY) -- both axes, both signs, any angle.
        No invert option; pinch stays zoom.

V3 head tags and bubbles are easy to hit
  CSS: .bub::after, .tagl::after, .qm::after, .rdev::after: content "", position absolute, inset -8px (at least 6 px
        each side, so the hit area is at least 12 px bigger than the box). .bub itself is not
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
const opens = h => [...h.matchAll(/data-open="([^"]*)"/g)].map(m => m[1]);
const pressed = h => [...h.matchAll(/data-focus="([^"]*)"[^>]*aria-pressed="true"|aria-pressed="true"[^>]*data-focus="([^"]*)"/g)].map(m => m[1] || m[2]);
const closed = railHtml(G, 'w1', new Set()), open = railHtml(G, null, new Set([A.id]));
const cnt0 = railCount(G);
byId('w1').waiting = true;
const cnt1 = railCount(railGroups());
byId('w1').waiting = false;
byId('y1').gone = true; byId('y2').gone = true;
const noB = railGroups().map(g => g.terr);
__out = { a: A.id, b: B.id, terrs: map.territories.map(t => t.id), colors: REPO_COLORS,
  cA: terrColor(A.id), cB: terrColor(B.id), cX: terrColor('nope'),
  groups: G.map(g => ({ terr: g.terr, name: g.name, color: g.color, rows: g.rows.map(r => [r.id, r.depth, !!r.rest]) })),
  names: [A.name, B.name],
  closed, open, closedIds: ids(closed), openIds: ids(open), closedOpens: opens(closed), pressed: pressed(closed),
  restA: i18n('rail.rest', { n: 1 }), cnt0, cnt1, noB };
"""


class TestRailData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(RAIL_DRIVER, payload(), ("apply", "landState", "railGroups", "railHtml", "railCount",
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

    def test_empty_territory_left_out(self):
        self.assertEqual(self.r["noB"], [self.r["a"]])

    def test_counts(self):
        self.assertEqual(self.r["cnt0"], {"active": 5, "you": 0}, "s:L w1 f1 remote y1")
        self.assertEqual(self.r["cnt1"], {"active": 5, "you": 1})

    def test_rows_html(self):
        a, b = self.r["a"], self.r["b"]
        self.assertEqual(self.r["closedIds"], ["gov:" + a, "s:L", "w1", "f1", "r:dev-ann:s:9", "y1"], "resting rows folded")
        self.assertEqual(self.r["closedOpens"], self.r["closedIds"], "every row has its open button")
        self.assertEqual(self.r["openIds"], ["gov:" + a, "s:L", "w1", "f1", "r:dev-ann:s:9", "w2", "y1"])
        self.assertEqual(self.r["pressed"], ["w1"])
        h = self.r["closed"]
        self.assertIn('class="rfocus"', h)
        self.assertIn('class="ropen"', h)
        self.assertRegex(h, r'<section class="rail-grp" data-terr="%s"' % re.escape(a))
        self.assertIn("--rc:%s" % self.r["cA"], h)
        self.assertRegex(h, r'data-rest="%s"[^>]*aria-expanded="false"|aria-expanded="false"[^>]*data-rest="%s"' % (re.escape(a), re.escape(a)))
        self.assertRegex(self.r["open"], r'data-rest="%s"[^>]*aria-expanded="true"|aria-expanded="true"[^>]*data-rest="%s"' % (re.escape(a), re.escape(a)))
        self.assertIn(self.r["restA"], h)
        self.assertIn('class="pill gov"', h)
        self.assertIn('class="rrow sub', h, "a worker under its lead")
        self.assertIn("resting", self.r["open"])
        self.assertNotIn("city <b>", h, "escaped")
        self.assertIn("city &lt;b&gt;", h)
        self.assertRegex(h, r'<span class="n">\s*4\s*</span>', "A: s:L w1 f1 remote")


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
  freeCentre(1200, 800, { right: 290 }, null),
  freeCentre(1200, 800, null, null),
  freeCentre(1200, 800, { right: 290 }, { left: 302, top: 12, right: 1000, bottom: 788 }),
  freeCentre(1200, 800, { right: 290 }, { left: 302, top: 12, right: 1150, bottom: 788 }),
  freeCentre(400, 700, null, { left: 8, top: 300, right: 392, bottom: 692 }),
  freeCentre(400, 700, null, { left: 8, top: 80, right: 392, bottom: 692 }),
];
"""


class TestFreeCentre(unittest.TestCase):

    def test_values(self):
        r = run_sim(FREE_DRIVER, {}, ("freeCentre",))
        self.assertEqual(r, [[745, 400], [600, 400], [1100, 400], [745, 400], [200, 150], [200, 350]])


TEAM_FOCUS_DRIVER = SNAPSHOT + r"""
follow = 'w1';
__out = teamListHtml(A.id, { t: 'c', id: 'f1' });
"""


class TestTeamRowFocus(unittest.TestCase):

    def test_focus_buttons(self):
        h = run_sim(TEAM_FOCUS_DRIVER, payload(), ("apply", "landState", "teamListHtml", "newCitizen", "citizens"))
        self.assertIn('class="tfocus"', h)
        ids = re.findall(r'data-follow="([^"]*)"', h)
        self.assertIn("w1", ids)
        self.assertIn("f1", ids)
        self.assertTrue(any(i.startswith("gov:") for i in ids), "the governor row too")
        self.assertRegex(h, r'data-follow="w1"[^>]*aria-pressed="true"|aria-pressed="true"[^>]*data-follow="w1"')
        self.assertNotRegex(h, r'data-follow="f1"[^>]*aria-pressed="true"')


# ---------------------------------------------------------------------------
# V1: the 3D part
# ---------------------------------------------------------------------------

class TestRailMarkup(unittest.TestCase):

    def test_markup_inside_the_stage(self):
        p = page()
        stage, tb = p.index('id="stage"'), p.index('class="toolbar"')
        for bit in ('<aside class="rail" id="rail"', 'id="rail-list"', 'id="rail-n"', 'id="rail-btn"',
                    'id="follow"', 'id="follow-t"', 'id="follow-stop"'):
            self.assertIn(bit, p, bit)
            self.assertTrue(stage < p.index(bit) < tb, bit + " inside #stage")
        self.assertRegex(p, r'<div class="follow" id="follow" role="status"[^>]*hidden')
        self.assertRegex(p, r'<button type="button" class="rail-btn" id="rail-btn" aria-controls="rail" aria-expanded="false"')

    def test_text_keys(self):
        for k in ("rail.title", "rail.count", "rail.rest", "rail.drawer", "row.open", "row.openAria", "row.focusAria",
                  "follow.on", "follow.stop", "team.focus", "b.focus"):
            self.assertEqual(text_keys(k), 2, k + " in zh and en")


class TestRailWiring(unittest.TestCase):

    def test_render_rail(self):
        src = function_source("renderRail") or ""
        for bit in ("railGroups(", "railHtml(", "railCount(", "lastRail", "rail.count", "rail.drawer"):
            self.assertIn(bit, src, bit)
        self.assertIn("renderRail(", function_source("renderPanel") or "")

    def test_drawer(self):
        src = function_source("setRail") or ""
        for bit in ("'open'", "aria-expanded", "drawer-open"):
            self.assertIn(bit, src, bit)
        self.assertIn("setRail(", listener_block(r"\$\('#rail-btn'\)", "click") or "")
        for name in ("selectPick", "selectFrom"):
            self.assertIn("setRail(false)", function_source(name) or "", name)

    def test_rail_clicks(self):
        block = listener_block(r"\$\('#rail-list'\)", "click") or ""
        for bit in ("data-rest", "data-focus", "data-open", "toggleFollow(", "selectFrom(", "setRail(false)", "railRestOpen"):
            self.assertIn(bit, block, bit)

    def test_team_and_building_focus(self):
        block = listener_block(r"\$\('#detail'\)", "click") or ""
        for bit in ("data-follow", "toggleFollow(", "data-focus-b", "stopFollow()", "flyTo(", "FOLLOW_DIST"):
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
        for name in ("dragBy", "zoomStep", "stopFly"):
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
        self.assertIn("--rail-w", c)
        r = rule(".rail")
        self.assertIn("position:absolute", r.replace(" ", ""))
        self.assertIn("display:none", rule(".rail-btn").replace(" ", ""))
        self.assertIn("var(--rail-w", rule(".win"), "the window sits right of the rail")
        self.assertIn("var(--rail-w", rule(".proto"), "so does the live/demo chip")

    def test_phone(self):
        m = media_960()
        for bit in (".rail.open", ".rail-btn", ".drawer-open"):
            self.assertIn(bit, m, bit)
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
