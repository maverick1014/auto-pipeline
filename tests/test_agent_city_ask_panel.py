"""Failing tests: city-ask-panel (owner, 2026-10-02, from a screenshot of the live city).

A session waited on a Bash permission. Its message panel said only 等你: the question and the buttons
were in the separate "?" dialog, reachable only from the small red "?" or the top 等你 button.
Now the open question or permission request is a card inside that person's own panel
(requirements/city.md, Interaction; approved mock mock/city-ask-panel-mock.html).

CONTRACT (bin/agent-city.html)

  Sim part (next to openAskId, before the 3D view):
  K1  let cardAskId = null       the id of the ask whose card is in the panel now, else null.
  K2  askPick(view) -> the selection that owns an ask: agent 'gov' -> {t:'gov', terr: view.terr}
      ({t:'gov'} when it has no terr); else {t:'c', id: view.agent} when byId(view.agent) is a person
      of this machine; null when nobody is on the page for it, or the person is another member's
      (c.remote).
  K3  panelAsk(sel) -> the ask whose card shows in the panel of selection `sel`, else null.
      {t:'c', id}: the asks with agent === id, only when byId(id) is a person of this machine.
      {t:'gov', terr}: the asks with agent 'gov' and terr === (sel.terr || govTerr).
      Only an ask in phase 'owner'. An open one (no .closed) wins over a closed one that still shows
      its result; among open ones the oldest (.at). Anything else (null, a building, 'rg') -> null.
  K4  apply 'ask_closed': the view stays in `asks` (with .closed and .shownAt) when
      openAskId === ev.id OR cardAskId === ev.id, and the card is drawn again (renderAskCard());
      shown nowhere -> deleted, as before.
  K5  askAutoClose(nowMs): as before for the small panel; and ASK_CLOSE_MS after the card's result
      showed (view.shownAt) the view leaves `asks` and renderAskCard() runs. An open card never goes.

  Page part (next to renderAskPanel):
  K6  askCardHtml(view) -> '<section class="askcard" id="askcard" data-ask="<id>">': a head
      (.askcard-h: a title #askcard-title with tabindex="-1" and the text i18n('card.permission') 要权限
      or i18n('card.question') 在问你, then the 等你 pill), askWhyLine, the same body as the small panel
      (askPermissionBody / askQuestionBody), the foot line. A closed view: class "askcard done", the
      已关闭 pill and askClosedLine only -- no form, no buttons. New texts in zh AND en.
  K7  wireAskControls(root, view): the form and button wiring that renderAskPanel had, looked up inside
      `root` only (root.querySelector, never $('#...')), so the card and the small panel never mix.
      renderAskPanel calls it with $('#ask').
  K8  renderAskCard(): fills $('#askslot') with askCardHtml(panelAsk(selected)), or '' when there is
      none; sets cardAskId. The slot is rewritten only when its key changes (ask id + open or closed);
      the key is kept in slot.dataset.key, so a picked option or a typed reason is kept between frames
      and a rebuilt panel (a fresh slot) gets its card again. An open card is wired with
      wireAskControls(slot, view). When a card stops showing and its view was closed (and is not the
      small panel's, openAskId), that view leaves `asks`. No slot -> cardAskId = null. Cloud page: no card.
  K9  renderDetail: '<div id="askslot"></div>' right after the head block of the local person's card
      and of the governor's card (never in another member's card), and renderAskCard() on every call.
      The window head, the header rows and the counters are not touched.
  K10 askRoot(id) -> $('#askslot') when id && cardAskId === id, else $('#ask'). showAskFailure(text, id) and
      setAskControlsDisabled(on, id) work inside askRoot(id); decide() passes its id and draws the
      card again (renderAskCard()) after a result or a 409.
  K11 showAsk(id): what the red "?" ([data-open]) and the top 等你 button (#next) call. askPick(view) ->
      a person: selectPick(pick) unless selKey(selected) === selKey(pick) already (a second pick of the
      same person would stop the follow); then setWinFolded(false) when the panel is folded;
      then focus #askcard-title. Nobody to pick -> openAsk(id), the small panel as before.
      Nothing else calls openAsk().
  K12 CSS: .askcard{flex:none; max-height; overflow:auto} (the history scrolls under it) and
      .askcard .cmd{max-height; overflow:auto} (a long command scrolls inside it).

  Bounce 1 (task manager review, 2026-10-02):
  K8b The slot's key also carries who closed it and how (closed.by, closed.verb): a 409 first writes
      "someone else was first" (verb 'closed'); when the real facts arrive (ask_closed: allow / deny /
      answer) the card is drawn again with them. The small panel always did.
  K13 keepAskSlot(el, old): after renderDetail rebuilt the panel's html, the OLD #askslot node goes back
      in place of the fresh empty one (fresh.replaceWith(old)), so a picked option or a typed reason
      survives a rebuild too (a person's state changes while it walks to the hall). No fresh slot, no old
      one, or the same node -> nothing. renderDetail takes the old node (el.querySelector('#askslot'))
      before it rebuilds and calls keepAskSlot(el, <old>) right after, before renderAskCard().
      renderAskCard's own key decides whether the kept node is still right (another person's ask has
      another key, so it is rewritten).

  Bounce 2 (main manager's browser check, 2026-10-02, 1440x900): the card was capped at 261 px of 424,
  the deny-reason box and 批准 / 拒绝 were below its visible bottom; a gap under the card; the folder
  was a full scratch path on 4 lines.
  K14 The open card's parts: head (.askcard-h), then ONE main element, then the foot line.
      Permission: <div class="askcard-main">. Question: <form id="qform" class="askcard-main" novalidate>.
      Inside main, in this order, exactly two children:
        <div class="askcard-body">  why line + the details (they scroll when long):
                                    askPermissionDetail(view) inside <div class="perm">, or
                                    askQuestionFields(view) (the fieldsets with the options)
        <div class="askcard-acts">  what the owner clicks, always in sight: askPermissionActs()
                                    (the deny-reason field #reason + 批准 / 拒绝) or askQuestionActs()
                                    (发送回答 #send).
      New top-level functions: askPermissionDetail(view) (工具, the command / file / url, 它说, 目录; no
      field, no button), askPermissionActs(), askQuestionFields(view), askQuestionActs().
      askPermissionBody(view) and askQuestionBody(view) are built from them and give the small dialog
      what it had before (one .perm block / one form#qform with everything).
  K15 CSS, no percent and no max-height on the card (the percent was the 261 px cap):
        #askslot{flex:0 1 auto;min-height:0;display:flex;flex-direction:column}   the slot is the flex item of the panel
        #askslot:empty{display:none}                                              no doubled gap without a card
        .askcard{flex:0 1 auto;min-height:0;display:flex;flex-direction:column;overflow:hidden; + its look}
        .askcard-main{flex:0 1 auto;min-height:0;display:flex;flex-direction:column;gap}
        .askcard-body{flex:0 1 auto;min-height:48px;overflow:auto;display:flex;flex-direction:column;gap}
        .askcard-acts{flex:none;display:flex;flex-direction:column;gap}
        .detail:has(.askcard) .chat{flex:1 1 0;min-height:56px}   the card takes the free height first,
                                                                 the history keeps a strip
      The `.askcard .cmd` rule with its own max-height / overflow goes (one scroll area: the body).
  K16 shortDir(path, repo) -> the folder, short. repo = the ask's own repo (its git dir, ".../name/.git").
      Inside the repo: "name" or "name/<path inside>". Else under /Users/<u>/ or /home/<u>/: "~" or "~/<rest>".
      Then, when the result is longer than 48 characters: "…/" + its last two parts. '' -> ''.
      askPermissionDetail shows <code title="<full path>">shortDir(d.cwd, view.repo)</code> (both escaped).

  Bounce 3 (main manager's second browser check, phone 390x844): the bottom sheet is 44% of a small map,
  the slot (min-height:0) was squeezed to ONE line 26 px tall and 批准 was below the screen. A shrinking
  chain with min-height:0 has no floor, and CSS cannot say "never smaller than head + controls".
  K17 The floor is measured. const ASK_BODY_MIN = 48 (the body's CSS min-height).
      askCardFloor(cardH, bodyH) -> Math.round(cardH - bodyH + Math.min(bodyH, ASK_BODY_MIN)), never
      below 0: the card's natural height with its details cut down to 48 px (a closed card has no body:
      bodyH 0 -> its whole height).
      fitAskSlot(slot): no .askcard inside -> slot.style.minHeight = '' and slot.dataset.w = ''.
      Else, only when String(slot.clientWidth) !== slot.dataset.w or slot.style.minHeight is empty
      (a new card, or the width changed: the text wraps differently): set slot.style.minHeight = '' and
      slot.style.flex = 'none' (nothing squeezes the card now), read card.offsetHeight and
      body.offsetHeight (the .askcard-body; none -> 0), set slot.style.flex = '' again,
      slot.style.minHeight = askCardFloor(...) + 'px' and slot.dataset.w = that width.
      renderAskCard(): after it wrote a card (the key changed) it clears slot.style.minHeight (the new
      card is measured again), and on EVERY call that has a slot it ends with fitAskSlot(slot) -- also
      when the key did not change.
  K18 Phone: inside the FIRST "@media (max-width: 960px)" block, after its .win rule:
        .win:has(.askcard){height:auto;max-height:calc(100% - 16px)}
      While a card is open the sheet takes what its content needs, up to the whole map; above that the
      details scroll inside the card (down to 48 px), then the panel body scrolls.

Run: python3 -m unittest tests.test_agent_city_ask_panel </dev/null
"""

