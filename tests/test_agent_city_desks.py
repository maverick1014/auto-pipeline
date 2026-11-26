"""city-agents-at-desks (requirements/city-agents-at-desks.md): every live worker and deputy is its own character at a
desk near the session that started it. One test per example of the requirement (EXAMPLES TEST), plus the plate and
the tag (rules 2 and 5). The page runs in the node sim harness of tests/citypage.py.

Contract the page meets (names the tests call):
  isDrawn(c)    -> true for a session; for a subagent only while its parent (c.up, else c.lead) is a live session
                   citizen on c's floor or that floor's area manager ('gov:<terr>'); else false (as today: not drawn)
  plateWord(c)  -> the role word on its name plate, in the page language: a session's roleWord(role); a worker 工人,
                   fast-lane deputy 快车道副手, merge deputy 合并副手, reviewer 审查员, check deputy 检查副手; any other
                   agent type: its type (its label) as it is
  seatSpot(c)   -> where c sits (sessions exactly as before; a drawn agent: the free desk nearest its parent; overflow:
                   the meeting places, then free floor cells near the meeting table, never closer than MIN_GAP)
"""

import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import re  # noqa: E402
from citypage import const_object, run_sim, script_function_source, text_zh, js_value, rule, media_block  # noqa: E402
import agent_city as ac  # noqa: E402


T1, T2 = "aaaa0001", "bbbb0002"
GOV = "gov:" + T1


def view(designs=None):
    return {"v": 2, "repos": [{"id": T1, "name": "shop", "here": True, "n": 0}, {"id": T2, "name": "blog", "here": True, "n": 1}],
            "floors": [T1, T2], "designs": designs or {}, "asked": [T1, T2]}


def agent(aid, role, up="", label=None, task=None, terr=T1, lead=""):
    return {"id": aid, "role": role, "label": label or role, "task": task or aid, "stuck": False, "waiting": False,
            "done": False, "status": "", "tools": {}, "terr": terr, "relay": "", "lead": lead, "office": None, "up": up}


def four_desk_design():
    """A floor design saved before this change: 3 manager desks + 1 helper desk = 4 desks (the server's own default
    layout of that size), with the colours and materials of a demo design."""
    base = next(d for d in ac.demo_world()["designs"].values() if d.get("v") == 2)
    d = copy.deepcopy(base)
    d["layout"] = ac.default_layout(3, 1, ["none", "none", "none"])
    return d


DRIVER_HEAD = r"""
let seed = 20261126; Math.random = () => (seed = (seed * 16807) % 2147483647) / 2147483647; rand = Math.random;
function snap(v, agents){
  apply({ type: 'snapshot', world: v, agents: agents || [], govs: [{ terr: v.floors[0], state: 'busy' }],
          gov: { state: 'busy', terr: v.floors[0] }, asks: [], governors: 1, adding: [], hist: {} });
}
// nobody takes an idle stroll while the scene settles
function settle(sec){ for (let t = 0; t < sec; t += .05) { for (const c of citizens) c.toolAt = simT; update(.05); } }
const r2 = v => +(+v).toFixed(2);
const floorOfC = c => terrOf(c.terr);
const loc = (c, s) => { const t = floorOfC(c); return { x: r2(s.x - t.cx), z: r2(s.y - t.cz) }; };
const seatOfId = id => loc(byId(id), seatSpot(byId(id)));
const posOfId = id => loc(byId(id), byId(id));
const deskSeats = terr => { const i = planInfo(planOf(terr)); return i.tm.concat(i.helper).map(d => ({ x: r2(d.sx), z: r2(d.sz) })); };
const meetSeats = terr => planInfo(planOf(terr)).meet.map(d => ({ x: r2(d.x), z: r2(d.z) }));
// a spot on a blocked cell of the walk grid, unless it is one of the meeting places (the chairs at the table are inside
// the table's blocked pad by design: sessions sit there today, so overflow agents may too)
const blockedAt = (c, p) => { const t = floorOfC(c), g = gridFor(t.id), lx = p.x - t.cx, lz = p.y - t.cz;
  if (planInfo(planOf(t.id)).meet.some(m => Math.hypot(m.x - lx, m.z - lz) < .02)) return false;
  return !!isBlocked(g, cellIx(lx), cellIx(lz)); };
const walking = c => !!(c.path && c.path.length);
const live = () => citizens.filter(c => !c.gone);
"""

REQUIRED = ("officeState", "apply", "update", "citizens", "byId", "seatSpot", "planInfo", "planOf", "terrOf",
            "gridFor", "isBlocked", "cellIx", "isDrawn", "plateWord", "nameOf", "MIN_GAP")


def sim(driver, payload=None, required=REQUIRED):
    return run_sim(DRIVER_HEAD + driver, payload or {}, required=required)


def dist(a, b):
    return ((a["x"] - b["x"]) ** 2 + (a["z"] - b["z"]) ** 2) ** 0.5


def same_spot(a, b, eps=0.02):
    return dist(a, b) <= eps


MIN_GAP = 0.45   # the page's MIN_GAP (tests read it back from the page in test_min_gap_is_the_pages)


class TestTwoWorkers(unittest.TestCase):
    """A session starts two workers: two more characters sit at desks on that repo's floor, each with its own name
    plate; the session's character stays where it was."""

    @classmethod
    def setUpClass(cls):
        cls.out = sim(r"""
snap(__payload.view, [__payload.tm]);
settle(5);
const before = seatOfId('s:t');
apply({ type: 'spawn', id: 'w1', role: 'worker', label: 'worker', task: 'city-x Worker 1: seats', terr: __payload.t1, up: 's:t' });
apply({ type: 'spawn', id: 'w2', role: 'worker', label: 'worker', task: 'city-x Worker 2: plates', terr: __payload.t1, up: 's:t' });
settle(40);
const w = ['w1', 'w2'].map(byId);
__out = { before, after: seatOfId('s:t'), tmPos: posOfId('s:t'),
          seats: { w1: seatOfId('w1'), w2: seatOfId('w2') }, pos: { w1: posOfId('w1'), w2: posOfId('w2') },
          drawn: w.map(isDrawn), drawnTm: isDrawn(byId('s:t')), at: w.map(c => [c.at, !!c.inLift]),
          desks: deskSeats(__payload.t1), tmDesks: planInfo(planOf(__payload.t1)).tm.length,
          words: w.map(plateWord), names: w.map(nameOf), tmWord: plateWord(byId('s:t')) };
""", {"view": view(), "t1": T1, "tm": agent("s:t", "task-manager", up=GOV, label="city-x Task Manager", task="city-x")})

    def test_both_are_drawn(self):
        self.assertEqual(self.out["drawn"], [True, True], "a worker with a live session is a character")
        self.assertTrue(self.out["drawnTm"], "a session is drawn as before")

    def test_they_are_on_the_floor_not_in_the_lift(self):
        self.assertEqual(self.out["at"], [[T1, False], [T1, False]])

    def test_each_sits_at_its_own_desk(self):
        desks = self.out["desks"]
        seats = self.out["seats"]
        for wid in ("w1", "w2"):
            with self.subTest(worker=wid):
                self.assertTrue(any(same_spot(seats[wid], d) for d in desks), "%s sits at a desk: %s" % (wid, seats[wid]))
                self.assertLess(dist(self.out["pos"][wid], seats[wid]), 0.3, "%s got there" % wid)
        self.assertGreaterEqual(dist(seats["w1"], seats["w2"]), MIN_GAP, "two desks, not one")
        for wid in ("w1", "w2"):
            self.assertGreaterEqual(dist(seats[wid], self.out["after"]), MIN_GAP, "not on the manager's chair")

    def test_they_sit_near_the_session(self):
        mgr = self.out["after"]
        free = [d for d in self.out["desks"] if not same_spot(d, mgr)]
        nearest = sorted(free, key=lambda d: dist(d, mgr))[:2]
        got = [self.out["seats"]["w1"], self.out["seats"]["w2"]]
        for s in got:
            self.assertTrue(any(same_spot(s, d) for d in nearest), "the two free desks nearest the manager: %s, got %s" % (nearest, got))

    def test_the_session_stays_where_it_was(self):
        self.assertTrue(same_spot(self.out["before"], self.out["after"]), (self.out["before"], self.out["after"]))
        self.assertLess(dist(self.out["tmPos"], self.out["after"]), 0.3)

    def test_the_default_floor_has_a_desk_for_each_agent(self):
        self.assertEqual(self.out["tmDesks"], 4, "no saved design: managers + agents + 1 manager desks (at most 9)")

    def test_each_has_its_own_name_plate(self):
        self.assertEqual(self.out["words"], ["工人", "工人"])
        n1, n2 = self.out["names"]
        self.assertNotEqual(n1, n2)
        self.assertIn("seats", n1)
        self.assertIn("plates", n2)
        self.assertEqual(self.out["tmWord"], "经理", "a session's plate word stays roleWord")


