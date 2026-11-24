# PRINCIPLES

- Read first. Binding for every agent in this repo.
- Output shape: section E. Human language: `language` in agent.conf (H2).
- All numbers, models and effort levels are config values (`agent.conf`, written by `./agent-settings.sh`, S1). Never hard-code.

## A. Repo

R1. Two lanes
- Small task → fast lane, no pipeline
- Big task → full pipeline
- Task size picks the lane
- Risk level is the second axis (R8): 3 and 4 always take the full lane
- Fast lane: no TDD while doing, human verifies directly, minimal test at merge

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
- Rubbish: `/auto-pipeline:clean-up` (main manager) lists other docs, old state copies, mocks of finished tasks and outdated agent_* lines; removes only the rows the human says yes to. A product repo keeps its real docs with `docs_keep` (agent.conf)

R4. No changelog
- Git history is the record

R5. Task files
- `agent_todo.txt` = open tasks only, always current
- Done → agent_completed.txt: date, name, what, then one `data` block written by `agent-file.sh`: repo, type, lane, mock, est, work, wait, clock, bounces, workers, files, lines, tests, adds. No test results, that is report material
- No other task tracking
- The housekeep pass never closes a todo line: it flags one whose branch is merged into origin/main, or one that is stale (no worktree line, no open wait, quiet longer than housekeep_interval_min)
- All four `agent_*.txt` files are written only through `./agent-file.sh`. No agent for that, it costs tokens

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

R8. Risk levels
- Second axis next to size: a risk level per task, picked at dispatch, on the todo line (`todo add ... --level <n>`, raise with `todo level <name> <n>`)
- Size still picks fast or full lane; 3 and 4 always take the full lane
- 0 wording: text values, one colour value, a switch to an existing style or variant, a move inside the same container with no responsive effect, a comment-only change
- 0 gate: the main manager reads the diff and approves. No test, no staging, no E2E, no mock
- 1 UI only: a component's own CSS, a new style, a shared colour token or theme variable, a move with responsive effect. No API, data or calculation
- 1 gate: lint + type-check; a non-builder takes before/after screenshots at desktop and phone width, console clean; owner OK
- Owner away at level 1: the main manager decides and logs "owner not seen". Mock only for a new page or whole-page re-layout (W2). No unit tests, no full suite
- 2 simple logic: one module, no money, schema, auth or permission. Gate: failing test first (TDD), touched-module tests + lint/type-check, E2E happy path + one error path
- 3 heavy logic: accounting core, money, cross-module, business rules, state flows, principles
- 3 gate: rules first as a table with examples in the requirement doc, owner yes before code; tests cover the table's edge cases
- 3 gate: a separate reviewer at the decider floor (Opus) reviews the logic; touched module + core integration group; full suite once
- 3 gate: E2E several paths incl. a failure path; real-data count first (H1)
- 4 danger: schema, migration, dependency, security, release. Gate: all of 3 + migration dry-run on a data copy + written rollback plan + owner signs before merge
- `bin/agent-level.sh check --base <ref> --declared <n>` before E2E and merge prints REQUIRED LEVEL; declared lower → RAISE, exit 1
- On RAISE: raise the todo line, bounce, follow the higher gate. A level only goes up, never down
- Built-in level 4 paths: lockfile, package.json deps, pubspec, dependency lists, migrations, schema files
- Each repo lists its core and danger folders in agent.conf: level3_paths, level4_paths (`agent-settings.sh`)
- The script cannot see a responsive effect: a level 0 move prints "manager: check responsive"; unsure → 1

## B. Work

W1. Finish in one run
- Never wait for the human
- Unknown → pick default, log it, continue
- Only owner-level or irreversible calls stop the line. Everything else: default, log, continue
- A rule and reality collide → report the collision, never route around it
- New ideas → `agent_ideas.txt` (R6), never in the work or the report, except the CLOSE CASE report (W13), which lists them too

W2. UI
- Clickable mock first (prototype artifact)
- Human says yes
- Then real code
- Level 0: no mock. Level 1: a mock only for a new page or a whole-page re-layout (R8)

