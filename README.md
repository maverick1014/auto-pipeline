# auto-pipeline

A way to run coding agents so you can read the result, trust it, and not get interrupted.
A main manager agent talks to you, and workers do the coding in the background.

## Install

Claude Code on your own computer, in the repo folder, from your shell:

```
claude plugin marketplace add maverick1014/auto-pipeline --scope project
claude plugin install auto-pipeline@auto-pipeline -s project
```

Or inside Claude Code: `/plugin marketplace add maverick1014/auto-pipeline`, then `/plugin install auto-pipeline`.

Answer the three questions (runtime `auto`, your language, max agents). Open Claude Code in that
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

Want it on every repo you open? Drop `--scope project` / `-s project`.

Cloud sessions (claude.ai/code): the agent handles them with cloud-pack. Nothing to do here.

## Commands

| Command | What it does |
|---|---|
| `/auto-pipeline:init` | One-time project setup. Prints the permissions block. |
| `/auto-pipeline:settings` | Show the settings, or change one ("language en", "max_agents 3"). |
| `/auto-pipeline:todo` | Show every open task, wait, to-do and parked question in one table. |
| `/auto-pipeline:question` | List the questions waiting for you and take your answers. |
| `/auto-pipeline:close-case` | Settle one finished case, or wrap up the whole repo. |
| `/auto-pipeline:clean-up` | List rubbish docs and outdated lines, remove only what you say yes to. |
| `/auto-pipeline:city` | Start the agent city visualiser and print its URL. |

You can also just type a keyword (e.g. "show todo", "看任务"). The list is in `bin/agent-keyword.sh`.

## Change settings

`/auto-pipeline:settings`, or `bin/agent-settings.sh <key> <value>` (for example `bin/agent-settings.sh language zh`).
