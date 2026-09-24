"""Failing tests for bin/agent-city.html and bin/agent-city-assets/.

The page is the approved 3D mock (mock/agent-city-3d-mock.html) turned into
the real thing: it reads live agent events from the city server. Every 3D
model is a ready-made CC0 Kenney model; nothing is modelled by hand. These
tests pin what a screenshot cannot show: it runs offline, stays cheap, and
speaks the server's event names. The main manager drives it in a headless
browser for the rest.

CONTRACT

  bin/agent-city.html
    A full HTML document (<!doctype html>) with <title>Agent City</title>.
    Fully offline: no http:// or https:// URL anywhere (no web fonts, no CDN).
    Loads three.js and its loaders from the server, in this order:
      <script src="assets/vendor/three.min.js">
      <script src="assets/vendor/GLTFLoader.js">
      <script src="assets/vendor/SkeletonUtils.js">
    const ASSET = 'assets/' and a const MODELS = [...] list of '<pack>/<name>'
    entries; each is loaded from ASSET + entry + '.glb'.
    Live mode: new EventSource('/events').
    Demo mode (the mock's fake agents) when location.hash is '#demo' or the page
    is opened as a file:// URL. Live mode never runs the fake agents.
    Handles snapshot spawn tool stuck answer done leave gov, each as a
    `case '<type>'` in one switch. Knows role 'other'.
    Cheap:
      const FRAME_MS = 33        at most about 30 frames a second
      const IDLE_FRAME_MS = 100  about 10 a second when nothing moves
      const MAX_CITIZENS = 40, MAX_LOG = 40, MAX_FLOATERS = 80, each used
      static scenery drawn with THREE.InstancedMesh
    Its <script> passes `node --check`.

  bin/agent-city-assets/
    vendor/three.min.js, vendor/GLTFLoader.js, vendor/SkeletonUtils.js
      (three.js r128, MIT, the licence header kept)
    <pack>/<name>.glb for every MODELS entry, and nothing unused
    <pack>/Textures/*.png for every texture those models name
    <pack>/License.txt for every pack, each saying CC0
    Everything together at most 6 MB.
"""

import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "bin", "agent-city.html")
ASSETS = os.path.join(ROOT, "bin", "agent-city-assets")


def page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


def inline_script():
    return "\n".join(re.findall(r"<script>(.*?)</script>", page(), re.S))


def models():
    block = re.search(r"const MODELS = \[(.*?)\];", inline_script(), re.S)
    return re.findall(r"'([a-z]+/[A-Za-z0-9_\-]+)'", block.group(1)) if block else []


def glb_images(path):
    with open(path, "rb") as fh:
        data = fh.read()
    length = struct.unpack("<I", data[12:16])[0]
    doc = json.loads(data[20:20 + length])
    return [img["uri"] for img in doc.get("images", []) if "uri" in img]


