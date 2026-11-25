"""Failing tests for city-office, the PAGE (requirements/city.md, "Office"; owner 2026-11-24, prototype approved
2026-11-25: mock/city-office-mock.html v5, "ok already, can approve", select zoom halved). The island goes; the
page becomes one office building, one floor per ticked repo. The server side: tests/test_agent_city_office.py
(the office view the snapshot carries, the endpoints the page calls).

The look, the furniture, the outside view, the avatars, the lift, the floor sign, the design box, the floor
picker and the renovation flow are the MOCK's: port its CSS and its scene code (buildFloor, buildOutside,
DECOR, SLOTS, addPerson/STYLE, the camera, enter/goOutside/goFloor, renderLift/renderFloorSign,
renderPicker, renderDesignPop/saveDiy/askRenovate/hireDesigner). The mock's own stand-ins are NOT ported: its
fake REPOS/P/THEMES data, its demo buttons, its fake designer replies (planFrom/designerHear: the real
designer is an agent session, the owner talks to it in its panel as with any session).

CONTRACT (bin/agent-city.html). "sim section" = the page script from 'use strict' up to the '3D view.' comment,
driven in node (tests/test_agent_city_people.py run_sim). "3D part" = the rest, checked on its source.

F1 the building (sim)
  FLOOR_GAP = 60. Every floor has its own stretch of the sim's ground: floor n (1-based) has cx = (n-1) *
    FLOOR_GAP, cz = 0, and a person on it stands at c.x = cx + local x, c.y = cz + local z. Only one floor is
    drawn at a time; the others go on in the sim.
  officeState(view): VIEW is the server's office view {v: 2, repos, floors (bottom first), designs, asked}.
    Sets `map` to {v, repos, floors, designs, asked, territories}, territories = the floors TOP FIRST, each
    {id, name, here, n, floor, cx, cz} (name/here/n from repos; an id of floors that is no repo is dropped).
    People of a repo that is no longer a floor are gone at once (c.gone). apply() calls it for the snapshot's
    "world" and for every {"type": "world"} event; a world event's "change" of kind "design" also logs one
    line naming the floor and the design name; "design_bad" logs one line naming the floor and every
    problem's zh. buildLand/landState no longer exist.
  floorOf(terr) -> its floor number (1 = bottom), 0 when it is not a floor. floorName(n) -> "G" for 0, else
    n + "F".
  FLOOR_DECOR: the 15 catalogue ids of the server, same order.
  themeOf(terr) -> {name, why, colors, decor, designed}: the floor's design read as DATA only: colors has the
    9 keys (accent carpet manager_floor pantry_floor desk desk_leg chair meeting_rug manager_rug), each the
    design's value when it is "#RRGGBB", else the base look's; decor is 3 entries, each a FLOOR_DECOR id or
    "none" (anything else -> "none"); name is the design's name, or i18n('office.noDesign') = 还没装修
    when there is no design; designed = there is one.
  needsAsk(terr) -> true when the live page (not DEMO) shows a floor with no design, the server's asked list
    does not have it, and no designer is on that floor. (The 3D part then asks once: 请室内设计师 / 自己装修
    / 先不装修.)

F2 who is shown (sim)
  SESSION_ROLES = ['task-manager', 'helper', 'designer']; isSub(c) -> its role is none of them.
  roleWord(role) -> 'governor' 区经理, 'task-manager' 经理, 'helper' 助理, 'designer' 设计师, else ''.
  No zh text of the page says 总督 any more: the governor is 区经理 everywhere (TEXT.zh).
  Subagents stay in the sim (their talks, relays and asks work as before) but are never drawn and never a rail
    row. subBadge(rowId) -> '' or e.g. 'worker ×2 · deputy ×1': the live subagents (not gone) whose up (else
    lead) is that row ('s:<sid>' or 'gov:<terr>'); a role ending in 'deputy' counts as deputy, any other as
    worker; worker first, a part only when its count > 0.
  railGroups() -> one group per floor, top first: {terr, name: floorName(n) + ' · ' + repo, color, add, rows};
    rows as before (the tree, resting last) but sessions and the governor only, each row with badge =
    subBadge(row id). The server's up puts every session under the governor's row ('gov:<terr>').
  rowWaitsOnYou(row) is also true when a subagent of that row waits on the owner: a question is never hidden.
  topCounts() -> [[i18n('top.work'), n], [i18n('top.ask'), n], [i18n('top.rest'), n]]: sessions and governors
    only (what the building shows); no 建成, no stalled sites. zh top.ask = 找区经理.
  floorTag(terr) -> {floor: 'nF', repo, design: themeOf(terr).name, people, wait}: people = the governor (when
    there) + the sessions on that floor (not gone); wait = how many of those wait on the owner, their
    subagents' asks included. The outside tags and the lift panel show these.

F3 where people are (sim; local coordinates of the mock, x east, z south)
  MGR_SEAT {x: 4.6, z: -6.2}; LIFT_CALL {x: -1.05, z: -5.5}; LIFT_IN, LIFT_OUT: 2 spots each (the mock's);
  ASSIST_DESKS: 3 desks, x = 2.9 + k * 1.5, z = -1.6; TM_DESKS: 9 desks, x in [-5.7, -3.2, -0.7], z in
  [-1.3, 1.6, 4.5], row by row; PANTRY: the mock's 6 spots (north-west); MEET: at least 4 spots in the meeting
  corner (south-east, around x 4.6, z 4.0).
  seatOf(c) -> {x, y} in sim ground coordinates of c's floor: a helper -> ASSIST_DESKS[k] (k = its place among
    the helpers of that floor, citizens order), a task manager -> TM_DESKS[k] (same), the 4th+ helper and the
    10th+ task manager -> a MEET spot; the designer -> a MEET spot; an idle or resting session -> a PANTRY spot.
  deskCount(terr) -> min(9, task managers on that floor + 1): the open office has one desk more than
    managers.
  The floor is a walk grid (the mock's: 0.4 cells over 14 x 14): walkable(x, y) is false inside a desk, a
    wall, the lift shaft or the glass room's walls, true in an aisle; findPath never goes through a
    blocked cell. People of another floor never block anyone.
  c.at = the floor (terr id) a person is on now: its own floor, or the floor it is visiting.

F4 between floors (sim; owner: "he pressing the lift and wait then sit the lift to that floor and talk")
  A talk (Face to face) whose sender and recipient are on different floors is no longer "no walk": the
  sender walks to LIFT_CALL, waits for the door, steps into the lift and is gone from its floor, comes out
  of the lift on the recipient's floor (c.at changes only then, and c.x/c.y are at LIFT_IN/LIFT_OUT of that
  floor), walks to the recipient, they talk, and it rides back the same way to its own floor and seat.

F5 the 3D part (source)
  Box avatars of the mock by role (STYLE: governor/区经理 dark suit and red tie, task manager light shirt, tie
    and lanyard, helper cardigan and clipboard, designer dark top, beret and tablet). No GLTF models: the page
    loads three.min.js only, and bin/agent-city-assets holds vendor/three.min.js and nothing else.
  The page opens outside, every time (let view = 'outside'). enter(terr) goes in through the door; goFloor
    switches at once (no camTween in it); goOutside comes back out.
  Selecting a person zooms in half as far as the island did: cam.wantDist = Math.min(cam.dist, (fitDist() +
    9) / 2).
  DECOR has exactly the 15 FLOOR_DECOR pieces; SLOTS has 3.
  Markup: #btnPick (选楼层), #lift, #floorSign, #tags, #pickBg, #dPop, #renoBg; none of the island's: #repos,
    #stage-top, #arr-btn, #arr-bar, #arr-ov, #rail-hid, #cap-hint, #empty-land.
  The page calls /api/floors, /api/design, /api/designer and /api/designer/leave, never /api/layout. A design
    is data: no eval, no new Function; the design name goes through esc().
  No island code: no buildLand, landState, landsOf, startShow, syncSites, newBuildingRecord, buildingName.
"""

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
PAGE = os.path.join(BIN, "agent-city.html")
ASSETS = os.path.join(BIN, "agent-city-assets")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from test_agent_city_people import run_sim, sim_section, function_source  # noqa: E402

