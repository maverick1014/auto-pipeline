# board-waiting — requirements (level 3 rules gate)

Status: rules table for the main manager's check against the owner's simulation (2026-11-20). No code before "rules yes".
Task: `board-waiting` (level 3). Base a3aee91 (release 0.37.0).
Source: owner decisions 2026-11-20 (simulation approved; correction 12:5x: the waited time stays, in waiting and hold rows).

## 0. Words

| Word | Meaning |
|---|---|
| wait | the open `waiting <kind> since <date>[: <note>]` field of a todo line (`todo wait ... on`) |
| owner | the human. A wait is **on the owner** when its kind is mock, question or review and it has no `who` field, or its `who` is `you`, `你` or `owner` (any case) |
| who | the new field ` \| who <name>` (`--who`); shown as `你` / `you` when it is the owner |
| after | the new field ` \| after <task>` (`--after`, queue only) |
| started | the new field ` \| started <date>[ after <n>m waited]`: written once, by the first `todo stage` of a line that has no stage field yet. `<n>` = the minutes waited before that moment (closed waits + the part of an open wait before it), only when n > 0 |
| what | the note of the wait, white space collapsed, cut to fit: board 40 display columns, status line 24 (a CJK sign = 2); longer → cut at the last space before the limit (none: at the limit), then `…` |
| waited | short time from the wait's start to now: zh `<m>分钟`, `<h>小时<m>分` (`<h>小时` when m = 0), `<d>天<h>小时` (`<d>天` when h = 0); en `<m>m`, `<h>h <m>m`, `<d>d <h>h` (today's minute form). A day or more drops the minutes |
| dash columns | 进度 估时 已工作 已等待 预计完成 / Progress Est Work Wait Done by: all `-` |

Examples: now = **2026-11-20 12:31**, machine maverick-pc2, home /Users/maverick. Fixture F = the real todo lines of 2026-11-20, re-recorded with the new options where the simulation needs them (section C). The real lines, as they are on pc2 now, are the old-line cases (rule 10).

## A. Rules

