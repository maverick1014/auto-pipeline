#!/usr/bin/env bash
# agent-file.sh — the only way to write agent_*.txt. No agent, no tokens, one format.
#
#   agent-file.sh todo add  "<name>" "<size>" "<what>" [est_minutes] [by]  -> agent_todo.txt (by defaults to "main")
#   agent-file.sh todo done "<name>" ["<result>"] [--work <m>] [--wait <m>] [--bounces <n>] [--workers <n>]
#                 [--mock yes|no] [--lane fast|full] [--type <t>] [--tests <n>] [--adds <n>]
#                 [--merge <commit> | --range <a>..<b>]       -> line moves to agent_completed.txt as one data line
#   agent-file.sh todo drop "<name>" "<reason>"               -> line moves to agent_completed.txt as: date | name | what | est <n>m actual - | dropped: <reason>
#   agent-file.sh idea add  "<text>"                          -> agent_ideas.txt
#   agent-file.sh idea list                                   -> print agent_ideas.txt, numbered (cat -n)
#   agent-file.sh idea rm   <n>                                -> remove line n from agent_ideas.txt
#   agent-file.sh worktree set "<path>" "<module>" "<status>" -> agent_worktree.txt (add or replace)
#   agent-file.sh worktree rm  "<path>"                       -> agent_worktree.txt
#   agent-file.sh show                                        -> print all four files
#   agent-file.sh time                                        -> table: name est work wait clock ratio (agent_completed.txt)
#
# todo done: every option is optional; a number is a whole number, 0 or more. "<result>" is not stored.
#   work = agent minutes. wait = minutes spent waiting (mock gate, owner, suite slot). Never mixed.
#   <t> is one of: page server script docs cloud app data mixed.
#   est comes from the todo line. clock = minutes from "opened" to now. repo = folder name of the main repo.
#   files and lines (lines = added + deleted) are counted only when asked, in the main repo:
#     --merge <commit>   git diff --shortstat <commit>^1 <commit>    what the merge brought in
#     --range <a>..<b>   git diff --shortstat <merge-base a b> <b>   what b changed since it left a
#   Neither given: files=- lines=- and "not counted" is printed. Both given, or a commit git does not know: refused.
#   A bad option is refused: one line on stderr that names it, exit 1, nothing moves.
#   It prints "todo done: <name>" and "TIME DATA: <n> of 30" (finished tasks that have a work number).
#
# The line in agent_completed.txt (keys in this order, "-" when not known):
#   <date> | <name> | <what> | data repo=<r> type=<t> lane=<l> mock=<yes|no> est=<m> work=<m> wait=<m> clock=<m> bounces=<n> workers=<n> files=<n> lines=<n> tests=<n> adds=<n>
#   An old line ("est <n>m actual <n>m") has no data block.
#
# time: ratio = work / est, one decimal; "-" when work or est is missing. An old line is est + clock, never work.
#   Dropped lines are skipped.
#
# AGENT_FAKE_NOW="YYYY-MM-DD HH:MM" replaces the machine clock (tests). Unset or empty: the machine clock.
# Files live in the main repo, never in a worktree. Writes are atomic (tmp + mv).

set -eu
TIME_DATA_GOAL=30
DATA_TYPES="page server script docs cloud app data mixed"
. "$(dirname "$0")/agent-roots.sh"
roots_read
ROOT="$PROJECT_ROOT"
TODO="$ROOT/agent_todo.txt"; DONE="$ROOT/agent_completed.txt"; IDEAS="$ROOT/agent_ideas.txt"; WT="$ROOT/agent_worktree.txt"
NOW=${AGENT_FAKE_NOW:-$(date '+%Y-%m-%d %H:%M')}; WHO=${AGENT_ROLE:-main}
touch "$TODO" "$DONE" "$IDEAS" "$WT"

