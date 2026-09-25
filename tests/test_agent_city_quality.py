"""Failing tests for city-quality and city-levelups (requirements/city.md,
Quality and Growth).

CONTRACT

  Hook (bin/agent-city-hook.sh)
    A 17th key "file", last, after "wt": for a PostToolUse of Edit, Write,
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
        the "<root>/.git" identity; a file that cannot be read is "good";
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
      the building goes; else q = the worst combine_quality of those files
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
        self.assertEqual(row["kind"], "other")

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

    def test_file_is_the_seventeenth_and_last_key(self):
        row = self.row(self.root, path=os.path.join(self.root, "a.py"))
        self.assertEqual(len(row), 17)
        self.assertEqual(list(row)[-3:], ["ask", "wt", "file"])


# ---------------------------------------------------------------------------
# Server: measuring
# ---------------------------------------------------------------------------

class TestFileQuality(unittest.TestCase):

    def test_small_clean_file_is_good(self):
        q = ac.file_quality("def a():\n    return 1\n\nx = a()\n")
        self.assertEqual(q["lines"], 4)
        self.assertEqual(q["score"], "good")

    def test_long_python_function(self):
        q = ac.file_quality(py_fn(100))
        self.assertGreaterEqual(q["long_fn"], 100)
        self.assertLessEqual(q["long_fn"], 102)
        self.assertEqual(q["score"], "fair")

    def test_long_js_function_is_poor(self):
        q = ac.file_quality(js_fn(250))
        self.assertGreaterEqual(q["long_fn"], 250)
        self.assertEqual(q["score"], "poor")

    def test_arrow_and_method_starts(self):
        text = "const f = (a) => {\n" + "  a++;\n" * 90 + "};\n"
        self.assertGreaterEqual(ac.file_quality(text)["long_fn"], 90)
        text = "  save(x) {\n" + "    x++;\n" * 85 + "  }\n"
        self.assertGreaterEqual(ac.file_quality(text)["long_fn"], 85)

    def test_nesting(self):
        self.assertGreaterEqual(ac.file_quality(nested_py(7))["depth"], 7)
        self.assertEqual(ac.file_quality(nested_py(7))["score"], "fair")
        self.assertEqual(ac.file_quality(nested_py(10))["score"], "poor")
        braces = "".join("{\n" for _ in range(9)) + "x;\n" + "".join("}\n" for _ in range(9))
        self.assertGreaterEqual(ac.file_quality(braces)["depth"], 9)

    def test_size(self):
        self.assertEqual(ac.file_quality(flat(600))["score"], "fair")
        self.assertEqual(ac.file_quality(flat(1600))["score"], "poor")
        self.assertEqual(ac.file_quality(flat(400))["score"], "good")

    def test_duplicates(self):
        block = "".join("value_%d = compute(%d)\n" % (i, i) for i in range(10))
        texts = {"a.py": "one = 1\n" + block, "b.py": block + "two = 2\n", "c.py": flat(30)}
        self.assertEqual(ac.duplicates(texts), {"a.py", "b.py"})
        short = "".join("value_%d = compute(%d)\n" % (i, i) for i in range(5))
        self.assertEqual(ac.duplicates({"a.py": short, "b.py": short}), set())
        self.assertEqual(ac.duplicates({"a.py": block + "mid = 0\n" + block}), {"a.py"})

    def test_short_lines_are_skipped_not_counted(self):
        block = "".join("value_%d = compute(%d)\n}\n\n" % (i, i) for i in range(9))
        self.assertEqual(ac.duplicates({"a.py": block, "b.py": block}), {"a.py", "b.py"})

    def test_combine(self):
        self.assertEqual(ac.combine_quality("good", False, False), "good")
        self.assertEqual(ac.combine_quality("good", True, False), "fair")
        self.assertEqual(ac.combine_quality("good", True, True), "poor")
        self.assertEqual(ac.combine_quality("fair", False, True), "poor")
        self.assertEqual(ac.combine_quality("poor", True, True), "poor")

    def test_wrong_district_is_stable(self):
        name = pick_name(True)
        self.assertTrue(ac.wrong_district(name))
        self.assertFalse(ac.wrong_district(pick_name(False)))

    def test_hot_counts(self):
        base = tempfile.mkdtemp(prefix="city_q_hot_")
        try:
            root, _ = make_repo(base)
            for i in range(3):
                with open(os.path.join(root, "a.txt"), "a") as fh:
                    fh.write("%d\n" % i)
                git(root, "commit", "-q", "-am", "c%d" % i)
            counts = ac.hot_counts(root)
            self.assertEqual(counts.get("a.txt"), 4)
        finally:
            shutil.rmtree(base, ignore_errors=True)


# ---------------------------------------------------------------------------
# Server: buildings
# ---------------------------------------------------------------------------

class BuildCase(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_q_state_")
        self.root, self.wt = make_repo(self.base)
        self.ident = os.path.join(self.root, ".git")
        self.terr = ac.territory_id(self.ident)
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"),
                               plans=ac.load_plans(), count_fn=lambda i: 0,
                               balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}},
                               start_repo=self.ident)
        self.snap, self.client = snapshot(self.st)
        self.st.feed_line(self.line("tm", tool="Read"), 1000.0)
        drain(self.client)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def line(self, sid, aid="", kind="", file="", tool="Edit", wt=""):
        return {"ev": "PostToolUse", "sid": sid, "aid": aid, "at": "worker" if aid else "", "tool": tool,
                "nt": "", "proj": "app", "role": "", "desc": "", "sub": "", "q": "", "klen": "",
                "repo": self.ident, "kind": kind, "ask": "", "wt": wt, "file": file}

    def put(self, rel, text, where=None):
        path = os.path.join(where or self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def edit(self, aid, rel, kind="other", wt=""):
        self.st.feed_line(self.line("tm", aid=aid, kind=kind, file=rel, wt=wt), 1000.0)
        return drain(self.client)

    def plan(self):
        pid = self.st.world["territories"][self.ident]["plan"]
        return next(p for p in ac.load_plans() if p["id"] == pid)

    def district(self, plot):
        return self.plan()["plots"][plot][2]

    def view_building(self, plot):
        snap, _ = snapshot(self.st)
        tv = [t for t in snap["world"]["territories"] if t["id"] == self.terr][0]
        found = [b for b in tv["buildings"] if b["plot"] == plot]
        return found[0] if found else None


class TestBuildingsRememberFiles(BuildCase):

    def test_build_carries_quality_home_files_level(self):
        self.put("src/a.py", "x = 1\n")
        ev = [e for e in self.edit("w1", "src/a.py") if e["type"] == "build"]
        self.assertEqual(len(ev), 1)
        b = ev[0]
        self.assertEqual((b["q"], b["home"], b["files"], b["lv"]), ("good", True, ["src/a.py"], 0))
        self.assertIsInstance(b["name"], str)
        self.assertEqual(self.district(b["plot"]), "house")
        vb = self.view_building(b["plot"])
        for key in ("q", "home", "files", "hist", "lv", "name"):
            self.assertIn(key, vb)

    def test_same_owner_new_file_is_a_touch(self):
        self.put("src/a.py", "x = 1\n")
        self.put("src/b.py", "y = 1\n")
        plot = [e for e in self.edit("w1", "src/a.py") if e["type"] == "build"][0]["plot"]
        ev = self.edit("w1", "src/b.py")
        self.assertEqual([e["type"] for e in ev if e["type"] in ("build", "touch")], ["touch"])
        self.assertEqual(self.view_building(plot)["files"], ["src/b.py", "src/a.py"])

    def test_another_owner_on_a_known_file_is_a_touch_with_history(self):
        self.put("src/a.py", "x = 1\n")
        plot = [e for e in self.edit("w1", "src/a.py") if e["type"] == "build"][0]["plot"]
        ev = self.edit("w2", "src/a.py")
        touch = [e for e in ev if e["type"] == "touch"]
        self.assertEqual(len(touch), 1)
        self.assertEqual((touch[0]["plot"], touch[0]["terr"]), (plot, self.terr))
        self.assertFalse([e for e in ev if e["type"] in ("build", "levelup", "noplot")])
        hist = self.view_building(plot)["hist"]
        self.assertEqual(len(hist), 1)
        self.assertIn("by", hist[0])

    def test_files_are_capped(self):
        plot = None
        for i in range(15):
            self.put("src/m%d.py" % i, "x = %d\n" % i)
            for e in self.edit("w1", "src/m%d.py" % i):
                if e["type"] == "build":
                    plot = e["plot"]
        files = self.view_building(plot)["files"]
        self.assertEqual(len(files), 12)
        self.assertEqual(files[0], "src/m14.py")

    def test_poor_file_picked_wrong_goes_to_another_district(self):
        name = pick_name(True)
        self.put(name, flat(1600))
        b = [e for e in self.edit("w1", name) if e["type"] == "build"][0]
        self.assertEqual((b["q"], b["home"]), ("poor", False))
        self.assertNotEqual(self.district(b["plot"]), "house")

    def test_poor_file_not_picked_stays_home(self):
        name = pick_name(False)
        self.put(name, flat(1600))
        b = [e for e in self.edit("w1", name) if e["type"] == "build"][0]
        self.assertEqual((b["q"], b["home"]), ("poor", True))
        self.assertEqual(self.district(b["plot"]), "house")

    def test_quality_read_from_the_worktree(self):
        self.put("src/w.py", flat(1600), where=self.wt)
        b = [e for e in self.edit("w1", "src/w.py", wt=self.wt) if e["type"] == "build"][0]
        self.assertEqual(b["q"], "poor")

    def test_old_buildings_get_defaults(self):
        t = self.st.world["territories"][self.ident]
        k = ac.open_plots(self.plan(), t["peak"])[0]
        t["buildings"].append({"plot": k, "type": self.district(k), "owner": "old", "by": "worker", "at": 1.0})
        self.st._invalidate_view()
        vb = self.view_building(k)
        self.assertEqual((vb["files"], vb["hist"], vb["q"], vb["home"], vb["lv"], vb["name"]),
                         ([], [], "good", True, 0, ""))


class TestRequality(BuildCase):

    def test_improved_file_moves_home(self):
        name = pick_name(True)
        self.put(name, flat(1600))
        first = [e for e in self.edit("w1", name) if e["type"] == "build"][0]
        self.put(name, "x = 1\n")
        self.st.requality(self.ident)
        ev = drain(self.client)
        q = [e for e in ev if e["type"] == "quality"]
        self.assertEqual([(e["plot"], e["q"]) for e in q], [(first["plot"], "good")])
        mv = [e for e in ev if e["type"] == "move"]
        self.assertEqual(len(mv), 1)
        self.assertEqual((mv[0]["from"], mv[0]["home"]), (first["plot"], True))
        self.assertEqual(self.district(mv[0]["plot"]), "house")
        vb = self.view_building(mv[0]["plot"])
        self.assertTrue(vb["home"])
        self.assertIsNone(self.view_building(first["plot"]))

    def test_worse_file_changes_quality_only(self):
        self.put("src/a.py", "x = 1\n")
        plot = [e for e in self.edit("w1", "src/a.py") if e["type"] == "build"][0]["plot"]
        self.put("src/a.py", flat(700))
        self.st.requality(self.ident)
        ev = drain(self.client)
        self.assertEqual([(e["type"], e.get("q")) for e in ev], [("quality", "fair")])
        self.assertEqual(self.view_building(plot)["q"], "fair")

    def test_no_change_no_events(self):
        self.put("src/a.py", "x = 1\n")
        self.edit("w1", "src/a.py")
        self.st.requality(self.ident)
        self.assertEqual(drain(self.client), [])

    def test_duplicates_across_buildings(self):
        block = "".join("value_%d = compute(%d)\n" % (i, i) for i in range(10))
        self.put("src/a.py", block)
        self.put("tests/test_b.py", block)
        pa = [e for e in self.edit("w1", "src/a.py") if e["type"] == "build"][0]["plot"]
        pb = [e for e in self.edit("w2", "tests/test_b.py", kind="test") if e["type"] == "build"][0]["plot"]
        self.st.requality(self.ident)
        got = {(e["plot"], e["q"]) for e in drain(self.client) if e["type"] == "quality"}
        self.assertEqual(got, {(pa, "fair"), (pb, "fair")})

    def test_all_files_gone_demolishes(self):
        self.put("src/a.py", "x = 1\n")
        plot = [e for e in self.edit("w1", "src/a.py") if e["type"] == "build"][0]["plot"]
        os.remove(os.path.join(self.root, "src", "a.py"))
        self.st.requality(self.ident)
        ev = drain(self.client)
        self.assertEqual([(e["type"], e["plot"]) for e in ev if e["type"] == "demolish"], [("demolish", plot)])
        self.assertIsNone(self.view_building(plot))

    def test_one_file_left_keeps_the_building(self):
        self.put("src/a.py", "x = 1\n")
        self.put("src/b.py", "y = 1\n")
        plot = [e for e in self.edit("w1", "src/a.py") if e["type"] == "build"][0]["plot"]
        self.edit("w1", "src/b.py")
        os.remove(os.path.join(self.root, "src", "a.py"))
        self.st.requality(self.ident)
        self.assertFalse([e for e in drain(self.client) if e["type"] == "demolish"])
        self.assertIsNotNone(self.view_building(plot))

    def test_a_file_only_in_a_live_worktree_stays(self):
        write(os.path.join(self.root, "agent_worktree.txt"), "%s | city-a | working | since x\n" % self.wt)
        self.st.scan_sites()
        self.put("src/w.py", "x = 1\n", where=self.wt)
        plot = [e for e in self.edit("w1", "src/w.py", wt=self.wt) if e["type"] == "build"][0]["plot"]
        drain(self.client)
        self.st.requality(self.ident)
        self.assertFalse([e for e in drain(self.client) if e["type"] == "demolish"])
        self.assertIsNotNone(self.view_building(plot))

    def test_recount_calls_requality(self):
        import inspect
        self.assertIn("requality", inspect.getsource(ac.CityState.recount))


class TestLevelUps(BuildCase):

    def test_full_district_levels_up_then_says_no_plot(self):
        self.put("src/a.py", "x = 1\n")
        first = [e for e in self.edit("w1", "src/a.py") if e["type"] == "build"][0]
        levels = []
        for i, w in enumerate(("w2", "w3", "w4")):
            self.put("src/l%d.py" % i, "x = 1\n")
            ev = self.edit(w, "src/l%d.py" % i)
            self.assertFalse([e for e in ev if e["type"] in ("build", "noplot")])
            up = [e for e in ev if e["type"] == "levelup"]
            self.assertEqual(len(up), 1)
            self.assertEqual((up[0]["plot"], up[0]["terr"]), (first["plot"], self.terr))
            levels.append(up[0]["lv"])
        self.assertEqual(levels, [1, 2, 3])
        vb = self.view_building(first["plot"])
        self.assertEqual(vb["lv"], 3)
        self.assertIn("src/l2.py", vb["files"])
        self.put("src/l9.py", "x = 1\n")
        ev = self.edit("w5", "src/l9.py")
        self.assertEqual([e["type"] for e in ev if e["type"] in ("build", "levelup", "noplot")], ["noplot"])

    def test_the_leveling_owner_then_touches(self):
        self.put("src/a.py", "x = 1\n")
        self.put("src/b.py", "x = 1\n")
        self.put("src/c.py", "x = 1\n")
        plot = [e for e in self.edit("w1", "src/a.py") if e["type"] == "build"][0]["plot"]
        self.assertEqual([e["lv"] for e in self.edit("w2", "src/b.py") if e["type"] == "levelup"], [1])
        ev = self.edit("w2", "src/c.py")
        self.assertEqual([e["type"] for e in ev if e["type"] in ("build", "levelup", "noplot", "touch")], ["touch"])
        self.assertEqual(self.view_building(plot)["lv"], 1)

    def test_lowest_level_oldest_first(self):
        t = self.st.world["territories"][self.ident]
        t["peak"] = t["lines"] = 200000
        self.st._invalidate_view()
        houses = [k for k in ac.open_plots(self.plan(), t["peak"]) if self.district(k) == "house"]
        self.assertGreaterEqual(len(houses), 2)
        plots = []
        for i in range(len(houses)):
            self.put("src/h%d.py" % i, "x = 1\n")
            plots.append([e for e in self.edit("h%d" % i, "src/h%d.py" % i) if e["type"] == "build"][0]["plot"])
        ups = []
        for i in range(len(houses) + 1):
            self.put("src/u%d.py" % i, "x = 1\n")
            ups += [(e["plot"], e["lv"]) for e in self.edit("u%d" % i, "src/u%d.py" % i) if e["type"] == "levelup"]
        want = [(p, 1) for p in plots] + [(plots[0], 2)]
        self.assertEqual(ups, want)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

PAGE_REQUIRED = ("apply", "update", "buildings", "buildingPose", "levelScale", "buildingInfo",
                 "MOVE_SEC", "DEMOLISH_SEC", "occupied", "landState")

Q_DRIVER = r"""
const V = JSON.parse(JSON.stringify(__payload.view)), T = V.territories[0], tid = T.id;
function buildLand(view){ landState(view); }
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


