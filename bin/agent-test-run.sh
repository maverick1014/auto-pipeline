#!/usr/bin/env bash
# agent-test-run.sh — a test run under the memory gate (check-blocks sections 24 and 25).
#
#   agent-test-run.sh --key <key> -- <command...>      "{workers}" in the command = the process count that keeps CPU under the limit
#
# No slots. It reserves its known MB (<git common dir>/agent_test_weights.json; weight.<key>= in agent_repo.conf is only a seed, never written)
# in the machine's reservation list while it runs. An unknown weight starts at once and is monitored: every 0.5 s, over the Max memory %
# limit and this run the pick (newest unmeasured first) -> it stops itself, records its peak, waits for room, runs again.
# A wait is capped by AGENT_TEST_RUN_WAIT_S (default 3600), then exit 3 with the ROOM line. Exit code = the command's.
# Logic: agent_nightly.py (testrun).
exec python3 "$(cd "$(dirname "$0")" && pwd -P)/agent_nightly.py" testrun "$@"
