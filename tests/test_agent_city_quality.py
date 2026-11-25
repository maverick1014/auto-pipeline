"""Failing tests for city-quality and city-levelups (requirements/city.md,
Quality and Growth).

CONTRACT

  Hook (bin/agent-city-hook.sh)
    A key "file", last, after "wt" (16 keys since idea-city C4 dropped "kind"): for a PostToolUse of Edit, Write,
    MultiEdit (tool_input.file_path) or NotebookEdit (notebook_path) found
    in the first 4096 bytes, the path relative to the folder holding .git
    (the same relative path the kind rule already uses), JSON-escaped;
    "" when the file is outside that folder, there is no git folder, the
    relative path is longer than 300 bytes, or for any other event/tool.
    Builtins only.

  Server (bin/agent_city.py), module level
    file_quality(text) -> {"lines", "long_fn", "depth", "score"}
      lines    number of lines
      long_fn  lines of the longest function: a start line matches
               ^\\s*(async\\s+)?(def|function|func|fn)\\b, or ends with ") {"
               or ") => {" (spaces allowed); it ends at the last following
               line indented deeper than the start (no "{" at the end of the
               start line) or where the brace depth drops back (a "{" at
               the end). Length = end - start + 1.
      depth    deepest nesting: max of brace depth and indent level
               (leading spaces // 4, a tab = 4 spaces)
      score    "poor": lines > 1500 or long_fn > 200 or depth > 8;
               "fair": lines > 500 or long_fn > 80 or depth > 5; else "good"
    duplicates(texts) -> set of names (keys of TEXTS) holding a run of 8 or
        more consecutive significant lines (stripped; lines under 4
        characters are skipped, not counted) that also appears elsewhere
        (another file, or another place in the same file).
    hot_counts(root, days=90) -> {repo-relative path: commits in the last
        DAYS days touching it} (one git log).
    combine_quality(score, dup, hot) -> the score made one step worse for
        dup and one more for hot, never past "poor".
    wrong_district(path) -> int(sha1(path utf-8).hexdigest(), 16) % 3 == 0

  Server, buildings
    A building has "files" (repo-relative, newest first, at most 12), "hist"
    ([{"by", "at"}], newest first, at most 10), "q" ("good"|"fair"|"poor"),
    "home" (bool: on its own district), "lv" (0..3), "name" (str). The
    layout view's buildings carry all six (old world.json buildings: files
    [], hist [], q "good", home true, lv 0, name "").
    PostToolUse with a kind and a "file":
      a building here already lists that file -> {"type": "touch", "terr",
        "plot", "by"}, a hist entry, no new building;
      the owner already has a building here -> the file is added to it,
        "touch";
      else build: quality = file_quality(that file's text)["score"] alone,
        read now (from obj "wt" when set, else the repo root = dirname of
        the "<root>/.git" identity; a file that cannot be read, or a path
        that is absolute or has a ".." part, is never read: "good";
        duplicates and hot spots only come with requality); poor and
        wrong_district(file) -> the
        first free open plot of another district in plan order, home false;
        else its own district. The "build" event carries "q", "home",
        "files", "name", "lv".
      its own district full -> level up (city-levelups): the building of that
        district with the lowest lv, oldest first (earliest in the
        territory's building list), lv + 1 (max 3); the file goes into its
        files; {"type": "levelup", "terr", "plot", "lv", "by"}. From then on
        that owner counts as having that building (its next edits touch
        it). All at 3 -> "noplot" as before.
    CityState.requality(identity): for every building, its files that still
      exist in the root checkout or in any live site (worktree) path of
      that territory: none left -> {"type": "demolish", "terr", "plot"} and
      the building goes (a building with no files recorded -- old ones --
      is never demolished and keeps its q); else q = the worst combine_quality of those files
      (duplicates across the territory's building files, hot_counts of the
      root); changed -> {"type": "quality", "terr", "plot", "q"}; a building
      with home false and q not "poor" moves to the first free open plot of
      its own district: {"type": "move", "terr", "from", "plot", "x", "z",
      "home": true}. recount() calls it for every territory it counts.

  Page (bin/agent-city.html), simulation section
    building records carry q, home, files, hist, lv, name from 'build',
      'snapshot' and 'world' (defaults as above).
    buildingPose(b) -> {dx, dz, ry}: good 0, 0, 0; fair |ry| in [.05, .2]
      and hypot(dx, dz) <= .15; poor |ry| in [.25, .5] and hypot(dx, dz) in
      [.15, .35]. Stable for a building (same result every call).
    apply 'touch' -> hist gets {by} first; 'quality' -> q; 'levelup' -> lv;
      'move' -> after MOVE_SEC (2..10 s of update) the record stands on the
      new plot (plot, gx, gy, home true) and the occupied map follows;
      'demolish' -> gone from buildings after DEMOLISH_SEC (1..8 s).
    levelScale(lv) -> {sy, sxz}: lv 0 = {1, 1}; sy and sxz grow with lv,
      sy faster; lv 3 sy <= 2.6.
    buildingInfo(b) -> {quality: '整齐'|'还行'|'有点乱', misplaced: !home,
      files, hist, level: lv, name}. The building card uses it.

Run: python3 -m unittest tests.test_agent_city_quality </dev/null
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HOOK = os.path.join(ROOT, "bin", "agent-city-hook.sh")
BASH = shutil.which("bash") or "/bin/bash"
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)

import agent_city as ac  # noqa: E402
from test_agent_city_people import page, run_sim, plan_views  # noqa: E402
from test_agent_city_worktrees import git, make_repo, write, drain, snapshot  # noqa: E402
from cityhelp import Mains  # noqa: E402


def flat(n):
    return "".join("x_%d = %d\n" % (i, i) for i in range(n))


def py_fn(body):
    return "def big():\n" + "".join("    y_%d = %d\n" % (i, i) for i in range(body)) + "\nz = 1\n"


def js_fn(body):
    return "function big(a) {\n" + "".join("  let v%d = %d;\n" % (i, i) for i in range(body)) + "}\n"


def nested_py(levels):
    out = []
    for i in range(levels):
        out.append("    " * i + "if a%d:\n" % i)
    out.append("    " * levels + "pass\n")
    return "".join(out)


def pick_name(want_wrong, stem="src/f%d.py"):
    for i in range(200):
        name = stem % i
        wrong = int(hashlib.sha1(name.encode("utf-8")).hexdigest(), 16) % 3 == 0
        if wrong == want_wrong:
            return name
    raise AssertionError("no name found")


# ---------------------------------------------------------------------------
# Hook
# ---------------------------------------------------------------------------

class TestHookFile(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_q_hook_")
        self.city = os.path.join(self.base, "city")
        os.mkdir(self.city)
        with open(os.path.join(self.city, "on"), "w") as fh:
            fh.write("%s 4777\n" % os.getpid())
        self.empty = os.path.join(self.base, "emptybin")
        os.mkdir(self.empty)
        self.root, self.wt = make_repo(self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def row(self, cwd, tool="Edit", path=None, event="PostToolUse", key="file_path"):
        data = {"session_id": "s1", "cwd": cwd, "hook_event_name": event, "tool_name": tool}
        if path is not None:
            data["tool_input"] = {key: path, "old_string": "a", "new_string": "b"}
        env = {"AGENT_CITY_DIR": self.city, "PATH": self.empty, "HOME": self.base}
        res = subprocess.run([BASH, HOOK], input=json.dumps(data).encode(), env=env,
                             capture_output=True, timeout=20)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(self.city, "events.jsonl"), encoding="utf-8") as fh:
            lines = [json.loads(x) for x in fh if x.strip()]
        os.remove(os.path.join(self.city, "events.jsonl"))
        return lines[-1]

    def test_edit_in_the_main_checkout(self):
        row = self.row(self.root, path=os.path.join(self.root, "src", "app.py"))
        self.assertEqual(row["file"], "src/app.py")
        self.assertNotIn("kind", row)  # idea-city C4: the server picks the building

    def test_edit_in_a_worktree_is_relative_to_the_worktree(self):
        row = self.row(self.wt, tool="Write", path=os.path.join(self.wt, "tests", "test_a.py"))
        self.assertEqual(row["file"], "tests/test_a.py")

    def test_notebook(self):
        row = self.row(self.root, tool="NotebookEdit", path=os.path.join(self.root, "nb", "a.ipynb"),
                       key="notebook_path")
        self.assertEqual(row["file"], "nb/a.ipynb")

    def test_outside_the_repo_is_empty(self):
        self.assertEqual(self.row(self.root, path="/etc/hosts")["file"], "")

    def test_pre_tool_use_and_other_tools_are_empty(self):
        self.assertEqual(self.row(self.root, event="PreToolUse",
                                  path=os.path.join(self.root, "a.py"))["file"], "")
        self.assertEqual(self.row(self.root, tool="Read", path=os.path.join(self.root, "a.py"))["file"], "")

    def test_a_long_path_is_empty(self):
        long = os.path.join(self.root, "d" * 320 + ".py")
        self.assertEqual(self.row(self.root, path=long)["file"], "")

    def test_quotes_stay_valid_json(self):
        row = self.row(self.root, path=os.path.join(self.root, 'we"ird.py'))
        self.assertEqual(row["file"], 'we"ird.py')

    def test_file_is_the_third_last_key(self):
        # idea-city C4: the hook line has no "kind" any more; session-names
        # added "tp" after "file" (tests/test_agent_city_session_names.py),
        # city-roles "pid" after "tp" (tests/test_agent_city_roles.py),
        # city-talk "to" right before "ask" (tests/test_agent_city_talk.py)
        row = self.row(self.root, path=os.path.join(self.root, "a.py"))
        self.assertEqual(len(row), 19)
        self.assertEqual(list(row)[-5:], ["ask", "wt", "file", "tp", "pid"])


# ---------------------------------------------------------------------------
# Server: measuring
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Server: buildings
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

PAGE_REQUIRED = ("apply", "update", "buildings", "buildingPose", "levelScale", "buildingInfo",
                 "MOVE_SEC", "DEMOLISH_SEC", "occupied", "officeState")

Q_DRIVER = r"""
const V = JSON.parse(JSON.stringify(__payload.view)), T = V.territories[0], tid = T.id;
function buildLand(view){ officeState(view); }
const P = T.plots;
T.buildings = [
  { plot: P[0].k, type: P[0].d === 'house' ? 'house' : 'house', by: 'worker', x: P[0].x, z: P[0].z,
    q: 'poor', home: false, files: ['src/a.py'], hist: [], lv: 0, name: '设置页 API' },
  { plot: P[1].k, type: 'house', by: 'worker', x: P[1].x, z: P[1].z },
];
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: tid }, govs: [], governors: 0, asks: [],
        shows: [], agents: [] });
