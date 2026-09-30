"""Failing tests: working people stay on their spot and show what kind of work they do
(owner, 2026-09-29, city-work-anim: "For an agent that is working, can it have some working
animation, instead of walking around only?"; mock mock/city-work-anim-mock.html, option A;
owner at the mock, 2026-09-30: "Plan A will do, just the frequency of doing the action is not
needed so frequent, can be less a bit" -> the action about half as often, calm pauses between).

CONTRACT (bin/agent-city.html)

  Simulation section (runs in node, see test_agent_city_people):
    WORK_HOLD_SEC = 6            a person keeps its working action this long after its last tool
                                 event, then stands on its spot (a short pause, never a walk).
    workKindOf(tool)             the kind of work of a tool kind the server sends: Edit, Write ->
                                 'build'; Read -> 'read' (the server already folds Grep, Glob,
                                 WebFetch, WebSearch into Read); Bash -> 'bash'; anything else
                                 ('Other', '', unknown) -> 'other'.
    A live 'tool' event, and a joined member's relayed 'tool' line, set c.workKind =
      workKindOf(tool) and c.workAt = simT. They never give the person a path: workWalk() is gone
      and nobody walks because of a tool event.
    c.workSince = simT only when the event starts a work spell (the person had no action right
      before it: workAction(c) was ''); a tool event during a spell leaves it alone, so the
      rhythm below keeps going instead of restarting on every fast tool call.
    workAction(c)                -> the kind the person acts out now, or '' (no action):
                                 the kind only while c.state is 'working' or 'building', c stands
                                 still (no path), is not stuck, not waiting, not relayed, not done,
                                 has had a tool event and simT - c.workAt < WORK_HOLD_SEC.
    citizenStatus(c)             a person that has had a tool event (c.workKind set), in 'working'
                                 or 'building' (and no ask / waiting / relay, which win as before):
                                 ['build', word] where word follows workAction(c):
                                   build with a building  -> 施工中 (state.building)
                                   build without one      -> 改代码 (work.edit)
                                   read -> 看文件 (work.read), bash -> 跑命令 (work.bash),
                                   other -> 忙着 (work.other), '' -> 停一下 (work.pause).
                                 A person with no tool event yet keeps the old words, and the code
                                 only reads the clock (simT) when c.workKind is set.
    TEXT has work.edit, work.read, work.bash, work.other, work.pause in zh and en.
    The calm idle stroll stays: 30 s (IDLE_STROLL_SEC) without a tool event -> a standalone
      working person takes its slow walk and comes back, as before.

  3D view (node with stubs):
    WORK_CYCLE_SEC = 4.5, WORK_ACT_SEC = 2: a calm rhythm -- in every 4.5 s cycle the person acts
      for the first 2 s, then holds still (the owner: about half as often as the mock).
    workPose(kind, t) -> { clip, speed, beat, flip }: what a still, working person plays at t
      seconds into its work spell (updatePerson passes simT - c.workSince, so people who started
      at different times never move in step). Real clips of the Kenney character models, no bones
      moved by code. beat = in the acting part of the cycle.
        build -> 'attack-melee-right' at speed .5 for t mod 4.5 < 2 (two hammer swings), else
                 'idle' (the hammer stays in hand)
        bash  -> 'interact-right' at speed 1.3 for t mod 4.5 < 2 (typing), else 'idle' at the laptop
        read  -> 'holding-both-shoot' all the time (the book held in both hands); flip = true for
                 t mod 4.5 < .5 (one page turn per cycle), never with reduced motion
        other -> 'interact-left' for t mod 4.5 < .9 (one hand gesture), else 'idle'
      prefers-reduced-motion (RM): the same clips at half the speed, no page flips.
    workProps(c) -> { hammer, book, laptop, lidOpen, planks } (booleans), what is shown now:
        workAction 'build': hammer; planks too when the person has no building (it hammers a
          small plank pile at its spot instead)
        'read': book; 'bash': laptop with lidOpen; 'other': nothing
        no action: nothing, except a person still standing on its spot (state 'working' or
          'building', no path) whose last work was bash keeps its laptop with the lid closed
          (no prop popping in and out)
        walking: nothing at all.
    updatePerson(c) plays workPose(workAction(c), ...) for a still, working person and sets the
      props from workProps(c); 'building' alone no longer loops interact-right.
    busy() (the frame-rate switch): true while anyone has a workAction; a building person that is
      pausing no longer keeps the full frame rate on its own.
    Dust at each hammer hit and small sparks at the laptop (only in the acting part) come from one
      shared pool:
      WORK_FX_MAX = 24 at most at once; workFx(kind, x, y, z) adds nothing when RM is on or the
      pool is full (returns false), else true.
    makePerson(c) hangs the book on the 'torso' bone and the hammer on 'arm-right' (as today);
      book, laptop and crate are a few boxes drawn in code with shared geometry -- no new files.

Run: python3 -m unittest tests.test_agent_city_work </dev/null
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import REQUIRED, function_source, page, plan_views, run_sim  # noqa: E402
from test_agent_city_ux_page import text_keys  # noqa: E402

WORK_REQUIRED = REQUIRED + ("workAction", "workKindOf", "WORK_HOLD_SEC")

# One territory, a present governor. Scenes:
#   solo  -- a task manager with no building: settles, then gets Read/Bash tool events
#   build -- a worker walks to its plot, builds, then Edit/Write/Read events at the building
#   stuck -- a working person that gets stuck walks to ask and acts nothing on the way
#   remote -- a joined member's person gets tool lines
#   stroll -- a standalone person with no tool event for 31 s still takes its calm walk
WORK_DRIVER = r"""
const V = __payload.view, T = V.territories[0], tid = T.id;
const PLOT = T.plots[0];
function buildLand(view){ landState(view); }
const trace = {};
function tick(sec){
  for (let i = 0; i < Math.round(sec * 10); i++) {
    const before = citizens.map(c => [c.id, c.x, c.y]);
    update(.1);
    for (const [id, x, y] of before) { const c = byId(id); if (c) trace[id] = (trace[id] || 0) + Math.hypot(c.x - x, c.y - y); }
  }
}
const st = c => citizenStatus(c, 1);
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: tid }, govs: [{ terr: tid, state: 'busy' }],
  governors: 1, asks: [], shows: [], agents: [] });
