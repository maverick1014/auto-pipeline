"""Failing tests for city-worktrees (requirements/city.md, Worktrees).

One worktree = one construction site inside its repo's territory.

CONTRACT

  Hook (bin/agent-city-hook.sh)
    A 16th key "wt", right after "ask" (city-quality adds "file" after it):
    when the folder holding .git (the
    same walk up from cwd the hook already does for "repo") has a .git FILE
    (a linked worktree), "wt" is that folder's physical path (cd -P, pwd -P),
    JSON-escaped. A .git folder (the main checkout), no git, or a missing
    cwd -> "". Builtins only (the tests run it with an empty PATH).

  Server (bin/agent_city.py), module level
    read_sites(root) -> [{"path", "module", "status", "human", "stalled"}]
        from <root>/agent_worktree.txt, one per line, file order. A line is
        "<path> | <module> | <status> | since <time>" (bin/agent-file.sh
        worktree set). status is "working", "final" or "idle"; anything
        else -> "working". A human-direct line (bin/agent-start.sh) is
        "<path> | task manager, human-direct | task: ... | since <time>":
        human true, status "working", module = the path's last part.
        stalled: <root>/.git/agent_watch.json (the watch status of
        bin/agent_watch.py) has a task with the same path and a non-empty
        "stall". Missing files -> [] / false.
        Blank lines skipped.
    site_id(path) -> "wt:" + sha1(realpath(path) as utf-8).hexdigest()[:10]
    site_branch(path) -> the worktree's branch ("feat-a") read from files
        (<path>/.git -> gitdir -> HEAD "ref: refs/heads/<b>"); a detached
        HEAD -> the first 7 hex of its sha; not a linked worktree -> "".
    site_head(path) -> the worktree's HEAD commit, 40 hex, from files only:
        a loose ref in the common dir, else packed-refs; detached -> the
        sha itself; unreadable -> "".

  Server, CityState
    scan_sites() -- for every territory identity that is a "<root>/.git"
        folder (the start repo and every territory in the world), read the
        two files again only when their size or mtime changed, and diff
        against the sites it knows:
      new site     -> it takes an office: a live lead in that territory
                      whose last line carried wt == the site path gives
                      the site its office tile; else the plan's first free
                      office spot. Then a {"type": "world"} broadcast (the
                      view's territory "offices" has {"site": id, "lead": "",
                      "x", "z"}; the territory "sites" list has the site),
                      then {"type": "site", "terr", "id", "branch", "module",
                      "status", "human", "stalled", "x", "z"}.
      changed      -> one "site" event with the new fields, no "world".
      gone         -> {"type": "site_end", "terr", "id", "how", "x", "z"}:
                      how "merged" when the site's last known head (site_head,
                      read on every scan while the site is live) is an
                      ancestor of the root checkout's HEAD
                      (git merge-base --is-ancestor), else "removed". Its
                      office frees; then a "world" broadcast.
      No change    -> no broadcast at all.
    Every lead office entry in the view has "site": "" too.
    A task-manager citizen whose line carries wt == a live site's path has
        that site's office as its own ("office" on spawn and snapshot), and
        no office entry of its own in the view.
    recount_loop calls scan_sites.

  Page (bin/agent-city.html), simulation section (runs in node)
    sites -- Map id -> {id, terr, branch, module, status, human, stalled,
        x, z, phase}; phase 'live' | 'merging' | 'packing'.
    siteList() -> the site records, in any order.
    apply(snapshot) and apply(world) take every territory's "sites" (terr =
        that territory's id) as phase 'live'; a live site missing from the
        view is dropped, a merging or packing one is kept.
    apply({type: 'site'}) upserts; apply({type: 'site_end', how}) -> phase
        'merging' (how 'merged') or 'packing'; update(dt) removes a merging
        site after SITE_MERGE_SEC and a packing one after SITE_PACK_SEC
        (both 3..12 s).
    siteRoad(id) -> while merging {from: {x, y}, to: {x, y}, p}: from within
        1.6 tiles of the office centre, to within 1.8 of the hall centre,
        p from 0 to 1 over the merge; null when not merging.
    siteDecor(site) -> [{key, x, z, ...}] (pure):
        live: at least 4 'roads/construction-fence' items, each 1.0 to 3.0
          tiles from the office centre, around it (both sides in x and z);
          one 'survival/signpost-single' with text == the branch; one
          'roads/construction-light' with on == (status !== 'idle');
          'survival/structure' (scaffolding) only while status 'working';
          stalled -> 'roads/construction-barrier' and a 'particles/smoke_01'
          item; human -> 'forest/flag' with label '亲自带'.
        merging: no fence (the fence goes); packing: nothing.
    topCounts() -> [[label, n], ...]: '干活', '找总督', '休息', '建成' as
        before, then ['卡住的工地', n] only when n (live stalled sites) > 0.
        renderStats draws from it.
    DEMO_SITES -- the demo's sites: at least 2, one stalled, one human.

  Assets: roads/construction-fence, roads/construction-light,
    roads/construction-barrier, survival/signpost-single in MODELS;
    particles/smoke_01.png with particles/License.txt (CC0).

Run: python3 -m unittest tests.test_agent_city_worktrees </dev/null
"""

