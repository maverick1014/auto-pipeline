#!/usr/bin/env bash
# agent-start.sh — every agent runs this first, before any work.
#
#   ./agent-start.sh                         resource check + PRINCIPLES + open tasks + quiz
#   ./agent-start.sh --answer "1A 2D ... 16B"   grade your quiz answers
#
# Rule: no work until the quiz says PASS.

set -u
cd "$(dirname "$0")"

# ---- config (S1 writes this file; S4/S5/S6 values) ----
[ -f agent.conf ] && . ./agent.conf
: "${max_usage_percent:=80}"

# ---- quiz answer key (salted hashes, one per question) ----
SALT="auto-pipeline-quiz-v1"
KEY=( _ ff689d761d10c13d 38ebe4aa1afa125b 5b09070227aba9ed 8fad5dd001704a23 526a99cc5399c609 47db38d6283a87c2 2c0aa4aa4d1dc695 d20e713f26917f2c 810aeef60af42d9e 99878dad4233c435 ffa4bdb3449e9897 ff9345bd5e5cfefa 18defa25be09413b 52fcf5e8a49617f0 496f90a01d738ae5 ba6a4831a815a230 )
RULE=( _ W1 R6 H1 W2 W3 W4 W5 S4 S5 H3 R5 R2 R3 H4 S7 R1 )
N=16

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
  [ -z "${2:-}" ] && { echo 'usage: ./agent-start.sh --answer "1A 2D ... 16B"'; exit 2; }
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
echo "=== todo.txt (open tasks) ==="; [ -s todo.txt ] && cat todo.txt || echo "(none)"
echo
echo "=== ideas.txt ==="; echo "$( [ -f ideas.txt ] && grep -c . ideas.txt || echo 0 ) ideas waiting for human review"
echo
cat <<'QUIZ'
=== QUIZ — answer all 16 before any work ===
Reply by running:   ./agent-start.sh --answer "1A 2B 3C ... 16D"
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
  D. Append it to ideas.txt

Q3. You have three questions not related to the current task.
  A. Ask them now, one by one
  B. Drop them
  C. Park them; show them at the end in one table
  D. Append them to ideas.txt

Q4. Task: build a settings page. Your first step:
  A. Write the component
  B. Make a clickable mock and get a yes
  C. Write a failing test
  D. Ask the human for a design

Q5. Task: add a function. Order of work:
  A. Code, then test
  B. Code only; tests later
  C. Ask if tests are needed
  D. Failing test, then code, then pass

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
  A. Move the line to completed.txt
  B. Delete the line from todo.txt
  C. Mark it [x] in todo.txt
  D. Add it to a changelog

Q12. You need the DB password from .secrets/.
  A. Copy it to .env
  B. Print it to confirm
  C. Read it, use it, never print it
  D. Commit it encrypted

Q13. You want to write ARCHITECTURE.md to explain the design.
  A. Write it
  B. Write it in README.md
  C. Put it in ideas.txt
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
  D. Write it in todo.txt

Q16. Fast lane task. The human already checked the result on screen. Before merge you:
  A. Run the full suite
  B. Write a failing test first
  C. Run the minimal test
  D. Nothing; the human already verified
QUIZ
