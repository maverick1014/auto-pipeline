#!/usr/bin/env bash
# agent-resume.sh — resume the pipeline after a restart (rule S2).
#
#   ./agent-resume.sh              resume the pipeline
#   ./agent-resume.sh --dry-run    print the plan, launch nothing
#   ./agent-resume.sh -h           this help
#
# Relaunches a task manager for every worktree line that needs one, then
# starts the health monitor if it is not already running.

set -eu
cd "$(dirname "$0")"

usage() {
  cat <<'EOF'
agent-resume.sh — resume the pipeline after a restart.

  ./agent-resume.sh              resume the pipeline
  ./agent-resume.sh --dry-run    print the plan, launch nothing
  ./agent-resume.sh -h           this help
EOF
}

DRY_RUN=0
case "${1:-}" in
  -h|--help) usage; exit 0;;
  --dry-run) DRY_RUN=1;;
  "") ;;
  *) usage; exit 2;;
esac

# agent.conf and the sibling scripts live next to this script. The four
# agent_*.txt data files live in the main repo (ROOT), which can be a
# different place when this script runs from inside a worktree.
[ -f ./agent.conf ] && . ./agent.conf
: "${max_usage_percent:=80}"
: "${task_manager:=opus-5:xhigh}"
: "${permission_mode:=auto}"
: "${max_agents:=4}"

. ./agent-resources.sh

ROOT=$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2; exit}'); : "${ROOT:=$PWD}"
WT="$ROOT/agent_worktree.txt"
TODO="$ROOT/agent_todo.txt"
IDEAS="$ROOT/agent_ideas.txt"

# ---- resources line, one reading reused everywhere ----
resources_read
resources_line "$max_usage_percent"
echo

over_cap=0
if [ "$RAM_USED" -ge "$max_usage_percent" ] || [ "$CPU_USED" -ge "$max_usage_percent" ]; then over_cap=1; fi

# ---- model name: family word only, cut down from opus-5:xhigh style ----
model_name() {
  spec=$1
  base=${spec%%:*}
  case "$base" in
    opus*)   echo opus;;
    sonnet*) echo sonnet;;
    haiku*)  echo haiku;;
    fable*)  echo fable;;
    *)       echo "$base";;
  esac
}
MODEL=$(model_name "$task_manager")

# ---- live pane lookup, one orca call. orca may not be running. ----
orca_down=0
ps_out=$(orca worktree ps --json 2>/dev/null) || orca_down=1
ps_tsv=""
if [ "$orca_down" -eq 0 ]; then
  ps_tsv=$(printf '%s' "$ps_out" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for w in data.get("result", {}).get("worktrees", []):
    path = w.get("path", "")
    agents = w.get("agents") or []
    is_main = 1 if w.get("isMainWorktree") else 0
    print("%s\t%d\t%d" % (path, len(agents), is_main))
')
fi

# The cap counts spawned agents, not main managers (rule S6). A main
# manager pane is still a live pane, so live_pane() must still see it;
# it just does not fill a cap slot.
total_live_panes=0
if [ "$orca_down" -eq 0 ] && [ -n "$ps_tsv" ]; then
  total_live_panes=$(printf '%s\n' "$ps_tsv" | awk -F'\t' '$3!=1{sum+=$2} END{print sum+0}')
fi
relaunch_count=0
cap_lines=""

live_pane() {
  path=$1
  match=$(printf '%s\n' "$ps_tsv" | awk -F'\t' -v p="$path" '$1==p{print; exit}')
  [ -n "$match" ] || return 1
  n=$(printf '%s' "$match" | cut -f2)
  [ "${n:-0}" -gt 0 ]
}

if [ "$orca_down" -eq 1 ]; then
  echo "orca is not answering"
  echo
fi

echo "=== resume ==="
echo "worktree | status | relaunched"
if [ ! -s "$WT" ]; then
  echo "(no live worktrees)"
else
  while IFS= read -r line || [ -n "$line" ]; do
    [ -z "$line" ] && continue
    path=$(printf '%s' "$line" | awk -F' \\| ' '{print $1}')
    module=$(printf '%s' "$line" | awk -F' \\| ' '{print $2}')
    status=$(printf '%s' "$line" | awk -F' \\| ' '{print $3}')

    relaunched="no, status is idle"
    if [ ! -d "$path" ]; then
      relaunched="no, path is gone"
    elif [ "$status" != "working" ] && [ "$status" != "final" ]; then
      relaunched="no, status is idle"
    elif [ "$orca_down" -eq 1 ]; then
      relaunched="no, orca is down"
    elif live_pane "$path"; then
      relaunched="no, pane is live"
    elif [ "$over_cap" -eq 1 ]; then
      relaunched="no, over cap"
    elif [ "$((total_live_panes + relaunch_count))" -ge "$max_agents" ]; then
      relaunched="no, cap reached"
      cap_lines="${cap_lines}cap reached ($((total_live_panes + relaunch_count))/$max_agents), not relaunching $path
"
    else
      cmd="AGENT_ROLE=task-manager claude --model $MODEL --permission-mode $permission_mode"
      if [ "$DRY_RUN" -eq 1 ]; then
        relaunched="would"
      else
        orca terminal create \
          --worktree "path:$path" \
          --title "TM $module" \
          --command "$cmd" \
          --json >/dev/null </dev/null
        relaunched="yes"
      fi
      relaunch_count=$((relaunch_count + 1))
    fi
    echo "$path | $status | $relaunched"
  done < "$WT"
fi
printf '%s' "$cap_lines"
echo

# ---- monitor handover ----
GITDIR=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || git rev-parse --git-common-dir 2>/dev/null || echo .git)
MON_PID_FILE="$GITDIR/agent_monitor.pid"
monitor_running=0
if [ -f "$MON_PID_FILE" ]; then
  mpid=$(awk '{print $1}' "$MON_PID_FILE" 2>/dev/null || true)
  [ -n "$mpid" ] && kill -0 "$mpid" 2>/dev/null && monitor_running=1
fi
if [ "$monitor_running" -eq 1 ]; then
  echo "monitor: already running (pid $mpid)"
elif [ "$DRY_RUN" -eq 1 ]; then
  echo "monitor: would start"
else
  out=$(./agent-monitor.sh start)
  echo "$out" | grep -E "^monitor:" || true
fi
echo

# ---- counts ----
todo_n=0
[ -s "$TODO" ] && todo_n=$(grep -c . "$TODO" || true)
ideas_n=0
[ -s "$IDEAS" ] && ideas_n=$(grep -c . "$IDEAS" || true)
echo "todo: ${todo_n:-0} open"
echo "ideas: ${ideas_n:-0} waiting"
