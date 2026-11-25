"""Failing tests for the city's chain of command, offices and rest place
(requirements/city.md, Interaction and Growth). Approved mock:
mock/city-people-mock.html (owner, 2026-09-25). P0 (people walk) and its
sim harness: tests/test_agent_city_people.py.

CONTRACT, hook (bin/agent-city-hook.sh): one more key, last: "ask".
  ask  "q" when a worker or a lead passes a question up the chain, else "":
         SubagentStop whose last_assistant_message starts with "QUESTION:"
         PostToolUse of SendMessage whose tool_input.message starts with
         "QUESTION:"
       Only the flag: never the text, never the recipient. Bash builtins
       only, first 4096 bytes only (the prefix is always there).

CONTRACT, server (bin/agent_city.py). Every line may carry "ask".
  Governor per territory: the first session without AGENT_ROLE seen in a
    repo is that repo's governor; a later one in the same repo is a citizen
    (role task-manager, label "session", as before). Snapshot "govs" lists
    every governor present; "gov" events carry "terr", "state", "present".
    Ask views carry "terr" (the territory id of the ask's repo).
  Leads: a session citizen with role task-manager is a lead. It gets an
    office: one of its plan's "offices" spots (local [x, z], at least 4 per
    plan, off roads, plots, the hall and the plaza box -2..1, at least 2
    tiles apart) in plan order, the first one no live lead holds. The
    office tile is land ("g") while held. Spawn events and snapshot agents
    carry "office": {"x", "z"} (world tile) or null, and "lead": the lead's
    citizen id ("s:<sid>") for a subagent inside a lead's session, "" else.
    The view's territory lists "offices": [{"lead", "x", "z"}]. A lead that
    leaves frees its office.
  Chain (relay events, never any text):
    {"type": "relay", "id", "to": "lead"|"governor", "lead": id or ""}
    {"type": "relay_end", "id", "by": "governor"|"lead"|"timeout"|"leave"}
    worker asks lead      SubagentStop ask=q of a subagent in a lead's
                          session -> relay to "lead" (then its done event)
    helper asks governor  SubagentStop ask=q of a subagent in a governor's
                          session -> relay to "governor"
    lead asks governor    PostToolUse SendMessage ask=q in a lead's session
                          -> relay to "governor"
    governor answers      PostToolUse SendMessage in a governor's session
                          -> relay_end (by governor) of the oldest open lead
                          relay in that territory, then of that lead's
                          waiting workers; also of its own helpers' relays
    lead decides          PreToolUse Agent/Task, or PostToolUse SendMessage
                          without ask=q, in a lead's session with no relay
                          of its own open -> relay_end (by lead) of its
                          waiting workers
    session end           relay_end (by leave) of that session's relays
    10 min (600 s)        relay_end (by timeout), checked on every line
    Snapshot agents carry "relay": "lead"|"governor"|"".
  Rest place: the first done citizen in a territory opens it, for good:
    world.json territory "rest": true; the view's territory "rest":
    {"x", "z"} (world tile of the 2x2 area's corner, from the plan's
    "rest" [x, z]) or null. Its 4 tiles are land ("g"). A world.json
    without the key loads as no rest place.

CONTRACT, page (bin/agent-city.html):
  governorAt(terr) for every territory with a present governor, each at
    its own hall. governorFigures() -> [{terr, x, y}] one per present
    governor; updateGovernor() draws a figure (with its bubble, "?" and tag)
    for each of them, not only the home territory's. Roster and detail group people by territory:
    rosterGroups() -> [{"terr", "name", "rows": [{"id", "depth"}]}] in map
    order; per group the governor first (id "gov:<terr>"), then each lead
    followed by its workers (depth 1), then everyone else (depth 0).
    The governor's window (renderDetail) lists its people through it
    (city-focus: the 市民 roster card is gone).
  A lead's home is its office (t.offices). Its workers live and walk
    around it (within 2.6 tiles of the office centre).
  A citizen with relay "lead" (or a worker that is stuck: question or
    permission) walks to its lead's office; a lead with relay "governor"
    (or stuck) walks to its governor; everyone else stuck walks to its
    governor, as today. relay_end sends it home; a done one then rests.
    citizenStatus: relay "lead" -> 问经理, relay "governor" -> 在问总督.
  Rest: with t.rest, restSlotsFor(t) gives seats inside the rest place
    (within 1.8 of its centre, x + 1, z + 1); without one, as today.
  restDecor(t) -> [{key, x, z}] the rest place's models for the era shown:
    village kaykit-medieval/building_tavern_red + 2 or more
    kaykit-city/bench; town a cafe building, 2 or more
    kaykit-restaurant/table_round_A, 4 or more kaykit-restaurant/chair_A,
    and 2 or more Kenney parasols (commercial/detail-parasol-a or -b,
     restored from git; never hand-drawn shapes, owner 2026-09-25); city
    fantasy/fountain-round and 3 or more kaykit-city/bench. [] without
    t.rest.
  officeDecor(t) -> per office kaykit-medieval/building_home_A_blue on the
    office tile and a forest/flag beside it.
  systemsDecor, village era: police = kaykit-medieval/building_barracks_blue,
    library = kaykit-medieval/building_church_green, power (infra healthy)
    = kaykit-medieval/building_windmill_yellow. Town and city: police =
    industrial/building-h with kaykit-city/car_police on a tile next to it.
  MODELS lists the 8 KayKit models; each KayKit pack folder has License.txt
    (CC0). Assets at most 8 MB.
  agents/worker.md: a third report form, first line "QUESTION: <one line>".

Run: python3 -m unittest tests.test_agent_city_chain </dev/null
"""

