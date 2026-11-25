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
from cityhelp import make_repo, drain, snapshot  # noqa: E402
from cityhelp import Mains  # noqa: E402
from citypage import ROOT  # noqa: E402
from citypage import ac as ac_chain  # noqa: E402
from citypage import A_REPO  # noqa: E402
from citypage import B_REPO  # noqa: E402
from citypage import TA  # noqa: E402
from citypage import TB  # noqa: E402
import glob  # noqa: E402
import re  # noqa: E402
import threading  # noqa: E402
from citypage import text_zh  # noqa: E402
import cityhelp as tq  # noqa: E402
from cityhelp import SHOP  # noqa: E402
from cityhelp import q_body  # noqa: E402
from cityhelp import InteractCase  # noqa: E402
from cityhelp import gline  # noqa: E402
from citypage import ac as ac_names  # noqa: E402
import shlex  # noqa: E402
from unittest import mock  # noqa: E402
import agent_conf  # noqa: E402
from citypage import run_sim  # noqa: E402
from citypage import style  # noqa: E402
from citypage import rule  # noqa: E402
from citypage import css  # noqa: E402
from cityhelp import RosterCase  # noqa: E402
import agent_city  # noqa: E402
from cityhelp import R as R_reducer  # noqa: E402
from cityhelp import Case as Case_reducer  # noqa: E402
import queue  # noqa: E402
import subprocess  # noqa: E402
from citypage import ac as ac_session_names  # noqa: E402
import citypage as tp  # noqa: E402
from cityhelp import Case as Case_steps  # noqa: E402
from cityhelp import R as R_steps  # noqa: E402

KIND_ZH = {"tower": "测试", "shop": "页面", "workshop": "脚本", "library": "文档", "house": "模块"}
KIND_EN = {"tower": "tests", "shop": "page", "workshop": "script", "library": "docs", "house": "module"}
BARE = ("住宅", "商店", "测试塔", "工坊", "图书馆", "House", "Shop", "Tower", "Workshop", "Library")


# ---------------------------------------------------------------------------
# N1 the subject
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# N2 the name
# ---------------------------------------------------------------------------

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
        self.work()
        snap, _ = snapshot(self.st)
        self.assertIn("hist", snap, "the local page gets the history")

    def test_wired_into_the_server(self):
        serve = inspect.getsource(ac.cmd_serve)
        self.assertIn("history.jsonl", serve)
        self.assertIn("history_path=", serve)
        self.assertIn("sweep_history(time.time())", inspect.getsource(ac.recount_loop))


def decode(raw):
    return json.loads(raw.decode("utf-8").split("data:", 1)[1])


class CityCase_chain(unittest.TestCase):
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
        return ac_chain.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world_path,
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


class TestGovernorPerTerritory(CityCase_chain):

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


class TestServerE2EFindings(CityCase_chain):
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


class TestNoRepoIsTheStartTerritory(CityCase_chain):
    """A session on an older hook sends lines without "repo" (the owner's main manager on plugin 0.4.4):
    they belong to the start territory, the same one as lines with the start repo, never a second state."""

    def new_state(self):
        return ac_chain.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world_path,
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


class TestChain(CityCase_chain):

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


HOOKS = os.path.join(ROOT, "hooks", "hooks.json")


REPO = "/r/shop/.git"


def line(ev, sid, aid="", role="", tool="Read", at="", repo=REPO):
    return {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": "shop", "role": role,
            "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}


def hook_entries(event):
    with open(HOOKS) as fh:
        data = json.load(fh)["hooks"]
    return [h for group in data.get(event, []) for h in group.get("hooks", [])]


class ChatCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_chat_")
        self.chat_path = os.path.join(self.base, "chat.jsonl")
        self.decisions = os.path.join(self.base, "decisions.jsonl")
        self.state = self.make()
        self.gov_id = "gov:" + ac.territory_id(REPO)

    def make(self):
        # city-roles: g1 (team()'s governor) holds the main manager lock of REPO
        return ac.CityState(decisions_path=self.decisions, world_path=None, chat_path=self.chat_path,
                            main_fn=Mains({REPO: "g1"}))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def feed(self, *lines):
        for obj in lines:
            self.state.feed_line(obj, time.monotonic())

    def team(self):
        """A governor g1 (idle), a task manager tm1 (busy), its worker a9."""
        self.feed(line("UserPromptSubmit", "g1"), line("Stop", "g1"),
                  line("UserPromptSubmit", "tm1", role="task-manager"),
                  line("PostToolUse", "tm1", aid="a9", at="worker", role="task-manager"))

    def client(self):
        c = self.state.add_client()
        while not c.queue.empty():
            c.queue.get_nowait()
        return c

    @staticmethod
    def events(client, kind="chat"):
        out = []
        while not client.queue.empty():
            raw = client.queue.get_nowait().decode("utf-8")
            if "data:" not in raw:
                continue
            msg = json.loads(raw.split("data:", 1)[1])
            if msg.get("type") == kind:
                out.append(msg)
        return out


class TestHookWiring(unittest.TestCase):
    def test_say_runs_on_prompt_and_turn_end(self):
        for event in ("UserPromptSubmit", "Stop", "SubagentStop"):
            with self.subTest(event=event):
                says = [h for h in hook_entries(event) if 'agent_city.py" say' in h.get("command", "")]
                self.assertEqual(len(says), 1)
                h = says[0]
                self.assertIn('/on" ]', h["command"])
                self.assertTrue(h["command"].rstrip().endswith("exit 0"))
                self.assertLessEqual(h.get("timeout", 60), 10)
                self.assertFalse(h.get("async"))

    def test_chat_watch_for_sessions_with_a_role(self):
        watches = [h for h in hook_entries("Stop") if 'agent_city.py" chat-watch' in h.get("command", "")]
        self.assertEqual(len(watches), 1)
        h = watches[0]
        self.assertIn('[ -n "${AGENT_ROLE:-}" ]', h["command"])
        self.assertIs(h.get("async"), True)
        self.assertIs(h.get("asyncRewake"), True)

    def test_per_tool_hook_never_says(self):
        for event in ("PreToolUse", "PostToolUse"):
            for h in hook_entries(event):
                self.assertNotIn(" say", h.get("command", ""))


class TestConversation(ChatCase):
    def test_lines_reach_the_right_window(self):
        self.team()
        c = self.client()
        self.state.feed_chat({"sid": "g1", "aid": "", "kind": "prompt", "text": "hi", "at": 1.0})
        self.state.feed_chat({"sid": "tm1", "aid": "", "kind": "reply", "text": "ok", "at": 2.0})
        self.state.feed_chat({"sid": "tm1", "aid": "a9", "kind": "reply", "text": "slice", "at": 3.0})
        events = self.events(c)
        got = [(e["to"], e["entry"]["kind"], e["entry"]["text"]) for e in events]
        self.assertEqual(got, [(self.gov_id, "prompt", "hi"), ("s:tm1", "reply", "ok"), ("a9", "reply", "slice")])
        ids = [e["entry"]["id"] for e in events]
        self.assertEqual(len(set(ids)), 3, "every entry has its own id")

    def test_view(self):
        self.team()
        self.state.feed_chat({"sid": "tm1", "aid": "", "kind": "prompt", "text": "go", "at": 1.0})
        code, body = self.state.chat_view("s:tm1")
        self.assertEqual(code, 200)
        self.assertEqual((body["to"], body["can_send"], body["busy"]), ("s:tm1", True, True))
        self.assertEqual([(e["kind"], e["text"]) for e in body["entries"]], [("prompt", "go")])
        code, body = self.state.chat_view(self.gov_id)
        self.assertEqual((code, body["can_send"], body["busy"]), (200, True, False))
        code, body = self.state.chat_view("a9")
        self.assertEqual((code, body["can_send"]), (200, False))
        self.assertEqual(self.state.chat_view("s:nobody")[0], 404)

    def test_bad_lines_are_ignored(self):
        self.team()
        for bad in ({"sid": "tm1", "kind": "reply"}, {"sid": "tm1", "kind": "shout", "text": "x"},
                    {"kind": "reply", "text": "x"}, {"sid": "tm1", "kind": "reply", "text": 5}):
            self.state.feed_chat(bad)
        self.assertEqual(self.state.chat_view("s:tm1")[1]["entries"], [])

    def test_only_the_last_chat_keep(self):
        self.team()
        for i in range(ac.CHAT_KEEP + 5):
            self.state.feed_chat({"sid": "tm1", "aid": "", "kind": "reply", "text": str(i), "at": float(i)})
        entries = self.state.chat_view("s:tm1")[1]["entries"]
        self.assertEqual(len(entries), ac.CHAT_KEEP)
        self.assertEqual(entries[-1]["text"], str(ac.CHAT_KEEP + 4))


class TestSending(ChatCase):
    def test_send_rules(self):
        self.team()
        self.assertEqual(self.state.chat_send("s:tm1", "", 0)[0], 400)
        self.assertEqual(self.state.chat_send("s:tm1", 5, 0)[0], 400)
        self.assertEqual(self.state.chat_send("s:tm1", "x" * (ac.CHAT_TEXT_MAX + 1), 0)[0], 400)
        code, body = self.state.chat_send("a9", "hi", 0)
        self.assertEqual((code, body), (400, {"error": "subagent"}))
        self.assertEqual(self.state.chat_send("r:dev:s:1", "hi", 0)[0], 400)
        self.assertEqual(self.state.chat_send("rg:x", "hi", 0)[0], 400)
        self.assertEqual(self.state.chat_send("s:nobody", "hi", 0)[0], 404)

    def test_queued_then_delivered_when_idle(self):
        self.team()
        c = self.client()
        code, body = self.state.chat_send("s:tm1", "先停一下，改用 B 方案", 100.0)
        self.assertEqual((code, body["state"]), (200, "queued"))
        msg_id = body["id"]
        queued = self.events(c)
        self.assertEqual([(e["to"], e["entry"]["kind"], e["entry"]["state"]) for e in queued],
                         [("s:tm1", "owner", "queued")])
        self.assertEqual(self.state.chat_next("tm1", "w1", 0), {"state": "none"}, "busy: it waits")
        self.feed(line("Stop", "tm1", role="task-manager"))
        got = self.state.chat_next("tm1", "w1", 0)
        self.assertEqual((got["state"], got["id"], got["text"]), ("message", msg_id, "先停一下，改用 B 方案"))
        done = self.events(c)
        self.assertEqual([(e["entry"]["id"], e["entry"]["state"]) for e in done], [(msg_id, "delivered")])
        self.assertEqual(self.state.chat_next("tm1", "w1", 0), {"state": "none"}, "delivered once")
        with open(self.decisions) as fh:
            last = json.loads(fh.read().strip().splitlines()[-1])
        self.assertEqual((last["by"], last["verb"], last["sid"], last["text"]),
                         ("owner", "message", "tm1", "先停一下，改用 B 方案"))
        with open(self.chat_path) as fh:
            kept = [json.loads(x) for x in fh if x.strip()]
        self.assertEqual([(x["sid"], x["kind"], x["text"]) for x in kept],
                         [("tm1", "owner", "先停一下，改用 B 方案")])

    def test_newer_watcher_wins(self):
        self.team()
        self.feed(line("Stop", "tm1", role="task-manager"))
        self.assertEqual(self.state.chat_next("tm1", "w1", 0), {"state": "none"})
        self.assertEqual(self.state.chat_next("tm1", "w2", 0), {"state": "none"})
        self.assertEqual(self.state.chat_next("tm1", "w1", 0), {"state": "replaced"})

    def test_session_end_turns_queued_undelivered(self):
        self.team()
        c = self.client()
        _, body = self.state.chat_send("s:tm1", "hello", 0)
        self.events(c)
        self.feed(line("SessionEnd", "tm1", role="task-manager"))
        self.assertEqual([(e["entry"]["id"], e["entry"]["state"]) for e in self.events(c)],
                         [(body["id"], "undelivered")])
        self.assertEqual(self.state.chat_send("s:tm1", "again", 0)[0], 404)

    def test_the_governor_gets_messages_through_gov_next(self):
        self.team()
        _, body = self.state.chat_send(self.gov_id, "总督，今天先做 A", 0)
        got = self.state.gov_next("g1", REPO, "gw1", 0)
        self.assertEqual((got["state"], got["id"], got["text"]), ("message", body["id"], "总督，今天先做 A"))

    def test_delivered_messages_survive_a_restart(self):
        self.team()
        self.state.feed_chat({"sid": "tm1", "aid": "", "kind": "prompt", "text": "go", "at": 1.0})
        with open(self.chat_path, "a") as fh:
            fh.write(json.dumps({"sid": "tm1", "aid": "", "kind": "prompt", "text": "go", "at": 1.0}) + "\n")
        self.feed(line("Stop", "tm1", role="task-manager"))
        self.state.chat_send("s:tm1", "hello", 0)
        self.state.chat_next("tm1", "w1", 0)
        again = self.make()
        again.feed_line(line("UserPromptSubmit", "tm1", role="task-manager"), time.monotonic())
        texts = [(e["kind"], e["text"]) for e in again.chat_view("s:tm1")[1]["entries"]]
        self.assertEqual(texts, [("prompt", "go"), ("owner", "hello")])


class TestLoadChat(unittest.TestCase):
    def test_keeps_the_last_per_key_and_rewrites(self):
        base = tempfile.mkdtemp(prefix="city_loadchat_")
        try:
            path = os.path.join(base, "chat.jsonl")
            with open(path, "w") as fh:
                for i in range(ac.CHAT_KEEP + 3):
                    fh.write(json.dumps({"sid": "s1", "aid": "", "kind": "reply", "text": str(i), "at": i}) + "\n")
                fh.write("garbage\n")
                fh.write(json.dumps({"sid": "s2", "aid": "", "kind": "prompt", "text": "p", "at": 1}) + "\n")
            got = ac.load_chat(path)
            self.assertEqual(len([x for x in got if x["sid"] == "s1"]), ac.CHAT_KEEP)
            self.assertEqual(got[0]["text"], "3")
            self.assertEqual(got[-1]["sid"], "s2")
            with open(path) as fh:
                self.assertEqual(len([x for x in fh if x.strip()]), ac.CHAT_KEEP + 1)
            self.assertEqual(ac.load_chat(os.path.join(base, "none.jsonl")), [])
        finally:
            shutil.rmtree(base, ignore_errors=True)


GRACE = 0.3


def line_delivery(ev, sid, role="", repo=REPO):
    return {"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "Read", "nt": "", "proj": "shop",
            "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "ask": "",
            "wt": "", "file": "", "tp": "", "pid": ""}


class DeliveryCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_delivery_")
        self.mains = Mains({REPO: "g1"})
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=None,
                               chat_path=os.path.join(self.base, "chat.jsonl"),
                               main_fn=self.mains, listen_grace_sec=GRACE)
        self.gov_page = "gov:" + ac.territory_id(REPO)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def feed(self, *lines):
        for obj in lines:
            self.st.feed_line(obj, time.monotonic())

    def idle_session(self, sid, role=""):
        self.feed(line_delivery("UserPromptSubmit", sid, role), line_delivery("Stop", sid, role))

    def entry(self, to, entry_id):
        return next(e for e in self.st.chat_view(to)[1]["entries"] if e["id"] == entry_id)

    def wait_in_thread(self, fn):
        out = {}
        t = threading.Thread(target=lambda: out.update(r=fn()))
        t.start()
        time.sleep(0.2)
        return t, out


class TestEachRoleIsReached(DeliveryCase):
    def test_a_helper_gets_its_message(self):
        """R6: roleless, not the holder -> its own page; gov-watch fell back to chat_next."""
        self.idle_session("h1")
        self.assertEqual(self.st.gov_next("h1", REPO, "w1", 0.1), {"state": "not-main"})
        t, out = self.wait_in_thread(lambda: self.st.chat_next("h1", "w1", 3))
        code, body = self.st.chat_send("s:h1", "helper, look", 0)
        t.join(5)
        self.assertEqual((code, body["state"]), (200, "queued"))
        self.assertEqual((out["r"]["state"], out["r"]["text"]), ("message", "helper, look"))
        self.assertEqual(self.entry("s:h1", body["id"])["state"], "delivered")

    def test_the_governor_gets_its_message(self):
        self.idle_session("g1")
        t, out = self.wait_in_thread(lambda: self.st.gov_next("g1", REPO, "gw", 3))
        code, body = self.st.chat_send(self.gov_page, "governor, look", 0)
        t.join(5)
        self.assertEqual((out["r"]["state"], out["r"]["text"]), ("message", "governor, look"))

    def test_a_task_manager_gets_its_message(self):
        self.idle_session("tm1", "task-manager")
        t, out = self.wait_in_thread(lambda: self.st.chat_next("tm1", "cw", 3))
        code, body = self.st.chat_send("s:tm1", "tm, look", 0)
        t.join(5)
        self.assertEqual((out["r"]["state"], out["r"]["text"]), ("message", "tm, look"))

    def test_only_the_holder_is_given_the_governor_page(self):
        self.idle_session("g1")
        self.idle_session("h1")
        self.assertEqual(self.st.gov_next("h1", REPO, "hw", 0.1), {"state": "not-main"})
        t, out = self.wait_in_thread(lambda: self.st.chat_next("h1", "hw", 1))
        self.st.gov_next("g1", REPO, "gw", 0.1)
        self.st.chat_send(self.gov_page, "for the governor", 0)
        t.join(5)
        self.assertEqual(out["r"], {"state": "none"}, "a helper never takes the governor's message")


class TestHonestState(DeliveryCase):
    def test_idle_and_nobody_listening_is_not_delivered_at_once(self):
        self.idle_session("h1")
        time.sleep(GRACE + 0.2)
        code, body = self.st.chat_send("s:h1", "anyone?", 0)
        self.assertEqual(code, 200)
        self.assertEqual((body["state"], body.get("why")), ("undelivered", "not-listening"))
        e = self.entry("s:h1", body["id"])
        self.assertEqual((e["state"], e.get("why")), ("undelivered", "not-listening"))
        self.assertEqual(self.st.chat_next("h1", "late", 0.2), {"state": "none"},
                         "an undelivered message is never given later")

    def test_right_after_its_stop_it_still_waits(self):
        self.idle_session("h1")
        code, body = self.st.chat_send("s:h1", "just stopped", 0)
        self.assertEqual(body["state"], "queued")
        self.assertEqual(self.st.chat_next("h1", "w1", 0.5)["text"], "just stopped")

    def test_busy_waits_then_the_sweep_tells_the_truth(self):
        self.feed(line_delivery("UserPromptSubmit", "h1"))           # busy
        client = self.st.add_client()
        client.queue.get_nowait()
        code, body = self.st.chat_send("s:h1", "after your turn", 0)
        self.assertEqual(body["state"], "queued")
        time.sleep(GRACE + 0.2)
        self.st.sweep_chat()
        self.assertEqual(self.entry("s:h1", body["id"])["state"], "queued", "busy: its turn is not over")
        self.feed(line_delivery("Stop", "h1"))                       # idle, but no watcher ever comes
        time.sleep(GRACE + 0.2)
        while not client.queue.empty():
            client.queue.get_nowait()
        self.st.sweep_chat()
        e = self.entry("s:h1", body["id"])
        self.assertEqual((e["state"], e.get("why")), ("undelivered", "not-listening"))
        told = []
        while not client.queue.empty():
            raw = client.queue.get_nowait()
            if isinstance(raw, bytes) and b"data:" in raw:
                told.append(json.loads(raw.decode("utf-8").split("data:", 1)[1]))
        self.assertIn(("chat", "s:h1", "undelivered"),
                      [(m.get("type"), m.get("to"), m.get("entry", {}).get("state")) for m in told])
        self.st.remove_client(client)

    def test_a_listening_watcher_keeps_it_queued(self):
        self.idle_session("h1")
        time.sleep(GRACE + 0.2)
        self.st.chat_next("h1", "w1", 0.05)                  # a watcher just polled
        code, body = self.st.chat_send("s:h1", "you there", 0)
        self.assertEqual(body["state"], "queued")
        self.st.sweep_chat()
        self.assertEqual(self.entry("s:h1", body["id"])["state"], "queued")

    def test_no_governor_the_governor_page_says_so(self):
        self.mains.clear()                                  # nobody holds the lock
        self.feed(line_delivery("UserPromptSubmit", "h1"))           # a citizen makes the territory known
        time.sleep(GRACE + 0.2)
        code, body = self.st.chat_send(self.gov_page, "governor?", 0)
        self.assertEqual(code, 200)
        self.assertEqual((body["state"], body.get("why")), ("undelivered", "not-listening"))

    def test_a_holder_that_loses_the_seat_is_told_not_main(self):
        self.idle_session("g1")
        t, out = self.wait_in_thread(lambda: self.st.gov_next("g1", REPO, "gw", 5))
        self.mains.clear()
        self.st.check_seats(time.monotonic())
        t.join(8)
        self.assertEqual(out["r"], {"state": "not-main"})


