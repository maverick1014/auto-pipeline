#!/usr/bin/env bash
# agent-init.sh — set up a project to use this plugin. Idempotent: running
# it twice changes not one byte.
#
#   bin/agent-init.sh              set up the current project
#   bin/agent-init.sh <dir>        set up that project
#   bin/agent-init.sh -h           print this block, create nothing, exit 0
#
# Creates, only when missing, in the project root: agent.conf (a copy of
# bin/agent.conf.default), the four agent_*.txt task files (empty),
# .secrets/ (empty dir) and AGENTS.md (one line pointing at this plugin).
# Adds .secrets/, agent_state.txt, agent_monitor.txt, agent_monitor.txt.tmp.*
# and .auto-pipeline/ to .gitignore, creating it when missing. Never
# overwrites a file already there; ends by printing the Bash permission
# block a human pastes into the project's .claude/settings.json.
set -eu
. "$(dirname "$0")/agent-roots.sh"

case "${1:-}" in
  -h|--help) sed -n '2,15p' "$0"; exit 0;;
esac

TARGET="${1:-}"
if [ -n "$TARGET" ] && [ ! -d "$TARGET" ]; then
  echo "agent-init.sh: no such directory: $TARGET" >&2
  exit 2
fi

roots_read "$TARGET"
ROOT="$PROJECT_ROOT"

file_empty() {
  name="$1"
  path="$ROOT/$name"
  if [ -e "$path" ]; then
    echo "kept: $name"
  else
    : > "$path"
    echo "created: $name"
  fi
}

file_conf() {
  path="$ROOT/agent.conf"
  if [ -e "$path" ]; then
    echo "kept: agent.conf"
  else
    cp "$PLUGIN_ROOT/bin/agent.conf.default" "$path"
    echo "created: agent.conf"
  fi
}

dir_secrets() {
  path="$ROOT/.secrets"
  if [ -d "$path" ]; then
    echo "kept: .secrets/"
  else
    mkdir -p "$path"
    echo "created: .secrets/"
  fi
}

file_agents_md() {
  path="$ROOT/AGENTS.md"
  line="Run $PLUGIN_ROOT/bin/agent-start.sh first. No work until the quiz says PASS."
  if [ -e "$path" ]; then
    if grep -qF "$line" "$path" 2>/dev/null; then
      echo "kept: AGENTS.md"
    else
      printf '%s\n' "$line" >> "$path"
      echo "appended: AGENTS.md"
    fi
  else
    printf '%s\n' "$line" > "$path"
    echo "created: AGENTS.md"
  fi
}

file_gitignore() {
  path="$ROOT/.gitignore"
  if [ -e "$path" ]; then
    status="kept"
  else
    : > "$path"
    status="created"
  fi
  for pat in ".secrets/" "agent_state.txt" "agent_monitor.txt" "agent_monitor.txt.tmp.*" ".auto-pipeline/"; do
    grep -qxF "$pat" "$path" 2>/dev/null || printf '%s\n' "$pat" >> "$path"
  done
  echo "$status: .gitignore"
}

file_conf
file_empty agent_todo.txt
file_empty agent_completed.txt
file_empty agent_ideas.txt
file_empty agent_worktree.txt
dir_secrets
file_agents_md
file_gitignore

cat <<'BLOCK'
{
  "permissions": {
    "allow": [
      "Bash(git push origin --delete *)",
      "Bash(git branch -d *)",
      "Bash(git worktree remove *)",
      "Bash(git worktree prune)",
      "Bash(orca worktree rm *)",
      "Bash(orca terminal close *)"
    ]
  }
}
BLOCK

echo "Paste that permission block into .claude/settings.json in this project."
echo "A plugin cannot add permission rules by itself, so a human must paste it."