| # | Rule | Input (todo line fields after `opened ... \| by main`) | Board 状态 (zh) | Board Status (en) | Other cells |
|---|---|---|---|---|---|
| 1.1 | waiting on the owner, default what | `waiting mock since 2026-11-20 12:21` | `等待 你 · 确认样稿或规则表 · 已等 10分钟` | `waiting you · check mock or rules table · waited 10m` | dash columns; 位置, 级别 as today |
| 1.2 | question, default what | `waiting question since 2026-11-20 10:21` | `等待 你 · 回答问题 · 已等 2小时10分` | `waiting you · answer a question · waited 2h 10m` | dash columns |
| 1.3 | review, default what (owner moment) | state-trim: `... \| on maverick-pc2 /Users/maverick/orca/workspaces/auto-pipeline/state-trim \| started 2026-11-20 11:24 \| waited 38m \| stage verify since 2026-11-20 12:10 \| waiting review since 2026-11-20 12:26` | `等待 你 · 合并前签字 · 已等 5分钟` | `waiting you · sign off before merge · waited 5m` | dash columns; 位置 `maverick-pc2, ~/orca/workspaces/auto-pipeline/state-trim`, 级别 `L4`; row on top |
| 1.4 | a note wins over the default | `waiting mock since 2026-11-20 12:21: 看规则表 v2` | `等待 你 · 看规则表 v2 · 已等 10分钟` | `waiting you · 看规则表 v2 · waited 10m` | dash columns |
| 1.5 | someone else (`--who`) | `waiting hold since 2026-11-16 15:47: 回复插件更新和同步脚本 \| who v4-Manager` | `等待 v4-Manager · 回复插件更新和同步脚本 · 已等 3天20小时` | `waiting v4-Manager · 回复插件更新和同步脚本 · waited 3d 20h` | dash columns; sorts with "waiting on others" |
| 1.6 | review by someone else | `waiting review since 2026-11-20 12:01 \| who v4-Manager` | `等待 v4-Manager · 合并前签字 · 已等 30分钟` | `waiting v4-Manager · sign off before merge · waited 30m` | dash columns; waiting on others |
| 1.7 | `--who you` / `你` / `owner` = the owner | `waiting hold since 2026-11-20 12:01: 选一个方案 \| who you` | `等待 你 · 选一个方案 · 已等 30分钟` | `waiting you · 选一个方案 · waited 30m` | dash columns; sorts with the owner waits |
| 1.8 | hold with who, no note | `waiting hold since 2026-11-20 12:01 \| who v4-Manager` | `等待 v4-Manager · 已等 30分钟` | `waiting v4-Manager · waited 30m` | dash columns |
| 2.1 | hold, no who | `waiting hold since 2026-11-16 17:31: 你说合并监控之后再做` | `暂缓 · 你说合并监控之后再做 · 已等 3天19小时` | `hold · 你说合并监控之后再做 · waited 3d 19h` | dash columns |
| 2.2 | hold, no who, no note | `waiting hold since 2026-11-20 12:01` | `暂缓 · 已等 30分钟` | `hold · waited 30m` | dash columns |
| 2.3 | hold, long note (real usage-track line) | `waiting hold since 2026-11-16 17:31: owner close case 2026-11-16: after one-watcher` | `暂缓 · owner close case 2026-11-16: after… · 已等 3天19小时` | `hold · owner close case 2026-11-16: after… · waited 3d 19h` | dash columns |
| 3.1 | queue with `--after` | board-waiting: `level 3 \| ... \| waiting queue since 2026-11-20 11:35 \| after state-trim` | `排队 · 在 state-trim 之后` | `queue · after state-trim` | dash columns, no waited time; 级别 `L3`, 位置 `-` |
| 3.2 | queue, old line, note "after <task>" | `waiting queue since 2026-11-20 11:35: after one-watcher` | `排队 · 在 one-watcher 之后` | `queue · after one-watcher` | `<task>` = the first word after `after ` (any case), a trailing `,;:.` dropped |
| 3.3 | queue, `--after` and a note | `waiting queue since 2026-11-20 11:35: slot on pc2 \| after state-trim` | `排队 · 在 state-trim 之后` | `queue · after state-trim` | the note is not shown |
| 3.4 | queue, neither | `waiting queue since 2026-11-20 11:35` or `...: slot on pc2` | `排队` | `queue` | dash columns |
| 5.1 | waited, short form | wait since 2026-11-20 12:31 / 12:26 / 10:21 / 10:31 / 2026-11-16 15:47 / 2026-11-19 12:31 | `已等 0分钟` / `5分钟` / `2小时10分` / `2小时` / `3天20小时` / `1天` | `waited 0m` / `5m` / `2h 10m` / `2h` / `3d 20h` / `1d` | from the open wait's since (see Q1) |
| 6.1 | work from the first stage, minus the waits after it | state-trim: `est 70m \| ... \| opened 2026-11-20 11:20 \| ... \| started 2026-11-20 11:24 \| waited 38m \| stage tests since 2026-11-20 12:21` | `进行中` | `running` | 进度 `██░░░░░░░░  20%`, 估时 `1h 10m`, 已工作 `29m` (67 − 38), 已等待 `38m`, 预计完成 `13:12` |
| 6.2 | time before the first stage is no work | `est 39m \| opened 2026-11-20 11:35 \| started 2026-11-20 12:21 \| stage brief since 2026-11-20 12:21` | `进行中` | `running` | 已工作 `10m` (today: 56m), 已等待 `0m`, 预计完成 `13:00` |
| 6.2b | waits before the start do not count twice | `est 39m \| opened 2026-11-20 10:00 \| started 2026-11-20 12:21 after 46m waited \| waited 46m \| stage brief since 2026-11-20 12:21` | `进行中` | `running` | 已工作 `10m` (today: 1h 45m), 已等待 `46m`, 预计完成 `13:00` |
| 6.3 | never started: no stage, no wait (real owner-relay line) | `est 42m \| guess 45m \| level 3 \| opened 2026-11-20 11:35 \| by main` | `进行中` | `running` | 进度 `-`, 估时 `42m`, 已工作 `-`, 已等待 `0m`, 预计完成 `-` (never 超出 / over by) |
| 6.4 | old line: a stage but no `started` field | `est 60m \| opened 2026-11-20 10:31 \| waited 30m \| stage workers since 2026-11-20 12:00` | `进行中` | `running` | 已工作 `1h 30m` (today's rule: opened → now minus every wait), 预计完成 by today's rule |
| 7.1 | the wait ends | 1.3 after `todo wait state-trim off` at 12:31: `... \| waited 43m \| stage verify since 2026-11-20 12:10 \| waited in stage 5m` | `进行中` | `running` | progress bar, 估时, 已工作, 已等待 `43m`, 预计完成 come back |
| 10.1 | old lines never crash | every real pc2 line of 2026-11-20 (section C2) | rules 2, 3.2/3.4, 6.3/6.4 | same | no traceback, exit 0 |

### A4. `todo wait` (agent-file.sh)

| # | Command | Result on the todo line |
|---|---|---|
| 4.1 | `todo wait x on mock` | ` \| waiting mock since <now>`; no who field (the owner by default) |
| 4.2 | `todo wait x on review --who v4-Manager` | ` \| waiting review since <now> \| who v4-Manager` |
| 4.3 | `todo wait x on hold "回复插件更新和同步脚本" --who v4-Manager` (the note may stand before or after the options) | ` \| waiting hold since <now>: 回复插件更新和同步脚本 \| who v4-Manager` |
| 4.4 | `todo wait x on queue --after state-trim` | ` \| waiting queue since <now> \| after state-trim` |
| 4.5 | `todo wait x on <kind> ...` while a wait is open | the open wait closes first (today); the old who and after fields go, the new ones are written |
| 4.6 | `todo wait x off` | the waiting, who and after fields go; `waited <m>m` and `waited in stage` as today |
| 4.7 | refused (one stderr line, exit 1, nothing written) | `--who` with queue; `--after` with any kind but queue; `--who` / `--after` with no value, an empty value, `" \| "` or a line break; the same option twice; an unknown option `--x`; two notes |
| 4.8 | `who` on a line with no wait | ignored by the board (a stray field never crashes) |

### A6. `todo stage` (agent-file.sh)

| # | Command | Result |
|---|---|---|
| 6.5 | `todo stage x brief` on a line with no stage and no started field, nothing waited | ` \| started <now>` then ` \| stage brief since <now>` |
| 6.6 | same, after `waited 46m` (closed waits) | ` \| started <now> after 46m waited` |
| 6.7 | same, a wait still open since 30 minutes, `waited 10m` | ` \| started <now> after 40m waited` |
| 6.8 | any later `todo stage` | `started` never changes |
| 6.9 | a line that has a stage field but no started field (old line) | no started field is added (work keeps today's rule, 6.4) |
| 6.10 | worktree with no todo line (STAGE line only) | unchanged: only the STAGE line |

Work of a started line = minutes(started, now) − (waited + the open wait up to now − `<n>` of `after <n>m waited`), 0 at least.

### A8. Sort (board and status line)

Groups, oldest first in each (a wait by its since, the rest as today):

| Group | Rows |
|---|---|
| 1 | waiting on the owner (1.1–1.4, 1.7) |
| 2 | running (todo lines with no wait, Helpers, workers) |
| 3 | waiting on others (1.5, 1.6, 1.8) |
| 4 | queue |
| 5 | hold without who |
| 6 | OWNER TODO |
| 7 | parked questions |

(Queue before hold: the simulation puts board-waiting, queued since 2026-11-20, above usage-track, held since 2026-11-16.)

### A9. Status line

| # | Rule | Text |
|---|---|---|
| 9.1 | running with a stage (today's line) | `state-trim` padded to 24 columns, 2 spaces, bar, 2 spaces, stage word, 2 spaces, done by: `state-trim                ██░░░░░░░░  20%  写测试  13:12` |
| 9.2 | waiting on the owner: keeps what (cut to 24) | `state-trim                等待 你 · 合并前签字 · 已等 5分钟` / en `state-trim                waiting you · sign off before merge · waited 5m` |
| 9.3 | waiting on others: drops what | `v4plus-followups          等待 v4-Manager · 已等 3天20小时` / en `v4plus-followups          waiting v4-Manager · waited 3d 20h` |
| 9.4 | queue, hold without who, and todo lines with no stage and no wait (never started, e.g. owner-relay, comment-shape) fold into one last line | `+5 排队/暂缓` / en `+5 queued/held` |
| 9.5 | at most 5 lines in all, the fold line included (Q3): more than 5 → the first 4 by sort, the rest join the fold line | 7 running + 1 hold → 4 lines + `+4 排队/暂缓` |
| 9.6 | nothing to fold, 5 lines or fewer | no fold line; nothing at all → prints nothing (today) |
| 9.7 | Helpers, workers, OWNER TODO, parked rows | not on the status line, not counted (today) |
| 9.8 | `--self` (a worktree) | its own row by the same rules (a queued own task → `+1 排队/暂缓`) |

## B. Not changed

The words and cells outside rules 1–10 stay as today: the what column (60 characters), the path in 位置 (`~/orca/workspaces/auto-pipeline/state-trim`), the stage words (`写测试`), the 24-column name on the status line, the 已等待 column of a running row (every closed wait + the open one), `questions` (still lists every mock, question and review wait), the city. See Q2.

## C. Fixtures

### C1. Fixture F (simulation, zh, now 2026-11-20 12:31), the board

| 任务 | 内容 | 状态 | 进度 | 位置 | 级别 | 估时 | 已工作 | 已等待 | 预计完成 |
|---|---|---|---|---|---|---|---|---|---|
| state-trim | State file trim + auto clear… | 进行中 | ██░░░░░░░░  20% | maverick-pc2, ~/orca/workspaces/auto-pipeline/state-trim | L4 | 1h 10m | 29m | 38m | 13:12 |
| owner-relay | OWNER ORDER relay … | 进行中 | - | - | L3 | 42m | - | 0m | - |
| comment-shape | agent-level.sh: a comment-only … | 进行中 | - | - | L3 | 28m | - | 0m | - |
| v4plus-followups | Cross-repo asks … | 等待 v4-Manager · 回复插件更新和同步脚本 · 已等 3天20小时 | - | - | - | - | - | - | - |
| pc2-plugin-update | Update auto-pipeline … | 等待 v4-Manager · pc2 空闲时更新 plugin · 已等 2天4小时 (Q1 B: 2天19小时) | - | maverick-pc2 | - | - | - | - | - |
| board-waiting | Board waiting status … | 排队 · 在 state-trim 之后 | - | - | L3 | - | - | - | - |
| usage-track | Track tied repos … | 暂缓 · 你说合并监控之后再做 · 已等 3天19小时 | - | - | - | - | - | - | - |
| one-watcher | One watcher … | 暂缓 · owner close case 2026-11-18: next… · 已等 2天4小时 | - | - | L3 | - | - | - | - |

(The what cells are cut at 60 characters as today; shortened here for the page.) The simulation leaves out owner-relay, comment-shape and one-watcher; by rule 8 they are on the board. The simulation's 预计完成 13:35 is the same rule at 12:54.

Status line:

```
state-trim                ██░░░░░░░░  20%  写测试  13:12
v4plus-followups          等待 v4-Manager · 已等 3天20小时
pc2-plugin-update         等待 v4-Manager · 已等 2天4小时
+5 排队/暂缓
```

Owner moment (state-trim on review since 12:26, rule 1.3): first board row `| state-trim | … | 等待 你 · 合并前签字 · 已等 5分钟 | - | maverick-pc2, ~/orca/workspaces/auto-pipeline/state-trim | L4 | - | - | - | - |`; status line first line `state-trim                等待 你 · 合并前签字 · 已等 5分钟`, then v4plus-followups, pc2-plugin-update, `+5 排队/暂缓`.

### C2. Old lines (rule 10): pc2's real agent_todo.txt of 2026-11-20, unchanged

| Task | Real fields | 状态 |
|---|---|---|
| v4plus-followups | `waiting hold since 2026-11-16 15:47: v4-Manager: not now, ledger rollout final suite + staging; …` (no who) | `暂缓 · v4-Manager: not now, ledger rollout… · 已等 3天20小时` |
| usage-track | rule 2.3 | `暂缓 · owner close case 2026-11-16: after… · 已等 3天19小时` |
| pc2-plugin-update | `waited 895m \| waiting hold since 2026-11-18 08:16: handed to v4-Manager 2026-11-18 (owner); …` | `暂缓 · handed to v4-Manager 2026-11-18… · 已等 2天4小时` (Q1 B: 2天19小时) |
| one-watcher | hold, no who | `暂缓 · owner close case 2026-11-18: next… · 已等 2天4小时` |
| owner-relay, comment-shape | no stage, no wait | `进行中`, 已工作 `-`, 预计完成 `-` (rule 6.3) |

The old who sits inside the note ("v4-Manager: not now"); it is not read out. The main manager re-records a line with `--who` to get rule 1.

## D. Questions for the gate

| # | Question | Options | Recommendation |
|---|---|---|---|
| Q1 | pc2-plugin-update: the simulation says `已等 2天19小时`; rule 5 ("from the wait's start") gives `2天4小时`. The line waited 895m (11-17 17:21 → 11-18 08:16), then a new hold began the same minute (a note change). | A: rule 5 as written, the open wait only (2天4小时). B: a run of waits with no work between counts as one: `todo wait on` over an open wait keeps the run's start (new field ` \| wait run since <date>`, gone at `off`); an old line whose waits fill all the time from opened counts from opened (2天19小时, as the simulation). | B: a note change never resets the clock, and it matches the simulation |
| Q2 | The simulation shortens some cells by hand: what (~30 characters), 位置 (`~/orca/…/state-trim`), the stage word (`测试`), the status line padding (17 columns). | A: keep today's cells (section B). B: shorten like the simulation | A: not in rules 1–10 |
| Q3 | "Status line max 5 lines": with the `+N` line or without? | A: 5 in all, the `+N` line counted. B: 5 task lines, then the `+N` line (6) | A |

## E. Files

bin/agent_board.py (board + status line), bin/agent-statusline.sh (comment), bin/agent-file.sh (todo wait --who/--after, todo stage started, header), PRINCIPLES.md W14, skills/dispatch/SKILL.md "Board records", README.md (the status line line), tests: tests/test_board_waiting.py (new), and the old expectations in tests/test_agent_board.py, tests/test_agent_progress.py, tests/test_agent_statusline.py, tests/test_statusline_vertical.py, tests/test_agent_show_todo.py that name the old status words (`等你：看样稿`, `排队中`, `+N 个`).