class TestPageWords(unittest.TestCase):
    def test_queued_is_not_called_sent(self):
        zh = text_zh()
        self.assertEqual(zh.get("chat.state.queued"), "排队中")
        self.assertEqual(zh.get("chat.why.notListening"), "它没在听，收不到")

    def test_the_reason_is_shown(self):
        import test_agent_city_page as chat_tests  # test-slim: TestPageChat lives in the page file now
        page = chat_tests.TestPageChat("test_chat_html")
        entries = [{"id": 1, "kind": "owner", "text": "x", "at": 1, "state": "undelivered", "why": "not-listening"},
                   {"id": 2, "kind": "owner", "text": "y", "at": 2, "state": "queued"}]
        html = page.html((entries, "h", False))[0]
        self.assertIn("没送到", html)
        self.assertIn("它没在听，收不到", html)
        self.assertIn("排队中", html)
        self.assertNotIn("已发送", html)


class TestDecisionsHome(unittest.TestCase):
    def test_default_follows_agent_city_home(self):
        base = tempfile.mkdtemp(prefix="city_dhome_")
        old = os.environ.get("AGENT_CITY_HOME")
        try:
            os.environ["AGENT_CITY_HOME"] = base
            st = ac.CityState(world_path=None)
            self.assertEqual(st.decisions_path, os.path.join(base, "decisions.jsonl"))
            del os.environ["AGENT_CITY_HOME"]
            st = ac.CityState(world_path=None)
            self.assertEqual(st.decisions_path, os.path.expanduser("~/.claude/agent-city/decisions.jsonl"))
        finally:
            if old is None:
                os.environ.pop("AGENT_CITY_HOME", None)
            else:
                os.environ["AGENT_CITY_HOME"] = old
            shutil.rmtree(base, ignore_errors=True)

    def test_every_test_state_names_its_decisions_file(self):
        """A CityState made by a test without decisions_path would write the owner's real file."""
        bad = []
        for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
            if os.path.basename(path) == os.path.basename(__file__):
                continue    # this file sets AGENT_CITY_HOME around its own two on purpose
            text = open(path, encoding="utf-8").read()
            for m in re.finditer(r"\b(?:ac|agent_city)\.CityState\(", text):
                call = text[m.end():m.end() + 800]
                depth, end = 1, len(call)
                for i, ch in enumerate(call):
                    depth += (ch == "(") - (ch == ")")
                    if depth == 0:
                        end = i
                        break
                if "decisions_path" not in call[:end]:
                    bad.append("%s:%d" % (os.path.basename(path), text[:m.start()].count("\n") + 1))
        self.assertEqual(bad, [], "pass decisions_path=<temp> in these")


CJK = re.compile(r"[㐀-鿿＀-￯　-〿]")


def R(ev, sid="s", aid="", at="", tool="", nt="", role="", ask="", **kw):
    line = {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": nt, "proj": "p",
            "role": role, "desc": "", "sub": "", "q": "", "ask": ask}
    line.update(kw)
    return line


NOTE = {"ev": "StopNote", "sid": "tm1", "need": "1", "bg": ""}


class TestNoticesFollowLang(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_lang_")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_unreadable_world_notice_en(self):
        path = os.path.join(self.base, "world.json")
        with open(path, "w") as fh:
            fh.write("{not json")
        _world, notice = ac.load_world(path, lang="en")
        self.assertTrue(notice)
        self.assertIsNone(CJK.search(notice), notice)

    def test_unreadable_world_notice_zh_default(self):
        path = os.path.join(self.base, "world.json")
        with open(path, "w") as fh:
            fh.write("{not json")
        _world, notice = ac.load_world(path)
        self.assertIsNotNone(CJK.search(notice), notice)


class TestIdleIsNotAQuestion(unittest.TestCase):
    def setUp(self):
        self.r = ac.Reducer()
        self.r.feed(R("UserPromptSubmit", sid="main"), 1.0)
        self.r.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Write"), 1.0)

    def test_idle_prompt_is_nothing(self):
        self.assertEqual(self.r.feed(R("Notification", sid="tm1", role="task-manager", nt="idle_prompt"), 2.0), [])
        a = [a for a in self.r.snapshot()["agents"] if a["id"] == "s:tm1"][0]
        self.assertEqual((a["waiting"], a["stuck"]), (False, False))

    def test_a_reply_that_asks_is_waiting_once(self):
        self.assertEqual(self.r.feed(dict(NOTE), 2.0), [{"type": "waiting", "id": "s:tm1"}])
        self.assertEqual(self.r.feed(dict(NOTE), 3.0), [])
        a = [a for a in self.r.snapshot()["agents"] if a["id"] == "s:tm1"][0]
        self.assertEqual((a["waiting"], a["stuck"]), (True, False))

    def test_resume_comes_first(self):
        self.r.feed(dict(NOTE), 2.0)
        out = self.r.feed(R("PostToolUse", sid="tm1", role="task-manager", tool="Edit"), 3.0)
        self.assertEqual(out, [{"type": "resume", "id": "s:tm1"}, {"type": "tool", "id": "s:tm1", "tool": "Edit", "name": "Edit"}])
        a = [a for a in self.r.snapshot()["agents"] if a["id"] == "s:tm1"][0]
        self.assertFalse(a["waiting"])

    def test_prompt_resumes(self):
        self.r.feed(dict(NOTE), 2.0)
        self.assertEqual(self.r.feed(R("UserPromptSubmit", sid="tm1", role="task-manager"), 3.0),
                         [{"type": "resume", "id": "s:tm1"}])

    def test_governor_idle_prompt_is_nothing(self):
        self.assertEqual(self.r.feed(R("Notification", sid="main", nt="idle_prompt"), 2.0), [])
        self.assertEqual(self.r.snapshot()["gov"], {"state": "busy"})

    def test_every_snapshot_agent_has_waiting(self):
        for a in self.r.snapshot()["agents"]:
            self.assertIn("waiting", a)


class TestIdleInTheCity(tq.BuildCase):
    def test_idle_prompt_no_event_at_all(self):
        self.st.feed_line(dict(self.line("tm1"), role="task-manager", tool="Write", file=""), 1000.0)
        tq.drain(self.client)
        self.st.feed_line(dict(self.line("tm1"), ev="Notification", nt="idle_prompt", role="task-manager",
                               tool="", file=""), 1001.0)
        types = [e["type"] for e in tq.drain(self.client)]
        for bad in ("waiting", "stuck", "relay", "ask"):
            self.assertNotIn(bad, types)

    def test_waiting_no_relay_no_ask_no_stuck(self):
        self.st.feed_line(dict(self.line("tm1"), role="task-manager", tool="Write", file=""), 1000.0)
        tq.drain(self.client)
        self.st.feed_line(dict(NOTE), 1001.0)
        types = [e["type"] for e in tq.drain(self.client)]
        self.assertIn("waiting", types)
        for bad in ("stuck", "relay", "ask"):
            self.assertNotIn(bad, types)


ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")


def perm_body(sid="s1", aid="", tool="Bash", command="rm -rf build/", repo=SHOP,
              role="worker", **extra):
    inp = {"command": command, "description": "clean the build"} if tool == "Bash" else extra.pop("input")
    return {"sid": sid, "aid": aid, "at": "worker" if aid else "", "role": role,
            "cwd": "/r/shop", "repo": repo, "tool": tool, "input": inp}


class TestToken(InteractCase):
    def test_token_file_private_and_long(self):
        self.start()
        path = os.path.join(self.dir, "token")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertRegex(self.token(), r"^[A-Za-z0-9_\-]{32,}$")

    def test_new_token_every_start(self):
        proc = self.start()
        first = self.token()
        proc.terminate()
        proc.wait(5)
        self.start()
        self.assertNotEqual(self.token(), first)

    def test_page_gets_the_token(self):
        page = os.path.join(self.base, "page.html")
        with open(page, "w") as fh:
            fh.write('<!doctype html><meta name="city-token" content="__CITY_TOKEN__"><p>x</p>')
        self.start("--idle-sec", "60", "--page", page, "--decisions", self.decisions)
        body = self.get("/")[2].decode("utf-8")
        self.assertIn('content="%s"' % self.token(), body)
        self.assertNotIn("__CITY_TOKEN__", body)

    def test_api_needs_the_token(self):
        self.start()
        self.assertEqual(self.api("GET", "/api/asks", token=None)[0], 403)
        self.assertEqual(self.api("GET", "/api/asks", token="wrong" * 8)[0], 403)
        self.assertEqual(self.api("GET", "/api/asks")[0], 200)

    def test_a_refused_request_changes_nothing(self):
        self.start()
        self.assertEqual(self.api("POST", "/api/ask", perm_body(), token=None)[0], 403)
        self.assertEqual(self.asks(), [])


class TestHostAndOrigin(InteractCase):
    def test_foreign_host_is_refused_even_for_the_page(self):
        self.start()
        status, _, body = self.api("GET", "/", token=None, host="evil.example:%d" % self.port)
        self.assertEqual(status, 403)
        self.assertNotIn(self.token().encode(), body if isinstance(body, bytes) else b"")
        self.assertEqual(self.api("GET", "/api/asks", host="evil.example")[0], 403)

    def test_loopback_hosts_pass(self):
        self.start()
        self.assertEqual(self.api("GET", "/api/asks", host="localhost:%d" % self.port)[0], 200)
        self.assertEqual(self.api("GET", "/api/asks", host="127.0.0.1:%d" % self.port)[0], 200)

    def test_foreign_origin_is_refused_with_a_good_token(self):
        self.start()
        status = self.api("POST", "/api/ask", perm_body(), origin="http://evil.example")[0]
        self.assertEqual(status, 403)
        self.assertEqual(self.asks(), [])

    def test_own_origin_passes(self):
        self.start()
        self.assertEqual(self.api("POST", "/api/ask", perm_body(), origin=self.origin)[0], 200)

    def test_decide_needs_the_page_origin(self):
        self.start()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.decide({"id": ask_id, "verb": "allow"}, origin=None)[0], 403)
        self.assertEqual(self.decide({"id": ask_id, "verb": "allow"}, origin="http://evil.example")[0], 403)
        self.assertIsNotNone(self.view(ask_id))

    def test_no_cors_header_and_no_preflight(self):
        self.start()
        status, headers, _ = self.api("OPTIONS", "/api/decide", origin="http://evil.example")
        self.assertFalse(200 <= status < 300)
        self.assertNotIn("access-control-allow-origin", headers)
        _, headers, _ = self.api("GET", "/api/asks", origin=self.origin)
        self.assertNotIn("access-control-allow-origin", headers)

    def test_bad_bodies(self):
        self.start()
        self.assertEqual(self.api("POST", "/api/ask", raw=b"[1,2]")[0], 400)
        self.assertEqual(self.api("POST", "/api/ask", raw=b"not json")[0], 400)
        self.assertEqual(self.api("POST", "/api/ask", raw=b'{"a":"' + b"x" * 70000 + b'"}')[0], 413)
        self.assertEqual(self.api("POST", "/api/ask", {"sid": "s1", "input": {}})[0], 400)
        self.assertEqual(self.asks(), [])


class TestGovernorGone(InteractCase):
    def test_session_end_forgets_the_governor(self):
        self.start()
        self.gov_next(sid="gs")
        self.assertEqual(self.health()["governors"], 1)
        out = {}
        t = threading.Thread(target=lambda: out.update(r=self.gov_next(sid="gs", timeout=20)))
        t.start()
        time.sleep(0.5)
        self.append(json.dumps({"ev": "SessionEnd", "sid": "gs", "aid": "", "at": "", "tool": "",
                                "nt": "", "proj": "shop", "role": "", "desc": "", "sub": "",
                                "q": "", "klen": ""}) + "\n")
        t.join(5)
        self.assertEqual(out.get("r", {}).get("state"), "replaced")
        self.assertEqual(self.health()["governors"], 0)
        self.assertEqual(self.view(self.ask(q_body()))["why"], "no-governor")


class TestGovernorWatcherSlot(InteractCase):
    def test_a_new_watcher_replaces_the_old_one(self):
        self.start()
        out = {}
        t = threading.Thread(target=lambda: out.update(r=self.gov_next(watcher="old", timeout=20)))
        t.start()
        time.sleep(0.5)
        self.gov_next(watcher="new")
        t.join(5)
        self.assertEqual(out.get("r", {}).get("state"), "replaced")
        self.assertEqual(self.gov_next(watcher="old")["state"], "replaced")


class TestDecisionsLog(InteractCase):
    def test_every_close_is_one_line(self):
        self.start()
        a = self.ask(perm_body(sid="s1"))
        b = self.ask(q_body(sid="s2"))
        self.decide({"id": a, "verb": "deny", "reason": "no"})
        self.decide({"id": b, "answers": {"Which port?": "4791"}})
        rows = self.decisions_lines()
        self.assertEqual([r["id"] for r in rows], [a, b])
        for row in rows:
            with self.subTest(row=row):
                self.assertEqual(set(row), {"t", "id", "by", "verb", "repo", "agent", "task", "tool",
                                            "what", "text", "reason"})
                self.assertRegex(row["t"], ISO)
                self.assertEqual(row["by"], "owner")
                self.assertEqual(row["repo"], SHOP)
        self.assertEqual((rows[0]["verb"], rows[0]["reason"], rows[0]["what"]), ("deny", "no", "rm -rf build/"))
        self.assertEqual((rows[1]["verb"], rows[1]["text"], rows[1]["tool"]), ("answer", "4791", "AskUserQuestion"))

    def test_nothing_written_before_a_decision(self):
        self.start()
        self.ask(perm_body())
        self.assertFalse(os.path.exists(self.decisions))


class TestStartTerritory(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_land_")
        self.path = os.path.join(self.base, "world.json")
        self.calls = []

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def state(self, start_repo, world=None, main_fn=None):
        if world is not None:
            ac.save_world(self.path, world)

        def count(identity):
            self.calls.append(identity)
            return 4000
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.path,
                            start_repo=start_repo, main_fn=main_fn)

    def snapshot(self, st):
        client = st.add_client()
        raw = client.queue.get_nowait()
        text = raw.decode() if isinstance(raw, bytes) else raw
        return json.loads(text.split("data:", 1)[1].strip())

    def saved(self):
        with open(self.path) as fh:
            return json.load(fh)["territories"]

    def test_the_start_repo_is_there_at_once(self):
        st = self.state("/r/shop/.git")
        self.assertIn("/r/shop/.git", st.world["territories"])
        self.assertEqual(st.world["territories"]["/r/shop/.git"]["name"], "shop")
        self.assertIn("/r/shop/.git", self.saved(), "saved at once, before any line")
        snap = self.snapshot(st)
        self.assertEqual([t["name"] for t in snap["world"]["repos"]], ["shop"])
        self.assertEqual(snap["gov"]["terr"], ac.territory_id("/r/shop/.git"),
                         "no governor yet: the governor belongs to the start territory")

    def test_a_plain_folder_is_a_start_territory_too(self):
        st = self.state("/r/notes")
        self.assertEqual([t["name"] for t in self.snapshot(st)["world"]["repos"]], ["notes"])

    def test_no_start_repo_adds_nothing(self):
        for start in (None, ""):
            with self.subTest(start=start):
                st = self.state(start)
                self.assertEqual(st.world["territories"], {})

    def test_old_territories_without_a_repo_are_dropped_on_load(self):
        w = ac.new_world()
        ac.add_territory(w, "dir:notes", "notes")
        ac.add_territory(w, "/r/shop/.git", "shop")
        st = self.state(None, world=w)
        self.assertEqual(list(st.world["territories"]), ["/r/shop/.git"])
        self.assertEqual(st.world["order"], ["/r/shop/.git"])
        self.assertEqual(list(self.saved()), ["/r/shop/.git"], "dropped from world.json at once")
        snap = self.snapshot(st)
        self.assertTrue(snap.get("notice"), "one line in the page log, never silent")
        self.assertEqual([t["name"] for t in snap["world"]["repos"]], ["shop"])

    def test_a_line_without_repo_goes_to_the_start_territory(self):
        # city-roles: g1 is the start repo's main manager, so it governs there
        st = self.state("/r/shop/.git", main_fn=lambda identity: (os.getpid(), "g1") if identity == "/r/shop/.git" else None)
        client = st.add_client()
        start_id = ac.territory_id("/r/shop/.git")
        for missing in (False, True):
            obj = json.loads(gline("UserPromptSubmit", sid="g1", repo="", proj="notes"))
            if missing:
                obj.pop("repo")
            st.feed_line(obj, 1000.0)
        st.feed_line(json.loads(gline("SubagentStart", sid="g1", aid="a1", at="worker", repo="", proj="notes")), 1001.0)
        self.assertEqual(list(st.world["territories"]), ["/r/shop/.git"], "old sessions (no repo) never create a territory")
        events = []
        while not client.queue.empty():
            raw = client.queue.get_nowait()
            if isinstance(raw, bytes) and raw.startswith(b"data:"):
                events.append(json.loads(raw.decode().split("data:", 1)[1].strip()))
        self.assertFalse([e for e in events if e.get("type") == "world"], "no world event for a line without repo")
        spawn = [e for e in events if e.get("type") == "spawn"]
        self.assertEqual([e["terr"] for e in spawn], [start_id], "its people stand on the start territory")
        snap = self.snapshot(st)
        self.assertEqual([(a["id"], a["terr"]) for a in snap["agents"]], [("a1", start_id)])
        self.assertEqual(snap["gov"]["terr"], start_id)

    def test_a_line_without_repo_and_no_start_territory(self):
        st = self.state(None)
        st.feed_line(json.loads(gline("SubagentStart", sid="g1", aid="a1", at="worker", repo="", proj="notes")), 1001.0)
        self.assertEqual(st.world["territories"], {})
        self.assertEqual([(a["id"], a["terr"]) for a in self.snapshot(st)["agents"]], [("a1", "")])


REPO_names = "/work/names/app/.git"


TYPE = "auto-pipeline:worker"


DESC = "Slice A: city server and hook"


class NamesCase(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_names_")
        self.world = os.path.join(self.base, "world.json")
        self.now = 1000.0
        self.st = self.state()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def state(self, done_ttl=600):
        st = ac_names.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world,
                          done_ttl=done_ttl)
        self.client = st.add_client()
        self.client.queue.get_nowait()
        return st

    def line(self, st, ev, aid="", at="", tool="", sub="", desc="", dt=1.0):
        self.now += dt
        st.feed_line({"ev": ev, "sid": "tm", "aid": aid, "at": at, "tool": tool, "nt": "", "proj": "app",
                      "role": "task-manager", "desc": desc, "sub": sub, "q": "", "klen": "", "repo": REPO_names,
                      "kind": "", "ask": ""}, self.now)

    def spawns(self):
        out = []
        while not self.client.queue.empty():
            raw = self.client.queue.get_nowait()
            if isinstance(raw, bytes):
                e = json.loads(raw.decode("utf-8").split("data:", 1)[1])
                if e.get("type") == "spawn":
                    out.append(e)
        return out

    def hire(self, st, aid, desc=DESC):
        self.line(st, "PreToolUse", tool="Agent", sub=TYPE, desc=desc)
        self.line(st, "SubagentStart", aid=aid, at=TYPE)

    def saved(self):
        with open(self.world, encoding="utf-8") as fh:
            return json.load(fh).get("names", {})


class TestBareType(unittest.TestCase):

    def test_plugin_prefix_goes(self):
        self.assertEqual(ac_names.bare_type("auto-pipeline:worker"), "worker")
        self.assertEqual(ac_names.bare_type("a:b:merge-deputy"), "merge-deputy")
        self.assertEqual(ac_names.bare_type("worker"), "worker")
        self.assertEqual(ac_names.bare_type(""), "")


class TestTypesWithoutPlugin(NamesCase):

    def test_spawn_role_and_label_are_bare(self):
        self.hire(self.st, "w1")
        s = [e for e in self.spawns() if e["id"] == "w1"][0]
        self.assertEqual(s["role"], "worker")
        self.assertEqual(s["label"], "worker")
        self.assertEqual(s["task"], DESC)

    def test_auto_spawn_is_bare_too(self):
        self.line(self.st, "PostToolUse", aid="w7", at=TYPE, tool="Read")
        s = [e for e in self.spawns() if e["id"] == "w7"][0]
        self.assertEqual((s["role"], s["label"]), ("worker", "worker"))
        self.assertNotIn(":", s["task"])


