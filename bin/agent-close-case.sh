#!/usr/bin/env bash
# agent-close-case.sh — UserPromptSubmit hook: sees the words "close case" in
# the human's prompt and prints the settle-down / merge-decision instructions
# that fit the session's role (task manager, human-direct, or main manager).
# Never blocks the prompt: always exit 0, nothing on stderr, no file ever
# written. See hooks/hooks.json (UserPromptSubmit, last entry) and
# tests/test_agent_close_case.py (the CONTRACT docstring is the spec).
#
#   Claude Code -> stdin JSON {"session_id","transcript_path","cwd",
#   "permission_mode","hook_event_name","prompt"} -> stdout is added to the
#   session's context.
set -u

[ -t 0 ] && exit 0
IN=$(cat)

# Fast path: most prompts never mention "close" at all, so never start
# python for them.
printf '%s' "$IN" | grep -qi close 2>/dev/null || exit 0

# The prompt can be far bigger than the OS exec limit for one process's
# argv+environment (ARG_MAX, 1 MB on macOS), so it is never passed in env or
# argv: the python code itself is loaded into a variable (small, fixed size,
# safe as an argv word) and the data is piped to python's stdin instead.
read -r -d '' PYCODE <<'PY' || true
import json, re, sys

raw = sys.stdin.read()
try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)

prompt = data.get("prompt") or ""
cwd = data.get("cwd") or ""

QUOTES = "\"'" + chr(96) + "“”‘’"


def unquoted(text, start):
    return start == 0 or text[start - 1] not in QUOTES


trigger_re = re.compile(r"\bclose\s+case\b", re.I)
triggered = any(unquoted(prompt, m.start()) for m in trigger_re.finditer(prompt))
if not triggered:
    sys.exit(0)

report_re = re.compile(r"CLOSE CASE\s+([^\s:]+)\s*:\s*(finished|unfinished)\b", re.I)
reports = [(m.group(1), m.group(2).lower())
           for m in report_re.finditer(prompt) if unquoted(prompt, m.start())]

sys.stdout.write("CWD\x1f%s\n" % cwd)
for name, status in reports:
    sys.stdout.write("REPORT\x1f%s\x1f%s\n" % (name, status))
PY

OUT=$(printf '%s' "$IN" | python3 -c "$PYCODE" 2>/dev/null)
[ -z "$OUT" ] && exit 0

CWD=""
REPORT_NAMES=()
REPORT_STATUSES=()
while IFS=$'\x1f' read -r tag a b; do
  case "$tag" in
    CWD) CWD="$a" ;;
    REPORT) REPORT_NAMES+=("$a"); REPORT_STATUSES+=("$b") ;;
  esac
done <<<"$OUT"

. "$(dirname "$0")/agent-roots.sh"
roots_read "$CWD" 2>/dev/null
[ -f "$PROJECT_ROOT/agent.conf" ] || exit 0

NAME=$(basename "$STATE_DIR")
REPO=$(basename "$PROJECT_ROOT")

# The role comes from role_read (agent-roots.sh, one copy for every hook);
# this script keeps its own names for the four cases.
role_read
case "$role" in
  spawned)  role=task-manager ;;
  second)   role=human-direct ;;
  takeover) role=orphan ;;
esac

IGNORE_LINE="Only a mention of the words (a brief, a question)? Ignore this. The upper decision on your report (finish first, close now)? Follow it."

case "$role" in
  task-manager|human-direct|orphan)
    if [ "$role" = task-manager ]; then
      LINE1="CLOSE CASE: you are the task manager \"$NAME\"."
    else
      LINE1="CLOSE CASE: you are the task manager \"$NAME\" (human-direct)."
    fi
    if [ "$role" = orphan ]; then
      UPPER="No live main manager (lock pid $lpid): print the report here, the human decides. First line:"
    else
      UPPER="Report to the main manager \"$REPO Manager\" (not listed: the \"$REPO-<xx>\" row) with SendMessage (another machine: print it in this terminal and say so). First line:"
    fi
    printf '%s\n%s\nOtherwise settle down now (PRINCIPLES.md W13):\n1. Start nothing new. Running workers finish their slice or stop cleanly.\n2. Save agent_state.txt. Commit + push the branch, a WIP commit if unfinished. Never lose work.\n3. %s\n   CLOSE CASE %s: finished   or   CLOSE CASE %s: unfinished\n   Then: what is done, what is left + next steps, tests run + results, E2E click path, new ideas, TIME: est <n>m, actual <n>m, human <n>m\n4. Wait for the decision: finish first, or close now. Never close yourself.\n' \
      "$LINE1" "$IGNORE_LINE" "$UPPER" "$NAME" "$NAME"
    ;;
  main)
    if [ "${#REPORT_NAMES[@]}" -gt 0 ]; then
      parts=""
      for i in "${!REPORT_NAMES[@]}"; do
        [ -n "$parts" ] && parts="$parts; "
        parts="$parts${REPORT_NAMES[$i]} ${REPORT_STATUSES[$i]}"
      done
      printf 'CLOSE CASE report: %s. You are the main manager (PRINCIPLES.md W13).\nOnly a mention of the words? Ignore this.\nfinished -> the normal path: /auto-pipeline:merge (browser E2E, merge deputy, cleanup).\nunfinished -> review it against the requirement, then decide:\n  finish first -> tell it to go on to DONE, then /auto-pipeline:merge\n  close now -> /auto-pipeline:close-case: branch stays pushed, todo line stays open with the next steps, pane closed, worktree removed\nLog the decision in agent_state.txt. Human away -> decide by the requirement doc and mark it "owner not seen".\n' \
        "$parts"
    else
      printf 'CLOSE CASE: you are the main manager. From the human this means the whole repo wraps up (PRINCIPLES.md W13).\nOnly a mention of the words? Ignore this.\nOtherwise run /auto-pipeline:close-case: send "close case" to every live task manager and human-direct session in agent_worktree.txt, collect every CLOSE CASE report, decide each, merge what passes, close all panes and worktrees, stop the crons and monitors you started, update the agent files. Then one final table to the human: task, result, what changed, what is left, decisions taken for the human. Nothing dropped.\n'
    fi
    ;;
esac

exit 0
