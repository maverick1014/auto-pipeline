#!/usr/bin/env bash
# agent-settings.sh — show the settings. No agent, no tokens. They change only in Claude Code:
# /plugin -> Installed -> auto-pipeline -> Configure
#   ./agent-settings.sh [show]      the settings table, with a * on a value that is not the default
#   ./agent-settings.sh get <key>   one line: the value and where it comes from
#   ./agent-settings.sh statusline on|off|refresh   progress status line in Claude Code settings.json, sets refreshInterval; refresh: only to a plugin cache root
set -eu
PLUGIN_ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
PYBIN="$PLUGIN_ROOT/bin"
CHANGE="settings change only in /plugin -> Installed -> auto-pipeline -> Configure"

usage() { sed -n '2,7p' "$0"; }
py() { PYTHONPATH="$PYBIN${PYTHONPATH:+:$PYTHONPATH}" python3 "$@"; }

getv() {
  py - "$1" <<'PY'
import sys, agent_conf as a
k = sys.argv[1]
try:
    print(f"{a.text(a.get(k))} (from {a.source(k)})")
except KeyError:
    sys.exit(f"unknown setting: {k}")
PY
}

statusline() {
  PYTHONPATH="$PYBIN${PYTHONPATH:+:$PYTHONPATH}" python3 "$PYBIN/agent_update.py" statusline "$1" "$PLUGIN_ROOT"
}

case "${1:-}" in
  statusline)
    case "${2:-}" in
      on|off|refresh) [ $# -eq 2 ] || { usage >&2; exit 2; }; statusline "$2" || exit 1; exit 0;;
      *) echo "usage: agent-settings.sh statusline on|off|refresh" >&2; exit 2;;
    esac;;
esac

case "${1:-}" in
  ""|show) [ $# -le 1 ] || { echo "$CHANGE"; exit 1; }; py "$PYBIN/agent_conf.py" show;;
  get) [ $# -eq 2 ] || { usage >&2; exit 2; }; getv "$2";;
  -h|--help) usage;;
  *) echo "$CHANGE"; exit 1;;
esac