class TestNamesSurviveRestart(NamesCase):

    def test_restart_keeps_label_and_task(self):
        self.hire(self.st, "w1")
        self.assertEqual(self.saved().get("w1"), {"label": "worker", "task": DESC})
        again = self.state()
        self.line(again, "PostToolUse", aid="w1", at=TYPE, tool="Read")
        s = [e for e in self.spawns() if e["id"] == "w1"][0]
        self.assertEqual((s["label"], s["task"]), ("worker", DESC))

    def test_a_citizen_that_left_is_forgotten(self):
        st = self.state(done_ttl=5)
        self.hire(st, "w1")
        self.line(st, "SubagentStop", aid="w1", at=TYPE)
        self.line(st, "PostToolUse", tool="Read", dt=10.0)
        self.assertNotIn("w1", self.saved())

    def test_at_most_200(self):
        for i in range(230):
            self.hire(self.st, "w%d" % i, desc="task %d" % i)
        names = self.saved()
        self.assertLessEqual(len(names), 200)
        self.assertIn("w229", names)
        self.assertNotIn("w0", names)

    def test_old_world_without_names_loads(self):
        w = ac_names.new_world()
        ac_names.add_territory(w, REPO_names, "app")
        ac_names.save_world(self.world, w)
        st = self.state()
        self.line(st, "PostToolUse", aid="w3", at=TYPE, tool="Read")
        self.assertEqual([e["label"] for e in self.spawns() if e["id"] == "w3"], ["worker"])
        self.assertEqual([n for n in os.listdir(self.base) if ".bad-" in n], [])


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


def line_office(ev, sid, repo, aid="", role="", at=""):
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
        self.feed(line_office("UserPromptSubmit", sid, identity), line_office("Stop", sid, identity))
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
        self.feed(line_office("PreToolUse", "s-blog", self.blog))
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


class TestRoles(OfficeCase):
    def spawns(self, *lines):
        c = self.client()
        self.feed(*lines)
        return {e["id"]: e for e in self.events(c, "spawn")}

    def test_session_roles(self):
        self.mains[self.shop] = "gov"
        self.known(self.shop, sid="gov")
        tid = ac.territory_id(self.shop)
        sp = self.spawns(line_office("UserPromptSubmit", "h1", self.shop),
                         line_office("UserPromptSubmit", "t1", self.shop, role="task-manager"),
                         line_office("UserPromptSubmit", "d1", self.shop, role="interior-designer"))
        self.assertEqual(sp["s:h1"]["role"], "helper", "no AGENT_ROLE = 助理")
        self.assertEqual(sp["s:t1"]["role"], "task-manager")
        self.assertEqual(sp["s:d1"]["role"], "designer")
        for sid in ("h1", "t1", "d1"):
            self.assertEqual(sp["s:" + sid].get("up"), "gov:" + tid, "the tree: 区经理 > 设计师, 助理, 经理")

    def test_a_subagent_still_hangs_on_its_session(self):
        self.known(self.shop, sid="h1")
        sp = self.spawns(line_office("PreToolUse", "h1", self.shop, aid="w1", at="worker"))
        ws = [e for e in sp.values() if e["role"] == "worker"]
        self.assertEqual(len(ws), 1)
        self.assertEqual(ws[0].get("up"), "s:h1")


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
        st.feed_line(line_office("UserPromptSubmit", "x1", self.shop), self.now)
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
        self.feed(line_office("UserPromptSubmit", "d1", self.shop, role="interior-designer"))
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
        self.feed(line_office("UserPromptSubmit", "d1", self.shop, role="interior-designer"))
        c = self.client()
        self.assertEqual(self.state.leave_designer(self.tid), (200, {}))
        self.assertEqual(self.closed, ["term_abc-1"])
        self.assertTrue([e for e in self.events(c, "leave") if e.get("id") == "s:d1"], "it leaves the page at once")
        self.assertEqual(self.state.leave_designer(self.tid), (404, {"error": "none"}))

    def test_bye_file_makes_it_leave(self):
        self.state.add_designer(self.tid, self.now)
        self.feed(line_office("UserPromptSubmit", "d1", self.shop, role="interior-designer"))
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


BIN = os.path.join(ROOT, "bin")


class Case(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_clean_"))
        self.world_file = os.path.join(self.base, "world.json")
        self.shop = os.path.join(self.base, "shop", ".git")
        self.blog = os.path.join(self.base, "blog", ".git")
        for g in (self.shop, self.blog):
            os.makedirs(g)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def make(self, **kw):
        return ac.CityState(decisions_path=os.path.join(self.base, "decisions.jsonl"), world_path=self.world_file,
                            floors_dir=os.path.join(self.base, "floors"), main_fn=Mains(), **kw)

    def saved(self):
        with open(self.world_file, encoding="utf-8") as fh:
            return json.load(fh)


class TestIslandIsGone(unittest.TestCase):
    def test_module_names(self):
        for name in ("load_plans", "count_lines", "growth", "radius", "territory_tiles", "open_plots", "layout",
                     "balance_of", "scan_sites", "read_sites", "GAPS", "SLOTS"):
            self.assertFalse(hasattr(ac, name), name)

    def test_state_names(self):
        for name in ("recount", "requality", "scan_sites", "set_layout", "balance_api"):
            self.assertFalse(hasattr(ac.CityState, name), name)

    def test_plans_file_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(BIN, "agent-city-plans.json")))

    def test_old_kwargs_are_refused(self):
        tmp = tempfile.mkdtemp(prefix="city_clean_kw_")
        try:
            for kw in ({"plans": {}}, {"count_fn": lambda i: 0}, {"balance_fn": lambda i, r: {}}):
                with self.assertRaises(TypeError):
                    ac.CityState(decisions_path=os.path.join(tmp, "d.jsonl"), **kw)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestWorldFile(Case):
    def test_only_office_keys_are_saved(self):
        st = self.make()
        st.feed_line(line_office("UserPromptSubmit", "a", self.shop), 1.0)
        st.feed_line(line_office("UserPromptSubmit", "b", self.blog), 1.0)
        st.skip_design(ac.territory_id(self.shop))
        w = self.saved()
        self.assertTrue(set(w) <= {"v", "territories", "order", "floors", "names", "gov_seen"}, set(w))
        for rec in w["territories"].values():
            self.assertTrue(set(rec) <= {"name", "reno_asked"}, set(rec))

    def test_an_island_world_loads_and_sheds_its_island(self):
        island = {"v": 1, "order": [self.shop, self.blog],
                  "territories": {
                      self.shop: {"name": "shop", "plan": "grassland", "slot": [0, 0], "lines": 900, "peak": 900,
                                  "buildings": [{"plot": 1, "type": "house"}], "era": "town", "balance": {},
                                  "rules_bad": [], "offices": {}, "rest": None},
                      self.blog: {"name": "blog", "plan": "coast", "slot": [1, 0], "lines": 10, "hidden": True,
                                  "buildings": [], "sites": {}}},
                  "names": {"s:x": {"label": "shop Helper", "task": ""}}, "gov_seen": {}}
        with open(self.world_file, "w", encoding="utf-8") as fh:
            json.dump(island, fh)
        st = self.make()
        self.assertFalse([f for f in os.listdir(self.base) if ".bad-" in f], "never moved aside")
        self.assertEqual(st.floors(), [ac.territory_id(self.shop)])
        st.set_floors([ac.territory_id(self.shop), ac.territory_id(self.blog)])
        w = self.saved()
        self.assertEqual(set(w["territories"]), {self.shop, self.blog})
        self.assertEqual(w["names"], island["names"])
        for rec in w["territories"].values():
            self.assertTrue(set(rec) <= {"name", "reno_asked"}, set(rec))


T1, T2 = "aaaa0001", "bbbb0002"


COLORS = {"accent": "#2E7D6B", "carpet": "#E4DCCB", "manager_floor": "#D9C2A0", "pantry_floor": "#EEEAE0",
          "desk": "#EFDAB5", "desk_leg": "#BBA27C", "chair": "#3E4560", "meeting_rug": "#A9BCE0", "manager_rug": "#C97B66"}


def view(designs=None):
    return {"v": 2, "repos": [{"id": T1, "name": "shop", "here": True, "n": 0}, {"id": T2, "name": "blog", "here": True, "n": 1}],
            "floors": [T1, T2], "designs": designs or {}, "asked": [T1, T2]}


def agent(aid, role, terr, status=""):
    return {"id": aid, "role": role, "label": aid, "task": aid, "stuck": False, "waiting": False, "done": False,
            "status": status, "tools": {}, "terr": terr, "relay": "", "lead": "", "office": None, "up": "gov:" + terr}


SNAP = r"""
function snap(v, agents){ apply({ type: 'snapshot', world: v, agents: agents || [], govs: [], gov: { state: 'idle', terr: v.floors[0] },
  asks: [], governors: 0, adding: [], hist: {} }); }
"""


def sim(driver, payload, required=("officeState", "apply", "citizens")):
    return run_sim(SNAP + driver, payload, required=required)


def base_items():
    return ac.default_layout(3, 1, ["none", "none", "none"])["items"]


def cases():
    """Layouts with the server's verdict: (name, items, first layout problem zh or None)."""
    out = []
    def add(name, items):
        probs = [p for p in ac.check_design({"v": 2, "name": "x", "colors": COLORS, "layout": {"items": items}})
                 if p["field"].startswith("layout")]
        out.append((name, items, probs[0]["zh"] if probs else None))
    add("default", base_items())
    it = base_items(); it[0] = dict(it[0], x=6.8, z=0.0); add("out", it)
    it = base_items(); it[0] = dict(it[0], x=-1.0, z=-5.6); add("lift", it)
    it = base_items(); it[1] = dict(it[1], x=it[0]["x"] + 0.4, z=it[0]["z"]); add("overlap", it)
    it = base_items(); it[0] = {"k": "tm", "x": -6.2, "z": 5.6, "yaw": 0}; it.append({"k": "decor", "id": "safe", "x": -4.8, "z": 6.1, "yaw": 90}); add("boxed", it)
    it = [dict(i, yaw=90) if i["k"] == "tm" else i for i in base_items()]; add("turned", it)
    it = base_items() + [{"k": "plant", "x": -5.7, "z": -0.6, "yaw": 0}]; add("plant on chair", it)
    it = base_items() + [{"k": "decor", "id": "cashier", "x": 0.4, "z": 2.8, "yaw": 180}]; add("free decor", it)
    return out


class TestSameAsServer(unittest.TestCase):
    def test_constants(self):
        out = sim("__out = { P: PIECES, Z: FIXED_ZONES, B: FIXED_BLOCKS, M: FLOOR_MATERIALS };", {},
                  required=("PIECES", "FIXED_ZONES", "FIXED_BLOCKS", "FLOOR_MATERIALS"))
        server = {k: {"zh": v["zh"], "walk": list(v["walk"]), "foot": list(v["foot"]),
                      "seat": list(v["seat"]) if v["seat"] else None, "min": v["min"], "max": v["max"]}
                  for k, v in ac.LAYOUT_KINDS.items()}
        self.assertEqual(out["P"], server)
        self.assertEqual(out["Z"], [[z, list(r)] for z, r in ac.FIXED_ZONES])
        self.assertEqual(out["B"], [list(b) for b in ac.FIXED_BLOCKS])
        self.assertEqual(out["M"], list(ac.FLOOR_MATERIALS))

    def test_default_plan(self):
        args = [(3, 1, ["none"] * 3), (7, 3, ["robot", "conveyor", "gears"]), (1, 2, ["none", "plants", "none"])]
        out = sim("__out = __payload.args.map(a => defaultPlan(a[0], a[1], a[2]));", {"args": args}, required=("defaultPlan",))
        self.assertEqual(out, [ac.default_layout(*a) for a in args])

    def test_check_plan(self):
        cs = cases()
        out = sim("__out = __payload.cases.map(c => checkPlan({ items: c[1] }));", {"cases": cs}, required=("checkPlan",))
        for (name, _, why), got in zip(cs, out):
            with self.subTest(case=name):
                self.assertEqual(got["ok"], why is None, got)
                if why:
                    self.assertEqual(got["why"], why)
        self.assertTrue(any(c[2] for c in cs) and any(c[2] is None for c in cs), "the cases cover both verdicts")


class TestPlanOnTheFloor(unittest.TestCase):
    def test_plan_of_and_seats(self):
        items = base_items()
        items[0] = {"k": "tm", "x": -6.2, "z": 5.6, "yaw": 90}
        items[1] = {"k": "tm", "x": 0.4, "z": 2.8, "yaw": 180}
        meet = next(i for i in items if i["k"] == "meet")
        meet.update(x=-2.8, z=3.0)
        d2 = {"v": 2, "name": "自由", "colors": COLORS, "layout": {"items": items},
              "materials": {"carpet": "wood", "manager_floor": "marble", "pantry_floor": "lava"}}
        self.assertEqual([p for p in ac.check_design(dict(d2, materials={"carpet": "wood", "manager_floor": "marble", "pantry_floor": "checker"}))], [])
        out = sim("""
snap(__payload.view, __payload.agents);
const t1 = __payload.t1, t2 = __payload.t2;
const c0 = byId('s:a'), c1 = byId('s:b');
const loc = s => [Math.round(s.x * 100) / 100, Math.round(s.y * 100) / 100];
__out = { plan: planOf(t1).items.length, def: planOf(t2).items.filter(i => i.k === 'tm').length,
          s0: loc(seatOf(c0)), s1: loc(seatOf(c1)), meet: MEET.length,
          oldFree: walkable(-5.7, -1.3), newBlocked: walkable(-6.2, 5.6),
          mats: themeOf(t1).materials, matsDefault: themeOf(t2).materials };
""", {"view": view({T1: d2}), "t1": T1, "t2": T2,
      "agents": [agent("s:a", "task-manager", T1), agent("s:b", "task-manager", T1), agent("s:c", "task-manager", T2)]},
            required=("planOf", "seatOf", "walkable", "themeOf", "byId"))
        self.assertEqual(out["plan"], len(items))
        self.assertEqual(out["def"], 2, "no v 2 design: the default plan, one desk more than managers")
        # desk 1 turned 90: its seat is at local (0, 0.78) -> (x + 0.78, z)
        self.assertEqual(out["s0"], [round(-6.2 + 0.78, 2), 5.6])
        # desk 2 turned 180: (x, z - 0.78)
        self.assertEqual(out["s1"], [0.4, round(2.8 - 0.78, 2)])
        self.assertTrue(out["oldFree"], "the old desk place is free")
        self.assertFalse(out["newBlocked"], "the desk's new place blocks")
        self.assertEqual(out["mats"], {"carpet": "wood", "manager_floor": "marble", "pantry_floor": "tile"}, "unknown -> base")
        self.assertEqual(out["matsDefault"], {"carpet": "plain", "manager_floor": "wood", "pantry_floor": "tile"})


def design(items, **kw):
    d = {"v": 2, "name": "自由摆放", "colors": dict(COLORS), "layout": {"items": items}}
    d.update(kw)
    return d


def fields(obj):
    probs = ac.check_design(obj)
    for p in probs:
        assert p.get("zh") and p.get("en"), p
    return probs


class TestConstants(unittest.TestCase):
    def test_kinds(self):
        K = ac.LAYOUT_KINDS
        self.assertEqual(set(K), {"tm", "helper", "meet", "decor", "plant"})
        self.assertEqual((K["tm"]["zh"], tuple(K["tm"]["walk"]), tuple(K["tm"]["foot"]), tuple(K["tm"]["seat"]), K["tm"]["min"], K["tm"]["max"]),
                         ("经理桌", (-0.75, 0.75, -0.4, 0.4), (-0.75, 0.75, -0.4, 1.1), (0, 0.78), 1, 9))
        self.assertEqual((K["helper"]["min"], K["helper"]["max"], tuple(K["helper"]["seat"])), (1, 3, (0, 0.74)))
        self.assertEqual((K["meet"]["min"], K["meet"]["max"], K["meet"]["seat"]), (1, 1, None))
        self.assertEqual((K["decor"]["min"], K["decor"]["max"]), (0, 8))
        self.assertEqual((K["plant"]["min"], K["plant"]["max"]), (0, 8))

    def test_fixed(self):
        self.assertEqual([z[0] for z in ac.FIXED_ZONES], ["电梯", "区经理室", "区经理室的门口", "茶水间", "白板"])
        self.assertEqual(tuple(ac.FIXED_ZONES[0][1]), (-2.85, 0.75, -7, -5.0))
        self.assertEqual(len(ac.FIXED_BLOCKS), 12)
        self.assertEqual(ac.FLOOR_MATERIALS, ("plain", "wood", "herringbone", "tile", "bigtile", "marble", "concrete", "checker"))


class TestDefault(unittest.TestCase):
    def test_shape(self):
        items = ac.default_layout(4, 2, ["robot", "none", "plants"])["items"]
        tm = [(i["x"], i["z"]) for i in items if i["k"] == "tm"]
        self.assertEqual(tm, [(-5.7, -1.3), (-3.2, -1.3), (-0.7, -1.3), (-5.7, 1.6)])
        self.assertEqual([(i["x"], i["z"]) for i in items if i["k"] == "helper"], [(2.9, -1.6), (4.4, -1.6)])
        self.assertEqual([(i["x"], i["z"]) for i in items if i["k"] == "meet"], [(4.6, 4.0)])
        self.assertEqual([(i["x"], i["z"], i.get("s", 1)) for i in items if i["k"] == "plant"], [(-3.2, 5.0, 1), (1.3, 6.5, 0.7)])
        self.assertEqual([(i["id"], i["x"], i["z"], i["yaw"]) for i in items if i["k"] == "decor"],
                         [("robot", -5.2, 6.35, 180), ("plants", 6.45, 0.75, 270)])
        self.assertTrue(all(i["yaw"] == 0 for i in items if i["k"] != "decor"))

    def test_no_plant_with_seven_desks(self):
        items = ac.default_layout(7, 1, ["none"] * 3)["items"]
        self.assertEqual(len([i for i in items if i["k"] == "plant"]), 1)

    def test_every_default_passes(self):
        for n_tm in range(1, 10):
            for n_h in (1, 2, 3):
                d = design(ac.default_layout(n_tm, n_h, ["robot", "conveyor", "gears"])["items"])
                self.assertEqual(ac.check_design(d), [], (n_tm, n_h))


class TestV2Shape(unittest.TestCase):
    def test_good(self):
        self.assertEqual(fields(design(base_items())), [])
        self.assertEqual(fields(design(base_items(), why="自己摆的",
                                       materials={"carpet": "wood", "manager_floor": "herringbone", "pantry_floor": "checker"})), [])

    def test_v1_still_works_and_decor_is_v1_only(self):
        v1 = {"v": 1, "name": "老版", "colors": dict(COLORS), "decor": ["robot", "none", "plants"]}
        self.assertEqual(fields(v1), [])
        bad = design(base_items(), decor=["robot", "none", "none"])
        self.assertIn("decor", [p["field"] for p in fields(bad)])
        v1_layout = dict(v1, layout={"items": base_items()})
        self.assertIn("layout", [p["field"] for p in fields(v1_layout)])

    def test_materials(self):
        f = [p["field"] for p in fields(design(base_items(), materials={"carpet": "lava", "manager_floor": "wood", "pantry_floor": "tile"}))]
        self.assertIn("materials.carpet", f)
        f = [p["field"] for p in fields(design(base_items(), materials={"carpet": "wood"}))]
        self.assertTrue(any(x.startswith("materials") for x in f))

    def test_item_shape(self):
        items = base_items()
        items[0] = {"k": "sofa", "x": 0, "z": 0, "yaw": 0}
        items[1] = dict(items[1], x=True)
        items[2] = dict(items[2], z=0.123)
        items[3] = dict(items[3], yaw=45)
        items.append({"k": "decor", "x": 0, "z": 2.0, "yaw": 0})
        items.append({"k": "plant", "x": 2.0, "z": 3.0, "yaw": 0, "s": 2})
        items.append({"k": "plant", "x": 2.0, "z": 3.6, "yaw": 0, "colour": "red"})
        f = {p["field"] for p in fields(design(items))}
        for n in (1, 2, 3, 4, len(items) - 2, len(items) - 1, len(items)):
            self.assertIn("layout.items.%d" % n, f)

    def test_layout_shape(self):
        for lay in (None, [], {"items": "x"}, {"items": [], "extra": 1}, {"items": [{"k": "tm"}] * 41}):
            self.assertTrue([p for p in fields(dict(design([]), layout=lay)) if p["field"].startswith("layout")], lay)

    def test_counts(self):
        def count_problem(items):
            return [p for p in fields(design(items)) if p["field"] == "layout"]
        items = [i for i in base_items() if i["k"] != "helper"]
        self.assertTrue(count_problem(items), "no assistant desk")
        items = [i for i in base_items() if i["k"] != "meet"]
        self.assertTrue(count_problem(items), "no meeting table")
        items = base_items() + [{"k": "decor", "id": "robot", "x": -6.0 + 0.0, "z": 0.0, "yaw": 0}] * 9
        self.assertTrue(count_problem(items), "9 decor")


