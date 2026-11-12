#!/usr/bin/env bash
# agent-file.sh — the only way to write agent_*.txt. No agent, no tokens, one format.
#
#   agent-file.sh todo add  "<name>" "<size>" "<what>" [est_minutes] [by]  -> agent_todo.txt (by defaults to "main")
#   agent-file.sh todo done "<name>" ["<result>"] [--work <m>] [--wait <m>] [--bounces <n>] [--workers <n>]
#                 [--mock yes|no] [--lane fast|full] [--type <t>] [--tests <n>] [--adds <n>]
#                 [--merge <commit> | --range <a>..<b>]       -> line moves to agent_completed.txt as one data line
#   agent-file.sh todo drop "<name>" "<reason>"               -> line moves to agent_completed.txt as: date | name | what | est <n>m actual - | dropped: <reason>
#   agent-file.sh idea add  "<text>"                          -> agent_ideas.txt
#   agent-file.sh idea list                                   -> print agent_ideas.txt, numbered (cat -n)
#   agent-file.sh idea rm   <n>                                -> remove line n from agent_ideas.txt
#   agent-file.sh worktree set "<path>" "<module>" "<status>" -> agent_worktree.txt (add or replace)
#   agent-file.sh worktree rm  "<path>"                       -> agent_worktree.txt
#   agent-file.sh helper-task "<Task Name>"                   -> the task of THIS human-direct Helper session: its name becomes "<repo> Helper - <Task Name>"
#   agent-file.sh show                                        -> print all four files
#   agent-file.sh time                                        -> table: name est work wait clock ratio (agent_completed.txt)
#   agent-file.sh backfill [--dry-run]                        -> old lines: take work and wait from the text of each line
#   agent-file.sh backfill <name> [--dry-run] [--force] <todo done options>   -> set the data of one finished line
#   agent-file.sh data [--what] [<repo path>...]              -> table: one row per finished task, every repo on this machine
#   agent-file.sh estimate --lane fast|full --mock yes|no --type <t> [--name <name>] "<what>"   -> work minutes, range, like tasks
#   agent-file.sh backtest [--tasks]                          -> the estimator against the rubric and the todo est, rolling
#   agent-file.sh retrain [--force]                           -> learn agent_estimate.txt when 30 tasks, then once a week
#   agent-file.sh eta <name> [--step <n>] [--work-so-far <m>] [--wait <m>]    -> one line: work left, done around, owner needed next
#   agent-file.sh todo wait "<name>" on <mock|question|review|hold|queue> ["<note>"]  -> the todo line starts a wait
#   agent-file.sh todo wait "<name>" off                      -> the wait closes; its minutes join "waited <m>m"
#   agent-file.sh todo where "<name>" <machine> ["<worktree path>"]   -> the todo line says where it runs
#   agent-file.sh park add "<question>" ["<task>"] [--sub "<line>"] [--why "<text>"] [--evidence "<text>"]
#                 [--fact "<key>: <value>"]... [--options "A text|B text"] [--rec <letter or option text>]
#                                                             -> agent_state.txt: PARKED: <question> | <task> | since <date> | sub .. | fact .. | option A: .. | rec A
#   agent-file.sh park list                                   -> the PARKED lines, numbered
#   agent-file.sh park rm <n>                                 -> remove the n-th PARKED line
#   agent-file.sh park rm --id <id>                           -> remove the PARKED line with that id (the id `questions` gives)
#   agent-file.sh questions [--self] [--json]                 -> every question that waits on the owner ("show question")
#   agent-file.sh questions [--self] --page <file>            -> write the answer page, its map, and the "QUESTIONS PAGE:" line
#   agent-file.sh questions --url <url>                       -> set the published url on the "QUESTIONS PAGE:" line
#   agent-file.sh questions answer <id> "<answer>"            -> close one question (parked: line goes; todo: wait closes; QUESTION: gets "ANSWER:")
#   agent-file.sh worker on <n> "<slice>"                     -> agent_state.txt: WORKER <n>: <slice> | since <date> (replaces worker n)
#   agent-file.sh worker off <n>                              -> remove WORKER <n>
#   agent-file.sh board [--self]                              -> the table of everything open ("show todo"); --self: this session's task only
#
# todo done: every option is optional; a number is a whole number, 0 or more. "<result>" is not stored.
#   work = agent minutes. wait = minutes spent waiting (mock gate, owner, suite slot). Never mixed.
#   <t> is one of: page server script docs cloud app data mixed.
#   est comes from the todo line. clock = minutes from "opened" to now. repo = folder name of the main repo.
#   files and lines (lines = added + deleted) are counted only when asked, in the main repo:
#     --merge <commit>   git diff --shortstat <commit>^1 <commit>    what the merge brought in
#     --range <a>..<b>   git diff --shortstat <merge-base a b> <b>   what b changed since it left a
#   Neither given: files=- lines=- and "not counted" is printed. Both given, or a commit git does not know: refused.
#   A bad option is refused: one line on stderr that names it, exit 1, nothing moves.
#   It prints "todo done: <name>" and "TIME DATA: <n> of 30" (finished tasks that have a work number).
#   Then the retrain, only when due: one line "estimate retrain: ...", never the table. A failure never stops todo done.
#
# The line in agent_completed.txt (keys in this order, "-" when not known):
#   <date> | <name> | <what> | data repo=<r> type=<t> lane=<l> mock=<yes|no> est=<m> work=<m> wait=<m> clock=<m> bounces=<n> workers=<n> files=<n> lines=<n> tests=<n> adds=<n>
#   An old line ("est <n>m actual <n>m") has no data block.
#
# time: ratio = work / est, one decimal; "-" when work or est is missing. An old line is est + clock, never work.
#   Dropped lines are skipped.
#
# backfill (no name): every old line (no data block, not dropped) is read for its work:
#   "work <a> + bounce <b> = <c>" gives work <c>; else the first "work <n>" gives work <n>; "wait <n>" gives wait.
#   Letter case does not matter, the "m" after a number is optional. "est <n>m actual <n>m" is not scanned.
#   A work number found: the line gets a data block (est and clock from the old field, other keys "-"), its text stays.
#   No work number: the line stays. Prints "took: <name> work <n> wait <n|->" or "skipped: <name> (<why>)",
#   then "backfill: took <n>, skipped <n>". --dry-run prints the same and writes nothing. One atomic write.
# backfill <name>: the LAST line of that name that is not dropped; only that line changes, its text stays.
#   Same options and same refusals as todo done. An old line: est and clock from its old field, the facts given.
#   A line that has data is refused unless --force: then the facts given replace, every other key keeps its value.
#   Refused (one line on stderr, exit 1, nothing written): no such line, only a dropped line, no fact given.
#   Prints "wrote: <the new line>" and "TIME DATA: <n> of 30". --dry-run prints "would write: <the new line>" only.
#
# data: read-only. Columns: repo name date type lane mock est work wait clock bounces workers files lines tests adds.
#   An old line gives est and clock, "-" elsewhere. The repo column is the data block's repo, else the folder name.
#   Repos, in this order, the same repo (real path) once:
#     1. this repo
#     2. the keys of "territories" in world.json in the city home ($AGENT_CITY_HOME, default ~/.claude/agent-city);
#        a key "<repo>/.git" names <repo>, any other key is passed over; no python3 or a bad file: passed over
#     3. the lines of joined-repos.txt in the city home (absolute paths; blank lines and "#" comments are passed over)
#     4. the paths given as arguments
#   It reads only <repo>/agent_completed.txt of another repo and writes nothing there.
#   No such file or folder: one line "skipped ..." on stderr, exit stays 0.
#   --what adds one last column, what: the text between the name and the data block ("-" when empty).
#
# estimate, backtest, retrain: the work is done by agent_estimate.py (python3), from the table of data --what.
#   Read requirements/estimate.md. An estimate = agent work minutes, from what is known before dispatch only.
#   estimate: read only. First line "estimate: <m>m work, range <lo>-<hi>m (<estimator|rubric> v<n>, <N> past tasks)",
#     then up to 3 "like <name>: <m>m work (...)" lines. A fact known only after the task (--work --wait --clock --est
#     --bounces --workers --files --lines --tests --adds), a missing or bad --lane --mock --type, or no what:
#     refused, one line on stderr that names it, exit 1, nothing on stdout.
#   backtest: read only. Each task with 10 tasks before it is estimated from those only; the estimator, the rubric
#     and the todo est are scored (median error, within 30%, in range); winner = estimator only when strictly better.
#     --tasks adds one row per tested task. Fewer than 11 tasks: "backtest: <N> tasks, needs at least 11".
#   retrain: due at 30 tasks, then once a week with 1+ new task (--force skips the week, never the 30). Writes agent_estimate.txt
#     (JSON, atomic) in the project root: v1 = the setting picked from all tasks and its backtest; a later check keeps
#     the new version only when its error on the new tasks is strictly lower. Prints the table and one verdict line.
#
# eta: one line, nothing written. est comes from the open todo line <name>. step = how far the work is, 0 to 7
#   (7 = done; no step = 0). All minutes round up.
#   work so far = --work-so-far, else est x step / 7.  work left = est - work so far.
#   Over the estimate (work so far >= est): work left = work so far x (7 - step) / step, the pace so far.
#   Over the estimate with no step: refused, the line names --step.
#   done = now + work left + --wait. --wait is waiting still ahead; it is said in the line, never counted as work.
#   owner needed next: "mock ready" when the todo text says mock (not "no mock") and step <= 2, at
#   now + work left x (3 - step) / (7 - step) (the wait is not added); else "review", at the done time.
#   A time that is not today is shown as "<HH:MM> tomorrow" or "<HH:MM> on <YYYY-MM-DD>".
#
# helper-task: only a human-direct Helper (role second, role_read in agent-roots.sh) may set a task, and only for its own
#   session: the id is $CLAUDE_CODE_SESSION_ID (letters, digits, "_" and "-"). Two Helpers in one folder never share a name.
#   Refused (exit 1, one line on stderr that says why, nothing written): any other role (main, takeover, closed, spawned),
#   no session id, a name with no English word left. No argument: usage, exit 2.
#   The name is cleaned: every character that is not an ASCII letter, digit or hyphen becomes a space; hyphens at the
#   ends of a word go; role words go, any letter case (the pair "Task Manager", then every "Helper", "Manager", "Agent";
#   "Task" alone stays): name the work, not the role; the first 4 words are kept, each with a capital first letter (the
#   rest as typed); then whole words leave from the end while it is over 40 characters (one word alone is cut to 40).
#   Use 2-4 English words, Title Case.
#   The task is one line in "<git dir of the project>/agent_helper_task_<session id>" (atomic; never in a work tree).
#   Files agent_helper_task_* and agent_helper_title_* in that folder older than 30 days are deleted.
#   Field 3 of this folder's human-direct line in agent_worktree.txt becomes "task: <Task Name>" (the line is added when
#   there is none; fields 1, 2, 4 and every other line stay). One atomic write.
#   Prints one line: helper task: <Task Name> -> "<repo> Helper - <Task Name>" from the human's next prompt
#   The title shows from the human's next prompt: bin/agent-name.sh --prompt (UserPromptSubmit) prints it once per change.
#
# todo wait, todo where: the todo line is edited in place (one atomic write); the other fields keep their place,
#   a new field goes at the end, a field set again is replaced, once.
#   todo wait on: field " | waiting <kind> since <YYYY-MM-DD HH:MM>" (+ ": <note>"). Already waiting: that wait is closed first.
#   todo wait off: closes the open wait: " | waited <m>m" = the sum of every closed wait; the "waiting" field goes.
#   The closed wait also adds its minutes inside the current stage (from max(wait since, stage since) to now) to
#   " | waited in stage <n>m" (replaced in place, once; added at the end when new; never on a line with no stage field).
#   todo where: field " | on <machine>[ <path>]".
#   Refused (one line on stderr, exit 1, nothing written): no todo line of that name, a kind not in the list, off when not
#   waiting, no on|off, a machine with a space, " | " or a line break in a note or a path.
#
# todo stage <name> <stage> [<i>/<m>]: the stage field of the todo line, " | stage <stage>[ <i>/<m>] since <date>" (one atomic
#   write, replaced in place, once). A new <i>/<m> of the same stage keeps its "since" (todo line and STAGE line); a new
#   stage name sets since = now and drops the " | waited in stage <n>m" field. The stages: brief register mock tests workers verify push report e2e merge. <i>/<m> only
#   with workers (i of m slices done, whole numbers, m >= 1, 0 <= i <= m). The same value again: nothing is written.
#   In a work tree (the git toplevel of the cwd is not the main repo) it also writes "STAGE <name>: <stage>[ <i>/<m>] | since
#   <date>" into that folder's agent_state.txt (one line per name, replaced in place, every other line kept byte for byte).
#   No todo line of that name: in a work tree only the STAGE line is written (exit 0); in the main repo: refused.
#   Refused (one line on stderr, exit 1, nothing written): no name, no stage, an unknown stage, <i>/<m> with another stage,
#   a bad <i>/<m>, too many arguments.
#
# park, worker: lines of agent_state.txt in the folder of this session (the git toplevel of the cwd), never the main repo's
#   unless this is it. Every other line is kept byte for byte; park rm and worker on|off are one atomic write.
#   park add: task defaults to the name of that folder. worker on: replaces the line of that worker.
#   Refused (one line on stderr, exit 1, nothing written): empty text, " | " or a line break in it, n not a whole number
#   from 1, no such n, an unknown verb.
#
# questions: the work is done by agent_questions.py (python3); the template is agent-questions-page.html.
#   Read only, except --page (page + map + one "QUESTIONS PAGE: <url> | <page> | <map> | since <date>" line in the own
#   agent_state.txt, url kept), --url and answer. Sources, order, ids, fields and the page: tests/test_agent_questions.py.
#   An open "QUESTION: <text>" line of an agent_state.txt is answered by a later line "ANSWER: <text>" (before the next
#   QUESTION: line and the next "=== " header). park add: --why and --evidence are facts; --fact keeps its key; --options
#   gives letters A to H (at most 8); --rec is a letter or an option text (with no --options: a fact).
#   Refused (one line on stderr, exit 1, nothing written): an empty value, " | " or a line break in a value, an unknown option,
#   a flag with no value, a bad --fact, an empty or ninth option, a --rec that is no option, an id that is not listed.
#
# board: read only. One markdown table of everything open (or one line "无" / "none"), then note lines; the work is done by
#   agent_board.py (python3). The columns and words follow `language` in agent.conf (zh, else en). --self: the session's own
#   task only. --watch [<sec>]: clear the screen and draw it again every <sec> seconds (whole number from 1; default
#   board_watch_sec in agent.conf, else the template bin/agent.conf.default) until Ctrl-C. Any other option: refused.
#
# AGENT_FAKE_NOW="YYYY-MM-DD HH:MM" replaces the machine clock (tests). Unset or empty: the machine clock.
# AGENT_FAKE_HOST replaces the machine name that board prints (tests). Unset: the short host name.
# Files live in the main repo, never in a worktree. Writes are atomic (tmp + mv).

