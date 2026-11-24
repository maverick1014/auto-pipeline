#!/usr/bin/env bash
# agent-keyword.sh — UserPromptSubmit hook: a keyword in the human's prompt
# adds one line telling the agent to run the matching skill. The hook only
# points; the logic lives in the skill (PRINCIPLES.md E4).
# Always exit 0, no network, nothing on stderr.
# Edit the KEYWORDS table below: one line per skill, keywords split by "|".
set -u
[ -t 0 ] && exit 0
IN=$(cat)

# KEYWORDS: skill <TAB> keyword|keyword (case-insensitive substring match)
read -r -d '' KEYWORDS <<'TABLE' || true
/auto-pipeline:init	setup pipeline|设置插件
/auto-pipeline:settings	show settings|看设置|改设置
/auto-pipeline:todo	show todo|看任务|进度
/auto-pipeline:question	show question|有什么问题|要我决定什么
/auto-pipeline:close-case	close case|收尾
/auto-pipeline:clean-up	clean up files|清理文件
/auto-pipeline:city	open city|看 agent
TABLE

printf '%s' "$IN" | KW="$KEYWORDS" python3 -c '
import json, os, sys
try:
    p = str(json.loads(sys.stdin.read()).get("prompt", "")).lower()
except Exception:
    sys.exit(0)
for line in os.environ["KW"].splitlines():
    skill, _, words = line.partition("\t")
    if skill and any(w.strip().lower() in p for w in words.split("|") if w.strip()):
        print("Keyword hook: run skill %s. If the words are only mentioned or quoted, ignore this." % skill)
' 2>/dev/null
exit 0
