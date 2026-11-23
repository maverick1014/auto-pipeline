# board-trust — requirements (level 4 rules gate)

Status: rules yes 2026-11-23 (1A 2A 3A: Q1 block, Q2 subagents only, Q3 record value); rule 4 change kept by the owner; default record everywhere, on in auto-pipeline (owner 3A 2026-11-20, bounce 3). Base a0f4d31 (release 0.38.0) → release 0.39.0.
Source: owner 2026-11-20 (1A 2A): "ensure the manager every time issue new agent or task will update my tracker display ... so that i only can trust it". Seen today: a merge deputy never showed on the board.
Examples: now = 2026-11-20 16:50, real names of 2026-11-20 (transcripts on pc2, the live pc2 pane list).

## 0. Words

| Word | Meaning |
|---|---|
| guard | the new hook script `bin/agent-guard.sh` (bash prefilter) + `bin/agent_guard.py` (logic) |
| launch | an `Agent`/`Task` tool call, or a Bash command that runs `orca terminal create`, `orca worktree create` |
| record | one line in `agent_state.txt` of the launching session's own folder (git toplevel of its cwd): `LAUNCH <tool_use_id>: <kind> \| task <task> \| <title> \| since <date> \| pid <claude pid> \| by <role>[ \| agent <agent_id>][ \| pane <handle>][ \| env <environment>]` |
| open task | a line of the main repo's `agent_todo.txt` with that name (any state: running, waiting, queued, held) |
| role | main = this session holds the live main lock; tm = `AGENT_ROLE=task-manager`; free = everything else (human-direct Helper, plain session, other `AGENT_ROLE`, a call from inside a subagent) |

## A. Rules table

