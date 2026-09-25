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
        stalled: <root>/agent_monitor.txt has a line for the same path whose
        6th field (" | " separated) is "STALL". Missing files -> [] / false.
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

    def test_wt_is_the_sixteenth_key_right_after_ask(self):
        # city-quality appends a 17th key "file" after it (tests/test_agent_city_quality.py)
        row = self.row(self.wt)
        keys = list(row)
        self.assertEqual(keys.index("wt"), 15)
        self.assertEqual(keys[14:16], ["ask", "wt"])


# ---------------------------------------------------------------------------
# Server: files
# ---------------------------------------------------------------------------

class TestReadSites(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="city_wt_read_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_missing_files_give_no_sites(self):
        self.assertEqual(ac.read_sites(self.root), [])

    def test_lines_statuses_and_human_direct(self):
        write(os.path.join(self.root, "agent_worktree.txt"),
              "/w/a | city-a | working | since 2026-09-25 10:00\n"
              "\n"
              "/w/b | city-b | final | since 2026-09-25 10:01\n"
              "/w/c | city-c | idle | since 2026-09-25 10:02\n"
              "/w/d | city-d | weird | since 2026-09-25 10:03\n"
              "/w/e | task manager, human-direct | task: (ask the human) | since 2026-09-25 10:04\n")
        got = ac.read_sites(self.root)
        self.assertEqual([s["path"] for s in got], ["/w/a", "/w/b", "/w/c", "/w/d", "/w/e"])
        self.assertEqual([s["status"] for s in got], ["working", "final", "idle", "working", "working"])
        self.assertEqual([s["module"] for s in got], ["city-a", "city-b", "city-c", "city-d", "e"])
        self.assertEqual([s["human"] for s in got], [False, False, False, False, True])
        self.assertEqual([s["stalled"] for s in got], [False] * 5)

    def test_stalled_from_the_monitor(self):
        write(os.path.join(self.root, "agent_worktree.txt"),
              "/w/a | city-a | working | since x\n/w/b | city-b | working | since x\n")
        write(os.path.join(self.root, "agent_monitor.txt"),
              "/w/a | city-a | pane none | commit 40m ago | activity none | STALL | 2026-09-25 11:00\n"
              "/w/b | city-b | pane working | commit 1m ago | activity 1m ago | OK | 2026-09-25 11:00\n")
        got = {s["path"]: s["stalled"] for s in ac.read_sites(self.root)}
        self.assertEqual(got, {"/w/a": True, "/w/b": False})


class TestSiteGit(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_wt_git_")
        self.root, self.wt = make_repo(self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_site_id(self):
        want = "wt:" + hashlib.sha1(os.path.realpath(self.wt).encode("utf-8")).hexdigest()[:10]
        self.assertEqual(ac.site_id(self.wt), want)

    def test_branch_and_head_from_files(self):
        self.assertEqual(ac.site_branch(self.wt), "feat-a")
        self.assertEqual(ac.site_head(self.wt), git(self.wt, "rev-parse", "HEAD"))

    def test_head_from_packed_refs(self):
        git(self.root, "pack-refs", "--all")
        self.assertFalse(os.path.exists(os.path.join(self.root, ".git", "refs", "heads", "feat-a")))
        self.assertEqual(ac.site_head(self.wt), git(self.wt, "rev-parse", "HEAD"))

    def test_detached_head(self):
        sha = git(self.wt, "rev-parse", "HEAD")
        git(self.wt, "checkout", "-q", "--detach")
        self.assertEqual(ac.site_branch(self.wt), sha[:7])
        self.assertEqual(ac.site_head(self.wt), sha)

    def test_not_a_worktree(self):
        self.assertEqual(ac.site_branch(self.root), "")
        self.assertEqual(ac.site_branch(os.path.join(self.base, "nope")), "")
        self.assertEqual(ac.site_head(os.path.join(self.base, "nope")), "")

    def test_recount_loop_scans_sites(self):
        self.assertIn("scan_sites", inspect.getsource(ac.recount_loop))


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


class SiteCase(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_wt_state_")
        self.root, self.wt = make_repo(self.base)
        self.ident = os.path.join(self.root, ".git")
        self.terr = ac.territory_id(self.ident)
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"),
                               plans=ac.load_plans(), count_fn=lambda i: 0,
                               balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}},
                               start_repo=self.ident)
        self.wtf = os.path.join(self.root, "agent_worktree.txt")
        self.mon = os.path.join(self.root, "agent_monitor.txt")
        self.snap, self.client = snapshot(self.st)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def terr_view(self, world):
        return [t for t in world["territories"] if t["id"] == self.terr][0]

    def register(self, status="working", path=None):
        write(self.wtf, "%s | city-a | %s | since 2026-09-25 10:00\n" % (path or self.wt, status))

    def scan(self):
        self.st.scan_sites()
        return drain(self.client)


class TestSitesLifecycle(SiteCase):

    def test_no_file_no_sites_no_events(self):
        self.assertEqual(self.scan(), [])
        self.assertEqual(self.terr_view(self.snap["world"]).get("sites", []), [])

    def test_new_site_world_then_site_event(self):
        self.register()
        msgs = self.scan()
        types = [m["type"] for m in msgs]
        self.assertIn("world", types)
        self.assertIn("site", types)
        self.assertLess(types.index("world"), types.index("site"))
        site = [m for m in msgs if m["type"] == "site"][0]
        self.assertEqual(site["id"], ac.site_id(self.wt))
        self.assertEqual(site["terr"], self.terr)
        self.assertEqual((site["branch"], site["module"], site["status"], site["human"], site["stalled"]),
                         ("feat-a", "city-a", "working", False, False))
        tv = self.terr_view([m for m in msgs if m["type"] == "world"][-1]["world"])
        self.assertEqual([s["id"] for s in tv["sites"]], [site["id"]])
        office = [o for o in tv["offices"] if o.get("site") == site["id"]]
        self.assertEqual(len(office), 1)
        self.assertEqual((office[0]["x"], office[0]["z"]), (site["x"], site["z"]))
        self.assertEqual(office[0]["lead"], "")

    def test_snapshot_carries_live_sites(self):
        self.register()
        self.scan()
        snap, _ = snapshot(self.st)
        self.assertEqual([s["id"] for s in self.terr_view(snap["world"])["sites"]], [ac.site_id(self.wt)])

    def test_unchanged_files_no_events(self):
        self.register()
        self.scan()
        self.assertEqual(self.scan(), [])

    def test_status_change_is_one_site_event(self):
        self.register()
        self.scan()
        self.register("final")
        msgs = self.scan()
        self.assertEqual([m["type"] for m in msgs], ["site"])
        self.assertEqual(msgs[0]["status"], "final")

    def test_stalled_from_monitor(self):
        self.register()
        self.scan()
        write(self.mon, "%s | city-a | pane none | commit 40m ago | activity none | STALL | t\n" % self.wt)
        msgs = self.scan()
        self.assertEqual([m["type"] for m in msgs], ["site"])
        self.assertTrue(msgs[0]["stalled"])

    def test_merged_site(self):
        self.register()
        self.scan()
        git(self.root, "merge", "-q", "--no-ff", "-m", "merge feat-a", "feat-a")
        git(self.root, "worktree", "remove", "--force", self.wt)
        git(self.root, "branch", "-D", "feat-a")
        write(self.wtf, "")
        msgs = self.scan()
        ends = [m for m in msgs if m["type"] == "site_end"]
        self.assertEqual(len(ends), 1)
        self.assertEqual((ends[0]["id"], ends[0]["how"], ends[0]["terr"]), (ac.site_id(self.wt), "merged", self.terr))
        self.assertIn("world", [m["type"] for m in msgs])
        tv = self.terr_view([m for m in msgs if m["type"] == "world"][-1]["world"])
        self.assertEqual(tv.get("sites", []), [])
        self.assertFalse([o for o in tv["offices"] if o.get("site")])

    def test_removed_site(self):
        self.register()
        self.scan()
        git(self.root, "worktree", "remove", "--force", self.wt)
        git(self.root, "branch", "-D", "feat-a")
        write(self.wtf, "")
        ends = [m for m in self.scan() if m["type"] == "site_end"]
        self.assertEqual([e["how"] for e in ends], ["removed"])

    def test_head_is_tracked_while_live(self):
        """A commit made after the site appeared, then merged: still "merged"."""
        self.register()
        self.scan()
        with open(os.path.join(self.wt, "c.txt"), "w") as fh:
            fh.write("c\n")
        git(self.wt, "add", "c.txt")
        git(self.wt, "commit", "-q", "-m", "three")
        self.scan()
        git(self.root, "merge", "-q", "--no-ff", "-m", "merge feat-a", "feat-a")
        git(self.root, "worktree", "remove", "--force", self.wt)
        git(self.root, "branch", "-D", "feat-a")
        write(self.wtf, "")
        ends = [m for m in self.scan() if m["type"] == "site_end"]
        self.assertEqual([e["how"] for e in ends], ["merged"])

    def test_human_direct_site(self):
        write(self.wtf, "%s | task manager, human-direct | task: (ask the human) | since x\n" % self.wt)
        site = [m for m in self.scan() if m["type"] == "site"][0]
        self.assertTrue(site["human"])
        self.assertEqual(site["module"], "wt-a")

    def test_lead_in_the_worktree_uses_the_site_office(self):
        self.register()
        self.scan()
        site = self.terr_view(snapshot(self.st)[0]["world"])["sites"][0]
        feed(self.st, "PostToolUse", "tm1", self.ident, role="task-manager", wt=self.wt)
        spawn = [m for m in drain(self.client) if m["type"] == "spawn" and m["id"] == "s:tm1"]
        self.assertEqual(len(spawn), 1)
        self.assertEqual(spawn[0]["office"], {"x": site["x"], "z": site["z"]})
        snap, _ = snapshot(self.st)
        tv = self.terr_view(snap["world"])
        self.assertFalse([o for o in tv["offices"] if o.get("lead") == "s:tm1"])
        agent = [a for a in snap["agents"] if a["id"] == "s:tm1"][0]
        self.assertEqual(agent["office"], {"x": site["x"], "z": site["z"]})

    def test_a_site_takes_over_its_live_leads_office(self):
        feed(self.st, "PostToolUse", "tm1", self.ident, role="task-manager", wt=self.wt)
        spawn = [m for m in drain(self.client) if m["type"] == "spawn" and m["id"] == "s:tm1"][0]
        self.assertIsNotNone(spawn["office"])
        self.register()
        site = [m for m in self.scan() if m["type"] == "site"][0]
        self.assertEqual({"x": site["x"], "z": site["z"]}, spawn["office"])
        snap, _ = snapshot(self.st)
        tv = self.terr_view(snap["world"])
        self.assertEqual(len([o for o in tv["offices"] if (o["x"], o["z"]) == (site["x"], site["z"])]), 1)
        agent = [a for a in snap["agents"] if a["id"] == "s:tm1"][0]
        self.assertEqual(agent["office"], spawn["office"])

    def test_lead_outside_any_site_keeps_its_own_office(self):
        self.register()
        self.scan()
        feed(self.st, "PostToolUse", "tm2", self.ident, role="task-manager", wt="")
        tv = self.terr_view(snapshot(self.st)[0]["world"])
        self.assertEqual(len([o for o in tv["offices"] if o.get("lead") == "s:tm2" and o.get("site") == ""]), 1)

    def test_lead_offices_carry_an_empty_site(self):
        feed(self.st, "PostToolUse", "tm3", self.ident, role="task-manager")
        offices = self.terr_view(snapshot(self.st)[0]["world"])["offices"]
        self.assertTrue(offices)
        self.assertTrue(all(o.get("site") == "" for o in offices))

    def test_plain_folder_start_has_no_sites(self):
        plain = os.path.join(self.base, "plain")
        os.mkdir(plain)
        st = ac.CityState(decisions_path=os.path.join(self.base, "d2.jsonl"), world_path=None,
                          plans=ac.load_plans(), count_fn=lambda i: 0,
                          balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}},
                          start_repo=os.path.realpath(plain))
        st.scan_sites()

    def test_a_second_repo_territory_is_scanned_too(self):
        other = os.path.join(self.base, "other")
        os.mkdir(other)
        o_root, o_wt = make_repo(other)
        o_ident = os.path.join(o_root, ".git")
        feed(self.st, "UserPromptSubmit", "g9", o_ident)
        drain(self.client)
        write(os.path.join(o_root, "agent_worktree.txt"), "%s | other-a | idle | since x\n" % o_wt)
        sites = [m for m in self.scan() if m["type"] == "site"]
        self.assertEqual([(s["terr"], s["status"]) for s in sites], [(ac.territory_id(o_ident), "idle")])

    def test_scan_is_cheap_when_nothing_changed(self):
        self.register()
        self.scan()
        t0 = time.monotonic()
        for _ in range(50):
            self.st.scan_sites()
        self.assertLess((time.monotonic() - t0) / 50, 0.02)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

