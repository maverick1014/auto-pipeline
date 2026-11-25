#!/usr/bin/env bash
# agent-resume.sh — resume the pipeline after a restart (rule S2).
#
#   ./agent-resume.sh              resume the pipeline
#   ./agent-resume.sh --dry-run    print the plan, launch nothing
#   ./agent-resume.sh -h           this help
#
# Relaunches a task manager for every worktree line that needs one, then
# prints the watch line (agent-watch.sh --all) when no watch runs.
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

# The settings come from Configure (setting <key>); the sibling scripts live in PLUGIN_ROOT/bin.
# The four agent_*.txt data files live in the main repo (ROOT), which can be a
# different place when this script runs from inside a worktree.
max_usage_percent=$(setting max_usage_percent) || max_usage_percent=80
task_manager=$(setting task_manager) || task_manager=opus-5.5:high
permission_mode=$(setting permission_mode) || permission_mode=bypassPermissions
case "$max_usage_percent" in ''|*[!0-9]*) max_usage_percent=80;; esac

. "$PLUGIN_ROOT/bin/agent-resources.sh"
. "$PLUGIN_ROOT/bin/agent-runtime.sh"

ROOT="$PROJECT_ROOT"
WT="$ROOT/agent_worktree.txt"
TODO="$ROOT/agent_todo.txt"
IDEAS="$ROOT/agent_ideas.txt"

KIND=$(runtime_kind)
# Pay for the probe (if any) once, then let every later runtime_ps /
# runtime_launch below reuse it instead of asking again per worktree. Unset
# again after the one-shot work (below).
export AGENT_RUNTIME="$KIND"

# ---- cleanup sweep: main manager or takeover only, before agent_worktree.txt
# and the live panes are read, so a worktree the sweep removes is not a row
# below. The start hook already swept and says so with AGENT_CLEANUP_DONE=1.
# --dry-run lists, removes nothing. Its lines print last. A failing sweep never
# breaks the resume. ----
CLEAN_OUT=""
role_read
if { [ "$role" = main ] || [ "$role" = takeover ]; } && [ "${AGENT_CLEANUP_DONE:-}" != 1 ]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    CLEAN_OUT=$("$PLUGIN_ROOT/bin/agent-cleanup.sh" --short 2>/dev/null </dev/null) || true
  else
    CLEAN_OUT=$("$PLUGIN_ROOT/bin/agent-cleanup.sh" --apply --short 2>/dev/null </dev/null) || true
  fi
fi

# ---- resources line, one reading reused everywhere ----
resources_read
resources_line "$max_usage_percent"
echo

over_cap=0
if [ "$RAM_USED" -ge "$max_usage_percent" ] || [ "$CPU_USED" -ge "$max_usage_percent" ]; then over_cap=1; fi

# ---- model name: the one the claude CLI takes, cut down from opus-5.5:xhigh style ----
# The rule (family word for opus*, sonnet*, haiku*, fable*; anything else
# unchanged) lives in one place, bin/agent_conf.py cli-model, so the city page
# and this script cannot drift apart. If python3 cannot answer, fall back to
# the spec without its ":effort" part, so a relaunch still gets a --model word.
# The word may end in "[1m]" and the relaunch cmd is a line a zsh pane runs
# (opus[1m] is a glob there), so the word is quoted with printf %q: a plain
# name stays bare, a suffixed one reaches claude exactly as opus[1m].
model_name() {
  if ! name=$(python3 "$PLUGIN_ROOT/bin/agent_conf.py" cli-model "$1" 2>/dev/null); then
    spec=$1
    name="${spec%%:*}"
  fi
  printf '%q\n' "$name"
}

# ---- orca-only setup: live pane lookup, one runtime call. orca may be down. ----
orca_down=0
ps_tsv=""
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
    busy = 0
    for a in agents:
        state = a.get("state") if isinstance(a, dict) else a
        if state in ("working", "permission"):
            busy += 1
    print("%s\t%d\t%d\t%d" % (path, len(agents), is_main, busy))
