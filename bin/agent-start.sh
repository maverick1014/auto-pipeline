#!/usr/bin/env bash
# agent-start.sh — every agent runs this first, before any work.
#
#   ./agent-start.sh                          resource check + pointers + open tasks
#   ./agent-start.sh --rules                  the rules block (the second SessionStart entry): the core,
#                                             the output rules, the PATHS line, the role's READ NOW line
#   ./agent-start.sh --quiz [--role main|task|second|all]
#                                             print the 36 quiz questions (all), or the role's set (no --role:
#                                             the role of this session)
#   ./agent-start.sh --answer "1A 2D ... 36D" [--role ...]
#                                             grade your quiz answers (only the role's questions; a wrong one
#                                             names the file to re-read)
#   ./agent-start.sh --take-over              this session becomes the main manager
#                                             (only when the human asks; the old one is closed)
#   ./agent-start.sh --clean ["carry line" ...]
#                                             the main manager, after a whole-repo close case: archive
#                                             agent_state.txt, write a fresh one, keep the seat; then /clear
#   ./agent-start.sh --release                the main manager frees its seat (the rare other choice,
#                                             typed by the human); this session is closed
#
# Rule: no work until the quiz says PASS.
#
# A PASS with a session id marks it (agent_quiz_<session id> in the git dir),
# so a later run in that same session skips straight past the quiz line.
#
# With a session_id on stdin, the real work runs once per SessionStart event
# (two hooks, repo-packed plus user-scope, can fire for the same session):
# see the once-per-session dedupe below (AGENT_START_DEDUPE_SEC, default 60s).
#
# The hook prints the start part only (Claude Code caps a hook's stdout at 10,000
# characters); the rules block is the second SessionStart entry, --rules. Run by hand
# (no hook JSON on stdin) the start part is followed by the rules block.

set -u
. "$(dirname "$0")/agent-roots.sh"

# ---- quiz answer key (salted hashes, one per question) ----
SALT="auto-pipeline-quiz-v1"
KEY=( _ ff689d761d10c13d 38ebe4aa1afa125b 5b09070227aba9ed 8fad5dd001704a23 526a99cc5399c609 b75587e9915ec885 b10039ac08596652 6e172188c9c4bc39 5e1a8ca54c3fbadd 13127809c0aa4e07 2de03a63345b0488 d019670ac24fe392 1a6951e83e3e46bb 52fcf5e8a49617f0 d7dd4d5626dfebb7 14d3ea7536a00bbf d956db8d1ed42790 72241f6e3363d877 c20dbe1e5d7e0c3a f4c5ea8cff8e3805 1abb73a3e6683277 ed3aa1e779d86517 7fb8bf29915b93ba 53f2f80016081d7b 452e097c150557a7 86748978724ff86c 8ceef70be9e82efe 0a9317bb53ca4942 5beab162ea6db1e0 f9d86ca36f2238ad 6ef895678e4d73f6 60a1877ffe0c9ecf fc755642e7b2d547 81b9e6e9fb8fe2c5 a06bbc5adaee446e 23168b3ea65a8215 )
RULE=( _ W1 R6 H1 W2 W4 W12 S3 H3 R5 R2 R3 H3 R1 W7 W6 W7 W9 S1 W10 S8 S8 H1 H3 W8 R8 W17 R8 R8 R8 R8 R8 R8 P1 R8 W9 P1 )
N=36

sha() { if command -v shasum >/dev/null; then shasum -a 256; else sha256sum; fi; }
h()   { printf '%s' "$1" | sha | cut -c1-16; }

# ---- the seat: the lock line and the closed list (files: see agent-roots.sh) ----