T1, T2, T3 = "aaaa0001", "bbbb0002", "cccc0003"
GOOD = {"v": 1, "name": "收银台风格", "why": "POS",
        "colors": {"accent": "#2E7D6B", "carpet": "#E4DCCB", "manager_floor": "#D9C2A0", "pantry_floor": "#EEEAE0",
                   "desk": "#EFDAB5", "desk_leg": "#BBA27C", "chair": "#3E4560", "meeting_rug": "#A9BCE0",
                   "manager_rug": "#C97B66"},
        "decor": ["cashier", "none", "goods"]}
VIEW = {"v": 2,
        "repos": [{"id": T1, "name": "shop", "here": True, "n": 0}, {"id": T2, "name": "blog", "here": True, "n": 1},
                  {"id": T3, "name": "wiki", "here": False, "n": 2}],
        "floors": [T1, T2], "designs": {T2: GOOD}, "asked": [T2]}


def agent(aid, role, terr, up="", status="", done=False, lead=""):
    return {"id": aid, "role": role, "label": aid, "task": aid, "stuck": False, "waiting": status == "waiting",
            "done": done, "status": status, "tools": {}, "terr": terr, "relay": "", "lead": lead, "office": None,
            "up": up}


def page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


SNAP = r"""
function snap(view, agents, govs){
  apply({ type: 'snapshot', world: view, agents: agents || [], govs: govs || [], gov: { state: 'idle', terr: view.floors[0] },
          asks: [], governors: (govs || []).length, adding: [], hist: {} });
}
function settle(sec){ for (let t = 0; t < sec; t += 0.05) update(0.05); }
"""


