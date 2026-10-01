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
#   agent-file.sh backfill [--dry-run]                        -> old lines: take work and wait from the text of each line
#   agent-file.sh backfill <name> [--dry-run] [--force] <todo done options>   -> set the data of one finished line
#   agent-file.sh data [<repo path>...]                       -> table: one row per finished task, every repo on this machine
#   agent-file.sh eta <name> [--step <n>] [--work-so-far <m>] [--wait <m>]    -> one line: work left, done around, owner needed next
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
# backfill (no name): every old line (no data block, not dropped) is read for its work:
#   "work <a> + bounce <b> = <c>" gives work <c>; else the first "work <n>" gives work <n>; "wait <n>" gives wait.
#   Letter case does not matter, the "m" after a number is optional. "est <n>m actual <n>m" is not scanned.
#   A work number found: the line gets a data block (est and clock from the old field, other keys "-"), its text stays.
#   No work number: the line stays. Prints "took: <name> work <n> wait <n|->" or "skipped: <name> (<why>)",
#   then "backfill: took <n>, skipped <n>". --dry-run prints the same and writes nothing. One atomic write.
# backfill <name>: the LAST line of that name that is not dropped; only that line changes, its text stays.
#   Same options and same refusals as todo done. An old line: est and clock from its old field, the facts given.
#   A line that has data is refused unless --force: then the facts given replace, every other key keeps its value.
#   Refused (one line on stderr, exit 1, nothing written): no such line, only a dropped line, no fact given.
#   Prints "wrote: <the new line>" and "TIME DATA: <n> of 30". --dry-run prints "would write: <the new line>" only.
#
# data: read-only. Columns: repo name date type lane mock est work wait clock bounces workers files lines tests adds.
#   An old line gives est and clock, "-" elsewhere. The repo column is the data block's repo, else the folder name.
#   Repos, in this order, the same repo (real path) once:
#     1. this repo
#     2. the keys of "territories" in world.json in the city home ($AGENT_CITY_HOME, default ~/.claude/agent-city);
#        a key "<repo>/.git" names <repo>, any other key is passed over; no python3 or a bad file: passed over
#     3. the lines of joined-repos.txt in the city home (absolute paths; blank lines and "#" comments are passed over)
#     4. the paths given as arguments
#   It reads only <repo>/agent_completed.txt of another repo and writes nothing there.
#   No such file or folder: one line "skipped ..." on stderr, exit stays 0.
#
# eta: one line, nothing written. est comes from the open todo line <name>. step = how far the work is, 0 to 7
#   (7 = done; no step = 0). All minutes round up.
#   work so far = --work-so-far, else est x step / 7.  work left = est - work so far.
#   Over the estimate (work so far >= est): work left = work so far x (7 - step) / step, the pace so far.
#   Over the estimate with no step: refused, the line names --step.
#   done = now + work left + --wait. --wait is waiting still ahead; it is said in the line, never counted as work.
#   owner needed next: "mock ready" when the todo text says mock (not "no mock") and step <= 2, at
#   now + work left x (3 - step) / (7 - step) (the wait is not added); else "review", at the done time.
#   A time that is not today is shown as "<HH:MM> tomorrow" or "<HH:MM> on <YYYY-MM-DD>".
#
# AGENT_FAKE_NOW="YYYY-MM-DD HH:MM" replaces the machine clock (tests). Unset or empty: the machine clock.
# Files live in the main repo, never in a worktree. Writes are atomic (tmp + mv).

