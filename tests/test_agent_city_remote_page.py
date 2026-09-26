"""Failing tests: other team members in the real city page (city-join-page).

Approved mock: mock/city-join-mock.html. Server side: the docstring of
tests/test_agent_city_relay_serve.py ("remote", "remote_snapshot", "relay").
Rules: requirements/city.md, "Joining".

bin/agent-city.html

  Events. The live switch in apply() gains three cases:
    case 'remote'           msg.ev is a normal page event ("spawn", "tool",
                            "stuck", "answer", "done", "leave", "gov") for
                            another member's agent; msg.who, msg.device,
                            msg.dev, msg.rid, msg.br say whose.
    case 'remote_snapshot'  replaces the whole picture of other members
                            (me, people, govs, teams).
    case 'team'             one team's state: ok | off | refused | left, and
                            its queued count. ('relay' belongs to city-people:
                            a question passed up the chain.)

  Other members' people (browser; the main manager's click path checks it):
    - drawn like my own citizens (same models, walks, tools, rest), in the
      territory ev.terr, each marked remote with who/device/dev/rid/br
    - two tags (owner decision 2026-09-25, as in the mock): the name tag
      (memberName(who, device)) and beside it a SEPARATE small grey device
      chip (device) — an overlay element of class "rdev", its own CSS rule
      `.rdev{...}`. Never one combined "<who> · <device>" tag on a person.
      Both set with textContent (a member's git user.name is outside input).
    - Owner decision 2026-09-25 (after the LAN test): the floating tags are
      OFF by default for every person. They show only while the pointer is
      over that person (hover) or it is selected: tagVisible(hover, sel).
      Hover: the canvas's pointermove, with no button down, picks the
      person under the pointer (pickAt) into a top-level `let hovered`.
    - While joined, the ring under EVERY person (mine and others', governors
      too) has the colour of the member it belongs to: memberColors() over
      "me" and each sender device (dev), mine = MEMBER_COLORS[0]. In a
      local-only city (not joined) the ring keeps the role colour as today:
      ringColor(joined, roleColor, memberColor).
    - The roster group headers and the 联城 chip keep the members' names,
      each with a dot in that member's colour: memberLegend().
    - A blank who is never shown: memberName() falls back to the device.
    - my governor never talks to them, never sends them ("去吧" is mine only)
    - their stuck "?" is grey and opens no ask panel; the detail card shows
      who, device, repo (rid), branch, what it is doing, and remoteNote(who);
      never an answer, allow or deny button for them
    - log lines name the person: "<who>（<device>）..."
    - at most MAX_REMOTE of them (const MAX_REMOTE = 20); a remote person
      never pushes out one of my own
  Other members' governors: extra governor figures at that territory's town
  hall, next to mine, several side by side, each with a name sign
  govSign(g); "present": false removes one.
  Relay chip in the top bar (#stats), only while joined: remoteChip(...),
  then the members from memberLegend(), each a colour dot + name.
  While a team is off, other members' figures fade and show
  staleText(seconds since their last event).
  Roster: my own first, then one group per "<who> · <device>".
  Demo (#demo): fake other members so the look can be checked without a
  relay: Maverick · pc2 (a governor and a worker), Ann · ann-laptop (a
  governor and a worker whose question shows the grey "?"), Bo · 云端 (a
  worker); my own device in the demo is mac-mini. Demo-only buttons, in the
  demo-only spawn group: data-remote="off" (中继断开), data-remote="on"
  (恢复), data-remote="leave" (退出联城).

  Pure helpers, between the exact comment lines
      /* city-join: pure */   and   /* end city-join: pure */
  using nothing but their arguments and JS built-ins (Math, Set, Array,
  String, Number), so this file runs them in node:
    remoteChip(relays, me, people, govs) -> null | {cls, text}
        relays: [{host, state, queued}], me: {who, device} or null,
        people / govs: [{who, device, dev}].
        No entry whose state is not "left" -> null (not joined: no chip).
        Any "off"      -> {cls: "off", text: "联城断开 · 待发 N 条"},
                          N = the sum of queued over the "off" entries.
        Else any "refused" -> {cls: "refused", text: "联城拒绝了密钥"}.
        Else           -> {cls: "ok", text: "联城 · P 人 · D 台设备"},
                          P = distinct memberName(who, device) over me,
                          people, govs;
                          D = (me ? 1 : 0) + distinct dev over people, govs.
    remoteNote(who) -> "只能看：这是 <who> 的 agent，只有 <who> 能回答。"
    memberLabel(who, device) -> "<memberName> · <device>", or just the
                       name when the name IS the device (no "pc2 · pc2").
    govSign(g)      -> memberLabel(g.who, g.device). Roster group headers use
                       memberLabel too.
    staleText(sec)  -> under 60: "最后更新 <floor(sec)> 秒前",
                       else "最后更新 <floor(sec / 60)> 分钟前"
    memberName(who, device) -> who trimmed; if blank, device trimmed; if
                       both blank, "未知". Never blank.
    MEMBER_COLORS   at least 8 distinct "#rrggbb" colours; [0] is mine.
    memberColors(keys, meKey) -> {key: colour}. meKey -> MEMBER_COLORS[0].
                       Every other key gets a colour from MEMBER_COLORS[1..]
                       picked from a hash of the key (moving on to the next
                       free one when taken), so it is the same whatever the
                       order of keys (keys are handled sorted) and distinct
                       while there are free colours; never MEMBER_COLORS[0].
    ringColor(joined, roleColor, memberColor) -> joined ? memberColor : roleColor
    tagVisible(hover, selected) -> !!(hover || selected)
    memberLegend(me, people, govs, colors) -> [{key, name, device, color}]
                       me first (key "me"), then one entry per dev in order
                       of first appearance (people, then govs); name =
                       memberName(); colour = colors[key]. me null -> no
                       "me" entry.

The page must keep passing tests/test_agent_city_page.py.

Run: python3 -m unittest tests.test_agent_city_remote_page
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGE = os.path.join(ROOT, "bin", "agent-city.html")
START = "/* city-join: pure */"
END = "/* end city-join: pure */"


def page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


def inline_script():
    return "\n".join(re.findall(r"<script>(.*?)</script>", page(), re.S))


def pure_section():
    text = inline_script()
    if START not in text or END not in text:
        return None
    return text[text.index(START) + len(START):text.index(END)]


RUNNER = r"""
const vm = require('vm'), fs = require('fs');
const { section, calls } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, Set, Array, String, Number, Object, JSON };
vm.createContext(box);
vm.runInContext(section, box);
const out = calls.map(([fn, args]) => {
  try { return { ok: vm.runInContext(fn, box).apply(null, args) }; }
  catch (e) { return { error: String(e && e.message || e) }; }
});
process.stdout.write(JSON.stringify(out));
"""


class TestEvents(unittest.TestCase):
    def test_three_new_cases(self):
        script = inline_script()
        for name in ("remote", "remote_snapshot", "team"):
            with self.subTest(case=name):
                self.assertIn("case '%s'" % name, script)

    def test_name_tag_and_device_chip_are_separate(self):
        text = page()
        self.assertRegex(text, r"\.rdev\s*\{", "no CSS rule for the device chip .rdev")
        self.assertRegex(inline_script(), r"['\"]rdev['\"]", "no element with class rdev")
        self.assertNotRegex(inline_script(), r"remote\.who\}\s*·\s*\$\{[^}]*remote\.device",
                            "a person still gets one combined 'who · device' tag")

    def test_hover_and_member_rings_are_wired(self):
        script = inline_script()
        outside = script.replace(pure_section() or "", "")
        self.assertRegex(script, r"\blet hovered\b", "no top-level `let hovered`")
        for fn in ("tagVisible(", "ringColor(", "memberColors(", "memberLegend(", "memberName("):
            with self.subTest(fn=fn):
                self.assertIn(fn, outside, "%s is defined but never used by the page" % fn)

    def test_team_state_never_uses_the_chain_event(self):
        script = inline_script()
        self.assertEqual(script.count("case 'relay'"), 1, "one 'relay' case only: city-people's chain")
        self.assertNotRegex(script, r"type:\s*'relay',\s*host", "the team state is type 'team'")

    def test_cap(self):
        self.assertRegex(inline_script(), r"const MAX_REMOTE = 20\b")

    def test_words(self):
        text = page()
        for word in ("只能看", "联城断开", "待发", "联城拒绝了密钥"):
            with self.subTest(word=word):
                self.assertIn(word, text)

    def test_demo_members_and_buttons(self):
        text = page()
        for word in ("ann-laptop", "云端", "pc2", "mac-mini",
                     'data-remote="off"', 'data-remote="on"', 'data-remote="leave"'):
            with self.subTest(word=word):
                self.assertIn(word, text)

    def test_never_a_key_or_address(self):
        text = page()
        for word in ("TEAM_KEY", "AGENT_CITY_RELAY", "Bearer", "workers.dev"):
            with self.subTest(word=word):
                self.assertNotIn(word, text)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestPureHelpers(unittest.TestCase):
    def run_calls(self, calls):
        section = pure_section()
        self.assertIsNotNone(section, "no /* city-join: pure */ ... /* end city-join: pure */ section")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump({"section": section, "calls": calls}, fh)
            data = fh.name
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(RUNNER)
            runner = fh.name
        try:
            proc = subprocess.run(["node", runner, data], capture_output=True, text=True, timeout=30)
        finally:
            os.unlink(data)
            os.unlink(runner)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        for r in out:
            self.assertNotIn("error", r, r.get("error"))
        return [r.get("ok") for r in out]

    ME = {"who": "Maverick", "device": "mac-mini"}
    PEOPLE = [{"who": "Maverick", "device": "pc2", "dev": "d-pc2"},
              {"who": "Ann", "device": "ann-laptop", "dev": "d-ann"},
              {"who": "Bo", "device": "云端", "dev": "d-bo"}]
    GOVS = [{"who": "Maverick", "device": "pc2", "dev": "d-pc2"},
            {"who": "Ann", "device": "ann-laptop", "dev": "d-ann"}]

    def test_chip(self):
        ok = [{"host": "r.example", "state": "ok", "queued": 0}]
        off = [{"host": "r.example", "state": "off", "queued": 12},
               {"host": "s.example", "state": "off", "queued": 3},
               {"host": "t.example", "state": "ok", "queued": 9}]
        got = self.run_calls([
            ["remoteChip", [[], self.ME, [], []]],
            ["remoteChip", [[{"host": "r.example", "state": "left", "queued": 0}], self.ME, [], []]],
            ["remoteChip", [ok, self.ME, self.PEOPLE, self.GOVS]],
            ["remoteChip", [ok, self.ME, [], []]],
            ["remoteChip", [ok, None, self.PEOPLE, []]],
            ["remoteChip", [off, self.ME, self.PEOPLE, self.GOVS]],
            ["remoteChip", [[{"host": "r.example", "state": "refused", "queued": 4}], self.ME, [], []]],
            ["remoteChip", [[{"host": "r.example", "state": "refused", "queued": 0},
                             {"host": "s.example", "state": "off", "queued": 2}], self.ME, [], []]],
        ])
        self.assertEqual(got[0], None)
        self.assertEqual(got[1], None)
        self.assertEqual(got[2], {"cls": "ok", "text": "联城 · 3 人 · 4 台设备"})
        self.assertEqual(got[3], {"cls": "ok", "text": "联城 · 1 人 · 1 台设备"})
        self.assertEqual(got[4], {"cls": "ok", "text": "联城 · 3 人 · 3 台设备"})
        self.assertEqual(got[5], {"cls": "off", "text": "联城断开 · 待发 15 条"})
        self.assertEqual(got[6], {"cls": "refused", "text": "联城拒绝了密钥"})
        self.assertEqual(got[7], {"cls": "off", "text": "联城断开 · 待发 2 条"})

    def test_note_sign_stale(self):
        got = self.run_calls([
            ["remoteNote", ["Ann"]],
            ["govSign", [{"who": "Ann", "device": "ann-laptop"}]],
            ["govSign", [{"who": "Bo", "device": "云端"}]],
            ["staleText", [0]], ["staleText", [59.9]], ["staleText", [60]], ["staleText", [185]],
        ])
        self.assertEqual(got, ["只能看：这是 Ann 的 agent，只有 Ann 能回答。",
                               "Ann · ann-laptop", "Bo · 云端",
                               "最后更新 0 秒前", "最后更新 59 秒前",
                               "最后更新 1 分钟前", "最后更新 3 分钟前"])

    def test_blank_name_counts_as_its_device(self):
        ok = [{"host": "r.example", "state": "ok", "queued": 0}]
        got = self.run_calls([
            ["remoteChip", [ok, self.ME, [{"who": "", "device": "pc2", "dev": "d-pc2"}], []]],
        ])
        self.assertEqual(got[0], {"cls": "ok", "text": "联城 · 2 人 · 2 台设备"})

    def test_member_label_never_repeats_the_device(self):
        got = self.run_calls([["memberLabel", ["Ann", "ann-laptop"]], ["memberLabel", ["", "pc2"]],
                              ["govSign", [{"who": "", "device": "pc2"}]],
                              ["govSign", [{"who": "Ann", "device": "ann-laptop"}]]])
        self.assertEqual(got, ["Ann · ann-laptop", "pc2", "pc2", "Ann · ann-laptop"])

    def test_member_name(self):
        got = self.run_calls([["memberName", ["Ann", "ann-laptop"]], ["memberName", ["", "pc2"]],
                              ["memberName", ["  ", " pc2 "]], ["memberName", ["", ""]],
                              ["memberName", [None, "pc2"]]])
        self.assertEqual(got, ["Ann", "pc2", "pc2", "未知", "pc2"])

    def test_member_colours(self):
        keys = ["d-pc2", "d-ann", "d-bo", "d-cy", "me"]
        got = self.run_calls([
            ["(() => MEMBER_COLORS)", []],
            ["memberColors", [keys, "me"]],
            ["memberColors", [list(reversed(keys)), "me"]],
            ["memberColors", [["me"], "me"]],
        ])
        palette, a, b, only_me = got
        self.assertGreaterEqual(len(palette), 8)
        self.assertEqual(len(set(palette)), len(palette))
        for c in palette:
            self.assertRegex(c, r"^#[0-9a-fA-F]{6}$")
        self.assertEqual(a, b, "colours must not depend on the order of keys")
        self.assertEqual(a["me"], palette[0])
        self.assertEqual(only_me, {"me": palette[0]})
        others = [a[k] for k in keys if k != "me"]
        self.assertNotIn(palette[0], others)
        self.assertEqual(len(set(others)), len(others), "distinct while colours are free")
        many = self.run_calls([["memberColors", [["d%d" % i for i in range(20)] + ["me"], "me"]]])[0]
        self.assertEqual(len(many), 21)
        self.assertEqual(sum(1 for k, v in many.items() if v == palette[0]), 1)

    def test_ring_tag_legend(self):
        colors = {"me": "#111111", "d-pc2": "#222222", "d-ann": "#333333"}
        people = [{"who": "", "device": "pc2", "dev": "d-pc2"},
                  {"who": "Ann", "device": "ann-laptop", "dev": "d-ann"},
                  {"who": "", "device": "pc2", "dev": "d-pc2"}]
        govs = [{"who": "Ann", "device": "ann-laptop", "dev": "d-ann"}]
        got = self.run_calls([
            ["ringColor", [True, "#role00", "#member"]], ["ringColor", [False, "#role00", "#member"]],
            ["tagVisible", [False, False]], ["tagVisible", [True, False]], ["tagVisible", [False, True]],
            ["memberLegend", [self.ME, people, govs, colors]],
            ["memberLegend", [None, people, [], colors]],
        ])
        self.assertEqual(got[:5], ["#member", "#role00", False, True, True])
        self.assertEqual(got[5], [
            {"key": "me", "name": "Maverick", "device": "mac-mini", "color": "#111111"},
            {"key": "d-pc2", "name": "pc2", "device": "pc2", "color": "#222222"},
            {"key": "d-ann", "name": "Ann", "device": "ann-laptop", "color": "#333333"},
        ])
        self.assertEqual([e["key"] for e in got[6]], ["d-pc2", "d-ann"])

    def test_pure_means_pure(self):
        section = pure_section()
        self.assertIsNotNone(section)
        for word in ("document", "window", "THREE", "citizens", "localStorage", "fetch"):
            with self.subTest(word=word):
                self.assertNotRegex(section, r"\b%s\b" % word)


if __name__ == "__main__":
    unittest.main()
