# estimate-improve: time estimates that hold

Owner, 2026-11-26: "for the time estimate script i leave it to you for doing the self imrpovement will do. keep improving until it is +/- less than 10 minutes". And his hint: "go to online reserach how previously human expect calculate a task outcome need how long time. find the professional way that is being proven is correct ... refer to them and know why they do like this, what is the behind the scene calcualtion".

The main manager owns this task and drives it without asking. This doc is the requirement; it holds what the data and the research showed, so a builder on any machine has it.

## 1. What the owner sees today

- `agent-file.sh estimate` gives minutes of work before dispatch: a kNN over finished tasks (geometric mean), blended 50/50 with the manager's own guess. The todo line carries `est`.
- The board shows "done by" = now + est - work. `agent-file.sh eta` answers the same question another way.
- Backtest 2026-11-26 (266 rows): the blend is within 30% of the real work for 38% of tasks (target in requirements/estimate.md: 50%). Median error 17 min; tasks of 120 min or more: 62.5 min.

## 2. What the data showed (read-only analysis, 266 usable rows of agent_completed.txt)

Inputs are the first problem, not the learner.

| Finding | Number |
|---|---|
| work > clock (impossible) | 61 rows (23%); 35 of them have clock < 15 min: the line was opened after the work began; small tasks get `--work` typed by hand |
| work = est exactly | 17 rows (fast lane 13%) |
| work a multiple of 5 | 54% of rows (about 20% if it were measured) |
| the manager wrote his guess as the est | 24 of the 55 rows that have an own guess |
| `todo est` overwrites the first estimate | the original value is lost, so it cannot be scored |
| est runs high | median est/work 1.30; 66% of rows over; guess/work median 1.67 |
| est >= 120 min: within 30% | written est 28%; the rolling blend would have been 50% (n=58) |
| tail = clock - work - wait, full lane, clean rows | median 28 min, p80 84 (n=79); with bounces 36/119, without 15/47 |
| what relates to work/est | bounces rho 0.44, tests 0.29, adds 0.24, workers 0.19; none is known before dispatch |
| blend weight | 0.5 is the best fixed weight (0: 27%, 0.25: 29%, 0.5: 36%, 0.75: 35%, 1: 24% within 30%, own-guess rows); per-bucket weights over-fit; deflating the guess makes it worse (36% -> 25%) |

Why the board and `eta` disagree: `eta` without `--work-so-far` takes the full est as work left. Heartbeat "work" minutes are typed by the task manager and used in no calculation.

## 3. What the professions learned (research with sources, 2026-11-26)

| Idea | The calculation | Why it works |
|---|---|---|
| Errors multiply | Q = actual / estimate; work with ln Q: bias = its median, spread = its standard deviation | Durations and their errors are log-normal (Little; DeMarco). The log spread is the same for small and big tasks, so minutes of error grow with size |
| Outside view (reference class forecasting; Kahneman, Flyvbjerg) | forecast = estimate x the ratio of similar past tasks at the chosen certainty | It skips the optimistic inside story. Our kNN already does this |
| Evidence-based scheduling (Spolsky) | divide each estimate by a randomly drawn past velocity (estimate/actual), many times; report 5/50/95% dates; keep tasks small | It replays the estimator's own past errors: steady bias cancels, past spread becomes the forecast spread. Intervals built from past errors hit 82% at "90%"; judged intervals hit 68% |
| Flow forecasting (Kanban; Vacanti, Magennis) | percentiles of cycle time; "85% done within X"; for an item of age a: P(done by t) = (F(t) - F(a)) / (1 - F(a)) | History already contains the waits and the rework nobody estimates |
| Cone of uncertainty (Boehm, McConnell; Little) | the range narrows only at decisions, not with time (Little: p90/p10 of remaining work stays 3-4 at every phase) | Only new information removes variance: re-forecast at stage changes |
| Earned schedule | SPI(t) = earned schedule / time passed; total = planned duration / SPI(t) | Pace so far predicts the rest; stable from 20-30% done; treat as a lower bound |
| Critical chain (Goldratt) | plan on 50% estimates; one shared buffer of sqrt(sum of (safe - median)^2) | Padding inside each task is used up (Parkinson, late starts); pooled variance is smaller |
| Merge bias (schedule risk analysis) | parallel slices finish at the MAX; E[max] >= max of the E's | A plan of most-likely durations is late; m parallel slices are on time 50%, 25%, 12.5%, 6% for m = 1..4 |
| Queues | lead time = work + wait; waits ignore task size and explode near full load | Review, merge and owner waits need their own distributions |
| Calibration | score how often a stated interval holds | Stated 90% intervals of people hold 60-70% of the time unless they are scored |

What these fields agree NOT to do: add medians or plan on averages; state a range as plus or minus fixed minutes or a fixed percent; tune a model by MMRE or MAPE (they reward underestimating); trust a stated interval that is never scored; pad each task; apply one fixed uplift or deflation; mix waits into work; expect uncertainty to shrink just because time passes; let the estimate become the target.

