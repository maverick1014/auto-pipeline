"""chat-enter: the chat box keys (bin/agent-city.html, sayKeyAction).

Enter sends; Shift/Cmd/Ctrl+Enter is a new line; no send while an input
method is composing (isComposing or keyCode 229); on a coarse pointer
(phone, tablet) Enter is a new line. Empty text never sends: the keydown
handler checks it and the submit handler checks it again.

Run: python3 -m unittest tests.test_agent_city_chat_enter </dev/null
"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_agent_city_people import function_source, page  # noqa: E402


def action(**ev):
    coarse = ev.pop("coarse", False)
    ev.setdefault("key", "Enter")
    js = function_source("sayKeyAction") + "\nconsole.log(JSON.stringify(sayKeyAction(%s, %s)));" % (
        json.dumps(ev), json.dumps(coarse))
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


class TestChatEnter(unittest.TestCase):

    def test_enter_sends_on_a_computer(self):
        self.assertEqual(action(), "send")

    def test_modified_enter_is_a_new_line(self):
        for mod in ("shiftKey", "metaKey", "ctrlKey"):
            self.assertEqual(action(**{mod: True}), "newline", mod)

    def test_composing_never_sends(self):
        self.assertEqual(action(isComposing=True), "")
        self.assertEqual(action(keyCode=229), "")
        self.assertEqual(action(isComposing=True, metaKey=True), "")

    def test_phone_enter_is_a_new_line_only_the_button_sends(self):
        self.assertEqual(action(coarse=True), "")

    def test_other_keys_are_left_alone(self):
        self.assertEqual(action(key="a"), "")

    def test_empty_text_never_sends(self):
        text = page()
        self.assertIn("ta.value.trim()", text)
        self.assertIn("if (!text.trim()) return;", text)

    def test_send_button_is_an_icon_with_a_label(self):
        text = page()
        i = text.index('class="btn say-send"')
        btn = text[i:text.index("</button>", i)]
        self.assertIn("<svg", btn)
        self.assertIn("currentColor", btn)
        self.assertIn("aria-label=", btn)
        self.assertIn("title=", btn)
        self.assertNotIn("</svg>${i18n", btn)


if __name__ == "__main__":
    unittest.main()
