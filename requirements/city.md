# CITY

- Requirement doc for the Agent City. Read before changing `bin/agent-city*`, `bin/agent_city.py`, `skills/city/`.
- Owner decisions, 2026-09-24. A change to a rule here needs the owner's yes.

## What it is
- Local 3D page. Real agents shown as people in a city. Chat text (what was typed to a session and what it answered) is shown only on this computer, in that person's window, and never leaves the machine (see Talking; owner, 2026-09-27, replaces "never reads chat text").
- Not watch-only: agents' questions and permission requests are answered from it (see Interaction), and the owner talks to any running session from it (see Talking).
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
- The city fills the whole page (owner, 2026-09-27; replaces the right column of cards 详情 / 城市平衡 / 市民 / 动态). Nothing sits beside it.
- The rail (owner, 2026-09-29, city-ux2; approved mock mock/city-ux2-mock.html v2): a compact list at the left of the city, always there on a computer (about 212 px), and it is the team list: per repo (a small repo colour, the same colour as its repo tag), the governor first, then each task manager with its workers, then everyone else, other members' people last; people resting are folded under "休息 N" at the end of their repo. One row = state dot + name + short state; the order never jumps when a state changes. A repo's title folds / opens that repo (a folded repo still shows who waits on you). The rail folds to a thin tab at the left edge (count + a red dot for who waits on you) and opens again from it; the folds are remembered in this browser. Phone: the rail is a drawer out of that tab, folded again after a pick.
- Click a person — a rail row, a person in the city, or any tag or bubble over its head (name tag, state bubble, question bubble) → the camera flies to it, zooms in until its bubble reads, and follows it while it walks (the rotation keeps turning around it); and its message panel opens, docked at the right of the city: that one person only — short facts (state, repo · branch · doing, progress), its history, newest at the bottom (activity lines the page records since it opened: started, tools, stuck, waiting, done; its questions and answers; its conversation, see Talking), and the reply box for a session (a subagent: view only, find its lead; another member's person: view only). The governor's panel is its conversation. No team window in the middle and no second team list (replaces city-ux's two-column team window, owner 2026-09-29). No tool counters (Edit / Write / Bash / Read), no explainer text, no 派出 / 回答 counters. The panel folds to a thin tab at the right edge (name + new messages), remembered; a new pick opens it again. Phone: the panel is the bottom half, folding to a tab at the bottom.
- Following stops on: the same person clicked again, Esc, 停止 on the small "跟随" chip at the top of the map, a repo tag or All, the reset-view button, dragging or two-finger scrolling the map, a tap on empty ground (which also closes the panel), or the person leaving. Zoom, rotation and folding a panel never stop it. The followed person sits in the middle of the map you can see — between the rail and the panel — and the zoom buttons move left of the panel: the map always shows in the middle.
- A person is easy to hit: a click within about 28 px of a person picks it; a head tag or bubble takes a click up to 8 px outside its box (city-ux2).
- Click a building → the panel shows one meaningful name (the task it came from, else the module its files point at, else its type; never a file path or its builder) and its type and district, and a 看看它 / Show it button that flies the camera there, nothing else. A site as before (a "?" keeps its own panel over the city). × or a tap on empty ground closes it: only the city again (no keyboard shortcut, as before).
- Top counts stay, small, over the city: 干活, 找总督, 休息, 建成. The page log (动态) opens from a small button there, on demand; every line the rules below call "never silent" still goes into it.
- No frame around the city: no border line, no rounded box.
- Camera is a perspective camera, not a top-down god view. Default tilt about 30° above the horizon, close to the town hall.
- Drag up/down tilts (about 15° to 60°), drag left/right orbits (a drag starts past 8 px; a plain click never moves or tilts the view). Trackpad like a MacBook: two fingers together pan, pinch zooms, both proportional. Sideways moves the land by the same rule as up/down (owner, 2026-09-29: up/down was right, sideways went the other way): the system's scroll setting (natural or not) decides both together; the page has no invert option of its own. A plain mouse wheel pans too; zoom with pinch, ctrl + wheel or + / −. Never clips into ground or buildings.
- Repo tags (owner, 2026-09-28): a row above the city, always visible: 全部 / All first, then one tag per repo; the tag of the repo in view is highlighted. A tag flies the camera there (smooth, keeps the tilt); All shows every repo. The user's own zoom-out stops at about two territories across (a short hint says so and points to All); only All goes past it.
- Camera auto-rotates, one turn per 5 min, and never stops: clicks, drags, zoom and panels do not pause it (owner, 2026-09-25; replaces stop-on-touch). A drag adds to the angle while it keeps turning. Off under `prefers-reduced-motion`.

## Interaction
- An agent that asks (AskUserQuestion) or needs a permission walks to the governor. Governor = main manager session of that repo.
- Chain of command, same as the real pipeline: worker → its task manager (the lead) → the governor → the owner. A worker's question goes to its task manager first; only what the task manager cannot decide goes on to the governor; only what the governor cannot decide gets the owner's "?".
- Every territory has its own governor: the main manager session of that repo. Task managers are leads with their own site office; their workers live and walk around it.
- The governor really answers questions.
- Permission requests are never approved by the governor (Claude Code's safety check blocks it; owner decision 2026-09-25: keep it that way). Every permission request goes straight to the owner: red "?" at once, the owner reviews and decides.
- Governor cannot decide, or no answer within `city_governor_wait_sec` (default 60) → red "?" above the agent.
- Owner clicks the "?": sees the exact question or request (tool + command or path) and answers, approves or denies in the page.
- First answer wins, from any side (governor, page, terminal). The others see it closed.
- After an answer, approval or denial the panel shows the result for 10 s, then closes by itself (owner, 2026-09-25).
- Every answer and approval is logged: who (governor or owner), what, when. In the page log and in `~/.claude/agent-city/decisions.jsonl`. Never silent.
- Control requests: 127.0.0.1 only, a random token per server start on every request, Origin and Host checked. No other website can answer or approve.
- City off or server down → the agent falls back to its normal terminal prompt, no waiting.
- Out of scope: Claude Code's own cross-session message hold ("Deliver this message"). Never auto-clicked.
- Build order: prove first, with a real session, how an answer or approval reaches it (hook decision or Orca terminal keys). Then build.

## Talking
- Owner decision, 2026-09-27: "我就可以直接看到他的聊天记录对话框然后直接跟他说话". The owner reads a session's conversation and talks to it from its person's window, no terminal needed. The terminal keeps working in parallel; both show the same conversation.
- What the window shows: what was typed to the session (UserPromptSubmit `prompt`), the text each turn ended with (`last_assistant_message` on Stop and SubagentStop), and the owner's messages from the page. Questions and permission requests stay in their own "?" panel (see Interaction). Not tool output, not the transcript file: its format is internal to Claude Code and changes between versions (code.claude.com/docs/en/sessions), so the city never parses it. Only from the time the city is on.
- A message typed in the window goes to that session. Idle session → it wakes at once with the message: the same background Stop hook that wakes a governor with a question (`asyncRewake`), now for every session, reachable while idle up to the same 12 h. Busy session → the message waits and goes in when its turn ends; the window says 等它做完这一步. The window shows each message as sent, then delivered.
- Sessions only: the governor and task managers. A worker (a subagent inside a session) shows its conversation read only, and the window offers its lead's window to talk to instead.
- The conversation shows simple markdown (paragraphs, lists, code, bold, simple tables) and hides HTML comments (e.g. <!-- buddy: … -->); raw HTML is shown as text, never run. The log never pulls the owner down: it follows new lines only while the owner is at the bottom; scrolled up, it stays put and a small 有新消息 ↓ / New messages ↓ chip jumps down.
- Every delivered message is logged like an answer: who, what, when, in the page log and `~/.claude/agent-city/decisions.jsonl`. Control requests as in Interaction: 127.0.0.1, token, Origin and Host checked.
- Chat text stays on this computer, in `chat.jsonl` next to `events.jsonl`, readable by this user only (file mode 0600), one append per line: never sent through the relay (a joined city shows other members' people, never their conversation; their windows have no box), never written into `world.json`.
- Cost: the per-tool-call hook stays as today (bash builtins, one line). The text is picked up only when a prompt is submitted or a turn ends.
- From outside this computer (phone, elsewhere): never through the relay, which carries events only (see Joining). Claude Code's own Remote Control in the Claude app is the way.

## Worktrees
- Owner decision 2026-09-25. Mock first, owner sees it, then build.
- One worktree = one construction site inside its repo's territory. The pipeline gives each worktree one task manager: the site office is that task manager's office (see Interaction).
- The site has a fence and a sign on the site office with the branch name. Its workers build inside it.
- Status from `agent_worktree.txt`: working = lights on, work going on; final = workers gone, the task manager checks, scaffolding comes down; idle = quiet, lights off.
- Stalled (from `agent_monitor.txt`) = smoke and a warning sign on the site, and a 卡住的工地 count next to the top counts.
- Merged = the merge deputy lays a road or bridge from the site to the town hall, the fence goes, the new buildings join the town.
- Worktree removed = the site office packs up and goes.
- A human-direct session (second session opened by hand) = a small 亲自带 flag on its site.
- Which worktree an agent is in: the hook already walks up to the folder holding `.git`; when that `.git` is a file (a linked worktree) it sends that folder's physical path as a 16th key `wt`, else "". Still bash builtins only, no git run per event (main manager, 2026-09-25: replaces "the server works it out with git").
- Sessions with no worktree (plain or cloud runtime) work on the town itself, as today.
- Built without a separate mock (owner, 2026-09-25: "能做你直接做就可以了"). Demo mode `/#demo` shows the sites, one of them stalled, so the owner can look without a real worktree.
- v1 limits (main manager, 2026-09-25): the site is the office, a low construction fence around it (people may step over it), the branch sign, a site light, and scaffolding while working. Buildings its workers make still go up on the town's plots, as today. The 卡住的工地 count shows only when at least one site is stalled. Merged: a lane is laid from the site to the town hall over a few seconds, the fence goes, then the site office packs up (the worktree is gone after a merge). A site's office uses one of the plan's office spots; a lead working in that worktree stands at the site office instead of getting its own.

## Growth
- One territory per repo. All territories on one land, not islands on a sea.
- Territories are split by a natural gap: river, ravine, mountain pass or forest. A bridge or road joins neighbours, so people could cross.
- Tight spacing (owner, 2026-09-28, city-ux): territories sit 22 tiles apart (was 26); the town plans are unchanged, their roads stop at the town's content box, and the outer edge and coast stay organic.
- Where the land ends it may meet sea (the coast terrain); that is the only sea.
- Territory size grows with the repo's git-tracked code lines. Not counted: binaries, images, 3D models, vendor, lock files.
- New repo = tiny territory with a small town hall only.
- The city is never empty: when the server starts it shows the territory of the dir it was started from (its git repo; a plain folder counts too), plus every territory saved in world.json, at once, before any agent acts.
- Minimum size: every territory, even an empty repo with 0 code lines, has at least a small land, a town hall and one open plot in every district of its plan (house, shop, test tower, workshop, library), so any first edit can build.
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
- Every building means something and says so. Click a building → its card: name (the task it was built for, e.g. "设置页 API"), what it is (kind and district), the feature it stands for (its module or folder and the files it covers), built when and by whom, and its history of touch-ups (who changed its files and when, newest first).
- Each building remembers the files it was built for. An agent leaving never removes its building. The files behind a building deleted → the building is demolished (a short demolition). Code comes back or is rewritten → a new building goes up.
- Idle people are calm: no looping gestures (the governor does not keep waving); they mostly stand, and now and then take a slow walk around their territory to look at the city, then come back. The governor strolls near his hall and returns at once when a question or permission needs him.
- People never walk through models: buildings, halls, trees, rocks, lamps, fountains, cars and tables block their footprint; paths go around, and people re-route when something new is built.
- A rest place per territory: appears when the first agent there finishes (day 0 stays bare). Benches and parasols first, a cafe and park with the eras. Free agents hang out there.
- When a district is full (every open plot of it taken), the next build there levels up a building instead: the one with the lowest level, oldest first, gets taller and a little wider (levels 1 to 3). Only when every building of that district is at level 3 does the page log say there is no free plot (main manager, 2026-09-25; owner: "能做你直接做就可以了").

## Balance
- 5 kinds of code, each one city system. Reward only, never a to-do list (owner, 2026-09-27: the kinds are an unspoken standard, not a goal; code a person checked by hand without a test can be fine and safe):

| kind | in the repo | in the city | measured by |
|---|---|---|---|
| build | feature code | houses, shops, offices | code lines |
| rules | automated tests, QA docs | traffic lights, signposts, police station | share of source files with a matching test file |
| beauty | UI components, UI rules | parks, flowers, fountains, painted walls | component count, and how often they are reused |
| knowledge | requirement, feature, module docs | library, district name signs | share of modules with a doc |
| infra | scripts, CI, config, DB schema, migrations | power plant, water tower, bridges, paved roads | file count |

- Lines are used for build only. The other kinds use the measure above; lines there mislead.
- Reward, never punish. Day 0 is clean empty land. A thing appears when its kind exists. A missing kind is absent, not broken: no cones, no cracks, no jaywalking.
- Kinds are never listed, scored or asked for on the page (owner, 2026-09-27): no 城市平衡 card, no bars, no file lists. A kind still brings its own buildings when it exists.
- A file's kind guessed wrong → fix one rule in the city config (`~/.claude/agent-city/rules/<repo>.conf`), never in the repo.
- Classification runs in the server, by path and file name rules, same result for every viewer and agent. Binaries, vendor, generated files never count.
- Eras: village (wood houses, dirt roads) → town (brick, stone roads, lamps) → city (towers, parks, fountains).
- Eras move by size only (owner, 2026-09-27; replaces the balance gate): the city keeps growing whether or not the repo has tests, docs or UI rules. No sign asks for anything (no 还差 sign).
- An era change is a show, not a blink: many small builders come out, walk to every building, road and lamp, scaffolding and hammering everywhere for a while, then in one moment the whole territory flips to the new era's look (wood → brick → tower). Positions and owners stay. Builders leave.
- The show runs once per era change, about 60 s, and is recorded in world.json so a reopen does not replay it.
- The city server never runs the repo's tests. Test pass counts: maybe later, only if cheap.

## Quality
- Code quality shapes how orderly the city is. Measured from the files only, no tools run: very large files, long functions and deep nesting, duplicated blocks, hot spots (large files changed very often in git).
- Good quality: straight streets, buildings aligned to their district. Poor quality: buildings crooked, crammed together, some built in the wrong district (a tower in the houses). Messy, never broken.
- When a file's quality improves, builders move its building to the right plot, aligned.
- How it is measured (main manager, 2026-09-25), per file, by reading it: lines; the longest function (a def/function/func/fn line, or a line ending in `) {` / `) => {`, to its end by indent or brace); the deepest nesting (brace depth or indent level). Good / fair / poor by thresholds. A block of 8 or more identical lines found twice anywhere in the territory's building files, or a hot spot (10 or more commits in 90 days on a file of 300 or more lines), each makes the file one step worse. A building's quality = its worst file.
- Where the files come from: the hook adds the edited file's path relative to the repo (17th key `file`, Edit/Write/MultiEdit/NotebookEdit only, never outside the repo). It stays on this computer: joining never sends it.
- Poor: the building stands crooked and a little off its plot (crammed), and one in three poor buildings (picked from its first file's name, stable) is built in another district. Fair: slightly off. Good: straight. The card says 整齐 / 还行 / 有点乱, and 放错区了 for one in the wrong district.
- Rechecked with the territory's count (never on every event). A file counts as still there when it exists in the main checkout or in a live worktree of that repo; every file of a building gone = demolished.
- Land looks smooth, not tiled (owner, 2026-09-25, replaces the per-tile shade): no per-tile colour steps, no stair-step edges; coast, cliffs, river banks and district edges are smooth curves; paths and roads are smooth lanes that curve, not rows of tiles. The tile grid stays only as hidden logic for plots.
- 3D models: Kenney and KayKit only (both CC0, same chunky low-poly look), License.txt per pack. KayKit fills the gaps: Medieval Hexagon (barracks = village police, church = village library, windmill/watermill = village power, tavern = village rest place, building_destroyed = demolition, scaffolding and stage_A/B/C = construction), City Builder Bits (police car beside a building = town/city police station, bench, traffic lights, streetlight, fire hydrant), Space Base (solar panels = city power), Restaurant (tables and chairs = cafe).

## Persistence
- World state (territories, land size, buildings, per repo) lives in one file: `~/.claude/agent-city/world.json`.
- Not in `~/.cache` (cleaners wipe it). Never inside a repo (no git noise).
- Written atomically (tmp + mv). Has a version field `"v"`.
- Broken or unknown file → move it aside as `world.json.bad-<time>`, start fresh, say so in the page log. Never silent.
- Server loads it at start; the first snapshot carries it. Browser closed, server stopped, Mac restarted → same city.
- `events.jsonl` is the feed, not the record. It may be cleared.
- The city is per computer. Another machine has its own city. A joined city also shows the other members live (see Joining); each machine's `world.json` stays its own.

## Limits
- Server listens on 127.0.0.1 only, port `city_port`, stops itself after `city_idle_min` with no browser open and no idle session waiting to be talked to (city-chat, 2026-09-27: a session's watcher polling keeps it up, so a closed tab never makes an idle session unreachable).
- Start refuses when RAM or CPU is over the cap.
- Cloud sessions: no city page (no localhost for the human). A joined cloud session sends its events to its team (see Joining).

## Joining
- Owner decision, 2026-09-25. The local city stays the default and keeps being maintained. Joining is an optional extra; the local city never needs it.
- Not joined = the city above: this computer only, no account, nothing leaves the machine.
- Joined = the local city also shows the other members of the same team: the owner's other machines, other people's terminals, cloud sessions. Every member still runs their own local city. There is no shared city page on the internet.
- Path: hook → `events.jsonl` (unchanged) → local server → relay → every joined local server → its page. The page talks only to 127.0.0.1, as before; only the local server talks to the relay.
- Relay: a small Cloudflare Worker, one per team. Holds the last few minutes only, never a history.
- Sent: the same short lines, with the working folder cut down to repo and branch. Never full paths, chat text (see Talking) or files: the hook's `wt` (a full path) is sent only as the branch name, and its `file` key (city-quality) is never sent.
- Same repo from different people = the same territory. Repo identity = the `origin` remote (host/owner/repo). No remote = not shared, stays local.
- Other members' people: a name tag (person) and a small device tag (machine name or 云端). Several main managers in one repo = several governors at the one town hall, each with a name sign. An agent asks its own person's governor.
- Other members' people are view only. Answering questions and permission requests works for your own agents only.
- Other members' people and sites are shown live and never written into your `world.json`. Leave → they disappear; your own world is unchanged.
- Orders (main manager's default, 2026-09-25; the owner may change it): the relay carries events only, never orders. Orders to agents go through the Claude Code app: local sessions via `claude remote-control`, cloud sessions are there already. The city may link a person to its session in the app. Reason: an order channel on a public site would be a way into the members' computers.
- Relay host (owner decision, 2026-09-25): self-hosted. Each team's owner makes their own free Cloudflare account and sets up the relay there by hand (see Relay setup). The plugin's author runs no server; teams share nothing.
- Key: setting up the relay gives two values, the relay address and a team key (kept as a secret in Cloudflare). The team owner hands both to each member.
- Joining is per repo: the address and key go into `<repo>/.secrets/agent-city-relay`. The person does this in their own terminal (`bin/agent-city.sh join` asks for both, the key hidden) or by hand. Agents never write, print or ask for the key, and it never goes into the chat. `.secrets/` is git-ignored by agent-init; join refuses when it is not. Only repos with that file send and see the team; every other repo stays local. `bin/agent-city.sh leave` deletes the file. Wrong or missing key = the relay refuses.
- One key per team for now. Remove a member = change the key in Cloudflare, hand the new key to the others.
- Name tag = the person's git `user.name`.
- Cloud sessions: send only, no page. Need the address and key as one environment secret (`AGENT_CITY_RELAY`), the relay host allowed in the environment's network setting, and the city hook and sender shipped by the cloud pack. The cloud pack's project hooks cover a session opened on one repo. A session opened on several repos starts above them (their common parent, e.g. `/home/user`, not a repo) and loads no repo's hooks at all, no matter how many of them carry the pack — so the environment's Setup script instead runs `bin/agent-city.sh cloud-hooks`, which writes the same SessionStart send hook and city hooks into user-level settings (`~/.claude/settings.json`), plus a fixed copy of `bin/` under `$AGENT_CITY_HOME` for them to run from. Those user-level hooks stand down (send nothing) whenever the session's project folder (`$CLAUDE_PROJECT_DIR`, where it started) is a repo that already carries the project pack, so a line is never sent twice. Only lines whose cwd is inside a repo with a shared origin are ever sent — a `/home/user` cwd with no repo stays local — this is `agent_city_relay.py`'s existing `offer()` behaviour, unchanged by any of the above.
- Joined machine with no browser open: the server keeps sending while its agents are active; it stops after `city_idle_min` with no browser and no new events.
- Relay down or offline: the local city keeps working. Unsent lines are kept up to a small cap, oldest dropped first. The page shows 联城断开.
- Cost: joining adds nothing to the hook. The sender batches lines every few seconds and counts toward the server's RAM limit.
- Build order: after the worktree sites. Mock first.

## Relay setup
- Owner decision, 2026-09-25: the relay comes with setup steps a person can follow by hand.
- Written together with the relay code. They live in `skills/city/` next to the command (config, not a new doc); `/auto-pipeline:city setup` walks through the same steps, but never asks for the key.
- Reader: someone who has never used Cloudflare. Numbered steps, plain words, each section ends with what you should see. Cloudflare website only where possible; any command is given exactly, ready to paste.
- Covers: make the account; make the relay; set the team key; find the relay address; hand address and key to members; join a local repo; join a cloud environment (secret and network setting); check it works (a second machine or a cloud session shows up in the city); change the key; remove the relay.
- Acceptance: the owner follows the steps by hand, from a new Cloudflare account, and it works. Until then `city-join` is not done. A step he gets stuck on = a bug in the steps, fixed in the same task.
- Set up (owner, 2026-09-28; was on hold since 2026-09-27): the relay runs at https://agentcity.maverickleeweilin88.workers.dev (the address is not secret; the key never goes in a file, a chat or a commit). Checked from a cloud session: GET / answers {"ok":true,"relay":"agent-city","v":1}, a sync without the key gets 401 (no Cloudflare Access in front). The cloud environment has AGENT_CITY_RELAY. Acceptance still open: the owner's Mac joins (agent-city.sh join) and a cloud session shows up in his city. A cloud session opened on several repos starts in /home/user, above the repos, and runs none of their hooks (seen 2026-09-28: no city dir, no sender) — the fix is the environment's Setup script running `bin/agent-city.sh cloud-hooks` (user-level settings, see "Joining"); opening the acceptance session on one repo that carries the cloud pack (event, home, website or work) is a workaround until he pastes that line in.

## Anywhere
- Owner decision, 2026-09-28: "even if I am not in the repo I can use agent-city start to see the city; makes more sense for an all-env monitor agent city".
- In the owner's own plain terminal (not a Claude session), `agent-city start|status|stop|demo|join|leave|...` works from any folder, even outside a repo. Only Claude sessions have the plugin's bin/ on PATH, so a small command does it.
- The command is `~/.local/bin/agent-city`, a copy of `bin/agent-city-shim`. Every run it finds the highest installed plugin version under `~/.claude/plugins/cache/auto-pipeline/auto-pipeline/` (plain versions only, sorted by version, never by name, never a hard-coded version) and runs its `bin/agent-city.sh` with the same args. Nothing installed → it says so, exit 1.
- `AGENT_CITY_PLUGIN_ROOT=<plugin folder>` runs that plugin instead, to try a checkout before it is released.
- Installed by `agent-city.sh install-shim`: the init skill asks the human first and runs it only after a yes. Manual one-line install from any folder: `bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" install-shim`. `agent-city.sh remove-shim` takes it away.
- Never overwrites or removes a `~/.local/bin/agent-city` that is not ours: ours carries the marker line `# auto-pipeline agent-city shim`; a file without it, a symlink or a folder is left alone and the command says "not ours". `~/.local/bin` not on PATH → it prints how to add it; it never edits a shell profile.
- Outside a repo = the folder is not inside a git work tree. There the city uses the plugin defaults (`bin/agent.conf.default`); an `agent.conf` lying in that folder is never read.
- Port anywhere: `AGENT_CITY_PORT` (1024-65535) wins over `city_port`, inside or outside a repo, so a city outside a repo can still get another port (main manager, 2026-09-28, after a laptop test found 4777 held by the owner's real city). A bad value is refused, nothing starts.
- Start says why, never a bare "failed to start": the port held by another program → it names the port and `AGENT_CITY_PORT`; a city already running in this city dir → its URL plus "already running", stop it first to start it again from here (its settings, e.g. no joined list when started inside a repo, stay until then).
- Language outside a repo: zh (the city's own default), `AGENT_CITY_LANG=en|zh` overrides it (main manager's default, 2026-09-28; the owner may change it). Inside a repo the repo's `language`, as before.
- Local events: the city shows every repo on this computer, wherever it was started (one city dir per machine, as before).
- Team relay outside a repo (owner, 2026-09-28: yes): a city started outside a repo syncs every team relay this machine has joined, with no local agent needed. `join` adds the repo to a user-level list, `$AGENT_CITY_HOME/joined-repos.txt` (default `~/.claude/agent-city/`), after the relay said ok; `leave` removes it. The list holds repo paths only, one per line, never keys; keys stay in each `<repo>/.secrets/agent-city-relay`. The owner may edit it by hand ("#" comments kept). A repo whose folder or join file is gone drops out quietly.
- Inside a repo, team behaviour stays as before.
- `status` from any folder is true for that folder: the CITY line, then outside a repo one `TEAM: joined <host> (<repo>)` per joined repo of the list, or `TEAM: not joined`; inside a repo the one TEAM line of that repo.
- `join` and `leave` outside a repo refuse and say to run them inside the repo.

## Open, not decided
- A key per person, so one member can be removed without changing everyone's key (proposal, later).
- People from git history, no joining needed (proposal): buildings carry the authors of their files; recent activity shows who works where, people without agents included.
