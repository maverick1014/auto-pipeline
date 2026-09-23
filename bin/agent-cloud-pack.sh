#!/usr/bin/env bash
# agent-cloud-pack.sh — lay this pipeline into a repo as plain committed
# files, for cloud sessions (claude.ai/code) that never install a plugin.
# They only read what is checked in: CLAUDE.md, .claude/settings.json
# (hooks and permission rules), .claude/skills/, .claude/agents/, scripts.
#
#   bin/agent-cloud-pack.sh <repo-path> [--language xx] [--update]
#   bin/agent-cloud-pack.sh -h                    print this block, exit 0
#
# <repo-path> may be any folder inside the target repo; the pack goes to its
# git toplevel (or the path itself, made absolute, when it is not a git
# repo). The source is the folder above this script's own bin/ (the plugin,
# or a plain clone of this repo). The source is never written.
#
# Lays, under the target repo root:
#   .claude/auto-pipeline/bin/        every file of the source bin/, same
#                                     bytes and mode, no __pycache__
#   .claude/auto-pipeline/PRINCIPLES.md   same bytes as the source
#   .claude/auto-pipeline/VERSION         source plugin.json version + "\n"
#   .claude/skills/<name>/SKILL.md   every source skill except init (the
#                                     built-in /init already does its job)
#                                     and cloud-pack (cannot run from a
#                                     packed copy)
#   .claude/agents/<name>.md         every source agent
#   .claude/settings.json            merged: every existing key and hook is
#                                     kept, one SessionStart hook and the
#                                     permission rules are added
#   CLAUDE.md                        one pointer line appended once, never
#                                     overwritten
#   agent.conf, agent_*.txt,
#   .secrets/, AGENTS.md             from running the packed agent-init.sh
#   .gitignore                       the task-file lines, plus the pack's
#                                     own __pycache__ line, each once
#
# --language xx   sets agent.conf's language (validated), new or existing.
# --update        refreshes bin/, PRINCIPLES.md, VERSION and the packed
#                 skills/agents to match this source, and drops any bin/
#                 script the source no longer has. Never touches agent.conf,
#                 agent_*.txt, CLAUDE.md, AGENTS.md, .gitignore, the user's
#                 own settings keys, or the user's own skills and agents.
#
# A second run with the same arguments changes not one byte. A pack whose
# VERSION differs from this source's, run without --update, is left alone:
# one line is printed telling you to run --update instead.
#
# Ends by printing the one-sentence cloud install (with the language now in
# use), a reminder that the Claude GitHub App must be installed on the
# target repo (or the cloud clone has no remote to push to), and a reminder
# to commit and push.
set -u
export PYTHONDONTWRITEBYTECODE=1

REPO_URL="https://github.com/maverick1014/auto-pipeline"

# Every later step (after the up-front validation) must stop the pack
# loudly on failure: one line naming the step, on stderr, non-zero exit,
# and the success footer never printed. Never fail silently.
die() {
  echo "agent-cloud-pack.sh: $1 failed" >&2
  exit 1
}

case "${1:-}" in
  -h|--help) sed -n '2,49p' "$0"; exit 0;;
esac

. "$(dirname "$0")/agent-roots.sh"

# ---- the source must look like the plugin ----
for need in bin skills agents PRINCIPLES.md .claude-plugin/plugin.json; do
  if [ ! -e "$PLUGIN_ROOT/$need" ]; then
    echo "agent-cloud-pack.sh: source is missing $need (looked in $PLUGIN_ROOT)" >&2
    exit 2
  fi
done

# ---- args ----
if [ "$#" -eq 0 ]; then
  echo "agent-cloud-pack.sh: repo path required. See -h." >&2
  exit 2
fi

REPO_PATH="$1"; shift

LANGUAGE=""
UPDATE=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help) sed -n '2,49p' "$0"; exit 0;;
    --language)
      if [ "$#" -lt 2 ]; then
        echo "agent-cloud-pack.sh: --language needs a value" >&2
        exit 2
      fi
      LANGUAGE="$2"; shift 2;;
    --update) UPDATE=1; shift;;
    *)
      echo "agent-cloud-pack.sh: unknown flag: $1" >&2
      exit 2;;
  esac
done

if [ ! -d "$REPO_PATH" ]; then
  echo "agent-cloud-pack.sh: no such directory: $REPO_PATH" >&2
  exit 2
fi

# ---- target: the git toplevel of repo-path, else repo-path itself, absolute ----
TARGET=$(git -C "$REPO_PATH" rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "$TARGET" ]; then
  TARGET=$(cd "$REPO_PATH" && pwd -P)
