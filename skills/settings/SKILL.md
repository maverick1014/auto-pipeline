---
name: settings
description: Show the current auto-pipeline settings in a short table. Use when the human asks what a setting is or how to change one.
---
# /settings: show the settings

Words to the human: the Language setting. Keys and values stay as printed.

## Show

Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-settings.sh` and show its table as printed. Nothing else.

## Change

This skill never changes a setting. Settings live only in Claude Code. To change one, tell the human:

change: /plugin -> Installed -> auto-pipeline -> Configure

A change reaches hooks and new agents at the next session start. Never edit a settings file by hand.