def sim(driver, payload=None, required=("officeState", "apply", "update", "citizens", "byId")):
    return run_sim(SNAP + driver, payload or {}, required=required)


# ---------------------------------------------------------------------------
# F1 the building
# ---------------------------------------------------------------------------

class TestBuilding(unittest.TestCase):
    def test_office_state(self):
        out = sim("""
officeState(__payload.view);
__out = { terrs: map.territories.map(t => [t.id, t.name, t.floor, t.cx, t.cz, t.here]),
          f1: floorOf(__payload.t1), f2: floorOf(__payload.t2), f3: floorOf(__payload.t3),
          names: [floorName(0), floorName(1), floorName(12)], gap: FLOOR_GAP };
""", {"view": VIEW, "t1": T1, "t2": T2, "t3": T3}, required=("officeState", "floorOf", "floorName", "map"))
        self.assertEqual(out["terrs"], [[T2, "blog", 2, 60, 0, True], [T1, "shop", 1, 0, 0, True]], "top first")
        self.assertEqual((out["f1"], out["f2"], out["f3"]), (1, 2, 0))
        self.assertEqual(out["names"], ["G", "1F", "12F"])
        self.assertEqual(out["gap"], 60)

    def test_an_unknown_floor_id_is_dropped(self):
        view = dict(VIEW, floors=[T1, "dead0000"])
        out = sim("officeState(__payload.v); __out = map.territories.map(t => t.id);", {"v": view},
                  required=("officeState", "map"))
        self.assertEqual(out, [T1])

    def test_untick_removes_its_people_at_once(self):
        out = sim("""
snap(__payload.view, __payload.agents);
apply({ type: 'world', world: Object.assign({}, __payload.view, { floors: [__payload.t2] }) });
__out = citizens.filter(c => !c.gone).map(c => c.id);
""", {"view": VIEW, "t2": T2, "agents": [agent("s:a", "helper", T1), agent("s:b", "helper", T2)]})
        self.assertEqual(out, ["s:b"])

    def test_theme_is_data_only(self):
        bad = json.loads(json.dumps(GOOD))
        bad["colors"]["carpet"] = "javascript:alert(1)"
        bad["decor"] = ["robot", "<img onerror=x>", "plants"]
        view = dict(VIEW, designs={T2: bad})
        out = sim("""
officeState(__payload.v);
const a = themeOf(__payload.t1), b = themeOf(__payload.t2);
__out = { a, b, decor: FLOOR_DECOR };
""", {"v": view, "t1": T1, "t2": T2}, required=("officeState", "themeOf", "FLOOR_DECOR"))
        a, b = out["a"], out["b"]
        self.assertEqual((a["name"], a["designed"], a["decor"]), ("还没装修", False, ["none", "none", "none"]))
        self.assertEqual(sorted(a["colors"]), sorted(GOOD["colors"]))
        self.assertTrue(all(re.fullmatch(r"#[0-9A-Fa-f]{6}", v) for v in a["colors"].values()))
        self.assertEqual((b["name"], b["designed"]), ("收银台风格", True))
        self.assertEqual(b["colors"]["carpet"], a["colors"]["carpet"], "a bad value falls back to the base look")
        self.assertEqual(b["colors"]["accent"], "#2E7D6B")
        self.assertEqual(b["decor"], ["robot", "none", "plants"])
        self.assertEqual(out["decor"], ["robot", "conveyor", "gears", "chart", "plants", "safe", "cabinets", "printer",
                                        "bookshelf", "clock", "cashier", "goods", "menu", "scanner", "lightbox"])

    def test_needs_ask(self):
        out = sim("""
snap(__payload.view, __payload.agents);
const before = [needsAsk(__payload.t1), needsAsk(__payload.t2)];
apply({ type: 'spawn', id: 's:d', role: 'designer', label: 'shop Designer', task: 'x', terr: __payload.t1,
        up: 'gov:' + __payload.t1 });
__out = { before, withDesigner: needsAsk(__payload.t1) };
""", {"view": VIEW, "t1": T1, "t2": T2, "agents": []})
        self.assertEqual(out["before"], [True, False], "shop: no design, not asked; blog has one")
        self.assertFalse(out["withDesigner"])

    def test_world_event_logs_the_change(self):
        out = sim("""
snap(__payload.view, []);
apply({ type: 'world', world: __payload.view2, change: { kind: 'design', terr: __payload.t1, by: 'designer' } });
apply({ type: 'design_bad', terr: __payload.t1, problems: [{ field: 'colors.carpet', zh: '地毯的亮度是 20%，要在 55%–95% 之间', en: 'x' }] });
__out = logEntries.map(e => String(e.text));
""", {"view": VIEW, "t1": T1, "view2": dict(VIEW, designs={T1: GOOD, T2: GOOD})})
        self.assertTrue(any("收银台风格" in s and "1F" in s for s in out), out)
        self.assertTrue(any("地毯的亮度是 20%" in s and "1F" in s for s in out), out)


