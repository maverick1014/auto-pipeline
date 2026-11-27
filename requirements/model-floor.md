# model-floor: the order header tells the sender's real model, and a model change below the floor is asked first

Owner, 2026-11-27: "C, becasue sometimes that have issues about billing or usage. so just allow will do, is ok, but just stop and ask for the user about this isses is that intended or just a mistake".

## Today

- 15:0x to 16:0x the owner switched the main manager to Sonnet 5.5 medium with `/model` and `/effort` (both write settings.json). The main manager went on writing `[opus-5.5 xhigh]` on every order, copied from its start text. Reviewers, deputies and merge deputies acted on that false header (decider floor, PRINCIPLES.md W17).
- The YOU line (bin/agent_conf.py `you_line`) reads the model and effort once, at the session start. Nothing notices a later `/model` or `/effort`.

## The rule

1. The header `[<model> <effort>]` of an order is the sender's model and effort at the time of the order, read from the same sources the YOU line uses (settings.json `model` and `effortLevel`, env, flags), never copied from the start text.
2. The guard (`bin/agent-guard.sh`, PreToolUse on Agent and on the Orca pane and message commands it already guards) refuses an order whose header model or effort differs from rule 1's current value, with one line: `header [<x>] is not your model [<y>]: write [<y>]`. Unreadable current value: no refusal, one note line.
3. A hook on every owner prompt (UserPromptSubmit) compares the current model and effort with the last ones it saw (stored per session in the repo's git dir). On a change it prints one line to the main manager: `MODEL CHANGED: <old> -> <new>`, plus, when the new one is below the floor (W17), `BELOW FLOOR: ask the owner first`.
4. Below the floor and not yet confirmed: the main manager's next reply starts with the question to the owner (intended, for billing or usage, or a mistake?) and sends no order, review, sign or merge before he answers.
5. He says it is intended: stored with his verified words (`agent_owner_order`, like an approval) as `MODEL OK <model> <effort>`. From then the main manager works as usual with the honest header; a receiving agent accepts a below-floor header from the main manager while that record holds for that model and effort (the guard and the agents' floor check read it). It ends at the next model change.
6. He says it is a mistake: the main manager waits for him to switch back; nothing else.
7. Task managers, reviewers and deputies keep the floor as now (their model comes from the settings); this task changes only the main manager's case and the header check for every sender.
8. Rule text: PRINCIPLES.md W17 (one line, within the core budget), rules/roles.md or rules/context.md for the detail, and the quiz question about a below-floor header if its answer changes.

## Examples

- Owner runs `/model sonnet` then types "merge cost-rules": the hook prints `MODEL CHANGED: opus-5.5 xhigh -> sonnet-5.5 medium` and `BELOW FLOOR`; the main manager asks "You switched me to Sonnet 5.5 medium, below the floor. Intended (billing, usage) or a mistake?" and merges nothing.
- He answers "intended, usage": `MODEL OK sonnet-5.5 medium` is stored; the main manager launches the merge deputy with `[sonnet-5.5 medium]`; the guard lets it through; the merge deputy acts.
- No `MODEL OK` record: a deputy that receives `[sonnet-5.5 medium]` from the main manager does not act and reports.
- On Sonnet, the main manager writes `[opus-5.5 xhigh]`: the guard refuses the launch with `header [opus-5.5 xhigh] is not your model [sonnet-5.5 medium]`.
- He switches back with `/model opus`: `MODEL CHANGED ... -> opus-5.5 xhigh`, no question, the `MODEL OK` record ends.

## Not in this task

Billing or usage numbers; the choice of model for spawned agents (settings).
