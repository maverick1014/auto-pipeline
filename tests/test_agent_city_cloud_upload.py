"""Failing tests, cloud-city-1 slice 3a: a machine uploads its own city
picture for the cloud page (requirements/city.md, "Cloud page").

One reducer: the local server already turns hook lines into the page's
snapshot and events. The uploader is ONE MORE PAGE CLIENT inside the server:
it gets the same snapshot and then the same events as the local page, cleans
them, and they ride on the sync the machine already makes (no extra request).

bin/agent_city_relay.py
  sync(address, key, dev, after, lines, timeout=10.0, view=None)
      view given -> the body gets "view". The ok data gains "city" (True only
      when the reply says "city": true) and "gen" (the reply's gen, else 0).
  read_cloud(path) -> the sorted list of relay hosts in the marker file
      (missing or broken file -> []).
  set_cloud(path, host, on) -> adds or removes HOST, written whole (tmp + mv);
      the file is removed when the last host goes. Hosts only, never a key.
  RelayHub(..., cloud_file=None, view_source=None)
      cloud_file: after every ANSWERED sync of a team the hub calls
          set_cloud(cloud_file, <team host>, <reply said city>). A relay that
          is down or refuses leaves the marker as it is.
      view_source: an object with
          take(host, rids, now) -> a view dict to send with this sync, or None
          sent(host, data, now) -> called after the sync: DATA is the ok data
                                   (with "city" and "gen") or None (down, refused)
      rids = the sorted repo ids joined to that team.
  CLI   python3 agent_city_relay.py cloud --secret <join file> --cloud-file <path> [--probe]
      prints ONE line, exit 0:  "on <host>" | "off <host>" | "none" (no join file).
      Without --probe: from the marker only, no network. With --probe: one
      sync (no lines); its reply sets the marker and decides the line; a relay
      that is down or refuses -> the marker decides. The key is never printed.

bin/agent_city.py  (its own block: "cloud-city")
  CLOUD_KEEP, CLOUD_DROP   frozensets of page message types. Together they are
      EXACTLY the types the page's apply() handles (bin/agent-city.html); a
      type on neither list is not uploaded. A new page message type must be
      put on one of them (this test fails until then).
      CLOUD_DROP = ask, ask_phase, ask_closed, chat (question and command
      text, chat text).
  cloud_clean(msg) -> a cleaned COPY for the cloud, or None (dropped):
      - a type in CLOUD_DROP, an unknown type, not a dict -> None
      - tool: no "file" key
      - stuck: "question" is ""
      - snapshot: "asks" is [], no "notice"; its world cleaned as below
      - world (and a snapshot's world): every territory without "balance" and
        "rules_note"; every building with "files": [], "hist": [], "name": ""
      - build: "files": [], "name": ""
      - in every string value: a word that starts with "/" or "~/" is cut to
        its last part (the relay's rule for sent lines), so no full path
      - everything else as it is (a person keeps its "label": the owner
        agreed to session names on his own rows, 2026-10-01)
  serve --cloud-snap-sec S   (default 60) a new picture is taken when S
      seconds passed since the last one AND something happened since.
  The uploader, while a joined relay says the cloud is on:
      - one picture per relay: only the territories, people, sites and events
        of repos JOINED to that relay. A repo that is not joined never leaves
        the machine (as today).
      - a view = {"label": the hub's device label, "gen", "counts",
        "snap" (a new picture) and/or "events" (since the last view)}
        counts = {"people": people in the picture, "wait": those waiting for
        the owner (waiting or stuck), "busy": those at work (not done, not
        waiting, not stuck, status "")}
      - nothing new -> no view, except one sign of life a minute
      - the reply's gen is not the uploader's gen -> the next view is a new picture
      - the relay says the cloud is off -> no view at all
      - it is not a browser: /health "clients" does not count it, four
        browsers still fit, and it never keeps the server from stopping
  The marker <AGENT_CITY_HOME>/cloud is kept by the server's hub (cloud_file).

Every test uses a fake relay on 127.0.0.1 and temp folders. Never a real key.

Run: python3 -m unittest tests.test_agent_city_cloud_upload
"""

import json
import os
import re
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

from relayhelp import FAKE_KEY, FakeRelay, hook_line, join, make_repo  # noqa: E402
from test_agent_city_server import ServerCase, wait_for  # noqa: E402
import agent_city as ac  # noqa: E402
import agent_city_relay as rl  # noqa: E402

