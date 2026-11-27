# nightly-remote-send: the remote full run must start, or fail with a clear reason

Day 2026-11-27: `agent-nightly.sh --start` on the connected machine failed 3 times. In its terminal only the tail of the one-line command arrived (cut at `...git rev-parse --git-common-di`), then a bare prompt; the script never ran, and the laptop kept the status `running` for 30+ minutes. The 4th try worked. Known trap (rules/traps.md W16): a long `terminal send` (about 4 KB) to a remote Orca pane arrives cut. Likely cause: the send arrives before the remote shell is ready, and the tty line limit (about 1 KB) cuts the one long line.

## The rule

`remote_run` in `bin/agent_nightly.py`:

1. Wait for a shell prompt. After the terminal is made, read it until its last non-empty line ends like a prompt (`$ % # > ❯ ➜`). Nothing is sent before that. No prompt within `AGENT_NIGHTLY_PROMPT_S` (default 30 s): go on anyway (rule 3 catches a lost send).
2. Never send one long line. The wrapper script and the command are written into the remote worktree in chunks, one `terminal send` each, every line under 700 characters (`printf %s <base64 piece> >> .nightly-run.b64`, the same for the command in `.nightly-cmd.b64`). A last short line decodes the script and runs it (`base64 -d`, `bash .nightly-run.sh "$(cat .nightly-cmd.b64)"`). Only letters, digits, `+ / =` are typed, as before; the token stays out of every sent line.
3. No BEGIN marker within 60 s (`AGENT_NIGHTLY_BEGIN_S`) after the last send: stop that try (interrupt the terminal), remove its remote terminal and worktree, and try once more with a fresh worktree and terminal. Still no BEGIN: the run is recorded failed (`result: red`, never `running`) with the reason `the connected machine: the remote run never started (no begin marker in 60 s, 2 tries)`.
4. A time limit for the whole run, counted from BEGIN: 2 x the last measured `nightly` weight in `agent_test_weights.json`, at least 20 minutes (`AGENT_NIGHTLY_REMOTE_TIMEOUT_S` overrides it, as before). No measured weight yet: 3 hours as before. At the limit the terminal is interrupted and the run is recorded failed: `the connected machine: the run stopped half way, timed out after <n> s`.
5. Cleanup of the remote terminal and worktree happens after every try, also a failed one.

## Examples (the failing tests come from these)

- The first send arrives cut (stub): no BEGIN, that try is cleaned, the second try runs; the record is green on the commit; two worktrees were made, none is left.
- Every send arrives cut: two tries, then recorded `red` with `the remote run never started`; no worktree left; the status is not `running`.
- A run that prints BEGIN and then never ends, with the limit set to 1 s: recorded `red`, `timed out`, the terminal interrupted, nothing left.
- The shell is not ready (no prompt for the first reads): nothing is sent until a prompt shows; the first try works; one worktree.
- The stub drops all but the last 1000 characters of any single send: the run is still green, and no sent line is over 700 characters.
- The limit: weight `3000 s` gives 6000 s; weight `100 s` gives 1200 s (the minimum); no weight gives 10800 s; the env override wins.
- The token is in no sent line (as before).

## Not in this task

A real full remote run. The runner on the remote machine. Other W16 traps.
