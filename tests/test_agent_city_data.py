"""Failing tests: city-data, the server half (owner, 2026-10-02; approved mock mock/city-data-mock.html).

Two things move from the page to the server (requirements/city.md: Growth "Building names",
Persistence "History"):
  1 every building gets a stable, meaningful name the server stores in world.json;
  2 the history in a person's panel is kept by the server per person, so a reload, a second tab and
    a server restart show the same history.
The page half is tests/test_agent_city_data_page.py.

CONTRACT (bin/agent_city.py)

  Names
  N1  name_subject(files) -> str. What the files point at, "" when nothing does.
      One file: its last path part ("/" or "\\" both split) without its extension (the last ".x" only),
      then without a "test_" prefix, or else a "_test", ".test" or ".spec" ending (case does not matter).
      A too-common name (NAME_COMMON_STEMS, lower case: index main __init__ init mod app util utils readme
      test tests spec setup conftest page layout route view style styles; also an empty name) gives its
      folder instead; a too-common folder (NAME_COMMON_DIRS: src lib test tests bin app pkg internal cmd
      web docs scripts components pages) gives the folder above it; none left -> "" for that file.
      Several files: the subject most of them point at; a tie goes to the OLDEST file. FILES is newest
      first (as a building keeps them), so the oldest is the last one.
      Longer than 24 characters -> the first 23 and "…". Never a "/" or "\\" in it.
  N2  building_name(btype, files, task, plot, lang="zh", taken=()) -> str, never "".
      a  a subject -> "<subject> <kind word>". Kind word by building type, zh / en:
         tower 测试 / tests, shop 页面 / page, workshop 脚本 / script, library 文档 / docs,
         house 模块 / module.
      b  else TASK when it can be a name: text after strip(), not a path (no "/" or "\\", no ending like
         ".py": a dot and 1 to 5 letters or digits), not a bare role word (worker, task-manager,
         fast-lane-deputy, merge-deputy, other, session). Longer than 24 characters -> 23 and "…".
      c  else an address: zh "<district> <plot + 1> 号" (住宅区 商业街 测试区 工坊区 图书馆区 for house
         shop tower workshop library), en "<district> no. <plot + 1>" (Homes Shops Tests Workshops Library).
      Never the bare type word. A name that is in TAKEN (the names used in that land) gets " 2", then
      " 3", ... until it is free.
  N3  name_world(world, lang="zh") -> int. Names every building of WORLD that has no name (no "name" key,
      None or ""), land by land, in the order the buildings are listed; TAKEN = the names that land has.
      A building that has a name is never touched. Returns how many it named (0 the second time).
  N4  CityState: a new building has its name when it is built: in the "build" event, in the view (snapshot,
      "world") and in world.json. The builder's task (the reducer's agent "task") is the TASK of N2.
      The name never changes later (a touch, another file, a restart). At start (after load_world) the
      server runs name_world and, when that named anything, saves world.json at once.
      The cloud picture is unchanged: cloud_clean still sends "name": "".

  History
  H1  HIST_KEEP = 200, HIST_GONE_SEC = 86400.
  H2  class History(path=None, keep=HIST_KEEP, gone_sec=HIST_GONE_SEC, now=None)
      note(ev, at) -> None, or {"id", "line", "fold"}: what one page event adds to the history of the
        person ev["id"]. AT = epoch seconds (time.time()). Events:
          spawn    {"k": "started", "task": ev["task"]}
          tool     {"k": "steps", "steps": [step]}, step = the event's "tool", "name" and, when it has
                   them, "file" and "desc". Tools in a row share ONE line: a step the line already holds
                   adds nothing (None); a new step goes to the end, at most 3 (the oldest goes); the
                   line keeps the "at" of its first step; the answer then has "fold": True (this line
                   replaces that person's last line). Any other line in between ends the run.
          stuck    {"k": "stuck", "question": ..., "tool": ...}
          answer   {"k": "qa", "question", "tool"} of that person's last "stuck" ("" when there was
                   none), "ok": ev["ok"], and "answer": ev["answer"] when the event carries a text
          relay    to "lead" -> {"k": "toLead"}; to "governor" -> {"k": "toGov"}
          waiting  {"k": "waiting"}      done  {"k": "done"}      leave  {"k": "left"}
        Every line has "at". "fold" is False for a new line. Any other type, or no str "id" -> None.
        "leave" marks the person gone at AT; a later "spawn" of the same id brings it back.
      lines(pid) -> that person's lines, oldest first (a copy; [] when unknown). Never more than KEEP:
        the oldest go.
      sweep(now) -> drops every person gone more than GONE_SEC before NOW. A person who never left stays.
      PATH (history.jsonl): every answer of note() is ONE appended row (the file is never rewritten per
        line); the file is made with mode 0600. A new History(path) reads it back: the same lines, folds
        applied, at most KEEP per person, a person gone more than GONE_SEC before NOW (default
        time.time()) dropped; then it writes the file compact (tmp + replace, 0600). A missing file or a
        broken row never raises (the row is skipped).
  H3  CityState(history_path=None, ...): self.history = History(history_path).
      _broadcast(ev): after EV went out, self.history.note(ev, time.time()); an answer goes out to the
        same pages as {"type": "hist", "id", "line", "fold"}.
      The snapshot has "hist": {id: lines} for every agent it lists.
      history_view(pid) -> self.history.lines(pid).   sweep_history(now) -> self.history.sweep(now).
  H4  Local only: "hist" is on CLOUD_DROP, and cloud_clean(snapshot) has no "hist" key.
  H5  cmd_serve passes history_path = <city dir>/history.jsonl; recount_loop calls
      city.sweep_history(time.time()) (guarded like its other calls).
"""

