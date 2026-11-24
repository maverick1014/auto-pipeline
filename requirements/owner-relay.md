# owner-relay — requirements (level 3 rules gate)

Status: RULES YES 2026-11-24 (owner "all approve", O1-O3 defaults taken). Step 3 clarifications in section L. Base 8d584c1 (release 0.40.0).
Source: the owner's rule "Relayed owner orders between managers" in ~/.claude/CLAUDE.md on the laptop (2026-11-20); owner 3A 2026-11-20 (after one-watcher); owner 2026-11-24: "this features is needed ya. because it can make the cross communication more reliable".
Goal: a main manager relays an owner order to another repo's main manager; the receiver proves with one command that the owner really typed those words, so it can act without asking him again.

Real data (H1), pc2 2026-11-24, read only, counts only. `~/.claude/projects`: 214 project folders, 273 top-level jsonl files. No `CLAUDE_CONFIG_DIR` and no Orca `claude-profiles` folder on pc2 (the laptop has them).
- 854 user lines have `origin.kind: "human"`. 416 of them carry a model bracket group in their first line (`[Opus 5.5 xhigh] …`): agent briefs typed into a pane with `orca terminal send`. 199 more start like agent text (`Manager here`, `You are the … task manager`, `Brief from …`), the newest on 2026-11-04, before the W17 header. 70 hold a `<pasted_content>` block.
- Other user lines: 42573 tool results, 244 `isMeta`, 66 peer messages, 59 compact summaries.
- So `origin.kind: "human"` + `promptSource: "typed"` means "came in through the terminal", not "the owner typed it" (B3).

## 0. Words

