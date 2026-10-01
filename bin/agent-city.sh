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
#   ./agent-city.sh cloud-build <dir> --d1-id <id> [--d1-name <name>] [--name <worker name>]
#                            make the folder the cloud page is deployed from
#                            (no network, no wrangler, no login)
#   ./agent-city.sh cloud-deploy   the owner's, in his own terminal only: ask the
#                            D1 database id, build into $AGENT_CITY_HOME/cloud-site,
#                            run `npx wrangler deploy` there
#   ./agent-city.sh cloud-talk on    the owner's, in his own terminal only: ask the
#                            talk key (hidden), let the cloud page send messages
#                            to this machine's sessions
#   ./agent-city.sh cloud-talk off   stop that (no terminal needed)
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
#
# cloud-build / cloud-deploy (requirements/city.md, "Cloud page"; the steps the
# owner follows are skills/city/setup.md sections 11-15). Logins, keys and the
# deploy are the owner's: no agent types, prints or stores a key or a token,
# and no agent runs a login or the deploy. cloud-build only copies files and
# writes <dir>/wrangler.jsonc: worker.js (bin/agent-city-cloud.js),
# site/index.html (bin/agent-city.html, byte for byte), site/assets
# (bin/agent-city-assets). The id (a UUID, not a secret) is checked before
# anything is written. It is built anew each time: only <dir>/site,
# <dir>/worker.js and <dir>/wrangler.jsonc are ever removed or replaced, and a
# folder that is not empty and not an earlier build of this command (no
# wrangler.jsonc of ours in it) is refused. No Access value, key or e-mail goes
# into any file: those are typed in the dashboard (the config has keep_vars).
# cloud-deploy refuses without a terminal on stdin (exit 2, nothing runs); with
# one it asks the database id (Enter keeps the one remembered in
# $AGENT_CITY_HOME/cloud-site.conf, the id only), builds, then runs
# `npx wrangler deploy` in $AGENT_CITY_HOME/cloud-site. It never runs a
# wrangler login: when the deploy fails it tells the owner to type that himself.
#
# cloud-talk on | off (requirements/city.md, "Cloud page", talk from the cloud
# page): `on` is the owner's, in his own terminal, inside a joined repo. It
# refuses without a terminal on stdin (exit 2: nothing asked, sent or saved), asks
# the talk key with echo off ("Talk key (hidden): "), hands it to
# agent_city_relay.py talk on on stdin only, and the relay must take it before
# anything is saved: the key goes to $AGENT_CITY_HOME/cloud-talk (mode 0600, one
# line "<relay host> <talk key>"). `off` needs no terminal and always works: in
# a joined repo it tells the relay, then forgets the key here; outside a repo,
# or in a repo that has not joined, it removes the whole file, no request. status prints "CLOUD TALK: on <relay host>" or
# "CLOUD TALK: off" right after the CLOUD line, from that file only -- no
# network, never the key.

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
  ./agent-city.sh cloud-build <dir> --d1-id <id> [--d1-name <name>] [--name <worker name>]
                           make the folder the cloud page is deployed from
                           (no network, no login)
  ./agent-city.sh cloud-deploy   deploy the cloud page to your Cloudflare account
                           (yours to run, in your own terminal)
  ./agent-city.sh cloud-talk on    let the cloud page send messages to your sessions
                           (yours to run, in your own terminal; asks the talk key)
  ./agent-city.sh cloud-talk off   stop that
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
TALK_FILE="$CITY_HOME/cloud-talk"
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
    talk_lines_outside || true
  else
    team_line
    cloud_line || true
    talk_line || true
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

# "CLOUD TALK: on <relay host>" or "CLOUD TALK: off" for a joined repo, nothing
# when it is not joined. From the talk file only, no network. Never the key.
talk_line() {
  out=$(python3 "$RELAY_MODULE" talk --secret "$SECRET_FILE" \
          --talk-file "$TALK_FILE" status 2>/dev/null) || out="none"
  case "$out" in
    "on "*) echo "CLOUD TALK: $out" ;;
    "off "*) echo "CLOUD TALK: off" ;;
  esac
  return 0
}

