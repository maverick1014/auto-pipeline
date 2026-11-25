# check-blocks — requirement (owner approved 2026-11-25: "1A ok", "4A correct", "Remove it is better")

Goal, in the owner's words: "only do the necessary thing when needed, dont do extra thing. and dont do less thing".
No levels (A-D, 0-4) any more. Each check is a block with a trigger. A task runs the blocks whose trigger fires, nothing else.
Rules live only in the plugin. A repo keeps only its own facts, written and kept up to date by the agent, never by the user.

## 1. Blocks

Decided by the tool from the real diff (no judgment):

| Block | Trigger | What runs |
|---|---|---|
| DIFF SCAN | every task | the tool scans the diff: files outside the task's scope, deleted or skipped tests, secrets, debug leftovers |
| BUILD | code changed | lint + type-check or syntax check of the app that was touched |
| RELATED TESTS | code, text or rule files changed | only the tests that import or name the changed files. API change: also the integration groups of every module that imports the changed file. Style-only change of a shared component: the component's own tests. Rule text: the tests that name the changed section |
| GUARD TESTS | code or text changed | the repo's tree-scanning tests (listed in the repo file) |
| DB CHECK | a migration or schema file is in the diff | dry run on a data copy, counts before and after, rollback plan. The owner signs only when the migration changes or removes data or columns |
| DATA CHECK + owner signs | a script that changes live data | preview of the rows (the count must match the expected one), backup |
| FULL SUITE + owner signs | dependencies, lockfile, CI or test config changed | the full suite, once |
| CORE REVIEW | a core path of the repo is touched (money, permission), or the brief says who can see or do what changes, or a posting rule changes | an independent read-only agent reads the logic against the rules the owner approved. A permission change needs the owner's sign |

Picked from the brief at dispatch (did we build the right thing: compare with what the owner approved):

| Block | When | What runs |
|---|---|---|
| DIFF READ | text, style, a simple move (banner -> toast) | someone who did not write it reads the diff. That is the acceptance. A 5-minute task stays a 5-minute task |
| EXAMPLES TEST | behaviour or logic changes | failing tests first, written from the examples in the requirement doc; they cover the fitting lines of the repo's edge list. Money and permission rules: the owner approves the examples before code |
| FLOW CHECK | a behaviour a user can reach changes | someone who did not build it runs 1 normal path + 1 error path |
| UI CHECK | new page, re-layout, size or responsive change | compare with the approved mock or the before screenshot, desktop and phone width. Style change of a shared component: look at a few different usages only |
| REAL DATA COUNT | a rule, limit or validation is added or tightened, or a list, print or export changes | one read-only count on real data: how many existing records would be refused, and the largest real size. No read access: skipped with one printed line, never silently |

Outside tasks (the net):
- The full suite runs every night or before a release, in the background on the heavy-test machine. Nobody waits for it. Red = the first task next morning.
- RELEASE SMOKE after every release: a fresh session uses the released version for real (start, one subagent launch and finish, the user-facing flows that changed).

## 2. Process rules