# the whole header comment block, whatever its length
usage() { awk 'NR > 1 { if (/^#/) print; else exit }' "$0"; exit 2; }
need()  { [ $# -ge "$1" ] || usage; }
append(){ printf '%s\n' "$2" >> "$1"; }
# drop lines whose first field (before " | ") equals $2 from file $1
drop()  { awk -v k="$2" -F' \\| ' '$1 != k' "$1" > "$1.tmp" && mv "$1.tmp" "$1"; }
first() { awk -v k="$2" -F' \\| ' '$1 == k {print; exit}' "$1"; }
# "YYYY-MM-DD HH:MM" -> epoch seconds, BSD date first (macOS), GNU date as fallback
to_epoch() { date -j -f '%Y-%m-%d %H:%M' "$1" +%s 2>/dev/null || date -d "$1" +%s 2>/dev/null || true; }

# --- small helpers (todo done, time; also for backfill, data, eta)
# a whole number, 0 or more
is_num() { case "$1" in ''|*[!0-9]*) return 1;; esac; return 0; }
# "<line>": ONE line on stderr, exit 1. Call it at the top level, before any file changes.
refuse() { echo "$1" >&2; exit 1; }
# folder name of a repo path (no spaces, so it stays one word in a data block)
repo_name() { basename "$1" | tr ' ' '_'; }
# minutes from "YYYY-MM-DD HH:MM" $1 to $2; nothing when a date does not read or $2 is before $1
minutes_between() {
  local o n
  o=$(to_epoch "$1"); n=$(to_epoch "$2")
  [ -n "$o" ] && [ -n "$n" ] && [ "$n" -ge "$o" ] && echo $(( (n - o) / 60 )) || true
}
# the data block as d_<key> variables: dreset sets them all to "-", dblock prints "data repo=... adds=..."
dreset() {
  d_repo=-; d_type=-; d_lane=-; d_mock=-; d_est=-; d_work=-; d_wait=-; d_clock=-
  d_bounces=-; d_workers=-; d_files=-; d_lines=-; d_tests=-; d_adds=-
}
dblock() {
  printf 'data repo=%s type=%s lane=%s mock=%s est=%s work=%s wait=%s clock=%s bounces=%s workers=%s files=%s lines=%s tests=%s adds=%s' \
    "$d_repo" "$d_type" "$d_lane" "$d_mock" "$d_est" "$d_work" "$d_wait" "$d_clock" \
    "$d_bounces" "$d_workers" "$d_files" "$d_lines" "$d_tests" "$d_adds"
}
# dkey "<line>" <key>: that key of the line's data block (can be "-"); nothing when the line has no block
dkey() {
  local w
  case "$1" in *' | data '*) ;; *) return 0;; esac
  for w in ${1##* | data }; do
    case "$w" in "$2="*) printf '%s' "${w#*=}"; return 0;; esac
  done
}
# old_num "<text>" est|actual: n of the first "est <n>m" / "actual <n>m" in the text
old_num() { printf '%s' "$1" | grep -o "$2 [0-9][0-9]*m" | head -1 | sed "s/$2 //;s/m//"; }
# est and clock (the old "actual") of an old completed line "... | est <n>m actual <n>m"
old_est()   { old_num "${1##* | }" est; }
old_clock() { old_num "${1##* | }" actual; }
# lines of agent_completed.txt that have a data block with a work number (dropped lines never count)
time_data() {
  awk '/[|] dropped: /{next} sub(/^.* [|] data /,"") && /(^| )work=[0-9]+( |$)/{n++} END{print n+0}' "$DONE"
}