# ---------------------------------------------------------------------------
# F2 who is shown
# ---------------------------------------------------------------------------

class TestWho(unittest.TestCase):
    def test_role_words(self):
        out = sim("__out = ['governor','task-manager','helper','designer','worker'].map(roleWord);",
                  required=("roleWord",))
        self.assertEqual(out, ["区经理", "经理", "助理", "设计师", ""])

    def test_no_governor_word_left(self):
        out = sim("__out = Object.values(TEXT.zh).filter(s => String(s).includes('总督'));", required=("TEXT",))
        self.assertEqual(out, [])

    def test_rail_floors_and_badges(self):
        agents = [agent("s:h", "helper", T1, up="gov:" + T1), agent("s:t", "task-manager", T1, up="gov:" + T1),
                  agent("w1", "worker", T1, up="s:t"), agent("w2", "worker", T1, up="s:t"),
                  agent("d1", "merge-deputy", T1, up="gov:" + T1), agent("s:b", "helper", T2, up="gov:" + T2)]
        out = sim("""
snap(__payload.view, __payload.agents, [{ terr: __payload.t1, state: 'busy' }]);
const g = railGroups();
__out = { groups: g.map(x => ({ terr: x.terr, name: x.name, rows: x.rows.map(r => [r.id, r.depth, r.badge]) })),
          badge: subBadge('s:t'), none: subBadge('s:h'), subs: citizens.filter(isSub).map(c => c.id).sort(),
          counts: topCounts() };
""", {"view": VIEW, "agents": agents, "t1": T1})
        self.assertEqual([g["name"] for g in out["groups"]], ["2F · blog", "1F · shop"], "top floor first")
        rows = {r[0]: r for r in out["groups"][1]["rows"]}
        self.assertEqual(set(rows), {"gov:" + T1, "s:h", "s:t"}, "no subagent rows")
        self.assertEqual(rows["s:t"][1], 1, "under the area manager")
        self.assertEqual(rows["s:t"][2], "worker ×2")
        self.assertEqual(rows["gov:" + T1][2], "deputy ×1")
        self.assertEqual((out["badge"], out["none"]), ("worker ×2", ""))
        self.assertEqual(out["subs"], ["d1", "w1", "w2"])
        self.assertEqual([c[0] for c in out["counts"]], ["干活", "找区经理", "休息"])
        self.assertEqual(sum(c[1] for c in out["counts"]), 4, "3 sessions + 1 governor, no subagents")

    def test_a_waiting_subagent_shows_on_its_parent(self):
        agents = [agent("s:t", "task-manager", T1, up="gov:" + T1), agent("w1", "worker", T1, up="s:t", status="waiting")]
        out = sim("""
snap(__payload.view, __payload.agents);
const g = railGroups().find(x => x.terr === __payload.t1);
const row = g.rows.find(r => r.id === 's:t');
__out = { waits: rowWaitsOnYou(row), count: railCount(railGroups()).you, tag: floorTag(__payload.t1) };
""", {"view": VIEW, "agents": agents, "t1": T1})
        self.assertTrue(out["waits"])
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["tag"], {"floor": "1F", "repo": "shop", "design": "还没装修", "people": 1, "wait": 1})


