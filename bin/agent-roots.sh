#!/usr/bin/env bash
# agent-roots.sh — the two roots every other script needs. Sourced, never run.
#
#   . "$(dirname "$0")/agent-roots.sh"
#   roots_read [<cwd>]   sets PROJECT_CWD, PROJECT_ROOT, PROJECT_GITDIR, STATE_DIR
#   setting <key>        prints one setting (or fixed constant) as text, from
#                         agent_conf.py get; nothing and status 1 on any failure.
#                         A key that settings_read read already is answered from
#                         the shell variables: no python3 start.
#   settings_read <key>...  ONE `agent_conf.py get <key>...` call for all the keys;
#                         keeps the values in the shell variables _AP_S_<key>
#                         (names listed in _AP_SET_KEYS). A key that failed to
#                         read stays unread, so setting <key> asks python3 itself.
#                         The values live in this process only, never exported:
#                         a child script reads its own (a settings write between
#                         parent and child, or a test's own settings.json, must
#                         never be served stale). Read after a write, not before;
#                         settings_forget drops them (call it after agent_conf.py
#                         migrate or any other settings write in the same script).
#   roots_read reuse     the result is exported as AP_ROOTS_CWD / AP_ROOTS_ROOT /
#                         AP_ROOTS_GITDIR / AP_ROOTS_STATE, only when git answered
#                         all three (no fallback used). A child script that asks for
#                         the same PROJECT_CWD takes them without asking git again.
#   repo_set_up          true when "$PROJECT_ROOT/agent_todo.txt" is a file
#                         (call after roots_read)
#   agent_pid            this session's pid: $CLAUDE_PID, else the first
#                         claude/codex/opencode/gemini ancestor (shared with
#                         agent-start.sh and agent-close-case.sh)
#   role_read            this session's role (W10). Call after roots_read.
#                         Read only, never writes the lock. Sets LOCK, CLOSED, ME
#                         and role = spawned (AGENT_ROLE is set) | main (no lock,
#                         or the lock is ours) | closed (this session was released
#                         or replaced, and the lock is not ours) | second (a live
#                         main manager holds the lock) | takeover (the lock's pid
#                         is dead). From the lock: lpid, lsince ("<date> <time>"),
#                         lsid, lterm (empty when the lock has a "-"). From the
#                         closed list, role closed only: cwhy (released|replaced),
#                         cwhen. One copy of the logic, for agent-start.sh,
#                         agent-close-case.sh and agent-name.sh.
#   pid_alive <pid>      true when that process is running
#   holder_text          "pid <lpid> ("<repo> Manager"[, terminal <t>])[, since <s>]"
#   closed_lines <lead>  what a closed session is told (4 lines, lead starts the
#                         first). After role_read.
#
# Lock "$PROJECT_GITDIR/agent_main.lock", one line, written by agent-start.sh:
#   "<pid> <YYYY-MM-DD> <HH:MM> <sid> <terminal>"   ("-" when unknown; the old
#   "<pid> <date> <time>" still reads).
# Closed list "$PROJECT_GITDIR/agent_main.closed", written by agent-start.sh
# (--release, --take-over), one line per closed session:
#   "<pid> <released|replaced> <YYYY-MM-DD> <HH:MM>"   (dead pids pruned on write)
#
# PLUGIN root  = the folder above bin/. Read only: PRINCIPLES.md, rules/, GLOSSARY.md, NOTICE.md, the quiz,
#                agent_conf.py. No script writes here. The settings are not
#                in any file of PROJECT_ROOT: they live in Claude Code,
#                /plugin -> Installed -> auto-pipeline -> Configure.
# PROJECT root = the repo being worked on, found from the starting directory:
#                1. $1 (a hook's stdin cwd), 2. $CLAUDE_PROJECT_DIR, 3. $PWD.
#                A starting directory that does not exist falls back to $PWD.
#                PROJECT_ROOT is the main worktree of `git worktree list`, so a
#                script started inside a git worktree still writes the shared
#                files into the project's main repo.
#
# Per-project files live in PROJECT_ROOT: agent_todo.txt,
# agent_completed.txt, agent_ideas.txt, agent_worktree.txt,
# .secrets/. The main-manager lock, the closed list and the watch status (agent_watch.json) live in
# PROJECT_GITDIR, the project's shared git dir, or "$PROJECT_ROOT/.auto-pipeline" when there is
# no git (never ".git" — that name belongs to git, not us). agent_state.txt
# lives in STATE_DIR, the git toplevel of the directory the agent is in, so a
# worktree keeps its own.

_ap_src=${BASH_SOURCE[0]}
case "$_ap_src" in
  */*) _ap_dir=${_ap_src%/*}; [ -n "$_ap_dir" ] || _ap_dir=/;;
  *)   _ap_dir=.;;
esac
PLUGIN_ROOT=$(cd "$_ap_dir/.." && pwd -P)
unset _ap_src _ap_dir

# _ap_base <path>: basename as plain text work, result in _AP_BASE
_ap_base() {
  local s=$1
  s=${s%"${s##*[!/]}"}
  [ -n "$s" ] || { [ -z "$1" ] || s=/; }
  _AP_BASE=${s##*/}
  [ "$s" != / ] || _AP_BASE=/
}

