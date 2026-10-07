"""Failing tests: the startup hook prints the output section (daily-rules F4).
Written by the task manager first.

CONTRACT. PRINCIPLES.md has a section "## E. Output": how every agent shapes
what a human reads. It is on by default in every session where the plugin is
on, also in a repo that was never set up. So bin/agent-start.sh prints it.

  The section = the lines of the plugin's PRINCIPLES.md from the line
  "## E. Output" up to, not including, the next line that starts with "## "
  (or the end of the file). Blank lines at its end are dropped. It is printed
  as is, ending with one newline. Nothing else of PRINCIPLES.md is printed.

  Where it goes:
    normal start, compact, clear   right before the RULES line (the RULES and
                                   QUIZ lines stay the last lines)
    repo not set up                right after the one-line hint
                                   "auto-pipeline: not set up in this repo, ..."
                                   (still no file, no folder, no marker)

  agent.conf key adhd=on|off. Missing key or no agent.conf -> on.
    off -> the section is never printed (normal, compact, clear).
  bin/agent.conf.default has adhd=on; agent_conf.py validates it (on or off,
  anything else is refused with a message naming both); it has a hint and a
  group; `agent-settings.sh sync` adds adhd=on to a conf that lacks it.
  The repo's own agent.conf has adhd=on, right after language.

  A PRINCIPLES.md with no "## E. Output" -> nothing extra, exit 0.

SIZE. Measured 2026-10-07 on Claude Code 2.1.292 with `claude -p`: a
SessionStart hook's stdout of 9,984 bytes reaches the model whole; 10,244
bytes becomes "Output too large ... Preview (first 2KB)". The limit is per
hook. The old 2000-byte budget stays for everything except the section
(pointer_part below); the section itself is at most 3000 bytes
(tests/test_output_rules.py); so the whole hook output stays at or under
5000 bytes, half the measured limit.

  agent-init.sh: after the permission block (never inside it) one line names
  "Bash(git push origin main)" as optional, for when the auto-mode classifier
  denies the push to the integration branch.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

from scripthelp import ScriptCase, ScriptRepo

HEADING = "## E. Output"
RULES_PREFIX = "RULES: read "
NOT_HERE_LINE = ("auto-pipeline: not set up in this repo, "
                 "run /auto-pipeline:init to enable")
MEASURED_LIMIT = 10000
POINTER_CAP = 2000
WHOLE_CAP = 5000

FIXTURE = """# PRINCIPLES

- TOP-MARK the top lines

## D. Auto setup

D-MARK a rule

## E. Output

E-MARK-1 first rule
- E-MARK-2 second rule


## Notice

NOTICE-MARK the license
"""

FIXTURE_BLOCK = HEADING + "\n\nE-MARK-1 first rule\n- E-MARK-2 second rule\n"

FIXTURE_E_LAST = """# PRINCIPLES

## D. Auto setup

D-MARK a rule

## E. Output

