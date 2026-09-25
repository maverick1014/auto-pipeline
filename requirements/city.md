# CITY

- Requirement doc for the Agent City. Read before changing `bin/agent-city*`, `bin/agent_city.py`, `skills/city/`.
- Owner decisions, 2026-09-24. A change to a rule here needs the owner's yes.

## What it is
- Local 3D page. Real agents shown as people in a city. Never reads chat text.
- Not watch-only: agents' questions and permission requests are answered from it (see Interaction).
- Live mode `/` = real hook events only. Demo mode `/#demo` = fake data, same look, demo-only controls.
- Page text Chinese for now.

## Data path
- `hooks/hooks.json` → `bin/agent-city-hook.sh` → `<city dir>/events.jsonl` → `bin/agent_city.py` → SSE `/events` → page.
- Hook when off: one `test -f`, nothing else. On: one JSON line per event. Bash builtins only.
- Session without `AGENT_ROLE` = governor. Session with `AGENT_ROLE` = citizen. Subagent = citizen.
- A session shows up only if it started with the city hook installed (plugin 0.6.0+).

## Look
- No credits, intro text, legend, or drag hint on the page. Kenney assets are CC0; `License.txt` files stay in `bin/agent-city-assets/`.
- No speed buttons, no pause. The view runs at real time.
- People walk at 1/3 of the 0.5.0 speed. Walk animation slowed to match.
- Right column cards (详情, 市民, 动态): click header to collapse or open; drag header to reorder, inside the column only.
- Card order and collapsed state saved per browser (`localStorage`, every access in try/catch).
- Top counts stay: 干活, 找总督, 休息, 建成.
- No frame around the city: no border line, no rounded box.
- Camera is a perspective camera, not a top-down god view. Default tilt about 30° above the horizon, close to the town hall.
- Drag up/down tilts (about 15° to 60°), drag left/right orbits, wheel/pinch zooms from near street level to the whole territory. Never clips into ground or buildings.
- Camera auto-rotates, one turn per 5 min. Stops on drag or zoom, resumes 10 s after. Off under `prefers-reduced-motion`.

