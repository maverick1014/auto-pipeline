#!/usr/bin/env bash
# agent-test-run.sh — a test run is light or heavy by MEASURED weight (check-blocks section 15, C7).
#
#   agent-test-run.sh --key <key> -- <command...>
#
# Weight: measured per machine in <git common dir>/agent_test_weights.json ({key: "<s> s <mb> MB"}); weight.<key>= in agent_repo.conf is only a seed. Unknown = heavy.
# Heavy takes a slot (<git common dir>/agent_heavy_slots/<pid>); light only meets the RAM guard.
# A wait is capped by AGENT_TEST_RUN_WAIT_S (default 3600), then exit 3 with the reason.
# Prints the command output, writes the measured weight (peak of the whole process tree) to the json, never to agent_repo.conf, exits with the command's exit code.
# Logic: agent_nightly.py (testrun).
exec python3 "$(cd "$(dirname "$0")" && pwd -P)/agent_nightly.py" testrun "$@"
