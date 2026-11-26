# GLOSSARY
Read when: a repo term in a rule, skill or brief is unclear. Each entry says what the term IS; the rule that uses it lives in PRINCIPLES.md or rules/.

## People and roles
**Owner**: the human whose typed words count as approval; a quote of them is checked against his transcript before it is stored (from bin/agent-owner-order.sh).
_Avoid_: boss
**Human**: whoever reads the replies and types in a session; in this repo the owner (inferred; the owner decides).
**Main manager**: the one session per repo that holds the main-manager lock: it routes tasks, talks to the human and decides. Named `<repo> Manager`.
_Avoid_: main agent, main chat (the chat is where it runs, not what it is)
**Task manager**: the session that runs one big feature in its own worktree (exception: human-direct, W10): tests, worker briefs, verification; never product code. Named `<feature> Task Manager`.
_Avoid_: TM in rule text
**Worker**: a subagent of a task manager that writes code for one slice until the given tests pass. `agents/worker.md`.
**Fast-lane deputy**: a subagent that does one small task start to finish in its own git worktree and pushes a branch. `agents/fast-lane-deputy.md`.
_Avoid_: deputy subagent, small-task subagent
**Reviewer**: a read-only subagent that does PR REVIEW and CORE REVIEW. `agents/reviewer.md`.
**Check deputy**: a read-and-browser subagent that runs FLOW CHECK, UI CHECK, re-checks and RELEASE SMOKE. `agents/check-deputy.md`.
**Merge deputy**: a subagent that merges a finished branch and does the cleanup. `agents/merge-deputy.md`.
**Deputy**: any fast-lane, check or merge deputy: a subagent that executes and never decides.
**Builder**: the agent that wrote a task's code (the todo line's builder or its LAUNCH records); it never passes its own review or check.
**Fixer**: a new agent, run as a normal task, that repairs a red full-suite run; never the builder of the merge that broke it.
**Decision maker**: an agent whose order, decision or approval another agent acts on: main manager, task manager, reviewer, any such session.
_Avoid_: decider
**Decider floor**: the lowest model and effort a decision maker may run on: Opus 5.5 or above, or any Fable, effort medium or above.
**Human-direct**: a session the human opened by hand in a repo that already has a live main manager; it acts as a task manager the human drives. Agent-spawned sessions are never human-direct.
**Helper**: the name of a human-direct session: `<repo> Helper - <Task Name>`. The "Helper model" setting is a different thing: the model of workers and deputies.
_Avoid_: Helper for a worker or deputy
**Peer**: the main manager of another repo, found as `<other repo folder> Manager` in ListAgents.

## Work units
**Task**: one todo line: a name, size, estimate and its check blocks.
**Task instance**: a task's record from `todo add` on: opened time, checks, stage; it stays when the target changes.
**Slice**: the part of a feature one worker builds; one worker = one slice.
**Fast lane**: the path of a small task: one fast-lane deputy, no task manager.
**Full lane**: the path of a big task (over 2 hours, several slices): a task manager and workers.
_Avoid_: level (levels are gone; blocks replaced them)
**Batch**: tasks given together (`--batch <name>`); after the last one merges, one full suite runs on the working branch.
**Brief**: the full instruction text a manager sends an agent; its first action copies it into `agent_state.txt`.
**Fix order**: a message that sends a defect back to its builder, in the fixed shape: where, what is seen, what is expected, evidence.
**Bounce**: a task sent back to its builder (by a fix order, a missing click path or TIME line, or GATE REFUSED); counted in the task's data (from skills/merge/SKILL.md and bin/agent-file.sh).
**Click path**: the exact steps a checker follows in the UI: start command, URL, clicks, expected result, how to restore (from skills/dispatch/SKILL.md, REPORT).
**Kick-off round**: the task manager's first questions to the main manager, before step 1 of its brief (from skills/dispatch/SKILL.md, step 0b).
**Requirement doc**: the doc the owner approves before the flow starts; the reviewer reads the diff against it.
**Edge list**: the `edge=` lines of `agent_repo.conf` (from bin/agent-file.sh): real edge cases of this repo; example tests cover its fitting lines.
**Core path**: a path of the repo listed in `agent_repo.conf` whose change triggers CORE REVIEW (money, permission).
**Mock**: a clickable prototype of a new page or a whole-page re-layout; once the owner says yes, it is the acceptance criterion.

