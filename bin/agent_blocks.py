#!/usr/bin/env python3
"""agent_blocks.py - the ONE table of check blocks and their triggers (R8). Python 3.9, stdlib only.

requirements/check-blocks.md section 1 and C1. agent_level.py imports the names and the order from here;
PRINCIPLES.md R8, the skills and the quiz are tested against it.

    agent_blocks.py names     the 13 block names, one per line, table order
    agent_blocks.py table     the markdown table | Block | Picked | Trigger | What runs | Owner signs |

sign: "no", "yes", or the condition text. OWNER SIGN is no row: the tool plans it when a sign fires.
No text here holds a pipe character (it is a table cell).
"""

import sys


def _b(name, picked, trigger, runs, sign="no"):
    return {"name": name, "picked": picked, "trigger": trigger, "runs": runs, "sign": sign}


BLOCKS = [
    _b("PR REVIEW", "tool", "every task",
       "an agent that did not build it reads the diff against the approved requirement: does it do what "
       "was asked and nothing else, are the edge list lines covered, is no check deleted, no secret; its "
       "cost follows the diff size"),
    _b("DIFF SCAN", "tool", "every task",
       "the tool scans the diff: files outside the task's scope, deleted or skipped tests, secrets, "
       "debug leftovers"),
    _b("BUILD", "tool", "code changed",
       "lint + type-check or syntax check of the app that was touched"),
    _b("RELATED TESTS", "tool", "code, text or rule files changed",
       "only the LIGHT tests (measured) that import or name the changed files. Style-only change of a "
       "shared component: the component's own tests. Rule text: the tests that name the changed section. "
       "A heavy one goes to the release run or the nightly"),
    _b("MODULE TESTS", "tool",
       "code used by other modules changed, or dependencies, lockfile, CI or test config changed",
       "the tests of every module that uses the changed code, light module groups only; a dependency, "
       "lockfile, CI or test-config change: the tests of every module. A heavy group goes to the release "
       "run or the nightly",
       "a dependency, lockfile, CI or test-config change"),
    _b("GUARD TESTS", "tool", "code or text changed",
       "the repo's tree-scanning tests (listed in the repo file)"),
    _b("DB CHECK", "tool", "a migration or schema file is in the diff",
       "dry run on a data copy, counts before and after, rollback plan",
       "only when the migration changes or removes data or columns"),
    _b("DATA CHECK", "tool", "a script that changes live data",
       "preview of the rows (the count must match the expected one), backup", "yes"),
    _b("CORE REVIEW", "tool",
       "a core path of the repo is touched (money, permission), or the brief says who can see or do "
       "what changes, or a posting rule changes",
       "an independent read-only agent reads the logic against the rules the owner approved",
       "a permission change"),
    _b("EXAMPLES TEST", "brief", "behaviour or logic changes",
       "failing tests first, written from the examples in the requirement doc; they cover the fitting "
       "lines of the repo's edge list. Money and permission rules: the owner approves the examples "
       "before code"),
    _b("FLOW CHECK", "brief", "what a user does changes",
       "someone who did not build it runs 1 normal path + 1 error path: only the approved items, a "
       "15-minute time box, extra finds go to the ideas file"),
    _b("UI CHECK", "brief", "what a user sees changes: new page, re-layout, size or responsive change",
       "compare with the approved mock or the before screenshot, desktop and phone width. Style change "
       "of a shared component: look at a few different usages only. A 15-minute time box, extra finds "
       "go to the ideas file"),
    _b("REAL DATA COUNT", "brief",
       "a rule, limit or validation is added or tightened, or a list, print or export changes",
       "one read-only count on real data: how many existing records would be refused, and the largest "
       "real size. No read access: skipped with one printed line, never silently"),
]

NET = [
    {"name": "NIGHTLY RUN",
     "runs": "all tests run once every night in the background on the machine with the most room. It "
             "gates nothing. A failure the causing task's own RELATED or MODULE run did not find is "
             "recorded as a selection miss"},
    {"name": "RELEASE RUN",
     "runs": "the full suite once on the working branch before a release (a green nightly on that commit "
             "counts); failures go to a new fixer agent, never back to the builder; the release waits "
             "until it is green"},
    {"name": "RELEASE SMOKE",
     "runs": "after every release a fresh session uses the released version for real: start, one "
             "subagent launch and finish, the user-facing flows that changed"},
]

NAMES = [b["name"] for b in BLOCKS]
TOOL_NAMES = [b["name"] for b in BLOCKS if b["picked"] == "tool"]
BRIEF_NAMES = [b["name"] for b in BLOCKS if b["picked"] == "brief"]


def table():
    rows = ["| Block | Picked | Trigger | What runs | Owner signs |", "|---|---|---|---|---|"]
    for b in BLOCKS:
        rows.append("| %s | %s | %s | %s | %s |" % (b["name"], b["picked"], b["trigger"], b["runs"], b["sign"]))
    return rows


def main(argv):
    if len(argv) == 1 and argv[0] == "names":
        sys.stdout.write("\n".join(NAMES) + "\n")
        return 0
    if len(argv) == 1 and argv[0] == "table":
        sys.stdout.write("\n".join(table()) + "\n")
        return 0
    sys.stderr.write("usage: agent_blocks.py names | table\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