class TestOneWorkerStops(unittest.TestCase):
    """One worker stops: its character leaves, the other stays."""

    def test_it_leaves_the_other_stays(self):
        out = sim(r"""
snap(__payload.view, __payload.agents);
settle(40);
const drawnBefore = ['w1', 'w2'].map(id => isDrawn(byId(id)));
apply({ type: 'done', id: 'w1' });
settle(60);
const w2 = byId('w2');
__out = { drawnBefore, w1: citizens.filter(c => c.id === 'w1' && !c.gone).length, w2drawn: !!w2 && isDrawn(w2),
          w2off: w2 ? dist2(posOfId('w2'), seatOfId('w2')) : -1, w2state: w2 ? w2.state : '' };
function dist2(a, b){ return Math.hypot(a.x - b.x, a.z - b.z); }
""", {"view": view(), "agents": [agent("s:t", "task-manager", up=GOV), agent("w1", "worker", up="s:t", task="city-x Worker 1: a"),
                                 agent("w2", "worker", up="s:t", task="city-x Worker 2: b")]})
        self.assertEqual(out["drawnBefore"], [True, True])
        self.assertEqual(out["w1"], 0, "a stopped worker walks out (it never rests in the pantry)")
        self.assertTrue(out["w2drawn"], "the other one stays")
        self.assertLess(out["w2off"], 0.3, "at its desk, state " + out["w2state"])


class TestSessionEnds(unittest.TestCase):
    """The session ends while a worker runs: both leave (the server sends done + leave for the agents, then the
    session)."""

    def test_both_leave(self):
        out = sim(r"""
snap(__payload.view, __payload.agents);
settle(30);
const drawnBefore = isDrawn(byId('w1'));
for (const id of ['w1', 's:t']) { apply({ type: 'done', id }); apply({ type: 'leave', id }); }
settle(120);
__out = { drawnBefore, left: live().map(c => c.id) };
""", {"view": view(), "agents": [agent("s:t", "task-manager", up=GOV), agent("w1", "worker", up="s:t")]})
        self.assertTrue(out["drawnBefore"])
        self.assertEqual(out["left"], [], "both walked out")


class TestReviewerAndMergeDeputy(unittest.TestCase):
    """A reviewer and a merge deputy at the same time: two characters, each named by its role. The main manager (the
    area manager, 'gov:<terr>') starts both; the server sends a reviewer as role "other" with its type as label."""

    def test_two_characters_named_by_role(self):
        out = sim(r"""
snap(__payload.view, [__payload.tm]);
settle(3);
apply({ type: 'spawn', id: 'r1', role: 'other', label: 'reviewer', task: 'city-x PR REVIEW', terr: __payload.t1, up: __payload.gov });
apply({ type: 'spawn', id: 'm1', role: 'merge-deputy', label: 'merge-deputy', task: 'city-x merge', terr: __payload.t1, up: __payload.gov });
settle(40);
__out = { drawn: ['r1', 'm1'].map(id => isDrawn(byId(id))), words: ['r1', 'm1'].map(id => plateWord(byId(id))),
          seats: ['r1', 'm1'].map(seatOfId), desks: deskSeats(__payload.t1) };
""", {"view": view(), "t1": T1, "gov": GOV, "tm": agent("s:t", "task-manager", up=GOV)})
        self.assertEqual(out["drawn"], [True, True], "the area manager's own agents are drawn too")
        self.assertEqual(out["words"], ["审查员", "合并副手"])
        r, m = out["seats"]
        self.assertGreaterEqual(dist(r, m), MIN_GAP)
        for s in (r, m):
            self.assertTrue(any(same_spot(s, d) for d in out["desks"]), "at a desk: %s" % s)

    def test_plate_words(self):
        out = sim(r"""
const mk = (role, label) => ({ role, label, task: 't', terr: '', up: '', lead: '' });
__out = [mk('worker', 'worker'), mk('fast-lane-deputy', 'fast-lane-deputy'), mk('merge-deputy', 'merge-deputy'),
         mk('other', 'reviewer'), mk('other', 'check-deputy'), mk('other', 'Explore'), mk('task-manager', 'x Task Manager'),
         mk('helper', 'h')].map(plateWord);
""", {}, required=("plateWord",))
        self.assertEqual(out, ["工人", "快车道副手", "合并副手", "审查员", "检查副手", "Explore", "经理", "助理"])

    def test_plate_words_in_english(self):
        lit = const_object("TEXT")
        self.assertIsNotNone(lit)
        en = js_value(lit)["en"]
        zh = text_zh()
        for key, word_en, word_zh in (("role.reviewer", "Reviewer", "审查员"), ("role.check-deputy", "Check deputy", "检查副手"),
                                      ("role.worker", "Worker", "工人"), ("role.fast-lane-deputy", "Fast-lane deputy", "快车道副手"),
                                      ("role.merge-deputy", "Merge deputy", "合并副手")):
            with self.subTest(key=key):
                self.assertEqual(en.get(key), word_en)
                self.assertEqual(zh.get(key), word_zh)


class TestOverflow(unittest.TestCase):
    """A floor with 4 desks and 6 characters: the overflow rule of today places all 6; nobody overlaps a wall or
    another character."""

    @classmethod
    def setUpClass(cls):
        design = four_desk_design()
        agents = [agent("s:t", "task-manager", up=GOV)] + [agent("w%d" % i, "worker", up="s:t", task="city-x Worker %d: s" % i)
                                                         for i in range(1, 6)]
        cls.out = sim(r"""
snap(__payload.view, __payload.agents);
settle(60);
const ids = live().map(c => c.id);
__out = { ids, drawn: ids.map(id => isDrawn(byId(id))), seats: ids.map(seatOfId), pos: ids.map(posOfId),
          walking: ids.map(id => walking(byId(id))), seatBlocked: ids.map(id => blockedAt(byId(id), seatSpot(byId(id)))),
          posBlocked: ids.map(id => blockedAt(byId(id), byId(id))), desks: deskSeats(__payload.t1), meet: meetSeats(__payload.t1),
          gap: MIN_GAP };
""", {"view": view({T1: design}), "t1": T1, "agents": agents})

    def test_min_gap_is_the_pages(self):
        self.assertEqual(self.out["gap"], MIN_GAP)

    def test_all_six_are_placed(self):
        self.assertEqual(len(self.out["ids"]), 6)
        self.assertEqual(self.out["drawn"], [True] * 6)
        self.assertEqual(len(self.out["desks"]), 4)

    def test_four_at_desks_two_at_the_meeting_places(self):
        seats, desks, meet = self.out["seats"], self.out["desks"], self.out["meet"]
        at_desk = [s for s in seats if any(same_spot(s, d) for d in desks)]
        at_meet = [s for s in seats if any(same_spot(s, m) for m in meet)]
        self.assertEqual((len(at_desk), len(at_meet)), (4, 2), seats)
        # today's overflow order: the meeting places from the first (the 4 chairs, then the standing spots)
        self.assertTrue(all(any(same_spot(s, m) for s in at_meet) for m in meet[:2]),
                        "the first two meeting places, as for sessions today: %s of %s" % (at_meet, meet))

    def test_no_two_seats_overlap(self):
        seats = self.out["seats"]
        for i in range(len(seats)):
            for j in range(i + 1, len(seats)):
                self.assertGreaterEqual(dist(seats[i], seats[j]), MIN_GAP - 1e-6, (self.out["ids"][i], self.out["ids"][j]))

    def test_nobody_on_a_wall(self):
        self.assertEqual(self.out["seatBlocked"], [False] * 6)
        self.assertEqual(self.out["posBlocked"], [False] * 6)

    def test_nobody_stands_on_another(self):
        pos, walk = self.out["pos"], self.out["walking"]
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                if walk[i] or walk[j]:
                    continue
                self.assertGreaterEqual(dist(pos[i], pos[j]), MIN_GAP - 0.02, (self.out["ids"][i], self.out["ids"][j]))


class TestManyAgents(unittest.TestCase):
    """Past the 6 meeting places (today they stack, index modulo 6): more agents still get spots of their own."""

    def test_fourteen_on_four_desks(self):
        agents = [agent("s:t", "task-manager", up=GOV)] + [agent("w%d" % i, "worker", up="s:t") for i in range(1, 14)]
        out = sim(r"""
snap(__payload.view, __payload.agents);
settle(5);
const ids = live().map(c => c.id);
__out = { ids, seats: ids.map(seatOfId), blocked: ids.map(id => blockedAt(byId(id), seatSpot(byId(id)))) };
""", {"view": view({T1: four_desk_design()}), "agents": agents})
        self.assertEqual(len(out["ids"]), 14)
        self.assertEqual(out["blocked"], [False] * 14)
        seats = out["seats"]
        for i in range(len(seats)):
            for j in range(i + 1, len(seats)):
                self.assertGreaterEqual(dist(seats[i], seats[j]), MIN_GAP - 1e-6, (out["ids"][i], out["ids"][j], seats[i]))