roots_read() {
  local _wl _l _k _a _rest _out _ok=1
  start="${1:-${CLAUDE_PROJECT_DIR:-$PWD}}"
  [ -d "$start" ] || start="$PWD"
  PROJECT_CWD=$(cd "$start" && pwd -P)

  if [ "${AP_ROOTS_CWD:-}" = "$PROJECT_CWD" ] && [ -n "${AP_ROOTS_ROOT:-}" ] \
     && [ -n "${AP_ROOTS_GITDIR:-}" ] && [ -n "${AP_ROOTS_STATE:-}" ]; then
    PROJECT_ROOT=$AP_ROOTS_ROOT; PROJECT_GITDIR=$AP_ROOTS_GITDIR; STATE_DIR=$AP_ROOTS_STATE
    return 0
  fi

  # the first "worktree <path>" line (awk's $2: the first word of the path)
  PROJECT_ROOT=""
  _wl=$(git -C "$PROJECT_CWD" worktree list --porcelain 2>/dev/null || true)
  while IFS= read -r _l; do
    case "$_l" in
      "worktree "*) read -r _k _a _rest <<<"$_l"; PROJECT_ROOT=$_a; break;;
    esac
  done <<<"$_wl"
  [ -n "$PROJECT_ROOT" ] || { PROJECT_ROOT=$PROJECT_CWD; _ok=0; }

  # one rev-parse prints the common dir, then the toplevel. In a bare dir the
  # toplevel fails after the first line: that one line is the common dir.
  _out=$(git -C "$PROJECT_CWD" rev-parse --path-format=absolute \
           --git-common-dir --show-toplevel 2>/dev/null || true)
  case "$_out" in
    *$'\n'*) PROJECT_GITDIR=${_out%%$'\n'*}; STATE_DIR=${_out#*$'\n'};;
    *)       PROJECT_GITDIR=$_out; STATE_DIR="";;
  esac
  [ -n "$PROJECT_GITDIR" ] || { PROJECT_GITDIR="$PROJECT_ROOT/.auto-pipeline"; _ok=0; }
  [ -n "$STATE_DIR" ] || { STATE_DIR=$PROJECT_CWD; _ok=0; }
  if [ "$_ok" = 1 ]; then
    export AP_ROOTS_CWD="$PROJECT_CWD" AP_ROOTS_ROOT="$PROJECT_ROOT" \
           AP_ROOTS_GITDIR="$PROJECT_GITDIR" AP_ROOTS_STATE="$STATE_DIR"
  fi
  return 0
}

: "${_AP_SET_KEYS:= }"

# settings_read <key>...: one python3 call for all keys (see the header)
settings_read() {
  local out line k v key keys=" "
  for key in "$@"; do
    case "$key" in ''|*[!a-z0-9_]*) ;; *) keys="$keys$key ";; esac
  done
  [ "$keys" != " " ] || return 0
  # shellcheck disable=SC2086
  set -- $keys
  if [ "$#" = 1 ]; then
    out=$(python3 "$PLUGIN_ROOT/bin/agent_conf.py" get "$1" 2>/dev/null </dev/null) || return 0
    printf -v "_AP_S_$1" '%s' "$out"
    case "$_AP_SET_KEYS" in *" $1 "*) ;; *) _AP_SET_KEYS="$_AP_SET_KEYS$1 ";; esac
    return 0
  fi
  out=$(python3 "$PLUGIN_ROOT/bin/agent_conf.py" get "$@" 2>/dev/null </dev/null || true)
  while IFS= read -r line; do
    case "$line" in *=*) ;; *) continue;; esac
    k=${line%%=*}; v=${line#*=}
    case "$keys" in *" $k "*) ;; *) continue;; esac
    printf -v "_AP_S_$k" '%s' "$v"
    case "$_AP_SET_KEYS" in *" $k "*) ;; *) _AP_SET_KEYS="$_AP_SET_KEYS$k ";; esac
  done <<<"$out"
  return 0
}

settings_forget() { _AP_SET_KEYS=" "; }

setting() {
  local out _n
  case "${_AP_SET_KEYS:- }" in
    *" $1 "*)
      _n="_AP_S_$1"; out=${!_n}
      [ -n "$out" ] || return 1
      printf '%s\n' "$out"
      return 0;;
  esac
  out=$(python3 "$PLUGIN_ROOT/bin/agent_conf.py" get "$1" 2>/dev/null </dev/null) || return 1
  [ -n "$out" ] || return 1
  printf '%s\n' "$out"
}

