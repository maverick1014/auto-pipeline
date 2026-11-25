"""Failing tests for city-rail-tree (owner, 2026-10-05; approved mock mock/city-rail-tree-mock.html 2b63d74,
"mock yes" 16:52 with the recommended picks: width B 300px, long names wrap to two lines, the server adds `up`).
Owner: "the online tab all is same aligned, no indent for its child. they should have indent according to the
repo and relationship, so that we can know who belongs to which one." and "the online tab can be wider".
requirements/city.md: Look ("The rail is a tree" .. "Phone: the rail stays a drawer") and Data path ("Who sent whom").

CONTRACT

S  Server (bin/agent_city.py)
  S1 Every spawn event carries "up" (a string), the page id of the person's parent:
       a subagent -> the session that started it, the same page id "from" gives ("gov:<terr>" for the governor,
         "s:<sid>" for a live session citizen, else "");
       a session whose hook role is "task-manager" -> "gov:<its own terr>", ALSO while that repo has no governor
         (unlike "from", which is "" then);
       any other session (a Helper, a plain session) -> "".
     "from" stays exactly as it was (tests/test_agent_city_talk.py).
  S2 Every agent record of the snapshot carries "up": the value its spawn had, kept as long as the person lives.
  S3 A session brought back from the roster after a server restart carries "up" by the same rule (a task
     manager -> "gov:<terr>", a role-less session -> "").

P  Page (bin/agent-city.html). "sim section" as in tests/test_agent_city_people.py (run_sim).
  P1 (sim) Every citizen has up: newCitizen() sets up: ''. placeAgent(a) (snapshot) keeps
     a.up when it is a string, else ''. apply 'spawn' keeps ev.up (else ''). spawnDemo's spawn carries up, the same
     value as its from.
  P2 (sim) railGroups() -> [{terr, name, color, add, rows}] as before (map order, a group per territory, also an
     empty one). rows is the tree, flat in pre-order (a parent, then its whole subtree, then its next sibling),
     then the resting rows. Each row {id, depth, rest, up, kids, lost}:
       members = the governor row 'gov:<terr>' (only while governorFigures() has that territory, as before),
         then this machine's citizens of the territory (not gone) in citizens order.
       parent of a citizen c: p = c.up || c.lead. p === 'gov:<terr>' and the governor row is there -> the
         governor; p is the id of another member of this group -> that member; else none (the repo).
         A loop (a -> b -> a) or a person that names itself never hangs: each person shows exactly once.
       rest: citizenStatus(c)[0] === 'rest' (as before). Resting rows leave the tree: they come last, in
         members order, rest: true, depth 0, up '', kids 0, lost false (the 休息 N fold is flat). An active
         row whose parent rests hangs on the nearest active ancestor (or the repo).
       Active rows: rest false; depth = how many active ancestors (0 = right under the repo); up = the
         parent's row id ('' = the repo); kids = how many active rows are under it, all levels; siblings keep
         members order (the governor first at the top).
       lost: true only for a worker (role 'worker') that has no parent member in this group (a resting parent
         still counts: it is in the 休息 fold, so the worker is not lost); else false.
     railCount() is unchanged (active rows, the ones waiting on the owner, hidden repos' waits).
  P3 (sim) railHtml(groups, selId, closed, openRest, adds, shut): shut (6th, optional: missing = nothing shut)
     = a Set of row ids folded by the owner. Everything else as before (section, head with every row counted,
     the + and its words, 没人在线, rest-t, closed group = head only). The active rows are a tree:
       <ul class="rrows tree"> with one <li> per top row (depth 0); every <li> is
       <li><div class="rl">ARROW ROW</div>[<ul class="kids"> its children's <li>s </ul>]</li>
       ARROW = for a row with kids: <button type="button" class="tw" data-tw="<id>" aria-expanded="<not shut>"
         aria-label="<i18n rail.fold while open, rail.unfold while shut>">; for a leaf: <span class="tw leaf"></span>.
       ROW = the row button as before: <button type="button" class="rrow[ sub][ resting]" data-focus="<id>"
         aria-current=...> dot, <b>name</b>, then for a SHUT row <span class="more">+<kids></span> and, when
         somebody under it waits on the owner (rowWaitsOnYou), <span class="you"><that many></span>; then for
         a lost row <span class="who"><i18n rail.lost></span>; then the chip. ' sub' = depth > 0 (a marker
         only: the indent comes from the nesting).
       A shut row's <ul class="kids"> is not drawn at all (all levels under it hidden).
     The resting rows (openRest has terr): <ul class="rrows"> flat, one <li> each, the row button only (no
     arrow, no kids list).
  P4 3D part: let railShut = a Set read from localStorage 'agent-city.railShut' (comma list, in try);
     saveRailShut() writes it (in try). renderRail passes railShut to railHtml. The #rail-list click listener:
     a [data-tw] click toggles that id in railShut, saves, renders the rail (before data-focus: the arrow is
     not the row). TEXT keys zh + en: rail.lost (zh 上级不明), rail.fold (zh 收起), rail.unfold (zh 展开).
  P5 CSS: --rail-w 290 .. 310px (about 300; was 212). Phone (@media max-width 960px): .rail width
     min(300px,84%). .rrow b: two lines then … (white-space normal, display -webkit-box, -webkit-line-clamp 2,
     -webkit-box-orient vertical, overflow hidden). .kids: list-style none, a left margin of 4 .. 16px; a guide
     line: a .kids > li ::before with border-top (the elbow) and a ::after with border-left (the line down).
     .tw: a fixed width; .tw[aria-expanded="false"] turns (rotate or transform); .tw.leaf visibility:hidden.
     .more and .who have rules. .rrow.sub has no padding-left (the old 16px indent is gone).
"""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from test_agent_city_people import ac, function_source, page, run_sim  # noqa: E402
from test_agent_city_chain import TA as PA, TB as PB, two_territory_view  # noqa: E402
from test_agent_city_ux_page import css, listener_block, media_960, rule, text_keys  # noqa: E402
from test_agent_city_talk import A_REPO, B_REPO, TA, TB, ServerCase  # noqa: E402
from test_agent_city_roster import RosterCase  # noqa: E402


