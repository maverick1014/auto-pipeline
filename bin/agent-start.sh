#!/usr/bin/env bash
# agent-start.sh — every agent runs this first, before any work.
#
#   ./agent-start.sh                          resource check + pointers + open tasks
#   ./agent-start.sh --quiz                   print the 29 quiz questions
#   ./agent-start.sh --answer "1A 2D ... 29B"    grade your quiz answers
#
# Rule: no work until the quiz says PASS.

set -u
. "$(dirname "$0")/agent-roots.sh"

# ---- quiz answer key (salted hashes, one per question) ----
SALT="auto-pipeline-quiz-v1"
KEY=( _ ff689d761d10c13d 38ebe4aa1afa125b 5b09070227aba9ed 8fad5dd001704a23 526a99cc5399c609 47db38d6283a87c2 2c0aa4aa4d1dc695 d20e713f26917f2c 810aeef60af42d9e 99878dad4233c435 ffa4bdb3449e9897 ff9345bd5e5cfefa 18defa25be09413b 52fcf5e8a49617f0 496f90a01d738ae5 ba6a4831a815a230 d956db8d1ed42790 72241f6e3363d877 64d26f41c9262571 8f6fba4ede3f932c 84bdc6be36e36afe 23f134bb4de59b4e 7fb8bf29915b93ba 4b57e10438403e80 a4dfa8b418c5d6de 5bc49497d74f49dc 96ebc45b039cdeb7 0a9317bb53ca4942 5beab162ea6db1e0 )
RULE=( _ W1 R6 H1 W2 W3 W4 W5 S4 S5 H3 R5 R2 R3 H4 S7 R1 W7 W6 W8 W5 W7 W9 W9 W9 R7 W10 W10 S8 S8 )
N=29

sha() { if command -v shasum >/dev/null; then shasum -a 256; else sha256sum; fi; }
h()   { printf '%s' "$1" | sha | cut -c1-16; }

# ---- --quiz: print the questions only, nothing else, no lock, no roots ----
if [ "${1:-}" = "--quiz" ]; then
  cat <<'QUIZ'
=== QUIZ — answer all 29 before any work ===
Reply by running:   ./agent-start.sh --answer "1A 2B 3C ... 29D"
Do not start work until you see PASS.

Q1. Mid-task, part of the spec is unclear.
  A. Pick a sensible default, log it, continue
  B. Stop and ask the human
  C. Skip that part
  D. Guess and say nothing

Q2. While working you think of a useful feature outside the task.
  A. Build it now
  B. Put it in the final report
  C. Tell the human right away
  D. Append it to agent_ideas.txt

Q3. You have three questions not related to the current task.
  A. Ask them now, one by one
  B. Drop them
  C. Park them; show them at the end in one table
  D. Append them to agent_ideas.txt

Q4. Task: build a settings page. Your first step:
  A. Write the component
  B. Make a clickable mock and get a yes
  C. Write a failing test
  D. Ask the human for a design

Q5. You are a worker. Your brief arrives. First:
  A. Write your own failing test
  B. Write code, tests later
  C. Ask if tests are needed
  D. Run the task manager's failing tests, then write code until they pass

Q6. You are one of four agents. You changed files under api/auth/. Which tests do you run?
  A. The full suite
  B. Tests for all of api/
  C. None; the manager runs them
  D. Tests for api/auth/ only

Q7. You must test a web page.
  A. Claude in Chrome
  B. Playwright
  C. curl
  D. jest-dom

Q8. RAM is at 85%. You need to start a sub-agent.
  A. Start it; it is only one
  B. Start it with a smaller model
  C. Wait until RAM drops below 80%
  D. Ask the human

Q9. Another agent is running a heavy test suite. You want to run yours.
  A. Queue and wait
  B. Run in parallel
  C. Run with fewer workers
  D. Skip your tests

Q10. Correct report shape:
  A. Result only
  B. Summary, background, steps, result, next steps
  C. Full log
  D. Result, what changed, what to decide

Q11. You finished the task "add login".
  A. Move the line to agent_completed.txt
  B. Delete the line from agent_todo.txt
  C. Mark it [x] in agent_todo.txt
  D. Add it to a changelog

Q12. You need the DB password from .secrets/.
  A. Copy it to .env
  B. Print it to confirm
  C. Read it, use it, never print it
  D. Commit it encrypted

Q13. You want to write ARCHITECTURE.md to explain the design.
  A. Write it
  B. Write it in README.md
  C. Put it in agent_ideas.txt
  D. Do not; only requirement, test and main idea docs are allowed

Q14. Your report compares three libraries.
  A. Paragraphs
  B. Bullet list
  C. Table
  D. Code block

