"""Failing tests for cloud-polish, part 1 (owner + laptop main manager, 2026-10-02, found on the owner's
real Cloudflare account): Q2 a governor is a session and is counted, Q3 the head of an open window follows
its person, Q4 `agent-city status` names the repos the cloud does not show, Q6 a second helper gets a free
name. The page layout (Q1 the two rows on the stage, Q5 the small + icon) has its own test file after the
mock is approved (mock/cloud-polish-mock.html).

Q2  A GOVERNOR IS A SESSION (measured: a machine whose only session is a governor uploaded
    {"people": 0, "busy": 0, "wait": 0}: the machine chip said 干活 0, the rail header said 在线 0 while the
    group said 1, and the notice 这台机器现在没有会话 covered the city while the governor stood there, busy).

  bin/agent_city.py
    CityState.cloud_counts(terrs) -> {"people", "wait", "busy"}: as before for the people, PLUS the seated
      governor (reducer.gov_sid is not None) of every territory in TERRS: people + 1; wait + 1 when its
      state is "waiting"; busy + 1 when its state is "busy"; "idle" and "background" count as a person
      only. A governor of a territory outside TERRS is never counted. An "unknown" governor (seen in a past
      run, not seated in this one) is not a session: not counted.

  bin/agent-city.html
    cloudNotice(feed, now, sessions): the third argument is how many sessions the page itself draws for the
      machine shown (its own people and its present governors). 'cloud.noSessions' only when the feed's
      counts say people 0 AND sessions is 0 (left out or not a number: the counts alone decide, as before).
      cloudRenderNotice passes it: own citizens (not remote, not gone) + governorFigures().length. So a
      machine that still runs the old upload (people 0 with a governor) shows no false notice either.
    railCount(groups) -> {active, you}: a governor row counts (railGroups() only has one while that
      territory's governor is present): active = every row that is not resting, the governor too; you =
      those waiting on the owner: a citizen whose citizenStatus(c)[0] is 'you', a governor whose state is
      'waiting'. railHtml(): the badge on a folded group's head counts the same way.
    topCounts(): 干活 (the first pair) also counts every present governor of my own city (governorFigures())
      whose state is 'busy'. Waiting, idle, background, away and unknown governors change nothing; the other
      pairs are as before. (#demo has no governor state: nothing changes there.)

Q3  THE HEAD OF AN OPEN WINDOW FOLLOWS ITS PERSON (owner's screenshot, cloud page: the rail row said 总督
    在忙 while the open window's head chip still said 空闲). Cause: renderDetail() refreshed the head chip on
    every call for a citizen only; the governor's chip was written when the card was built, and the card's
    key holds no governor state, so it kept its first word for as long as the window stayed open (on the
    local page too).

  bin/agent-city.html, simulation section
    headPill(sel) -> [class, text] of the head chip of the window of selection SEL, or null:
      {t: 'gov', terr}  -> govRowStatus(terr || govTerr)  (the very words of the rail row)
      {t: 'c', id}      -> citizenStatus(byId(id), governorCount); an unknown id -> null
      anything else (a building, another member's governor, null) -> null
    refreshHeadPill(el, sel): the element el.querySelector('.p-head .pill') gets className 'pill <class>'
      and that text, each written only when it differs. headPill(sel) null, or no such element: nothing,
      never an error.
  3D view
    renderDetail() calls refreshHeadPill(el, selected) on EVERY call, after the part that rebuilds the
      card (after "lastChatTo = chatTo;"). Only the head: the body of the panel is not touched here.

Q4  `agent-city status` SAYS WHICH REPOS THE CLOUD DOES NOT SHOW (only repos joined to a relay go up: the
    rule stays; the owner could not see it anywhere).

  bin/agent_city.py
    CityState.health() gains "not_joined": the names (as the page's world view names the territory), sorted,
      each once, of every territory that has a live session now (reducer.sessions is not empty: a seated
      governor or a session citizen) and whose repo folder (repo_folder(identity)) has no join file that
      agent_city_relay.read_join() accepts (<folder>/.secrets/agent-city-relay). Names only: never a path.
  bin/agent-city.sh status
    One more line, the LAST one, only when all three hold: the city server runs (DIR/on), the cloud marker
    (<AGENT_CITY_HOME>/cloud) names at least one relay host, and /health's "not_joined" is a list with at
    least one name:
        NOT SHOWN IN THE CLOUD: v4-plus, v4-pospro (not joined)
    The names as the server gave them, joined by ", "; an entry that is not a string, is empty or holds a
    "/" is left out (no path is ever printed). No server, no answer in 2 s, an old server without the key,
    an empty list, no marker: no line, and status still exits 0 with its other lines. Inside a repo and
    outside one alike.

Q6  A SECOND HELPER GETS A FREE NAME (the owner opened two helpers in one repo: both were named
    "<repo> Helper", and SendMessage needed a [ref] to tell them apart).

  bin/agent_city.py  CityState.add_agent(terr, now, force=False)
    role "helper": the name is the first free one of "<repo> Helper", "<repo> Helper 2", "<repo> Helper 3",
      ... A name is TAKEN when, in that repo's own territory,
        - a live session citizen's label is exactly that name, or
        - this city gave that name to a session it opened (add_agent) that showed up and is still live,
          whatever its label says (its title may not have been read yet).
      A session that ended frees its name. Another repo's sessions never count.
    role "main": the name stays "<repo> Manager", always.
    The same name everywhere: the answer's "name", the opener's title, `claude --name`, the "plain" command,
      the "adding" event.

Run: python3 -m unittest tests.test_agent_city_cloud_polish </dev/null
"""