const out = { hold: WORK_HOLD_SEC, kinds: {} };
for (const t of ['Edit', 'Write', 'Read', 'Bash', 'Other', '', 'Mystery']) out.kinds[t] = workKindOf(t);

// solo: no building
apply({ type: 'spawn', id: 's:tm', role: 'task-manager', label: 'task-manager', task: 'solo', terr: tid });
tick(20);
const tm = byId('s:tm');
out.soloBefore = { state: tm.state, action: workAction(tm), status: st(tm), path: tm.path.length };
const w0 = trace['s:tm'] || 0, p0 = { x: tm.x, y: tm.y };
out.solo = [];
const spell0 = simT;
for (let i = 0; i < 6; i++) {
  const tool = i % 2 ? 'Read' : 'Bash';
  apply({ type: 'tool', id: 's:tm', tool });
  out.solo.push({ tool, kind: tm.workKind, action: workAction(tm), status: st(tm), path: tm.path.length,
                  since: tm.workSince - spell0 });
  tick(2);
}
out.soloWalked = (trace['s:tm'] || 0) - w0;
out.soloMoved = Math.hypot(tm.x - p0.x, tm.y - p0.y);
// last event (Read) was 2 s ago: still acting at 5.5 s, pausing after 6
tick(3.5);
out.soloAt55 = { action: workAction(tm), status: st(tm) };
tick(1);
out.soloAt65 = { action: workAction(tm), status: st(tm), path: tm.path.length, state: tm.state };
const spell1 = simT;
apply({ type: 'tool', id: 's:tm', tool: 'Edit' });
out.soloEdit = { action: workAction(tm), status: st(tm), since: tm.workSince - spell1 };
apply({ type: 'tool', id: 's:tm', tool: 'Other' });
out.soloOther = { action: workAction(tm), status: st(tm) };
tick(15);
out.soloStill = { moved: Math.hypot(tm.x - p0.x, tm.y - p0.y), path: tm.path.length };

// build: a worker at its own plot
apply({ type: 'spawn', id: 'w1', role: 'worker', label: 'worker', task: 'build', terr: tid });
tick(4);
apply({ type: 'build', id: 'w1', terr: tid, plot: PLOT.k, btype: 'house', x: PLOT.x, z: PLOT.z, by: 'worker' });
tick(45);
const w1 = byId('w1');
out.builtBefore = { state: w1.state, hasBld: !!w1.bld, action: workAction(w1), status: st(w1) };
const b0 = { x: w1.x, y: w1.y };
out.build = [];
for (const tool of ['Edit', 'Write', 'Read', 'Bash', 'Edit']) {
  apply({ type: 'tool', id: 'w1', tool });
  out.build.push({ tool, action: workAction(w1), status: st(w1), path: w1.path.length });
  tick(1.5);
}
tick(6);
out.buildPause = { action: workAction(w1), status: st(w1), state: w1.state };
out.buildMoved = Math.hypot(w1.x - b0.x, w1.y - b0.y);

