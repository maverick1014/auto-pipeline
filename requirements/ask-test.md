# ask-test — requirements (rule text)

Status: written from the owner's words (main manager briefs TELL 04f17b89 and TELL 2e63d2df, 2026-11-27). By line 1 below, it needs no second yes.
Task: `ask-test` (todo line, small, checks PR REVIEW). Base 4a2f4ff (origin/ap-main-maverick).
Source, owner 2026-11-27: "why you keep stop and ask for me ?", "i though in principle already written clearly. but why you still make this mistake ?" and "this dont just record in memories, i want it become a principle, dont just rely on memories. and if all use memories then why principle is use for ?"

## A. What changes

Rows 1-4: three lines pushed the main manager to ask where P1 and W1 say decide. Rows 5-7 (TELL 2e63d2df): verify the launch, and where an owner rule goes.

| # | Where | Old | New meaning |
|---|---|---|---|
| 1 | PRINCIPLES.md R1, "Before the flow" | the owner approves the requirement doc | his request in his own words is the yes of a doc that only writes it down; a doc that adds scope or picks an owner-level option goes to him first (detail: rules/checks.md) |
| 2 | rules/output.md E1 | "Destructive action → confirm first" | destructive = loses the owner's data or work; temp files, caches, records of dead sessions and a checkout switch with a backup first are not (listed in rules/human.md H3) |
| 3 | PRINCIPLES.md "Talking to the human" + rules/human.md H3 | every report ends with a decide section | the decide section is normally none; a question goes in only when it passes the ask test |
| 4 | bin/agent-start.sh quiz | 36 questions | Q37, the main manager's set (rules/human.md): the ask test |
| 5 | PRINCIPLES.md R1 (one line), rules/routing.md W9, rules/watch.md W15, skills/dispatch step 7 | "Verify every launch within 2 min" | an agent counts as started only when seen working (its `STAGE <task>: brief` line, its pane busy on the brief, its first reply); until then "brief sent, not yet confirmed"; TELL FAIL → type the pointer line by hand at once; within 2 min read the pane, a welcome screen = not landed; a watch sweep 'ok' is not proof |
| 6 | rules/files.md R3 + PRINCIPLES.md S8 (one line) | - | a rule the owner gives becomes rule text through a task with PR REVIEW and the quiz, never only an auto memory; memory holds only personal facts that must not go into the public repo |
| 7 | bin/agent-start.sh quiz | 37 questions | Q38, the main manager's set (rules/routing.md): verify the launch |

Ask test: a question goes in only when one of these holds
- a permission check blocks the action
- it is irreversible, outward or outside the repo, and his words do not cover it
- a real product or owner-level choice

## B. Examples (EXAMPLES TEST)

| # | Case | Decide section |
|---|---|---|
| B1 | requirement doc that only writes down his CSV export request | no question |
| B2 | an old temp test folder to delete | no question: not his data or work |
| B3 | a helper name no rule or word of his fixes | no question: a default, logged |
| B4 | a push to another team's repo his words do not cover | one question |
| B5 | Q37 answer | C (only the push) |
| B6 | TELL FAIL, then a watch sweep "ok" (ask-test's own brief, 2026-11-27) | not started: type the pointer by hand, read the pane, report "brief sent, not yet confirmed"; Q38 answer C |

## C. Limits

- Every other rule line stays as it is
- The rules block stays within its character cap; the core within 100 lines and 1,300 words
- The quiz keys of Q1-Q36, the SALT and their text do not change; the counts the tests pin move by two for the main manager (30 → 32); task manager 15 and human-direct 17 stay
- Core room (main manager, TELL aa2c0529, answer (b)): the block had 11 characters left; items 5 and 6 each get one core line and the cap goes up by the least that fits: BLOCK_CAP and RULES_BLOCK_CAP 9700 → 9900 (block 9842 with a 200-character plugin path, under Claude Code's 10,000). No slim pass of other core lines