class TestPageQuality(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = run_sim(Q_DRIVER, {"view": q_view()}, PAGE_REQUIRED)

    def test_snapshot_fields_and_defaults(self):
        self.assertEqual(self.out["snap0"], {"q": "poor", "home": False, "files": ["src/a.py"], "lv": 0,
                                             "name": "设置页 API"})
        self.assertEqual(self.out["snap1"], {"q": "good", "home": True, "files": [], "hist": [], "lv": 0,
                                             "name": ""})

    def test_pose_by_quality(self):
        for row in self.out["poses"]["good"]:
            self.assertEqual((row["dx"], row["dz"], row["ry"]), (0, 0, 0))
        for row in self.out["poses"]["fair"]:
            self.assertTrue(.05 <= abs(row["ry"]) <= .2, row)
            self.assertLessEqual((row["dx"] ** 2 + row["dz"] ** 2) ** .5, .15)
        for row in self.out["poses"]["poor"]:
            self.assertTrue(.25 <= abs(row["ry"]) <= .5, row)
            self.assertTrue(.15 <= (row["dx"] ** 2 + row["dz"] ** 2) ** .5 <= .35, row)
        for q in ("good", "fair", "poor"):
            self.assertTrue(all(r["same"] for r in self.out["poses"][q]))
        self.assertGreater(len({round(r["ry"], 4) for r in self.out["poses"]["poor"]}), 1,
                           "not every poor building leans the same way")

    def test_touch_quality_levelup(self):
        self.assertEqual(self.out["touched"], ["fast-lane-deputy"])
        self.assertEqual(self.out["q1"], "fair")
        self.assertEqual(self.out["lv1"], 2)

    def test_level_scale(self):
        s = self.out["scales"]
        self.assertEqual((s[0]["sy"], s[0]["sxz"]), (1, 1))
        for a, b in zip(s, s[1:]):
            self.assertGreater(b["sy"], a["sy"])
            self.assertGreater(b["sxz"], a["sxz"])
            self.assertGreater(b["sy"] - a["sy"], b["sxz"] - a["sxz"])
        self.assertLessEqual(s[3]["sy"], 2.6)

    def test_building_info(self):
        i0, i1 = self.out["info0"], self.out["info1"]
        self.assertEqual((i0["quality"], i0["misplaced"], i0["files"], i0["level"], i0["name"]),
                         ("有点乱", True, ["src/a.py"], 0, "设置页 API"))
        self.assertEqual((i1["quality"], i1["misplaced"], i1["level"]), ("还行", False, 2))
        self.assertEqual([h["by"] for h in i1["hist"]], ["fast-lane-deputy"])

    def test_move_after_the_builders(self):
        m, t = self.out["moved"], self.out["target"]
        self.assertEqual((m["plot"], m["gx"], m["gy"], m["home"]), (t["k"], t["x"], t["z"], True))
        self.assertTrue(m["occNew"])
        self.assertFalse(m["occOld"])
        self.assertTrue(2 <= self.out["moveSec"] <= 10)

    def test_demolish(self):
        self.assertTrue(self.out["demolished"])
        self.assertTrue(1 <= self.out["demolishSec"] <= 8)

    def test_build_event_fields(self):
        self.assertEqual(self.out["built"], {"q": "fair", "home": True, "files": ["ui/x.html"], "lv": 0})

    def test_card_uses_building_info(self):
        text = page()
        self.assertGreaterEqual(text.count("buildingInfo("), 2)
        for word in ("整齐", "还行", "有点乱", "放错区了"):
            self.assertIn(word, text)


if __name__ == "__main__":
    unittest.main()
