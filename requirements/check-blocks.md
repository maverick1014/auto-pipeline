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
