"""Failing tests for city-ux (owner, 2026-09-28, the live city in Orca's browser, dark theme;
approved mock mock/city-ux-mock.html). U7 (smaller territories) is server layout: see
tests/test_agent_city_ux_layout.py.

CONTRACT (bin/agent-city.html). "sim section" = the page script from 'use strict' up to the
'3D view.' comment: every function named "(sim)" below lives there, needs no three.js and no DOM,
and is driven straight by these tests (tests/test_agent_city_people.py run_sim).

U1 repo tags + zoom-out limit
  (sim) repoTags(view) -> [{id, name, x, z}], one per view.territories entry, in that order: id = t.id,
        name = t.name, x/z = the territory middle in scene coordinates (t.cx - mid.x, t.cz - mid.z,
        mid = { x: Math.round(view.x0 + view.w / 2), z: Math.round(view.z0 + view.h / 2) }, as landState).
  (sim) nearestTerr(tags, x, z) -> the id of the tag nearest to (x, z); null for no tags.
  (sim) let camFly = null; FLY_SEC (0.6 .. 1.2): how long a fly takes.
        flyTo(x, z, dist): camFly = a tween from the camera's tx/tz/dist now to (x, z, dist).
        cameraStep(dt) moves it along with an ease-in-out, done after FLY_SEC (then camFly = null, the
        camera exactly at x/z/dist). It never touches cam.el (the owner's tilt); cam.az keeps only the
        never-stop rotation (autoRotate, unchanged). No jump: one 1/60 s step moves at most 8% of the way.
        stopFly(): camFly = null. dragBy() stops a fly too; so does every other user camera control
        (wheel, pinch, gesture, zoom buttons, pan): each handler calls stopFly().
  (sim) spanDist(span, w, h) -> the camera distance at which `span` tiles fill the stage's shorter side:
        span / (2 * tan(FOV/2) * min(1, w / h)).
  (sim) ZOOM_OUT_TERR (1.5 .. 3): territories across the shorter side at the zoom-out limit.
        zoomCapDist(cell, w, h) = spanDist(ZOOM_OUT_TERR * cell, w, h).
  (sim) capZoom(want, cur, limit, max) -> the new cam.dist for a zoom that wants `want` from `cur`:
        at least DIST_MIN; zooming out never goes past max(limit, cur) nor past max (so a view already
        past the limit -- the All tag -- never jumps in, and zooming in from there works).
  (sim) pullShare(dist, limit, dm) -> 0..1, how far camTarget() draws the look point to the land middle:
        smoothstep k*k*(3-2k), k = clamp((dist - start) / max(1, dm - start), 0, 1), start = FADE_DIST
        when limit >= dm (small land: exactly today's pull), else max(FADE_DIST, limit) (big land: no pull
        until past the limit, so zooming out never slides the view off the repo the owner looks at).
  3D part: distLimit() = Math.min(distMax(), zoomCapDist(map.cell || 26, W, H)); every user zoom
        (wheel/ctrl-wheel, pinch, gesture*, zoomStep buttons) goes through capZoom(..., distLimit(),
        distMax()); dragBy's limit argument is distLimit(); camTarget() uses pullShare(cam.dist,
        distLimit(), distMax()). updateCamera() still clamps to distMax() only.
  Markup: <nav class="repos" id="repos" data-t-aria="aria.repos"> in .app, after header.bar, before
        main (always visible, above the city). renderRepos() fills it: first a
        <button type="button" class="repo all" data-terr="*"> (i18n repo.all: 全部 / All), then one
        <button type="button" class="repo" data-terr="<id>"> per repoTags() entry with the repo name.
        buildLand() calls renderRepos(). Click ($('#repos').addEventListener('click', ...)): "*" -> flyTo(land.cx, land.cz,
        distMax()); a repo -> flyTo(tag.x, tag.z, <a view of that territory, within distLimit()>).
        aria-current="true" on the tag nearest the look point (nearestTerr), or on All while cam.dist >
        distLimit(). New TEXT keys, zh and en both: repo.all, aria.repos, repo.goAria.

  The zoom-out hint (approved mock v3): <div class="cap-hint" id="cap-hint" aria-live="polite" hidden>
        inside #stage; capHint() shows it with i18n cap.hint (zh + en) for about 1.6 s. zoomStep, the wheel
        listener and the gesturechange listener call capHint() when a zoom-out was stopped by the limit.

U2 a click never moves the view
  (sim) TAP_PX (6 .. 12); isDrag(x0, y0, x1, y1) -> true once the pointer is TAP_PX or more away.
  3D part: the pointermove handler uses isDrag(); camLift() treats only a real drag (drag.moved) or a
        pinch as dragging, never a press that has not moved; a 'lostpointercapture' listener and a move
        with no button down (e.buttons === 0) end a press that is still tracked (no stuck drag).

U3 trackpad like a MacBook
  (sim) WHEEL_ZOOM = 0.01. wheelMove(e, h) for a wheel event e = {deltaX, deltaY, deltaMode, ctrlKey}
        (h = page height, the size of one deltaMode 2 page; deltaMode 1 = 16 px a line):
        ctrlKey (a pinch in Chrome/Orca) -> { zoom: Math.exp(clamp(deltaY * unit * WHEEL_ZOOM, -.5, .5)) }
        else (two-finger swipe, and a plain mouse wheel) -> { pan: [deltaX * unit, -deltaY * unit] }
        (fed to panBy, the same px a drag uses; city-ux2 V2, owner 2026-09-29: X was -deltaX and went
        the other way from Y -- see tests/test_agent_city_ux2.py).
  3D part: the wheel listener is on #stage (not only the canvas, so a wheel over a head tag still
        pans), passive:false, and leaves wheels inside .win / .ask-panel alone (the chat log scrolls);
        it uses wheelMove(); zoom -> capZoom(cam.dist * zoom, ...). Safari: gesturestart/gesturechange
        listeners zoom by e.scale (cam.dist = start / scale, through capZoom).

U6 head tags are clickable; a bigger hit area for a person
  (sim) tagPick(el, t, id): el.dataset.pickT = t, el.dataset.pickId = id || ''.
  (sim) pickOfTag(t, id) -> { t:'c', id } | { t:'rg', id } | { t:'gov', terr: id } ({ t:'gov' } for an
        empty id: the home governor) | null for anything else.
  (sim) PICK_PX (20 .. 40); nearestPick(px, py, cands, maxPx) -> the .pick of the cands entry
        ({pick, x, y}, screen px) nearest to (px, py) within maxPx, else null.
  3D part: every name tag and bubble is tagged with tagPick: the citizen's bubble and tag and a remote
        person's device chip (ensureOv), the home governor's govBub and govTag, each pool governor's bub
        and tag (ensureGovFigure), a remote governor's tag (ensureRemoteGovView). CSS: .bub and .tagl get
        pointer-events:auto and cursor:pointer. selectPick(pk) = exactly what a tap on that person does
        (selected = pk, winLog = false, the panel re-rendered); endPointer's tap branch calls it and so
        does an #ov click on a [data-pick-t] element. pickAt() falls back to nearestPick() with PICK_PX
        over the people and governors on screen when the ray hits no person. Hover keeps working over a
        tag: #ov 'pointerover' on a tag sets hovered to its pick, and the canvas 'pointerleave' does not
        clear hovered when e.relatedTarget is such a tag (no flicker).

U4 the governor window says less
  TEXT has no gov.presentNote, dt.dispatched, dt.answered (either language); the page never says
  总督就是你正在聊的主对话; the governor branch of renderDetail has no d-tools box. gov.awayNote stays.

U5 the governor window: two columns, the conversation on the right
  renderDetail's governor branch: <div class="gov-cols"> with <div class="gov-side"> (the team list, see
  U11) and <div class="gov-chat"> (the compact header, the conversation #chat, the #say form). renderWin() toggles
  class "wide" on #win while the governor is selected. CSS: .win.wide is wider (min(...px, ...)) and full
  height (height: calc(100% - 24px)); .gov-cols is a two-column grid; .gov-chat .chat has no fixed
  max-height (it fills the column). The @media (max-width: 960px) block stacks it (.gov-cols one column,
  a .win.wide rule).

U8 the chat log never yanks the owner down
  (sim) CHAT_STICK_PX = 40. chatScroll(prev, next) -> { top, chip }: prev = null (first time this chat
  is shown) or {top, height, client} of the log before the update; next = {height, client} after it.
  prev null, or prev within CHAT_STICK_PX of its bottom -> { top: max(0, next.height - next.client),
  chip:false }; else -> { top: prev.top, chip: next.height > prev.height }.
  3D part: renderDetail uses chatScroll() both when it refreshes the log and when it rebuilds the card
  (the same chat keeps its place); a <button type="button" class="newmsg"> (i18n chat.new, zh + en)
  shows while chip, a click scrolls to the bottom and hides it, and it hides once the owner scrolls
  back within CHAT_STICK_PX of the bottom.

U9 chat text: simple markdown, safe
  (sim) mdLite(text) -> HTML, self-contained (its own escaping; no three.js, no DOM): drops every
  <!-- ... --> (an unclosed one to the end); escapes & < > " first; then paragraphs (blank line),
  - / * lists (<ul><li>), 1. lists (<ol><li>), ```fenced``` blocks (<pre><code>, nothing formatted
  inside), `code` (<code>), **bold** (<b> or <strong>), and simple | tables | with a |---| line
  (<table>, <th>, <td>). No links, no images, no raw HTML ever. chatHtml() renders every message's
  text through mdLite inside an element with class "md"; CSS styles .md tables, code and lists.

U10 every person opens the same two-column window, with its history (owner, mock v2 5ebd055)
  (sim) ACT_KEEP = 60. Every citizen has c.acts = [] (newCitizen): its activity lines, oldest first.
        actLog(c, text): appends { at: Date.now() / 1000, text }, keeps only the last ACT_KEEP.
        actTool(c, tool): when the last line is a tools line (it has .tools), counts the tool there and
        rewrites its text; else appends a new tools line { at, tools: {tool: 1}, text }. A tools line's
        text is "<tool> ×<n>" per tool, in the order first used, joined by " · " ("Edit ×2 · Read ×1").
        apply() records, for the event's citizen: spawn -> hist.started {task}; tool -> actTool; stuck
        -> hist.stuck {text: stuckText(ev)}; relay -> hist.toLead (to 'lead') or hist.toGov; waiting ->
        hist.waiting; done -> hist.done; leave -> hist.left (remote people get their spawn / done / leave
        lines the same way). giveAnswer() stores { q, a, at: Date.now() / 1000 } in c.qa.
  (sim) personHistory(c, entries) -> one list, oldest first (a stable sort by .at): every c.acts line
        {k:'act', at, text}, every c.qa {k:'ask', q, a, at}, every chat entry (prompt / reply / owner)
        {k: entry.kind, text, at, state}, and last of all, while c.stuck, the open question
        {k:'ask', q: c.question, a: null}.
  (sim) historyHtml(items, name, busy) -> the <li> rows of the history list: 'act' -> <li class="act">
        with <time> (HH:MM) and the escaped text; 'ask' -> <li class="qa"> with label.ask + the escaped
        question and label.answer + the escaped answer, or label.awaitingAnswer while a is null; a message
        -> <li class="msg" data-kind="..."> as chatHtml() makes it (text through mdLite, class "md"; a
        subagent's prompt is labelled chat.task); no items -> <li class="msg-empty"> hist.empty.
  3D part: renderWin() makes the window wide for every person: selected.t 'c' (local or remote) and
        'gov' (a building, a site and a remote governor stay narrow).

U11 one window for the whole team (owner, mock v3): the left column never changes
  (sim) esc moves into the sim section (same function). teamListHtml(terr, sel) -> the team list of
        territory terr, exactly rosterGroups()'s group for it: one <button type="button" class="row"
        data-sel="<row id>" aria-current="true|false"> per row, in order (the governor first,
        data-sel="gov:<terr>"; depth-1 rows inside <li class="sub">), aria-current="true" on the row of
        sel only (a governor selection with no terr is the home governor, govTerr); rows look as the
        governor window's rows do today (dot, name, sub line, state pill). After the group's rows, always,
        one row per other member's person standing in that territory (c.remote, not gone), so the list is
        the same whoever is selected (headless E2E: a remote person used to appear only while selected).
  winTitle(): for a person (selected.t 'c' or 'gov') the team window's title, i18n('team.title', {repo:
        that territory's name}) (zh '{repo} · 团队', en '{repo} · Team'): the same whoever is selected.
  renderDetail(): for a governor and for a citizen, <div class="gov-cols"> with <div class="gov-side">
        = hint.team + teamListHtml(the person's territory, selected) and nothing else, and
        <div class="gov-chat"> = a compact header <div class="p-head"> (dot, name, state pill, one line
        of facts: repo · branch · doing for a citizen, repo · gov.ownTag for the governor (its pill the
        same words as its list row, govRowText), the away note for an away governor, a thin
        progress bar for a citizen), then hint hist.title, the #chat list (the governor: its
        conversation; a citizen: historyHtml(personHistory(c, chat entries))), the .newmsg chip, then
        the #say form for a session or the governor, or the read-only hint + find-lead button for a
        subagent. A row click (data-sel) only changes `selected`: the list stays, the right side
        switches. The demo actions (#demo only) go under the header.

U12 no tool counters: renderDetail shows no Edit / Write / Bash / Read boxes (no d-tools anywhere in it)
        and no longer updates them.

  New TEXT keys, zh and en: hist.title, hist.empty, hist.started, hist.stuck, hist.toLead, hist.toGov,
        hist.waiting, hist.done, hist.left, chat.task.

U13 a building shows one meaningful name (owner, 2026-09-28; no new mock, main manager approved by text)
  (sim) buildingName(b) -> one name, never a file path, never the builder:
        1. b.name, when it is not empty and not path-like (no / or \\, no ".ext" end);
        2. else b.task, when it is not empty, not path-like, not b.by and not a bare role word
           (worker, task-manager, fast-lane-deputy, merge-deputy, other);
        3. else i18n('building.module', {name}) with name = the module the files point at: per file the
           last part's stem (extension dropped; a test_ prefix or _test/.test/.spec suffix dropped); a
           generic stem (index, main, __init__, init, mod, app, util, utils, readme, test, tests, spec,
           setup, conftest) gives its folder name instead (a generic folder: src, lib, test, tests, bin,
           app, pkg, internal, cmd, or none -> that file gives nothing); the most frequent wins, a tie ->
           the earliest file;
        4. else the type word, i18n('type.' + b.type).
        newBuildingRecord keeps task: ev.task || ''. The 'build' case hands the builder's task on:
        owner.pendingBuild gets task: owner.task (so the record made on arrival has it).
        bldLabel(b) and buildingInfo(b).name use buildingName(b).
  renderDetail's building branch: the head shows buildingName and one line with the type word (and its
        district); no quality pill, no level, no files list, no builders list (no hint.files / hint.history,
        no .files / .hist in that branch). New TEXT key building.module, zh '{name} 模块', en '{name} module'.

Run: python3 -m unittest tests.test_agent_city_ux_page </dev/null
"""

