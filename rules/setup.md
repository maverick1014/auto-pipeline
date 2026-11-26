# Setup and settings
Read when: you set up a repo, read or change a setting, put a number in code, or pack a repo for cloud sessions.

- Numbers that are not settings are fixed constants in `bin/agent_conf.py`. Never hard-code.

S1. Settings
- Settings live only in /plugin -> Installed -> auto-pipeline -> Configure, user level (Claude Code keeps them in `~/.claude/settings.json` `pluginConfigs`)
- Why: the plugin is a developer workflow, one setup for every repo
- Configure holds the 20 settings
- Repo facts (core paths, guard tests, test commands, edges, real-data access) live in the committed `agent_repo.conf` at the main repo root, not in Configure (R8)
- New terminals use the "Permissions: Permission mode" setting, default bypassPermissions
- `/auto-pipeline:settings` shows them as a table and never changes them
- No settings file in a repo, none on a machine: start and init move an old repo or machine settings file into Configure once (keys still unset there only, a value the human set is never overwritten) and say each move
- A cloud session (no plugin) runs the defaults
- Also holds the watch and housekeep config (`housekeep_interval_min`)
- Setup: init offers to merge the permission rules into `.claude/settings.json` (`agent-init.sh --add-permissions`); agents never hand-edit JSON. Manager default `opus-5.5:high`; `xhigh` is an install choice
- Setup: init asks all vs selected repos; `agent-init.sh --scope` writes the files; agents never hand-edit JSON

W17 (settings)
- A Main or Task manager model below the floor is refused; the default is used (`agent_conf.py`)

Cloud pack
- Installing into a cloud repo: the cloud-pack skill (`/auto-pipeline:cloud-pack`, `bin/agent-cloud-pack.sh`; `--update` refreshes only bin, PRINCIPLES.md, VERSION and packed skills/agents)
- A cloud session reads only what is committed: `git clone https://github.com/maverick1014/auto-pipeline /tmp/ap && /tmp/ap/bin/agent-cloud-pack.sh .`, then commit and push (the Claude GitHub App must be on the repo), then open a new session
- The pack lands in `.claude/auto-pipeline/` (bin, PRINCIPLES.md, VERSION), `.claude/skills`, `.claude/agents`, `.claude/settings.json`, one pointer line in `CLAUDE.md`, the four `agent_*.txt`, `.secrets/`, `AGENTS.md`
