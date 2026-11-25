#!/usr/bin/env bash
# agent-room.sh — the memory gate and the reservation list (check-blocks sections 24 and 25).
#
#   agent-room.sh check <mb>|unknown      exit 0 when memory in use + live reservations + <mb> <= the Max memory % limit
#                                         (unknown = need 0), else exit 1 with "ROOM: no: <used> MB in use + <reserved> MB reserved + <need> MB > <limit> MB"
#   agent-room.sh reserve <pid> <mb> "<what>" [--kind test|build|pane] [--unmeasured]
#   agent-room.sh release <pid>
#   agent-room.sh list                    one line per live job
#   agent-room.sh relief                  over the limit: stop test and build runs (newest unmeasured first), never a pane
#   agent-room.sh measure-pane <pid>      summed RSS of that process tree into the weights key "pane" (keeps the highest)
#
# One reservation file per machine: $AGENT_RESERVE_FILE, default ~/.claude/auto-pipeline-reservations.json. Logic: agent_nightly.py.
exec python3 "$(cd "$(dirname "$0")" && pwd -P)/agent_nightly.py" "$@"
