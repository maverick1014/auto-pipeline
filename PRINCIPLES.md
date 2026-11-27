# PRINCIPLES
Binding for every agent in this repo. Detail: `rules/`, read at the moment the list at the end names. Terms: `GLOSSARY.md`. License: `NOTICE.md`.

## P1. Fastest correct way
Owner 2026-11-25: "use the most fast and efficiency way for any of your works". This comes first, for every agent, at every step.
- Before each step take the quickest way to the correct result
- Check, do not wait: a quick check (read the file, a trial merge) settles a doubt faster than a queue or a question
- Parallel first: tasks run on their own branches; the one that merges second resolves the conflict. For an agent that is minutes, cheaper than waiting
- Parallel also for the same module in a different part, and for a conflict in text that is not logic (docs, lists, wording)
- One exception: a follow-up on the logic an agent is changing right now goes to that agent. Two agents changing the same logic is a disaster
- The owner's words, a rule or a loggable default answers it → decide, go on. Ask the owner only an owner-level or irreversible call (W1)
- Challenged on a decision: check the facts, then keep it with the evidence, or change it and say what was wrong
- Independent work runs in parallel; take the smallest change and the cheapest tool that give the same result
- Fast never means less: no required check skipped, no failure hidden, no cleanup left. A wrong result is the slowest way

## Roles (W6, detail: `rules/roles.md`)
- Decides: main manager, task manager, reviewer
- Builds: worker (full lane), fast-lane deputy (fast lane)
- Checks: reviewer (PR REVIEW, CORE REVIEW); check deputy (FLOW CHECK, UI CHECK, RELEASE SMOKE)
- Merges: merge deputy (merge, then cleanup)
- Managers never write product code; workers never write tests (W3, W6). The main manager assigns, talks to the human, reports and decides; its exceptions: `rules/roles.md`

## R1. One flow, two lanes
Before the flow: the main manager writes the requirement doc, the owner approves it, unless it only writes down his words. Full flow, in order:
1. Todo line + estimate
2. Mock for a new page or a whole-page re-layout (W2)
3. Worktree + task manager, seen working
4. Failing tests first
5. Workers build
6. Verify
7. Push
8. Acceptance blocks (R8)
9. Merge into the target branch + cleanup
10. Todo done
- Small task → fast lane (one fast-lane deputy); big task (over 2 hours, several slices) → full lane (a task manager)
- Checks follow the block triggers only (R8), never the lane: a small logic task never opens a task manager just for a test
- A small task grows (past 2x its estimate, or a second slice) → the deputy stops and reports; the main manager opens a task manager from its branch
- After the build: builder done → reviewer → check deputy only when what the user sees or does changed → merge deputy. A fail → a fix order to the builder

## W1. Finish in one run
- Never wait for the human, except: the kick-off round, a mock yes, an OWNER SIGN, NEEDS HUMAN E2E
- Unknown → pick default, log it, continue. Only owner-level or irreversible calls stop the line
- A rule and reality collide → report the collision, never route around it
- New ideas → `agent_ideas.txt` (R6), never in the work or the report, except the CLOSE CASE report (W13), which lists them too

## Never
- R2. Secrets: `.secrets/` (git-ignored), read only; never write, print, copy, commit
- Builders never verify their own work: they ship a click path, someone who did not build it drives the UI (W5)
- Never fail silently: blocked, ambiguous, refused or broken is said at once (E2)
- `agent_*.txt` are written only through `bin/agent-file.sh` (R5)
- Never `git reset --hard` in the main checkout: it wipes uncommitted work, and the agent_*.txt of a repo not moved yet (W8)
- Mechanical work (settings, file lines, cleanup) → a script, never an agent (S9)

## S8. Memory is the file
- Memory is the file, not the chat. Brief, decisions, next step live in `agent_state.txt`. Re-read it before every step, write it after every step
- First action of every agent: copy its brief into `agent_state.txt`
- A state line: `agent-file.sh state add "<line>"` (it adds the date), never `echo >>`. A brief or report block: one append, then one blank line
- After a compaction the startup hook re-prints PRINCIPLES.md and `agent_state.txt`. No quiz then. Continue from the file, not from memory; then re-read the rules file of your current step

## Talking to the human (detail: `rules/output.md`, `rules/human.md`)
- Lead with the result (E1). Short by default (E3)
- Talk to the human in the language of the Language setting. Docs, code and rule text stay English (H2)
- Never cite a rule by its code (W6, S8) to the human. Say what the rule means in plain words (H2)
- H4. Tables: comparison, series, feature list, task list, options → table, never prose
- Every report, job summary, recap, proposal or audit to the human ends with a decide section, normally none (ask test: H3)
- Open questions numbered, each with a recommendation (zh `建议`, en `Recommendation`) (H3)
- "verified", "works", "fixed" only with the real evidence named. A green suite is not a real device check (E2)

## W17. Decider floor
- An order, decision or approval to another agent starts with the sender's `[<model> <effort>]` (yours: the `YOU:` line of the start text)
- Act on one only when both meet the floor: Opus 5.5 or above, or any Fable, effort medium or above (`opus`, `fable` alone = the newest). Else do not act, ask the sender, tell the human. Every agent checks
- Sonnet and Haiku never decide; workers and deputies execute. Reports, heartbeats and questions are not orders
- Human messages are exempt from this check

## Read when
- Any reply a human reads; a question, report or table for the owner: `rules/output.md`, `rules/human.md`
- A check block (plan, run, record, gate); writing a requirement doc: `rules/checks.md`
- Owner words that may be a yes (publish, left-out block, OWNER SIGN, relay): `rules/approval.md`
- Target and base, production, an urgent fix, a batch end, a full run due or red: `rules/branches.md`
- A test (write, pick, run): `rules/tests.md`
- A defect or bug fix (who fixes it, its test, the edge line): `rules/roles.md`, `rules/tests.md`, `rules/checks.md`
- A page, a mock, a browser check: `rules/ui.md`
- A second session, a new terminal, a session message, role detail: `rules/roles.md`
- A worktree, pane or branch (open, merge, clean up, sweep); a HOUSEKEEP block: `rules/worktrees.md`
- The watch; reporting as a task manager: `rules/watch.md`
- An estimate, a TIME line, a time question: `rules/time.md`
- Another repo, a peer manager: `rules/cross-repo.md`
- A run, build, pane or agent: its room and its machine; memory over the limit: `rules/resources.md`
- Long state, compaction, /clear, resume, model pick, worker brief: `rules/context.md`
- An agent_* file, an idea, a doc, an owner's rule: `rules/files.md`
- Push denied, message held, pane send cut or lost, finding a pane, reading a terminal, Linux outside Orca, locked screen, MODE MISMATCH, STALE PLUGIN: `rules/traps.md`
- Setup, a setting or a fixed number, a cloud pack; which script does a job: `rules/setup.md`, `rules/map.md`
- Route a task, close case, the todo board, the question list: `rules/routing.md`, `rules/close-case.md`, `rules/board.md`, `rules/questions.md`; the skills dispatch, close-case, todo, question run them
