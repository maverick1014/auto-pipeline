#!/usr/bin/env bash
# agent-guard.sh — the board-trust launch hook (PreToolUse / PostToolUse Agent|Task|Bash,
# SubagentStart, SubagentStop). Rules: requirements/board-trust.md.
#
# Bash builtins only on the fast path: a Bash call that does not mention
# "orca terminal|worktree" exits 0 at once and python never starts.
#
# Protocol with agent_guard.py: its last stdout line is exactly one of
#   OK              silent allow
#   WARN <line>     allow, <line> to stderr
#   BLOCK <line>    <line> to stderr, exit 2
# A line "POINT <line>" may come before the last line: a moment pointer (rules/*.md), turned here
# into the PreToolUse additionalContext JSON on stdout; never a gate.
# python never signals by exit code (python3 exits 2 for a missing script, which
# would look like a block). This wrapper exits non-zero only with 2 for a BLOCK.

IFS= read -r -d '' p

re_bash='"tool_name"[[:space:]]*:[[:space:]]*"Bash"'
re_orca='orca([[:space:]]|\\\\|\\n|\\t)+(terminal|worktree|orchestration)|agent-runtime\.sh[^[:alnum:]]{1,6}close'
re_point='agent-file\.sh.*(todo.{1,8}add|checks.{1,8}gate)|agent-promote\.sh|git.*push'
if [[ $p =~ $re_bash ]] && ! [[ $p =~ $re_orca ]] && ! [[ $p =~ $re_point ]]; then
  exit 0
fi

py="$(dirname "$0")/agent_guard.py"
if [ ! -f "$py" ]; then
  echo "board guard: agent_guard.py missing; allowed" >&2
  exit 0
fi

out=$(printf '%s' "$p" | python3 "$py" 2>/dev/null)
rc=$?
last=${out##*$'\n'}
if [ "$rc" -ne 0 ]; then
  echo "board guard: agent_guard.py failed (exit $rc); allowed" >&2
  exit 0
fi
point=
if [[ $out == POINT\ * ]]; then
  point=${out%%$'\n'*}
  point=${point#POINT }
fi
emit_point() {
  [ -n "$point" ] || return 0
  point=${point//\\/\\\\}
  point=${point//\"/\\\"}
  printf '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "%s"}}\n' "$point"
}
case "$last" in
  OK) emit_point; exit 0;;
  "WARN "*) echo "${last#WARN }" >&2; emit_point; exit 0;;
  "BLOCK "*) echo "${last#BLOCK }" >&2; exit 2;;
  *) echo "board guard: agent_guard.py failed (exit $rc); allowed" >&2; exit 0;;
esac