# Outside a repo: one "CLOUD TALK: on <host>" per joined relay host (each once,
# list order) that the talk file names, else one "CLOUD TALK: off" when a repo
# is joined, nothing when none is. Talk file only, no network. Never the key.
talk_lines_outside() {
  python3 -c '
import os
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
from urllib.parse import urlsplit

held = rl.read_talk(sys.argv[3])
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
    on = [h for h in hosts if h in held]
    if on:
        for h in on:
            print("CLOUD TALK: on " + h)
    else:
        print("CLOUD TALK: off")
' "$PLUGIN_ROOT/bin" "$CITY_HOME/joined-repos.txt" "$TALK_FILE"
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

# True when $1 is a UUID (8-4-4-4-12 hex digits), the shape of a D1 database id.
# The case pattern fixes the length first, so a value with a newline in it
# cannot slip through grep's line by line matching.
is_uuid() {
  case "$1" in
    ????????-????-????-????-????????????) ;;
    *) return 1 ;;
  esac
  printf '%s\n' "$1" | LC_ALL=C grep -Eq \
    '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
}

# True when <dir>/wrangler.jsonc is one cloud-build wrote (its three fixed
# lines), so a folder of somebody's own project is never touched.
cloud_is_ours() {
  [ -f "$1/wrangler.jsonc" ] || return 1
  grep -Fq '"main": "worker.js"' "$1/wrangler.jsonc" || return 1
  grep -Fq '"directory": "./site"' "$1/wrangler.jsonc" || return 1
  grep -Fq '"binding": "DB"' "$1/wrangler.jsonc" || return 1
  return 0
}

# Prints wrangler.jsonc: plain JSON (always valid, python3 writes it). The
# asset version (the ?v= of the asset addresses) is the plugin version, else a
# time stamp; only letters, digits, dot, dash, underscore, at most 32 long.
# args: worker name, D1 name, D1 id, language, path of plugin.json
cloud_config_json() {
  python3 - "$@" <<'PY'
import json
import re
import sys
import time

name, d1_name, d1_id, lang, plugin_json = sys.argv[1:6]
version = ""
try:
    with open(plugin_json) as fh:
        version = str(json.load(fh).get("version", ""))
except (OSError, ValueError, AttributeError):
    pass
version = re.sub(r"[^A-Za-z0-9._-]", "", version)[:32]
if not version:
    version = time.strftime("%Y%m%d%H%M%S")
config = {
    "name": name,
    "main": "worker.js",
    "compatibility_date": "2026-09-01",
    "keep_vars": True,
    "workers_dev": True,
    "assets": {"directory": "./site", "binding": "ASSETS", "run_worker_first": True},
    "d1_databases": [{"binding": "DB", "database_name": d1_name, "database_id": d1_id}],
    "vars": {"CITY_LANG": lang, "CITY_ASSET_V": version},
}
print(json.dumps(config, indent=2))
PY
}

# The work of cloud-build, silent on success. args: folder, D1 id, D1 name,
# worker name. Everything is checked before anything is written; it exits 2 on
# a bad argument or a folder that is not ours, 1 when it cannot build.
cloud_build_core() {
  dir="$1"; d1_id="$2"; d1_name="$3"; wname="$4"

  if [ -z "$dir" ]; then
    echo "CLOUD: usage: agent-city.sh cloud-build <dir> --d1-id <id> [--d1-name <name>] [--name <worker name>]" >&2
    exit 2
  fi
  if ! is_uuid "$d1_id"; then
    echo "CLOUD: --d1-id must be the D1 database id (letters and digits in groups, like xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx); nothing was written" >&2
    exit 2
  fi
  if [ -z "$d1_name" ]; then
    echo "CLOUD: --d1-name is empty; nothing was written" >&2
    exit 2
  fi
  case "$wname" in
    ''|-*|*-|*[!abcdefghijklmnopqrstuvwxyz0123456789-]*)
      echo "CLOUD: the worker name must be lowercase letters, digits and dashes (not starting or ending with a dash); nothing was written" >&2
      exit 2 ;;
  esac
  if [ "${#wname}" -gt 63 ]; then
    echo "CLOUD: the worker name is longer than 63 characters; nothing was written" >&2
    exit 2
  fi

  # The page's language: the repo's language from agent.conf; outside a repo
  # the same rule as start (AGENT_CITY_LANG, else zh). Only en or zh.
  lang="$language"
  if [ "$OUTSIDE_REPO" = yes ]; then
    lang="${AGENT_CITY_LANG:-}"
  fi
  case "$lang" in
    en|zh) : ;;
    *) lang="zh" ;;
  esac

  src_worker="$PLUGIN_ROOT/bin/agent-city-cloud.js"
  src_page="$PLUGIN_ROOT/bin/agent-city.html"
  src_assets="$PLUGIN_ROOT/bin/agent-city-assets"
  for f in "$src_worker" "$src_page"; do
    if [ ! -f "$f" ]; then
      echo "CLOUD: this plugin has no $f; nothing was written" >&2
      exit 1
    fi
  done
  if [ ! -d "$src_assets" ]; then
    echo "CLOUD: this plugin has no $src_assets; nothing was written" >&2
    exit 1
  fi

  # Only an empty folder or an earlier build of this command is built into;
  # nothing else is ever removed.
  if [ -e "$dir" ] || [ -L "$dir" ]; then
    if [ ! -d "$dir" ]; then
      echo "CLOUD: $dir is not a folder; nothing was written" >&2
      exit 2
    fi
    if [ -n "$(ls -A "$dir")" ] && ! cloud_is_ours "$dir"; then
      echo "CLOUD: $dir is not empty and is not a folder this command built; choose another folder (nothing was written)" >&2
      exit 2
    fi
  fi

  cfg=$(cloud_config_json "$wname" "$d1_name" "$d1_id" "$lang" \
          "$PLUGIN_ROOT/.claude-plugin/plugin.json") || cfg=""
  if [ -z "$cfg" ]; then
    echo "CLOUD: could not write the settings (python3 is needed); nothing was written" >&2
    exit 1
  fi

  mkdir -p "$dir" || { echo "CLOUD: cannot make $dir" >&2; exit 1; }
  rm -rf "$dir/site" "$dir/worker.js"
  if ! { printf '%s\n' "$cfg" > "$dir/wrangler.jsonc" \
         && cp "$src_worker" "$dir/worker.js" \
         && mkdir "$dir/site" \
         && cp "$src_page" "$dir/site/index.html" \
         && cp -R "$src_assets" "$dir/site/assets"; }; then
    rm -rf "$dir/site" "$dir/worker.js"
    echo "CLOUD: could not build $dir (is the disk full?); do not deploy it" >&2
    exit 1
  fi
  return 0
}

