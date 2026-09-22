#!/usr/bin/env bash
# agent-file.sh — the only way to write agent_*.txt. No agent, no tokens, one format.
#
#   agent-file.sh todo add  "<name>" "<size>" "<what>" [est_minutes]  -> agent_todo.txt
#   agent-file.sh todo done "<name>"                          -> line moves to agent_completed.txt as: date | name | what | est <n>m actual <n>m
#   agent-file.sh idea add  "<text>"                          -> agent_ideas.txt
#   agent-file.sh idea list                                   -> print agent_ideas.txt, numbered (cat -n)
#   agent-file.sh idea rm   <n>                                -> remove line n from agent_ideas.txt
#   agent-file.sh worktree set "<path>" "<module>" "<status>" -> agent_worktree.txt (add or replace)
#   agent-file.sh worktree rm  "<path>"                       -> agent_worktree.txt
#   agent-file.sh show                                        -> print all four files
#   agent-file.sh time                                        -> table: name, est, actual, ratio (agent_completed.txt)
#
# Files live in the main repo, never in a worktree. Writes are atomic (tmp + mv).

set -eu
. "$(dirname "$0")/agent-roots.sh"
roots_read
ROOT="$PROJECT_ROOT"
TODO="$ROOT/agent_todo.txt"; DONE="$ROOT/agent_completed.txt"; IDEAS="$ROOT/agent_ideas.txt"; WT="$ROOT/agent_worktree.txt"
NOW=$(date '+%Y-%m-%d %H:%M'); WHO=${AGENT_ROLE:-main}
touch "$TODO" "$DONE" "$IDEAS" "$WT"

usage() { sed -n '2,16p' "$0"; exit 2; }
need()  { [ $# -ge "$1" ] || usage; }
append(){ printf '%s\n' "$2" >> "$1"; }
# drop lines whose first field (before " | ") equals $2 from file $1
drop()  { awk -v k="$2" -F' \\| ' '$1 != k' "$1" > "$1.tmp" && mv "$1.tmp" "$1"; }
first() { awk -v k="$2" -F' \\| ' '$1 == k {print; exit}' "$1"; }
# "YYYY-MM-DD HH:MM" -> epoch seconds, BSD date first (macOS), GNU date as fallback
to_epoch() { date -j -f '%Y-%m-%d %H:%M' "$1" +%s 2>/dev/null || date -d "$1" +%s 2>/dev/null || true; }

case "${1:-}:${2:-}" in
  todo:add)
    need 5 "$@"; drop "$TODO" "$3"
    what="$5"
    [ -n "${6:-}" ] && what="$5 | est ${6}m"
    append "$TODO" "$3 | $4 | $what | opened $NOW | by $WHO"
    echo "todo added: $3";;
  todo:done)
    need 3 "$@"; line=$(first "$TODO" "$3")
    [ -n "$line" ] || { echo "no todo line named: $3" >&2; exit 1; }
    what=$(printf '%s\n' "$line" | awk -F' \\| ' '{print $3}')
    est=$(printf '%s' "$line" | grep -o 'est [0-9][0-9]*m' | head -1 | sed 's/est //;s/m//')
    [ -n "$est" ] || est="-"
    opened=$(printf '%s\n' "$line" | sed -n 's/.*opened \([0-9][0-9-]* [0-9:]*\).*/\1/p')
    actual="-"
    if [ -n "$opened" ]; then
      o=$(to_epoch "$opened"); n=$(to_epoch "$NOW")
      if [ -n "$o" ] && [ -n "$n" ]; then actual=$(( (n - o) / 60 )); fi
    fi
    [ "$est" = "-" ] && est_disp="-" || est_disp="${est}m"
    [ "$actual" = "-" ] && actual_disp="-" || actual_disp="${actual}m"
    date="${NOW%% *}"
    drop "$TODO" "$3"; append "$DONE" "$date | $3 | $what | est $est_disp actual $actual_disp"
    echo "todo done: $3";;
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
    printf '%-30s %8s %8s %8s\n' "name" "est" "actual" "ratio"
    [ -s "$DONE" ] || exit 0
    while IFS= read -r ln; do
      [ -n "$ln" ] || continue
      name=$(printf '%s' "$ln" | awk -F' \\| ' '{print $2}')
      last=$(printf '%s' "$ln" | awk -F' \\| ' '{print $NF}')
      est=$(printf '%s' "$last" | grep -o 'est [0-9][0-9]*m' | head -1 | sed 's/est //;s/m//')
      actual=$(printf '%s' "$last" | grep -o 'actual [0-9][0-9]*m' | head -1 | sed 's/actual //;s/m//')
      [ -n "$est" ] || est="-"
      [ -n "$actual" ] || actual="-"
      if [ "$est" != "-" ] && [ "$actual" != "-" ]; then
        ratio=$(awk -v a="$actual" -v e="$est" 'BEGIN{printf "%.1f", a/e}')
      else
        ratio="-"
      fi
      printf '%-30s %8s %8s %8s\n' "$name" "$est" "$actual" "$ratio"
    done < "$DONE";;
  *) usage;;
esac
