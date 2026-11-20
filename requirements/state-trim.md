# state-trim — requirements (level 4 rules gate)

Status: owner "rules yes" 2026-11-20 12:2x ("all ok first, we use for a period and see how"), with answers Q1 A, Q2 C, Q3 A and two review changes from the main manager (section D). Owner signs again before merge.
Task: `state-trim` (todo line, level 4). Base b58fc2a (release 0.36.0). Ships as release 0.37.0.
Source: ideas 121 (state bloat) and 122 (compaction rule not kept) of the v4-plus audit, owner decisions 2026-11-16 1A-4A, 2026-11-17 (/goal), 2026-11-20 (this gate).

## 0. Words

| Word | Meaning |
|---|---|
| state file | `agent_state.txt` in the git toplevel of the cwd: the main repo for the main manager, the own worktree for a task manager (same folder `park` and `worker` write today) |
| stamp | a date-time a script or `state add` wrote into a line (list in A2.1). A date mentioned in the text ("tested 2026-11-17") is not a stamp |
| time of a line | its stamp; no stamp: the stamp of the next stamped line below it; none below: now |
| young | time of the line is less than `state_keep_hours` (24) hours before now; old = not young |
| open task | the first field of a line of the main repo's `agent_todo.txt` |
| closed task | the second field of a line of the main repo's `agent_completed.txt` |
| names a task | the task name stands in the line as a whole word: no letter, digit, `_` or `-` right before or after it |
| heartbeat task | in a line `HEARTBEAT <task>: ...` (a leading stamp allowed), the word between `HEARTBEAT ` and `:` |
| header | lines 1 to the first blank line (that blank line included), or to the line before the first `=== ` line, at most `state_header_lines` (40) lines |

Examples below use now = 2026-11-20 12:00 and the real open tasks of pc2's agent_todo.txt: v4plus-followups, usage-track, pc2-plugin-update, state-trim, one-watcher, owner-relay, comment-shape. Closed (agent_completed.txt, 111 lines) include goal-probe, test-levels, stale-plugin-guard, plugin, time.

## A. Rules

### A1. `agent-file.sh state add "<line>"`

