# Independent comparison, second pass (draft 2)

This is a read-only pass, and this file is the only one written. The old file is PRINCIPLES.old-249f1c1.md, 740 lines. It equals origin/main 149710d, because the approval-design branch was merged and deleted while the check ran. The new core is 93 lines and 1,240 words by `wc -w`.

## Method
- My own word-for-word script ran again on every old line. 50 lines have no exact hit, and every one of them was checked by hand. No line hits only proposed-skill-changes.md now.
- The proof.md check script was run again. All 554 "move" rows and all 43 "keep" rows are word for word at the home they name. No row's home is proposed-skill-changes.md.
- The old W9, W13, W14 and W18 lines were diffed line by line against the four new rule files.

## 1. Items of the first report
| item | verdict | new line |
|---|---|---|
| old 312 (urgent task needs non-urgent code) | FIXED | rules/routing.md:19 "tell the owner at once (ship them together, or move that part into the urgent task), never guess" |
| old 439 (human messages exempt) | FIXED, with an addition | PRINCIPLES.md:73 "Human messages are exempt: no model-and-effort check; follow them". "follow them" is new: the old line said only "exempt". It can be read as overriding output.md:17 "Destructive action → confirm first" and :19 "Ambiguous request → one short question" |
| old 375 (update the agent files) | FIXED | rules/close-case.md:14 "... stop its own crons, update the agent files" |
| old 624 (`--language zh`) | FIXED | proof mark "stale, fixed by code evidence". report.md lists it under "Changes that are not rewords" |
| dangling URGENT FIX pointer | FIXED | rules/checks.md:49 "the URGENT FIX path in rules/branches.md" |
| files.md "No agent writes them" | FIXED | rules/files.md:23 "Do not launch an agent to write these files: it costs tokens; `bin/agent-file.sh` writes them" |
| 18 ONLY PROPOSED rows | 18/18 FIXED | 297, 298, 300, 304, 305, 311 → rules/routing.md:4-18; 365, 371, 376, 379 → rules/close-case.md:4,10,15,18; 381, 385-388, 391, 392 → rules/board.md:4,8-11,14-15; 443, 446-448 → rules/questions.md:4,7-9. The core points to all four files at PRINCIPLES.md:93 |
| proof 281 / 401 / 341 / 164 / 393 | FIXED | they are now rows 285 move, 404 reword, 344 move, 167 reword and 396 reword, and the homes are correct |
| proof 3 | FIXED | pointer to PRINCIPLES.md:76 plus the core's "Talking to the human". Printing output.md at start is listed as phase 2 work |
| proof 505 | FIXED | row 508 is now a reword: the added clause is declared |
| proof 15-27 | FIXED | they now read "unchanged words, always loaded" and no longer claim "every agent at every step" |

## 2. The four new rule files against old W9, W13, W14, W18
- routing.md:4-22 = old 297-315: identical.
- board.md:4-19 = old 381-396: identical.
- questions.md:4-17 = old 443-456: identical.
- close-case.md:4-18 = old 365-379: identical except line 8, which is decision (2).

What the four files add is their "Read when" line. Each one says "The skill ... runs these steps", and that claims too much:
- skills/close-case part C3 still says SendMessage, which is the opposite of close-case.md:8.
- skills/dispatch still lacks the two options in routing.md:19.

No line says which one wins, the rule file or the skill, until phase 2.

## 3. The core
| core line | old line | same? |
|---|---|---|
| 61 "Lead with the result (E1). Short by default (E3)" | 580 / 610 "Lead with the result", 612 "Short by default" | SAME. The copies are removed from output.md, so there is one source |
| 62 Language setting | 475 (word for word) | SAME |
| 63 never cite a rule code | 476 (word for word) | SAME |
| 64 H4 tables | 496-498 | SAME |
| 65 decide section | 481 (word for word) | SAME |
| 66 numbered questions with a recommendation | 483 (word for word) | SAME |
| 67 evidence line | 605 (word for word) | SAME |
| 21 role limits | 211 "Workers never write tests. Task managers never write product code"; 248 "Managers never write product code"; 239 "Assigns tasks, talks to the human, reports, accepts decisions, brainstorms. Nothing else" | REWORDED. "accepts decisions" became "decides" and "brainstorms" was dropped (it is still in roles.md:5). CONFLICT: the same line says "Managers never write product code" and points to the exceptions in roles.md:5, which include "it builds when the owner orders it directly" |
| 44 ideas | 198 (word for word) | SAME |
| 52 script line | 574 + "(S9)" | SAME |
| 57 report block | 556 (word for word) | SAME |
| 58 compaction | 560 + "then re-read the rules file of your current step" | an added rule, which the report declares |