set -eu
TIME_DATA_GOAL=30
DATA_TYPES="page server script docs cloud app data mixed"
DATA_KEYS="repo type lane mock est work wait clock bounces workers files lines tests adds"
OPT_CMD="todo done"   # the prefix of a refusal from done_opts; backfill sets it to "backfill"
. "$(dirname "$0")/agent-roots.sh"
roots_read
ROOT="$PROJECT_ROOT"
TODO="$ROOT/agent_todo.txt"; DONE="$ROOT/agent_completed.txt"; IDEAS="$ROOT/agent_ideas.txt"; WT="$ROOT/agent_worktree.txt"
NOW=${AGENT_FAKE_NOW:-$(date '+%Y-%m-%d %H:%M')}; WHO=${AGENT_ROLE:-main}
case "${1:-}" in data|eta) ;; *) touch "$TODO" "$DONE" "$IDEAS" "$WT";; esac   # data and eta only read

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
want_num() { is_num "$2" || refuse "$OPT_CMD: $1 wants a whole number, 0 or more (got: $2)"; }
# want_in <option> <value> <word>...
want_in() {
  local o="$1" v="$2" w
  shift 2
  for w in "$@"; do [ "$w" = "$v" ] && return 0; done
  refuse "$OPT_CMD: $o is one of: $* (got: $v)"
}
# d_files, d_lines from git diff --shortstat <from> <to>; <value> is what the caller typed
git_count() {
  local opt="$1" st
  st=$(LC_ALL=C git -C "$ROOT" diff --shortstat "$3" "$4" -- 2>/dev/null) || refuse "$OPT_CMD: $opt: git does not know $2"
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
      *) refuse "$OPT_CMD: unknown option: $o";;
    esac
    [ $# -ge 2 ] || refuse "$OPT_CMD: $o needs a value"
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
      --merge)   case "$v" in ''|-*) refuse "$OPT_CMD: --merge wants a commit (got: $v)";; esac; merge=$v;;
      --range)   range=$v;;
    esac
  done
  if [ -n "$merge" ] && [ -n "$range" ]; then refuse "$OPT_CMD: --merge and --range together; give one"; fi
  if [ -n "$merge" ]; then git_count --merge "$merge" "$merge^1" "$merge"; fi
  if [ -n "$range" ]; then
    case "$range" in *..*) ;; *) refuse "$OPT_CMD: --range wants <a>..<b> (got: $range)";; esac
    a=${range%%..*}; b=${range#*..}
    case "$a:$b" in :*|*:|-*|*:-*) refuse "$OPT_CMD: --range wants <a>..<b> (got: $range)";; esac
    base=$(git -C "$ROOT" merge-base "$a" "$b" 2>/dev/null) || refuse "$OPT_CMD: --range: git does not know $range"
    git_count --range "$range" "$base" "$b"
  fi
}

# --- backfill
# scan_num "<lower case text>" "<regex>": the last number of the first match of <regex>, as a word of its own
scan_num() { printf '%s' "$1" | grep -oE "(^|[^a-z])$2" | head -1 | grep -oE '[0-9]+$' || true; }
# backfill [--dry-run]: the text scan of every old line
backfill_text() {
  local dry="" a ln name text work wt took=0 skipped=0 tmp="$DONE.tmp"
  for a in "$@"; do
    case "$a" in --dry-run) dry=1;; *) refuse "backfill: unknown option: $a";; esac
  done
  [ -n "$dry" ] || : > "$tmp"
  while IFS= read -r ln || [ -n "$ln" ]; do
    if [ -n "$ln" ]; then
      name=${ln#* | }; name=${name%% | *}
      case "$ln" in
        *'| dropped: '*) echo "skipped: $name (dropped)"; skipped=$((skipped + 1));;
        *' | data '*)    echo "skipped: $name (already has data)"; skipped=$((skipped + 1));;
        *)
          text=${ln% | *}; text=${text#* | }; text=$(printf '%s' "${text#* | }" | tr 'A-Z' 'a-z')
          work=$(scan_num "$text" 'work +[0-9]+m? *[+] *bounces? +[0-9]+m? *= *[0-9]+')
          [ -n "$work" ] || work=$(scan_num "$text" 'work +[0-9]+')
          if [ -z "$work" ]; then
            echo "skipped: $name (no work number in the text)"; skipped=$((skipped + 1))
          else
            wt=$(scan_num "$text" 'wait +[0-9]+')
            dreset; d_repo=$(repo_name "$ROOT"); d_est=$(old_est "$ln"); d_clock=$(old_clock "$ln")
            d_est=${d_est:--}; d_clock=${d_clock:--}; d_work=$((10#$work)); d_wait=${wt:--}
            [ "$d_wait" = - ] || d_wait=$((10#$d_wait))
            ln="${ln% | *} | $(dblock)"
            echo "took: $name work $d_work wait $d_wait"; took=$((took + 1))
          fi;;
      esac
    fi
    [ -n "$dry" ] || printf '%s\n' "$ln" >> "$tmp"
  done < "$DONE"
  [ -n "$dry" ] || { [ "$took" -eq 0 ] && rm -f "$tmp" || mv "$tmp" "$DONE"; }
  echo "backfill: took $took, skipped $skipped"
}
# backfill <name> [--dry-run] [--force] <todo done options>: the facts of one finished line
backfill_name() {
  local name="$1" dry="" force="" has="" given="" i a k v n line new
  shift; OPT_CMD=backfill
  i=$#
  while [ "$i" -gt 0 ]; do   # --dry-run and --force may stand anywhere; the rest goes on to done_opts
    a=$1; shift; i=$((i - 1))
    case "$a" in --dry-run) dry=1;; --force) force=1;; *) set -- "$@" "$a";; esac
  done
  n=$(awk -v k="$name" -F' \\| ' '$2 == k && !/[|] dropped: /{n = NR} END{print n + 0}' "$DONE")
  if [ "$n" -eq 0 ]; then
    if awk -v k="$name" -F' \\| ' '$2 == k {f = 1} END{exit !f}' "$DONE"; then
      refuse "backfill: $name: only a dropped line has that name, nothing to set"
    fi
    refuse "no completed line named: $name"
  fi
  line=$(sed -n "${n}p" "$DONE")
  dreset
  done_opts "$@"
  case "$line" in *' | data '*) has=1;; esac
  [ -z "$has" ] || [ -n "$force" ] || refuse "backfill: $name already has data; --force replaces the facts you give"
  for k in type lane mock work wait bounces workers files lines tests adds; do
    eval "v=\$d_$k"; [ "$v" = - ] || given=1
  done
  [ -n "$given" ] || refuse "backfill: $name: no fact given (--work, --wait, --bounces, --workers, --mock, --lane, --type, --tests, --adds, --merge, --range)"
  if [ -n "$has" ]; then
    for k in $DATA_KEYS; do
      eval "v=\$d_$k"
      [ "$v" != - ] || { v=$(dkey "$line" "$k"); eval "d_$k=\${v:--}"; }
    done
  else
    d_repo=$(repo_name "$ROOT"); d_est=$(old_est "$line"); d_clock=$(old_clock "$line")
    d_est=${d_est:--}; d_clock=${d_clock:--}
  fi
  new="${line% | *} | $(dblock)"
  if [ -n "$dry" ]; then echo "would write: $new"; return 0; fi
  NEW="$new" awk -v n="$n" 'NR == n {print ENVIRON["NEW"]; next} {print}' "$DONE" > "$DONE.tmp" && mv "$DONE.tmp" "$DONE"
  echo "wrote: $new"
  echo "TIME DATA: $(time_data) of $TIME_DATA_GOAL"
}

