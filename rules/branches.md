# Branches, the net, release
Read when: you pick a task's target or base, make an urgent fix, merge into production, end a batch, start or read a nightly or release run, or a full run is red.

R1 (target)
- The target: the user's request decides, read by the approval cases (R8). It says publish or merge to main -> the task, once its own checks pass (its blocks; no full suite), goes straight into the production branch, and the deploy follows by itself (here: the release build; a repo like v4: its own sync)
- No such words, or unclear -> the working branch (ap-main-<name>, setting "Flow: Working branch"); nothing goes to production by itself

R8 (branches, the net, release)
- The full suite is the safety net only: the release run on the working branch and the nightly, never in a task; a heavy test never blocks a merge
- URGENT FIX: branch from the production branch, the smallest fix, PR REVIEW and the light related tests
- Here his verified words at dispatch, read as the publish of that task, are his final yes (W12); no second yes after the fix
- Then merge to production (`agent-promote.sh --task`; the deploy follows) and merge production back into the working branch
- Outside tasks, the net: NIGHTLY RUN, all tests once every night in the background (`agent-nightly.sh`); it gates nothing
- A failure the nightly finds that the causing task's own RELATED or MODULE run did not find is a selection miss: one line, the test and the merge (`agent-nightly.sh --misses`)
- After two weeks the owner reads the selection miss count and decides whether the nightly goes too
- The watch's housekeep pass starts it once a day after 22:00 (`nightly_hour`) when no heavy test runs; no watch alive: the next session start, when the last run is older than 24 hours
- A release needs a green full run on the working branch: the last nightly on that commit, or one background run; no other pre-release run
- Since a green full run on G only .md, mock/, tests/test_*.py or the version line changed: a green top-up on the tip is enough (guard, changed, related tests); a deleted test, other files or a red full: the full run
- `agent-nightly.sh --start` runs the full suite in the background (a top-up when small and faster); `agent-nightly.sh --release-ok` only checks that a green run covers the commit, names the run needed and why
- The automatic nightly always runs the full suite (`--start --nightly`); a frontmatter change, a new or deleted .md in agents/ or skills/ is code
- The working branch (setting "Flow: Working branch", default `ap-main-<name>`) is only a branch
- Everything merged or pushed lands there first, never on the production branch by accident: the main checkout is switched to the working branch
- init switches the main checkout of a new repo to the working branch; in a repo that already uses the plugin the main manager switches it at a quiet point after the start's WORKING BRANCH line
- A repo whose working branch exists but whose main checkout is not switched yet: merges go into the production branch as before (section 33 of requirements/check-blocks.md)
- The working branch is per person (<name> = the git user name in lower case, only letters, digits and "-"): worked out once per clone and stored, pushed to origin
- A task manager or deputy on another machine never derives it again (git user names differ between machines); every brief names the branch
- It belongs to that person: the sweep never deletes it, nobody else merges into it
- Other people publish to the production branch meanwhile: it is merged into the working branch at the start of a batch and again before a publish (`agent-promote.sh --sync`), and the full suite runs on that result
- Batches: tasks given together merge into the working branch; when the last one of the batch is merged, ONE full suite runs on the working branch (`agent-nightly.sh --start`)
- A red batch run goes to a new fixer agent, never back to the builder
- The fixer is a normal task: todo add first, a brief with target, base and both branches, its own PR REVIEW and gate; then `agent-nightly.sh --start` again
- Production from the working branch: only on the owner's approval (verified words) and only from a green commit: `agent-promote.sh --owner-quote "<his words>" --means "<what you read>"`
- A repo with a release build runs it right after, so merged to production = published
- RELEASE RUN: the full suite runs once on the working branch before such a publish (the batch run on that commit counts)
- Release run failures: `agent-nightly.sh --failures` names, for each failing test, the merge that introduced it (it runs that test across the merges since the last green run)
- The new fixer agent gets the test, the merge and that task's requirement, and labels each failure
- "test out of date": update it, cite the requirement line or commit that changed the behaviour on purpose; "real break": fix the code
- No check is deleted without a twin; the fixer's report is a table of these labels: test | merge | task | label | cite or fix
- RELEASE SMOKE after every release: a fresh session uses the released version for real (start, one subagent launch and finish, the user-facing flows that changed)
