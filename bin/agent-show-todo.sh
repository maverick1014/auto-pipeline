#!/usr/bin/env bash
# agent-show-todo.sh — UserPromptSubmit hook: sees "show todo" (or a prompt that
# is just "todo") in the human's prompt and prints the instruction that fits the
# session's role: run `agent-file.sh board` (the whole repo, main manager) or
# `agent-file.sh board --self` (task manager, Helper), show its table as printed,
# then the decide section. A quoted mention is not an order. A spawned helper
# agent (worker, deputy, reviewer) gets nothing.
# Never blocks the prompt: always exit 0, nothing on stderr, writes no file.
# See hooks/hooks.json (UserPromptSubmit, right after agent-close-case.sh),
# PRINCIPLES.md W14 and tests/test_agent_show_todo.py (the CONTRACT docstring is
# the spec).
#
#   Claude Code -> stdin JSON {"session_id","transcript_path","cwd",
#   "permission_mode","hook_event_name","prompt"} -> stdout is added to the
#   session's context.
set -u

[ -t 0 ] && exit 0
IN=$(cat)

# Fast path: most prompts never contain "todo" at all, so never start python
# (or even look for the project) for them. The session id, the transcript path
# and the cwd are cut out first: a folder or a session named ...todo must not
# count as the human typing it.
printf '%s' "$IN" \
  | sed -e 's/"session_id" *: *"[^"]*"//' -e 's/"transcript_path" *: *"[^"]*"//' -e 's/"cwd" *: *"[^"]*"//' \
  | grep -qi todo 2>/dev/null || exit 0

. "$(dirname "$0")/agent-roots.sh"

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
if not isinstance(data, dict):
    sys.exit(0)

prompt = data.get("prompt") or ""
cwd = data.get("cwd") or ""
if not isinstance(prompt, str) or not isinstance(cwd, str):
    sys.exit(0)

QUOTES = "\"'" + chr(96) + "“”‘’"


def unquoted(text, start):
    return start == 0 or text[start - 1] not in QUOTES


# "show todo" / "show todos" anywhere. The word edges are ASCII only, so a
# Chinese character right next to the words does not hide them.
show_re = re.compile(r"(?<![A-Za-z0-9_])show\s+todos?(?![A-Za-z0-9_])", re.I)
triggered = any(unquoted(prompt, m.start()) for m in show_re.finditer(prompt))

# Or the whole prompt is just "todo", only spaces and punctuation around it.
if not triggered:
    whole = re.fullmatch(r"\W*(todo)\W*", prompt, re.I)
    triggered = bool(whole) and unquoted(prompt, whole.start(1))

if triggered:
    sys.stdout.write("CWD\x1f%s\n" % cwd)
PY

OUT=$(printf '%s' "$IN" | python3 -c "$PYCODE" 2>/dev/null)
[ -z "$OUT" ] && exit 0

CWD=""
while IFS=$'\x1f' read -r tag a; do
  case "$tag" in
    CWD) CWD="$a" ;;
  esac
done <<<"$OUT"

roots_read "$CWD" 2>/dev/null
[ -f "$PROJECT_ROOT/agent.conf" ] || exit 0
conf_read 2>/dev/null

NAME=$(basename "$STATE_DIR")
REPO=$(basename "$PROJECT_ROOT")

# Who we are. A spawned helper agent (AGENT_ROLE set, not task-manager) never
# gets this. Otherwise role_read decides (agent-roots.sh, one copy for every hook).
WHO=""
SELF=""
if [ -n "${AGENT_ROLE:-}" ]; then
  [ "$AGENT_ROLE" = task-manager ] || exit 0
  WHO="the task manager \"$NAME\""
  SELF=" --self"
else
  role_read
  case "$role" in
    main)     ;;
    second)   WHO="the Helper \"$NAME\" (human-direct)"; SELF=" --self" ;;
    takeover) WHO="\"$NAME\" (human-direct, no live main manager)"; SELF=" --self" ;;
    closed)   WHO="\"$NAME\", no longer the main manager"; SELF=" --self" ;;
    *)        exit 0 ;;
  esac
fi

case "${language:-en}" in
  zh|zh-*) HEADING="## 要你决定" ;;
  en|en-*) HEADING="## To decide" ;;
  *)       HEADING="## To decide (in your language)" ;;
esac

if [ -z "$SELF" ]; then
  LINE1="SHOW TODO: you are the main manager \"$REPO Manager\": the board of the whole repo (PRINCIPLES.md W14)."
else
  LINE1="SHOW TODO: you are $WHO: the board of your own task and its workers only (PRINCIPLES.md W14)."
fi

printf '%s\nOnly a mention of the words (a brief, a quote)? Ignore this.\n1. Run this one command from the project folder, nothing else (no agent, no other file read):\n   %s/bin/agent-file.sh board%s\n2. Show its output as printed: the table, every row, nothing added, dropped or changed, then its note lines.\n3. Then the decide section (%s): one numbered question per row that waits on the owner and per parked question, each with what, why now, evidence, recommendation (H3).\n' \
  "$LINE1" "$PLUGIN_ROOT" "$SELF" "$HEADING"

exit 0
