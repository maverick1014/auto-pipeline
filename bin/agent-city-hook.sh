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

# has_question_prefix KEY HAY — true when the value of "KEY" in HAY begins
# with the literal text QUESTION: -- a prefix match only, so it works even
# when HAY is cut off mid-value (no closing quote needed).
has_question_prefix() {
    local key=$1 hay=$2 pat
    pat='"'"$key"'"[[:space:]]*:[[:space:]]*"QUESTION:'
    [[ $hay =~ $pat ]]
}

# unescape STR — reverse the three JSON escapes a path can carry: \" \\ \/.
# Builtins only; any other backslash escape (never produced by a real path)
# is left as-is.
unescape() {
    local s=$1 out= chunk ch
    while :; do
        case "$s" in
            *\\*)
                chunk=${s%%\\*}
                out=$out$chunk
                s=${s#*\\}
                ch=${s:0:1}
                s=${s:1}
                case "$ch" in
                    '"') out=$out'"' ;;
                    '\') out=$out'\' ;;
                    /) out=$out/ ;;
                    *) out=$out'\'$ch ;;
                esac
                ;;
            *) out=$out$s; break ;;
        esac
    done
    printf '%s' "$out"
}

# escape_json STR — JSON-escape backslash and double quote, the only two
# characters a physical filesystem path can carry that would break the line.
escape_json() {
    local s=$1 out= chunk ch
    while :; do
        case "$s" in
            *[\"\\]*)
                chunk=${s%%[\"\\]*}
                out=$out$chunk
                s=${s#"$chunk"}
                ch=${s:0:1}
                s=${s:1}
                out=$out'\'$ch
                ;;
            *) out=$out$s; break ;;
        esac
    done
    printf '%s' "$out"
}

# find_git_folder DIR — walk up from the plain (unescaped) path DIR to the
# first folder holding .git; print it (0), or print nothing (1) when DIR
# does not exist or no .git turns up.
find_git_folder() {
    local p=$1
    [ -d "$p" ] || return 1
    while :; do
        [ -e "$p/.git" ] && { printf '%s' "$p"; return 0; }
        [ "$p" = / ] && return 1
        p=${p%/*}
        [ -z "$p" ] && p=/
    done
}

# classify_path RAW FOLDER — the kind of work for the JSON-escaped path RAW
# (tool_input.file_path/notebook_path), taken relative to the plain FOLDER
# that holds .git ("" when there is none); outside FOLDER, or when FOLDER is
# "", classify by the base name alone. Folder rules match any path segment;
# name rules match the base name; first rule that fits wins. Never prints
# the path itself.
classify_path() {
    local raw=$1 folder=$2 plain rel base dirpart segs
    plain=$(unescape "$raw")
    rel=
    if [ -n "$folder" ]; then
        case "$plain" in
            "$folder"/*) rel=${plain#"$folder"/} ;;
        esac
    fi
    [ -n "$rel" ] || rel=${plain##*/}
    case "$rel" in
        */*) base=${rel##*/}; dirpart=${rel%/*} ;;
        *) base=$rel; dirpart= ;;
    esac
    segs="/$dirpart/"
    case "$segs" in
        */test/*|*/tests/*|*/__tests__/*|*/spec/*|*/e2e/*) printf test; return ;;
    esac
    case "$base" in
        test_*|*_test.*|*.test.*|*.spec.*|*_spec.*|*Test.*) printf test; return ;;
    esac
    case "$segs" in
        */docs/*|*/doc/*|*/requirements/*) printf doc; return ;;
    esac
    case "$base" in
        *.md|*.markdown|*.mdx|*.rst|*.adoc|*.txt) printf doc; return ;;
    esac
    case "$segs" in
        */components/*|*/ui/*|*/views/*|*/pages/*|*/widgets/*|*/screens/*) printf ui; return ;;
    esac
    case "$base" in
        *.html|*.htm|*.css|*.scss|*.sass|*.less|*.jsx|*.tsx|*.vue|*.svelte) printf ui; return ;;
    esac
    case "$segs" in
        */bin/*|*/scripts/*|*/.github/*) printf script; return ;;
    esac
    case "$base" in
        *.sh|*.bash|*.zsh|*.fish|*.ps1|*.bat|*.cmd|*.mk|Makefile|Dockerfile) printf script; return ;;
    esac
    printf other
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

# repo — growth (requirements/city.md): the physical path of the git common
# dir of cwd, so a linked worktree gives its main repo's .git.
cwd_plain=$(unescape "$cwd")
git_folder=$(find_git_folder "$cwd_plain")
repo=
if [ -n "$git_folder" ]; then
    gitdir_path=
    if [ -d "$git_folder/.git" ]; then
        gitdir_path=$git_folder/.git
    elif [ -f "$git_folder/.git" ]; then
        gitline=
        IFS= read -r gitline < "$git_folder/.git" 2>/dev/null
        case "$gitline" in
            "gitdir: "*) gitdir_path=${gitline#"gitdir: "} ;;
        esac
        if [ -n "$gitdir_path" ]; then
            case "$gitdir_path" in
                /*) : ;;
                *) gitdir_path=$git_folder/$gitdir_path ;;
            esac
        fi
    fi
    if [ -n "$gitdir_path" ]; then
        common_path=$gitdir_path
        if [ -f "$gitdir_path/commondir" ]; then
            cline=
            IFS= read -r cline < "$gitdir_path/commondir" 2>/dev/null
            if [ -n "$cline" ]; then
                case "$cline" in
                    /*) common_path=$cline ;;
                    *) common_path=$gitdir_path/$cline ;;
                esac
            fi
        fi
        repo_raw=$(cd -P -- "$common_path" 2>/dev/null && pwd -P)
        [ -n "$repo_raw" ] && repo=$(escape_json "$repo_raw")
    fi
fi

role=$AGENT_ROLE
role=${role//[^A-Za-z0-9._-]/}

desc=
sub=
q=
klen=
kind=
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
    Bash|Edit|Write|MultiEdit|WebFetch|NotebookEdit)
        after4096=${chunk#"$base"}
        kval=
        case "$tool" in
            Bash) kval=$(extract command "$after4096") ;;
            Edit|Write|MultiEdit) kval=$(extract file_path "$after4096") ;;
            WebFetch) kval=$(extract url "$after4096") ;;
            NotebookEdit) kval=$(extract notebook_path "$after4096") ;;
        esac
        case "$tool" in
            NotebookEdit) : ;;
            *) [ -n "$kval" ] && klen=${#kval} ;;
        esac
        if [ "$ev" = PostToolUse ] && [ -n "$kval" ]; then
            case "$tool" in
                Edit|Write|MultiEdit|NotebookEdit) kind=$(classify_path "$kval" "$git_folder") ;;
            esac
        fi
        ;;
esac

# ask — "q" when a question is passed up the chain, else "": a SubagentStop
# whose last_assistant_message starts with QUESTION:, or a PostToolUse of
# SendMessage whose tool_input.message starts with QUESTION:. Only the
# flag, from the already-capped 4096-byte chunk: never the text, never the
# recipient.
ask=
case "$ev" in
    SubagentStop)
        has_question_prefix last_assistant_message "$chunk" && ask=q
        ;;
    PostToolUse)
        if [ "$tool" = SendMessage ]; then
            ti_chunk=${chunk#"$base"}
            has_question_prefix message "$ti_chunk" && ask=q
        fi
        ;;
esac

printf '{"ev":"%s","sid":"%s","aid":"%s","at":"%s","tool":"%s","nt":"%s","proj":"%s","role":"%s","desc":"%s","sub":"%s","q":"%s","klen":"%s","repo":"%s","kind":"%s","ask":"%s"}\n' \
    "$ev" "$sid" "$aid" "$at" "$tool" "$nt" "$proj" "$role" "$desc" "$sub" "$q" "$klen" "$repo" "$kind" "$ask" \
    >> "$dir/events.jsonl" 2>/dev/null

exit 0
