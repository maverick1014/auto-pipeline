"""Failing tests: the rule text of daily-rules (F1-F3, F5, F6, F8). Written by
the task manager first.

CONTRACT, PRINCIPLES.md:

  "## E. Output" is a new section after "## D. Auto setup", in the terse
  PRINCIPLES style (a rule code and title, then one short line per rule).
  The hook prints it whole in every session (tests/test_output_hook.py), so it
  is at most 3000 bytes: from its heading up to the next "## " heading,
  blank lines at its end dropped.

  F1  the i-have-adhd ruleset (https://github.com/ayghri/i-have-adhd v0.4.1,
      MIT, (c) Ayoub Ghriss) rewritten: lead with the next action, numbered
      steps, one next action at the end, no tangents, restate state
      (Step <n> of <m>), concrete time estimates, show what now works, matter-
      of-fact errors (no "Uh oh"), lists of 5 items, no preamble / recap /
      closer, the overrides (explain, destructive, still broken, ambiguous, a
      rule that fights the task or the harness), the pre-send check (first
      line, last line, hedges, idioms), on for the rest of the session.
      A credit line inside the section names the source, version, author, MIT.
  F2  owner overrides: never fail silently (blocked, ambiguous, refused,
      broken: said at once, never a tangent, never a trimmed hedge, never
      behind a partial success); tables and ledgers are not lists; "verified"
      only with real evidence named (a green suite is not a real-device
      check); the decide section (H3) is never deleted. Language: H2.
  F3  concise: lead with the result, cut narration, short by default, state
      plainly, full detail on request, never trade correctness for brevity.
  F4  adhd=off in agent.conf turns it off; "stop adhd mode" or "normal mode"
      turns it off for the session.

  The MIT notice (the copyright line and the whole permission notice, same
  words as the LICENSE, any line wrapping) sits in PRINCIPLES.md outside
  section E, after it, so the hook never prints it.

  Generic: no owner name and no machine name in PRINCIPLES.md.

  F5  the manager laws, only what was missing (phrases below).
  F6  the time and command lessons (phrases below).

CONTRACT, F8: README.md and `agent-city.sh -h` show the short command
`agent-city <cmd>` (the ~/.local/bin shim), never `./agent-city.sh <cmd>` or
`./bin/agent-city.sh <cmd>`. Nothing installs the shim by itself (only the init
skill, on a yes), so both say once: run `agent-city.sh install-shim` one time.
README keeps its bin/ file list as is. README names the adhd setting.
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

from scripthelp import ScriptRepo

SECTION_CAP = 3000

MIT_NOTICE = """Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def section_e(text):
    """What the hook prints: "## E. Output" up to the next "## " line."""
    lines = text.splitlines()
    start = lines.index("## E. Output")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return "\n".join(lines[start:end]).rstrip() + "\n"


def rule(text, code, nxt):
    """The text of one rule, from its code ("W8.") to the next marker."""
    start = text.index(code)
    return text[start:text.index(nxt, start)]


class PrinciplesCase(unittest.TestCase):
    def setUp(self):
        self.text = read("PRINCIPLES.md")
        self.assertIn("## E. Output", self.text.splitlines(),
                      "PRINCIPLES.md has no '## E. Output' line yet")
        self.e = section_e(self.text)
        self.low = self.e.lower()

    def has(self, *phrases, where=None):
        block = (where if where is not None else self.e).lower()
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), block)


class TestTheSection(PrinciplesCase):
    def test_it_comes_after_d(self):
        self.assertLess(self.text.index("## D. Auto setup"), self.text.index("## E. Output"))

    def test_it_fits_the_hook(self):
        size = len(self.e.encode())
        self.assertLessEqual(size, SECTION_CAP, "section E is %d bytes" % size)

    def test_terse_lines(self):
        for line in self.e.splitlines():
            with self.subTest(line=line[:60]):
                self.assertLessEqual(len(line), 160)

    def test_rule_codes(self):
        self.assertRegex(self.e, r"(?m)^E1\. ")

    def test_credit_line(self):
        self.has("i-have-adhd", "v0.4.1", "Ayoub Ghriss", "MIT")

    def test_no_owner_or_machine(self):
        for word in ("Maverick", "maverick", "laptop", "pc2"):
            with self.subTest(word=word):
                self.assertNotIn(word, self.e)


class TestF1TheRuleset(PrinciplesCase):
    def test_shape(self):
        self.has("next action", "number", "Step <n> of <m>", "tangent",
                 "estimate", "what now works", "Uh oh", "5 items")

    def test_no_padding(self):
        self.has("preamble", "recap", "closer")

    def test_overrides(self):
        self.has("explain", "destructive", "still broken", "ambiguous", "harness")

    def test_pre_send_check(self):
        self.has("pre-send", "first line", "last line", "hedge", "idiom")

    def test_it_stays_on(self):
        self.has("rest of the session")


class TestF2OwnerOverrides(PrinciplesCase):
    def test_never_fail_silently(self):
        self.has("fail silently", "blocked", "refused", "broken", "partial success")

    def test_tables_are_not_lists(self):
        self.has("tables and ledgers are not lists", "completeness")

    def test_verified_needs_evidence(self):
        self.has("verified", "evidence", "real device")

    def test_decide_section_stays(self):
        self.has("decide section", "H3")

    def test_language(self):
        self.has("H2")


