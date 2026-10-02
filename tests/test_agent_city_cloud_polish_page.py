"""Failing tests for cloud-polish, part 2: the page layout (owner, 2026-10-02; approved mock
mock/cloud-polish-mock.html, c3c1f4f, approved as shown, plus one change C1). The look is the mock's:
port its afterCss() and its Q1 script (the strip, --top-h, the fade) into the page itself; the mock's
`.q1` scope class is not needed in the page (the rules ARE the page now), and its `:has()` rules become
the two stage classes below.

Q1  THE TWO ROWS SIT ON THE STAGE (owner: "this part should be on the screen, I do not want the header
    too many, then the main screen visual area will be small". Measured in a 1280 x 727 window: the
    cloud page's stage started 183 px down and was 549 px high; after: 84 px down, 648 px high. Local
    page: 132 -> 84 px down, 642 -> 690 px high.)

  HTML (bin/agent-city.html): nothing between </header> and <main class="layout"> any more. Inside
    <div class="stage" id="stage">, before <aside class="rail" id="rail">, ONE strip:
        <div class="stage-top" id="stage-top">
          <nav class="machines" id="machines" data-t-aria="cloud.machines" hidden></nav>   (cloud page only, as before;
                                                                 it keeps its "cloud-city: html" comment marks)
          <nav class="repos" id="repos" data-t-aria="aria.repos"></nav>
        </div>
    Each nav exists once. The scripts that fill them (renderRepos, cloudRenderRow) and their click
    listeners find them by id, as before.
  CSS, desktop:
    .stage-top  position:absolute; top:12px; left:calc(var(--rail-w) + 24px); right:66px; z-index:3;
                display:flex; flex-direction:column; pointer-events:none (the map is dragged between the
                chips); its navs (.stage-top>nav) pointer-events:auto, max-width:100%, no scrollbar; a nav
                that is longer than its room scrolls sideways and fades at the cut edge (.stage-top>nav.more
                has a mask-image; the script keeps the class).
    It makes room:  .stage.rail-folded .stage-top{left:42px}   the rail folded to its tab
                    .stage.rail-none .stage-top{left:12px}     no rail and no tab (no repo at all)
                    .stage.win-open .stage-top{right:calc(var(--msg-w) + 78px)}    an open window
                    .stage.win-tab-open .stage-top{right:106px}                    a folded window
    The chips get their own small shadow over the map: .stage-top .repo and .stage-top .mc (box-shadow).
    What sat at the top middle of the map goes under the strip: .proto, .follow -> top:calc(18px +
      var(--top-h,34px)); .cloud-banner -> top:calc(20px + var(--top-h,34px)). None keeps top:12px/14px.
    The stage gets the freed height: .stage height calc(100dvh - var(--stage-off,102px)) (was 150);
      .stage-col.no-bar --stage-off:37px (was 85); .cloud-page .stage-col.no-bar --stage-off:82px (was
      130); the rule .cloud-row .stage-col.no-bar is gone (the machine row takes no header height).
    The header is one row: .bar flex-wrap:nowrap; .stats flex-wrap:nowrap, min-width:0, overflow-x:auto.
  CSS, phone (inside the FIRST @media (max-width: 960px) block):
    .stage-top{top:8px;left:38px;right:58px} in every state (the rail tab is at the left edge, the camera
      buttons at the right; a window is a bottom sheet): the same left/right for .stage.rail-folded,
      .stage.win-open and .stage.win-tab-open; .stage.rail-none .stage-top left:8px.
    The header: .bar flex-wrap:wrap; the counters on ONE line of their own under the title row:
      .stats{order:9;flex:1 1 100%}.
  Script:
    renderRail(): stage.classList.toggle('rail-folded', <the tab shows>) and stage.classList.toggle(
      'rail-none', <neither the rail nor the tab shows>).
    --top-h: the strip's own height in px, kept on #stage (style.setProperty('--top-h', ...)) by a
      ResizeObserver on the strip; the same pass sets / clears the class 'more' on each nav (it has more
      to the right than fits). A nav's own scroll runs the pass too.

C1  THE ACCOUNT CHIP IS ONE LINE (owner, with the mock yes): the green dot and the e-mail sit on one line
    (the dot was on its own line above the e-mail: the older rule .who{flex-direction:column} reached it).
    .acct .who: flex-direction:row, align-items:center, white-space:nowrap: the chip is as low as the
    other header chips.

E   FOUND ON THE REAL PAGES (headless, 2026-10-02: the local city and the cloud page on the dev runner):
    E1 the connection chip (.proto) sits under the strip, so it starts where the strip starts:
       .stage.rail-folded .proto{left:42px}, .stage.rail-none .proto{left:12px}; phone (first 960 block):
       .stage.rail-folded .proto{left:38px}, .stage.rail-none .proto{left:8px}.
    E2 a narrow phone with a view-only machine: the header's 只能看 chip pushed the account onto a row of
       its own (three header rows). In a block @media (max-width: 520px): .ro{display:none} (the machine's
       own chip on the map says 只能看, and so does the window) and .sign-name{font-size:20px} (the title
       row then holds 动态 and the account on a 375 px phone too).
       Phone: the connection chip keeps a line of its own UNDER the "跟随" chip, as before (it was at
       top:52px, 40 px under the follow chip's 12px; both under the strip they lay on each other):
       .proto{left:38px;top:calc(50px + var(--top-h,34px))} in the first 960 block.
    E3 phone, the rail drawer open: the "跟随" chip, now under the strip, lay over a row of the drawer:
       .stage.drawer-open .follow{visibility:hidden} (first 960 block; following goes on).

Q5  the small + (phone): inside the first @media (max-width: 960px) block .add-i is 28 x 28 px (a finger).
    Its markup and states: tests/test_agent_city_add_agent_page.py (A2) and
    tests/test_agent_city_cloud_start_page.py.

Run: python3 -m unittest tests.test_agent_city_cloud_polish_page </dev/null
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_page import function_source, inline_script  # noqa: E402
from test_agent_city_people import page  # noqa: E402
from test_agent_city_ux_page import css, listener_block, media_960, rule  # noqa: E402


def body_html():
    """The page's own markup: from <body> to the first <script."""
    text = page()
    start = text.index("<body>")
    return text[start:text.index("<script", start)]


