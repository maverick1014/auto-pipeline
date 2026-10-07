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
#   ./agent-city.sh join     join the team relay, once for this computer (address + key,
#                            asked here)
#   ./agent-city.sh leave    this computer leaves the team relay (no repo sends)
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
#   ./agent-city.sh cloud-talk off   stop that (no terminal needed); it also turns
#                            starting off
#   ./agent-city.sh cloud-start on   the owner's, in his own terminal only: ask the
#                            talk key again (hidden), let the cloud page start
#                            agents on this machine (talk must be on first)
#   ./agent-city.sh cloud-start off  stop that (no terminal needed)
#   ./agent-city.sh login-start on   start the small city program when you log in, so the
#                            cloud page sees this computer after a restart (the owner's,
#                            in his own terminal only; macOS only for now)
#   ./agent-city.sh login-start off  stop that (no terminal needed)
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
# join/leave use bin/agent_city_relay.py (requirements/city.md, "Joining").
# Not in a cloud session: join is once per computer, from any folder. The
# device join file is $AGENT_CITY_HOME/team-relay (DEVICE_FILE), mode 0600, never
# inside a repo, written only after the relay accepts the key; no origin or
# .gitignore check. Inside a repo with a shared origin its main root also goes into
# $AGENT_CITY_HOME/joined-repos.txt. A computer with no device join and a repo joined
# the old way (first listed repo whose folder and own .secrets/agent-city-relay
# are there) is offered that repo's relay first ("Use it for every repo on this
# computer? [Y/n]"): yes = the relay checks that same key (join --from-file: the
# key goes from the repo's file to the relay check inside python, never typed,
# shown or on an argv), then it is the computer's join. leave removes the device
# join, the own join file of every listed repo and of the repo it runs in, and
# every path line of the list. "The join here" is effective_join(<main repo
# root>, DEVICE_FILE) inside a repo (the repo's own file wins when it names
# another relay), the device file outside one; status, cloud-talk, cloud-start,
# autostart and login-start run use it. The team key is never an argv or on screen.
# A cloud session (CLAUDE_CODE_REMOTE set) has no device: it never reads or
# writes the device file, and join/leave stay per repo, as before: a per-repo join
# file at <main repo root>/.secrets/agent-city-relay, inside a repo only, a shared
# origin and a git-ignored .secrets/ needed.
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
# AGENT_CITY_LANG (en or zh, else zh). join/leave work there too (the computer's
# join); only in a cloud session do they refuse outside a repo and say to cd into
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
# running -> nothing; a cloud session (CLAUDE_CODE_REMOTE) -> nothing; no join
# here (the computer's join, or this repo's own on another relay) -> nothing, no
# network; the marker names that relay host -> start; else one quiet
# `cloud --probe`, on -> start. start there is the plain start with --joined-list
# always, no browser.
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
# page): `on` is the owner's, in his own terminal, from any folder on a joined
# computer (the join here: inside a repo that repo's join, else the computer's;
# a cloud session: the repo's own join only). It refuses without a terminal on
# stdin (exit 2: nothing asked, sent or saved), then, with no join here, exits 1
# saying to join first (nothing asked), asks
# the talk key with echo off ("Talk key (hidden): "), hands it to
# agent_city_relay.py talk on on stdin only, and the relay must take it before
# anything is saved: the key goes to $AGENT_CITY_HOME/cloud-talk (mode 0600, one
# line "<relay host> <talk key>"). `off` needs no terminal and always works: with
# a join here it tells the relay, then forgets the key here (outside a repo the
# whole file goes after that); with no join here it removes the whole file, no
# request. status prints "CLOUD TALK: on <relay host>" or
# "CLOUD TALK: off" right after the CLOUD line, from that file only -- no
# network, never the key.
#
# cloud-start on | off (requirements/city.md, "Cloud page", "Start"): the switch
# that lets the cloud page open an agent on this machine. No new secret: the key
# is the talk key, typed again. `on` is the owner's, in his own terminal, from any
# folder on a joined computer (the join here, as for cloud-talk), and talk must be
# on there first (a talk key for that host in
# the talk file). It refuses without a terminal on stdin (exit 2: nothing asked,
# sent or saved), then, with no join here, exits 1 saying to join first, asks the
# talk key with echo off ("Talk key (hidden): "), hands
# it to agent_city_relay.py start on on stdin only, and the relay must say
# starting is on before anything is saved: the host (never a key) goes to
# $AGENT_CITY_HOME/cloud-start (mode 0600, one relay host per line). `off` needs
# no terminal and always works: with a join here it tells the relay (with the
# key of the talk file), then forgets that host (outside a repo the whole file
# goes after that); with no join here it removes the whole file, no request.
# cloud-talk off
# also turns starting off (the relay is told first: it needs the key);
# cloud-talk on never turns it on. status prints "CLOUD START: on <relay host>"
# or "CLOUD START: off" right after the CLOUD TALK line, from the two files only
# -- on only when talk is on too; no network, never the key.
# A start typed inside a repo also passes --joined-list while the start file
# names a host (see START_JOINED).
#
# login-start on | off | run (requirements/city.md, "Cloud page", "Login start"): the
# small city program comes back by itself after a restart, so the cloud page sees
# this computer without anybody opening a session. A macOS LaunchAgent, off by
# default, macOS only for now (`uname -s` is not Darwin: one line, exit 1, nothing
# touched, launchctl never called). `on` is the owner's, in his own terminal: it
# refuses without a terminal on stdin (exit 2, nothing written), so an agent, a hook
# or a plugin update can never install it. It copies bin/agent-city-shim byte for
# byte to $CITY_HOME/login-start.sh (mode 0755, temp file then mv): the launcher is a
# copy of the shim, outside the versioned plugin folder, so no plugin path goes stale
# (the shim picks the newest installed plugin at every run; an update needs no new
# `on`). It writes $HOME/Library/LaunchAgents/com.auto-pipeline.agent-city.login.plist
# (python3 plistlib, temp file then replace): ProgramArguments /bin/sh <launcher>
# login-start run; RunAtLoad (at once and at every login); AbandonProcessGroup (else
# launchd kills the city server, a child of the launcher, when the launcher exits);
# EnvironmentVariables PATH = this terminal's PATH without the entries inside a plugin
# folder (the running plugin's own, any .../plugins/cache/...: launchd's own PATH has
# no python3, orca or claude, and a versioned entry goes stale), plus AGENT_CITY_HOME,
# AGENT_CITY_DIR, AGENT_CITY_PORT each only when set; no KeepAlive, no StartInterval:
# the server's own idle rule stays. Then `launchctl bootout` (quiet, not loaded is
# fine) and `launchctl bootstrap gui/<uid>`; a bootstrap that fails is tried again, at
# most 3 times, 1 s apart: the old copy can still be going away; when all 3 fail it
# removes the plist and the launcher again (exit 1). launchctl and uname are found on PATH. `off` needs
# no terminal: bootout, then the plist and the launcher go, nothing else.
# `run` is what the login item runs (not in the help; a login has no folder): in the
# foreground, prints nothing, always exit 0. It walks $CITY_HOME/joined-repos.txt in
# order (repos whose folder is there and that have a join -- their own file, or the
# computer's -- each relay host once) and for each runs autostart_work from that
# repo (this script again, in that folder, as the internal verb `run-here`: its
# agent.conf decides port, idle and language, --start-dir is the repo, --joined-list
# always, no browser), until a city server runs. When none does and the computer
# has a valid device join, it runs autostart_work from where it is (outside a repo).
# A server already running, or a cloud session, or nothing joined: nothing, no network. status prints "LOGIN START: on"
# (the plist file is there) or "LOGIN START: off" as its last line, from the file
# only: launchctl is never called there.

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
  agent-city join               join the team relay, once for this computer (address + key, asked here)
  agent-city leave              this computer leaves the team relay (no repo sends)
  agent-city send               cloud sender: send this session's lines to the team relay
  agent-city relay-dev [port]   run the dev relay for a two-machine LAN test
  agent-city cloud-hooks        write the city hooks into user-level settings
  agent-city install-shim       copy the agent-city command to ~/.local/bin, so it runs from any folder
  agent-city remove-shim        remove that copy, if it is ours
  agent-city autostart          what the session-start hook runs: start the city by itself
                                on a joined machine whose relay has the cloud page on
                                (prints nothing, returns at once)
  agent-city cloud-build <dir> --d1-id <id> [--d1-name <name>] [--name <worker name>]
                                make the folder the cloud page is deployed from
                                (no network, no login)
  agent-city cloud-deploy       deploy the cloud page to your Cloudflare account
                                (yours to run, in your own terminal)
  agent-city cloud-talk on      let the cloud page send messages to your sessions
                                (yours to run, in your own terminal; asks the talk key)
  agent-city cloud-talk off     stop that (it also turns starting off)
  agent-city cloud-start on     let the cloud page start agents on this machine
                                (yours to run, in your own terminal; asks the talk key
                                again; talk must be on first)
  agent-city cloud-start off    stop that
  agent-city login-start on     start the small city program when you log in, so the cloud
                                page sees this computer after a restart (yours to run, in your
                                own terminal; macOS only for now)
  agent-city login-start off    stop that
  agent-city -h                 this help

