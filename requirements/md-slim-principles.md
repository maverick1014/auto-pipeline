# md-slim-principles: the rules in the new structure

Owner, 2026-11-26: "i just now view the pricnciple files already, i saw it is very long. actually what i want is like the matpoccok that one. i knew his md is very strong and tidy. this is what i want to achieve." On the draft: "i have readthe draft already so far so good. it is much more clearer and human understand able too". On starting the real change: "this can go ya".

## 1. What exists

- Today: `PRINCIPLES.md`, 740 lines, about 12,200 words. Every deciding agent reads all of it at every session start.
- The draft, in `requirements/md-slim-principles/`: `PRINCIPLES.md` (the core, 93 lines), `rules/` (22 files, each with a "Read when:" line), `GLOSSARY.md`, `NOTICE.md` (the license text, unchanged).
- Proof material in the same folder: `proof.md` (655 statements of the old file, each with its new home), `codes.md` (where each of the 44 rule codes is), `compare.md` and `compare2.md` (two passes of an independent agent that compared old and new: nothing lost; every finding fixed), `report.md` (rewords, the decisions, the quiz table, the hook table, the list of scripts and tests that name the old file), `proposed-skill-changes.md` (optional wording).
- The source text of the draft is `PRINCIPLES.md` at main 149710d.

## 2. The rule for this task

The text of the draft is approved. Do not change its meaning. A wording change is allowed only where a script or a test needs it; list every such change in the report (old line, new line, why). The independent comparison runs once more on your result.

Decisions already written into the draft ("decided by the main manager 2026-11-26" in `report.md`); keep them:
1. A table whose value is completeness (the board, the question list, a ledger) is never cut; a summary table in a report keeps the five-row cap.
2. A task manager's CLOSE CASE report goes into `agent_state.txt`; the watch wakes the main manager.
3. Parallel first: the scope hold in `bin/agent_checks.py` `next_lines` is stale. Remove it.
4. "(section 33)" names its file, `requirements/check-blocks.md`.
5. The main manager's "nothing else" has two exceptions: it writes the requirement doc; on plain or cloud it runs the task itself with subagents.
6. A report = the result (with the command or path the human must use), what changed, one concrete next action, the decide section.
7. "Lead with the result" stands once.
8. The new doc kinds (`rules/*.md`, `GLOSSARY.md`, `NOTICE.md`) are allowed: the owner's yes of 2026-11-26. The allowed-docs rule names them.
9. A connected machine = a machine paired in Orca (remove the "inferred" mark). "Human" and "owner": keep the glossary entry as it is; the owner's answer is still open.

## 3. What to build

A. The files in place
1. `PRINCIPLES.md` = the core. `rules/*.md`, `GLOSSARY.md`, `NOTICE.md` at the plugin root, beside it. They ship: the release ship set (`bin/agent_release.py`), the cloud pack (`bin/agent-cloud-pack.sh`, copy and `--update`), the clean-up keep list (`bin/agent_cleanfiles.py`), the rule-text names of the related-tests picker (`bin/agent_level.py`).
2. A pointer in the core must lead an agent in ANY repo to the file: the start text prints the absolute folder of the rule files once; the pointers stay relative to it.
3. Every skill, agent file and script line that cites `PRINCIPLES.md <code>` points to the file `codes.md` gives for that code. The lists are in `report.md` ("What phase 2 must change").
4. Two skills follow their rule file: `close-case` part C 3 (a task manager reports into `agent_state.txt`), `dispatch` (the two options when an urgent task needs a non-urgent task's code).
5. `requirements/md-slim-principles/` keeps only the proof material at the end (`proof.md`, `codes.md`, `compare.md`, `compare2.md`, `report.md`); the draft copies of the rule files are gone from it.

B. The start
6. The start text prints the core, then `rules/output.md` (where it prints section E today), then one line per role: the rule files that role reads before its quiz. After a compaction: the core and the same role line, nothing more.
7. The role reading lists (short on purpose; everything else is read at its moment):
   - main manager: `rules/human.md`, `rules/routing.md`, `rules/approval.md`, `rules/checks.md`, `rules/branches.md`, `rules/worktrees.md`, `rules/watch.md`
   - task manager: `rules/tests.md`, `rules/checks.md`, `rules/watch.md`, `rules/context.md`, `rules/resources.md`
   - a human-direct second session: `rules/roles.md`, then the task manager list
   - worker, deputy, reviewer: nothing at start; their brief and their agent file name what to read
8. The quiz. It stays a gate. Each question carries the file that holds its rule (the table is in `report.md`). A role is asked only the questions whose file is the core or on its reading list; the other questions are not asked at start. A wrong answer names the file to re-read, not a rule code. The 36 questions and their answers do not change in this task; what changes is which role gets which, and the refusal text. Report how many questions each role gets.

C. Hooks point to the rule at its moment
9. One short line, added by the hook that already runs at that moment (the table is in `report.md`): the owner's publish or skip words -> `rules/approval.md`; a dispatch (todo add, a deputy or task manager launch) -> `rules/routing.md`; a merge or a gate call -> `rules/checks.md`, `rules/worktrees.md`; a second session -> `rules/roles.md`; close case -> `rules/close-case.md`; MODE MISMATCH, STALE PLUGIN, a denied push -> `rules/traps.md`; a watch signal -> `rules/watch.md`.
10. A hook line is a pointer, never a gate: it refuses nothing new. At most once per session and moment, so it never becomes noise.

D. Tests
11. Every pin of rule text follows the text to its new file. A test names the file it reads; no helper that glues all files together to make an old pin pass.
12. New structure tests: the core is at most 100 lines and 1,300 words (`wc -w`); a rule file is at most 70 lines and has a "Read when:" line; every rule file is named in the core's "Read when" list and every file named there exists; each of the 44 codes is an anchor in exactly one file; a glossary term is defined once; the start text prints the core and the role line; the ship set and the cloud pack carry `rules/`, `GLOSSARY.md`, `NOTICE.md`.
13. The scope hold: a queued task whose scope touches a running task's files is offered by `todo next`, not held.

## 4. Examples (the failing tests come from these)

- A fresh main manager start prints the core's first line, the line "Read when", the folder of the rule files, and a role line naming `rules/routing.md`; it does not print the text of `rules/ui.md`.
- A task manager start names `rules/tests.md` and not `rules/routing.md`.
- The quiz of a task manager does not ask the question on the owner's publish words; the main manager's does.
- A wrong quiz answer on the worktree rule prints "re-read rules/worktrees.md".
- The owner types "2. need to publish direct after done" to a main manager: the keyword hook line names `rules/approval.md`.
- The release ship set and the cloud pack contain `rules/checks.md`, `GLOSSARY.md` and `NOTICE.md`; the clean-up list does not offer them for removal.
- `grep -rn 'PRINCIPLES.md W13' skills agents bin` finds nothing; the line names `rules/close-case.md`.
- With a core of 101 lines the structure test fails.
- Task A runs with scope `bin/x.py`; queued task B has scope `bin/x.py`: `todo next` offers B.

## 5. Not in this task

- A change of what a rule means, beyond section 2.
- Where the agent files live and which are in git (the task agent-files-local changes the lines on the task files and `bin/agent-init.sh`).
- The time estimate (the task estimate-improve changes `rules/time.md` lines and the estimator).
- The version number and the release.

## 6. After the build

The main manager's reviewers, who did not build it, check it: the comparison of the old text (main 149710d) with the final files once more, and the flow code (start, quiz, hooks, ship set, cloud pack). Then the full run on main and the release.