def media_block(query):
    """The first @media block of the page's CSS with exactly this query, e.g. "(max-width: 520px)"."""
    c = css()
    i = c.find("@media " + query)
    if i < 0:
        return ""
    depth = 0
    for j in range(c.index("{", i), len(c)):
        if c[j] == "{":
            depth += 1
        elif c[j] == "}":
            depth -= 1
            if depth == 0:
                return c[i:j + 1]
    return ""


def flat(decls):
    return re.sub(r"\s+", "", decls or "")


class TestRowsOnTheStage(unittest.TestCase):
    def test_nothing_between_the_header_and_the_layout(self):
        html = body_html()
        between = html[html.index("</header>"):html.index('<main class="layout">')]
        self.assertNotIn("<nav", between, "the machine row and the repo row left the header")

    def test_one_strip_on_the_stage_holds_both(self):
        html = body_html()
        self.assertEqual(html.count('id="machines"'), 1)
        self.assertEqual(html.count('id="repos"'), 1)
        m = re.search(r'<div class="stage-top" id="stage-top">(.*?)</div>', html, re.S)
        self.assertIsNotNone(m, 'no <div class="stage-top" id="stage-top"> in the page')
        inner = m.group(1)
        self.assertRegex(inner, r'<nav class="machines" id="machines" data-t-aria="cloud\.machines" hidden></nav>')
        self.assertRegex(inner, r'<nav class="repos" id="repos" data-t-aria="aria\.repos"></nav>')
        self.assertLess(inner.index('id="machines"'), inner.index('id="repos"'), "machines first, repos under it")
        self.assertLess(html.index('<div class="stage" id="stage">'), m.start())
        self.assertLess(m.start(), html.index('<aside class="rail" id="rail"'), "inside the stage, before the rail")
        self.assertRegex(inner, r"(?s)<!-- cloud-city: html.*?-->.*id=\"machines\".*<!-- end cloud-city: html -->",
                         "the machine row keeps its cloud-city marks")

    def test_the_scripts_still_find_them(self):
        self.assertIn("$('#repos')", function_source("renderRepos") or "")
        self.assertIn("$('#machines')", function_source("cloudRenderRow") or "")
        self.assertIsNotNone(listener_block(r"\$\('#repos'\)", "click"))
        self.assertIsNotNone(listener_block(r"\$\('#machines'\)", "click"))