repo_set_up() { [ -n "${PROJECT_ROOT:-}" ] && [ -f "$PROJECT_ROOT/agent_todo.txt" ]; }

role_read() {
  local _d _t _p _row _l _f _n
  LOCK="$PROJECT_GITDIR/agent_main.lock"; CLOSED="$PROJECT_GITDIR/agent_main.closed"
  ME=$(agent_pid)
  role=main; lpid=""; lsince=""; lsid=""; lterm=""; cwhy=""; cwhen=""
  if [ -f "$LOCK" ]; then
    read -r lpid _d _t lsid lterm < "$LOCK" 2>/dev/null || true
    lsince="${_d:-}${_t:+ $_t}"
    case "$lsid" in -) lsid="";; esac
    case "$lterm" in -) lterm="";; esac
  fi
  if [ -n "${AGENT_ROLE:-}" ]; then role=spawned
  elif [ -f "$LOCK" ] && [ "$lpid" = "$ME" ]; then role=main
  else
    _row=""
    if [ -f "$CLOSED" ]; then
      # the first line whose first word is this pid (awk compared two numbers as numbers)
      while IFS= read -r _l || [ -n "$_l" ]; do
        read -r _f _n <<<"$_l"
        if [ "$_f" = "$ME" ]; then _row=$_l; break; fi
        case "$_f$ME" in
          ''|*[!0-9]*) ;;
          *) [ -n "$_f" ] && [ -n "$ME" ] && [ "${#_f}" -lt 15 ] && [ "${#ME}" -lt 15 ] \
               && [ "$((10#$_f))" = "$((10#$ME))" ] && { _row=$_l; break; };;
        esac
      done 2>/dev/null <"$CLOSED"
    fi
    if [ -n "$_row" ]; then
      role=closed
      read -r _p cwhy _d _t <<<"$_row"
      cwhen="${_d:-}${_t:+ $_t}"
    elif [ -f "$LOCK" ]; then
      if kill -0 "$lpid" 2>/dev/null; then role=second; else role=takeover; fi
    fi
  fi
  return 0
}

pid_alive() { kill -0 "$1" 2>/dev/null; }

holder_text() {
  _ap_base "$PROJECT_ROOT"
  printf 'pid %s ("%s Manager"%s)%s' "$lpid" "$_AP_BASE" \
    "${lterm:+, terminal $lterm}" "${lsince:+, since $lsince}"
}

closed_lines() {
  local why b
  _ap_base "$PROJECT_ROOT"; b=$_AP_BASE
  case "$cwhy" in
    released) why="released after a whole-repo close case${cwhen:+, $cwhen}";;
    *)        why="another session took over${cwhen:+, $cwhen}";;
  esac
  printf '%s You are no longer the main manager of "%s" (%s). Do not act as the main manager.\n' \
    "$1" "$b" "$why"
  if [ -z "$lpid" ]; then
    echo "No main manager now: the next session the human opens becomes it."
  elif kill -0 "$lpid" 2>/dev/null; then
    echo "Main manager now: $(holder_text)."
  else
    echo "The lock names pid $lpid, which is gone: the next session the human opens becomes the main manager."
  fi
  echo "Your session name may still say \"$(basename "$PROJECT_ROOT") Manager\": ask the human once to type /rename $b Helper (with a task: /rename $b Helper - <Task Name>)"
  echo "Take over again only when the human asks. The human types this line in this session; never run it yourself:"
  echo "! $PLUGIN_ROOT/bin/agent-start.sh --take-over"
}

agent_pid() {
  [ -n "${CLAUDE_PID:-}" ] && { echo "$CLAUDE_PID"; return; }
  local p c i tbl pid ppid comm
  local -a _pp _cm
  # one ps for the whole table; a pid it does not list is asked on its own, as before
  tbl=$(ps -A -o pid= -o ppid= -o comm= 2>/dev/null || true)
  while read -r pid ppid comm; do
    case "$pid" in ''|*[!0-9]*) continue;; esac
    case "$ppid" in ''|*[!0-9]*) continue;; esac
    _pp[$pid]=$ppid; _cm[$pid]=$comm
  done <<<"$tbl"
  p=$PPID
  for i in 1 2 3 4 5 6 7 8; do
    case "$p" in ''|*[!0-9]*) c=$(ps -o comm= -p "$p" 2>/dev/null | tr -d ' ');; *)
      if [ -n "${_pp[$p]+x}" ]; then c=${_cm[$p]// /}
      else c=$(ps -o comm= -p "$p" 2>/dev/null | tr -d ' '); fi;;
    esac
    case "$c" in *claude*|*codex*|*opencode*|*gemini*) echo "$p"; return;; esac
    case "$p" in
      ''|*[!0-9]*) p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ');;
      *) if [ -n "${_pp[$p]+x}" ]; then p=${_pp[$p]}
         else p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' '); fi;;
    esac
    [ -z "$p" ] || [ "$p" = 1 ] && break
  done
  echo "$PPID"
}
