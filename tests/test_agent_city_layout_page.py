"""Failing tests for city-layout, the page (owner, 2026-10-01 and 2026-10-02; approved mock
mock/city-layout-mock.html, 837530b, "mock yes" 2026-10-02 11:57 with its three marked defaults: arrange
on the real 3D island; every drop is saved at once, Cancel saves back; the top counts are the shown repos
only). The server side: tests/test_agent_city_layout.py (its docstring has the request, the answers and
what a page gets). The look is the mock's: port its CSS (mockCss, "THE CHANGE (city-layout)") and its
script into the page; the mock's own stand-ins (its JS layout(), its people store) are NOT ported: the
server lays the island out and sends a fresh picture after every change.

CONTRACT (bin/agent-city.html). "sim section" = the page script from 'use strict' up to the '3D view.'
comment: every name marked (sim) lives there and is driven in node (tests/test_agent_city_people.py
run_sim). Everything else is "3D part", checked on its source and its CSS, and looked at in a browser by
the task manager.

L1 the rule, in the page too (the server checks it again; the page only offers what will pass)
  A land = {id, name, slot: [i, j], sea}. A slot is a cell of the island's 9 x 9 grid, -4..4 each.
  (sim) landsOf(view) -> one land per territory of the view, in view order; sea = (t.sea === true)
      (the server's view says which land has sea).
  (sim) landsOk(lands) -> true when every slot is inside the grid, no two lands share a slot, and no land
      stands on the cell just south ([i, j + 1]) of a land with sea.
  (sim) landMove(lands, id, slot) -> the request rows for "land ID goes to SLOT":
      a free slot     [{id, slot}]
      a land is there [{id, slot}, {id: <that land>, slot: <ID's own slot>}]   (the two swap)
      null when ID is no land of the list, SLOT is ID's own slot, or landsOk fails after it.
  (sim) landFree(lands, id) -> the free cells [[i, j], ...] land ID may go to: no land on it, it touches (4
      sides) a land that is not ID (ID alone on the island: it touches ID), and landMove(lands, id, cell) is
      not null. id null -> the free cells any land could take: no land on it, it touches a land, and it is
      not the cell just south of a land with sea. Any order.

L2 what is hidden
  (sim) hiddenLands: the server's list [{id, name, people, wait}] ([] at start). apply(): case 'snapshot'
      sets it from ev.hidden (missing -> []); case 'hidden' sets it from ev.lands.
  (sim) hiddenHtml(list) -> '' for an empty list, else
      '<i></i><span>' + i18n('arr.hidden', {n: list.length}) + (w ? i18n('arr.hiddenWait', {n: w}) : '')
      + '</span><u>' + i18n('arr.manage') + '</u>', w = how many lands of the list have wait > 0.
      zh: 已隐藏 2 个 / · 其中 1 个在等你 / 管理. A repo's name is never in it.
  (sim) railCount(groups).you also counts the people who wait in hidden repos (the sum of wait in
      hiddenLands): the rail head's and the folded tab's red count never hide them. active is as before.
  (sim) topCounts() is as before: the page never hears of a hidden repo's people, so the top counts are
      the shown repos only.
  3D part: <button type="button" class="rail-hid" id="rail-hid" hidden> inside <aside id="rail">, after
      #rail-list. renderRail() fills it with hiddenHtml(hiddenLands), shows it only when the list is not
      empty and the page is the live local one (not DEMO, not CLOUD), and sets the class "you" when
      somebody there waits. A click on it opens the mode (arrEnter()).

L3 people follow their land
  (sim) landState(view): compared with the view before it,
      a territory with another cx / cz: everything of it moves by that step at once -- every citizen (x, y,
        and the spots it holds: stand, home, its rest seat, its office), its path is dropped or moved with
        it (it never walks back over the sea), its building records (gx, gy; `occupied` is keyed by the new
        place; no second record for the same plot);
      a territory that is no longer in the view: its citizens are gone at once (c.gone, or out of
        `citizens`: no walk to the edge), its building records are dropped.
      A territory that did not move: nothing of it changes.
      The server sends a fresh snapshot after every change of the arrangement, so this runs with it.

L4 the mode
  (sim) arr = {on: false, pick: null, entry: null, err: ''}
  (sim) arrEntry(lands, hidden) -> what Cancel goes back to: [{id, slot, hidden: false}] for every land,
      then [{id, hidden: true}] for every land of the hidden list.
  (sim) arrBack(entry, lands, hidden) -> the request rows that put everything back, [] when nothing
      differs: an entry row that was shown and is now somewhere else or hidden -> {id, slot, hidden: false};
      one that was hidden and is now shown -> {id, hidden: true}; a row whose id is in neither list any
      more is left out; a land that came after the mode opened is not named (the server keeps it).
  (sim) arrWhy(code, body) -> '' for 200; 409 "taken" -> i18n('arr.errTaken'); 409 "sea" ->
      i18n('arr.errSea'); 409 "empty" -> i18n('arr.errEmpty'); anything else (400, 403, 404, no answer =
      code 0) -> i18n('arr.errOther'). Never silent: the bar shows it (#arr-err, role="alert").
  3D part, HTML:
      inside <div class="stage-top" id="stage-top">, after <nav id="repos">:
        <button type="button" class="arr-btn" id="arr-btn" aria-pressed="false" hidden>   icon + arr.btn
      inside <div class="stage" id="stage">:
        <div class="arr-ov" id="arr-ov"></div>                         the name plates (.arr-h)
        <div class="arr-bar" id="arr-bar" role="region" hidden>        #arr-tip, #arr-err (role="alert"),
          #arr-tray, <button id="arr-cancel" data-t="arr.cancel">, <button id="arr-done" data-t="arr.done">
  3D part, script:
      #arr-btn shows only on the live local page: $('#arr-btn').hidden = DEMO || CLOUD. The demo and the
        cloud page have no control and no mode.
      layoutPost(lands): fetch('/api/layout', {method: 'POST', headers: {'Content-Type':
        'application/json', 'X-City-Token': TOKEN}, body: JSON.stringify({lands})}) -> arr.err =
        arrWhy(status, body) and a redraw; a failed fetch -> arrWhy(0, {}). The island itself changes
        through the snapshot the server sends, never by the page's own guess.
      arrEnter(): arr.on, arr.entry = arrEntry(landsOf(map), hiddenLands); any follow stops, an open
        window closes; the camera flies out to the whole island (flyTo ... distMax()), tilts to look from
        above and turns square to the grid. arrLeave(): the mode off, the camera back.
      Done = arrLeave(). Cancel = layoutPost(arrBack(arr.entry, landsOf(map), hiddenLands)) when that is
        not empty, then arrLeave().
      A drop / a second tap = layoutPost(landMove(...)). 隐藏 on a plate = layoutPost([{id, hidden:
        true}]) (the last shown land: the button is aria-disabled, i18n('arr.last')). 显示 in the tray =
        layoutPost([{id, hidden: false}]).
      An era show that runs on a land that moves: buildLand() drops that land's show run (showRuns,
        dropShowRun) -- it knows which lands moved from landSteps(view), asked before landState(view) -- and
        stepShows() makes it again from the new view: the builders stand on the land, never in the sea.
      While arr.on: autoRotating() is false (the one thing that pauses, with follow); selectPick() opens
        nobody; a press on a land or its plate drags it (a footprint on the slot under the pointer), a
        press on the sea pans the map.
  3D part, CSS (the mock's): .arr-btn (pinned at the right end of the repo row: position:absolute in the
      strip, it never scrolls away with the tags), .arr-btn[aria-pressed="true"], .arr-ov, .arr-h,
      .arr-h.on, .arr-eye, .arr-bar (position:absolute, at the stage's bottom edge), .arr-tray, .arr-hid,
      .rail-hid, .rail-hid.you. Phone (the first @media (max-width: 960px) block): .arr-bar spans the
      width at the bottom edge; a plate is the name alone and only the picked plate shows 隐藏
      (.arr-h .arr-eye{display:none}, .arr-h.on .arr-eye shows).
  Words (TEXT, zh and en, each key once per language): arr.btn 整理, arr.on 整理中, arr.tip, arr.tipPick
      ({name}), arr.hide 隐藏, arr.show 显示, arr.cancel 取消, arr.done 完成, arr.tray 已隐藏, arr.waits
      ({n} 人在等你), arr.last 至少留一块地, arr.hidden, arr.hiddenWait, arr.manage, arr.errTaken, arr.errSea,
      arr.errEmpty, arr.errOther.
"""

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from test_agent_city_people import function_source, page, run_sim  # noqa: E402
from test_agent_city_ux_page import css, listener_block, media_960, rule, text_keys  # noqa: E402

