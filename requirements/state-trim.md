# state-trim — requirements (level 4 rules gate)

Status: waiting for the owner's "rules yes". No worker before it.
Task: `state-trim` (todo line, level 4). Base b58fc2a (release 0.36.0). Ships as release 0.37.0.
Source: ideas 121 (state bloat) and 122 (compaction rule not kept) of the v4-plus audit, owner decisions 2026-11-16 1A-4A, 2026-11-17 (/goal).

## 0. Words

| Word | Meaning |
|---|---|
| state file | `agent_state.txt` in the git toplevel of the cwd: the main repo for the main manager, the own worktree for a task manager (same folder `park` and `worker` write today) |
| stamp | a date-time a script or `state add` wrote into a line (list in A2.1). A date mentioned in the text ("tested 2026-11-17") is not a stamp |
| time of a line | its stamp; no stamp: the stamp of the next stamped line below it; none below: now |
| young | time of the line is less than `state_keep_hours` (24) hours before now |
| open task | the first field of a line of the main repo's `agent_todo.txt` |
| names a task | the task name stands in the line as a whole word: no letter, digit, `_` or `-` right before or after it |
| header | lines 1 to the first blank line (that blank line included), or to the line before the first `=== ` line, at most `state_header_lines` (40) lines |

Examples below use now = 2026-11-20 12:00 and the real open tasks of pc2's agent_todo.txt: v4plus-followups, usage-track, pc2-plugin-update, state-trim, one-watcher, owner-relay, comment-shape. Closed: goal-probe, test-levels, stale-plugin-guard.

## A. Rules

### A1. `agent-file.sh state add "<line>"`

