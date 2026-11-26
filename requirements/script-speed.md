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
