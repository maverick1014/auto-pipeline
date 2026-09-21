#!/usr/bin/env bash
# agent-settings.sh — read or change agent.conf. No agent, no tokens.
#   ./agent-settings.sh                 show all keys
#   ./agent-settings.sh <key> <value>   set one key, validated. e.g. ./agent-settings.sh worker sonnet-5:high
#   ./agent-settings.sh menu            pick the key and type the value
# Takes effect at the next agent start.
set -eu
cd "$(dirname "$0")"
CONF=agent.conf

show() { awk -F= 'NF==2{printf "  %-20s %s\n",$1,$2}' "$CONF"; }
setv() {
  python3 - "$1" "$2" <<'PY'
import sys, agent_conf as a
k, v = sys.argv[1], sys.argv[2]
c = a.load('agent.conf')
if k not in c: sys.exit(f"unknown key: {k}. Keys: {', '.join(c)}")
c[k] = v
msg = a.validate_value(k, v)
if msg: sys.exit(f"not saved. {k}={v} is invalid: {msg}")
a.save(c, 'agent.conf'); print(f"saved: {k}={v}")
PY
}

case "${1:-}" in
  "") show;;
  menu)
    keys=$(awk -F= 'NF==2{print $1}' "$CONF"); i=0
    for k in $keys; do i=$((i+1)); printf '  %2d) %-20s %s\n' "$i" "$k" "$(awk -F= -v k="$k" '$1==k{print $2}' "$CONF")"; done
    printf 'key number: '; read -r n
    k=$(printf '%s\n' $keys | sed -n "${n}p"); [ -n "$k" ] || { echo "no such number"; exit 1; }
    printf 'new value for %s: ' "$k"; read -r v
    setv "$k" "$v";;
  -h|--help) sed -n '2,6p' "$0";;
  *) [ $# -eq 2 ] || { sed -n '2,6p' "$0"; exit 2; }; setv "$1" "$2";;
esac
