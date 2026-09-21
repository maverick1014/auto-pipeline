# PRINCIPLES

- Read first. Binding for every agent in this repo.
- Output reader: Maverick, non-native English. Keep output simple.
- All numbers are config values (settings menu, S1). Never hard-code.

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
- Failing test → code → pass
- No test = not started
- Full lane only; fast lane → R1

W4. Multi-agent tests
- Run tests for your changed files only
- Full suite: manager, once, at the end

W5. Web UI testing
- Claude in Chrome, not Playwright
- Main manager only, saves RAM. Others write the click path and hand it to the main manager

W6. Roles
- Main manager = the main chat. Assigns tasks, talks to the human, reports, accepts decisions, brainstorms. Nothing else
- Deputy = main manager's subagent. Merges, then deletes branch and worktree
- Task manager = one agent in its own worktree. Judges, decides, directs its workers. Never does the job
- Worker = Sonnet or Haiku subagent of a task manager. Does the job
- Managers never write code or tests. A defect goes back to the worker that wrote it, with evidence

W7. Big feature (> 2 hours)
- New worktree
- One task manager inside it
- Task manager spawns workers as needed
- Every role counts toward `max_agents` (S6)

W8. Merge and cleanup
- Deputy merges into the integration branch
- Deputy deletes the branch (local + remote) and the worktree right after merge
- Never skip cleanup

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

S7. Session recovery
- Each agent saves state to a file while working: task, progress, decisions, next step
- S2 restores it after crash or shutdown
