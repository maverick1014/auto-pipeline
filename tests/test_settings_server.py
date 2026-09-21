"""Failing tests for settings_server.py. Written by the task manager, before any code.

CONTRACT the worker must implement in settings_server.py (module at repo root):

    HOST          -> "127.0.0.1"
    PORT          -> 8790
    DEFAULT_CONF  -> absolute path of agent.conf next to this module
    DEFAULT_HTML  -> absolute path of settings.html next to this module
    make_server(port=PORT, conf_path=DEFAULT_CONF, html_path=DEFAULT_HTML, quiet=False)
                  -> an http.server.HTTPServer, not yet serving.
                     port 0 means "pick a free port"; read it from srv.server_address[1].
                     quiet=True turns off the per-request stderr log line.
    main()        -> make_server() and serve forever, so `python3 settings_server.py`
                     serves http://127.0.0.1:8790/

Routes:
    GET  /       -> 200 text/html. The filled-in settings.html.
    POST /save   -> 200 text/html. All values good: write agent.conf, show the Saved
                    banner. Any value bad: agent.conf is NOT touched, and every bad
                    field shows its error inside its own row.
    anything else-> 404.

settings.html is a template. The server replaces these exact comment markers:
    <!--SAVED-->          the banner, or "" when there is nothing to say
    <!--ROWS:limits-->    the rows of that group
    <!--ROWS:roles-->
    <!--ROWS:permission-->
    <!--ROWS:other-->     unknown keys. "" when there are none. The server also
                          writes this group's own <h2> heading, so nothing shows
                          when agent.conf has no unknown keys.

Row markup the server writes (class names are the contract with settings.html):

    <div class="row">                     good, or  <div class="row bad">  when bad
      <label for="KEY">KEY</label>
      <div class="field">
        <input id="KEY" name="KEY" value="VALUE">
        <div class="err">MESSAGE</div>    only when that value is bad
      </div>
      <div class="hint">HINT</div>
    </div>

Saved banner markup:  <div class="saved">Saved</div>

Rules:
  - Values are HTML-escaped. A value with " or < must not break the page.
  - A POST field whose key is not already in agent.conf is ignored. No new keys.
  - A key missing from the POST keeps its current value.
"""

import os
import sys
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import agent_conf
import settings_server


CONF_TEXT = (
    "max_usage_percent=80\n"
    "heavy_test_slots=1\n"
    "max_agents=4\n"
    "main_manager=fable-5.1:xhigh\n"
    "fast_lane_deputy=sonnet-5:medium\n"
    "merge_deputy=sonnet-5:medium\n"
    "task_manager=opus-5:xhigh\n"
    "worker=sonnet-5:medium\n"
    "file_clerk=haiku-4.5:low\n"
    "permission_mode=auto\n"
)

GOOD_FORM = {
    "max_usage_percent": "80",
    "heavy_test_slots": "1",
    "max_agents": "4",
    "main_manager": "fable-5.1:xhigh",
    "fast_lane_deputy": "sonnet-5:medium",
    "merge_deputy": "sonnet-5:medium",
    "task_manager": "opus-5:xhigh",
    "worker": "sonnet-5:medium",
    "file_clerk": "haiku-4.5:low",
    "permission_mode": "auto",
}


def row_for(page, key):
    """Return the one <div class="row"> block that holds this key's input."""
    parts = page.split('<div class="row')
    for part in parts[1:]:
        if 'name="%s"' % key in part:
            return part
    return ""


