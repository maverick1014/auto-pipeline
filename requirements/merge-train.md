# merge-train — requirements (level 3 rules gate)

Status: RULES READY 2026-11-24, waiting for the owner's yes. Base c16bc59 (0.42.0 + watch fixes).
Source: owner 2026-11-24: "why you dont just merge all of them first then only do the test suit"; "last time ... let each of the module only check for thier changes only, that one is actually better and is faster ... now need around 4 hour only can done all. last time is around 1 hour".
Scope add 1 (TELL af5b34e8, owner's words): "when the task is being merged into the merge train then the old worktree and agent will be clean ya. then if testing in merge train have some others issues. then will send out another agent at new worktree to do it again." → A21-A23; A22 is the main manager's addition. No new owner gate for these rows.
Scope add 2 (TELL 9ee4626c, the owner asked where the test-by-module rule went): it lives only in the owner's personal ~/.claude/CLAUDE.md law 7 (2026-11-12) and never reached PRINCIPLES.md, so every repo on the plugin runs a full suite per task (idea 128 saw it 11-16). Law 7: "touched modules only while iterating; at the handoff: the cheap whole-repo checks (guards, type-checks, lint) + the related tests the runners find from the diff. Integration tests by group: before a task merges, run only the touched module's integration group + the core group; the whole suite only for migrations / schema / dependency changes, release trains, and nightly on the integration branch." Plus per-repo test commands in agent.conf, so a brief pastes literal commands → section A0 and T1-T8.
Evidence (pc2, 2026-11-24): per task a TM full suite of 40-43 min (5700-5800 tests, one at a time under the heavy lock, tasks queued for it), then a second scoped suite at merge of 10-26 min, often a third run after a flaky fail: about 3 h of tests for 3 tasks. A per-task suite runs old main + one branch, so it never sees a clash between parallel branches. 2026-11-20: a deputy `reset --hard` wiped 2 todo lines + 3 queue waits (idea 149). 2026-11-24 12:23: a deputy's `while pgrep -f` wait loops never ended (idea 169).
Real data count (H1, this repo's agent files and git log): merges 2026-11-20: 3, 11-23: 1, 11-24: 5. Finished tasks with a level: 19, of them level 4: 4 (state-trim, board-waiting, board-trust, plugin-slim: hooks and release, no migration). Level 4 is common here: D2.

## 0. Words

| Word | Meaning |
|---|---|
| touched tests | the test files of the modules the diff changes |
| related tests | test files that import, call or name what the diff changed: a file, function, config key or rule code. A file almost every test names (the rules file, the config template): only the tests that name the changed part |
| cheap checks | the repo's whole-repo checks that take seconds to minutes: guards, lint, type-check, in CI's order |
| group tests | the touched module's integration group + the core group (law 7) |
| full suite | every test of the repo |
| train | one or more DONE PASS branches merged one by one into a local main (not pushed), then one test run (group tests or full suite, T6), one release, one push |
| base | origin/main when the train starts (P0) |
| merge point P<i> | the commit after the i-th branch of the train is merged |
| F | the tests the train's run failed |
| culprit | per test of F: the branch whose merge point is the first where that test fails |
| flaky | a test of F that fails at no merge point and passes alone 3 times at the train head |
| drop | take a branch out of the train: `git reset --keep` to the point before it, re-merge the later kept branches |
| join | a DONE PASS branch enters the train queue: its panes and worktree are cleaned at once, its branch stays (A21, A22) |
| report copy | the joined task's agent_state.txt, copied to `<git common dir>/agent_reports/<name>.txt` before its worktree goes (never tracked, shared by every worktree of the repo) |
| bounce | a dropped branch goes back for a fix: a NEW task manager in a NEW worktree from the kept branch (A23) |

## A0. Test commands (agent.conf, group `tests`)

| Key | Runs | Slots | Empty (default) | This repo |
|---|---|---|---|---|
| `test_check_cmd` | the cheap checks, at handoff | none | the TM names the checks it ran, or "none", in the report | `python3 -m compileall -q bin tests` |
| `test_related_cmd` | the related tests, at handoff | `{files}` changed files, `{base}` base ref, `{tests}` the related test files the TM found | the TM finds the related tests itself and writes the exact command in the report | `python3 -m unittest {tests}` (`{tests}` as module names, `tests.test_agent_watch`) |
| `test_group_cmd` | group tests, a train of one | `{files}`, `{base}` | a train of one runs `test_full_cmd` | empty: this repo has no integration groups |
| `test_full_cmd` | the full suite: trains of two or more, level 4, nightly | none | the main manager writes the command into the deputy brief by hand | `python3 -m unittest discover -s tests -t .` |
| `train_wait_min` | the longest wait of a queued branch (A5) | - | 60 (0 = run the train at once) | 60 |

Validation (agent_conf.py): the four commands are free text; a `{...}` slot other than the ones of its row is refused with one line naming it. `train_wait_min` is a whole number 0-1440. The keys go after `level4_paths` in the template, in the order above; init and settings show them as group `tests`.

## T. Which tests run when (law 7 in the plugin)

| # | Rule | Example |
|---|---|---|
| T1 | While iterating: the touched module's tests only (a worker: its one test command) | worker on bin/agent_watch.py: `python3 -m unittest tests.test_agent_watch` |
| T2 | At handoff (TM verify), levels 2-4: `test_check_cmd` + `test_related_cmd`. Level 1: the cheap checks only (R8). Level 0: none | merge-train itself: `python3 -m compileall -q bin tests` + `python3 -m unittest tests.test_merge_train tests.test_risk_levels ...` |
| T3 | Never a full suite in a task, at any level. Level 4 keeps its dry-run, rollback plan and owner sign | a level 4 lockfile bump: dry-run + related tests in the task, full suite in its train |
| T4 | The brief pastes the commands of agent.conf literally (`TESTS:` line); an empty key says what the TM must do instead (A0 column "Empty") | `TESTS: check: python3 -m compileall -q bin tests · related: python3 -m unittest {tests} · group, full: at merge (train)` |
| T5 | The report's Result names every command run, with its counts; never "ran the tests" | `Result: compileall ok; python3 -m unittest tests.test_merge_train ... : Ran 61 tests OK` |
| T6 | At merge the train runs ONE of: `test_group_cmd` (a train of one, no level 4 branch, key set); else `test_full_cmd` (two or more branches, or a level 4 branch, or the group key empty) (D4) | train [X] in a Flutter repo with groups: group tests 4 min. Train [A, B]: full suite |
| T7 | Full-suite trigger = REQUIRED LEVEL 4 of `agent-level.sh check` (migrations, schema, lockfiles, dependency lists, `level4_paths`); no second path list (D5) | a branch touching `db/migrations/` → level 4 → its train runs the full suite |
| T8 | Nightly: `test_full_cmd` on the integration branch, where the repo has a nightly job; red → a main-red task | this repo has no nightly job (idea logged, not in this task) |

## A. Train rules

| # | Rule | Example |
|---|---|---|
| A1 | The train replaces every per-task full suite and every second suite at merge; the per-level extras stay (1 screenshots, 2 TDD + E2E, 3 rules table + Opus reviewer, 4 dry-run + rollback plan + owner sign) | 3 tasks done the same hour: 1 suite of 40 min instead of 3 x (40 + 10-26) min |
| A4 | Join (main manager, after merge step 1-3: level check once, E2E, app stopped): `todo stage "<name>" merge` and `todo wait "<name>" on queue "merge train"`; the todo line stays open; then the join cleanup (A21). The deputy does not repeat the level check (the worktree is gone) | board: `queue · merge train · waited 12m` |
| A5 | Run the train when: (a) no other open task is at stage verify, push or report, or (b) the oldest queued branch has waited `train_wait_min`, or (c) the owner says merge now. A single urgent task = a train of one (c) | 14:00 A done, B at verify: wait. 14:20 B done, C at workers: train A+B. B still at verify at 15:00: train A alone |
| A6 | Order: oldest DONE PASS first; a branch that needs another goes after it; at most one level 4 branch per train, merged last (D2) | A (L3), B (L2), D (L4): order A, B, D |
| A7 | Run (merge deputy, one launch): fetch; local main = origin/main; per branch `git merge --no-ff`, note its merge point; then the train's one test run (T6) on the head, in the heavy test slot | train A, B, D: P1 = A, P2 = A+B, P3 = A+B+D, full suite on P3 |
| A8 | Green: one release (version bump once, one commit naming every merged task, the tests that name the version file), the release branch push before main (repos with bin/agent-release.sh), push main, then per merged branch: delete the branch (remote + local), todo done with the facts | `release 0.43.0 (A, B, D)`, `bin/agent-release.sh --push`, `git push origin main` |
| A9 | Red: run only F at the base, then at P1, P2, ... in order (`git checkout --detach <point>`, run F, `git checkout main`). Per test of F, its first failing point names its culprit | see B2 |
| A10 | Drop every culprit and every later branch that needs one (it holds the culprit's commits: `git merge-base --is-ancestor`, or its brief row says needs): `git reset --keep` to the point before the first dropped one, re-merge the later kept branches, run only F on the new head. Green → A8. Never a second suite run in one train | see B2, B5 |
| A11 | Bounce (main manager): the fix dispatch of A23 with the failed tests, their first output lines and the merge point. The branch and the todo line stay; after the fix it is DONE PASS again and joins the next train | brief: `test_x fails at P2 (B merged onto A), train head 1a2b3c4` |
| A12 | F fails at the base → main is red: `git reset --keep origin/main`, MERGE FAIL main red, no branch blamed; the main manager opens a main-red task first | see B7 |
| A13 | F fails at no merge point and passes alone 3 times on the head → flaky: the report names it, the main manager logs an idea, the train goes on (A8). One of the 3 fails → MERGE FAIL with the output | see B3 |
| A14 | Red again after a drop → `git reset --keep origin/main`, MERGE FAIL with the evidence; the main manager decides | a second, hidden clash between the kept branches |
| A15 | Conflict while merging a branch → `git merge --abort`, drop it (CONFLICT + files), go on with the rest. Fix (A23): after the train is pushed, the new task manager merges origin/main into the branch, resolves, runs the handoff tests (T2), DONE PASS again | C and A both edit W8 of PRINCIPLES.md |
| A16 | Rollback is always `git reset --keep <commit>`: it keeps uncommitted agent files and stops when they clash. Never `--hard` (the permission classifier denies it; it wiped agent files 2026-11-20). A checkout or reset that stops → MERGE FAIL with its message, never forced | `git reset --keep origin/main` drops the whole local train; nothing was pushed |
| A17 | Waiting for a test run: fits one Bash call (10 min) → foreground. Longer → Bash run_in_background writes the exit code to a file; wait for that file in foreground calls of at most 9 min. Never a `while pgrep -f` loop: it matches its own command line and never ends (D3) | pc2 full suite 40-43 min: 1 background start + 5 waits |
| A18 | While a train runs: no commit on main in the main checkout (a fast-lane deputy waits, `todo wait ... on queue --after <train task>`); a new DONE PASS joins the queue and waits for the next train | fast lane typo-fix at 14:30, train suite until 15:05: the deputy starts 15:06 |
| A19 | Who: the merge deputy runs A7-A10, A12, A13, A15-A17 as written; they hold no choice. The main manager does the join (A4, A21), picks the train, its order and its test command (A5, A6, T6), bounces (A11, A23), logs flaky ideas, decides A14. Sonnet never decides (W17) | MERGE PASS with `DROPPED B` → the main manager dispatches B's fix |
| A20 | Other repos get this by the plugin release. The rules name no path of this repo: the commands come from agent.conf (A0), the version file and the release step from the brief | a Flutter repo: full `flutter test -j 2`, version file pubspec.yaml |
| A21 | Join cleanup (main manager, right after A4): copy the report (report copy); the worktree must be clean (only agent_state.txt) and pushed (`git log origin/<branch>..HEAD` empty), else the still-open task manager is told to push first. Then close the task manager pane and, on another machine, its shell pane (`agent-runtime.sh close <handle>`), `orca worktree rm`, `agent-file.sh worktree rm <path>`. Plain or cloud: no pane or worktree, nothing to close | B DONE PASS 14:20, E2E ok 14:30: report copied, pane closed, worktree removed 14:31; todo line open, stage merge, queue merge train |
| A22 | The branch (remote and local) is KEPT until its train is green; the deputy deletes it then. A dropped branch keeps it (main manager's addition) | B dropped at 15:10: origin/B stays for the fix |
| A23 | Fix after a red train (main manager): dispatch a NEW task manager in a NEW worktree based on the kept branch (`orca worktree create --name <name>-fix<n> --base-branch <branch>`), same todo line, same level. Brief: the failed tests + their output, the report copy path, the train head sha. It fixes (workers), runs the failed tests + the handoff tests (T2), reports DONE PASS, joins the next train; that train runs its one test run as usual. The old branch goes with the train that merges the fix (the fix branch holds its commits) | B dropped → `B-fix1` worktree from origin/B, DONE PASS 15:40, joins train 2 |

## B. Edge cases, worked through

| # | Case | What happens |
|---|---|---|
| B1 | Train of one (urgent fix) | Owner: "merge X now" → train [X]: merge, `test_group_cmd` (or `test_full_cmd` when empty or X is level 4), release, push. The task itself ran no full suite |
| B2 | Failing train, 3 branches A, B, C | Full suite on P3 red: test_x, test_y. F = [test_x, test_y] at base: pass; P1 (A): pass; P2 (A+B): both fail → B is the culprit. `git reset --keep P1`, re-merge C → P2', run F: green → `release (A, C)`, push. origin/B kept; a new task manager in worktree B-fix1 gets "test_x, test_y fail at P2 (B merged onto A)", the report copy and the train head. Cost: one 40 min suite + 3 runs of 2 tests (seconds); today: 3 x (40 + 10-26) min |
| B3 | Flaky test | Suite red only on test_z; test_z passes at base, P1, P2, P3 and 3 times alone on P3 → `FLAKY test_z` in the report, idea logged, train pushed |
| B4 | Level 4 branch D in a train | Owner signed D before the train. Order A, B, D (D last, only one L4); the train runs the full suite (T6, T7). D culprit → reset to P2, push A+B. A or B culprit → dropped, D re-merged, F re-run. D's rollback plan covers one merge commit, the last one |
| B5 | B needs A (branched from A, or the brief row says needs A) | Order A, B. A dropped → B dropped too (it holds A's commits); B's fix brief says "dropped because A was dropped"; when A's fix changes nothing B needs, B's new task manager merges A's fix and reports DONE PASS again |
| B6 | Nightly | The repo's nightly job runs `test_full_cmd` on main; red → a main-red task. A repo without a nightly job: the train runs are its only full runs; this repo has none today (idea) |
| B7 | Main already red | F fails at the base → MERGE FAIL main red, nothing pushed, the branches stay queued, the main-red task goes first, then the train again |
| B8 | DONE PASS while the suite runs | Joins the queue, waits for the next train |
| B9 | Two culprits | test_x first fails at P1 (A), test_y at P3 (C) → drop A and C: `git reset --keep` base, re-merge B → P1', run F: green → push B |
| B10 | RAISE at the level check | Found at merge step 1, before the E2E and the join, as today: the main manager raises the todo line and bounces it to the still-open task manager; it never joins the queue |
| B11 | Worktree not clean or not pushed at the join | No cleanup: the still-open task manager is told to commit and push first, then the join runs again |
| B12 | The main manager's session is cleared or crashes during a queue | The queue is on the board (todo lines at stage merge with a queue wait); the reports are in `<git common dir>/agent_reports/`; nothing lived only in the closed panes |
| B13 | A repo with every test key empty | Same rules; the TM states its handoff commands in the report, the main manager writes the full suite command into the deputy brief, and every train runs the full suite |

## C. Text changes (old → new; one line per rule, each at most 200 characters)

PRINCIPLES.md
- R7: `Deputy removes the line after cleanup` → `The main manager removes the line when the task joins a merge train (W8)`
- R8 level 2 line: `touched-module tests + lint/type-check` → `touched-module + related tests + the cheap checks (W4)`
- R8 level 3 line: `touched module + core integration group; full suite once` → `touched module + related tests; group tests or the full suite once, in the merge train (W8)`
- R8 after the level 4 gate line (it would pass 200 characters): `- 4 in a merge train: at most one level 4 branch, merged last; that train runs the full suite (W8)`
- W4, new text:
  - `- While iterating: the touched module's tests only`
  - `- At handoff, levels 2-4: the cheap checks (test_check_cmd: guards, lint, type-check) + the related tests (test_related_cmd)`
  - `- Related tests import, call or name what changed (file, function, key, rule). Key empty: find them, write the exact command in the report`
  - `- Never a full suite in a task. The merge train runs test_group_cmd for one branch, test_full_cmd for two or more or level 4 (W8)`
  - `- Nightly: test_full_cmd on the integration branch, where the repo has a nightly job`
  - `- CI's steps run in CI's order: the cheap checks once at handoff, the train's run once at merge`
  - kept: `- After a bounce: re-run only the tests that failed, not the suite`, `- Which tests run follows the level gate (R8)`
- W8: `- Deputy merges into the integration branch` → the train lines:
  - `- Deputy merges a train into the integration branch: one or more DONE PASS branches, one by one, on a local main, not pushed`
  - `- Train: one test run on the merged tree (heavy test slot, S5, W4), then one release, then one push. An urgent single task is a train of one`
  - `- Run it when no other open task is at stage verify, push or report, or the oldest queued branch waited train_wait_min, or the owner says merge now`
  - `- Order: oldest DONE PASS first; a branch that needs another goes after it; at most one level 4 branch, merged last`
  - `- Red train: run only the failed tests at the base, then at each merge point in order; the first point where a test fails names its branch`
  - `- Drop that branch and every branch that needs it, re-merge the rest, re-run only the failed tests. Never a second suite run in one train`
  - `- Failed tests that fail at no merge point and pass alone 3 times: flaky. Name it, log an idea, go on. Red at the base: main is red, no branch blamed`
  - `- Rollback: git reset --keep <commit>, never --hard (it wipes uncommitted agent files). Nothing is pushed before the train is green`
  - `- Deputy deletes the branch (local + remote) and the worktree right after merge` → `- At the join the main manager saves the report, closes the task's panes, removes its worktree; the branch stays until its train is green`
  - `- Clean up only after the merge is verified` → `- Delete a branch only after the merge is verified; a dropped branch stays for a new task manager in a new worktree`
  - `- Deputy runs ./agent-file.sh worktree rm <path> and ./agent-file.sh todo done ...` → worktree rm by the main manager at the join; todo done by the deputy after the green train, with the facts and `--merge <commit>`
- S6: `Never one still waiting on a merge, a question or a decision (W8 closes it after the merge)` → `Never one still waiting on a question or a decision; a DONE PASS pane closes when its task joins a merge train (W8)`
- S9: `- Passing tests are not re-run. Full suite once, at the end (W4)` → `- Passing tests are not re-run. No full suite in a task; one test run per merge train (W4)`

skills/dispatch/SKILL.md
- Task manager brief: a new `TESTS:` line after `LEVEL:`, filled from agent.conf (`agent-settings.sh get test_check_cmd`, `test_related_cmd`): the literal commands, or the "Empty" text of A0.
- Step 5: `Full suite once.` → `The handoff tests of the TESTS: line (W4); no full suite, the merge train runs it.`
- REPORT: `Result (test count)` → `Result (every test command run, with its counts)`
- NEVER: `Full suite twice (W4).` → `A full suite (W4: the merge train runs it).`
- A fix after a red train (A23): `orca worktree create --name <name>-fix<n> ... --base-branch <branch>`; the brief carries the failed tests, the report copy path and the train head.
- Stage names: the board knows no `train` stage, so a joined task shows stage `merge` + wait `queue · merge train` (the TELL said stage train; a new stage is code in agent-file.sh and agent.conf for no new information).

skills/merge/SKILL.md
- Description and title: merge done features as one train.
- Steps 1-3 per DONE PASS branch stay (level check once, E2E, stop the app); then the join (A4, A21): stage merge, queue wait, report copy, clean and pushed check, close panes, `orca worktree rm`, `worktree rm`.
- New step: when to run the train (A5), order (A6), its test command (T6, T7), while it runs (A18).
- Deputy brief: train rows `<name> | <branch> | level <n> | needs <names or -> | <todo done arguments>`, `test command` (filled `test_group_cmd` or `test_full_cmd`, in the heavy test slot), `release: <version> in <file> | none`. Description `<first name> Merge: train <name>, <name>`.
- MERGE PASS: per `DROPPED` line the fix dispatch (A11, A15, A23); per `FLAKY` line `agent-file.sh idea add`; then the H3 report.
- Release step: one release per train, the deputy bumps the version once; the `bin/agent-release.sh --push` before main line stays, same order.

agents/merge-deputy.md
- Brief: the train rows, the test command, release.
- Steps: A7 (no level check, no worktree), A8 (delete branches, todo done; no pane or worktree step), A9, A10, A12, A13, A15, A16, A17 as numbered steps; `git reset --hard ORIG_HEAD` → `git reset --keep`; report lines `MERGED <name> <hash>`, `DROPPED <name>: <why>`, `FLAKY <test>`.

agents/worker.md: no change (it runs only its one test command and never the full suite).
README.md: the merge deputy row and tree line lose "close terminal, remove worktree" (now at the join): `Merge a train, one test run, release once, push, delete merged branches, update agent files.`; tree: `train merge → one test run → push → delete branches`.
bin/agent_conf.py, bin/agent.conf.default, this repo's agent.conf: the five keys of A0 (code, one worker slice).

## D. Tests (step 3)

New tests/test_merge_train.py, rule text tests like tests/test_board_trust.py TestRuleText: W4 (T1-T8 words, the key names), W8 (train, red train, reset --keep, flaky, join, kept branch), R7, R8 (every level line), S6, S9, each line at most 200 characters; dispatch brief TESTS: line, step 5, REPORT and NEVER lines, the fix worktree; merge skill join, train steps, brief rows, fix dispatch, flaky, the one release line still before main; merge-deputy (reset --keep, no --hard, no pgrep loop, exit-code file wait, F at the base first, DROPPED/FLAKY/MERGED lines, no worktree step). Config: the five keys (template order after level4_paths, group `tests`, slot check, number range, this repo's values). Old tests that pin a replaced line change only where they pin it (tests/test_agent_cleanup.py S6 phrase).
This task's own verify (the new way): `python3 -m compileall -q bin tests` + tests/test_merge_train.py + the related tests (those that name the changed rules, skills, agent files or keys). No full suite.

## E. To decide (the rules gate waits for the owner's yes)

| # | Question | Options | Recommendation |
|---|---|---|---|
| D1 | The train's longest wait needs a number; the rules say every number is a setting | A: `train_wait_min=60` (in A0's code slice anyway). B: no cap, wait only while another task is at verify, push or report | A |
| D2 | A level 4 branch (here 4 of 19 tasks) | A: rides in a train, at most one, merged last (its rollback = one merge commit, no extra suite). B: always a train of one (one more 40 min suite each) | A |
| D3 | The brief says "foreground suite", but one Bash call stops at 10 min and the pc2 suite takes 40 min | A: foreground when it fits, else background + wait for its exit-code file in foreground calls of at most 9 min, never pgrep. B: split the suite into parts under 10 min (repo specific) | A |
| D4 | A train of one: law 7 says group tests before a single task merges; the first brief said one full suite | A: group tests when `test_group_cmd` is set and no level 4 branch, else the full suite (this repo: full, no groups). B: always the full suite | A |
| D5 | Full-suite trigger paths (law 7: migrations, schema, dependency) | A: reuse level 4 of agent-level.sh (its built-in paths + `level4_paths`), no new key. B: a new key `test_full_triggers`, read by agent-level.sh (more code and tests) | A |