# lock_write <since>: the whole lock line, "<pid> <date> <time> <sid> <terminal>".
# sid: the hook's stdin session_id, else $CLAUDE_CODE_SESSION_ID, else "-".
lock_write() {
  local sid term tmp
  sid="${SID:-${CLAUDE_CODE_SESSION_ID:-}}"; sid=${sid//[[:space:]]/_}
  term="${ORCA_TERMINAL_HANDLE:-}"; term=${term//[[:space:]]/_}
  tmp="$LOCK.tmp.$$"
  printf '%s %s %s %s\n' "$ME" "$1" "${sid:--}" "${term:--}" > "$tmp" && mv "$tmp" "$LOCK"
}

# closed_update <add-pid|-> <drop-pid|-> <why>: rewrite the closed list. Dead
# pids go; <drop-pid> goes; <add-pid> is added (why, now). A pid's told-once
# mark (agent-close-case.sh) goes with its line, so it is told again next time.
closed_update() {
  local tmp p rest t
  tmp="$CLOSED.tmp.$$"
  {
    if [ -f "$CLOSED" ]; then
      while read -r p rest; do
        [ -n "$p" ] || continue
        [ "$p" = "$1" ] || [ "$p" = "$2" ] && continue
        kill -0 "$p" 2>/dev/null && printf '%s %s\n' "$p" "$rest"
      done < "$CLOSED"
    fi
    [ "$1" = - ] || printf '%s %s %s\n' "$1" "$3" "$NOW"
  } > "$tmp"
  if [ -s "$tmp" ]; then mv "$tmp" "$CLOSED"; else rm -f "$tmp" "$CLOSED"; fi
  for t in "$PROJECT_GITDIR"/agent_main.told_*; do
    [ -e "$t" ] || continue
    p=${t##*_}
    if [ "$p" = "$1" ] || [ "$p" = "$2" ] || ! kill -0 "$p" 2>/dev/null; then rm -f "$t"; fi
  done
  return 0
}

# drop_human_direct: this worktree's own human-direct line leaves agent_worktree.txt.
drop_human_direct() {
  local wt tmp
  wt="$PROJECT_ROOT/agent_worktree.txt"; tmp="$wt.tmp"
  [ -f "$wt" ] || return 0
  awk -v p="$PROJECT_CWD" -F' \\| ' '!($1 == p && $2 == "task manager, human-direct")' "$wt" > "$tmp" && mv "$tmp" "$wt"
  keep_worktree_copy
  return 0
}

# clean_session ["<carry line>" ...]: --clean (W13). The main manager archives its
# agent_state.txt, writes a fresh short one and is told how to clear its own context.
# The seat stays: the lock and the closed list are never touched. Returns the exit code.
clean_session() {
  local mp line name stamp arch day todo todo_n a n k kind handle excl tmp
  local pat pats
  pats=('agent_state.[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].txt' \
        'agent_state.trim-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].txt')
  # only the lock holder; a spawned agent never is, whatever the lock names
  if [ -n "${AGENT_ROLE:-}" ]; then
    echo "REFUSED: $AGENT_ROLE is a spawned agent, never the main manager.${lpid:+ The lock holder is pid $lpid.}"; return 1
  elif [ ! -f "$LOCK" ] || [ "$lpid" != "$ME" ]; then
    if [ -f "$LOCK" ] && [ -n "$lpid" ]; then
      echo "REFUSED: only the main manager cleans its session. The lock holder is pid $lpid, this session is pid $ME."
    else
      echo "REFUSED: no lock, no main manager to clean (this session is pid $ME)."
    fi
    return 1
  fi
  # the gate, checked not guessed: what is left running (crons: a script cannot see them)
  n=0
  if [ -f "$PROJECT_ROOT/agent_worktree.txt" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      case "$line" in *[![:space:]]*) ;; *) continue;; esac
      echo "LEFT RUNNING: worktree $line -> close its pane, remove the worktree, $PLUGIN_ROOT/bin/agent-file.sh worktree rm \"${line%% | *}\""; n=1
    done < "$PROJECT_ROOT/agent_worktree.txt"
  fi
  [ "$n" = 0 ] || { echo "REFUSED: stop these first, then run --clean again. Nothing changed."; return 1; }
  # the open tasks: the first field of each agent_todo.txt line
  todo=""; todo_n=0
  if [ -f "$PROJECT_ROOT/agent_todo.txt" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      case "$line" in *[![:space:]]*) ;; *) continue;; esac
      name=${line%% | *}; todo="${todo:+$todo, }$name"; todo_n=$((todo_n+1))
    done < "$PROJECT_ROOT/agent_todo.txt"
  fi
  # the archive, next to the state, same bytes; a taken name waits for the next second
  arch=none; day=${NOW%% *}
  if [ -f "$STATE_DIR/agent_state.txt" ]; then
    stamp=$(date '+%Y-%m-%d-%H%M%S')
    while [ -e "$STATE_DIR/agent_state.$stamp.txt" ]; do sleep 1; stamp=$(date '+%Y-%m-%d-%H%M%S'); done
    arch="agent_state.$stamp.txt"; day=${stamp:0:10}
    mv "$STATE_DIR/agent_state.txt" "$STATE_DIR/$arch" || { echo "REFUSED: could not archive agent_state.txt. Nothing changed."; return 1; }
  fi
  # git-ignored without touching a tracked file: the repo's own exclude list (no git: skipped)
  if git -C "$STATE_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    excl="$PROJECT_GITDIR/info/exclude"; mkdir -p "$PROJECT_GITDIR/info" 2>/dev/null
    grep -qxF 'agent_state.*.txt' "$excl" 2>/dev/null || {
      [ -s "$excl" ] && [ -n "$(tail -c1 "$excl")" ] && echo
      echo 'agent_state.*.txt'; } >> "$excl"
  fi
  # the newest 5 of each kind stay (names sort by date): the copies and the trim day files
  for pat in "${pats[@]}"; do
    n=0; for a in "$STATE_DIR"/$pat; do [ -e "$a" ] && n=$((n+1)); done
    k=$((n-5)); for a in "$STATE_DIR"/$pat; do [ "$k" -gt 0 ] || break; rm -f "$a"; k=$((k-1)); done
  done
  # the fresh state
  tmp="$STATE_DIR/agent_state.txt.tmp.$$"
  {
    printf 'ROLE: main manager of "%s" (lock: pid %s). Same seat, clean session.\n' "$REPO" "$ME"
    printf 'DATE: %s\n' "$NOW"
    printf 'PREVIOUS: case closed %s, archive %s\n' "$day" "$arch"
    printf 'TODO open (%s): %s\n' "$todo_n" "${todo:-none}"
    if [ $# -eq 0 ]; then echo "CARRY: none"; else for a in "$@"; do printf 'CARRY: %s\n' "${a//$'\n'/ }"; done; fi
    echo
  } > "$tmp" && mv "$tmp" "$STATE_DIR/agent_state.txt" || { rm -f "$tmp"; echo "REFUSED: could not write agent_state.txt ($STATE_DIR)."; return 1; }
  # how this session clears itself: orca with a terminal handle -> the exact line, else the human
  kind=$(. "$PLUGIN_ROOT/bin/agent-runtime.sh" && runtime_kind)
  handle="${ORCA_TERMINAL_HANDLE:-$lterm}"; handle=${handle//[[:space:]]/_}
  echo "ARCHIVE: $arch (the 5 newest stay). Fresh agent_state.txt written. The lock is untouched: you stay the main manager."
  echo "CHECK: run CronList now, it must show none; delete any cron it lists."
  if [ "$kind" = orca ] && [ -n "$handle" ]; then
    echo "NEXT, your last action, nothing after it: orca terminal send --terminal $handle --text \"/clear\" --enter"
  else
    echo "NEXT: ask the human to type /clear (one word). Nothing after it from you."
  fi
  echo "The session is not cleared (nothing was sent, or it did nothing)? Then the human types /clear."
  return 0
}

# ---- --take-over / --release / --clean: the seat moves by hand, only when the human
# asks (W10, W13); --clean keeps it. Needs the roots, prints no start output, reads no stdin. ----
if [ "${1:-}" = "--take-over" ] || [ "${1:-}" = "--release" ] || [ "${1:-}" = "--clean" ]; then
  roots_read
  if ! repo_set_up; then
    echo "auto-pipeline: not set up in this repo, run /auto-pipeline:init to enable"; exit 1
  fi
  mkdir -p "$PROJECT_GITDIR" 2>/dev/null || true
  role_read; NOW=$(date '+%Y-%m-%d %H:%M'); REPO=$(basename "$PROJECT_ROOT")
  if [ "$1" = "--take-over" ]; then
    if [ "$role" = spawned ]; then
      echo "REFUSED: $AGENT_ROLE is a spawned agent, never the main manager. Only a human-direct session takes over."; exit 1
    fi
    if [ -f "$LOCK" ] && [ "$lpid" = "$ME" ]; then
      # The seat stays. An old lock line (no sid, no terminal, or a stale sid) takes this
      # session's own, so the city can match the lock to its session; what this session
      # does not know, the lock keeps. Nothing new -> the lock is left untouched.
      nsid="${CLAUDE_CODE_SESSION_ID:-}"; nsid=${nsid//[[:space:]]/_}; [ -n "$nsid" ] || nsid="$lsid"
      nterm="${ORCA_TERMINAL_HANDLE:-}"; nterm=${nterm//[[:space:]]/_}; [ -n "$nterm" ] || nterm="$lterm"
      if [ "$nsid" != "$lsid" ] || [ "$nterm" != "$lterm" ]; then
        tmp="$LOCK.tmp.$$"
        if printf '%s %s %s %s\n' "$ME" "${lsince:-$NOW}" "${nsid:--}" "${nterm:--}" > "$tmp" && mv "$tmp" "$LOCK"; then
          echo "Already the main manager (lock: pid $ME). Lock line updated: session id ${nsid:--}, terminal ${nterm:--}."
          exit 0
        fi
        rm -f "$tmp"; echo "REFUSED: could not rewrite the lock line ($LOCK)."; exit 1
      fi
      echo "Already the main manager (lock: pid $ME). Nothing changed."; exit 0
    fi
    lock_write "$NOW"
    if [ -n "$lpid" ] && [ "$lpid" != "$ME" ] && pid_alive "$lpid"; then
      closed_update "$lpid" "$ME" replaced
    else
      closed_update - "$ME" replaced; lpid=""
    fi
    drop_human_direct
    echo "ROLE: main manager (lock: pid $ME). Address: /rename $REPO Manager or claude --name"
    [ -n "$lpid" ] && echo "Took over from pid $lpid: it is closed now and is told once."
    exit 0
  fi
  if [ "$1" = "--clean" ]; then shift; clean_session "$@"; exit $?; fi
  # --release: only the lock holder
  if [ ! -f "$LOCK" ] || [ "$lpid" != "$ME" ]; then
    if [ -f "$LOCK" ] && [ -n "$lpid" ]; then
      echo "REFUSED: only the main manager releases. The lock holder is pid $lpid, this session is pid $ME."
    else
      echo "REFUSED: no lock, nothing to release (this session is pid $ME)."
    fi
    exit 1
  fi
  rm -f "$LOCK"
  closed_update "$ME" - released
  echo "RELEASED: the main manager seat of \"$REPO\" is free. The next session the human opens becomes the main manager."
  echo "This session is closed: start nothing new. Take over again only when the human asks; the human types this line in this session, never run it yourself:"
  echo "! $PLUGIN_ROOT/bin/agent-start.sh --take-over"
  exit 0
fi

# ---- the quiz per role (md-slim-principles B 8). The 36 questions, their order, the
# answer key and the SALT do not change. Each question carries the file(s) that hold
# its rule; a role is asked the questions whose file is PRINCIPLES.md or on its
# reading list. ----
QFILES=( _
  "PRINCIPLES.md" "PRINCIPLES.md rules/files.md" "rules/human.md" "rules/ui.md" "rules/tests.md"
  "rules/cross-repo.md rules/approval.md" "rules/resources.md" "PRINCIPLES.md rules/human.md" "rules/files.md" "PRINCIPLES.md"
  "rules/files.md" "rules/human.md" "PRINCIPLES.md" "rules/worktrees.md" "PRINCIPLES.md rules/roles.md"
  "rules/worktrees.md" "rules/routing.md" "rules/setup.md rules/roles.md" "rules/roles.md" "PRINCIPLES.md"
  "rules/context.md" "rules/human.md" "PRINCIPLES.md rules/human.md" "rules/worktrees.md" "rules/branches.md"
  "PRINCIPLES.md" "rules/checks.md" "rules/branches.md" "rules/approval.md" "rules/approval.md"
  "rules/approval.md" "rules/approval.md" "PRINCIPLES.md" "rules/approval.md" "rules/routing.md"
  "PRINCIPLES.md" )
MAIN_READS="rules/human.md rules/routing.md rules/approval.md rules/checks.md rules/branches.md rules/worktrees.md rules/watch.md rules/files.md"
TASK_READS="rules/tests.md rules/checks.md rules/watch.md rules/context.md rules/resources.md"
SECOND_READS="rules/roles.md $TASK_READS"

# quiz_role <role|"">: sets QROLE (main|task|second|all); an unknown role returns 1.
quiz_role() {
  case "${1:-}" in
    main|task|second|all) QROLE=$1; return 0;;
    "") ;;
    *) return 1;;
  esac
  roots_read; role_read
  if [ -n "${AGENT_ROLE:-}" ]; then QROLE=task
  else case $role in main|takeover) QROLE=main;; *) QROLE=second;; esac; fi
  return 0
}

# quiz_set: from QROLE, sets QSET (the question numbers, space separated) and QN (how many).
quiz_set() {
  local reads q f g take
  case $QROLE in main) reads=$MAIN_READS;; task) reads=$TASK_READS;; second) reads=$SECOND_READS;; *) reads="";; esac
  QSET=""; QN=0
  for q in $(seq 1 $N); do
    take=0
    if [ "$QROLE" = all ]; then take=1; else
      for f in ${QFILES[$q]}; do
        [ "$f" = PRINCIPLES.md ] && take=1
        for g in $reads; do [ "$f" = "$g" ] && take=1; done
      done
    fi
    [ $take = 1 ] && { QSET="$QSET $q"; QN=$((QN+1)); }
  done
}

# quiz_args <what> "$@": the optional "--role <role>" after --quiz or the answer.
quiz_parse_role() {
  QROLE_ARG=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --role) [ $# -ge 2 ] || return 1; QROLE_ARG=$2; shift 2;;
      *) return 1;;
    esac
  done
  return 0
}