W3. TDD
- Task manager writes the failing tests → worker writes code → tests pass
- Workers never write tests. Task managers never write product code
- No test = not started
- Full lane only; fast lane → R1

W4. Multi-agent tests
- Run tests for your changed files only
- Full suite: manager, once, at the end. Never twice
- The full gate runs CI's steps in CI's order, at handoff and before merge (still once each)
- After a bounce: re-run only the tests that failed, not the suite
- Which tests run follows the level gate (R8)

W5. Web UI testing
- Claude in Chrome, not Playwright, on orca and plain
- Main manager only, saves RAM. Others write the click path and hand it to the main manager
- Unit tests are not proof, the UI E2E is
- Builders never verify their own work: they ship an E2E click path, a verifier drives the UI, the main manager has the last word before merge
- What a browser cannot prove goes on a standing "needs a real device" list, never counted as verified
- Level 0 skips the E2E, the main manager reads the diff (R8)
- Ask `agent-runtime.sh browser` first: chrome, headless or none
- cloud → headless Chromium via Playwright, the extension can never reach a VM
- none → print the click path under NEEDS HUMAN E2E and stop, wait for the human. Never silent, never forever

W6. Roles
- Main manager (Opus 5.5, xhigh) = the main chat. Assigns tasks, talks to the human, reports, accepts decisions, brainstorms. Nothing else
- Fast-lane deputy (Sonnet 5, medium) = `.claude/agents/fast-lane-deputy.md`, new one per small task. Does the task, no worktree
- Merge deputy (Sonnet 5, medium) = `.claude/agents/merge-deputy.md`. Merges, then deletes branch and worktree
- Task manager (Opus 5.5, xhigh) = one agent per big feature, in its own worktree (exception: human-direct, W10). Writes the tests, briefs workers, judges, verifies every worker result before reporting done to the main manager. Never writes product code
- Worker (Sonnet 5, medium) = `.claude/agents/worker.md`, subagent of a task manager. Writes code until the task manager's tests pass
- Managers never write product code. A defect goes back to the worker that wrote it, with evidence
- Names: `bin/agent-name.sh` (SessionStart hook) shows `<repo> Manager`, `<feature> Task Manager`, `<repo> Helper - <Task Name>` (human-direct); it is the SendMessage address after `claude --name`, `/rename` or a resume. `Agent` descriptions: `<feature> Worker <n>: <slice>`, `<task> Deputy`, `<feature> Merge`

W7. Big feature (> 2 hours)
- Before opening a worktree: idle or done worktrees > 0 → deputy cleans them all first (W8)
- A worktree needs Orca. `agent-runtime.sh kind` picks the shape
- On Orca: read Orca's own guide first, `orca skills get --topic orca-cli --full --json`. Flags change: `orca agent-context --json` is the current schema
- Then new worktree
- One task manager inside it
- Task manager spawns workers as needed
- plain or cloud → no worktree, no second terminal. Main manager runs the task itself with `Agent` subagents, up to `max_agents`
- Every spawned agent counts toward `max_agents` (S6). The main manager does not
- One agent = one worktree = one branch = one terminal. Push at every stage

W8. Merge and cleanup
- Deputy merges into the integration branch
- Deputy deletes the branch (local + remote) and the worktree right after merge
- Never skip cleanup
- Clean up only after the merge is verified
- Deputy runs `./agent-file.sh worktree rm <path>` and `./agent-file.sh todo done <name>` with the facts from the main manager and `--merge <commit>`
- Sweep: `bin/agent-cleanup.sh --apply` at session start and when the last open task closes (todo empty, no live worktree). The scripts run it, no loop
- Housekeep: every housekeep_interval_min minutes (default 120, 0 = off) the monitor loop runs `bin/agent-housekeep.sh --apply`, which ends with this sweep. Plain and cloud: no loop, run it by hand
- The housekeep pass runs `agent-file.sh state trim` on the main repo's agent_state.txt before it writes its block (S8)
- The main manager reads the HOUSEKEEP block in agent_state.txt at its next activity. Per suspect: `idea rm <n>` if done or voided by a recorded owner decision, else `idea keep <n>` (still wanted)
- It then acts on the other flags of the block
- Main manager only. Task managers, Helpers and workers never run it
- Own repo only: this machine and every paired Orca machine
- Removes only safe items: merged into origin/main, no live agent, no uncommitted or unpushed work, no working/final/human-direct line
- A done pane (finished, idle) in a kept worktree: closed when its task is done or dropped, or its line is gone and its branch merged; else one kept row
- Everything else is never deleted: one table to the human (what, where, why kept, suggestion)
- A paired machine unreachable → one line, skipped. Never hangs the start

