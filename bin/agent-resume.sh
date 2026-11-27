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
case "$0" in */*) _res_dir=${0%/*}; [ -n "$_res_dir" ] || _res_dir=/;; *) _res_dir=.;; esac
. "$_res_dir/agent-roots.sh"
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
# One python3 start for all four values (runtime is read by runtime_kind below).
settings_read max_usage_percent task_manager permission_mode runtime
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

# ---- model name, live panes, room numbers: ONE python3 start (agent_nightly.py resume-prep) ----
# The model word is the one the claude CLI takes, cut down from opus-5.5:xhigh style: the rule
# (family word for opus*, sonnet*, haiku*, fable*; anything else unchanged) lives in one place,
# bin/agent_conf.py cli_model, so the city page and this script cannot drift apart. If python3
# cannot answer, fall back to the spec without its ":effort" part, so a relaunch still gets a
# --model word. The word may end in "[1m]" and the relaunch cmd is a line a zsh pane runs
# (opus[1m] is a glob there), so the word is quoted with printf %q: a plain name stays bare, a
# suffixed one reaches claude exactly as opus[1m].
# The live pane lookup is one runtime call (orca may be down). The memory rule: memory in use +
# live reservations + the panes planned in this run + one pane's need <= the Max memory % limit.
# "numbers" = "<used MB> <reserved MB> <limit MB> <pane MB>".
orca_down=0
ps_tsv=""
ps_out=""
watch_line=""
prep_model=""
room_nums=""
room_ok=1
TAB=$'\t'
prep_args=(resume-prep)
if [ -n "${AP_ROOTS_GITDIR:-}" ] && [ "${AP_ROOTS_CWD:-}" = "$PROJECT_CWD" ] && [ "${AP_ROOTS_GITDIR}" = "$PROJECT_GITDIR" ]; then
  prep_args+=(--gitdir "$PROJECT_GITDIR")
fi
if [ "$KIND" = "orca" ]; then
  prep_args+=(--model "$task_manager")
  ps_out=$(runtime_ps 2>/dev/null) || orca_down=1
  [ "$orca_down" -eq 1 ] || prep_args+=(--ps)
  [ -n "${AGENT_WATCH_LINE_DONE:-}" ] || prep_args+=(--watch "$ROOT" "$PLUGIN_ROOT")
fi
prep_rc=0
if [ "$orca_down" -eq 0 ] && [ "$KIND" = "orca" ]; then
  prep_out=$(cd "$PROJECT_ROOT" && printf '%s' "$ps_out" | python3 "$PLUGIN_ROOT/bin/agent_nightly.py" "${prep_args[@]}") || prep_rc=$?
  # a bad ps answer ends the run, as its own python3 did
  [ "$prep_rc" -eq 0 ] || exit "$prep_rc"
else
  prep_out=$(cd "$PROJECT_ROOT" && python3 "$PLUGIN_ROOT/bin/agent_nightly.py" "${prep_args[@]}" 2>/dev/null </dev/null) || prep_out=""
fi
while IFS= read -r _l; do
  case "$_l" in
    "M$TAB"*) prep_model=${_l#M"$TAB"};;
    "P$TAB"*) _l=${_l#P"$TAB"}
      if [ -n "$ps_tsv" ]; then ps_tsv="$ps_tsv
$_l"; else ps_tsv=$_l; fi;;
    "N$TAB"*) _l=${_l#N"$TAB"}; [ "${_l%%"$TAB"*}" = 0 ] && room_nums=${_l#*"$TAB"} || room_ok=0;;
    "W$TAB"*) watch_line=${_l#W"$TAB"};;
  esac
done <<<"$prep_out"
if [ "$KIND" = "orca" ]; then
  if [ -z "$prep_model" ]; then prep_model="${task_manager%%:*}"; fi
  printf -v MODEL '%q' "$prep_model"
  EFFORT=${task_manager#*:}
fi

# No count cap (check-blocks section 25): column 2 (any agent at the path) is a live pane for
# live_pane(); a done pane or a main manager pane still blocks a relaunch. Whether one more pane
# fits is the memory rule.
room_used=0; room_reserved=0; room_limit=0; room_pane=550; room_known=0
if [ "$room_ok" -eq 1 ] && [ -n "$room_nums" ]; then
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
  # the first row whose first column is the path; its second column is the agent count
  local row n
  while IFS= read -r row; do
    [ "${row%%"$TAB"*}" = "$path" ] || continue
    n=${row#*"$TAB"}; n=${n%%"$TAB"*}
    [ "${n:-0}" -gt 0 ]
    return
  done <<<"$ps_tsv"
  return 1
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
    # the three columns, split on " | " (plain text work: no awk start per column)
    path=${line%% | *}
    module=""; status=""
    case "$line" in
      *" | "*)
        module=${line#* | }
        case "$module" in
          *" | "*) status=${module#* | }; module=${module%% | *}; status=${status%% | *};;
        esac;;
    esac

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
          # C24, C25: the room check and the reservation happen before the create, in one step; resume launches
          # on this machine only (no --environment), so the pane is reserved in this machine's list.
          pane_key="resume-$$-$relaunch_count"
          if ! (cd "$PROJECT_ROOT" && "$PLUGIN_ROOT/bin/agent-room.sh" reserve-pane --pending "$pane_key" "$room_pane") >/dev/null 2>&1 </dev/null; then
            relaunched="no, no room"
            cap_lines="${cap_lines}no room (another agent took it first), not relaunching $path
"
          # (runtime_launch is the orca terminal create)
          elif launch_out=$(runtime_launch "$path" "TM $module" "$cmd" </dev/null); then
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
            # the reservation takes the new handle (no check); no handle in the answer: it stays under its key
            if [ -n "$pane_handle" ]; then
              (cd "$PROJECT_ROOT" && "$PLUGIN_ROOT/bin/agent-room.sh" reserve-pane --name "$pane_key" "$pane_handle") >/dev/null 2>&1 </dev/null || true
            fi
            relaunched="yes"
          else
            # a failed create gives the reservation back
            (cd "$PROJECT_ROOT" && "$PLUGIN_ROOT/bin/agent-room.sh" release-pane "$pane_key") >/dev/null 2>&1 </dev/null || true
            relaunched="yes"
          fi
        fi
        if [ "$relaunched" = yes ] || [ "$relaunched" = would ]; then
          relaunch_count=$((relaunch_count + 1))
          room_planned=$((room_planned + room_pane))
        fi
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
  # (the line was worked out above, in the one resume-prep start)
  if [ -n "$watch_line" ]; then
    echo "$watch_line"
    echo
  fi
fi

# ---- counts ----
# lines with at least one character, counted in bash (no grep start)
count_lines() {
  _cl_n=0
  while IFS= read -r _cl_l || [ -n "$_cl_l" ]; do
    [ -z "$_cl_l" ] || _cl_n=$((_cl_n + 1))
  done <"$1"
}
# a file that cannot be read goes to the old grep (same count, same stderr), never ends the run
todo_n=0
if [ -s "$TODO" ]; then
  if [ -r "$TODO" ]; then count_lines "$TODO"; todo_n=$_cl_n; else todo_n=$(grep -c . "$TODO" || true); fi
fi
ideas_n=0
if [ -s "$IDEAS" ]; then
  if [ -r "$IDEAS" ]; then count_lines "$IDEAS"; ideas_n=$_cl_n; else ideas_n=$(grep -c . "$IDEAS" || true); fi
fi
echo "todo: ${todo_n:-0} open"
echo "ideas: ${ideas_n:-0} waiting"
[ -z "$CLEAN_OUT" ] || printf '%s\n' "$CLEAN_OUT"
