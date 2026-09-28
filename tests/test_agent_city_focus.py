"""Failing tests for city-focus (requirements/city.md, Look and Balance;
owner, 2026-09-27): the city fills the page, a window opens over it on a
click, and nothing lists, scores or asks for the 5 kinds. The server side
(eras by size only, no "next") is in tests/test_agent_city_balance.py.

CONTRACT (bin/agent-city.html)

  Gone, with everything that only served them:
    the right column <aside class="panel" id="panel"> and its cards
      (data-card, .card-head, drag to reorder, the 'agent-city-cards'
      storage key); the 市民 roster (#roster, renderRoster); the 城市平衡
      card (#balance, renderBalance, balanceHtml, kindBar, openBalanceKind);
      the 还差 sign (signText, .era-sign, landOverlays makes no sign).
    The page says 还差 and 城市平衡 nowhere. No CSS grid column of 360px.

  The window, over the city:
    <div class="win" id="win" role="dialog" aria-labelledby="win-title"
      hidden> inside #stage. Inside it: an element id="win-title", a
      <button type="button" id="win-close" aria-label="关闭">, and the two
      bodies #detail (what was clicked) and #log (the page log, 动态).
    .win is position:absolute; the @media (max-width: 960px) block has a
      .win rule (a phone gets a window that fits).
    Phone: the city fills the screen below the top bar too. The phone
      block gives .stage-col and .stage flex:1 and no fixed 66vh height
      (E2E 2026-09-27: a third of a 390 x 844 screen stayed blank, the
      room the right column used to take under the city). The canvas never
      sizes the stage there (.stage canvas position:absolute, the stage
      flex:1 1 0), or its drawing size feeds back into the layout and the
      page scrolls (second E2E: the canvas ran 76 px past an 844 px screen).
    <button type="button" id="logbtn"> with the text 动态, in header.bar
      next to the top counts.

  State (top level):
    let winLog = false;  true while the window shows the page log.
    winState() -> 'log' when winLog, 'detail' when something is selected,
      else null.
    openLog(): winLog = true, selected = null, then renderPanel().
    closeWin(): winLog = false, selected = null, then renderPanel().
    selectFrom(val) (the existing picker for rows) also sets winLog = false.
    A tap on the canvas (endPointer's tap branch) sets winLog = false, so a
      tap on a person opens its window and a tap on empty ground (pickAt ->
      null) closes the window.
    renderPanel() calls renderWin(), never renderRoster or renderBalance.
    renderWin() sets $('#win').hidden = !winState(), shows #detail only for
      'detail' and #log only for 'log' (their .hidden), and sets #win-title
      (动态 for the log).
    Clicks: #win-close -> closeWin(); #logbtn -> openLog(); a [data-sel]
      row inside #detail -> selectFrom(its data-sel) (the governor's window
      lists its people through rosterGroups(), each row a data-sel).

Run: python3 -m unittest tests.test_agent_city_focus </dev/null
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_page import (function_source, inline_script, markup, media_block,  # noqa: E402
                                  page, page_fns, run_node, style, zh_resolved)


GONE_FUNCTIONS = ("renderRoster", "renderBalance", "balanceHtml", "kindBar", "openBalanceKind", "signText")


class TestGone(unittest.TestCase):
    def test_no_right_column(self):
        text = page()
        for needle in ('id="panel"', "data-card=", 'class="card-head"', 'id="roster"', 'id="balance"',
                       "agent-city-cards"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)

    def test_nothing_asks_for_a_kind(self):
        text = page()
        for word in ("还差", "城市平衡", "era-sign"):
            with self.subTest(word=word):
                self.assertNotIn(word, text)

    def test_the_old_functions_are_gone(self):
        for name in GONE_FUNCTIONS:
            with self.subTest(fn=name):
                self.assertIsNone(function_source(name), name + " is still in the page")

    def test_no_side_column_in_the_css(self):
        self.assertIsNone(re.search(r"grid-template-columns:[^;}]*360px", style()),
                          "a 360px column is still in the layout")

    def test_land_overlays_make_no_sign(self):
        body = function_source("landOverlays") or ""
        self.assertTrue(body, "landOverlays(view) not found")
        for needle in ("era-sign", "signText", "signs"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, body)


def win_block():
    m = re.search(r'<div class="win" id="win"[^>]*>', markup())
    if not m:
        return None, ""
    text = markup()
    depth, i = 0, m.start()
    for tag in re.finditer(r"<(/?)div\b[^>]*>", text[m.start():]):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return m.group(0), text[m.start():m.start() + tag.end()]
    return m.group(0), text[m.start():]


class TestWindowMarkup(unittest.TestCase):
    def test_window_over_the_city(self):
        open_tag, block = win_block()
        self.assertIsNotNone(open_tag, '<div class="win" id="win" ...> not found')
        for attr in ('role="dialog"', 'aria-labelledby="win-title"', "hidden"):
            with self.subTest(attr=attr):
                self.assertIn(attr, open_tag)
        stage = re.search(r'id="stage"', markup())
        self.assertIsNotNone(stage)
        self.assertLess(stage.start(), markup().index('id="win"'))

    def test_window_holds_title_close_detail_and_log(self):
        _, block = win_block()
        block = zh_resolved(block)  # idea-city C1: aria-label text may come from TEXT (data-t-aria)
        self.assertIn('id="win-title"', block)
        self.assertRegex(block, r'<button type="button"[^>]*id="win-close"[^>]*aria-label="关闭"|'
                                r'<button type="button"[^>]*aria-label="关闭"[^>]*id="win-close"')
        self.assertIn('id="detail"', block)
        self.assertIn('id="log"', block)

    def test_window_css(self):
        self.assertRegex(style(), r"\.win\{[^}]*position:absolute")
        self.assertIn(".win", media_block("@media (max-width: 960px)"))

    def test_phone_city_fills_the_screen(self):
        block = media_block("@media (max-width: 960px)")
        self.assertNotIn("66vh", block)
        self.assertRegex(block, r"\.stage-col\{[^}]*flex:1")
        self.assertRegex(block, r"\.stage\{[^}]*flex:1 1 0")
        self.assertRegex(block, r"\.stage canvas\{[^}]*position:absolute")

    def test_log_button_in_the_top_bar(self):
        bar = re.search(r'<header class="bar"[^>]*>(.*?)</header>', zh_resolved(markup()), re.S)
        self.assertIsNotNone(bar, '<header class="bar"> not found')
        self.assertRegex(bar.group(1), r'<button type="button"[^>]*id="logbtn"[^>]*>[^<]*动态')


STATE_JS = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, selected: null, winLog: false, lastDetailKey: 'x', lastRoster: 'x',
  needFrame: false, govTerr: 't1', renders: 0 };
box.renderPanel = () => { box.renders++; };
vm.createContext(box);
vm.runInContext(fns, box);
const out = {};
const snap = () => ({ state: box.winState(), selected: box.selected, renders: box.renders });
out.fresh = snap();
box.selectFrom('c7'); out.person = snap();
box.openLog(); out.log = snap();
box.selectFrom('gov:t1'); out.gov = snap();
box.closeWin(); out.closed = snap();
box.openLog(); box.closeWin(); out.logClosed = snap();
process.stdout.write(JSON.stringify(out));
"""