set -eu
TIME_DATA_GOAL=30
DATA_TYPES="page server script docs cloud app data mixed"
DATA_KEYS="repo type lane mock est work wait clock bounces workers files lines tests adds"
OPT_CMD="todo done"   # the prefix of a refusal from done_opts; backfill sets it to "backfill"
. "$(dirname "$0")/agent-roots.sh"
roots_read
ROOT="$PROJECT_ROOT"
TODO="$ROOT/agent_todo.txt"; DONE="$ROOT/agent_completed.txt"; IDEAS="$ROOT/agent_ideas.txt"; WT="$ROOT/agent_worktree.txt"
NOW=${AGENT_FAKE_NOW:-$(date '+%Y-%m-%d %H:%M')}; WHO=${AGENT_ROLE:-main}
case "${1:-}" in data|eta|estimate|backtest|retrain|helper-task|board|park|worker|questions) ;; *) touch "$TODO" "$DONE" "$IDEAS" "$WT";; esac   # these only read (retrain writes agent_estimate.txt only; helper-task touches nothing before it is sure; park and worker write agent_state.txt only)

# the whole header comment block, whatever its length
usage() { awk 'NR > 1 { if (/^#/) print; else exit }' "$0"; exit 2; }
need()  { [ $# -ge "$1" ] || usage; }
append(){ printf '%s\n' "$2" >> "$1"; }
# drop lines whose first field (before " | ") equals $2 from file $1
drop()  { awk -v k="$2" -F' \\| ' '$1 != k' "$1" > "$1.tmp" && mv "$1.tmp" "$1"; }
first() { awk -v k="$2" -F' \\| ' '$1 == k {print; exit}' "$1"; }
# "YYYY-MM-DD HH:MM" -> epoch seconds, BSD date first (macOS), GNU date as fallback
to_epoch() { date -j -f '%Y-%m-%d %H:%M' "$1" +%s 2>/dev/null || date -d "$1" +%s 2>/dev/null || true; }

# --- small helpers (todo done, time; also for backfill, data, eta)
# a whole number, 0 or more
is_num() { case "$1" in ''|*[!0-9]*) return 1;; esac; return 0; }
# "<line>": ONE line on stderr, exit 1. Call it at the top level, before any file changes.
refuse() { echo "$1" >&2; exit 1; }
# folder name of a repo path (no spaces, so it stays one word in a data block)
repo_name() { basename "$1" | tr ' ' '_'; }
# minutes from "YYYY-MM-DD HH:MM" $1 to $2; nothing when a date does not read or $2 is before $1
minutes_between() {
  local o n
  o=$(to_epoch "$1"); n=$(to_epoch "$2")
  [ -n "$o" ] && [ -n "$n" ] && [ "$n" -ge "$o" ] && echo $(( (n - o) / 60 )) || true
}
# the data block as d_<key> variables: dreset sets them all to "-", dblock prints "data repo=... adds=..."
dreset() {
  d_repo=-; d_type=-; d_lane=-; d_mock=-; d_est=-; d_work=-; d_wait=-; d_clock=-
  d_bounces=-; d_workers=-; d_files=-; d_lines=-; d_tests=-; d_adds=-
}
dblock() {
  printf 'data repo=%s type=%s lane=%s mock=%s est=%s work=%s wait=%s clock=%s bounces=%s workers=%s files=%s lines=%s tests=%s adds=%s' \
    "$d_repo" "$d_type" "$d_lane" "$d_mock" "$d_est" "$d_work" "$d_wait" "$d_clock" \
    "$d_bounces" "$d_workers" "$d_files" "$d_lines" "$d_tests" "$d_adds"
}
# dkey "<line>" <key>: that key of the line's data block (can be "-"); nothing when the line has no block
dkey() {
  local w
  case "$1" in *' | data '*) ;; *) return 0;; esac
  for w in ${1##* | data }; do
    case "$w" in "$2="*) printf '%s' "${w#*=}"; return 0;; esac
  done
}
# old_num "<text>" est|actual: n of the first "est <n>m" / "actual <n>m" in the text
old_num() { printf '%s' "$1" | grep -o "$2 [0-9][0-9]*m" | head -1 | sed "s/$2 //;s/m//"; }
# est and clock (the old "actual") of an old completed line "... | est <n>m actual <n>m"
old_est()   { old_num "${1##* | }" est; }
old_clock() { old_num "${1##* | }" actual; }
# lines of agent_completed.txt that have a data block with a work number (dropped lines never count)
time_data() {
  awk '/[|] dropped: /{next} sub(/^.* [|] data /,"") && /(^| )work=[0-9]+( |$)/{n++} END{print n+0}' "$DONE"
}