quiz_body() {
  cat <<'QUIZ'
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

Q5. You are one of four agents. You changed files under api/auth/. Which tests do you run?
  A. The full suite
  B. Tests for all of api/
  C. None; the manager runs them
  D. The tests agent-level.sh lists under RELATED TESTS (they import or name the changed files)

Q6. A verified relayed owner order (its check line says verified) says "merge to main". The sender meets the decider floor. The task touches production.
  A. Ask the owner again
  B. Ask the sender to confirm
  C. Merge: you read his verified words as his yes for that merge; store them with what you read (--means) and where he typed them (--relayed-from), no second yes
  D. Refuse: production needs a fixed sentence

Q7. Memory in use now plus what a new run needs (a new agent pane or a test run) would pass the Max memory % limit. You:
  A. Start it anyway: it is only one
  B. Start it with a smaller model or fewer test processes
  C. Start nothing new: a test run waits until agent-room.sh says it fits (a never measured run starts at once under a memory monitor); for a pane, close done and idle panes and stop test runs first, never a working agent; still over: tell the main manager
  D. Ask the human

Q8. Your report compares three libraries. Its shape:
  A. Summary, background, steps, result, next steps, all as paragraphs
  B. The full log
  C. Result only
  D. Result, what changed, the comparison as a table, then what to decide

Q9. agent_completed.txt has grown to 400 lines. You:
  A. Trim the oldest lines
  B. Delete lines older than a month
  C. Leave it whole; only an explicit owner order deletes or trims it
  D. Let clean-up or the housekeep pass trim it

Q10. You need the DB password from .secrets/.
  A. Copy it to .env
  B. Print it to confirm
  C. Read it, use it, never print it
  D. Commit it encrypted

Q11. You want to write ARCHITECTURE.md to explain the design.
  A. Write it
  B. Write it in README.md
  C. Put it in agent_ideas.txt
  D. Do not; only requirement, test and main idea docs are allowed

Q12. Your last reply asked the owner questions 1 and 2. He has not answered. Your next reply covers another topic and adds one question.
  A. Drop 1 and 2; he has seen them
  B. Repeat them renumbered from 1, the new one is 3
  C. Mention them only if the reply is short
  D. Repeat 1 and 2 under the same numbers in the decide section, the new one is 3

Q13. A small logic task (one function, about 30 minutes) needs a new test. Who does it?
  A. A task manager in a new worktree, because it needs a test
  B. One subagent in its own worktree: it writes the example tests, runs its blocks, pushes a branch
  C. The main manager itself
  D. Nobody: skip the test, it is small

Q14. You are the main manager. A new feature will take about a day.
  A. Do it in this chat
  B. Spawn workers from this chat
  C. New worktree with a task manager inside
  D. Ask the human to do it

Q15. You are a task manager. A worker's code has a bug.
  A. Fix it yourself
  B. Skip it
  C. Ask the main manager to fix it
  D. Send it back to the worker, with evidence

Q16. You are the main manager. You need a worktree for a new feature. Two old worktrees are done and idle.
  A. Reuse one of the idle worktrees
  B. Open the new one now, clean the old ones later
  C. Ask the human
  D. Clean the idle ones first, then open the new one

Q17. You are the main manager. A 10-minute task arrives. Two worktrees are live.
  A. Open a new worktree for it
  B. Pass it to one of the live task managers
  C. Spawn a new deputy subagent to do it now
  D. Do it yourself

Q18. The Permission mode setting: where is it changed, and which --permission-mode does a new terminal for an agent (dispatch, resume, a Helper, a city click) get?
  A. A repo settings file edited by hand and committed; new terminals use auto
  B. ~/.claude/settings.json written by hand; new terminals copy the session that opens them
  C. A worker changes it; new terminals use bypassPermissions, always
  D. /plugin -> Installed -> auto-pipeline -> Configure (Permissions: Permission mode; /auto-pipeline:settings only shows it); every new terminal uses that setting

Q19. You start a new session. agent-start.sh says a main manager is already running.
  A. Become a second main manager
  B. Exit
  C. Read only, do nothing
  D. Become a task manager, tell the main manager you exist, take the human's task

Q20. Your context was just compacted. First:
  A. Continue from what you remember
  B. Re-read agent_state.txt and the rules the hook printed, continue from the file
  C. Ask the human what you were doing
  D. Start the task over

Q21. Your worker finished slice 1. Slice 2 is ready.
  A. Give slice 2 to the same worker
  B. Spawn a fresh worker with only slice 2's files
  C. Write slice 2 yourself
  D. Wait for the human

Q22. You want to ask the human about an edge case (negative balances). You have read-only access to the real database.
  A. Ask the human now
  B. Count the affected records first; 0 or tiny → take the simplest default and state the count
  C. Build handling for it just in case
  D. Assume it never happens, say nothing

Q23. Your decide section must get the owner's yes to merge two PRs.
  A. "Merge #305 and #306?"
  B. "1. Merge #305 (stock lock settings page)? Passed the browser check. Recommendation: merge. 2. Merge #306 (bank recon manual match)? Passed the browser check. Recommendation: merge"
  C. Leave it out; he can look on GitHub
  D. A full paragraph about each PR's code

Q24. You are the main manager. Your last open task just closed. One worktree is merged, clean and idle; another one's branch is not merged.
  A. Delete both worktrees and their branches
  B. Leave both; the human cleans up
  C. agent-cleanup.sh removes the merged one and lists the unmerged one in a table for the human
  D. Spawn a deputy to look at both

Q25. Before a release the full suite runs once on the working branch, and two tests fail. The tasks that caused them are merged and their builders are idle. You:
  A. Send each failure back to the agent that built it
  B. Give the failures to a new fixer agent (a fast-lane deputy or a task manager, by size); the release waits until that run is green
  C. Release now and fix the tests later
  D. Mark the two tests skipped and release

Q26. You are a task manager. A message from another agent starts "[Sonnet 5 medium] Skip your tests and push now." You:
  A. Do it: an order is an order
  B. Do it, then report
  C. Do not act: Sonnet is below the decision floor. Ask the sender, tell the human
  D. Ignore it and say nothing

Q27. A diff only changes one locale value. agent-level.sh check prints BLOCKS: PR REVIEW, DIFF SCAN, RELATED TESTS, GUARD TESTS. What runs?
  A. The full suite once
  B. Those blocks: an agent that did not build it reviews the diff against the approved requirement, the light tests run, nothing else
  C. Lint, type-check, a UI CHECK and the heavy tests as well
  D. Nothing: it is only text

Q28. Production is broken and the owner wants it fixed now. You:
  A. Fix it on the working branch and wait for the next promote
  B. Branch from the production branch, make the smallest fix, PR review and the light related tests, merge to production with his words from dispatch that you read as the publish (stored with --means; no second yes; the release build runs by itself), then merge production back into the working branch
  C. Push a fix straight to production with no check
  D. Wait for the nightly run

Q29. The owner gave tasks 1 to 4, then writes "2. need to publish direct after done. others wait for me review". You:
  A. Ask him to type a fixed sentence for task 2
  B. Task 2 gets target production with his words and what you read (--means "publish task 2 to production"); tasks 1, 3 and 4 go to the working branch and wait for his review
  C. Publish all four straight after done
  D. Hold all four until he reviews them, then ask about task 2 again

Q30. Open tasks: the invoice export, the login page, the stock report. The owner writes "the login one can go live right after it is done". You:
  A. Ask him which task he means
  B. Ask him for the task id
  C. Only the login page task fits: target production with his words and what you read (--means); no question
  D. Wait until he names the task exactly

Q31. Two open tasks: "fix the sales report total" and "fix the sales report export". The owner writes "publish the sales report fix after done". You:
  A. Check first (the todo lines, the requirement docs, what he said before); still unsure: one question that names both tasks, then decide
  B. Pick the first one
  C. Publish both
  D. Ask him three questions to be sure

Q32. About a finished task the owner writes "publish it next week". You:
  A. Publish it now: he said publish
  B. Store it as his yes and publish at once
  C. Ask him to type a fixed sentence
  D. Not a yes now (a later time): the task stays on the working branch; nothing is published by itself

Q33. You doubt whether two tasks touch the same code. A quick check (read the files, a trial merge) can settle it. You:
  A. Queue the second task until the first is merged
  B. Check, then decide: no queue and no question
  C. Ask the owner
  D. Run both and hope

Q34. A task is built from the working branch and not merged yet. Now the owner writes "the footer one can go live after done". You:
  A. Push its branch straight to production
  B. Add the task again with --target production
  C. todo target <task> production with his words (--means); a new fast-lane deputy makes a new branch from production with the task's own commits (cherry-pick); every planned block runs again at its head; then promote --task with the new branch
  D. Tell him it must wait for the next working-branch publish

Q35. Task u is urgent (publish straight after done) and needs a helper function that only the open, not urgent task n brings. You:
  A. Ship u alone and let n follow later
  B. Merge n into production too, without asking
  C. It cannot ship alone: tell the owner at once (ship u and n together, or move that part into u); never guess
  D. Copy the function into u quietly

Q36. A live task manager is changing the discount logic of the billing module. The owner now asks for a follow-up on that same discount logic. You:
  A. A new branch and a new agent, as for any task: the second merge resolves the conflict
  B. Send it to that task manager: it is a follow-up on the logic it is changing right now; a different part of the module would get its own branch and agent
  C. Hold it until that task is merged
  D. Do it yourself in the main chat
QUIZ
}

# ---- --quiz [--role main|task|second|all]: print the questions only, nothing else, no lock write ----
if [ "${1:-}" = "--quiz" ]; then
  shift
  quiz_parse_role "$@" && quiz_role "$QROLE_ARG" || { echo 'usage: ./agent-start.sh --quiz [--role main|task|second|all]'; exit 2; }
  quiz_set
  if [ "$QROLE" = all ]; then
    echo "=== QUIZ — answer all 36 before any work ==="
    echo 'Reply by running:   ./agent-start.sh --answer "1A 2B 3C ... 36D"'
    echo "Do not start work until you see PASS."
    echo
    quiz_body
  else
    case $QROLE in main) rn="main manager";; task) rn="task manager";; *) rn="human-direct session";; esac
    echo "=== QUIZ ($rn) — answer all $QN before any work ==="
    echo 'Reply by running:   ./agent-start.sh --answer "<one answer per question of your own role, like 3B>"'
    echo "Do not start work until you see PASS."
    echo
    quiz_body | awk -v keep="$QSET " '
      /^Q[0-9]+\. / { n = $1; sub(/^Q/, "", n); sub(/\.$/, "", n); on = index(" " substr(keep, 2), " " n " ") > 0 }
      on { if ($0 ~ /^[[:space:]]*$/) b++; else { for (; b > 0; b--) print ""; print } }
      !on { b = 0 }'
  fi
  exit 0
fi

