"""Failing tests for city-layout (requirements/city.md, "Arrange"; owner,
2026-10-01 and 2026-10-02: "let them arrange their city"; approved mock
mock/city-layout-mock.html): the owner places his repos' lands his own way
and hides the repos he does not want to see. This file: the server side (Y3
the saved arrangement and its one guarded endpoint, Y4 the cloud picture).
The page: tests/test_agent_city_layout_page.py.

No test here touches the owner's world.json: every CityState gets a file in
a temp folder, every server process its own AGENT_CITY_HOME.

CONTRACT, server (bin/agent_city.py, Python standard library only)

  THE FILE (world.json, one per machine: every machine keeps its own
  arrangement, nothing of it goes through the team relay)
    A territory's record may carry "hidden": true. Missing or false = shown.
    "v" stays 1; a file without the key loads as before. A slot is the cell
    [i, j] the file holds today, -4..4 each.

  layout(world, plans)
    A hidden territory is not there: no entry in "territories", none of its
    tiles in "rows", no link to it; its neighbours get their outer edge on
    that side. The answer is exactly layout() of the same world without that
    record. Two records may hold the same slot when at most one is shown.
    Every territory of the view says whether its plan has sea: "sea": true |
    false (the page offers no slot just south of such a land).

  add_territory(world, plans, identity, name, lines=0)
    A known identity is never moved (hidden or not), as today. A new one
    takes the first slot in SLOTS order that no SHOWN territory holds, by
    today's rules measured against the shown territories alone: it touches a
    shown territory (when one is shown), it is not the cell just south of a
    shown sea plan, and a sea plan takes no cell with a shown territory just
    south of it. A hidden territory's slot is free.

  CityState.set_layout(lands) -> (code, body)
    LANDS: a list of 1..81 dicts. Keys, and no other:
      "id"      a territory id, 8 lowercase hex digits; needed; once a request
      "slot"    [i, j]: two ints (never a bool, never a float), each -4..4
      "hidden"  true | false
    and at least one of "slot", "hidden" in every dict.
    400 {"error": "bad"}       anything else
    404 {"error": "unknown"}   an id that is no territory of this world
    All of it is applied together; then the rule is checked on the SHOWN
    territories:
      409 {"error": "taken"}   two of them on one slot
      409 {"error": "sea"}     one on the cell just south ([i, j + 1]) of one
                               whose plan has sea
      409 {"error": "empty"}   none is left
    A territory that the request shows again ("hidden": false, it was
    hidden) and gives no "slot": it keeps its slot when the rule holds with
    it there, else it takes the slot add_territory would give a new
    territory of its plan.
    200 {"lands": [{"id", "slot", "hidden"}, ...]}   every territory of the
                               world, in world order, as it is now
    On 400, 404 and 409 nothing changes: the world, the file, no event.
    On 200 world.json is saved before the call returns (save_world: tmp +
    replace). No folder, name or other text is read from LANDS; nothing of
    it reaches a path or a shell.

  WHAT A PAGE GETS (every /events client; the cloud tap is one of them)
    After a 200 that changed something, every client gets a fresh
    {"type": "snapshot", ...}: the one add_client builds for a new page
    (then the remote snapshot, when there is one). People follow their land
    through it: every place in it (the land, the buildings, an agent's
    "office") is the new one.
    A hidden territory is cut out of everything a page hears:
      the snapshot (a new page's too): not in "world" (layout() leaves it
        out), none of its "agents", "govs", "asks", "shows", "adding"; its
        "gov" (the camera home) never names a hidden territory: then it is
        the first shown territory that has a governor, else the first shown
        territory, with that territory's governor state ("idle" without one);
      the remote snapshot: none of its "people" and "govs";
      events: an event of a hidden territory is not sent: its "terr" is
        hidden, or its "id" is an agent of that territory, or it is an
        "ask" / "ask_phase" / "ask_closed" of an ask of that territory, or a
        "remote" event whose inner event has it as "terr";
      "world" events: the shown territories' layout, as the snapshot's.
    The local page learns what is hidden from one list:
      snapshot["hidden"] = [{"id", "name", "people", "wait"}, ...]   one per
        hidden territory, world order ([] when none). people = its agents
        (the Reducer's, as the snapshot counts them). wait = those of them
        that wait for the owner: waiting, stuck, or with an open ask in
        phase "owner" (each person once); plus 1 when its governor's state
        is "waiting" or the governor has an open ask in phase "owner".
      {"type": "hidden", "lands": <that list>}   sent to every client when
        the list changes (a person came or left, waits or stopped waiting).
    The sessions of a hidden repo go on: their lines are reduced as before
    (health, asks, chat, the watchers); only the pages do not hear of them.

  POST /api/layout  {"lands": [...]}  -> set_layout(lands)
    The gate of POST /api/agent/add: Host (127.0.0.1 / localhost), an Origin
    header that is this server's own, the X-City-Token header; else 403. A
    body that is not one JSON object, or that carries any key besides
    "lands" -> 400. GET never changes anything.

  THE CLOUD PICTURE (Y4)
    "hidden" is in CLOUD_DROP, and cloud_clean() of a snapshot has no
    "hidden" key: the cloud never learns that a hidden repo exists.
    cloud_identities() leaves hidden territories out, so the uploader's
    joined set (its key), its counts and its world are the shown repos
    alone; cloud_world() never draws a hidden one.
    After a change the uploader's next sync carries a new picture ("snap").
    From then on no view names the hidden repo, its people or its land.
"""

import copy
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from cityhelp import Mains  # noqa: E402
from relayhelp import join, make_repo  # noqa: E402
from test_agent_city_cloud_upload import UploadCase  # noqa: E402
from test_agent_city_server import wait_for  # noqa: E402

