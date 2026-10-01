"""Failing tests: city-talk T1 + T2 + T3 (owner, 2026-10-01; approved mock mock/city-talk-mock.html 08751c5).
People in the city talk like people. The owner kept the default talk style: the sender walks over and
talks. There is no "turn in place + flying letter" in the real page.

T1  A new agent appears NEXT TO the one who sent it; the two face each other, the task is handed over,
    then the new one walks to its own spot.
T2  People never stack: a gap when they stand, appear, wait, leave and walk.
T3  A face-to-face talk whenever one agent messages, asks or answers another. A talk never hides or
    delays a real status (等你, 后台在跑, 空闲, stuck, done).

CONTRACT

Page, the simulation part of bin/agent-city.html (before the "3D view." comment)

  Numbers (top-level const): HANDOVER_SEC = 2.6, TALK_SEC = 2, TALK_REPLY_AT = .62, TALK_NEAR = 1.2,
    TALK_TRIP_MAX_SEC = 4, TALK_WAIT_MAX = 3, WALK_GAP = .3. MIN_GAP stays .45.
  Page ids: a citizen's id, or "gov:<territory id>" for that territory's governor (as in the chat).
  talkOf(c) -> null, or { kind, with, speaking, icon } while citizen c is IN a talk (standing face to
    face; never while it walks over or waits in line). govTalkOf(terr) -> the same for the governor.
      kind: 'handover' | 'msg' | 'ask' | 'answer'; with: the other one's page id ('' = nobody stands by);
      speaking: true for the one whose bubble shows now; icon: the bubble text when speaking, else ''.
      The one who starts speaks first: 📋 handover, 💬 msg, ❓ ask, ✅ answer. From TALK_REPLY_AT of the
      talk's length on the other one speaks: 👌. A hand-over to several new ones: the sender speaks all
      the time.
  While in a talk both face each other (c.yaw; the governor: governorAt(terr).yaw). Nobody moves.

  T1  A 'spawn' event carries "from": '' | a citizen id | "gov:<terr>".
      Sender = that citizen (alive, same territory) or that governor (present). With a sender the new
      one starts in state 'handover' on a free walkable spot beside the sender: MIN_GAP .. TALK_NEAR
      away from it (up to 1.6 when many arrive at once), at least MIN_GAP from everybody else; a
      'handover' talk runs for HANDOVER_SEC from its own start; the sender stays where it is. Then the
      new one walks to its own spot as before (to_plot; a stuck one goes up the chain). Several new
      ones from one sender at once: each on its own spot, one hand-over for all.
      No sender ("from" missing, '', unknown, a governor who is away): state 'spawn' as before, but
      never on the governor's spot or on each other: a free spot beside the hall stand.
      People placed by a snapshot get no hand-over.
  T3  A 'talk' event { type: 'talk', from, to, terr }: from / to are page ids, to may be ''.
      - The sender walks over (state 'to_talk') only when it is at work (working / building), the other
        one stands in the same territory, and they are further apart than TALK_NEAR. It gets to a free
        spot beside the other one (MIN_GAP .. TALK_NEAR) in about TALK_TRIP_MAX_SEC, faster when far.
        Then 'talking' for TALK_SEC, then it walks back to its own spot ('back') and both go on.
      - Closer than TALK_NEAR: nobody walks, both turn and talk where they stand.
      - The governor as sender walks over the same way and goes back to his hall stand after; anyone
        who needs him (goHall / governorSummon) calls him back at once and that talk is dropped.
        The governor as the other one: the sender walks to a spot beside the hall stand.
      - No walk, the bubble on the sender's own spot for TALK_SEC ({ kind: 'msg', with: '' }): "to" is
        '' or unknown, the other one is in another territory or walking, the sender is not at work, or
        more than TALK_WAIT_MAX talks already wait for that person.
      - One talk per person at a time; the others wait in line, in order.
      - Unknown sender: nothing happens.
      A relay (question passed up): on arrival (at_lead / asking) an 'ask' talk of TALK_SEC with the
      lead / the governor; the waiting one keeps facing whom it waits for. relay_end by 'lead' or
      'governor' while it stands there: an 'answer' talk of TALK_SEC first (the lead / the governor
      speaks), then it walks back. relay_end by anything else, or while it still walks: straight back.
      An answered ask ('answer' event -> 'heard'): the governor speaks an 'answer' talk meanwhile.
      A talk never changes citizenStatus(c): to_talk / talking read as the work state it left
      (working / building). A real change ends the talk for both at once: 'waiting' (等你回话 shows
      at once), 'stuck' and 'relay' (it heads up the chain at once), 'done' (it finishes; rest
      follows). 'background' and 'idle' show at once.
  T2  Standing people of a territory (and its governor) are never closer than MIN_GAP: on spawn (with or
      without a sender), in every talk, while waiting, and a leaving person at the hall.
      A walker walks around people: it never comes closer than WALK_GAP to a person who stands or to
      another walker, when there is room to pass; it still arrives.

Page, demo mode (#demo; fake data, same look): spawnDemo's spawn event carries from: 'gov:' + terr only in
  the territory whose governor the demo draws (terr === govTerr: the demo governor hands the new one its
  task); in every other demo territory nobody stands at the hall, so from is '' there. demoTalkTick(dt), called from update() only in DEMO, sends a
  { type: 'talk', from, to, terr } event between two demo people at work in one territory about every
  DEMO_TALK_SEC (a top-level number, 6 .. 15) seconds, through emit()/apply() like a live event.

Page, the 3D part: a .talkb bubble per person (CSS rule .talkb; ensureOv makes it; updatePerson shows
  it from talkOf(c)); the governor's from govTalkOf(terr); the one who speaks plays a talk gesture
  (the 3D part reads `.speaking`); with prefers-reduced-motion no gesture, the bubble stays.

  The governor's head (bounce 2, 2026-10-01: in a hand-over his 📋 stood about 130 px over his head, on the
  hall roof: his overlays were anchored at height .9 although he is about .5 tall, and the talk bubble
  was stacked on top of his speech bubble). GOV_HEAD_H = .78, a top-level number: a citizen's bubble
  height (.72) plus what the governor is taller. updateGovernor and updateGovPool take the head point
  from toScreen(x, GOV_HEAD_H, y) for his talk bubble, his speech bubble and his "?". The talk bubble
  takes the spot at his head; the others stand above it. govHeadRows(talkOn, bubOn, qmOn), top-level
  and pure -> how many px above the head point each one is pinned:
  { talk: 0, bub: talkOn ? 38 : 0, qm: (talkOn ? 38 : 0) + (bubOn ? 32 : 0) }. Both functions use it.

Server (bin/agent_city.py)
  A 'spawn' event carries "from": a subagent -> its owner session's page id ("gov:<terr>" when the owner
    is that territory's governor, else "s:<sid>" when that citizen is live, else ""); a session whose
    hook role is "task-manager" -> "gov:<terr>" when its territory has a governor, else ""; any other
    session -> "".
  A PostToolUse SendMessage line with a "to" (the recipient's name) -> one event
    {"type": "talk", "from": <sender page id>, "to": <page id or "">, "terr": <sender's territory>}.
    Sender: the subagent (aid), the governor ("gov:<terr>") or the session citizen ("s:<sid>").
    "to" is resolved, in this order: a live session citizen whose label equals it (any case; the
    sender's territory first); a live subagent's id; a session id (a live session citizen -> "s:<sid>",
    a territory's governor -> "gov:<terr>"); a socket address "uds:<any path>/<pid>.sock" (bounce 1,
    2026-10-01: Claude Code answers a message to the sender's socket, named after its pid) -> the live
    session whose known pid (the "pid" of its hook lines; a governor with none: the pid it was seated
    with) is <pid>, as a citizen or as a governor; a territory with a governor whose name it starts
    with (then the end, a space or "-": "app Manager", "app-7f") -> "gov:<terr>" (the sender's own
    territory first); else "". Never the sender itself: that gives "".
    No talk event: no "to" (old hooks), ask == "q" (the relay shows it), or the line closed a relay
    (relay_end shows the answer).
Hook (bin/agent-city-hook.sh)
  A PostToolUse SendMessage line carries "to": tool_input.to, at most 80 characters, JSON-safe; never
  the message. "" for a question (ask == "q": the recipient is not needed), for every other tool and
  event. The key sits right before "ask" (the last five keys stay ask wt file tp pid).
  The relay never gets it (to_wire keeps its own field list).

Run: python3 -m unittest tests.test_agent_city_talk </dev/null
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import REQUIRED, ac, function_source, page, run_sim  # noqa: E402
from test_agent_city_page import page_fns, run_node  # noqa: E402
from test_agent_city_walk import plan_view  # noqa: E402
from cityhelp import Mains  # noqa: E402
import agent_city_relay as relay  # noqa: E402

MIN_GAP, WALK_GAP, TALK_NEAR, HANDOVER_SEC, TALK_SEC, TRIP = .45, .3, 1.2, 2.6, 2.0, 4.0
EPS = 1e-6

TALK_REQUIRED = REQUIRED + ("talkOf", "govTalkOf", "HANDOVER_SEC", "TALK_SEC", "MIN_GAP", "angleDiff", "hallStand",
                            "findPath", "freeAt", "waitStand", "goTo", "leave", "govMove", "simT")

PRELUDE = r"""
function buildLand(view){ landState(view); }
{   // the driver lives in its own block: a new name in the page never clashes with a name here
let seed = 20261001; Math.random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;   // same scene every run
const V = __payload.view, T = V.territories[0], tid = T.id, GOV = 'gov:' + tid, OFF = T.offices[0];
const AG = (id, role, extra) => Object.assign({ id, role, label: role, task: 't-' + id, stuck: false, done: false, tools: {},
  terr: tid, lead: '', office: null, relay: '' }, extra || {});
const CAST = () => [AG('s:L', 'task-manager', { office: { x: OFF.x, z: OFF.z } }),
  AG('w1', 'worker', { lead: 's:L' }), AG('w2', 'worker', { lead: 's:L' }), AG('w3', 'worker', { lead: 's:L' }),
  AG('s:H', 'task-manager'), AG('d1', 'fast-lane-deputy')];
const g = () => governorAt(tid);
const P = id => id === GOV ? g() : byId(id);
const D = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const faces = (a, b) => Math.abs(angleDiff(a.yaw, Math.atan2(b.x - a.x, b.y - a.y))) < .3;
const walking = c => !!(c && c.path && c.path.length);
const govWalking = () => { const m = govMove.get(tid); return !!(m && m.path && m.path.length); };
const tk = id => { const t = id === GOV ? govTalkOf(tid) : (byId(id) ? talkOf(byId(id)) : null);
  return t ? { kind: t.kind, with: t.with, speaking: !!t.speaking, icon: t.icon || '' } : null; };
const at = id => { const p = P(id); return p ? { x: p.x, y: p.y } : null; };
const st = c => citizenStatus(c, 1);
const r3 = v => +(+v).toFixed(3);
const stackBad = [];
// T2: standing people (and the governor) are never closer than MIN_GAP, at every tick of every scene
function checkGaps(label){
  const ps = citizens.filter(c => !c.gone && c.state !== 'resting' && c.state !== 'leaving')
    .map(c => ({ id: c.id, x: c.x, y: c.y, walk: walking(c) }));
  const gv = g(); if (gv) ps.push({ id: GOV, x: gv.x, y: gv.y, walk: govWalking() });
  for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) {
    if (ps[i].walk || ps[j].walk) continue;
    const d = D(ps[i], ps[j]);
    if (d < MIN_GAP - 1e-6 && stackBad.length < 12) stackBad.push([label, ps[i].id, ps[j].id, r3(d)]);
  }
}
function tick(sec, label, each){
  for (let i = 0; i < Math.round(sec * 10); i++) {
    for (const c of citizens) c.toolAt = simT;              // nobody takes an idle stroll in these scenes
    const m = govMove.get(tid); if (m) m.idleSince = simT;  // the governor neither
    update(.1); checkGaps(label || ''); if (each) each();
  }
}
function until(cond, max, label, each){ let t = 0; while (!cond() && t < max) { tick(.1, label, each); t += .1; } return +t.toFixed(1); }
function start(){
  apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: tid }, govs: [{ terr: tid, state: 'busy' }], governors: 1,
    asks: [], shows: [], agents: CAST() });
  tick(1, 'start');
}
// the point at fraction f of the way `from` -> path (a list of [x, y])
function along(path, from, f){
  const pts = [[from.x, from.y]].concat(path), seg = []; let len = 0;
  for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(d); len += d; }
  let t = len * f;
  for (let i = 0; i < seg.length; i++) {
    if (t <= seg[i]) { const k = seg[i] ? t / seg[i] : 0; return { x: pts[i][0] + (pts[i + 1][0] - pts[i][0]) * k, y: pts[i][1] + (pts[i + 1][1] - pts[i][1]) * k }; }
    t -= seg[i];
  }
  const e = pts[pts.length - 1]; return { x: e[0], y: e[1] };
}
function put(c, p){ c.x = p.x; c.y = p.y; c.home = { x: p.x, y: p.y }; c.stand = c.home; c.path = []; c.state = 'working'; }
// two points 3 to 4 apart with open ground between and around them, away from everybody: [A, B] or null
function openWay(){
  const ring = p => [0, 1, 2, 3, 4, 5, 6, 7].every(i => freeAt(p.x + Math.cos(i * Math.PI / 4) * .6, p.y + Math.sin(i * Math.PI / 4) * .6));
  const clear = p => freeAt(p.x, p.y) && ring(p) && citizens.every(c => D(c, p) > 1.1) && D(g(), p) > 1.1;
  for (let r = 0; r < V.h; r++) for (let c = 0; c < V.w; c++) {
    const A = { x: V.x0 + c + .5, y: V.z0 + r + .5 };
    if (Math.hypot(A.x - T.cx, A.y - T.cz) > 9 || !clear(A)) continue;
    for (const [dx, dy] of [[4, 0], [0, 4], [3, 0], [0, 3], [2.5, 2.5], [2.5, -2.5]]) {
      const B = { x: A.x + dx, y: A.y + dy }; let ok = true;
      for (let k = 0; k <= 16 && ok; k++) ok = clear({ x: A.x + dx * k / 16, y: A.y + dy * k / 16 });
      if (ok && findPath(A.x, A.y, B.x, B.y)) return [A, B];
    }
  }
  return null;
}
const out = {};
"""

SCENES = {}

# T1: one worker from its lead, a deputy and a task manager from the governor, a helper's own subagent, 5 at once
SCENES["spawn"] = r"""
start();
const L = byId('s:L'), H = byId('s:H');
out.snapTalk = ['s:L', 'w1', 's:H', GOV].map(tk);
const L0 = at('s:L');
apply({ type: 'spawn', id: 'w9', role: 'worker', label: 'worker', task: 'page', terr: tid, lead: 's:L', office: null, from: 's:L' });
const n = byId('w9'), n0 = at('w9');
out.one = { state0: n.state, d0: D(n, L), talkNew0: tk('w9'), talkLead0: tk('s:L') };
tick(.8, 'handover');
out.one.face = [faces(n, L), faces(L, n)];
tick(HANDOVER_SEC * .8 - .8, 'handover');
out.one.reply = [tk('w9'), tk('s:L')]; out.one.stateMid = n.state; out.one.movedMid = D(n, n0); out.one.leadMoved = D(L, L0);
tick(HANDOVER_SEC * .2 + .4, 'handover-end');
out.one.after = { state: n.state, talks: [tk('w9'), tk('s:L')] };
out.one.t = until(() => n.state === 'working' && !walking(n), 30, 'to-spot');
out.one.end = { state: n.state, home: D(n, n.home) };

