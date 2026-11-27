# deputy-merge-text: an isolated fast-lane deputy pushes, a merge deputy merges

Owner, 2026-11-27, on the self-audit: "for the fast lane gate issues also need to fix". Found the same day: the cost-rules deputy (launched with `isolation: "worktree"`) could not merge; the harness refuses any git command on the shared main checkout from an isolated agent.

## Today

- fast-lane-simple (merged 0ece711) says the same deputy, resumed with `MERGE`, merges its branch into the working branch in the main checkout. skills/dispatch/SKILL.md launches that deputy with `isolation: "worktree"`, so it never can.
- Every fast-lane merge today needed a merge deputy anyway.

## The rule

1. A fast-lane deputy launched with `isolation: "worktree"` ends with its push and report; it never merges.
2. After the main manager's review and a GATE PASS, a merge deputy (not isolated) merges, cleans up (the deputy's worktree and its `worktree-agent-*` branch too) and closes the todo line.
3. Update every place that says the deputy merges: skills/dispatch/SKILL.md step 2, skills/merge/SKILL.md step 0b, agents/fast-lane-deputy.md, rules/routing.md, rules/roles.md, PRINCIPLES.md R1 ("fast lane → the main manager reviews, the deputy merges": within the core budget), skills/flow-diagram/reference.html (box 5 text and the caption), and the tests that pin the old words.

## Examples

- A fast-lane deputy reports DONE PASS; the main manager reviews the diff, the gate passes; a merge deputy merges, pushes, removes the deputy's worktree and branch, `todo done`.
- No text left says the fast-lane deputy merges.

## Not in this task

The gate logic (task gate-self-check).
