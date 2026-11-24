#!/usr/bin/env bash
# agent-level.sh — the risk level a diff needs (R8). No agent, no tokens.
#   ./agent-level.sh check --base <ref> [--declared <0-4>]
# Diff = working tree of this git repo vs `git merge-base <ref> HEAD` (tracked + untracked, not ignored).
# stdout: REQUIRED LEVEL <n>, one "<path>: L<k> <reason>" per file, notes, RAISE line when declared < needed.
# Exit 0 ok, 1 RAISE (declared level too low), 2 usage or setup error (one stderr line).
# Reads level3_paths and level4_paths from the MAIN repo's agent.conf, also from a worktree.
set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
exec python3 "$(dirname "$0")/agent_level.py" "$PROJECT_ROOT/agent.conf" "$PROJECT_CWD" "$@"