import inspect
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))

import agent_city as ac  # noqa: E402
from test_agent_city_worktrees import make_repo, drain, snapshot  # noqa: E402
from cityhelp import Mains  # noqa: E402

KIND_ZH = {"tower": "测试", "shop": "页面", "workshop": "脚本", "library": "文档", "house": "模块"}
KIND_EN = {"tower": "tests", "shop": "page", "workshop": "script", "library": "docs", "house": "module"}
BARE = ("住宅", "商店", "测试塔", "工坊", "图书馆", "House", "Shop", "Tower", "Workshop", "Library")


# ---------------------------------------------------------------------------
# N1 the subject
# ---------------------------------------------------------------------------

class TestNameSubject(unittest.TestCase):

    def test_one_file(self):
        for files, want in (
            (["web/checkout/form.tsx"], "form"),
            (["web/checkout/page.tsx"], "checkout"),
            (["tests/test_checkout.py"], "checkout"),
            (["tests/Test_Checkout.py"], "Checkout"),
            (["web/cart.test.ts"], "cart"),
            (["src/cart.spec.js"], "cart"),
            (["pkg/orders_test.go"], "orders"),
            (["api/payment/__init__.py"], "payment"),
            (["docs/setup/README.md"], "setup"),
            (["web/login/index.tsx"], "login"),
            (["web/components/CartButton.tsx"], "CartButton"),
            (["bin/deploy.sh"], "deploy"),
            (["docs/api.md"], "api"),
            (["web\\checkout\\page.tsx"], "checkout"),
            (["api/v2/users.py"], "users"),
            (["shop/.gitignore"], "shop"),
        ):
            with self.subTest(files=files):
                self.assertEqual(ac.name_subject(files), want)

    def test_nothing_to_point_at(self):
        for files in ([], ["src/index.ts"], ["README.md"], ["lib/utils.py"], ["web/pages/index.tsx"], ["main.py"]):
            with self.subTest(files=files):
                self.assertEqual(ac.name_subject(files), "")

    def test_most_files_win(self):
        files = ["web/checkout/form.tsx", "web/checkout/page.tsx", "web/checkout/index.tsx"]
        self.assertEqual(ac.name_subject(files), "checkout", "two files point at checkout, one at form")

    def test_a_tie_goes_to_the_oldest_file(self):
        self.assertEqual(ac.name_subject(["api/orders_repo.py", "api/orders.py"]), "orders",
                         "files are newest first: the oldest is the last one")
        self.assertEqual(ac.name_subject(["api/orders.py", "api/orders_repo.py"]), "orders_repo")

    def test_a_long_name_is_cut(self):
        got = ac.name_subject(["src/" + "a" * 40 + ".py"])
        self.assertEqual(got, "a" * 23 + "…")
        self.assertEqual(ac.name_subject(["src/" + "b" * 24 + ".py"]), "b" * 24, "24 characters fit")

    def test_never_a_path(self):
        for files in (["a/b/c/d.py"], ["a\\b\\c.py"], ["x/y/index.js"]):
            got = ac.name_subject(files)
            self.assertNotIn("/", got)
            self.assertNotIn("\\", got)


# ---------------------------------------------------------------------------
# N2 the name
# ---------------------------------------------------------------------------