def decl(block):
    return re.sub(r"\s+", "", block or "")


def margin_left(block):
    """The left margin in px a declaration block sets (margin-left, else the margin shorthand); -1 when none."""
    m = re.search(r"margin-left:(-?\d+(?:\.\d+)?)px", block)
    if m:
        return float(m.group(1))
    m = re.search(r"margin:([^;]*)", block)
    if not m:
        return -1
    vals = [float(v[:-2]) if v.endswith("px") else 0.0 for v in m.group(1).replace(",", " ").split()]
    return {1: lambda v: v[0], 2: lambda v: v[1], 3: lambda v: v[1], 4: lambda v: v[3]}.get(len(vals), lambda v: -1)(vals)


# ---------------------------------------------------------------------------
# S: the server keeps who sent whom
# ---------------------------------------------------------------------------

class TestUpOnSpawnS1(ServerCase):

    def test_a_task_manager_hangs_on_its_governor(self):
        self.governor()
        self.events()
        self.lead()
        self.assertEqual(self.spawn_of("s:tm1")["up"], "gov:" + TA)

    def test_a_task_manager_without_a_governor_still_names_it(self):
        self.lead()
        ev = self.spawn_of("s:tm1")
        self.assertEqual(ev["up"], "gov:" + TA, "the page puts it under the repo while there is no governor")
        self.assertEqual(ev["from"], "", "from is unchanged")

    def test_a_worker_hangs_on_its_task_manager(self):
        self.governor()
        self.lead()
        self.events()
        self.sub("w1", "tm1", role="task-manager")
        self.assertEqual(self.spawn_of("w1")["up"], "s:tm1")

    def test_a_governors_deputy_hangs_on_the_governor(self):
        self.governor()
        self.events()
        self.sub("d1", "g1", kind="fast-lane-deputy")
        self.assertEqual(self.spawn_of("d1")["up"], "gov:" + TA)

    def test_a_helper_hangs_on_the_area_manager_and_its_subagent_on_it(self):
        # city-office O2 (2026-11-24): the tree is 区经理 > 设计师, 助理, 经理 (was: a helper right under the repo)
        self.governor()
        self.events()
        self.helper()
        self.assertEqual(self.spawn_of("s:h1")["up"], "gov:" + TA)
        self.sub("e1", "h1", kind="Explore")
        self.assertEqual(self.spawn_of("e1")["up"], "s:h1")

    def test_another_repos_task_manager_names_its_own_governor(self):
        self.governor("g1", A_REPO)
        self.events()
        self.line("PostToolUse", "tm9", B_REPO, role="task-manager", tool="Bash")
        self.assertEqual(self.spawn_of("s:tm9")["up"], "gov:" + TB)