# --- todo done options
want_num() { is_num "$2" || refuse "$OPT_CMD: $1 wants a whole number, 0 or more (got: $2)"; }
# want_in <option> <value> <word>...
want_in() {
  local o="$1" v="$2" w
  shift 2
  for w in "$@"; do [ "$w" = "$v" ] && return 0; done
  refuse "$OPT_CMD: $o is one of: $* (got: $v)"
}
# d_files, d_lines from git diff --shortstat <from> <to>; <value> is what the caller typed
git_count() {
  local opt="$1" st
  st=$(LC_ALL=C git -C "$ROOT" diff --shortstat "$3" "$4" -- 2>/dev/null) || refuse "$OPT_CMD: $opt: git does not know $2"
  set -- $(printf '%s\n' "$st" | awk '{for (i = 2; i <= NF; i++) {if ($i ~ /^file/) f = $(i-1); else if ($i ~ /^insertion/) a = $(i-1); else if ($i ~ /^deletion/) d = $(i-1)}} END{print f+0, a+d}')
  d_files=$1; d_lines=$2
}
# every option of todo done into d_*; refuses the first bad one. Nothing is written here.
done_opts() {
  local o v merge="" range="" a b base
  while [ $# -gt 0 ]; do
    o="$1"
    case "$o" in
      --work|--wait|--bounces|--workers|--tests|--adds|--mock|--lane|--type|--merge|--range) ;;
      *) refuse "$OPT_CMD: unknown option: $o";;
    esac
    [ $# -ge 2 ] || refuse "$OPT_CMD: $o needs a value"
    v="$2"; shift 2
    case "$o" in
      --work)    want_num "$o" "$v"; d_work=$v;;
      --wait)    want_num "$o" "$v"; d_wait=$v;;
      --bounces) want_num "$o" "$v"; d_bounces=$v;;
      --workers) want_num "$o" "$v"; d_workers=$v;;
      --tests)   want_num "$o" "$v"; d_tests=$v;;
      --adds)    want_num "$o" "$v"; d_adds=$v;;
      --mock)    want_in "$o" "$v" yes no; d_mock=$v;;
      --lane)    want_in "$o" "$v" fast full; d_lane=$v;;
      --type)    want_in "$o" "$v" $DATA_TYPES; d_type=$v;;
      --merge)   case "$v" in ''|-*) refuse "$OPT_CMD: --merge wants a commit (got: $v)";; esac; merge=$v;;
      --range)   range=$v;;
    esac
  done
  if [ -n "$merge" ] && [ -n "$range" ]; then refuse "$OPT_CMD: --merge and --range together; give one"; fi
  if [ -n "$merge" ]; then git_count --merge "$merge" "$merge^1" "$merge"; fi
  if [ -n "$range" ]; then
    case "$range" in *..*) ;; *) refuse "$OPT_CMD: --range wants <a>..<b> (got: $range)";; esac
    a=${range%%..*}; b=${range#*..}
    case "$a:$b" in :*|*:|-*|*:-*) refuse "$OPT_CMD: --range wants <a>..<b> (got: $range)";; esac
    base=$(git -C "$ROOT" merge-base "$a" "$b" 2>/dev/null) || refuse "$OPT_CMD: --range: git does not know $range"
    git_count --range "$range" "$base" "$b"
  fi
}

