# nightly-on-machine: the full run of this repo runs on a connected machine

Owner, 2026-11-26: "why only recognize local record ya, actually run on pc2 or local is the same result. but pc2 is much more better option". Then: "ok then for this case, force the test for this repo in pc2 will do."
His machine rule (personal notes): every job goes to a connected machine first (Orca, never ssh); the laptop only when no connected machine has room; clean up what is sent out.

## Today

- `bin/agent-nightly.sh --start` runs the full suite (`full_cmd` of `agent_repo.conf`) in a scratch tree of THIS clone and records the result in this clone's git folder. `--release-ok` and `bin/agent_promote.py` read only that record.
- A full run started on another machine is not seen here, so the publish check asks for a second run on the laptop.

## The rule

1. Where the full run goes:
   - A personal setting, "Full run machine" in /plugin Configure (an Orca environment name; default empty). It is never written into a repo file: the repo is public and machine names are personal.
   - A repo fact in `agent_repo.conf`, `full_run_where`: `either` (default: the connected machine when one is set and has room, else this machine), `remote` (only the connected machine; when it is not set, not reachable or has no room, the run waits or is refused with one line; it never falls back to the laptop), `local` (as today).
   - This repo: `full_run_where = remote` (the owner's "force"). The person's setting on the laptop names the machine.
2. How it runs there, through Orca only (`orca worktree create|remove`, `orca terminal create|send|read|wait|close`, `--environment <name>`; never ssh):
   - a clean worktree of the EXACT commit being checked, from the remote's clone of this repo, cut by commit (no branch is pushed for it);
   - the same `full_cmd` from that commit's `agent_repo.conf`, the same runner and its memory gate on that machine;
   - one full run at a time per repo; the room rule of the machine applies there.
3. The result comes back and is recorded here as a full run of that commit: green or red, the failing tests by name, the start and end time, the test weights if the runner writes them. The record says it ran on a connected machine (no machine name in any file that is committed).
4. The result counts only when the remote reports the commit it ran (`git rev-parse HEAD` in its worktree) and that commit is the one asked for; a missing or different commit, an output that cannot be read, a run that stopped half way: recorded as a failed run with that line, never green.
5. Afterwards the remote worktree, its terminal and any scratch folder are removed there, also after a failure or a timeout. A worktree left by a killed run is removed by the next start.
6. `--status` says where the last full run ran and how it ended. `--release-ok` and the publish accept a green full run from the connected machine exactly like a local one.

## Examples (the failing tests come from these)

- `full_run_where = remote`, the setting names an environment, Orca stubbed: `--start` creates a worktree of commit C on that environment, sends the full command, reads the result with commit C, records green on C; `--release-ok` passes on C; the worktree and terminal are removed.
- The same with a red result naming `test_x`: recorded red, `--failures` names `test_x`, publish refused; cleanup done.
- The remote reports commit D while C was asked: recorded failed, "the connected machine ran D, not C"; never green.
- `remote` and the environment is not reachable (the Orca stub says so): refused with one line, no local run started.
- `remote` and the setting is empty: refused, "set Full run machine in /plugin Configure".
- `either` with no setting: runs here as today; `either` with a reachable machine: runs there.
- `local`: runs here as today, no Orca call.
- A stale remote worktree from a killed run: removed by the next `--start`.
- No machine name appears in `agent_repo.conf`, the tests' fixtures or any committed file.

## Proof on the real machines

The builder runs the mechanics once for real from the laptop on the connected machine with a SHORT command (an override for this proof only, e.g. two light test files, never the full suite), shows the record, and shows that nothing is left on the remote. The real full run of the batch is started by the main manager after the merge.

## Not in this task

Making the suite faster (test-slim-3). The nightly's time of day. Other repos.
