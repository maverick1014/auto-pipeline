#!/usr/bin/env bash
# agent-name.sh — SessionStart hook: names the Claude Code session by its role.
# Second hook next to agent-start.sh (that one prints plain text for the
# context, a hook cannot print both text and JSON). See hooks/hooks.json and
# tests/test_agent_name.py (the CONTRACT docstring is the spec).
#
#   Claude Code -> stdin JSON {"session_id","transcript_path","cwd",
#   "hook_event_name","source"} -> stdout is nothing, or one JSON line
#   {"hookSpecificOutput": {"hookEventName": "SessionStart", "sessionTitle": name}}
#
#   main manager (or a takeover)      "<repo> Manager"
#   second session, human-direct      "<repo> Helper"
#   spawned, AGENT_ROLE=task-manager  "<feature> Task Manager"
#   spawned, any other AGENT_ROLE     "<feature> <Words Of The Role>"
#   closed (released or replaced)     no name: it is not the main manager any more
#
# repo = folder of the project's main worktree, feature = folder of the git
# toplevel the session runs in. The role comes from role_read (agent-roots.sh),
# the same code agent-start.sh prints its ROLE line from.
# Only for source startup, resume, fork; a project without agent.conf is left
# alone. Inside Orca ($ORCA_TERMINAL_HANDLE) the tab gets the same name, cut
# off after 2 s (macOS has no `timeout`). Always exit 0, nothing on stderr,
# no file written.
set -u
exec 2>/dev/null
trap 'exit 0' EXIT
. "$(dirname "$0")/agent-roots.sh"

# ---- hook input (bad or empty stdin JSON means a startup, like agent-start.sh) ----
SRC=startup; CWD=""
if [ ! -t 0 ]; then
  IN=""; line=""
  while IFS= read -t 1 -r line || [ -n "$line" ]; do IN="$IN$line"; done   # read -t: never block on an open pipe; || keeps a final line with no trailing newline
  [ -n "$IN" ] && eval "$(printf '%s' "$IN" | python3 -c 'import json,sys,shlex
try:
    d=json.load(sys.stdin)
    print("SRC=%s; CWD=%s" % (shlex.quote(d.get("source","startup")), shlex.quote(d.get("cwd",""))))
except Exception: print("SRC=startup; CWD=")' 2>/dev/null)"
fi

case "$SRC" in startup|resume|fork) ;; *) exit 0;; esac

roots_read "$CWD"
[ -f "$PROJECT_ROOT/agent.conf" ] || exit 0
role_read

repo=$(basename "$PROJECT_ROOT")
feature=$(basename "$STATE_DIR")
case "$role" in
  closed) exit 0;;
  spawned)
    if [ "$AGENT_ROLE" = task-manager ]; then
      name="$feature Task Manager"
    else
      # merge-deputy -> Merge Deputy: split on - and _, capitalise each word
      words=""; oldifs=$IFS; IFS='-_'; set -f
      for w in $AGENT_ROLE; do
        [ -n "$w" ] || continue
        words="$words $(printf '%s' "${w:0:1}" | tr '[:lower:]' '[:upper:]')${w:1}"
      done
      set +f; IFS=$oldifs
      name="$feature${words:- $AGENT_ROLE}"
    fi;;
  second) name="$repo Helper";;
  *)      name="$repo Manager";;
esac

out=$(AGENT_NAME_TITLE="$name" python3 -c 'import json,os
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "sessionTitle": os.environ["AGENT_NAME_TITLE"]}}))' 2>/dev/null)
[ -n "$out" ] || exit 0
printf '%s\n' "$out"

# ---- the Orca tab gets the same name; a slow, failing or missing orca changes nothing ----
if [ -n "${ORCA_TERMINAL_HANDLE:-}" ] && command -v orca >/dev/null 2>&1; then
  orca terminal rename --terminal "$ORCA_TERMINAL_HANDLE" --title "$name" --json </dev/null >/dev/null 2>&1 &
  pid=$!
  step=0
  while [ "$step" -lt 20 ] && kill -0 "$pid" 2>/dev/null; do
    sleep 0.1
    step=$((step + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    pkill -TERM -P "$pid" 2>/dev/null
    kill -TERM "$pid" 2>/dev/null
  fi
fi
exit 0
