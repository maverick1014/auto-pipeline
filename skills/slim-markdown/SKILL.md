---
name: slim-markdown
description: Keep the files agents read (PRINCIPLES.md, CLAUDE.md, AGENTS.md, skills, agent files, requirement docs) short and exact in meaning. Use when you create or edit one of them, when one has grown or says a thing twice, or when the human calls /auto-pipeline:slim-markdown.
---
# /slim-markdown: agent-read files stay short and exact

The reader is an agent. It knows standard technical terms; it does not know this repo. Every line is paid for on every load.
Words to the human: the Language setting.

## Scope

| Files | Reader | What applies |
|---|---|---|
| PRINCIPLES.md, CLAUDE.md, AGENTS.md, skills/*/SKILL.md, agents/*.md, requirement docs | agent | all of this skill |
| README.md, replies and reports to the human | human | W3, W4, W5, W6 only; plain words stay (PRINCIPLES H2) |

Writing rules: any agent that edits an agent-read file. Slim pass: the main manager, or a deputy it sends.

Never rewritten: license text, a rule code and its title line (scripts, skills and tests point at them), quoted owner words, text that is a copy of code (change the code, then the copy).

## Writing rules

W1. One rule, one line
- Imperative and positive: the condition first, then the action ("push denied → hand the owner one push line").
- A prohibition only for a real danger, with its reason in a few words.

W2. The technical term, not its description
- A standard term exists → write the term, delete the description.
- Examples: idempotent, atomic write, fast-forward, rebase, race condition, dry run, rollback, invariant, allowlist, least privilege, exit code, single source of truth, debounce.
- Test: would an agent that never saw this repo know the term? Yes → use it bare. No → it is a repo term.
- A repo term (working branch, check block, fixer) is defined once, in one line, in the section that owns it; everywhere else it stands bare.

W3. One term per concept
- Two words for one thing → pick one, replace the other in every agent-read file and in the messages scripts print.
- One word for two things → split it into two terms.
- A pass over one file: list the other places that hold the dropped term; they change in the same task.

W4. Single source of truth
- A rule lives in one file and one section. Elsewhere: a pointer to it, never a copy.
- A copy that must exist (a skill that runs without PRINCIPLES.md loaded) names its source.

W5. No no-op lines
- Delete a line when deleting it changes nothing an agent does.
- No-ops: a restated heading, "be careful", "make sure", history, motivation with no consequence, an example that only repeats its rule.
- The owner's quote stays only where it is the authority of a rule, once.

W6. Only real things
- Every command, path, file, setting name and number is checked before it is written: grep the repo, run `--help`.
- A setting is named by its Configure title; its current value is never copied into the text.
- A fixed constant may stand with its value. A default that another line explains (a name pattern, a limit) stays.

W7. Shape follows use
- Steps run in order → a numbered list. Facts looked up → a table. Rare detail → its own file, with a pointer that says when to read it.
- Every step has a completion criterion: an output line, an exit code, a file that exists.
- First and most used goes first. A skill's description line holds the trigger words: when to use it.

## Slim pass

Duplicates and no-ops give little on a dense file; reword and move give the most.

1. Pins first, changes nothing. Find the tests that read the file (`grep -ln "<file name>" tests/*.py`) and list what they pin: phrases, line-length caps, section order. Done: the pin list is written down.
2. Inventory, changes nothing. One row per bullet, table row or fenced command line that changes what an agent does; split a row whose parts go to different homes. Scratch file: `n | line | statement`. Done: the count is written down.
3. Mark each row:
   - keep
   - reword: the same meaning in fewer words or a standard term (W2); old and new both go into the proof
   - merge with n: only when row n carries every clause of this row; a missing clause moves into row n first
   - pointer to <source>
   - move: rare detail to its own file with a pointer (W7). In PRINCIPLES.md a move is only proposed in the report; the owner decides
   - stale: it names a thing that is gone, or contradicts row n. Check the repo first and say where you looked (PRINCIPLES P1). Code settles it → fix the name or the path. It needs new words or a choice → an open meaning question with the evidence; the line stays
   - no-op
4. Rewrite the file by the writing rules. A pinned phrase stays, or its pin changes in the same pass; a pinned duplicate is marked keep (pinned) and listed.
5. Prove the meaning is unchanged. Every inventory row has a home: `| n | old statement | new line, pointer, or "removed" | why |`. A row with no home is a lost rule: put it back. Done: rows with a home = the count of step 2.
6. Run only the test files that hold a phrase you changed or removed, light ones, one at a time. Done: each passes, or its new failure is listed with the phrase.
7. Report: lines and words before and after (whole file and per section), rows per mark, the removed rows with their reason, each reword (old → new), the terms unified, the proposed moves with their line counts, pins kept and pins changed, the open meaning questions.

Removing a rule that is neither a duplicate nor stale changes the meaning. A slim pass never does that; it is the owner's call.

Ideas: mattpocock/skills (writing-for-agents, domain-modeling).
