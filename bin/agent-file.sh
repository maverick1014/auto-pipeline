#!/usr/bin/env bash
# agent-file.sh — the only way to write agent_*.txt. No agent, no tokens, one format.
#
#   agent-file.sh todo add  "<name>" "<size>" "<what>" [est_minutes] [by] [--guess <m>] [--level <A-D>, old callers only]  -> agent_todo.txt (by defaults to "main")
#   agent-file.sh todo done "<name>" ["<result>"] [--work <m>] [--wait <m>] [--bounces <n>] [--workers <n>]
#                 [--mock yes|no] [--lane fast|full] [--type <t>] [--tests <n>] [--adds <n>]
#                 [--merge <commit> | --range <a>..<b>]       -> line moves to agent_completed.txt as one data line
#   agent-file.sh todo level "<name>" <A-D>                   -> old callers only (levels are gone, use todo checks): the todo line says " | level <A-D>" (old 0-4 read: 0=A 1=B 2,3=C 4=D; replaced in place, only goes up)
#   agent-file.sh todo drop "<name>" "<reason>"               -> line moves to agent_completed.txt as: date | name | what | est <n>m actual - | dropped: <reason>
#   agent-file.sh todo add ... [--checks "<BLOCK>,<BLOCK>"] [--scope "<glob>,<glob>"] [--builder "<name>"]
#                                                             -> fields " | checks A, B" (table order) right after guess (else est, else what), " | scope <globs>", " | builder <name>"; an unknown block is refused
#   agent-file.sh todo checks "<name>" <BLOCK>[,<BLOCK>]      -> union into the checks field, table order; prints "todo checks: <name> <old or -> -> <new>"
#   agent-file.sh todo checks "<name>" --remove <BLOCK> --owner-quote "<words>" --means "<action>" [--question "<q>"] [--time <t>] [--relayed-from <folder> | --relayed-by-leader <transcript file> --time "YYYY-MM-DD HH:MM"]
#                                                             -> only on a verified owner order (agent-owner-order.sh verify): the block leaves the field, the line gets " | removed <BLOCK> <date time>"
#   agent-file.sh todo target "<name>" production --owner-quote "<words>" --means "<action>" [--question "<q>"] [--time <t>] [--relayed-from <folder> | --relayed-by-leader <transcript file> --time "YYYY-MM-DD HH:MM"]
#                                                             -> the owner's yes after the task was added: verified and stored like todo add --target production; the line's target field becomes "target production", every other field stays
#   agent-file.sh todo builder "<name>" <who>                 -> field " | builder <who>" (replaced in place; a comma list is fine)
#   agent-file.sh todo est "<name>" <minutes> [--guess <m>]   -> est (and guess) replaced in place; the first est stays as " | est0 <m>m", the sum of every +<m> as " | added <m>m"; prints "todo est: <name> <old>m -> <new>m"
#   agent-file.sh check "<task>" "<BLOCK>" pass|fail --by <who> --evidence "<text>" [--owner-quote "<words>" --means "<what he signs>" [--question "<q>"] [--relayed-from <folder> | --relayed-by-leader <transcript file> --time "YYYY-MM-DD HH:MM"]]
#                                                             -> agent_state.txt of this folder: "CHECK <task> <BLOCK>: pass | by <who> | at <sha12> | <evidence> | <date time>" (OWNER SIGN allowed; [--commit <sha>], default HEAD of this folder)
#   agent-file.sh checks gather "<task>" --dir <path>         -> appends the task's CHECK lines of <path>/agent_state.txt to the main repo's agent_state.txt (lines already there skipped); prints "checks gather: <task> <n> lines"
#   agent-file.sh checks gate "<task>" --dir <path> [--base <ref>] [--branch <b>] [--results <file>] [--checks "<list>"]
#                                                             -> the merge guard: per planned block "<BLOCK>: pass (by <who>)|fail (by <who>)|missing", then "GATE PASS <task>" (exit 0) or "GATE REFUSED <task>: <BLOCK> missing, ..." (exit 1); no todo line and no --checks: exit 2
#   agent-file.sh next                                        -> "NEXT: <n> can start (room <mb> MB under the <p>% limit)", then START / WAIT lines for the queued tasks
#   agent-file.sh model ok --owner-quote "<words>" --means "<action>" [--question "<q>"] [--time <t>]  -> the owner says the main manager's model change is intended: verified, stored as MODEL OK <model> <effort> (requirements/model-floor.md)
#   agent-file.sh model check <model> <effort>               -> exit 0 and "MODEL OK <model> <effort>" while that record stands, else exit 1
#   agent-file.sh edge add "<text>"                           -> one "edge=<text>" line in agent_repo.conf of this folder's git toplevel; "edge add: already listed" when present
#   agent-file.sh idea add  "<text>"                          -> agent_ideas.txt
#   agent-file.sh idea list                                   -> print agent_ideas.txt, numbered (cat -n)
#   agent-file.sh idea rm   <n>                                -> remove line n from agent_ideas.txt
#   agent-file.sh idea keep <n>                                -> line n gets " | kept <date>": still wanted, never a housekeep suspect again
#   agent-file.sh files show                                  -> "files: task_files=<v> task_take=<v> place=<ap-data|tree>", then "<file>: local" or "<file>: in git" per agent file
#   agent-file.sh todo assign <task> <name>                   -> shared todo, the owner only: " | assignee <name>", committed, pushed
#   agent-file.sh todo take <task>                            -> shared todo, task_take=anyone: " | taken <me>", pushed at once; refused when another took it
#   agent-file.sh files sync                                  -> fetch origin ap-data, merge it into the files in git, commit, push (agent_share.py)
#   agent-file.sh files move                                  -> main checkout only: every tracked agent file leaves the code branch (copy kept in <git dir>/agent-files-kept), ignore lines written, the files in git go onto ap-data; second run changes nothing
#   agent-file.sh files restore <file> [<saved name> | --list]  -> a saved copy (default the newest) becomes the working copy; the current one is saved first (undo: restore it by name); --list shows the saved copies, newest first; none is ever deleted
#   agent-file.sh files set <task_files|task_take|task_place|data_branch> <value>   -> the fact in agent_repo.conf (one code-branch commit of that file); task_files then runs files move (and writes the missing task_files, task_take, data_branch values); data_branch on a branch that holds code (e.g. main) needs an origin (else refused, one line); its files live under .ap-data/ and are pushed on top of the remote tip, no local ref or checkout moves; on the production branch one line says a commit there can start a deploy
#
# Files in git (place data, the default): agent_completed.txt and agent_estimate.txt always, agent_ideas.txt and agent_todo.txt when
#   agent_repo.conf says task_files=ideas or ideas,todo. A run that changes one of them ends with one commit on the data branch ap-data
#   (git plumbing, HEAD and the index never move; message = the command words, e.g. "todo done t") and a push of origin ap-data at once.
#   A push that fails never fails the command: one line "ap-data: not pushed (<why>); the next write pushes it". Place tree (cloud): nothing is committed here.
#   idea add writes "by <git user.name>" (no name: the role); idea list shows "[<name>]" before a line that carries a name.
#   agent-file.sh worktree set "<path>" "<module>" "<status>" -> agent_worktree.txt (add or replace)
#   agent-file.sh worktree rm  "<path>"                       -> agent_worktree.txt
#   agent-file.sh helper-task "<Task Name>"                   -> the task of THIS human-direct Helper session: its name becomes "<repo> Helper - <Task Name>"
#   agent-file.sh session-end <sid> | --dead [--dry-run]      -> a session leaves nothing behind: its agent_*_<sid> files in the git dir and its human-direct line; --dead: the human-direct lines whose pid on this host is gone (one line each: "human-direct line <path> (pid <n> gone)"), and an old-format line with no pid and no session id 12 h old or more is only FLAGGED, never removed ("flag: human-direct line <path>: no pid, no session id, <n>h old: ...")
#   agent-file.sh show                                        -> print all four files
#   agent-file.sh time                                        -> table: name est work wait clock ratio (agent_completed.txt)
#   agent-file.sh backfill [--dry-run]                        -> old lines: take work and wait from the text of each line
#   agent-file.sh backfill <name> [--dry-run] [--force] <todo done options>   -> set the data of one finished line
#   agent-file.sh data [--what] [<repo path>...]              -> table: one row per finished task, every repo on this machine
#   agent-file.sh repos                                       -> read only: real paths one per line: this repo, then world.json territories; each once, a missing folder is skipped
#   agent-file.sh todo cross "<name>" <repo>                  -> the todo line says the other repo of a two-repo task: " | cross <repo>" (replaced in place, else appended)
#   agent-file.sh estimate --lane fast|full --mock yes|no --type <t> [--name <name>] [--guess <m>] "<what>"   -> work minutes, range, like tasks
#   agent-file.sh backtest [--tasks]                          -> the estimator against the rubric and the todo est, rolling
#   agent-file.sh estimate-queue                              -> queues one estimator run and starts its background runner (agent_share after a sync that brought finished records); never waits
#   agent-file.sh retrain [--force]                           -> learn agent_estimate.txt when 30 tasks, then once a week
#                                                             -> an older plugin than installed: one line "retrain skipped: <running> is older than installed <newest>", nothing changes
#   agent-file.sh eta <name> [--step <n>] [--work-so-far <m>] [--wait <m>]    -> one line: work left, done around, owner needed next; with neither --step nor --work-so-far the numbers are the board's "Done by" cell (p50 and p85 from the history, agent_forecast.py); with one of them, the old rule
#   agent-file.sh todo wait "<name>" on <mock|question|review|hold|queue> ["<note>"] [--who <name>] [--after <task>]  -> the todo line starts a wait
#   agent-file.sh todo wait "<name>" off                      -> the wait closes; its minutes join "waited <m>m"; who, after, wait run since go
#   agent-file.sh todo where "<name>" <machine> ["<worktree path>"]   -> the todo line says where it runs
#   agent-file.sh todo beat "<name>" "<work>m <text>"        -> the todo line carries the last heartbeat (the watch writes it; shown in the progress cell)
#   agent-file.sh park add "<question>" ["<task>"] [--sub "<line>"] [--why "<text>"] [--evidence "<text>"]
#                 [--fact "<key>: <value>"]... [--options "A text|B text"] [--rec <letter or option text>]
#                                                             -> agent_state.txt: PARKED: <question> | <task> | since <date> | sub .. | fact .. | option A: .. | rec A
#   agent-file.sh park list                                   -> the PARKED lines, numbered
#   agent-file.sh park rm <n>                                 -> remove the n-th PARKED line
#   agent-file.sh park rm --id <id>                           -> remove the PARKED line with that id (the id `questions` gives)
#   agent-file.sh questions [--self] [--json]                 -> every question that waits on the owner (/auto-pipeline:question)
#   agent-file.sh questions [--self] --page <file>            -> write the answer page, its map, and the "QUESTIONS PAGE:" line
#   agent-file.sh questions --url <url>                       -> set the published url on the "QUESTIONS PAGE:" line
#   agent-file.sh questions answer <id> "<answer>"            -> close one question (parked: line goes; todo: wait closes; QUESTION: gets "ANSWER:")
#   agent-file.sh worker on <n> "<slice>"                     -> agent_state.txt: WORKER <n>: <slice> | since <date> (replaces worker n)
#   agent-file.sh worker off <n>                              -> remove WORKER <n>
#   agent-file.sh board [--self]                              -> the table of everything open (/auto-pipeline:todo); --self: this session's task only
#   agent-file.sh state add "<line>"                          -> agent_state.txt of this folder gets "<line> | <date time>" (one line, " | " inside is fine)
#   agent-file.sh tell "<task>" "[<model> <effort>] <msg>"    -> the block "TELL <sha8> ..." at the end of that task's agent_state.txt, then one pointer line into its TM pane (rules D1-D8, requirements/one-watcher.md); prints "TELL OK <task> <sha8>"
#   agent-file.sh heartbeat "<task>" <step 0-7> "<what runs now>"  -> agent_state.txt: "HEARTBEAT <task>: step <n> of 7, work <m>m, <text> | <date time>"; the work is computed (the todo line as the board counts it, else the WORK START line of this folder's agent_state.txt; neither: refused). The form with typed minutes (<step> <work min> "<text>") still works: a known start wins (a note on stderr when they differ by more than 5)
#   agent-file.sh helper-join "<task>"                        -> a human-direct Helper becomes a normal agent: its worktree line becomes "<path> | <task> | working | since .. | pane .. | session .."
#   agent-file.sh todo est "<name>" +<minutes>                -> adds minutes to the estimate (guess stays); todo add also takes --target production|working (production needs --owner-quote "<words>" --means "<action>" [--question "<q>"] [--time <t>] [--relayed-from <folder> | --relayed-by-leader <transcript file> --time "YYYY-MM-DD HH:MM"], verified at once) and --batch <name>
#   agent-file.sh state trim [--dry-run]                      -> old lines of agent_state.txt move to agent_state.trim-<date>.txt (rules: requirements/state-trim.md); --dry-run only counts
#
# todo done also closes the queue wait of every open line whose " | after <name>" field is that task, drops the after field, and prints "released: <line name>" per line.
# todo done: every option is optional; a number is a whole number, 0 or more. "<result>" is not stored.
#   work = agent minutes, MEASURED: minutes(started, now) - max(0, W - n) (n = the " after <n>m waited" of the started field), else
#   clock - W when the line has an opened time; W = closed waits + the open wait up to now (--wait <m> given: the larger). Never below 0.
#   No time on the line: the typed --work, else "-". The typed --work is kept as typed=<m>, never as the label. A typed --work over
#   the clock: one warning line on stderr, the line moves as usual. wait = W. Work and wait are never mixed.
#   est0 = the " | est0 <m>m" field, else est; added = the " | added <m>m" field, else "-". stages, slices, built come from the
#   " | stage log" field (todo stage): stages=<stage>:<m>,... slices=<m>,... built=<m> ("-" when there is no log).
#   <t> is one of: page server script docs cloud app data mixed.
#   est comes from the todo line. clock = minutes from "opened" to now. repo = folder name of the main repo.
#   files and lines (lines = added + deleted) are counted only when asked, in the main repo:
#     --merge <commit>   git diff --shortstat <commit>^1 <commit>    what the merge brought in
#     --range <a>..<b>   git diff --shortstat <merge-base a b> <b>   what b changed since it left a
#   Neither given: files=- lines=- and "not counted" is printed. Both given, or a commit git does not know: refused.
#   A bad option is refused: one line on stderr that names it, exit 1, nothing moves.
#   It prints "todo done: <name>" and "TIME DATA: <n> of 30" (finished tasks that have a work number).
#   No --type or no --lane: one warning line on stderr ("todo done: warning: no --type --lane given (...)"), exit 0.
#   --guess <m> (whole number, 1 or more; anywhere after "todo add") adds the field " | guess <m>m" after est; done copies it to guess=<m>.
#   An est equal to --guess is refused (one line on stderr naming --why, exit 1, nothing written) unless --why "<reason>" is given;
#   --why adds " | why <reason>" right after guess (an empty reason, " | " or a line break: refused; needs --guess).
#   --level <A-D>: old callers only (levels are gone, use --checks) (old 0-4 accepted, stored as a letter; anywhere after "todo add") adds " | level <A-D>" right after guess (else after est, else after the what); done copies it to level=<A-D>.
#   todo level "<name>" <A-D>: old callers only; sets it in place, every other field stays; prints "todo level: <name> <old> -> <new>" ("-" for none) or "todo level: <name> already type <new>" (writes nothing).
#     A lower type, no such line, a bad or missing type: refused (one line on stderr, exit 1, nothing written).
#   Then the retrain, only when due: one line "estimate retrain: ...", never the table. A failure never stops todo done.
#
# The line in agent_completed.txt (keys in this order, "-" when not known):
#   <date> | <name> | <what> | data repo=<r> type=<t> lane=<l> mock=<yes|no> est=<m> work=<m> wait=<m> clock=<m> bounces=<n> workers=<n> files=<n> lines=<n> tests=<n> adds=<n> guess=<m> level=<n> typed=<m> est0=<m> added=<m> built=<m> stages=<s:m,...> slices=<m,...>
#   level = the risk type from the todo line's "level <A-D>" field (an old line may hold 0-4), "-" when none. An older block has no level key (read as "-").
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
# data: read-only. Columns: repo name date type lane mock est work wait clock bounces workers files lines tests adds guess.
#   data --what adds est0 typed built stages slices after guess, then what.
#   An old line gives est and clock, "-" elsewhere. The repo column is the data block's repo, else the folder name.
#   Repos, in this order, the same repo (real path) once:
#     1. this repo
#     2. the keys of "territories" in world.json in the city home ($AGENT_CITY_HOME, default ~/.claude/agent-city);
#        a key "<repo>/.git" names <repo>, any other key is passed over; no python3 or a bad file: passed over
#     3. the paths given as arguments
#   It reads only <repo>/agent_completed.txt of another repo and writes nothing there.
#   No such file or folder: one line "skipped ..." on stderr, exit stays 0.
#   guess = the manager's own minutes from the todo line, "-" when none. --what adds one last column, what: the text between the name and the data block ("-" when empty).
#
# estimate, backtest, retrain: the work is done by agent_estimate.py (python3), from the table of data --what.
#   Read requirements/estimate.md. An estimate = agent work minutes, from what is known before dispatch only.
#   estimate: read only. First line "estimate: <m>m work, range <lo>-<hi>m (<estimator|rubric> v<n>, <N> past tasks)",
#     then up to 3 "like <name>: <m>m work (...)" lines. A fact known only after the task (--work --wait --clock --est
#     --bounces --workers --files --lines --tests --adds), a missing or bad --lane --mock --type, or no what:
#     refused, one line on stderr that names it, exit 1, nothing on stdout.
#   estimate --guess <m>: the manager's own minutes, blended in only when the version is a blend.
#   estimate and backtest read estimate_target_pct, estimate_bias_min, estimate_big_min as constants (agent_conf.py).
#   backtest: read only. Each task with 10 tasks before it is estimated from those only. Rows: estimator, blend, blend+repo,
#     rubric, todo est (median error, within 30%, in range), then "work >= <big>m: <n> tasks" and the same rows for big tasks.
#     winner = a blend only when its within 30% beats the base winner (estimator or rubric). Last line:
#     "target within 30% <goal>%: ...". --tasks: one row per tested task, with guess, blend and blend+repo. Under 11 tasks: one line "backtest: <N> tasks, needs at least 11", exit 0.
#   retrain: due at 30 tasks, then once a week with 1+ new task (--force skips the week, never the 30). Writes agent_estimate.txt
#     (JSON, atomic) in the project root: v1 = the winner's method from all tasks (a blend only when it wins); a later check
#     keeps the new version only when its error on the new tasks is strictly lower, and switches from a non-blend version
#     to the blend only when the blend's backtest within 30% beats it. Prints the table and one verdict line.
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
#     The options and the one note come in any order after the kind.
#     --who <name>: field " | who <name>" (spaces inside are fine; not with queue). --after <task>: field " | after <task>" (only with queue).
#     Field order: waiting, who, after, wait run since. Already waiting: the old who and after go, the new ones are written, and
#     " | wait run since <r>" is written: r = the old line's "wait run since", else the old wait's since. No open wait: no
#     "wait run since" (a stale one goes).
#   todo wait off: closes the open wait: " | waited <m>m" = the sum of every closed wait; the waiting, who, after and
#     wait run since fields go.
#   The closed wait also adds its minutes inside the current stage (from max(wait since, stage since) to now) to
#   " | waited in stage <n>m" (replaced in place, once; added at the end when new; never on a line with no stage field).
#   todo where: field " | on <machine>[ <path>]".
#   Refused (one line on stderr, exit 1, nothing written): no todo line of that name, a kind not in the list, off when not
#   waiting, no on|off, a machine with a space, " | " or a line break in a note or a path; --who with queue, --after with
#   any other kind; --who or --after with no value, an empty value, " | " or a line break in it, or given twice; an unknown
#   option starting with "--"; two notes; anything after off.
#
# todo beat <name> "<work>m <text>": the field " | beat <work>m <text>" of the todo line (one atomic write, replaced in place, added at
#   the end when new; the same text again: nothing is written). A new stage name (todo stage) drops it. Refused (one line on stderr,
#   exit 1, nothing written): no todo line of that name, an empty text, " | " or a line break in it, too many arguments.
# todo stage <name> <stage> [<i>/<m>]: (first stage: a line with no stage and no started field also gets " | started <date>[ after <n>m waited]"
#   right before the stage field; n = closed waited <m>m + an open wait up to now, no " after " when 0; never added or changed later.)
#   A new value (new stage or new <i>/<m>) also adds the entry "<value> <m>" to " | stage log <entry>, <entry>, ..." right before the
#   started field (else the stage field); m = the work minutes at now as todo done counts them (the first stage: 0).
#   The stage field of the todo line, " | stage <stage>[ <i>/<m>] since <date>" (one atomic
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
#   agent_board.py (python3). The columns and words follow the `language` setting (zh, else en). --self: the session's own
#   task only. --watch [<sec>]: clear the screen and draw it again every <sec> seconds (whole number from 1; default
#   the board_watch_sec constant) until Ctrl-C. Any other option: refused.
#
# AGENT_FAKE_NOW="YYYY-MM-DD HH:MM" replaces the machine clock (tests). Unset or empty: the machine clock.
# AGENT_FAKE_HOST replaces the machine name that board prints (tests). Unset: the short host name.
# Files live in the main repo, never in a worktree. Writes are atomic (tmp + mv).

