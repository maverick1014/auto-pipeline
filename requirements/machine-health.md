# machine-health: someone watches the whole machine and cleans what our runs leave

Owner, 2026-11-27: "the main thing is why nobody track the pc2 ram memory and do the clean up. for now can you try to review it and see".

## Today (pc2, 2026-11-27 13:4x)

- TMPDIR holds 281,441 files: a Jest cache of another repo (133,049 files, 3.1 GB), node's compile cache (25,241), and our own leftovers: about 10 `check-blocks-demo.*` folders (~1,000 files each, tests/test_check_blocks_demo.py), `auto_pipeline_*.equiv-snap` folders (script-speed's old-vs-new proof, tests/scriptequiv.py), `cloud_pack_*`.
- fseventsd uses about 2 GB of the 8 GB and a whole core (up 15 days); swap is 4.6 of 5 GB; Spotlight indexes everything, TMPDIR not excluded.
- The memory rule gates only the start of a job (`agent-room.sh check`: memory only, no CPU, no swap); nothing watches the machine between jobs; cleanup removes only what a task registered (panes, worktrees, branches, run2 folders).

## The rule

1. A machine check (`agent-room.sh health`, read only) prints one table: memory in use, swap used, CPU idle (from `top`, two samples), the 5 biggest processes, and TMPDIR file count by kind with the owner of each kind when known (this repo's kinds by name; others "other").
2. `agent-room.sh check <MB>` refuses also when CPU idle is under 20% or swap is over 90% used, with one line naming which.
3. Housekeep (and the main manager's start) runs a sweep of THIS repo's own temp kinds on every machine it uses (the connected machine through Orca): `check-blocks-demo.*`, `auto_pipeline_*`, `cloud_pack_*`, `run2_*` (marker rule of runner-integrity), `agent_test_tools_*`: entries older than 3 hours and not in use by a live process are removed. Other repos' files are never touched; they are only listed.
4. The tests that leave folders clean up after themselves (test_check_blocks_demo, tests/scriptequiv.py, the cloud pack tests), also when a test fails.
5. The watch prints one warning line a sweep when a connected machine is over the limits of rule 2, so the main manager sees it without asking.

## Examples

- `agent-room.sh health` on pc2 today: names fseventsd ~2 GB, swap 4.6/5 GB, TMPDIR 281,441 files with jest_dy (other, 3.1 GB) first.
- `agent-room.sh check 600` at 2% CPU idle: refused, "CPU idle 2% (< 20%)".
- A `check-blocks-demo.x` folder 4 hours old with no process using it: removed by the sweep; one 1 hour old: kept; a `jest_dy` folder: kept and listed as other.
- test_check_blocks_demo run alone, green or red: no `check-blocks-demo.*` folder afterwards.

## Not in this task

Other repos' caches (Jest, node): the owner decides. A reboot of pc2 (clears fseventsd and swap): the owner decides. Spotlight settings of the owner's machines: the owner decides.