import json
import math
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import (ROOT, REQUIRED, ac, function_source, run_sim)  # noqa: E402
from cityhelp import Mains  # noqa: E402

A_REPO, B_REPO = "/work/fa/app/.git", "/work/fb/app/.git"
TA, TB = ac.territory_id(A_REPO), ac.territory_id(B_REPO)


def decode(raw):
    return json.loads(raw.decode("utf-8").split("data:", 1)[1])


class CityCase(unittest.TestCase):
    lines_count = 6000

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_people_f_")
        self.world_path = os.path.join(self.base, "world.json")
        self.mains = Mains()   # city-roles: territory -> its main manager (the governor)
        self.st = self.new_state()
        self.client = self.st.add_client()
        self.client.queue.get_nowait()
        self.now = 1000.0

    def new_state(self):
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world_path,
                            main_fn=self.mains)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def line(self, ev, sid, repo=A_REPO, role="", aid="", at="", tool="", ask="", sub="", desc="", nt="", dt=1.0):
        self.now += dt
        self.st.feed_line({"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": nt, "proj": "app",
                           "role": role, "desc": desc, "sub": sub, "q": "", "klen": "", "repo": repo,
                           "kind": "", "ask": ask}, self.now)

    def drain(self):
        out = []
        while not self.client.queue.empty():
            raw = self.client.queue.get_nowait()
            if isinstance(raw, bytes):
                out.append(decode(raw))
        return out

    def snap(self):
        return decode(self.st.add_client().queue.get_nowait())

    def terr_view(self, snap, terr):
        return next(t for t in snap["world"]["territories"] if t["id"] == terr)

    def agent(self, snap, cid):
        return next(a for a in snap["agents"] if a["id"] == cid)

    # common casts
    def governor(self, sid="g1", repo=A_REPO):
        # city-roles: the first governor() of a territory holds its main manager lock
        self.mains.setdefault(repo if repo else self.st.start_repo, sid)
        self.line("UserPromptSubmit", sid, repo)

    def lead(self, sid="tm1", repo=A_REPO):
        self.line("PostToolUse", sid, repo, role="task-manager", tool="Bash")

    def worker(self, aid="w1", sid="tm1", repo=A_REPO, role="task-manager"):
        self.line("PreToolUse", sid, repo, role=role, tool="Agent", sub="worker", desc="slice")
        self.line("SubagentStart", sid, repo, role=role, aid=aid, at="worker")


def tile(view, x, z):
    r, c = z - view["z0"], x - view["x0"]
    if 0 <= r < view["h"] and 0 <= c < view["w"]:
        return view["rows"][r][c]
    return " "