PAGE = os.path.join(BIN, "agent-city.html")
MARK = "MARK-7f3a"


def page_types():
    with open(PAGE) as fh:
        src = fh.read()
    body = src[src.index("function apply(ev)"):src.index("const emit = ev => apply(ev)")]
    return set(re.findall(r"case '([a-z_]+)':", body))


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from strings(v)


def need(case, name, module=ac):
    case.assertTrue(hasattr(module, name), "%s.%s is missing" % (module.__name__, name))
    return getattr(module, name)


# --------------------------------------------------------------- the allow-list

class TestLists(unittest.TestCase):
    def test_every_page_message_type_is_decided(self):
        keep, drop = need(self, "CLOUD_KEEP"), need(self, "CLOUD_DROP")
        self.assertEqual(set(keep) & set(drop), set())
        self.assertEqual(set(keep) | set(drop), page_types(),
                         "a page message type is on neither cloud list (or a list names a type the page "
                         "does not know): decide whether it goes to the cloud")

    def test_what_never_goes_up(self):
        self.assertEqual(set(need(self, "CLOUD_DROP")), {"ask", "ask_phase", "ask_closed", "chat"})


class TestClean(unittest.TestCase):
    def clean(self, msg):
        return need(self, "cloud_clean")(msg)

    def test_dropped(self):
        for msg in ({"type": "ask", "id": "q1", "questions": [MARK]},
                    {"type": "ask_phase", "id": "q1"},
                    {"type": "ask_closed", "id": "q1", "text": MARK},
                    {"type": "chat", "to": "s:1", "entry": {"text": MARK}},
                    {"type": "something-new", "id": 1},
                    {"id": "no type"}, "text", None, 3, [1]):
            self.assertIsNone(self.clean(msg), msg)

    def test_plain_events_pass(self):
        for msg in ({"type": "waiting", "id": "s:1"}, {"type": "idle", "id": "s:1"},
                    {"type": "background", "id": "s:1"}, {"type": "done", "id": "s:1"},
                    {"type": "leave", "id": "s:1"}, {"type": "talk", "from": "s:1", "to": "s:2", "terr": "t1"},
                    {"type": "gov", "state": "busy", "terr": "t1", "present": True},
                    {"type": "label", "id": "s:1", "label": "cloud-city-1 Task Manager", "terr": "t1"},
                    {"type": "site", "terr": "t1", "id": "wt:ab12", "branch": "feat/x", "module": "x",
                     "status": "working", "human": False, "stalled": False, "x": 1, "z": 2},
                    {"type": "remote", "dev": "d2", "who": "Ann", "device": "pc2", "rid": "github.com/a/b",
                     "br": "main", "ev": {"type": "tool", "id": "r:d2:s:1", "tool": "Bash", "name": "Bash"}},
                    {"type": "team", "host": "relay.example", "state": "ok", "queued": 0}):
            self.assertEqual(self.clean(msg), msg)

    def test_a_copy_not_the_same_object(self):
        msg = {"type": "tool", "id": "s:1", "tool": "Edit", "name": "Edit", "file": "a.py"}
        out = self.clean(msg)
        self.assertIsNot(out, msg)
        self.assertEqual(msg["file"], "a.py", "the local page still gets the file name")

    def test_tool_has_no_file(self):
        out = self.clean({"type": "tool", "id": "s:1", "tool": "Edit", "name": "Edit",
                          "file": "checkout_%s.py" % MARK, "desc": "write the checkout test"})
        self.assertEqual(out, {"type": "tool", "id": "s:1", "tool": "Edit", "name": "Edit",
                               "desc": "write the checkout test"})

    def test_stuck_has_no_question(self):
        out = self.clean({"type": "stuck", "id": "s:1", "question": "retry? " + MARK, "tool": "Bash"})
        self.assertEqual(out, {"type": "stuck", "id": "s:1", "question": "", "tool": "Bash"})

    def world(self):
        return {"cell": 2, "x0": 0, "z0": 0, "w": 2, "h": 2, "rows": ["gg", "gg"], "links": [],
                "territories": [{
                    "id": "t1", "name": "shop", "plan": "grass", "lines": 120,
                    "balance": {"build": {"files": ["src/%s.py" % MARK]}}, "rules_note": MARK,
                    "plots": [{"k": "h1", "x": 1, "z": 1, "d": "house"}],
                    "buildings": [{"plot": "h1", "type": "house", "by": "worker 1", "x": 1, "z": 1,
                                   "files": ["src/%s.py" % MARK], "hist": [{"by": "w", "file": MARK}],
                                   "q": "good", "home": True, "lv": 1, "name": "module " + MARK}],
                    "offices": [], "rest": None,
                    "sites": [{"id": "wt:ab12", "branch": "feat/x", "module": "x", "status": "working",
                               "human": False, "stalled": False, "x": 3, "z": 3}]}]}

    def check_world(self, world):
        terr = world["territories"][0]
        self.assertNotIn("balance", terr)
        self.assertNotIn("rules_note", terr)
        self.assertEqual((terr["name"], terr["lines"], terr["plots"]),
                         ("shop", 120, [{"k": "h1", "x": 1, "z": 1, "d": "house"}]))
        self.assertEqual(terr["buildings"], [{"plot": "h1", "type": "house", "by": "worker 1", "x": 1, "z": 1,
                                              "files": [], "hist": [], "q": "good", "home": True,
                                              "lv": 1, "name": ""}])
        self.assertEqual(terr["sites"][0]["branch"], "feat/x")
        self.assertEqual(world["rows"], ["gg", "gg"])

    def test_snapshot(self):
        snap = {"type": "snapshot", "gov": {"state": "idle", "terr": "t1"}, "govs": [{"terr": "t1", "state": "idle"}],
                "agents": [{"id": "s:1", "role": "task-manager", "label": "cloud-city-1 Task Manager",
                            "task": "", "stuck": False, "waiting": True, "done": False, "status": "waiting",
                            "tools": {"Edit": 2}, "terr": "t1", "relay": None, "lead": "", "office": None}],
                "asks": [{"id": "q1", "what": "rm -rf " + MARK, "questions": [MARK]}],
                "governors": 1, "shows": [], "world": self.world(), "notice": "note " + MARK}
        out = self.clean(snap)
        self.assertEqual(out["asks"], [])
        self.assertNotIn("notice", out)
        self.assertEqual(out["agents"], snap["agents"], "people keep their name and state")
        self.assertEqual((out["gov"], out["govs"], out["governors"]), (snap["gov"], snap["govs"], 1))
        self.check_world(out["world"])
        self.assertFalse([s for s in strings(out) if MARK in s])
        self.assertEqual(len(snap["asks"]), 1, "the input is not changed")

    def test_world_event(self):
        out = self.clean({"type": "world", "world": self.world()})
        self.check_world(out["world"])
        self.assertFalse([s for s in strings(out) if MARK in s])

    def test_build_event(self):
        out = self.clean({"type": "build", "id": "s:1", "terr": "t1", "plot": "h1", "btype": "house",
                          "x": 1, "z": 1, "by": "worker 1", "q": "good", "home": True,
                          "files": ["src/%s.py" % MARK], "name": "module " + MARK, "lv": 1})
        self.assertEqual((out["files"], out["name"], out["btype"], out["by"]), ([], "", "house", "worker 1"))

    def test_no_full_path_in_any_text(self):
        out = self.clean({"type": "spawn", "id": "a:1", "role": "worker",
                          "label": "worker", "task": "fix /Users/zz/proj/api/x.py and ~/notes/todo.md now",
                          "terr": "t1", "from": "s:1", "lead": "s:1", "office": None})
        self.assertEqual(out["task"], "fix x.py and todo.md now")
        out = self.clean({"type": "tool", "id": "s:1", "tool": "Agent", "name": "Agent",
                          "desc": "read /private/tmp/%s/report.txt" % MARK})
        self.assertEqual(out["desc"], "read report.txt")

    def test_result_is_json(self):
        json.dumps(self.clean({"type": "world", "world": self.world()}))


