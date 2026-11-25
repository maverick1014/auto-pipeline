---
name: city
description: Start the Agent City, a local 3D view of the running agents. Use when the human wants to see or watch the agents.
---
# /city — start the Agent City

1. Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh start` and show its output to the human unchanged (the URL line and the "stops by itself" line). If it says OVER CAP, tell the human the computer is busy and nothing was started.
2. Tell the human: open the URL in a browser; the city fills as agents work. Add `#demo` to the end of the URL to see fake agents.
3. Tell the human: the hooks are read when a session starts, so agents in a new session show up in the city; this session's own subagents may not.
4. To stop: `${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh stop`. It also stops by itself when no browser is open for the "City: City auto close (min)" setting.
5. Cloud sessions (claude.ai/code) have no localhost the human can open: say so and stop there. The city is local only.
6. Once the `agent-city` command is installed (`${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh install-shim`, see the init skill), the human can type `agent-city start` (also `status`, `stop`, `demo`) in a plain terminal — not a Claude session — from any folder, not just this one. `${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh remove-shim` takes it away again.