Q15. You are two hours into a long task.
  A. Keep progress in memory
  B. Save state to a file as you go
  C. Save only at the end
  D. Write it in agent_todo.txt

Q16. Fast lane task. The human already checked the result on screen. Before merge you:
  A. Run the full suite
  B. Write a failing test first
  C. Run the minimal test
  D. Nothing; the human already verified

Q17. You are the main manager. A new feature will take about a day.
  A. Do it in this chat
  B. Spawn workers from this chat
  C. New worktree with a task manager inside
  D. Ask the human to do it

Q18. You are a task manager. A worker's code has a bug.
  A. Fix it yourself
  B. Skip it
  C. Ask the main manager to fix it
  D. Send it back to the worker, with evidence

Q19. A feature branch was just merged. The branch and worktree:
  A. Leave them for later
  B. Deputy deletes both now
  C. The worker deletes them
  D. The main manager deletes them

Q20. You are a worker. You need to check a web page in the browser.
  A. Write the click path, hand it to the main manager
  B. Use Claude in Chrome yourself
  C. Use Playwright
  D. Skip the check

Q21. You are the main manager. You need a worktree for a new feature. Two old worktrees are done and idle.
  A. Reuse one of the idle worktrees
  B. Open the new one now, clean the old ones later
  C. Ask the human
  D. Clean the idle ones first, then open the new one

Q22. You are the main manager. A 10-minute task arrives. Two worktrees are live.
  A. Open a new worktree for it
  B. Pass it to one of the live task managers
  C. Spawn a new deputy subagent to do it now
  D. Do it yourself

Q23. A big task about the auth module arrives. Worktree "auth" has a task manager working, with capacity.
  A. Open a new worktree
  B. Pass it to the auth task manager
  C. Spawn a deputy
  D. Ask the human

Q24. A task manager is compiling its workers' results. A related task arrives.
  A. Pass it now
  B. Open a new worktree for it
  C. Give it to a deputy
  D. Hold it until the task manager finishes

Q25. You are the main manager, about to dispatch a task. First:
  A. Read agent_worktree.txt
  B. Open a new worktree
  C. Spawn a deputy
  D. Ask the human which worktree is free

Q26. You start a new session. agent-start.sh says a main manager is already running.
  A. Become a second main manager
  B. Exit
  C. Read only, do nothing
  D. Become a task manager, tell the main manager you exist, take the human's task

Q27. You are that second session. The human says "report to main manager".
  A. Report done + click path to the main manager, then act as a normal task manager
  B. Keep working with the human
  C. Merge your own work
  D. Exit

Q28. Your context was just compacted. First:
  A. Continue from what you remember
  B. Re-read agent_state.txt and the rules the hook printed, continue from the file
  C. Ask the human what you were doing
  D. Start the task over

Q29. Your worker finished slice 1. Slice 2 is ready.
  A. Give slice 2 to the same worker
  B. Spawn a fresh worker with only slice 2's files
  C. Write slice 2 yourself
  D. Wait for the human
QUIZ
  exit 0
fi

# ---- grade ----
if [ "${1:-}" = "--answer" ]; then
  [ -z "${2:-}" ] && { echo 'usage: ./agent-start.sh --answer "1A 2D ... 29B"'; exit 2; }
  ok=0; wrong=""
  for q in $(seq 1 $N); do
    tok=$(printf '%s\n' $2 | grep -i "^${q}[a-d]$" | head -1)
    l=$(printf '%s' "${tok#$q}" | tr a-d A-D)
    if [ -n "$l" ] && [ "$(h "$SALT:$q:$l")" = "${KEY[$q]}" ]; then ok=$((ok+1)); else wrong="$wrong Q$q(${RULE[$q]})"; fi
  done
  if [ $ok -eq $N ]; then
    echo "QUIZ RESULT: $ok/$N PASS"; echo "You may start work."; exit 0
  else
    echo "QUIZ RESULT: $ok/$N FAIL"; echo "Wrong:$wrong"
    echo "Re-read those rules in PRINCIPLES.md, then answer again."; exit 1
  fi
fi

# ---- resources (defines the functions; reading happens below) ----
. "$PLUGIN_ROOT/bin/agent-resources.sh"

# ---- hook input (Claude Code SessionStart passes JSON on stdin) ----
SRC=startup; SID=""; CWD=""
if [ ! -t 0 ]; then
  IN=""; line=""
  while IFS= read -t 1 -r line || [ -n "$line" ]; do IN="$IN$line"; done   # read -t: never block on an open pipe; || keeps a final line with no trailing newline
  [ -n "$IN" ] && eval "$(printf '%s' "$IN" | python3 -c 'import json,sys,shlex
