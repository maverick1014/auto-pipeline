# ESTIMATE

- Requirement doc for the time estimator. Read before changing `bin/agent_estimate.py`, the `estimate`, `backtest`, `retrain` parts of `bin/agent-file.sh`, or the estimate step of `skills/dispatch/SKILL.md`.
- Owner ask, 2026-09-30: when the time data has 30 tasks, learn an estimate from it, backtest it against today's rubric, ship the better one; every 10 new tasks learn again and keep the new version only if its backtest error is lower.
- Owner rules: an estimate = agent WORK minutes only; waits (mock gate, owner question or review, hold, suite slot) never count. No hand-made formula like a median ratio: learn from the data. A time answer to the owner = a duration AND a clock time AND when he is needed next (`bin/agent-file.sh eta`, unchanged).

## Inputs
- Only what is known BEFORE dispatch: lane (fast | full), mock (yes | no), type (page server script docs cloud app data mixed), the one line "what", and the todo name if there is one.
- Facts known only after the task (work, wait, clock, est, bounces, workers, files, lines, tests, adds) are never inputs. Asked for one → refused, the line names it.
- No size word: the finished tasks carry none, so there is nothing to learn it from (decision, task manager, 2026-10-05).

## The data
- The finished tasks of `bin/agent-file.sh data`: every repo on this machine with agent files. A task counts when its line has a work number. Dropped lines and old lines with no work never count.
- `agent-file.sh data --what` = the same table with one more column at the end, `what`: the text between the name and the data block ("-" when empty). Without `--what` the table stays exactly as it is.
- Finish order = the date, then the order of the table (stable).
- Unknown lane ("-") is read as full. Unknown mock is read as no. An unknown type ("-") matches no type.

## How it estimates (the method)
- Nearest past tasks. The pool = past tasks of the same lane (none of that lane → every past task).
- Likeness of a past task = 1 if the mock matches + `type` x (1 if both types are known and equal) + `text` x the text likeness.
- Text likeness = cosine of word weights. Words = lower case runs of a-z and 0-9, 3 letters or more, from the name and the what. Weight = count x (ln((N + 1) / (df + 1)) + 1), N = the tasks in play, df = how many of them have the word.
- Tasks in play = the past tasks used plus the task being estimated. The weights are computed once per estimate (once per backtest task) over them; the leave-one-out runs inside that estimate (settings, range) reuse the same weights.
- The `k` most alike are the neighbours; a tie → the newer task first.
- Estimate = the geometric mean of the neighbours' work (a work of 0 counts as 1), a whole minute (half up), at least 1.
- Range = the estimate x the 20th and the 80th percentile (linear) of actual / estimate over the past tasks, each estimated from all the other past tasks (leave one out). Whole minutes, half up; 1 <= low <= estimate <= high. About 6 tasks in 10 should land inside.
- Settings: `k` in 3, 5, 7; `text` in 0, 1; `type` in 0, 0.5. Training = picking the one setting with the lowest median absolute error, leave one out over the given tasks. A tie → the lowest mean absolute error (clean data ties at 0 a lot); still a tie → the first in that order (k first, then text, then type, each smallest first).
- Python 3.9 standard library only. No new packages.

## The rubric (what it is compared with)
- Today's rubric, rows chosen by facts known before dispatch: lane fast → 5 to 15; mock yes → 60 to 90; type script → 45 to 60; any other → 90 to 120.
- Its estimate = the middle of the row, half up (10, 75, 53, 105). Its range = the row.

## Backtest
- Rolling, oldest to newest. Fewer than 11 tasks → one line `backtest: <N> tasks, needs at least 11`, nothing else.
- Each task with at least 10 tasks finished before it is estimated only from those earlier tasks: the setting is picked from them and the neighbours are taken from them. Nothing that came later is used, so a task's backtest row never changes when tasks are added after it.
- Errors are measured on the whole-minute estimates. Per method: tasks, median absolute error (minutes, one decimal), share within 30% (|estimate - work| <= 0.3 x work, whole percent), share inside its range (whole percent).
- Methods: estimator, rubric, and "todo est" (the est the task really had on its todo line; info only, no range).
- Winner: the estimator only when its median error is strictly lower than the rubric's. A tie → the rubric.

## Versions and retraining
- The file `agent_estimate.txt` in the project root holds the versions and their backtest numbers. Committed with the agent files. Written only by `agent-file.sh retrain` (also when `todo done` runs it), atomic.
- First version (no file, at least 30 tasks): pick the setting from all tasks, run the backtest. Its method = estimator if the estimator won, else rubric. Saved as v1 either way, with the backtest numbers.
- Retrain is due every 10 new tasks: tasks >= the tasks at the last check + 10.
- The check: a new version is trained the same way from all tasks. Both are judged on the new tasks only (the newest, in finish order, since the last check), each estimated only from the tasks before it: the current version with its saved setting (it never saw them), the new one picking its setting from the tasks before each one. A rubric version gives the rubric middle. Keep the new version only if its median error there is strictly lower (decision, task manager, 2026-10-05: neither version is graded on tasks it learned from). Either way the check is saved and the next one is 10 tasks later.
- `todo done` runs the retrain after its line is written, only when due. One line out. A failure never stops `todo done`.

## Commands (all through `bin/agent-file.sh`, the project root as usual)
- `estimate --lane fast|full --mock yes|no --type <t> [--name <name>] "<what>"` → read only. First line `estimate: <m>m work, range <lo>-<hi>m (<estimator|rubric> v<n>, <N> past tasks)`. Then up to 3 lines, the nearest past tasks as the reason, most alike first: `like <name>: <m>m work (<type>, <lane>, mock <yes|no>, <date>)` (an unknown type shows "-"). `<N>` = every task that counts. A rubric version or no file (v0) gives the rubric's estimate and range; the like lines still come from the data (no file: the setting k 3, text 1, type 0.5). A file that does not read is taken as no file.
- `backtest [--tasks]` → read only. First line `backtest: <N> tasks, <T> tested, each from the tasks before it`, then the table (header `method tasks error within 30% in range`, rows `estimator`, `rubric`, `todo est`, columns split by spaces, error like `23.0m`, shares like `40%`, todo est in range `-`), then `winner: estimator` or `winner: rubric`. `--tasks` adds one row per tested task before the table: `task <name> work <w> estimator <e> (<lo>-<hi>) rubric <r>`.
- `retrain [--force]` → due (or --force, with at least 30 tasks): the check, the backtest table, one verdict line last. Not due: one line, nothing written. The file's keys are in the CONTRACT of `tests/test_agent_estimate.py`.
- Verdict lines: `estimate retrain: v1 made from <N> tasks: <estimator|rubric> (...)`, `estimate retrain: kept v<n> (on the <k> new tasks: ...)`, `estimate retrain: not due (<N> tasks, next check at <M>)`, `estimate retrain: not yet (<N> of 30 tasks)`.
- Speed: on 60 tasks, `retrain` well under 30 s, `estimate` under 5 s.

## Wired in
- The dispatch skill's estimate step runs `agent-file.sh estimate`; its minutes go on the todo line as est; its range and like lines are the reason. The rubric numbers live in the script, not in the skill.
- `eta` keeps working from the est on the todo line.
- PRINCIPLES.md (time rules): before a new estimate, `bin/agent-file.sh time`, then `bin/agent-file.sh estimate`. README: the command list shows estimate, backtest, retrain; the files table has `agent_estimate.txt`.
