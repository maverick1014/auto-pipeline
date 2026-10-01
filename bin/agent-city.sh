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
#   ./agent-city.sh join     join this repo's team relay (address + key, asked here)
#   ./agent-city.sh leave    leave this repo's team relay
#   ./agent-city.sh send     cloud sender: send this session's lines to the
#                            team relay named by the environment secret
#                            AGENT_CITY_RELAY (no page, no join file)
#   ./agent-city.sh relay-dev [port]   run the dev relay for a two-machine
#                            LAN test (no Cloudflare account); default
#                            port 8787, key asked here, needs Node 22.5+
#   ./agent-city.sh cloud-hooks   write this pipeline's city hooks into
#                            user-level settings ($HOME/.claude/settings.json)
#                            and a fixed copy of bin/ under $AGENT_CITY_HOME,
#                            for a cloud session opened above several repos
#                            (requirements/city.md, "Joining")
#   ./agent-city.sh install-shim   copy bin/agent-city-shim to
#                            $HOME/.local/bin/agent-city, so `agent-city` works
#                            from any folder (requirements/city.md, "Anywhere")
#   ./agent-city.sh remove-shim    remove that copy, if it is ours
#   ./agent-city.sh autostart   what the SessionStart hook runs: bring the city up
#                            by itself on a joined machine whose relay has the
#                            cloud page on; prints nothing, returns at once
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
# started. city_relay_sec (agent.conf, default 5) is passed to serve as
# --relay-sec, how often a joined team relay is synced.
#
# join/leave use bin/agent_city_relay.py (requirements/city.md, "Joining"):
# a per-repo join file at <main repo root>/.secrets/agent-city-relay, mode
# 0600, written only after the relay accepts the key. The team key is never
# an argv or on screen.
#
# answer/pass/pending talk to an already-running server (bin/agent_city.py
# gov-answer / gov-pass / gov-pending). The governor may answer or pass a
# question; it never touches a permission request — only the owner, from the
# city page, may allow or deny one (requirements/city.md, "Interaction").
# decisions.jsonl lives under $AGENT_CITY_HOME, default $HOME/.claude/agent-city.
#
# cloud-hooks (requirements/city.md, "Joining"): a cloud session opened on
# several repos at once starts above them (e.g. /home/user, not a repo), so
# none of their .claude/settings.json project hooks ever load -- the cloud
# pack's SessionStart sender and city hooks never run, no matter how many of
# the repos carry it. The fix lives one level up, in user-level settings,
# which the environment's Setup script (pasted by the owner, see
# skills/city/setup.md section 7) can write before Claude Code even starts:
# `agent-city.sh cloud-hooks` copies this plugin's bin/ to a fixed path under
# $AGENT_CITY_HOME and merges the same SessionStart send hook and city hooks
# (hooks/hooks.json's agent-city-hook.sh entries) into
# $HOME/.claude/settings.json. Each hook command there first checks that no
# project-level pack is already sending for this session
# (.claude/auto-pipeline/bin/agent-city-hook.sh under $CLAUDE_PROJECT_DIR) --
# when a session does start inside one packed repo, its own project hooks
# send, and the user-level ones stand down, so nothing is ever sent twice.
#
# Anywhere (requirements/city.md, "Anywhere"): outside a repo (cwd not
# inside a git work tree), start/status/join/leave still work -- plugin
# defaults only, no agent.conf from that folder. start/demo there sync every
# repo listed in $AGENT_CITY_HOME/joined-repos.txt, language from
# AGENT_CITY_LANG (en or zh, else zh); join/leave refuse and say to cd into
# the repo first.
#
# Cloud page (requirements/city.md, "Cloud page"): the marker
# $AGENT_CITY_HOME/cloud holds the relay hosts that said the cloud page is on
# (agent_city_relay.py read_cloud / set_cloud; join writes it). status prints
# "CLOUD: on <relay host>" or "CLOUD: off" after the TEAM line(s) of a joined
# machine, from the marker only -- it never talks to the relay -- and nothing
# for a machine that never joined. autostart is the SessionStart hook's verb
# (hooks/hooks.json): the work runs in a detached background subshell, so a
# session start never waits on the network. In order: a city server already
# running -> nothing; a cloud session (CLAUDE_CODE_REMOTE) -> nothing; this
# repo not joined, or no repo -> nothing, no network; the marker names this
# repo's relay host -> start; else one quiet `cloud --probe`, on -> start.
# start there is the plain start with --joined-list always, no browser.

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
agent-city.sh — start/stop/status/demo for the Agent City playground.

  ./agent-city.sh start    start the server in the background, print its URL
  ./agent-city.sh stop     stop it
  ./agent-city.sh status   is it running, and where
  ./agent-city.sh demo     same as start, URL opens straight into the demo scene
  ./agent-city.sh answer ID TEXT...   the governor answers a question waiting on it
  ./agent-city.sh pass ID             the governor hands a question to the owner
  ./agent-city.sh pending             list what is waiting in the city
  ./agent-city.sh join     join this repo's team relay (address + key, asked here)
  ./agent-city.sh leave    leave this repo's team relay
  ./agent-city.sh send     cloud sender: send this session's lines to the team relay
  ./agent-city.sh relay-dev [port]   run the dev relay for a two-machine LAN test
  ./agent-city.sh cloud-hooks   write the city hooks into user-level settings
  ./agent-city.sh install-shim   copy the agent-city command to ~/.local/bin, so it runs from any folder
  ./agent-city.sh remove-shim    remove that copy, if it is ours
  ./agent-city.sh autostart   what the session-start hook runs: start the city by itself
                           on a joined machine whose relay has the cloud page on
                           (prints nothing, returns at once)
  ./agent-city.sh -h       this help

