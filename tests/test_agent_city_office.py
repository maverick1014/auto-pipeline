"""Failing tests for city-office, the SERVER side (requirements/city.md, "Office"; owner 2026-11-24, prototype
approved 2026-11-25: mock/city-office-mock.html v5). The city becomes one office building: one floor per repo
the owner ticks, a design file per floor, and an interior designer agent the city can open. The page side:
tests/test_agent_city_office_page.py. No test here opens a real session or writes the owner's real files.

CONTRACT (bin/agent_city.py, Python standard library only)

O1 floors -- which repos are in the building (replaces Arrange's slots and hidden flags)
  world["floors"]: the identities in the building, bottom first (index 0 = 1F). Saved in world.json.
  A world without "floors" (an island world.json, or a fresh one): every territory of world["order"] that is
    not hidden, in that order. Identities that are no territory are dropped on load.
  A repo the city sees for the first time (its first line adds the territory) goes on top of the floors at
    once (a new company moves in) and the page hears a "world" event. A repo the owner unticked stays out:
    its later lines never put it back.
  CityState.floors() -> the territory ids of the floors, bottom first.
  CityState.set_floors(ids) -> (code, body):
    400 {"error": "bad"}      ids is not a list of 1..64 strings of 8 lowercase hex digits, or has a repeat
    404 {"error": "unknown"}  an id that is no territory of this world
    200 {"floors": [ids]}     saved (world.json written before the call returns); every page gets a "world" event
    On 400 and 404 nothing changes. An empty list is 400 (at least one floor stays).
  A territory not in the floors is HIDDEN for everything the page hears (the city-layout filter stays: its
    people, governor, asks, adding and events are never sent). The hidden flag of a territory record is no
    longer read or written: floors decide.

O2 who is who (Who is shown)
  A session line with no hook role (no AGENT_ROLE: a Helper, a plain session) that is not the governor ->
    role "helper" (was "task-manager"). Hook role "task-manager" -> "task-manager". Hook role
    "interior-designer" -> role "designer". Subagents keep their roles.
  The spawn's "up" (city-rail-tree): every session that is not the governor (helper, task-manager,
    designer) -> "gov:<terr>" (the tree is 区经理 > 设计师, 助理, 经理); a subagent -> its session, as before.

O3 floor designs (Floor design)
  DESIGN_COLORS = ("accent", "carpet", "manager_floor", "pantry_floor", "desk", "desk_leg", "chair",
                   "meeting_rug", "manager_rug")
  DESIGN_LIGHT = ("carpet", "manager_floor", "pantry_floor")      lightness 55..95 % (HSL, (max + min) / 2)
  FLOOR_DECOR = ("robot", "conveyor", "gears", "chart", "plants", "safe", "cabinets", "printer",
                 "bookshelf", "clock", "cashier", "goods", "menu", "scanner", "lightbox")
  check_design(obj) -> [] when OBJ is a good design, else a list of problems {"field", "zh", "en"} (field is
    the key path: "v", "name", "why", "colors", "colors.<key>", "decor", "decor.<1..3>", or the unknown key
    itself). A good design: a dict with keys v, name, colors, decor and maybe why, nothing else;
      v      the int 1 (never a bool)
      name   a str of 1..20 characters, not only spaces
      why    a str of 0..60 characters
      colors a dict with exactly the 9 DESIGN_COLORS keys, each "#RRGGBB" (hex, either case); the three
             DESIGN_LIGHT ones with 55 <= lightness <= 95 (exact, not rounded)
      decor  a list of exactly 3 entries, each a FLOOR_DECOR id or "none"
    The lightness problem's zh is exactly "<label>的亮度是 <L>%，要在 55%–95% 之间" (L rounded to a whole
    number; labels: carpet 地毯, manager_floor 区经理室地板, pantry_floor 茶水间地板). Every problem has a
    non-empty zh and en. All problems are listed, not only the first. Never raises, whatever OBJ is.
  FLOOR_RULES: the rules as plain text (`agent-city floor rules` prints it): every field, every colour key,
    every catalogue id, "55" and "95", "exactly 3", which decor entry is which slot ("south-west corner",
    "south middle", "east wall"), the never-settable things (floor size, the lift, the
    area manager's room, the desks, the pantry, the meeting corner, people), where the file lives, and the
    commands `agent-city.sh floor show` and `agent-city.sh floor set`.
  floors_home() -> $AGENT_CITY_HOME/floors (default ~/.claude/agent-city/floors).
  CityState(..., floors_dir=None): None = designs live in memory only (tests), else the folder of
    <tid>.json (the design) and <tid>.history.jsonl (the last 5 designs it replaced, one JSON per line,
    null = "no design"). Files are written atomically (tmp + os.replace).
  CityState.designs() -> {tid: design} for every territory with a good design.
  CityState.set_design(tid, obj, by) -> (code, body); BY is "owner" (the DIY form) or "designer":
    404 {"error": "unknown"}                  no such territory
    422 {"error": "bad", "problems": [...]}   check_design said no; nothing is written, nothing is sent
    200 {"design": obj}                       saved; the design it replaced (or null) goes to the history
                                              (the last 5 kept); the territory counts as asked; every page
                                              gets {"type": "world", "world": <office view>,
                                              "change": {"kind": "design", "terr", "by"}}
  CityState.undo_design(tid) -> 409 {"error": "empty"} with no history; else the last history entry comes
    back (null: the file is removed, the base look), it leaves the history, 200 {"design": <it or None>},
    and a "world" event with change kind "undo".
  CityState.skip_design(tid) -> 200 {}: 先不装修, the territory counts as asked (no design); "world" event
    with change kind "skip". 404 for no such territory.
  "asked" is kept in world.json (the territory record's "reno_asked": true), so the renovation question is
    asked once per repo, also after a restart.
  CityState.scan_floors(): what someone else wrote (another session, an editor, `floor set`). For every
    floor file of a known territory whose (size, mtime) changed since the last look: a good design -> taken,
    "world" event with change {"kind": "design", "terr", "by": "file"}; a broken one (bad JSON or
    problems) -> the last good design stays and every page gets {"type": "design_bad", "terr",
    "problems": [...]} once per change of the file; a removed file -> no design, "world" event. The
    server's own writes are never reported back as "file". A file `<tid>.bye` (written by `floor bye`)
    -> that floor's designer leaves (O6) and the file is removed. Called by the 2 s loop (recount_loop).

O4 what a page gets
  The snapshot's "world" and every "world" event's "world" is the office view:
    {"v": 2,
     "repos":   [{"id", "name", "here", "n"}, ...]   every territory this machine knows, world order
                                                    (n = the place in world["order"]; here = its folder is
                                                    on this machine)
     "floors":  [ids], bottom first
     "designs": {tid: design}                       the good designs of every known territory
     "asked":   [tids]}                             territories whose renovation question was answered

O5 HTTP (the guard of chat and add agent: 127.0.0.1, token, own Origin; POST only; JSON object body)
  POST /api/floors         {"floors": [ids]}                       -> set_floors
  POST /api/design         {"terr", "design"} | {"terr", "undo": true} | {"terr", "skip": true}
                                                                   -> set_design(by "owner") / undo / skip
  POST /api/designer       {"terr", "force"}                       -> add_designer
  POST /api/designer/leave {"terr"}                                -> leave_designer
  Any other key, a missing key or a wrong type -> 400 {"error": "bad"}; no token -> 403; a foreign Origin
  -> 403; GET on these paths opens or changes nothing.

O6 the interior designer (Renovation)
  interior_designer: one of agent_conf.ROLE_KEYS, a helper role (settings-configure: it reads the
    "Models: Helper model" setting; no agent.conf, no Configure item of its own).
  agent_command(name, folder, city_dir=None, model_key="main_manager", prompt=FIRST_PROMPT, role=None):
    as before, plus: the model comes from MODEL_KEY of <folder>/agent.conf, and for "interior_designer"
    from bin/agent.conf.default when the repo's file has no such line; ROLE -> "AGENT_ROLE=<role> " right
    before "claude" (after AGENT_CITY_DIR=...); PROMPT is the last word. The add-agent line is unchanged.
  designer_prompt(repo) -> one line: "You were opened from the Agent City page as the interior designer of
    the <repo> floor. Read <plugin>/agents/interior-designer.md now and follow it. Do not run
    agent-start.sh: you are not a pipeline agent." (<plugin> = the folder above this bin/).
  CityState.add_designer(tid, now, force=False) -> (code, body): the same order and answers as add_agent
    (400, 404, 409 gone, 409 busy, kind -> 200 "plain" with the line, cap -> 200 "cap", opener 502, 200
    "opening"), plus 409 {"error": "designer-here"} while a live designer session is on that floor. Name
    "<repo> Designer", role "designer"; the line is agent_command(name, folder, city_dir,
    "interior_designer", designer_prompt(repo), "interior-designer"). Its hold is its own: a designer
    opening never blocks an add agent of the same repo, nor the other way round. The "adding" events carry
    "kind": "designer".
  The opener: open_session(...) -> (True, <terminal handle>) on success (the handle of the JSON the
    runtime prints, "" when none). The city keeps the handle of the designer it opened.
  CityState.leave_designer(tid) -> 404 {"error": "none"} with no live designer on that floor; else
    close_fn(handle) (CityState(..., close_fn=...), default `bash bin/agent-runtime.sh close <handle>`), the
    designer leaves the page at once (its "leave" event; the page walks it to the lift) and 200 {}.
  agents/interior-designer.md: the designer's role and knowledge (frontmatter name interior-designer, model
    sonnet). It says: read `agent-city.sh floor rules` first; read only the repo's README or CLAUDE.md
    (first 60 lines) and the top-level folder names; never edit, add or remove a file of the repo; answer
    the owner with a plan, then write the design with `agent-city.sh floor set`; a wish that is not
    settable: change what it may and say in one line what it left alone; when the owner says it may go
    ("可以走了"), say goodbye and run `agent-city.sh floor bye`.

O7 the command line (agent_city.py floor ..., and agent-city.sh floor ... passes everything through)
  floor rules                 prints FLOOR_RULES, exit 0
  floor show <repo>           the design file as JSON, or "no design yet (base look)"; exit 0
  floor set <repo> <file|->   check_design; problems -> one line per problem "<field>: <en>" on stderr,
                              exit 1, nothing written; good -> written (atomic, history as O3), "saved", exit 0
  floor bye <repo>            writes <tid>.bye (O3 scan), exit 0
  <repo> is a territory id, a repo name of world.json, or "." (the repo of the current folder). Unknown ->
  exit 1 with the known names. Paths: --world (default world_path()), --floors-dir (default floors_home()).
"""

