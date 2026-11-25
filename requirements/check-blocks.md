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