Outside a repo: start/demo sync every repo listed in
$AGENT_CITY_HOME/joined-repos.txt (language from AGENT_CITY_LANG, en or zh,
else zh); status shows them. join, leave, cloud-talk and cloud-start work from
any folder too. Only a cloud session (join and leave stay per repo there) is told
to cd into the repo first.

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
# city-device-join: this computer's join, written once by `join` from any folder.
# A cloud session (CLAUDE_CODE_REMOTE set) has no device: DEVICE_JOIN is empty
# there and nothing ever reads or writes DEVICE_FILE.
DEVICE_FILE="$CITY_HOME/team-relay"
DEVICE_JOIN="$DEVICE_FILE"
[ -z "${CLAUDE_CODE_REMOTE:-}" ] || DEVICE_JOIN=""
# The join file that counts here (join_here sets it): the computer's, or this
# repo's own one on another relay; empty = nothing joined here.
JOIN_HERE=""
CLOUD_FILE="$CITY_HOME/cloud"
TALK_FILE="$CITY_HOME/cloud-talk"
START_FILE="$CITY_HOME/cloud-start"
LOGIN_LABEL="com.auto-pipeline.agent-city.login"
LOGIN_DIR="$HOME/Library/LaunchAgents"
LOGIN_PLIST="$LOGIN_DIR/$LOGIN_LABEL.plist"
LOGIN_LAUNCHER="$CITY_HOME/login-start.sh"
# yes: do_start always passes --joined-list (autostart, also inside a repo).
# Also passed when the start file names a host (do_start checks it): a machine
# that takes start orders syncs every repo it joined from the first moment, so a
# server started by hand inside a repo, with nobody working there, is still seen
# by the cloud page. No start file, or one with no host: as before.
START_JOINED=no