class TestHookAskFlag(unittest.TestCase):
    """The hook writes ask=q for a question passed up the chain, never its text."""

    def setUp(self):
        import test_agent_city_hook as th
        self.th = th
        self.case = th.HookCase("run_hook")
        self.case.setUp()
        self.case.switch_on()

    def tearDown(self):
        self.case.tearDown()

    def row(self, stdin):
        result = self.case.run_hook(stdin)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.case.lines()
        self.assertTrue(rows, "no line written")
        raw = open(self.case.events, "rb").read()
        return rows[-1], raw

    def stop(self, text):
        return self.th.payload("SubagentStop", agent=("w-1", "worker"), stop_hook_active=False,
                               agent_transcript_path="/home/u/t.jsonl", last_assistant_message=text,
                               background_tasks=[])

    def send(self, message, event="PostToolUse"):
        return self.th.payload(event, tool_name="SendMessage",
                               tool_input={"to": "auto-pipeline-88", "summary": "ask", "message": message},
                               tool_response={"success": True, "message": "queued"})

    def test_ask_key_is_last_and_a_string(self):
        # city-worktrees added "wt" after it, city-quality "file" after that,
        # session-names "tp" after that, city-roles "pid" last (tests/test_agent_city_worktrees.py,
        # tests/test_agent_city_quality.py, tests/test_agent_city_session_names.py,
        # tests/test_agent_city_roles.py)
        row, _ = self.row(self.stop("PASS\nall green"))
        self.assertEqual(list(row)[-5:], ["ask", "wt", "file", "tp", "pid"])
        self.assertEqual(row["ask"], "")

    def test_worker_question_sets_the_flag_not_the_text(self):
        row, raw = self.row(self.stop("QUESTION: which port, 4791 or 4777?\nWhat changed: nothing"))
        self.assertEqual(row["ask"], "q")
        self.assertNotIn(b"4791", raw)
        self.assertNotIn(b"which port", raw)

    def test_only_a_first_line_question_counts(self):
        for text in ("FAIL: tests\nQUESTION: x", "question: lower case", "PASS"):
            with self.subTest(text=text):
                row, _ = self.row(self.stop(text))
                self.assertEqual(row["ask"], "")

    def test_lead_question_to_the_governor(self):
        row, raw = self.row(self.send("QUESTION: port 4791 or 4777?\nDefault 4791 after 10 min."))
        self.assertEqual(row["ask"], "q")
        self.assertEqual(row["tool"], "SendMessage")
        self.assertNotIn(b"4791", raw)
        self.assertNotIn(b"auto-pipeline-88", raw)

    def test_other_messages_are_no_question(self):
        for msg in ("DONE PASS city-people", "HEARTBEAT city-people: step 4", "MOCK READY"):
            with self.subTest(msg=msg):
                row, _ = self.row(self.send(msg))
                self.assertEqual(row["ask"], "")

    def test_only_post_tool_use_counts(self):
        row, _ = self.row(self.send("QUESTION: x", event="PreToolUse"))
        self.assertEqual(row["ask"], "")

    def test_a_session_stop_is_never_a_chain_question(self):
        row, _ = self.row(self.th.payload("Stop", stop_hook_active=False, last_assistant_message="QUESTION: x"))
        self.assertEqual(row["ask"], "")

    def test_long_message_still_flagged(self):
        row, _ = self.row(self.send("QUESTION: " + "x" * 20000))
        self.assertEqual(row["ask"], "q")