# ------------------------------------------------------------- the relay client

class ClientCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_cloud_"))
        self.fake = FakeRelay()
        self.fake.city = True
        self.repo = make_repo(self.base)
        self.marker = os.path.join(self.base, "cityhome", "cloud")

    def tearDown(self):
        import shutil
        self.fake.stop()
        shutil.rmtree(self.base, ignore_errors=True)

    def hub(self, **kw):
        opts = dict(relay_sec=0, dev_id="dev-me", label="mac-1", join_ttl=0, timeout=3.0)
        opts.update(kw)
        return rl.RelayHub(**opts)


class TestSync(ClientCase):
    def test_view_rides_on_the_sync(self):
        v = {"label": "mac-1", "gen": 1, "counts": {"people": 0, "busy": 0, "wait": 0},
             "snap": [{"type": "snapshot"}]}
        state, data = rl.sync(self.fake.url, FAKE_KEY, "dev-me", 0, [], view=v)
        self.assertEqual(state, "ok")
        self.assertEqual((data["city"], data["gen"]), (True, 1))
        self.assertEqual(self.fake.sync_bodies()[0]["view"], v)

    def test_no_view_no_key_in_the_body(self):
        state, data = rl.sync(self.fake.url, FAKE_KEY, "dev-me", 0, [])
        self.assertEqual(set(self.fake.sync_bodies()[0]), {"dev", "after", "lines"})
        self.assertEqual((data["city"], data["gen"]), (True, 0))

    def test_an_old_relay_means_cloud_off(self):
        self.fake.city = False
        state, data = rl.sync(self.fake.url, FAKE_KEY, "dev-me", 0, [])
        self.assertEqual((state, data["city"], data["gen"]), ("ok", False, 0))


