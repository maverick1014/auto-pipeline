# Owner approval
Read when: owner words may be a yes for a task published straight to production, a block left out, the working branch published, or an OWNER SIGN; or a relayed owner order arrives.

R8 (owner approval)
- Approval rule: three places need his yes: a task published straight to production, a block left out, the working branch published; OWNER SIGN too
- The deciding agent reads his words; no fixed sentence, no word list
- The tool only checks the quote is a prompt he typed and stores it with what the main manager read: `--owner-quote "<his words>" --means "<the action>"`; add `--question "<the question>"` when he answered one
- A quote under 20 characters ("1A", "ok") counts only as his whole prompt, with the question it answered
- The gate and promote print the stored pair as OWNER WORDS lines; the report to him repeats them
- Approval cases:
  - A numbered batch: "2. publish direct after done, others wait for my review" -> task 2 gets target production with his words; the others merge into the working branch and wait there for his review
  - No numbers, a task named by its description: exactly one fits -> no question
  - With two similar tasks: check first (todo lines, requirement docs, what he said before); still unsure -> one question that names both, then decide
  - Not a yes now: a question ("is it ready to publish?"), a later time ("publish next week": park one `agent-file.sh state add "OWNER TODO: ..."` line), a refusal
  - A yes after the task was added: `todo target <task> production --owner-quote "<his words>" --means "<the action>"`; the task instance (opened, checks, stage) stays
  - After `todo target <task> production ...` the main manager sends a new fast-lane deputy: a new branch from the production branch, `git cherry-pick` of its own commits, the builder's blocks again, a push
  - Its brief names `late yes of: <task>` and `old branch: <branch>`
  - Then every planned block runs again at its head (PR REVIEW, FLOW CHECK, UI CHECK, CORE REVIEW, OWNER SIGN), then `agent-promote.sh --task` with the new branch; the merge deputy deletes the old branch at cleanup
  - A task already merged (todo line closed): the same deputy cherry-picks its commits from the working branch, under a new todo line `<task>-publish`: target production, his words, `--checks "<its BLOCK list>"`
  - A cherry-pick that conflicts, or a task that depends on other unreleased work -> the main manager tells the owner (W9)
  - A relayed owner order is verified where he typed it: the approval commands take `--relayed-from <the sender's repo folder>` (from the OWNER ORDER header); the record says relayed from that repo
  - `--relayed-from` must be a repo with a main manager lock (now or before); a relay from another machine cannot be verified here and goes to the owner
  - An approval passed on by the Leader bot: the approval commands take `--relayed-by-leader <transcript file> --time "YYYY-MM-DD HH:MM"` (Leader gives his exact words, the minute, the file); the tool opens that transcript itself and accepts only a prompt he typed there; the record says relayed by Leader
  - The file must lie in the Configure folder "Approval: Leader transcript folder" (empty = off: every relay by Leader is refused); refused -> ask the owner
  - A condition the flow already meets ("publish after the tests pass") is a yes; unsure -> one question
  - His short answer to a numbered question counts together with that question: the question stands in the assistant message right before his prompt, as a whole line or sentence (or its numbered key line)
- A production task is added at dispatch: `todo add ... --target production --owner-quote "<his words>" --means "publish <task> to production"`; no second yes later

W12 (relayed owner words)
- Verified owner words that the main manager reads as a yes for that action (approval cases, R8) are his final yes, production included; unsure -> one question. Decider floor (W17) holds
