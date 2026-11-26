# UI work and browser checks
Read when: a task has a new page, a re-layout or a mock, or runs a FLOW CHECK, UI CHECK or RELEASE SMOKE.

W2. UI
- Clickable mock first (prototype artifact)
- Start from a screenshot of the existing real page (Claude in Chrome); change only what the task changes. Never imagine a page from scratch when one exists. Same layout, components, theme
- No existing page to screenshot → the mock follows the project's current style (theme, components); the agent proceeds without asking
- Human says yes
- A mock only for a new page or a whole-page re-layout; the approved mock is what UI CHECK compares with (R8)
- The approved mock is the acceptance criterion of the task
- Then real code

W5. Web UI testing
- Claude in Chrome, not Playwright, on orca and plain
- The check deputy (`agents/check-deputy.md`) drives the browser for FLOW CHECK, UI CHECK and RELEASE SMOKE, one at a time
- Others write the click path and hand it to the main manager, who sends the check deputy
- Unit tests are not proof of a flow a user can reach: FLOW CHECK is (R8)
- What a browser cannot prove goes on a standing "needs a real device" list, never counted as verified
- UI CHECK: the real page against the approved mock or the before screenshot, item by item (layout, content, states, behaviour), desktop and phone width; list every difference
- A layout, content or behaviour difference = not done, back to the builder
- A difference from the real UI theme (colours, fonts, spacing tokens) is fine: keep the real theme, list it as "theme difference" in the report
- The owner says pass = pass; agents follow his final decision. Only a critical problem (crash, wrong data, security) goes to him
- Ask `agent-runtime.sh browser` first: chrome, headless or none
- cloud → headless Chromium via Playwright, the extension can never reach a VM
- none → print the click path under NEEDS HUMAN E2E and stop, wait for the human. Never silent, never forever
