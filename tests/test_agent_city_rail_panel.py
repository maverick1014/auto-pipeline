"""Failing tests for city-polish P2-P4 (owner, 2026-09-30, screenshots of the live city; mock
mock/city-polish-mock.html, f486e27, approved with two owner changes: C1 the panel stays full height, the
history fills it; C2 the history shows the main messages only, one small toggle shows the rest).

CONTRACT (bin/agent-city.html). "sim section" = the page script from 'use strict' up to the '3D view.'
comment: every function named "(sim)" below lives there and is driven in node (tests/test_agent_city_people.py
run_sim). Everything else is "3D part", checked on its source and its CSS.

P2 + C1 the message panel: full height, the history fills it, no empty space at the bottom
  CSS: --msg-w 360 .. 400px (about 380; was 330). .win stays docked full height: right:12px, top:12px,
      bottom:12px, width:var(--msg-w) (C1, owner: "scrolling a short box is annoying").
      .chat (the history): no fixed max-height (none, or no max-height at all; was 220px), min-height:0,
      overflow:auto and a flex that grows and shrinks (flex:1 ..., neither grow nor shrink 0): it fills all the
      space above the input row and scrolls inside. .say (the box + 发送): one row -- display:flex, not
      flex-direction:column; its textarea flex:1 (or flex-grow 1), min-width:0, one line tall (min-height and
      height at most 40px, resize:none); .say .btn does not wrap (white-space:nowrap or flex:none). .newmsg
      sits just above that row (bottom at most 80px, the phone too).
  Phone, @media (max-width: 960px): .win stays the bottom sheet (top:auto), as today. The sheet is short (44% of
      the stage), so there the history never shrinks to nothing: .chat min-height at least 80px (the sheet's
      #detail scrolls to the input row, as it did before). Headless check 2026-09-30, 390 x 844: a 167 px
      sheet showed no history and cut the input row off.

C2 the history shows the main messages; one small toggle shows the rest (owner: "like Claude Code itself
  hides its mechanism")
  Main = the human's prompts and the agent's final replies to the human. Hidden by default: every activity
      line (tool steps, 出门 / 完工 / 下班, 派出, 发消息), prompts that are machine traffic (task
      notifications, messages from other sessions or teammates, system / hook / command lines) and the replies
      to them, and a subagent's replies (its report to its lead). Question/answer cards always show.
  (sim) MACHINE_STARTS: the texts a machine prompt starts with, at least '<task-notification',
      '<agent-message', '<teammate-message', 'Another Claude session sent a message', '<system-reminder',
      '<command-name', '<command-message', '<local-command-', '<bash-input', '<user-prompt-submit-hook',
      '[Request interrupted', 'This session is being continued from a previous conversation'.
  (sim) isMachinePrompt(text) -> true when String(text) without its leading white space starts with one of
      MACHINE_STARTS (a human paste, <pasted_content ...>, is not one).
  (sim) markMain(entries, sub) -> a new array, same order, each entry a copy with main set (the input is
      left as it is): 'owner' -> true; 'prompt' -> !isMachinePrompt(text); 'reply' -> false when sub (a
      subagent's page), else the main of the latest 'owner' / 'prompt' entry before it (true when there is
      none); any other kind -> true.
  (sim) personHistory(c, entries): as before, and every item carries main: 'act' false, 'ask' true, a chat
      entry the main markMain(entries, !!c.lead) gives it.
  (sim) mainOnly(items) -> the items whose main is not false (an item without main counts as main).
  3D part: let histAll = readStoredBool('agent-city.histAll', false); setHistAll(v) sets it, saves it
      (writeStoredBool) and redraws the panel. renderDetail: the history line (<p class="hint hist-h">) holds
      <button type="button" class="hist-all" id="hist-all" aria-pressed="<histAll>">, text i18n('hist.all',
      {n: the number hidden}) while off (hidden when that is 0) and i18n('hist.hide') while on; the list shows
      histAll ? every item : mainOnly(items) -- a person's personHistory() and the governor's
      markMain(entries, false) alike; when that leaves nothing but something is hidden, one
      <li class="msg-empty"> with i18n('hist.onlyMech'). The #detail click listener: #hist-all ->
      setHistAll(!histAll). winEntryCount() (the folded tab's badge) counts what the list would show
      (mainOnly unless histAll). New TEXT keys, zh and en: hist.all, hist.hide, hist.onlyMech.

P3 names never repeat the repo name
  (sim) shortLabel(text, repo) -> text without the repo name: '' when text === repo; the rest (trimmed) when
      text starts with repo followed by ' · ', ' ', ':' or '/'; else text unchanged (also when repo is '').
  (sim) nameOf(c): the name inside c's own territory. repo = terrOf(c.terr).name ('' when none);
      label = shortLabel(c.label, repo), task = shortLabel(c.task, repo); an empty label takes the task's place
      (the task then shows no more); both empty -> c.label as it is. Then, as before: label, or
      "label · task" when the task is not empty and differs; " #" + the last 4 characters of c.id when another
      citizen of the SAME territory (not gone, not remote) reads the same.
  P6 (owner screenshot, "worker · picker-sticky-header Worker 1: product-p" is too long): in nameOf, when that
      task (after shortLabel) reads "<feature> <Kind> <n>: <slice>" or "<Kind> <n>: <slice>" (Kind one word
      that starts with a capital letter, n digits), the name is "<Kind> <n> · <slice>" and the label does not
      show (the kind already says it). The full task stays in the panel subtitle (factsLine).
  (sim) fullName(c) -> "<repo> · <nameOf(c)>" (nameOf(c) alone when there is no repo or the name is the repo
      itself): the repo once, in front. Only for the page log (chatDisplayName), where every repo mixes.
  (sim) factsLine(c) -> the panel's subtitle, plain text: the repo name, then " · " + shortLabel(c.task, repo)
      only when that is not empty and not already part of nameOf(c) (so the repo never shows twice).
  (sim) doingText(c): the task part is shortLabel(c.task, repo) (a task that is only the repo name shows no
      task; the step alone).
  3D part: the rail row, the head tag (updatePerson), the panel title (winTitle) and p-name, the find-lead
      button, the follow chip and the chat's own lines show nameOf(c); chatDisplayName uses fullName(pc);
      renderDetail's person subtitle is esc(factsLine(c)); winTitle for the governor is i18n('who.governor')
      (the repo is in the subtitle already, never twice).

P4 one straight colour bar per repo group
  (sim) railHtml: <section class="rail-grp" data-terr="<terr>" style="--rc:<color>"> (the group's colour on
      the section); the head's <span class="n"> = every row of the group (the governor, the active and the
      resting people: g.rows.length); each row's dot is <span class="sdot st-<cls>">, cls = the class of its
      chip (the governor: gov; a person: citizenStatus(c)[0]).
  CSS: .rail-grp has border-left: 3 .. 6px solid var(--rc) and square corners (no border-radius); .rrow has no
      border-left any more; .sdot.st-you, .st-ask, .st-build, .st-walk, .st-rest and .st-gov each have their
      own rule with a background that is not var(--ink-3) (you and ask/gov differ from build; rest differs
      from build).

Run: python3 -m unittest tests.test_agent_city_rail_panel </dev/null
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import function_source, page, run_sim  # noqa: E402
from test_agent_city_chain import TA, TB, two_territory_view  # noqa: E402
from test_agent_city_ux_page import css, listener_block, media_960, rule, text_keys  # noqa: E402

SIM_REQUIRED = ("apply", "landState", "railGroups", "railHtml", "nameOf", "fullName", "shortLabel", "factsLine",
                "doingText", "citizenStatus", "newCitizen", "citizens", "byId", "terrColor")


def top_css():
    """The page CSS without its @media blocks (the computer look)."""
    c, out, i = css(), [], 0
    while True:
        j = c.find("@media", i)
        if j < 0:
            out.append(c[i:])
            return "".join(out)
        out.append(c[i:j])
        depth, k = 0, c.index("{", j)
        for k in range(k, len(c)):
            if c[k] == "{":
                depth += 1
            elif c[k] == "}":
                depth -= 1
                if depth == 0:
                    break
        i = k + 1


def top(sel):
    return rule(sel, top_css())


def flat(block):
    return (block or "").replace(" ", "").replace("\n", "")


def px(value):
    m = re.search(r"(-?\d+(?:\.\d+)?)px", value or "")
    return float(m.group(1)) if m else None


def decl(block, prop):
    """The last value of PROP in a declaration block (no spaces), or None."""
    vals = re.findall(r"(?:^|;)%s:([^;]*)" % re.escape(prop), flat(block))
    return vals[-1] if vals else None


# ---------------------------------------------------------------------------
# P3 + P4: two repos, v4-pospro (A, a governor) and v4-plus (B, a governor), names as the server sends them
# ---------------------------------------------------------------------------

DRIVER = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
A.name = 'v4-pospro'; B.name = 'v4-plus';
function buildLand(view){ landState(view); }
const ag = (id, label, task, terr, extra) => Object.assign({ id, role: 'task-manager', label, task, stuck: false, done: false,
  tools: {}, terr, lead: '', office: null, relay: '' }, extra || {});
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 2, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'busy' }, { terr: B.id, state: 'idle' }], agents: [
  ag('s:hhhh0001', 'v4-pospro Helper', 'v4-pospro', A.id),
  ag('s:pppp0002', 'session', 'v4-pospro', A.id),
  ag('s:mmmm0003', 'v4-pospro Manager', 'v4-pospro', A.id),
  ag('s:cccc0004', 'city-polish Task Manager', 'v4-pospro', A.id),
  ag('w5', 'worker', '小票打印', A.id, { role: 'worker' }),
  ag('s:rrrr0006', 'fast-lane-deputy', '按钮颜色', A.id, { role: 'fast-lane-deputy' }),
  ag('s:aaaa1111', 'session', 'v4-plus', B.id),
  ag('s:bbbb2222', 'session', 'v4-plus', B.id),
  ag('s:xxxx0007', 'v4-plus', 'v4-plus', B.id),
  ag('s:yyyy0008', 'v4-plus', '结账', B.id),
  ag('w6', 'worker', 'picker-sticky-header Worker 1: product-p', A.id, { role: 'worker' }),
  ag('w7', 'worker', 'v4-pospro Worker 2: rail', A.id, { role: 'worker' }),
  ag('w8', 'worker', 'Worker 3: api', A.id, { role: 'worker' }),
  ag('w9', 'worker', 'fix: login', A.id, { role: 'worker' }),
  ag('w10', 'worker', 'city-polish Deputy', A.id, { role: 'worker' }),
]});
byId('s:rrrr0006').state = 'resting';
byId('s:hhhh0001').waiting = true;
const rp = newCitizen('r:dev-ann:s:9', 'task-manager', 'v4-plus', B.id); rp.label = 'session'; rp.task = 'v4-plus';
rp.remote = { who: 'Ann', device: 'lap', dev: 'dev-ann', rid: 'acme/plus', br: 'b' }; citizens.push(rp);
const ids = ['s:hhhh0001', 's:pppp0002', 's:mmmm0003', 's:cccc0004', 'w5', 's:rrrr0006', 's:aaaa1111', 's:bbbb2222', 's:xxxx0007', 's:yyyy0008',
  'w6', 'w7', 'w8', 'w9', 'w10'];
const names = {}, full = {}, facts = {};
for (const id of ids) { names[id] = nameOf(byId(id)); full[id] = fullName(byId(id)); facts[id] = factsLine(byId(id)); }
const short = [shortLabel('v4-pospro Helper', 'v4-pospro'), shortLabel('session', 'v4-plus'), shortLabel('v4-plus', 'v4-plus'),
  shortLabel('v4-plusplus Helper', 'v4-plus'), shortLabel('auto-pipeline:worker', 'auto-pipeline'),
  shortLabel('auto-pipeline · Manager', 'auto-pipeline'), shortLabel('app/api Worker', 'app'), shortLabel('Helper', ''),
  shortLabel('auto-pipeline Manager', 'auto-pipeline'), shortLabel('', 'x')];
// doingText: a working session whose task is only the repo name shows the step alone
const d = byId('s:pppp0002'); d.path = []; d.state = 'working'; d.workKind = 'read'; d.workAt = simT; d.workSince = simT; d.step = '看文件';
const doing = [doingText(d)];
const w = byId('w5'); w.path = []; w.state = 'working'; w.workKind = 'read'; w.workAt = simT; w.workSince = simT; w.step = '看文件';
doing.push(doingText(w));
const G = railGroups();
const html = railHtml(G, null, new Set(), new Set([A.id]));
const sections = [...html.matchAll(/<section\b[^>]*>/g)].map(m => m[0]);
const heads = G.map(g => {
  const i = html.indexOf('data-grp="' + g.terr + '"');
  const m = /<span class="n">\s*(\d+)\s*<\/span>/.exec(html.slice(i));
  return { terr: g.terr, rows: g.rows.length, n: m ? +m[1] : null, color: g.color };
});
const rowDots = [...html.matchAll(/data-focus="([^"]*)"[^>]*>\s*<span class="([^"]*)"><\/span>\s*<b>([^<]*)<\/b>\s*<span class="chip ([^"]*)"/g)]
  .map(m => ({ id: m[1], dot: m[2], name: m[3], chip: m[4] }));
__out = { a: A.id, b: B.id, names, full, facts, short, doing, sections, heads, rowDots, html };
"""