| # | Input | Result |
|---|---|---|
| A1.1 | `state add "DECIDED state-trim: one archive per day"` | appends `DECIDED state-trim: one archive per day \| 2026-11-20 12:00`, prints `state add: DECIDED state-trim: one archive per day` (first 60 chars) |
| A1.2 | `state add "QUESTION: keep HEARTBEAT lines of open tasks?"` | appends `QUESTION: keep HEARTBEAT lines of open tasks? \| 2026-11-20 12:00`. The stamp goes at the END, so every line-start reader still works: show question (`QUESTION:`), the watch (`^(DONE (PASS\|FAIL)\|CLOSE CASE\|QUESTION:\|MOCK READY)`), board |
| A1.3 | `state add "LIVE: city-tier \| pc2 \| term_15ce"` | " \| " inside the text is allowed (LIVE lines use fields); stamp appended after it |
| A1.4 | `state add ""`, `state add "   "`, a text with a line break, two unquoted words | refused: one line on stderr, exit 1, nothing written |
| A1.5 | file missing / last line has no newline | file created / a newline is added first, then the line (today's `state_append`) |
| A1.6 | run in a worktree | writes the worktree's own file, never the main repo's |

`questions answer` gets the same stamp on the line it inserts: `ANSWER: rules yes | 2026-11-20 12:00` (only the "was it answered" test reads ANSWER lines; it reads the line start).

### A2. `agent-file.sh state trim [--dry-run]`: what stays

A2.1 Stamps, first match wins:
1. trailing ` | YYYY-MM-DD HH:MM` (state add, questions answer)
2. leading `YYYY-MM-DD[ HH:MM]` after spaces or a `- ` / `* ` bullet (the board's OWNER TODO rule; date only = 00:00)
3. a field `since YYYY-MM-DD HH:MM` (STAGE, WORKER, PARKED, QUESTIONS PAGE)
4. a header `=== <words> YYYY-MM-DD HH:MM ===` or `HOUSEKEEP YYYY-MM-DD HH:MM: clean`

Why "next stamped line below" for an unstamped line: lines are appended, so a line is never newer than a line written after it. This can only make a line look younger than it is (kept too long), never older (moved too early).

A2.2 A line is KEPT when any row says so. Every other line is MOVED.

| # | Keep rule | Real example line | Verdict at 2026-11-20 12:00 | Why |
|---|---|---|---|---|
| K1 | header | line 1-28 of this task's brief: `[Opus 5.5 xhigh] Brief from the main manager ...` | kept | the brief / the ROLE..CARRY block of `--clean` is the session's memory (S8) |
| K2 | line starts with `RULE` or `CARRY:` (word, then `:` or space; a leading stamp allowed) | `RULE: pc2 full suite only under /tmp/pc2-heavy.lock \| 2026-11-12 09:00` | kept (8 days old) | owner rules carry across sessions |
| K2 | `PARKED: `, `QUESTIONS PAGE: `, `STAGE `, `WORKER `, `TODO LINE:`, `GOAL:` at the line start | `STAGE state-trim: mock \| since 2026-11-20 11:40` | kept | scripts parse them: board, questions, watch, show question, the auto clear (GOAL) |
| K2 | holds `OWNER TODO:` (not right after a quote mark, the board's rule) | `2026-11-10 OWNER TODO: sign the Apple form` | kept | board row |
| K3 | an open `QUESTION:` (no `ANSWER:` after it before the next `QUESTION:` or `=== ` line) | `QUESTION: keep HEARTBEAT lines of open tasks? \| 2026-11-18 10:00` | kept (2 days old) | show question and the watch must still see it |
| K3b | the first `QUESTION:` or `=== ` line after an open question (and, when it is a question, its answer) | `=== REPORT ===` right after an open QUESTION | kept | else a later young ANSWER would close the open question |
| K4 | the HOUSEKEEP block (`=== HOUSEKEEP <date> ===` + its two-space lines) or the `HOUSEKEEP <date>: clean` line | `=== HOUSEKEEP 2026-11-18 08:00 ===` | kept | the pass replaces it in place, there is at most one; the main manager acts on it (W8) |
| K5 | a `=== REPORT ===` block (header to the line before the next `=== ` line) in which a line names an open task | `=== REPORT ===` / `DONE PASS state-trim` / ... | kept whole | the watch and the merge read it until the task is merged |
| K6 | names an open task (not for HEARTBEAT lines, see H) | `DECIDED one-watcher: --all reads agent_worktree.txt \| 2026-11-16 14:00` | kept | open-task memory |
| K6 | a LIVE line is kept only by K6 or K7 (review change 1) | `LIVE: one-watcher \| laptop \| term_a1b2 \| 2026-11-18 09:00` | kept (names one-watcher, open) | |
| K7 | young | `HEARTBEAT test-levels: step 7 of 7, work 60m \| 2026-11-20 09:30` | kept until 2026-11-21 09:30 | the last day stays |
| K8 | a standing owner decision: starts with `OWNER ` (a leading stamp allowed), not `OWNER TODO:`, and names NO open task and NO closed task (review change 2) | `OWNER 2026-11-13: ideas -> script finds suspects, owner decides each` | kept forever | owner decisions outlive tasks |
| H | an old HEARTBEAT line of an open heartbeat task: only the last one of that task in the file is kept (owner Q1 A). Young ones stay (K7) | `HEARTBEAT one-watcher: step 4 of 7, work 50m \| 2026-11-18 16:00` (the last old one of one-watcher) | kept; every earlier old one-watcher heartbeat moves | v4-plus kept 102 heartbeat lines of one task |
| P | an answered `QUESTION:` and its `ANSWER:` are one unit: kept when either line is kept by K5-K8, else both move | `QUESTION: level 4 for goal-probe? \| 2026-11-17 10:00` + `ANSWER: no \| 2026-11-17 10:20` | both moved | never split a pair: a kept question without its answer would open again |

MOVED examples (all old, no keep rule):

| Line | Why moved |
|---|---|
| `HEARTBEAT goal-probe: step 3 of 7, work 20m \| 2026-11-17 15:00` | goal-probe is closed |
| `HEARTBEAT one-watcher: step 3 of 7, work 35m \| 2026-11-18 15:45` | open task, but not its last old heartbeat (H) |
| `DECIDED test-levels: R8 levels 0-4 \| 2026-11-19 09:00` | test-levels closed, 27 h old |
| `LIVE: test-levels \| pc2 \| term_9f3e \| 2026-11-19 08:00` | LIVE is no longer kept forever; test-levels is closed (review change 1) |
| `OWNER 2026-11-17: goal-probe answers are enough, no second probe` | names only a closed task: normal rules (review change 2) |
| `OWNER 2026-11-14: plugin updates stay manual on pc2` | `plugin` is a closed task name (agent_completed.txt), so this is not standing: normal rules. Known effect of K8 with short task names (`plugin`, `time`) |
| `merged stale-plugin-guard, worktree removed` (no stamp; next stamped line below is 2026-11-16 18:00) | its time comes from the line below |
| `=== REPORT ===` block whose lines name only goal-probe | the task is merged |

### A3. `state trim`: how it moves

| # | Rule |
|---|---|
| T1 | Only the session's own state file. Never another folder's, never across machines |
| T2 | One archive per DAY (owner Q2 C): moved lines are appended, verbatim and in file order, to `agent_state.trim-<YYYY-MM-DD>.txt` (date of the trim run) next to the file. A second trim the same day appends to the same file. Nothing to move: the day file is not touched, prints `state trim: nothing to move (<n> lines)` |
| T3 | Checked before writing: kept + moved = every original line exactly once; open questions, PARKED, WORKER, STAGE, QUESTIONS PAGE, OWNER TODO, TODO LINE, GOAL, HOUSEKEEP are the same before and after. Fail: refused, nothing written |
| T4 | Order: the day archive first (its old bytes + the moved lines, tmp + mv), then the state file (tmp + mv). Just before the state write the state file is read again; changed meanwhile (an agent appended) → the archive gets its old bytes back, start over, at most 3 times, then refused, nothing changed |
| T5 | After writing both: read back, check that the state file = kept lines and the day file = its old bytes + moved lines; fail → the state file gets the original bytes, the day file its old bytes (a day file this run created is left empty, never deleted), refused |
| T6 | Prints `state trim: kept <k>, moved <m> of <n> -> agent_state.trim-<date>.txt (checked)` |
| T7 | `--dry-run`: writes nothing; prints `state trim (dry run): keep <k>, move <m> of <n>`, the keep count per rule (K1..K8, H, P), then the first 5 kept and first 5 moved lines (cut to 100 chars) |
| T8 | The day file matches the `agent_state.*.txt` git-ignore line that `--clean` writes (trim adds the line when missing) |
| T9 | Trim never deletes an archive. `--clean` keeps the 5 newest of each kind: its own copies `agent_state.<YYYY-MM-DD-HHMMSS>.txt` (as today) and the trim day files `agent_state.trim-<date>.txt` (about 5 days of trims) |
| T10 | Run by `todo done` (after the line moved to agent_completed.txt, so the finished task no longer counts as open) and by `agent-housekeep.sh --apply` (before it writes its block). Its line goes into their output (housekeep: one `note:` line when lines moved). A trim failure never fails them: one warning line, exit as before |
| T11 | `state_trim_auto=off` in agent.conf: todo done and housekeep do not trim; `state trim` by hand still works |

### A4. Start text warning

| # | Case | Start text |
|---|---|---|
| W1 | state file 301 non-empty lines (same count as the `agent_state.txt: <n> lines` header) | one line right before the state block: `STATE LONG: agent_state.txt has 301 lines (over 300). Trim: <plugin>/bin/agent-file.sh state trim --dry-run, then state trim` |
| W2 | 300 lines | no line |
| W3 | normal start, compaction, clear | all three print it; it counts inside the existing 2000-byte cap |

### A5. Auto clear at the 2nd compaction

| # | Event | What happens |
|---|---|---|
| C1 | compaction 1 | as today: `COMPACTED 1 time(s) this session ...` |
| C2 | compaction 2 (`compact_clear_at`), orca, `ORCA_TERMINAL_HANDLE` set, `orca` found | hook prints `LIMIT: compacted 2 times. Save agent_state.txt now, then stop. This pane gets a save prompt and /clear at its next idle prompt (S8).`, appends `AUTO CLEAR queued: compacted 2 times \| <date>` to the state file, starts the waiter `bin/agent-autoclear.sh` detached (the hook returns at once) |
| C3 | waiter | 1 waits until the pane may be typed into (C10) → 2 types `AUTO CLEAR: save agent_state.txt now (S8), nothing else. /clear comes next.` → 3 waits (C10) → 4 types `/clear` → 5 waits (C10) → 6 a `GOAL:` line in the state file: types `/goal <that text>`; none: types `CLEARED: continue from agent_state.txt (S8).` → 7 appends `AUTO CLEAR done \| <date>` |
| C10 | may type (owner Q3 A), checked before every typed text, task manager and main manager panes alike | `orca terminal wait --for tui-idle` succeeds AND a pane read shows the input box empty: the last line starting with `❯` between the two `─` rule lines has nothing after the `❯` but spaces. Text there → wait `compact_clear_check_sec` (30), check again; never type over it. The first time it waits on text it appends `AUTO CLEAR waiting: input box not empty \| <date>` once (a dim hint text reads as text too; never silent) |
| C4 | a step fails (send refused, orca error) | appends `AUTO CLEAR failed at step <n>: <error> \| <date>`, exits. The next compaction tries again |
| C5 | compaction 3 while a waiter for this session lives | LIMIT line only, no second waiter (pid file `<git dir>/agent_autoclear_<session id>`) |
| C6 | plain or cloud, no handle, no orca | one line: `LIMIT: compacted 2 times. No pane to type into: save agent_state.txt, then tell the human to type /clear.` |
| C7 | `/clear` happened (SessionStart source clear) | the compaction count of that session starts again at 0 |
| C8 | `compact_clear_at=0` | off: the hook prints today's LIMIT line, no waiter |
| C9 | a task manager with an active /goal | the goal text (A6) ends with "or you saved agent_state.txt after an AUTO CLEAR notice", so the goal evaluator lets it stop; the waiter then sees idle |
| C11 | the pane is gone (session ended) | the waiter exits, removes its pid file |

Why a save prompt before /clear: after a manual `/compact` nobody gets a turn, so the hook text alone never makes the agent save. The typed prompt always gives it one turn to save.

Empty input box, as `orca terminal read` shows it (pc2, 2026-11-20 12:37):
```
──────────────────────────────────── state-trim Task
❯
────────────────────────────────────────────────────
  ⏵⏵ bypass permissions on (shift+tab to cycle) · esc to interrupt
```
Not empty: `❯ rules yes, and one more thing` on that line.

### A6. /goal on every task manager

| # | Rule | Example |
|---|---|---|
| G1 | The dispatch brief carries one line `GOAL: <text>` (kept by trim, K2) | `GOAL: task manager state-trim: done when DONE PASS or DONE FAIL is written under === REPORT === in agent_state.txt and the branch is pushed, or a QUESTION:, MOCK READY or CLOSE CASE line waits for an answer, or you saved agent_state.txt after an AUTO CLEAR notice` |
| G2 | Typed by the main manager after the brief is received (the TM's `STAGE <name>: brief` line or its first reply), at the TM's next idle prompt with an empty input box (C10): `orca terminal wait --for tui-idle`, read, then `orca terminal send --text "/goal <text>" --enter`, then a read back; not shown → send once more | /goal starts a turn at once (docs), so it is typed only at an idle prompt |
| G3 | Re-typed by the main manager after it sends an answer to a QUESTION, and after a mock or rules answer (`mock yes`, `rules yes`, or changes) | met at the question → the goal is cleared → a new one is needed |
| G4 | Re-typed by the waiter after the auto /clear (C3 step 6), from the GOAL: line. The main manager does nothing for it | /clear wipes /goal |
| G5 | Met (evaluator, reads only the transcript): `DONE PASS state-trim` appended + `git push` output shown; or `MOCK READY state-trim: ...` appended and the TM stops; or `QUESTION: ...` appended and it waits; or a `CLOSE CASE state-trim: ...` report; or state saved after an AUTO CLEAR notice | the goal clears, the pane goes idle |
| G6 | Not met: anything else, e.g. the TM stops with "waiting for workers" or "tests written, next workers" | the evaluator sends it on |
| G7 | Never typed: plain or cloud (the main manager runs the task itself), a human-direct Helper, subagents | |
| G8 | Survives /compact and --resume (owner test 2026-11-17); gone after /clear (G4) | |

### A7. Config keys (agent.conf, `agent-settings.sh`, validated by agent_conf.py)

| Key | Default | Range |
|---|---|---|
| `state_keep_hours` | 24 | 1-720 |
| `state_warn_lines` | 300 | 10-100000 |
| `state_header_lines` | 40 | 0-500 |
| `state_trim_auto` | on | on, off |
| `compact_clear_at` | 2 | 0-20 (0 = off) |
| `compact_clear_check_sec` | 30 | 5-600 |

### A8. Text changes

| File | Change |
|---|---|
| PRINCIPLES.md S8 | the "Compacted 2 times" line is replaced; new lines for `state add`, `state trim` (what stays, the day archive, who runs it), the 300-line warning, the auto clear (idle + empty input box), /goal. One terse English line each, each at most 200 chars (new test) |
| PRINCIPLES.md W8 | the housekeep line: the pass trims agent_state.txt first |
| PRINCIPLES.md W14 | state lines: written with `state add`, kept by trim |
| skills/dispatch/SKILL.md | brief: `GOAL:` line, STATE line says `state add`, a blank line after the brief; the main-manager steps G2, G3 |
| bin/agent-start.sh `--clean` | one blank line after the fresh header (so the header rule finds it); the 5-newest rule per kind (T9) |
| README.md | one line on state add / trim / auto clear in the flow |
| .claude-plugin/plugin.json | 0.37.0 |

## B. Dry-run plan (verify step, never the live files)

1. Copies only, in a temp folder under the scratchpad: a fresh `git init` folder with copies of pc2's `agent_todo.txt` and `agent_completed.txt` and a copy of a state file. Real files on pc2: `/Users/maverick/auto-pipeline/agent_state*.txt` does not exist (checked 2026-11-20 11:42); this worktree's own `agent_state.txt` (task manager shape) is copied and trimmed at now and at now + 48 h.
2. A synthetic 1500-line main-manager file from a generator script, with its own todo (open: alpha-pay, beta-sync, gamma-ui, delta-api) and completed file (closed: old-login, old-report). The generator writes the expected verdict of each line itself, independent of the trim code. Expected at now = 2026-11-20 12:00:

| Part | Lines | Keep | Move | Rule |
|---|---|---|---|---|
| `--clean` header + blank line | 6 | 6 | 0 | K1 |
| RULE (old) | 4 | 4 | 0 | K2 |
| PARKED 3, OWNER TODO 2, QUESTIONS PAGE 1 | 6 | 6 | 0 | K2 |
| HOUSEKEEP block | 5 | 5 | 0 | K4 |
| LIVE (old): 4 name open tasks, 2 name closed | 6 | 4 | 2 | K6 (review change 1) |
| OWNER (old): 3 standing, 2 name only closed tasks, 1 names an open task | 6 | 4 | 2 | K8 3, K6 1 (review change 2) |
| HEARTBEAT old: 4 open tasks x 60, 2 closed tasks x 25 | 290 | 4 | 286 | H (owner Q1 A) |
| HEARTBEAT young (open tasks) | 10 | 10 | 0 | K7 |
| answered QUESTION/ANSWER pairs (old): 2 pairs name open tasks, 10 do not | 24 | 4 + 2 | 18 | P; one pair is the separator after an open question (K3b) |
| open QUESTION (old) | 2 | 2 | 0 | K3 |
| REPORT blocks x 10 lines: 1 live, 3 closed (one header is a K3b separator) | 40 | 10 + 1 | 29 | K5, K3b |
| DECIDED (old): 60 name open tasks, 60 closed | 120 | 60 | 60 | K6 |
| unstamped legacy lines among old lines | 200 | 0 | 200 | time from the line below |
| young stamped notes | 80 | 80 | 0 | K7 |
| unstamped lines at the very end | 10 | 10 | 0 | time = now |
| old stamped notes naming nothing | 691 | 0 | 691 | |
| total | 1500 | 212 | 1288 | |

3. Run `state trim --dry-run` on each copy (`AGENT_FAKE_NOW` fixed), then `state trim`, then a second `state trim` the same day (appends to the same day file, moves nothing new). Report keep/move counts per rule against the table.
4. Check kept + archived = original: sorted lines of (state + day file) equal sorted lines of the original copy, `diff` empty. `questions --json` and `board --self` give the same output before and after.
5. Restore check (rollback C1) on the copy: the restore command gives back every original line, `diff` of sorted lines empty.
6. Auto clear: a fake `orca` on PATH that logs every call and serves a pane read; SessionStart payloads compact, compact, then clear. Expect in order: wait, read, save prompt, wait, read, `/clear`, wait, read, `/goal <GOAL text>`; with text in the fake input box: no send until the text is gone, one `AUTO CLEAR waiting` line. No real pane touched.

## C. Rollback plan (live repo)

| # | What to undo | How |
|---|---|---|
| C1 | a trim moved a line it should not | every moved line is in `agent_state.trim-<date>.txt` next to the file. Single line: copy it back with `state add`. A whole day: `{ head -n <header lines> agent_state.txt; cat agent_state.trim-<date>.txt; tail -n +<header lines + 1> agent_state.txt; } > agent_state.txt.new && mv agent_state.txt.new agent_state.txt`, then move the day file away (all lines back, archived ones placed after the header; exact positions are not kept) |
| C2 | stop automatic trims | `agent-settings.sh state_trim_auto off` (todo done and housekeep stop trimming; nothing else changes) |
| C3 | stop the auto clear | `agent-settings.sh compact_clear_at 0`; a waiter already running: `kill $(cat <git dir>/agent_autoclear_<session id>)` |
| C4 | the whole release | on main: `git revert -m 1 <merge commit>`, version 0.37.1, push; sessions restart to load it. State files and archives stay as they are (they are git-ignored data) |

## D. Decisions (owner 2026-11-20, rules yes)

| # | Question | Answer |
|---|---|---|
| Q1 | HEARTBEAT lines of an open task | A: old ones keep only the newest per task (rule H); young stay |
| Q2 | archives | C: one archive per day, `agent_state.trim-<date>.txt`, appended (T2, T4, T5); `--clean` keeps 5 → about 5 days of trims (T9) |
| Q3 | waiter in the main manager's pane | A: yes, task manager and main manager panes, only at an idle prompt with an empty input box (C10) |
| R1 | main manager review change 1 | LIVE lines are kept only by K6 or K7; RULE and CARRY stay kept forever |
| R2 | main manager review change 2 | standing owner decisions: `OWNER ` lines that name no open and no closed task are kept forever (K8) |

Read as default, logged (W1): T9 "5 newest" counts each kind on its own, so the existing `--clean` copies keep their rule and the day files get the same 5.

## E. Scope adds against the todo line

1. `questions answer` stamps its ANSWER line (A1).
2. `GOAL:` line in the brief, re-typed by the waiter (G1, G4).
3. Save prompt before /clear (C3).
4. Six config keys (A7), because PRINCIPLES says every number is a config value.
5. `--clean` writes a blank line after its header and keeps 5 day files (A8, T9).
6. Review change 1: LIVE lines (K6, K7).
7. Review change 2: standing OWNER lines (K8).

No change to hooks/hooks.json: the compaction branch of agent-start.sh (SessionStart) is the compact hook. The release (.claude-plugin/) keeps the task at level 4.
