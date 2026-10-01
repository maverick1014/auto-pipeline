"""Failing tests, cloud-city-2 slice S5: the page talks from the cloud
(requirements/city.md, "Cloud page", step 2; approved mock
mock/cloud-city-2-mock.html, screens send / fail / answer / phone / later).

bin/agent-city.html stays ONE file. Cloud code stays in the blocks marked
`cloud-city`; the two message renderers are shared with the local page.

  A message of the owner, in BOTH renderers (chatHtml: the 总督's window;
  historyHtml: a session's window; before this the session's window showed no
  state at all):
      who    its entry has a cid (it was typed on the cloud page) -> chat.you.cloud
             你（云端）; else chat.you.page 你（页面）, as before. On the cloud page
             (CLOUD true) an entry with no cid was typed on the computer's own
             page: there it reads chat.you.local 你（电脑上的页面）, as in the mock
             ("页面" alone would mean the wrong page).
      state  after the who, through chat.stateSuffix as before: queued,
             delivered, undelivered, and new: 'sent' and 'taken' -> chat.state.sent 在路上
      why    an undelivered entry with a reason adds " · " + the reason:
             not-listening (as before), off, ended, talk-off, refused, flood
             -> chat.why.notListening / off / ended / talkOff / refused / flood
      resend an undelivered entry WITH a cid gets, inside its <li>,
             <button type="button" class="resend" data-resend="<cid>">重发</button> (chat.resend)
      A busy window whose last entry is a queued owner message still ends
      with <li class="msg-wait">等它做完这一步</li> (historyHtml too).
      Everything through esc() / mdLite as before; the <li> keeps its shape
      (<li class="msg" data-kind="..." data-id="..."> in chatHtml).
      Each of the two functions stays self-contained (older tests run each one
      alone): it uses only esc, i18n and mdLite, no new shared helper.
  personHistory(c, entries): a chat entry's item also carries why and cid.

  Pure helpers (between `/* cloud-city: pure */` and `/* end cloud-city: pure */`):
    cloudFeedUrl(cur) -> as before; a cur with a non-empty `chat` adds
        &chat=<URI-encoded window id>&cc=<cursor, 0 when missing>.
    cloudChatMerge(box, chat) -> the window's next box {entries, cc, busy,
        canSend, loaded: true} from the feed's "chat" {to, cc, rows, msgs}; it
        changes neither argument. BOX may be undefined or null (a window just opened).
          a row -> the entry {id: k, kind, text, at, state, why, cid}; a row
              whose k is already there replaces that entry (a change of state);
          a msg (a message on its way, or one that never reached the machine)
              -> the entry {id: cid, cid, kind: 'owner', text, at, state, why},
              unless a row with that cid is there (it shows once);
          an entry the page added itself when the owner pressed send (mine:
              true) stays until the feed knows its cid; then the feed's entry
              takes its place;
          an entry that came from a msg and is in neither list any more goes;
          order: every entry by at (equal at: the order they came in; a
              row's at is the machine's clock, a msg's the cloud's: seconds
              both), so a message on its way sits at the bottom and one that
              was never delivered stays at its own time;
          cc = chat.cc.
    cloudTalkNote(dev, now) -> why the box is off for the machine shown, a
        text key or '': 'cloud.box.talkOff' when dev.talk is not true, else
        'cloud.box.offline' when the machine is stale (cloudStale), else ''.
        No machine -> 'cloud.box.offline'.
    cloudCid() -> a new random id for a message: 22 to 40 characters of
        A-Z a-z 0-9 _ -, from crypto.getRandomValues (never Math.random).

  The page as the cloud page (CLOUD true):
    curChatTo() gives the window id for the machine's own people (never null
        because of CLOUD; a guest still has none).
    The feed request carries the open window (cloudFeedUrl with chat and cc);
        its "chat" goes through cloudChatMerge into `chats`. loadChat never
        fetches on the cloud page (the feed brings the conversation).
    sendChat(to, text) on the cloud page: POST '/api/chat/send' with the
        headers Content-Type application/json and 'X-City-Page': '1', the body
        {dev, to, text, cid: cloudCid()}; the entry shows at once (mine, state
        'sent'); 429 -> the line cloud.tooFast / cloud.tooMany under the box;
        a failure is shown, never swallowed, and the text stays in the box.
        A request that got NO answer (the network failed, or a 5xx) is sent
        again with the SAME cid, up to 3 requests in all, before the failure
        is shown: the Worker may have stored the message, and with the same
        cid it stores it once. An answered refusal (429, 4xx) is not retried.
        The local page's sendChat is unchanged (token header, {to, text}).
    A click on [data-resend] sends that entry's text again as a NEW message.
    The box is replaced by a note (cloudTalkNote: cloud.box.talkOff names the
        command `agent-city cloud-talk on`; cloud.box.offline) when the machine
        cannot take a message.
    Each machine in the row shows cloud.talk.on 可对话 or cloud.talk.off 只能看.
    Later, shown not hidden (T6): cloud.later.ask (a "?" = a permission or a
        choice: answer it on that computer), cloud.later.add (the add-agent
        button), cloud.later.demo (the demo tools). decide() and addAgent()
        still send nothing on the cloud page.
    Phone (T7): in the page's 960px rule a cloud window (.cloud-page .win) is
        a sheet over the lower part of the SCREEN (position: fixed), its
        height from --vvh, which the script keeps equal to
        window.visualViewport.height (resize), so the box stays above the
        keyboard. The sheet's height is (written exactly so, in that rule)
            max(calc(var(--vvh) * 0.56), min(calc(var(--vvh) - 12px), 400px))
        : 56% of a full screen, and with the keyboard up (little room) nearly
        all the room that is left (E2E 2026-10-01: at 470 px the sheet was
        263 px and the conversation 96 px). When the room changes while the
        owner is at the bottom of the conversation, the list stays at the
        bottom (the resize handler sets #chat's scrollTop).

Run: python3 -m unittest tests.test_agent_city_cloud_talk_page
"""

