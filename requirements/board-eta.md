# board-eta: the board's finish time follows the real state of a task

Owner, 2026-11-27: "so which mean actually the board time is not the one you write written down ? and is that same for others ? check and find the root causes".

## Today (measured 2026-11-27 11:18)

| Task | Board | Real |
|---|---|---|
| script-speed | 421 min left, 18:19 | a fix round after review, about 30-45 min |
| session-cleanup | 105 min left, 13:03 | DONE PASS at 11:15 |
| ask-test | 32 min left, 11:50 | DONE PASS at 11:10, waiting for review |

Root causes (in the code):
1. `bin/agent_watch.py` (`STAGE|HEARTBEAT|STEP` reader, ~453-488) takes the LAST matching line of a remote `agent_state.txt` by file position. The task manager's `STAGE <task>: <stage> | since ...` line is rewritten in place near the top of the file, and `HEARTBEAT ... step <n> of 7` lines are appended below it. So an older heartbeat (step 5 = verify) wins over a newer STAGE line (report).
2. `carry_stage` (~788) writes that stage into the main repo's todo line even when the main manager set a later stage itself (e2e, merge), so a review stage falls back to verify.
3. `forecast_of` (`bin/agent_board.py` ~604) passes the current stage, the work so far and `built_work`. The forecast reads stage `workers` as about 40 % done, also for a fix round after a task already reached e2e or report, which gives 400+ minutes for a round of 30-45.

## The rule

1. The watch carries the newest stage by TIME: each candidate line carries its own time (the `since` of a STAGE line, the date of a HEARTBEAT line); the newest time wins; the file position only breaks a tie.
2. The watch never moves a todo line's stage backwards past a stage the main manager set itself (e2e, merge) unless the task manager starts a new round: a STAGE line newer than the main manager's stage.
3. A task that has a `built_work` (it reached e2e or report once) and is again in a stage before report is in a fix round: its time left is forecast from the fix rounds of past tasks (the minutes between a return to workers or verify and the next report), or from the todo line's added minutes when there is too little history, never from the step share of the whole task.
4. Nothing else of the board, the estimate or the watch changes.

## Examples (the failing tests come from these)

- A remote state with `STAGE t: report | since 11:10` on line 29 and `HEARTBEAT t: step 5 of 7, ... | 11:08` on line 60: the watch carries report.
- The same with the heartbeat at 11:12 (newer): it carries verify.
- The main manager set e2e at 11:13; the remote's newest line is a heartbeat step 5 from 11:08: the todo stays e2e. A remote `STAGE t: workers | since 11:20` (a new round): the todo goes to workers.
- A todo line with stage log `... e2e 123, push 129, workers 168`, est 135, work 171: time left is in the range of past fix rounds (tens of minutes), not hundreds.
- A first round (no e2e or report yet): the forecast is the same as today.

## Not in this task

The estimator itself (the est numbers are too low: a separate, known issue). The board's layout.