set -eu
TIME_DATA_GOAL=30
DATA_TYPES="page server script docs cloud app data mixed"
DATA_KEYS="repo type lane mock est work wait clock bounces workers files lines tests adds guess level typed est0 added built stages slices by"
OPT_CMD="todo done"   # the prefix of a refusal from done_opts; backfill sets it to "backfill"
case "$0" in */*) AF_DIR=${0%/*}; [ -n "$AF_DIR" ] || AF_DIR=/;; *) AF_DIR=.;; esac   # dirname "$0" without a start
. "$AF_DIR/agent-roots.sh"
roots_read
ROOT="$PROJECT_ROOT"
TODO="$ROOT/agent_todo.txt"; DONE="$ROOT/agent_completed.txt"; IDEAS="$ROOT/agent_ideas.txt"; WT="$ROOT/agent_worktree.txt"
# the fake clock only with AGENT_TESTING=1 and a repo root under the system temp folder (section 47 G6)
fake_clock_ok() {
  local c t r
  [ "${AGENT_TESTING:-}" = 1 ] && [ -n "${AGENT_FAKE_NOW:-}" ] && command -v python3 >/dev/null 2>&1 || return 1
  # python's tempfile.gettempdir() without a start: the first of $TMPDIR $TEMP $TMP /tmp /var/tmp /usr/tmp that is a writable
  # folder; the cwd and every case this cannot decide go to python3 as before
  t=""
  for c in "${TMPDIR:-}" "${TEMP:-}" "${TMP:-}" /tmp /var/tmp /usr/tmp; do
    [ -n "$c" ] || continue
    case "$c" in /*) ;; *) t=""; break;; esac
    if [ -d "$c" ] && [ -w "$c" ] && [ -x "$c" ]; then t=$(cd "$c" 2>/dev/null && pwd -P) || t=""; break; fi
  done
  r=$(cd "$ROOT" 2>/dev/null && pwd -P) || r=""
  if [ -n "$t" ] && [ -n "$r" ]; then
    [ "$r" = "$t" ] && return 0
    case "$r" in "${t%/}/"*) return 0;; esac
    return 1
  fi
  python3 -c 'import os, sys, tempfile
t = os.path.realpath(tempfile.gettempdir()); r = os.path.realpath(sys.argv[1])
sys.exit(0 if r == t or r.startswith(t.rstrip("/") + "/") else 1)' "$ROOT" 2>/dev/null
}
if fake_clock_ok; then NOW=$AGENT_FAKE_NOW; else NOW=$(date '+%Y-%m-%d %H:%M'); fi; WHO=${AGENT_ROLE:-main}
# a moved repo (no agent file tracked, the ignore line agent_completed.txt): the kept copies in <git common dir>/agent-files-kept.
# A repo that still tracks an agent file is not moved: nothing here runs for it (grep first, git ls-files only when the line is there).
AF_FIVE="agent_todo.txt agent_ideas.txt agent_worktree.txt agent_completed.txt agent_estimate.txt"
KEPT_DIR=""; KEPT_SNAP=""
# snap_of <var> <file>...: one cksum start over the existing files of $ROOT (in the given order) in <var>, one line each
snap_of() {
  local _v=$1 _f _o="" _l=()
  shift
  for _f in "$@"; do
    [ -f "$ROOT/$_f" ] && _l[${#_l[@]}]="$ROOT/$_f"
  done
  [ "${#_l[@]}" -eq 0 ] || _o=$(cksum -- "${_l[@]}" 2>/dev/null) || true
  printf -v "$_v" '%s' "$_o"
}
# gi_has <file>: a line that is exactly agent_completed.txt (grep -qx 'agent_completed.txt', the dot is any character)
gi_has() {
  local l
  [ -f "$1" ] && [ -r "$1" ] || return 1
  while IFS= read -r l || [ -n "$l" ]; do
    if [[ $l =~ ^agent_completed.txt$ ]]; then return 0; fi
  done < "$1"
  return 1
}
kept_readonly() {   # a command that never writes one of the five agent files
  case "${1:-}:${2:-}" in data:*|repos:*|eta:*|estimate:*|estimate-runner:*|estimate-queue:*|backtest:*|helper-task:*|board:*|park:*|worker:*|questions:*|state:*|tell:*|heartbeat:*|todo:level|check:*|checks:*|next:*|edge:*|model:*|show:*|time:*|idea:list|files:*) return 0;; esac
  return 1
}
kept_save() {   # kept_save <file>: keep the old kept copy as <file>.before-<time>[-n] before anything is written, say it, sweep
  local f=$1 k="$KEPT_DIR/$1" stamp n=0 dst old i=0
  stamp=$(date '+%Y%m%d-%H%M%S'); dst="$KEPT_DIR/$f.before-$stamp"
  while [ -e "$dst" ]; do n=$((n+1)); dst="$KEPT_DIR/$f.before-$stamp-$n"; done
  if cp "$k" "$dst" 2>/dev/null; then
    echo "WARNING: $ROOT/$f differs from its kept copy (changed outside the scripts); the old kept copy is saved as $dst; put it back with: agent-file.sh files restore $f" >&2
    # sweep: older than 7 days, except the newest 5 by mtime
    while IFS= read -r old; do
      i=$((i+1))
      [ "$i" -gt 5 ] || continue
      [ -n "$(find "$old" -mtime +7 2>/dev/null)" ] && rm -f "$old"
    done < <(cd "$KEPT_DIR" && ls -t -- "$f".before-* 2>/dev/null | sed "s|^|$KEPT_DIR/|")
  else
    echo "WARNING: $ROOT/$f differs from its kept copy $k (changed outside the scripts); the old kept copy could not be saved" >&2
  fi
  return 0
}
kept_start() {   # restore a missing working copy from its kept copy; say (never touch) one that differs
  local gd f k
  [ -e "$ROOT/.git" ] && gi_has "$ROOT/.gitignore" || return 0
  [ -z "$(git -C "$ROOT" ls-files -- $AF_FIVE 2>/dev/null)" ] || return 0
  gd=$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 0
  [ -n "$gd" ] || return 0
  KEPT_DIR="$gd/agent-files-kept"
  for f in $AF_FIVE; do
    k="$KEPT_DIR/$f"
    [ -f "$k" ] || continue
    if [ ! -e "$ROOT/$f" ]; then
      cp -p "$k" "$ROOT/$f" 2>/dev/null && echo "restored $f from $k" >&2
    elif ! cmp -s "$k" "$ROOT/$f"; then
      case "${1:-}:${2:-}" in files:restore) continue;; esac
      if kept_readonly "$@"; then
        echo "WARNING: $ROOT/$f differs from its kept copy $k (changed outside the scripts); left as it is" >&2
      else
        kept_save "$f" "$@"
      fi
    fi
  done
  snap_of KEPT_SNAP $AF_FIVE
  return 0
}
kept_end() {     # a run that ended 0 copies each of the five files it changed to its kept copy
  local f l now=""
  [ -n "$KEPT_DIR" ] || return 0
  [ -d "$KEPT_DIR" ] || mkdir -p "$KEPT_DIR" 2>/dev/null || return 0
  snap_of now $AF_FIVE
  while IFS= read -r l || [ -n "$l" ]; do
    [ -n "$l" ] || continue
    case $'\n'"$KEPT_SNAP"$'\n' in *$'\n'"$l"$'\n'*) continue;; esac
    f=${l##*/}
    cp -p "$ROOT/$f" "$KEPT_DIR/$f.tmp.$$" 2>/dev/null && mv "$KEPT_DIR/$f.tmp.$$" "$KEPT_DIR/$f"
  done <<< "$now"
  return 0
}
kept_start "$@"
case "${1:-}:${2:-}" in data:*|repos:*|eta:*|estimate:*|estimate-runner:*|estimate-queue:*|backtest:*|retrain:*|helper-task:*|session-end:*|board:*|park:*|worker:*|questions:*|state:*|tell:*|heartbeat:*|todo:level|check:*|checks:*|next:*|edge:*|model:*) ;; *) touch "$TODO" "$DONE" "$IDEAS" "$WT";; esac   # these only read (retrain writes agent_estimate.txt only; helper-task touches nothing before it is sure; park and worker write agent_state.txt only)

