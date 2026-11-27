#!/usr/bin/env bash
# agent-runtime.sh — which runtime this agent is in, and the only place that
# knows it. Orca is one way to run this pipeline, not the only one: the owner
# is half Orca, half the Claude app, and a cloud session is a third shape
# again. Every place that used to say `orca` asks this instead. Sourced, it
# defines the five functions below and runs nothing; run directly, it
# dispatches one verb.
#
#   bin/agent-runtime.sh kind                              orca | plain | cloud
#   bin/agent-runtime.sh ps                                the worktree JSON, or nothing
#   bin/agent-runtime.sh browser                           chrome | headless | none
#   bin/agent-runtime.sh launch <path> <title> <command>   open a terminal (orca only)
#   bin/agent-runtime.sh close <handle>                    close a terminal (orca only)
#   bin/agent-runtime.sh -h                                this help
#
# KIND is worked out fresh on every call, never cached, never written to a
# file, because the owner switches between Orca and the Claude app inside one
# day:
#   0. $AGENT_RUNTIME is exactly orca, plain or cloud   -> that one, full stop
#   1. the `runtime` setting (Configure) is orca, plain or cloud -> that one, full stop
#   2. CLAUDE_CODE_REMOTE=true                         -> cloud
#   3. orca on PATH and `orca worktree ps --json`
#      answers inside 3 seconds                        -> orca
#      cut off at 3 seconds -> one more try, 3 seconds -> orca
#      (a busy Orca can miss one window)
#   4. anything else                                   -> plain
# The retry in step 3 is for a timeout only: an orca that answers fast with an
# error (app not running) is a real answer, plain at once, one call, no retry.
# `auto`, an empty value, a missing line, or any other value all fall through
# to the next step, at either tier.
#
# AGENT_RUNTIME is something a CALLER sets, never something this script writes
# or exports itself: a caller that already paid for the probe once (a
# resume run working the kind out at the top) can pass it down so
# every later runtime_ps/runtime_launch/runtime_close is free instead of
# probing again.
#
# The 3 second probe cannot use `timeout` (macOS has none): it backgrounds the
# call and polls in 0.1s steps, up to 30 steps, then kills it on the way out.
# The background call redirects stdin, stdout and stderr, so a caller piping
# our own stdout/stderr never inherits them and hangs waiting for them to
# close. Any temp file it needs lives under ${TMPDIR:-/tmp} and is always
# removed before the probe returns, timed out or not. Its exit code tells a
# cut-off call (2, worth one retry) apart from one that ran to completion,
# whether that was a success (0) or a real, fast error (1, no retry).
#
# plain and cloud are the same shape: no terminals, no panes, no watch.
# They differ only in the browser: Claude in Chrome can never reach a cloud
# VM, so cloud looks for a headless browser instead.