# --- data
DATA_FMT='%-14s %-30s %-10s %-6s %-4s %-4s %5s %5s %5s %6s %7s %7s %5s %6s %5s %4s\n'
DATA_SEEN="
"
# dload "<line>": d_* from the data block of the line ("-" for a key it does not say)
dload() {
  local w k
  dreset
  for w in ${1##* | data }; do
    k=${w%%=*}
    case " $DATA_KEYS " in *" $k "*) eval "d_$k=\${w#*=}";; esac
  done
}
# the repo folders named by the keys of "territories" in world.json: "<repo>/.git" gives <repo>
world_repos() {
  [ -f "$1" ] || return 0
  command -v python3 >/dev/null 2>&1 || { echo "note: no python3, so $1 is not read" >&2; return 0; }
  python3 -c '
import json, sys
t = json.load(open(sys.argv[1])).get("territories")
for k in (t if isinstance(t, dict) else []):
    if k.endswith("/.git") and len(k) > 5:
        print(k[:-5])
' "$1" 2>/dev/null || echo "note: $1 is not read (not valid)" >&2
}
# data_repo <path>: the rows of one repo, once
data_repo() {
  local rp ln name date repo
  rp=$(cd "$1" 2>/dev/null && pwd -P) || { echo "skipped: no such folder: $1" >&2; return 0; }
  case "$DATA_SEEN" in *"
$rp
"*) return 0;; esac
  DATA_SEEN="$DATA_SEEN$rp
"
  [ -f "$rp/agent_completed.txt" ] || { echo "skipped: no agent_completed.txt in $1" >&2; return 0; }
  repo=$(repo_name "$rp")
  while IFS= read -r ln || [ -n "$ln" ]; do
    case "$ln" in ''|*'| dropped: '*) continue;; esac
    name=${ln#* | }; name=${name%% | *}; date=${ln%% | *}
    case "$ln" in
      *' | data '*) dload "$ln";;
      *) dreset; d_est=$(old_est "$ln"); d_clock=$(old_clock "$ln");;
    esac
    [ "${d_repo:--}" != - ] || d_repo=$repo
    printf "$DATA_FMT" "${d_repo// /_}" "${name// /_}" "${date// /_}" "${d_type:--}" "${d_lane:--}" "${d_mock:--}" \
      "${d_est:--}" "${d_work:--}" "${d_wait:--}" "${d_clock:--}" "${d_bounces:--}" "${d_workers:--}" \
      "${d_files:--}" "${d_lines:--}" "${d_tests:--}" "${d_adds:--}"
  done < "$rp/agent_completed.txt"
}
# data [<repo path>...]
data_run() {
  local city="${AGENT_CITY_HOME:-${HOME:-}/.claude/agent-city}" p list
  printf "$DATA_FMT" repo name date type lane mock est work wait clock bounces workers files lines tests adds
  data_repo "$ROOT"
  list=$(world_repos "$city/world.json")
  while IFS= read -r p; do [ -z "$p" ] || data_repo "$p"; done <<< "$list"
  if [ -f "$city/joined-repos.txt" ]; then
    while read -r p || [ -n "$p" ]; do
      case "$p" in /*) data_repo "$p";; esac
    done < "$city/joined-repos.txt"
  fi
  for p in "$@"; do data_repo "$p"; done
}

# --- eta
# epoch seconds -> "YYYY-MM-DD HH:MM", BSD date first (macOS), GNU date as fallback
from_epoch() { date -r "$1" '+%Y-%m-%d %H:%M' 2>/dev/null || date -d "@$1" '+%Y-%m-%d %H:%M'; }
# eta_when <epoch>: "HH:MM", "HH:MM tomorrow" or "HH:MM on YYYY-MM-DD" (needs $today and $tomorrow of eta_run)
eta_when() {
  local s d
  s=$(from_epoch "$1"); d=${s%% *}
  if [ "$d" = "$today" ]; then echo "${s#* }"
  elif [ "$d" = "$tomorrow" ]; then echo "${s#* } tomorrow"
  else echo "${s#* } on $d"; fi
}
# eta <name> [--step <n>] [--work-so-far <m>] [--wait <m>]
eta_run() {
  local name="$1" step="" wsf="" wt=0 o v line est s left mock_m="" now_e noon who who_e done_e today tomorrow msg
  shift; OPT_CMD=eta
  while [ $# -gt 0 ]; do
    o=$1
    case "$o" in --step|--work-so-far|--wait) ;; *) refuse "eta: unknown option: $o";; esac
    [ $# -ge 2 ] || refuse "eta: $o needs a value"
    v=$2; shift 2
    case "$o" in
      --step)        is_num "$v" && [ $((10#$v)) -le 7 ] || refuse "eta: --step is a whole number from 0 to 7 (got: $v)"; step=$((10#$v));;
      --work-so-far) want_num "$o" "$v"; wsf=$((10#$v));;
      --wait)        want_num "$o" "$v"; wt=$((10#$v));;
    esac
  done
  line=; [ ! -f "$TODO" ] || line=$(first "$TODO" "$name")
  [ -n "$line" ] || refuse "no todo line named: $name"
  est=$(old_num "$line" est)
  [ -n "$est" ] || refuse "eta: no estimate on the todo line: $name"
  est=$((10#$est)); s=${step:-0}
  if [ -z "$wsf" ]; then left=$(( (est * (7 - s) + 6) / 7 ))
  elif [ "$wsf" -lt "$est" ]; then left=$((est - wsf))
  elif [ "$s" -ge 1 ]; then left=$(( (wsf * (7 - s) + s - 1) / s ))
  else refuse "eta: --work-so-far is over the estimate, so --step (1 to 7) is needed for the pace so far"
  fi
  case "$(printf '%s\n' "$line" | awk -F' \\| ' '{print $3}' | tr 'A-Z' 'a-z')" in
    *'no mock'*) ;;
    *mock*) if [ "$s" -le 2 ]; then mock_m=$(( (left * (3 - s) + 6 - s) / (7 - s) )); fi;;
  esac
  now_e=$(to_epoch "$NOW"); today=${NOW%% *}; noon=$(to_epoch "$today 12:00")
  [ -n "$now_e" ] && [ -n "$noon" ] || refuse "eta: cannot read the time: $NOW"
  tomorrow=$(from_epoch $((noon + 86400))); tomorrow=${tomorrow%% *}
  done_e=$((now_e + (left + wt) * 60))
  if [ "$wt" -gt 0 ]; then msg="about $left min of work left and $wt min of waiting"; else msg="about $left min of work left"; fi
  if [ -n "$mock_m" ]; then who="mock ready"; who_e=$((now_e + mock_m * 60)); else who=review; who_e=$done_e; fi
  echo "$msg, done around $(eta_when "$done_e"); owner needed next: $who about $(eta_when "$who_e")"
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
  backfill:*)
    shift
    case "${1:-}" in ''|--*) backfill_text "$@";; *) backfill_name "$@";; esac;;
  data:*)
    shift; data_run "$@";;
  eta:*)
    [ $# -ge 2 ] || usage
    case "$2" in --*) usage;; esac
    shift; eta_run "$@";;
  *) usage;;
esac
