#!/usr/bin/env bash
# agent-init.sh — set up a project to use this plugin. Idempotent: running
# it twice changes not one byte.
#
#   bin/agent-init.sh              set up the current project
#   bin/agent-init.sh <dir>        set up that project
#   bin/agent-init.sh --mode ... / --auto-update ...
#                                  gone: exit 2, one line naming where settings live
#                                  (/plugin -> Installed -> auto-pipeline -> Configure)
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
#   bin/agent-init.sh --no-measure [<dir>]
#                                  set up, but do not time the build and the guard tests
#   bin/agent-init.sh --no-branch [<dir>]
#                                  set up, but no working-branch step (the start makes the branch itself)
#   bin/agent-init.sh -h           print this block, create nothing, exit 0
#
# Creates, only when missing, in the project root: the four agent_*.txt task
# files (empty), .secrets/ (empty dir) and AGENTS.md (one line pointing at this
# plugin, relative to the project root when the plugin is packed inside it, e.g.
# .claude/auto-pipeline, absolute otherwise).
# Writes agent_repo.conf (this repo's facts, committed) when missing, or adds only the
# keys it lacks, never changing a value that is set (bin/agent_repo_init.py). It times
# the build and the guard tests once, only under the RAM/CPU cap, unless --no-measure.
# Adds .secrets/, agent_state.txt, agent_monitor.txt, agent_monitor.txt.tmp.*
# and .auto-pipeline/ to .gitignore, creating it when missing. Never
# overwrites a file already there.
#
# Asks nothing about settings and writes no settings file: they live only in
# /plugin -> Installed -> auto-pipeline -> Configure. After the setup it prints
# the lines of an old agent file moved into Configure (agent_conf.py migrate),
# the lines of plugin scopes of this folder brought up to date (agent_update.py
# sync), then one line "settings: /plugin -> Installed -> auto-pipeline -> Configure".
# When the Permission mode setting is bypassPermissions and ~/.claude/settings.json
# lacks "skipDangerousModePermissionPrompt": true, one line says new panes stop on
# the bypass warning screen. The file is only read, never written.
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
  -h|--help) sed -n '2,60p' "$0"; exit 0;;
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

SCOPE=""

ADD_PERMS=0
NO_MEASURE=""
NO_BRANCH=""
while [ $# -gt 0 ]; do
  case "$1" in
    --mode|--auto-update)
      echo "agent-init.sh: $1 is gone: settings change only in /plugin -> Installed -> auto-pipeline -> Configure" >&2
      exit 2;;
    --add-permissions) ADD_PERMS=1; shift;;
    --no-measure) NO_MEASURE="--no-measure"; shift;;
    --no-branch) NO_BRANCH="--no-branch"; shift;;
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

skip_warning_line() {
  local pm
  pm=$(python3 "$PLUGIN_ROOT/bin/agent_conf.py" get permission_mode 2>/dev/null </dev/null) || pm=""
  [ "$pm" = "bypassPermissions" ] || return 0
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

file_empty agent_todo.txt
file_empty agent_completed.txt
file_empty agent_ideas.txt
file_empty agent_worktree.txt
dir_secrets
file_agents_md
file_gitignore

repo_conf() {
  local cap
  cap=$(setting max_usage_percent 2>/dev/null) || cap=80
  case "$cap" in ''|*[!0-9]*) cap=80;; esac
  python3 "$(dirname "$0")/agent_repo_init.py" "$ROOT" $NO_MEASURE $NO_BRANCH --cap "$cap" \
    --resources "$(dirname "$0")/agent-resources.sh" </dev/null \
    || echo "agent_repo.conf: scan failed, nothing written"
}
repo_conf

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
if [ -n "$NO_BRANCH" ]; then wb_cmd=stored-working-branch; else wb_cmd=working-branch; fi
wb_allow=$(python3 "$PLUGIN_ROOT/bin/agent_conf.py" "$wb_cmd" "$ROOT" 2>/dev/null </dev/null) || wb_allow=""
[ -n "$wb_allow" ] || wb_allow="<your working branch>"
echo "Optional: if the auto-mode classifier denies the push of your working branch, also allow \"Bash(git push origin $wb_allow)\"."

echo "For cloud sessions (claude.ai/code): the default cloud image already ships Playwright and Chromium. Paste this into the cloud environment's Setup script only if $PLUGIN_ROOT/bin/agent-runtime.sh browser prints none there, it is not a repo file, a plugin cannot set it:"
echo "npx playwright install --with-deps chromium || true"
echo "Skip this if you never run this repo in a cloud session."

python3 "$PLUGIN_ROOT/bin/agent_conf.py" migrate "$ROOT" 2>/dev/null </dev/null || true
python3 "$PLUGIN_ROOT/bin/agent_update.py" sync "$ROOT" 2>/dev/null </dev/null || true
echo "settings: /plugin -> Installed -> auto-pipeline -> Configure"
echo "Setup done. /auto-pipeline:settings shows the settings; it never changes them."
echo "Main commands: /auto-pipeline:todo (see all open tasks), /auto-pipeline:question (answer the agents' questions)."