class TestBuildingName(unittest.TestCase):

    def test_subject_and_kind_word(self):
        f = ["web/checkout/page.tsx"]
        for btype, word in KIND_ZH.items():
            with self.subTest(btype=btype):
                self.assertEqual(ac.building_name(btype, f, "", 0), "checkout " + word)
        for btype, word in KIND_EN.items():
            with self.subTest(btype=btype, lang="en"):
                self.assertEqual(ac.building_name(btype, f, "", 0, lang="en"), "checkout " + word)

    def test_the_examples_of_the_mock(self):
        for btype, files, want in (
            ("shop", ["web/checkout/form.tsx", "web/checkout/page.tsx"], "checkout 页面"),
            ("tower", ["tests/test_orders_refund.py", "tests/test_orders.py"], "orders 测试"),
            ("workshop", ["bin/deploy.sh"], "deploy 脚本"),
            ("library", ["docs/api.md"], "api 文档"),
            ("house", ["api/payment/stripe.py", "api/payment/__init__.py"], "payment 模块"),
        ):
            with self.subTest(want=want):
                self.assertEqual(ac.building_name(btype, files, "别的任务", 3), want,
                                 "the files decide, the task is only for a building with no file")

    def test_no_file_uses_the_builders_task(self):
        self.assertEqual(ac.building_name("house", [], "修退款金额", 4), "修退款金额")
        self.assertEqual(ac.building_name("house", ["src/index.ts"], "  修退款金额  ", 4), "修退款金额",
                         "files that point at nothing count as no file")
        self.assertEqual(ac.building_name("house", [], "x" * 30, 4), "x" * 23 + "…")

    def test_a_task_that_cannot_be_a_name_gives_an_address(self):
        for task in ("", "   ", "worker", "task-manager", "fast-lane-deputy", "merge-deputy", "other", "session",
                     "src/a.py", "a\\b", "fix a.py", "notes.md"):
            with self.subTest(task=task):
                self.assertEqual(ac.building_name("house", [], task, 4), "住宅区 5 号")

    def test_the_address_per_district(self):
        zh = {"house": "住宅区", "shop": "商业街", "tower": "测试区", "workshop": "工坊区", "library": "图书馆区"}
        en = {"house": "Homes", "shop": "Shops", "tower": "Tests", "workshop": "Workshops", "library": "Library"}
        for btype in zh:
            with self.subTest(btype=btype):
                self.assertEqual(ac.building_name(btype, [], "", 0), zh[btype] + " 1 号")
                self.assertEqual(ac.building_name(btype, [], "", 11, lang="en"), en[btype] + " no. 12")

    def test_never_empty_never_the_bare_type_word(self):
        for btype in KIND_ZH:
            for files, task in (([], ""), (["README.md"], "worker"), (["a/b.py"], "")):
                for lang in ("zh", "en"):
                    got = ac.building_name(btype, files, task, 2, lang=lang)
                    self.assertTrue(got)
                    self.assertNotIn(got, BARE)

    def test_a_name_used_in_that_land_gets_a_number(self):
        f = ["web/checkout/index.tsx"]
        self.assertEqual(ac.building_name("shop", f, "", 1, taken={"checkout 页面"}), "checkout 页面 2")
        self.assertEqual(ac.building_name("shop", f, "", 1, taken=["checkout 页面", "checkout 页面 2"]),
                         "checkout 页面 3")
        self.assertEqual(ac.building_name("shop", f, "", 1, taken={"orders 页面"}), "checkout 页面")
        self.assertEqual(ac.building_name("house", [], "修退款金额", 1, taken={"修退款金额"}), "修退款金额 2")


# ---------------------------------------------------------------------------
# N3 old buildings get a name once
# ---------------------------------------------------------------------------

def old_world():
    def b(plot, btype, files, **more):
        d = {"plot": plot, "type": btype, "owner": "o%d" % plot, "owners": ["o%d" % plot], "by": "worker",
             "at": 1.0, "files": files, "hist": [], "q": "good", "home": True, "lv": 0}
        d.update(more)
        return d
    return {"v": 1, "order": ["/a/.git", "/b/.git"], "territories": {
        "/a/.git": {"name": "a", "buildings": [
            b(0, "shop", ["web/checkout/page.tsx"]),                 # no "name" key at all
            b(1, "shop", ["web/checkout/index.tsx"], name=""),
            b(2, "house", [], name=None),
            b(3, "tower", ["tests/test_x.py"], name="手起的名字"),
            b(4, "shop", ["web/x/page.tsx"], name="checkout 页面 2"),
        ]},
        "/b/.git": {"name": "b", "buildings": [b(0, "shop", ["web/checkout/page.tsx"], name="")]},
    }}


class TestNameWorld(unittest.TestCase):

    def names(self, world, ident):
        return [x.get("name") for x in world["territories"][ident]["buildings"]]

    def test_names_only_the_nameless(self):
        w = old_world()
        n = ac.name_world(w)
        self.assertEqual(n, 4, "three in land a, one in land b")
        self.assertEqual(self.names(w, "/a/.git"),
                         ["checkout 页面", "checkout 页面 3", "住宅区 3 号", "手起的名字", "checkout 页面 2"],
                         "in list order; a name already in that land (also one of a later building) is taken")
        self.assertEqual(self.names(w, "/b/.git"), ["checkout 页面"], "another land has its own names")

    def test_once(self):
        w = old_world()
        ac.name_world(w)
        before = json.dumps(w, sort_keys=True)
        self.assertEqual(ac.name_world(w), 0)
        self.assertEqual(json.dumps(w, sort_keys=True), before, "a second run changes nothing")

    def test_language(self):
        w = old_world()
        ac.name_world(w, lang="en")
        self.assertEqual(self.names(w, "/a/.git")[:3], ["checkout page", "checkout page 2", "Homes no. 3"])


# ---------------------------------------------------------------------------
# N4 the server names a building when it is built, and keeps the name
# ---------------------------------------------------------------------------