Outside a repo: start/demo sync every repo listed in
$AGENT_CITY_HOME/joined-repos.txt (language from AGENT_CITY_LANG, en or zh,
else zh); status shows them; join/leave refuse there and say to cd into the
repo first.

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
: "${city_relay_sec:=5}"
SECRET_FILE="$PROJECT_ROOT/.secrets/agent-city-relay"
RELAY_MODULE="$PLUGIN_ROOT/bin/agent_city_relay.py"
CLOUD_FILE="$CITY_HOME/cloud"
# yes: do_start always passes --joined-list (autostart, also inside a repo)
START_JOINED=no

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
  # the city's own default); everything else (do_send, ...) keeps today's
  # $language from agent.conf/agent.conf.default.
  set --
  if [ "$OUTSIDE_REPO" = yes ]; then
    case "${AGENT_CITY_LANG:-}" in
      en|zh) language="$AGENT_CITY_LANG" ;;
      *) language="zh" ;;
    esac
  fi
  if [ "$OUTSIDE_REPO" = yes ] || [ "$START_JOINED" = yes ]; then
    set -- --joined-list "$CITY_HOME/joined-repos.txt"
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
    --relay-sec "$city_relay_sec" \
    --decisions "$CITY_HOME/decisions.jsonl" --world "$CITY_HOME/world.json" \
    --start-dir "$(pwd -P)" --lang "$language" "$@" \
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
  if [ "$OUTSIDE_REPO" = yes ]; then
    joined_list_lines
    cloud_lines_outside || true
  else
    team_line
    cloud_line || true
  fi
  return 0
}

# "CLOUD: on <relay host>" or "CLOUD: off" for a joined repo, nothing when it
# is not joined. From the marker only: no --probe, so no network. Never the key.
cloud_line() {
  out=$(python3 "$RELAY_MODULE" cloud --secret "$SECRET_FILE" \
          --cloud-file "$CLOUD_FILE" 2>/dev/null) || out="none"
  case "$out" in
    "on "*) echo "CLOUD: $out" ;;
    "off "*) echo "CLOUD: off" ;;
  esac
  return 0
}

# Outside a repo: one "CLOUD: on <host>" per joined relay host (each once, list
# order) that the marker names, else one "CLOUD: off" when a repo is joined,
# nothing when none is. Marker only, no network. Never the key.
cloud_lines_outside() {
  python3 -c '
import os
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
from urllib.parse import urlsplit

marked = rl.read_cloud(sys.argv[3])
hosts = []
for repo in rl.read_joined_list(sys.argv[2]):
    if not os.path.isdir(repo):
        continue
    joined = rl.read_join(os.path.join(repo, ".secrets", "agent-city-relay"))
    if not joined:
        continue
    host = urlsplit(joined["address"]).netloc
    if host not in hosts:
        hosts.append(host)
if hosts:
    on = [h for h in hosts if h in marked]
    if on:
        for h in on:
            print("CLOUD: on " + h)
    else:
        print("CLOUD: off")
' "$PLUGIN_ROOT/bin" "$CITY_HOME/joined-repos.txt" "$CLOUD_FILE"
}