import os
import re
import sys
import unittest
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_page import (constants_prelude, function_source, inline_script, page_fns,  # noqa: E402
                                  run_node, style)
from test_agent_city_people import REQUIRED, run_sim, sim_section  # noqa: E402
from test_agent_city_polish import ASK_Q, named_view  # noqa: E402

VM_JS = r"""
const fs = require('fs'), vm = require('vm');
const { fns, driver, payload } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { __payload: payload, __out: null, console };
vm.createContext(box);
vm.runInContext(fns + '\n;\n' + driver, box);
process.stdout.write(JSON.stringify(box.__out));
"""


def run_vm(fns, driver, payload=None):
    return run_node(VM_JS, {"fns": fns, "driver": driver, "payload": payload or {}})


def esc_source():
    m = re.search(r"^const esc = .*$", inline_script(), re.M)
    if not m:
        raise AssertionError("const esc = ... not found in the page script")
    return "var esc" + m.group(0)[len("const esc"):]


PERM = {"id": "p1", "agent": "gov", "terr": "tA", "label": "", "task": "", "kind": "permission", "phase": "owner",
        "why": "permission", "wait": 60, "left": 0, "tool": "Bash", "what": "Bash: osascript", "at": 1000,
        "detail": {"command": "osascript -e 'tell application \"Google Chrome\"' <b>x</b>",
                   "description": "Give the owner his own tab back", "cwd": "/Users/me/repo"}}
QUESTION = {"id": "q7", "agent": "s:tm1", "terr": "tA", "label": "task-manager", "task": "cloud-polish",
            "kind": "question", "phase": "owner", "why": "pass", "wait": 60, "left": 0, "tool": "AskUserQuestion",
            "what": "left or top?", "at": 2000,
            "questions": [{"question": "left or top?", "header": "head", "multiSelect": False,
                           "options": [{"label": "left", "description": "on the map"},
                                       {"label": "top", "description": "one bar"}]}]}