import math
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import function_source, page, run_sim, sim_section  # noqa: E402
from test_agent_city_chain import two_territory_view  # noqa: E402

FOV = 40
DIST_MIN = 2.5
FADE_DIST = 12


def sim_has(name):
    return re.search(r"(?:function\s+%s\s*\(|(?:const|let)\s+%s\s*=)" % (re.escape(name), re.escape(name)),
                     sim_section()) is not None


def listener_block(target_regex, event):
    """Every `<target>.addEventListener('<event>', ...)` call in the page, each up to its matching ')',
    joined (None when there is none)."""
    text, out = page(), []
    for m in re.finditer(r"(?<![\w$])%s\.addEventListener\(\s*'%s'" % (target_regex, re.escape(event)), text):
        depth = 0
        for j in range(m.start() + m.group(0).index("addEventListener(") + len("addEventListener"), len(text)):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    out.append(text[m.start():j + 1])
                    break
    return "\n".join(out) if out else None


def css():
    text = page()
    return re.sub(r"/\*.*?\*/", "", text[text.index("<style>"):text.index("</style>")], flags=re.S)


def media_960():
    c = css()
    i = c.index("@media (max-width: 960px)")
    depth = 0
    for j in range(c.index("{", i), len(c)):
        if c[j] == "{":
            depth += 1
        elif c[j] == "}":
            depth -= 1
            if depth == 0:
                return c[i:j + 1]
    return ""