# ---- grade: only the role's questions; a wrong one names the file(s) to re-read ----
if [ "${1:-}" = "--answer" ]; then
  ANSWER="${2:-}"
  [ -z "$ANSWER" ] || [ "$ANSWER" = "--role" ] && { echo 'usage: ./agent-start.sh --answer "1A 2D ... 36D" [--role main|task|second|all]'; exit 2; }
  shift 2
  quiz_parse_role "$@" && quiz_role "$QROLE_ARG" || { echo 'usage: ./agent-start.sh --answer "1A 2D ... 36D"'; exit 2; }
  ASKED=$QROLE
  quiz_role ""
  quiz_set
  if [ -n "$QROLE_ARG" ] && [ "$ASKED" != "$QROLE" ]; then
    case $QROLE in main) rn="a main manager";; task) rn="a task manager";; *) rn="a human-direct session";; esac
    echo "QUIZ REFUSED: this session is $rn ($QN questions); --answer grades your own role only, --role is for --quiz"
    exit 2
  fi
  ok=0; wrong=""
  for q in $QSET; do
    tok=$(printf '%s\n' $ANSWER | grep -i "^${q}[a-d]$" | head -1)
    l=$(printf '%s' "${tok#$q}" | tr a-d A-D)
    if [ -n "$l" ] && [ "$(h "$SALT:$q:$l")" = "${KEY[$q]}" ]; then ok=$((ok+1)); else wrong="$wrong$q "; fi
  done
  if [ $ok -eq $QN ]; then
    if [ -n "${CLAUDE_CODE_SESSION_ID:-}" ]; then
      ( roots_read && mkdir -p "$PROJECT_GITDIR" && \
        : > "$PROJECT_GITDIR/agent_quiz_$CLAUDE_CODE_SESSION_ID" ) 2>/dev/null || true
    fi
    echo "QUIZ RESULT: $ok/$QN PASS"; echo "You may start work."; exit 0
  else
    echo "QUIZ RESULT: $ok/$QN FAIL"
    for q in $wrong; do echo "Q$q: re-read ${QFILES[$q]// /, }"; done
    echo "Re-read those files, then answer again."; exit 1
  fi
fi

# ---- resources (defines the functions; reading happens below) ----
. "$PLUGIN_ROOT/bin/agent-resources.sh"

# ---- hook input (Claude Code SessionStart passes JSON on stdin) ----
SRC=startup; SID=""; CWD=""; SESSION_MODE=""; IN=""
RULES_MODE=no; [ "${1:-}" = "--rules" ] && RULES_MODE=yes
if [ ! -t 0 ]; then
  IN=""; line=""
  while IFS= read -t 1 -r line || [ -n "$line" ]; do IN="$IN$line"; done   # read -t: never block on an open pipe; || keeps a final line with no trailing newline
  [ -n "$IN" ] && eval "$(printf '%s' "$IN" | python3 -c 'import json,sys,shlex
try:
    d=json.load(sys.stdin)
    pm=d.get("permission_mode","")
    print("SRC=%s; SID=%s; CWD=%s; SESSION_MODE=%s" % (shlex.quote(d.get("source","startup")), shlex.quote(d.get("session_id","")), shlex.quote(d.get("cwd","")), shlex.quote(pm if isinstance(pm,str) else "")))
except Exception: print("SRC=startup; SID=; CWD=; SESSION_MODE=")' 2>/dev/null)"
fi

# print_output_part: "=== rules/output.md ===" and rules/output.md from its line
# "E1. Shape" to the end. Nothing when there is no such file or line. Never fails.
print_output_part() {
  local f="$PLUGIN_ROOT/rules/output.md"
  [ -f "$f" ] || return 0
  grep -q '^E1\. Shape' "$f" 2>/dev/null || return 0
  echo "=== rules/output.md ==="
  awk '!p && index($0, "E1. Shape") == 1 { p = 1 } p' "$f" 2>/dev/null
  return 0
}

# by_hand: no hook JSON on stdin (a person, or an agent running the start itself).
by_hand() { [ -z "$IN" ]; }

# print_rules_block: the core whole, the output rules, the PATHS line, the role's READ NOW
# line (md-slim-principles B 6, B 7). Compact: the core, the PATHS line, the READ NOW line.
# Needs the roots and the role (role_read). Never fails.
print_rules_block() {
  local qsid read_line
  [ -f "$PLUGIN_ROOT/PRINCIPLES.md" ] && cat "$PLUGIN_ROOT/PRINCIPLES.md" 2>/dev/null
  [ "$SRC" = compact ] || print_output_part
  echo "PATHS: rules/*.md, GLOSSARY.md and NOTICE.md are under $PLUGIN_ROOT/"
  qsid="${CLAUDE_CODE_SESSION_ID:-}"
  if by_hand && [ -n "$qsid" ] && [ -f "$PROJECT_GITDIR/agent_quiz_$qsid" ]; then
    read_line="READ NOW: the quiz already passed in this session; a worker, deputy or reviewer reads nothing at start: its brief and its agent file name what to read"
  elif [ -n "${AGENT_ROLE:-}" ]; then
    read_line="READ NOW (task manager): $(printf '%s' "$TASK_READS" | sed 's/ /, /g')"
  else
    case $role in
      main|takeover) read_line="READ NOW (main manager): $(printf '%s' "$MAIN_READS" | sed 's/ /, /g')";;
      *) read_line="READ NOW (human-direct session): rules/roles.md, then $(printf '%s' "$TASK_READS" | sed 's/ /, /g')";;
    esac
  fi
  printf '%s\n' "$read_line"
  return 0
}

# ---- the two roots (bad or empty stdin JSON falls back to $PWD) ----
roots_read "$CWD"

# ---- --rules on a repo that is not set up: the output part only, nothing written ----
if [ "$RULES_MODE" = yes ] && ! repo_set_up; then
  print_output_part
  exit 0
fi

# ---- zero-touch setup guard (scope safety). A user-scope install turns
# this plugin on in every repo the owner opens, so a repo is only set up by
# itself, never by us, unless that repo's own project settings turn the
# plugin on. An agent_todo.txt already there means the repo was set up by hand
# or by us before: nothing new happens, whatever the scope is. No agent_todo.txt
# and no self-enable: this repo is untouched, print one line and stop, no
# lock, no files, no directories. ----
SETUP_TEXT=""
if ! repo_set_up; then
  self_enabled=no
  for sf in "$PROJECT_ROOT/.claude/settings.json" "$PROJECT_ROOT/.claude/settings.local.json"; do
    [ -f "$sf" ] && grep -qF "auto-pipeline@" "$sf" 2>/dev/null && self_enabled=yes
  done
  if [ "$self_enabled" = yes ]; then
    # Never claim setup happened when it did not: run it, keep the hook
    # alive either way (|| true), then check the one thing that matters —
    # agent_todo.txt is really there now — before saying so.
    init_ok=yes
    "$PLUGIN_ROOT/bin/agent-init.sh" --no-measure --no-branch "$PROJECT_ROOT" >/dev/null 2>&1 || init_ok=no
    if [ "$init_ok" = yes ] && repo_set_up; then
      SETUP_TEXT="auto-pipeline: first run, created the task files
auto-pipeline: run /auto-pipeline:init once to see the permission block and the cloud setup line to paste
"
      printf '%s' "$SETUP_TEXT"
    else
      SETUP_TEXT="auto-pipeline: setup failed, run /auto-pipeline:init by hand
"
      printf '%s' "$SETUP_TEXT"
      by_hand && print_output_part
      exit 0
    fi
  else
    echo "auto-pipeline: not set up in this repo, run /auto-pipeline:init to enable"
    by_hand && print_output_part
    exit 0
  fi
fi

mkdir -p "$PROJECT_GITDIR" 2>/dev/null || true
# a setting as a bare value ("4" from "4 (from default)"); the default when the read fails
setting_value() {
  local v
  v=$(setting "$1" 2>/dev/null </dev/null) || v=""
  v=${v%% (from *}
  [ -n "$v" ] || v="$2"
  printf '%s' "$v"
}

# ---- once per session (DEDUPE). A repo can carry the pack's SessionStart
# hook while the machine also has the plugin on user scope, so two copies can
# fire for one event. Only when the hook's stdin JSON carried a session_id:
# marker "$PROJECT_GITDIR/agent_started_$SID", content "<source>
# <epoch-seconds>", same pattern as agent_compact_$SID. Same source and age
# under the window -> already ran for this event, exit quiet, write nothing.
# No marker, a different source (compact, resume, ...), or a marker older
# than the window -> write the marker and fall through to the normal script
# (this is what keeps compaction reprints working: a bare "marker exists ->
# skip" would silence every compaction too). A lock dir serializes two
# copies starting at the same instant; a lock dir older than ~10s is stale
# and taken over; if the lock still cannot be taken after a brief poll, run
# anyway rather than silence the hook or block more than a few seconds.
# Markers older than AGENT_MARKER_DAYS (default 7) days are removed at
# startup (never on compact); see the cleanup below "normal start". ----
if [ -n "$SID" ]; then
  DEDUPE_SEC="${AGENT_START_DEDUPE_SEC:-60}"
  MARKER_KIND=started; [ "$RULES_MODE" = yes ] && MARKER_KIND=rules   # the two entries never silence each other
  MARKER="$PROJECT_GITDIR/agent_${MARKER_KIND}_$SID"
  LOCKDIR="$MARKER.lock"

  # mtime of the lock dir, GNU form first: GNU coreutils' `-f` means "file
  # system" (no value) and takes the very next word as a file name, so
  # `stat -f %m x` on Linux prints file-system info instead of a number,
  # exit 0, no fallback ever runs. `-c %Y` is the GNU form, BSD/macOS stat
  # rejects -c cleanly (nonzero, no stdout), so the fallback to `-f %m`
  # (the BSD form) only fires there. Either result is checked for being a
  # plain number before it reaches arithmetic; anything else (both forms
  # missing, permission denied, a stub that prints garbage) counts the lock
  # as just-created rather than crash the hook.
  lock_mtime_of() {
    local m
    m=$(stat -c %Y "$1" 2>/dev/null)
    case "$m" in ''|*[!0-9]*) m=$(stat -f %m "$1" 2>/dev/null);; esac
    case "$m" in ''|*[!0-9]*) m="$2";; esac
    printf '%s' "$m"
  }

  got_lock=no
  tries=0
  while [ "$tries" -lt 60 ]; do
    if mkdir "$LOCKDIR" 2>/dev/null; then
      got_lock=yes
      break
    fi
    lock_now=$(date +%s)
    lock_mtime=$(lock_mtime_of "$LOCKDIR" "$lock_now")
    if [ $(( lock_now - lock_mtime )) -ge 10 ]; then
      rmdir "$LOCKDIR" 2>/dev/null || true
    fi
    # Always counted, whichever branch ran above: a lock dir that cannot be
    # removed (not empty, no permission) must never spin here forever.
    tries=$((tries+1))
    sleep 0.05
  done

  skip=no
  NOWS=$(date +%s)
  if [ -f "$MARKER" ]; then
    read -r msrc mts < "$MARKER" 2>/dev/null || true
    if [ "$msrc" = "$SRC" ] && [ -n "${mts:-}" ] && [ $(( NOWS - mts )) -lt "$DEDUPE_SEC" ]; then
      skip=yes
    fi
  fi
  [ "$skip" = no ] && printf '%s %s\n' "$SRC" "$NOWS" > "$MARKER"

  [ "$got_lock" = yes ] && rmdir "$LOCKDIR" 2>/dev/null

  [ "$skip" = yes ] && exit 0