PLANS = ac.load_plans()
SHOP, BLOG = "/work/layout/shop/.git", "/work/layout/blog/.git"
TA, TB = ac.territory_id(SHOP), ac.territory_id(BLOG)
SEA = {p["id"]: bool(p["sea"]) for p in PLANS}

SIM_REQUIRED = ("apply", "update", "landState", "citizens", "buildings", "occupied", "byId", "governorAt", "railGroups",
                "railCount", "topCounts", "i18n", "landsOf", "landsOk", "landMove", "landFree", "hiddenHtml", "arr",
                "arrEntry", "arrBack", "arrWhy")

KEYS = ("arr.btn", "arr.on", "arr.tip", "arr.tipPick", "arr.hide", "arr.show", "arr.cancel", "arr.done", "arr.tray",
        "arr.waits", "arr.last", "arr.hidden", "arr.hiddenWait", "arr.manage", "arr.errTaken", "arr.errSea",
        "arr.errEmpty", "arr.errOther")


def view_of(shop_slot, blog=True):
    """The server's view of shop (meadow, two buildings, a rest place) and blog (ridge, one building)."""
    world = ac.new_world()
    rows = [(SHOP, "shop", "meadow", shop_slot, [0, 1])] + ([(BLOG, "blog", "ridge", [1, 0], [0])] if blog else [])
    for ident, name, plan, slot, plots in rows:
        plan_rec = next(p for p in PLANS if p["id"] == plan)
        world["territories"][ident] = {
            "name": name, "plan": plan, "slot": list(slot), "lines": 6000, "peak": 6000, "era": "village",
            "balance": {}, "rules_bad": [], "offices": {}, "rest": name == "shop",
            "buildings": [{"plot": k, "type": plan_rec["plots"][k][2], "by": "worker", "files": [], "hist": []} for k in plots]}
        world["order"].append(ident)
    view = ac.layout(world, PLANS)
    for t in view["territories"]:
        t.setdefault("sea", SEA[t["plan"]])   # the server's part of city-layout adds it; the page reads it
    return view


