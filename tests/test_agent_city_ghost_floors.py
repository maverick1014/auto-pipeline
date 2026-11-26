"""city-ghost-floors: a floor whose local repo folder no longer exists is dropped (owner, 2026-11-26).

Territory identity kinds the city knows (bin/agent_city.py): a git common dir path ("<repo>/.git" or a
bare "x.git"; a worktree has its repo's), a plain folder path, "dir:<name>" (old data, dropped at
load), and the demo office's "/demo/..." identities (never in world.json). Only an absolute path of
this machine is checked (territory_folder_gone); every other kind is never dropped.

  G1 world.json with 3 floors, one folder gone: after start 2 floors; the file has no trace of the
     third in territories, order, floors, gov_seen; its design file is still there.
  G2 while the server runs a folder is removed: one sweep drops it, a page client gets the change.
  G3 a gone folder with a live session stays.
  G4 "/demo/..." and non-local kinds are never dropped.
  G5 a dropped repo whose folder is back and a session starts there: a floor again, the old design.
  G6 no gone floor: world.json is not rewritten (byte-identical).
  G7 the sweep looks at most once a minute.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))

import agent_city as ac  # noqa: E402
from cityhelp import Mains, drain  # noqa: E402

COLORS = {"accent": "#2E7D6B", "carpet": "#E4DCCB", "manager_floor": "#D9C2A0", "pantry_floor": "#EEEAE0",
          "desk": "#EFDAB5", "desk_leg": "#BBA27C", "chair": "#3E4560", "meeting_rug": "#A9BCE0",
          "manager_rug": "#C97B66"}
GOOD = {"v": 1, "name": "ghost", "why": "test", "colors": COLORS, "decor": ["cashier", "none", "goods"]}


class GhostCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_ghost_")
        self.world_path = os.path.join(self.base, "world.json")
        self.floors_dir = os.path.join(self.base, "floors")
        os.makedirs(self.floors_dir)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def repo(self, name, create=True):
        folder = os.path.join(self.base, "repos", name)
        if create:
            os.makedirs(os.path.join(folder, ".git"))
        return os.path.join(folder, ".git")

    def write_world(self, idents, **more):
        world = {"v": 1, "territories": {i: {"name": ac.repo_name(i)} for i in idents},
                 "order": list(idents), "floors": list(idents)}
        world.update(more)
        with open(self.world_path, "w", encoding="utf-8") as fh:
            json.dump(world, fh)

    def read_world(self):
        with open(self.world_path, encoding="utf-8") as fh:
            return json.load(fh)

    def city(self, **more):
        kw = dict(world_path=self.world_path, floors_dir=self.floors_dir, main_fn=Mains({}))
        kw.update(more)
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), **kw)

    def start_line(self, ident, sid="s1"):
        return {"ev": "SessionStart", "sid": sid, "aid": "", "at": "", "tool": "", "nt": "", "proj": "app",
                "role": "", "desc": "", "sub": "", "q": "", "klen": "", "repo": ident, "kind": "", "ask": "",
                "wt": "", "file": "", "pid": "4242"}


class TestGhostFloors(GhostCase):
    def test_G1_start_drops_the_gone_floor_and_keeps_its_design(self):
        a, b, c = self.repo("a"), self.repo("b"), self.repo("c", create=False)
        self.write_world([a, b, c], gov_seen={c: "old-sid", a: "sa"})
        design = os.path.join(self.floors_dir, ac.territory_id(c) + ".json")
        with open(design, "w", encoding="utf-8") as fh:
            json.dump(GOOD, fh)
        st = self.city()
        self.assertEqual(len(st.floors()), 2)
        on_disk = self.read_world()
        self.assertNotIn(c, on_disk["territories"])
        self.assertNotIn(c, on_disk["order"])
        self.assertNotIn(c, on_disk["floors"])
        self.assertNotIn(c, on_disk.get("gov_seen", {}))
        self.assertIn(a, on_disk["gov_seen"])
        self.assertNotIn(c, open(self.world_path, encoding="utf-8").read())
        self.assertTrue(os.path.exists(design), "the design file stays")

    def test_G2_a_folder_removed_while_running_is_dropped_and_told(self):
        a, b = self.repo("a"), self.repo("b")
        self.write_world([a, b], gov_seen={a: "sa", b: "sb"})
        st = self.city()
        client = st.add_client()
        drain(client)
        shutil.rmtree(os.path.dirname(b))
        self.assertEqual(st.sweep_gone_floors(1000.0), 1)
        self.assertEqual(st.floors(), [ac.territory_id(a)])
        kinds = [e.get("type") for e in drain(client)]
        self.assertIn("world", kinds)
        self.assertIn("snapshot", kinds)
        on_disk = self.read_world()
        for key in ("territories", "order", "floors", "gov_seen"):
            self.assertNotIn(b, on_disk.get(key, {}), key)
        self.assertIn(a, on_disk["gov_seen"])

    def test_G3_a_gone_folder_with_a_live_session_stays(self):
        a = self.repo("a", create=False)
        b = self.repo("b")
        self.write_world([b])
        st = self.city(start_repo=b)
        st.feed_line(self.start_line(a), 1000.0)    # a session of a repo whose folder is gone
        self.assertIn(a, st.world["territories"])
        self.assertEqual(st.sweep_gone_floors(1000.0), 0)
        self.assertIn(a, st.world["territories"])
        # a live lock holder keeps a floor too
        c = self.repo("c", create=False)
        st2 = self.city(world_path=None, main_fn=Mains({c: "tm"}))
        ac.add_territory(st2.world, c, "c")
        st2.world["floors"] = [c]
        self.assertEqual(st2.sweep_gone_floors(1000.0), 0)
        self.assertIn(c, st2.world["territories"])

    def test_G4_demo_and_non_local_kinds_are_never_gone(self):
        for ident in ("/demo/auto-pipeline/.git", "/demo/v3/.git", "dir:shop", "shop", "git@host:o/r.git",
                      "https://host/o/r.git", "cloud:abc123", ""):
            self.assertFalse(ac.territory_folder_gone(ident), ident)
        self.assertTrue(ac.territory_folder_gone(self.repo("nope", create=False)))
        self.assertFalse(ac.territory_folder_gone(self.repo("yes")))
        self.assertTrue(ac.territory_folder_gone(os.path.join(self.base, "plain-gone")))
        os.makedirs(os.path.join(self.base, "plain-here"))
        self.assertFalse(ac.territory_folder_gone(os.path.join(self.base, "plain-here")))
        # a world holding such identities keeps them through start and sweep
        keep = ["/demo/v4-plus/.git", "shop", "git@host:o/r.git"]
        self.write_world(keep)
        st = self.city()
        st.sweep_gone_floors(1000.0)
        self.assertEqual(sorted(st.world["territories"]), sorted(keep))

    def test_G5_a_dropped_repo_that_comes_back_is_a_floor_with_its_old_design(self):
        a, b = self.repo("a"), self.repo("b")
        self.write_world([a, b])
        st = self.city()
        self.assertEqual(st.set_design(ac.territory_id(b), GOOD, "owner")[0], 200)
        shutil.rmtree(os.path.dirname(b))
        st2 = self.city()
        self.assertNotIn(b, st2.world["territories"])
        os.makedirs(b)
        st2.feed_line(self.start_line(b), 1000.0)
        st2.scan_floors()      # the loop's own look at the floor files (every 2 s) takes the design back
        tid = ac.territory_id(b)
        self.assertIn(b, st2.world["territories"])
        self.assertIn(tid, st2.floors())
        self.assertIn(tid, st2.designs())
        self.assertEqual(st2.designs()[tid]["name"], "ghost")

    def test_G6_no_gone_floor_leaves_world_json_byte_identical(self):
        a, b = self.repo("a"), self.repo("b")
        self.write_world([a, b])
        before = open(self.world_path, "rb").read()
        st = self.city()
        self.assertEqual(st.sweep_gone_floors(1000.0), 0)
        self.assertEqual(open(self.world_path, "rb").read(), before)

    def test_G7_the_sweep_looks_once_a_minute(self):
        a, b = self.repo("a"), self.repo("b")
        self.write_world([a, b])
        st = self.city()
        self.assertEqual(st.sweep_gone_floors(1000.0), 0)
        shutil.rmtree(os.path.dirname(b))
        self.assertEqual(st.sweep_gone_floors(1030.0), 0, "inside the minute: no look")
        self.assertEqual(st.sweep_gone_floors(1061.0), 1)

    def test_G8_a_folder_that_cannot_be_looked_at_is_not_gone(self):
        a, b = self.repo("a"), self.repo("b")
        self.write_world([a, b])
        parent = os.path.join(self.base, "repos")   # the folder's parent cannot be looked into
        self.addCleanup(os.chmod, parent, 0o755)
        os.chmod(parent, 0o000)
        st = self.city()
        self.assertEqual(len(st.floors()), 2, "start keeps it")
        self.assertEqual(st.sweep_gone_floors(1000.0), 0)
        self.assertIn(b, st.world["territories"])
        self.assertFalse(ac.territory_folder_gone(b))

    def test_G9_a_floor_with_a_restored_live_session_keeps_its_place(self):
        k1, k2 = self.repo("k1"), self.repo("k2")
        gone = self.repo("gone", create=False)
        self.write_world([k1, gone, k2], gov_seen={gone: "old-sid"})
        roster = os.path.join(self.base, "roster.json")
        ac.save_roster(roster, [{"sid": "live1", "pid": os.getpid(), "gov": False, "repo": gone, "role": "",
                                 "proj": "app", "wt": "", "tp": "", "label": "", "task": ""}])
        st = self.city(roster_path=roster)
        self.assertEqual(st.world["order"], [k1, gone, k2])
        self.assertEqual(st.world["floors"], [k1, gone, k2])
        self.assertEqual(st.world["gov_seen"].get(gone), "old-sid")

    def test_G10_an_unmounted_disk_is_not_gone(self):
        vols = os.path.join(self.base, "Volumes")
        os.makedirs(vols)
        old = ac.VOLUME_PARENTS
        ac.VOLUME_PARENTS = (vols,)
        self.addCleanup(setattr, ac, "VOLUME_PARENTS", old)
        away = os.path.join(vols, "Disk", "proj", ".git")
        self.assertFalse(ac.territory_folder_gone(away))
        self.assertTrue(ac.territory_folder_gone(os.path.join(self.base, "other", "proj", ".git")))
        a = self.repo("a")
        self.write_world([a, away], gov_seen={away: "sid"})
        st = self.city()
        self.assertEqual(st.sweep_gone_floors(1000.0), 0)
        self.assertEqual(st.world["order"], [a, away])
        self.assertEqual(st.world["gov_seen"], {away: "sid"})
        for yes in ("/Volumes/D", "/media", "/media/u", "/media/u/disk", "/run/media/u/disk", "/mnt/d", "/mnt"):
            ac.VOLUME_PARENTS = old
            self.assertTrue(ac._volume_root(yes), yes)
        for no in ("/home/u", "/Users/x", "/media/u/disk/x/y", "/tmp/x"):
            self.assertFalse(ac._volume_root(no), no)

    def test_G11_the_start_repo_is_never_dropped(self):
        a, b = self.repo("a"), self.repo("b")
        start = self.repo("start", create=False)
        self.write_world([a, start, b])
        st = self.city(start_repo=start)
        self.assertEqual(st.world["order"], [a, start, b])
        self.assertEqual(st.sweep_gone_floors(1000.0), 0)
        self.assertEqual(st.world["floors"], [a, start, b])


if __name__ == "__main__":
    unittest.main()