# --- todo done options
want_num() { is_num "$2" || refuse "todo done: $1 wants a whole number, 0 or more (got: $2)"; }
# want_in <option> <value> <word>...
want_in() {
  local o="$1" v="$2" w
  shift 2
  for w in "$@"; do [ "$w" = "$v" ] && return 0; done
  refuse "todo done: $o is one of: $* (got: $v)"
}
# d_files, d_lines from git diff --shortstat <from> <to>; <value> is what the caller typed
git_count() {
  local opt="$1" st
  st=$(LC_ALL=C git -C "$ROOT" diff --shortstat "$3" "$4" -- 2>/dev/null) || refuse "todo done: $opt: git does not know $2"
  set -- $(printf '%s\n' "$st" | awk '{for (i = 2; i <= NF; i++) {if ($i ~ /^file/) f = $(i-1); else if ($i ~ /^insertion/) a = $(i-1); else if ($i ~ /^deletion/) d = $(i-1)}} END{print f+0, a+d}')
  d_files=$1; d_lines=$2
}
# every option of todo done into d_*; refuses the first bad one. Nothing is written here.
done_opts() {
  local o v merge="" range="" a b base
  while [ $# -gt 0 ]; do
    o="$1"
    case "$o" in
      --work|--wait|--bounces|--workers|--tests|--adds|--mock|--lane|--type|--merge|--range) ;;
      *) refuse "todo done: unknown option: $o";;
    esac
    [ $# -ge 2 ] || refuse "todo done: $o needs a value"
    v="$2"; shift 2
    case "$o" in
      --work)    want_num "$o" "$v"; d_work=$v;;
      --wait)    want_num "$o" "$v"; d_wait=$v;;
      --bounces) want_num "$o" "$v"; d_bounces=$v;;
      --workers) want_num "$o" "$v"; d_workers=$v;;
      --tests)   want_num "$o" "$v"; d_tests=$v;;
      --adds)    want_num "$o" "$v"; d_adds=$v;;
      --mock)    want_in "$o" "$v" yes no; d_mock=$v;;
      --lane)    want_in "$o" "$v" fast full; d_lane=$v;;
      --type)    want_in "$o" "$v" $DATA_TYPES; d_type=$v;;
      --merge)   case "$v" in ''|-*) refuse "todo done: --merge wants a commit (got: $v)";; esac; merge=$v;;
      --range)   range=$v;;
    esac
  done
  if [ -n "$merge" ] && [ -n "$range" ]; then refuse "todo done: --merge and --range together; give one"; fi
  if [ -n "$merge" ]; then git_count --merge "$merge" "$merge^1" "$merge"; fi
  if [ -n "$range" ]; then
    case "$range" in *..*) ;; *) refuse "todo done: --range wants <a>..<b> (got: $range)";; esac
    a=${range%%..*}; b=${range#*..}
    case "$a:$b" in :*|*:|-*|*:-*) refuse "todo done: --range wants <a>..<b> (got: $range)";; esac
    base=$(git -C "$ROOT" merge-base "$a" "$b" 2>/dev/null) || refuse "todo done: --range: git does not know $range"
    git_count --range "$range" "$base" "$b"
  fi
}

