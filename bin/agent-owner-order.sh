#!/usr/bin/env bash
# agent-owner-order.sh — prove an owner's words were really typed by him (owner-relay). No agent, no tokens.
#   ./agent-owner-order.sh verify --repo <folder> --quote "<words>" [--question "<the question it answered>"] [--time <HH:MM|"YYYY-MM-DD HH:MM">] [--machine <name>]
#   ./agent-owner-order.sh verify --relayed-by-leader <transcript file> --quote "<words>" --time "YYYY-MM-DD HH:MM" [--question "<the question it answered>"]
#   ./agent-owner-order.sh line --quote "<words>" [--question "<the question it answered>"] [--repo <folder>]
# A quote under owner_order_min_chars (20) must be a whole owner prompt and needs --question; the question must stand in the assistant message right before that prompt.
# The file must lie directly in the Configure folder "Approval: Leader transcript folder"; --time is this machine's local minute; only the quote is printed.
# A slash command he typed (/goal <words>) counts with its arguments only; text in a system-reminder or other tag block of a typed prompt never counts.
# Reads Claude transcripts of this machine, read only. Rules: requirements/owner-relay.md.
# Exit 0 ok, 1 refused (stdout says why), 2 usage error (one stderr line).
# Reads owner_order_hours and owner_order_min_chars from the fixed constants of bin/agent_conf.py.
set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
pid=""
[ "${1:-}" = "line" ] && pid=$(agent_pid)
exec python3 -B "$(dirname "$0")/agent_owner_order.py" "$PROJECT_CWD" "$pid" "$@"