import json
import os
import shlex
import shutil
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
import agent_city_relay as rl  # noqa: E402
import test_agent_city_cloud_page as cp  # noqa: E402
from cityhelp import lock_file  # noqa: E402
from relayhelp import join  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402
from test_agent_city_add_agent import FLAGS, PROMPT, AddCase, line  # noqa: E402
from test_agent_city_cloud_upload import UploadCase  # noqa: E402
from test_agent_city_page import function_source  # noqa: E402
from test_agent_city_people import run_sim  # noqa: E402
from test_agent_city_server import wait_for  # noqa: E402
from test_agent_city_ux2 import SNAPSHOT, payload  # noqa: E402

RELAY = "https://relay.example.test/t/team-1"


def note(sid, repo, need="", bg=""):
    """The Stop hook's note at the end of a turn: need "1" -> waiting, bg "1" -> background, else idle."""
    return dict(line("StopNote", sid, repo), need=need, bg=bg)


# ---------------------------------------------------------------------------
# Q2, server: the uploaded counts
# ---------------------------------------------------------------------------

class TestGovernorIsCounted(AddCase):
    def setUp(self):
        super().setUp()
        self.mains[self.shop] = "g1"

    def counts(self, *idents):
        return self.state.cloud_counts({ac.territory_id(i) for i in idents or (self.shop,)})

    def test_a_busy_governor_alone(self):
        self.feed(line("UserPromptSubmit", "g1", self.shop))
        self.assertEqual(self.counts(), {"people": 1, "busy": 1, "wait": 0})

    def test_an_idle_governor_is_a_person(self):
        self.feed(line("UserPromptSubmit", "g1", self.shop), line("Stop", "g1", self.shop))
        self.assertEqual(self.counts(), {"people": 1, "busy": 0, "wait": 0})

    def test_a_waiting_governor_waits(self):
        self.feed(line("UserPromptSubmit", "g1", self.shop), line("PermissionRequest", "g1", self.shop))
        self.assertEqual(self.counts(), {"people": 1, "busy": 0, "wait": 1})
        self.feed(line("Stop", "g1", self.shop), note("g1", self.shop, need="1"))
        self.assertEqual(self.counts(), {"people": 1, "busy": 0, "wait": 1})

    def test_a_governor_in_the_background_is_a_person_only(self):
        self.feed(line("UserPromptSubmit", "g1", self.shop), line("Stop", "g1", self.shop), note("g1", self.shop, bg="1"))
        self.assertEqual(self.counts(), {"people": 1, "busy": 0, "wait": 0})

    def test_governor_and_helper(self):
        self.feed(line("UserPromptSubmit", "g1", self.shop), line("UserPromptSubmit", "h1", self.shop))
        self.assertEqual(self.counts(), {"people": 2, "busy": 2, "wait": 0})
        self.feed(line("Stop", "g1", self.shop))
        self.assertEqual(self.counts(), {"people": 2, "busy": 1, "wait": 0})

    def test_no_session_at_all(self):
        self.feed(line("UserPromptSubmit", "g1", self.shop), line("SessionEnd", "g1", self.shop))
        self.assertEqual(self.counts(), {"people": 0, "busy": 0, "wait": 0})

    def test_only_the_territories_asked_for(self):
        other = self.repo("other")
        self.mains[other] = "g2"
        self.feed(line("UserPromptSubmit", "g1", self.shop), line("UserPromptSubmit", "g2", other))
        self.assertEqual(self.counts(self.shop), {"people": 1, "busy": 1, "wait": 0})
        self.assertEqual(self.counts(self.shop, other), {"people": 2, "busy": 2, "wait": 0})
        self.assertEqual(self.state.cloud_counts(set()), {"people": 0, "busy": 0, "wait": 0})