class ServerCase(unittest.TestCase):
    """Runs a real settings_server on a free port, against a throwaway agent.conf."""

    conf_text = CONF_TEXT

    def setUp(self):
        self.tmpdir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "_tmp_%d" % id(self)
        )
        os.makedirs(self.tmpdir, exist_ok=True)
        self.conf_path = os.path.join(self.tmpdir, "agent.conf")
        with open(self.conf_path, "w") as fh:
            fh.write(self.conf_text)

        self.server = settings_server.make_server(
            port=0,
            conf_path=self.conf_path,
            html_path=os.path.join(ROOT, "settings.html"),
            quiet=True,
        )
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        if os.path.exists(self.conf_path):
            os.unlink(self.conf_path)
        if os.path.isdir(self.tmpdir):
            os.rmdir(self.tmpdir)

    def url(self, path="/"):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def get(self, path="/"):
        with urllib.request.urlopen(self.url(path), timeout=10) as res:
            return res.status, res.headers.get("Content-Type", ""), res.read().decode("utf-8")

    def post(self, fields, path="/save"):
        body = urllib.parse.urlencode(fields).encode("utf-8")
        request = urllib.request.Request(
            self.url(path),
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(request, timeout=10) as res:
            return res.status, res.headers.get("Content-Type", ""), res.read().decode("utf-8")

    def conf_on_disk(self):
        with open(self.conf_path) as fh:
            return fh.read()


class TestGetPage(ServerCase):
    def test_returns_200_html(self):
        status, ctype, page = self.get("/")
        self.assertEqual(status, 200)
        self.assertTrue(ctype.startswith("text/html"), ctype)
        self.assertIn("<form", page)

    def test_shows_every_key_with_its_current_value(self):
        _, _, page = self.get("/")
        for key, value in agent_conf.load(self.conf_path).items():
            with self.subTest(key=key):
                block = row_for(page, key)
                self.assertTrue(block, "no row for %s" % key)
                self.assertIn('name="%s"' % key, block)
                self.assertIn('value="%s"' % value, block)
                self.assertIn(key, block)

    def test_shows_one_hint_per_key(self):
        _, _, page = self.get("/")
        for key in agent_conf.load(self.conf_path):
            with self.subTest(key=key):
                block = row_for(page, key)
                self.assertIn('class="hint"', block)
                self.assertIn(agent_conf.hint_for(key), block)

    def test_renders_each_key_exactly_once(self):
        _, _, page = self.get("/")
        for key in agent_conf.load(self.conf_path):
            with self.subTest(key=key):
                self.assertEqual(page.count('name="%s"' % key), 1)

    def test_has_the_save_form(self):
        _, _, page = self.get("/")
        self.assertIn('action="/save"', page)
        self.assertIn('method="post"', page.lower())
        self.assertIn("Save", page)

    def test_leaves_no_template_marker_behind(self):
        _, _, page = self.get("/")
        self.assertNotIn("<!--ROWS:", page)
        self.assertNotIn("<!--SAVED-->", page)

    def test_is_clean_before_any_save(self):
        _, _, page = self.get("/")
        self.assertNotIn('class="saved"', page)
        self.assertNotIn('class="err"', page)
        self.assertNotIn("row bad", page)

    def test_unknown_path_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/nope")
        self.assertEqual(caught.exception.code, 404)


class TestGetWithUnknownKeys(ServerCase):
    conf_text = CONF_TEXT + "some_new_key=hello\n"

    def test_unknown_key_gets_a_row_too(self):
        _, _, page = self.get("/")
        block = row_for(page, "some_new_key")
        self.assertTrue(block, "no row for the unknown key")
        self.assertIn('value="hello"', block)
        self.assertIn('class="hint"', block)

    def test_unknown_key_row_is_not_marked_bad(self):
        _, _, page = self.get("/")
        self.assertNotIn("row bad", page)


class TestGetEscaping(ServerCase):
    conf_text = 'max_agents=4\nnote=a"b<c>d&e\n'

    def test_value_is_html_escaped(self):
        _, _, page = self.get("/")
        self.assertNotIn('a"b<c>d&e', page)
        self.assertIn("&lt;", page)
        self.assertIn("&amp;", page)
        block = row_for(page, "note")
        self.assertTrue(block)
        self.assertNotIn("<c>", block)


class TestSaveGood(ServerCase):
    def test_writes_the_new_values_and_says_saved(self):
        fields = dict(GOOD_FORM)
        fields["max_agents"] = "9"
        fields["worker"] = "opus-5:high"
        status, ctype, page = self.post(fields)

        self.assertEqual(status, 200)
        self.assertTrue(ctype.startswith("text/html"), ctype)
        self.assertIn('class="saved"', page)
        self.assertIn("Saved", page)
        self.assertNotIn('class="err"', page)

        conf = agent_conf.load(self.conf_path)
        self.assertEqual(conf["max_agents"], "9")
        self.assertEqual(conf["worker"], "opus-5:high")

    def test_saved_page_shows_the_new_values(self):
        fields = dict(GOOD_FORM)
        fields["max_agents"] = "9"
        _, _, page = self.post(fields)
        self.assertIn('value="9"', row_for(page, "max_agents"))

    def test_keeps_key_order(self):
        fields = dict(GOOD_FORM)
        fields["max_agents"] = "9"
        self.post(fields)
        self.assertEqual(list(agent_conf.load(self.conf_path).keys()), list(GOOD_FORM.keys()))

    def test_a_field_not_in_the_form_keeps_its_value(self):
        fields = dict(GOOD_FORM)
        del fields["permission_mode"]
        fields["max_agents"] = "9"
        self.post(fields)
        conf = agent_conf.load(self.conf_path)
        self.assertEqual(conf["permission_mode"], "auto")
        self.assertEqual(conf["max_agents"], "9")

    def test_a_stray_field_does_not_become_a_new_key(self):
        fields = dict(GOOD_FORM)
        fields["not_a_real_key"] = "junk"
        self.post(fields)
        self.assertNotIn("not_a_real_key", agent_conf.load(self.conf_path))

    def test_save_to_unknown_path_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post(GOOD_FORM, path="/nope")
        self.assertEqual(caught.exception.code, 404)


class TestSaveWithUnknownKeys(ServerCase):
    conf_text = CONF_TEXT + "some_new_key=hello\n"

    def test_unknown_key_survives_a_save(self):
        fields = dict(GOOD_FORM)
        fields["some_new_key"] = "changed"
        fields["max_agents"] = "9"
        self.post(fields)
        conf = agent_conf.load(self.conf_path)
        self.assertEqual(list(conf.keys()), list(GOOD_FORM.keys()) + ["some_new_key"])
        self.assertEqual(conf["some_new_key"], "changed")


class TestSaveBad(ServerCase):
    def test_bad_value_does_not_touch_the_file(self):
        before = self.conf_on_disk()
        fields = dict(GOOD_FORM)
        fields["max_agents"] = "99"
        self.post(fields)
        self.assertEqual(self.conf_on_disk(), before)

    def test_bad_value_shows_the_error_in_its_own_row(self):
        fields = dict(GOOD_FORM)
        fields["max_agents"] = "99"
        _, _, page = self.post(fields)

        block = row_for(page, "max_agents")
        self.assertTrue(block)
        self.assertIn("bad", block.split(">")[0])
        self.assertIn('class="err"', block)
        self.assertIn(agent_conf.validate_value("max_agents", "99"), block)

    def test_good_rows_stay_clean(self):
        fields = dict(GOOD_FORM)
        fields["max_agents"] = "99"
        _, _, page = self.post(fields)
        self.assertEqual(page.count('class="err"'), 1)
        self.assertNotIn('class="err"', row_for(page, "worker"))

    def test_no_saved_banner_when_something_is_bad(self):
        fields = dict(GOOD_FORM)
        fields["max_agents"] = "99"
        _, _, page = self.post(fields)
        self.assertNotIn('class="saved"', page)

    def test_the_typed_value_is_shown_back(self):
        fields = dict(GOOD_FORM)
        fields["max_agents"] = "99"
        _, _, page = self.post(fields)
        self.assertIn('value="99"', row_for(page, "max_agents"))

    def test_every_bad_field_gets_its_own_error(self):
        fields = dict(GOOD_FORM)
        fields["max_agents"] = "99"
        fields["permission_mode"] = "yolo"
        fields["worker"] = "sonnet-5:ultra"
        _, _, page = self.post(fields)

        self.assertEqual(page.count('class="err"'), 3)
        for key in ("max_agents", "permission_mode", "worker"):
            with self.subTest(key=key):
                self.assertIn('class="err"', row_for(page, key))
        self.assertEqual(self.conf_on_disk(), CONF_TEXT)

    def test_good_edits_are_lost_when_another_field_is_bad(self):
        fields = dict(GOOD_FORM)
        fields["heavy_test_slots"] = "5"
        fields["max_agents"] = "99"
        self.post(fields)
        self.assertEqual(agent_conf.load(self.conf_path)["heavy_test_slots"], "1")


class TestDefaults(unittest.TestCase):
    def test_serves_on_the_briefed_host_and_port(self):
        self.assertEqual(settings_server.HOST, "127.0.0.1")
        self.assertEqual(settings_server.PORT, 8790)

    def test_default_paths_point_next_to_the_module(self):
        self.assertEqual(settings_server.DEFAULT_CONF, os.path.join(ROOT, "agent.conf"))
        self.assertEqual(settings_server.DEFAULT_HTML, os.path.join(ROOT, "settings.html"))


if __name__ == "__main__":
    unittest.main()