import json
import os
import re
import shutil
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import test_agent_city_page as tp  # noqa: E402

PAGE = os.path.join(ROOT, "bin", "agent-city.html")
START = "/* cloud-city: pure */"
END = "/* end cloud-city: pure */"
T0 = 1_800_000_000_000

RENDER_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns, calls } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, String, Array, Object, Date, Number };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
process.stdout.write(JSON.stringify(calls.map(([fn, args]) => {
  try { return { ok: vm.runInContext(fn, box).apply(null, args) }; }
  catch (e) { return { error: String(e && e.stack || e) }; }
})));
"""

PURE_JS = r"""
const fs = require('fs'), vm = require('vm');
const { section, calls } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let randomCalls = 0;
const real = require('crypto').webcrypto;
const crypto = { getRandomValues(a) { randomCalls += 1; return real.getRandomValues(a); } };
const mathNoRandom = Object.create(Math);
mathNoRandom.random = () => { throw new Error('Math.random is not random enough for a message id'); };
const box = { Math: mathNoRandom, Set, Map, Array, String, Number, Object, JSON, Uint8Array, Uint32Array, crypto, btoa };
vm.createContext(box);
vm.runInContext(section, box);
const out = calls.map(([fn, args]) => {
  try { return { ok: vm.runInContext(fn, box).apply(null, args) }; }
  catch (e) { return { error: String(e && e.stack || e) }; }
});
process.stdout.write(JSON.stringify({ out, randomCalls }));
"""


def page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


def script():
    return tp.inline_script()


def texts():
    return tp.js_value(tp.const_object("TEXT") or "null") or {}


def pure_section():
    text = script()
    return text[text.index(START) + len(START):text.index(END)]


def cloud_blocks():
    """The script blocks marked cloud-city, joined."""
    return "\n".join(re.findall(r"(?s)/\* cloud-city:.*?/\* end cloud-city:[^*]*\*/", script()))


def fn(case, name):
    src = tp.function_source(name)
    case.assertTrue(src, "function %s is missing" % name)
    return src


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class RenderCase(unittest.TestCase):
    def render(self, *calls):
        esc = re.search(r"^const esc = .*;$", script(), re.M)
        prelude = esc.group(0).replace("const esc", "var esc") + "\n" + tp.constants_prelude()
        fns = tp.page_fns("chatHtml", "historyHtml", optional=("mdLite",))
        out = tp.run_node(RENDER_JS, {"prelude": prelude, "fns": fns, "calls": [list(c) for c in calls]})
        for r in out:
            self.assertNotIn("error", r, r.get("error"))
        return [r["ok"] for r in out]

    def chat(self, entries, busy=False):
        return self.render(["chatHtml", [entries, "tm", busy]])[0]

    def hist(self, entries, busy=False):
        items = [{"k": e["kind"], "text": e["text"], "at": e["at"], "state": e.get("state"), "why": e.get("why"),
                  "cid": e.get("cid"), "main": True} for e in entries]
        return self.render(["historyHtml", [items, "tm", busy]])[0]


def owner(text="hi", state=None, why=None, cid=None, i=1):
    e = {"id": cid or i, "kind": "owner", "text": text, "at": 100 + i}
    if state:
        e["state"] = state
    if why:
        e["why"] = why
    if cid:
        e["cid"] = cid
    return e


class TestMessageWords(RenderCase):
    def both(self, entries, busy=False):
        return self.chat(entries, busy), self.hist(entries, busy)

    def test_texts_in_both_languages(self):
        t = texts()
        want = {"chat.state.sent": "在路上", "chat.you.cloud": "你（云端）", "chat.why.off": "那台电脑没开",
                "chat.why.ended": "这个会话已经结束", "chat.why.talkOff": "那台电脑不接收云端消息",
                "chat.resend": "重发"}
        for key, zh in want.items():
            self.assertEqual(t.get("zh", {}).get(key), zh, key)
        for key in list(want) + ["chat.why.refused", "chat.why.flood", "cloud.talk.on", "cloud.talk.off",
                                 "cloud.box.talkOff", "cloud.box.offline", "cloud.tooFast", "cloud.tooMany",
                                 "cloud.later.ask", "cloud.later.add", "cloud.later.demo"]:
            for lang in ("zh", "en"):
                self.assertTrue(t.get(lang, {}).get(key), "%s has no %s text" % (key, lang))
        self.assertEqual(t["zh"]["cloud.talk.on"], "可对话")
        self.assertIn("agent-city cloud-talk on", t["zh"]["cloud.box.talkOff"])
        self.assertIn("agent-city cloud-talk on", t["en"]["cloud.box.talkOff"])
        for key in ("cloud.later.ask", "cloud.later.add", "cloud.later.demo"):
            self.assertIn("以后开放", t["zh"][key])

    def test_on_its_way(self):
        for state in ("sent", "taken"):
            for html in self.both([owner(state=state, cid="cid-1")]):
                self.assertIn("你（云端）（在路上）", html, state)

    def test_on_the_cloud_page_the_other_page_is_named(self):
        zh = texts()["zh"]
        self.assertEqual(zh.get("chat.you.local"), "你（电脑上的页面）")
        self.assertTrue(texts()["en"].get("chat.you.local"))
        esc = re.search(r"^const esc = .*;$", script(), re.M)
        prelude = esc.group(0).replace("const esc", "var esc") + "\n" + tp.constants_prelude()
        fns = tp.page_fns("chatHtml", "historyHtml", optional=("mdLite",)).replace("var CLOUD = false;", "var CLOUD = true;")
        local, cloud = owner(state="delivered"), owner(state="delivered", cid="cid-1", i=2)
        items = [{"k": "owner", "text": e["text"], "at": e["at"], "state": e["state"], "cid": e.get("cid"), "main": True}
                 for e in (local, cloud)]
        out = tp.run_node(RENDER_JS, {"prelude": prelude, "fns": fns,
                                      "calls": [["chatHtml", [[local, cloud], "tm", False]], ["historyHtml", [items, "tm", False]]]})
        for r in out:
            self.assertNotIn("error", r, r.get("error"))
            self.assertIn("你（电脑上的页面）（已送达）", r["ok"])
            self.assertIn("你（云端）（已送达）", r["ok"])
            self.assertNotIn("你（页面）", r["ok"])

    def test_queued_and_delivered_as_before(self):
        for html in self.both([owner(state="queued", cid="cid-1")]):
            self.assertIn("你（云端）（排队中）", html)
        for html in self.both([owner(state="delivered", cid="cid-1")]):
            self.assertIn("你（云端）（已送达）", html)
        for html in self.both([owner(state="delivered")]):
            self.assertIn("你（页面）（已送达）", html, "typed on the computer's own page")
            self.assertNotIn("云端", html)

    def test_the_session_window_shows_the_state_too(self):
        html = self.hist([owner(state="queued")])
        self.assertIn("你（页面）（排队中）", html, "decision (d): one renderer rule for both windows")
        html = self.hist([owner(state="undelivered", why="not-listening")])
        self.assertIn("你（页面）（没送到） · 它没在听，收不到", html)

    def test_not_delivered_says_why(self):
        want = {"off": "那台电脑没开", "ended": "这个会话已经结束", "talk-off": "那台电脑不接收云端消息",
                "not-listening": "它没在听，收不到"}
        for why, words in want.items():
            for html in self.both([owner(state="undelivered", why=why, cid="cid-1")]):
                self.assertIn("你（云端）（没送到） · " + words, html, why)
        zh = texts()["zh"]
        for why, key in (("refused", "chat.why.refused"), ("flood", "chat.why.flood")):
            for html in self.both([owner(state="undelivered", why=why, cid="cid-1")]):
                self.assertIn("（没送到） · " + zh[key], html, why)

    def test_an_unknown_reason_shows_no_reason(self):
        for html in self.both([owner(state="undelivered", why="<img src=x onerror=1>", cid="cid-1")]):
            self.assertIn("（没送到）", html)
            self.assertNotIn("<img", html)
            self.assertNotIn(" · ", html.split("</b>")[0])

    def test_send_again_only_for_a_cloud_message_that_was_not_delivered(self):
        for html in self.both([owner(state="undelivered", why="off", cid="cid-9")]):
            self.assertRegex(html, r'<button type="button" class="resend" data-resend="cid-9">重发</button>')
        for entry in (owner(state="undelivered", why="not-listening"), owner(state="delivered", cid="cid-9"),
                      owner(state="sent", cid="cid-9"), owner(state="queued", cid="cid-9")):
            for html in self.both([entry]):
                self.assertNotIn("data-resend", html, entry)

    def test_a_cid_is_escaped(self):
        for html in self.both([owner(state="undelivered", why="off", cid='x"><script>1</script>')]):
            self.assertNotIn("<script>", html)

    def test_the_wait_line(self):
        entries = [{"id": 1, "kind": "reply", "text": "ok", "at": 1}, owner(state="queued", cid="cid-1")]
        for html in self.both(entries, busy=True):
            self.assertTrue(html.endswith('<li class="msg-wait">等它做完这一步</li>'), html[-120:])
        for html in self.both(entries, busy=False):
            self.assertNotIn("msg-wait", html)
        for html in self.both([owner(state="delivered", cid="cid-1")], busy=True):
            self.assertNotIn("msg-wait", html)

    def test_the_old_shape_stays(self):
        entries = [{"id": 1, "kind": "prompt", "text": "fix <b>it</b>", "at": 1},
                   {"id": 2, "kind": "reply", "text": "done", "at": 2}, owner(state="queued", i=3)]
        html = self.chat(entries)
        self.assertEqual(re.findall(r'<li class="msg" data-kind="(\w+)" data-id="(\d+)"', html),
                         [("prompt", "1"), ("reply", "2"), ("owner", "3")])
        self.assertIn("你（终端）", html)
        self.assertNotIn("<b>it</b>", html)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestHistoryCarriesTheState(unittest.TestCase):
    def test_person_history_keeps_why_and_cid(self):
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Object, Array, String }; vm.createContext(box); vm.runInContext(fns, box);
const items = vm.runInContext(`personHistory({ acts: [], qa: [], stuck: false }, [
  { id: 1, kind: 'owner', text: 'a', at: 5, state: 'undelivered', why: 'off', cid: 'cid-1' },
  { id: 2, kind: 'reply', text: 'b', at: 6 }])`, box);
process.stdout.write(JSON.stringify(items));
"""
        src = script()
        starts = "\n".join(m.group(0).replace("const ", "var ", 1)
                           for m in re.finditer(r"(?ms)^const (MACHINE_STARTS|AGENT_STARTS) = \[.*?\];", src))
        fns = starts + "\n" + tp.page_fns("personHistory", "markMain", "isMachinePrompt", "isAgentPrompt")
        items = tp.run_node(js, {"fns": fns})
        mine = [it for it in items if it["k"] == "owner"][0]
        self.assertEqual((mine["state"], mine.get("why"), mine.get("cid")), ("undelivered", "off", "cid-1"))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestPure(unittest.TestCase):
    def run_calls(self, calls, whole=False):
        self.assertIn(START, script())
        got = tp.run_node(PURE_JS, {"section": tp.constants_prelude() + "\n" + pure_section(), "calls": calls})
        for r in got["out"]:
            self.assertNotIn("error", r, r.get("error"))
        out = [r.get("ok") for r in got["out"]]
        return (out, got) if whole else out

    def test_feed_url_with_an_open_window(self):
        out = self.run_calls([
            ["cloudFeedUrl", [{"dev": "mac", "gen": 3, "after": 12, "chat": "s:tm1", "cc": 41}]],
            ["cloudFeedUrl", [{"dev": "mac", "gen": 3, "after": 12, "chat": "gov:t 1/&x"}]],
            ["cloudFeedUrl", [{"dev": "mac", "gen": 3, "after": 12, "chat": "", "cc": 9}]],
            ["cloudFeedUrl", [{"dev": "mac", "gen": 3, "after": 12}]],
            ["cloudFeedUrl", [{"chat": "s:tm1", "cc": 1}]],
        ])
        self.assertEqual(out[0], "/api/feed?dev=mac&gen=3&after=12&chat=s%3Atm1&cc=41")
        self.assertEqual(out[1], "/api/feed?dev=mac&gen=3&after=12&chat=gov%3At%201%2F%26x&cc=0")
        self.assertEqual(out[2], "/api/feed?dev=mac&gen=3&after=12")
        self.assertEqual(out[3], "/api/feed?dev=mac&gen=3&after=12", "no window: the address of step 1")
        self.assertEqual(out[4], "/api/feed", "no machine yet: no window either")

    ROWS = [{"k": "k1", "kind": "prompt", "text": "先写测试", "at": 10, "state": "", "why": "", "cid": ""},
            {"k": "k2", "kind": "reply", "text": "收到", "at": 20, "state": "", "why": "", "cid": ""}]

    def merge(self, box, chat):
        return self.run_calls([["cloudChatMerge", [box, chat]]])[0]

    def test_a_window_just_opened(self):
        box = self.merge(None, {"to": "s:tm1", "cc": 2, "rows": self.ROWS, "msgs": []})
        self.assertEqual([(e["id"], e["kind"], e["text"]) for e in box["entries"]],
                         [("k1", "prompt", "先写测试"), ("k2", "reply", "收到")])
        self.assertEqual((box["cc"], box["loaded"]), (2, True))
        self.assertIsNot(box.get("canSend"), False)

    def test_rows_in_the_machines_order(self):
        rows = [dict(self.ROWS[1]), dict(self.ROWS[0]), {"k": "k3", "kind": "reply", "text": "same time", "at": 20,
                                                          "state": "", "why": "", "cid": ""}]
        box = self.merge(None, {"to": "s:tm1", "cc": 3, "rows": rows, "msgs": []})
        self.assertEqual([e["id"] for e in box["entries"]], ["k1", "k2", "k3"])

    def test_a_message_on_its_way_sits_at_the_bottom_and_shows_once(self):
        first = self.merge(None, {"to": "s:tm1", "cc": 2, "rows": self.ROWS,
                                  "msgs": [{"cid": "cid-1", "text": "go on", "at": 30, "state": "sent", "why": ""}]})
        self.assertEqual([(e["id"], e.get("state")) for e in first["entries"]][-1], ("cid-1", "sent"))
        self.assertEqual((first["entries"][-1]["kind"], first["entries"][-1]["cid"]), ("owner", "cid-1"))
        taken = self.merge(first, {"to": "s:tm1", "cc": 2, "rows": [],
                                   "msgs": [{"cid": "cid-1", "text": "go on", "at": 30, "state": "taken", "why": ""}]})
        self.assertEqual([(e["id"], e.get("state")) for e in taken["entries"]],
                         [("k1", ""), ("k2", ""), ("cid-1", "taken")])
        row = {"k": "cid-1", "kind": "owner", "text": "go on", "at": 15, "state": "queued", "why": "", "cid": "cid-1"}
        late = self.merge(taken, {"to": "s:tm1", "cc": 2, "rows": [
            {"k": "k9", "kind": "reply", "text": "a reply in between", "at": 25, "state": "", "why": "", "cid": ""}],
            "msgs": [{"cid": "cid-1", "text": "go on", "at": 5, "state": "undelivered", "why": "off"}]})
        self.assertEqual([e["id"] for e in late["entries"]], ["cid-1", "k1", "k2", "k9"],
                         "every entry sits at its own time: a failed message does not stay under newer replies")
        queued = self.merge(taken, {"to": "s:tm1", "cc": 3, "rows": [row], "msgs": []})
        self.assertEqual([(e["id"], e.get("state")) for e in queued["entries"]],
                         [("k1", ""), ("cid-1", "queued"), ("k2", "")],
                         "the machine has it: one entry, at the machine's place")
        done = self.merge(queued, {"to": "s:tm1", "cc": 4, "rows": [dict(row, state="delivered")], "msgs": []})
        self.assertEqual([(e["id"], e.get("state")) for e in done["entries"]],
                         [("k1", ""), ("cid-1", "delivered"), ("k2", "")])
        self.assertEqual(done["cc"], 4)

    def test_a_row_and_a_msg_with_the_same_cid_show_once(self):
        row = {"k": "cid-1", "kind": "owner", "text": "go on", "at": 15, "state": "queued", "why": "", "cid": "cid-1"}
        box = self.merge(None, {"to": "s:tm1", "cc": 3, "rows": self.ROWS + [row],
                                "msgs": [{"cid": "cid-1", "text": "go on", "at": 5, "state": "taken", "why": ""}]})
        self.assertEqual([e["id"] for e in box["entries"]].count("cid-1"), 1)
        self.assertEqual([e for e in box["entries"] if e["id"] == "cid-1"][0]["state"], "queued")

    def test_my_own_entry_stays_until_the_feed_knows_it(self):
        mine = {"id": "cid-7", "cid": "cid-7", "kind": "owner", "text": "just typed", "at": 99, "state": "sent", "mine": True}
        start = {"entries": [dict(r, id=r["k"]) for r in self.ROWS] + [mine], "cc": 2, "loaded": True}
        same = self.merge(start, {"to": "s:tm1", "cc": 2, "rows": [], "msgs": []})
        self.assertEqual([e["id"] for e in same["entries"]], ["k1", "k2", "cid-7"], "the feed is a few seconds behind")
        known = self.merge(same, {"to": "s:tm1", "cc": 2, "rows": [],
                                  "msgs": [{"cid": "cid-7", "text": "just typed", "at": 30, "state": "undelivered", "why": "off"}]})
        last = known["entries"][-1]
        self.assertEqual((last["id"], last["state"], last["why"], bool(last.get("mine"))), ("cid-7", "undelivered", "off", False))
        self.assertEqual(len(known["entries"]), 3)

    def test_a_msg_that_left_the_feed_goes(self):
        first = self.merge(None, {"to": "s:tm1", "cc": 2, "rows": self.ROWS,
                                  "msgs": [{"cid": "cid-1", "text": "go on", "at": 5, "state": "sent", "why": ""}]})
        gone = self.merge(first, {"to": "s:tm1", "cc": 2, "rows": [], "msgs": []})
        self.assertEqual([e["id"] for e in gone["entries"]], ["k1", "k2"])

    def test_merge_changes_neither_argument(self):
        js_box = {"entries": [dict(self.ROWS[0], id="k1")], "cc": 1, "loaded": True}
        chat = {"to": "s:tm1", "cc": 2, "rows": [self.ROWS[1]], "msgs": []}
        out = self.run_calls([["(b, c) => { const before = JSON.stringify([b, c]); cloudChatMerge(b, c); "
                               "return before === JSON.stringify([b, c]); }", [js_box, chat]]])
        self.assertIs(out[0], True)

    def test_keeps_busy_and_can_send(self):
        box = self.merge({"entries": [], "cc": 0, "busy": True, "canSend": False, "loaded": True},
                         {"to": "s:tm1", "cc": 0, "rows": [], "msgs": []})
        self.assertEqual((box["busy"], box["canSend"]), (True, False))

    def test_talk_note(self):
        on = {"dev": "mac", "ts": T0, "talk": True}
        out = self.run_calls([["cloudTalkNote", [on, T0 + 1000]], ["cloudTalkNote", [dict(on, talk=False), T0 + 1000]],
                              ["cloudTalkNote", [{"dev": "mac", "ts": T0}, T0 + 1000]],
                              ["cloudTalkNote", [on, T0 + 150001]], ["cloudTalkNote", [dict(on, talk=False), T0 + 150001]],
                              ["cloudTalkNote", [None, T0]]])
        self.assertEqual(out, ["", "cloud.box.talkOff", "cloud.box.talkOff", "cloud.box.offline",
                               "cloud.box.talkOff", "cloud.box.offline"])

    def test_a_message_id_is_random(self):
        out, got = self.run_calls([["cloudCid", []], ["cloudCid", []], ["cloudCid", []]], whole=True)
        for cid in out:
            self.assertRegex(cid, r"^[A-Za-z0-9_-]{22,40}$")
        self.assertEqual(len(set(out)), 3)
        self.assertGreaterEqual(got["randomCalls"], 3, "crypto.getRandomValues, never Math.random")


