#!/usr/bin/env bash
# agent-city.sh — start, stop, check on, or demo the Agent City playground
# (bin/agent_city.py serve), the localhost visualizer for a running pipeline.
# The city is local only: one server on 127.0.0.1, fed by the hooks on this
# computer. Nothing is sent anywhere.
#
#   ./agent-city.sh start    start the server in the background, print its URL
#   ./agent-city.sh stop     stop it
#   ./agent-city.sh status   is it running, and where
#   ./agent-city.sh demo     same as start, URL opens straight into the demo scene
#   ./agent-city.sh answer ID TEXT...   the governor answers a question waiting on it
#   ./agent-city.sh pass ID             the governor hands a question to the owner
#   ./agent-city.sh pending             list what is waiting in the city
#   ./agent-city.sh install-shim   copy bin/agent-city-shim to
#                            $HOME/.local/bin/agent-city, so `agent-city` works
#                            from any folder (requirements/city.md, "Anywhere")
#   ./agent-city.sh remove-shim    remove that copy, if it is ours
#   ./agent-city.sh -h       this help
#
# City dir: $AGENT_CITY_DIR, default $HOME/.cache/agent-city (the same dir the
# hook writes events.jsonl into). Port and idle timeout come from the
# project's agent.conf (city_port, city_idle_min), falling back to the
# plugin template when a key is missing there. AGENT_CITY_PORT, a whole
# number 1024-65535, wins over city_port for start/demo, inside or outside a
# repo (requirements/city.md, "Port anywhere"); any other non-empty value
# refuses to start. Before starting, RAM and CPU are checked against
# max_usage_percent (bin/agent-resources.sh); over the cap, nothing is
# started.
#
# answer/pass/pending talk to an already-running server (bin/agent_city.py
# gov-answer / gov-pass / gov-pending). The governor may answer or pass a
# question; it never touches a permission request — only the owner, from the
# city page, may allow or deny one (requirements/city.md, "Interaction").
# decisions.jsonl lives under $AGENT_CITY_HOME, default $HOME/.claude/agent-city.
#
# Anywhere (requirements/city.md, "Anywhere"): outside a repo (cwd not
# inside a git work tree), start/status still work -- plugin defaults only,
# no agent.conf from that folder, language from AGENT_CITY_LANG (en or zh,
# else zh).

set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read

