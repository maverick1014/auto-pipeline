#!/usr/bin/env bash
# agent-level.sh — the check blocks a diff triggers (R8, requirements/check-blocks.md). No agent, no tokens.
#   ./agent-level.sh check --base <ref> [--scope "<glob>,<glob>"] [--json] [--declared <x>]
# Diff = working tree of this git repo vs `git merge-base <ref> HEAD` (tracked + untracked, not ignored).
# stdout, in this order: BLOCKS: PR REVIEW first, then the triggered tool blocks, table order[, OWNER SIGN]; one "FILE <path>: <kind>[+<kind>] (<reason>)"
#   per file (kinds: code style text rule asset deps ci migration schema data-script, +core); one detail line per
#   block (DIFF SCAN findings indented); notes; NOT TRIGGERED; NET (heavy over the check_budget_s; RELATED TESTS and MODULE TESTS whose measured weight is
#   light_test_s s or light_test_mb MB or more: the release run or the nightly); BRIEF PICKS last (EXAMPLES TEST, FLOW CHECK, UI CHECK, REAL DATA COUNT).
#   Weights: agent_test_weights.json in the git common dir, then weight.<key> in agent_repo.conf (keys related, group.<folder>, full).
#   MODULE TESTS: the groups of the modules that use a changed file; deps, lockfile, CI or test config: every module (owner signs).
#   --json: one object {blocks, sign, files, findings, related, guard, net}. --declared is accepted and ignored.
# Exit 0 ok, 2 usage or setup error (one stderr line, nothing on stdout).
# The table of blocks: bin/agent_blocks.py. Core paths and the commands come from the main repo's agent_repo.conf.
set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
exec python3 "$(dirname "$0")/agent_level.py" "$PROJECT_CWD" "$@"
