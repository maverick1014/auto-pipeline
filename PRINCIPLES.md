# PRINCIPLES

Source of truth for every agent working in this repo. Read this file first. Every rule is one line, plain English, no jargon.

Owner: Maverick. His English is not strong. Write for him.

All numbers below (RAM reserve, agent cap, test slots) are config values, set in the settings menu (S1). Never hard-code them.

---

## A. Repo principle — how this repo is built

**R1. Two lanes.**
Small task = fast lane. Minutes, no pipeline, just do it.
Big task = full pipeline. Plan, build, verify, report.
Task size picks the lane. Never force a small task through the full pipeline.

**R2. Secrets stay out of git.**
Login credentials live in one folder that git ignores (`.secrets/`). Agents may read it. Never write, print, copy or commit it.

**R3. Only three kinds of docs.**
The repo holds only: requirement doc, test doc, main idea doc. No other document, ever.
`PRINCIPLES.md` is the main idea doc.

**R4. No changelog.**
No changelog file. Git history is the record.

**R5. One todo file, one done file.**
`todo.txt` = open tasks only, always current. When a task is done, move the line to `completed.txt`.
Nothing else tracks tasks.

---

## B. Work principle — how an agent does a task

**W1. Finish in one run.**
Do not stop to wait for the human. Pick a default, write it down, keep going.
New ideas go in the final report, never in the middle of the work.

**W2. Mock before build (UI).**
Any UI work starts with a clickable mock (prototype artifact).
Get a yes on the mock. Only then write the real code.

**W3. Test first (TDD).**
Every task: write the failing test, then the code, then make the test pass.
No test = task not started.

**W4. Test only your own part.**
When many agents work together, each agent runs only the tests for the files it changed.
Never the full suite. The full suite runs once, at the end, by the manager.

**W5. Web UI is tested in Claude in Chrome.**
All web-based work is tested with the Claude in Chrome tools, in the real browser. Not Playwright.

---

## C. Human principle — how an agent talks to the human

**H1. One task, one topic.**
Ask only about the current task. Park every other question.
Show parked questions at the end, in one table. Never in the middle.

**H2. Simple words.**
Short sentences. Common words. No jargon unless it is a code name.
If a child could not follow it, rewrite it.

**H3. One report shape, always the same.**
1. Result — done or not, pass or fail.
2. What changed.
3. What the human must decide.
Nothing else.

**H4. Table for anything side by side.**
Comparison, series, feature list, task list, options = table. Never prose.

---

## D. Auto setup principle — what runs by itself

**S1. Settings menu sets up the monitor.**
Human picks options in a menu. The tool writes the agent-monitor config. No hand editing.
The same menu holds every number in this file (S4, S5, S6).

**S2. One resume script.**
Run one command on `claude` resume. It loads everything the session needs:
context, memory, agents, monitor, and every saved agent session (S7).

**S3. Resource guard before heavy work.**
Before starting a new agent or a heavy process: check free RAM and CPU.
Low = wait, or run smaller. Never let the machine become slow.

**S4. RAM reserve for the human.**
At least 80% of RAM stays for the human to use the laptop. Agents and tests share the rest.
Over the line = no new agent, no new heavy process, until it drops back.
Config value: `ram_reserve_percent` (default 80).

**S5. One heavy test slot.**
Only one heavy test run at a time, across all agents. Others wait in a queue.
Config value: `heavy_test_slots` (default 1).

**S6. Agent cap by device.**
Max agents running at once is set by the device spec, and is a config value.
Not a fixed number. Different laptop, different cap.
Config value: `max_agents` (this laptop: 4, maverick-pc2: 6).

**S7. Every agent session is saved and can be recovered.**
Each agent writes its state to a file as it works: task, progress, decisions, next step.
After a shutdown or crash, the resume script (S2) restores every agent from its file.

---

## Map: owner's original concern → principle

| # | Owner's concern (short) | Principle |
|---|---|---|
| 1 | AI asks too many side questions, breaks focus | H1 |
| 2 | AI stops and waits instead of finishing | W1 |
| 3 | Output words too hard | H2 |
| 4 | Report format too hard | H3 |
| 5 | Use tables for comparisons/lists | H4 |
| 6 | Mock UI first, then build | W2 |
| 7 | Settings menu that auto-configures the agent monitor | S1 |
| 8 | Resume script that sets up everything | S2 |
| 9 | Check memory before new agents / heavy process | S3 |
| 10 | Full pipeline + shortcut lane for small tasks | R1 |
| 11 | All tasks are TDD | W3 |
| 12 | Keep at least 80% RAM for the human | S4 |
| 13 | Only one heavy test at a time | S5 |
| 14 | Each agent tests only its own part | W4 |
| 15 | Agent cap by device spec, configurable | S6 |
| 16 | Credentials in a private, read-only-for-agents space | R2 |
| 17 | Web work tested with Claude in Chrome, not Playwright | W5 |
| 18 | Track each agent session, recover after shutdown | S7 |
| 19 | Only requirement / test / main-idea docs in repo | R3 |
| 20 | No changelog | R4 |
| 21 | todo.txt always clean; done tasks go to completed.txt | R5 |