class TestMarker(ClientCase):
    def test_set_and_read(self):
        read, put = need(self, "read_cloud", rl), need(self, "set_cloud", rl)
        self.assertEqual(read(self.marker), [])
        put(self.marker, "b.example", True)
        put(self.marker, "a.example", True)
        put(self.marker, "a.example", True)
        self.assertEqual(read(self.marker), ["a.example", "b.example"])
        put(self.marker, "b.example", False)
        self.assertEqual(read(self.marker), ["a.example"])
        put(self.marker, "a.example", False)
        self.assertFalse(os.path.exists(self.marker), "no host left: no file")
        put(self.marker, "zz.example", False)
        self.assertFalse(os.path.exists(self.marker))

    def test_broken_file_reads_empty(self):
        os.makedirs(os.path.dirname(self.marker))
        with open(self.marker, "wb") as fh:
            fh.write(b"\xff\xfe\x00")
        self.assertEqual(need(self, "read_cloud", rl)(self.marker), [])

    def test_the_hub_keeps_the_marker(self):
        join(self.repo, self.fake.url)
        hub = self.hub(cloud_file=self.marker)
        hub.offer(hook_line(self.repo))
        hub.tick()
        self.assertEqual(rl.read_cloud(self.marker), [self.fake.host])
        with open(self.marker) as fh:
            self.assertNotIn(FAKE_KEY, fh.read())
        self.fake.mode = "error"
        hub.tick()
        self.assertEqual(rl.read_cloud(self.marker), [self.fake.host], "a relay that is down decides nothing")
        self.fake.mode = "ok"
        self.fake.city = False
        hub.tick()
        self.assertEqual(rl.read_cloud(self.marker), [])

    def cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(BIN, "agent_city_relay.py"), "cloud"] + list(args),
                              capture_output=True, text=True, timeout=30)

    def test_cli_from_the_marker(self):
        secret = join(self.repo, self.fake.url)
        r = self.cli("--secret", secret, "--cloud-file", self.marker)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "off " + self.fake.host), r.stderr)
        rl.set_cloud(self.marker, self.fake.host, True)
        r = self.cli("--secret", secret, "--cloud-file", self.marker)
        self.assertEqual(r.stdout.strip(), "on " + self.fake.host)
        self.assertEqual(self.fake.requests, [], "no network without --probe")

    def test_cli_probe(self):
        secret = join(self.repo, self.fake.url)
        r = self.cli("--secret", secret, "--cloud-file", self.marker, "--probe")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "on " + self.fake.host), r.stderr)
        self.assertEqual(rl.read_cloud(self.marker), [self.fake.host])
        self.assertEqual(len(self.fake.sync_bodies()), 1)
        self.assertEqual(self.fake.sync_bodies()[0]["lines"], [])
        self.assertNotIn("view", self.fake.sync_bodies()[0])
        self.fake.city = False
        r = self.cli("--secret", secret, "--cloud-file", self.marker, "--probe")
        self.assertEqual(r.stdout.strip(), "off " + self.fake.host)
        self.assertEqual(rl.read_cloud(self.marker), [])
        self.assertNotIn(FAKE_KEY, r.stdout + r.stderr)

    def test_cli_probe_relay_down_keeps_the_marker(self):
        secret = join(self.repo, self.fake.url)
        rl.set_cloud(self.marker, self.fake.host, True)
        self.fake.mode = "error"
        r = self.cli("--secret", secret, "--cloud-file", self.marker, "--probe")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "on " + self.fake.host))
        self.fake.mode = "refuse"
        r = self.cli("--secret", secret, "--cloud-file", self.marker, "--probe")
        self.assertEqual(r.stdout.strip(), "on " + self.fake.host)

    def test_cli_not_joined(self):
        r = self.cli("--secret", os.path.join(self.repo, ".secrets", "agent-city-relay"),
                     "--cloud-file", self.marker, "--probe")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "none"))
        self.assertEqual(self.fake.requests, [])


