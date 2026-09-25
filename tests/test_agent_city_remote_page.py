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
                            (me, people, govs, relay).
    case 'relay'            one team's state: ok | off | refused | left, and
                            its queued count.

  Other members' people (browser; the main manager's click path checks it):
    - drawn like my own citizens (same models, walks, tools, rest), in the
      territory ev.terr, each marked remote with who/device/dev/rid/br
    - two tags, always shown (owner decision 2026-09-25, as in the mock):
      the name tag with the person (who), and beside it a SEPARATE small
      grey device chip (device) — an overlay element of class "rdev", its
      own CSS rule `.rdev{...}` (smaller, grey). Never one combined
      "<who> · <device>" tag on a person. Governor signs stay govSign(g).
      Both set with textContent (a member's git user.name is outside input).
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
  Relay chip in the top bar (#stats), only while joined: remoteChip(...).
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
        people / govs: [{who, dev}].
        No entry whose state is not "left" -> null (not joined: no chip).
        Any "off"      -> {cls: "off", text: "联城断开 · 待发 N 条"},
                          N = the sum of queued over the "off" entries.
        Else any "refused" -> {cls: "refused", text: "联城拒绝了密钥"}.
        Else           -> {cls: "ok", text: "联城 · P 人 · D 台设备"},
                          P = distinct non-empty who over me, people, govs;
                          D = (me ? 1 : 0) + distinct dev over people, govs.
    remoteNote(who) -> "只能看：这是 <who> 的 agent，只有 <who> 能回答。"
    govSign(g)      -> "<g.who> · <g.device>"
    staleText(sec)  -> under 60: "最后更新 <floor(sec)> 秒前",
                       else "最后更新 <floor(sec / 60)> 分钟前"

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
        for name in ("remote", "remote_snapshot", "relay"):
            with self.subTest(case=name):
                self.assertIn("case '%s'" % name, script)

    def test_name_tag_and_device_chip_are_separate(self):
        text = page()
        self.assertRegex(text, r"\.rdev\s*\{", "no CSS rule for the device chip .rdev")
        self.assertRegex(inline_script(), r"['\"]rdev['\"]", "no element with class rdev")
        self.assertNotRegex(inline_script(), r"remote\.who\}\s*·\s*\$\{[^}]*remote\.device",
                            "a person still gets one combined 'who · device' tag")

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
    PEOPLE = [{"who": "Maverick", "dev": "d-pc2"}, {"who": "Ann", "dev": "d-ann"},
              {"who": "Bo", "dev": "d-bo"}]
    GOVS = [{"who": "Maverick", "dev": "d-pc2"}, {"who": "Ann", "dev": "d-ann"}]

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

    def test_pure_means_pure(self):
        section = pure_section()
        self.assertIsNotNone(section)
        for word in ("document", "window", "THREE", "citizens", "localStorage", "fetch"):
            with self.subTest(word=word):
                self.assertNotRegex(section, r"\b%s\b" % word)


if __name__ == "__main__":
    unittest.main()