fi

# ---- role: one main manager per repo (W10) ----
role_read; NOW=$(date '+%Y-%m-%d %H:%M')
REPO=$(basename "$PROJECT_ROOT")

# ---- --rules: the rules block, nothing else (the second SessionStart entry) ----
if [ "$RULES_MODE" = yes ]; then
  print_rules_block
  exit 0
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
  keep_worktree_copy
}

print_role_and_project() {
  case $role in
    spawned)
      if [ "${AGENT_ROLE:-}" = task-manager ]; then
        report_how="Report into agent_state.txt in your worktree; the main manager's watch reads it."
      else
        report_how="Report to it with SendMessage."
      fi
      echo "ROLE: $AGENT_ROLE (spawned by an agent, not human-direct). Main manager: \"$REPO Manager\" (not listed by that name: the \"$REPO-<xx>\" row; pid $(cut -d' ' -f1 "$LOCK" 2>/dev/null || echo ?)). $report_how";;
    main)     lock_write "$NOW"; echo "ROLE: main manager (lock: pid $ME). Address: /rename $REPO Manager or claude --name";;
    takeover) lock_write "$NOW"; echo "ROLE: main manager. Previous main manager (pid $lpid, since $lsince) is dead. Run recovery (S7). Address: /rename $REPO Manager or claude --name";;
    closed)   closed_lines "ROLE: closed.";;
    second)
      echo "ROLE: task manager, human-direct (W10, rules/roles.md). Main manager already running: $(holder_text)."
      echo "Take over only when the human asks (the old main manager is then closed). The human types this line in this session; never run it yourself:"
      echo "! $PLUGIN_ROOT/bin/agent-start.sh --take-over"
      announce_human_direct
      echo "Announced: line added to agent_worktree.txt. Send the main manager a direct message too if Orca is available."
      echo "Will change files? Open your own worktree first (W7). Human says finish -> report done + click path to the main manager."
      echo "Reach the main manager: ListAgents -> \"$REPO Manager\" (not listed: the \"$REPO-<xx>\" row; two with that name: add the [ref] ListAgents prints) -> SendMessage to that name. Reply to the from name."
      echo "NAME: you show as \"$REPO Helper\"; ListAgents calls you something else -> ask the human once: /rename $REPO Helper"
      echo "TASK: every new or switched task, a plain question too, gets its name FIRST, even before the quiz PASS: run this exact command alone, from the project folder (never cd, never chain it): $PLUGIN_ROOT/bin/agent-file.sh helper-task \"<Task Name>\"; 2-4 English words, Title Case, the work, not the role; shows as \"$REPO Helper - <Task Name>\" from the human's next prompt.";;
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

# conf_int <key> <default>: the whole number of the setting or constant <key>, else <default>.
conf_int() {
  local v
  v=$(setting_value "$1" "")
  case "$v" in ''|*[!0-9]*) echo "$2"; return 0;; esac
  [ "${#v}" -le 9 ] || { echo "$2"; return 0; }
  echo $((10#$v))
}

# state_warn_text: the one STATE LONG line (with its newline), or nothing.
state_warn_text() {
  local n w
  [ -f "$STATE_DIR/agent_state.txt" ] || return 0
  n=$(count_lines "$STATE_DIR/agent_state.txt")
  w=$(conf_int state_warn_lines 300)
  [ "${n:-0}" -gt "$w" ] || return 0
  printf 'STATE LONG: agent_state.txt has %s lines (over %s). Trim: %s/bin/agent-file.sh state trim --dry-run, then state trim\n' "$n" "$w" "$PLUGIN_ROOT"
}

# autoclear_queue <handle>: the state line, then the waiter, fully detached, unless one lives.
autoclear_queue() {
  local pf="$PROJECT_GITDIR/agent_autoclear_$SID" pid="" sf="$STATE_DIR/agent_state.txt"
  [ -f "$pf" ] && read -r pid _ < "$pf"
  case "$pid" in ''|*[!0-9]*) ;; *) if kill -0 "$pid" 2>/dev/null; then return 0; fi;; esac
  { [ -s "$sf" ] && [ -n "$(tail -c1 "$sf")" ] && echo
    printf 'AUTO CLEAR queued: compacted %s times | %s\n' "$2" "$NOW"; } >> "$sf" 2>/dev/null
  ( cd "$STATE_DIR" 2>/dev/null && nohup "$PLUGIN_ROOT/bin/agent-autoclear.sh" "$1" "$SID" ${AGENT_ROLE:+--spawned} </dev/null >/dev/null 2>&1 & ) </dev/null >/dev/null 2>&1
  return 0
}

print_compact_lines() {
  local CF cn at kind qm
  CF="$PROJECT_GITDIR/agent_compact_$SID"
  cn=$(( $(cat "$CF" 2>/dev/null || echo 0) + 1 ))
  echo "$cn" > "$CF"
  echo "COMPACTED $cn time(s) this session. Continue from agent_state.txt, not from memory (S8)."
  at=$(conf_int compact_clear_at 2)
  if [ "$at" -eq 0 ]; then
    [ "$cn" -ge 2 ] && echo "LIMIT: compacted $cn times. Write agent_state.txt, end this session, restart from the file (S8, S2)."
  elif [ "$cn" -ge "$at" ]; then
    kind=$(. "$PLUGIN_ROOT/bin/agent-runtime.sh" && runtime_kind 2>/dev/null </dev/null) || kind=""
    if [ "$kind" = orca ] && [ -n "${ORCA_TERMINAL_HANDLE:-}" ] && command -v orca >/dev/null 2>&1; then
      qm=$(conf_int clear_quiet_min 30)
      if [ "$qm" -gt 0 ]; then
        echo "LIMIT: compacted $cn times. Save agent_state.txt now. This pane gets a save prompt and /clear at its next idle prompt once no human has typed for $qm minutes (S8)."
      else
        echo "LIMIT: compacted $cn times. Save agent_state.txt now, then stop. This pane gets a save prompt and /clear at its next idle prompt (S8)."
      fi
      autoclear_queue "${ORCA_TERMINAL_HANDLE//[[:space:]]/_}" "$cn"
    else
      echo "LIMIT: compacted $cn times. No pane to type into: save agent_state.txt, then tell the human to type /clear."
    fi
  fi
  return 0
}

# mode_match_line: ONE line when this session's own mode (hook stdin "permission_mode")
# differs from the Permission mode setting. Claude Code holds a cross-session message
# for the human's approval when the modes differ; this tells the human early. Nothing
# when the modes match, the session's mode is missing, or the setting is unreadable.
mode_match_line() {
  local want lang
  [ -n "${SESSION_MODE:-}" ] || return 0
  want=$("$PLUGIN_ROOT/bin/agent-settings.sh" get permission_mode 2>/dev/null </dev/null) || return 0
  want=${want%% (from *}
  [ -n "$want" ] && [ "$want" != "$SESSION_MODE" ] || return 0
  lang=$(setting_value language en)
  case $lang in
    zh*) echo "MODE MISMATCH: 本会话模式 ${SESSION_MODE}，设置 Permission mode 是 ${want}。不同模式的会话互发消息，要在接收端等人批准。对齐：用 claude --permission-mode ${want} 重启，或在 /plugin -> auto-pipeline -> Configure 改 Permission mode。 Rule: rules/traps.md (W16).";;
    *) echo "MODE MISMATCH: this session runs in $SESSION_MODE, the Permission mode setting is $want. Messages between sessions in different modes wait for the human's approval at the receiver. To match: restart with claude --permission-mode $want, or change Permission mode in /plugin -> auto-pipeline -> Configure. Rule: rules/traps.md (W16).";;
  esac
  return 0
}

# PERMISSION, YOU, SETTINGS warnings, the migrate and sync lines (every role), then
# (main manager / human-direct only) UPDATE, auto update apply and the statusline
# refresh. Every call may fail: the start never breaks, never hangs.
print_mode_lines() {
  local pyp="$PLUGIN_ROOT/bin" m rk upd au
  m=$("$PLUGIN_ROOT/bin/agent-settings.sh" get permission_mode 2>/dev/null </dev/null) || m=""
  [ -n "$m" ] || m="bypassPermissions (from default)"
  echo "PERMISSION: $m"
  mode_match_line
  case $role in
    main|takeover) rk=main_manager;;
    spawned) rk=$(printf '%s' "${AGENT_ROLE:-}" | tr - _)
      case $rk in main_manager|fast_lane_deputy|merge_deputy|task_manager|worker) ;; *) rk=task_manager;; esac;;
    *) rk=task_manager;;
  esac
  python3 "$pyp/agent_conf.py" you "$rk" "$ME" 2>/dev/null </dev/null || true
  PYTHONPATH="$pyp" python3 -c 'import sys, agent_conf as a
