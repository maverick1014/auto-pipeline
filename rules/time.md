# Time
Read when: you estimate a task, write a TIME line, close a task's time, or answer a time question.

W11. Time
- Every task gets an estimate in minutes before dispatch, on its todo line
- Write your own guess in minutes first, then `estimate ... --guess <m>`; est and guess both go on the todo line (`todo add ... --guess <m>`)
- Estimate = agent work only. Waiting is not work: mock gate, owner question, owner review, hold, suite run
- Every done report has one line: `TIME: est <n>m, actual <n>m, wait <n>m`. Actual = agent work only
- Done = merged and cleaned. The main manager passes work, wait and the task facts to `bin/agent-file.sh todo done`
- Work over 2× estimate → say it in the report, never silent
- Time comes from `date`, never guessed (a remote machine's clock can drift)
- Scope grows → re-estimate, on the record
- Before a new estimate: `bin/agent-file.sh time`, then `bin/agent-file.sh estimate` (dispatch skill)
- A time question from the human → a duration AND a clock time, and when he is needed next: `bin/agent-file.sh eta`
