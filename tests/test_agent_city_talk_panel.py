"""Failing tests: city-talk T4 + T5 (owner, 2026-10-01, from a screenshot of the live city).

T4  The message panel of a subagent showed the red line 对话没加载出来 (chat.loadError). A subagent has no
    chat of its own: its panel shows the read-only note only, never the red error.
T5  The label "fast-lane-deputy · msg-sides Deputy" says the kind twice. Show "msg-sides Deputy": the kind
    is dropped when the name already says it. Same text in the rail, the head label and the panel title
    (all three show nameOf(c)).

CONTRACT (bin/agent-city.html)

  T4  chatFailText(to, box) -> the text of the red line in the panel of page id `to`: box.error for a
      session (an id that starts with "gov:" or "s:"), '' for anyone else (a subagent), '' when there is
      no error or no box. Top-level, pure.
      renderDetail (chatSectionHtml and the per-call refresh of #chat-fail) takes the red line's text and
      its hidden state from chatFailText only: for a subagent #chat-fail stays hidden and empty, the
      hint.readOnlySub note and the find-lead button stay. A session's failed load still shows the line.
  T5  nameBase(c, repo): after the repo is taken off (shortLabel) and before "<label> · <task>" is built,
      the label (the kind) is dropped and the task alone is the name when the task already says the kind:
        - the kind's last word (the text after its last "-") is in the task as a whole word, any case
          ("fast-lane-deputy" + "msg-sides Deputy" -> "msg-sides Deputy"), or
        - the task's last word is one of the kind's words ("merge-deputy" + "city-status Merge" ->
          "city-status Merge").
      Unchanged: a task that does not say the kind keeps it ("fast-lane-deputy · 按钮颜色",
      "worker · city-polish Deputy", "worker · coworker list"); "<Kind> <n>: <slice>" still reads
      "<Kind> <n> · <slice>"; label === task shows once; the " #xxxx" tag on a double name.
      The rail row (railRowHtml), the head tag (updatePerson) and the panel title (winTitle) show nameOf(c).

Run: python3 -m unittest tests.test_agent_city_talk_panel </dev/null
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_page import constants_prelude, function_source, page_fns, run_node  # noqa: E402
from test_agent_city_people import REQUIRED, run_sim  # noqa: E402

ERR = "对话没加载出来，等会儿再打开看看。"


class TestSubagentPanelHasNoRedLineT4(unittest.TestCase):

    def fail_text(self, cases):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = {}; vm.createContext(box); vm.runInContext(fns, box);
process.stdout.write(JSON.stringify(cases.map(c => box.chatFailText(c[0], c[1]))));
"""
        return run_node(js, {"fns": constants_prelude() + "\n" + page_fns("chatFailText"), "cases": cases})

    def test_a_subagent_never_gets_the_red_line(self):
        out = self.fail_text([["a9f3c2", {"error": ERR}], ["w1", {"error": ERR, "entries": []}],
                              ["agent-77", {"error": "x"}]])
        self.assertEqual(out, ["", "", ""], "a subagent has no chat of its own: read-only note only")

    def test_a_session_still_shows_a_failed_load(self):
        out = self.fail_text([["s:tm1", {"error": ERR}], ["gov:t1", {"error": ERR}]])
        self.assertEqual(out, [ERR, ERR], "a failure is shown in a session's window, never swallowed")

    def test_no_error_no_line(self):
        out = self.fail_text([["s:tm1", {"entries": []}], ["s:tm1", None], ["w1", None], ["gov:t1", {"error": ""}]])
        self.assertEqual(out, ["", "", "", ""])

    def test_the_panel_uses_it_in_both_places(self):
        body = function_source("renderDetail") or ""
        self.assertGreaterEqual(body.count("chatFailText("), 2,
                                "chatSectionHtml and the per-call #chat-fail refresh both ask chatFailText")
        self.assertNotIn("box.error ? '' : ' hidden'", body, "the red line no longer follows box.error alone")
        self.assertNotIn("fail.hidden = !box.error", body, "the refresh no longer follows box.error alone")
        self.assertIn("hint.readOnlySub", body, "the read-only note stays")
        self.assertIn("btn.findLead", body, "the way to its lead stays")


class TestLabelDropsTheRepeatedKindT5(unittest.TestCase):

    def names(self, pairs):
        driver = r"""
__out = __payload.pairs.map(p => nameOf({ id: 'x1', label: p[0], task: p[1] }));
"""
        return run_sim(driver, {"pairs": pairs}, REQUIRED + ("nameOf",))

    def test_the_owner_case(self):
        self.assertEqual(self.names([["fast-lane-deputy", "msg-sides Deputy"]]), ["msg-sides Deputy"],
                         "owner screenshot: 'fast-lane-deputy · msg-sides Deputy' repeats the kind")

    def test_the_kinds_last_word_in_the_name(self):
        out = self.names([["fast-lane-deputy", "msg-sides deputy"], ["fast-lane-deputy", "Deputy for the rail"],
                          ["merge-deputy", "city-status Deputy"], ["worker", "the login Worker"],
                          ["worker", "worker: api"]])
        self.assertEqual(out, ["msg-sides deputy", "Deputy for the rail", "city-status Deputy", "the login Worker",
                               "worker: api"])

    def test_the_names_last_word_is_a_word_of_the_kind(self):
        self.assertEqual(self.names([["merge-deputy", "city-status Merge"], ["merge-deputy", "city-status merge"]]),
                         ["city-status Merge", "city-status merge"])

    def test_a_name_that_does_not_say_the_kind_keeps_it(self):
        out = self.names([["fast-lane-deputy", "按钮颜色"], ["worker", "city-polish Deputy"],
                          ["worker", "coworker list"], ["fast-lane-deputy", "fast checkout"],
                          ["fast-lane-deputy", "deputyship notes"], ["Explore", "Survey city page"]])
        self.assertEqual(out, ["fast-lane-deputy · 按钮颜色", "worker · city-polish Deputy", "worker · coworker list",
                               "fast-lane-deputy · fast checkout", "fast-lane-deputy · deputyship notes",
                               "Explore · Survey city page"])

    def test_old_rules_stay(self):
        out = self.names([["worker", "worker"], ["worker", ""], ["worker", "Slice A"],
                          ["worker", "city-talk Worker 2: page"], ["task-manager", "city-people"]])
        self.assertEqual(out, ["worker", "worker", "worker · Slice A", "Worker 2 · page", "task-manager · city-people"])

    def test_rail_head_tag_and_panel_title_show_it(self):
        for fn in ("railRowHtml", "updatePerson", "winTitle"):
            with self.subTest(fn=fn):
                self.assertIn("nameOf(", function_source(fn) or "", fn + " shows the name through nameOf()")


if __name__ == "__main__":
    unittest.main()
