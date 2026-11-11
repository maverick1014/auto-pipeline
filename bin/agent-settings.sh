#!/usr/bin/env bash
# agent-settings.sh — read or change agent.conf. No agent, no tokens.
#   ./agent-settings.sh                 show all keys
#   ./agent-settings.sh <key> <value>   set one key, validated. e.g. ./agent-settings.sh worker sonnet-5:high
#   ./agent-settings.sh menu            pick the key and type the value
#   ./agent-settings.sh sync            add any key missing from agent.conf, template value
#   ./agent-settings.sh get <key>       one line: the value and where it comes from (user file, else agent.conf)
#   ./agent-settings.sh --user <key> <value>   set a key in ~/.claude/auto-pipeline.conf (this machine only)
#   ./agent-settings.sh statusline on|off|refresh   progress status line in Claude Code settings.json (needs no agent.conf)
# Takes effect at the next agent start.
# Run from a worktree: still reads/writes the MAIN repo's agent.conf; show, set and sync say so.
set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
CONF="$PROJECT_ROOT/agent.conf"
TEMPLATE="$PLUGIN_ROOT/bin/agent.conf.default"

ROOT_REAL=$(cd "$PROJECT_ROOT" && pwd -P)
STATE_REAL=$(cd "$STATE_DIR" && pwd -P)
WORKTREE_NOTE=""
if [ "$STATE_REAL" != "$ROOT_REAL" ]; then
  WORKTREE_NOTE="agent.conf: $ROOT_REAL/agent.conf (main repo copy; this worktree's own agent.conf is not used)"
fi
note() { [ -z "$WORKTREE_NOTE" ] || echo "$WORKTREE_NOTE"; }

case "${1:-}" in
  -h|--help) sed -n '2,11p' "$0"; exit 0;;
esac

PYBIN="$PLUGIN_ROOT/bin"
py() { PYTHONPATH="$PYBIN${PYTHONPATH:+:$PYTHONPATH}" python3 "$@"; }

userset() {
  py - "$1" "$2" <<'PY'
import os, sys, agent_conf as a
k, v = sys.argv[1], sys.argv[2]
if k not in a.USER_KEYS:
    sys.exit(f"not saved. {k} is not a user-file key. Keys: {', '.join(a.USER_KEYS)}")
msg = a.validate_value(k, v)
if msg: sys.exit(f"not saved. {k}={v} is invalid: {msg}")
path = a.user_conf_path()
try:
    with open(path, "r", encoding="utf-8") as fh: lines = fh.read().splitlines()
except FileNotFoundError:
    lines = []
except Exception as e:
    sys.exit(f"not saved. cannot read {a.display_path(path)}: {e}")
out, done = [], False
for line in lines:
    if "=" in line and not line.strip().startswith("#") and line.split("=", 1)[0].strip() == k:
        if not done: out.append(f"{k}={v}")
        done = True
    else:
        out.append(line)
if not done: out.append(f"{k}={v}")
try:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh: fh.write("\n".join(out) + "\n")
except Exception as e:
    sys.exit(f"not saved. cannot write {a.display_path(path)}: {e}")
print(f"saved: {k}={v} in {a.display_path(path)}")
PY
}

getv() {
  py - "$1" "$CONF" <<'PY'
import sys, agent_conf as a
k = sys.argv[1]
try: conf = a.load(sys.argv[2])
except Exception: conf = {}
v, src = a.effective(k, conf)
if v is not None:
    print(f"{v} (from {src})")
elif k in ("permission_mode", "cloud_permission_mode"):
    print("auto (default)")
elif k == "auto_update":
    print("on (default)")
else:
    sys.exit(f"{k} is not set in agent.conf")
PY
}