do_cloud_build() {
  dir=""
  d1_id=""
  d1_name="agent-city"
  wname="agent-city-page"
  while [ $# -gt 0 ]; do
    case "$1" in
      --d1-id|--d1-name|--name)
        if [ $# -lt 2 ]; then
          echo "CLOUD: $1 needs a value" >&2
          exit 2
        fi
        case "$1" in
          --d1-id) d1_id="$2" ;;
          --d1-name) d1_name="$2" ;;
          --name) wname="$2" ;;
        esac
        shift 2 ;;
      -*)
        echo "CLOUD: unknown option $1" >&2
        exit 2 ;;
      *)
        if [ -n "$dir" ]; then
          echo "CLOUD: one folder only" >&2
          exit 2
        fi
        dir="$1"
        shift ;;
    esac
  done
  cloud_build_core "$dir" "$d1_id" "$d1_name" "$wname"
  echo "CLOUD: built $dir"
  echo "CLOUD: deploy it yourself: cd $dir && npx wrangler deploy"
  return 0
}

# cloud-deploy: the owner's, in his own terminal. No terminal on stdin (an
# agent, a pipe) -> refuse before anything is asked, built or run. The database
# id is not a secret; it is remembered, alone, in cloud-site.conf. This never
# runs a wrangler login: wrangler's own sign-in message is passed on and the
# owner types the login himself.
do_cloud_deploy() {
  if [ ! -t 0 ]; then
    echo "CLOUD: run this yourself in your own terminal (it deploys to your Cloudflare account)" >&2
    exit 2
  fi
  if ! command -v npx >/dev/null 2>&1; then
    echo "CLOUD: npx not found; install Node.js (https://nodejs.org), then run this again" >&2
    exit 1
  fi
  conf="$CITY_HOME/cloud-site.conf"
  site="$CITY_HOME/cloud-site"

  saved=""
  if [ -f "$conf" ]; then
    read -r saved < "$conf" || true
    is_uuid "$saved" || saved=""
  fi
  if [ -n "$saved" ]; then
    printf 'D1 database id (press Enter to keep %s): ' "$saved" >&2
  else
    printf 'D1 database id (dashboard: Storage & Databases, D1, your database, "Database ID"): ' >&2
  fi
  read -r answer || answer=""
  answer=$(printf '%s' "$answer" | tr -d '[:space:]')
  [ -n "$answer" ] || answer="$saved"
  if [ -z "$answer" ]; then
    echo "CLOUD: no database id entered" >&2
    exit 2
  fi
  if ! is_uuid "$answer"; then
    echo "CLOUD: that is not a D1 database id (letters and digits in groups, like xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)" >&2
    exit 2
  fi
  if [ "$answer" != "$saved" ]; then
    if ! { mkdir -p "$CITY_HOME" && printf '%s\n' "$answer" > "$conf"; }; then
      echo "CLOUD: could not remember the id in $conf; going on" >&2
    fi
  fi

  cloud_build_core "$site" "$answer" "agent-city" "agent-city-page"
  echo "CLOUD: built $site"

  echo "CLOUD: deploying to your Cloudflare account (npx wrangler deploy) ..."
  rc=0
  (cd "$site" && npx wrangler deploy) || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "CLOUD: the deploy did not finish." >&2
    echo "CLOUD: if it said you are not logged in, type this yourself in this terminal, then run cloud-deploy again:  npx wrangler login" >&2
    exit "$rc"
  fi
  echo "CLOUD: deployed. The page answers 'login required' until the login is set up (skills/city/setup.md, 'Set up the login')."
  return 0
}