# the fixture island of the rule: dock is the coast land, its sea takes [-1, 1]
LANDS = [{"id": "aaaaaaaa", "name": "shop", "slot": [0, 0], "sea": False},
         {"id": "bbbbbbbb", "name": "blog", "slot": [1, 0], "sea": False},
         {"id": "cccccccc", "name": "dock", "slot": [-1, 0], "sea": True},
         {"id": "dddddddd", "name": "wood", "slot": [0, 1], "sea": False}]



def ref_ok(lands):
    seen = set()
    for l in lands:
        i, j = l["slot"]
        if abs(i) > 4 or abs(j) > 4 or (i, j) in seen:
            return False
        seen.add((i, j))
    return not any(l["sea"] and (l["slot"][0], l["slot"][1] + 1) in seen for l in lands)


def ref_move(lands, lid, slot):
    a = next((l for l in lands if l["id"] == lid), None)
    if a is None or a["slot"] == slot:
        return None
    b = next((l for l in lands if l is not a and l["slot"] == slot), None)
    after = [dict(l, slot=slot if l is a else a["slot"] if l is b else l["slot"]) for l in lands]
    if not ref_ok(after):
        return None
    return [{"id": lid, "slot": slot}] + ([{"id": b["id"], "slot": a["slot"]}] if b else [])


def ref_free(lands, lid):
    held = {tuple(l["slot"]) for l in lands}
    others = [l for l in lands if l["id"] != lid] or lands
    out = []
    for i in range(-4, 5):
        for j in range(-4, 5):
            if (i, j) in held or not any(abs(l["slot"][0] - i) + abs(l["slot"][1] - j) == 1 for l in others):
                continue
            if lid is None:
                if any(l["sea"] and (l["slot"][0], l["slot"][1] + 1) == (i, j) for l in lands):
                    continue
            elif ref_move(lands, lid, [i, j]) is None:
                continue
            out.append("%d,%d" % (i, j))
    return sorted(out)