class Source:
    def __init__(self):
        self.takes = []
        self.sents = []
        self.next = None

    def take(self, host, rids, now):
        self.takes.append((host, list(rids)))
        return self.next

    def sent(self, host, data, now):
        self.sents.append((host, data))


class TestHubView(ClientCase):
    def setUp(self):
        super().setUp()
        join(self.repo, self.fake.url)
        self.src = Source()
        self.hub_ = self.hub(view_source=self.src)
        self.hub_.offer(hook_line(self.repo))

    def test_source_is_asked_and_told(self):
        self.hub_.tick()
        self.assertEqual(self.src.takes, [(self.fake.host, ["github.com/acme/shop"])])
        self.assertNotIn("view", self.fake.sync_bodies()[0], "the source gave nothing")
        host, data = self.src.sents[0]
        self.assertEqual((host, data["city"], data["gen"]), (self.fake.host, True, 0))

    def test_the_view_goes_with_the_sync(self):
        v = {"label": "mac-1", "gen": 4, "counts": {"people": 1, "busy": 1, "wait": 0},
             "snap": [{"type": "snapshot"}]}
        self.src.next = v
        self.hub_.tick()
        body = self.fake.sync_bodies()[0]
        self.assertEqual(body["view"], v)
        self.assertEqual(len(body["lines"]), 1, "the line and the view share one request")
        self.assertEqual(self.src.sents[0][1]["gen"], 4)
        self.assertEqual(len(self.fake.requests), 1)

    def test_down_or_refused_is_told_as_none(self):
        self.fake.mode = "error"
        self.hub_.tick()
        self.fake.mode = "refuse"
        self.hub_.tick()
        self.assertEqual([d for _, d in self.src.sents], [None, None])

    def test_no_source_is_today(self):
        hub = self.hub()
        hub.offer(hook_line(self.repo))
        hub.tick()
        self.assertEqual(set(self.fake.sync_bodies()[-1]), {"dev", "after", "lines"})


# ------------------------------------------------------- the server uploads

class UploadCase(ServerCase):
    def setUp(self):
        super().setUp()
        self.fake = FakeRelay()
        self.fake.city = True
        self.repo = make_repo(self.base)
        join(self.repo, self.fake.url)
        self.marker = os.path.join(self.base, "cityhome", "cloud")

    def tearDown(self):
        self.fake.stop()
        super().tearDown()

    def up(self, idle="60", relay_sec="0.2", snap_sec="60"):
        return self.start("--idle-sec", idle, "--relay-sec", relay_sec, "--cloud-snap-sec", snap_sec)

    def add(self, repo=None, **fields):
        self.append(json.dumps(hook_line(repo or self.repo, **fields)) + "\n")

    def picture(self):
        held = wait_for(lambda: self.fake.view_of(), timeout=10)
        self.assertTrue(held, "no picture reached the relay")
        self.assertEqual(held["snap"][0]["type"], "snapshot")
        return held

    def all_events(self):
        """Every event of every view sent so far (a new picture empties the relay's own list)."""
        return [m for _, v in list(self.fake.view_log) for m in v.get("events") or []]

    def last_snap(self):
        snaps = [v["snap"] for _, v in list(self.fake.view_log) if "snap" in v]
        return snaps[-1][0] if snaps else None

    def view_bodies(self):
        return [b for b in self.fake.sync_bodies() if isinstance(b, dict) and "view" in b]

    def local_snapshot(self):
        client = self.sse()
        return [m for m in client.messages if m.get("type") == "snapshot"][0]