What "good" is: 40% within 30% is a log spread of about 0.59, the level of published industry data. 50% within 30% is about 0.46, the best data set found. The often quoted "75% within 25%" has no evidence. Plus or minus 10 minutes at a spread of 0.46 holds for 93% of 10-minute tasks, 29% of 1-hour tasks, 7% of 4-hour tasks. So a fixed number of minutes is the wrong promise for big tasks; the honest promise is a ratio and a certainty.

Full notes with every source: the research agent's notes.md (kept by the main manager); the main sources are listed at the end.

## 4. The measure (fixed, so progress can be compared)

Reported by `agent-file.sh backtest`, rolling, grouped by the ESTIMATE (not by the real work):

1. bias = median of ln(actual/estimate); spread = standard deviation of ln(actual/estimate); for work at dispatch, and for the END time (merged) at dispatch.
2. hit rate of the stated ranges: how many finished tasks landed inside their p50-p85 statement.
3. the live forecast: the median absolute error in minutes of "done by", asked at each stage change, for tasks of one hour or less and for bigger ones.

Targets: spread 0.59 -> 0.46 for work; an "85%" statement holds 80-90% of the time; the live forecast of a running task within 10 minutes at its last two stage changes. Under 10 minutes at dispatch for every task is not a target: the data and the research both say it cannot hold for big tasks.

## 5. What to build, in this order

A. Inputs first (every later step learns from them)
1. `todo done`: work = wall minutes from `started` minus the waits, as the board counts it. A typed `--work` is kept as a second field, never as the label. Warn when work > clock.
2. Each stage change stores its start time on the todo line; `todo done` writes the minutes of every stage, the builder-done time and, for a task manager, the minutes of each slice into the data block.
3. `todo est +m` keeps the first estimate (`est0`) and the added minutes apart.
4. `todo add`: est is the output of `estimate --guess`; est equal to the guess is refused unless `--why "<reason>"` is given.
5. A learner never trains on a row with work > clock, clock over one day, or a missing wait.

B. The model
6. Replace the fixed 50/50 blend by a log-space fit with a slope, rolling: ln(work) = a + b ln(knn) + c ln(guess); kept only when its rolling backtest beats the blend on spread. It must undo the compression of the kNN mean (big tasks ran 2.21 times the kNN number).
7. Ranges come from the history of ln(actual/estimate), never from a guess: `estimate` prints p50 and p85 minutes.

C. The end time
8. "done by" = remaining work + the tail (review, fix rounds, merge), each drawn from its own history, combined by Monte Carlo (10,000 draws); the board shows p50 and p85 clock times. Waits on the owner are shown apart, never inside work.
9. Re-forecast at every stage change with the tasks that had spent at least as long in that stage (the age rule above); for worker slices use the max over the open slices; once 20-30% of the plan is done use the earned-schedule total as a lower bound.
10. `eta` and the board call the same function.
11. Heartbeat work = wall minutes, computed, not typed.

D. Self-improvement
12. `retrain` after every 10 finished tasks; a new model is kept only when the rolling backtest improves; each `todo done` appends the three measures of section 4 to agent_estimate.txt so the trend can be read.
13. A flag on the board when a task's p50 slips by more than the time that passed.

## 6. Examples (the tests are written from these)

- A row with work=20, clock=9 is not used to train, and `todo done` with `--work 20` on a task whose clock is 9 stores work 9 and prints a warning.
- `todo add ... 120 --guess 120` after `estimate` printed 48 is refused without `--why`.
- `todo est x +40` on est 80: est 120, est0 80, added 40.
- With a history where big tasks ran 2 times their kNN number, the fitted model gives a bigger number than the kNN for a big task and about the same for a small one; with fewer than 30 clean rows it falls back to the blend.
- `estimate` prints `p50 <m>, p85 <m>`; on the backtest rows the p85 statement holds for 80-90%.
- The board row of a full-lane task in stage verify shows two clock times (p50, p85) and both are later than now + est - work.
- `eta <task>` and the board print the same p50.
- A task with 3 open slices of 20 min each: the forecast of the slices' end is later than 20 min (the max of three draws).
- After 10 `todo done` a retrain runs; a worse model is not kept.

## 7. Not in this task

Predicting an overrun before dispatch (nothing known then relates to it). Per-bucket blend weights (too few rows). Changing how a task is built or reviewed.

## Sources (main)

Spolsky, Evidence Based Scheduling (joelonsoftware.com/2007/10/26/evidence-based-scheduling/). Flyvbjerg, reference class forecasting (arxiv.org/pdf/1302.3642). Buehler, Griffin, Ross 1994, the planning fallacy. Little, "Schedule estimation and uncertainty surrounding the cone of uncertainty" (toddlittleweb.com). McConnell / Construx, the cone of uncertainty. Vacanti, Actionable Agile Metrics for Predictability; ProKanban, service level expectations. Lipke, earned schedule (earnedschedule.com); Christensen, CPI stability. Goldratt, critical chain. Jørgensen, reviews of software effort estimation (simula.no). Batselier and Vanhoucke 2016, reference class forecasting against earned value and Monte Carlo.
