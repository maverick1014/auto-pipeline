#!/usr/bin/env bash
# agent-init.sh — set up a project to use this plugin. Idempotent: running
# it twice changes not one byte.
#
#   bin/agent-init.sh              set up the current project
#   bin/agent-init.sh <dir>        set up that project
#   bin/agent-init.sh --mode bypass|auto [<dir>]
#                                  also set permission_mode for every agent
#                                  (bypass = bypassPermissions, auto = auto);
#                                  any other value exits 2, nothing created
#   bin/agent-init.sh -h           print this block, create nothing, exit 0
#
# Creates, only when missing, in the project root: agent.conf (a copy of
# bin/agent.conf.default), the four agent_*.txt task files (empty),
# .secrets/ (empty dir) and AGENTS.md (one line pointing at this plugin,
# relative to the project root when the plugin is packed inside it, e.g.
# .claude/auto-pipeline, absolute otherwise).
# Adds .secrets/, agent_state.txt, agent_monitor.txt, agent_monitor.txt.tmp.*
# and .auto-pipeline/ to .gitignore, creating it when missing. Never
# overwrites a file already there.
#
# A fresh agent.conf is seeded from bin/agent.conf.default, then any of
# CLAUDE_PLUGIN_OPTION_RUNTIME, CLAUDE_PLUGIN_OPTION_LANGUAGE and
# CLAUDE_PLUGIN_OPTION_MAX_AGENTS that Claude Code collected at enable time
# are written over it, key by key, when set and not empty.
#
# Permission mode: only when agent.conf is created in this run. --mode writes
# it through bin/agent-settings.sh permission_mode. Without --mode, a fresh
# agent.conf and a terminal on stdin: one question, "Permission mode for every
# agent: bypass (recommended) or auto?"; Enter or anything else keeps the
# template value. agent.conf already there: never changed; with --mode, one
# line says it was kept and how to change it.
# When the project's permission_mode is bypassPermissions and
# ~/.claude/settings.json lacks "skipDangerousModePermissionPrompt": true, one
# line says new panes stop on the bypass warning screen. The file is only
# read, never written.
#
# Ends by printing two blocks a human pastes himself, since a plugin cannot
# reach either place:
#   1. the Bash permission block, for the project's .claude/settings.json.
#   2. the cloud block, for a cloud session's Setup script. The default
#      cloud image already ships Playwright and Chromium, so paste this
#      line only if <plugin>/bin/agent-runtime.sh browser prints none there:
#          npx playwright install --with-deps chromium || true
#      Skip it if this repo never runs in a cloud session.
set -eu
. "$(dirname "$0")/agent-roots.sh"

case "${1:-}" in
  -h|--help) sed -n '2,45p' "$0"; exit 0;;
esac

MODE=""
MODE_GIVEN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --mode)
      if [ $# -lt 2 ]; then
        echo "agent-init.sh: --mode needs a value: bypass or auto" >&2
        exit 2
      fi
      MODE_GIVEN=1
      case "$2" in
        bypass) MODE="bypassPermissions";;
        auto) MODE="auto";;
        *) echo "agent-init.sh: --mode must be bypass or auto, got: $2" >&2; exit 2;;
      esac
      shift 2;;
    *) break;;
  esac
done

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
    seed_conf_from_env "$path"
    echo "created: agent.conf"
    CONF_FRESH=1
  fi
}

conf_permission_mode() {
  PYTHONPATH="$PLUGIN_ROOT/bin${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys, agent_conf
print(agent_conf.load(sys.argv[1]).get("permission_mode", ""))' "$ROOT/agent.conf"
}

set_permission_mode() {
  CLAUDE_PROJECT_DIR="$ROOT" "$PLUGIN_ROOT/bin/agent-settings.sh" permission_mode "$1"
}