class TestPlacing(unittest.TestCase):
    def one(self, items):
        probs = [p for p in fields(design(items)) if p["field"].startswith("layout")]
        self.assertEqual(len(probs), 1, probs)
        return probs[0]

    def test_out_of_the_floor(self):
        items = base_items()
        items[0] = dict(items[0], x=6.8, z=0.0)
        p = self.one(items)
        self.assertEqual((p["field"], p["zh"]), ("layout.items.1", "「经理桌 1」出了楼层"))

    def test_on_the_lift(self):
        items = base_items()
        items[0] = dict(items[0], x=-1.0, z=-5.6)
        p = self.one(items)
        self.assertEqual(p["zh"], "「经理桌 1」压到电梯了，那里是固定的")

    def test_overlap(self):
        items = base_items()
        items[1] = dict(items[1], x=items[0]["x"] + 0.4, z=items[0]["z"])
        p = self.one(items)
        self.assertEqual((p["field"], p["zh"]), ("layout.items.2", "「经理桌 2」跟「经理桌 1」叠在一起了"))

    def test_a_boxed_seat(self):
        items = base_items()
        items[0] = {"k": "tm", "x": -6.2, "z": 5.6, "yaw": 0}
        self.assertEqual(fields(design(items)), [], "the desk alone in the corner is fine")
        items.append({"k": "decor", "id": "safe", "x": -4.8, "z": 6.1, "yaw": 90})
        p = self.one(items)
        self.assertEqual((p["field"], p["zh"]), ("layout.items.1", "「经理桌 1」的座位被挡住了，从电梯走不过去"))
        items[-1] = dict(items[-1], x=-4.6)
        self.assertEqual(fields(design(items)), [], "0.2 further: a path again")

    def test_turned_desks(self):
        items = base_items()
        for i in items:
            if i["k"] == "tm":
                i["yaw"] = 90
        self.assertEqual(fields(design(items)), [], "turned desks in the open office still fit")

    def test_a_plant_on_a_chair_is_an_overlap(self):
        items = base_items()
        seat_z = items[0]["z"] + 0.78
        items.append({"k": "plant", "x": items[0]["x"], "z": round(round(seat_z / 0.2) * 0.2, 2), "yaw": 0})
        p = self.one(items)
        self.assertIn("叠在一起", p["zh"])


class TestRulesAndDemo(unittest.TestCase):
    def test_rules_text(self):
        t = ac.FLOOR_RULES
        for word in ("layout", "items", "tm", "helper", "meet", "decor", "plant", "2 decimals", "yaw", "90", "1 to 9", "1 to 3",
                     "lift", "area manager's room", "door", "pantry", "whiteboard", "every seat", "from the lift", "materials") + ac.FLOOR_MATERIALS:
            self.assertIn(word, t)

    def test_demo_has_a_v2_design(self):
        w = ac.demo_world()
        v2 = [d for d in w["designs"].values() if d.get("v") == 2]
        self.assertTrue(v2)
        for d in v2:
            self.assertEqual(ac.check_design(d), [])
            self.assertIn("materials", d)


T1_office_page, T2_office_page, T3_office_page = "aaaa0001", "bbbb0002", "cccc0003"


GOOD_office_page = {"v": 1, "name": "收银台风格", "why": "POS",
        "colors": {"accent": "#2E7D6B", "carpet": "#E4DCCB", "manager_floor": "#D9C2A0", "pantry_floor": "#EEEAE0",
                   "desk": "#EFDAB5", "desk_leg": "#BBA27C", "chair": "#3E4560", "meeting_rug": "#A9BCE0",
                   "manager_rug": "#C97B66"},
        "decor": ["cashier", "none", "goods"]}


VIEW = {"v": 2,
        "repos": [{"id": T1_office_page, "name": "shop", "here": True, "n": 0}, {"id": T2_office_page, "name": "blog", "here": True, "n": 1},
                  {"id": T3_office_page, "name": "wiki", "here": False, "n": 2}],
        "floors": [T1_office_page, T2_office_page], "designs": {T2_office_page: GOOD_office_page}, "asked": [T2_office_page]}


def agent_office_page(aid, role, terr, up="", status="", done=False, lead=""):
    return {"id": aid, "role": role, "label": aid, "task": aid, "stuck": False, "waiting": status == "waiting",
            "done": done, "status": status, "tools": {}, "terr": terr, "relay": "", "lead": lead, "office": None,
            "up": up}


SNAP_office_page = r"""
function snap(view, agents, govs){
  apply({ type: 'snapshot', world: view, agents: agents || [], govs: govs || [], gov: { state: 'idle', terr: view.floors[0] },
          asks: [], governors: (govs || []).length, adding: [], hist: {} });
}
function settle(sec){ for (let t = 0; t < sec; t += 0.05) update(0.05); }
"""


def sim_office_page(driver, payload=None, required=("officeState", "apply", "update", "citizens", "byId")):
    return run_sim(SNAP_office_page + driver, payload or {}, required=required)


class TestBuilding(unittest.TestCase):
    def test_office_state(self):
        out = sim_office_page("""
officeState(__payload.view);
__out = { terrs: map.territories.map(t => [t.id, t.name, t.floor, t.cx, t.cz, t.here]),
          f1: floorOf(__payload.t1), f2: floorOf(__payload.t2), f3: floorOf(__payload.t3),
          names: [floorName(0), floorName(1), floorName(12)], gap: FLOOR_GAP };
""", {"view": VIEW, "t1": T1_office_page, "t2": T2_office_page, "t3": T3_office_page}, required=("officeState", "floorOf", "floorName", "map"))
        self.assertEqual(out["terrs"], [[T2_office_page, "blog", 2, 60, 0, True], [T1_office_page, "shop", 1, 0, 0, True]], "top first")
        self.assertEqual((out["f1"], out["f2"], out["f3"]), (1, 2, 0))
        self.assertEqual(out["names"], ["G", "1F", "12F"])
        self.assertEqual(out["gap"], 60)

    def test_an_unknown_floor_id_is_dropped(self):
        view = dict(VIEW, floors=[T1_office_page, "dead0000"])
        out = sim_office_page("officeState(__payload.v); __out = map.territories.map(t => t.id);", {"v": view},
                  required=("officeState", "map"))
        self.assertEqual(out, [T1_office_page])

    def test_untick_removes_its_people_at_once(self):
        out = sim_office_page("""
snap(__payload.view, __payload.agents);
apply({ type: 'world', world: Object.assign({}, __payload.view, { floors: [__payload.t2] }) });
__out = citizens.filter(c => !c.gone).map(c => c.id);
""", {"view": VIEW, "t2": T2_office_page, "agents": [agent_office_page("s:a", "helper", T1_office_page), agent_office_page("s:b", "helper", T2_office_page)]})
        self.assertEqual(out, ["s:b"])

    def test_theme_is_data_only(self):
        bad = json.loads(json.dumps(GOOD_office_page))
        bad["colors"]["carpet"] = "javascript:alert(1)"
        bad["decor"] = ["robot", "<img onerror=x>", "plants"]
        view = dict(VIEW, designs={T2_office_page: bad})
        out = sim_office_page("""
officeState(__payload.v);
const a = themeOf(__payload.t1), b = themeOf(__payload.t2);
__out = { a, b, decor: FLOOR_DECOR };
""", {"v": view, "t1": T1_office_page, "t2": T2_office_page}, required=("officeState", "themeOf", "FLOOR_DECOR"))
        a, b = out["a"], out["b"]
        self.assertEqual((a["name"], a["designed"], a["decor"]), ("还没装修", False, ["none", "none", "none"]))
        self.assertEqual(sorted(a["colors"]), sorted(GOOD_office_page["colors"]))
        self.assertTrue(all(re.fullmatch(r"#[0-9A-Fa-f]{6}", v) for v in a["colors"].values()))
        self.assertEqual((b["name"], b["designed"]), ("收银台风格", True))
        self.assertEqual(b["colors"]["carpet"], a["colors"]["carpet"], "a bad value falls back to the base look")
        self.assertEqual(b["colors"]["accent"], "#2E7D6B")
        self.assertEqual(b["decor"], ["robot", "none", "plants"])
        self.assertEqual(out["decor"], ["robot", "conveyor", "gears", "chart", "plants", "safe", "cabinets", "printer",
                                        "bookshelf", "clock", "cashier", "goods", "menu", "scanner", "lightbox"])

    def test_needs_ask(self):
        out = sim_office_page("""
snap(__payload.view, __payload.agents);
const before = [needsAsk(__payload.t1), needsAsk(__payload.t2)];
apply({ type: 'spawn', id: 's:d', role: 'designer', label: 'shop Designer', task: 'x', terr: __payload.t1,
        up: 'gov:' + __payload.t1 });
__out = { before, withDesigner: needsAsk(__payload.t1) };
""", {"view": VIEW, "t1": T1_office_page, "t2": T2_office_page, "agents": []})
        self.assertEqual(out["before"], [True, False], "shop: no design, not asked; blog has one")
        self.assertFalse(out["withDesigner"])

    def test_world_event_logs_the_change(self):
        out = sim_office_page("""
snap(__payload.view, []);
apply({ type: 'world', world: __payload.view2, change: { kind: 'design', terr: __payload.t1, by: 'designer' } });
apply({ type: 'design_bad', terr: __payload.t1, problems: [{ field: 'colors.carpet', zh: '地毯的亮度是 20%，要在 55%–95% 之间', en: 'x' }] });
__out = logEntries.map(e => String(e.text));
""", {"view": VIEW, "t1": T1_office_page, "view2": dict(VIEW, designs={T1_office_page: GOOD_office_page, T2_office_page: GOOD_office_page})})
        self.assertTrue(any("收银台风格" in s and "1F" in s for s in out), out)
        self.assertTrue(any("地毯的亮度是 20%" in s and "1F" in s for s in out), out)


class TestWho(unittest.TestCase):
    def test_role_words(self):
        out = sim_office_page("__out = ['governor','task-manager','helper','designer','worker'].map(roleWord);",
                  required=("roleWord",))
        self.assertEqual(out, ["区经理", "经理", "助理", "设计师", ""])

    def test_no_governor_word_left(self):
        out = sim_office_page("__out = Object.values(TEXT.zh).filter(s => String(s).includes('总督'));", required=("TEXT",))
        self.assertEqual(out, [])

    def test_rail_floors_and_badges(self):
        agents = [agent_office_page("s:h", "helper", T1_office_page, up="gov:" + T1_office_page), agent_office_page("s:t", "task-manager", T1_office_page, up="gov:" + T1_office_page),
                  agent_office_page("w1", "worker", T1_office_page, up="s:t"), agent_office_page("w2", "worker", T1_office_page, up="s:t"),
                  agent_office_page("d1", "merge-deputy", T1_office_page, up="gov:" + T1_office_page), agent_office_page("s:b", "helper", T2_office_page, up="gov:" + T2_office_page)]
        out = sim_office_page("""
snap(__payload.view, __payload.agents, [{ terr: __payload.t1, state: 'busy' }]);
const g = railGroups();
__out = { groups: g.map(x => ({ terr: x.terr, name: x.name, rows: x.rows.map(r => [r.id, r.depth, r.badge]) })),
          badge: subBadge('s:t'), none: subBadge('s:h'), subs: citizens.filter(isSub).map(c => c.id).sort(),
          counts: topCounts() };
""", {"view": VIEW, "agents": agents, "t1": T1_office_page})
        self.assertEqual([g["name"] for g in out["groups"]], ["2F · blog", "1F · shop"], "top floor first")
        rows = {r[0]: r for r in out["groups"][1]["rows"]}
        self.assertEqual(set(rows), {"gov:" + T1_office_page, "s:h", "s:t"}, "no subagent rows")
        self.assertEqual(rows["s:t"][1], 1, "under the area manager")
        self.assertEqual(rows["s:t"][2], "worker ×2")
        self.assertEqual(rows["gov:" + T1_office_page][2], "deputy ×1")
        self.assertEqual((out["badge"], out["none"]), ("worker ×2", ""))
        self.assertEqual(out["subs"], ["d1", "w1", "w2"])
        self.assertEqual([c[0] for c in out["counts"]], ["干活", "找区经理", "休息"])
        self.assertEqual(sum(c[1] for c in out["counts"]), 4, "3 sessions + 1 governor, no subagents")

    def test_a_waiting_subagent_shows_on_its_parent(self):
        agents = [agent_office_page("s:t", "task-manager", T1_office_page, up="gov:" + T1_office_page), agent_office_page("w1", "worker", T1_office_page, up="s:t", status="waiting")]
        out = sim_office_page("""
snap(__payload.view, __payload.agents);
const g = railGroups().find(x => x.terr === __payload.t1);
const row = g.rows.find(r => r.id === 's:t');
__out = { waits: rowWaitsOnYou(row), count: railCount(railGroups()).you, tag: floorTag(__payload.t1) };
""", {"view": VIEW, "agents": agents, "t1": T1_office_page})
        self.assertTrue(out["waits"])
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["tag"], {"floor": "1F", "repo": "shop", "design": "还没装修", "people": 1, "wait": 1})


class TestSeats(unittest.TestCase):
    def test_desks(self):
        agents = [agent_office_page("s:h%d" % i, "helper", T2_office_page, up="gov:" + T2_office_page, status="") for i in range(4)] + \
                 [agent_office_page("s:t%d" % i, "task-manager", T2_office_page, up="gov:" + T2_office_page) for i in range(10)] + \
                 [agent_office_page("s:d", "designer", T2_office_page, up="gov:" + T2_office_page), agent_office_page("s:i", "helper", T2_office_page, status="idle")]
        out = sim_office_page("""
snap(__payload.view, __payload.agents);
const loc = c => { const s = seatOf(c); return [Math.round((s.x - 60) * 100) / 100, Math.round(s.y * 100) / 100]; };
__out = { seats: Object.fromEntries(citizens.map(c => [c.id, loc(c)])), desks: deskCount(__payload.t2),
          meet: MEET.map(m => [m.x, m.z]), pantry: PANTRY.map(m => [m.x, m.z]) };
""", {"view": VIEW, "agents": agents, "t2": T2_office_page})
        s = out["seats"]
        # city-office-2: seatOf is the chair, in front of the desk (helper desk z + 0.74, manager desk z + 0.78)
        self.assertEqual([s["s:h%d" % i] for i in range(3)], [[2.9, -0.86], [4.4, -0.86], [5.9, -0.86]])
        self.assertEqual(s["s:t0"], [-5.7, -0.52])
        self.assertEqual(s["s:t4"], [-3.2, 2.38])
        self.assertEqual(s["s:t8"], [-0.7, 5.28])
        meet = [list(m) for m in out["meet"]]
        self.assertGreaterEqual(len(meet), 4)
        for k in ("s:h3", "s:t9", "s:d"):
            self.assertIn(s[k], [[round(a, 2), round(b, 2)] for a, b in meet], k + " goes to the meeting corner")
        self.assertIn(s["s:i"], [[round(a, 2), round(b, 2)] for a, b in out["pantry"]], "idle -> pantry")
        self.assertEqual(out["desks"], 9)

    def test_desk_count_and_walk_grid(self):
        agents = [agent_office_page("s:t0", "task-manager", T1_office_page, up="gov:" + T1_office_page)]
        out = sim_office_page("""
snap(__payload.view, __payload.agents);
const p = findPath(LIFT_OUT[0].x, LIFT_OUT[0].z, TM_DESKS[8].x + 1.25, TM_DESKS[8].z);
__out = { desks: deskCount(__payload.t1), aisle: walkable(-1.95, 0.1), desk: walkable(TM_DESKS[0].x, TM_DESKS[0].z),
          shaft: walkable(-1.05, -6.9), path: p.length, bad: p.filter(q => !walkable(q.x, q.y !== undefined ? q.y : q.z)).length };
""", {"view": VIEW, "agents": agents, "t1": T1_office_page})
        self.assertEqual(out["desks"], 2, "one more desk than managers")
        self.assertTrue(out["aisle"])
        self.assertFalse(out["desk"])
        self.assertFalse(out["shaft"])
        self.assertGreater(out["path"], 0)
        self.assertEqual(out["bad"], 0)


class TestLift(unittest.TestCase):
    def test_a_talk_to_another_floor_rides_the_lift(self):
        agents = [agent_office_page("s:a", "helper", T1_office_page, up="gov:" + T1_office_page), agent_office_page("s:b", "task-manager", T2_office_page, up="gov:" + T2_office_page)]
        out = sim_office_page("""
snap(__payload.view, __payload.agents);
settle(15);
const a = byId('s:a'), b = byId('s:b');
const home = { x: a.x, y: a.y };
apply({ type: 'talk', from: 's:a', to: 's:b' });
const trace = [];
for (let t = 0; t < 150; t += 0.05) {
  update(0.05);
  trace.push([a.at, Math.round(a.x * 100) / 100, Math.round(a.y * 100) / 100, Math.hypot(a.x - b.x, a.y - b.y)]);
}
__out = { trace, home, liftIn: LIFT_IN.concat(LIFT_OUT).map(s => [s.x, s.z]), gap: FLOOR_GAP, t1: __payload.t1, t2: __payload.t2 };
""", {"view": VIEW, "agents": agents, "t1": T1_office_page, "t2": T2_office_page})
        tr = out["trace"]
        ats = [x[0] for x in tr]
        self.assertIn(T2_office_page, ats, "she rides up to blog's floor")
        first = ats.index(T2_office_page)
        _, x, y, _ = tr[first]
        lift2 = [(60 + lx, lz) for lx, lz in out["liftIn"]]
        self.assertTrue(min(((x - lx) ** 2 + (y - lz) ** 2) ** 0.5 for lx, lz in lift2) < 0.8,
                        "she comes out of the lift, never pops up elsewhere")
        self.assertTrue(any(d < 1.6 for at, _, _, d in tr[first:] if at == T2_office_page), "they meet face to face")
        self.assertEqual(ats[-1], T1_office_page, "and she rides back")
        _, x, y, _ = tr[-1]
        self.assertLess(((x - out["home"]["x"]) ** 2 + (y - out["home"]["y"]) ** 2) ** 0.5, 0.8, "back at her desk")
        changes = [i for i in range(1, len(ats)) if ats[i] != ats[i - 1]]
        self.assertEqual(len(changes), 2, "one ride up, one ride down")


class TestNoFrame(unittest.TestCase):
    def test_no_frame_around_the_city(self):
        rules = re.findall(r"(?<![\w-])\.stage\{([^}]*)\}", style())
        self.assertTrue(rules)
        for rule in rules:
            with self.subTest(rule=rule):
                self.assertNotRegex(rule, r"border(-radius)?\s*:\s*(?!0\b|none\b)")
                self.assertNotIn("var(--sky)", rule, "the city must blend into the page, no box")


def feed(st, ev, sid, repo, role="", aid="", tool="Read"):
    st.feed_line({"ev": ev, "sid": sid, "aid": aid, "at": "", "tool": tool, "nt": "", "proj": "p",
                  "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}, 1000.0)


def snapshot_people(st):
    client = st.add_client()
    return json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1])


class TestGovernorPresenceServerP0(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_people_")
        # city-roles: g1 is the main manager of /a/.git (the governor is the lock holder only)
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"),
                               main_fn=lambda identity: (os.getpid(), "g1") if identity == "/a/.git" else None)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_no_governor_session_lists_none(self):
        feed(self.st, "PostToolUse", "tm", "/a/.git", role="task-manager")
        self.assertEqual(snapshot_people(self.st)["govs"], [])

    def test_governor_session_is_listed_with_its_territory(self):
        feed(self.st, "UserPromptSubmit", "g1", "/a/.git")
        govs = snapshot_people(self.st)["govs"]
        self.assertEqual([g["terr"] for g in govs], [ac.territory_id("/a/.git")])
        self.assertIn("state", govs[0])

    def test_governor_leaving_is_broadcast(self):
        feed(self.st, "UserPromptSubmit", "g1", "/a/.git")
        client = self.st.add_client()
        client.queue.get_nowait()
        feed(self.st, "SessionEnd", "g1", "/a/.git")
        msgs = []
        while not client.queue.empty():
            msgs.append(json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1]))
        gone = [m for m in msgs if m.get("type") == "gov" and m.get("present") is False]
        self.assertTrue(gone, "a gov event with present false")
        self.assertEqual(gone[0]["terr"], ac.territory_id("/a/.git"))
        self.assertEqual(snapshot_people(self.st)["govs"], [])


def top_css():
    """The page CSS without its @media blocks (the computer look)."""
    c, out, i = css(), [], 0
    while True:
        j = c.find("@media", i)
        if j < 0:
            out.append(c[i:])
            return "".join(out)
        out.append(c[i:j])
        depth, k = 0, c.index("{", j)
        for k in range(k, len(c)):
            if c[k] == "{":
                depth += 1
            elif c[k] == "}":
                depth -= 1
                if depth == 0:
                    break
        i = k + 1


def top(sel):
    return rule(sel, top_css())


def flat(block):
    return (block or "").replace(" ", "").replace("\n", "")


def decl(block, prop):
    """The last value of PROP in a declaration block (no spaces), or None."""
    vals = re.findall(r"(?:^|;)%s:([^;]*)" % re.escape(prop), flat(block))
    return vals[-1] if vals else None


