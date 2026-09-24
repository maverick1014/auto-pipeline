#!/usr/bin/env bash
# agent-resources.sh — RAM and CPU readers, sourced by other scripts.
#
#   . ./agent-resources.sh
#   ram_used              -> percent used, or -1 when it cannot tell
#   cpu_used               -> percent used, or -1 when it cannot tell
#   resources_read         -> reads once into RAM_USED and CPU_USED (skips if already set)
#   resources_line <cap>   -> "RESOURCES: RAM <n>% CPU <n>% (cap <n>%) -> OK" or "-> OVER CAP"
#   resources_ok <cap>     -> exit 0 when both readings are under the cap
#
# AGENT_FAKE_RAM and AGENT_FAKE_CPU, when set, replace the real readings.
# Meant to be sourced, not executed directly.
#
#   ./agent-resources.sh relief   run this file directly with this one
#                                 argument (S4) to bring load back under cap
#
# relief stops only what the pipeline owns: test-run monitor loops, and
# monitors of repos with no live main manager. It never touches a process it
# does not own — the human's apps, other repos' sessions, Gradle or node
# runners are only ever listed in one table for the human to act on.

ram_used() {
  if [ -n "${AGENT_FAKE_RAM:-}" ]; then echo "$AGENT_FAKE_RAM"; return; fi
  if [ "$(uname)" = Darwin ]; then
    f=$(memory_pressure 2>/dev/null | awk -F': ' '/free percentage/{gsub("%","",$2);print $2}')
    [ -n "$f" ] && echo $((100 - f)) || echo -1
  else
    awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{if(t)printf "%d",(t-a)*100/t; else print -1}' /proc/meminfo
  fi
}
cpu_used() {
  if [ -n "${AGENT_FAKE_CPU:-}" ]; then echo "$AGENT_FAKE_CPU"; return; fi
  if [ "$(uname)" = Darwin ]; then
    i=$(top -l 2 -n 0 -s 1 2>/dev/null | awk '/CPU usage/{idle=$7}END{gsub("%","",idle);print idle}')
    [ -n "$i" ] && printf '%d\n' "${i%.*}" | awk '{print 100-$1}' || echo -1
  else
    read -r _ a b c d _ < /proc/stat; sleep 1; read -r _ a2 b2 c2 d2 _ < /proc/stat
    t=$(( (a2+b2+c2+d2)-(a+b+c+d) )); id=$(( d2-d ))
    [ "$t" -gt 0 ] && echo $(( (t-id)*100/t )) || echo -1
  fi
}

resources_read() {
  [ -n "${RAM_USED:-}" ] || RAM_USED=$(ram_used)
  [ -n "${CPU_USED:-}" ] || CPU_USED=$(cpu_used)
}

resources_line() {
  cap=$1
  resources_read
  r=$RAM_USED; c=$CPU_USED
  if [ "$r" -ge "$cap" ] || [ "$c" -ge "$cap" ]; then
    echo "RESOURCES: RAM ${r}% CPU ${c}% (cap ${cap}%) -> OVER CAP"
  else
    echo "RESOURCES: RAM ${r}% CPU ${c}% (cap ${cap}%) -> OK"
  fi
}

resources_ok() {
  cap=$1
  resources_read
  [ "$RAM_USED" -lt "$cap" ] && [ "$CPU_USED" -lt "$cap" ]
}

# ---- relief: only runs when this file is executed directly (see foot) ----

# Kills every "auto_pipeline_*/plugin/bin/agent-monitor.sh" process: monitor
# loops a test run started and left behind. This pattern only ever matches a
# throwaway test copy's own plugin tree, never a real install.
relief_kill_test_monitors() {
  pids=$(pgrep -f 'auto_pipeline_[a-z0-9_]*/plugin/bin/agent-monitor\.sh' 2>/dev/null || true)
  n=0
  for pid in $pids; do
    kill "$pid" 2>/dev/null && n=$((n + 1))
  done
  echo "stopped $n test monitors"
}