DRIVER = r"""
const P = __payload, TA = P.ta, TB = P.tb;
function buildLand(view){ landState(view); }
const out = {};
function tick(sec){ for (let i = 0; i < Math.round(sec * 10); i++) update(.1); }
const of = terr => citizens.filter(c => c.terr === terr && !c.gone && !c.remote);
const pos = terr => { const o = {}; for (const c of of(terr)) o[c.id] = [c.x, c.y]; return o; };
const blds = terr => buildings.filter(b => b.terr === terr).map(b => ({ plot: b.plot, x: b.gx, z: b.gy, own: occupied.get(b.gx + ',' + b.gy) === b }))
  .sort((a, b) => a.plot - b.plot);
const cell = view => { const m = {}; for (const t of view.territories) m[t.id] = [t.cx, t.cz]; return m; };

// L1: the rule
out.landsOf = landsOf(P.v1);
out.ok = P.okCases.map(c => landsOk(c));
out.move = P.moveCases.map(([id, slot]) => landMove(P.lands, id, slot));
out.free = P.freeCases.map(id => landFree(P.lands, id).map(c => c.join(',')).sort());
out.freeAlone = landFree([P.lands[0]], P.lands[0].id).map(c => c.join(',')).sort();
out.landsAfter = JSON.stringify(P.lands);

// L2: what is hidden
out.hid0 = typeof hiddenLands === 'undefined' ? null : hiddenLands.length;
out.html = [hiddenHtml([]), hiddenHtml([{ id: 'x', name: 'blog', people: 2, wait: 0 }, { id: 'y', name: 'secret-repo', people: 0, wait: 0 }]),
  hiddenHtml([{ id: 'x', name: 'blog', people: 3, wait: 2 }, { id: 'y', name: 'secret-repo', people: 1, wait: 0 }])];

// L4: the mode's own answers
out.arr = JSON.parse(JSON.stringify(arr));
const hidden1 = [{ id: 'eeeeeeee', name: 'old', people: 0, wait: 0 }];
const entry = arrEntry(P.lands, hidden1);
out.entry = entry;
out.backSame = arrBack(entry, P.lands, hidden1);
const moved = P.lands.map(l => l.id === 'dddddddd' ? Object.assign({}, l, { slot: [1, 1] }) : l).filter(l => l.id !== 'bbbbbbbb')
  .concat([{ id: 'eeeeeeee', name: 'old', slot: [2, 0], sea: false }, { id: 'ffffffff', name: 'new', slot: [0, -1], sea: false }]);
out.back = arrBack(entry, moved, [{ id: 'bbbbbbbb', name: 'blog', people: 1, wait: 0 }]);
out.backGone = arrBack(entry, P.lands.filter(l => l.id !== 'cccccccc'), hidden1);
out.why = [[200, {}], [409, { error: 'taken' }], [409, { error: 'sea' }], [409, { error: 'empty' }], [400, { error: 'bad' }], [403, {}], [0, {}]]
  .map(([code, body]) => arrWhy(code, body));
out.texts = P.keys.map(k => i18n(k, { n: 2, name: 'shop' }));

// L3: people follow their land
const agents = [
  { id: 's:tm', role: 'task-manager', label: 'shop Manager', task: 'shop', stuck: false, done: false, tools: { Bash: 3 }, terr: TA },
  { id: 'a1', role: 'worker', label: 'worker', task: 'x', stuck: false, done: false, tools: { Edit: 2 }, terr: TA },
  { id: 'a2', role: 'worker', label: 'worker', task: 'y', stuck: false, done: true, tools: { Edit: 2 }, terr: TA },
  { id: 'b1', role: 'worker', label: 'worker', task: 'z', stuck: false, done: false, tools: { Read: 1 }, terr: TB }];
const snap = (view, list, hidden) => apply({ type: 'snapshot', world: view, gov: { state: 'busy', terr: TA }, govs: [{ terr: TA, state: 'busy' }],
  governors: 1, asks: [], shows: [], agents: list, hidden });
snap(P.v1, agents);
tick(20);
out.count1 = { top: topCounts().map(x => x[1]), rail: railCount(railGroups()) };
apply({ type: 'stuck', id: 'a1', tool: 'AskUserQuestion', question: 'q' });   // a1 walks to the hall
tick(.4);
out.walking = !!(byId('a1').path && byId('a1').path.length);
const p1 = { a: pos(TA), b: pos(TB), g: governorAt(TA) }, b1 = { a: blds(TA), b: blds(TB) };
snap(P.v2, agents.map(a => a.id === 'a1' ? Object.assign({}, a, { stuck: true }) : a));
const p2 = { a: pos(TA), b: pos(TB), g: governorAt(TA) };
out.step = Object.keys(p1.a).map(id => p2.a[id] ? [p2.a[id][0] - p1.a[id][0], p2.a[id][1] - p1.a[id][1]] : null);
out.still = Object.keys(p1.b).map(id => p2.b[id] ? [p2.b[id][0] - p1.b[id][0], p2.b[id][1] - p1.b[id][1]] : null);
out.govStep = p1.g && p2.g ? [p2.g.x - p1.g.x, p2.g.y - p1.g.y] : null;
out.blds1 = b1; out.blds2 = { a: blds(TA), b: blds(TB) };
out.want2 = { a: P.v2.territories.find(t => t.id === TA).buildings.map(b => ({ plot: b.plot, x: b.x, z: b.z })),
  b: P.v2.territories.find(t => t.id === TB).buildings.map(b => ({ plot: b.plot, x: b.x, z: b.z })) };
let far = 0;
const c2 = cell(P.v2);
for (let i = 0; i < 300; i++) {
  update(.1);
  for (const c of of(TA)) far = Math.max(far, Math.abs(c.x - c2[TA][0]), Math.abs(c.y - c2[TA][1]));
}
out.far = far;
out.people2 = of(TA).length;

// L2: the server says what is hidden and who waits there
out.count2a = { top: topCounts().map(x => x[1]), rail: railCount(railGroups()) };
apply({ type: 'hidden', lands: [{ id: 'eeeeeeee', name: 'old', people: 2, wait: 2 }] });
out.hidEvent = JSON.parse(JSON.stringify(hiddenLands));
out.count2 = { top: topCounts().map(x => x[1]), rail: railCount(railGroups()) };

// blog is hidden: the picture comes without it
snap(P.v3, agents.filter(a => a.terr === TA).map(a => a.id === 'a1' ? Object.assign({}, a, { stuck: true }) : a),
  [{ id: TB, name: 'blog', people: 1, wait: 1 }]);
out.gone = { people: of(TB).length, leaving: citizens.filter(c => c.terr === TB && c.state === 'leaving').length, blds: blds(TB).length,
  groups: railGroups().map(g => g.terr), hid: JSON.parse(JSON.stringify(hiddenLands)), shop: of(TA).length };
out.count3 = { top: topCounts().map(x => x[1]), rail: railCount(railGroups()) };
apply({ type: 'hidden', lands: [] });
out.count3a = { rail: railCount(railGroups()), hid: hiddenLands.length };
tick(5);
out.goneLater = citizens.filter(c => c.terr === TB && !c.gone).length;

// shown again: the picture brings it back; a picture without the key empties the list
snap(P.v2, agents.map(a => a.id === 'a1' ? Object.assign({}, a, { stuck: true }) : a));
const c = byId('b1');
out.back1 = { there: !!c && !c.gone, off: c ? [Math.abs(c.x - c2[TB][0]), Math.abs(c.y - c2[TB][1])] : null, hid: hiddenLands.length, blds: blds(TB).length };
__out = out;
"""