class TestRailCss(unittest.TestCase):

    def test_one_straight_bar_per_group(self):
        g = flat(top(".rail-grp"))
        m = re.search(r"border-left:(\d+(?:\.\d+)?)pxsolidvar\(--rc\)", g)
        self.assertIsNotNone(m, ".rail-grp border-left: <n>px solid var(--rc) -- got " + g)
        self.assertTrue(3 <= float(m.group(1)) <= 6, m.group(1))
        self.assertNotIn("border-radius", g, "a straight bar")
        self.assertNotIn("border-left", flat(top(".rrow")), "no curved edge per row")

    def test_dot_colours(self):
        seen = {}
        for cls in ("you", "ask", "build", "walk", "rest", "gov"):
            with self.subTest(cls=cls):
                bg = decl(top(".sdot.st-" + cls), "background")
                self.assertIsNotNone(bg, ".sdot.st-%s has its own background" % cls)
                self.assertNotEqual(bg, "var(--ink-3)")
                seen[cls] = bg
        if len(seen) < 6:
            return
        self.assertNotEqual(seen["you"], seen["build"])
        self.assertNotEqual(seen["ask"], seen["build"])
        self.assertNotEqual(seen["rest"], seen["build"])


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


class TestSpawn(Case_reducer):
    def test_agent_description_names_the_task(self):
        self.govern()
        self.assertEqual(self.feed(R_reducer("PreToolUse", tool="Agent", desc="设置页表单", sub="worker")), [])
        out = self.spawn()
        self.assertEqual(out, [{"type": "spawn", "id": "a1", "role": "worker",
                                "label": "worker", "task": "设置页表单"}])

    def test_no_description_task_is_the_type(self):
        out = self.spawn(at="merge-deputy")
        self.assertEqual(out[0]["task"], "merge-deputy")
        self.assertEqual(out[0]["role"], "merge-deputy")

    def test_queue_matches_by_type_then_blank_then_nothing(self):
        self.feed(R_reducer("PreToolUse", tool="Agent", desc="tests", sub="task-manager"))
        self.feed(R_reducer("PreToolUse", tool="Task", desc="look around", sub=""))
        self.feed(R_reducer("PreToolUse", tool="Agent", desc="form", sub="worker"))
        self.assertEqual(self.spawn("a1", "worker")[0]["task"], "form")
        self.assertEqual(self.spawn("a2", "Explore")[0]["task"], "look around")
        self.assertEqual(self.spawn("a3", "task-manager")[0]["task"], "tests")
        self.assertEqual(self.spawn("a4", "worker")[0]["task"], "worker")

    def test_queue_is_per_session(self):
        self.feed(R_reducer("PreToolUse", sid="s2", tool="Agent", desc="other session", sub="worker"))
        self.assertEqual(self.spawn("a1", "worker", sid="s1")[0]["task"], "worker")

    def test_unknown_types_are_other(self):
        for aid, at in (("a1", "Explore"), ("a2", "general-purpose"), ("a3", "Plan")):
            with self.subTest(at=at):
                out = self.spawn(aid, at)
                self.assertEqual(out[0]["role"], "other")
                self.assertEqual(out[0]["label"], at)

    def test_the_four_pipeline_roles(self):
        for i, at in enumerate(("task-manager", "worker", "fast-lane-deputy", "merge-deputy")):
            with self.subTest(at=at):
                self.assertEqual(self.spawn("a%d" % i, at)[0]["role"], at)

    def test_long_names_are_cut(self):
        self.feed(R_reducer("PreToolUse", tool="Agent", desc="x" * 100, sub=""))
        out = self.spawn("a1", "y" * 100)
        self.assertLessEqual(len(out[0]["task"]), 40)
        self.assertLessEqual(len(out[0]["label"]), 30)

    def test_unknown_subagent_is_spawned_before_its_first_tool(self):
        out = self.feed(R_reducer("PostToolUse", aid="a9", at="worker", tool="Edit"))
        self.assertEqual(self.types(out), ["spawn", "tool"])
        self.assertEqual(out[0]["id"], "a9")

    def test_second_start_for_the_same_agent_does_not_spawn_twice(self):
        self.spawn()
        self.assertEqual(self.spawn(), [])


class TestTools(Case_reducer):
    def test_tool_kinds(self):
        self.spawn()
        cases = {"Edit": "Edit", "MultiEdit": "Edit", "NotebookEdit": "Edit", "Write": "Write",
                 "Bash": "Bash", "Read": "Read", "Grep": "Read", "Glob": "Read", "LS": "Read",
                 "WebFetch": "Read", "WebSearch": "Read", "TodoWrite": "Other",
                 "mcp__github__create_pull_request": "Other", "Agent": "Other"}
        for tool, kind in cases.items():
            with self.subTest(tool=tool):
                out = self.feed(R_reducer("PostToolUse", aid="a1", at="worker", tool=tool))
                # city-work-anim bounce 1: the event also names the raw tool, for the page's plain-words step
                self.assertEqual(out, [{"type": "tool", "id": "a1", "tool": kind, "name": tool}])

    def test_pre_tool_use_of_a_normal_tool_says_nothing(self):
        self.spawn()
        self.assertEqual(self.feed(R_reducer("PreToolUse", aid="a1", at="worker", tool="Agent",
                                     desc="nested", sub="worker")), [])

    def test_snapshot_counts_tools(self):
        self.spawn()
        for tool in ("Edit", "Edit", "Bash", "Grep"):
            self.feed(R_reducer("PostToolUse", aid="a1", at="worker", tool=tool))
        agent = self.r.snapshot()["agents"][0]
        self.assertEqual(agent["tools"], {"Edit": 2, "Write": 0, "Bash": 1, "Read": 1, "Other": 0})


class TestStuck(Case_reducer):
    def test_permission_request_then_the_tool_runs(self):
        self.spawn()
        out = self.feed(R_reducer("PermissionRequest", aid="a1", at="worker", tool="Bash"))
        self.assertEqual(out, [{"type": "stuck", "id": "a1", "question": "", "tool": "Bash"}])
        out = self.feed(R_reducer("PostToolUse", aid="a1", at="worker", tool="Bash"))
        self.assertEqual(out, [{"type": "answer", "id": "a1", "ok": True},
                               {"type": "tool", "id": "a1", "tool": "Bash", "name": "Bash"}])

    def test_permission_denied(self):
        self.spawn()
        self.feed(R_reducer("PermissionRequest", aid="a1", at="worker", tool="Bash"))
        out = self.feed(R_reducer("PermissionDenied", aid="a1", at="worker", tool="Bash"))
        self.assertEqual(out, [{"type": "answer", "id": "a1", "ok": False}])
        self.assertFalse(self.r.snapshot()["agents"][0]["stuck"])

    def test_ask_user_question(self):
        self.spawn()
        out = self.feed(R_reducer("PreToolUse", aid="a1", at="worker", tool="AskUserQuestion", q="API 路径用哪个？"))
        self.assertEqual(out, [{"type": "stuck", "id": "a1", "question": "API 路径用哪个？",
                                "tool": "AskUserQuestion"}])
        out = self.feed(R_reducer("PostToolUse", aid="a1", at="worker", tool="AskUserQuestion"))
        self.assertEqual(self.types(out), ["answer", "tool"])

    def test_long_question_is_cut(self):
        self.spawn()
        out = self.feed(R_reducer("PreToolUse", aid="a1", at="worker", tool="AskUserQuestion", q="q" * 200))
        self.assertLessEqual(len(out[0]["question"]), 60)

    def test_no_second_stuck_while_stuck(self):
        self.spawn()
        self.feed(R_reducer("PermissionRequest", aid="a1", at="worker", tool="Bash"))
        self.assertEqual(self.feed(R_reducer("PermissionRequest", aid="a1", at="worker", tool="Bash")), [])

    def test_snapshot_shows_stuck(self):
        self.spawn()
        self.feed(R_reducer("PermissionRequest", aid="a1", at="worker", tool="Bash"))
        self.assertTrue(self.r.snapshot()["agents"][0]["stuck"])


class TestDone(Case_reducer):
    def test_subagent_stop_is_done(self):
        self.spawn()
        self.assertEqual(self.feed(R_reducer("SubagentStop", aid="a1", at="worker")),
                         [{"type": "done", "id": "a1"}])

    def test_second_stop_and_later_tools_are_ignored(self):
        self.spawn()
        self.feed(R_reducer("SubagentStop", aid="a1", at="worker"))
        self.assertEqual(self.feed(R_reducer("SubagentStop", aid="a1", at="worker")), [])
        self.assertEqual(self.feed(R_reducer("PostToolUse", aid="a1", at="worker", tool="Edit")), [])

    def test_stop_from_an_unknown_agent_is_ignored(self):
        self.assertEqual(self.feed(R_reducer("SubagentStop", aid="zz", at="worker")), [])

    def test_done_agents_leave_after_the_ttl(self):
        self.r = agent_city.Reducer(done_ttl=60)
        self.spawn()
        self.feed(R_reducer("SubagentStop", aid="a1", at="worker"))
        # any line moves the clock; not a Stop: city-status makes a citizen's Stop an "idle" event
        self.assertEqual(self.feed(R_reducer("Notification", sid="s9", role="worker", nt="auth_success"), dt=30), [
            {"type": "spawn", "id": "s:s9", "role": "worker", "label": "worker", "task": "shop"}])
        out = self.feed(R_reducer("Notification", sid="s9", role="worker", nt="auth_success"), dt=40)
        self.assertIn({"type": "leave", "id": "a1"}, out)
        self.assertEqual([a["id"] for a in self.r.snapshot()["agents"]], ["s:s9"])


class TestSessions(Case_reducer):
    def test_first_plain_session_is_the_governor(self):
        out = self.feed(R_reducer("UserPromptSubmit", sid="main"))
        self.assertEqual(out, [{"type": "gov", "state": "busy"}])
        self.assertEqual(self.r.snapshot()["agents"], [])

    def test_governor_states_change_only_on_change(self):
        self.govern("main")
        self.assertEqual(self.feed(R_reducer("PostToolUse", sid="main", tool="Read")), [])
        self.assertEqual(self.feed(R_reducer("Notification", sid="main", nt="idle_prompt")), [])
        self.assertEqual(self.feed(R_reducer("Notification", sid="main", nt="permission_prompt")),
                         [{"type": "gov", "state": "waiting"}])
        self.assertEqual(self.feed(R_reducer("Notification", sid="main", nt="permission_prompt")), [])
        self.assertEqual(self.feed(R_reducer("PreToolUse", sid="main", tool="Agent", desc="d", sub="worker")),
                         [{"type": "gov", "state": "busy"}])
        self.assertEqual(self.feed(R_reducer("Stop", sid="main")), [{"type": "gov", "state": "idle"}])
        self.assertEqual(self.r.snapshot()["gov"], {"state": "idle"})

    def test_other_notifications_do_nothing(self):
        self.govern("main")
        self.assertEqual(self.feed(R_reducer("Notification", sid="main", nt="auth_success")), [])

    def test_session_with_a_role_is_a_citizen(self):
        self.govern("main")
        out = self.feed(R_reducer("PostToolUse", sid="tm1", role="task-manager", tool="Write", proj="shop-wt"))
        self.assertEqual(out, [
            {"type": "spawn", "id": "s:tm1", "role": "task-manager", "label": "task-manager", "task": "shop-wt"},
            {"type": "tool", "id": "s:tm1", "tool": "Write", "name": "Write"}])

    def test_second_plain_session_is_a_helper_citizen(self):
        # city-office O2 (2026-11-24): a session with no AGENT_ROLE is 助理 (role "helper"), was "task-manager"
        self.govern("main")
        out = self.feed(R_reducer("UserPromptSubmit", sid="other", proj=""))
        self.assertEqual(out, [{"type": "spawn", "id": "s:other", "role": "helper",
                                "label": "session", "task": "session"}])

    def test_citizen_session_gets_stuck_and_answered(self):
        self.govern("main")
        self.feed(R_reducer("PostToolUse", sid="tm1", role="task-manager", tool="Write"))
        out = self.feed(R_reducer("Notification", sid="tm1", role="task-manager", nt="permission_prompt"))
        self.assertEqual(out, [{"type": "stuck", "id": "s:tm1", "question": "", "tool": ""}])
        out = self.feed(R_reducer("UserPromptSubmit", sid="tm1", role="task-manager"))
        self.assertEqual(out, [{"type": "answer", "id": "s:tm1", "ok": True}])

    def test_citizen_session_stop_is_not_done(self):
        self.govern("main")
        self.feed(R_reducer("PostToolUse", sid="tm1", role="task-manager", tool="Write"))
        # city-status: the turn ended -> idle (tests/test_agent_city_status.py), never done
        self.assertEqual(self.feed(R_reducer("Stop", sid="tm1", role="task-manager")), [{"type": "idle", "id": "s:tm1"}])
        self.assertFalse([a for a in self.r.snapshot()["agents"] if a["id"] == "s:tm1"][0]["done"])

    def test_session_end_sends_everyone_home(self):
        self.govern("main")
        self.feed(R_reducer("PostToolUse", sid="tm1", role="task-manager", tool="Write"))
        self.feed(R_reducer("SubagentStart", sid="tm1", aid="w1", at="worker"))
        self.feed(R_reducer("SubagentStart", sid="main", aid="w2", at="worker"))
        out = self.feed(R_reducer("SessionEnd", sid="tm1", role="task-manager"))
        self.assertIn({"type": "done", "id": "s:tm1"}, out)
        self.assertIn({"type": "leave", "id": "s:tm1"}, out)
        self.assertIn({"type": "done", "id": "w1"}, out)
        self.assertIn({"type": "leave", "id": "w1"}, out)
        self.assertNotIn("w2", [e.get("id") for e in out])
        self.assertEqual([a["id"] for a in self.r.snapshot()["agents"]], ["w2"])

    def test_governor_session_end_frees_the_seat(self):
        self.govern("main")
        self.feed(R_reducer("SubagentStart", sid="main", aid="w2", at="worker"))
        out = self.feed(R_reducer("SessionEnd", sid="main"))
        self.assertIn({"type": "gov", "state": "idle"}, out)
        self.assertIn({"type": "leave", "id": "w2"}, out)
        self.assertEqual(self.feed(R_reducer("UserPromptSubmit", sid="new")), [{"type": "gov", "state": "busy"}])


class TestBounds(Case_reducer):
    def test_oldest_leave_past_the_cap(self):
        self.r = agent_city.Reducer(max_agents=40)
        for i in range(60):
            self.spawn("a%d" % i)
        leaves = [e["id"] for e in self.all if e["type"] == "leave"]
        self.assertEqual(leaves, ["a%d" % i for i in range(20)])
        self.assertEqual(len(self.r.snapshot()["agents"]), 40)

    def test_a_busy_old_agent_is_kept(self):
        self.r = agent_city.Reducer(max_agents=3)
        self.spawn("a0")
        self.spawn("a1")
        self.spawn("a2")
        self.feed(R_reducer("PostToolUse", aid="a0", at="worker", tool="Edit"))
        self.spawn("a3")
        self.assertIn({"type": "leave", "id": "a1"}, self.all)
        self.assertNotIn({"type": "leave", "id": "a0"}, self.all)

    def test_queue_does_not_grow_forever(self):
        for i in range(5000):
            self.r.feed(R_reducer("PreToolUse", tool="Agent", desc="d%d" % i, sub="nobody"), float(i))
        self.assertLessEqual(len(json.dumps(self.r.snapshot())), 2000)
        self.assertLess(sum(len(q) for q in self.r.pending.values()), 100)

    def test_many_sessions_do_not_pile_up(self):
        for i in range(500):
            self.r.feed(R_reducer("SessionEnd", sid="s%d" % i, role="worker"), float(i))
        self.assertLess(len(self.r.sessions), 50)


class TestSafety(Case_reducer):
    def test_garbage_gives_nothing(self):
        for raw in (None, 3, "x", [], {}, {"sid": "s1"}, {"ev": None}, {"ev": "PostToolUse", "aid": 5}):
            with self.subTest(raw=raw):
                self.assertEqual(self.r.feed(raw, 1.0), [])

    def test_unknown_event_gives_nothing(self):
        self.assertEqual(self.feed(R_reducer("FileChanged")), [])

    def test_extra_raw_keys_never_leak(self):
        raw = R_reducer("PreToolUse", tool="Agent", desc="d", sub="worker")
        raw["secret"] = "SECRET_X"
        self.feed(raw)
        raw = R_reducer("SubagentStart", aid="a1", at="worker")
        raw["prompt"] = "SECRET_Y"
        self.feed(raw)
        text = json.dumps(self.all) + json.dumps(self.r.snapshot())
        self.assertNotIn("SECRET", text)

    def test_snapshot_shape(self):
        self.spawn()
        snap = self.r.snapshot()
        self.assertEqual(set(snap), {"gov", "agents"})
        self.assertEqual(set(snap["agents"][0]),
                         {"id", "role", "label", "task", "stuck", "waiting", "status", "done",
                          "tools"})  # waiting: idea-city C5, status: city-status
        json.dumps(snap)


def dead_pid():
    proc = subprocess.Popen(["sleep", "60"])
    proc.kill()
    proc.wait()
    return proc.pid


class RolesCase(unittest.TestCase):
    """CityState with real lock files: repo A (the start repo) and repo B."""

    start_repo = True

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_roles_"))
        self.world = os.path.join(self.base, "world.json")
        self.repo = os.path.join(self.base, "repoA", ".git")
        self.repo_b = os.path.join(self.base, "repoB", ".git")
        os.makedirs(self.repo)
        os.makedirs(self.repo_b)
        self.procs = []
        self.st = self.make_state()
        self.client = None

    def make_state(self, **kw):
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world,
                            start_repo=self.repo if self.start_repo else None, **kw)

    def tearDown(self):
        if self.client is not None:
            self.st.remove_client(self.client)
        for p in self.procs:
            if p.poll() is None:
                p.kill()
                p.wait()
        shutil.rmtree(self.base, ignore_errors=True)

    # -- helpers ---------------------------------------------------------

    def live_pid(self):
        proc = subprocess.Popen(["sleep", "60"])
        self.procs.append(proc)
        return proc

    def kill(self, proc):
        proc.kill()
        proc.wait()

    def write_lock(self, pid, sid="-", repo=None, term="-", old=False):
        path = os.path.join(self.repo if repo is None else repo, "agent_main.lock")
        with open(path, "w") as fh:
            if old:
                fh.write("%s 2026-09-30 10:00\n" % pid)
            else:
                fh.write("%s 2026-09-30 10:00 %s %s\n" % (pid, sid, term))

    def drop_lock(self, repo=None):
        os.remove(os.path.join(self.repo if repo is None else repo, "agent_main.lock"))

    def line(self, ev, sid, now=100.0, repo=None, role="", aid="", at="", tool="Read", pid=""):
        self.st.feed_line({"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "",
                           "proj": "p", "role": role, "desc": "", "sub": "", "q": "", "klen": "",
                           "repo": self.repo if repo is None else repo, "ask": "", "wt": "",
                           "file": "", "tp": "", "pid": pid}, now)

    def act(self, sid, now=100.0, **kw):
        self.line("PostToolUse", sid, now, **kw)

    def holder(self, repo=None):
        reducer = self.st.reducers.get(self.repo if repo is None else repo)
        return None if reducer is None else reducer.gov_sid

    def snapshot(self):
        client = self.st.add_client()
        try:
            data = client.queue.get_nowait().decode("utf-8")
        finally:
            self.st.remove_client(client)
        return json.loads(data.split("data:", 1)[1])

    def agent_ids(self):
        return {a["id"] for a in self.snapshot()["agents"]}

    def govs(self):
        return {g["terr"]: g["state"] for g in self.snapshot()["govs"]}

    def listen(self):
        """Start collecting broadcast events (after the snapshot)."""
        self.client = self.st.add_client()
        self.client.queue.get_nowait()  # the snapshot

    def heard(self):
        out = []
        while True:
            try:
                raw = self.client.queue.get_nowait()
            except queue.Empty:
                return out
            if not isinstance(raw, bytes):
                continue
            text = raw.decode("utf-8")
            if "data:" in text:
                out.append(json.loads(text.split("data:", 1)[1]))

    def assert_governor(self, sid, repo=None):
        self.assertEqual(self.holder(repo), sid)
        self.assertNotIn("s:" + sid, self.agent_ids())

    def assert_citizen(self, sid, repo=None):
        self.assertNotEqual(self.holder(repo), sid)
        self.assertIn("s:" + sid, self.agent_ids())