case "${1:-}:${2:-}" in
  todo:add)
    need 5 "$@"; drop "$TODO" "$3"
    what="$5"
    [ -n "${6:-}" ] && what="$5 | est ${6}m"
    by="${7:-$WHO}"
    append "$TODO" "$3 | $4 | $what | opened $NOW | by $by"
    echo "todo added: $3";;
  todo:done)
    need 3 "$@"; name="$3"; line=$(first "$TODO" "$name")
    [ -n "$line" ] || { echo "no todo line named: $name" >&2; exit 1; }
    shift 3
    case "${1:-}" in --*) ;; *) [ $# -eq 0 ] || shift;; esac   # the "<result>" text is not stored
    dreset; d_files=; d_lines=
    done_opts "$@"
    counted=yes; [ -n "$d_files" ] || { counted=; d_files=-; d_lines=-; }
    what=$(printf '%s\n' "$line" | awk -F' \\| ' '{print $3}')
    est=$(old_num "$line" est)
    opened=$(printf '%s\n' "$line" | sed -n 's/.*opened \([0-9][0-9-]* [0-9:]*\).*/\1/p')
    clock=; [ -z "$opened" ] || clock=$(minutes_between "$opened" "$NOW")
    d_repo=$(repo_name "$ROOT"); d_est=${est:--}; d_clock=${clock:--}
    date="${NOW%% *}"
    drop "$TODO" "$name"; append "$DONE" "$date | $name | $what | $(dblock)"
    echo "todo done: $name"
    [ -n "$counted" ] || echo "files and lines: not counted (no --merge or --range)"
    echo "TIME DATA: $(time_data) of $TIME_DATA_GOAL";;
  todo:drop)
    need 5 "$@"; line=$(first "$TODO" "$3")
    [ -n "$line" ] || { echo "no todo line named: $3" >&2; exit 1; }
    what=$(printf '%s\n' "$line" | awk -F' \\| ' '{print $3}')
    est=$(printf '%s' "$line" | grep -o 'est [0-9][0-9]*m' | head -1 | sed 's/est //;s/m//')
    [ -n "$est" ] || est="-"
    [ "$est" = "-" ] && est_disp="-" || est_disp="${est}m"
    date="${NOW%% *}"
    drop "$TODO" "$3"; append "$DONE" "$date | $3 | $what | est $est_disp actual - | dropped: $4"
    echo "todo dropped: $3";;
  idea:add)
    need 3 "$@"; append "$IDEAS" "$3 | $NOW | by $WHO"
    echo "idea added";;
  idea:list)
    [ -s "$IDEAS" ] && cat -n "$IDEAS" || echo "(empty)";;
  idea:rm)
    need 3 "$@"; n="$3"
    case "$n" in ''|*[!0-9]*) echo "no idea number $n" >&2; exit 1;; esac
    line=$(sed -n "${n}p" "$IDEAS")
    [ -n "$line" ] || { echo "no idea number $n" >&2; exit 1; }
    sed "${n}d" "$IDEAS" > "$IDEAS.tmp" && mv "$IDEAS.tmp" "$IDEAS"
    printf 'idea %s removed: %s\n' "$n" "$(printf '%s' "$line" | cut -c1-60)";;
  worktree:set)
    need 5 "$@"; old=$(first "$WT" "$3"); since=$(printf '%s' "$old" | awk -F' \\| ' '{print $4}')
    [ -n "$since" ] || since="since $NOW"
    drop "$WT" "$3"; append "$WT" "$3 | $4 | $5 | $since"
    echo "worktree $5: $3";;
  worktree:rm)
    need 3 "$@"; drop "$WT" "$3"; echo "worktree removed: $3";;
  show:*)
    for f in "$TODO" "$DONE" "$IDEAS" "$WT"; do
      echo "=== $(basename "$f") ==="; [ -s "$f" ] && cat "$f" || echo "(empty)"; echo
    done;;
  time:)
    printf '%-30s %8s %8s %8s %8s %8s\n' "name" "est" "work" "wait" "clock" "ratio"
    [ -s "$DONE" ] || exit 0
    while IFS= read -r ln; do
      [ -n "$ln" ] || continue
      case "$ln" in *'| dropped: '*) continue;; esac
      name=${ln#* | }; name=${name%% | *}
      case "$ln" in
        *' | data '*) est=$(dkey "$ln" est); work=$(dkey "$ln" work); wt=$(dkey "$ln" wait); clock=$(dkey "$ln" clock);;
        *) est=$(old_est "$ln"); work=; wt=; clock=$(old_clock "$ln");;
      esac
      est=${est:--}; work=${work:--}; wt=${wt:--}; clock=${clock:--}
      if is_num "$work" && is_num "$est" && [ "$est" -gt 0 ]; then
        ratio=$(awk -v w="$work" -v e="$est" 'BEGIN{printf "%.1f", w/e}')
      else
        ratio="-"
      fi
      printf '%-30s %8s %8s %8s %8s %8s\n' "$name" "$est" "$work" "$wt" "$clock" "$ratio"
    done < "$DONE";;
  *) usage;;
esac