PLANS = ac.load_plans()
# the fixture island: dock is the coast plan, its sea takes the cell south of it ([-1, 1])
LANDS = (("shop", "meadow", [0, 0]), ("blog", "ridge", [1, 0]), ("dock", "harbor", [-1, 0]), ("wood", "woods", [0, 1]))


def record(name, plan, slot, **more):
    rec = {"name": name, "plan": plan, "slot": list(slot), "lines": 400, "peak": 400, "buildings": [],
           "era": "village", "balance": {}, "rules_bad": [], "offices": {}, "rest": False}
    rec.update(more)
    return rec


def world_of(*lands):
    """{"v": 1, ...} of (identity, name, plan, slot[, hidden]) rows."""
    world = {"v": 1, "territories": {}, "order": []}
    for identity, name, plan, slot, *hidden in lands:
        world["territories"][identity] = record(name, plan, slot, **({"hidden": True} if hidden and hidden[0] else {}))
        world["order"].append(identity)
    return world


def line(ev, sid, repo, aid="", role="", **more):
    out = {"ev": ev, "sid": sid, "aid": aid, "at": "", "tool": "Read", "nt": "", "proj": "x", "role": role,
           "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}
    out.update(more)
    return out


def need(case, name, obj=ac):
    case.assertTrue(hasattr(obj, name), "%s is missing" % name)
    return getattr(obj, name)


# ---------------------------------------------------------------------------
# the pure part: layout() and add_territory() with hidden territories
# ---------------------------------------------------------------------------

class TestLayoutLeavesHiddenOut(unittest.TestCase):
    def rows(self, hidden=False):
        return [("/r/shop/.git", "shop", "meadow", [0, 0]), ("/r/blog/.git", "blog", "ridge", [1, 0], hidden),
                ("/r/dock/.git", "dock", "harbor", [-1, 0]), ("/r/wood/.git", "wood", "woods", [0, 1])]

    def test_a_hidden_territory_is_not_in_the_view(self):
        view = ac.layout(world_of(*self.rows(hidden=True)), PLANS)
        self.assertEqual([t["name"] for t in view["territories"]], ["shop", "dock", "wood"])
        blog = ac.territory_id("/r/blog/.git")
        self.assertFalse([l for l in view["links"] if blog in (l["a"], l["b"])], "a link to a hidden territory")
        self.assertEqual(view["x0"] + view["w"] - 1, 10, "the land ends where shop ends: blog's cell is not there")

    def test_it_is_the_layout_of_the_world_without_it(self):
        without = [r for r in self.rows() if r[1] != "blog"]
        self.assertEqual(ac.layout(world_of(*self.rows(hidden=True)), PLANS), ac.layout(world_of(*without), PLANS),
                         "the neighbours must get their own outer edge where the hidden land was")

    def test_a_shown_land_may_stand_on_a_hidden_lands_slot(self):
        rows = [("/r/shop/.git", "shop", "meadow", [0, 0]), ("/r/blog/.git", "blog", "ridge", [1, 0], True),
                ("/r/wood/.git", "wood", "woods", [1, 0])]
        view = ac.layout(world_of(*rows), PLANS)
        self.assertEqual([(t["name"], t["slot"]) for t in view["territories"]], [("shop", [0, 0]), ("wood", [1, 0])])
        self.assertEqual(view, ac.layout(world_of(rows[0], rows[2]), PLANS))

    def test_the_view_says_which_land_has_sea(self):
        view = ac.layout(world_of(*self.rows()), PLANS)
        self.assertEqual({t["name"]: t.get("sea") for t in view["territories"]},
                         {"shop": False, "blog": False, "dock": True, "wood": False})

    def test_hidden_false_is_shown(self):
        world = world_of(*self.rows())
        world["territories"]["/r/blog/.git"]["hidden"] = False
        self.assertEqual(len(ac.layout(world, PLANS)["territories"]), 4)


class TestNewRepoWithHiddenOnes(unittest.TestCase):
    def test_a_hidden_lands_slot_is_free(self):
        world = world_of(("/r/shop/.git", "shop", "meadow", [0, 0]), ("/r/blog/.git", "blog", "ridge", [1, 0], True))
        new = ac.add_territory(world, PLANS, "/r/new/.git", "new")
        self.assertEqual(new["slot"], [1, 0], "the first cell next to the shown land, hidden blog does not hold it")
        self.assertEqual(world["territories"]["/r/blog/.git"]["slot"], [1, 0], "the hidden record is not touched")
        self.assertNotIn("hidden", new)

    def test_it_stands_next_to_a_shown_land_never_next_to_a_hidden_one_alone(self):
        world = world_of(("/r/shop/.git", "shop", "meadow", [0, 0], True), ("/r/blog/.git", "blog", "ridge", [3, 0]))
        new = ac.add_territory(world, PLANS, "/r/new/.git", "new")
        i, j = new["slot"]
        self.assertEqual(abs(i - 3) + abs(j), 1, "it must touch blog (the shown land), got %r" % new["slot"])

    def test_never_on_a_shown_land_nor_in_a_shown_sea(self):
        world = world_of(("/r/dock/.git", "dock", "harbor", [0, 0]), ("/r/shop/.git", "shop", "meadow", [1, 0]))
        for k in range(6):
            new = ac.add_territory(world, PLANS, "/r/new%d/.git" % k, "new%d" % k)
            shown = [tuple(t["slot"]) for t in world["territories"].values() if t is not new and not t.get("hidden")]
            self.assertNotIn(tuple(new["slot"]), shown)
            self.assertNotEqual(new["slot"], [0, 1], "the cell south of the coast land is its sea")

    def test_a_known_hidden_repo_is_never_moved(self):
        world = world_of(("/r/shop/.git", "shop", "meadow", [0, 0]), ("/r/blog/.git", "blog", "ridge", [1, 0], True))
        before = copy.deepcopy(world)
        self.assertIs(ac.add_territory(world, PLANS, "/r/blog/.git", "blog"), world["territories"]["/r/blog/.git"])
        self.assertEqual(world, before)


# ---------------------------------------------------------------------------
# CityState.set_layout
# ---------------------------------------------------------------------------

class Case(unittest.TestCase):
    """A city whose world.json holds the fixture island (LANDS), in a temp folder."""

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_layout_"))
        self.path = os.path.join(self.base, "home", "world.json")
        self.ident = {}
        for name, _, _ in LANDS:
            os.makedirs(os.path.join(self.base, name, ".git"))
            self.ident[name] = os.path.join(self.base, name, ".git")
        ac.save_world(self.path, world_of(*[(self.ident[n], n, p, s) for n, p, s in LANDS]))
        self.mains = Mains()
        self.state = self.make()
        self.now = 1000.0

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def make(self, **kw):
        args = dict(world_path=self.path, token="tok", count_fn=lambda i: 0, main_fn=self.mains,
                    balance_fn=lambda i, r: {"kinds": {}, "files": {}, "bad": []})
        args.update(kw)
        return ac.CityState(decisions_path=os.path.join(self.base, "decisions.jsonl"), **args)

    def tid(self, name):
        return ac.territory_id(self.ident[name])

    def set(self, *lands, state=None):
        fn = need(self, "set_layout", state or self.state)
        return fn([dict(l) for l in lands])

    def ok(self, *lands):
        code, body = self.set(*lands)
        self.assertEqual(code, 200, body)
        return body

    def rec(self, name, state=None):
        return (state or self.state).world["territories"][self.ident[name]]

    def shown(self, state=None):
        with (state or self.state).lock:
            view = (state or self.state)._view()
        return {t["name"]: t["slot"] for t in view["territories"]}

    def file(self):
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)

    def feed(self, *lines):
        for obj in lines:
            self.now += 1
            self.state.feed_line(obj, self.now)

    def client(self, state=None):
        c = (state or self.state).add_client()
        self.drain(c)
        return c

    @staticmethod
    def drain(client):
        out = []
        while not client.queue.empty():
            raw = client.queue.get_nowait()
            raw = raw.decode("utf-8") if isinstance(raw, bytes) else ""
            if "data:" in raw:
                out.append(json.loads(raw.split("data:", 1)[1]))
        return out

    def first_picture(self, state=None):
        c = (state or self.state).add_client()
        return [m for m in self.drain(c) if m.get("type") == "snapshot"][0]


