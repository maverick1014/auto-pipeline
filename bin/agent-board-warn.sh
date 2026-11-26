#!/usr/bin/env bash
# agent-board-warn.sh — UserPromptSubmit and PostToolUse hook: the board's warnings (watch not running, a task
# not confirmed, a pane without a task line) reach the main manager's context, so it acts with no human.
# Main manager only (role main, AGENT_ROLE unset). Prints the WARN set when it is new or changed since the last
# print and at least one minute after it; state: $PROJECT_GITDIR/agent_warn_seen.json.
# UserPromptSubmit: plain lines; PostToolUse: the hookSpecificOutput JSON.
# Same lines as `agent-file.sh next` (agent_board.board_warnings). No orca, no git log. Always exit 0, no stderr.
set -u
[ -z "${AGENT_ROLE:-}" ] || exit 0
[ -t 0 ] && exit 0
IN=$(cat 2>/dev/null) || IN=""
. "$(dirname "$0")/agent-roots.sh" 2>/dev/null || exit 0

{
  eval "$(printf '%s' "$IN" | python3 -c 'import json,sys,shlex
try:
    d=json.load(sys.stdin)
    print("EVENT=%s; HCWD=%s; SUB=%s" % (shlex.quote(str(d.get("hook_event_name",""))), shlex.quote(str(d.get("cwd",""))), "1" if d.get("agent_id") else ""))
except Exception: print("EVENT=; HCWD=; SUB=")' 2>/dev/null)"
  [ -z "$SUB" ] || exit 0
  roots_read "$HCWD"
  repo_set_up || exit 0
  role_read
  [ "$role" = main ] || exit 0
  NOW="${AGENT_FAKE_NOW:-$(date '+%Y-%m-%d %H:%M')}"
  PYTHONPATH="$PLUGIN_ROOT/bin" python3 - "$PROJECT_ROOT" "$PLUGIN_ROOT" "$NOW" "$PROJECT_GITDIR/agent_warn_seen.json" "$EVENT" <<'PY'
import json, os, sys

root, plugin, now, state, event = sys.argv[1:6]
try:
    with open(state) as fh:
        seen = json.load(fh)
    if not isinstance(seen, dict):
        seen = {}
except (IOError, ValueError):
    seen = {}
if seen.get("checked") == now:      # the board is built at most once a minute: leave before importing it
    sys.exit(0)


def save(data):
    data["checked"] = now
    tmp = "%s.tmp.%d" % (state, os.getpid())
    with open(tmp, "w") as fh:
        json.dump(data, fh)
    os.replace(tmp, state)


import agent_board as b
lines = b.board_warnings(root, plugin, now)
if not lines:
    save({"set": [], "at": seen.get("at", "")} if seen.get("set") else dict(seen))
    sys.exit(0)


def keys(ls):
    import re
    return sorted(re.sub(r" \(\d+m\)(?= ->)", "", x) for x in ls or [] if isinstance(x, str))


if keys(lines) == keys(seen.get("set")):
    save(dict(seen))
    sys.exit(0)
last = b.parse_time(seen.get("at")) if isinstance(seen.get("at"), str) else None
if last is not None:
    gap = b.minutes(last, b.parse_time(now))
    if gap is not None and gap < 1:
        save(dict(seen))
        sys.exit(0)
save({"set": lines, "at": now})
text = "Board warning for the main manager, act in this turn:\n" + "\n".join(lines)
if event == "PostToolUse":
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}))
else:
    print(text)
PY
} 2>/dev/null
exit 0