class TestSavedDesign(unittest.TestCase):
    """A custom floor design saved before this change loads with no problem line."""

    def test_server_accepts_it(self):
        self.assertEqual(ac.check_design(four_desk_design()), [])
        for d in ac.demo_world()["designs"].values():
            if d.get("v") == 2:
                self.assertEqual(ac.check_design(d), [])

    def test_page_uses_it_as_saved(self):
        design = four_desk_design()
        agents = [agent("s:t", "task-manager", up=GOV), agent("w1", "worker", up="s:t"), agent("w2", "worker", up="s:t")]
        out = sim(r"""
snap(__payload.view, __payload.agents);
settle(10);
const p = planOf(__payload.t1);
__out = { n: p.items.length, kinds: p.items.map(it => it.k).sort(), ok: checkPlan(p).ok,
          bad: logEntries.map(e => String(e.text)).filter(s => s.includes(i18n('ed.badLayout'))) };
""", {"view": view({T1: design}), "t1": T1, "agents": agents},
            required=REQUIRED + ("checkPlan", "logEntries"))
        self.assertEqual(out["n"], len(design["layout"]["items"]), "a saved design never grows desks")
        self.assertEqual(out["kinds"], sorted(it["k"] for it in design["layout"]["items"]))
        self.assertTrue(out["ok"])
        self.assertEqual(out["bad"], [])


class TestDemo(unittest.TestCase):
    """The demo floor shows at least one manager with two agents at desks."""

    def test_demo_has_a_manager_with_two_agents_at_desks(self):
        world = const_object("DEMO_WORLD")
        seed = script_function_source("seedDemo")
        self.assertIsNotNone(world, "const DEMO_WORLD")
        self.assertIsNotNone(seed, "function seedDemo")
        out = sim("var DEMO_WORLD = " + world + ";\n" + seed + r"""
seedDemo();
settle(40);
const rows = [];
for (const m of live().filter(c => c.role === 'task-manager')) {
  const kids = live().filter(c => (c.up || c.lead) === m.id && isDrawn(c));
  const desks = deskSeats(m.terr);
  const atDesk = kids.filter(k => { const s = seatOfId(k.id); return desks.some(d => Math.hypot(d.x - s.x, d.z - s.z) < .02); });
  rows.push([m.id, kids.length, atDesk.length]);
}
__out = rows;
""", {})
        self.assertTrue(any(n >= 2 and d >= 2 for _, n, d in out), "a demo manager with two agents at desks: %s" % out)


class TestDemoKeepsItsAgents(unittest.TestCase):
    """#demo keeps showing workers and deputies at desks: its fake agents finish and leave like real ones, so the demo
    spawner (spawner -> demoCrew) gives each demo manager up to two live agents again, one per call."""

    def test_each_manager_gets_two_agents_back(self):
        out = sim(r"""
snap(__payload.view, [__payload.a, __payload.b, __payload.h]);
settle(2);
const crew = id => live().filter(c => (c.up || c.lead) === id && !c.doneFlag && isDrawn(c));
for (let i = 0; i < 6; i++) { demoCrew(); settle(.5); }
const first = ['s:a', 's:b'].map(id => crew(id).length);
const roles = [...new Set(live().filter(c => isSub(c)).map(c => c.role))].sort();
const one = crew('s:a')[0].id;
apply({ type: 'done', id: one });
settle(40);
const afterLeave = crew('s:a').length;
demoCrew(); settle(.5);
__out = { first, roles, afterLeave, back: crew('s:a').length, helperCrew: crew('s:h').length };
""", {"view": view(), "a": agent("s:a", "task-manager", up=GOV), "b": agent("s:b", "task-manager", up=GOV),
          "h": agent("s:h", "helper", up=GOV)}, required=REQUIRED + ("demoCrew", "isSub"))
        self.assertEqual(out["first"], [2, 2], "two agents for each manager, no more")
        self.assertTrue(set(out["roles"]) <= {"worker", "fast-lane-deputy", "merge-deputy"}, out["roles"])
        self.assertEqual(out["afterLeave"], 1, "a finished one walked out")
        self.assertEqual(out["back"], 2, "the next call brings the crew back to two")
        self.assertEqual(out["helperCrew"], 0, "only managers get a crew")

    def test_the_spawner_calls_it(self):
        self.assertIn("demoCrew(", script_function_source("spawner") or "")


class TestUnknownSession(unittest.TestCase):
    """A subagent event for a session the city does not know: as today (no character, no error)."""

    def test_server_side_as_today(self):
        r = ac.Reducer()
        line = {"ev": "SubagentStart", "sid": "nobody", "aid": "a1", "at": "auto-pipeline:worker", "repo": "/work/shop/.git"}
        events = r.feed(line, 1000.0)
        self.assertEqual([e["type"] for e in events], ["spawn"], "the server keeps it as before")
        self.assertEqual(ac._spawn_up(r, T1, line), "", "no parent: up is empty")

    def test_page_draws_no_character(self):
        out = sim(r"""
snap(__payload.view, __payload.agents);
settle(10);
__out = ['w8', 'w9'].map(id => byId(id) ? isDrawn(byId(id)) : 'missing');
""", {"view": view(), "agents": [agent("w9", "worker", up=""), agent("w8", "worker", up="s:nobody")]})
        self.assertEqual(out, [False, False])


class TestTag(unittest.TestCase):
    """Where the agents are shown as characters, the tag no longer stands in for them; the rail's head count stays."""

    def test_head_tag_has_no_agent_count(self):
        for name in ("syncFigs", "pinOv"):
            with self.subTest(fn=name):
                src = script_function_source(name) or ""
                self.assertTrue(src, name)
                self.assertNotIn("subBadge(", src, name + " no longer puts 'worker ×2' on the head tag")

    def test_head_tag_uses_the_plate_word(self):
        self.assertIn("plateWord(", script_function_source("pinOv") or "")

    def test_rail_row_keeps_the_count(self):
        src = script_function_source("railGroups") or ""
        self.assertIn("subBadge(", src, "the rail row's head count stays")

    def test_toolbar_options_no_longer_say_not_drawn(self):
        lit = const_object("TEXT")
        texts = js_value(lit)
        for key in ("opt.worker", "opt.fastLaneDeputy", "opt.mergeDeputy"):
            with self.subTest(key=key):
                self.assertNotIn("不画出来", texts["zh"].get(key, ""))
                self.assertNotIn("not drawn", texts["en"].get(key, ""))
                self.assertTrue(texts["zh"].get(key) and texts["en"].get(key))



# -- fix round (TELL 7fba8777, the UI CHECK on the laptop) ---------------------------------------------------------
#
# plateLayout(items, opts) -> one mode per item, in input order: 'full' | 'chip' | 'none'. An item is a name plate on
# screen: { x, y (its head: the plate's bottom centre, px), w (full plate width), wChip (the role chip alone), h, pri (the
# selected person 3, the hovered 2, a session or area manager 1, an agent 0), wd, hd (its doing line, optional) }. Order:
# higher pri first; equal pri: the one lower on screen (larger y, nearer the viewer) first, then input order.
# Fix round 2 (main manager, UI CHECK 2): every person keeps at least a chip when there is room; a plate is hidden only
# when even its chip would truly overlap one laid out before it; the hovered or selected person always shows in full.
#   1. pri >= 2: 'full' first; a panel (opts.blocks) in the way moves it the least way out (down, left or right).
#   2. every other one: its chip over its head, else nudged left or right by 0.6 chip widths, else one row up (h + 2);
#      the first spot that meets no panel and no box laid out before; none fits -> 'none'.
#   3. in order, a chip becomes 'full' when its full box (with its doing line) over its head meets no panel and no other
#      box laid out. With opts.bounds each box is first kept inside the bounds by its own width (a chip stays over its
#      head); a head outside the bounds is 'none' and not moved. Each item's x, y end at its final box's bottom centre.

def boxes_of(items, modes):
    out = []
    for it, m in zip(items, modes):
        if m == "none":
            continue
        w = it["w"] if m == "full" else it["wChip"]
        out.append((it["x"] - w / 2, it["y"] - it["h"], it["x"] + w / 2, it["y"]))
    return out


def overlapping(boxes, eps=0.5):
    bad = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if min(a[2], b[2]) - max(a[0], b[0]) > eps and min(a[3], b[3]) - max(a[1], b[1]) > eps:
                bad.append((i, j))
    return bad


def layout(items):
    return sim("__out = plateLayout(__payload.items);", {"items": items}, required=("plateLayout",))


