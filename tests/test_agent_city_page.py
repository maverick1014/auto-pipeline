"""Failing tests for bin/agent-city.html, the city page the server hands out.

The page grows out of mock/agent-city-mock.html (the approved look). These
tests pin what cannot be seen in a screenshot: that it runs offline, stays
cheap on CPU and memory, and speaks the server's event names. The main
manager drives it in a headless browser for the rest.

CONTRACT

  A full HTML document (<!doctype html>) with <title>Agent City</title>.
  Fully offline: no http:// or https:// URL anywhere (no web fonts, no CDN).
  Live mode: connects with new EventSource('/events').
  Demo mode (the mock's fake agents) when location.hash is '#demo' or the page
  is opened as a file:// URL. Live mode never runs the fake agents.
  Handles these messages: snapshot spawn tool stuck answer done leave gov,
  each as a `case '<type>'` in one switch.
  Knows role 'other' (any agent type outside the pipeline).
  Cheap:
    const FRAME_MS = 33        at most about 30 frames a second
    const IDLE_FRAME_MS = 100  about 10 a second when nothing moves
    const MAX_CITIZENS = 40, MAX_LOG = 40, MAX_PARTICLES = 300, MAX_FLOATERS = 80
    the ground is drawn once into a cached canvas (a name containing
    groundCache) and redrawn only when the view, size or theme changes.
  Its <script> passes `node --check`.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "bin", "agent-city.html")


def page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


def script_text():
    blocks = re.findall(r"<script>(.*?)</script>", page(), re.S)
    return "\n".join(blocks)


class TestDocument(unittest.TestCase):
    def test_it_exists(self):
        self.assertTrue(os.path.exists(PAGE), "bin/agent-city.html is missing")

    def test_full_document_with_title(self):
        text = page()
        self.assertTrue(text.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn("<title>Agent City</title>", text)

    def test_fully_offline(self):
        urls = re.findall(r"https?://[^\s\"')]+", page())
        self.assertEqual(urls, [])

    def test_script_parses(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(script_text())
            path = fh.name
        try:
            result = subprocess.run([node, "--check", path], capture_output=True, text=True)
        finally:
            os.remove(path)
        self.assertEqual(result.returncode, 0, result.stderr)


class TestModes(unittest.TestCase):
    def test_live_mode_uses_the_event_stream(self):
        self.assertRegex(script_text(), r"new EventSource\(\s*['\"]/events['\"]\s*\)")

    def test_demo_mode_is_behind_the_hash_or_a_file_url(self):
        text = script_text()
        self.assertIn("'#demo'", text)
        self.assertIn("'file:'", text)

    def test_every_message_type_is_handled(self):
        text = script_text()
        for kind in ("snapshot", "spawn", "tool", "stuck", "answer", "done", "leave", "gov"):
            with self.subTest(kind=kind):
                self.assertRegex(text, r"case\s+'%s'\s*:" % kind)

    def test_role_other_exists(self):
        self.assertRegex(script_text(), r"['\"]?other['\"]?\s*:\s*\{")


class TestCost(unittest.TestCase):
    def test_frame_caps(self):
        text = script_text()
        self.assertRegex(text, r"const FRAME_MS = 33\b")
        self.assertRegex(text, r"const IDLE_FRAME_MS = 100\b")
        self.assertGreaterEqual(len(re.findall(r"\bFRAME_MS\b", text)), 2)
        self.assertGreaterEqual(len(re.findall(r"\bIDLE_FRAME_MS\b", text)), 2)

    def test_limits(self):
        text = script_text()
        for name, value in (("MAX_CITIZENS", 40), ("MAX_LOG", 40),
                            ("MAX_PARTICLES", 300), ("MAX_FLOATERS", 80)):
            with self.subTest(name=name):
                self.assertRegex(text, r"const %s = %d\b" % (name, value))
                self.assertGreaterEqual(len(re.findall(r"\b%s\b" % name, text)), 2,
                                        "%s is declared but never used" % name)

    def test_ground_is_cached(self):
        self.assertGreaterEqual(len(re.findall(r"groundCache", script_text())), 3)


if __name__ == "__main__":
    unittest.main()