class TestWindowState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [n for n in ("winState", "openLog", "closeWin", "selectFrom") if function_source(n) is None]
        if missing:
            raise AssertionError("not found in the page: " + ", ".join(missing))
        cls.r = run_node(STATE_JS, {"fns": page_fns("winState", "openLog", "closeWin", "selectFrom")})

    def test_closed_until_something_is_picked(self):
        self.assertIsNone(self.r["fresh"]["state"])

    def test_picking_a_person_opens_its_window(self):
        self.assertEqual(self.r["person"]["state"], "detail")
        self.assertEqual(self.r["person"]["selected"], {"t": "c", "id": "c7"})

    def test_the_log_replaces_the_detail(self):
        self.assertEqual(self.r["log"]["state"], "log")
        self.assertIsNone(self.r["log"]["selected"])
        self.assertGreater(self.r["log"]["renders"], self.r["person"]["renders"], "openLog redraws")

    def test_picking_from_the_log_shows_the_detail(self):
        self.assertEqual(self.r["gov"]["state"], "detail")
        self.assertEqual(self.r["gov"]["selected"], {"t": "gov", "terr": "t1"})

    def test_close_leaves_only_the_city(self):
        for name in ("closed", "logClosed"):
            with self.subTest(after=name):
                self.assertIsNone(self.r[name]["state"])
                self.assertIsNone(self.r[name]["selected"])

    def test_win_log_is_top_level(self):
        self.assertRegex(inline_script(), r"(?m)^let winLog = false;")


class TestWindowWiring(unittest.TestCase):
    def test_render_panel_draws_the_window_only(self):
        body = function_source("renderPanel") or ""
        self.assertIn("renderWin()", body)
        for name in ("renderRoster(", "renderBalance("):
            with self.subTest(fn=name):
                self.assertNotIn(name, body)

    def test_render_win(self):
        body = zh_resolved(function_source("renderWin") or "")  # idea-city C1
        self.assertTrue(body, "renderWin() not found")
        for needle in ("'#win'", "winState()", "'#detail'", "'#log'", "'#win-title'", "动态", "hidden"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)

    def test_close_and_log_buttons(self):
        text = inline_script()
        self.assertRegex(text, r"\$\('#win-close'\)\.addEventListener\('click',[^\n]*closeWin\(\)")
        self.assertRegex(text, r"\$\('#logbtn'\)\.addEventListener\('click',[^\n]*openLog\(\)")

    def test_rows_in_the_window_open_that_person(self):
        text = inline_script()
        m = re.search(r"\$\('#detail'\)\.addEventListener\('click', e => \{(.*?)\n\}\);", text, re.S)
        self.assertIsNotNone(m, "#detail click handler not found")
        self.assertIn("data-sel", m.group(1))
        self.assertIn("selectFrom(", m.group(1))
        self.assertIn("data-sel", function_source("renderDetail") or "")

    def test_a_tap_on_the_city_closes_the_log(self):
        body = function_source("endPointer") or ""
        self.assertRegex(body, r"winLog = false|closeWin\(")


if __name__ == "__main__":
    unittest.main()
