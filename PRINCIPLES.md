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
> 小任务走快车道，几分钟解决。大任务才走完整流程。任务大小决定走哪条道。

**R2. Secrets stay out of git.**
Login credentials live in one folder that git ignores (`.secrets/`). Agents may read it. Never write, print, copy or commit it.
> 登录凭证放在 git 不会推的 `.secrets/`。agent 只能读，不能写、不能打印、不能 commit。

**R3. Only three kinds of docs.**
The repo holds only: requirement doc, test doc, main idea doc. No other document, ever.
`PRINCIPLES.md` is the main idea doc.
> repo 里只允许三种文档：需求、测试、主思路。其他一律不写。本文件就是主思路文档。

**R4. No changelog.**
No changelog file. Git history is the record.
> 不写 changelog。git 历史就是记录。

**R5. One todo file, one done file.**
`todo.txt` = open tasks only, always current. When a task is done, move the line to `completed.txt`.
Nothing else tracks tasks.
> `todo.txt` 只放没做完的，随时更新。做完的搬到 `completed.txt`。别的地方不记任务。

---

## B. Work principle — how an agent does a task

**W1. Finish in one run.**
Do not stop to wait for the human. Pick a default, write it down, keep going.
New ideas go in the final report, never in the middle of the work.
> 一口气做完。不要停下来等人。有疑问就用默认值，记下来，继续做。新想法放在最后的报告里。

**W2. Mock before build (UI).**
Any UI work starts with a clickable mock (prototype artifact).
Get a yes on the mock. Only then write the real code.
> 做 UI 先出可点击的 mock。人说 OK 才写真代码。

**W3. Test first (TDD).**
Every task: write the failing test, then the code, then make the test pass.
No test = task not started.
> 所有任务都用 TDD：先写会失败的测试，再写代码，再让测试通过。没测试等于没开工。

**W4. Test only your own part.**
When many agents work together, each agent runs only the tests for the files it changed.
Never the full suite. The full suite runs once, at the end, by the manager.
> 多个 agent 一起做时，每个 agent 只跑自己改过的部分的测试。不跑全量。全量测试最后由 manager 跑一次。

**W5. Web UI is tested in Claude in Chrome.**
All web-based work is tested with the Claude in Chrome tools, in the real browser. Not Playwright.
> 所有网页类工作用 Claude in Chrome 在真浏览器里测。不用 Playwright。

---

## C. Human principle — how an agent talks to the human

**H1. One task, one topic.**
Ask only about the current task. Park every other question.
Show parked questions at the end, in one table. Never in the middle.
> 只问当前任务相关的问题。其他问题先放一边，最后用一个表列出来。

**H2. Simple words.**
Short sentences. Common words. No jargon unless it is a code name.
If a child could not follow it, rewrite it.
> 短句，常用字，不用行话。

**H3. One report shape, always the same.**
1. Result — done or not, pass or fail.
2. What changed.
3. What the human must decide.
Nothing else.
> 报告永远三段：结果、改了什么、要你决定什么。

**H4. Table for anything side by side.**
Comparison, series, feature list, task list, options = table. Never prose.
> 凡是对比、清单、功能列表，一律用表格。

---

## D. Auto setup principle — what runs by itself

**S1. Settings menu sets up the monitor.**
Human picks options in a menu. The tool writes the agent-monitor config. No hand editing.
The same menu holds every number in this file (S4, S5, S6).
> 一个设置菜单，选一选，agent 监控自动配好。本文件里所有数字都在这个菜单里改。

**S2. One resume script.**
Run one command on `claude` resume. It loads everything the session needs:
context, memory, agents, monitor, and every saved agent session (S7).
> 一个 resume 脚本，一跑全部就位，包括之前存下来的 agent session。

**S3. Resource guard before heavy work.**
Before starting a new agent or a heavy process: check free RAM and CPU.
Low = wait, or run smaller. Never let the machine become slow.
> 开新 agent 或重活之前先看内存和 CPU。不够就等或缩小。绝不拖慢机器。

**S4. RAM reserve for the human.**
At least 80% of RAM stays for the human to use the laptop. Agents and tests share the rest.
Over the line = no new agent, no new heavy process, until it drops back.
Config value: `ram_reserve_percent` (default 80).
> 至少 80% 的内存留给人用电脑。agent 和测试只能用剩下的。超线就不准开新东西，等降回来。

**S5. One heavy test slot.**
Only one heavy test run at a time, across all agents. Others wait in a queue.
Config value: `heavy_test_slots` (default 1).
> 重测试同一时间只能跑一个，其他排队。

**S6. Agent cap by device.**
Max agents running at once is set by the device spec, and is a config value.
Not a fixed number. Different laptop, different cap.
Config value: `max_agents` (this laptop: 4, maverick-pc2: 6).
> 同时能跑几个 agent 由机器配置决定，是可改的设定。不同机器不同上限。

**S7. Every agent session is saved and can be recovered.**
Each agent writes its state to a file as it works: task, progress, decisions, next step.
After a shutdown or crash, the resume script (S2) restores every agent from its file.
> 每个 agent 边做边把状态写进文件：任务、进度、决定、下一步。关机或崩溃后，resume 脚本能把每个 agent 恢复回来。

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
