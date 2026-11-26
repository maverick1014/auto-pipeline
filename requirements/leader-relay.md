# leader-relay: an owner approval passed on by the Leader bot

Owner, 2026-11-26, typed to his Leader bot (the two lines were checked by the main manager in Leader's transcript):
- "agree with that one, but then the verfiication actualy have a step which is you need to record down my original words and the worker is able to cross checking on the oriignal text. so that it only will be agree with the instruction"
- "hermm forward the request and checking for the auto-pipeline"

## Today

- An owner approval (a task published straight to production, a check block left out, the working branch published, OWNER SIGN) counts only when the tool finds his exact words as a prompt he typed: in this repo's own session (`--owner-quote`), or in the session of another repo's main manager (`--relayed-from <repo folder>`: a repo with a main manager lock). Code: `bin/agent_owner_order.py`, `bin/agent-owner-order.sh`, the approval commands in `bin/agent_checks.py` and `bin/agent_promote.py`; rules: `rules/approval.md`.
- The owner now talks to one bot above every repo manager ("Leader"). Leader is not a repo and has no main manager lock, so an approval he gives Leader is refused and he must type it again in the repo's session.

## The rule

Leader passes on three things: his exact words, the time he typed them, and the path of the transcript file where he typed them. The receiving agent never trusts the relay text: the approval tool opens that transcript itself and accepts only when ALL hold:

1. The source is Leader's chat: the transcript file lies inside the one folder the owner named as Leader's (a new setting, "Leader transcript folder", in /plugin Configure; empty = this feature is off). The real path is compared after links are resolved; a path that leaves the folder, a link pointing out of it, or any other file is refused.
2. The exact quote stands in a message the owner typed himself in that file: a user prompt, as the same-session check defines one. Not a tool result. Not text put into the chat by anyone else: a relayed mail or message, an Orca note, a system reminder, a task notification, a system notification, a pasted block, a command or skill expansion.
3. The time matches: the message that holds the quote carries the time Leader gave (to the minute).
4. A quote under 20 characters counts only as his whole prompt, with the question it answered standing in the assistant message right before it in that same transcript (the rule of the same-session check).

Anything else is refused, with one line saying which point failed: one character changed, no match, the wrong file, the wrong time, a quote that is only inside relayed text.

- The same-session check and `--relayed-from` stay exactly as they are.
- The stored record says where the words were verified ("relayed by Leader", the file, the time), and the gate and the publish print it with the OWNER WORDS lines.
- The deciding agent still reads his words by the approval cases (`rules/approval.md`); the tool only proves they are his.
- The transcript is read only. Nothing of it is copied but the quoted words and their time.
- Threat model as for every gate here: mistakes and shortcuts through the documented commands. A transcript forged by hand is a breach, not a case the tool can catch.

## How it is used

- The approval commands take the relay in one option beside `--owner-quote` and `--means`: the transcript path and the time (for example `--relayed-by-leader <transcript file> --time <when>`; the builder picks the exact form and keeps it the same on every approval command: `todo add --target production`, `todo target`, `todo checks --remove`, the OWNER SIGN line, `agent-promote.sh`).
- `agent-owner-order.sh` gets the matching `verify` form, so a main manager can check a relay before acting on it.
- The rule text (`rules/approval.md`, `rules/cross-repo.md`) gets the case in two or three lines; the quiz gets no new question in this task.

## Examples (the failing tests come from these)

- A transcript in the Leader folder with a user prompt "publish task t9 to production when it is done" at 10:15: the approval with that quote, that file and 10:15 is accepted; the record says relayed by Leader.
- The same with one character changed in the quote: refused, "no such prompt".
- The same quote, time 10:40: refused, "the time does not match".
- The same quote in a transcript outside the Leader folder (another project folder, /tmp, a link inside the Leader folder that points outside): refused, "not Leader's transcript".
- The setting is empty: every relay by Leader is refused, "no Leader folder is set".
- The quote stands only inside a tool result, inside a relayed message block, inside a system reminder, inside a task notification, or inside an assistant message: refused.
- The quote is part of a longer prompt he typed (20 characters or more): accepted, as the same-session check does.
- "ok" as his whole prompt right after an assistant message that holds the numbered question: accepted with `--question`; "ok" inside a longer prompt: refused.
- The transcript file is missing, empty, not JSON lines, or larger than the tool will read: refused with a line, no traceback.
- `--owner-quote` in the repo's own session and `--relayed-from <repo>` behave exactly as before (their tests are not changed).

## Not in this task

Who Leader is or how it sends its message. Any change of what needs an approval. A release of the plugin: that still needs the owner's own words in this repo's session.