class TestMainFn(RolesCase):
    def test_default_reads_pid_and_sid(self):
        p = self.live_pid()
        self.write_lock(p.pid, "sid-m", term="term_1")
        self.assertEqual(self.st.main_fn(self.repo), (p.pid, "sid-m"))

    def test_old_lock_has_no_sid(self):
        p = self.live_pid()
        self.write_lock(p.pid, old=True)
        self.assertEqual(self.st.main_fn(self.repo), (p.pid, ""))

    def test_dash_is_no_sid(self):
        p = self.live_pid()
        self.write_lock(p.pid, "-")
        self.assertEqual(self.st.main_fn(self.repo), (p.pid, ""))

    def test_nothing_live_is_none(self):
        self.assertIsNone(self.st.main_fn(self.repo))           # no lock
        self.assertIsNone(self.st.main_fn(None))
        self.write_lock(dead_pid(), "sid-m")
        self.assertIsNone(self.st.main_fn(self.repo))           # dead pid
        for garbage in ("", "\n", "abc 2026", "-5 x y z", "0 a b c"):
            with open(os.path.join(self.repo, "agent_main.lock"), "w") as fh:
                fh.write(garbage)
            with self.subTest(lock=garbage):
                self.assertIsNone(self.st.main_fn(self.repo))

    def test_a_given_main_fn_is_used(self):
        st = self.make_state(main_fn=lambda identity: (os.getpid(), "gx"))
        st.feed_line({"ev": "PostToolUse", "sid": "gx", "aid": "", "role": "", "tool": "Read",
                      "repo": self.repo}, 1.0)
        self.assertEqual(st.reducers[self.repo].gov_sid, "gx")