def payload():
    return {"view": two_territory_view(), "ta": TA, "tb": TB}


class TestShortNames(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(DRIVER, payload(), SIM_REQUIRED)

    def test_short_label(self):
        self.assertEqual(self.r["short"], ["Helper", "session", "", "v4-plusplus Helper", "worker", "Manager",
                                           "api Worker", "Helper", "Manager", ""])

    def test_names_inside_the_repo(self):
        n = self.r["names"]
        self.assertEqual(n["s:hhhh0001"], "Helper")
        self.assertEqual(n["s:pppp0002"], "session", "a task that is only the repo name is dropped")
        self.assertEqual(n["s:mmmm0003"], "Manager")
        self.assertEqual(n["s:cccc0004"], "city-polish Task Manager", "a feature name is not the repo name")
        self.assertEqual(n["w5"], "worker · 小票打印")
        self.assertEqual(n["s:xxxx0007"], "v4-plus", "nothing left: the label as it is")
        self.assertEqual(n["s:yyyy0008"], "结账", "an empty label takes the task's place")

    def test_worker_names_drop_the_repeated_kind_and_feature(self):
        n, f = self.r["names"], self.r["facts"]
        self.assertEqual(n["w6"], "Worker 1 · product-p")
        self.assertEqual(n["w7"], "Worker 2 · rail", "the repo goes first, then the kind rule")
        self.assertEqual(n["w8"], "Worker 3 · api")
        self.assertEqual(n["w9"], "worker · fix: login", "no <Kind> <n>: no change")
        self.assertEqual(n["w10"], "worker · city-polish Deputy")
        self.assertEqual(f["w6"], "v4-pospro · picker-sticky-header Worker 1: product-p", "the full task in the subtitle only")
        self.assertEqual(f["w7"], "v4-pospro · Worker 2: rail", "the repo once")

    def test_twins_are_told_apart_only_inside_one_repo(self):
        n = self.r["names"]
        self.assertEqual([n["s:aaaa1111"], n["s:bbbb2222"]], ["session #1111", "session #2222"])
        self.assertEqual(n["s:pppp0002"], "session", "v4-pospro's session is in another repo: no tag")

    def test_no_name_repeats_the_repo(self):
        for cid, name in self.r["names"].items():
            if cid in ("s:xxxx0007",):
                continue
            with self.subTest(id=cid):
                self.assertNotIn("v4-pospro", name)
                self.assertNotIn("v4-plus", name)

    def test_full_name_for_the_log(self):
        f = self.r["full"]
        self.assertEqual(f["s:hhhh0001"], "v4-pospro · Helper")
        self.assertEqual(f["s:pppp0002"], "v4-pospro · session")
        self.assertEqual([f["s:aaaa1111"], f["s:bbbb2222"]], ["v4-plus · session #1111", "v4-plus · session #2222"])
        self.assertEqual(f["w5"], "v4-pospro · worker · 小票打印")
        self.assertEqual(f["s:xxxx0007"], "v4-plus", "never the repo twice")

    def test_subtitle_names_the_repo_once(self):
        f = self.r["facts"]
        self.assertEqual(f["s:hhhh0001"], "v4-pospro")
        self.assertEqual(f["s:pppp0002"], "v4-pospro")
        self.assertEqual(f["s:cccc0004"], "v4-pospro")
        self.assertEqual(f["w5"], "v4-pospro", "the task is already in the name")
        self.assertEqual(f["s:aaaa1111"], "v4-plus")

    def test_doing_line_never_shows_the_repo(self):
        self.assertEqual(self.r["doing"][0], "看文件")
        self.assertEqual(self.r["doing"][1], "小票打印 · 看文件")

    def test_rail_rows_show_the_short_name(self):
        rows = {r["id"]: r["name"] for r in self.r["rowDots"]}
        self.assertEqual(rows.get("s:hhhh0001"), "Helper")
        self.assertEqual(rows.get("s:aaaa1111"), "session #1111")
        for cid, name in rows.items():
            if cid.startswith("gov:") or cid == "s:xxxx0007":
                continue
            with self.subTest(id=cid):
                self.assertNotIn("v4-p", name)


class TestRailGroups(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(DRIVER, payload(), SIM_REQUIRED)

    def test_colour_on_the_section(self):
        by = {h["terr"]: h for h in self.r["heads"]}
        for sec in self.r["sections"]:
            with self.subTest(sec=sec):
                m = re.search(r'data-terr="([^"]*)"', sec)
                self.assertIsNotNone(m)
                self.assertRegex(sec, r'class="rail-grp"')
                self.assertIn('style="--rc:%s"' % by[m.group(1)]["color"], sec)

    def test_count_is_everyone_in_the_group(self):
        for h in self.r["heads"]:
            with self.subTest(terr=h["terr"]):
                self.assertEqual(h["n"], h["rows"], "governor, active and resting people")
        by = {h["terr"]: h for h in self.r["heads"]}
        self.assertEqual(by[self.r["a"]]["n"], 12, "A: governor + 11 people (one resting)")
        self.assertEqual(by[self.r["b"]]["n"], 6, "B: governor + 4 people + Ann's")

    def test_dot_has_the_state_colour_class(self):
        rows = self.r["rowDots"]
        self.assertGreater(len(rows), 8)
        for r in rows:
            with self.subTest(id=r["id"]):
                self.assertEqual(r["dot"], "sdot st-" + r["chip"])
        chips = {r["id"]: r["chip"] for r in rows}
        self.assertEqual(chips["gov:" + self.r["a"]], "gov")
        self.assertEqual(chips["s:hhhh0001"], "you", "waiting on the owner")
        self.assertEqual(chips["s:rrrr0006"], "rest")


class TestRailCss(unittest.TestCase):

    def test_one_straight_bar_per_group(self):
        g = flat(top(".rail-grp"))
        m = re.search(r"border-left:(\d+(?:\.\d+)?)pxsolidvar\(--rc\)", g)
        self.assertIsNotNone(m, ".rail-grp border-left: <n>px solid var(--rc) -- got " + g)
        self.assertTrue(3 <= float(m.group(1)) <= 6, m.group(1))
        self.assertNotIn("border-radius", g, "a straight bar")
        self.assertNotIn("border-left", flat(top(".rrow")), "no curved edge per row")

    def test_dot_colours(self):
        seen = {}
        for cls in ("you", "ask", "build", "walk", "rest", "gov"):
            with self.subTest(cls=cls):
                bg = decl(top(".sdot.st-" + cls), "background")
                self.assertIsNotNone(bg, ".sdot.st-%s has its own background" % cls)
                self.assertNotEqual(bg, "var(--ink-3)")
                seen[cls] = bg
        if len(seen) < 6:
            return
        self.assertNotEqual(seen["you"], seen["build"])
        self.assertNotEqual(seen["ask"], seen["build"])
        self.assertNotEqual(seen["rest"], seen["build"])


class TestNamesDrawn(unittest.TestCase):
    """The 3D part shows nameOf / fullName / factsLine where the contract says."""

    def test_short_name_everywhere_in_a_repo(self):
        for fn in ("railRowHtml", "updatePerson", "winTitle", "renderDetail", "renderFollow"):
            with self.subTest(fn=fn):
                self.assertTrue("nameOf(" in (function_source(fn) or ""), fn + " shows nameOf(c)")

    def test_log_keeps_the_full_name(self):
        self.assertTrue("fullName(" in (function_source("chatDisplayName") or ""), "chatDisplayName uses fullName(pc)")

    def test_subtitle_from_facts_line(self):
        self.assertTrue("factsLine(c)" in (function_source("renderDetail") or ""), "renderDetail's subtitle is esc(factsLine(c))")

    def test_governor_title_is_just_governor(self):
        src = function_source("winTitle") or ""
        line = next((l for l in src.splitlines() if "selected.t === 'gov'" in l), "")
        self.assertTrue("who.governor" in line and "gov.title" not in line,
                        "winTitle for the governor is i18n('who.governor'): the repo shows in the subtitle, not twice")


# ---------------------------------------------------------------------------
# P2: the panel CSS
# ---------------------------------------------------------------------------

class TestPanelCss(unittest.TestCase):

    def test_a_bit_wider(self):
        m = re.search(r"--msg-w\s*:\s*(\d+)px", css())
        self.assertIsNotNone(m)
        self.assertTrue(360 <= int(m.group(1)) <= 400, m.group(1))

    def test_full_height(self):
        w = flat(top(".win"))
        for bit in ("right:12px", "top:12px", "bottom:12px", "width:var(--msg-w)"):
            self.assertIn(bit, w, bit)

    def test_history_takes_what_is_left_and_scrolls(self):
        c = top(".chat")
        self.assertIn(decl(c, "max-height"), (None, "none"), "no 220 px cap")
        self.assertEqual(decl(c, "min-height"), "0")
        self.assertEqual(decl(c, "overflow") or decl(c, "overflow-y"), "auto")
        f = decl(c, "flex")
        self.assertIsNotNone(f, ".chat has a flex")
        parts = f.split() if " " in (f or "") else re.findall(r"\d+(?:\.\d+)?%?|auto|none", f)
        self.assertNotEqual(parts[0], "0", "it grows to fill the panel")
        self.assertFalse(len(parts) > 1 and parts[1] == "0", "it shrinks")

    def test_box_and_send_on_one_line(self):
        s = top(".say")
        self.assertEqual(decl(s, "display"), "flex")
        self.assertNotEqual(decl(s, "flex-direction"), "column")
        t = top(".say textarea")
        self.assertTrue((decl(t, "flex") or "").startswith("1") or decl(t, "flex-grow") == "1", "the box takes the room")
        self.assertEqual(decl(t, "min-width"), "0")
        self.assertEqual(decl(t, "resize"), "none")
        for prop in ("min-height", "height"):
            v = px(decl(t, prop))
            self.assertIsNotNone(v, prop)
            self.assertLessEqual(v, 40, prop + ": one line")
        b = flat(top(".say .btn"))
        self.assertTrue("white-space:nowrap" in b or "flex:none" in b, "发送 never wraps")

    def test_new_message_chip_just_above_the_row(self):
        for where, block in (("computer", top(".newmsg")), ("phone", rule(".newmsg", media_960()) or top(".newmsg"))):
            with self.subTest(where=where):
                v = px(decl(block, "bottom"))
                self.assertIsNotNone(v)
                self.assertLessEqual(v, 80)

    def test_phone_sheet_stays(self):
        self.assertEqual(decl(rule(".win", media_960()), "top"), "auto", "still a bottom sheet")

    def test_phone_history_never_collapses(self):
        v = px(decl(rule(".chat", media_960()), "min-height"))
        self.assertIsNotNone(v, "@media (max-width: 960px) .chat{min-height:...}")
        self.assertGreaterEqual(v, 80)


# ---------------------------------------------------------------------------
# C2: main messages only, one toggle for the rest
# ---------------------------------------------------------------------------

C2_DRIVER = r"""
const texts = ['<task-notification>\n<task-id>b1</task-id>', '  <agent-message from="x">hi</agent-message>',
  'Another Claude session sent a message:\n<agent-message from="a2">done</agent-message>', '<teammate-message teammate_id="w">x',
  '<system-reminder>x</system-reminder>', '<command-name>/loop</command-name>', '<command-message>loop</command-message>',
  '<local-command-stdout>ok</local-command-stdout>', '<bash-input>ls</bash-input>', '<user-prompt-submit-hook>x',
  '[Request interrupted by user]', 'This session is being continued from a previous conversation that ran out of context.',
  'fix the login page', '<pasted_content id="1">notes</pasted_content> use these', 'please look at <task-notification> handling',
  'Main manager: go', '', 'x'];
const machine = texts.map(t => isMachinePrompt(t));
const E = [
  { id: 1, kind: 'prompt', text: 'fix the login page', at: 1 },
  { id: 2, kind: 'reply', text: 'fixed', at: 2 },
  { id: 3, kind: 'prompt', text: '<task-notification>\n<task-id>b1</task-id>', at: 3 },
  { id: 4, kind: 'reply', text: 'worker done, checking', at: 4 },
  { id: 5, kind: 'owner', text: 'stop for now', at: 5, state: 'delivered' },
  { id: 6, kind: 'reply', text: 'stopped', at: 6 },
  { id: 7, kind: 'prompt', text: 'Another Claude session sent a message:\n<agent-message from="m">go</agent-message>', at: 7 },
  { id: 8, kind: 'reply', text: 'ok manager', at: 8 },
];
const frozen = JSON.stringify(E);
const session = markMain(E, false).map(e => [e.id, e.main]);
const sub = markMain([{ id: 9, kind: 'reply', text: 'report', at: 1 }], true).map(e => e.main);
const first = markMain([{ id: 10, kind: 'reply', text: 'hello', at: 1 }], false).map(e => e.main);
const untouched = JSON.stringify(E) === frozen && !('main' in E[0]);
const c = { acts: [{ at: 0.5, text: '出门：x' }, { at: 2.5, text: '改代码 · 看文件' }], qa: [{ q: 'q?', a: 'a', at: 1.5 }], stuck: false, lead: '' };
const hist = personHistory(c, E).map(it => [it.k, it.main]);
const shown = mainOnly(personHistory(c, E)).map(it => it.k + ':' + (it.text || it.q));
const w = { acts: [], qa: [], stuck: false, lead: 's:L' };
const subHist = personHistory(w, [{ id: 11, kind: 'reply', text: 'report to lead', at: 1 }]).map(it => it.main);
const plain = mainOnly([{ k: 'x' }, { k: 'y', main: false }, { k: 'z', main: true }]).map(it => it.k);
__out = { machine, session, sub, first, untouched, hist, shown, subHist, plain, starts: MACHINE_STARTS };
"""


class TestMainMessages(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(C2_DRIVER, {}, ("isMachinePrompt", "markMain", "personHistory", "mainOnly", "MACHINE_STARTS"))

    def test_machine_prompts(self):
        self.assertEqual(self.r["machine"], [True] * 12 + [False] * 6)

    def test_starts_listed(self):
        for start in ("<task-notification", "<agent-message", "<teammate-message", "Another Claude session sent a message",
                      "<system-reminder", "<command-name", "<command-message", "<local-command-", "<bash-input",
                      "<user-prompt-submit-hook", "[Request interrupted",
                      "This session is being continued from a previous conversation"):
            with self.subTest(start=start):
                self.assertIn(start, self.r["starts"])

    def test_replies_follow_the_turn(self):
        self.assertEqual(self.r["session"], [[1, True], [2, True], [3, False], [4, False], [5, True], [6, True],
                                             [7, False], [8, False]])
        self.assertEqual(self.r["first"], [True], "a reply with no prompt before it shows")
        self.assertEqual(self.r["sub"], [False], "a subagent's reply is its report to its lead")
        self.assertTrue(self.r["untouched"], "markMain copies, never marks the chat store itself")

    def test_history_items_carry_main(self):
        self.assertEqual(self.r["hist"], [["act", False], ["prompt", True], ["ask", True], ["reply", True],
                                          ["act", False], ["prompt", False], ["reply", False], ["owner", True],
                                          ["reply", True], ["prompt", False], ["reply", False]])
        self.assertEqual(self.r["shown"], ["prompt:fix the login page", "ask:q?", "reply:fixed", "owner:stop for now",
                                           "reply:stopped"])
        self.assertEqual(self.r["subHist"], [False])
        self.assertEqual(self.r["plain"], ["x", "z"], "no main field counts as main")


class TestToggleDrawn(unittest.TestCase):

    def test_setting_is_remembered(self):
        text = re.sub(r"/\*.*?\*/", "", page(), flags=re.S)
        self.assertRegex(text, r"let\s+histAll\s*=\s*readStoredBool\(\s*'agent-city\.histAll'\s*,\s*false\s*\)")
        src = function_source("setHistAll") or ""
        self.assertTrue("writeStoredBool(" in src and "'agent-city.histAll'" in src, "setHistAll saves it")

    def test_detail_has_the_toggle_and_filters(self):
        src = function_source("renderDetail") or ""
        for bit in ('class="hist-all"', 'id="hist-all"', "aria-pressed", "hist.all", "hist.hide", "hist.onlyMech",
                    "mainOnly(", "markMain(", "histAll"):
            with self.subTest(bit=bit):
                self.assertTrue(bit in src, "renderDetail: " + bit)

    def test_click_toggles(self):
        blk = listener_block(r"(?:\$\('#detail'\)|detail|detailEl)", "click") or ""
        self.assertTrue("hist-all" in blk and "setHistAll(" in blk, "#detail click: #hist-all -> setHistAll(!histAll)")

    def test_badge_counts_what_shows(self):
        self.assertTrue("mainOnly(" in (function_source("winEntryCount") or ""), "winEntryCount counts the shown list")

    def test_texts(self):
        for key in ("hist.all", "hist.hide", "hist.onlyMech"):
            with self.subTest(key=key):
                self.assertEqual(text_keys(key), 2, key + " in zh and en")


if __name__ == "__main__":
    unittest.main()