def payload():
    ok_cases = [LANDS,
                [dict(LANDS[0]), dict(LANDS[1], slot=[0, 0])],                         # two on one slot
                [dict(LANDS[2]), dict(LANDS[3], slot=[-1, 1])],                        # a land in the coast land's sea
                [dict(LANDS[2], slot=[0, -1]), dict(LANDS[0])],                        # the coast land north of a land
                [dict(LANDS[0], slot=[5, 0])], [dict(LANDS[0], slot=[0, -5])],         # off the grid
                [dict(LANDS[0], slot=[4, -4]), dict(LANDS[1], slot=[-4, 4])],          # the corners are on it
                [dict(LANDS[2]), dict(LANDS[3], slot=[-1, 2])]]                        # two cells south: fine
    move_cases = [["dddddddd", [1, 1]], ["aaaaaaaa", [1, 0]], ["dddddddd", [-1, 1]], ["cccccccc", [0, -1]],
                  ["dddddddd", [0, 1]], ["99999999", [2, 2]], ["cccccccc", [0, 0]], ["cccccccc", [1, 0]]]
    return {"v1": view_of([0, 0]), "v2": view_of([1, 1]), "v3": view_of([1, 1], blog=False), "ta": TA, "tb": TB,
            "lands": LANDS, "okCases": ok_cases, "moveCases": move_cases, "freeCases": ["dddddddd", "cccccccc", None],
            "keys": list(KEYS)}


class SimCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(DRIVER, payload(), SIM_REQUIRED)


# ---------------------------------------------------------------------------
# L1: the rule
# ---------------------------------------------------------------------------

class TestTheRule(SimCase):
    def test_the_lands_of_a_view(self):
        self.assertEqual(self.r["landsOf"], [{"id": TA, "name": "shop", "slot": [0, 0], "sea": False},
                                             {"id": TB, "name": "blog", "slot": [1, 0], "sea": False}])

    def test_what_is_a_good_arrangement(self):
        self.assertEqual(self.r["ok"], [True, False, False, False, False, False, True, True])

    def test_a_move_to_a_free_slot(self):
        self.assertEqual(self.r["move"][0], [{"id": "dddddddd", "slot": [1, 1]}])

    def test_a_drop_on_a_land_swaps_the_two(self):
        self.assertEqual(self.r["move"][1], [{"id": "aaaaaaaa", "slot": [1, 0]}, {"id": "bbbbbbbb", "slot": [0, 0]}])
        self.assertEqual(self.r["move"][7], [{"id": "cccccccc", "slot": [1, 0]}, {"id": "bbbbbbbb", "slot": [-1, 0]}],
                         "the coast land swaps with blog: nothing lies south of [1, 0]")

    def test_what_the_rule_refuses(self):
        self.assertIsNone(self.r["move"][2], "the cell south of the coast land is its sea")
        self.assertIsNone(self.r["move"][3], "the coast land may not go north of a land")
        self.assertIsNone(self.r["move"][4], "its own slot is no move")
        self.assertIsNone(self.r["move"][5], "an unknown land")
        self.assertIsNone(self.r["move"][6], "a swap that leaves wood in the coast land's sea")

    def test_every_case_as_the_rule_says(self):
        p = payload()
        self.assertEqual(self.r["ok"], [ref_ok(c) for c in p["okCases"]])
        self.assertEqual(self.r["move"], [ref_move(LANDS, i, s) for i, s in p["moveCases"]])

    def test_the_free_slots_of_a_land(self):
        wood, dock = self.r["free"][0], self.r["free"][1]
        self.assertEqual(wood, ref_free(LANDS, "dddddddd"))
        self.assertEqual(dock, ref_free(LANDS, "cccccccc"))
        self.assertNotIn("-1,1", wood, "the sea of the coast land")
        self.assertNotIn("0,1", wood, "its own slot is no move")
        self.assertIn("1,1", wood)
        self.assertNotIn("0,-1", dock, "the coast land may not lie north of shop")
        self.assertIn("-1,1", dock, "one step south: its sea goes with it")
        self.assertNotIn("3,0", wood, "a slot must touch the island")

    def test_the_free_slots_before_a_land_is_picked(self):
        self.assertEqual(self.r["free"][2], ref_free(LANDS, None))
        self.assertEqual(self.r["free"][2], sorted(["0,-1", "1,-1", "-1,-1", "2,0", "-2,0", "1,1", "0,2"]))

    def test_a_land_alone_may_step_to_its_own_neighbours(self):
        self.assertEqual(self.r["freeAlone"], sorted(["1,0", "-1,0", "0,1", "0,-1"]))

    def test_the_helpers_change_nothing(self):
        self.assertEqual(json.loads(self.r["landsAfter"]), LANDS)


