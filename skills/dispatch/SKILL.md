---
name: dispatch
description: Main manager only. Route a new task by W9, open a worktree by W7 when needed, launch the task manager and send its brief. Use when the human gives a task.
---
# /dispatch — route one task (PRINCIPLES.md W9, W7)

Run these in order. First match wins.

1. `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh show`, `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh time`, and the RESOURCES line. Estimate the task in minutes of agent work only; the waits (mock gate, owner question or review, hold, suite slot) are not in it. Then run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh estimate --type <t> --lane fast|full --mock yes|no "<one line what>"` (only facts known before dispatch). Its minutes go on the todo line as est. Its range and its `like` lines (the 3 nearest past tasks) are the reason you give. It says `rubric`: the rubric won its backtest (or no version is trained yet), so its numbers are the rubric row.

Touches another repo? → W12: keep your part, send the peer main manager the cross-repo brief below, called side first, hold your todo line until its DONE PASS.

2. Small task (fast lane, R1)? → `Agent` with `subagent_type: fast-lane-deputy`, description `<task> Deputy`. Brief: the task, the file(s), the one test if any. Done. After its DONE PASS: `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo done "<name>" --lane fast --work <m> --type <t>`.
3. Touches a live worktree's module? → `SendMessage` the task to that task manager. Status `final` → hold it, tell the human.
4. Big, and a live task manager has capacity? → `SendMessage` it to that task manager.
5. Idle or done worktrees in `agent_worktree.txt`? → run `/merge` for each first.
6. RESOURCES over cap, or spawned agents at `max_agents`? → wait, tell the human.
7. Otherwise, ask `${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh kind` first: orca, plain or cloud.
   ```
   ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add "<name>" big "<one line what>" <est_minutes>
   ```
   **orca** — open a worktree. Read `<model>` and `<effort>` from `task_manager` in the project's `agent.conf` (form model:effort) and `<mode>` from `permission_mode`:
   ```
   orca worktree create --name <name> --repo path:<main repo> --base-branch main --no-parent --json
   orca terminal create --worktree path:<worktree path> --title "<name> Task Manager" --command "AGENT_ROLE=task-manager claude --name '<name> Task Manager' --model <model> --effort <effort> --permission-mode <mode>" --json
   orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 90000 --json
   ```
   A new pane stops at a menu (trust prompt)? `orca terminal send` has no key flag: send the raw key as text, then Enter, e.g. Down: `orca terminal send --terminal <handle> --text $'\x1b[B' --enter`.
   Then `ListAgents`, find `<name> Task Manager`, `SendMessage` it the brief below. Keep the terminal handle for `/merge`.

   **plain or cloud** — no terminal can be opened here, so no worktree either. The main manager does the task itself, from the session it is already in, with `Agent` subagents (`subagent_type: worker`, description `<name> Worker <n>: <slice>`), up to `max_agents` at a time. Use the task manager brief below as its own task list and run the steps in order.

8. Early merge: a fix from a still-running branch merged into main → at once `SendMessage` that task manager: merge main back into your branch now. Never cherry-pick slices; merge the branch (or its prefix) — cherry-picks cost a conflict round at the final merge.

## Time question from the human

The human asks how long a task takes or when it is done (a time question) → run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh eta "<name>" --step <n> --work-so-far <m> [--wait <m>]`. Step and work come from the last HEARTBEAT; `--wait` = known waiting still ahead.
Answer with its line: a duration AND a clock time, and when he is needed next. Never "soon".

## Task manager brief (fill the <>)

```
Brief from the main manager (<my session name>): you are the task manager for "<name>".
WHERE: worktree <worktree path>, branch <branch>. Main repo <main repo> only for ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh.
FEATURE: <requirement, 5 to 10 lines. Files to produce. What the user sees. Validation rules.>
STEPS: 0 save this whole brief into agent_state.txt in your worktree, first action (S8)
 1 register: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree set "<worktree path>" "<name>" working
 2 mock first if UI (W2): commit mock/<name>-mock.html, send me the path, STOP until "mock yes"
 3 write the failing tests yourself (W3), commit
 4 workers: Agent subagent_type worker, description "<name> Worker <n>: <slice>", max 2 at once, each gets named files + one test command (W4). Check RESOURCES before each spawn (S3, S4)
 5 verify every worker result yourself. Full suite once. Defect → back to the worker with evidence. Set status final: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree set "<worktree path>" "<name>" final
 6 commit, git push -u origin <branch>
 7 report done, set status done, stay idle
REPORT: SendMessage to "<my session name>". First line "DONE PASS <name>" or "DONE FAIL <name>: <why>". Then Result (test count), What changed (files), What to decide. Then the E2E click path: start command, URL, exact clicks, expected result, how to restore. Then one line: TIME: est <n>m, actual <n>m, wait <n>m (actual = agent work only; wait = mock gate, owner question or review, hold, suite slot). Then one line: FACTS: type <page|server|script|docs|cloud|app|data|mixed>, lane full, mock <yes|no>, bounces <n>, workers <n>, tests <n added>, scope adds <n>.
ASK: first line "QUESTION:". Wait max 10 min, then default + log + continue (W1). Mock gate always waits.
HEARTBEAT: every 15 min, one line "HEARTBEAT <name>: step <n> of 7, work <m>m, <what runs now>".
CLOSE: on "close case" from me or the human: start nothing new, commit + push (WIP if unfinished), report first line "CLOSE CASE <name>: finished" or "CLOSE CASE <name>: unfinished", then done, left + next steps, tests, click path, ideas, TIME. Wait for my decision; never close yourself.
STATE: write agent_state.txt after every step (S7, S8).
NEVER: Claude in Chrome (W5). Product code. Full suite twice (W4). Files outside the worktree except via ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh.
```

## Cross-repo brief (W12, fill the <>)

```
CROSS-REPO TASK <name> from <repo>
WHAT: <requirement, 5 lines max. What the peer repo must build or change.>
CONTRACT NEEDED: <what the sender must get back: endpoint, fields, errors>
REPORT: SendMessage to "<sender session name>". First line "DONE PASS <name>" or "DONE FAIL <name>: <why>". Then the contract.
ASK: first line "QUESTION:". Wait max 10 min, then default + log + continue (W1).
HEARTBEAT: every 15 min, one line "HEARTBEAT <name>: <what runs now>".
```
