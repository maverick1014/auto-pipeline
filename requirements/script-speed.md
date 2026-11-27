# script-speed: the core scripts start fewer processes, with the same output

Owner, 2026-11-26: "full test is good. but then slow"; target of test-slim-3: the full run (python3 tests/run2.py, 6 processes) under 5 minutes on pc2 with the same checks. test-slim-3 reached 413 s with test-side work only and measured what is left: the scripts themselves (requirements/test-slim.md, "Follow-up: the scripts").

## Today (measured in the test-slim-3 AFTER run on pc2)

| Script (verb) | Calls | Seconds | s a call |
|---|---|---|---|
| agent-start.sh | 468 | 453 | 0.97 |
| agent-file.sh todo | 983 | 309 | 0.31 |
| agent-resume.sh | 79 | 61 | 0.77 |
| agent-file.sh tell | 31 | 51 | 1.65 |

- agent-start.sh: about 27 python3 and 35 git starts a call; `--answer` runs one shasum per question.
- agent-file.sh: a verb is bash plus 8-12 python3/git starts; `todo done` and agent-resume.sh run the cleanup sweep (0.3-0.45 s).
- agent-file.sh tell: the read-back loop waits up to 20 x 0.5 s when the block does not read back.

## The rule

1. agent-start.sh, agent-file.sh (todo verbs, tell) and agent-resume.sh do the same work with fewer process starts: one python3 process per call where today there are many, git asked once per value, one hash pass for all quiz answers.
2. Output, exit codes and every file they write stay exactly the same. Proof: a recorded set of calls (every verb, flag and exit code the tests use) run with the old and the new script on copies of the same state; outputs and files compared, only commit hashes, temp folder names and times normalised.
3. The tell read-back keeps today's wait for real use; tests may shorten it only through one documented setting whose default is today's value.
4. Targets, measured on pc2 with the same method as test-slim-3: agent-start.sh at most 0.5 s a call, agent-file.sh todo at most 0.2 s, agent-resume.sh at most 0.4 s; then one full run, wall time reported (projected about 350 s).
5. No test is weakened or removed; test files change only where a test pinned an internal detail that no longer exists (each such change listed with its reason).

## Examples (the failing tests come from these)

- The quiz: `--answer` with all keys right prints PASS with one hash pass; one wrong key prints the same failure text as today.
- `agent-start.sh` as main manager, task manager and second session in a fresh repo: the start text byte-equal to today's (after normalising).
- `todo add`, `todo stage`, `todo done`: same lines in agent_todo.txt and agent_completed.txt, same printed lines.
- `tell` when the block reads back at once: returns without waiting; when it never reads back: the same failure line after today's wait.
- A per-call timing test per script that fails when a call starts more processes than the new count (counted, not timed, so it never flakes).

## Not in this task

Spotlight on pc2. Test-side changes beyond rule 5. Other repos.

## Result (2026-11-27, task script-speed)

The way (main manager, 2026-11-27): no port to Python. The cheapest changes first (each value asked once, plain text work in bash builtins, back-to-back python3 calls merged into one), measured after each slice, stopped at the targets.

### Seconds a call (rule 4)

Same method as test-slim-3: the seconds of every ScriptRepo.run call (`AGENT_CALL_TIMES`) of 8 related test files (test_agent_start, _file, _resume, test_two_roots, test_agent_board, _checks, _cleanup, _watch), run2 -j 6, pc2, old and new back to back.

| Script (verb) | Calls | Before s a call | After s a call | Target |
|---|---|---|---|---|
| agent-start.sh | 390 | 0.934 | 0.358 | 0.5 |
| agent-file.sh todo | 482 | 0.247 | 0.137 | 0.2 |
| agent-resume.sh | 79 | 0.798 | 0.373 | 0.4 |
| agent-file.sh tell | 31 | 1.637 | 1.567 | none |
| agent-file.sh, other verbs | 221 | 0.167 | 0.107 | none |

The 8 files: 173 s -> 120 s wall. tell keeps its cost in the tests: the old tell tests wait today's read-back (rule 3: only a test that sets AGENT_TELL_READBACK_S is shorter; changing the old tests is outside rule 5, an idea).

Real use (a copy of the real agent files of pc2, 100 KB, 5 rounds, median, old -> new): agent-start.sh main manager 2.519 -> 0.918 s, task manager 0.546 -> 0.161, --answer 0.369 -> 0.096; agent-resume.sh 0.835 -> 0.386; todo add 0.165 -> 0.117, stage 0.208 -> 0.133, done 0.320 -> 0.169; state add 0.081 -> 0.066.