import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HOOK = os.path.join(ROOT, "bin", "agent-city-hook.sh")
ASSETS = os.path.join(ROOT, "bin", "agent-city-assets")
BASH = shutil.which("bash") or "/bin/bash"
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)

import agent_city as ac  # noqa: E402
from test_agent_city_people import page, run_sim, plan_views  # noqa: E402


def git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    return subprocess.run(["git", "-C", cwd] + list(args), check=True, capture_output=True, env=env,
                          stdin=subprocess.DEVNULL, text=True).stdout.strip()


def make_repo(base):
    """A main checkout <base>/app on branch main with one commit, and a linked
    worktree <base>/wt-a on branch feat-a with one more commit."""
    root = os.path.join(base, "app")
    os.mkdir(root)
    git(root, "init", "-q", "-b", "main")
    with open(os.path.join(root, "a.txt"), "w") as fh:
        fh.write("a\n")
    git(root, "add", "a.txt")
    git(root, "commit", "-q", "-m", "one")
    wt = os.path.join(base, "wt-a")
    git(root, "worktree", "add", "-q", "-b", "feat-a", wt)
    with open(os.path.join(wt, "b.txt"), "w") as fh:
        fh.write("b\n")
    git(wt, "add", "b.txt")
    git(wt, "commit", "-q", "-m", "two")
    return os.path.realpath(root), os.path.realpath(wt)


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    # a later write in the same second must still look changed (size or mtime)
    st = os.stat(path)
    os.utime(path, (st.st_atime, st.st_mtime + write.bump))
    write.bump += 1


write.bump = 1


# ---------------------------------------------------------------------------
# Hook
# ---------------------------------------------------------------------------

class TestHookWt(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_wt_hook_")
        self.city = os.path.join(self.base, "city")
        os.mkdir(self.city)
        with open(os.path.join(self.city, "on"), "w") as fh:
            fh.write("%s 4777\n" % os.getpid())
        self.empty = os.path.join(self.base, "emptybin")
        os.mkdir(self.empty)
        self.root, self.wt = make_repo(self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def row(self, cwd):
        data = json.dumps({"session_id": "s1", "cwd": cwd, "hook_event_name": "PostToolUse",
                           "tool_name": "Read", "tool_input": {"file_path": "/x"}}).encode()
        env = {"AGENT_CITY_DIR": self.city, "PATH": self.empty, "HOME": self.base}
        res = subprocess.run([BASH, HOOK], input=data, env=env, capture_output=True, timeout=20)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(self.city, "events.jsonl"), encoding="utf-8") as fh:
            lines = [json.loads(x, object_pairs_hook=lambda p: dict(p)) for x in fh if x.strip()]
        os.remove(os.path.join(self.city, "events.jsonl"))
        return lines[-1]

    def test_linked_worktree_gives_its_physical_folder(self):
        row = self.row(self.wt)
        self.assertEqual(row["wt"], self.wt)
        self.assertEqual(row["repo"], os.path.join(self.root, ".git"))

    def test_a_subfolder_of_the_worktree_gives_the_same(self):
        sub = os.path.join(self.wt, "deep", "er")
        os.makedirs(sub)
        self.assertEqual(self.row(sub)["wt"], self.wt)

    def test_a_symlinked_path_is_made_physical(self):
        link = os.path.join(self.base, "link-to-wt")
        os.symlink(self.wt, link)
        self.assertEqual(self.row(link)["wt"], self.wt)

    def test_main_checkout_gives_empty(self):
        self.assertEqual(self.row(self.root)["wt"], "")

    def test_outside_git_gives_empty(self):
        plain = os.path.join(self.base, "plain")
        os.mkdir(plain)
        self.assertEqual(self.row(plain)["wt"], "")

    def test_missing_cwd_gives_empty(self):
        self.assertEqual(self.row(os.path.join(self.base, "nope"))["wt"], "")

    def test_wt_is_the_key_right_after_ask(self):
        # city-quality appends "file" after it (tests/test_agent_city_quality.py); idea-city C4 dropped
        # "kind", so wt moved up one; city-talk put "to" before "ask", so both moved down one
        row = self.row(self.wt)
        keys = list(row)
        self.assertEqual(keys.index("wt"), 15)
        self.assertEqual(keys[13:16], ["to", "ask", "wt"])


# ---------------------------------------------------------------------------
# Server: files
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Server: CityState
# ---------------------------------------------------------------------------

def drain(client):
    out = []
    while not client.queue.empty():
        out.append(json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1]))
    return out