class TestMoveAndSwap(Case):
    def test_a_land_moves_to_a_free_slot(self):
        body = self.ok({"id": self.tid("wood"), "slot": [1, 1]})
        self.assertEqual(self.rec("wood")["slot"], [1, 1])
        self.assertEqual(self.shown(), {"shop": [0, 0], "blog": [1, 0], "dock": [-1, 0], "wood": [1, 1]})
        with self.state.lock:
            wood = [t for t in self.state._view()["territories"] if t["name"] == "wood"][0]
        self.assertEqual((wood["cx"], wood["cz"]), (22, 22), "the view is laid out again")
        self.assertEqual(body, {"lands": [{"id": self.tid(n), "slot": s, "hidden": False}
                                          for n, s in (("shop", [0, 0]), ("blog", [1, 0]), ("dock", [-1, 0]), ("wood", [1, 1]))]})

    def test_two_lands_swap_in_one_request(self):
        self.ok({"id": self.tid("shop"), "slot": [1, 0]}, {"id": self.tid("blog"), "slot": [0, 0]})
        self.assertEqual((self.rec("shop")["slot"], self.rec("blog")["slot"]), ([1, 0], [0, 0]))

    def test_nothing_else_of_the_record_changes(self):
        before = copy.deepcopy(self.rec("wood"))
        self.ok({"id": self.tid("wood"), "slot": [1, 1]})
        after = dict(self.rec("wood"))
        before.pop("slot"), after.pop("slot")
        after.pop("hidden", None)
        self.assertEqual(after, before, "name, plan, lines, buildings stay: only the slot moved")

    def test_a_taken_slot_is_refused_and_nothing_changes(self):
        before = copy.deepcopy(self.state.world)
        raw = open(self.path, "rb").read()
        page = self.client()
        self.assertEqual(self.set({"id": self.tid("wood"), "slot": [1, 0]}), (409, {"error": "taken"}))
        self.assertEqual(self.state.world, before)
        self.assertEqual(open(self.path, "rb").read(), raw)
        self.assertEqual(self.drain(page), [], "a refused arrangement tells the pages nothing")

    def test_half_a_swap_is_refused(self):
        self.assertEqual(self.set({"id": self.tid("shop"), "slot": [1, 0]})[0], 409)
        self.assertEqual(self.rec("shop")["slot"], [0, 0])

    def test_the_cell_south_of_a_coast_land_stays_its_sea(self):
        self.assertEqual(self.set({"id": self.tid("wood"), "slot": [-1, 1]}), (409, {"error": "sea"}))
        self.assertEqual(self.set({"id": self.tid("dock"), "slot": [0, -1]}), (409, {"error": "sea"}),
                         "the coast land itself may not go north of a land")
        self.assertEqual(self.rec("dock")["slot"], [-1, 0])
        self.ok({"id": self.tid("dock"), "slot": [1, 1]})   # nothing south of [1, 1]: fine

    def test_unknown_territory(self):
        self.assertEqual(self.set({"id": "0badc0de", "slot": [2, 2]}), (404, {"error": "unknown"}))

    def test_only_ids_slots_and_the_flag(self):
        t = self.tid("wood")
        before = copy.deepcopy(self.state.world)
        bad = [None, {}, "x", [], [t], [{}], [{"id": t}], [{"slot": [1, 1]}], [{"id": self.ident["wood"], "slot": [1, 1]}],
               [{"id": t.upper(), "slot": [1, 1]}], [{"id": t, "slot": [1, 1], "path": "/tmp/evil"}],
               [{"id": t, "slot": [1, 1], "name": "x"}], [{"id": t, "hidden": "yes"}], [{"id": t, "hidden": 1}],
               [{"id": t, "slot": [1]}], [{"id": t, "slot": [1, 1, 1]}], [{"id": t, "slot": "1,1"}], [{"id": t, "slot": [1, "1"]}],
               [{"id": t, "slot": [True, 1]}], [{"id": t, "slot": [1.0, 1]}], [{"id": t, "slot": [5, 0]}], [{"id": t, "slot": [0, -5]}],
               [{"id": t, "slot": [1, 1]}, {"id": t, "slot": [2, 2]}], [{"id": t, "slot": [1, 1]}] * 82]
        fn = need(self, "set_layout", self.state)
        for lands in bad:
            with self.subTest(lands=str(lands)[:60]):
                self.assertEqual(fn(lands), (400, {"error": "bad"}))
        self.assertEqual(self.state.world, before)


