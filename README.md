# auto-pipeline

A way to run coding agents so a human can read the result, trust it, and not get interrupted.
Rules live in [PRINCIPLES.md](PRINCIPLES.md). This page is the picture.

## The tree

```
Human
  │  task ↓   report ↑
Main manager   (Fable 5.1, xhigh · the main chat · only one with the browser)
  ├── Fast-lane deputy   (Sonnet 5, medium)  one small task, no worktree, then gone
  ├── Merge deputy       (Sonnet 5, medium)  merge → push → delete branch → remove worktree
  └── Worktree, one per big feature
        └── Task manager (Opus 5, xhigh)     writes the tests, briefs workers, verifies, never codes
              ├── Worker (Sonnet 5, medium)  code until the tests pass, slice 1
              └── Worker (Sonnet 5, medium)  code until the tests pass, slice 2

Scripts, not agents (cost no tokens):
  bin/agent-start.sh   RAM/CPU guard, prints the rules, 29-question quiz gate, main-manager lock
  bin/agent-file.sh    the only writer of agent_*.txt
  bin/agent-settings.sh  show or change agent.conf, validated
  bin/agent-resume.sh    one command to bring the pipeline back after a restart
  bin/agent-monitor.sh   watches every worktree, writes agent_monitor.txt
  bin/agent-init.sh      sets a project up: agent.conf, the four task files, .secrets/, .gitignore lines, AGENTS.md, and it prints the permissions block
```

## Who does what

| Agent | Does | Never does |
|---|---|---|
| Main manager | Talks to the human. Routes every task. Reports in 3 parts. Runs the browser E2E. | Code, tests, merges |
| Fast-lane deputy | One small task on the current branch. Human checks the screen. | Worktrees, browser |
| Merge deputy | Merge, suite once, push, delete branch, close terminal, remove worktree, update agent files. | Product code |
| Task manager | Splits the feature. Writes the failing tests. Briefs workers. Verifies every result. Bounces defects with evidence. | Product code, browser, talking to the human |
| Worker | Writes code until the task manager's tests pass. Runs only its own tests. | Tests, full suite, browser |

## How a task is routed (W9)

Checked in this order, first match wins.

1. Small task → fast-lane deputy. No worktree.
2. Touches a live worktree's module → that task manager. In final stage → hold.
3. Big, and a task manager has capacity → that task manager.
4. Idle or done worktrees → merge deputy cleans them first.
5. RAM and CPU under 80%, agents under cap → open a worktree with a task manager. Else wait.

## One real day

| Task | Path | Result |
|---|---|---|
| Fix a typo | Fast-lane deputy → human checks screen → merge deputy | 5 minutes |
| Build the settings page | Worktree → mock, human says yes → task manager writes tests → 2 workers → verify → browser E2E → merge | About 40 minutes |
| Add dark mode to settings | Same module, task manager has capacity → passed to it | Folded in |
| Font size option, arrives during final stage | Held. After merge, small → fast-lane deputy | Next |

## The files

| File | Who writes it | Who reads it |
|---|---|---|
| `agent_todo.txt` | `agent-file.sh todo add` / `todo done` | Every agent at start |
| `agent_completed.txt` | `agent-file.sh todo done` | Human |
| `agent_ideas.txt` | `agent-file.sh idea add` | Human, on his own time |
| `agent_worktree.txt` | `agent-file.sh worktree set` / `rm` | Main manager before every dispatch |
| `agent.conf` | `./bin/agent-settings.sh` | `agent-start.sh` |
| `agent_monitor.txt` | `./bin/agent-monitor.sh` | Every agent at start |
| `.secrets/` | Human only | Any agent, read only, never printed |

## Install

1. `/plugin marketplace add maverick1014/auto-pipeline`
2. `/plugin install auto-pipeline`
3. `/auto-pipeline:init`
4. Paste the permissions block it prints into this project's `.claude/settings.json` yourself — a plugin cannot add permission rules:

```
Bash(git push origin --delete *)
Bash(git branch -d *)
Bash(git worktree remove *)
Bash(git worktree prune)
Bash(orca worktree rm *)
Bash(orca terminal close *)
```

## Start

```
./bin/agent-start.sh             # rules, resources, quiz. No work until PASS
./bin/agent-resume.sh            # after a restart: relaunch, monitor, one table
/auto-pipeline:dispatch          # main manager: route one task
/auto-pipeline:merge             # main manager: E2E, then merge deputy
/auto-pipeline:init              # one-time project setup, prints the permissions block
./bin/agent-settings.sh          # show or change agent.conf, no agent
```

A second Claude session in this repo becomes a task manager under the main manager, by itself.