class TestGovernorPerTerritory(CityCase):

    def test_two_repos_two_governors(self):
        self.governor("g1", A_REPO)
        self.governor("g2", B_REPO)
        self.assertEqual(sorted(g["terr"] for g in self.snap()["govs"]), sorted([TA, TB]))
        present = [e for e in self.drain() if e.get("type") == "gov" and e.get("present") is True]
        self.assertEqual({e["terr"] for e in present}, {TA, TB})

    def test_a_second_roleless_session_in_the_same_repo_is_a_citizen(self):
        self.governor("g1")
        self.governor("g3")
        spawns = [e for e in self.drain() if e.get("type") == "spawn"]
        self.assertEqual([e["id"] for e in spawns], ["s:g3"])
        self.assertEqual([g["terr"] for g in self.snap()["govs"]], [TA])

    def test_a_governor_leaving_touches_only_its_territory(self):
        self.governor("g1", A_REPO)
        self.governor("g2", B_REPO)
        self.drain()
        self.line("SessionEnd", "g1", A_REPO)
        gone = [e for e in self.drain() if e.get("type") == "gov" and e.get("present") is False]
        self.assertEqual([e["terr"] for e in gone], [TA])
        self.assertEqual([g["terr"] for g in self.snap()["govs"]], [TB])

    def test_an_idle_governor_leaving_is_broadcast_too(self):
        self.governor("g1", A_REPO)
        self.line("Stop", "g1", A_REPO)
        self.drain()
        self.line("SessionEnd", "g1", A_REPO)
        gone = [e for e in self.drain() if e.get("type") == "gov" and e.get("present") is False]
        self.assertEqual([e["terr"] for e in gone], [TA])

    def test_state_is_per_territory(self):
        self.governor("g1", A_REPO)
        self.governor("g2", B_REPO)
        self.line("Stop", "g2", B_REPO)
        govs = {g["terr"]: g["state"] for g in self.snap()["govs"]}
        self.assertEqual(govs[TA], "busy")
        self.assertEqual(govs[TB], "idle")

    def test_ask_view_names_its_territory(self):
        body, code = self.st.create_ask({"sid": "x1", "aid": "", "at": "", "role": "task-manager", "cwd": "/w",
                                         "repo": B_REPO, "tool": "Bash", "input": {"command": "ls"}}, 1000.0)
        self.assertEqual(code, 200)
        self.assertEqual(self.st.asks_view()[0]["terr"], TB)


class TestServerE2EFindings(CityCase):
    """Task manager's headless run (real server, synthetic hook lines)."""

    def test_a_governors_own_ask_is_the_governors(self):
        # no gov-watch has polled yet (first turn): the session is still the governor of its territory
        self.governor("g1")
        body, code = self.st.create_ask({"sid": "g1", "aid": "", "at": "", "role": "", "cwd": "/w", "repo": A_REPO,
                                         "tool": "AskUserQuestion",
                                         "input": {"questions": [{"question": "port?", "header": "p", "options": [],
                                                                  "multiSelect": False}]}}, 1000.0)
        self.assertEqual(code, 200)
        view = self.st.asks_view()[0]
        self.assertEqual(view["agent"], "gov")
        self.assertEqual(view["terr"], TA)
        self.assertEqual(view["phase"], "owner", "the governor asks the owner: red ? at once")


class TestNoRepoIsTheStartTerritory(CityCase):
    """A session on an older hook sends lines without "repo" (the owner's main manager on plugin 0.4.4):
    they belong to the start territory, the same one as lines with the start repo, never a second state."""

    def new_state(self):
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world_path,
                            start_repo=A_REPO,
                            main_fn=self.mains)

    def test_one_governor_for_the_start_territory(self):
        self.governor("g-old", repo="")
        self.governor("g-new", repo=A_REPO)
        self.assertEqual([g["terr"] for g in self.snap()["govs"]], [TA])
        spawns = [e["id"] for e in self.drain() if e.get("type") == "spawn"]
        self.assertEqual(spawns, ["s:g-new"], "the second roleless session there is a citizen")

    def test_a_governor_without_repo_answers_a_lead_with_repo(self):
        self.governor("g-old", repo="")
        self.lead("tm1", repo=A_REPO)
        self.line("PostToolUse", "tm1", A_REPO, role="task-manager", tool="SendMessage", ask="q")
        self.drain()
        self.line("PostToolUse", "g-old", "", tool="SendMessage")
        ends = [(e["type"], e["id"]) for e in self.drain() if e.get("type") == "relay_end"]
        self.assertIn(("relay_end", "s:tm1"), ends)

    def test_snapshot_home_is_the_start_territory(self):
        # headless E2E: the page loads its models for a few seconds, so its first snapshot often comes after
        # other governors' gov events; the snapshot's gov.terr (the page's camera home) is the start territory
        self.governor("g1", A_REPO)
        self.governor("g2", B_REPO)
        self.line("PostToolUse", "g2", B_REPO, tool="Read")
        self.assertEqual(self.snap()["gov"]["terr"], TA)

