# PRINCIPLES

- Read first. Binding for every agent in this repo.
- Output shape: section E. Human language: the Language setting (H2).
- Settings live only in /plugin -> Installed -> auto-pipeline -> Configure (S1). Other numbers are fixed constants in `bin/agent_conf.py`. Never hard-code.

## A. Repo

R1. One flow, two lanes
- Before the flow: the main manager writes the requirement doc, the owner approves it
- Full flow, in order:
  1. Todo line + estimate
  2. Mock if the task has UI
  3. Worktree + task manager
  4. Failing tests first
  5. Workers build
  6. Verify
  7. Push
  8. Acceptance blocks (R8)
  9. Merge + cleanup
  10. Todo done
- Task size picks who does the work: small task = one subagent in its own git worktree (fast lane); it writes its example tests and runs its blocks
- Big task (over 2 hours, several slices) = a task manager (full lane)
- Which checks run follows the triggers only (R8), never the lane
- A small logic task never opens a task manager just because it needs a test
- A small task that grows (past 2x its estimate, or it needs a second slice): the subagent stops and reports; the main manager opens a task manager that goes on from its branch

R2. Secrets
- Live in `.secrets/` (git-ignored)
- Read only
- Never write, print, copy, commit

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
- Done → agent_completed.txt: date, name, what, then one `data` block written by `agent-file.sh`: repo, type, lane, mock, est, work, wait, clock, bounces, workers, files, lines, tests, adds. No test results, that is report material
- No other task tracking
- The housekeep pass never closes a todo line: it flags one whose branch is merged into origin/main, or one that is stale (no worktree line, no open wait, quiet longer than housekeep_interval_min)
- All four `agent_*.txt` files are written only through `./agent-file.sh`. No agent for that, it costs tokens
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

R8. Check blocks
- Owner 2026-11-25: "only do the necessary thing when needed, dont do extra thing. and dont do less thing"
- No levels: each check is a block with a trigger; a task runs the blocks whose trigger fires, nothing else
- The one table, source `bin/agent_blocks.py`; this table, the skills and the quiz are tested against it:

| Block | Picked | Trigger | What runs | Owner signs |
|---|---|---|---|---|
| DIFF SCAN | tool | every task | the tool scans the diff: files outside the task's scope, deleted or skipped tests, secrets, debug leftovers | no |
| BUILD | tool | code changed | lint + type-check or syntax check of the app that was touched | no |
| RELATED TESTS | tool | code, text or rule files changed | only the tests that import or name the changed files. Style-only change of a shared component: the component's own tests. Rule text: the tests that name the changed section | no |
| MODULE TESTS | tool | code used by other modules changed, or dependencies, lockfile, CI or test config changed | the tests of every module that uses the changed code; a dependency, lockfile, CI or test-config change: the tests of every module | a dependency, lockfile, CI or test-config change |
| GUARD TESTS | tool | code or text changed | the repo's tree-scanning tests (listed in the repo file) | no |
| DB CHECK | tool | a migration or schema file is in the diff | dry run on a data copy, counts before and after, rollback plan | only when the migration changes or removes data or columns |
| DATA CHECK | tool | a script that changes live data | preview of the rows (the count must match the expected one), backup | yes |
| CORE REVIEW | tool | a core path of the repo is touched (money, permission), or the brief says who can see or do what changes, or a posting rule changes | an independent read-only agent reads the logic against the rules the owner approved | a permission change |
| DIFF READ | brief | text, style, a simple move (banner -> toast) | someone who did not write it reads the diff. That is the acceptance. A 5-minute task stays a 5-minute task | no |
| EXAMPLES TEST | brief | behaviour or logic changes | failing tests first, written from the examples in the requirement doc; they cover the fitting lines of the repo's edge list. Money and permission rules: the owner approves the examples before code | no |
| FLOW CHECK | brief | a behaviour a user can reach changes | someone who did not build it runs 1 normal path + 1 error path | no |
| UI CHECK | brief | new page, re-layout, size or responsive change | compare with the approved mock or the before screenshot, desktop and phone width. Style change of a shared component: look at a few different usages only | no |
| REAL DATA COUNT | brief | a rule, limit or validation is added or tightened, or a list, print or export changes | one read-only count on real data: how many existing records would be refused, and the largest real size. No read access: skipped with one printed line, never silently | no |