| # | Launch (who → what) | Recorded as | Shown as (board, zh) | Removed when | Block? why |
|---|---|---|---|---|---|
| 1 | main → Agent `merge-deputy`, "state-trim Merge" (state-trim open) | `merge \| task state-trim \| state-trim Merge` | row `state-trim 合并` right under the state-trim row, 进行中, 已工作 since launch | SubagentStop with its agent id | allowed |
| 2 | main → same, after `todo done state-trim` | nothing | - | - | **blocked**: `board guard: "state-trim Merge" names state-trim, which is not an open todo task. Run agent-file.sh todo add "state-trim" ... first, then launch again.` |
| 3 | tm board-waiting (pc2) → Agent `worker`, "board-waiting Worker 1: board rows" | `worker \| task board-waiting \| board rows` in the worktree's agent_state.txt | `board-waiting 工人 1` under its row (`board --self` and the pc2 board); status line `board-waiting  ███░░  写代码  17:30 · 1 代理` | SubagentStop | allowed: own task |
| 4 | tm board-trust → "state-trim Worker 1: trim engine" | `worker 1 \| task state-trim \| trim engine` | `state-trim 工人 1` under the state-trim row | SubagentStop | allowed, recorded under the task it names (changed 2026-11-23 after the dry-run, default taken: was **blocked**; 150 of 519 real v4-plus task manager launches name a batch, short or -2 task name) |
| 5 | tm state-trim → `claude-code-guide`, "Check /goal command semantics" (free) | `guide \| task state-trim \| Check /goal command semantics` | `state-trim 指南` under its row | SubagentStop | allowed: a tm's free launch is its own task |
| 6 | main → `Explore`, "Find hook payload fields" (free) | `explore \| task auto-pipeline Manager \| Find hook payload fields` | `auto-pipeline Manager 探查`, running group | SubagentStop | allowed: read-only types (Explore, Plan, claude-code-guide, web-fetch, statusline-setup) never need a task |
| 7 | main → `general-purpose`, "Find hook payload fields" (free) | nothing | - | - | **blocked**: a type that can write (worker, deputies, general-purpose, claude, fork, any other) must name an open task (Q1) |
| 8 | main → `orca terminal create --worktree path:… --title "[auto-pipeline] board-waiting pc2 shell · LIVE - do not close" --environment pc2` at 12:00 (board-waiting open) | `shell pane \| task board-waiting \| <title> \| env pc2`, handle added from the `--json` output (PostToolUse) | `board-waiting 窗格` under its row, 内容 = title | `orca terminal close --terminal <handle>`; `orca worktree rm` of its worktree; handle not in `orca terminal list --json` at a board read | allowed |
| 9 | main → same title now (board-waiting done 15:xx) | nothing | - | - | **blocked** (no open task board-waiting) |
| 10 | main → `orca terminal create ... --title "board-trust Task Manager" --command "AGENT_ROLE=task-manager claude --name 'board-trust Task Manager' ..."` | `tm pane \| task board-trust` | `board-trust 窗格` under its row | as 8 | allowed |
| 11 | main → `orca worktree create --name board-trust ...` | nothing (the task row shows 位置 already) | - | - | allowed if board-trust is open, else **blocked** |
| 12 | main → `orca terminal create ... --title "auto-pipeline Helper"` (W10) | `helper-pane \| task auto-pipeline Helper` | `auto-pipeline Helper 窗格` | as 8 | allowed: a Helper pane needs no task |
| 13 | free (Helper, plain session, a subagent) → anything | as 1-12, task from the parse, else the folder name | as 1-12 | as 1-12 | never blocked |
| 14 | v4-plus tm → worker "W14 slice2 rules M26-M29" (real, city log) | `worker \| task <own>` | under its row | SubagentStop | allowed: free = own task (no breakage in other repos' task managers) |
| 15 | main → Bash `grep -n "orca terminal create" skills/dispatch/SKILL.md`, a heredoc or `python3 - <<EOF` body that mentions orca | nothing | - | - | not a launch: only `orca` at a command position outside quotes and heredoc bodies counts |
| 16 | the launching session crashes or ends | stays in the file | not shown (pid dead) | the next guard write in that folder deletes it | - |
| 17 | launch refused by the user or another hook (no PostToolUse, no SubagentStart) | `... ` without agent id | not shown once 2 min old with no agent id / no pane handle | next guard write | - |
| 18 | hand `worker on 1 "board rows"` and record 3 both exist | both | one row (the record wins) | - | `worker on/off` stays for plain and cloud sessions (no hooks) |

## B. Exact parse

Task name NAME = `[A-Za-z0-9][A-Za-z0-9._-]*`. Agent description, trimmed, role word any case:

| # | Pattern | Kind |
|---|---|---|
| P1 | `NAME Worker <n>[: <slice>]` | worker n, title = slice |
| P2 | `NAME Deputy[: …]` | deputy |
| P3 | `NAME Merge[: …]` | merge |
| P4 | `NAME Reviewer[: …]` (real: "state-trim reviewer: trim and hook logic") | reviewer |
| P5 | first word (up to space or `:`) = an open task (main) or the own task (tm) | kind from subagent_type: worker, deputy (fast-lane-deputy), merge (merge-deputy), explore, plan, guide, else agent |
| P6 | anything else | no task |

Pane title (`--title`, else `--name '<x>'` inside `--command`): T1 `[<repo>] NAME Task Manager` or `NAME Task Manager` → tm pane; T2 `[<repo>] NAME <rest>` → shell pane if rest has "shell", else pane; T3 `NAME Helper[ - <Task>]` → helper pane, no task needed; T4 first word = open task → pane; else no task. Worktree: `--name NAME`. `run_in_background` may be `true` or `"true"` (real transcripts).

A tm's own task: its line in agent_worktree.txt (this folder), else `TODO LINE: <name> |` of its agent_state.txt, else the folder name. A tm launch is never blocked: P1-P4/T1-T2 record it under the task it names, anything else under the own task (rule 4, changed 2026-11-23).

## C. Fail open, switch, speed

| Case | Result |
|---|---|
| not a pipeline repo (no agent.conf at the main repo) | silent exit 0, nothing recorded: the plugin is user-wide |
| any error, unreadable or missing agent_todo.txt, bad JSON, lock busy > 2 s, hook timeout (5 s) | allowed + one stderr line `board guard: <what>; allowed` |
| `board_guard=record` (template default, every repo) / `on` (auto-pipeline's own agent.conf) / `off` in agent.conf, `agent-settings.sh board_guard <v>` (validated). A missing, empty, unreadable or bad value = record (owner 3A 2026-11-20) | record only / block + record / nothing. Read at every call: no restart |
| Bash call with no `orca` in the command | bash builtins only, no python start (~5 ms) |
| status line | counts live subagent records of the task (`· 2 代理` / `· 2 agents`); panes only on the board (an orca list call is too slow for the status line) |

Hooks: PreToolUse `Agent|Task|Bash` (check + record), PostToolUse `Agent|Task|Bash` (add agent id or pane handle; a foreground `completed` result removes), SubagentStart (adds agent id when PostToolUse comes late), SubagentStop (removes). `state trim` keeps LAUNCH lines.

## D. Dry-run plan (step 5)

1. Copies only, in a temp folder: every Agent tool_use and every Bash command with `orca` from `~/.claude/projects/*auto-pipeline*/*.jsonl` on pc2 (113 found today), with their tool results.
2. A temp repo per launch: agent.conf, a todo copy holding the tasks open at that time (today's todo + agent_completed.txt done dates); role from the session folder (worktree → tm, main checkout → main). `CLAUDE_CONFIG_DIR` = temp.
3. Pipe each Pre / Post / SubagentStop payload through the real hook. Report: allowed / blocked / recorded / not a launch, every block with why, and 3 full lifecycles (record shown, then gone).
4. Extra, read only: the same count over the v4-plus transcripts (other repo, its task managers' real descriptions) to show the reach.

## E. Rollback plan

1. One line, no restart: `bin/agent-settings.sh board_guard off` (or `record`, the default of every other repo, to keep records and stop blocks).
2. Full: `git revert` the merge commit on main, release 0.39.1, plugin update on each machine.
3. Records are plain LAUNCH lines in git-ignored agent_state.txt: the old board ignores them, `board_guard=off` makes the new board and status line ignore them too, `state trim` keeps them (K2) and the guard prunes dead ones. Todo, worktree and done files are never written by the guard.

## F. Rule text (item 6)

PRINCIPLES W14 (launches record themselves; a launch naming no open task is refused; `worker on/off` only without hooks), W7 one line, dispatch skill "Board records" + task manager brief step 4, merge skill, worker and deputy agent files where they say worker on/off, README one line, plugin.json 0.39.0.

## G. Not covered (ideas, not in this task)

Panes opened by scripts (`agent-resume.sh`, city clicks) are not seen by the hook (the Bash text has no `orca`). The laptop board cannot read pc2 records (already a note row today).

## H. Questions (defaults taken if no answer)

| # | Question | Default |
|---|---|---|
| Q1 | Main manager launches a type that can write files (general-purpose, claude) with a free description: block (rule 7) or allow like Explore? | block |
| Q2 | Status line counts subagents only, panes on the board only? | yes |
| Q3 | Third switch value `record` (keep records, never block) as the soft rollback? | yes |
| Q3 (main manager's) | Owner 3A 2026-11-20, reached this task at bounce 3: every repo records only by default; only auto-pipeline blocks | default record, auto-pipeline agent.conf on |

## I. Changes after the dry-run and the review (2026-11-23)

| # | Change | Why |
|---|---|---|
| I1 | Rule 4: a task manager is never blocked. P1-P4/T1-T2 naming an open todo task (or its own) record under that task; any other name is a role label ("Code Reviewer", "Backend Worker 1") and records under the own task | dry-run: 150 of 519 real v4-plus task manager launches name a batch, short or -2 task name; review 3 |
| I2 | A plain `worker` kind (type worker, no number) shows as `<task> 工人` / `<task> worker` | review 1: such records were never shown |
| I3 | Pane with a handle and orca cannot answer (down, error, list cut by `truncated` or omitted hosts) → shown while the session pid lives; the guard prunes pane lines with a dead pid older than state_keep_hours | review 4, 14: ghost panes |
| I4 | Status line: each task line counts its own live subagent records | review 8, spec C "of the task" |
| I5 | `board_guard=off`: the guard does nothing and the board and status line ignore LAUNCH lines | review 15: a clean rollback |
| I6 | Guard writes take the same flock as `state add` / `state trim` (`<git dir>/agent_state.lock`, 2 s, then allow loudly); a newline is added before a record when the file does not end in one; the temp file lives in the git dir; one record per key | review 2, 7, 17, 18 |
| I7 | Foreground links: SubagentStart links the oldest unlinked record of that type; `completed` removes by agent id when given; only `completed` removes, any other status keeps the record (and links its agentId) | review 5, 11 |
| I8 | Parse: every orca operation of one command counts (any block blocks the whole call); heredoc bodies are cut before quotes are read; a title with `$` or a backtick is unknown (allowed, recorded under the parse or the Manager); trailing `,.;:)` is cut from a first-word task name; orca by full path and after `env`, `time`, `then`, `do`, `{` counts | review 6, 9, 12, 21 |
| I9 | Unknown session pid (CLAUDE_PID not a number, or no claude process up the chain) → no record; no git on PATH → silent; `board_guard=off  # note` reads as off | review 13, 19, 20 |
| I10 | Dispatch fast lane: `todo add` before the `<task> Deputy` launch | review 16 |
| I11 | Default `board_guard=record` in the template; a missing, empty, unreadable or bad value = record; auto-pipeline's agent.conf says `on`. Only an explicit `on` blocks | owner 3A 2026-11-20 (bounce 3, 2026-11-23) |
| - | Not done: a PostToolUseFailure hook (review 10, an idea: an unknown hook event key could break the plugin's whole hooks file); `$(...)`-captured pane create gets no handle (pruned after 2 min) | |
