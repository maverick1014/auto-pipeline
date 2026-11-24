#!/usr/bin/env bash
# agent-version.sh — is the running plugin older than the newest installed one?
#
#   agent-version.sh running          the running version (folder name above bin/), or nothing
#   agent-version.sh newest           "<NEWEST>\t<CACHE>/<NEWEST>", or nothing
#   agent-version.sh check            STALE -> "<RUNNING>\t<NEWEST>\t<CACHE>/<NEWEST>", exit 0
#                                     else nothing, exit 1
#   agent-version.sh scopes <dir>...  OLD PLUGIN lines for installed_plugins.json entries
#   agent-version.sh hook             UserPromptSubmit hook: one STALE PLUGIN line per session
#
# CACHE = <claude dir>/plugins/cache/auto-pipeline/auto-pipeline, <claude dir> =
# $CLAUDE_CONFIG_DIR (when not empty) else $HOME/.claude. Versions are dotted digits
# only. The check path is plain bash: no python, no git. bash 3.2 safe.
# Spec: tests/test_stale_plugin_guard.py (CONTRACT, sections 1-3).
set -u

SELF_DIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd -P)
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-${HOME:-}/.claude}"
CACHE="$CLAUDE_DIR/plugins/cache/auto-pipeline/auto-pipeline"

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
is_version() {
  case "$1" in
    ""|*[!0-9.]*|.*|*.|*..*) return 1 ;;
  esac
  return 0
}

RUNNING=""
NEWEST=""
find_running() {
  local up name
  up=$(dirname "$SELF_DIR"); name=$(basename "$up")
  RUNNING=""
  is_version "$name" && RUNNING="$name"
  return 0
}
find_newest() {
  local cand name
  NEWEST=""
  for cand in "$CACHE"/*/; do
    cand=${cand%/}; name=${cand##*/}
    [ -f "$cand/bin/agent-start.sh" ] || continue
    is_version "$name" || continue
    if [ -z "$NEWEST" ] || ver_newer "$name" "$NEWEST"; then NEWEST="$name"; fi
  done 2>/dev/null
  return 0
}
is_stale() {
  find_running; find_newest
  [ -n "$RUNNING" ] && [ -n "$NEWEST" ] && ver_newer "$NEWEST" "$RUNNING"
}

usage() {
  echo "usage: agent-version.sh running|newest|check|scopes <dir>...|hook" >&2
  exit 2
}

cmd_hook() {
  local IN="" sid cwd line tail told
  [ -t 0 ] || IN=$(cat)
  is_stale || return 0
  sid=$(printf '%s' "$IN" | sed -n 's/.*"session_id" *: *"\([^"]*\)".*/\1/p' | head -1)
  cwd=$(printf '%s' "$IN" | sed -n 's/.*"cwd" *: *"\([^"]*\)".*/\1/p' | head -1)
  [ -n "$sid" ] || sid="${CLAUDE_CODE_SESSION_ID:-}"
  . "$SELF_DIR/agent-roots.sh" || return 0
  roots_read "$cwd" || return 0
  [ -f "$PROJECT_ROOT/agent.conf" ] || return 0
  if [ -n "$sid" ]; then
    told=""
    [ -f "$PROJECT_GITDIR/agent_stale_$sid" ] && told=$(head -1 "$PROJECT_GITDIR/agent_stale_$sid")
    [ "$told" = "$NEWEST" ] && return 0
    tail="(claude --resume $sid)."
  else
    tail="(claude --resume)."
  fi
  printf 'STALE PLUGIN: this session runs %s, %s is installed. Call %s/%s/bin/... for every script and in every subagent brief. Restart this session at the next quiet point %s\n' \
    "$RUNNING" "$NEWEST" "$CACHE" "$NEWEST" "$tail"
  if [ -n "$sid" ]; then
    mkdir -p "$PROJECT_GITDIR" 2>/dev/null
    printf '%s\n' "$NEWEST" > "$PROJECT_GITDIR/agent_stale_$sid" 2>/dev/null
  fi
  return 0
}

cmd_scopes() {
  find_newest
  [ -n "$NEWEST" ] || return 0
  [ -f "$CLAUDE_DIR/plugins/installed_plugins.json" ] || return 0
  command -v python3 >/dev/null 2>&1 || return 0
  python3 -I -c '
import json, os, re, sys
try:
    path, newest = sys.argv[1], sys.argv[2]
    dirs = [os.path.realpath(d) for d in sys.argv[3:]]
    with open(path) as fh:
        data = json.load(fh)
    entries = data["plugins"]["auto-pipeline@auto-pipeline"]
    def key(v):
        return [int(p) for p in v.split(".")]
    def ok(v):
        return isinstance(v, str) and re.fullmatch(r"[0-9]+(\.[0-9]+)*", v) is not None
    def older(a, b):
        x, y = key(a), key(b)
        n = max(len(x), len(y))
        x += [0] * (n - len(x)); y += [0] * (n - len(y))
        return x < y
    seen = []
    for e in entries:
        try:
            v = e.get("version"); scope = e.get("scope")
            if not ok(v) or not older(v, newest):
                continue
            if scope == "user":
                line = ("OLD PLUGIN: the user scope runs %s, %s is installed. Update it: claude plugin "
                        "update auto-pipeline@auto-pipeline --scope user, then restart the session." % (v, newest))
            elif scope in ("project", "local"):
                pp = e.get("projectPath")
                if not isinstance(pp, str) or not pp or os.path.realpath(pp) not in dirs:
                    continue
                line = ("OLD PLUGIN: the %s scope of %s runs %s, %s is installed. Update it: cd %s && "
                        "claude plugin update auto-pipeline@auto-pipeline --scope %s, then restart the "
                        "session." % (scope, pp, v, newest, pp, scope))
            else:
                continue
            if line not in seen:
                seen.append(line)
        except Exception:
            continue
    for line in seen:
        print(line)
except Exception:
    pass
' "$CLAUDE_DIR/plugins/installed_plugins.json" "$NEWEST" "$@" 2>/dev/null </dev/null
  return 0
}

case "${1:-}" in
  running) find_running; [ -n "$RUNNING" ] && echo "$RUNNING"; exit 0 ;;
  newest)  find_newest; [ -n "$NEWEST" ] && printf '%s\t%s/%s\n' "$NEWEST" "$CACHE" "$NEWEST"; exit 0 ;;
  check)
    if is_stale; then printf '%s\t%s\t%s/%s\n' "$RUNNING" "$NEWEST" "$CACHE" "$NEWEST"; exit 0; fi
    exit 1 ;;
  scopes)  shift; cmd_scopes "$@"; exit 0 ;;
  hook)    cmd_hook 2>/dev/null; exit 0 ;;
  *)       usage ;;
esac
