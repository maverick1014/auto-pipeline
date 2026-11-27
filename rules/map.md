# Map: scripts and commands
Read when: you need which script, skill or command does a job. Rules: PRINCIPLES.md and rules/.

Agent skills: `/auto-pipeline:dispatch` (route one task), `/auto-pipeline:merge` (the reviewer and the check deputy, then the merge deputy), `/auto-pipeline:cloud-pack`, `/auto-pipeline:slim-test-case` (slim a repo's tests), `/auto-pipeline:slim-markdown`, `/auto-pipeline:teacher-teach-me`. A second session in a repo becomes a task manager by itself (W10).

```
Scripts, not agents (cost no tokens):
  bin/agent-start.sh   RAM/CPU guard, prints the rules, 36-question quiz gate, main-manager lock
  bin/agent-nightly.sh  the nightly run of all tests: gates nothing, records selection misses, --release-ok
  bin/agent-test-run.sh  every test run: reserves its measured memory, a monitor watches it (S3, S5)
  bin/agent-room.sh  the memory gate: check, reserve, release, list, relief, measure-pane
  bin/agent-level.sh   the blocks a diff triggers (R8): agent-level.sh check --base <ref>
  bin/agent_blocks.py  the one table of blocks and triggers (R8)
  bin/agent-owner-order.sh  relayed owner orders between repo managers: `line` prints the OWNER ORDER header (sender), `verify` checks the words are a typed owner prompt in the sender's transcript (receiver)
  bin/agent-file.sh    the only writer of agent_*.txt
  bin/agent_estimate.py  the time estimator: learns work minutes from the finished tasks, backtests against the rubric; prints a p50 and a p85
  bin/agent-settings.sh  show the settings (/plugin -> Configure changes them)
  bin/agent-resume.sh    one command to bring the pipeline back after a restart
  bin/agent-cleanup.sh   the main manager's sweep: removes merged, clean, idle worktrees and branches; lists the rest in one table
  bin/agent-housekeep.sh the main manager's pass every housekeep_interval_min from the `agent-watch.sh --all` loop: worktree, todo and ideas files, related repos read only, then the cleanup sweep; writes one HOUSEKEEP block
  bin/agent-watch.sh     `agent-watch.sh --all`: one background watch for every task manager, local or remote (pane + agent_state.txt); exits on a report, question, stall or lost machine
  bin/agent-file.sh tell `agent-file.sh tell <task> "<msg>"`: long text to a task manager, a block in its agent_state.txt + one pointer line
  bin/agent-init.sh      sets a project up: the four task files, .secrets/, .gitignore lines, AGENTS.md, and it prints the permissions block
  bin/agent-cloud-pack.sh  lays this pipeline into a repo as plain files, for cloud sessions
  bin/agent-city.sh       starts/stops the agent city visualiser, a local server
  bin/agent-city-shim     the ~/.local/bin/agent-city command; runs the newest installed plugin's agent-city.sh
  bin/agent-city-hook.sh  hook that feeds the city; off costs a `test -f`, on appends one JSON line
  bin/agent-close-case.sh  UserPromptSubmit hook: tells a released or replaced main manager once
  bin/agent-keyword.sh  UserPromptSubmit hook: a keyword in the prompt adds one line pointing to its skill or rule (E4)
  bin/agent-board-warn.sh  hook: a new or changed board warning into the main manager's context
  bin/agent_board.py     the todo board: one table of every open task, wait, owner to-do and parked question
  bin/agent_questions.py  the question list: every question pending on the owner, as a chat list, JSON or an Artifact page; records the answers
  bin/agent-questions-page.html  the page template (one page grouped by task, lettered options, answer bar)
  bin/agent-name.sh       SessionStart + UserPromptSubmit hook: names the session by role (W6; a human-direct one is `<repo> Helper - <Task Name>`), also the Orca tab
  bin/agent-session-end.sh  SessionEnd hook: a session leaves nothing behind (its git-dir markers, a Helper's line and files; agent-file.sh session-end)
  bin/agent-guard.sh     hook: records every Agent launch and orca pane on the board, refuses a manager's launch that names no open todo task when the Todo before agent setting is on; off records only
  bin/agent-promote.sh   the working branch to production, only on the owner's verified words (--owner-quote), `--task` for a direct merge, `--sync` for production into the working branch
  bin/agent-runtime.sh   which runtime this agent is in (orca, plain, cloud) and the browser; the one place that knows
  bin/agent-resources.sh  RAM and CPU readers, sourced by other scripts
  bin/agent-autoclear.sh  the waiter behind the auto /clear: save prompt, /clear, /goal, only after the human has been quiet (S8)
  bin/agent-release.sh   builds, checks and pushes the `release` branch, one commit per version
  bin/agent-statusline.sh  the Claude Code status line: one line per running task
  bin/agent-roots.sh     the two roots every script needs (project and plugin), sourced
  bin/agent-version.sh   UserPromptSubmit hook + check: a session running an older plugin than installed gets one STALE PLUGIN line; the start text names old scopes; an old version never retrains
```

```
./bin/agent-start.sh             # rules, resources, quiz. No work until PASS
./bin/agent-resume.sh            # runs by itself at startup (Auto resume setting on); run by hand only if you turned that off
./bin/agent-settings.sh          # show the settings, no agent (change them in /plugin -> Installed -> auto-pipeline -> Configure)
bin/agent-file.sh time              # est, work, wait, clock of every finished task
bin/agent-file.sh data              # the same data of every repo on this machine, one table
bin/agent-file.sh eta <name>        # work left as a p50 and a p85 clock time (the board's Done by), and when the human is needed next
bin/agent-file.sh estimate ... [--guess <m>]   # work minutes of a new task, with p50, p85 and the 3 nearest past tasks; its number is the est, --guess is your own minutes (est equal to it is refused without --why)
bin/agent-file.sh backtest          # estimator, blend and rubric on the finished tasks, who wins
bin/agent-file.sh retrain           # learn the estimate again from the finished tasks (after every 10 new ones, also by itself); a worse model is never kept
bin/agent-file.sh next              # the queued tasks that can start now, then the board warnings
bin/agent-file.sh checks gate <task> --dir <path>  # the merge gate
bin/agent-nightly.sh --status | --misses | --release-ok   # the nightly run of all tests: its state, the selection misses, the release check
bin/agent-file.sh board             # the todo board: open tasks, waits on the owner, owner to-dos, parked questions
bin/agent-file.sh questions         # the question list: every question pending on the owner (--self, --json, --page <file>, --url <url>, answer <id> "<answer>")
bin/agent-city.sh install-shim      # one time: puts the agent-city command in ~/.local/bin; nothing installs it by itself, the init skill offers it
agent-city start                    # agent city visualiser, off by default, costs almost nothing
```