class TestUpInTheSnapshotS2(ServerCase):

    def snap_agents(self):
        client = self.st.add_client()
        try:
            data = client.queue.get_nowait().decode("utf-8")
        finally:
            self.st.remove_client(client)
        return {a["id"]: a for a in json.loads(data.split("data:", 1)[1])["agents"]}

    def test_every_agent_carries_its_up(self):
        self.governor()
        self.lead()
        self.helper()
        self.sub("w1", "tm1", role="task-manager")
        self.sub("d1", "g1", kind="fast-lane-deputy")
        agents = self.snap_agents()
        for cid, want in (("s:tm1", "gov:" + TA), ("s:h1", "gov:" + TA), ("w1", "s:tm1"), ("d1", "gov:" + TA)):
            self.assertIn(cid, agents)
            self.assertIn("up", agents[cid], cid)
            self.assertEqual(agents[cid]["up"], want, cid)

    def test_up_stays_after_later_lines(self):
        self.governor()
        self.lead()
        self.sub("w1", "tm1", role="task-manager")
        for _ in range(3):
            self.line("PostToolUse", "tm1", role="task-manager", aid="w1", at="worker", tool="Read")
        self.assertEqual(self.snap_agents()["w1"]["up"], "s:tm1")


class TestUpAfterRestartS3(RosterCase):

    def test_a_restored_task_manager_names_its_governor(self):
        self.a_citizen("sid-tm", role="task-manager")
        self.restart()
        self.assertEqual(self.agents()["s:sid-tm"].get("up"), "gov:" + self.terr())

    def test_a_restored_role_less_session_hangs_on_the_area_manager(self):
        # city-office O2: a session with no role is 助理, under the area manager
        self.a_citizen("sid-h", role="")
        self.restart()
        self.assertEqual(self.agents()["s:sid-h"].get("up"), "gov:" + self.terr())


# ---------------------------------------------------------------------------
# P1 + P2 + P3: the page builds the tree
# ---------------------------------------------------------------------------

TREE_SETUP = r"""
const V = __payload.view, A = V.territories.find(t => t.id === __payload.ta), B = V.territories.find(t => t.id === __payload.tb);
const OF = A.offices[0];
function buildLand(view){ officeState(view); }
const ag = (id, role, label, terr, up, lead, office) => Object.assign({ id, role, label, task: label, stuck: false,
  done: false, tools: {}, terr, lead: lead || '', office: office || null, relay: '' }, up === undefined ? {} : { up });
const AGENTS = [
  ag('s:T1', 'task-manager', 'rail <b> Task Manager', A.id, 'gov:' + A.id),          // a lead with NO office
  ag('s:T2', 'task-manager', 'est Task Manager', A.id, 'gov:' + A.id, '', { x: OF.x, z: OF.z }),
  ag('w11', 'worker', 'w11', A.id, 's:T1', 's:T1'),
  ag('w12', 'worker', 'w12', A.id, 's:T1'),                     // up says it, no lead
  ag('w21', 'worker', 'w21', A.id, 's:T2', 's:T2'),
  ag('w22', 'worker', 'w22', A.id, undefined, 's:T2'),          // an older server: no up, the lead says it
  ag('d1', 'fast-lane-deputy', 'd1', A.id, 'gov:' + A.id),      // the governor's deputy
  ag('s:H', 'task-manager', 'app Helper', A.id, ''),            // the owner opened it: right under the repo
  ag('x1', 'worker', 'x1', A.id, ''),                           // nobody knows its parent
  ag('x2', 'worker', 'x2', A.id, 's:GONE'),                     // its parent is not here
  ag('r1', 'worker', 'r1', A.id, 's:T1', 's:T1'),               // resting
  ag('s:T3', 'task-manager', 'b Task Manager', B.id, 'gov:' + B.id),   // B has no governor
  ag('y1', 'worker', 'y1', B.id, 's:T3', 's:T3'),
];
apply({ type: 'snapshot', world: V, gov: { state: 'busy', terr: A.id }, governors: 1, asks: [], shows: [],
  govs: [{ terr: A.id, state: 'busy' }], agents: AGENTS });
byId('r1').state = 'resting';
apply({ type: 'spawn', id: 'n1', role: 'worker', label: 'n1', task: 'n1', terr: B.id, up: 's:T3', lead: 's:T3', from: 's:T3' });
const rowsOf = g => g.rows.map(r => [r.id, r.depth, !!r.rest, r.up, r.kids, !!r.lost]);
/* the nesting of the drawn tree: for every data-focus, how many <ul class="kids"> it sits in */
function nest(h){
  const out = {}, stack = [], re = /<ul class="([^"]*)"|<\/ul>|data-focus="([^"]*)"/g;
  let m;
  while ((m = re.exec(h))) {
    if (m[1] !== undefined) stack.push(m[1]);
    else if (m[0] === '</ul>') stack.pop();
    else out[m[2]] = stack.filter(k => k.split(' ').includes('kids')).length;
  }
  return out;
}
const ids = h => [...h.matchAll(/data-focus="([^"]*)"/g)].map(m => m[1]);
/* one row button's own markup, from <button ... data-focus="id" to its </button> */
const rowOf = (h, id) => { const i = h.indexOf('data-focus="' + id + '"'); if (i < 0) return ''; const s = h.lastIndexOf('<button', i); return h.slice(s, h.indexOf('</button>', i) + 9); };
"""

