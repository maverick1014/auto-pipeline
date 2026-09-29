"""Tests: tests/nodehelp.py picks a Node with node:sqlite for the relay tests.

CONTRACT (ideas-soon S2)
  find_node(path, places): the first "node" that loads node:sqlite, first
    every PATH folder in order, then PLACES in order; an old node (no
    node:sqlite) is passed over; none -> None.
  default_places(): /opt/homebrew/bin, /usr/local/bin, then nvm versions
    newest first, then ~/.volta/bin, /usr/bin.
  SKIP_REASON: one clear reason, names Node 22.5+.
  Every tests/test_agent_city_relay_*.py that runs node takes it from
  nodehelp (never a bare shutil.which("node") or "node"), and skips with
  SKIP_REASON when there is none.

Run: python3 -m unittest tests.test_nodehelp </dev/null
"""

import glob
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import nodehelp  # noqa: E402

OLD = "#!/bin/sh\ncase \"$1\" in --version) echo v20.19.6; exit 0;; esac\nexit 1\n"
NEW = "#!/bin/sh\n[ \"$1\" = -e ] && [ \"$2\" = \"require('node:sqlite')\" ] && exit 0\nexit 1\n"


class TestFindNode(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="nodehelp_")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def fake(self, folder, body):
        d = os.path.join(self.base, folder)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "node")
        with open(p, "w") as fh:
            fh.write(body)
        os.chmod(p, 0o755)
        return d, p

    def test_old_node_first_on_path_is_passed_over_for_a_new_one_in_a_place(self):
        old_dir, _ = self.fake("old", OLD)
        _, new = self.fake("brew", NEW)
        self.assertEqual(nodehelp.find_node(path=old_dir, places=[new]), new)

    def test_path_comes_before_places_and_keeps_its_order(self):
        old_dir, _ = self.fake("old", OLD)
        a_dir, a = self.fake("a", NEW)
        b_dir, _ = self.fake("b", NEW)
        _, place = self.fake("place", NEW)
        path = os.pathsep.join([old_dir, a_dir, b_dir])
        self.assertEqual(nodehelp.find_node(path=path, places=[place]), a)

    def test_none_found(self):
        old_dir, old = self.fake("old", OLD)
        missing = os.path.join(self.base, "nope", "node")
        self.assertIsNone(nodehelp.find_node(path=old_dir, places=[old, missing]))
        self.assertIsNone(nodehelp.find_node(path="", places=[]))

    def test_a_file_that_cannot_run_is_skipped(self):
        d, p = self.fake("plain", NEW)
        os.chmod(p, 0o644)
        self.assertIsNone(nodehelp.find_node(path=d, places=[]))

    def test_default_places_nvm_newest_first(self):
        home = os.path.join(self.base, "home")
        for v in ("v20.19.6", "v24.1.0", "v22.5.1", "v9.11.2"):
            self.fake(os.path.join("home", ".nvm", "versions", "node", v, "bin"), NEW)
        with mock.patch.dict(os.environ, {"HOME": home}):
            places = nodehelp.default_places()
        nvm = [p for p in places if "/.nvm/" in p]
        self.assertEqual([p.split(os.sep)[-3] for p in nvm], ["v24.1.0", "v22.5.1", "v20.19.6", "v9.11.2"])
        self.assertEqual(places[:2], ["/opt/homebrew/bin/node", "/usr/local/bin/node"])
        self.assertEqual(places[-1], "/usr/bin/node")
        self.assertIn(os.path.join(home, ".volta", "bin", "node"), places)

    def test_skip_reason_is_one_clear_line(self):
        self.assertIn("Node 22.5+", nodehelp.SKIP_REASON)
        self.assertNotIn("\n", nodehelp.SKIP_REASON)


class TestRelayModulesUseIt(unittest.TestCase):
    def test_no_bare_node_in_relay_tests(self):
        mods = sorted(glob.glob(os.path.join(HERE, "test_agent_city_relay_*.py")))
        self.assertTrue(mods)
        users = []
        for m in mods:
            with open(m, encoding="utf-8") as fh:
                src = fh.read()
            self.assertNotIn('shutil.which("node")', src, os.path.basename(m))
            self.assertNotIn('["node", ', src, os.path.basename(m))
            if "node" in src.lower() and ("HARNESS" in src or "relay-dev.mjs" in src):
                users.append(os.path.basename(m))
                self.assertIn("nodehelp", src, os.path.basename(m))
                self.assertIn("SKIP_REASON", src, os.path.basename(m))
        self.assertGreaterEqual(len(users), 3, users)


if __name__ == "__main__":
    unittest.main()
