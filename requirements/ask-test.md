# ask-test — requirements (rule text)

Status: written from the owner's own words (main manager brief TELL 04f17b89, 2026-11-27). By line 1 below, it needs no second yes.
Task: `ask-test` (todo line, small, checks PR REVIEW). Base 4a2f4ff (origin/ap-main-maverick).
Source, owner 2026-11-27: "why you keep stop and ask for me ?" and "i though in principle already written clearly. but why you still make this mistake ?"

## A. What changes

Three lines push the main manager to ask where P1 and W1 say decide.

| # | Where | Old | New meaning |
|---|---|---|---|
| 1 | PRINCIPLES.md R1, "Before the flow" | the owner approves the requirement doc | his request in his own words is the yes of a doc that only writes it down; a doc that adds scope or picks an owner-level option goes to him first (detail: rules/checks.md) |
| 2 | rules/output.md E1 | "Destructive action → confirm first" | destructive = loses the owner's data or work; temp files, caches, records of dead sessions and a checkout switch with a backup first are not (listed in rules/human.md H3) |
| 3 | PRINCIPLES.md "Talking to the human" + rules/human.md H3 | every report ends with a decide section | the decide section is normally none; a question goes in only when it passes the ask test |
| 4 | bin/agent-start.sh quiz | 36 questions | Q37, the main manager's set (rules/human.md): the ask test |

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

## C. Limits

- Every other rule line stays as it is
- The rules block stays within its character cap (tests/test_rules_structure.py BLOCK_CAP); the core within 100 lines and 1,300 words
- The quiz keys of Q1-Q36, the SALT and their text do not change; the counts the tests pin move by one for the main manager (30 → 31); task manager 15 and human-direct 17 stay
