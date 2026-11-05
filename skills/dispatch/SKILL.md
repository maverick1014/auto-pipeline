---
name: dispatch
description: Main manager only. Route a new task by W9, open a worktree by W7 when needed, launch the task manager and send its brief. Use when the human gives a task.
---
# /dispatch — route one task (PRINCIPLES.md W9, W7)

Run these in order. First match wins.

Every order you send another agent (brief, task, decision) starts with `[<model> <effort>]`: your own, from the `YOU:` line of your start text (PRINCIPLES.md W17).

1. `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh show`, `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh time`, and the RESOURCES line. Estimate the task in minutes of agent work only; the waits (mock gate, owner question or review, hold, suite slot) are not in it. Then run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh estimate --type <t> --lane fast|full --mock yes|no "<one line what>"` (only facts known before dispatch). Its minutes go on the todo line as est. Its range and its `like` lines (the 3 nearest past tasks) are the reason you give. It says `rubric`: the rubric won its backtest (or no version is trained yet), so its numbers are the rubric row.

Touches another repo? → W12: keep your part, send the peer main manager the cross-repo brief below, called side first, hold your todo line until its DONE PASS.

2. Small task (fast lane, R1)? → `Agent` with `subagent_type: fast-lane-deputy`, description `<task> Deputy`. Brief: `[<model> <effort>]` first, then the task, the file(s), the one test if any. Done. After its DONE PASS: `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo done "<name>" --lane fast --work <m> --type <t>`.
3. Touches a live worktree's module? → `SendMessage` the task to that task manager. Status `final` → hold it, tell the human.
4. Big, and a live task manager has capacity? → `SendMessage` it to that task manager.
5. Idle or done worktrees in `agent_worktree.txt`? → run `/merge` for each first.
6. RESOURCES over cap, or agents in state working or permission at `max_agents` (done or idle panes do not count)? → wait, tell the human.
7. Otherwise, ask `${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh kind` first: orca, plain or cloud.
   ```
   ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add "<name>" big "<one line what>" <est_minutes>
   ```
   Once the worktree path is known (the board reads it), record where it runs:
   ```
   ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo where "<name>" <machine> "<worktree path>"
   ```
   **orca** — open a worktree. Read `task_manager` in the project's `agent.conf` (form model:effort): `<model>` is what `${CLAUDE_PLUGIN_ROOT}/bin/agent_conf.py cli-model <task_manager value>` prints (the CLI refuses opus-5.5, takes opus), `<effort>` is the part after the colon. Read `<mode>` from `permission_mode`, read with `${CLAUDE_PLUGIN_ROOT}/bin/agent-settings.sh get permission_mode` (its first word; this machine's ~/.claude/auto-pipeline.conf wins over agent.conf):
   ```
   orca worktree create --name <name> --repo path:<main repo> --base-branch main --no-parent --json
   orca terminal create --worktree path:<worktree path> --title "<name> Task Manager" --command "AGENT_ROLE=task-manager claude --name '<name> Task Manager' --model '<model>' --effort <effort> --permission-mode <mode>" --json
   orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 90000 --json
   ```
   A new pane stops at a menu (trust prompt)? `orca terminal send` has no key flag: send the raw key as text, then Enter, e.g. Down: `orca terminal send --terminal <handle> --text $'\x1b[B' --enter`.
   Then start the watch with Bash `run_in_background`:
   ```
   ${CLAUDE_PLUGIN_ROOT}/bin/agent-watch.sh --terminal <handle> --worktree "<worktree path>" --name <name>
   ```
   Task manager on another machine: add `--environment <env> --shell <shell handle>` (a plain shell pane on that machine; the script sends only a short read command into it, never anything into the task manager's pane).
   It exits on WATCH SIGNAL (a DONE PASS, DONE FAIL, CLOSE CASE, QUESTION: or MOCK READY line in agent_state.txt), WATCH STALL, WATCH LOST or WATCH MAX. Handle it, then start it again, until the task is merged.
   Then `ListAgents`, find `<name> Task Manager`, `SendMessage` it the brief below. Keep the terminal handle for `/merge`.

   **plain or cloud** — no terminal can be opened here, so no worktree either. The main manager does the task itself, from the session it is already in, with `Agent` subagents (`subagent_type: worker`, description `<name> Worker <n>: <slice>`), up to `max_agents` at a time. Use the task manager brief below as its own task list and run the steps in order.

8. Early merge: a fix from a still-running branch merged into main → at once `SendMessage` that task manager: merge main back into your branch now. Never cherry-pick slices; merge the branch (or its prefix) — cherry-picks cost a conflict round at the final merge.

## Board records

The board (PRINCIPLES.md W14) reads these. Write each as it happens, never later from memory:
- Each wait gets `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo wait "<name>" on mock|question|review|hold|queue ["<note>"]` when it starts and `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo wait "<name>" off` when it ends
- Mock sent -> on mock; mock yes -> off
- Owner question -> on question; answered -> off
- DONE PASS waiting for the owner -> on review; he decides -> off
- Held -> on hold; released -> off
- Waiting for a slot -> on queue; slot found -> off
- Parked question for later (H1): `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh park add "<question>"`

## Time question from the human

The human asks how long a task takes or when it is done (a time question) → run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh eta "<name>" --step <n> --work-so-far <m> [--wait <m>]`. Step and work come from the last HEARTBEAT; `--wait` = known waiting still ahead.
Answer with its line: a duration AND a clock time, and when he is needed next. Never "soon".

## Task manager brief (fill the <>)

```
[<model> <effort>] Brief from the main manager (<my session name>): you are the task manager for "<name>".
WHERE: worktree <worktree path>, branch <branch>. Main repo <main repo> only for ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh.
TODO LINE: <the todo line, as agent-file.sh show prints it>
FEATURE: <requirement, 5 to 10 lines. Files to produce. What the user sees. Validation rules.>
STEPS: 0 save this whole brief into agent_state.txt in your worktree, first action (S8)
 1 register: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree set "<worktree path>" "<name>" working
 2 mock first if UI (W2): commit mock/<name>-mock.html, send me the path, STOP until "mock yes"; on another machine also append one line "MOCK READY <name>: <mock path>" to agent_state.txt in your worktree
 3 write the failing tests yourself (W3), commit
 4 workers: Agent subagent_type worker, description "<name> Worker <n>: <slice>", max 2 at once, each gets named files + one test command (W4); every worker brief starts with your own `[<model> <effort>]`. Check RESOURCES before each spawn (S3, S4). Record each worker: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worker on <n> "<slice>" when it starts, ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worker off <n> when it ends
 5 verify every worker result yourself. Full suite once. Defect → back to the worker with evidence. Set status final: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree set "<worktree path>" "<name>" final
 6 commit, git push -u origin <branch>
 7 report done, set status done, stay idle
REPORT: SendMessage to "<my session name>"; on another machine also append the same report to agent_state.txt in your worktree under "=== REPORT ===". First line "DONE PASS <name>" or "DONE FAIL <name>: <why>". Then Result (test count), What changed (files), What to decide. Then the E2E click path: start command, URL, exact clicks, expected result, how to restore. Then one line: TIME: est <n>m, actual <n>m, wait <n>m (actual = agent work only; wait = mock gate, owner question or review, hold, suite slot). Then one line: FACTS: type <page|server|script|docs|cloud|app|data|mixed>, lane full, mock <yes|no>, bounces <n>, workers <n>, tests <n added>, scope adds <n>.
ASK: first line "QUESTION:". Wait max 10 min, then default + log + continue (W1). Mock gate always waits. A question for later: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh park add "<question>"
HEARTBEAT: every 15 min, one line "HEARTBEAT <name>: step <n> of 7, work <m>m, <what runs now>".
CLOSE: on "close case" from me or the human: start nothing new, commit + push (WIP if unfinished), report first line "CLOSE CASE <name>: finished" or "CLOSE CASE <name>: unfinished", then done, left + next steps, tests, click path, ideas, TIME. Wait for my decision; never close yourself.
STATE: write agent_state.txt after every step (S7, S8).
NEVER: Claude in Chrome (W5). Product code. Full suite twice (W4). Files outside the worktree except via ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh.
```

## Cross-repo brief (W12, fill the <>)

```
[<model> <effort>] CROSS-REPO TASK <name> from <repo>
WHAT: <requirement, 5 lines max. What the peer repo must build or change.>
CONTRACT NEEDED: <what the sender must get back: endpoint, fields, errors>
REPORT: SendMessage to "<sender session name>". First line "DONE PASS <name>" or "DONE FAIL <name>: <why>". Then the contract.
ASK: first line "QUESTION:". Wait max 10 min, then default + log + continue (W1).
HEARTBEAT: every 15 min, one line "HEARTBEAT <name>: <what runs now>".
```