## Interaction
- An agent that asks (AskUserQuestion) or needs a permission walks to the governor. Governor = main manager session of that repo.
- Chain of command, same as the real pipeline: worker → its task manager (the lead) → the governor → the owner. A worker's question goes to its task manager first; only what the task manager cannot decide goes on to the governor; only what the governor cannot decide gets the owner's "?".
- Every territory has its own governor: the main manager session of that repo. Task managers are leads with their own site office; their workers live and walk around it.
- The governor really answers questions.
- Permission requests are never approved by the governor (Claude Code's safety check blocks it; owner decision 2026-09-25: keep it that way). Every permission request goes straight to the owner: red "?" at once, the owner reviews and decides.
- Governor cannot decide, or no answer within `city_governor_wait_sec` (default 60) → red "?" above the agent.
- Owner clicks the "?": sees the exact question or request (tool + command or path) and answers, approves or denies in the page.
- First answer wins, from any side (governor, page, terminal). The others see it closed.
- Every answer and approval is logged: who (governor or owner), what, when. In the page log and in `~/.claude/agent-city/decisions.jsonl`. Never silent.
- Control requests: 127.0.0.1 only, a random token per server start on every request, Origin and Host checked. No other website can answer or approve.
- City off or server down → the agent falls back to its normal terminal prompt, no waiting.
- Out of scope: Claude Code's own cross-session message hold ("Deliver this message"). Never auto-clicked.
- Build order: prove first, with a real session, how an answer or approval reaches it (hook decision or Orca terminal keys). Then build.

## Growth
- One territory per repo. All territories on one land, not islands on a sea.
- Territories are split by a natural gap: river, ravine, mountain pass or forest. A bridge or road joins neighbours, so people could cross.
- Where the land ends it may meet sea (the coast terrain); that is the only sea.
- Territory size grows with the repo's git-tracked code lines. Not counted: binaries, images, 3D models, vendor, lock files.
- New repo = tiny territory with a small town hall only.
- The city is never empty: when the server starts it shows the territory of the dir it was started from (its git repo; a plain folder counts too), plus every territory saved in world.json, at once, before any agent acts.
- Minimum size: every territory, even an empty repo with 0 code lines, has at least a small land, a town hall and a few open plots (about 3), so the first agents can build.
- A build that finds no free plot says so in the page log (e.g. "r1 没有空地了，先等等"). Never silent.
- Old data is dropped (owner 2026-09-25, nobody uses it): territories saved without a repo identity are removed from world.json on load; events without a repo go to the start territory, never make their own.
- Zoom in and out always move; the governor stands at a hall, never in the void.
- Territory edge is natural: river bank, cliff, forest edge, or beach on the coast. No brown earth block sides, no hard line.
- Territory shape is uneven: organic edge, never a square or rectangle. Growth adds land at the edge and keeps it uneven.
- Same repo → same shape every time (shape seeded from the repo identity), so reopening shows the territory the owner remembers.
- Repo identity = git common dir. Agents in a worktree land on their main repo's territory.
- 5 hand-made town plans. Each plan: edge line, roads, town hall spot, bridge or road spots to neighbours, districts, and preset building plots with a growth order.
- Each plan has its own terrain: grassland, mountain, desert, forest, coast. Terrain changes the look only (ground, plants, path material: cactus on desert, pines on mountain, sand paths on coast). Rules are the same on every terrain.
- Day 0 = bare terrain with a tiny town hall, nothing else. Everything that appears later comes from the repo.
- Each repo gets one plan, picked from the repo identity (stable, not a new pick each start).
- Growth unlocks the plan's plots in its order. No building is ever placed off-plan.
- Building type is picked automatically from the kind of work (files touched): tests → test tower, UI → shop, scripts → workshop, docs → library, other → house.
- Each type goes to its district in the plan (test towers together, shops on the shop street, and so on).
- The 5 plans go through the mock gate: owner sees all 5 before real code.
- Each building remembers the files it was built for. An agent leaving never removes its building. The files behind a building deleted → the building is demolished (a short demolition). Code comes back or is rewritten → a new building goes up.
- A rest place per territory: appears when the first agent there finishes (day 0 stays bare). Benches and parasols first, a cafe and park with the eras. Free agents hang out there.
- Planned, not built: when a district is full, buildings level up (taller, bigger) instead of nothing happening.

## Balance
- The city shows how healthy the repo is, not only how big. 5 kinds of code, each one city system:

| kind | in the repo | in the city | measured by |
|---|---|---|---|
| build | feature code | houses, shops, offices | code lines |
| rules | automated tests, QA docs | traffic lights, signposts, police station | share of source files with a matching test file |
| beauty | UI components, UI rules | parks, flowers, fountains, painted walls | component count, and how often they are reused |
| knowledge | requirement, feature, module docs | library, district name signs | share of modules with a doc |
| infra | scripts, CI, config, DB schema, migrations | power plant, water tower, bridges, paved roads | file count |

- Lines are used for build only. The other kinds use the measure above; lines there mislead.
- Reward, never punish. Day 0 is clean empty land. A thing appears when its kind exists. A missing kind is absent, not broken: no cones, no cracks, no jaywalking.
- Each kind is scored healthy / low / missing against build. A 城市平衡 card in the right column, one bar per kind.
- Click a kind → the list of files it counted. Wrong guess → fix one rule in the city config (`~/.claude/agent-city/rules/<repo>.conf`), never in the repo.
- Classification runs in the server, by path and file name rules, same result for every viewer and agent. Binaries, vendor, generated files never count.
- A kind the repo's own rules forbid (e.g. auto-pipeline allows only 3 doc kinds) → "not applicable", never "missing". Per repo setting.
- Eras: village (wood houses, dirt roads) → town (brick, stone roads, lamps) → city (towers, parks, fountains).
- Village → town: size, and no kind missing. Town → city: size, and rules and beauty both healthy. Size alone never moves an era.
- A sign in front of the town hall shows what the next era still needs (e.g. 还差：规则).
- An era change is a show, not a blink: many small builders come out, walk to every building, road and lamp, scaffolding and hammering everywhere for a while, then in one moment the whole territory flips to the new era's look (wood → brick → tower). Positions and owners stay. Builders leave.
- The show runs once per era change, about 60 s, and is recorded in world.json so a reopen does not replay it.
- The city server never runs the repo's tests. Test pass counts: maybe later, only if cheap.

## Quality
- Code quality shapes how orderly the city is. Measured from the files only, no tools run: very large files, long functions and deep nesting, duplicated blocks, hot spots (large files changed very often in git).
- Good quality: straight streets, buildings aligned to their district. Poor quality: buildings crooked, crammed together, some built in the wrong district (a tower in the houses). Messy, never broken.
- When a file's quality improves, builders move its building to the right plot, aligned.
- Land looks smooth, not tiled (owner, 2026-09-25, replaces the per-tile shade): no per-tile colour steps, no stair-step edges; coast, cliffs, river banks and district edges are smooth curves; paths and roads are smooth lanes that curve, not rows of tiles. The tile grid stays only as hidden logic for plots.
- 3D models: Kenney and KayKit only (both CC0, same chunky low-poly look), License.txt per pack. KayKit fills the gaps: Medieval Hexagon (barracks = village police, church = village library, windmill/watermill = village power, tavern = village rest place, building_destroyed = demolition, scaffolding and stage_A/B/C = construction), City Builder Bits (police car beside a building = town/city police station, bench, traffic lights, streetlight, fire hydrant), Space Base (solar panels = city power), Restaurant (tables and chairs = cafe).

## Persistence
- World state (territories, land size, buildings, per repo) lives in one file: `~/.claude/agent-city/world.json`.
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
