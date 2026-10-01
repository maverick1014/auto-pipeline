"""Failing tests, cloud-city-1 slice 4: the same page, fed by the cloud
(requirements/city.md, "Cloud page"; approved mock mock/cloud-city-1-mock.html).

bin/agent-city.html stays ONE file for the local city, the demo and the cloud.
All cloud code sits in its own block(s), marked `cloud-city` in a comment, so
the parallel work on the rail does not meet it.

  const CLOUD = '__CITY_CLOUD__' === '1';
      Only the City Worker fills the placeholder with 1. The local server
      leaves it alone, so CLOUD is false there and nothing changes.
  const CLOUD_POLL_MS = 3000;     one feed request every 3 s while the tab shows
  const CLOUD_STALE_MS = 150000;  a machine that sent nothing for 150 s is "not online"

  Boot: `if (DEMO) seed(); else if (CLOUD) connectCloud(); else connectLive();`
  connectCloud(): fetch(cloudFeedUrl(cur)) every CLOUD_POLL_MS, never an
      EventSource; no request while document.hidden, one at once when the tab
      shows again (visibilitychange); the messages go through the page's own
      apply(); a 403 shows the login notice (with a reload link) and nothing of
      the city; a failed request shows a small "not connected" chip and tries
      again.
  View only when CLOUD: sendChat, loadChat, decide and addAgent never call
      fetch (they return before it); no chat box, no answer / approve buttons,
      a "?" opens nothing; no "add agent" button in the rail (addHtml() gives ''
      at once, city-add-agent merged 2026-10-01); demo tools are gone (as on
      the live page).
  New on the page when CLOUD (as in the mock): the machine row (class
      "machines": label, 干活 n, 等你 n, age; a tap picks that machine, kept in
      localStorage), the "只能看" pill, the account chip with the e-mail and
      退出 (a link to /cdn-cgi/access/logout), the notices 还没有机器 /
      这台机器现在没有会话 / 没有机器在线, the note in a person's window.
      Phone (the page's one breakpoint, max-width 960px): the machine row
      scrolls sideways.

  Pure helpers, between `/* cloud-city: pure */` and `/* end cloud-city: pure */`
  (plain functions; they use only their arguments, the constants above and i18n):
    cloudPick(devs, wanted) -> the dev id to show: WANTED when DEVS has it,
        else the first one (the feed lists the newest first), else ''.
    cloudFeedUrl(cur) -> '/api/feed' plus ?dev=&gen=&after= from cur
        {dev, gen, after}; the dev is URI-encoded; a cur without a dev -> '/api/feed'.
    cloudStep(cur, feed, known) -> {cur, apply}: the next cursor {dev, gen,
        after} (from the feed) and the messages to hand to apply(), in order:
        the feed's snap (when there is one), then its events. A snap that holds
        no remote_snapshot message gets one empty remote_snapshot right after
        its snapshot message ({type:'remote_snapshot', me:{}, people:[],
        govs:[], teams:[]}), so guests of the machine shown before never stay.
        A NEW PICTURE MUST ALSO MOVE THE PEOPLE ALREADY DRAWN (bounce 1,
        2026-10-01: the page's own snapshot case only places people it does
        not have yet; a machine sends a new picture about once a minute, and a
        change that falls into it comes with no event). KNOWN = the people the
        page shows now, [{id, status, done, stuck, label}] (status: 'waiting' |
        'background' | 'idle' | ''); missing or empty = nothing to catch up.
        For every agent of the snapshot that is in KNOWN and differs, catch-up
        events follow the snapshot (and its remote_snapshot), before the
        feed's events, per person in this order:
          label differs            {type:'label', id, label, terr}
          stuck false -> true      {type:'stuck', id, question:'', tool:''}
          stuck true -> false      {type:'answer', id, ok:true}
          status differs           {type: 'waiting' | 'background' | 'idle', id},
                                   or {type:'resume', id} when it is '' now
                                   (an agent without "status": 'waiting' when
                                   its "waiting" is true, else '')
          done false -> true       {type:'done', id}
        Nothing differs -> no catch-up event (no log line is made up).
    cloudKnown() (in the script block, not pure) -> that list from the page's
        own people; connectCloud calls cloudStep(cur, feed, cloudKnown()).
    cloudAge(ms) -> a short text: under 10 s 刚刚 / just now; then N 秒前,
        N 分钟前, N 小时前, N 天前 (N s ago, N min ago, N h ago, N d ago).
    cloudStale(dev, now) -> true when now - dev.ts is over CLOUD_STALE_MS.
    cloudNotice(feed, now) -> which notice the city shows, a text key or '':
        'cloud.noMachine'   the user has no machine yet
        'cloud.offline'     every machine is stale (the last picture stays)
        'cloud.noSessions'  the machine shown has no people (counts.people 0)
        ''                  otherwise
  Texts (zh and en): cloud.readOnly, cloud.machines, cloud.busy, cloud.wait,
      cloud.noMachine, cloud.noSessions, cloud.offline, cloud.login,
      cloud.logout, cloud.viewNote, cloud.notConnected, cloud.justNow.

Run: python3 -m unittest tests.test_agent_city_cloud_page
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import test_agent_city_page as tp  # noqa: E402
from test_agent_city_remote_page import RUNNER  # noqa: E402

PAGE = os.path.join(ROOT, "bin", "agent-city.html")
START = "/* cloud-city: pure */"
END = "/* end cloud-city: pure */"
T0 = 1_800_000_000_000


def page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


def script():
    return tp.inline_script()


def pure_section():
    text = script()
    if START not in text or END not in text:
        return None
    return text[text.index(START) + len(START):text.index(END)]


def fn(case, name):
    src = tp.function_source(name)
    case.assertTrue(src, "function %s is missing" % name)
    return src


class TestSwitch(unittest.TestCase):
    def test_cloud_flag(self):
        self.assertIn("const CLOUD = '__CITY_CLOUD__' === '1';", script())
        self.assertEqual(page().count("__CITY_CLOUD__"), 1, "one place decides it")

    def test_constants(self):
        self.assertRegex(script(), r"(?m)^const CLOUD_POLL_MS = 3000;")
        self.assertRegex(script(), r"(?m)^const CLOUD_STALE_MS = 150000;")

    def test_boot_picks_the_feed(self):
        self.assertIn("if (DEMO) seed(); else if (CLOUD) connectCloud(); else connectLive();", script())

    def test_local_feed_is_untouched(self):
        live = fn(self, "connectLive")
        self.assertIn("new EventSource('/events')", live)
        self.assertNotIn("CLOUD", live)

    def test_block_is_marked(self):
        self.assertGreaterEqual(len(re.findall(r"cloud-city", page())), 4,
                                "the cloud code sits in blocks marked cloud-city (css, html, script, pure)")


class TestFeedLoop(unittest.TestCase):
    def test_polls_never_streams(self):
        src = fn(self, "connectCloud")
        self.assertIn("cloudFeedUrl(", src)
        self.assertIn("fetch(", src)
        self.assertNotIn("EventSource", src)
        self.assertIn("CLOUD_POLL_MS", src)
        self.assertIn("apply(", src)
        self.assertIn("cloudStep(", src)

    def test_a_new_picture_reaches_the_people_already_drawn(self):
        src = fn(self, "connectCloud")
        self.assertIn("cloudStep(cur, feed, cloudKnown())", src)
        known = fn(self, "cloudKnown")
        for word in ("citizens", "waiting", "bgrun", "idle", "doneFlag", "stuck", "label"):
            self.assertIn(word, known, "cloudKnown() reads %s of the page's people" % word)

    def test_no_request_while_hidden(self):
        text = script()
        self.assertIn("visibilitychange", text)
        self.assertIn("document.hidden", text)

    def test_login_lost(self):
        src = fn(self, "connectCloud")
        self.assertIn("403", src)
        self.assertIn("cloud.login", script())

    def test_logout_link(self):
        self.assertIn("/cdn-cgi/access/logout", page())


class TestViewOnly(unittest.TestCase):
    def before_fetch(self, name):
        src = fn(self, name)
        self.assertIn("fetch(", src)
        head = src[:src.index("fetch(")]
        self.assertRegex(head, r"if \(CLOUD\)[^;{]*(return|\{\s*return)",
                         "%s must return before its fetch when CLOUD" % name)

    def test_chat_send_is_off(self):
        self.before_fetch("sendChat")

    def test_chat_load_is_off(self):
        self.before_fetch("loadChat")

    def test_decide_is_off(self):
        self.before_fetch("decide")

    def test_add_agent_is_off(self):
        self.before_fetch("addAgent")

    def test_no_add_agent_button(self):
        src = fn(self, "addHtml")
        self.assertRegex(src, r"^function addHtml\(group, st\)\s*\{\s*if \(CLOUD\) return '';",
                         "the cloud page is view only: addHtml() gives '' before anything else")

    def test_no_chat_target(self):
        src = fn(self, "curChatTo")
        self.assertIn("CLOUD", src, "in the cloud nobody can be talked to: curChatTo() gives null")

    def test_only_feed_and_local_urls(self):
        urls = set(re.findall(r"fetch\(\s*'([^']+)'", script()))
        self.assertLessEqual(urls, {"/api/chat?to=", "/api/chat/send", "/api/decide", "/api/agent/add"},
                             "no new acting address; the feed address comes from cloudFeedUrl()")


class TestLook(unittest.TestCase):
    def test_machine_row_and_pills(self):
        html = page()
        self.assertRegex(html, r"\.machines\s*\{")
        self.assertIn('class="machines"', html)
        self.assertIn("cloud.readOnly", html)
        self.assertIn("cloud.logout", html)

    def test_machine_choice_is_remembered(self):
        self.assertRegex(script(), r"localStorage\.(setItem|getItem)\('city-cloud-dev'")

    def test_phone_rule(self):
        html = page()
        blocks = []
        for m in re.finditer(r"@media \(max-width: 960px\)", html):
            depth, end = 0, html.index("{", m.start())
            while True:
                ch = html[end]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        break
                end += 1
            blocks.append(html[m.start():end])
        self.assertTrue([b for b in blocks if ".machines" in b], "the machine row has a phone rule")

    def test_hidden_when_not_cloud(self):
        self.assertRegex(page(), r'<nav class="machines"[^>]*\bhidden\b',
                         "the local city never shows the machine row")


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestPure(unittest.TestCase):
    def run_calls(self, calls):
        section = pure_section()
        self.assertIsNotNone(section, "no %s ... %s section" % (START, END))
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump({"section": tp.constants_prelude() + "\n" + section, "calls": calls}, fh)
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

    DEVS = [{"dev": "pc2", "label": "maverick-pc2", "ts": T0, "gen": 4,
             "counts": {"people": 2, "busy": 1, "wait": 1}},
            {"dev": "mac", "label": "MacBook-Pro", "ts": T0 - 30000, "gen": 1,
             "counts": {"people": 0, "busy": 0, "wait": 0}}]

    def test_pick(self):
        out = self.run_calls([["cloudPick", [self.DEVS, "mac"]], ["cloudPick", [self.DEVS, "gone"]],
                              ["cloudPick", [self.DEVS, ""]], ["cloudPick", [[], "mac"]],
                              ["cloudPick", [self.DEVS, None]]])
        self.assertEqual(out, ["mac", "pc2", "pc2", "", "pc2"])

    def test_feed_url(self):
        out = self.run_calls([
            ["cloudFeedUrl", [{"dev": "", "gen": 0, "after": 0}]],
            ["cloudFeedUrl", [{"dev": "mac", "gen": 3, "after": 12}]],
            ["cloudFeedUrl", [{"dev": "a b/&c", "gen": 0, "after": 0}]],
            ["cloudFeedUrl", [{}]],
        ])
        self.assertEqual(out[0], "/api/feed")
        self.assertEqual(out[1], "/api/feed?dev=mac&gen=3&after=12")
        self.assertEqual(out[2], "/api/feed?dev=a%20b%2F%26c&gen=0&after=0")
        self.assertEqual(out[3], "/api/feed")

    def test_step_first_picture(self):
        snap = {"type": "snapshot", "agents": []}
        e1, e2 = {"type": "tool", "id": "s:1"}, {"type": "idle", "id": "s:1"}
        empty = {"type": "remote_snapshot", "me": {}, "people": [], "govs": [], "teams": []}
        out = self.run_calls([["cloudStep", [{"dev": "", "gen": 0, "after": 0},
                                             {"dev": "mac", "gen": 1, "after": 2, "snap": [snap],
                                              "events": [e1, e2]}]]])[0]
        self.assertEqual(out["cur"], {"dev": "mac", "gen": 1, "after": 2})
        self.assertEqual(out["apply"], [snap, empty, e1, e2])

    def test_step_keeps_the_machines_own_guests(self):
        snap = {"type": "snapshot", "agents": []}
        guests = {"type": "remote_snapshot", "me": {"who": "m", "device": "mac"},
                  "people": [{"id": "r:d2:s:1"}], "govs": [], "teams": []}
        out = self.run_calls([["cloudStep", [{"dev": "pc2", "gen": 9, "after": 4},
                                             {"dev": "mac", "gen": 1, "after": 0,
                                              "snap": [snap, guests], "events": []}]]])[0]
        self.assertEqual(out["apply"], [snap, guests])
        self.assertEqual(out["cur"], {"dev": "mac", "gen": 1, "after": 0})

    EMPTY = {"type": "remote_snapshot", "me": {}, "people": [], "govs": [], "teams": []}

    def agent(self, pid="s:1", label="one", status="", done=False, stuck=False, terr="t1"):
        return {"id": pid, "role": "task-manager", "label": label, "task": "", "stuck": stuck,
                "waiting": status == "waiting", "done": done, "status": status, "tools": {}, "terr": terr}

    def known(self, pid="s:1", label="one", status="", done=False, stuck=False):
        return {"id": pid, "label": label, "status": status, "done": done, "stuck": stuck}

    def picture(self, gen, *agents, events=()):
        return {"dev": "mac", "gen": gen, "after": 0,
                "snap": [{"type": "snapshot", "agents": list(agents)}], "events": list(events)}

    def test_two_pictures_in_a_row_no_events(self):
        # bounce 1: the change is INSIDE the new picture, no event comes with it
        cur = {"dev": "mac", "gen": 1, "after": 3}
        waiting = self.picture(2, self.agent(status="waiting"))
        busy = self.picture(3, self.agent(status=""))
        out = self.run_calls([
            ["cloudStep", [cur, waiting, [self.known(status="")]]],
            ["cloudStep", [{"dev": "mac", "gen": 2, "after": 0}, busy, [self.known(status="waiting")]]],
        ])
        self.assertEqual(out[0]["apply"], [waiting["snap"][0], self.EMPTY, {"type": "waiting", "id": "s:1"}])
        self.assertEqual(out[0]["cur"], {"dev": "mac", "gen": 2, "after": 0})
        self.assertEqual(out[1]["apply"], [busy["snap"][0], self.EMPTY, {"type": "resume", "id": "s:1"}])

    def test_catch_up_every_kind_of_change(self):
        cases = [
            (self.agent(status="background"), self.known(status=""), [{"type": "background", "id": "s:1"}]),
            (self.agent(status="idle"), self.known(status="waiting"), [{"type": "idle", "id": "s:1"}]),
            (self.agent(label="cloud-city-1 Task Manager"), self.known(label="task-manager"),
             [{"type": "label", "id": "s:1", "label": "cloud-city-1 Task Manager", "terr": "t1"}]),
            (self.agent(stuck=True), self.known(), [{"type": "stuck", "id": "s:1", "question": "", "tool": ""}]),
            (self.agent(stuck=False), self.known(stuck=True), [{"type": "answer", "id": "s:1", "ok": True}]),
            (self.agent(done=True), self.known(), [{"type": "done", "id": "s:1"}]),
            (self.agent(label="new", status="waiting", done=True), self.known(label="old"),
             [{"type": "label", "id": "s:1", "label": "new", "terr": "t1"},
              {"type": "waiting", "id": "s:1"}, {"type": "done", "id": "s:1"}]),
        ]
        cur = {"dev": "mac", "gen": 1, "after": 0}
        out = self.run_calls([["cloudStep", [cur, self.picture(2, a), [k]]] for a, k, _ in cases])
        for (a, k, want), got in zip(cases, out):
            self.assertEqual(got["apply"][2:], want, (a, k))

    def test_no_change_no_catch_up(self):
        cur = {"dev": "mac", "gen": 1, "after": 0}
        same = self.picture(2, self.agent(status="waiting", stuck=True, done=False, label="one"))
        new_person = self.picture(2, self.agent(pid="s:2", status="waiting"))
        old_server = self.picture(2, {"id": "s:1", "label": "one", "waiting": True, "done": False,
                                      "stuck": False, "terr": "t1"})
        out = self.run_calls([
            ["cloudStep", [cur, same, [self.known(status="waiting", stuck=True)]]],
            ["cloudStep", [cur, new_person, [self.known()]]],        # s:2 is placed by the snapshot itself
            ["cloudStep", [cur, same, []]],
            ["cloudStep", [cur, same]],                              # no third argument: as before
            ["cloudStep", [cur, old_server, [self.known(status="")]]],
        ])
        for got in out[:4]:
            self.assertEqual(len(got["apply"]), 2, got["apply"])
        self.assertEqual(out[4]["apply"][2:], [{"type": "waiting", "id": "s:1"}],
                         "an agent without a status field: its waiting flag decides")

    def test_catch_up_comes_before_the_feeds_events(self):
        cur = {"dev": "mac", "gen": 1, "after": 0}
        later = {"type": "tool", "id": "s:1", "tool": "Bash", "name": "Bash"}
        feed = self.picture(2, self.agent(status="waiting"), events=[later])
        out = self.run_calls([["cloudStep", [cur, feed, [self.known()]]]])[0]
        self.assertEqual(out["apply"][2:], [{"type": "waiting", "id": "s:1"}, later])

    def test_events_without_a_picture_need_no_catch_up(self):
        e = {"type": "waiting", "id": "s:1"}
        out = self.run_calls([["cloudStep", [{"dev": "mac", "gen": 1, "after": 2},
                                             {"dev": "mac", "gen": 1, "after": 3, "events": [e]},
                                             [self.known(status="")]]]])[0]
        self.assertEqual(out["apply"], [e])

    def test_step_events_only(self):
        e3 = {"type": "waiting", "id": "s:1"}
        out = self.run_calls([
            ["cloudStep", [{"dev": "mac", "gen": 1, "after": 2}, {"dev": "mac", "gen": 1, "after": 3, "events": [e3]}]],
            ["cloudStep", [{"dev": "mac", "gen": 1, "after": 3}, {"dev": "mac", "gen": 1, "after": 3, "events": []}]],
            ["cloudStep", [{"dev": "mac", "gen": 1, "after": 3}, {"dev": "", "gen": 0, "after": 0, "events": []}]],
        ])
        self.assertEqual(out[0], {"cur": {"dev": "mac", "gen": 1, "after": 3}, "apply": [e3]})
        self.assertEqual(out[1], {"cur": {"dev": "mac", "gen": 1, "after": 3}, "apply": []})
        self.assertEqual(out[2], {"cur": {"dev": "", "gen": 0, "after": 0}, "apply": []})

    def test_age(self):
        out = self.run_calls([["cloudAge", [ms]] for ms in
                              (0, 9000, 10000, 59000, 60000, 3599000, 3600000, 7200000, 86400000, 3 * 86400000, -5)])
        self.assertEqual(out, ["刚刚", "刚刚", "10 秒前", "59 秒前", "1 分钟前", "59 分钟前",
                               "1 小时前", "2 小时前", "1 天前", "3 天前", "刚刚"])

    def test_stale(self):
        dev = {"dev": "mac", "ts": T0}
        out = self.run_calls([["cloudStale", [dev, T0 + 149000]], ["cloudStale", [dev, T0 + 150001]],
                              ["cloudStale", [dev, T0 - 5000]]])
        self.assertEqual(out, [False, True, False])

    def test_notice(self):
        def feed(devs, dev):
            return {"devs": devs, "dev": dev}
        now = T0 + 1000
        late = T0 + 400000
        busy_only = [self.DEVS[0]]
        out = self.run_calls([
            ["cloudNotice", [feed([], ""), now]],
            ["cloudNotice", [feed(self.DEVS, "pc2"), now]],
            ["cloudNotice", [feed(self.DEVS, "mac"), now]],
            ["cloudNotice", [feed(self.DEVS, "pc2"), late]],
            ["cloudNotice", [feed(self.DEVS, "mac"), late]],
            ["cloudNotice", [feed(busy_only, "pc2"), T0 + 149000]],
        ])
        self.assertEqual(out, ["cloud.noMachine", "", "cloud.noSessions", "cloud.offline",
                               "cloud.offline", ""])

    def test_texts_in_both_languages(self):
        keys = ["cloud.readOnly", "cloud.machines", "cloud.busy", "cloud.wait", "cloud.noMachine",
                "cloud.noSessions", "cloud.offline", "cloud.login", "cloud.logout", "cloud.viewNote",
                "cloud.notConnected", "cloud.justNow"]
        out = self.run_calls([["(k => [TEXT.zh[k], TEXT.en[k]])", [k]] for k in keys])
        for key, (zh, en) in zip(keys, out):
            self.assertTrue(zh and en, "%s needs a zh and an en text" % key)
            self.assertNotEqual(zh, en, key)
        self.assertEqual(out[0][0], "只能看")
        self.assertEqual(out[-1], ["刚刚", "just now"])


if __name__ == "__main__":
    unittest.main()
