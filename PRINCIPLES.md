# PRINCIPLES

- Read first. Binding for every agent in this repo.
- Output reader: Maverick, non-native English. Keep output simple.
- All numbers, models and effort levels are config values (`agent.conf`, written by the settings menu S1). Never hard-code.

## A. Repo

R1. Two lanes
- Small task → fast lane, no pipeline
- Big task → full pipeline
- Task size picks the lane
- Fast lane: no TDD while doing, human verifies directly, minimal test at merge

R2. Secrets
- Live in `.secrets/` (git-ignored)
- Read only
- Never write, print, copy, commit

R3. Docs
- Allowed: requirement, test, main idea
- Nothing else
- `PRINCIPLES.md` = main idea doc
- Entry files allowed: `CLAUDE.md`, `AGENTS.md` (one line, point to `agent-start.sh`)

R4. No changelog
- Git history is the record

R5. Task files
- `agent_todo.txt` = open tasks only, always current
- Done → move line to `agent_completed.txt`
- No other task tracking

R6. Ideas file
- `agent_ideas.txt` = ideas outside the current task
- Agents append, keep it clean and current
- Human reviews it on his own time

R7. Worktree file
- `agent_worktree.txt` = one line per live worktree: path, task manager, module, status (working | final | idle)
- Task manager updates its own line. Deputy removes the line after cleanup
- Main manager reads it before every dispatch (W9)

## B. Work

W1. Finish in one run
- Never wait for the human
- Unknown → pick default, log it, continue
- New ideas → `agent_ideas.txt` (R6), never in the work or the report

W2. UI
- Clickable mock first (prototype artifact)
- Human says yes
- Then real code

W3. TDD
- Task manager writes the failing tests → worker writes code → tests pass
- Workers never write tests. Task managers never write product code
- No test = not started
- Full lane only; fast lane → R1

W4. Multi-agent tests
- Run tests for your changed files only
- Full suite: manager, once, at the end. Never twice
- After a bounce: re-run only the tests that failed, not the suite

W5. Web UI testing
- Claude in Chrome, not Playwright
- Main manager only, saves RAM. Others write the click path and hand it to the main manager

W6. Roles
- Main manager (Fable 5.1, xhigh) = the main chat. Assigns tasks, talks to the human, reports, accepts decisions, brainstorms. Nothing else
- Fast-lane deputy (Sonnet 5, medium) = main manager's subagent, new one per small task. Does the task, no worktree
- Merge deputy (Sonnet 5, medium) = main manager's subagent. Merges, then deletes branch and worktree
- Task manager (Opus 5, xhigh) = one agent per big feature, in its own worktree (exception: human-direct, W10). Writes the tests, briefs workers, judges, verifies every worker result before reporting done to the main manager. Never writes product code
- Worker (Sonnet 5, medium) = subagent of a task manager. Writes code until the task manager's tests pass
- File clerk (Haiku 4.5, low) = subagent any manager or deputy spawns to read or write `agent_*.txt` files. Nothing else
- Managers never write product code. A defect goes back to the worker that wrote it, with evidence

W7. Big feature (> 2 hours)
- Before opening a worktree: idle or done worktrees > 0 → deputy cleans them all first (W8)
- Then new worktree
- One task manager inside it
- Task manager spawns workers as needed
- Every spawned agent counts toward `max_agents` (S6). The main manager does not

W8. Merge and cleanup
- Deputy merges into the integration branch
- Deputy deletes the branch (local + remote) and the worktree right after merge
- Never skip cleanup
- Deputy removes the worktree line from `agent_worktree.txt`

W9. Task routing (main manager, before every dispatch)
- Read `agent_worktree.txt` first
- Small task (fast lane) → spawn a new deputy subagent, it does the task. No worktree
- Task touches a live worktree's module → that worktree's task manager
- Big task, and a live task manager has capacity → that task manager
- Task manager in final stage (compiling worker results) → do not disturb. Hold the task until it finishes
- Otherwise → new worktree (W7). Never spawn a worktree for a small task

W10. Second session in the same repo
- One main manager per repo. `agent-start.sh` keeps a lock in the shared git dir
- Lock owner alive → this session is a task manager (human-direct). Never a second main manager
- Human-direct = only a session the human opened by hand. Agent-spawned agents are never human-direct. They run fully by agent, no human in the loop
- At start: the script adds a line to `agent_worktree.txt` (status human-direct). Also send the main manager a direct message if a channel exists (Orca)
- Will change files → open its own worktree first (W7). Only looking → no worktree
- Human talks to it directly for now. All task manager rules still apply
- Human says "finish" or "report to main manager" → report done + click path to the main manager, then act as a normal task manager. Merge deputy cleans up
- Finished with nothing to merge → main manager sends a file clerk to remove its line from `agent_worktree.txt`
- The main manager closes every human-direct session after the human says finish: `orca terminal close --terminal <handle> --json`. Nothing stays parked
- Lock owner dead → take over as main manager, run recovery (S7)
- Talk between sessions: `ListAgents` → find the peer's name → `SendMessage` to that name. Reply to the `from` name. First line of every message = one clear sentence
- Open a second session with the same permission mode as the main manager (`permission_mode` in `agent.conf`): `orca terminal create --worktree path:<repo> --command "claude --permission-mode auto" --json`, then `orca terminal wait --for tui-idle`

## C. Human

H1. One topic
- Ask only about the current task
- Park other questions
- Show them at the end, one table

H2. Words
- Short sentences
- Common words
- Jargon only for code names

H3. Report
- Result (pass/fail)
- What changed
- What to decide
- Nothing else

H4. Tables
- Comparison, series, feature list, task list, options → table
- Never prose

## D. Auto setup

S1. Settings menu
- Writes agent-monitor config
- No hand editing
- Holds every config value in this file

S2. Resume script
- One command
- Loads context, memory, agents, monitor, saved sessions (S7)

S3. Resource guard
- Before new agent or heavy process: check free RAM and CPU
- Low → wait or run smaller

S4. Usage cap
- RAM and CPU each ≤ 80%
- Over → no new job to any agent until it drops back
- Config `max_usage_percent`=80

S5. Heavy tests
- One at a time across all agents
- Others queue
- Config `heavy_test_slots`=1

S6. Agent cap
- Per device
- Config `max_agents`: this laptop 4, maverick-pc2 6
- Counts spawned agents only. The main manager is not counted

S7. Session recovery
- Each agent saves state to `agent_state.txt` in its own worktree while working: task, progress, decisions, next step
- `agent_state.txt` is git-ignored. It never merges
- S2 restores it after crash or shutdown

S8. Context guard (forgetting)
- Memory is the file, not the chat. Brief, decisions, next step live in `agent_state.txt`. Re-read it before every step, write it after every step
- After a compaction the startup hook re-prints PRINCIPLES.md and `agent_state.txt`. No quiz then. Continue from the file, not from memory
- Compacted 2 times → write state, end the session, restart from the file (S2)
- One worker = one slice, then it ends. A second slice gets a fresh worker

S9. Token guard (cost)
- Cheapest model that can do the job (`agent.conf`). Managers judge, they do not read whole repos
- A worker gets only the files it needs, named in its brief. No repo-wide reads
- Passing tests are not re-run. Full suite once, at the end (W4)
- Quiz once per session start. Not after compaction, not for subagents
- Briefs, reports, heartbeats: short (H2, H3). One line per heartbeat
