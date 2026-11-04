#!/usr/bin/env bash
# agent-show-question.sh — UserPromptSubmit hook, two jobs:
#  1. "show question" (and related words, or a prompt that is just "questions")
#     in the human's prompt: print the instruction that fits the session's role:
#     run `agent-file.sh questions` (whole repo, main manager) or
#     `agent-file.sh questions --self` (task manager, Helper), 10 or fewer in
#     chat, more than 10 as an Artifact page.
#  2. The done flow: the session's own agent_state.txt has a "QUESTIONS PAGE:"
#     line, the page still has an open question, and the prompt is a done word
#     (done, 答完了 ...) or an answer list (1A 2B ...): print the instruction to
#     read every answer at once and close each question.
# A show trigger wins over the done flow. A quoted mention is not an order. A
# spawned helper agent (worker, deputy, reviewer) gets nothing.
# Never blocks the prompt: always exit 0, nothing on stderr, writes no file.
# See hooks/hooks.json (UserPromptSubmit, right after agent-show-todo.sh),
# PRINCIPLES.md W18 and tests/test_agent_show_question.py (the CONTRACT
# docstring is the spec).
#
#   Claude Code -> stdin JSON {"session_id","transcript_path","cwd",
#   "permission_mode","hook_event_name","prompt"} -> stdout is added to the
#   session's context.
set -u

[ -t 0 ] && exit 0
exec 2>/dev/null
IN=$(cat)

# Fast path: the session id, the transcript path and the cwd are cut out first
# (a folder or a session named ...question must not count as the human typing
# it). The stems are also matched as backslash-u escapes (JSON may carry either).
# No stem and no done word or answer list: python never starts.
CUT=$(printf '%s' "$IN" \
  | sed -e 's/"session_id" *: *"[^"]*"//' -e 's/"transcript_path" *: *"[^"]*"//' -e 's/"cwd" *: *"[^"]*"//')

SHOW_CAND=0
DONE_CAND=0
printf '%s' "$CUT" | grep -qiE 'question|decide|decision|问题|回答|决定|\\u95ee\\u9898|\\u56de\\u7b54|\\u51b3\\u5b9a' && SHOW_CAND=1
{ printf '%s' "$CUT" | grep -qiE 'done|answered|finished|好了|完成|答|\\u597d\\u4e86|\\u5b8c\\u6210|\\u7b54' \
  || printf '%s' "$CUT" | grep -qE '"prompt" *: *" *[0-9]'; } && DONE_CAND=1
[ "$SHOW_CAND$DONE_CAND" = "00" ] && exit 0

. "$(dirname "$0")/agent-roots.sh"

# A done word or an answer list counts only with a QUESTIONS PAGE line in the
# session's own agent_state.txt (the git toplevel of the payload cwd).
HASPAGE=0
PAGELINE=""
if [ "$DONE_CAND" = 1 ]; then
  JCWD=$(printf '%s' "$IN" | sed -n 's/.*"cwd" *: *"\([^"]*\)".*/\1/p' | head -1)
  roots_read "$JCWD"
  if [ -f "$STATE_DIR/agent_state.txt" ]; then
    PAGELINE=$(grep -m1 '^QUESTIONS PAGE: ' "$STATE_DIR/agent_state.txt")
  fi
  [ -n "$PAGELINE" ] && HASPAGE=1
fi
[ "$SHOW_CAND" = 0 ] && [ "$HASPAGE" = 0 ] && exit 0

# The prompt can be far bigger than ARG_MAX, so it is never passed in env or
# argv: the python code is loaded into a variable and the data goes to stdin.
read -r -d '' PYCODE <<'PY' || true
import json, re, sys

raw = sys.stdin.buffer.read().decode("utf-8", "replace")
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
haspage = len(sys.argv) > 1 and sys.argv[1] == "1"

QUOTES = "\"'" + chr(96) + "“”‘’«»「」『』"


def unquoted(text, start):
    return start == 0 or text[start - 1] not in QUOTES


E = r"(?<![A-Za-z0-9_])"
X = r"(?![A-Za-z0-9_])"
SHOW = [
    r"show\s+(?:pending\s+)?questions?", r"list\s+(?:the\s+)?questions?",
    r"pending\s+questions?", r"open\s+questions?", r"questions\s+for\s+me",
    r"question\s+list", r"pending\s+decisions?", r"show\s+decisions?",
    r"what\s+do\s+i\s+(?:need|have)\s+to\s+decide", r"what\s+needs\s+my\s+decision",
]
show_re = re.compile(E + "(?:" + "|".join(SHOW) + ")" + X, re.I)
zh_re = re.compile("显示问题|列出问题|问题列表|待回答|待决定|要我决定|要我回答|待我决定|待我回答|我要决定什么")
whole_re = re.compile(r"\W*(questions?|any\s+questions?|有问题吗|还有问题吗|有什么问题|有没有问题|问题)\W*", re.I)

