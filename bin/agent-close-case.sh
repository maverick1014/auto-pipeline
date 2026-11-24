#!/usr/bin/env bash
# agent-close-case.sh — UserPromptSubmit hook, one job: a session that was
# released or replaced as main manager is told so once (the told-once mark below).
# The "close case" rule itself is no keyword hook any more: it is the skill
# /auto-pipeline:close-case (skills/close-case/SKILL.md, PRINCIPLES.md W13).
# Never blocks the prompt: always exit 0, nothing on stderr. The only file it
# ever writes is the told-once mark of a closed session (below). Second mode:
# --release-line (no stdin), prints the release line for the human. See
# hooks/hooks.json (UserPromptSubmit) and tests/test_agent_close_case.py.
#
#   Claude Code -> stdin JSON {"session_id","transcript_path","cwd",
#   "permission_mode","hook_event_name","prompt"} -> stdout is added to the
#   session's context.
set -u

. "$(dirname "$0")/agent-roots.sh"

# ver_newer <a> <b>: version a is higher than b, compared number by number.
ver_newer() {
  local IFS=. i=0 n x y
  local -a a b
  a=($1); b=($2)
  n=${#a[@]}; [ "${#b[@]}" -gt "$n" ] && n=${#b[@]}
  while [ "$i" -lt "$n" ]; do
    x=$((10#${a[$i]:-0})); y=$((10#${b[$i]:-0}))
    [ "$x" -gt "$y" ] && return 0
    [ "$x" -lt "$y" ] && return 1
    i=$((i + 1))
  done
  return 1
}
# is_version <name>: only digits and dots, like 0.14.0.
is_version() {
  case "$1" in
    ""|*[!0-9.]*|.*|*.|*..*) return 1 ;;
  esac
  return 0
}
# plugin_now <running plugin dir>: the plugin installed now. A running plugin in a
# folder named like a version -> the highest version folder next to it that has
# bin/agent-start.sh (a neighbour with another name or without it never wins).
# Any other folder name -> the plugin itself. bash 3.2: no GNU flags, no assoc arrays.
plugin_now() {
  local base name best="" cand
  base=$(dirname "$1"); name=$(basename "$1")
  is_version "$name" || { printf '%s' "$1"; return 0; }
  for cand in "$base"/*/; do
    cand=${cand%/}
    [ -f "$cand/bin/agent-start.sh" ] || continue
    is_version "${cand##*/}" || continue
    if [ -z "$best" ] || ver_newer "${cand##*/}" "${best##*/}"; then best="$cand"; fi
  done 2>/dev/null
  printf '%s' "${best:-$1}"
}

# `agent-close-case.sh --release-line`: no hook, one line for the human to type to
# make this session stop being main manager (skill close-case, part B step 8). The
# path is the plugin installed now, never an older running one.
if [ "${1:-}" = "--release-line" ]; then
  printf '! %s/bin/agent-start.sh --release\n' "$(plugin_now "$PLUGIN_ROOT")"
  exit 0
fi

[ -t 0 ] && exit 0
IN=$(cat)

# A session that was released or replaced as main manager (agent-start.sh
# --release, --take-over) is told once, on its first prompt after that, any
# prompt: "$PROJECT_GITDIR/agent_main.told_<pid>" is the told mark. Cheap: one
# git call, and nothing more unless the closed list is there. No git (empty
# answer) takes the full path, roots_read knows the fallback dir.
CWD0=$(printf '%s' "$IN" | sed -n 's/.*"cwd" *: *"\([^"]*\)".*/\1/p' | head -1)
GD=$(git -C "${CWD0:-${CLAUDE_PROJECT_DIR:-$PWD}}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
if [ -z "$GD" ] || [ -f "$GD/agent_main.closed" ]; then
  roots_read "$CWD0" 2>/dev/null
  if [ -f "$PROJECT_ROOT/agent.conf" ] && [ -f "$PROJECT_GITDIR/agent_main.closed" ]; then
    role_read
    if [ "$role" = closed ] && [ ! -f "$PROJECT_GITDIR/agent_main.told_$ME" ]; then
      closed_lines "NOTICE:"
      : > "$PROJECT_GITDIR/agent_main.told_$ME" 2>/dev/null || true
    fi
  fi
fi
exit 0