const G0 = at(GOV);
apply({ type: 'spawn', id: 'd9', role: 'fast-lane-deputy', label: 'fast-lane-deputy', task: 'msg-sides Deputy', terr: tid, lead: '', office: null, from: GOV });
const d9 = byId('d9');
out.gov = { state0: d9.state, d0: D(d9, g()), talkGov0: tk(GOV), talkNew0: tk('d9') };
tick(.8, 'gov-handover');
out.gov.face = [faces(d9, g()), faces(g(), d9)]; out.gov.govMoved = D(g(), G0);
tick(HANDOVER_SEC, 'gov-handover-end');
out.gov.after = { state: d9.state, talkGov: tk(GOV) };

apply({ type: 'spawn', id: 's:N', role: 'task-manager', label: 'city-rail Task Manager', task: 'app', terr: tid, lead: '', office: null, from: GOV });
out.tm = { state0: byId('s:N').state, d0: D(byId('s:N'), g()), talkGov0: tk(GOV) };
apply({ type: 'spawn', id: 'h1', role: 'other', label: 'Explore', task: 'survey', terr: tid, lead: '', office: null, from: 's:H' });
out.sub = { state0: byId('h1').state, d0: D(byId('h1'), H), talkH0: tk('s:H') };
tick(HANDOVER_SEC + .6, 'two-handovers');
out.tm.after = byId('s:N').state; out.sub.after = byId('h1').state;
until(() => citizens.every(c => !walking(c)), 30, 'settle');

const five = ['k1', 'k2', 'k3', 'k4', 'k5'];
for (const id of five) apply({ type: 'spawn', id, role: 'worker', label: 'worker', task: id, terr: tid, lead: 's:L', office: null, from: 's:L' });
let minPair = 9;
for (let i = 0; i < 5; i++) for (let j = i + 1; j < 5; j++) minPair = Math.min(minPair, D(byId(five[i]), byId(five[j])));
out.five = { states0: five.map(id => byId(id).state), d0: five.map(id => r3(D(byId(id), L))), minPair0: minPair, talkLead0: tk('s:L') };
tick(HANDOVER_SEC * .8, 'five');
out.five.talkLeadLate = tk('s:L'); out.five.statesMid = five.map(id => byId(id).state);
tick(HANDOVER_SEC * .2 + .5, 'five-end');
out.five.after = { states: five.map(id => byId(id).state), talkLead: tk('s:L') };
out.five.t = until(() => five.every(id => byId(id).state === 'working' && !walking(byId(id))), 45, 'five-walk');
out.five.end = five.map(id => byId(id).state);
out.stackBad = stackBad;
__out = out;
}
"""

# T1 + T2: nobody sent it -> as before, but never on the governor or on each other
SCENES["nosender"] = r"""
start();
apply({ type: 'spawn', id: 'p1', role: 'worker', label: 'worker', task: 'a', terr: tid });
apply({ type: 'spawn', id: 'p2', role: 'worker', label: 'worker', task: 'b', terr: tid, from: '' });
apply({ type: 'spawn', id: 'p3', role: 'worker', label: 'worker', task: 'c', terr: tid, from: 'nobody' });
const ids = ['p1', 'p2', 'p3'], ps = ids.map(byId);
let minPair = 9;
for (let i = 0; i < 3; i++) for (let j = i + 1; j < 3; j++) minPair = Math.min(minPair, D(ps[i], ps[j]));
out.states = ps.map(c => c.state); out.talks = ids.map(tk); out.dGov = ps.map(c => r3(D(c, g()))); out.minPair = minPair;
out.govTalk = tk(GOV);
tick(.5, 'spawned');
until(() => ps.every(c => c.state === 'working' && !walking(c)), 40, 'walk');
out.end = ps.map(c => c.state);
apply({ type: 'gov', terr: tid, state: 'idle', present: false });
apply({ type: 'spawn', id: 'p4', role: 'worker', label: 'worker', task: 'd', terr: tid, from: GOV });
out.noGov = { state: byId('p4').state, talk: tk('p4') };
tick(1, 'no-gov');
out.stackBad = stackBad;
__out = out;
}
"""

# T3: a message, far apart -> the sender walks over, they talk, it walks back; close by; not recognised
SCENES["talk"] = r"""
start();
const L = byId('s:L'), H = byId('s:H');
out.far0 = D(H, L);
const H0 = at('s:H'), L0 = at('s:L'), sH = st(H), sL = st(L);
apply({ type: 'talk', from: 's:H', to: 's:L', terr: tid });
out.go = { state: H.state, walking: walking(H), talks: [tk('s:H'), tk('s:L')], status: [st(H), st(L)], before: [sH, sL] };
out.trip = until(() => !walking(H) && H.state === 'talking', 14, 'walk-over');
out.arrive = { state: H.state, d: D(H, L), talks: [tk('s:H'), tk('s:L')], status: [st(H), st(L)], leadMoved: D(L, L0) };
tick(.8, 'talk'); out.face = [faces(H, L), faces(L, H)];
tick(TALK_SEC * .8 - .8, 'talk'); out.reply = [tk('s:H'), tk('s:L')];
tick(TALK_SEC * .2 + .4, 'talk-end');
out.after = { state: H.state, walking: walking(H), talks: [tk('s:H'), tk('s:L')], leadState: L.state, leadMoved: D(L, L0) };
out.backT = until(() => !walking(H) && (H.state === 'working' || H.state === 'building'), 30, 'walk-back');
out.end = { state: H.state, home: D(H, H0) };