# cloud-talk on | off: see the header comment. `on` is the owner's, in his own
# terminal: no terminal on stdin (an agent, a pipe) -> refuse before anything is
# asked, sent or saved. The talk key is read with echo off and handed to
# agent_city_relay.py on stdin only -- never argv, never on screen, never in a
# message below. The relay must say talk is on before the key is saved.
do_cloud_talk() {
  case "${1:-}" in
    on) do_talk_on ;;
    off) do_talk_off ;;
    *)
      echo "CLOUD TALK: usage: agent-city.sh cloud-talk on | off" >&2
      exit 2 ;;
  esac
}

do_talk_on() {
  if [ ! -t 0 ]; then
    echo "CLOUD TALK: run this yourself in your own terminal (it lets the cloud page send messages to your sessions)" >&2
    exit 2
  fi
  talk_need_joined on
  printf 'Talk key (hidden): ' >&2
  read -rs key || key=""
  printf '\n' >&2

  rc=0
  out=$(printf '%s\n' "$key" | python3 "$RELAY_MODULE" talk --secret "$SECRET_FILE" \
          --talk-file "$TALK_FILE" on 2>/dev/null) || rc=$?
  key=""
  case "$rc" in
    0)
      echo "CLOUD TALK: $out"
      return 0 ;;
    2) echo "CLOUD TALK: no key entered; nothing was saved" >&2 ;;
    3) echo "CLOUD TALK: the relay did not take this key; nothing was saved" >&2 ;;
    4) echo "CLOUD TALK: the relay has no TALK_KEY (or its cloud page is off); nothing was saved" >&2 ;;
    5) echo "CLOUD TALK: cannot reach the relay; nothing was saved" >&2 ;;
    6) echo "CLOUD TALK: cannot write $TALK_FILE; nothing was saved" >&2 ;;
    *) echo "CLOUD TALK: this repo has not joined a team relay (run join first); nothing was saved" >&2 ;;
  esac
  exit 1
}

# off must always work, it is the way to stop. In a joined repo it tells the
# relay and forgets that host. Outside a repo, or in a repo that has not joined
# (any more), there is no host to name: the whole talk file goes, with no
# request to anybody (that machine's copy on Cloudflare ages out).
do_talk_off() {
  rc=1
  if [ "$OUTSIDE_REPO" = no ] && [ -f "$SECRET_FILE" ]; then
    rc=0
    python3 "$RELAY_MODULE" talk --secret "$SECRET_FILE" --talk-file "$TALK_FILE" off \
      >/dev/null 2>&1 || rc=$?
  fi
  if [ "$rc" -ne 0 ]; then
    rm -f "$TALK_FILE" 2>/dev/null || true
  fi
  echo "CLOUD TALK: off"
  return 0
}

# cloud-talk on needs a repo that has joined a team relay: the relay host comes
# from its join file. $1 = the word, for the message.
talk_need_joined() {
  if [ "$OUTSIDE_REPO" = yes ]; then
    echo "CLOUD TALK: not inside a repo; cd into the joined repo, then run cloud-talk $1" >&2
    exit 1
  fi
  if [ ! -f "$SECRET_FILE" ]; then
    echo "CLOUD TALK: this repo has not joined a team relay; run join first" >&2
    exit 1
  fi
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
  cloud-build) shift; do_cloud_build "$@";;
  cloud-deploy) do_cloud_deploy;;
  cloud-talk) shift; do_cloud_talk "$@";;
  *) usage; exit 2;;
esac