// a walking person acts nothing, even right after a tool event
w1.path = [[w1.x + 3, w1.y]];
apply({ type: 'tool', id: 'w1', tool: 'Edit' });
out.walking = workAction(w1);
w1.path = [];

// stuck: asks, walks away, no action on the way
apply({ type: 'tool', id: 'w1', tool: 'Edit' });
apply({ type: 'stuck', id: 'w1', question: 'Which port?' });
tick(.5);
out.stuck = { action: workAction(w1), state: w1.state };

// remote member
apply({ type: 'remote', who: 'Ann', device: 'ann-laptop', dev: 'dev-ann', rid: 'acme/app', br: 'main',
        ev: { type: 'spawn', id: 'r:dev-ann:s:1', role: 'worker', label: 'worker', task: 'far', terr: tid } });
tick(20);
const r = byId('r:dev-ann:s:1');
const rw0 = trace['r:dev-ann:s:1'] || 0;
const rstate = r ? r.state : '';
for (let i = 0; i < 4; i++) {
  apply({ type: 'remote', who: 'Ann', device: 'ann-laptop', dev: 'dev-ann', rid: 'acme/app', br: 'main',
          ev: { type: 'tool', id: 'r:dev-ann:s:1', tool: i % 2 ? 'Bash' : 'Read' } });
  tick(1.5);
}
out.remote = r ? { found: true, state: rstate, kind: r.workKind, action: workAction(r), walked: (trace['r:dev-ann:s:1'] || 0) - rw0 } : { found: false };

// stroll: a standalone working person with no tool event for 31 s still strolls
apply({ type: 'spawn', id: 's:st', role: 'fast-lane-deputy', label: 'fast-lane-deputy', task: 'stroll', terr: tid });
tick(10);
const s = byId('s:st');
apply({ type: 'tool', id: 's:st', tool: 'Read' });
const sw0 = trace['s:st'] || 0;
tick(20);
const quiet20 = (trace['s:st'] || 0) - sw0;
tick(40);
out.stroll = { quiet20, after60: (trace['s:st'] || 0) - sw0 };