def rule(sel, text=None):
    """Every declaration block whose selector list names exactly this selector, joined."""
    text = css() if text is None else text
    out = []
    for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", text):
        if sel in [x.strip() for x in m.group(1).split(",")]:
            out.append(m.group(2))
    return ";".join(out)


def tracks(value):
    """The number of grid tracks in a grid-template-columns value (parens kept together)."""
    depth, n, cur = 0, 0, ""
    for ch in value.strip() + " ":
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch.isspace() and depth == 0:
            if cur:
                n += 1
            cur = ""
        else:
            cur += ch
    return n


def columns(block):
    m = re.search(r"grid-template-columns:([^;]*)", block)
    return tracks(m.group(1)) if m else 0


def text_keys(key):
    return len(re.findall(r"'%s'\s*:" % re.escape(key), page()))


# ---------------------------------------------------------------------------
# U1: repo tags, the fly, the zoom-out limit
# ---------------------------------------------------------------------------

U1_DRIVER = r"""
const V = __payload.view;
const tags = repoTags(V);
const out = { tags, empty: nearestTerr([], 0, 0) };
out.near = [nearestTerr(tags, tags[0].x + 1, tags[0].z - 1), nearestTerr(tags, tags[1].x - 2, tags[1].z + 1)];
// the fly
cam.az = 1; cam.el = 0.7; cam.dist = 5; cam.tx = 0; cam.tz = 0;
const az0 = cam.az, dir = autoRotDir;
flyTo(tags[1].x, tags[1].z, 14);
out.started = !!camFly;
const total = Math.hypot(tags[1].x, tags[1].z);
let maxStep = 0, els = new Set(), steps = 0, doneAt = -1, prev = [cam.tx, cam.tz], mono = true, lastD = Infinity;
for (let i = 0; i < 150; i++) {
  cameraStep(1 / 60); steps++;
  const d = Math.hypot(cam.tx - tags[1].x, cam.tz - tags[1].z);
  if (d > lastD + 1e-9) mono = false; lastD = d;
  maxStep = Math.max(maxStep, Math.hypot(cam.tx - prev[0], cam.tz - prev[1])); prev = [cam.tx, cam.tz];
  els.add(cam.el.toFixed(9));
  if (doneAt < 0 && camFly === null) doneAt = steps;
}
out.fly = { tx: cam.tx, tz: cam.tz, dist: cam.dist, els: [...els], maxStep, total, doneAt, mono,
  azMoved: cam.az - az0, azWant: 150 * dir * (1 / 60) * Math.PI * 2 / AUTO_ROT_SEC, flySec: FLY_SEC };
// a drag stops a fly
cam.tx = 0; cam.tz = 0; cam.dist = 5;
flyTo(10, 10, 12); cameraStep(1 / 60); cameraStep(1 / 60);
dragBy(4, 0);
const a = [cam.tx, cam.tz, cam.dist];
for (let i = 0; i < 40; i++) cameraStep(1 / 60);
out.drag = { fly: camFly, a, b: [cam.tx, cam.tz, cam.dist] };
flyTo(3, 3, 9); stopFly(); out.stopped = camFly;
// zoom-out limit maths
out.span = [spanDist(50, 1200, 800), spanDist(100, 1200, 800), spanDist(50, 400, 800)];
out.terr = ZOOM_OUT_TERR;
out.capd = [zoomCapDist(20, 1200, 800), spanDist(ZOOM_OUT_TERR * 20, 1200, 800)];
out.cap = [capZoom(3, 10, 40, 100), capZoom(1, 10, 40, 100), capZoom(30, 10, 40, 100), capZoom(60, 10, 40, 100),
  capZoom(120, 90, 40, 100), capZoom(80, 90, 40, 100), capZoom(60, 10, 40, 30), capZoom(45, 40, 40, 100)];
out.pull = { small: [10, 20, 25, 30].map(d => pullShare(d, 50, 30)),
  big: [20, 40, 70, 100, 130].map(d => pullShare(d, 40, 100)), low: pullShare(12, 5, 100), fade: FADE_DIST };
__out = out;
"""

U1_REQUIRED = ("repoTags", "nearestTerr", "flyTo", "stopFly", "camFly", "FLY_SEC", "cameraStep", "cam", "dragBy",
               "autoRotDir", "AUTO_ROT_SEC", "spanDist", "ZOOM_OUT_TERR", "zoomCapDist", "capZoom", "pullShare",
               "FADE_DIST")