import http.client
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
SERVER = os.path.join(BIN, "agent_city.py")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
import agent_conf  # noqa: E402
from cityhelp import Mains  # noqa: E402

CONF = "main_manager=opus-5.5:high\npermission_mode=auto\n"

GOOD = {"v": 1, "name": "收银台风格", "why": "POS 收银的 repo",
        "colors": {"accent": "#2E7D6B", "carpet": "#E4DCCB", "manager_floor": "#D9C2A0", "pantry_floor": "#EEEAE0",
                   "desk": "#EFDAB5", "desk_leg": "#BBA27C", "chair": "#3E4560", "meeting_rug": "#A9BCE0",
                   "manager_rug": "#C97B66"},
        "decor": ["cashier", "none", "goods"]}


def good(**kw):
    d = json.loads(json.dumps(GOOD))
    for k, v in kw.items():
        if k.startswith("c_"):
            d["colors"][k[2:]] = v
        else:
            d[k] = v
    return d


def line(ev, sid, repo, aid="", role="", at=""):
    return {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": "Read", "nt": "", "proj": "shop", "role": role,
            "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}


class OfficeCase(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_office_"))
        self.calls, self.closed = [], []
        self.answer = (True, "term_abc-1")
        self.mains = Mains()
        self.kind = "orca"
        self.res = {"ram": 10, "cpu": 10, "max": 80, "ok": True}
        self.now = 1000.0
        self.floors_dir = os.path.join(self.base, "floors")
        self.world_file = os.path.join(self.base, "world.json")
        self.shop = self.repo("shop")
        self.blog = self.repo("blog")
        self.state = self.make()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def repo(self, name, conf=CONF):
        folder = os.path.join(self.base, name)
        os.makedirs(os.path.join(folder, ".git"))
        if conf is not None:
            with open(os.path.join(folder, "agent.conf"), "w") as fh:
                fh.write(conf)
        return os.path.join(folder, ".git")

    def opener(self, folder, title, command):
        self.calls.append((folder, title, command))
        return self.answer

    def make(self, **kw):
        args = dict(world_path=self.world_file, token="tok", floors_dir=self.floors_dir,
                    main_fn=self.mains, open_fn=self.opener, kind_fn=lambda folder: self.kind,
                    resources_fn=lambda folder: dict(self.res), close_fn=lambda h: self.closed.append(h) or True)
        args.update(kw)
        return ac.CityState(decisions_path=os.path.join(self.base, "decisions.jsonl"), **args)

    def feed(self, *lines, at=None):
        for obj in lines:
            self.state.feed_line(obj, self.now if at is None else at)

    def known(self, identity, sid=None):
        sid = sid or "s-" + os.path.basename(os.path.dirname(identity))
        self.feed(line("UserPromptSubmit", sid, identity), line("Stop", sid, identity))
        return ac.territory_id(identity)

    def client(self):
        c = self.state.add_client()
        while not c.queue.empty():
            c.queue.get_nowait()
        return c

    def snapshot(self):
        c = self.state.add_client()
        raw = c.queue.get_nowait().decode("utf-8")
        self.state.remove_client(c)
        return json.loads(raw.split("data:", 1)[1])

    @staticmethod
    def events(client, kind=None):
        out = []
        while not client.queue.empty():
            raw = client.queue.get_nowait().decode("utf-8")
            if "data:" not in raw:
                continue
            msg = json.loads(raw.split("data:", 1)[1])
            if kind is None or msg.get("type") == kind:
                out.append(msg)
        return out

    def saved_world(self):
        with open(self.world_file, encoding="utf-8") as fh:
            return json.load(fh)


# ---------------------------------------------------------------------------
# O1 floors
# ---------------------------------------------------------------------------

class TestFloors(OfficeCase):
    def test_a_new_repo_moves_in_on_top(self):
        a = self.known(self.shop)
        b = self.known(self.blog)
        self.assertEqual(self.state.floors(), [a, b], "first seen first: 1F shop, 2F blog")
        self.assertEqual(self.saved_world()["floors"], [self.shop, self.blog], "identities, bottom first")

    def test_new_repo_sends_a_world_event(self):
        self.known(self.shop)
        c = self.client()
        b = self.known(self.blog)
        evs = self.events(c, "world")
        self.assertTrue(evs, "the page hears the new floor")
        self.assertEqual(evs[-1]["world"]["floors"][-1], b)

    def test_set_floors_orders_and_unticks(self):
        a, b = self.known(self.shop), self.known(self.blog)
        c = self.client()
        code, body = self.state.set_floors([b])
        self.assertEqual((code, body), (200, {"floors": [b]}))
        self.assertEqual(self.state.floors(), [b])
        self.assertEqual(self.saved_world()["floors"], [self.blog])
        self.assertTrue(self.events(c, "world"))
        code, body = self.state.set_floors([b, a])
        self.assertEqual((code, body), (200, {"floors": [b, a]}), "blog 1F, shop 2F")

    def test_an_unticked_repo_never_comes_back_by_itself(self):
        a, b = self.known(self.shop), self.known(self.blog)
        self.state.set_floors([a])
        self.known(self.blog, sid="s-blog-2")
        self.assertEqual(self.state.floors(), [a])

    def test_bad_requests_change_nothing(self):
        a, b = self.known(self.shop), self.known(self.blog)
        for bad in ([], "x", [a, a], [1], ["NOTHEX00"], [a] * 70, None):
            self.assertEqual(self.state.set_floors(bad), (400, {"error": "bad"}), bad)
        self.assertEqual(self.state.set_floors([a, "0badc0de"]), (404, {"error": "unknown"}))
        self.assertEqual(self.state.floors(), [a, b])

    def test_unticked_people_are_never_sent(self):
        a, b = self.known(self.shop), self.known(self.blog)
        self.state.set_floors([a])
        snap = self.snapshot()
        self.assertEqual({x["terr"] for x in snap["agents"]}, {a}, "blog's session is not in the snapshot")
        c = self.client()
        self.feed(line("PreToolUse", "s-blog", self.blog))
        self.assertFalse([e for e in self.events(c) if e.get("terr") == b or str(e.get("id", "")).endswith("s-blog")])

    def test_floors_survive_a_restart(self):
        a, b = self.known(self.shop), self.known(self.blog)
        self.state.set_floors([b, a])
        again = self.make()
        self.assertEqual(again.floors(), [b, a])

    def test_an_island_world_gets_floors_from_its_order(self):
        a, b = self.known(self.shop), self.known(self.blog)
        w = self.saved_world()
        w.pop("floors", None)
        w["territories"][self.blog]["hidden"] = True
        with open(self.world_file, "w", encoding="utf-8") as fh:
            json.dump(w, fh)
        self.assertEqual(self.make().floors(), [a], "a hidden island repo is not ticked")


# ---------------------------------------------------------------------------
# O2 roles
# ---------------------------------------------------------------------------

class TestRoles(OfficeCase):
    def spawns(self, *lines):
        c = self.client()
        self.feed(*lines)
        return {e["id"]: e for e in self.events(c, "spawn")}

    def test_session_roles(self):
        self.mains[self.shop] = "gov"
        self.known(self.shop, sid="gov")
        tid = ac.territory_id(self.shop)
        sp = self.spawns(line("UserPromptSubmit", "h1", self.shop),
                         line("UserPromptSubmit", "t1", self.shop, role="task-manager"),
                         line("UserPromptSubmit", "d1", self.shop, role="interior-designer"))
        self.assertEqual(sp["s:h1"]["role"], "helper", "no AGENT_ROLE = 助理")
        self.assertEqual(sp["s:t1"]["role"], "task-manager")
        self.assertEqual(sp["s:d1"]["role"], "designer")
        for sid in ("h1", "t1", "d1"):
            self.assertEqual(sp["s:" + sid].get("up"), "gov:" + tid, "the tree: 区经理 > 设计师, 助理, 经理")

    def test_a_subagent_still_hangs_on_its_session(self):
        self.known(self.shop, sid="h1")
        sp = self.spawns(line("PreToolUse", "h1", self.shop, aid="w1", at="worker"))
        ws = [e for e in sp.values() if e["role"] == "worker"]
        self.assertEqual(len(ws), 1)
        self.assertEqual(ws[0].get("up"), "s:h1")


# ---------------------------------------------------------------------------
# O3 check_design
# ---------------------------------------------------------------------------

class TestCheckDesign(unittest.TestCase):
    def fields(self, obj):
        probs = ac.check_design(obj)
        for p in probs:
            self.assertTrue(p.get("zh") and p.get("en"), p)
        return {p["field"] for p in probs}

    def test_constants(self):
        self.assertEqual(ac.DESIGN_COLORS, ("accent", "carpet", "manager_floor", "pantry_floor", "desk", "desk_leg",
                                            "chair", "meeting_rug", "manager_rug"))
        self.assertEqual(ac.DESIGN_LIGHT, ("carpet", "manager_floor", "pantry_floor"))
        self.assertEqual(ac.FLOOR_DECOR, ("robot", "conveyor", "gears", "chart", "plants", "safe", "cabinets",
                                          "printer", "bookshelf", "clock", "cashier", "goods", "menu", "scanner",
                                          "lightbox"))

    def test_good(self):
        self.assertEqual(ac.check_design(GOOD), [])
        d = good()
        del d["why"]
        self.assertEqual(ac.check_design(d), [], "why is optional")
        self.assertEqual(ac.check_design(good(decor=["none", "none", "none"])), [])
        self.assertEqual(ac.check_design(good(c_accent="#abcdef")), [], "either case")

    def test_lightness_message_is_the_owners(self):
        probs = ac.check_design(good(c_pantry_floor="#333333"))
        self.assertEqual(len(probs), 1)
        self.assertEqual(probs[0]["field"], "colors.pantry_floor")
        self.assertEqual(probs[0]["zh"], "茶水间地板的亮度是 20%，要在 55%–95% 之间")

    def test_lightness_edges(self):
        self.assertIn("colors.carpet", self.fields(good(c_carpet="#8C8C8C")), "54.9 %")
        self.assertEqual(ac.check_design(good(c_carpet="#8D8D8D")), [], "55.3 %")
        self.assertEqual(ac.check_design(good(c_manager_floor="#F2F2F2")), [], "94.9 %")
        self.assertIn("colors.manager_floor", self.fields(good(c_manager_floor="#F3F3F3")), "95.3 %")
        self.assertEqual(ac.check_design(good(c_desk="#000000", c_chair="#FFFFFF")), [], "only the 3 floors")

    def test_every_problem_is_listed(self):
        bad = good(v=3, name="", why="x" * 61, decor=["robot", "sofa"], c_carpet="red")
        bad["colors"].pop("chair")
        bad["colors"]["wall"] = "#FFFFFF"
        bad["lift"] = "south"
        f = self.fields(bad)
        for want in ("v", "name", "why", "decor", "colors.carpet", "colors.chair", "colors.wall", "lift"):
            self.assertIn(want, f)

    def test_decor_entries(self):
        self.assertIn("decor.2", self.fields(good(decor=["robot", "sofa", "none"])))
        self.assertIn("decor", self.fields(good(decor=["robot", "none", "none", "none"])))
        self.assertIn("decor", self.fields(good(decor="robot")))

    def test_types(self):
        self.assertIn("v", self.fields(good(v=True)))
        self.assertIn("name", self.fields(good(name="   ")))
        self.assertIn("name", self.fields(good(name="一" * 21)))
        self.assertEqual(ac.check_design(good(name="一" * 20)), [])
        self.assertIn("colors.accent", self.fields(good(c_accent="#12345")))
        self.assertIn("colors.accent", self.fields(good(c_accent=123456)))
        for junk in (None, [], "x", 3, {"v": 1}):
            self.assertTrue(ac.check_design(junk), junk)

    def test_rules_text(self):
        t = ac.FLOOR_RULES
        for word in ac.DESIGN_COLORS + ac.FLOOR_DECOR + ("name", "why", "decor", "55", "95", "exactly 3", "lift",
                                                       "pantry", "meeting", "floor size", "south-west corner", "south middle",
                                                       "east wall", "agent-city.sh floor show",
                                                       "agent-city.sh floor set"):
            self.assertIn(word, t)


# ---------------------------------------------------------------------------
# O3 set / undo / skip / scan
# ---------------------------------------------------------------------------

class TestDesigns(OfficeCase):
    def setUp(self):
        super().setUp()
        self.tid = self.known(self.shop)

    def path(self, ext=".json"):
        return os.path.join(self.floors_dir, self.tid + ext)

    def test_set_writes_the_file_and_tells_the_page(self):
        c = self.client()
        self.assertEqual(self.state.set_design(self.tid, GOOD, "owner"), (200, {"design": GOOD}))
        with open(self.path(), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), GOOD)
        ev = self.events(c, "world")[-1]
        self.assertEqual(ev["world"]["designs"][self.tid], GOOD)
        self.assertEqual(ev["change"], {"kind": "design", "terr": self.tid, "by": "owner"})
        self.assertIn(self.tid, ev["world"]["asked"])
        self.assertEqual(self.state.designs(), {self.tid: GOOD})

    def test_a_bad_design_writes_nothing(self):
        c = self.client()
        code, body = self.state.set_design(self.tid, good(c_carpet="#111111"), "owner")
        self.assertEqual((code, body["error"]), (422, "bad"))
        self.assertEqual([p["field"] for p in body["problems"]], ["colors.carpet"])
        self.assertFalse(os.path.exists(self.path()))
        self.assertFalse(self.events(c, "world"))
        self.assertEqual(self.state.set_design("0badc0de", GOOD, "owner"), (404, {"error": "unknown"}))

    def test_history_keeps_five_and_undo_walks_back(self):
        names = ["d%d" % i for i in range(7)]
        for n in names:
            self.assertEqual(self.state.set_design(self.tid, good(name=n), "owner")[0], 200)
        with open(self.path(".history.jsonl"), encoding="utf-8") as fh:
            hist = [json.loads(x) for x in fh if x.strip()]
        self.assertEqual([h["name"] for h in hist], ["d1", "d2", "d3", "d4", "d5"], "the last 5 replaced")
        c = self.client()
        code, body = self.state.undo_design(self.tid)
        self.assertEqual((code, body["design"]["name"]), (200, "d5"))
        self.assertEqual(self.events(c, "world")[-1]["change"]["kind"], "undo")
        with open(self.path(), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["name"], "d5")

    def test_undo_to_no_design_removes_the_file(self):
        self.state.set_design(self.tid, GOOD, "designer")
        self.assertEqual(self.state.undo_design(self.tid), (200, {"design": None}))
        self.assertFalse(os.path.exists(self.path()))
        self.assertEqual(self.state.designs(), {})
        self.assertEqual(self.state.undo_design(self.tid), (409, {"error": "empty"}))

    def test_skip_counts_as_asked_and_survives_a_restart(self):
        self.assertNotIn(self.tid, self.snapshot()["world"]["asked"])
        self.assertEqual(self.state.skip_design(self.tid), (200, {}))
        self.assertIn(self.tid, self.snapshot()["world"]["asked"])
        self.assertIn(self.tid, self._snap_of(self.make())["world"]["asked"], "asked once, also after a restart")
        self.assertEqual(self.state.skip_design("0badc0de"), (404, {"error": "unknown"}))

    def _snap_of(self, st):
        c = st.add_client()
        raw = c.queue.get_nowait().decode("utf-8")
        st.remove_client(c)
        return json.loads(raw.split("data:", 1)[1])

    def test_designs_load_at_start(self):
        self.state.set_design(self.tid, GOOD, "owner")
        self.assertEqual(self._snap_of(self.make())["world"]["designs"], {self.tid: GOOD})

    def test_scan_takes_a_good_file(self):
        self.state.scan_floors()
        c = self.client()
        os.makedirs(self.floors_dir, exist_ok=True)
        with open(self.path(), "w", encoding="utf-8") as fh:
            json.dump(good(name="外面写的"), fh)
        self.state.scan_floors()
        ev = self.events(c, "world")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["change"], {"kind": "design", "terr": self.tid, "by": "file"})
        self.assertEqual(ev[0]["world"]["designs"][self.tid]["name"], "外面写的")
        self.state.scan_floors()
        self.assertFalse(self.events(c), "nothing changed: nothing sent")

    def test_scan_refuses_a_broken_file_once_and_keeps_the_last_good(self):
        self.state.set_design(self.tid, GOOD, "owner")
        self.state.scan_floors()
        c = self.client()
        self.assertFalse(self.events(c), "the server's own write is never reported back")
        with open(self.path(), "w", encoding="utf-8") as fh:
            json.dump(good(c_pantry_floor="#333333"), fh)
        self.state.scan_floors()
        self.state.scan_floors()
        bad = self.events(c, "design_bad")
        self.assertEqual(len(bad), 1, "once per change of the file")
        self.assertEqual(bad[0]["terr"], self.tid)
        self.assertEqual(bad[0]["problems"][0]["zh"], "茶水间地板的亮度是 20%，要在 55%–95% 之间")
        self.assertEqual(self.state.designs(), {self.tid: GOOD})
        with open(self.path(), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.state.scan_floors()
        self.assertEqual(len(self.events(c, "design_bad")), 1)

    def test_scan_a_removed_file(self):
        self.state.set_design(self.tid, GOOD, "owner")
        self.state.scan_floors()
        os.remove(self.path())
        c = self.client()
        self.state.scan_floors()
        self.assertEqual(self.events(c, "world")[-1]["world"]["designs"], {})

    def test_no_floors_dir_means_memory_only(self):
        st = self.make(floors_dir=None)
        tid = ac.territory_id(self.shop)
        st.feed_line(line("UserPromptSubmit", "x1", self.shop), self.now)
        self.assertEqual(st.set_design(tid, GOOD, "owner")[0], 200)
        self.assertFalse(os.path.exists(self.floors_dir))
        st.scan_floors()

    def test_floors_home(self):
        old = os.environ.get("AGENT_CITY_HOME")
        os.environ["AGENT_CITY_HOME"] = self.base
        try:
            self.assertEqual(ac.floors_home(), os.path.join(self.base, "floors"))
        finally:
            if old is None:
                os.environ.pop("AGENT_CITY_HOME", None)
            else:
                os.environ["AGENT_CITY_HOME"] = old


# ---------------------------------------------------------------------------
# O4 the office view
# ---------------------------------------------------------------------------

class TestView(OfficeCase):
    def test_snapshot_world_is_the_office_view(self):
        a, b = self.known(self.shop), self.known(self.blog)
        self.state.set_floors([b])
        w = self.snapshot()["world"]
        self.assertEqual(set(w), {"v", "repos", "floors", "designs", "asked"})
        self.assertEqual(w["v"], 2)
        self.assertEqual([(r["id"], r["name"], r["here"], r["n"]) for r in w["repos"]],
                         [(a, "shop", True, 0), (b, "blog", True, 1)], "unticked repos stay in the picker")
        self.assertEqual(w["floors"], [b])
        self.assertEqual((w["designs"], w["asked"]), ({}, []))


# ---------------------------------------------------------------------------
# O6 the interior designer
# ---------------------------------------------------------------------------

class TestDesignerCommand(OfficeCase):
    def test_conf_key(self):
        # settings-configure (TELL c87d1093): the designer is a helper role, it reads the Helper
        # model setting; no agent.conf, no Configure item of its own
        self.assertIn("interior_designer", agent_conf.ROLE_KEYS)
        self.assertNotIn("interior_designer", agent_conf.user_config())
        env = {"CLAUDE_CONFIG_DIR": os.path.join(self.base, "cfg")}
        self.assertEqual(agent_conf.get("interior_designer", env), agent_conf.get("helper_model", env))

    def test_add_agent_line_is_unchanged(self):
        folder = os.path.dirname(self.shop)
        words = shlex.split(ac.agent_command("shop Helper", folder))
        self.assertEqual(words[0], "claude")
        self.assertNotIn("AGENT_ROLE", " ".join(words))

    def test_designer_line(self):
        folder = os.path.dirname(self.shop)
        cmd = ac.agent_command("shop Designer", folder, None, "interior_designer", ac.designer_prompt("shop"),
                               "interior-designer")
        words = shlex.split(cmd)
        self.assertEqual(words[:4], ["AGENT_ROLE=interior-designer", "claude", "--name", "shop Designer"])
        self.assertIn("--model", words)
        self.assertEqual(words[words.index("--model") + 1], "sonnet", "the Helper model default")
        self.assertEqual(words[words.index("--effort") + 1], "medium")
        self.assertEqual(words[-1], ac.designer_prompt("shop"))
        cmd = ac.agent_command("shop Designer", folder, "/tmp/city x", "interior_designer", "hi", "interior-designer")
        self.assertEqual(shlex.split(cmd)[:2], ["AGENT_CITY_DIR=/tmp/city x", "AGENT_ROLE=interior-designer"])

    def test_designer_model_is_the_helper_model_setting(self):
        cfg = os.path.join(self.base, "cfg")
        os.makedirs(cfg, exist_ok=True)
        with open(os.path.join(cfg, "settings.json"), "w") as fh:
            json.dump({"pluginConfigs": {"auto-pipeline@auto-pipeline": {"options": {"helper_model": "opus-5.5:medium"}}}}, fh)
        folder = os.path.dirname(self.repo("pos", conf=CONF + "interior_designer=sonnet-5:low\n"))
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": cfg}):
            words = shlex.split(ac.agent_command("pos Designer", folder, None, "interior_designer", "hi",
                                                 "interior-designer"))
        self.assertEqual(words[words.index("--model") + 1], "opus")
        self.assertEqual(words[words.index("--effort") + 1], "medium")

    def test_prompt(self):
        p = ac.designer_prompt("shop")
        self.assertEqual(p.count("\n"), 0)
        self.assertIn("interior designer of the shop floor", p)
        self.assertIn(os.path.join(ROOT, "agents", "interior-designer.md"), p)
        self.assertIn("Do not run agent-start.sh", p)


class TestAddDesigner(OfficeCase):
    def setUp(self):
        super().setUp()
        self.tid = self.known(self.shop)

    def test_opens_one_designer(self):
        c = self.client()
        code, body = self.state.add_designer(self.tid, self.now)
        self.assertEqual(code, 200, body)
        self.assertEqual((body["state"], body["name"], body["role"]), ("opening", "shop Designer", "designer"))
        folder, title, command = self.calls[0]
        self.assertEqual((folder, title), (os.path.dirname(self.shop), "shop Designer"))
        self.assertTrue(command.startswith("AGENT_ROLE=interior-designer claude --name "), command)
        adding = self.events(c, "adding")
        self.assertTrue(adding and all(e.get("kind") == "designer" for e in adding))

    def test_its_own_hold(self):
        self.assertEqual(self.state.add_designer(self.tid, self.now)[0], 200)
        self.assertEqual(self.state.add_designer(self.tid, self.now), (409, {"error": "busy"}))
        self.assertEqual(self.state.add_agent(self.tid, self.now)[0], 200, "add agent is not blocked by it")

    def test_one_designer_per_floor(self):
        self.feed(line("UserPromptSubmit", "d1", self.shop, role="interior-designer"))
        self.assertEqual(self.state.add_designer(self.tid, self.now), (409, {"error": "designer-here"}))

    def test_the_usual_answers(self):
        self.assertEqual(self.state.add_designer("zz", self.now), (400, {"error": "bad"}))
        self.assertEqual(self.state.add_designer("0badc0de", self.now), (404, {"error": "unknown"}))
        self.kind = "plain"
        code, body = self.state.add_designer(self.tid, self.now)
        self.assertEqual((code, body["state"]), (200, "plain"))
        self.assertIn("AGENT_ROLE=interior-designer", body["command"])
        self.kind = "orca"
        self.res["ok"] = False
        self.assertEqual(self.state.add_designer(self.tid, self.now)[1]["state"], "cap")
        self.assertEqual(self.state.add_designer(self.tid, self.now, force=True)[0], 200)

    def test_leave_closes_its_terminal(self):
        self.state.add_designer(self.tid, self.now)
        self.feed(line("UserPromptSubmit", "d1", self.shop, role="interior-designer"))
        c = self.client()
        self.assertEqual(self.state.leave_designer(self.tid), (200, {}))
        self.assertEqual(self.closed, ["term_abc-1"])
        self.assertTrue([e for e in self.events(c, "leave") if e.get("id") == "s:d1"], "it leaves the page at once")
        self.assertEqual(self.state.leave_designer(self.tid), (404, {"error": "none"}))

    def test_bye_file_makes_it_leave(self):
        self.state.add_designer(self.tid, self.now)
        self.feed(line("UserPromptSubmit", "d1", self.shop, role="interior-designer"))
        os.makedirs(self.floors_dir, exist_ok=True)
        open(os.path.join(self.floors_dir, self.tid + ".bye"), "w").close()
        self.state.scan_floors()
        self.assertEqual(self.closed, ["term_abc-1"])
        self.assertFalse(os.path.exists(os.path.join(self.floors_dir, self.tid + ".bye")))

    def test_open_session_returns_the_handle(self):
        fake = os.path.join(self.base, "rt.sh")
        with open(fake, "w") as fh:
            fh.write('#!/bin/bash\necho \'{"terminal": {"handle": "term_9f-2", "title": "x"}}\'\n')
        self.assertEqual(ac.open_session(self.base, "t", "true", runtime=fake), (True, "term_9f-2"))


class TestAgentFile(unittest.TestCase):
    def test_interior_designer_md(self):
        path = os.path.join(ROOT, "agents", "interior-designer.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        head = text.split("---")[1]
        self.assertIn("name: interior-designer", head)
        self.assertIn("model: sonnet", head)
        for word in ("agent-city.sh floor rules", "agent-city.sh floor set", "agent-city.sh floor bye", "README",
                     "CLAUDE.md", "60 lines", "top-level folder", "可以走了"):
            self.assertIn(word, text)
        self.assertRegex(text, r"(?i)never (edit|change)")


# ---------------------------------------------------------------------------
# O5 HTTP
# ---------------------------------------------------------------------------

class TestHttp(OfficeCase):
    def setUp(self):
        super().setUp()
        self.tid = self.known(self.shop)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ac.CityHandler)
        self.server.daemon_threads = True
        self.server.city = self.state
        self.server.hub = None
        self.server.page_bytes = b""
        self.server.assets_dir = self.base
        self.port = self.server.server_address[1]
        self.server.host_set = {"127.0.0.1:%d" % self.port, "localhost:%d" % self.port}
        self.server.origin_set = {"http://127.0.0.1:%d" % self.port, "http://localhost:%d" % self.port}
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        super().tearDown()

    def call(self, path, body=None, method="POST", token="tok", origin="own"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        headers = {}
        if token is not None:
            headers["X-City-Token"] = token
        if origin is not None:
            headers["Origin"] = "http://127.0.0.1:%d" % self.port if origin == "own" else origin
        data = json.dumps(body).encode() if body is not None else None
        if data is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        text = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(text or b"null")
        except ValueError:
            return resp.status, None

    def test_floors(self):
        self.assertEqual(self.call("/api/floors", {"floors": [self.tid]}), (200, {"floors": [self.tid]}))
        self.assertEqual(self.call("/api/floors", {"floors": [self.tid], "x": 1})[0], 400)
        self.assertEqual(self.call("/api/floors", {"floors": [self.tid]}, token=None)[0], 403)
        self.assertEqual(self.call("/api/floors", {"floors": [self.tid]}, origin="http://evil.example")[0], 403)

    def test_design(self):
        self.assertEqual(self.call("/api/design", {"terr": self.tid, "design": GOOD}), (200, {"design": GOOD}))
        code, body = self.call("/api/design", {"terr": self.tid, "design": good(c_carpet="#000000")})
        self.assertEqual((code, body["error"]), (422, "bad"))
        self.assertEqual(self.call("/api/design", {"terr": self.tid, "undo": True}), (200, {"design": None}))
        self.assertEqual(self.call("/api/design", {"terr": self.tid, "skip": True}), (200, {}))
        for bad in ({"terr": self.tid}, {"terr": self.tid, "undo": 1}, {"terr": self.tid, "design": GOOD, "undo": True},
                    {"terr": self.tid, "design": GOOD, "path": "/etc"}):
            self.assertEqual(self.call("/api/design", bad)[0], 400, bad)
        self.assertEqual(self.call("/api/design", {"terr": self.tid, "design": GOOD}, token="no")[0], 403)

    def test_designer(self):
        code, body = self.call("/api/designer", {"terr": self.tid, "force": False})
        self.assertEqual((code, body["state"]), (200, "opening"))
        self.assertEqual(self.call("/api/designer", {"terr": self.tid, "force": False, "name": "x"})[0], 400)
        self.assertEqual(self.call("/api/designer/leave", {"terr": self.tid}), (404, {"error": "none"}))
        self.assertEqual(self.call("/api/designer", {"terr": self.tid, "force": False}, origin=None)[0], 403)

    def test_get_changes_nothing(self):
        for path in ("/api/floors", "/api/design", "/api/designer", "/api/designer/leave"):
            self.call(path, method="GET")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.state.floors(), [self.tid])


# ---------------------------------------------------------------------------
# O7 the command line
# ---------------------------------------------------------------------------

class TestCli(OfficeCase):
    def setUp(self):
        super().setUp()
        self.tid = self.known(self.shop)   # world.json now knows shop

    def run_cli(self, *args, stdin=None, cwd=None):
        env = dict(os.environ, AGENT_CITY_HOME=self.base)
        return subprocess.run([sys.executable, SERVER, "floor"] + list(args) +
                              ["--world", self.world_file, "--floors-dir", self.floors_dir],
                              input=stdin, capture_output=True, text=True, env=env, cwd=cwd or self.base, timeout=60)

    def test_rules(self):
        r = self.run_cli("rules")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), ac.FLOOR_RULES.strip())

    def test_set_and_show_by_name_id_and_dot(self):
        r = self.run_cli("show", "shop")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no design yet", r.stdout)
        r = self.run_cli("set", "shop", "-", stdin=json.dumps(GOOD))
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "saved"), r.stderr)
        self.assertEqual(json.loads(self.run_cli("show", self.tid).stdout), GOOD)
        r = self.run_cli("set", ".", "-", stdin=json.dumps(good(name="点")), cwd=os.path.dirname(self.shop))
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.floors_dir, self.tid + ".history.jsonl"), encoding="utf-8") as fh:
            self.assertEqual(json.loads(fh.readline())["name"], GOOD["name"])

    def test_set_refuses_and_names_the_fields(self):
        r = self.run_cli("set", "shop", "-", stdin=json.dumps(good(c_carpet="#000000", decor=["x"])))
        self.assertEqual(r.returncode, 1)
        self.assertIn("colors.carpet: ", r.stderr)
        self.assertIn("decor: ", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.floors_dir, self.tid + ".json")))
        r = self.run_cli("set", "shop", "-", stdin="{not json")
        self.assertEqual(r.returncode, 1)

    def test_unknown_repo(self):
        r = self.run_cli("show", "nope")
        self.assertEqual(r.returncode, 1)
        self.assertIn("shop", r.stdout + r.stderr, "says which repos it knows")

    def test_bye(self):
        r = self.run_cli("bye", "shop")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.floors_dir, self.tid + ".bye")))

    def test_shell_passes_floor_through(self):
        with open(os.path.join(BIN, "agent-city.sh"), encoding="utf-8") as fh:
            self.assertRegex(fh.read(), r"floor\)\s*shift;.*agent_city\.py\"? floor \"\$@\"")


if __name__ == "__main__":
    unittest.main()