- Picked tool: `agent-level.sh check --base <ref>` decides them from the real diff, no judgment
- Picked brief: dispatch picks them from what the owner approved: `todo add ... --checks "<BLOCK>,<BLOCK>"`
- Two passes: the brief blocks at dispatch; before merge the tool recomputes the tool blocks from the real diff
- Blocks are only added; removing one needs a verified owner order: `todo checks <task> --remove <BLOCK> --owner-quote "<his words>"`
- One result line per block: `agent-file.sh check <task> "<BLOCK>" pass|fail --by <who> --evidence "<text>"`
- The merge gate `agent-file.sh checks gate <task>` refuses while a planned block has no pass line
- DIFF READ, FLOW CHECK and UI CHECK pass only by someone who did not build the task: not the builder (the todo line's builder or its LAUNCH records)
- No task runs the full suite (owner 1A 2026-11-25): MODULE TESTS is the largest per-task check
- OWNER SIGN is planned when a sign fires: MODULE TESTS on a dependency, lockfile, CI or test-config change, DATA CHECK, DB CHECK on a data change
- Dispatch plans OWNER SIGN with CORE REVIEW when the brief changes who can see or do what
- BUILD and GUARD TESTS run per task only when their measured time in agent_repo.conf is under `check_budget_s` (60 s)
- Slower = heavy: it runs in the net; a heavy BUILD takes the heavy-test slot (S5)
- REAL DATA COUNT with no read access: skipped with one printed line, never silently
- Outside tasks, the net: NIGHTLY RUN, all tests once every night in the background on the heavy-test machine (`agent-nightly.sh`); it gates nothing
- A failure the nightly finds that the causing task's own RELATED or MODULE run did not find is a selection miss: one line, the test and the merge (`agent-nightly.sh --misses`)
- After two weeks the owner reads the selection miss count and decides whether the nightly goes too
- The watch's housekeep pass starts it once a day after 22:00 (`nightly_hour`) when no heavy test runs; no watch alive: the next session start, when the last run is older than 24 hours
- A release needs the last nightly on that main to be green, or one background run (`agent-nightly.sh --release-ok`); no other pre-release run
- RELEASE SMOKE after every release: a fresh session uses the released version for real (start, one subagent launch and finish, the user-facing flows that changed)
- Four kinds of request, one line each:
  - Refactor (no behaviour change): BUILD + RELATED TESTS; no new examples, the existing tests are the acceptance
  - Urgent fix (production is broken): the smallest fix, the same triggers; a verified owner order may move a block to right after the release, never drop it
  - Rollback: back to the last green commit; BUILD + RELATED TESTS of the reverted files; a database change follows its written rollback plan
  - Research only (no diff): no blocks; the report is the deliverable
- Repo facts live in the committed `agent_repo.conf`, written by init and kept by agents, never by the user: core paths, guard tests, test commands, the edge list, real-data access
- After each bug fix the fixing agent asks "which example would have shown it" and adds one line with `agent-file.sh edge add "<text>"` when the list lacks it
- A second agent's opinion only for CORE REVIEW, or when someone wants a tool-triggered block removed
- A requirement table copies its defaults from the released template and lists every changed default for the owner

## B. Work

W1. Finish in one run
- Never wait for the human
- Exception, kick-off round only: a task manager reads its brief and asks the main manager its questions before starting; the main manager answers what it can and asks the owner only the rest. During the work this rule holds again: default, log, continue
- Unknown → pick default, log it, continue
- Only owner-level or irreversible calls stop the line
- A rule and reality collide → report the collision, never route around it
- New ideas → `agent_ideas.txt` (R6), never in the work or the report, except the CLOSE CASE report (W13), which lists them too

W2. UI
- Clickable mock first (prototype artifact)
- Start from a screenshot of the existing real page (Claude in Chrome); change only what the task changes. Never imagine a page from scratch when one exists. Same layout, components, theme
- No existing page to screenshot → the mock follows the project's current style (theme, components); the agent proceeds without asking
- Human says yes
- A mock only for a new page or a whole-page re-layout; the approved mock is what UI CHECK compares with (R8)
- The approved mock is the acceptance criterion of the task
- Then real code

W3. TDD
- Task manager writes the failing tests → worker writes code → tests pass
- Workers never write tests. Task managers never write product code
- No test = not started
- Full lane only; fast lane → R1

W4. Multi-agent tests
- Tests are organised module → feature
- No task runs the full suite (owner 1A 2026-11-25). Which tests run follows the blocks (R8): RELATED TESTS and GUARD TESTS per task; MODULE TESTS only when its trigger fires
- Every test run goes through `agent-test-run.sh`: light or heavy by measured weight (S5)
- The main manager and the merge deputy never re-run tests the task manager already passed. Only on a merge conflict: test the conflicted part
- After a bounce: re-run only the tests that failed, not the suite

W5. Web UI testing
- Claude in Chrome, not Playwright, on orca and plain
- The check deputy (`agents/check-deputy.md`) drives the browser for FLOW CHECK, UI CHECK and RELEASE SMOKE, one at a time
- Others write the click path and hand it to the main manager, who sends the check deputy
- Unit tests are not proof of a flow a user can reach: FLOW CHECK is (R8)
- Builders never verify their own work: they ship a click path, someone who did not build it drives the UI
- What a browser cannot prove goes on a standing "needs a real device" list, never counted as verified
- UI CHECK: the real page against the approved mock or the before screenshot, item by item (layout, content, states, behaviour), desktop and phone width; list every difference
- A layout, content or behaviour difference = not done, back to the builder
- A difference from the real UI theme (colours, fonts, spacing tokens) is fine: keep the real theme, list it as "theme difference" in the report
- The owner says pass = pass; agents follow his final decision. Only a critical problem (crash, wrong data, security) goes to him
- Ask `agent-runtime.sh browser` first: chrome, headless or none
- cloud → headless Chromium via Playwright, the extension can never reach a VM
- none → print the click path under NEEDS HUMAN E2E and stop, wait for the human. Never silent, never forever

W6. Roles
- Main manager (Opus 5.5, xhigh) = the main chat. Assigns tasks, talks to the human, reports, accepts decisions, brainstorms. Nothing else
- Fast-lane deputy (Sonnet 5, medium) = `agents/fast-lane-deputy.md`, new one per small task: works in its own git worktree, writes the example tests of a small logic task, runs its blocks, pushes a branch
- Merge deputy (Sonnet 5, medium) = `.claude/agents/merge-deputy.md`. Merges, then deletes branch and worktree
- Check deputy (Sonnet 5, medium) = `agents/check-deputy.md`, read and browser tools only: DIFF READ, FLOW CHECK, UI CHECK, re-checks after a bounce, RELEASE SMOKE; a verdict with evidence, the main manager decides
- The main manager stays free for the human: it runs no long check itself; it sends the check deputy and gets a short verdict with evidence
- Task manager (Opus 5.5, xhigh) = one agent per big feature, in its own worktree (exception: human-direct, W10). Writes the tests, briefs workers, judges, verifies every worker result before reporting done to the main manager. Never writes product code
- Worker (Sonnet 5, medium) = `.claude/agents/worker.md`, subagent of a task manager. Writes code until the task manager's tests pass
- Managers never write product code. A defect goes back to the worker that wrote it, with evidence
- A main manager fix order to a task manager has a fixed shape: where, what is seen, what is expected, evidence (screenshot). The task manager reassigns a subagent
- Names: `bin/agent-name.sh` (SessionStart hook) shows `<repo> Manager`, `<feature> Task Manager`, `<repo> Helper - <Task Name>` (human-direct); it is the SendMessage address after `claude --name`, `/rename` or a resume. `Agent` descriptions: `<feature> Worker <n>: <slice>`, `<task> Deputy`, `<feature> Merge`

W7. Big feature (> 2 hours)
- Before opening a worktree: idle or done worktrees > 0 → deputy cleans them all first (W8)
- A worktree needs Orca. `agent-runtime.sh kind` picks the shape
- On Orca: read Orca's own guide first, `orca skills get --topic orca-cli --full --json`. Flags change: `orca agent-context --json` is the current schema
- Then new worktree
- One task manager inside it
- Task manager spawns workers as needed
- plain or cloud → no worktree, no second terminal. Main manager runs the task itself with `Agent` subagents, up to the Max agents setting
- Every spawned agent counts toward the Max agents setting (S6). The main manager does not
- One agent = one worktree = one branch = one terminal. Push at every stage

W8. Merge and cleanup
- Deputy merges into the integration branch
- The merge deputy runs `agent-file.sh checks gate <task>` first: GATE REFUSED → no merge, the task goes back
- Deputy deletes the branch (local + remote) and the worktree right after merge
- A failed run after the merge is undone with `git reset --merge ORIG_HEAD`, never --hard (that wipes the uncommitted agent_*.txt of the main checkout)
- Every merge ends with cleanup, in every case: a task manager pane, a subagent's git worktree, a human-direct Helper (its own pane stays), a worktree on another machine (agents/merge-deputy.md)
- The worktree line of a merged task is always removed or rewritten at merge, also when the folder stays
- human-direct protects only the human's own session pane; the sweep never closes a Claude pane, only a shell pane that never got a prompt and is idle over 30 minutes (`unused_pane_min`)
- The sweep prunes a LAUNCH record whose pid is dead or whose pane is gone; its table never lists main or the release branch; a worktree with a live LAUNCH record is "live agent"
- The plain list shows what --apply would remove; --apply is main manager only
- Never skip cleanup
- Main manager verified + waiting for the owner's yes → close the task manager pane, remove its worktree, keep the pushed branch, start the next task
- Owner yes → merge deputy merges the branch. Owner no → a new task manager from that branch. Goal: work all night, RAM stays free
- Clean up only after the merge is verified
- Deputy runs `./agent-file.sh worktree rm <path>` and `./agent-file.sh todo done <name>` with the facts from the main manager and `--merge <commit>`
- Sweep: `bin/agent-cleanup.sh --apply` after every merge, at session start and when the last open task closes (todo empty, no live worktree). The scripts run it, no loop
- Housekeep: every housekeep_interval_min minutes (default 120, 0 = off) `agent-watch.sh --all` runs `bin/agent-housekeep.sh --apply`, then this sweep. Plain and cloud: no watch, run it by hand
- The housekeep pass runs `agent-file.sh state trim` on the main repo's agent_state.txt before it writes its block (S8)
- The main manager reads the HOUSEKEEP block in agent_state.txt at its next activity. Per suspect: `idea rm <n>` if done or voided by a recorded owner decision, else `idea keep <n>` (still wanted)
- It then acts on the other flags of the block
- Main manager only. Task managers, Helpers and workers never run it
- Own repo only: this machine and every paired Orca machine
- Removes only safe items: merged into origin/main, no live agent, no uncommitted or unpushed work, no working/final/human-direct line
- Everything else is never deleted: one table to the human (what, where, why kept, suggestion)
- A done pane (finished, idle) in a kept worktree: closed when its task is done or dropped, or its line is gone and its branch merged; else one kept row
- A paired machine unreachable → one line, skipped. Never hangs the start

W9. Task routing (main manager, before every dispatch)
- Read `agent_worktree.txt` first
- Small task (fast lane) → a new deputy subagent in its own git worktree (Agent isolation worktree); it pushes a branch, a merge deputy merges it
- Several small tasks run side by side and never share a checkout (owner 1A 2026-11-25; 21 tasks done this way, median 22 minutes)
- Task touches a live worktree's module → that worktree's task manager
- Big task, and a live task manager has capacity → that task manager
- Task manager in final stage (compiling worker results) → do not disturb. Hold the task until it finishes
- Otherwise → new worktree (W7). Never an Orca worktree and a task manager for a small task
- `todo done <X>` releases every task queued after X
- The main manager runs `agent-file.sh next` at every wake (a report, a watch signal, a human message) and dispatches what can start: a free slot under the machine caps, RAM under the cap, no open task on the same files
- A task the owner already approved needs no new question
- Shared first: before parallel features, find the code they share (models, components, APIs); the shared part is its own task, merged first; features that need it wait (`todo wait <name> on queue --after <task>`)
- The todo line comes first: `todo add` before the worktree, the pane or any agent. The guard refuses a main manager launch for a task that is not open (W14)

W10. Second session in the same repo
- One main manager per repo. `agent-start.sh` keeps a lock in the shared git dir: pid, date, session id, terminal
- Lock owner alive → this session is a task manager (human-direct). Never a second main manager
- Its start text names the main manager: pid, `<repo> Manager`, terminal
- Human wants this session as main manager → the human types `! agent-start.sh --take-over` (full path in the start text); the agent never runs it. The old one is told once, never main again by itself
- Human-direct = only a session the human opened by hand. Agent-spawned agents are never human-direct. They run fully by agent, no human in the loop
- At start: the script adds a line to `agent_worktree.txt` (status human-direct). Also send the main manager a direct message if a channel exists (Orca)
- Will change files → open its own worktree first (W7). Only looking → no worktree
- Human talks to it directly for now. All task manager rules still apply
- Human says "finish" or "report to main manager" → report done + click path to the main manager, then act as a normal task manager. Merge deputy cleans up
- Finished with nothing to merge → main manager runs `./agent-file.sh worktree rm <path>`
- The main manager closes every human-direct session after the human says finish: `orca terminal close --terminal <handle> --json`. Nothing stays parked
- Lock owner dead → take over as main manager, run recovery (S7)
- Talk between sessions: `ListAgents` → find the peer by its name (W6), not listed → the row named after its folder (`<folder>-<xx>`) → `SendMessage` to that name. Two share a name → add the `[ref]` ListAgents prints. Reply to the `from` name. First line of every message = one clear sentence
- Open a second session with the same permission mode and effort as the main manager (`<mode>` from `agent-settings.sh get permission_mode`, effort from the "Models: Main manager model" setting, form model:effort): `orca terminal create --worktree path:<repo> --command "claude --name '<repo> Helper' --permission-mode <mode> --effort <effort>" --json`, then `orca terminal wait --for tui-idle`
- New terminals (dispatch, resume, a Helper, a city click) use the "Permissions: Permission mode" setting, read with `agent-settings.sh get permission_mode`
- Task name: every new or switched task, a plain question too, gets its name first, even before the quiz PASS -> run the full-path `<plugin>/bin/agent-file.sh helper-task "<Task Name>"` from the start text, alone, from the project folder (never cd, never chain it); 2-4 English words, Title Case, the work, not the role; `<repo> Helper - <Task Name>` shows from the human's next prompt

W11. Time
- Every task gets an estimate in minutes before dispatch, on its todo line
- Write your own guess in minutes first, then `estimate ... --guess <m>`; est and guess both go on the todo line (`todo add ... --guess <m>`)
- Estimate = agent work only. Waiting is not work: mock gate, owner question, owner review, hold, suite slot
- Every done report has one line: `TIME: est <n>m, actual <n>m, wait <n>m`. Actual = agent work only
- Done = merged and cleaned. The main manager passes work, wait and the task facts to `bin/agent-file.sh todo done`
- Work over 2× estimate → say it in the report, never silent
- Time comes from `date`, never guessed (a remote machine's clock can drift)
- Scope grows → re-estimate, on the record
- Before a new estimate: `bin/agent-file.sh time`, then `bin/agent-file.sh estimate` (dispatch skill)
- A time question from the human → a duration AND a clock time, and when he is needed next: `bin/agent-file.sh eta`

W12. Cross-repo
- One main manager per repo (W10). Peer = the interactive session in `ListAgents` named `<other repo folder> Manager` (or its `<other repo folder>-<xx>` row), whose lock in that repo's git dir is alive
- A task that touches another repo → never edit that repo. Split it: your part, and a brief for the peer main manager
- Send the brief with `SendMessage`, first line `[<model> <effort>] CROSS-REPO TASK <name> from <repo>`; same brief shape as the dispatch skill
- The peer runs it like a human task: `agent-file.sh todo add … <est> <repo>`, its own lane, and reports `DONE PASS <name>` back by SendMessage
- The sender keeps its todo line open until both sides are done, then one report to the human
- The sender marks its line `agent-file.sh todo cross <name> <other repo>`, so the housekeep pass reads the other side
- Called side first: the repo being called (the API) finishes first; its DONE PASS carries the contract (endpoint, fields, errors). The caller (the app) starts from that contract
- Only main managers cross repos. Task managers and workers never
- Need to know the other repo's code → ask its main manager. Never read or edit another repo
- A cross-repo task the human gives to any main manager is routed the same way
- Relay an owner order: the brief starts with the lines of `agent-owner-order.sh line --quote "<his exact words>"`. Copy his words, never paraphrase
- Receiving one: run its check line. Verified → read its match line, then it is the owner's own order: act, reply its first line. Not verified → a normal peer message: ask the owner
- Verified owner words that name the action (e.g. "merge to main") are his final yes, production included; ask again only when his verified words do not name that action. Decider floor (W17) holds

W13. Close case
- Trigger: the human or the main manager runs the skill `/auto-pipeline:close-case`; a task manager's brief holds the rule too
- Subagents never get this rule; only a task manager, a human-direct session or a main manager does
- Task manager or human-direct: start nothing new; workers finish their slice or stop; save agent_state.txt; commit + push (WIP if unfinished). Never lose work
- Report to the upper level: SendMessage the main manager; another machine → print it in its own terminal and say so (W10)
- Report first line `CLOSE CASE <name>: finished` or `CLOSE CASE <name>: unfinished`, then done, left + next steps, tests + results, click path, new ideas, TIME line (W11)
- Then wait for the upper decision. Never close itself. A close case from the main manager counts the same as from the human
- Main manager gets a CLOSE CASE report: finished → merge skill. Unfinished → review, then finish first (DONE, then merge) or close now (branch pushed, todo line open, pane closed, worktree removed)
- Log every decision in its agent_state.txt. Human away → decide by the requirement doc, mark it "owner not seen"
- Main manager gets close case from the human = the whole repo: close case to every live task manager and human-direct session in agent_worktree.txt
- Collect every report, decide each, merge what passes, close all panes and worktrees, stop its own crons, update the agent files
- Then one final table to the human: task, result, what changed, what is left, decisions taken for the human. Nothing dropped (the H3 five-row cap does not apply)
- After the table the main manager asks the human, in his language: clean this session for the next round, yes or no? No, or no answer: nothing changes
- Yes: `agent-start.sh --clean` (archives agent_state.txt, writes a short fresh one, says what still runs), then `/clear`. Same main manager, same lock, same name
- Rare, the human wants this session to stop being main manager: he types `! agent-start.sh --release`; the agent never runs it. The next new session is main manager, never Helper

W14. Todo board
- Trigger: the human runs the skill `/auto-pipeline:todo`; the skill holds this rule per role
- One script, no agent: `bin/agent-file.sh board`. Show its table as printed, every row, then the decide section (H3)
- Main manager: the whole repo. Task manager or Helper: `board --self`, its own task and its workers only. Subagents never
- Rows: open tasks, waits on the owner (mock check, owner question, owner review), `OWNER TODO:` and `PARKED:` lines. Each: task, what in a few words, status, where, est, work, wait, progress, done by
- Status of a wait: `waiting <who> · <what> · waited <n>`, held `hold · <what> · waited <n>`, queued `queue · after <task>`; no stage, no wait: not started. Time cells `-` (not started keeps est)
- Sort: waiting on the owner, running, waiting on others, queued and not started, held, OWNER TODO, parked questions last; oldest first in each group
- Times come from the files, never guessed. Work counts from the first stage minus later waits. Waited: since a run of waits began. Done by = now + est - work; over: by progress, else 超出 <n>m
- Progress: `agent-file.sh todo stage <name> <stage> [i/m]` at each step boundary. Task manager: brief register mock tests workers verify push report. Main manager: e2e merge
- Stage weights are fixed (`bin/agent_conf.py`)
- Live: `board --watch` · `statusline` on or off, 5 lines at most (a warning line counts), queued/held/not started own row if room, rest `+N queued/held`. Language: the Language setting
- Record as it happens: `todo wait <name> on <kind> ["<note>"] [--who <name>] [--after <task>]|off` at every mock check, owner question, owner review, hold, queue; `todo where` at dispatch
- `park add` for a parked question (H1); `OWNER TODO:` lines are written with `agent-file.sh state add`
- `agent-guard.sh` records launches by task. The "Rules: Todo before agent" setting, on (default), refuses a main manager launch naming no open todo task: `todo add` first; off records only
- `worker on`: no hooks only.

W15. Watch
- After a watch wake the first action is to start the watch again, then handle the signal
- The watch also wakes the main manager when a slot is free and a task is queued (WATCH SLOT)
- A board warning (watch not running, not confirmed, a pane without a task line) reaches the main manager through `agent-file.sh next` and the board warning hook; it reacts in the same turn
- Stall detection is the watch: each sweep reads the pane screen and the `agent_state.txt` file; 3 sweeps with neither changed = STALL. The same watch runs the housekeep timer (W8)
- Verify every launch within 2 min
- One `agent-watch.sh --all` in the background (Bash run_in_background) watches every task manager, local and on another machine: its pane and its worktree `agent_state.txt` (a report goes under `=== REPORT ===`); restart it after each wake
- A task manager's HEARTBEAT, ACK, report and question go into `agent_state.txt` only, never SendMessage; only DONE PASS, DONE FAIL, QUESTION:, MOCK READY, CLOSE CASE and the watch's STALL and LOST wake the main manager
- The watch carries a task's stage to the main repo from the newest STAGE line or HEARTBEAT step (0-7 = brief to report); the heartbeat's work minutes and text go to the board's progress cell
- A manager at its idle prompt while its own background run goes (pane shows shells or monitors, or its newest state line says started, for watch_quiet_min) is not a stall
- Long text to a task manager: `agent-file.sh tell <task> "<msg>"` (the block goes into its file, one pointer line to its pane, receipt checked)
- Start and resume print the `agent-watch.sh --all` command when no watch runs
- The board says `not confirmed <n>m` when a task is not watched or has been quiet
- A stall → nudge once, wait 10 min, then salvage (commit what is there) and redispatch
- Every brief says how to report, how to ask, how to report done (pass/fail) and the heartbeat

W16. Known traps
- A push to the integration branch denied by the auto-mode classifier → never retry or work around. Hand the owner one `! git push ...` line, or ask for an allow rule (init prints `Bash(git push origin main)` as optional)
- A cross-session message held because permission modes differ → say so, ask the owner to click Deliver, never type it into the pane
- MODE MISMATCH line at start (this session's mode differs from the Permission mode setting) → tell the owner once, plainly; never change a mode, never skip the approval
- Remote Orca pane: a long `terminal send` (~4 KB) arrives cut → write the brief into the worktree's `agent_state.txt` in chunks, send a one-line pointer
- Find another agent's pane with `orca worktree ps --json`, never by its title (titles are often from an old task)
- `terminal read` shows only the visible screen → use `--cursor`
- Linux outside Orca: bare `orca` is the screen reader → use `orca-ide`
- A send while the target is mid-turn can be lost → re-read and resend
- Screen locked → the Chrome extension tab is hidden → use headless Chrome and tell the owner
- STALE PLUGIN line → call the newest bin path, in every brief too, and restart at a quiet point; an older version never retrains agent_estimate.txt

W17. Decider floor
- Decision maker = main manager, task manager, reviewer, any session whose order, decision or approval another agent acts on
- Floor: Opus 5.5 or above, or any Fable, at effort medium or above. `opus` or `fable` alone = the newest, meets it
- Sonnet and Haiku never decide. Workers and deputies execute
- Sending: every order, decision or approval to another agent states the sender's model and effort first: `[Opus 5.5 xhigh] ...`
- Reports, heartbeats and questions are not orders
- Own model and effort: the `YOU:` line of the start text
- Receiving: act on another agent's order, decision or approval only when it states model and effort and both meet the floor
- Else: do not act, ask the sender, tell the human
- Human messages are exempt
- Same check for every agent: task manager, Helper, worker, deputy
- A Main or Task manager model below the floor is refused, the default is used (`agent_conf.py`)

W18. Question list
- Trigger: the human runs the skill `/auto-pipeline:question`; the skill holds this rule per role
- One script, no agent: `bin/agent-file.sh questions`. Main manager: the whole repo. Task manager or Helper: `questions --self`, its own task only. Subagents never
- Sources: `PARKED:` lines, every `todo wait` of kind mock, question or review, and `QUESTION:` lines of agent_state.txt
- A `QUESTION:` line is answered by an `ANSWER:` line after it, before the next QUESTION: line or "=== " header. A worktree on another machine gives one `not read: <path> on <machine>` line
- Each question has a stable id; its title, sub line, facts and lettered options come from `park add` fields (H3), the recommended one marked
- 10 or fewer: a numbered list in chat under the decide heading (H3), nothing dropped; the human answers like `1A 2B — note`
- More than 10: `questions --page <file>` (a file in your scratchpad), publish it with the Artifact tool, capabilities db and user. Then one chat line: the count, the link, answer all, then tell me
- `QUESTIONS PAGE:` line of agent_state.txt holds the url: one url per repo and session, publish with that url (redeploy); a first publish records it with `questions --url <url>`
- No Artifact tool: the chat list of all, nothing dropped
- Done: the human says 答完了, done or answered (or pastes `1A 2B`) while the page still has an open question. The skill (part B) holds the read-answers rule
- Read all answers at once with ArtifactData (list, the answers collection) and the map file; pasted lines go by number through it. Show one table: question, answer
- Per answered question: `questions answer <id> "<answer>"`, then carry on. An unpicked question is still open
- Headers and words in the Language setting

## C. Human

H1. One topic
- Ask only about the current task
- Edge-case question + read access to the real data → count first: how many records or companies it touches. Read-only, aggregates only, name the DB the count came from
- Count is 0 or tiny → take the simplest default, state the count in one line, do not ask
- No read access → ask as before, say the count could not be checked. Never guess a count
- Prefer the simplest change that gives the same result over machinery the data does not need
- Park other questions
- Show them at the end, one table
- Ask everything while the human is here, in one batch
- Human gone → never block, park it. On return lead with one table: issue, evidence, blocks what, interim default, decide, recommendation

H2. Words
- Short sentences
- Common words
- Jargon only for code names
- Talk to the human in the language of the Language setting. Docs, code and rule text stay English
- Never cite a rule by its code (W6, S8) to the human. Say what the rule means in plain words

H3. Report
- Result (pass/fail)
- What changed
- Every report, job summary, recap, proposal or audit to the human ends with a decide section
- Heading in the Language setting: zh `## 要你决定`, en `## To decide`, other languages a short translation of "to decide"
- Open questions numbered, each with a recommendation (zh `建议`, en `Recommendation`)
- Every question to the owner has a number in front; numbers never repeat within one message, and an open question keeps its number in later messages
- When every question is answered, the next new set starts again at 1. While any is open, open ones keep their numbers and new ones continue after the highest open number, never renumber
- Every open question is repeated in the decide section of every reply until the owner answers it, even when the reply gets long
- Each question stands alone: a reader who sees only that line knows what it is about and can decide
- A named thing (PR, task, branch, ticket, file) gets what it is in a few words: `#305 (stock lock settings page)`, never a bare number, tag or code name
- A question names every task/PR/ticket by id AND its title, + the state + what is asked, e.g. "Task t10211 - Milah Enterprise invoice duplicate due to calculation error, pending approval to merge to main". Never an id or code alone ("PR 1211 ready, approve?" is wrong). The owner must be able to decide from that line alone, even waking up cold
- Per question: what, why it needs the human now, one line of evidence, then the recommendation. One or two lines, no long explanation
- Nothing open: keep the heading, one line: none (zh `无`)
- Every question the main manager puts to the owner in a decide section is recorded with `park add` (--why --evidence --options --rec if known), removed when answered (`park rm` or `questions answer`)
- Few numbers. One table at most, five rows or fewer, unless the human asks for the full list
- Nothing else, except the decide section

H4. Tables
- Comparison, series, feature list, task list, options → table
- Never prose

## D. Auto setup

S1. Settings
- Settings live only in /plugin -> Installed -> auto-pipeline -> Configure, user level (Claude Code keeps them in `~/.claude/settings.json` `pluginConfigs`)
- Why: the plugin is a developer workflow, one setup for every repo
- Configure holds the 16 settings
- Repo facts (core paths, guard tests, test commands, edges, real-data access) live in the committed `agent_repo.conf` at the main repo root, not in Configure (R8)
- `/auto-pipeline:settings` shows them as a table and never changes them
- No settings file in a repo, none on a machine: start and init move an old repo or machine settings file into Configure once (keys still unset there only, a value the human set is never overwritten) and say each move
- A cloud session (no plugin) runs the defaults
- Also holds the watch and housekeep config (`housekeep_interval_min`)
- Setup: init offers to merge the permission rules into `.claude/settings.json` (`agent-init.sh --add-permissions`); agents never hand-edit JSON. Manager default `opus-5.5:high`; `xhigh` is an install choice
- Setup: init asks all vs selected repos; `agent-init.sh --scope` writes the files; agents never hand-edit JSON

S2. Resume script
- One command
- Loads context, memory, agents, saved sessions (S7), and prints the watch command when no watch runs

S3. Resource guard
- Before new agent or heavy process: check free RAM and CPU
- Low → wait or run smaller

S4. Usage cap
- RAM and CPU each ≤ 80%
- Over → no new job to any agent until it drops back
- Over → run `bin/agent-resources.sh relief` first, then wait
- relief stops only what the pipeline owns: `agent-watch.sh --all` processes left by tests, watches of repos with no live main manager
- The sweep (W8) runs `agent-resources.sh stop-leftovers`: this repo's orphan watch and finished test watches only, no table
- A task manager over cap parks: commit, write state, set idle; the main manager closes its pane; resume brings it back
- The human's apps, other repos' sessions, Gradle or node runners: never killed by an agent. One table to the human: process · MB · CPU · what · suggestion
- Setting "Load: Max memory %" = 80

S5. Heavy tests
- A test run is light or heavy by measured weight, never by its name: `agent_repo.conf` keeps seconds and peak MB per test command or module group (`weight.<key>`); init measures, each real run through `agent-test-run.sh` updates them
- Light (under 120 s and under 1 GB): no slot, on the agent's own machine, several at once, under the normal RAM guard (S4)
- Heavy: the heavy-test slot on the heavy-test machine. Unknown weight counts as heavy the first time
- Start one; once it runs and has settled, start another only if RAM is still more than 50% free; never two at the same moment. The Heavy test slot/time setting is the ceiling, RAM decides below it
- Every test run caps its own parallelism, e.g. `jest --maxWorkers=2`, `flutter test -j 2`
- Every test run that can run in the background runs in the background by default (Bash `run_in_background`)
- Setting "Load: Heavy test slot/time" = 2

S6. Agent cap
- Per device
- Setting "Load: Max agents": per machine
- Counts spawned agents in state working or permission only. A done or idle pane and the main manager are not counted
- A finished idle pane (state done): its own repo's main manager closes it once its task is merged, dropped or closed
- Never one still waiting on a merge, a question or a decision (W8 closes it after the merge). Never another repo's panes
- Reviewers count toward the cap too

S7. Session recovery
- Each agent saves state to `agent_state.txt` in its own worktree while working: task, progress, decisions, next step
- `agent_state.txt` is git-ignored. It never merges
- S2 restores it after crash or shutdown

S8. Context guard (forgetting)
- Memory is the file, not the chat. Brief, decisions, next step live in `agent_state.txt`. Re-read it before every step, write it after every step
- First action of every agent: copy its brief into `agent_state.txt`. The main manager keeps one too, in the main repo: open decisions, live sessions and terminal handles
- A state line: `agent-file.sh state add "<line>"` (it adds the date), never `echo >>`. A brief or report block: one append, then one blank line
- `agent-file.sh state trim` keeps the header, RULE/CARRY and machine lines, open questions, open-task lines, standing OWNER lines and the last 24 hours (fixed)
- `state trim` moves the rest to `agent_state.trim-<date>.txt` next to it, never lost. `todo done` and the housekeep pass run it (`state_trim_auto`); check with `--dry-run`
- Over 300 lines (fixed) the start text says STATE LONG: trim it
- After a compaction the startup hook re-prints PRINCIPLES.md and `agent_state.txt`. No quiz then. Continue from the file, not from memory
- Compacted 2 times (fixed) → save state. Orca: `agent-autoclear.sh` types a save prompt, `/clear`, then `/goal` into the own pane, only at an idle prompt with an empty input box
- A task manager runs under `/goal` from the GOAL: line of its brief: typed after the brief and after each answer; the auto clear types it again
- After a close case the main manager clears itself the same way: it types `/clear` into its own pane (its handle is in the lock line). Plain or cloud → the human types it
- No pane to type into (plain, cloud) or the send is refused → tell the human to type `/clear`; else end the session, restart from the file (S2)
- One worker = one slice, then it ends. A second slice gets a fresh worker

S9. Token guard (cost)
- Cheapest model that can do the job (the Models settings). Managers judge, they do not read whole repos
- Model by kind of thinking: deciding roles get the strongest model, executing roles a cheaper one (the Models settings)
- A worker gets only the files it needs, named in its brief. No repo-wide reads
- Quiz once per session start. Not after compaction, not for subagents
- Mechanical work (settings, file lines, cleanup) → a script, never an agent

## E. Output

E1. Shape
- For every reply a human reads
- Lead with the next action. A command, path or snippet goes first
- Number multi-step work, fewest steps
- End with one concrete next action
- No tangents: finish one, offer the other as a separate question. A mid-work question you can answer yourself is not a tangent
- Restate state every turn: Step <n> of <m> done, next
- Time estimates in real units
- Show what now works
- Errors: cause and fix, never "Uh oh"
- Lists: 5 items or fewer per group, ranked. Keep the rest, never drop them
- No preamble, no recap, no closer
- Break the shape: "explain" or "walk me through" → full length, headers
- Destructive action → confirm first
- 3 turns of "still broken" → name the assumption, ask one question
- Ambiguous request → one short question
- A rule that would delete the answer → the task wins, the shape stays
- The harness or system prompt outranks this section
- Pre-send check: delete an announcing first line, a recap or "anything else" last line, by-the-way sidebars
- Also delete empty hedges (keep a hedge with real uncertainty) and idioms
- Then: first line and last line tell what to do next and what just happened

E2. Owner overrides
- These win over E1
- Never fail silently: blocked, ambiguous, refused or broken is said at once. Never hidden as a tangent, trimmed as a hedge, or put behind a partial success
- Tables and ledgers are not lists: the 5-item cap never cuts a record whose value is completeness
- "verified", "works", "fixed" only with the real evidence named. A green suite is not a real device check
- The decide section (H3) is never deleted by "one next action" or "no closers"
- Language stays H2 (the Language setting)

E3. Concise
- Lead with the result
- Cut narration
- Short by default
- State plainly
- Full detail on request
- Never trade correctness for brevity

E4. Keyword hooks
- A keyword hook (bin/agent-keyword.sh) only points to a skill; the logic lives in the skill

## F. Map

The pieces. Rules are in A-E; this is where things live.

Roles and routing: W9. Check blocks: R8; installing into a cloud repo: the cloud-pack skill (`/auto-pipeline:cloud-pack`, `bin/agent-cloud-pack.sh`; `--update` refreshes only bin, PRINCIPLES.md, VERSION and packed skills/agents). A cloud session reads only what is committed: `git clone https://github.com/maverick1014/auto-pipeline /tmp/ap && /tmp/ap/bin/agent-cloud-pack.sh . --language zh`, then commit and push (the Claude GitHub App must be on the repo), then open a new session. The pack lands in `.claude/auto-pipeline/` (bin, PRINCIPLES.md, VERSION), `.claude/skills`, `.claude/agents`, `.claude/settings.json`, one pointer line in `CLAUDE.md`, the four `agent_*.txt`, `.secrets/`, `AGENTS.md`.

Agent skills: `/auto-pipeline:dispatch` (route one task), `/auto-pipeline:merge` (E2E, then merge deputy), `/auto-pipeline:cloud-pack`. A second session in a repo becomes a task manager by itself (W10).

### Tree

```
Human
  │  task ↓   report ↑
Main manager   (Opus 5.5, xhigh · the main chat · free for the human)
  ├── Fast-lane deputy   (Sonnet 5, medium)  one small task in its own git worktree, then gone
  ├── Check deputy       (Sonnet 5, medium)  diff read, flow and UI checks, release smoke; one at a time on the browser
  ├── Merge deputy       (Sonnet 5, medium)  merge → push → delete branch → remove worktree
  └── Worktree, one per big feature
        └── Task manager (Opus 5.5, xhigh)     writes the tests, briefs workers, verifies, never codes
              ├── Worker (Sonnet 5, medium)  code until the tests pass, slice 1
              └── Worker (Sonnet 5, medium)  code until the tests pass, slice 2

Scripts, not agents (cost no tokens):
  bin/agent-start.sh   RAM/CPU guard, prints the rules, 39-question quiz gate, main-manager lock
  bin/agent-nightly.sh  the nightly run of all tests: gates nothing, records selection misses, --release-ok
  bin/agent-test-run.sh  every test run: light or heavy by measured weight, the heavy-test slot
  bin/agent-level.sh   the blocks a diff triggers (R8): agent-level.sh check --base <ref>
  bin/agent_blocks.py  the one table of blocks and triggers (R8)
  bin/agent-owner-order.sh  relayed owner orders between repo managers: `line` prints the OWNER ORDER header (sender), `verify` checks the words are a typed owner prompt in the sender's transcript (receiver)
  bin/agent-file.sh    the only writer of agent_*.txt
  bin/agent_estimate.py  the time estimator: learns work minutes from the finished tasks, backtests against the rubric
  bin/agent-settings.sh  show the settings (/plugin -> Configure changes them)
  bin/agent-resume.sh    one command to bring the pipeline back after a restart
  bin/agent-cleanup.sh   the main manager's sweep: removes merged, clean, idle worktrees and branches; lists the rest in one table
  bin/agent-housekeep.sh the main manager's pass every housekeep_interval_min from the `agent-watch.sh --all` loop: worktree, todo and ideas files, related repos read only, then the cleanup sweep; writes one HOUSEKEEP block
  bin/agent-watch.sh     `agent-watch.sh --all`: one background watch for every task manager, local or remote (pane + agent_state.txt); exits on a report, question, stall or lost machine
  bin/agent-file.sh tell `agent-file.sh tell <task> "<msg>"`: long text to a task manager, a block in its agent_state.txt + one pointer line
  bin/agent-init.sh      sets a project up: the four task files, .secrets/, .gitignore lines, AGENTS.md, and it prints the permissions block
  bin/agent-cloud-pack.sh  lays this pipeline into a repo as plain files, for cloud sessions
  bin/agent-city.sh       starts/stops the agent city visualiser, a local server
  bin/agent-city-shim     the ~/.local/bin/agent-city command; runs the newest installed plugin's agent-city.sh
  bin/agent-city-hook.sh  hook that feeds the city; off costs a `test -f`, on appends one JSON line
  bin/agent-close-case.sh  UserPromptSubmit hook: tells a released or replaced main manager once
  bin/agent-keyword.sh  UserPromptSubmit hook: a keyword in the prompt adds one line pointing to its skill (E4)
  bin/agent-board-warn.sh  hook: a new or changed board warning into the main manager's context
  bin/agent_board.py     the todo board: one table of every open task, wait, owner to-do and parked question
  bin/agent_questions.py  the question list: every question pending on the owner, as a chat list, JSON or an Artifact page; records the answers
  bin/agent-questions-page.html  the page template (one page grouped by task, lettered options, answer bar)
  bin/agent-name.sh       SessionStart + UserPromptSubmit hook: names the session by role (W6; a human-direct one is `<repo> Helper - <Task Name>`), also the Orca tab
  bin/agent-guard.sh     hook: records every Agent launch and orca pane on the board, refuses a manager's launch that names no open todo task when the Todo before agent setting is on; off records only
  bin/agent-version.sh   UserPromptSubmit hook + check: a session running an older plugin than installed gets one STALE PLUGIN line; the start text names old scopes; an old version never retrains
```

### Files

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

### Commands

```
./bin/agent-start.sh             # rules, resources, quiz. No work until PASS
./bin/agent-resume.sh            # runs by itself at startup (Auto resume setting on); run by hand only if you turned that off
./bin/agent-settings.sh          # show the settings, no agent (change them in /plugin -> Installed -> auto-pipeline -> Configure)
bin/agent-file.sh time              # est, work, wait, clock of every finished task
bin/agent-file.sh data              # the same data of every repo on this machine, one table
bin/agent-file.sh eta <name>        # work left as minutes and a clock time, and when the human is needed next
bin/agent-file.sh estimate ... [--guess <m>]   # work minutes of a new task, with a range and the 3 nearest past tasks; --guess blends in your own minutes
bin/agent-file.sh backtest          # estimator, blend and rubric on the finished tasks, who wins
bin/agent-file.sh retrain           # learn the estimate again from the finished tasks, keep it only if better
bin/agent-file.sh next              # the queued tasks that can start now, then the board warnings
bin/agent-file.sh checks gate <task> --dir <path>  # the merge gate
bin/agent-nightly.sh --status | --misses | --release-ok   # the nightly run of all tests: its state, the selection misses, the release check
bin/agent-file.sh board             # the todo board: open tasks, waits on the owner, owner to-dos, parked questions
bin/agent-file.sh questions         # the question list: every question pending on the owner (--self, --json, --page <file>, --url <url>, answer <id> "<answer>")
bin/agent-city.sh install-shim      # one time: puts the agent-city command in ~/.local/bin; nothing installs it by itself, the init skill offers it
agent-city start                    # agent city visualiser, off by default, costs almost nothing
```


## Notice

Section E is adapted from i-have-adhd (https://github.com/ayghri/i-have-adhd) under the MIT License.

Copyright (c) 2026 Ayoub Ghriss

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
