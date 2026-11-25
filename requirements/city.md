# CITY

- Requirement doc for the Agent City. Read before changing `bin/agent-city*`, `bin/agent_city.py`, `skills/city/`.
- Owner decisions, 2026-09-24. A change to a rule here needs the owner's yes.

## What it is
- Local 3D page. Real agents shown as people in a city. Chat text (what was typed to a session and what it answered) is shown only on this computer, in that person's window, and never leaves the machine (see Talking; owner, 2026-09-27, replaces "never reads chat text").
- Not watch-only: agents' questions and permission requests are answered from it (see Interaction), and the owner talks to any running session from it (see Talking).
- Live mode `/` = real hook events only. Demo mode `/#demo` = fake data, same look, demo-only controls.
- Page text Chinese for now.

## Office

- Owner, 2026-11-24 (city-office; prototype https://claude.ai/artifact/BhrUSCTgwVkVpVYiYnibmY, kept as `mock/city-office-mock.html`; approved 2026-11-25: "ok already, can approve"; his words: "instead of building the whole city, a position in their office is better ... different repo is different department"). The city becomes ONE office building, "Agent 办公楼". It replaces the island: in Look the island, camera, repo tags and tag strip; Arrange; Worktrees; Growth; Balance; Quality. The build removed those sections (2026-11-25); the rules that still hold moved to People.
- Kept as they are: Data path, Interaction, Status, Face to face (on one floor), Talking, Add agent, Persistence, Limits, Anywhere. The governor is called 区经理 (area manager) on the page; the rule of who it is does not change.

### Building
- One floor per repo the owner picks. Every floor is the same square, 14 x 14 tiles ("the office is too big" at 20 x 20).
- Floor picker (选楼层, a button in the header): every repo this machine knows (the same list as Add agent). Tick = in the building, ↑ / ↓ moves a floor, at least one floor stays. A newly ticked repo goes on top. 1F is the bottom floor; G is the lobby. Saved per machine in world.json (replaces Arrange's slots and hidden flags).
- A repo not ticked is not shown anywhere: no floor, no people, no rail group, no counts, no waits (owner: "dont care, because this thing is the user choose").

### Who is shown
- Sessions only (owner: "only spawn those that is create and not CLI"): main manager = 区经理 (one per floor, in its glass room), task manager = 经理 (a desk in the open office), Helper and a plain session with no role = 助理, the area manager's assistant (desks outside its door). The interior designer = 设计师 (see Renovation).
- Subagents (workers, deputies, reviewers) are never drawn. Whoever runs them shows "worker ×n" or "deputy ×n" on its label and its rail row.
- The owner is the director of the building: not drawn. The 等你 button and the red bubbles are his inbox.
- Outfits by role, drawn in code (boxes, no new model files): 区经理 dark suit and red tie, 经理 light shirt, tie and lanyard, 助理 cardigan and clipboard, 设计师 dark top, beret and tablet.

### Views
- Outside (G): every page open starts here (owner: every time). The building from the street: a lobby with a door, one band per floor in that floor's accent colour, windows lit while someone on it works, a tag per floor (nF, repo, design name, people, the red count of who waits), the roof sign. A click on the door: the camera goes in through it (about 1 s), then the floor last looked at (first time: the top floor). A click on a floor's band or tag: that floor.
- Inside: one floor at a time. The lift panel at the right lists the floors, top first, then G. A click switches at once, no transition (owner: "no need transition animation, it will cause the thing become slower"). The floor sign at the top of the map: nF, repo, design name, people, and the 装修 button.
- Fixed zones on every floor: the lift (north middle), the area manager's glass room (north-east), the assistant desks outside its door, the open office of manager desks (one more desk than managers, at most 9), the pantry (north-west; idle people go there), the meeting corner (south-east). The outer wall on the camera's side drops to a low sill, so the floor is always seen inside.
- Rail, person panel, talking, question cards and Add agent work as before. The rail groups are floors (nF + repo, top first); the tree is 区经理 > 设计师, 助理, 经理.
- Selecting someone on another floor: the view goes to that floor first. From outside: in through the door to that floor.
- Selecting someone zooms in half as far as the island did (owner, 2026-11-25: "the zoom in for the avatar might no need so many ... reduce about 50%"): the camera goes to distance (floor view distance + 9) / 2, about 15 on a computer (the island went to 9), never further out than it already is. Following works as in Look.

### Between floors
- Owner: "if manager v4 want to find manager v3 ... he pressing the lift and wait then sit the lift to that floor and talk with the manager". A face-to-face talk (Face to face) with someone on another floor: the sender walks to the lift, presses the button, waits for the door, rides, walks out on the other floor, talks, and rides back the same way.
- The view goes with them only while that person is selected (followed). Otherwise the floor in view just shows them leave or arrive.

### Floor design
- Owner: "the office design according to the repo"; "the rules of setting is must be very clear, so that player can use AI to adjust it also"; "able to let them design their own office too, as long as wont break the base code". A design changes the look only, never the layout or who is shown.

| field | rule |
|---|---|
| `v` | 1 (format version) |
| `name` | 1-20 characters, on the floor sign and the outside tag |
| `why` | 0-60 characters, why it fits the repo; on hover |
| `colors.accent` | #RRGGBB; outside band, window frames, decor accents |
| `colors.carpet` (open office), `colors.manager_floor` (the area manager's glass room), `colors.pantry_floor` | #RRGGBB, HSL lightness 55-95% (people and labels stay readable) |
| `colors.desk`, `colors.desk_leg`, `colors.chair`, `colors.meeting_rug`, `colors.manager_rug` | #RRGGBB |
| `decor` | exactly 3 entries, one per slot (1 south-west corner, 2 south middle, 3 east wall): a catalogue id or `none` |

- Catalogue (15 pieces, each fits 1.6 x 0.9 tiles, drawn in code): robot, conveyor, gears, chart, plants, safe, cabinets, printer, bookshelf, clock, cashier, goods, menu, scanner, lightbox.
- Never settable: the floor size; the places of the lift, the area manager's room, the assistant desks, the manager desks, the pantry and the meeting corner; the number of desks; people, labels, states.
- Where: `~/.claude/agent-city/floors/<repo id>.json`, per machine, next to world.json, never in a repo, written atomically (tmp + mv). The last 5 versions are kept (`<repo id>.history.jsonl`) for undo (撤销上一步).
- `agent-city floor rules` prints these rules and the catalogue as plain text, so any AI or person can read them; `agent-city floor show <repo>` prints the current file.
- Checking: every write, whoever made it, is checked against the table. Unknown key, bad value, wrong count: the whole file is refused, the floor keeps its last good design, and the page log names each bad field and why (e.g. "茶水间地板的亮度是 20%，要在 55%–95% 之间"). Never silent. The design is data only: the page never runs code or loads files from it.
- A wish that is not settable (move the lift, a bigger floor) is not an error: the designer changes what it may and says in one line what it left alone.
- No design yet: the base look (plain carpet, no decor), floor sign "还没装修".

### Renovation
- Owner: "when adding a new repo which means add in a new company then we need to have renovation ... ask whether you want to renovate your office, or hire interior designer ... the interior designer is actually the agent in the user computer ... the role and also the knowledge is get from our plugin".
- A repo ticked into the building for the first time asks once: 请室内设计师 (recommended) / 自己装修 / 先不装修. The same choice is behind 装修 on the floor sign and 重新装修 in the floor picker.
- Interior designer: one agent session on this computer, opened by the city the way Add agent opens one (same guard, same cap check), in that repo's folder. Its role and design knowledge come from the plugin: `agents/interior-designer.md` plus these rules. Model from agent.conf (new key `interior_designer`, default Sonnet: it executes, it decides nothing for other agents). It reads only the repo's README or CLAUDE.md (first 60 lines) and the top-level folder names.
- On the page it arrives by the lift on that floor as 设计师, its panel opens, and it asks what the owner wants (等你). The owner answers in the panel (example chips: 温馨一点，多点植物 / 冷色，简单干净 / 加个收银台 / 按你的想法来). It answers with a plan, renovates (cones and tape on the 3 slots, it walks between them; floor sign 装修中…), writes the file, then waits in the meeting corner. Another wish: it renovates again. "好了，你可以走了": it rides the lift away and its session ends.
- It is shown, though opened by the city: a person the owner hires, not a subagent. It is never a Helper and never takes the area manager's seat.
- 自己装修 (DIY, this round, owner chose "A first"): a form in the 装修 box: name, the 9 colours, one catalogue piece (or none) per slot; checked before saving, same rules.
- The designer fails or stops answering (60 s per step): the floor keeps its last good design, one log line says why, 重新装修 starts again.
- Next round (owner prefers it: "do A first, then when free do B"): free placement of furniture and decor anywhere on the floor grid, checked so every seat stays reachable from the lift and nothing overlaps.

## Data path
- `hooks/hooks.json` → `bin/agent-city-hook.sh` → `<city dir>/events.jsonl` → `bin/agent_city.py` → SSE `/events` → page.
- Hook when off: one `test -f`, nothing else. On: one JSON line per event. Bash builtins only.
- Governor = the repo's real main manager only (owner, 2026-09-30, city-roles; replaces "first session without `AGENT_ROLE`"): the session holding `<git common dir>/agent_main.lock` (pid alive; its session id matches, or with an old lock that has no session id, the hook's `pid`, else the pid the server remembers for that session). Everyone else is a citizen, a session without `AGENT_ROLE` too. Subagent = citizen.
- Who sent whom (owner, 2026-10-05, city-rail-tree): every person the server sends (spawn event, snapshot, the roster brought back after a restart) carries `up`, the page id of its parent: a subagent → the session that started it ("gov:<terr>" when that is the governor, "s:<sid>" for a live session citizen, else ""); a session whose hook role is task-manager → "gov:<terr>" of its own repo (also while that repo has no governor: the page then puts it under the repo); any other session → "". Kept as long as the person lives; the spawn's `from` stays as it was.  No new hook field.
- No live lock holder → no governor in that territory (the page says 区经理不在; questions go straight to the owner).
- The lock changes hands (take-over, close case, a new main manager) → the new holder is governor on its next line, even if it was a citizen; the old one leaves the seat. The server also checks the seats about every 2 s: a dead holder ends like its SessionEnd, a released lock empties the seat.
- Only the governor gets governor questions and the governor's messages. Any other session's watcher hears its own messages, like a citizen.
- Old hooks (lines carry no `pid`): still the governor when the lock names its session id (owner, 2026-10-01, city-rediscover).
- The server remembers the pid a governor was seated with. A lock that later has no session id again (an old `agent-start.sh` rewrites it on compaction) and still names that pid keeps the seat; another pid takes it away.
- An old lock line (no session id, or no terminal) is filled in by its holder's own `agent-start.sh`: any start, or `--take-over` typed in that session (same pid, same date). The holder never changes. Nothing known to add → "Nothing changed".
- Server restart: live sessions come back at once, with no new event. The server keeps `<city dir>/roster.json`: every live session it knows a pid for (governor: its line's `pid`, else the lock's pid). At start, pid alive → shown again (the lock holder as governor, idle; the others as citizens with their name, role and office); pid dead → dropped.
- Not brought back: a citizen with no known pid (old hooks) and subagents. They show up on their next event, as before.
- The roster is written (tmp + mv) only when a session appears, ends, takes or loses the seat, or gets its name. Never per tool line. Broken or missing file → empty roster, the city starts.
- A line with no repo stays in the territory its session was last seen in. Only an unknown session with no repo goes to the start territory (old hooks).
- A session shows up only if it started with the city hook installed (plugin 0.6.0+).

## Look
- The office replaced the island (owner, 2026-11-24, see Office). In the rail, panel and header rules below a repo's group is its floor, and "the city" is the building.
- No credits, intro text, legend, or drag hint on the page. People and furniture are boxes drawn in code: no model files (only `bin/agent-city-assets/vendor/three.min.js`).
- No speed buttons, no pause. The view runs at real time.
- People walk at 1/3 of the 0.5.0 speed. Walk animation slowed to match.
- The building fills the whole page (owner, 2026-09-27; replaces the right column of cards 详情 / 城市平衡 / 市民 / 动态). Nothing sits beside it.
- The rail (owner, 2026-09-29, city-ux2; approved mock mock/city-ux2-mock.html v2): a compact list at the left of the city, always there on a computer (about 300 px; city-rail-tree, owner 2026-10-05, was 212), and it is the team list: per repo (a small repo colour, the same colour as its repo tag), a tree of who belongs to whom (see the rail tree lines below; replaces "the governor first, then each task manager with its workers, then everyone else"), other members' people last; people resting are folded under "休息 N" at the end of their repo. One row = state dot + name + short state; the order never jumps when a state changes. A repo's title folds / opens that repo (a folded repo still shows who waits on you). The rail folds to a thin tab at the left edge (count + a red dot for who waits on you) and opens again from it; the folds are remembered in this browser. Phone: the rail is a drawer out of that tab, folded again after a pick.
- The rail is a tree (owner, 2026-10-05, city-rail-tree; approved mock mock/city-rail-tree-mock.html 2b63d74; his words: "they should have indent according to the repo and relationship, so that we can know who belongs to which one"). Floor > its area manager (区经理) > the sessions of that floor (设计师, 助理, 经理; Office, Who is shown). Subagents are not rows: their parent's row says worker ×n / deputy ×n. Each level is indented about 14 px and a thin guide line runs down from the parent to each of its children (├ … └), so a child clearly belongs to its parent.
- Who is whose parent: the person's `up` from the server (see Data path), else its `lead` (an older server). The parent must be in the same repo group and not resting; else the person sits right under the repo, never lost. A worker whose parent is not in the list shows a small dashed tag 上级不明 after its name. Children keep the order they came in; this machine's people before other members' people. The order never jumps when a state changes.
- Fold a parent: a small arrow in front of every row that has children (▾ open, ▸ folded). A tap on the arrow hides that row's children (all levels under it); the row then shows +n (how many are hidden) and, when somebody hidden waits on the owner, the red count of them, so a question is never hidden. A tap on the name still opens the person. Counts do not change: the repo head counts everyone, 在线 n and the red dot as before. Every row starts open; what the owner folds is remembered in this browser.
- Long names wrap to two lines (then cut with …), on the computer and the phone; no hover tip. Resting people stay folded under 休息 N at the end of their repo, flat, as before.
- Phone: the rail stays a drawer out of the thin tab at the left edge; the drawer is min(300 px, 84%) wide (was min(250 px, 78%)), the same tree inside.
- A name never says its kind twice (owner, 2026-10-01, city-talk): "fast-lane-deputy · msg-sides Deputy" reads "msg-sides Deputy". The kind is dropped when the name already says it: the kind's last word is in the name, or the name ends with a word of the kind ("merge-deputy · city-status Merge" reads "city-status Merge"). Same text in the rail, the head tag and the panel title.
- Click a person — a rail row, a person in the city, or any tag or bubble over its head (name tag, state bubble, question bubble) → the camera flies to it, zooms in until its bubble reads, and follows it while it walks (the rotation keeps turning around it); and its message panel opens, docked at the right of the city: that one person only — short facts (state, repo · branch · doing, progress), its history, newest at the bottom (activity lines: started, tools, stuck, waiting, done; its questions and answers; its conversation, see Talking; kept by the server per person, so a reload or a second tab shows the same history, see Persistence; owner, 2026-10-02, city-data, replaces "the page records since it opened"), and the reply box for a session (a subagent: view only, find its lead; another member's person: view only). The governor's panel is its conversation. The state chip in a panel's head follows its person for as long as the panel stays open, the governor's too: it always reads what that person's rail row reads (owner, 2026-10-02, cloud-polish: the rail said 总督 在忙 while the open panel still said 空闲). No team window in the middle and no second team list (replaces city-ux's two-column team window, owner 2026-09-29). No tool counters (Edit / Write / Bash / Read), no explainer text, no 派出 / 回答 counters. The panel folds to a thin tab at the right edge (name + new messages), remembered; a new pick opens it again. Phone: the panel is the bottom half, folding to a tab at the bottom.
- Following stops on: the same person clicked again, Esc, 停止 on the small "跟随" chip at the top of the map, a lift button, going outside, the reset-view button, dragging or two-finger scrolling the map, a tap on empty ground (which also closes the panel), or the person leaving. Zoom, rotation and folding a panel never stop it. The followed person sits in the middle of the map you can see — between the rail and the panel — and the zoom buttons move left of the panel: the map always shows in the middle.
- A person is easy to hit: a click within about 28 px of a person picks it; a head tag or bubble takes a click up to 8 px outside its box (city-ux2).
- Top counts stay, small, over the building: 干活, 找区经理, 休息, sessions and area managers of the floors only (what the building shows; subagents are in their parent's worker ×n). The page log (动态) opens from a small button there, on demand; every line the rules below call "never silent" still goes into it. An area manager is a session: a busy one counts in 干活, and the rail's 在线 n counts every area manager that is there (a waiting one also in the "waits on you" dot).
- The header is ONE row (owner, 2026-10-02, cloud-polish; approved mock mock/cloud-polish-mock.html: "I do not want the header too many, then the main screen visual area will be small"): the title, the counts, 动态. Nothing else sits above the city; the height the old rows took goes to the map. On a computer the page fits the window: the header and the map fill it exactly (the map takes what is left under the header), nothing runs under the screen, and an open panel's reply box is always on screen (2026-10-02: a fixed height left 69 px under the screen at 1440 x 900). Phone width: the title on one row, the counts on ONE line under it that scrolls sideways. On a narrow phone (520 px or less) the title is a little smaller, so the title row still holds 动态.
- No frame around the city: no border line, no rounded box.
- Camera: a perspective camera, not a top-down god view. Inside: one floor seen from above at an angle (the prototype's view), the open wall side towards the camera. Outside: the street view of the building (Office, Views). No auto-rotate (the approved prototype has none).
- Drag up/down tilts (about 15° to 60°), drag left/right orbits (a drag starts past 8 px; a plain click never moves or tilts the view). Trackpad like a MacBook: two fingers together pan, pinch zooms, both proportional. Sideways moves the land by the same rule as up/down (owner, 2026-09-29: up/down was right, sideways went the other way): the system's scroll setting (natural or not) decides both together; the page has no invert option of its own. A plain mouse wheel pans too; zoom with pinch, ctrl + wheel or + / −. Never clips into the floor or the walls.

## Interaction
- An agent that asks (AskUserQuestion) or needs a permission walks to the governor. Governor = main manager session of that repo.
- Chain of command, same as the real pipeline: worker → its task manager (the lead) → the governor → the owner. A worker's question goes to its task manager first; only what the task manager cannot decide goes on to the governor; only what the governor cannot decide gets the owner's "?".
- Every territory has its own governor: the main manager session of that repo. Task managers are leads at their desks; their workers are not drawn (see Office, Who is shown).
- The governor really answers questions.
- Permission requests are never approved by the governor (Claude Code's safety check blocks it; owner decision 2026-09-25: keep it that way). Every permission request goes straight to the owner: red "?" at once, the owner reviews and decides.
- Governor cannot decide, or no answer within `city_governor_wait_sec` (default 60) → red "?" above the agent.
- Owner, 2026-10-02 (city-ask-panel; approved mock mock/city-ask-panel-mock.html; replaces "the owner clicks the ?" as the only way in): a person who waits on the owner shows its open question or permission request inside its own message panel, as a card between the panel's head and the history: the exact question with its options, or the request (tool + command or path, what it said, the folder), and the answer, approve and deny controls. The owner found the panel saying only 等你, with nothing to answer.
- Every way to that person opens that panel with the card: the person, its name tag, its 等你回话 bubble, its rail row, the red "?" over its head, and the 等你 button at the top (the oldest one waiting). No second click.
- The card shows only while the ask is with the owner (the red "?"). While the governor still decides there is nothing to answer.
- The card stays in sight and its controls too: the deny-reason box, 批准 / 拒绝 and 发送回答 are always visible at the bottom of the card; only the details above them (the command, what it said, the folder, the options) scroll when they are long. The card takes the free height of the panel first; the history keeps a small strip under it. Found in the first browser check, 2026-10-02: the buttons were below the card's visible bottom.
- The card is never squeezed below its head, 48 px of details, its controls and its foot line (measured when the card is drawn): when the panel is too small for that, the panel body scrolls instead. Phone: while a card is open the bottom sheet grows, up to the whole map, and the history may shrink to its strip. Found in the second browser check, 2026-10-02 (390x844: the card was one line, 批准 was off the screen).
- The folder is shown short: the repo name plus the path inside it, else ~/… for a path in the home folder, else its last two parts after "…/"; the full path on hover.
- The asking person is not on the page (nobody to pick) → the "?" and the 等你 button open the small "?" panel over the city, as before.
- First answer wins, from any side (governor, page, terminal). The others see it closed.
- After an answer, approval or denial the card (or the small "?" panel) shows the result for 10 s, then goes away by itself (owner, 2026-09-25); the person's panel stays open and its history keeps the question and the answer.
- Every answer and approval is logged: who (governor or owner), what, when. In the page log and in `~/.claude/agent-city/decisions.jsonl`. Never silent.
- Control requests: 127.0.0.1 only, a random token per server start on every request, Origin and Host checked. No other website can answer or approve.
- City off or server down → the agent falls back to its normal terminal prompt, no waiting.
- Out of scope: Claude Code's own cross-session message hold ("Deliver this message"). Never auto-clicked.
- Build order: prove first, with a real session, how an answer or approval reaches it (hook decision or Orca terminal keys). Then build.

## Status
- Owner rule, 2026-10-01 (city-status). 等你 (rail, panel, the 等你回话 head bubble) only when the agent really needs the owner: a permission prompt or a question prompt (AskUserQuestion) is open, or its last reply asks the owner.
- A reply asks the owner when: a line begins with 要你决定 or "What to decide" (a section head), or a line begins with `QUESTION:`, or its last sentence ends with ? or ？.
- An empty decision section is a report, not a question (owner, 2026-10-01): the head followed only by nothing, none, 无, 没有, 暂无, - or n/a, on the same line or the next line, does not make 等你.
- A report-only turn while background work still runs → 后台在跑 ("Working in background"): its own colour (violet), no bubble.
- Otherwise → 空闲. A Notification `idle_prompt` changes nothing (before: every stopped session turned 等你 after a minute).
- Same rule for the governor and every session: task manager, helper, plain session. Subagents keep their states.
- Source: the Stop hook input. `last_assistant_message` is the reply. `background_tasks` (Claude Code 2.1.145+) lists the work in flight: shells, subagents, workflows, monitors, teammates, cloud sessions. Housekeeping entries (dream, auto-mode scan, memory import) do not count. `session_crons` (a wake-up later) does not count. Async hooks are not listed there, so they do not count.
- `agent_city.py say` (a Stop hook) adds one line to `events.jsonl`: `{"ev":"StopNote","sid","need","bg"}`. Flags only, never the reply text or a command.
- StopNote decides: need → 等你; else bg → 后台在跑; else 空闲. A Stop with no note (old hooks, cloud sessions) → 空闲. Next prompt or tool → busy again.
- Background work ends → Claude Code wakes the session; that turn ends with nothing in flight → 空闲.
- Older Claude Code (no `background_tasks`) → never 后台在跑, 空闲 instead.

## Face to face
- Owner, 2026-10-01 (city-talk; approved mock mock/city-talk-mock.html): people in the city talk like people. The sender walks over and talks; there is no turn-in-place and no flying letter.
- A new agent appears next to the one who sent it, 0.45 to 1.2 away, never on it: a subagent next to its session (the 区经理 for his own), a task manager session next to the 区经理 of its repo. They face each other for about 2.6 s (hand-over, 📋), then the new one walks to its own spot. Several at once: each on its own spot, one hand-over for all.
- Nobody sent it, or the sender is gone: it appears beside the lift as before, never on the 区经理 and never on another new one. People placed when the page opens or reconnects get no hand-over.
- Nobody stacks: standing people are never closer than 0.45 (appearing, working, waiting, talking, leaving at the hall). A walker walks around people and other walkers, never closer than 0.3, when there is room to pass.
- A message between agents (SendMessage) is a face-to-face talk: the sender walks to the other one (there in about 4 s, faster when far), they face each other for about 2 s (💬, then 👌 from the other one), the sender walks back, both go on. Closer than 1.2: nobody walks, both turn.
- The 区经理 walks over with his messages too and goes back to his glass room; anyone who needs him calls him back at once and that talk is dropped.
- No walk, the bubble on the sender's own spot: the recipient is not recognised or is walking; the sender is not at work; or more than 3 talks already wait for that person. A recipient on another floor is not "no walk": the sender rides the lift (Office, Between floors).
- One talk per person at a time; the rest wait in line.
- A question passed up (relay) is asked face to face on arrival (❓, about 2 s) and answered face to face before the walk back (✅; the lead or the 区经理 speaks). A timeout or a leave: no answer talk.
- The 区经理's talk bubble sits just above his head like a citizen's, at every zoom (never up on the glass room's roof): it takes the spot at his head, his speech bubble and his "?" stand above it.
- The talk bubble holds one icon, never chat text. Reduced motion: no gesture, the bubble stays.
- A talk never changes a status word and never delays a real one: 等你, stuck, a relay and done end the talk at once; 后台在跑 and 空闲 show at once.
- Demo (`/#demo`) plays it too: a new demo person on the demo 区经理's floor is handed its task by him, and two demo people at work talk about every 9 s.
- Data: a spawn event says who sent the agent (`from`); a SendMessage that is not a question becomes one `talk` event. The hook adds the recipient's name (`to`, at most 80 characters) to that line: never the message. The name is matched to a session name, a subagent id, a session id, the socket address Claude Code answers to (`uds:…/<pid>.sock`: the session with that pid), or a repo name (its 区经理); else nobody.

## Talking
- Owner decision, 2026-09-27: "我就可以直接看到他的聊天记录对话框然后直接跟他说话". The owner reads a session's conversation and talks to it from its person's window, no terminal needed. The terminal keeps working in parallel; both show the same conversation.
- What the window shows: what was typed to the session (UserPromptSubmit `prompt`), the text each turn ended with (`last_assistant_message` on Stop and SubagentStop), and the owner's messages from the page. An open question or permission request shows as a card at the top of that person's window (see Interaction; owner, 2026-10-02, replaces "stay in their own ? panel"). Not tool output, not the transcript file: its format is internal to Claude Code and changes between versions (code.claude.com/docs/en/sessions), so the city never parses it. Only from the time the city is on.
- A message typed in the window goes to that session. Idle session → it wakes at once with the message: the same background Stop hook that wakes a governor with a question (`asyncRewake`), now for every session, reachable while idle up to the same 12 h. Busy session → the message waits and goes in when its turn ends; the window says 等它做完这一步. The window shows each message as queued (排队中), then delivered (已送达), in the 区经理's window and in a session's window alike. Nobody can take it (the session is idle and its watcher is not listening, or a governor page with no governor) → 没送到 with the reason 它没在听，收不到, at once or as soon as that is true; never a silent wait (owner, 2026-09-30, city-roles R6).
- Sessions only: the governor, task managers and every other session (a Helper too: its watcher listens for its own window, only the governor's listens for the governor's). A worker (a subagent inside a session) shows its conversation read only, and the window offers its lead's window to talk to instead.
- A subagent's window never shows the red load error (对话没加载出来 / Could not load the conversation): it has no chat of its own, only the read-only note and the way to its lead. A session's failed load still shows the line (owner, 2026-10-01, city-talk).
- The conversation shows simple markdown (paragraphs, lists, code, bold, simple tables) and hides HTML comments (e.g. <!-- buddy: … -->); raw HTML is shown as text, never run. The log never pulls the owner down: it follows new lines only while the owner is at the bottom; scrolled up, it stays put and a small 有新消息 ↓ / New messages ↓ chip jumps down.
- Every delivered message is logged like an answer: who, what, when, in the page log and `$AGENT_CITY_HOME/decisions.jsonl` (default `~/.claude/agent-city/decisions.jsonl`; tests never write the real one, R7). Control requests as in Interaction: 127.0.0.1, token, Origin and Host checked.
- Chat text stays on this computer, in `chat.jsonl` next to `events.jsonl`, readable by this user only (file mode 0600), one append per line: never sent anywhere, never written into `world.json`.
- Cost: the per-tool-call hook stays as today (bash builtins, one line). The text is picked up only when a prompt is submitted or a turn ends.

## Add agent

- Owner, 2026-10-01 (city-add-agent; approved mock mock/city-add-agent-mock.html): start a new agent session from the city page, no terminal needed.
- The rail lists every repo this city knows on this machine (its territories in world.json), also a repo with nobody online: its group shows one quiet line, 没人在线. A repo that is not in the building is not listed (see Office, Building).
- On every repo group's name row, at its right end next to the count: one small + (tooltip and screen-reader name: 加 agent / Add agent). Owner, 2026-10-02 (cloud-polish; approved mock mock/cloud-polish-mock.html; replaces the full-width 加 agent row at the bottom of every group: with seven repos, "too many things already"). Only for a repo whose folder is on this machine; a repo that is not here gets no +. A folded group keeps its + (it is on the name row). The demo has none.
- Words show only while there is something to say, as ONE row right under that repo's name row, on a folded group too, and go away after: opening (the + shows a spinner meanwhile), the over-the-limit confirm, an error with its reason (再试 / 知道了), the command to run by hand where there is no Orca, and 已打开 (the + is a tick until that line goes). While a row with buttons shows, the + itself takes no click.
- Click → the local server opens ONE new session in that repo: with Orca, a new terminal in the repo's folder running claude, with the model, effort and permission mode of that repo's own agent.conf (`main_manager`, `permission_mode`). The model goes in as a name the claude CLI takes: fable-5.1 → fable, opus-5.5 → opus (the family word; `claude --model fable-5.1` is refused and the session's first turn dies). One rule for every script: `bin/agent_conf.py cli-model`.
- The new session gets one fixed first message from the server ("You were opened from the Agent City page. Do your start steps now, then stop and wait: the owner will talk to you from the city page."): a session sends the city nothing before its first prompt, and the page can only talk to a session that has had a turn. So it appears within seconds and can be talked to from the page. Cost: that first turn.
- A city that runs with its own city dir (not ~/.cache/agent-city) passes `AGENT_CITY_DIR` to the session it opens, so that session reports to this city.
- The role is never asked. The repo has no live main manager (its agent_main.lock holder is absent or dead) → the new session is its main manager, named "<repo> Manager"; else it is a helper, "<repo> Helper". A second helper gets a free name (owner, 2026-10-02, cloud-polish: two helpers of one repo were both "<repo> Helper", and a message needed a [ref] to tell them apart): the first free one of "<repo> Helper", "<repo> Helper 2", "<repo> Helper 3", …; a name is taken while a live session of that repo carries it, or while a session this city opened under it is still live; an ended session frees its name. The main manager's name stays "<repo> Manager". The session's own agent-start.sh decides the role from the lock. This button never creates a task manager: main managers dispatch them.
- Feedback sits in the rail under that repo, never in a dialog: the button reads 正在打开 … until the new session's first event arrives (the person then appears in the city as usual); a failure is one line with the reason in plain words (Orca could not open the terminal, the repo's folder is gone, the terminal opened but no session came within 60 s). Never silent.
- Over the resource cap (RAM or CPU above that repo's `max_usage_percent`): nothing starts by itself and nothing is refused: the RAM / CPU line shows, and the owner confirms or cancels. It is his click.
- No Orca on this machine (agent-runtime.sh kind is not orca): no terminal can be opened; the page shows the one command to run by hand, with a copy button.
- Safety: POST only, behind the same guard as the chat endpoints (token, same origin), the local page only (127.0.0.1). The request names a territory id and nothing else; the server takes the folder from its own world.json and runs a fixed command: no path, name or other text of the request ever reaches a shell line. One open at a time per repo: a double click opens one session.

## People
- Owner decisions carried over from the island (2026-09-25 to 2026-09-30), in office words.
- Repo identity = git common dir. Agents in a worktree are on their main repo's floor.
- The building is never empty: when the server starts it shows the floor of the repo it was started from (a plain folder counts too), plus every floor saved in world.json, at once, before any agent acts.
- Old data is dropped: territories saved without a repo identity are removed from world.json on load; events without a repo go to their session's floor, else to the start floor.
- Working people sit at their desk and act out their work (the prototype: typing; waiting: a raised hand; background: hands still on the desk). Idle and resting people go to the pantry; now and then an idle one takes a short walk on its floor and comes back. The area manager sits in its glass room; idle, it stands by its window; it is back at once when a question or permission needs it.
- No tool names over heads (owner, 2026-09-30, city-work-anim): while a person acts, one short line over its head says what it is doing in plain words, zh/en: its task and the current step, e.g. 写结账测试 · 改 checkout.py (改/写 <file>, 看文件, 找代码, 查资料, 跑命令, 派出：<task>, 排计划, 发消息, 忙着); nothing in the pause. Only a file's name, never its folder. A command's text is not known (the hook sends only its length), so a command is 跑命令. The history says the same steps (last 3 of a run), never tool names or counts.
- People never walk through furniture: desks, walls, the lift shaft, the glass room and the decor block their cells; paths go around.

## Persistence
- World state (the repos this machine knows, the floors of the building in order, which floors were asked about renovation, session names) lives in one file: `~/.claude/agent-city/world.json`. Floor designs live next to it in `floors/` (Office, Floor design).
- Not in `~/.cache` (cleaners wipe it). Never inside a repo (no git noise).
- Written atomically (tmp + mv). Has a version field `"v"`.
- Broken or unknown file → move it aside as `world.json.bad-<time>`, start fresh, say so in the page log. Never silent.
- Server loads it at start; the first snapshot carries it. Browser closed, server stopped, Mac restarted → same city.
- The people are not in `world.json`: live sessions come back from `<city dir>/roster.json` (see Data path).
- `events.jsonl` is the feed, not the record. It may be cleared.
- History (owner, 2026-10-02, city-data): the history in a person's panel (started, tools, stuck, waiting, done, its questions and answers) is kept by the server per person, so a reload, a second tab and a server restart show the same history; its conversation was kept already (`chat.jsonl`, see Talking). The server writes the lines and every open page shows the same ones. `<city dir>/history.jsonl`, next to `events.jsonl`, readable by this user only (file mode 0600), one append per line. Bounded: the last 200 lines per person; a person gone more than 24 h is dropped. The local page only; the demo has none. No new look.
- The city is per computer. Another machine has its own city. Each machine's `world.json` stays its own.

## Limits
- Server listens on 127.0.0.1 only, port `city_port`, stops itself after `city_idle_min` with no browser open and no idle session waiting to be talked to (city-chat, 2026-09-27: a session's watcher polling keeps it up, so a closed tab never makes an idle session unreachable).
- Start never refuses: over the cap it prints one warning line (the city is small).
- Cloud sessions: no city page (no localhost for the human). The city is local only.

## Anywhere
- Owner decision, 2026-09-28: "even if I am not in the repo I can use agent-city start to see the city; makes more sense for an all-env monitor agent city".
- In the owner's own plain terminal (not a Claude session), `agent-city start|status|stop|demo|...` works from any folder, even outside a repo. Only Claude sessions have the plugin's bin/ on PATH, so a small command does it.
- The command is `~/.local/bin/agent-city`, a copy of `bin/agent-city-shim`. Every run it finds the highest installed plugin version under `~/.claude/plugins/cache/auto-pipeline/auto-pipeline/` (plain versions only, sorted by version, never by name, never a hard-coded version) and runs its `bin/agent-city.sh` with the same args. Nothing installed → it says so, exit 1.
- `AGENT_CITY_PLUGIN_ROOT=<plugin folder>` runs that plugin instead, to try a checkout before it is released.
- Installed by `agent-city.sh install-shim`: the init skill asks the human first and runs it only after a yes. Manual one-line install from any folder: `bash "$(ls -d ~/.claude/plugins/cache/auto-pipeline/auto-pipeline/*/ | sort -V | tail -1)bin/agent-city.sh" install-shim`. `agent-city.sh remove-shim` takes it away.
- Never overwrites or removes a `~/.local/bin/agent-city` that is not ours: ours carries the marker line `# auto-pipeline agent-city shim`; a file without it, a symlink or a folder is left alone and the command says "not ours". `~/.local/bin` not on PATH → it prints how to add it; it never edits a shell profile.
- Outside a repo = the folder is not inside a git work tree. There the city uses the plugin defaults (`bin/agent.conf.default`); an `agent.conf` lying in that folder is never read.
- Port anywhere: `AGENT_CITY_PORT` (1024-65535) wins over `city_port`, inside or outside a repo, so a city outside a repo can still get another port (main manager, 2026-09-28, after a laptop test found 4777 held by the owner's real city). A bad value is refused, nothing starts.
- Start says why, never a bare "failed to start": the port held by another program → it names the port and `AGENT_CITY_PORT`; a city already running in this city dir → its URL plus "already running", stop it first to start it again from here (its settings stay until then).
- Language outside a repo: zh (the city's own default), `AGENT_CITY_LANG=en|zh` overrides it (main manager's default, 2026-09-28; the owner may change it). Inside a repo the repo's `language`, as before.
- Local events: the city shows every repo on this computer, wherever it was started (one city dir per machine, as before).
- `status` from any folder is true for that folder: one line, `CITY: running http://127.0.0.1:<port>` or `CITY: not running`.

## Open, not decided
- A key per person, so one member can be removed without changing everyone's key (proposal, later).
- People from git history, no joining needed (proposal): buildings carry the authors of their files; recent activity shows who works where, people without agents included.
