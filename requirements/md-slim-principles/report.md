# Report: PRINCIPLES.md restructure, draft 2

Source: the final text, `origin/main:PRINCIPLES.md` at 149710d, byte-identical to `249f1c1:PRINCIPLES.md` (PRINCIPLES.old-249f1c1.md, 740 lines). Draft 2 applies the 12 fix items of the coordinator after the independent comparison (compare.md). Nothing in the repo was changed. Earlier copies PRINCIPLES.old.md (c23d06b) and PRINCIPLES.old-83a087c.md stay for history.

## Numbers
| | lines | words (wc -w) | words without arrows, pipes, dashes |
|---|---|---|---|
| Always loaded before: PRINCIPLES.md | 740 | 12,298 | - |
| Always loaded after: PRINCIPLES.md (budget 100 lines, 1,150 words) | 93 | 1240 | 1150 |
| Always loaded after, once phase 2 prints rules/output.md at start | 133 | 1614 | 1488 |
| Total before | 740 | 12,298 | - |
| Total after: core + 22 rule files + GLOSSARY + NOTICE + proposed skill wording | 883 | 14888 | - |

## Files
| file | lines | words | read when |
|---|---|---|---|
| PRINCIPLES.md | 93 | 1240 | always (every session start, after a compaction) |
| GLOSSARY.md | 86 | 1374 | a repo term in a rule, skill or brief is unclear. Each entry says what the term IS; the rule that uses it lives in PRINCIPLES.md or rules/. |
| NOTICE.md | 23 | 180 | license text, unchanged; the core points to it |
| rules/approval.md | 28 | 594 | owner words may be a yes for a task published straight to production, a block left out, the working branch published, or an OWNER SIGN; or a relayed owner order arrives. |
| rules/board.md | 19 | 375 | the human asks for the todo board, or you record a wait, a stage, a parked question or an OWNER TODO line. The skill /auto-pipeline:todo shows it. |
| rules/branches.md | 37 | 836 | you pick a task's target or base, make an urgent fix, merge into production, end a batch, start or read a nightly or release run, or a full run is red. |
| rules/checks.md | 55 | 1366 | you plan the blocks of a task, run one, write its result line, gate a merge, or write a requirement doc (its examples and defaults feed the blocks). Owner approval of a block: rules/approval.md. |
| rules/close-case.md | 18 | 411 | the human or the main manager says close case, or a CLOSE CASE report arrives. The skill /auto-pipeline:close-case runs these steps. |
| rules/context.md | 30 | 456 | agent_state.txt grows long, after a compaction or /clear, at a resume or recovery, when you pick a model or brief a worker. The every-step part of S8: PRINCIPLES.md. |
| rules/cross-repo.md | 17 | 322 | a task touches another repo, or a message from a peer main manager arrives. Relayed owner words: rules/approval.md. |
| rules/files.md | 50 | 565 | you write an agent_* file, add or remove a doc, or need which file is written and read by whom. |
| rules/human.md | 36 | 604 | you ask the owner a question or park one, send a report, summary, recap, proposal or audit, or show a table. The language, no rule codes, tables, the decide section and numbered questions: PRINCIPLES.md. |
| rules/map.md | 63 | 911 | you need which script, skill or command does a job. Rules: PRINCIPLES.md and rules/. |
| rules/output.md | 40 | 374 | you shape a reply a human reads. E1-E4 are the "Section E" that NOTICE.md names; the every-step lines of it (lead with the result, short by default, evidence for "verified") are in PRINCIPLES.md. |
| rules/questions.md | 17 | 325 | the human asks for the pending questions, or says he answered the question page. The skill /auto-pipeline:question runs these steps. |
| rules/resources.md | 29 | 564 | before a run, build, pane or agent starts; you place a job or a test run on a machine; memory or usage is over the limit; you count panes. |
| rules/roles.md | 36 | 900 | you need a role's full duties, a defect must go back to its builder, you are a second session in a repo, you open a terminal for an agent, name a session, or message another session. |
| rules/routing.md | 22 | 495 | the main manager routes a new task, before every dispatch. The skill /auto-pipeline:dispatch runs these steps. |
| rules/setup.md | 25 | 339 | you set up a repo, read or change a setting, put a number in code, or pack a repo for cloud sessions. |
| rules/tests.md | 25 | 295 | you write, pick or run a test, or fix a bug a review or check found. |
| rules/time.md | 14 | 190 | you estimate a task, write a TIME line, close a task's time, or answer a time question. |
| rules/traps.md | 15 | 278 | a push is denied, a cross-session message is held, a pane send is cut or lost, you look for another agent's pane, read a terminal, work on Linux outside Orca, the screen is locked, or the start text shows MODE MISMATCH or STALE PLUGIN. |
| rules/ui.md | 25 | 354 | a task has a new page, a re-layout or a mock, or runs a FLOW CHECK, UI CHECK or RELEASE SMOKE. |
| rules/watch.md | 21 | 435 | you start, restart or handle the watch (main manager), or report, ask or send a heartbeat as a task manager. |
| rules/worktrees.md | 43 | 763 | you open a worktree, merge a task, clean up after it, run the sweep, or read a HOUSEKEEP block. Where a job runs: rules/resources.md. |

