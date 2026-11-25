"""Failing tests for city-office, slice 2: the island leaves the server (requirements/city.md: "The build removed
those sections"; Look, Arrange, Worktrees, Growth, Balance, Quality are gone, People keeps what still holds).

CONTRACT (bin/agent_city.py)
  Gone: the town plans (bin/agent-city-plans.json and load_plans), land growth (count_lines, growth, radius,
    territory_tiles, open_plots), buildings and their names, quality (requality and the per-file quality),
    balance and eras (balance_of, the era show), worktree sites (scan_sites, read_sites), the island layout
    (layout, GAPS, SLOTS, set_layout) and the routes /api/layout and /api/balance (both answer 404 now).
    CityState keeps no recount/requality/scan_sites/set_layout/balance_api.
  world.json: {"v": 1, "territories": {identity: {"name", "reno_asked"?}}, "order", "floors", "names",
    "gov_seen"}: nothing else is written. An island world.json (plans, slots, buildings, eras, offices, sites,
    hidden flags) still loads: it is never moved aside for its island keys, its territories and names stay,
    its floors come from its order without the hidden ones (O1), and the next save drops the island keys.
  demo_world() / `agent_city.py demo-world`: the demo building as an office view (O4 shape: v 2, repos,
    floors, designs, asked): at least 3 floors, at least one floor with a design check_design accepts and
    one without. The page's DEMO_WORLD is the same JSON (tests/test_agent_city_office_page.py TestDemo).
  CityState no longer takes plans=, count_fn= or balance_fn= (a test passing them gets a TypeError).
"""

import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
SERVER = os.path.join(BIN, "agent_city.py")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from cityhelp import Mains  # noqa: E402


def line(ev, sid, repo):
    return {"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "Read", "nt": "", "proj": "shop", "role": "",
            "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}


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
        st.feed_line(line("UserPromptSubmit", "a", self.shop), 1.0)
        st.feed_line(line("UserPromptSubmit", "b", self.blog), 1.0)
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


class TestRoutesAreGone(Case):
    def test_layout_and_balance_404(self):
        st = self.make(token="tok")
        server = ThreadingHTTPServer(("127.0.0.1", 0), ac.CityHandler)
        server.daemon_threads = True
        server.city, server.hub, server.page_bytes, server.assets_dir = st, None, b"", self.base
        port = server.server_address[1]
        server.host_set = {"127.0.0.1:%d" % port}
        server.origin_set = {"http://127.0.0.1:%d" % port}
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            for method, path in (("POST", "/api/layout"), ("GET", "/api/balance?terr=x&kind=build")):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                conn.request(method, path, body=b"{}" if method == "POST" else None,
                             headers={"X-City-Token": "tok", "Origin": "http://127.0.0.1:%d" % port,
                                      "Content-Type": "application/json"})
                resp = conn.getresponse()
                resp.read()
                conn.close()
                self.assertEqual(resp.status, 404, path)
        finally:
            server.shutdown()
            server.server_close()
            t.join(5)


class TestDemoWorld(unittest.TestCase):
    def test_demo_is_an_office(self):
        w = ac.demo_world()
        self.assertEqual(set(w), {"v", "repos", "floors", "designs", "asked"})
        self.assertEqual(w["v"], 2)
        self.assertGreaterEqual(len(w["floors"]), 3)
        ids = {r["id"] for r in w["repos"]}
        self.assertTrue(set(w["floors"]) <= ids)
        self.assertTrue(w["designs"])
        for d in w["designs"].values():
            self.assertEqual(ac.check_design(d), [])
        self.assertTrue([f for f in w["floors"] if f not in w["designs"]], "one floor shows the base look")

    def test_cli_prints_it(self):
        r = subprocess.run([sys.executable, SERVER, "demo-world"], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), ac.demo_world())


if __name__ == "__main__":
    unittest.main()