# autostart (requirements/city.md, "Cloud page"): the SessionStart hook's verb.
# Prints nothing, exits 0 and comes back at once -- the checks (and any relay
# question) run in a detached background subshell with every stream on
# /dev/null, so a slow or dead relay never holds up a session start.
do_autostart() {
  (
    trap '' HUP
    autostart_work || true
  ) </dev/null >/dev/null 2>&1 &
  disown "$!" 2>/dev/null || true
  return 0
}

autostart_work() {
  # 1. a city server is already running
  read_on >/dev/null && return 0
  # 2. a cloud session sends only, it has no page
  [ -z "${CLAUDE_CODE_REMOTE:-}" ] || return 0
  # 3. not in a repo, or this repo is not joined: no network at all
  [ "$OUTSIDE_REPO" = no ] || return 0
  [ -f "$SECRET_FILE" ] || return 0
  state=$(python3 "$RELAY_MODULE" cloud --secret "$SECRET_FILE" \
            --cloud-file "$CLOUD_FILE" 2>/dev/null) || return 0
  case "$state" in
    "on "*) ;;
    "off "*)
      # 5. no marker for this relay: one quiet sync asks the relay
      state=$(python3 "$RELAY_MODULE" cloud --secret "$SECRET_FILE" \
                --cloud-file "$CLOUD_FILE" --probe 2>/dev/null) || return 0
      case "$state" in "on "*) ;; *) return 0 ;; esac ;;
    *) return 0 ;;
  esac
  # 4. the cloud is on: today's start, with the machine's joined list
  START_JOINED=yes
  do_start "" || true
  return 0
}

# "TEAM: not joined" or "TEAM: joined <relay host>". Never the key.
team_line() {
  python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
from urllib.parse import urlsplit
joined = rl.read_join(sys.argv[2])
if joined:
    print("TEAM: joined " + urlsplit(joined["address"]).netloc)
else:
    print("TEAM: not joined")
' "$PLUGIN_ROOT/bin" "$SECRET_FILE"
}

# Outside a repo: one "TEAM: joined <host> (<repo>)" per listed repo whose
# folder and join file are both there (list order), else "TEAM: not
# joined". Never the key.
joined_list_lines() {
  python3 -c '
import os
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
from urllib.parse import urlsplit

repos = rl.read_joined_list(sys.argv[2])
printed = False
for repo in repos:
    if not os.path.isdir(repo):
        continue
    joined = rl.read_join(os.path.join(repo, ".secrets", "agent-city-relay"))
    if not joined:
        continue
    print("TEAM: joined %s (%s)" % (urlsplit(joined["address"]).netloc, repo))
    printed = True
if not printed:
    print("TEAM: not joined")
' "$PLUGIN_ROOT/bin" "$CITY_HOME/joined-repos.txt"
}

# Cloud sender (requirements/city.md, "Joining": cloud sessions send only, no
# page). Reads the team relay from the environment secret AGENT_CITY_RELAY
# only -- it is never an argv and never printed, and the sender inherits it
# straight from this process's environment.
do_send() {
  if [ -z "${AGENT_CITY_RELAY:-}" ]; then
    echo "SEND: AGENT_CITY_RELAY is not set" >&2
    return 1
  fi

  if ! resources_ok "$max_usage_percent"; then
    resources_line "$max_usage_percent"
    echo "warning: over the resource cap; the sender is small, starting anyway"
  fi

  existing=$(read_on) || existing=""
  if [ -z "$existing" ]; then
    mkdir -p "$CITY_DIR"
    idle_sec=$((city_idle_min * 60))
    nohup python3 "$RELAY_MODULE" send --dir "$CITY_DIR" \
      --relay-sec "$city_relay_sec" --idle-sec "$idle_sec" --lang "$language" \
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
      echo "SEND: failed to start" >&2
      return 1
    fi
  fi

  host=$(send_host) || { echo "SEND: bad AGENT_CITY_RELAY" >&2; return 1; }
  echo "CITY: sending to the team relay ${host}"
  return 0
}

