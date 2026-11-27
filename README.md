# auto-pipeline

A way to run coding agents so you can read the result, trust it, and not get interrupted.
A main manager agent talks to you, and workers do the coding in the background.

## Install

Claude Code on your own computer, from your shell (installs for all your repos):

```
claude plugin marketplace add maverick1014/auto-pipeline
claude plugin install auto-pipeline@auto-pipeline
```

Or inside Claude Code: `/plugin marketplace add maverick1014/auto-pipeline`, then `/plugin install auto-pipeline`. That one lets you pick the scope: all your repos, or only this project.

Set your Language in Configure; the defaults fit the other settings. Open Claude Code in that
repo. Run `/auto-pipeline:init` once, then paste the permissions block it prints into
`.claude/settings.json` (a plugin cannot add permission rules for you):

```
Bash(git push origin --delete *)
Bash(git branch -d *)
Bash(git worktree remove *)
Bash(git worktree prune)
Bash(orca worktree rm *)
Bash(orca terminal close *)
```

Setup asks whether to use auto-pipeline in all repos or only selected ones; change it later with `bin/agent-init.sh --scope ...` (or rerun `/auto-pipeline:init`).

Cloud sessions (claude.ai/code): the agent handles them with cloud-pack. Nothing to do here.

## With or without Orca

- With Orca: the main manager opens task managers in their own terminals and worktrees, and runs several in parallel.
- Without Orca (plain Claude Code): the main manager does the work itself with subagents, one task at a time, no extra terminals.

## Commands

| Command | What it does |
|---|---|
| `/auto-pipeline:init` | One-time project setup. Prints the permissions block. |
| `/auto-pipeline:settings` | Show the settings as a table. |
| `/auto-pipeline:todo` | Show every open task, wait, to-do and parked question in one table. |
| `/auto-pipeline:question` | List the questions waiting for you and take your answers. |
| `/auto-pipeline:close-case` | Settle one finished case, or wrap up the whole repo. |
| `/auto-pipeline:clean-up` | List rubbish docs and outdated lines, remove only what you say yes to. |
| `/auto-pipeline:slim-test-case` | Measure the tests of a repo, merge duplicates and make the slow ones cheaper, with an audit that no check is lost. |
| `/auto-pipeline:slim-markdown` | Keep the files agents read short and exact: one term per concept, the technical term instead of a long description, a proof that no rule is lost. |
| `/auto-pipeline:teacher-teach-me` | Ask anything about this repo. A friendly teacher explains it in very simple words, from a separate agent, so your current chat goes on undisturbed. |
| `/auto-pipeline:city` | Start the agent city visualiser and print its URL. |
| `/auto-pipeline:flow-diagram` | Draw a flow diagram of the agents in the approved style (role tags on top, one diagram, nothing below). |

You can also just type a keyword instead of the command (case does not matter):

| Command | Keywords |
|---|---|
| `/auto-pipeline:init` | setup pipeline, 设置插件 |
| `/auto-pipeline:settings` | show settings, 看设置, 改设置 |
| `/auto-pipeline:todo` | show todo, 看任务, 进度 |
| `/auto-pipeline:question` | show question, 有什么问题, 要我决定什么 |
| `/auto-pipeline:close-case` | close case, 收尾 |
| `/auto-pipeline:clean-up` | clean up files, 清理文件 |
| `/auto-pipeline:city` | open city, 看 agent |
| `/auto-pipeline:teacher-teach-me` | teach me, explain to me, can you explain, 教我, 解释一下, 给我讲讲 |

## Flow diagram

The whole agent flow, from your request to the release, is one page: [`skills/flow-diagram/reference.html`](skills/flow-diagram/reference.html). Open it in a browser to read the flow. It is also the model for any new flow diagram: copy it and change the content ([`skills/flow-diagram/SKILL.md`](skills/flow-diagram/SKILL.md) says how). Update it when the flow changes.

## Change settings

Settings change only in /plugin -> Installed -> auto-pipeline -> Configure. `/auto-pipeline:settings` shows them and never changes them.

The task files (`agent_todo.txt`, `agent_ideas.txt`, ...) are local by default: git-ignored, never committed; the finished records go to the data branch `ap-data`.
To share the ideas and the todo with your team: the Configure settings "Team: Task files in git", "Who may take a task" and "Data branch", or `agent-file.sh files set task_files ideas,todo` (an older repo first runs `agent-file.sh files move`).

Built by Maverick.