class TestPlateLayout(unittest.TestCase):
    """Fix 1: no two name plates overlap on screen; the selected (then hovered) one keeps its full plate."""

    def test_a_tight_cluster_never_overlaps(self):
        import random
        rnd = random.Random(7)
        items = [{"x": 600 + rnd.uniform(-60, 60), "y": 300 + rnd.uniform(-30, 30), "w": rnd.uniform(100, 180),
                  "wChip": rnd.choice([32, 52, 62]), "h": 22, "pri": 0} for _ in range(30)]
        first = max(range(30), key=lambda i: (items[i]["pri"], items[i]["y"], -i))   # from the heads, before any move
        out = sim("const items = __payload.items; __out = { modes: plateLayout(items), items };", {"items": items},
                  required=("plateLayout",))
        modes = out["modes"]
        self.assertEqual(len(modes), 30)
        self.assertTrue(set(modes) <= {"full", "chip", "none"}, modes)
        self.assertEqual(overlapping(boxes_of(out["items"], modes)), [], "the boxes where they end (a chip may be nudged)")
        self.assertNotEqual(modes[first], "none", "the first in order always keeps at least its chip")

    def test_the_selected_one_is_full_in_a_pile(self):
        items = [{"x": 500, "y": 400, "w": 150, "wChip": 32, "h": 22, "pri": 0} for _ in range(8)]
        items[5]["pri"] = 2
        out = sim("const items = __payload.items; __out = { modes: plateLayout(items), items };", {"items": items},
                  required=("plateLayout",))
        self.assertEqual(out["modes"][5], "full")
        self.assertEqual(overlapping(boxes_of(out["items"], out["modes"])), [], "a pile: nothing overlaps the selected one")
        self.assertGreaterEqual(out["modes"].count("none"), 5, "a true pile hides the rest")

    def test_apart_all_full(self):
        items = [{"x": 100 + 300 * i, "y": 300, "w": 180, "wChip": 32, "h": 22, "pri": 0} for i in range(5)]
        self.assertEqual(layout(items), ["full"] * 5)

    def test_chip_when_only_the_chip_fits(self):
        items = [{"x": 100, "y": 100, "w": 160, "wChip": 32, "h": 22, "pri": 0},
                 {"x": 210, "y": 100, "w": 160, "wChip": 32, "h": 22, "pri": 0}]
        self.assertEqual(layout(items), ["full", "chip"])

    def test_nearer_first_on_a_tie(self):
        items = [{"x": 100, "y": 100, "w": 160, "wChip": 32, "h": 22, "pri": 0},
                 {"x": 110, "y": 110, "w": 160, "wChip": 32, "h": 22, "pri": 0}]
        modes = layout(items)
        self.assertEqual(modes[1], "full", "lower on screen = nearer the viewer")
        self.assertNotEqual(modes[0], "full")

    def test_the_figure_pass_uses_it(self):
        src = script_function_source("syncFigs") or ""
        for bit in ("plateLayout(", "platePri(", "bounds", "blocks"):
            with self.subTest(bit=bit):
                self.assertIn(bit, src, "syncFigs lays the plates out once per frame: priorities, the stage's bounds, the panels")
        pri = script_function_source("platePri") or ""
        for bit in ("selected", "hovered"):
            with self.subTest(bit=bit):
                self.assertIn(bit, pri)


class TestPlateBoundsAndPanels(unittest.TestCase):
    """Fix round 2 (my headless check at 390x844): plates ran off the screen edge and over the page's panels.
    plateLayout(items, opts): opts.bounds {l, t, r, b} -- before the layout each item is moved (its x and y changed in
    place) the least that keeps its full box inside the bounds (x into [l + w/2, r - w/2], y into [t + h, b]); opts.blocks
    [[l, t, r, b], ...] -- boxes already taken (the panels over the floor view): no shown plate meets one, the first item
    included. Without opts it works as before."""

    def run_layout(self, items, opts):
        return sim("const items = __payload.items; __out = { modes: plateLayout(items, __payload.opts), items };",
                   {"items": items, "opts": opts}, required=("plateLayout",))

    def test_plates_move_inside_the_bounds(self):
        items = [{"x": 10, "y": 300, "w": 160, "wChip": 32, "h": 22, "pri": 0},
                 {"x": 385, "y": 500, "w": 160, "wChip": 32, "h": 22, "pri": 0},
                 {"x": 200, "y": 8, "w": 160, "wChip": 32, "h": 22, "pri": 0}]
        out = self.run_layout(items, {"bounds": {"l": 0, "t": 0, "r": 390, "b": 844}, "blocks": []})
        self.assertEqual(out["modes"], ["full"] * 3)
        moved = out["items"]
        self.assertEqual([round(i["x"]) for i in moved], [80, 310, 200], "moved the least: half a plate from the edge")
        self.assertEqual(round(moved[2]["y"]), 22, "down to its own height")
        for b in boxes_of(moved, out["modes"]):
            self.assertTrue(b[0] >= -0.01 and b[1] >= -0.01 and b[2] <= 390.01 and b[3] <= 844.01, b)

    def test_panels_are_never_covered(self):
        block = [100, 280, 300, 320]
        items = [{"x": 200, "y": 330, "w": 160, "wChip": 32, "h": 22, "pri": 0},
                 {"x": 200, "y": 420, "w": 160, "wChip": 32, "h": 22, "pri": 0},
                 {"x": 150, "y": 300, "w": 160, "wChip": 32, "h": 22, "pri": 3}]
        out = self.run_layout(items, {"bounds": {"l": 0, "t": 0, "r": 390, "b": 844}, "blocks": [block]})
        self.assertEqual(out["modes"][1], "full", "a plate clear of the panel")
        self.assertEqual(out["modes"][0], "none", "every spot of its chip meets the panel")
        self.assertEqual(out["modes"][2], "full", "the selected one always shows in full (fix round 2) ...")
        self.assertEqual(round(out["items"][2]["y"]), 342, "... moved straight down below the panel, the least move")
        self.assertEqual(overlapping(boxes_of(out["items"], out["modes"]) + [tuple(block)]), [], "no plate meets the panel")

    def test_without_opts_as_before(self):
        items = [{"x": 10, "y": 300, "w": 160, "wChip": 32, "h": 22, "pri": 0}]
        out = self.run_layout(items, None)
        self.assertEqual(out["modes"], ["full"])
        self.assertEqual(out["items"][0]["x"], 10, "no bounds: nothing moves")


class TestPlatePriority(unittest.TestCase):
    """Fix round 2: at phone width the manager's own plate lost to its agents' plates. platePri(f) for a figure f
    ({ c } a person, { gv: { terr } } an area manager): the selected one 3, the hovered one 2, a session or an area
    manager 1, an agent 0."""

    def test_priorities(self):
        out = sim(r"""
snap(__payload.view, __payload.agents);
settle(2);
const P = id => platePri({ c: byId(id) }), G = () => platePri({ gv: { terr: __payload.t1 } });
const plain = { tm: P('s:t'), w1: P('w1'), w2: P('w2'), gov: G() };
selected = { t: 'c', id: 'w1' }; hovered = { t: 'c', id: 'w2' };
const picked = { w1: P('w1'), w2: P('w2'), tm: P('s:t') };
selected = { t: 'gov', terr: __payload.t1 }; hovered = null;
__out = { plain, picked, govSel: G() };
""", {"view": view(), "t1": T1, "agents": [agent("s:t", "task-manager", up=GOV), agent("w1", "worker", up="s:t"),
                                         agent("w2", "worker", up="s:t")]}, required=REQUIRED + ("platePri",))
        self.assertEqual(out["plain"], {"tm": 1, "w1": 0, "w2": 0, "gov": 1})
        self.assertEqual(out["picked"], {"w1": 3, "w2": 2, "tm": 1})
        self.assertEqual(out["govSel"], 3)


class TestPlateOffScreen(unittest.TestCase):
    """Fix round (my zoom check): with opts.bounds, an item whose own point (x, y: the head) lies outside the bounds is a
    person off screen: 'none', and it is not moved (before, its plate was clamped to the screen edge)."""

    def test_off_screen_heads_get_no_plate(self):
        items = [{"x": -50, "y": 300, "w": 160, "wChip": 32, "h": 22, "pri": 0},
                 {"x": -9999, "y": -9999, "w": 160, "wChip": 32, "h": 22, "pri": 3},
                 {"x": 200, "y": 900, "w": 160, "wChip": 32, "h": 22, "pri": 0},
                 {"x": 10, "y": 300, "w": 160, "wChip": 32, "h": 22, "pri": 0}]
        out = sim("const items = __payload.items; __out = { modes: plateLayout(items, { bounds: { l: 0, t: 0, r: 390, b: 844 }, blocks: [] }), items };",
                  {"items": items}, required=("plateLayout",))
        self.assertEqual(out["modes"], ["none", "none", "none", "full"])
        self.assertEqual([i["x"] for i in out["items"][:3]], [-50, -9999, 200], "not moved")
        self.assertEqual(round(out["items"][3]["x"]), 80, "a head on screen near the edge: its plate moves in")