class TestPanelAskK3(unittest.TestCase):

    PRELUDE = r"""
var govTerr = 'tA';
var people = { w1: { id: 'w1' }, 's:tm1': { id: 's:tm1' }, r1: { id: 'r1', remote: { who: 'x', device: 'd' } } };
function byId(id){ return people[id] || null; }
var asks = new Map();
function put(a){ asks.set(a.id, a); }
function idOf(v){ return v ? v.id : null; }
"""

    def ask(self, driver):
        return run_vm(self.PRELUDE + page_fns("panelAsk"), driver)

    def test_a_person_with_an_ask_at_the_owner(self):
        out = self.ask(r"""
put({ id: 'a1', agent: 'w1', phase: 'owner', at: 5 });
put({ id: 'a2', agent: 's:tm1', phase: 'owner', at: 6 });
__out = [idOf(panelAsk({ t: 'c', id: 'w1' })), idOf(panelAsk({ t: 'c', id: 's:tm1' }))];
""")
        self.assertEqual(out, ["a1", "a2"], "each person's panel gets its own ask")

    def test_nothing_while_the_governor_still_decides(self):
        out = self.ask(r"""
put({ id: 'a1', agent: 'w1', phase: 'governor', at: 5 });
__out = idOf(panelAsk({ t: 'c', id: 'w1' }));
""")
        self.assertIsNone(out, "only an ask with the owner has something to answer")

    def test_the_governor_by_territory(self):
        out = self.ask(r"""
put({ id: 'gA', agent: 'gov', terr: 'tA', phase: 'owner', at: 5 });
put({ id: 'gB', agent: 'gov', terr: 'tB', phase: 'owner', at: 6 });
__out = [idOf(panelAsk({ t: 'gov', terr: 'tA' })), idOf(panelAsk({ t: 'gov', terr: 'tB' })),
         idOf(panelAsk({ t: 'gov' })), idOf(panelAsk({ t: 'gov', terr: 'tC' }))];
""")
        self.assertEqual(out, ["gA", "gB", "gA", None], "'gov' is shared: the ask's own terr picks the governor")

    def test_open_wins_over_closed_and_the_oldest_open_first(self):
        out = self.ask(r"""
put({ id: 'done', agent: 'w1', phase: 'owner', at: 1, closed: { by: 'owner', verb: 'allow' } });
const onlyClosed = idOf(panelAsk({ t: 'c', id: 'w1' }));
put({ id: 'late', agent: 'w1', phase: 'owner', at: 9 });
put({ id: 'early', agent: 'w1', phase: 'owner', at: 4 });
__out = [onlyClosed, idOf(panelAsk({ t: 'c', id: 'w1' }))];
""")
        self.assertEqual(out[0], "done", "a closed ask still in `asks` shows its result")
        self.assertEqual(out[1], "early", "an open ask wins over a closed one, the oldest open first")

    def test_nobody_and_view_only_people_get_none(self):
        out = self.ask(r"""
put({ id: 'a1', agent: 'r1', phase: 'owner', at: 5 });
put({ id: 'a2', agent: 'ghost', phase: 'owner', at: 5 });
__out = [idOf(panelAsk(null)), idOf(panelAsk({ t: 'b', id: 'w1' })), idOf(panelAsk({ t: 'rg', id: 'w1' })),
         idOf(panelAsk({ t: 'c', id: 'r1' })), idOf(panelAsk({ t: 'c', id: 'ghost' }))];
""")
        self.assertEqual(out, [None, None, None, None, None],
                         "no selection, a building, a remote governor, another member's person, nobody on the page")


class TestAskPickK2(unittest.TestCase):

    def test_who_owns_an_ask(self):
        out = run_vm(TestPanelAskK3.PRELUDE + page_fns("askPick"), r"""
__out = [askPick({ agent: 'gov', terr: 'tB' }), askPick({ agent: 'gov', terr: '' }), askPick({ agent: 'gov' }),
         askPick({ agent: 'w1', terr: 'tA' }), askPick({ agent: 's:tm1' }), askPick({ agent: 'ghost' }),
         askPick({ agent: 'r1' })];
""")
        self.assertEqual(out[0], {"t": "gov", "terr": "tB"})
        self.assertEqual(out[1], {"t": "gov"})
        self.assertEqual(out[2], {"t": "gov"})
        self.assertEqual(out[3], {"t": "c", "id": "w1"})
        self.assertEqual(out[4], {"t": "c", "id": "s:tm1"})
        self.assertIsNone(out[5], "nobody on the page for it")
        self.assertIsNone(out[6], "another member's person is view only")


