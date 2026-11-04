#!/usr/bin/env bash
# agent-watch.sh — watch one task manager (TM) on two signals: its Orca pane AND
# its worktree's agent_state.txt. The main manager starts it in the background
# (run_in_background) and is woken when it exits.
#
#   bin/agent-watch.sh --terminal <TM handle> --worktree <path>
#                      [--environment <env> --shell <shell handle>]
#                      [--interval-min 5] [--max 36] [--name <task>]
#
# --environment: the TM runs on another machine; agent_state.txt is then read
# through the --shell pane (one short command, answer read back with --cursor).
# Only file lines fire. The screen feeds the stall and the sweep line, nothing else.
# The TM pane is only ever read, never sent to.
#
# Exits (all code 0, the WATCH line first, then the evidence):
#   WATCH SIGNAL <name>: <line>   a new file line: DONE PASS/FAIL, CLOSE CASE,
#                                 QUESTION: or MOCK READY (then the last 15
#                                 screen lines)
#   WATCH STALL <name>            3 sweeps, same screen, file unchanged
#   WATCH LOST <name>             3 failed reads in a row
#   WATCH MAX <name>              --max sweeps done
# plain or cloud runtime: prints "watch: not used in <kind> mode", exit 0.
# Missing --terminal/--worktree, or --environment without --shell: usage, exit 2.
#
# Env: AGENT_WATCH_INTERVAL_S  seconds between sweeps; wins over --interval-min.

export PYTHONIOENCODING=utf-8

usage() {
  echo "usage: agent-watch.sh --terminal <TM handle> --worktree <path> [--environment <env> --shell <shell handle>] [--interval-min 5] [--max 36] [--name <task>]"
  [ -n "$1" ] && echo "agent-watch.sh: $1"
  exit 2
}

T=""; W=""; ENVNAME=""; SH=""; MIN=5; MAX=36; NAME=""
while [ $# -gt 0 ]; do
  case "$1" in
    --terminal) T=$2; shift 2 || usage "--terminal needs a value" ;;
    --worktree) W=$2; shift 2 || usage "--worktree needs a value" ;;
    --environment) ENVNAME=$2; shift 2 || usage "--environment needs a value" ;;
    --shell) SH=$2; shift 2 || usage "--shell needs a value" ;;
    --interval-min) MIN=$2; shift 2 || usage "--interval-min needs a value" ;;
    --max) MAX=$2; shift 2 || usage "--max needs a value" ;;
    --name) NAME=$2; shift 2 || usage "--name needs a value" ;;
    -h|--help) usage "" ;;
    *) usage "unknown argument: $1" ;;
  esac
done

KIND=$("$(dirname "$0")/agent-runtime.sh" kind 2>/dev/null)
case "$KIND" in
  plain|cloud) echo "watch: not used in $KIND mode"; exit 0 ;;
esac

[ -n "$T" ] || usage "missing --terminal"
[ -n "$W" ] || usage "missing --worktree"
if [ -n "$ENVNAME" ] && [ -z "$SH" ]; then usage "--environment needs --shell <shell handle>"; fi
case "$MAX" in ''|*[!0-9]*) usage "--max must be a number" ;; esac
[ -n "$NAME" ] || NAME=$(basename "$W")

if [ -n "${AGENT_WATCH_INTERVAL_S:-}" ]; then
  IV=$AGENT_WATCH_INTERVAL_S
else
  IV=$(awk -v m="$MIN" 'BEGIN{print m*60}')
fi

E=()
[ -n "$ENVNAME" ] && E=(--environment "$ENVNAME")
ERRF=$(mktemp "${TMPDIR:-/tmp}/agent-watch.XXXXXX")
trap 'rm -f "$ERRF"' EXIT

RE='^(DONE (PASS|FAIL)|CLOSE CASE|QUESTION:|MOCK READY)'
LASTERR=""

# JSON from orca on stdin -> the tail lines (or the cursor with "cursor"); fails
# when there is no result.terminal.
json_part() {
  python3 -c '
import json, sys
t = json.load(sys.stdin)["result"]["terminal"]
if sys.argv[1] == "cursor":
    sys.stdout.write(str(t.get("latestCursor") or ""))
else:
    sys.stdout.write("\n".join(str(x) for x in (t.get("tail") or [])))
' "$1" 2>/dev/null
}