class TestDoingLineFollowsThePlate(unittest.TestCase):
    """Fix round (my zoom check: zoomed in, the 'what it does' lines of people whose plates were hidden piled up at the
    top right and ran under the lift panel). An item may carry wd, hd: the doing line above its plate (width, height).
    A 'full' item's box is then [x - max(w, wd)/2, y - h - hd, x + max(w, wd)/2, y]; a 'chip' item shows no doing line
    (its box is the chip alone); syncFigs shows the doing line only over a 'full' plate, at the plate's moved spot."""

    def test_the_doing_line_is_part_of_the_full_box(self):
        items = [{"x": 300, "y": 300, "w": 120, "wChip": 32, "h": 22, "pri": 2, "wd": 200, "hd": 20},
                 {"x": 300, "y": 270, "w": 120, "wChip": 32, "h": 22, "pri": 0, "wd": 0, "hd": 0}]
        out = sim("const items = __payload.items; __out = { modes: plateLayout(items, { bounds: { l: 0, t: 0, r: 1440, b: 713 }, blocks: [] }), items };",
                  {"items": items}, required=("plateLayout",))
        self.assertEqual(out["modes"], ["full", "chip"])
        self.assertLessEqual(out["items"][1]["y"], 258.01, "its chip moved up, clear of the hovered one's doing line")

    def test_a_doing_line_wider_than_its_plate(self):
        items = [{"x": 300, "y": 300, "w": 120, "wChip": 32, "h": 22, "pri": 0, "wd": 300, "hd": 20},
                 {"x": 520, "y": 280, "w": 120, "wChip": 32, "h": 22, "pri": 0, "wd": 0, "hd": 0}]
        out = sim("__out = plateLayout(__payload.items, { bounds: { l: 0, t: 0, r: 1440, b: 713 }, blocks: [] });",
                  {"items": items}, required=("plateLayout",))
        self.assertEqual(out, ["full", "full"], "apart: both full (the doing line ends at 450)")
        items[1]["x"] = 480
        out = sim("__out = plateLayout(__payload.items, { bounds: { l: 0, t: 0, r: 1440, b: 713 }, blocks: [] });",
                  {"items": items}, required=("plateLayout",))
        self.assertEqual(out[0], "full")
        self.assertNotEqual(out[1], "full", "its full box [420, 540] meets the doing line [150, 450]")

    def test_the_figure_pass_places_the_doing_line(self):
        src = script_function_source("syncFigs") or ""
        for bit in ("doing", "wd", "hd"):
            with self.subTest(bit=bit):
                self.assertIn(bit, src, "syncFigs lays out the doing line with its plate")


TEAM_AGENTS = [agent("s:t", "task-manager", up=GOV, label="task-manager", task="city-agents-at-desks"),
               agent("w1", "worker", up="s:t", task="city-agents-at-desks Worker 1: seats"),
               agent("w2", "worker", up="s:t", task="city-agents-at-desks Worker 2: plates"),
               agent("rv", "other", up="s:t", label="reviewer", task="city-agents-at-desks PR REVIEW"),
               agent("md", "merge-deputy", up="s:t", task="city-agents-at-desks merge")]
# the panels over the floor view as the page lays them out (stage coordinates), measured headless on the live page:
# viewport 500x713 -> stage 468x583; viewport 390x844 -> stage 358x714 (floor sign, rail tab, badge, lift, 4 camera buttons)
PANELS = {468: (583, [[42, 12, 268, 54], [0, 12, 32, 91], [12, 545, 112, 571], [392, 12, 456, 186], [286, 533, 324, 571],
                      [330, 533, 368, 571], [374, 533, 412, 571], [418, 533, 456, 571]]),
          358: (714, [[42, 12, 268, 54], [0, 12, 32, 91], [12, 676, 112, 702], [282, 12, 346, 186], [176, 664, 214, 702],
                      [220, 664, 258, 702], [264, 664, 302, 702], [308, 664, 346, 702]])}


class TestTeamFloorEveryoneShows(unittest.TestCase):
    """Fix round 2, item 1 (UI CHECK 2: the reviewer had no plate at about 500 px and on the phone page). The click path's
    team floor (a manager, two workers, a reviewer, a merge deputy), projected as the page's default view on the stage of
    a 500x713 and a 390x844 window with the page's panels: every one shows a plate or a chip, none hidden, nothing
    overlaps or meets a panel; hovering any one of them shows its full plate."""

    def test_five_plates_or_chips_and_hover_gives_full(self):
        out = sim(PROJECT_JS + r"""
snap(__payload.view, __payload.agents);
settle(40);
const ppl = live().filter(c => isDrawn(c) && c.at === c.terr);
const res = {};
for (const [W, H, panels] of __payload.sizes) {
  const base = plateItems(W, H).map((o, i) => Object.assign(o, { pri: platePri({ c: ppl[i] }) }));
  const opts = { bounds: { l: 4, t: 4, r: W - 4, b: H - 4 }, blocks: panels };
  const items = base.map(o => Object.assign({}, o)), modes = plateLayout(items, opts);
  const hov = base.map((_, i) => { const its = base.map((o, j) => Object.assign({}, o, { pri: j === i ? 2 : o.pri }));
    const m = plateLayout(its, opts); return { mode: m[i], items: its, modes: m }; });
  res[W] = { items, modes, hov, panels };
}
__out = res;
""", {"view": view(), "agents": TEAM_AGENTS, "sizes": [[w, PANELS[w][0], PANELS[w][1]] for w in (468, 358)]},
            required=REQUIRED + ("plateLayout", "platePri", "FOV"))
        for w in ("468", "358"):
            with self.subTest(stage=w):
                r = out[w]
                self.assertEqual(len(r["modes"]), 5)
                self.assertEqual(r["modes"].count("none"), 0, "every one keeps a plate or a chip: %s" % r["modes"])
                bx = boxes_of(r["items"], r["modes"])
                self.assertEqual(overlapping(bx), [])
                self.assertEqual([b for b in bx for q in r["panels"] if overlapping([b, tuple(q)])], [], "no panel covered")
                for i, h in enumerate(r["hov"]):
                    self.assertEqual(h["mode"], "full", "hovering person %d shows its full plate" % i)
                    self.assertEqual(overlapping(boxes_of(h["items"], h["modes"])), [])


class TestFloorSignCount(unittest.TestCase):
    """Fix round 2, item 3 (UI CHECK 2: the floor tag was cut at narrow widths, '还没装…', and below 720 px the count was
    not shown at all). The count '<n> 人' has its own element (.fpc) that never shrinks; the note (.frs: the design or
    renovating text) gives way first; the floor name may shrink too. The live check at 390 and 500 is in the report."""

    def test_the_count_has_its_own_element(self):
        src = script_function_source("renderFloorSign") or ""
        self.assertIn("fpc", src)
        self.assertIn("office.people", src)

    def test_the_count_never_shrinks(self):
        decl = re.sub(r"\s+", "", rule(".floorsign .fpc"))
        self.assertIn("flex-shrink:0", decl)
        self.assertIn("white-space:nowrap", decl)

    def test_the_note_and_the_name_give_way(self):
        note = re.sub(r"\s+", "", rule(".floorsign .frs"))
        for bit in ("min-width:0", "overflow:hidden", "text-overflow:ellipsis", "white-space:nowrap"):
            with self.subTest(bit=bit):
                self.assertIn(bit, note)
        self.assertIn("min-width:0", re.sub(r"\s+", "", rule(".floorsign .frn")))

    def test_the_note_keeps_its_separator(self):
        # the look before this round: '还没装修 · 5 人'; the ' ·' goes with the note, so it leaves with the note on a phone
        src = (script_function_source("renderFloorSign") or "").replace("function renderFloorSign(", "function signCopy(", 1)
        self.assertIn("$('#floorSign')", src)
        src = src.replace("$('#floorSign')", "__el")
        out = sim("var __el = { innerHTML: '', title: '' };\n" + src + r"""
officeState(__payload.view); view = 'inside'; cur = __payload.t1;
signCopy();
__out = __el.innerHTML;
""", {"view": view(), "t1": T1}, required=("renderFloorSign", "officeState"))
        m = re.search(r'<span class="frs">([^<]*)</span>', out)
        self.assertTrue(m, out)
        self.assertTrue(m.group(1).endswith(" ·"), "the note ends with its separator: %r" % m.group(1))
        self.assertRegex(out, r'<span class="fpc">\d+ ', "the count stays in its own element")

    def test_narrow_screens_keep_the_count(self):
        m = re.sub(r"\s+", "", media_block("(max-width:720px)"))
        self.assertNotRegex(m, r"\.floorsign\.fpc\{[^}]*display:none")
        self.assertNotIn(".floorsign .fpc{display:none", media_block("(max-width:720px)"))


