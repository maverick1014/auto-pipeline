# city-agents-at-desks: workers and deputies sit in the office as agents

Owner, 2026-11-26: "then for the agent city i think for the worker and deputy instead of displaying on the tag only. make it an agent worker will be better on the agent office. is not the office too empty"

## Today (the task manager confirms each point at kick-off and corrects this section)

- The city server keeps every subagent of a session as a citizen of its own (`bin/agent_city.py`: `_handle_subagent_event`, `_spawn_subagent`, kind "subagent", owner = its session).
- The page (`bin/agent-city.html`, `bin/agent-city-assets/`) shows a session as a character at a desk. Its workers and deputies show only as a tag, so a floor where one manager runs five agents looks empty.
- Confirmed at kick-off (2026-11-26, the code): the page keeps every subagent in its sim (talks, relays, asks, its card) but `isSub(c)` (any role outside task-manager, helper, designer) keeps it out of `syncFigs` (never drawn), out of the gap rules, and `seatPlan` parks it at the lift. The tag is `subBadge(row)` ("worker ×2 · deputy ×1"), shown on its session's head tag (`pinOv`) and on its rail row. The toolbar's spawn options say "not drawn".
- The server sends a subagent with `up` = its session's page id ("s:<sid>", or "gov:<terr>" for the area manager's own agents), "" when the session is unknown; it already sends done + leave for every agent of a session that ends. A SubagentStop sends "done" only; "leave" follows after 10 minutes (done_ttl). Reviewer and check deputy arrive as role "other" with their type as label.
- The default floor (no saved design) has one manager desk more than its managers (at most 9) and 1-3 helper desks; overflow sits at the 6 meeting places, and past 6 they stack (index modulo 6).

## The rule

1. Every live subagent is its own character at its own desk on the floor of its repo: worker, fast-lane deputy, reviewer, check deputy, merge deputy, and any other agent a session starts.
2. It sits near the session that started it. Its name plate says what it is and what it works on (its description: the task name and the role), in the page language.
3. It arrives when it starts, shows working and waiting the way a session's character does, and leaves when it stops. A session that ends takes its agents with it.
4. More agents than free desks: the same rule the floor uses today when more sessions arrive than it has desks. A saved floor design stays valid; no design file has to change.
5. Where the agents are shown as characters, the tag no longer stands in for them. A head count that the page already shows stays.
6. `#demo` shows workers and deputies at desks too.
7. The page stays smooth with 30 characters on one floor (the task manager measures the frame time before and after and reports both).

## Examples (the failing tests come from these)

- A session starts two workers: two more characters sit at desks on that repo's floor, each with its own name plate; the session's character stays where it was.
- One worker stops: its character leaves, the other stays.
- The session ends while a worker runs: both leave.
- A reviewer and a merge deputy at the same time: two characters, each named by its role.
- A floor with 4 desks and 6 characters: the overflow rule of today places all 6; nobody overlaps a wall or another character.
- A custom floor design saved before this change loads with no problem line.
- The demo floor shows at least one manager with two agents at desks.
- A subagent event for a session the city does not know: as today (no character, no error).

## Checks

PR REVIEW, EXAMPLES TEST, UI CHECK (a check deputy opens the city in the browser at desktop and phone width: the demo, then a real session with two agents; screenshots; console clean).

## Not in this task

- Agents that run on another machine: the city is local, so a task manager's workers on a connected machine do not reach it. That is its own task (the main manager files it as an idea).
- Floor design rules, the interior designer, the governor, the chat.
- Which floors exist (the task city-ghost-floors).