| # | Input | Result |
|---|---|---|
| A1.1 | `state add "DECIDED state-trim: one archive per trim run"` | appends `DECIDED state-trim: one archive per trim run \| 2026-11-20 12:00`, prints `state add: DECIDED state-trim: one archive per trim run` (first 60 chars) |
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
| K2 | line starts with `LIVE`, `RULE`, `CARRY:` (word, then `:` or space; a leading stamp allowed) | `RULE: pc2 full suite only under /tmp/pc2-heavy.lock \| 2026-11-12 09:00` | kept (8 days old) | owner rules and live handles carry across sessions |
| K2 | `PARKED: `, `QUESTIONS PAGE: `, `STAGE `, `WORKER `, `TODO LINE:`, `GOAL:` at the line start | `STAGE state-trim: mock \| since 2026-11-20 11:40` | kept | scripts parse them: board, questions, watch, show question, the auto clear (GOAL) |
| K2 | holds `OWNER TODO:` (not right after a quote mark, the board's rule) | `2026-11-10 OWNER TODO: sign the Apple form` | kept | board row |
| K3 | an open `QUESTION:` (no `ANSWER:` after it before the next `QUESTION:` or `=== ` line) | `QUESTION: keep HEARTBEAT lines of open tasks? \| 2026-11-18 10:00` | kept (2 days old) | show question and the watch must still see it |
| K3b | the first `QUESTION:` or `=== ` line after an open question (and, when it is a question, its answer) | `=== REPORT ===` right after an open QUESTION | kept | else a later young ANSWER would close the open question |
| K4 | the HOUSEKEEP block (`=== HOUSEKEEP <date> ===` + its two-space lines) or the `HOUSEKEEP <date>: clean` line | `=== HOUSEKEEP 2026-11-18 08:00 ===` | kept | the pass replaces it in place, there is at most one; the main manager acts on it (W8) |
| K5 | a `=== REPORT ===` block (header to the line before the next `=== ` line) in which a line names an open task | `=== REPORT ===` / `DONE PASS state-trim` / ... | kept whole | the watch and the merge read it until the task is merged |
| K6 | names an open task | `DECIDED one-watcher: --all reads agent_worktree.txt \| 2026-11-16 14:00` | kept | open-task memory |
| K7 | young | `HEARTBEAT test-levels: step 7 of 7, work 60m \| 2026-11-20 09:30` | kept until 2026-11-21 09:30 | the last day stays |
| P | an answered `QUESTION:` and its `ANSWER:` are one unit: kept when either line is kept by K5-K7, else both move | `QUESTION: level 4 for goal-probe? \| 2026-11-17 10:00` + `ANSWER: no \| 2026-11-17 10:20` | both moved | never split a pair: a kept question without its answer would open again |

MOVED examples (all older than 24 h, none names an open task):

| Line | Why moved |
|---|---|
| `HEARTBEAT goal-probe: step 3 of 7, work 20m \| 2026-11-17 15:00` | goal-probe is closed |
| `DECIDED test-levels: R8 levels 0-4 \| 2026-11-19 09:00` | test-levels closed, 27 h old |
| `merged stale-plugin-guard, worktree removed` (no stamp; next stamped line below is 2026-11-16 18:00) | its time comes from the line below |
| `=== REPORT ===` block whose lines name only goal-probe | the task is merged |

Open point Q1 (section D): K6 keeps every HEARTBEAT of an open task. A task open for days keeps them all (v4-plus: 102 heartbeat lines of one task).

### A3. `state trim`: how it moves

| # | Rule |
|---|---|
| T1 | Only the session's own state file. Never another folder's, never across machines |
| T2 | Moved lines go, verbatim and in file order, to `agent_state.<YYYY-MM-DD-HHMMSS>.txt` next to the file (the `--clean` name). A taken name waits for the next second. Nothing to move: no archive, prints `state trim: nothing to move (<n> lines)` |
| T3 | Checked before writing: kept + moved = every original line exactly once; open questions, PARKED, WORKER, STAGE, QUESTIONS PAGE, OWNER TODO, TODO LINE, GOAL, HOUSEKEEP are the same before and after. Fail: refused, nothing written |
| T4 | Order: archive first (tmp + mv), then the state file (tmp + mv). Just before the state write the file is read again; changed meanwhile (an agent appended) → start over, at most 3 times, then refused, the new archive removed, nothing changed |
| T5 | After writing both: read back, check T3 again; fail → the original bytes are written back, the archive removed, refused |
| T6 | Prints `state trim: kept <k>, moved <m> of <n> -> agent_state.<stamp>.txt (checked)` |
| T7 | `--dry-run`: writes nothing; prints `state trim (dry run): keep <k>, move <m> of <n>`, the keep count per rule (K1..K7, P), then the first 5 kept and first 5 moved lines (cut to 100 chars) |
| T8 | The archive name is git-ignored through the same `agent_state.*.txt` exclude line `--clean` writes (trim adds it when missing) |
| T9 | Trim never deletes an archive. The `--clean` rule "the 5 newest archives stay" stays as it is and counts trim archives too (Q2) |
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
| C3 | waiter | 1 `orca terminal wait --for tui-idle` on its own handle (repeats while busy; ends when the pane is gone) → 2 types `AUTO CLEAR: save agent_state.txt now (S8), nothing else. /clear comes next.` → 3 waits idle → 4 types `/clear` → 5 waits idle → 6 a `GOAL:` line in the state file: types `/goal <that text>`; none: types `CLEARED: continue from agent_state.txt (S8).` → 7 appends `AUTO CLEAR done \| <date>` |
| C4 | a step fails (send refused, orca error) | appends `AUTO CLEAR failed at step <n>: <error> \| <date>`, exits. The next compaction tries again |
| C5 | compaction 3 while a waiter for this session lives | LIMIT line only, no second waiter (pid file `<git dir>/agent_autoclear_<session id>`) |
| C6 | plain or cloud, no handle, no orca | one line: `LIMIT: compacted 2 times. No pane to type into: save agent_state.txt, then tell the human to type /clear.` |
| C7 | `/clear` happened (SessionStart source clear) | the compaction count of that session starts again at 0 |
| C8 | `compact_clear_at=0` | off: the hook prints today's LIMIT line, no waiter |
| C9 | a task manager with an active /goal | the goal text (A6) ends with "or you saved agent_state.txt after an AUTO CLEAR notice", so the goal evaluator lets it stop; the waiter then sees idle |

Why a save prompt before /clear: after a manual `/compact` nobody gets a turn, so the hook text alone never makes the agent save. The typed prompt always gives it one turn to save.

### A6. /goal on every task manager

| # | Rule | Example |
|---|---|---|
| G1 | The dispatch brief carries one line `GOAL: <text>` (kept by trim, K2) | `GOAL: task manager state-trim: done when DONE PASS or DONE FAIL is written under === REPORT === in agent_state.txt and the branch is pushed, or a QUESTION:, MOCK READY or CLOSE CASE line waits for an answer, or you saved agent_state.txt after an AUTO CLEAR notice` |
| G2 | Typed by the main manager after the brief is received (the TM's `STAGE <name>: brief` line or its first reply), at the TM's next idle prompt: `orca terminal wait --for tui-idle`, then `orca terminal send --text "/goal <text>" --enter`, then a read back; not shown → send once more | /goal starts a turn at once (docs), so it is typed only at an idle prompt |
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

### A8. Text changes

| File | Change |
|---|---|
| PRINCIPLES.md S8 | the "Compacted 2 times" line is replaced; new lines for `state add`, `state trim` (what stays, archive, who runs it), the 300-line warning, the auto clear, /goal. One terse English line each, each at most 200 chars (new test) |
| PRINCIPLES.md W8 | the housekeep line: the pass trims agent_state.txt first |
| PRINCIPLES.md W14 | state lines: written with `state add`, kept by trim |
| skills/dispatch/SKILL.md | brief: `GOAL:` line, STATE line says `state add`, a blank line after the brief; the main-manager steps G2, G3 |
| bin/agent-start.sh `--clean` | one blank line after the fresh header (so the header rule finds it) |
| README.md | one line on state add / trim / auto clear in the flow |
| .claude-plugin/plugin.json | 0.37.0 |

## B. Dry-run plan (verify step, never the live files)

1. Copies only, in a temp folder under the scratchpad: a fresh `git init` folder with a copy of pc2's `agent_todo.txt` and a copy of a state file. Real files on pc2: `/Users/maverick/auto-pipeline/agent_state*.txt` does not exist (checked 2026-11-20 11:42); this worktree's own `agent_state.txt` (task manager shape) is copied.
2. A synthetic 1500-line main-manager file from a generator script: `--clean` header, 6 tasks over 10 days (4 open, 2 closed), 300 HEARTBEAT lines, DECIDED / LIVE / RULE / CARRY lines, 3 PARKED, 2 OWNER TODO, 12 QUESTION/ANSWER pairs (2 open), one HOUSEKEEP block, 4 REPORT blocks (1 live), 200 unstamped legacy lines, 80 lines of the last 24 h. The generator writes the expected keep/move count per rule itself, independent of the trim code.
3. Run `state trim --dry-run` on each copy (`AGENT_FAKE_NOW` fixed), then `state trim`. Report keep/move counts per rule against the expected counts.
4. Check kept + archived = original: sorted lines of (state + archive) equal sorted lines of the original copy, `diff` empty. `questions --json` and `board --self` give the same output before and after.
5. Restore check (rollback C1) on the copy: the restore command gives back every original line, `diff` of sorted lines empty.
6. Auto clear: a fake `orca` on PATH that logs every call; SessionStart payloads compact, compact, then clear. Expect in order: wait tui-idle, save prompt, wait, `/clear`, wait, `/goal <GOAL text>`; no real pane touched.

## C. Rollback plan (live repo)

| # | What to undo | How |
|---|---|---|
| C1 | one trim moved a line it should not | every moved line is in `agent_state.<stamp>.txt` next to the file. Single line: copy it back with `state add`. Whole trim: `{ head -n <header lines> agent_state.txt; cat agent_state.<stamp>.txt; tail -n +<header lines + 1> agent_state.txt; } > agent_state.txt.new && mv agent_state.txt.new agent_state.txt` (all lines back, archived ones placed after the header; exact positions are not kept) |
| C2 | stop automatic trims | `agent-settings.sh state_trim_auto off` (todo done and housekeep stop trimming; nothing else changes) |
| C3 | stop the auto clear | `agent-settings.sh compact_clear_at 0`; a waiter already running: `kill $(cat <git dir>/agent_autoclear_<session id>)` |
| C4 | the whole release | on main: `git revert -m 1 <merge commit>`, version 0.37.1, push; sessions restart to load it. State files and archives stay as they are (they are git-ignored data) |

## D. Open decisions for the owner

| # | Question | Recommendation |
|---|---|---|
| Q1 | HEARTBEAT lines of an OPEN task: keep all (as the todo line says) or, after 24 h, keep only the newest one per task? | newest one per task: v4-plus had 102 heartbeat lines of one task |
| Q2 | Archives: trim makes one per run (busy main manager: about 10 a day). `--clean` at close case keeps only the 5 newest of all archives, so older moved lines are deleted then. OK, or keep trim archives forever? | OK as is: moved lines are dead by rule, the 5 newest cover the recent trims |
| Q3 | The waiter types into the main manager's pane too, where the owner may be typing. OK, or task managers only (main manager gets the C6 line)? | both, typed only at an idle prompt: the main manager is the one that broke the rule 5 times |

## E. Scope adds against the todo line

1. `questions answer` stamps its ANSWER line (A1).
2. `GOAL:` line in the brief, re-typed by the waiter (G1, G4).
3. Save prompt before /clear (C3).
4. Five config keys (A7), because PRINCIPLES says every number is a config value.
5. `--clean` writes a blank line after its header (A8).

No change to hooks/hooks.json: the compaction branch of agent-start.sh (SessionStart) is the compact hook. The release (.claude-plugin/) keeps the task at level 4.