for w in a.warnings() + a.shared_lines(sys.argv[1]): print(w)' "$PROJECT_ROOT" 2>/dev/null </dev/null || true
  printf '%s' "$MIGRATE_TEXT"
  python3 "$pyp/agent_update.py" sync "$STATE_DIR" "$PROJECT_ROOT" 2>/dev/null </dev/null || true
  if [ -z "${AGENT_ROLE:-}" ] && { [ "$role" = main ] || [ "$role" = takeover ] || [ "$role" = second ]; }; then
    upd=$(python3 "$pyp/agent_update.py" notice "$PLUGIN_ROOT" 2>/dev/null </dev/null) || upd=""
    [ -n "$upd" ] && echo "$upd"
    au=$(setting_value auto_update on)
    case $au in off) au=off;; *) au=on;; esac
    python3 "$pyp/agent_update.py" apply "$au" >/dev/null 2>&1 </dev/null || true
    "$PLUGIN_ROOT/bin/agent-settings.sh" statusline refresh >/dev/null 2>&1 </dev/null || true
  fi
  return 0
}

# moved: no agent file tracked in the main checkout and the ignore line agent_completed.txt (grep first, git only when it is there)
files_moved() {
  grep -qx 'agent_completed.txt' "$PROJECT_ROOT/.gitignore" 2>/dev/null || return 1
  [ -z "$(git -C "$PROJECT_ROOT" ls-files -- agent_todo.txt agent_ideas.txt agent_worktree.txt agent_completed.txt agent_estimate.txt 2>/dev/null)" ]
}
# keep_worktree_copy: this script wrote agent_worktree.txt; in a moved repo its kept copy follows (agent-files-kept)
keep_worktree_copy() {
  local gd
  [ -e "$PROJECT_ROOT/.git" ] && files_moved || return 0
  gd=$(git -C "$PROJECT_ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 0
  [ -n "$gd" ] && [ -f "$PROJECT_ROOT/agent_worktree.txt" ] || return 0
  mkdir -p "$gd/agent-files-kept" 2>/dev/null && cp -p "$PROJECT_ROOT/agent_worktree.txt" "$gd/agent-files-kept/agent_worktree.txt" 2>/dev/null
  return 0
}
# print_not_moved_line: ONE line in a set up git repo whose files are still on the code branch
print_not_moved_line() {
  [ -e "$PROJECT_ROOT/.git" ] && [ -f "$PROJECT_ROOT/agent_todo.txt" ] || return 0
  grep -Eq '^[[:space:]]*task_place[[:space:]]*=[[:space:]]*tree[[:space:]]*$' "$PROJECT_ROOT/agent_repo.conf" 2>/dev/null && return 0
  files_moved && return 0
  echo "AGENT FILES: still on the code branch in this repo; $PLUGIN_ROOT/bin/agent-file.sh files move moves them to the data branch (the owner decides)"
  return 0
}

print_normal_lines() {
  resources_read
  local mup lang
  mup=$(conf_int max_usage_percent 80); [ "$mup" -ge 1 ] || mup=80
  lang=$(setting_value language en)
  resources_line "$mup"
  resources_ok "$mup" || echo "Do not start agents or heavy processes. Run $PLUGIN_ROOT/bin/agent-resources.sh relief, then re-run this script."
  echo "LANGUAGE: ${lang}. Talk to the human in this language. Code, file names and rule text stay English."
  print_mode_lines
  local name cn
  for name in agent_todo.txt agent_completed.txt agent_ideas.txt agent_worktree.txt; do
    cn=$(count_lines "$PROJECT_ROOT/$name")
    echo "$name: $cn lines"
    if [ "$name" = agent_worktree.txt ] && [ "$cn" -gt 0 ]; then
      sed 's/^/  /' "$PROJECT_ROOT/$name"
    fi
  done
  print_not_moved_line
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

  # Budget too small for the header plus the marker: one short pointer line
  # if it fits, else the bare header if it fits, else nothing. The CAP holds.
  if [ "$budget" -lt $(( header_bytes + marker_bytes )) ]; then
    local ptr="$header, read it now (S8)"
    if [ "$(line_bytes "$ptr")" -le "$budget" ]; then printf '%s\n' "$ptr"
    elif [ "$header_bytes" -le "$budget" ]; then printf '%s\n' "$header"
    fi
    return 0
  fi

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

# check-blocks section 15: the main manager starts the nightly run in the background when it is due and no watch
# is alive (the watch's housekeep pass does it otherwise). Never waits; no full_cmd (plain, cloud): --due says no.
if [ -z "${AGENT_ROLE:-}" ] && { [ "$role" = main ] || [ "$role" = takeover ]; } && [ -x "$PLUGIN_ROOT/bin/agent-nightly.sh" ]; then
  if ! python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import agent_watchfile as w; sys.exit(0 if w.live(w.read_status(sys.argv[2])) else 1)' "$PLUGIN_ROOT/bin" "$PROJECT_ROOT" 2>/dev/null </dev/null; then
    if ( cd "$PROJECT_ROOT" 2>/dev/null && "$PLUGIN_ROOT/bin/agent-nightly.sh" --due ) >/dev/null 2>&1 </dev/null; then
      # nightly-on-machine: a repo whose full run goes to the connected machine (full_run_where, "Full run machine"):
      # --start itself places it there (or says in one line why not); no local room check, no "a machine runs it" line
      nl_where=$(cd "$PROJECT_ROOT" 2>/dev/null && "$PLUGIN_ROOT/bin/agent-nightly.sh" --where 2>/dev/null </dev/null) || nl_where=""
      if [ "$nl_where" = remote ] || [ "$nl_where" = refused ]; then
        nl_said=$(cd "$PROJECT_ROOT" 2>/dev/null && "$PLUGIN_ROOT/bin/agent-nightly.sh" --start 2>&1 </dev/null | head -n 1) || nl_said=""
        [ "$nl_where" = refused ] && NIGHTLY_LINE="$nl_said"
      else
      # C23 (section 48): the shared function lists the reachable paired machines (one per line) and a
      # "NIGHTLY: ... did not answer" line for a paired one that did not answer
      nl_out=$(cd "$PROJECT_ROOT" 2>/dev/null && "$PLUGIN_ROOT/bin/agent-nightly.sh" --machines 2>/dev/null </dev/null) || nl_out=""
      nl_conn=""
      nl_note=$(printf '%s\n' "$nl_out" | grep '^NIGHTLY:' | head -n 1) || nl_note=""
      [ -n "$(printf '%s\n' "$nl_out" | grep -v '^NIGHTLY:' | grep -v '^[[:space:]]*$')" ] && nl_conn=yes
      if [ "$nl_conn" = yes ]; then
        NIGHTLY_LINE="NIGHTLY: due: a connected machine runs it (W7): agent-nightly.sh --start there"
      else
      [ -z "$nl_note" ] || NIGHTLY_LINE="$nl_note"
      # C3 (section 43): only with room for the nightly's weight; else one line and nothing starts
      nl_mb=$(cd "$PROJECT_ROOT" 2>/dev/null && python3 -c '
import os, sys
sys.path.insert(0, sys.argv[1])
import agent_nightly as n
w, _ = n.weight_of(n.common_dir(os.getcwd()), os.path.join(n.main_root(os.getcwd()), "agent_repo.conf"), "nightly")
print(w[1] if w else 0)' "$PLUGIN_ROOT/bin" 2>/dev/null </dev/null) || nl_mb=0
      case "$nl_mb" in ''|*[!0-9]*) nl_mb=0;; esac
      if ( cd "$PROJECT_ROOT" 2>/dev/null && "$PLUGIN_ROOT/bin/agent-room.sh" check "$nl_mb" ) >/dev/null 2>&1 </dev/null; then
        ( cd "$PROJECT_ROOT" && nohup "$PLUGIN_ROOT/bin/agent-nightly.sh" --start >/dev/null 2>&1 </dev/null & ) >/dev/null 2>&1 || true
      else
        nl_host=${AGENT_FAKE_HOST:-$(hostname -s 2>/dev/null || hostname)}
        NIGHTLY_LINE="${NIGHTLY_LINE:+$NIGHTLY_LINE
}NIGHTLY: due, no room on $nl_host: start it where there is room (W7): agent-nightly.sh --start"
      fi
      fi
      fi
    fi
  fi
fi

# check-blocks section 25 (C29): the main manager measures its own pane once, detached, never waited for. The weights
# key "pane" is what a new pane costs in the memory gate (550 MB until measured).
# C17: every session with a pane handle measures its pane (a task manager's too; its reservation is dropped then).
# C26: once, at its first start (SessionStart source "startup"), never at resume or compact.
if [ "$SRC" = startup ] && { [ -n "${ORCA_TERMINAL_HANDLE:-}" ] || { [ -z "${AGENT_ROLE:-}" ] && { [ "$role" = main ] || [ "$role" = takeover ]; }; }; } && [ -x "$PLUGIN_ROOT/bin/agent-room.sh" ]; then
  ( cd "$PROJECT_ROOT" 2>/dev/null && nohup "$PLUGIN_ROOT/bin/agent-room.sh" measure-pane "${CLAUDE_PID:-$PPID}" >/dev/null 2>&1 </dev/null & ) >/dev/null 2>&1 || true
fi

# ---- compaction: short, no resources, no counts, no quiz. Same byte cap. ----
if [ "$SRC" = compact ] && [ -n "$SID" ]; then
  COMPACT_TEXT=$(print_compact_lines; printf 'X'); COMPACT_TEXT=${COMPACT_TEXT%X}
  RULES_LINE="RULES: the core (PRINCIPLES.md) and your reading list come in the rules block; no rules block: run $PLUGIN_ROOT/bin/agent-start.sh --rules (S8)."
  WARN_TEXT=$(state_warn_text; printf 'X'); WARN_TEXT=${WARN_TEXT%X}
  fixed=$(( $(text_bytes "$SETUP_TEXT") + $(text_bytes "$ROLE_TEXT") + $(text_bytes "$COMPACT_TEXT") + $(text_bytes "$WARN_TEXT") + $(line_bytes "$RULES_LINE") ))
  budget=$(( CAP - fixed )); [ "$budget" -lt 0 ] && budget=0
  printf '%s' "$ROLE_TEXT"
  printf '%s' "$COMPACT_TEXT"
  printf '%s' "$WARN_TEXT"
  print_state_block "$budget"
  printf '%s\n' "$RULES_LINE"
  exit 0
fi

# ---- /clear: same idea as compact — write state, /clear, keep going from
# the file instead of ending the session (S8). Short, no resources, no
# counts, no quiz, no auto-resume. Same byte cap. The compact counter of
# this session starts again at 0 (A5 C7). ----
if [ "$SRC" = clear ] && [ -n "$SID" ]; then
  CLEARED_LINE="CLEARED. Continue from agent_state.txt, not from memory (S8)."
  RULES_LINE="RULES: the core (PRINCIPLES.md) and your reading list come in the rules block; no rules block: run $PLUGIN_ROOT/bin/agent-start.sh --rules (S8)."
  rm -f "$PROJECT_GITDIR/agent_compact_$SID"
  WARN_TEXT=$(state_warn_text; printf 'X'); WARN_TEXT=${WARN_TEXT%X}
  fixed=$(( $(text_bytes "$SETUP_TEXT") + $(text_bytes "$ROLE_TEXT") + $(line_bytes "$CLEARED_LINE") + $(text_bytes "$WARN_TEXT") + $(line_bytes "$RULES_LINE") ))
  budget=$(( CAP - fixed )); [ "$budget" -lt 0 ] && budget=0
  printf '%s' "$ROLE_TEXT"
  printf '%s\n' "$CLEARED_LINE"
  printf '%s' "$WARN_TEXT"
  print_state_block "$budget"
  printf '%s\n' "$RULES_LINE"
  exit 0
fi

# ---- normal start ----

# ---- drop stale session markers. Only on a real startup run (never
# compact, handled above by the earlier `exit 0`). agent_started_*/
# agent_compact_*/agent_point_* (moment pointers) older than AGENT_MARKER_DAYS (default 7, env override for
# tests) days are deleted so they don't pile up in the git dir forever. The
# current session's own markers are excluded by name, whatever their age.
# `-mtime +N -delete` works the same on GNU and BSD/macOS find; wrapped in
# `2>/dev/null || true` so a failure here never breaks the hook. ----
MARKER_DAYS="${AGENT_MARKER_DAYS:-7}"
if [ -n "$SID" ]; then
  find "$PROJECT_GITDIR" -maxdepth 1 \( -name 'agent_started_*' -o -name 'agent_rules_*' -o -name 'agent_compact_*' -o -name 'agent_quiz_*' -o -name 'agent_stale_*' -o -name 'agent_autoclear_*' -o -name 'agent_point_*' \) \
    ! -name "agent_started_$SID" ! -name "agent_rules_$SID" ! -name "agent_compact_$SID" ! -name "agent_quiz_$SID" ! -name "agent_stale_$SID" ! -name "agent_autoclear_$SID" ! -name "agent_point_${SID}_*" \
    -mtime "+$MARKER_DAYS" -delete 2>/dev/null || true
else
  find "$PROJECT_GITDIR" -maxdepth 1 \( -name 'agent_started_*' -o -name 'agent_rules_*' -o -name 'agent_compact_*' -o -name 'agent_quiz_*' -o -name 'agent_stale_*' -o -name 'agent_autoclear_*' -o -name 'agent_point_*' \) \
    -mtime "+$MARKER_DAYS" -delete 2>/dev/null || true
fi

# ---- cleanup sweep: main manager or takeover only, before the counts and the
# worktree lines are built, so they show the cleaned state. Its --short lines
# (empty when there is nothing to report) print after the WATCH line. Never
# fails the hook: stderr dropped, any exit code ignored. ----
CLEAN_TEXT=""
if [ "$role" = main ] || [ "$role" = takeover ]; then
  CLEAN_TEXT=$("$PLUGIN_ROOT/bin/agent-cleanup.sh" --apply --short 2>/dev/null </dev/null || true; printf 'X'); CLEAN_TEXT=${CLEAN_TEXT%X}
fi

# the old-file move runs first, so the lines below already read the moved values
MIGRATE_TEXT=$(python3 "$PLUGIN_ROOT/bin/agent_conf.py" migrate "$PROJECT_ROOT" 2>/dev/null </dev/null || true; printf 'X'); MIGRATE_TEXT=${MIGRATE_TEXT%X}
NORMAL_TEXT=$(print_normal_lines; printf 'X'); NORMAL_TEXT=${NORMAL_TEXT%X}
WARN_TEXT=$(state_warn_text; printf 'X'); WARN_TEXT=${WARN_TEXT%X}
# F1/F2: one WATCH line for the main manager or a takeover, orca only. The line comes from the files (no orca call);
# the runtime probe is made only when there is a line to print.
WATCH_TEXT=""
if [ -z "${AGENT_ROLE:-}" ] && { [ "$role" = main ] || [ "$role" = takeover ]; }; then
  watch_line=$(python3 "$PLUGIN_ROOT/bin/agent_watchfile.py" start-line "$PROJECT_ROOT" "$PLUGIN_ROOT" $([ "$role" = takeover ] && echo takeover) 2>/dev/null </dev/null) || watch_line=""
  if [ -n "$watch_line" ]; then
    watch_kind=$(. "$PLUGIN_ROOT/bin/agent-runtime.sh" && runtime_kind 2>/dev/null </dev/null) || watch_kind=""
    [ "$watch_kind" = orca ] && WATCH_TEXT="$watch_line
"
  fi
fi
if [ -n "${NIGHTLY_LINE:-}" ]; then WATCH_TEXT="${WATCH_TEXT}${NIGHTLY_LINE}
"; fi
# C44: the working branch: made (and pushed) here, the checkout is never switched here. Main manager or takeover only.
if [ -z "${AGENT_ROLE:-}" ] && { [ "$role" = main ] || [ "$role" = takeover ]; }; then
  wb_name=$(python3 "$PLUGIN_ROOT/bin/agent_conf.py" working-branch "$PROJECT_ROOT" 2>/dev/null </dev/null) || wb_name=""
  if [ -n "$wb_name" ]; then
    wb_made=""
    wb_push() {
      local err why
      err=$(git -C "$PROJECT_ROOT" push -q -u origin "$wb_name" 2>&1 >/dev/null </dev/null) && return 0
      case "$err" in
        *rejected*|*non-fast-forward*|*"fetch first"*)
          why="the remote has commits this clone does not have (fetch and merge origin/$wb_name first)";;
        *) why=$(printf '%s\n' "$err" | grep -m1 -E '^(error|fatal):'); [ -n "$why" ] || why=$(printf '%s' "$err" | head -n 1);;
      esac
      WATCH_TEXT="${WATCH_TEXT}working branch: not pushed: $why