# ---------------------------------------------------------------------------
# F3 seats and the walk grid
# ---------------------------------------------------------------------------

class TestSeats(unittest.TestCase):
    def test_desks(self):
        agents = [agent("s:h%d" % i, "helper", T2, up="gov:" + T2, status="") for i in range(4)] + \
                 [agent("s:t%d" % i, "task-manager", T2, up="gov:" + T2) for i in range(10)] + \
                 [agent("s:d", "designer", T2, up="gov:" + T2), agent("s:i", "helper", T2, status="idle")]
        out = sim("""
snap(__payload.view, __payload.agents);
const loc = c => { const s = seatOf(c); return [Math.round((s.x - 60) * 100) / 100, Math.round(s.y * 100) / 100]; };
__out = { seats: Object.fromEntries(citizens.map(c => [c.id, loc(c)])), desks: deskCount(__payload.t2),
          meet: MEET.map(m => [m.x, m.z]), pantry: PANTRY.map(m => [m.x, m.z]) };
""", {"view": VIEW, "agents": agents, "t2": T2})
        s = out["seats"]
        self.assertEqual([s["s:h%d" % i] for i in range(3)], [[2.9, -1.6], [4.4, -1.6], [5.9, -1.6]])
        self.assertEqual(s["s:t0"], [-5.7, -1.3])
        self.assertEqual(s["s:t4"], [-3.2, 1.6])
        self.assertEqual(s["s:t8"], [-0.7, 4.5])
        meet = [list(m) for m in out["meet"]]
        self.assertGreaterEqual(len(meet), 4)
        for k in ("s:h3", "s:t9", "s:d"):
            self.assertIn(s[k], [[round(a, 2), round(b, 2)] for a, b in meet], k + " goes to the meeting corner")
        self.assertIn(s["s:i"], [[round(a, 2), round(b, 2)] for a, b in out["pantry"]], "idle -> pantry")
        self.assertEqual(out["desks"], 9)

    def test_desk_count_and_walk_grid(self):
        agents = [agent("s:t0", "task-manager", T1, up="gov:" + T1)]
        out = sim("""
snap(__payload.view, __payload.agents);
const p = findPath(LIFT_OUT[0].x, LIFT_OUT[0].z, TM_DESKS[8].x + 1.25, TM_DESKS[8].z);
__out = { desks: deskCount(__payload.t1), aisle: walkable(-1.95, 0.1), desk: walkable(TM_DESKS[0].x, TM_DESKS[0].z),
          shaft: walkable(-1.05, -6.9), path: p.length, bad: p.filter(q => !walkable(q.x, q.y !== undefined ? q.y : q.z)).length };
""", {"view": VIEW, "agents": agents, "t1": T1})
        self.assertEqual(out["desks"], 2, "one more desk than managers")
        self.assertTrue(out["aisle"])
        self.assertFalse(out["desk"])
        self.assertFalse(out["shaft"])
        self.assertGreater(out["path"], 0)
        self.assertEqual(out["bad"], 0)


# ---------------------------------------------------------------------------
# F4 between floors
# ---------------------------------------------------------------------------

class TestLift(unittest.TestCase):
    def test_a_talk_to_another_floor_rides_the_lift(self):
        agents = [agent("s:a", "helper", T1, up="gov:" + T1), agent("s:b", "task-manager", T2, up="gov:" + T2)]
        out = sim("""
snap(__payload.view, __payload.agents);
settle(15);
const a = byId('s:a'), b = byId('s:b');
const home = { x: a.x, y: a.y };
apply({ type: 'talk', from: 's:a', to: 's:b' });
const trace = [];
for (let t = 0; t < 150; t += 0.05) {
  update(0.05);
  trace.push([a.at, Math.round(a.x * 100) / 100, Math.round(a.y * 100) / 100, Math.hypot(a.x - b.x, a.y - b.y)]);
}
__out = { trace, home, liftIn: LIFT_IN.concat(LIFT_OUT).map(s => [s.x, s.z]), gap: FLOOR_GAP, t1: __payload.t1, t2: __payload.t2 };
""", {"view": VIEW, "agents": agents, "t1": T1, "t2": T2})
        tr = out["trace"]
        ats = [x[0] for x in tr]
        self.assertIn(T2, ats, "she rides up to blog's floor")
        first = ats.index(T2)
        _, x, y, _ = tr[first]
        lift2 = [(60 + lx, lz) for lx, lz in out["liftIn"]]
        self.assertTrue(min(((x - lx) ** 2 + (y - lz) ** 2) ** 0.5 for lx, lz in lift2) < 0.8,
                        "she comes out of the lift, never pops up elsewhere")
        self.assertTrue(any(d < 1.6 for at, _, _, d in tr[first:] if at == T2), "they meet face to face")
        self.assertEqual(ats[-1], T1, "and she rides back")
        _, x, y, _ = tr[-1]
        self.assertLess(((x - out["home"]["x"]) ** 2 + (y - out["home"]["y"]) ** 2) ** 0.5, 0.8, "back at her desk")
        changes = [i for i in range(1, len(ats)) if ats[i] != ats[i - 1]]
        self.assertEqual(len(changes), 2, "one ride up, one ride down")