W9. Task routing (main manager, before every dispatch)
- Read `agent_worktree.txt` first
- Small task (fast lane) → spawn a new deputy subagent, it does the task. No worktree
- Task touches a live worktree's module → that worktree's task manager
- Big task, and a live task manager has capacity → that task manager
- Task manager in final stage (compiling worker results) → do not disturb. Hold the task until it finishes
- Otherwise → new worktree (W7). Never spawn a worktree for a small task
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
- Open a second session with the same permission mode and effort as the main manager (`<mode>` from `agent-settings.sh get permission_mode`, effort from `main_manager` in `agent.conf`, form model:effort): `orca terminal create --worktree path:<repo> --command "claude --name '<repo> Helper' --permission-mode <mode> --effort <effort>" --json`, then `orca terminal wait --for tui-idle`
- New terminals (dispatch, resume, a Helper, a city click) use `permission_mode`; a session started from the Agent City cloud page uses `cloud_permission_mode` (missing or refused: auto, never bypass); this machine's own `~/.claude/auto-pipeline.conf` wins over `agent.conf` for both
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
- Even verified, ask the owner first: production deploy or production data writes, deleting data, a push to a branch he reviews, anything irreversible or outward-facing. Decider floor (W17) holds

W13. Close case
- Trigger: the human or the main manager runs the skill `/auto-pipeline:close-case` (no keyword hook); a task manager's brief holds the rule too
- Subagents never get this rule; only a task manager, a human-direct session or a main manager does
- Task manager or human-direct: start nothing new; workers finish their slice or stop; save agent_state.txt; commit + push (WIP if unfinished). Never lose work
- Report to the upper level: SendMessage the main manager; another machine → print it in its own terminal and say so (W10)
- Report first line `CLOSE CASE <name>: finished` or `CLOSE CASE <name>: unfinished`, then done, left + next steps, tests + results, click path, new ideas, TIME line (W11)
- Then wait for the upper decision. Never close itself. A close case from the main manager counts the same as from the human
- Main manager gets a CLOSE CASE report: finished → merge skill. Unfinished → review, then finish first (DONE, then merge) or close now (branch pushed, todo line open, pane closed, worktree removed)
- Log every decision in its agent_state.txt. Human away → decide by the requirement doc, mark it "owner not seen"
- Main manager gets close case from the human = the whole repo: close case to every live task manager and human-direct session in agent_worktree.txt
- Collect every report, decide each, merge what passes, close all panes and worktrees, stop its own crons and monitors, update the agent files
- Then one final table to the human: task, result, what changed, what is left, decisions taken for the human. Nothing dropped (the H3 five-row cap does not apply)
- After the table the main manager asks the human, in his language: clean this session for the next round, yes or no? No, or no answer: nothing changes
- Yes: `agent-start.sh --clean` (archives agent_state.txt, writes a short fresh one, says what still runs), then `/clear`. Same main manager, same lock, same name
- Rare, the human wants this session to stop being main manager: he types `! agent-start.sh --release`; the agent never runs it. The next new session is main manager, never Helper

