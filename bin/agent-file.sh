#!/usr/bin/env bash
# agent-file.sh — the only way to write agent_*.txt. No agent, no tokens, one format.
#
#   agent-file.sh todo add  "<name>" "<size>" "<what>" [est_minutes]  -> agent_todo.txt
#   agent-file.sh todo done "<name>" "<result>"               -> line moves to agent_completed.txt, records actual minutes
#   agent-file.sh idea add  "<text>"                          -> agent_ideas.txt
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

usage() { sed -n '2,14p' "$0"; exit 2; }
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
    need 4 "$@"; line=$(first "$TODO" "$3")
    [ -n "$line" ] || { echo "no todo line named: $3" >&2; exit 1; }
    opened=$(printf '%s\n' "$line" | sed -n 's/.*opened \([0-9][0-9-]* [0-9:]*\).*/\1/p')
    actual="actual ?"
    if [ -n "$opened" ]; then
      o=$(to_epoch "$opened"); n=$(to_epoch "$NOW")
      if [ -n "$o" ] && [ -n "$n" ]; then actual="actual $(( (n - o) / 60 ))m"; fi
    fi
    drop "$TODO" "$3"; append "$DONE" "$line | $4 | $actual | done $NOW"
    echo "todo done: $3";;
  idea:add)
    need 3 "$@"; append "$IDEAS" "$3 | $NOW | by $WHO"
    echo "idea added";;
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
      name=$(printf '%s' "$ln" | awk -F' \\| ' '{print $1}')
      est=$(printf '%s' "$ln" | grep -o 'est [0-9][0-9]*m' | head -1 | sed 's/est //;s/m//')
      actual=$(printf '%s' "$ln" | grep -o 'actual [0-9][0-9]*m' | head -1 | sed 's/actual //;s/m//')
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
