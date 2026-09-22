---
name: dispatch
description: Main manager only. Route a new task by W9, open a worktree by W7 when needed, launch the task manager and send its brief. Use when the human gives a task.
---
# /dispatch — route one task (PRINCIPLES.md W9, W7)

Run these in order. First match wins.

1. `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh show`, `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh time`, and the RESOURCES line. Estimate the task in minutes with this rubric, adjusted by the last ratios: fast lane 5 to 15; one script with tests 45 to 60; feature with a mock gate 60 to 90; moves and multi-script 90 to 120. Bounces add 20 to 40 percent.
2. Small task (fast lane, R1)? → `Agent` with `subagent_type: fast-lane-deputy`. Brief: the task, the file(s), the one test if any. Done.
3. Touches a live worktree's module? → `SendMessage` the task to that task manager. Status `final` → hold it, tell the human.
4. Big, and a live task manager has capacity? → `SendMessage` it to that task manager.
5. Idle or done worktrees in `agent_worktree.txt`? → run `/merge` for each first.
6. RESOURCES over cap, or spawned agents at `max_agents`? → wait, tell the human.
7. Otherwise open a worktree. Read `<model>` and `<effort>` from `task_manager` in the project's `agent.conf` (form model:effort) and `<mode>` from `permission_mode`:
   ```
   ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add "<name>" big "<one line what>" <est_minutes>
   orca worktree create --name <name> --repo path:<main repo> --base-branch main --no-parent --json
   orca terminal create --worktree path:<worktree path> --title "TM <name>" --command "AGENT_ROLE=task-manager claude --model <model> --effort <effort> --permission-mode <mode>" --json
   orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 90000 --json
   ```
   Then `ListAgents`, find the new session, `SendMessage` it the brief below. Keep the terminal handle for `/merge`.

## Task manager brief (fill the <>)

```
Brief from the main manager (<my session name>): you are the task manager for "<name>".
WHERE: worktree <worktree path>, branch <branch>. Main repo <main repo> only for ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh.
FEATURE: <requirement, 5 to 10 lines. Files to produce. What the user sees. Validation rules.>
STEPS: 0 save this whole brief into agent_state.txt in your worktree, first action (S8)
 1 register: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree set "<worktree path>" "<name>" working
 2 mock first if UI (W2): commit mock/<name>-mock.html, send me the path, STOP until "mock yes"
 3 write the failing tests yourself (W3), commit
 4 workers: Agent subagent_type worker, max 2 at once, each gets named files + one test command (W4). Check RESOURCES before each spawn (S3, S4)
 5 verify every worker result yourself. Full suite once. Defect → back to the worker with evidence. Set status final: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree set "<worktree path>" "<name>" final
 6 commit, git push -u origin <branch>
 7 report done, set status done, stay idle
REPORT: SendMessage to "<my session name>". First line "DONE PASS <name>" or "DONE FAIL <name>: <why>". Then Result (test count), What changed (files), What to decide. Then the E2E click path: start command, URL, exact clicks, expected result, how to restore. Then one line: TIME: est <n>m, actual <n>m, human <n>m (human = minutes the owner had to be present).
ASK: first line "QUESTION:". Wait max 10 min, then default + log + continue (W1). Mock gate always waits.
HEARTBEAT: every 15 min, one line "HEARTBEAT <name>: step <n> of 7, <what runs now>".
STATE: write agent_state.txt after every step (S7, S8).
NEVER: Claude in Chrome (W5). Product code. Full suite twice (W4). Files outside the worktree except via ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh.
```