# --- backfill
# scan_num "<lower case text>" "<regex>": the last number of the first match of <regex>, as a word of its own
scan_num() { printf '%s' "$1" | grep -oE "(^|[^a-z])$2" | head -1 | grep -oE '[0-9]+$' || true; }
# backfill [--dry-run]: the text scan of every old line
backfill_text() {
  local dry="" a ln name text work wt took=0 skipped=0 tmp="$DONE.tmp"
  for a in "$@"; do
    case "$a" in --dry-run) dry=1;; *) refuse "backfill: unknown option: $a";; esac
  done
  [ -n "$dry" ] || : > "$tmp"
  while IFS= read -r ln || [ -n "$ln" ]; do
    if [ -n "$ln" ]; then
      name=${ln#* | }; name=${name%% | *}
      case "$ln" in
        *'| dropped: '*) echo "skipped: $name (dropped)"; skipped=$((skipped + 1));;
        *' | data '*)    echo "skipped: $name (already has data)"; skipped=$((skipped + 1));;
        *)
          text=${ln% | *}; text=${text#* | }; text=$(printf '%s' "${text#* | }" | tr 'A-Z' 'a-z')
          work=$(scan_num "$text" 'work +[0-9]+m? *[+] *bounces? +[0-9]+m? *= *[0-9]+')
          [ -n "$work" ] || work=$(scan_num "$text" 'work +[0-9]+')
          if [ -z "$work" ]; then
            echo "skipped: $name (no work number in the text)"; skipped=$((skipped + 1))
          else
            wt=$(scan_num "$text" 'wait +[0-9]+')
            dreset; d_repo=$(repo_name "$ROOT"); d_est=$(old_est "$ln"); d_clock=$(old_clock "$ln")
            d_est=${d_est:--}; d_clock=${d_clock:--}; d_work=$((10#$work)); d_wait=${wt:--}
            [ "$d_wait" = - ] || d_wait=$((10#$d_wait))
            ln="${ln% | *} | $(dblock)"
            echo "took: $name work $d_work wait $d_wait"; took=$((took + 1))
          fi;;
      esac
    fi
    [ -n "$dry" ] || printf '%s\n' "$ln" >> "$tmp"
  done < "$DONE"
  [ -n "$dry" ] || { [ "$took" -eq 0 ] && rm -f "$tmp" || mv "$tmp" "$DONE"; }
  echo "backfill: took $took, skipped $skipped"
}
# backfill <name> [--dry-run] [--force] <todo done options>: the facts of one finished line
backfill_name() {
  local name="$1" dry="" force="" has="" given="" i a k v n line new
  shift; OPT_CMD=backfill
  i=$#
  while [ "$i" -gt 0 ]; do   # --dry-run and --force may stand anywhere; the rest goes on to done_opts
    a=$1; shift; i=$((i - 1))
    case "$a" in --dry-run) dry=1;; --force) force=1;; *) set -- "$@" "$a";; esac
  done
  n=$(awk -v k="$name" -F' \\| ' '$2 == k && !/[|] dropped: /{n = NR} END{print n + 0}' "$DONE")
  if [ "$n" -eq 0 ]; then
    if awk -v k="$name" -F' \\| ' '$2 == k {f = 1} END{exit !f}' "$DONE"; then
      refuse "backfill: $name: only a dropped line has that name, nothing to set"
    fi
    refuse "no completed line named: $name"
  fi
  line=$(sed -n "${n}p" "$DONE")
  dreset
  done_opts "$@"
  case "$line" in *' | data '*) has=1;; esac
  [ -z "$has" ] || [ -n "$force" ] || refuse "backfill: $name already has data; --force replaces the facts you give"
  for k in type lane mock work wait bounces workers files lines tests adds; do
    eval "v=\$d_$k"; [ "$v" = - ] || given=1
  done
  [ -n "$given" ] || refuse "backfill: $name: no fact given (--work, --wait, --bounces, --workers, --mock, --lane, --type, --tests, --adds, --merge, --range)"
  if [ -n "$has" ]; then
    for k in $DATA_KEYS; do
      eval "v=\$d_$k"
      [ "$v" != - ] || { v=$(dkey "$line" "$k"); eval "d_$k=\${v:--}"; }
    done
  else
    d_repo=$(repo_name "$ROOT"); d_est=$(old_est "$line"); d_clock=$(old_clock "$line")
    d_est=${d_est:--}; d_clock=${d_clock:--}
  fi
  new="${line% | *} | $(dblock)"
  if [ -n "$dry" ]; then echo "would write: $new"; return 0; fi
  NEW="$new" awk -v n="$n" 'NR == n {print ENVIRON["NEW"]; next} {print}' "$DONE" > "$DONE.tmp" && mv "$DONE.tmp" "$DONE"
  echo "wrote: $new"
  echo "TIME DATA: $(time_data) of $TIME_DATA_GOAL"
}