class TestChain(CityCase):

    def setUp(self):
        super().setUp()
        self.governor("g1")
        self.lead("tm1")
        self.worker("w1", "tm1")
        self.drain()

    def relays(self, events):
        return [(e["type"], e["id"], e.get("to", e.get("by"))) for e in events if e.get("type") in ("relay", "relay_end")]

    def test_worker_question_walks_to_its_lead(self):
        self.line("SubagentStop", "tm1", role="task-manager", aid="w1", at="worker", ask="q")
        ev = self.drain()
        self.assertIn(("relay", "w1", "lead"), self.relays(ev))
        r = [e for e in ev if e.get("type") == "relay"][0]
        self.assertEqual(r["lead"], "s:tm1")
        order = [e["type"] for e in ev if e.get("id") == "w1" and e.get("type") in ("relay", "done")]
        self.assertEqual(order, ["relay", "done"], "relay first, so the page never cheers 完工啦 for a question (headless E2E)")
        self.assertEqual(self.agent(self.snap(), "w1")["relay"], "lead")

    def test_a_plain_stop_is_only_done(self):
        self.line("SubagentStop", "tm1", role="task-manager", aid="w1", at="worker")
        ev = self.drain()
        self.assertEqual(self.relays(ev), [])
        self.assertIn("done", [e["type"] for e in ev if e.get("id") == "w1"])

    def test_lead_passes_it_to_the_governor_and_the_answer_comes_back(self):
        self.line("SubagentStop", "tm1", role="task-manager", aid="w1", at="worker", ask="q")
        self.line("PostToolUse", "tm1", role="task-manager", tool="SendMessage", ask="q")
        self.assertIn(("relay", "s:tm1", "governor"), self.relays(self.drain()))
        snap = self.snap()
        self.assertEqual(self.agent(snap, "s:tm1")["relay"], "governor")
        self.assertEqual(self.agent(snap, "w1")["relay"], "lead")
        self.line("PostToolUse", "g1", tool="SendMessage")
        ends = self.relays(self.drain())
        self.assertIn(("relay_end", "s:tm1", "governor"), ends)
        self.assertIn(("relay_end", "w1", "governor"), ends)
        snap = self.snap()
        self.assertEqual(self.agent(snap, "s:tm1")["relay"], "")

    def test_lead_decides_itself(self):
        self.line("SubagentStop", "tm1", role="task-manager", aid="w1", at="worker", ask="q")
        self.drain()
        self.line("PreToolUse", "tm1", role="task-manager", tool="Agent", sub="worker", desc="again")
        self.assertIn(("relay_end", "w1", "lead"), self.relays(self.drain()))

    def test_oldest_lead_first(self):
        self.lead("tm2")
        self.line("PostToolUse", "tm1", role="task-manager", tool="SendMessage", ask="q")
        self.line("PostToolUse", "tm2", role="task-manager", tool="SendMessage", ask="q")
        self.drain()
        self.line("PostToolUse", "g1", tool="SendMessage")
        self.assertEqual([r for r in self.relays(self.drain()) if r[0] == "relay_end"],
                         [("relay_end", "s:tm1", "governor")])
        self.line("PostToolUse", "g1", tool="SendMessage")
        self.assertEqual([r for r in self.relays(self.drain()) if r[0] == "relay_end"],
                         [("relay_end", "s:tm2", "governor")])

    def test_another_territorys_governor_does_not_answer(self):
        self.governor("g2", B_REPO)
        self.line("PostToolUse", "tm1", role="task-manager", tool="SendMessage", ask="q")
        self.drain()
        self.line("PostToolUse", "g2", B_REPO, tool="SendMessage")
        self.assertEqual(self.relays(self.drain()), [])

    def test_a_lead_leaving_ends_its_chain(self):
        self.line("SubagentStop", "tm1", role="task-manager", aid="w1", at="worker", ask="q")
        self.line("PostToolUse", "tm1", role="task-manager", tool="SendMessage", ask="q")
        self.drain()
        self.line("SessionEnd", "tm1", role="task-manager")
        ends = self.relays(self.drain())
        self.assertIn(("relay_end", "s:tm1", "leave"), ends)
        self.assertIn(("relay_end", "w1", "leave"), ends)

    def test_ten_minutes_end_a_relay(self):
        self.line("PostToolUse", "tm1", role="task-manager", tool="SendMessage", ask="q")
        self.drain()
        self.line("PostToolUse", "g1", tool="Read", dt=601.0)
        self.assertIn(("relay_end", "s:tm1", "timeout"), self.relays(self.drain()))

    def test_a_governors_helper_asks_the_governor(self):
        self.worker("d1", "g1", role="")
        self.drain()
        self.line("SubagentStop", "g1", aid="d1", at="worker", ask="q")
        self.assertIn(("relay", "d1", "governor"), self.relays(self.drain()))
        self.line("PostToolUse", "g1", tool="SendMessage")
        self.assertIn(("relay_end", "d1", "governor"), self.relays(self.drain()))