# agent-roots.sh again only when the caller has not sourced it already (no dirname start either way)
if ! declare -F setting >/dev/null 2>&1; then
  _rt_src=${BASH_SOURCE[0]}
  case "$_rt_src" in */*) _rt_dir=${_rt_src%/*}; [ -n "$_rt_dir" ] || _rt_dir=/;; *) _rt_dir=.;; esac
  . "$_rt_dir/agent-roots.sh"
  unset _rt_src _rt_dir
fi

# ---- kind ---------------------------------------------------------------

# The `runtime` setting (user level, Configure), read fresh every time through
# `setting`, never kept in a variable, so a value from an earlier call can
# never linger. Prints nothing when it cannot be read.
_runtime_conf_value() {
  setting runtime 2>/dev/null || true
}

# The 3 second probe. Prints nothing. Exit code: 0 orca answered in time,
# 1 no orca on PATH or a real answer that was an error, 2 cut off at 3
# seconds (the only case worth a retry).
_runtime_probe_orca() {
  command -v orca >/dev/null 2>&1 || return 1
  local pid line rrc=0
  # The call runs in a background job of a child shell that prints the job's pid, then its exit
  # status when it is done. This shell waits on that pipe with `read -t 3`: it wakes the moment
  # the call ends (no polling, no sleep start), and cuts it off after 3 seconds. The child shell
  # and the call have no stdin, stderr or stdout of ours, so a caller piping our output never
  # waits on them. The answer itself is never read.
  exec 8< <(
    exec 2>/dev/null </dev/null
    orca worktree ps --json >/dev/null 2>&1 &
    echo "$!"
    wrc=0
    wait "$!" || wrc=$?
    echo "rc=$wrc"
  )
  read -r -u 8 pid || { exec 8<&-; return 1; }
  read -r -t 3 -u 8 line || rrc=$?
  if [ "$rrc" -eq 0 ]; then
    exec 8<&-
    [ "$line" = "rc=0" ] && return 0
    return 1
  fi
  # no answer line: cut off at 3 seconds (bash 3.2 gives plain 1 for that, bash 4 more than 128)
  kill -TERM "$pid" 2>/dev/null
  pkill -TERM -P "$pid" 2>/dev/null
  exec 8<&-
  return 2
}

runtime_kind() {
  local value rc
  case "${AGENT_RUNTIME:-}" in
    orca|plain|cloud) printf '%s\n' "$AGENT_RUNTIME"; return 0;;
  esac
  value=$(_runtime_conf_value)
  case "$value" in
    orca|plain|cloud) printf '%s\n' "$value"; return 0;;
  esac
  if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
    echo cloud
    return 0
  fi
  _runtime_probe_kind
}

# Steps 3 and 4 only (no setting, no env): orca when `orca worktree ps --json` answers, else plain.
_runtime_probe_kind() {
  local rc=0
  _runtime_probe_orca || rc=$?
  if [ "$rc" -eq 2 ]; then
    rc=0
    _runtime_probe_orca || rc=$?
  fi
  if [ "$rc" -eq 0 ]; then
    echo orca
  else
    echo plain
  fi
}

# ---- ps -------------------------------------------------------------------

runtime_ps() {
  case "$(runtime_kind)" in
    orca) orca worktree ps --json;;
    *) return 0;;
  esac
}

# ---- launch / close ---------------------------------------------------------

runtime_launch() {
  local path title run_cmd kind
  path=$1; title=$2; run_cmd=$3
  kind=$(runtime_kind)
  case "$kind" in
    orca)
      orca terminal create \
        --worktree "path:$path" \
        --title "$title" \
        --command "$run_cmd" \
        --json
      ;;
    *)
      echo "runtime: $kind mode has no terminals, launch $title with the Agent tool (a subagent) instead" >&2
      return 1
      ;;
  esac
}

runtime_close() {
  local handle
  handle=$1
  case "$(runtime_kind)" in
    orca) orca terminal close --terminal "$handle" --json;;
    *) return 0;;
  esac
}

# ---- browser ----------------------------------------------------------------

_runtime_native_host_present() {
  local name dir
  name="com.anthropic.claude_code_browser_extension.json"
  for dir in \
    "$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts" \
    "$HOME/Library/Application Support/Microsoft Edge/NativeMessagingHosts" \
    "$HOME/.config/google-chrome/NativeMessagingHosts" \
    "$HOME/.config/microsoft-edge/NativeMessagingHosts"
  do
    [ -f "$dir/$name" ] && return 0
  done
  return 1
}

_runtime_headless_available() {
  local name
  for name in chromium chromium-browser google-chrome; do
    command -v "$name" >/dev/null 2>&1 && return 0
  done
  command -v npx >/dev/null 2>&1 || return 1
  npx --no-install playwright --version >/dev/null 2>&1
}

runtime_browser() {
  local kind
  kind=$(runtime_kind)
  case "$kind" in
    cloud)
      if _runtime_headless_available; then echo headless; else echo none; fi
      ;;
    *)
      if _runtime_native_host_present; then echo chrome; else echo none; fi
      ;;
  esac
}

# ---- entry point --------------------------------------------------------

# Not named `usage`: this file is sourced by scripts that define their own
# `usage`, and a sourced function definition would silently replace theirs.
_runtime_usage() {
  cat <<'EOF'
agent-runtime.sh — which runtime this agent is in (orca | plain | cloud).

  bin/agent-runtime.sh kind                              orca | plain | cloud
  bin/agent-runtime.sh ps                                the worktree JSON, or nothing
  bin/agent-runtime.sh browser                           chrome | headless | none
  bin/agent-runtime.sh launch <path> <title> <command>   open a terminal (orca only)
  bin/agent-runtime.sh close <handle>                    close a terminal (orca only)
  bin/agent-runtime.sh -h                                this help
EOF
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  set -eu
  case "${1:-}" in
    -h|--help) _runtime_usage; exit 0;;
    kind) runtime_kind;;
    probe) _runtime_probe_kind;;
    ps) runtime_ps;;
    browser) runtime_browser;;
    launch) shift; [ $# -eq 3 ] || { _runtime_usage; exit 2; }; runtime_launch "$1" "$2" "$3";;
    close) shift; [ $# -eq 1 ] || { _runtime_usage; exit 2; }; runtime_close "$1";;
    *) _runtime_usage; exit 2;;
  esac
fi
