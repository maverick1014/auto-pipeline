# Task routing
Read when: the main manager routes a new task, before every dispatch. The skill /auto-pipeline:dispatch carries this out; where the two differ, this file wins.

W9. Task routing (main manager, before every dispatch)
- Read `agent_worktree.txt` first
- Small task (fast lane) → a new deputy subagent in its own git worktree (Agent isolation worktree); it pushes a branch, a merge deputy merges it
- Several small tasks run side by side and never share a checkout (owner 1A 2026-11-25; 21 tasks done this way, median 22 minutes)
- A new task gets its own branch and its own agent, also when it touches a live worktree's module in a different part
- A follow-up on the logic a live task manager is changing right now must go to that task manager (P1), never to a second agent
- Task manager in final stage (compiling worker results) → do not disturb. Hold the task until it finishes
- Otherwise → new worktree (W7). Never an Orca worktree and a task manager for a small task
- `todo done <X>` releases every task queued after X
- The main manager runs `agent-file.sh next` at every wake (a report, a watch signal, a human message) and dispatches what can start: room under the Max memory % limit (S3)
- A task waits only for a real dependency: it needs code that another open task brings (shared first, below)
- A task the owner already approved needs no new question
- A new worktree or pane goes to the connected machine first that has room (W7, S3)
- Target and base (R1; his words by the approval cases of R8): a task that goes straight to production branches from the production branch; a task for the working branch branches from the working branch (it sees the batch's earlier merges): `todo add ... --target production|working --batch <name>`
- The target is per task, not per request: an urgent task branches from the production branch and merges straight into production when it is done, production merged back into the working branch after each; the others branch from the working branch and merge there; the batch's one full suite runs after the last of them
- Before dispatch: does an urgent task need code that only a non-urgent one brings? Yes -> it cannot ship alone: tell the owner at once (ship them together, or move that part into the urgent task), never guess
- A new request may also wait until the working branch is tested and published; the main manager picks what is faster and says which
- Shared first: before parallel features, find the code they share (models, components, APIs); the shared part is its own task, merged first; features that need it wait (`todo wait <name> on queue --after <task>`)
- A task is started in the turn it is added, or its wait is recorded with the reason in that turn
- What only the main manager can do and an agent waits on (a requirement doc, an answer, a decision) comes before work nothing waits on
- The todo line comes first: `todo add` before the worktree, the pane or any agent. The guard refuses a main manager launch for a task that is not open (W14)
