# Proof: every statement of the old PRINCIPLES.md has a home

Source: the final text, `origin/main:PRINCIPLES.md` at 149710d = `249f1c1:PRINCIPLES.md` (saved as PRINCIPLES.old-249f1c1.md, 740 lines). Rows: one per non-blank line, except the section headings (## 0. First, ## A-F, ### Tree/Files/Commands) and code fences, which carry no rule. Earlier copies (PRINCIPLES.old.md at c23d06b, PRINCIPLES.old-83a087c.md) are kept for history only.

Rows: 655. Rows with a home: 655. rows with a home = rows. No row ends in proposed-skill-changes.md: every home is PRINCIPLES.md, rules/, GLOSSARY.md or NOTICE.md.

| mark | rows |
|---|---|
| move | 554 |
| keep | 43 |
| reword | 32 |
| merge | 24 |
| pointer | 1 |
| stale, fixed by code evidence | 1 |

| n | old line | statement (short) | mark | new home | why |
|---|---|---|---|---|---|
| 1 | 1 | PRINCIPLES | keep | PRINCIPLES.md:1 | unchanged words, always loaded |
| 2 | 3 | Read first. Binding for every agent in this repo. | reword | PRINCIPLES.md:2 | 'Read first' is what the start text's RULES line does |
| 3 | 4 | Output shape: section E. Human language: the Language setting (H2). | pointer | PRINCIPLES.md:76 | output shape -> rules/output.md (and the core's 'Talking to the human'); Language setting -> core (H2) |
| 4 | 5 | Settings live only in /plugin -> Installed -> auto-pipeline -> Configure (S1). Other numbers are fixed cons... | move | rules/setup.md:4 | unchanged words, read at the moment of its file |
| 5 | 9 | P1. Fastest correct way | keep | PRINCIPLES.md:4 | unchanged words, always loaded |
| 6 | 10 | Owner 2026-11-25: "use the most fast and efficiency way for any of your works". This comes first, for every... | keep | PRINCIPLES.md:5 | unchanged words, always loaded |
| 7 | 11 | Before each step ask: what is the quickest way to the correct result? Take that way | reword | PRINCIPLES.md:6 | question + 'take that way' -> one imperative |
| 8 | 12 | Check, do not wait: a quick check (read the file, a trial merge) settles a doubt faster than a queue or a q... | keep | PRINCIPLES.md:7 | unchanged words, always loaded |
| 9 | 13 | Parallel first: tasks run on their own branches; the one that merges second resolves the conflict. For an a... | keep | PRINCIPLES.md:8 | unchanged words, always loaded |
| 10 | 14 | Parallel also for the same module in a different part, and for a conflict in text that is not logic (docs, ... | keep | PRINCIPLES.md:9 | unchanged words, always loaded |
| 11 | 15 | One exception: a follow-up on the logic an agent is changing right now goes to that agent. Two agents chang... | keep | PRINCIPLES.md:10 | unchanged words, always loaded |
| 12 | 16 | Decide, do not ask: when the owner's words or a rule already answer it, or a default can be taken and logge... | reword | PRINCIPLES.md:11 | 'Decide, do not ask: when ... a default can be taken and logged' -> 'a loggable default answers it → decide, go on' |
| 13 | 17 | Ask the owner only an owner-level or irreversible call (W1) | keep | PRINCIPLES.md:11 | unchanged words, always loaded |
| 14 | 18 | Challenged on a decision: check the facts first, then keep it with the evidence, or change it and say what ... | reword | PRINCIPLES.md:12 | 'check the facts first, then' -> 'check the facts, then' |
| 15 | 19 | Work that does not depend on other work runs in parallel; take the smallest change and the cheapest tool th... | reword | PRINCIPLES.md:13 | 'work that does not depend on other work' -> 'independent work' (standard term) |
| 16 | 20 | Fast never means less: no required check skipped, no failure hidden, no cleanup left. A wrong result is the... | keep | PRINCIPLES.md:14 | unchanged words, always loaded |
| 17 | 24 | R1. One flow, two lanes | keep | PRINCIPLES.md:23 | unchanged words, always loaded |
| 18 | 25 | Before the flow: the main manager writes the requirement doc, the owner approves it | keep | PRINCIPLES.md:24 | unchanged words, always loaded |
| 19 | 26 | Full flow, in order: | keep | PRINCIPLES.md:24 | unchanged words, always loaded |
| 20 | 27 | 1. Todo line + estimate | keep | PRINCIPLES.md:25 | unchanged words, always loaded |
| 21 | 28 | 2. Mock for a new page or a whole-page re-layout (W2) | keep | PRINCIPLES.md:26 | unchanged words, always loaded |
| 22 | 29 | 3. Worktree + task manager | keep | PRINCIPLES.md:27 | unchanged words, always loaded |
| 23 | 30 | 4. Failing tests first | keep | PRINCIPLES.md:28 | unchanged words, always loaded |
| 24 | 31 | 5. Workers build | keep | PRINCIPLES.md:29 | unchanged words, always loaded |
| 25 | 32 | 6. Verify | keep | PRINCIPLES.md:30 | unchanged words, always loaded |
| 26 | 33 | 7. Push | keep | PRINCIPLES.md:31 | unchanged words, always loaded |
| 27 | 34 | 8. Acceptance blocks (R8) | keep | PRINCIPLES.md:32 | unchanged words, always loaded |
| 28 | 35 | 9. Merge into the target branch + cleanup | keep | PRINCIPLES.md:33 | unchanged words, always loaded |
| 29 | 36 | 10. Todo done | keep | PRINCIPLES.md:34 | unchanged words, always loaded |
| 30 | 37 | Task size picks who does the work: small task = one subagent in its own git worktree (fast lane); it writes... | reword | PRINCIPLES.md:35 | the deputy's own work (own git worktree, example tests, its blocks): rules/roles.md W6, agents/fast-lane-deputy.md |
| 31 | 38 | Big task (over 2 hours, several slices) = a task manager (full lane) | merge with 37 | PRINCIPLES.md:35 | same line |
| 32 | 39 | Which checks run follows the triggers only (R8), never the lane | reword | PRINCIPLES.md:36 | joined with row 40 |
| 33 | 40 | A small logic task never opens a task manager just because it needs a test | merge with 39 | PRINCIPLES.md:36 | 'just because it needs a test' -> 'just for a test' |
| 34 | 41 | A small task that grows (past 2x its estimate, or it needs a second slice): the subagent stops and reports;... | reword | PRINCIPLES.md:37 | 'the subagent' -> 'the deputy' |
| 35 | 42 | One fixed sequence after the build: builder reports done -> reviewer reads the diff against the approved re... | reword | PRINCIPLES.md:38 | 'reads the diff against the approved requirement' = rules/checks.md R8 (PR REVIEW); '15 min box' = rules/checks.md (FLOW/UI CHECK); Reviewer model = rules/roles.md |
| 36 | 43 | A fail at review or check goes back to the builder as a fix order | merge with 42 | PRINCIPLES.md:38 | same line |
| 37 | 44 | The target: the user's request decides, read by the approval cases (R8). It says publish or merge to main -... | move | rules/branches.md:5 | unchanged words, read at the moment of its file |
| 38 | 45 | No such words, or unclear -> the working branch (ap-main-<name>, setting "Flow: Working branch"); nothing g... | move | rules/branches.md:6 | unchanged words, read at the moment of its file |
| 39 | 47 | R2. Secrets | keep | PRINCIPLES.md:47 | unchanged words, always loaded |
| 40 | 48 | Live in `.secrets/` (git-ignored) | reword | PRINCIPLES.md:47 | three lines -> one |
| 41 | 49 | Read only | merge with 48 | PRINCIPLES.md:47 | same line |
| 42 | 50 | Never write, print, copy, commit | merge with 48 | PRINCIPLES.md:47 | same line |
| 43 | 52 | R3. Docs | move | rules/files.md:4 | unchanged words, read at the moment of its file |
| 44 | 53 | Allowed: requirement, test, main idea | move | rules/files.md:5 | unchanged words, read at the moment of its file |
| 45 | 54 | Nothing else | move | rules/files.md:6 | unchanged words, read at the moment of its file |
| 46 | 55 | `PRINCIPLES.md` = main idea doc | move | rules/files.md:7 | unchanged words, read at the moment of its file |
| 47 | 56 | Entry files allowed: `CLAUDE.md`, `AGENTS.md` (one line, point to `bin/agent-start.sh`) | move | rules/files.md:8 | unchanged words, read at the moment of its file |
| 48 | 57 | `README.md` allowed: the picture of the tree and the flow, for people new to the repo | move | rules/files.md:9 | unchanged words, read at the moment of its file |
| 49 | 58 | Config, not docs, allowed: `.claude-plugin/`, `agents/`, `skills/`, `hooks/`, `bin/` | move | rules/files.md:10 | unchanged words, read at the moment of its file |
| 50 | 59 | Rubbish: `/auto-pipeline:clean-up` (main manager) lists other docs, old state copies, finished mocks and st... | move | rules/files.md:11 | unchanged words, read at the moment of its file |
| 51 | 61 | R4. No changelog | move | rules/files.md:13 | unchanged words, read at the moment of its file |
| 52 | 62 | Git history is the record | move | rules/files.md:14 | unchanged words, read at the moment of its file |
| 53 | 64 | R5. Task files | move | rules/files.md:16 | unchanged words, read at the moment of its file |
| 54 | 65 | `agent_todo.txt` = open tasks only, always current | move | rules/files.md:17 | unchanged words, read at the moment of its file |
| 55 | 66 | Done → agent_completed.txt: date, name, what, then one `data` block written by `agent-file.sh`: repo, type,... | move | rules/files.md:18 | unchanged words, read at the moment of its file |
| 56 | 67 | No test results in it, that is report material | move | rules/files.md:19 | unchanged words, read at the moment of its file |
| 57 | 68 | No other task tracking | move | rules/files.md:20 | unchanged words, read at the moment of its file |
| 58 | 69 | The housekeep pass never closes a todo line: it flags one whose branch is merged into the working branch or... | move | rules/files.md:21 | unchanged words, read at the moment of its file |
| 59 | 70 | A stale todo line is flagged too: no worktree line, no open wait, quiet longer than the interval of W8 | move | rules/files.md:22 | unchanged words, read at the moment of its file |
| 60 | 71 | All four `agent_*.txt` files are written only through `bin/agent-file.sh`. No agent for that, it costs tokens | reword | PRINCIPLES.md:50 | split: the rule in the core (Never); 'No agent for that, it costs tokens' -> rules/files.md: 'Do not launch an agent to write these files: it costs tokens; `bin/agent-file.sh` writes them' |
| 61 | 72 | `agent_completed.txt` is never deleted, trimmed or cleaned (every clean-up skips it); only on an explicit o... | move | rules/files.md:24 | unchanged words, read at the moment of its file |
| 62 | 74 | R6. Ideas file | move | rules/files.md:26 | unchanged words, read at the moment of its file |
| 63 | 75 | `agent_ideas.txt` = ideas outside the current task | move | rules/files.md:27 | unchanged words, read at the moment of its file |
| 64 | 76 | Agents append, keep it clean and current | move | rules/files.md:28 | unchanged words, read at the moment of its file |
| 65 | 77 | Human reviews it on his own time | move | rules/files.md:29 | unchanged words, read at the moment of its file |
| 66 | 78 | The housekeep pass removes an exact duplicate idea (the first stays) and flags suspects (an idea naming a t... | move | rules/files.md:30 | unchanged words, read at the moment of its file |
| 67 | 80 | R7. Worktree file | move | rules/files.md:32 | unchanged words, read at the moment of its file |
| 68 | 81 | `agent_worktree.txt` = one line per live worktree: path, task manager, module, status (working \| final \| ... | move | rules/files.md:33 | unchanged words, read at the moment of its file |
| 69 | 82 | Task manager updates its own line. Deputy removes the line after cleanup | move | rules/files.md:34 | unchanged words, read at the moment of its file |
| 70 | 83 | Main manager reads it before every dispatch (W9) | move | rules/files.md:35 | unchanged words, read at the moment of its file |
| 71 | 84 | The housekeep pass removes a line whose worktree folder is gone and has no live pane; a working, final or h... | move | rules/files.md:36 | unchanged words, read at the moment of its file |
| 72 | 86 | R8. Check blocks | move | rules/checks.md:4 | unchanged words, read at the moment of its file |
| 73 | 87 | Owner 2026-11-25: "let other agents verify the outcome of the code instead of letting test cases do it"; te... | move | rules/checks.md:5 | unchanged words, read at the moment of its file |
| 74 | 88 | PR REVIEW, the main check of every task: an agent that did not build it reads the diff against the approved... | move | rules/checks.md:6 | unchanged words, read at the moment of its file |
| 75 | 89 | It asks: does it do what was asked, nothing else; are the edge list lines covered; is no check deleted; no ... | move | rules/checks.md:7 | unchanged words, read at the moment of its file |
| 76 | 90 | A run or browser check (FLOW CHECK, UI CHECK) comes on top only when what the user sees or does changed: on... | move | rules/checks.md:8 | unchanged words, read at the moment of its file |
| 77 | 91 | Tests stay as a cheap guard: light related tests in every task; a bug that a review or check finds gets a s... | move | rules/tests.md:5 | unchanged words, read at the moment of its file |
| 78 | 92 | The full suite is the safety net only: the release run on the working branch and the nightly, never in a ta... | move | rules/branches.md:9 | unchanged words, read at the moment of its file |
| 79 | 93 | URGENT FIX: branch from the production branch, the smallest fix, PR REVIEW and the light related tests | move | rules/branches.md:10 | unchanged words, read at the moment of its file |
| 80 | 94 | Here his verified words at dispatch, read as the publish of that task, are his final yes (W12); no second y... | move | rules/branches.md:11 | unchanged words, read at the moment of its file |
| 81 | 95 | Then merge to production (`agent-promote.sh --task`; the deploy follows) and merge production back into the... | move | rules/branches.md:12 | unchanged words, read at the moment of its file |
| 82 | 96 | Owner 2026-11-25: "only do the necessary thing when needed, dont do extra thing. and dont do less thing" | move | rules/checks.md:9 | unchanged words, read at the moment of its file |
| 83 | 97 | No levels: each check is a block with a trigger; a task runs the blocks whose trigger fires, nothing else | move | rules/checks.md:10 | unchanged words, read at the moment of its file |
| 84 | 98 | The one table, source `bin/agent_blocks.py`; this table, the skills and the quiz are tested against it: | move | rules/checks.md:11 | unchanged words, read at the moment of its file |
| 85 | 100 | \| Block \| Picked \| Trigger \| What runs \| Owner signs \| | move | rules/checks.md:13 | unchanged words, read at the moment of its file |
| 86 | 101 | \|---\|---\|---\|---\|---\| | move | rules/checks.md:14 | unchanged words, read at the moment of its file |
| 87 | 102 | \| PR REVIEW \| tool \| every task \| an agent that did not build it reads the diff against the approved re... | move | rules/checks.md:15 | unchanged words, read at the moment of its file |
| 88 | 103 | \| DIFF SCAN \| tool \| every task \| the tool scans the diff: files outside the task's scope, deleted or s... | move | rules/checks.md:16 | unchanged words, read at the moment of its file |
| 89 | 104 | \| BUILD \| tool \| code changed \| lint + type-check or syntax check of the app that was touched \| no \| | move | rules/checks.md:17 | unchanged words, read at the moment of its file |
| 90 | 105 | \| RELATED TESTS \| tool \| code, text or rule files changed \| only the LIGHT tests (measured) that import... | move | rules/checks.md:18 | unchanged words, read at the moment of its file |
| 91 | 106 | \| MODULE TESTS \| tool \| code used by other modules changed, or dependencies, lockfile, CI or test config... | move | rules/checks.md:19 | unchanged words, read at the moment of its file |
| 92 | 107 | \| GUARD TESTS \| tool \| code or text changed \| the repo's tree-scanning tests (listed in the repo file) ... | move | rules/checks.md:20 | unchanged words, read at the moment of its file |
| 93 | 108 | \| DB CHECK \| tool \| a migration or schema file is in the diff \| dry run on a data copy, counts before a... | move | rules/checks.md:21 | unchanged words, read at the moment of its file |
| 94 | 109 | \| DATA CHECK \| tool \| a script that changes live data \| preview of the rows (the count must match the e... | move | rules/checks.md:22 | unchanged words, read at the moment of its file |
| 95 | 110 | \| CORE REVIEW \| tool \| a core path of the repo is touched (money, permission), or the brief says who can... | move | rules/checks.md:23 | unchanged words, read at the moment of its file |
| 96 | 111 | \| EXAMPLES TEST \| brief \| behaviour or logic changes \| failing tests first, written from the examples i... | move | rules/checks.md:24 | unchanged words, read at the moment of its file |
| 97 | 112 | \| FLOW CHECK \| brief \| what a user does changes \| someone who did not build it runs 1 normal path + 1 e... | move | rules/checks.md:25 | unchanged words, read at the moment of its file |
| 98 | 113 | \| UI CHECK \| brief \| what a user sees changes: new page, re-layout, size or responsive change \| compare... | move | rules/checks.md:26 | unchanged words, read at the moment of its file |
| 99 | 114 | \| REAL DATA COUNT \| brief \| a rule, limit or validation is added or tightened, or a list, print or expor... | move | rules/checks.md:27 | unchanged words, read at the moment of its file |
| 100 | 116 | Picked tool: `agent-level.sh check --base <ref>` decides them from the real diff, no judgment | move | rules/checks.md:29 | unchanged words, read at the moment of its file |
| 101 | 117 | Picked brief: dispatch picks them from what the owner approved: `todo add ... --checks "<BLOCK>,<BLOCK>"` | move | rules/checks.md:30 | unchanged words, read at the moment of its file |
| 102 | 118 | Two passes: the brief blocks at dispatch; before merge the tool recomputes the tool blocks from the real diff | move | rules/checks.md:31 | unchanged words, read at the moment of its file |
| 103 | 119 | Blocks are only added; removing one needs a verified owner order: `todo checks <task> --remove <BLOCK> --ow... | move | rules/checks.md:32 | unchanged words, read at the moment of its file |
| 104 | 120 | Approval rule: three places need his yes: a task published straight to production, a block left out, the wo... | move | rules/approval.md:5 | unchanged words, read at the moment of its file |
| 105 | 121 | The deciding agent reads his words; no fixed sentence, no word list | move | rules/approval.md:6 | unchanged words, read at the moment of its file |
| 106 | 122 | The tool only checks the quote is a prompt he typed and stores it with what the main manager read: `--owner... | move | rules/approval.md:7 | unchanged words, read at the moment of its file |
| 107 | 123 | A quote under 20 characters ("1A", "ok") counts only as his whole prompt, with the question it answered | move | rules/approval.md:8 | unchanged words, read at the moment of its file |
| 108 | 124 | The gate and promote print the stored pair as OWNER WORDS lines; the report to him repeats them | move | rules/approval.md:9 | unchanged words, read at the moment of its file |
| 109 | 125 | Approval cases: | move | rules/approval.md:10 | unchanged words, read at the moment of its file |
| 110 | 126 | A numbered batch: "2. publish direct after done, others wait for my review" -> task 2 gets target productio... | move | rules/approval.md:11 | unchanged words, read at the moment of its file |
| 111 | 127 | No numbers, a task named by its description: exactly one fits -> no question | move | rules/approval.md:12 | unchanged words, read at the moment of its file |
| 112 | 128 | With two similar tasks: check first (todo lines, requirement docs, what he said before); still unsure -> on... | move | rules/approval.md:13 | unchanged words, read at the moment of its file |
| 113 | 129 | Not a yes now: a question ("is it ready to publish?"), a later time ("publish next week": park one `agent-f... | move | rules/approval.md:14 | unchanged words, read at the moment of its file |
| 114 | 130 | A yes after the task was added: `todo target <task> production --owner-quote "<his words>" --means "<the ac... | move | rules/approval.md:15 | unchanged words, read at the moment of its file |
| 115 | 131 | After `todo target <task> production ...` the main manager sends a new fast-lane deputy: a new branch from ... | move | rules/approval.md:16 | unchanged words, read at the moment of its file |
| 116 | 132 | Its brief names `late yes of: <task>` and `old branch: <branch>` | move | rules/approval.md:17 | unchanged words, read at the moment of its file |
| 117 | 133 | Then every planned block runs again at its head (PR REVIEW, FLOW CHECK, UI CHECK, CORE REVIEW, OWNER SIGN),... | move | rules/approval.md:18 | unchanged words, read at the moment of its file |
| 118 | 134 | A task already merged (todo line closed): the same deputy cherry-picks its commits from the working branch,... | move | rules/approval.md:19 | unchanged words, read at the moment of its file |
| 119 | 135 | A cherry-pick that conflicts, or a task that depends on other unreleased work -> the main manager tells the... | move | rules/approval.md:20 | unchanged words, read at the moment of its file |
| 120 | 136 | A relayed owner order is verified where he typed it: the approval commands take `--relayed-from <the sender... | move | rules/approval.md:21 | unchanged words, read at the moment of its file |
| 121 | 137 | `--relayed-from` must be a repo with a main manager lock (now or before); a relay from another machine cann... | move | rules/approval.md:22 | unchanged words, read at the moment of its file |
| 122 | 138 | A condition the flow already meets ("publish after the tests pass") is a yes; unsure -> one question | move | rules/approval.md:23 | unchanged words, read at the moment of its file |
| 123 | 139 | His short answer to a numbered question counts together with that question: the question stands in the assi... | move | rules/approval.md:24 | unchanged words, read at the moment of its file |
| 124 | 140 | PR REVIEW and OWNER SIGN are never removed | move | rules/checks.md:33 | unchanged words, read at the moment of its file |
| 125 | 141 | A production task is added at dispatch: `todo add ... --target production --owner-quote "<his words>" --mea... | move | rules/approval.md:25 | unchanged words, read at the moment of its file |
| 126 | 142 | One result line per block: `agent-file.sh check <task> "<BLOCK>" pass\|fail --by <who> --evidence "<text>"` | move | rules/checks.md:34 | unchanged words, read at the moment of its file |
| 127 | 143 | The reviewer and the check deputy always pass --commit <the head they looked at> | move | rules/checks.md:35 | unchanged words, read at the moment of its file |
| 128 | 144 | PR REVIEW, FLOW CHECK and UI CHECK count only from a reviewer or check deputy the main manager launched (th... | move | rules/checks.md:36 | unchanged words, read at the moment of its file |
| 129 | 145 | A check line records the commit it saw; PR REVIEW, FLOW CHECK and UI CHECK count only at the head being mer... | move | rules/checks.md:37 | unchanged words, read at the moment of its file |
| 130 | 146 | Threat model: the gate guards against mistakes and shortcuts made through the documented commands | move | rules/checks.md:38 | unchanged words, read at the moment of its file |
| 131 | 147 | It does not stop an agent that forges files by hand; a forgery is a breach the main manager reports to the ... | move | rules/checks.md:39 | unchanged words, read at the moment of its file |
| 132 | 148 | The merge gate `agent-file.sh checks gate <task>` refuses while a planned block has no pass line | move | rules/checks.md:40 | unchanged words, read at the moment of its file |
| 133 | 149 | PR REVIEW, CORE REVIEW, FLOW CHECK and UI CHECK pass only by someone who did not build the task: not the bu... | move | rules/checks.md:41 | unchanged words, read at the moment of its file |
| 134 | 150 | No task runs the full suite (owner 1A 2026-11-25): MODULE TESTS is the largest per-task check | move | rules/checks.md:42 | unchanged words, read at the moment of its file |
| 135 | 151 | OWNER SIGN is planned when a sign fires: MODULE TESTS on a dependency, lockfile, CI or test-config change, ... | move | rules/checks.md:43 | unchanged words, read at the moment of its file |
| 136 | 152 | Dispatch plans OWNER SIGN with CORE REVIEW when the brief changes who can see or do what | move | rules/checks.md:44 | unchanged words, read at the moment of its file |
| 137 | 153 | BUILD and GUARD TESTS run per task only when their measured time in agent_repo.conf is under `check_budget_... | move | rules/checks.md:45 | unchanged words, read at the moment of its file |
| 138 | 154 | Slower = heavy: it runs in the net, not in the task | move | rules/checks.md:46 | unchanged words, read at the moment of its file |
| 139 | 155 | REAL DATA COUNT with no read access: skipped with one printed line, never silently | merge with 114 | rules/checks.md:27 | the table row says the same: 'No read access: skipped with one printed line, never silently' |
| 140 | 156 | Outside tasks, the net: NIGHTLY RUN, all tests once every night in the background (`agent-nightly.sh`); it ... | move | rules/branches.md:13 | unchanged words, read at the moment of its file |
| 141 | 157 | A failure the nightly finds that the causing task's own RELATED or MODULE run did not find is a selection m... | move | rules/branches.md:14 | unchanged words, read at the moment of its file |
| 142 | 158 | After two weeks the owner reads the selection miss count and decides whether the nightly goes too | move | rules/branches.md:15 | unchanged words, read at the moment of its file |
| 143 | 159 | The watch's housekeep pass starts it once a day after 22:00 (`nightly_hour`) when no heavy test runs; no wa... | move | rules/branches.md:16 | unchanged words, read at the moment of its file |
| 144 | 160 | A release needs a green full run on the working branch: the last nightly on that commit, or one background ... | move | rules/branches.md:17 | unchanged words, read at the moment of its file |
| 145 | 161 | `agent-nightly.sh --start` runs the full suite in the background; `agent-nightly.sh --release-ok` only chec... | move | rules/branches.md:18 | unchanged words, read at the moment of its file |
| 146 | 162 | The working branch (setting "Flow: Working branch", default `ap-main-<name>`) is only a branch | move | rules/branches.md:19 | unchanged words, read at the moment of its file |
| 147 | 163 | Everything merged or pushed lands there first, never on the production branch by accident: the main checkou... | move | rules/branches.md:20 | unchanged words, read at the moment of its file |
| 148 | 164 | init switches the main checkout of a new repo to the working branch; in a repo that already uses the plugin... | move | rules/branches.md:21 | unchanged words, read at the moment of its file |
| 149 | 165 | A repo whose working branch exists but whose main checkout is not switched yet: merges go into the producti... | reword | rules/branches.md:22 | the section names its file; decided by the main manager 2026-11-26, the owner can veto |
| 150 | 166 | The working branch is per person (<name> = the git user name in lower case, only letters, digits and "-"): ... | move | rules/branches.md:23 | unchanged words, read at the moment of its file |
| 151 | 167 | A task manager or deputy on another machine never derives it again (git user names differ between machines)... | move | rules/branches.md:24 | unchanged words, read at the moment of its file |
| 152 | 168 | It belongs to that person: the sweep never deletes it, nobody else merges into it | move | rules/branches.md:25 | unchanged words, read at the moment of its file |
| 153 | 169 | Other people publish to the production branch meanwhile: it is merged into the working branch at the start ... | move | rules/branches.md:26 | unchanged words, read at the moment of its file |
| 154 | 170 | Batches: tasks given together merge into the working branch; when the last one of the batch is merged, ONE ... | move | rules/branches.md:27 | unchanged words, read at the moment of its file |
| 155 | 171 | A red batch run goes to a new fixer agent, never back to the builder | move | rules/branches.md:28 | unchanged words, read at the moment of its file |
| 156 | 172 | The fixer is a normal task: todo add first, a brief with target, base and both branches, its own PR REVIEW ... | move | rules/branches.md:29 | unchanged words, read at the moment of its file |
| 157 | 173 | Production from the working branch: only on the owner's approval (verified words) and only from a green com... | move | rules/branches.md:30 | unchanged words, read at the moment of its file |
| 158 | 174 | A repo with a release build runs it right after, so merged to production = published | move | rules/branches.md:31 | unchanged words, read at the moment of its file |
| 159 | 175 | RELEASE RUN: the full suite runs once on the working branch before such a publish (the batch run on that co... | move | rules/branches.md:32 | unchanged words, read at the moment of its file |
| 160 | 176 | Release run failures: `agent-nightly.sh --failures` names, for each failing test, the merge that introduced... | move | rules/branches.md:33 | unchanged words, read at the moment of its file |
| 161 | 177 | The new fixer agent gets the test, the merge and that task's requirement, and labels each failure | move | rules/branches.md:34 | unchanged words, read at the moment of its file |
| 162 | 178 | "test out of date": update it, cite the requirement line or commit that changed the behaviour on purpose; "... | move | rules/branches.md:35 | unchanged words, read at the moment of its file |
| 163 | 179 | No check is deleted without a twin; the fixer's report is a table of these labels: test \| merge \| task \|... | move | rules/branches.md:36 | unchanged words, read at the moment of its file |
| 164 | 180 | RELEASE SMOKE after every release: a fresh session uses the released version for real (start, one subagent ... | move | rules/branches.md:37 | unchanged words, read at the moment of its file |
| 165 | 181 | Four kinds of request, one line each: | move | rules/checks.md:47 | unchanged words, read at the moment of its file |
| 166 | 182 | Refactor (no behaviour change): BUILD + RELATED TESTS; no new examples, the existing tests are the acceptance | move | rules/checks.md:48 | unchanged words, read at the moment of its file |
| 167 | 183 | Urgent fix (production is broken): the URGENT FIX path above | reword | rules/checks.md:49 | 'above' -> the file that now holds it (pointer fix) |
| 168 | 184 | Rollback: back to the last green commit; BUILD + RELATED TESTS of the reverted files; a database change fol... | move | rules/checks.md:50 | unchanged words, read at the moment of its file |
| 169 | 185 | Research only (no diff): no blocks; the report is the deliverable | move | rules/checks.md:51 | unchanged words, read at the moment of its file |
| 170 | 186 | Repo facts live in the committed `agent_repo.conf`, written by init and kept by agents; a human may edit it... | move | rules/checks.md:52 | unchanged words, read at the moment of its file |
| 171 | 187 | After each bug fix the fixing agent asks "which example would have shown it" and adds one line with `agent-... | move | rules/checks.md:53 | unchanged words, read at the moment of its file |
| 172 | 188 | Beyond the reviewer's PR REVIEW, a second agent's opinion only for CORE REVIEW, or when someone wants a too... | move | rules/checks.md:54 | unchanged words, read at the moment of its file |
| 173 | 189 | A requirement table copies its defaults from the released template and lists every changed default for the ... | move | rules/checks.md:55 | unchanged words, read at the moment of its file |
| 174 | 193 | W1. Finish in one run | keep | PRINCIPLES.md:40 | unchanged words, always loaded |
| 175 | 194 | Never wait for the human, except: the kick-off round, a mock yes, an OWNER SIGN, NEEDS HUMAN E2E | keep | PRINCIPLES.md:41 | unchanged words, always loaded |
| 176 | 195 | Unknown → pick default, log it, continue | keep | PRINCIPLES.md:42 | unchanged words, always loaded |
| 177 | 196 | Only owner-level or irreversible calls stop the line | keep | PRINCIPLES.md:42 | unchanged words, always loaded |
| 178 | 197 | A rule and reality collide → report the collision, never route around it | keep | PRINCIPLES.md:43 | unchanged words, always loaded |
| 179 | 198 | New ideas → `agent_ideas.txt` (R6), never in the work or the report, except the CLOSE CASE report (W13), wh... | keep | PRINCIPLES.md:44 | unchanged words, always loaded |
| 180 | 200 | W2. UI | move | rules/ui.md:4 | unchanged words, read at the moment of its file |
| 181 | 201 | Clickable mock first (prototype artifact) | move | rules/ui.md:5 | unchanged words, read at the moment of its file |
| 182 | 202 | Start from a screenshot of the existing real page (Claude in Chrome); change only what the task changes. Ne... | move | rules/ui.md:6 | unchanged words, read at the moment of its file |
| 183 | 203 | No existing page to screenshot → the mock follows the project's current style (theme, components); the agen... | move | rules/ui.md:7 | unchanged words, read at the moment of its file |
| 184 | 204 | Human says yes | move | rules/ui.md:8 | unchanged words, read at the moment of its file |
| 185 | 205 | A mock only for a new page or a whole-page re-layout; the approved mock is what UI CHECK compares with (R8) | move | rules/ui.md:9 | unchanged words, read at the moment of its file |
| 186 | 206 | The approved mock is the acceptance criterion of the task | move | rules/ui.md:10 | unchanged words, read at the moment of its file |
| 187 | 207 | Then real code | move | rules/ui.md:11 | unchanged words, read at the moment of its file |
| 188 | 209 | W3. TDD | move | rules/tests.md:7 | unchanged words, read at the moment of its file |
| 189 | 210 | Task manager writes the failing tests → worker writes code → tests pass | move | rules/tests.md:8 | unchanged words, read at the moment of its file |
| 190 | 211 | Workers never write tests. Task managers never write product code | reword | PRINCIPLES.md:21 | merged into the core's role-limits line; rules/tests.md W3 points to it |
| 191 | 212 | No test = not started | move | rules/tests.md:10 | unchanged words, read at the moment of its file |
| 192 | 213 | Full lane only; fast lane → R1 | move | rules/tests.md:11 | unchanged words, read at the moment of its file |
| 193 | 215 | W4. Multi-agent tests | move | rules/tests.md:13 | unchanged words, read at the moment of its file |
| 194 | 216 | Tests are organised module → feature | move | rules/tests.md:14 | unchanged words, read at the moment of its file |
| 195 | 217 | No task runs the full suite (owner 1A 2026-11-25) | merge with 150 | rules/checks.md:42 | same words in R8 |
| 196 | 218 | Which tests run follows the blocks (R8): the light RELATED TESTS and GUARD TESTS per task; MODULE TESTS onl... | move | rules/tests.md:15 | unchanged words, read at the moment of its file |
| 197 | 219 | Every test run goes through `agent-test-run.sh` (S5) | move | rules/tests.md:16 | unchanged words, read at the moment of its file |
| 198 | 220 | The main manager and the merge deputy never re-run tests the task manager already passed. Only on a merge c... | move | rules/tests.md:17 | unchanged words, read at the moment of its file |
| 199 | 221 | After a bounce: re-run only the tests that failed, not the suite | move | rules/tests.md:18 | unchanged words, read at the moment of its file |
| 200 | 223 | W5. Web UI testing | move | rules/ui.md:13 | unchanged words, read at the moment of its file |
| 201 | 224 | Claude in Chrome, not Playwright, on orca and plain | move | rules/ui.md:14 | unchanged words, read at the moment of its file |
| 202 | 225 | The check deputy (`agents/check-deputy.md`) drives the browser for FLOW CHECK, UI CHECK and RELEASE SMOKE, ... | move | rules/ui.md:15 | unchanged words, read at the moment of its file |
| 203 | 226 | Others write the click path and hand it to the main manager, who sends the check deputy | move | rules/ui.md:16 | unchanged words, read at the moment of its file |
| 204 | 227 | Unit tests are not proof of a flow a user can reach: FLOW CHECK is (R8) | move | rules/ui.md:17 | unchanged words, read at the moment of its file |
| 205 | 228 | Builders never verify their own work: they ship a click path, someone who did not build it drives the UI | keep | PRINCIPLES.md:48 | unchanged words, always loaded |
| 206 | 229 | What a browser cannot prove goes on a standing "needs a real device" list, never counted as verified | move | rules/ui.md:18 | unchanged words, read at the moment of its file |
| 207 | 230 | UI CHECK: the real page against the approved mock or the before screenshot, item by item (layout, content, ... | move | rules/ui.md:19 | unchanged words, read at the moment of its file |
| 208 | 231 | A layout, content or behaviour difference = not done, back to the builder | move | rules/ui.md:20 | unchanged words, read at the moment of its file |
| 209 | 232 | A difference from the real UI theme (colours, fonts, spacing tokens) is fine: keep the real theme, list it ... | move | rules/ui.md:21 | unchanged words, read at the moment of its file |
| 210 | 233 | The owner says pass = pass; agents follow his final decision. Only a critical problem (crash, wrong data, s... | move | rules/ui.md:22 | unchanged words, read at the moment of its file |
| 211 | 234 | Ask `agent-runtime.sh browser` first: chrome, headless or none | move | rules/ui.md:23 | unchanged words, read at the moment of its file |
| 212 | 235 | cloud → headless Chromium via Playwright, the extension can never reach a VM | move | rules/ui.md:24 | unchanged words, read at the moment of its file |
| 213 | 236 | none → print the click path under NEEDS HUMAN E2E and stop, wait for the human. Never silent, never forever | move | rules/ui.md:25 | unchanged words, read at the moment of its file |
| 214 | 238 | W6. Roles | move | rules/roles.md:4 | unchanged words, read at the moment of its file |
| 215 | 239 | Main manager (the "Main manager model" setting) = the main chat. Assigns tasks, talks to the human, reports... | reword | rules/roles.md:5 | 'Nothing else' names its exceptions (R1, W7, an owner's direct order); decided by the main manager 2026-11-26, the owner can veto; the core's role-limits line points here |
| 216 | 240 | Fast-lane deputy (the "Helper model" setting) = `agents/fast-lane-deputy.md`, new one per small task: works... | move | rules/roles.md:6 | unchanged words, read at the moment of its file |
| 217 | 241 | Merge deputy (the "Helper model" setting) = `agents/merge-deputy.md`. Merges, then deletes branch and worktree | move | rules/roles.md:7 | unchanged words, read at the moment of its file |
| 218 | 242 | Reviewer (Reviewer model, default opus-5.5:high) = `agents/reviewer.md`: PR REVIEW of every task and CORE R... | move | rules/roles.md:8 | unchanged words, read at the moment of its file |
| 219 | 243 | Check deputy (the "Helper model" setting) = `agents/check-deputy.md`, read and browser tools only: FLOW CHE... | move | rules/roles.md:9 | unchanged words, read at the moment of its file |
| 220 | 244 | The main manager stays free for the human: it runs no long check itself; it sends the check deputy and gets... | move | rules/roles.md:10 | unchanged words, read at the moment of its file |
| 221 | 245 | Task manager (the "Task manager model" setting) = one agent per big feature, in its own worktree (exception... | move | rules/roles.md:11 | unchanged words, read at the moment of its file |
| 222 | 246 | It writes the tests, briefs workers, judges, verifies every worker result before reporting done to the main... | move | rules/roles.md:12 | unchanged words, read at the moment of its file |
| 223 | 247 | Worker (the "Helper model" setting) = `agents/worker.md`, subagent of a task manager. Writes code until the... | move | rules/roles.md:13 | unchanged words, read at the moment of its file |
| 224 | 248 | Managers never write product code. A defect goes back to the worker that wrote it, with evidence | reword | PRINCIPLES.md:21 | split: 'Managers never write product code' in the core; 'A defect goes back to the worker that wrote it, with evidence' stays in rules/roles.md |
| 225 | 249 | A main manager fix order to a task manager has a fixed shape: where, what is seen, what is expected, eviden... | move | rules/roles.md:15 | unchanged words, read at the moment of its file |
| 226 | 250 | Names: `bin/agent-name.sh` (SessionStart hook) shows `<repo> Manager`, `<feature> Task Manager`, `<repo> He... | move | rules/roles.md:16 | unchanged words, read at the moment of its file |
| 227 | 252 | W7. Big feature (> 2 hours) | move | rules/worktrees.md:4 | unchanged words, read at the moment of its file |
| 228 | 253 | Before opening a worktree: idle or done worktrees > 0 → deputy cleans them all first (W8) | move | rules/worktrees.md:5 | unchanged words, read at the moment of its file |
| 229 | 254 | A worktree needs Orca. `agent-runtime.sh kind` picks the shape | move | rules/worktrees.md:6 | unchanged words, read at the moment of its file |
| 230 | 255 | On Orca: read Orca's own guide first, `orca skills get --topic orca-cli --full --json`. Flags change: `orca... | move | rules/worktrees.md:7 | unchanged words, read at the moment of its file |
| 231 | 256 | Then new worktree | move | rules/worktrees.md:8 | unchanged words, read at the moment of its file |
| 232 | 257 | One task manager inside it | move | rules/worktrees.md:9 | unchanged words, read at the moment of its file |
| 233 | 258 | Task manager spawns workers as needed | move | rules/worktrees.md:10 | unchanged words, read at the moment of its file |
| 234 | 259 | plain or cloud → no worktree, no second terminal. Main manager runs the task itself with `Agent` subagents,... | move | rules/worktrees.md:11 | unchanged words, read at the moment of its file |
| 235 | 260 | Placement: every job goes to a connected machine first (the one with the most room by S3); the local machin... | move | rules/resources.md:5 | unchanged words, read at the moment of its file |
| 236 | 261 | The automatic nightly starts only where there is room, else it says so; the main manager places a nightly b... | move | rules/resources.md:6 | unchanged words, read at the moment of its file |
| 237 | 262 | While a connected machine exists the automatic nightly never runs the full suite locally; it says so and th... | move | rules/resources.md:7 | unchanged words, read at the moment of its file |
| 238 | 263 | One agent = one worktree = one branch = one terminal. Push at every stage | move | rules/worktrees.md:12 | unchanged words, read at the moment of its file |
| 239 | 265 | W8. Merge and cleanup | move | rules/worktrees.md:14 | unchanged words, read at the moment of its file |
| 240 | 266 | The merge deputy merges into the working branch (ap-main-<name>) in the main checkout | move | rules/worktrees.md:15 | unchanged words, read at the moment of its file |
| 241 | 267 | A task with target production goes straight in through `agent-promote.sh --task`: a short-lived worktree of... | move | rules/worktrees.md:16 | unchanged words, read at the moment of its file |
| 242 | 268 | After any direct merge into production, production is merged back into the working branch at once, so they ... | move | rules/worktrees.md:17 | unchanged words, read at the moment of its file |
| 243 | 269 | The merge deputy runs `agent-file.sh checks gate <task>` first: GATE REFUSED → no merge, the task goes back | move | rules/worktrees.md:18 | unchanged words, read at the moment of its file |
| 244 | 270 | Deputy deletes the branch (local + remote) and the worktree right after merge | move | rules/worktrees.md:19 | unchanged words, read at the moment of its file |
| 245 | 271 | Never `git reset --hard` in the main checkout: it wipes the uncommitted agent_*.txt | keep | PRINCIPLES.md:51 | unchanged words, always loaded |
| 246 | 272 | Every merge ends with cleanup, in every case: a task manager pane, a subagent's git worktree, a human-direc... | move | rules/worktrees.md:20 | unchanged words, read at the moment of its file |
| 247 | 273 | The worktree line of a merged task is always removed or rewritten at merge, also when the folder stays | move | rules/worktrees.md:21 | unchanged words, read at the moment of its file |
| 248 | 274 | human-direct protects only the human's own session pane; the sweep never closes a Claude pane, only a shell... | move | rules/worktrees.md:22 | unchanged words, read at the moment of its file |
| 249 | 275 | The sweep prunes a LAUNCH record whose pid is dead or whose pane is gone; its table never lists main or the... | move | rules/worktrees.md:23 | unchanged words, read at the moment of its file |
| 250 | 276 | The plain list shows what --apply would remove; --apply is main manager only | move | rules/worktrees.md:24 | unchanged words, read at the moment of its file |
| 251 | 277 | Whatever is sent to another machine is cleaned up there when it is done: pane, worktree, branches, scratch ... | move | rules/worktrees.md:25 | unchanged words, read at the moment of its file |
| 252 | 278 | The sweep covers every connected machine and its list names what is left there | move | rules/worktrees.md:26 | unchanged words, read at the moment of its file |
| 253 | 279 | Never skip cleanup | move | rules/worktrees.md:27 | unchanged words, read at the moment of its file |
| 254 | 280 | Main manager verified + waiting for the owner's yes → agent-file.sh checks gather first, close the task man... | move | rules/worktrees.md:28 | unchanged words, read at the moment of its file |
| 255 | 281 | Owner yes → merge deputy merges the branch. Owner no → a new task manager from that branch. Goal: work all ... | move | rules/worktrees.md:29 | unchanged words, read at the moment of its file |
| 256 | 282 | Delete the branch and close the todo line only after the merge is verified | move | rules/worktrees.md:30 | unchanged words, read at the moment of its file |
| 257 | 283 | Meanwhile the pane and the worktree may go while waiting for the owner's yes; the pushed branch stays | move | rules/worktrees.md:31 | unchanged words, read at the moment of its file |
| 258 | 284 | Deputy runs `bin/agent-file.sh worktree rm <path>` and `bin/agent-file.sh todo done <name>` with the facts ... | move | rules/worktrees.md:32 | unchanged words, read at the moment of its file |
| 259 | 285 | Sweep: `bin/agent-cleanup.sh --apply` after every merge, at session start and when the last open task close... | move | rules/worktrees.md:33 | unchanged words, read at the moment of its file |
| 260 | 286 | Housekeep: every housekeep_interval_min minutes (default 120, 0 = off) `agent-watch.sh --all` runs `bin/age... | move | rules/worktrees.md:34 | unchanged words, read at the moment of its file |
| 261 | 287 | The housekeep pass runs `agent-file.sh state trim` on the main repo's agent_state.txt before it writes its ... | move | rules/worktrees.md:35 | unchanged words, read at the moment of its file |
| 262 | 288 | The main manager reads the HOUSEKEEP block in agent_state.txt at its next activity. Per suspect: `idea rm <... | move | rules/worktrees.md:36 | unchanged words, read at the moment of its file |
| 263 | 289 | It then acts on the other flags of the block | move | rules/worktrees.md:37 | unchanged words, read at the moment of its file |
| 264 | 290 | Main manager only. Task managers, Helpers and workers never run it | move | rules/worktrees.md:38 | unchanged words, read at the moment of its file |
| 265 | 291 | Own repo only: this machine and every paired Orca machine | move | rules/worktrees.md:39 | unchanged words, read at the moment of its file |
| 266 | 292 | Removes only safe items: merged into the working branch or the production branch (origin/main here), no liv... | move | rules/worktrees.md:40 | unchanged words, read at the moment of its file |
| 267 | 293 | Everything else is never deleted: one table to the human (what, where, why kept, suggestion) | move | rules/worktrees.md:41 | unchanged words, read at the moment of its file |
| 268 | 294 | A done pane (finished, idle) in a kept worktree: closed when its task is done or dropped, or its line is go... | move | rules/worktrees.md:42 | unchanged words, read at the moment of its file |
| 269 | 295 | A paired machine unreachable → one line, skipped. Never hangs the start | move | rules/worktrees.md:43 | unchanged words, read at the moment of its file |
| 270 | 297 | W9. Task routing (main manager, before every dispatch) | move | rules/routing.md:4 | unchanged words, read at the moment of its file |
| 271 | 298 | Read `agent_worktree.txt` first | move | rules/routing.md:5 | unchanged words, read at the moment of its file |
| 272 | 299 | Small task (fast lane) → a new deputy subagent in its own git worktree (Agent isolation worktree); it pushe... | move | rules/routing.md:6 | unchanged words, read at the moment of its file |
| 273 | 300 | Several small tasks run side by side and never share a checkout (owner 1A 2026-11-25; 21 tasks done this wa... | move | rules/routing.md:7 | unchanged words, read at the moment of its file |
| 274 | 301 | A new task gets its own branch and its own agent, also when it touches a live worktree's module in a differ... | move | rules/routing.md:8 | unchanged words, read at the moment of its file |
| 275 | 302 | A follow-up on the logic a live task manager is changing right now must go to that task manager (P1), never... | move | rules/routing.md:9 | unchanged words, read at the moment of its file |
| 276 | 303 | Task manager in final stage (compiling worker results) → do not disturb. Hold the task until it finishes | move | rules/routing.md:10 | unchanged words, read at the moment of its file |
| 277 | 304 | Otherwise → new worktree (W7). Never an Orca worktree and a task manager for a small task | move | rules/routing.md:11 | unchanged words, read at the moment of its file |
| 278 | 305 | `todo done <X>` releases every task queued after X | move | rules/routing.md:12 | unchanged words, read at the moment of its file |
| 279 | 306 | The main manager runs `agent-file.sh next` at every wake (a report, a watch signal, a human message) and di... | move | rules/routing.md:13 | unchanged words, read at the moment of its file |
| 280 | 307 | A task waits only for a real dependency: it needs code that another open task brings (shared first, below) | move | rules/routing.md:14 | unchanged words, read at the moment of its file |
| 281 | 308 | A task the owner already approved needs no new question | move | rules/routing.md:15 | unchanged words, read at the moment of its file |
| 282 | 309 | A new worktree or pane goes to the connected machine first that has room (W7, S3) | move | rules/routing.md:16 | unchanged words, read at the moment of its file |
| 283 | 310 | Target and base (R1; his words by the approval cases of R8): a task that goes straight to production branch... | move | rules/routing.md:17 | unchanged words, read at the moment of its file |
| 284 | 311 | The target is per task, not per request: an urgent task branches from the production branch and merges stra... | move | rules/routing.md:18 | unchanged words, read at the moment of its file |
| 285 | 312 | Before dispatch: does an urgent task need code that only a non-urgent one brings? Yes -> it cannot ship alo... | move | rules/routing.md:19 | unchanged words, read at the moment of its file |
| 286 | 313 | A new request may also wait until the working branch is tested and published; the main manager picks what i... | move | rules/routing.md:20 | unchanged words, read at the moment of its file |
| 287 | 314 | Shared first: before parallel features, find the code they share (models, components, APIs); the shared par... | move | rules/routing.md:21 | unchanged words, read at the moment of its file |
| 288 | 315 | The todo line comes first: `todo add` before the worktree, the pane or any agent. The guard refuses a main ... | move | rules/routing.md:22 | unchanged words, read at the moment of its file |
| 289 | 317 | W10. Second session in the same repo | move | rules/roles.md:18 | unchanged words, read at the moment of its file |
| 290 | 318 | One main manager per repo. `agent-start.sh` keeps a lock in the shared git dir: pid, date, session id, term... | move | rules/roles.md:19 | unchanged words, read at the moment of its file |
| 291 | 319 | Lock owner alive → this session is a task manager (human-direct). Never a second main manager | move | rules/roles.md:20 | unchanged words, read at the moment of its file |
| 292 | 320 | Its start text names the main manager: pid, `<repo> Manager`, terminal | move | rules/roles.md:21 | unchanged words, read at the moment of its file |
| 293 | 321 | Human wants this session as main manager → the human types `! agent-start.sh --take-over` (full path in the... | move | rules/roles.md:22 | unchanged words, read at the moment of its file |
| 294 | 322 | Human-direct = only a session the human opened by hand. Agent-spawned agents are never human-direct. They r... | move | rules/roles.md:23 | unchanged words, read at the moment of its file |
| 295 | 323 | A human-direct session keeps its protection only while the human alone drives it. Once it takes a task from... | move | rules/roles.md:24 | unchanged words, read at the moment of its file |
| 296 | 324 | The merge of its last open task closes its pane and removes its line, like a task manager; the close messag... | move | rules/roles.md:25 | unchanged words, read at the moment of its file |
| 297 | 325 | At start: the script adds a line to `agent_worktree.txt` (status human-direct). Also send the main manager ... | move | rules/roles.md:26 | unchanged words, read at the moment of its file |
| 298 | 326 | Will change files → open its own worktree first (W7). Only looking → no worktree | move | rules/roles.md:27 | unchanged words, read at the moment of its file |
| 299 | 327 | Human talks to it directly for now. All task manager rules still apply | move | rules/roles.md:28 | unchanged words, read at the moment of its file |
| 300 | 328 | Human says "finish" or "report to main manager" → report done + click path to the main manager, then act as... | move | rules/roles.md:29 | unchanged words, read at the moment of its file |
| 301 | 329 | Finished with nothing to merge → main manager runs `bin/agent-file.sh worktree rm <path>` | move | rules/roles.md:30 | unchanged words, read at the moment of its file |
| 302 | 330 | The main manager closes every human-direct session after the human says finish: `orca terminal close --term... | move | rules/roles.md:31 | unchanged words, read at the moment of its file |
| 303 | 331 | Lock owner dead → take over as main manager, run recovery (S7) | move | rules/roles.md:32 | unchanged words, read at the moment of its file |
| 304 | 332 | Talk between sessions: `ListAgents` → find the peer by its name (W6), not listed → the row named after its ... | move | rules/roles.md:33 | unchanged words, read at the moment of its file |
| 305 | 333 | Open a second session with the same permission mode and effort as the main manager (`<mode>` from `agent-se... | move | rules/roles.md:34 | unchanged words, read at the moment of its file |
| 306 | 334 | New terminals (dispatch, resume, a Helper, a city click) use the "Permissions: Permission mode" setting, re... | move | rules/roles.md:35 | unchanged words, read at the moment of its file |
| 307 | 335 | Task name: every new or switched task, a plain question too, gets its name first, even before the quiz PASS... | move | rules/roles.md:36 | unchanged words, read at the moment of its file |
| 308 | 337 | W11. Time | move | rules/time.md:4 | unchanged words, read at the moment of its file |
| 309 | 338 | Every task gets an estimate in minutes before dispatch, on its todo line | move | rules/time.md:5 | unchanged words, read at the moment of its file |
| 310 | 339 | Write your own guess in minutes first, then `estimate ... --guess <m>`; est and guess both go on the todo l... | move | rules/time.md:6 | unchanged words, read at the moment of its file |
| 311 | 340 | Estimate = agent work only. Waiting is not work: mock gate, owner question, owner review, hold, suite run | move | rules/time.md:7 | unchanged words, read at the moment of its file |
| 312 | 341 | Every done report has one line: `TIME: est <n>m, actual <n>m, wait <n>m`. Actual = agent work only | move | rules/time.md:8 | unchanged words, read at the moment of its file |
| 313 | 342 | Done = merged and cleaned. The main manager passes work, wait and the task facts to `bin/agent-file.sh todo... | move | rules/time.md:9 | unchanged words, read at the moment of its file |
| 314 | 343 | Work over 2× estimate → say it in the report, never silent | move | rules/time.md:10 | unchanged words, read at the moment of its file |
| 315 | 344 | Time comes from `date`, never guessed (a remote machine's clock can drift) | move | rules/time.md:11 | unchanged words, read at the moment of its file |
| 316 | 345 | Scope grows → re-estimate, on the record | move | rules/time.md:12 | unchanged words, read at the moment of its file |
| 317 | 346 | Before a new estimate: `bin/agent-file.sh time`, then `bin/agent-file.sh estimate` (dispatch skill) | move | rules/time.md:13 | unchanged words, read at the moment of its file |
| 318 | 347 | A time question from the human → a duration AND a clock time, and when he is needed next: `bin/agent-file.s... | move | rules/time.md:14 | unchanged words, read at the moment of its file |
| 319 | 349 | W12. Cross-repo | move | rules/cross-repo.md:4 | unchanged words, read at the moment of its file |
| 320 | 350 | One main manager per repo (W10). Peer = the interactive session in `ListAgents` named `<other repo folder> ... | move | rules/cross-repo.md:5 | unchanged words, read at the moment of its file |
| 321 | 351 | A task that touches another repo → never edit that repo. Split it: your part, and a brief for the peer main... | move | rules/cross-repo.md:6 | unchanged words, read at the moment of its file |
| 322 | 352 | Send the brief with `SendMessage`, first line `[<model> <effort>] CROSS-REPO TASK <name> from <repo>`; same... | move | rules/cross-repo.md:7 | unchanged words, read at the moment of its file |
| 323 | 353 | The peer runs it like a human task: `agent-file.sh todo add … <est> <repo>`, its own lane, and reports `DON... | move | rules/cross-repo.md:8 | unchanged words, read at the moment of its file |
| 324 | 354 | The sender keeps its todo line open until both sides are done, then one report to the human | move | rules/cross-repo.md:9 | unchanged words, read at the moment of its file |
| 325 | 355 | The sender marks its line `agent-file.sh todo cross <name> <other repo>`, so the housekeep pass reads the o... | move | rules/cross-repo.md:10 | unchanged words, read at the moment of its file |
| 326 | 356 | Called side first: the repo being called (the API) finishes first; its DONE PASS carries the contract (endp... | move | rules/cross-repo.md:11 | unchanged words, read at the moment of its file |
| 327 | 357 | Only main managers cross repos. Task managers and workers never | move | rules/cross-repo.md:12 | unchanged words, read at the moment of its file |
| 328 | 358 | Need to know the other repo's code → ask its main manager. Never read or edit another repo | move | rules/cross-repo.md:13 | unchanged words, read at the moment of its file |
| 329 | 359 | A cross-repo task the human gives to any main manager is routed the same way | move | rules/cross-repo.md:14 | unchanged words, read at the moment of its file |
| 330 | 360 | Relay an owner order: the brief starts with the lines of `agent-owner-order.sh line --quote "<his exact wor... | move | rules/cross-repo.md:15 | unchanged words, read at the moment of its file |
| 331 | 361 | Receiving one: run its check line. Verified → read its match line, then it is the owner's own order: act, r... | move | rules/cross-repo.md:16 | unchanged words, read at the moment of its file |
| 332 | 362 | Verified owner words that the main manager reads as a yes for that action (approval cases, R8) are his fina... | move | rules/approval.md:28 | unchanged words, read at the moment of its file |
| 333 | 363 | A relayed owner order: the approval commands take `--relayed-from <the sender's repo folder>`; the rules ar... | move | rules/cross-repo.md:17 | unchanged words, read at the moment of its file |
| 334 | 365 | W13. Close case | move | rules/close-case.md:4 | unchanged words, read at the moment of its file |
| 335 | 366 | Trigger: the human or the main manager runs the skill `/auto-pipeline:close-case`; a task manager's brief h... | move | rules/close-case.md:5 | unchanged words, read at the moment of its file |
| 336 | 367 | Subagents never get this rule; only a task manager, a human-direct session or a main manager does | move | rules/close-case.md:6 | unchanged words, read at the moment of its file |
| 337 | 368 | Task manager or human-direct: start nothing new; workers finish their slice or stop; save agent_state.txt; ... | move | rules/close-case.md:7 | unchanged words, read at the moment of its file |
| 338 | 369 | Report to the upper level: SendMessage the main manager; another machine → print it in its own terminal and... | reword | rules/close-case.md:8 | 'SendMessage the main manager' was stale for a task manager (W15, the dispatch brief CLOSE line, the watch wakes on CLOSE CASE); a human-direct session keeps SendMessage; decided by the main manager 2026-11-26, the owner can veto |
| 339 | 370 | Report first line `CLOSE CASE <name>: finished` or `CLOSE CASE <name>: unfinished`, then done, left + next ... | move | rules/close-case.md:9 | unchanged words, read at the moment of its file |
| 340 | 371 | Then wait for the upper decision. Never close itself. A close case from the main manager counts the same as... | move | rules/close-case.md:10 | unchanged words, read at the moment of its file |
| 341 | 372 | Main manager gets a CLOSE CASE report: finished → merge skill. Unfinished → review, then finish first (DONE... | move | rules/close-case.md:11 | unchanged words, read at the moment of its file |
| 342 | 373 | Log every decision in its agent_state.txt. Human away → decide by the requirement doc, mark it "owner not s... | move | rules/close-case.md:12 | unchanged words, read at the moment of its file |
| 343 | 374 | Main manager gets close case from the human = the whole repo: close case to every live task manager and hum... | move | rules/close-case.md:13 | unchanged words, read at the moment of its file |
| 344 | 375 | Collect every report, decide each, merge what passes, close all panes and worktrees, stop its own crons, up... | move | rules/close-case.md:14 | unchanged words, read at the moment of its file |
| 345 | 376 | Then one final table to the human: task, result, what changed, what is left, decisions taken for the human.... | move | rules/close-case.md:15 | unchanged words, read at the moment of its file |
| 346 | 377 | After the table the main manager asks the human, in his language: clean this session for the next round, ye... | move | rules/close-case.md:16 | unchanged words, read at the moment of its file |
| 347 | 378 | Yes: `agent-start.sh --clean` (archives agent_state.txt, writes a short fresh one, says what still runs), t... | move | rules/close-case.md:17 | unchanged words, read at the moment of its file |
| 348 | 379 | Rare, the human wants this session to stop being main manager: he types `! agent-start.sh --release`; the a... | move | rules/close-case.md:18 | unchanged words, read at the moment of its file |
| 349 | 381 | W14. Todo board | move | rules/board.md:4 | unchanged words, read at the moment of its file |
| 350 | 382 | Trigger: the human runs the skill `/auto-pipeline:todo`; the skill holds this rule per role | move | rules/board.md:5 | unchanged words, read at the moment of its file |
| 351 | 383 | One script, no agent: `bin/agent-file.sh board`. Show its table as printed, every row, then the decide sect... | move | rules/board.md:6 | unchanged words, read at the moment of its file |
| 352 | 384 | Main manager: the whole repo. Task manager or Helper: `board --self`, its own task and its workers only. Su... | move | rules/board.md:7 | unchanged words, read at the moment of its file |
| 353 | 385 | Rows: open tasks, waits on the owner (mock check, owner question, owner review), `OWNER TODO:` and `PARKED:... | move | rules/board.md:8 | unchanged words, read at the moment of its file |
| 354 | 386 | Status of a wait: `waiting <who> · <what> · waited <n>`, held `hold · <what> · waited <n>`, queued `queue ·... | move | rules/board.md:9 | unchanged words, read at the moment of its file |
| 355 | 387 | Sort: waiting on the owner, running, waiting on others, queued and not started, held, OWNER TODO, parked qu... | move | rules/board.md:10 | unchanged words, read at the moment of its file |
| 356 | 388 | Times come from the files, never guessed. Work counts from the first stage minus later waits. Waited: since... | move | rules/board.md:11 | unchanged words, read at the moment of its file |
| 357 | 389 | Progress: `agent-file.sh todo stage <name> <stage> [i/m]` at each step boundary. | move | rules/board.md:12 | unchanged words, read at the moment of its file |
| 358 | 390 | Stages, task manager: brief register mock tests workers verify push report. Main manager: e2e (the review a... | move | rules/board.md:13 | unchanged words, read at the moment of its file |
| 359 | 391 | Stage weights are fixed (`bin/agent_conf.py`) | move | rules/board.md:14 | unchanged words, read at the moment of its file |
| 360 | 392 | Live: `board --watch` · `statusline` on or off, 5 lines at most (a warning line counts), queued/held/not st... | move | rules/board.md:15 | unchanged words, read at the moment of its file |
| 361 | 393 | Record as it happens: `todo wait <name> on <kind> ["<note>"] [--who <name>] [--after <task>]\|off` at every... | move | rules/board.md:16 | unchanged words, read at the moment of its file |
| 362 | 394 | `park add` for a parked question (H1); `OWNER TODO:` lines are written with `agent-file.sh state add` | move | rules/board.md:17 | unchanged words, read at the moment of its file |
| 363 | 395 | `agent-guard.sh` records launches by task. The "Rules: Todo before agent" setting, on (default), refuses a ... | move | rules/board.md:18 | unchanged words, read at the moment of its file |
| 364 | 396 | `worker on`: no hooks only. | move | rules/board.md:19 | unchanged words, read at the moment of its file |
| 365 | 398 | W15. Watch | move | rules/watch.md:4 | unchanged words, read at the moment of its file |
| 366 | 399 | After a watch wake the first action is to start the watch again, then handle the signal | move | rules/watch.md:5 | unchanged words, read at the moment of its file |
| 367 | 400 | The watch also wakes the main manager when there is room for a queued task (WATCH ROOM) | move | rules/watch.md:6 | unchanged words, read at the moment of its file |
| 368 | 401 | A board warning (watch not running, not confirmed, a pane without a task line) reaches the main manager thr... | move | rules/watch.md:7 | unchanged words, read at the moment of its file |
| 369 | 402 | Stall detection is the watch: each sweep reads the pane screen and the `agent_state.txt` file; 3 sweeps wit... | move | rules/watch.md:8 | unchanged words, read at the moment of its file |
| 370 | 403 | Verify every launch within 2 min | move | rules/watch.md:9 | unchanged words, read at the moment of its file |
| 371 | 404 | One `agent-watch.sh --all` in the background (Bash run_in_background) watches every task manager, local and... | move | rules/watch.md:10 | unchanged words, read at the moment of its file |
| 372 | 405 | A task manager's HEARTBEAT, ACK, report and question go into `agent_state.txt` only, never SendMessage; onl... | move | rules/watch.md:11 | unchanged words, read at the moment of its file |
| 373 | 406 | DONE FAIL → the main manager reviews the report, then sends the task manager a fix order (where, what is se... | move | rules/watch.md:12 | unchanged words, read at the moment of its file |
| 374 | 407 | LOST (the watch cannot reach a machine or a pane) → wait one more sweep; still lost → tell the owner in one... | move | rules/watch.md:13 | unchanged words, read at the moment of its file |
| 375 | 408 | Never redispatch a LOST task on another machine by itself | move | rules/watch.md:14 | unchanged words, read at the moment of its file |
| 376 | 409 | The watch carries a task's stage to the main repo from the newest STAGE line or HEARTBEAT step (0-7 = brief... | move | rules/watch.md:15 | unchanged words, read at the moment of its file |
| 377 | 410 | A manager at its idle prompt while its own background run goes (pane shows shells or monitors, or its newes... | move | rules/watch.md:16 | unchanged words, read at the moment of its file |
| 378 | 411 | Long text to a task manager: `agent-file.sh tell <task> "<msg>"` (the block goes into its file, one pointer... | move | rules/watch.md:17 | unchanged words, read at the moment of its file |
| 379 | 412 | Start and resume print the `agent-watch.sh --all` command when no watch runs | move | rules/watch.md:18 | unchanged words, read at the moment of its file |
| 380 | 413 | The board says `not confirmed <n>m` when a task is not watched or has been quiet | move | rules/watch.md:19 | unchanged words, read at the moment of its file |
| 381 | 414 | A stall → nudge once, wait 10 min, then salvage (commit what is there) and redispatch | move | rules/watch.md:20 | unchanged words, read at the moment of its file |
| 382 | 415 | Every brief says how to report, how to ask, how to report done (pass/fail) and the heartbeat | move | rules/watch.md:21 | unchanged words, read at the moment of its file |
| 383 | 417 | W16. Known traps | move | rules/traps.md:4 | unchanged words, read at the moment of its file |
| 384 | 418 | A push to the working branch denied by the auto-mode classifier → never retry or work around | move | rules/traps.md:5 | unchanged words, read at the moment of its file |
| 385 | 419 | Hand the owner one `! git push ...` line, or ask for an allow rule (init prints `Bash(git push origin <work... | move | rules/traps.md:6 | unchanged words, read at the moment of its file |
| 386 | 420 | A cross-session message held because permission modes differ → say so, ask the owner to click Deliver, neve... | move | rules/traps.md:7 | unchanged words, read at the moment of its file |
| 387 | 421 | MODE MISMATCH line at start (this session's mode differs from the Permission mode setting) → tell the owner... | move | rules/traps.md:8 | unchanged words, read at the moment of its file |
| 388 | 422 | Remote Orca pane: a long `terminal send` (~4 KB) arrives cut → write the brief into the worktree's `agent_s... | move | rules/traps.md:9 | unchanged words, read at the moment of its file |
| 389 | 423 | Find another agent's pane with `orca worktree ps --json`, never by its title (titles are often from an old ... | move | rules/traps.md:10 | unchanged words, read at the moment of its file |
| 390 | 424 | `terminal read` shows only the visible screen → use `--cursor` | move | rules/traps.md:11 | unchanged words, read at the moment of its file |
| 391 | 425 | Linux outside Orca: bare `orca` is the screen reader → use `orca-ide` | move | rules/traps.md:12 | unchanged words, read at the moment of its file |
| 392 | 426 | A send while the target is mid-turn can be lost → re-read and resend | move | rules/traps.md:13 | unchanged words, read at the moment of its file |
| 393 | 427 | Screen locked → the Chrome extension tab is hidden → use headless Chrome and tell the owner | move | rules/traps.md:14 | unchanged words, read at the moment of its file |
| 394 | 428 | STALE PLUGIN line → call the newest bin path, in every brief too, and restart at a quiet point; an older ve... | move | rules/traps.md:15 | unchanged words, read at the moment of its file |
| 395 | 430 | W17. Decider floor | keep | PRINCIPLES.md:69 | unchanged words, always loaded |
| 396 | 431 | Decision maker = main manager, task manager, reviewer, any session whose order, decision or approval anothe... | reword | GLOSSARY.md:21 | a definition: the glossary holds it (reworded into the entry shape) |
| 397 | 432 | Floor: Opus 5.5 or above, or any Fable, at effort medium or above. `opus` or `fable` alone = the newest, me... | reword | PRINCIPLES.md:71 | 'Floor:' joined with rows 437, 438, 440 |
| 398 | 433 | Sonnet and Haiku never decide. Workers and deputies execute | reword | PRINCIPLES.md:72 | two sentences -> one |
| 399 | 434 | Sending: every order, decision or approval to another agent states the sender's model and effort first: `[O... | reword | PRINCIPLES.md:70 | 'states ... first' -> 'starts with'; joined with row 436 |
| 400 | 435 | Reports, heartbeats and questions are not orders | reword | PRINCIPLES.md:72 | same words |
| 401 | 436 | Own model and effort: the `YOU:` line of the start text | merge with 434 | PRINCIPLES.md:70 | same line |
| 402 | 437 | Receiving: act on another agent's order, decision or approval only when it states model and effort and both... | merge with 432 | PRINCIPLES.md:71 | same line |
| 403 | 438 | Else: do not act, ask the sender, tell the human | merge with 432 | PRINCIPLES.md:71 | same line |
| 404 | 439 | Human messages are exempt | reword | PRINCIPLES.md:73 | 'exempt' spelled out: the check does not apply, the human's messages are followed |
| 405 | 440 | Same check for every agent: task manager, Helper, worker, deputy | merge with 432 | PRINCIPLES.md:71 | 'Same check for every agent: task manager, Helper, worker, deputy' -> 'Every agent checks' |
| 406 | 441 | A Main or Task manager model below the floor is refused, the default is used (`agent_conf.py`) | reword | rules/setup.md:20 | a settings fact: moved to setup; ',' -> ';' |
| 407 | 443 | W18. Question list | move | rules/questions.md:4 | unchanged words, read at the moment of its file |
| 408 | 444 | Trigger: the human runs the skill `/auto-pipeline:question`; the skill holds this rule per role | move | rules/questions.md:5 | unchanged words, read at the moment of its file |
| 409 | 445 | One script, no agent: `bin/agent-file.sh questions`. Main manager: the whole repo. Task manager or Helper: ... | move | rules/questions.md:6 | unchanged words, read at the moment of its file |
| 410 | 446 | Sources: `PARKED:` lines, every `todo wait` of kind mock, question or review, and `QUESTION:` lines of agen... | move | rules/questions.md:7 | unchanged words, read at the moment of its file |
| 411 | 447 | A `QUESTION:` line is answered by an `ANSWER:` line after it, before the next QUESTION: line or "=== " head... | move | rules/questions.md:8 | unchanged words, read at the moment of its file |
| 412 | 448 | Each question has a stable id; its title, sub line, facts and lettered options come from `park add` fields ... | move | rules/questions.md:9 | unchanged words, read at the moment of its file |
| 413 | 449 | 10 or fewer: a numbered list in chat under the decide heading (H3), nothing dropped; the human answers like... | move | rules/questions.md:10 | unchanged words, read at the moment of its file |
| 414 | 450 | More than 10: `questions --page <file>` (a file in your scratchpad), publish it with the Artifact tool, cap... | move | rules/questions.md:11 | unchanged words, read at the moment of its file |
| 415 | 451 | `QUESTIONS PAGE:` line of agent_state.txt holds the url: one url per repo and session, publish with that ur... | move | rules/questions.md:12 | unchanged words, read at the moment of its file |
| 416 | 452 | No Artifact tool: the chat list of all, nothing dropped | move | rules/questions.md:13 | unchanged words, read at the moment of its file |
| 417 | 453 | Done: the human says 答完了, done or answered (or pastes `1A 2B`) while the page still has an open question. T... | move | rules/questions.md:14 | unchanged words, read at the moment of its file |
| 418 | 454 | Read all answers at once with ArtifactData (list, the answers collection) and the map file; pasted lines go... | move | rules/questions.md:15 | unchanged words, read at the moment of its file |
| 419 | 455 | Per answered question: `questions answer <id> "<answer>"`, then carry on. An unpicked question is still open | move | rules/questions.md:16 | unchanged words, read at the moment of its file |
| 420 | 456 | Headers and words in the Language setting | move | rules/questions.md:17 | unchanged words, read at the moment of its file |
| 421 | 460 | H1. One topic | move | rules/human.md:4 | unchanged words, read at the moment of its file |
| 422 | 461 | Ask only about the current task | move | rules/human.md:5 | unchanged words, read at the moment of its file |
| 423 | 462 | Edge-case question + read access to the real data → count first: how many records or companies it touches. ... | move | rules/human.md:6 | unchanged words, read at the moment of its file |
| 424 | 463 | Count is 0 or tiny → take the simplest default, state the count in one line, do not ask | move | rules/human.md:7 | unchanged words, read at the moment of its file |
| 425 | 464 | No read access → ask as before, say the count could not be checked. Never guess a count | move | rules/human.md:8 | unchanged words, read at the moment of its file |
| 426 | 465 | Prefer the simplest change that gives the same result over machinery the data does not need | move | rules/human.md:9 | unchanged words, read at the moment of its file |
| 427 | 466 | Park other questions | move | rules/human.md:10 | unchanged words, read at the moment of its file |
| 428 | 467 | Show them at the end, one table | move | rules/human.md:11 | unchanged words, read at the moment of its file |
| 429 | 468 | Ask everything while the human is here, in one batch | move | rules/human.md:12 | unchanged words, read at the moment of its file |
| 430 | 469 | Human gone → never block, park it. On return lead with one table: issue, evidence, blocks what, interim def... | move | rules/human.md:13 | unchanged words, read at the moment of its file |
| 431 | 471 | H2. Words | move | rules/human.md:15 | unchanged words, read at the moment of its file |
| 432 | 472 | Short sentences | move | rules/human.md:16 | unchanged words, read at the moment of its file |
| 433 | 473 | Common words | move | rules/human.md:17 | unchanged words, read at the moment of its file |
| 434 | 474 | Jargon only for code names | move | rules/human.md:18 | unchanged words, read at the moment of its file |
| 435 | 475 | Talk to the human in the language of the Language setting. Docs, code and rule text stay English | keep | PRINCIPLES.md:62 | unchanged words, always loaded |
| 436 | 476 | Never cite a rule by its code (W6, S8) to the human. Say what the rule means in plain words | keep | PRINCIPLES.md:63 | unchanged words, always loaded |
| 437 | 478 | H3. Report | move | rules/human.md:20 | unchanged words, read at the moment of its file |
| 438 | 479 | Result (pass/fail) | move | rules/human.md:21 | unchanged words, read at the moment of its file |
| 439 | 480 | What changed | move | rules/human.md:22 | unchanged words, read at the moment of its file |
| 440 | 481 | Every report, job summary, recap, proposal or audit to the human ends with a decide section | keep | PRINCIPLES.md:65 | unchanged words, always loaded |
| 441 | 482 | Heading in the Language setting: zh `## 要你决定`, en `## To decide`, other languages a short translation of "t... | move | rules/human.md:25 | unchanged words, read at the moment of its file |
| 442 | 483 | Open questions numbered, each with a recommendation (zh `建议`, en `Recommendation`) | keep | PRINCIPLES.md:66 | unchanged words, always loaded |
| 443 | 484 | Every question to the owner has a number in front; numbers never repeat within one message, and an open que... | move | rules/human.md:26 | unchanged words, read at the moment of its file |
| 444 | 485 | When every question is answered, the next new set starts again at 1. While any is open, open ones keep thei... | move | rules/human.md:27 | unchanged words, read at the moment of its file |
| 445 | 486 | Every open question is repeated in the decide section of every reply until the owner answers it, even when ... | move | rules/human.md:28 | unchanged words, read at the moment of its file |
| 446 | 487 | Each question stands alone: a reader who sees only that line knows what it is about and can decide | move | rules/human.md:29 | unchanged words, read at the moment of its file |
| 447 | 488 | A named thing (PR, task, branch, ticket, file) gets what it is in a few words: `#305 (stock lock settings p... | move | rules/human.md:30 | unchanged words, read at the moment of its file |
| 448 | 489 | A question names every task/PR/ticket by id AND its title, + the state + what is asked, e.g. "Task t10211 -... | move | rules/human.md:31 | unchanged words, read at the moment of its file |
| 449 | 490 | Per question: what, why it needs the human now, one line of evidence, then the recommendation. One or two l... | move | rules/human.md:32 | unchanged words, read at the moment of its file |
| 450 | 491 | Nothing open: keep the heading, one line: none (zh `无`) | move | rules/human.md:33 | unchanged words, read at the moment of its file |
| 451 | 492 | Every question the main manager puts to the owner in a decide section is recorded with `park add` (--why --... | move | rules/human.md:34 | unchanged words, read at the moment of its file |
| 452 | 493 | Few numbers. One table at most, five rows or fewer, unless the human asks for the full list | reword | rules/human.md:35 | clause added (the five-row cap is for a summary table); decided by the main manager 2026-11-26, the owner can veto |
| 453 | 494 | Nothing else, except the decide section | reword | rules/human.md:36 | the report shape named; decided by the main manager 2026-11-26, the owner can veto |
| 454 | 496 | H4. Tables | keep | PRINCIPLES.md:64 | unchanged words, always loaded |
| 455 | 497 | Comparison, series, feature list, task list, options → table | reword | PRINCIPLES.md:64 | H4 in one core line |
| 456 | 498 | Never prose | merge with 497 | PRINCIPLES.md:64 | same line |
| 457 | 502 | S1. Settings | move | rules/setup.md:6 | unchanged words, read at the moment of its file |
| 458 | 503 | Settings live only in /plugin -> Installed -> auto-pipeline -> Configure, user level (Claude Code keeps the... | move | rules/setup.md:7 | unchanged words, read at the moment of its file |
| 459 | 504 | Why: the plugin is a developer workflow, one setup for every repo | move | rules/setup.md:8 | unchanged words, read at the moment of its file |
| 460 | 505 | Configure holds the 17 settings | move | rules/setup.md:9 | unchanged words, read at the moment of its file |
| 461 | 506 | Repo facts (core paths, guard tests, test commands, edges, real-data access) live in the committed `agent_r... | move | rules/setup.md:10 | unchanged words, read at the moment of its file |
| 462 | 507 | New terminals use the "Permissions: Permission mode" setting, default bypassPermissions | move | rules/setup.md:11 | unchanged words, read at the moment of its file |
| 463 | 508 | `/auto-pipeline:settings` shows them as a table and never changes them | move | rules/setup.md:12 | unchanged words, read at the moment of its file |
| 464 | 509 | No settings file in a repo, none on a machine: start and init move an old repo or machine settings file int... | move | rules/setup.md:13 | unchanged words, read at the moment of its file |
| 465 | 510 | A cloud session (no plugin) runs the defaults | move | rules/setup.md:14 | unchanged words, read at the moment of its file |
| 466 | 511 | Also holds the watch and housekeep config (`housekeep_interval_min`) | move | rules/setup.md:15 | unchanged words, read at the moment of its file |
| 467 | 512 | Setup: init offers to merge the permission rules into `.claude/settings.json` (`agent-init.sh --add-permiss... | move | rules/setup.md:16 | unchanged words, read at the moment of its file |
| 468 | 513 | Setup: init asks all vs selected repos; `agent-init.sh --scope` writes the files; agents never hand-edit JSON | move | rules/setup.md:17 | unchanged words, read at the moment of its file |
| 469 | 515 | S2. Resume script | move | rules/context.md:4 | unchanged words, read at the moment of its file |
| 470 | 516 | One command | move | rules/context.md:5 | unchanged words, read at the moment of its file |
| 471 | 517 | Loads context, memory, agents, saved sessions (S7), and prints the watch command when no watch runs | move | rules/context.md:6 | unchanged words, read at the moment of its file |
| 472 | 519 | S3. Resource guard | move | rules/resources.md:9 | unchanged words, read at the moment of its file |
| 473 | 520 | A run (a test command, a build, a new agent pane) starts when memory in use now + the memory this run is kn... | move | rules/resources.md:10 | unchanged words, read at the moment of its file |
| 474 | 521 | Known to need = the measured peak MB; a Claude pane counts too (about 300-550 MB; 550 MB while never measured) | move | rules/resources.md:11 | unchanged words, read at the moment of its file |
| 475 | 522 | A run that was never measured is not held back: it starts at once with a monitor on its memory; the monitor... | move | rules/resources.md:12 | unchanged words, read at the moment of its file |
| 476 | 523 | Over the limit the monitor stops the newest, unmeasured one first, records its peak MB, and the run is trie... | move | rules/resources.md:13 | unchanged words, read at the moment of its file |
| 477 | 524 | CPU: a parallel test runner uses as many processes as keep CPU under the same limit (`{workers}`); memory i... | move | rules/resources.md:14 | unchanged words, read at the moment of its file |
| 478 | 526 | S4. Usage cap | move | rules/resources.md:16 | unchanged words, read at the moment of its file |
| 479 | 527 | Over the limit: start nothing new; close done and idle panes first; stop test runs before anything else (`a... | move | rules/resources.md:17 | unchanged words, read at the moment of its file |
| 480 | 528 | A working agent is left alone: never stop a working agent, tell the main manager instead, one line: which m... | move | rules/resources.md:18 | unchanged words, read at the moment of its file |
| 481 | 529 | relief stops only what the pipeline owns: `agent-watch.sh --all` processes left by tests, watches of repos ... | move | rules/resources.md:19 | unchanged words, read at the moment of its file |
| 482 | 530 | The sweep (W8) runs `agent-resources.sh stop-leftovers`: this repo's orphan watch and finished test watches... | move | rules/resources.md:20 | unchanged words, read at the moment of its file |
| 483 | 531 | A task manager over cap parks: commit, write state, set idle; the main manager closes its pane; resume brin... | move | rules/resources.md:21 | unchanged words, read at the moment of its file |
| 484 | 532 | The human's apps, other repos' sessions, Gradle or node runners: never killed by an agent. One table to the... | move | rules/resources.md:22 | unchanged words, read at the moment of its file |
| 485 | 533 | Setting "Load: Max memory %" = 80 | move | rules/resources.md:23 | unchanged words, read at the moment of its file |
| 486 | 535 | S5. Test runs | move | rules/tests.md:20 | unchanged words, read at the moment of its file |
| 487 | 536 | Every test run goes through `agent-test-run.sh`: it reserves its measured peak MB while it runs, and the mo... | move | rules/tests.md:21 | unchanged words, read at the moment of its file |
| 488 | 537 | One small shared reservation list per machine (every running job: pid, reserved MB; a dead pid frees its en... | move | rules/tests.md:22 | unchanged words, read at the moment of its file |
| 489 | 538 | Measured weights live per machine (`agent_test_weights.json` in the git common dir); `agent_repo.conf` `wei... | move | rules/tests.md:23 | unchanged words, read at the moment of its file |
| 490 | 539 | Every test run caps its own parallelism, e.g. `jest --maxWorkers=2`, `flutter test -j 2` | move | rules/tests.md:24 | unchanged words, read at the moment of its file |
| 491 | 540 | Every test run that can run in the background runs in the background by default (Bash `run_in_background`) | move | rules/tests.md:25 | unchanged words, read at the moment of its file |
| 492 | 542 | S6. No count caps | move | rules/resources.md:25 | unchanged words, read at the moment of its file |
| 493 | 543 | No count caps: no fixed count of agents, task managers or subagents per machine; a new agent pane is admitt... | move | rules/resources.md:26 | unchanged words, read at the moment of its file |
| 494 | 544 | A pane in state working or permission is a busy agent; a done or idle pane and the main manager are not cou... | move | rules/resources.md:27 | unchanged words, read at the moment of its file |
| 495 | 545 | A finished idle pane (state done): its own repo's main manager closes it once its task is merged, dropped o... | move | rules/resources.md:28 | unchanged words, read at the moment of its file |
| 496 | 546 | Never one still waiting on a merge, a question or a decision (W8 closes it after the merge). Never another ... | move | rules/resources.md:29 | unchanged words, read at the moment of its file |
| 497 | 548 | S7. Session recovery | move | rules/context.md:8 | unchanged words, read at the moment of its file |
| 498 | 549 | Each agent saves state to `agent_state.txt` in its own worktree while working: task, progress, decisions, n... | move | rules/context.md:9 | unchanged words, read at the moment of its file |
| 499 | 550 | `agent_state.txt` is git-ignored. It never merges | move | rules/context.md:10 | unchanged words, read at the moment of its file |
| 500 | 551 | S2 restores it after crash or shutdown | move | rules/context.md:11 | unchanged words, read at the moment of its file |
| 501 | 553 | S8. Context guard (forgetting) | reword | PRINCIPLES.md:54 | the anchor splits: every-step part in the core, the rest under 'S8 (cont.)' in rules/context.md |
| 502 | 554 | Memory is the file, not the chat. Brief, decisions, next step live in `agent_state.txt`. Re-read it before ... | keep | PRINCIPLES.md:55 | unchanged words, always loaded |
| 503 | 555 | First action of every agent: copy its brief into `agent_state.txt`. The main manager keeps one too, in the ... | reword | PRINCIPLES.md:56 | split: the main manager's own state file -> rules/context.md |
| 504 | 556 | A state line: `agent-file.sh state add "<line>"` (it adds the date), never `echo >>`. A brief or report blo... | keep | PRINCIPLES.md:57 | unchanged words, always loaded |
| 505 | 557 | `agent-file.sh state trim` keeps the header, RULE/CARRY and machine lines, open questions, open-task lines,... | move | rules/context.md:15 | unchanged words, read at the moment of its file |
| 506 | 558 | `state trim` moves the rest to `agent_state.trim-<date>.txt` next to it, never lost. `todo done` and the ho... | move | rules/context.md:16 | unchanged words, read at the moment of its file |
| 507 | 559 | Over 300 lines (fixed) the start text says STATE LONG: trim it | move | rules/context.md:17 | unchanged words, read at the moment of its file |
| 508 | 560 | After a compaction the startup hook re-prints PRINCIPLES.md and `agent_state.txt`. No quiz then. Continue f... | reword | PRINCIPLES.md:58 | clause added: 'then re-read the rules file of your current step' (the old hook re-printed every rule; now only the core) |
| 509 | 561 | Compacted 2 times (fixed) → save state. Orca: `agent-autoclear.sh` types a save prompt, `/clear`, then `/go... | move | rules/context.md:18 | unchanged words, read at the moment of its file |
| 510 | 562 | The auto clear fires only when no human has typed a prompt in that pane for the last N minutes (setting "Co... | move | rules/context.md:19 | unchanged words, read at the moment of its file |
| 511 | 563 | Not a human prompt: a task notification, a tell pointer, a cross-session message, the watch or the auto cle... | move | rules/context.md:20 | unchanged words, read at the moment of its file |
| 512 | 564 | A task manager runs under `/goal` from the GOAL: line of its brief: typed after the brief and after each an... | move | rules/context.md:21 | unchanged words, read at the moment of its file |
| 513 | 565 | After a close case the main manager clears itself the same way: it types `/clear` into its own pane (its ha... | move | rules/context.md:22 | unchanged words, read at the moment of its file |
| 514 | 566 | No pane to type into (plain, cloud) or the send is refused → tell the human to type `/clear`; else end the ... | move | rules/context.md:23 | unchanged words, read at the moment of its file |
| 515 | 567 | One worker = one slice, then it ends. A second slice gets a fresh worker | move | rules/context.md:24 | unchanged words, read at the moment of its file |
| 516 | 569 | S9. Token guard (cost) | move | rules/context.md:26 | unchanged words, read at the moment of its file |
| 517 | 570 | Cheapest model that can do the job (the Models settings). Managers judge, they do not read whole repos | move | rules/context.md:27 | unchanged words, read at the moment of its file |
| 518 | 571 | Model by kind of thinking: deciding roles get the strongest model, executing roles a cheaper one (the Model... | move | rules/context.md:28 | unchanged words, read at the moment of its file |
| 519 | 572 | A worker gets only the files it needs, named in its brief. No repo-wide reads | move | rules/context.md:29 | unchanged words, read at the moment of its file |
| 520 | 573 | Quiz once per session start. Not after compaction, not for subagents | move | rules/context.md:30 | unchanged words, read at the moment of its file |
| 521 | 574 | Mechanical work (settings, file lines, cleanup) → a script, never an agent | keep | PRINCIPLES.md:52 | unchanged words, always loaded |
| 522 | 578 | E1. Shape | move | rules/output.md:4 | unchanged words, read at the moment of its file |
| 523 | 579 | For every reply a human reads | move | rules/output.md:5 | unchanged words, read at the moment of its file |
| 524 | 580 | Lead with the result | keep | PRINCIPLES.md:61 | unchanged words, always loaded |
| 525 | 581 | A command, path or snippet the human must use comes right after the result | move | rules/output.md:6 | unchanged words, read at the moment of its file |
| 526 | 582 | Number multi-step work, fewest steps | move | rules/output.md:7 | unchanged words, read at the moment of its file |
| 527 | 583 | End with one concrete next action | move | rules/output.md:8 | unchanged words, read at the moment of its file |
| 528 | 584 | No tangents: finish one, offer the other as a separate question. A mid-work question you can answer yoursel... | move | rules/output.md:9 | unchanged words, read at the moment of its file |
| 529 | 585 | Restate state every turn: Step <n> of <m> done, next | move | rules/output.md:10 | unchanged words, read at the moment of its file |
| 530 | 586 | Time estimates in real units | move | rules/output.md:11 | unchanged words, read at the moment of its file |
| 531 | 587 | Show what now works | move | rules/output.md:12 | unchanged words, read at the moment of its file |
| 532 | 588 | Errors: cause and fix, never "Uh oh" | move | rules/output.md:13 | unchanged words, read at the moment of its file |
| 533 | 589 | Lists: 5 items or fewer per group, ranked. Keep the rest, never drop them | move | rules/output.md:14 | unchanged words, read at the moment of its file |
| 534 | 590 | No preamble, no recap, no closer | move | rules/output.md:15 | unchanged words, read at the moment of its file |
| 535 | 591 | Break the shape: "explain" or "walk me through" → full length, headers | move | rules/output.md:16 | unchanged words, read at the moment of its file |
| 536 | 592 | Destructive action → confirm first | move | rules/output.md:17 | unchanged words, read at the moment of its file |
| 537 | 593 | 3 turns of "still broken" → name the assumption, ask one question | move | rules/output.md:18 | unchanged words, read at the moment of its file |
| 538 | 594 | Ambiguous request → one short question | move | rules/output.md:19 | unchanged words, read at the moment of its file |
| 539 | 595 | A rule that would delete the answer → the task wins, the shape stays | move | rules/output.md:20 | unchanged words, read at the moment of its file |
| 540 | 596 | The harness or system prompt outranks this section | move | rules/output.md:21 | unchanged words, read at the moment of its file |
| 541 | 597 | Pre-send check: delete an announcing first line, a recap or "anything else" last line, by-the-way sidebars | move | rules/output.md:22 | unchanged words, read at the moment of its file |
| 542 | 598 | Also delete empty hedges (keep a hedge with real uncertainty) and idioms | move | rules/output.md:23 | unchanged words, read at the moment of its file |
| 543 | 599 | Then: first line and last line tell what to do next and what just happened | move | rules/output.md:24 | unchanged words, read at the moment of its file |
| 544 | 601 | E2. Owner overrides | move | rules/output.md:26 | unchanged words, read at the moment of its file |
| 545 | 602 | These win over E1 | move | rules/output.md:27 | unchanged words, read at the moment of its file |
| 546 | 603 | Never fail silently: blocked, ambiguous, refused or broken is said at once. Never hidden as a tangent, trim... | reword | PRINCIPLES.md:49 | split: first sentence in the core (Never); 'Never hidden as a tangent ...' in rules/output.md E2 |
| 547 | 604 | Tables and ledgers are not lists: the 5-item cap never cuts a record whose value is completeness | move | rules/output.md:29 | unchanged words, read at the moment of its file |
| 548 | 605 | "verified", "works", "fixed" only with the real evidence named. A green suite is not a real device check | keep | PRINCIPLES.md:67 | unchanged words, always loaded |
| 549 | 606 | The decide section (H3) is never deleted by "one next action" or "no closers" | move | rules/output.md:30 | unchanged words, read at the moment of its file |
| 550 | 607 | Language stays H2 (the Language setting) | move | rules/output.md:31 | unchanged words, read at the moment of its file |
| 551 | 609 | E3. Concise | move | rules/output.md:33 | unchanged words, read at the moment of its file |
| 552 | 610 | Lead with the result | merge with 580 | PRINCIPLES.md:61 | 'Lead with the result' stands once; decided by the main manager 2026-11-26, the owner can veto |
| 553 | 611 | Cut narration | move | rules/output.md:34 | unchanged words, read at the moment of its file |
| 554 | 612 | Short by default | keep | PRINCIPLES.md:61 | unchanged words, always loaded |
| 555 | 613 | State plainly | move | rules/output.md:35 | unchanged words, read at the moment of its file |
| 556 | 614 | Full detail on request | move | rules/output.md:36 | unchanged words, read at the moment of its file |
| 557 | 615 | Never trade correctness for brevity | move | rules/output.md:37 | unchanged words, read at the moment of its file |
| 558 | 617 | E4. Keyword hooks | move | rules/output.md:39 | unchanged words, read at the moment of its file |
| 559 | 618 | A keyword hook (bin/agent-keyword.sh) only points to a skill or a rule; the logic lives in the skill or the... | move | rules/output.md:40 | unchanged words, read at the moment of its file |
| 560 | 622 | The pieces. Rules are in A-E; this is where things live. | reword | rules/map.md:2 | the map's intro; A-E are gone |
| 561 | 624 | Roles and routing: W9. Check blocks: R8; installing into a cloud repo: the cloud-pack skill (`/auto-pipelin... | stale, fixed by code evidence | rules/setup.md:24 | `--language zh` removed: bin/agent-cloud-pack.sh line 39 '--language is gone: given, it exits 2'; skills/cloud-pack 'takes no --language'. A change, not a reword; the rest moved, split into 3 lines |
| 562 | 626 | Agent skills: `/auto-pipeline:dispatch` (route one task), `/auto-pipeline:merge` (the reviewer and the chec... | move | rules/map.md:4 | unchanged words, read at the moment of its file |
| 563 | 631 | Human | merge with 239 | rules/roles.md:5 | tree picture of W6 |
| 564 | 632 | │  task ↓   report ↑ | merge with 239 | rules/roles.md:5 | tree picture of W6 |
| 565 | 633 | Main manager   (Main manager model · the main chat · free for the human) | merge with 239 | rules/roles.md:5 | tree picture of W6 |
| 566 | 634 | ├── Fast-lane deputy   (Helper model)  one small task in its own git worktree, then gone | merge with 240 | rules/roles.md:6 | tree row |
| 567 | 635 | ├── Reviewer           (Reviewer model setting)  PR review of every task, core review; read only | merge with 242 | rules/roles.md:8 | tree row |
| 568 | 636 | ├── Check deputy       (Helper model)  flow and UI checks, release smoke; one at a time on the browser | merge with 243 | rules/roles.md:9 | tree row; 'one at a time on the browser' = W5 rules/ui.md |
| 569 | 637 | ├── Merge deputy       (Helper model)  merge → push → delete branch → remove worktree | merge with 241 | rules/roles.md:7 | tree row |
| 570 | 638 | └── Worktree, one per big feature | merge with 245 | rules/roles.md:11 | tree rows; 'never codes' = the core's role-limits line |
| 571 | 639 | └── Task manager (Task manager model)     writes the tests, briefs workers, verifies, never codes | merge with 245 | rules/roles.md:11 | tree rows; 'never codes' = the core's role-limits line |
| 572 | 640 | ├── Worker (Helper model)  code until the tests pass, slice 1 | merge with 247 | rules/roles.md:13 | tree rows; 'slice 1, slice 2' = S8 'One worker = one slice' |
| 573 | 641 | └── Worker (Helper model)  code until the tests pass, slice 2 | merge with 247 | rules/roles.md:13 | tree rows; 'slice 1, slice 2' = S8 'One worker = one slice' |
| 574 | 643 | Scripts, not agents (cost no tokens): | move | rules/map.md:7 | unchanged words, read at the moment of its file |
| 575 | 644 | bin/agent-start.sh   RAM/CPU guard, prints the rules, 36-question quiz gate, main-manager lock | move | rules/map.md:8 | unchanged words, read at the moment of its file |
| 576 | 645 | bin/agent-nightly.sh  the nightly run of all tests: gates nothing, records selection misses, --release-ok | move | rules/map.md:9 | unchanged words, read at the moment of its file |
| 577 | 646 | bin/agent-test-run.sh  every test run: reserves its measured memory, a monitor watches it (S3, S5) | move | rules/map.md:10 | unchanged words, read at the moment of its file |
| 578 | 647 | bin/agent-room.sh  the memory gate: check, reserve, release, list, relief, measure-pane | move | rules/map.md:11 | unchanged words, read at the moment of its file |
| 579 | 648 | bin/agent-level.sh   the blocks a diff triggers (R8): agent-level.sh check --base <ref> | move | rules/map.md:12 | unchanged words, read at the moment of its file |
| 580 | 649 | bin/agent_blocks.py  the one table of blocks and triggers (R8) | move | rules/map.md:13 | unchanged words, read at the moment of its file |
| 581 | 650 | bin/agent-owner-order.sh  relayed owner orders between repo managers: `line` prints the OWNER ORDER header ... | move | rules/map.md:14 | unchanged words, read at the moment of its file |
| 582 | 651 | bin/agent-file.sh    the only writer of agent_*.txt | move | rules/map.md:15 | unchanged words, read at the moment of its file |
| 583 | 652 | bin/agent_estimate.py  the time estimator: learns work minutes from the finished tasks, backtests against t... | move | rules/map.md:16 | unchanged words, read at the moment of its file |
| 584 | 653 | bin/agent-settings.sh  show the settings (/plugin -> Configure changes them) | move | rules/map.md:17 | unchanged words, read at the moment of its file |
| 585 | 654 | bin/agent-resume.sh    one command to bring the pipeline back after a restart | move | rules/map.md:18 | unchanged words, read at the moment of its file |
| 586 | 655 | bin/agent-cleanup.sh   the main manager's sweep: removes merged, clean, idle worktrees and branches; lists ... | move | rules/map.md:19 | unchanged words, read at the moment of its file |
| 587 | 656 | bin/agent-housekeep.sh the main manager's pass every housekeep_interval_min from the `agent-watch.sh --all`... | move | rules/map.md:20 | unchanged words, read at the moment of its file |
| 588 | 657 | bin/agent-watch.sh     `agent-watch.sh --all`: one background watch for every task manager, local or remote... | move | rules/map.md:21 | unchanged words, read at the moment of its file |
| 589 | 658 | bin/agent-file.sh tell `agent-file.sh tell <task> "<msg>"`: long text to a task manager, a block in its age... | move | rules/map.md:22 | unchanged words, read at the moment of its file |
| 590 | 659 | bin/agent-init.sh      sets a project up: the four task files, .secrets/, .gitignore lines, AGENTS.md, and ... | move | rules/map.md:23 | unchanged words, read at the moment of its file |
| 591 | 660 | bin/agent-cloud-pack.sh  lays this pipeline into a repo as plain files, for cloud sessions | move | rules/map.md:24 | unchanged words, read at the moment of its file |
| 592 | 661 | bin/agent-city.sh       starts/stops the agent city visualiser, a local server | move | rules/map.md:25 | unchanged words, read at the moment of its file |
| 593 | 662 | bin/agent-city-shim     the ~/.local/bin/agent-city command; runs the newest installed plugin's agent-city.sh | move | rules/map.md:26 | unchanged words, read at the moment of its file |
| 594 | 663 | bin/agent-city-hook.sh  hook that feeds the city; off costs a `test -f`, on appends one JSON line | move | rules/map.md:27 | unchanged words, read at the moment of its file |
| 595 | 664 | bin/agent-close-case.sh  UserPromptSubmit hook: tells a released or replaced main manager once | move | rules/map.md:28 | unchanged words, read at the moment of its file |
| 596 | 665 | bin/agent-keyword.sh  UserPromptSubmit hook: a keyword in the prompt adds one line pointing to its skill or... | move | rules/map.md:29 | unchanged words, read at the moment of its file |
| 597 | 666 | bin/agent-board-warn.sh  hook: a new or changed board warning into the main manager's context | move | rules/map.md:30 | unchanged words, read at the moment of its file |
| 598 | 667 | bin/agent_board.py     the todo board: one table of every open task, wait, owner to-do and parked question | move | rules/map.md:31 | unchanged words, read at the moment of its file |
| 599 | 668 | bin/agent_questions.py  the question list: every question pending on the owner, as a chat list, JSON or an ... | move | rules/map.md:32 | unchanged words, read at the moment of its file |
| 600 | 669 | bin/agent-questions-page.html  the page template (one page grouped by task, lettered options, answer bar) | move | rules/map.md:33 | unchanged words, read at the moment of its file |
| 601 | 670 | bin/agent-name.sh       SessionStart + UserPromptSubmit hook: names the session by role (W6; a human-direct... | move | rules/map.md:34 | unchanged words, read at the moment of its file |
| 602 | 671 | bin/agent-guard.sh     hook: records every Agent launch and orca pane on the board, refuses a manager's lau... | move | rules/map.md:35 | unchanged words, read at the moment of its file |
| 603 | 672 | bin/agent-promote.sh   the working branch to production, only on the owner's verified words (--owner-quote)... | move | rules/map.md:36 | unchanged words, read at the moment of its file |
| 604 | 673 | bin/agent-runtime.sh   which runtime this agent is in (orca, plain, cloud) and the browser; the one place t... | move | rules/map.md:37 | unchanged words, read at the moment of its file |
| 605 | 674 | bin/agent-resources.sh  RAM and CPU readers, sourced by other scripts | move | rules/map.md:38 | unchanged words, read at the moment of its file |
| 606 | 675 | bin/agent-autoclear.sh  the waiter behind the auto /clear: save prompt, /clear, /goal, only after the human... | move | rules/map.md:39 | unchanged words, read at the moment of its file |
| 607 | 676 | bin/agent-release.sh   builds, checks and pushes the `release` branch, one commit per version | move | rules/map.md:40 | unchanged words, read at the moment of its file |
| 608 | 677 | bin/agent-statusline.sh  the Claude Code status line: one line per running task | move | rules/map.md:41 | unchanged words, read at the moment of its file |
| 609 | 678 | bin/agent-roots.sh     the two roots every script needs (project and plugin), sourced | move | rules/map.md:42 | unchanged words, read at the moment of its file |
| 610 | 679 | bin/agent-version.sh   UserPromptSubmit hook + check: a session running an older plugin than installed gets... | move | rules/map.md:43 | unchanged words, read at the moment of its file |
| 611 | 684 | \| File \| Who writes it \| Who reads it \| | move | rules/files.md:40 | unchanged words, read at the moment of its file |
| 612 | 685 | \|---\|---\|---\| | move | rules/files.md:41 | unchanged words, read at the moment of its file |
| 613 | 686 | \| `agent_todo.txt` \| `agent-file.sh todo add` / `todo done` \| Every agent at start \| | move | rules/files.md:42 | unchanged words, read at the moment of its file |
| 614 | 687 | \| `agent_completed.txt` \| `agent-file.sh todo done`, one data line per task \| Human, `agent-file.sh time... | move | rules/files.md:43 | unchanged words, read at the moment of its file |
| 615 | 688 | \| `agent_estimate.txt` \| `agent-file.sh retrain`, also `todo done` once a week \| `agent-file.sh estimate... | move | rules/files.md:44 | unchanged words, read at the moment of its file |
| 616 | 689 | \| `agent_ideas.txt` \| `agent-file.sh idea add` \| Human, on his own time \| | move | rules/files.md:45 | unchanged words, read at the moment of its file |
| 617 | 690 | \| `agent_repo.conf` (committed, repo root) \| `bin/agent-init.sh`, agents via `agent-file.sh edge add` \| ... | move | rules/files.md:46 | unchanged words, read at the moment of its file |
| 618 | 691 | \| `agent_worktree.txt` \| `agent-file.sh worktree set` / `rm` \| Main manager before every dispatch \| | move | rules/files.md:47 | unchanged words, read at the moment of its file |
| 619 | 692 | \| `agent_watch.json` (git dir, git-ignored by being there) \| `agent-watch.sh --all` \| `agent-watch.sh`, ... | move | rules/files.md:48 | unchanged words, read at the moment of its file |
| 620 | 693 | \| `agent_state.txt` \| Each session: `agent-file.sh state add`; `state trim` moves old lines to `agent_sta... | move | rules/files.md:49 | unchanged words, read at the moment of its file |
| 621 | 694 | \| `.secrets/` \| Human only \| Any agent, read only, never printed \| | move | rules/files.md:50 | unchanged words, read at the moment of its file |
| 622 | 699 | ./bin/agent-start.sh             # rules, resources, quiz. No work until PASS | move | rules/map.md:47 | unchanged words, read at the moment of its file |
| 623 | 700 | ./bin/agent-resume.sh            # runs by itself at startup (Auto resume setting on); run by hand only if ... | move | rules/map.md:48 | unchanged words, read at the moment of its file |
| 624 | 701 | ./bin/agent-settings.sh          # show the settings, no agent (change them in /plugin -> Installed -> auto... | move | rules/map.md:49 | unchanged words, read at the moment of its file |
| 625 | 702 | bin/agent-file.sh time              # est, work, wait, clock of every finished task | move | rules/map.md:50 | unchanged words, read at the moment of its file |
| 626 | 703 | bin/agent-file.sh data              # the same data of every repo on this machine, one table | move | rules/map.md:51 | unchanged words, read at the moment of its file |
| 627 | 704 | bin/agent-file.sh eta <name>        # work left as minutes and a clock time, and when the human is needed next | move | rules/map.md:52 | unchanged words, read at the moment of its file |
| 628 | 705 | bin/agent-file.sh estimate ... [--guess <m>]   # work minutes of a new task, with a range and the 3 nearest... | move | rules/map.md:53 | unchanged words, read at the moment of its file |
| 629 | 706 | bin/agent-file.sh backtest          # estimator, blend and rubric on the finished tasks, who wins | move | rules/map.md:54 | unchanged words, read at the moment of its file |
| 630 | 707 | bin/agent-file.sh retrain           # learn the estimate again from the finished tasks, keep it only if better | move | rules/map.md:55 | unchanged words, read at the moment of its file |
| 631 | 708 | bin/agent-file.sh next              # the queued tasks that can start now, then the board warnings | move | rules/map.md:56 | unchanged words, read at the moment of its file |
| 632 | 709 | bin/agent-file.sh checks gate <task> --dir <path>  # the merge gate | move | rules/map.md:57 | unchanged words, read at the moment of its file |
| 633 | 710 | bin/agent-nightly.sh --status \| --misses \| --release-ok   # the nightly run of all tests: its state, the ... | move | rules/map.md:58 | unchanged words, read at the moment of its file |
| 634 | 711 | bin/agent-file.sh board             # the todo board: open tasks, waits on the owner, owner to-dos, parked ... | move | rules/map.md:59 | unchanged words, read at the moment of its file |
| 635 | 712 | bin/agent-file.sh questions         # the question list: every question pending on the owner (--self, --jso... | move | rules/map.md:60 | unchanged words, read at the moment of its file |
| 636 | 713 | bin/agent-city.sh install-shim      # one time: puts the agent-city command in ~/.local/bin; nothing instal... | move | rules/map.md:61 | unchanged words, read at the moment of its file |
| 637 | 714 | agent-city start                    # agent city visualiser, off by default, costs almost nothing | move | rules/map.md:62 | unchanged words, read at the moment of its file |
| 638 | 718 | Notice | move | NOTICE.md:1 | license text, unchanged |
| 639 | 720 | Section E is adapted from i-have-adhd (https://github.com/ayghri/i-have-adhd) under the MIT License. | move | NOTICE.md:3 | license text, unchanged |
| 640 | 722 | Copyright (c) 2026 Ayoub Ghriss | move | NOTICE.md:5 | license text, unchanged |
| 641 | 724 | Permission is hereby granted, free of charge, to any person obtaining a copy | move | NOTICE.md:7 | license text, unchanged |
| 642 | 725 | of this software and associated documentation files (the "Software"), to deal | move | NOTICE.md:8 | license text, unchanged |
| 643 | 726 | in the Software without restriction, including without limitation the rights | move | NOTICE.md:9 | license text, unchanged |
| 644 | 727 | to use, copy, modify, merge, publish, distribute, sublicense, and/or sell | move | NOTICE.md:10 | license text, unchanged |
| 645 | 728 | copies of the Software, and to permit persons to whom the Software is | move | NOTICE.md:11 | license text, unchanged |
| 646 | 729 | furnished to do so, subject to the following conditions: | move | NOTICE.md:12 | license text, unchanged |
| 647 | 731 | The above copyright notice and this permission notice shall be included in all | move | NOTICE.md:14 | license text, unchanged |
| 648 | 732 | copies or substantial portions of the Software. | move | NOTICE.md:15 | license text, unchanged |
| 649 | 734 | THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR | move | NOTICE.md:17 | license text, unchanged |
| 650 | 735 | IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, | move | NOTICE.md:18 | license text, unchanged |
| 651 | 736 | FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE | move | NOTICE.md:19 | license text, unchanged |
| 652 | 737 | AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER | move | NOTICE.md:20 | license text, unchanged |
| 653 | 738 | LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, | move | NOTICE.md:21 | license text, unchanged |
| 654 | 739 | OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE | move | NOTICE.md:22 | license text, unchanged |
| 655 | 740 | SOFTWARE. | move | NOTICE.md:23 | license text, unchanged |
