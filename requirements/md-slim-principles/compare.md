# Independent comparison: old PRINCIPLES.md vs the new set (task md-slim-principles)

Written by a separate read-only agent. Nothing else was changed. `bin/agent-start.sh` was not run (read-only brief; it writes the seat lock and state files).

## Which "old"
- OLD = `PRINCIPLES.old-249f1c1.md`, **740 lines**. It is byte-identical to `249f1c1:PRINCIPLES.md`. During this check the branch `Niagawan-mave/approval-design` was merged into main (149710d) and the remote branch deleted; `git diff 249f1c1 149710d -- PRINCIPLES.md skills agents` is empty, so this copy is still the live text. Skills were read at 249f1c1.
- NEW = PRINCIPLES.md (79) + rules/*.md (18 files) + GLOSSARY.md + NOTICE.md + proposed-skill-changes.md, plus the skills it points to.

## Method
1. Every non-blank line of OLD (headings and code fences skipped; license and map lines included) was searched word for word in the new files with my own script (not from proof.md).
2. The 92 lines with no word-for-word hit, and the 18 that hit only proposed-skill-changes.md, were checked by hand against the new files and the skills at 249f1c1.
3. Only after that, proof.md was compared (section 6).

## Counts (653 lines)
| class | lines |
|---|---|
| SAME | 587 (incl. 17 license lines, ~75 map/command/file-table lines) |
| REWORDED-OK | 43 |
| REWORDED-CHANGED | 3 (375, 439, 624; 624 is justified by code) |
| WEAKER | 1 (312) |
| STRONGER | 0 |
| LOST | 0 |
| ONLY PROPOSED | 18 (4 are W9/W13/W14/W18 anchors, 8 describe script output, 6 are agent rules) |
| n/a | 1 (622, map intro) |

## Items to fix (old line -> what)
| old line | class | what is missing or changed |
|---|---|---|
| 312 W9 | WEAKER | skill dispatch:23 has "tell the owner at once, never guess" but not the two options "(ship them together, or move that part into the urgent task)". Not in proposed-skill-changes.md. Quiz Q35 tests this rule |
| 439 W17 | REWORDED-CHANGED | "Human messages are exempt" (from the floor check) became "Reports, heartbeats, questions and human messages are not orders" (core:60). Read plainly it says a human message is not an order. Fix: "Human messages are exempt from this check" |
| 375 W13 | REWORDED-CHANGED | "update the agent files" -> skill close-case B4 only runs `agent-file.sh show` to check them |
| 624 F | REWORDED-CHANGED (justified) | `--language zh` dropped from the cloud-pack clone command; bin/agent-cloud-pack.sh:39 exits 2 on --language. Correct, but it is a change, not a reword |
| 183 R8 | SAME, broken pointer | checks.md:49 "the URGENT FIX path above": URGENT FIX is in rules/branches.md:10 |
| 71 R5 | REWORDED-OK, wording | files.md:23 "No agent writes them" reads as "agents never write agent_* files"; old meant "do not spend an agent on it" |
| 4, 560 | SAME words, smaller effect | the start hook prints `## E. Output` of PRINCIPLES.md and re-prints PRINCIPLES.md after compaction: with the new core, E is printed nowhere and the rule files are not re-printed. rules/output.md:2 "The start text prints this file" is false until phase 2 |
| 300, 304, 305, 311, 379, 448 | ONLY PROPOSED | agent rules that sit only in proposed-skill-changes.md: never share a checkout; never an Orca worktree + task manager for a small task; `todo done <X>` releases the queue; target is per task, not per request (full line); next session after --release is main manager, never Helper; question fields come from `park add`. Most are implied elsewhere (see table), but none is in a file an agent reads until phase 2 applies them |
| 385-388, 391, 392, 446, 447 | ONLY PROPOSED | board / question-list output rules (script behaviour) |
| 297, 365, 381, 443 | ONLY PROPOSED | the code anchors W9, W13, W14, W18 (skill titles already cite them) |

## 1. Full table (old file top to bottom)
| old line | old text | class | new home | note |
|---|---|---|---|---|
| 3 | - Read first. Binding for every agent in this repo. | REWORDED-OK | PRINCIPLES.md:2 | "Read first" dropped; the start text RULES line does it |
| 4 | - Output shape: section E. Human language: the Language setting (H2). | REWORDED-OK | PRINCIPLES.md:63 -> rules/output.md; rules/human.md:19 | the start text prints "## E. Output" of PRINCIPLES.md; the new core has none, so nothing prints until phase 2 |
| 5 | - Settings live only in /plugin -> Installed -> auto-pipeline -> Configure (S1). Other numbers are fixed const... | SAME | PRINCIPLES.md:3 | word for word |
| 9 | P1. Fastest correct way | SAME | PRINCIPLES.md:5 | word for word |
| 10 | - Owner 2026-11-25: "use the most fast and efficiency way for any of your works". This comes first, for every ... | SAME | PRINCIPLES.md:6 | word for word |
| 11 | - Before each step ask: what is the quickest way to the correct result? Take that way | REWORDED-OK | PRINCIPLES.md:7 |  |
| 12 | - Check, do not wait: a quick check (read the file, a trial merge) settles a doubt faster than a queue or a qu... | SAME | PRINCIPLES.md:8 | word for word |
| 13 | - Parallel first: tasks run on their own branches; the one that merges second resolves the conflict. For an ag... | SAME | PRINCIPLES.md:9 | word for word |
| 14 | - Parallel also for the same module in a different part, and for a conflict in text that is not logic (docs, l... | SAME | PRINCIPLES.md:10 | word for word |
| 15 | - One exception: a follow-up on the logic an agent is changing right now goes to that agent. Two agents changi... | SAME | PRINCIPLES.md:11 | word for word |
| 16 | - Decide, do not ask: when the owner's words or a rule already answer it, or a default can be taken and logged... | REWORDED-OK | PRINCIPLES.md:12 |  |
| 17 | - Ask the owner only an owner-level or irreversible call (W1) | SAME | PRINCIPLES.md:12 | word for word |
| 18 | - Challenged on a decision: check the facts first, then keep it with the evidence, or change it and say what w... | REWORDED-OK | PRINCIPLES.md:13 | "first" dropped; order kept by "then" |
| 19 | - Work that does not depend on other work runs in parallel; take the smallest change and the cheapest tool tha... | REWORDED-OK | PRINCIPLES.md:14 |  |
| 20 | - Fast never means less: no required check skipped, no failure hidden, no cleanup left. A wrong result is the ... | SAME | PRINCIPLES.md:15 | word for word |
| 24 | R1. One flow, two lanes | SAME | PRINCIPLES.md:23 | word for word |
| 25 | - Before the flow: the main manager writes the requirement doc, the owner approves it | SAME | PRINCIPLES.md:24 | word for word |
| 26 | - Full flow, in order: | SAME | PRINCIPLES.md:24 | word for word |
| 27 | 1. Todo line + estimate | SAME | PRINCIPLES.md:25 | word for word |
| 28 | 2. Mock for a new page or a whole-page re-layout (W2) | SAME | PRINCIPLES.md:26 | word for word |
| 29 | 3. Worktree + task manager | SAME | PRINCIPLES.md:27 | word for word |
| 30 | 4. Failing tests first | SAME | PRINCIPLES.md:28 | word for word |
| 31 | 5. Workers build | SAME | PRINCIPLES.md:29 | word for word |
| 32 | 6. Verify | SAME | PRINCIPLES.md:30, rules/watch.md:9 | word for word |
| 33 | 7. Push | SAME | PRINCIPLES.md:31, PRINCIPLES.md:77 | word for word |
| 34 | 8. Acceptance blocks (R8) | SAME | PRINCIPLES.md:32 | word for word |
| 35 | 9. Merge into the target branch + cleanup | SAME | PRINCIPLES.md:33 | word for word |
| 36 | 10. Todo done | SAME | PRINCIPLES.md:34 | word for word |
| 37 | - Task size picks who does the work: small task = one subagent in its own git worktree (fast lane); it writes ... | REWORDED-OK | PRINCIPLES.md:35 + rules/roles.md:6 | own worktree, example tests, its blocks: only rules/roles.md:6 and agents/fast-lane-deputy.md |
| 38 | - Big task (over 2 hours, several slices) = a task manager (full lane) | REWORDED-OK | PRINCIPLES.md:35-37 |  |
| 39 | - Which checks run follows the triggers only (R8), never the lane | REWORDED-OK | PRINCIPLES.md:35-37 |  |
| 40 | - A small logic task never opens a task manager just because it needs a test | REWORDED-OK | PRINCIPLES.md:35-37 |  |
| 41 | - A small task that grows (past 2x its estimate, or it needs a second slice): the subagent stops and reports; ... | REWORDED-OK | PRINCIPLES.md:35-37 |  |
| 42 | - One fixed sequence after the build: builder reports done -> reviewer reads the diff against the approved req... | REWORDED-OK | PRINCIPLES.md:38 + rules/checks.md:6,8 + rules/roles.md:8 | "one fixed sequence" -> arrows; the 15-min box and "against the approved requirement" only in checks.md |
| 43 | - A fail at review or check goes back to the builder as a fix order | SAME | PRINCIPLES.md:38 |  |
| 44 | - The target: the user's request decides, read by the approval cases (R8). It says publish or merge to main ->... | SAME | rules/branches.md:5 | word for word |
| 45 | - No such words, or unclear -> the working branch (ap-main-<name>, setting "Flow: Working branch"); nothing go... | SAME | rules/branches.md:6 | word for word |
| 47 | R2. Secrets | SAME | PRINCIPLES.md:46 | word for word |
| 48 | - Live in `.secrets/` (git-ignored) | REWORDED-OK | PRINCIPLES.md:46 | three lines -> one |
| 49 | - Read only | REWORDED-OK | PRINCIPLES.md:46 | three lines -> one |
| 50 | - Never write, print, copy, commit | REWORDED-OK | PRINCIPLES.md:46 | three lines -> one |
| 52 | R3. Docs | SAME | rules/files.md:4 | word for word |
| 53 | - Allowed: requirement, test, main idea | SAME | rules/files.md:5 | word for word |
| 54 | - Nothing else | SAME | rules/files.md:6, rules/human.md:38 | word for word |
| 55 | - `PRINCIPLES.md` = main idea doc | SAME | rules/files.md:7 | word for word |
| 56 | - Entry files allowed: `CLAUDE.md`, `AGENTS.md` (one line, point to `bin/agent-start.sh`) | SAME | rules/files.md:8 | word for word |
| 57 | - `README.md` allowed: the picture of the tree and the flow, for people new to the repo | SAME | rules/files.md:9 | word for word |
| 58 | - Config, not docs, allowed: `.claude-plugin/`, `agents/`, `skills/`, `hooks/`, `bin/` | SAME | rules/files.md:10 | word for word |
| 59 | - Rubbish: `/auto-pipeline:clean-up` (main manager) lists other docs, old state copies, finished mocks and sta... | SAME | rules/files.md:11 | word for word |
| 61 | R4. No changelog | SAME | rules/files.md:13 | word for word |
| 62 | - Git history is the record | SAME | rules/files.md:14 | word for word |
| 64 | R5. Task files | SAME | rules/files.md:16 | word for word |
| 65 | - `agent_todo.txt` = open tasks only, always current | SAME | rules/files.md:17 | word for word |
| 66 | - Done → agent_completed.txt: date, name, what, then one `data` block written by `agent-file.sh`: repo, type, ... | SAME | rules/files.md:18 | word for word |
| 67 | - No test results in it, that is report material | SAME | rules/files.md:19 | word for word |
| 68 | - No other task tracking | SAME | rules/files.md:20 | word for word |
| 69 | - The housekeep pass never closes a todo line: it flags one whose branch is merged into the working branch or ... | SAME | rules/files.md:21 | word for word |
| 70 | - A stale todo line is flagged too: no worktree line, no open wait, quiet longer than the interval of W8 | SAME | rules/files.md:22 | word for word |
| 71 | - All four `agent_*.txt` files are written only through `bin/agent-file.sh`. No agent for that, it costs token... | REWORDED-OK | PRINCIPLES.md:49 + rules/files.md:23 | "No agent for that" -> "No agent writes them": reads as "agents never write them"; meant "never spend an agent on it". Fix the words |
| 72 | - `agent_completed.txt` is never deleted, trimmed or cleaned (every clean-up skips it); only on an explicit ow... | SAME | rules/files.md:24 | word for word |
| 74 | R6. Ideas file | SAME | rules/files.md:26 | word for word |
| 75 | - `agent_ideas.txt` = ideas outside the current task | SAME | rules/files.md:27 | word for word |
| 76 | - Agents append, keep it clean and current | SAME | rules/files.md:28 | word for word |
| 77 | - Human reviews it on his own time | SAME | rules/files.md:29 | word for word |
| 78 | - The housekeep pass removes an exact duplicate idea (the first stays) and flags suspects (an idea naming a ta... | SAME | rules/files.md:30 | word for word |
| 80 | R7. Worktree file | SAME | rules/files.md:35 | word for word |
| 81 | - `agent_worktree.txt` = one line per live worktree: path, task manager, module, status (working \| final \| i... | SAME | rules/files.md:36 | word for word |
| 82 | - Task manager updates its own line. Deputy removes the line after cleanup | SAME | rules/files.md:37 | word for word |
| 83 | - Main manager reads it before every dispatch (W9) | SAME | rules/files.md:38 | word for word |
| 84 | - The housekeep pass removes a line whose worktree folder is gone and has no live pane; a working, final or hu... | SAME | rules/files.md:39 | word for word |
| 86 | R8. Check blocks | SAME | rules/checks.md:4 | word for word |
| 87 | - Owner 2026-11-25: "let other agents verify the outcome of the code instead of letting test cases do it"; tes... | SAME | rules/checks.md:5 | word for word |
| 88 | - PR REVIEW, the main check of every task: an agent that did not build it reads the diff against the approved ... | SAME | rules/checks.md:6 | word for word |
| 89 | - It asks: does it do what was asked, nothing else; are the edge list lines covered; is no check deleted; no s... | SAME | rules/checks.md:7 | word for word |
| 90 | - A run or browser check (FLOW CHECK, UI CHECK) comes on top only when what the user sees or does changed: onl... | SAME | rules/checks.md:8 | word for word |
| 91 | - Tests stay as a cheap guard: light related tests in every task; a bug that a review or check finds gets a sm... | SAME | rules/tests.md:5 | word for word |
| 92 | - The full suite is the safety net only: the release run on the working branch and the nightly, never in a tas... | SAME | rules/branches.md:9 | word for word |
| 93 | - URGENT FIX: branch from the production branch, the smallest fix, PR REVIEW and the light related tests | SAME | rules/branches.md:10 | word for word |
| 94 | - Here his verified words at dispatch, read as the publish of that task, are his final yes (W12); no second ye... | SAME | rules/branches.md:11 | word for word |
| 95 | - Then merge to production (`agent-promote.sh --task`; the deploy follows) and merge production back into the ... | SAME | rules/branches.md:12 | word for word |
| 96 | - Owner 2026-11-25: "only do the necessary thing when needed, dont do extra thing. and dont do less thing" | SAME | rules/checks.md:9 | word for word |
| 97 | - No levels: each check is a block with a trigger; a task runs the blocks whose trigger fires, nothing else | SAME | rules/checks.md:10 | word for word |
| 98 | - The one table, source `bin/agent_blocks.py`; this table, the skills and the quiz are tested against it: | SAME | rules/checks.md:11 | word for word |
| 100 | \| Block \| Picked \| Trigger \| What runs \| Owner signs \| | SAME | rules/checks.md:13 | word for word |
| 101 | \|---\|---\|---\|---\|---\| | SAME | rules/checks.md:14 | word for word |
| 102 | \| PR REVIEW \| tool \| every task \| an agent that did not build it reads the diff against the approved requi... | SAME | rules/checks.md:15 | word for word |
| 103 | \| DIFF SCAN \| tool \| every task \| the tool scans the diff: files outside the task's scope, deleted or skip... | SAME | rules/checks.md:16 | word for word |
| 104 | \| BUILD \| tool \| code changed \| lint + type-check or syntax check of the app that was touched \| no \| | SAME | rules/checks.md:17 | word for word |
| 105 | \| RELATED TESTS \| tool \| code, text or rule files changed \| only the LIGHT tests (measured) that import or... | SAME | rules/checks.md:18 | word for word |
| 106 | \| MODULE TESTS \| tool \| code used by other modules changed, or dependencies, lockfile, CI or test config ch... | SAME | rules/checks.md:19 | word for word |
| 107 | \| GUARD TESTS \| tool \| code or text changed \| the repo's tree-scanning tests (listed in the repo file) \| ... | SAME | rules/checks.md:20 | word for word |
| 108 | \| DB CHECK \| tool \| a migration or schema file is in the diff \| dry run on a data copy, counts before and ... | SAME | rules/checks.md:21 | word for word |
| 109 | \| DATA CHECK \| tool \| a script that changes live data \| preview of the rows (the count must match the expe... | SAME | rules/checks.md:22 | word for word |
| 110 | \| CORE REVIEW \| tool \| a core path of the repo is touched (money, permission), or the brief says who can se... | SAME | rules/checks.md:23 | word for word |
| 111 | \| EXAMPLES TEST \| brief \| behaviour or logic changes \| failing tests first, written from the examples in t... | SAME | rules/checks.md:24 | word for word |
| 112 | \| FLOW CHECK \| brief \| what a user does changes \| someone who did not build it runs 1 normal path + 1 erro... | SAME | rules/checks.md:25 | word for word |
| 113 | \| UI CHECK \| brief \| what a user sees changes: new page, re-layout, size or responsive change \| compare wi... | SAME | rules/checks.md:26 | word for word |
| 114 | \| REAL DATA COUNT \| brief \| a rule, limit or validation is added or tightened, or a list, print or export c... | SAME | rules/checks.md:27 | word for word |
| 116 | - Picked tool: `agent-level.sh check --base <ref>` decides them from the real diff, no judgment | SAME | rules/checks.md:29 | word for word |
| 117 | - Picked brief: dispatch picks them from what the owner approved: `todo add ... --checks "<BLOCK>,<BLOCK>"` | SAME | rules/checks.md:30 | word for word |
| 118 | - Two passes: the brief blocks at dispatch; before merge the tool recomputes the tool blocks from the real dif... | SAME | rules/checks.md:31 | word for word |
| 119 | - Blocks are only added; removing one needs a verified owner order: `todo checks <task> --remove <BLOCK> --own... | SAME | rules/checks.md:32 | word for word |
| 120 | - Approval rule: three places need his yes: a task published straight to production, a block left out, the wor... | SAME | rules/approval.md:5 | word for word |
| 121 | - The deciding agent reads his words; no fixed sentence, no word list | SAME | rules/approval.md:6 | word for word |
| 122 | - The tool only checks the quote is a prompt he typed and stores it with what the main manager read: `--owner-... | SAME | rules/approval.md:7 | word for word |
| 123 | - A quote under 20 characters ("1A", "ok") counts only as his whole prompt, with the question it answered | SAME | rules/approval.md:8 | word for word |
| 124 | - The gate and promote print the stored pair as OWNER WORDS lines; the report to him repeats them | SAME | rules/approval.md:9 | word for word |
| 125 | - Approval cases: | SAME | rules/approval.md:10 | word for word |
| 126 | - A numbered batch: "2. publish direct after done, others wait for my review" -> task 2 gets target production... | SAME | rules/approval.md:11 | word for word |
| 127 | - No numbers, a task named by its description: exactly one fits -> no question | SAME | rules/approval.md:12 | word for word |
| 128 | - With two similar tasks: check first (todo lines, requirement docs, what he said before); still unsure -> one... | SAME | rules/approval.md:13 | word for word |
| 129 | - Not a yes now: a question ("is it ready to publish?"), a later time ("publish next week": park one `agent-fi... | SAME | rules/approval.md:14 | word for word |
| 130 | - A yes after the task was added: `todo target <task> production --owner-quote "<his words>" --means "<the act... | SAME | rules/approval.md:15 | word for word |
| 131 | - After `todo target <task> production ...` the main manager sends a new fast-lane deputy: a new branch from t... | SAME | rules/approval.md:16 | word for word |
| 132 | - Its brief names `late yes of: <task>` and `old branch: <branch>` | SAME | rules/approval.md:17 | word for word |
| 133 | - Then every planned block runs again at its head (PR REVIEW, FLOW CHECK, UI CHECK, CORE REVIEW, OWNER SIGN), ... | SAME | rules/approval.md:18 | word for word |
| 134 | - A task already merged (todo line closed): the same deputy cherry-picks its commits from the working branch, ... | SAME | rules/approval.md:19 | word for word |
| 135 | - A cherry-pick that conflicts, or a task that depends on other unreleased work -> the main manager tells the ... | SAME | rules/approval.md:20 | word for word |
| 136 | - A relayed owner order is verified where he typed it: the approval commands take `--relayed-from <the sender'... | SAME | rules/approval.md:21 | word for word |
| 137 | - `--relayed-from` must be a repo with a main manager lock (now or before); a relay from another machine canno... | SAME | rules/approval.md:22 | word for word |
| 138 | - A condition the flow already meets ("publish after the tests pass") is a yes; unsure -> one question | SAME | rules/approval.md:23 | word for word |
| 139 | - His short answer to a numbered question counts together with that question: the question stands in the assis... | SAME | rules/approval.md:24 | word for word |
| 140 | - PR REVIEW and OWNER SIGN are never removed | SAME | rules/checks.md:33 | word for word |
| 141 | - A production task is added at dispatch: `todo add ... --target production --owner-quote "<his words>" --mean... | SAME | rules/approval.md:25 | word for word |
| 142 | - One result line per block: `agent-file.sh check <task> "<BLOCK>" pass\|fail --by <who> --evidence "<text>"` | SAME | rules/checks.md:34 | word for word |
| 143 | - The reviewer and the check deputy always pass --commit <the head they looked at> | SAME | rules/checks.md:35 | word for word |
| 144 | - PR REVIEW, FLOW CHECK and UI CHECK count only from a reviewer or check deputy the main manager launched (the... | SAME | rules/checks.md:36 | word for word |
| 145 | - A check line records the commit it saw; PR REVIEW, FLOW CHECK and UI CHECK count only at the head being merg... | SAME | rules/checks.md:37 | word for word |
| 146 | - Threat model: the gate guards against mistakes and shortcuts made through the documented commands | SAME | rules/checks.md:38 | word for word |
| 147 | - It does not stop an agent that forges files by hand; a forgery is a breach the main manager reports to the o... | SAME | rules/checks.md:39 | word for word |
| 148 | - The merge gate `agent-file.sh checks gate <task>` refuses while a planned block has no pass line | SAME | rules/checks.md:40 | word for word |
| 149 | - PR REVIEW, CORE REVIEW, FLOW CHECK and UI CHECK pass only by someone who did not build the task: not the bui... | SAME | rules/checks.md:41 | word for word |
| 150 | - No task runs the full suite (owner 1A 2026-11-25): MODULE TESTS is the largest per-task check | SAME | rules/checks.md:42 | word for word |
| 151 | - OWNER SIGN is planned when a sign fires: MODULE TESTS on a dependency, lockfile, CI or test-config change, D... | SAME | rules/checks.md:43 | word for word |
| 152 | - Dispatch plans OWNER SIGN with CORE REVIEW when the brief changes who can see or do what | SAME | rules/checks.md:44 | word for word |
| 153 | - BUILD and GUARD TESTS run per task only when their measured time in agent_repo.conf is under `check_budget_s... | SAME | rules/checks.md:45 | word for word |
| 154 | - Slower = heavy: it runs in the net, not in the task | SAME | rules/checks.md:46 | word for word |
| 155 | - REAL DATA COUNT with no read access: skipped with one printed line, never silently | SAME | rules/checks.md:27 | same words as the table row |
| 156 | - Outside tasks, the net: NIGHTLY RUN, all tests once every night in the background (`agent-nightly.sh`); it g... | SAME | rules/branches.md:13 | word for word |
| 157 | - A failure the nightly finds that the causing task's own RELATED or MODULE run did not find is a selection mi... | SAME | rules/branches.md:14 | word for word |
| 158 | - After two weeks the owner reads the selection miss count and decides whether the nightly goes too | SAME | rules/branches.md:15 | word for word |
| 159 | - The watch's housekeep pass starts it once a day after 22:00 (`nightly_hour`) when no heavy test runs; no wat... | SAME | rules/branches.md:16 | word for word |
| 160 | - A release needs a green full run on the working branch: the last nightly on that commit, or one background r... | SAME | rules/branches.md:17 | word for word |
| 161 | - `agent-nightly.sh --start` runs the full suite in the background; `agent-nightly.sh --release-ok` only check... | SAME | rules/branches.md:18 | word for word |
| 162 | - The working branch (setting "Flow: Working branch", default `ap-main-<name>`) is only a branch | SAME | rules/branches.md:19 | word for word |
| 163 | - Everything merged or pushed lands there first, never on the production branch by accident: the main checkout... | SAME | rules/branches.md:20 | word for word |
| 164 | - init switches the main checkout of a new repo to the working branch; in a repo that already uses the plugin ... | SAME | rules/branches.md:21 | word for word |
| 165 | - A repo whose working branch exists but whose main checkout is not switched yet: merges go into the productio... | SAME | rules/branches.md:22 | word for word |
| 166 | - The working branch is per person (<name> = the git user name in lower case, only letters, digits and "-"): w... | SAME | rules/branches.md:23 | word for word |
| 167 | - A task manager or deputy on another machine never derives it again (git user names differ between machines);... | SAME | rules/branches.md:24 | word for word |
| 168 | - It belongs to that person: the sweep never deletes it, nobody else merges into it | SAME | rules/branches.md:25 | word for word |
| 169 | - Other people publish to the production branch meanwhile: it is merged into the working branch at the start o... | SAME | rules/branches.md:26 | word for word |
| 170 | - Batches: tasks given together merge into the working branch; when the last one of the batch is merged, ONE f... | SAME | rules/branches.md:27 | word for word |
| 171 | - A red batch run goes to a new fixer agent, never back to the builder | SAME | rules/branches.md:28 | word for word |
| 172 | - The fixer is a normal task: todo add first, a brief with target, base and both branches, its own PR REVIEW a... | SAME | rules/branches.md:29 | word for word |
| 173 | - Production from the working branch: only on the owner's approval (verified words) and only from a green comm... | SAME | rules/branches.md:30 | word for word |
| 174 | - A repo with a release build runs it right after, so merged to production = published | SAME | rules/branches.md:31 | word for word |
| 175 | - RELEASE RUN: the full suite runs once on the working branch before such a publish (the batch run on that com... | SAME | rules/branches.md:32 | word for word |
| 176 | - Release run failures: `agent-nightly.sh --failures` names, for each failing test, the merge that introduced ... | SAME | rules/branches.md:33 | word for word |
| 177 | - The new fixer agent gets the test, the merge and that task's requirement, and labels each failure | SAME | rules/branches.md:34 | word for word |
| 178 | - "test out of date": update it, cite the requirement line or commit that changed the behaviour on purpose; "r... | SAME | rules/branches.md:35 | word for word |
| 179 | - No check is deleted without a twin; the fixer's report is a table of these labels: test \| merge \| task \| ... | SAME | rules/branches.md:36 | word for word |
| 180 | - RELEASE SMOKE after every release: a fresh session uses the released version for real (start, one subagent l... | SAME | rules/branches.md:37 | word for word |
| 181 | - Four kinds of request, one line each: | SAME | rules/checks.md:47 | word for word |
| 182 | - Refactor (no behaviour change): BUILD + RELATED TESTS; no new examples, the existing tests are the acceptanc... | SAME | rules/checks.md:48 | word for word |
| 183 | - Urgent fix (production is broken): the URGENT FIX path above | SAME | rules/checks.md:49 | BROKEN POINTER: "the URGENT FIX path above" - URGENT FIX is in rules/branches.md:10, not above |
| 184 | - Rollback: back to the last green commit; BUILD + RELATED TESTS of the reverted files; a database change foll... | SAME | rules/checks.md:50 | word for word |
| 185 | - Research only (no diff): no blocks; the report is the deliverable | SAME | rules/checks.md:51 | word for word |
| 186 | - Repo facts live in the committed `agent_repo.conf`, written by init and kept by agents; a human may edit it,... | SAME | rules/checks.md:52 | word for word |
| 187 | - After each bug fix the fixing agent asks "which example would have shown it" and adds one line with `agent-f... | SAME | rules/checks.md:53 | word for word |
| 188 | - Beyond the reviewer's PR REVIEW, a second agent's opinion only for CORE REVIEW, or when someone wants a tool... | SAME | rules/checks.md:54 | word for word |
| 189 | - A requirement table copies its defaults from the released template and lists every changed default for the o... | SAME | skill dispatch:21 | only in the skill; the core has no pointer for writing the requirement doc |
| 193 | W1. Finish in one run | SAME | PRINCIPLES.md:40 | word for word |
| 194 | - Never wait for the human, except: the kick-off round, a mock yes, an OWNER SIGN, NEEDS HUMAN E2E | SAME | PRINCIPLES.md:41 | word for word |
| 195 | - Unknown → pick default, log it, continue | SAME | PRINCIPLES.md:42 | word for word |
| 196 | - Only owner-level or irreversible calls stop the line | SAME | PRINCIPLES.md:42 | word for word |
| 197 | - A rule and reality collide → report the collision, never route around it | SAME | PRINCIPLES.md:43 | word for word |
| 198 | - New ideas → `agent_ideas.txt` (R6), never in the work or the report, except the CLOSE CASE report (W13), whi... | SAME | rules/files.md:33 | word for word |
| 200 | W2. UI | SAME | rules/ui.md:4 | word for word |
| 201 | - Clickable mock first (prototype artifact) | SAME | rules/ui.md:5 | word for word |
| 202 | - Start from a screenshot of the existing real page (Claude in Chrome); change only what the task changes. Nev... | SAME | rules/ui.md:6 | word for word |
| 203 | - No existing page to screenshot → the mock follows the project's current style (theme, components); the agent... | SAME | rules/ui.md:7 | word for word |
| 204 | - Human says yes | SAME | rules/ui.md:8 | word for word |
| 205 | - A mock only for a new page or a whole-page re-layout; the approved mock is what UI CHECK compares with (R8) | SAME | rules/ui.md:9 | word for word |
| 206 | - The approved mock is the acceptance criterion of the task | SAME | rules/ui.md:10 | word for word |
| 207 | - Then real code | SAME | rules/ui.md:11 | word for word |
| 209 | W3. TDD | SAME | rules/tests.md:7 | word for word |
| 210 | - Task manager writes the failing tests → worker writes code → tests pass | SAME | rules/tests.md:8 | word for word |
| 211 | - Workers never write tests. Task managers never write product code | SAME | rules/tests.md:9 | word for word |
| 212 | - No test = not started | SAME | rules/tests.md:10 | word for word |
| 213 | - Full lane only; fast lane → R1 | SAME | rules/tests.md:11 | word for word |
| 215 | W4. Multi-agent tests | SAME | rules/tests.md:13 | word for word |
| 216 | - Tests are organised module → feature | SAME | rules/tests.md:14 | word for word |
| 217 | - No task runs the full suite (owner 1A 2026-11-25) | SAME | rules/checks.md:42 | left out of W4 in rules/tests.md, kept in R8 |
| 218 | - Which tests run follows the blocks (R8): the light RELATED TESTS and GUARD TESTS per task; MODULE TESTS only... | SAME | rules/tests.md:15 | word for word |
| 219 | - Every test run goes through `agent-test-run.sh` (S5) | SAME | rules/tests.md:16 | word for word |
| 220 | - The main manager and the merge deputy never re-run tests the task manager already passed. Only on a merge co... | SAME | rules/tests.md:17 | word for word |
| 221 | - After a bounce: re-run only the tests that failed, not the suite | SAME | rules/tests.md:18 | word for word |
| 223 | W5. Web UI testing | SAME | rules/ui.md:13 | word for word |
| 224 | - Claude in Chrome, not Playwright, on orca and plain | SAME | rules/ui.md:14 | word for word |
| 225 | - The check deputy (`agents/check-deputy.md`) drives the browser for FLOW CHECK, UI CHECK and RELEASE SMOKE, o... | SAME | rules/ui.md:15 | word for word |
| 226 | - Others write the click path and hand it to the main manager, who sends the check deputy | SAME | rules/ui.md:16 | word for word |
| 227 | - Unit tests are not proof of a flow a user can reach: FLOW CHECK is (R8) | SAME | rules/ui.md:17 | word for word |
| 228 | - Builders never verify their own work: they ship a click path, someone who did not build it drives the UI | SAME | PRINCIPLES.md:47 | word for word |
| 229 | - What a browser cannot prove goes on a standing "needs a real device" list, never counted as verified | SAME | rules/ui.md:18 | word for word |
| 230 | - UI CHECK: the real page against the approved mock or the before screenshot, item by item (layout, content, s... | SAME | rules/ui.md:19 | word for word |
| 231 | - A layout, content or behaviour difference = not done, back to the builder | SAME | rules/ui.md:20 | word for word |
| 232 | - A difference from the real UI theme (colours, fonts, spacing tokens) is fine: keep the real theme, list it a... | SAME | rules/ui.md:21 | word for word |
| 233 | - The owner says pass = pass; agents follow his final decision. Only a critical problem (crash, wrong data, se... | SAME | rules/ui.md:22 | word for word |
| 234 | - Ask `agent-runtime.sh browser` first: chrome, headless or none | SAME | rules/ui.md:23 | word for word |
| 235 | - cloud → headless Chromium via Playwright, the extension can never reach a VM | SAME | rules/ui.md:24 | word for word |
| 236 | - none → print the click path under NEEDS HUMAN E2E and stop, wait for the human. Never silent, never forever | SAME | rules/ui.md:25 | word for word |
| 238 | W6. Roles | SAME | rules/roles.md:4 | word for word |
| 239 | - Main manager (the "Main manager model" setting) = the main chat. Assigns tasks, talks to the human, reports,... | SAME | rules/roles.md:5 | word for word |
| 240 | - Fast-lane deputy (the "Helper model" setting) = `agents/fast-lane-deputy.md`, new one per small task: works ... | SAME | rules/roles.md:6 | word for word |
| 241 | - Merge deputy (the "Helper model" setting) = `agents/merge-deputy.md`. Merges, then deletes branch and worktr... | SAME | rules/roles.md:7 | word for word |
| 242 | - Reviewer (Reviewer model, default opus-5.5:high) = `agents/reviewer.md`: PR REVIEW of every task and CORE RE... | SAME | rules/roles.md:8 | word for word |
| 243 | - Check deputy (the "Helper model" setting) = `agents/check-deputy.md`, read and browser tools only: FLOW CHEC... | SAME | rules/roles.md:9 | word for word |
| 244 | - The main manager stays free for the human: it runs no long check itself; it sends the check deputy and gets ... | SAME | rules/roles.md:10 | word for word |
| 245 | - Task manager (the "Task manager model" setting) = one agent per big feature, in its own worktree (exception:... | SAME | rules/roles.md:11 | word for word |
| 246 | - It writes the tests, briefs workers, judges, verifies every worker result before reporting done to the main ... | SAME | rules/roles.md:12 | word for word |
| 247 | - Worker (the "Helper model" setting) = `agents/worker.md`, subagent of a task manager. Writes code until the ... | SAME | rules/roles.md:13 | word for word |
| 248 | - Managers never write product code. A defect goes back to the worker that wrote it, with evidence | SAME | rules/roles.md:14 | word for word |
| 249 | - A main manager fix order to a task manager has a fixed shape: where, what is seen, what is expected, evidenc... | SAME | rules/roles.md:15 | word for word |
| 250 | - Names: `bin/agent-name.sh` (SessionStart hook) shows `<repo> Manager`, `<feature> Task Manager`, `<repo> Hel... | SAME | rules/roles.md:16 | word for word |
| 252 | W7. Big feature (> 2 hours) | SAME | rules/worktrees.md:4 | word for word |
| 253 | - Before opening a worktree: idle or done worktrees > 0 → deputy cleans them all first (W8) | SAME | rules/worktrees.md:5 | word for word |
| 254 | - A worktree needs Orca. `agent-runtime.sh kind` picks the shape | SAME | rules/worktrees.md:6 | word for word |
| 255 | - On Orca: read Orca's own guide first, `orca skills get --topic orca-cli --full --json`. Flags change: `orca ... | SAME | rules/worktrees.md:7 | word for word |
| 256 | - Then new worktree | SAME | rules/worktrees.md:8 | word for word |
| 257 | - One task manager inside it | SAME | rules/worktrees.md:9 | word for word |
| 258 | - Task manager spawns workers as needed | SAME | rules/worktrees.md:10 | word for word |
| 259 | - plain or cloud → no worktree, no second terminal. Main manager runs the task itself with `Agent` subagents, ... | SAME | rules/worktrees.md:11 | word for word |
| 260 | - Placement: every job goes to a connected machine first (the one with the most room by S3); the local machine... | SAME | rules/worktrees.md:12 | word for word |
| 261 | - The automatic nightly starts only where there is room, else it says so; the main manager places a nightly by... | SAME | rules/worktrees.md:13 | word for word |
| 262 | - While a connected machine exists the automatic nightly never runs the full suite locally; it says so and the... | SAME | rules/worktrees.md:14 | word for word |
| 263 | - One agent = one worktree = one branch = one terminal. Push at every stage | SAME | rules/worktrees.md:15 | word for word |
| 265 | W8. Merge and cleanup | SAME | rules/worktrees.md:17 | word for word |
| 266 | - The merge deputy merges into the working branch (ap-main-<name>) in the main checkout | SAME | rules/worktrees.md:18 | word for word |
| 267 | - A task with target production goes straight in through `agent-promote.sh --task`: a short-lived worktree of ... | SAME | rules/worktrees.md:19 | word for word |
| 268 | - After any direct merge into production, production is merged back into the working branch at once, so they n... | SAME | rules/worktrees.md:20 | word for word |
| 269 | - The merge deputy runs `agent-file.sh checks gate <task>` first: GATE REFUSED → no merge, the task goes back | SAME | rules/worktrees.md:21 | word for word |
| 270 | - Deputy deletes the branch (local + remote) and the worktree right after merge | SAME | rules/worktrees.md:22 | word for word |
| 271 | - Never `git reset --hard` in the main checkout: it wipes the uncommitted agent_*.txt | SAME | PRINCIPLES.md:50 | word for word |
| 272 | - Every merge ends with cleanup, in every case: a task manager pane, a subagent's git worktree, a human-direct... | SAME | rules/worktrees.md:23 | word for word |
| 273 | - The worktree line of a merged task is always removed or rewritten at merge, also when the folder stays | SAME | rules/worktrees.md:24 | word for word |
| 274 | - human-direct protects only the human's own session pane; the sweep never closes a Claude pane, only a shell ... | SAME | rules/worktrees.md:25 | word for word |
| 275 | - The sweep prunes a LAUNCH record whose pid is dead or whose pane is gone; its table never lists main or the ... | SAME | rules/worktrees.md:26 | word for word |
| 276 | - The plain list shows what --apply would remove; --apply is main manager only | SAME | rules/worktrees.md:27 | word for word |
| 277 | - Whatever is sent to another machine is cleaned up there when it is done: pane, worktree, branches, scratch c... | SAME | rules/worktrees.md:28 | word for word |
| 278 | - The sweep covers every connected machine and its list names what is left there | SAME | rules/worktrees.md:29 | word for word |
| 279 | - Never skip cleanup | SAME | rules/worktrees.md:30 | word for word |
| 280 | - Main manager verified + waiting for the owner's yes → agent-file.sh checks gather first, close the task mana... | SAME | rules/worktrees.md:31 | word for word |
| 281 | - Owner yes → merge deputy merges the branch. Owner no → a new task manager from that branch. Goal: work all n... | SAME | rules/worktrees.md:32 | word for word |
| 282 | - Delete the branch and close the todo line only after the merge is verified | SAME | rules/worktrees.md:33 | word for word |
| 283 | - Meanwhile the pane and the worktree may go while waiting for the owner's yes; the pushed branch stays | SAME | rules/worktrees.md:34 | word for word |
| 284 | - Deputy runs `bin/agent-file.sh worktree rm <path>` and `bin/agent-file.sh todo done <name>` with the facts f... | SAME | rules/worktrees.md:35 | word for word |
| 285 | - Sweep: `bin/agent-cleanup.sh --apply` after every merge, at session start and when the last open task closes... | SAME | rules/worktrees.md:36 | word for word |
| 286 | - Housekeep: every housekeep_interval_min minutes (default 120, 0 = off) `agent-watch.sh --all` runs `bin/agen... | SAME | rules/worktrees.md:37 | word for word |
| 287 | - The housekeep pass runs `agent-file.sh state trim` on the main repo's agent_state.txt before it writes its b... | SAME | rules/worktrees.md:38 | word for word |
| 288 | - The main manager reads the HOUSEKEEP block in agent_state.txt at its next activity. Per suspect: `idea rm <n... | SAME | rules/worktrees.md:39 | word for word |
| 289 | - It then acts on the other flags of the block | SAME | rules/worktrees.md:40 | word for word |
| 290 | - Main manager only. Task managers, Helpers and workers never run it | SAME | rules/worktrees.md:41 | word for word |
| 291 | - Own repo only: this machine and every paired Orca machine | SAME | rules/worktrees.md:42 | word for word |
| 292 | - Removes only safe items: merged into the working branch or the production branch (origin/main here), no live... | SAME | rules/worktrees.md:43 | word for word |
| 293 | - Everything else is never deleted: one table to the human (what, where, why kept, suggestion) | SAME | rules/worktrees.md:44 | word for word |
| 294 | - A done pane (finished, idle) in a kept worktree: closed when its task is done or dropped, or its line is gon... | SAME | rules/worktrees.md:45 | word for word |
| 295 | - A paired machine unreachable → one line, skipped. Never hangs the start | SAME | rules/worktrees.md:46 | word for word |
| 297 | W9. Task routing (main manager, before every dispatch) | ONLY PROPOSED | proposed-skill-changes.md:6 | W9 anchor; the skill title already says W9 |
| 298 | - Read `agent_worktree.txt` first | REWORDED-OK | skill dispatch:11 (`agent-file.sh show` prints all four files) + rules/files.md:38 |  |
| 299 | - Small task (fast lane) → a new deputy subagent in its own git worktree (Agent isolation worktree); it pushes... | SAME | skill dispatch:31 |  |
| 300 | - Several small tasks run side by side and never share a checkout (owner 1A 2026-11-25; 21 tasks done this way... | ONLY PROPOSED | proposed-skill-changes.md:12 | "never share a checkout" is implied by "its own git worktree" (dispatch:31) |
| 301 | - A new task gets its own branch and its own agent, also when it touches a live worktree's module in a differe... | SAME | PRINCIPLES.md:10 + skill dispatch:32 |  |
| 302 | - A follow-up on the logic a live task manager is changing right now must go to that task manager (P1), never ... | SAME | PRINCIPLES.md:11 + skill dispatch:32 |  |
| 303 | - Task manager in final stage (compiling worker results) → do not disturb. Hold the task until it finishes | REWORDED-OK | skill dispatch:32 | "Status final -> hold it, tell the human" |
| 304 | - Otherwise → new worktree (W7). Never an Orca worktree and a task manager for a small task | ONLY PROPOSED | proposed-skill-changes.md:15 | implied by PRINCIPLES.md:35 |
| 305 | - `todo done <X>` releases every task queued after X | ONLY PROPOSED | proposed-skill-changes.md:18 | tool behaviour; no agent step lost |
| 306 | - The main manager runs `agent-file.sh next` at every wake (a report, a watch signal, a human message) and dis... | REWORDED-OK | skill dispatch:11,35 |  |
| 307 | - A task waits only for a real dependency: it needs code that another open task brings (shared first, below) | SAME | skill dispatch:33 |  |
| 308 | - A task the owner already approved needs no new question | SAME | skill dispatch:11 |  |
| 309 | - A new worktree or pane goes to the connected machine first that has room (W7, S3) | SAME | skill dispatch:35 + rules/worktrees.md:12 |  |
| 310 | - Target and base (R1; his words by the approval cases of R8): a task that goes straight to production branche... | REWORDED-OK | skill dispatch:23 | "(it sees the batch's earlier merges)" dropped |
| 311 | - The target is per task, not per request: an urgent task branches from the production branch and merges strai... | ONLY PROPOSED | proposed-skill-changes.md:21 | parts in rules/branches.md:10-12,27 and dispatch:23 ("per task") |
| 312 | - Before dispatch: does an urgent task need code that only a non-urgent one brings? Yes -> it cannot ship alon... | WEAKER | skill dispatch:23 | the two options "(ship them together, or move that part into the urgent task)" are gone |
| 313 | - A new request may also wait until the working branch is tested and published; the main manager picks what is... | REWORDED-OK | skill dispatch:23 | "say which is faster" |
| 314 | - Shared first: before parallel features, find the code they share (models, components, APIs); the shared part... | SAME | skill dispatch:27 |  |
| 315 | - The todo line comes first: `todo add` before the worktree, the pane or any agent. The guard refuses a main m... | REWORDED-OK | skill dispatch:31,81 |  |
| 317 | W10. Second session in the same repo | SAME | rules/roles.md:18 | word for word |
| 318 | - One main manager per repo. `agent-start.sh` keeps a lock in the shared git dir: pid, date, session id, termi... | SAME | rules/roles.md:19 | word for word |
| 319 | - Lock owner alive → this session is a task manager (human-direct). Never a second main manager | SAME | rules/roles.md:20 | word for word |
| 320 | - Its start text names the main manager: pid, `<repo> Manager`, terminal | SAME | rules/roles.md:21 | word for word |
| 321 | - Human wants this session as main manager → the human types `! agent-start.sh --take-over` (full path in the ... | SAME | rules/roles.md:22 | word for word |
| 322 | - Human-direct = only a session the human opened by hand. Agent-spawned agents are never human-direct. They ru... | SAME | rules/roles.md:23 | word for word |
| 323 | - A human-direct session keeps its protection only while the human alone drives it. Once it takes a task from ... | SAME | rules/roles.md:24 | word for word |
| 324 | - The merge of its last open task closes its pane and removes its line, like a task manager; the close message... | SAME | rules/roles.md:25 | word for word |
| 325 | - At start: the script adds a line to `agent_worktree.txt` (status human-direct). Also send the main manager a... | SAME | rules/roles.md:26 | word for word |
| 326 | - Will change files → open its own worktree first (W7). Only looking → no worktree | SAME | rules/roles.md:27 | word for word |
| 327 | - Human talks to it directly for now. All task manager rules still apply | SAME | rules/roles.md:28 | word for word |
| 328 | - Human says "finish" or "report to main manager" → report done + click path to the main manager, then act as ... | SAME | rules/roles.md:29 | word for word |
| 329 | - Finished with nothing to merge → main manager runs `bin/agent-file.sh worktree rm <path>` | SAME | rules/roles.md:30 | word for word |
| 330 | - The main manager closes every human-direct session after the human says finish: `orca terminal close --termi... | SAME | rules/roles.md:31 | word for word |
| 331 | - Lock owner dead → take over as main manager, run recovery (S7) | SAME | rules/roles.md:32 | word for word |
| 332 | - Talk between sessions: `ListAgents` → find the peer by its name (W6), not listed → the row named after its f... | SAME | rules/roles.md:33 | word for word |
| 333 | - Open a second session with the same permission mode and effort as the main manager (`<mode>` from `agent-set... | SAME | rules/roles.md:34 | word for word |
| 334 | - New terminals (dispatch, resume, a Helper, a city click) use the "Permissions: Permission mode" setting, rea... | SAME | rules/roles.md:35 | word for word |
| 335 | - Task name: every new or switched task, a plain question too, gets its name first, even before the quiz PASS ... | SAME | rules/roles.md:36 | word for word |
| 337 | W11. Time | SAME | rules/time.md:4 | word for word |
| 338 | - Every task gets an estimate in minutes before dispatch, on its todo line | SAME | rules/time.md:5 | word for word |
| 339 | - Write your own guess in minutes first, then `estimate ... --guess <m>`; est and guess both go on the todo li... | SAME | rules/time.md:6 | word for word |
| 340 | - Estimate = agent work only. Waiting is not work: mock gate, owner question, owner review, hold, suite run | SAME | rules/time.md:7 | word for word |
| 341 | - Every done report has one line: `TIME: est <n>m, actual <n>m, wait <n>m`. Actual = agent work only | SAME | rules/time.md:8 | word for word |
| 342 | - Done = merged and cleaned. The main manager passes work, wait and the task facts to `bin/agent-file.sh todo ... | SAME | rules/time.md:9 | word for word |
| 343 | - Work over 2× estimate → say it in the report, never silent | SAME | rules/time.md:10 | word for word |
| 344 | - Time comes from `date`, never guessed (a remote machine's clock can drift) | SAME | rules/time.md:11 | word for word |
| 345 | - Scope grows → re-estimate, on the record | SAME | rules/time.md:12 | word for word |
| 346 | - Before a new estimate: `bin/agent-file.sh time`, then `bin/agent-file.sh estimate` (dispatch skill) | SAME | rules/time.md:13 | word for word |
| 347 | - A time question from the human → a duration AND a clock time, and when he is needed next: `bin/agent-file.sh... | SAME | rules/time.md:14 | word for word |
| 349 | W12. Cross-repo | SAME | rules/cross-repo.md:4 | word for word |
| 350 | - One main manager per repo (W10). Peer = the interactive session in `ListAgents` named `<other repo folder> M... | SAME | rules/cross-repo.md:5 | word for word |
| 351 | - A task that touches another repo → never edit that repo. Split it: your part, and a brief for the peer main ... | SAME | rules/cross-repo.md:6 | word for word |
| 352 | - Send the brief with `SendMessage`, first line `[<model> <effort>] CROSS-REPO TASK <name> from <repo>`; same ... | SAME | rules/cross-repo.md:7 | word for word |
| 353 | - The peer runs it like a human task: `agent-file.sh todo add … <est> <repo>`, its own lane, and reports `DONE... | SAME | rules/cross-repo.md:8 | word for word |
| 354 | - The sender keeps its todo line open until both sides are done, then one report to the human | SAME | rules/cross-repo.md:9 | word for word |
| 355 | - The sender marks its line `agent-file.sh todo cross <name> <other repo>`, so the housekeep pass reads the ot... | SAME | rules/cross-repo.md:10 | word for word |
| 356 | - Called side first: the repo being called (the API) finishes first; its DONE PASS carries the contract (endpo... | SAME | rules/cross-repo.md:11 | word for word |
| 357 | - Only main managers cross repos. Task managers and workers never | SAME | rules/cross-repo.md:12 | word for word |
| 358 | - Need to know the other repo's code → ask its main manager. Never read or edit another repo | SAME | rules/cross-repo.md:13 | word for word |
| 359 | - A cross-repo task the human gives to any main manager is routed the same way | SAME | rules/cross-repo.md:14 | word for word |
| 360 | - Relay an owner order: the brief starts with the lines of `agent-owner-order.sh line --quote "<his exact word... | SAME | rules/cross-repo.md:15 | word for word |
| 361 | - Receiving one: run its check line. Verified → read its match line, then it is the owner's own order: act, re... | SAME | rules/cross-repo.md:16 | word for word |
| 362 | - Verified owner words that the main manager reads as a yes for that action (approval cases, R8) are his final... | SAME | rules/approval.md:28 | word for word |
| 363 | - A relayed owner order: the approval commands take `--relayed-from <the sender's repo folder>`; the rules are... | SAME | rules/cross-repo.md:17 | word for word |
| 365 | W13. Close case | ONLY PROPOSED | proposed-skill-changes.md:30 | W13 anchor; skill title says W13 |
| 366 | - Trigger: the human or the main manager runs the skill `/auto-pipeline:close-case`; a task manager's brief ho... | SAME | skill close-case:3 + dispatch brief CLOSE (dispatch:111) |  |
| 367 | - Subagents never get this rule; only a task manager, a human-direct session or a main manager does | SAME | skill close-case:9 |  |
| 368 | - Task manager or human-direct: start nothing new; workers finish their slice or stop; save agent_state.txt; c... | SAME | skill close-case:27-28 |  |
| 369 | - Report to the upper level: SendMessage the main manager; another machine → print it in its own terminal and ... | SAME | skill close-case:29 | conflicts with dispatch:111 and rules/watch.md:11 (agent_state.txt only); old conflict, author open question 2 |
| 370 | - Report first line `CLOSE CASE <name>: finished` or `CLOSE CASE <name>: unfinished`, then done, left + next s... | SAME | skill close-case:29 |  |
| 371 | - Then wait for the upper decision. Never close itself. A close case from the main manager counts the same as ... | REWORDED-OK | skill close-case:3,30 | "counts the same as from the human": only proposed (proposed-skill-changes.md:33), but the skill description already names both triggers |
| 372 | - Main manager gets a CLOSE CASE report: finished → merge skill. Unfinished → review, then finish first (DONE,... | SAME | skill close-case:15-22 |  |
| 373 | - Log every decision in its agent_state.txt. Human away → decide by the requirement doc, mark it "owner not se... | SAME | skill close-case:23 |  |
| 374 | - Main manager gets close case from the human = the whole repo: close case to every live task manager and huma... | SAME | skill close-case:34 |  |
| 375 | - Collect every report, decide each, merge what passes, close all panes and worktrees, stop its own crons, upd... | REWORDED-CHANGED | skill close-case:35-37 | "update the agent files" -> "agent-file.sh show to check the agent files" |
| 376 | - Then one final table to the human: task, result, what changed, what is left, decisions taken for the human. ... | REWORDED-OK | skill close-case:38 | "(the H3 five-row cap does not apply)" only proposed; "Every task one row, nothing dropped" carries it |
| 377 | - After the table the main manager asks the human, in his language: clean this session for the next round, yes... | SAME | skill close-case:39 |  |
| 378 | - Yes: `agent-start.sh --clean` (archives agent_state.txt, writes a short fresh one, says what still runs), th... | SAME | skill close-case:40 |  |
| 379 | - Rare, the human wants this session to stop being main manager: he types `! agent-start.sh --release`; the ag... | ONLY PROPOSED | skill close-case:41 + proposed-skill-changes.md:39 | "The next new session is main manager, never Helper" only proposed; the rest is in part B 8 |
| 381 | W14. Todo board | ONLY PROPOSED | proposed-skill-changes.md:43 | W14 anchor; skill title says W14 |
| 382 | - Trigger: the human runs the skill `/auto-pipeline:todo`; the skill holds this rule per role | SAME | skill todo:3 |  |
| 383 | - One script, no agent: `bin/agent-file.sh board`. Show its table as printed, every row, then the decide secti... | SAME | skill todo:12-15 |  |
| 384 | - Main manager: the whole repo. Task manager or Helper: `board --self`, its own task and its workers only. Sub... | SAME | skill todo:7-11 |  |
| 385 | - Rows: open tasks, waits on the owner (mock check, owner question, owner review), `OWNER TODO:` and `PARKED:`... | ONLY PROPOSED | proposed-skill-changes.md:46-49 | describes the script output (the agent shows it as printed) |
| 386 | - Status of a wait: `waiting <who> · <what> · waited <n>`, held `hold · <what> · waited <n>`, queued `queue · ... | ONLY PROPOSED | proposed-skill-changes.md:46-49 | describes the script output (the agent shows it as printed) |
| 387 | - Sort: waiting on the owner, running, waiting on others, queued and not started, held, OWNER TODO, parked que... | ONLY PROPOSED | proposed-skill-changes.md:46-49 | describes the script output (the agent shows it as printed) |
| 388 | - Times come from the files, never guessed. Work counts from the first stage minus later waits. Waited: since ... | ONLY PROPOSED | proposed-skill-changes.md:46-49 | describes the script output (the agent shows it as printed) |
| 389 | - Progress: `agent-file.sh todo stage <name> <stage> [i/m]` at each step boundary. | SAME | skill dispatch:98 |  |
| 390 | - Stages, task manager: brief register mock tests workers verify push report. Main manager: e2e (the review an... | SAME | skill dispatch:99-107 + skill merge:11,16 |  |
| 391 | - Stage weights are fixed (`bin/agent_conf.py`) | ONLY PROPOSED | proposed-skill-changes.md:50-51 | script output / statusline |
| 392 | - Live: `board --watch` · `statusline` on or off, 5 lines at most (a warning line counts), queued/held/not sta... | ONLY PROPOSED | proposed-skill-changes.md:50-51 | script output / statusline |
| 393 | - Record as it happens: `todo wait <name> on <kind> ["<note>"] [--who <name>] [--after <task>]\|off` at every ... | SAME | skill dispatch:74-80,43 |  |
| 394 | - `park add` for a parked question (H1); `OWNER TODO:` lines are written with `agent-file.sh state add` | REWORDED-OK | skill dispatch:82 + rules/approval.md:14 | OWNER TODO via state add: approval.md:14 case only; the dispatch clause is proposed |
| 395 | - `agent-guard.sh` records launches by task. The "Rules: Todo before agent" setting, on (default), refuses a m... | SAME | skill dispatch:81 + rules/map.md:35 |  |
| 396 | - `worker on`: no hooks only. | SAME | skill dispatch:104 |  |
| 398 | W15. Watch | SAME | rules/watch.md:4 | word for word |
| 399 | - After a watch wake the first action is to start the watch again, then handle the signal | SAME | rules/watch.md:5 | word for word |
| 400 | - The watch also wakes the main manager when there is room for a queued task (WATCH ROOM) | SAME | rules/watch.md:6 | word for word |
| 401 | - A board warning (watch not running, not confirmed, a pane without a task line) reaches the main manager thro... | SAME | rules/watch.md:7 | word for word |
| 402 | - Stall detection is the watch: each sweep reads the pane screen and the `agent_state.txt` file; 3 sweeps with... | SAME | rules/watch.md:8 | word for word |
| 403 | - Verify every launch within 2 min | SAME | rules/watch.md:9 | word for word |
| 404 | - One `agent-watch.sh --all` in the background (Bash run_in_background) watches every task manager, local and ... | SAME | rules/watch.md:10 | word for word |
| 405 | - A task manager's HEARTBEAT, ACK, report and question go into `agent_state.txt` only, never SendMessage; only... | SAME | rules/watch.md:11 | word for word |
| 406 | - DONE FAIL → the main manager reviews the report, then sends the task manager a fix order (where, what is see... | SAME | rules/watch.md:12 | word for word |
| 407 | - LOST (the watch cannot reach a machine or a pane) → wait one more sweep; still lost → tell the owner in one ... | SAME | rules/watch.md:13 | word for word |
| 408 | - Never redispatch a LOST task on another machine by itself | SAME | rules/watch.md:14 | word for word |
| 409 | - The watch carries a task's stage to the main repo from the newest STAGE line or HEARTBEAT step (0-7 = brief ... | SAME | rules/watch.md:15 | word for word |
| 410 | - A manager at its idle prompt while its own background run goes (pane shows shells or monitors, or its newest... | SAME | rules/watch.md:16 | word for word |
| 411 | - Long text to a task manager: `agent-file.sh tell <task> "<msg>"` (the block goes into its file, one pointer ... | SAME | rules/watch.md:17 | word for word |
| 412 | - Start and resume print the `agent-watch.sh --all` command when no watch runs | SAME | rules/watch.md:18 | word for word |
| 413 | - The board says `not confirmed <n>m` when a task is not watched or has been quiet | SAME | rules/watch.md:19 | word for word |
| 414 | - A stall → nudge once, wait 10 min, then salvage (commit what is there) and redispatch | SAME | rules/watch.md:20 | word for word |
| 415 | - Every brief says how to report, how to ask, how to report done (pass/fail) and the heartbeat | SAME | rules/watch.md:21 | word for word |
| 417 | W16. Known traps | SAME | rules/traps.md:4 | word for word |
| 418 | - A push to the working branch denied by the auto-mode classifier → never retry or work around | SAME | rules/traps.md:5 | word for word |
| 419 | - Hand the owner one `! git push ...` line, or ask for an allow rule (init prints `Bash(git push origin <worki... | SAME | rules/traps.md:6 | word for word |
| 420 | - A cross-session message held because permission modes differ → say so, ask the owner to click Deliver, never... | SAME | rules/traps.md:7 | word for word |
| 421 | - MODE MISMATCH line at start (this session's mode differs from the Permission mode setting) → tell the owner ... | SAME | rules/traps.md:8 | word for word |
| 422 | - Remote Orca pane: a long `terminal send` (~4 KB) arrives cut → write the brief into the worktree's `agent_st... | SAME | rules/traps.md:9 | word for word |
| 423 | - Find another agent's pane with `orca worktree ps --json`, never by its title (titles are often from an old t... | SAME | rules/traps.md:10 | word for word |
| 424 | - `terminal read` shows only the visible screen → use `--cursor` | SAME | rules/traps.md:11 | word for word |
| 425 | - Linux outside Orca: bare `orca` is the screen reader → use `orca-ide` | SAME | rules/traps.md:12 | word for word |
| 426 | - A send while the target is mid-turn can be lost → re-read and resend | SAME | rules/traps.md:13 | word for word |
| 427 | - Screen locked → the Chrome extension tab is hidden → use headless Chrome and tell the owner | SAME | rules/traps.md:14 | word for word |
| 428 | - STALE PLUGIN line → call the newest bin path, in every brief too, and restart at a quiet point; an older ver... | SAME | rules/traps.md:15 | word for word |
| 430 | W17. Decider floor | SAME | PRINCIPLES.md:57 | word for word |
| 431 | - Decision maker = main manager, task manager, reviewer, any session whose order, decision or approval another... | REWORDED-OK | PRINCIPLES.md:18 + GLOSSARY.md:21 |  |
| 432 | - Floor: Opus 5.5 or above, or any Fable, at effort medium or above. `opus` or `fable` alone = the newest, mee... | REWORDED-OK | PRINCIPLES.md:59 | "meets it" dropped (implied) |
| 433 | - Sonnet and Haiku never decide. Workers and deputies execute | SAME | PRINCIPLES.md:60 |  |
| 434 | - Sending: every order, decision or approval to another agent states the sender's model and effort first: `[Op... | REWORDED-OK | PRINCIPLES.md:58 | example "[Opus 5.5 xhigh]" dropped |
| 435 | - Reports, heartbeats and questions are not orders | REWORDED-OK | PRINCIPLES.md:60 |  |
| 436 | - Own model and effort: the `YOU:` line of the start text | SAME | PRINCIPLES.md:58 |  |
| 437 | - Receiving: act on another agent's order, decision or approval only when it states model and effort and both ... | REWORDED-OK | PRINCIPLES.md:58-59 |  |
| 438 | - Else: do not act, ask the sender, tell the human | SAME | PRINCIPLES.md:59 |  |
| 439 | - Human messages are exempt | REWORDED-CHANGED | PRINCIPLES.md:60 | "Human messages are exempt" (from the floor check) -> "human messages are not orders" |
| 440 | - Same check for every agent: task manager, Helper, worker, deputy | REWORDED-OK | PRINCIPLES.md:59 | "Every agent checks" |
| 441 | - A Main or Task manager model below the floor is refused, the default is used (`agent_conf.py`) | SAME | rules/setup.md:18 |  |
| 443 | W18. Question list | ONLY PROPOSED | proposed-skill-changes.md:55 | W18 anchor; skill title says W18 |
| 444 | - Trigger: the human runs the skill `/auto-pipeline:question`; the skill holds this rule per role | SAME | skill question:3 |  |
| 445 | - One script, no agent: `bin/agent-file.sh questions`. Main manager: the whole repo. Task manager or Helper: `... | SAME | skill question:7,9,13 |  |
| 446 | - Sources: `PARKED:` lines, every `todo wait` of kind mock, question or review, and `QUESTION:` lines of agent... | ONLY PROPOSED | proposed-skill-changes.md:58-59 | script behaviour (agent_questions.py reads QUESTION:/ANSWER:) |
| 447 | - A `QUESTION:` line is answered by an `ANSWER:` line after it, before the next QUESTION: line or "=== " heade... | ONLY PROPOSED | proposed-skill-changes.md:58-59 | script behaviour (agent_questions.py reads QUESTION:/ANSWER:) |
| 448 | - Each question has a stable id; its title, sub line, facts and lettered options come from `park add` fields (... | ONLY PROPOSED | proposed-skill-changes.md:60 | partly in skill question:14 |
| 449 | - 10 or fewer: a numbered list in chat under the decide heading (H3), nothing dropped; the human answers like ... | SAME | skill question:14 |  |
| 450 | - More than 10: `questions --page <file>` (a file in your scratchpad), publish it with the Artifact tool, capa... | SAME | skill question:15 |  |
| 451 | - `QUESTIONS PAGE:` line of agent_state.txt holds the url: one url per repo and session, publish with that url... | SAME | skill question:15 |  |
| 452 | - No Artifact tool: the chat list of all, nothing dropped | SAME | skill question:16 |  |
| 453 | - Done: the human says 答完了, done or answered (or pastes `1A 2B`) while the page still has an open question. Th... | SAME | skill question:20 |  |
| 454 | - Read all answers at once with ArtifactData (list, the answers collection) and the map file; pasted lines go ... | SAME | skill question:22-23 |  |
| 455 | - Per answered question: `questions answer <id> "<answer>"`, then carry on. An unpicked question is still open | SAME | skill question:24 |  |
| 456 | - Headers and words in the Language setting | SAME | skill question:7 |  |
| 460 | H1. One topic | SAME | rules/human.md:4 | word for word |
| 461 | - Ask only about the current task | SAME | rules/human.md:5 | word for word |
| 462 | - Edge-case question + read access to the real data → count first: how many records or companies it touches. R... | SAME | rules/human.md:6 | word for word |
| 463 | - Count is 0 or tiny → take the simplest default, state the count in one line, do not ask | SAME | rules/human.md:7 | word for word |
| 464 | - No read access → ask as before, say the count could not be checked. Never guess a count | SAME | rules/human.md:8 | word for word |
| 465 | - Prefer the simplest change that gives the same result over machinery the data does not need | SAME | rules/human.md:9 | word for word |
| 466 | - Park other questions | SAME | rules/human.md:10 | word for word |
| 467 | - Show them at the end, one table | SAME | rules/human.md:11 | word for word |
| 468 | - Ask everything while the human is here, in one batch | SAME | rules/human.md:12 | word for word |
| 469 | - Human gone → never block, park it. On return lead with one table: issue, evidence, blocks what, interim defa... | SAME | rules/human.md:13 | word for word |
| 471 | H2. Words | SAME | rules/human.md:15 | word for word |
| 472 | - Short sentences | SAME | rules/human.md:16 | word for word |
| 473 | - Common words | SAME | rules/human.md:17 | word for word |
| 474 | - Jargon only for code names | SAME | rules/human.md:18 | word for word |
| 475 | - Talk to the human in the language of the Language setting. Docs, code and rule text stay English | SAME | rules/human.md:19 | word for word |
| 476 | - Never cite a rule by its code (W6, S8) to the human. Say what the rule means in plain words | SAME | rules/human.md:20 | word for word |
| 478 | H3. Report | SAME | rules/human.md:22 | word for word |
| 479 | - Result (pass/fail) | SAME | rules/human.md:23 | word for word |
| 480 | - What changed | SAME | rules/human.md:24 | word for word |
| 481 | - Every report, job summary, recap, proposal or audit to the human ends with a decide section | SAME | rules/human.md:25 | word for word |
| 482 | - Heading in the Language setting: zh `## 要你决定`, en `## To decide`, other languages a short translation of "to... | SAME | rules/human.md:26 | word for word |
| 483 | - Open questions numbered, each with a recommendation (zh `建议`, en `Recommendation`) | SAME | rules/human.md:27 | word for word |
| 484 | - Every question to the owner has a number in front; numbers never repeat within one message, and an open ques... | SAME | rules/human.md:28 | word for word |
| 485 | - When every question is answered, the next new set starts again at 1. While any is open, open ones keep their... | SAME | rules/human.md:29 | word for word |
| 486 | - Every open question is repeated in the decide section of every reply until the owner answers it, even when t... | SAME | rules/human.md:30 | word for word |
| 487 | - Each question stands alone: a reader who sees only that line knows what it is about and can decide | SAME | rules/human.md:31 | word for word |
| 488 | - A named thing (PR, task, branch, ticket, file) gets what it is in a few words: `#305 (stock lock settings pa... | SAME | rules/human.md:32 | word for word |
| 489 | - A question names every task/PR/ticket by id AND its title, + the state + what is asked, e.g. "Task t10211 - ... | SAME | rules/human.md:33 | word for word |
| 490 | - Per question: what, why it needs the human now, one line of evidence, then the recommendation. One or two li... | SAME | rules/human.md:34 | word for word |
| 491 | - Nothing open: keep the heading, one line: none (zh `无`) | SAME | rules/human.md:35 | word for word |
| 492 | - Every question the main manager puts to the owner in a decide section is recorded with `park add` (--why --e... | SAME | rules/human.md:36 | word for word |
| 493 | - Few numbers. One table at most, five rows or fewer, unless the human asks for the full list | SAME | rules/human.md:37 | word for word |
| 494 | - Nothing else, except the decide section | SAME | rules/human.md:38 | word for word |
| 496 | H4. Tables | SAME | rules/human.md:40 | word for word |
| 497 | - Comparison, series, feature list, task list, options → table | SAME | rules/human.md:41 | word for word |
| 498 | - Never prose | SAME | rules/human.md:42 | word for word |
| 502 | S1. Settings | SAME | rules/setup.md:4 | word for word |
| 503 | - Settings live only in /plugin -> Installed -> auto-pipeline -> Configure, user level (Claude Code keeps them... | SAME | rules/setup.md:5 | word for word |
| 504 | - Why: the plugin is a developer workflow, one setup for every repo | SAME | rules/setup.md:6 | word for word |
| 505 | - Configure holds the 17 settings | SAME | rules/setup.md:7 | word for word |
| 506 | - Repo facts (core paths, guard tests, test commands, edges, real-data access) live in the committed `agent_re... | SAME | rules/setup.md:8 | word for word |
| 507 | - New terminals use the "Permissions: Permission mode" setting, default bypassPermissions | SAME | rules/setup.md:9 | word for word |
| 508 | - `/auto-pipeline:settings` shows them as a table and never changes them | SAME | rules/setup.md:10 | word for word |
| 509 | - No settings file in a repo, none on a machine: start and init move an old repo or machine settings file into... | SAME | rules/setup.md:11 | word for word |
| 510 | - A cloud session (no plugin) runs the defaults | SAME | rules/setup.md:12 | word for word |
| 511 | - Also holds the watch and housekeep config (`housekeep_interval_min`) | SAME | rules/setup.md:13 | word for word |
| 512 | - Setup: init offers to merge the permission rules into `.claude/settings.json` (`agent-init.sh --add-permissi... | SAME | rules/setup.md:14 | word for word |
| 513 | - Setup: init asks all vs selected repos; `agent-init.sh --scope` writes the files; agents never hand-edit JSO... | SAME | rules/setup.md:15 | word for word |
| 515 | S2. Resume script | SAME | rules/context.md:4 | word for word |
| 516 | - One command | SAME | rules/context.md:5 | word for word |
| 517 | - Loads context, memory, agents, saved sessions (S7), and prints the watch command when no watch runs | SAME | rules/context.md:6 | word for word |
| 519 | S3. Resource guard | SAME | rules/resources.md:4 | word for word |
| 520 | - A run (a test command, a build, a new agent pane) starts when memory in use now + the memory this run is kno... | SAME | rules/resources.md:5 | word for word |
| 521 | - Known to need = the measured peak MB; a Claude pane counts too (about 300-550 MB; 550 MB while never measure... | SAME | rules/resources.md:6 | word for word |
| 522 | - A run that was never measured is not held back: it starts at once with a monitor on its memory; the monitor ... | SAME | rules/resources.md:7 | word for word |
| 523 | - Over the limit the monitor stops the newest, unmeasured one first, records its peak MB, and the run is tried... | SAME | rules/resources.md:8 | word for word |
| 524 | - CPU: a parallel test runner uses as many processes as keep CPU under the same limit (`{workers}`); memory is... | SAME | rules/resources.md:9 | word for word |
| 526 | S4. Usage cap | SAME | rules/resources.md:11 | word for word |
| 527 | - Over the limit: start nothing new; close done and idle panes first; stop test runs before anything else (`ag... | SAME | rules/resources.md:12 | word for word |
| 528 | - A working agent is left alone: never stop a working agent, tell the main manager instead, one line: which ma... | SAME | rules/resources.md:13 | word for word |
| 529 | - relief stops only what the pipeline owns: `agent-watch.sh --all` processes left by tests, watches of repos w... | SAME | rules/resources.md:14 | word for word |
| 530 | - The sweep (W8) runs `agent-resources.sh stop-leftovers`: this repo's orphan watch and finished test watches ... | SAME | rules/resources.md:15 | word for word |
| 531 | - A task manager over cap parks: commit, write state, set idle; the main manager closes its pane; resume bring... | SAME | rules/resources.md:16 | word for word |
| 532 | - The human's apps, other repos' sessions, Gradle or node runners: never killed by an agent. One table to the ... | SAME | rules/resources.md:17 | word for word |
| 533 | - Setting "Load: Max memory %" = 80 | SAME | rules/resources.md:18 | word for word |
| 535 | S5. Test runs | SAME | rules/tests.md:20 | word for word |
| 536 | - Every test run goes through `agent-test-run.sh`: it reserves its measured peak MB while it runs, and the mon... | SAME | rules/tests.md:21 | word for word |
| 537 | - One small shared reservation list per machine (every running job: pid, reserved MB; a dead pid frees its ent... | SAME | rules/tests.md:22 | word for word |
| 538 | - Measured weights live per machine (`agent_test_weights.json` in the git common dir); `agent_repo.conf` `weig... | SAME | rules/tests.md:23 | word for word |
| 539 | - Every test run caps its own parallelism, e.g. `jest --maxWorkers=2`, `flutter test -j 2` | SAME | rules/tests.md:24 | word for word |
| 540 | - Every test run that can run in the background runs in the background by default (Bash `run_in_background`) | SAME | rules/tests.md:25 | word for word |
| 542 | S6. No count caps | SAME | rules/resources.md:20 | word for word |
| 543 | - No count caps: no fixed count of agents, task managers or subagents per machine; a new agent pane is admitte... | SAME | rules/resources.md:21 | word for word |
| 544 | - A pane in state working or permission is a busy agent; a done or idle pane and the main manager are not coun... | SAME | rules/resources.md:22 | word for word |
| 545 | - A finished idle pane (state done): its own repo's main manager closes it once its task is merged, dropped or... | SAME | rules/resources.md:23 | word for word |
| 546 | - Never one still waiting on a merge, a question or a decision (W8 closes it after the merge). Never another r... | SAME | rules/resources.md:24 | word for word |
| 548 | S7. Session recovery | SAME | rules/context.md:8 | word for word |
| 549 | - Each agent saves state to `agent_state.txt` in its own worktree while working: task, progress, decisions, ne... | SAME | rules/context.md:9 | word for word |
| 550 | - `agent_state.txt` is git-ignored. It never merges | SAME | rules/context.md:10 | word for word |
| 551 | - S2 restores it after crash or shutdown | SAME | rules/context.md:11 | word for word |
| 553 | S8. Context guard (forgetting) | REWORDED-OK | PRINCIPLES.md:52 + rules/context.md:13 | heading split |
| 554 | - Memory is the file, not the chat. Brief, decisions, next step live in `agent_state.txt`. Re-read it before e... | SAME | PRINCIPLES.md:53 | word for word |
| 555 | - First action of every agent: copy its brief into `agent_state.txt`. The main manager keeps one too, in the m... | SAME | PRINCIPLES.md:54 + rules/context.md:14 | split |
| 556 | - A state line: `agent-file.sh state add "<line>"` (it adds the date), never `echo >>`. A brief or report bloc... | SAME | PRINCIPLES.md:55 + rules/context.md:15 | split |
| 557 | - `agent-file.sh state trim` keeps the header, RULE/CARRY and machine lines, open questions, open-task lines, ... | SAME | rules/context.md:16 | word for word |
| 558 | - `state trim` moves the rest to `agent_state.trim-<date>.txt` next to it, never lost. `todo done` and the hou... | SAME | rules/context.md:17 | word for word |
| 559 | - Over 300 lines (fixed) the start text says STATE LONG: trim it | SAME | rules/context.md:18 | word for word |
| 560 | - After a compaction the startup hook re-prints PRINCIPLES.md and `agent_state.txt`. No quiz then. Continue fr... | SAME | rules/context.md:19 | same words, smaller effect: PRINCIPLES.md is now the 79-line core, rule files are not re-printed after a compaction |
| 561 | - Compacted 2 times (fixed) → save state. Orca: `agent-autoclear.sh` types a save prompt, `/clear`, then `/goa... | SAME | rules/context.md:20 | word for word |
| 562 | - The auto clear fires only when no human has typed a prompt in that pane for the last N minutes (setting "Con... | SAME | rules/context.md:21 | word for word |
| 563 | - Not a human prompt: a task notification, a tell pointer, a cross-session message, the watch or the auto clea... | SAME | rules/context.md:22 | word for word |
| 564 | - A task manager runs under `/goal` from the GOAL: line of its brief: typed after the brief and after each ans... | SAME | rules/context.md:23 | word for word |
| 565 | - After a close case the main manager clears itself the same way: it types `/clear` into its own pane (its han... | SAME | rules/context.md:24 | word for word |
| 566 | - No pane to type into (plain, cloud) or the send is refused → tell the human to type `/clear`; else end the s... | SAME | rules/context.md:25 | word for word |
| 567 | - One worker = one slice, then it ends. A second slice gets a fresh worker | SAME | rules/context.md:26 | word for word |
| 569 | S9. Token guard (cost) | SAME | rules/context.md:28 | word for word |
| 570 | - Cheapest model that can do the job (the Models settings). Managers judge, they do not read whole repos | SAME | rules/context.md:29 | word for word |
| 571 | - Model by kind of thinking: deciding roles get the strongest model, executing roles a cheaper one (the Models... | SAME | rules/context.md:30 | word for word |
| 572 | - A worker gets only the files it needs, named in its brief. No repo-wide reads | SAME | rules/context.md:31 | word for word |
| 573 | - Quiz once per session start. Not after compaction, not for subagents | SAME | rules/context.md:32 | word for word |
| 574 | - Mechanical work (settings, file lines, cleanup) → a script, never an agent | SAME | rules/context.md:33 | word for word |
| 578 | E1. Shape | SAME | rules/output.md:4 | word for word |
| 579 | - For every reply a human reads | SAME | rules/output.md:5 | word for word |
| 580 | - Lead with the result | SAME | rules/output.md:6, rules/output.md:36 | word for word |
| 581 | - A command, path or snippet the human must use comes right after the result | SAME | rules/output.md:7 | word for word |
| 582 | - Number multi-step work, fewest steps | SAME | rules/output.md:8 | word for word |
| 583 | - End with one concrete next action | SAME | rules/output.md:9 | word for word |
| 584 | - No tangents: finish one, offer the other as a separate question. A mid-work question you can answer yourself... | SAME | rules/output.md:10 | word for word |
| 585 | - Restate state every turn: Step <n> of <m> done, next | SAME | rules/output.md:11 | word for word |
| 586 | - Time estimates in real units | SAME | rules/output.md:12 | word for word |
| 587 | - Show what now works | SAME | rules/output.md:13 | word for word |
| 588 | - Errors: cause and fix, never "Uh oh" | SAME | rules/output.md:14 | word for word |
| 589 | - Lists: 5 items or fewer per group, ranked. Keep the rest, never drop them | SAME | rules/output.md:15 | word for word |
| 590 | - No preamble, no recap, no closer | SAME | rules/output.md:16 | word for word |
| 591 | - Break the shape: "explain" or "walk me through" → full length, headers | SAME | rules/output.md:17 | word for word |
| 592 | - Destructive action → confirm first | SAME | rules/output.md:18 | word for word |
| 593 | - 3 turns of "still broken" → name the assumption, ask one question | SAME | rules/output.md:19 | word for word |
| 594 | - Ambiguous request → one short question | SAME | rules/output.md:20 | word for word |
| 595 | - A rule that would delete the answer → the task wins, the shape stays | SAME | rules/output.md:21 | word for word |
| 596 | - The harness or system prompt outranks this section | SAME | rules/output.md:22 | word for word |
| 597 | - Pre-send check: delete an announcing first line, a recap or "anything else" last line, by-the-way sidebars | SAME | rules/output.md:23 | word for word |
| 598 | - Also delete empty hedges (keep a hedge with real uncertainty) and idioms | SAME | rules/output.md:24 | word for word |
| 599 | - Then: first line and last line tell what to do next and what just happened | SAME | rules/output.md:25 | word for word |
| 601 | E2. Owner overrides | SAME | rules/output.md:27 | word for word |
| 602 | - These win over E1 | SAME | rules/output.md:28 | word for word |
| 603 | - Never fail silently: blocked, ambiguous, refused or broken is said at once. Never hidden as a tangent, trimm... | SAME | PRINCIPLES.md:48 + rules/output.md:29 | split |
| 604 | - Tables and ledgers are not lists: the 5-item cap never cuts a record whose value is completeness | SAME | rules/output.md:30 | word for word |
| 605 | - "verified", "works", "fixed" only with the real evidence named. A green suite is not a real device check | SAME | rules/output.md:31 | word for word |
| 606 | - The decide section (H3) is never deleted by "one next action" or "no closers" | SAME | rules/output.md:32 | word for word |
| 607 | - Language stays H2 (the Language setting) | SAME | rules/output.md:33 | word for word |
| 609 | E3. Concise | SAME | rules/output.md:35 | word for word |
| 610 | - Lead with the result | SAME | rules/output.md:6, rules/output.md:36 | word for word |
| 611 | - Cut narration | SAME | rules/output.md:37 | word for word |
| 612 | - Short by default | SAME | rules/output.md:38 | word for word |
| 613 | - State plainly | SAME | rules/output.md:39 | word for word |
| 614 | - Full detail on request | SAME | rules/output.md:40 | word for word |
| 615 | - Never trade correctness for brevity | SAME | rules/output.md:41 | word for word |
| 617 | E4. Keyword hooks | SAME | rules/output.md:43 | word for word |
| 618 | - A keyword hook (bin/agent-keyword.sh) only points to a skill or a rule; the logic lives in the skill or the ... | SAME | rules/output.md:44 | word for word |
| 622 | The pieces. Rules are in A-E; this is where things live. | n/a | rules/map.md:2 | map intro, no rule |
| 624 | Roles and routing: W9. Check blocks: R8; installing into a cloud repo: the cloud-pack skill (`/auto-pipeline:c... | REWORDED-CHANGED | rules/setup.md:21-23 | `--language zh` dropped from the clone command; justified: bin/agent-cloud-pack.sh:39 exits 2 on --language |
| 626 | Agent skills: `/auto-pipeline:dispatch` (route one task), `/auto-pipeline:merge` (the reviewer and the check d... | SAME | rules/map.md:4 | word for word |
| 631 | Human | REWORDED-OK | rules/roles.md:4-16, rules/ui.md:15 | tree picture dropped; every fact is in W6/W5 |
| 632 | │  task ↓   report ↑ | REWORDED-OK | rules/roles.md:4-16, rules/ui.md:15 | tree picture dropped; every fact is in W6/W5 |
| 633 | Main manager   (Main manager model · the main chat · free for the human) | REWORDED-OK | rules/roles.md:4-16, rules/ui.md:15 | tree picture dropped; every fact is in W6/W5 |
| 634 | ├── Fast-lane deputy   (Helper model)  one small task in its own git worktree, then gone | REWORDED-OK | rules/roles.md:4-16, rules/ui.md:15 | tree picture dropped; every fact is in W6/W5 |
| 635 | ├── Reviewer           (Reviewer model setting)  PR review of every task, core review; read only | REWORDED-OK | rules/roles.md:4-16, rules/ui.md:15 | tree picture dropped; every fact is in W6/W5 |
| 636 | ├── Check deputy       (Helper model)  flow and UI checks, release smoke; one at a time on the browser | REWORDED-OK | rules/roles.md:4-16, rules/ui.md:15 | tree picture dropped; every fact is in W6/W5 |
| 637 | ├── Merge deputy       (Helper model)  merge → push → delete branch → remove worktree | REWORDED-OK | rules/roles.md:4-16, rules/ui.md:15 | tree picture dropped; every fact is in W6/W5 |
| 638 | └── Worktree, one per big feature | REWORDED-OK | rules/roles.md:4-16, rules/ui.md:15 | tree picture dropped; every fact is in W6/W5 |
| 639 | └── Task manager (Task manager model)     writes the tests, briefs workers, verifies, never codes | REWORDED-OK | rules/roles.md:4-16, rules/ui.md:15 | tree picture dropped; every fact is in W6/W5 |
| 640 | ├── Worker (Helper model)  code until the tests pass, slice 1 | REWORDED-OK | rules/roles.md:4-16, rules/ui.md:15 | tree picture dropped; every fact is in W6/W5 |
| 641 | └── Worker (Helper model)  code until the tests pass, slice 2 | REWORDED-OK | rules/roles.md:4-16, rules/ui.md:15 | tree picture dropped; every fact is in W6/W5 |
| 643 | Scripts, not agents (cost no tokens): | SAME | rules/map.md:7 | word for word |
| 644 | bin/agent-start.sh   RAM/CPU guard, prints the rules, 36-question quiz gate, main-manager lock | SAME | rules/map.md:8 | word for word |
| 645 | bin/agent-nightly.sh  the nightly run of all tests: gates nothing, records selection misses, --release-ok | SAME | rules/map.md:9 | word for word |
| 646 | bin/agent-test-run.sh  every test run: reserves its measured memory, a monitor watches it (S3, S5) | SAME | rules/map.md:10 | word for word |
| 647 | bin/agent-room.sh  the memory gate: check, reserve, release, list, relief, measure-pane | SAME | rules/map.md:11 | word for word |
| 648 | bin/agent-level.sh   the blocks a diff triggers (R8): agent-level.sh check --base <ref> | SAME | rules/map.md:12 | word for word |
| 649 | bin/agent_blocks.py  the one table of blocks and triggers (R8) | SAME | rules/map.md:13 | word for word |
| 650 | bin/agent-owner-order.sh  relayed owner orders between repo managers: `line` prints the OWNER ORDER header (se... | SAME | rules/map.md:14 | word for word |
| 651 | bin/agent-file.sh    the only writer of agent_*.txt | SAME | rules/map.md:15 | word for word |
| 652 | bin/agent_estimate.py  the time estimator: learns work minutes from the finished tasks, backtests against the ... | SAME | rules/map.md:16 | word for word |
| 653 | bin/agent-settings.sh  show the settings (/plugin -> Configure changes them) | SAME | rules/map.md:17 | word for word |
| 654 | bin/agent-resume.sh    one command to bring the pipeline back after a restart | SAME | rules/map.md:18 | word for word |
| 655 | bin/agent-cleanup.sh   the main manager's sweep: removes merged, clean, idle worktrees and branches; lists the... | SAME | rules/map.md:19 | word for word |
| 656 | bin/agent-housekeep.sh the main manager's pass every housekeep_interval_min from the `agent-watch.sh --all` lo... | SAME | rules/map.md:20 | word for word |
| 657 | bin/agent-watch.sh     `agent-watch.sh --all`: one background watch for every task manager, local or remote (p... | SAME | rules/map.md:21 | word for word |
| 658 | bin/agent-file.sh tell `agent-file.sh tell <task> "<msg>"`: long text to a task manager, a block in its agent_... | SAME | rules/map.md:22 | word for word |
| 659 | bin/agent-init.sh      sets a project up: the four task files, .secrets/, .gitignore lines, AGENTS.md, and it ... | SAME | rules/map.md:23 | word for word |
| 660 | bin/agent-cloud-pack.sh  lays this pipeline into a repo as plain files, for cloud sessions | SAME | rules/map.md:24 | word for word |
| 661 | bin/agent-city.sh       starts/stops the agent city visualiser, a local server | SAME | rules/map.md:25 | word for word |
| 662 | bin/agent-city-shim     the ~/.local/bin/agent-city command; runs the newest installed plugin's agent-city.sh | SAME | rules/map.md:26 | word for word |
| 663 | bin/agent-city-hook.sh  hook that feeds the city; off costs a `test -f`, on appends one JSON line | SAME | rules/map.md:27 | word for word |
| 664 | bin/agent-close-case.sh  UserPromptSubmit hook: tells a released or replaced main manager once | SAME | rules/map.md:28 | word for word |
| 665 | bin/agent-keyword.sh  UserPromptSubmit hook: a keyword in the prompt adds one line pointing to its skill or ru... | SAME | rules/map.md:29 | word for word |
| 666 | bin/agent-board-warn.sh  hook: a new or changed board warning into the main manager's context | SAME | rules/map.md:30 | word for word |
| 667 | bin/agent_board.py     the todo board: one table of every open task, wait, owner to-do and parked question | SAME | rules/map.md:31 | word for word |
| 668 | bin/agent_questions.py  the question list: every question pending on the owner, as a chat list, JSON or an Art... | SAME | rules/map.md:32 | word for word |
| 669 | bin/agent-questions-page.html  the page template (one page grouped by task, lettered options, answer bar) | SAME | rules/map.md:33 | word for word |
| 670 | bin/agent-name.sh       SessionStart + UserPromptSubmit hook: names the session by role (W6; a human-direct on... | SAME | rules/map.md:34 | word for word |
| 671 | bin/agent-guard.sh     hook: records every Agent launch and orca pane on the board, refuses a manager's launch... | SAME | rules/map.md:35 | word for word |
| 672 | bin/agent-promote.sh   the working branch to production, only on the owner's verified words (--owner-quote), `... | SAME | rules/map.md:36 | word for word |
| 673 | bin/agent-runtime.sh   which runtime this agent is in (orca, plain, cloud) and the browser; the one place that... | SAME | rules/map.md:37 | word for word |
| 674 | bin/agent-resources.sh  RAM and CPU readers, sourced by other scripts | SAME | rules/map.md:38 | word for word |
| 675 | bin/agent-autoclear.sh  the waiter behind the auto /clear: save prompt, /clear, /goal, only after the human ha... | SAME | rules/map.md:39 | word for word |
| 676 | bin/agent-release.sh   builds, checks and pushes the `release` branch, one commit per version | SAME | rules/map.md:40 | word for word |
| 677 | bin/agent-statusline.sh  the Claude Code status line: one line per running task | SAME | rules/map.md:41 | word for word |
| 678 | bin/agent-roots.sh     the two roots every script needs (project and plugin), sourced | SAME | rules/map.md:42 | word for word |
| 679 | bin/agent-version.sh   UserPromptSubmit hook + check: a session running an older plugin than installed gets on... | SAME | rules/map.md:43 | word for word |
| 684 | \| File \| Who writes it \| Who reads it \| | SAME | rules/files.md:43 | word for word |
| 685 | \|---\|---\|---\| | SAME | rules/checks.md:14, rules/files.md:44 | word for word |
| 686 | \| `agent_todo.txt` \| `agent-file.sh todo add` / `todo done` \| Every agent at start \| | SAME | rules/files.md:45 | word for word |
| 687 | \| `agent_completed.txt` \| `agent-file.sh todo done`, one data line per task \| Human, `agent-file.sh time` \... | SAME | rules/files.md:46 | word for word |
| 688 | \| `agent_estimate.txt` \| `agent-file.sh retrain`, also `todo done` once a week \| `agent-file.sh estimate` \... | SAME | rules/files.md:47 | word for word |
| 689 | \| `agent_ideas.txt` \| `agent-file.sh idea add` \| Human, on his own time \| | SAME | rules/files.md:48 | word for word |
| 690 | \| `agent_repo.conf` (committed, repo root) \| `bin/agent-init.sh`, agents via `agent-file.sh edge add` \| `ag... | SAME | rules/files.md:49 | word for word |
| 691 | \| `agent_worktree.txt` \| `agent-file.sh worktree set` / `rm` \| Main manager before every dispatch \| | SAME | rules/files.md:50 | word for word |
| 692 | \| `agent_watch.json` (git dir, git-ignored by being there) \| `agent-watch.sh --all` \| `agent-watch.sh`, the... | SAME | rules/files.md:51 | word for word |
| 693 | \| `agent_state.txt` \| Each session: `agent-file.sh state add`; `state trim` moves old lines to `agent_state.... | SAME | rules/files.md:52 | word for word |
| 694 | \| `.secrets/` \| Human only \| Any agent, read only, never printed \| | SAME | rules/files.md:53 | word for word |
| 699 | ./bin/agent-start.sh             # rules, resources, quiz. No work until PASS | SAME | rules/map.md:49 | word for word |
| 700 | ./bin/agent-resume.sh            # runs by itself at startup (Auto resume setting on); run by hand only if you... | SAME | rules/map.md:50 | word for word |
| 701 | ./bin/agent-settings.sh          # show the settings, no agent (change them in /plugin -> Installed -> auto-pi... | SAME | rules/map.md:51 | word for word |
| 702 | bin/agent-file.sh time              # est, work, wait, clock of every finished task | SAME | rules/map.md:52 | word for word |
| 703 | bin/agent-file.sh data              # the same data of every repo on this machine, one table | SAME | rules/map.md:53 | word for word |
| 704 | bin/agent-file.sh eta <name>        # work left as minutes and a clock time, and when the human is needed next | SAME | rules/map.md:54 | word for word |
| 705 | bin/agent-file.sh estimate ... [--guess <m>]   # work minutes of a new task, with a range and the 3 nearest pa... | SAME | rules/map.md:55 | word for word |
| 706 | bin/agent-file.sh backtest          # estimator, blend and rubric on the finished tasks, who wins | SAME | rules/map.md:56 | word for word |
| 707 | bin/agent-file.sh retrain           # learn the estimate again from the finished tasks, keep it only if better | SAME | rules/map.md:57 | word for word |
| 708 | bin/agent-file.sh next              # the queued tasks that can start now, then the board warnings | SAME | rules/map.md:58 | word for word |
| 709 | bin/agent-file.sh checks gate <task> --dir <path>  # the merge gate | SAME | rules/map.md:59 | word for word |
| 710 | bin/agent-nightly.sh --status \| --misses \| --release-ok   # the nightly run of all tests: its state, the sel... | SAME | rules/map.md:60 | word for word |
| 711 | bin/agent-file.sh board             # the todo board: open tasks, waits on the owner, owner to-dos, parked que... | SAME | rules/map.md:61 | word for word |
| 712 | bin/agent-file.sh questions         # the question list: every question pending on the owner (--self, --json, ... | SAME | rules/map.md:62 | word for word |
| 713 | bin/agent-city.sh install-shim      # one time: puts the agent-city command in ~/.local/bin; nothing installs ... | SAME | rules/map.md:63 | word for word |
| 714 | agent-city start                    # agent city visualiser, off by default, costs almost nothing | SAME | rules/map.md:64 | word for word |
| 720 | Section E is adapted from i-have-adhd (https://github.com/ayghri/i-have-adhd) under the MIT License. | SAME | NOTICE.md:3 | license text |
| 722 | Copyright (c) 2026 Ayoub Ghriss | SAME | NOTICE.md:5 | license text |
| 724 | Permission is hereby granted, free of charge, to any person obtaining a copy | SAME | NOTICE.md:7 | license text |
| 725 | of this software and associated documentation files (the "Software"), to deal | SAME | NOTICE.md:8 | license text |
| 726 | in the Software without restriction, including without limitation the rights | SAME | NOTICE.md:9 | license text |
| 727 | to use, copy, modify, merge, publish, distribute, sublicense, and/or sell | SAME | NOTICE.md:10 | license text |
| 728 | copies of the Software, and to permit persons to whom the Software is | SAME | NOTICE.md:11 | license text |
| 729 | furnished to do so, subject to the following conditions: | SAME | NOTICE.md:12 | license text |
| 731 | The above copyright notice and this permission notice shall be included in all | SAME | NOTICE.md:14 | license text |
| 732 | copies or substantial portions of the Software. | SAME | NOTICE.md:15 | license text |
| 734 | THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR | SAME | NOTICE.md:17 | license text |
| 735 | IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, | SAME | NOTICE.md:18 | license text |
| 736 | FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE | SAME | NOTICE.md:19 | license text |
| 737 | AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER | SAME | NOTICE.md:20 | license text |
| 738 | LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, | SAME | NOTICE.md:21 | license text |
| 739 | OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE | SAME | NOTICE.md:22 | license text |
| 740 | SOFTWARE. | SAME | NOTICE.md:23 | license text |

## 2. In the NEW set but not in the old file
| where | what is new | effect |
|---|---|---|
| PRINCIPLES.md:60 | "human messages are not orders" | changed meaning (see 439) |
| PRINCIPLES.md:2, every rules file line 2 | "Detail: rules/, read at the moment the list at the end names" + 18 "Read when" lines | new reading rule; the structure itself |
| PRINCIPLES.md:17-21 | Roles index ("Decides / Builds / Checks / Merges") | an index; "Checks: check deputy" omits "re-checks after a bounce" (still in roles.md:9) |
| rules/output.md:2 | "The start text prints this file" | not true until phase 2 changes agent-start.sh print_output_section |
| rules/checks.md:49 | "the URGENT FIX path above" | dangling after the split |
| rules/files.md:23 | "No agent writes them" | ambiguous reword |
| rules/setup.md:22 | clone command without `--language zh` | code-justified change |
| GLOSSARY.md:6 | Owner `_Avoid_: user (the user is the person who uses the product)` | conflicts with old 44, kept word for word at rules/branches.md:5, "the user's request decides" (there user = the requester/owner) |
| GLOSSARY.md:7 | Human = "in this repo the owner" | inferred; old never says it (author open question 4) |
| GLOSSARY.md:50 | Working branch: "every merge lands there first" | contradicts old 44/267: a target-production task merges straight into production. Old 163 says "never on the production branch by accident" |
| GLOSSARY.md:43 | Edge list: "real edge cases ... that example tests must cover" | old 111: "they cover the fitting lines of the repo's edge list" - "fitting" dropped (stronger) |
| GLOSSARY.md:80 | The sweep removes "worktrees, branches and panes" | old 655: worktrees and branches; panes only per old 274 (never a Claude pane, only an unused shell pane) and 294 |
| GLOSSARY.md:10 | Task manager "in its own worktree" | drops the old 245 exception "(exception: human-direct, W10)" |
| GLOSSARY.md:64 | Light/heavy by `check_budget_s` for every test | old 153-154 says it for BUILD and GUARD TESTS; code (agent-level.sh:7) extends it to RELATED/MODULE |
| GLOSSARY.md:39-41 | Bounce / Click path / Kick-off round | defined from skills (merge:9, dispatch:108, dispatch:100), not from old text |
| GLOSSARY.md:48, 60, 79 | production-branch order, check-line format, "Stuck: Tidy every (min)" | from code (agent_conf.py:873, agent_checks.py:580, plugin.json:123), not old text; correct |

## 3. Reachability (agent reads only the core)
| moment | core sends to | needed rule there? | verdict |
|---|---|---|---|
| (a) main manager, new small task | core:35, core:79 skill dispatch, core:64, core:72 | dispatch steps 1-2 hold it; W9 lines 300/304/305/311 only proposed; 312 options missing | PASS (with 312) |
| (b) a task manager's worker reports a bug | nothing fits ("role detail" at most) | needed: roles.md:14 (defect back to the worker that wrote it, with evidence), checks.md:53 (edge add after a bug fix), tests.md:5 (small test with the fix), files.md:33 (idea outside the task). The brief (dispatch:105) holds "Defect -> back to the worker with evidence"; worker.md:16 holds edge add | FAIL via the core |
| (c) "2. need to publish direct after done" | core:65 | approval.md:11, :15-19, :24 | PASS (agent-keyword.sh:56 still points to "PRINCIPLES.md R8": phase 2) |
| (d) deputy about to merge | core:70, :64, :66, :50 | worktrees.md W8, checks.md:40, branches.md; agents/merge-deputy.md | PASS |
| (e) memory 85%, a test must run | core:74, :67 | resources.md S3/S4, tests.md S5 | PASS |
| (f) context just compacted | core:75 | context.md:19-20 | PASS, but only the core is re-printed; no line says "re-read the rule file of your current step" |
| (g) push denied | core:77 | traps.md:5-6 | PASS |
| (h) second session starts | core:69 (+ start text TASK line) | roles.md W10 | PASS |
| (i) task manager must report done | core:71, :72 | watch.md:11, :21; time.md:8; brief REPORT | PASS; "a report block: one append, then one blank line" (context.md:15) is not reached |
| (j) reply with two open questions | core:63 | human.md H3:25-36 | PASS |
| (k) reviewer asked for PR REVIEW | core:64 (+ agents/reviewer.md) | checks.md:6-7, :15, :34-37, :41 | PASS |
| (l) worker starts its slice | core:67, :74 (+ agents/worker.md) | tests.md W3/S5, resources.md, context.md:26,31 | PASS |
| extra: look for another agent's pane, read a pane, Linux outside Orca, screen locked | core:77 lists only push denied, message held, send cut, MODE MISMATCH, STALE PLUGIN | traps.md:10-12, :14 | FAIL |
| extra: read a HOUSEKEEP block | core:70 has no HOUSEKEEP | worktrees.md:39-40 | FAIL |
| extra: place a job or test run | core:74 -> resources.md, which has no placement | worktrees.md:12-14 (dispatch step 6 only for panes) | FAIL |
| extra: write the requirement doc | no pointer | dispatch:21 (defaults table), checks.md:24 (owner approves money/permission examples) | FAIL |
| extra: the start quiz | core only | 27 of 36 questions test codes outside the core (R3, R6, R8 x8, H1 x2, H3 x3, W2, W4, W6, W7 x2, W8, W9 x2, W10, W12, S1, S3); refusal says "Re-read those rules in PRINCIPLES.md" | FAIL until phase 2 |

## 4. The core (79 lines)
Every-step rules now only in rule files (no longer always loaded):
- E1-E3 output shape (rules/output.md): every reply. The start text prints section E today; with the new core it prints nothing.
- H2 (Language setting; never cite a rule code to the human) and H3 (every report ends with the decide section; open questions repeated) - rules/human.md.
- E2 "verified / works / fixed only with the real evidence named" - rules/output.md:31.
- Role limits: "Main manager ... Nothing else" and "stays free for the human, runs no long check itself" (roles.md:5, :10); "Managers never write product code" (roles.md:14); "Workers never write tests" (tests.md:9). The core Roles index names the roles but not these limits.
- W1 ideas: "never in the work or the report" (files.md:33).
- S9 "Mechanical work -> a script, never an agent" (context.md:33).
Core lines not needed by every agent (main manager routing only; a task manager follows its brief's STEPS): R1 core:24-34 (10-step flow) and core:35-38 (lanes, post-build sequence). Candidates to move to skill dispatch / rules/roles.md. core:3 (settings, never hard-code) is needed only when touching a setting or a number.

## 5. Glossary support (old line quoted)
Supported: Main manager (318, 239), Worker (247, 567), Fast-lane deputy (240, 299), Reviewer (242), Check deputy (243), Merge deputy (241), Deputy (433), Builder (149), Fixer (171-172), Decision maker (431), Decider floor (432), Human-direct (319, 322), Helper (250, 290, 440), Peer (350), Task (338, 117), Task instance (130), Slice (567), Fast lane (37), Full lane (38, 97), Batch (170), Brief (555), Fix order (249, 43), Requirement doc (25, 88), Core path (110, 186), Mock (201-206), Target (44-45), Base (310), Main checkout (163-165), Late yes (130-134), Check block (97-98), The gate (148), Owner sign (120, 151), Selection miss (157), The net (92, 156), Release run (175), Pane (274, 544), The lock (318), LAUNCH record (275, 671), The watch (404), Stall (402), Housekeep pass (286, 656), State file (554), Decide section (481-486), Parked question (394, 466), OWNER TODO (129), Start text (436, 644).
Not supported by old text: Owner `_Avoid_ user`; Human = owner; Working branch "every merge lands there first"; Edge list ("fitting" dropped; `edge=` from code); The sweep "and panes"; Task manager (exception dropped); Light/heavy for every test; Connected machine = paired Orca machine (old uses both, never equates them); Bounce, Click path, Kick-off round (from skills); Production branch order, Check line format, Tidy title (from code).

## 6. proof.md vs this check
My script confirmed all 528 "move" and 33 "keep" rows word for word at their stated home (one exception: row 393, "Decision maker =", marked move but reworded in GLOSSARY.md:21), and all 48 skill snippets of the "pointer" rows. Claims I could not confirm:
| proof row | old.md line | proof says | finding |
|---|---|---|---|
| 281 | 308 | pointer, skill dispatch holds it | the two options are not in the skill (WEAKER) |
| 401 | 436 | merge, "'exempt' = not an order to check" | new words say human messages are not orders (CHANGED) |
| 341 | 372 | pointer, part B 2-4 | "update the agent files" is not there; B4 only checks |
| 164 | 180 | move, unchanged words | words unchanged, but "above" now dangles |
| 393 | 428 | move to GLOSSARY.md:21 | reworded, not moved word for word |
| 58 | 69 | reword | "No agent writes them" shifts the meaning |
| 3, 505 | 4, 557 | pointer / move | true on paper; the start hook still prints and re-prints from PRINCIPLES.md, so E is lost and the rule files are not re-printed until phase 2 |
| 15-27 | 22-34 | keep, "every agent at every step" | R1 flow and lanes are main-manager routing, not every agent's step |
