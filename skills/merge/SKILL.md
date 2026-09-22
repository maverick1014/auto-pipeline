---
name: merge
description: Main manager only. After a task manager reports DONE PASS, run the browser E2E, then send the merge deputy to merge, push, delete the branch, close the terminal, remove the worktree, update the agent files. Use when a feature is done.
---
# /merge — finish one feature (PRINCIPLES.md W5, W8)

1. Read the task manager's done report. No click path → bounce it: "no E2E script, not done".
2. Run the click path yourself in Claude in Chrome (W5). Every step must match. A miss → send the evidence back to the task manager, stop here.
3. Stop the app server, close the tab.
4. `Agent` with `subagent_type: merge-deputy`. Brief, all six values:
   ```
   name: <name>
   branch: <branch>
   worktree path: <path>
   terminal handle: <term_...>
   suite command: <exact command>
   result text: <one line, e.g. "63 tests OK, E2E pass in Chrome">
   ```
5. On `MERGE PASS`: `git log --oneline -2`, `git worktree list`, `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh show`. All clean → report to the human in H3 shape.
6. On `MERGE FAIL`: report the first line to the human with the deputy's evidence. Do not retry on your own.