class TestStripCss(unittest.TestCase):
    def test_the_strip(self):
        r = flat(rule(".stage-top"))
        for bit in ("position:absolute", "top:12px", "left:calc(var(--rail-w)+24px)", "right:66px", "z-index:3",
                    "display:flex", "flex-direction:column", "pointer-events:none"):
            with self.subTest(bit=bit):
                self.assertIn(bit, r)
        nav = flat(rule(".stage-top>nav"))
        self.assertIn("pointer-events:auto", nav, "the chips take clicks, the gaps between them do not")
        self.assertIn("max-width:100%", nav)
        self.assertIn("mask-image", rule(".stage-top>nav.more"), "a line that is cut fades at the edge")

    def test_it_makes_room(self):
        self.assertIn("left:42px", flat(rule(".stage.rail-folded .stage-top")))
        self.assertIn("left:12px", flat(rule(".stage.rail-none .stage-top")))
        self.assertIn("right:calc(var(--msg-w)+78px)", flat(rule(".stage.win-open .stage-top")))
        self.assertIn("right:106px", flat(rule(".stage.win-tab-open .stage-top")))

    def test_chips_have_a_shadow_over_the_map(self):
        for sel in (".stage-top .repo", ".stage-top .mc"):
            with self.subTest(sel=sel):
                self.assertIn("box-shadow", rule(sel))

    def test_what_was_at_the_top_middle_goes_under_it(self):
        for sel in (".proto", ".follow"):
            with self.subTest(sel=sel):
                r = flat(rule(sel))
                self.assertIn("top:calc(18px+var(--top-h,34px))", r)
                self.assertNotIn("top:12px", r)
        banner = flat(rule(".cloud-banner"))
        self.assertIn("top:calc(20px+var(--top-h,34px))", banner)
        self.assertNotIn("top:14px", banner)

    def test_the_stage_gets_the_freed_height(self):
        self.assertIn("height:calc(100dvh-var(--stage-off,102px))", flat(rule(".stage")), "150 minus the repo row's 48")
        self.assertIn("--stage-off:37px", flat(rule(".stage-col.no-bar")), "85 minus 48")
        self.assertIn("--stage-off:82px", flat(rule(".cloud-page .stage-col.no-bar")), "130 minus 48")
        self.assertEqual(rule(".cloud-row .stage-col.no-bar").strip(), "", "the machine row takes no header height any more")

    def test_the_header_is_one_row(self):
        self.assertIn("flex-wrap:nowrap", flat(rule(".bar")))
        stats = flat(rule(".stats"))
        for bit in ("flex-wrap:nowrap", "min-width:0", "overflow-x:auto"):
            with self.subTest(bit=bit):
                self.assertIn(bit, stats)