## Branches
**Production branch**: the branch users get (`production_branch` of `agent_repo.conf`, else origin/HEAD, else main; from skills/merge/SKILL.md and bin/agent_conf.py).
_Avoid_: main (as a role name), target branch (a target is production or working)
**Working branch**: one person's integration branch (setting "Flow: Working branch", default `ap-main-<name>`); every merge lands there first, except a task with target production, which goes straight into the production branch (`agent-promote.sh --task`).
_Avoid_: ap-main (bare), integration branch
**Target**: where a task merges: production (only on the owner's verified yes) or working (the default).
**Base**: the branch a task branches from: the production branch for target production, else the working branch.
**Main checkout**: the main repo folder, not a worktree; switched to the working branch.
**Late yes**: the owner's publish yes after a task was added; a new branch from production gets the task's commits cherry-picked (the brief field `late yes of:`, from agents/fast-lane-deputy.md).

## Checks
**Check block**: one named check with a trigger (PR REVIEW, DIFF SCAN, BUILD ...); the table in `rules/checks.md` mirrors `bin/agent_blocks.py`.
_Avoid_: level, check level
**Check line**: the result line of one block, `CHECK <task> <BLOCK>: pass|fail | by | at <sha> | evidence`, written by `agent-file.sh check` (from bin/agent-file.sh).
**The gate**: `agent-file.sh checks gate <task>`: refuses a merge while a planned block has no pass line.
_Avoid_: merge guard (the usage text of bin/agent-file.sh says it; the guard is `agent-guard.sh`)
**Owner sign**: the block OWNER SIGN: it passes only with the owner's verified words.
**Light / heavy test**: BUILD and GUARD TESTS are heavy when their measured time in agent_repo.conf is over `check_budget_s` (60 s): they run in the net, not in the task. RELATED and MODULE TESTS take only the light tests ("measured").
**Selection miss**: a failure the nightly finds that the causing task's RELATED or MODULE run did not.
**The net**: the full-suite runs outside tasks: NIGHTLY RUN and the release run; it gates nothing in a task.
_Avoid_: safety net (same thing)
**Release run**: the one full suite on the working branch before a publish; the batch run on that commit counts.

## Machines, sessions, records
**Connected machine**: another machine paired in Orca that can take jobs; placement tries it first.
_Avoid_: paired machine, remote machine, another machine (when it means this)
**Pane**: an Orca terminal running one agent or shell.
**The lock**: the main-manager lock line in the shared git dir: pid, date, session id, terminal.
**LAUNCH record**: the line `agent-guard.sh` writes for every Agent launch and Orca pane, under its task.
**The watch**: one background `agent-watch.sh --all` that watches every task manager's pane and `agent_state.txt` and exits on a signal.
**Stall**: three watch sweeps with neither the pane screen nor `agent_state.txt` changed.
**The housekeep pass**: `agent-housekeep.sh --apply`, run by the watch every housekeep interval: flags and removes stale lines of the task files, then runs the sweep; writes one HOUSEKEEP block.
_Avoid_: tidy (the setting title "Stuck: Tidy every (min)" names its interval; from .claude-plugin/plugin.json)
**The sweep**: `agent-cleanup.sh --apply`: "removes merged, clean, idle worktrees and branches; lists the rest in one table"; it "never closes a Claude pane, only a shell pane that never got a prompt and is idle over 30 minutes" (W8).
_Avoid_: cleanup sweep, cleanup (cleanup = the merge's own removal of branch, pane and worktree)
**State file**: `agent_state.txt` of a worktree or the main repo: the agent's memory.
**Decide section**: the last part of every report to the human: numbered open questions, each with a recommendation.
**Parked question**: a question kept for later with `park add`; shown on the board and in the question list.
**OWNER TODO**: a state line for something the owner must do later (for example "publish next week").
**Start text**: what `agent-start.sh` prints at session start: the `YOU:` line, resources, rules, the quiz line.
