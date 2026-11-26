# Resources and placement
Read when: before a run, build, pane or agent starts; you place a job or a test run on a machine; memory or usage is over the limit; you count panes.

W7 (placement)
- Placement: every job goes to a connected machine first (the one with the most room by S3); the local machine only when no connected machine has room or the job needs it; no machine is special; local stays clean and fast for the human
- The automatic nightly starts only where there is room, else it says so; the main manager places a nightly by hand like any heavy job: a connected machine with the most room first
- While a connected machine exists the automatic nightly never runs the full suite locally; it says so and the main manager places it there

S3. Resource guard
- A run (a test command, a build, a new agent pane) starts when memory in use now + the memory this run is known to need <= the "Load: Max memory %" limit (default 80): `agent-room.sh check`
- Known to need = the measured peak MB; a Claude pane counts too (about 300-550 MB; 550 MB while never measured)
- A run that was never measured is not held back: it starts at once with a monitor on its memory; the monitor runs for every test or build run, measured or not
- Over the limit the monitor stops the newest, unmeasured one first, records its peak MB, and the run is tried again when there is room. Only test and build runs are stopped
- CPU: a parallel test runner uses as many processes as keep CPU under the same limit (`{workers}`); memory is the hard gate, CPU the soft one. Long but light runs just go

S4. Usage cap
- Over the limit: start nothing new; close done and idle panes first; stop test runs before anything else (`agent-room.sh relief`)
- A working agent is left alone: never stop a working agent, tell the main manager instead, one line: which machine, how much over, what it did
- relief stops only what the pipeline owns: `agent-watch.sh --all` processes left by tests, watches of repos with no live main manager
- The sweep (W8) runs `agent-resources.sh stop-leftovers`: this repo's orphan watch and finished test watches only, no table
- A task manager over cap parks: commit, write state, set idle; the main manager closes its pane; resume brings it back
- The human's apps, other repos' sessions, Gradle or node runners: never killed by an agent. One table to the human: process · MB · CPU · what · suggestion
- Setting "Load: Max memory %" = 80

S6. No count caps
- No count caps: no fixed count of agents, task managers or subagents per machine; a new agent pane is admitted by the same rule as any job (S3)
- A pane in state working or permission is a busy agent; a done or idle pane and the main manager are not counted when the memory rule (S3) adds up panes
- A finished idle pane (state done): its own repo's main manager closes it once its task is merged, dropped or closed
- Never one still waiting on a merge, a question or a decision (W8 closes it after the merge). Never another repo's panes
