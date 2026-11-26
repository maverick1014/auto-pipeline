# Question list
Read when: the human asks for the pending questions, or says he answered the question page. The skill /auto-pipeline:question carries this out; where the two differ, this file wins.

W18. Question list
- Trigger: the human runs the skill `/auto-pipeline:question`; the skill holds this rule per role
- One script, no agent: `bin/agent-file.sh questions`. Main manager: the whole repo. Task manager or Helper: `questions --self`, its own task only. Subagents never
- Sources: `PARKED:` lines, every `todo wait` of kind mock, question or review, and `QUESTION:` lines of agent_state.txt
- A `QUESTION:` line is answered by an `ANSWER:` line after it, before the next QUESTION: line or "=== " header. A worktree on another machine gives one `not read: <path> on <machine>` line
- Each question has a stable id; its title, sub line, facts and lettered options come from `park add` fields (H3), the recommended one marked
- 10 or fewer: a numbered list in chat under the decide heading (H3), nothing dropped; the human answers like `1A 2B — note`
- More than 10: `questions --page <file>` (a file in your scratchpad), publish it with the Artifact tool, capabilities db and user. Then one chat line: the count, the link, answer all, then tell me
- `QUESTIONS PAGE:` line of agent_state.txt holds the url: one url per repo and session, publish with that url (redeploy); a first publish records it with `questions --url <url>`
- No Artifact tool: the chat list of all, nothing dropped
- Done: the human says 答完了, done or answered (or pastes `1A 2B`) while the page still has an open question. The skill (part B) holds the read-answers rule
- Read all answers at once with ArtifactData (list, the answers collection) and the map file; pasted lines go by number through it. Show one table: question, answer
- Per answered question: `questions answer <id> "<answer>"`, then carry on. An unpicked question is still open
- Headers and words in the Language setting
