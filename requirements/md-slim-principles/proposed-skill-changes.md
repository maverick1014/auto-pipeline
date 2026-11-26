# Proposed skill wording (phase 2; no skill is edited here)
Every rule lives in a file an agent reads: PRINCIPLES.md or rules/. The skills run the steps and stay as they are. The lines below are wording a skill could take later; no rule depends on them.

## Needed in phase 2 (a skill now says the opposite of its rule file)
- skills/close-case/SKILL.md part C step 3: "with `SendMessage`" → "a task manager: `agent-file.sh state add` into its agent_state.txt (the watch wakes the main manager); a human-direct session: `SendMessage`" (rules/close-case.md, W13; decided by the main manager 2026-11-26)
- The title lines cite `PRINCIPLES.md W..` today: skills/dispatch "(PRINCIPLES.md W9, W7)" → "(rules/routing.md W9, rules/worktrees.md W7)"; skills/close-case "(PRINCIPLES.md W13)" → "(rules/close-case.md W13)"; skills/todo "(PRINCIPLES.md W14)" → "(rules/board.md W14)"; skills/question "(PRINCIPLES.md W18)" → "(rules/questions.md W18)"; the same for every other skill and agent file that cites a code (codes.md)

## Optional
- skills/dispatch/SKILL.md step 1: "Read `agent_worktree.txt` first" (rules/routing.md, W9)
- skills/dispatch/SKILL.md target paragraph, after "tell the owner at once": "(ship them together, or move that part into the urgent task)" (rules/routing.md, W9)
- skills/dispatch/SKILL.md step 7: "Never an Orca worktree and a task manager for a small task" (rules/routing.md, W9)
- skills/dispatch/SKILL.md: "Beyond the reviewer's PR REVIEW, a second agent's opinion ..." → a pointer "A second opinion: rules/checks.md (R8)" (the rule lives there; the skill holds a copy)
- skills/close-case/SKILL.md part B step 4: "Then `agent-file.sh show` to check the agent files" → "update the agent files, then `agent-file.sh show` to check them" (rules/close-case.md, W13)
- skills/close-case/SKILL.md part B step 5: add "(the H3 five-row cap does not apply)"; part B step 8: add "The next new session is main manager, never Helper"; part C step 4: add "A close case from the main manager counts the same as from the human" (rules/close-case.md, W13)
- skills/todo/SKILL.md: a line "What the board shows (rows, status, sort, times, stages, live view): rules/board.md (W14); show it as printed" 
- skills/question/SKILL.md part A: "Sources and the stable id of each question: rules/questions.md (W18)"