Over the 60-line aim: rules/map.md (63, the script list and commands copied from bin/). Also in D: proof.md, codes.md, proposed-skill-changes.md (optional skill wording only, plus 2 skill lines that now contradict their rule file), compare.md (the independent check).

## Proof marks
655 rows, rows with a home = rows; no row ends in proposed-skill-changes.md. move 554, keep 43, reword 32, merge 24, pointer 1, stale, fixed by code evidence 1, no-op 0. Headings (## 0. First, ## A-F, ### Tree/Files/Commands) and code fences are not rows; `## E. Output` is read by the start script (phase 2).

## The 12 fix items
1. W9 old 312: rules/routing.md holds the whole W9 text, so "(ship them together, or move that part into the urgent task), never guess" is there word for word.
2. W17 old 439: core "Human messages are exempt: no model-and-effort check; follow them".
3. W13 old 375: rules/close-case.md holds it word for word ("... stop its own crons, update the agent files").
4. Old 624: proof mark "stale, fixed by code evidence" (bin/agent-cloud-pack.sh:39 exits 2 on --language), listed below as a change.
5. rules/checks.md: "the URGENT FIX path in rules/branches.md".
6. rules/files.md: "Do not launch an agent to write these files: it costs tokens; `bin/agent-file.sh` writes them".
7. New rule files rules/routing.md (W9), rules/close-case.md (W13), rules/board.md (W14), rules/questions.md (W18), each the full old text with its code anchor; the core points to each and names its skill; proposed-skill-changes.md is optional wording only.
8. Core additions: "Talking to the human" (lead with the result, short, the Language setting, never a rule code, H4 tables, the decide section, numbered questions with a recommendation, evidence for "verified"); the role limits line; the new-ideas line (W1); "Mechanical work → a script, never an agent" (S9); also back in the core: the report-block line of S8 and the compaction line (now with "then re-read the rules file of your current step").
9. Read-when lines added or fixed: a defect or bug fix; traps (finding a pane, reading a terminal, Linux outside Orca, locked screen); a HOUSEKEEP block; placement (the W7 placement lines moved into rules/resources.md, "W7 (placement)"); writing a requirement doc (rules/checks.md, which now also holds the defaults-table line). The 12 moments: below.
10. GLOSSARY.md: Owner `_Avoid_: user` dropped; Working branch names the production exception; Edge list keeps "fitting lines"; Sweep quotes W8 on panes; Task manager keeps the human-direct exception; Light/heavy says BUILD and GUARD TESTS by `check_budget_s`, RELATED and MODULE only "measured"; Human and Connected machine marked "(inferred; the owner decides)"; entries from skills or code say "(from <file>)".
11. Decisions written into the draft (list below).
12. Quiz table: under phase 2.

## Decided by the main manager 2026-11-26, the owner can veto
- (1) rules/human.md H3: "a table whose value is completeness (the board, the question list, a ledger) is never cut"; a summary table in a report keeps the five-row cap.
- (2) rules/close-case.md W13: a task manager writes its CLOSE CASE report into agent_state.txt (the watch wakes the main manager); a human-direct session keeps SendMessage (the decision named only the task manager). skills/close-case part C 3 still says SendMessage: phase 2.
- (3) The scope hold in bin/agent_checks.py next_lines (a queued task with a `--scope` clash waits) is stale under parallel-first; the rule text stays as the owner wrote it; the code change is phase 2.
- (5) rules/branches.md: "(section 33 of requirements/check-blocks.md)". bin/agent_promote.py:195 prints "(section 33)" too: phase 2 may name the file there.
- (6) rules/roles.md W6: "Nothing else, except: it writes the requirement doc (R1), it runs the task itself on plain or cloud (W7), and it builds when the owner orders it directly". The last exception is new: it was in no old line.
- (7) rules/human.md H3: a report is the result, what changed, one concrete next action, the decide section (a new line "One concrete next action" after "What changed").
- (9) "Lead with the result" stands once: the core line "Lead with the result (E1)"; the E3 copy is merged.

## Every reword (old -> new)
| old line | old | new | why |
|---|---|---|---|
| 3 | Read first. Binding for every agent in this repo. | Binding for every agent in this repo. Detail: `rules/`, read at the moment the list at the end names. Terms: `GLOSSARY.md`. License: `NOTICE.md`. | 'Read first' is what the start text's RULES line does |
| 11 | Before each step ask: what is the quickest way to the correct result? Take that way | - Before each step take the quickest way to the correct result | question + 'take that way' -> one imperative |
| 16 | Decide, do not ask: when the owner's words or a rule already answer it, or a default can be taken and logge... | - The owner's words, a rule or a loggable default answers it → decide, go on. Ask the owner only an owner-level or irreversible call (W1) | 'Decide, do not ask: when ... a default can be taken and logged' -> 'a loggable default answers it → decide, go on' |
| 18 | Challenged on a decision: check the facts first, then keep it with the evidence, or change it and say what ... | - Challenged on a decision: check the facts, then keep it with the evidence, or change it and say what was wrong | 'check the facts first, then' -> 'check the facts, then' |
| 19 | Work that does not depend on other work runs in parallel; take the smallest change and the cheapest tool th... | - Independent work runs in parallel; take the smallest change and the cheapest tool that give the same result | 'work that does not depend on other work' -> 'independent work' (standard term) |
| 37 | Task size picks who does the work: small task = one subagent in its own git worktree (fast lane); it writes... | - Small task → fast lane (one fast-lane deputy); big task (over 2 hours, several slices) → full lane (a task manager) | the deputy's own work (own git worktree, example tests, its blocks): rules/roles.md W6, agents/fast-lane-deputy.md |
| 39 | Which checks run follows the triggers only (R8), never the lane | - Checks follow the block triggers only (R8), never the lane: a small logic task never opens a task manager just for a test | joined with row 40 |
| 41 | A small task that grows (past 2x its estimate, or it needs a second slice): the subagent stops and reports;... | - A small task grows (past 2x its estimate, or a second slice) → the deputy stops and reports; the main manager opens a task manager from its branch | 'the subagent' -> 'the deputy' |
| 42 | One fixed sequence after the build: builder reports done -> reviewer reads the diff against the approved re... | - After the build: builder done → reviewer → check deputy only when what the user sees or does changed → merge deputy. A fail → a fix order to the builder | 'reads the diff against the approved requirement' = rules/checks.md R8 (PR REVIEW); '15 min box' = rules/checks.md (FLOW/UI CHECK); Reviewer model = rules/roles.md |
| 48 | Live in `.secrets/` (git-ignored) | - R2. Secrets: `.secrets/` (git-ignored), read only; never write, print, copy, commit | three lines -> one |
| 71 | All four `agent_*.txt` files are written only through `bin/agent-file.sh`. No agent for that, it costs tokens | - `agent_*.txt` are written only through `bin/agent-file.sh` (R5) | split: the rule in the core (Never); 'No agent for that, it costs tokens' -> rules/files.md: 'Do not launch an agent to write these files: it costs tokens; `bin/agent-file.sh` writes them' |
| 165 | A repo whose working branch exists but whose main checkout is not switched yet: merges go into the producti... | - A repo whose working branch exists but whose main checkout is not switched yet: merges go into the production branch as before (section 33 of requirements/check-blocks. | the section names its file; decided by the main manager 2026-11-26, the owner can veto |
| 183 | Urgent fix (production is broken): the URGENT FIX path above | - Urgent fix (production is broken): the URGENT FIX path in rules/branches.md | 'above' -> the file that now holds it (pointer fix) |
| 211 | Workers never write tests. Task managers never write product code | - Managers never write product code; workers never write tests (W3, W6). The main manager assigns, talks to the human, reports and decides; its exceptions: `rules/roles.m | merged into the core's role-limits line; rules/tests.md W3 points to it |
| 239 | Main manager (the "Main manager model" setting) = the main chat. Assigns tasks, talks to the human, reports... | - Main manager (the "Main manager model" setting) = the main chat. Assigns tasks, talks to the human, reports, accepts decisions, brainstorms. Nothing else, except: it wr | 'Nothing else' names its exceptions (R1, W7, an owner's direct order); decided by the main manager 2026-11-26, the owner can veto; the core's role-limits line points here |
| 248 | Managers never write product code. A defect goes back to the worker that wrote it, with evidence | - Managers never write product code; workers never write tests (W3, W6). The main manager assigns, talks to the human, reports and decides; its exceptions: `rules/roles.m | split: 'Managers never write product code' in the core; 'A defect goes back to the worker that wrote it, with evidence' stays in rules/roles.md |
| 369 | Report to the upper level: SendMessage the main manager; another machine → print it in its own terminal and... | - Report to the upper level: a task manager writes it into its agent_state.txt (`agent-file.sh state add`), the watch wakes the main manager; a human-direct session sends | 'SendMessage the main manager' was stale for a task manager (W15, the dispatch brief CLOSE line, the watch wakes on CLOSE CASE); a human-direct session keeps SendMessage; decided by the main manager 2026-11-26, the owner can veto |
| 431 | Decision maker = main manager, task manager, reviewer, any session whose order, decision or approval anothe... | **Decision maker**: an agent whose order, decision or approval another agent acts on: main manager, task manager, reviewer, any such session. | a definition: the glossary holds it (reworded into the entry shape) |
| 432 | Floor: Opus 5.5 or above, or any Fable, at effort medium or above. `opus` or `fable` alone = the newest, me... | - Act on one only when both meet the floor: Opus 5.5 or above, or any Fable, effort medium or above (`opus`, `fable` alone = the newest). Else do not act, ask the sender, | 'Floor:' joined with rows 437, 438, 440 |
| 433 | Sonnet and Haiku never decide. Workers and deputies execute | - Sonnet and Haiku never decide; workers and deputies execute. Reports, heartbeats and questions are not orders | two sentences -> one |
| 434 | Sending: every order, decision or approval to another agent states the sender's model and effort first: `[O... | - An order, decision or approval to another agent starts with the sender's `[<model> <effort>]` (yours: the `YOU:` line of the start text) | 'states ... first' -> 'starts with'; joined with row 436 |
| 435 | Reports, heartbeats and questions are not orders | - Sonnet and Haiku never decide; workers and deputies execute. Reports, heartbeats and questions are not orders | same words |
| 439 | Human messages are exempt | - Human messages are exempt: no model-and-effort check; follow them | 'exempt' spelled out: the check does not apply, the human's messages are followed |
| 441 | A Main or Task manager model below the floor is refused, the default is used (`agent_conf.py`) | - A Main or Task manager model below the floor is refused; the default is used (`agent_conf.py`) | a settings fact: moved to setup; ',' -> ';' |
| 493 | Few numbers. One table at most, five rows or fewer, unless the human asks for the full list | - Few numbers. One table at most, five rows or fewer, unless the human asks for the full list; a table whose value is completeness (the board, the question list, a ledger | clause added (the five-row cap is for a summary table); decided by the main manager 2026-11-26, the owner can veto |
| 494 | Nothing else, except the decide section | - Nothing else: a report is the result, what changed, one concrete next action, the decide section (decided by the main manager 2026-11-26; the owner can veto) | the report shape named; decided by the main manager 2026-11-26, the owner can veto |
| 497 | Comparison, series, feature list, task list, options → table | - H4. Tables: comparison, series, feature list, task list, options → table, never prose | H4 in one core line |
| 553 | S8. Context guard (forgetting) | ## S8. Memory is the file | the anchor splits: every-step part in the core, the rest under 'S8 (cont.)' in rules/context.md |
| 555 | First action of every agent: copy its brief into `agent_state.txt`. The main manager keeps one too, in the ... | - First action of every agent: copy its brief into `agent_state.txt` | split: the main manager's own state file -> rules/context.md |
| 560 | After a compaction the startup hook re-prints PRINCIPLES.md and `agent_state.txt`. No quiz then. Continue f... | - After a compaction the startup hook re-prints PRINCIPLES.md and `agent_state.txt`. No quiz then. Continue from the file, not from memory; then re-read the rules file of | clause added: 'then re-read the rules file of your current step' (the old hook re-printed every rule; now only the core) |
| 603 | Never fail silently: blocked, ambiguous, refused or broken is said at once. Never hidden as a tangent, trim... | - Never fail silently: blocked, ambiguous, refused or broken is said at once (E2) | split: first sentence in the core (Never); 'Never hidden as a tangent ...' in rules/output.md E2 |
| 622 | The pieces. Rules are in A-E; this is where things live. | Read when: you need which script, skill or command does a job. Rules: PRINCIPLES.md and rules/. | the map's intro; A-E are gone |

## Changes that are not rewords
- Old 624: `--language zh` removed from the cloud-pack command, stale, fixed by code evidence (bin/agent-cloud-pack.sh:39 "--language is gone: given, it exits 2"; skills/cloud-pack "takes no --language").
- The decided lines above (1, 2, 5, 6, 7, 9).
- Old 560: the compaction line gets "then re-read the rules file of your current step" (before, the hook re-printed every rule; now only the core), and the start script must print rules/output.md (phase 2) to keep section E always shown.

## Terms unified (GLOSSARY.md `_Avoid_` lines)
connected machine (avoid: paired machine, remote machine), the net (avoid: safety net), the sweep (avoid: cleanup sweep), the housekeep pass (avoid: tidy), the gate (avoid: merge guard), check block (avoid: level), production branch (avoid: main as a role name, target branch), working branch (avoid: bare ap-main), decision maker (avoid: decider), Helper = a human-direct session only (the "Helper model" setting is the model of workers and deputies), fast-lane deputy (avoid: deputy subagent). Moved lines keep their old words; replacing the avoided words in rules/, skills and script output is phase 2.

## The 12 moments (from the core)
| moment | the core leads to |
|---|---|
| a main manager gets a small task | R1 lanes in the core; rules/routing.md (skill dispatch runs it) |
| a worker reports a bug | rules/roles.md (back to the worker that wrote it, with evidence), rules/tests.md (a small test with the fix), rules/checks.md (the edge line) |
| the owner writes "2. need to publish direct after done" | rules/approval.md (the numbered-batch case), rules/branches.md (target and base) |
| a deputy is about to merge | rules/worktrees.md (W8), rules/checks.md (the gate); agents/merge-deputy.md |
| memory at 85 percent and a test must run | rules/resources.md (S3 room, S4 over the limit, W7 placement), rules/tests.md (S5 test runs) |
| the context was just compacted | the core S8 lines (re-read the file, then the rules file of the current step), rules/context.md |
| a push is denied | rules/traps.md |
| a second session starts | rules/roles.md (W10) |
| a task manager must report done | rules/watch.md (report under === REPORT ===), rules/time.md (TIME line); the core S8 report-block line |
| a reply to the owner with two open questions | the core (decide section, numbered questions with a recommendation), rules/human.md (numbers kept, repeated until answered) |
| a reviewer is asked for a PR REVIEW | rules/checks.md (R8); agents/reviewer.md |
| a worker starts its slice | rules/tests.md (W3, W4, S5), rules/resources.md, rules/context.md (worker brief, one slice); agents/worker.md |

## Open questions for the owner
1. Owner vs human: the old text uses both; the glossary keeps both, "Human" marked inferred. Can a human who is not the owner type in a session? If not, one word.
2. R3 allows only requirement, test and main-idea docs, "Nothing else": rules/*.md, GLOSSARY.md and NOTICE.md need your yes (and agent_cleanfiles.py must keep them).
3. Connected machine = paired Orca machine (glossary, inferred): the same thing?
4. Decision (6) adds an exception no old line had: the main manager builds when the owner orders it directly. Keep?

## What phase 2 must change
Tests that pin the old file (grep at main 149710d, tests not run):
| test file | lines naming PRINCIPLES | rule-code title strings | what it pins |
|---|---|---|---|
| tests/test_rules_text.py | 115 | 83 | 64 classes read PRINCIPLES.md (514 assert calls, some on other files); section() cuts W1-W2, W12-W13, W13-W14, W14-W15, W15-W16 (x2); one-line pins (W6 names, helper-task, approval cases, decider floor, W11, W12 relay, R8, S8 trim ...) |
| tests/test_agent_start.py | 20 | 0 | RULES line, the printed `## E. Output` section, quiz |
| tests/test_agent_cloud_pack.py | 10 | 0 | the pack copies PRINCIPLES.md only |
| tests/test_agent_level.py | 9 | 0 | RULE_NAMES for RELATED TESTS of rule text |
| tests/test_agent_release.py | 7 | 0 | SHIP list |
| tests/test_two_roots.py | 6 | 0 | plugin root reads PRINCIPLES.md |
| tests/test_agent_housekeep.py | 3 | 0 |  |
| tests/test_agent_cleanfiles.py | 2 | 1 | TOP_KEEP_FILES |
| tests/test_agent_settings.py, test_agent_city_script.py, scripthelp.py, estimate_real.txt | 8 | 0 | 2 each |
| tests/test_agent_statusline.py, test_agent_init.py, test_agent_checks.py, test_agent_state.py, test_agent_keyword.py | 5 | 3 | 1 each |

Scripts and skills:
- bin/agent-start.sh: print_output_section (awk on `## E. Output`) → print rules/output.md; quiz refusal "Re-read those rules in PRINCIPLES.md" → name the rules file of the code; the compaction re-print stays the core.
- bin/agent_release.py SHIP, bin/agent-cloud-pack.sh (copy and --update): add rules/, GLOSSARY.md, NOTICE.md.
- bin/agent_cleanfiles.py TOP_KEEP_FILES: add GLOSSARY.md, NOTICE.md, keep rules/*.md. bin/agent_level.py RULE_NAMES: add rules/*.md, GLOSSARY.md.
- bin/agent_blocks.py docstring and the R8 table test: the table is in rules/checks.md.
- bin/agent-keyword.sh approval line "(PRINCIPLES.md R8) ... (W9)" → rules/approval.md, rules/routing.md.
- bin/agent_checks.py next_lines: drop the scope-clash hold (decision 3).
- bin/agent_promote.py:195 "(section 33)" → name requirements/check-blocks.md (decision 5).
- skills/close-case part C 3: SendMessage → agent_state.txt for a task manager (decision 2). Skill and agent title lines citing `PRINCIPLES.md <code>` → the file in codes.md.

Hooks that should point to a rule file at its moment:
| moment | hook | line it adds |
|---|---|---|
| session start, after compaction | SessionStart agent-start.sh | the core + rules/output.md |
| owner publish / skip words (main manager) | UserPromptSubmit agent-keyword.sh | rules/approval.md |
| dispatch (a todo add, a deputy or task manager launch) | PreToolUse agent-guard.sh | rules/routing.md, rules/checks.md (--checks) |
| merge (merge-deputy, reviewer, check-deputy launch; checks gate) | PreToolUse agent-guard.sh | rules/checks.md (the gate), rules/worktrees.md (W8) |
| a second session (lock owner alive) | SessionStart agent-start.sh | rules/roles.md (W10) |
| close case | UserPromptSubmit agent-keyword.sh (exists) | rules/close-case.md + the skill |
| MODE MISMATCH, STALE PLUGIN, push denied | agent-start.sh, agent-version.sh lines | rules/traps.md |
| a watch signal | agent-watch.sh output | rules/watch.md |

The quiz (36 questions, not changed): the code each question tests and the file that holds it now. In the core: 7 (Q1, Q10, Q13, Q20, Q26, Q33, Q36); partly in the core: Q2, Q8, Q15, Q23.
| question | rule | file now |
|---|---|---|
| Q1 | W1 | PRINCIPLES.md |
| Q2 | R6 | PRINCIPLES.md (W1 ideas line), rules/files.md (R6) |
| Q3 | H1 | rules/human.md |
| Q4 | W2 | rules/ui.md |
| Q5 | W4 | rules/tests.md |
| Q6 | W12 | rules/cross-repo.md, rules/approval.md |
| Q7 | S3 | rules/resources.md |
| Q8 | H3 | PRINCIPLES.md (H4 tables), rules/human.md |
| Q9 | R5 | rules/files.md |
| Q10 | R2 | PRINCIPLES.md |
| Q11 | R3 | rules/files.md |
| Q12 | H3 | rules/human.md |
| Q13 | R1 | PRINCIPLES.md |
| Q14 | W7 | rules/worktrees.md |
| Q15 | W6 | PRINCIPLES.md (role limits), rules/roles.md |
| Q16 | W7 | rules/worktrees.md |
| Q17 | W9 | rules/routing.md |
| Q18 | S1 | rules/setup.md, rules/roles.md (W10 new terminals) |
| Q19 | W10 | rules/roles.md |
| Q20 | S8 | PRINCIPLES.md |
| Q21 | S8 | rules/context.md |
| Q22 | H1 | rules/human.md |
| Q23 | H3 | PRINCIPLES.md (decide section), rules/human.md |
| Q24 | W8 | rules/worktrees.md |
| Q25 | R8 | rules/branches.md |
| Q26 | W17 | PRINCIPLES.md |
| Q27 | R8 | rules/checks.md |
| Q28 | R8 | rules/branches.md |
| Q29 | R8 | rules/approval.md |
| Q30 | R8 | rules/approval.md |
| Q31 | R8 | rules/approval.md |
| Q32 | R8 | rules/approval.md |
| Q33 | P1 | PRINCIPLES.md |
| Q34 | R8 | rules/approval.md |
| Q35 | W9 | rules/routing.md |
| Q36 | P1 | PRINCIPLES.md |

## Least sure
1. The core is now 93 lines and 1,150 words without symbols (1,240 by wc -w): exactly at the budget by the measure used for draft 1; by wc -w it is over.
2. Moving verbatim lines into the core (H2, H3, H4, E1, E2, E3, S9, W1) keeps one source, but it splits sections E and H between the core and rules/output.md, rules/human.md.
3. Decision (2) for a human-direct session (kept SendMessage) and decision (6) "builds when the owner orders it directly" are my wording of the main manager's decisions.

## Re-check 2 (independent comparison, 2026-11-26; table: compare2.md)
Verdict: every finding of the first comparison is fixed; the meaning is the same apart from the decisions marked "decided by the main manager". Four more fixes, applied by the main manager:
1. rules/roles.md: the exception "it builds when the owner orders it directly" is removed (no old line says it; an owner's direct order is his override, not a rule).
2. PRINCIPLES.md "Read when": `rules/output.md` is for any reply a human reads (was narrowed to "the full reply shape").
3. rules/routing.md, close-case.md, questions.md: "the skill runs these steps" became "the skill carries this out; where the two differ, this file wins".
4. PRINCIPLES.md W17: "Human messages are exempt from this check" (the added "follow them" is gone).
Also: rules/human.md report shape names the command or path right after the result; the doubled settings line in rules/setup.md is one line now.
Still open (old lines contradict each other, kept as they are): a CLOSE CASE report of a human-direct session (W13 SendMessage, W15 state file only).
Phase 2 must also change two skills so they match their rule file: close-case part C 3 (SendMessage -> agent_state.txt for a task manager), dispatch (the two options when an urgent task needs a non-urgent task's code).
