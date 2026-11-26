# Known traps
Read when: a push is denied, a cross-session message is held, a pane send is cut or lost, you look for another agent's pane, read a terminal, work on Linux outside Orca, the screen is locked, or the start text shows MODE MISMATCH or STALE PLUGIN.

W16. Known traps
- A push to the working branch denied by the auto-mode classifier → never retry or work around
- Hand the owner one `! git push ...` line, or ask for an allow rule (init prints `Bash(git push origin <working branch>)` as optional)
- A cross-session message held because permission modes differ → say so, ask the owner to click Deliver, never type it into the pane
- MODE MISMATCH line at start (this session's mode differs from the Permission mode setting) → tell the owner once, plainly; never change a mode, never skip the approval
- Remote Orca pane: a long `terminal send` (~4 KB) arrives cut → write the brief into the worktree's `agent_state.txt` in chunks, send a one-line pointer
- Find another agent's pane with `orca worktree ps --json`, never by its title (titles are often from an old task)
- `terminal read` shows only the visible screen → use `--cursor`
- Linux outside Orca: bare `orca` is the screen reader → use `orca-ide`
- A send while the target is mid-turn can be lost → re-read and resend
- Screen locked → the Chrome extension tab is hidden → use headless Chrome and tell the owner
- STALE PLUGIN line → call the newest bin path, in every brief too, and restart at a quiet point; an older version never retrains agent_estimate.txt
