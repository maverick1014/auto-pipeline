# Time
Read when: you estimate a task, write a TIME line, close a task's time, or answer a time question.

W11. Time
- Every task gets an estimate in minutes before dispatch, on its todo line
- Write your own guess in minutes first, then `estimate ... --guess <m>`; est and guess both go on the todo line (`todo add ... --guess <m>`)
- The est on the todo line is the number `estimate` prints; an est equal to the guess is refused unless `--why "<reason>"`
- `estimate` prints a p50 and a p85 from past errors: say "about p50, 85% sure within p85", never plus or minus fixed minutes
- Estimate = agent work only. Waiting is not work: mock gate, owner question, owner review, hold, queue, suite run
- Waiting is never inside work, the tail or a forecast (owner, 2026-11-26):
- "for those who have waiting time in the task ya, remove the waiting time ya. becasue this esitmation nedto remove those unstable variable such as human waiting time"
- Every done report has one line: `TIME: est <n>m, actual <n>m, wait <n>m`. Actual = agent work only
- Done = merged and cleaned. `bin/agent-file.sh todo done` measures the work itself: minutes from the start minus every wait
- The main manager passes the other facts; a typed `--work` is kept apart (`typed=`) and never wins
- Work over 2× estimate → say it in the report, never silent
- Time comes from `date`, never guessed (a remote machine's clock can drift)
- Scope grows → re-estimate, on the record: `todo est <task> +<m>` keeps the first estimate (est0) and the added minutes apart
- Before a new estimate: `bin/agent-file.sh time`, then `bin/agent-file.sh estimate` (dispatch skill)
- A time question from the human → a duration AND a clock time, and when he is needed next: `bin/agent-file.sh eta`; it prints the board's Done by numbers (p50 and p85)
- The estimator trains its first version at 30 clean tasks, then retrains after every 10 new finished tasks, in the background after `todo done`; a worse model is never kept
- Each `todo done` adds a measures entry