class TestPlateNameShort(unittest.TestCase):
    """Fix round 2, item 2 (main manager's decision): an agent's plate drops the leading task name when its description
    starts with the task's own name (fix round 3: the task of a live session of its floor -- its worktree folder, c.task,
    or the '<task>' of a '<task> Task Manager' label -- followed by more text): '审查员 · PR REVIEW',
    '合并副手 · merge', '工人 · Worker 1 · seats'. plateName(c, true), the hovered or selected plate, keeps the whole
    description; the tag's title keeps nameOf."""

    def test_short_and_long_forms(self):
        agents = [agent("s:t", "task-manager", up=GOV, label="city-x Task Manager", task="city-x"),
                  agent("s:u", "task-manager", up=GOV, label="task-manager", task="city-agents-at-desks"),
                  agent("s:v", "task-manager", up=GOV, label="city-y Task Manager", task="some-folder"),
                  agent("rv", "other", up=GOV, label="reviewer", task="city-agents-at-desks PR REVIEW"),
                  agent("md", "merge-deputy", up=GOV, label="merge-deputy", task="city-agents-at-desks merge"),
                  agent("w1", "worker", up="s:t", label="worker", task="city-agents-at-desks Worker 1: seats"),
                  agent("e1", "other", up="s:t", label="Explore", task="find the hook"),
                  agent("p1", "other", up=GOV, label="reviewer", task="PR REVIEW of the plates"),
                  agent("o1", "worker", up="s:t", label="worker", task="city-x"),
                  agent("c1", "other", up=GOV, label="check-deputy", task="city-y UI CHECK"),
                  agent("c2", "other", up=GOV, label="check-deputy", task="city-y UI CHECK"),
                  agent("r2", "worker", up="s:t", label="worker", task="re-run the tests"),
                  agent("x1", "merge-deputy", up=GOV, label="merge-deputy", task="other-task merge")]
        out = sim(r"""
snap(__payload.view, __payload.agents);
settle(2);
const ids = ['rv', 'md', 'w1', 'e1', 'p1', 'o1', 'c1', 'c2', 'r2', 'x1'];
__out = { short: ids.map(id => plateName(byId(id))), long: ids.map(id => plateName(byId(id), true)),
          tm: [plateName(byId('s:t')), plateName(byId('s:t'), true), nameOf(byId('s:t'))] };
""", {"view": view(), "agents": agents}, required=REQUIRED + ("plateName",))
        keys = ["rv", "md", "w1", "e1", "p1", "o1", "c1", "c2", "r2", "x1"]
        sh, lg = dict(zip(keys, out["short"])), dict(zip(keys, out["long"]))
        # fix round 3 (PR REVIEW pass 3): only the task's own name goes: a word that is the task of a live session of the
        # floor (its worktree folder, or the '<task>' of a '<task> Task Manager' name); any other hyphenated word stays
        self.assertEqual(sh["r2"], "re-run the tests", "a hyphenated word that is no task stays")
        self.assertEqual(sh["x1"], "other-task merge", "the name of a task nobody runs here stays")
        self.assertEqual(sh["rv"], "PR REVIEW")
        self.assertEqual(sh["md"], "merge")
        self.assertEqual(sh["w1"], "Worker 1 · seats")
        self.assertEqual(sh["e1"], "find the hook", "no task name in front: kept")
        self.assertEqual(sh["p1"], "PR REVIEW of the plates", "no task name in front: kept")
        self.assertEqual(sh["o1"], "city-x", "a task name alone stays")
        self.assertNotEqual(sh["c1"], sh["c2"])
        self.assertTrue(sh["c1"].startswith("UI CHECK") and sh["c2"].startswith("UI CHECK"), (sh["c1"], sh["c2"]))
        self.assertEqual(lg["rv"], "city-agents-at-desks PR REVIEW", "the hover plate keeps the whole description")
        self.assertEqual(lg["md"], "city-agents-at-desks merge")
        self.assertEqual(lg["e1"], "find the hook")
        self.assertEqual(out["tm"][0], out["tm"][2], "a session: nameOf, both forms")
        self.assertEqual(out["tm"][1], out["tm"][2])

    def test_the_plate_picks_the_form(self):
        src = script_function_source("pinOv") or ""
        self.assertRegex(src, r"plateName\(\s*c\s*,", "pinOv asks for the long form when the plate is hovered or selected")


class TestSelectedAndHoveredNeverOverlap(unittest.TestCase):
    """Fix round 3, item 1 (PR REVIEW pass 3, blocker): step 1 placed the selected (pri 3) and the hovered (pri 2) plates
    in full but checked them only against the panels. Now the second one moves the least way out of the first's box
    (down, left or right, inside the bounds, off the panels), as step 1 does for a panel: both full, never overlapping."""

    def test_the_two_item_repro(self):
        items = [{"x": 300, "y": 300, "w": 160, "wChip": 32, "h": 22, "pri": 3},
                 {"x": 330, "y": 305, "w": 160, "wChip": 32, "h": 22, "pri": 2}]
        out = sim("const items = __payload.items; __out = { modes: plateLayout(items, { bounds: { l: 0, t: 0, r: 1440, b: 713 }, blocks: [] }), items };",
                  {"items": items}, required=("plateLayout",))
        self.assertEqual(out["modes"], ["full", "full"])
        self.assertEqual(overlapping(boxes_of(out["items"], out["modes"])), [])

    def test_every_selected_and_hovered_pair_on_the_team_floor(self):
        out = sim(PROJECT_JS + r"""
snap(__payload.view, __payload.agents);
settle(40);
const ppl = live().filter(c => isDrawn(c) && c.at === c.terr);
const res = {};
for (const [W, H, panels] of __payload.sizes) {
  const base = plateItems(W, H).map((o, i) => Object.assign(o, { pri: platePri({ c: ppl[i] }) }));
  const opts = { bounds: { l: 4, t: 4, r: W - 4, b: H - 4 }, blocks: panels }, pairs = [];
  for (let a = 0; a < base.length; a++) for (let b = 0; b < base.length; b++) if (a !== b) {
    const its = base.map((o, j) => Object.assign({}, o, { pri: j === a ? 3 : j === b ? 2 : o.pri }));
    const m = plateLayout(its, opts);
    pairs.push({ a, b, ma: m[a], mb: m[b], items: its, modes: m });
  }
  res[W] = { pairs, panels };
}
__out = res;
""", {"view": view(), "agents": TEAM_AGENTS, "sizes": [[w, PANELS[w][0], PANELS[w][1]] for w in (468, 358)]},
            required=REQUIRED + ("plateLayout", "platePri", "FOV"))
        for w in ("468", "358"):
            with self.subTest(stage=w):
                pairs = out[w]["pairs"]
                self.assertEqual(len(pairs), 20)
                for pr in pairs:
                    self.assertEqual((pr["ma"], pr["mb"]), ("full", "full"), "selected %d, hovered %d" % (pr["a"], pr["b"]))
                    bx = boxes_of(pr["items"], pr["modes"])
                    self.assertEqual(overlapping(bx), [], "selected %d, hovered %d" % (pr["a"], pr["b"]))
                    self.assertEqual([b for b in bx for q in out[w]["panels"] if overlapping([b, tuple(q)])], [])


class TestPlateGap(unittest.TestCase):
    """Fix round 3 (my live check at 500x713: a full plate and a chip ended edge to edge, 0.6 px into each other, because
    the page measured whole-pixel widths of fractional plates). Two plates keep a gap of at least 2 px (panels: no gap
    needed); the page measures a plate's width as drawn (getBoundingClientRect, not offsetWidth)."""

    def test_plates_one_px_apart_are_too_close(self):
        items = [{"x": 100, "y": 100, "w": 100, "wChip": 32, "h": 22, "pri": 0},
                 {"x": 201, "y": 100, "w": 100, "wChip": 32, "h": 22, "pri": 0}]
        self.assertEqual(layout(items), ["full", "chip"], "1 px apart: the second keeps its chip")

    def test_plates_three_px_apart_are_fine(self):
        items = [{"x": 100, "y": 100, "w": 100, "wChip": 32, "h": 22, "pri": 0},
                 {"x": 203, "y": 100, "w": 100, "wChip": 32, "h": 22, "pri": 0}]
        self.assertEqual(layout(items), ["full", "full"])

    def test_the_selected_and_the_hovered_keep_the_gap(self):
        items = [{"x": 300, "y": 300, "w": 160, "wChip": 32, "h": 22, "pri": 3},
                 {"x": 461, "y": 300, "w": 160, "wChip": 32, "h": 22, "pri": 2}]
        out = sim("const items = __payload.items; __out = { modes: plateLayout(items, { bounds: { l: 0, t: 0, r: 1440, b: 713 }, blocks: [] }), items };",
                  {"items": items}, required=("plateLayout",))
        self.assertEqual(out["modes"], ["full", "full"])
        b = boxes_of(out["items"], out["modes"])
        gap = max(b[1][0] - b[0][2], b[0][0] - b[1][2], b[1][1] - b[0][3], b[0][1] - b[1][3])
        self.assertGreaterEqual(gap, 2 - 1e-6, "the hovered one moved at least 2 px clear: %s" % b)

    def test_widths_are_measured_as_drawn(self):
        src = (script_function_source("pinOv") or "") + (script_function_source("syncFigs") or "")
        self.assertIn("getBoundingClientRect", src)


class TestHoveredChipKeepsItsSpot(unittest.TestCase):
    """Fix round 3, item 3 (PR REVIEW pass 3): a chip nudged aside or a row up jumped back over its head when hovered, out
    from under a still pointer, so the hover ended at once (flicker). An item may carry px, py: where its plate was laid
    out last frame; a pri >= 2 item starts from there (not its head), so its full plate covers the spot it was hovered in."""

    def test_the_hovered_chip_stays_where_the_pointer_is(self):
        items = [{"x": 200, "y": 300, "w": 160, "wChip": 40, "h": 22, "pri": 0},
                 {"x": 212, "y": 300, "w": 160, "wChip": 40, "h": 22, "pri": 0},
                 {"x": 188, "y": 300, "w": 160, "wChip": 40, "h": 22, "pri": 0}]
        opts = {"bounds": {"l": 0, "t": 0, "r": 1440, "b": 713}, "blocks": []}
        first = sim("const items = __payload.items; __out = { modes: plateLayout(items, __payload.opts), items };",
                    {"items": items, "opts": opts}, required=("plateLayout",))
        moved = [i for i in range(3) if first["modes"][i] == "chip" and
                 (abs(first["items"][i]["x"] - items[i]["x"]) > 0.5 or abs(first["items"][i]["y"] - items[i]["y"]) > 0.5)]
        self.assertTrue(moved, "a chip was nudged: %s" % first)
        k = moved[0]
        spot = (first["items"][k]["x"], first["items"][k]["y"] - 11)   # the pointer rests on the middle of that chip
        again = [dict(it) for it in items]
        again[k]["pri"] = 2
        again[k]["px"], again[k]["py"] = first["items"][k]["x"], first["items"][k]["y"]
        out = sim("const items = __payload.items; __out = { modes: plateLayout(items, __payload.opts), items };",
                  {"items": again, "opts": opts}, required=("plateLayout",))
        self.assertEqual(out["modes"][k], "full")
        b = boxes_of([out["items"][k]], ["full"])[0]
        self.assertTrue(b[0] <= spot[0] <= b[2] and b[1] <= spot[1] <= b[3], "the full plate still covers the pointer: %s %s" % (b, spot))
        self.assertEqual(overlapping(boxes_of(out["items"], out["modes"])), [])

    def test_the_figure_pass_passes_the_last_spot(self):
        src = script_function_source("syncFigs") or ""
        for key in ("px", "py"):
            with self.subTest(key=key):
                self.assertRegex(src, r"[{,]\s*%s\s*:" % key, "the items carry %s (last frame's spot)" % key)


