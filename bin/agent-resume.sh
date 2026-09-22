#!/usr/bin/env bash
# agent-resume.sh — resume the pipeline after a restart (rule S2).
#
#   ./agent-resume.sh              resume the pipeline
#   ./agent-resume.sh --dry-run    print the plan, launch nothing
#   ./agent-resume.sh -h           this help
#
# Relaunches a task manager for every worktree line that needs one, then
# starts the health monitor if it is not already running.
#
# Orca is not the only runtime (bin/agent-runtime.sh). In plain and cloud mode
# there are no terminals to relaunch into and nothing to sweep: the table
# still lists every worktree, in file order, but a row that would have been
# relaunched under Orca reads "no, plain mode" or "no, cloud mode" instead,
# and one line per such row prints after the table, naming what still needs
# to be started by hand with the Agent tool. "orca is not answering" is an
# Orca-mode fault message only: it is never printed in plain or cloud, where
# having no orca is the normal case.

set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
conf_read

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

# agent.conf lives in PROJECT_ROOT; the sibling scripts live in PLUGIN_ROOT/bin.
# The four agent_*.txt data files live in the main repo (ROOT), which can be a
# different place when this script runs from inside a worktree.
: "${max_usage_percent:=80}"
: "${task_manager:=opus-5:xhigh}"
: "${permission_mode:=auto}"
: "${max_agents:=4}"

. "$PLUGIN_ROOT/bin/agent-resources.sh"
. "$PLUGIN_ROOT/bin/agent-runtime.sh"

ROOT="$PROJECT_ROOT"
WT="$ROOT/agent_worktree.txt"
TODO="$ROOT/agent_todo.txt"
IDEAS="$ROOT/agent_ideas.txt"

KIND=$(runtime_kind)
# Pay for the probe (if any) once, then let every later runtime_ps /
# runtime_launch below reuse it instead of asking again per worktree. Unset
# again before handing off to agent-monitor.sh (below): its background loop
# lives for hours and must re-derive the kind on its own, sweep by sweep.
export RUNTIME_KIND="$KIND"

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

# ---- orca-only setup: live pane lookup, one runtime call. orca may be down. ----
orca_down=0
ps_tsv=""
total_live_panes=0
if [ "$KIND" = "orca" ]; then
  MODEL=$(model_name "$task_manager")
  EFFORT=${task_manager#*:}

  ps_out=$(runtime_ps 2>/dev/null) || orca_down=1
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
  if [ "$orca_down" -eq 0 ] && [ -n "$ps_tsv" ]; then
    total_live_panes=$(printf '%s\n' "$ps_tsv" | awk -F'\t' '$3!=1{sum+=$2} END{print sum+0}')
  fi
fi
relaunch_count=0
cap_lines=""
need_by_hand=""

live_pane() {
  path=$1
  match=$(printf '%s\n' "$ps_tsv" | awk -F'\t' -v p="$path" '$1==p{print; exit}')
  [ -n "$match" ] || return 1
  n=$(printf '%s' "$match" | cut -f2)
  [ "${n:-0}" -gt 0 ]
}

if [ "$KIND" = "orca" ] && [ "$orca_down" -eq 1 ]; then
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

    if [ "$KIND" = "orca" ]; then
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
        cmd="AGENT_ROLE=task-manager claude --model $MODEL --effort $EFFORT --permission-mode $permission_mode"
        if [ "$DRY_RUN" -eq 1 ]; then
          relaunched="would"
        else
          runtime_launch "$path" "TM $module" "$cmd" >/dev/null </dev/null
          relaunched="yes"
        fi
        relaunch_count=$((relaunch_count + 1))
      fi
    else
      # plain, cloud: no terminals. Same "is this worth relaunching" checks,
      # minus everything that needs a live orca (pane lookup, the cap).
      relaunched="no, status is idle"
      if [ ! -d "$path" ]; then
        relaunched="no, path is gone"
      elif [ "$status" != "working" ] && [ "$status" != "final" ]; then
        relaunched="no, status is idle"
      else
        relaunched="no, $KIND mode"
        need_by_hand="${need_by_hand}start by hand with the Agent tool: $path ($module)
"
      fi
    fi
    echo "$path | $status | $relaunched"
  done < "$WT"
fi
printf '%s' "$cap_lines"
printf '%s' "$need_by_hand"
echo

# The one-shot work above is done. Never let a child process (agent-monitor.sh
# below, whose background loop outlives this run by hours) inherit a kind
# pinned to this one moment.
unset RUNTIME_KIND

# ---- monitor handover ----
if [ "$KIND" = "orca" ]; then
  MON_PID_FILE="$PROJECT_GITDIR/agent_monitor.pid"
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
    out=$("$PLUGIN_ROOT/bin/agent-monitor.sh" start)
    echo "$out" | grep -E "^monitor:" || true
  fi
else
  echo "monitor: not used in $KIND mode"
fi
echo

# ---- counts ----
todo_n=0
[ -s "$TODO" ] && todo_n=$(grep -c . "$TODO" || true)
ideas_n=0
[ -s "$IDEAS" ] && ideas_n=$(grep -c . "$IDEAS" || true)
echo "todo: ${todo_n:-0} open"
echo "ideas: ${ideas_n:-0} waiting"
