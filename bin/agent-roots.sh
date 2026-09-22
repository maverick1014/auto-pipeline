#!/usr/bin/env bash
# agent-roots.sh — the two roots every other script needs. Sourced, never run.
#
#   . "$(dirname "$0")/agent-roots.sh"
#   roots_read [<cwd>]   sets PROJECT_CWD, PROJECT_ROOT, PROJECT_GITDIR, STATE_DIR
#   conf_read            sources "$PROJECT_ROOT/agent.conf" when it is there
#                         (call after roots_read)
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
# .secrets/. The main-manager lock and the monitor pid live in PROJECT_GITDIR,
# the project's shared git dir, or "$PROJECT_ROOT/.auto-pipeline" when there is
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
