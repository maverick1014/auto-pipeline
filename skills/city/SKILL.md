---
name: city
description: Start the Agent City, a local 3D view of the running agents. Use when the human wants to see or watch the agents.
---
# /city — start the Agent City

1. Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh start` and show its output to the human unchanged (the URL line and the "stops by itself" line). If it says OVER CAP, tell the human the computer is busy and nothing was started.
2. Tell the human: open the URL in a browser; the city fills as agents work. Add `#demo` to the end of the URL to see fake agents.
3. Tell the human: the hooks are read when a session starts, so agents in a new session show up in the city; this session's own subagents may not.
4. To stop: `${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh stop`. It also stops by itself when no browser is open for `city_idle_min` minutes (`agent.conf`).
5. Cloud sessions (claude.ai/code) have no localhost the human can open: say so and stop there.
