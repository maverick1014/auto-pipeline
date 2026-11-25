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
    _b("DIFF SCAN", "tool", "every task",
       "the tool scans the diff: files outside the task's scope, deleted or skipped tests, secrets, "
       "debug leftovers"),
    _b("BUILD", "tool", "code changed",
       "lint + type-check or syntax check of the app that was touched"),
    _b("RELATED TESTS", "tool", "code, text or rule files changed",
       "only the tests that import or name the changed files. Style-only change of a shared component: "
       "the component's own tests. Rule text: the tests that name the changed section"),
    _b("MODULE TESTS", "tool",
       "code used by other modules changed, or dependencies, lockfile, CI or test config changed",
       "the tests of every module that uses the changed code; a dependency, lockfile, CI or test-config "
       "change: the tests of every module",
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
    _b("DIFF READ", "brief", "text, style, a simple move (banner -> toast)",
       "someone who did not write it reads the diff. That is the acceptance. A 5-minute task stays a "
       "5-minute task"),
    _b("EXAMPLES TEST", "brief", "behaviour or logic changes",
       "failing tests first, written from the examples in the requirement doc; they cover the fitting "
       "lines of the repo's edge list. Money and permission rules: the owner approves the examples "
       "before code"),
    _b("FLOW CHECK", "brief", "a behaviour a user can reach changes",
       "someone who did not build it runs 1 normal path + 1 error path"),
    _b("UI CHECK", "brief", "new page, re-layout, size or responsive change",
       "compare with the approved mock or the before screenshot, desktop and phone width. Style change "
       "of a shared component: look at a few different usages only"),
    _b("REAL DATA COUNT", "brief",
       "a rule, limit or validation is added or tightened, or a list, print or export changes",
       "one read-only count on real data: how many existing records would be refused, and the largest "
       "real size. No read access: skipped with one printed line, never silently"),
]

NET = [
    {"name": "NIGHTLY RUN",
     "runs": "all tests run once every night in the background on the heavy-test machine. It gates "
             "nothing. A failure the causing task's own RELATED or MODULE run did not find is recorded "
             "as a selection miss"},
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