# Outside a repo: plugin defaults only, this folder's own agent.conf (if
# any) is never read.
if [ "$(git -C "$PROJECT_CWD" rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ]; then
  OUTSIDE_REPO=no
else
  OUTSIDE_REPO=yes
fi

. "$PLUGIN_ROOT/bin/agent.conf.default"
[ "$OUTSIDE_REPO" = yes ] || conf_read
. "$PLUGIN_ROOT/bin/agent-resources.sh"

usage() {
  cat <<'EOF'
agent-city — start/stop/status/demo for the Agent City playground.

First time: run bin/agent-city.sh install-shim once to get the agent-city command (~/.local/bin).

  agent-city start              start the server in the background, print its URL
  agent-city stop               stop it
  agent-city status             is it running, and where
  agent-city demo               same as start, URL opens straight into the demo scene
  agent-city answer ID TEXT...  the governor answers a question waiting on it
  agent-city pass ID            the governor hands a question to the owner
  agent-city pending            list what is waiting in the city
  agent-city install-shim       copy the agent-city command to ~/.local/bin, so it runs from any folder
  agent-city remove-shim        remove that copy, if it is ours
  agent-city -h                 this help

AGENT_CITY_PORT=<1024-65535>   start/demo use this port instead of city_port,
                               inside or outside a repo.
EOF
}

CITY_DIR="${AGENT_CITY_DIR:-$HOME/.cache/agent-city}"
CITY_HOME="${AGENT_CITY_HOME:-$HOME/.claude/agent-city}"
ON_FILE="$CITY_DIR/on"
SERVER="$PLUGIN_ROOT/bin/agent_city.py"
: "${max_usage_percent:=80}"
: "${city_port:=4777}"
: "${city_idle_min:=30}"
: "${city_governor_wait_sec:=60}"

# True when something already answers on 127.0.0.1:<port> (short connect,
# 1s timeout) -- tells "another program holds the port" apart from a plain
# start failure.
port_busy() {
  python3 - "$1" >/dev/null 2>&1 <<'PY'
import socket
import sys

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(1)
try:
    s.connect(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(1)
s.close()
sys.exit(0)
PY
}

# Prints "pid port" and returns 0 when ON_FILE names a pid that is alive.
read_on() {
  [ -f "$ON_FILE" ] || return 1
  set -- $(cat "$ON_FILE" 2>/dev/null || true)
  pid="${1:-}"; port="${2:-}"
  [ -n "$pid" ] && [ -n "$port" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  printf '%s %s\n' "$pid" "$port"
}

do_start() {
  suffix="${1:-}"

  # AGENT_CITY_PORT (requirements/city.md, "Port anywhere"): a whole number
  # 1024-65535 wins over city_port, inside or outside a repo. Case pattern
  # first, before any arithmetic -- set -u, a value like "47 77" must never
  # reach -lt/-gt and crash the script.
  env_port="${AGENT_CITY_PORT:-}"
  case "$env_port" in
    '') : ;;
    *[!0-9]*)
      echo "CITY: AGENT_CITY_PORT is not a port number (1024-65535): $env_port" >&2
      return 1 ;;
    *)
      if [ "$env_port" -lt 1024 ] || [ "$env_port" -gt 65535 ]; then
        echo "CITY: AGENT_CITY_PORT is not a port number (1024-65535): $env_port" >&2
        return 1
      fi
      city_port="$env_port" ;;
  esac

  # Outside a repo: AGENT_CITY_LANG picks the language (en/zh, else zh --
  # the city's own default); inside one, $language comes from
  # agent.conf/agent.conf.default.
  if [ "$OUTSIDE_REPO" = yes ]; then
    case "${AGENT_CITY_LANG:-}" in
      en|zh) language="$AGENT_CITY_LANG" ;;
      *) language="zh" ;;
    esac
  fi
  if ! resources_ok "$max_usage_percent"; then
    resources_line "$max_usage_percent"
    echo "warning: over the resource cap; the city is small, starting anyway"
  fi

  existing=$(read_on) || existing=""
  if [ -n "$existing" ]; then
    port=$(printf '%s' "$existing" | awk '{print $2}')
    echo "CITY: http://127.0.0.1:${port}${suffix}"
    echo "CITY: already running; its settings stay. To start it again from here: stop it first, then start."
    return 0
  fi

  mkdir -p "$CITY_DIR"
  nohup python3 "$SERVER" serve --dir "$CITY_DIR" --port "$city_port" \
    --idle-min "$city_idle_min" --gov-wait-sec "$city_governor_wait_sec" \
    --decisions "$CITY_HOME/decisions.jsonl" --world "$CITY_HOME/world.json" \
    --start-dir "$(pwd -P)" --lang "$language" \
    </dev/null >/dev/null 2>&1 &
  disown "$!" 2>/dev/null || true

  step=0
  found=""
  while [ "$step" -lt 50 ]; do
    if found=$(read_on); then
      break
    fi
    found=""
    sleep 0.1
    step=$((step + 1))
  done
  if [ -z "$found" ]; then
    if port_busy "$city_port"; then
      echo "CITY: failed to start: port $city_port is already in use by another program; set AGENT_CITY_PORT to a free port and start again" >&2
    else
      echo "CITY: failed to start" >&2
    fi
    return 1
  fi
  port=$(printf '%s' "$found" | awk '{print $2}')
  echo "CITY: http://127.0.0.1:${port}${suffix}"
  echo "CITY: stops by itself after ${city_idle_min} min with no browser open"
  return 0
}