fi

# ---- validate everything before writing anything ----
if [ -n "$LANGUAGE" ]; then
  if ! LANG_ERR=$(PYTHONPATH="$PLUGIN_ROOT/bin${PYTHONPATH:+:$PYTHONPATH}" python3 - "$LANGUAGE" 2>&1 <<'PY'
import sys
import agent_conf
msg = agent_conf.validate_value("language", sys.argv[1])
if msg:
    sys.stderr.write(msg)
    sys.exit(1)
PY
  ); then
    echo "agent-cloud-pack.sh: bad --language '$LANGUAGE': $LANG_ERR" >&2
    exit 2
  fi
fi

SETTINGS_JSON="$TARGET/.claude/settings.json"
if [ -f "$SETTINGS_JSON" ]; then
  if ! JSON_ERR=$(python3 -c "
import json, sys
with open(sys.argv[1]) as fh:
    json.load(fh)
" "$SETTINGS_JSON" 2>&1); then
    echo "agent-cloud-pack.sh: $SETTINGS_JSON is not valid JSON: $JSON_ERR" >&2
    exit 2
  fi
fi

SRC_VER=$(python3 -c "
import json, sys
with open(sys.argv[1]) as fh:
    print(json.load(fh)['version'])
" "$PLUGIN_ROOT/.claude-plugin/plugin.json")

PACK="$TARGET/.claude/auto-pipeline"

if [ -f "$PACK/VERSION" ]; then
  OLD_VER=$(cat "$PACK/VERSION")
  if [ "$OLD_VER" != "$SRC_VER" ] && [ "$UPDATE" -ne 1 ]; then
    echo "pack is $OLD_VER, source is $SRC_VER: run bin/agent-cloud-pack.sh $REPO_PATH --update to refresh it"
    exit 0
  fi
fi

# ---- lay bin/, PRINCIPLES.md, VERSION, the packed skills and agents ----
PYTHONPATH="$PLUGIN_ROOT/bin${PYTHONPATH:+:$PYTHONPATH}" python3 - "$PLUGIN_ROOT" "$TARGET" "$SRC_VER" "$UPDATE" <<'PY' || die "laying the pack files"
import filecmp
import os
import shutil
import stat
import sys

SRC, TARGET, SRC_VER, UPDATE = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
PACK = os.path.join(TARGET, ".claude", "auto-pipeline")


def status(prefix, name):
    print("%s: %s" % (prefix, name))


def same_bytes_and_mode(a, b):
    try:
        if stat.S_IMODE(os.stat(a).st_mode) != stat.S_IMODE(os.stat(b).st_mode):
            return False
    except OSError:
        return False
    return filecmp.cmp(a, b, shallow=False)


def sync_file(src, dst, label, always_refresh):
    exists = os.path.exists(dst)
    if not exists:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        status("created", label)
    elif always_refresh:
        if same_bytes_and_mode(src, dst):
            status("kept", label)
        else:
            shutil.copy2(src, dst)
            status("updated", label)
    else:
        status("kept", label)


def transform(text):
    return (text.replace("${CLAUDE_PLUGIN_ROOT}", ".claude/auto-pipeline")
                .replace("/auto-pipeline:", "/"))


def sync_transformed(src, dst, label, always_refresh):
    with open(src) as fh:
        text = transform(fh.read())
    exists = os.path.exists(dst)
    if not exists:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w") as fh:
            fh.write(text)
        status("created", label)
        return
    if always_refresh:
        with open(dst) as fh:
            current = fh.read()
        if current == text:
            status("kept", label)
        else:
            with open(dst, "w") as fh:
                fh.write(text)
            status("updated", label)
    else:
        status("kept", label)


# ---- bin/ ----
src_bin = os.path.join(SRC, "bin")
pack_bin = os.path.join(PACK, "bin")
os.makedirs(pack_bin, exist_ok=True)
src_names = sorted(n for n in os.listdir(src_bin)
                    if os.path.isfile(os.path.join(src_bin, n)))
for name in src_names:
    sync_file(os.path.join(src_bin, name), os.path.join(pack_bin, name),
              ".claude/auto-pipeline/bin/%s" % name, UPDATE)
if UPDATE:
    for name in sorted(os.listdir(pack_bin)):
        if name == "__pycache__":
            continue
        path = os.path.join(pack_bin, name)
        if os.path.isfile(path) and name not in src_names:
            os.remove(path)
            status("removed", ".claude/auto-pipeline/bin/%s" % name)

# ---- PRINCIPLES.md ----
sync_file(os.path.join(SRC, "PRINCIPLES.md"), os.path.join(PACK, "PRINCIPLES.md"),
          ".claude/auto-pipeline/PRINCIPLES.md", UPDATE)

# ---- VERSION ----
version_path = os.path.join(PACK, "VERSION")
version_text = SRC_VER + "\n"
version_label = ".claude/auto-pipeline/VERSION"
if not os.path.exists(version_path):
    with open(version_path, "w") as fh:
        fh.write(version_text)
    status("created", version_label)
elif UPDATE:
    with open(version_path) as fh:
        current = fh.read()
    if current != version_text:
        with open(version_path, "w") as fh:
            fh.write(version_text)
        status("updated", version_label)
    else:
        status("kept", version_label)
else:
    status("kept", version_label)

# ---- skills, except init (the built-in /init already did its job) and
# cloud-pack (cannot run from a packed copy) ----
SKIP_SKILLS = {"init", "cloud-pack"}
skills_dir = os.path.join(SRC, "skills")
if os.path.isdir(skills_dir):
    for name in sorted(os.listdir(skills_dir)):
        if name in SKIP_SKILLS:
            continue
        src_skill = os.path.join(skills_dir, name, "SKILL.md")
        if not os.path.isfile(src_skill):
            continue
        dst_skill = os.path.join(TARGET, ".claude", "skills", name, "SKILL.md")
        sync_transformed(src_skill, dst_skill,
                          ".claude/skills/%s/SKILL.md" % name, UPDATE)

# ---- agents ----
agents_dir = os.path.join(SRC, "agents")
if os.path.isdir(agents_dir):
    for name in sorted(os.listdir(agents_dir)):
        if not name.endswith(".md"):
            continue
        src_agent = os.path.join(agents_dir, name)
        dst_agent = os.path.join(TARGET, ".claude", "agents", name)
        sync_transformed(src_agent, dst_agent, ".claude/agents/%s" % name, UPDATE)
PY

# ---- run the packed agent-init.sh, not the source one, so AGENTS.md gets
# the relative path. Clear inherited enable-time options first so only
# --language (below) counts. ----
CONF="$TARGET/agent.conf"
CONF_EXISTED=0
[ -f "$CONF" ] && CONF_EXISTED=1

unset CLAUDE_PLUGIN_OPTION_RUNTIME CLAUDE_PLUGIN_OPTION_LANGUAGE CLAUDE_PLUGIN_OPTION_MAX_AGENTS

if [ "$CONF_EXISTED" -eq 0 ] && [ -n "$LANGUAGE" ]; then
  INIT_OUT=$(CLAUDE_PLUGIN_OPTION_LANGUAGE="$LANGUAGE" "$PACK/bin/agent-init.sh" "$TARGET") || die "agent-init.sh"
else
  INIT_OUT=$("$PACK/bin/agent-init.sh" "$TARGET") || die "agent-init.sh"
fi

# ---- show agent-init.sh's file lines and its cloud Setup-script hint, but
# not the permission JSON block or the two lines asking the human to paste
# it: the pack merges those rules into .claude/settings.json itself, below,
# so telling him to paste them too would be false. ----
FILTERED_OUT=$(python3 - "$INIT_OUT" <<'PY' || die "agent-init.sh"
import sys

lines = sys.argv[1].splitlines()
out = []
in_json = False
drop = (
    "Paste that permission block into .claude/settings.json in this project.",
    "A plugin cannot add permission rules by itself, so a human must paste it.",
)
for line in lines:
    if not in_json and line == "{":
        in_json = True
        continue
    if in_json:
        if line == "}":
            in_json = False
        continue
    if line in drop:
        continue
    out.append(line)

cleaned = []
prev_blank = False
for line in out:
    blank = line.strip() == ""
    if blank and prev_blank:
        continue
    cleaned.append(line)
    prev_blank = blank
while cleaned and cleaned[0].strip() == "":
    cleaned.pop(0)
while cleaned and cleaned[-1].strip() == "":
    cleaned.pop()

print("\n".join(cleaned))
PY
)
printf '%s\n' "$FILTERED_OUT"

if [ "$CONF_EXISTED" -eq 1 ] && [ -n "$LANGUAGE" ]; then
  CUR_LANG=$(awk -F= '$1=="language"{print $2}' "$CONF")
  if [ "$CUR_LANG" != "$LANGUAGE" ]; then
    ( cd "$TARGET" && CLAUDE_PROJECT_DIR="$TARGET" "$PACK/bin/agent-settings.sh" language "$LANGUAGE" >/dev/null ) \
      || die "agent-settings.sh"
  fi
fi

# ---- the permission block agent-init.sh printed is the single source of
# the rules: lines from "{" to the matching "}" ----
PERM_JSON=$(printf '%s\n' "$INIT_OUT" | awk '/^\{$/{p=1} p{print} /^\}$/{if(p){exit}}')
[ -n "$PERM_JSON" ] || die "permission block parse"
PERM_FILE=$(mktemp)
trap 'rm -f "$PERM_FILE"' EXIT
printf '%s\n' "$PERM_JSON" > "$PERM_FILE"
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$PERM_FILE" >/dev/null 2>&1 \
  || die "permission block parse"

# ---- merge .claude/settings.json: keep every existing key and hook ----
python3 - "$SETTINGS_JSON" "$PERM_FILE" <<'PY' || die "settings.json"
import json
import os
import sys

settings_path, perm_path = sys.argv[1], sys.argv[2]
HOOK_MARKER = ".claude/auto-pipeline/bin/agent-start.sh"
HOOK_CMD = 'bash "$CLAUDE_PROJECT_DIR"/.claude/auto-pipeline/bin/agent-start.sh'

with open(perm_path) as fh:
    perm_block = json.load(fh)
rules = perm_block.get("permissions", {}).get("allow", [])

existed = os.path.exists(settings_path)
if existed:
    with open(settings_path) as fh:
        data = json.load(fh)
else:
    data = {}

changed = not existed

hooks = data.setdefault("hooks", {})
session_start = hooks.setdefault("SessionStart", [])
has_hook = any(HOOK_MARKER in hook.get("command", "")
               for entry in session_start for hook in entry.get("hooks", []))
if not has_hook:
    session_start.append({"hooks": [{"type": "command", "command": HOOK_CMD}]})
    changed = True

permissions = data.setdefault("permissions", {})
allow = permissions.setdefault("allow", [])
for rule in rules:
    if rule not in allow:
        allow.append(rule)
        changed = True

if changed:
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    print("merged: the permission rules into .claude/settings.json")
else:
    print("kept: .claude/settings.json")
PY

# ---- .gitignore: keep the pack's own __pycache__ out, once ----
GITIGNORE="$TARGET/.gitignore"
PYCACHE_LINE=".claude/auto-pipeline/bin/__pycache__/"
touch "$GITIGNORE" || die ".gitignore"
if ! grep -qxF "$PYCACHE_LINE" "$GITIGNORE" 2>/dev/null; then
  printf '%s\n' "$PYCACHE_LINE" >> "$GITIGNORE" || die ".gitignore"
fi

# ---- CLAUDE.md: the pointer line, appended once, never overwritten ----
CLAUDE_MD="$TARGET/CLAUDE.md"
POINTER='Run .claude/auto-pipeline/bin/agent-start.sh first. Follow its output. No work until the quiz says PASS.'
if [ -f "$CLAUDE_MD" ]; then
  if ! grep -qxF "$POINTER" "$CLAUDE_MD" 2>/dev/null; then
    if [ -s "$CLAUDE_MD" ] && [ -n "$(tail -c1 "$CLAUDE_MD")" ]; then
      printf '\n' >> "$CLAUDE_MD" || die "CLAUDE.md"
    fi
    printf '%s\n' "$POINTER" >> "$CLAUDE_MD" || die "CLAUDE.md"
  fi
else
  printf '%s\n' "$POINTER" > "$CLAUDE_MD" || die "CLAUDE.md"
fi

# ---- language in use, for the one-sentence install below ----
if [ -n "$LANGUAGE" ]; then
  LANG_IN_USE="$LANGUAGE"
else
  LANG_IN_USE=$(awk -F= '$1=="language"{print $2}' "$CONF" 2>/dev/null)
fi

echo
echo "Commit and push so a cloud session can read this:"
echo "  git add .claude CLAUDE.md AGENTS.md agent.conf agent_*.txt .gitignore"
echo "  git commit -m 'auto-pipeline: lay the cloud pack'"
echo "  git push"
echo
echo "The Claude GitHub App must be installed on this repo, or the cloud clone has no remote to push to."
echo
echo "To set up any other repo the same way, paste this into a fresh cloud session of it, then commit and push:"
echo "git clone $REPO_URL /tmp/ap && /tmp/ap/bin/agent-cloud-pack.sh . --language $LANG_IN_USE"
