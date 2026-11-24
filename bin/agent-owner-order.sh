#!/usr/bin/env bash
# agent-owner-order.sh — prove an owner's words were really typed by him (owner-relay). No agent, no tokens.
#   ./agent-owner-order.sh verify --repo <folder> --quote "<words>" [--time <HH:MM|"YYYY-MM-DD HH:MM">] [--machine <name>]
#   ./agent-owner-order.sh line --quote "<words>" [--repo <folder>]
# Reads Claude transcripts of this machine, read only. Rules: requirements/owner-relay.md.
# Exit 0 ok, 1 refused (stdout says why), 2 usage error (one stderr line).
# Reads owner_order_hours and owner_order_min_chars from the MAIN repo's agent.conf.
set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
pid=""
[ "${1:-}" = "line" ] && pid=$(agent_pid)
exec python3 -B "$(dirname "$0")/agent_owner_order.py" "$PROJECT_ROOT/agent.conf" "$PROJECT_CWD" "$pid" "$@"
