#!/usr/bin/env bash
# agent-settings.sh — show the settings. No agent, no tokens. They change only in Claude Code:
# /plugin -> Installed -> auto-pipeline -> Configure
#   ./agent-settings.sh [show]      the settings table, with a * on a value that is not the default
#   ./agent-settings.sh get <key>   one line: the value and where it comes from
#   ./agent-settings.sh statusline on|off|refresh   progress status line in Claude Code settings.json, sets refreshInterval; refresh: only to a plugin cache root
set -eu
PLUGIN_ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
PYBIN="$PLUGIN_ROOT/bin"
CHANGE="settings change only in /plugin -> Installed -> auto-pipeline -> Configure"

usage() { sed -n '2,7p' "$0"; }
py() { PYTHONPATH="$PYBIN${PYTHONPATH:+:$PYTHONPATH}" python3 "$@"; }

getv() {
  py - "$1" <<'PY'
import sys, agent_conf as a
k = sys.argv[1]
try:
    print(f"{a.text(a.get(k))} (from {a.source(k)})")
except KeyError:
    sys.exit(f"unknown setting: {k}")
PY
}

statusline() {
  PYTHONPATH="$PYBIN${PYTHONPATH:+:$PYTHONPATH}" python3 - "$1" "$PLUGIN_ROOT" <<'PY'
import json, os, sys, tempfile
import agent_conf as ac
mode, root = sys.argv[1:3]
n = ac.get("statusline_refresh_sec")
d = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
path = os.path.join(d, "settings.json")
refresh = mode == "refresh"
if refresh:
    cache = os.path.realpath(os.path.join(d, "plugins", "cache")) + "/"
    target = None
    for cand in (root, os.environ.get("CLAUDE_PLUGIN_ROOT") or ""):
        if cand and os.path.realpath(cand).startswith(cache) and os.path.isfile(os.path.join(cand, "bin", "agent-statusline.sh")):
            target = cand
            break
    if target is None: sys.exit(0)
    root = target
cmd = '"%s/bin/agent-statusline.sh"' % root
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
    want = {"type": "command", "command": cmd}
    if n is not None: want["refreshInterval"] = n
    if ours and sl == want: done()
    data["statusLine"] = want
elif mode == "off":
    if not has: done()
    del data["statusLine"]
else:
    if not ours: sys.exit(0)
    if n is not None and sl.get("refreshInterval") == n and sl.get("command") == cmd: sys.exit(0)
    if n is None and sl.get("command") == cmd: sys.exit(0)
    sl["command"] = cmd
    if n is not None: sl["refreshInterval"] = n
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
      on|off|refresh) [ $# -eq 2 ] || { usage >&2; exit 2; }; statusline "$2" || exit 1; exit 0;;
      *) echo "usage: agent-settings.sh statusline on|off|refresh" >&2; exit 2;;
    esac;;
esac

case "${1:-}" in
  ""|show) [ $# -le 1 ] || { echo "$CHANGE"; exit 1; }; py "$PYBIN/agent_conf.py" show;;
  get) [ $# -eq 2 ] || { usage >&2; exit 2; }; getv "$2";;
  -h|--help) usage;;
  *) echo "$CHANGE"; exit 1;;
esac