const out = {};
const b0 = buildings.find(b => b.plot === P[0].k), b1 = buildings.find(b => b.plot === P[1].k);
out.snap0 = { q: b0.q, home: b0.home, files: b0.files, lv: b0.lv, name: b0.name };
out.snap1 = { q: b1.q, home: b1.home, files: b1.files, hist: b1.hist, lv: b1.lv, name: b1.name };
out.poses = {};
for (const q of ['good', 'fair', 'poor']) {
  const rows = [];
  for (let i = 0; i < 12; i++) {
    const b = { id: 1000 + i, plot: i, gx: i * 3, gy: i * 2, seed: (i * 7919) % 1000, q };
    const a = buildingPose(b), c = buildingPose(b);
    rows.push({ dx: a.dx, dz: a.dz, ry: a.ry, same: a.dx === c.dx && a.dz === c.dz && a.ry === c.ry });
  }
  out.poses[q] = rows;
}
apply({ type: 'touch', terr: tid, plot: P[1].k, by: 'fast-lane-deputy' });
out.touched = b1.hist.map(h => h.by);
apply({ type: 'quality', terr: tid, plot: P[1].k, q: 'fair' });
out.q1 = b1.q;
apply({ type: 'levelup', terr: tid, plot: P[1].k, lv: 2, by: 'worker' });
out.lv1 = b1.lv;
out.scales = [0, 1, 2, 3].map(levelScale);
out.info0 = buildingInfo(b0);
out.info1 = buildingInfo(b1);
const target = P[2];
apply({ type: 'move', terr: tid, from: P[0].k, plot: target.k, x: target.x, z: target.z, home: true });
for (let i = 0; i < Math.ceil((MOVE_SEC + 1) * 10); i++) update(.1);
out.moved = { plot: b0.plot, gx: b0.gx, gy: b0.gy, home: b0.home,
              occNew: occupied.get(target.x + ',' + target.z) === b0,
              occOld: occupied.get(P[0].x + ',' + P[0].z) === b0 };