case "${1:-}" in
  get) [ $# -eq 2 ] || { sed -n '2,11p' "$0"; exit 2; }; getv "$2"; exit $?;;
  --user)
    [ $# -eq 3 ] || { sed -n '2,11p' "$0"; exit 2; }
    userset "$2" "$3" || exit 1
    if [ "$2" = auto_update ] && [ -f "$PLUGIN_ROOT/bin/agent_update.py" ]; then
      python3 "$PLUGIN_ROOT/bin/agent_update.py" apply "$3" || true
    fi
    exit 0;;
esac

statusline() {
  python3 - "$1" "$PLUGIN_ROOT" <<'PY'
import json, os, sys, tempfile
mode, root = sys.argv[1], sys.argv[2]
d = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
path = os.path.join(d, "settings.json")
cmd = '"%s/bin/agent-statusline.sh"' % root
refresh = mode == "refresh"
def done():
    if not refresh: print("statusline %s: %s" % (mode, path))
    sys.exit(0)
def stop(msg):
    if refresh: sys.exit(0)
    sys.exit(msg)
try:
    with open(path, "r", encoding="utf-8") as fh: data = json.load(fh)
    if not isinstance(data, dict): raise ValueError("not an object")
except FileNotFoundError:
    if refresh: sys.exit(0)
    data = {}
except Exception as e:
    stop("not changed. %s is not valid JSON, left as it is" % path)
sl = data.get("statusLine")
has = "statusLine" in data
ours = isinstance(sl, dict) and isinstance(sl.get("command"), str) and "/bin/agent-statusline.sh" in sl["command"]
if has and not ours:
    stop("not changed. the statusLine in %s is not ours, left as it is" % path)
if mode == "on":
    if ours and sl.get("command") == cmd: done()
    data["statusLine"] = {"type": "command", "command": cmd}
elif mode == "off":
    if not has: done()
    del data["statusLine"]
else:
    if not ours or sl.get("command") == cmd: sys.exit(0)
    sl["command"] = cmd
try:
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".settings.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False); fh.write("\n")
        try: os.chmod(tmp, os.stat(path).st_mode & 0o777)
        except OSError: pass
        os.replace(tmp, path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise
except Exception as e:
    stop("not changed. cannot write %s: %s" % (path, e))
done()
PY
}

case "${1:-}" in
  statusline)
    case "${2:-}" in
      on|off|refresh) [ $# -eq 2 ] || { sed -n '2,11p' "$0" >&2; exit 2; }; statusline "$2" || exit 1; exit 0;;
      *) echo "usage: agent-settings.sh statusline on|off|refresh" >&2; exit 2;;
    esac;;
esac

if [ ! -f "$CONF" ]; then
  echo "no agent.conf in $PROJECT_ROOT. Run $PLUGIN_ROOT/bin/agent-init.sh first." >&2
  exit 2
fi

show() {
  note; awk -F= 'NF==2{printf "  %-20s %s\n",$1,$2}' "$CONF"
  py - <<'PY'
import agent_conf as a
values, ignored = a.read_user_conf()
if values or ignored:
    print(f"user file: {a.display_path(a.user_conf_path())}")
    for k, v in values.items(): print(f"  {k:<20} {v}")
    for e in ignored: print(f"  ignored: {e}")
PY
}
setv() {
  note
  PYTHONPATH="$PLUGIN_ROOT/bin${PYTHONPATH:+:$PYTHONPATH}" python3 - "$1" "$2" "$CONF" "$TEMPLATE" <<'PY'
import sys, agent_conf as a
k, v, conf_path, template_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
c = a.load(conf_path)
template = a.load(template_path)
if k not in c and k not in template:
    sys.exit(f"unknown key: {k}. Keys: {', '.join(c)}")
msg = a.validate_value(k, v)
if msg: sys.exit(f"not saved. {k}={v} is invalid: {msg}")
if k in c:
    c[k] = v
    a.save(c, conf_path)
else:
    with open(conf_path, "rb") as fh: data = fh.read()
    with open(conf_path, "a") as fh:
        if data and not data.endswith(b"\n"): fh.write("\n")
        fh.write(f"{k}={v}\n")
print(f"saved: {k}={v}"); print("takes effect at the next agent start; running agents keep the old value")
PY
}
sync() {
  note
  PYTHONPATH="$PLUGIN_ROOT/bin${PYTHONPATH:+:$PYTHONPATH}" python3 - "$CONF" "$TEMPLATE" <<'PY'
import sys, agent_conf as a
conf_path, template_path = sys.argv[1], sys.argv[2]
existing = a.load(conf_path)
template = a.load(template_path)
missing = [k for k in template if k not in existing]
if not missing:
    print("agent.conf is up to date")
    sys.exit(0)
with open(conf_path, "rb") as fh: data = fh.read()
with open(conf_path, "a") as fh:
    if data and not data.endswith(b"\n"): fh.write("\n")
    for k in missing:
        v = template[k]
        fh.write(f"{k}={v}\n")
        print(f"added {k}={v}")
PY
}

case "${1:-}" in
  ""|show) show;;
  sync) sync;;
  menu)
    keys=$(awk -F= 'NF==2{print $1}' "$CONF"); i=0
    for k in $keys; do i=$((i+1)); printf '  %2d) %-20s %s\n' "$i" "$k" "$(awk -F= -v k="$k" '$1==k{print $2}' "$CONF")"; done
    printf 'key number: '; read -r n
    k=$(printf '%s\n' $keys | sed -n "${n}p"); [ -n "$k" ] || { echo "no such number"; exit 1; }
    printf 'new value for %s: ' "$k"; read -r v
    setv "$k" "$v";;
  -h|--help) sed -n '2,11p' "$0";;
  *) [ $# -eq 2 ] || { sed -n '2,11p' "$0"; exit 2; }; setv "$1" "$2";;
esac