class TestF3Concise(PrinciplesCase):
    def test_concise(self):
        self.has("lead with the result", "narration", "short by default",
                 "plainly", "full detail on request",
                 "never trade correctness for brevity")


class TestF4Switch(PrinciplesCase):
    def test_off_switches(self):
        self.has("adhd=off", "stop adhd mode", "normal mode")


class TestTheNotice(PrinciplesCase):
    def test_copyright_line(self):
        self.assertIn("Copyright (c) 2026 Ayoub Ghriss", self.text)

    def test_the_whole_permission_notice(self):
        self.assertIn(squash(MIT_NOTICE), squash(self.text))

    def test_it_is_after_section_e_not_inside(self):
        self.assertNotIn("Permission is hereby granted", self.e)
        self.assertGreater(self.text.index("Permission is hereby granted"),
                           self.text.index("## E. Output"))


class TestGeneric(PrinciplesCase):
    def test_no_owner_or_machine_names_anywhere(self):
        for word in ("Maverick", "maverick-pc2", "this laptop"):
            with self.subTest(word=word):
                self.assertNotIn(word, self.text)


class TestF5ManagerLaws(PrinciplesCase):
    def test_test_parallelism_is_capped(self):
        self.has("maxWorkers=2", "-j 2", where=rule(self.text, "S5.", "S6."))

    def test_reviewers_count_toward_the_cap(self):
        self.has("reviewer", where=rule(self.text, "S6.", "S7."))

    def test_push_at_every_stage_and_clean_after_a_verified_merge(self):
        self.has("push at every stage", where=self.text)
        self.has("merge is verified", where=rule(self.text, "W8.", "W9."))

    def test_watching_launches_and_stalls(self):
        self.has("process, terminal output, git movement", "2 min",
                 "nudge once", "salvage", "heartbeat", where=self.text)

    def test_only_owner_level_or_irreversible_stops_the_line(self):
        self.has("owner-level", "irreversible", where=rule(self.text, "W1.", "W2."))

    def test_model_by_kind_of_thinking(self):
        self.has("strongest", where=rule(self.text, "S9.", "## E. Output"))

    def test_full_gate_in_ci_order(self):
        self.has("CI's order", where=rule(self.text, "W4.", "W5."))

    def test_e2e_is_the_proof(self):
        block = rule(self.text, "W5.", "W6.")
        self.has("unit tests are not proof", "never verify their own work",
                 "needs a real device", where=block)

    def test_ask_in_one_batch_and_the_return_table(self):
        self.has("one batch", "interim default", "recommendation",
                 where=rule(self.text, "H1.", "H2."))

    def test_collision(self):
        self.has("collision", "never route around", where=self.text)


class TestF6Lessons(PrinciplesCase):
    def test_time(self):
        block = rule(self.text, "W11.", "W12.")
        self.has("`date`", "drift", "re-estimate", where=block)

    def test_commands(self):
        self.has("classifier", "! git push", "Deliver", "4 KB", "--cursor",
                 "mid-turn", "screen locked", "headless Chrome", where=self.text)


class TestF8ShortCityCommand(unittest.TestCase):
    def setUp(self):
        self.readme = read("README.md")

    def test_readme_uses_the_short_command(self):
        self.assertIsNone(re.search(r"\./bin/agent-city\.sh [a-z]", self.readme))
        self.assertIsNone(re.search(r"(?m)^\s*\./agent-city\.sh [a-z]", self.readme))
        self.assertRegex(self.readme, r"(?m)^agent-city start\b")

    def test_readme_says_once_how_to_get_it(self):
        lines = [l for l in self.readme.splitlines() if "agent-city.sh install-shim" in l]
        self.assertEqual(len(lines), 1, lines)
        self.assertRegex(lines[0], r"(?i)once|one time")

    def test_readme_keeps_the_bin_list(self):
        for row in ("  bin/agent-city.sh       starts/stops the agent city visualiser",
                    "  bin/agent-city-shim     the ~/.local/bin/agent-city command",
                    "  bin/agent-city-hook.sh  hook that feeds the city"):
            with self.subTest(row=row):
                self.assertIn(row, self.readme)

    def test_readme_names_the_adhd_setting(self):
        self.assertIn("adhd", self.readme)

    def help(self):
        repo = ScriptRepo()
        self.addCleanup(repo.cleanup)
        result = repo.run("agent-city.sh", "-h")
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_help_uses_the_short_command(self):
        out = self.help()
        self.assertIsNone(re.search(r"(?m)^\s*\./agent-city\.sh ", out), out)
        for verb in ("start", "stop", "status", "demo", "join", "cloud-deploy"):
            with self.subTest(verb=verb):
                self.assertRegex(out, r"(?m)^\s*agent-city %s\b" % re.escape(verb))

    def test_help_says_once_how_to_get_it(self):
        out = self.help()
        lines = [l for l in out.splitlines() if "agent-city.sh install-shim" in l]
        self.assertTrue(lines, out)
        self.assertRegex(" ".join(lines), r"(?i)once|one time|first")


if __name__ == "__main__":
    unittest.main()
