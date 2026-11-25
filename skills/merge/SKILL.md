---
name: merge
description: Main manager only. After a task manager reports DONE PASS, run the browser E2E, then send the merge deputy to merge, push, delete the branch, close the terminal, remove the worktree, update the agent files. Use when a feature is done.
---
# /merge — finish one feature (PRINCIPLES.md W5, W8)

0. A CLOSE CASE report instead of DONE PASS? → run `/close-case` first. Finished → it sends you back here to continue. Unfinished → it decides finish first or close now.

1. Read the task manager's done report. No click path → bounce it: "no E2E script, not done". No TIME line with work and wait apart, or no FACTS line → bounce it: "no TIME, not done".
   Then, in the task's worktree, before any E2E: `${CLAUDE_PLUGIN_ROOT}/bin/agent-level.sh check --base origin/main --declared <type of the todo line>` (R8). It prints REQUIRED TYPE per file and per part. RAISE (exit 1, a C or D file above the declared type) → `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo level "<name>" <A-D>`, bounce to the task manager, check that part by the higher type. A type only goes up.
   Check each part by its own type (R8), never the whole task by the highest. Type A: skip the E2E (steps 2 and 3), read the diff and approve, then go on at step 4. Type B: Chrome compare with the approved mock at desktop and phone width, console clean, owner OK. Type C: one browser flow. Type D: owner signs before merge.
2. First run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" e2e`. Ask `${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh browser`: chrome, headless or none.
   - **chrome** — run the click path yourself in Claude in Chrome (W5). Every step must match. A miss → send the evidence back to the task manager, stop here.
   - **headless** — cloud only, the extension can never reach a VM. Run the same click path with Playwright against the dev server, and save one screenshot per step as evidence. Same rule: a miss → send the evidence back to the task manager, stop here.
   - **none** — no browser at all. Print the click path under the heading NEEDS HUMAN E2E and stop. Do not merge, do not pass, and never call a path "verified" when nobody drove it. Wait for the human to sign it off.
3. Stop the app server, close whatever ran the click path: the tab, the headless Playwright browser, or nothing if the answer was none.
4. Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" merge`, then `Agent` with `subagent_type: merge-deputy`, description `<name> Merge`. Brief, all values:
   ```
   [<model> <effort>]   (yours, from the YOU: line of your start text)
   name: <name>
   level: <A-D>
   branch: <branch>
   worktree path: <path>
   terminal handle: <term_...>   (orca only, leave empty in plain and cloud)
   suite command: <exact command>
   todo done arguments: --work <actual> --wait <wait> --bounces <n> --workers <n> --mock <yes|no> --lane full --type <t> --tests <n> --adds <n>
   ```
   The numbers come from the report's TIME and FACTS lines (actual = agent work only). A number you do not know → leave that option out, never guess.
   The guard (`bin/agent-guard.sh`) records the merge deputy under the task and, only with the "Rules: Todo before agent" setting on, refuses it when the task line is no longer open, so the todo line stays open until the deputy's own `todo done`.
5. On `MERGE PASS`: `git log --oneline -2`, `git worktree list`, `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh show`. All clean → report to the human in H3 shape.
   The merged task leaves `agent-watch.sh --all` by itself (its worktree line goes); no watch to stop.
6. On `MERGE FAIL`: report the first line to the human with the deputy's evidence. Do not retry on your own.
7. Merged a fix early, while its branch is still running? → `SendMessage` that task manager at once: merge main back into your branch. Never cherry-pick slices; merge the branch (or its prefix).
8. Every release bumps `version` in `.claude-plugin/plugin.json`; users get nothing without it (no update notice, no auto update).
   Only in the auto-pipeline repo (the one with `bin/agent-release.sh`): after the version bump is committed on main, run `bin/agent-release.sh --push` before main is pushed, because users install the `release` branch (the ship set only), not main, and a main pushed first points users at a release that does not exist yet.
