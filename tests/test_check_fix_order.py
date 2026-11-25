"""Failing tests for check-blocks section 42: FIX ORDER 1 of the main manager (TELL 6bf8830d).
Written by the task manager before any fix. One class per item: B1-B5, S1-S11, D1-D4.

Run: python3 -m unittest tests.test_check_fix_order
"""

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def rule(start, end):
    text = read("PRINCIPLES.md")
    return text[text.index(start):text.index(end)]


DISPATCH = ("skills", "dispatch", "SKILL.md")
MERGE = ("skills", "merge", "SKILL.md")
DEPUTY = ("agents", "merge-deputy.md")
FAST = ("agents", "fast-lane-deputy.md")
CHECK = ("agents", "check-deputy.md")


class TestB1NoWorkerCap(unittest.TestCase):
    def test_dispatch(self):
        d = read(*DISPATCH)
        self.assertNotIn("max 2 at once", d)
        self.assertIn("as many at once as the memory rule admits (S3)", d)


class TestB2NoSuiteAtTheMerge(unittest.TestCase):
    def test_merge_and_deputy(self):
        self.assertNotIn("suite command:", read(*MERGE))
        dep = read(*DEPUTY)
        self.assertNotIn("<suite command>", dep)
        self.assertIn("No test run at the merge (W4: never re-run what passed; R8: no task runs the full suite)", dep)


class TestB3StepOneChecksTheBuildersBlocks(unittest.TestCase):
    def test_merge_step_1(self):
        m = read(*MERGE)
        self.assertNotIn("a tool block with no pass line → bounce it", m)
        self.assertIn("a block the builder owns with no pass line", m)
        self.assertIn("PR REVIEW, CORE REVIEW, FLOW CHECK and UI CHECK are checked by the gate after the reviewer and "
                      "the check deputy ran", m)


class TestB4FastLaneReportHasTimeAndFacts(unittest.TestCase):
    def test_fast_lane(self):
        f = read(*FAST)
        report = f[f.index("Report (H3)"):]
        self.assertIn("TIME:", report)
        self.assertIn("FACTS:", report)


class TestB5TodoDoneOnce(unittest.TestCase):
    def test_dispatch_and_merge(self):
        step2 = [l for l in read(*DISPATCH).splitlines() if l.startswith("2. Small task")][0]
        self.assertNotIn("todo done", step2)
        m = read(*MERGE)
        self.assertNotIn("--lane full", m)
        self.assertIn("--lane <full|fast>", m)


class TestS1ProductionPathCleansUp(unittest.TestCase):
    def test_merge_and_deputy(self):
        self.assertIn("merged: <merge hash>", read(*MERGE))
        dep = read(*DEPUTY)
        self.assertIn("`merged: <merge hash>`", dep)
        self.assertIn("skips steps 1-4", dep)


class TestS2S3CheckDeputy(unittest.TestCase):
    def test_smoke_launch_is_the_main_managers(self):
        self.assertIn("the main manager does the one subagent launch", read(*CHECK))

    def test_resize_tool(self):
        tools = [l for l in read(*CHECK).splitlines() if l.startswith("tools:")][0]
        self.assertIn("mcp__claude-in-chrome__resize_window", tools)


class TestS4HeadlessIsTheCheckDeputys(unittest.TestCase):
    def test_merge(self):
        m = read(*MERGE)
        self.assertNotIn("Run the same click path with Playwright", m)
        self.assertIn("the check deputy runs the same click path with Playwright", m)


class TestS5SyncAtABatchStart(unittest.TestCase):
    def test_dispatch(self):
        self.assertIn("agent-promote.sh --sync", read(*DISPATCH))


class TestS6NotSwitchedYet(unittest.TestCase):
    def test_r8(self):
        self.assertIn("A repo whose working branch exists but whose main checkout is not switched yet: merges go into "
                      "the production branch as before", rule("R8. ", "W1. "))


class TestS7NoSlotNoLevel(unittest.TestCase):
    def test_texts(self):
        text = read("PRINCIPLES.md")
        self.assertNotIn("WATCH SLOT", text)
        self.assertIn("WATCH ROOM", rule("W15. ", "W16. "))
        self.assertIn("level (old tasks only, - for new ones)", rule("R5. ", "R6. "))
        d = read(*DISPATCH)
        self.assertNotIn("slot", d.lower())
        self.assertIn("Waiting for room or another task", d)

    def test_code(self):
        self.assertNotIn("WATCH SLOT", read("bin", "agent_watch.py"))
        self.assertIn("WATCH ROOM %s: can start", read("bin", "agent_watch.py"))
        af = read("bin", "agent-file.sh")
        self.assertNotIn("slots <free>", af)
        self.assertNotIn("suite slot", af)


class TestS8ModelsBySetting(unittest.TestCase):
    def test_w6_and_tree(self):
        text = read("PRINCIPLES.md")
        self.assertNotIn("Sonnet 5, medium", text)
        w6 = rule("W6. ", "W7. ")
        for role in ("Fast-lane deputy", "Merge deputy", "Check deputy", "Worker"):
            line = [l for l in w6.splitlines() if l.startswith("- %s (" % role)][0]
            self.assertIn("Helper model", line)

    def test_the_setting_names_the_check_deputy(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import agent_conf
        desc = [s for s in agent_conf.SETTINGS if s["key"] == "helper_model"][0]
        self.assertIn("check deputy", json.dumps(desc))
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as fh:
            self.assertIn("check deputy", json.load(fh)["userConfig"]["helper_model"]["description"])


class TestS9OneWording(unittest.TestCase):
    def test_r8(self):
        r8 = rule("R8. ", "W1. ")
        self.assertNotIn("never by the user", r8)
        self.assertIn("a human may edit it, never has to", r8)


class TestS10StatusFinal(unittest.TestCase):
    def test_dispatch(self):
        d = read(*DISPATCH)
        self.assertNotIn("set status done", d)
        self.assertIn("set status final (R7)", d)


class TestS11PermissionModeDefault(unittest.TestCase):
    def test_s1(self):
        s1 = rule("S1. ", "S2. ")
        self.assertIn('"Permissions: Permission mode" setting, default bypassPermissions', s1)


class TestD1MockRule(unittest.TestCase):
    def test_r1_and_dispatch(self):
        r1 = rule("R1. ", "R2. ")
        self.assertNotIn("Mock if the task has UI", r1)
        self.assertIn("2. Mock for a new page or a whole-page re-layout (W2)", r1)
        self.assertIn("a new page or a whole-page re-layout", read(*DISPATCH))


class TestD2CleanupOrder(unittest.TestCase):
    def test_w8(self):
        w8 = rule("W8. ", "W9. ")
        self.assertNotIn("Clean up only after the merge is verified", w8)
        self.assertIn("Delete the branch and close the todo line only after the merge is verified", w8)
        self.assertIn("the pane and the worktree may go while waiting for the owner's yes; the pushed branch stays", w8)


class TestD3ResultFirst(unittest.TestCase):
    def test_e1(self):
        e1 = rule("E1. ", "E2. ")
        self.assertNotIn("Lead with the next action", e1)
        self.assertIn("Lead with the result", e1)
        self.assertIn("A command, path or snippet the human must use comes right after the result", e1)
        self.assertIn("End with one concrete next action", e1)


class TestD4WaitExceptions(unittest.TestCase):
    def test_w1(self):
        self.assertIn("Never wait for the human, except: the kick-off round, a mock yes, an OWNER SIGN, NEEDS HUMAN E2E",
                      rule("W1. ", "W2. "))


if __name__ == "__main__":
    unittest.main()
