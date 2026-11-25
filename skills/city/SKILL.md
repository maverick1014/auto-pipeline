---
name: city
description: Start the Agent City, a local 3D office building of the running agents (one floor per repo). Use when the human wants to see or watch the agents.
---
# /city — start the Agent City

1. Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh start` and show its output to the human unchanged (the URL line and the "stops by itself" line). If it says OVER CAP, tell the human the computer is busy and nothing was started.
2. Tell the human: open the URL in a browser. It opens outside the office building (Agent 办公楼); a click on the door goes in. Each repo is one floor (选楼层 picks and orders them), and the sessions sit at their desks as they work. Add `#demo` to the end of the URL to see fake agents.
3. Tell the human: the hooks are read when a session starts, so agents in a new session show up in the city; this session's own subagents may not.
4. To stop: `${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh stop`. It also stops by itself when no browser is open for `city_idle_min` minutes (`agent.conf`).
5. Cloud sessions (claude.ai/code) have no localhost the human can open: say so and stop there. The city is local only.
6. Once the `agent-city` command is installed (`${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh install-shim`, see the init skill), the human can type `agent-city start` (also `status`, `stop`, `demo`) in a plain terminal — not a Claude session — from any folder, not just this one. `${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh remove-shim` takes it away again.
7. Floor designs: `${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh floor rules` prints the rules a floor design must follow, `floor show <repo>` the current one, `floor set <repo> <file|->` checks and saves one. Any AI or person can design a floor this way; the page also offers an interior designer and a do-it-yourself form.
