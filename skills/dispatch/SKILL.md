---
name: dispatch
description: Main manager only. Route a new task by W9, open a worktree by W7 when needed, launch the task manager and send its brief. Use when the human gives a task.
---
# /dispatch — route one task (rules/routing.md W9, rules/worktrees.md W7)

Run these in order. First match wins.

Every order you send another agent (brief, task, decision) starts with `[<model> <effort>]`: your own, from the `YOU:` line of your start text (PRINCIPLES.md W17).

1. `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh show`, `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh time`, and the RESOURCES line. Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh next` at every wake (a report, a watch signal, a human message) and dispatch what it lists as START at once; a task the owner already approved needs no new question. Estimate the task in minutes of agent work only; the waits (mock gate, owner question or review, hold, suite run) are not in it. First write your own guess in minutes, before you run the estimator. Then run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh estimate --type <t> --lane fast|full --mock yes|no "<one line what>" --guess <your minutes>` (only facts known before dispatch; `<t>` is the kind of work: page, server, script, docs, cloud, app, data or mixed). Its minutes go on the todo line as est, never your own guess: an est equal to `--guess` is refused unless `--why "<reason>"` says why. Its `p50 <m>m, p85 <m>m` line comes from the past errors: say "done in about p50, 85% sure within p85", never plus or minus fixed minutes. A fit version shows a `fit:` line; a blend version shows a `blend:` line; any other version says `guess: <g>m, not used` until a retrain picks the blend. Its range and its `like` lines (the 3 nearest past tasks) are the reason you give. It says `rubric`: the rubric won its backtest (or no version is trained yet), so its numbers are the rubric row.

Pick the brief blocks (R8) from what the owner approved: what changes for the user, how much other code depends on it. The tool decides its own blocks from the real diff before merge (`agent-level.sh check`); you only add the ones the brief shows:
- PR REVIEW: every task (the tool plans it; the brief says what the owner approved, the reviewer reads the diff against it)
- EXAMPLES TEST: behaviour or logic changes
- FLOW CHECK: what a user does changes (only the approved items, a 15-minute time box)
- UI CHECK: what a user sees changes: new page, re-layout, size or responsive change (a 15-minute time box)
- REAL DATA COUNT: a rule, limit or validation is added or tightened, or a list, print or export changes
- CORE REVIEW: the brief changes who can see or do what, or a posting rule

Every `todo add` line carries them as `--checks "<BLOCK>,<BLOCK>"`. A requirement table copies its defaults from the released template and lists every changed default for the owner. Beyond the reviewer's PR REVIEW, a second agent's opinion only for CORE REVIEW, or when someone wants a tool-triggered block removed (a removal needs a verified owner order).

At the start of a batch run `agent-promote.sh --sync` before its first task is dispatched (R8). Decide the target from the request words, per task (R1, W9): "publish or merge to main" → `--target production`; no such words, or unclear → none = the working branch (ap-main-<name>); nothing goes to production by itself. The main manager reads his words by the approval cases of R8, no fixed sentence: a numbered batch ("2. publish direct after done"), a task named by its description (exactly one fits: no question), two similar tasks (check first, then one question that names both), words that are not a yes now ("publish next week", a question, a refusal). When his words are a publish, store them: `todo add ... --target production --owner-quote "<his words>" --means "publish <task> to production"`, plus `--question "<the question>"` when his words are a short answer to a numbered question; promote takes none for --task, and there is no second yes later. A yes that comes after the task was added: `todo target <task> production --owner-quote "<his words>" --means "<the action>"` (the task instance stays; the branch rule is in R8). A block left out needs his verified words too (`--owner-quote` and `--means`; PR REVIEW and OWNER SIGN never). Tasks given together get `--batch <name>`. The base branch is the production branch for target production, else the working branch. Before dispatch ask one thing: does an urgent task need code that only a non-urgent one brings? Yes → it cannot ship alone: tell the owner at once (ship them together, or move that part into the urgent task), never guess. A new request may also wait until the working branch is tested and published; say which is faster.