TREE_DRIVER = TREE_SETUP + r"""
const G = railGroups();
const none = new Set();
const h0 = railHtml(G, 'w21', none, none);
const h0b = railHtml(G, 'w21', none, none, undefined, new Set());
byId('w12').waiting = true;
const G1 = railGroups();
const h1 = railHtml(G1, null, none, none, undefined, new Set(['s:T1']));
const h2 = railHtml(G1, null, none, none, undefined, new Set(['gov:' + A.id]));
const h3 = railHtml(G1, null, none, new Set([A.id]), undefined, none);
const cnt = railCount(G1);
byId('w12').waiting = false;
const fresh = newCitizen('zz', 'worker', 't', A.id);
__out = { a: A.id, b: B.id, terrs: map.territories.map(t => t.id),
  groups: G.map(g => ({ terr: g.terr, rows: rowsOf(g) })),
  ups: { T1: byId('s:T1').up, w12: byId('w12').up, w22: byId('w22').up, n1: byId('n1').up,
         fresh: fresh.up },
  h0, h0b, h1, h2, h3, ids0: ids(h0), ids1: ids(h1), ids2: ids(h2), ids3: ids(h3), nest0: nest(h0), nest3: nest(h3),
  rowT1shut: rowOf(h1, 's:T1'), rowGovShut: rowOf(h2, 'gov:' + A.id), rowT1open: rowOf(h0, 's:T1'),
  rowX1: rowOf(h0, 'x1'), rowX2: rowOf(h0, 'x2'), rowH: rowOf(h0, 's:H'), rowW11: rowOf(h0, 'w11'), rowD1: rowOf(h0, 'd1'),
  cnt, lost: i18n('rail.lost'), fold: i18n('rail.fold'), unfold: i18n('rail.unfold') };
"""

NO_GOV_DRIVER = TREE_SETUP + r"""
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: A.id }, governors: 0, asks: [], shows: [], govs: [],
  agents: AGENTS.concat([ag('c1', 'worker', 'c1', B.id, 'c2'), ag('c2', 'worker', 'c2', B.id, 'c1'),
                         ag('c3', 'worker', 'c3', B.id, 'c3')]) });
const G = railGroups();
__out = { a: A.id, b: B.id, groups: G.map(g => ({ terr: g.terr, rows: rowsOf(g) })), h: railHtml(G, null, new Set(), new Set()) };
"""

PAYLOAD = None


def payload():
    global PAYLOAD
    if PAYLOAD is None:
        PAYLOAD = {"view": two_territory_view(), "ta": PA, "tb": PB}
    return PAYLOAD


REQ = ("apply", "officeState", "railGroups", "railHtml", "railCount", "byId", "newCitizen", "i18n", "citizens")


class TestPageKeepsUpP1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = run_sim(TREE_DRIVER, payload(), REQ)

    def test_snapshot_and_spawn_keep_up(self):
        u = self.r["ups"]
        self.assertEqual(u["T1"], "gov:" + self.r["a"], "placeAgent keeps a.up")
        self.assertEqual(u["w12"], "s:T1")
        self.assertEqual(u["w22"], "", "no up from the server: ''")
        self.assertEqual(u["n1"], "s:T3", "a live spawn keeps ev.up")
        self.assertEqual(u["fresh"], "", "newCitizen starts with up ''")

    def test_demo_spawn_carries_up(self):
        src = function_source("spawnDemo") or ""
        self.assertRegex(src, r"\bup\s*:", "spawnDemo's spawn event carries up")


