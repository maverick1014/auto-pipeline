---
name: close-case
description: Main manager only. On a CLOSE CASE report from a task manager decide finish first or close now; when the human says close case, the whole repo wraps up.
---
# /close-case — settle a case, or wrap up the whole repo (PRINCIPLES.md W13)

## A. One CLOSE CASE report

1. `finished` → run `/merge`.
2. `unfinished` → review it against the requirement doc, then decide:
   - **finish first** → `SendMessage` it: go on to DONE, then report `DONE PASS <name>` as usual; later `/merge`.
   - **close now** → keep the pushed branch, never delete it.
     - Close its pane (orca only): `${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh close <terminal handle>`.
     - Remove the worktree: orca → `orca worktree rm --worktree path:<worktree path> --json`; plain → `git worktree remove <worktree path>`, then `git worktree prune`.
     - `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree rm "<worktree path>"`.
     - Keep the todo line open with the next steps: `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add "<name>" big "<what>; next: <next steps>; branch <branch>" <est_minutes>` (todo add replaces the line; never put " | " inside the text).
3. Log the decision in your `agent_state.txt` (date, name, decision, why). Human away → decide by the requirement doc, add "owner not seen".

## B. The human says close case (whole repo)

1. Read `agent_worktree.txt`. Send the words close case to every live task manager and human-direct session: `SendMessage`, or type it into its pane, `orca terminal send --terminal <handle> --text "close case" --enter`. A session on another machine: tell the human it must be read in its own terminal.
2. Hold new dispatches. Collect every CLOSE CASE report, wait max 30 min each, then record it "no report".
3. Apply part A to each report. Merge what passes with `/merge`.
4. Close every pane and worktree left. Stop the crons you started: `CronList` then `CronDelete` each. Stop the monitor: `${CLAUDE_PLUGIN_ROOT}/bin/agent-monitor.sh stop`. Then `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh show` to check the agent files.
5. Then ONE final table to the human: task · result · what changed · what is left · decisions taken for the human. Every task one row, nothing dropped.