W14. Show todo
- Trigger: the human runs the skill `/auto-pipeline:todo` (no keyword hook); the skill holds this rule per role
- One script, no agent: `bin/agent-file.sh board`. Show its table as printed, every row, then the decide section (H3)
- Main manager: the whole repo. Task manager or Helper: `board --self`, its own task and its workers only. Subagents never
- Rows: open tasks, waits on the owner (mock check, owner question, owner review), `OWNER TODO:` and `PARKED:` lines. Each: task, what in a few words, status, where, est, work, wait, progress, done by
- Status of a wait: `waiting <who> · <what> · waited <n>`, held `hold · <what> · waited <n>`, queued `queue · after <task>`; no stage, no wait: not started. Time cells `-` (not started keeps est)
- Sort: waiting on the owner, running, waiting on others, queued and not started, held, OWNER TODO, parked questions last; oldest first in each group
- Times come from the files, never guessed. Work counts from the first stage minus later waits. Waited: since a run of waits began. Done by = now + est - work; over: by progress, else 超出 <n>m
- Progress: `agent-file.sh todo stage <name> <stage> [i/m]` at each step boundary. Task manager: brief register mock tests workers verify push report. Main manager: e2e merge. Weights in agent.conf
- Live: `board --watch` · `agent-settings.sh statusline on|off`, 5 lines at most (a warning line counts), queued/held/not started own row if room, rest `+N queued/held`. `language` of agent.conf
- Record as it happens: `todo wait <name> on <kind> ["<note>"] [--who <name>] [--after <task>]|off` at every mock check, owner question, owner review, hold, queue; `todo where` at dispatch
- `park add` for a parked question (H1); `OWNER TODO:` lines are written with `agent-file.sh state add`
- `agent-guard.sh` records launches by task; default `board_guard=record`. Only `board_guard=on` refuses a main manager launch naming no open todo task: `todo add` first. `worker on`: no hooks only.

W15. Watch
- Monitor sweep on three signals: process, terminal output, git movement
- Verify every launch within 2 min
- One `agent-watch.sh --all` in the background (Bash run_in_background) watches every task manager, local and on another machine: its pane and its worktree `agent_state.txt` (a report goes under `=== REPORT ===`); restart it after each wake
- A task manager's HEARTBEAT, ACK, report and question go into `agent_state.txt` only, never SendMessage; only DONE PASS, DONE FAIL, QUESTION:, MOCK READY, CLOSE CASE and the watch's STALL and LOST wake the main manager
- Long text to a task manager: `agent-file.sh tell <task> "<msg>"` (the block goes into its file, one pointer line to its pane, receipt checked)
- Start and resume print the `agent-watch.sh --all` command when no watch runs
- The board says `not confirmed <n>m` when a task is not watched or has been quiet
- A stall → nudge once, wait 10 min, then salvage (commit what is there) and redispatch
- Every brief says how to report, how to ask, how to report done (pass/fail) and the heartbeat

W16. Known traps
- A push to the integration branch denied by the auto-mode classifier → never retry or work around. Hand the owner one `! git push ...` line, or ask for an allow rule (init prints `Bash(git push origin main)` as optional)
- A cross-session message held because permission modes differ → say so, ask the owner to click Deliver, never type it into the pane
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
- `agent_conf.py` refuses `main_manager` or `task_manager` below the floor

W18. Show question
- Trigger: the human runs the skill `/auto-pipeline:question` (no keyword hook); the skill holds this rule per role
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
- Headers and words in the `language` of agent.conf

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
- Talk to the human in the language set by `language` in agent.conf. Docs, code and rule text stay English
- Never cite a rule by its code (W6, S8) to the human. Say what the rule means in plain words

H3. Report
- Result (pass/fail)
- What changed
- Every report, job summary, recap, proposal or audit to the human ends with a decide section
- Heading in the `language` of agent.conf: zh `## 要你决定`, en `## To decide`, other languages a short translation of "to decide"
- Open questions numbered, each with a recommendation (zh `建议`, en `Recommendation`)
- Each question stands alone: a reader who sees only that line knows what it is about and can decide
- A named thing (PR, task, branch, ticket, file) gets what it is in a few words: `#305 (stock lock settings page)`, never a bare number, tag or code name
- Per question: what, why it needs the human now, one line of evidence, then the recommendation. One or two lines, no long explanation
- Nothing open: keep the heading, one line: none (zh `无`)
- Every question the main manager puts to the owner in a decide section is recorded with `park add` (--why --evidence --options --rec if known), removed when answered (`park rm` or `questions answer`)
- Never drop the decide section as a closer. Never cut it for brevity
- Few numbers. One table at most, five rows or fewer, unless the human asks for the full list
- Nothing else, except the decide section

