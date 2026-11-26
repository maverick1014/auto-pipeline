# Repo files
Read when: you write an agent_* file, add or remove a doc, or need which file is written and read by whom.

R3. Docs
- Allowed: requirement, test, main idea
- Nothing else
- `PRINCIPLES.md` = main idea doc
- Entry files allowed: `CLAUDE.md`, `AGENTS.md` (one line, point to `bin/agent-start.sh`)
- `README.md` allowed: the picture of the tree and the flow, for people new to the repo
- Config, not docs, allowed: `.claude-plugin/`, `agents/`, `skills/`, `hooks/`, `bin/`
- Rubbish: `/auto-pipeline:clean-up` (main manager) lists other docs, old state copies, finished mocks and stale agent_* lines; removes only rows the human says yes to; a product repo's real docs stay by a no

R4. No changelog
- Git history is the record

R5. Task files
- `agent_todo.txt` = open tasks only, always current
- Done → agent_completed.txt: date, name, what, then one `data` block written by `agent-file.sh`: repo, type, lane, mock, est, guess, work, wait, clock, level (old tasks only, - for new ones), bounces, workers, files, lines, tests, adds
- No test results in it, that is report material
- No other task tracking
- The housekeep pass never closes a todo line: it flags one whose branch is merged into the working branch or the production branch
- A stale todo line is flagged too: no worktree line, no open wait, quiet longer than the interval of W8
- Do not launch an agent to write these files: it costs tokens; `bin/agent-file.sh` writes them (the rule: PRINCIPLES.md, Never)
- `agent_completed.txt` is never deleted, trimmed or cleaned (every clean-up skips it); only on an explicit owner order

R6. Ideas file
- `agent_ideas.txt` = ideas outside the current task
- Agents append, keep it clean and current
- Human reviews it on his own time
- The housekeep pass removes an exact duplicate idea (the first stays) and flags suspects (an idea naming a task finished after it, or a file that is gone), never removes a suspect

R7. Worktree file
- `agent_worktree.txt` = one line per live worktree: path, task manager, module, status (working | final | idle)
- Task manager updates its own line. Deputy removes the line after cleanup
- Main manager reads it before every dispatch (W9)
- The housekeep pass removes a line whose worktree folder is gone and has no live pane; a working, final or human-direct line is only flagged

Files:

| File | Who writes it | Who reads it |
|---|---|---|
| `agent_todo.txt` | `agent-file.sh todo add` / `todo done` | Every agent at start |
| `agent_completed.txt` | `agent-file.sh todo done`, one data line per task | Human, `agent-file.sh time` |
| `agent_estimate.txt` | `agent-file.sh retrain`, also `todo done` once a week | `agent-file.sh estimate` |
| `agent_ideas.txt` | `agent-file.sh idea add` | Human, on his own time |
| `agent_repo.conf` (committed, repo root) | `bin/agent-init.sh`, agents via `agent-file.sh edge add` | `agent-level.sh`, the merge gate, init |
| `agent_worktree.txt` | `agent-file.sh worktree set` / `rm` | Main manager before every dispatch |
| `agent_watch.json` (git dir, git-ignored by being there) | `agent-watch.sh --all` | `agent-watch.sh`, the board, the city (stall) |
| `agent_state.txt` | Each session: `agent-file.sh state add`; `state trim` moves old lines to `agent_state.trim-<date>.txt` (todo done, housekeep) | The same session, after a start, compaction or clear |
| `.secrets/` | Human only | Any agent, read only, never printed |
