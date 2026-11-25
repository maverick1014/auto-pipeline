---
name: md-slim
description: Keep the files agents read (PRINCIPLES.md, CLAUDE.md, AGENTS.md, skills, agent files, requirement docs) short and exact in meaning. Use when you create or edit one of them, when one has grown or says a thing twice, or when the human calls /auto-pipeline:md-slim.
---
# /md-slim: agent-read files stay short and exact

The reader is an agent. It knows standard technical terms; it does not know this repo. Every line is paid for on every load.
Words to the human: the Language setting.

## Scope

| Files | Reader | What applies |
|---|---|---|
| PRINCIPLES.md, CLAUDE.md, AGENTS.md, skills/*/SKILL.md, agents/*.md, requirement docs | agent | all of this skill |
| README.md, replies and reports to the human | human | W3, W4, W5, W6 only; plain words stay (PRINCIPLES H2) |

Writing rules: any agent that edits an agent-read file. Slim pass: the main manager, or a deputy it sends.

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

W4. Single source of truth
- A rule lives in one file and one section. Elsewhere: a pointer to it, never a copy.
- A copy that must exist (a skill that runs without PRINCIPLES.md loaded) names its source.

W5. No no-op lines
- Delete a line when deleting it changes nothing an agent does.
- No-ops: a restated heading, "be careful", "make sure", history, motivation with no consequence, an example that only repeats its rule.
- The owner's quote stays only where it is the authority of a rule, once.

W6. Only real things
- Every command, path, file, setting name and number is checked before it is written: grep the repo, run `--help`.
- A setting is named by its setting name; its value is never copied into the text.

W7. Shape follows use
- Steps run in order → a numbered list. Facts looked up → a table. Rare detail → its own file, with a pointer that says when to read it.
- Every step has a completion criterion: an output line, an exit code, a file that exists.
- First and most used goes first. A skill's description line holds the trigger words: when to use it.

## Slim pass

1. Inventory, changes nothing. List every statement of the file that changes what an agent does (rule, number, command, name) in a scratch file: `n | line | statement`. Done: the count is written down.
2. Mark each row: keep, merge with n, pointer to <source>, stale (it names a thing that is gone, or contradicts row n), no-op. For a stale or contradicting row check the repo first and decide which side is true (PRINCIPLES P1). Only a real meaning question goes to the owner.
3. Rewrite the file by the writing rules.
4. Prove the meaning is unchanged. Every inventory row has a home: `| n | old statement | new line, pointer, or "removed" | why |`. A row with no home is a lost rule: put it back. Done: rows with a home = the count of step 1.
5. Run the tests that pin the text: `grep -ln "<file name>" tests/*.py`, then those files only. A phrase a test pins changes together with its pin, or stays.
6. Report: lines and words before and after, the removed rows with their reason, the terms unified (old → new), the open meaning questions.

Removing a rule that is neither a duplicate nor stale changes the meaning. A slim pass never does that; it is the owner's call.

Ideas: mattpocock/skills (writing-for-agents, domain-modeling).