# ---------------------------------------------------------------------------
# L2: what is hidden
# ---------------------------------------------------------------------------

class TestHidden(SimCase):
    def test_nothing_is_hidden_at_start(self):
        self.assertEqual(self.r["hid0"], 0)
        self.assertEqual(self.r["html"][0], "")

    def test_the_quiet_line(self):
        self.assertEqual(self.r["html"][1], "<i></i><span>已隐藏 2 个</span><u>管理</u>")

    def test_the_line_says_that_somebody_waits(self):
        self.assertEqual(self.r["html"][2], "<i></i><span>已隐藏 2 个 · 其中 1 个在等你</span><u>管理</u>")
        for html in self.r["html"]:
            self.assertNotIn("secret-repo", html, "a hidden repo's name is not on the page outside the mode")

    def test_the_server_says_what_is_hidden(self):
        self.assertEqual(self.r["hidEvent"], [{"id": "eeeeeeee", "name": "old", "people": 2, "wait": 2}])
        self.assertEqual(self.r["gone"]["hid"], [{"id": TB, "name": "blog", "people": 1, "wait": 1}], "from the snapshot")
        self.assertEqual(self.r["back1"]["hid"], 0, "a picture without the key: nothing is hidden")

    def test_the_rails_red_count_takes_them_in(self):
        before, after = self.r["count2a"]["rail"], self.r["count2"]["rail"]
        self.assertEqual(after["you"], before["you"] + 2, "the 2 who wait in the hidden repo")
        self.assertEqual(after["active"], before["active"], "they are not in the rail's rows")
        self.assertEqual(self.r["count3a"]["hid"], 0)
        self.assertEqual(self.r["count3"]["rail"]["you"], self.r["count3a"]["rail"]["you"] + 1, "the one who waits in hidden blog")

    def test_the_top_counts_are_the_shown_repos(self):
        self.assertEqual(sum(self.r["count1"]["top"][:3]), 5, "the fixture: 3 in shop and its busy governor, 1 in blog")
        self.assertEqual(self.r["count2"]["top"], self.r["count2a"]["top"], "people the server only counts are not in the top counts")
        self.assertEqual(sum(self.r["count3"]["top"][:3]), 4, "blog is hidden: its person leaves the counts at once")


# ---------------------------------------------------------------------------
# L3: people follow their land
# ---------------------------------------------------------------------------

class TestPeopleFollow(SimCase):
    def test_everybody_of_a_moved_land_moves_with_it_at_once(self):
        self.assertTrue(self.r["walking"], "the fixture: a1 walks while the land moves")
        self.assertEqual(len(self.r["step"]), 3)
        for step in self.r["step"]:
            self.assertIsNotNone(step, "nobody of a moved land may vanish")
            self.assertAlmostEqual(step[0], 22, places=6)
            self.assertAlmostEqual(step[1], 22, places=6)

    def test_its_governor_too(self):
        self.assertIsNotNone(self.r["govStep"])
        self.assertAlmostEqual(self.r["govStep"][0], 22, places=6)
        self.assertAlmostEqual(self.r["govStep"][1], 22, places=6)

    def test_a_land_that_did_not_move_is_left_alone(self):
        self.assertEqual(self.r["still"], [[0, 0]])
        self.assertEqual(self.r["blds2"]["b"], self.r["blds1"]["b"])

    def test_nobody_walks_back_over_the_sea(self):
        self.assertEqual(self.r["people2"], 3)
        self.assertLessEqual(self.r["far"], 11.5, "30 s later everybody of the moved land is still on it")

    def test_its_buildings_stand_on_the_new_place(self):
        got = [{k: b[k] for k in ("plot", "x", "z")} for b in self.r["blds2"]["a"]]
        self.assertEqual(got, sorted(self.r["want2"]["a"], key=lambda b: b["plot"]))
        self.assertTrue(all(b["own"] for b in self.r["blds2"]["a"]), "occupied is keyed by the new place")
        self.assertEqual(len(self.r["blds1"]["a"]), 2)

    def test_a_hidden_lands_people_are_gone_at_once(self):
        gone = self.r["gone"]
        self.assertEqual((gone["people"], gone["leaving"]), (0, 0), "no walk to the edge of a land that is not there")
        self.assertEqual(gone["blds"], 0)
        self.assertEqual(gone["groups"], [TA], "no rail group")
        self.assertEqual(gone["shop"], 3, "the others stay")
        self.assertEqual(self.r["goneLater"], 0)

    def test_shown_again_its_people_stand_on_it(self):
        back = self.r["back1"]
        self.assertTrue(back["there"])
        self.assertLessEqual(max(back["off"]), 11.5)
        self.assertEqual(back["blds"], 1)