class TestHideAndShow(Case):
    def test_hide_keeps_everything_and_draws_nothing(self):
        before = copy.deepcopy(self.rec("blog"))
        body = self.ok({"id": self.tid("blog"), "hidden": True})
        self.assertEqual(dict(self.rec("blog")), dict(before, hidden=True), "data kept, nothing deleted")
        self.assertEqual(self.shown(), {"shop": [0, 0], "dock": [-1, 0], "wood": [0, 1]})
        self.assertIn({"id": self.tid("blog"), "slot": [1, 0], "hidden": True}, body["lands"])

    def test_the_last_land_cannot_be_hidden(self):
        self.ok(*[{"id": self.tid(n), "hidden": True} for n in ("blog", "dock", "wood")])
        self.assertEqual(self.set({"id": self.tid("shop"), "hidden": True}), (409, {"error": "empty"}))
        self.assertEqual(self.shown(), {"shop": [0, 0]})

    def test_a_hidden_land_holds_no_slot(self):
        self.ok({"id": self.tid("blog"), "hidden": True})
        self.ok({"id": self.tid("wood"), "slot": [1, 0]})
        self.assertEqual(self.shown()["wood"], [1, 0])

    def test_shown_again_at_its_old_slot(self):
        self.ok({"id": self.tid("blog"), "hidden": True})
        self.ok({"id": self.tid("blog"), "hidden": False})
        self.assertFalse(self.rec("blog").get("hidden"))
        self.assertEqual(self.shown()["blog"], [1, 0])

    def test_shown_again_when_its_slot_was_taken(self):
        self.ok({"id": self.tid("blog"), "hidden": True})
        self.ok({"id": self.tid("wood"), "slot": [1, 0]})
        self.ok({"id": self.tid("blog"), "hidden": False})
        self.assertEqual(self.shown(), {"shop": [0, 0], "dock": [-1, 0], "wood": [1, 0], "blog": [0, 1]},
                         "the first free cell next to the island, as a new repo of its plan would get")

    def test_shown_again_at_the_slot_the_request_names(self):
        self.ok({"id": self.tid("blog"), "hidden": True})
        self.ok({"id": self.tid("blog"), "hidden": False, "slot": [1, 1]})
        self.assertEqual(self.shown()["blog"], [1, 1])
        self.ok({"id": self.tid("blog"), "hidden": True})
        self.assertEqual(self.set({"id": self.tid("blog"), "hidden": False, "slot": [0, 0]}), (409, {"error": "taken"}))
        self.assertTrue(self.rec("blog").get("hidden"))

    def test_move_and_hide_in_one_request(self):
        self.ok({"id": self.tid("blog"), "hidden": True}, {"id": self.tid("wood"), "slot": [1, 0]})
        self.assertEqual(self.shown(), {"shop": [0, 0], "dock": [-1, 0], "wood": [1, 0]})

    def test_hiding_the_coast_land_frees_its_sea(self):
        self.ok({"id": self.tid("dock"), "hidden": True})
        self.ok({"id": self.tid("wood"), "slot": [-1, 1]})
        self.assertEqual(self.set({"id": self.tid("dock"), "hidden": False, "slot": [-1, 0]}), (409, {"error": "sea"}))
        self.ok({"id": self.tid("dock"), "hidden": False})
        slot = self.shown()["dock"]
        self.assertNotIn(slot, [[0, 0], [1, 0], [-1, 1]])
        self.assertNotIn([slot[0], slot[1] + 1], [[0, 0], [1, 0], [-1, 1]], "a land may not lie in its sea")


