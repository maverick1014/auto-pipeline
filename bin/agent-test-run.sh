#!/usr/bin/env bash
# agent-test-run.sh — a test run is light or heavy by MEASURED weight (check-blocks section 15, C7).
#
#   agent-test-run.sh --key <key> -- <command...>
#
# Weight: weight.<key>=<s> s <mb> MB in agent_repo.conf of the git toplevel of the cwd. Unknown = heavy.
# Heavy takes a slot (<git common dir>/agent_heavy_slots/<pid>); light only meets the RAM guard.
# A wait is capped by AGENT_TEST_RUN_WAIT_S (default 3600), then exit 3 with the reason.
# Prints the command's output, writes the measured weight back, exits with the command's exit code.
# Logic: agent_nightly.py (testrun).
exec python3 "$(cd "$(dirname "$0")" && pwd -P)/agent_nightly.py" testrun "$@"
