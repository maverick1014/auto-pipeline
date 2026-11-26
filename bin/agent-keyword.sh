#!/usr/bin/env bash
# agent-keyword.sh — UserPromptSubmit hook: a keyword in the human's prompt
# adds one line telling the agent to run the matching skill. The hook only
# points; the logic lives in the skill (PRINCIPLES.md E4).
# Always exit 0, no network, nothing on stderr.
# Edit the KEYWORDS table below: one line per skill, keywords split by "|".
set -u
[ -t 0 ] && exit 0
IN=$(cat)

# KEYWORDS: skill <TAB> keyword|keyword [<TAB> extra sentence] (case-insensitive substring match)
read -r -d '' KEYWORDS <<'TABLE' || true
/auto-pipeline:init	setup pipeline|设置插件
/auto-pipeline:settings	show settings|看设置|改设置
/auto-pipeline:todo	show todo|看任务|进度
/auto-pipeline:question	show question|有什么问题|要我决定什么
/auto-pipeline:close-case	close case|收尾
/auto-pipeline:clean-up	clean up files|清理文件
/auto-pipeline:city	open city|看 agent
/auto-pipeline:teacher-teach-me	teach me|explain to me|can you explain|教我|解释一下|给我讲讲	Pass his question as the argument; a question about the work in progress in this chat is answered by the main agent itself.
TABLE

OUT=$(printf '%s' "$IN" | KW="$KEYWORDS" python3 -c '
import json, os, sys
try:
    d = json.loads(sys.stdin.read())
    p = str(d.get("prompt", "")).lower()
except Exception:
    sys.exit(0)
for line in os.environ["KW"].splitlines():
    skill, _, words = line.partition("\t")
    words, _, extra = words.partition("\t")
    if skill and any(w.strip().lower() in p for w in words.split("|") if w.strip()):
        print("Keyword hook: run skill %s. %sIf the words are only mentioned or quoted, ignore this." % (skill, extra + " " if extra else ""))
APPROVAL = ("publish", "merge to main", "release", "deploy", "production", "上线", "发布", "部署", "skip the", "leave out", "跳过")
if not d.get("agent_id") and any(w in p for w in APPROVAL):
    print("\001" + str(d.get("cwd", "")).replace("\n", " "))
' 2>/dev/null) || OUT=""
CWD=""
while IFS= read -r L; do
  case "$L" in
    $'\001'*) CWD=${L#$'\001'}; WANT=1 ;;
    "") ;;
    *) printf '%s\n' "$L" ;;
  esac
done <<EOF2
$OUT
EOF2
if [ "${WANT:-}" = 1 ] && [ -z "${AGENT_ROLE:-}" ]; then
  (
    . "$(dirname "$0")/agent-roots.sh" 2>/dev/null || exit 0
    roots_read "$CWD" 2>/dev/null || exit 0
    repo_set_up 2>/dev/null || exit 0
    role_read 2>/dev/null
    [ "${role:-}" = main ] || exit 0
    echo "Approval hook: if the owner is approving a publish or a skipped check here, read his words by the approval cases (PRINCIPLES.md R8) and the per-task target (W9). If the words are only mentioned or quoted, ignore this."
  ) 2>/dev/null
fi
exit 0
