#!/usr/bin/env bash
# agent-nightly.sh — the nightly run (check-blocks section 15, C6). Gates nothing.
#
#   agent-nightly.sh --start [--wait] [--nightly]   (--nightly: the automatic nightly, always the full run)
#                                       run full_cmd of the main repo agent_repo.conf in a scratch worktree at the tip of the working branch,
#                                       in the background (returns at once); --wait runs in the foreground
#                                       after a green full run on G, when G..tip changes only .md, mock/, tests/test_*.py or the plugin.json
#                                       version line, and no frontmatter of agents/ or skills/ (decided from git alone): a TOP-UP instead (guard_tests + the changed test files)
#   agent-nightly.sh --status           NIGHTLY: green|red|running|none <commit> <finished> full run|top-up over <G>,
#                                       then NEEDED: the kind of run the tip needs now and why
#   agent-nightly.sh --due              exit 0 when a start is due, else 1
#   agent-nightly.sh --release-ok       exit 0 only when the last nightly (full, or a top-up standing on a green full run that is an
#                                       ancestor) is green on the working branch tip (or its parent when the tip only bumps plugin.json)
#   agent-nightly.sh --failures         one row per failing test of the last red run: test | merge | task | requirement
#   agent-nightly.sh --machines         the reachable paired machines, one name per line; a paired one that did not answer: one
#                                       line starting NIGHTLY: after the names
#   agent-nightly.sh --misses           selection misses, then "misses: <n> since <date>"
#
# Files in the git common dir: agent_nightly.json, agent_selection_misses.txt. Logic: agent_nightly.py.
exec python3 "$(cd "$(dirname "$0")" && pwd -P)/agent_nightly.py" "$@"