# Sets JOIN_HERE to the join file that counts here, or "" when nothing is joined.
# Inside a repo: effective_join(<main repo root>, device) -- the repo's own file
# when it names another relay than the computer's, else the computer's. Outside
# a repo: the device file when read_join takes it. A cloud session has no device:
# only the repo's own file, inside a repo. Never the key, no network.
join_here() {
  inside=yes
  [ "$OUTSIDE_REPO" = no ] || inside=no
  JOIN_HERE=$(python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl

root, device, inside = sys.argv[2], sys.argv[3], sys.argv[4] == "yes"
if inside:
    got = rl.effective_join(root, device)
    if got:
        print(got["path"])
elif device and rl.read_join(device):
    print(device)
' "$PLUGIN_ROOT/bin" "$PROJECT_ROOT" "$DEVICE_JOIN" "$inside" 2>/dev/null) || JOIN_HERE=""
  return 0
}

# True when the computer's join file is there and read_join takes it (never in
# a cloud session).
device_valid() {
  [ -n "$DEVICE_JOIN" ] || return 1
  python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
sys.exit(0 if rl.read_join(sys.argv[2]) else 1)
' "$PLUGIN_ROOT/bin" "$DEVICE_JOIN" >/dev/null 2>&1
}

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
  # city-device-join: not in a cloud session, serve always knows the computer's
  # join file (a join made later is picked up); a valid one also brings the
  # joined list, so every repo of a joined computer syncs from the first moment.
  device_ok=no
  if [ -n "$DEVICE_JOIN" ]; then
    set -- --device-join "$DEVICE_FILE"
    if device_valid; then device_ok=yes; fi
  fi
  if [ "$OUTSIDE_REPO" = yes ] || [ "$START_JOINED" = yes ] || [ "$device_ok" = yes ] \
     || grep -qE '^[[:space:]]*[^#[:space:]][^[:space:]]*[[:space:]]*$' "$START_FILE" 2>/dev/null; then
    set -- "$@" --joined-list "$CITY_HOME/joined-repos.txt"
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
    start_lines_outside || true
    not_shown_line || true
  else
    join_here
    team_line
    cloud_line || true
    talk_line || true
    start_line || true
    not_shown_line || true
  fi
  login_line
  return 0
}

# "LOGIN START: on" when the login item's plist is there, else "LOGIN START: off".
# The file only: launchctl is never called here. Always the last status line.
login_line() {
  if [ -f "$LOGIN_PLIST" ]; then
    echo "LOGIN START: on"
  else
    echo "LOGIN START: off"
  fi
  return 0
}

# "CLOUD: on <relay host>" or "CLOUD: off" for the join here, nothing when
# nothing is joined here. From the marker only: no --probe, so no network.
# Never the key.
cloud_line() {
  [ -n "$JOIN_HERE" ] || return 0
  out=$(python3 "$RELAY_MODULE" cloud --secret "$JOIN_HERE" \
          --cloud-file "$CLOUD_FILE" 2>/dev/null) || out="none"
  case "$out" in
    "on "*) echo "CLOUD: $out" ;;
    "off "*) echo "CLOUD: off" ;;
  esac
  return 0
}

# Outside a repo: the relay hosts this computer is joined to, one per line, each
# once: the computer's own join host first (when it is joined), then the join host
# of each listed repo whose folder is there (effective_join: its own file when it
# names another relay, else the computer's). Nothing when nothing is joined. Hosts
# only, never the key, no network.
outside_hosts() {
  python3 -c '
import os
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
from urllib.parse import urlsplit

device = sys.argv[3]
hosts = []
dev = rl.read_join(device) if device else None
if dev:
    hosts.append(urlsplit(dev["address"]).netloc)
for repo in rl.read_joined_list(sys.argv[2]):
    if not os.path.isdir(repo):
        continue
    joined = rl.effective_join(repo, device)
    if not joined:
        continue
    host = urlsplit(joined["address"]).netloc
    if host not in hosts:
        hosts.append(host)
for host in hosts:
    print(host)
' "$PLUGIN_ROOT/bin" "$CITY_HOME/joined-repos.txt" "$DEVICE_JOIN"
}

# Outside a repo: one "CLOUD: on <host>" per joined relay host that the marker
# names, else one "CLOUD: off" when anything is joined, nothing when nothing is.
# Marker only, no network. Never the key.
cloud_lines_outside() {
  hosts=$(outside_hosts 2>/dev/null) || hosts=""
  [ -n "$hosts" ] || return 0
  python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl

marked = rl.read_cloud(sys.argv[2])
on = [h for h in sys.argv[3].split() if h in marked]
if on:
    for h in on:
        print("CLOUD: on " + h)
else:
    print("CLOUD: off")
' "$PLUGIN_ROOT/bin" "$CLOUD_FILE" "$hosts"
}

