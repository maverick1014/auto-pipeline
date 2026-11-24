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
STEP=1; CHILD=""
trap '[ -n "$CHILD" ] && kill "$CHILD" 2>/dev/null; rm -f "$PIDF" "$TMPO"' EXIT
trap 'trap - TERM INT HUP; [ -n "$CHILD" ] && kill "$CHILD" 2>/dev/null; add "AUTO CLEAR failed at step $STEP: stopped by a signal"; exit 143' TERM INT HUP

# bg_out <file> <cmd...>: run in the background and wait, so a signal trap runs at once; rc = the command's
TMPO="${TMPDIR:-/tmp}/agent_autoclear_$$.out"
bg() {
  "$@" >"$TMPO" 2>&1 </dev/null &
  CHILD=$!
  wait "$CHILD"; local rc=$?
  CHILD=""
  OUT=$(cat "$TMPO" 2>/dev/null); rm -f "$TMPO"
  return $rc
}

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
for i, l in enumerate(t):
    if l.startswith("\u276f"):
        last = i
if last is None:
    print("none")
elif last == 0 or last + 1 >= len(t) or not t[last - 1].startswith("\u2500") or not t[last + 1].startswith("\u2500"):
    print("text")
else:
    print("empty" if t[last][1:].replace("\u00a0", " ").strip() == "" else "text")
' 2>/dev/null
}

fail() { add "AUTO CLEAR failed at step $1: $2"; exit 1; }

warned=0
# ready <step>: wait for idle, check the box is empty; returns only when typing is allowed
ready() {
  local out rc code st
  STEP=$1
  while :; do
    bg orca terminal wait --terminal "$H" --for tui-idle --json; rc=$?; out=$OUT
    if [ $rc -ne 0 ]; then
      code=$(printf '%s' "$out" | errcode)
      case "$code" in *timeout*) continue;; esac
      fail "$1" "$code"
    fi
    while :; do
      bg orca terminal read --terminal "$H" --json; rc=$?; out=$OUT
      [ $rc -eq 0 ] || fail "$1" "$(printf '%s' "$out" | errcode)"
      st=$(printf '%s' "$out" | box_state)
      case "$st" in
        empty) return 0;;
        ERR) fail "$1" "bad_read";;
      esac
      if [ "$warned" = 0 ]; then add "AUTO CLEAR waiting: input box not empty"; warned=1; fi
      bg sleep "$check_sec"
      # the pane may have changed state: wait for idle again before the next read
      continue 2
    done
  done
}

type_text() {
  local out
  STEP=$1
  bg orca terminal send --terminal "$H" --text "$2" --enter || fail "$1" "$(printf '%s' "$OUT" | errcode)"
  # tui-idle can come back before the pane went busy: let the turn start first
  bg sleep "$check_sec"
}

read_goal() {
  goal=""
  if [ -f "$SF" ]; then
    goal=$(grep '^GOAL: ' "$SF" | tail -n 1)
    goal=${goal#GOAL: }
    # one trailing " | YYYY-MM-DD HH:MM" stamp (state add) is not part of the goal
    if [[ "$goal" =~ ^(.*)\ \|\ [0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}$ ]]; then goal=${BASH_REMATCH[1]}; fi
  fi
}

ready 1
type_text 2 "AUTO CLEAR: save agent_state.txt now (S8), nothing else. /clear comes next."
ready 3
type_text 4 "/clear"
ready 5
read_goal
if [ -n "$goal" ]; then type_text 6 "/goal $goal"; else type_text 6 "CLEARED: continue from agent_state.txt (S8)."; fi
add "AUTO CLEAR done"
exit 0
