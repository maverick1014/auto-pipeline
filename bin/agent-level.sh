#!/usr/bin/env bash
# agent-level.sh — the risk type (A-D) of each file and task part of a diff (R8). No agent, no tokens.
#   ./agent-level.sh check --base <ref> [--declared <A|B|C|D>]   (old 0-4 still read: 0=A 1=B 2,3=C 4=D)
# Diff = working tree of this git repo vs `git merge-base <ref> HEAD` (tracked + untracked, not ignored).
# stdout: REQUIRED TYPE <types joined by +>, one "<path>: <type> <reason>" per file, one "PART <type>: <paths>" per type,
#   notes, a RAISE line when a C or D file is above the declared type. A and B files never raise.
# Exit 0 ok, 1 RAISE, 2 usage or setup error (one stderr line).
# Reads level3_paths (C) and level4_paths (D) from the MAIN repo's agent.conf, also from a worktree.
set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
exec python3 "$(dirname "$0")/agent_level.py" "$PROJECT_ROOT/agent.conf" "$PROJECT_CWD" "$@"