out.target = { k: target.k, x: target.x, z: target.z };
out.moveSec = MOVE_SEC; out.demolishSec = DEMOLISH_SEC;
apply({ type: 'demolish', terr: tid, plot: P[1].k });
for (let i = 0; i < Math.ceil((DEMOLISH_SEC + 1) * 10); i++) update(.1);
out.demolished = !buildings.includes(b1);
apply({ type: 'build', id: 'gov', terr: tid, plot: P[3].k, btype: 'shop', x: P[3].x, z: P[3].z, by: 'worker',
        q: 'fair', home: true, files: ['ui/x.html'], name: 'x', lv: 0 });
const nb = buildings.find(b => b.plot === P[3].k);
out.built = { q: nb.q, home: nb.home, files: nb.files, lv: nb.lv };
__out = out;
"""


def q_view():
    views = plan_views()
    for key in sorted(views):
        if len(views[key]["territories"][0]["plots"]) >= 4:
            return views[key]
    raise AssertionError("no plan view with 4 open plots")



class BuildCase(unittest.TestCase):
    """A CityState with one repo whose main manager is "tm" (kept for tests/test_agent_city_idea_server.py)."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_q_state_")
        self.root, self.wt = make_repo(self.base)
        self.ident = os.path.join(self.root, ".git")
        self.terr = ac.territory_id(self.ident)
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"),
                               start_repo=self.ident,
                               main_fn=Mains({self.ident: "tm"}))   # city-roles: "tm" is the main manager
        self.snap, self.client = snapshot(self.st)
        self.st.feed_line(self.line("tm", tool="Read"), 1000.0)
        drain(self.client)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def line(self, sid, aid="", kind="", file="", tool="Edit", wt=""):
        return {"ev": "PostToolUse", "sid": sid, "aid": aid, "at": "worker" if aid else "", "tool": tool,
                "nt": "", "proj": "app", "role": "", "desc": "", "sub": "", "q": "", "klen": "",
                "repo": self.ident, "kind": kind, "ask": "", "wt": wt, "file": file}

if __name__ == "__main__":
    unittest.main()
