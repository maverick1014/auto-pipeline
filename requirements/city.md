# CITY

- Requirement doc for the Agent City. Read before changing `bin/agent-city*`, `bin/agent_city.py`, `skills/city/`.
- Owner decisions, 2026-09-24. A change to a rule here needs the owner's yes.

## What it is
- Local 3D page. Real agents shown as people in a city. Watch only: never controls an agent, never reads chat text.
- Live mode `/` = real hook events only. Demo mode `/#demo` = fake data, same look, demo-only controls.
- Page text Chinese for now.

## Data path
- `hooks/hooks.json` → `bin/agent-city-hook.sh` → `<city dir>/events.jsonl` → `bin/agent_city.py` → SSE `/events` → page.
- Hook when off: one `test -f`, nothing else. On: one JSON line per event. Bash builtins only.
- Session without `AGENT_ROLE` = governor. Session with `AGENT_ROLE` = citizen. Subagent = citizen.
- A session shows up only if it started with the city hook installed (plugin 0.5.0+).

## Look
- No credits, intro text, legend, or drag hint on the page. Kenney assets are CC0; `License.txt` files stay in `bin/agent-city-assets/`.
- No speed buttons, no pause. The view runs at real time.
- People walk at 1/3 of the 0.5.0 speed. Walk animation slowed to match.
- Right column cards (详情, 市民, 动态): click header to collapse or open; drag header to reorder, inside the column only.
- Card order and collapsed state saved per browser (`localStorage`, every access in try/catch).
- Top counts stay: 干活, 找总督, 休息, 建成.
- No frame around the city: no border line, no rounded box.
- Camera is a perspective camera, not a top-down god view. Default tilt about 30° above the horizon, close to the town hall.
- Drag up/down tilts (about 15° to 60°), drag left/right orbits, wheel/pinch zooms from near street level to the whole island. Never clips into ground or buildings.
- Camera auto-rotates, one turn per 5 min. Stops on drag or zoom, resumes 10 s after. Off under `prefers-reduced-motion`.

## Growth
- One island per repo. All islands on one sea.
- Island size grows with the repo's git-tracked code lines. Not counted: binaries, images, 3D models, vendor, lock files.
- New repo = tiny island with a small town hall only.
- Land edge is beach meeting sea. No brown earth block sides.
- Island shape is uneven: organic coastline, never a square or rectangle. Growth adds land at the edge and keeps it uneven.
- Same repo → same shape every time (shape seeded from the repo identity), so reopening shows the island the owner remembers.
- Repo identity = git common dir. Agents in a worktree land on their main repo's island.
- New land gets buildings. Building type is picked automatically from the kind of work (files touched): tests → test tower, UI → shop, scripts → workshop, docs → library, other → house.
- Buildings are permanent. An agent leaving never removes its building.

## Persistence
- World state (islands, land size, buildings, per repo) lives in one file: `~/.claude/agent-city/world.json`.
- Not in `~/.cache` (cleaners wipe it). Never inside a repo (no git noise).
- Written atomically (tmp + mv). Has a version field `"v"`.
- Broken or unknown file → move it aside as `world.json.bad-<time>`, start fresh, say so in the page log. Never silent.
- Server loads it at start; the first snapshot carries it. Browser closed, server stopped, Mac restarted → same city.
- `events.jsonl` is the feed, not the record. It may be cleared.
- The city is per computer. Another machine has its own city.

## Limits
- Server listens on 127.0.0.1 only, port `city_port`, stops itself after `city_idle_min` with no browser open.
- Start refuses when RAM or CPU is over the cap.
- Cloud sessions: no city (no localhost for the human).