class CityCase(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_data_")
        self.root, self.wt = make_repo(self.base)
        self.ident = os.path.join(self.root, ".git")
        self.terr = ac.territory_id(self.ident)
        self.world_path = os.path.join(self.base, "world.json")
        self.hist_path = os.path.join(self.base, "history.jsonl")
        self.st = self.city()
        self.snap, self.client = snapshot(self.st)
        self.feed("PostToolUse", tool="Read")          # "tm" is the main manager: the governor
        drain(self.client)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def city(self, **more):
        kw = dict(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world_path,
                  plans=ac.load_plans(), count_fn=lambda i: 0,
                  balance_fn=lambda i, r: {"kinds": {}, "bad": [], "files": {}},
                  start_repo=self.ident, main_fn=Mains({self.ident: "tm"}))
        kw.update(more)
        return ac.CityState(decisions_path=kw.pop("decisions_path"), **kw)   # never the owner's real decisions file

    def feed(self, ev, sid="tm", st=None, **f):
        line = {"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "", "nt": "", "proj": "app", "role": "",
                "desc": "", "sub": "", "q": "", "klen": "", "repo": self.ident, "kind": "", "ask": "", "wt": "",
                "file": ""}
        line.update(f)
        if line["aid"] and not line["at"]:
            line["at"] = "worker"
        (st or self.st).feed_line(line, 1000.0)

    def put(self, rel, text="x = 1\n"):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def edit(self, aid, rel, st=None, client=None, **f):
        self.put(rel)
        self.feed("PostToolUse", st=st, aid=aid, tool="Edit", file=rel, **f)
        return drain(client or self.client)

    def view_buildings(self, st=None):
        snap, _ = snapshot(st or self.st)
        return [t for t in snap["world"]["territories"] if t["id"] == self.terr][0]["buildings"]

    def disk_buildings(self):
        with open(self.world_path, encoding="utf-8") as fh:
            return json.load(fh)["territories"][self.ident]["buildings"]


class TestCityNames(CityCase):

    def built(self, events):
        got = [e for e in events if e["type"] == "build"]
        self.assertEqual(len(got), 1, "one building went up: %r" % [e["type"] for e in events])
        return got[0]

    def test_named_when_built_everywhere_the_same(self):
        ev = self.built(self.edit("w1", "web/checkout/page.tsx"))
        want = "checkout " + KIND_ZH[ev["btype"]]
        self.assertEqual(ev["name"], want, "the build event carries the server's name")
        self.assertEqual([b["name"] for b in self.view_buildings()], [want], "a reload (a new snapshot)")
        self.assertEqual([b["name"] for b in self.disk_buildings()], [want], "world.json")

    def test_a_test_file(self):
        ev = self.built(self.edit("w1", "tests/test_checkout.py"))
        self.assertEqual(ev["name"], "checkout " + KIND_ZH[ev["btype"]])

    def test_the_name_never_changes(self):
        first = self.built(self.edit("w1", "web/checkout/page.tsx"))["name"]
        self.assertTrue(first, "it has a name")
        for rel in ("web/orders/list.tsx", "web/orders/item.tsx", "web/orders/index.tsx"):
            self.assertFalse([e for e in self.edit("w1", rel) if e["type"] == "build"], "its own building: a touch")
        self.assertEqual([b["name"] for b in self.view_buildings()], [first],
                         "most files now point at orders, the name stays")
        st2 = self.city()                                    # the server restarts
        self.assertEqual([b["name"] for b in self.view_buildings(st2)], [first])
        self.assertEqual([b["name"] for b in self.disk_buildings()], [first])

    def test_a_second_one_gets_a_number(self):
        t = self.st.world["territories"][self.ident]
        t["peak"] = t["lines"] = 10 ** 6          # a big land: two free plots in one district
        a = self.built(self.edit("w1", "web/checkout/page.tsx"))
        b = self.built(self.edit("w2", "web/checkout/index.tsx"))
        self.assertEqual(a["btype"], b["btype"])
        self.assertEqual(b["name"], a["name"] + " 2")

    def test_english(self):
        st = self.city(lang="en", world_path=os.path.join(self.base, "en.json"))
        _, client = snapshot(st)
        self.feed("PostToolUse", st=st, tool="Read")
        ev = self.built(self.edit("w1", "web/checkout/page.tsx", st=st, client=client))
        self.assertEqual(ev["name"], "checkout " + KIND_EN[ev["btype"]])

    def test_no_file_the_builders_task(self):
        # an old hook line: a "kind", no "file". The worker was sent with a task.
        self.feed("PreToolUse", tool="Agent", sub="worker", desc="修退款金额")
        self.feed("SubagentStart", aid="w9")
        spawn = [e for e in drain(self.client) if e["type"] == "spawn"]
        self.assertEqual([e["task"] for e in spawn], ["修退款金额"], "the test's own setup")
        self.feed("PostToolUse", aid="w9", tool="Edit", kind="other")
        ev = self.built(drain(self.client))
        self.assertEqual(ev["name"], "修退款金额")

    def test_nothing_known_an_address(self):
        self.feed("PostToolUse", aid="w7", tool="Edit", kind="other")   # its task is the bare role word
        ev = self.built(drain(self.client))
        self.assertEqual(ev["name"], "住宅区 %d 号" % (ev["plot"] + 1))

    def test_old_buildings_get_a_name_once_at_start(self):
        self.edit("w1", "web/checkout/page.tsx")
        self.edit("w2", "tests/test_orders.py")
        with open(self.world_path, encoding="utf-8") as fh:
            world = json.load(fh)
        blds = world["territories"][self.ident]["buildings"]
        self.assertEqual(len(blds), 2)
        kinds = [b["type"] for b in blds]
        del blds[0]["name"]                  # a world.json from before this task
        blds[1]["name"] = ""
        with open(self.world_path, "w", encoding="utf-8") as fh:
            json.dump(world, fh)
        st2 = self.city()
        want = ["checkout " + KIND_ZH[kinds[0]], "orders " + KIND_ZH[kinds[1]]]
        self.assertEqual([b["name"] for b in self.disk_buildings()], want, "saved at once, before any event")
        self.assertEqual(sorted(b["name"] for b in self.view_buildings(st2)), sorted(want))
        st3 = self.city()
        self.assertEqual([b["name"] for b in self.disk_buildings()], want, "the next start changes nothing")
        self.assertEqual(sorted(b["name"] for b in self.view_buildings(st3)), sorted(want))

    def test_the_cloud_picture_carries_no_name(self):
        self.edit("w1", "web/checkout/page.tsx")
        snap, _ = snapshot(self.st)
        clean = ac.cloud_clean(snap)
        names = [b["name"] for t in clean["world"]["territories"] for b in t["buildings"]]
        self.assertEqual(names, [""], "file and folder names never go up")
        self.assertEqual(ac.cloud_clean({"type": "build", "id": "w1", "terr": self.terr, "plot": 0, "btype": "shop",
                                         "x": 0, "z": 0, "by": "w", "q": "good", "home": True, "files": ["a/b.tsx"],
                                         "name": "b 页面", "lv": 0})["name"], "")


# ---------------------------------------------------------------------------
# H2 the history keeper
# ---------------------------------------------------------------------------

def tool(pid, name, kind=None, **more):
    ev = {"type": "tool", "id": pid, "tool": kind or name, "name": name}
    ev.update(more)
    return ev


class TestHistoryLines(unittest.TestCase):

    def setUp(self):
        self.h = ac.History()

    def test_constants(self):
        self.assertEqual(ac.HIST_KEEP, 200)
        self.assertEqual(ac.HIST_GONE_SEC, 86400)

    def test_started(self):
        got = self.h.note({"type": "spawn", "id": "w1", "role": "worker", "label": "worker", "task": "登录 API"}, 100.0)
        self.assertEqual(got, {"id": "w1", "line": {"k": "started", "task": "登录 API", "at": 100.0}, "fold": False})
        self.assertEqual(self.h.lines("w1"), [{"k": "started", "task": "登录 API", "at": 100.0}])

    def test_tools_in_a_row_share_one_line(self):
        h = self.h
        a = h.note(tool("w1", "Edit", file="a.py"), 101.0)
        self.assertEqual(a, {"id": "w1", "fold": False,
                             "line": {"k": "steps", "at": 101.0, "steps": [{"tool": "Edit", "name": "Edit", "file": "a.py"}]}})
        self.assertIsNone(h.note(tool("w1", "Edit", file="a.py"), 102.0), "the same step again adds nothing")
        b = h.note(tool("w1", "Read"), 103.0)
        self.assertTrue(b["fold"], "it replaces the person's last line")
        self.assertEqual(b["line"]["at"], 101.0, "the line keeps the time of its first step")
        self.assertEqual(b["line"]["steps"], [{"tool": "Edit", "name": "Edit", "file": "a.py"}, {"tool": "Read", "name": "Read"}])
        h.note(tool("w1", "Bash"), 104.0)
        d = h.note(tool("w1", "Agent", kind="Other", desc="写测试"), 105.0)
        self.assertEqual(d["line"]["steps"], [{"tool": "Read", "name": "Read"}, {"tool": "Bash", "name": "Bash"},
                                              {"tool": "Other", "name": "Agent", "desc": "写测试"}],
                         "at most 3 steps, the oldest goes")
        self.assertEqual(len(h.lines("w1")), 1, "still one line")
        self.assertEqual(h.lines("w1")[0], d["line"])

    def test_another_line_ends_the_run(self):
        h = self.h
        h.note(tool("w1", "Edit", file="a.py"), 1.0)
        h.note({"type": "waiting", "id": "w1"}, 2.0)
        c = h.note(tool("w1", "Edit", file="a.py"), 3.0)
        self.assertEqual(c["fold"], False)
        self.assertEqual([x["k"] for x in h.lines("w1")], ["steps", "waiting", "steps"])

    def test_two_people_never_mix(self):
        h = self.h
        h.note(tool("w1", "Edit", file="a.py"), 1.0)
        b = h.note(tool("w2", "Read"), 2.0)
        self.assertFalse(b["fold"])
        self.assertEqual(len(h.lines("w1")[0]["steps"]), 1)
        self.assertEqual(h.lines("w2")[0]["steps"], [{"tool": "Read", "name": "Read"}])

    def test_question_and_answer(self):
        h = self.h
        s = h.note({"type": "stuck", "id": "w1", "question": "red or blue?", "tool": "AskUserQuestion"}, 5.0)
        self.assertEqual(s["line"], {"k": "stuck", "question": "red or blue?", "tool": "AskUserQuestion", "at": 5.0})
        a = h.note({"type": "answer", "id": "w1", "ok": True}, 6.0)
        self.assertEqual(a["line"], {"k": "qa", "question": "red or blue?", "tool": "AskUserQuestion", "ok": True, "at": 6.0})
        self.assertFalse(a["fold"])
        b = h.note({"type": "answer", "id": "w2", "ok": False, "answer": "blue"}, 7.0)
        self.assertEqual(b["line"], {"k": "qa", "question": "", "tool": "", "ok": False, "answer": "blue", "at": 7.0},
                         "no question known: empty, the answer's own text is kept")
        h.note({"type": "stuck", "id": "w1", "question": "", "tool": "Bash"}, 8.0)
        c = h.note({"type": "answer", "id": "w1", "ok": False}, 9.0)
        self.assertEqual((c["line"]["question"], c["line"]["tool"]), ("", "Bash"), "the LAST stuck of that person")

    def test_the_other_lines(self):
        h = self.h
        for ev, k in (({"type": "relay", "id": "w1", "to": "lead", "lead": "s:x"}, "toLead"),
                      ({"type": "relay", "id": "w1", "to": "governor", "lead": ""}, "toGov"),
                      ({"type": "waiting", "id": "w1"}, "waiting"),
                      ({"type": "done", "id": "w1"}, "done"),
                      ({"type": "leave", "id": "w1"}, "left")):
            with self.subTest(k=k):
                self.assertEqual(h.note(ev, 3.5), {"id": "w1", "line": {"k": k, "at": 3.5}, "fold": False})

    def test_events_that_make_no_history(self):
        h = self.h
        for ev in ({"type": "resume", "id": "w1"}, {"type": "idle", "id": "w1"}, {"type": "background", "id": "w1"},
                   {"type": "relay_end", "id": "w1", "by": "lead"}, {"type": "world", "world": {}},
                   {"type": "build", "id": "w1", "terr": "t", "plot": 0}, {"type": "gov", "state": "busy"},
                   {"type": "chat", "to": "w1"}, {"type": "hist", "id": "w1", "line": {}},
                   {"type": "relay", "id": "w1", "to": "nobody"},
                   {"type": "done"}, {"type": "done", "id": 7}, {"type": "done", "id": ""}, {}, "x", None):
            with self.subTest(ev=ev):
                self.assertIsNone(h.note(ev, 1.0))
        self.assertEqual(h.lines("w1"), [])

    def test_lines_is_a_copy(self):
        self.h.note({"type": "done", "id": "w1"}, 1.0)
        self.h.lines("w1").append("x")
        self.h.lines("w1")[0]["k"] = "changed"
        self.assertEqual(self.h.lines("w1"), [{"k": "done", "at": 1.0}])
        self.assertEqual(self.h.lines("nobody"), [])


def fill(h, pid, n, start=0):
    """n lines that never fold (waiting / done by turns)."""
    for i in range(start, start + n):
        h.note({"type": "waiting" if i % 2 == 0 else "done", "id": pid}, float(i))


class TestHistoryBounds(unittest.TestCase):

    def test_the_last_200_lines_per_person(self):
        h = ac.History()
        fill(h, "w1", 450)
        fill(h, "w2", 3)
        got = h.lines("w1")
        self.assertEqual(len(got), 200)
        self.assertEqual((got[0]["at"], got[-1]["at"]), (250.0, 449.0), "the oldest go")
        self.assertEqual(len(h.lines("w2")), 3)

    def test_keep_can_be_set(self):
        h = ac.History(keep=5)
        fill(h, "w1", 9)
        self.assertEqual([x["at"] for x in h.lines("w1")], [4.0, 5.0, 6.0, 7.0, 8.0])

    def test_gone_more_than_24_hours_is_dropped(self):
        h = ac.History()
        t = 1_790_000_000.0
        h.note({"type": "spawn", "id": "w1", "task": "a"}, t - 50)
        h.note({"type": "spawn", "id": "w2", "task": "b"}, t - 50)
        h.note({"type": "leave", "id": "w1"}, t)
        h.sweep(t + 23 * 3600)
        self.assertEqual(len(h.lines("w1")), 2, "gone 23 h: kept")
        h.sweep(t + 24 * 3600 + 1)
        self.assertEqual(h.lines("w1"), [], "gone more than 24 h: dropped")
        self.assertEqual(len(h.lines("w2")), 1, "a person who never left stays, however old its lines")

    def test_coming_back_keeps_the_history(self):
        h = ac.History()
        t = 1_790_000_000.0
        h.note({"type": "spawn", "id": "s:a", "task": "a"}, t)
        h.note({"type": "leave", "id": "s:a"}, t + 1)
        h.note({"type": "spawn", "id": "s:a", "task": "a"}, t + 3600)      # the same session, resumed
        h.sweep(t + 30 * 3600)
        self.assertEqual([x["k"] for x in h.lines("s:a")], ["started", "left", "started"])

    def test_gone_sec_can_be_set(self):
        h = ac.History(gone_sec=10)
        h.note({"type": "leave", "id": "w1"}, 100.0)
        h.sweep(111.0)
        self.assertEqual(h.lines("w1"), [])


class TestHistoryFile(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_hist_")
        self.path = os.path.join(self.base, "history.jsonl")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def rows(self):
        with open(self.path, encoding="utf-8") as fh:
            return [x for x in fh.read().splitlines() if x.strip()]

    def test_no_file_before_the_first_line_and_private(self):
        h = ac.History(self.path)
        self.assertEqual(h.lines("w1"), [])
        h.note({"type": "spawn", "id": "w1", "task": "T"}, 1.0)
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600, "task and question text: this user only")

    def test_one_appended_row_per_answer(self):
        h = ac.History(self.path)
        h.note({"type": "spawn", "id": "w1", "task": "T"}, 1.0)
        ino, n1 = os.stat(self.path).st_ino, len(self.rows())
        h.note(tool("w1", "Edit", file="a.py"), 2.0)
        h.note(tool("w1", "Edit", file="a.py"), 3.0)                      # adds nothing
        h.note(tool("w1", "Read"), 4.0)                                   # a fold
        self.assertEqual(os.stat(self.path).st_ino, ino, "appended, never rewritten per line")
        self.assertEqual(len(self.rows()) - n1, 2)

    def test_a_new_server_reads_it_back(self):
        t = time.time()
        h = ac.History(self.path)
        h.note({"type": "spawn", "id": "w1", "task": "登录 API"}, t)
        h.note(tool("w1", "Edit", file="a.py"), t + 1)
        h.note(tool("w1", "Read"), t + 2)
        h.note({"type": "stuck", "id": "w1", "question": "q?", "tool": "AskUserQuestion"}, t + 3)
        h.note({"type": "answer", "id": "w1", "ok": True}, t + 4)
        h.note({"type": "spawn", "id": "s:b", "task": "b"}, t + 5)
        h2 = ac.History(self.path)
        self.assertEqual(h2.lines("w1"), h.lines("w1"))
        self.assertEqual([x["k"] for x in h2.lines("w1")], ["started", "steps", "stuck", "qa"])
        self.assertEqual(len(h2.lines("w1")[1]["steps"]), 2, "the fold is applied")
        self.assertEqual(h2.lines("s:b"), h.lines("s:b"))
        # the run goes on after a restart: the next tool folds into the same line
        self.assertIsNone(h2.note({"type": "resume", "id": "w1"}, t + 6))
        h2.note({"type": "waiting", "id": "w1"}, t + 7)
        self.assertEqual(ac.History(self.path).lines("w1"), h2.lines("w1"))

    def test_the_question_of_an_open_stuck_survives_a_restart(self):
        t = time.time()
        h = ac.History(self.path)
        h.note({"type": "stuck", "id": "w1", "question": "q?", "tool": "AskUserQuestion"}, t)
        h2 = ac.History(self.path)
        a = h2.note({"type": "answer", "id": "w1", "ok": True}, t + 1)
        self.assertEqual((a["line"]["question"], a["line"]["tool"]), ("q?", "AskUserQuestion"))

    def test_load_keeps_200_and_writes_the_file_compact(self):
        t = time.time()
        h = ac.History(self.path)
        for i in range(450):
            h.note({"type": "waiting" if i % 2 == 0 else "done", "id": "w1"}, t + i)
        self.assertGreaterEqual(len(self.rows()), 450)
        h2 = ac.History(self.path)
        self.assertEqual(h2.lines("w1"), h.lines("w1"))
        self.assertEqual(len(h2.lines("w1")), 200)
        self.assertLessEqual(len(self.rows()), 210, "the file was written compact at load")
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(ac.History(self.path).lines("w1"), h.lines("w1"))

    def test_gone_people_are_dropped_at_load(self):
        t = time.time()
        h = ac.History(self.path)
        h.note({"type": "spawn", "id": "w1", "task": "a"}, t - 26 * 3600)
        h.note({"type": "leave", "id": "w1"}, t - 25 * 3600)
        h.note({"type": "spawn", "id": "w2", "task": "b"}, t - 26 * 3600)
        h.note({"type": "leave", "id": "w2"}, t - 3600)
        h.note({"type": "spawn", "id": "w3", "task": "c"}, t - 40 * 3600)
        h2 = ac.History(self.path)
        self.assertEqual(h2.lines("w1"), [], "gone 25 h")
        self.assertEqual(len(h2.lines("w2")), 2, "gone 1 h")
        self.assertEqual(len(h2.lines("w3")), 1, "never left")
        self.assertEqual(ac.History(self.path, now=t + 30 * 3600).lines("w2"), [], "NOW decides")
        h3 = ac.History(self.path)
        self.assertEqual(h3.lines("w2"), [], "the compact file no longer has it")

    def test_a_sweep_holds_after_a_restart(self):
        t = time.time()
        h = ac.History(self.path)
        h.note({"type": "spawn", "id": "w1", "task": "a"}, t)
        h.note({"type": "leave", "id": "w1"}, t + 1)
        h.sweep(t + 30 * 3600)
        self.assertEqual(h.lines("w1"), [])
        h.note({"type": "spawn", "id": "w1", "task": "again"}, t + 2)
        self.assertEqual([x["task"] for x in ac.History(self.path).lines("w1")], ["again"],
                         "the dropped lines do not come back from the file")

    def test_a_broken_file_never_raises(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("not json\n{\"x\": 1}\n[1, 2]\n\n")
        h = ac.History(self.path)
        self.assertEqual(h.lines("w1"), [])
        h.note({"type": "done", "id": "w1"}, time.time())
        self.assertEqual(len(ac.History(self.path).lines("w1")), 1)

    def test_a_folder_that_is_not_there_never_raises(self):
        h = ac.History(os.path.join(self.base, "nope", "history.jsonl"))
        self.assertIsNotNone(h.note({"type": "done", "id": "w1"}, 1.0))
        self.assertEqual(len(h.lines("w1")), 1, "kept in memory")


# ---------------------------------------------------------------------------
# H3 the server keeps it and every page gets the same lines
# ---------------------------------------------------------------------------

class TestCityHistory(CityCase):

    def city(self, **more):
        more.setdefault("history_path", self.hist_path)
        return super().city(**more)

    def work(self):
        """A worker starts, edits two files, asks, is answered, finishes."""
        self.feed("PreToolUse", tool="Agent", sub="worker", desc="登录 API")
        self.feed("SubagentStart", aid="w1")
        self.put("api/login.py")
        self.feed("PostToolUse", aid="w1", tool="Edit", file="api/login.py")
        self.feed("PostToolUse", aid="w1", tool="Read")
        self.feed("PreToolUse", aid="w1", tool="AskUserQuestion", q="red or blue?")
        self.feed("PostToolUse", aid="w1", tool="AskUserQuestion")
        self.feed("SubagentStop", aid="w1")
        return drain(self.client)

    def test_a_history_object(self):
        self.assertIsInstance(self.st.history, ac.History)
        self.assertIsInstance(ac.CityState(decisions_path=os.path.join(self.base, "d2.jsonl"),
                                           world_path=os.path.join(self.base, "w2.json")).history, ac.History,
                              "no history_path: kept in memory")

    def test_live_lines_follow_their_event(self):
        events = self.work()
        kinds = [e["type"] for e in events]
        self.assertIn("hist", kinds)
        i = kinds.index("spawn")
        self.assertEqual(kinds[i + 1], "hist", "the line goes out right after its event")
        first = events[i + 1]
        self.assertEqual(first["id"], "w1")
        self.assertEqual(first["fold"], False)
        self.assertEqual((first["line"]["k"], first["line"]["task"]), ("started", "登录 API"))
        self.assertLess(abs(first["line"]["at"] - time.time()), 60, "epoch seconds: the page shows the clock time")
        mine = [e for e in events if e["type"] == "hist" and e["id"] == "w1"]
        self.assertEqual([(e["line"]["k"], e["fold"]) for e in mine],
                         [("started", False), ("steps", False), ("steps", True), ("stuck", False), ("qa", False),
                          ("steps", False), ("done", False)])
        self.assertEqual(mine[2]["line"]["steps"][0].get("file"), "login.py", "the file's name, never its folder")
        self.assertEqual(mine[4]["line"]["question"], "red or blue?")

    def test_a_second_tab_and_a_reload_show_the_same(self):
        self.work()
        want = self.st.history_view("w1")
        self.assertEqual([x["k"] for x in want], ["started", "steps", "stuck", "qa", "steps", "done"])
        a, _ = snapshot(self.st)
        b, _ = snapshot(self.st)
        self.assertIsInstance(a.get("hist"), dict)
        self.assertEqual(a["hist"]["w1"], want)
        self.assertEqual(b["hist"], a["hist"])
        self.assertEqual(sorted(a["hist"]), sorted(x["id"] for x in a["agents"]), "one list per person on the page")

    def test_a_server_restart_keeps_it(self):
        self.work()
        want = self.st.history_view("w1")
        st2 = self.city()
        self.assertEqual(st2.history_view("w1"), want)
        _, client = snapshot(st2)
        self.feed("PostToolUse", st=st2, tool="Read")
        self.feed("PostToolUse", st=st2, aid="w1", tool="Bash")          # the worker is seen again
        snap, _ = snapshot(st2)
        self.assertEqual(snap["hist"]["w1"][:len(want)], want, "the old lines first")
        self.assertGreater(len(snap["hist"]["w1"]), len(want))

    def test_sweep_history(self):
        self.work()
        self.feed("PostToolUse", sid="s2", tool="Read")                  # a second session: a citizen
        self.feed("SessionEnd", sid="s2")
        drain(self.client)
        self.assertEqual([x["k"] for x in self.st.history_view("s:s2")][-1], "left")
        self.st.sweep_history(time.time() + 23 * 3600)
        self.assertTrue(self.st.history_view("s:s2"))
        self.st.sweep_history(time.time() + 25 * 3600)
        self.assertEqual(self.st.history_view("s:s2"), [])
        self.assertTrue(self.st.history_view("w1"), "w1 is done, not gone")

    def test_local_only(self):
        self.assertIn("hist", ac.CLOUD_DROP)
        self.assertNotIn("hist", ac.CLOUD_KEEP)
        self.assertIsNone(ac.cloud_clean({"type": "hist", "id": "w1", "line": {"k": "done", "at": 1.0}, "fold": False}))
        self.work()
        snap, _ = snapshot(self.st)
        self.assertIn("hist", snap)
        clean = ac.cloud_clean(snap)
        self.assertNotIn("hist", clean, "the cloud picture stays as it is")
        self.assertIn("hist", snap, "the local page still gets everything")

    def test_wired_into_the_server(self):
        serve = inspect.getsource(ac.cmd_serve)
        self.assertIn("history.jsonl", serve)
        self.assertIn("history_path=", serve)
        self.assertIn("sweep_history(time.time())", inspect.getsource(ac.recount_loop))


if __name__ == "__main__":
    unittest.main()
