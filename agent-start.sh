#!/usr/bin/env bash
# agent-start.sh — every agent runs this first, before any work.
#
#   ./agent-start.sh                         resource check + PRINCIPLES + open tasks + quiz
#   ./agent-start.sh --answer "1A 2D ... 27B"   grade your quiz answers
#
# Rule: no work until the quiz says PASS.

set -u
cd "$(dirname "$0")"

# ---- config (S1 writes this file; S4/S5/S6 values) ----
[ -f agent.conf ] && . ./agent.conf
: "${max_usage_percent:=80}"

# ---- quiz answer key (salted hashes, one per question) ----
SALT="auto-pipeline-quiz-v1"
KEY=( _ ff689d761d10c13d 38ebe4aa1afa125b 5b09070227aba9ed 8fad5dd001704a23 526a99cc5399c609 47db38d6283a87c2 2c0aa4aa4d1dc695 d20e713f26917f2c 810aeef60af42d9e 99878dad4233c435 ffa4bdb3449e9897 ff9345bd5e5cfefa 18defa25be09413b 52fcf5e8a49617f0 496f90a01d738ae5 ba6a4831a815a230 d956db8d1ed42790 72241f6e3363d877 64d26f41c9262571 8f6fba4ede3f932c 84bdc6be36e36afe 23f134bb4de59b4e 7fb8bf29915b93ba 4b57e10438403e80 a4dfa8b418c5d6de 5bc49497d74f49dc 96ebc45b039cdeb7 )
RULE=( _ W1 R6 H1 W2 W3 W4 W5 S4 S5 H3 R5 R2 R3 H4 S7 R1 W7 W6 W8 W5 W7 W9 W9 W9 R7 W10 W10 )
N=27

sha() { if command -v shasum >/dev/null; then shasum -a 256; else sha256sum; fi; }
h()   { printf '%s' "$1" | sha | cut -c1-16; }

# ---- resources ----
ram_used() {
  if [ "$(uname)" = Darwin ]; then
    f=$(memory_pressure 2>/dev/null | awk -F': ' '/free percentage/{gsub("%","",$2);print $2}')
    [ -n "$f" ] && echo $((100 - f)) || echo -1
  else
    awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{if(t)printf "%d",(t-a)*100/t; else print -1}' /proc/meminfo
  fi
}
cpu_used() {
  if [ "$(uname)" = Darwin ]; then
    i=$(top -l 2 -n 0 -s 1 2>/dev/null | awk '/CPU usage/{idle=$7}END{gsub("%","",idle);print idle}')
    [ -n "$i" ] && printf '%d\n' "${i%.*}" | awk '{print 100-$1}' || echo -1
  else
    read -r _ a b c d _ < /proc/stat; sleep 1; read -r _ a2 b2 c2 d2 _ < /proc/stat
    t=$(( (a2+b2+c2+d2)-(a+b+c+d) )); id=$(( d2-d ))
    [ "$t" -gt 0 ] && echo $(( (t-id)*100/t )) || echo -1
  fi
}

# ---- grade ----
if [ "${1:-}" = "--answer" ]; then
  [ -z "${2:-}" ] && { echo 'usage: ./agent-start.sh --answer "1A 2D ... 27B"'; exit 2; }
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
GITDIR=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || git rev-parse --git-common-dir 2>/dev/null || echo .git)
MAINREPO=$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2; exit}'); : "${MAINREPO:=$PWD}"
LOCK="$GITDIR/agent_main.lock"; ME=$(agent_pid); NOW=$(date '+%Y-%m-%d %H:%M')
role=main
if [ -n "${AGENT_ROLE:-}" ]; then role=spawned
elif [ -f "$LOCK" ]; then
  read -r lpid lsince < "$LOCK" || true
  if [ "$lpid" = "$ME" ]; then role=main
  elif kill -0 "$lpid" 2>/dev/null; then role=second
  else role=takeover; fi
fi
case $role in
  spawned)  echo "ROLE: $AGENT_ROLE (spawned by an agent, not human-direct). Main manager: pid $(cut -d' ' -f1 "$LOCK" 2>/dev/null || echo ?). Report to it with SendMessage.";;
  main)     echo "$ME $NOW" > "$LOCK"; echo "ROLE: main manager (lock: pid $ME)";;
  takeover) echo "$ME $NOW" > "$LOCK"; echo "ROLE: main manager. Previous main manager (pid $lpid, since $lsince) is dead. Run recovery (S7).";;
  second)
    echo "ROLE: task manager, human-direct (W10). Main manager already running: pid $lpid, since $lsince."
    echo "$PWD | task manager, human-direct | task: (ask the human) | since $NOW" >> "$MAINREPO/agent_worktree.txt"
    echo "Announced: line added to agent_worktree.txt. Send the main manager a direct message too if Orca is available."
    echo "Will change files? Open your own worktree first (W7). Human says finish -> report done + click path to the main manager."
    echo "Reach the main manager: ListAgents -> the earlier peer session of this repo -> SendMessage to that name. Reply to the from name.";;
esac
echo

# ---- startup ----
r=$(ram_used); c=$(cpu_used)
if [ "$r" -ge "$max_usage_percent" ] || [ "$c" -ge "$max_usage_percent" ]; then
  echo "RESOURCES: RAM ${r}% CPU ${c}% (cap ${max_usage_percent}%) -> OVER CAP"
  echo "Do not start agents or heavy processes. Re-run this script until OK."
else
  echo "RESOURCES: RAM ${r}% CPU ${c}% (cap ${max_usage_percent}%) -> OK"
fi
echo
echo "=== PRINCIPLES.md ==="; cat PRINCIPLES.md
echo
echo "=== agent_todo.txt (open tasks) ==="; [ -s agent_todo.txt ] && cat agent_todo.txt || echo "(none)"
echo
echo "=== agent_worktree.txt (live worktrees) ==="; [ -s agent_worktree.txt ] && cat agent_worktree.txt || echo "(none)"
echo
echo "=== agent_ideas.txt ==="; echo "$( [ -f agent_ideas.txt ] && grep -c . agent_ideas.txt || echo 0 ) ideas waiting for human review"
echo
cat <<'QUIZ'
=== QUIZ — answer all 27 before any work ===
Reply by running:   ./agent-start.sh --answer "1A 2B 3C ... 27D"
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
QUIZ