class TestPictureGoesUp(UploadCase):
    def test_the_picture_is_the_local_page_cleaned(self):
        # A first picture may be taken a moment before the person appears (then the
        # person is an event of it); with a short snap time the next picture holds it.
        self.up(snap_sec="0.5")
        self.add(sid="s1")
        self.assertTrue(wait_for(lambda: self.health()["agents"] == 1))
        self.assertTrue(wait_for(lambda: (self.last_snap() or {}).get("agents"), timeout=10),
                        "the picture with the person never reached the relay")
        held = self.fake.view_of()
        snap = held["snap"][0]
        local = self.local_snapshot()
        self.assertEqual([a["id"] for a in snap["agents"]], [a["id"] for a in local["agents"]])
        self.assertEqual(snap["agents"][0]["label"], local["agents"][0]["label"])
        self.assertEqual([t["name"] for t in snap["world"]["territories"]], ["shop"])
        self.assertEqual(snap["asks"], [])
        self.assertEqual(held["label"], rl._default_label())
        self.assertEqual(held["counts"], {"people": 1, "busy": 1, "wait": 0})
        self.assertGreaterEqual(held["gen"], 1)

    def test_events_follow_in_the_same_picture(self):
        self.up()
        self.add(sid="s1")
        gen = self.picture()["gen"]
        self.assertTrue(wait_for(lambda: self.health()["agents"] == 1))
        self.add(sid="s1", tool="Read")
        self.assertTrue(wait_for(lambda: [m for m in self.all_events() if m.get("type") == "tool"
                                          and m.get("tool") == "Read"], timeout=10),
                        "the tool event never reached the relay")
        self.assertEqual(self.fake.view_of()["gen"], gen, "events do not start a new picture")
        snaps = [v for _, v in self.fake.view_log if "snap" in v]
        self.assertEqual(len(snaps), 1)

    def test_waiting_is_counted(self):
        self.up()
        self.add(sid="s1")
        self.picture()
        self.add(sid="s1", ev="Stop")
        self.append(json.dumps({"ev": "StopNote", "sid": "s1", "need": "1", "bg": ""}) + "\n")
        self.assertTrue(wait_for(lambda: (self.fake.view_of() or {}).get("counts") ==
                                 {"people": 1, "busy": 0, "wait": 1}, timeout=10),
                        "counts: %r" % ((self.fake.view_of() or {}).get("counts"),))
        self.assertTrue([m for m in self.all_events() if m.get("type") == "waiting"])


class TestOnlyJoined(UploadCase):
    def test_a_repo_that_is_not_joined_never_goes_up(self):
        private = make_repo(self.base, name="private-zone", origin="git@github.com:Acme/Private.git")
        self.up(snap_sec="0.5")
        self.add(sid="s1")
        self.add(private, sid="p1")
        self.assertTrue(wait_for(lambda: self.health()["agents"] == 2))
        self.picture()
        local = self.local_snapshot()
        self.assertEqual(sorted(t["name"] for t in local["world"]["territories"]), ["private-zone", "shop"],
                         "the local page shows both, as today")
        mine = {t["id"] for t in local["world"]["territories"] if t["name"] == "shop"}
        hidden = [a["id"] for a in local["agents"] if a["terr"] not in mine]
        self.assertEqual(len(hidden), 1)
        self.add(private, sid="p1", tool="Read")
        self.add(sid="s1", tool="Read")
        self.assertTrue(wait_for(lambda: [m for m in self.all_events() if m.get("type") == "tool"],
                                 timeout=10))
        self.assertTrue(wait_for(lambda: (self.last_snap() or {}).get("agents"), timeout=10))
        time.sleep(0.6)
        held = self.fake.view_of()
        snap = self.last_snap()
        self.assertEqual([t["name"] for t in snap["world"]["territories"]], ["shop"])
        self.assertEqual(len(snap["agents"]), 1)
        self.assertEqual(held["counts"]["people"], 1)
        for _, v in list(self.fake.view_log):
            for one in v.get("snap") or []:
                if one.get("type") == "snapshot":
                    self.assertEqual([t["name"] for t in one["world"]["territories"]], ["shop"])
        for link in snap["world"].get("links", []):
            self.assertTrue({link["a"], link["b"]} <= mine, "a link to a hidden territory: %r" % link)
        text = json.dumps(self.fake.sync_bodies())
        self.assertNotIn("private-zone", text)
        self.assertNotIn(hidden[0], json.dumps([v for _, v in self.fake.view_log]))


