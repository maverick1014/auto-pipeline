# Check blocks
Read when: you plan the blocks of a task, run one, write its result line, gate a merge, or write a requirement doc (its examples and defaults feed the blocks). Owner approval of a block: rules/approval.md.

R8. Check blocks
- Owner 2026-11-25: "let other agents verify the outcome of the code instead of letting test cases do it"; tests only show old things still work and cost memory and time; an urgent fix must not wait for a test flow
- PR REVIEW, the main check of every task: an agent that did not build it reads the diff against the approved requirement
- It asks: does it do what was asked, nothing else; are the edge list lines covered; is no check deleted; no secret; its cost follows the diff size, one more reason for small tasks
- A run or browser check (FLOW CHECK, UI CHECK) comes on top only when what the user sees or does changed: only the approved items, a 15-minute time box (`verify_box_min`), extra finds go to the ideas file
- Owner 2026-11-25: "only do the necessary thing when needed, dont do extra thing. and dont do less thing"
- No levels: each check is a block with a trigger; a task runs the blocks whose trigger fires, nothing else
- The one table, source `bin/agent_blocks.py`; this table, the skills and the quiz are tested against it:

| Block | Picked | Trigger | What runs | Owner signs |
|---|---|---|---|---|
| PR REVIEW | tool | every task | an agent that did not build it reads the diff against the approved requirement: does it do what was asked and nothing else, are the edge list lines covered, is no check deleted, no secret; its cost follows the diff size | no |
| DIFF SCAN | tool | every task | the tool scans the diff: files outside the task's scope, deleted or skipped tests, secrets, debug leftovers | no |
| BUILD | tool | code changed | lint + type-check or syntax check of the app that was touched | no |
| RELATED TESTS | tool | code, text or rule files changed | only the LIGHT tests (measured) that import or name the changed files. Style-only change of a shared component: the component's own tests. Rule text: the tests that name the changed section. A heavy one goes to the release run or the nightly | no |
| MODULE TESTS | tool | code used by other modules changed, or dependencies, lockfile, CI or test config changed | the tests of every module that uses the changed code, light module groups only; a dependency, lockfile, CI or test-config change: the tests of every module. A heavy group goes to the release run or the nightly | a dependency, lockfile, CI or test-config change |
| GUARD TESTS | tool | code or text changed | the repo's tree-scanning tests (listed in the repo file) | no |
| DB CHECK | tool | a migration or schema file is in the diff | dry run on a data copy, counts before and after, rollback plan | only when the migration changes or removes data or columns |
| DATA CHECK | tool | a script that changes live data | preview of the rows (the count must match the expected one), backup | yes |
| CORE REVIEW | tool | a core path of the repo is touched (money, permission), or the brief says who can see or do what changes, or a posting rule changes | an independent read-only agent reads the logic against the rules the owner approved | a permission change |
| EXAMPLES TEST | brief | behaviour or logic changes | failing tests first, written from the examples in the requirement doc; they cover the fitting lines of the repo's edge list. Money and permission rules: the owner approves the examples before code | no |
| FLOW CHECK | brief | what a user does changes | someone who did not build it runs 1 normal path + 1 error path: only the approved items, a 15-minute time box, extra finds go to the ideas file | no |
| UI CHECK | brief | what a user sees changes: new page, re-layout, size or responsive change | compare with the approved mock or the before screenshot, desktop and phone width. Style change of a shared component: look at a few different usages only. A 15-minute time box, extra finds go to the ideas file | no |
| REAL DATA COUNT | brief | a rule, limit or validation is added or tightened, or a list, print or export changes | one read-only count on real data: how many existing records would be refused, and the largest real size. No read access: skipped with one printed line, never silently | no |

- Picked tool: `agent-level.sh check --base <ref>` decides them from the real diff, no judgment
- Picked brief: dispatch picks them from what the owner approved: `todo add ... --checks "<BLOCK>,<BLOCK>"`
- Two passes: the brief blocks at dispatch; before merge the tool recomputes the tool blocks from the real diff
- Blocks are only added; removing one needs a verified owner order: `todo checks <task> --remove <BLOCK> --owner-quote "<his words>" --means "<the action>"`
- PR REVIEW and OWNER SIGN are never removed
- One result line per block: `agent-file.sh check <task> "<BLOCK>" pass|fail --by <who> --evidence "<text>"`
- The reviewer and the check deputy always pass --commit <the head they looked at>
- PR REVIEW, FLOW CHECK and UI CHECK count only from a reviewer or check deputy the main manager launched (the guard records the launch)
- A check line records the commit it saw; PR REVIEW, FLOW CHECK and UI CHECK count only at the head being merged (or a commit after which every commit is a merge of the base)
- Threat model: the gate guards against mistakes and shortcuts made through the documented commands
- It does not stop an agent that forges files by hand; a forgery is a breach the main manager reports to the owner
- The merge gate `agent-file.sh checks gate <task>` refuses while a planned block has no pass line
- PR REVIEW, CORE REVIEW, FLOW CHECK and UI CHECK pass only by someone who did not build the task: not the builder (the todo line's builder or its LAUNCH records)
- No task runs the full suite (owner 1A 2026-11-25): MODULE TESTS is the largest per-task check
- OWNER SIGN is planned when a sign fires: MODULE TESTS on a dependency, lockfile, CI or test-config change, DATA CHECK, DB CHECK on a data change, CORE REVIEW on a permission change
- Dispatch plans OWNER SIGN with CORE REVIEW when the brief changes who can see or do what
- BUILD and GUARD TESTS run per task only when their measured time in agent_repo.conf is under `check_budget_s` (60 s)
- Slower = heavy: it runs in the net, not in the task
- Four kinds of request, one line each:
  - Refactor (no behaviour change): BUILD + RELATED TESTS; no new examples, the existing tests are the acceptance
  - Urgent fix (production is broken): the URGENT FIX path in rules/branches.md
  - Rollback: back to the last green commit; BUILD + RELATED TESTS of the reverted files; a database change follows its written rollback plan
  - Research only (no diff): no blocks; the report is the deliverable
- Repo facts live in the committed `agent_repo.conf`, written by init and kept by agents; a human may edit it, never has to: core paths, guard tests, test commands, the edge list, real-data access
- The team values live there too and win over a member's Configure: task_files, task_take, data_branch
- After each bug fix the fixing agent asks "which example would have shown it" and adds one line with `agent-file.sh edge add "<text>"` when the list lacks it
- Beyond the reviewer's PR REVIEW, a second agent's opinion only for CORE REVIEW, or when someone wants a tool-triggered block removed
- A requirement table copies its defaults from the released template and lists every changed default for the owner
- A requirement doc that only writes down his request in his words needs no second yes; one that adds scope or picks an owner-level option goes to him first (R1)