class TestHoverStaysWhenThePlateMoves(unittest.TestCase):
    """Fix round 3 (my live check: with one person selected, hovering another one's plate either never showed it full or
    flickered 11 times a second). When the hovered plate must move out of the selected one's way it leaves the still
    pointer; the browser then fires pointerout towards the canvas, which cleared the hover, the plate went back under the
    pointer, and so on. Now: a plate's pointerout clears the hover only when the pointer went to something that is neither
    the canvas nor another plate (a panel, or off the page); the canvas changes the hover only on a real pointer move."""

    def test_pointerout_towards_the_canvas_keeps_the_hover(self):
        from citypage import listener_block
        blk = listener_block(r"ovRoot", "pointerout") or ""
        self.assertIn("relatedTarget", blk)
        self.assertIn("canvas", blk, "the canvas under the pointer is no reason to drop the hover")

    def test_the_canvas_hover_needs_a_real_move(self):
        from citypage import listener_block
        blk = listener_block(r"canvas", "pointermove") or ""
        self.assertRegex(blk, r"movementX", "a pointermove with no movement (the page moved, not the pointer) changes nothing")


class TestOpenWindowsArePanels(unittest.TestCase):
    """Fix round 3 (my live check at 390x844: selecting a person opens its detail window as a sheet over the lower half of
    the stage, and plates were laid out under it, unseen and unreachable for the pointer). Every panel that can lie over
    the floor view is a block for the plates: also the detail window (#win), its tab (#win-tab), the ask panel (#ask)
    and the design popup (#dPop), whenever they show."""

    def test_panel_blocks_name_the_windows(self):
        src = script_function_source("panelBlocks") or ""
        for sel in ("#floorSign", "#rail", "#rail-tab", "#follow", "#proto", "#lift", ".cam", "#win", "#win-tab", "#ask", "#dPop"):
            with self.subTest(sel=sel):
                self.assertIn(sel, src)


class TestAgentOnItsParentsFloor(unittest.TestCase):
    """Fix round 3, item 5 (main manager's decision): an agent sits near its parent, so an agent whose own repo is another
    floor (its lines carry its own repo) is drawn on its parent's floor: at a desk there, counted there, not on its own."""

    def test_drawn_on_the_parents_floor(self):
        out = sim(r"""
snap(__payload.view, __payload.agents);
apply({ type: 'spawn', id: 'w2', role: 'worker', label: 'worker', task: 'city-x Worker 2: b', terr: __payload.t2, up: 's:t' });
settle(40);
const w1 = byId('w1'), w2 = byId('w2');
__out = { drawn: [isDrawn(w1), isDrawn(w2)], terr: [w1.terr, w2.terr], at: [w1.at, w2.at],
          seats: [seatOfId('w1'), seatOfId('w2')], desks: deskSeats(__payload.t1),
          count: [floorTag(__payload.t1).people, floorTag(__payload.t2).people] };
""", {"view": view(), "t1": T1, "t2": T2, "agents": [agent("s:t", "task-manager", up=GOV), agent("w1", "worker", up="s:t", terr=T2)]},
            required=REQUIRED + ("floorTag",))
        self.assertEqual(out["drawn"], [True, True], "from the snapshot and from a live spawn")
        self.assertEqual(out["terr"], [T1, T1], "on its parent's floor")
        self.assertEqual(out["at"], [T1, T1])
        for s_ in out["seats"]:
            self.assertTrue(any(same_spot(s_, d) for d in out["desks"]), "at a desk there: %s" % s_)
        self.assertEqual(out["count"], [4, 0], "counted on the parent's floor (its area manager, s:t, w1, w2), not on its own")

    def test_the_server_names_a_parent_on_another_floor(self):
        sys.path.insert(0, HERE)
        from cityhelp import TalkServerCase, A_REPO, B_REPO, TALK_TA, TALK_TB

        class Probe(TalkServerCase):
            def runTest(self):
                pass
        t = Probe()
        t.setUp()
        try:
            t.governor("g1", A_REPO)
            t.lead("tm1", repo=A_REPO)
            t.events()
            t.line("SubagentStart", "tm1", B_REPO, role="task-manager", aid="w9", at="worker")
            ev = t.spawn_of("w9")
            self.assertEqual(ev["up"], "s:tm1", "its parent, found on the other floor")
            self.assertEqual(ev["terr"], TALK_TB, "the server keeps its own repo; the page draws it at its parent")
            t.line("SubagentStart", "g1", B_REPO, aid="d9", at="merge-deputy")
            self.assertEqual(t.spawn_of("d9")["up"], "gov:" + TALK_TA, "the area manager of the other floor")
        finally:
            t.doCleanups()


class TestSeatCache(unittest.TestCase):
    """Fix round (main manager's decision 6): agentSeatsOf(terr) keeps its seats object until the people on the floor or
    the floor plan change: ticks with no change reuse the same object; a join, a leave or a new design rebuilds it."""

    def test_reused_until_something_changes(self):
        agents = [agent("s:t", "task-manager", up=GOV)] + [agent("w%d" % i, "worker", up="s:t") for i in range(1, 5)]
        out = sim(r"""
snap(__payload.view, __payload.agents);
settle(40);
const a = agentSeatsOf(__payload.t1); update(.05); const b = agentSeatsOf(__payload.t1); update(.05); const b2 = agentSeatsOf(__payload.t1);
apply({ type: 'spawn', id: 'w5', role: 'worker', label: 'worker', task: 'city-x Worker 5: new', terr: __payload.t1, up: 's:t' });
update(.05);
const c = agentSeatsOf(__payload.t1);
apply({ type: 'done', id: 'w1' });
settle(40);
const d = agentSeatsOf(__payload.t1);
apply({ type: 'world', world: __payload.view2, change: { kind: 'design', terr: __payload.t1, by: 'designer' } });
update(.05);
const e = agentSeatsOf(__payload.t1);
__out = { same: a === b && b === b2, joined: c !== b2 && c.has('w5'), left: d !== c && !d.has('w1') && !byId('w1'),
          plan: e !== d, n: [a.size, c.size, d.size, e.size] };
""", {"view": view(), "view2": view({T1: four_desk_design()}), "t1": T1, "agents": agents},
            required=REQUIRED + ("agentSeatsOf",))
        self.assertTrue(out["same"], "no change: the same seats object")
        self.assertTrue(out["joined"], "a join rebuilds")
        self.assertTrue(out["left"], "a leave rebuilds")
        self.assertTrue(out["plan"], "a new design rebuilds")
        self.assertEqual(out["n"], [4, 5, 4, 4])


