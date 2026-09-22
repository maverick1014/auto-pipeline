#!/usr/bin/env bash
# agent-monitor.sh — background health sweep of live worktrees (rule S1).
#
#   ./agent-monitor.sh start    start the background loop
#   ./agent-monitor.sh stop     stop it
#   ./agent-monitor.sh status   pid and the time of the last sweep
#   ./agent-monitor.sh once     one sweep, then print the file
#   ./agent-monitor.sh -h       this help
#
# One sweep reads agent_worktree.txt (main repo) and writes agent_monitor.txt
# (main repo), one line per worktree line, written atomically (tmp + mv).

set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
conf_read

usage() {
  cat <<'EOF'
agent-monitor.sh — background health sweep of live worktrees.

  ./agent-monitor.sh start    start the background loop
  ./agent-monitor.sh stop     stop it
  ./agent-monitor.sh status   pid and the time of the last sweep
  ./agent-monitor.sh once     one sweep, then print the file
  ./agent-monitor.sh -h       this help
EOF
}

GITDIR="$PROJECT_GITDIR"
ROOT="$PROJECT_ROOT"
mkdir -p "$GITDIR" 2>/dev/null || true
: "${stall_min:=10}"
: "${monitor_interval_min:=5}"

PIDFILE="$GITDIR/agent_monitor.pid"
LASTSWEEP="$GITDIR/agent_monitor.lastsweep"
WT="$ROOT/agent_worktree.txt"
MON="$ROOT/agent_monitor.txt"

running() {
  [ -f "$PIDFILE" ] || return 1
  pid=$(awk '{print $1}' "$PIDFILE" 2>/dev/null || true)
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

sweep() {
  ts=$(date '+%Y-%m-%d %H:%M')
  tmp="$ROOT/agent_monitor.txt.tmp.$$"
  : > "$tmp"
  if [ -s "$WT" ]; then
    ps_tsv=""
    if ps_out=$(orca worktree ps --json 2>/dev/null); then
      ps_tsv=$(printf '%s' "$ps_out" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for w in data.get("result", {}).get("worktrees", []):
    path = w.get("path", "")
    agents = w.get("agents") or []
    state = agents[0].get("state") if agents else None
    lo = w.get("lastActivityAt")
    print("%s\t%s\t%s" % (path, state if state else "none", lo if lo is not None else ""))
')
    else
      echo "orca is not answering"
    fi
    now_ms=$(python3 -c 'import time; print(int(time.time()*1000))')
    now_epoch=$(date +%s)
    while IFS= read -r line || [ -n "$line" ]; do
      [ -z "$line" ] && continue
      path=$(printf '%s' "$line" | awk -F' \\| ' '{print $1}')
      module=$(printf '%s' "$line" | awk -F' \\| ' '{print $2}')

      match=$(printf '%s\n' "$ps_tsv" | awk -F'\t' -v p="$path" '$1==p{print; exit}')
      if [ -n "$match" ]; then
        pane=$(printf '%s' "$match" | cut -f2)
        lo=$(printf '%s' "$match" | cut -f3)
      else
        pane="none"; lo=""
      fi

      if [ -n "$lo" ]; then
        out_min=$(( (now_ms - lo) / 60000 ))
        out_disp="${out_min}m ago"
      else
        out_disp="none"
      fi

      ct=""
      if [ -d "$path" ]; then
        toplevel=$(git -C "$path" rev-parse --show-toplevel 2>/dev/null) || toplevel=""
        real_path=$(cd "$path" && pwd -P)
        if [ -n "$toplevel" ] && [ "$toplevel" = "$real_path" ]; then
          ct=$(git -C "$path" log -1 --format=%ct 2>/dev/null) || ct=""
        fi
      fi
      if [ -n "$ct" ]; then
        commit_min=$(( (now_epoch - ct) / 60 ))
        commit_disp="${commit_min}m ago"
      else
        commit_disp="none"
      fi

      verdict="STALL"
      [ "$pane" = "working" ] && verdict="OK"
      if [ "$verdict" = "STALL" ] && [ -n "$ct" ] && [ "$commit_min" -lt "$stall_min" ]; then verdict="OK"; fi
      if [ "$verdict" = "STALL" ] && [ -n "$lo" ] && [ "$out_min" -lt "$stall_min" ]; then verdict="OK"; fi

      printf '%s | %s | pane %s | commit %s | activity %s | %s | %s\n' \
        "$path" "$module" "$pane" "$commit_disp" "$out_disp" "$verdict" "$ts" >> "$tmp"
    done < "$WT"
  fi
  mv "$tmp" "$MON"
  echo "$ts" > "$LASTSWEEP"
}

do_once() {
  sweep
  if [ -s "$MON" ]; then
    cat "$MON"
  else
    echo "(no live worktrees)"
  fi
}

do_start() {
  if running; then
    pid=$(awk '{print $1}' "$PIDFILE")
    echo "monitor: already running (pid $pid)"
    return 0
  fi
  sweep
  (
    trap 'rm -f "$PIDFILE"; exit 0' TERM
    while true; do
      sleep "$((monitor_interval_min * 60))" &
      wait $! 2>/dev/null || true
      sweep
    done
  ) >/dev/null 2>&1 </dev/null &
  pid=$!
  disown "$pid" 2>/dev/null || true
  echo "$pid" > "$PIDFILE"
  echo "monitor: started (pid $pid)"
  echo "sweeping every $monitor_interval_min minutes"
}

do_stop() {
  if running; then
    pid=$(awk '{print $1}' "$PIDFILE")
    kill -TERM "$pid" 2>/dev/null || true
    rm -f "$PIDFILE"
    echo "monitor: stopped"
  else
    rm -f "$PIDFILE" 2>/dev/null || true
    echo "monitor: not running"
  fi
}

do_status() {
  if running; then
    pid=$(awk '{print $1}' "$PIDFILE")
    echo "monitor: running (pid $pid)"
  else
    echo "monitor: not running"
  fi
  if [ -f "$LASTSWEEP" ]; then
    echo "last sweep: $(cat "$LASTSWEEP")"
  else
    echo "last sweep: (none)"
  fi
}

[ $# -eq 0 ] && { usage; exit 2; }
case "$1" in
  -h|--help) usage; exit 0;;
  once) do_once;;
  start) do_start;;
  stop) do_stop;;
  status) do_status;;
  *) usage; exit 2;;
esac