### Process starts (tests/test_script_speed.py, counted, never timed)

The caps are the reached counts: python3 exact, all starts + 2. Table in the test file's docstring. In short: agent-start.sh main manager 157 -> 43 starts (python3 27 -> 5), task manager 65 -> 11 (7 -> 1), second session 142 -> 23 (11 -> 1), --answer 115 -> 6 (shasum 15 -> one hashlib pass); agent-resume.sh 48 -> 17 (9 -> 3); todo add 19 -> 8 (2 -> 1), todo stage 31 -> 9 (3 -> 2), todo done with the sweep 167 -> 45 (15 -> 6); no git command line twice in any call (before: up to 6 repeats).

Not reached by cheap changes, and why: todo stage keeps 2 python3 (the board's p50 runs after the line is written; merging it means moving the stage write into Python); todo done keeps 6 (the sweep's one, agent_estimate.py retrain and measure, may-work, the task-end batch, the estimate settings). Both calls are under the time target.

### Same output (rule 2)

Proof: tests/scriptequiv.py, switched on by AGENT_EQUIV_OLD=<ref> in ScriptRepo.run (off by default, nothing runs when off). Every script call of the related tests runs first with the old ref's bin/ on a snapshot of the test's temp folder, then the folder is put back and the new script runs; exit code, stdout, stderr and every file compared, after normalising only commit hashes, clock times, pids, measured MB, time stamps in file names and temp names. Copies of the plugin's own bin/ files (fake plugin caches) are compared old-to-old and new-to-new; the detached estimate runner's files are skipped (a background process of the old run can still write after the snapshot is put back).

Run: AGENT_EQUIV_OLD=78b565f over the 50 related test files (the tool's RELATED TESTS list), about 3805 script calls compared, 773 s wall. 222 difference lines in 81 tests; the same 81 tests old against old (a frozen copy of 78b565f) give 204 of them: noise of two runs of one script (the city server of the first run still holds its port, the random token of a remote nightly, measured MB, the trim race tests). The 16 tests left were run again old against new and old against old with AGENT_EQUIV_SETTLE=3 (the background jobs a script starts are done before its files are read).

Result: 0 differences in the work the scripts do, after one defect was found and fixed: todo done stored clock and work one minute short (59 for 60) with a false "--work is more than the clock" warning, intermittently. The new cached epoch of NOW and a later parse of the opened time took different wall-clock seconds from macOS `date -j -f` (fix 10f0f17: to_epoch gives date the seconds; test TestClockMinutes, red on 8081332, green on 78b565f and 10f0f17). The differences that stay are listed below.

### Test files changed (rule 5)

| Test | Change | Reason |
|---|---|---|
| test_agent_city_server TestCliModel.test_one_place | asserts agent-resume.sh hands the spec to agent_nightly.py resume-prep (--model) and resume-prep asks agent_conf.cli_model; no family list in either | the call moved from agent-resume.sh's own python3 start into its one resume-prep start; same rule, one copy |
| tests/scripthelp.py | two hooks in ScriptRepo.run (AGENT_EQUIV_OLD, AGENT_CALL_TIMES), off by default | the proof and the measure |
| new: tests/test_script_speed.py, tests/proccount.py, tests/scriptequiv.py | the count tests, the counting wrappers, the equivalence check | rules 2, 3, 4 |

No test removed or weakened.

### Known differences

| Where | Old | New | Why it stays |
|---|---|---|---|
| agent-file.sh tell, AGENT_TELL_READBACK_S set (tests only) | 20 reads | N / 0.5 reads | rule 3, the setting; unset (real use) the same 20 x 0.5 s |
| agent-resume.sh (and the start that runs it) when `orca worktree ps --json` is not JSON | exit 1, a Python traceback through "<string>" | exit 1, a traceback through agent_nightly.py | the error path's trace names the file the parse now lives in; no designed line changes |
| agent-runtime.sh, the orca probe cut off after 3 s | bash's job-control line "line 65: <pid> Terminated: 15 ..." on stderr | no such line | the probe no longer polls a background job; the line held only a pid |
| agent-start.sh, main manager with a due nightly | "CLEANUP: ... kept 1" or "kept 0" | the same two | a race already in today's code: the background nightly start makes its scratch worktree before or after the sweep lists worktrees (same order of steps old and new; the new start reaches the sweep sooner) |

Kept on purpose, byte-equal: agent-roots.sh cuts a main worktree path at its first blank (today's awk); agent-start.sh --take-over prints "keep_worktree_copy: command not found" (line 89) on stderr. Both are old bugs, in agent_ideas.txt.