class TestNothingPrivate(UploadCase):
    def test_no_path_no_question_no_file(self):
        self.up()
        self.add(sid="s1", desc="fix %s/api/x.py" % self.repo)
        self.picture()
        self.add(sid="s1", tool="Edit", file="src/%s_file.py" % MARK, tp="/tmp/%s-tp.jsonl" % MARK,
                 q="a question " + MARK)
        self.add(sid="s1", ev="PreToolUse", tool="AskUserQuestion", q="deploy now? " + MARK, ask="q")
        self.add(sid="s1", tool="Bash")
        self.assertTrue(wait_for(lambda: [m for m in self.all_events() if m.get("tool") == "Bash"],
                                 timeout=10))
        text = json.dumps(self.fake.sync_bodies())
        self.assertNotIn(MARK, text)
        self.assertNotIn(self.base, text, "a full path went up")
        self.assertNotIn(FAKE_KEY, text)


class TestCost(UploadCase):
    def test_cloud_off_sends_no_view(self):
        self.fake.city = False
        self.up()
        self.add(sid="s1")
        self.assertTrue(wait_for(lambda: self.fake.sent_lines()))
        time.sleep(1.2)
        self.assertEqual(self.view_bodies(), [])
        self.assertFalse(os.path.exists(self.marker))

    def test_a_quiet_city_sends_no_more_views(self):
        self.up()
        self.add(sid="s1")
        self.picture()
        time.sleep(0.8)
        before = len(self.view_bodies())
        time.sleep(2.0)   # about ten syncs
        self.assertLessEqual(len(self.view_bodies()) - before, 1,
                             "nothing happened: at most a sign of life, not a view per sync")
        self.assertGreater(len(self.fake.sync_bodies()), before + 5, "the syncs themselves go on")

    def test_a_new_picture_after_snap_sec_only_when_something_happened(self):
        self.up(snap_sec="0.6")
        self.add(sid="s1")
        first = self.picture()["gen"]
        end = time.monotonic() + 2.5
        while time.monotonic() < end:
            self.add(sid="s1", tool="Read")
            time.sleep(0.2)
        gens = [v["gen"] for _, v in self.fake.view_log if "snap" in v]
        self.assertGreaterEqual(len(gens), 3, "busy: a new picture about every 0.6 s")
        self.assertEqual(gens, sorted(set(gens)), "every new picture has a higher gen")
        self.assertEqual(gens[0], first)
        time.sleep(1.0)
        quiet = len([1 for _, v in self.fake.view_log if "snap" in v])
        time.sleep(2.0)
        self.assertEqual(len([1 for _, v in self.fake.view_log if "snap" in v]), quiet,
                         "nothing happened: no new picture")

    def test_a_lost_picture_is_sent_again(self):
        self.up()
        self.add(sid="s1")
        self.picture()
        self.fake.lose_views()
        self.assertTrue(wait_for(lambda: self.fake.view_of(), timeout=10),
                        "the relay said gen 0: the uploader must send a new picture")
        snaps = [v for _, v in self.fake.view_log if "snap" in v]
        self.assertEqual(len(snaps), 2)
        self.assertGreater(snaps[1]["gen"], snaps[0]["gen"])


class TestMarkerAndBrowsers(UploadCase):
    def test_the_server_keeps_the_marker(self):
        self.up()
        self.add(sid="s1")
        self.assertTrue(wait_for(lambda: rl.read_cloud(self.marker) == [self.fake.host], timeout=10))
        self.fake.city = False
        self.assertTrue(wait_for(lambda: rl.read_cloud(self.marker) == [], timeout=10))

    def test_the_uploader_is_not_a_browser(self):
        self.up()
        self.add(sid="s1")
        self.picture()
        self.assertEqual(self.health()["clients"], 0)
        clients = [self.sse() for _ in range(4)]
        self.assertEqual([c.status for c in clients], [200] * 4, "four browsers still fit")
        self.assertEqual(self.health()["clients"], 4)

    def test_it_never_keeps_the_server_up(self):
        proc = self.up(idle="1.5")
        self.add(sid="s1")
        self.picture()
        self.assertTrue(wait_for(lambda: proc.poll() is not None, timeout=10),
                        "no browser, no new lines: the server stops after the idle time, cloud or not")


if __name__ == "__main__":
    unittest.main()