# "CLOUD TALK: on <relay host>" or "CLOUD TALK: off" for the join here, nothing
# when nothing is joined here. From the talk file only, no network. Never the key.
talk_line() {
  [ -n "$JOIN_HERE" ] || return 0
  out=$(python3 "$RELAY_MODULE" talk --secret "$JOIN_HERE" \
          --talk-file "$TALK_FILE" status 2>/dev/null) || out="none"
  case "$out" in
    "on "*) echo "CLOUD TALK: $out" ;;
    "off "*) echo "CLOUD TALK: off" ;;
  esac
  return 0
}

# Outside a repo: one "CLOUD TALK: on <host>" per joined relay host that the talk
# file names, else one "CLOUD TALK: off" when anything is joined, nothing when
# nothing is. Talk file only, no network. Never the key.
talk_lines_outside() {
  hosts=$(outside_hosts 2>/dev/null) || hosts=""
  [ -n "$hosts" ] || return 0
  python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl

held = rl.read_talk(sys.argv[2])
on = [h for h in sys.argv[3].split() if h in held]
if on:
    for h in on:
        print("CLOUD TALK: on " + h)
else:
    print("CLOUD TALK: off")
' "$PLUGIN_ROOT/bin" "$TALK_FILE" "$hosts"
}

# "CLOUD START: on <relay host>" or "CLOUD START: off" for the join here, nothing
# when nothing is joined here. From the start file and the talk file only, no network
# (on only when the talk file has the host too). Never the key.
start_line() {
  [ -n "$JOIN_HERE" ] || return 0
  out=$(python3 "$RELAY_MODULE" start --secret "$JOIN_HERE" \
          --talk-file "$TALK_FILE" --start-file "$START_FILE" status 2>/dev/null) || out="none"
  case "$out" in
    "on "*) echo "CLOUD START: $out" ;;
    "off "*) echo "CLOUD START: off" ;;
  esac
  return 0
}

# Outside a repo: one "CLOUD START: on <host>" per joined relay host that the
# start file and the talk file both name, else one "CLOUD START: off" when anything
# is joined, nothing when nothing is. Files only, no network. Never the key.
start_lines_outside() {
  hosts=$(outside_hosts 2>/dev/null) || hosts=""
  [ -n "$hosts" ] || return 0
  python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl

started = rl.read_start(sys.argv[3])
held = rl.read_talk(sys.argv[2])
on = [h for h in sys.argv[4].split() if h in started and h in held]
if on:
    for h in on:
        print("CLOUD START: on " + h)
else:
    print("CLOUD START: off")
' "$PLUGIN_ROOT/bin" "$TALK_FILE" "$START_FILE" "$hosts"
}

# This status line comes right after the cloud lines (CLOUD, CLOUD TALK, CLOUD START)
# and before LOGIN START, which stays the last status line:
# "NOT SHOWN IN THE CLOUD: <name>, <name> (not joined)",
# the repos with a live session that the cloud page does not show. Only when the
# city server runs, the cloud marker names a relay host and the server's /health
# answers within 2 s with a "not_joined" list holding at least one usable name (a
# non-empty string with no "/" in it: never a path). Anything else: no line.
not_shown_line() {
  found=$(read_on) || found=""
  [ -n "$found" ] || return 0
  python3 -c '
import json
import sys
sys.path.insert(0, sys.argv[1])
from urllib.request import ProxyHandler, build_opener

try:
    import agent_city_relay as rl
    if rl.read_cloud(sys.argv[2]):
        opener = build_opener(ProxyHandler({}))
        with opener.open("http://127.0.0.1:%s/health" % sys.argv[3], timeout=2) as reply:
            body = json.loads(reply.read(1000000).decode("utf-8"))
        listed = body.get("not_joined") if isinstance(body, dict) else None
        if isinstance(listed, list):
            names = [n for n in listed if isinstance(n, str) and n != "" and "/" not in n]
            if names:
                print("NOT SHOWN IN THE CLOUD: " + ", ".join(names) + " (not joined)")
except Exception:
    pass
' "$PLUGIN_ROOT/bin" "$CLOUD_FILE" "$(printf '%s' "$found" | awk '{print $2}')" 2>/dev/null
  return 0
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
  # 3. no join here (outside a repo: the computer's join; inside one: its own
  #    file on another relay, else the computer's): no network at all
  join_here
  [ -n "$JOIN_HERE" ] || return 0
  state=$(python3 "$RELAY_MODULE" cloud --secret "$JOIN_HERE" \
            --cloud-file "$CLOUD_FILE" 2>/dev/null) || return 0
  case "$state" in
    "on "*) ;;
    "off "*)
      # 5. no marker for this relay: one quiet sync asks the relay
      state=$(python3 "$RELAY_MODULE" cloud --secret "$JOIN_HERE" \
                --cloud-file "$CLOUD_FILE" --probe 2>/dev/null) || return 0
      case "$state" in "on "*) ;; *) return 0 ;; esac ;;
    *) return 0 ;;
  esac
  # 4. the cloud is on: today's start, with the machine's joined list
  START_JOINED=yes
  do_start "" || true
  return 0
}

