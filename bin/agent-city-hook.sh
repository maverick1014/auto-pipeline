#!/usr/bin/env bash
# agent-city-hook.sh — appends one JSON line per hook event, for the agent city visualiser.
#
#   off (no <dir>/on, or its pid is dead)  -> exit 0, nothing read, nothing written
#   on  ($AGENT_CITY_DIR/on holds "<pid> <port>" of the running city server)
#       -> reads the hook JSON from stdin, appends one line to $AGENT_CITY_DIR/events.jsonl
#
# Bash builtins only (read, [[, kill -0, printf): PATH may be empty, and this
# must stay free when the city is off and cheap even for a 1 MB tool payload.

dir=${AGENT_CITY_DIR:-$HOME/.cache/agent-city}
switch="$dir/on"

[ -f "$switch" ] || exit 0

pid=
port=
read -r pid port < "$switch" 2>/dev/null

case "$pid" in
    ''|*[!0-9]*) exit 0 ;;
esac
kill -0 "$pid" 2>/dev/null || exit 0

LC_ALL=C
export LC_ALL

# extract KEY HAYSTACK — the JSON-escaped string value of "KEY" in HAYSTACK, or "".
extract() {
    local key=$1 hay=$2 pat
    pat='"'"$key"'"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)"'
    if [[ $hay =~ $pat ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
    fi
}

# cap200 VALUE — VALUE cut to 200 bytes, then trimmed so it is still a valid
# JSON string: a trailing partial \uXXXX escape is dropped, then an unpaired
# trailing backslash (an escape that got cut off mid-way) is dropped too.
cap200() {
    local v=${1:0:200} u_pat tail run
    u_pat='\\u[0-9A-Fa-f]?[0-9A-Fa-f]?[0-9A-Fa-f]?$'
    if [[ $v =~ $u_pat ]]; then
        v=${v%${BASH_REMATCH[0]}}
    fi
    tail=$v
    run=0
    while [[ $tail == *\\ ]]; do
        tail=${tail%\\}
        run=$((run + 1))
    done
    if [ $((run % 2)) -eq 1 ]; then
        v=${v%\\}
    fi
    printf '%s' "$v"
}

chunk=
IFS= read -r -n 4096 -d '' chunk

marker='"tool_input"'
base=${chunk%%"$marker"*}

ev=$(extract hook_event_name "$base")
[ -n "$ev" ] || exit 0

sid=$(extract session_id "$base")
aid=$(extract agent_id "$base")
at=$(extract agent_type "$base")
tool=$(extract tool_name "$base")
nt=$(extract notification_type "$base")
cwd=$(extract cwd "$base")
proj=${cwd##*/}

role=$AGENT_ROLE
role=${role//[^A-Za-z0-9._-]/}

desc=
sub=
q=
case "$tool" in
    Agent|Task|AskUserQuestion)
        rest=
        IFS= read -r -d '' rest || true
        full=$chunk$rest
        after=${full#"$base"}
        case "$tool" in
            Agent|Task)
                desc=$(cap200 "$(extract description "$after")")
                sub=$(extract subagent_type "$after")
                ;;
            AskUserQuestion)
                q=$(cap200 "$(extract question "$after")")
                ;;
        esac
        ;;
esac

printf '{"ev":"%s","sid":"%s","aid":"%s","at":"%s","tool":"%s","nt":"%s","proj":"%s","role":"%s","desc":"%s","sub":"%s","q":"%s"}\n' \
    "$ev" "$sid" "$aid" "$at" "$tool" "$nt" "$proj" "$role" "$desc" "$sub" "$q" \
    >> "$dir/events.jsonl" 2>/dev/null

exit 0
