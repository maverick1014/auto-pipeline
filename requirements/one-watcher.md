# one-watcher — requirements (level 3 rules gate)

Status: RULES YES 2026-11-24 (owner, Q1-Q5 defaults); SCOPE CHANGE 2026-11-24 08:22: B16 this repo only. Base 5beb3d3 (release 0.39.0).
Source: v4-plus audit 2026-11-16 (ideas 123-125, 141-142): 30+ own watch scripts, 695 remote sends + 832 reads, DONE/QUESTION missed 7x (a SKIP regex hid lines signed `[Opus 5.5 xhigh]`), 5 cut or lost sends in Nov, heartbeats and ACKs by SendMessage = 46% of the main manager's cache-read; a closed TM pane reported as WATCH STALL twice in 36 min; one flaky orca probe made a watch exit 0 as "plain". Owner 2026-11-17: start or resume rebuilds every watch from agent_worktree.txt. Owner 2026-11-20: board stale flag.
Real orca, probed on pc2 2026-11-23: a closed pane reads `ok: true, status: "exited", tail: []`; `orca terminal wait --for exit` then gives `exitCode: 0, exitCause: {kind: "operator_close"}`. A live pane reads `status: "running"`.
Real data count (H1): pc2 main repo today: 2 worktree lines (board-trust done, one-watcher working), 0 LAUNCH records, 0 orca environments saved on pc2.

## 0. Words

LAUNCH kinds are spelled as agent_guard.py writes them: `tm-pane`, `shell-pane` (fixed 2026-11-24 in step 3; the table said `tm pane`). A live record: its pid answers `kill -0`.

