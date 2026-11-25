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
