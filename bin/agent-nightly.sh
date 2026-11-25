#!/usr/bin/env bash
# agent-nightly.sh — the nightly run (check-blocks section 15, C6). Gates nothing.
#
#   agent-nightly.sh --start [--wait]   run full_cmd of the main repo's agent_repo.conf on its main HEAD,
#                                       in the background (returns at once); --wait runs in the foreground
#   agent-nightly.sh --status           NIGHTLY: green|red|running|none <commit> <finished>
#   agent-nightly.sh --due              exit 0 when a start is due, else 1
#   agent-nightly.sh --release-ok       exit 0 only when the last nightly is green on the current origin/main
#   agent-nightly.sh --misses           selection misses, then "misses: <n> since <date>"
#
# Files in the git common dir: agent_nightly.json, agent_selection_misses.txt. Logic: agent_nightly.py.
exec python3 "$(cd "$(dirname "$0")" && pwd -P)/agent_nightly.py" "$@"
