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

from citypage import const_object, run_sim, script_function_source, text_zh, js_value  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
