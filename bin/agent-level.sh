#!/usr/bin/env bash
# agent-level.sh — the check blocks a diff triggers (R8, requirements/check-blocks.md). No agent, no tokens.
#   ./agent-level.sh check --base <ref> [--scope "<glob>,<glob>"] [--json] [--declared <x>]
# Diff = working tree of this git repo vs `git merge-base <ref> HEAD` (tracked + untracked, not ignored).
# stdout, in this order: BLOCKS: <triggered tool blocks, table order>[, OWNER SIGN]; one "FILE <path>: <kind>[+<kind>] (<reason>)"
#   per file (kinds: code style text rule asset deps ci migration schema data-script, +core); one detail line per
#   block (DIFF SCAN findings indented); notes; NOT TRIGGERED; NET (heavy over the check_budget_s); BRIEF PICKS last.
#   --json: one object {blocks, sign, files, findings, related, guard, net}. --declared is accepted and ignored.
# Exit 0 ok, 2 usage or setup error (one stderr line, nothing on stdout).
# The table of blocks: bin/agent_blocks.py. Core paths and the commands come from the main repo's agent_repo.conf.
set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
exec python3 "$(dirname "$0")/agent_level.py" "$PROJECT_CWD" "$@"