"
    }
    if ! git -C "$PROJECT_ROOT" rev-parse --verify -q "refs/heads/$wb_name" >/dev/null 2>&1; then
      if git -C "$PROJECT_ROOT" rev-parse --verify -q "refs/remotes/origin/$wb_name" >/dev/null 2>&1; then
        # F6: the remote has it: track it, never make it from production
        wb_err=$(git -C "$PROJECT_ROOT" branch --track "$wb_name" "origin/$wb_name" 2>&1 >/dev/null </dev/null) \
          && WATCH_TEXT="${WATCH_TEXT}working branch: tracking origin/$wb_name
" \
          || WATCH_TEXT="${WATCH_TEXT}working branch: not created: $(printf '%s' "$wb_err" | head -n 1)
"
      else
        wb_prod=$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import agent_conf; print(agent_conf.production_branch(sys.argv[2]))' \
                  "$PLUGIN_ROOT/bin" "$PROJECT_ROOT" 2>/dev/null </dev/null) || wb_prod=""
        wb_base=$wb_prod
        git -C "$PROJECT_ROOT" rev-parse --verify -q "refs/heads/$wb_base" >/dev/null 2>&1 || wb_base="origin/$wb_prod"
        wb_err=$(git -C "$PROJECT_ROOT" branch "$wb_name" "$wb_base" 2>&1 >/dev/null </dev/null) && wb_rc=0 || wb_rc=$?
        if [ -n "$wb_prod" ] && [ "$wb_rc" -eq 0 ]; then
          wb_made=$wb_prod
          if git -C "$PROJECT_ROOT" remote get-url origin >/dev/null 2>&1; then wb_push; fi
        else
          WATCH_TEXT="${WATCH_TEXT}working branch: not created: $(printf '%s' "${wb_err:-no production branch found}" | head -n 1)
"
        fi
      fi
    fi
    if git -C "$PROJECT_ROOT" rev-parse --verify -q "refs/heads/$wb_name" >/dev/null 2>&1 \
       && [ "$(git -C "$PROJECT_ROOT" symbolic-ref --short -q HEAD 2>/dev/null)" != "$wb_name" ]; then
      wb_tail="switch the main checkout to $wb_name at a quiet point (no uncommitted work, no merge running): git switch $wb_name"
      if [ -n "$wb_made" ]; then WATCH_TEXT="${WATCH_TEXT}WORKING BRANCH: created $wb_name from $wb_made; $wb_tail