do_status() {
  found=$(read_on) || found=""
  if [ -n "$found" ]; then
    port=$(printf '%s' "$found" | awk '{print $2}')
    echo "CITY: running http://127.0.0.1:${port}"
  else
    echo "CITY: not running"
  fi
  return 0
}

do_stop() {
  found=$(read_on) || found=""
  if [ -z "$found" ]; then
    rm -f "$ON_FILE" 2>/dev/null || true
    echo "CITY: not running"
    return 0
  fi
  pid=$(printf '%s' "$found" | awk '{print $1}')
  kill -TERM "$pid" 2>/dev/null || true
  step=0
  while [ "$step" -lt 50 ] && kill -0 "$pid" 2>/dev/null; do
    sleep 0.1
    step=$((step + 1))
  done
  rm -f "$ON_FILE" 2>/dev/null || true
  echo "CITY: stopped"
  return 0
}

# The governor may answer or pass a question. It has no verb for a
# permission request — only the owner, from the city page, decides those
# (requirements/city.md, "Interaction"). Do not add one.
do_answer() {
  shift  # drop the verb
  id="${1:-}"
  [ -n "$id" ] || { usage; exit 2; }
  shift
  [ $# -ge 1 ] || { usage; exit 2; }
  python3 "$SERVER" gov-answer --dir "$CITY_DIR" "$id" "$@"
}

do_pass() {
  shift
  id="${1:-}"
  [ -n "$id" ] || { usage; exit 2; }
  python3 "$SERVER" gov-pass --dir "$CITY_DIR" "$id"
}

do_pending() {
  python3 "$SERVER" gov-pending --dir "$CITY_DIR"
}

do_install_shim() {
  marker="# auto-pipeline agent-city shim"
  src="$PLUGIN_ROOT/bin/agent-city-shim"
  dst_dir="$HOME/.local/bin"
  dst="$dst_dir/agent-city"

  if [ -L "$dst" ]; then
    echo "SHIM: $dst is not ours, left alone" >&2
    return 1
  fi
  if [ -e "$dst" ]; then
    if [ -d "$dst" ] || ! grep -qxF "$marker" "$dst" 2>/dev/null; then
      echo "SHIM: $dst is not ours, left alone" >&2
      return 1
    fi
  fi

  mkdir -p "$dst_dir"
  # temp file in the same folder, then mv: never a half-written shim, and no
  # leftover file whatever happens in between
  tmp="$dst_dir/.agent-city.$$"
  cp "$src" "$tmp"
  chmod 755 "$tmp"
  mv -f "$tmp" "$dst"
  echo "SHIM: installed $dst"

  case ":$PATH:" in
    *":$dst_dir:"*) ;;
    *) echo "SHIM: $dst_dir is not on your PATH; add to ~/.zshrc: export PATH=\"$dst_dir:\$PATH\"" ;;
  esac
  return 0
}

do_remove_shim() {
  marker="# auto-pipeline agent-city shim"
  dst="$HOME/.local/bin/agent-city"

  if [ -L "$dst" ]; then
    echo "SHIM: $dst is not ours, left alone" >&2
    return 1
  fi
  if [ -e "$dst" ]; then
    if [ -d "$dst" ] || ! grep -qxF "$marker" "$dst" 2>/dev/null; then
      echo "SHIM: $dst is not ours, left alone" >&2
      return 1
    fi
    rm -f "$dst"
    echo "SHIM: removed $dst"
    return 0
  fi

  echo "SHIM: not installed"
  return 0
}

[ $# -eq 0 ] && { usage; exit 2; }
case "$1" in
  -h|--help) usage; exit 0;;
  start) do_start "";;
  demo) do_start "/#demo";;
  status) do_status;;
  stop) do_stop;;
  answer) do_answer "$@";;
  pass) do_pass "$@";;
  pending) do_pending;;
  install-shim) do_install_shim;;
  remove-shim) do_remove_shim;;
  *) usage; exit 2;;
esac