class TestSeatIsTheHolder(RolesCase):
    def test_no_lock_no_governor(self):
        self.act("a")
        self.act("b")
        self.assertIsNone(self.holder())
        self.assert_citizen("a")
        self.assert_citizen("b")
        self.assertNotIn(ac.territory_id(self.repo), self.govs())

    def test_holder_by_sid(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("h")
        self.act("m")
        self.assert_governor("m")
        self.assert_citizen("h")

    def test_holder_by_pid_when_the_lock_has_no_sid(self):
        p = self.live_pid()
        self.write_lock(p.pid, old=True)
        self.act("x", pid="")
        self.act("m", pid=str(p.pid))
        self.assert_governor("m")
        self.assert_citizen("x")

    def test_a_wrong_pid_is_not_the_holder(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("x", pid=str(p.pid + 100000))
        self.assertIsNone(self.holder())
        self.assert_citizen("x")

    def test_dead_holder_is_nobody(self):
        self.write_lock(dead_pid(), "m")
        self.act("m")
        self.assertIsNone(self.holder())
        self.assert_citizen("m")

    def test_the_holder_governs_whatever_its_role(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m", role="task-manager")
        self.assert_governor("m")

    def test_a_foreign_first_session_never_takes_the_seat(self):
        """E1 + E2: a roleless session that is not the holder comes first; the holder next."""
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("foreign", repo="")        # no repo: start territory (repo A), unknown sid
        self.assertIsNone(self.holder())
        self.act("m")
        self.assert_governor("m")
        self.assert_citizen("foreign")

    def test_the_seat_follows_the_lock(self):
        """E3 / take-over: the lock moves to a known citizen; it becomes governor on its next line."""
        old, new = self.live_pid(), self.live_pid()
        self.write_lock(old.pid, "m")
        self.act("m", 100.0)
        self.act("h", 101.0)
        self.assert_governor("m")
        self.assert_citizen("h")
        self.write_lock(new.pid, "h")
        self.listen()
        self.act("h", 102.0)
        self.assert_governor("h")
        events = self.heard()
        self.assertIn("s:h", [e.get("id") for e in events if e.get("type") == "leave"])
        gov = [e for e in events if e.get("type") == "gov"]
        self.assertTrue(gov, "a seat change is always told to the page")
        self.assertIs(gov[-1].get("present"), True)
        self.assertEqual(gov[-1].get("terr"), ac.territory_id(self.repo))
        self.act("m", 103.0)
        self.assert_citizen("m")
        self.assert_governor("h")

    def test_a_released_lock_turns_the_governor_into_a_citizen_on_its_next_line(self):
        """R3: close case released the lock; the old main manager goes on typing."""
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m", 100.0)
        self.assert_governor("m")
        self.drop_lock()
        self.act("m", 101.0)
        self.assertIsNone(self.holder())
        self.assert_citizen("m")

    def test_other_territories_keep_their_governor(self):
        pa, pb = self.live_pid(), self.live_pid()
        self.write_lock(pa.pid, "ma")
        self.write_lock(pb.pid, "mb", repo=self.repo_b)
        self.act("ma")
        self.act("mb", repo=self.repo_b)
        self.drop_lock()
        self.act("ma", 101.0)
        self.assertIsNone(self.holder())
        self.assertEqual(self.holder(self.repo_b), "mb")


class TestCheckSeats(RolesCase):
    def test_a_dead_holder_leaves_without_any_line(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m", 100.0)
        self.line("SubagentStart", "m", 100.5, aid="a1", at="worker")
        self.assert_governor("m")
        self.assertIn("a1", self.agent_ids())
        self.listen()
        self.kill(p)
        self.st.check_seats(200.0)
        self.assertIsNone(self.holder())
        ids = self.agent_ids()
        self.assertNotIn("a1", ids, "a dead governor ends like its SessionEnd: its subagents leave")
        self.assertNotIn("s:m", ids)
        gov = [e for e in self.heard() if e.get("type") == "gov"]
        self.assertTrue(gov, "the page is told")
        self.assertIs(gov[-1].get("present"), False)
        self.assertEqual(gov[-1].get("terr"), ac.territory_id(self.repo))
        self.assertNotIn(ac.territory_id(self.repo), self.govs())

    def test_a_released_lock_frees_the_seat_without_any_line(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m", 100.0)
        self.listen()
        self.drop_lock()
        self.st.check_seats(200.0)
        self.assertIsNone(self.holder())
        gov = [e for e in self.heard() if e.get("type") == "gov"]
        self.assertTrue(gov and gov[-1].get("present") is False)
        self.act("m", 201.0)
        self.assert_citizen("m")

    def test_a_live_holder_keeps_the_seat(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m", 100.0)
        self.listen()
        self.st.check_seats(100000.0)       # however quiet
        self.assertEqual(self.holder(), "m")
        self.assertEqual([e for e in self.heard() if e.get("type") == "gov"], [])

    def test_other_territories_are_not_touched(self):
        pa, pb = self.live_pid(), self.live_pid()
        self.write_lock(pa.pid, "ma")
        self.write_lock(pb.pid, "mb", repo=self.repo_b)
        self.act("ma")
        self.act("mb", repo=self.repo_b)
        self.kill(pa)
        self.st.check_seats(200.0)
        self.assertIsNone(self.holder())
        self.assertEqual(self.holder(self.repo_b), "mb")

    def test_no_governor_nothing_happens(self):
        self.act("a")
        self.st.check_seats(200.0)
        self.assert_citizen("a")


class TestSeenBeforeRestart(RolesCase):
    def restart(self):
        self.st = self.make_state()

    def test_unknown_only_while_a_holder_lives(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.act("m")
        terr = ac.territory_id(self.repo)
        self.restart()
        self.assertEqual(self.govs().get(terr), "unknown")
        self.kill(p)
        self.assertNotIn(terr, self.govs(), "no live main manager: nobody, not unknown")


class TestRepoLessLines(RolesCase):
    def test_a_known_sid_stays_in_its_territory(self):
        """E1: a session of repo B sends one line with repo ""."""
        self.act("x", 100.0, repo=self.repo_b)
        self.act("x", 101.0, repo="")
        self.assertNotIn("x", self.st.reducers[self.repo].sessions if self.repo in self.st.reducers else {})
        self.assertIn("x", self.st.reducers[self.repo_b].sessions)

    def test_a_subagent_line_teaches_the_territory_too(self):
        self.line("SubagentStart", "x", 100.0, repo=self.repo_b, aid="a1", at="worker")
        self.act("x", 101.0, repo="")
        self.assertIn("x", self.st.reducers[self.repo_b].sessions)
        self.assertNotIn("x", self.st.reducers[self.repo].sessions if self.repo in self.st.reducers else {})

    def test_an_unknown_sid_still_falls_back_to_the_start_territory(self):
        self.act("y", 100.0, repo="")
        self.assertIn("y", self.st.reducers[self.repo].sessions)

    def test_a_repo_less_line_never_takes_the_start_seat(self):
        """E1 exactly: the start territory's old governor is dead, a foreign session comes in."""
        old = self.live_pid()
        self.write_lock(old.pid, "old")
        self.act("old", 100.0)
        self.kill(old)
        self.act("foreign", 101.0, repo=self.repo_b)
        self.act("foreign", 102.0, repo="")
        self.assertNotEqual(self.holder(), "foreign")
        self.assertNotEqual(self.holder(self.repo_b), "foreign")


class TestGovNext(RolesCase):
    def test_a_non_holder_is_told_not_main(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        out = self.st.gov_next("h", self.repo, "w1", 0.2)
        self.assertEqual(out, {"state": "not-main"})
        self.assertNotIn(self.repo, self.st.governors)

    def test_no_lock_nobody_is_main(self):
        self.assertEqual(self.st.gov_next("h", self.repo, "w1", 0.2), {"state": "not-main"})
        self.assertEqual(self.st.governors, {})

    def test_the_holder_is_registered(self):
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        out = self.st.gov_next("m", self.repo, "w1", 0.1)
        self.assertEqual(out, {"state": "none"})
        self.assertEqual(self.st.governors[self.repo]["sid"], "m")

    def test_the_holder_by_pid(self):
        p = self.live_pid()
        self.write_lock(p.pid, old=True)
        self.assertEqual(self.st.gov_next("m", self.repo, "w1", 0.1, pid=str(p.pid)), {"state": "none"})
        self.assertEqual(self.st.governors[self.repo]["sid"], "m")

    def test_a_question_skips_a_helper(self):
        """A human-direct helper (roleless, not the holder) never answers as governor."""
        p = self.live_pid()
        self.write_lock(p.pid, "m")
        self.st.gov_next("h", self.repo, "w1", 0.1)
        body, code = self.st.create_ask({"sid": "w", "aid": "a1", "at": "worker", "role": "worker",
                                         "cwd": self.base, "repo": self.repo, "tool": "AskUserQuestion",
                                         "input": {"questions": [{"question": "which?", "options": []}]}},
                                        0)
        self.assertEqual(code, 200)
        self.assertEqual(body["phase"], "owner")
        self.assertEqual(body["why"], "no-governor")


class TestComesBack(RosterCase):
    def test_a_citizen_is_back_at_once(self):
        self.a_citizen("sid-tm")
        before = self.agents()["s:sid-tm"]
        self.restart()
        self.assertIn("s:sid-tm", self.agents(), "an idle task manager vanished with the restart")
        after = self.agents()["s:sid-tm"]
        for key in ("id", "role", "label", "task", "terr"):
            self.assertEqual(after[key], before[key], key)
        self.assertEqual(after["role"], "task-manager")
        self.assertEqual(after["terr"], self.terr())
        self.assertFalse(after["done"])

    def test_no_line_was_read_for_it(self):
        self.a_citizen("sid-tm")
        self.restart()
        health = self.st.health()
        self.assertEqual(health["lines"], 0)
        self.assertEqual(health["agents"], 1)

    def test_the_governor_is_back_idle_not_unknown(self):
        self.a_governor("sid-gov")
        self.restart()
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.assertEqual(self.holder(), "sid-gov")
        self.assertNotIn("s:sid-gov", self.agents())

    def test_governor_and_citizens_together(self):
        self.a_governor("sid-gov")
        self.a_citizen("sid-tm")
        self.a_citizen("sid-helper", role="")
        self.restart()
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.assertEqual(set(self.agents()), {"s:sid-tm", "s:sid-helper"})

    def test_each_one_in_its_own_territory(self):
        self.a_governor("sid-gov-a")
        self.a_governor("sid-gov-b", repo=self.repo_b)
        self.a_citizen("sid-tm-b", repo=self.repo_b)
        self.restart()
        self.assertEqual(sorted(self.govs()), sorted([(self.terr(), "idle"), (self.terr(self.repo_b), "idle")]))
        self.assertEqual(self.holder(self.repo_b), "sid-gov-b")
        self.assertEqual(self.agents()["s:sid-tm-b"]["terr"], self.terr(self.repo_b))

    def test_a_second_restart_keeps_them(self):
        self.a_governor("sid-gov")
        self.a_citizen("sid-tm")
        self.restart()
        self.restart()
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.assertIn("s:sid-tm", self.agents())

    def test_subagents_are_not_in_the_roster(self):
        tm = self.a_citizen("sid-tm")
        self.line("SubagentStart", "sid-tm", aid="agent-w1", at="worker", role="task-manager", pid=tm.pid)
        self.assertIn("agent-w1", self.agents())
        self.restart()
        self.assertEqual(set(self.agents()), {"s:sid-tm"}, "sessions first; a subagent comes back on its next event")
        self.line("PostToolUse", "sid-tm", aid="agent-w1", at="worker", role="task-manager", pid=tm.pid)
        self.assertIn("agent-w1", self.agents())


class TestSameSession(RosterCase):
    def test_a_citizens_next_line_makes_no_second_spawn(self):
        tm = self.a_citizen("sid-tm")
        self.restart()
        self.listen()
        self.act("sid-tm", role="task-manager", pid=tm.pid)
        types = [e["type"] for e in self.heard()]
        self.assertNotIn("spawn", types)
        self.assertIn("tool", types)
        self.assertEqual(set(self.agents()), {"s:sid-tm"})

    def test_the_governors_next_line_governs(self):
        gov = self.a_governor("sid-gov")
        self.restart()
        self.listen()
        self.line("UserPromptSubmit", "sid-gov", pid=gov.pid)
        events = self.heard()
        self.assertNotIn("spawn", [e["type"] for e in events])
        busy = [e for e in events if e["type"] == "gov"]
        self.assertEqual([(e["state"], e["terr"], e.get("present")) for e in busy],
                         [("busy", self.terr(), True)])
        self.assertEqual(self.holder(), "sid-gov")

    def test_session_end_ends_it_for_good(self):
        tm = self.a_citizen("sid-tm")
        self.restart()
        self.line("SessionEnd", "sid-tm", role="task-manager", pid=tm.pid)
        self.assertEqual(self.agents(), {})
        self.assertNotIn("sid-tm", self.roster_text())
        self.restart()
        self.assertEqual(self.agents(), {}, "its process still runs, but the session said it ended")

    def test_a_restored_governor_that_dies_is_ended_by_check_seats(self):
        gov = self.a_governor("sid-gov")
        self.restart()
        self.listen()
        self.kill(gov)
        self.st.check_seats(200.0)
        gone = [e for e in self.heard() if e["type"] == "gov"]
        self.assertEqual([(e["terr"], e.get("present")) for e in gone], [(self.terr(), False)])
        self.assertIsNone(self.holder())
        self.assertNotIn("sid-gov", self.roster_text())


class TestDeadAreDropped(RosterCase):
    def test_a_dead_citizen_is_gone(self):
        self.a_citizen("sid-keep")
        dead = self.a_citizen("sid-dead")
        self.kill(dead)
        self.restart()
        self.assertEqual(set(self.agents()), {"s:sid-keep"})
        self.assertNotIn("sid-dead", self.roster_text(), "a dropped entry leaves the file too")
        self.assertIn("sid-keep", self.roster_text())

    def test_a_dead_governor_is_gone(self):
        gov = self.a_governor("sid-gov")
        self.a_citizen("sid-tm")
        self.kill(gov)
        self.restart()
        self.assertEqual(self.govs(), [], "a dead main manager is nobody, not idle and not unknown")
        self.assertIsNone(self.holder())
        self.assertEqual(set(self.agents()), {"s:sid-tm"})

    def test_ended_before_the_restart_stays_gone(self):
        tm = self.a_citizen("sid-tm")
        self.line("SessionEnd", "sid-tm", role="task-manager", pid=tm.pid)
        self.assertNotIn("sid-tm", self.roster_text())
        self.restart()
        self.assertEqual(self.agents(), {})

    def test_a_citizen_with_no_known_pid_is_not_brought_back(self):
        self.act("sid-oldhook", role="task-manager")          # no "pid" key: an old hook
        self.assertIn("s:sid-oldhook", self.agents())
        self.restart()
        self.assertEqual(self.agents(), {}, "nothing proves it alive: it shows up on its next line")
        self.act("sid-oldhook", role="task-manager")
        self.assertIn("s:sid-oldhook", self.agents())

    def test_a_garbage_roster_is_an_empty_one(self):
        for garbage in ("", "not json", "[1, 2", '{"sessions": 7}', '{"sessions": [3, null, {"sid": 5}]}',
                        '[{"sid": "x", "pid": "abc", "repo": 1}]'):
            with self.subTest(roster=garbage):
                with open(self.roster, "w") as fh:
                    fh.write(garbage)
                self.restart()                                  # never raises
                self.assertEqual(self.agents(), {})
                self.assertEqual(self.govs(), [])
        tm = self.a_citizen("sid-tm")                           # and the next write is a good file
        json.loads(self.roster_text())
        self.restart()
        self.assertIn("s:sid-tm", self.agents())
        self.assertIsNotNone(tm)

    def test_no_roster_path_no_file(self):
        self.st = self.make_state(roster_path=None)
        self.a_citizen("sid-tm")
        self.assertEqual(os.listdir(self.city_dir), [])
        self.st = self.make_state(roster_path=None)
        self.assertEqual(self.agents(), {})


class TestSeatAtLoad(RosterCase):
    def test_a_released_lock_makes_the_old_governor_a_citizen(self):
        self.a_governor("sid-gov")
        self.drop_lock()
        self.restart()
        self.assertEqual(self.govs(), [])
        self.assertIsNone(self.holder())
        self.assertIn("s:sid-gov", self.agents(), "alive and not the main manager: a citizen")

    def test_a_lock_that_moved_seats_the_new_holder(self):
        self.a_governor("sid-old")
        new = self.a_citizen("sid-new", role="")
        self.write_lock(new.pid, "sid-new")                     # take-over while the server was down
        self.restart()
        self.assertEqual(self.holder(), "sid-new")
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.assertEqual(set(self.agents()), {"s:sid-old"})

    def test_an_old_lock_seats_the_session_with_that_pid(self):
        proc = self.live()
        self.write_lock(proc.pid, old=True)
        self.act("sid-gov", pid=proc.pid)                        # new hooks: matched by the line's pid
        self.assertEqual(self.holder(), "sid-gov")
        self.restart()
        self.assertEqual(self.holder(), "sid-gov")
        self.assertEqual(self.govs(), [(self.terr(), "idle")])


class TestTheFile(RosterCase):
    def test_it_names_every_live_session(self):
        self.a_governor("sid-gov")
        self.a_citizen("sid-tm")
        json.loads(self.roster_text())
        self.assertIn("sid-gov", self.roster_text())
        self.assertIn("sid-tm", self.roster_text())

    def test_no_temp_file_is_left(self):
        self.a_governor("sid-gov")
        tm = self.a_citizen("sid-tm")
        self.line("SessionEnd", "sid-tm", role="task-manager", pid=tm.pid)
        self.assertEqual(os.listdir(self.city_dir), ["roster.json"])

    def test_a_tool_line_never_rewrites_it(self):
        gov = self.a_governor("sid-gov")
        tm = self.a_citizen("sid-tm")
        before = os.stat(self.roster)
        text = self.roster_text()
        for i in range(30):
            self.line("PreToolUse", "sid-tm", 101.0 + i, role="task-manager", pid=tm.pid, tool="Edit")
            self.act("sid-tm", 101.5 + i, role="task-manager", pid=tm.pid, tool="Edit")
            self.act("sid-gov", 101.7 + i, pid=gov.pid, tool="Bash")
        after = os.stat(self.roster)
        self.assertEqual((after.st_ino, after.st_mtime_ns), (before.st_ino, before.st_mtime_ns),
                         "the roster was written again for a plain tool line")
        self.assertEqual(self.roster_text(), text)

    def test_a_roster_that_cannot_be_written_never_stops_the_city(self):
        self.st = self.make_state(roster_path=os.path.join(self.base, "no", "such", "dir", "roster.json"))
        self.a_citizen("sid-tm")                                # no exception
        self.assertIn("s:sid-tm", self.agents())


class TestOldHooks(RosterCase):
    def test_the_locks_sid_makes_it_the_governor(self):
        self.a_governor("sid-gov", with_pid=False)
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.assertNotIn("s:sid-gov", self.agents())

    def test_it_comes_back_after_a_restart(self):
        self.a_governor("sid-gov", with_pid=False)             # its pid: the lock's
        self.restart()
        self.assertEqual(self.holder(), "sid-gov")
        self.assertEqual(self.govs(), [(self.terr(), "idle")])

    def test_dead_it_does_not_come_back(self):
        gov = self.a_governor("sid-gov", with_pid=False)
        self.kill(gov)
        self.restart()
        self.assertEqual(self.govs(), [])
        self.assertEqual(self.agents(), {})


class TestOldLockAgain(RosterCase):
    """R3b: the session's own old agent-start.sh wrote "<pid> <date> <time>" again (a compaction)."""

    def seat_then_old_lock(self):
        gov = self.a_governor("sid-gov", with_pid=False)
        self.write_lock(gov.pid, old=True)
        return gov

    def test_its_next_line_keeps_the_seat(self):
        self.seat_then_old_lock()
        self.listen()
        self.act("sid-gov")
        self.assertEqual(self.holder(), "sid-gov")
        self.assertNotIn("s:sid-gov", self.agents())
        self.assertEqual([e for e in self.heard() if e["type"] == "gov" and e.get("present") is False], [])

    def test_check_seats_keeps_the_seat(self):
        self.seat_then_old_lock()
        self.listen()
        self.st.check_seats(200.0)
        self.assertEqual(self.holder(), "sid-gov")
        self.assertEqual([e for e in self.heard() if e["type"] == "gov"], [])

    def test_gov_next_still_knows_it(self):
        self.seat_then_old_lock()
        reply = self.st.gov_next("sid-gov", self.repo, "w1", 0.0, pid="")
        self.assertNotEqual(reply.get("state"), "not-main")

    def test_it_comes_back_after_a_restart(self):
        self.seat_then_old_lock()
        self.restart()
        self.assertEqual(self.holder(), "sid-gov")
        self.assertEqual(self.govs(), [(self.terr(), "idle")])
        self.act("sid-gov")                                     # and its line still governs
        self.assertEqual(self.holder(), "sid-gov")
        self.assertNotIn("s:sid-gov", self.agents())

    def test_an_old_lock_of_another_pid_takes_the_seat_away(self):
        self.a_governor("sid-gov", with_pid=False)
        other = self.live()
        self.write_lock(other.pid, old=True)
        self.act("sid-gov")
        self.assertIsNone(self.holder())
        self.assertIn("s:sid-gov", self.agents())

    def test_another_session_never_gets_the_seat_from_an_old_lock(self):
        self.seat_then_old_lock()
        self.act("sid-other")                                   # no pid either: not the holder
        self.assertEqual(self.holder(), "sid-gov")
        self.assertIn("s:sid-other", self.agents())


REPO_session_names = "/work/v4/v4-plus/.git"


def title_line(kind, value, sid="s1"):
    key = {"custom-title": "customTitle", "agent-name": "agentName", "ai-title": "aiTitle"}[kind]
    return json.dumps({"type": kind, key: value, "sessionId": sid}) + "\n"


def talk_line(text="hello", sid="s1"):
    return json.dumps({"type": "user", "message": {"role": "user", "content": text},
                       "sessionId": sid}) + "\n"


class TitleCase(unittest.TestCase):

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_titles_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.root = os.path.join(self.base, "projects")
        os.makedirs(os.path.join(self.root, "-work-v4-plus"))

    def transcript(self, name="s1", lines=(), folder="-work-v4-plus"):
        path = os.path.join(self.root, folder, name + ".jsonl")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("".join(lines))
        return path

    def add(self, path, *lines):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("".join(lines))


class CityCase_session_names(TitleCase):

    def setUp(self):
        super().setUp()
        self.world = os.path.join(self.base, "world.json")
        self.now = 1000.0
        self.st = self.state()

    def state(self):
        st = ac_session_names.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world,
                          titles=ac_session_names.TitleReader(root=self.root),
                          main_fn=lambda identity: (os.getpid(), "gov"))   # city-roles: "gov" is the main manager
        self.client = st.add_client()
        self.client.queue.get_nowait()
        return st

    def line(self, sid, ev="PostToolUse", tp="", role="", aid="", at="", tool="Read", st=None):
        self.now += 1.0
        (st or self.st).feed_line({
            "ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": "v4-plus",
            "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": REPO_session_names, "ask": "",
            "wt": "", "file": "", "tp": tp}, self.now)

    def events(self):
        out = []
        while not self.client.queue.empty():
            raw = self.client.queue.get_nowait()
            if isinstance(raw, bytes) and b"data:" in raw:
                out.append(json.loads(raw.decode("utf-8").split("data:", 1)[1]))
        return out

    def of(self, etype, events):
        return [e for e in events if e.get("type") == etype]

    def citizen_session(self, sid, tp):
        """A governor first (the repo's first roleless session), then SID as a citizen."""
        self.line("gov")
        self.line(sid, tp=tp)


class TestTitleReader(TitleCase):

    def reader(self, **kw):
        return ac_session_names.TitleReader(root=self.root, **kw)

    def test_custom_title_wins(self):
        p = self.transcript(lines=[title_line("ai-title", "Sales invoice overpayment"),
                                   title_line("custom-title", "plus-manager"),
                                   title_line("agent-name", "plus-manager"), talk_line()])
        self.assertEqual(self.reader().title(p), "plus-manager")

    def test_agent_name_when_no_custom_title(self):
        p = self.transcript(lines=[title_line("agent-name", "consignment"),
                                   title_line("ai-title", "Consignment phase 3")])
        self.assertEqual(self.reader().title(p), "consignment")

    def test_ai_title_last(self):
        p = self.transcript(lines=[talk_line(), title_line("ai-title", "Menu visibility")])
        self.assertEqual(self.reader().title(p), "Menu visibility")

    def test_nothing_found(self):
        self.assertEqual(self.reader().title(self.transcript(lines=[talk_line()])), "")

    def test_the_newest_one_counts(self):
        p = self.transcript(lines=[title_line("custom-title", "old name"), talk_line(),
                                   title_line("custom-title", "new name")])
        self.assertEqual(self.reader().title(p), "new name")

    def test_a_later_rename_is_seen(self):
        r = self.reader()
        p = self.transcript(lines=[title_line("ai-title", "First talk")])
        self.assertEqual(r.title(p), "First talk")
        self.add(p, talk_line(), title_line("custom-title", "plus-manager"))
        self.assertEqual(r.title(p), "plus-manager")
        self.add(p, title_line("custom-title", "plus-manager 2"))
        self.assertEqual(r.title(p), "plus-manager 2")

    def test_titles_found_earlier_are_kept(self):
        r = self.reader()
        p = self.transcript(lines=[title_line("custom-title", "plus-manager")])
        self.assertEqual(r.title(p), "plus-manager")
        self.add(p, *[talk_line("x" * 50) for _ in range(20)])
        self.assertEqual(r.title(p), "plus-manager")

    def test_a_half_written_line_waits(self):
        r = self.reader()
        p = self.transcript(lines=[title_line("ai-title", "First talk")])
        full = title_line("custom-title", "plus-manager")
        self.add(p, full[:25])
        self.assertEqual(r.title(p), "First talk")
        self.add(p, full[25:])
        self.assertEqual(r.title(p), "plus-manager")

    def test_a_shorter_file_is_read_again(self):
        r = self.reader()
        p = self.transcript(lines=[talk_line("y" * 200), title_line("custom-title", "old")])
        self.assertEqual(r.title(p), "old")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(title_line("ai-title", "fresh"))
        self.assertEqual(r.title(p), "fresh")

    def test_first_read_is_only_the_tail(self):
        p = self.transcript(lines=[title_line("custom-title", "early name")]
                            + [talk_line("z" * 100) for _ in range(100)]
                            + [title_line("ai-title", "late title")])
        self.assertEqual(self.reader(tail_bytes=4096).title(p), "late title")
        self.assertEqual(self.reader().title(p), "early name")

    def test_bad_lines_are_skipped(self):
        p = self.transcript(lines=['{"type": "custom-title", "customTitle": \n', "not json\n",
                                   title_line("ai-title", "ok title")])
        self.assertEqual(self.reader().title(p), "ok title")

    def test_only_inside_root(self):
        outside = os.path.join(self.base, "elsewhere.jsonl")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write(title_line("custom-title", "secret"))
        link = os.path.join(self.root, "-work-v4-plus", "link.jsonl")
        os.symlink(outside, link)
        r = self.reader()
        self.assertEqual(r.title(outside), "")
        self.assertEqual(r.title(link), "")
        self.assertEqual(r.title(os.path.join(self.root, "..", "elsewhere.jsonl")), "")

    def test_bad_paths_give_nothing(self):
        r = self.reader()
        txt = os.path.join(self.root, "-work-v4-plus", "notes.txt")
        with open(txt, "w", encoding="utf-8") as fh:
            fh.write(title_line("custom-title", "x"))
        for path in ("", "relative/s1.jsonl", txt,
                     os.path.join(self.root, "-work-v4-plus", "missing.jsonl"), None, 42):
            with self.subTest(path=path):
                self.assertEqual(r.title(path), "")

    def test_default_root(self):
        old = os.environ.get("CLAUDE_CONFIG_DIR")
        self.addCleanup(lambda: os.environ.__setitem__("CLAUDE_CONFIG_DIR", old) if old is not None
                        else os.environ.pop("CLAUDE_CONFIG_DIR", None))
        os.environ["CLAUDE_CONFIG_DIR"] = self.base
        p = self.transcript(lines=[title_line("custom-title", "from config dir")])
        self.assertEqual(ac_session_names.TitleReader().title(p), "from config dir")


class TestCitySessionNames(CityCase_session_names):

    def test_spawn_carries_the_real_name(self):
        tp = self.transcript("s1", [title_line("custom-title", "plus-manager")])
        self.citizen_session("s1", tp)
        spawns = [e for e in self.of("spawn", self.events()) if e["id"] == "s:s1"]
        self.assertEqual(len(spawns), 1)
        self.assertEqual(spawns[0]["label"], "plus-manager")
        self.assertEqual(spawns[0]["task"], "v4-plus")

    def test_two_sessions_of_one_repo_differ(self):
        a = self.transcript("s1", [title_line("custom-title", "plus-manager")])
        b = self.transcript("s2", [title_line("ai-title", "Consignment phase 3 brief")])
        self.citizen_session("s1", a)
        self.line("s2", tp=b)
        labels = {e["id"]: e["label"] for e in self.of("spawn", self.events())}
        self.assertEqual(labels["s:s1"], "plus-manager")
        self.assertEqual(labels["s:s2"], "Consignment phase 3 brief")

    def test_no_title_keeps_the_old_label(self):
        tp = self.transcript("s1", [talk_line()])
        self.citizen_session("s1", tp)
        self.line("s3", tp="")
        labels = {e["id"]: e["label"] for e in self.of("spawn", self.events())}
        self.assertEqual(labels["s:s1"], "session")
        self.assertEqual(labels["s:s3"], "session")

    def test_a_task_manager_gets_its_name_too(self):
        tp = self.transcript("tm", [title_line("custom-title", "session-names Task Manager")])
        self.line("tm", tp=tp, role="task-manager")
        spawn = [e for e in self.of("spawn", self.events()) if e["id"] == "s:tm"][0]
        self.assertEqual(spawn["label"], "session-names Task Manager")
        self.assertEqual(spawn["role"], "task-manager")

    def test_a_later_title_sends_one_label_event(self):
        tp = self.transcript("s1", [talk_line()])
        self.citizen_session("s1", tp)
        self.events()
        self.add(tp, title_line("ai-title", "Sales invoice overpayment"))
        self.line("s1", tp=tp)
        self.line("s1", tp=tp)
        labels = self.of("label", self.events())
        self.assertEqual(len(labels), 1, labels)
        self.assertEqual((labels[0]["id"], labels[0]["label"]), ("s:s1", "Sales invoice overpayment"))

    def test_a_rename_sends_another(self):
        tp = self.transcript("s1", [title_line("ai-title", "First talk")])
        self.citizen_session("s1", tp)
        self.events()
        self.add(tp, title_line("custom-title", "plus-manager"))
        self.line("s1", tp=tp)
        self.assertEqual([e["label"] for e in self.of("label", self.events())], ["plus-manager"])

    def test_long_titles_are_cut_to_40(self):
        long_title = "Brief plus variant remove stock di and much more words here"
        tp = self.transcript("s1", [title_line("ai-title", long_title)])
        self.citizen_session("s1", tp)
        spawn = [e for e in self.of("spawn", self.events()) if e["id"] == "s:s1"][0]
        self.assertEqual(spawn["label"], long_title[:40])

    def test_snapshot_and_restart_keep_the_new_label(self):
        tp = self.transcript("s1", [talk_line()])
        self.citizen_session("s1", tp)
        self.add(tp, title_line("custom-title", "plus-manager"))
        self.line("s1", tp=tp)
        client = self.st.add_client()
        snap = json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1])
        self.assertIn("plus-manager", [a["label"] for a in snap["agents"] if a["id"] == "s:s1"])
        with open(self.world, encoding="utf-8") as fh:
            names = json.load(fh).get("names", {})
        self.assertEqual(names.get("s:s1", {}).get("label"), "plus-manager")

    def test_a_subagent_never_takes_the_session_title(self):
        tp = self.transcript("s1", [title_line("custom-title", "plus-manager")])
        self.citizen_session("s1", tp)
        self.line("s1", tp=tp, aid="w1", at="worker")
        self.line("s1", tp=tp, aid="w1", at="worker")
        events = self.events()
        spawn_w1 = [e for e in self.of("spawn", events) if e["id"] == "w1"]
        self.assertEqual([e["label"] for e in spawn_w1], ["worker"])
        self.assertEqual([e for e in self.of("label", events) if e["id"] == "w1"], [])

    def test_the_governor_gets_no_label_event(self):
        tp = self.transcript("gov", [title_line("custom-title", "v4-plus Manager")])
        self.line("gov", tp=tp)
        self.line("gov", tp=tp)
        events = self.events()
        self.assertEqual(self.of("label", events), [])
        self.assertEqual([e for e in self.of("spawn", events) if e["id"] == "s:gov"], [])

    def test_a_path_outside_the_root_is_never_read(self):
        outside = os.path.join(self.base, "s9.jsonl")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write(title_line("custom-title", "secret"))
        self.citizen_session("s9", outside)
        spawn = [e for e in self.of("spawn", self.events()) if e["id"] == "s:s9"][0]
        self.assertEqual(spawn["label"], "session")


def fn(name):
    f = getattr(ac, name, None)
    if f is None:
        raise AssertionError("bin/agent_city.py has no %s()" % name)
    return f


ASKS = [
    "Result: pass\n\n要你决定\n- 现在合并，还是等 E2E",
    "## 要你决定\n- 无法自动合并，要你来定",
    "结果：通过\n**要你决定**：现在合并吗",
    "Result: pass\nWhat changed: 2 files\nWhat to decide: merge now or wait",
    "### What to decide\n- nothing works without the key: send it or drop the step",
    "- **What to decide**: none of the two ports is free, pick a third",
    "What to decide\n\n- merge now or wait",
    "要你决定：无\n\n要继续下一步吗？",
    "What to decide: nothing\nQUESTION: which port",
    "QUESTION: which port should the city use",
    "Tests pass.\nQUESTION: merge now, or wait for the E2E",
    "  QUESTION: indented",
    "要现在合并吗？",
    "合并已完成。要我继续下一步吗？\n",
    "Shall I merge now?",
    "Two options are open. Which one do you want?   \n\n",
    "**Merge now?**",
    "Done with step 1. Go on with step 2 (the page)?",
    "下一步做页面，可以吗？」",
]


REPORTS = [
    "合并已经在 pc2 上开始了，11:00 左右完成。",
    "合并已经在 pc2 上开始了… 11:00 左右完成",
    "Done. 3 files changed, 12 tests pass.",
    "Why did it fail? The port was taken. Fixed now.",
    "为什么失败？端口被占用了。已经修好。",
    "See http://127.0.0.1:4777/?token=abc for the page.",
    "The line has QUESTION: in the middle, it is no question.",
    "I renamed the 要你决定 heading in the report.",
    "The report has a part named What to decide, it is empty.",
    "consignment-count-only: 4 rows counted.",
    "",
    "   \n",
]


# an empty decision section is a report, not a question (main manager, 2026-10-01)
EMPTY_SECTIONS = [
    # same line
    "Result: pass\nWhat changed: 2 files\nWhat to decide: nothing",
    "What to decide: none",
    "What to decide: None.",
    "What to decide: -",
    "What to decide: n/a",
    "What to decide: N/A",
    "**What to decide**: nothing",
    "- **What to decide**: nothing",
    "**What to decide:** Nothing.",
    "结果：通过\n改了什么：2 个文件\n要你决定：无",
    "要你决定：没有",
    "要你决定: 暂无",
    "要你决定：无。",
    "要你决定：-",
    "**要你决定**：无",
    "- **要你决定：** 暂无",
    # the next line
    "### What to decide\n- nothing",
    "## What to decide\nNone",
    "What to decide\n\nnothing",
    "What to decide\n-",
    "What to decide:\n- n/a",
    "## 要你决定\n无",
    "要你决定\n- 没有",
    "### 要你决定\n\n暂无",
    "要你决定：\n- 无",
    # a report goes on after the empty section
    "Result: pass\n\nWhat to decide\n- nothing\n\nTIME: est 75m, actual 52m (agent work only), wait 0m",
    "结果：通过\n\n要你决定：无\n\nTIME: est 75m, actual 52m",
]


def task(kind, **kw):
    out = {"id": "t1", "type": kind, "status": "running", "description": "d"}
    out.update(kw)
    return out


def R_status(ev, sid="main", aid="", at="", tool="", nt="", role="", **kw):
    line = {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": nt, "proj": "shop",
            "role": role, "desc": "", "sub": "", "q": ""}
    line.update(kw)
    return line


def note(sid, need="", bg="", **kw):
    line = {"ev": "StopNote", "sid": sid, "need": need, "bg": bg}
    line.update(kw)
    return line


def gov(state):
    return [{"type": "gov", "state": state}]


def drain_status(client):
    out = []
    while not client.queue.empty():
        out.append(json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1]))
    return out


def snapshot_status(st):
    client = st.add_client()
    return json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1])


def need(*names):
    for n in names:
        if tp.script_function_source(n) is None:
            raise AssertionError("function %s(...) not found in the page script" % n)
    return tp.page_fns(*names)


_CACHE = {}


def texts():
    if "texts" not in _CACHE:
        _CACHE["texts"] = tp.js_value(tp.const_object("TEXT"))
    return _CACHE["texts"]


class TestAsksOwner(unittest.TestCase):
    def test_empty_decision_section_is_a_report(self):
        asks_owner = fn("asks_owner")
        for text in EMPTY_SECTIONS:
            with self.subTest(text=text):
                self.assertIs(asks_owner(text), False)

    def test_asks(self):
        asks_owner = fn("asks_owner")
        for text in ASKS:
            with self.subTest(text=text):
                self.assertIs(asks_owner(text), True)

    def test_reports(self):
        asks_owner = fn("asks_owner")
        for text in REPORTS:
            with self.subTest(text=text):
                self.assertIs(asks_owner(text), False)

    def test_not_a_text(self):
        asks_owner = fn("asks_owner")
        for value in (None, 42, ["要你决定"], {"a": "?"}, b"ok?"):
            with self.subTest(value=value):
                self.assertIs(asks_owner(value), False)

    def test_long_reply_asks_at_the_end(self):
        asks_owner = fn("asks_owner")
        body = "一行报告。\n" * 3000
        self.assertIs(asks_owner(body), False)
        self.assertIs(asks_owner(body + "要继续吗？"), True)
        self.assertIs(asks_owner("要你决定\n" + body), True)


class TestBackgroundWork(unittest.TestCase):
    def test_work_that_counts(self):
        background_work = fn("background_work")
        for kind in ("shell", "subagent", "workflow", "monitor", "MCP task", "teammate", "cloud session",
                     "some_new_type"):
            with self.subTest(kind=kind):
                self.assertIs(background_work([task(kind)]), True)

    def test_nothing_in_flight(self):
        background_work = fn("background_work")
        for value in ([], None, "", "shell", 3, {"type": "shell"}, [None, "shell", 7]):
            with self.subTest(value=value):
                self.assertIs(background_work(value), False)

    def test_housekeeping_does_not_count(self):
        background_work = fn("background_work")
        house = [task("dream"), task("auto-mode scan"), task("memory import")]
        self.assertIs(background_work(house), False)
        self.assertIs(background_work(house + [task("shell", command="sleep 60")]), True)


class TestGovernorStatus(unittest.TestCase):
    def setUp(self):
        self.r = ac.Reducer()
        self.t = 0.0
        self.assertEqual(self.feed(R_status("UserPromptSubmit")), gov("busy"))

    def feed(self, line):
        self.t += 1.0
        return self.r.feed(line, self.t)

    def state(self):
        return self.r.snapshot()["gov"]["state"]

    def test_report_only_is_idle(self):
        self.assertEqual(self.feed(R_status("Stop")), gov("idle"))
        self.assertEqual(self.feed(note("main")), [])
        self.assertEqual(self.state(), "idle")

    def test_note_first_then_stop(self):
        self.assertEqual(self.feed(note("main")), gov("idle"))
        self.assertEqual(self.feed(R_status("Stop")), [])

    def test_idle_prompt_is_not_waiting(self):
        self.feed(R_status("Stop"))
        self.feed(note("main"))
        self.assertEqual(self.feed(R_status("Notification", nt="idle_prompt")), [])
        self.assertEqual(self.state(), "idle")

    def test_idle_prompt_while_busy_changes_nothing(self):
        self.assertEqual(self.feed(R_status("Notification", nt="idle_prompt")), [])
        self.assertEqual(self.state(), "busy")

    def test_reply_that_asks_is_waiting(self):
        self.assertEqual(self.feed(R_status("Stop")), gov("idle"))
        self.assertEqual(self.feed(note("main", need="1")), gov("waiting"))
        self.assertEqual(self.feed(R_status("Notification", nt="idle_prompt")), [])
        self.assertEqual(self.state(), "waiting")

    def test_asking_note_first_then_stop_stays_waiting(self):
        self.assertEqual(self.feed(note("main", need="1")), gov("waiting"))
        self.assertEqual(self.feed(R_status("Stop")), [])
        self.assertEqual(self.state(), "waiting")

    def test_background_work(self):
        self.assertEqual(self.feed(R_status("Stop")), gov("idle"))
        self.assertEqual(self.feed(note("main", bg="1")), gov("background"))
        self.assertEqual(self.feed(R_status("Notification", nt="idle_prompt")), [])
        self.assertEqual(self.state(), "background")

    def test_background_ends_with_the_next_note(self):
        self.feed(note("main", bg="1"))
        self.feed(R_status("Stop"))
        # the shell ended: Claude Code wakes the session, the wake-up turn ends with nothing in flight
        self.assertEqual(self.feed(R_status("Stop")), [])
        self.assertEqual(self.feed(note("main")), gov("idle"))

    def test_asking_wins_over_background(self):
        self.assertEqual(self.feed(note("main", need="1", bg="1")), gov("waiting"))

    def test_next_turn_is_busy_again(self):
        for flags in ({"need": "1"}, {"bg": "1"}, {}):
            with self.subTest(flags=flags):
                self.feed(note("main", **flags))
                self.assertEqual(self.feed(R_status("UserPromptSubmit")), gov("busy"))

    def test_open_prompts_are_waiting(self):
        self.assertEqual(self.feed(R_status("PermissionRequest", tool="Bash")), gov("waiting"))
        self.assertEqual(self.feed(R_status("PostToolUse", tool="Bash")), gov("busy"))
        self.assertEqual(self.feed(R_status("PreToolUse", tool="AskUserQuestion", q="Which one?")), gov("waiting"))
        self.assertEqual(self.feed(R_status("PostToolUse", tool="AskUserQuestion")), gov("busy"))
        self.assertEqual(self.feed(R_status("Notification", nt="permission_prompt")), gov("waiting"))
        self.assertEqual(self.feed(R_status("PermissionDenied", tool="Bash")), gov("busy"))
        self.assertEqual(self.feed(R_status("PreToolUse", tool="Agent", desc="d", sub="worker")), [])

    def test_a_note_with_an_agent_id_is_ignored(self):
        self.assertEqual(self.feed(note("main", need="1", aid="a1")), [])
        self.assertEqual(self.state(), "busy")
        self.assertEqual(self.r.snapshot()["agents"], [])


class TestCitizenStatus(unittest.TestCase):
    def setUp(self):
        self.r = ac.Reducer()
        self.t = 0.0
        self.feed(R_status("UserPromptSubmit"))                       # the governor
        self.feed(R_status("PostToolUse", sid="tm1", role="task-manager", tool="Write"))
        self.feed(R_status("PostToolUse", sid="h1", tool="Read"))    # a helper: no role, a citizen

    def feed(self, line):
        self.t += 1.0
        return self.r.feed(line, self.t)

    def agent(self, cid):
        return [a for a in self.r.snapshot()["agents"] if a["id"] == cid][0]

    def test_working_citizen_has_no_status(self):
        a = self.agent("s:tm1")
        self.assertEqual((a["status"], a["waiting"]), ("", False))

    def test_report_only_is_idle(self):
        self.assertEqual(self.feed(R_status("Stop", sid="tm1", role="task-manager")), [{"type": "idle", "id": "s:tm1"}])
        self.assertEqual(self.feed(note("tm1")), [])
        a = self.agent("s:tm1")
        self.assertEqual((a["status"], a["waiting"], a["stuck"]), ("idle", False, False))

    def test_first_seen_at_its_stop_is_idle(self):
        # the city started in the middle of this session's turn: its first line is the Stop
        out = self.feed(R_status("Stop", sid="late", role="task-manager"))
        self.assertEqual([e["type"] for e in out], ["spawn", "idle"])
        self.assertEqual(out[1], {"type": "idle", "id": "s:late"})
        self.assertEqual(self.agent("s:late")["status"], "idle")
        self.assertEqual(self.feed(note("late", need="1")), [{"type": "waiting", "id": "s:late"}])

    def test_idle_prompt_is_not_waiting(self):
        self.feed(R_status("Stop", sid="tm1", role="task-manager"))
        self.assertEqual(self.feed(R_status("Notification", sid="tm1", role="task-manager", nt="idle_prompt")), [])
        self.assertEqual(self.agent("s:tm1")["status"], "idle")
        self.assertEqual(self.feed(R_status("Notification", sid="h1", nt="idle_prompt")), [])
        self.assertEqual(self.agent("s:h1")["status"], "")

    def test_reply_that_asks_is_waiting(self):
        self.feed(R_status("Stop", sid="tm1", role="task-manager"))
        self.assertEqual(self.feed(note("tm1", need="1")), [{"type": "waiting", "id": "s:tm1"}])
        self.assertEqual(self.feed(R_status("Stop", sid="tm1", role="task-manager")), [])
        a = self.agent("s:tm1")
        self.assertEqual((a["status"], a["waiting"], a["stuck"]), ("waiting", True, False))

    def test_background_work_then_idle(self):
        self.assertEqual(self.feed(note("h1", bg="1")), [{"type": "background", "id": "s:h1"}])
        self.assertEqual(self.feed(R_status("Stop", sid="h1")), [])
        a = self.agent("s:h1")
        self.assertEqual((a["status"], a["waiting"]), ("background", False))
        self.assertEqual(self.feed(R_status("Stop", sid="h1")), [])
        self.assertEqual(self.feed(note("h1")), [{"type": "idle", "id": "s:h1"}])
        self.assertEqual(self.agent("s:h1")["status"], "idle")

    def test_same_note_twice_is_one_event(self):
        self.assertEqual(self.feed(note("tm1", need="1")), [{"type": "waiting", "id": "s:tm1"}])
        self.assertEqual(self.feed(note("tm1", need="1")), [])

    def test_resume_comes_first(self):
        for flags in ({"need": "1"}, {"bg": "1"}, {}):
            with self.subTest(flags=flags):
                self.feed(note("tm1", **flags))
                out = self.feed(R_status("PostToolUse", sid="tm1", role="task-manager", tool="Edit"))
                self.assertEqual(out[0], {"type": "resume", "id": "s:tm1"})
                self.assertEqual(out[1]["type"], "tool")
                self.assertEqual(self.agent("s:tm1")["status"], "")

    def test_prompt_resumes(self):
        self.feed(note("h1"))
        self.assertEqual(self.feed(R_status("UserPromptSubmit", sid="h1")), [{"type": "resume", "id": "s:h1"}])

    def test_permission_prompt_is_still_stuck(self):
        out = self.feed(R_status("Notification", sid="tm1", role="task-manager", nt="permission_prompt"))
        self.assertEqual(out, [{"type": "stuck", "id": "s:tm1", "question": "", "tool": ""}])

    def test_never_seen_session(self):
        before = self.r.snapshot()
        self.assertEqual(self.feed(note("ghost", need="1", bg="1")), [])
        self.assertEqual(self.r.snapshot(), before)
        self.assertNotIn("ghost", self.r.sessions)

    def test_subagents_keep_their_states(self):
        self.feed(R_status("SubagentStart", sid="tm1", aid="w1", at="worker"))
        self.assertEqual(self.feed(note("tm1", need="1", aid="w1")), [])
        self.assertEqual(self.feed(R_status("Notification", sid="tm1", aid="w1", at="worker", nt="idle_prompt")), [])
        w = self.agent("w1")
        self.assertEqual((w["status"], w["waiting"], w["stuck"], w["done"]), ("", False, False, False))
        self.assertEqual(self.agent("s:tm1")["status"], "")


class TestStatusInTheCity(unittest.TestCase):
    A = "/work/a/.git"
    B = "/work/b/.git"

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_status_")
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"),
                               start_repo=self.A, main_fn=Mains({self.A: "g1", self.B: "g2"}))
        self.t = 1000.0
        self.line("UserPromptSubmit", "g1", self.A)
        self.line("UserPromptSubmit", "g2", self.B)
        self.line("PostToolUse", "tm1", self.B, role="task-manager", tool="Write")
        self.client = self.st.add_client()
        drain_status(self.client)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def line(self, ev, sid, repo, role="", tool="", nt=""):
        self.t += 1.0
        self.st.feed_line({"ev": ev, "sid": sid, "aid": "", "at": "", "tool": tool, "nt": nt, "proj": "p",
                           "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo,
                           "ask": "", "wt": "", "file": "", "tp": "", "pid": ""}, self.t)

    def note(self, sid, need="", bg=""):
        self.t += 1.0
        self.st.feed_line({"ev": "StopNote", "sid": sid, "need": need, "bg": bg}, self.t)

    def govs(self):
        return {g["terr"]: g["state"] for g in snapshot_status(self.st)["govs"]}

    def status_events(self):
        return [(e["type"], e.get("id")) for e in drain_status(self.client)
                if e["type"] in ("gov", "waiting", "background", "idle", "resume", "stuck", "spawn", "leave")]

    def test_a_note_stays_in_its_sessions_territory(self):
        self.line("Stop", "g2", self.B)
        self.note("g2", bg="1")
        events = [e for e in drain_status(self.client) if e["type"] == "gov"]
        self.assertEqual([(e["state"], e["terr"], e["present"]) for e in events],
                         [("idle", ac.territory_id(self.B), True), ("background", ac.territory_id(self.B), True)])
        self.assertEqual(self.govs(), {ac.territory_id(self.A): "busy", ac.territory_id(self.B): "background"})

    def test_the_governor_keeps_the_seat(self):
        self.note("g1", need="1")
        snap = snapshot_status(self.st)
        self.assertEqual({g["terr"]: g["state"] for g in snap["govs"]}[ac.territory_id(self.A)], "waiting")
        self.assertEqual([a["id"] for a in snap["agents"]], ["s:tm1"])

    def test_citizen_status_reaches_the_page(self):
        self.note("tm1", bg="1")
        self.assertEqual(self.status_events(), [("background", "s:tm1")])
        a = snapshot_status(self.st)["agents"][0]
        self.assertEqual((a["id"], a["status"], a["waiting"], a["terr"]),
                         ("s:tm1", "background", False, ac.territory_id(self.B)))
        self.note("tm1")
        self.assertEqual(self.status_events(), [("idle", "s:tm1")])
        self.assertEqual(snapshot_status(self.st)["agents"][0]["status"], "idle")

    def test_idle_prompt_changes_nothing(self):
        self.line("Stop", "g1", self.A)
        self.line("Stop", "tm1", self.B, role="task-manager")
        drain_status(self.client)
        self.line("Notification", "g1", self.A, nt="idle_prompt")
        self.line("Notification", "tm1", self.B, role="task-manager", nt="idle_prompt")
        self.assertEqual([e for e in drain_status(self.client) if e["type"] in ("gov", "waiting", "stuck", "ask")], [])
        snap = snapshot_status(self.st)
        self.assertEqual({g["terr"]: g["state"] for g in snap["govs"]}[ac.territory_id(self.A)], "idle")
        self.assertEqual(snap["agents"][0]["status"], "idle")

    def test_never_seen_session(self):
        before = snapshot_status(self.st)
        self.note("ghost", need="1", bg="1")
        self.assertEqual(drain_status(self.client), [])
        after = snapshot_status(self.st)
        self.assertEqual((after["govs"], after["agents"]), (before["govs"], before["agents"]))


