# city-one-sidebar: one left sidebar, and a click on a person keeps the whole office in view

Owner, 2026-11-27:
- "for the agentcity, actually i think the right lift selection is very annoying. can it combine to the left bar some how. because i think both design is good. just because the screen did not have much space so i think 1 sidebar will do. you can use prototype to update first."
- "then for the agent city, when click to the person dont zoom in, because sometimes it zoom in and it will be hard to zoom out. and actually i dont want to see it own only. i want overlook the whole office"

## Today (bin/agent-city.html)

- Left: the rail (`.rail`, `--rail-w: 300px`), the team list as a tree, folds to a thin tab.
- Right: the lift panel (`--lift-w: 168px`, top right), the floor picker of the office building (approved look: mock/city-office-mock.html v5).
- A click on a person selects them: `select()` turns on follow and sets `cam.wantDist`, so the camera eases and zooms onto that person; a detail window or sheet opens.

## The rule

1. One sidebar on the left. The lift's job (pick the floor, see which floors exist and which one you are on, its floor count) moves into the left bar, together with the team list. The right side is free for the office. Both designs stay recognisable (the owner likes both); only their place changes.
2. Prototype first (a whole-page re-layout): a mock page, desktop and phone width, before any change to the real page. Nothing is built for item 1 until the owner says yes to the mock.
3. A click on a person never moves or zooms the camera: the whole office stays in view; the person is marked (their plate full, a highlight) and their details open as today (window on desktop, sheet on phone). Zoom stays the user's own choice (the zoom buttons, the wheel, pinch).
4. Nothing else changes: the floors, the seats, the plates, the designer, the street view.

## Examples

- Desktop 1440 wide: one bar on the left with the floor list and the team list; no panel on the right; the office fills the rest.
- Phone 390 wide: the one bar folds to a tab; opening it shows the floors and the team; the office stays full width.
- Pick another floor in the left bar: the office shows that floor, as the lift did.
- Click a person on a floor (desktop and phone): the camera stays where it was (same zoom, same view of the whole floor), the person's plate is full and marked, the detail window or sheet opens; close it: nothing moved.
- Zoom in by hand, click a person: the view stays at that zoom.

## Checks

PR REVIEW, EXAMPLES TEST, UI CHECK (desktop and phone, against the approved mock for item 1).
