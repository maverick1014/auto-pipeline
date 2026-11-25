"""The page's assets are versioned by their files (__CITY_ASSET_V__), kept from city-balance when the island went
(city-office, 2026-11-25)."""


import http.client
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from test_agent_city_server import ServerCase, wait_for  # noqa: E402
from test_agent_city_world import gline, make_repo, plans, world_of  # noqa: E402


def kinds_of(**states):
    """{kind: {"state": ...}} with every kind healthy unless named."""
    out = {k: {"state": "healthy", "value": 1, "n": 1, "text": ""} for k in ac.KINDS}
    for k, st in states.items():
        out[k] = dict(out[k], state=st)
    return out


def score(files, rules_text="", reuse=None):
    return ac.score_balance([(p, n) for p, n in files], rules_text, reuse)


# ---------------------------------------------------------------------------
# What kind is a file
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Healthy / low / missing
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# From a real git repo
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Eras and the sign
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# CityState: counted with the lines, era raised, show recorded once
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Server: /api/balance, versioned assets, demo world
# ---------------------------------------------------------------------------

class TestAssetVersion(ServerCase):
    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.base, "cityhome")
        self.world = os.path.join(self.home, "world.json")
        self.assets = os.path.join(self.base, "assets")
        os.makedirs(os.path.join(self.assets, "pets"))
        with open(os.path.join(self.assets, "pets", "a.glb"), "wb") as fh:
            fh.write(b"glTF")

    def test_version_follows_the_files(self):
        v1 = ac.asset_version(self.assets)
        self.assertRegex(v1, r"^[0-9a-f]{8,}$")
        self.assertEqual(ac.asset_version(self.assets), v1)
        with open(os.path.join(self.assets, "pets", "b.glb"), "wb") as fh:
            fh.write(b"x")
        v2 = ac.asset_version(self.assets)
        self.assertNotEqual(v2, v1)
        with open(os.path.join(self.assets, "pets", "a.glb"), "wb") as fh:
            fh.write(b"glTF-2")
        self.assertNotEqual(ac.asset_version(self.assets), v2)

    def test_page_and_cache_headers(self):
        page = os.path.join(self.base, "page.html")
        with open(page, "w") as fh:
            fh.write("<script src=\"assets/pets/a.glb?v=__CITY_ASSET_V__\"></script>")
        self.start("--idle-sec", "60", "--world", self.world, "--assets", self.assets, "--page", page)
        status, headers, body = self.get("/")
        v = ac.asset_version(self.assets)
        self.assertIn(("?v=" + v).encode(), body)
        self.assertNotIn(b"__CITY_ASSET_V__", body)
        status, headers, body = self.get("/assets/pets/a.glb?v=" + v)
        self.assertEqual((status, body), (200, b"glTF"))
        self.assertEqual(headers.get("Cache-Control"), "max-age=31536000, immutable")
        for path in ("/assets/pets/a.glb", "/assets/pets/a.glb?v=old"):
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertEqual(headers.get("Cache-Control"), "no-cache")


if __name__ == "__main__":
    unittest.main()
