---
name: close-case
description: Run when the human or the main manager says close case. Task manager or human-direct session - settle down and send the CLOSE CASE report. Main manager - decide on a CLOSE CASE report (finish first or close now), or wrap up the whole repo.
---
# /close-case — settle a case, or wrap up the whole repo (PRINCIPLES.md W13)

`[<model> <effort>]` = yours, from the `YOU:` line of your start text.

Pick your part: task manager or human-direct session (a `<name> Task Manager` or `<repo> Helper`) -> part C. Main manager -> parts A and B. A spawned worker, deputy or reviewer never runs this. Only a mention of the words (a brief, a quote)? Do nothing. The upper decision on your report (finish first, close now)? Follow it.

## A. One CLOSE CASE report

The report's TIME line keeps work and wait apart: est, actual (agent work only), wait. Missing → ask for it once.

1. `finished` → run `/merge`.
2. `unfinished` → review it against the requirement doc, then decide:
   - **finish first** → `SendMessage` it, text starting `[<model> <effort>]`: go on to DONE, then report `DONE PASS <name>` as usual; later `/merge`.
   - **close now** → keep the pushed branch, never delete it.
     - Close its pane (orca only): `${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh close <terminal handle>`.
     - Remove the worktree: orca → `orca worktree rm --worktree path:<worktree path> --json`; plain → `git worktree remove <worktree path>`, then `git worktree prune`.
     - `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree rm "<worktree path>"`.
     - Keep the todo line open with the next steps and the time so far: `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add "<name>" big "<what>; next: <next steps>; branch <branch>; work so far <n>m, wait <n>m" <est_minutes>` (todo add replaces the line; never put " | " inside the text).
3. Log the decision in your `agent_state.txt` (date, name, decision, why). Human away → decide by the requirement doc, add "owner not seen".

## C. Task manager or human-direct session: settle down

1. Start nothing new. Running workers finish their slice or stop cleanly.
2. Save `agent_state.txt`. Commit + push the branch, a WIP commit if unfinished. Never lose work.
3. Report to the upper level: the main manager `<repo> Manager` (not listed: the `<repo>-<xx>` row) with `SendMessage` (another machine: print it in this terminal and say so). No live main manager: print the report here, the human decides. First line `CLOSE CASE <name>: finished` or `CLOSE CASE <name>: unfinished`. Then: what is done, what is left + next steps, tests run + results, E2E click path, new ideas, `TIME: est <n>m, actual <n>m, wait <n>m`.
4. Wait for the decision: finish first, or close now. Never close yourself.

## B. The human says close case (whole repo)

1. Read `agent_worktree.txt`. Send the words `[<model> <effort>] close case: run /auto-pipeline:close-case, part C` to every live task manager (`<name> Task Manager`) and human-direct session (`<repo> Helper - <Task Name>`, or `<repo> Helper`, or its `<repo>-<xx>` row): `SendMessage`, or type it into its pane, `orca terminal send --terminal <handle> --text "[<model> <effort>] close case: run /auto-pipeline:close-case, part C" --enter`. A session on another machine: tell the human it must be read in its own terminal.
2. Hold new dispatches. Collect every CLOSE CASE report, wait max 30 min each, then record it "no report".
3. Apply part A to each report. Merge what passes with `/merge`.
4. Close every pane and worktree left. Stop the crons you started: `CronList` then `CronDelete` each. Then `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh show` to check the agent files.
5. Then ONE final table to the human: task · result · what changed · what is left · decisions taken for the human. Every task one row, nothing dropped.
6. Under the final table, ask the human in his language: clean this session for the next round, yes or no? No, or no answer: nothing changes.
7. Yes → `${CLAUDE_PLUGIN_ROOT}/bin/agent-start.sh --clean "<open decision for the owner>" ...` (one argument per carry line). It checks first: LEFT RUNNING → stop it, run `--clean` again. Then do its NEXT line as your last action, nothing after it (orca: it types /clear into your own pane; plain, cloud: the human types /clear). Same lock, same name: you stay the main manager.
8. The other choice, rare: the human types a line that makes this session stop being main manager; never run it yourself. Get the line with `${CLAUDE_PLUGIN_ROOT}/bin/agent-close-case.sh --release-line` (the hook script prints the path of the plugin installed now) and show it as printed.