class TestAskCardHtmlK6(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        fns = (constants_prelude() + "\n" + esc_source() + "\n"
               + page_fns("askCardHtml", "askWhyLine", "askQuestionBody", "askPermissionBody", "askClosedLine",
                          "askPermissionDetail", "askPermissionActs", "askQuestionFields", "askQuestionActs",
                          "shortDir"))
        closed = dict(PERM, closed={"by": "owner", "verb": "allow", "text": "", "reason": "", "at": 1790000000000})
        cls.perm, cls.question, cls.closed = run_vm(
            fns, "__out = [askCardHtml(__payload.p), askCardHtml(__payload.q), askCardHtml(__payload.c)];",
            {"p": PERM, "q": QUESTION, "c": closed})

    def test_the_card_frame(self):
        for name, html, ask_id in (("permission", self.perm, "p1"), ("question", self.question, "q7")):
            with self.subTest(kind=name):
                tag = re.match(r"\s*<section[^>]*>", html)
                self.assertIsNotNone(tag, "the card is one <section>")
                for bit in ('class="askcard"', 'id="askcard"', 'data-ask="%s"' % ask_id):
                    self.assertIn(bit, tag.group(0))
                self.assertIn('class="askcard-h"', html)
                self.assertRegex(html, r'id="askcard-title"[^>]*tabindex="-1"|tabindex="-1"[^>]*id="askcard-title"')
                self.assertIn("等你", html, "the 等你 pill")
                self.assertIn("终端里也能答", html, "the foot line: the terminal can answer too")

    def test_a_permission_shows_the_request_and_both_buttons(self):
        h = self.perm
        self.assertIn("要权限", h)
        self.assertIn("权限只由你来批", h, "why it is with the owner")
        self.assertIn("Bash", h)
        self.assertIn("osascript -e", h, "the exact command")
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", h, "the command is text, never markup")
        self.assertNotIn("<b>x</b>", h)
        self.assertIn("Give the owner his own tab back", h, "what it said")
        self.assertIn("/Users/me/repo", h, "the folder")
        self.assertIn('data-verb="allow"', h)
        self.assertIn('data-verb="deny"', h)
        self.assertIn('id="reason"', h, "the deny reason")

    def test_a_question_shows_its_options_and_send(self):
        h = self.question
        self.assertIn("在问你", h)
        self.assertIn('id="qform"', h)
        self.assertIn("left or top?", h)
        for label in ("left", "top", "on the map", "one bar"):
            self.assertIn(label, h)
        self.assertIn("data-other", h, "the write-your-own answer")
        self.assertIn("发送回答", h)
        self.assertNotIn("data-verb", h)

    def test_a_closed_card_shows_only_the_result(self):
        h = self.closed
        tag = re.match(r"\s*<section[^>]*>", h).group(0)
        self.assertRegex(tag, r'class="askcard done"')
        self.assertIn("已关闭", h)
        self.assertIn("批准了", h)
        for gone in ("data-verb", 'id="qform"', 'id="reason"', "osascript"):
            self.assertNotIn(gone, h, "a closed card has nothing left to click")

    def test_the_new_words_are_in_both_languages(self):
        text = inline_script()
        for key in ("card.permission", "card.question"):
            self.assertEqual(len(re.findall(r"'%s': '" % re.escape(key), text)), 2, key + " in zh and en")


class TestRenderAskCardK8(unittest.TestCase):

    PRELUDE = r"""
var selected = { t: 'c', id: 'w1' }, cardAskId = null, openAskId = null;
var asks = new Map();
var current = null;
function panelAsk(sel){ return sel ? current : null; }
function askCardHtml(v){ return '<card ' + v.id + (v.closed ? ' closed' : ' open') + '>'; }
var wired = [];
function wireAskControls(root, v){ wired.push([root === slot ? 'slot' : 'other', v.id]); }
function mkSlot(){
  return { dataset: {}, style: { minHeight: 'old' }, clientWidth: 348, sets: 0, _h: '',
           get innerHTML(){ return this._h; }, set innerHTML(v){ this._h = v; this.sets++; },
           querySelector(){ return null; }, querySelectorAll(){ return []; } };
}
var fits = [];
function fitAskSlot(s){ fits.push(s === slot ? s.style.minHeight : 'other'); }
var slot = mkSlot();
function $(sel){ return sel === '#askslot' ? slot : null; }
"""

    def run_card(self, driver):
        return run_vm(self.PRELUDE + page_fns("renderAskCard"), driver)

    def test_the_card_is_written_once_and_kept_between_frames(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard(); renderAskCard(); renderAskCard();
__out = { html: slot.innerHTML, sets: slot.sets, card: cardAskId, wired };
""")
        self.assertEqual(r["html"], "<card p1 open>")
        self.assertEqual(r["sets"], 1, "a picked option or a typed reason must survive the next frames")
        self.assertEqual(r["card"], "p1")
        self.assertEqual(r["wired"], [["slot", "p1"]], "wired once, inside the slot")

    def test_a_result_redraws_the_card(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();
current.closed = { by: 'terminal', verb: 'allow' };
renderAskCard(); renderAskCard();
__out = { html: slot.innerHTML, sets: slot.sets, card: cardAskId };
""")
        self.assertEqual(r["html"], "<card p1 closed>")
        self.assertEqual(r["sets"], 2)
        self.assertEqual(r["card"], "p1", "the closed card still shows its result")

    def test_the_real_facts_replace_someone_else_was_first(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();
current.closed = { by: 'terminal', verb: 'closed' };   // a 409: only "someone else was first" is known
renderAskCard();
const after409 = slot.sets;
current.closed = { by: 'terminal', verb: 'allow' };    // ask_closed arrives with the facts
renderAskCard(); renderAskCard();
const afterFacts = slot.sets;
current.closed = { by: 'governor', verb: 'allow' };
renderAskCard();
__out = { after409, afterFacts, afterWho: slot.sets };
""")
        self.assertEqual(r, {"after409": 2, "afterFacts": 3, "afterWho": 4},
                         "bounce 1 K8b: the key carries closed.by and closed.verb")

    def test_every_call_fits_the_slot_and_a_new_card_is_measured_again(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();                       // the card is written: the old floor is cleared before the fit
slot.style.minHeight = '272px';        // (what the real fitAskSlot would leave)
renderAskCard(); renderAskCard();      // same key: nothing rewritten, the floor is kept, the fit still runs
const kept = fits.slice();
current.closed = { by: 'owner', verb: 'allow' };
renderAskCard();                       // another card (the result): measured again
__out = { kept, afterResult: fits[fits.length - 1], n: fits.length };
""")
        self.assertEqual(r["kept"], ["", "272px", "272px"], "bounce 3 K17: fitAskSlot(slot) on every call")
        self.assertEqual(r["afterResult"], "", "a newly written card clears the old floor first")
        self.assertEqual(r["n"], 4)

    def test_a_rebuilt_panel_gets_its_card_again(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();
slot = mkSlot();           // renderDetail rebuilt the panel: a fresh, empty slot
renderAskCard();
__out = { html: slot.innerHTML, sets: slot.sets };
""")
        self.assertEqual(r, {"html": "<card p1 open>", "sets": 1}, "the key lives on the slot (slot.dataset.key)")

    def test_no_ask_empties_the_slot(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();
current = null;
renderAskCard();
__out = { html: slot.innerHTML, card: cardAskId, kept: asks.has('p1') };
""")
        self.assertEqual(r["html"], "")
        self.assertIsNone(r["card"])
        self.assertTrue(r["kept"], "an OPEN ask is never dropped because another person was picked")

    def test_a_closed_view_leaves_asks_when_its_card_stops_showing(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner', closed: { by: 'owner', verb: 'deny' } }; asks.set('p1', current);
renderAskCard();
current = null;
renderAskCard();
const cardGone = asks.has('p1');
current = { id: 'p2', agent: 'w1', phase: 'owner', closed: { by: 'owner', verb: 'deny' } }; asks.set('p2', current);
openAskId = 'p2';          // the small panel shows this one too: it keeps the view
renderAskCard();
current = null;
renderAskCard();
__out = { cardGone, panelKept: asks.has('p2') };
""")
        self.assertFalse(r["cardGone"], "nothing shows the result any more: the view goes")
        self.assertTrue(r["panelKept"], "the small panel still shows it")

    def test_no_slot_no_card(self):
        r = self.run_card(r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();
slot = null;               // the panel is closed, or it is a building's card
renderAskCard();
__out = { card: cardAskId, kept: asks.has('p1') };
""")
        self.assertEqual(r, {"card": None, "kept": True})

    def test_the_cloud_page_never_shows_a_card(self):
        r = run_vm(self.PRELUDE + page_fns("renderAskCard").replace("var CLOUD = false;", "var CLOUD = true;"), r"""
current = { id: 'p1', agent: 'w1', phase: 'owner' }; asks.set('p1', current);
renderAskCard();
__out = { html: slot.innerHTML, card: cardAskId };
""")
        self.assertEqual(r, {"html": "", "card": None})


class TestAskRootK10(unittest.TestCase):

    def test_where_an_ask_shows(self):
        out = run_vm("var cardAskId = 'p1'; function $(sel){ return sel; }\n" + page_fns("askRoot"),
                     "__out = [askRoot('p1'), askRoot('q7'), askRoot(undefined)];")
        self.assertEqual(out, ["#askslot", "#ask", "#ask"])
        none = run_vm("var cardAskId = null; function $(sel){ return sel; }\n" + page_fns("askRoot"),
                      "__out = [askRoot(null), askRoot(undefined), askRoot('p1')];")
        self.assertEqual(none, ["#ask", "#ask", "#ask"], "no card: everything goes to the small panel")

    def test_failure_line_and_disabling_follow_it(self):
        for fn in ("showAskFailure", "setAskControlsDisabled"):
            with self.subTest(fn=fn):
                src = function_source(fn) or ""
                self.assertIn("askRoot(", src)
                self.assertNotIn("$('#ask')", src, fn + " no longer goes to the small panel only")

    def test_decide_passes_its_id_and_redraws_the_card(self):
        src = function_source("decide") or ""
        self.assertIn("renderAskCard(", src)
        self.assertGreaterEqual(len(re.findall(r"setAskControlsDisabled\((?:true|false),\s*id\)", src)), 3)
        self.assertGreaterEqual(len(re.findall(r"showAskFailure\([^;]*,\s*id\);", src)), 2)


class TestShowAskK11(unittest.TestCase):

    PRELUDE = r"""
var govTerr = 'tA', winFolded = false;
var selected = null;
var asks = new Map([['a1', { id: 'a1', agent: 'w1', phase: 'owner' }], ['g1', { id: 'g1', agent: 'gov', terr: 'tA', phase: 'owner' }],
                    ['x1', { id: 'x1', agent: 'ghost', phase: 'owner' }]]);
var people = { w1: { id: 'w1' } };
function byId(id){ return people[id] || null; }
var calls = [];
function selectPick(pk){ calls.push(['pick', pk]); selected = pk; winFolded = false; }
function openAsk(id){ calls.push(['dialog', id]); }
function setWinFolded(v){ calls.push(['fold', v]); winFolded = v; }
function renderPanel(){}
function renderAskCard(){}
var needFrame = false;
function $(sel){ return { focus(){ calls.push(['focus', sel]); } }; }
"""

    def run_show(self, driver):
        return run_vm(self.PRELUDE + page_fns("showAsk", "askPick", "selKey"), driver)

    def test_it_opens_the_persons_own_panel(self):
        r = self.run_show("showAsk('a1'); __out = calls;")
        self.assertIn(["pick", {"t": "c", "id": "w1"}], r)
        self.assertNotIn(["dialog", "a1"], r, "no separate dialog for a person on the page")
        self.assertIn(["focus", "#askcard-title"], r)

    def test_the_governor(self):
        r = self.run_show("showAsk('g1'); __out = calls;")
        self.assertIn(["pick", {"t": "gov", "terr": "tA"}], r)
        self.assertEqual([c for c in r if c[0] == "dialog"], [])

    def test_the_same_person_is_not_picked_twice(self):
        r = self.run_show(r"""
selected = { t: 'c', id: 'w1' }; winFolded = true;
showAsk('a1');
const first = calls.slice();
calls = []; selected = { t: 'gov' };     // the home governor, picked without a terr
showAsk('g1');
__out = { first, second: calls };
""")
        self.assertEqual([c for c in r["first"] if c[0] == "pick"], [],
                         "a second pick of the same person would stop the follow")
        self.assertIn(["fold", False], r["first"], "a folded panel opens again")
        self.assertEqual([c for c in r["second"] if c[0] == "pick"], [], "{t:'gov'} is the home governor")
        self.assertEqual([c for c in r["second"] if c[0] == "fold"], [], "an open panel is left alone")

    def test_nobody_to_pick_falls_back_to_the_small_panel(self):
        r = self.run_show("showAsk('x1'); showAsk('nope'); __out = calls;")
        self.assertEqual(r, [["dialog", "x1"]], "as before for an ask with no person; an unknown id does nothing")

    def test_only_show_ask_opens_the_small_panel(self):
        text = inline_script()
        for fn in ("showAsk", "openAsk"):
            src = function_source(fn)
            self.assertIsNotNone(src, "function %s(...) not found" % fn)
            text = text.replace(src, "")
        self.assertNotIn("openAsk(", text, 'the red "?" and the 等你 button call showAsk()')
        self.assertGreaterEqual(text.count("showAsk("), 2, "both of them")


class TestPanelWiringK7K9K12(unittest.TestCase):

    def test_the_slot_is_in_the_person_card_and_the_governor_card(self):
        body = function_source("renderDetail") or ""
        self.assertEqual(body.count('<div id="askslot"></div>'), 2, "the local person's card and the governor's card")
        self.assertIn("renderAskCard(", body, "the card follows on every call")
        remote = body[body.index("c.remote) {"):body.index("} else if (c) {")]
        self.assertNotIn("askslot", remote, "another member's person is view only")
        person = body.index("} else if (c) {")
        gov = body.index("} else if (selected && selected.t === 'gov') {")
        for card in (body[person:body.index("selected.t === 'rg'", person)], body[gov:body.index("hint.noAgents", gov)]):
            self.assertLess(card.index("p-head"), card.index("askslot"))
            self.assertLess(card.index("askslot"), card.index("hist.title"), "between the head and the history")

    def test_one_wiring_for_the_card_and_the_small_panel(self):
        src = function_source("wireAskControls")
        self.assertIsNotNone(src, "function wireAskControls(root, view) not found")
        self.assertNotIn("$('#", src, "looked up inside root only")
        self.assertIn("root.querySelector", src)
        self.assertIn("decide(", src)
        panel = function_source("renderAskPanel") or ""
        self.assertIn("wireAskControls(", panel)
        self.assertNotIn("addEventListener('submit'", panel, "the wiring moved out")

    def test_the_controls_never_scroll_away(self):
        """Bounce 2 K15: the slot is the panel's flex item, the card shrinks, only its body scrolls."""
        css = style().replace(" ", "")

        def rule(selector):
            m = re.search(r"(?:^|\})" + re.escape(selector) + r"\{([^}]*)\}", css, re.M)
            self.assertIsNotNone(m, selector + " rule")
            return m.group(1)

        for bit in ("flex:01auto", "min-height:0", "display:flex", "flex-direction:column"):
            self.assertIn(bit, rule("#askslot"))
        self.assertIn("display:none", rule("#askslot:empty"))
        card = rule(".askcard")
        for bit in ("flex:01auto", "min-height:0", "display:flex", "flex-direction:column", "overflow:hidden"):
            self.assertIn(bit, card)
        self.assertNotIn("max-height", card, "the percent cap hid the buttons (261 px of 424)")
        self.assertNotIn("%", card)
        for bit in ("flex:01auto", "min-height:0", "display:flex", "flex-direction:column"):
            self.assertIn(bit, rule(".askcard-main"))
        for bit in ("flex:01auto", "min-height:48px", "overflow:auto"):
            self.assertIn(bit, rule(".askcard-body"), "only the details scroll")
        self.assertIn("flex:none", rule(".askcard-acts"), "the controls keep their height")
        chat = rule(".detail:has(.askcard).chat")
        for bit in ("flex:110", "min-height:56px"):
            self.assertIn(bit, chat, "the card takes the free height first, the history keeps a strip")
        self.assertNotRegex(css, r"\.askcard\.cmd\{[^}]*(?:max-height|overflow)", "one scroll area, the body")

    def test_the_card_state_lives_in_the_sim_part(self):
        self.assertRegex(sim_section(), r"\bcardAskId\s*=\s*null", "declared next to openAskId")


class Tree(HTMLParser):
    """A tiny DOM: nodes are dicts {tag, attrs, kids, parent, text}; void tags never open a level."""

    VOID = {"input", "br", "img", "hr", "meta", "link"}

    def __init__(self, html):
        super().__init__()
        self.root = {"tag": "#root", "attrs": {}, "kids": [], "parent": None, "text": ""}
        self.cur = self.root
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "kids": [], "parent": self.cur, "text": ""}
        self.cur["kids"].append(node)
        if tag not in self.VOID:
            self.cur = node

    def handle_endtag(self, tag):
        node = self.cur
        while node is not self.root and node["tag"] != tag:
            node = node["parent"]
        if node is not self.root:
            self.cur = node["parent"]

    def handle_data(self, data):
        node = self.cur
        while node:
            node["text"] += data
            node = node["parent"]

    def all(self, node=None):
        node = node or self.root
        for kid in node["kids"]:
            yield kid
            yield from self.all(kid)

    def one(self, test, what):
        found = [n for n in self.all() if test(n)]
        if len(found) != 1:
            raise AssertionError("%s: expected one, found %d" % (what, len(found)))
        return found[0]