# LASTERR from a failed orca call: error.code/message from the JSON on stdout
# ($1), else stderr, else "<what> exit <rc>"
orca_error() {
  local msg
  msg=$(printf '%s' "$1" | python3 -c '
import json, sys
e = json.load(sys.stdin).get("error") or {}
sys.stdout.write(str(e.get("code") or e.get("message") or ""))' 2>/dev/null)
  [ -n "$msg" ] || msg=$(head -c 300 "$ERRF" | tr '\n' ' ')
  [ -n "$msg" ] || msg="$2 exit $3"
  LASTERR=$msg
}

# orca terminal read <handle> [cursor] -> RAW; sets LASTERR on failure
orca_read() {
  local rc
  if [ -n "$2" ]; then
    RAW=$(orca terminal read "${E[@]}" --terminal "$1" --cursor "$2" --json 2>"$ERRF"); rc=$?
  else
    RAW=$(orca terminal read "${E[@]}" --terminal "$1" --json 2>"$ERRF"); rc=$?
  fi
  if [ $rc -ne 0 ]; then
    orca_error "$RAW" "orca terminal read" "$rc"
    return 1
  fi
  return 0
}

tm_read() {
  orca_read "$T" "" || return 1
  SCREEN=$(printf '%s' "$RAW" | json_part tail) || { LASTERR="no result.terminal in the TM pane read"; return 1; }
  return 0
}

# sets FN (signal count), FL (line count), FLAST (last signal line)
file_read() {
  local f q cmd cur body rest k mark rc
  if [ -z "$ENVNAME" ]; then
    f="$W/agent_state.txt"
    [ -r "$f" ] || { LASTERR="cannot read $f"; return 1; }
    FN=$(grep -cE "$RE" "$f")
    FL=$(wc -l <"$f" | tr -d ' ')
    FLAST=$(grep -E "$RE" "$f" | tail -1)
    return 0
  fi
  orca_read "$SH" "" || return 1
  cur=$(printf '%s' "$RAW" | json_part cursor)
  [ -n "$cur" ] || { LASTERR="no latestCursor in the shell pane read"; return 1; }
  q=$(printf '%s' "$W/agent_state.txt" | sed "s/'/'\\\\''/g")
  cmd="f='$q'; R='$RE'; echo FSIG \$(grep -cE \"\$R\" \"\$f\") \$(wc -l <\"\$f\") \"\$(grep -E \"\$R\" \"\$f\"|tail -1|cut -c1-100)\" FEND"
  RAW=$(orca terminal send "${E[@]}" --terminal "$SH" --text "$cmd" --enter --json 2>"$ERRF"); rc=$?
  if [ $rc -ne 0 ]; then
    orca_error "$RAW" "orca terminal send" "$rc"
    return 1
  fi
  mark=""
  for k in $(seq 1 20); do
    if orca_read "$SH" "$cur"; then
      mark=$(printf '%s' "$RAW" | json_part tail | tr -d '\r' | grep -E '^FSIG [0-9]+ [0-9]+ .*FEND$' | tail -1)
      [ -n "$mark" ] && break
    else
      return 1
    fi
    sleep 0.5
  done
  [ -n "$mark" ] || { LASTERR="no FSIG marker line in the shell pane"; return 1; }
  body=${mark#FSIG }; body=${body% FEND}
  FN=${body%% *}; rest=${body#* }
  FL=${rest%% *}; FLAST=${rest#* }
  [ "$FLAST" = "$rest" ] && FLAST=""
  return 0
}

last15() { printf '%s\n' "$SCREEN" | tail -15; }

# ---- baselines ----
BASE_N=""
PREV_OK=0; PREV_SCREEN=""; PREV_N=""; PREV_L=""
if file_read; then BASE_N=$FN; PREV_N=$FN; PREV_L=$FL; fi
if tm_read; then PREV_OK=1; PREV_SCREEN=$SCREEN; fi
echo "$(date '+%H:%M') watch $NAME: start, file signals already there: ${BASE_N:-unknown}"

same=0; fails=0
i=1
while [ "$i" -le "$MAX" ]; do
  i=$((i+1))
  sleep "$IV"
  now=$(date '+%H:%M')
  if ! { tm_read && file_read; }; then
    fails=$((fails+1))
    echo "$now read failed ($fails of 3): $LASTERR"
    if [ "$fails" -ge 3 ]; then
      echo "WATCH LOST $NAME"
      echo "$LASTERR"
      exit 0
    fi
    continue
  fi
  fails=0

  # baselines that could not be read at the start: this read is the baseline
  if [ -z "$BASE_N" ]; then BASE_N=$FN; fi

  if [ "$FN" -gt "$BASE_N" ] 2>/dev/null; then
    echo "WATCH SIGNAL $NAME: $FLAST"
    last15
    exit 0
  fi

  if [ "$PREV_OK" -eq 1 ] && [ "$SCREEN" = "$PREV_SCREEN" ] && [ "$FN" = "$PREV_N" ] && [ "$FL" = "$PREV_L" ]; then
    same=$((same+1))
  else
    same=0
  fi
  case "$SCREEN" in *"shell still running"*) same=0 ;; esac
  PREV_OK=1; PREV_SCREEN=$SCREEN; PREV_N=$FN; PREV_L=$FL

  tail1=$(printf '%s\n' "$SCREEN" | grep -E '⏺|✻' | tail -1 | python3 -c '
import sys
sys.stdout.write(sys.stdin.read().rstrip("\n")[:110])' 2>/dev/null)
  echo "$now same=$same file=$FN | $tail1"
  if [ "$same" -ge 3 ]; then
    echo "WATCH STALL $NAME"
    last15
    exit 0
  fi
done

echo "WATCH MAX $NAME"
exit 0