Lines that were right in draft 1 and changed in draft 2:
- PRINCIPLES.md:76, the pointer to output.md, changed from "Any reply a human reads" to "The full reply shape". The E1 lines that apply to every reply now sit behind a narrower trigger until phase 2 prints output.md at start: output.md:17 "Destructive action → confirm first", :19 "Ambiguous request → one short question", :6 "A command, path ... right after the result", :15 "No preamble, no recap, no closer".
- The settings / never-hard-code line (old 5) left the core and went to setup.md:4. It is reachable through PRINCIPLES.md:92.

Said twice:
- setup.md:4 and setup.md:7 both say "Settings live only in ... Configure".
- codes.md does not list PRINCIPLES.md:21 under W3 or PRINCIPLES.md:52 under S9.

## 4. Moments that failed in the first pass
| moment | core line | file and rule | verdict |
|---|---|---|---|
| a worker reports a defect | 81 | roles.md:14, tests.md:5, checks.md:53 | PASS |
| finding a pane, reading a terminal, Linux outside Orca, locked screen | 91 | traps.md:10-12 and :14 | PASS |
| a HOUSEKEEP block | 84 | worktrees.md:36-37 | PASS |
| where a job is placed | 88 | resources.md:4-7 (W7 placement) | PASS |
| writing a requirement doc | 77 | checks.md:55 (defaults table), checks.md:24 (owner approves the money and permission examples) | PASS |
| the start quiz | none | 25+ of the 36 questions are still answered only in rule files | FAIL until phase 2 (declared) |

## 5. Glossary entries listed as unsupported
All 14 are fixed or marked:
- Owner: the `_Avoid_: user` line is dropped.
- Working branch: now names the production exception.
- Edge list: "fitting lines" is back.
- Sweep: quotes W8 on panes.
- Task manager: the human-direct exception is back.
- Light / heavy: matches old lines 105-106 and 153-154.
- Human and Connected machine: marked "inferred".
- Bounce, Click path, Kick-off round, Production branch, Check line, Tidy: each names its source ("from ...").

## 6. The main manager's decisions (old lines they override)
| decision | new line | old lines it overrides | changes more than the contradiction? |
|---|---|---|---|
| (1) table cap | human.md:35 | 493 (five rows) against 604, 383, 449, 452, 376 (completeness tables never cut) | no |
| (2) CLOSE CASE channel | close-case.md:8 | 369 (SendMessage) against 405 W15 ("never SendMessage") and the dispatch brief CLOSE line | for a task manager, no. For a human-direct session it keeps SendMessage, so the old conflict stays open: 328 W10 "All task manager rules still apply" plus 405 "never SendMessage". skills/close-case C3 says the opposite of the rule until phase 2 |
| (3) scope hold stale | no rule text | code only (agent_checks.py). The rule text 13-15 and 307 stays | no |
| (5) section 33 | branches.md:22 | 165 "(section 33)". The file exists: requirements/check-blocks.md:634 "## 33." | no, it is a clarification |
| (6) main-manager exceptions | roles.md:5 | 239 "Nothing else". Exceptions taken from 25 (R1) and 259 (W7), plus "builds when the owner orders it directly", which has NO old line | YES. It is a new rule. It conflicts with core:21, 248 and 211 ("never write product code") and with 244 ("stays free for the human"). Also, "runs the task itself on plain or cloud" drops 259's "with `Agent` subagents" |
| (7) report shape | human.md:23, :36 | 494 "Nothing else, except the decide section" against 583 E1 "End with one concrete next action" | partly. The next action is settled, but 581 E1 "A command, path or snippet the human must use comes right after the result" is still excluded by "Nothing else" (the author's own open question 7) |
| (9) "Lead with the result" once | PRINCIPLES.md:61 | duplicates 580 / 610 | no |

## 7. Other new problems in draft 2
- The conflict between core:21 and roles.md:5, described in section 6 (6).
- The narrower output.md trigger at core:76, described in section 3.
- The added "follow them" at core:73, described in section 1.
- The "runs these steps" claim in the four "Read when" lines while two skills differ from their rule file, described in section 2.
- setup.md says the settings line twice, and codes.md misses two "also" entries.
- The core is 1,240 words by `wc -w`, over the 1,150 budget. The author flags this.