class TestPlateName(unittest.TestCase):
    """Fix round (main manager's decision 7): the plate's name does not repeat the type the role chip already says
    ('审查员 reviewer · city-x PR REVIEW' -> '审查员 · city-x PR REVIEW'); an unknown type keeps its type word as the chip.
    plateName(c): a session -> nameOf(c); an agent -> its description (the same short form nameOf gives a task, e.g.
    'Worker 1 · seats'), '' when its description is only its type; two agents of one floor with the same name get the
    '#<id>' ending nameOf uses."""

    def test_names(self):
        agents = [agent("s:t", "task-manager", up=GOV, label="city-x Task Manager", task="city-x"),
                  agent("s:y", "task-manager", up=GOV, label="task-manager", task="city-y"),
                  agent("r1", "other", up=GOV, label="reviewer", task="city-x PR REVIEW"),
                  agent("m1", "merge-deputy", up=GOV, label="merge-deputy", task="city-x merge"),
                  agent("w1", "worker", up="s:t", label="worker", task="city-x Worker 1: seats"),
                  agent("e1", "other", up="s:t", label="Explore", task="find the hook"),
                  agent("a1", "worker", up="s:t", label="worker", task="worker"),
                  agent("c1", "other", up=GOV, label="check-deputy", task="city-y UI CHECK"),
                  agent("c2", "other", up=GOV, label="check-deputy", task="city-y UI CHECK")]
        out = sim(r"""
snap(__payload.view, __payload.agents);
settle(2);
const ids = ['s:t', 'r1', 'm1', 'w1', 'e1', 'a1', 'c1', 'c2'];
__out = { names: ids.map(id => plateName(byId(id))), words: ids.map(id => plateWord(byId(id))), tm: nameOf(byId('s:t')) };
""", {"view": view(), "agents": agents}, required=REQUIRED + ("plateName",))
        n = dict(zip(["s:t", "r1", "m1", "w1", "e1", "a1", "c1", "c2"], out["names"]))
        w = dict(zip(["s:t", "r1", "m1", "w1", "e1", "a1", "c1", "c2"], out["words"]))
        self.assertEqual(n["s:t"], out["tm"], "a session: as before")
        # fix round 2 (main manager's decision): the short name also drops the leading task name (TestPlateNameShort)
        self.assertEqual((w["r1"], n["r1"]), ("审查员", "PR REVIEW"))
        self.assertEqual((w["m1"], n["m1"]), ("合并副手", "merge"))
        self.assertEqual((w["w1"], n["w1"]), ("工人", "Worker 1 · seats"))
        self.assertEqual((w["e1"], n["e1"]), ("Explore", "find the hook"))
        self.assertEqual(n["a1"], "", "a description that is only the type: the chip alone")
        self.assertNotEqual(n["c1"], n["c2"])
        self.assertTrue(n["c1"].startswith("UI CHECK") and n["c2"].startswith("UI CHECK"), (n["c1"], n["c2"]))
        labels = {a["id"]: a["label"] for a in agents}
        for k, v in n.items():
            if k != "s:t":
                self.assertFalse(v.startswith(labels[k] + " "), "%s repeats its type: %s" % (k, v))

    def test_the_plate_uses_it(self):
        self.assertIn("plateName(", script_function_source("pinOv") or "")


PROJECT_JS = r"""
// the page's default floor view (resetView + fitDist + FOV), projected the way three.js does it
function project(W, H, pts){
  const a = W / Math.max(1, H), dist = (a < .9 ? Math.max(31, 24 / a) : 21) * Math.min(1.3, Math.max(1, 760 / Math.max(1, H)));
  const az = -.62, el = .86, T = [0, 0, .3], cp = Math.cos(el);
  const P = [T[0] + Math.sin(az) * cp * dist, T[1] + Math.sin(el) * dist, T[2] + Math.cos(az) * cp * dist];
  const sub = (u, v) => [u[0] - v[0], u[1] - v[1], u[2] - v[2]], dot = (u, v) => u[0] * v[0] + u[1] * v[1] + u[2] * v[2];
  const cross = (u, v) => [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
  const norm = u => { const l = Math.hypot(u[0], u[1], u[2]); return [u[0] / l, u[1] / l, u[2] / l]; };
  const f = norm(sub(T, P)), r = norm(cross(f, [0, 1, 0])), u = cross(r, f), t = Math.tan(FOV * Math.PI / 360);
  return pts.map(p => { const v = sub([p.x, 2.2, p.z], P), zc = dot(v, f);
    return { x: (dot(v, r) / (zc * t * a) + 1) / 2 * W, y: (1 - dot(v, u) / (zc * t)) / 2 * H }; });
}
// a plate's width as the page's CSS draws it: chip (10px bold, padding 6) + gap 5 + name (12px, max 130) + padding 15 + border 3
const textW = (s, px) => [...String(s)].reduce((n, ch) => n + (ch.charCodeAt(0) > 0x2e80 ? px : px * .58), 0);
function plateItems(W, H){
  const ps = live().filter(c => isDrawn(c) && c.at === c.terr);
  const at = project(W, H, ps.map(c => { const t = floorOfC(c); return { x: c.x - t.cx, z: c.y - t.cz }; }));
  return ps.map((c, i) => { const chip = 12 + textW(plateWord(c), 10);
    return { x: at[i].x, y: at[i].y, w: chip + 5 + Math.min(130, textW(nameOf(c), 12)) + 18, wChip: chip + 18, h: 22, pri: 0 }; });
}
"""


class TestPlatesOnTheCrowdFloor(unittest.TestCase):
    """Fix 1 on the 30-person crowd floor (6 managers x 4 workers), projected as the page's default floor view at the
    laptop's 1440x713 and at phone width 390x844: the plate boxes the layout computes do not intersect."""

    def test_no_two_plates_intersect(self):
        agents = []
        for i in range(6):
            agents.append(agent("s:m%d" % i, "task-manager", up=GOV, label="task-%d Task Manager" % i, task="task-%d" % i))
            agents += [agent("w%d-%d" % (i, k), "worker", up="s:m%d" % i, task="task-%d Worker %d: slice %d" % (i, k, k))
                       for k in range(1, 5)]
        out = sim(PROJECT_JS + r"""
snap(__payload.view, __payload.agents);
settle(40);
const res = {};
for (const [W, H] of [[1440, 713], [390, 844]]) { const items = plateItems(W, H); const modes = plateLayout(items, { bounds: { l: 0, t: 0, r: W, b: H }, blocks: [] }); res[W] = { items, modes, W, H }; }
__out = { n: live().filter(isDrawn).length, res };
""", {"view": view(), "agents": agents}, required=REQUIRED + ("plateLayout", "FOV"))
        self.assertEqual(out["n"], 30)
        for width in ("1440", "390"):
            with self.subTest(width=width):
                items, modes = out["res"][width]["items"], out["res"][width]["modes"]
                self.assertEqual(len(modes), 30)
                self.assertEqual(overlapping(boxes_of(items, modes)), [])
                self.assertGreater(sum(m != "none" for m in modes), 0)
                W, H = out["res"][width]["W"], out["res"][width]["H"]
                off = [b for b in boxes_of(items, modes) if b[0] < -0.5 or b[1] < -0.5 or b[2] > W + 0.5 or b[3] > H + 0.5]
                self.assertEqual(off, [], "nothing off screen")


class TestOthersStayWhenOneLeaves(unittest.TestCase):
    """Fix 2 (rule 3, the others stay): a leaving agent frees its desk; nobody else moves, also when a new one comes."""

    def test_the_other_three_keep_their_seats(self):
        agents = [agent("s:t", "task-manager", up=GOV)] + [agent("w%d" % i, "worker", up="s:t", task="city-x Worker %d: s%d" % (i, i))
                                                         for i in range(1, 5)]
        out = sim(r"""
snap(__payload.view, __payload.agents);
settle(40);
const ids = ['w2', 'w3', 'w4'];
const before = ids.map(seatOfId);
apply({ type: 'done', id: 'w1' });
settle(40);
const gone = !byId('w1');
const after = ids.map(seatOfId), pos = ids.map(posOfId);
apply({ type: 'spawn', id: 'w5', role: 'worker', label: 'worker', task: 'city-x Worker 5: new', terr: __payload.t1, up: 's:t' });
settle(40);
__out = { gone, before, after, pos, later: ids.map(seatOfId), w5: seatOfId('w5'), desks: deskSeats(__payload.t1), tm: seatOfId('s:t') };
""", {"view": view(), "t1": T1, "agents": agents})
        self.assertTrue(out["gone"], "worker 1 left")
        for i, wid in enumerate(("w2", "w3", "w4")):
            with self.subTest(worker=wid):
                self.assertTrue(same_spot(out["before"][i], out["after"][i]), "kept its desk: %s -> %s" % (out["before"][i], out["after"][i]))
                self.assertLess(dist(out["pos"][i], out["after"][i]), 0.3, "and sits there")
                self.assertTrue(same_spot(out["before"][i], out["later"][i]), "a new one coming moves nobody")
        self.assertTrue(any(same_spot(out["w5"], d) for d in out["desks"]), "the new one gets a desk")
        for s in out["later"] + [out["tm"]]:
            self.assertGreaterEqual(dist(out["w5"], s), MIN_GAP, "a free one")


class TestFloorCount(unittest.TestCase):
    """Fix 3 (main manager's decision): the floor label '<n> 人' (floorTag(terr).people, also the lift's number) counts
    every character drawn on that floor, managers and agents; an agent that is not drawn does not count."""

    def test_five_then_four(self):
        agents = [agent("s:t", "task-manager", up=GOV)] + [agent("w%d" % i, "worker", up="s:t") for i in range(1, 5)] + \
                 [agent("w9", "worker", up="s:nobody")]
        out = sim(r"""
apply({ type: 'snapshot', world: __payload.view, agents: __payload.agents, govs: [], gov: { state: 'idle', terr: __payload.view.floors[0] },
        asks: [], governors: 0, adding: [], hist: {} });
settle(30);
const first = floorTag(__payload.t1).people;
apply({ type: 'done', id: 'w1' });
settle(40);
__out = { first, after: floorTag(__payload.t1).people, other: floorTag(__payload.t2).people };
""", {"view": view(), "t1": T1, "t2": T2, "agents": agents}, required=REQUIRED + ("floorTag",))
        self.assertEqual(out["first"], 5, "1 manager + 4 agents (the agent of an unknown session is not drawn)")
        self.assertEqual(out["after"], 4)
        self.assertEqual(out["other"], 0)

if __name__ == "__main__":
    unittest.main()