# Inside a repo, from the join here: "TEAM: joined <relay host> (this device, all
# repos)" when it is the computer's join, "TEAM: joined <relay host>" when it is
# the repo's own file, else "TEAM: not joined". Never the key.
team_line() {
  python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
from urllib.parse import urlsplit

path, device = sys.argv[2], sys.argv[3]
joined = rl.read_join(path) if path else None
if joined:
    host = urlsplit(joined["address"]).netloc
    if device and path == device:
        print("TEAM: joined %s (this device, all repos)" % host)
    else:
        print("TEAM: joined " + host)
else:
    print("TEAM: not joined")
' "$PLUGIN_ROOT/bin" "$JOIN_HERE" "$DEVICE_JOIN"
}

# Outside a repo: "TEAM: joined <host> (this device, all repos)" when the
# computer is joined, then one "TEAM: joined <host> (<repo>)" per listed repo
# whose folder and own join file are there and whose relay is not the computer's;
# with no device join, one line per such listed repo; "TEAM: not joined" when
# there is no line at all. Never the key.
joined_list_lines() {
  python3 -c '
import os
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
from urllib.parse import urlsplit

device = sys.argv[3]
printed = False
dev = rl.read_join(device) if device else None
if dev:
    print("TEAM: joined %s (this device, all repos)" % urlsplit(dev["address"]).netloc)
    printed = True
for repo in rl.read_joined_list(sys.argv[2]):
    if not os.path.isdir(repo):
        continue
    joined = rl.effective_join(repo, device)
    if not joined or joined["path"] == device:
        continue
    print("TEAM: joined %s (%s)" % (urlsplit(joined["address"]).netloc, repo))
    printed = True
if not printed:
    print("TEAM: not joined")
' "$PLUGIN_ROOT/bin" "$CITY_HOME/joined-repos.txt" "$DEVICE_JOIN"
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

# Join the team relay (requirements/city.md, "Joining"). Not in a cloud session:
# once per computer, from any folder (do_join_device). A cloud session has no
# device and keeps the join per repo (do_join_repo).
do_join() {
  if [ -n "${CLAUDE_CODE_REMOTE:-}" ]; then
    do_join_repo
  else
    do_join_device
  fi
}

# This computer's join: <city home>/team-relay, written (0600) only after the
# relay takes the key. No origin or .gitignore check: the file is never inside a
# repo. The team key is read with echo off and handed to agent_city_relay.py on
# stdin only -- never argv, never on screen.
do_join_device() {
  # Moving up: no valid device join, and a listed repo (list order) whose folder
  # and own join file are there -> offer that repo's relay first. Its key goes
  # from its own file to the relay check inside agent_city_relay.py (join
  # --from-file): never typed, shown or on an argv.
  offer=""
  if ! device_valid; then
    offer=$(python3 -c '
import os
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
from urllib.parse import urlsplit

for repo in rl.read_joined_list(sys.argv[2]):
    if not os.path.isdir(repo):
        continue
    joined = rl.read_join(os.path.join(repo, ".secrets", "agent-city-relay"))
    if joined:
        print(repo)
        print(urlsplit(joined["address"]).netloc)
        break
' "$PLUGIN_ROOT/bin" "$CITY_HOME/joined-repos.txt" 2>/dev/null) || offer=""
  fi

  if [ -n "$offer" ]; then
    up_repo=$(printf '%s\n' "$offer" | sed -n 1p)
    up_host=$(printf '%s\n' "$offer" | sed -n 2p)
    printf 'JOIN: a repo on this computer is in the team %s (%s). Use it for every repo on this computer? [Y/n] ' \
      "$up_host" "$(basename "$up_repo")" >&2
    # no answer line at all (a closed stdin) is not a yes
    answer=""
    read -r answer || [ -n "$answer" ] || answer="n"
    answer=$(printf '%s' "$answer" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
    case "$answer" in
      n|no) ;;
      *)
        rc=0
        out=$(python3 "$RELAY_MODULE" join --from-file "$up_repo/.secrets/agent-city-relay" \
                --file "$DEVICE_FILE" --cloud-file "$CLOUD_FILE" 2>&1 </dev/null) || rc=$?
        if [ "$rc" -ne 0 ]; then
          echo "$out" >&2
          exit 1
        fi
        join_device_done "${out#RELAY: ok }"
        return 0 ;;
    esac
  fi

  printf 'Relay address: ' >&2
  read -r address || address=""
  printf 'Team key (hidden): ' >&2
  read -rs key || key=""
  printf '\n' >&2

  rc=0
  out=$(printf '%s\n' "$key" | python3 "$RELAY_MODULE" \
          join --address "$address" --file "$DEVICE_FILE" \
          --cloud-file "$CLOUD_FILE" 2>&1) || rc=$?
  key=""
  if [ "$rc" -ne 0 ]; then
    echo "$out" >&2
    exit 1
  fi

  join_device_done "${out#RELAY: ok }"
  return 0
}

# The computer is joined: say so. Inside a repo with a shared origin, its main
# root also goes into the joined list, once, never the key. $1 = relay host.
join_device_done() {
  echo "JOINED: this device -> $1 (all repos)"
  if [ "$OUTSIDE_REPO" = no ]; then
    origin=$(git -C "$PROJECT_ROOT" config --get remote.origin.url 2>/dev/null) || origin=""
    python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl

if rl.origin_id(sys.argv[3]):
    rl.add_joined(sys.argv[2], sys.argv[4])
' "$PLUGIN_ROOT/bin" "$CITY_HOME/joined-repos.txt" "$origin" "$PROJECT_ROOT" || true
  fi
  return 0
}

# Cloud sessions only: join this repo's team relay (requirements/city.md,
# "Joining"). Refuses, before asking anything, when there is no origin remote,
# the origin is not shared (a local path or file:// URL -- origin_id() is empty),
# or .secrets/ is not git-ignored. The team key is read with echo off and handed
# to agent_city_relay.py on stdin only -- never argv, never on screen.
do_join_repo() {
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

# leave. Not in a cloud session: this computer leaves, from any folder. The
# device join, the own join file of every listed repo and of the repo it runs in
# go, and the list keeps no path line (comments stay). The talk and start files
# are not touched. A cloud session has no device: it leaves only its own repo
# (do_leave_repo).
do_leave() {
  if [ -n "${CLAUDE_CODE_REMOTE:-}" ]; then
    do_leave_repo
    return 0
  fi
  inside=yes
  [ "$OUTSIDE_REPO" = no ] || inside=no
  gone=$(python3 -c '
import os
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl

device, listing, root, inside = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] == "yes"
removed = False


def drop(path):
    global removed
    if os.path.lexists(path):
        os.remove(path)
        removed = True


drop(device)
repos = list(rl.read_joined_list(listing))
if inside:
    repos.append(root)
for repo in repos:
    try:
        drop(os.path.join(repo, ".secrets", "agent-city-relay"))
    except OSError:
        pass
    rl.remove_joined(listing, repo)
print("yes" if removed else "no")
' "$PLUGIN_ROOT/bin" "$DEVICE_FILE" "$CITY_HOME/joined-repos.txt" "$PROJECT_ROOT" "$inside") || gone="no"
  if [ "$gone" = yes ]; then
    echo "LEFT: this computer left the team; no repo sends now"
  else
    echo "LEFT: was not joined"
  fi
  return 0
}

# Cloud sessions only: leave this repo's team relay.
do_leave_repo() {
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
  out=$(printf '%s\n' "$key" | python3 "$RELAY_MODULE" talk --secret "$JOIN_HERE" \
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
    *) echo "CLOUD TALK: nothing is joined here (run agent-city join first); nothing was saved" >&2 ;;
  esac
  exit 1
}

# off must always work, it is the way to stop. With a join here it tells the
# relay and forgets that host; outside a repo the whole talk file goes after
# that. With no join here (or a failed answer) there is no host to name: the whole
# talk file goes, with no request to anybody (that machine's copy on Cloudflare
# ages out). Starting needs talk, so it goes off too: with a join here the relay
# is told about it FIRST (it needs the key, which the talk off below forgets), and
# the start file loses the host; else the whole start file goes with the talk file.
do_talk_off() {
  join_here
  rc=1
  if [ -n "$JOIN_HERE" ]; then
    rc=0
    python3 "$RELAY_MODULE" start --secret "$JOIN_HERE" --talk-file "$TALK_FILE" \
      --start-file "$START_FILE" off >/dev/null 2>&1 || rm -f "$START_FILE" 2>/dev/null || true
    python3 "$RELAY_MODULE" talk --secret "$JOIN_HERE" --talk-file "$TALK_FILE" off \
      >/dev/null 2>&1 || rc=$?
  fi
  if [ "$rc" -ne 0 ] || [ "$OUTSIDE_REPO" = yes ]; then
    rm -f "$TALK_FILE" "$START_FILE" 2>/dev/null || true
  fi
  echo "CLOUD TALK: off"
  return 0
}

# cloud-talk on needs a join here: the relay host comes from its file. $1 = the
# word, for the message. A cloud session has no device: its repo's own file only.
talk_need_joined() {
  join_here
  if [ -n "$JOIN_HERE" ]; then
    return 0
  fi
  if [ -n "${CLAUDE_CODE_REMOTE:-}" ]; then
    if [ "$OUTSIDE_REPO" = yes ]; then
      echo "CLOUD TALK: not inside a repo; cd into the joined repo, then run cloud-talk $1" >&2
    else
      echo "CLOUD TALK: this repo has not joined a team relay; run join first" >&2
    fi
  else
    echo "CLOUD TALK: this computer has not joined a team relay; run agent-city join first" >&2
  fi
  exit 1
}

# cloud-start on | off: see the header comment. `on` is the owner's, in his own
# terminal: no terminal on stdin (an agent, a pipe) -> refuse before anything is
# asked, sent or saved. The key is the talk key, typed again: read with echo off
# and handed to agent_city_relay.py on stdin only -- never argv, never on screen,
# never in a message below. The relay must say starting is on before the host is
# saved (the start file holds hosts only).
do_cloud_start() {
  case "${1:-}" in
    on) do_start_on ;;
    off) do_start_off ;;
    *)
      echo "CLOUD START: usage: agent-city.sh cloud-start on | off" >&2
      exit 2 ;;
  esac
}