def snapshot(st):
    client = st.add_client()
    return json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1]), client


def feed(st, ev, sid, repo, role="", wt=""):
    st.feed_line({"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "Read", "nt": "", "proj": "p",
                  "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": "",
                  "ask": "", "wt": wt}, 1000.0)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

PAGE_REQUIRED = ("apply", "update", "sites", "siteList", "siteRoad", "siteDecor", "topCounts",
                 "SITE_MERGE_SEC", "SITE_PACK_SEC", "DEMO_SITES", "officeState")


def page_view():
    views = plan_views()
    return views[sorted(views)[0]]


SITE_DRIVER = r"""
const V = JSON.parse(JSON.stringify(__payload.view)), T = V.territories[0], tid = T.id;
function buildLand(view){ officeState(view); }
const O = T.plots[0];
const office = { x: O.x, z: O.z };
T.offices = [{ lead: '', site: 'wt:1', x: office.x, z: office.z }];
T.sites = [{ id: 'wt:1', branch: 'feat-a', module: 'city-a', status: 'working', human: false, stalled: false,
             x: office.x, z: office.z }];
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: tid }, govs: [], governors: 0, asks: [],
        shows: [], agents: [] });
const out = {};
out.afterSnap = siteList().map(s => ({ id: s.id, terr: s.terr, phase: s.phase, branch: s.branch }));
out.tid = tid;
function decor(s){ return siteDecor(s).map(d => ({ key: d.key, x: d.x, z: d.z, text: d.text, on: d.on, label: d.label })); }
out.working = decor(sites.get('wt:1'));
apply({ type: 'site', terr: tid, id: 'wt:1', branch: 'feat-a', module: 'city-a', status: 'final', human: false,
        stalled: false, x: office.x, z: office.z });
out.final = decor(sites.get('wt:1'));
apply({ type: 'site', terr: tid, id: 'wt:1', branch: 'feat-a', module: 'city-a', status: 'idle', human: true,
        stalled: true, x: office.x, z: office.z });
out.idleStalledHuman = decor(sites.get('wt:1'));
out.counts = topCounts();
apply({ type: 'site', terr: tid, id: 'wt:1', branch: 'feat-a', module: 'city-a', status: 'working', human: false,
        stalled: false, x: office.x, z: office.z });
out.countsCalm = topCounts();
out.office = office; out.hall = { x: T.cx, z: T.cz };
out.roadBefore = siteRoad('wt:1');
apply({ type: 'site_end', terr: tid, id: 'wt:1', how: 'merged', x: office.x, z: office.z });
const W2 = JSON.parse(JSON.stringify(V)); W2.territories[0].sites = []; W2.territories[0].offices = [];
apply({ type: 'world', world: W2 });
out.phaseAfterEnd = sites.get('wt:1') ? sites.get('wt:1').phase : null;
out.mergingDecor = decor(sites.get('wt:1'));
out.road0 = siteRoad('wt:1');
for (let i = 0; i < 20; i++) update(.1);
out.road1 = siteRoad('wt:1');
for (let i = 0; i < 150; i++) update(.1);
out.goneAfterMerge = !sites.get('wt:1');
out.mergeSec = SITE_MERGE_SEC; out.packSec = SITE_PACK_SEC;
apply({ type: 'site', terr: tid, id: 'wt:2', branch: 'feat-b', module: 'city-b', status: 'working', human: false,
        stalled: false, x: office.x, z: office.z });
apply({ type: 'site_end', terr: tid, id: 'wt:2', how: 'removed', x: office.x, z: office.z });
out.packPhase = sites.get('wt:2') ? sites.get('wt:2').phase : null;
out.packDecor = decor(sites.get('wt:2'));
out.packRoad = siteRoad('wt:2');
for (let i = 0; i < 150; i++) update(.1);
out.goneAfterPack = !sites.get('wt:2');
apply({ type: 'site', terr: tid, id: 'wt:3', branch: 'feat-c', module: 'city-c', status: 'working', human: false,
        stalled: false, x: office.x, z: office.z });
const W3 = JSON.parse(JSON.stringify(V)); W3.territories[0].sites = [];
apply({ type: 'world', world: W3 });
out.liveDroppedByWorld = !sites.get('wt:3');
out.demo = DEMO_SITES.map(s => ({ stalled: !!s.stalled, human: !!s.human }));
__out = out;
"""


if __name__ == "__main__":
    unittest.main()
