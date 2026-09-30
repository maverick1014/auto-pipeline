#!/usr/bin/env bash
# agent-roots.sh — the two roots every other script needs. Sourced, never run.
#
#   . "$(dirname "$0")/agent-roots.sh"
#   roots_read [<cwd>]   sets PROJECT_CWD, PROJECT_ROOT, PROJECT_GITDIR, STATE_DIR
#   conf_read            sources "$PROJECT_ROOT/agent.conf" when it is there
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
# PLUGIN root  = the folder above bin/. Read only: PRINCIPLES.md, the quiz,
#                agent_conf.py, bin/agent.conf.default. No script writes here.
# PROJECT root = the repo being worked on, found from the starting directory:
#                1. $1 (a hook's stdin cwd), 2. $CLAUDE_PROJECT_DIR, 3. $PWD.
#                A starting directory that does not exist falls back to $PWD.
#                PROJECT_ROOT is the main worktree of `git worktree list`, so a
#                script started inside a git worktree still writes the shared
#                files into the project's main repo.
#
# Per-project files live in PROJECT_ROOT: agent.conf, agent_todo.txt,
# agent_completed.txt, agent_ideas.txt, agent_worktree.txt, agent_monitor.txt,
# .secrets/. The main-manager lock, the closed list and the monitor pid live in
# PROJECT_GITDIR, the project's shared git dir, or "$PROJECT_ROOT/.auto-pipeline" when there is
# no git (never ".git" — that name belongs to git, not us). agent_state.txt
# lives in STATE_DIR, the git toplevel of the directory the agent is in, so a
# worktree keeps its own.

PLUGIN_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)

roots_read() {
  start="${1:-${CLAUDE_PROJECT_DIR:-$PWD}}"
  [ -d "$start" ] || start="$PWD"
  PROJECT_CWD=$(cd "$start" && pwd -P)

  PROJECT_ROOT=$(git -C "$PROJECT_CWD" worktree list --porcelain 2>/dev/null \
                 | awk '/^worktree /{print $2; exit}')
  : "${PROJECT_ROOT:=$PROJECT_CWD}"

  PROJECT_GITDIR=$(git -C "$PROJECT_CWD" rev-parse --path-format=absolute \
                    --git-common-dir 2>/dev/null || true)
  : "${PROJECT_GITDIR:=$PROJECT_ROOT/.auto-pipeline}"

  STATE_DIR=$(git -C "$PROJECT_CWD" rev-parse --show-toplevel 2>/dev/null || true)
  : "${STATE_DIR:=$PROJECT_CWD}"
  return 0
}

conf_read() {
  if [ -n "${PROJECT_ROOT:-}" ] && [ -f "$PROJECT_ROOT/agent.conf" ]; then
    . "$PROJECT_ROOT/agent.conf"
  fi
  return 0
}

role_read() {
  local _d _t _p _row
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
    [ -f "$CLOSED" ] && _row=$(awk -v p="$ME" '$1 == p {print; exit}' "$CLOSED" 2>/dev/null)
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
  printf 'pid %s ("%s Manager"%s)%s' "$lpid" "$(basename "$PROJECT_ROOT")" \
    "${lterm:+, terminal $lterm}" "${lsince:+, since $lsince}"
}

closed_lines() {
  local why
  case "$cwhy" in
    released) why="released after a whole-repo close case${cwhen:+, $cwhen}";;
    *)        why="another session took over${cwhen:+, $cwhen}";;
  esac
  printf '%s You are no longer the main manager of "%s" (%s). Do not act as the main manager.\n' \
    "$1" "$(basename "$PROJECT_ROOT")" "$why"
  if [ -z "$lpid" ]; then
    echo "No main manager now: the next session the human opens becomes it."
  elif kill -0 "$lpid" 2>/dev/null; then
    echo "Main manager now: $(holder_text)."
  else
    echo "The lock names pid $lpid, which is gone: the next session the human opens becomes the main manager."
  fi
  echo "Your session name may still say \"$(basename "$PROJECT_ROOT") Manager\": ask the human once to type /rename $(basename "$PROJECT_ROOT") Helper"
  echo "Take over again only when the human asks. The human types this line in this session; never run it yourself:"
  echo "! $PLUGIN_ROOT/bin/agent-start.sh --take-over"
}

agent_pid() {
  [ -n "${CLAUDE_PID:-}" ] && { echo "$CLAUDE_PID"; return; }
  p=$PPID
  for _ in 1 2 3 4 5 6 7 8; do
    c=$(ps -o comm= -p "$p" 2>/dev/null | tr -d ' ')
    case "$c" in *claude*|*codex*|*opencode*|*gemini*) echo "$p"; return;; esac
    p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' '); [ -z "$p" ] || [ "$p" = 1 ] && break
  done
  echo "$PPID"
}