# --- data
DATA_FMT='%-14s %-30s %-10s %-6s %-4s %-4s %5s %5s %5s %6s %7s %7s %5s %6s %5s %4s\n'
DATA_FMT_WHAT='%-14s %-30s %-10s %-6s %-4s %-4s %5s %5s %5s %6s %7s %7s %5s %6s %5s %4s %s\n'   # data --what: one more column
DATA_WHAT=
DATA_SEEN="
"
# dload "<line>": d_* from the data block of the line ("-" for a key it does not say)
dload() {
  local w k
  dreset
  for w in ${1##* | data }; do
    k=${w%%=*}
    case " $DATA_KEYS " in *" $k "*) eval "d_$k=\${w#*=}";; esac
  done
}
# the repo folders named by the keys of "territories" in world.json: "<repo>/.git" gives <repo>
world_repos() {
  [ -f "$1" ] || return 0
  command -v python3 >/dev/null 2>&1 || { echo "note: no python3, so $1 is not read" >&2; return 0; }
  python3 -c '
import json, sys
t = json.load(open(sys.argv[1])).get("territories")
for k in (t if isinstance(t, dict) else []):
    if k.endswith("/.git") and len(k) > 5:
        print(k[:-5])
' "$1" 2>/dev/null || echo "note: $1 is not read (not valid)" >&2
}
# data_repo <path>: the rows of one repo, once
data_repo() {
  local rp ln name date repo rest what
  rp=$(cd "$1" 2>/dev/null && pwd -P) || { echo "skipped: no such folder: $1" >&2; return 0; }
  case "$DATA_SEEN" in *"
$rp
"*) return 0;; esac
  DATA_SEEN="$DATA_SEEN$rp
"
  [ -f "$rp/agent_completed.txt" ] || { echo "skipped: no agent_completed.txt in $1" >&2; return 0; }
  repo=$(repo_name "$rp")
  while IFS= read -r ln || [ -n "$ln" ]; do
    case "$ln" in ''|*'| dropped: '*) continue;; esac
    name=${ln#* | }; name=${name%% | *}; date=${ln%% | *}
    case "$ln" in
      *' | data '*) dload "$ln";;
      *) dreset; d_est=$(old_est "$ln"); d_clock=$(old_clock "$ln");;
    esac
    [ "${d_repo:--}" != - ] || d_repo=$repo
    if [ -n "$DATA_WHAT" ]; then
      # what = the text between the name and the data block (an old line: the text before its last field)
      rest=${ln#* | }; rest=${rest#* | }
      case "$ln" in
        *' | data '*) case "$rest" in *' | data '*) what=${rest% | data *};; *) what=;; esac;;
        *) case "$rest" in *' | '*) what=${rest% | *};; *) what=;; esac;;
      esac
      printf "$DATA_FMT_WHAT" "${d_repo// /_}" "${name// /_}" "${date// /_}" "${d_type:--}" "${d_lane:--}" "${d_mock:--}" \
        "${d_est:--}" "${d_work:--}" "${d_wait:--}" "${d_clock:--}" "${d_bounces:--}" "${d_workers:--}" \
        "${d_files:--}" "${d_lines:--}" "${d_tests:--}" "${d_adds:--}" "${what:--}"
    else
      printf "$DATA_FMT" "${d_repo// /_}" "${name// /_}" "${date// /_}" "${d_type:--}" "${d_lane:--}" "${d_mock:--}" \
        "${d_est:--}" "${d_work:--}" "${d_wait:--}" "${d_clock:--}" "${d_bounces:--}" "${d_workers:--}" \
        "${d_files:--}" "${d_lines:--}" "${d_tests:--}" "${d_adds:--}"
    fi
  done < "$rp/agent_completed.txt"
}
# data [--what] [<repo path>...]
data_run() {
  local city="${AGENT_CITY_HOME:-${HOME:-}/.claude/agent-city}" p list a i=$#
  DATA_WHAT=
  while [ "$i" -gt 0 ]; do   # --what may stand anywhere; the rest are repo paths
    a=$1; shift; i=$((i - 1))
    case "$a" in --what) DATA_WHAT=1;; *) set -- "$@" "$a";; esac
  done
  if [ -n "$DATA_WHAT" ]; then
    printf "$DATA_FMT_WHAT" repo name date type lane mock est work wait clock bounces workers files lines tests adds what
  else
    printf "$DATA_FMT" repo name date type lane mock est work wait clock bounces workers files lines tests adds
  fi
  data_repo "$ROOT"
  list=$(world_repos "$city/world.json")
  while IFS= read -r p; do [ -z "$p" ] || data_repo "$p"; done <<< "$list"
  if [ -f "$city/joined-repos.txt" ]; then
    while read -r p || [ -n "$p" ]; do
      case "$p" in /*) data_repo "$p";; esac
    done < "$city/joined-repos.txt"
  fi
  for p in "$@"; do data_repo "$p"; done
}

# --- estimate, backtest, retrain
# est_py <estimate|backtest|retrain> [option...]: the table of data --what into agent_estimate.py (python3 only).
# The model file is the project root's agent_estimate.txt, today is the date of $NOW (AGENT_FAKE_NOW works).
est_py() {
  local cmd="$1" rows
  shift
  command -v python3 >/dev/null 2>&1 || refuse "$cmd: python3 is needed and was not found"
  rows=$(data_run --what 2>/dev/null) || true
  python3 "$(dirname "$0")/agent_estimate.py" "$cmd" "$ROOT/agent_estimate.txt" "${NOW%% *}" "$@" <<< "$rows"
}
# the retrain after todo done: one verdict line only when it ran; any failure is swallowed (one short line)
retrain_auto() {
  local out rc=0
  out=$(est_py retrain --auto 2>/dev/null) || rc=$?
  if [ "$rc" -ne 0 ]; then echo "estimate retrain: failed"
  elif [ -n "$out" ]; then printf '%s\n' "$out"
  fi
  return 0
}

# the sweep after the last task closes: agent_todo.txt has no non-blank line, agent_worktree.txt has no
# working or final line and no human-direct line, and this is the main manager (or a takeover). Prints the
# sweep's --short lines. Any failure of it is swallowed: it never changes the exit code of todo done.
sweep_after_last_task() {
  local busy
  if grep -q '[^[:space:]]' "$TODO" 2>/dev/null; then return 0; fi
  busy=$(awk -F' \\| ' '$3 == "working" || $3 == "final" || $2 == "task manager, human-direct" { n++ } END { print n + 0 }' "$WT" 2>/dev/null) || return 0
  [ "${busy:-0}" -eq 0 ] || return 0
  role_read
  case "$role" in main|takeover) ;; *) return 0;; esac
  "$PLUGIN_ROOT/bin/agent-cleanup.sh" --apply --short 2>/dev/null </dev/null || true
  return 0
}

# --- eta
# epoch seconds -> "YYYY-MM-DD HH:MM", BSD date first (macOS), GNU date as fallback
from_epoch() { date -r "$1" '+%Y-%m-%d %H:%M' 2>/dev/null || date -d "@$1" '+%Y-%m-%d %H:%M'; }
# eta_when <epoch>: "HH:MM", "HH:MM tomorrow" or "HH:MM on YYYY-MM-DD" (needs $today and $tomorrow of eta_run)
eta_when() {
  local s d
  s=$(from_epoch "$1"); d=${s%% *}
  if [ "$d" = "$today" ]; then echo "${s#* }"
  elif [ "$d" = "$tomorrow" ]; then echo "${s#* } tomorrow"
  else echo "${s#* } on $d"; fi
}
# eta <name> [--step <n>] [--work-so-far <m>] [--wait <m>]
eta_run() {
  local name="$1" step="" wsf="" wt=0 o v line est s left mock_m="" now_e noon who who_e done_e today tomorrow msg
  shift; OPT_CMD=eta
  while [ $# -gt 0 ]; do
    o=$1
    case "$o" in --step|--work-so-far|--wait) ;; *) refuse "eta: unknown option: $o";; esac
    [ $# -ge 2 ] || refuse "eta: $o needs a value"
    v=$2; shift 2
    case "$o" in
      --step)        is_num "$v" && [ $((10#$v)) -le 7 ] || refuse "eta: --step is a whole number from 0 to 7 (got: $v)"; step=$((10#$v));;
      --work-so-far) want_num "$o" "$v"; wsf=$((10#$v));;
      --wait)        want_num "$o" "$v"; wt=$((10#$v));;
    esac
  done
  line=; [ ! -f "$TODO" ] || line=$(first "$TODO" "$name")
  [ -n "$line" ] || refuse "no todo line named: $name"
  est=$(old_num "$line" est)
  [ -n "$est" ] || refuse "eta: no estimate on the todo line: $name"
  est=$((10#$est)); s=${step:-0}
  if [ -z "$wsf" ]; then left=$(( (est * (7 - s) + 6) / 7 ))
  elif [ "$wsf" -lt "$est" ]; then left=$((est - wsf))
  elif [ "$s" -ge 1 ]; then left=$(( (wsf * (7 - s) + s - 1) / s ))
  else refuse "eta: --work-so-far is over the estimate, so --step (1 to 7) is needed for the pace so far"
  fi
  case "$(printf '%s\n' "$line" | awk -F' \\| ' '{print $3}' | tr 'A-Z' 'a-z')" in
    *'no mock'*) ;;
    *mock*) if [ "$s" -le 2 ]; then mock_m=$(( (left * (3 - s) + 6 - s) / (7 - s) )); fi;;
  esac
  now_e=$(to_epoch "$NOW"); today=${NOW%% *}; noon=$(to_epoch "$today 12:00")
  [ -n "$now_e" ] && [ -n "$noon" ] || refuse "eta: cannot read the time: $NOW"
  tomorrow=$(from_epoch $((noon + 86400))); tomorrow=${tomorrow%% *}
  done_e=$((now_e + (left + wt) * 60))
  if [ "$wt" -gt 0 ]; then msg="about $left min of work left and $wt min of waiting"; else msg="about $left min of work left"; fi
  if [ -n "$mock_m" ]; then who="mock ready"; who_e=$((now_e + mock_m * 60)); else who=review; who_e=$done_e; fi
  echo "$msg, done around $(eta_when "$done_e"); owner needed next: $who about $(eta_when "$who_e")"
}

# --- helper-task
# helper_clean "<text>": the Task Name (see the header), nothing when no English word is left
helper_clean() {
  local words
  words=$(printf '%s' "$1" | LC_ALL=C tr -c 'A-Za-z0-9-' ' ')   # only letters, digits, hyphens and spaces remain
  LC_ALL=C awk -v s="$words" 'BEGIN {
    m = split(s, raw, " "); k = 0
    for (i = 1; i <= m; i++) {
      w = raw[i]; sub(/^-+/, "", w); sub(/-+$/, "", w)
      if (w != "") a_[++k] = w
    }
    # role words go, any letter case: the pair "task manager" first, then "helper", "manager", "agent"
    j = 0
    for (i = 1; i <= k; i++) {
      if (tolower(a_[i]) == "task" && i < k && tolower(a_[i + 1]) == "manager") { i++; continue }
      b_[++j] = a_[i]
    }
    n = 0
    for (i = 1; i <= j && n < 4; i++) {
      lw = tolower(b_[i])
      if (lw == "helper" || lw == "manager" || lw == "agent") continue
      w_[++n] = toupper(substr(b_[i], 1, 1)) substr(b_[i], 2)
    }
    out = ""
    for (i = 1; i <= n; i++) out = out (i > 1 ? " " : "") w_[i]
    while (length(out) > 40 && n > 1) {
      n--; out = ""
      for (i = 1; i <= n; i++) out = out (i > 1 ? " " : "") w_[i]
    }
    if (length(out) > 40) out = substr(out, 1, 40)
    print out
  }'
}
# helper_task "<text>": validate everything first (refuse = exit 1, nothing written), then write
helper_task() {
  local sid="${CLAUDE_CODE_SESSION_ID:-}" task f tmp repo
  role_read
  [ "$role" = second ] || refuse "helper-task: only a human-direct Helper (a second session) can set a task; this session is: $role${AGENT_ROLE:+ ($AGENT_ROLE)}"
  case "$sid" in
    ''|*[!A-Za-z0-9_-]*) refuse "helper-task: no usable session id (CLAUDE_CODE_SESSION_ID is empty or has other characters than letters, digits, _ and -)";;
  esac
  task=$(helper_clean "$1")
  [ -n "$task" ] || refuse "helper-task: no English word left in that name; name the work, not the role; use 2-4 English words, Title Case"
  mkdir -p "$PROJECT_GITDIR" 2>/dev/null || refuse "helper-task: cannot write in $PROJECT_GITDIR"
  f="$PROJECT_GITDIR/agent_helper_task_$sid"; tmp="$f.tmp.$$"
  { printf '%s\n' "$task" > "$tmp" && mv "$tmp" "$f"; } 2>/dev/null || { rm -f "$tmp"; refuse "helper-task: cannot write $f"; }
  find "$PROJECT_GITDIR" -maxdepth 1 -type f \( -name 'agent_helper_task_*' -o -name 'agent_helper_title_*' \) -mtime +30 -exec rm -f {} + 2>/dev/null || true
  touch "$WT"
  awk -F' \\| ' -v p="$PROJECT_CWD" -v t="task: $task" -v now="$NOW" 'BEGIN { OFS = " | " }
    $1 == p && $2 == "task manager, human-direct" { $3 = t; seen = 1 }
    { print }
    END { if (!seen) print p, "task manager, human-direct", t, "since " now }' "$WT" > "$WT.tmp" && mv "$WT.tmp" "$WT"
  repo=$(basename "$PROJECT_ROOT")
  echo "helper task: $task -> \"$repo Helper - $task\" from the human's next prompt"
}

# --- todo wait, todo where
# bad_text "<text>": true when it holds " | " or a line break (it would break the line it goes into)
bad_text() {
  case "$1" in *' | '*|*$'\n'*|*$'\r'*) return 0;; esac
  return 1
}
# todo_wait <name> on <kind> ["<note>"] | todo_wait <name> off
todo_wait() {
  local name="${1:-}" verb="${2:-}" kind note line open since m closed=0 new="" ssince="" ins=0 hasst=0 from
  [ -n "$name" ] || refuse "todo wait: needs a todo name"
  line=$(first "$TODO" "$name")
  [ -n "$line" ] || refuse "no todo line named: $name"
  open=$(printf '%s\n' "$line" | awk -F' \\| ' '{ for (i = 4; i <= NF; i++) if ($i ~ /^waiting /) { print $i; exit } }')
  case "$verb" in
    on)
      kind="${3:-}"
      case "$kind" in
        mock|question|review|hold|queue) ;;
        *) refuse "todo wait: the kind is one of: mock question review hold queue (got: ${kind:-nothing})";;
      esac
      [ $# -le 4 ] || refuse "todo wait: too many arguments; quote the note"
      note="${4:-}"
      if bad_text "$note"; then refuse "todo wait: the note must not hold \" | \" or a line break"; fi
      new="waiting $kind since $NOW${note:+: $note}";;
    off)
      [ $# -eq 2 ] || refuse "todo wait: off takes nothing after it"
      [ -n "$open" ] || refuse "todo wait: $name is not waiting";;
    *) refuse "todo wait: on or off (got: ${verb:-nothing})";;
  esac
  if [ -n "$open" ]; then
    since=$(printf '%s' "$open" | sed -n 's/^waiting [^ ]* since \([0-9][0-9-]* [0-9:]*\).*/\1/p')
    m=$(minutes_between "$since" "$NOW"); closed=${m:-0}
    ssince=$(printf '%s\n' "$line" | awk -F' \\| ' '{ for (i = 4; i <= NF; i++) if ($i ~ /^stage .* since [0-9]/) { sub(/^.* since /, "", $i); print $i; exit } }')
    if [ -n "$ssince" ]; then
      hasst=1; from="$since"
      if [[ "$ssince" > "$since" ]]; then from="$ssince"; fi
      m=$(minutes_between "$from" "$NOW"); ins=${m:-0}
    fi
  fi
  NEW="$new" awk -F' \\| ' -v OFS=' | ' -v k="$name" -v add="$closed" -v ins="$ins" -v hasst="$hasst" '
    $1 == k && !hit {
      hit = 1; oi = 0; wi = 0; w = 0; si = 0; sw = 0
      for (i = 4; i <= NF; i++) {
        if (!wi && $i ~ /^waited [0-9]+m$/) { wi = i; w = substr($i, 8) + 0 }
        else if (!si && $i ~ /^waited in stage [0-9]+m$/) { si = i; sw = substr($i, 17) + 0 }
        else if (!oi && $i ~ /^waiting /) oi = i
      }
      n = 0
      for (i = 1; i <= NF; i++) {
        if (i == oi) { if (ENVIRON["NEW"] != "") out[++n] = ENVIRON["NEW"]; continue }
        if (i == wi && oi) { out[++n] = "waited " (w + add) "m"; continue }
        if (i == si && oi && hasst) { out[++n] = "waited in stage " (sw + ins) "m"; continue }
        out[++n] = $i
      }
      if (!oi && ENVIRON["NEW"] != "") out[++n] = ENVIRON["NEW"]
      if (oi && !wi) out[++n] = "waited " add "m"
      if (oi && hasst && !si) out[++n] = "waited in stage " ins "m"
      s = out[1]
      for (i = 2; i <= n; i++) s = s OFS out[i]
      print s; next
    }
    { print }' "$TODO" > "$TODO.tmp" && mv "$TODO.tmp" "$TODO"
  if [ "$verb" = on ]; then echo "todo wait on: $name ($kind)"; else echo "todo wait off: $name (+${closed}m waited)"; fi
}
# todo_where <name> <machine> ["<worktree path>"]
todo_where() {
  local name="${1:-}" machine="${2:-}" path="${3:-}" line
  [ -n "$name" ] || refuse "todo where: needs a todo name"
  line=$(first "$TODO" "$name")
  [ -n "$line" ] || refuse "no todo line named: $name"
  [ -n "$machine" ] || refuse "todo where: needs a machine name"
  case "$machine" in *[[:space:]]*) refuse "todo where: the machine name has no space (got: $machine)";; esac
  [ $# -le 3 ] || refuse "todo where: too many arguments; quote the path"
  if bad_text "$machine" || bad_text "$path"; then refuse "todo where: the machine and the path must not hold \" | \" or a line break"; fi
  NEW="on $machine${path:+ $path}" awk -F' \\| ' -v OFS=' | ' -v k="$name" '
    $1 == k && !hit {
      hit = 1; wi = 0
      for (i = 4; i <= NF; i++) if (!wi && $i ~ /^on /) wi = i
      if (wi) $wi = ENVIRON["NEW"]; else $(NF + 1) = ENVIRON["NEW"]
    }
    { print }' "$TODO" > "$TODO.tmp" && mv "$TODO.tmp" "$TODO"
  echo "todo where: $name -> $machine${path:+ $path}"
}

