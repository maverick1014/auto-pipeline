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
#   bin/agent-init.sh --auto-update on|off [<dir>]
#                                  save auto_update in the user file and apply
#                                  it (agent-settings.sh --user auto_update);
#                                  any other value exits 2, nothing created
#   bin/agent-init.sh --add-permissions [<dir>]
#                                  merge the permission block into the project's
#                                  .claude/settings.json (top-level
#                                  permissions.allow; other keys and entries
#                                  kept; no duplicates; file created when
#                                  missing). Invalid JSON or a wrong shape:
#                                  exit 1, file untouched. Nothing else is done.
#   bin/agent-init.sh --scope selected <repo path>...
#                                  run auto-pipeline only in those repos: merge
#                                  enabledPlugins["auto-pipeline@auto-pipeline"]=true
#                                  into each <repo>/.claude/settings.json (created
#                                  when missing, other keys kept), then set it false
#                                  in the user settings file (~/.claude/settings.json,
#                                  or $CLAUDE_CONFIG_DIR/settings.json; .bak copy
#                                  first). Invalid JSON anywhere: exit 1, nothing
#                                  written. One line per file changed.
#   bin/agent-init.sh --scope all  run in all repos: set it true in the user
#                                  settings file; repo files are left alone.
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
# CLAUDE_PLUGIN_OPTION_RUNTIME, CLAUDE_PLUGIN_OPTION_LANGUAGE,
# CLAUDE_PLUGIN_OPTION_MANAGER_MODEL (sets main_manager and task_manager) and
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
# Auto update: after the permission step. --auto-update given: saved. Else
# auto_update already in the user file: nothing. Else a terminal on stdin: one
# question on stderr, "Auto update: on (recommended) or off?" (Enter, EOF or
# anything else = on). Else on. Saved through agent-settings.sh --user.
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
  -h|--help) sed -n '2,72p' "$0"; exit 0;;
esac

# Plugin on/off per repo or per user. Python does the JSON. Args: all|selected,
# then repo paths. All files are checked first; any bad one = exit 1, no write.
scope_run() {
  python3 - "$@" <<'PY'
import json, os, shutil, sys

KEY = "auto-pipeline@auto-pipeline"
scope, repos = sys.argv[1], sys.argv[2:]
cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
user = os.path.join(cfg, "settings.json")

def load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as fh:
            text = fh.read()
        data = json.loads(text) if text.strip() else {}
    except ValueError as exc:
        sys.stderr.write("agent-init.sh: %s is not valid JSON (%s). Nothing written.\n" % (path, exc))
        sys.exit(1)
    if not isinstance(data, dict) or not isinstance(data.get("enabledPlugins", {}), dict):
        sys.stderr.write("agent-init.sh: %s has the wrong shape (enabledPlugins). Nothing written.\n" % path)
        sys.exit(1)
    return data

jobs = []
if scope == "selected":
    for r in repos:
        jobs.append((os.path.join(r, ".claude", "settings.json"), True, False))
    jobs.append((user, False, True))
else:
    jobs.append((user, True, True))
loaded = [(p, v, b, load(p)) for p, v, b in jobs]
for path, value, backup, data in loaded:
    ep = data.setdefault("enabledPlugins", {})
    if ep.get(KEY) is value:
        print("kept: %s (%s already %s)" % (path, KEY, str(value).lower()))
        continue
    existed = os.path.exists(path)
    ep[KEY] = value
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if backup and existed:
        shutil.copy2(path, path + ".bak")
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
    print("updated: %s (%s set to %s)" % (path, KEY, str(value).lower()))
PY
}

MODE=""
MODE_GIVEN=0
SCOPE=""

ADD_PERMS=0
AUTO_UPDATE=""
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
    --auto-update)
      if [ $# -lt 2 ]; then
        echo "agent-init.sh: --auto-update needs a value: on or off" >&2
        exit 2
      fi
      case "$2" in
        on|off) AUTO_UPDATE="$2";;
        *) echo "agent-init.sh: --auto-update must be on or off, got: $2" >&2; exit 2;;
      esac
      shift 2;;
    --add-permissions) ADD_PERMS=1; shift;;
    --scope)
      case "${2:-}" in
        all|selected) SCOPE="$2";;
        *) echo "agent-init.sh: --scope must be all or selected, got: ${2:-}" >&2; exit 2;;
      esac
      shift 2;;
    *) break;;
  esac
done

