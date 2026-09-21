"""Failing tests for the agent-start.sh changes.

CONTRACT:

  1. agent-start.sh prints an agent_monitor.txt section at startup, a section
     like the other files, right after the agent_worktree.txt section:

         === agent_monitor.txt (agent health) ===
         <the file, or "(none)" when there is nothing to show>

  2. The RAM and CPU readers move into agent-resources.sh, which agent-start.sh
     sources. agent-resources.sh gives:

         ram_used              -> percent, or -1 when it cannot tell
         cpu_used              -> percent, or -1 when it cannot tell
         resources_line <cap>  -> "RESOURCES: RAM <n>% CPU <n>% (cap <n>%) -> OK"
                                  or the same line ending "-> OVER CAP"
         resources_ok <cap>    -> exit 0 when both are under the cap

     AGENT_FAKE_RAM and AGENT_FAKE_CPU override the real readings, so a test
     never has to measure the machine.

  3. Nothing else about agent-start.sh changes: the quiz still grades, and
     --answer with all 29 right still says PASS.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase

MONITOR_LINE = ("/tmp/wt | alpha | pane working | commit 2m ago | "
                "output 0m ago | OK | 2026-09-21 18:00")


class StartCase(ScriptCase):
    script = "agent-start.sh"

    def start(self, *args, **kwargs):
        return self.repo.run("agent-start.sh", *args, **kwargs)


class TestMonitorSection(StartCase):
    def test_prints_the_section_with_the_file(self):
        with open(self.repo.path("agent_monitor.txt"), "w") as fh:
            fh.write(MONITOR_LINE + "\n")
        out = self.assertOk(self.start())
        self.assertIn("=== agent_monitor.txt (agent health) ===", out)
        self.assertIn(MONITOR_LINE, out)

    def test_says_none_when_there_is_no_file(self):
        out = self.assertOk(self.start())
        head, _, tail = out.partition("=== agent_monitor.txt (agent health) ===")
        self.assertTrue(tail, "the monitor section is missing")
        self.assertEqual(tail.strip().splitlines()[0], "(none)")

    def test_says_none_when_the_file_is_empty(self):
        open(self.repo.path("agent_monitor.txt"), "w").close()
        out = self.assertOk(self.start())
        _, _, tail = out.partition("=== agent_monitor.txt (agent health) ===")
        self.assertEqual(tail.strip().splitlines()[0], "(none)")

    def test_comes_after_the_worktree_section(self):
        out = self.assertOk(self.start())
        worktree_at = out.index("=== agent_worktree.txt")
        monitor_at = out.index("=== agent_monitor.txt")
        self.assertLess(worktree_at, monitor_at)

    def test_comes_before_the_quiz(self):
        out = self.assertOk(self.start())
        self.assertLess(out.index("=== agent_monitor.txt"), out.index("=== QUIZ"))


class TestResourcesHelper(StartCase):
    def helper(self, *args, **kwargs):
        return self.repo.run("agent-resources.sh", *args, **kwargs)

    def test_the_helper_file_exists(self):
        self.assertTrue(os.path.exists(self.repo.path("agent-resources.sh")),
                        "agent-resources.sh is missing")

    def test_agent_start_uses_the_fake_readings(self):
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "12",
                                            "AGENT_FAKE_CPU": "34"}))
        self.assertIn("RESOURCES: RAM 12% CPU 34% (cap 80%) -> OK", out)

    def test_over_cap_line_and_warning(self):
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "95",
                                            "AGENT_FAKE_CPU": "10"}))
        self.assertIn("RESOURCES: RAM 95% CPU 10% (cap 80%) -> OVER CAP", out)
        self.assertIn("Do not start agents", out)

    def test_cpu_over_cap_also_trips_it(self):
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "10",
                                            "AGENT_FAKE_CPU": "99"}))
        self.assertIn("-> OVER CAP", out)

    def test_cap_comes_from_agent_conf(self):
        self.repo.set_conf("max_usage_percent", "30")
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "40",
                                            "AGENT_FAKE_CPU": "10"}))
        self.assertIn("(cap 30%) -> OVER CAP", out)

    def test_the_helper_can_be_sourced_on_its_own(self):
        script = self.repo.path("check.sh")
        with open(script, "w") as fh:
            fh.write("#!/usr/bin/env bash\nset -eu\n"
                     "cd \"$(dirname \"$0\")\"\n"
                     ". ./agent-resources.sh\n"
                     "resources_line 80\n"
                     "resources_ok 80 && echo under || echo over\n")
        os.chmod(script, 0o755)
        out = self.assertOk(self.repo.run("check.sh",
                                          env={"AGENT_FAKE_RAM": "15",
                                               "AGENT_FAKE_CPU": "25"}))
        self.assertIn("RESOURCES: RAM 15% CPU 25% (cap 80%) -> OK", out)
        self.assertIn("under", out)

    def test_the_reading_is_taken_once(self):
        """resources_read fills RAM_USED and CPU_USED. The rest reuse them.

        Reading twice costs about 1.4 seconds each time on a Mac, and the
        printed line can then disagree with the decision that follows it.
        """
        script = self.repo.path("check3.sh")
        with open(script, "w") as fh:
            fh.write("#!/usr/bin/env bash\nset -eu\n"
                     "cd \"$(dirname \"$0\")\"\n"
                     ". ./agent-resources.sh\n"
                     "resources_read\n"
                     "echo \"read: $RAM_USED $CPU_USED\"\n"
                     "AGENT_FAKE_RAM=99 AGENT_FAKE_CPU=98 resources_line 80\n")
        os.chmod(script, 0o755)
        out = self.assertOk(self.repo.run("check3.sh",
                                          env={"AGENT_FAKE_RAM": "11",
                                               "AGENT_FAKE_CPU": "22"}))
        self.assertIn("read: 11 22", out)
        self.assertIn("RESOURCES: RAM 11% CPU 22% (cap 80%) -> OK", out,
                      "resources_line measured again instead of reusing the reading")

    def test_agent_start_reads_the_machine_once(self):
        """One reading for the line and the warning together."""
        script = self.repo.path("count.sh")
        with open(script, "w") as fh:
            fh.write("#!/usr/bin/env bash\nset -eu\n"
                     "cd \"$(dirname \"$0\")\"\n"
                     ". ./agent-resources.sh\n"
                     "resources_read\n"
                     "resources_line 80 >/dev/null\n"
                     "resources_ok 80 && echo under || echo over\n"
                     "echo \"ram=$RAM_USED\"\n")
        os.chmod(script, 0o755)
        out = self.assertOk(self.repo.run("count.sh",
                                          env={"AGENT_FAKE_RAM": "11",
                                               "AGENT_FAKE_CPU": "22"}))
        self.assertIn("under", out)
        self.assertIn("ram=11", out)

    def test_resources_ok_fails_over_the_cap(self):
        script = self.repo.path("check2.sh")
        with open(script, "w") as fh:
            fh.write("#!/usr/bin/env bash\nset -eu\n"
                     "cd \"$(dirname \"$0\")\"\n"
                     ". ./agent-resources.sh\n"
                     "resources_ok 80 && echo under || echo over\n")
        os.chmod(script, 0o755)
        out = self.assertOk(self.repo.run("check2.sh",
                                          env={"AGENT_FAKE_RAM": "90",
                                               "AGENT_FAKE_CPU": "10"}))
        self.assertIn("over", out)


class TestQuizStillWorks(StartCase):
    ANSWERS = ("1A 2D 3C 4B 5D 6D 7A 8C 9A 10D 11A 12C 13D 14C 15B 16C 17C "
               "18D 19B 20A 21D 22C 23B 24D 25A 26D 27A 28B 29B")

    def test_all_right_is_a_pass(self):
        out = self.assertOk(self.start("--answer", self.ANSWERS))
        self.assertIn("29/29 PASS", out)

    def test_one_wrong_is_a_fail(self):
        result = self.start("--answer", self.ANSWERS.replace("1A", "1B"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL", result.stdout)

    def test_the_rules_are_still_printed(self):
        out = self.assertOk(self.start())
        self.assertIn("=== PRINCIPLES.md ===", out)
        self.assertIn("=== QUIZ", out)


class TestGitignore(unittest.TestCase):
    def test_agent_monitor_txt_is_ignored(self):
        root = os.path.dirname(HERE)
        with open(os.path.join(root, ".gitignore")) as fh:
            lines = [l.strip() for l in fh]
        self.assertIn("agent_monitor.txt", lines)

    def test_the_half_written_sweep_file_is_ignored_too(self):
        """A sweep killed mid-write leaves agent_monitor.txt.tmp.<pid> behind."""
        root = os.path.dirname(HERE)
        with open(os.path.join(root, ".gitignore")) as fh:
            lines = [l.strip() for l in fh]
        self.assertIn("agent_monitor.txt.tmp.*", lines)


if __name__ == "__main__":
    unittest.main()