class TestGovernorOnlyPictureGoesUp(UploadCase):
    def test_the_view_counts_the_governor(self):
        """The measured case, end to end: the machine's only session is the main manager."""
        lock_file(os.path.join(self.repo, ".git"), "g1")
        self.up(snap_sec="0.5")
        self.add(sid="g1", ev="UserPromptSubmit")
        self.assertTrue(wait_for(lambda: self.health()["lines"] >= 1), "the line was never read")
        self.assertEqual(self.health()["agents"], 0, "the session is the governor, not a citizen")
        self.assertTrue(wait_for(lambda: (self.fake.view_of() or {}).get("counts") ==
                                 {"people": 1, "busy": 1, "wait": 0}, timeout=10),
                        "counts: %r" % ((self.fake.view_of() or {}).get("counts"),))


# ---------------------------------------------------------------------------
# Q2, page: the notice and the page's own counters
# ---------------------------------------------------------------------------

@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestNoticeNeedsNoSessionAtAll(unittest.TestCase):
    T0 = cp.T0
    DEVS = [{"dev": "mac", "label": "MacBook-Pro", "ts": cp.T0, "gen": 1,
             "counts": {"people": 0, "busy": 0, "wait": 0}}]

    def notice(self, *more):
        feed = {"devs": self.DEVS, "dev": "mac"}
        return cp.TestPure.run_calls(self, [["cloudNotice", [feed, self.T0 + 1000] + list(more)]])[0]

    def test_no_session_at_all_shows_it(self):
        self.assertEqual(self.notice(0), "cloud.noSessions")

    def test_a_governor_the_page_draws_hides_it(self):
        self.assertEqual(self.notice(1), "", "the feed's counts say 0 (an old upload), the page draws a governor")
        self.assertEqual(self.notice(3), "")

    def test_without_the_third_argument_the_counts_decide(self):
        self.assertEqual(self.notice(), "cloud.noSessions")
        self.assertEqual(self.notice(None), "cloud.noSessions")

    def test_counts_with_people_never_show_it(self):
        feed = {"devs": [dict(self.DEVS[0], counts={"people": 1, "busy": 1, "wait": 0})], "dev": "mac"}
        out = cp.TestPure.run_calls(self, [["cloudNotice", [feed, self.T0 + 1000, 0]]])
        self.assertEqual(out, [""])

    def test_the_page_passes_what_it_draws(self):
        src = function_source("cloudRenderNotice") or ""
        self.assertRegex(src, r"cloudNotice\(feed,\s*feed\.now,\s*[^)\s]", "cloudNotice gets a third argument")
        self.assertIn("governorFigures(", src, "the present governors are sessions")
        self.assertIn("citizens", src)


COUNT_DRIVER = SNAPSHOT + r"""
const setGov = state => apply({ type: 'gov', state, terr: A.id, present: true });
const work = () => topCounts()[0][1];
const out = {};
out.busy = railCount(railGroups());                    // gov(A) busy + s:L w1 f1 remote y1
out.workBusy = work();
setGov('idle'); out.workIdle = work(); out.idle = railCount(railGroups());
setGov('waiting'); out.workWaiting = work(); out.waiting = railCount(railGroups());
out.closedWaiting = railHtml(railGroups(), null, new Set([A.id]), new Set());
setGov('background'); out.workBg = work(); out.bg = railCount(railGroups());
setGov('busy');
out.pairs = topCounts().map(p => p[0]);
// the measured case: nobody but the governor (a new picture with no people; the other member's person leaves)
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'busy' }], agents: [] });
for (const c of citizens) c.gone = true;
out.aloneRows = railGroups().find(g => g.terr === A.id).rows.map(r => r.id);
out.alone = railCount(railGroups());
out.workAlone = work();
setGov('waiting'); out.aloneWaiting = railCount(railGroups());
apply({ type: 'gov', state: 'idle', terr: A.id, present: false });
out.gone = railCount(railGroups()); out.workGone = work();
out.a = A.id;
__out = out;
"""