class TestPhone(unittest.TestCase):
    def setUp(self):
        self.m = media_960()

    def test_the_strip_between_the_rail_tab_and_the_camera_buttons(self):
        r = flat(rule(".stage-top", self.m))
        for bit in ("top:8px", "left:38px", "right:58px"):
            with self.subTest(bit=bit):
                self.assertIn(bit, r)

    def test_the_same_room_in_every_state(self):
        for sel in (".stage.rail-folded .stage-top", ".stage.win-open .stage-top", ".stage.win-tab-open .stage-top"):
            with self.subTest(sel=sel):
                r = flat(rule(sel, self.m))
                self.assertIn("left:38px", r)
                self.assertIn("right:58px", r)
        self.assertIn("left:8px", flat(rule(".stage.rail-none .stage-top", self.m)))

    def test_the_header(self):
        self.assertIn("flex-wrap:wrap", flat(rule(".bar", self.m)))
        stats = flat(rule(".stats", self.m))
        self.assertIn("order:9", stats)
        self.assertIn("flex:11100%", stats, "the counters: one line of their own (flex:1 1 100%)")

    def test_the_small_plus_is_bigger_for_a_finger(self):
        self.assertRegex(flat(rule(".add-i", self.m)), r"width:28px;height:28px")


class TestStripScript(unittest.TestCase):
    def test_render_rail_tells_the_stage(self):
        src = function_source("renderRail") or ""
        self.assertRegex(src, r"stage\.classList\.toggle\('rail-folded',")
        self.assertRegex(src, r"stage\.classList\.toggle\('rail-none',")

    def test_top_h_follows_the_strip(self):
        script = inline_script()
        self.assertRegex(script, r"setProperty\('--top-h',")
        self.assertRegex(script, r"new ResizeObserver\([^\n]{0,80}?\)\.observe\(\s*(?:\$\('#stage-top'\)|stageTop)\b",
                         "a ResizeObserver on the strip (stageTop = $('#stage-top')) keeps --top-h")
        self.assertRegex(script, r"classList\.toggle\('more',", "and the fade class of each row")


class TestFoundOnTheRealPages(unittest.TestCase):
    def test_the_connection_chip_starts_where_the_strip_starts(self):
        self.assertIn("left:42px", flat(rule(".stage.rail-folded .proto")))
        self.assertIn("left:12px", flat(rule(".stage.rail-none .proto")))
        m = media_960()
        self.assertIn("left:38px", flat(rule(".stage.rail-folded .proto", m)))
        self.assertIn("left:8px", flat(rule(".stage.rail-none .proto", m)))

    def test_phone_the_connection_chip_is_under_the_follow_chip(self):
        r = flat(rule(".proto", media_960()))
        self.assertIn("left:38px", r)
        self.assertIn("top:calc(50px+var(--top-h,34px))", r, "one line under the follow chip, as before the move")

    def test_a_narrow_phone_keeps_the_account_on_the_title_row(self):
        block = media_block("(max-width: 520px)")
        self.assertTrue(block, "no @media (max-width: 520px) block")
        self.assertIn("display:none", flat(rule(".ro", block)), "the machine's own chip says 只能看")
        self.assertIn("font-size:20px", flat(rule(".sign-name", block)))

    def test_the_follow_chip_is_not_over_the_open_drawer(self):
        self.assertIn("visibility:hidden", flat(rule(".stage.drawer-open .follow", media_960())))


class TestAccountChip(unittest.TestCase):
    """C1 (owner, with the mock yes): the dot and the e-mail on one line."""

    def test_one_line(self):
        r = flat(rule(".acct .who"))
        self.assertIn("flex-direction:row", r, "the older .who{flex-direction:column} must not reach the account chip")
        self.assertIn("align-items:center", r)
        self.assertIn("white-space:nowrap", r)

    def test_the_markup_is_the_dot_then_the_mail(self):
        src = function_source("cloudRenderAcct") or ""
        self.assertIn('<span class="who"><i></i><span>', src)

    def test_no_later_rule_stacks_it_again(self):
        c = css()
        last = max(m.start() for m in re.finditer(r"\.acct \.who\s*\{", c))
        after = c[last:]
        self.assertNotRegex(after, r"\.who\s*\{[^}]*flex-direction:\s*column")


if __name__ == "__main__":
    unittest.main()
