#!/usr/bin/env bash
# agent-nightly.sh — the nightly run (check-blocks section 15, C6). Gates nothing.
#
#   agent-nightly.sh --start [--wait]   run full_cmd of the main repo agent_repo.conf in a scratch worktree at the tip of the working branch
#                                       (full_run_where=remote: in a worktree of that commit on the connected machine, through Orca),
#                                       in the background (returns at once); --wait runs in the foreground
#   agent-nightly.sh --status           NIGHTLY: green|red|running|none <commit> <finished>
#   agent-nightly.sh --due              exit 0 when a start is due, else 1
#   agent-nightly.sh --release-ok       exit 0 only when the last nightly is green on the working branch tip (or its parent when the tip only bumps plugin.json)
#   agent-nightly.sh --failures         one row per failing test of the last red run: test | merge | task | requirement
#   agent-nightly.sh --machines         the reachable paired machines, one name per line; a paired one that did not answer: one
#                                       line starting NIGHTLY: after the names
#   agent-nightly.sh --where            where the full run goes now: local | remote | refused (full_run_where, setting "Full run machine")
#   agent-nightly.sh --misses           selection misses, then "misses: <n> since <date>"
#
# Files in the git common dir: agent_nightly.json, agent_selection_misses.txt. Logic: agent_nightly.py.
case "$0" in */*) _nd=${0%/*};; *) _nd=.;; esac
exec python3 "$(cd "${_nd:-/}" && pwd -P)/agent_nightly.py" "$@"
