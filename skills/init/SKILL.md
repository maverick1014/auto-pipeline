---
name: init
description: One-time project setup — agent.conf, the task files, .secrets/, AGENTS.md, and it prints the permissions block. Use right after installing the plugin.
---
# /init — set up this project (PRINCIPLES.md S1)

1. Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-init.sh` on the current project.
2. Show its output to the human unchanged, including the permissions block it prints.
3. Tell the human: a plugin cannot add permission rules — he must paste that block into this project's `.claude/settings.json` himself.