try:
    d=json.load(sys.stdin)
    print("SRC=%s; SID=%s; CWD=%s" % (shlex.quote(d.get("source","startup")), shlex.quote(d.get("session_id","")), shlex.quote(d.get("cwd",""))))
except Exception: print("SRC=startup; SID=; CWD=")' 2>/dev/null)"
fi

# ---- the two roots (bad or empty stdin JSON falls back to $PWD) ----
roots_read "$CWD"
conf_read

# ---- zero-touch setup guard (scope safety). A user-scope install turns
# this plugin on in every repo the owner opens, so a repo is only set up by
# itself, never by us, unless that repo's own project settings turn the
# plugin on. An agent.conf already there means the repo was set up by hand
# or by us before: nothing new happens, whatever the scope is. No agent.conf
# and no self-enable: this repo is untouched, print one line and stop, no
# lock, no monitor, no files, no directories. ----
SETUP_TEXT=""
if [ ! -f "$PROJECT_ROOT/agent.conf" ]; then
  self_enabled=no
  for sf in "$PROJECT_ROOT/.claude/settings.json" "$PROJECT_ROOT/.claude/settings.local.json"; do
    [ -f "$sf" ] && grep -qF "auto-pipeline@" "$sf" 2>/dev/null && self_enabled=yes
  done
  if [ "$self_enabled" = yes ]; then
    # Never claim setup happened when it did not: run it, keep the hook
    # alive either way (|| true), then check the one thing that matters —
    # agent.conf is really there now — before saying so.
    init_ok=yes
    "$PLUGIN_ROOT/bin/agent-init.sh" "$PROJECT_ROOT" >/dev/null 2>&1 || init_ok=no
    if [ "$init_ok" = yes ] && [ -f "$PROJECT_ROOT/agent.conf" ]; then
      SETUP_TEXT="auto-pipeline: first run, created agent.conf and the task files
auto-pipeline: run /auto-pipeline:init once to see the permission block and the cloud setup line to paste
"
      printf '%s' "$SETUP_TEXT"
      conf_read
    else
      SETUP_TEXT="auto-pipeline: setup failed, run /auto-pipeline:init by hand
"
      printf '%s' "$SETUP_TEXT"
      exit 0
    fi
  else
    echo "auto-pipeline: not set up in this repo, run /auto-pipeline:init to enable"
    exit 0
  fi
fi

mkdir -p "$PROJECT_GITDIR" 2>/dev/null || true
: "${max_usage_percent:=80}"
: "${auto_resume:=yes}"

# ---- role: one main manager per repo (W10) ----
agent_pid() {
  [ -n "${CLAUDE_PID:-}" ] && { echo "$CLAUDE_PID"; return; }
  p=$PPID
  for _ in 1 2 3 4 5 6 7 8; do
    c=$(ps -o comm= -p "$p" 2>/dev/null | tr -d ' ')
    case "$c" in *claude*|*codex*|*opencode*|*gemini*) echo "$p"; return;; esac
    p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' '); [ -z "$p" ] || [ "$p" = 1 ] && break
  done
  echo "$PPID"
}
LOCK="$PROJECT_GITDIR/agent_main.lock"; ME=$(agent_pid); NOW=$(date '+%Y-%m-%d %H:%M')
role=main
if [ -n "${AGENT_ROLE:-}" ]; then role=spawned
elif [ -f "$LOCK" ]; then
  read -r lpid lsince < "$LOCK" || true
  if [ "$lpid" = "$ME" ]; then role=main
  elif kill -0 "$lpid" 2>/dev/null; then role=second
  else role=takeover; fi
fi

# ---- CAP: the whole output, always, at or under this many bytes. The state
# block (the unbounded one) gets whatever the fixed parts below leave. ----
CAP=2000

# Replace, never append: this worktree's own human-direct line in
# agent_worktree.txt. That file is what the main manager reads before every
# dispatch (W9); a restarted session, or the hook firing twice, must not
# pile up copies of the same line. Match on the path (field 1) and only on
# the human-direct rows (field 2), so a normal registered line for the same
# path, or any line belonging to another path, keeps its own entry. Written
# the way agent-file.sh does it: build the new text next to the target, then
# mv it over, so a half-written file is never left behind.
announce_human_direct() {
  local wt tmp
  wt="$PROJECT_ROOT/agent_worktree.txt"
  tmp="$wt.tmp"
  touch "$wt"
  awk -v p="$PROJECT_CWD" -F' \\| ' \
    '!($1 == p && $2 == "task manager, human-direct")' "$wt" > "$tmp"
  printf '%s\n' "$PROJECT_CWD | task manager, human-direct | task: (ask the human) | since $NOW" >> "$tmp"
  mv "$tmp" "$wt"
}

