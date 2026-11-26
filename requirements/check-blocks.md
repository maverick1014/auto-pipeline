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

## 9. Contract (task manager, for the tests; defaults logged in agent_state.txt)

C1. The one table: `bin/agent_blocks.py` (Python 3.9, stdlib only)
- `BLOCKS`: list of dicts, table order: `name`, `picked` (`tool` | `brief`), `trigger`, `runs`, `sign`.
  Tool rows: DIFF SCAN, BUILD, RELATED TESTS, GUARD TESTS, DB CHECK, DATA CHECK, FULL SUITE, CORE REVIEW.
  Brief rows: DIFF READ, EXAMPLES TEST, FLOW CHECK, UI CHECK, REAL DATA COUNT. Texts as in section 1.
  `sign`: `no`, `yes`, or the condition text (DB CHECK: "only when the migration changes or removes data or columns"; CORE REVIEW: "a permission change").
- `OWNER SIGN` is no row: the tool plans it when a sign fires. `NET`: NIGHTLY SUITE, RELEASE SMOKE (outside tasks).
- `python3 bin/agent_blocks.py table` prints the markdown table `| Block | Picked | Trigger | What runs | Owner signs |`, one row per block. PRINCIPLES.md R8 holds exactly these rows (a test compares).
- `python3 bin/agent_blocks.py names` prints the 13 names, one per line, table order.

C2. `agent-level.sh check --base <ref> [--scope "<glob>,<glob>"] [--json]` (names kept)
- Diff as today (working tree vs merge base, untracked not ignored files count).
- stdout, in this order, exit 0 (usage or setup error: one stderr line, exit 2):
  `BLOCKS: <triggered tool blocks, table order, ", ">[, OWNER SIGN]` (none: `BLOCKS: DIFF SCAN`)
  `FILE <path>: <kind>[+<kind>] (<reason>)` one per changed file, sorted; kinds: code style text rule asset deps ci migration schema data-script, `+core` when a core path matches
  one detail line per triggered block, `<BLOCK>: ...` (below)
  `NOT TRIGGERED: <tool blocks not triggered, ", ">`
  `BRIEF PICKS: DIFF READ, EXAMPLES TEST, FLOW CHECK, UI CHECK, REAL DATA COUNT (dispatch picks them from the brief)`
  `no changes` when nothing changed. `--declared <x>` is accepted and ignored with the line `note: --declared is ignored: levels are gone, blocks only`.
