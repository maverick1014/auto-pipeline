# model-floor: the order header tells the sender's real model, and a model change below the floor is asked first

Owner, 2026-11-27: "C, becasue sometimes that have issues about billing or usage. so just allow will do, is ok, but just stop and ask for the user about this isses is that intended or just a mistake".

## Today

- 15:0x to 16:0x the owner switched the main manager to Sonnet 5.5 medium with `/model` and `/effort` (both write settings.json). The main manager went on writing `[opus-5.5 xhigh]` on every order, copied from its start text. Reviewers, deputies and merge deputies acted on that false header (decider floor, PRINCIPLES.md W17).
- The YOU line (bin/agent_conf.py `you_line`) reads the model and effort once, at the session start. Nothing notices a later `/model` or `/effort`.
- Round 2 (coordinator decision, logged): settings.json is global and a launch flag (`--model`, Agent City and Orca sessions) beats it, so neither says what THIS session runs. The source is the session's own transcript.

## The rule

1. The header `[<model> <effort>]` of an order is the sender's model at the time of the order: the `model` of the latest assistant message in this session's transcript (`transcript_path` of the hook payload; only the tail is read), never copied from the start text and never from settings.json, env or flags. No transcript or no assistant message yet: unreadable. The effort is NOT enforced (no source is session-true after an in-session `/effort`): the header check, the floor check and the MODEL OK record compare the model only. The floor stays: Sonnet and Haiku below, Opus 5.5+ or any Fable at or above.
2. The guard (`bin/agent-guard.sh`, PreToolUse on Agent and on the Orca pane and message commands it already guards) refuses an order whose header model differs from rule 1's current model, with one line: `header [<x> <e>] is not your model [<y>]: write [<y> <your effort>]`. Unreadable current model: no refusal, one note line (fail open: a value that may be stale is never enforced).
3. A hook on every owner prompt (UserPromptSubmit) compares the current model (rule 1) with the last one it saw (stored per session in the repo's git dir). On a change it prints one line to the main manager: `MODEL CHANGED: <old model> -> <new model>`, plus, when the new one is below the floor (W17), `BELOW FLOOR: ask the owner first`.
4. Below the floor and not yet confirmed: the main manager's next reply starts with the question to the owner (intended, for billing or usage, or a mistake?) and sends no order, review, sign or merge before he answers.
5. He says it is intended: stored with his verified words (`agent_owner_order`, like an approval) as `MODEL OK <model>`. From then the main manager works as usual with the honest header; a receiving agent accepts a below-floor header from the main manager while that record holds for that model (the guard and the agents' floor check read it). It ends at the next model change.
6. He says it is a mistake: the main manager waits for him to switch back; nothing else.
7. Task managers, reviewers and deputies keep the floor as now (their model comes from the settings); this task changes only the main manager's case and the header check for every sender.
8. Rule text: PRINCIPLES.md W17 (one line, within the core budget), rules/roles.md or rules/context.md for the detail, and the quiz question about a below-floor header if its answer changes.

## Examples

- Owner runs `/model sonnet` then types "merge cost-rules": the hook prints `MODEL CHANGED: opus-5.5 -> sonnet-5.5` and `BELOW FLOOR`; the main manager asks "You switched me to Sonnet 5.5, below the floor. Intended (billing, usage) or a mistake?" and merges nothing.
- He answers "intended, usage": `MODEL OK sonnet-5.5` is stored; the main manager launches the merge deputy with `[sonnet-5.5 medium]`; the guard lets it through; the merge deputy acts.
- No `MODEL OK` record: a deputy that receives `[sonnet-5.5 medium]` from the main manager does not act and reports.
- On Sonnet, the main manager writes `[opus-5.5 xhigh]`: the guard refuses the launch with `header [opus-5.5 xhigh] is not your model [sonnet-5.5]`.
- He switches back with `/model opus`: `MODEL CHANGED ... -> opus-5.5`, no question, the `MODEL OK` record ends.

## Not in this task

Billing or usage numbers; the choice of model for spawned agents (settings).

A `/model` shows in the transcript from the next assistant reply, so the hook sees it at the prompt after that reply, not at the prompt that follows the `/model` at once.