class TestPageTexts(unittest.TestCase):
    def test_words(self):
        t = texts()
        self.assertEqual((t["zh"].get("status.background"), t["en"].get("status.background")),
                         ("后台在跑", "Working in background"))
        self.assertEqual((t["zh"].get("status.idle"), t["en"].get("status.idle")), ("空闲", "Idle"))

    def test_waiting_words_stay(self):
        t = texts()
        self.assertEqual((t["zh"]["status.waiting"], t["zh"]["status.waiting_reply"]), ("等你", "等你回话"))


class TestPageColour(unittest.TestCase):
    def test_violet_in_every_theme(self):
        style = tp.style()
        for var in ("--bgrun-bg", "--bgrun-ink"):
            with self.subTest(var=var):
                self.assertEqual(len(re.findall(re.escape(var) + r"\s*:\s*#[0-9A-Fa-f]{6}", style)), 3,
                                 "%s is set for light, the dark media query and the dark theme" % var)

    def test_chip_pill_and_dot(self):
        style = tp.style()
        for selector in (r"\.chip\.bgrun", r"\.pill\.bgrun"):
            with self.subTest(selector=selector):
                self.assertRegex(style, selector + r"\{background:var\(--bgrun-bg\);color:var\(--bgrun-ink\)\}")
        self.assertRegex(style, r"\.sdot\.st-bgrun\{background:#[0-9A-Fa-f]{6}\}")

    def test_not_an_existing_colour(self):
        style = tp.style()
        m = re.search(r":root\{.*?--bgrun-bg\s*:\s*(#[0-9A-Fa-f]{6}).*?--bgrun-ink\s*:\s*(#[0-9A-Fa-f]{6})", style, re.S)
        self.assertIsNotNone(m, "--bgrun-bg and --bgrun-ink in :root")
        taken = {"#E1ECFF", "#3160B5", "#FFE1E8", "#C2345A", "#DAF5E8", "#1E8657", "#EDEFF7", "#5F6488",
                 "#FFF0C7", "#8A6000"}
        self.assertNotIn(m.group(1).upper(), taken)
        self.assertNotIn(m.group(2).upper(), taken)


class TestRequirementLines(unittest.TestCase):
    def test_status_section(self):
        with open(os.path.join(ROOT, "requirements", "city.md"), encoding="utf-8") as fh:
            text = fh.read()
        m = re.search(r"^## Status\n(.*?)(?=^## )", text, re.M | re.S)
        self.assertIsNotNone(m, "requirements/city.md has a Status section")
        body = m.group(1)
        for word in ("等你", "后台在跑", "空闲", "要你决定", "What to decide", "QUESTION:", "background_tasks",
                     "nothing", "none", "没有", "暂无", "n/a",
                     "idle_prompt", "StopNote"):
            with self.subTest(word=word):
                self.assertIn(word, body)


def RF(ev, file=None, **kw):
    raw = R_steps(ev, **kw)
    if file is not None:
        raw["file"] = file
    return raw


class TestToolEventNamesTheStep(Case_steps):
    """Server: a tool event carries the raw tool name, the edited file's name, a Task's description."""

    def tool_event(self, **kw):
        out = self.feed(RF("PostToolUse", aid="a1", at="worker", **kw))
        tools = [e for e in out if e.get("type") == "tool"]
        self.assertEqual(len(tools), 1, out)
        return tools[0]

    def test_raw_name_rides_along(self):
        self.spawn()
        for tool, kind in {"Edit": "Edit", "MultiEdit": "Edit", "Grep": "Read", "WebSearch": "Read",
                           "TodoWrite": "Other", "Agent": "Other", "mcp__github__create_pull_request": "Other"}.items():
            with self.subTest(tool=tool):
                e = self.tool_event(tool=tool)
                self.assertEqual(e["tool"], kind)
                self.assertEqual(e["name"], tool)

    def test_odd_names_are_dropped(self):
        self.spawn()
        for tool in ("Bad Name!", "x" * 65, "Edit;rm"):
            with self.subTest(tool=tool):
                self.assertEqual(self.tool_event(tool=tool)["name"], "")

    def test_edited_file_gives_only_its_name(self):
        self.spawn()
        for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            with self.subTest(tool=tool):
                self.assertEqual(self.tool_event(tool=tool, file="src/pay/checkout.py")["file"], "checkout.py")
        self.assertEqual(self.tool_event(tool="Edit", file="README.md")["file"], "README.md")
        long = "f" * 70 + ".py"
        self.assertEqual(self.tool_event(tool="Edit", file="a/" + long)["file"], long[:60])

    def test_no_file_when_unsafe_or_not_an_edit(self):
        self.spawn()
        for tool, file in (("Edit", "../x.py"), ("Edit", "/abs/x.py"), ("Edit", ""), ("Bash", "x.py"), ("Read", "x.py")):
            with self.subTest(tool=tool, file=file):
                self.assertNotIn("file", self.tool_event(tool=tool, file=file))

    def test_task_description_for_agent_and_task_only(self):
        self.spawn()
        self.assertEqual(self.tool_event(tool="Agent", desc="设置页表单")["desc"], "设置页表单")
        self.assertEqual(self.tool_event(tool="Task", desc="d" * 80)["desc"], "d" * 60)
        self.assertNotIn("desc", self.tool_event(tool="Bash", desc="run the tests"))
        self.assertNotIn("desc", self.tool_event(tool="Agent"))

    def test_a_session_citizen_gets_the_same(self):
        out = self.feed(RF("PostToolUse", sid="w9", role="worker", tool="Write", file="docs/guide.md"))
        tool = [e for e in out if e.get("type") == "tool"][0]
        self.assertEqual((tool["tool"], tool["name"], tool["file"]), ("Write", "Write", "guide.md"))


def world_of(*repos):
    """repos: (identity, lines) in arrival order (city-office: lines are no longer kept)."""
    w = ac.new_world()
    for ident, _lines in repos:
        ac.add_territory(w, ident, ac.repo_name(ident))
    w["floors"] = [ident for ident, _ in repos]
    return w


def function_src(fn):
    import inspect
    return inspect.getsource(fn)


class TestWorldFileWorld(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_world_")
        self.path = os.path.join(self.base, "home", "agent-city", "world.json")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_path_follows_agent_city_home(self):
        old = os.environ.get("AGENT_CITY_HOME")
        try:
            os.environ["AGENT_CITY_HOME"] = os.path.join(self.base, "h")
            self.assertEqual(ac.world_path(), os.path.join(self.base, "h", "world.json"))
            del os.environ["AGENT_CITY_HOME"]
            self.assertEqual(ac.world_path(), os.path.expanduser("~/.claude/agent-city/world.json"))
        finally:
            if old is None:
                os.environ.pop("AGENT_CITY_HOME", None)
            else:
                os.environ["AGENT_CITY_HOME"] = old

    def test_save_then_load_is_the_same_world(self):
        w = world_of(("/a/.git", 12000), ("/b/.git", 40))
        w["territories"]["/a/.git"]["reno_asked"] = True
        ac.save_world(self.path, w)
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ["world.json"], "temp file left behind")
        loaded, notice = ac.load_world(self.path)
        self.assertIsNone(notice)
        self.assertEqual(loaded, json.loads(json.dumps(w)))
        with open(self.path) as fh:
            self.assertEqual(json.load(fh)["v"], 1)

    def test_save_is_atomic(self):
        src = function_src(ac.save_world)
        self.assertIn("os.replace", src)
        self.assertRegex(src, r"tmp|temp|mkstemp")

    def test_missing_file_is_a_fresh_world(self):
        w, notice = ac.load_world(self.path)
        self.assertEqual(w, ac.new_world())
        self.assertIsNone(notice)
        self.assertFalse(os.path.exists(os.path.dirname(self.path)) and os.listdir(os.path.dirname(self.path)))

    def test_broken_or_unknown_file_is_moved_aside(self):
        good = world_of(("/a/.git", 10))
        cases = {"not json": b"{not json", "a list": b"[1, 2]", "future version": json.dumps(dict(good, v=2)).encode(),
                 "no version": json.dumps({"territories": {}, "order": []}).encode(),
                 "binary": b"\xff\xfe\x00junk"}
        for name, data in cases.items():
            with self.subTest(case=name):
                folder = os.path.dirname(self.path)
                shutil.rmtree(folder, ignore_errors=True)
                os.makedirs(folder)
                with open(self.path, "wb") as fh:
                    fh.write(data)
                w, notice = ac.load_world(self.path)
                self.assertEqual(w, ac.new_world())
                aside = [f for f in os.listdir(folder) if f.startswith("world.json.bad-")]
                self.assertEqual(len(aside), 1)
                self.assertRegex(aside[0], r"^world\.json\.bad-\d{8}-\d{6}$")
                with open(os.path.join(folder, aside[0]), "rb") as fh:
                    self.assertEqual(fh.read(), data)
                self.assertFalse(os.path.exists(self.path))
                self.assertIsInstance(notice, str)
                self.assertIn(aside[0], notice)
                self.assertRegex(notice, r"[一-鿿]", "the page log is Chinese")


if __name__ == "__main__":
    unittest.main()
