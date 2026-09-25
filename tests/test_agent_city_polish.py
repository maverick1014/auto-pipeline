"""Failing tests from the main manager's real-session E2E of city-people (61c7daa), owner calls 2026-09-25.

CONTRACT

  D3 words (bin/agent-city.html). askName(view) -> who asks, as people read it: a governor's own
    ask (agent "gov") -> "<territory name> 总督" (the territory of view.terr); anyone else ->
    their task, else their label. The ask panel title and every log line of an ask (ask,
    ask_phase, ask_closed) use it. A governor's own question says "总督定不了，交给你" (never
    "没有总督在"), and its log line never says "问总督" (the governor asks the owner).
  D4 overlays: the red "?" (.qm) and the name tags (.tag) always draw above the 还差 sign
    (.era-sign): CSS z-index .qm > .tag > .era-sign. A tool event of kind "Other" makes no
    floating English tag (Edit/Write/Bash/Read still float).
  D5 (bin/agent_city.py): world.json keeps "gov_seen": {identity: sid} of the governor last seen
    per territory. After a restart the snapshot lists such a territory in "govs" with state
    "unknown" until a governor acts there (then its normal state) or that sid ends (then gone,
    and removed from gov_seen). Page: a governor entry with state "unknown" is not a present
    governor (governorAt null, no figure) and its roster row says 未知, not 不在.
  Result line then close: when the open ask panel shows its result (answered, allowed, denied,
    or someone else was first), the panel closes by itself ASK_CLOSE_MS = 10000 ms later:
    function askAutoClose(nowMs), called from frame(), closes it once nowMs - shownAt >=
    ASK_CLOSE_MS, where shownAt = performance.now() when the result was first shown.
    askName, askAutoClose and ASK_CLOSE_MS live in the simulation section (tests run it in node).

Run: python3 -m unittest tests.test_agent_city_polish </dev/null
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import REQUIRED, ac, function_source, page, run_sim  # noqa: E402
import test_agent_city_page as tp  # noqa: E402

A_REPO, B_REPO = "/work/repoA/.git", "/work/repoB/.git"
TA, TB = ac.territory_id(A_REPO), ac.territory_id(B_REPO)


def named_view():
    plans = ac.load_plans()
    w = ac.new_world()
    ac.add_territory(w, plans, A_REPO, "repoA", 3000)
    ac.add_territory(w, plans, B_REPO, "repoB", 3000)
    return ac.layout(w, plans)


ASK_Q = {"id": "q1", "agent": "gov", "terr": TA, "label": "", "task": "", "repo": A_REPO, "kind": "question",
         "phase": "owner", "why": "no-governor", "wait": 60, "left": 0, "tool": "AskUserQuestion",
         "what": "red or blue?", "at": 1000,
         "questions": [{"question": "red or blue?", "header": "c", "multiSelect": False,
                        "options": [{"label": "red", "description": ""}, {"label": "blue", "description": ""}]}]}

WORDS_DRIVER = r"""
const V = __payload.view, ask = __payload.ask;
function buildLand(view){ landState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: ask.terr }, govs: [{ terr: ask.terr, state: 'busy' }],
  governors: 1, asks: [], shows: [], agents: [] });
const name = askName(ask);
apply(Object.assign({ type: 'ask' }, ask));
const asked = logEntries[0].text;
apply({ type: 'ask_closed', id: ask.id, agent: 'gov', kind: 'question', tool: 'AskUserQuestion', what: ask.what,
  by: 'owner', verb: 'answer', text: 'red', reason: '', at: 2000 });
const answered = logEntries[0].text;
apply({ type: 'spawn', id: 'w1', role: 'worker', label: 'worker', task: 'slice w1', terr: ask.terr });
const other = askName({ agent: 'w1', label: 'worker', task: 'slice w1' });
const before = floaters.length;
apply({ type: 'tool', id: 'w1', tool: 'Other' });
const afterOther = floaters.length;
apply({ type: 'tool', id: 'w1', tool: 'Edit' });
__out = { name, asked, answered, other, otherFloats: afterOther - before, editFloats: floaters.length - afterOther };
"""


class TestWords(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(WORDS_DRIVER, {"view": named_view(), "ask": ASK_Q}, REQUIRED + ("askName", "logEntries", "floaters"))

    def test_the_governor_is_named_with_his_territory(self):
        self.assertEqual(self.r["name"], "repoA 总督")
        self.assertEqual(self.r["other"], "slice w1")

    def test_log_lines_name_the_asker(self):
        self.assertIn("repoA 总督", self.r["asked"])
        self.assertNotIn("问总督", self.r["asked"], "the governor asks the owner, not himself")
        self.assertIn("repoA 总督", self.r["answered"])
        self.assertIn("red", self.r["answered"])

    def test_panel_title_and_why_line(self):
        self.assertIn("askName(", function_source("renderAskPanel") or "")
        js = r"""