# ---------------------------------------------------------------------------
# L4: the mode
# ---------------------------------------------------------------------------

class TestTheMode(SimCase):
    def test_off_at_start(self):
        self.assertEqual(self.r["arr"], {"on": False, "pick": None, "entry": None, "err": ""})

    def test_what_cancel_goes_back_to(self):
        self.assertEqual(self.r["entry"], [{"id": l["id"], "slot": l["slot"], "hidden": False} for l in LANDS]
                         + [{"id": "eeeeeeee", "hidden": True}])

    def test_nothing_changed_nothing_is_sent(self):
        self.assertEqual(self.r["backSame"], [])

    def test_cancel_puts_everything_back(self):
        # wood moved, blog was hidden, old was shown, "new" came meanwhile
        self.assertEqual(sorted(self.r["back"], key=lambda r: r["id"]),
                         [{"id": "bbbbbbbb", "slot": [1, 0], "hidden": False}, {"id": "dddddddd", "slot": [0, 1], "hidden": False},
                          {"id": "eeeeeeee", "hidden": True}])

    def test_a_land_that_is_gone_is_not_named(self):
        self.assertEqual(self.r["backGone"], [])

    def test_a_refusal_is_said_in_plain_words(self):
        why = self.r["why"]
        self.assertEqual(why[0], "")
        self.assertEqual(len(set(why[1:4])), 3, "taken, sea and empty each have their own words")
        self.assertTrue(all(why[1:]), "never silent")
        self.assertEqual(len(set(why[4:])), 1, "everything else is one sentence")
        self.assertNotIn(why[4], why[1:4])

    def test_the_words(self):
        for key, text in zip(KEYS, self.r["texts"]):
            with self.subTest(key=key):
                self.assertTrue(text and text != key, "no text for %s" % key)
                self.assertEqual(text_keys(key), 2, "%s: once in zh, once in en" % key)
        zh = dict(zip(KEYS, self.r["texts"]))
        self.assertEqual((zh["arr.btn"], zh["arr.on"], zh["arr.cancel"], zh["arr.done"], zh["arr.hide"], zh["arr.show"]),
                         ("整理", "整理中", "取消", "完成", "隐藏", "显示"))
        self.assertIn("shop", zh["arr.tipPick"])
        self.assertIn("2", zh["arr.waits"])


