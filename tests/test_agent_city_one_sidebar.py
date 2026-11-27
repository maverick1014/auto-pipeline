"""city-one-sidebar (requirements/city-one-sidebar.md, owner 2026-11-27) -- examples test, page bin/agent-city.html.

Item 2: a click on a person never moves or zooms the camera; the whole office stays in view. The person is marked
and their details open as today; zoom stays the user's own (the zoom buttons, the wheel, pinch).

  C1 desktop (1440 wide), the whole-floor view, click a person: same zoom, same look point, 3 s of frames later too;
     the person is selected, the window opens (afterSelect).
  C2 phone (390 wide): the same.
  C3 zoomed in and panned by hand, then click a person: the view stays at that zoom and that spot.
  C4 the same person clicked again: nothing moves, the person stays selected.
  C5 close (select nobody): nothing moved.
  C6 the area manager (gov:<floor>) clicked: nothing moves.
  C7 a rail row of a person on another floor: that floor shows at its whole-floor view (as the lift does), never
     zoomed or panned onto the person.
  C8 the selected person walks to another floor: the view stays on this floor (no camera follows anybody).

The driver runs the page's own select, stopFollow, stepCamMove, watchFollow and updateCamera (function_source) in node
with stand-ins for the scene: a floor is a set of people at (x, z) on it, goFloor shows a floor at its whole-floor view.

Item 1 (approved mock v2, mock/city-one-sidebar-mock.html at 2521ed2; owner: "the agent list direct inside the lift list
design will do. no need split 2"): ONE list on the left, the lift's floor list is the sidebar (#rail). One row per floor
(= one repo), top floor first, then G (the street). The floor in view is the open one: its repo's team tree sits right
under its row; the other floors stay one row each. No team block, no second header, no lift panel on the right.
sideHtml(groups, selId, openTerr, outside, openRest, adds, shut) -> the HTML of #rail-list (a pure function, page sim).

  S1 inside floor A: rows B, A, then G; one team, right under A's row, with A's people; B is one row; no group heads.
  S2 inside floor B (nobody online): B's team shows the quiet line and the add control; A's people are gone.
  S3 on the street: no team, G is the current row, no floor is open.
  S4 a selected person's row is marked; S5 the resting people show when their toggle is open.
  S6 the repo's add control is the team's last line ("加 agent"); while opening it shows the spinner, no second click.
  P1-P5 the page: one aside, the lift header in it, no #lift; renderRail draws sideHtml and the office refresh keeps it
     current; a floor click goes there (goFloor / goOutside) and never folds the bar (phone too); a person pick still
     folds it on a phone (afterSelect); the floor names stay on a phone.
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
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from citypage import function_source, run_sim, TA, TB, two_territory_view, listener_block, page, css, rule  # noqa: E402

PAGE_FUNCS = ("select", "stopFollow", "stepCamMove", "watchFollow", "updateCamera", "fitDist")

DRIVER = r"""
const fs = require('fs'), vm = require('vm');
const { fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
for (const c of cases) {
  const box = { Math, JSON, console, performance: { now: () => 0 }, RM: false,
    W: c.W, H: c.H, view: 'inside', cur: 'f1', follow: null, selected: null, camMove: null,
    viewShiftX: 0, viewShiftY: 0, railBoxNow: null, winBoxNow: null, liftBoxNow: null,
    cam: { az: -.62, el: .86, dist: 21, tx: 0, ty: 0, tz: .3, wantDist: null },
    camera: { position: { set(){} }, lookAt(){}, updateMatrixWorld(){}, aspect: 1, setViewOffset(){}, clearViewOffset(){},
      updateProjectionMatrix(){} },
    calls: [] };
  // who is where: f1 has p1 and p3, f2 has p2; the area manager of f1 stands by the door
  box.people = { p1: { at: 'f1', inLift: null, x: 4, z: -3 }, p3: { at: 'f1', inLift: null, x: -5, z: 2.5 },
    p2: { at: 'f2', inLift: null, x: 3, z: 4 }, 'gov:f1': { at: 'f1', inLift: null, x: -2, z: 5 } };
  box.rowPos = id => box.people[id] ? Object.assign({}, box.people[id]) : null;
  box.byId = id => box.people[id] ? { id } : null;
  box.isDrawn = () => true;
  box.selKey = s => !s ? null : s.t === 'c' ? s.id : s.t === 'gov' ? 'gov:' + s.terr : null;
  box.afterSelect = () => { box.calls.push(['afterSelect', box.selKey(box.selected)]); };
  box.enter = (at, cb) => { box.calls.push(['enter', at]); box.view = 'inside'; box.cur = at; if (cb) cb(); };
  // the page's goFloor: clearFigs(); buildFloor(); resetView(); cam.dist = cam.wantDist; cam.wantDist = null -- the whole floor
  box.goFloor = at => { box.calls.push(['goFloor', at]); box.cur = at;
    Object.assign(box.cam, { az: -.62, el: .86, tx: 0, ty: 0, tz: .3 }); box.cam.dist = box.fitDist(); box.cam.wantDist = null;
    box.follow = null; };
  box.refreshPanelBoxes = () => {};
  box.freeCentre = (W, H) => [W / 2, H / 2];
  vm.createContext(box);
  vm.runInContext(fns, box);
  const cam = box.cam;
  const snap = () => ({ dist: cam.dist, wantDist: cam.wantDist, tx: cam.tx, ty: cam.ty, tz: cam.tz, az: cam.az, el: cam.el });
  const frames = n => { for (let i = 0; i < n; i++) { box.watchFollow(); box.updateCamera(1 / 60); } };
  cam.dist = box.fitDist();                                  // the whole-floor view of this width
  if (c.hand) Object.assign(cam, c.hand);                    // the user's own zoom and pan
  frames(10);
  const before = snap(), r = { before, cur0: box.cur };
  for (const step of c.steps) {
    if (step[0] === 'select') box.select(step[1]);
    else if (step[0] === 'walk') box.people[step[1]] = Object.assign(box.people[step[1]], step[2]);
    else if (step[0] === 'frames') frames(step[1]);
  }
  r.after = snap(); r.fit = box.fitDist(); r.selected = box.selected; r.follow = box.follow; r.cur = box.cur;
  r.calls = box.calls;
  out[c.name] = r;
}
require('fs').writeSync(1, JSON.stringify(out));
"""

DESK = {"W": 1440, "H": 713}
PHONE = {"W": 358, "H": 714}   # a 390-wide phone: the stage is 358 x 714 (tests/test_agent_city_desks.py)
CASES = [
    dict(name="C1", steps=[["select", "p1"], ["frames", 180]], **DESK),
    dict(name="C2", steps=[["select", "p1"], ["frames", 180]], **PHONE),
    dict(name="C3", hand={"dist": 9, "tx": 1.5, "tz": -2}, steps=[["select", "p1"], ["frames", 180]], **DESK),
    dict(name="C3phone", hand={"dist": 12, "tx": -1, "tz": 1}, steps=[["select", "p3"], ["frames", 180]], **PHONE),
    dict(name="C4", steps=[["select", "p1"], ["frames", 60], ["select", "p1"], ["frames", 120]], **DESK),
    dict(name="C5", steps=[["select", "p1"], ["frames", 60], ["select", None], ["frames", 120]], **DESK),
    dict(name="C6", steps=[["select", "gov:f1"], ["frames", 180]], **DESK),
    dict(name="C7", hand={"dist": 9, "tx": 2, "tz": 2}, steps=[["select", "p2"], ["frames", 180]], **DESK),
    dict(name="C8", steps=[["select", "p1"], ["frames", 30], ["walk", "p1", {"at": "f2", "x": 1, "z": 1}],
                           ["frames", 150]], **DESK),
]


def run_cases():
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not installed")
    srcs = []
    for name in PAGE_FUNCS:
        src = function_source(name)
        if src is None:
            raise AssertionError("the page has no function %s" % name)
        srcs.append(src)
    with tempfile.TemporaryDirectory() as tmp:
        script, data = os.path.join(tmp, "drv.js"), os.path.join(tmp, "data.json")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(DRIVER)
        with open(data, "w", encoding="utf-8") as fh:
            json.dump({"fns": "\n".join(srcs), "cases": CASES}, fh)
        res = subprocess.run([node, script, data], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    if res.returncode != 0 or not res.stdout.strip():
        raise AssertionError("driver failed:\n" + res.stderr[-3000:])
    return json.loads(res.stdout)


class TestAClickKeepsTheView(unittest.TestCase):
    """Item 2: the camera stays where it was -- same zoom, same look point -- whatever was clicked."""

    @classmethod
    def setUpClass(cls):
        cls.out = run_cases()

    def assert_view_kept(self, name, ref=None):
        r = self.out[name]
        ref = ref or r["before"]
        for k in ("dist", "tx", "ty", "tz", "az", "el"):
            with self.subTest(case=name, key=k):
                self.assertAlmostEqual(r["after"][k], ref[k], places=6,
                                       msg="%s: cam.%s moved %s -> %s" % (name, k, ref[k], r["after"][k]))
        self.assertIsNone(r["after"]["wantDist"], "%s: no zoom is still on its way" % name)
        self.assertIsNone(r["follow"], "%s: the camera follows nobody" % name)

    def test_c1_desktop_click(self):
        self.assert_view_kept("C1")
        self.assertEqual(self.out["C1"]["selected"], {"t": "c", "id": "p1"})
        self.assertIn(["afterSelect", "p1"], self.out["C1"]["calls"], "the window opens as today")

    def test_c2_phone_click(self):
        self.assert_view_kept("C2")
        self.assertAlmostEqual(self.out["C2"]["after"]["dist"], self.out["C2"]["fit"], places=6,
                               msg="the phone keeps its whole-floor distance")
        self.assertEqual(self.out["C2"]["selected"], {"t": "c", "id": "p1"})

    def test_c3_hand_zoom_is_kept(self):
        self.assert_view_kept("C3")
        self.assertAlmostEqual(self.out["C3"]["after"]["dist"], 9, places=6)
        self.assert_view_kept("C3phone")
        self.assertAlmostEqual(self.out["C3phone"]["after"]["dist"], 12, places=6)

    def test_c4_same_person_again(self):
        self.assert_view_kept("C4")
        self.assertEqual(self.out["C4"]["selected"], {"t": "c", "id": "p1"}, "a second click keeps the person selected")

    def test_c5_close_moves_nothing(self):
        self.assert_view_kept("C5")
        self.assertIsNone(self.out["C5"]["selected"])

    def test_c6_area_manager(self):
        self.assert_view_kept("C6")
        self.assertEqual(self.out["C6"]["selected"], {"t": "gov", "terr": "f1"})

    def test_c7_other_floor_shows_whole_floor(self):
        r = self.out["C7"]
        self.assertIn(["goFloor", "f2"], r["calls"], "a row of another floor shows that floor, as the lift does")
        self.assertEqual(r["cur"], "f2")
        whole = {"dist": r["fit"], "tx": 0, "ty": 0, "tz": .3, "az": -.62, "el": .86}
        self.assert_view_kept("C7", ref=whole)
        self.assertEqual(r["selected"], {"t": "c", "id": "p2"})

    def test_c8_no_camera_goes_after_a_walker(self):
        r = self.out["C8"]
        self.assertEqual([c for c in r["calls"] if c[0] == "goFloor"], [], "the view stays on this floor")
        self.assertEqual(r["cur"], "f1")
        self.assert_view_kept("C8")


class TestSelectHasNoCameraWords(unittest.TestCase):
    """Item 2 (replaces city-office's 'select zoom is halved', mock v5): select() itself sets no zoom, no look point
    and no follow; a floor change it asks for goes through goFloor / enter (their whole-floor view)."""

    def test_select_sets_no_camera(self):
        src = function_source("select")
        self.assertIsNotNone(src)
        self.assertNotRegex(src, r"cam\.(wantDist|dist|tx|ty|tz|az|el)\s*=(?!=)", "select() never zooms or pans")
        self.assertNotRegex(src, r"\bfollow\s*=(?!=)(?!\s*null\b)", "select() locks the camera onto nobody")


# ---------------------------------------------------------------- item 1: one list (mock v2)
SIDE_REQUIRED = ("apply", "officeState", "railGroups", "sideHtml", "floorTag", "i18n", "byId")

# Two repos (tests/citypage two_territory_view): A = auto-pipeline (an area manager, a task manager, a resting one),
# B = v4-plus (nobody online). Both are on this machine (here), so both have the add control. The resting person is a
# session (task-manager): a subagent role (fast-lane-deputy, worker...) never gets a rail row (railGroups skips isSub).
SIDE_DRIVER = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
A.name = 'auto-pipeline'; B.name = 'v4-plus'; A.here = true; B.here = true;
for (const t of [A, B]) { const r = V.repos.find(x => x.id === t.id); r.name = t.name; r.here = true; }
const ag = (id, label, task, terr, extra) => Object.assign({ id, role: 'task-manager', label, task, stuck: false, done: false,
  tools: {}, terr, lead: '', office: null, relay: '' }, extra || {});
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'busy' }], agents: [ag('s:tttt0001', 'city-add-agent Task Manager', 'auto-pipeline', A.id),
  ag('s:rrrr0002', 'board-eta Task Manager', 'board-eta', A.id)], adding: [] });   // a session role: a subagent role has no row
byId('s:rrrr0002').state = 'resting';
const G = railGroups(), none = new Set(), noAdds = new Map();
const out = { a: A.id, b: B.id };
out.openA = sideHtml(G, null, A.id, false, none, noAdds, none);
out.openB = sideHtml(G, null, B.id, false, none, noAdds, none);
out.outside = sideHtml(G, null, null, true, none, noAdds, none);
out.sel = sideHtml(G, 's:tttt0001', A.id, false, none, noAdds, none);
out.rest = sideHtml(G, null, A.id, false, new Set([A.id]), noAdds, none);
out.opening = sideHtml(G, null, B.id, false, none, new Map([[B.id, { s: 'opening', name: 'v4-plus Manager' }]]), none);
out.tagA = floorTag(A.id); out.tagB = floorTag(B.id);
out.t = { none: i18n('rail.none'), add: i18n('add.tip'), outside: i18n('office.outside') };
__out = out;
"""


def floor_button(html, terr):
    m = re.search(r'<button[^>]*\bdata-floor="%s"[^>]*>' % re.escape(terr), html)
    return m


def team_of(html):
    """[(start, end, terr)] of every open team block: <div class="team" ... data-terr="X" ...> up to its </div> pair."""
    out = []
    for m in re.finditer(r'<div class="team"[^>]*\bdata-terr="([^"]+)"[^>]*>', html):
        depth, i = 0, m.start()
        for t in re.finditer(r"<(/?)div\b[^>]*>", html[m.start():]):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                out.append((m.start(), m.start() + t.end(), m.group(1)))
                break
    return out


class TestOneList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(SIDE_DRIVER, {"view": two_territory_view(), "ta": TA, "tb": TB}, SIDE_REQUIRED)
        cls.a, cls.b = cls.r["a"], cls.r["b"]

    def rows_in_order(self, html):
        ia, ib = floor_button(html, self.a), floor_button(html, self.b)
        g = re.search(r'<button[^>]*\bdata-out="1"[^>]*>', html)
        self.assertTrue(ia and ib and g, "a row for every floor and G")
        self.assertLess(ib.start(), ia.start(), "top floor first (B is 2F, A is 1F)")
        self.assertLess(ia.start(), g.start(), "G (the street) last")
        return ia, ib, g

    def test_s1_the_floor_in_view_opens_its_team_under_its_row(self):
        h = self.r["openA"]
        ia, ib, g = self.rows_in_order(h)
        teams = team_of(h)
        self.assertEqual([t[2] for t in teams], [self.a], "one open team: the floor in view")
        start, end, _ = teams[0]
        self.assertLess(ia.end(), start, "the team comes after A's row")
        self.assertEqual(h[ia.end():start].count("<button"), 0, "right under A's row")
        self.assertLessEqual(end, g.start(), "and before the next row")
        team = h[start:end]
        for row in ("gov:" + self.a, "s:tttt0001"):
            self.assertIn('data-focus="%s"' % row, team, row)
        self.assertNotIn("s:rrrr0002", team, "a resting person shows only when the toggle is open")
        self.assertIn('data-rest="%s"' % self.a, team, "the resting toggle sits in the team")
        self.assertIn('aria-current="true"', ia.group(0))
        self.assertIn('aria-expanded="true"', ia.group(0))
        self.assertIn('aria-expanded="false"', ib.group(0), "the other floor is one row")
        self.assertIn('aria-current="false"', ib.group(0))

    def test_s1_a_floor_row_keeps_the_lift_look(self):
        h, tag = self.r["openA"], self.r["tagA"]
        m = floor_button(h, self.a)
        row = h[m.start():h.index("</button>", m.start())]
        self.assertIn('class="lb"', row)
        self.assertIn('<span class="no">%s</span>' % tag["floor"], row)
        self.assertIn('<span class="ln">auto-pipeline</span>', row)
        self.assertRegex(row, r'<span class="lc">\s*%d\b' % tag["people"], "the people count")

    def test_s1_no_second_header_no_group_block(self):
        for k in ("openA", "openB", "outside"):
            for bit in ("rail-grp", "grp-h", "data-grp", "rail-head"):
                with self.subTest(case=k, bit=bit):
                    self.assertNotIn(bit, self.r[k])

    def test_s2_a_floor_with_nobody(self):
        h = self.r["openB"]
        self.rows_in_order(h)
        teams = team_of(h)
        self.assertEqual([t[2] for t in teams], [self.b])
        team = h[teams[0][0]:teams[0][1]]
        self.assertIn(self.r["t"]["none"], team, "the quiet line")
        self.assertIn('data-add="%s"' % self.b, team)
        self.assertNotIn("s:tttt0001", h, "A's people are not listed while B is in view")
        self.assertIn('aria-expanded="false"', floor_button(h, self.a).group(0))

    def test_s3_on_the_street_no_floor_is_open(self):
        h = self.r["outside"]
        self.rows_in_order(h)
        self.assertEqual(team_of(h), [])
        self.assertNotIn("data-focus=", h)
        g = re.search(r'<button[^>]*\bdata-out="1"[^>]*>', h).group(0)
        self.assertIn('aria-current="true"', g)
        for terr in (self.a, self.b):
            self.assertIn('aria-expanded="false"', floor_button(h, terr).group(0))

    def test_s4_the_selected_person_is_marked(self):
        h = self.r["sel"]
        m = re.search(r'<button[^>]*data-focus="s:tttt0001"[^>]*>', h)
        self.assertTrue(m)
        self.assertIn('aria-current="true"', m.group(0))

    def test_s5_resting_people_when_open(self):
        h = self.r["rest"]
        start, end, _ = team_of(h)[0]
        self.assertIn('data-focus="s:rrrr0002"', h[start:end])

    def test_s6_the_add_control_is_the_last_line(self):
        h = self.r["openA"]
        start, end, _ = team_of(h)[0]
        team = h[start:end]
        i = team.find('data-add="%s"' % self.a)
        self.assertGreater(i, 0, "the repo's add control is in its team")
        self.assertGreater(i, team.rfind("data-focus="), "after the people")
        self.assertIn(self.r["t"]["add"], team[i:], "it reads 加 agent")
        op = self.r["opening"]
        s2, e2, _ = team_of(op)[0]
        self.assertNotIn('data-add="%s"' % self.b, op[s2:e2], "opening: no second click")
        self.assertIn('class="spin"', op[s2:e2])


def aside_block():
    p = page()
    i = p.find('<aside class="rail" id="rail"')
    return p[i:p.index("</aside>", i)] if i >= 0 else ""


class TestOneListInThePage(unittest.TestCase):
    def test_p1_one_aside_with_the_lift_header(self):
        p, a = page(), aside_block()
        self.assertTrue(a, "the one sidebar is the aside #rail")
        for bit in ('class="lift-h"', 'id="rail-fold"', 'id="rail-list"'):
            self.assertIn(bit, a, bit)
        self.assertNotIn('data-t="rail.title"', a, "no second header")
        self.assertNotIn('id="lift"', p, "no lift panel on the right")
        self.assertNotIn("$('#lift')", p)
        self.assertNotIn("liftBoxNow", p, "the office centres between the bar and the window only")

    def test_p2_the_list_is_drawn_and_kept_current(self):
        src = function_source("renderRail") or ""
        self.assertRegex(src, r"sideHtml\([^;]*railGroups\(\)|railGroups\(\)[\s\S]*sideHtml\(")
        self.assertRegex(src, r"\bcur\b", "the open floor is the floor in view")
        self.assertRegex(src, r"view\s*===?\s*'(inside|outside)'")
        self.assertIn("renderRail(", function_source("renderOffice") or "", "counts and the open floor follow the view")
        self.assertIsNone(function_source("renderLift"), "the lift has no panel of its own any more")

    def test_p3_a_floor_click_goes_there_and_keeps_the_bar(self):
        block = listener_block(r"\$\('#rail-list'\)", "click") or ""
        self.assertRegex(block, r"data-floor|dataset\.floor")
        self.assertIn("goFloor(", block)
        self.assertIn("goOutside(", block)
        self.assertNotIn("setRailFolded", block, "a floor pick keeps the bar open, on a phone too")
        self.assertLess(block.find("goFloor("), block.find("data-focus"), "a floor row is handled before a person row")

    def test_p4_a_person_pick_still_folds_it_on_a_phone(self):
        src = function_source("afterSelect") or ""
        self.assertRegex(src, r"max-width:\s*960px[\s\S]*setRailFolded\(true\)")

    def test_p5_floor_names_show_on_a_phone(self):
        self.assertIsNone(re.search(r"\.ln[^{}]*\{[^}]*display:\s*none", css()), "no rule hides the floor names")
        self.assertIn("var(--ink)", rule(".rail"), "the bar has the lift's dark look")


if __name__ == "__main__":
    unittest.main()