done_whole = re.compile(
    r"\W*(done|all\s+done|answered|finished|ok\s+done|i['’]m\s+done|好了|完成了?|答好了|选好了|都答了|答完了?)\W*", re.I)
done_any = re.compile("答完了|" + E + r"(?:answered\s+all|all\s+answered)" + X, re.I)
answer_list = re.compile(r"\s*(?:\d+[A-Ha-h](?![A-Za-z0-9])|\d+\s*[—–-])")

show = any(unquoted(prompt, m.start()) for m in show_re.finditer(prompt))
show = show or any(unquoted(prompt, m.start()) for m in zh_re.finditer(prompt))
if not show:
    whole = whole_re.fullmatch(prompt)
    show = bool(whole) and unquoted(prompt, whole.start(1))

done = False
if not show and haspage:
    whole = done_whole.fullmatch(prompt)
    done = bool(whole) and unquoted(prompt, whole.start(1))
    done = done or any(unquoted(prompt, m.start()) for m in done_any.finditer(prompt))
    done = done or bool(answer_list.match(prompt))

if show:
    sys.stdout.write("SHOW\x1f%s\n" % cwd)
elif done:
    sys.stdout.write("DONE\x1f%s\n" % cwd)
PY

OUT=$(printf '%s' "$IN" | python3 -c "$PYCODE" "$HASPAGE" 2>/dev/null)
[ -z "$OUT" ] && exit 0

KIND=""
CWD=""
while IFS=$'\x1f' read -r tag a; do
  KIND="$tag"; CWD="$a"
done <<<"$OUT"

roots_read "$CWD" 2>/dev/null
[ -f "$PROJECT_ROOT/agent.conf" ] || exit 0
conf_read 2>/dev/null

NAME=$(basename "$STATE_DIR")
REPO=$(basename "$PROJECT_ROOT")

# Who we are: exactly like show todo (agent-roots.sh role_read, one copy).
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

AF="$PLUGIN_ROOT/bin/agent-file.sh"

if [ "$KIND" = SHOW ]; then
  case "${language:-en}" in
    zh|zh-*) HEADING="## 要你决定"; MARK="(建议)"; DONEWORD="答完了" ;;
    en|en-*) HEADING="## To decide"; MARK="(recommended)"; DONEWORD="done" ;;
    *)       HEADING="## To decide (in your language)"; MARK="(recommended, in your language)"; DONEWORD="done (in your language)" ;;
  esac
  if [ -z "$SELF" ]; then
    LINE1="SHOW QUESTION: you are the main manager \"$REPO Manager\": every question that waits on the owner, whole repo (PRINCIPLES.md W18)."
  else
    LINE1="SHOW QUESTION: you are $WHO: the questions of your own task only (PRINCIPLES.md W18)."
  fi
  printf '%s\nOnly a mention of the words (a brief, a quote)? Ignore this.\n1. Run this one command from the project folder, nothing else:\n   %s questions%s\n2. Its first line is the count. 10 or fewer: show all as a numbered list in chat under %s, each a decide item (title, sub line, facts, lettered options, the recommended one marked %s), nothing dropped. The owner answers like "1A 2B — note".\n3. More than 10: the same command with --page <file> (a file in your scratchpad); publish that file with the Artifact tool (capabilities db and user). The QUESTIONS PAGE line of agent_state.txt has the url: publish with that url (redeploy). A first publish: record the new url with %s questions --url <url>. Then one chat line: the count, the link, answer all, then tell me (%s).\n4. No Artifact tool: the chat list of all, nothing dropped.\n' \
    "$LINE1" "$AF" "$SELF" "$HEADING" "$MARK" "$AF" "$DONEWORD"
  exit 0
fi

# ---- the done flow: is a question of the page still open? ----
URL="${PAGELINE#QUESTIONS PAGE: }"
REST="${URL#* | }"
URL="${URL%% | *}"
REST="${REST#* | }"
MAPF="${REST%% | *}"

OPENCODE='
import json, sys
try:
    now = {q.get("id") for q in json.loads(sys.stdin.read()).get("questions", [])}
except Exception:
    sys.exit(0)
mapped = None
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        mapped = {q.get("id") for q in json.load(fh).get("questions", [])}
except Exception:
    mapped = None
if (now & mapped) if mapped is not None else now:
    print("open")
'
OPEN=$(cd "$PROJECT_CWD" 2>/dev/null && "$AF" questions$SELF --json 2>/dev/null | python3 -c "$OPENCODE" "$MAPF" 2>/dev/null)
[ "$OPEN" = open ] || exit 0

printf 'QUESTIONS ANSWERED: the owner says the questions page is answered (PRINCIPLES.md W18).\nOnly a mention of the words (a quote)? Ignore this.\n1. The page: %s\n   Read every answer at once with ArtifactData (list, the "answers" collection). Lines the owner pasted in chat go by number through the map file %s.\n2. Show one table: question, answer.\n3. For each answered question run: %s questions answer <id> "<answer>" and carry on. An unpicked question is still open.\n' \
  "$URL" "$MAPF" "$AF"

exit 0