class TestPageCountsTheGovernor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(COUNT_DRIVER, payload(), ("apply", "landState", "railGroups", "railHtml", "railCount",
                                                  "topCounts", "newCitizen", "citizens", "byId"))

    def test_the_rail_header_counts_the_governor(self):
        self.assertEqual(self.r["busy"], {"active": 6, "you": 0}, "gov s:L w1 f1 remote y1")
        self.assertEqual(self.r["idle"], {"active": 6, "you": 0}, "an idle governor is online too")
        self.assertEqual(self.r["bg"], {"active": 6, "you": 0})

    def test_a_waiting_governor_waits_on_you(self):
        self.assertEqual(self.r["waiting"], {"active": 6, "you": 1})
        self.assertRegex(self.r["closedWaiting"], r'<span class="you">\s*1\s*</span>',
                         "the folded group's head badge counts the waiting governor")

    def test_a_governor_alone_is_one_online(self):
        self.assertEqual(self.r["aloneRows"], ["gov:" + self.r["a"]])
        self.assertEqual(self.r["alone"], {"active": 1, "you": 0}, "在线 1, as the group says")
        self.assertEqual(self.r["aloneWaiting"], {"active": 1, "you": 1})

    def test_no_governor_no_count(self):
        self.assertEqual(self.r["gone"], {"active": 0, "you": 0})
        self.assertEqual(self.r["workGone"], 0)

    def test_a_busy_governor_is_at_work_in_the_top_counts(self):
        self.assertEqual(self.r["workBusy"] - self.r["workIdle"], 1, "干活 counts the busy governor")
        self.assertEqual(self.r["workWaiting"], self.r["workIdle"], "a waiting governor is not at work")
        self.assertEqual(self.r["workBg"], self.r["workIdle"])
        self.assertEqual(self.r["workAlone"], 1, "the measured case: 干活 1, not 0")
        self.assertEqual(len(self.r["pairs"]), 4, "the same four pairs")


# ---------------------------------------------------------------------------
# Q3: the head of an open window follows its person
# ---------------------------------------------------------------------------

HEAD_DRIVER = SNAPSHOT + r"""
const setGov = state => apply({ type: 'gov', state, terr: A.id, present: true });
let writes = 0;
const pill = { _c: 'pill gov', _t: '', get className(){ return this._c; }, set className(v){ writes++; this._c = v; },
               get textContent(){ return this._t; }, set textContent(v){ writes++; this._t = v; } };
const asked = [];
const el = { querySelector: s => { asked.push(s); return s === '.p-head .pill' ? pill : null; } };
const look = sel => { refreshHeadPill(el, sel); return [pill._c, pill._t]; };
const rail = () => { const s = govRowStatus(A.id); return ['pill ' + s[0], s[1]]; };
const gsel = { t: 'gov', terr: A.id }, out = { gov: [], rail: [] };
for (const st of ['busy', 'waiting', 'idle', 'background', 'busy']) { setGov(st); out.gov.push(look(gsel)); out.rail.push(rail()); }
out.words = [i18n('gov.busyRow'), i18n('status.waiting'), i18n('gov.idleRow'), i18n('status.background')];
// written only when it differs
writes = 0; look(gsel); look(gsel); out.sameWrites = writes;
// the home governor: a selection without a territory
out.home = [headPill({ t: 'gov' }), govRowStatus(govTerr)];
// a citizen: the words of citizenStatus, now
const f1 = byId('f1'), csel = { t: 'c', id: 'f1' };
const want = () => { const s = citizenStatus(f1, governorCount); return ['pill ' + s[0], s[1]]; };
out.c = [[look(csel), want()]];
f1.waiting = true; out.c.push([look(csel), want()]);
f1.waiting = false; f1.idle = true; out.c.push([look(csel), want()]);
f1.idle = false; out.c.push([look(csel), want()]);
out.waitWord = i18n('status.waiting_reply');
// nothing to say: nothing written, no error
const before = [pill._c, pill._t]; writes = 0;
for (const sel of [null, undefined, { t: 'b', id: 'x' }, { t: 'rg', id: 'q' }, { t: 'c', id: 'nope' }]) refreshHeadPill(el, sel);
out.untouched = writes === 0 && pill._c === before[0] && pill._t === before[1];
out.nulls = [headPill(null), headPill({ t: 'b', id: 'x' }), headPill({ t: 'rg', id: 'q' }), headPill({ t: 'c', id: 'nope' })];
refreshHeadPill({ querySelector: () => null }, gsel);     // a card with no head chip
out.asked = [...new Set(asked)];
__out = out;
"""


