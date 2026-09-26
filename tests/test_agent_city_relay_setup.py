"""Failing tests for the relay setup steps (requirements/city.md, "Relay setup").

skills/city/setup.md: the hand steps a team owner follows to run their own
relay (bin/agent-city-relay.js) on their own free Cloudflare account. Config
next to the city command, not a new doc. Reader: someone who has never used
Cloudflare. Plain words, numbered steps, each step says what you should see.
Cloudflare website only where possible; any command exact and ready to paste.

Shape the tests hold it to:

  Exactly these ten "## " headings, in this order:
      ## 1. Make a Cloudflare account
      ## 2. Make the relay
      ## 3. Set the team key
      ## 4. Find the relay address
      ## 5. Hand the address and key to members
      ## 6. Join a local repo
      ## 7. Join a cloud environment
      ## 8. Check it works
      ## 9. Change the key
      ## 10. Remove the relay
  Every section: numbered steps ("1. ", "2. ", ...) and at least one
  "You should see".
  2  names agent-city-relay.js, a D1 database, the binding name DB.
  3  names TEAM_KEY, says it is a secret, and that the key never goes into
     the chat (or to Claude, or to any agent).
  4  names workers.dev.
  6  gives the join command in a code block (agent-city.sh join, or
     agent-city.sh" join when the path is quoted), names .secrets.
  7  names the environment secret AGENT_CITY_RELAY (value: the address, one
     space, the key) and the network setting.
  8  gives agent-city.sh status (path may be quoted) and the line
     "TEAM: joined".
  9  names TEAM_KEY and join (every member joins again with the new key).
  10 names leave.
  The whole file: mentions the free plan; holds no key or key-like value
  (no run of 32+ letters/digits, every "key=" is a <placeholder>).

skills/city/SKILL.md: gains a `setup` branch that walks through
skills/city/setup.md, and says it never asks for the key.

Run: python3 -m unittest tests.test_agent_city_relay_setup
"""

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SETUP = os.path.join(ROOT, "skills", "city", "setup.md")
SKILL = os.path.join(ROOT, "skills", "city", "SKILL.md")

HEADINGS = [
    "## 1. Make a Cloudflare account",
    "## 2. Make the relay",
    "## 3. Set the team key",
    "## 4. Find the relay address",
    "## 5. Hand the address and key to members",
    "## 6. Join a local repo",
    "## 7. Join a cloud environment",
    "## 8. Check it works",
    "## 9. Change the key",
    "## 10. Remove the relay",
]


def read(path):
    with open(path) as fh:
        return fh.read()


class SetupCase(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.isfile(SETUP), "skills/city/setup.md is missing")
        self.text = read(SETUP)

    def sections(self):
        """{heading: body} for every '## ' heading."""
        out, current = {}, None
        for line in self.text.splitlines():
            if line.startswith("## "):
                current = line.strip()
                out[current] = []
            elif current is not None:
                out[current].append(line)
        return {k: "\n".join(v) for k, v in out.items()}

    def section(self, n):
        return self.sections().get(HEADINGS[n - 1], "")


class TestShape(SetupCase):
    def test_the_ten_headings_in_order(self):
        got = [l.strip() for l in self.text.splitlines() if l.startswith("## ")]
        self.assertEqual(got, HEADINGS)

    def test_every_section_has_numbered_steps_and_what_you_see(self):
        for heading in HEADINGS:
            body = self.sections().get(heading, "")
            with self.subTest(heading=heading):
                self.assertRegex(body, r"(?m)^1\. ", "no numbered steps")
                self.assertIn("You should see", body)


class TestContent(SetupCase):
    def assert_names(self, n, *words):
        body = self.section(n)
        for w in words:
            with self.subTest(section=n, word=w):
                self.assertIn(w, body)

    def test_make_the_relay(self):
        self.assert_names(2, "agent-city-relay.js", "D1", "DB")

    def test_team_key(self):
        self.assert_names(3, "TEAM_KEY")
        body = self.section(3).lower()
        self.assertIn("secret", body)
        self.assertIn("never", body)
        self.assertTrue("chat" in body or "claude" in body or "agent" in body)

    def test_address(self):
        self.assert_names(4, "workers.dev")

    def test_join_local(self):
        body = self.section(6)
        blocks = re.findall(r"```[a-z]*\n(.*?)```", body, re.S)
        self.assertTrue(any(re.search(r'agent-city\.sh"? join', b) for b in blocks),
                        "the join command must be in a code block, ready to paste")
        self.assertIn(".secrets", body)

    def test_join_cloud(self):
        self.assert_names(7, "AGENT_CITY_RELAY")
        self.assertIn("network", self.section(7).lower())

    def test_check(self):
        self.assertRegex(self.section(8), r'agent-city\.sh"? status')
        self.assert_names(8, "TEAM: joined")

    def test_change_key(self):
        self.assert_names(9, "TEAM_KEY", "join")

    def test_remove(self):
        self.assert_names(10, "leave")

    def test_free_plan(self):
        self.assertIn("free", self.text.lower())


class TestNoSecrets(SetupCase):
    def test_no_key_like_value(self):
        self.assertIsNone(re.search(r"[A-Za-z0-9]{32,}", self.text),
                          "a key-like value is in the steps")

    def test_key_lines_are_placeholders(self):
        for m in re.finditer(r"key=(\S*)", self.text):
            with self.subTest(found=m.group(0)):
                self.assertTrue(m.group(1).startswith("<"), m.group(0))


class TestSkill(unittest.TestCase):
    def test_setup_branch(self):
        text = read(SKILL)
        self.assertIn("setup.md", text)
        self.assertRegex(text, r"(?i)\bsetup\b")
        self.assertRegex(text, r"(?i)never ask[^\n]*key|key[^\n]*never ask")


if __name__ == "__main__":
    unittest.main()