- Two passes. At dispatch the manager picks the acceptance blocks from the brief. Before merge the tool recomputes the tool-decided blocks from the real diff. Blocks are only added. Removing a block needs a verified owner order (agent-owner-order.sh).
- Each block writes one result line: block, pass or fail, who, evidence. The merge refuses while a planned block has no pass line.
- Who does the work follows size only: a small task = one subagent, which also writes its example tests and runs its blocks. A big task (over 2 hours, several slices) = a task manager. Which checks run follows the triggers only. A small logic task never opens a task manager just because it needs a test.
- Each subagent works in its own git worktree and pushes a branch; a merge deputy merges it. Several small tasks run side by side and never share a checkout (owner 1A, 2026-11-25; evidence: 21 tasks done this way, median 22 minutes from open to done).
- A small task that grows: past 2x its estimate, or it needs a second slice -> the subagent stops and reports. The manager opens a task manager that goes on from its branch.
- Tasks are assigned by themselves when a slot is free (owner 1A, 2026-11-25). Three parts:
  - `todo done <X>` releases every task queued after X and prints them.
  - At every wake (an agent's report, a watch signal, a human message) the main manager first runs one command (`agent-file.sh next`): it lists the queued tasks that can start now: a slot is free under the machine caps, RAM is under the cap, no open task changes the same files. The manager dispatches them at once; a task the owner already approved needs no new question.
  - The watch wakes the main manager when a slot is free and a task is queued.
- Four kinds of request, one line each:
  - Refactor (no behaviour change): BUILD + RELATED TESTS. No new examples; the existing tests are the acceptance.
  - Urgent fix (production is broken): the smallest fix, the same triggers. A verified owner order may move a block to right after the release; a block is never dropped.
  - Rollback: back to the last green commit; BUILD + RELATED TESTS of the reverted files; a database change follows its written rollback plan.
  - Research only (no diff): no blocks. The report is the deliverable.
- BUILD cost is measured, not guessed: init times the repo's lint and type-check commands and notes their RAM in the repo file. A build that needs a machine-wide lock (v4-plus API type-check: 6 GB, one at a time) is queued like a heavy test; decide on a lighter build only after the numbers are in.
- The main manager stays free for the human (owner 2026-11-25): it runs no long check itself. Browser checks, diff reads, re-checks after a bounce and the release smoke go to a deputy, one at a time on the browser. The manager gets a short verdict with evidence. The chat with the human stays short and tidy.
- A second agent's opinion only for CORE REVIEW, or when someone wants a tool-triggered block removed. Not for every task.
- Rules live in the plugin only. A repo's CLAUDE.md keeps what is only that repo's own.
- One source: one table of blocks and triggers. The tool reads it; PRINCIPLES, the skills and the quiz are tested against it.

## 3. Repo facts: fully handled by the agent

- One committed file in the repo (agent_repo.conf): core paths, guard tests, the test commands (build, related, integration groups), the edge list, real-data access (where the read-only secret is, or none).
- init writes version 1 by scanning the repo: it detects the test tools, finds the tree-scanning tests, proposes core paths (auth, permission, money, migrations), picks the generic edges that fit (empty value, more than one page, deleted rows, invalid input, day boundary in local time, double submit, large size) and reads about the last 20 fix commits for edges of this repo.
- After each bug fix the fixing agent asks "which example would have shown it" and adds one line when the list lacks it.
- A human may read or edit the file. A human never has to.

## 4. What changes (one change, every copy)

- PRINCIPLES.md: R1 (lane by size), R8 rewritten (blocks, no A-D), W4, W5 (who drives the browser), W6 (main manager free, check deputy), W8, the map lines.
- skills/dispatch (the task manager brief says "run the blocks of the task", never "Full suite once"), skills/merge, agents/merge-deputy, agents/fast-lane-deputy (writes the example tests of a small logic task), a new check deputy with browser and read tools, the quiz.
- bin/agent_level.py prints the triggered blocks. agent-file.sh: the todo line carries `checks ...`; a result line per block; the merge guard.
- The board: column "level" becomes "checks". Old todo lines with a level still read.
- tests/test_agent_release.py dry run: no longer red on main between a release and the next version bump.
- Tests follow. The full suite once before the release of this change.

## 5. Acceptance examples (the owner's use cases first)

| Task | Blocks | Not run |
|---|---|---|
| banner -> toast on one page | DIFF SCAN, BUILD, RELATED (that page's tests), DIFF READ; about 5 minutes | mock, flow, suite |
| style change of a shared component | the same + UI CHECK on a few different usages | every other page |
| wording (locale values) | DIFF SCAN, RELATED (tests that name the string), GUARD, DIFF READ | UI, flow |
| new export column, one feature | BUILD, RELATED, EXAMPLES, FLOW | suite |
| a shared validator changes | BUILD, RELATED (every spec that imports it + the groups of importing modules), EXAMPLES, FLOW | suite |
| migration that only adds a column | DB CHECK, no sign | suite |
| migration with UPDATE or DROP | DB CHECK + owner signs | |
| script that fixes live data | DATA CHECK + owner signs | tests |
| a new validation limit | + REAL DATA COUNT | |
| rule text in PRINCIPLES.md | DIFF READ, RELATED (tests that name the section), GUARD | suite |
| dependency bump | FULL SUITE + owner signs | |

## 6. Evidence behind this design

- Review of the old rules: 14 findings (2026-11-25, in the main manager's transcript).
- Replay on v4-plus history, 742 code merges: FULL SUITE triggers on 44 (6%); owner signs 135 (18%) with "data-changing migrations only" against 217 (29%) with every migration; 190 (26%) need no logic test; median diff 889 lines, 11 files; 113 (15%) touch a core path; 68 (9%) change journal code outside the core paths.
- 20 real fix merges traced to their cause: 16 product bugs, the full suite was green when each was merged. 4 test-only reds: caught by RELATED + GUARD. 5 wrong rule or limit, seen only on real data -> REAL DATA COUNT. 4 edge cases missing from the examples -> edge list. 3 nothing could catch. 1 needs a real device. 3 other.
- Data files: scratchpad/replay/v4-blocks.tsv, replay_v4.py (main manager's scratchpad).

## 7. Also in this task (same files, from the brief 2026-11-25)

- `agent-file.sh todo est <name> <minutes> [--guess <m>]`: re-estimate an open todo line; every other field stays (opened, started, waited, stage, where).
- merge deputy: after a failed post-merge run it undoes with `git reset --merge ORIG_HEAD`, never `--hard` (that wipes the uncommitted agent_*.txt of the main checkout).
- merge deputy: two cases get their own steps: (a) the session is a human-direct Helper that stays (no pane close, no worktree removal, branch kept); (b) the worktree and pane are on another machine (block check on a local scratch copy, orca commands with --environment).
- The requirement table of a task copies defaults from the released template and lists every changed default for the owner (a table once changed permission_mode from bypassPermissions to auto by mistake).

## 8. Not in this task

- The status line layout (branch statusline-wide: statusline_text in bin/agent_board.py).
- The start-time permission mode notice (branch mode-match: start text in bin/agent-start.sh).
- The pc2 stage push and the watch's false stall (report-to-main-pc2).
