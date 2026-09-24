#!/usr/bin/env bash
# agent-city.sh — start, stop, check on, or demo the Agent City playground
# (bin/agent_city.py serve), the localhost visualizer for a running pipeline.
#
#   ./agent-city.sh start    start the server in the background, print its URL
#   ./agent-city.sh stop     stop it
#   ./agent-city.sh status   is it running, and where
#   ./agent-city.sh demo     same as start, URL opens straight into the demo scene
#   ./agent-city.sh answer ID TEXT...   the governor answers a question waiting on it
#   ./agent-city.sh pass ID             the governor hands a question to the owner
#   ./agent-city.sh pending             list what is waiting in the city
#   ./agent-city.sh -h       this help
#
# City dir: $AGENT_CITY_DIR, default $HOME/.cache/agent-city (the same dir the
# hook writes events.jsonl into). Port and idle timeout come from the
# project's agent.conf (city_port, city_idle_min), falling back to the
# plugin template when a key is missing there. Before starting, RAM and CPU
# are checked against max_usage_percent (bin/agent-resources.sh); over the
# cap, nothing is started.
#
# answer/pass/pending talk to an already-running server (bin/agent_city.py
# gov-answer / gov-pass / gov-pending). The governor may answer or pass a
# question; it never touches a permission request — only the owner, from the
# city page, may allow or deny one (requirements/city.md, "Interaction").
# decisions.jsonl lives under $AGENT_CITY_HOME, default $HOME/.claude/agent-city.

set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
. "$PLUGIN_ROOT/bin/agent.conf.default"
conf_read
. "$PLUGIN_ROOT/bin/agent-resources.sh"

usage() {
  cat <<'EOF'
agent-city.sh — start/stop/status/demo for the Agent City playground.

  ./agent-city.sh start    start the server in the background, print its URL
  ./agent-city.sh stop     stop it
  ./agent-city.sh status   is it running, and where
  ./agent-city.sh demo     same as start, URL opens straight into the demo scene
  ./agent-city.sh answer ID TEXT...   the governor answers a question waiting on it
  ./agent-city.sh pass ID             the governor hands a question to the owner
  ./agent-city.sh pending             list what is waiting in the city
  ./agent-city.sh -h       this help
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
  if ! resources_ok "$max_usage_percent"; then
    resources_line "$max_usage_percent"
    echo "not starting the city: over the resource cap"
    return 1
  fi

  existing=$(read_on) || existing=""
  if [ -n "$existing" ]; then
    port=$(printf '%s' "$existing" | awk '{print $2}')
    echo "CITY: http://127.0.0.1:${port}${suffix}"
    return 0
  fi

  mkdir -p "$CITY_DIR"
  nohup python3 "$SERVER" serve --dir "$CITY_DIR" --port "$city_port" \
    --idle-min "$city_idle_min" --gov-wait-sec "$city_governor_wait_sec" \
    --decisions "$CITY_HOME/decisions.jsonl" </dev/null >/dev/null 2>&1 &
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
    echo "CITY: failed to start" >&2
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
  *) usage; exit 2;;
esac