# --- park, worker (agent_state.txt of the folder this session is in)
STATE_FILE="$STATE_DIR/agent_state.txt"
# todo_stage <name> <stage> [<i>/<m>]
STAGE_WORDS="brief register mock tests workers verify push report e2e merge"
todo_stage() {
  local name="${1:-}" stage="${2:-}" frac="${3:-}" line val cur i m wt_here= csince tsince keep
  [ -n "$name" ] || refuse "todo stage: needs a todo name"
  [ -n "$stage" ] || refuse "todo stage: needs a stage"
  case " $STAGE_WORDS " in *" $stage "*) ;; *) refuse "todo stage: the stage is one of: $STAGE_WORDS (got: $stage)";; esac
  if [ "$stage" = workers ]; then
    [ $# -le 3 ] || refuse "todo stage: too many arguments"
    if [ -n "$frac" ]; then
      case "$frac" in */*) ;; *) refuse "todo stage: workers takes <i>/<m> (got: $frac)";; esac
      i=${frac%%/*}; m=${frac#*/}
      is_num "$i" && is_num "$m" && [ "${#i}" -le 9 ] && [ "${#m}" -le 9 ] || refuse "todo stage: <i>/<m> are whole numbers (got: $frac)"
      [ $((10#$m)) -ge 1 ] && [ $((10#$i)) -le $((10#$m)) ] || refuse "todo stage: <i>/<m> needs m >= 1 and i <= m (got: $frac)"
      frac="$((10#$i))/$((10#$m))"
    fi
  else
    [ $# -le 2 ] || refuse "todo stage: <i>/<m> goes only with workers"
  fi
  val="$stage${frac:+ $frac}"
  if [ "$(cd "$STATE_DIR" 2>/dev/null && pwd -P)" != "$(cd "$PROJECT_ROOT" 2>/dev/null && pwd -P)" ]; then wt_here=1; fi
  line=$(first "$TODO" "$name")
  if [ -z "$line" ] && [ -z "$wt_here" ]; then refuse "no todo line named: $name"; fi
  if [ -n "$line" ]; then
    cur=$(printf '%s\n' "$line" | awk -F' \\| ' '{ for (i = 4; i <= NF; i++) if ($i ~ /^stage /) { sub(/^stage /, "", $i); sub(/ since .*$/, "", $i); print $i; exit } }')
    if [ "$cur" != "$val" ]; then
      tsince=$NOW; keep=0
      if [ "${cur%% *}" = "$stage" ]; then
        csince=$(printf '%s\n' "$line" | awk -F' \\| ' '{ for (i = 4; i <= NF; i++) if ($i ~ /^stage /) { if (sub(/^.* since /, "", $i)) print $i; exit } }')
        if [ -n "$csince" ]; then tsince=$csince; keep=1; fi
      fi
      NEW="stage $val since $tsince" awk -F' \\| ' -v OFS=' | ' -v k="$name" -v keep="$keep" '
        $1 == k && !hit {
          hit = 1; wi = 0
          for (i = 4; i <= NF; i++) if (!wi && $i ~ /^stage /) wi = i
          if (wi) $wi = ENVIRON["NEW"]; else $(NF + 1) = ENVIRON["NEW"]
          if (!keep) {
            n = 0
            for (i = 1; i <= NF; i++) if (!(i >= 4 && $i ~ /^waited in stage [0-9]+m$/)) out[++n] = $i
            s = out[1]
            for (i = 2; i <= n; i++) s = s OFS out[i]
            print s; next
          }
        }
        { print }' "$TODO" > "$TODO.tmp" && mv "$TODO.tmp" "$TODO"
    fi
  fi
  if [ -n "$wt_here" ]; then
    cur=; csince=
    if [ -f "$STATE_FILE" ]; then
      cur=$(awk -v p="STAGE $name: " 'index($0, p) == 1 { s = substr($0, length(p) + 1); sub(/ \| since .*$/, "", s); print s; exit }' "$STATE_FILE")
      csince=$(awk -v p="STAGE $name: " 'index($0, p) == 1 { s = $0; if (sub(/^.* \| since /, "", s)) print s; exit }' "$STATE_FILE")
    fi
    if [ "$cur" != "$val" ]; then
      local src="$STATE_FILE" ssn=$NOW; [ -f "$src" ] || src=/dev/null
      if [ -n "$cur" ] && [ "${cur%% *}" = "$stage" ] && [ -n "$csince" ]; then ssn=$csince; fi
      NEW="STAGE $name: $val | since $ssn" awk -v p="STAGE $name: " '
        index($0, p) == 1 { if (!d) print ENVIRON["NEW"]; d = 1; next }
        { print }
        END { if (!d) print ENVIRON["NEW"] }' "$src" > "$STATE_FILE.tmp" && mv "$STATE_FILE.tmp" "$STATE_FILE"
    fi
  fi
  echo "todo stage: $name -> $val"
}

# state_text <command> "<text>": refuses an empty text, " | " and a line break
state_text() {
  case "$2" in *[![:space:]]*) ;; *) refuse "$1: the text is empty";; esac
  if bad_text "$2"; then refuse "$1: the text must not hold \" | \" or a line break"; fi
}
# state_n <command> <n>: a whole number from 1 (nothing else is let through)
state_n() {
  is_num "$2" && [ "${#2}" -le 9 ] && [ $((10#$2)) -ge 1 ] || refuse "$1: n is a whole number from 1 (got: $2)"
}
state_append() {
  if [ -s "$STATE_FILE" ] && [ -n "$(tail -c 1 "$STATE_FILE")" ]; then printf '\n' >> "$STATE_FILE"; fi
  printf '%s\n' "$1" >> "$STATE_FILE"
}
# questions_py <command> [args...]: agent_questions.py does the work (python3 only)
questions_py() {
  local lang
  command -v python3 >/dev/null 2>&1 || refuse "questions: python3 is needed and was not found"
  lang=$(unset language; conf_read; printf '%s' "${language:-en}") || lang=en
  case "$lang" in zh) ;; *) lang=en;; esac
  python3 "$(dirname "$0")/agent_questions.py" "$PROJECT_ROOT" "$STATE_DIR" "$PROJECT_CWD" "$NOW" "$lang" "$@"
}
questions_run() {
  local out first
  case "${1:-}" in
    answer)
      shift
      out=$(questions_py answer "$@")
      first=${out%%$'\n'*}
      case "$first" in
        @TODO-WAIT-OFF$'\t'*) todo_wait "${first#*$'\t'}" off >/dev/null; printf '%s\n' "${out#*$'\n'}";;
        *) printf '%s\n' "$out";;
      esac;;
    --url) shift; questions_py url "$@";;
    *) questions_py list "$@";;
  esac
}
park_run() {
  local sub="${1:-}" n line task
  [ $# -eq 0 ] || shift
  case "$sub" in
    add)
      [ $# -ge 1 ] || refuse "park add: needs the question"
      questions_py park-add "$@";;
    list)
      [ $# -eq 0 ] || refuse "park list: takes nothing after it"
      if [ -f "$STATE_FILE" ]; then
        awk '/^PARKED: / { n++; sub(/^PARKED: /, ""); print n ". " $0 } END { if (!n) print "(empty)" }' "$STATE_FILE"
      else
        echo "(empty)"
      fi;;
    rm)
      if [ "${1:-}" = "--id" ]; then shift; questions_py park-rm-id "$@"; return 0; fi
      [ $# -eq 1 ] || refuse "park rm: needs one number"
      state_n "park rm" "$1"; n=$((10#$1))
      line=; [ ! -f "$STATE_FILE" ] || line=$(awk -v n="$n" '/^PARKED: / { c++; if (c == n) { print; exit } }' "$STATE_FILE")
      [ -n "$line" ] || refuse "park rm: no parked item number $n"
      awk -v n="$n" '/^PARKED: / { c++; if (c == n) next } { print }' "$STATE_FILE" > "$STATE_FILE.tmp" && mv "$STATE_FILE.tmp" "$STATE_FILE"
      printf 'parked %s removed: %s\n' "$n" "$(printf '%s' "${line#PARKED: }" | cut -c1-60)";;
    *) refuse "park: add, list or rm (got: ${sub:-nothing})";;
  esac
}
worker_run() {
  local sub="${1:-}" n line
  [ $# -eq 0 ] || shift
  case "$sub" in
    on)
      [ $# -ge 2 ] || refuse "worker on: needs <n> and the slice"
      [ $# -le 2 ] || refuse "worker on: too many arguments; quote the slice"
      state_n "worker on" "$1"; n=$((10#$1))
      state_text "worker on" "$2"
      line="WORKER $n: $2 | since $NOW"
      if [ -f "$STATE_FILE" ] && grep -q "^WORKER $n: " "$STATE_FILE"; then
        NEW="$line" awk -v p="WORKER $n: " 'index($0, p) == 1 { if (!d) print ENVIRON["NEW"]; d = 1; next } { print }' "$STATE_FILE" > "$STATE_FILE.tmp" && mv "$STATE_FILE.tmp" "$STATE_FILE"
      else
        state_append "$line"
      fi
      echo "worker $n on: $2";;
    off)
      [ $# -eq 1 ] || refuse "worker off: needs one number"
      state_n "worker off" "$1"; n=$((10#$1))
      if [ ! -f "$STATE_FILE" ] || ! grep -q "^WORKER $n: " "$STATE_FILE"; then refuse "worker off: no worker $n"; fi
      awk -v p="WORKER $n: " 'index($0, p) != 1' "$STATE_FILE" > "$STATE_FILE.tmp" && mv "$STATE_FILE.tmp" "$STATE_FILE"
      echo "worker $n off";;
    *) refuse "worker: on or off (got: ${sub:-nothing})";;
  esac
}

# --- board
# board [--self] [--watch [<sec>]]: agent_board.py draws it (python3 only); nothing is written
# conf_num <key> <low> <high>: the whole number of <key> in agent.conf, else the one in the template bin/agent.conf.default
conf_num() {
  local f v
  for f in "$PROJECT_ROOT/agent.conf" "$(dirname "$0")/agent.conf.default"; do
    [ -f "$f" ] || continue
    v=$(awk -F= -v k="$1" '$1 == k { v = $2 } END { print v }' "$f" | tr -d '[:space:]')
    if is_num "$v" && [ "${#v}" -le 9 ] && [ $((10#$v)) -ge "$2" ] && [ $((10#$v)) -le "$3" ]; then echo $((10#$v)); return 0; fi
  done
  return 1
}
board_run() {
  local self="" watch="" sec="" host lang
  while [ $# -gt 0 ]; do
    case "$1" in
      --self) self=1;;
      --watch)
        watch=1
        if [ $# -ge 2 ] && [ "$2" != "--self" ]; then sec="$2"; shift; fi;;
      *) refuse "board: unknown option: $1 (only --self and --watch [<sec>])";;
    esac
    shift
  done
  if [ -n "$watch" ]; then
    if [ -z "$sec" ]; then sec=$(conf_num board_watch_sec 1 3600) || refuse "board: --watch needs <sec>: board_watch_sec is not set in agent.conf or bin/agent.conf.default"; fi
    is_num "$sec" && [ "${#sec}" -le 9 ] && [ $((10#$sec)) -ge 1 ] || refuse "board: --watch takes a whole number of seconds from 1 (got: $sec)"
    sec=$((10#$sec))
  fi
  command -v python3 >/dev/null 2>&1 || refuse "board: python3 is needed and was not found"
  lang=$(unset language; conf_read; printf '%s' "${language:-en}") || lang=en
  case "$lang" in zh) ;; *) lang=en;; esac
  host=${AGENT_FAKE_HOST:-$(hostname -s 2>/dev/null || hostname)}
  if [ -n "$watch" ]; then
    exec python3 "$(dirname "$0")/agent_board.py" --root "$PROJECT_ROOT" --state-dir "$STATE_DIR" --cwd "$PROJECT_CWD" \
      --now "$NOW" --lang "$lang" --host "$host" ${self:+--self} --watch "$sec"
  fi
  python3 "$(dirname "$0")/agent_board.py" --root "$PROJECT_ROOT" --state-dir "$STATE_DIR" --cwd "$PROJECT_CWD" \
    --now "$NOW" --lang "$lang" --host "$host" ${self:+--self}
}

case "${1:-}:${2:-}" in
  helper-task:*)
    [ $# -ge 2 ] || usage
    helper_task "$2";;
  todo:add)
    need 5 "$@"; drop "$TODO" "$3"
    what="$5"
    [ -n "${6:-}" ] && what="$5 | est ${6}m"
    by="${7:-$WHO}"
    append "$TODO" "$3 | $4 | $what | opened $NOW | by $by"
    echo "todo added: $3";;
  todo:done)
    need 3 "$@"; name="$3"; line=$(first "$TODO" "$name")
    [ -n "$line" ] || { echo "no todo line named: $name" >&2; exit 1; }
    shift 3
    case "${1:-}" in --*) ;; *) [ $# -eq 0 ] || shift;; esac   # the "<result>" text is not stored
    dreset; d_files=; d_lines=
    done_opts "$@"
    counted=yes; [ -n "$d_files" ] || { counted=; d_files=-; d_lines=-; }
    what=$(printf '%s\n' "$line" | awk -F' \\| ' '{print $3}')
    est=$(old_num "$line" est)
    opened=$(printf '%s\n' "$line" | sed -n 's/.*opened \([0-9][0-9-]* [0-9:]*\).*/\1/p')
    clock=; [ -z "$opened" ] || clock=$(minutes_between "$opened" "$NOW")
    d_repo=$(repo_name "$ROOT"); d_est=${est:--}; d_clock=${clock:--}
    date="${NOW%% *}"
    drop "$TODO" "$name"; append "$DONE" "$date | $name | $what | $(dblock)"
    echo "todo done: $name"
    [ -n "$counted" ] || echo "files and lines: not counted (no --merge or --range)"
    echo "TIME DATA: $(time_data) of $TIME_DATA_GOAL"
    retrain_auto
    sweep_after_last_task;;
  todo:wait)
    shift 2; todo_wait "$@";;
  todo:where)
    shift 2; todo_where "$@";;
  todo:stage)
    shift 2; todo_stage "$@";;
  park:*)
    shift; park_run "$@";;
  worker:*)
    shift; worker_run "$@";;
  board:*)
    shift; board_run "$@";;
  questions:*)
    shift; questions_run "$@";;
  todo:drop)
    need 5 "$@"; line=$(first "$TODO" "$3")
    [ -n "$line" ] || { echo "no todo line named: $3" >&2; exit 1; }
    what=$(printf '%s\n' "$line" | awk -F' \\| ' '{print $3}')
    est=$(printf '%s' "$line" | grep -o 'est [0-9][0-9]*m' | head -1 | sed 's/est //;s/m//')
    [ -n "$est" ] || est="-"
    [ "$est" = "-" ] && est_disp="-" || est_disp="${est}m"
    date="${NOW%% *}"
    drop "$TODO" "$3"; append "$DONE" "$date | $3 | $what | est $est_disp actual - | dropped: $4"
    echo "todo dropped: $3";;
  idea:add)
    need 3 "$@"; append "$IDEAS" "$3 | $NOW | by $WHO"
    echo "idea added";;
  idea:list)
    [ -s "$IDEAS" ] && cat -n "$IDEAS" || echo "(empty)";;
  idea:rm)
    need 3 "$@"; n="$3"
    case "$n" in ''|*[!0-9]*) echo "no idea number $n" >&2; exit 1;; esac
    line=$(sed -n "${n}p" "$IDEAS")
    [ -n "$line" ] || { echo "no idea number $n" >&2; exit 1; }
    sed "${n}d" "$IDEAS" > "$IDEAS.tmp" && mv "$IDEAS.tmp" "$IDEAS"
    printf 'idea %s removed: %s\n' "$n" "$(printf '%s' "$line" | cut -c1-60)";;
  worktree:set)
    need 5 "$@"; old=$(first "$WT" "$3"); since=$(printf '%s' "$old" | awk -F' \\| ' '{print $4}')
    [ -n "$since" ] || since="since $NOW"
    drop "$WT" "$3"; append "$WT" "$3 | $4 | $5 | $since"
    echo "worktree $5: $3";;
  worktree:rm)
    need 3 "$@"; drop "$WT" "$3"; echo "worktree removed: $3";;
  show:*)
    for f in "$TODO" "$DONE" "$IDEAS" "$WT"; do
      echo "=== $(basename "$f") ==="; [ -s "$f" ] && cat "$f" || echo "(empty)"; echo
    done;;
  time:)
    printf '%-30s %8s %8s %8s %8s %8s\n' "name" "est" "work" "wait" "clock" "ratio"
    [ -s "$DONE" ] || exit 0
    while IFS= read -r ln; do
      [ -n "$ln" ] || continue
      case "$ln" in *'| dropped: '*) continue;; esac
      name=${ln#* | }; name=${name%% | *}
      case "$ln" in
        *' | data '*) est=$(dkey "$ln" est); work=$(dkey "$ln" work); wt=$(dkey "$ln" wait); clock=$(dkey "$ln" clock);;
        *) est=$(old_est "$ln"); work=; wt=; clock=$(old_clock "$ln");;
      esac
      est=${est:--}; work=${work:--}; wt=${wt:--}; clock=${clock:--}
      if is_num "$work" && is_num "$est" && [ "$est" -gt 0 ]; then
        ratio=$(awk -v w="$work" -v e="$est" 'BEGIN{printf "%.1f", w/e}')
      else
        ratio="-"
      fi
      printf '%-30s %8s %8s %8s %8s %8s\n' "$name" "$est" "$work" "$wt" "$clock" "$ratio"
    done < "$DONE";;
  backfill:*)
    shift
    case "${1:-}" in ''|--*) backfill_text "$@";; *) backfill_name "$@";; esac;;
  data:*)
    shift; data_run "$@";;
  estimate:*|backtest:*|retrain:*)
    cmd="$1"; shift; est_py "$cmd" "$@";;
  eta:*)
    [ $# -ge 2 ] || usage
    case "$2" in --*) usage;; esac
    shift; eta_run "$@";;
  *) usage;;
esac
