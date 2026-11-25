---
name: merge
description: Main manager only. After a task manager reports DONE PASS, run the browser E2E, then send the merge deputy to merge, push, delete the branch, close the terminal, remove the worktree, update the agent files. Use when a feature is done.
---
# /merge — finish one feature (PRINCIPLES.md W5, W8)

0. A CLOSE CASE report instead of DONE PASS? → run `/close-case` first. Finished → it sends you back here to continue. Unfinished → it decides finish first or close now.

1. Read the task manager's done report. No click path → bounce it: "no E2E script, not done". No TIME line with work and wait apart, or no FACTS line → bounce it: "no TIME, not done".
   Then, in the task's worktree: `${CLAUDE_PLUGIN_ROOT}/bin/agent-level.sh check --base origin/main` (R8). It prints the blocks the real diff triggers. The task manager's pass lines (`agent-file.sh check`) cover them; a tool block with no pass line → bounce it.
2. First run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" e2e`. DIFF READ, FLOW CHECK and UI CHECK of the task go to a check deputy, one at a time on the browser: `Agent` with `subagent_type: check-deputy`, description `<name> Check`, brief `[<model> <effort>]` first, then the task, the block, the worktree path, the click path or the approved mock. It writes its pass or fail line with `agent-file.sh check` and reports CHECK PASS or CHECK FAIL: its verdict is evidence, you decide. A fail → send the evidence back to the task manager, stop here. Ask `${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh browser` first:
   - **chrome** — the check deputy drives Claude in Chrome (W5). Every step must match.
   - **headless** — cloud only, the extension can never reach a VM. Run the same click path with Playwright against the dev server, and save one screenshot per step as evidence. Same rule: a miss → send the evidence back to the task manager, stop here.
   - **none** — no browser at all. Print the click path under the heading NEEDS HUMAN E2E and stop. Do not merge, do not pass, and never call a path "verified" when nobody drove it. Wait for the human to sign it off.
3. Stop the app server, close whatever ran the click path: the tab, the headless Playwright browser, or nothing if the answer was none. A block that needs the owner's sign (OWNER SIGN of R8) waits for his yes.
4. Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" merge`, then the gate: `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh checks gate "<name>" --dir <worktree path>`. The task's worktree is gone (W8): gate on a scratch copy of the pushed branch (`git worktree add --detach <scratch> origin/<branch>`, removed after) with `--dir <scratch>`; the gate reads the lines gathered into main by `checks gather`. `GATE REFUSED` → no merge: bounce the task with the missing blocks. A remote task (machine not empty): first save the CHECK lines of its REPORT to a file and give the gate `--results <file>`. `GATE PASS` → `Agent` with `subagent_type: merge-deputy`, description `<name> Merge`. Brief, all values:
   ```
   [<model> <effort>]   (yours, from the YOU: line of your start text)
   name: <name>
   session: <task manager | helper>
   machine: <the Orca environment name, empty when the worktree is on this machine>
   branch: <branch>
   worktree path: <path>
   results file: <path>   (remote task only: the CHECK lines of its REPORT, for the gate's `--results`; else leave empty)
   terminal handle: <term_...>   (orca only, leave empty in plain and cloud)
   suite command: <exact command>
   todo done arguments: --work <actual> --wait <wait> --bounces <n> --workers <n> --mock <yes|no> --lane full --type <t> --tests <n> --adds <n>
   ```
   The numbers come from the report's TIME and FACTS lines (actual = agent work only). A number you do not know → leave that option out, never guess.
   The guard (`bin/agent-guard.sh`) records the merge deputy under the task and, only with the "Rules: Todo before agent" setting on, refuses it when the task line is no longer open, so the todo line stays open until the deputy's own `todo done`.
5. On `MERGE PASS`: `git log --oneline -2`, `git worktree list`, `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh show`. All clean → report to the human in H3 shape.
   The merged task leaves `agent-watch.sh --all` by itself (its worktree line goes); no watch to stop.
   Then run `${CLAUDE_PLUGIN_ROOT}/bin/agent-cleanup.sh --apply` (the sweep after every merge, W8).
6. On `MERGE FAIL`: report the first line to the human with the deputy's evidence. Do not retry on your own.
7. Merged a fix early, while its branch is still running? → `SendMessage` that task manager at once: merge main back into your branch. Never cherry-pick slices; merge the branch (or its prefix).
8. Every release bumps `version` in `.claude-plugin/plugin.json`; users get nothing without it (no update notice, no auto update).
   Only in the auto-pipeline repo (the one with `bin/agent-release.sh`): after the version bump is committed on main, run `bin/agent-nightly.sh --release-ok` first (exit 1 → `bin/agent-nightly.sh --start` in the background, release after it is green; no other pre-release run), then run `bin/agent-release.sh --push` before main is pushed, because users install the `release` branch (the ship set only), not main, and a main pushed first points users at a release that does not exist yet.