const w1 = byId('w1');
put(w1, waitStand({ x: L.x, y: L.y }, citizens.filter(c => c !== w1 && c !== L).map(c => ({ x: c.x, y: c.y }))));
tick(.5, 'near-settle');
const w0 = at('w1');
apply({ type: 'talk', from: 'w1', to: 's:L', terr: tid });
out.near = { d: D(w1, L), walking: walking(w1), talks: [tk('w1'), tk('s:L')] };
tick(.8, 'near'); out.near.face = [faces(w1, L), faces(L, w1)]; out.near.moved = D(w1, w0);
tick(TALK_SEC + .5, 'near-end');
out.near.after = { talks: [tk('w1'), tk('s:L')], moved: D(w1, w0) };
tick(1, 'near-after'); out.near.after.state = w1.state;

const d1 = byId('d1'), d0 = at('d1'), ds = d1.state;
apply({ type: 'talk', from: 'd1', to: '', terr: tid });
out.lost = { talk: tk('d1'), walking: walking(d1), state: d1.state, state0: ds };
tick(TALK_SEC * .5, 'lost'); out.lost.mid = tk('d1'); out.lost.moved = D(d1, d0);
tick(TALK_SEC * .5 + .4, 'lost'); out.lost.after = tk('d1');
apply({ type: 'talk', from: 'd1', to: 'nobody', terr: tid });
out.lost2 = { talk: tk('d1'), walking: walking(d1) };
tick(TALK_SEC + .4, 'lost2');
apply({ type: 'talk', from: 'nobody', to: 's:L', terr: tid });
tick(.3, 'no-sender'); out.noSender = [tk('s:L'), citizens.filter(c => walking(c)).length];
out.stackBad = stackBad;
__out = out;
}
"""

# T3: the governor as the other one, and as the sender; anyone who needs him calls him back
SCENES["gov"] = r"""
start();
const L = byId('s:L'), H = byId('s:H'), hs = hallStand(T);
const H0 = at('s:H');
apply({ type: 'talk', from: 's:H', to: GOV, terr: tid });
out.toGov = { state: H.state };
out.toGov.trip = until(() => !walking(H) && H.state === 'talking', 14, 'to-gov');
out.toGov.arrive = { d: D(H, g()), talks: [tk('s:H'), tk(GOV)], govAtHall: D(g(), hs) };
tick(.8, 'to-gov'); out.toGov.face = [faces(H, g()), faces(g(), H)];
tick(TALK_SEC + .3, 'to-gov'); out.toGov.after = [tk('s:H'), tk(GOV)];
until(() => !walking(H) && H.state === 'working', 30, 'back'); out.toGov.home = D(H, H0);

out.far0 = D(g(), L);
const L0 = at('s:L');
apply({ type: 'talk', from: GOV, to: 's:L', terr: tid });
out.fromGov = { talk0: tk(GOV) };
out.fromGov.trip = until(() => !!tk(GOV), 16, 'gov-walks');
out.fromGov.arrive = { d: D(g(), L), talks: [tk(GOV), tk('s:L')], leadMoved: D(L, L0), walking: govWalking() };
tick(.8, 'gov-talk'); out.fromGov.face = [faces(g(), L), faces(L, g())];
tick(TALK_SEC + .3, 'gov-talk'); out.fromGov.after = [tk(GOV), tk('s:L')];
out.fromGov.backT = until(() => D(g(), hs) < .05 && !govWalking(), 30, 'gov-back');
out.fromGov.home = D(g(), hs);

apply({ type: 'talk', from: GOV, to: 's:L', terr: tid });
tick(1.2, 'gov-leaves'); out.cut = { away: D(g(), hs) };
apply({ type: 'relay', id: 'w1', to: 'governor', lead: '' });
let talkedToL = 0;
out.cut.t = until(() => byId('w1').state === 'asking', 30, 'summon', () => { const t = tk(GOV); if (t && t.with === 's:L') talkedToL++; });
out.cut.w1 = byId('w1').state; out.cut.govHome = D(g(), hs); out.cut.talkedToL = talkedToL; out.cut.talkL = tk('s:L');
out.stackBad = stackBad;
__out = out;
}
"""

# T3: one talk per person at a time; over TALK_WAIT_MAX waiting -> no walk
SCENES["queue"] = r"""
start();
const L = byId('s:L');
apply({ type: 'talk', from: 'w1', to: 's:L', terr: tid });
apply({ type: 'talk', from: 'w2', to: 's:L', terr: tid });
let both = 0; const seen = {}, withL = {};
tick(40, 'queue', () => {
  const a = tk('w1'), b = tk('w2'), l = tk('s:L');
  if (a && b && a.with === 's:L' && b.with === 's:L') both++;
  if (a && a.with === 's:L') seen.w1 = 1; if (b && b.with === 's:L') seen.w2 = 1; if (l) withL[l.with] = 1;
});
out.two = { both, seen: Object.keys(seen).sort(), withL: Object.keys(withL).sort(), talkL: tk('s:L'),
  home: ['w1', 'w2'].map(id => r3(D(byId(id), byId(id).home))), states: ['w1', 'w2'].map(id => byId(id).state) };

const five = ['w1', 'w2', 'w3', 's:H', 'd1'], pos0 = five.map(at);
for (const id of five) apply({ type: 'talk', from: id, to: 's:L', terr: tid });
out.over = { last0: tk('d1'), lastWalking: walking(byId('d1')) };
let moved = 0; const got = {};
tick(70, 'over', () => {
  moved = Math.max(moved, D(byId('d1'), pos0[4]));
  for (const id of five) { const t = tk(id); if (t && t.with === 's:L') got[id] = 1; }
});
out.over.lastMoved = moved; out.over.got = Object.keys(got).sort(); out.over.talkL = tk('s:L');
out.over.home = five.map((id, i) => r3(D(byId(id), pos0[i])));
out.stackBad = stackBad;
__out = out;
}
"""

# T3: a real status change ends the talk at once (one change per run: __payload.change)
SCENES["status"] = r"""
start();
const L = byId('s:L'), H = byId('s:H'), ch = __payload.change;
const H0 = at('s:H');
out.words = { bg: i18n('status.background'), idle: i18n('status.idle') };
if (ch === 'handover-stuck') {
  apply({ type: 'spawn', id: 'w9', role: 'worker', label: 'worker', task: 'page', terr: tid, lead: 's:L', office: null, from: 's:L' });
  tick(.5, 'handover');
  apply({ type: 'stuck', id: 'w9', tool: 'AskUserQuestion', question: 'which port?' });
  out.now = { state: byId('w9').state, talks: [tk('w9'), tk('s:L')] };
} else {
  apply({ type: 'talk', from: 's:H', to: 's:L', terr: tid });
  if (ch === 'waiting-walker') tick(1, 'walk-over');
  else { out.trip = until(() => !walking(H) && H.state === 'talking', 14, 'walk-over'); tick(.5, 'talk'); }
  out.before = { state: H.state, talks: [tk('s:H'), tk('s:L')] };
  if (ch === 'waiting-walker') apply({ type: 'waiting', id: 's:H' });
  if (ch === 'waiting-other') apply({ type: 'waiting', id: 's:L' });
  if (ch === 'stuck-sender') apply({ type: 'stuck', id: 's:H', tool: 'AskUserQuestion', question: 'which port?' });
  if (ch === 'relay-other') apply({ type: 'relay', id: 's:L', to: 'governor', lead: '' });
  if (ch === 'done-sender') apply({ type: 'done', id: 's:H' });
  if (ch === 'background-other') apply({ type: 'background', id: 's:L' });
  if (ch === 'idle-sender') apply({ type: 'idle', id: 's:H' });
  out.now = { stateH: H.state, stateL: L.state, talks: [tk('s:H'), tk('s:L')], status: [st(H), st(L)] };
  let later = 0;
  tick(45, 'after', () => { if (tk('s:L') && ch !== 'background-other' && ch !== 'idle-sender') later++; });
  out.end = { stateH: H.state, stateL: L.state, home: D(H, H0), talkedLater: later, walking: walking(H) };
}
out.stackBad = stackBad;
__out = out;
}
"""

# T3: a question passed up, and the answer coming back
SCENES["relay"] = r"""
start();
const L = byId('s:L'), w1 = byId('w1');
apply({ type: 'relay', id: 'w1', to: 'lead', lead: 's:L' });
out.walkTalk = tk('w1');
out.t1 = until(() => w1.state === 'at_lead', 30, 'to-lead'); tick(.1, 'at-lead');
out.ask = { talks: [tk('w1'), tk('s:L')], d: D(w1, L) };
tick(.8, 'ask'); out.ask.face = [faces(w1, L), faces(L, w1)];
tick(TALK_SEC + .3, 'ask-end'); out.ask.after = { talks: [tk('w1'), tk('s:L')], state: w1.state, face: faces(w1, L) };
const wAt = at('w1');
apply({ type: 'relay_end', id: 'w1', by: 'lead' });
out.answer = { relay: w1.relay, talks: [tk('w1'), tk('s:L')], walking: walking(w1) };
tick(TALK_SEC * .5, 'answer'); out.answer.mid = { moved: D(w1, wAt), talkL: tk('s:L'), face: [faces(w1, L), faces(L, w1)] };
tick(TALK_SEC * .5 + .4, 'answer-end'); out.answer.after = { talks: [tk('w1'), tk('s:L')] };
until(() => !walking(w1) && w1.state === 'working', 30, 'back'); out.answer.end = { state: w1.state, home: D(w1, w1.home) };