PAGE_REQUIRED = ("apply", "update", "sites", "siteList", "siteRoad", "siteDecor", "topCounts",
                 "SITE_MERGE_SEC", "SITE_PACK_SEC", "DEMO_SITES", "landState")


def page_view():
    views = plan_views()
    return views[sorted(views)[0]]


SITE_DRIVER = r"""
const V = JSON.parse(JSON.stringify(__payload.view)), T = V.territories[0], tid = T.id;
function buildLand(view){ landState(view); }
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


class TestPageSites(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = run_sim(SITE_DRIVER, {"view": page_view()}, PAGE_REQUIRED)

    def keys(self, items):
        return [d["key"] for d in items]

    def test_snapshot_takes_the_views_sites(self):
        self.assertEqual(self.out["afterSnap"], [{"id": "wt:1", "terr": self.out["tid"], "phase": "live",
                                                  "branch": "feat-a"}])

    def test_fence_around_the_office(self):
        fence = [d for d in self.out["working"] if d["key"] == "roads/construction-fence"]
        self.assertGreaterEqual(len(fence), 4)
        cx, cz = self.out["office"]["x"] + .5, self.out["office"]["z"] + .5
        for d in fence:
            dist = ((d["x"] - cx) ** 2 + (d["z"] - cz) ** 2) ** .5
            self.assertTrue(1.0 <= dist <= 3.0, dist)
        self.assertTrue(any(d["x"] < cx for d in fence) and any(d["x"] > cx for d in fence))
        self.assertTrue(any(d["z"] < cz for d in fence) and any(d["z"] > cz for d in fence))

    def test_branch_sign(self):
        signs = [d for d in self.out["working"] if d["key"] == "survival/signpost-single"]
        self.assertEqual([d["text"] for d in signs], ["feat-a"])

    def test_light_and_scaffold_by_status(self):
        def light(items):
            return [d["on"] for d in items if d["key"] == "roads/construction-light"]
        self.assertEqual(light(self.out["working"]), [True])
        self.assertEqual(light(self.out["final"]), [True])
        self.assertEqual(light(self.out["idleStalledHuman"]), [False])
        self.assertIn("survival/structure", self.keys(self.out["working"]))
        self.assertNotIn("survival/structure", self.keys(self.out["final"]))
        self.assertNotIn("survival/structure", self.keys(self.out["idleStalledHuman"]))

    def test_stalled_and_human_marks(self):
        k = self.keys(self.out["idleStalledHuman"])
        self.assertIn("roads/construction-barrier", k)
        self.assertIn("particles/smoke_01", k)
        flags = [d for d in self.out["idleStalledHuman"] if d["key"] == "forest/flag"]
        self.assertEqual([d["label"] for d in flags], ["亲自带"])
        calm = self.keys(self.out["working"])
        self.assertNotIn("roads/construction-barrier", calm)
        self.assertNotIn("particles/smoke_01", calm)
        self.assertNotIn("forest/flag", calm)

    def test_stalled_count_only_when_any(self):
        labels = [c[0] for c in self.out["counts"]]
        self.assertEqual(labels[:4], ["干活", "找总督", "休息", "建成"])
        self.assertIn(["卡住的工地", 1], self.out["counts"])
        self.assertNotIn("卡住的工地", [c[0] for c in self.out["countsCalm"]])

    def test_merge_lays_a_road_then_the_site_goes(self):
        self.assertIsNone(self.out["roadBefore"])
        self.assertEqual(self.out["phaseAfterEnd"], "merging")
        self.assertNotIn("roads/construction-fence", self.keys(self.out["mergingDecor"]))
        r0, r1 = self.out["road0"], self.out["road1"]
        self.assertIsNotNone(r0)
        cx, cz = self.out["office"]["x"] + .5, self.out["office"]["z"] + .5
        self.assertLessEqual(((r0["from"]["x"] - cx) ** 2 + (r0["from"]["y"] - cz) ** 2) ** .5, 1.6)
        hx, hz = self.out["hall"]["x"], self.out["hall"]["z"]
        self.assertLessEqual(((r0["to"]["x"] - hx) ** 2 + (r0["to"]["y"] - hz) ** 2) ** .5, 1.8)
        self.assertLess(r0["p"], r1["p"])
        self.assertTrue(0 <= r0["p"] <= 1 and 0 <= r1["p"] <= 1)
        self.assertTrue(self.out["goneAfterMerge"])
        self.assertTrue(3 <= self.out["mergeSec"] <= 12 and 3 <= self.out["packSec"] <= 12)

    def test_removed_site_packs_up(self):
        self.assertEqual(self.out["packPhase"], "packing")
        self.assertEqual(self.out["packDecor"], [])
        self.assertIsNone(self.out["packRoad"])
        self.assertTrue(self.out["goneAfterPack"])

    def test_a_world_without_a_live_site_drops_it(self):
        self.assertTrue(self.out["liveDroppedByWorld"])

    def test_demo_has_a_stalled_and_a_human_site(self):
        demo = self.out["demo"]
        self.assertGreaterEqual(len(demo), 2)
        self.assertTrue(any(s["stalled"] for s in demo))
        self.assertTrue(any(s["human"] for s in demo))


class TestPageSiteAssets(unittest.TestCase):

    def test_models_listed_and_on_disk(self):
        text = page()
        for key in ("roads/construction-fence", "roads/construction-light", "roads/construction-barrier",
                    "survival/signpost-single"):
            with self.subTest(key=key):
                self.assertIn("'%s'" % key, text)
                self.assertTrue(os.path.exists(os.path.join(ASSETS, key + ".glb")))

    def test_smoke_sprite_and_its_licence(self):
        self.assertTrue(os.path.exists(os.path.join(ASSETS, "particles", "smoke_01.png")))
        with open(os.path.join(ASSETS, "particles", "License.txt"), encoding="utf-8") as fh:
            self.assertIn("CC0", fh.read())
        self.assertIn("particles/smoke_01", page())

    def test_render_stats_uses_top_counts(self):
        from test_agent_city_people import function_source
        self.assertIn("topCounts()", function_source("renderStats") or "")


if __name__ == "__main__":
    unittest.main()