do_start_on() {
  if [ ! -t 0 ]; then
    echo "CLOUD START: run this yourself in your own terminal (it lets the cloud page start agents on this machine)" >&2
    exit 2
  fi
  start_need_joined
  printf 'Talk key (hidden): ' >&2
  read -rs key || key=""
  printf '\n' >&2

  rc=0
  out=$(printf '%s\n' "$key" | python3 "$RELAY_MODULE" start --secret "$JOIN_HERE" \
          --talk-file "$TALK_FILE" --start-file "$START_FILE" on 2>/dev/null) || rc=$?
  key=""
  case "$rc" in
    0)
      echo "CLOUD START: $out"
      return 0 ;;
    2) echo "CLOUD START: no key entered; nothing was saved" >&2 ;;
    3) echo "CLOUD START: the relay did not take this key; nothing was saved" >&2 ;;
    4) echo "CLOUD START: the relay has no TALK_KEY (or its cloud page is off); nothing was saved" >&2 ;;
    5) echo "CLOUD START: cannot reach the relay; nothing was saved" >&2 ;;
    6) echo "CLOUD START: cannot write $START_FILE; nothing was saved" >&2 ;;
    7) echo "CLOUD START: turn talking on first (agent-city cloud-talk on); nothing was saved" >&2 ;;
    8) echo "CLOUD START: the relay does not know starting yet; put the new relay code on Cloudflare (skills/city/setup.md), then run this again; nothing was saved" >&2 ;;
    *) echo "CLOUD START: nothing is joined here (run agent-city join first); nothing was saved" >&2 ;;
  esac
  exit 1
}

