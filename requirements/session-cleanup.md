# session-cleanup: a designer or Helper session leaves nothing behind when it ends

Owner, 2026-11-27: "for this office layout file ya, i think need to improve the flow, so that when the designer finish it will not leftover anything".

What he saw on the board ("auto-pipeline Helper (ask the human) running", and two `.git/agent_helper_*` files named "Free Office Layout") came from a Helper session he opened by hand on 2026-11-24 to build the office feature (session 680a5ee4), not from the designer. The designer flow (the city's 请室内设计师 button, session 73a4b0a1 on 2026-11-26) has its own leftovers. This task closes both.

## Today (traced 2026-11-27, file:line in the trace)

Interior designer (AGENT_ROLE=interior-designer, a pane opened by the city server):
- `.git/agent_started_<sid>` and `.git/agent_rules_<sid>` always stay (also `agent_quiz_`, `agent_stale_`, `agent_compact_`, `agent_autoclear_` when made); only a 7-day sweep at a later start removes them. Nothing runs at SessionEnd.
- The pane is closed only through a handle the server keeps in memory: after a server restart or idle stop, in plain mode, or when bye never comes, the pane, its idle claude and a chat-watch process (up to 12 h) stay.
- After bye, a hook line from the still-open pane brings the designer back on the page and in the roster, and a new designer is refused with 409 designer-here.
- `chat.jsonl` keeps every designer conversation forever (9 MB today); `history.jsonl` drops it after 24 h only while a server runs.
- The start hook treats the designer like a task manager: ROLE and QUIZ lines, the task-manager reading list, and its small pane is measured into the pane weight of the memory gate.
- `floor bye` uses the default floors folder; a city run with another floors folder never sees the bye.

Helper (a human-direct session):
- Its human-direct line in `agent_worktree.txt` is never removed by housekeep, so the board shows "<repo> Helper (ask the human)" after the session is gone; its `agent_helper_task_` / `agent_helper_title_` files stay 30 days.

## The rule

1. When a session ends (SessionEnd, or its pane is gone), the plugin removes everything it made for that session id: the `.git/agent_*_<sid>` markers, and for a Helper its human-direct line and its `agent_helper_*` files. The 7-day and 30-day sweeps stay as the fallback for a session that ended without the hook (crash, power off).
2. Housekeep (and the start of the next main manager) removes a human-direct line whose session no longer runs.
3. The designer's pane always closes when the designer is done: `floor bye` closes the designer's own pane (its ORCA_TERMINAL_HANDLE) after writing the bye, so no server memory is needed; the server keeps closing it as today when it holds the handle. A server stop closes the designer panes it opened.
4. A session that said bye never comes back: the city ignores later hook lines of that session id; a new designer can start at once.
5. The city drops an ended session's `chat.jsonl` lines 24 h after it left, like `history.jsonl`, also at load when no server ran in between.
6. The start hook gives the designer only what it needs: no quiz, no task-manager reading list, no pane weight measuring, no auto clear; one line that names its role.
7. The designer command carries the city's floors folder (AGENT_CITY_HOME) so `floor bye` lands where the server looks.
8. Kept on purpose (not leftovers): the floor design `floors/<tid>.json`, its undo history (`floors/<tid>.history.jsonl`, last 5), and Claude's own transcripts.

## Examples (the failing tests come from these)

- A designer session starts and ends (bye): afterwards no `.git/agent_*_<sid>` file, no pane, no chat-watch process, no citizen, no roster entry; the floor design file is there.
- The server restarts between the designer's start and its bye: the pane still closes (the designer closes its own pane).
- After bye, a late hook line of that session id: no citizen comes back; a new designer starts (no 409).
- A Helper session ends: its human-direct line and its `agent_helper_*` files are gone; the board has no Helper row.
- A human-direct line whose session died without the hook: housekeep removes it; a live Helper's line stays.
- `chat.jsonl` holds lines of a session that ended 25 h ago and of one that ended 1 h ago: after a load, only the second remains.
- The designer's start text has no QUIZ line and no reading list; `agent_test_weights.json` gets no pane weight from it.
- A city with a non-default floors folder: the designer's bye is seen and acted on.

## Not in this task

The design editor (自己装修). The floor layout itself. Other repos.
