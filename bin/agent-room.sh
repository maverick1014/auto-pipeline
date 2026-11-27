#!/usr/bin/env bash
# agent-room.sh — the memory gate and the reservation list (check-blocks sections 24 and 25).
#
#   agent-room.sh check <mb>|unknown      exit 0 when memory in use + live reservations + <mb> <= the Max memory % limit
#                                         (unknown = need 0), else exit 1 with "ROOM: no: <used> MB in use + <reserved> MB reserved + <need> MB > <limit> MB"
#   agent-room.sh reserve <pid> <mb> "<what>" [--kind test|build|pane] [--unmeasured]
#   agent-room.sh reserve-pane <handle> <mb>   a pane reserved from its launch until measure-pane of that ORCA_TERMINAL_HANDLE (or 15 min)
#   agent-room.sh reserve-pane --pending <key> <mb>   before the create: check room and reserve in one step (exit 1: no room, or the key exists)
#   agent-room.sh reserve-pane --name <key> <handle>  after the create: the pending reservation takes the new handle (no check)
#   agent-room.sh release-pane <key>      a failed create: drop the pending reservation
#   agent-room.sh release <pid>
#   agent-room.sh list                    one line per live job
#   agent-room.sh relief                  over the limit: stop test and build runs (newest unmeasured first), never a pane
#   agent-room.sh measure-pane <pid>      summed RSS of that process tree into the weights key "pane" (the highest of the last 5, never below 550 MB)
#
# One reservation file per machine: $AGENT_RESERVE_FILE, default ~/.claude/auto-pipeline-reservations.json. Logic: agent_nightly.py.
case "$0" in */*) _room_dir=${0%/*}; [ -n "$_room_dir" ] || _room_dir=/;; *) _room_dir=.;; esac
AGENT_ROOM_CLI=1 exec python3 "$(cd "$_room_dir" && pwd -P)/agent_nightly.py" "$@"
