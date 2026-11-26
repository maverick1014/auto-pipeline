# State, context, cost
Read when: agent_state.txt grows long, after a compaction or /clear, at a resume or recovery, when you pick a model or brief a worker. The every-step part of S8: PRINCIPLES.md.

S2. Resume script
- One command
- Loads context, memory, agents, saved sessions (S7), and prints the watch command when no watch runs

S7. Session recovery
- Each agent saves state to `agent_state.txt` in its own worktree while working: task, progress, decisions, next step
- `agent_state.txt` is git-ignored. It never merges
- S2 restores it after crash or shutdown

S8 (cont.). Context guard (forgetting)
- The main manager's `agent_state.txt` is in the main repo: open decisions, live sessions and terminal handles
- `agent-file.sh state trim` keeps the header, RULE/CARRY and machine lines, open questions, open-task lines, standing OWNER lines and the last 24 hours (fixed)
- `state trim` moves the rest to `agent_state.trim-<date>.txt` next to it, never lost. `todo done` and the housekeep pass run it (`state_trim_auto`); check with `--dry-run`
- Over 300 lines (fixed) the start text says STATE LONG: trim it
- Compacted 2 times (fixed) → save state. Orca: `agent-autoclear.sh` types a save prompt, `/clear`, then `/goal` into the own pane, only at an idle prompt with an empty input box
- The auto clear fires only when no human has typed a prompt in that pane for the last N minutes (setting "Context: Auto clear after quiet (min)", default 30); until then it waits and tries again
- Not a human prompt: a task notification, a tell pointer, a cross-session message, the watch or the auto clear's own prompts. A task manager nobody types into is cleared as today
- A task manager runs under `/goal` from the GOAL: line of its brief: typed after the brief and after each answer; the auto clear types it again
- After a close case the main manager clears itself the same way: it types `/clear` into its own pane (its handle is in the lock line). Plain or cloud → the human types it
- No pane to type into (plain, cloud) or the send is refused → tell the human to type `/clear`; else end the session, restart from the file (S2)
- One worker = one slice, then it ends. A second slice gets a fresh worker

S9. Token guard (cost)
- Cheapest model that can do the job (the Models settings). Managers judge, they do not read whole repos
- Model by kind of thinking: deciding roles get the strongest model, executing roles a cheaper one (the Models settings)
- A worker gets only the files it needs, named in its brief. No repo-wide reads
- Quiz once per session start. Not after compaction, not for subagents