| Word | Meaning |
|---|---|
| watch | `bin/agent-watch.sh`. Single mode: `--terminal <h> --worktree <p>` (today's, kept). All mode: `--all` (new, the one the main manager runs) |
| target | one task the all mode watches: name, worktree path, env (none = this machine), TM pane handle, shell pane handle (remote only) |
| wake line | a state file line that, after at most one leading `[<model> <effort>] ` group, starts with `DONE PASS`, `DONE FAIL`, `CLOSE CASE`, `QUESTION:` or `MOCK READY` |
| status file | `<git common dir of the main repo>/agent_watch.json`, written by the all mode each sweep (atomic); read by tell, the board, the status line and the start text |
| live pid | the pid in the status file answers `kill -0` and its last sweep is at most 2 x interval + 2 min old |
| idle prompt | the TM screen has no line with `esc to interrupt` and has a line starting with `❯` (box chars and spaces before it ignored) |
| login expired | a screen line holds `Please run /login`, `OAuth token has expired`, `Invalid API key` or `API Error: 401` |
| waiting by design | the task's last wake line is `QUESTION:` or `MOCK READY` with no `ANSWER:` line after it, or `DONE PASS`, `DONE FAIL`, `CLOSE CASE` |

## A. Targets (all mode) — part 1

| # | Rule | Example |
|---|---|---|
| A1 | Targets, re-read every sweep: every line of the main repo's agent_worktree.txt with status `working` or `final` (name = field 2, path = field 1), plus every open todo line with an `on <machine> <path>` field and no such worktree line (name = todo name, path = that path) | `…/one-watcher \| one-watcher \| working \| since …` → target one-watcher. `…/board-trust \| board-trust \| done` → not a target. A human-direct line → not a target |
| A2 | A new line is watched from the next sweep; a line that leaves (merged, done) is dropped with its saved state, no exit | dispatch of city-tier at 10:02 → `10:05 watch: + city-tier` |
| A3 | Where: the path is a folder on this machine → local. Else remote, env = the `env` of the task's newest live `tm-pane` LAUNCH record, else the `<machine>` of its todo `on` field. Neither → not watched, why `folder not here and no machine known` | todo `… \| on maverick-pc2 /Users/m/orca/workspaces/auto-pipeline/one-watcher` on the laptop → env maverick-pc2 |
| A4 | TM pane, first hit: the newest LAUNCH record `tm-pane \| task <name> \| … \| pane <h>` in the main repo's agent_state.txt; else `orca terminal list [--environment <env>] --worktree path:<path> --json` → the terminal whose title holds `Task Manager`, else the only one with `agentIdentity: claude`. None → not watched, why `no task manager pane` | `"title": "◑ one-watcher Task Manager"` → that handle |
| A5 | Shell pane (remote only), first hit: newest LAUNCH record `shell-pane \| task <name>` with the same env; else the same list → a terminal with no `agentIdentity`. None → not watched, why `no shell pane on <env>; open one: orca terminal create --environment <env> --worktree path:<path> --title "<name> shell"` | |
| A6 | A read that fails with a gone handle (`terminal_handle_stale`, `terminal_not_found`) re-resolves the pane once (A4/A5) before it counts as a failed read | Orca restart gave the TM a new handle → watched again, no LOST |
| A7 | Never filter by signature: no line or target is skipped for a `[...]` prefix or any other text | `[Opus 5.5 xhigh] QUESTION: rules yes?` is a wake line. `[Opus 5.5 xhigh] Brief from …` is not (no wake word after the group) |
| A8 | Not a wake line: indented, or the word mid-line, or two bracket groups | `  QUESTION: x`, `note: DONE PASS later`, `[a] [b] DONE PASS x` → no wake |
| A9 | Not watched targets are printed once at start and on change (`<HH:MM> watch: <name> not watched: <why>`), kept in the status file; they never end the watch | |

## B. Sweep and wake (all mode) — parts 1, 2, 4

| # | Rule | Example |
|---|---|---|
| B1 | Each sweep reads every watched target: its TM pane (`orca terminal read`) and its state file (local: the file; remote: one short command through its shell pane, under 400 chars, answer read with `--cursor`, as the single mode does today) | |
| B2 | Wake lines fire: `WATCH SIGNAL <name>: <line>`, then the last 15 screen lines of that TM | `WATCH SIGNAL one-watcher: QUESTION: RULES READY one-watcher: requirements/one-watcher.md, rules yes? \| 2026-11-23 18:10` |
| B3 | Never wake (part 4): HEARTBEAT, ACK, STAGE, ANSWER, TELL lines, any other line. They count as a file change (no stall). STAGE is still carried to the todo line as today | `HEARTBEAT one-watcher: step 4 of 7, work 40m, worker 1` → sweep line only |
| B4 | One sweep finishes every target first, then prints one WATCH line (+ evidence) per event, in target order, then exits 0. Two tasks with a new line in one sweep → two WATCH lines, one exit | `WATCH SIGNAL a: DONE PASS a` and `WATCH SIGNAL b: QUESTION: port?` |
| B5 | Saved baseline: the status file keeps, per task, the number of wake lines already reported. A restarted all mode fires only lines it never reported; a line written while no watch ran fires at the next start. A task seen for the first time: its existing lines are the baseline (no fire). A count below the saved one (state trim) becomes the new baseline | DONE PASS a fired, watch restarted → no second fire. b wrote QUESTION between exit and restart → fires on the first sweep |
| B6 | Stall, busy screen: 3 sweeps with the same screen and no file change → `WATCH STALL <name>: no change`. `shell still running` on screen resets it (as today; `<n> shells still running` too; or `Waiting for <n> background agent(s) to finish`) | |
| B7 | Stall, idle prompt: 2 sweeps at an idle prompt with no file change → `WATCH STALL <name>: idle prompt` (`shell still running`, `<n> shells still running` or `Waiting for <n> background agent(s) to finish` on screen resets it) | TM ended its turn without a report |
| B8 | Login expired on screen → `WATCH STALL <name>: login expired` on the first sweep that sees it | `API Error: 401 · Please run /login` |
| B9 | Waiting by design → never a stall (B6, B7); the sweep line says `waiting`. Login expired (B8) still fires | open `QUESTION:` 2 h, owner away → no wake |
| B10 | A stall is reported once: the status file keeps the screen of the reported stall; the same task with the same screen and file does not wake again; any change clears it | |
| B11 | LOST, pane exited (part 2): a read with `status` other than `running` → at once `WATCH LOST <name>: pane exited (<exitCause.kind>, exit <exitCode>)`, cause from `orca terminal wait --terminal <h> --for exit --timeout-ms 2000 --json`; no cause → `pane exited (cause unknown)` | `WATCH LOST city-tier: pane exited (operator_close, exit 0)` — never WATCH STALL |
| B12 | LOST, failed reads: 3 failed reads in a row of one target (after A6) → `WATCH LOST <name>: <orca error>` | machine down → `WATCH LOST one-watcher: orca: environment maverick-pc2 is not reachable` |
| B13 | Sweep line, one per sweep: `<HH:MM> sweep: <name> <state>, …` with state `ok`, `same <k>`, `idle <k>`, `waiting`, `fail <k>/3` or `not watched`; time from `date` | `18:05 sweep: one-watcher ok, city-tier waiting` |
| B14 | `--max <n>` sweeps done → `WATCH MAX all`. Zero targets is fine: it keeps sweeping (a dispatch adds one) | |
| B15 | One all mode per repo: a new `--all` stops an older live one (its pid from the status file, only when that pid's command line holds `agent-watch` or `agent_watch` and `--all`) and prints `watch --all: replaced pid <p>` | |
| B16 | Live pane with no task line, this repo only (owner SCOPE CHANGE 2026-11-24: each repo watches only itself): each sweep, `orca terminal list --json` (this machine). A terminal is this repo's when its `worktreeId` starts with this repo's id and `::` (the id = the part before `::` of the worktreeId of a terminal whose worktreePath is the main repo, else the `repoId` of the main repo's entry in `orca worktree list --json`), or its worktreePath is the main repo, under it, or one of the main repo's git worktrees (`git worktree list`). Of this repo's terminals, one with `agentIdentity: claude` whose worktree path is not the main repo, not a path of agent_worktree.txt and not the path of an open todo `on` field → kept in the status file as an orphan, printed once `<HH:MM> watch: live pane with no task line: <path> (<title>)`. A pane of another repo is never an orphan (F5, F6 the same). Never a wake | `worktreeId: "d8bd…::/Users/m/auto-pipeline-wt/ghost"`, claude, no task line → orphan. A `✳ v4-pospro Manager` pane (worktreeId `ee33…::/Users/m/v4-pospro`) while auto-pipeline watches → not an orphan |
| B17 | The TM pane is only read, never sent to. The shell pane gets only the read command | |
| B18 | Status file per sweep: `pid`, `started`, `sweep` (date time), `interval_min`, `tasks` {name: path, env, pane, shell, watched, why, signals, confirmed (last good read), changed (last file change), stall}, `orphans` [path, title, handle] | |

## C. Probe and single mode — part 2

| # | Rule | Example |
|---|---|---|
| C1 | `AGENT_RUNTIME`, agent.conf `runtime` or `CLAUDE_CODE_REMOTE=true` say plain or cloud → `watch: not used in <kind> mode`, exit 0 (as today, both modes) | |
| C2 | The probe alone says plain (none of C1 set) → probe again, 2 more times, `AGENT_WATCH_RETRY_S` (default 2) apart; orca on any try → watch on. Plain all 3 times → `watch: orca did not answer 3 times; a watch needs orca; not watching`, exit 1. Never exit 0 as plain (both modes) | 2026-11-16 17:22 case: one cut-off probe, orca up → watch runs |
| C3 | Single mode keeps every rule and line of today (tests/test_agent_watch.py), plus: B11 (exited → `WATCH LOST <name>: pane exited (…)` at once) and A7/A8 (one signature group before the wake word) | |

## D. tell — part 3

`bin/agent-file.sh tell <task> "<msg>"` (work in the watch engine).

| # | Rule | Example |
|---|---|---|
| D1 | `<msg>` must start with `[<model> <effort>] ` (decider floor: orders say who sends) and have text after it; else refused: one stderr line, exit 1, nothing written or sent | `tell one-watcher "rules yes"` → `tell: the message must start with [<model> <effort>]` |
| D2 | The pane, env and shell come from the status file, else A3-A5. None → `tell: no pane for <task>: <why>`, exit 1, nothing written | |
| D3 | sha8 = first 8 hex of sha256 of `<msg>` as given (UTF-8). The block, appended to the task's worktree agent_state.txt, then one blank line: line `TELL <sha8> <signature> \| <YYYY-MM-DD HH:MM>`, every message line after the signature indented by two spaces, line `END TELL <sha8>` | msg `[Opus 5.5 xhigh] ANSWER: rules yes` → `TELL 564b1788 [Opus 5.5 xhigh] \| 2026-11-23 18:20` / `  ANSWER: rules yes` / `END TELL 564b1788` |
| D4 | The indent means a told line never wakes the watch and is never a `=== ` header or a QUESTION:; an indented `ANSWER:` still answers the open QUESTION: before it (the questions tool strips leading spaces) | |
| D5 | Local: one append under the state lock (`agent_state.lock`, as `state add`). Remote: the block base64 in chunks of at most 300 characters per send through the shell pane into a temp file, then one command decodes and appends it | a 4 KB brief → about 18 short sends, never one long send |
| D6 | Read back before the pointer: the block's bytes read back from the file (remote: one command printing its sha256) must equal what was written; else write once more; still wrong → `TELL FAIL <task> <sha8>: file check`, exit 1 | |
| D7 | Pointer, one line into the TM pane: `<signature> TELL <sha8>: read the TELL <sha8> block at the end of agent_state.txt and act on it`. Before it `orca terminal wait --for tui-idle --timeout-ms 120000` (a timeout still sends) | |
| D8 | Echo check: read the TM pane with `--cursor` (from before the send) up to 10 s for `TELL <sha8>`. Not seen → one more tui-idle wait and send. Seen → `TELL OK <task> <sha8>`, exit 0. Still not → `TELL FAIL <task> <sha8>: pointer not seen (block is in the file)`, exit 1 | a send lost mid-turn → resent once |

## E. Heartbeats and wakes — part 4 (rule text)

| # | Rule |
|---|---|
| E1 | A task manager writes heartbeats, ACKs, reports and questions into its worktree agent_state.txt only (`agent-file.sh state add`, a report block = one append). Never by SendMessage |
| E2 | Only DONE PASS, DONE FAIL, QUESTION:, MOCK READY, CLOSE CASE (file lines) and the watch's STALL and LOST wake the main manager |
| E3 | The task manager's start line says: report into agent_state.txt, the main manager's watch reads it (was: report with SendMessage) |
| E4 | The dispatch brief template: REPORT, ASK, HEARTBEAT, CLOSE lines say agent_state.txt, no SendMessage; the main manager sends any text to a task manager with `agent-file.sh tell` |

## F. Start, resume and the board — part 5

| # | Rule | Example |
|---|---|---|
| F1 | Main manager start (`agent-start.sh`, role main or takeover) and `agent-resume.sh`, orca only, print one WATCH line. Live pid → `WATCH: running (pid <p>), <n> tasks, last sweep <HH:MM>` | |
| F2 | No live pid and at least one target (A1, from the files only, no orca call) → `WATCH: not running, <n> tasks to watch (<names>). Start it now with Bash run_in_background, timeout 7200000: <plugin>/bin/agent-watch.sh --all`. No targets → no line. Plain or cloud → no line | a script cannot start a watch that wakes the session; the main manager's own background Bash can, so the start text hands it the command |
| F3 | Board row warning, appended to the status cell: zh `未确认 <n>m`, en `not confirmed <n>m`, for a row whose task is a target (A1) when (a) no live pid, or (b) the status file says not watched, or (c) its row is running (no open wait) and its file has not changed for `watch_quiet_min` (agent.conf, default 15) minutes | `进行中 · 未确认 22m` |
| F4 | n = minutes since the task's `changed` in the status file, else its `confirmed`, else since the todo line's `started`, else since `opened` | |
| F5 | Orphan panes (B16) of a live status file → one note line under the table: zh `看板可能不准：<path> 有活动窗格但没有任务行`, en `board may be wrong: <path> has a live pane but no task line` | |
| F6 | Status line: any F3 warning or orphan → the first line is zh `看板可能不准：<k> 个未确认` (or `…：看守未运行` when no live pid, `…：有窗格无任务行` for orphans only), en `board may be wrong: <k> not confirmed` / `watch not running` / `a pane has no task line`; it counts in the 5-line limit | |
| F7 | The board and the status line stay read only: they read the status file and test the pid with `kill -0`, never call orca | |

## G. Rule text

PRINCIPLES W15: one line each — one `agent-watch.sh --all` for every task manager (pane + state file, local and remote, restart after each wake); heartbeats and ACKs to the state file only, the six wakes; `agent-file.sh tell` for long text; start/resume print the watch command; board `not confirmed`. Dispatch skill: start or restart `--all` instead of one watch per task; tell instead of pane sends; brief template E4. Merge skill: one line (the merged task leaves the watch by itself). README one line. agent.conf.default + agent_conf.py: `watch_quiet_min=15` (1-240).

## K. Status line rows — owner SCOPE ADD 2026-11-24 08:47 (no new gate: the owner asked for it)

Changes board-waiting rule 9.4 (fold) and the W14 status line text. Rows 9.1-9.3, 9.5-9.8 stay.

| # | Rule | Example |
|---|---|---|
| K1 | Queued, held (no who) and not started tasks get their own status line row while there is room: name padded to 24 columns, 2 spaces, a short status | |
| K2 | Short status: queue = the board's queue text (`排队 · 在 <task> 之后` / `queue · after <task>`, no task: `排队` / `queue`); hold = `暂缓 · 已等 <n>` / `hold · waited <n>` (the what dropped, as 9.3; no time known: `暂缓` / `hold`); not started = `未开始` / `not started` | `plugin-slim               排队 · 在 one-watcher 之后` |
| K3 | Same order as the board: waiting on the owner, running, waiting on others, queued and not started, held; oldest first in a group | |
| K4 | At most 5 lines in all; the F6 warning line and the fold line count. More rows than room → the first rows by order, then one last line `+N 排队/暂缓` / `+N queued/held`, N = every row left out (run rows too, as 9.5). Everything fits → no fold line | warning + 6 rows → warning, 3 rows, `+3 排队/暂缓` |
| K5 | Not on the line, not counted (as 9.7): a running row with no stage, Helpers, workers, OWNER TODO, parked | |
| K6 | `--self` (a worktree): its own row by the same rules | a queued own task → `alpha                     排队 · 在 state-trim 之后` |

Estimate: +15m (owner).

## R. Review fixes — Opus reviewer 2026-11-24, task manager decisions (in the report under "What to decide")

Gaps the first tests did not catch. Each closes a way the watch could miss a wake or wake for nothing; none widens the task.

| # | Fix | Rows |
|---|---|---|
| R1 | The remote read command is built short enough for real sizes (30-char name under a v4-plus path); a command that would still be 400 chars or more is never sent: not watched, why `read command too long (<n> chars)` | B1 |
| R2 | A task not baselined in a run (not watched, or the run ended before its first good read) keeps its saved wake-line count in the status file (or null = seen for the first time); it never falls to 0 | B5 |
| R3 | An exited pane: the state file is still read, its new wake lines fire first, then `WATCH LOST <name>: pane exited (…)`. LOST is reported once per pane handle (kept in the status file; sweep state `lost`); a new pane for the task is watched again | B11, B13 |
| R4 | Idle-prompt and login stalls are held by (reason, state file) only, not by the screen (a status line clock moves): reported once until the file changes | B7, B8, B10 |
| R5 | A takeover start (the old main manager is dead) never says "running": `WATCH: running (pid <p>) for the previous main manager; its wakes reach no one. Start it now with Bash run_in_background, timeout 7200000: <plugin>/bin/agent-watch.sh --all` (the new watch replaces it, B15) | F1 |
| R6 | No `orca` on PATH (a PATH lookup, not an orca call) counts as plain for the board and the status line: no warning | F3, F6 |
| R8 | Sweeps keep their cadence: the sleep is the interval minus the time the sweep took, so `--max` sweeps end near max x interval | B14 |
| R9 | A replaced watch prints `WATCH REPLACED all: a newer watch runs (pid <p>); do not restart` and exits 0 (SIGTERM handler), so two main managers never keep replacing each other | B15 |
| R10 | The orca-list fallback skips terminals with `connected: false` or `orphaned: true`; a shell pane titled `<name> shell` wins, then a title holding `shell`, then any non-agent terminal; a shell pane whose read is not `running` is resolved once more (as A6) before the read counts as failed | A4, A5, A6 |
| R11 | A TELL block after the task's last wake line ends "waiting by design" (new work was told after DONE FAIL, or an answer without `ANSWER:`) | B9 |
| R12 | Several new wake lines of one task in one sweep: local → one WATCH SIGNAL per line; remote → the last line, then the evidence line `+<k> earlier new wake line(s): read agent_state.txt` | B2, B4 |
| R13 | The status file also keeps the task's last wake line; the same count with another last line (a trim and a new line in one interval) fires | B5 |
| R15 | tell: a status-file pane that is gone or exited is resolved once more through A3-A5 before tell gives up | D2 |
| R16 | One fcntl lock per shell pane, `<git common dir of the main repo>/agent_shell_<handle>.lock`, held by the watch's remote read and by tell's remote sends; tell checks the read-back line that carries its own hash | B1, D5, D6 |
| R19 | `--interval-min` must be a number above 0, else usage, exit 2 | B14 |
| R22 | Login expired counts only on a screen that is not busy (no `esc to interrupt`) and in its last 10 lines (test output holding the words is no stall) | B8 |

| R4b | (bounce 2) A held stall holds only its own reason: a held idle-prompt stall never hides a later login-expired or no-change stall | B7, B8, B10 |
| R22b | (bounce 2) The login words are looked for in the 10 lines above the input prompt line (the last line starting with `❯`, box chars ignored), else in the last 10 lines | B8 |
| R3b | (bounce 2) A handle reported LOST is treated like a gone handle when the TM pane is resolved (LAUNCH records, list cache); while the task's pane is a LOST one it is resolved again every sweep | A4, A6, B11 |
| R9b | (bounce 2) `WATCH REPLACED` only when the status file names a live pid whose command line holds `--all` and that is not this watch; any other SIGTERM exits 143 with no line | B15 |
| R12b | (bounce 2) A failed shell read keeps the orca error for the LOST line (B12) | B12 |
| R15b | (bounce 2) tell checks the status file's shell pane too and resolves it again when it is gone or exited | D2, D5 |
| R10b | (bounce 2) The orphan scan skips terminals with `connected: false` or `orphaned: true` | B16 |
| R23 | (bounce 4, laptop E2E on a real Claude pane) The echo check reads the pane with --cursor AND its full screen (no cursor); either holding `TELL <sha8>` is seen. Before the second send the full screen is checked again: the first pointer on screen → no second send | D8 |

Not fixed, accepted (in the report): R7 a remote task's `changed` is the sweep that saw the change (up to one interval late), so the 15 min quiet warning can show briefly around a 15 min heartbeat; R14 tell's echo check sees the pointer typed in the input box, not that the turn started (dispatch waits for the idle prompt first); R17 a LOST line names the orca error code only; R18 `CLAUDE_PROJECT_DIR` can win over the root tell is given; R21 the FSIG/TSIG marker lines assume orca does not wrap a shell pane's rows (checked in E2E when a remote machine is there); bounce 2 review: the Claude app with Orca installed but closed still shows the board warning (true: nothing watches those panes), an immediate first sweep can push the second one to two intervals, remote STAGE takes the last STAGE line of any name and any `TELL ` line ends waiting remotely (local: the task's own STAGE, `TELL <8 hex> `), `agent_shell_<handle>.lock` files stay in .git.

## H. Not in this task

No plugin version bump (`.claude-plugin/` is a level 4 path): the main manager bumps at release. The questions tool still reads only unsigned `QUESTION:` lines (an idea). Remote tell has no lock on the other machine: a TM rewrite in the same millisecond could drop the block; the read-back and the pointer echo catch most, the TM sees the pointer either way.

## I. E2E plan (step 5, on pc2, real orca)

1. Live pane: a scratch worktree line (status working) whose pane is a plain shell titled `<scratch> Task Manager`; `AGENT_WATCH_INTERVAL_S=20 bin/agent-watch.sh --all --max 3`; append `QUESTION: e2e?` to its agent_state.txt → `WATCH SIGNAL <scratch>: QUESTION: e2e?`.
2. Exited pane (failure path): the same with the pane closed by `orca terminal close` → `WATCH LOST <name>: pane exited (operator_close, exit 0)` on the first sweep.
3. tell: `agent-file.sh tell <scratch> "[Opus 5.5 xhigh] hello"` against a plain shell pane → block in the file, `TELL OK`.
4. Restore: remove the scratch worktree line, close the scratch panes, delete the status file.

## J. Questions (defaults taken if no answer)

| # | Question | Default |
|---|---|---|
| Q1 | Reports (DONE, QUESTION, MOCK READY, CLOSE CASE) go to the state file only, no SendMessage copy (E1)? | yes: one channel, the watch wakes |
| Q2 | A task waiting by design (open QUESTION, DONE, CLOSE CASE) never wakes as a stall (B9)? | yes |
| Q3 | Start/resume print the watch command (F2) rather than start a detached watch that nobody hears? | print |
| Q4 | Quiet limit for the board warning `watch_quiet_min` = 15 (F3)? | 15 |
| Q5 | tell refuses a message without `[<model> <effort>]` (D1)? | refuse |
