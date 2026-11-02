#!/usr/bin/env bash
# agent-cleanup.sh — the cleanup sweep. One mechanical pass, never an agent.
#
#   agent-cleanup.sh            list: what --apply would do, then the kept table.
#                               Changes nothing (a git fetch is fine)
#   agent-cleanup.sh --apply    remove the SAFE items, then the kept table
#   agent-cleanup.sh --short    (with or without --apply) the hook form
#   agent-cleanup.sh -h         this help
#
# Main manager only (role main or takeover, agent-roots.sh role_read). A spawned
# agent, a human-direct Helper and a closed session are refused before any orca
# or git call. The logic is bin/agent_cleanup.py; this file only checks the role,
# works out the runtime kind and hands over.

set -u
. "$(dirname "$0")/agent-roots.sh"

usage() {
  cat <<'EOF'
agent-cleanup.sh — remove what is finished: merged worktrees and branches, dead panes, leftover pipeline processes.

  agent-cleanup.sh             list what --apply would do, then the kept table (changes nothing)
  agent-cleanup.sh --apply     remove the SAFE items, then the kept table
  agent-cleanup.sh --short     the hook form (with or without --apply)
  agent-cleanup.sh -h          this help

Main manager only. A worktree is removed only when it is merged into origin/main,
pushed, clean, on a branch, with no live agent and no working, final or
human-direct line in agent_worktree.txt. Never --force. A paired machine's
worktree is listed, never removed.
EOF
}

APPLY=0
SHORT=0
for arg in "$@"; do
  case "$arg" in
    -h|--help) usage; exit 0;;
    --apply) APPLY=1;;
    --short) SHORT=1;;
    *) usage >&2; exit 2;;
  esac
done

roots_read
role_read
case "$role" in
  spawned|second|closed)
    echo "REFUSED: cleanup is main manager only (role $role)." >&2
    exit 1;;
esac

ROOT="$PROJECT_ROOT"
PLUGIN="$PLUGIN_ROOT"
. "$(dirname "$0")/agent-runtime.sh"
KIND=$(runtime_kind)

args=(--root "$ROOT" --plugin "$PLUGIN" --kind "$KIND")
[ "$APPLY" = 1 ] && args+=(--apply)
[ "$SHORT" = 1 ] && args+=(--short)
exec python3 "$PLUGIN/bin/agent_cleanup.py" "${args[@]}"
