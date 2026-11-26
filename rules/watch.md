# The watch
Read when: you start, restart or handle the watch (main manager), or report, ask or send a heartbeat as a task manager.

W15. Watch
- After a watch wake the first action is to start the watch again, then handle the signal
- The watch also wakes the main manager when there is room for a queued task (WATCH ROOM)
- A board warning (watch not running, not confirmed, a pane without a task line) reaches the main manager through `agent-file.sh next` and the board warning hook; it reacts in the same turn
- Stall detection is the watch: each sweep reads the pane screen and the `agent_state.txt` file; 3 sweeps with neither changed = STALL. The same watch runs the housekeep timer (W8)
- Verify every launch within 2 min
- One `agent-watch.sh --all` in the background (Bash run_in_background) watches every task manager, local and on another machine: its pane and its worktree `agent_state.txt` (a report goes under `=== REPORT ===`); restart it after each wake
- A task manager's HEARTBEAT, ACK, report and question go into `agent_state.txt` only, never SendMessage; only DONE PASS, DONE FAIL, QUESTION:, MOCK READY, CLOSE CASE and the watch's STALL and LOST wake the main manager
- DONE FAIL → the main manager reviews the report, then sends the task manager a fix order (where, what is seen, what is expected, evidence). Never merged, never closed silently
- LOST (the watch cannot reach a machine or a pane) → wait one more sweep; still lost → tell the owner in one line with the machine and the task
- Never redispatch a LOST task on another machine by itself
- The watch carries a task's stage to the main repo from the newest STAGE line or HEARTBEAT step (0-7 = brief to report); the heartbeat's work minutes and text go to the board's progress cell
- A manager at its idle prompt while its own background run goes (pane shows shells or monitors, or its newest state line says started, for watch_quiet_min) is not a stall
- Long text to a task manager: `agent-file.sh tell <task> "<msg>"` (the block goes into its file, one pointer line to its pane, receipt checked)
- Start and resume print the `agent-watch.sh --all` command when no watch runs
- The board says `not confirmed <n>m` when a task is not watched or has been quiet
- A stall → nudge once, wait 10 min, then salvage (commit what is there) and redispatch
- Every brief says how to report, how to ask, how to report done (pass/fail) and the heartbeat