# the files in git (agent_share.py): a snapshot before and after, one commit on the data branch when a run changed them.
# Bash only (no python start when nothing changed): the facts are read from agent_repo.conf with grep and sed.
conf_fact() {   # the value of the last "<key> = <value>" line of agent_repo.conf, blanks removed; nothing when there is none
  local l v="" got="" f="$ROOT/agent_repo.conf"
  [ -f "$f" ] && [ -r "$f" ] || return 0
  while IFS= read -r l || [ -n "$l" ]; do
    if [[ $l =~ ^[[:space:]]*$1[[:space:]]*= ]]; then v=${l#*=}; got=1; fi
  done < "$f"
  [ -n "$got" ] || return 0
  printf '%s\n' "${v//[[:space:]]/}"
}
share_files() {
  local tf; [ -n "$KEPT_DIR" ] || return 0   # not moved: no snapshot, no commit
  [ "$(conf_fact task_place)" != tree ] || return 0
  tf=$(conf_fact task_files)
  printf '%s\n' agent_completed.txt agent_estimate.txt
  # no repo fact: the person's Configure setting may say more, so watch both (agent_share.py commit decides)
  case "$tf" in ideas) echo agent_ideas.txt;; ideas,todo|'') echo agent_ideas.txt; echo agent_todo.txt;; esac
}
share_snap() { local fl; fl=$(share_files); snap_of SHARE_NOW $fl; }   # the snapshot in SHARE_NOW
share_msg() {
  case "${1:-}" in
    idea) case "${2:-}" in add) echo "idea add";; *) echo "idea ${2:-} ${3:-}";; esac;;
    todo) echo "todo ${2:-} ${3:-}";;
    *) echo "${1:-run}";;
  esac
}
SHARE_MSG=$(share_msg "$@")
case "$SHARE_MSG" in
  *$'\n'*) SHARE_MSG=$(share_msg "$@" | sed 's/ *$//');;
  *) SHARE_MSG=${SHARE_MSG%"${SHARE_MSG##*[! ]}"};;
esac
SHARE_NOW=""; share_snap; SHARE_SNAP=$SHARE_NOW
SHARE_COMMITS=1
share_exit() {
  local rc=$?
  trap - EXIT
  if [ "$rc" -eq 0 ]; then
    kept_end
    if [ "$SHARE_COMMITS" = 1 ]; then
      share_snap
      if [ -n "$SHARE_SNAP$SHARE_NOW" ] && [ "$SHARE_NOW" != "$SHARE_SNAP" ]; then
        command -v python3 >/dev/null 2>&1 && python3 "$AF_DIR/agent_share.py" "$ROOT" commit "$SHARE_MSG" || true
      fi
    fi
  fi
  exit "$rc"
}
case "${1:-}" in files) ;; *) trap share_exit EXIT;; esac
case "${1:-}" in show|time|data|repos|estimate|estimate-queue|backtest|eta) SHARE_COMMITS=0;; esac

# a shared todo (agent_share.py): the newest data before a decision (quiet, a failed fetch never blocks), and who may work a task
share_pull() {
  case "$(conf_fact task_files)" in local|ideas) return 0;; esac
  [ -e "$ROOT/.git" ] && command -v python3 >/dev/null 2>&1 || return 0
  python3 "$AF_DIR/agent_share.py" "$ROOT" pull >/dev/null 2>&1 || true
}
SHARE_WHO=""
share_gate() {   # share_gate <task> [who]: refuse (stderr, exit 1) a task of a shared todo this person may not work; who: SHARE_WHO = the name for "by"
  local msg
  case "$(conf_fact task_files)" in local|ideas) return 0;; esac
  [ -n "$(first "$TODO" "$1")" ] && command -v python3 >/dev/null 2>&1 || return 0
  if [ "${2:-}" = who ]; then
    msg=$(python3 "$AF_DIR/agent_share.py" "$ROOT" may-work-who "$1" "$PWD" 2>/dev/null) || { printf '%s\n' "$msg" >&2; exit 1; }
    SHARE_WHO=$msg
    return 0
  fi
  msg=$(python3 "$AF_DIR/agent_share.py" "$ROOT" may-work "$1" 2>/dev/null) || { printf '%s\n' "$msg" >&2; exit 1; }
}
# share_pull_gate <task>: share_pull, then share_gate, in one python3 start (the same two steps, the same refusal)
share_pull_gate() {
  local msg
  case "$(conf_fact task_files)" in local|ideas) return 0;; esac
  command -v python3 >/dev/null 2>&1 || return 0
  msg=$(python3 "$AF_DIR/agent_share.py" "$ROOT" pull-may-work "$1" "$PWD" 2>/dev/null) || { printf '%s\n' "$msg" >&2; exit 1; }
}

# the whole header comment block, whatever its length
usage() { awk 'NR > 1 { if (/^#/) print; else exit }' "$0"; exit 2; }
need()  { [ $# -ge "$1" ] || usage; }
append(){ printf '%s\n' "$2" >> "$1"; }
# drop lines whose first field (before " | ") equals $2 from file $1
# (bash only; awk when the name is empty, holds a backslash (awk -v reads escapes) or may read as a number (awk compares numbers
# as numbers), or the file is not readable)
awk_name() { case "$1" in ''|*\\*) return 0;; *[!0-9.eE+infaINFA-]*) return 1;; esac; return 0; }
drop() {
  local l
  if awk_name "$2"; then awk -v k="$2" -F' \\| ' '$1 != k' "$1" > "$1.tmp" && mv "$1.tmp" "$1"; return; fi
  if [ ! -f "$1" ] || [ ! -r "$1" ]; then awk -v k="$2" -F' \\| ' '$1 != k' "$1" > "$1.tmp" && mv "$1.tmp" "$1"; return; fi
  {
    while IFS= read -r l || [ -n "$l" ]; do
      if [ "${l%% | *}" = "$2" ]; then continue; fi
      printf '%s\n' "$l"
    done < "$1"
  } > "$1.tmp" && mv "$1.tmp" "$1"
}
first() {
  local l
  if awk_name "$2"; then awk -v k="$2" -F' \\| ' '$1 == k {print; exit}' "$1"; return; fi
  if [ ! -f "$1" ] || [ ! -r "$1" ]; then awk -v k="$2" -F' \\| ' '$1 == k {print; exit}' "$1"; return; fi
  while IFS= read -r l || [ -n "$l" ]; do
    if [ "${l%% | *}" = "$2" ]; then printf '%s\n' "$l"; return 0; fi
  done < "$1"
  return 0
}
# "YYYY-MM-DD HH:MM" -> epoch seconds, BSD date first (macOS), GNU date as fallback
# NOW_EP: the epoch of $NOW once the main shell has asked for it (now_ep), so a $(...) below never starts date for it again
NOW_EP=""
to_epoch() {
  if [ -n "$NOW_EP" ] && [ "$1" = "$NOW" ]; then echo "$NOW_EP"; return 0; fi
  # BSD date takes the seconds it is not given from the wall clock: give it :00 so the minute is exact
  case "$1" in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\ [0-9][0-9]:[0-9][0-9]) date -j -f '%Y-%m-%d %H:%M:%S' "$1:00" +%s 2>/dev/null || date -d "$1" +%s 2>/dev/null || true; return 0;;
  esac
  date -j -f '%Y-%m-%d %H:%M' "$1" +%s 2>/dev/null || date -d "$1" +%s 2>/dev/null || true
}
now_ep() { NOW_EP=""; NOW_EP=$(to_epoch "$NOW"); }