class TestSaved(Case):
    def test_saved_at_once_in_this_machines_file(self):
        self.ok({"id": self.tid("wood"), "slot": [1, 1]}, {"id": self.tid("blog"), "hidden": True})
        data = self.file()
        self.assertEqual(data["v"], 1)
        self.assertEqual(data["territories"][self.ident["wood"]]["slot"], [1, 1])
        self.assertIs(data["territories"][self.ident["blog"]]["hidden"], True)
        self.assertEqual(sorted(os.listdir(os.path.dirname(self.path))), ["world.json"], "no temp file is left")

    def test_a_restart_keeps_the_arrangement(self):
        self.ok({"id": self.tid("wood"), "slot": [1, 1]}, {"id": self.tid("blog"), "hidden": True})
        again = self.make()
        self.assertEqual(self.shown(again), {"shop": [0, 0], "dock": [-1, 0], "wood": [1, 1]})
        self.assertTrue(self.rec("blog", again)["hidden"])
        names = [t["name"] for t in self.first_picture(again)["world"]["territories"]]
        self.assertEqual(names, ["shop", "dock", "wood"])

    def test_a_new_repo_takes_a_free_slot_and_moves_nobody(self):
        self.ok({"id": self.tid("wood"), "slot": [1, 1]}, {"id": self.tid("blog"), "hidden": True})
        os.makedirs(os.path.join(self.base, "fresh", ".git"))
        fresh = os.path.join(self.base, "fresh", ".git")
        self.feed(line("UserPromptSubmit", "n1", fresh))
        shown = self.shown()
        self.assertEqual({n: shown[n] for n in ("shop", "dock", "wood")}, {"shop": [0, 0], "dock": [-1, 0], "wood": [1, 1]})
        self.assertNotIn(shown["fresh"], [[0, 0], [-1, 0], [1, 1], [-1, 1]])
        self.assertTrue(self.rec("blog")["hidden"], "a new repo never shows a hidden one")
        self.assertEqual(self.file()["territories"][fresh]["slot"], shown["fresh"])

    def test_an_old_file_loads_as_before(self):
        self.assertEqual(self.shown(), {n: s for n, _, s in LANDS})
        self.assertNotIn("hidden", self.rec("shop"))


# ---------------------------------------------------------------------------
# what a page gets
# ---------------------------------------------------------------------------

class PageCase(Case):
    """shop has one session (s1); blog has a governor (g1, the lock holder) and one session (b1)."""

    def setUp(self):
        super().setUp()
        self.mains[self.ident["blog"]] = "g1"
        self.feed(line("UserPromptSubmit", "s1", self.ident["shop"]),
                  line("UserPromptSubmit", "g1", self.ident["blog"], pid=str(os.getpid())),
                  line("UserPromptSubmit", "b1", self.ident["blog"]))
        self.blog, self.shop = self.tid("blog"), self.tid("shop")

    def hide(self, name="blog"):
        self.ok({"id": self.tid(name), "hidden": True})

    def of_blog(self, msgs):
        """The messages that tell a page something of blog (the "hidden" list is not one of them)."""
        out = []
        for m in msgs:
            if m.get("type") in ("hidden", "snapshot", "world"):
                continue
            text = json.dumps(m)
            if self.blog in text or "s:b1" in text or "s:b2" in text or '"blog"' in text:
                out.append(m)
        return out


