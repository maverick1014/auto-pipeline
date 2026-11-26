# Close case
Read when: the human or the main manager says close case, or a CLOSE CASE report arrives. The skill /auto-pipeline:close-case carries this out; where the two differ, this file wins.

W13. Close case
- Trigger: the human or the main manager runs the skill `/auto-pipeline:close-case`; a task manager's brief holds the rule too
- Subagents never get this rule; only a task manager, a human-direct session or a main manager does
- Task manager or human-direct: start nothing new; workers finish their slice or stop; save agent_state.txt; commit + push (WIP if unfinished). Never lose work
- Report to the upper level: a task manager writes it into its agent_state.txt (`agent-file.sh state add`), the watch wakes the main manager; a human-direct session sends it with SendMessage (decided by the main manager 2026-11-26; the owner can veto); another machine → print it in its own terminal and say so (W10)
- Report first line `CLOSE CASE <name>: finished` or `CLOSE CASE <name>: unfinished`, then done, left + next steps, tests + results, click path, new ideas, TIME line (W11)
- Then wait for the upper decision. Never close itself. A close case from the main manager counts the same as from the human
- Main manager gets a CLOSE CASE report: finished → merge skill. Unfinished → review, then finish first (DONE, then merge) or close now (branch pushed, todo line open, pane closed, worktree removed)
- Log every decision in its agent_state.txt. Human away → decide by the requirement doc, mark it "owner not seen"
- Main manager gets close case from the human = the whole repo: close case to every live task manager and human-direct session in agent_worktree.txt
- Collect every report, decide each, merge what passes, close all panes and worktrees, stop its own crons, update the agent files
- Then one final table to the human: task, result, what changed, what is left, decisions taken for the human. Nothing dropped (the H3 five-row cap does not apply)
- After the table the main manager asks the human, in his language: clean this session for the next round, yes or no? No, or no answer: nothing changes
- Yes: `agent-start.sh --clean` (archives agent_state.txt, writes a short fresh one, says what still runs), then `/clear`. Same main manager, same lock, same name
- Rare, the human wants this session to stop being main manager: he types `! agent-start.sh --release`; the agent never runs it. The next new session is main manager, never Helper