# ---------------------------------------------------------------------------
# P4: wiring, storage, words
# ---------------------------------------------------------------------------

class TestWiringP4(unittest.TestCase):

    def test_shut_is_remembered(self):
        p = page()
        self.assertRegex(p, r"let railShut\s*=\s*new Set\(")
        self.assertIn("agent-city.railShut", p)
        src = function_source("saveRailShut") or ""
        self.assertIn("localStorage.setItem", src)
        self.assertIn("try", src)
        i = p.index("let railShut")
        near = p[i:i + 600]
        self.assertIn("localStorage.getItem('agent-city.railShut')", near)
        self.assertIn("try", near)

    def test_render_passes_it(self):
        self.assertRegex(function_source("renderRail") or "", r"railHtml\([^;]*\brailShut\)")

    def test_arrow_click(self):
        block = listener_block(r"\$\('#rail-list'\)", "click") or ""
        self.assertRegex(block, r"data-tw|dataset\.tw")
        self.assertIn("railShut", block)
        self.assertIn("saveRailShut()", block)
        self.assertIn("renderRail()", block)
        tw = block.find("tw"), block.find("data-focus")
        self.assertTrue(0 <= tw[0] < tw[1], "the arrow is handled before a row's data-focus")

    def test_words(self):
        for key in ("rail.lost", "rail.fold", "rail.unfold"):
            self.assertEqual(text_keys(key), 2, key + ": zh and en")
        p = page()
        self.assertIn("'rail.lost': '上级不明'", p)
        self.assertIn("'rail.fold': '收起'", p)
        self.assertIn("'rail.unfold': '展开'", p)


# ---------------------------------------------------------------------------
# P5: width, wrap, indent, guide line
# ---------------------------------------------------------------------------

class TestCssP5(unittest.TestCase):

    def test_wider_rail(self):
        m = re.search(r"--rail-w\s*:\s*(\d+)px", css())
        self.assertIsNotNone(m)
        self.assertTrue(290 <= int(m.group(1)) <= 310, "about 300px (owner pick B): " + m.group(1))

    def test_phone_drawer(self):
        self.assertIn("width:min(300px,84%)", decl(rule(".rail", media_960())))

    def test_names_wrap_to_two_lines(self):
        b = decl(rule(".rrow b"))
        for bit in ("display:-webkit-box", "-webkit-line-clamp:2", "-webkit-box-orient:vertical", "overflow:hidden"):
            self.assertIn(bit, b, bit)
        self.assertNotIn("white-space:nowrap", b)
        self.assertNotIn("text-overflow:ellipsis;white-space:nowrap", b)

    def test_indent_and_guide_line(self):
        c = css()
        # every block whose selector ends with the .kids list itself (".kids", "ul.kids", ".tree .kids", ...)
        kids = ";".join(decl(b) for s, b in re.findall(r"([^{}]*)\{([^{}]*)\}", c)
                        if any(re.search(r"\.kids$", x.strip()) for x in s.split(",")))
        self.assertIn("list-style:none", kids)
        self.assertTrue(4 <= margin_left(kids) <= 16, "indent per level: " + kids)
        before = [b for s, b in re.findall(r"([^{}]*)\{([^{}]*)\}", c) if ".kids" in s and "::before" in s]
        after = [b for s, b in re.findall(r"([^{}]*)\{([^{}]*)\}", c) if ".kids" in s and "::after" in s]
        self.assertTrue(any("border-top" in b for b in before), "the elbow into each child")
        self.assertTrue(any("border-left" in b for b in after), "the line down from the parent")

    def test_arrow(self):
        self.assertRegex(decl(rule(".tw")), r"width:\d+px")
        turned = decl(rule('.tw[aria-expanded="false"]'))
        self.assertRegex(turned, r"rotate|transform")
        self.assertIn("visibility:hidden", decl(rule(".tw.leaf")))

    def test_tags_and_no_old_indent(self):
        self.assertTrue(rule(".more"), ".more")
        self.assertTrue(rule(".who"), ".who")
        self.assertNotIn("padding-left", decl(rule(".rrow.sub")), "the indent comes from the nesting now")


if __name__ == "__main__":
    unittest.main()