class TestRepoTagsAndFly(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.view = two_territory_view()
        cls.r = run_sim(U1_DRIVER, {"view": cls.view}, U1_REQUIRED)

    def test_one_tag_per_territory_in_order(self):
        v = self.view
        mx, mz = math.floor(v["x0"] + v["w"] / 2 + .5), math.floor(v["z0"] + v["h"] / 2 + .5)
        want = [{"id": t["id"], "name": t["name"], "x": t["cx"] - mx, "z": t["cz"] - mz} for t in v["territories"]]
        got = [{k: tag[k] for k in ("id", "name", "x", "z")} for tag in self.r["tags"]]
        self.assertEqual(got, want)

    def test_nearest_territory(self):
        ids = [t["id"] for t in self.r["tags"]]
        self.assertEqual(self.r["near"], ids[:2])
        self.assertIsNone(self.r["empty"])

    def test_fly_lands_exactly_and_ends(self):
        f, tag = self.r["fly"], self.r["tags"][1]
        self.assertTrue(self.r["started"], "flyTo sets camFly")
        self.assertAlmostEqual(f["tx"], tag["x"], places=6)
        self.assertAlmostEqual(f["tz"], tag["z"], places=6)
        self.assertAlmostEqual(f["dist"], 14, places=6)
        self.assertTrue(.6 <= f["flySec"] <= 1.2, f["flySec"])
        self.assertGreater(f["doneAt"], 0, "camFly goes back to null when the fly is done")
        self.assertLessEqual(f["doneAt"], math.ceil(f["flySec"] * 60) + 2)

    def test_fly_is_smooth_and_keeps_the_tilt(self):
        f = self.r["fly"]
        self.assertEqual(len(f["els"]), 1, "the owner's tilt (cam.el) never changes during a fly")
        self.assertTrue(f["mono"], "the fly only ever gets closer")
        self.assertLessEqual(f["maxStep"], .08 * f["total"], "no jump: one frame moves at most 8% of the way")
        self.assertAlmostEqual(f["azMoved"], f["azWant"], places=6, msg="the angle only moves by the never-stop rotation")

    def test_a_drag_or_stopfly_ends_the_fly(self):
        d = self.r["drag"]
        self.assertIsNone(d["fly"], "dragBy stops a fly")
        for a, b in zip(d["a"], d["b"]):
            self.assertAlmostEqual(a, b, places=9)
        self.assertIsNone(self.r["stopped"])

    def test_span_distance(self):
        t = math.tan(FOV * math.pi / 360)
        s = self.r["span"]
        self.assertAlmostEqual(s[0], 50 / (2 * t), places=6)
        self.assertAlmostEqual(s[1], 2 * s[0], places=6)
        self.assertAlmostEqual(s[2], 50 / (2 * t * .5), places=6, msg="a tall stage: the width is the short side")
        self.assertTrue(1.5 <= self.r["terr"] <= 3, self.r["terr"])
        self.assertAlmostEqual(self.r["capd"][0], self.r["capd"][1], places=6)

    def test_cap_zoom(self):
        self.assertEqual(self.r["cap"], [3, DIST_MIN, 30, 40, 90, 80, 30, 40])

    def test_pull_share(self):
        p = self.r["pull"]
        self.assertEqual(p["fade"], FADE_DIST)

        def smooth(d, start, dm):
            k = min(1, max(0, (d - start) / max(1, dm - start)))
            return k * k * (3 - 2 * k)
        for d, got in zip([10, 20, 25, 30], p["small"]):
            self.assertAlmostEqual(got, smooth(d, FADE_DIST, 30), places=9, msg="small land: today's pull, d=%s" % d)
        for d, got in zip([20, 40, 70, 100, 130], p["big"]):
            self.assertAlmostEqual(got, smooth(d, 40, 100), places=9, msg="big land: no pull before the limit, d=%s" % d)
        self.assertAlmostEqual(p["low"], smooth(12, FADE_DIST, 100), places=9)


class TestRepoTagsWiring(unittest.TestCase):

    def test_tag_row_markup(self):
        text = page()
        m = re.search(r'<nav\b[^>]*\bid="repos"[^>]*>', text)
        self.assertIsNotNone(m, '<nav id="repos"> missing')
        self.assertIn('class="repos"', m.group(0))
        self.assertIn('data-t-aria="aria.repos"', m.group(0))
        self.assertLess(text.index("</header>"), m.start(), "under the top bar")
        self.assertLess(m.start(), text.index('<main class="layout">'), "above the city")

    def test_text_keys_both_languages(self):
        for key in ("repo.all", "aria.repos", "repo.goAria"):
            self.assertEqual(text_keys(key), 2, key)
        self.assertIn("'repo.all': '全部'", page())
        self.assertIn("'repo.all': 'All'", page())

    def test_render_repos(self):
        src = function_source("renderRepos")
        self.assertIsNotNone(src, "renderRepos() missing")
        self.assertIn("repoTags(", src)
        self.assertIn('data-terr="*"', src)
        self.assertIn("repo.all", src)
        self.assertIn("renderRepos(", function_source("buildLand") or "", "buildLand() calls renderRepos()")

    def test_clicks_fly(self):
        block = listener_block(r"\$\('#repos'\)", "click")
        self.assertIsNotNone(block, "$('#repos').addEventListener('click', ...) missing")
        self.assertIn("flyTo(", block)
        self.assertIn("distMax()", block, "All flies out to the whole land")
        self.assertIn("distLimit()", block, "a repo view stays within the zoom-out limit")

    def test_every_user_zoom_goes_through_the_limit(self):
        self.assertIsNotNone(function_source("distLimit"), "distLimit() missing")
        self.assertIn("zoomCapDist(", function_source("distLimit"))
        self.assertIn("distMax()", function_source("distLimit"))
        self.assertIn("capZoom(", function_source("zoomStep") or "")
        self.assertIn("distLimit()", function_source("zoomStep") or "")
        self.assertIn("pullShare(", function_source("camTarget") or "")
        move = listener_block(r"canvas", "pointermove") or ""
        self.assertIn("capZoom(", move, "pinch goes through capZoom")
        self.assertIn("dragBy(dx, dy, distLimit())", move)
        self.assertIn("distMax()", function_source("updateCamera") or "")

    def test_zoom_out_hint(self):
        self.assertEqual(text_keys("cap.hint"), 2)
        self.assertRegex(page(), r'<div class="cap-hint" id="cap-hint"[^>]*hidden')
        self.assertIsNotNone(function_source("capHint"), "capHint() missing")
        self.assertIn("capHint(", function_source("zoomStep") or "")
        self.assertIn("capHint(", listener_block(r"(?:stage|\$\('#stage'\))", "wheel") or "")
        self.assertIn("capHint(", listener_block(r"(?:stage|\$\('#stage'\)|canvas)", "gesturechange") or "")

    def test_user_controls_stop_a_fly(self):
        for name in ("zoomStep", "panBy"):
            self.assertIn("stopFly()", function_source(name) or "", name)
        drag = function_source("dragBy") or ""
        self.assertTrue("stopFly()" in drag or "camFly = null" in drag, "dragBy stops a fly")


# ---------------------------------------------------------------------------
# U2 + U3: a click never moves the view; the trackpad
# ---------------------------------------------------------------------------

INPUT_DRIVER = r"""
const out = { tap: TAP_PX, k: WHEEL_ZOOM };
out.drag = [isDrag(0, 0, TAP_PX - .5, 0), isDrag(0, 0, 0, TAP_PX), isDrag(10, 10, 13, 14), isDrag(0, 0, 30, 0)];
const W = (dx, dy, mode, ctrl) => wheelMove({ deltaX: dx, deltaY: dy, deltaMode: mode, ctrlKey: ctrl }, 900);
out.pan = [W(0, 10, 0, false), W(-6, 4, 0, false), W(0, 3, 1, false), W(2, 1, 2, false)];
out.zoom = [W(0, -10, 0, true), W(0, 20, 0, true), W(0, 40, 0, true), W(0, 1000, 0, true), W(0, -1000, 0, true), W(0, 2, 1, true)];
__out = out;
"""


class TestTapAndTrackpad(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(INPUT_DRIVER, {}, ("TAP_PX", "isDrag", "WHEEL_ZOOM", "wheelMove"))

    def test_tap_threshold(self):
        self.assertTrue(6 <= self.r["tap"] <= 12, self.r["tap"])
        self.assertEqual(self.r["drag"], [False, True, False, True])

    def test_two_finger_swipe_pans_with_the_fingers(self):
        p = self.r["pan"]
        for got, want in zip(p, [[0, -10], [-6, -4], [0, -48], [1800, -900]]):  # city-ux2 V2: X no longer negated
            self.assertIn("pan", got)
            self.assertNotIn("zoom", got)
            self.assertAlmostEqual(got["pan"][0], want[0], places=9)
            self.assertAlmostEqual(got["pan"][1], want[1], places=9)

    def test_pinch_zooms_proportionally_without_jumps(self):
        z = [x.get("zoom") for x in self.r["zoom"]]
        self.assertEqual(self.r["k"], .01)
        self.assertAlmostEqual(z[0], math.exp(-.1), places=9, msg="pinch out (deltaY < 0) zooms in: a smaller distance")
        self.assertAlmostEqual(z[1], math.exp(.2), places=9)
        self.assertAlmostEqual(z[2], z[1] ** 2, places=9, msg="twice the fingers, twice the zoom (in log)")
        self.assertAlmostEqual(z[3], math.exp(.5), places=9, msg="one event never jumps: clamped")
        self.assertAlmostEqual(z[4], math.exp(-.5), places=9)
        self.assertAlmostEqual(z[5], math.exp(.32), places=9, msg="deltaMode 1 = 16 px a line")
        for x in self.r["zoom"]:
            self.assertNotIn("pan", x)


class TestInputWiring(unittest.TestCase):

    def test_press_without_move_does_not_lift(self):
        src = function_source("camLift") or ""
        self.assertIn("drag.moved", src, "only a real drag counts as dragging in camLift")
        self.assertNotRegex(src, r"\(\s*drag\s*\|\|", "a bare press (drag set, not moved) must not change the lift")

    def test_pointer_handlers(self):
        move = listener_block(r"canvas", "pointermove") or ""
        self.assertIn("isDrag(", move)
        self.assertGreaterEqual(move.count("buttons === 0"), 2, "hover, and a tracked press with no button down any more")
        self.assertIn("addEventListener('lostpointercapture'", page())

    def test_wheel_on_the_stage(self):
        block = listener_block(r"(?:stage|\$\('#stage'\))", "wheel")
        self.assertIsNotNone(block, "the wheel listener sits on #stage")
        for bit in ("wheelMove(", "panBy(", "capZoom(", "distLimit()", "passive:", "stopFly()", ".win", ".ask-panel", "preventDefault"):
            self.assertIn(bit, block, bit)
        self.assertIsNone(listener_block(r"canvas", "wheel"), "no second wheel listener on the canvas")

    def test_safari_gestures(self):
        for ev in ("gesturestart", "gesturechange"):
            block = listener_block(r"(?:stage|\$\('#stage'\)|canvas)", ev)
            self.assertIsNotNone(block, ev)
            self.assertIn("preventDefault", block)
        self.assertIn(".scale", listener_block(r"(?:stage|\$\('#stage'\)|canvas)", "gesturechange"))
        self.assertIn("capZoom(", listener_block(r"(?:stage|\$\('#stage'\)|canvas)", "gesturechange"))


# ---------------------------------------------------------------------------
# U6: clickable head tags, a bigger hit area
# ---------------------------------------------------------------------------

U6_DRIVER = r"""
const el = { dataset: {} }, el2 = { dataset: {} };
tagPick(el, 'c', 'abc'); tagPick(el2, 'gov');
const cands = [{ pick: { t: 'c', id: 'a' }, x: 100, y: 100 }, { pick: { t: 'c', id: 'b' }, x: 130, y: 100 }, { pick: { t: 'gov' }, x: 400, y: 400 }];
__out = { el: el.dataset, el2: el2.dataset, px: PICK_PX,
  picks: [pickOfTag('c', 'x1'), pickOfTag('rg', 'r1'), pickOfTag('gov', 'T'), pickOfTag('gov', ''), pickOfTag('b', '3'), pickOfTag('', '')],
  near: [nearestPick(112, 100, cands, 28), nearestPick(118, 100, cands, 28), nearestPick(100, 140, cands, 28),
    nearestPick(380, 400, cands, 28), nearestPick(250, 250, cands, 28), nearestPick(0, 0, [], 28)] };
"""


class TestTagPicks(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(U6_DRIVER, {}, ("tagPick", "pickOfTag", "PICK_PX", "nearestPick"))

    def test_tag_pick(self):
        self.assertEqual(self.r["el"], {"pickT": "c", "pickId": "abc"})
        self.assertEqual(self.r["el2"], {"pickT": "gov", "pickId": ""})

    def test_pick_of_tag(self):
        self.assertEqual(self.r["picks"], [{"t": "c", "id": "x1"}, {"t": "rg", "id": "r1"}, {"t": "gov", "terr": "T"},
                                           {"t": "gov"}, None, None])

    def test_nearest_pick(self):
        self.assertTrue(20 <= self.r["px"] <= 40, self.r["px"])
        self.assertEqual(self.r["near"], [{"t": "c", "id": "a"}, {"t": "c", "id": "b"}, None, {"t": "gov"}, None, None])


class TestTagWiring(unittest.TestCase):

    def test_every_tag_and_bubble_is_tagged(self):
        for name in ("ensureOv", "ensureGovFigure", "ensureRemoteGovView"):
            self.assertIn("tagPick(", function_source(name) or "", name)
        src = function_source("ensureOv")
        for bit in ("c.o.bub", "c.o.tag", "c.o.rdev"):
            self.assertRegex(src, r"tagPick\(\s*%s\b" % re.escape(bit), bit)
        text = page()
        self.assertRegex(text, r"tagPick\(\s*govBub\b")
        self.assertRegex(text, r"tagPick\(\s*govTag\b")
        for bit in ("bub", "tag"):
            self.assertRegex(function_source("ensureGovFigure"), r"tagPick\(\s*%s\b" % bit)
        self.assertRegex(function_source("ensureRemoteGovView"), r"tagPick\(\s*tag\b")

    def test_tags_take_clicks(self):
        for sel in (".bub", ".tagl", ".rdev"):
            r = rule(sel)
            self.assertIn("pointer-events:auto", r.replace(" ", ""), sel)
            self.assertIn("cursor:pointer", r.replace(" ", ""), sel)

    def test_one_select_path(self):
        self.assertIsNotNone(function_source("selectPick"), "selectPick() missing")
        self.assertIn("selectPick(", function_source("endPointer") or "")
        block = listener_block(r"ovRoot", "click") or ""
        self.assertIn("data-pick-t", block)
        self.assertIn("pickOfTag(", block)
        self.assertIn("selectPick(", block)
        self.assertIn("data-open", block, "the red ? still opens the answer panel")

    def test_bigger_hit_area(self):
        src = function_source("pickAt") or ""
        self.assertIn("nearestPick(", src)
        self.assertIn("PICK_PX", src)

    def test_hover_over_a_tag_does_not_flicker(self):
        self.assertIsNotNone(listener_block(r"ovRoot", "pointerover"), "#ov pointerover keeps the hover")
        leave = listener_block(r"canvas", "pointerleave") or ""
        self.assertIn("relatedTarget", leave)


# ---------------------------------------------------------------------------
# U4 + U5: the governor window
# ---------------------------------------------------------------------------

def gov_branch():
    src = function_source("renderDetail") or ""
    i = src.find("selected.t === 'gov') {")
    j = src.find("} else if (!DEMO && citizens.length === 0)", i)
    return src[i:j] if i >= 0 and j > i else ""


class TestGovernorWindow(unittest.TestCase):

    def test_explainer_and_counters_gone(self):
        text = page()
        for key in ("gov.presentNote", "dt.dispatched", "dt.answered"):
            self.assertEqual(text_keys(key), 0, key)
        self.assertNotIn("总督就是你正在聊的主对话", text)
        self.assertNotIn("The governor is the main conversation you are talking to", text)
        self.assertEqual(text_keys("gov.awayNote"), 2, "the away note stays")
        branch = gov_branch()
        self.assertTrue(branch, "renderDetail's governor branch not found")
        self.assertNotIn("d-tools", branch)
        self.assertNotIn("presentNote", branch)

    def test_two_columns(self):
        branch = gov_branch()
        for cls in ("gov-cols", "gov-side", "gov-chat", "p-head"):
            self.assertIn('class="%s"' % cls, branch, cls)
        side = branch[branch.index('class="gov-side"'):branch.index('class="gov-chat"')]
        self.assertIn("teamListHtml(", side, "the team list is the left column")
        right = branch[branch.index('class="gov-chat"'):]
        self.assertIn("p-head", right, "the short facts head the right column")
        self.assertIn("chatSectionHtml(", right, "the chat is in the right column")

    def test_wide_window(self):
        src = function_source("renderWin") or ""
        self.assertRegex(src, r"classList\.toggle\(\s*'wide'")
        wide = rule(".win.wide").replace(" ", "")
        self.assertIn("width:min(", wide)
        self.assertIn("height:calc(100%-24px)", wide)
        cols = rule(".gov-cols")
        self.assertIn("display:grid", cols.replace(" ", ""))
        self.assertEqual(columns(cols), 2, "two columns")
        chat = rule(".gov-chat .chat").replace(" ", "")
        self.assertIn("max-height:none", chat)

    def test_phone_stacks(self):
        m = media_960()
        self.assertTrue(rule(".win.wide", m), "a .win.wide rule for phones")
        self.assertEqual(columns(rule(".gov-cols", m)), 1, "phone: one column")


# ---------------------------------------------------------------------------
# U8 + U9: the chat log
# ---------------------------------------------------------------------------

CHAT_DRIVER = r"""
const md = s => mdLite(s);
__out = { stick: CHAT_STICK_PX,
  scroll: [chatScroll(null, { height: 900, client: 300 }), chatScroll(null, { height: 200, client: 300 }),
    chatScroll({ top: 570, height: 900, client: 300 }, { height: 1000, client: 300 }),
    chatScroll({ top: 100, height: 900, client: 300 }, { height: 1000, client: 300 }),
    chatScroll({ top: 100, height: 900, client: 300 }, { height: 900, client: 300 })],
  md: {
    comment: md('<!-- buddy: idle, no action -->hello'), open: md('hi <!-- never closed'),
    script: md('<script>alert(1)</script>'), bold: md('**bold** text'), code: md('run `ls -la` now'),
    fence: md('```\n**x** <b>\n```'), ul: md('- a\n- b'), ol: md('1. a\n2. b'),
    table: md('| a | b |\n|---|---|\n| 1 | 2 |'), paras: md('one\n\ntwo'),
    img: md('**<img src=x onerror=alert(1)>**'), link: md('[x](javascript:alert(1))'), quote: md('say "hi" & bye') } };
"""


class TestChatLog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(CHAT_DRIVER, {}, ("CHAT_STICK_PX", "chatScroll", "mdLite"))

    def test_chat_scroll(self):
        self.assertEqual(self.r["stick"], 40)
        self.assertEqual(self.r["scroll"], [{"top": 600, "chip": False}, {"top": 0, "chip": False},
                                            {"top": 700, "chip": False}, {"top": 100, "chip": True},
                                            {"top": 100, "chip": False}])

    def test_comments_are_hidden(self):
        m = self.r["md"]
        self.assertNotIn("buddy", m["comment"])
        self.assertIn("hello", m["comment"])
        self.assertNotIn("never closed", m["open"])
        self.assertIn("hi", m["open"])

    def test_no_raw_html_ever(self):
        m = self.r["md"]
        self.assertNotIn("<script", m["script"])
        self.assertIn("&lt;script&gt;", m["script"])
        self.assertNotIn("<img", m["img"])
        self.assertIn("&lt;img", m["img"])
        self.assertNotIn("<a", m["link"])
        self.assertNotIn("href", m["link"])
        self.assertIn("&amp;", m["quote"])
        self.assertIn("&quot;hi&quot;", m["quote"])

    def test_simple_markdown(self):
        m = self.r["md"]
        self.assertRegex(m["bold"], r"<(b|strong)>bold</(b|strong)>")
        self.assertIn("<code>ls -la</code>", m["code"])
        self.assertIn("<pre><code>", m["fence"])
        self.assertIn("**x** &lt;b&gt;", m["fence"], "nothing formatted inside a fence")
        self.assertRegex(m["ul"], r"<ul><li>a</li><li>b</li></ul>")
        self.assertRegex(m["ol"], r"<ol><li>a</li><li>b</li></ol>")
        self.assertIn("<table", m["table"])
        self.assertIn("<th>a</th>", m["table"])
        self.assertIn("<td>2</td>", m["table"])
        self.assertNotIn("---", m["table"])
        self.assertEqual(len(re.findall(r"<p>", m["paras"])), 2)


class TestChatWiring(unittest.TestCase):

    def test_chat_uses_mdlite(self):
        src = function_source("chatHtml") or ""
        self.assertIn("mdLite(", src)
        self.assertIn('class="md"', src)
        self.assertTrue(sim_has("mdLite"), "mdLite lives in the sim section (no three.js, no DOM)")
        self.assertTrue(rule(".md table") or rule(".md th"), "CSS for markdown tables")
        self.assertTrue(rule(".md code") or rule(".md pre"), "CSS for markdown code")

    def test_no_forced_jump_to_the_bottom(self):
        src = function_source("renderDetail") or ""
        self.assertIn("chatScroll(", src)
        self.assertNotRegex(src, r"ol\.innerHTML\s*=\s*html;\s*ol\.scrollTop\s*=\s*ol\.scrollHeight",
                            "the old unconditional jump to the bottom is gone")

    def test_chip_and_place_survive_refreshes(self):
        """Headless E2E: the chip showed for one refresh and was hidden by the next; a rebuilt card (the person's
        state changed) threw the owner back to the bottom. The chip stays until clicked or the owner is back at
        the bottom; a rebuild of the SAME chat keeps its scroll place (prev = the state saved before the rebuild)."""
        src = function_source("renderDetail") or ""
        self.assertNotRegex(src, r"hidden\s*=\s*!\s*res\.chip", "a later refresh must not hide the chip again")
        self.assertNotRegex(src, r"rebuilt\s*\?\s*null", "a rebuild of the same chat keeps its place")

    def test_new_messages_chip(self):
        for key in ("chat.new",):
            self.assertEqual(text_keys(key), 2, key)
        self.assertIn('class="newmsg"', page())
        self.assertTrue(rule(".newmsg"), "CSS for the chip")


# ---------------------------------------------------------------------------
# U10: every person's window, with its history
# ---------------------------------------------------------------------------

U10_DRIVER = r"""
const V = __payload.view, A = V.territories[0];
function buildLand(view){ landState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'idle' }], agents: [] });
apply({ type: 'spawn', id: 'x1', role: 'worker', label: 'worker', task: '登录 API', terr: A.id });
const c = byId('x1'), out = { fresh: Array.isArray(c.acts) };
out.n0 = c.acts.length;
for (const t of ['Edit', 'Edit', 'Read']) apply({ type: 'tool', id: 'x1', tool: t });
out.afterTools = c.acts.map(a => a.text);
apply({ type: 'stuck', id: 'x1', question: '支付超时要不要自动重试？' });
apply({ type: 'tool', id: 'x1', tool: 'Bash' });
apply({ type: 'relay', id: 'x1', to: 'governor', lead: '' });
apply({ type: 'waiting', id: 'x1' });
apply({ type: 'done', id: 'x1' });
apply({ type: 'leave', id: 'x1' });
out.acts = c.acts.map(a => a.text);
out.atOk = c.acts.every(a => typeof a.at === 'number' && a.at > 1.6e9);
out.want = [i18n('hist.started', { task: '登录 API' }), 'Edit ×2 · Read ×1', i18n('hist.stuck', { text: '支付超时要不要自动重试？' }),
  'Bash ×1', i18n('hist.toGov'), i18n('hist.waiting'), i18n('hist.done'), i18n('hist.left')];
out.keys = ['hist.started', 'hist.stuck', 'hist.toLead', 'hist.toGov', 'hist.waiting', 'hist.done', 'hist.left', 'hist.title', 'hist.empty', 'chat.task'].map(k => i18n(k, { task: 'T', text: 'X' }));
for (let i = 0; i < 200; i++) actLog(c, 'line ' + i);
out.cap = { n: c.acts.length, keep: ACT_KEEP, last: c.acts[c.acts.length - 1].text, first: c.acts[0].text };
const q = { question: 'q?', answer: 'a!', qa: [], stuck: true, state: 'asking', terr: A.id };
giveAnswer(q);
out.qa = q.qa.map(x => ({ q: x.q, a: x.a, at: typeof x.at === 'number' && x.at > 1.6e9 }));
const p = { acts: [{ at: 10, text: 'a' }, { at: 30, text: 'b' }], qa: [{ q: 'q1', a: 'a1', at: 20 }], stuck: true, question: 'q2' };
out.hist = personHistory(p, [{ kind: 'prompt', text: 't', at: 5 }, { kind: 'reply', text: 'r', at: 25 }, { kind: 'owner', text: 'o', at: 30, state: 'delivered' }])
  .map(x => x.k + ':' + (x.k === 'ask' ? x.q + (x.a === null ? ':open' : ':' + x.a) : x.text));
p.stuck = false;
out.hist2 = personHistory(p, []).map(x => x.k);
out.html = historyHtml([{ k: 'act', at: 1727500000, text: '<b>x</b>' }, { k: 'ask', q: '<q>', a: null, at: 2 },
  { k: 'ask', q: 'q', a: 'a<i>', at: 3 }, { k: 'reply', text: '**bold**', at: 4 }], 'worker', false);
out.empty = historyHtml([], 'w', false);
out.labels = { ask: i18n('label.ask'), answer: i18n('label.answer'), waiting: i18n('label.awaitingAnswer'), empty: i18n('hist.empty') };
__out = out;
"""


class TestPersonHistory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(U10_DRIVER, {"view": two_territory_view()},
                        ("apply", "byId", "landState", "i18n", "actLog", "actTool", "ACT_KEEP", "personHistory",
                         "historyHtml", "giveAnswer"))

    def test_activity_lines_from_live_events(self):
        self.assertTrue(self.r["fresh"], "newCitizen gives c.acts = []")
        self.assertEqual(self.r["n0"], 1, "spawn -> one started line")
        self.assertEqual(self.r["afterTools"], self.r["want"][:2], "tools in a row share one line")
        self.assertEqual(self.r["acts"], self.r["want"])
        self.assertTrue(self.r["atOk"], "every line has at = Date.now() / 1000")

    def test_texts_exist(self):
        for got in self.r["keys"]:
            self.assertFalse(got.startswith(("hist.", "hint.", "chat.")), "missing TEXT key: " + got)

    def test_capped(self):
        c = self.r["cap"]
        self.assertEqual(c["keep"], 60)
        self.assertEqual(c["n"], 60)
        self.assertEqual(c["last"], "line 199")
        self.assertEqual(c["first"], "line 140")

    def test_answers_are_dated(self):
        self.assertEqual(self.r["qa"], [{"q": "q?", "a": "a!", "at": True}])

    def test_one_history_oldest_first(self):
        self.assertEqual(self.r["hist"], ["prompt:t", "act:a", "ask:q1:a1", "reply:r", "act:b", "owner:o", "ask:q2:open"])
        self.assertEqual(self.r["hist2"], ["act", "ask", "act"])

    def test_history_rows(self):
        h, L = self.r["html"], self.r["labels"]
        self.assertIn('<li class="act">', h)
        self.assertIn("<time>", h)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", h)
        self.assertNotIn("<b>x</b>", h)
        self.assertEqual(h.count('<li class="qa"'), 2)
        self.assertIn("&lt;q&gt;", h)
        self.assertIn(L["waiting"], h)
        self.assertIn("a&lt;i&gt;", h)
        self.assertIn('class="msg"', h)
        self.assertRegex(h, r"<(b|strong)>bold</(b|strong)>")
        self.assertIn("msg-empty", self.r["empty"])
        self.assertIn(L["empty"], self.r["empty"])


def citizen_branch():
    src = function_source("renderDetail") or ""
    i = src.find("} else if (c) {")
    j = src.find("} else if (selected && selected.t === 'rg')", i)
    return src[i:j] if i >= 0 and j > i else ""


class TestPersonWindow(unittest.TestCase):

    def test_wide_for_every_person(self):
        src = function_source("renderWin") or ""
        m = re.search(r"classList\.toggle\(\s*'wide'\s*,([^)]*)\)", src)
        self.assertIsNotNone(m, "renderWin toggles 'wide'")
        cond = m.group(1)
        self.assertIn("'c'", cond + src, "citizens get the wide window")
        self.assertIn("'gov'", cond + src)

    def test_citizen_two_columns(self):
        b = citizen_branch()
        self.assertTrue(b, "renderDetail's citizen branch not found")
        for cls in ("gov-cols", "gov-side", "gov-chat", "p-head"):
            self.assertIn('class="%s"' % cls, b, cls)
        side = b[b.index('class="gov-side"'):b.index('class="gov-chat"')]
        self.assertIn("teamListHtml(", side, "U11: the same full team list on the left")
        for gone in ("d-bar", "kv.branch", "kv.repo", "d-tools"):
            self.assertNotIn(gone, side, "U11: the person's facts are not in the left column: " + gone)
        right = b[b.index('class="gov-chat"'):]
        self.assertIn("hist.title", right)
        self.assertIn("personHistory(", b + (function_source("renderDetail") or ""))
        self.assertIn("historyHtml(", function_source("renderDetail") or "")

    def test_history_list_is_refreshed(self):
        src = function_source("renderDetail") or ""
        tail = src[src.rfind("if (chatTo)"):] if "if (chatTo)" in src else src
        self.assertIn("historyHtml(", tail, "the per-call refresh keeps the history current")


TEAM_DRIVER = r"""
const V = __payload.view, A = V.territories[0], B = V.territories[1];
function buildLand(view){ landState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'idle' }], agents: [] });
apply({ type: 'spawn', id: 'x1', role: 'worker', label: 'worker', task: 'one', terr: A.id });
apply({ type: 'spawn', id: 'x2', role: 'worker', label: 'worker', task: 'two <b>', terr: A.id });
apply({ type: 'spawn', id: 'y1', role: 'worker', label: 'worker', task: 'far', terr: B.id });
const rows = html => [...html.matchAll(/<button\b[^>]*class="row"[^>]*>/g)].map(m => { // city-ux2: only the row buttons, not their focus buttons
  const sel = /data-sel="([^"]*)"/.exec(m[0]), cur = /aria-current="([^"]*)"/.exec(m[0]);
  return (sel ? sel[1] : '?') + (cur && cur[1] === 'true' ? '*' : ''); });
const group = rosterGroups().find(g => g.terr === A.id).rows.map(r => r.id);
const rp = newCitizen('r:dev-ann:s:9', 'worker', 'far task', A.id);
rp.remote = { who: 'Ann', device: 'lap', dev: 'dev-ann', rid: 'acme/shop', br: 'b' }; citizens.push(rp);
__out = { group, a: A.id,
  x2: rows(teamListHtml(A.id, { t: 'c', id: 'x2' })), gov: rows(teamListHtml(A.id, { t: 'gov', terr: A.id })),
  home: rows(teamListHtml(A.id, { t: 'gov' })), other: rows(teamListHtml(A.id, { t: 'c', id: 'y1' })),
  raw: teamListHtml(A.id, { t: 'c', id: 'x1' }),
  withRemote: rows(teamListHtml(A.id, { t: 'c', id: 'x1' })), remoteSel: rows(teamListHtml(A.id, { t: 'c', id: 'r:dev-ann:s:9' })) };
"""


class TestTeamList(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(TEAM_DRIVER, {"view": two_territory_view()}, ("apply", "landState", "rosterGroups", "teamListHtml", "esc", "newCitizen", "citizens"))

    def test_same_rows_as_the_roster(self):
        g = self.r["group"]
        self.assertEqual(g[0], "gov:" + self.r["a"])
        # every list below is taken after the driver added one other member's person to territory A
        self.assertEqual([x.rstrip("*") for x in self.r["x2"]], g + ["r:dev-ann:s:9"])

    def test_only_the_selected_row_is_current(self):
        a = self.r["a"]
        self.assertEqual([x for x in self.r["x2"] if x.endswith("*")], ["x2*"])
        self.assertEqual([x for x in self.r["gov"] if x.endswith("*")], ["gov:%s*" % a])
        self.assertEqual([x for x in self.r["home"] if x.endswith("*")], ["gov:%s*" % a], "no terr = the home governor")
        self.assertEqual([x for x in self.r["other"] if x.endswith("*")], [], "someone of another repo is not in this list")

    def test_other_members_are_always_listed(self):
        g = self.r["group"]
        self.assertEqual(self.r["withRemote"], [("x1*" if x == "x1" else x) for x in g] + ["r:dev-ann:s:9"],
                         "the remote person is listed while someone else is selected")
        self.assertEqual(self.r["remoteSel"], g + ["r:dev-ann:s:9*"])

    def test_rows_are_escaped_buttons(self):
        raw = self.r["raw"]
        self.assertIn('class="row"', raw)
        self.assertNotIn("two <b>", raw)
        self.assertTrue(sim_has("esc"), "esc lives in the sim section")


class TestTeamWindowHead(unittest.TestCase):

    def test_one_title_for_the_team(self):
        self.assertEqual(text_keys("team.title"), 2)
        self.assertIn("'team.title': '{repo} · 团队'", page())
        self.assertIn("team.title", function_source("winTitle") or "")

    def test_governor_head_facts(self):
        branch = gov_branch()
        i = branch.find('class="p-head"')
        self.assertGreater(i, 0)
        head = branch[i:branch.find("hist.title", i) if "hist.title" in branch[i:] else i + 1500]
        self.assertIn("gov.ownTag", head, "repo · main manager · 主对话 under the name")
        self.assertIn("govRowText(", head, "the same state words as its list row")


class TestNoToolCounters(unittest.TestCase):

    def test_gone(self):
        src = function_source("renderDetail") or ""
        self.assertNotIn("d-tools", src)
        self.assertNotRegex(src, r"\[\s*'Edit'\s*,\s*'Write'\s*,\s*'Bash'\s*,\s*'Read'\s*\]")


BUILDING_DRIVER = r"""
const T = o => buildingName(Object.assign({ name: '', task: '', by: 'worker', files: [], type: 'house' }, o));
const V = __payload.view, A = V.territories[0];
function buildLand(view){ landState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'idle' }], agents: [] });
const rec = newBuildingRecord(A.id, 99, 'shop', 0, 0, 'worker', true, { task: '导出 CSV', files: ['web/export.js'] });
__out = { names: [
    T({ name: 'Checkout' }),
    T({ name: 'src/a.py', task: '登录 API' }),
    T({ task: 'worker', files: ['api/login.py', 'tests/test_login.py'] }),
    T({ files: ['src/components/Cart/index.js', 'src/components/Cart/Cart.css', 'src/components/Nav/Nav.js'] }),
    T({ files: ['README.md'] }),
    T({ type: 'tower' }),
    T({ task: 'task-manager', by: 'task-manager', files: ['bin/agent_city.py', 'bin/agent-city.html'] }),
    T({ task: 'web/export.js', files: ['lib/util.py'] }),
    T({ name: 'x.py', task: 'merge-deputy', files: ['a\\\\b\\\\report_test.go'] })],
  want: [i18n('building.module', { name: 'login' }), i18n('building.module', { name: 'Cart' }), i18n('type.house'), i18n('type.tower'),
    i18n('building.module', { name: 'agent_city' }), i18n('type.house'), i18n('building.module', { name: 'report' })],
  rec: { task: rec.task, name: buildingName(rec), label: bldLabel(rec), info: buildingInfo(rec).name },
  key: i18n('building.module', { name: 'N' }) };
"""


class TestBuildingName(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(BUILDING_DRIVER, {"view": two_territory_view()},
                        ("buildingName", "newBuildingRecord", "bldLabel", "buildingInfo", "apply", "landState", "i18n"))

    def test_one_meaningful_name(self):
        n, w = self.r["names"], self.r["want"]
        self.assertEqual(n[0], "Checkout")
        self.assertEqual(n[1], "登录 API", "a path-like name is skipped, the task wins")
        self.assertEqual(n[2], w[0], "a bare role word is no task: the module from the files")
        self.assertEqual(n[3], w[1], "a generic stem gives its folder; the most frequent wins")
        self.assertEqual(n[4], w[2], "nothing meaningful: the type word")
        self.assertEqual(n[5], w[3])
        self.assertEqual(n[6], w[4], "the builder's own label is no task; first file wins a tie")
        self.assertEqual(n[7], w[5], "a path-like task is skipped; util in lib gives nothing")
        self.assertEqual(n[8], w[6], "backslash paths and a _test suffix")

    def test_never_a_path(self):
        for name in self.r["names"]:
            self.assertNotRegex(name, r"[/\\\\]|\.[A-Za-z0-9]{1,5}$", name)

    def test_the_record_keeps_the_task(self):
        r = self.r["rec"]
        self.assertEqual(r["task"], "导出 CSV")
        self.assertEqual(r["name"], "导出 CSV")
        self.assertEqual(r["label"], "导出 CSV")
        self.assertEqual(r["info"], "导出 CSV")

    def test_text(self):
        self.assertEqual(text_keys("building.module"), 2)
        self.assertEqual(self.r["key"], "N 模块")


def building_branch():
    src = function_source("renderDetail") or ""
    i = src.find("} else if (b) {")
    j = src.find("} else if (", i + 5)
    return src[i:j] if i >= 0 and j > i else ""


class TestBuildingCard(unittest.TestCase):

    def test_only_the_name_and_the_type(self):
        b = building_branch()
        self.assertTrue(b, "renderDetail's building branch not found")
        for gone in ("hint.files", "hint.history", ".files", ".hist", "info.quality", "building.level", "building.misplaced"):
            self.assertNotIn(gone, b, gone)
        self.assertTrue("buildingName(" in b or "info.name" in b)

    def test_build_hands_the_task_on(self):
        src = page()
        i = src.find("case 'build': {")
        self.assertGreater(i, 0)
        self.assertRegex(src[i:i + 1500], r"pendingBuild\s*=\s*\{[^}]*task:\s*owner\.task")


if __name__ == "__main__":
    unittest.main()
