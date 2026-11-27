# board-fast-lane: the board shows a fast-lane task while its deputy works

Owner, 2026-11-27: "i notice the board is not updating". The todo board showed a fast-lane task as "not started, idle N min" while its deputy worked.

## Causes (found by the main manager)

1. Nobody runs `todo stage` for a fast-lane task (skills/dispatch step 2 and skills/merge 0b stage only the full lane), so the todo line never gets "started".
2. A deputy resumed with `SendMessage` for a fix round writes no new LAUNCH record, so a finished-then-resumed deputy is invisible.
3. `agent-file.sh session-end --dead` did not catch a dead human-direct Helper line that has no session id (the line stayed on the board).

## Rules

1. First stage by the guard. When the guard records the launch of a `fast-lane-deputy` for an open task whose todo line has no `stage` field, it runs `agent-file.sh todo stage <task> brief`, so the line gets `stage brief since ..` and `started ..` (todo stage writes both at the first stage). A line that already has a stage is not touched. Any other agent type, or a task that is not open: nothing.
2. Stages of the fast-lane steps (skills/dispatch step 2, skills/merge step 0b/2/4): the deputy launch = `brief` (the guard); its DONE report = `report` (main manager runs `todo stage "<task>" report` when the deputy reports DONE PASS); the main manager's own diff review = `e2e` (the same stage word as the reviewer step); the merge (`MERGE` sent to the deputy) = `merge`.
3. SendMessage = a launch. A `SendMessage` whose `to` is a deputy or worker agent the guard has seen before (by agent id, or by its description) for an open task writes a LAUNCH record like a launch (kind and title of the known agent, `agent <id>`, new `since`), so the board shows the task running again. The record goes when that agent stops (SubagentStop). A message to an unknown name, to a task that is no longer open, or by a session that has no pid: nothing, and it is never blocked. The guard keeps what it needs in `<git common dir>/agent_known_agents.jsonl` (one JSON line per agent with an agent id: agent, task, kind, title, type), written when the agent id is known (PostToolUse of the launch).
4. `session-end --dead` also drops a human-direct line that has no pid field and no session id (nothing to find a process by) and whose `since` is 12 hours or more before now. Chosen as the safe option: a line of today's format always has pid and session, so a pid-less, session-less line is of the old format; under 12 hours it stays (it may be a live old Helper). A line with a pid or a session id keeps the rule of today (pid on this host gone = dropped; live or another host = kept). The printed line: `human-direct line <path> (no pid, no session id, <n>h old)`.

## Examples (the failing tests come from these)

Now = 2026-11-27 12:00 (AGENT_FAKE_NOW).

1. (cause 1) todo line `board-fast-lane | small | ... | opened 2026-11-27 11:30 | by main` has no stage. The main manager launches `Agent` `fast-lane-deputy`, description `board-fast-lane Deputy`. After the hook the line has `started 2026-11-27 12:00` and `stage brief since 2026-11-27 12:00`. A line that already has `stage tests since ..` is unchanged. A `worker` launch leaves a stage-less line unchanged.
2. (cause 2) A deputy was launched (agent id `a1`), then stopped (its record is gone). The main manager sends `SendMessage to a1`. After the hook there is one LAUNCH record: kind `deputy`, task `board-fast-lane`, `agent a1`; the board shows the task running (1 agent). SubagentStop of `a1` removes it. A `SendMessage` to an id never seen: no record.
3. (cause 3) agent_worktree.txt has `/x/wt | task manager, human-direct | task: (ask the human) | since 2026-11-26 09:00` (no pid, no session): `session-end --dead` removes it and prints `human-direct line /x/wt (no pid, no session id, 27h old)`. The same line with `since 2026-11-27 11:00` stays. A line with `pid <live> | host <this> | session s1` stays.