')
  fi

  # No count cap (check-blocks section 25): column 2 (any agent at the path) is a live pane for
  # live_pane(); a done pane or a main manager pane still blocks a relaunch. Whether one more pane
  # fits is the memory rule below.
fi
# The memory rule: memory in use + live reservations + the panes planned in this run + one pane's need
# <= the Max memory % limit. "numbers" = "<used MB> <reserved MB> <limit MB> <pane MB>".
room_used=0; room_reserved=0; room_limit=0; room_pane=550; room_known=0
if room_nums=$(cd "$PROJECT_ROOT" && "$PLUGIN_ROOT/bin/agent-room.sh" numbers 2>/dev/null </dev/null); then
  set -- $room_nums
  if [ "$#" -eq 4 ]; then
    room_used=$1; room_reserved=$2; room_limit=$3; room_pane=$4; room_known=1
  fi
fi
room_planned=0
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
      elif [ "$room_known" -ne 1 ] || [ "$((room_used + room_reserved + room_planned + room_pane))" -gt "$room_limit" ]; then
        relaunched="no, no room"
        if [ "$room_known" -ne 1 ]; then
          cap_lines="${cap_lines}no room (memory unknown), not relaunching $path
"
        else
          cap_lines="${cap_lines}no room ($((room_used + room_reserved + room_planned)) MB + $room_pane MB > $room_limit MB), not relaunching $path
"
        fi
      else
        mode_eff="$permission_mode"
        cmd="AGENT_ROLE=task-manager claude --model $MODEL --effort $EFFORT --permission-mode $mode_eff"
        if [ "$DRY_RUN" -eq 1 ]; then
          relaunched="would"
        else
          launch_out=$(runtime_launch "$path" "TM $module" "$cmd" </dev/null) || launch_out=""
          # C7: the new pane is reserved until it measures itself (agent-room.sh measure-pane drops it)
          pane_handle=$(printf '%s' "$launch_out" | python3 -c '
import json, sys
def find(o):
    if isinstance(o, dict):
        if isinstance(o.get("handle"), str):
            return o["handle"]
        for v in o.values():
            h = find(v)
            if h:
                return h
    elif isinstance(o, list):
        for v in o:
            h = find(v)
            if h:
                return h
    return ""
try:
    print(find(json.load(sys.stdin)))
except Exception:
    print("")' 2>/dev/null) || pane_handle=""
          # no handle in the answer: a name of our own, so the pane still counts until the reservation expires
          [ -n "$pane_handle" ] || pane_handle="resume-$$-$relaunch_count"
          (cd "$PROJECT_ROOT" && "$PLUGIN_ROOT/bin/agent-room.sh" reserve-pane "$pane_handle" "$room_pane") >/dev/null 2>&1 </dev/null || true
          relaunched="yes"
        fi
        relaunch_count=$((relaunch_count + 1))
        room_planned=$((room_planned + room_pane))
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

# The one-shot work above is done. Never let a child process inherit a kind
# pinned to this one moment.
unset AGENT_RUNTIME

# ---- watch line (F1, F2): orca only; agent-start.sh prints it itself when it runs this script ----
if [ "$KIND" = "orca" ] && [ -z "${AGENT_WATCH_LINE_DONE:-}" ]; then
  watch_line=$(python3 "$PLUGIN_ROOT/bin/agent_watchfile.py" start-line "$ROOT" "$PLUGIN_ROOT" 2>/dev/null </dev/null) || watch_line=""
  if [ -n "$watch_line" ]; then
    echo "$watch_line"
    echo
  fi
fi

# ---- counts ----
todo_n=0
[ -s "$TODO" ] && todo_n=$(grep -c . "$TODO" || true)
ideas_n=0
[ -s "$IDEAS" ] && ideas_n=$(grep -c . "$IDEAS" || true)
echo "todo: ${todo_n:-0} open"
echo "ideas: ${ideas_n:-0} waiting"
[ -z "$CLEAN_OUT" ] || printf '%s\n' "$CLEAN_OUT"