apply({ type: 'relay', id: 's:L', to: 'governor', lead: '' });
out.t2 = until(() => L.state === 'asking', 40, 'to-hall'); tick(.1, 'asking');
out.gask = { talks: [tk('s:L'), tk(GOV)], d: D(L, g()) };
tick(.8, 'gov-ask'); out.gask.face = [faces(L, g()), faces(g(), L)];
tick(TALK_SEC + .3, 'gov-ask-end'); out.gask.after = { talks: [tk('s:L'), tk(GOV)], state: L.state };
const lAt = at('s:L');
apply({ type: 'relay_end', id: 's:L', by: 'governor' });
out.ganswer = { talks: [tk('s:L'), tk(GOV)], walking: walking(L) };
tick(TALK_SEC * .5, 'gov-answer'); out.ganswer.mid = { moved: D(L, lAt), talkG: tk(GOV), face: faces(g(), L) };
tick(TALK_SEC * .5 + .4, 'gov-answer-end'); out.ganswer.after = { talkG: tk(GOV) };
until(() => !walking(L) && (L.state === 'working' || L.state === 'building'), 40, 'lead-back'); out.ganswer.end = L.state;

const w2 = byId('w2'), w3 = byId('w3');
apply({ type: 'relay', id: 'w2', to: 'lead', lead: 's:L' });
until(() => w2.state === 'at_lead', 30, 'w2'); tick(TALK_SEC + .5, 'w2-waits');
apply({ type: 'relay_end', id: 'w2', by: 'timeout' });
out.timeout = { talks: [tk('w2'), tk('s:L')], state: w2.state };
tick(.3, 'timeout'); out.timeout.talksSoon = [tk('w2'), tk('s:L')];
apply({ type: 'relay', id: 'w3', to: 'lead', lead: 's:L' });
tick(.2, 'w3-leaves'); out.onTheWay = { state0: w3.state };
apply({ type: 'relay_end', id: 'w3', by: 'lead' });
out.onTheWay.state = w3.state; out.onTheWay.talks = [tk('w3'), tk('s:L')];
tick(.3, 'w3-back'); out.onTheWay.talksSoon = [tk('w3'), tk('s:L')];
out.stackBad = stackBad;
__out = out;
}
"""

# T3: the owner answered an ask -> the governor tells the one who asked
SCENES["heard"] = r"""
start();
const H = byId('s:H');
apply({ type: 'stuck', id: 's:H', tool: 'AskUserQuestion', question: 'which port?' });
out.t = until(() => H.state === 'asking', 30, 'to-hall');
apply({ type: 'answer', id: 's:H', answer: '4791' });
out.t2 = until(() => H.state === 'heard', 6, 'answer');
tick(.3, 'heard'); out.heard = { state: H.state, talks: [tk('s:H'), tk(GOV)] };
tick(.6, 'heard'); out.face = [faces(H, g()), faces(g(), H)]; out.state = H.state;
out.stackBad = stackBad;
__out = out;
}
"""

# T2: a walker walks around a person who stands on its way
SCENES["around"] = r"""
start();
const H = byId('s:H'), b = byId('d1');
const way = openWay();
out.open = !!way;
if (way) {
  const [A, B] = way, M = { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2 };
  put(H, A); H.home = { x: B.x, y: B.y }; H.stand = H.home; put(b, M);
  tick(.3, 'placed');
  goTo(H, H.home, 'back');
  let minD = 9;
  out.t = until(() => !walking(H) && H.state === 'working', 25, 'around', () => { minD = Math.min(minD, D(H, b)); });
  out.around = { minD, state: H.state, arrived: D(H, B), blockerMoved: D(b, M) };
}
out.stackBad = stackBad;
__out = out;
}
"""

# T2: two walkers head-on on the same way do not walk through each other
SCENES["headon"] = r"""
start();
const H = byId('s:H'), b = byId('d1');
const way = openWay();
out.open = !!way;
if (way) {
  const [A, B] = way;
  put(H, A); H.home = { x: B.x, y: B.y }; H.stand = H.home; put(b, B); b.home = { x: A.x, y: A.y }; b.stand = b.home;
  tick(.3, 'placed');
  goTo(H, H.home, 'back'); goTo(b, b.home, 'back');
  let minD = 9, bothWalked = 0;
  out.t = until(() => !walking(H) && !walking(b) && H.state === 'working' && b.state === 'working', 30, 'head-on',
    () => { if (walking(H) && walking(b)) bothWalked++; minD = Math.min(minD, D(H, b)); });
  out.headOn = { minD, bothWalked, arrived: [D(H, B), D(b, A)] };
}
out.stackBad = stackBad;
__out = out;
}
"""

# T2: a person who leaves does not stand on the governor
SCENES["leave"] = r"""
start();
const d = byId('d1');
leave(d);
let minD = 9, stood = 0;
tick(30, 'leave', () => { if (!d.gone && d.state === 'leaving' && !walking(d)) { stood++; minD = Math.min(minD, D(d, g())); } });
out.leave = { minD, stood, gone: !!d.gone };
out.stackBad = stackBad;
__out = out;
}
"""


class SimCase(unittest.TestCase):
    """Runs one scene of the page simulation on a grown territory (a lead with an office, its three
    workers, a helper session, a deputy, the governor at his hall)."""

    scene = ""
    payload = {}
    _view = None

    @classmethod
    def view(cls):
        if SimCase._view is None:
            SimCase._view = plan_view("meadow", "town")
        return SimCase._view

    @classmethod
    def run_scene(cls, name, **payload):
        return run_sim(PRELUDE + SCENES[name], dict(payload, view=cls.view()), TALK_REQUIRED)

    @classmethod
    def setUpClass(cls):
        if cls.scene:
            cls.r = cls.run_scene(cls.scene, **cls.payload)

    def talk(self, got, kind, other, speaking, icon=None):
        self.assertIsNotNone(got, "in a talk")
        self.assertEqual((got["kind"], got["with"], got["speaking"]), (kind, other, speaking))
        if icon is not None:
            self.assertEqual(got["icon"], icon)
        if not speaking:
            self.assertEqual(got["icon"], "", "only the one who speaks has a bubble")

    def beside(self, d, far=TALK_NEAR):
        self.assertGreaterEqual(d, MIN_GAP - EPS, "never on the other one's spot")
        self.assertLessEqual(d, far + EPS, "next to it")

    def no_stack(self):
        self.assertEqual(self.r["stackBad"], [], "standing people closer than %.2f: [scene, a, b, distance]" % MIN_GAP)


class TestNewAgentAppearsNextToItsSenderT1(SimCase):
    scene = "spawn"

    def test_snapshot_people_get_no_hand_over(self):
        self.assertEqual(self.r["snapTalk"], [None, None, None, None])

    def test_a_worker_appears_next_to_its_lead(self):
        one = self.r["one"]
        self.assertEqual(one["state0"], "handover")
        self.beside(one["d0"])

    def test_the_task_is_handed_over_face_to_face(self):
        one = self.r["one"]
        self.talk(one["talkLead0"], "handover", "w9", True, "📋")
        self.talk(one["talkNew0"], "handover", "s:L", False)
        self.assertEqual(one["face"], [True, True], "the new one and its lead face each other")
        self.assertEqual(one["stateMid"], "handover")
        self.assertLess(one["movedMid"], .01, "the new one stands still during the hand-over")
        self.assertLess(one["leadMoved"], .01, "the sender stays where it is")

    def test_the_new_one_answers_at_the_end(self):
        new, lead = self.r["one"]["reply"]
        self.talk(new, "handover", "s:L", True, "👌")
        self.talk(lead, "handover", "w9", False)

    def test_then_it_walks_to_its_own_spot(self):
        one = self.r["one"]
        self.assertIn(one["after"]["state"], ("to_plot", "working", "building"))
        self.assertEqual(one["after"]["talks"], [None, None], "the hand-over is over after HANDOVER_SEC")
        self.assertEqual(one["end"]["state"], "working")
        self.assertLess(one["end"]["home"], .05, "it ends on its own spot")

    def test_a_deputy_appears_next_to_the_governor(self):
        gov = self.r["gov"]
        self.assertEqual(gov["state0"], "handover")
        self.beside(gov["d0"])
        self.talk(gov["talkGov0"], "handover", "d9", True, "📋")
        self.talk(gov["talkNew0"], "handover", "gov:" + self.view()["territories"][0]["id"], False)
        self.assertEqual(gov["face"], [True, True], "the deputy and the governor face each other")
        self.assertLess(gov["govMoved"], .01, "the governor stays where he is")
        self.assertIsNone(gov["after"]["talkGov"])
        self.assertNotEqual(gov["after"]["state"], "handover")

    def test_a_task_manager_sent_by_the_governor(self):
        tm = self.r["tm"]
        self.assertEqual(tm["state0"], "handover")
        self.beside(tm["d0"])
        self.assertEqual(tm["talkGov0"]["kind"], "handover")
        self.assertNotEqual(tm["after"], "handover")

    def test_a_subagent_of_a_plain_session(self):
        sub = self.r["sub"]
        self.assertEqual(sub["state0"], "handover")
        self.beside(sub["d0"])
        self.talk(sub["talkH0"], "handover", "h1", True, "📋")
        self.assertNotEqual(sub["after"], "handover")

    def test_five_at_once_stand_apart_around_the_sender(self):
        five = self.r["five"]
        self.assertEqual(five["states0"], ["handover"] * 5)
        for d in five["d0"]:
            self.beside(d, 1.6)
        self.assertGreaterEqual(five["minPair0"], MIN_GAP - EPS, "the five never stack on each other")

    def test_five_at_once_get_one_hand_over(self):
        five = self.r["five"]
        self.assertEqual(five["talkLead0"]["kind"], "handover")
        self.assertTrue(five["talkLead0"]["speaking"])
        self.assertEqual(five["statesMid"], ["handover"] * 5)
        self.assertIsNotNone(five["talkLeadLate"])
        self.assertTrue(five["talkLeadLate"]["speaking"], "to several new ones the sender speaks all the time")
        self.assertNotIn("handover", five["after"]["states"])
        self.assertIsNone(five["after"]["talkLead"])
        self.assertEqual(five["end"], ["working"] * 5, "each one reaches its own spot")

    def test_nobody_stacks(self):
        self.no_stack()


class TestNoSenderT1T2(SimCase):
    scene = "nosender"

    def test_without_a_sender_it_spawns_as_before(self):
        self.assertEqual(self.r["states"], ["spawn"] * 3)
        self.assertEqual(self.r["talks"], [None] * 3)
        self.assertIsNone(self.r["govTalk"])
        self.assertEqual(self.r["end"], ["working"] * 3)

    def test_never_on_the_governor_or_on_each_other(self):
        for d in self.r["dGov"]:
            self.assertGreaterEqual(d, MIN_GAP - EPS, "a new one never appears on the governor's spot")
        self.assertGreaterEqual(self.r["minPair"], MIN_GAP - EPS, "three at once never appear on one spot")

    def test_a_governor_who_is_away_sends_nobody(self):
        self.assertEqual(self.r["noGov"], {"state": "spawn", "talk": None})

    def test_nobody_stacks(self):
        self.no_stack()


class TestMessageTalkT3(SimCase):
    scene = "talk"

    def test_setup_is_far_apart(self):
        self.assertGreater(self.r["far0"], TALK_NEAR + .5, "the scene needs the helper far from the lead")

    def test_the_sender_walks_over(self):
        go = self.r["go"]
        self.assertEqual(go["state"], "to_talk")
        self.assertTrue(go["walking"])
        self.assertEqual(go["talks"], [None, None], "no bubble while it walks over")
        self.assertLessEqual(self.r["trip"], TRIP + 2, "there in about TALK_TRIP_MAX_SEC")

    def test_they_talk_face_to_face(self):
        arrive = self.r["arrive"]
        self.assertEqual(arrive["state"], "talking")
        self.beside(arrive["d"])
        self.talk(arrive["talks"][0], "msg", "s:L", True, "💬")
        self.talk(arrive["talks"][1], "msg", "s:H", False)
        self.assertEqual(self.r["face"], [True, True])
        self.assertLess(arrive["leadMoved"], .01, "the other one stays on its spot")

    def test_the_other_one_answers(self):
        sender, other = self.r["reply"]
        self.talk(other, "msg", "s:H", True, "👌")
        self.talk(sender, "msg", "s:L", False)

    def test_then_both_go_back_to_what_they_did(self):
        after, end = self.r["after"], self.r["end"]
        self.assertEqual(after["talks"], [None, None])
        self.assertEqual((after["state"], after["walking"]), ("back", True), "the sender walks back")
        self.assertIn(after["leadState"], ("working", "building"))
        self.assertLess(after["leadMoved"], .01)
        self.assertIn(end["state"], ("working", "building"))
        self.assertLess(end["home"], .05, "the sender ends on its own spot")

    def test_a_talk_never_changes_the_status(self):
        before = self.r["go"]["before"]
        self.assertEqual(self.r["go"]["status"], before, "walking over: both read as before")
        self.assertEqual(self.r["arrive"]["status"], before, "talking: both read as before")

    def test_close_by_nobody_walks(self):
        near = self.r["near"]
        self.assertLessEqual(near["d"], TALK_NEAR)
        self.assertFalse(near["walking"])
        self.talk(near["talks"][0], "msg", "s:L", True, "💬")
        self.talk(near["talks"][1], "msg", "w1", False)
        self.assertEqual(near["face"], [True, True], "both turn to face each other")
        self.assertLess(near["moved"], .01)
        self.assertEqual(near["after"]["talks"], [None, None])
        self.assertLess(near["after"]["moved"], .01)
        self.assertIn(near["after"]["state"], ("working", "building"))

    def test_recipient_not_recognised_the_bubble_on_its_own_spot(self):
        lost = self.r["lost"]
        self.talk(lost["talk"], "msg", "", True, "💬")
        self.assertFalse(lost["walking"])
        self.assertEqual(lost["state"], lost["state0"], "its state does not change")
        self.talk(lost["mid"], "msg", "", True, "💬")
        self.assertLess(lost["moved"], .01)
        self.assertIsNone(lost["after"], "gone after TALK_SEC")
        self.talk(self.r["lost2"]["talk"], "msg", "", True, "💬")
        self.assertFalse(self.r["lost2"]["walking"])

    def test_unknown_sender_does_nothing(self):
        self.assertEqual(self.r["noSender"], [None, 0])

    def test_nobody_stacks(self):
        self.no_stack()


class TestGovernorTalksT3(SimCase):
    scene = "gov"

    def gid(self):
        return "gov:" + self.view()["territories"][0]["id"]

    def test_a_message_to_the_governor(self):
        to = self.r["toGov"]
        self.assertEqual(to["state"], "to_talk")
        self.assertLessEqual(to["trip"], TRIP + 2)
        self.beside(to["arrive"]["d"])
        self.assertLess(to["arrive"]["govAtHall"], .05, "the governor is at his hall stand for it")
        self.talk(to["arrive"]["talks"][0], "msg", self.gid(), True, "💬")
        self.talk(to["arrive"]["talks"][1], "msg", "s:H", False)
        self.assertEqual(to["face"], [True, True])
        self.assertEqual(to["after"], [None, None])
        self.assertLess(to["home"], .05)

    def test_the_governor_walks_over_with_his_message(self):
        fg = self.r["fromGov"]
        self.assertGreater(self.r["far0"], TALK_NEAR + .5, "the scene needs the lead far from the hall")
        self.assertIsNone(fg["talk0"], "no bubble while he walks over")
        self.assertLessEqual(fg["trip"], TRIP + 2.5)
        self.beside(fg["arrive"]["d"])
        self.assertFalse(fg["arrive"]["walking"])
        self.talk(fg["arrive"]["talks"][0], "msg", "s:L", True, "💬")
        self.talk(fg["arrive"]["talks"][1], "msg", self.gid(), False)
        self.assertLess(fg["arrive"]["leadMoved"], .01)
        self.assertEqual(fg["face"], [True, True])
        self.assertEqual(fg["after"], [None, None])

    def test_then_he_goes_back_to_his_hall(self):
        self.assertLess(self.r["fromGov"]["home"], .05)

    def test_someone_who_needs_him_calls_him_back(self):
        cut = self.r["cut"]
        self.assertGreater(cut["away"], .3, "the scene needs him on his way")
        self.assertEqual(cut["w1"], "asking")
        self.assertLess(cut["govHome"], .05, "he is back at his hall stand when the asker arrives")
        self.assertEqual(cut["talkedToL"], 0, "the talk he walked to is dropped")
        self.assertIsNone(cut["talkL"])

    def test_nobody_stacks(self):
        self.no_stack()


class TestOneTalkAtATimeT3(SimCase):
    scene = "queue"

    def test_two_messages_for_one_person_take_turns(self):
        two = self.r["two"]
        self.assertEqual(two["both"], 0, "never two talks with one person at the same time")
        self.assertEqual(two["seen"], ["w1", "w2"], "both get their talk")
        self.assertEqual(two["withL"], ["w1", "w2"])
        self.assertIsNone(two["talkL"])
        self.assertEqual(two["states"], ["working", "working"])
        for d in two["home"]:
            self.assertLess(d, .05, "both end on their own spots")

    def test_over_three_waiting_the_next_one_does_not_walk(self):
        over = self.r["over"]
        self.talk(over["last0"], "msg", "", True, "💬")
        self.assertFalse(over["lastWalking"])
        self.assertLess(over["lastMoved"], .01, "the fifth sender never leaves its spot")
        self.assertEqual(over["got"], ["s:H", "w1", "w2", "w3"], "the first four get their talk, in line")
        self.assertIsNone(over["talkL"])
        for d in over["home"]:
            self.assertLess(d, .05, "everybody ends where it started")

    def test_nobody_stacks(self):
        self.no_stack()


class TestStatusAlwaysWinsT3(SimCase):
    """A talk never hides or delays a real status change."""

    def change(self, name):
        self.r = self.run_scene("status", change=name)
        return self.r

    def test_waiting_while_it_walks_over(self):
        r = self.change("waiting-walker")
        self.assertEqual(r["before"]["state"], "to_talk")
        self.assertEqual(r["now"]["status"][0][0], "you", "等你回话 shows at once")
        self.assertEqual(r["now"]["talks"], [None, None])
        self.assertNotEqual(r["now"]["stateH"], "to_talk", "it stops walking over at once")
        self.assertEqual(r["end"]["talkedLater"], 0, "the talk never happens")
        self.assertLess(r["end"]["home"], .05, "it is back on its own spot")
        self.no_stack()

    def test_waiting_of_the_other_one_ends_the_talk(self):
        r = self.change("waiting-other")
        self.assertIsNotNone(r["before"]["talks"][1], "the scene needs the talk running")
        self.assertEqual(r["now"]["status"][1][0], "you", "等你回话 shows at once")
        self.assertEqual(r["now"]["talks"], [None, None], "the talk ends for both at once")
        self.assertEqual(r["now"]["stateH"], "back", "the sender walks back at once")
        self.assertLess(r["end"]["home"], .05)

    def test_a_stuck_sender_heads_up_the_chain_at_once(self):
        r = self.change("stuck-sender")
        self.assertEqual(r["now"]["stateH"], "to_hall")
        self.assertEqual(r["now"]["talks"], [None, None])
        self.assertEqual(r["end"]["stateH"], "asking")

    def test_a_relay_of_the_other_one_ends_the_talk(self):
        r = self.change("relay-other")
        self.assertEqual(r["now"]["stateL"], "to_hall")
        self.assertEqual(r["now"]["talks"], [None, None])
        self.assertEqual(r["now"]["stateH"], "back")
        self.assertLess(r["end"]["home"], .05)

    def test_done_ends_the_talk_and_it_rests(self):
        r = self.change("done-sender")
        self.assertEqual(r["now"]["talks"], [None, None])
        self.assertIn(r["end"]["stateH"], ("finishing", "to_rest", "resting"))

    def test_background_shows_at_once(self):
        r = self.change("background-other")
        self.assertEqual(r["now"]["status"][1], ["bgrun", r["words"]["bg"]])

    def test_idle_shows_at_once(self):
        r = self.change("idle-sender")
        self.assertEqual(r["now"]["status"][0], ["walk", r["words"]["idle"]])

    def test_a_stuck_newcomer_leaves_the_hand_over_at_once(self):
        r = self.change("handover-stuck")
        self.assertEqual(r["now"]["state"], "to_lead")
        self.assertEqual(r["now"]["talks"], [None, None])


class TestQuestionAndAnswerT3(SimCase):
    scene = "relay"

    def gid(self):
        return "gov:" + self.view()["territories"][0]["id"]

    def test_a_worker_asks_its_lead_face_to_face(self):
        ask = self.r["ask"]
        self.assertIsNone(self.r["walkTalk"], "no bubble while it walks")
        self.beside(ask["d"])
        self.talk(ask["talks"][0], "ask", "s:L", True, "❓")
        self.talk(ask["talks"][1], "ask", "w1", False)
        self.assertEqual(ask["face"], [True, True])
        self.assertEqual(ask["after"]["talks"], [None, None], "the talk is short")
        self.assertEqual(ask["after"]["state"], "at_lead", "it keeps waiting there")
        self.assertTrue(ask["after"]["face"], "and keeps facing its lead")

    def test_the_lead_answers_before_it_walks_back(self):
        ans = self.r["answer"]
        self.assertEqual(ans["relay"], "", "the status follows at once")
        self.talk(ans["talks"][1], "answer", "w1", True, "✅")
        self.talk(ans["talks"][0], "answer", "s:L", False)
        self.assertFalse(ans["walking"])
        self.assertLess(ans["mid"]["moved"], .01, "it listens first")
        self.assertEqual(ans["mid"]["face"], [True, True])
        self.assertEqual(ans["after"]["talks"], [None, None])
        self.assertEqual(ans["end"]["state"], "working")
        self.assertLess(ans["end"]["home"], .05)

    def test_a_lead_asks_the_governor_face_to_face(self):
        ask = self.r["gask"]
        self.beside(ask["d"], 1.3)
        self.talk(ask["talks"][0], "ask", self.gid(), True, "❓")
        self.talk(ask["talks"][1], "ask", "s:L", False)
        self.assertEqual(ask["face"], [True, True], "the governor turns to the one who asks")
        self.assertEqual(ask["after"]["talks"], [None, None])
        self.assertEqual(ask["after"]["state"], "asking")

    def test_the_governor_answers_before_it_walks_back(self):
        ans = self.r["ganswer"]
        self.talk(ans["talks"][1], "answer", "s:L", True, "✅")
        self.talk(ans["talks"][0], "answer", self.gid(), False)
        self.assertFalse(ans["walking"])
        self.assertLess(ans["mid"]["moved"], .01)
        self.assertTrue(ans["mid"]["face"])
        self.assertIsNone(ans["after"]["talkG"])
        self.assertIn(ans["end"], ("working", "building"))

    def test_no_answer_no_talk(self):
        self.assertEqual(self.r["timeout"]["talks"], [None, None])
        self.assertEqual(self.r["timeout"]["talksSoon"], [None, None])
        self.assertEqual(self.r["timeout"]["state"], "back", "a timeout sends it straight back")

    def test_answered_on_the_way_no_talk(self):
        way = self.r["onTheWay"]
        self.assertEqual(way["state0"], "to_lead")
        self.assertEqual(way["state"], "back")
        self.assertEqual(way["talks"], [None, None])
        self.assertEqual(way["talksSoon"], [None, None])

    def test_nobody_stacks(self):
        self.no_stack()


class TestOwnerAnswerT3(SimCase):
    scene = "heard"

    def test_the_governor_tells_the_one_who_asked(self):
        gid = "gov:" + self.view()["territories"][0]["id"]
        self.assertEqual(self.r["heard"]["state"], "heard")
        self.talk(self.r["heard"]["talks"][1], "answer", "s:H", True, "✅")
        self.talk(self.r["heard"]["talks"][0], "answer", gid, False)
        self.assertEqual(self.r["face"], [True, True])
        self.no_stack()


class TestWalkersKeepAGapT2(SimCase):

    def test_a_walker_walks_around_a_standing_person(self):
        r = self.r = self.run_scene("around")
        self.assertTrue(r["open"], "the scene needs open ground with room to pass")
        self.assertEqual(r["around"]["state"], "working", "it still arrives")
        self.assertLess(r["around"]["arrived"], .05)
        self.assertGreaterEqual(r["around"]["minD"], WALK_GAP - EPS, "it never walks through the one who stands on its way")
        self.assertLess(r["around"]["blockerMoved"], .01, "the one who stands is not pushed away")
        self.no_stack()

    def test_two_walkers_head_on_pass_each_other(self):
        r = self.r = self.run_scene("headon")
        self.assertTrue(r["open"], "the scene needs open ground with room to pass")
        self.assertGreater(r["headOn"]["bothWalked"], 5, "the scene needs both walking")
        for d in r["headOn"]["arrived"]:
            self.assertLess(d, .05, "both still arrive")
        self.assertGreaterEqual(r["headOn"]["minD"], WALK_GAP - EPS, "they never walk through each other")

    def test_a_leaving_person_never_stands_on_the_governor(self):
        r = self.r = self.run_scene("leave")
        self.assertGreater(r["leave"]["stood"], 0, "the scene needs it standing at the hall")
        self.assertGreaterEqual(r["leave"]["minD"], MIN_GAP - EPS)


class TestTalkLookT3(unittest.TestCase):
    """The 3D part cannot run here: the bubble and the gesture are wired to talkOf / govTalkOf."""

    def three_d(self):
        text = page()
        return text[text.index("3D view."):]

    def test_css_has_the_talk_bubble(self):
        self.assertRegex(page(), r"\.talkb\s*\{[^}]*border", "a .talkb rule for the small talk bubble")

    def test_each_person_has_a_talk_bubble(self):
        self.assertIn("talkb", function_source("ensureOv") or "", "ensureOv makes the bubble element")
        self.assertIn("talkOf(", function_source("updatePerson") or "", "updatePerson shows it from talkOf(c)")

    def test_the_governor_has_one_too(self):
        self.assertIn("govTalkOf(", self.three_d(), "the governor's bubble comes from govTalkOf(terr)")

    def test_the_speaker_gestures(self):
        self.assertIn(".speaking", self.three_d(), "the one who speaks plays a talk gesture")

    def test_no_chat_text_in_the_bubble(self):
        for fn in ("talkOf", "govTalkOf"):
            src = function_source(fn) or ""
            self.assertTrue(src, fn + " exists")
            for word in ("entries", "last_assistant_message", ".text"):
                self.assertNotIn(word, src, "the bubble is an icon, never chat text")

    def test_no_letter_mode(self):
        self.assertNotIn("letter", (function_source("talkOf") or "") + (function_source("govTalkOf") or ""))


class TestGovernorBubbleAtHisHeadB2(unittest.TestCase):
    """Bounce 2: the governor's talk bubble sits just above his head, like a citizen's."""

    def rows(self, cases):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = {}; vm.createContext(box); vm.runInContext(fns, box);
process.stdout.write(JSON.stringify(cases.map(c => box.govHeadRows(c[0], c[1], c[2]))));
"""
        return run_node(js, {"fns": page_fns("govHeadRows"), "cases": cases})

    def test_the_head_height_is_a_citizens_plus_what_he_is_taller(self):
        m = re.search(r"^const GOV_HEAD_H = ([\d.]+);", page(), re.M)
        self.assertIsNotNone(m, "const GOV_HEAD_H = <height>;")
        self.assertAlmostEqual(float(m.group(1)), .78, delta=.03)

    def test_the_talk_bubble_takes_the_spot_at_his_head(self):
        out = self.rows([[True, False, False], [True, True, False], [True, True, True], [True, False, True]])
        self.assertEqual([r["talk"] for r in out], [0, 0, 0, 0])
        self.assertEqual([r["bub"] for r in out[1:3]], [38, 38], "his speech bubble stands above the talk bubble")
        self.assertEqual([r["qm"] for r in out[2:]], [70, 38], "the ? stands above both")

    def test_without_a_talk_the_old_order_stays(self):
        out = self.rows([[False, True, False], [False, True, True], [False, False, True]])
        self.assertEqual([r["bub"] for r in out[:2]], [0, 0])
        self.assertEqual([r["qm"] for r in out[1:]], [32, 0])

    def test_both_governor_figures_use_them(self):
        for fn in ("updateGovernor", "updateGovPool"):
            with self.subTest(fn=fn):
                src = function_source(fn) or ""
                self.assertRegex(src, r"toScreen\([^)]*GOV_HEAD_H", fn + " takes the head point at GOV_HEAD_H")
                self.assertNotRegex(src, r"toScreen\([^,]+, \.9,", "no head overlay at the old height .9")
                self.assertIn("govHeadRows(", src)