class TestPagesFollow(PageCase):
    def test_every_page_gets_a_fresh_picture(self):
        a, b = self.client(), self.client()
        self.ok({"id": self.tid("wood"), "slot": [1, 1]})
        for page in (a, b):
            snaps = [m for m in self.drain(page) if m.get("type") == "snapshot"]
            self.assertEqual(len(snaps), 1, "one fresh picture for every page")
            slots = {t["name"]: t["slot"] for t in snaps[0]["world"]["territories"]}
            self.assertEqual(slots["wood"], [1, 1])
            self.assertEqual(sorted(x["id"] for x in snaps[0]["agents"]), ["s:b1", "s:s1"])
            self.assertEqual(snaps[0]["hidden"], [])

    def test_an_office_moves_with_its_land(self):
        was = [a for a in self.first_picture()["agents"] if a["id"] == "s:s1"][0].get("office")
        self.assertTrue(was, "the fixture: shop's session has an office in its land")
        page = self.client()
        self.ok({"id": self.shop, "slot": [2, 1]})
        snap = [m for m in self.drain(page) if m.get("type") == "snapshot"][-1]
        now = [a for a in snap["agents"] if a["id"] == "s:s1"][0]["office"]
        self.assertEqual((now["x"] - was["x"], now["z"] - was["z"]), (2 * ac.CELL, 1 * ac.CELL))
        land = [t for t in snap["world"]["territories"] if t["id"] == self.shop][0]
        self.assertEqual((land["cx"], land["cz"]), (2 * ac.CELL, 1 * ac.CELL))
        self.assertIn({"x": now["x"], "z": now["z"]}, [{"x": o["x"], "z": o["z"]} for o in land["offices"]])

    def test_the_same_arrangement_again_tells_nobody(self):
        page = self.client()
        self.ok({"id": self.tid("wood"), "slot": [0, 1]})
        self.assertEqual([m for m in self.drain(page) if m.get("type") == "snapshot"], [])

    def test_a_hidden_repo_is_cut_out_of_the_picture(self):
        _, code = self.state.create_ask({"sid": "b1", "repo": self.ident["blog"], "tool": "Bash",
                                         "input": {"command": "ls"}}, time.time())
        self.assertEqual(code, 200)
        page = self.client()
        self.hide()
        snap = [m for m in self.drain(page) if m.get("type") == "snapshot"][-1]
        self.assertEqual([t["name"] for t in snap["world"]["territories"]], ["shop", "dock", "wood"])
        self.assertEqual([a["id"] for a in snap["agents"]], ["s:s1"])
        self.assertEqual(snap["govs"], [])
        self.assertEqual(snap["asks"], [], "its question is not on the page (the hidden line says somebody waits)")
        self.assertEqual([h["id"] for h in snap["hidden"]], [self.blog])
        self.assertEqual(snap["hidden"], [{"id": self.blog, "name": "blog", "people": 1, "wait": 1}],
                         "the open permission request of b1 is somebody waiting for the owner")
        self.assertNotIn(self.blog, json.dumps(dict(snap, hidden=[])), "nothing else names it")

    def test_a_new_page_gets_the_cut_picture(self):
        self.hide()
        snap = self.first_picture()
        self.assertEqual([t["name"] for t in snap["world"]["territories"]], ["shop", "dock", "wood"])
        self.assertEqual([a["id"] for a in snap["agents"]], ["s:s1"])
        self.assertEqual(snap["hidden"], [{"id": self.blog, "name": "blog", "people": 1, "wait": 0}])

    def test_its_events_are_not_sent(self):
        self.hide()
        page = self.client()
        self.feed(line("PostToolUse", "b1", self.ident["blog"], tool="Edit"),
                  line("UserPromptSubmit", "b2", self.ident["blog"]),
                  line("PostToolUse", "g1", self.ident["blog"], pid=str(os.getpid())),
                  line("PostToolUse", "s1", self.ident["shop"], tool="Edit"))
        self.state.create_ask({"sid": "b1", "repo": self.ident["blog"], "tool": "Bash", "input": {"command": "ls"}}, time.time())
        msgs = self.drain(page)
        self.assertEqual(self.of_blog(msgs), [], "a page must hear nothing of a hidden repo")
        self.assertTrue([m for m in msgs if m.get("type") == "tool" and m.get("id") == "s:s1"], "shop goes on as before")
        self.assertFalse([m for m in msgs if m.get("type") in ("ask", "gov")])

    def test_its_sessions_go_on(self):
        before = self.state.health()["agents"]
        self.hide()
        self.feed(line("UserPromptSubmit", "b2", self.ident["blog"]))
        self.assertEqual(self.state.health()["agents"], before + 1, "hidden is a matter of the picture, the sessions run")
        self.assertEqual(self.state.cloud_counts({self.blog})["people"], 2)

    def test_the_hidden_line_knows_who_waits(self):
        self.hide()
        page = self.client()
        self.feed(line("Stop", "b1", self.ident["blog"]), {"ev": "StopNote", "sid": "b1", "need": "1", "bg": ""})
        msgs = self.drain(page)
        self.assertEqual(self.of_blog(msgs), [])
        lists = [m["lands"] for m in msgs if m.get("type") == "hidden"]
        self.assertEqual(lists[-1], [{"id": self.blog, "name": "blog", "people": 1, "wait": 1}])
        self.feed(line("Stop", "g1", self.ident["blog"], pid=str(os.getpid())), {"ev": "StopNote", "sid": "g1", "need": "1", "bg": ""})
        lists = [m["lands"] for m in self.drain(page) if m.get("type") == "hidden"]
        self.assertEqual(lists[-1][0]["wait"], 2, "its governor waits for the owner too")
        self.feed(line("UserPromptSubmit", "b1", self.ident["blog"]))
        lists = [m["lands"] for m in self.drain(page) if m.get("type") == "hidden"]
        self.assertEqual(lists[-1][0]["wait"], 1)
        self.assertEqual(self.first_picture()["hidden"], [{"id": self.blog, "name": "blog", "people": 1, "wait": 1}])

    def test_no_hidden_event_while_the_list_stays_the_same(self):
        self.hide()
        page = self.client()
        self.feed(line("PostToolUse", "b1", self.ident["blog"], tool="Edit"), line("PostToolUse", "b1", self.ident["blog"]))
        self.assertEqual([m for m in self.drain(page) if m.get("type") == "hidden"], [])

    def test_shown_again_everything_is_back(self):
        self.state.create_ask({"sid": "b1", "repo": self.ident["blog"], "tool": "Bash", "input": {"command": "ls"}}, time.time())
        self.hide()
        self.feed(line("Stop", "b1", self.ident["blog"]), {"ev": "StopNote", "sid": "b1", "need": "1", "bg": ""})
        page = self.client()
        self.ok({"id": self.blog, "hidden": False})
        snap = [m for m in self.drain(page) if m.get("type") == "snapshot"][-1]
        self.assertEqual(snap["hidden"], [])
        self.assertIn("blog", [t["name"] for t in snap["world"]["territories"]])
        b1 = [a for a in snap["agents"] if a["id"] == "s:b1"]
        self.assertTrue(b1 and b1[0]["waiting"], "the person who waited is there, still waiting")
        self.assertEqual([g["terr"] for g in snap["govs"]], [self.blog])
        self.assertEqual([a["terr"] for a in snap["asks"]], [self.blog])
        self.feed(line("PostToolUse", "b1", self.ident["blog"], tool="Edit"))
        self.assertTrue([m for m in self.drain(page) if m.get("id") == "s:b1"], "and its events come again")

    def test_the_camera_home_is_never_a_hidden_land(self):
        state = self.make(start_repo=self.ident["blog"])
        self.assertEqual(self.first_picture(state)["gov"]["terr"], self.blog)
        self.assertEqual(need(self, "set_layout", state)([{"id": self.blog, "hidden": True}])[0], 200)
        gov = self.first_picture(state)["gov"]
        self.assertEqual(gov, {"state": "idle", "terr": self.shop}, "the first shown territory, no governor there")

    def test_world_events_never_draw_it(self):
        self.hide()
        page = self.client()
        os.makedirs(os.path.join(self.base, "fresh", ".git"))
        self.feed(line("UserPromptSubmit", "n1", os.path.join(self.base, "fresh", ".git")))
        worlds = [m["world"] for m in self.drain(page) if m.get("type") == "world"]
        self.assertTrue(worlds, "a new repo is a world event, as today")
        for w in worlds:
            self.assertNotIn("blog", [t["name"] for t in w["territories"]])

    def test_guests_of_a_hidden_repo_are_not_sent(self):
        self.hide()
        page = self.client()

        def remote(terr, rid, ev):
            self.state.push_relay_event({"type": "remote", "who": "Ann", "device": "ann-laptop", "dev": "dev-ann",
                                         "rid": rid, "br": "main", "ev": dict(ev, terr=terr)})
        remote(self.blog, "acme/blog", {"type": "spawn", "id": "r:dev-ann:s:1", "role": "worker", "label": "worker", "task": "t"})
        remote(self.blog, "acme/blog", {"type": "gov", "id": "r:dev-ann:gov", "state": "busy", "present": True})
        remote(self.shop, "acme/shop", {"type": "spawn", "id": "r:dev-ann:s:2", "role": "worker", "label": "worker", "task": "t"})
        got = [m["ev"]["id"] for m in self.drain(page) if m.get("type") == "remote"]
        self.assertEqual(got, ["r:dev-ann:s:2"], "another member's people in a repo hidden HERE are not drawn here")

    def test_the_remote_picture_is_cut_too(self):
        blog, shop = self.blog, self.shop

        class Remote:
            def snapshot_event(self):
                return {"type": "remote_snapshot", "teams": [],
                        "people": [{"id": "r:d:s:1", "terr": blog, "rid": "acme/blog"}, {"id": "r:d:s:2", "terr": shop, "rid": "acme/shop"}],
                        "govs": [{"id": "r:d:gov:" + blog, "terr": blog, "state": "busy"}, {"id": "r:d:gov:" + shop, "terr": shop, "state": "busy"}]}
        self.state.remote = Remote()
        self.hide()
        c = self.state.add_client()
        snap = [m for m in self.drain(c) if m.get("type") == "remote_snapshot"][0]
        self.assertEqual([p["id"] for p in snap["people"]], ["r:d:s:2"])
        self.assertEqual([g["terr"] for g in snap["govs"]], [shop])


