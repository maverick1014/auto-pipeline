#!/usr/bin/env bash
# agent-settings.sh — read or change agent.conf. No agent, no tokens.
#   ./agent-settings.sh                 show all keys
#   ./agent-settings.sh <key> <value>   set one key, validated. e.g. ./agent-settings.sh worker sonnet-5:high
#   ./agent-settings.sh menu            pick the key and type the value
#   ./agent-settings.sh sync            add any key missing from agent.conf, template value
# Takes effect at the next agent start.
set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
CONF="$PROJECT_ROOT/agent.conf"
TEMPLATE="$PLUGIN_ROOT/bin/agent.conf.default"

case "${1:-}" in
  -h|--help) sed -n '2,7p' "$0"; exit 0;;
esac

if [ ! -f "$CONF" ]; then
  echo "no agent.conf in $PROJECT_ROOT. Run $PLUGIN_ROOT/bin/agent-init.sh first." >&2
  exit 2
fi

show() { awk -F= 'NF==2{printf "  %-20s %s\n",$1,$2}' "$CONF"; }
setv() {
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
  "") show;;
  sync) sync;;
  menu)
    keys=$(awk -F= 'NF==2{print $1}' "$CONF"); i=0
    for k in $keys; do i=$((i+1)); printf '  %2d) %-20s %s\n' "$i" "$k" "$(awk -F= -v k="$k" '$1==k{print $2}' "$CONF")"; done
    printf 'key number: '; read -r n
    k=$(printf '%s\n' $keys | sed -n "${n}p"); [ -n "$k" ] || { echo "no such number"; exit 1; }
    printf 'new value for %s: ' "$k"; read -r v
    setv "$k" "$v";;
  -h|--help) sed -n '2,7p' "$0";;
  *) [ $# -eq 2 ] || { sed -n '2,7p' "$0"; exit 2; }; setv "$1" "$2";;
esac
