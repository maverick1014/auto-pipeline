"""Failing tests for housekeep-suspects: `agent-file.sh idea keep <n>`.
Written by the task manager, before any code.

WHY: the housekeep pass flags idea suspects; the main manager judges each one.
Done (or voided by a recorded owner decision) -> `idea rm <n>`. Still wanted ->
`idea keep <n>`, so the same idea is never flagged again.

CONTRACT
    agent-file.sh idea keep <n>

    - Line n of agent_ideas.txt gets the field " | kept <YYYY-MM-DD>" at its end
      (the date part of AGENT_FAKE_NOW, else today). Any line shape: with the
      "| <date time> | by <who>" tail or without it.
    - A line that already has " | kept <date>" at its end: the date is replaced
      in place, the line keeps one kept field.
    - Every other line stays byte for byte; the text of line n too (a "/",
      "&", "\\", "'" or "$" in it is not touched). Written via a tmp file + mv,
      like idea rm.
    - Prints "idea <n> kept: <first 60 chars of the line as it was>".
    - n not a whole number, 0, or past the last line -> "no idea number <n>"
      on stderr, exit 1, nothing written. No n at all -> usage, exit 2.
    - idea list shows the field (it prints the lines as they are).
    - idea rm <n> removes a kept line like any other.
    - The usage header has one line for `agent-file.sh idea keep <n>`.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase  # noqa: E402

NOW = "2026-11-13 21:00"
A = "teach todo-est to keep the reason | 2026-11-05 10:02 | by main"
B = "a gap seen (five-fixes S1, pc2) | 2026-11-05 10:03 | by task-manager"
C = "plain idea with no tail"


class IdeaKeepCase(ScriptCase):
    script = "agent-file.sh"

    def set_ideas(self, lines):
        with open(self.repo.path("agent_ideas.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def ideas_raw(self):
        with open(self.repo.path("agent_ideas.txt")) as fh:
            return fh.read()

    def ideas(self):
        return self.ideas_raw().splitlines()

    def keep(self, *args, now=NOW):
        return self.repo.run("agent-file.sh", "idea", "keep", *args,
                             env={"AGENT_FAKE_NOW": now})


class TestIdeaKeep(IdeaKeepCase):
    def test_the_field_goes_at_the_end_of_line_n(self):
        self.set_ideas([A, B, C])
        self.assertOk(self.keep("2"))
        self.assertEqual(self.ideas(), [A, B + " | kept 2026-11-13", C])

    def test_it_says_what_it_did(self):
        self.set_ideas([A, B])
        out = self.assertOk(self.keep("1"))
        self.assertIn("idea 1 kept: " + A[:60], out)

    def test_a_line_with_no_tail(self):
        self.set_ideas([A, C])
        self.assertOk(self.keep("2"))
        self.assertEqual(self.ideas(), [A, C + " | kept 2026-11-13"])

    def test_keep_again_replaces_the_date(self):
        self.set_ideas([A])
        self.assertOk(self.keep("1"))
        self.assertOk(self.keep("1", now="2026-11-14 08:00"))
        self.assertEqual(self.ideas(), [A + " | kept 2026-11-14"])

    def test_the_other_lines_stay_byte_for_byte(self):
        odd = "path a/b & c \\d 'q' $x  two spaces | 2026-11-05 10:04 | by main"
        self.set_ideas([odd, A, odd + " again"])
        before = self.ideas_raw()
        self.assertOk(self.keep("2"))
        after = self.ideas_raw()
        self.assertEqual(after, before.replace(A + "\n", A + " | kept 2026-11-13\n", 1))

    def test_a_special_line_itself_is_kept_as_it_is(self):
        odd = "path a/b & c \\d 'q' $x  two spaces | 2026-11-05 10:04 | by main"
        self.set_ideas([odd])
        self.assertOk(self.keep("1"))
        self.assertEqual(self.ideas(), [odd + " | kept 2026-11-13"])

    def test_no_tmp_file_is_left(self):
        self.set_ideas([A])
        self.assertOk(self.keep("1"))
        left = [n for n in os.listdir(self.repo.dir) if n.startswith("agent_ideas.txt.")]
        self.assertEqual(left, [])


class TestIdeaKeepRefusals(IdeaKeepCase):
    def test_bad_numbers_change_nothing(self):
        self.set_ideas([A, B])
        before = self.ideas_raw()
        for bad in ("0", "3", "x", "-1", "1x", ""):
            with self.subTest(n=bad):
                res = self.keep(bad)
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn("no idea number", res.stderr)
                self.assertEqual(self.ideas_raw(), before)

    def test_no_number_is_usage(self):
        self.set_ideas([A])
        before = self.ideas_raw()
        res = self.keep()
        self.assertEqual(res.returncode, 2)
        self.assertEqual(self.ideas_raw(), before)


class TestIdeaKeepWithTheOtherVerbs(IdeaKeepCase):
    def test_idea_list_shows_the_field(self):
        self.set_ideas([A, B])
        self.assertOk(self.keep("1"))
        out = self.assertOk(self.repo.run("agent-file.sh", "idea", "list"))
        self.assertIn("kept 2026-11-13", out)

    def test_idea_rm_removes_a_kept_line(self):
        self.set_ideas([A, B])
        self.assertOk(self.keep("1"))
        self.assertOk(self.repo.run("agent-file.sh", "idea", "rm", "1"))
        self.assertEqual(self.ideas(), [B])

    def test_idea_add_after_a_keep_appends_as_before(self):
        self.set_ideas([A])
        self.assertOk(self.keep("1"))
        self.assertOk(self.repo.run("agent-file.sh", "idea", "add", "new one",
                                    env={"AGENT_FAKE_NOW": NOW}))
        self.assertEqual(self.ideas(), [A + " | kept 2026-11-13",
                                        "new one | 2026-11-13 21:00 | by main"])

    def test_usage_lists_idea_keep(self):
        res = self.repo.run("agent-file.sh")
        self.assertEqual(res.returncode, 2)
        lines = [l for l in (res.stdout + res.stderr).splitlines()
                 if "agent-file.sh idea keep <n>" in l]
        self.assertEqual(len(lines), 1, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