class TestWindowHeadFollowsItsPerson(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(HEAD_DRIVER, payload(), ("apply", "landState", "headPill", "refreshHeadPill", "govRowStatus",
                                                 "citizenStatus", "byId", "newCitizen", "citizens"))

    def test_the_governors_chip_follows_its_state_while_open(self):
        busy, waiting, idle, bg = self.r["words"]
        self.assertEqual(self.r["gov"], [["pill gov", busy], ["pill gov", waiting], ["pill gov", idle],
                                         ["pill bgrun", bg], ["pill gov", busy]])

    def test_the_head_and_the_rail_row_say_the_same(self):
        self.assertEqual(self.r["gov"], self.r["rail"])

    def test_written_only_when_it_differs(self):
        self.assertEqual(self.r["sameWrites"], 0)

    def test_the_home_governor(self):
        self.assertEqual(self.r["home"][0], self.r["home"][1])

    def test_a_citizens_chip_follows_too(self):
        for got, want in self.r["c"]:
            self.assertEqual(got, want)
        self.assertEqual(self.r["c"][1][0], ["pill you", self.r["waitWord"]])
        self.assertEqual(len({tuple(got) for got, _ in self.r["c"]}), 3, "work, waiting, idle: three different chips")

    def test_nothing_to_say_changes_nothing(self):
        self.assertTrue(self.r["untouched"])
        self.assertEqual(self.r["nulls"], [None, None, None, None])
        self.assertEqual(self.r["asked"], [".p-head .pill"], "the head chip only, nothing else of the panel")

    def test_render_detail_refreshes_the_head_on_every_call(self):
        rd = function_source("renderDetail") or ""
        self.assertIn("lastChatTo = chatTo;", rd)
        tail = rd[rd.index("lastChatTo = chatTo;"):]
        self.assertRegex(tail, r"refreshHeadPill\(\s*el\s*,\s*selected\s*\)",
                         "after the rebuild part, every call refreshes the head chip, for a governor too")


# ---------------------------------------------------------------------------
# Q4: status names the repos the cloud does not show
# ---------------------------------------------------------------------------

class TestHealthNamesNotJoined(AddCase):
    def joined(self, identity):
        join(os.path.dirname(identity), RELAY)

    def names(self):
        return self.state.health().get("not_joined")

    def test_a_live_session_in_a_repo_that_is_not_joined(self):
        private = self.repo("v4-plus")
        self.joined(self.shop)
        self.feed(line("UserPromptSubmit", "s1", self.shop), line("UserPromptSubmit", "p1", private))
        self.assertEqual(self.names(), ["v4-plus"])

    def test_sorted_and_each_once(self):
        b, a = self.repo("v4-pospro"), self.repo("v4-plus")
        self.feed(line("UserPromptSubmit", "b1", b), line("UserPromptSubmit", "a1", a),
                  line("UserPromptSubmit", "a2", a), line("UserPromptSubmit", "s1", self.shop))
        self.assertEqual(self.names(), ["shop", "v4-plus", "v4-pospro"])

    def test_a_governor_alone_is_a_live_session(self):
        self.mains[self.shop] = "g1"
        self.feed(line("UserPromptSubmit", "g1", self.shop))
        self.assertEqual(self.names(), ["shop"])

    def test_all_joined_is_an_empty_list(self):
        self.joined(self.shop)
        self.feed(line("UserPromptSubmit", "s1", self.shop))
        self.assertEqual(self.names(), [])

    def test_nobody_live_is_not_named(self):
        self.feed(line("UserPromptSubmit", "s1", self.shop), line("SessionEnd", "s1", self.shop))
        self.assertEqual(self.names(), [], "the territory stays in the world, its last session ended")

    def test_a_broken_join_file_is_not_joined(self):
        folder = os.path.dirname(self.shop)
        os.makedirs(os.path.join(folder, ".secrets"))
        with open(os.path.join(folder, ".secrets", "agent-city-relay"), "w") as fh:
            fh.write("nothing useful\n")
        self.feed(line("UserPromptSubmit", "s1", self.shop))
        self.assertEqual(self.names(), ["shop"])

    def test_names_only(self):
        self.feed(line("UserPromptSubmit", "s1", self.shop))
        names = self.names()
        self.assertEqual(names, ["shop"])
        for name in names:
            self.assertNotIn("/", name)
        self.assertNotIn(self.base, json.dumps(self.state.health()), "no path in /health")


class _Health(BaseHTTPRequestHandler):
    body = {}

    def do_GET(self):
        data = json.dumps(self.server.body).encode("utf-8") if self.path == "/health" else b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


LINE = "NOT SHOWN IN THE CLOUD: "


class TestStatusLine(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.repo.base, "cityhome")
        self.dir = os.path.join(self.repo.base, "city")
        os.makedirs(self.home)
        os.makedirs(self.dir)
        self.server = None

    def tearDown(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        super().tearDown()

    def city(self, body):
        """A stand-in city server: DIR/on names this (live) test process and its port."""
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Health)
        self.server.body = body
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        with open(os.path.join(self.dir, "on"), "w") as fh:
            fh.write("%d %d\n" % (os.getpid(), self.server.server_address[1]))

    def cloud_on(self):
        rl.set_cloud(os.path.join(self.home, "cloud"), "relay.example.test", True)

    def status(self, cwd=None):
        result = self.repo.run("agent-city.sh", "status", cwd=cwd,
                               env={"AGENT_CITY_HOME": self.home, "AGENT_CITY_DIR": self.dir}, timeout=60)
        self.assertOk(result)
        return self.lines(result.stdout)

    def hidden(self, lines):
        return [x for x in lines if x.startswith("NOT SHOWN")]

    def test_the_line(self):
        self.city({"ok": True, "not_joined": ["v4-plus", "v4-pospro"]})
        self.cloud_on()
        lines = self.status()
        self.assertEqual(self.hidden(lines), [LINE + "v4-plus, v4-pospro (not joined)"])
        self.assertEqual(lines[-1], LINE + "v4-plus, v4-pospro (not joined)", "the last line")
        self.assertTrue(lines[0].startswith("CITY: running"), lines)

    def test_one_repo(self):
        self.city({"ok": True, "not_joined": ["v4-plus"]})
        self.cloud_on()
        self.assertEqual(self.hidden(self.status()), [LINE + "v4-plus (not joined)"])

    def test_outside_a_repo_too(self):
        self.city({"ok": True, "not_joined": ["v4-plus"]})
        self.cloud_on()
        outside = os.path.join(self.repo.base, "nowhere")
        os.makedirs(outside)
        self.assertEqual(self.hidden(self.status(cwd=outside)), [LINE + "v4-plus (not joined)"])

    def test_nothing_hidden_no_line(self):
        self.city({"ok": True, "not_joined": []})
        self.cloud_on()
        self.assertEqual(self.hidden(self.status()), [])

    def test_no_cloud_on_this_machine_no_line(self):
        self.city({"ok": True, "not_joined": ["v4-plus"]})
        self.assertEqual(self.hidden(self.status()), [], "no marker: nothing of this machine goes to a cloud page")

    def test_no_city_server_no_line(self):
        self.cloud_on()
        lines = self.status()
        self.assertEqual(self.hidden(lines), [])
        self.assertEqual(lines[0], "CITY: not running")

    def test_an_old_server_without_the_key(self):
        self.city({"ok": True, "agents": 2})
        self.cloud_on()
        self.assertEqual(self.hidden(self.status()), [])

    def test_never_a_path_never_junk(self):
        self.city({"ok": True, "not_joined": ["v4-plus", "/Users/x/secret-repo", "", 7, None, "a/b"]})
        self.cloud_on()
        self.assertEqual(self.hidden(self.status()), [LINE + "v4-plus (not joined)"])
        self.city({"ok": True, "not_joined": "v4-plus"})
        self.assertEqual(self.hidden(self.status()), [], "not a list: no line")

    def test_only_paths_no_line(self):
        self.city({"ok": True, "not_joined": ["/Users/x/secret-repo"]})
        self.cloud_on()
        self.assertEqual(self.hidden(self.status()), [])


# ---------------------------------------------------------------------------
# Q6: a second helper gets a free name
# ---------------------------------------------------------------------------

class Titles:
    """Stands in for TitleReader: path -> the session's own name."""

    def __init__(self):
        self.map = {}

    def title(self, path):
        return self.map.get(path, "")


class TestHelperNames(AddCase):
    def setUp(self):
        super().setUp()
        self.titles = Titles()
        self.state = self.make(titles=self.titles)
        self.mains[self.shop] = "g1"
        self.known(self.shop, "g1")

    def session(self, sid, name, repo=None):
        """A live session SID of REPO whose own name (its title) is NAME."""
        path = "/t/%s.jsonl" % sid
        self.titles.map[path] = name
        self.feed(dict(line("UserPromptSubmit", sid, repo or self.shop), tp=path))

    def name(self, **kw):
        self.now += ac.ADD_WAIT_SEC + 1          # no open of an earlier call holds the repo
        code, body = self.add(self.shop, **kw)
        self.assertEqual(code, 200, body)
        return body["name"]

    def test_the_first_helper(self):
        self.assertEqual(self.name(), "shop Helper")

    def test_the_second_helper(self):
        self.session("h1", "shop Helper")
        client = self.client()
        self.assertEqual(self.name(), "shop Helper 2")
        folder, title, command = self.calls[-1]
        self.assertEqual(title, "shop Helper 2")
        self.assertEqual(shlex.split(command), ["claude", "--name", "shop Helper 2"] + FLAGS + [PROMPT])
        opening = [e for e in self.events(client) if e.get("state") == "opening"]
        self.assertEqual([e["name"] for e in opening], ["shop Helper 2"])

    def test_the_third_helper(self):
        self.session("h1", "shop Helper")
        self.session("h2", "shop Helper 2")
        self.assertEqual(self.name(), "shop Helper 3")

    def test_the_lowest_free_name(self):
        self.session("h2", "shop Helper 2")
        self.assertEqual(self.name(), "shop Helper")
        self.session("h1", "shop Helper")
        self.session("h4", "shop Helper 4")
        self.assertEqual(self.name(), "shop Helper 3")

    def test_an_ended_session_frees_its_name(self):
        self.session("h1", "shop Helper")
        self.feed(line("SessionEnd", "h1", self.shop))
        self.assertEqual(self.name(), "shop Helper")

    def test_a_session_this_city_opened_keeps_its_name_before_its_title_shows(self):
        self.assertEqual(self.name(), "shop Helper")
        self.feed(line("UserPromptSubmit", "n1", self.shop))          # the new session's first line: no title yet
        self.assertEqual(self.name(), "shop Helper 2")
        self.feed(line("UserPromptSubmit", "n2", self.shop))
        self.assertEqual(self.name(), "shop Helper 3")
        self.feed(line("SessionEnd", "n1", self.shop))
        self.assertEqual(self.name(), "shop Helper", "n1 ended: its name is free again")

    def test_another_repo_never_counts(self):
        other = self.repo("other")
        self.session("o1", "shop Helper", repo=other)
        self.assertEqual(self.name(), "shop Helper")

    def test_the_plain_command_has_the_free_name(self):
        self.session("h1", "shop Helper")
        self.kind = "plain"
        code, body = self.add(self.shop)
        self.assertEqual((code, body["state"], body["name"]), (200, "plain", "shop Helper 2"))
        self.assertIn("--name 'shop Helper 2'", body["command"])

    def test_the_main_manager_name_stays(self):
        del self.mains[self.shop]                 # no live main manager any more
        self.session("m1", "shop Manager")        # a session that carries the name
        self.now += ac.ADD_WAIT_SEC + 1
        code, body = self.add(self.shop)
        self.assertEqual((code, body["name"], body["role"]), (200, "shop Manager", "main"))


if __name__ == "__main__":
    unittest.main()