print_role_and_project() {
  case $role in
    spawned)  echo "ROLE: $AGENT_ROLE (spawned by an agent, not human-direct). Main manager: pid $(cut -d' ' -f1 "$LOCK" 2>/dev/null || echo ?). Report to it with SendMessage.";;
    main)     echo "$ME $NOW" > "$LOCK"; echo "ROLE: main manager (lock: pid $ME)";;
    takeover) echo "$ME $NOW" > "$LOCK"; echo "ROLE: main manager. Previous main manager (pid $lpid, since $lsince) is dead. Run recovery (S7).";;
    second)
      echo "ROLE: task manager, human-direct (W10). Main manager already running: pid $lpid, since $lsince."
      announce_human_direct
      echo "Announced: line added to agent_worktree.txt. Send the main manager a direct message too if Orca is available."
      echo "Will change files? Open your own worktree first (W7). Human says finish -> report done + click path to the main manager."
      echo "Reach the main manager: ListAgents -> the earlier peer session of this repo -> SendMessage to that name. Reply to the from name.";;
  esac
  echo "PROJECT: $PROJECT_ROOT | PLUGIN: $PLUGIN_ROOT"
}

# ---- small helpers for the pointer-shaped, byte-budgeted output ----
count_lines() {
  if [ -f "$1" ]; then
    n=$(grep -c . "$1" 2>/dev/null)
    printf '%s' "${n:-0}"
  else
    printf '%s' 0
  fi
}

# byte length of $1, plus a trailing newline (what `printf '%s\n' "$1"` costs)
line_bytes() { printf '%s\n' "$1" | wc -c | tr -d ' '; }
# byte length of $1 exactly as given (no newline added)
text_bytes() { printf '%s' "$1" | wc -c | tr -d ' '; }

print_compact_lines() {
  local CF cn
  CF="$PROJECT_GITDIR/agent_compact_$SID"
  cn=$(( $(cat "$CF" 2>/dev/null || echo 0) + 1 ))
  echo "$cn" > "$CF"
  echo "COMPACTED $cn time(s) this session. Continue from agent_state.txt, not from memory (S8)."
  [ "$cn" -ge 2 ] && echo "LIMIT: compacted $cn times. Write agent_state.txt, end this session, restart from the file (S8, S2)."
  return 0
}

print_normal_lines() {
  resources_read
  resources_line "$max_usage_percent"
  resources_ok "$max_usage_percent" || echo "Do not start agents or heavy processes. Re-run this script until OK."
  echo "LANGUAGE: ${language:-en}. Talk to the human in this language. Code, file names and rule text stay English."
  local name cn
  for name in agent_todo.txt agent_completed.txt agent_ideas.txt agent_worktree.txt; do
    cn=$(count_lines "$PROJECT_ROOT/$name")
    echo "$name: $cn lines"
    if [ "$name" = agent_worktree.txt ] && [ "$cn" -gt 0 ]; then
      sed 's/^/  /' "$PROJECT_ROOT/$name"
    fi
  done
  return 0
}

print_monitor_block() {
  local f cn
  f="$PROJECT_ROOT/agent_monitor.txt"
  if [ -f "$f" ]; then
    cn=$(count_lines "$f")
    if [ "$cn" -gt 0 ]; then
      echo "agent_monitor.txt: $cn lines"
      sed 's/^/  /' "$f"
    fi
  fi
  return 0
}

# print_state_block <budget-in-bytes>
# Header always shows the real total. Content lines are added while the
# running byte total stays inside the budget, never more than 30 lines.
# A line too long to fit is cut to fit. Anything left out, for any reason,
# gets "  (truncated, read the file)" as the last line of the block.
print_state_block() {
  local budget f sn header header_bytes marker marker_bytes remaining
  local total_phys idx line indented ibytes cut_len truncated
  budget=$1
  [ "$budget" -lt 0 ] && budget=0
  f="$STATE_DIR/agent_state.txt"
  [ -f "$f" ] || return 0
  sn=$(count_lines "$f")
  [ "$sn" -gt 0 ] || return 0

  header="agent_state.txt: $sn lines"
  marker="  (truncated, read the file)"
  header_bytes=$(line_bytes "$header")
  marker_bytes=$(line_bytes "$marker")

  printf '%s\n' "$header"

  remaining=$(( budget - header_bytes - marker_bytes ))
  [ "$remaining" -lt 0 ] && remaining=0

  total_phys=$(awk 'END{print NR}' "$f")
  [ -z "$total_phys" ] && total_phys=0

  idx=0
  truncated=0
  while IFS= read -r line || [ -n "$line" ]; do
    idx=$((idx+1))
    if [ "$idx" -gt 30 ]; then
      truncated=1
      break
    fi
    indented="  $line"
    ibytes=$(line_bytes "$indented")
    if [ "$ibytes" -le "$remaining" ]; then
      printf '%s\n' "$indented"
      remaining=$(( remaining - ibytes ))
    else
      cut_len=$(( remaining - 1 ))
      if [ "$cut_len" -gt 0 ]; then
        printf '%s' "$indented" | head -c "$cut_len"
        printf '\n'
      fi
      truncated=1
      break
    fi
  done < "$f"

  if [ "$truncated" -eq 0 ] && [ "$idx" -lt "$total_phys" ]; then
    truncated=1
  fi

  [ "$truncated" -eq 1 ] && printf '%s\n' "$marker"
  return 0
}

