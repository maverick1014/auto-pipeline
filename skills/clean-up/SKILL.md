---
name: clean-up
description: Main manager only. List rubbish docs, old state copies, finished mocks and outdated agent_* lines, then remove only the rows the human picks.
---
# /clean-up: rubbish files and outdated lines (requirements/clean-up.md)

Main manager only. A task manager or Helper: refuse in one line, run nothing.

Words to the human: the Language setting. Ids and commands stay as printed.

## Step 1: the table (changes nothing)

1. Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-cleanup.sh --files`.
2. Show the table as printed: every row, the kept rows and the notes. Never cut a row.
3. `nothing to clean` → say so, stop.
4. Then the decide section: remove which rows? all, some ids, or none. Say what each kind is (D doc, S state copy or monitor file, M mock, I idea line, T todo line, W worktree line), what goes with no copy (S untracked) and what is kept (files in git history, lines in a backup). End with your recommendation and why.

## Step 2: remove (only after the human's answer)

1. Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-cleanup.sh --files --yes <ids>`, or `--yes all`, or `--yes none`. Ids as printed, comma separated.
2. A line starting `REFUSED` (the table changed, or a merge is in progress) → nothing changed. Run step 1 again, show the new table, ask again.
3. A line starting `FAILED at` → show it as printed, with the ids removed before it. Do not retry by yourself.
4. Never run `--yes` without the human's answer in this session, and never from an earlier table.

## After

- Show the output lines (`removed:`, `backup:`, `commit`, the last line).
- Files went (a `commit` line) → push the branch the main checkout is on (`git branch --show-current`), or hand the owner one line: `! git push origin <that branch>`.
- Restore: tracked files `git revert <sha>`; lines from the backup file named in the `backup:` line.