URGENT FIX (production is broken): branch from the production branch (`git switch -c <branch> origin/<production branch>`) (`--target production`, base = the production branch). A fast-lane deputy makes the smallest fix, a reviewer does the PR REVIEW, the light related tests run, his verified words at dispatch, read as the publish of that task, are his final yes, then `agent-promote.sh --task "<name>" --branch <branch>` merges it (the owner's words were stored at `todo add`) to production and the deploy follows by itself; production is merged back into the working branch at once.

Parallel features? → first find the code they share (models, components, APIs). The shared part is its own task, merged first; the features that need it get `todo wait "<name>" on queue --after <shared task>` (W9).

Touches another repo? → W12: keep your part, send the peer main manager the cross-repo brief below, called side first, hold your todo line until its DONE PASS.

2. Small task (fast lane, R1)? → first `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add "<task>" small "<one line what>" <est_minutes> --guess <your_guess> --checks "<BLOCK>,<BLOCK>" [--target production --owner-quote "<his words>" --means "publish <task> to production" [--question "<the question>"]] [--batch <name>] --builder "<task> Deputy"` (the guard refuses a deputy for a task with no todo line), then `Agent` with `subagent_type: fast-lane-deputy`, `isolation: "worktree"`, description `<task> Deputy`. It works in its own git worktree and pushes a branch; several small tasks run side by side. The deputy brief carries `[<model> <effort>]` first, then `checks: <the BLOCK list>`, `target: <production|working>`, `base: <origin/<production branch> for target production, else origin/<working branch>>`, `working branch:`, `production branch:`, the task, the file(s); for a late yes (R8) also `late yes of: <task>` and `old branch: <branch>`. When EXAMPLES TEST is planned the deputy writes the example tests first. Done. After its DONE PASS: run the blocks the brief planned that the deputy cannot (PR REVIEW goes to the reviewer, FLOW CHECK and UI CHECK to a check deputy, by `/merge`), then a merge-deputy merges its branch (`/merge`). The merge deputy closes the todo line once, with the task's real lane.
2b. In a shared todo (`task_files` names todo) a task of someone else is dispatched only when it is assigned to you, or, with `task_take` anyone, after `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo take <task>`.
3. A new task gets its own branch and its own agent, also when it touches a live worktree's module in a different part. A follow-up on the logic a live task manager is changing right now must go to that task manager (`SendMessage`), never to a second agent (PRINCIPLES P1). Status `final` → hold it, tell the human. A task given to a live Helper: its TELL starts with "run `agent-file.sh helper-join "<task>"` first".
4. A task that needs code another open task brings waits for it: `todo wait "<name>" on queue --after <task>` (shared first). Nothing else waits.
5. Idle or done worktrees in `agent_worktree.txt`? → run `/merge` for each first.
6. A new pane or job: `agent-room.sh check <pane MB>` on the connected machine first (the one with the most room by S3); the local machine only when no connected machine has room or the job needs it. No room anywhere → close done and idle panes first, then wait and tell the human.
7. Otherwise, ask `${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh kind` first: orca, plain or cloud.
   ```
   ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add "<name>" big "<one line what>" <est_minutes> --guess <your_guess> --checks "<BLOCK>,<BLOCK>" [--target production] [--batch <name>] --builder "<name> Task Manager"
   ```
   A brief that changes who can see or do what plans `--checks "CORE REVIEW,OWNER SIGN"` (OWNER SIGN passes only with the owner's verified words: `agent-file.sh check ... --commit <head> --owner-quote "<his words>" --means "<what he signs>"`; /merge gives the head).
   Once the worktree path is known (the board reads it), record where it runs:
   ```
   ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo where "<name>" <machine> "<worktree path>"
   ```
   **orca** — open a worktree. Read the "Models: Task manager model" setting with `${CLAUDE_PLUGIN_ROOT}/bin/agent-settings.sh get task_manager` (form model:effort): `<model>` is what `python3 ${CLAUDE_PLUGIN_ROOT}/bin/agent_conf.py cli-model '<task_manager value>'` prints (the CLI refuses opus-5.5, takes opus), `<effort>` is the part after the colon. Read `<mode>` from the "Permissions: Permission mode" setting, read with `${CLAUDE_PLUGIN_ROOT}/bin/agent-settings.sh get permission_mode` (its first word):
   First the pane's room, in one step: `${CLAUDE_PLUGIN_ROOT}/bin/agent-room.sh reserve-pane --pending <task name> <pane MB>` checks room and reserves. No room: wait, create nothing. Then create the pane:
   ```
   orca worktree create --name <name> --branch <name> --repo path:<main repo> --base-branch <base branch> --no-parent --json
   orca terminal create --worktree path:<worktree path> --title "<name> Task Manager" --command "AGENT_ROLE=task-manager claude --name '<name> Task Manager' --model '<model>' --effort <effort> --permission-mode <mode>" --json
   orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 90000 --json
   ```
   The branch is named by the task (`--branch <name>`); never a prefix from the machine or the account.
   Then `${CLAUDE_PLUGIN_ROOT}/bin/agent-room.sh reserve-pane --name <task name> <the new handle>` gives the reservation its handle (it is dropped when the pane measures itself). A failed create: `${CLAUDE_PLUGIN_ROOT}/bin/agent-room.sh release-pane <task name>`. Note: a pane on another machine is not reserved in the local list (its room is that machine's; it reserves itself there at its start).
   `worktree create` opens default tabs (a shell "Terminal 1" and a Claude "<name> Task Manager" session). Use that default agent pane for the brief (`orca terminal list --worktree path:<worktree path> --json` gives its handle, skip the `terminal create` line), or close it first; never open a second one beside it.
   A new pane stops at a menu (trust prompt)? `orca terminal send` has no key flag: send the raw key as text, then Enter, e.g. Down: `orca terminal send --terminal <handle> --text $'\x1b[B' --enter`.
   Then start, or restart, the ONE watch with Bash `run_in_background`:
   ```
   ${CLAUDE_PLUGIN_ROOT}/bin/agent-watch.sh --all
   ```
   It finds every task from agent_worktree.txt and the LAUNCH records, so no per-task flags. A task manager on another machine needs a plain shell pane there; the watch says how to open one.
   It exits on WATCH SIGNAL (a DONE PASS, DONE FAIL, CLOSE CASE, QUESTION: or MOCK READY line in agent_state.txt), WATCH STALL, WATCH LOST, WATCH ROOM or WATCH MAX. Handle it, then start it again.
   Then send it the brief below with `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh tell <name> "[<model> <effort>] <brief>"` (no ListAgents + SendMessage, no pane send); later text goes the same way. Keep the terminal handle for `/merge`.
   Then confirm the start (the rule: rules/routing.md). `TELL OK <name> <sha>` → go on. `TELL FAIL <name> <sha>: pointer not seen (block is in the file)` → `orca terminal read --terminal <handle> --json`, then `orca terminal send --terminal <handle> --text "[<model> <effort>] TELL <sha8>: read the TELL <sha8> block at the end of agent_state.txt and act on it" --enter`. `TELL FAIL <name> <sha>: file check` → run the `agent-file.sh tell` line again. Within 2 min `orca terminal read --terminal <handle> --json` again.
   Then /goal: once the task manager has the brief (its `STAGE <name>: brief` line or its first reply), `orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 600000 --json`, read the pane (`orca terminal read --terminal <handle> --json`: nothing after the ❯ of the input box), then `orca terminal send --terminal <handle> --text "/goal <the GOAL: text of the brief>" --enter`; read back, not shown → send once more.
   Re-type /goal the same way after you send an answer to a QUESTION: line and after a mock or rules answer (mock yes, rules yes, or changes). The auto clear types it again by itself. Never on plain or cloud, never for a Helper.

   **plain or cloud** — no terminal can be opened here, so no worktree either. The main manager does the task itself, from the session it is already in, with `Agent` subagents (`subagent_type: worker`, description `<name> Worker <n>: <slice>`), each admitted by the memory rule (S3). Use the task manager brief below as its own task list and run the steps in order.

8. Task manager done and verified, waiting for the owner's decision → first run `agent-file.sh checks gather "<name>" --dir "<worktree path>"` (its CHECK lines go to the main repo), then close its pane, remove its worktree, keep the pushed branch, start the next task (W8). Owner yes → `/merge`. Owner no → a new task manager from that branch. Fix orders to a task manager always have: where, what is seen, what is expected, evidence (screenshot) (W6). Never re-run tests the task manager passed (W4).

9. Early merge: a fix from a still-running branch merged into its target branch → at once `SendMessage` that task manager: merge its base branch back into your branch now (the working branch, or the production branch for a direct fix). Never cherry-pick slices; merge the branch (or its prefix) — cherry-picks cost a conflict round at the final merge.

## Board records

The board (rules/board.md W14) reads these. Write each as it happens, never later from memory:
- Each wait gets `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo wait "<name>" on mock|question|review|hold|queue ["<note>"] [--who <name>] [--after <task>]` when it starts and `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo wait "<name>" off` when it ends
- Mock sent -> on mock; mock yes -> off
- Owner question -> on question; answered -> off
- DONE PASS waiting for the owner -> on review; he decides -> off
- Held -> on hold; released -> off
- Waiting on someone other than the owner (a peer manager, a reviewer) -> --who <name>; the owner is the default for mock, question, review
- Waiting for room or another task -> on queue --after <task>; room found -> off
- Launches record themselves (`bin/agent-guard.sh`, W14). Every Agent description and pane title must start with the task name, else the launch is refused (only with the "Rules: Todo before agent" setting on, the default; off never refuses). Read-only agents (Explore, Plan) and Helper panes need no task name. Run the `todo add` line of step 2 or 7 first
- Parked question for later (H1): `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh park add "<question>"`

## Time question from the human

The human asks how long a task takes or when it is done (a time question) → run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh eta "<name>" [--wait <m>]`: it prints the board's Done by numbers (p50 and p85, waits never inside); with `--step <n>` / `--work-so-far <m>` (from the last HEARTBEAT) it uses the old rule instead; `--wait` = known waiting still ahead.
Answer with its line: a duration AND a clock time, and when he is needed next. Never "soon".

## Task manager brief (fill the <>)

```
[<model> <effort>] Brief from the main manager (<my session name>): you are the task manager for "<name>".
WHERE: worktree <worktree path>, branch <branch>, target <production|working branch>, base <base branch>, working branch: <the working branch (ap-main-<name>), never derive it again>. Main repo <main repo> only for ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh.
TODO LINE: <the todo line, as agent-file.sh show prints it>
CHECKS: <the BLOCK list of the todo line> (R8; the tool adds its own blocks from the real diff before merge)
GOAL: task manager <name>: done when DONE PASS or DONE FAIL is written under === REPORT === in agent_state.txt and the branch is pushed, or a "QUESTION:", "MOCK READY" or "CLOSE CASE" line waits for an answer, or you saved agent_state.txt after an AUTO CLEAR notice
FEATURE: <requirement, 5 to 10 lines. Files to produce. What the user sees. Validation rules.>
STEPS (at the start of each step run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" <stage>`; on another machine it writes a STAGE line into agent_state.txt and the main manager's watch carries it):
 0 brief: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" brief, then save this whole brief into agent_state.txt in your worktree, first action (S8), then one blank line
 0b kick-off: read the brief, then send the main manager your questions as QUESTION: lines (agent-file.sh state add) and wait for the answers before step 1; the main manager answers what it can and asks the owner only the rest (W1). After that, default + log (W1)
 1 register: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" register, then ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree set "<worktree path>" "<name>" working
 2 mock: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" mock; first, for a new page or a whole-page re-layout (W2): commit mock/<name>-mock.html, send me the path, STOP until "mock yes"; on another machine also append one line "MOCK READY <name>: <mock path>" to agent_state.txt in your worktree
 3 tests: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" tests; write the failing tests yourself (W3; the EXAMPLES TEST block), commit
 4 workers: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" workers; after each verified slice ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" workers <i>/<m> (i of m slices done). Agent subagent_type worker, description "<name> Worker <n>: <slice>", as many at once as the memory rule admits (S3), each gets named files + one test command (W4); every worker brief starts with your own `[<model> <effort>]`. Check RESOURCES before each spawn (S3, S4). The board records each worker by itself (bin/agent-guard.sh). Only in a session without hooks (plain or cloud): ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worker on <n> "<slice>" when it starts, ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worker off <n> when it ends
 5 verify: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" verify; every worker result yourself; run the blocks of the task (`agent-level.sh check --base <ref>` lists them, one `agent-file.sh check` line per block). Defect → back to the worker with evidence. Set status final: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree set "<worktree path>" "<name>" final
 6 push: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" push; commit, git push -u origin <branch>
 7 report: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" report; done, set status final (R7), stay idle
REPORT: append it to agent_state.txt in your worktree (`agent-file.sh state add`) under "=== REPORT ===", nothing else. First line "DONE PASS <name>" or "DONE FAIL <name>: <why>". Then Result (test count), What changed (files), What to decide. Then the task's CHECK lines (copy of its agent_state.txt CHECK lines), each indented by two spaces (state add refuses a line that starts with CHECK). Then the E2E click path: start command, URL, exact clicks, expected result, how to restore. Then one line: TIME: est <n>m, actual <n>m, wait <n>m (actual = agent work only; wait = mock gate, owner question or review, hold, suite run). Then one line: FACTS: type <page|server|script|docs|cloud|app|data|mixed>, lane full, mock <yes|no>, bounces <n>, workers <n>, tests <n added>, scope adds <n>.
ASK: append a line starting "QUESTION:" to agent_state.txt (`agent-file.sh state add`). Wait max 10 min, then default + log + continue (W1). Mock gate always waits. A question for later: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh park add "<question>"
HEARTBEAT: every 15 min run `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh heartbeat "<name>" <step 0-7> "<what runs now>"`; the work minutes are computed, never typed; it writes the one valid line "HEARTBEAT <name>: step <n> of 7, work <m>m, <text>" into agent_state.txt (never write it by hand).
CLOSE: on "close case" from me or the human: start nothing new, commit + push (WIP if unfinished), report into agent_state.txt (`agent-file.sh state add`), first line "CLOSE CASE <name>: finished" or "CLOSE CASE <name>: unfinished", then done, left + next steps, tests, click path, ideas, TIME. Wait for my decision; never close yourself.
STATE: write agent_state.txt after every step (S7, S8): one line = `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh state add "<line>"`, never echo >>.
NEVER: Claude in Chrome (W5). Product code. Files outside the worktree except via ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh.
```

## Cross-repo brief (W12, fill the <>)

Relaying an owner order (W12): the three lines of `${CLAUDE_PLUGIN_ROOT}/bin/agent-owner-order.sh line --quote "<his exact words>"` go first, above this block; the receiver runs its `check:` line.

```
[<model> <effort>] CROSS-REPO TASK <name> from <repo>
WHAT: <requirement, 5 lines max. What the peer repo must build or change.>
CONTRACT NEEDED: <what the sender must get back: endpoint, fields, errors>
REPORT: SendMessage to "<sender session name>". First line "DONE PASS <name>" or "DONE FAIL <name>: <why>". Then the contract.
ASK: first line "QUESTION:". Wait max 10 min, then default + log + continue (W1).
HEARTBEAT: every 15 min, one line "HEARTBEAT <name>: <what runs now>".
```