def has_class(node, name):
    return name in (node["attrs"].get("class") or "").split()


def inside(node, name):
    node = node["parent"]
    while node:
        if has_class(node, name):
            return True
        node = node["parent"]
    return False


LONG_CMD = "echo " + " && echo ".join("line-%04d" % i for i in range(400))
LONG_DIR = "/private/tmp/claude-502/-Users-me-repo/a8712f6d-e725-4809-9737-067022907c06/scratchpad/deep/er"


class TestControlsAlwaysInSightK14(unittest.TestCase):
    """Bounce 2: the deny-reason box and the buttons are never inside the part that scrolls."""

    @classmethod
    def setUpClass(cls):
        fns = (constants_prelude() + "\n" + esc_source() + "\n"
               + page_fns("askCardHtml", "askWhyLine", "askQuestionBody", "askPermissionBody", "askClosedLine",
                          "askPermissionDetail", "askPermissionActs", "askQuestionFields", "askQuestionActs",
                          "shortDir"))
        long_perm = dict(PERM, repo="/Users/me/repo/.git",
                         detail={"command": LONG_CMD, "description": "x" * 300, "cwd": LONG_DIR})
        many = dict(QUESTION, questions=[dict(QUESTION["questions"][0],
                                              options=[{"label": "option %d" % i, "description": "d" * 80}
                                                       for i in range(12)])])
        out = run_vm(fns, "__out = [askCardHtml(__payload.p), askCardHtml(__payload.q), askPermissionBody(__payload.p),"
                          " askQuestionBody(__payload.q), askCardHtml(__payload.s)];",
                     {"p": long_perm, "q": many, "s": dict(PERM, repo="/Users/me/repo/.git")})
        cls.perm, cls.question, cls.dialog_perm, cls.dialog_question, cls.short_perm = out

    def parts(self, html):
        t = Tree(html)
        card = t.one(lambda n: has_class(n, "askcard"), ".askcard")
        main = t.one(lambda n: has_class(n, "askcard-main"), ".askcard-main")
        body = t.one(lambda n: has_class(n, "askcard-body"), ".askcard-body")
        acts = t.one(lambda n: has_class(n, "askcard-acts"), ".askcard-acts")
        self.assertIs(main["parent"], card, "main is a child of the card")
        self.assertEqual([k for k in main["kids"]], [body, acts], "main holds the body, then the controls, nothing else")
        tags = [k["tag"] for k in card["kids"]]
        self.assertEqual(len(card["kids"]), 3, "head, main, foot: %s" % tags)
        self.assertTrue(has_class(card["kids"][0], "askcard-h"))
        self.assertIs(card["kids"][1], main)
        self.assertTrue(has_class(card["kids"][2], "foot"))
        return t, main, body, acts

    def test_a_long_permission_keeps_its_controls_out_of_the_scroll(self):
        t, main, body, acts = self.parts(self.perm)
        self.assertEqual(main["tag"], "div")
        controls = [n for n in t.all() if n["attrs"].get("data-verb") or n["attrs"].get("id") == "reason"]
        self.assertEqual(sorted(n["attrs"].get("data-verb") or "reason" for n in controls), ["allow", "deny", "reason"])
        for n in controls:
            self.assertTrue(inside(n, "askcard-acts"), "always in sight")
            self.assertFalse(inside(n, "askcard-body"), "never in the part that scrolls")
        self.assertIn("line-0399", body["text"], "the whole long command is in the body")
        self.assertIn("权限只由你来批", body["text"], "the why line scrolls with the details")
        self.assertNotIn("line-0000", acts["text"])

    def test_a_question_with_many_options(self):
        t, main, body, acts = self.parts(self.question)
        self.assertEqual(main["tag"], "form", "the form holds both, so 发送回答 submits it")
        self.assertEqual(main["attrs"].get("id"), "qform")
        send = t.one(lambda n: n["attrs"].get("id") == "send", "#send")
        self.assertTrue(inside(send, "askcard-acts"))
        radios = [n for n in t.all() if n["attrs"].get("type") == "radio"]
        self.assertEqual(len(radios), 13, "12 options and the write-your-own one")
        for n in radios:
            self.assertTrue(inside(n, "askcard-body"), "the options scroll")
        self.assertEqual(len([n for n in t.all() if n["attrs"].get("id") == "qform"]), 1)

    def test_the_folder_is_short_with_the_full_path_on_hover(self):
        t = Tree(self.perm)
        code = t.one(lambda n: n["tag"] == "code" and n["attrs"].get("title") == LONG_DIR, "the folder <code>")
        self.assertEqual(code["text"], "…/deep/er")
        self.assertTrue(inside(code, "askcard-body"))
        t2 = Tree(self.short_perm)
        code2 = t2.one(lambda n: n["tag"] == "code" and n["attrs"].get("title") == "/Users/me/repo", "the folder <code>")
        self.assertEqual(code2["text"], "repo", "the repo's own folder is just its name")

    def test_the_small_dialog_keeps_everything_in_one_block(self):
        t = Tree(self.dialog_perm)
        self.assertEqual(len([n for n in t.all() if has_class(n, "perm")]), 1)
        verbs = sorted(n["attrs"]["data-verb"] for n in t.all() if n["attrs"].get("data-verb"))
        self.assertEqual(verbs, ["allow", "deny"])
        t.one(lambda n: n["attrs"].get("id") == "reason", "#reason")
        self.assertNotIn("askcard", self.dialog_perm)
        q = Tree(self.dialog_question)
        form = q.one(lambda n: n["attrs"].get("id") == "qform", "form#qform")
        self.assertEqual(form["tag"], "form")
        send = q.one(lambda n: n["attrs"].get("id") == "send", "#send")
        node = send
        while node and node is not form:
            node = node["parent"]
        self.assertIs(node, form, "发送回答 is inside the form")
        self.assertNotIn("askcard", self.dialog_question)


