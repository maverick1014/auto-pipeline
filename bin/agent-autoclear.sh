#!/usr/bin/env bash
# agent-autoclear.sh — the waiter behind the auto /clear (state-trim A5). Started detached by
# agent-start.sh at the compaction named by compact_clear_at; runs in the foreground itself.
#
#   agent-autoclear.sh <terminal handle> <session id>
#
# Writes its pid to <git dir>/agent_autoclear_<session id> and removes it when it ends.
# Before each typed text: `orca terminal wait --for tui-idle` (an error whose code holds
# "timeout": wait again; any other error: failed), then `orca terminal read --json`: the last
# tail line starting with the prompt mark must be empty after the mark; else wait
# compact_clear_check_sec and check again (one "AUTO CLEAR waiting" line in agent_state.txt).
# Types: 2 the save prompt, 4 /clear, 6 "/goal <last GOAL: line>" or the continue prompt.
# Appends "AUTO CLEAR done | <date>" or "AUTO CLEAR failed at step <n>: <code> | <date>".
# AGENT_FAKE_NOW="YYYY-MM-DD HH:MM" replaces the clock (tests). Missing arguments: usage, exit 2.

set -u
if [ $# -lt 2 ] || [ -z "$1" ] || [ -z "$2" ]; then
  echo "usage: agent-autoclear.sh <terminal handle> <session id>" >&2; exit 2
fi
. "$(dirname "$0")/agent-roots.sh"
H=$1; SID=$2
roots_read "$PWD"

PIDF="$PROJECT_GITDIR/agent_autoclear_$SID"
SF="$STATE_DIR/agent_state.txt"
mkdir -p "$PROJECT_GITDIR" 2>/dev/null || true
echo "$$" > "$PIDF"
trap 'rm -f "$PIDF"' EXIT
trap 'exit 143' TERM INT HUP

now() { echo "${AGENT_FAKE_NOW:-$(date '+%Y-%m-%d %H:%M')}"; }
add() {
  { [ -s "$SF" ] && [ -n "$(tail -c1 "$SF")" ] && echo
    printf '%s | %s\n' "$1" "$(now)"; } >> "$SF"
}

check_sec=$(awk -F= '$1 == "compact_clear_check_sec" { v = $2 } END { print v }' "$PROJECT_ROOT/agent.conf" 2>/dev/null | tr -d '[:space:]')
case "$check_sec" in ''|*[!0-9]*)
  check_sec=$(awk -F= '$1 == "compact_clear_check_sec" { v = $2 } END { print v }' "$PLUGIN_ROOT/bin/agent.conf.default" 2>/dev/null | tr -d '[:space:]');;
esac
case "$check_sec" in ''|*[!0-9]*) check_sec=30;; esac

# error code of an orca JSON answer on stdin: result.. error.code, else the text
errcode() {
  python3 -c '
import json, sys
raw = sys.stdin.read()
try:
    e = json.loads(raw).get("error")
    c = e.get("code") if isinstance(e, dict) else e
    print(c or "error")
except Exception:
    print((raw.strip().splitlines() or ["error"])[0][:60])
' 2>/dev/null || echo error
}

# box_state: prints empty | text | none for the last "❯" line of the pane tail; rc 1 = read failed
box_state() {
  python3 -c '
import json, sys
try:
    d = json.loads(sys.stdin.read())
    t = d["result"]["terminal"]["tail"]
except Exception:
    print("ERR"); sys.exit(0)
if isinstance(t, str):
    t = t.split("\n")
last = None
for l in t:
    if l.startswith("❯"):
        last = l
if last is None:
    print("none")
else:
    print("empty" if last[1:].replace(" ", " ").strip() == "" else "text")
' 2>/dev/null
}

fail() { add "AUTO CLEAR failed at step $1: $2"; exit 1; }

warned=0
# ready <step>: wait for idle, check the box is empty; returns only when typing is allowed
ready() {
  local out rc code st
  while :; do
    out=$(orca terminal wait --terminal "$H" --for tui-idle --json 2>&1 </dev/null); rc=$?
    if [ $rc -ne 0 ]; then
      code=$(printf '%s' "$out" | errcode)
      case "$code" in *timeout*) continue;; esac
      fail "$1" "$code"
    fi
    while :; do
      out=$(orca terminal read --terminal "$H" --json 2>&1 </dev/null); rc=$?
      [ $rc -eq 0 ] || fail "$1" "$(printf '%s' "$out" | errcode)"
      st=$(printf '%s' "$out" | box_state)
      case "$st" in
        empty) return 0;;
        ERR) fail "$1" "bad_read";;
      esac
      if [ "$warned" = 0 ]; then add "AUTO CLEAR waiting: input box not empty"; warned=1; fi
      sleep "$check_sec"
      # the pane may have changed state: wait for idle again before the next read
      continue 2
    done
  done
}

type_text() {
  local out
  out=$(orca terminal send --terminal "$H" --text "$2" --enter 2>&1 </dev/null) || fail "$1" "$(printf '%s' "$out" | errcode)"
}

goal=""
if [ -f "$SF" ]; then
  goal=$(grep '^GOAL: ' "$SF" | tail -n 1)
  goal=${goal#GOAL: }
  # one trailing " | YYYY-MM-DD HH:MM" stamp (state add) is not part of the goal
  if [[ "$goal" =~ ^(.*)\ \|\ [0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}$ ]]; then goal=${BASH_REMATCH[1]}; fi
fi

ready 1
type_text 2 "AUTO CLEAR: save agent_state.txt now (S8), nothing else. /clear comes next."
ready 3
type_text 4 "/clear"
ready 5
if [ -n "$goal" ]; then type_text 6 "/goal $goal"; else type_text 6 "CLEARED: continue from agent_state.txt (S8)."; fi
add "AUTO CLEAR done"
exit 0
