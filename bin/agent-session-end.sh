#!/usr/bin/env bash
# agent-session-end.sh — the SessionEnd hook (hooks/hooks.json, next to the city's entry).
# A session that ends leaves nothing behind (requirements/session-cleanup.md rule 1).
#
#   Claude Code -> stdin JSON {"session_id","cwd",...} -> agent-file.sh session-end <session id>
#   for the repo of cwd: the session's .git/agent_*_<sid> files and its human-direct line go.
#
# Prints nothing, nothing on stderr, always exit 0: bad or empty stdin, a bad session id
# (letters, digits, "_" and "-" only), a repo not set up -> nothing. Never blocks on stdin.
# Spec: tests/test_session_cleanup.py (the CONTRACT docstring).
set -u
exec 2>/dev/null
trap 'exit 0' EXIT
. "$(dirname "$0")/agent-roots.sh"

SID=""; CWD=""
if [ ! -t 0 ]; then
  IN=""; line=""
  while IFS= read -t 1 -r line || [ -n "$line" ]; do IN="$IN$line"; done   # read -t: never block on an open pipe
  [ -n "$IN" ] && eval "$(printf '%s' "$IN" | python3 -c 'import json,sys,shlex
def s(d, k):
    v = d.get(k, "")
    return v if isinstance(v, str) else ""
try:
    d=json.load(sys.stdin)
    print("SID=%s; CWD=%s" % (shlex.quote(s(d, "session_id")), shlex.quote(s(d, "cwd"))))
except Exception: print("SID=; CWD=")' 2>/dev/null)"
fi
case "$SID" in ''|*[!A-Za-z0-9_-]*) exit 0;; esac

roots_read "$CWD"
repo_set_up || exit 0
cd "$PROJECT_CWD" 2>/dev/null || exit 0
CLAUDE_PROJECT_DIR="$PROJECT_CWD" "$PLUGIN_ROOT/bin/agent-file.sh" session-end "$SID" >/dev/null 2>&1 </dev/null
exit 0