class TestShortDirK16(unittest.TestCase):

    def test_cases(self):
        repo = "/Users/me/work/auto-pipeline/.git"
        cases = [
            ["/Users/me/work/auto-pipeline", repo, "auto-pipeline"],
            ["/Users/me/work/auto-pipeline/bin/sub", repo, "auto-pipeline/bin/sub"],
            ["/Users/me/work/auto-pipeline-2/x", repo, "~/work/auto-pipeline-2/x"],
            ["/Users/me/orca/workspaces/auto-pipeline/city-ask-panel", repo, "~/orca/workspaces/auto-pipeline/city-ask-panel"],
            ["/Users/me", repo, "~"],
            ["/home/dev/src/app", "", "~/src/app"],
            ["/home/dev/src/app", None, "~/src/app"],
            [LONG_DIR, repo, "…/deep/er"],
            ["/Users/me/" + "/".join(["folder-%d" % i for i in range(8)]), repo, "…/folder-6/folder-7"],
            ["/opt/tool", repo, "/opt/tool"],
            ["", repo, ""],
        ]
        out = run_vm(page_fns("shortDir"), "__out = __payload.cases.map(c => shortDir(c[0], c[1]));", {"cases": cases})
        for case, got in zip(cases, out):
            with self.subTest(path=case[0]):
                self.assertEqual(got, case[2])