class TestThePage(unittest.TestCase):
    """The 3D part, on its source."""

    @classmethod
    def setUpClass(cls):
        cls.html = page()
        cls.script = cls.html[cls.html.index("'use strict'"):]

    def test_one_small_control_at_the_end_of_the_repo_row(self):
        m = re.search(r'<div class="stage-top" id="stage-top">(.*?)</div>', self.html, re.S)
        self.assertIsNotNone(m, "the strip on the stage (cloud-polish) is not in the page")
        inner = m.group(1)
        self.assertRegex(inner, r'<button type="button" class="arr-btn" id="arr-btn" aria-pressed="false"[^>]*\bhidden\b')
        self.assertLess(inner.index('id="repos"'), inner.index('id="arr-btn"'), "after the repo row")
        self.assertEqual(self.html.count('id="arr-btn"'), 1)
        r = rule(".arr-btn")
        self.assertIn("position:absolute", r.replace(" ", ""), "pinned: it never scrolls away with the tags")
        self.assertTrue(rule('.arr-btn[aria-pressed="true"]'), "it looks pressed while the mode is on")

    def test_only_the_live_local_page_has_it(self):
        self.assertRegex(self.script, r"\$\('#arr-btn'\)\.hidden\s*=\s*DEMO\s*\|\|\s*CLOUD",
                         "the demo and the cloud page have no arrange control")
        enter = function_source("arrEnter") or ""
        self.assertRegex(enter[:enter.find("arr.on = true")], r"if \([^)]*DEMO \|\| CLOUD[^)]*\)\s*return",
                         "and no mode: the cloud page never sends /api/layout (its Worker has no such route)")

    def test_the_bar_and_the_plates(self):
        stage = self.html[self.html.index('<div class="stage" id="stage">'):self.html.index("</main>")]
        self.assertRegex(stage, r'<div class="arr-ov" id="arr-ov"></div>')
        m = re.search(r'<div class="arr-bar" id="arr-bar" role="region"[^>]*\bhidden\b[^>]*>', stage)
        self.assertIsNotNone(m, "the mode's bar, hidden until the mode opens")
        for part in ('id="arr-tip"', 'id="arr-tray"', 'id="arr-err" role="alert"',
                     'id="arr-cancel" data-t="arr.cancel"', 'id="arr-done" data-t="arr.done"'):
            self.assertIn(part, stage)
        bar = rule(".arr-bar").replace(" ", "")
        self.assertIn("position:absolute", bar)
        self.assertIn("bottom:", bar, "at the stage's bottom edge: it covers no land")
        for sel in (".arr-ov", ".arr-h", ".arr-h.on", ".arr-eye", ".arr-tray", ".arr-hid"):
            self.assertTrue(rule(sel), "no CSS rule for %s" % sel)

    def test_phone(self):
        m = media_960()
        self.assertTrue(rule(".arr-bar", m), "the bar has its phone rule")
        self.assertIn("display:none", rule(".arr-h .arr-eye", m).replace(" ", ""), "a plate is the name alone")
        self.assertTrue(rule(".arr-h.on .arr-eye", m), "the picked plate shows 隐藏")

    def test_the_hidden_line_at_the_rails_foot(self):
        start = self.html.index('<aside class="rail" id="rail"')
        rail = self.html[start:self.html.index("</aside>", start)]
        self.assertRegex(rail, r'<button type="button" class="rail-hid" id="rail-hid"[^>]*\bhidden\b')
        self.assertLess(rail.index('id="rail-list"'), rail.index('id="rail-hid"'), "at the foot")
        self.assertTrue(rule(".rail-hid"))
        self.assertTrue(rule(".rail-hid.you"), "it turns red when somebody there waits")
        src = function_source("renderRail") or ""
        self.assertIn("hiddenHtml(hiddenLands)", src)
        self.assertRegex(src, r"DEMO\s*\|\|\s*CLOUD", "the line is the live local page's")
        block = listener_block(r"\$\('#rail-hid'\)", "click")
        self.assertIsNotNone(block, "a click on the line must do something")
        self.assertIn("arrEnter(", block)

    def test_one_request_behind_the_gate(self):
        src = function_source("layoutPost")
        self.assertIsNotNone(src, "function layoutPost(lands) is missing")
        self.assertIn("'/api/layout'", src)
        self.assertRegex(src, r"method:\s*'POST'")
        self.assertRegex(src, r"'X-City-Token':\s*TOKEN")
        self.assertRegex(src, r"JSON\.stringify\(\{\s*lands\s*\}\)", "ids, slots and the flag: nothing else goes up")
        self.assertIn("arrWhy(", src)
        self.assertEqual(self.script.count("'/api/layout'"), 1, "one place sends it")

    def test_the_page_never_guesses_the_island(self):
        for name in ("arrEnter", "arrLeave", "layoutPost"):
            src = function_source(name)
            self.assertIsNotNone(src, "function %s is missing" % name)
            self.assertNotIn("buildLand(", src, "the island changes through the server's picture only")

    def test_what_pauses(self):
        self.assertIn("arr.on", function_source("autoRotating") or "", "the camera's own turn stops in the mode")
        self.assertIn("arr.on", function_source("selectPick") or "", "a tap in the mode opens nobody")
        enter = function_source("arrEnter") or ""
        self.assertIn("stopFollow()", enter)
        self.assertIn("distMax()", enter, "the whole island comes into view")
        self.assertIn("arrEntry(", enter)

    def test_cancel_and_done(self):
        cancel = listener_block(r"\$\('#arr-cancel'\)", "click") or ""
        self.assertIn("arrBack(", cancel)
        self.assertIn("arrLeave(", cancel)
        done = listener_block(r"\$\('#arr-done'\)", "click") or ""
        self.assertIn("arrLeave(", done)
        self.assertNotIn("layoutPost(", done, "every drop is saved when it is made: Done only leaves")

    def test_a_running_era_show_follows_its_land(self):
        # seen in the browser (task manager, 2026-10-02): a land moved while its era show ran (a fresh server, the
        # first page): the show's small builders stayed on the old cell, in the sea, until the show ended (60 s)
        src = function_source("buildLand") or ""
        self.assertIn("showRuns", src, "buildLand() must look at the running shows")
        self.assertIn("dropShowRun(", src, "the show of a land that moved is dropped there: stepShows() starts it "
                      "again from the new view, so its builders stand on the land")
        self.assertIn("landSteps(", src, "which lands moved: the same compare landState() uses, taken before it runs")

    def test_css_has_no_leftover_of_the_mock(self):
        self.assertNotIn(".q1", css())
        self.assertNotIn("mockApi", self.html)


if __name__ == "__main__":
    unittest.main()