if [ -n "$SCOPE" ]; then
  if [ "$SCOPE" = selected ]; then
    if [ $# -eq 0 ]; then
      echo "agent-init.sh: --scope selected needs at least one repo path" >&2
      exit 2
    fi
    for d in "$@"; do
      [ -d "$d" ] || { echo "agent-init.sh: no such directory: $d" >&2; exit 2; }
    done
  fi
  scope_run "$SCOPE" "$@"
  exit $?
fi

TARGET="${1:-}"
if [ -n "$TARGET" ] && [ ! -d "$TARGET" ]; then
  echo "agent-init.sh: no such directory: $TARGET" >&2
  exit 2
fi

roots_read "$TARGET"
ROOT="$PROJECT_ROOT"

# Merge the permission block into <root>/.claude/settings.json. Python does the
# JSON, so it is never edited by hand. Exit 0 = merged or already there,
# 1 = file not valid JSON or wrong shape (nothing written).
add_permissions() {
  python3 - "$ROOT/.claude/settings.json" <<'PY'
import json, os, sys

RULES = [
    "Bash(git push origin --delete *)",
    "Bash(git branch -d *)",
    "Bash(git worktree remove *)",
    "Bash(git worktree prune)",
    "Bash(orca worktree rm *)",
    "Bash(orca terminal close *)",
]
path = sys.argv[1]
data = {}
if os.path.exists(path):
    try:
        with open(path) as fh:
            text = fh.read()
        data = json.loads(text) if text.strip() else {}
    except ValueError as exc:
        sys.stderr.write("agent-init.sh: %s is not valid JSON (%s). Nothing written. Fix it, or paste the block yourself.\n" % (path, exc))
        sys.exit(1)
if not isinstance(data, dict):
    sys.stderr.write("agent-init.sh: %s is not a JSON object. Nothing written.\n" % path)
    sys.exit(1)
perms = data.setdefault("permissions", {})
if not isinstance(perms, dict):
    sys.stderr.write("agent-init.sh: permissions in %s is not an object. Nothing written.\n" % path)
    sys.exit(1)
allow = perms.setdefault("allow", [])
if not isinstance(allow, list):
    sys.stderr.write("agent-init.sh: permissions.allow in %s is not a list. Nothing written.\n" % path)
    sys.exit(1)
added = [r for r in RULES if r not in allow]
if not added and os.path.exists(path):
    print("kept: .claude/settings.json (permissions already there)")
    sys.exit(0)
allow.extend(added)
os.makedirs(os.path.dirname(path), exist_ok=True)
tmp = path + ".tmp"
with open(tmp, "w") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
os.replace(tmp, path)
print("updated: .claude/settings.json (%d permission rules added)" % len(added))
PY
}

ask_add_permissions() {
  [ -t 0 ] || return 0
  printf 'Add these permissions to .claude/settings.json for you? (yes/no) [no]: ' >&2
  ans=""
  read -r ans || ans=""
  ans=$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')
  case "$ans" in
    y|yes) add_permissions || true;;
  esac
}

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

save_auto_update() {
  "$PLUGIN_ROOT/bin/agent-settings.sh" --user auto_update "$1"
}

auto_update_step() {
  if [ -n "$AUTO_UPDATE" ]; then
    save_auto_update "$AUTO_UPDATE"
    return 0
  fi
  if python3 "$PLUGIN_ROOT/bin/agent_conf.py" effective auto_update "$ROOT/agent.conf" >/dev/null 2>&1; then
    return 0
  fi
  ans=on
  if [ -t 0 ]; then
    printf 'Auto update: on (recommended) or off? [on/off, Enter = on]: ' >&2
    read -r ans || ans=""
    ans=$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')
    [ "$ans" = off ] || ans=on
  fi
  save_auto_update "$ans"
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
    "CLAUDE_PLUGIN_OPTION_MANAGER_MODEL": "main_manager",
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
    if conf_key == "main_manager":
        conf["task_manager"] = value
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

if [ "$ADD_PERMS" = 1 ]; then
  add_permissions
  exit $?
fi

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
auto_update_step
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

echo "Those permission rules go into .claude/settings.json in this project."
echo "A plugin cannot add permission rules by itself: either paste the block, or run $PLUGIN_ROOT/bin/agent-init.sh --add-permissions and it merges them for you."
ask_add_permissions
echo "Optional: if the auto-mode classifier denies the merge push to your integration branch, also allow \"Bash(git push origin main)\" (use your integration branch name)."

echo "For cloud sessions (claude.ai/code): the default cloud image already ships Playwright and Chromium. Paste this into the cloud environment's Setup script only if $PLUGIN_ROOT/bin/agent-runtime.sh browser prints none there, it is not a repo file, a plugin cannot set it:"
echo "npx playwright install --with-deps chromium || true"
echo "Skip this if you never run this repo in a cloud session."

echo "Setup done. To change a setting later: /auto-pipeline:settings, for example /auto-pipeline:settings language en"
echo "Main commands: /auto-pipeline:todo (see all open tasks), /auto-pipeline:question (answer the agents' questions)."