# --- small helpers (todo done, time; also for backfill, data, eta)
# a whole number, 0 or more
is_num() { case "$1" in ''|*[!0-9]*) return 1;; esac; return 0; }
# "<line>": ONE line on stderr, exit 1. Call it at the top level, before any file changes.
refuse() { echo "$1" >&2; exit 1; }
# folder name of a repo path (no spaces, so it stays one word in a data block)
repo_name() {
  local p=$1
  p=${p%"${p##*[!/]}"}
  if [ -z "$p" ] && [ -n "$1" ]; then p=/; fi   # basename of / is /
  [ "$p" = / ] || p=${p##*/}
  printf '%s\n' "${p// /_}"
}
# minutes from "YYYY-MM-DD HH:MM" $1 to $2; nothing when a date does not read or $2 is before $1
minutes_between() {
  local o n
  o=$(to_epoch "$1"); n=$(to_epoch "$2")
  [ -n "$o" ] && [ -n "$n" ] && [ "$n" -ge "$o" ] && echo $(( (n - o) / 60 )) || true
}
# the data block as d_<key> variables: dreset sets them all to "-", dblock prints "data repo=... adds=..."
dreset() {
  d_repo=-; d_type=-; d_lane=-; d_mock=-; d_est=-; d_work=-; d_wait=-; d_clock=-
  d_bounces=-; d_workers=-; d_files=-; d_lines=-; d_tests=-; d_adds=-; d_guess=-; d_level=-
  d_typed=-; d_est0=-; d_added=-; d_built=-; d_stages=-; d_slices=-; d_by=-
}
dblock() {
  printf 'data repo=%s type=%s lane=%s mock=%s est=%s work=%s wait=%s clock=%s bounces=%s workers=%s files=%s lines=%s tests=%s adds=%s guess=%s level=%s typed=%s est0=%s added=%s built=%s stages=%s slices=%s by=%s' \
    "$d_repo" "$d_type" "$d_lane" "$d_mock" "$d_est" "$d_work" "$d_wait" "$d_clock" \
    "$d_bounces" "$d_workers" "$d_files" "$d_lines" "$d_tests" "$d_adds" "$d_guess" "$d_level" \
    "$d_typed" "$d_est0" "$d_added" "$d_built" "$d_stages" "$d_slices" "$d_by"
}
# split_line "<line>": LF[0..], LFN: the fields of a line as awk -F' \\| ' sees them (0-based: awk's $3 is LF[2])
split_line() {
  local rest=$1
  LF=(); LFN=0
  while :; do
    case "$rest" in
      *' | '*) LF[$LFN]=${rest%%' | '*}; rest=${rest#*' | '}; LFN=$((LFN+1));;
      *) LF[$LFN]=$rest; LFN=$((LFN+1)); break;;
    esac
  done
}
# fld_re <ERE>: the first of the fields 4.. of the line split_line took that matches; FLD = it (BASH_REMATCH has its groups)
fld_re() {
  local i=3
  FLD=""
  while [ "$i" -lt "$LFN" ]; do
    if [[ ${LF[$i]} =~ $1 ]]; then FLD=${LF[$i]}; return 0; fi
    i=$((i+1))
  done
  return 1
}
# last_opened "<line>": the date time of the last "opened YYYY-MM-DD HH:MM" in the line
last_opened() {
  local t=$1 c re='^([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2})'
  while [[ $t == *"opened "* ]]; do
    c=${t##*opened }
    if [[ $c =~ $re ]]; then printf '%s\n' "${BASH_REMATCH[1]}"; return 0; fi
    t=${t%opened *}
  done
  return 0
}
# todo_times "<todo line>" [<typed wait>]: t_clock, t_wait (W), t_work from the times on the line ("-" when unknown). Like the board:
# work = minutes(started, now) - max(0, W - n), else clock - W (opened); W = closed waits + the open wait up to now, or the typed wait when larger.
todo_times() {
  local m i f x r dre='^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}$'
  local are=' after [0-9]+m waited$' wre='^waiting [^ ]+ since ' cre='^waited [0-9]+m$'
  t_opened=-; t_started=-; t_before=0; t_closed=0; t_wo=-
  split_line "$1"
  i=3
  while [ "$i" -lt "$LFN" ]; do
    f=${LF[$i]}
    if [ "$t_opened" = - ] && [[ $f == "opened "* ]] && [[ ${f:7:16} =~ $dre ]]; then t_opened=${f:7:16}
    elif [ "$t_started" = - ] && [[ $f == "started "* ]] && [[ ${f:8:16} =~ $dre ]]; then
      t_started=${f:8:16}
      if [[ $f =~ $are ]]; then x=${f##* after }; x=${x%%[!0-9]*}; t_before=$((10#$x)); fi
    elif [ "$t_wo" = - ] && [[ $f =~ $wre ]]; then
      r=${f#* since }
      if [[ ${r:0:16} =~ $dre ]]; then t_wo=${r:0:16}; fi
    elif [[ $f =~ $cre ]]; then x=${f:7}; x=${x%%[!0-9]*}; t_closed=$((10#$x))
    fi
    i=$((i+1))
  done
  t_wait=$t_closed
  if [ "$t_wo" != - ]; then m=$(minutes_between "$t_wo" "$NOW"); t_wait=$((t_wait + ${m:-0})); fi
  if [ -n "${2:-}" ] && [ "$2" != - ] && [ $((10#$2)) -gt "$t_wait" ]; then t_wait=$((10#$2)); fi
  t_clock=-; t_work=-
  if [ "$t_opened" != - ]; then m=$(minutes_between "$t_opened" "$NOW"); [ -z "$m" ] || t_clock=$m; fi
  if [ "$t_started" != - ]; then
    m=$(minutes_between "$t_started" "$NOW"); m=${m:-0}
    m=$((m - (t_wait > t_before ? t_wait - t_before : 0)))
    t_work=$((m > 0 ? m : 0))
  elif [ "$t_clock" != - ]; then
    m=$((t_clock - t_wait)); t_work=$((m > 0 ? m : 0))
  fi
}
# stage_facts "<todo line>" <work>: d_stages d_slices d_built from the " | stage log" field ("-" when there is none)
stage_facts() {
  local log out
  d_stages=-; d_slices=-; d_built=-
  split_line "$1"
  log=""
  if fld_re '^stage log '; then log=${FLD:10}; fi
  [ -n "$log" ] || return 0
  IFS=$'\t' read -r d_stages d_slices d_built <<< "$(printf '%s\n' "$log" | awk -v done="$2" '
    { n = split($0, e, ", ")
      for (k = 1; k <= n; k++) {
        m[k] = e[k]; sub(/^.* /, "", m[k]); m[k] += 0
        v = e[k]; sub(/ [0-9]+$/, "", v)
        w[k] = v; sub(/ .*$/, "", w[k]); f[k] = v; if (index(v, " ")) sub(/^[^ ]* /, "", f[k]); else f[k] = ""
      }
      for (k = 1; k <= n; k++) {
        if (k > 1 && w[k] == w[k - 1]) continue
        end = done; for (j = k + 1; j <= n; j++) if (w[j] != w[k]) { end = m[j]; break }
        if (end == "-" || end == "") end = m[k]
        d = end - m[k]; if (d < 0) d = 0
        if (!(w[k] in dur)) order[++no] = w[k]
        dur[w[k]] += d
      }
      st = ""; for (k = 1; k <= no; k++) st = st (k > 1 ? "," : "") order[k] ":" dur[order[k]]
      fm = ""; sl = ""
      for (k = 1; k <= n; k++) if (w[k] == "workers") {
        if (fm == "") fm = m[k]
        if (f[k] ~ /^[0-9]+\/[0-9]+$/) { i = f[k]; sub(/\/.*$/, "", i); i += 0
          if (!(i in seen)) { seen[i] = 1; if (i >= 1) sl = sl (sl == "" ? "" : ",") (m[k] - fm) } }
      }
      b = ""
      for (k = 1; k <= n && b == ""; k++) if (w[k] == "report") b = m[k]
      for (k = 1; k <= n && b == ""; k++) if (w[k] == "e2e") b = m[k]
      printf "%s\t%s\t%s\n", (st == "" ? "-" : st), (sl == "" ? "-" : sl), (b == "" ? "-" : b) }')"
}
# dkey "<line>" <key>: that key of the line's data block (can be "-"); nothing when the line has no block
dkey() {
  local w
  case "$1" in *' | data '*) ;; *) return 0;; esac
  if [ "$2" = by ]; then   # by= is the last key and holds the name as written, to the end of the line
    case "$1" in *' by='*) printf '%s' "${1##* by=}";; esac
    return 0
  fi
  for w in ${1##* | data }; do
    case "$w" in "$2="*) printf '%s' "${w#*=}"; return 0;; esac
  done
}
# old_num "<text>" est|actual: n of the first "est <n>m" / "actual <n>m" in the text
old_num() {
  local rest=$1 d
  while :; do
    case "$rest" in *"$2 "*) rest=${rest#*"$2 "};; *) return 0;; esac
    d=${rest%%[!0-9]*}
    case "$d" in '') continue;; esac
    case "${rest#"$d"}" in m*) printf '%s\n' "$d"; return 0;; esac
  done
}
# est and clock (the old "actual") of an old completed line "... | est <n>m actual <n>m"
old_est()   { old_num "${1##* | }" est; }
old_clock() { old_num "${1##* | }" actual; }
# lines of agent_completed.txt that have a data block with a work number (dropped lines never count)
time_data() {
  local l n=0 c=0 big="" re='(^| )work=[0-9]+( |$)'
  if [ -f "$DONE" ] && [ -r "$DONE" ]; then
    while IFS= read -r l || [ -n "$l" ]; do   # up to 600 lines here, a longer file goes to one awk start
      c=$((c+1))
      if [ "$c" -gt 600 ]; then big=1; break; fi
      case "$l" in *'| dropped: '*) continue;; *' | data '*) ;; *) continue;; esac
      if [[ ${l##* | data } =~ $re ]]; then n=$((n+1)); fi
    done < "$DONE"
    if [ -z "$big" ]; then echo "$n"; else
      awk '/[|] dropped: /{next} sub(/^.* [|] data /,"") && /(^| )work=[0-9]+( |$)/{n++} END{print n+0}' "$DONE"
    fi
  else
    awk '/[|] dropped: /{next} sub(/^.* [|] data /,"") && /(^| )work=[0-9]+( |$)/{n++} END{print n+0}' "$DONE"
  fi
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
DATA_FMT='%-14s %-30s %-10s %-6s %-4s %-4s %5s %5s %5s %6s %7s %7s %5s %6s %5s %4s %5s\n'
DATA_FMT_WHAT='%-14s %-30s %-10s %-6s %-4s %-4s %5s %5s %5s %6s %7s %7s %5s %6s %5s %4s %5s %5s %5s %5s %s %s %s\n'   # data --what: est0 typed built stages slices, then what
DATA_WHAT=
DATA_SEEN="
"
# dload "<line>": d_* from the data block of the line ("-" for a key it does not say)
dload() {
  local w k rest
  dreset
  rest=${1##* | data }
  case "$rest" in *' by='*) d_by=${rest##* by=}; rest=${rest% by=*};; esac
  for w in $rest; do
    k=${w%%=*}
    case " $DATA_KEYS " in *" $k "*) [ "$k" = by ] || eval "d_$k=\${w#*=}";; esac
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
        "${d_files:--}" "${d_lines:--}" "${d_tests:--}" "${d_adds:--}" "${d_guess:--}" "${d_est0:--}" "${d_typed:--}" \
        "${d_built:--}" "${d_stages:--}" "${d_slices:--}" "${what:--}"
    else
      printf "$DATA_FMT" "${d_repo// /_}" "${name// /_}" "${date// /_}" "${d_type:--}" "${d_lane:--}" "${d_mock:--}" \
        "${d_est:--}" "${d_work:--}" "${d_wait:--}" "${d_clock:--}" "${d_bounces:--}" "${d_workers:--}" \
        "${d_files:--}" "${d_lines:--}" "${d_tests:--}" "${d_adds:--}" "${d_guess:--}"
    fi
  done < "$rp/agent_completed.txt"
}
# repos_list: the real paths of this repo, the world.json territories; each once, a missing folder skipped
repos_list() {
  local city="${AGENT_CITY_HOME:-${HOME:-}/.claude/agent-city}" p rp all seen="
"
  all=$(printf '%s\n' "$ROOT"; world_repos "$city/world.json")
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    rp=$(cd "$p" 2>/dev/null && pwd -P) || { echo "skipped: no such folder: $p" >&2; continue; }
    case "$seen" in *"
$rp
"*) continue;; esac
    seen="$seen$rp
"
    printf '%s\n' "$rp"
  done <<< "$all"
}
# data [--what] [<repo path>...]
data_run() {
  local p list a i=$#
  DATA_WHAT=
  while [ "$i" -gt 0 ]; do   # --what may stand anywhere; the rest are repo paths
    a=$1; shift; i=$((i - 1))
    case "$a" in --what) DATA_WHAT=1;; *) set -- "$@" "$a";; esac
  done
  if [ -n "$DATA_WHAT" ]; then
    printf "$DATA_FMT_WHAT" repo name date type lane mock est work wait clock bounces workers files lines tests adds guess est0 typed built stages slices what
  else
    printf "$DATA_FMT" repo name date type lane mock est work wait clock bounces workers files lines tests adds guess
  fi
  list=$(repos_list)
  while IFS= read -r p; do [ -z "$p" ] || data_repo "$p"; done <<< "$list"
  for p in "$@"; do data_repo "$p"; done
}

# --- estimate, backtest, retrain
# est_py <estimate|backtest|retrain> [option...]: the table of data --what into agent_estimate.py (python3 only).
# The model file is the project root's agent_estimate.txt, today is the date of $NOW (AGENT_FAKE_NOW works).
# est_settings: the three estimate numbers in one python3 start (agent-roots.sh settings_read), once per run; called in the main
# shell, so the values are still there when est_py reads them inside $(...)
est_settings() {
  if declare -F settings_read >/dev/null 2>&1; then
    case "${_AP_SET_KEYS:- }" in *" estimate_target_pct "*) ;; *) settings_read estimate_target_pct estimate_bias_min estimate_big_min;; esac
  fi
  return 0
}
est_py() {
  local cmd="$1" rows
  shift
  command -v python3 >/dev/null 2>&1 || refuse "$cmd: python3 is needed and was not found"
  rows=$(data_run --what 2>/dev/null) || true
  est_settings
  AGENT_ESTIMATE_REPO=$(repo_name "$ROOT") \
  AGENT_ESTIMATE_TARGET_PCT=$(conf_num estimate_target_pct 1 100 || true) \
  AGENT_ESTIMATE_BIAS_MIN=$(conf_num estimate_bias_min 1 1000 || true) \
  AGENT_ESTIMATE_BIG_MIN=$(conf_num estimate_big_min 1 10000 || true) \
  python3 "$AF_DIR/agent_estimate.py" "$cmd" "$ROOT/agent_estimate.txt" "${NOW%% *}" "$@" <<< "$rows"
}
# stale_skip: when this session runs an older plugin than the newest installed, print the one skip line and return 0
stale_skip() {
  local v="$AF_DIR/agent-version.sh" run newest rest
  [ -f "$v" ] || return 1
  IFS=$'\t' read -r run newest rest < <("$v" check 2>/dev/null) || return 1
  [ -n "$run" ] && [ -n "$newest" ] || return 1
  echo "retrain skipped: $run is older than installed $newest"
}
# the retrain after todo done: one verdict line only when it ran; any failure is swallowed (one short line)
retrain_auto() {
  local out rc=0
  if stale_skip; then return 0; fi
  est_settings
  out=$(est_py retrain --auto 2>/dev/null) || rc=$?
  if [ "$rc" -ne 0 ]; then echo "estimate retrain: failed"
  elif [ -n "$out" ]; then printf '%s\n' "$out"
  fi
  est_py measure >/dev/null 2>&1 || true     # one entry of the list "measures"; a failure never stops todo done
  return 0
}

