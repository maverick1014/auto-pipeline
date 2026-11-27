# Roles and sessions
Read when: you need a role's full duties, a defect must go back to its builder, you are a second session in a repo, you open a terminal for an agent, name a session, or message another session.

W6. Roles
- Main manager (the "Main manager model" setting) = the main chat. Assigns tasks, talks to the human, reports, accepts decisions, brainstorms. Nothing else, except: it writes the requirement doc (R1) and it runs the task itself with subagents on plain or cloud (W7) (decided by the main manager 2026-11-26; the owner can veto)
- Fast-lane deputy (the "Helper model" setting) = `agents/fast-lane-deputy.md`, new one per small task: works in its own git worktree, asks its questions first, writes the example tests of a small logic task, runs its blocks, pushes a branch; never merges: a merge deputy merges after the main manager's PR REVIEW and the gate
- Merge deputy (the "Helper model" setting) = `agents/merge-deputy.md`. Merges, then deletes branch and worktree (full lane only; a fast-lane deputy merges its own branch)
- Reviewer (Reviewer model, default opus-5.5:high) = `agents/reviewer.md`: PR REVIEW of every full-lane task and CORE REVIEW (the main manager reviews a fast-lane diff itself); read only; a fail is a fix order to the builder
- Check deputy (the "Helper model" setting) = `agents/check-deputy.md`, read and browser tools only: FLOW CHECK, UI CHECK, re-checks after a bounce, RELEASE SMOKE; a verdict with evidence, the main manager decides
- The main manager stays free for the human: it runs no long check itself; it sends the check deputy and gets a short verdict with evidence
- Task manager (the "Task manager model" setting) = one agent per big feature, in its own worktree (exception: human-direct, W10)
- It writes the tests, briefs workers, judges, verifies every worker result before reporting done to the main manager. Never writes product code
- Worker (the "Helper model" setting) = `agents/worker.md`, subagent of a task manager. Writes code until the task manager's tests pass
- A defect goes back to the worker that wrote it, with evidence (managers never write product code: PRINCIPLES.md, Roles)
- A main manager fix order to a task manager has a fixed shape: where, what is seen, what is expected, evidence (screenshot). The task manager reassigns a subagent
- Names: `bin/agent-name.sh` (SessionStart hook) shows `<repo> Manager`, `<feature> Task Manager`, `<repo> Helper - <Task Name>` (human-direct); it is the SendMessage address after `claude --name`, `/rename` or a resume. `Agent` descriptions: `<feature> Worker <n>: <slice>`, `<task> Deputy`, `<feature> Merge`

W10. Second session in the same repo
- One main manager per repo. `agent-start.sh` keeps a lock in the shared git dir: pid, date, session id, terminal
- Lock owner alive → this session is a task manager (human-direct). Never a second main manager
- Its start text names the main manager: pid, `<repo> Manager`, terminal
- Human wants this session as main manager → the human types `! agent-start.sh --take-over` (full path in the start text); the agent never runs it. The old one is told once, never main again by itself
- Human-direct = only a session the human opened by hand. Agent-spawned agents are never human-direct. They run fully by agent, no human in the loop
- A human-direct session keeps its protection only while the human alone drives it. Once it takes a task from the main manager or reports DONE to it, it runs `agent-file.sh helper-join "<task>"` and is a normal agent
- The merge of its last open task closes its pane and removes its line, like a task manager; the close message names `claude --resume <session id>`
- At start: the script adds a line to `agent_worktree.txt` (status human-direct). Also send the main manager a direct message if a channel exists (Orca)
- The session's end removes that line and its `agent_helper_*` files (the SessionEnd hook); a session that died without the hook: the next main manager's start or housekeep removes it
- Will change files → open its own worktree first (W7). Only looking → no worktree
- Human talks to it directly for now. All task manager rules still apply
- Human says "finish" or "report to main manager" → report done + click path to the main manager, then act as a normal task manager. Merge deputy cleans up
- Finished with nothing to merge → main manager runs `bin/agent-file.sh worktree rm <path>`
- The main manager closes every human-direct session after the human says finish: `orca terminal close --terminal <handle> --json`. Nothing stays parked
- Lock owner dead → take over as main manager, run recovery (S7)
- Talk between sessions: `ListAgents` → find the peer by its name (W6), not listed → the row named after its folder (`<folder>-<xx>`) → `SendMessage` to that name. Two share a name → add the `[ref]` ListAgents prints. Reply to the `from` name. First line of every message = one clear sentence
- Open a second session with the same permission mode and effort as the main manager (`<mode>` from `agent-settings.sh get permission_mode`, effort from the "Models: Main manager model" setting, form model:effort): `orca terminal create --worktree path:<repo> --command "claude --name '<repo> Helper' --permission-mode <mode> --effort <effort>" --json`, then `orca terminal wait --for tui-idle`
- New terminals (dispatch, resume, a Helper, a city click) use the "Permissions: Permission mode" setting, read with `agent-settings.sh get permission_mode`
- Task name: every new or switched task, a plain question too, gets its name first, even before the quiz PASS -> run the full-path `<plugin>/bin/agent-file.sh helper-task "<Task Name>"` from the start text, alone, from the project folder (never cd, never chain it); 2-4 English words, Title Case, the work, not the role; `<repo> Helper - <Task Name>` shows from the human's next prompt