- Kind of a file (first rule that fits, the existing lexers decide text and style):
  deps (lockfile, package.json deps, pubspec, dependency lists) · ci (CI or test config: .github/workflows/*, .gitlab-ci.yml, .circleci/*, Jenkinsfile, azure-pipelines.yml, bitbucket-pipelines.yml, .travis.yml, jest.config.*, vitest.config.*, karma.conf.*, playwright.config.*, cypress.config.*, pytest.ini, tox.ini, conftest.py, .mocharc*, phpunit.xml*, dart_test.yaml, plus `test_config` globs of agent_repo.conf) · migration (a folder named migrations, migration, migrate, alembic; `+code` when its extension is code) · schema (schema.*, *.schema.*, *.prisma, *.sql) · data-script (`data_scripts` globs of agent_repo.conf, or a file under a folder named scripts, script, oneoff, datafix, data-fix, backfill whose added lines hold UPDATE .. SET, DELETE FROM, INSERT INTO or TRUNCATE) · rule (PRINCIPLES.md, CLAUDE.md, AGENTS.md, skills/**, agents/*.md, .claude/skills/**, .claude/agents/**) · text (.md .markdown .txt .rst .adoc; a code or markup file whose only change is text values, comments or white space) · style (.css .scss .sass .less .styl .pcss; a code or markup file whose only change is colour values, existing prop values or a line move) · asset (images, fonts) · code (the rest).
  Old reasons stay ("text change", "colour change", "comment only", "style file", "component file", "new file"), `built-in D: <kind>` becomes `built-in: <kind>`.
- Triggers: BUILD = a code or style file. RELATED TESTS = a code, style, text or rule file. GUARD TESTS = the same, and agent_repo.conf lists `guard_tests` (none listed: the line `GUARD TESTS: none listed in agent_repo.conf (init writes them)` among the notes, not triggered). DB CHECK = migration or schema. DATA CHECK = data-script. FULL SUITE = deps or ci. CORE REVIEW = a `+core` file (core_paths, old level3_paths and level4_paths).
- OWNER SIGN = FULL SUITE, DATA CHECK, or DB CHECK on a data change: a removed non-blank line in a migration or schema file, or an added line with UPDATE, DELETE, DROP, TRUNCATE, RENAME, ALTER .. DROP/ALTER COLUMN, remove_column, drop_table, rename_column, change_column, RemoveField, DeleteModel, AlterField, RenameField, RunSQL, RunPython, op.drop_, op.alter_column, dropColumn, dropTable, renameColumn (case-insensitive). Unsure = sign.
- Detail lines:
  `DIFF SCAN: <n> findings` then `  <finding>` lines: `outside scope: <path>` (only with --scope) · `deleted test: <path>` · `removed test: <path>: <name>` · `skipped test: <path>:<line>` (unittest.skip, skipTest(, pytest.mark.skip, xit(, it.skip(, describe.skip(, test.skip(, xdescribe(, @Disabled, skip: true) · `secret: <path>:<line> <kind>` (never the value) · `secret file: <path>` (.env*, .secrets/*, *.pem, id_rsa*) · `debug leftover: <path>:<line> <marker>` (console.log(, debugger, breakpoint(), pdb.set_trace, binding.pry, var_dump(; not in test files)
  `BUILD: <files> | run: <build_cmd of agent_repo.conf, else "syntax or type check of the touched app (no build_cmd in agent_repo.conf)">`
  `RELATED TESTS: <test files, ", "> | run: <related_cmd with {tests} = the paths, {modules} = dotted module names>`; none found: `RELATED TESTS: none found | run: -`. Related = a test file that is itself changed, or names a changed file (its path, its file name, or its stem when 4 chars or more). A rule file: the tests that name a changed section code (`R8`, `W4`: the code of the nearest `^<code>. ` heading above each changed line) or the file path. A code (not style) file: also `group <module>: <cmd>` lines, one per `group.<module>` of agent_repo.conf whose module folder holds a file that names the changed file
  `GUARD TESTS: <files> | run: <related_cmd over them>` · `DB CHECK: <files> | owner signs: yes (<why>)` or `| owner signs: no (adds only)` · `DATA CHECK: <files>` · `FULL SUITE: <files> | run: <full_cmd, else "-">` · `CORE REVIEW: <files>` · `OWNER SIGN: <BLOCK> (<files>)[; ...]`
- `--json`: one JSON object {blocks, sign, files: {path: {kinds, reason}}, findings, related, guard} for the gate.

C3. `bin/agent-file.sh` (the only writer of agent_*.txt)
- `todo add ... [--checks "<BLOCK>,<BLOCK>"] [--scope "<glob>,<glob>"]`: fields ` | checks <BLOCK>, <BLOCK>` (table order) and ` | scope <globs>` after guess (else est). An unknown block name: refused, exit 1. `--level` still works for old callers, no doc names it.
- `todo checks "<name>" <BLOCK>[,<BLOCK>...]`: union into the field, table order; prints `todo checks: <name> <old or -> -> <new>`.
- `todo checks "<name>" --drop <BLOCK> --quote "<owner words>" [--time <t>]`: runs `agent-owner-order.sh verify --repo <main repo folder> --quote ..`; exit 0 -> the block leaves the checks field and the line gets ` | dropped <BLOCK> <date>`; else refused, its output named, nothing changes.
- `todo est "<name>" <minutes> [--guess <m>]`: est (and guess) replaced in place, every other field stays; prints `todo est: <name> <old>m -> <new>m`.
- `check "<task>" "<BLOCK>" pass|fail --by <who> --evidence "<text>"`: agent_state.txt of this folder gets `CHECK <task> <BLOCK>: pass | by <who> | <evidence> | <date>`. A block outside the table (OWNER SIGN allowed), no --by or no --evidence: refused.
- `checks gate "<task>" --dir <path> [--base <ref, default origin/main>] [--results <file>] [--checks "<list>"]`: planned = the todo line's checks field (or --checks when the line is not in this repo) + the tool blocks of `agent-level.sh check --base <ref>` run in <dir> (+ OWNER SIGN) - dropped blocks. Result lines from <file>, else <dir>/agent_state.txt; the last line of a block wins. Prints `<BLOCK>: pass (by <who>)` / `<BLOCK>: fail (by <who>)` / `<BLOCK>: missing` per planned block, then `GATE PASS <task>` (exit 0) or `GATE REFUSED <task>: <BLOCK> missing, <BLOCK> fail` (exit 1). No todo line and no --checks: exit 2.
- `next`: one line `NEXT: <n> can start (slots <free> of <max agents>, RAM <p>% under <cap>%)`, then `START <name> | est <m>m | <what>` per task that can start now, then `WAIT <name>: <why>` per queued one that cannot (`after <task> still open`, `clashes with <task> on <glob>`). Can start = an open line with no stage and no open wait other than a queue wait whose after-task is closed. Running = an open line with a stage and no open wait. No slot or RAM at or over the cap: `NEXT: 0 can start: <why>`. A task with no scope: `WAIT`-free, listed with ` | scope unknown: judge`.
- `todo done "<X>"`: also closes the queue wait of every open line whose `after` is X (as `todo wait off`) and prints `released: <name>` per line.
- `edge add "<text>"`: one `edge=<text>` line in the agent_repo.conf of the git toplevel of the cwd (commit it with the fix); an existing same line: `edge add: already listed`.

C4. agent_repo.conf v1 (committed, main repo root; written by init, kept by agents)
- `key=value` lines, `#` comments; repeated keys `edge=` and `group.<module>=`. Keys: `version=1`, `core_paths`, `guard_tests`, `build_cmd`, `related_cmd`, `full_cmd`, `group.<module>`, `test_config`, `data_scripts`, `real_data` (a .secrets/ file name, or `none`), `build_seconds`, `build_mb`, `edge`. Old `level3_paths`, `level4_paths` still read as core paths.
- `agent-init.sh` writes it when missing, adds only missing keys when present (never changes a set value), one line per key it adds. `--no-measure` skips timing the build.
- Detects: test tool (python unittest/pytest, jest, vitest, flutter, go) -> related_cmd and full_cmd; build_cmd (python: `python3 -m compileall -q <dirs>`; node: package.json lint and typecheck/tsc scripts; flutter: `flutter analyze`; go: `go vet ./...`); guard_tests (test files that read the tree: os.walk, rglob, glob with **, git ls-files, readdirSync with recursive); core_paths (folders or files named auth, permission(s), acl, role(s), money, payment(s), billing, ledger, journal, invoice(s), migrations); the 7 generic edges that fit (empty value, more than one page, deleted rows, invalid input, day boundary in local time, double submit, large size); `# fix: <subject>` lines for the last 20 commits whose subject starts with fix, bug or hotfix; real_data.
- Measures: runs build_cmd once (120 s cap), writes build_seconds and build_mb.

C5. Agents and skills
- `agents/check-deputy.md` (new): model sonnet, tools Read, Grep, Glob, Bash and the Claude in Chrome tools. Does DIFF READ, FLOW CHECK, UI CHECK, re-checks after a bounce, RELEASE SMOKE; one at a time on the browser; never edits files; writes its result line with `agent-file.sh check`; first report line `CHECK PASS <task> <BLOCK>` or `CHECK FAIL <task> <BLOCK>: <why>`, then evidence.
- `agents/fast-lane-deputy.md`: own worktree (Agent isolation), writes the example tests first when EXAMPLES TEST is planned, runs its blocks, writes one result line per block, commits and pushes its branch; past 2x its estimate or a second slice -> stops and reports.
- `agents/merge-deputy.md`: step 1 = `agent-file.sh checks gate`; a failed run after the merge -> `git reset --merge ORIG_HEAD`, never --hard; brief field `session: helper` -> no pane close, no worktree removal, branch kept; brief field `machine: <env>` -> gate on a local scratch copy of the branch, orca commands with `--environment <env>`.
- skills/dispatch: picks the brief blocks, `--checks` on the todo line, a `CHECKS:` brief line instead of `LEVEL:`, the brief says "run the blocks of the task", never "Full suite once"; a requirement table copies defaults from the released template and lists every changed default. skills/merge: the gate, the check deputy, no level words.
- Board: column `Checks` (zh `检查`) shows the checks field, an old line `level <X>`, else `-`.

## 10. Slice 8: cleanup (TELL 101f0c46, owner 2026-11-25: fix it by the best design "that will not affect user workflow"; last slice)

Evidence 2026-11-25: `agent-cleanup.sh` listed "kept 10, remove 0" while a merged worktree with its local and remote branch, 4 panes nobody used (2 idle Claude sessions), 21 LAUNCH lines of ended agents and a worktree line still "working" stayed.

- (a) Every merge ends with cleanup, in every case. merge-deputy.md has steps for: a task manager pane (as today); a subagent's plain git worktree (unlock, remove, prune, delete its task branch and its `worktree-agent-*` branch, delete the remote branch); a human-direct Helper (its own pane always stays; the merged task's worktree, branches and other panes go, unless the Helper's own session runs inside that worktree: then the folder stays and the line says so); a worktree on another machine.
- (b) The worktree line of a merged task is always removed or rewritten at merge, also when the folder stays.
- (c) `human-direct` protects only the human's own session pane, not every pane in that worktree. A pane that never got a prompt and is idle over 30 minutes is closed by the sweep and named in its output. Orca's `worktree create` opens default tabs (a shell "Terminal 1" and a Claude "<name> Task Manager" session): dispatch uses that default agent pane for the brief or closes it, never opens a second one beside it.
- (d) Every LAUNCH kind has a remover: subagent at SubagentStop (5afbd13), pane and tm-pane when the pane is closed or its handle is gone, merge at its end; the sweep prunes a record whose pid is dead or whose pane is gone.
- (e) The cleanup table never lists main or the release branch; a worktree with a live LAUNCH record is "live agent", never "commit or discard the changes".
- (f) The sweep runs after every merge, not only at start, at the last task and every 120 minutes.
- (g) The plain list shows what `--apply` would remove under these rules; `--apply` stays main manager only.
- Tests first, by module -> feature.

## 11. Contract additions from the kick-off answers (TELL df857e05, 2026-11-25)

- C2 budget: `check_budget_s` = 60, a fixed constant in `bin/agent_conf.py`. agent_repo.conf `build_seconds` / `guard_seconds` over it -> that block is heavy: not in BLOCKS, not in NOT TRIGGERED, one line `NET: BUILD (heavy, <n> s over the 60 s budget): nightly or pre-release, queued like a heavy test` or `NET: GUARD TESTS (heavy, <n> s over the 60 s budget): nightly or pre-release`; `--json` key `net`. Unmeasured or at most 60 s: runs per task.
- C2 style and text related tests: a style-only file takes only its own tests (a test file whose name holds the file's stem); a text file also takes the tests that hold a changed string (a quoted or markup text of 4 chars or more, old or new).
- C3 remove: `todo checks "<task>" --remove <BLOCK> --owner-quote "<his words>" [--time <t>]` (not --drop): runs `agent-owner-order.sh verify --repo <main repo folder> --quote "<words>"`; exit 0 -> the block leaves the checks field and the line gets ` | removed <BLOCK> <date>`; else refused. The gate always recomputes the tool blocks from the diff, so a removed tool block that the diff triggers is still planned; a removed brief block is not planned.
- C3 builder: field ` | builder <name>` (`todo add --builder <name>`, `todo builder "<task>" <name>`, comma list). Builders = that field + the titles of the task's LAUNCH records of kind `worker <n>` or `tm-pane` in <dir>/agent_state.txt and the main repo's. A DIFF READ, FLOW CHECK or UI CHECK pass line whose `by` is a builder (case-insensitive): `<BLOCK>: pass by the builder (<who>), not accepted`, refused as `<BLOCK> by the builder`. No builder known: accepted, one line `note: builder unknown: <BLOCK> by <who> accepted` per such block.
- C4 measure: init measures build_cmd and the guard tests only when RAM and CPU are under the cap (else one line, no number written); a run that hits the 120 s cap is written as `build_seconds=120` (or `guard_seconds=120`) with the comment `# heavy: hit the 120 s cap`, never retried.

## 12. Slice 2 addition: board warnings reach the main manager (TELL 315ae904, owner 2026-11-25)

The owner sees "board may be wrong: the watch is not running / N not confirmed / a pane has no task line" under his prompt; only the status line shows them, so the human has to report them.
- (1) `agent-file.sh next` also prints every board warning with the reaction the main manager takes in the same turn: `WARN watch not running -> start it now: <agent-watch.sh --all command>`; `WARN not confirmed <task> -> read its pane or its newest state line, then fix the record or the agent`; `WARN pane without a task line <path> -> add the todo line or close the pane`.
- (2) A hook puts a new or changed warning into the main manager's context, at a user prompt and after a tool call, rate limited, main manager only, so it reacts with no human.
- (3) Rule: after a watch wake the first action is to start the watch again, then handle the signal (evidence: the watch exited about 20 times on 2026-11-25 and stayed down for minutes each time, once about 40 minutes).
- (4) A human-direct Helper's task counts as confirmed by the Helper's own live pane, wherever its worktree is (city-office-2 showed "not confirmed" because the Helper works from the main folder).
- Tests first.

## 13. Rule text (task manager draft; the rules worker puts it into PRINCIPLES.md as written, the table rows from `python3 bin/agent_blocks.py table`)

R1 (replaces the whole rule):
```
R1. One flow, two lanes
- Before the flow: the main manager writes the requirement doc, the owner approves it
- Full flow, in order:
  1. Todo line + estimate
  2. Mock if the task has UI
  3. Worktree + task manager
  4. Failing tests first
  5. Workers build
  6. Verify
  7. Push
  8. Acceptance blocks (R8)
  9. Merge + cleanup
  10. Todo done
- Task size picks who does the work: small task = one subagent in its own git worktree (fast lane); it writes its example tests and runs its blocks
- Big task (over 2 hours, several slices) = a task manager (full lane)
- Which checks run follows the triggers only (R8), never the lane
- A small logic task never opens a task manager just because it needs a test
- A small task that grows (past 2x its estimate, or it needs a second slice): the subagent stops and reports; the main manager opens a task manager that goes on from its branch
```

R8 (replaces "R8. Risk types"):
```
R8. Check blocks
- Owner 2026-11-25: "only do the necessary thing when needed, dont do extra thing. and dont do less thing"
- No levels: each check is a block with a trigger; a task runs the blocks whose trigger fires, nothing else
- The one table, source `bin/agent_blocks.py`; this table, the skills and the quiz are tested against it:

<the 15 lines of `python3 bin/agent_blocks.py table`>

- Picked tool: `agent-level.sh check --base <ref>` decides them from the real diff, no judgment
- Picked brief: dispatch picks them from what the owner approved: `todo add ... --checks "<BLOCK>,<BLOCK>"`
- Two passes: the brief blocks at dispatch; before merge the tool recomputes the tool blocks from the real diff
- Blocks are only added; removing one needs a verified owner order: `todo checks <task> --remove <BLOCK> --owner-quote "<his words>"`
- One result line per block: `agent-file.sh check <task> "<BLOCK>" pass|fail --by <who> --evidence "<text>"`
- The merge gate `agent-file.sh checks gate <task>` refuses while a planned block has no pass line
- DIFF READ, FLOW CHECK and UI CHECK pass only by someone who did not build the task: not the builder (the todo line's builder or its LAUNCH records)
- OWNER SIGN is planned when a sign fires: FULL SUITE, DATA CHECK, DB CHECK on a data change, CORE REVIEW on a permission change
- BUILD and GUARD TESTS run per task only when their measured time in agent_repo.conf is under `check_budget_s` (60 s)
- Slower = heavy: it runs in the net; a heavy BUILD is queued like a heavy test (S5)
- REAL DATA COUNT with no read access: skipped with one printed line, never silently
- Outside tasks, the net: NIGHTLY SUITE (the full suite every night or before a release, in the background on the heavy-test machine; nobody waits; red = the first task next morning)
- RELEASE SMOKE after every release: a fresh session uses the released version for real (start, one subagent launch and finish, the user-facing flows that changed)
- Four kinds of request, one line each:
  - Refactor (no behaviour change): BUILD + RELATED TESTS; no new examples, the existing tests are the acceptance
  - Urgent fix (production is broken): the smallest fix, the same triggers; a verified owner order may move a block to right after the release, never drop it
  - Rollback: back to the last green commit; BUILD + RELATED TESTS of the reverted files; a database change follows its written rollback plan
  - Research only (no diff): no blocks; the report is the deliverable
- Repo facts live in the committed `agent_repo.conf`, written by init and kept by agents, never by the user: core paths, guard tests, test commands, the edge list, real-data access
- After each bug fix the fixing agent asks "which example would have shown it" and adds one line with `agent-file.sh edge add "<text>"` when the list lacks it
- A second agent's opinion only for CORE REVIEW, or when someone wants a tool-triggered block removed
- A requirement table copies its defaults from the released template and lists every changed default for the owner
```

W2: "- Which risk type needs a mock: R8" becomes "- A mock only for a new page or a whole-page re-layout; the approved mock is what UI CHECK compares with (R8)".

W4 (replaces the whole rule):
```
W4. Multi-agent tests
- Tests are organised module → feature
- Which tests run follows the blocks (R8): RELATED TESTS (the tests that import or name the changed files) and GUARD TESTS per task
- FULL SUITE only when its trigger fires: once, never twice
- The main manager and the merge deputy never re-run tests the task manager already passed. Only on a merge conflict: test the conflicted part
- After a bounce: re-run only the tests that failed, not the suite
```

W5 (replaces the whole rule):
```
W5. Web UI testing
- Claude in Chrome, not Playwright, on orca and plain
- The check deputy (`agents/check-deputy.md`) drives the browser for FLOW CHECK, UI CHECK and RELEASE SMOKE, one at a time
- Others write the click path and hand it to the main manager, who sends the check deputy
- Unit tests are not proof of a flow a user can reach: FLOW CHECK is (R8)
- Builders never verify their own work: they ship a click path, someone who did not build it drives the UI
- What a browser cannot prove goes on a standing "needs a real device" list, never counted as verified
- UI CHECK: the real page against the approved mock or the before screenshot, item by item (layout, content, states, behaviour), desktop and phone width; list every difference
- A layout, content or behaviour difference = not done, back to the builder
- A difference from the real UI theme (colours, fonts, spacing tokens) is fine: keep the real theme, list it as "theme difference" in the report
- The owner says pass = pass; agents follow his final decision. Only a critical problem (crash, wrong data, security) goes to him
- Ask `agent-runtime.sh browser` first: chrome, headless or none
- cloud → headless Chromium via Playwright, the extension can never reach a VM
- none → print the click path under NEEDS HUMAN E2E and stop, wait for the human. Never silent, never forever
```

W6: the fast-lane deputy line becomes "- Fast-lane deputy (Sonnet 5, medium) = `agents/fast-lane-deputy.md`, new one per small task: works in its own git worktree, writes the example tests of a small logic task, runs its blocks, pushes a branch"; add after the merge deputy line "- Check deputy (Sonnet 5, medium) = `agents/check-deputy.md`, read and browser tools only: DIFF READ, FLOW CHECK, UI CHECK, re-checks after a bounce, RELEASE SMOKE; a verdict with evidence, the main manager decides" and "- The main manager stays free for the human: it runs no long check itself; it sends the check deputy and gets a short verdict with evidence".

W8: add "- The merge deputy runs `agent-file.sh checks gate <task>` first: GATE REFUSED → no merge, the task goes back", "- A failed run after the merge is undone with `git reset --merge ORIG_HEAD`, never --hard (that wipes the uncommitted agent_*.txt of the main checkout)", "- Every merge ends with cleanup, in every case: a task manager pane, a subagent's git worktree, a human-direct Helper (its own pane stays), a worktree on another machine (agents/merge-deputy.md)", "- The worktree line of a merged task is always removed or rewritten at merge, also when the folder stays", "- human-direct protects only the human's own session pane, not every pane in that worktree; the sweep closes a pane that never got a prompt and is idle over 30 minutes (`unused_pane_min`), and names it", "- The sweep prunes a LAUNCH record whose pid is dead or whose pane is gone; its table never lists main or the release branch; a worktree with a live LAUNCH record is \"live agent\"", "- The plain list shows what --apply would remove; --apply is main manager only"; the Sweep line becomes "- Sweep: `bin/agent-cleanup.sh --apply` after every merge, at session start and when the last open task closes (todo empty, no live worktree). The scripts run it, no loop".

W9: "- Small task (fast lane) → spawn a new deputy subagent, it does the task. No worktree" becomes "- Small task (fast lane) → a new deputy subagent in its own git worktree (Agent isolation worktree); it pushes a branch, a merge deputy merges it" + "- Several small tasks run side by side and never share a checkout (owner 1A 2026-11-25; 21 tasks done this way, median 22 minutes)"; "- Otherwise → new worktree (W7). Never spawn a worktree for a small task" becomes "- Otherwise → new worktree (W7). Never an Orca worktree and a task manager for a small task"; add "- `todo done <X>` releases every task queued after X", "- At every wake (a report, a watch signal, a human message) the main manager first runs `agent-file.sh next` and dispatches what can start: a free slot under the machine caps, RAM under the cap, no open task on the same files", "- A task the owner already approved needs no new question".

W15: add "- After a watch wake the first action is to start the watch again, then handle the signal", "- The watch also wakes the main manager when a slot is free and a task is queued (WATCH SLOT)", "- A board warning (watch not running, not confirmed, a pane without a task line) reaches the main manager through `agent-file.sh next` and the board warning hook; it reacts in the same turn".

S1: "- Core paths of a repo (`level3_paths`, `level4_paths`) live in its committed `agent_repo.conf` at the main repo root, not in Configure" becomes "- Repo facts (core paths, guard tests, test commands, edges, real-data access) live in the committed `agent_repo.conf` at the main repo root, not in Configure (R8)".

F. Map: "Risk types: R8" becomes "Check blocks: R8"; the tree gets "  ├── Check deputy       (Sonnet 5, medium)  diff read, flow and UI checks, release smoke; one at a time on the browser" and the main manager line "(Opus 5.5, xhigh · the main chat · free for the human)"; scripts: "bin/agent-level.sh   the blocks a diff triggers (R8): agent-level.sh check --base <ref>", "bin/agent_blocks.py  the one table of blocks and triggers (R8)", "bin/agent-board-warn.sh  hook: a new or changed board warning into the main manager's context"; commands: "bin/agent-file.sh next  the queued tasks that can start now, then the board warnings", "bin/agent-file.sh checks gate <task> --dir <path>  the merge gate"; Files table: a row for `agent_repo.conf` (init, agents via `edge add` / who reads: agent-level.sh, the gate, init).
Every other "type", "level" or "R8 check" word in PRINCIPLES.md, skills and agents goes (tests/test_check_rules.py LEVEL_WORDS).

## 14. Contract: the watch's slot wake (section 2, tests/test_check_warnings.py TestWatchSlot)

- `agent-watch.sh --all` exits with `WATCH SLOT <name>: can start (run agent-file.sh next)` when `agent-file.sh next` lists START for a line with an open queue wait (after-task closed, or none). A line that never queued never wakes it. Each name is said once: the status file keeps `"slots": [<names said>]`.

## 15. Owner decision 1A, 2026-11-25 13:4x (TELL df880580): no task runs the full suite

- (1) FULL SUITE leaves the table. The largest per-task check is MODULE TESTS: the tests of every module that uses the changed code. A dependency, lockfile, CI or test-config change affects every module, so its module tests are all of them; the owner still signs that change.
- (2) The net: all tests run once every night in the background on the heavy-test machine. It gates nothing. Every failure it finds that the causing task's own RELATED or MODULE run did not find is recorded as a selection miss (one line: the test, the merge that caused it). After two weeks the owner reads the count and decides whether the nightly goes too. A release needs the last nightly on that main to be green, or one background run; no other pre-release run. Who starts it: the housekeep pass of the watch, once per day after a set hour when no heavy test runs; no watch alive -> at the next session start when the last nightly is older than 24 hours, in the background.
- (3) A test run is light or heavy by MEASURED weight, never by its name. The repo file keeps seconds and peak MB per test command or module group (init measures them; each real run updates them). Light (under 120 s and under 1 GB) runs with no slot on the agent's own machine, several at once, under the normal RAM guard. Heavy takes the heavy-test slot (the Heavy test slot/time setting, default 1; the next one starts only when RAM is more than 50% free) on the heavy-test machine. Unknown weight counts as heavy the first time. S5 says this; no new setting for the user.
- (4) This task touches nearly every script, so its module tests are all of them: its one final run stays.

Contract (task manager):
- C1': BLOCKS rows: DIFF SCAN, BUILD, RELATED TESTS, MODULE TESTS, GUARD TESTS, DB CHECK, DATA CHECK, CORE REVIEW (tool); the brief rows unchanged. MODULE TESTS: picked tool; trigger "code used by other modules changed, or dependencies, lockfile, CI or test config changed"; runs "the tests of every module that uses the changed code; a dependency, lockfile, CI or test-config change: the tests of every module"; sign "a dependency, lockfile, CI or test-config change". RELATED TESTS runs text loses its "API change: ..." sentence (that is MODULE TESTS now). NET: NIGHTLY RUN, RELEASE SMOKE.
- C2': `MODULE TESTS: <group folders, ", "> | run: <one cmd per group joined by " ; ">` when a changed code file is named by a file in a `group.<folder>` folder other than its own; deps/lockfile/CI/test config: `MODULE TESTS: every module (<files>) | run: <every group cmd joined by " ; ", or full_cmd when no groups>` and OWNER SIGN `MODULE TESTS (<files>)`. No `group lines` under RELATED TESTS any more. No groups and a plain code change: not triggered.
- C6 nightly: `bin/agent-nightly.sh` (logic `bin/agent_nightly.py`): `--start` runs full_cmd of agent_repo.conf once in the background on the main repo's HEAD of main (writes `<git common dir>/agent_nightly.json`: started, commit, finished, result green|red, failed tests); `--status` prints `NIGHTLY: green|red|running|none <commit> <finished>`; `--due` exit 0 when a start is due (no run today after `nightly_hour` (fixed constant 22) and no heavy run, or no watch alive and the last run older than 24 hours), else 1; `--release-ok` exit 0 only when the last nightly ran on the current origin/main commit and was green, else 1 with one line saying what to run; a red run after a green one records one line per failing test in `<git common dir>/agent_selection_misses.txt`: `<date> | <test> | <merge commit short> <merge subject>` (the first merge on main's first-parent line since the last green nightly that touched a file the test names, else the last merge since then); `--misses` prints them and `misses: <n> since <first date>`.
- C7 weight: `bin/agent-test-run.sh --key <key> -- <command...>`: weight from agent_repo.conf `weight.<key>=<seconds> <MB>`; light = under 120 s and under 1024 MB; unknown or heavy: takes the heavy slot (a lock in the git common dir; waits while it is held) and starts only when RAM used is under 50%; light: only the normal RAM guard; runs the command, prints its output, writes `weight.<key>=<s> <mb>` back into the agent_repo.conf of the git toplevel of the cwd, exits with the command's exit code; first line `TEST RUN <key>: light|heavy (<why>)`. Constants: light_test_s 120, light_test_mb 1024, nightly_hour 22.

## 16. Rule text for sections 15 and the slot default (task manager draft; the rules worker puts it in as written)

R8: the table again from `python3 bin/agent_blocks.py table`. Replace the OWNER SIGN, budget and net lines with:
```
- No task runs the full suite (owner 1A 2026-11-25): MODULE TESTS is the largest per-task check
- OWNER SIGN is planned when a sign fires: MODULE TESTS on a dependency, lockfile, CI or test-config change, DATA CHECK, DB CHECK on a data change; dispatch plans it with CORE REVIEW when the brief changes who can see or do what
- BUILD and GUARD TESTS run per task only when their measured time in agent_repo.conf is under `check_budget_s` (60 s)
- Slower = heavy: it runs in the net; a heavy BUILD takes the heavy-test slot (S5)
- REAL DATA COUNT with no read access: skipped with one printed line, never silently
- Outside tasks, the net: NIGHTLY RUN, all tests once every night in the background on the heavy-test machine (`agent-nightly.sh`); it gates nothing
- A failure the nightly finds that the causing task's own RELATED or MODULE run did not find is a selection miss: one line, the test and the merge (`agent-nightly.sh --misses`)
- After two weeks the owner reads the selection miss count and decides whether the nightly goes too
- The watch's housekeep pass starts it once a day after 22:00 (`nightly_hour`) when no heavy test runs; no watch alive: the next session start, when the last run is older than 24 hours
- A release needs the last nightly on that main to be green, or one background run (`agent-nightly.sh --release-ok`); no other pre-release run
- RELEASE SMOKE after every release: a fresh session uses the released version for real (start, one subagent launch and finish, the user-facing flows that changed)
```
W4 (replaces the whole rule):
```
W4. Multi-agent tests
- Tests are organised module → feature
- No task runs the full suite (owner 1A 2026-11-25). Which tests run follows the blocks (R8): RELATED TESTS and GUARD TESTS per task; MODULE TESTS only when its trigger fires
- Every test run goes through `agent-test-run.sh`: light or heavy by measured weight (S5)
- The main manager and the merge deputy never re-run tests the task manager already passed. Only on a merge conflict: test the conflicted part
- After a bounce: re-run only the tests that failed, not the suite
```
S5 (replaces the whole rule):
```
S5. Heavy tests
- A test run is light or heavy by measured weight, never by its name: `agent_repo.conf` keeps seconds and peak MB per test command or module group (`weight.<key>`); init measures, each real run through `agent-test-run.sh` updates them
- Light (under 120 s and under 1 GB): no slot, on the agent's own machine, several at once, under the normal RAM guard (S4)
- Heavy: the heavy-test slot on the heavy-test machine. Unknown weight counts as heavy the first time
- Start one; once it runs and has settled, start another only if RAM is still more than 50% free; never two at the same moment. The Heavy test slot/time setting is the ceiling, RAM decides below it
- Every test run caps its own parallelism, e.g. `jest --maxWorkers=2`, `flutter test -j 2`
- Every test run that can run in the background runs in the background by default (Bash `run_in_background`)
- Setting "Load: Heavy test slot/time" = 2
```
skills/merge step 8: before `bin/agent-release.sh --push`, run `bin/agent-nightly.sh --release-ok`; exit 1 → `bin/agent-nightly.sh --start` in the background, release after it is green; no other pre-release run.
F map: scripts `bin/agent-nightly.sh  the nightly run of all tests: gates nothing, records selection misses, --release-ok`, `bin/agent-test-run.sh  every test run: light or heavy by measured weight, the heavy-test slot`; commands `bin/agent-nightly.sh --status | --misses | --release-ok`.
Quiz Q9 (rule S5, answer A): see tests/test_check_rules.py QUIZ_Q9.
Every "FULL SUITE" and "NIGHTLY SUITE" word leaves PRINCIPLES.md, skills and agents.

## 17. Owner decision 1A, 2026-11-25 15:0x (TELL 6ce0708e): rapid-development flow

- (1) No task runs the full suite: a task runs its related/module tests and its needed checks, then merges into the WORKING BRANCH.
- (2) Working branch = the branch that does not reach users: in auto-pipeline that is main (users install `release`); a repo whose main deploys to production keeps a branch `dev` as working branch, and dev merges into main only at release. agent_repo.conf names it (`working_branch=`, default main when a release branch exists, else dev); init asks nothing, it detects and writes it.
- (3) The full suite runs ONCE on the working branch before a release (and the nightly net). Failures: the main manager gives them to a NEW fixer agent (fast-lane deputy or a task manager by size), never back to the builder. The release waits until that run is green.
- (4) This task follows it too: no full suite in this task; its final check is the module tests of what it touched (nearly all tests; with a free heavy slot, in 2 processes).

Contract (task manager):
- C8 agent_repo.conf `working_branch=<name>`; init writes it after real_data: `main` when a branch named `release` exists (local or origin), else `dev`; an existing value is never changed. The reader `agent_conf.repo_conf()` gives it, default `main` when the key is missing.
- C9 `agent-file.sh checks gate`: `--base` default `origin/<working_branch>`.
- C10 `agent-nightly.sh`: --start tests the tip of the working branch (local branch `<working_branch>`, else HEAD), in its scratch tree; --release-ok compares with that tip, or its parent when the tip only bumps .claude-plugin/plugin.json; a nightly run started after the bump (on the tip) counts too.
- C11 NET rows: NIGHTLY RUN, RELEASE RUN, RELEASE SMOKE. RELEASE RUN runs: "the full suite once on the working branch before a release (a green nightly on that commit counts); failures go to a new fixer agent, never back to the builder; the release waits until it is green".
- C12 Rule text: R1 step 9 "Merge into the working branch + cleanup"; R8 the working branch and the release run lines; W8 the deputy merges into the working branch; merge skill, merge deputy (brief field `working branch: <name>`, `git merge` there, `git push origin <working branch>`), dispatch brief; quiz Q25 option C ("merge into the working branch + cleanup") and Q35 (rule R8, answer B: a failure of the release run goes to a new fixer agent).

## 18. Rule text for section 17 (task manager draft; the rules worker puts it in as written)

R1 step 9: `  9. Merge into the working branch + cleanup`.
R8, after "- No task runs the full suite ...":
```
- A task merges into the working branch (`working_branch` in agent_repo.conf): the branch that does not reach users; main where users install a release branch, else dev, which merges into main only at release
- RELEASE RUN: before a release the full suite runs once on the working branch (a green nightly on that commit counts)
- The release waits until the release run is green
- A failure of the release run or the nightly goes to a new fixer agent (fast-lane deputy or task manager, by size), never back to the builder
```
and the line "- A release needs the last nightly on that main to be green, ..." becomes "- A release needs a green full run on the working branch: the last nightly on that commit, or one background run (`agent-nightly.sh --release-ok`); no other pre-release run".
W8: "- Deputy merges into the integration branch" becomes "- Deputy merges into the working branch (R8)".
skills/merge: the deputy brief gets `working branch: <working_branch of agent_repo.conf>`; step 8: before a release, `agent-nightly.sh --release-ok` (else `--start` in the background): the full suite once on the working branch; a failure goes to a new fixer agent (fast-lane deputy or task manager by size), never back to the builder; the release waits until it is green; a repo with a dev working branch releases by merging dev into main.
agents/merge-deputy.md: `<working branch>` in "Your brief gives"; the gate with `--base origin/<working branch>`; `git checkout <working branch>` then `git merge --no-ff origin/<branch>`; `git push origin <working branch>` (never a fixed `main`).
skills/dispatch: `orca worktree create ... --base-branch <working branch>`; the brief's WHERE names the working branch; the REPORT line: the task's CHECK lines, indented by two spaces (state add refuses a line that starts with CHECK).
Quiz: Q25 and Q35 as tests/test_check_rules.py QUIZ_Q25 and QUIZ_Q35 (Q35: answer B, RULE R8).

## 19. Owner principle 2026-11-25 15:1x (TELL bd0506cc), for the plugin: the outcome is the proof, tests are a cheap guard

His words: let other agents verify the outcome of the code instead of letting test cases do it; tests only show old things still work, and they cost too much memory and time; an urgent fix that has to wait for the test flow is a disaster. The head of the check rules:
- (1) The proof that a change is right = an agent that did not build it checks the OUTCOME against what the owner approved: reads the diff and runs the real thing once (the feature path, the page, the command). That is the main check of every task.
- (2) Tests are a cheap guard only: a task runs only its related tests that are LIGHT (measured: short and small); a heavy test never blocks a merge, it goes to the run on the working branch before release or the nightly.
- (3) The full suite never runs in a task (already decided).
- (4) URGENT FIX path: smallest fix -> one verifier agent checks the outcome -> light related tests -> merge and release at once; everything heavy runs afterwards, and a failure there goes to a new fixer agent.
- (5) Verifier checks are short: only what the owner approved, a time box (default 15 min), extra finds go to the ideas file.

Contract (task manager):
- C13 Table: OUTCOME CHECK is the first row: picked tool, trigger "every task", runs "an agent that did not build it checks the outcome against what the owner approved: reads the diff and runs the real thing once (the feature path, the page, the command; a path a user can reach: one normal and one error path); the main check of every task; short: what the owner approved, a 15-minute time box, extra finds go to the ideas file", sign "no". DIFF READ and FLOW CHECK leave the table (OUTCOME CHECK holds both). UI CHECK stays (brief). RELATED TESTS runs: "only the LIGHT tests (measured) that import or name the changed files ... ; a heavy one goes to the release run or the nightly". MODULE TESTS runs: light module groups only; a heavy one goes to the release run or the nightly. 12 rows: OUTCOME CHECK, DIFF SCAN, BUILD, RELATED TESTS, MODULE TESTS, GUARD TESTS, DB CHECK, DATA CHECK, CORE REVIEW (tool); EXAMPLES TEST, UI CHECK, REAL DATA COUNT (brief).
- C14 agent-level.sh: OUTCOME CHECK is in every BLOCKS line (first); `OUTCOME CHECK: an agent that did not build it: read the diff, run the real thing once (15 min box)`. RELATED TESTS and MODULE TESTS whose measured weight is heavy (key `related`, `group.<folder>`, `full` for every module; agent_test_weights.json or the repo file seed; heavy = light_test_s / light_test_mb or more) leave BLOCKS for one line each: `NET: RELATED TESTS (heavy, <s> s, <mb> MB): the release run or the nightly` / `NET: MODULE TESTS (heavy, ...): the release run or the nightly`; OWNER SIGN for a dependency, lockfile, CI or test-config change stays planned. Unmeasured: runs per task.
- C15 The gate's builder rule covers OUTCOME CHECK and UI CHECK. Constant `verify_box_min` = 15 (bin/agent_conf.py).
- C16 Rule text: R8 starts with the principle (owner words, the five points); W4, W5 (the check deputy runs OUTCOME CHECK); the urgent fix path in R8 replaces the old "Urgent fix" kind line; dispatch (every task plans its OUTCOME CHECK; urgent path); merge skill (urgent: release at once, then `agent-nightly.sh --start`, a failure to a new fixer agent); check deputy (OUTCOME CHECK, 15-minute box, extra finds to `agent-file.sh idea add`); quiz Q38 (OUTCOME CHECK), Q39 (the urgent fix, answer B).

## 20. Rule text for section 19 (task manager draft; the rules worker puts it in as written)

R8 head (right after the heading, before the owner's "only do the necessary thing" line):
```
- Owner 2026-11-25: "let other agents verify the outcome of the code instead of letting test cases do it"; tests only show old things still work and cost memory and time; an urgent fix must not wait for a test flow
- The proof that a change is right: an agent that did not build it checks the outcome against what the owner approved
- It reads the diff and runs the real thing once (the feature path, the page, the command): OUTCOME CHECK, the main check of every task
- Tests are a cheap guard only: a task runs only its LIGHT related and module tests (measured, S5); a heavy test never blocks a merge, it goes to the release run on the working branch or the nightly
- The full suite never runs in a task
- URGENT FIX: the smallest fix, one OUTCOME CHECK, the light related tests, then merge and release at once; everything heavy runs afterwards, and a failure there goes to a new fixer agent
- Verifier checks are short: only what the owner approved, a 15-minute time box (`verify_box_min`), extra finds go to the ideas file
```
R8 body: "DIFF READ, FLOW CHECK and UI CHECK pass only by ..." becomes "OUTCOME CHECK and UI CHECK pass only by someone who did not build the task: not the builder (...)"; the four-kinds line "Urgent fix (production is broken): ..." becomes "  - Urgent fix (production is broken): the URGENT FIX path above". The table from `python3 bin/agent_blocks.py table`.
W4: "Which tests run follows the blocks (R8): the LIGHT RELATED TESTS and GUARD TESTS per task; MODULE TESTS only when its trigger fires, light ones only; a heavy one goes to the release run or the nightly".
W5 and W6: the check deputy runs OUTCOME CHECK, UI CHECK, re-checks after a bounce and RELEASE SMOKE (no DIFF READ, no FLOW CHECK anywhere).
skills/dispatch: every task gets its OUTCOME CHECK (the tool plans it; the brief says what the owner approved, which is what the check deputy checks); the brief blocks are EXAMPLES TEST, UI CHECK, REAL DATA COUNT, and CORE REVIEW,OWNER SIGN for who-can-see-or-do; an "URGENT FIX" paragraph: smallest fix by one fast-lane deputy, one OUTCOME CHECK by a check deputy, light related tests, merge and release at once, then `agent-nightly.sh --start` in the background; a failure there goes to a new fixer agent.
skills/merge: the OUTCOME CHECK and UI CHECK go to a check-deputy; an URGENT FIX releases at once (no release-run wait), then `agent-nightly.sh --start`; a failure goes to a new fixer agent, never back to the builder.
agents/check-deputy.md: OUTCOME CHECK = read the diff, run the real thing once (the feature path, the page, the command), only what the owner approved, a 15-minute time box, extra finds go to `agent-file.sh idea add`; UI CHECK as before.
agents/fast-lane-deputy.md and agents/merge-deputy.md: OUTCOME CHECK in place of DIFF READ and FLOW CHECK.

## 21. Correction of section 19 (TELL db3ae549, owner and main manager argued it out, 2026-11-25): THIS version holds

- (1) Main check of every task = a PR-style review: an agent that did not build it reads the diff against the approved requirement (does it do what was asked, nothing else, edge list lines covered, no check deleted, no secret). Its cost follows the diff size, one more reason for small tasks. This replaces "reads the diff and runs the real thing once" for every task.
- (2) A run or browser check comes on top ONLY when what the user sees or does changed; time box 15 min; only the approved items; extra finds go to the ideas file.
- (3) Tests stay: light related tests in every task; a bug that a review or check finds gets a small test with its fix (as W3 already says for bugs). The full suite is the safety net only: working branch before release + nightly.
- (4) Pre-release run, failures: the tool finds for each failing test the merge that introduced it (run that test file across the merges since the last green run); the fixer agent gets test + merge + that task's requirement and must label each one: "test out of date" (update it and cite the requirement line or commit that changed the behaviour on purpose) or "real break" (fix the code). No check is deleted without a twin; the fixer's report is a table of these labels.
- (5) Urgent fix: branch from the latest stable release (the commit the release branch was built from), smallest fix, PR-style review, light related tests, release alone; then merge it back into the working branch.

Contract (task manager; replaces C13-C16 where they differ):
- C13' Table, 13 rows: PR REVIEW (tool, "every task", runs: "an agent that did not build it reads the diff against the approved requirement: does it do what was asked and nothing else, are the edge list lines covered, is no check deleted, no secret; its cost follows the diff size", sign no), DIFF SCAN, BUILD, RELATED TESTS (LIGHT only; heavy -> release run or nightly), MODULE TESTS (light only), GUARD TESTS, DB CHECK, DATA CHECK, CORE REVIEW; brief: EXAMPLES TEST, FLOW CHECK (trigger "what a user does changes"; runs "someone who did not build it runs 1 normal path + 1 error path: only the approved items, a 15-minute time box, extra finds go to the ideas file"), UI CHECK (trigger "what a user sees changes: new page, re-layout, size or responsive change"; runs as before + "a 15-minute time box, extra finds go to the ideas file"), REAL DATA COUNT. No OUTCOME CHECK, no DIFF READ.
- C14' agent-level.sh: PR REVIEW first in every BLOCKS line; its line `PR REVIEW: an agent that did not build it reads the diff against the approved requirement`. The light-only NET lines of C14 stay.
- C15' The gate's builder rule covers PR REVIEW, FLOW CHECK, UI CHECK. verify_box_min = 15 stays.
- C17 `agent-nightly.sh --failures`: for the last red run, each failing test's file is run (related_cmd with its {tests}/{modules}) at each first-parent merge since the last green commit, oldest first, in a scratch worktree; the first merge where it fails introduced it. One row per failing test: `<test> | <merge short> <merge subject> | <task> | <requirements/<task>.md or ->` (task from a subject "Merge <task> ..."); no green run before: merge `-`. The selection-miss line uses the same merge.
- C18 `agent-release.sh --source` prints the commit the release tip was built from (its message "release <v> from <short>"). `agent-release.sh --urgent [--from <ref>]`: build (and with --push, push) from a commit that is not on main, only when the release source commit is its ancestor; the version must still be higher; refused otherwise.
- C19 Rule text: R8 head per (1)-(5); a bug a review or check finds gets a small test with its fix; the fixer report table (test | merge | task | label | cite or fix); no check deleted without a twin; urgent path per (5) with merge back into the working branch; check deputy; dispatch; merge skill; quiz Q38 (PR REVIEW) and Q39 (urgent: branch from the latest stable release, review, light tests, release alone, merge back).

## 22. Rule text for section 21 (replaces section 20's draft; the rules worker puts it in as written)

R8 head (right after "R8. Check blocks", before the owner's "only do the necessary thing" line):
```
- Owner 2026-11-25: "let other agents verify the outcome of the code instead of letting test cases do it"; tests only show old things still work and cost memory and time; an urgent fix must not wait for a test flow
- PR REVIEW, the main check of every task: an agent that did not build it reads the diff against the approved requirement
- It asks: does it do what was asked, nothing else; are the edge list lines covered; is no check deleted; no secret. Its cost follows the diff size, one more reason for small tasks
- A run or browser check (FLOW CHECK, UI CHECK) comes on top only when what the user sees or does changed: only the approved items, a 15-minute time box (`verify_box_min`), extra finds go to the ideas file
- Tests stay as a cheap guard: light related tests in every task; a bug that a review or check finds gets a small test with its fix (W3)
- The full suite is the safety net only: the release run on the working branch and the nightly, never in a task; a heavy test never blocks a merge
- URGENT FIX: branch from the latest stable release (`agent-release.sh --source`), the smallest fix, PR REVIEW, the light related tests; release it alone (`agent-release.sh --urgent`), then merge it back into the working branch
```
R8 body, after the RELEASE RUN lines:
```
- Release run failures: `agent-nightly.sh --failures` names, for each failing test, the merge that introduced it (it runs that test across the merges since the last green run)
- The new fixer agent gets the test, the merge and that task's requirement, and labels each: "test out of date" (update it, cite the requirement line or commit that changed the behaviour on purpose) or "real break" (fix the code)
- No check is deleted without a twin; the fixer's report is a table of these labels: test | merge | task | label | cite or fix
```
R8 body, other lines: "OUTCOME CHECK and UI CHECK pass only by ..." becomes "PR REVIEW, FLOW CHECK and UI CHECK pass only by someone who did not build the task: not the builder (...)"; the four-kinds "Urgent fix" line becomes "  - Urgent fix (production is broken): the URGENT FIX path above". Remove section 20's head lines ("The proof that a change is right", "runs the real thing once", "OUTCOME CHECK"). The table from `python3 bin/agent_blocks.py table`.
W4: "Which tests run follows the blocks (R8): the light RELATED TESTS and GUARD TESTS per task; MODULE TESTS only when its trigger fires, light ones only; a heavy one goes to the release run or the nightly".
W5: the check deputy drives the browser for FLOW CHECK, UI CHECK and RELEASE SMOKE, one at a time (keep "never verify their own work").
W6: the check deputy runs PR REVIEW, FLOW CHECK, UI CHECK, re-checks after a bounce, RELEASE SMOKE.
skills/dispatch: every task gets its PR REVIEW (the tool plans it; the brief says what the owner approved); FLOW CHECK and UI CHECK only when what the user does or sees changes; an "URGENT FIX" paragraph: `agent-release.sh --source` names the latest stable release; a fast-lane deputy branches from it, makes the smallest fix; a check deputy does the PR REVIEW; the light related tests; release alone with `agent-release.sh --urgent`; then merge it back into the working branch.
skills/merge: PR REVIEW, FLOW CHECK and UI CHECK go to a check-deputy; release step: `agent-nightly.sh --release-ok`, else `--start`; on a red release run `agent-nightly.sh --failures` and a new fixer agent (fast-lane deputy or task manager by size, never the builder) with the test, the merge and the requirement, labels "test out of date" or "real break"; URGENT FIX: `agent-release.sh --urgent`, then merge it back into the working branch.
agents/check-deputy.md: PR REVIEW = read the diff against the approved requirement (asked, nothing else, edge list lines, no check deleted, no secret); FLOW CHECK and UI CHECK only the approved items, a 15-minute time box, extra finds go to `agent-file.sh idea add`.
agents/fast-lane-deputy.md and agents/merge-deputy.md: PR REVIEW in place of DIFF READ; a bug found in review gets a small test with its fix.

## 23. Slice 8 addition (TELL 9a3a99b5, owner 2026-11-25: "when an agent is already continue with you and already direct report to you, why it is still useful for human?")

- A human-direct session keeps its protection only while the human alone drives it. Once it takes a task from the main manager or reports DONE to it, it is a normal agent: at the merge of its last open task its pane is closed and its worktree line removed, like a task manager. The close message names the resume command (`claude --resume <session id>`). (Seen 2026-11-25: the Helper stayed open and listed after two merges until the owner asked.)

Contract (task manager):
- C20 `agent-file.sh helper-join "<task>"`: only a human-direct Helper (role second) runs it, when it takes a task from the main manager or reports DONE to it. Its folder's human-direct line becomes `<path> | <task> | working | since <date> | pane <ORCA_TERMINAL_HANDLE or -> | session <CLAUDE_CODE_SESSION_ID or ->`; prints `helper-join: <task> (pane <h>, session <s>): a normal agent now; the merge of its last task closes this pane`. Any other role: refused, nothing written.
- C21 Rule text: W10 (protection only while the human alone drives it; helper-join; closed at the merge of its last open task; `claude --resume <session id>`); agents/merge-deputy.md (a joined Helper: its line's pane is closed and the line removed, like a task manager; the report names `claude --resume <session id>`); skills/merge (the deputy brief's `session: helper` only while the human alone drives it); skills/dispatch (a task given to a live Helper: the TELL starts with "run agent-file.sh helper-join first").

## 24. Owner decisions 2026-11-25 15:4x (TELL 076c1faf): memory, not slots; jobs go to connected machines. REPLACES the slot rule (the default 2 of TELL de03b3fb is void)

- (A) No slots. Remove the setting "Load: Heavy test slot/time" (Configure holds 15 items) and the heavy-test lock. A run (a test command, a build, a new agent pane) starts when: memory in use now + the memory this run is known to need <= the limit ("Load: Max memory %", default 80). "Known to need" = the measured peak MB (a Claude pane counts too: measure it, about 300-550 MB here); not measured yet = it starts alone once and gets measured. CPU: a parallel test runner uses as many processes as keep CPU under the same limit; memory is the hard gate, CPU the soft one. Long but light runs just go.
- (B) One small shared reservation list per machine (every running job: pid, reserved MB; a dead pid frees its entry), so two agents, also of different repos, never count the same free memory.
- (C) Placement, plugin principle: every job goes to a connected machine first (the one with the most room by rule A); the local machine only when no connected machine has room or the job needs it; no machine is special any more ("tests only on the heavy-test machine" goes). Local stays clean and fast for the human.
- (D) Whatever is sent to another machine is cleaned up there when it is done: pane, worktree, branches, scratch clones, temp test folders, its reservation; the sweep covers every connected machine and its list names what is left there.
- S3-S6 and the quiz follow; tests first.

Contract (task manager):
- C22 Settings: heavy_test_slots leaves SETTINGS (15 settings), plugin.json userConfig follows; an old value of it in Configure or an old file is ignored (never moved, never an error). Constants light_test_s / light_test_mb stay for the per-task light-test rule of R8 only.
- C23 Reservation list: one JSON file per machine at `$AGENT_RESERVE_FILE`, default `~/.claude/auto-pipeline-reservations.json`: `{"jobs": [{"pid", "mb", "what", "repo", "since"}]}`; an entry whose pid is dead is dropped on every read; writes under a lock file next to it.
- C24 `bin/agent-room.sh` (logic in bin/agent_nightly.py): `check <mb>|unknown` -> exit 0 when used MB now + the live reservations' MB + <mb> <= total MB x max_usage_percent / 100, else exit 1 with `ROOM: no: <used> MB in use + <reserved> MB reserved + <need> MB > <limit> MB`; `unknown` -> room only when no live reservation exists (it starts alone); `reserve <pid> <mb> "<what>"`, `release <pid>`, `list` (one line per live job). Test hooks: AGENT_FAKE_RAM (percent in use), AGENT_FAKE_RAM_TOTAL_MB.
- C25 `agent-test-run.sh`: no slots, no heavy-test lock. It reserves its measured peak MB (weights json; repo file seed) while it runs and releases after; unknown weight: starts only alone, then measured; it waits (capped by AGENT_TEST_RUN_WAIT_S) while `check` says no, then exit 3 with the ROOM line; `{workers}` in the command becomes the process count that keeps CPU under max_usage_percent (cores x (limit - CPU in use) / 100, at least 1). First line `TEST RUN <key>: <mb> MB known (<s> s)` or `TEST RUN <key>: unknown weight, starts alone`. The nightly uses the same gate.
- C26 Rule text: S3-S6 rewritten (memory gate, reservation list, CPU soft); placement (C) in W7/W9 and the dispatch skill (a new pane or job: the connected machine with the most room first; `agent-room.sh check` there); (D) in W8 and the merge deputy (remote: pane, worktree, branches, scratch clones, temp test folders, its reservation); no "heavy-test machine", no "heavy-test slot" anywhere; quiz Q9 (memory gate).
- C24/C25 details pinned by the tests: `check unknown` with live jobs -> `ROOM: no: unknown weight starts alone (<n> jobs running)`; `{workers}` = floor(cores x (limit - CPU in use) / 100), at least 1; test hooks AGENT_FAKE_CPU (percent in use) and AGENT_FAKE_CORES; the nightly `--start --wait` with no room after the capped wait: exit 3 with the ROOM line, nothing recorded.

## 25. Owner 2026-11-25 15:5x (TELL bd4e87ee): two changes to rule (A) of section 24

- (E) A run that was never measured is NOT held back to run alone: it starts at once with a monitor on its memory (and the monitor runs for every test or build run, measured or not, because a measured number can be wrong). If the run pushes the machine over the limit, the monitor stops that run (the newest, unmeasured one first), records its peak MB, and the run is tried again when there is room. Only test and build runs are stopped this way; they can be run again.
- (F) Count caps go: remove the setting "Load: Max agents" (Configure holds 14 items) and every fixed count of agents, task managers or subagents per machine (S6 and the like). A new agent pane is admitted by the same rule as any job: memory in use + what a pane needs <= the limit, CPU under the limit. Over the limit: start nothing new; close done and idle panes first; stop test runs before anything else; never stop a working agent, tell the main manager instead (one line: which machine, how much over, what it did). Quiz Q8 and the questions about max agents follow. Tests first.

Contract (task manager; replaces the "starts alone" parts of C24/C25):
- C27 `agent-room.sh check unknown` = room when memory in use <= the limit (need 0); the reservation entry gets `"kind": "test"|"build"|"pane"` and `"measured": true|false`.
- C28 Monitor: every `agent-test-run.sh` run samples machine memory (AGENT_FAKE_RAM_FILE: a file the runner re-reads each sample, tests only) every 0.5 s; over the limit: the pick among live test/build jobs is the newest unmeasured, else the newest; the pick's runner stops its run (the whole process group), records its peak MB in the weights json, prints `TEST RUN <key>: stopped over the limit (<used> MB > <limit> MB), peak <mb> MB recorded`, then waits for room (the wait cap) and runs again; no room within the cap: exit 3. A runner that is not the pick goes on.
- C29 `agent-room.sh measure-pane <pid>`: summed RSS of that process tree -> weights `pane` (keeps the highest); agent-start.sh runs it for its own session once. `agent-room.sh relief`: over the limit, stop live test/build jobs newest-unmeasured-first until the reserved MB freed brings it under; never a pane or another kind; one line `OVER LIMIT <host>: <n> MB over; stopped <k> test runs (<pids>); working agents left alone` (`<k>` may be 0); under the limit: `ROOM: ok` and nothing stopped.
- C30 Settings: max_agents leaves SETTINGS (14 settings), plugin.json follows; an old value is ignored. `agent-file.sh next`: `NEXT: <n> can start (room <free> MB under the <limit>% limit)` / `NEXT: 0 can start: no room: <used> MB in use + <reserved> MB reserved + <pane> MB for a pane > <limit> MB`; agent-resume.sh relaunches panes by the same memory rule, no count cap.
- C31 Rule text: S4 (over the limit: start nothing new, close done and idle panes first, stop test runs first, never a working agent, tell the main manager), S6 (no count caps; a pane passes the memory rule), W7 (no "Max agents"), dispatch step 6; quiz Q8 (answer C).
- C27-C29 details pinned by the tests: `reserve <pid> <mb> "<what>" [--kind test|build|pane] [--unmeasured]` (default kind test, measured); each entry keeps `started` (epoch seconds) to order "newest"; the host of the OVER LIMIT line = AGENT_FAKE_HOST or the short host name; the unknown first line `TEST RUN <key>: unknown weight, starts at once, monitored`; the pane need while unmeasured: 550 MB (`NEXT: 0 can start: no room: <used> MB in use + <reserved> MB reserved + <pane> MB for a pane > <limit> MB`; resume: `no room (<used + reserved + planned> MB + <pane> MB > <limit> MB), not relaunching <path>`, row "no, no room").

## 26. Owner 2A 2026-11-25 16:1x (TELL 173d8a8b): the Reviewer model

- New Configure item "Models: Reviewer model" (key `reviewer_model`), default opus-5.5:high (same as the managers); Configure holds 15 items. The PR-style reviewer of every task runs on it; the CORE REVIEW uses it too. A reviewer decides: the decider floor holds (a model below it is refused).
- R1 states one fixed sequence: builder reports done -> reviewer reads the diff against the approved requirement -> check deputy only when what the user sees or does changed (15 min box) -> merge deputy. A fail at review or check goes back to the builder as a fix order.
- `agents/reviewer.md` (new): model opus, read-only tools (Read, Grep, Glob, Bash); runs PR REVIEW and CORE REVIEW; writes its line with `agent-file.sh check <task> "PR REVIEW" pass|fail --by "<task> Review"`; a fail is a fix order to the builder. The merge skill sends it (`subagent_type: reviewer`, model from `reviewer_model`) before the check deputy. The check deputy keeps FLOW CHECK, UI CHECK, RELEASE SMOKE.
- Changed defaults to list in the report: Reviewer model opus-5.5:high (new); Max agents and Heavy test slot/time removed.

## 27. Rule text for sections 23-26 (task manager draft; the rules worker puts it in as written, with sections 18 and 22)

R1, after the flow list (step 9 "Merge into the working branch + cleanup"):
```
- One fixed sequence after the build: builder reports done -> reviewer reads the diff against the approved requirement (PR REVIEW, on the Reviewer model) -> check deputy only when what the user sees or does changed (15 min box) -> merge deputy
- A fail at review or check goes back to the builder as a fix order
```
S3 (replaces the rule):
```
S3. Resource guard
- A run (a test command, a build, a new agent pane) starts when memory in use now + the memory this run is known to need <= the "Load: Max memory %" limit (default 80): `agent-room.sh check`
- Known to need = the measured peak MB; a Claude pane counts too (about 300-550 MB; 550 MB while never measured)
- A run that was never measured is not held back: it starts at once with a monitor on its memory; the monitor runs for every test or build run, measured or not
- Over the limit the monitor stops the newest, unmeasured one first, records its peak MB, and the run is tried again when there is room. Only test and build runs are stopped
- CPU: a parallel test runner uses as many processes as keep CPU under the same limit (`{workers}`); memory is the hard gate, CPU the soft one. Long but light runs just go
```
S4 (first lines; keep the existing relief, stop-leftovers and "the human's apps" lines):
```
- Over the limit: start nothing new; close done and idle panes first; stop test runs before anything else (`agent-room.sh relief`)
- Never stop a working agent: tell the main manager instead, one line: which machine, how much over, what it did
```
S5 (replaces the rule):
```
S5. Test runs
- Every test run goes through `agent-test-run.sh`: it reserves its measured peak MB while it runs, and the monitor watches it
- One small shared reservation list per machine (every running job: pid, reserved MB; a dead pid frees its entry): two agents, also of different repos, never count the same free memory
- Measured weights live per machine (`agent_test_weights.json` in the git common dir); `agent_repo.conf` `weight.<key>` lines are seeds only
- Every test run caps its own parallelism, e.g. `jest --maxWorkers=2`, `flutter test -j 2`
- Every test run that can run in the background runs in the background by default (Bash `run_in_background`)
```
S6 (replaces the first two lines; keep the "finished idle pane" lines):
```
S6. No count caps
- No count caps: no fixed count of agents, task managers or subagents per machine; a new agent pane is admitted by the same rule as any job (S3)
```
W7: "Main manager runs the task itself with `Agent` subagents, up to the Max agents setting" becomes "... with `Agent` subagents, each admitted by the memory rule (S3)"; drop "Every spawned agent counts toward the Max agents setting (S6). The main manager does not"; add "- Placement: every job goes to a connected machine first (the one with the most room by S3); the local machine only when no connected machine has room or the job needs it; no machine is special; local stays clean and fast for the human".
W8, add: "- Whatever is sent to another machine is cleaned up there when it is done: pane, worktree, branches, scratch clones, temp test folders, its reservation; the sweep covers every connected machine and its list names what is left there".
W9, add: "- A new worktree or pane goes to the connected machine first that has room (W7, S3)".
W10, add: "- A human-direct session keeps its protection only while the human alone drives it. Once it takes a task from the main manager or reports DONE to it, it runs `agent-file.sh helper-join "<task>"` and is a normal agent: the merge of its last open task closes its pane and removes its line, like a task manager; the close message names `claude --resume <session id>`".
W6: add "- Reviewer (Reviewer model, default opus-5.5:high) = `agents/reviewer.md`: PR REVIEW of every task and CORE REVIEW; read only; a fail is a fix order to the builder"; the check deputy line keeps FLOW CHECK, UI CHECK, re-checks after a bounce, RELEASE SMOKE.
W17: the reviewer decides (floor).
F map: the tree gets "├── Reviewer (Opus 5.5, high) PR review of every task, core review; read only"; scripts "bin/agent-room.sh  the memory gate: check, reserve, release, list, relief, measure-pane"; no "Max agents", no "slot".
skills/dispatch: step 6 "6. A new pane or job: `agent-room.sh check <pane MB>` on the connected machine first; no room anywhere → close done and idle panes first, then wait and tell the human" (no max_agents); a task given to a live Helper: its TELL starts with "run `agent-file.sh helper-join "<task>"` first".
skills/merge: after DONE PASS: `Agent` with `subagent_type: reviewer`, model from `${CLAUDE_PLUGIN_ROOT}/bin/agent-settings.sh get reviewer_model`, description `<name> Review` → PR REVIEW (and CORE REVIEW when planned); a fail → a fix order to the builder; then the check deputy only when what the user sees or does changed; the deputy brief's `session: helper` only while the human alone drives it (a Helper that ran helper-join is `task manager`, its pane handle from its line).
agents/merge-deputy.md: a Helper that ran helper-join (its line has `pane` and `session`): close its pane like a task manager and remove its line; the report names `claude --resume <session id>`; on another machine also its scratch clones, temp test folders and its reservation.
agents/reviewer.md (new): frontmatter name reviewer, description, model: opus, tools: Read, Grep, Glob, Bash; body: the floor check of the sender; "Model and effort: the Reviewer model setting"; PR REVIEW = read the diff against the approved requirement: does it do what was asked, nothing else, are the edge list lines covered, no check deleted, no secret; CORE REVIEW when planned: the logic against the rules the owner approved; one line `agent-file.sh check "<task>" "PR REVIEW" pass|fail --by "<task> Review" --evidence "<text>"`; a fail is a fix order to the builder (where, what is seen, what is expected, evidence); never edits files.
Quiz: Q8, Q9, Q25, Q35, Q38, Q39 exactly as tests/test_check_rules.py QUIZ_Q8 .. QUIZ_Q39 (answers 8C 9A 25C 35B 38B 39B; RULE Q35 R8).

## 28. Owner decision 2026-11-25 15:3x (TELL 76bfcc8f): one working-branch model for every repo. REPLACES the working-branch parts of sections 17-18 and the urgent path of section 21 (5) / C18

- (1) New Configure item "Flow: Working branch", default "ap-worktree" (Configure then holds 16 items).
- (2) In every repo the plugin keeps a branch of that name with its own git worktree (init creates both from the production branch; the cleanup sweep never removes them). Every task branches from the working branch and is merged into it by the merge deputy, inside that worktree, never in the user's main checkout, which stays on the production branch.
- (3) The full suite runs in the background on the working branch after merges (one run covers the merges that landed meanwhile; a docs-only merge starts none); red -> a fixer agent gets that failure with the merge that caused it.
- (4) Production: the working branch goes to the production branch (the repo's default branch; agent_repo.conf may name another) ONLY on the owner's approval (verified words) and only from a green commit. In a repo with a release build (this one: bin/agent-release.sh) that build runs right after that merge, by itself: so "merged to production = published" holds everywhere.
- (5) Urgent fix: branch from the production branch, review + related tests + the owner's yes, merge to production, then merge production back into the working branch.
- (6) The first version that ships this still goes out the old way (by hand from main); the new flow starts with it.

Contract (task manager):
- C32 Setting `working_branch` ("Flow: Working branch", string, default "ap-worktree", right after todo_before_agent; 16 settings). agent_repo.conf: optional `production_branch` (missing: the target of origin/HEAD, else main); no working_branch key. C8 (detection) and C18 (release --source/--urgent) are void.
- C33 init: creates, when missing, the working branch from the production branch and a git worktree for it at `<parent of the main repo>/<main repo folder>-<working branch>`; keeps existing ones; lines `working branch: created <b> from <prod>` / `working branch: kept <b>`, `working worktree: created <path>` / `working worktree: kept <path>`.
- C34 The sweep never removes, and never lists as a row, the working branch or its worktree (local or origin).
- C35 `agent-nightly.sh --after-merge`: run by the merge deputy after each merge, in the background: the diff of the merge (HEAD^1..HEAD of the working branch) only text or rule files -> `after-merge: docs-only merge, nothing to run` and nothing starts; a run already going -> `after-merge: a run is going, one more run when it ends` (status `pending: true`; when that run ends it starts one more); else it starts the run (as --start). A red run names each failure's merge (--failures) for a new fixer agent.
- C36 `bin/agent-promote.sh --owner-quote "<words>" [--time <t>]`: from the main repo; refused (one line, exit 1, nothing changes) unless agent-owner-order.sh verify accepts the words, the last run is green on the working branch tip (`agent-nightly.sh --release-ok` against that tip), and the production branch is an ancestor of the working branch tip (fast-forward only). Then `git push origin <working>:<production>`, the main checkout (when clean and on production) `git merge --ff-only origin/<production>`, and, when the repo has `bin/agent-release.sh`, it runs `bin/agent-release.sh --push` right after; lines `promote: <production> -> <short> (<subject>)`, `release: ran bin/agent-release.sh --push` (or `release: no release build in this repo`).
- C37 Urgent fix: a branch from the production branch; PR REVIEW + light related tests + the owner's yes; merge to production (the release build runs right after, like a promote); then merge production back into the working branch. Rule text only (no new command).
- C38 Rule text: R1, W7, W8, W9, merge skill, merge deputy (cd into the working-branch worktree, merge and push there; never the main checkout), dispatch brief (tasks branch from the working branch), init skill, quiz Q39 (the urgent path) per tests.

## 29. Owner correction 15:4x (TELL 84fbcf51) to section 28 point (2): no separate worktree

- It is only a branch. The repo's main checkout (where the main manager sits) is switched to the working branch, so everything that is merged or pushed lands there first and never on the production branch by accident; init creates the branch from the production branch and switches the checkout to it; the merge deputy merges into it in that checkout as today. Points (1), (3), (4), (5), (6) stay.
- The default NAME is not final (the owner finds "ap-worktree" unsuitable and is choosing): one constant, easy to change (`agent_conf.WORKING_BRANCH_DEFAULT`); the main manager sends the name.

Contract changes: C33' init: creates the working branch from the production branch when missing and switches the main checkout to it (`git switch`; local changes are carried, a switch that git refuses is left as it is and said); lines `working branch: created <b> from <prod>` / `working branch: kept <b>`, `checkout: switched to <b>` / `checkout: on <b>` / `checkout: not switched: <git's reason>`; no worktree. C36' promote: the main checkout stays on the working branch; the local production branch ref follows the pushed tip (`git branch -f`, or a fast-forward fetch); nothing else in the checkout changes.

## 30. Owner 2026-11-25 15:5x (TELL 3a66d74e): the working branch is "ap-main"; the target comes from the request. REPLACES "background full run after every merge" (C35)

- (a) TARGET: the user's request decides. It says publish or merge to main -> the task, once its own checks pass (its blocks; no full suite), is merged straight into the production branch, and the deploy follows by itself (this repo: the release build; a repo like v4: its own sync). No such words, or unclear -> the working branch ap-main; nothing goes to production by itself.
- (b) BATCH: several tasks given together (x1..x4, several task managers) all merge into ap-main; when the last one of the batch is merged, ONE full suite runs on ap-main (not one per merge); red -> a fixer agent; then the main manager reports and the owner approves ap-main -> production, from a green commit.
- (c) BASE: a task that goes straight to production branches from the production branch; a task for ap-main branches from ap-main (it then sees the batch's earlier merges); after any direct merge into production, production is merged back into ap-main at once so they never drift.
- (d) A new request may also wait until ap-main is tested and published; the main manager picks what is faster and says which.
- (e) The main checkout sits on ap-main (only a branch, no extra worktree); a direct merge into production must not need a checkout switch that would disturb it (merge in a short-lived worktree of the production branch, removed right after).
- The full suite runs when a batch is complete or before a publish from ap-main.

Contract (task manager):
- C39 `agent_conf.WORKING_BRANCH_DEFAULT = "ap-main"`. C35 (--after-merge) is void.
- C40 todo line: `todo add ... --target production|working` (field ` | target production`; missing = working) and `--batch <name>` (field ` | batch <name>`). `todo done "<X>"`: when X had a batch and no open line of that batch is left: `batch <name>: all merged: run the full suite on <working branch>: agent-nightly.sh --start`.
- C41 The gate's `--base` default: `origin/<production branch>` for a todo line with `target production`, else `origin/<working branch>`.
- C42 `agent-promote.sh --task "<task>" --branch <branch> --owner-quote "<words>" [--time <t>]` (the direct path): verify the words; a short-lived worktree of `origin/<production>` in the git common dir, `git merge --no-ff origin/<branch> -m "Merge <task> (W8)"`, `git push origin HEAD:<production>`, the worktree removed (also on failure); the release build when the repo has `bin/agent-release.sh`; then production is merged back into the working branch in the main checkout (when it is on the working branch and has no change other than agent_*.txt; else one line saying it waits) and `git push origin <working branch>`. Lines: `promote: <task> -> <production> (<short>)`, `release: ...`, `merged back: <production> -> <working branch>` or `merge back waits: <why>`. A merge conflict: `git merge --abort`, the worktree removed, refused, nothing pushed. The batch path (no --task) stays as C36'.
- C43 Rule text: R1 (step 9 "Merge into the target branch + cleanup"; the target rule), W8 (the deputy merges into ap-main in the main checkout, or straight into production through agent-promote.sh --task; production merged back at once), W9 (target and base, batches, (d)), merge skill and deputy, dispatch (`--target`, `--batch`, the base branch), quiz Q25 (the target question, answer B, RULE R1).

## 31. Rule text for sections 28-30 (task manager draft; replaces section 18's working-branch lines; the rules worker puts it in as written)

R1: step 9 becomes `  9. Merge into the target branch + cleanup`; after the flow list add:
```
- The target: the user's request decides. It says publish or merge to main -> the task, once its own checks pass (its blocks; no full suite), goes straight into the production branch, and the deploy follows by itself (here: the release build; a repo like v4: its own sync)
- No such words, or unclear -> the working branch ap-main (setting "Flow: Working branch"); nothing goes to production by itself
```
R8: the working-branch lines become:
```
- The working branch ap-main (setting "Flow: Working branch") is only a branch: the main checkout is switched to the working branch by init, so everything merged or pushed lands there first and never on the production branch by accident
- Batches: several tasks given together all merge into ap-main; when the last one of the batch is merged, ONE full suite runs on ap-main (`agent-nightly.sh --start`); red -> a new fixer agent, never back to the builder
- Production from ap-main: only on the owner's approval (verified words) and only from a green commit: `agent-promote.sh --owner-quote "<his words>"`; a repo with a release build runs it right after, so merged to production = published
- RELEASE RUN: the full suite runs once on ap-main before such a publish (the batch run on that commit counts)
- URGENT FIX: branch from the production branch, the smallest fix, PR REVIEW and the light related tests, the owner's yes; merge to production (`agent-promote.sh --task`; the deploy follows), then merge production back into the working branch
```
(the release-run failure lines of section 22 stay: `agent-nightly.sh --failures`, "test out of date" / "real break", no check deleted without a twin, the fixer's table).
W8, add:
```
- The merge deputy merges into ap-main in the main checkout; a task with target production goes straight in through `agent-promote.sh --task` (a short-lived worktree of the production branch, removed right after; the main checkout never switches)
- After any direct merge into production, production is merged back into ap-main at once, so they never drift
```
W9, add:
```
- Target and base (R1): a task that goes straight to production branches from the production branch; a task for ap-main branches from ap-main (it sees the batch's earlier merges): `todo add ... --target production|working --batch <name>`
- A new request may also wait until ap-main is tested and published; the main manager picks what is faster and says which
```
skills/dispatch: decide the target from the request words ("publish or merge to main" → `--target production`; else none = ap-main); `--batch <name>` for tasks given together; `orca worktree create ... --base-branch <base branch>` (the production branch for target production, else the working branch); the brief's WHERE names the target and the base.
skills/merge: target working → the merge deputy (in the main checkout, on ap-main); target production → `agent-promote.sh --task "<name>" --branch <branch> --owner-quote "<his words>"` (the main manager, after the gate); on "batch <name>: all merged" → `agent-nightly.sh --start` on ap-main, then report to the owner for the publish (`agent-promote.sh --owner-quote`); a red run → `agent-nightly.sh --failures` → a new fixer agent.
agents/merge-deputy.md: `<working branch>` in "Your brief gives"; it works in the main checkout, which is on the working branch: `git merge --no-ff origin/<branch>` there and `git push origin <working branch>` (never `git push origin main`); a task with target production is not its job (agent-promote.sh --task).
skills/init: init creates the working branch from the production branch and switches the main checkout to it (one line each).
Quiz: Q25 and Q39 as tests/test_check_rules.py.

## 32. Owner example (TELL 893f2fe6): the target is per task, not per request

- One request with x1, x2, x3, x4 where x1 and x2 are urgent ("after done direct merge"): x1 and x2 branch from the production branch, pass their own checks, merge straight into production each when it is done (not waiting for the other), and production is merged back into ap-main after each; x3 and x4 branch from ap-main and merge there; the one full suite runs on ap-main after x3 and x4 are both in.
- Before dispatch the main manager checks one thing: does an urgent task need code that only a non-urgent one brings? Yes -> it cannot ship alone: tell the owner at once (ship them together, or move that part into the urgent task), never guess.
- Rule text, W9: "- The target is per task, not per request: an urgent task branches from the production branch and merges straight into production when it is done, production merged back into ap-main after each; the others branch from ap-main and merge there; the batch's one full suite runs after the last of them" and "- Before dispatch: does an urgent task need code that only a non-urgent one brings? Yes -> it cannot ship alone: tell the owner at once (ship them together, or move that part into the urgent task), never guess". Quiz Q23 (RULE W9, answer B) per tests/test_check_rules.py QUIZ_Q23.

## 33. Owner 2026-11-25 15:4x (TELL f96c32e8): moving repos that already use the plugin

- At the first start after the upgrade the plugin only CREATES ap-main from the production branch (when it is missing). It never switches a checkout by itself: work may be half way there. It prints one line for that repo's main manager: switch the main checkout to ap-main at a quiet point (no uncommitted work, no merge running); that agent decides when. Until it has switched, merges go on as before and the start text repeats the line. A new repo (init) creates the branch and switches at once.
- Contract C44 (agent-start.sh, main manager or takeover only; never a spawned agent): working branch missing -> created from the production branch (origin/HEAD's target, else main, else the current branch); the main checkout not on it -> one line `WORKING BRANCH: switch the main checkout to <b> at a quiet point (no uncommitted work, no merge running): git switch <b>` (after a creation the line starts `WORKING BRANCH: created <b> from <prod>; switch ...`); on it -> no line; HEAD never moves.

## 34. Owner 2026-11-25 15:5x (TELL 9976949a): the working branch is PER PERSON. Replaces "ap-main" everywhere in sections 28-33 by the person's branch

- Several people in one repo would all use "ap-main" and their unapproved work would mix on origin. The working branch is per person: default name "ap-main-<name>", <name> = the person's git user name in lower case, only letters, digits and "-" (here: ap-main-maverick). The Configure item "Flow: Working branch" holds that form as its default; a fixed name stays allowed for a team that wants one shared branch.
- The name is worked out ONCE per clone and stored; every brief names the branch; a task manager or deputy on another machine never derives it again (git user names differ between machines).
- The branch is pushed to origin (other machines need it) and belongs to that person: the sweep never deletes it and nobody else merges into it.
- Other people publish to the production branch meanwhile, so the production branch is merged into the working branch at the start of a batch and again before a publish, and the full suite runs on that result.

Contract (task manager):
- C45 `agent_conf.WORKING_BRANCH_DEFAULT = "ap-main-<name>"`. `agent_conf.working_branch(repo)`: the stored value (`git config --local auto-pipeline.workingbranch` of that clone) when set; else the setting with `<name>` replaced by the git user.name lower-cased, every run of characters outside a-z 0-9 "-" made one "-", trimmed of "-" (empty -> "user"); stored at once; a fixed setting is stored as is. CLI: `python3 bin/agent_conf.py working-branch <repo>` prints it. Every script that needs the working branch uses this function.
- C46 init and the start create it (sections 29, 33) and push it to origin when origin exists (`git push -u origin <b>`; a failed push: one line, nothing else stops).
- C47 The sweep never deletes, and never lists, a branch whose name starts with the setting's prefix before `<name>` (default `ap-main-`), local or origin, nor the stored working branch.
- C48 `agent-promote.sh --sync`: in the main checkout (on the working branch; no change other than agent_*.txt): fetch, merge `origin/<production>` into the working branch when it is not in yet (`--no-edit`), push origin <working branch>; lines `sync: <production> merged into <b> (<short>)` / `sync: <b> already has <production>` / `sync waits: <why>` (a conflict: merge --abort, refused, nothing pushed). The batch-complete line (C40) becomes `batch <name>: all merged: agent-promote.sh --sync, then the full suite: agent-nightly.sh --start`. A publish (`agent-promote.sh --owner-quote`) runs the same sync first and needs a green run on that result.
- C49 Rule text: "ap-main" in R1, R8, W8, W9, the skills, the deputies and the quiz becomes "the working branch (ap-main-<name>)"; plus the lines of this section (per person, stored once, every brief names it, never derived again elsewhere, pushed, the sweep never deletes it, nobody else merges into it, production merged in at a batch start and before a publish).

## 35. Two board bugs the owner saw (TELL 74d06893): "test-slim become 1% again; when a new task is assigned it starts from 0"

- (1) Proven: the watch carries only the NEWEST STAGE/HEARTBEAT/STEP line of a remote task; test-slim wrote "HEARTBEAT step 4. ..." (no task name, no "of 7"), so its valid "STAGE test-slim: workers" line was never carried and the todo line stayed at "register" = 1 percent. Fix: take the newest VALID line of that task and skip a malformed one; and one command for the task manager that writes the heartbeat in the right form (the brief names it).
- (2) Work added to a running task changes neither the estimate nor the bar. Fix: one command for the main manager to add minutes to a running task's estimate; the bar is computed against the new estimate and never falls back to 0; the tell text reminds the manager to run it when the message adds work.

Contract (task manager):
- C50 `agent_watch.remote_command(path)`: the newest line that is a valid STAGE (`STAGE <name>: <stage>`), HEARTBEAT (`HEARTBEAT <name>: step <0-7> of 7, work <m>m, <text>`) or STEP (`STEP <0-7> `) line; a malformed one is skipped (the line before it counts).
- C51 `agent-file.sh heartbeat "<task>" <step 0-7> <work minutes> "<what runs now>"`: one state line `HEARTBEAT <task>: step <n> of 7, work <m>m, <text> | <date>`; a bad step, minutes or empty text: refused, nothing written. The dispatch brief's HEARTBEAT line names this command.
- C52 `agent-file.sh todo est "<name>" +<minutes>` adds to the estimate (guess unchanged), every other field stays; prints `todo est: <name> <old>m -> <new>m`. The board's bar follows the new estimate and never shows less than the start of the task's stage.
- C53 `agent-file.sh tell`: the line before `TELL OK ...` is `if this message adds work: agent-file.sh todo est "<task>" +<minutes>`.

## 36. Owner order 2026-11-25 15:5x (TELL 9bb87b13): the auto clear waits until the human has been quiet

- His words: "When no human interactive with you within the reent 30 minutes then you can clean ya". Cause: at 15:40 the auto clear wiped the main manager's chat while the owner was mid-discussion (his last prompt 15:34); it counted compactions only.
- The auto clear (agent-autoclear.sh, the LIMIT line of agent-start.sh) fires only when no human has typed a prompt in that pane during the last N minutes (new Configure item, default 30); until then it waits and tries again at the next idle prompt. It holds for every session a human talks to (main manager, Helper); a task manager nobody types into is cleared as today.
- A human prompt = typed by the human: not a task notification, a tell pointer, a cross-session message, the watch, or the auto clear's own prompts (agent-owner-order.sh verify already tells a typed owner prompt apart; reuse it). The quiz has no question about the clear: no quiz change. Section 34 is final (owner: "for ths one ok").

Contract (task manager):
- C54 Setting `clear_quiet_min`, Configure item "Context: Auto clear after quiet (min)", number, default 30, range 0-1440, right after housekeep_interval_min; 0 = no wait (the clear as before). 17 settings.
- C55 `agent-owner-order.sh human-quiet --session <id> --minutes <n> [--repo <folder>]` (repo default: the caller's folder): the newest human prompt of that session's transcript (`<config home>/projects/<folder name>/<id>.jsonl`; a prompt verify counts as the owner's, pasted ones too) except the auto clear's own texts (they start with "AUTO CLEAR:", "/clear", "/goal ", "CLEARED:"); now = AGENT_FAKE_NOW when set, else the clock; exit 0 and `quiet` when there is none or it is n minutes old or older (n = 0: always quiet), else exit 1 and `typed <YYYY-MM-DD HH:MM>` (local time). Read only.
- C56 agent-autoclear.sh: at step 1 (before the save prompt) and step 3 (before /clear), after the input box is empty: `human-quiet --session <session id> --minutes <clear_quiet_min> --repo <its folder>`; not quiet -> one line `AUTO CLEAR waiting: a human typed at <HH:MM>; the clear waits for <N> quiet minutes | <date>` (once per wait), pause compact_clear_check_sec, wait for the idle prompt again, check again. Not quiet at step 3 -> once quiet, back to step 1 (the save prompt again).
- C57 The LIMIT line (agent-start.sh, pane case) with N > 0: `LIMIT: compacted <n> times. Save agent_state.txt now. This pane gets a save prompt and /clear at its next idle prompt once no human has typed for <N> minutes (S8).`; N = 0: the old line.
- C58 Rule text, S8 (replaces the "Compacted 2 times" line; each line at most 200 characters):
```
- Compacted 2 times (fixed) → save state. Orca: `agent-autoclear.sh` types a save prompt, `/clear`, then `/goal` into the own pane, only at an idle prompt with an empty input box
- The auto clear fires only when no human has typed a prompt in that pane for the last N minutes (setting "Context: Auto clear after quiet (min)", default 30); until then it waits and tries again
- Not a human prompt: a task notification, a tell pointer, a cross-session message, the watch or the auto clear's own prompts. A task manager nobody types into is cleared as today
```
and "17 settings" where PRINCIPLES.md counts them.

## 37. CORE REVIEW findings (2026-11-25 16:4x, an independent read-only agent): fixes, each with a small test

- F1 agents/merge-deputy.md step 2: the deputy reads `git branch --show-current` in the main checkout first. On `<working branch>`: merge there and `git push origin <working branch>`. Still on the production branch (a repo not switched yet, section 33: "until it has switched, merges go on as before"): merge there as before and push that branch. Any other branch: FAIL, nothing merged. Rule: "push the branch the main checkout is on".
- F2 CORE REVIEW joins the builder rule (bin/agent_checks.py BUILDER_BLOCKS, R8 text): a CORE REVIEW pass by the task's own task manager, worker or deputy is refused like PR REVIEW.
- F3 No standing allow rule for a push to production: W16 and agent-init.sh say "working branch" instead of "integration branch"; init's optional allow line names `Bash(git push origin <working branch>)` with the real name, never `git push origin main`; skills/clean-up pushes the branch the main checkout is on.
- F4 `agent_conf.working_branch`: a setting value equal to the repo's production branch is never used: the default form is used instead, with one stderr line `working branch: "<value>" is the production branch; using <default>`.
- F5 W9 and W15 speak of room, not slots: W9 "dispatches what can start: room under the Max memory % limit (S3)"; W15 "when there is room for a queued task (WATCH SLOT)". The signal name WATCH SLOT stays.
- F6 R8 and skills/dispatch: "Beyond the reviewer's PR REVIEW, a second agent's opinion only for CORE REVIEW, or when someone wants a tool-triggered block removed".
- F7 skills/merge: description "send the reviewer and the check deputy" (no "run the browser E2E"; also PRINCIPLES.md); step 1 bounces a report without a click path only when FLOW CHECK or UI CHECK is planned; skills/merge and skills/dispatch: an early fix: "merge its base branch back into your branch" (the working branch, or the production branch for a direct fix), never "merge main back".
- F8 agent-board-warn.sh: reads its state first and builds the board at most once a minute (`"checked": "<minute>"` in agent_warn_seen.json); inside that minute it exits before importing the board.
- F9 human-quiet: when the folder from --repo has no `<session>.jsonl`, it looks in every project folder of every config home for that session file (a session started in a subfolder).
- F10 The name is derived only by init and the start (`working_branch(repo, derive=True)`); every other caller reads the stored value only (`working_branch(repo)` returns None when nothing is stored, stores nothing). The gate with nothing stored: base origin/<production> and one note `note: no working branch stored in this clone: give --base origin/<working branch> (the brief names it)`. agent-promote.sh and agent-nightly.sh with nothing stored: refused, `no working branch stored in this clone: run agent-init.sh or start the main manager here`. An empty git user.name: the login name (cleaned), else "user". The CLI `working-branch <repo>` derives (it is the person's own command).
- F11 bin/agent_conf.py docstring: 17 settings.
- PR REVIEW findings (2026-11-25 16:4x, the reviewer), same section:
- P1 agent_promote.py direct path: the local production ref follows the merge (fast-forward only) before the release build runs, so the release (which builds only from a commit on local production) succeeds.
- P2 The direct path refuses a task branch that carries commits of the working branch not in production: `<branch> carries commits of <working branch> that are not in <production>: branch it from <production>`, nothing pushed. The urgent deputy and the dispatch skill start the branch with `git switch -c <branch> origin/<production branch>`.
- P3 `follow_local` moves the local production ref only as a fast-forward; else one line `local <production> not moved: not a fast-forward` (never backward).
- P4 init switches the checkout only in a new repo (no agent_state.txt in its root); a repo that already uses the plugin gets the branch created and the start's `WORKING BRANCH: ... at a quiet point ...` line (section 33).
- P5 `agent-init.sh --no-branch`: no working-branch step. The start's first-run setup runs `agent-init.sh" --no-measure --no-branch` (the start creates the branch itself, C44); agent-cloud-pack.sh passes --no-branch.
- P6 Each promote uses its own short-lived worktree (`<git common dir>/agent_promote_wt_<pid>`) and removes only that one.
- P7 The sweep counts a branch as merged when it is in origin/<production> or origin/<working branch> (the stored one); its advice: "merge it into the working branch, or remove it by hand".
- P8 A failed push of the working branch: `working branch: not pushed: <git's first line>` (init and the start); a failed creation: `working branch: not created: <git's first line>`. The lost twin of test_this_repo_has_its_file comes back (agent_repo.conf tracked, its core paths pinned).

## 38. Owner order 16:4x (TELL 10b4d922, "1. ok", option A): what happens after DONE FAIL and LOST

- DONE FAIL -> the main manager reviews the report, then sends the task manager a fix order in the fixed shape (where, what is seen, what is expected, evidence); never merged, never closed silently.
- LOST (the watch cannot reach a machine or a pane) -> wait one more sweep; still lost -> tell the owner in one line with the machine and the task; never redispatch the task on another machine by itself.
- Rule text, W15, right after the line that lists the signals that wake the main manager (each at most 200 characters):
```
- DONE FAIL → the main manager reviews the report, then sends the task manager a fix order (where, what is seen, what is expected, evidence). Never merged, never closed silently
- LOST (the watch cannot reach a machine or a pane) → wait one more sweep; still lost → tell the owner in one line with the machine and the task
- Never redispatch a LOST task on another machine by itself
```

## 39. Leftovers the main manager found reading PRINCIPLES.md as a newcomer (TELL d2d93d25)

- (a) "slot" against "No count caps" (S6): W9 and W15 as section 37 F5; W11 "suite slot" becomes "suite run". The signal name WATCH SLOT stays (a name).
- (b) R5 (the housekeep flag) and W8 (the sweep's safe items) say "merged into the working branch or the production branch", not "merged into origin/main"; the code does the same: agent_housekeep.py flags a todo line whose branch is merged into origin/<stored working branch> too (`flag: todo <name>: merged into origin/<working branch> (branch <b>)`, the production form unchanged); agent-cleanup.sh's help text says the same as the sweep (section 37 P7).
- (c) Old names: the F Map's merge skill line "(the reviewer and the check deputy, then the merge deputy)", no "E2E"; W14's main manager stages "e2e (the review and the checks), merge" (the stage word e2e stays in the code as the name of that stage); W16 as section 37 F3.
- (d) W6: every agent file is named by its plugin path `agents/<name>.md` (merge deputy and worker said `.claude/agents/`).

## 40. Facts from a slim-pass trial on PRINCIPLES.md (TELL e2fd5575), each checked against the code

- (1) W6 and the F tree name the main manager's and task manager's model by the setting ("Main manager model", "Task manager model"; default opus-5.5:high), not "(Opus 5.5, xhigh)".
- (2) R8: `agent-nightly.sh --start` runs the full suite in the background; `agent-nightly.sh --release-ok` only checks that a green run covers the commit.
- (3) `bin/agent-file.sh`, never `./agent-file.sh` (R5, W8).
- (4) R5's todo field list names guess and level too (agent-file.sh writes them).
- (5) The F Map's script list names agent-promote, agent-runtime, agent-resources, agent-autoclear, agent-release, agent-statusline, agent-roots.

## 41. CORE REVIEW, second pass (17:5x): F1-F11 confirmed, five more findings, all accepted

- G1 The sweep never removes or lists the production branch (production_branch in agent_repo.conf, else origin/HEAD's target, else main), "release", nor any working branch (bin/agent_cleanup.py PROTECTED becomes these, worked out per repo). Since production is merged back into the working branch at once, it would otherwise count as merged (section 37 P7).
- G2 `agent-init.sh --no-branch` stores nothing: its optional allow line reads the stored name only (`python3 bin/agent_conf.py stored-working-branch <repo>`: prints the stored name or nothing, stores nothing); nothing stored -> `<your working branch>`.
- G3 The merge deputy's brief gives `<production branch>` (the merge skill fills it from agent_repo.conf, else origin/HEAD's target, else main); step 2 compares `git branch --show-current` with `<working branch>` and `<production branch>` exactly; any other branch (release, master ...): FAIL, nothing merged.
- G4 A stored name equal to the production branch is never returned: `working_branch(repo)` gives None with the F4 stderr line; `derive=True` works out the default form again and stores it.
- G5 skills/dispatch step 9: "a fix from a still-running branch merged into its target branch", no "merged into main".
- PR REVIEW delta (17:5x): pass, all 8 fixed; four low items, accepted:
- G6 agent_promote.py: when the local production branch is checked out (a repo not switched yet, section 33) the release cannot build from it: the release step is not run and says `release: not run: local <production> is checked out in <path>; switch that checkout to the working branch (section 33), then run bin/agent-release.sh --push`; exit 1.
- G7 agent_cleanup.py: "no own commits" also when the head is on origin/<working branch>'s first-parent line (a worktree just branched from the working branch is never swept as merged); task_finished likewise.
- G8 agent_nightly.py: each scratch worktree of `--failures` and of record_misses has its own name (`..._<pid>`) and removes only its own.
- G9 PRINCIPLES.md R8: "init switches the main checkout of a new repo to the working branch; in a repo that already uses the plugin the main manager switches it at a quiet point after the start's WORKING BRANCH line".
- G10 skills/dispatch: the brief's list of waits says "suite run", not "suite slot" (section 39 a).
- G11 (CORE REVIEW third pass, low): the sweep always protects the default prefix "ap-main-" too, whatever this clone's setting (a fixed team name must not expose other people's default-named branches).

## 42. FIX ORDER 1 from the main manager (TELL 6bf8830d, an independent review of the rule text at 1167369): where | seen | expected

Blockers:
- B1 skills/dispatch step 4: no "max 2 at once"; workers run "as many at once as the memory rule admits (S3)".
- B2 No test run at the merge: skills/merge drops the `suite command:` field; agents/merge-deputy.md drops `<suite command>` and step 3 says "No test run at the merge (W4: never re-run what passed; R8: no task runs the full suite)".
- B3 skills/merge step 1 bounces only "a block the builder owns with no pass line"; PR REVIEW, CORE REVIEW, FLOW CHECK and UI CHECK are checked by the gate after the reviewer and the check deputy ran.
- B4 agents/fast-lane-deputy.md: its report ends with the TIME line and the FACTS line (the same two lines as the dispatch brief's REPORT).
- B5 `todo done` once, by the merge deputy, with the task's real lane: skills/dispatch step 2 no longer runs `todo done` after the merge; skills/merge's todo done arguments say `--lane <full|fast>` (the task's lane), never a fixed `--lane full`.
Should fix:
- S1 skills/merge, target production: after `agent-promote.sh --task` a merge deputy does the cleanup and `todo done` with `merged: <merge hash>` in its brief; agents/merge-deputy.md: with `merged: <merge hash>` it skips steps 1-4 and does the rest (branch, cleanup, worktree line, todo done --merge <merge hash>).
- S2 agents/check-deputy.md RELEASE SMOKE: the main manager does the one subagent launch and gives the check deputy its result; the check deputy starts no agents.
- S3 agents/check-deputy.md tools add `mcp__claude-in-chrome__resize_window` (UI CHECK at desktop and phone width).
- S4 skills/merge headless: the check deputy runs the same click path with Playwright, not the main manager.
- S5 skills/dispatch: at the start of a batch `agent-promote.sh --sync` before its first task is dispatched (R8).
- S6 R8: "A repo whose working branch exists but whose main checkout is not switched yet: merges go into the production branch as before (section 33)".
- S7 No slot, no level: R5's data block names "level (old tasks only, - for new ones)"; the watch signal WATCH SLOT becomes WATCH ROOM (bin/agent_watch.py, W15); skills/dispatch "Waiting for room or another task -> on queue --after <task>; room found -> off"; bin/agent-file.sh comments: `next` -> "NEXT: <n> can start (room <mb> MB under the <p>% limit)", waits "suite run".
- S8 W6 and the F tree: the fast-lane deputy, merge deputy, check deputy and worker run on the "Helper model" setting (no "Sonnet 5, medium"); the setting's description names the check deputy too (bin/agent_conf.py, plugin.json).
- S9 R8: agent_repo.conf is "written by init and kept by agents; a human may edit it, never has to" (the same words as skills/init and the file's header).
- S10 skills/dispatch step 7: "set status final (R7)", never "status done".
- S11 S1: "New terminals use the "Permissions: Permission mode" setting, default bypassPermissions".
Decided by the main manager (listed for the owner):
- D1 R1 step 2: "2. Mock for a new page or a whole-page re-layout (W2)"; the dispatch brief follows.
- D2 W8: "Delete the branch and close the todo line only after the merge is verified"; "the pane and the worktree may go while waiting for the owner's yes; the pushed branch stays".
- D3 E1: "Lead with the result"; "A command, path or snippet the human must use comes right after the result"; "End with one concrete next action" stays; no "Lead with the next action".
- D4 W1: "Never wait for the human, except: the kick-off round, a mock yes, an OWNER SIGN, NEEDS HUMAN E2E".

## 43. FIX ORDER 2 from the main manager (TELL d6040ada, review of memory, sessions, cleanup and tests at 1167369)

- C1 A reservation entry stores `start` (the process start time, `ps -o lstart= -p <pid>`) and `by`: "runner" for agent-test-run.sh and the nightly, "hand" for `agent-room.sh reserve`. relief signals only an entry that is by "runner", of this repo (`repo` = this repo's name) and whose pid still has the stored start time; an entry whose pid is alive with another start time is pruned (dropped from the list), never signalled. A working agent, the human's apps and other repos' processes are never stopped.
- C2 The nightly (and the batch full run, the same `run`) goes through run_monitored like a test run: it reserves its known weight (key "nightly"), is monitored, and records its peak under "nightly" in agent_test_weights.json.
- C3 The automatic start (agent-start.sh, the housekeep pass) starts a due nightly here only when this machine has room for its weight; else one line `NIGHTLY: due, no room on <host>: start it where there is room (W7): agent-nightly.sh --start` and nothing starts. The main manager places a nightly by hand like any heavy job (W7: a connected machine with the most room first).
- C4 SIGINT, SIGTERM and SIGHUP in agent-test-run.sh and in the nightly's run stop the child process group, remove the scratch tree (nightly) and drop the reservation, then exit 128+signal; the status file of a stopped nightly says `"result": "stopped"`.
- C5 --failures: at a merge where the test file does not exist yet the run is "not there" (skipped, never a failure); a test id whose file cannot be found stays `unknown` (the merge column `unknown`, never the newest merge as a guess); every rerun waits for room with the related weight and holds a reservation; at most 20 merges are rerun, then `unknown`.
- C6 Room counts a running reserved job once: for each live reserved job its current tree memory is taken out of "in use" and its reserved MB counted instead (`agent-room.sh check` and `numbers` alike).
- C7 A new pane is reserved from its launch until it measures itself: `agent-room.sh reserve-pane <handle> <mb>` (an entry with `handle`, kind pane, by "launch", dropped by `measure-pane` of the pane whose ORCA_TERMINAL_HANDLE is that handle, or after 15 minutes); agent-resume.sh reserves each pane it launches; skills/dispatch step "launch" reserves before `orca terminal create`.
- C8 agent-autoclear.sh: the human-quiet gate runs first, then `ready` (idle prompt, empty box) right before each typed text.
- C9 human-quiet: a missing or unreadable transcript, or an unknown session id: exit 2 and `unknown: <why>`. The waiter of a session a human talks to (no `--spawned`) waits on unknown and says once `AUTO CLEAR waiting: the transcript of this session cannot be read`; agent-start.sh passes `--spawned` for a spawned task manager, which is cleared as today. clear_quiet_min 0: no gate at all.
- C10 A reservation file that is not valid JSON is moved aside to `<file>.corrupt-<YYYYmmdd-HHMMSS>` with one line `RESERVATIONS: <file> could not be read; moved to <path>`, never overwritten silently; a signal handler never takes a second blocking lock (a non-blocking try, else the stale entry is pruned later by C1).
- C11 One lock around a full run (`<git common dir>/agent_nightly.lock`, non-blocking): a second start while one runs says `NIGHTLY: already running` and touches no scratch tree.
- C12 A test for "memory unknown -> no relaunch" in agent-resume.sh.

## 44. FIX ORDER 3 from the main manager (TELL 7a7407c8, review of the flow code at 1167369, each reproduced)

- F1 The direct path is bound to the task. `todo add ... --target production` needs `--owner-quote "<words>" [--time <t>]`: verified at once (agent-owner-order.sh verify); not verified -> refused, nothing written; verified -> the todo line gets ` | target production` and `<git common dir>/agent_owner_words.json` keeps `{"<task>": {"quote", "time", "verified"}}`. `agent-promote.sh --task <task> --branch <b>` takes no --owner-quote (`the owner's words come from the task (todo add --target production --owner-quote), not from promote`); it refuses `<task> is not a production task (todo add --target production)` when the todo line lacks the target, `no owner words stored for <task>` when none are stored, and runs `agent-file.sh checks gate <task> --dir <a detached scratch worktree of origin/<b>> --base origin/<production> --branch <b>` first: GATE REFUSED -> refused with the gate's lines, nothing pushed. No full suite here (R1).
- F2 The guard appends a durable record to `<git common dir>/agent_launches.jsonl` for every Agent launch of subagent type reviewer or check-deputy (any plugin prefix): `{"task", "type": "reviewer"|"check-deputy", "by": <role>, "at": "<YYYY-MM-DD HH:MM>"}`. The gate accepts PR REVIEW only with a reviewer record by the main manager (`by` main) for that task, FLOW CHECK and UI CHECK only with a check-deputy record by the main manager, and only a pass dated at or after that record: else `<BLOCK>: no <reviewer|check deputy> launched by the main manager for <task>, not accepted`. agent-file.sh reads AGENT_FAKE_NOW only when AGENT_TESTING=1 (the tests set it).
- F3 A check line records the commit it saw: `CHECK <task> <BLOCK>: <result> | by <who> | at <sha12> | <evidence> | <date>` (`at` = HEAD of the folder it runs in, or `--commit <sha>`). The gate accepts PR REVIEW, FLOW CHECK and UI CHECK only at the head being merged, or at a commit after which every commit is a merge whose other parent is in origin/<base>: else `<BLOCK>: pass at <c>, not at the head <h>, not accepted`. `checks gate ... --branch <b>`: --dir's HEAD must be origin/<b>, else `GATE REFUSED <task>: --dir is not on origin/<b>`. Lines dated before the todo line's `opened` date are ignored. The merge skill and the merge deputy pass --branch.
- F4 "Already uses the plugin" = agent_repo.conf or agent_todo.txt is tracked at HEAD (git ls-files), never a local file: init does not switch such a repo (a fresh clone included) and prints the start's WORKING BRANCH line.
- F5 Two lines of one block at the same minute: fail wins.
- F6 The local working branch missing while origin/<working branch> exists: it is created tracking origin/<working branch> (`working branch: tracking origin/<b>`), never from production. A refused push says why in words: `working branch: not pushed: the remote has commits this clone does not have (fetch and merge origin/<b> first)` for a rejected push, else git's `error:` or `fatal:` line.
- F7 agent_promote.py reads `git status --porcelain -z` exactly; agent_*.txt changes never block sync, publish or the merge back.
- F8 publish pushes the sha that release_ok checked, never a re-read ref.
- F9 publish runs the release build in a short-lived worktree at the published commit, never the main checkout's HEAD; local production checked out -> the G6 line, release not run, exit 1.
- F10 A changed string literal in a code file is code (SQL, a role name, a URL); "text" is docs, comments, locale and translation files.
- F11 Blocks are only added, also across `todo drop` and `todo add`: `<git common dir>/agent_task_blocks.json` keeps per task the brief blocks ever planned and the verified removals; `todo add` of a name with a record plans its blocks again; the gate plans the tool blocks plus these minus the verified removals.
- F12 sync and the merge back abort only a merge this run started; a merge already in progress: `sync waits: a merge is in progress in <path> (not started by this run)`.
- F13 One function `agent_conf.production_branch(repo)`: production_branch in agent_repo.conf, else origin/HEAD's target, else main when refs/heads/main or origin/main exists, else master when it exists, else the current branch; promote, the gate, init, the start, the sweep and the nightly use it.
- F14 Every promote first removes leftover `<git common dir>/agent_promote_wt_<pid>` worktrees whose pid is dead.
- tests/check_blocks_demo.sh shows F1-F4 and F7.
- B2 (also): W8 drops the undo line of a failed run after the merge (no run there); it keeps: "Never `git reset --hard` in the main checkout: it wipes the uncommitted agent_*.txt".
- C8 (also): the waiter calls the gate through `bin/agent-owner-order.sh human-quiet` (its documented entry), not the Python file.
- F3 (also): a PR REVIEW, FLOW CHECK or UI CHECK line without `at` (an old line, or one appended by hand) is not accepted: `<BLOCK>: pass with no commit, not accepted`. "Before the task opened" compares days (the worker's reading, kept).
- F10 (as applied): code files only (not markup such as .html .jsx .tsx .vue, not config such as .yml .json): a changed quoted string is code, except a docstring and a comment line; markup text and config values keep their rules.

## 45. FIX ORDER 4 from the main manager (TELL fe33c244, bounce 2: second pass of the review of the rule text at 6be98d2)

- A1 (blocker) A check line records the commit it saw; the reviewer and the check deputy are subagents whose shell starts in the main checkout, so they always pass `--commit <the head they looked at>`: agents/reviewer.md and agents/check-deputy.md write `agent-file.sh check "<name>" "<BLOCK>" pass|fail --by ... --commit <head> --evidence ...`; skills/merge gives that head in their brief (`head: <sha>`, read with `git -C <worktree path> rev-parse HEAD`, or `git rev-parse origin/<branch>` for another machine); PRINCIPLES.md R8 says so. The gate's refusal names both commits (`pass at <c>, not at the head <h>`).
- A2 skills/dispatch's fast-lane brief names `target:`, `base:` (origin/<production branch> for target production, else origin/<working branch>), `working branch:` and `production branch:`; agents/fast-lane-deputy.md takes them from the brief (never derives a name) and starts its branch from `base:`.
- A3 agents/fast-lane-deputy.md: the report carries the click path when FLOW CHECK or UI CHECK is planned.
- A4 skills/dispatch: `orca terminal create` first, then `agent-room.sh reserve-pane <the new handle> <mb>` (as agent-resume.sh does).
- A5 bin/agent-promote.sh usage: `--task "<task>" --branch <branch>` takes no --owner-quote (the words stored at todo add --target production).
- A6 agents/merge-deputy.md: one meaning: a production task is merged by `agent-promote.sh --task` (not by you); with `merged: <merge hash>` you do its cleanup and todo done.
- A7 skills/dispatch's list of watch signals names WATCH ROOM.
- A8 PRINCIPLES.md F tree: "Reviewer (Reviewer model setting)"; skills/merge: the reviewer's Agent call passes the model and the effort of the Reviewer model setting (agents/reviewer.md holds only `model: opus`).
- A9 (decided by the main manager) No second yes after an urgent fix: the owner's verified words at dispatch that name the publish are his final yes (W12, P1). R8 URGENT FIX, skills/dispatch and skills/merge say so and drop "the owner's yes" after the fix.
- Walks: tests/check_blocks_demo.sh walks (1) a small task from dispatch to todo done on the working branch and (2) a task with target production, with only the commands of the skill and agent texts, each gate passed by check lines written from another checkout with --commit.
- W-1 (found by the walk) The direct path's gate must see the task's lines: before its gate, `agent-promote.sh --task` gathers the task's CHECK lines from its worktree (the agent_worktree.txt line of that task; `checks gather`) into the main repo, and takes `--results <file>` for a task on another machine and passes it to the gate. skills/merge's production path passes `--results <file>` for a remote task.

## 46. FIX ORDER 5 from the main manager (TELL ed67796b, second pass of the review of memory and sessions at 6be98d2)

- C13 (blocker) No text is typed more than a moment after a passing human-quiet check and an empty-box check: before the save prompt, before /clear and before /goal the waiter runs the gate, then ready; when ready took 2 seconds or more (it waited), the gate and ready run again, until ready returns at once; then the text is typed. A human prompt during the save turn: no /clear.
- C14 The process start time does not depend on locale or TZ (`ps -o lstart=` run with LC_ALL=C and TZ=UTC); an empty answer is unknown: never pruned, never signalled.
- C15 A reservation's `repo` is the main root path (the parent of the git common dir); relief compares that path: a run started in a task worktree of this repo is this repo's; another repo with the same folder name is not.
- C16 pick_of takes only entries that can be stopped (by runner).
- C17 `agent-room.sh reserve-pane <handle> <mb>` checks room and reserves in one locked step (no room: exit 1 with the ROOM: no line, nothing reserved); skills/dispatch and agent-resume.sh call it after the create; agent-start.sh measures the pane of every session that has a pane handle, a task manager's too (its reservation is dropped then).
- C18 The automatic nightly (agent-start.sh, the housekeep pass) never runs the full suite locally by itself while a connected machine exists (`orca environment list --json` names one): it prints `NIGHTLY: due: a connected machine runs it (W7): agent-nightly.sh --start there` and the main manager places it; with no connected machine it starts locally when there is room (C3).
- C19 --failures has the same stop handling as the full run (signals stop the child group and remove its scratch tree); a stopped run leaves no agent_nightly_wt_failures_<pid>.
- C20 A stopped nightly is not done: `--due` treats "stopped" like no run today.
- C21 Tests: one whole waiter run of a human's pane (no --spawned) with a quiet transcript; behaviour tests for the pane reservation (resume reserves the launched handle; a task manager's start measures and drops it).

## 47. FIX ORDER 6 from the main manager (TELL 34525d7d, second pass of the review of the flow code at 6be98d2)

- Threat model: the gate guards against mistakes and shortcuts made through the documented commands; it does not claim to stop an agent that forges files by hand (a CHECK line, agent_launches.jsonl, a test switch): a forgery is a breach the main manager reports to the owner, not a case the code must win. Must hold: no documented command lets a task pass without its checks. (Also one line in R8.)
- G1 (decided by the main manager) PR REVIEW and OWNER SIGN are never removable. Any other block is removable only when the verified words name it: the quote holds a word of that block and a word of leaving it out. Both word lists in bin/agent_conf.py (BLOCK_WORDS per block: review, flow, ui, build, tests, data, db, core, scan, examples, count, ...; SKIP_WORDS: skip, without, no need, remove, leave out, 不用, 跳过, ...). Refusals: `todo checks: <BLOCK> is never removed`, `todo checks: the owner's words do not name <BLOCK> and leaving it out`.
- G2 A task's plan and its removals belong to one task instance: cleared at todo done and todo drop (a new todo add of the same name starts clean).
- G3 A merge after the reviewed commit counts only when it is a clean merge: its tree equals `git merge-tree --write-tree <parent 1> <parent 2>`; anything else needs the review at the new head.
- G4 The words of `todo add --target production` must hold a publish word (PUBLISH_WORDS in bin/agent_conf.py: publish, production, merge to main, release, deploy, live, 上线, 发布, ...): else refused `todo add: the owner's words do not name the publish`; stored per task instance (cleared at todo done and todo drop); one sentence may serve several tasks of the same request.
- G5 `check --commit <sha>` must name a commit of this repo; the gate accepts a line's commit only when it is the head being merged or an ancestor of it (with G3); agents/reviewer.md and agents/check-deputy.md: the commit you pass is the one you read.
- G6 The fake clock (AGENT_FAKE_NOW) works only with AGENT_TESTING=1 and a repo root under the system temp folder; the gate ignores a line dated more than one minute in the future.
- G7 In .tsx .jsx .vue .svelte a changed literal inside an expression (a comparison, a call argument, an assignment) is code; text shown between tags stays text. In .yml .yaml .json .toml a changed value is code unless the file is a locale or translation file (a path part locales, locale, i18n, translations, lang, or a file named like en.json, zh-CN.json).
- G8 The gate takes a PR REVIEW, FLOW CHECK or UI CHECK pass only when its `by` is not the builder (the todo line's builder, the builder's LAUNCH records) and a main-manager launch of the matching type exists for this task instance (dated at or after the todo line's opened time).
- tests/check_blocks_demo.sh shows G1-G4.
- G2 (as applied, with F11): verified removals end at todo done and todo drop; the brief blocks ever planned end only at todo done, so a drop and a new add of the same name keeps them (F11) but loses its removals.

## 48. FIX ORDER 7 from the main manager (TELL a677e9c8, bounce 3: third pass of the review of memory and sessions at e7cb397)

- C22 (blocker) The repeat (gate, ready, and again when ready waited) runs for every pane: the owner types into task manager and Helper panes too. `--spawned` changes only the unreadable-transcript branch (a spawned pane is cleared as before on exit 2). A human prompt in a task manager pane during the save turn: no /clear.
- C23 One shared function `agent_nightly.machines(cwd)` (CLI `agent-nightly.sh --machines`) used by agent-start.sh and the housekeep pass: paired = `orca environment list --json` -> `result.environments` (by name); reachable = a probe of each paired machine with our own time limit (`orca terminal list --environment <name> --json` run from Python with a 10 s timeout; exit 0 and ok -> reachable). A reachable paired machine -> the automatic nightly never runs locally (the NIGHTLY: due line). Paired but none reachable -> the local room rule, with one line `NIGHTLY: the paired machine <names> did not answer; it runs here when there is room`. The test fixture copies the real answer shape (id, ok, result.environments[{id, name, endpoints, ...}], _meta).
- C24 A pane is counted once: the room check and the reservation happen before the create (`agent-room.sh reserve-pane --pending <key> <mb>`: check and reserve in one step), then the reservation takes the new handle (`agent-room.sh reserve-pane --name <key> <handle>`, no check); a failed create releases it (`agent-room.sh release-pane <key>`). No check after the create, so a pane just made is never closed for room. agent-resume.sh and skills/dispatch follow this order.
- C25 A pane's reservation lives on the machine the pane runs on: a pane on another machine is not reserved in the local list (resume and dispatch reserve only a local pane; the remote pane reserves itself there at its start).
- C26 A pane measures itself once, at its first start (SessionStart source "startup"), never at resume or compact; the stored pane weight is the highest of the last 5 measurements (`pane_recent` in agent_test_weights.json), not the highest ever.
- C27 An entry whose start time is unknown or empty expires after 6 hours (it cannot be verified).

## 49. FIX ORDER 8 from the main manager (TELL ff975386, bounce 3: third pass of the review of the rule text at e7cb397, done as flow walks)

- A10 (blocker) One way for every task, fast-lane included: `checks gate <task> --dir <d>` copies the task's CHECK lines it read from <d> into the main repo's agent_state.txt (as `checks gather` does, lines already there skipped), so promote's gate finds them there. A third walk in tests/check_blocks_demo.sh: an urgent small production task done by a fast-lane deputy in an Agent worktree (no agent_worktree.txt line).
- A11 agents/reviewer.md: read `git diff <base>...<head>` after `git fetch`, from any checkout (no worktree needed); agents/check-deputy.md: its brief says where the app runs (a scratch copy of the head here, or the machine and how to reach it).
- A12 skills/merge's `session:` field has three values: task manager | helper | fast-lane (a subagent's git worktree, no pane); agents/merge-deputy.md has a case for each.
- A13 Quiz Q39 option B follows A9: "... merge to production with his verified words from dispatch (no second yes) ...".
- A14 skills/merge maps the Reviewer model setting like dispatch: `agent_conf.py cli-model` gives the Agent call's model, and the effort goes into its own field.
- A15 skills/dispatch step 2's template: `[--target production --owner-quote "<the owner's words>"]`.
- A16 BUILDER_BLOCKS has no DIFF READ.
- A17 agents/merge-deputy.md: for a production task the deputy checks the merge against the production branch (`git merge-base --is-ancestor origin/<branch> origin/<production branch>`), then deletes the branch with -D.
- A18 skills/merge step 4: a remote task is gated on a scratch copy (`git worktree add --detach <scratch> origin/<branch>`, removed after); its reservation on the other machine goes by itself when its process ends (a dead pid is pruned), no release command.

## 50. FIX ORDER 9 from the main manager (TELL ba09a48b, bounce 3: third pass of the review of the flow code at e7cb397, documented commands only)

- G9 (blocker) A pass belongs to one task instance: a line dated before the todo line's opened time (to the minute) is ignored; and EVERY pass line (tool blocks and OWNER SIGN too) counts only when its commit is the head being merged or one of this branch's own commits (base..head); a line without a commit is not accepted. (Replaces the day comparison of section 44 F3.)
- G10 (blocker) Safe side for the words of `todo add --target production`: a publish word AND no word of refusal or delay anywhere (NEGATION_WORDS in agent_conf: not, don't, do not, never, no, wait, later, yet, after, before, without, hold, 不, 别, 先, 等, 暂, ...). Refused: `todo add: the owner's words do not clearly say publish now: ask him one plain question and quote his answer`.
- G11 A removal: the skip word stands right before the block's own name (at most 3 words between: "skip the build check", "without the related tests", "不用 build"); one removal per command; else refused with the same "ask him one plain question and quote his answer" line.
- G12 A locale file is one inside a locale, locales, i18n, lang or translations folder, or whose stem is a real language code from a fixed list (en, de, fr, es, it, pt, nl, sv, da, no, fi, pl, cs, ru, uk, tr, ar, he, hi, th, vi, id, ms, ja, ko, zh, with an optional region: en-US, zh-CN, pt_BR); config/db.json is code.
- G13 tests/check_blocks_demo.sh: the walks use the real verify against a made transcript (a config home with the owner's typed words), the commands exactly as agents/merge-deputy.md gives them, and once the owner's real state (the main checkout still on production, agent_todo.txt, agent_ideas.txt and agent_completed.txt modified, an upgraded repo).
- G14 agents/merge-deputy.md: before any `worktree remove --force` or `branch -D` of a subagent's git worktree the deputy checks it is clean (agent_*.txt aside) and its commits are in the merged target (`git -C <wt> log --oneline origin/<target>..HEAD` empty); else it stops and reports.
- G15 A merge after the review that is not clean is refused with `<BLOCK>: the merge after the review changed code (<commit>): review the new head`; promote's gather prints one line for each worktree it skipped (`gather: skipped <path>: missing` or `: on another machine`).
- For the owner tomorrow, not built now: approvals bound to a numbered question he answered ("1A") instead of word lists.

## 51. FIX ORDER 10 from the main manager (TELL 11cc1b2b, bounce 4, meant as the last): two reviews pass; the flow-code review fails on two points

- H1 (blocker) OWNER SIGN, DB CHECK and DATA CHECK need the head being merged (or a clean base merge after it), like PR REVIEW. The documented OWNER SIGN command (skills/dispatch) passes `--commit <head>`, and /merge gives that head.
- H2 (blocker; the main manager's design error) The word lists go: PUBLISH_WORDS, NEGATION_WORDS, BLOCK_WORDS, SKIP_WORDS and skip_before_name are removed. INTERIM RULE (the main manager's decision; the owner picks the final design tomorrow): an approval is one exact sentence the tool itself names, typed by the owner and verified as his typed prompt: for a production task `yes, publish <task> to production`; for leaving out a block `yes, skip <BLOCK> for <task>` (PR REVIEW and OWNER SIGN stay never removable). Compared after lower-casing and dropping punctuation and extra spaces. Anything else is refused with one line that prints the exact sentence to ask him for: `todo add: ask the owner to type exactly: yes, publish <task> to production` / `todo checks: ask the owner to type exactly: yes, skip <BLOCK> for <task>`. skills/dispatch: his request says publish -> the main manager shows him that one sentence to type and stores it with the task (`todo add --target production --owner-quote "yes, publish <task> to production"`); no second yes later (A9 stays). Quiz Q23 and Q39 agree.
- H3 skills/merge and R8: the fixer of a red batch run is a normal task: todo add first (the guard needs it), a brief with target, base and both branches, its own PR REVIEW and gate; then the main manager starts the run again (`agent-nightly.sh --start`).
- H4 skills/merge: the check deputy's brief carries `where the app runs:`.
- H5 agents/merge-deputy.md: before `git branch -D` of a production task the LOCAL branch is checked: `git merge-base --is-ancestor <branch> origin/<production branch>`.
- H6 agent-autoclear.sh: the repeat (gate, ready) has a cap of 3 rounds; then one line `AUTO CLEAR waiting: the pane did not settle in 3 rounds; trying again later` and it waits its normal interval before it tries again.
- H7 measure-pane: the stored pane weight is never below 550 MB.
- H8 `reserve-pane --pending <key>` refuses a key that exists (exit 1, one line); skills/dispatch names the key: the task name.
- H9 agent-room.sh's usage names reserve-pane --pending, --name and release-pane.

## 52. Approval design, open for the owner (he picks tomorrow)

- A: an answer bound to a numbered question the main manager asked ("1A").
- B: one exact sentence the tool names, typed by the owner and verified (the interim rule of section 51 H2, built now).
- C: the main manager reads his verified words and decides (no word lists).

## 53. Approval design: the owner picked C (2026-11-26, TELL 3c316bc4)

Owner 2026-11-26: "Normally when i give you alot of task, normally it have number order, then i will say 2. need to publish direct after done. others wait for me review. Or sometimes i did not say the number order, then i will mention the task description, then agent will decide which one is the one i am asking for. if can self confirm then no need ask user again. but if got 2 similiar, which faced the issues that you cannot decide is which one, then you need to follow the princicple, check/ask only decide. Actualy no need to stick with the fixed sentences, because nowsaday agent is very smart, they can self decide on it. what you need to wirte in princicple is to let them know have this cases will do. then for the quiz need to update ya, hooks actually can very effetively helps the agent works."

Replaces the interim rule of section 51 H2 and the open choice of section 52.

A. One approval rule (a task published straight to production; a block left out; the working branch published; OWNER SIGN)
- A1. The deciding agent reads his words. No fixed sentence, no word list: `publish_sentence`, `skip_sentence`, `says`, `approval_key` go from bin/agent_conf.py, and no refusal prints a sentence to ask him for.
- A2. The tool only (1) verifies the quote is a prompt he typed (`agent-owner-order.sh verify`) and (2) stores the quote with what the main manager read from it.
- A3. Every place that takes `--owner-quote "<his words>"` also needs `--means "<the action, e.g. publish task x to production>"` and takes `--question "<the question it answered>"` and `--time <t>`: `todo add --target production`, `todo checks <task> --remove <BLOCK>`, `check <task> "OWNER SIGN" pass`, `agent-promote.sh --owner-quote` (the working branch publish). A missing `--means` is refused (the refusal names `--means`); `--means` or `--question` without `--owner-quote` is refused; a value with a line break or " | " is refused. Nothing is written on a refusal.
- A4. A quote under 20 characters (width, `owner_order_min_chars`; "1A", "ok") is verified only when it equals a WHOLE typed owner prompt (after the usual whitespace normalising) and only with `--question`; without `--question` verify refuses with a line that names `--question`. A quote of 20 or more is matched inside a prompt as before; `--question` is optional there and stored when given.
- A5. verify prints `OWNER ORDER verified <file> <YYYY-MM-DD HH:MM>`, `match: "<snippet>"`, and with `--question` a third line `question: "<question>"`. The record keeps the typed minute (`typed`) from that first line.
- A6. Stored per task instance in `agent_owner_words.json` (git common dir): `{task: {"publish": rec, "skip": {BLOCK: rec}}}`, rec = `{"quote", "means", "question" (when given), "typed", "time", "verified": true}`. An old flat record (no `means`) is not a publish record: promote --task refuses it. `todo done` and `todo drop` remove the task's entry (as today).
- A7. OWNER SIGN: the CHECK line evidence is `owner order verified: <quote> | means: <means>[ | question: <question>] | typed: <YYYY-MM-DD HH:MM>`. The gate believes it only when verify accepts the quote again with that typed minute (and the question); an OWNER SIGN line without `means:` is not accepted.
- A8. The stored pair is printed, so he always sees which words were taken as his yes: `checks gate <task>` prints one line per stored approval of the task before its GATE line, `OWNER WORDS publish: "<quote>" (typed <minute>) read as: <means>`, `OWNER WORDS skip <BLOCK>: ...`, `OWNER WORDS OWNER SIGN: ...`, each with ` | question: "<question>"` when there is one. `agent-promote.sh --task` prints its `OWNER WORDS publish:` line; `agent-promote.sh --owner-quote` prints `OWNER WORDS publish <working branch>: "<quote>" (typed <minute>) read as: <means>`. The report to the owner repeats these lines (skills/merge).
- A9. PR REVIEW and OWNER SIGN stay never removable. A relayed owner order (W12) is verified in the sender's repo transcript; `line --quote "<q>" --question "<question>"` prints the question line and a check line with `--question`, so a short answer can be relayed verified. The threat model line stays.

B. The cases (PRINCIPLES.md R8, once; R1, W9, W12 and skills/dispatch agree)
- B1. A numbered batch, "2. publish direct after done, others wait for my review": task 2 gets target production with his words; the others go to the working branch and wait for his review.
- B2. No numbers, he names a task by its description: the main manager maps it to the task; exactly one fits -> no question.
- B3. Two similar tasks fit and it cannot tell which: check first (todo lines, requirement docs, what he said before); still unsure -> ONE question that names both, then decide (P1).
- B4. Words that are not a yes now: a question ("is it ready to publish?"), a later time ("publish next week"), a refusal. A condition the flow already meets ("publish after the tests pass") is a yes. Unsure -> one question.
- B5. His short answer to a numbered question counts together with that question (`--question`).

C. Hook: bin/agent-keyword.sh adds ONE line for a main manager session (AGENT_ROLE unset, the lock's pid is this session) when the prompt speaks of publishing or merging to production (publish, merge to main, release, deploy, production, 上线, 发布, 部署) or of leaving out a check (skip the, leave out, 跳过): `Approval hook: if the owner is approving a publish or a skipped check here, read his words by the approval cases (PRINCIPLES.md R8) and the per-task target (W9). If the words are only mentioned or quoted, ignore this.` No logic in the hook; another session gets nothing.

D. Quiz: Q7, Q23, Q39 follow the new rule; Q40 the numbered batch, Q41 a description that fits one task, Q42 two similar tasks, Q43 "publish next week", Q44 P1 (a doubt a quick check settles: check, do not queue, do not ask). 44 questions.

E. Text leftovers: R1 target lines, R8 lines on removal/production/promote, W12 "words that name the action" follow A and B; R8 says PR REVIEW, FLOW CHECK and UI CHECK count only from a reviewer or check deputy the main manager launched; agents/merge-deputy.md fast-lane case: its commits are checked against `origin/<working branch>` (a task with `merged:`: `origin/<production branch>`), never `origin/<target>` (no brief field), and a task with `merged:` deletes its local branch with `git branch -D` after the production check; section F's "Agent skills:" line names `/auto-pipeline:slim-markdown` (renamed from md-slim, S6 below) and (TELL 9594c165) `/auto-pipeline:teacher-teach-me` (main e198fbe; origin/main is merged into the branch before the final verify).

F. tests/test_check_blocks_demo.py runs tests/check_blocks_demo.sh and asserts exit 0 and its walk and OWNER WORDS lines. It is heavy: it runs only when tests/run2.py runs the full suite (no file named), which sets AGENT_FULL_RUN=1 for its processes; else it is skipped with a reason. agent_repo.conf full_cmd = `python3 tests/run2.py`. The demo exits 1 with `DEMO FAILED:` when an expected exit code is not met.

G. `agent-file.sh state add`: a text holding a guessed clock time (a digit replaced by x: `18:0x`, `1x:45`, `18:xx`; or a tilde clock: `~11:45`, `~ 11:45`) prints one line `state add: warning: "<the time>" looks guessed; the stamp is the time` and still stores the line, exit 0.

## 54. FIX ORDERS 1 and 2 of approval-design (TELLs cdacc0c5, f68297ca, 37160e3c, 7e677c4d)

- FIX ORDER 1 R1-R6 and FIX ORDER 2 S1-S4: as written in those TELL blocks (the main manager's fix orders); the tests name each item.
- S5 (owner 2026-11-26 "for the quiz did you tidy it up ? means for those outdated can remove ya"): the quiz is tidied to 34 questions: old Q5, Q19, Q20, Q23, Q25, Q27, Q33, Q37 removed; Q8+Q9, Q10+Q14, Q24+Q34 merged; Q36 asks a task manager (a merge deputy is a subagent and takes no quiz).
- S6 (owner 2026-11-26 "test-slim and md-slim rename abit to slim-test-case to slim-markdown"): skills/test-slim -> skills/slim-test-case, skills/md-slim -> skills/slim-markdown; every place that names the SKILL follows; task names in history (test-slim, test-slim-2, md-slim, requirements/test-slim.md) and the tool file names stay.