# The host for the line above: the address part of AGENT_CITY_RELAY (its
# first word) only, parsed with agent_city_relay's own check_address and
# urlsplit. Never the second word (the key).
send_host() {
  python3 -c '
import os
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
from urllib.parse import urlsplit

value = os.environ.get("AGENT_CITY_RELAY", "")
address = value.split()[0] if value.split() else ""
if rl.check_address(address):
    sys.exit(1)
print(urlsplit(address).netloc)
' "$PLUGIN_ROOT/bin"
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

# Join this repo's team relay (requirements/city.md, "Joining"). Refuses,
# before asking anything, when there is no origin remote, the origin is not
# shared (a local path or file:// URL -- origin_id() is empty), or .secrets/
# is not git-ignored. The team key is read with echo off and handed to
# agent_city_relay.py on stdin only -- never argv, never on screen.
do_join() {
  if [ "$OUTSIDE_REPO" = yes ]; then
    echo "JOIN: not inside a repo; cd into the repo you want to join, then run join" >&2
    exit 1
  fi
  origin=$(git -C "$PROJECT_ROOT" config --get remote.origin.url 2>/dev/null) || origin=""
  if [ -z "$origin" ]; then
    echo "JOIN: this repo has no origin remote to join a team relay for" >&2
    exit 1
  fi
  rid=$(python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
print(rl.origin_id(sys.argv[2]) or "")
' "$PLUGIN_ROOT/bin" "$origin")
  if [ -z "$rid" ]; then
    echo "JOIN: origin is a local path; this repo stays local" >&2
    exit 1
  fi
  if ! git -C "$PROJECT_ROOT" check-ignore -q -- ".secrets/agent-city-relay" >/dev/null 2>&1; then
    echo "JOIN: .secrets/ is not git-ignored here; add it to .gitignore first" >&2
    exit 1
  fi

  printf 'Relay address: ' >&2
  read -r address
  printf 'Team key (hidden): ' >&2
  read -rs key
  printf '\n' >&2

  rc=0
  out=$(printf '%s\n' "$key" | python3 "$RELAY_MODULE" \
          join --address "$address" --file "$SECRET_FILE" \
          --cloud-file "$CLOUD_FILE" 2>&1) || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "$out" >&2
    exit 1
  fi

  host="${out#RELAY: ok }"
  echo "JOINED: ${rid} -> ${host}"

  # Add this repo to the user-level joined list, once, never the key.
  python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
rl.add_joined(sys.argv[2], sys.argv[3])
' "$PLUGIN_ROOT/bin" "$CITY_HOME/joined-repos.txt" "$PROJECT_ROOT"
  return 0
}

# Dev relay for a two-machine LAN test (no Cloudflare account yet):
# bin/agent-city-relay-dev.mjs, the very Worker the owner would paste into
# Cloudflare, run behind a plain HTTP server on this machine's LAN, with an
# in-memory D1 stand-in. Needs Node 22.5+ (node:sqlite). The team key is
# read here with echo off and handed to the .mjs on stdin only -- never
# argv, never printed.
do_relay_dev() {
  port="${1:-8787}"
  if ! node -e "require('node:sqlite')" >/dev/null 2>&1; then
    echo "RELAY-DEV: needs Node 22.5 or newer" >&2
    exit 1
  fi

  printf 'Team key for the dev relay (hidden): ' >&2
  read -rs key
  printf '\n' >&2
  if [ -z "$key" ]; then
    echo "RELAY-DEV: no key entered" >&2
    exit 1
  fi

  # exec, not a pipe: a pipe forks node into a subshell, so a SIGINT sent to
  # this script's own pid (Ctrl-C) would never reach it. Process substitution
  # (not a here-string: bash before 5.1 writes those to a temp file) feeds
  # node's stdin from printf, a builtin, so the key touches neither argv nor
  # disk; exec then replaces this process with node in place, same pid.
  exec node "$PLUGIN_ROOT/bin/agent-city-relay-dev.mjs" --port "$port" < <(printf '%s\n' "$key")
}

# cloud-hooks (requirements/city.md, "Joining"): see the header comment
# above for the why. Never needs AGENT_CITY_RELAY to be set, never starts
# the sender, never prints the relay secret.
do_cloud_hooks() {
  bin_dst="$CITY_HOME/bin"
  mkdir -p "$bin_dst"
  for f in "$PLUGIN_ROOT"/bin/*; do
    name=$(basename "$f")
    [ "$name" = "__pycache__" ] && continue
    [ -f "$f" ] || continue
    cp -p "$f" "$bin_dst/$name"
  done
  echo "CITY: user hooks bin copied to $bin_dst"

  python3 - "$HOME/.claude/settings.json" "$PLUGIN_ROOT/hooks/hooks.json" "$CITY_HOME" <<'PY'
import json
import os
import sys

settings_path, src_hooks_path, city_home = sys.argv[1], sys.argv[2], sys.argv[3]

# Same guard on both commands: stand down when this session's project folder
# ($CLAUDE_PROJECT_DIR, where it started) is a repo that already carries the cloud pack (its own project hooks send
# instead), so a line is never written twice.
GUARD = ('[ ! -f "${CLAUDE_PROJECT_DIR:-/nonexistent}/.claude/auto-pipeline'
         '/bin/agent-city-hook.sh" ]')
SEND_CMD = ('[ -n "${AGENT_CITY_RELAY:-}" ] && %s && '
            'bash "%s/bin/agent-city.sh" send; exit 0') % (GUARD, city_home)
CITY_HOOK_CMD = ('[ -f "${AGENT_CITY_DIR:-$HOME/.cache/agent-city}/on" ] && %s && '
                 'bash "%s/bin/agent-city-hook.sh"; exit 0') % (GUARD, city_home)

existed = os.path.exists(settings_path)
if existed:
    with open(settings_path) as fh:
        raw = fh.read()
    try:
        data = json.loads(raw)
    except ValueError as exc:
        sys.stderr.write(
            "agent-city.sh cloud-hooks: %s is not valid JSON: %s\n"
            % (settings_path, exc))
        sys.exit(2)
else:
    data = {}

changed = not existed

hooks = data.setdefault("hooks", {})
session_start = hooks.setdefault("SessionStart", [])
has_send = any(hook.get("command", "") == SEND_CMD
               for entry in session_start for hook in entry.get("hooks", []))
if not has_send:
    session_start.append({"hooks": [{"type": "command", "command": SEND_CMD}]})
    changed = True

if os.path.exists(src_hooks_path):
    with open(src_hooks_path) as fh:
        src_hooks = json.load(fh).get("hooks", {})
    for event, entries in src_hooks.items():
        for entry in entries:
            if not any("agent-city-hook.sh" in h.get("command", "")
                       for h in entry.get("hooks", [])):
                continue
            matcher = entry.get("matcher")
            event_list = hooks.setdefault(event, [])
            has_city = any(
                e.get("matcher") == matcher and
                any(h.get("command", "") == CITY_HOOK_CMD for h in e.get("hooks", []))
                for e in event_list)
            if not has_city:
                new_entry = {"hooks": [{"type": "command", "command": CITY_HOOK_CMD}]}
                if matcher is not None:
                    new_entry["matcher"] = matcher
                event_list.append(new_entry)
                changed = True

if changed:
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    tmp_path = settings_path + ".tmp"
    with open(tmp_path, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp_path, settings_path)
    print("CITY: user hooks written to %s" % settings_path)
else:
    print("CITY: user hooks already there")
PY
}

do_leave() {
  if [ "$OUTSIDE_REPO" = yes ]; then
    echo "LEFT: not inside a repo; cd into the joined repo, then run leave" >&2
    exit 1
  fi
  if [ -f "$SECRET_FILE" ]; then
    rm -f "$SECRET_FILE"
    echo "LEFT: left the team relay"
  else
    echo "LEFT: was not joined"
  fi

  # Always drop this repo's line from the user-level joined list, even when
  # the join file was already gone.
  python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
rl.remove_joined(sys.argv[2], sys.argv[3])
' "$PLUGIN_ROOT/bin" "$CITY_HOME/joined-repos.txt" "$PROJECT_ROOT"
  return 0
}

# install-shim / remove-shim (requirements/city.md, "Anywhere"): put
# bin/agent-city-shim on the owner's PATH as ~/.local/bin/agent-city, so a
# plain terminal can run `agent-city ...` from any folder. A target that is
# not ours -- a symlink, a folder, or a file without our marker line -- is
# never touched, on either command.
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
  send) do_send;;
  answer) do_answer "$@";;
  pass) do_pass "$@";;
  pending) do_pending;;
  join) do_join;;
  leave) do_leave;;
  relay-dev) do_relay_dev "${2:-}";;
  cloud-hooks) do_cloud_hooks;;
  install-shim) do_install_shim;;
  remove-shim) do_remove_shim;;
  autostart) do_autostart;;
  *) usage; exit 2;;
esac