ask_permission_mode() {
  [ -t 0 ] || return 0
  printf 'Permission mode for every agent: bypass (recommended) or auto? [bypass/auto, Enter = template default]: ' >&2
  ans=""
  read -r ans || ans=""
  ans=$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')
  case "$ans" in
    bypass|b) set_permission_mode bypassPermissions;;
    auto|a) set_permission_mode auto;;
  esac
}

skip_warning_line() {
  [ "$(conf_permission_mode)" = "bypassPermissions" ] || return 0
  if python3 - "$HOME/.claude/settings.json" <<'PY'
import json, sys
try:
    with open(sys.argv[1]) as f:
        d = json.load(f)
    ok = isinstance(d, dict) and d.get("skipDangerousModePermissionPrompt") is True
except Exception:
    ok = False
sys.exit(0 if ok else 1)
PY
  then
    return 0
  fi
  echo 'Note: new panes stop on the bypass warning screen until you add this to ~/.claude/settings.json yourself (this script never writes it): "skipDangerousModePermissionPrompt": true'
}

# Write the enable-time answers Claude Code collected over a freshly copied
# agent.conf. Only called right after the copy, never when the file was
# already there. A key with no matching env var, or an empty one, is left as
# the template set it; every other key and the key order stay untouched. A
# value that fails agent_conf.validate_value is never written: the template's
# own value stands, and one line naming the key, the bad value and why goes
# to stderr, so it can never land inside the permission block a test (or a
# human) parses as JSON. One bad key never stops the others.
seed_conf_from_env() {
  PYTHONPATH="$PLUGIN_ROOT/bin${PYTHONPATH:+:$PYTHONPATH}" python3 - "$1" <<'PY'
import os
import sys

import agent_conf

path = sys.argv[1]
conf = agent_conf.load(path)
mapping = {
    "CLAUDE_PLUGIN_OPTION_RUNTIME": "runtime",
    "CLAUDE_PLUGIN_OPTION_LANGUAGE": "language",
    "CLAUDE_PLUGIN_OPTION_MAX_AGENTS": "max_agents",
}
changed = False
for env_key, conf_key in mapping.items():
    value = os.environ.get(env_key, "")
    if not value:
        continue
    error = agent_conf.validate_value(conf_key, value)
    if error:
        sys.stderr.write(
            "agent-init.sh: ignored %s=%s, %s Kept %s.\n"
            % (env_key, value, error, conf.get(conf_key, ""))
        )
        continue
    conf[conf_key] = value
    changed = True
if changed:
    agent_conf.save(conf, path)
PY
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
  case "$PLUGIN_ROOT" in
    "$ROOT"/*) plugin_ref="${PLUGIN_ROOT#"$ROOT"/}";;
    *) plugin_ref="$PLUGIN_ROOT";;
  esac
  line="Run $plugin_ref/bin/agent-start.sh first. No work until the quiz says PASS."
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

CONF_FRESH=0
file_conf
file_empty agent_todo.txt
file_empty agent_completed.txt
file_empty agent_ideas.txt
file_empty agent_worktree.txt
dir_secrets
file_agents_md
file_gitignore

if [ "$CONF_FRESH" = 1 ]; then
  if [ "$MODE_GIVEN" = 1 ]; then
    set_permission_mode "$MODE"
  else
    ask_permission_mode
  fi
elif [ "$MODE_GIVEN" = 1 ]; then
  echo "kept: agent.conf permission_mode=$(conf_permission_mode), change it with: $PLUGIN_ROOT/bin/agent-settings.sh permission_mode <mode>"
fi
skip_warning_line

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
echo "Optional: if the auto-mode classifier denies the merge push to your integration branch, also allow \"Bash(git push origin main)\" (use your integration branch name)."

echo "For cloud sessions (claude.ai/code): the default cloud image already ships Playwright and Chromium. Paste this into the cloud environment's Setup script only if $PLUGIN_ROOT/bin/agent-runtime.sh browser prints none there, it is not a repo file, a plugin cannot set it:"
echo "npx playwright install --with-deps chromium || true"
echo "Skip this if you never run this repo in a cloud session."