const fs = require('fs'), vm = require('vm');
const { fns } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, askName: v => 'repoA 总督' };
vm.createContext(box);
vm.runInContext(fns, box);
process.stdout.write(JSON.stringify({
  gov: box.askWhyLine({ kind: 'question', why: 'no-governor', agent: 'gov', terr: 't' }),
  other: box.askWhyLine({ kind: 'question', why: 'no-governor', agent: 'w1', terr: 't' }) }));
"""
        out = tp.run_node(js, {"fns": tp.page_fns("askWhyLine")})
        self.assertIn("总督定不了，交给你", out["gov"])
        self.assertNotIn("没有总督在", out["gov"])
        self.assertIn("没有总督在", out["other"], "a citizen's question with no governor keeps its line")

    def test_no_english_other_floater(self):
        self.assertEqual(self.r["otherFloats"], 0)
        self.assertEqual(self.r["editFloats"], 1)


def z_index(selector):
    m = re.search(r"(?m)^%s\{[^}]*?z-index:\s*(\d+)" % re.escape(selector), tp.style())
    return int(m.group(1)) if m else 0


class TestOverlaysOnTop(unittest.TestCase):

    def test_question_mark_and_tags_above_the_sign(self):
        qm, tag, sign = z_index(".qm"), z_index(".tag"), z_index(".era-sign")
        self.assertGreater(qm, tag, ".qm above .tag")
        self.assertGreater(tag, sign, ".tag above .era-sign")
        self.assertGreater(qm, 0)


class TestUnknownGovernorAfterRestart(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_polish_")
        self.world = os.path.join(self.base, "world.json")
        self.now = 1000.0

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def state(self):
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world,
                            plans=ac.load_plans(), count_fn=lambda i: 0,
                            balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}})

    def line(self, st, ev, sid, repo=A_REPO):
        self.now += 1
        st.feed_line({"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "Read", "nt": "", "proj": "p", "role": "",
                      "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": "", "ask": ""}, self.now)

    def govs(self, st):
        return json.loads(st.add_client().queue.get_nowait().decode("utf-8").split("data:", 1)[1])["govs"]

    def test_a_known_governor_is_unknown_after_a_restart(self):
        st = self.state()
        self.line(st, "UserPromptSubmit", "g1")
        again = self.state()
        self.assertEqual(self.govs(again), [{"terr": TA, "state": "unknown"}])
        self.line(again, "PostToolUse", "g1")
        self.assertEqual([(g["terr"], g["state"]) for g in self.govs(again)], [(TA, "busy")])

    def test_a_governor_that_ended_is_forgotten(self):
        st = self.state()
        self.line(st, "UserPromptSubmit", "g1")
        self.line(st, "SessionEnd", "g1")
        with open(self.world, encoding="utf-8") as fh:
            self.assertNotIn(A_REPO, json.load(fh).get("gov_seen", {}))
        self.assertEqual(self.govs(self.state()), [])

    def test_page_says_unknown_and_draws_no_figure(self):
        driver = r"""
const V = __payload.view;
function buildLand(view){ landState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: __payload.ta }, governors: 0, asks: [], shows: [], agents: [],
  govs: [{ terr: __payload.ta, state: 'unknown' }] });
__out = { row: govRowText(__payload.ta), at: governorAt(__payload.ta) };
"""
        r = run_sim(driver, {"view": named_view(), "ta": TA}, REQUIRED + ("govRowText",))
        self.assertEqual(r["row"], "未知")
        self.assertIsNone(r["at"])


class TestResultThenClose(unittest.TestCase):

    def test_the_panel_closes_10s_after_its_result(self):
        driver = r"""
const V = __payload.view, ask = __payload.ask;
function buildLand(view){ landState(view); }
let closes = 0;
function closeAskPanel(){ closes++; openAskId = null; }
function renderAskPanel(){}
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: ask.terr }, govs: [{ terr: ask.terr, state: 'busy' }],
  governors: 1, asks: [ask], shows: [], agents: [] });
openAskId = ask.id;
askAutoClose(50000);
const openBefore = closes;
apply({ type: 'ask_closed', id: ask.id, agent: 'gov', kind: 'question', tool: 'AskUserQuestion', what: ask.what,
  by: 'owner', verb: 'answer', text: 'red', reason: '', at: 2000 });
askAutoClose(9999);
const at9 = closes;
askAutoClose(10000);
__out = { openBefore, at9, at10: closes, ms: ASK_CLOSE_MS };
"""
        r = run_sim(driver, {"view": named_view(), "ask": ASK_Q}, REQUIRED + ("askAutoClose", "ASK_CLOSE_MS"))
        self.assertEqual(r["ms"], 10000)
        self.assertEqual(r["openBefore"], 0, "an open, unanswered ask never closes by itself")
        self.assertEqual(r["at9"], 0, "the result line stays 10 s")
        self.assertEqual(r["at10"], 1, "then the panel closes by itself")

    def test_every_result_path_sets_the_time_and_frame_checks_it(self):
        self.assertIn("askAutoClose(", function_source("frame") or "")
        text = page()
        self.assertGreaterEqual(len(re.findall(r"shownAt\s*[:=]", text)), 2,
                                "ask_closed and the page's own decide() both stamp shownAt")


if __name__ == "__main__":
    unittest.main()
