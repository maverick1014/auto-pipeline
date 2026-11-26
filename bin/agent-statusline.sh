#!/usr/bin/env bash
# agent-statusline.sh — the Claude Code statusLine command: one line per task that runs with a
# stage (name, progress bar, stage, done by) or waits on the owner or on others; queue, hold and
# not started tasks fold into one "+N tasks" line; 5 lines at most (see agent_board.py
# --statusline). When it can read the terminal width ($AGENT_STATUSLINE_WIDTH, $COLUMNS, /dev/tty) it lays
# every open task out in 3, 2 or 1 columns (statusline-wide); width unknown: one column as before. Reads the session JSON on stdin; prints those lines or nothing; always exit 0;
# writes no file. Installed by `agent-settings.sh statusline on`.
exec python3 "$(dirname "$0")/agent_board.py" --statusline