# off must always work, it is the way to stop. With a join here it tells the
# relay (so an order that waits is never opened) and forgets that host; outside a
# repo the whole start file goes after that. With no join here (or a failed
# answer) there is no host to name: the whole start file goes, with no request to
# anybody. Talk stays as it is.
do_start_off() {
  join_here
  rc=1
  if [ -n "$JOIN_HERE" ]; then
    rc=0
    python3 "$RELAY_MODULE" start --secret "$JOIN_HERE" --talk-file "$TALK_FILE" \
      --start-file "$START_FILE" off >/dev/null 2>&1 || rc=$?
  fi
  if [ "$rc" -ne 0 ] || [ "$OUTSIDE_REPO" = yes ]; then
    rm -f "$START_FILE" 2>/dev/null || true
  fi
  echo "CLOUD START: off"
  return 0
}

# cloud-start on needs a join here: the relay host comes from its file. A cloud
# session has no device: its repo's own file only.
start_need_joined() {
  join_here
  if [ -n "$JOIN_HERE" ]; then
    return 0
  fi
  if [ -n "${CLAUDE_CODE_REMOTE:-}" ]; then
    if [ "$OUTSIDE_REPO" = yes ]; then
      echo "CLOUD START: not inside a repo; cd into the joined repo, then run cloud-start on" >&2
    else
      echo "CLOUD START: this repo has not joined a team relay; run join first" >&2
    fi
  else
    echo "CLOUD START: this computer has not joined a team relay; run agent-city join first" >&2
  fi
  exit 1
}

# login-start on | off | run: see the header comment. `run-here` is internal (one
# repo of the walk of `run`), not for people and not in the help.
do_login_start() {
  case "${1:-}" in
    on) login_on ;;
    off) login_off ;;
    run) login_run >/dev/null 2>&1 </dev/null || true ;;
    run-here) autostart_work >/dev/null 2>&1 </dev/null || true ;;
    *)
      echo "LOGIN START: usage: agent-city.sh login-start on | off" >&2
      exit 2 ;;
  esac
  return 0
}

# Only macOS has the LaunchAgent this needs. One plain line, nothing touched,
# launchctl never called.
login_need_mac() {
  if [ "$(uname -s 2>/dev/null)" != "Darwin" ]; then
    echo "LOGIN START: macOS only for now; nothing was changed" >&2
    exit 1
  fi
}