# --- the estimator after todo done runs in the background (fix order 2B): a queue file, one detached runner
# est_gitdir: the absolute git common dir of the project root; fails when there is none
est_gitdir() {
  local d
  if [ -n "${AP_ROOTS_GITDIR:-}" ] && [ "${AP_ROOTS_ROOT:-}" = "$ROOT" ]; then d=$AP_ROOTS_GITDIR   # roots_read asked git already
  else
    d=$(git -C "$ROOT" rev-parse --git-common-dir 2>/dev/null) || return 1
    case "$d" in /*) ;; *) d="$ROOT/$d";; esac
  fi
  (cd "$d" 2>/dev/null && pwd -P)
}
# est_lock <git dir>: takes the lock dir (a dead pid's lock is taken over); returns 1 when a live runner holds it
est_lock() {
  local lock="$1/agent_estimate.lock" pid try
  for try in 1 2; do
    if mkdir "$lock" 2>/dev/null; then return 0; fi
    pid=$(cat "$lock/pid" 2>/dev/null) || pid=
    if [ -z "$pid" ] || kill -0 "$pid" 2>/dev/null; then return 1; fi
    rm -rf "$lock"
  done
  return 1
}
# est_gate: a test hook, read only when AGENT_ESTIMATE_GATE names a file: write this pid to <file>.reached, then wait
# while the file exists (at most 120 s). Unset (production): nothing happens.
est_gate() {
  local n=0
  [ -n "${AGENT_ESTIMATE_GATE:-}" ] || return 0
  printf '%s\n' "$$" > "$AGENT_ESTIMATE_GATE.reached" 2>/dev/null || true
  while [ -e "$AGENT_ESTIMATE_GATE" ] && [ "$n" -lt 1200 ]; do sleep 0.1; n=$((n + 1)); done
  return 0
}
# est_runner: oldest queue file first: the retrain when due, then one measures entry; every line goes to the log
est_runner() {
  local gd q lock f
  gd=$(est_gitdir) || return 0
  q="$gd/agent_estimate.queue"; lock="$gd/agent_estimate.lock"
  mkdir -p "$q" "$lock" 2>/dev/null || true
  printf '%s\n' "$$" > "$lock/pid"
  while :; do
    while f=$(ls "$q" 2>/dev/null | sort | head -n 1) && [ -n "$f" ]; do
      est_gate
      rm -f "$q/$f"
      retrain_auto || true
    done
    rm -rf "$lock"
    [ -n "$(ls "$q" 2>/dev/null | head -n 1)" ] || break
    est_lock "$gd" || break
    printf '%s\n' "$$" > "$lock/pid"
  done
  return 0
}
# est_after_done: queue one run and start the runner unless one lives; AGENT_ESTIMATE_WAIT=1 runs it here, verdict printed
est_after_done() {
  local gd q
  if [ "${AGENT_ESTIMATE_WAIT:-}" = 1 ]; then retrain_auto; return 0; fi
  gd=$(est_gitdir) || return 0
  q="$gd/agent_estimate.queue"
  mkdir -p "$q" 2>/dev/null || return 0
  printf '%s\n' "$NOW" > "$q/$(date +%s)-$$-$RANDOM" 2>/dev/null || return 0
  est_lock "$gd" || return 0
  ( trap '' HUP; exec "$0" estimate-runner </dev/null >>"$gd/agent_estimate.log" 2>&1 ) </dev/null >/dev/null 2>&1 &
  printf '%s\n' "$!" > "$gd/agent_estimate.lock/pid" 2>/dev/null || true
  return 0
}

# the sweep after the last task closes: agent_todo.txt has no non-blank line, agent_worktree.txt has no
# working or final line and no human-direct line, and this is the main manager (or a takeover). Prints the
# sweep's --short lines. Any failure of it is swallowed: it never changes the exit code of todo done.
# has_text <file>: a line with a character that is not a space (grep -q '[^[:space:]]'); false for a file that cannot be read
has_text() {
  local l re='[^[:space:]]'
  [ -f "$1" ] && [ -r "$1" ] || return 1
  while IFS= read -r l || [ -n "$l" ]; do
    if [[ $l =~ $re ]]; then return 0; fi
  done < "$1"
  return 1
}
sweep_after_last_task() {
  local busy l
  [ "${AGENT_CLEANUP_DONE:-}" = 1 ] && return 0
  if has_text "$TODO"; then return 0; fi
  if [ -f "$WT" ] && [ -r "$WT" ]; then
    busy=0
    while IFS= read -r l || [ -n "$l" ]; do
      split_line "$l"
      if [ "${LF[2]:-}" = working ] || [ "${LF[2]:-}" = final ] || [ "${LF[1]:-}" = "task manager, human-direct" ]; then busy=$((busy + 1)); fi
    done < "$WT"
  else
    busy=$(awk -F' \\| ' '$3 == "working" || $3 == "final" || $2 == "task manager, human-direct" { n++ } END { print n + 0 }' "$WT" 2>/dev/null) || return 0
  fi
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
  if [ -z "$step" ] && [ -z "$wsf" ]; then   # no old option: the board's numbers (agent_forecast), one answer
    command -v python3 >/dev/null 2>&1 || refuse "eta: python3 is needed and was not found"
    python3 "$AF_DIR/agent_board.py" --root "$PROJECT_ROOT" --state-dir "$STATE_DIR" --cwd "$PROJECT_CWD" \
      --now "$NOW" --lang en --eta "$name" --wait "$wt" || exit $?
    return 0
  fi
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
  hpid=$(agent_pid 2>/dev/null); case "$hpid" in ''|*[!0-9]*) hpid=-;; esac
  hhost=${AGENT_FAKE_HOST:-$(hostname -s 2>/dev/null || hostname)}
  awk -F' \\| ' -v p="$PROJECT_CWD" -v t="task: $task" 'BEGIN { OFS = " | " }
    $1 == p && $2 == "task manager, human-direct" {
      has = 0; val = ""
      for (i = 3; i <= NF; i++) if ($i ~ /^session /) { has = 1; val = substr($i, 9) }
      if (!has || val == sid) { $3 = t; seen = 1 }
    }
    { print }
    END { if (!seen) print p, "task manager, human-direct", t, "since " now, "pid " pid, "host " host, "session " sid }' \
    pid="$hpid" host="$hhost" sid="$sid" now="$NOW" "$WT" > "$WT.tmp" && mv "$WT.tmp" "$WT"
  repo=$(basename "$PROJECT_ROOT")
  echo "helper task: $task -> \"$repo Helper - $task\" from the human's next prompt"
}

# session_end_files <sid>: remove the session's files in the shared git dir; prints how many files went
session_end_files() {
  local sid=$1 n=0 f
  for f in "$PROJECT_GITDIR/agent_started_$sid" "$PROJECT_GITDIR/agent_rules_$sid" "$PROJECT_GITDIR/agent_compact_$sid" \
           "$PROJECT_GITDIR/agent_quiz_$sid" "$PROJECT_GITDIR/agent_stale_$sid" "$PROJECT_GITDIR/agent_autoclear_$sid" \
           "$PROJECT_GITDIR/agent_helper_task_$sid" "$PROJECT_GITDIR/agent_helper_title_$sid" "$PROJECT_GITDIR/agent_point_${sid}_"*; do
    case "$f" in "$PROJECT_GITDIR/agent_point_${sid}_"*) case "${f#"$PROJECT_GITDIR/agent_point_${sid}_"}" in *_*) continue;; esac;; esac   # the moment has no "_": agent_point_abc_def_watch is session abc_def's
    if [ -f "$f" ] || [ -L "$f" ]; then rm -f "$f" 2>/dev/null && n=$((n + 1)); fi
  done
  rmdir "$PROJECT_GITDIR/agent_started_$sid.lock" "$PROJECT_GITDIR/agent_rules_$sid.lock" 2>/dev/null || true
  echo "$n"
}
# session_end_valid <sid>: letters, digits, _ and - only, starting with a letter or digit
session_end_valid() { case "$1" in ''|[!A-Za-z0-9]*|*[!A-Za-z0-9_-]*) return 1;; esac; return 0; }
# session_end_lines <sid>: drop the human-direct lines naming that session; prints how many went
session_end_lines() {
  local sid=$1 before after
  [ -f "$WT" ] || { echo 0; return; }
  before=$(awk 'END { print NR }' "$WT")
  awk -F' \\| ' -v s="session $sid" '{ if ($2 == "task manager, human-direct") for (i = 3; i <= NF; i++) if ($i == s) next; print }' "$WT" > "$WT.tmp.$$" \
    || { rm -f "$WT.tmp.$$"; echo 0; return; }
  after=$(awk 'END { print NR }' "$WT.tmp.$$")
  if [ "$after" -lt "$before" ]; then mv "$WT.tmp.$$" "$WT"; else rm -f "$WT.tmp.$$"; fi
  echo $((before - after))
}
# session_end <sid> | --dead [--dry-run]
session_end() {
  local sid host rows nums="" row nr path pid ssid dry="" nf nl
  [ $# -ge 1 ] || usage
  if [ "$1" != --dead ]; then
    [ $# -eq 1 ] || usage
    session_end_valid "$1" || refuse "session-end: the session id must be letters, digits, _ and - only (got: $1)"
    nf=$(session_end_files "$1"); nl=$(session_end_lines "$1")
    echo "session-end $1: $nf files, $nl lines removed"
    return 0
  fi
  shift
  case "${1:-}" in --dry-run) dry=1; shift;; esac
  [ $# -eq 0 ] || usage
  [ -f "$WT" ] || return 0
  host=${AGENT_FAKE_HOST:-$(hostname -s 2>/dev/null || hostname)}
  rows=$(awk -F' \\| ' -v h="$host" '$2 == "task manager, human-direct" {
    pid = ""; hh = ""; s = "-"; since = ""
    for (i = 3; i <= NF; i++) {
      if ($i ~ /^pid [0-9]+$/) pid = substr($i, 5)
      else if ($i ~ /^host /) hh = substr($i, 6)
      else if ($i ~ /^session /) s = substr($i, 9)
      else if ($i ~ /^since /) since = substr($i, 7)
    }
    if (pid != "" && hh == h) print NR "\t" $1 "\t" pid "\t" s
    else if (pid == "" && hh == "" && s == "-" && since != "") print NR "\t" $1 "\t-\t" since }' "$WT")
  while IFS=$'\t' read -r nr path pid ssid; do
    [ -n "$nr" ] || continue
    if [ "$pid" = - ]; then   # board-fast-lane rule 4: no pid, no session id: nothing to find a process by; 12 h old or more is FLAGGED, never removed (only the main manager removes a human-direct line, after the owner says it is finished)
      m=$(minutes_between "$ssid" "$NOW")
      [ -n "$m" ] && [ "$m" -ge 720 ] || continue
      echo "flag: human-direct line $path: no pid, no session id, $((m / 60))h old: close it with agent-file.sh worktree rm when the owner says it is finished"
      continue
    fi
    kill -0 "$pid" 2>/dev/null && continue
    nums="$nums $nr "
    echo "human-direct line $path (pid $pid gone)"
    [ -n "$dry" ] && continue
    if session_end_valid "$ssid"; then session_end_files "$ssid" >/dev/null; fi
  done <<< "$rows"
  if [ -n "$nums" ] && [ -z "$dry" ]; then
    awk -v nums="$nums" 'index(nums, " " NR " ") == 0' "$WT" > "$WT.tmp.$$" && mv "$WT.tmp.$$" "$WT"
  fi
  return 0
}

# helper-join "<task>": a human-direct Helper takes a task from the main manager (or reports DONE to it): its
# folder's human-direct line becomes a normal task line (check-blocks C20)
helper_join() {
  local task="${1:-}" pane="${ORCA_TERMINAL_HANDLE:-}" sid="${CLAUDE_CODE_SESSION_ID:-}"
  role_read
  [ "$role" = second ] || refuse "helper-join: only a human-direct Helper (a second session) can join; this session is: $role${AGENT_ROLE:+ ($AGENT_ROLE)}"
  [ -n "$task" ] || refuse "helper-join: needs the task name"
  if bad_text "$task"; then refuse "helper-join: the task must not hold \" | \" or a line break"; fi
  [ -n "$pane" ] || pane=-
  case "$sid" in ''|*[!A-Za-z0-9_-]*) sid=-;; esac
  case "$pane" in *[!A-Za-z0-9_.:-]*) pane=-;; esac
  touch "$WT"
  awk -F' \\| ' -v p="$PROJECT_CWD" -v t="$task" -v now="$NOW" -v pane="$pane" -v sid="$sid" 'BEGIN { OFS = " | " }
    $1 == p && $2 == "task manager, human-direct" {
      has = 0; val = ""
      for (i = 3; i <= NF; i++) if ($i ~ /^session /) { has = 1; val = substr($i, 9) }
      if (!has || val == sid) { print p, t, "working", "since " now, "pane " pane, "session " sid; seen = 1; next }
    }
    { print }
    END { if (!seen) print p, t, "working", "since " now, "pane " pane, "session " sid }' "$WT" > "$WT.tmp" && mv "$WT.tmp" "$WT"
  echo "helper-join: $task (pane $pane, session $sid): a normal agent now; the merge of its last task closes this pane"
}

# --- todo wait, todo where
# bad_text "<text>": true when it holds " | " or a line break (it would break the line it goes into)
bad_text() {
  case "$1" in *' | '*|*$'\n'*|*$'\r'*) return 0;; esac
  return 1
}
# todo_wait <name> on <kind> ["<note>"] [--who <name>] [--after <task>] | todo_wait <name> off
todo_wait() {
  local name="${1:-}" verb="${2:-}" kind note line open since m closed=0 new="" ssince="" ins=0 hasst=0 from
  local who="" after="" havewho=0 haveafter=0 havenote=0 opt run="" oldrun=""
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
      [ $# -ge 3 ] && shift 3
      note=""
      while [ $# -gt 0 ]; do
        case "$1" in
          --who|--after)
            opt="$1"
            [ $# -ge 2 ] || refuse "todo wait: $opt needs a name"
            case "$2" in
              ''|*[![:space:]]*) ;;
              *) refuse "todo wait: $opt needs a name, not blank text";;
            esac
            [ -n "$2" ] || refuse "todo wait: $opt needs a name, not an empty one"
            case "$2" in --*) refuse "todo wait: $opt needs a name (got: $2)";; esac
            if bad_text "$2"; then refuse "todo wait: the $opt value must not hold \" | \" or a line break"; fi
            if [ "$opt" = --who ]; then
              [ "$havewho" -eq 0 ] || refuse "todo wait: --who given twice"
              [ "$kind" != queue ] || refuse "todo wait: --who does not go with queue (use --after)"
              havewho=1; who="$2"
            else
              [ "$haveafter" -eq 0 ] || refuse "todo wait: --after given twice"
              [ "$kind" = queue ] || refuse "todo wait: --after goes only with queue"
              haveafter=1; after="$2"
            fi
            shift 2;;
          --*) refuse "todo wait: unknown option: $1";;
          *)
            [ "$havenote" -eq 0 ] || refuse "todo wait: too many arguments; quote the note"
            havenote=1; note="$1"; shift;;
        esac
      done
      if bad_text "$note"; then refuse "todo wait: the note must not hold \" | \" or a line break"; fi
      new="waiting $kind since $NOW${note:+: $note}";;
    off)
      [ $# -eq 2 ] || refuse "todo wait: off takes nothing after it"
      [ -n "$open" ] || refuse "todo wait: $name is not waiting";;
    *) refuse "todo wait: on or off (got: ${verb:-nothing})";;
  esac
  if [ -n "$open" ]; then
    since=$(printf '%s' "$open" | sed -n 's/^waiting [^ ]* since \([0-9]\{4\}-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]\).*/\1/p')
    m=$(minutes_between "$since" "$NOW"); closed=${m:-0}
    ssince=$(printf '%s\n' "$line" | awk -F' \\| ' '{ for (i = 4; i <= NF; i++) if ($i ~ /^stage .* since [0-9]/) { sub(/^.* since /, "", $i); print $i; exit } }')
    if [ -n "$ssince" ]; then
      hasst=1; from="$since"
      if [[ "$ssince" > "$since" ]]; then from="$ssince"; fi
      m=$(minutes_between "$from" "$NOW"); ins=${m:-0}
    fi
    if [ "$verb" = on ]; then
      oldrun=$(printf '%s\n' "$line" | awk -F' \\| ' '{ for (i = 4; i <= NF; i++) if ($i ~ /^wait run since /) { sub(/^wait run since /, "", $i); print $i; exit } }')
      oldrun=$(printf '%s' "$oldrun" | sed -n 's/^\([0-9]\{4\}-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]\).*/\1/p')
      run="${oldrun:-$since}"
    fi
  fi
  if [ "$verb" = on ]; then
    [ -z "$who" ] || new="$new | who $who"
    [ -z "$after" ] || new="$new | after $after"
    [ -z "$run" ] || new="$new | wait run since $run"
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
        if (i >= 4 && i != oi && ($i ~ /^who / || $i ~ /^after / || $i ~ /^wait run since /)) continue
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

# todo_cross <name> <repo>
todo_cross() {
  local name="${1:-}" repo="${2:-}" line
  [ -n "$name" ] || refuse "todo cross: needs a todo name"
  line=$(first "$TODO" "$name")
  [ -n "$line" ] || refuse "no todo line named: $name"
  [ -n "$repo" ] || refuse "todo cross: needs a repo"
  [ $# -le 2 ] || refuse "todo cross: too many arguments; the repo has no space"
  case "$repo" in *[[:space:]]*) refuse "todo cross: the repo has no space (got: $repo)";; esac
  if bad_text "$repo"; then refuse "todo cross: the repo must not hold \" | \" or a line break"; fi
  NEW="cross $repo" awk -F' \\| ' -v OFS=' | ' -v k="$name" '
    $1 == k && !hit {
      hit = 1; wi = 0
      for (i = 4; i <= NF; i++) if (!wi && $i ~ /^cross /) wi = i
      if (wi) $wi = ENVIRON["NEW"]; else $(NF + 1) = ENVIRON["NEW"]
    }
    { print }' "$TODO" > "$TODO.tmp" && mv "$TODO.tmp" "$TODO"
  echo "todo cross: $name -> $repo"
}

# --- park, worker (agent_state.txt of the folder this session is in)
STATE_FILE="$STATE_DIR/agent_state.txt"
# todo_beat <name> "<work>m <text>"
todo_beat() {
  local name="${1:-}" text="${2:-}" line cur
  [ -n "$name" ] || refuse "todo beat: needs a todo name"
  [ $# -le 2 ] || refuse "todo beat: too many arguments; quote the text"
  line=$(first "$TODO" "$name")
  [ -n "$line" ] || refuse "no todo line named: $name"
  state_text "todo beat" "$text"
  cur=$(printf '%s\n' "$line" | awk -F' \\| ' '{ for (i = 4; i <= NF; i++) if ($i ~ /^beat /) { print substr($i, 6); exit } }')
  if [ "$cur" != "$text" ]; then
    NEW="beat $text" awk -F' \\| ' -v OFS=' | ' -v k="$name" '
      $1 == k && !hit {
        hit = 1; wi = 0
        for (i = 4; i <= NF; i++) if (!wi && $i ~ /^beat /) wi = i
        if (wi) $wi = ENVIRON["NEW"]; else $(NF + 1) = ENVIRON["NEW"]
      }
      { print }' "$TODO" > "$TODO.tmp" && mv "$TODO.tmp" "$TODO"
  fi
  echo "todo beat: $name -> $text"
}

# last_waiting "<line>": the date time of the last " | waiting <kind> since YYYY-MM-DD HH:MM" in the line
last_waiting() {
  local t=$1 c re='^[^ ]* since ([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2})'
  while [[ $t == *" | waiting "* ]]; do
    c=${t##* | waiting }
    if [[ $c =~ $re ]]; then printf '%s\n' "${BASH_REMATCH[1]}"; return 0; fi
    t=${t% | waiting *}
  done
  return 0
}
# todo_stage <name> <stage> [<i>/<m>]
STAGE_WORDS="brief register mock tests workers verify push report e2e merge"
todo_stage() {
  local name="${1:-}" stage="${2:-}" frac="${3:-}" line val cur i m wt_here= csince tsince keep started wn wo swork f sfield hasst hasstart
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
  share_pull_gate "$name"
  line=$(first "$TODO" "$name")
  if [ -z "$line" ] && [ -z "$wt_here" ]; then refuse "no todo line named: $name"; fi
  if [ -n "$line" ]; then
    split_line "$line"
    cur=""; sfield=""; hasst=""; hasstart=""
    for ((i = 3; i < LFN; i++)); do   # the first stage field (not the stage log): its value and its since; a stage or started field
      f=${LF[$i]}
      if [[ $f == "stage "* && $f != "stage log "* ]]; then
        if [ -z "$hasst" ]; then hasst=1; sfield=$f; cur=${f#stage }; cur=${cur%% since *}; fi
      elif [[ $f == "started "* ]]; then hasstart=1
      fi
    done
    if [ "$cur" != "$val" ]; then
      tsince=$NOW; keep=0; started=
      if [ -z "$cur" ] && [ -z "$hasst" ] && [ -z "$hasstart" ]; then
        wn=0
        if fld_re '^waited ([0-9]+)m$'; then wn=$((10#${BASH_REMATCH[1]})); fi
        wo=$(last_waiting "$line")
        if [ -n "$wo" ]; then m=$(minutes_between "$wo" "$NOW"); wn=$((wn + ${m:-0})); fi
        started="started $NOW"
        if [ "$wn" -gt 0 ]; then started="$started after ${wn}m waited"; fi
        swork=0
      else
        todo_times "$line"; swork=$t_work; [ "$swork" != - ] || swork=0
      fi
      if [ "${cur%% *}" = "$stage" ]; then
        csince=""
        case "$sfield" in *' since '*) csince=${sfield##* since };; esac
        if [ -n "$csince" ]; then tsince=$csince; keep=1; fi
      fi
      NEW="stage $val since $tsince" STARTED="$started" ENTRY="$val $swork" awk -F' \\| ' -v OFS=' | ' -v k="$name" -v keep="$keep" '
        $1 == k && !hit {
          hit = 1; wi = 0; li = 0; si = 0
          for (i = 4; i <= NF; i++) {
            if (!li && $i ~ /^stage log /) li = i
            else if (!wi && $i ~ /^stage /) wi = i
            if (!si && $i ~ /^started /) si = i
          }
          if (wi) $wi = ENVIRON["NEW"]
          else { if (ENVIRON["STARTED"] != "") $(NF + 1) = ENVIRON["STARTED"]; $(NF + 1) = ENVIRON["NEW"] }
          if (li) $li = $li ", " ENVIRON["ENTRY"]
          else {   # the log goes right before the started field, else right before the stage field
            at = 0
            for (i = 4; i <= NF; i++) if (!at && $i ~ /^started /) at = i
            if (!at) for (i = 4; i <= NF; i++) if (!at && $i ~ /^stage / && $i !~ /^stage log /) at = i
            for (i = NF; i >= at; i--) $(i + 1) = $i
            $at = "stage log " ENVIRON["ENTRY"]
          }
          if (!keep) {
            n = 0
            for (i = 1; i <= NF; i++) if (!(i >= 4 && ($i ~ /^waited in stage [0-9]+m$/ || $i ~ /^beat /))) out[++n] = $i
            s = out[1]
            for (i = 2; i <= n; i++) s = s OFS out[i]
            print s; next
          }
        }
        { print }' "$TODO" > "$TODO.tmp" && mv "$TODO.tmp" "$TODO"
      # the slip flag: the board's p50 clock of this line, kept as " | p50 <time> at <now>" (no forecast: the line stays)
      if [ -z "$wt_here" ] && command -v python3 >/dev/null 2>&1; then
        local p50
        p50=$(python3 "$AF_DIR/agent_board.py" --root "$PROJECT_ROOT" --state-dir "$STATE_DIR" --cwd "$PROJECT_CWD" \
          --now "$NOW" --lang en --p50-of "$name" 2>/dev/null) || p50=
        case "$p50" in
          [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\ [0-9][0-9]:[0-9][0-9])
            NEW="p50 $p50 at $NOW" awk -F' \\| ' -v OFS=' | ' -v k="$name" '
              $1 == k && !hit {
                hit = 1; n = 0
                for (i = 1; i <= NF; i++) if (!(i >= 4 && $i ~ /^p50 [0-9-]+ [0-9:]+ at /)) out[++n] = $i
                out[++n] = ENVIRON["NEW"]
                s = out[1]
                for (i = 2; i <= n; i++) s = s OFS out[i]
                print s; next
              }
              { print }' "$TODO" > "$TODO.tmp" && mv "$TODO.tmp" "$TODO";;
        esac
      fi
    fi
  fi
  if [ -n "$wt_here" ]; then
    cur=; csince=
    if [ -f "$STATE_FILE" ]; then
      cur=$(awk -v p="STAGE $name: " 'index($0, p) == 1 { s = substr($0, length(p) + 1); sub(/ \| since .*$/, "", s); print s; exit }' "$STATE_FILE")
      csince=$(awk -v p="STAGE $name: " 'index($0, p) == 1 { s = $0; if (sub(/^.* \| since /, "", s)) print s; exit }' "$STATE_FILE")
    fi
    if [ "$cur" != "$val" ]; then
      if ! grep -qF "WORK START $name | " "$STATE_FILE" 2>/dev/null; then state_append "WORK START $name | $NOW"; fi   # the start of the work, once (heartbeat counts from it)
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
  lang=$(setting language 2>/dev/null) || lang=en
  case "$lang" in zh) ;; *) lang=en;; esac
  python3 "$AF_DIR/agent_questions.py" "$PROJECT_ROOT" "$STATE_DIR" "$PROJECT_CWD" "$NOW" "$lang" "$@"
}
# state_py <command> [args...]: agent_state.py does the work (python3 only)
state_py() {
  command -v python3 >/dev/null 2>&1 || refuse "state: python3 is needed and was not found"
  python3 "$AF_DIR/agent_state.py" "$PROJECT_ROOT" "$STATE_DIR" "$NOW" "$@"
}
state_run() {
  case "${1:-}" in
    add|trim) state_py "$@";;
    *) refuse "state: unknown command: ${1:-} (add or trim)";;
  esac
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
# conf_num <key> <low> <high>: the whole number of <key> (a setting or a constant, read by `setting`), if in range
conf_num() {
  local v
  v=$(setting "$1" 2>/dev/null) || v=""
  v=${v//[[:space:]]/}
  if is_num "$v" && [ "${#v}" -le 9 ] && [ $((10#$v)) -ge "$2" ] && [ $((10#$v)) -le "$3" ]; then echo $((10#$v)); return 0; fi
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
    if [ -z "$sec" ]; then sec=$(conf_num board_watch_sec 1 3600) || refuse "board: --watch needs <sec>: board_watch_sec cannot be read"; fi
    is_num "$sec" && [ "${#sec}" -le 9 ] && [ $((10#$sec)) -ge 1 ] || refuse "board: --watch takes a whole number of seconds from 1 (got: $sec)"
    sec=$((10#$sec))
  fi
  command -v python3 >/dev/null 2>&1 || refuse "board: python3 is needed and was not found"
  share_pull
  lang=$(setting language 2>/dev/null) || lang=en
  case "$lang" in zh) ;; *) lang=en;; esac
  host=${AGENT_FAKE_HOST:-$(hostname -s 2>/dev/null || hostname)}
  if [ -n "$watch" ]; then
    exec python3 "$AF_DIR/agent_board.py" --root "$PROJECT_ROOT" --state-dir "$STATE_DIR" --cwd "$PROJECT_CWD" \
      --now "$NOW" --lang "$lang" --host "$host" ${self:+--self} --watch "$sec"
  fi
  python3 "$AF_DIR/agent_board.py" --root "$PROJECT_ROOT" --state-dir "$STATE_DIR" --cwd "$PROJECT_CWD" \
    --now "$NOW" --lang "$lang" --host "$host" ${self:+--self}
}

# the risk type of a todo line: fields 4+ only ("level <A-D>", or an old "level <0-4>"); nothing when none
todo_line_level() {
  split_line "$1"
  if fld_re '^level ([0-9]+|[A-D])$'; then printf '%s\n' "${FLD#level }"; fi
}
# a type or an old level -> the type letter (0=A 1=B 2,3=C 4=D); empty when it is neither
risk_type() {
  case "$1" in
    A|a|0) echo A;; B|b|1) echo B;; C|c|2|3) echo C;; D|d|4) echo D;; *) echo "";;
  esac
}
risk_rank() { case "$1" in A) echo 0;; B) echo 1;; C) echo 2;; D) echo 3;; esac; }
# todo level "<name>" <A-D>: the line's type field, set in place (only goes up); 0-4 still accepted, stored as a letter
todo_level() {
  local name="${1:-}" n="${2:-}" line old oldt
  [ $# -eq 2 ] || refuse "todo level: usage: todo level \"<name>\" <A-D>  (old 0-4 still read)"
  n=$(risk_type "$n"); [ -n "$n" ] || refuse "todo level: the type wants one of A B C D (got: ${2:-nothing})"
  line=""; [ ! -f "$TODO" ] || line=$(first "$TODO" "$name")
  [ -n "$line" ] || refuse "no todo line named: $name"
  old=$(todo_line_level "$line")
  if [ -n "$old" ]; then
    oldt=$(risk_type "$old"); [ -n "$oldt" ] || oldt=A
    [ "$(risk_rank "$n")" -ge "$(risk_rank "$oldt")" ] || refuse "todo level: $name: type only goes up ($old -> $n)"
    if [ "$n" = "$oldt" ]; then echo "todo level: $name already type $n"; return 0; fi
  fi
  NAME="$name" LV="$n" awk -F' \\| ' '
    !done && $1 == ENVIRON["NAME"] {
      done = 1; lv = "level " ENVIRON["LV"]; out = ""; hasl = 0
      for (i = 4; i <= NF; i++) if ($i ~ /^level ([0-9]+|[A-D])$/) hasl = 1
      gi = 0; ei = 0
      for (i = 4; i <= NF; i++) { if (!gi && $i ~ /^guess [0-9]+m$/) gi = i; if (!ei && $i ~ /^est [0-9]+m$/) ei = i }
      at = gi ? gi : (ei ? ei : 3)
      for (i = 1; i <= NF; i++) {
        f = $i
        if (i >= 4 && f ~ /^level ([0-9]+|[A-D])$/) f = lv
        out = out (i > 1 ? " | " : "") f
        if (!hasl && i == at) out = out " | " lv
      }
      print out; next
    }
    {print}' "$TODO" > "$TODO.tmp" && mv "$TODO.tmp" "$TODO"
  echo "todo level: $name ${old:--} -> $n"
}

# --- check blocks (agent_checks.py does the work)
checks_py() {
  command -v python3 >/dev/null 2>&1 || refuse "${1:-checks}: python3 is needed and was not found"
  python3 "$AF_DIR/agent_checks.py" "$PROJECT_ROOT" "$STATE_DIR" "$NOW" "$@"
}
# next: the memory rule (section 25) reads the numbers from agent-room.sh; the rest is agent_checks.py
next_run() {
  local cap nums
  [ $# -eq 0 ] || refuse "next: takes nothing after it"
  share_pull
  cap=$(conf_num max_usage_percent 1 100) || cap=80
  if nums=$(cd "$PROJECT_ROOT" && "$AF_DIR/agent-room.sh" numbers 2>/dev/null </dev/null) && [ "$(printf '%s\n' "$nums" | wc -w | tr -d ' ')" -eq 4 ]; then
    checks_py next $nums "$cap"
  else
    checks_py next unknown
  fi
}
# batch_done <line> <name>: the last open line of a batch is done -> say what comes next (check-blocks C48)
batch_done() {
  local b left
  split_line "$1"
  b=""
  if fld_re '^batch '; then b=${FLD#batch }; fi
  [ -n "$b" ] || return 0
  left=$(awk -F' \\| ' -v b="$b" '{for (i = 4; i <= NF; i++) if ($i == "batch " b) {n++; break}} END {print n + 0}' "$TODO")
  [ "$left" -eq 0 ] || return 0
  echo "batch $b: all merged: agent-promote.sh --sync, then the full suite: agent-nightly.sh --start"
}
# released_after <name>: close the queue wait of every open line queued after <name>
# released_list "<names>": the same lines as released_after for names already read (one name a line)
released_list() {
  local n
  while IFS= read -r n; do
    [ -n "$n" ] || continue
    todo_wait "$n" off >/dev/null
    echo "released: $n"
  done <<< "$1"
}
released_after() {
  local n list
  list=$(checks_py after-list "$1" 2>/dev/null) || return 0
  while IFS= read -r n; do
    [ -n "$n" ] || continue
    todo_wait "$n" off >/dev/null
    echo "released: $n"
  done <<< "$list"
}

case "${1:-}:${2:-}" in
  helper-task:*)
    [ $# -ge 2 ] || usage
    helper_task "$2";;
  helper-join:*)
    [ $# -ge 2 ] || usage
    helper_join "$2";;
  session-end:*)
    shift; session_end "$@";;
  todo:add)
    shift 2; guess=""; why=""; haswhy=""; level=""; rest=(); checks=""; scope=""; builder=""; target=""; batch=""; oquote=""; otime=""; omeans=""; oquestion=""; orelay=""; oleader=""
    # --checks is normalised (python3) in the one start that plans the blocks; a refusal that would have come after its
    # normalising still waits for it: flush_norm runs it first (every refusal below, the usage, the owner words)
    norm_raw=""; norm_pend=""
    flush_norm() { if [ -n "$norm_pend" ]; then norm_pend=""; checks=$(checks_py norm "$norm_raw") || exit 1; fi; }
    refuse() { flush_norm; echo "$1" >&2; exit 1; }
    while [ $# -gt 0 ]; do   # --guess <m> may stand anywhere after "todo add"; the other args keep their order
      if [ "$1" = "--guess" ]; then
        [ $# -ge 2 ] && is_num "$2" && [ "${#2}" -le 9 ] && [ $((10#$2)) -ge 1 ] || refuse "todo add: --guess wants a whole number, 1 or more (got: ${2:-nothing})"
        guess=$((10#$2)); shift 2
      elif [ "$1" = "--why" ]; then
        [ $# -ge 2 ] && [ -n "$2" ] || refuse "todo add: --why needs a reason"
        if bad_text "$2"; then refuse "todo add: the --why value must not hold \" | \" or a line break"; fi
        why=$2; haswhy=1; shift 2
      elif [ "$1" = "--level" ]; then
        level=$(risk_type "${2:-}"); [ -n "$level" ] || refuse "todo add: --level wants one of A B C D (got: ${2:-nothing})"
        shift 2
      elif [ "$1" = "--checks" ]; then
        [ $# -ge 2 ] || refuse "todo add: --checks needs a list of blocks"
        flush_norm; norm_raw=$2; norm_pend=1
        shift 2
      elif [ "$1" = "--scope" ] || [ "$1" = "--builder" ]; then
        [ $# -ge 2 ] && [ -n "$2" ] || refuse "todo add: $1 needs a value"
        if bad_text "$2"; then refuse "todo add: the $1 value must not hold \" | \" or a line break"; fi
        if [ "$1" = "--scope" ]; then scope=$2; else builder=$2; fi
        shift 2
      elif [ "$1" = "--target" ]; then
        case "${2:-}" in production|working) target=$2;; *) refuse "todo add: --target wants production or working (got: ${2:-nothing})";; esac
        shift 2
      elif [ "$1" = "--owner-quote" ] || [ "$1" = "--time" ] || [ "$1" = "--means" ] || [ "$1" = "--question" ] || [ "$1" = "--relayed-from" ] || [ "$1" = "--relayed-by-leader" ]; then
        [ $# -ge 2 ] && [ -n "$2" ] || refuse "todo add: $1 needs a value"
        case "$1" in --owner-quote) oquote=$2;; --time) otime=$2;; --means) omeans=$2;; --relayed-from) orelay=$2;; --relayed-by-leader) oleader=$2;; *) oquestion=$2;; esac
        shift 2
      elif [ "$1" = "--batch" ]; then
        [ $# -ge 2 ] && [ -n "$2" ] || refuse "todo add: --batch needs a name"
        if bad_text "$2"; then refuse "todo add: the --batch value must not hold \" | \" or a line break"; fi
        batch=$2; shift 2
      else rest+=("$1"); shift; fi
    done
    set -- todo add ${rest[@]+"${rest[@]}"}
    if [ $# -lt 5 ]; then flush_norm; fi
    need 5 "$@"
    if [ -n "$haswhy" ] && [ -z "$guess" ]; then refuse "todo add: --why goes with --guess"; fi
    if [ -n "$guess" ] && [ -z "$why" ] && is_num "${6:-}" && [ "${#6}" -le 9 ] && [ $((10#$6)) -eq "$guess" ]; then
      refuse "todo add: est $((10#$6)) is the --guess; give the number the estimate printed, or --why \"<reason>\""
    fi
    if [ "$target" = production ]; then   # the direct path is bound to the owner's words, verified at once (F1)
      flush_norm
      checks_py owner-words "$3" "$oquote" "$otime" "$omeans" "$oquestion" "$orelay" "$oleader" || exit 1
    elif [ -n "$oquote$otime$omeans$oquestion$orelay$oleader" ]; then refuse "todo add: --owner-quote, --means, --question, --time, --relayed-from and --relayed-by-leader belong to --target production"
    fi
    # the blocks this name ever had are planned again (F11); the owner name comes in the same python3 start
    if command -v python3 >/dev/null 2>&1; then
      plan_in=$checks; norm_flag=0
      if [ -n "$norm_pend" ]; then plan_in=$norm_raw; norm_flag=1; norm_pend=""; fi
      plan_out=$(checks_py plan-add-owner "$3" "$plan_in" "$PWD" "$norm_flag") || exit 1
      checks=${plan_out%%$'\n'*}; owner=${plan_out#*$'\n'}
      [ "$owner" != "$plan_out" ] || owner=user
    else
      flush_norm
      checks=$(checks_py plan-add "$3" "$checks") || exit 1
      owner=user
    fi
    drop "$TODO" "$3"
    what="$5"
    [ -n "${6:-}" ] && what="$5 | est ${6}m"
    [ -z "$guess" ] || what="$what | guess ${guess}m"
    [ -z "$why" ] || what="$what | why $why"
    [ -z "$level" ] || what="$what | level $level"
    [ -z "$checks" ] || what="$what | checks $checks"
    [ -z "$scope" ] || what="$what | scope $scope"
    [ -z "$builder" ] || what="$what | builder $builder"
    [ -z "$target" ] || what="$what | target $target"
    [ -z "$batch" ] || what="$what | batch $batch"
    by="${7:-$WHO}"
    append "$TODO" "$3 | $4 | $what | opened $NOW | by $by | owner ${owner:-user}"
    echo "todo added: $3";;
  todo:done)
    need 3 "$@"; name="$3"; line=$(first "$TODO" "$name")
    [ -n "$line" ] || { echo "no todo line named: $name" >&2; exit 1; }
    share_gate "$name" who
    shift 3
    case "${1:-}" in --*) ;; *) [ $# -eq 0 ] || shift;; esac   # the "<result>" text is not stored
    dreset; d_files=; d_lines=
    done_opts "$@"
    miss=; [ "$d_type" != - ] || miss=" --type"; [ "$d_lane" != - ] || miss="$miss --lane"
    [ -z "$miss" ] || echo "todo done: warning: no${miss} given (the estimator learns less from this line)" >&2
    counted=yes; [ -n "$d_files" ] || { counted=; d_files=-; d_lines=-; }
    split_line "$line"
    what=${LF[2]:-}
    est=$(old_num "$line" est)
    opened=$(last_opened "$line")
    clock=; [ -z "$opened" ] || { now_ep; clock=$(minutes_between "$opened" "$NOW"); }
    d_repo=$(repo_name "$ROOT"); d_est=${est:--}; d_clock=${clock:--}
    d_typed=$d_work                                # the typed --work is kept as typed, the label is measured
    todo_times "$line" "$d_wait"
    if [ "$t_work" != - ]; then
      d_work=$t_work; d_wait=$t_wait
      if [ "$d_typed" != - ] && [ "$d_clock" != - ] && [ $((10#$d_typed)) -gt "$d_clock" ]; then
        echo "todo done: warning: --work ${d_typed}m is more than the clock ${d_clock}m; work ${d_work}m is stored, the typed number is kept as typed=$((10#$d_typed))" >&2
      fi
    fi
    [ "$d_typed" = - ] || d_typed=$((10#$d_typed))
    split_line "$line"
    d_est0=""; d_added=""; d_guess=""
    if fld_re '^est0 ([0-9]+)m$'; then d_est0=${BASH_REMATCH[1]}; fi
    d_est0=${d_est0:-$d_est}
    if fld_re '^added ([0-9]+)m$'; then d_added=${BASH_REMATCH[1]}; fi
    d_added=${d_added:--}
    if fld_re '^guess ([0-9]+)m$'; then d_guess=${BASH_REMATCH[1]}; fi
    d_guess=${d_guess:--}
    stage_facts "$line" "$d_work"
    d_level=$(todo_line_level "$line"); d_level=${d_level:--}
    if [ -n "$SHARE_WHO" ]; then d_by=$SHARE_WHO   # the shared-todo check already asked python3 for it
    else d_by=$(PYTHONPATH="$AF_DIR" python3 -c 'import sys, agent_conf; print(agent_conf.user_name(sys.argv[1]))' "$PWD" 2>/dev/null) || d_by=user
    fi
    d_by=${d_by:-user}
    date="${NOW%% *}"
    drop "$TODO" "$name"; append "$DONE" "$date | $name | $what | $(dblock)"
    # task-end (its removals, stored owner words and planned blocks end: G2, G4), the list of the lines queued after this
    # one, and the state trim: ONE python3 start (the trim only when no line was queued after this one)
    tail_out=""; tail_te=""; tail_names=""; tail_trim=""; tail_ran=""; tail_mark=""
    if command -v python3 >/dev/null 2>&1; then
      tail_out=$(checks_py task-end-after "$name" 1) || true
      case "$tail_out" in *$'\001A'*) tail_mark=1;; esac   # no marker: the batch died, the separate steps run below
      tail_te=${tail_out%%$'\001A'*}
      tail_names=${tail_out#*$'\001A'}
      [ -n "$tail_mark" ] || { tail_te=""; tail_names=""; }
      case "$tail_names" in *$'\001T'*) tail_trim=${tail_names#*$'\001T'}; tail_names=${tail_names%%$'\001T'*}; tail_ran=1;; esac
      [ -z "$tail_te" ] || printf '%s' "$tail_te"
    else
      checks_py task-end done "$name" || true     # python3 missing: the refusal that ends the run
    fi
    echo "todo done: $name"
    if [ -n "$tail_mark" ]; then released_list "$tail_names"; else released_after "$name"; fi
    batch_done "$line" "$name"
    [ -n "$counted" ] || echo "files and lines: not counted (no --merge or --range)"
    echo "TIME DATA: $(time_data) of $TIME_DATA_GOAL"
    # the finished task no longer counts as open: trim the state file (silent unless lines moved; a refusal is a warning)
    if [ -n "$tail_ran" ]; then
      [ -z "${tail_trim#$'\n'}" ] || printf '%s\n' "${tail_trim#$'\n'}"
    elif command -v python3 >/dev/null 2>&1; then python3 "$AF_DIR/agent_state.py" "$PROJECT_ROOT" "$STATE_DIR" "$NOW" trim --auto || true; fi
    est_after_done || true
    sweep_after_last_task;;
  todo:wait)
    shift 2; todo_wait "$@";;
  todo:where)
    shift 2; todo_where "$@";;
  todo:cross)
    shift 2; todo_cross "$@";;
  todo:level)
    shift 2; todo_level "$@";;
  todo:checks)
    shift 2; checks_py todo-checks "$@";;
  todo:target)
    shift 2; checks_py todo-target "$@";;
  todo:builder)
    shift 2; checks_py todo-builder "$@";;
  todo:est)
    shift 2; checks_py todo-est "$@";;
  check:*)
    shift; checks_py check "$@";;
  checks:gate)
    shift 2; checks_py gate "$@";;
  checks:gather)
    shift 2; checks_py gather "$@";;
  next:*)
    shift; next_run "$@";;
  edge:add)
    shift 2; checks_py edge-add "$@";;
  model:ok|model:check)
    cmd=$2; shift 2; checks_py "model-$cmd" "$@";;
  todo:take)
    [ $# -eq 3 ] || refuse "todo take: usage: todo take <task>"
    command -v python3 >/dev/null 2>&1 || refuse "todo take: python3 is needed and was not found"
    exec python3 "$AF_DIR/agent_share.py" "$ROOT" take "$3";;
  todo:assign)
    [ $# -eq 4 ] || refuse "todo assign: usage: todo assign <task> <name>"
    command -v python3 >/dev/null 2>&1 || refuse "todo assign: python3 is needed and was not found"
    exec python3 "$AF_DIR/agent_share.py" "$ROOT" assign "$3" "$4";;
  todo:stage)
    shift 2; todo_stage "$@";;
  todo:beat)
    shift 2; todo_beat "$@";;
  park:*)
    shift; park_run "$@";;
  worker:*)
    shift; worker_run "$@";;
  board:*)
    shift; board_run "$@";;
  questions:*)
    shift; questions_run "$@";;
  state:*)
    shift; state_run "$@";;
  files:*)
    command -v python3 >/dev/null 2>&1 || refuse "files: python3 is needed and was not found"
    case "${2:-}" in
      show|sync|move|set|restore) ;;
      *) usage;;
    esac
    shift
    exec python3 "$AF_DIR/agent_share.py" "$ROOT" "$@";;
  todo:drop)
    need 5 "$@"; line=$(first "$TODO" "$3")
    [ -n "$line" ] || { echo "no todo line named: $3" >&2; exit 1; }
    what=$(printf '%s\n' "$line" | awk -F' \\| ' '{print $3}')
    est=$(printf '%s' "$line" | grep -o 'est [0-9][0-9]*m' | head -1 | sed 's/est //;s/m//')
    [ -n "$est" ] || est="-"
    [ "$est" = "-" ] && est_disp="-" || est_disp="${est}m"
    date="${NOW%% *}"
    drop "$TODO" "$3"; append "$DONE" "$date | $3 | $what | est $est_disp actual - | dropped: $4"
    checks_py task-end drop "$3" || true        # its removals and stored owner words end (G2, G4)
    echo "todo dropped: $3";;
  idea:add)
    need 3 "$@"; by=$(python3 "$AF_DIR/agent_share.py" "$ROOT" name 2>/dev/null | head -n 1 || true)
    append "$IDEAS" "$3 | $NOW | by ${by:-$WHO}"
    echo "idea added";;
  idea:list)
    if [ -s "$IDEAS" ]; then
      awk '{ tag = ""
             if (match($0, / \| by [^|]+( \| kept [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9])?$/)) {
               x = substr($0, RSTART); sub(/^ \| by /, "", x); sub(/ \| kept [0-9-]+$/, "", x); sub(/[ \t]+$/, "", x)
               if (x !~ /^(main|task-manager|task_manager|manager|worker|deputy|helper|fast-lane-deputy|merge-deputy|interior-designer)$/) tag = "[" x "] "
             }
             printf "%6d\t%s%s\n", NR, tag, $0 }' "$IDEAS"
    else echo "(empty)"; fi;;
  idea:rm)
    need 3 "$@"; n="$3"
    case "$n" in ''|*[!0-9]*) echo "no idea number $n" >&2; exit 1;; esac
    line=$(sed -n "${n}p" "$IDEAS")
    [ -n "$line" ] || { echo "no idea number $n" >&2; exit 1; }
    sed "${n}d" "$IDEAS" > "$IDEAS.tmp" && mv "$IDEAS.tmp" "$IDEAS"
    printf 'idea %s removed: %s\n' "$n" "$(printf '%s' "$line" | cut -c1-60)";;
  idea:keep)
    need 4 "$@"; n="$3"
    case "$n" in ''|*[!0-9]*) echo "no idea number $n" >&2; exit 1;; esac
    line=$(sed -n "${n}p" "$IDEAS")
    [ -n "$line" ] || { echo "no idea number $n" >&2; exit 1; }
    awk -v n="$n" -v d="${NOW%% *}" 'NR==n { if ($0 ~ / \| kept [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) $0 = substr($0, 1, length($0) - 10) d; else $0 = $0 " | kept " d } { print }' "$IDEAS" > "$IDEAS.tmp" && mv "$IDEAS.tmp" "$IDEAS"
    printf 'idea %s kept: %s\n' "$n" "$(printf '%s' "$line" | cut -c1-60)";;
  worktree:set)
    need 5 "$@"; old=$(first "$WT" "$3"); since=$(printf '%s' "$old" | awk -F' \\| ' '{print $4}')
    [ -n "$since" ] || since="since $NOW"
    drop "$WT" "$3"; append "$WT" "$3 | $4 | $5 | $since"
    echo "worktree $5: $3";;
  worktree:rm)
    need 3 "$@"; drop "$WT" "$3"; echo "worktree removed: $3";;
  show:*)
    for f in "$TODO" "$DONE" "$IDEAS" "$WT"; do
      echo "=== $(basename "$f") ==="
      if [ -s "$f" ]; then
        case "$f" in
          "$TODO") sed -E 's/^(.* \| owner ([^|]*[^| ])( \| .*)?)$/\1 [\2]/' "$f";;
          "$DONE") sed -E '/ data .* by=-$/!s/^(.* data .* by=(.+))$/\1 [\2]/' "$f";;
          *) cat "$f";;
        esac
      else echo "(empty)"; fi
      echo
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
  heartbeat:*)
    # heartbeat "<task>" <step 0-7> "<what runs now>": the work is computed (the todo line, else WORK START);
    # the five-word form (typed minutes) still works; with a known start the computed minutes win
    hb_typed=
    case $# in
      4) hb_raw=$4;;
      5) hb_typed=$4; hb_raw=$5;;
      *) refuse "heartbeat: usage: heartbeat \"<task>\" <step 0-7> \"<what runs now>\" (or with typed minutes: heartbeat \"<task>\" <step 0-7> <work minutes> \"<what runs now>\")";;
    esac
    case "$2" in ''|*[[:space:]:]*) refuse "heartbeat: the task name must be one word without a colon";; esac
    case "$3" in [0-7]) ;; *) refuse "heartbeat: the step is a whole number from 0 to 7 (got: $3)";; esac
    if [ $# -eq 5 ]; then is_num "$hb_typed" && [ "${#hb_typed}" -le 9 ] || refuse "heartbeat: the work minutes are a whole number (got: $hb_typed)"; fi
    hb_text=$(printf '%s' "$hb_raw" | tr '\r\n' '  ' | sed 's/^ *//; s/ *$//')
    [ -n "$hb_text" ] || refuse "heartbeat: say what runs now (the text is empty)"
    hb_work=
    if [ -f "$TODO" ] && [ -n "$(first "$TODO" "$2")" ] && command -v python3 >/dev/null 2>&1; then
      hb_work=$(python3 "$AF_DIR/agent_board.py" --root "$PROJECT_ROOT" --state-dir "$STATE_DIR" --cwd "$PROJECT_CWD" \
        --now "$NOW" --lang en --work-of "$2" 2>/dev/null) || hb_work=
      is_num "$hb_work" || hb_work=
    fi
    if [ -z "$hb_work" ] && [ -f "$STATE_FILE" ]; then
      hb_start=$(awk -v p="WORK START $2 | " 'index($0, p) == 1 { print substr($0, length(p) + 1); exit }' "$STATE_FILE")
      if [ -n "$hb_start" ] && [ -n "$(to_epoch "$hb_start")" ]; then hb_work=$(minutes_between "$hb_start" "$NOW"); hb_work=${hb_work:-0}; fi
    fi
    if [ -z "$hb_work" ]; then
      [ $# -eq 5 ] || refuse "heartbeat: no start is known for $2 (no todo line, no WORK START line); give the minutes: heartbeat \"$2\" $3 <work minutes> \"<what runs now>\""
      hb_work=$((10#$hb_typed))
    elif [ $# -eq 5 ]; then
      hb_d=$((hb_work - 10#$hb_typed)); [ "$hb_d" -ge 0 ] || hb_d=$((-hb_d))
      if [ "$hb_d" -gt 5 ]; then echo "heartbeat: work ${hb_work}m from the start, not the typed $((10#$hb_typed))m" >&2; fi
    fi
    mkdir -p "$STATE_DIR" 2>/dev/null
    if [ -s "$STATE_FILE" ] && [ -n "$(tail -c 1 "$STATE_FILE")" ]; then printf '\n' >> "$STATE_FILE"; fi
    append "$STATE_FILE" "HEARTBEAT $2: step $3 of 7, work $((10#$hb_work))m, $hb_text | $NOW"
    echo "heartbeat: $2 step $3 of 7";;
  tell:*)
    need 3 "$@"; [ $# -eq 3 ] || usage
    command -v python3 >/dev/null 2>&1 || refuse "tell: python3 is needed and was not found"
    # C53: the line before "TELL OK ..." reminds the main manager to add minutes when the message adds work
    tell_rc=0
    tell_out=$(python3 "$AF_DIR/agent_watch.py" tell "$PROJECT_ROOT" "$NOW" "$2" "$3") || tell_rc=$?
    tell_hint="if this message adds work: agent-file.sh todo est \"$2\" +<minutes>"
    case "$tell_hint" in
      *\\*) printf '%s\n' "$tell_out" | awk -v h="$tell_hint" '{ if ($0 ~ /^TELL OK / && prev != h) print h; print; prev = $0 }';;
      *)   # the same filter without a start: the hint line before a "TELL OK " line, unless that line follows it already
        tell_prev=""
        while IFS= read -r tell_l || [ -n "$tell_l" ]; do
          if [[ $tell_l == "TELL OK "* ]] && [ "$tell_prev" != "$tell_hint" ]; then printf '%s\n' "$tell_hint"; fi
          printf '%s\n' "$tell_l"
          tell_prev=$tell_l
        done <<< "$tell_out";;
    esac
    exit "$tell_rc";;
  backfill:*)
    shift
    case "${1:-}" in ''|--*) backfill_text "$@";; *) backfill_name "$@";; esac;;
  data:*)
    shift; data_run "$@";;
  repos:*)
    repos_list;;
  estimate-runner:*)
    est_runner;;
  estimate-queue:*)
    est_after_done; exit 0;;
  estimate:*|backtest:*|retrain:*)
    cmd="$1"; shift
    if [ "$cmd" = retrain ] && stale_skip; then exit 0; fi
    est_py "$cmd" "$@";;
  eta:*)
    [ $# -ge 2 ] || usage
    case "$2" in --*) usage;; esac
    shift; eta_run "$@";;
  *) usage;;
esac