// a person without any tool event keeps the old words
const fresh = { state: 'building', askKind: '', askPhase: '', relay: '', waiting: false };
const freshW = { state: 'working', askKind: '', askPhase: '', relay: '', waiting: false };
out.fresh = [st(fresh), st(freshW)];
__out = out;
"""


class TestWorkingPeopleSim(unittest.TestCase):
    """The simulation half: who acts what, for how long, and nobody walks because of a tool."""

    @classmethod
    def setUpClass(cls):
        views = plan_views()
        cls.plan, view = sorted(views.items())[0]
        cls.r = run_sim(WORK_DRIVER, {"view": view}, WORK_REQUIRED)

    def test_hold_is_six_seconds(self):
        self.assertEqual(self.r["hold"], 6)

    def test_kind_of_each_tool(self):
        self.assertEqual(self.r["kinds"], {"Edit": "build", "Write": "build", "Read": "read", "Bash": "bash",
                                           "Other": "other", "": "other", "Mystery": "other"})

    def test_workwalk_is_gone(self):
        self.assertIsNone(function_source("workWalk"), "no walk on a tool event any more")
        self.assertNotIn("workWalk(", page())

    def test_no_action_before_the_first_tool(self):
        b = self.r["soloBefore"]
        self.assertEqual(b["state"], "working")
        self.assertEqual(b["action"], "")

    def test_a_person_without_a_building_stays_on_its_spot(self):
        for row in self.r["solo"]:
            with self.subTest(tool=row["tool"]):
                self.assertEqual(row["path"], 0, "a tool event gives no path")
        self.assertLess(self.r["soloWalked"], 0.05, "six tool events over 12 s: no walking")
        self.assertLess(self.r["soloMoved"], 0.05)

    def test_action_follows_the_last_tool(self):
        for row in self.r["solo"]:
            with self.subTest(tool=row["tool"]):
                want = "read" if row["tool"] == "Read" else "bash"
                self.assertEqual(row["kind"], want)
                self.assertEqual(row["action"], want)
                self.assertEqual(row["status"], ["build", "看文件" if want == "read" else "跑命令"])

    def test_a_spell_keeps_its_start(self):
        for row in self.r["solo"]:
            with self.subTest(tool=row["tool"]):
                self.assertAlmostEqual(row["since"], 0, places=6,
                                       msg="tool events during a spell never restart the rhythm")
        self.assertAlmostEqual(self.r["soloEdit"]["since"], 0, places=6,
                               msg="the first tool after a pause starts a new spell")

    def test_short_pause_after_the_hold(self):
        self.assertEqual(self.r["soloAt55"]["action"], "read", "5.5 s after the last tool: still reading")
        p = self.r["soloAt65"]
        self.assertEqual(p["action"], "", "6.5 s after: pausing")
        self.assertEqual(p["status"], ["build", "停一下"])
        self.assertEqual(p["path"], 0, "the pause is standing, never a walk")
        self.assertEqual(p["state"], "working")

    def test_edit_without_a_building_is_editing_not_building(self):
        e = self.r["soloEdit"]
        self.assertEqual(e["action"], "build")
        self.assertEqual(e["status"], ["build", "改代码"], "施工中 only with a building")

    def test_other_tools_are_busy(self):
        o = self.r["soloOther"]
        self.assertEqual(o["action"], "other")
        self.assertEqual(o["status"], ["build", "忙着"])

    def test_standing_stays_under_the_stroll_time(self):
        s = self.r["soloStill"]
        self.assertEqual(s["path"], 0)
        self.assertLess(s["moved"], 0.05, "15 s after the last tool, under the 30 s stroll time: still on its spot")

    def test_builder_acts_at_its_building(self):
        b = self.r["builtBefore"]
        self.assertEqual(b["state"], "building")
        self.assertTrue(b["hasBld"])
        want = {"Edit": ("build", "施工中"), "Write": ("build", "施工中"), "Read": ("read", "看文件"), "Bash": ("bash", "跑命令")}
        for row in self.r["build"]:
            with self.subTest(tool=row["tool"]):
                kind, word = want[row["tool"]]
                self.assertEqual(row["action"], kind)
                self.assertEqual(row["status"], ["build", word])
                self.assertEqual(row["path"], 0)
        self.assertLess(self.r["buildMoved"], 0.05, "a builder never leaves its building for a tool")
        p = self.r["buildPause"]
        self.assertEqual(p["state"], "building")
        self.assertEqual(p["action"], "")
        self.assertEqual(p["status"], ["build", "停一下"])

    def test_walking_person_acts_nothing(self):
        self.assertEqual(self.r["walking"], "")

    def test_stuck_person_acts_nothing(self):
        self.assertEqual(self.r["stuck"]["action"], "")
        self.assertNotIn(self.r["stuck"]["state"], ("working", "building"))

    def test_remote_member_acts_without_walking(self):
        r = self.r["remote"]
        self.assertTrue(r["found"], "the remote person was spawned")
        self.assertIn(r["state"], ("working", "building"))
        self.assertEqual(r["kind"], "bash")
        self.assertEqual(r["action"], "bash")
        self.assertLess(r["walked"], 0.05)

    def test_calm_stroll_still_after_thirty_quiet_seconds(self):
        s = self.r["stroll"]
        self.assertLess(s["quiet20"], 0.05, "20 s without a tool: still standing")
        self.assertGreater(s["after60"], 0.5, "then the slow walk around, as before")

    def test_no_tool_yet_keeps_the_old_words(self):
        self.assertEqual(self.r["fresh"][0], ["build", "施工中"])
        self.assertEqual(self.r["fresh"][1], ["build", "干活"])

    def test_new_words_in_both_languages(self):
        for key in ("work.edit", "work.read", "work.bash", "work.other", "work.pause"):
            with self.subTest(key=key):
                self.assertEqual(text_keys(key), 2, "zh and en")
        text = page()
        for word in ("改代码", "看文件", "跑命令", "忙着", "停一下"):
            with self.subTest(word=word):
                self.assertIn("'%s'" % word, text)


# ---------------------------------------------------------------------------
# 3D view: poses, props, frame rate, effects (functions run in node with stubs)
# ---------------------------------------------------------------------------

def const_value(name):
    m = re.search(r"^const %s = ([^;\n]+);" % re.escape(name), page(), re.M)
    return m.group(1).strip() if m else None


UNIT_JS = r"""
const fs = require('fs'), vm = require('vm');
const { src } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
const TS = [0, .3, .6, .95, 1.9, 2.1, 4.4, 4.6, 5.0, 6.4, 6.6];
out.ts = TS;
function box(extra){ const b = Object.assign({ Math, JSON, console }, extra); vm.createContext(b); vm.runInContext(src, b); return b; }
// workPose
for (const RM of [false, true]) {
  const b = box({ RM });
  const key = RM ? 'rm' : 'full';
  out[key] = {};
  for (const k of ['build', 'read', 'bash', 'other']) out[key][k] = TS.map(t => b.workPose(k, t));
}
// workProps
{
  let act = '';
  const b = box({ RM: false, workAction: () => act });
  const P = (c, a) => { act = a; return b.workProps(c); };
  out.props = {
    buildBld: P({ bld: {}, path: [], workKind: 'build' }, 'build'),
    buildNone: P({ bld: null, path: [], workKind: 'build' }, 'build'),
    read: P({ bld: null, path: [], workKind: 'read' }, 'read'),
    bash: P({ bld: null, path: [], workKind: 'bash' }, 'bash'),
    other: P({ bld: null, path: [], workKind: 'other' }, 'other'),
    pauseBash: P({ bld: null, path: [], workKind: 'bash', state: 'working' }, ''),
    pauseBuild: P({ bld: {}, path: [], workKind: 'build', state: 'building' }, ''),
    walkBash: P({ bld: null, path: [[3, 3]], workKind: 'bash', state: 'working' }, ''),
    askBash: P({ bld: null, path: [], workKind: 'bash', state: 'asking' }, ''),
    none: P({ bld: null, path: [], workKind: '', state: 'working' }, ''),
  };
}
// busy
{
  let acting = new Set();
  const cit = [];
  const b = box({ RM: false, drag: null, pinch: null, camTween: null, autoRotating: () => false, floaters: [], shows: new Map(),
                  needFrame: false, citizens: cit, workAction: c => acting.has(c.id) ? 'build' : '' });
  cit.push({ id: 'p', path: [], state: 'building' });
  out.busyPaused = b.busy();
  acting.add('p');
  out.busyActing = b.busy();
}
process.stdout.write(JSON.stringify(out));
"""


def run_unit(src):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "unit.js")
        data = os.path.join(tmp, "data.json")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(UNIT_JS)
        with open(data, "w", encoding="utf-8") as fh:
            json.dump({"src": src}, fh)
        result = subprocess.run([node, script, data], capture_output=True, text=True, timeout=60,
                                stdin=subprocess.DEVNULL)
    if result.returncode != 0 or not result.stdout.strip():
        raise AssertionError("unit harness failed:\n" + result.stderr[-3000:])
    return json.loads(result.stdout)


class TestWorkingPeople3D(unittest.TestCase):
    """The 3D half: which clip, which props, frame rate, the effect pool."""

    @classmethod
    def setUpClass(cls):
        parts = []
        for name in ("workPose", "workProps", "busy"):
            src = function_source(name)
            if src is None:
                raise AssertionError("function %s not found in bin/agent-city.html" % name)
            parts.append(src)
        consts = []
        for name in ("WORK_FX_MAX", "WORK_CYCLE_SEC", "WORK_ACT_SEC"):
            v = const_value(name)
            if v is not None:
                consts.append("var %s = %s;" % (name, v))
        # WORK_POSE (if the page keeps the table in a const object) goes in as written
        m = re.search(r"^const WORK_POSE = \{.*?^\};|^const WORK_POSE = \{[^\n]*\};", page(), re.M | re.S)
        if m:
            consts.append(m.group(0).replace("const WORK_POSE", "var WORK_POSE", 1))
        cls.r = run_unit("\n".join(consts + parts))

    def test_cycle_constants(self):
        self.assertEqual(const_value("WORK_CYCLE_SEC"), "4.5")
        self.assertEqual(const_value("WORK_ACT_SEC"), "2")

    def pose(self, key, kind):
        return dict(zip(self.r["ts"], self.r[key][kind]))

    def test_build_swings_then_holds_still(self):
        p = self.pose("full", "build")
        for t in (0, .3, .6, .95, 1.9, 4.6, 5.0, 6.4):
            with self.subTest(t=t):
                self.assertEqual(p[t]["clip"], "attack-melee-right")
                self.assertAlmostEqual(p[t]["speed"], .5)
                self.assertTrue(p[t]["beat"])
        for t in (2.1, 4.4, 6.6):
            with self.subTest(t=t):
                self.assertEqual(p[t]["clip"], "idle", "a calm pause between swings")
                self.assertFalse(p[t]["beat"])

    def test_bash_types_then_holds_still(self):
        p = self.pose("full", "bash")
        for t in (0, .95, 1.9, 4.6, 6.4):
            with self.subTest(t=t):
                self.assertEqual(p[t]["clip"], "interact-right")
                self.assertAlmostEqual(p[t]["speed"], 1.3)
                self.assertTrue(p[t]["beat"])
        for t in (2.1, 4.4, 6.6):
            with self.subTest(t=t):
                self.assertEqual(p[t]["clip"], "idle")
                self.assertFalse(p[t]["beat"])

    def test_read_holds_the_book_and_turns_one_page_a_cycle(self):
        p = self.pose("full", "read")
        for t in self.r["ts"]:
            with self.subTest(t=t):
                self.assertEqual(p[t]["clip"], "holding-both-shoot")
        flips = [t for t in self.r["ts"] if p[t]["flip"]]
        self.assertEqual(flips, [0, .3, 4.6], "one page turn in the first .5 s of each 4.5 s cycle")

    def test_other_is_one_gesture_a_cycle(self):
        p = self.pose("full", "other")
        clips = [p[t]["clip"] for t in self.r["ts"]]
        self.assertEqual(clips, ["interact-left", "interact-left", "interact-left", "idle", "idle", "idle",
                                 "idle", "interact-left", "interact-left", "idle", "idle"])

    def test_no_page_flips_for_other_kinds(self):
        for k in ("build", "bash", "other"):
            with self.subTest(kind=k):
                self.assertFalse(any(x["flip"] for x in self.r["full"][k]))

    def test_reduced_motion_is_half_speed_and_no_flips(self):
        for k in ("build", "read", "bash", "other"):
            for full, rm in zip(self.r["full"][k], self.r["rm"][k]):
                with self.subTest(kind=k):
                    self.assertEqual(rm["clip"], full["clip"])
                    self.assertAlmostEqual(rm["speed"], full["speed"] / 2)
                    self.assertFalse(rm["flip"], "no page flips with reduced motion")

    def test_props_follow_the_work(self):
        p = self.r["props"]
        on = lambda d: sorted(k for k, v in d.items() if v)  # noqa: E731
        self.assertEqual(on(p["buildBld"]), ["hammer"])
        self.assertEqual(on(p["buildNone"]), ["hammer", "planks"])
        self.assertEqual(on(p["read"]), ["book"])
        self.assertEqual(on(p["bash"]), ["laptop", "lidOpen"])
        self.assertEqual(on(p["other"]), [])
        self.assertEqual(on(p["pauseBash"]), ["laptop"], "pausing at the laptop: lid closed, it stays")
        self.assertEqual(on(p["pauseBuild"]), [], "pausing: the hammer is put away")
        self.assertEqual(on(p["walkBash"]), [], "walking: nothing in hand")
        self.assertEqual(on(p["askBash"]), [], "asking at the hall: no laptop there")
        self.assertEqual(on(p["none"]), [])

    def test_frame_rate_follows_real_work(self):
        self.assertFalse(self.r["busyPaused"], "a pausing builder alone lets the page idle")
        self.assertTrue(self.r["busyActing"])

    def test_update_person_uses_pose_and_props(self):
        up = function_source("updatePerson") or ""
        self.assertIn("workAction(", up)
        self.assertIn("workPose(", up)
        self.assertIn("workProps(", up)
        self.assertNotRegex(up, r"state\s*===\s*'building'\)\s*a\s*=\s*'interact-right'",
                            "'building' alone no longer loops interact-right")

    def test_effect_pool(self):
        self.assertEqual(const_value("WORK_FX_MAX"), "24")
        fx = function_source("workFx") or ""
        self.assertTrue(fx, "function workFx(kind, x, y, z) not found")
        self.assertIn("RM", fx, "no dust or sparks with reduced motion")
        self.assertIn("WORK_FX_MAX", fx)

    def test_props_hang_on_the_bones(self):
        mp = function_source("makePerson") or ""
        self.assertIn("'torso'", mp, "the book is held in front of the torso")
        self.assertIn("'arm-right'", mp, "the hammer stays in the right hand")

    def test_no_new_asset_files(self):
        text = page()
        for name in ("book", "laptop", "crate"):
            with self.subTest(prop=name):
                self.assertNotRegex(text, r"['/]%s[\w-]*\.glb" % name, "props are drawn in code")


if __name__ == "__main__":
    unittest.main()