# `on` is the owner's, in his own terminal: no terminal on stdin (an agent, a
# hook, a pipe) -> refuse before anything is written or launchctl is called.
login_on() {
  login_need_mac
  if [ ! -t 0 ]; then
    echo "LOGIN START: run this yourself in your own terminal (it lets the small city program start when you log in)" >&2
    exit 2
  fi

  # the launcher: a byte copy of the shim, temp file in the same folder, then mv
  tmp="$CITY_HOME/.login-start.$$"
  if ! { mkdir -p "$CITY_HOME" "$LOGIN_DIR" \
         && cp "$PLUGIN_ROOT/bin/agent-city-shim" "$tmp" \
         && chmod 755 "$tmp" \
         && mv -f "$tmp" "$LOGIN_LAUNCHER"; }; then
    rm -f "$tmp" 2>/dev/null || true
    echo "LOGIN START: could not write $LOGIN_LAUNCHER; nothing was changed" >&2
    exit 1
  fi

  # the plist: python3 plistlib (always valid XML), temp file in the same folder,
  # then replace, so LaunchAgents never holds a half-written or a stray file
  rc=0
  python3 - "$LOGIN_PLIST" "$LOGIN_LABEL" "$LOGIN_LAUNCHER" "$PLUGIN_ROOT" <<'PY' || rc=$?
import os
import plistlib
import sys

path, label, launcher, plugin_root = sys.argv[1:5]
roots = {plugin_root.rstrip("/") or "/", os.path.realpath(plugin_root)}


def in_a_plugin_folder(entry):
    forms = {entry}
    if os.path.isabs(entry):
        forms.add(os.path.realpath(entry))
    for form in forms:
        if "/plugins/cache/" in form + "/":
            return True
        for root in roots:
            if form == root or form.startswith(root.rstrip("/") + "/"):
                return True
    return False


# this terminal's PATH, order kept, without the entries inside a plugin folder
kept = [e for e in os.environ.get("PATH", "").split(os.pathsep) if not in_a_plugin_folder(e)]
env = {"PATH": os.pathsep.join(kept)}
for key in ("AGENT_CITY_HOME", "AGENT_CITY_DIR", "AGENT_CITY_PORT"):
    if os.environ.get(key):
        env[key] = os.environ[key]

data = {
    "Label": label,
    "ProgramArguments": ["/bin/sh", launcher, "login-start", "run"],
    "RunAtLoad": True,
    "AbandonProcessGroup": True,
    "EnvironmentVariables": env,
}

tmp = os.path.join(os.path.dirname(path), ".%s.tmp%d" % (os.path.basename(path), os.getpid()))
try:
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as fh:
        plistlib.dump(data, fh)
    os.replace(tmp, path)
except OSError:
    sys.exit(1)
finally:
    try:
        os.remove(tmp)
    except OSError:
        pass
PY
  if [ "$rc" -ne 0 ]; then
    rm -f "$LOGIN_PLIST" "$LOGIN_LAUNCHER" 2>/dev/null || true
    echo "LOGIN START: could not write the login item $LOGIN_PLIST; nothing was left in place" >&2
    exit 1
  fi

  # unload an older copy first (failing is normal: it was not loaded), then load.
  # A bootstrap right after a bootout can fail while the old copy is still going
  # away: try again, at most 3 tries in all, 1 s apart (no sleep after the last).
  uid=$(id -u)
  launchctl bootout "gui/$uid/$LOGIN_LABEL" >/dev/null 2>&1 || true
  try=1
  while [ "$try" -le 3 ]; do
    if launchctl bootstrap "gui/$uid" "$LOGIN_PLIST" >/dev/null 2>&1; then
      echo "LOGIN START: on"
      return 0
    fi
    if [ "$try" -lt 3 ]; then
      sleep 1
    fi
    try=$((try + 1))
  done
  rm -f "$LOGIN_PLIST" "$LOGIN_LAUNCHER" 2>/dev/null || true
  echo "LOGIN START: launchctl would not load the login item; nothing was left in place" >&2
  exit 1
}

# off must always work, it is the way to stop: no terminal needed, fine when it
# never was on. Only the plist and the launcher go; nothing else in LaunchAgents
# or in the city home.
login_off() {
  login_need_mac
  uid=$(id -u)
  launchctl bootout "gui/$uid/$LOGIN_LABEL" >/dev/null 2>&1 || true
  rm -f "$LOGIN_PLIST" "$LOGIN_LAUNCHER" 2>/dev/null || true
  echo "LOGIN START: off"
  return 0
}

# What the login item runs. Foreground: when it returns, the server is up or will
# not come. The caller keeps every stream on /dev/null. A city server already
# running, or a cloud session: nothing. Else the joined repos in list order (the
# first repo of each relay host, folder there and a join that counts: its own file,
# or the computer's -- effective_join): for each, this script again from that repo
# (autostart_work with that repo's own agent.conf), stopping as soon as a server
# runs. CLAUDE_PROJECT_DIR is set to the repo, so the child never takes the repo
# from an inherited one. After the walk, with no server and a valid device join,
# autostart_work runs from where this is (outside a repo: the login item has no
# folder).
login_run() {
  read_on >/dev/null && return 0
  [ -z "${CLAUDE_CODE_REMOTE:-}" ] || return 0
  repos=$(python3 -c '
import os
import sys
sys.path.insert(0, sys.argv[1])
import agent_city_relay as rl
from urllib.parse import urlsplit

hosts = []
for repo in rl.read_joined_list(sys.argv[2]):
    if not os.path.isdir(repo):
        continue
    joined = rl.effective_join(repo, sys.argv[3])
    if not joined:
        continue
    host = urlsplit(joined["address"]).netloc
    if host not in hosts:
        hosts.append(host)
        print(repo)
' "$PLUGIN_ROOT/bin" "$CITY_HOME/joined-repos.txt" "$DEVICE_JOIN" 2>/dev/null) || repos=""
  while IFS= read -r repo; do
    [ -n "$repo" ] || continue
    ( cd "$repo" && CLAUDE_PROJECT_DIR="$repo" bash "$PLUGIN_ROOT/bin/agent-city.sh" login-start run-here
    ) </dev/null >/dev/null 2>&1 || true
    read_on >/dev/null && return 0
  done <<EOF
$repos
EOF
  if device_valid; then
    autostart_work || true
  fi
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
  cloud-build) shift; do_cloud_build "$@";;
  cloud-deploy) do_cloud_deploy;;
  cloud-talk) shift; do_cloud_talk "$@";;
  cloud-start) shift; do_cloud_start "$@";;
  login-start) shift; do_login_start "$@";;
  *) usage; exit 2;;
esac
