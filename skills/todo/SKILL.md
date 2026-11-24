---
name: todo
description: Show the todo board: one table of every open task, wait on the owner, owner to-do and parked question, then the decide section. Use when the human asks for the todo.
---
# /todo — show the board (PRINCIPLES.md W14)

Words to the human: the language of `agent.conf`. A spawned worker, deputy or reviewer never runs this: do nothing.

1. Your role, from the `YOU:` line of your start text:
   - main manager (`<repo> Manager`): the board of the whole repo, `BOARD=""`.
   - task manager, or a human-direct Helper, or a session with no live main manager: the board of your own task and its workers only, `BOARD=" --self"`.
2. Run this one command from the project folder, nothing else (no agent, no other file read):
   `${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh board$BOARD`
3. Show its output as printed: the table, every row, nothing added, dropped or changed, then its note lines.
4. Then the decide section, heading `## To decide` (zh: `## 要你决定`): one numbered question per row that waits on the owner and per parked question, each with what, why now, evidence, recommendation (H3).
