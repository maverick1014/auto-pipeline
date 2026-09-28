---
name: init
description: One-time project setup — agent.conf, the task files, .secrets/, AGENTS.md, and it prints the permissions block. Use right after installing the plugin.
---
# /init — set up this project (PRINCIPLES.md S1)

1. Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-init.sh` on the current project.
2. Show its output to the human unchanged, including the permissions block it prints.
3. Tell the human: a plugin cannot add permission rules — he must paste that block into this project's `.claude/settings.json` himself.
4. Tell the human: a cloud session (claude.ai/code) has no `/plugin` command at all, so the only way this plugin reaches a cloud session is the repo's own committed `.claude/settings.json`.
5. Ask the human one short question: install the `agent-city` command in `~/.local/bin`, so `agent-city start` works in any terminal, from any folder? On a yes, run `${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh install-shim` and show its output unchanged (including the PATH hint line, if it prints one). On anything else, skip it; the human can run the same command later.