# Every other "agent-monitor.sh start" process still alive after
# relief_kill_test_monitors: find the repo it watches, and stop it only when
# that repo's own main-manager lock is missing or its owner is dead.
relief_kill_orphan_monitors() {
  pids=$(pgrep -f 'agent-monitor\.sh start' 2>/dev/null || true)
  for pid in $pids; do
    # skip anything the test-monitor pass above already owns/would have killed
    case "$(ps -o args= -p "$pid" 2>/dev/null)" in
      *auto_pipeline_*/plugin/bin/agent-monitor.sh*) continue ;;
    esac

    cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | awk '/^n/{print substr($0,2); exit}')
    [ -n "$cwd" ] || continue
    [ -d "$cwd" ] || continue

    gitdir=$(git -C "$cwd" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)
    [ -n "$gitdir" ] || continue
    repo_root=$(git -C "$cwd" worktree list --porcelain 2>/dev/null \
                | awk '/^worktree /{print $2; exit}')
    [ -n "$repo_root" ] || repo_root=$(dirname "$gitdir")

    lock="$gitdir/agent_main.lock"
    lock_pid=""
    [ -f "$lock" ] && lock_pid=$(awk '{print $1; exit}' "$lock" 2>/dev/null || true)

    if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
      continue
    fi

    repo_name=$(basename "$repo_root")
    if [ -x "$repo_root/bin/agent-monitor.sh" ]; then
      ( cd "$repo_root" && "$repo_root/bin/agent-monitor.sh" stop ) >/dev/null 2>&1 || true
    else
      kill "$pid" 2>/dev/null || true
    fi
    echo "stopped monitor of $repo_name (no live main manager)"
  done
}

relief_what_suggest() {
  # $1 = comm (from ps -Ao rss,pcpu,pid,comm), $2 = full args for the same pid
  comm=$1; args=$2
  case "$comm" in
    *GradleDaemon*) echo "GradleDaemon|gradle --stop"; return ;;
  esac
  case "$args" in
    *GradleDaemon*) echo "GradleDaemon|gradle --stop"; return ;;
  esac
  case "$comm" in
    */claude|claude|*Claude*|*claude*)
      cwd=$(lsof -a -p "$pid_for_what" -d cwd -Fn 2>/dev/null | awk '/^n/{print substr($0,2); exit}')
      echo "claude session ${cwd:-?}|close from Orca if idle"; return ;;
  esac
  case "$comm$args" in
    *[Oo]rca*) echo "Orca|close from Orca if idle"; return ;;
  esac
  case "$comm" in
    node|*/node)
      case "$args" in
        *tsc*) echo "node tsc|let it finish"; return ;;
        *jest*) echo "node jest|let it finish"; return ;;
        *vite*) echo "node vite|let it finish"; return ;;
        *) echo "node|let it finish"; return ;;
      esac
      ;;
  esac
  echo "other|human decides"
}

relief_human_table() {
  echo "PROCESS | MB | CPU% | WHAT | SUGGEST"
  ps -Ao rss,pcpu,pid,comm 2>/dev/null | awk 'NR>1' | sort -rn -k1,1 | while read -r rss pcpu pid comm; do
    case "$comm" in
      /usr/libexec/*|/sbin/*|/System/*|kernel_task|launchd) continue ;;
    esac
    args=$(ps -o args= -p "$pid" 2>/dev/null || true)
    pid_for_what=$pid
    what_suggest=$(relief_what_suggest "$comm" "$args")
    what=${what_suggest%%|*}
    suggest=${what_suggest#*|}
    mb=$((rss / 1024))
    printf '%s | %s | %s | %s | %s\n' "$comm" "$mb" "$pcpu" "$what" "$suggest"
  done | head -8
}

do_relief() {
  relief_kill_test_monitors
  relief_kill_orphan_monitors
  relief_human_table
  resources_read
  resources_line "${max_usage_percent:-80}"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  case "${1:-}" in
    relief) do_relief; exit 0 ;;
    *)
      echo "usage: agent-resources.sh relief" >&2
      exit 2
      ;;
  esac
fi
