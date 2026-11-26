# Todo board
Read when: the human asks for the todo board, or you record a wait, a stage, a parked question or an OWNER TODO line. The skill /auto-pipeline:todo shows it.

W14. Todo board
- Trigger: the human runs the skill `/auto-pipeline:todo`; the skill holds this rule per role
- One script, no agent: `bin/agent-file.sh board`. Show its table as printed, every row, then the decide section (H3)
- Main manager: the whole repo. Task manager or Helper: `board --self`, its own task and its workers only. Subagents never
- Rows: open tasks, waits on the owner (mock check, owner question, owner review), `OWNER TODO:` and `PARKED:` lines. Each: task, what in a few words, status, where, est, work, wait, progress, done by
- One row per task: agents under a task (deputy, merge deputy, reviewer, worker, its task manager pane) show as ` · N agents` on its row, never as rows; one with no todo row keeps its own
- A task's owner shows as `[<name>]` after its name
- Status of a wait: `waiting <who> · <what> · waited <n>`, held `hold · <what> · waited <n>`, queued `queue · after <task>`; no stage, no wait: not started. Time cells `-` (not started keeps est)
- Sort: waiting on the owner, running, waiting on others, queued and not started, held, OWNER TODO, parked questions last; oldest first in each group
- Times come from the files, never guessed. Work counts from the first stage minus later waits. Waited: since a run of waits began
- Done by = p50 / p85 clock time (work left + review and merge tail, each from history), `eta` the same
- Today's cell (under 10 clean rows): now + est - work; over est: by progress, else 超出 <n>m
- Progress: `agent-file.sh todo stage <name> <stage> [i/m]` at each step boundary.
- Stages, task manager: brief register mock tests workers verify push report. Main manager: e2e (the review and the checks), merge
- Stage weights are fixed (`bin/agent_conf.py`)
- Live: `board --watch` · `statusline` on or off, 5 lines at most (a warning line counts), queued/held/not started own row if room, rest `+N tasks`. Language: the Language setting
- Record as it happens: `todo wait <name> on <kind> ["<note>"] [--who <name>] [--after <task>]|off` at every mock check, owner question, owner review, hold, queue; `todo where` at dispatch
- `park add` for a parked question (H1); `OWNER TODO:` lines are written with `agent-file.sh state add`
- `agent-guard.sh` records launches by task. The "Rules: Todo before agent" setting, on (default), refuses a main manager launch naming no open todo task: `todo add` first; off records only
- `worker on`: no hooks only.
