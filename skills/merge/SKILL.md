---
name: merge
description: Main manager only. After a task manager reports DONE PASS, run the browser E2E, then send the merge deputy to merge, push, delete the branch, close the terminal, remove the worktree, update the agent files. Use when a feature is done.
---
# /merge — finish one feature (PRINCIPLES.md W5, W8)

1. Read the task manager's done report. No click path → bounce it: "no E2E script, not done".
2. Ask `${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh browser` first: chrome, headless or none.
   - **chrome** — run the click path yourself in Claude in Chrome (W5). Every step must match. A miss → send the evidence back to the task manager, stop here.
   - **headless** — cloud only, the extension can never reach a VM. Run the same click path with Playwright against the dev server, and save one screenshot per step as evidence. Same rule: a miss → send the evidence back to the task manager, stop here.
   - **none** — no browser at all. Print the click path under the heading NEEDS HUMAN E2E and stop. Do not merge, do not pass, and never call a path "verified" when nobody drove it. Wait for the human to sign it off.
3. Stop the app server, close whatever ran the click path: the tab, the headless Playwright browser, or nothing if the answer was none.
4. `Agent` with `subagent_type: merge-deputy`. Brief, all five values:
   ```
   name: <name>
   branch: <branch>
   worktree path: <path>
   terminal handle: <term_...>   (orca only, leave empty in plain and cloud)
   suite command: <exact command>
   ```
5. On `MERGE PASS`: `git log --oneline -2`, `git worktree list`, `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh show`. All clean → report to the human in H3 shape.
6. On `MERGE FAIL`: report the first line to the human with the deputy's evidence. Do not retry on your own.
