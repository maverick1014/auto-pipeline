# test-slim

Owner order 2026-11-25: slim the tests of this repo ("this is very important"). Tests only, no product code.

## Before (main 08eb27e)

| | files | tests | lines |
|---|---|---|---|
| all | 102 | 4165 | 58,661 |
| Agent City | 41 | 1131 | 21,538 |
| bin/ (for scale) | | | 29,714 |

- 79 of 102 files are named after a task, 23 after a script. Classes of one script sit in up to 8 files.
- Cost of one test on pc2: `ScriptRepo()` 0.11 s (5 git starts + a 40-file plugin copy). A script start 0.09 s (`agent-file.sh show`) to 2.0 s (`agent-start.sh`: resume 0.8 s, cleanup sweep 0.4 s, ~25 python3 starts).
- Same pin in many files, e.g. the quiz count and its PASS line in test_agent_cleanup, test_bypass_mode, test_decider_floor, test_risk_levels.

## Target layout: module -> feature

One file per script or module, one class per feature. Text pins of PRINCIPLES.md, skills, agents, README and hooks go to `test_rules_text.py`, one class per rule section, each pin once.

| Target file | Module | Fed from (today) | When |
|---|---|---|---|
| test_agent_file.py | agent-file.sh: todo, idea, worktree, data, time, stage, park | agent_file, agent_file_data, agent_file_idea_keep, agent_progress | now |
| test_agent_state.py | agent_state.py: state add, state trim | state_trim | now |
| test_agent_estimate.py | agent_estimate.py | agent_estimate, agent_estimate_blend | now |
| test_agent_watch.py | agent-watch.sh, agent_watch.py: --all, tell, report, housekeep timer | agent_watch, watch_all, watch_tell, watch_report, watch_housekeep, watch_board (watch parts) | now |
| test_agent_autoclear.py | agent-autoclear.sh | auto_clear | now |
| test_agent_statusline.py | agent-statusline.sh | agent_statusline, statusline_vertical, statusline_wide, statusline_refresh, watch_board (status line parts); board_waiting parts later | now |
| test_agent_housekeep.py | agent-housekeep.sh | agent_housekeep, housekeep_rows | now |
| test_agent_cleanfiles.py | agent_cleanfiles.py | agent_cleanfiles, completed_keep | now |
| test_agent_name.py | agent-name.sh | agent_name, agent_name_rules | now |
| test_agent_owner_order.py | agent-owner-order.sh | agent_owner_order, owner_relay_text | now |
| test_agent_settings.py | agent-settings.sh, agent_conf.py | agent_conf, settings_readers, permission_setting, model_suffix, five_fixes; settings_configure later | now |
| test_agent_update.py | agent_update.py | auto_update | now |
| test_agent_version.py | agent-version.sh | stale_plugin_guard | now |
| test_agent_resume.py | agent-resume.sh | agent_resume, resume parts of five_fixes, model_suffix, permission_setting | now |
| test_agent_runtime.py, test_agent_resources.py, test_agent_questions.py, test_agent_keyword.py, test_agent_cloud_pack.py, test_two_roots.py | one module each | as is | now |
| test_agent_close_case.py | agent-close-case.sh | agent_close_case, session_clean (hook parts) | now |
| test_agent_start.py | agent-start.sh: resources, quiz, seat, take-over, release, clean, section E hook, YOU line | agent_start, agent_main_seat, agent_session_clean, output_hook, bypass_mode, decider_floor | after check-blocks |
| test_agent_board.py | agent_board.py | agent_board, board_waiting, watch_board (board rows) | after check-blocks |
| test_agent_guard.py | agent-guard.sh | board_trust, guard_var_path | after check-blocks |
| test_agent_cleanup.py | agent-cleanup.sh | agent_cleanup, check_cleanup | after check-blocks |
| test_agent_init.py | agent-init.sh | agent_init, check_init | after check-blocks |
| test_agent_level.py | agent-level.sh, check blocks | risk_levels, comment_shape, check_* | after check-blocks |
| test_agent_release.py | agent-release.sh | as is | after check-blocks |
| test_rules_text.py | rule text pins | output_rules, decider_floor, plugin_layout, every *Text/*Principles/*Skill class | now (free classes), rest after check-blocks |
| test_agent_city_*.py (about 5 files) | server, page, hook, script, office | 41 files | after city-office-2 |

## How a slice is done

1. Classes move with `movecls.py` (body and method names unchanged, the helpers they use come along). The audit matches old and new tests by method name.
2. A duplicate check goes only with a twin: a row in the table below. No twin, no removal.
3. Never weakened: rules (PRINCIPLES, skills, quiz), the core scripts (agent-file, guard, start, watch, board, level/blocks, release, cleanup, settings), money, secrets, permissions. Text pins stay; only a second copy of the same pin goes.
4. Speed: a class whose tests only read one fixture becomes a `SharedScriptCase` (tests/sharedrepo.py): one repo per class, each script run once in `prepare()`, a guard fails any test that changes the shared folder. Tests that write keep one repo per test (`ScriptCase`).
5. Every new repo copies a per-process seeded template instead of five git starts (tests/scripthelp.py, after check-blocks).
6. Before a slice: the test list of the touched files. After it: the audit (moved + removed-with-twin = before) and the slice's tests pass.

## Two processes

```
python3 tests/run2.py            # every test file, 2 processes, split by tests/timings.txt
python3 tests/run2.py --time     # each file alone, prints file, tests, seconds; rewrites tests/timings.txt
python3 -m unittest discover -s tests   # still works, one process
```

The split deals files slowest first to the process with the least seconds so far.

## Removed checks

| Old file::test | Why it is a duplicate | Twin file::test that still checks it |
|---|---|---|

## Before and after

To fill: files, tests, lines, seconds for all tests (pc2, same run), 10 slowest files.