class TestCardFloorK17(unittest.TestCase):
    """Bounce 3: the card is never squeezed below its head, 48 px of details, its controls and its foot."""

    def test_the_floor(self):
        fns = constants_prelude() + "\n" + page_fns("askCardFloor")
        out = run_vm(fns, "__out = [askCardFloor(424, 200), askCardFloor(300, 30), askCardFloor(120, 0), "
                          "askCardFloor(0, 0), askCardFloor(271.6, 48), ASK_BODY_MIN];")
        self.assertEqual(out, [272, 300, 120, 0, 272, 48])
        self.assertRegex(style().replace(" ", ""), r"(?:^|\})\.askcard-body\{[^}]*min-height:48px",
                         "ASK_BODY_MIN is the body's CSS min-height")

    PRELUDE = r"""
var reads = [];
function mk(cardH, bodyH, width){
  const slot = { style: { minHeight: '', flex: '' }, dataset: {}, clientWidth: width };
  const card = cardH === null ? null : { get offsetHeight(){ reads.push([slot.style.flex, slot.style.minHeight]); return cardH; } };
  const body = bodyH === null ? null : { offsetHeight: bodyH };
  slot.querySelector = sel => sel === '.askcard' ? card : (sel === '.askcard-body' ? body : null);
  return slot;
}
"""

    def fit(self, driver):
        return run_vm(constants_prelude() + "\n" + self.PRELUDE + page_fns("fitAskSlot", "askCardFloor"), driver)

    def test_it_measures_the_card_unsqueezed(self):
        r = self.fit(r"""
const slot = mk(424, 200, 348);
slot.style.minHeight = '26px';
slot.dataset.w = '';
fitAskSlot(slot);
__out = { min: slot.style.minHeight, flex: slot.style.flex, w: slot.dataset.w, reads };
""")
        self.assertEqual(r["min"], "272px")
        self.assertEqual(r["flex"], "", "the inline flex is taken off again")
        self.assertEqual(r["w"], "348")
        self.assertEqual(r["reads"], [["none", ""]], "measured with flex:none and no old floor: its natural height")

    def test_once_per_width(self):
        r = self.fit(r"""
const slot = mk(424, 200, 348);
fitAskSlot(slot); fitAskSlot(slot); fitAskSlot(slot);
const same = reads.length;
slot.clientWidth = 300;                // the phone turned: the text wraps differently
fitAskSlot(slot);
const turned = reads.length;
slot.style.minHeight = '';             // renderAskCard wrote another card
fitAskSlot(slot);
__out = { same, turned, again: reads.length, w: slot.dataset.w };
""")
        self.assertEqual(r, {"same": 1, "turned": 2, "again": 3, "w": "300"})

    def test_a_closed_card_and_no_card(self):
        r = self.fit(r"""
const closed = mk(96, null, 348);
fitAskSlot(closed);
const none = mk(null, null, 348);
none.style.minHeight = '272px'; none.dataset.w = '348';
fitAskSlot(none);
__out = { closed: closed.style.minHeight, none: none.style.minHeight, w: none.dataset.w };
""")
        self.assertEqual(r, {"closed": "96px", "none": "", "w": ""}, "a result card is never cut; no card, no floor")

    def test_the_sheet_grows_on_a_phone(self):
        from test_agent_city_page import media_block
        block = media_block("@media (max-width: 960px)").replace(" ", "")
        m = re.search(r"\.win:has\(\.askcard\)\{([^}]*)\}", block)
        self.assertIsNotNone(m, "bounce 3 K18: .win:has(.askcard) in the first phone block")
        for bit in ("height:auto", "max-height:calc(100%-16px)"):
            self.assertIn(bit, m.group(1))
        self.assertLess(block.index(".win{"), m.start(), "after the sheet's own .win rule")