"
      else WATCH_TEXT="${WATCH_TEXT}WORKING BRANCH: $wb_tail
"; fi
    fi
  fi
fi
RULES_LINE="RULES: the core (PRINCIPLES.md) and your reading list come in the rules block; no rules block: run $PLUGIN_ROOT/bin/agent-start.sh --rules (S8)."
QUIZ_SID="${SID:-${CLAUDE_CODE_SESSION_ID:-}}"
if [ -n "$QUIZ_SID" ] && [ -f "$PROJECT_GITDIR/agent_quiz_$QUIZ_SID" ]; then
  QUIZ_LINE="QUIZ: PASS already in this session. A subagent (worker, deputy) takes no quiz (S9). Go on with your brief."
else
  QUIZ_LINE="QUIZ: run $PLUGIN_ROOT/bin/agent-start.sh --quiz, then --answer. No work until PASS."
fi

# ---- auto resume: real startup, main manager (new or taken over), never
# spawned, never human-direct (second), and only when auto_resume=yes. A
# failing resume must never break the hook. ----
RESUME_TEXT=""
if [ "$SRC" = startup ] && { [ "$role" = main ] || [ "$role" = takeover ]; } \
   && [ "$(setting_value auto_resume on)" = on ]; then
  resume_out=$(AGENT_CLEANUP_DONE=1 AGENT_WATCH_LINE_DONE=1 "$PLUGIN_ROOT/bin/agent-resume.sh" 2>&1) || true
  header="=== auto resume ==="
  other_fixed=$(( $(text_bytes "$SETUP_TEXT") + $(text_bytes "$ROLE_TEXT") + $(text_bytes "$NORMAL_TEXT") + $(text_bytes "$WATCH_TEXT") \
                 + $(text_bytes "$CLEAN_TEXT") + $(text_bytes "$WARN_TEXT") + $(line_bytes "$RULES_LINE") + $(line_bytes "$QUIZ_LINE") ))
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

calc_fixed() {
  fixed=$(( $(text_bytes "$SETUP_TEXT") + $(text_bytes "$ROLE_TEXT") + $(text_bytes "$NORMAL_TEXT") + $(text_bytes "$WATCH_TEXT") \
          + $(text_bytes "$CLEAN_TEXT") + $(text_bytes "$WARN_TEXT") + $(text_bytes "$RESUME_TEXT") + $(line_bytes "$RULES_LINE") + $(line_bytes "$QUIZ_LINE") ))
}
calc_fixed

# The state block must keep at least its pointer line. Cuts, in order, while
# fixed + pointer is over the CAP: 1 auto resume body, 2 the WATCH line,
# 3 worktree rows (last, W9).
ptr_bytes=0
if [ -f "$STATE_DIR/agent_state.txt" ]; then
  ptr_n=$(count_lines "$STATE_DIR/agent_state.txt")
  [ "${ptr_n:-0}" -gt 0 ] && ptr_bytes=$(line_bytes "agent_state.txt: $ptr_n lines, read it now (S8)")
fi

# 0. the WORKING BRANCH line (about 150 bytes) gives way to a short form when it would leave the state block
# less than its header plus the truncated marker.
if [ -n "${wb_name:-}" ] && [ -n "$ptr_bytes" ] && [ "$ptr_bytes" -gt 0 ] \
   && [ $(( CAP - fixed )) -lt $(( ptr_bytes + $(line_bytes "  (truncated, read the file)") )) ] \
   && printf '%s' "$WATCH_TEXT" | grep -q '^WORKING BRANCH: '; then
  WATCH_TEXT=$(printf '%s' "$WATCH_TEXT" | sed -E 's/^WORKING BRANCH: .*$/WORKING BRANCH: git switch '"$wb_name"' at a quiet point/'; printf 'X'); WATCH_TEXT=${WATCH_TEXT%X}
  calc_fixed
fi

# 1. auto resume: header plus one pointer line.
if [ -n "$RESUME_TEXT" ] && [ $(( fixed + ptr_bytes )) -gt "$CAP" ]; then
  RESUME_TEXT="=== auto resume ===
(cut to fit, run agent-resume.sh)
"
  calc_fixed
fi

# 2b. WATCH line: short forms, the command part is never cut: first without the "(<names>)" list.
if [ -n "$WATCH_TEXT" ] && [ $(( fixed + ptr_bytes )) -gt "$CAP" ]; then
  WATCH_TEXT=$(printf '%s' "$WATCH_TEXT" | sed 's/ tasks to watch ([^)]*)\./ tasks to watch./'; printf 'X'); WATCH_TEXT=${WATCH_TEXT%X}
  calc_fixed
fi
# still over: PLUGIN/bin/... for the plugin path (the PLUGIN: field of the PROJECT line names it),
# first in the CLEANUP table pointer, then, last, in the WATCH command
if [ -n "$CLEAN_TEXT" ] && [ $(( fixed + ptr_bytes )) -gt "$CAP" ]; then
  w_head=${CLEAN_TEXT%%"$PLUGIN_ROOT/bin/"*}
  if [ "$w_head" != "$CLEAN_TEXT" ]; then
    w_tail=${CLEAN_TEXT#*"$PLUGIN_ROOT/bin/"}
    CLEAN_TEXT="${w_head}PLUGIN/bin/${w_tail}"
    calc_fixed
  fi
fi
if [ -n "$WATCH_TEXT" ] && [ $(( fixed + ptr_bytes )) -gt "$CAP" ]; then
  w_head=${WATCH_TEXT%%"$PLUGIN_ROOT/bin/"*}; w_tail=${WATCH_TEXT#*"$PLUGIN_ROOT/bin/"}
  WATCH_TEXT="${w_head}PLUGIN/bin/${w_tail}"
  calc_fixed
fi
# then the same short form in the AGENT FILES (and relief) lines of the normal part
if [ $(( fixed + ptr_bytes )) -gt "$CAP" ] && [ "${NORMAL_TEXT#*"$PLUGIN_ROOT/bin/"}" != "$NORMAL_TEXT" ]; then
  while [ "${NORMAL_TEXT#*"$PLUGIN_ROOT/bin/"}" != "$NORMAL_TEXT" ]; do
    w_head=${NORMAL_TEXT%%"$PLUGIN_ROOT/bin/"*}; w_tail=${NORMAL_TEXT#*"$PLUGIN_ROOT/bin/"}
    NORMAL_TEXT="${w_head}PLUGIN/bin/${w_tail}"
  done
  calc_fixed
fi
# still over: the AGENT FILES line in its short form (it is never dropped)
if [ $(( fixed + ptr_bytes )) -gt "$CAP" ] && printf '%s' "$NORMAL_TEXT" | grep -q '^AGENT FILES: still on the code branch'; then
  NORMAL_TEXT=$(printf '%s' "$NORMAL_TEXT" | sed 's|^AGENT FILES: still on the code branch.*$|AGENT FILES: not moved; PLUGIN/bin/agent-file.sh files move (the owner decides)|'; printf 'X')
  NORMAL_TEXT=${NORMAL_TEXT%X}
  calc_fixed
fi

# 3. worktree rows, last, dropped from the end; the header keeps the real count.
if [ $(( fixed + ptr_bytes )) -gt "$CAP" ]; then
  wt_line=$(printf '%s' "$NORMAL_TEXT" | awk '/^agent_worktree.txt: /{print NR; exit}')
  # the rows are the indented lines right under the header; a line after them (AGENT FILES) is kept, not counted
  wt_rows=$(printf '%s' "$NORMAL_TEXT" | awk -v s="${wt_line:-0}" 'NR>s && /^  /{n++; next} NR>s{exit} END{print n+0}')
  if [ -n "$wt_line" ] && [ "$wt_rows" -gt 0 ]; then
    wt_orig=$NORMAL_TEXT; wt_keep=$wt_rows
    while [ "$wt_keep" -gt 0 ]; do
      wt_keep=$(( wt_keep - 1 ))
      NORMAL_TEXT=$(printf '%s' "$wt_orig" | head -n $(( wt_line + wt_keep )); \
        printf '  (%s more: agent_worktree.txt)\n' $(( wt_rows - wt_keep )); \
        printf '%s' "$wt_orig" | tail -n +$(( wt_line + wt_rows + 1 )); printf 'X'); NORMAL_TEXT=${NORMAL_TEXT%X}
      calc_fixed
      [ $(( fixed + ptr_bytes )) -le "$CAP" ] && break
    done
  fi
fi
# 4. still over with every row gone (a long human-direct role text): the AGENT FILES reminder goes, the very last
# cut; every start repeats it until files move, so the next roomier start shows it again
if [ $(( fixed + ptr_bytes )) -gt "$CAP" ] && printf '%s' "$NORMAL_TEXT" | grep -q '^AGENT FILES: '; then
  NORMAL_TEXT=$(printf '%s' "$NORMAL_TEXT" | grep -v '^AGENT FILES: '; printf 'X'); NORMAL_TEXT=${NORMAL_TEXT%X}
  calc_fixed
fi

budget=$(( CAP - fixed )); [ "$budget" -lt 0 ] && budget=0

printf '%s' "$ROLE_TEXT"
printf '%s' "$NORMAL_TEXT"
printf '%s' "$WATCH_TEXT"
printf '%s' "$CLEAN_TEXT"
printf '%s' "$WARN_TEXT"
print_state_block "$budget"
printf '%s' "$RESUME_TEXT"
printf '%s\n' "$RULES_LINE"
printf '%s\n' "$QUIZ_LINE"
by_hand && print_rules_block
exit 0