class TestDemoShowsItT1T3(unittest.TestCase):
    """#demo plays hand-overs and talks, so the look can be checked without real sessions."""

    def test_a_demo_person_is_sent_by_the_demo_governor(self):
        self.assertRegex(function_source("spawnDemo") or "", r"'gov:'\s*\+\s*terr")

    def test_only_where_the_demo_draws_a_governor(self):
        # owner-side check 2026-10-01 (headless #demo): a new person in v4-plus / pos-lite stood beside an
        # empty hall and answered 👌 to nobody; the demo draws one governor, in govTerr (governorFigures)
        self.assertRegex(function_source("spawnDemo") or "", r"from:\s*terr === govTerr \? 'gov:'\s*\+\s*terr : ''")

    def test_demo_people_talk_now_and_then(self):
        src = function_source("demoTalkTick") or ""
        self.assertTrue(src, "function demoTalkTick(dt) exists")
        self.assertRegex(src, r"type:\s*'talk'")
        self.assertRegex(src, r"emit\(|apply\(", "through the same path as a live event")
        self.assertRegex(function_source("update") or "", r"if \(DEMO\)[^\n]*demoTalkTick\(dt\)")
        m = re.search(r"^const DEMO_TALK_SEC = ([\d.]+);", page(), re.M)
        self.assertIsNotNone(m, "const DEMO_TALK_SEC = <seconds>;")
        self.assertTrue(6 <= float(m.group(1)) <= 15)