H4. Tables
- Comparison, series, feature list, task list, options → table
- Never prose

## D. Auto setup

S1. Settings
- `./agent-settings.sh` shows and writes `agent.conf`, validated. No hand editing, no agent
- Holds every config value in this file
- Also writes the agent-monitor config
- `~/.claude/auto-pipeline.conf` = this machine's own file, never in a repo: `permission_mode`, `cloud_permission_mode`, wins over `agent.conf`. Write it with `agent-settings.sh --user <key> <value>`

S2. Resume script
- One command
- Loads context, memory, agents, monitor, saved sessions (S7)

S3. Resource guard
- Before new agent or heavy process: check free RAM and CPU
- Low → wait or run smaller

S4. Usage cap
- RAM and CPU each ≤ 80%
- Over → no new job to any agent until it drops back
- Over → run `bin/agent-resources.sh relief` first, then wait
- relief stops only what the pipeline owns: monitor loops left by tests, monitors of repos with no live main manager
- The sweep (W8) runs `agent-resources.sh stop-leftovers`: this repo's orphan monitor and finished test loops only, no table
- Finished or idle worktrees → merge deputy cleans them (W8). A task manager over cap parks: commit, write state, set idle; the main manager closes its pane; resume brings it back
- The human's apps, other repos' sessions, Gradle or node runners: never killed by an agent. One table to the human: process · MB · CPU · what · suggestion
- Config `max_usage_percent`=80

S5. Heavy tests
- One at a time across all agents
- Others queue
- Every test run caps its own parallelism, e.g. `jest --maxWorkers=2`, `flutter test -j 2`
- Config `heavy_test_slots`=1

S6. Agent cap
- Per device
- Config `max_agents`: per machine, the value is in agent.conf
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
- `agent-file.sh state trim` keeps the header, RULE/CARRY and machine lines, open questions, open-task lines, standing OWNER lines and the last `state_keep_hours`
- `state trim` moves the rest to `agent_state.trim-<date>.txt` next to it, never lost. `todo done` and the housekeep pass run it (`state_trim_auto`); check with `--dry-run`
- Over `state_warn_lines` lines the start text says STATE LONG: trim it
- After a compaction the startup hook re-prints PRINCIPLES.md and `agent_state.txt`. No quiz then. Continue from the file, not from memory
- Compacted `compact_clear_at` times → save state. Orca: `agent-autoclear.sh` types a save prompt, `/clear`, then `/goal` into the own pane, only at an idle prompt with an empty input box
- A task manager runs under `/goal` from the GOAL: line of its brief: typed after the brief and after each answer; the auto clear types it again
- After a close case the main manager clears itself the same way: it types `/clear` into its own pane (its handle is in the lock line). Plain or cloud → the human types it
- No pane to type into (plain, cloud) or the send is refused → tell the human to type `/clear`; else end the session, restart from the file (S2)
- One worker = one slice, then it ends. A second slice gets a fresh worker

S9. Token guard (cost)
- Cheapest model that can do the job (`agent.conf`). Managers judge, they do not read whole repos
- Model by kind of thinking: deciding roles get the strongest model, executing roles a cheaper one (`agent.conf`)
- A worker gets only the files it needs, named in its brief. No repo-wide reads
- Passing tests are not re-run. Full suite once, at the end (W4)
- Quiz once per session start. Not after compaction, not for subagents
- Briefs, reports, heartbeats: short (H2, H3). One line per heartbeat
- Mechanical work (settings, file lines, cleanup) → a script, never an agent

## E. Output

E1. Shape
- For every reply a human reads
- Adapted from i-have-adhd v0.4.1 by Ayoub Ghriss (github.com/ayghri/i-have-adhd), MIT, notice at the end of this file
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
- Every decide question stands alone (H3): what each named thing is, why now, the evidence
- Language stays H2 (`language` in agent.conf)

E3. Concise
- Lead with the result
- Cut narration
- Short by default
- State plainly
- Full detail on request
- Never trade correctness for brevity

E4. Keyword hooks
- A keyword hook (bin/agent-keyword.sh) only points to a skill; the logic lives in the skill

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