class TestWorkerQuestionForm(unittest.TestCase):

    def test_worker_md_has_the_question_form(self):
        with open(os.path.join(ROOT, "agents", "worker.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("QUESTION:", text)
        self.assertIn("PASS", text)


# ---------------------------------------------------------------------------
# Page: governors per territory, offices, the chain walk, the rest place
# ---------------------------------------------------------------------------

def two_territory_view():
    """city-office: A and B as two floors (A 1F, B 2F) of the office view."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cityoffice import office_view_of
    return office_view_of((A_REPO, "app"), (B_REPO, "app"))

FEATURE_DRIVER = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
const OF = A.offices[0], OC = { x: OF.x + .5, y: OF.z + .5 }, RC = { x: A.rest.x + 1, y: A.rest.z + 1 };
function buildLand(view){ officeState(view); }
function tick(sec){ for (let i = 0; i < Math.round(sec * 10); i++) update(.1); }
const pos = id => { const c = byId(id); return c ? { x: c.x, y: c.y, state: c.state } : null; };
const who = () => citizens.filter(c => !c.gone && c.state !== 'leaving' && !(c.path && c.path.length)).map(c => ({ id: c.id, x: c.x, y: c.y })); // standing people (strollers may pass)
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 2, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'busy' }, { terr: B.id, state: 'idle' }], agents: [
  { id: 's:L', role: 'task-manager', label: 'task-manager', task: 'city-people', stuck: false, done: false, tools: { Bash: 2 }, terr: A.id, lead: '', office: { x: OF.x, z: OF.z }, relay: '' },
  { id: 'w1', role: 'worker', label: 'worker', task: 'reducer', stuck: false, done: false, tools: { Edit: 1 }, terr: A.id, lead: 's:L', office: null, relay: '' },
  { id: 'w2', role: 'worker', label: 'worker', task: 'page', stuck: false, done: false, tools: { Edit: 1 }, terr: A.id, lead: 's:L', office: null, relay: '' },
  { id: 'r1', role: 'fast-lane-deputy', label: 'fast-lane-deputy', task: 'typo', stuck: false, done: true, tools: { Edit: 1 }, terr: A.id, lead: '', office: null, relay: '' },
  { id: 'r2', role: 'worker', label: 'worker', task: 'b', stuck: false, done: true, tools: { Edit: 1 }, terr: B.id, lead: '', office: null, relay: '' } ] });
const gA = governorAt(A.id), gB = governorAt(B.id);
tick(25);
const settle = { L: pos('s:L'), w1: pos('w1'), w2: pos('w2'), r1: pos('r1'), r2: pos('r2'), all: who() };
const groups = rosterGroups().map(g => ({ terr: g.terr, rows: g.rows.map(r => [r.id, r.depth]) }));
apply({ type: 'relay', id: 'w1', to: 'lead', lead: 's:L' });
apply({ type: 'done', id: 'w1' });
tick(20);
const c1 = { w1: pos('w1'), L: pos('s:L'), status: citizenStatus(byId('w1'), 2), bubble: (byId('w1').bubble && byId('w1').bubble.text) || '' };
apply({ type: 'relay', id: 's:L', to: 'governor', lead: '' });
tick(35);
const c2 = { L: pos('s:L'), w1: pos('w1'), status: citizenStatus(byId('s:L'), 2), noWatch: citizenStatus(byId('s:L'), 0) };
apply({ type: 'relay_end', id: 's:L', by: 'governor' });
apply({ type: 'relay_end', id: 'w1', by: 'governor' });
tick(45);
const c3 = { L: pos('s:L'), w1: pos('w1'), all: who() };
apply({ type: 'stuck', id: 'w2', question: '', tool: 'Bash' });
tick(20);
const p1 = pos('w2');
apply({ type: 'stuck', id: 's:L', question: '', tool: 'Bash' });
tick(35);
const p2 = pos('s:L');
__out = { gA, gB, settle, groups, c1, c2, c3, p1, p2, OC, RC, hallA: { x: A.cx, y: A.cz }, hallB: { x: B.cx, y: B.cz },
  restA: restSlotsFor(A).map(s => ({ x: s.x, y: s.y })), restB: restSlotsFor(B).map(s => ({ x: s.x, y: s.y })) };
"""

FEATURE_REQUIRED = REQUIRED + ("rosterGroups", "restSlotsFor")


def dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


GOVFIG_DRIVER = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
function buildLand(view){ officeState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 1, asks: [], shows: [], agents: [],
  govs: [{ terr: A.id, state: 'busy' }, { terr: B.id, state: 'idle' }] });
const two = governorFigures().map(g => ({ terr: g.terr, x: g.x, y: g.y }));
apply({ type: 'gov', terr: B.id, state: 'idle', present: false });
const one = governorFigures().map(g => g.terr);
__out = { two, one, hallA: { x: A.cx + MGR_SEAT.x, y: A.cz + MGR_SEAT.z }, hallB: { x: B.cx + MGR_SEAT.x, y: B.cz + MGR_SEAT.z } };
"""


class TestGovernorFigures(unittest.TestCase):
    """One governor figure per present governor, each at its own hall (B1 drew only one)."""

    def test_one_figure_per_present_governor(self):
        r = run_sim(GOVFIG_DRIVER, {"view": two_territory_view(), "ta": TA, "tb": TB},
                    FEATURE_REQUIRED + ("governorFigures",))
        self.assertEqual(sorted(g["terr"] for g in r["two"]), sorted([TA, TB]))
        by = {g["terr"]: g for g in r["two"]}
        self.assertLessEqual(dist(by[TA], r["hallA"]), 2.5)
        self.assertLessEqual(dist(by[TB], r["hallB"]), 2.5)
        self.assertEqual(r["one"], [TA])

    def test_the_3d_draws_every_figure(self):
        self.assertIn("governorFigures(", function_source("updateGovernor") or "")


HOME_DRIVER = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
function buildLand(view){ officeState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 1, asks: [], shows: [], agents: [],
  govs: [{ terr: A.id, state: 'busy' }] });
const h0 = { x: home.x, z: home.z };
apply({ type: 'gov', terr: B.id, state: 'busy', present: true });
apply({ type: 'gov', terr: B.id, state: 'idle', present: true });
const h1 = { x: home.x, z: home.z };
apply({ type: 'world', world: V });
const h2 = { x: home.x, z: home.z };
__out = { h0, h1, h2 };
"""


def decor_run(cases):
    import test_agent_city_page as tp
    js = r"""
const fs = require('fs'), vm = require('vm');
const { prelude, fns, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const box = { Math, JSON, console, occupied: new Map(), blocked: new Set(), shows: new Map(), performance: { now: () => 0 } };
vm.createContext(box);
vm.runInContext(prelude + '\n' + fns, box);
const out = {};
for (const [name, t] of Object.entries(cases)) out[name] = { rest: box.restDecor(t), office: box.officeDecor(t) };
require(`fs`).writeSync(1, JSON.stringify(out));
"""
    fns = tp.page_fns("restDecor", "officeDecor",
                      optional=("eraShown", "showOf", "eraLook", "sr", "terrOf", "tileAt", "walkable", "frontOf"))
    prelude = tp.constants_prelude() + "\n" + tp.consts("ERA_LOOK")
    return tp.run_node(js, {"prelude": prelude, "fns": fns, "cases": cases})


KAYKIT = ("kaykit-medieval/building_tavern_red", "kaykit-medieval/building_barracks_blue",
          "kaykit-medieval/building_church_green", "kaykit-medieval/building_windmill_yellow",
          "kaykit-medieval/building_home_A_blue", "kaykit-city/car_police", "kaykit-city/bench",
          "kaykit-restaurant/table_round_A", "kaykit-restaurant/chair_A")

