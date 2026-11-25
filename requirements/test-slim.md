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
| test_agent_name.py::TestRoles.test_main_manager_with_no_lock | default start with no lock: "project Manager"; the twin's "startup" case is the same input, then resume and fork | test_agent_name.py::TestSources.test_startup_resume_and_fork_get_the_name |
| test_agent_name.py::TestHelperTaskCommand.test_sets_the_name_of_this_session | helper-task "SST Calculation" gives "project Helper - SST Calculation"; the twin's first case is exactly that, then 17 more | test_agent_name.py::TestHelperTaskCommand.test_the_name_is_cleaned |
| test_agent_session_clean.py::TestTheHookText.test_a_report_text_does_not_ask | close-case hook, lock held by this pid, a CLOSE CASE report prompt: prints nothing; the twin asserts "" for the same env and lock with 3 prompts | test_agent_close_case.py::TestNoKeywordHook.test_close_case_in_a_prompt_prints_nothing |
| test_agent_session_clean.py::TestTheHookText.test_a_task_manager_is_never_asked | task-manager env, prompt "close case": no --clean/--release; the twin asserts the whole output is "" for that env and prompt | test_agent_close_case.py::TestNoKeywordHook.test_close_case_in_a_prompt_prints_nothing |
| test_agent_housekeep.py::TestDocs.test_release | plugin.json version >= 0.33.0; the twin asserts >= 0.34.1 | test_agent_housekeep.py::TestDocs.test_release_housekeep_suspects |
| test_agent_housekeep.py::TestDocs.test_the_main_manager_reads_the_block | a W8 or S8 line with HOUSEKEEP and "idea rm"; the twin asserts exactly one W8 line with idea rm, idea keep and HOUSEKEEP | test_agent_housekeep.py::TestDocs.test_the_main_manager_removes_or_keeps_each_suspect |
| test_agent_main_seat.py::TestTheTexts.test_principles_say_it | "--take-over" in W10 and "--release" in W13; the twin asserts "`! agent-start.sh --take-over`" and "`! agent-start.sh --release`" in the same slices | test_agent_main_seat.py::TestTheHumanTypesIt.test_the_principles_say_the_human_types_it |
| test_agent_cloud_pack.py::TestIdempotent.test_a_second_run_without_the_flag_changes_nothing_either | body identical to the twin (pack, snapshot, pack again, same bytes); a removed flag had left two copies | test_agent_cloud_pack.py::TestIdempotent.test_a_second_run_changes_not_one_byte |
| test_agent_cloud_pack.py::TestTheOutput.test_it_prints_the_one_sentence_cloud_install | same pack output: asserts the one-sentence install; the twin asserts it and that no --language is in it | test_agent_cloud_pack.py::TestTheOutput.test_the_sentence_has_no_settings |
| test_agent_resume.py::TestRelaunch.test_does_not_relaunch_when_a_pane_is_live | a "working" pane: "no, pane is live", no create call; the twin runs the same for working, done and permission | test_agent_resume.py::TestRelaunch.test_a_pane_in_any_state_counts_as_live |
| test_agent_resume.py::TestAgentCap.test_a_done_pane_is_still_a_live_pane | a "done" pane: "no, pane is live"; the twin's "done" case asserts the same and no create call | test_agent_resume.py::TestRelaunch.test_a_pane_in_any_state_counts_as_live |
| test_agent_resume.py::TestDryRun.test_dry_run_launches_nothing | --dry-run: no create call and "would"; the twin asserts both, plus the cap row | test_agent_resume.py::TestAgentCap.test_dry_run_respects_the_cap_and_launches_nothing |
| test_agent_resume.py::TestLaunchCommand.test_the_effort_flag_comes_after_the_model_flag | --model before --effort; the twin asserts the exact argument list, which fixes the order | test_agent_resume.py::TestLaunchCommand.test_full_argument_list |
| test_agent_resume.py::TestLaunchCommand.test_command_sets_the_task_manager_role | the command starts "AGENT_ROLE=task-manager claude "; the twin's exact list holds that command | test_agent_resume.py::TestLaunchCommand.test_full_argument_list |
| test_agent_resume.py::TestPlainRelaunchesNothing.test_it_exits_zero | exit 0 of the plain resume; the twin's assertOk on the same run needs exit 0 | test_agent_resume.py::TestPlainRelaunchesNothing.test_the_working_row_names_the_mode |
| test_agent_resume.py::TestAConfWrittenBeforeRuntimeExisted.test_it_exits_zero | exit 0 with an old conf; the twin's assertOk on the same resume needs exit 0 | test_agent_resume.py::TestAConfWrittenBeforeRuntimeExisted.test_it_still_relaunches_through_orca |
| test_agent_runtime.py::TestKindAuto.test_orca_slower_than_three_seconds_is_plain | ORCA_STUB_SLEEP=6: kind is plain (6 s); the twin has the same input and also checks no temp file is left | test_agent_runtime.py::TestKindIsNeverCached.test_a_cut_off_probe_leaves_no_temp_file_behind |
| test_agent_runtime.py::TestKindAuto.test_a_slow_orca_does_not_hang_the_caller | ORCA_STUB_SLEEP=20: kind returns in under 10 s; the twin asserts that, plain, and 2 probe calls | test_agent_runtime.py::TestKindRetriesASlowProbe.test_slow_twice_is_plain_and_stays_under_ten_seconds |
| test_agent_runtime.py::TestKindAuto.test_orca_present_but_not_answering_is_plain | orca down: kind is plain; the twin asserts plain and exactly 1 probe call | test_agent_runtime.py::TestKindRetriesASlowProbe.test_a_fast_error_is_plain_without_a_retry |
| test_agent_watch.py::TestRuntimeAndArgs.test_plain_is_not_used | single-mode watch with AGENT_RUNTIME=plain: "watch: not used in plain mode", no terminal call; the twin runs the same check for plain and cloud, in single and --all mode | test_agent_watch.py::TestProbe.test_c1_plain_or_cloud_is_not_used_in_both_modes |
| test_agent_watch.py::TestRuntimeAndArgs.test_cloud_is_not_used | same for AGENT_RUNTIME=cloud: "watch: not used in cloud mode", no terminal call | test_agent_watch.py::TestProbe.test_c1_plain_or_cloud_is_not_used_in_both_modes |
| test_agent_watch.py::TestScreenNeverFires.test_a_new_done_line_on_screen_does_not_fire | a moving screen with "DONE PASS feat" added: no WATCH SIGNAL, ends WATCH MAX; the twin's first case is the same line, then four more wake words | test_agent_watch.py::TestScreenNeverFires.test_no_screen_word_fires |
| test_auto_clear.py::TestStartWarning.test_the_limit_is_the_fixed_300 | same 300-line state file, same `agent-start.sh` as task manager; asserts no line starts with STATE LONG, the twin asserts STATE LONG is nowhere in the output | test_agent_autoclear.py::TestStartWarning.test_300_lines_do_not |
| test_agent_file.py::TestTodoAddBy.test_default_by_is_main | same `todo add` with no by: asserts "\| by main"; the twin asserts the whole line, ending "\| by main" | test_agent_estimate.py::TestTodoGuess.test_no_guess_is_the_line_as_before |
| test_agent_file.py::TestTodoDrop.test_usage_lists_todo_drop | same bare `agent-file.sh`: exit 2 and "todo drop" in the usage; the twin checks exit 2 and "todo drop" among 10 verbs | test_agent_file.py::TestUsage.test_usage_lists_the_new_commands |
| test_agent_file_data.py::TestTimeTable.test_dropped_lines_are_skipped | same `time` table; its one assert ("gone" is no row) moved into the twin | test_agent_file.py::TestTimeTable.test_one_row_per_finished_task |
| test_agent_file_data.py::TestBackfillByName.test_it_sets_the_facts_of_an_old_line | same `backfill d-task`; the twin asserts the whole file, the new d-task line first | test_agent_file.py::TestBackfillByName.test_only_that_line_changes_and_the_order_stays |
| test_agent_file_data.py::TestDataAllRepos.test_dropped_lines_are_not_rows | same `data`; the twin asserts the exact rows, shop-gone is not among them | test_agent_file.py::TestDataAllRepos.test_this_repo_and_the_city_world_are_read |
| test_agent_estimate.py::TestDataWhat.test_without_the_option_the_table_stays_as_it_was | `data` without --what: last header cell is guess, no what text; the twin asserts the header ends "adds guess" and the row ends with the guess number | test_agent_estimate.py::TestDataGuess.test_the_table_has_a_guess_column_after_adds |
| test_agent_estimate.py::TestDataWhat.test_the_table_gets_a_last_column_what | `data --what`: last header cell what, the row ends with the what text; the twin asserts "adds guess what" and the row tails | test_agent_estimate.py::TestDataGuess.test_with_what_the_guess_comes_before_what |
| test_agent_estimate.py::TestBacktest.test_a_row_never_changes_when_later_tasks_come | rolling `backtest --tasks`: earlier rows stay byte-equal when tasks are added; the twin does the same on 45 tasks in today's row format | test_agent_estimate.py::TestBacktestBlend.test_a_row_never_changes_when_later_tasks_come |
| test_agent_estimate.py::TestBacktest.test_one_row_per_tested_task_in_finish_order | same 14 lines, same expected order; the twin shuffles the file order and expects the same list | test_agent_estimate.py::TestBacktest.test_finish_order_is_the_date_not_the_file_order |
| test_agent_estimate_blend.py::TestBacktestBlend.test_the_big_line_is_the_fixed_120 | same `backtest` on 40 steady lines; the twin asserts "work >= 120m: 7 tasks" | test_agent_estimate.py::TestBacktestBlend.test_the_rows_the_big_rows_the_winner_and_the_target_last |

## Before and after

To fill: files, tests, lines, seconds for all tests (pc2, same run), 10 slowest files.
