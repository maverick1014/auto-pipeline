#!/usr/bin/env bash
# agent-housekeep.sh — the housekeeping pass. One mechanical pass, never an agent.
#
#   agent-housekeep.sh           list: print the block, change nothing
#   agent-housekeep.sh --apply   do it, write the block into agent_state.txt
#   agent-housekeep.sh -h        this help
#
# Main manager only (role main or takeover, agent-roots.sh role_read). Other
# roles are refused before any orca or git call. The logic is
# bin/agent_housekeep.py; this file checks the role, works out the runtime kind
# and hands over.

set -u
. "$(dirname "$0")/agent-roots.sh"

usage() {
  cat <<'EOF2'
agent-housekeep.sh — the housekeeping pass: stale worktree lines, duplicate and suspect ideas, merged and stale todos, related repos, then the cleanup sweep.

  agent-housekeep.sh           list mode: print the block, change nothing (no stamp, no agent_state.txt)
  agent-housekeep.sh --apply   do it, write the block into agent_state.txt, print it
  agent-housekeep.sh -h        this help

This is main manager only. The monitor loop runs it with --apply every
housekeep_interval_min minutes (agent.conf, 0 = off). In plain and cloud there is no
loop: run agent-housekeep.sh --apply by hand there.
EOF2
}

APPLY=0
for arg in "$@"; do
  case "$arg" in
    -h|--help) usage; exit 0;;
    --apply) APPLY=1;;
    *) usage >&2; exit 2;;
  esac
done

roots_read
role_read
case "$role" in
  spawned|second|closed)
    echo "REFUSED: housekeep is main manager only (role $role)." >&2
    exit 1;;
esac

. "$(dirname "$0")/agent-runtime.sh"
KIND=$(runtime_kind)

args=(--root "$PROJECT_ROOT" --plugin "$PLUGIN_ROOT" --gitdir "$PROJECT_GITDIR" --kind "$KIND")
[ "$APPLY" = 1 ] && args+=(--apply)
exec python3 "$PLUGIN_ROOT/bin/agent_housekeep.py" "${args[@]}"
