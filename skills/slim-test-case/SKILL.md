---
name: slim-test-case
description: Main manager only. Use when the tests of a repo have grown too many or too slow: measure, report the plan to the owner, then merge and speed them up without losing a check. The human may call /auto-pipeline:slim-test-case.
---
# /slim-test-case: fewer, faster tests in any repo

Main manager only. A task manager or Helper: refuse in one line, run nothing. Words to the human: the Language setting.

1. Measure (changes nothing). Save the test ids first: `${CLAUDE_PLUGIN_ROOT}/bin/agent_test_audit.py ids <tests dir> > before.txt` (`ids` lists Python unittest ids; for another runner save one id per line, `file::test`, from the runner's own list, e.g. `pytest --collect-only -q` or `jest --listTests`). Then run `${CLAUDE_PLUGIN_ROOT}/bin/agent_test_time.py --cmd "<the repo's one-file test command with {file}>" --files "<tests dir>/**/test_*.py" --out times.tsv`. It gives seconds and peak MB per test file. Report the slowest 20, how many files are named after a task instead of a module, and the checks repeated in several files.
2. Profile one slow file: where the time goes (program starts, set-up, waits, type checking). Name the share of each.
3. Report to the owner before changing anything: the findings table (file, seconds, peak MB, cause) and the plan (target files, what gets cheaper). Wait for the answer.
4. Merge, by module then feature (one file per module, one class per feature). Remove a test as a duplicate only with its twin: one row in the removed-checks table `| Old file::test | Why it is a duplicate | Twin file::test that still checks it |`. Make the slowest cheaper: shared set-up, fewer program starts, in-process calls where the start is most of the cost, a parallel runner that stays under 80% of the CPU cores and 80% of RAM.
5. Never weaken a check on money, permissions, migrations, secrets or rules. A second copy of the same check may go only with a twin that checks the same or more (one row in the table); every other check there moves unchanged.
6. Prove it. Save the new ids the same way (`ids <tests dir> > after.txt`, or the runner's list; the audit takes any such lists), then `${CLAUDE_PLUGIN_ROOT}/bin/agent_test_audit.py --before before.txt --after after.txt --table <table.md>` must say `AUDIT PASS` (moved + removed with twin = before). Run `agent_test_time.py` again and show before and after seconds per file and in total.
