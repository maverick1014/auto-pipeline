# fast-lane-simple: every question before dispatch; a small task is one deputy, reviewed by the main manager

Owner, 2026-11-27, his words:
- "1. i tell task to main manager 2. main manager review my request and determine it is big or small task 3. if big task go for TM 4. small task go for deputy 5. for the case of small task fast lane deputy, after done only run the necessary test 6. then that is the end of story."
- "the reviewer is only when needed. ... those question should be ask by the TM before it start the task. same for fast lane deputy if have question before do direct ask the manager will do. dont wait for the end and let reviewer pick the problem."
- "for large task reviewer is needed because it might have some missed out, but for small task actually a single agent is already able to handle on it"
- "who say main manager cannot ask the human. it should be ask until all no problem then only assign the task. and not after assign the task then only give problem."
- "the main manager is the reviewer because the main manager is the one who assign the task, so it should be very clean on what it wants."
- On the developer-estimates idea: "your idea is good for the TM big module task only".

## Today
- Small or big is decided by a time estimate (R1: big = over 2 hours). Estimates are unreliable: on 2026-11-27 the estimator alone was low on 4 of 4 tasks, fresh agents were high on 3 of 4.
- Every task gets a PR REVIEW from a reviewer agent (rules/checks.md lines 6, 15, 33, 36; `LAUNCH_KIND` in bin/agent_checks.py), a check deputy for a visible change and a merge deputy. A one-line setting change runs 4 agents.
- Questions come late: a builder's open points reach the main manager in its done report, or the reviewer finds them (session-cleanup: two Helpers in one folder; runner-integrity: log paths of a red run).
- After the ask test (2026-11-27) the main manager decides unclear points of a request by default instead of asking; they come back as rework.

## The rule
1. Before dispatch the main manager reads the request and the code it touches and asks the owner every unclear point at once (one numbered list, each with a recommendation), until nothing is open. Then it dispatches. After dispatch the owner is asked only owner-level or irreversible calls, as today. The ask test stays for reports, not for the kick-off.
2. Small or big comes from the scope, never from a time estimate. Small: one agent, one slice, no new page and no whole-page re-layout. Big: several slices, a new page, a whole-page re-layout, or a module change across several parts. The estimate stays for the board only.
3. Every builder (task manager, fast-lane deputy) first reads the code it will change, then asks all its questions to the main manager before it edits anything. The deputy ends its first turn with `QUESTIONS:` (numbered, each with its default) or with `NO QUESTIONS` and goes on; the main manager answers by resuming it, and asks the owner only what it cannot answer from his words.
4. Small task: the deputy builds, runs only the necessary tests (BUILD, RELATED TESTS, GUARD TESTS, DIFF SCAN; the example tests first for logic), pushes and reports. The main manager reviews the diff against what it asked and writes the PR REVIEW line itself (`--by` its own name); the gate accepts that line for a fast-lane task. Pass → the same deputy, resumed, merges its branch into the working branch and cleans up (worktree, branch, `todo done`) by the steps the merge deputy runs today. Fail → a fix order to the same deputy, then the main manager reviews again.
5. A small task launches no reviewer, no check deputy and no merge deputy. Exception, the main manager's call: the diff touches money, permissions, deleting data, publish, or the start or hook scripts → it launches a reviewer (CORE REVIEW).
6. A small task that changes what the user sees gets no browser check; the batch report names the change. The gate does not ask a fast-lane task for FLOW CHECK or UI CHECK.
7. Big task: unchanged (reviewer, check deputy for a visible change, gate, merge deputy), plus a kick-off report from the task manager before it builds: its time guess, the split, the risks, and its report-back point (past 1.5x its guess, or a named risk hit). At that point it reports; the main manager adds a worker or gives time.
8. A small task that grows (a second slice, or past 2x its guess) stops and reports, as today; the main manager opens a task manager from its branch.
9. Publish unchanged: one full run per batch, the owner's word.
10. "Builders never verify their own work" stays: the main manager's review is not the builder's.

## Examples (the failing tests come from these)
- Owner: "add emptyTableCell="" to the table setting". Main manager: nothing unclear, small. Deputy: `NO QUESTIONS`, builds, related tests green, pushes. Main manager reads the diff, PR REVIEW pass by itself. Deputy merges into the working branch and cleans up. Agents launched: 1.
- A request with an unclear point: the main manager asks it before any `todo add`; no agent starts until the owner answers.
- The deputy finds the request conflicts with an existing test: `QUESTIONS: 1. ... (default: ...)`; the main manager answers; the deputy goes on. No reviewer finds it later.
- A small diff that touches `bin/agent-start.sh`: the main manager adds a reviewer (CORE REVIEW).
- Gate, fast-lane task, PR REVIEW by the main manager, a page diff and no UI CHECK line: GATE PASS. The same lines on a full-lane task: GATE REFUSED (PR REVIEW must come from a reviewer the main manager launched, UI CHECK missing).
- Big task: the task manager's kick-off says guess 120m, 2 slices, 2 risks, report back at 180m; at 180m it reports instead of going on.

## Files (expected)
PRINCIPLES.md (R1, W1, Roles), rules/routing.md, rules/checks.md, rules/roles.md, skills/dispatch, skills/merge, agents/fast-lane-deputy.md, bin/agent_checks.py (the gate for the fast lane), their tests.

## Not in this task
Model choices (cost-rules, on hold). The board's ETA (board-eta).