E-MARK-1 first rule
- E-MARK-2 last rule in the file
"""


def pointer_part(out):
    """The hook output without the output section: drop the lines from
    "## E. Output" up to the RULES line (or the end)."""
    keep, skip = [], False
    for line in out.splitlines(keepends=True):
        if line.startswith(HEADING):
            skip = True
        elif skip and line.startswith(RULES_PREFIX):
            skip = False
        if not skip:
            keep.append(line)
    return "".join(keep)


class OutputCase(ScriptCase):
    script = "agent-start.sh"

    def setUp(self):
        super().setUp()
        self.write_principles(FIXTURE)

    def write_principles(self, text):
        with open(self.repo.plugin_path("PRINCIPLES.md"), "w") as fh:
            fh.write(text)

    def start(self, stdin=None, role="task-manager"):
        env = {"AGENT_ROLE": role} if role else {}
        return self.assertOk(self.repo.run("agent-start.sh", stdin=stdin, env=env))

    def hook(self, source, sid="s-out"):
        return self.start(stdin=json.dumps(
            {"cwd": self.repo.dir, "session_id": sid, "source": source}))

    def assert_block_before_rules(self, out):
        lines = out.splitlines()
        rules = [i for i, l in enumerate(lines) if l.startswith(RULES_PREFIX)]
        self.assertTrue(rules, out)
        before = "\n".join(lines[:rules[0]]) + "\n"
        self.assertTrue(before.endswith("\n" + FIXTURE_BLOCK) or before == FIXTURE_BLOCK,
                        "the section is not right before the RULES line:\n" + out)

    def assert_no_block(self, out):
        self.assertNotIn(HEADING, out)
        self.assertNotIn("E-MARK", out)


class TestAnInitializedRepo(OutputCase):
    def test_the_section_comes_right_before_the_rules_line(self):
        self.assert_block_before_rules(self.start())

    def test_rules_and_quiz_stay_the_last_two_lines(self):
        lines = self.lines(self.start())
        self.assertTrue(lines[-2].startswith(RULES_PREFIX), lines[-2])
        self.assertTrue(lines[-1].startswith("QUIZ: "), lines[-1])

    def test_nothing_else_of_principles(self):
        out = self.start()
        for mark in ("TOP-MARK", "D-MARK", "NOTICE-MARK", "## D.", "## Notice"):
            with self.subTest(mark=mark):
                self.assertNotIn(mark, out)

    def test_printed_once(self):
        self.assertEqual(self.start().count(HEADING), 1)

    def test_a_main_manager_gets_it_too(self):
        self.assert_block_before_rules(self.start(role=None))

    def test_a_missing_key_means_on(self):
        self.repo.unset_conf("adhd")
        self.assert_block_before_rules(self.start())

    def test_on_means_on(self):
        self.repo.set_conf("adhd", "on")
        self.assert_block_before_rules(self.start())

    def test_the_last_section_of_the_file_is_printed_to_the_end(self):
        self.write_principles(FIXTURE_E_LAST)
        out = self.start()
        self.assertIn("- E-MARK-2 last rule in the file\n" + RULES_PREFIX, out)
        self.assertNotIn("D-MARK", out)


class TestCompactAndClear(OutputCase):
    def test_compact_prints_it(self):
        self.assert_block_before_rules(self.hook("compact"))

    def test_clear_prints_it(self):
        self.assert_block_before_rules(self.hook("clear"))

    def test_compact_has_no_quiz_still(self):
        self.assertNotIn("QUIZ:", self.hook("compact"))


class TestOff(OutputCase):
    def setUp(self):
        super().setUp()
        self.repo.set_conf("adhd", "off")

    def test_normal_start(self):
        out = self.start()
        self.assert_no_block(out)
        self.assertTrue(self.lines(out)[-1].startswith("QUIZ: "))

    def test_compact(self):
        self.assert_no_block(self.hook("compact"))

    def test_clear(self):
        self.assert_no_block(self.hook("clear"))


class TestNoSection(OutputCase):
    def test_principles_without_section_e_prints_nothing_extra(self):
        self.write_principles("# PRINCIPLES\n\n## D. Auto setup\n\nD-MARK\n")
        out = self.start()
        self.assert_no_block(out)
        lines = self.lines(out)
        self.assertTrue(lines[-2].startswith(RULES_PREFIX))
        self.assertTrue(lines[-1].startswith("QUIZ: "))


class TestARepoNotSetUp(unittest.TestCase):
    """User-scope install, a repo that never turned the plugin on: the hint
    line, then the section. Still nothing written."""

    def setUp(self):
        self.repo = ScriptRepo(init_project=False)
        self.addCleanup(self.repo.cleanup)
        open(self.repo.orca_log, "w").close()
        self.repo.set_panes([])
        self.repo.git_init(self.repo.dir)
        with open(self.repo.plugin_path("PRINCIPLES.md"), "w") as fh:
            fh.write(FIXTURE)

    def start(self, stdin=None):
        result = self.repo.run("agent-start.sh", stdin=stdin,
                               env={"AGENT_ROLE": "task-manager"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def names(self):
        return sorted(n for n in os.listdir(self.repo.dir)
                      if n not in (".git", "stubbin", "seed.txt"))

    def test_hint_then_section(self):
        self.assertEqual(self.start(), NOT_HERE_LINE + "\n" + FIXTURE_BLOCK)

    def test_with_a_session_id_too(self):
        out = self.start(stdin=json.dumps(
            {"cwd": self.repo.dir, "session_id": "s1", "source": "startup"}))
        self.assertEqual(out, NOT_HERE_LINE + "\n" + FIXTURE_BLOCK)
        left = [n for n in os.listdir(os.path.join(self.repo.dir, ".git"))
                if n.startswith("agent_started_")]
        self.assertEqual(left, [])

    def test_nothing_is_written(self):
        self.start()
        self.assertEqual(self.names(), [])

    def test_the_real_section_fits(self):
        os.remove(self.repo.plugin_path("PRINCIPLES.md"))
        import shutil
        shutil.copy2(os.path.join(ROOT, "PRINCIPLES.md"),
                     self.repo.plugin_path("PRINCIPLES.md"))
        out = self.start()
        self.assertTrue(out.startswith(NOT_HERE_LINE + "\n"), out[:300])
        self.assertLessEqual(len(out.encode()), WHOLE_CAP)


class TestTheRealSizeOnABusyProject(ScriptCase):
    """The real PRINCIPLES.md (whatever section E holds today) on a busy
    project: the pointer part keeps its 2000 bytes, the whole stays at or
    under 5000, under the measured 10,000-byte limit."""

    script = "agent-start.sh"

    def setUp(self):
        super().setUp()
        long_line = "x" * 400
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            for i in range(4):
                fh.write("/very/long/path/to/worktree/number_%d | module_%d | "
                         "working | since 2026-09-22 10:00\n" % (i, i))
        with open(self.repo.path("agent_monitor.txt"), "w") as fh:
            for i in range(4):
                fh.write("/very/long/path/to/worktree/number_%d | module_%d | "
                         "pane working | commit 2m ago | activity 1m ago | OK "
                         "| 2026-09-22 10:00\n" % (i, i))
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            for i in range(60):
                fh.write("%02d %s\n" % (i, long_line))

    def check(self, out):
        size = len(out.encode())
        self.assertLessEqual(len(pointer_part(out).encode()), POINTER_CAP)
        self.assertLessEqual(size, WHOLE_CAP, "hook is %d bytes" % size)
        self.assertLess(size, MEASURED_LIMIT)

    def test_normal_start(self):
        self.check(self.assertOk(self.repo.run("agent-start.sh")))

    def test_compact(self):
        self.check(self.assertOk(self.repo.run(
            "agent-start.sh",
            stdin=json.dumps({"cwd": self.repo.dir, "session_id": "s2",
                              "source": "compact"}))))


class TestTheConfKey(ScriptCase):
    script = "agent-settings.sh"

    def conf_value(self, key):
        for line in open(self.repo.path("agent.conf")):
            if line.split("=", 1)[0].strip() == key:
                return line.split("=", 1)[1].strip()
        return None

    def test_the_template_says_on(self):
        import agent_conf
        conf = agent_conf.load(os.path.join(BIN, "agent.conf.default"))
        self.assertEqual(conf.get("adhd"), "on")

    def test_the_repo_conf_says_on_right_after_language(self):
        import agent_conf
        keys = list(agent_conf.load(os.path.join(ROOT, "agent.conf")))
        self.assertIn("adhd", keys)
        self.assertEqual(keys.index("adhd"), keys.index("language") + 1)
        self.assertEqual(agent_conf.load(os.path.join(ROOT, "agent.conf"))["adhd"], "on")

    def test_the_template_puts_it_right_after_language(self):
        import agent_conf
        keys = list(agent_conf.load(os.path.join(BIN, "agent.conf.default")))
        self.assertEqual(keys.index("adhd"), keys.index("language") + 1)

    def test_validate_value(self):
        import agent_conf
        self.assertIsNone(agent_conf.validate_value("adhd", "on"))
        self.assertIsNone(agent_conf.validate_value("adhd", "off"))
        for bad in ("yes", "ON", "", "true"):
            with self.subTest(bad=bad):
                message = agent_conf.validate_value("adhd", bad)
                self.assertTrue(message)
                self.assertIn("on", message)
                self.assertIn("off", message)

    def test_hint_and_group(self):
        import agent_conf
        self.assertTrue(agent_conf.HINTS.get("adhd", "").strip())
        self.assertNotEqual(agent_conf.group_of("adhd"), "other")

    def test_settings_saves_off(self):
        out = self.assertOk(self.repo.run("agent-settings.sh", "adhd", "off"))
        self.assertIn("saved: adhd=off", out)
        self.assertEqual(self.conf_value("adhd"), "off")

    def test_settings_refuses_a_bad_value(self):
        before = self.conf_value("adhd")
        result = self.repo.run("agent-settings.sh", "adhd", "maybe")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.conf_value("adhd"), before)

    def test_sync_adds_it(self):
        self.repo.unset_conf("adhd")
        out = self.assertOk(self.repo.run("agent-settings.sh", "sync"))
        self.assertIn("added adhd=on", out)
        self.assertEqual(self.conf_value("adhd"), "on")


class TestInitNamesThePushRule(ScriptCase):
    script = "agent-init.sh"

    def setUp(self):
        self.repo = ScriptRepo(init_project=False)
        self.addCleanup(self.repo.cleanup)
        self.repo.git_init(self.repo.dir)

    def test_optional_line_after_the_block(self):
        out = self.assertOk(self.repo.run("agent-init.sh"))
        start, end = out.index("{"), out.rindex("}")
        block = json.loads(out[start:end + 1])
        self.assertNotIn("Bash(git push origin main)", block["permissions"]["allow"])
        after = out[end + 1:]
        line = [l for l in after.splitlines() if "Bash(git push origin main)" in l]
        self.assertTrue(line, after)
        self.assertIn("optional", line[0].lower())


if __name__ == "__main__":
    unittest.main()