class TestKeepAskSlotK13(unittest.TestCase):
    """Bounce 1: a rebuild of the panel keeps the card's node, so nothing typed or picked is lost."""

    PRELUDE = r"""
function node(name){ return { name, swaps: [], replaceWith(o){ this.swaps.push(o.name); } }; }
function panel(fresh){ return { querySelector(sel){ return sel === '#askslot' ? fresh : null; } }; }
"""

    def test_the_old_node_goes_back(self):
        r = run_vm(self.PRELUDE + page_fns("keepAskSlot"), r"""
const fresh = node('fresh'), old = node('old');
keepAskSlot(panel(fresh), old);
const none = node('fresh2');
keepAskSlot(panel(none), null);
const same = node('same');
keepAskSlot(panel(same), same);
keepAskSlot(panel(null), node('orphan'));
__out = { swapped: fresh.swaps, none: none.swaps, same: same.swaps };
""")
        self.assertEqual(r["swapped"], ["old"], "fresh.replaceWith(old)")
        self.assertEqual(r["none"], [], "nothing to keep on a first open")
        self.assertEqual(r["same"], [], "no rebuild happened")

    def test_render_detail_keeps_it_across_a_rebuild(self):
        body = function_source("renderDetail") or ""
        rebuild = body.index("if (key !== lastDetailKey) {")
        self.assertRegex(body[:rebuild], r"el\.querySelector\('#askslot'\)", "the old node is taken before the rebuild")
        keep, card = body.find("keepAskSlot(el,"), body.find("renderAskCard(")
        self.assertGreater(keep, rebuild, "put back after the rebuild")
        self.assertLess(keep, card, "before renderAskCard() looks at the slot")


class TestResultThenFoldK4K5(unittest.TestCase):

    DRIVER = r"""
function buildLand(view){ landState(view); }
let __cards = 0;
function renderAskCard(){ __cards++; }
function renderAskPanel(){}
function closeAskPanel(){ openAskId = null; }
{   // a block: the driver's own names never meet the page's
  const V = __payload.view, ask = __payload.ask;
  const idOf = v => (v ? v.id : null);
  const snap = () => apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: ask.terr }, govs: [{ terr: ask.terr, state: 'busy' }],
    governors: 1, asks: [ask], shows: [], agents: [] });
  const closeIt = () => apply({ type: 'ask_closed', id: ask.id, agent: 'gov', kind: 'question', tool: 'AskUserQuestion', what: ask.what,
    by: 'terminal', verb: 'answer', text: 'red', reason: '', at: 2000 });
  snap();
  closeIt();
  const nowhere = asks.has(ask.id);
  snap();
  cardAskId = ask.id;
  askAutoClose(50000);
  const openStays = asks.has(ask.id);
  __cards = 0;
  closeIt();
  const kept = asks.has(ask.id), v = asks.get(ask.id);
  const closed = !!(v && v.closed && v.closed.by === 'terminal' && typeof v.shownAt === 'number');
  const redrawn = __cards;
  const shown = idOf(panelAsk({ t: 'gov', terr: ask.terr }));
  askAutoClose(9999);
  const at9 = asks.has(ask.id);
  __cards = 0;
  askAutoClose(10000);
  __out = { nowhere, openStays, kept, closed, redrawn, shows: shown, at9, at10: asks.has(ask.id), folded: __cards };
}
"""

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(cls.DRIVER, {"view": named_view(), "ask": ASK_Q},
                        REQUIRED + ("askAutoClose", "ASK_CLOSE_MS", "panelAsk", "cardAskId"))

    def test_run(self):
        self.assertNotIn("fatal", self.r, self.r)

    def test_shown_nowhere_is_deleted_as_before(self):
        self.assertFalse(self.r["nowhere"])

    def test_an_open_card_never_goes_by_itself(self):
        self.assertTrue(self.r["openStays"])

    def test_a_close_keeps_the_view_while_its_card_shows(self):
        self.assertTrue(self.r["kept"], "answered in the terminal first: the card says so")
        self.assertTrue(self.r["closed"])
        self.assertGreaterEqual(self.r["redrawn"], 1, "the card is drawn again at once")
        self.assertEqual(self.r["shows"], ASK_Q["id"], "the panel still shows it, as a result")

    def test_the_result_stays_10s_then_the_card_goes(self):
        self.assertTrue(self.r["at9"])
        self.assertFalse(self.r["at10"])
        self.assertGreaterEqual(self.r["folded"], 1, "the slot is emptied")


if __name__ == "__main__":
    unittest.main()
