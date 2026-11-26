# Worktrees, merge, cleanup
Read when: you open a worktree, merge a task, clean up after it, run the sweep, or read a HOUSEKEEP block. Where a job runs: rules/resources.md.

W7. Big feature (> 2 hours)
- Before opening a worktree: idle or done worktrees > 0 → deputy cleans them all first (W8)
- A worktree needs Orca. `agent-runtime.sh kind` picks the shape
- On Orca: read Orca's own guide first, `orca skills get --topic orca-cli --full --json`. Flags change: `orca agent-context --json` is the current schema
- Then new worktree
- One task manager inside it
- Task manager spawns workers as needed
- plain or cloud → no worktree, no second terminal. Main manager runs the task itself with `Agent` subagents, each admitted by the memory rule (S3)
- One agent = one worktree = one branch = one terminal. Push at every stage

W8. Merge and cleanup
- The merge deputy merges into the working branch (ap-main-<name>) in the main checkout
- A task with target production goes straight in through `agent-promote.sh --task`: a short-lived worktree of the production branch, removed right after; the main checkout never switches
- After any direct merge into production, production is merged back into the working branch at once, so they never drift
- The merge deputy runs `agent-file.sh checks gate <task>` first: GATE REFUSED → no merge, the task goes back
- Deputy deletes the branch (local + remote) and the worktree right after merge
- Every merge ends with cleanup, in every case: a task manager pane, a subagent's git worktree, a human-direct Helper (its own pane stays), a worktree on another machine (agents/merge-deputy.md)
- The worktree line of a merged task is always removed or rewritten at merge, also when the folder stays
- human-direct protects only the human's own session pane; the sweep never closes a Claude pane, only a shell pane that never got a prompt and is idle over 30 minutes (`unused_pane_min`)
- The sweep prunes a LAUNCH record whose pid is dead or whose pane is gone; its table never lists main or the release branch; a worktree with a live LAUNCH record is "live agent"
- The plain list shows what --apply would remove; --apply is main manager only
- Whatever is sent to another machine is cleaned up there when it is done: pane, worktree, branches, scratch clones, temp test folders, its reservation
- The sweep covers every connected machine and its list names what is left there
- Never skip cleanup
- Main manager verified + waiting for the owner's yes → agent-file.sh checks gather first, close the task manager pane, remove its worktree, keep the pushed branch, start the next task
- Owner yes → merge deputy merges the branch. Owner no → a new task manager from that branch. Goal: work all night, RAM stays free
- Delete the branch and close the todo line only after the merge is verified
- Meanwhile the pane and the worktree may go while waiting for the owner's yes; the pushed branch stays
- Deputy runs `bin/agent-file.sh worktree rm <path>` and `bin/agent-file.sh todo done <name>` with the facts from the main manager and `--merge <commit>`
- Sweep: `bin/agent-cleanup.sh --apply` after every merge, at session start and when the last open task closes (todo empty, no live worktree). The scripts run it, no loop
- Housekeep: every housekeep_interval_min minutes (default 120, 0 = off) `agent-watch.sh --all` runs `bin/agent-housekeep.sh --apply`, then this sweep. Plain and cloud: no watch, run it by hand
- The housekeep pass runs `agent-file.sh state trim` on the main repo's agent_state.txt before it writes its block (S8)
- The main manager reads the HOUSEKEEP block in agent_state.txt at its next activity. Per suspect: `idea rm <n>` if done or voided by a recorded owner decision, else `idea keep <n>` (still wanted)
- It then acts on the other flags of the block
- Main manager only. Task managers, Helpers and workers never run it
- Own repo only: this machine and every paired Orca machine
- Removes only safe items: merged into the working branch or the production branch (origin/main here), no live agent, no uncommitted or unpushed work, no working/final/human-direct line
- Everything else is never deleted: one table to the human (what, where, why kept, suggestion)
- A done pane (finished, idle) in a kept worktree: closed when its task is done or dropped, or its line is gone and its branch merged; else one kept row
- A paired machine unreachable → one line, skipped. Never hangs the start
