#!/usr/bin/env bash
# agent-name.sh — names the Claude Code session by its role. Two hook modes, one copy of the name logic.
# Second hook next to agent-start.sh (that one prints plain text for the
# context, a hook cannot print both text and JSON). See hooks/hooks.json and
# tests/test_agent_name.py (the CONTRACT docstring is the spec).
#
# 1. SessionStart (no argument)
#   Claude Code -> stdin JSON {"session_id","transcript_path","cwd",
#   "hook_event_name","source"} -> stdout is nothing, or one JSON line
#   {"hookSpecificOutput": {"hookEventName": "SessionStart", "sessionTitle": name}}
#
#   main manager (or a takeover)      "<repo> Manager"
#   second session, human-direct      "<repo> Helper <Task Name>" (its task), else "<repo> Helper"
#   spawned, AGENT_ROLE=task-manager  "<feature> Task Manager"
#   spawned, any other AGENT_ROLE     "<feature> <Words Of The Role>"
#   closed (released or replaced)     no name: it is not the main manager any more
#
#   repo = folder of the project's main worktree, feature = folder of the git
#   toplevel the session runs in. The role comes from role_read (agent-roots.sh),
#   the same code agent-start.sh prints its ROLE line from.
#   Only for source startup, resume, fork; a project without agent.conf is left
#   alone. Inside Orca ($ORCA_TERMINAL_HANDLE) the tab gets the same name, cut
#   off after 2 s (macOS has no `timeout`). Always exit 0, nothing on stderr,
#   no file written.
#
#   The Helper's task: the first line of "<git dir of the project>/agent_helper_task_<session id>",
#   written by `agent-file.sh helper-task "<Task Name>"`. The session id is the stdin "session_id",
#   else $CLAUDE_CODE_SESSION_ID (letters, digits, "_" and "-" only). No file, or an empty first line: no task.
#   A task never changes the name of any other role.
#
# 2. UserPromptSubmit: agent-name.sh --prompt
#   Claude Code -> stdin JSON {"session_id","cwd","prompt",...} -> stdout is nothing, or one JSON line
#   {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "sessionTitle": "<repo> Helper <Task Name>"}}
#
#   Only a Helper (role second) with a task, and only when that name differs from the last one this mode
#   printed for this session id (marker "<git dir>/agent_helper_title_<session id>", written atomically
#   when a title is printed; the only file this mode writes). Otherwise nothing, so a human /rename is
#   kept. The session id comes from the parsed JSON only, never from the text of the prompt.
#   Checked cheapest first: AGENT_ROLE set (a spawned agent is never a Helper), stdin JSON, agent.conf,
#   role, task, marker. The Orca tab is renamed with the same 2 s cut, only when a title is printed.
#   Runs on every prompt: no network, one python3 call when nothing is printed, aims under 300 ms.
#   Always exit 0, nothing on stderr.
set -u
exec 2>/dev/null
trap 'exit 0' EXIT
. "$(dirname "$0")/agent-roots.sh"

PROMPT=""; [ "${1:-}" = "--prompt" ] && PROMPT=1
[ -z "$PROMPT" ] || [ -z "${AGENT_ROLE:-}" ] || exit 0   # a spawned agent is never a Helper: nothing to read

# ---- the Orca tab gets the same name; a slow, failing or missing orca changes nothing ----
orca_rename() {
  local pid step=0
  [ -n "${ORCA_TERMINAL_HANDLE:-}" ] && command -v orca >/dev/null 2>&1 || return 0
  orca terminal rename --terminal "$ORCA_TERMINAL_HANDLE" --title "$1" --json </dev/null >/dev/null 2>&1 &
  pid=$!
  while [ "$step" -lt 20 ] && kill -0 "$pid" 2>/dev/null; do
    sleep 0.1
    step=$((step + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    pkill -TERM -P "$pid" 2>/dev/null
    kill -TERM "$pid" 2>/dev/null
  fi
  return 0
}

# the first line of a one-line file in the shared git dir; nothing when it is not there
first_line() {
  local l=""
  [ -f "$1" ] && { IFS= read -r l < "$1" || true; }
  printf '%s' "$l"
}

# ---- hook input (bad or empty stdin JSON means a startup, like agent-start.sh) ----
SRC=startup; CWD=""; SID=""
if [ ! -t 0 ]; then
  IN=""; line=""
  while IFS= read -t 1 -r line || [ -n "$line" ]; do IN="$IN$line"; done   # read -t: never block on an open pipe; || keeps a final line with no trailing newline
  [ -n "$IN" ] && eval "$(printf '%s' "$IN" | python3 -c 'import json,sys,shlex
def s(d, k, x):
    v = d.get(k, x)
    return v if isinstance(v, str) else x
try:
    d=json.load(sys.stdin)
    print("SRC=%s; CWD=%s; SID=%s" % (shlex.quote(s(d, "source", "startup")), shlex.quote(s(d, "cwd", "")), shlex.quote(s(d, "session_id", ""))))
except Exception: print("SRC=startup; CWD=; SID=")' 2>/dev/null)"
fi

if [ -n "$PROMPT" ]; then
  [ -n "$SID" ] || exit 0   # bad or empty JSON, or no session id: nothing to name
else
  case "$SRC" in startup|resume|fork) ;; *) exit 0;; esac
  [ -n "$SID" ] || SID=${CLAUDE_CODE_SESSION_ID:-}
fi
case "$SID" in ''|*[!A-Za-z0-9_-]*) SID="";; esac

roots_read "$CWD"
[ -f "$PROJECT_ROOT/agent.conf" ] || exit 0
role_read

repo=$(basename "$PROJECT_ROOT")
feature=$(basename "$STATE_DIR")
task=""
if [ "$role" = second ] && [ -n "$SID" ]; then task=$(first_line "$PROJECT_GITDIR/agent_helper_task_$SID"); fi

if [ -n "$PROMPT" ]; then
  # a title only for a Helper with a task, and only when it is not the one already printed
  [ "$role" = second ] && [ -n "$task" ] || exit 0
  name="$repo Helper $task"
  marker="$PROJECT_GITDIR/agent_helper_title_$SID"
  [ "$(first_line "$marker")" != "$name" ] || exit 0
  EVENT=UserPromptSubmit
else
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
    second) name="$repo Helper${task:+ $task}";;
    *)      name="$repo Manager";;
  esac
  EVENT=SessionStart
fi

out=$(AGENT_NAME_EVENT="$EVENT" AGENT_NAME_TITLE="$name" python3 -c 'import json,os
print(json.dumps({"hookSpecificOutput": {"hookEventName": os.environ["AGENT_NAME_EVENT"], "sessionTitle": os.environ["AGENT_NAME_TITLE"]}}))' 2>/dev/null)
[ -n "$out" ] || exit 0
printf '%s\n' "$out"

# the prompt mode remembers what it printed (atomic), so the same title is not printed again
if [ -n "$PROMPT" ]; then
  { printf '%s\n' "$name" > "$marker.tmp.$$" && mv "$marker.tmp.$$" "$marker"; } 2>/dev/null || rm -f "$marker.tmp.$$"
fi

orca_rename "$name"
exit 0