class TestDocument(unittest.TestCase):
    def test_it_exists(self):
        self.assertTrue(os.path.exists(PAGE), "bin/agent-city.html is missing")

    def test_full_document_with_title(self):
        text = page()
        self.assertTrue(text.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn("<title>Agent City</title>", text)

    def test_fully_offline(self):
        self.assertEqual(re.findall(r"https?://[^\s\"')<]+", page()), [])

    def test_vendor_scripts_in_order(self):
        srcs = re.findall(r'<script src="([^"]+)"', page())
        self.assertEqual(srcs, ["assets/vendor/three.min.js", "assets/vendor/GLTFLoader.js",
                                "assets/vendor/SkeletonUtils.js"])

    def test_script_parses(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(inline_script())
            path = fh.name
        try:
            result = subprocess.run([node, "--check", path], capture_output=True, text=True)
        finally:
            os.remove(path)
        self.assertEqual(result.returncode, 0, result.stderr)


class TestModes(unittest.TestCase):
    def test_live_mode_uses_the_event_stream(self):
        self.assertRegex(inline_script(), r"new EventSource\(\s*['\"]/events['\"]\s*\)")

    def test_demo_mode_is_behind_the_hash_or_a_file_url(self):
        text = inline_script()
        self.assertIn("'#demo'", text)
        self.assertIn("'file:'", text)

    def test_every_message_type_is_handled(self):
        text = inline_script()
        for kind in ("snapshot", "spawn", "tool", "stuck", "answer", "done", "leave", "gov"):
            with self.subTest(kind=kind):
                self.assertRegex(text, r"case\s+'%s'\s*:" % kind)

    def test_role_other_exists(self):
        self.assertRegex(inline_script(), r"['\"]?other['\"]?\s*:\s*\{")

    def test_assets_come_from_the_server(self):
        self.assertIn("const ASSET = 'assets/'", inline_script())
        self.assertGreater(len(models()), 20)


class TestCost(unittest.TestCase):
    def test_frame_caps(self):
        text = inline_script()
        self.assertRegex(text, r"const FRAME_MS = 33\b")
        self.assertRegex(text, r"const IDLE_FRAME_MS = 100\b")
        self.assertGreaterEqual(len(re.findall(r"\bFRAME_MS\b", text)), 2)
        self.assertGreaterEqual(len(re.findall(r"\bIDLE_FRAME_MS\b", text)), 2)

    def test_limits(self):
        text = inline_script()
        for name, value in (("MAX_CITIZENS", 40), ("MAX_LOG", 40), ("MAX_FLOATERS", 80)):
            with self.subTest(name=name):
                self.assertRegex(text, r"const %s = %d\b" % (name, value))
                self.assertGreaterEqual(len(re.findall(r"\b%s\b" % name, text)), 2,
                                        "%s is declared but never used" % name)

    def test_static_scenery_is_instanced(self):
        self.assertIn("new THREE.InstancedMesh", inline_script())


class TestAssets(unittest.TestCase):
    def test_vendor_scripts_are_three_r128_with_licence(self):
        for name in ("three.min.js", "GLTFLoader.js", "SkeletonUtils.js"):
            with self.subTest(name=name):
                path = os.path.join(ASSETS, "vendor", name)
                self.assertTrue(os.path.exists(path), path)
        with open(os.path.join(ASSETS, "vendor", "three.min.js"), encoding="utf-8") as fh:
            head = fh.read(400)
        self.assertIn("SPDX-License-Identifier: MIT", head)

    def test_every_model_is_there(self):
        for entry in models():
            with self.subTest(entry=entry):
                self.assertTrue(os.path.exists(os.path.join(ASSETS, entry + ".glb")))

    def test_no_unused_model(self):
        wanted = {e + ".glb" for e in models()}
        found = set()
        for folder, _, files in os.walk(ASSETS):
            for name in files:
                if name.endswith(".glb"):
                    found.add(os.path.relpath(os.path.join(folder, name), ASSETS))
        self.assertEqual(found - wanted, set())

    def test_every_texture_a_model_names_is_there(self):
        for entry in models():
            path = os.path.join(ASSETS, entry + ".glb")
            if not os.path.exists(path):
                continue
            for uri in glb_images(path):
                with self.subTest(entry=entry, uri=uri):
                    self.assertTrue(os.path.exists(os.path.join(os.path.dirname(path), uri)))

    def test_every_pack_has_its_cc0_licence(self):
        packs = {e.split("/")[0] for e in models()}
        self.assertTrue(packs)
        for pack in packs:
            with self.subTest(pack=pack):
                path = os.path.join(ASSETS, pack, "License.txt")
                self.assertTrue(os.path.exists(path), path)
                with open(path, encoding="utf-8", errors="replace") as fh:
                    self.assertIn("CC0", fh.read())

    def test_size_budget(self):
        total = sum(os.path.getsize(os.path.join(folder, name))
                    for folder, _, files in os.walk(ASSETS) for name in files)
        self.assertLessEqual(total, 6 * 1024 * 1024, "assets are %.1f MB" % (total / 1048576))


if __name__ == "__main__":
    unittest.main()
