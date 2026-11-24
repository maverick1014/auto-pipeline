# merge-train — requirements (level 3 rules gate)

Status: RULES READY 2026-11-24, waiting for the owner's yes. Base c16bc59 (0.42.0 + watch fixes).
Scope add 2026-11-24 (TELL af5b34e8, owner's words): "when the task is being merged into the merge train then the old worktree and agent will be clean ya. then if testing in merge train have some others issues. then will send out another agent at new worktree to do it again." → A21-A23; A22 is the main manager's addition. No new owner gate for these rows (the owner asked for them).
Source: owner 2026-11-24: "why you dont just merge all of them first then only do the test suit"; "last time ... let each of the module only check for thier changes only, that one is actually better and is faster ... now need around 4 hour only can done all. last time is around 1 hour". Owner machine rule 2026-11-12 (law 7): touched modules while iterating; at handoff the cheap whole-repo checks + the related tests the runners find from the diff; the whole suite only for migrations/schema/dependency changes, release trains and nightly.
Evidence (pc2, 2026-11-24): per task a TM full suite of 40-43 min (5700-5800 tests, one at a time under the heavy lock, tasks queued for it), then a second scoped suite at merge of 10-26 min, often a third run after a flaky fail: about 3 h of tests for 3 tasks. A per-task suite runs old main + one branch, so it never sees a clash between parallel branches. 2026-11-20: a deputy `reset --hard` wiped 2 todo lines + 3 queue waits (idea 149). 2026-11-24 12:23: a deputy's `while pgrep -f` wait loops never ended (idea 169).
Real data count (H1, this repo's agent files and git log): merges 2026-11-20: 3, 11-23: 1, 11-24: 5. Finished tasks with a level: 19, of them level 4: 4 (state-trim, board-waiting, board-trust, plugin-slim: hooks and release, no migration). So level 4 is common here: D2.

## 0. Words

| Word | Meaning |
|---|---|
| touched tests | the test files of the modules the diff changes |
| related tests | test files that import, call or name what the diff changed: a file, function, config key or rule code. A file almost every test names (the rules file, the config template): only the tests that name the changed part |
| cheap checks | the repo's whole-repo checks that take seconds to minutes: guards, lint, type-check, in CI's order |
| full suite | every test of the repo |
| train | one or more DONE PASS branches merged one by one into a local main (not pushed), then one full suite, one release, one push |
| base | origin/main when the train starts (P0) |
| merge point P<i> | the commit after the i-th branch of the train is merged |
| F | the tests the train's full suite failed |
| culprit | per test of F: the branch whose merge point is the first where that test fails |
| flaky | a test of F that fails at no merge point and passes alone 3 times at the train head |
| drop | take a branch out of the train: `git reset --keep` to the point before it, re-merge the later kept branches |
| join | a DONE PASS branch enters the train queue: its panes and worktree are cleaned at once, its branch stays (A21, A22) |
| report copy | the joined task's agent_state.txt, copied to `<git common dir>/agent_reports/<name>.txt` before its worktree goes (never tracked, shared by every worktree of the repo) |
| bounce | a dropped branch goes back for a fix: a NEW task manager in a NEW worktree from the kept branch (A23) |

## A. Rules table

| # | Rule | Example |
|---|---|---|
| A1 | Task verify, every level: touched tests + related tests + cheap checks. Never a full suite in a task. A worker runs its one test command (unchanged) | TM changed bin/agent_watch.py: tests/test_agent_watch.py + the test files that name agent_watch (test_watch_board.py, ...) + the guards. Minutes, not 40 min |
| A2 | Level gates keep their extras and lose only the full suite: 1 screenshots, 2 TDD + E2E, 3 rules table + Opus reviewer + core integration group, 4 dry-run + rollback plan + owner sign | level 3 one-watcher: reviewer + touched + related + core group; its full suite runs in its train |
| A3 | The full suite runs only: once per train (on the merged tree, in the heavy test slot), and nightly where the repo has a nightly job | 3 tasks done the same hour: 1 suite of 40 min instead of 3 x (40 + 10-26) min |
| A4 | Queue: a DONE PASS branch that passed its E2E and level check joins the queue: `todo stage "<name>" merge` and `todo wait "<name>" on queue "merge train"`. The todo line stays open. The level check runs here, once (merge step 1); the deputy does not repeat it (the worktree is gone) | board: `queue · merge train · waited 12m` |
| A5 | Run the train when: (a) no other open task is at stage verify, push or report, or (b) the oldest waiting branch has waited `train_wait_min` (agent.conf, default 60, D1), or (c) the owner says merge now | 14:00 A done, B at verify: wait. 14:20 B done, C at workers: train A+B. B still at verify at 15:00: train A alone |
| A6 | Order: oldest DONE PASS first; a branch that needs another goes after it; at most one level 4 branch per train, merged last (D2) | A (L3), B (L2), D (L4): order A, B, D |
| A7 | Run (merge deputy, one launch): fetch; local main = origin/main; per branch: level check, `git merge --no-ff`, note its merge point; then the full suite once on the head | train A, B, D: P1 = A, P2 = A+B, P3 = A+B+D, suite on P3 |
| A8 | Green: one release (version bump once, one commit naming every merged task, the tests that name the version file), the release branch push before main (repos with bin/agent-release.sh), push main, then per merged branch: delete the branch (remote + local), todo done (panes and worktree went at the join, A21) | `release 0.43.0 (A, B, D)`, `bin/agent-release.sh --push`, `git push origin main` |
| A9 | Red: run only F at the base, then at P1, P2, ... in order (`git checkout --detach <point>`, run F, `git checkout main`). Per test of F, its first failing point names its culprit | see B2 |
| A10 | Drop every culprit and every later branch that needs one (it contains the culprit's commits: `git merge-base --is-ancestor`, or its brief row says needs): `git reset --keep` to the point before the first dropped one, re-merge the later kept branches, run only F on the new head. Green → A8. Never a second full suite in one train | see B2, B5 |
| A11 | Bounce (main manager): dispatch per A23 with the failed tests, their first output lines and the merge point. The branch and the todo line stay; after the fix it is DONE PASS again and joins the next train | brief: `test_x fails at P2 (B merged onto A), train head 1a2b3c4` |
| A12 | F fails at the base → main is red: `git reset --keep origin/main`, MERGE FAIL main red, no branch blamed; the main manager opens a main-red task first | see B7 |
| A13 | F fails at no merge point and passes alone 3 times on the head → flaky: the report names it, the main manager logs an idea, the train goes on (A8). One of the 3 fails → MERGE FAIL with the output | see B3 |
| A14 | Red again after a drop → `git reset --keep origin/main`, MERGE FAIL with the evidence; the main manager decides | a second, hidden clash between the kept branches |
| A15 | Conflict while merging a branch → `git merge --abort`, drop it (CONFLICT + files), go on with the rest. Bounce (A23): after the train is pushed, the new task manager merges origin/main into the branch, resolves, runs touched + related tests, DONE PASS again | C and A both edit W8 of PRINCIPLES.md |
| A16 | Rollback is always `git reset --keep <commit>`: it keeps uncommitted agent files and stops when they clash. Never `--hard` (the permission classifier denies it; it wiped agent files 2026-11-20). A checkout or reset that stops → MERGE FAIL with its message, never forced | `git reset --keep origin/main` drops the whole local train; nothing was pushed |
| A17 | Waiting for the suite: fits one Bash call (10 min) → foreground. Longer → Bash run_in_background writes the exit code to a file; wait for that file in foreground calls of at most 9 min. Never a `while pgrep -f` loop: it matches its own command line and never ends (D3) | pc2 full suite 40-43 min: 1 background start + 5 waits |
| A18 | While a train runs: no commit on main in the main checkout (a fast-lane deputy waits, `todo wait ... on queue --after <train task>`); a new DONE PASS joins the queue (A4, A21) and waits for the next train | fast lane typo-fix at 14:30, train suite until 15:05: the deputy starts 15:06 |
| A19 | Who: the merge deputy runs A7-A10, A12, A13, A15-A17 as written; they hold no choice. The main manager does the join cleanup (A21), picks the train and its order (A5, A6), bounces (A11, A23), logs flaky ideas, decides A14. Sonnet never decides (W17) | MERGE PASS with `DROPPED B` → the main manager sends the bounce |
| A21 | Join cleanup (main manager, right after A4): copy the report (report copy); the worktree must be clean (only agent_state.txt) and pushed (`git log origin/<branch>..HEAD` empty), else bounce to the still-open task manager: push first. Then close the task manager pane and, on another machine, its shell pane (`agent-runtime.sh close <handle>`), `orca worktree rm`, `agent-file.sh worktree rm <path>`. Plain or cloud: there is no pane or worktree, nothing to close | B DONE PASS 14:20, E2E ok 14:30: report copied, pane closed, worktree removed 14:31; todo line open, stage merge, queue merge train |
| A22 | The branch (remote and local) is KEPT until its train is green; the deputy deletes it then. A dropped branch keeps it (main manager's addition) | B dropped at 15:10: origin/B stays for the fix |
| A23 | Fix after a red train (main manager): dispatch a NEW task manager in a NEW worktree based on the kept branch (`orca worktree create --name <name>-fix<n> --base-branch <branch>`), same todo line, same level. Brief: the failed tests + their output, the report copy, the train head sha. It fixes (workers), runs the failed tests + touched + related tests (no full suite), reports DONE PASS, joins the next train; that train runs its one full suite as usual. The old branch is deleted with the train that merges the fix (the fix branch holds its commits) | B dropped → `B-fix1` worktree from origin/B, DONE PASS 15:40, joins train 2 |
| A20 | Other repos get this by the plugin release. The rules name no path of this repo: the suite command, the version file and the release step come from the brief | a Flutter repo: suite `flutter test -j 2`, version file pubspec.yaml, release none |

## B. Edge cases, worked through

| # | Case | What happens |
|---|---|---|
| B1 | Train of one (urgent fix) | Owner: "merge X now" → train [X]: merge, full suite once, release, push. The task itself ran no full suite |
| B2 | Failing train, 3 branches A, B, C | Suite on P3 red: test_x, test_y. F = [test_x, test_y] at base: pass; P1 (A): pass; P2 (A+B): both fail → B is the culprit; P3 not needed for them. `git reset --keep P1`, re-merge C → P2', run F: green → `release (A, C)`, push. origin/B kept; a new task manager in worktree B-fix1 gets "test_x, test_y fail at P2 (B merged onto A)", the report copy and the train head. Cost: one 40 min suite + 3 runs of 2 tests (seconds); today: 3 x (40 + 10-26) min |
| B3 | Flaky test | Suite red only on test_z; test_z passes at base, P1, P2, P3 and 3 times alone on P3 → `FLAKY test_z` in the report, idea logged, train pushed |
| B4 | Level 4 branch D in a train | Owner signed D before the train. Order A, B, D (D last, only one L4). D culprit → reset to P2, push A+B. A or B culprit → dropped, D re-merged, F re-run. D's rollback plan covers one merge commit, the last one |
| B5 | B needs A (branched from A, or the brief row says needs A) | Order A, B. A dropped → B dropped too (it holds A's commits); B's fix brief says "dropped because A was dropped"; when A's fix holds no change B needs, B's new task manager just reports DONE PASS again after merging A's fix |
| B6 | Nightly | The repo's nightly job runs the full suite on main; red → a main-red task. This repo has no nightly job today: the train suites are its only full runs (idea logged, not in this task) |
| B7 | Main already red | F fails at the base → MERGE FAIL main red, nothing pushed, the branches stay queued, the main-red task goes first, then the train again |
| B8 | DONE PASS while the suite runs | Waits for the next train |
| B9 | Two culprits | test_x first fails at P1 (A), test_y at P3 (C) → drop A and C: `git reset --keep` base, re-merge B → P1', run F: green → push B |
| B10 | RAISE at the level check of one branch | Found at merge step 1, before the E2E and the join, as today: the main manager raises the todo line and bounces it to the still-open task manager; it never joins the queue |
| B11 | Worktree not clean or not pushed at the join | No cleanup: the still-open task manager is told to commit and push first, then the join runs again |
| B12 | The main manager's session is cleared or crashes during a queue | The queue is on the board (todo lines at stage merge with a queue wait); the reports are in `<git common dir>/agent_reports/`; nothing lived only in the closed panes |

## C. Text changes (old → new; one line per rule, each at most 200 characters)

PRINCIPLES.md
- R8 level 2 line: `touched-module tests + lint/type-check` → `touched-module + related tests + lint/type-check`
- R8 level 3 line: `touched module + core integration group; full suite once` → `touched module + related tests + core integration group; full suite once, in the merge train (W8)`
- R8 after the level 4 gate line, a new line (the gate line would pass 200 characters): `- 4 in a merge train: at most one level 4 branch, merged last (W8)`
- W4: `- Full suite: manager, once, at the end. Never twice` and the CI line → four lines:
  - `- Task verify, every level: touched-module tests + related tests (they import, call or name what changed) + the cheap whole-repo checks (guards, lint, type-check)`
  - `- Never a full suite in a task. The full suite runs once per merge train, on the merged tree (W8), and nightly where the repo has a nightly job`
  - `- CI's steps run in CI's order: the cheap checks once at handoff, the full suite once in the train`
- W8: `- Deputy merges into the integration branch` → the train lines:
  - `- Deputy merges a train into the integration branch: one or more DONE PASS branches, one by one, on a local main, not pushed`
  - `- Train: one full suite on the merged tree (heavy test slot, S5), then one release, then one push. An urgent single task is a train of one`
  - `- Run it when no other open task is at stage verify, push or report, or the oldest waiting branch waited train_wait_min, or the owner says merge now`
  - `- Order: oldest DONE PASS first; a branch that needs another goes after it; at most one level 4 branch, merged last`
  - `- Red train: run only the failed tests at the base, then at each merge point in order; the first point where a test fails names its branch`
  - `- Drop that branch and every branch that needs it, re-merge the rest, re-run only the failed tests. Never a second full suite in one train`
  - `- The main manager bounces each dropped branch to its task manager with the evidence: failed tests, output, merge point`
  - `- Failed tests that fail at no merge point and pass alone 3 times: flaky. Name it, log an idea, go on. Red at the base: main is red, no branch blamed`
  - `- Rollback: git reset --keep <commit>, never --hard (it wipes uncommitted agent files). Nothing is pushed before the train is green`
  - `- Deputy deletes the branch (local + remote) and the worktree right after merge` → `- At the join the main manager saves the report, closes the task's panes, removes its worktree; the branch stays until its train is green`
  - `- Clean up only after the merge is verified` → `- Delete a branch only after the merge is verified; a dropped branch stays for a new task manager in a new worktree`
  - `- Deputy runs ./agent-file.sh worktree rm <path> and ./agent-file.sh todo done ...` → worktree rm by the main manager at the join; todo done by the deputy after the green train, with the facts and `--merge <commit>`
- R7: `Deputy removes the line after cleanup` → `The main manager removes the line when the task joins a merge train (W8)`
- S6: `Never one still waiting on a merge, a question or a decision (W8 closes it after the merge)` → `Never one still waiting on a question or a decision; a DONE PASS pane closes when its task joins a merge train (W8)`
- S9: `- Passing tests are not re-run. Full suite once, at the end (W4)` → `- Passing tests are not re-run. Full suite once per merge train, never in a task (W4)`

skills/dispatch/SKILL.md (task manager brief)
- Step 5: `Full suite once.` → `Touched-module tests + related tests + the cheap whole-repo checks (W4); no full suite, it runs once in the merge train.`
- REPORT: `Result (test count)` → `Result (tests run: which and how many)`
- NEVER: `Full suite twice (W4).` → `A full suite (W4: it runs once per merge train).`

skills/merge/SKILL.md
- Description and title: merge done features as one train.
- Steps 1-3 per DONE PASS branch stay; after step 3 the branch waits: `todo wait "<name>" on queue "merge train"`.
- New step: when to run the train (A5), order (A6), while it runs (A18).
- After the E2E: the join (A4, A21): report copy, clean and pushed check, close panes, `orca worktree rm`, `worktree rm`, stage merge, queue wait.
- Deputy brief: train rows `<name> | <branch> | level <n> | needs <names or -> | <todo done arguments>` (no worktree, no terminal: gone at the join), `suite command` (the full suite, in the heavy test slot), `release: <version> in <file> | none`. Description `<first name> Merge: train <name>, <name>`.
- MERGE PASS: per `DROPPED` line the fix dispatch (A11, A15, A23); per `FLAKY` line `agent-file.sh idea add`; then the H3 report.
- Release step: one release per train, the deputy bumps the version once; the `bin/agent-release.sh --push` before main line stays, same order.

skills/dispatch/SKILL.md (routing)
- A fix after a red train (A23): `orca worktree create --name <name>-fix<n> ... --base-branch <branch>`; the brief carries the failed tests, the report copy path and the train head.
- Stage names: the board knows no `train` stage, so a joined task shows stage `merge` + wait `queue · merge train` (the TELL said stage train; adding a stage is code in agent-file.sh and agent.conf for no new information).

agents/merge-deputy.md
- Brief: the train rows, suite command, release.
- Steps: A7 (no level check, no worktree), A8 (delete branches, todo done; no pane or worktree step), A9, A10, A12, A13, A15, A16, A17 as numbered steps; `git reset --hard ORIG_HEAD` → `git reset --keep`; report lines `MERGED <name> <hash>`, `DROPPED <name>: <why>`, `FLAKY <test>`.

agents/worker.md: no change (it already runs only its one test command and never the full suite).
README.md: the merge deputy row and tree line lose "close terminal, remove worktree" (now at the join): `Merge a train, suite once, release once, push, delete merged branches, update agent files.`; tree: `train merge → one suite → push → delete branches`.
D1 A only: `train_wait_min` in bin/agent_conf.py (range 0-1440, 0 = run at once, description), bin/agent.conf.default and this repo's agent.conf (60, template key order).

## D. Tests (step 3)

New tests/test_merge_train.py, rule text tests like tests/test_board_trust.py TestRuleText: W4, W8, R8, S9 lines and their 200-character cap; dispatch step 5, REPORT and NEVER lines; merge skill train steps, brief rows, bounce and flaky handling, the one release line still before main; merge-deputy steps (reset --keep, no --hard, no pgrep loop, exit-code file wait, DROPPED/FLAKY/MERGED lines, failed tests at the base first). D1 A: tests for the new key in tests/test_agent_conf.py style. Join and fix rules (A21-A23) in W8, R7, S6, the merge skill and the dispatch skill. Old tests that pin a replaced line are changed only where they pin it (tests/test_agent_cleanup.py S6 phrase).
This task's own verify (the new way): tests/test_merge_train.py + the related tests (those that name the changed rules, skills, agent files or key) + the cheap checks. No full suite.

## E. To decide (defaults taken after 10 min only for D1-D3 wording; the gate itself waits)

| # | Question | Options | Recommendation |
|---|---|---|---|
| D1 | The train's longest wait needs a number; the rules say every number is a setting | A: new setting `train_wait_min=60` (small code in bin/agent_conf.py, the template and this repo's agent.conf; one worker). B: no cap, wait only while another task is at verify, push or report | A |
| D2 | A level 4 branch (here 4 of 19 tasks) | A: rides in a train, at most one, merged last (its rollback = one merge commit, no extra suite). B: always a train of one (one more 40 min suite each) | A |
| D3 | The brief says "foreground suite", but one Bash call stops at 10 min and the pc2 suite takes 40 min | A: foreground when it fits, else background + wait for its exit-code file in foreground calls of at most 9 min, never pgrep. B: split the suite into parts under 10 min (repo specific) | A |