| Word | Meaning |
|---|---|
| config home | a Claude config folder, in this order, each real path once: `$CLAUDE_CONFIG_DIR` (when set), `~/.claude`, every `~/Library/Application Support/orca/claude-profiles/*/home` (Orca profiles; the laptop's main manager runs in one) |
| project folder | `<config home>/projects/<repo path, every character that is not A-Z a-z 0-9 turned into ->`. `/Users/maverick/auto-pipeline` → `-Users-maverick-auto-pipeline`; `/private/tmp/claude-502/x` → `-private-tmp-claude-502-x` (checked on all 214 folders on pc2) |
| transcript | a `*.jsonl` file directly in a project folder. Sub folders (subagent transcripts) are not read |
| normalise | Unicode NFC, every run of whitespace (space, tab, newline) becomes one space, both ends trimmed |
| quote | the owner's words as the sender relays them, normalised |
| prompt text | of a user line: `message.content` when it is a string; when a list, the `text` of its `type: "text"` items joined with a newline. Then every `<pasted_content …>…</pasted_content>` block is cut out (an unclosed one: to the end). Then normalised |
| owner prompt | a user line that passes B1 |
| window | the last `owner_order_hours` hours before now (agent.conf, default 24) |
| minute | the line's `timestamp` (UTC, like `2026-11-24T03:49:21.018Z`) in local time as `YYYY-MM-DD HH:MM` |
| width | the length of the quote; a wide character (East Asian width W or F: Chinese, full-width) counts 2 |
| machine | the short host name: `scutil --get LocalHostName` on macOS, else `hostname -s` |
| tool | `bin/agent-owner-order.sh` (shell entry) + `bin/agent_owner_order.py` (the logic), like agent-level.sh |

## A. Where the transcripts are (verify and line)

| # | Rule | Example |
|---|---|---|
| A1 | Look in the project folder of the repo in every config home. A missing folder is skipped. The folder name comes from the repo path as given and from its real path when that is different | repo `/Users/maverick/auto-pipeline` on the laptop → `~/Library/Application Support/orca/claude-profiles/<id>/home/projects/-Users-maverick-auto-pipeline/*.jsonl` and `~/.claude/projects/-Users-maverick-auto-pipeline/*.jsonl` |
| A2 | Read only transcripts changed inside the window (an older file cannot hold a prompt inside it), newest first. A line that is not valid JSON is skipped, the rest of the file is read | a file last changed 3 days ago → not opened |
| A3 | Repo path: `~` expanded, a trailing `/` cut | `~/v4-plus/` → `/Users/maverick/v4-plus` |
| A4 | No project folder for the repo in any config home → `no transcript for <repo> on this machine (looked in: <homes>)` | |

## B. Which line is an owner prompt

| # | Rule | Example (real field shapes, section I) |
|---|---|---|
| B1 | Owner prompt only when all hold: `type` is `user`; `origin.kind` is `human`; `promptSource` is `typed` or `queued`; no `isMeta: true`; no `isCompactSummary: true`; no `isSidechain: true`; no `toolUseResult` key; no content item of `type: "tool_result"`; not agent-typed (B3) | a typed line and a queued line (owner typed while the session was busy) → owner prompts |
| B2 | Every other line is a kind with a name, used in the reasons (D5): `peer` (`origin.kind: "peer"`), `meta` (`isMeta`), `tool_result`, `compact summary`, `task notification` (`origin.kind: "task-notification"`), `system` (`promptSource` system, scheduled or sdk), `agent-typed` (B3), `pasted` (B4), `assistant` (`type: "assistant"`: the sender's own words), `other` | a quote found only in a peer message → `only in a peer line` |
| B3 | Agent-typed: the first line of the prompt text holds a bracket group that names a model family, any case: `\[[^\]\n]*\b(opus\|sonnet\|haiku\|fable)\b[^\]\n]*\]` | `[Opus 5.5 xhigh] Brief from …`, `v4-plus Manager [Opus 5.5 xhigh] ANSWER …`, `[main manager, Opus 5.5 xhigh] …` → agent-typed. `use opus for this` → owner prompt (no brackets) |
| B4 | Pasted: a quote found only inside a `<pasted_content>` block of an owner prompt is not the owner's own words | the owner pastes a brief that holds the words → `only in a pasted line` |
| B5 | A user line with no `origin` (an older Claude Code) is not an owner prompt (kind `other`): fails closed, the receiver asks the owner | |

## C. Matching

| # | Rule | Example |
|---|---|---|
| C1 | The quote must be an exact substring of the prompt text, both normalised. Case and punctuation count. Never fuzzy | prompt `keep it,  this features\nis needed ya.` holds quote `keep it, this features is needed ya.` |
| C2 | The quote may be part of a longer prompt | quote `this features is needed ya` inside a 3-line prompt → match |
| C3 | Too short: width below `owner_order_min_chars` (agent.conf, default 20) → refused before any search: `quote too short (<width> < <min>)` | `rules yes` (9) → too short. `keep it, this features is needed ya` (35) → ok. `这个功能需要保留很重要` (11 wide = 22) → ok |
| C4 | Empty after normalising → usage error (exit 2) | `--quote "   "` |
| C5 | Matches with the same minute are one match (a resumed session copies its history into a new file); the newest file is shown | same line in `a.jsonl` and `b.jsonl`, both 11:42 → one match |

## D. `agent-owner-order.sh verify` (the receiver)

`verify --repo <sender repo folder> --quote "<words>" [--time <HH:MM | YYYY-MM-DD HH:MM>] [--machine <name>]`

| # | Rule | Example |
|---|---|---|
| D1 | `--machine` given and not this machine → `OWNER ORDER not verified: sender on another machine (<m>, this is <here>)`, exit 1, nothing read | header says `machine <laptop name>`, receiver on pc2 → refused |
| D2 | Exactly one owner-prompt match inside the window → line 1 `OWNER ORDER verified <file> <minute>`, line 2 `match: "<snippet>"` (F2), exit 0. `$HOME` in the file path shows as `~` | `OWNER ORDER verified ~/.claude/projects/-Users-maverick-v4-plus/1f3c….jsonl 2026-11-24 11:42` |
| D3 | `--time` given: only matches at that minute count. `HH:MM` = that clock time on any day inside the window, a full date-time = that minute. Matches exist but none at that time → `not verified: no owner prompt at <time> (found at <minutes>)` | `--time 11:42`, only a match at 11:40 → `not verified: no owner prompt at 11:42 (found at 2026-11-24 11:40)` |
| D4 | Several minutes left → `OWNER ORDER not verified: several owner prompts hold the quote, pass --time`, then one line per match, newest first: `  <file> <minute> "<snippet>"`; exit 1 | owner typed the same words at 11:40 and 11:42, no `--time` |
| D5 | No owner-prompt match inside the window → the first reason that fits: (1) only owner prompts older than the window → `older than <h>h (newest <minute>)`; (2) found only in other kinds → `only in a <kind>[, <kind>] line (<file> <minute>)`, the newest hit shown; (3) nothing → `not found (paraphrased, or typed on another machine?)` | sender changed one word → `not found …` |
| D6 | Every refusal is one stdout line starting `OWNER ORDER not verified: ` (D4 adds its match lines), exit 1 | |
| D7 | Usage error (unknown option, missing `--repo` or `--quote`, bad `--time`): one stderr line, exit 2 | `--time 25:99` → exit 2 |

## E. `agent-owner-order.sh line` (the sender)

`line --quote "<words>" [--repo <folder>]`

| # | Rule | Example |
|---|---|---|
| E1 | Repo default: the git toplevel of `$CLAUDE_PROJECT_DIR`, else of `$PWD`: the folder the session runs in | main manager in `/Users/maverick/auto-pipeline` |
| E2 | Same search as verify (A, B, C) in its own repo's transcripts; several matches → the newest; its minute goes on the header. The sender never types the time by hand | |
| E3 | Prints three lines: `OWNER ORDER [<model> <effort>] repo <folder> · machine <machine> · typed <minute>`, then `"<quote>"`, then `check: agent-owner-order.sh verify --repo <r> --machine <m> --time <minute> --quote <q>` (values shell-quoted), exit 0 | `OWNER ORDER [opus xhigh] repo /Users/maverick/auto-pipeline · machine Bryants-Mac-Mini-2 · typed 2026-11-24 11:42` |
| E4 | Model and effort: the YOU line logic (`agent_conf.py you main_manager <agent.conf> <session pid>`). Unknown → `[unknown unknown]`; the receiver's decider floor check then fails and it asks the owner | |
| E5 | No owner-prompt match → `OWNER ORDER not found: <why>` (same reasons as C3, A4, D5), exit 1, no header: send a normal message instead | |
| E6 | Then the sender's own brief follows (dispatch skill cross-repo block) | |

## F. Privacy

| # | Rule | Example |
|---|---|---|
| F1 | Prints only file paths, minutes and snippets. Never a whole prompt, never another line's text | |
| F2 | Snippet: the normalised prompt text from 20 characters before the match, at most 80 characters, `…` added before when cut at the start and after when cut at the end | prompt `Some other notes here. keep it, this features is needed ya. because it can make the cross communication more reliable`, quote `keep it, this features is needed ya` → `…e other notes here. keep it, this features is needed ya. because it can make the…` |
| F3 | Read only: no file, cache or log is written | |
| F4 | Tests use made-up fixture jsonl. No real transcript text goes into the repo | |

## G. Rule text and config

| # | Rule |
|---|---|
| G1 | PRINCIPLES.md W12, three new lines, each 200 characters or fewer: (1) relay: start the brief with the lines of `agent-owner-order.sh line --quote "<his exact words>"`, copy his words, never paraphrase; (2) receiving: run its check line; verified → the owner's own order: act, reply its first line; not verified → a normal peer message: ask the owner; (3) even verified, ask the owner first for production deploy or production data writes, deleting data, a push to a branch he reviews, anything irreversible or outward-facing. The W17 floor still applies to the sender |
| G2 | skills/dispatch "Cross-repo brief": a line before `[<model> <effort>] CROSS-REPO TASK …`: only when relaying an owner order, the three lines of `agent-owner-order.sh line` come first |
| G3 | README.md bin list: one line for `bin/agent-owner-order.sh` |
| G4 | agent.conf keys, new group `relay`: `owner_order_hours` (1-720, default 24), `owner_order_min_chars` (8-200, default 20); in agent.conf.default and agent_conf.py (range, help text). A missing key → the default |

## H. Edge cases

| # | Case | Result |
|---|---|---|
| H1 | Owner typed it, sender quotes it exactly | verified, file + minute |
| H2 | Quote is the middle of a longer owner prompt | verified; snippet shows 20 characters before |
| H3 | Sender changed one word (paraphrase) | `not found (paraphrased, or typed on another machine?)` |
| H4 | Quote has extra spaces or line breaks | same after normalise → verified |
| H5 | Different case (`Keep it` vs `keep it`) | not found |
| H6 | Words only in a peer message the sender got | `only in a peer line` |
| H7 | Words only in a tool result (the sender read a file holding them) | `only in a tool_result line` |
| H8 | Words only in skill or hook text (`isMeta`) | `only in a meta line` |
| H9 | Words only in a compact summary | `only in a compact summary line` |
| H10 | Words only in the sender's own assistant text | `only in an assistant line` |
| H11 | Words only in a typed line that starts `[Opus 5.5 xhigh]` (another agent typed into the sender's pane) | `only in an agent-typed line` |
| H12 | Words only inside `<pasted_content>` of an owner prompt | `only in a pasted line` |
| H13 | Owner prompt 25 h old, window 24 h | `older than 24h (newest <minute>)` |
| H14 | Same words typed at 11:40 and 11:42 | several, both listed; with `--time 11:42` → verified 11:42 |
| H15 | Same line in two files (resume), same minute | one match, verified, newest file |
| H16 | Sender on the laptop, receiver on pc2 (same repo path on both) | with `--machine` → `sender on another machine`; without → `not found` |
| H17 | No project folder for the repo | `no transcript for <repo> on this machine (looked in: …)` |
| H18 | Transcript only in an Orca profile home | found |
| H19 | `CLAUDE_CONFIG_DIR` set | its projects searched first |
| H20 | A half-written last line in the transcript | skipped, verified from the other lines |
| H21 | Quote `rules yes` | `quote too short (9 < 20)` |
| H22 | A user line without `origin` | not an owner prompt (kind other) |
| H23 | A queued prompt (`promptSource: "queued"`) | owner prompt |
| H24 | Content as a list (an image and a text item) | the text item is used |
| H25 | `--time 11:42`, only a match at 11:40 | `no owner prompt at 11:42 (found at … 11:40)` |
| H26 | Words only in a subagent transcript (`<session>/subagents/…`) | not read → not found |
| H27 | Owner typed the words in another session of the same repo folder (a Helper) | verified: any session of that folder on this machine |
| H28 | `line` when the owner prompt is missing | `OWNER ORDER not found: …`, exit 1, no header |
| H29 | Quote holds `'`, `"` or `$` | the check line is shell-quoted and runs as is |

## I. Real field shapes (pc2, Claude Code 2.1.325-2.1.331; text replaced by `<…>`, ids cut)

```
typed owner prompt  {"type":"user","origin":{"kind":"human"},"promptSource":"typed","turnOrigin":"human","timestamp":"2026-11-24T03:49:21.018Z","message":{"role":"user","content":"<typed text>"},"version":"2.1.331"}
queued              {"type":"user","origin":{"kind":"human"},"promptSource":"queued","turnOrigin":"human","message":{"role":"user","content":"<pasted_content id=\"dd45\"><pasted text></pasted_content> <typed text>"}}
agent-typed         {"type":"user","origin":{"kind":"human"},"promptSource":"typed","turnOrigin":"human","message":{"role":"user","content":"[Opus 5.5 xhigh] <brief text>"}}
peer                {"type":"user","isMeta":true,"origin":{"kind":"peer","from":"uds:/tmp/cc-socks/<pid>.<…>","verifiedPeerPid":<pid>,"name":"<peer session name>","fromMode":"bypass","body":"<peer text>","verifiedLocal":true},"promptSource":"system","turnOrigin":"peer","message":{"role":"user","content":"Another Claude session sent a <…>"}}
tool_result         {"type":"user","toolUseResult":{"stdout":"<…>","stderr":"","interrupted":false},"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"<id>","content":"<…>","is_error":false}]}}
meta (skill text)   {"type":"user","isMeta":true,"message":{"role":"user","content":[{"type":"text","text":"Base directory for this skill: <…>"}]}}
compact summary     {"type":"user","isCompactSummary":true,"isVisibleInTranscriptOnly":true,"message":{"role":"user","content":"This session is being continued <…>"}}
task notification   {"type":"user","origin":{"kind":"task-notification","producer":"session-task","runId":"<id>"},"promptSource":"system","turnOrigin":"task_notification","message":{"role":"user","content":"<task-notification><…>"}}
```
Also seen: scheduled wake (`promptSource: "system"`, `turnOrigin: "scheduled"`, `isMeta`), SDK prompt (`promptSource: "sdk"`), slash command output (no `origin`, `turnOrigin: "human"`, content `<local-command-stdout>…`), interrupt (no `origin`, content list text `[Request interrupted by user]`). None of them pass B1.

## J. Known limits

| # | Limit |
|---|---|
| J1 | An agent that types into the sender's pane without a model header looks like the owner. None seen on pc2 since 2026-11-04 (the W17 header). The still-ask list (G1 line 3) covers the risky acts |
| J2 | Same machine only: the receiver reads local files. Another machine → a normal peer message, ask the owner |
| J3 | A repo path over 200 characters: Claude Code shortens its folder name → not found (fails closed) |

## K. Tests (step 3)

- `tests/test_agent_owner_order.py`: a temp `HOME` with fixture config homes (`~/.claude`, an Orca profile home, `CLAUDE_CONFIG_DIR`), made-up jsonl; one test per row of A-F and H.
- `tests/test_owner_relay_text.py`: the W12 lines (G1), the dispatch block line (G2), the README line (G3).
- `tests/test_agent_conf.py`: the two new keys and the `relay` group (G4).

## L. Step 3 clarifications (same rules; the exact forms the tests pin)

| # | Clarification |
|---|---|
| L1 | B3 reads the first non-empty line of the content after the pasted cut, before normalise (normalise joins all lines) |
| L2 | Kinds are decided in this order: `assistant` (`type: "assistant"`, its `text` items), `tool_result` (`toolUseResult` key or a `tool_result` item), `compact summary`, `peer`, `task notification`, `meta`, `system` (`promptSource` `system` or `sdk`), `other` (no `origin`, an `origin.kind` that is not `human`, `isSidechain: true`, a `promptSource` that is not `typed`/`queued`), then `agent-typed` (B3), `pasted` (B4), else owner prompt |
| L3 | Text searched for a reason (D5), besides the prompt text: the `content` of each `tool_result` item (a string, or its `text` items), with the pasted blocks kept |
| L4 | D5 (2) lists the kinds in the L2 order, joined by `, `, then ` line`; the article is `an` before a vowel: `only in a peer line (…)`, `only in an assistant line (…)`, `only in a peer, tool_result line (…)` |
| L5 | `machine`: `AGENT_FAKE_HOST` when set and not empty (tests, the same switch agent-file.sh has), else `scutil --get LocalHostName` on macOS, else `hostname -s` |
| L6 | D3 not found at the time: `no owner prompt at <time as given> (found at <minute>[, <minute>])`, newest first |
| L7 | An agent.conf value that is missing or out of range → the default (24, 20) |
| L8 | `line` model and effort: the session pid is `$CLAUDE_PID`, else the first claude ancestor (agent-roots.sh `agent_pid`) |
| L9 | A user line that is the owner's prompt and also holds the words in a peer line: the owner prompt wins (verified) |

## Owner choices (defaults taken unless the owner changes them)

| # | Choice | Default |
|---|---|---|
| O1 | 24 h and 20 characters as agent.conf keys (every number is a config value), a wide character counts 2 | yes |
| O2 | B3: a typed line with a model bracket group in its first line is not the owner | yes |
| O3 | E3: `line` prints a ready `check:` line, and the header carries the machine (`--machine`) | yes |