# ---------------------------------------------------------------------------
# Server: who sent a new agent, and who talks to whom
# ---------------------------------------------------------------------------

A_REPO, B_REPO = "/work/ta/app/.git", "/work/tb/shop/.git"
TA, TB = ac.territory_id(A_REPO), ac.territory_id(B_REPO)


def title_line(value, sid):
    return json.dumps({"type": "custom-title", "customTitle": value, "sessionId": sid}) + "\n"


class ServerCase(unittest.TestCase):

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_talk_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.root = os.path.join(self.base, "projects")
        os.makedirs(os.path.join(self.root, "-work-app"))
        self.mains = Mains()
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"), plans=ac.load_plans(),
                               count_fn=lambda i: 6000, balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}},
                               main_fn=self.mains, titles=ac.TitleReader(root=self.root))
        self.client = self.st.add_client()
        self.client.queue.get_nowait()
        self.now = 1000.0

    def named(self, sid, name):
        """A transcript that names session SID."""
        path = os.path.join(self.root, "-work-app", sid + ".jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(title_line(name, sid))
        return path

    def line(self, ev, sid, repo=A_REPO, role="", aid="", at="", tool="", ask="", sub="", desc="", tp="", **more):
        self.now += 1.0
        obj = {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "role": role, "desc": desc,
               "sub": sub, "q": "", "klen": "", "repo": repo, "ask": ask, "wt": "", "file": "", "tp": tp,
               "proj": "shop" if repo == B_REPO else "app"}
        obj.update(more)
        self.st.feed_line(obj, self.now)

    def events(self):
        out = []
        while not self.client.queue.empty():
            raw = self.client.queue.get_nowait()
            if isinstance(raw, bytes) and b"data:" in raw:
                out.append(json.loads(raw.decode("utf-8").split("data:", 1)[1]))
        return out

    def spawn_of(self, cid):
        found = [e for e in self.events() if e.get("type") == "spawn" and e.get("id") == cid]
        self.assertEqual(len(found), 1, "one spawn event for " + cid)
        return found[0]

    def talks(self):
        return [e for e in self.events() if e.get("type") == "talk"]

    def governor(self, sid="g1", repo=A_REPO):
        self.mains.setdefault(repo, sid)
        self.line("UserPromptSubmit", sid, repo)

    def lead(self, sid="tm1", name="city-talk Task Manager", repo=A_REPO):
        self.line("PostToolUse", sid, repo, role="task-manager", tool="Bash", tp=self.named(sid, name))

    def helper(self, sid="h1", name="app Helper", repo=A_REPO):
        self.line("PostToolUse", sid, repo, tool="Bash", tp=self.named(sid, name))

    def sub(self, aid, sid, role="", kind="worker", repo=A_REPO):
        self.line("PreToolUse", sid, repo, role=role, tool="Agent", sub=kind, desc="slice")
        self.line("SubagentStart", sid, repo, role=role, aid=aid, at=kind)

    def send(self, sid, to, repo=A_REPO, role="", aid="", ask="", ev="PostToolUse", **more):
        self.line(ev, sid, repo, role=role, aid=aid, at="worker" if aid else "", tool="SendMessage", ask=ask, to=to,
                  **more)


class TestSpawnSaysWhoSentItT1(ServerCase):

    def test_a_workers_sender_is_its_lead(self):
        self.governor()
        self.lead()
        self.events()
        self.sub("w1", "tm1", role="task-manager")
        self.assertEqual(self.spawn_of("w1")["from"], "s:tm1")

    def test_the_governors_subagent_comes_from_the_governor(self):
        self.governor()
        self.events()
        self.sub("d1", "g1", kind="fast-lane-deputy")
        self.assertEqual(self.spawn_of("d1")["from"], "gov:" + TA)

    def test_a_helpers_subagent_comes_from_the_helper(self):
        self.governor()
        self.helper()
        self.events()
        self.sub("e1", "h1", kind="Explore")
        self.assertEqual(self.spawn_of("e1")["from"], "s:h1")

    def test_a_task_manager_session_comes_from_the_governor(self):
        self.governor()
        self.events()
        self.lead()
        self.assertEqual(self.spawn_of("s:tm1")["from"], "gov:" + TA)

    def test_no_governor_no_sender(self):
        self.lead()
        self.assertEqual(self.spawn_of("s:tm1")["from"], "")

    def test_a_session_the_owner_opened_has_no_sender(self):
        self.governor()
        self.events()
        self.helper()
        self.assertEqual(self.spawn_of("s:h1")["from"], "")

    def test_another_repos_governor_is_not_the_sender(self):
        self.governor("g1", A_REPO)
        self.events()
        self.line("PostToolUse", "tm9", B_REPO, role="task-manager", tool="Bash")
        self.assertEqual(self.spawn_of("s:tm9")["from"], "")


class TestSendMessageBecomesATalkT3(ServerCase):

    def setUp(self):
        super().setUp()
        self.governor()
        self.lead("tm1", "city-talk Task Manager")
        self.lead("tm2", "city-rail Task Manager")
        self.helper("h1", "app Helper")
        self.sub("w1", "tm1", role="task-manager")
        self.events()

    def one(self):
        found = self.talks()
        self.assertEqual(len(found), 1, "one talk event")
        return found[0]

    def test_session_to_session_by_its_name(self):
        self.send("h1", "city-talk Task Manager")
        self.assertEqual(self.one(), {"type": "talk", "from": "s:h1", "to": "s:tm1", "terr": TA})

    def test_the_name_matches_in_any_case(self):
        self.send("tm1", "  CITY-RAIL task manager ", role="task-manager")
        self.assertEqual(self.one()["to"], "s:tm2")

    def test_to_the_governor_by_the_repo_name(self):
        for name in ("app Manager", "app-7f", "app"):
            with self.subTest(to=name):
                self.send("tm2", name, role="task-manager")
                self.assertEqual(self.one(), {"type": "talk", "from": "s:tm2", "to": "gov:" + TA, "terr": TA})

    def test_a_session_name_wins_over_the_repo_name(self):
        self.send("tm1", "app Helper", role="task-manager")
        self.assertEqual(self.one()["to"], "s:h1")

    def test_only_a_whole_repo_name_means_the_governor(self):
        self.send("tm1", "application team", role="task-manager")
        self.assertEqual(self.one()["to"], "")

    def test_from_the_governor(self):
        self.send("g1", "city-rail Task Manager")
        self.assertEqual(self.one(), {"type": "talk", "from": "gov:" + TA, "to": "s:tm2", "terr": TA})

    def test_the_governor_never_talks_to_himself(self):
        self.send("g1", "app Manager")
        self.assertEqual(self.one()["to"], "")

    def test_to_a_subagent_by_its_id(self):
        self.send("tm1", "w1", role="task-manager")
        self.assertEqual(self.one(), {"type": "talk", "from": "s:tm1", "to": "w1", "terr": TA})

    def test_from_a_subagent(self):
        self.send("tm1", "app Helper", role="task-manager", aid="w1")
        self.assertEqual(self.one()["from"], "w1")

    def test_not_recognised_is_an_empty_recipient(self):
        self.send("h1", "somebody else")
        self.assertEqual(self.one(), {"type": "talk", "from": "s:h1", "to": "", "terr": TA})

    def test_another_repos_governor(self):
        self.governor("g2", B_REPO)
        self.events()
        self.send("h1", "shop Manager")
        self.assertEqual(self.one(), {"type": "talk", "from": "s:h1", "to": "gov:" + TB, "terr": TA})

    # bounce 1 (real sessions on pc2, 2026-10-01): the manager's REPLY went out with
    # to = "uds:/tmp/cc-socks/41216.sock" (41216 = the helper's pid), so the answer had no walk-over

    def test_a_reply_to_a_socket_address_means_the_session_with_that_pid(self):
        self.line("PostToolUse", "h1", tool="Bash", pid="41216")
        self.events()
        self.send("g1", "uds:/tmp/cc-socks/41216.sock")
        self.assertEqual(self.one(), {"type": "talk", "from": "gov:" + TA, "to": "s:h1", "terr": TA})

    def test_any_socket_folder(self):
        self.line("PostToolUse", "tm2", role="task-manager", tool="Bash", pid="5150")
        self.events()
        self.send("tm1", "uds:/var/folders/hl/9td/T/cc-socks/5150.sock", role="task-manager")
        self.assertEqual(self.one()["to"], "s:tm2")

    def test_a_socket_address_of_the_governor(self):
        self.line("UserPromptSubmit", "g1", pid=str(os.getpid()))
        self.events()
        self.send("h1", "uds:/tmp/cc-socks/%d.sock" % os.getpid())
        self.assertEqual(self.one(), {"type": "talk", "from": "s:h1", "to": "gov:" + TA, "terr": TA})

    def test_a_socket_address_nobody_has(self):
        self.line("PostToolUse", "h1", tool="Bash", pid="41216")
        self.events()
        for name in ("uds:/tmp/cc-socks/99999.sock", "uds:/tmp/cc-socks/abc.sock", "uds:/tmp/cc-socks/41216.sock.bak",
                     "/tmp/cc-socks/41216.sock", "uds:41216"):
            with self.subTest(to=name):
                self.send("g1", name)
                self.assertEqual(self.one()["to"], "")

    def test_its_own_socket_address_is_nobody(self):
        self.line("PostToolUse", "h1", tool="Bash", pid="41216")
        self.events()
        self.send("h1", "uds:/tmp/cc-socks/41216.sock", pid="41216")
        self.assertEqual(self.one()["to"], "")

    def test_the_latest_pid_of_a_session_counts(self):
        self.line("PostToolUse", "h1", tool="Bash", pid="41216")
        self.line("PostToolUse", "h1", tool="Bash", pid="41300")
        self.events()
        self.send("g1", "uds:/tmp/cc-socks/41216.sock")
        self.assertEqual(self.one()["to"], "", "the old pid is nobody's now")
        self.send("g1", "uds:/tmp/cc-socks/41300.sock")
        self.assertEqual(self.one()["to"], "s:h1")

    def test_a_session_id_means_that_session(self):
        self.send("g1", "h1")
        self.assertEqual(self.one(), {"type": "talk", "from": "gov:" + TA, "to": "s:h1", "terr": TA})
        self.send("tm1", "TM2", role="task-manager")
        self.assertEqual(self.one()["to"], "s:tm2")

    def test_the_governors_session_id_means_the_governor(self):
        self.send("h1", "g1")
        self.assertEqual(self.one(), {"type": "talk", "from": "s:h1", "to": "gov:" + TA, "terr": TA})

    def test_its_own_session_id_is_nobody(self):
        self.send("h1", "h1")
        self.assertEqual(self.one()["to"], "")
        self.send("g1", "g1")
        self.assertEqual(self.one()["to"], "")

    def test_a_session_that_ended_is_nobody(self):
        self.line("PostToolUse", "h1", tool="Bash", pid="41216")
        self.line("SessionEnd", "h1", pid="41216")
        self.events()
        self.send("g1", "uds:/tmp/cc-socks/41216.sock")
        self.assertEqual(self.one()["to"], "")
        self.send("g1", "h1")
        self.assertEqual(self.one()["to"], "")

    def test_old_hook_lines_make_no_talk(self):
        self.line("PostToolUse", "h1", tool="SendMessage")
        self.send("h1", "")
        self.assertEqual(self.talks(), [])

    def test_a_question_is_a_relay_not_a_talk(self):
        self.send("tm1", "app Manager", role="task-manager", ask="q")
        ev = self.events()
        self.assertEqual([e for e in ev if e.get("type") == "talk"], [])
        self.assertEqual([(e["id"], e["to"]) for e in ev if e.get("type") == "relay"], [("s:tm1", "governor")])

    def test_an_answer_that_closes_a_relay_is_no_talk(self):
        self.line("SubagentStop", "tm1", role="task-manager", aid="w1", at="worker", ask="q")
        self.events()
        self.send("tm1", "w1", role="task-manager")
        ev = self.events()
        self.assertEqual([(e["id"], e["by"]) for e in ev if e.get("type") == "relay_end"], [("w1", "lead")])
        self.assertEqual([e for e in ev if e.get("type") == "talk"], [], "relay_end already shows the answer")

    def test_only_post_tool_use(self):
        self.send("h1", "city-talk Task Manager", ev="PreToolUse")
        self.assertEqual(self.talks(), [])

    def test_other_tools_never_talk(self):
        self.line("PostToolUse", "h1", tool="Bash", to="city-talk Task Manager")
        self.assertEqual(self.talks(), [])

    def test_a_talk_is_not_kept_in_the_snapshot(self):
        self.send("h1", "city-talk Task Manager")
        raw = self.st.add_client().queue.get_nowait()
        self.assertNotIn(b'"talk"', raw)


class TestRelayNeverGetsTheRecipient(unittest.TestCase):

    def test_to_wire_drops_it(self):
        line = {"ev": "PostToolUse", "sid": "s1", "aid": "", "at": "", "tool": "SendMessage", "nt": "", "role": "",
                "desc": "", "sub": "", "klen": "", "to": "city-talk Task Manager", "ask": ""}
        wire = relay.to_wire(line, {"rid": "acme/app", "br": "main", "who": "Ann", "dev": "d1"})
        self.assertNotIn("to", wire)
        self.assertNotIn("city-talk Task Manager", json.dumps(wire))


# ---------------------------------------------------------------------------
# Hook: the recipient's name, never the text
# ---------------------------------------------------------------------------

class TestHookSendsTheRecipientT3(unittest.TestCase):

    def setUp(self):
        import test_agent_city_hook as th
        self.th = th
        self.case = th.HookCase("run_hook")
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.case.switch_on()

    def row(self, stdin):
        result = self.case.run_hook(stdin)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.case.lines()
        self.assertTrue(rows, "no line written")
        with open(self.case.events, "rb") as fh:
            return rows[-1], fh.read()

    def send(self, to, message="DONE PASS city-talk\nResult: 12 tests", event="PostToolUse"):
        return self.th.payload(event, tool_name="SendMessage",
                               tool_input={"to": to, "summary": "report", "message": message},
                               tool_response={"success": True, "message": "queued"})

    def test_the_recipient_is_on_the_line(self):
        row, raw = self.row(self.send("city-talk Task Manager"))
        self.assertEqual(row["to"], "city-talk Task Manager")
        self.assertEqual(row["tool"], "SendMessage")
        self.assertNotIn(b"DONE PASS", raw, "never the message")
        self.assertNotIn(b"12 tests", raw)
        self.assertNotIn(b"report", raw, "never the summary")

    def test_the_key_sits_right_before_ask(self):
        row, _ = self.row(self.send("app Manager"))
        self.assertEqual(list(row)[-6:], ["to", "ask", "wt", "file", "tp", "pid"])
        for value in row.values():
            self.assertIsInstance(value, str)

    def test_a_question_carries_no_recipient(self):
        row, raw = self.row(self.send("auto-pipeline-88", "QUESTION: port 4791 or 4777?"))
        self.assertEqual((row["ask"], row["to"]), ("q", ""))
        self.assertNotIn(b"auto-pipeline-88", raw)

    def test_a_long_name_is_cut_to_80(self):
        row, _ = self.row(self.send("n" * 300))
        self.assertEqual(row["to"], "n" * 80)

    def test_a_name_with_quotes_stays_valid_json(self):
        row, _ = self.row(self.send('say "hi" \\ now'))
        self.assertEqual(row["to"], 'say "hi" \\ now')

    def test_a_chinese_name(self):
        row, _ = self.row(self.send("城市 任务经理"))
        self.assertEqual(row["to"], "城市 任务经理")

    def test_only_post_tool_use_send_message(self):
        row, _ = self.row(self.send("city-talk Task Manager", event="PreToolUse"))
        self.assertEqual(row["to"], "")
        row, _ = self.row(self.th.payload("PostToolUse", tool_name="Bash", tool_input={"command": "ls", "to": "x"},
                                          tool_response={"stdout": ""}))
        self.assertEqual(row["to"], "")

    def test_a_message_that_names_a_recipient_inside_its_text_is_not_read(self):
        row, _ = self.row(self.th.payload("PostToolUse", tool_name="SendMessage",
                                          tool_input={"message": 'see "to": "evil"', "summary": "x", "to": "app Helper"},
                                          tool_response={"success": True}))
        self.assertEqual(row["to"], "app Helper")


if __name__ == "__main__":
    unittest.main()