SEND_JS = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns, plan } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const calls = [], delays = [];
const box = { Math, JSON, console, String, Array, Object, Date, Number, Promise, Map, Set, Error, Uint8Array,
  crypto: require('crypto').webcrypto,
  setTimeout: (fn, ms) => { delays.push(ms); return setTimeout(fn, 0); },
  fetch: (url, init) => {
    const step = plan[Math.min(calls.length, plan.length - 1)];
    calls.push({ url, method: init.method, headers: init.headers, body: JSON.parse(init.body) });
    if (step === 'throw') return Promise.reject(new TypeError('network'));
    return Promise.resolve({ ok: step.status >= 200 && step.status < 300, status: step.status,
                             json: () => Promise.resolve(step.body || {}) });
  } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
vm.runInContext("sendChat('s:tm1', 'hello')", box).then(ok => {
  const held = vm.runInContext("chats.get('s:tm1')", box) || {};
  process.stdout.write(JSON.stringify({ ok, calls, delays, entries: held.entries || [], error: held.error || '', fast: held.fast || '' }));
}).catch(e => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
"""


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestSendTriesAgainWithTheSameId(unittest.TestCase):
    """A request with no answer may still have reached the Worker. Typing the message again would
    deliver it twice; sending the same cid again cannot."""

    def send(self, *plan):
        prelude = (tp.constants_prelude() + "\nvar CLOUD = true, DEMO = false, TOKEN = '';\n"
                   "var chats = new Map(); var cloudLive = { feed: { dev: 'mac' } };\n"
                   "function renderPanel(){} function demoSendChat(){}\n")
        fns = "\n".join(tp.function_source(n) for n in ("sendChat", "cloudCid"))
        return tp.run_node(SEND_JS, {"prelude": prelude, "fns": fns, "plan": list(plan)})

    OK = {"status": 200, "body": {"ok": True, "state": "sent", "why": ""}}

    def test_one_request_when_it_works(self):
        got = self.send(self.OK)
        self.assertIs(got["ok"], True)
        self.assertEqual(len(got["calls"]), 1)
        call = got["calls"][0]
        self.assertEqual((call["url"], call["method"], call["headers"].get("X-City-Page")), ("/api/chat/send", "POST", "1"))
        self.assertEqual(set(call["body"]), {"dev", "to", "text", "cid"})
        self.assertEqual((call["body"]["dev"], call["body"]["to"], call["body"]["text"]), ("mac", "s:tm1", "hello"))
        self.assertEqual([(e["id"], e["state"]) for e in got["entries"]], [(call["body"]["cid"], "sent")])

    def test_no_answer_is_tried_again_with_the_same_id(self):
        for plan in (["throw", self.OK], [{"status": 503}, "throw", self.OK]):
            got = self.send(*plan)
            self.assertIs(got["ok"], True, plan)
            self.assertEqual(len(got["calls"]), len(plan))
            self.assertEqual(len({c["body"]["cid"] for c in got["calls"]}), 1, "every try carries the same cid")
            self.assertEqual(len(got["entries"]), 1)
            self.assertEqual(got["error"], "")

    def test_three_tries_then_it_says_so(self):
        got = self.send("throw", "throw", "throw", self.OK)
        self.assertIs(got["ok"], False)
        self.assertEqual(len(got["calls"]), 3, "three requests in all, not more")
        self.assertEqual(len({c["body"]["cid"] for c in got["calls"]}), 1)
        self.assertTrue(got["error"], "the failure is shown")
        self.assertEqual(got["entries"], [])

    def test_a_refusal_is_not_tried_again(self):
        got = self.send({"status": 429, "body": {"ok": False, "error": "too fast"}}, self.OK)
        self.assertEqual((got["ok"], len(got["calls"])), (False, 1))
        self.assertTrue(got["fast"])
        got = self.send({"status": 400, "body": {"ok": False, "error": "text"}}, self.OK)
        self.assertEqual((got["ok"], len(got["calls"])), (False, 1))
        self.assertTrue(got["error"])
        got = self.send({"status": 403, "body": {"ok": False, "error": "login required"}}, self.OK)
        self.assertEqual((got["ok"], len(got["calls"])), (False, 1))

    def test_the_worker_says_not_delivered_at_once(self):
        got = self.send({"status": 200, "body": {"ok": True, "state": "undelivered", "why": "off"}})
        self.assertIs(got["ok"], True)
        self.assertEqual([(e["state"], e["why"]) for e in got["entries"]], [("undelivered", "off")])


class TestCloudPageTalks(unittest.TestCase):
    def test_a_window_has_a_target_on_the_cloud_page(self):
        src = fn(self, "curChatTo")
        self.assertNotRegex(src, r"if \(CLOUD\)\s*return null", "the cloud page talks now")
        self.assertIn("remote", src, "a guest still has no window to talk to")

    def test_send_goes_to_the_city_worker(self):
        src = fn(self, "sendChat")
        self.assertNotRegex(src, r"if \(CLOUD\)\s*return Promise\.resolve\(false\)")
        self.assertIn("'/api/chat/send'", src)
        self.assertRegex(src, r"'X-City-Page':\s*'1'")
        self.assertIn("cloudCid(", src)
        self.assertRegex(src, r"\bdev\b")
        self.assertIn("'X-City-Token': TOKEN", src, "the local page's send is unchanged")
        self.assertRegex(src, r"429")
        self.assertIn("cloud.tooFast", src)
        self.assertIn("cloud.tooMany", src)

    def test_the_conversation_comes_with_the_feed(self):
        blocks = cloud_blocks()
        self.assertIn("cloudChatMerge(", blocks)
        src = fn(self, "loadChat")
        head = src[:src.index("fetch(")]
        self.assertRegex(head, r"if \(CLOUD\)", "on the cloud page loadChat never fetches: the feed brings the window")

    def test_send_again(self):
        self.assertRegex(script(), r"data-resend|dataset\.resend")
        self.assertRegex(script(), r"closest\(\s*'\[data-resend\]'\s*\)|\.resend\b")

    def test_the_box_says_why_it_is_off(self):
        blocks = cloud_blocks() + fn(self, "renderDetail")
        self.assertIn("cloudTalkNote(", blocks)

    def test_the_machine_row_says_who_talks(self):
        blocks = cloud_blocks()
        self.assertIn("cloud.talk.on", blocks)
        self.assertIn("cloud.talk.off", blocks)

    def test_later_is_shown(self):
        text = script()
        for key in ("cloud.later.ask", "cloud.later.add", "cloud.later.demo"):
            self.assertRegex(text, r"i18n\('%s'" % re.escape(key), key)

    def test_approve_and_add_agent_still_send_nothing(self):
        for name in ("decide", "addAgent"):
            src = fn(self, name)
            head = src[:src.index("fetch(")]
            self.assertRegex(head, r"if \(CLOUD\)[^;{]*(return|\{\s*return)", name)

    def test_only_known_addresses(self):
        urls = set(re.findall(r"fetch\(\s*'([^']+)'", script()))
        self.assertLessEqual(urls, {"/api/chat?to=", "/api/chat/send", "/api/decide", "/api/agent/add"})

    def test_phone_sheet_follows_the_keyboard(self):
        html = page()
        blocks = []
        for m in re.finditer(r"@media \(max-width: 960px\)", html):
            depth, end = 0, html.index("{", m.start())
            while True:
                depth += html[end] == "{"
                depth -= html[end] == "}"
                if depth == 0:
                    break
                end += 1
            blocks.append(html[m.start():end])
        rules = [r for b in blocks for r in re.findall(r"\.cloud-page \.win\s*\{[^}]*\}", b)]
        self.assertTrue(rules, "no phone rule for .cloud-page .win")
        rule = " ".join(rules)
        self.assertIn("position:fixed", rule.replace(" ", ""))
        self.assertIn("--vvh", rule)
        self.assertIn("max(calc(var(--vvh)*0.56),min(calc(var(--vvh)-12px),400px))", rule.replace(" ", ""),
                      "with the keyboard up the sheet takes nearly all the room that is left")
        handler = re.search(r"visualViewport[\s\S]{0,1500}", cloud_blocks())
        self.assertTrue(handler and "scrollTop" in handler.group(0),
                        "the room changed: a conversation that was at the bottom stays at the bottom")
        blocks_js = cloud_blocks()
        self.assertIn("visualViewport", blocks_js)
        self.assertIn("--vvh", blocks_js)
        self.assertRegex(blocks_js, r"visualViewport[\s\S]{0,200}addEventListener\(\s*'resize'")

    def test_the_local_page_is_untouched_by_the_sheet(self):
        html = page()
        self.assertNotRegex(html, r"(?<!\.cloud-page )\.win\s*\{[^}]*--vvh", "the sheet rule is for the cloud page only")


if __name__ == "__main__":
    unittest.main()
