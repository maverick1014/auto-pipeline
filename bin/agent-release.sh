#!/usr/bin/env bash
# Build, check and push the `release` branch: one commit per version, whose tree
# is the ship set of a main commit. All logic is in agent_release.py.
exec python3 "$(dirname "$0")/agent_release.py" "$@"