# ---------------------------------------------------------------------------
# F5 the 3D part
# ---------------------------------------------------------------------------

class TestScene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = page()
        cls.sim = sim_section()

    def fn(self, name):
        src = function_source(name)
        self.assertIsNotNone(src, name + " is missing")
        return src

    def test_scene_functions(self):
        for name in ("buildFloor", "buildOutside", "enter", "goOutside", "goFloor", "renderLift", "renderFloorSign",
                     "renderPicker", "renderDesignPop", "addPerson", "placeDecor", "select"):
            self.fn(name)

    def test_opens_outside_and_switches_at_once(self):
        self.assertRegex(self.text, r"let view\s*=\s*'outside'")
        self.assertNotIn("camTween", self.fn("goFloor"))

    def test_select_zoom_is_halved(self):
        self.assertRegex(self.fn("select"), r"Math\.min\(cam\.dist,\s*\(fitDist\(\)\s*\+\s*9\)\s*/\s*2\)")

    def test_decor_and_slots(self):
        m = re.search(r"const DECOR\s*=\s*\{(.*?)\n\};", self.text, re.S)
        self.assertIsNotNone(m)
        keys = re.findall(r"^\s{2}(\w+)\s*[:(]", m.group(1), re.M)
        self.assertEqual(sorted(set(keys)), sorted(["robot", "conveyor", "gears", "chart", "plants", "safe",
                                                    "cabinets", "printer", "bookshelf", "clock", "cashier", "goods",
                                                    "menu", "scanner", "lightbox"]))
        self.assertRegex(self.text, r"const SLOTS\s*=\s*\[\{[^\]]*\},\s*\{[^\]]*\},\s*\{[^\]]*\}\]")

    def test_avatars_are_boxes_by_role(self):
        m = re.search(r"const STYLE\s*=\s*\{(.*?)\n\};", self.text, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        for role in ("governor", "'task-manager'", "helper", "designer"):
            self.assertIn(role, body)
        self.assertNotIn("GLTFLoader", self.text)
        self.assertNotIn("SkeletonUtils", self.text)
        self.assertNotRegex(self.text, r"\.glb")
        scripts = re.findall(r'<script src="([^"]+)"', self.text)
        self.assertEqual([s.split("?")[0] for s in scripts], ["assets/vendor/three.min.js"])

    def test_assets_hold_only_three(self):
        found = []
        for dirpath, _, files in os.walk(ASSETS):
            for f in files:
                found.append(os.path.relpath(os.path.join(dirpath, f), ASSETS))
        self.assertEqual(sorted(found), ["vendor/three.min.js"])

    def test_markup(self):
        for i in ("btnPick", "lift", "floorSign", "tags", "pickBg", "dPop", "renoBg"):
            self.assertRegex(self.text, r'id="%s"' % i)
        for i in ("repos", "stage-top", "arr-btn", "arr-bar", "arr-ov", "rail-hid", "cap-hint", "empty-land"):
            self.assertNotRegex(self.text, r'id="%s"' % i)

    def test_endpoints_and_data_only(self):
        for path in ("/api/floors", "/api/design", "/api/designer", "/api/designer/leave"):
            self.assertIn("'" + path + "'", self.text)
        self.assertNotIn("/api/layout", self.text)
        self.assertNotRegex(self.text, r"\beval\(|new Function\(")
        self.assertIn("esc(", self.fn("renderFloorSign"))

    def test_no_island_code(self):
        for name in ("buildLand", "landState", "landsOf", "startShow", "syncSites", "newBuildingRecord", "buildingName"):
            self.assertIsNone(function_source(name), name + " is island code")


if __name__ == "__main__":
    unittest.main()
