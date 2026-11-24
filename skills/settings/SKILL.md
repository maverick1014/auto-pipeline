---
name: settings
description: Show the current auto-pipeline settings in a short table, or change one ("language en", "max_agents 3"). Use when the human asks about or wants to change a setting.
---
# /settings: show or change a setting

Words to the human: the language of `agent.conf`. Keys and values stay as printed.

## Show

Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-settings.sh` and show it as a short table: key, value, one plain-words meaning. Nothing else.

## Change

The human says a key and a value, e.g. "language en" or "max_agents 3".

1. Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-settings.sh <key> <value>`.
2. Show its one-line answer unchanged. If it refuses the value, show the refusal and the allowed values it prints. Never guess another value.
3. Tell the human it takes effect at the next agent start.

Never edit `agent.conf` by hand. Only that script changes it.
