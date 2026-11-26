# Talking to the owner
Read when: you ask the owner a question or park one, send a report, summary, recap, proposal or audit, or show a table. The language, no rule codes, tables, the decide section and numbered questions: PRINCIPLES.md.

H1. One topic
- Ask only about the current task
- Edge-case question + read access to the real data → count first: how many records or companies it touches. Read-only, aggregates only, name the DB the count came from
- Count is 0 or tiny → take the simplest default, state the count in one line, do not ask
- No read access → ask as before, say the count could not be checked. Never guess a count
- Prefer the simplest change that gives the same result over machinery the data does not need
- Park other questions
- Show them at the end, one table
- Ask everything while the human is here, in one batch
- Human gone → never block, park it. On return lead with one table: issue, evidence, blocks what, interim default, decide, recommendation

H2. Words
- Short sentences
- Common words
- Jargon only for code names

H3. Report
- Result (pass/fail)
- What changed
- One concrete next action (decided by the main manager 2026-11-26; the owner can veto)
- Every report ends with the decide section; its questions are numbered, each with a recommendation: PRINCIPLES.md (Talking to the human). The lines below shape it
- Heading in the Language setting: zh `## 要你决定`, en `## To decide`, other languages a short translation of "to decide"
- Every question to the owner has a number in front; numbers never repeat within one message, and an open question keeps its number in later messages
- When every question is answered, the next new set starts again at 1. While any is open, open ones keep their numbers and new ones continue after the highest open number, never renumber
- Every open question is repeated in the decide section of every reply until the owner answers it, even when the reply gets long
- Each question stands alone: a reader who sees only that line knows what it is about and can decide
- A named thing (PR, task, branch, ticket, file) gets what it is in a few words: `#305 (stock lock settings page)`, never a bare number, tag or code name
- A question names every task/PR/ticket by id AND its title, + the state + what is asked, e.g. "Task t10211 - Milah Enterprise invoice duplicate due to calculation error, pending approval to merge to main". Never an id or code alone ("PR 1211 ready, approve?" is wrong). The owner must be able to decide from that line alone, even waking up cold
- Per question: what, why it needs the human now, one line of evidence, then the recommendation. One or two lines, no long explanation
- Nothing open: keep the heading, one line: none (zh `无`)
- Every question the main manager puts to the owner in a decide section is recorded with `park add` (--why --evidence --options --rec if known), removed when answered (`park rm` or `questions answer`)
- Few numbers. One table at most, five rows or fewer, unless the human asks for the full list; a table whose value is completeness (the board, the question list, a ledger) is never cut (decided by the main manager 2026-11-26; the owner can veto)
- Nothing else: a report is the result (a command, path or snippet the human must use comes right after it), what changed, one concrete next action, the decide section (decided by the main manager 2026-11-26; the owner can veto)