ROLE_TEXT=$(print_role_and_project; printf 'X'); ROLE_TEXT=${ROLE_TEXT%X}

# ---- compaction: short, no resources, no counts, no quiz. Same byte cap. ----
if [ "$SRC" = compact ] && [ -n "$SID" ]; then
  COMPACT_TEXT=$(print_compact_lines; printf 'X'); COMPACT_TEXT=${COMPACT_TEXT%X}
  RULES_LINE="RULES: read $PLUGIN_ROOT/PRINCIPLES.md now (S8)."
  fixed=$(( $(text_bytes "$SETUP_TEXT") + $(text_bytes "$ROLE_TEXT") + $(text_bytes "$COMPACT_TEXT") + $(line_bytes "$RULES_LINE") ))
  budget=$(( CAP - fixed )); [ "$budget" -lt 0 ] && budget=0
  printf '%s' "$ROLE_TEXT"
  printf '%s' "$COMPACT_TEXT"
  print_state_block "$budget"
  printf '%s\n' "$RULES_LINE"
  exit 0
fi

# ---- normal start ----
NORMAL_TEXT=$(print_normal_lines; printf 'X'); NORMAL_TEXT=${NORMAL_TEXT%X}
MON_TEXT=$(print_monitor_block; printf 'X'); MON_TEXT=${MON_TEXT%X}
RULES_LINE="RULES: read $PLUGIN_ROOT/PRINCIPLES.md now (S8)."
QUIZ_LINE="QUIZ: run $PLUGIN_ROOT/bin/agent-start.sh --quiz, then --answer. No work until PASS."

# ---- auto resume: real startup, main manager (new or taken over), never
# spawned, never human-direct (second), and only when auto_resume=yes. A
# failing resume must never break the hook. ----
RESUME_TEXT=""
if [ "$SRC" = startup ] && { [ "$role" = main ] || [ "$role" = takeover ]; } \
   && [ "$auto_resume" = yes ]; then
  resume_out=$("$PLUGIN_ROOT/bin/agent-resume.sh" 2>&1) || true
  header="=== auto resume ==="
  other_fixed=$(( $(text_bytes "$SETUP_TEXT") + $(text_bytes "$ROLE_TEXT") + $(text_bytes "$NORMAL_TEXT") + $(text_bytes "$MON_TEXT") \
                 + $(line_bytes "$RULES_LINE") + $(line_bytes "$QUIZ_LINE") ))
  candidate_bytes=$(( $(line_bytes "$header") + $(text_bytes "$resume_out") + 1 ))
  if [ $(( other_fixed + candidate_bytes )) -gt "$CAP" ]; then
    resume_out=$(printf '%s\n' "$resume_out" | head -n 6)
    resume_out="${resume_out}
(more, run agent-resume.sh)"
  fi
  RESUME_TEXT="$header
$resume_out
"
fi

fixed=$(( $(text_bytes "$SETUP_TEXT") + $(text_bytes "$ROLE_TEXT") + $(text_bytes "$NORMAL_TEXT") + $(text_bytes "$MON_TEXT") \
        + $(text_bytes "$RESUME_TEXT") + $(line_bytes "$RULES_LINE") + $(line_bytes "$QUIZ_LINE") ))
budget=$(( CAP - fixed )); [ "$budget" -lt 0 ] && budget=0

printf '%s' "$ROLE_TEXT"
printf '%s' "$NORMAL_TEXT"
printf '%s' "$MON_TEXT"
print_state_block "$budget"
printf '%s' "$RESUME_TEXT"
printf '%s\n' "$RULES_LINE"
printf '%s\n' "$QUIZ_LINE"