# ---------------------------------------------------------------------------
# POST /api/layout: the gate of chat and add agent
# ---------------------------------------------------------------------------

class TestHttp(Case):
    def setUp(self):
        super().setUp()
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
        self.move = {"lands": [{"id": self.tid("wood"), "slot": [1, 1]}]}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        super().tearDown()

    def call(self, method="POST", body=None, token="tok", origin="own", host=None, raw=None, path="/api/layout"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        headers = {}
        if token is not None:
            headers["X-City-Token"] = token
        if origin is not None:
            headers["Origin"] = "http://127.0.0.1:%d" % self.port if origin == "own" else origin
        if host is not None:
            headers["Host"] = host
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
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

    def test_the_page_arranges(self):
        code, body = self.call(body=self.move)
        self.assertEqual(code, 200, body)
        self.assertIn({"id": self.tid("wood"), "slot": [1, 1], "hidden": False}, body["lands"])
        self.assertEqual(self.file()["territories"][self.ident["wood"]]["slot"], [1, 1])
        code, body = self.call(body={"lands": [{"id": self.tid("blog"), "hidden": True}]})
        self.assertEqual(code, 200, body)
        self.assertEqual(self.call(body={"lands": [{"id": self.tid("shop"), "slot": [1, 1]}]}), (409, {"error": "taken"}))
        self.assertEqual(self.call(body={"lands": [{"id": "0badc0de", "hidden": True}]}), (404, {"error": "unknown"}))

    def test_the_gate(self):
        self.assertEqual(self.call(body=self.move, token=None)[0], 403, "no token")
        self.assertEqual(self.call(body=self.move, token="wrong")[0], 403, "wrong token")
        self.assertEqual(self.call(body=self.move, origin=None)[0], 403, "no Origin: not the page")
        self.assertEqual(self.call(body=self.move, origin="http://evil.example")[0], 403, "another site's page")
        self.assertEqual(self.call(body=self.move, host="evil.example")[0], 403, "not asked as 127.0.0.1")
        self.assertEqual(self.call(body=self.move, host="192.168.1.5:%d" % self.port)[0], 403, "not asked as 127.0.0.1")
        self.assertEqual(self.rec("wood")["slot"], [0, 1], "a refused request must never move a land")
        self.assertEqual(self.call(body=self.move)[0], 200, "the page's own request passes the same gate")

    def test_post_only(self):
        for method in ("GET", "PUT", "DELETE"):
            with self.subTest(method=method):
                self.assertNotEqual(self.call(method=method)[0] // 100, 2)
        self.assertEqual(self.rec("wood")["slot"], [0, 1])

    def test_nothing_but_lands(self):
        lands = self.move["lands"]
        for body in ({"lands": lands, "path": "/tmp/evil"}, {"lands": lands, "save": "/tmp/x.json"}, {"lands": lands, "name": "x"},
                     {}, {"land": lands}, {"lands": {"id": self.tid("wood"), "slot": [1, 1]}},
                     {"lands": [dict(lands[0], folder=self.base)]}):
            with self.subTest(body=str(body)[:70]):
                self.assertEqual(self.call(body=body)[0], 400)
        self.assertEqual(self.call(raw=b"not json")[0], 400)
        self.assertEqual(self.call(raw=json.dumps(lands).encode())[0], 400)
        self.assertEqual(self.rec("wood")["slot"], [0, 1])


# ---------------------------------------------------------------------------
# Y4: the cloud picture is this machine's arrangement, a hidden repo is not in it
# ---------------------------------------------------------------------------

class TestCloudCut(PageCase):
    def test_the_cloud_never_hears_the_word(self):
        self.assertIn("hidden", ac.CLOUD_DROP)
        self.assertNotIn("hidden", ac.CLOUD_KEEP)
        self.hide()
        clean = ac.cloud_clean(self.first_picture())
        self.assertNotIn("hidden", clean)
        self.assertNotIn("blog", json.dumps(clean))
        self.assertNotIn(self.blog, json.dumps(clean))

    def test_a_hidden_repo_is_no_cloud_repo(self):
        self.assertIn(self.ident["blog"], self.state.cloud_identities())
        self.hide()
        self.assertNotIn(self.ident["blog"], self.state.cloud_identities())
        world = self.state.cloud_world([self.ident[n] for n, _, _ in LANDS])
        self.assertEqual([t["name"] for t in world["territories"]], ["shop", "dock", "wood"])

    def test_the_cloud_world_is_this_machines_arrangement(self):
        self.ok({"id": self.tid("wood"), "slot": [1, 1]})
        world = self.state.cloud_world([self.ident["shop"], self.ident["wood"]])
        self.assertEqual({t["name"]: t["slot"] for t in world["territories"]}, {"shop": [0, 0], "wood": [1, 1]})

    def test_a_tap_gets_a_fresh_picture_too(self):
        tap = self.state.cloud_open()
        self.drain(tap)
        self.hide()
        snaps = [m for m in self.drain(tap) if m.get("type") == "snapshot"]
        self.assertEqual(len(snaps), 1)
        self.assertEqual([a["id"] for a in snaps[0]["agents"]], ["s:s1"])
        self.feed(line("PostToolUse", "b1", self.ident["blog"], tool="Edit"))
        self.assertEqual(self.of_blog(self.drain(tap)), [])


class TestCloudPicture(UploadCase):
    """A real server process, a fake relay: two joined repos, one gets hidden on this machine."""

    def setUp(self):
        super().setUp()
        self.blog = make_repo(self.base, name="blog", origin="git@github.com:Acme/Blog.git")
        join(self.blog, self.fake.url)

    def token(self):
        with open(os.path.join(self.dir, "token")) as fh:
            return fh.read().strip()

    def layout(self, *lands):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        conn.request("POST", "/api/layout", body=json.dumps({"lands": list(lands)}).encode(),
                     headers={"X-City-Token": self.token(), "Origin": "http://127.0.0.1:%d" % self.port,
                              "Content-Type": "application/json"})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(body or b"null")
        except ValueError:
            return resp.status, None

    def names(self, snap):
        return sorted(t["name"] for t in snap["world"]["territories"])

    def test_a_repo_hidden_here_is_not_in_the_cloud_picture(self):
        self.up(snap_sec="0.5")
        self.add(sid="s1")
        self.add(self.blog, sid="b1")
        self.assertTrue(wait_for(lambda: self.health()["agents"] == 2))
        self.assertTrue(wait_for(lambda: self.last_snap() and self.names(self.last_snap()) == ["blog", "shop"], timeout=10),
                        "both joined repos go up, as today")
        blog_id = ac.territory_id(os.path.join(self.blog, ".git"))
        person = [a["id"] for a in self.last_snap()["agents"] if a["terr"] == blog_id]
        self.assertEqual(len(person), 1)
        code, body = self.layout({"id": blog_id, "hidden": True})
        self.assertEqual(code, 200, body)
        self.assertTrue(wait_for(lambda: self.names(self.last_snap()) == ["shop"], timeout=10),
                        "the next picture must leave the hidden repo out")
        mark = len(self.fake.view_log)
        snap = self.last_snap()
        self.assertEqual([a["terr"] for a in snap["agents"]], [t["id"] for t in snap["world"]["territories"]])
        self.assertTrue(wait_for(lambda: (self.fake.view_of() or {}).get("counts", {}).get("people") == 1, timeout=10))
        self.add(self.blog, sid="b1", tool="Read")
        self.add(sid="s1", tool="Read")
        self.assertTrue(wait_for(lambda: [m for _, v in list(self.fake.view_log)[mark:] for m in v.get("events") or []
                                          if m.get("type") == "tool"], timeout=10), "shop's event never went up")
        time.sleep(0.6)
        later = json.dumps([v for _, v in list(self.fake.view_log)[mark:]])
        self.assertNotIn("blog", later, "no land, no people, no name")
        self.assertNotIn(blog_id, later)
        self.assertNotIn(person[0], later)
        self.assertNotIn("hidden", later)
        local = self.local_snapshot()
        self.assertEqual([h["name"] for h in local["hidden"]], ["blog"], "the local page knows what it hides")

    def test_the_cloud_picture_is_this_machines_arrangement(self):
        self.up(snap_sec="60")
        self.add(sid="s1")
        self.assertTrue(wait_for(lambda: self.last_snap() and self.names(self.last_snap()) == ["shop"], timeout=10))
        shop_id = self.last_snap()["world"]["territories"][0]["id"]
        self.assertEqual(self.last_snap()["world"]["territories"][0]["slot"], [0, 0])
        code, body = self.layout({"id": shop_id, "slot": [2, 1]})
        self.assertEqual(code, 200, body)
        self.assertTrue(wait_for(lambda: self.last_snap()["world"]["territories"][0]["slot"] == [2, 1], timeout=10),
                        "a new picture with the new place must go up with the next sync, not a minute later")
        with open(os.path.join(self.base, "cityhome", "world.json"), encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual([t["slot"] for t in saved["territories"].values()], [[2, 1]])


if __name__ == "__main__":
    unittest.main()
