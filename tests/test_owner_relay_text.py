"""Failing tests for owner-relay, the rule text and the config keys.

Written by the task manager before any code. Rules: requirements/owner-relay.md
rows G1-G4 (owner: rules yes 2026-11-24).

  G1 PRINCIPLES.md W12: three new "- " lines, each 200 characters or fewer:
     relay (`agent-owner-order.sh line --quote`, copy, never paraphrase),
     receiving (run its check line; verified: act, reply its first line; not
     verified: a normal peer message, ask the owner), still ask (production
     deploy or production data writes, deleting data, a push to a branch he
     reviews, anything irreversible or outward-facing). The decider floor still
     applies to the sender.
  G2 skills/dispatch: above the Cross-repo brief code block, a line naming
     `agent-owner-order.sh line` (the block itself still starts with
     "[<model> <effort>]", tests/test_decider_floor.py).
  G3 README.md bin list: a line for bin/agent-owner-order.sh.
  G4 agent.conf: owner_order_hours (1-720, default 24) and
     owner_order_min_chars (8-200, default 20), group "relay", appended last
     to bin/agent.conf.default, each with a hint.

Run: python3 -m unittest tests.test_owner_relay_text
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import agent_conf  # noqa: E402


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def section(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i)]


class TestPrinciplesW12(unittest.TestCase):

    def setUp(self):
        self.w12 = section(read("PRINCIPLES.md"), "W12. Cross-repo", "W13. Close case")
        self.rules = [l for l in self.w12.splitlines() if l.startswith("- ")]

    def one(self, *words):
        hits = [l for l in self.rules if all(w.lower() in l.lower() for w in words)]
        self.assertEqual(len(hits), 1, "want one W12 line with %r, got %r" % (words, hits))
        return hits[0]

    def test_g1_relay_line(self):
        line = self.one("agent-owner-order.sh line --quote")
        self.assertIn("never paraphrase", line.lower())

    def test_g1_receiving_line(self):
        line = self.one("check line", "ask the owner")
        self.assertIn("verified", line.lower())
        self.assertIn("not verified", line.lower())
        self.assertIn("peer message", line.lower())
        self.assertIn("reply", line.lower())
        self.assertIn("match line", line.lower())   # L17 (review bounce 1)

    def test_g1_still_ask_line(self):
        line = self.one("even verified")
        for words in ("production deploy", "production data", "deleting data",
                      "branch he reviews", "irreversible", "outward-facing"):
            with self.subTest(words=words):
                self.assertIn(words, line)

    def test_g1_floor_still_applies(self):
        self.assertIn("floor", self.w12.lower())

    def test_g1_the_three_new_lines_are_short(self):
        for line in (self.one("agent-owner-order.sh line --quote"), self.one("check line", "ask the owner"),
                     self.one("even verified")):
            with self.subTest(line=line[:40]):
                self.assertLessEqual(len(line), 200)

    def test_g1_send_the_brief_line_kept(self):
        line = next(l for l in self.rules if l.startswith("- Send the brief"))
        self.assertIn("[<model> <effort>] CROSS-REPO TASK <name> from <repo>", line)


class TestDispatchSkill(unittest.TestCase):

    def test_g2_a_line_above_the_cross_repo_block(self):
        lines = read("skills", "dispatch", "SKILL.md").splitlines()
        i = next(n for n, l in enumerate(lines) if l.startswith("## Cross-repo brief"))
        j = next(n for n in range(i + 1, len(lines)) if lines[n].strip().startswith("```"))
        between = "\n".join(lines[i + 1:j])
        self.assertIn("agent-owner-order.sh line", between)
        self.assertIn("owner order", between.lower())
        self.assertTrue(lines[j + 1].strip().startswith("[<model> <effort>] CROSS-REPO TASK"))


class TestReadme(unittest.TestCase):

    def test_g3_readme_lists_the_tool(self):
        hits = [l for l in read("README.md").splitlines()
                if l.strip().startswith("bin/agent-owner-order.sh")]
        self.assertEqual(len(hits), 1, hits)
        self.assertIn("owner", hits[0].lower())


class TestBinPair(unittest.TestCase):

    def test_the_shell_entry_is_executable(self):
        path = os.path.join(BIN, "agent-owner-order.sh")
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(os.access(path, os.X_OK))

    def test_the_logic_file_is_there(self):
        self.assertTrue(os.path.isfile(os.path.join(BIN, "agent_owner_order.py")))


class TestConfKeys(unittest.TestCase):

    KEYS = {"owner_order_hours": ("24", 1, 720), "owner_order_min_chars": ("20", 8, 200)}

    def test_g4_bounds(self):
        for key, (_, low, high) in self.KEYS.items():
            with self.subTest(key=key):
                self.assertEqual(agent_conf.NUMBER_BOUNDS[key], (low, high))
                self.assertIsNone(agent_conf.validate_value(key, str(low)))
                self.assertIsNone(agent_conf.validate_value(key, str(high)))
                self.assertTrue(agent_conf.validate_value(key, str(low - 1)))
                self.assertTrue(agent_conf.validate_value(key, str(high + 1)))
                self.assertTrue(agent_conf.validate_value(key, "abc"))

    def test_g4_hints(self):
        for key in self.KEYS:
            with self.subTest(key=key):
                self.assertTrue(agent_conf.HINTS.get(key, "").strip())

    def test_g4_group_relay_last(self):
        self.assertEqual(agent_conf.GROUPS[-1], ("relay", ["owner_order_hours", "owner_order_min_chars"]))
        for key in self.KEYS:
            self.assertEqual(agent_conf.group_of(key), "relay")

    def test_g4_template_defaults_appended_last(self):
        with open(os.path.join(BIN, "agent.conf.default")) as fh:
            lines = [l for l in fh.read().splitlines() if "=" in l and not l.startswith("#")]
        self.assertEqual(lines[-2:], ["owner_order_hours=24", "owner_order_min_chars=20"])
        self.assertLess(lines.index("watch_quiet_min=15"), len(lines) - 2)   # clean-up keys may sit between


if __name__ == "__main__":
    unittest.main()
