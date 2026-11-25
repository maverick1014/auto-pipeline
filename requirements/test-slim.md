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
| test_agent_city_page.py, _data.py, _server.py, _hook.py, _script.py | the page (node), agent_city.py state, the HTTP server and API, agent-city-hook.sh, agent-city.sh and the shim | 43 city files; test_agent_city_add_agent.py stays until check-blocks (test_bypass_mode imports it) | done |

## How a slice is done

1. Classes move with `movecls.py` (body and method names unchanged, the helpers they use come along). The audit matches old and new tests by method name.
2. A duplicate check goes only with a twin: a row in the table below. No twin, no removal.
3. Never weakened: rules (PRINCIPLES, skills, quiz), the core scripts (agent-file, guard, start, watch, board, level/blocks, release, cleanup, settings), money, secrets, permissions. Text pins stay; only a second copy of the same pin goes.
4. Speed: a class whose tests only read one fixture becomes a `SharedScriptCase` (tests/sharedrepo.py): one repo per class, each script run once in `prepare()`, a guard fails any test that changes the shared folder. Tests that write keep one repo per test (`ScriptCase`).
5. Every new repo copies a per-process seeded template instead of five git starts (tests/scripthelp.py, after check-blocks).
6. Before a slice: the test list of the touched files. After it: the audit (moved + removed-with-twin = before) and the slice's tests pass.

## Parallel runs

```
python3 tests/run2.py            # every test file; processes = CPU cores x 80% (6 on 8 cores)
python3 tests/run2.py -j 2 FILE  # chosen files, 2 processes
python3 tests/run2.py --time     # each file alone; file, tests, seconds; rewrites tests/timings.txt
python3 -m unittest discover -s tests   # still works, one process
```

- Load rule (owner 2026-11-25): CPU under 80% (the default -j); a process starts only while memory in use + 30 MB stays under 80%. No slot or lock.
- The split deals files slowest first (tests/timings.txt) to the process with the least seconds so far; a file bigger than a third of one process's share is dealt out class by class.
- Every merged file must also pass alone in one process (`--time` runs it so): two classes from different old files can share a module-level object.

## Speed levers, measured on pc2

| Lever | Where | Gain |
|---|---|---|
| Seeded repo template, copied per test (tests/scripthelp.py) | every ScriptCase test | 0.11 s -> 0.03 s per repo |
| One fixture and one run per call for read-only classes (tests/sharedrepo.py) | file, resume, name, questions, housekeep, owner_order, close_case, two_roots, cloud_pack | cloud_pack 86 s -> 48 s |
| Shorter fake pause in the auto-clear waiter (the pause test keeps 1 s) | autoclear | 72 s -> 48 s |
| Batching the cases of one test in one repo, one commit, one check | comment_shape (after check-blocks) | 211.6 s -> 94.3 s on a copy |
| In-process call of the Python module (ScriptRepo.run_py) | housekeep | about 0.08 s per call; the rest is real git work inside |

In-process, start costs measured: bash 7 ms, python 27 ms, plus imports; a script call costs statusline 0.16 s, agent-file.sh verbs about 0.20 s, agent-level.sh 0.33 s, housekeep 0.3-0.6 s.
Files that could call the Python module in-process (not rewritten in this task unless listed above):

| File | Module | Expected gain |
|---|---|---|
| test_comment_shape, test_risk_levels, test_check_blocks | agent_level.py (agent-level.sh is roots + exec) | 0.1-0.15 s per check, about 20-30 s after batching |
| test_agent_statusline, the board tests | agent_board.py --statusline | about 0.08 s per line call |
| test_agent_file, test_agent_state, test_agent_estimate | agent_state.py, agent_estimate.py, agent_board.py behind agent-file.sh | about 0.1 s per call; the bash dispatcher's argument work must keep real starts |
| not worth it | agent_watch.py (loop, signals), cleanup, resume, start, cloud-pack | their time is git, servers or bash, not the start |

## Removed checks

| Old file::test | Why it is a duplicate | Twin file::test that still checks it |
|---|---|---|
| test_agent_city_page.py::TestDocument.test_it_exists | bin/agent-city.html exists; the twin reads the page first (page() fails if it is missing) and checks doctype and title | test_agent_city_page.py::TestDocument.test_full_document_with_title |
| test_agent_city_page.py::TestInteraction.test_phone_layout_has_the_panel | ".ask-panel" in the 960px phone block; the twin asserts it after .drawer-open in the same block | test_agent_city_page.py::TestRailCss.test_phone |
| test_agent_city_rail_panel.py::TestPanelCss.test_phone_sheet_stays | .win top is auto in the 960px block; the twin asserts top:auto on the same rule | test_agent_city_page.py::TestRailCss.test_phone |
| test_agent_city_ux2.py::TestRailWiring.test_esc | the page keydown listener holds Escape and stopFollow(); the twin finds that one listener, stopFollow() in it, Escape the only key | test_agent_city_page.py::TestRemoved.test_no_keyboard_shortcuts |
| test_agent_city_talk_panel.py::TestLabelDropsTheRepeatedKindT5.test_rail_head_tag_and_panel_title_show_it | nameOf( in railRowHtml, updatePerson, winTitle; the twin checks those three plus renderDetail and renderFollow | test_agent_city_page.py::TestNamesDrawn.test_short_name_everywhere_in_a_repo |
| test_agent_city_names.py::TestNameShownOnce.test_name_of | nameOf of 4 label/task pairs; the twin runs the same 4 with the same results plus one more | test_agent_city_page.py::TestLabelDropsTheRepeatedKindT5.test_old_rules_stay |
| test_agent_city_talk.py::TestDemoShowsItT1T3.test_a_demo_person_is_sent_by_the_demo_governor | spawnDemo has 'gov:' + terr; the twin's pattern contains that text in its full from: line | test_agent_city_page.py::TestDemoShowsItT1T3.test_only_where_the_demo_draws_a_governor |
| test_agent_city_ask_panel.py::TestResultThenFoldK4K5.test_run | no "fatal" in the sim result; run_sim already raises on a fatal result, and every test of the class reads the same run | test_agent_city_page.py::TestResultThenFoldK4K5.test_shown_nowhere_is_deleted_as_before |
| test_agent_city_idea_server.py::TestIdleIsNotAQuestion.test_permission_prompt_is_still_stuck | same Notification permission_prompt for tm1, same exact stuck event | test_agent_city_data.py::TestCitizenStatus.test_permission_prompt_is_still_stuck |
| test_agent_city_talk.py::TestSpawnSaysWhoSentItT1.test_no_governor_no_sender | lead() with no governor: spawn from is ""; the twin asserts the same and the up field | test_agent_city_server.py::TestUpOnSpawnS1.test_a_task_manager_without_a_governor_still_names_it |
| test_agent_city_server.py::TestCityScript.test_the_server_really_answers | after agent-city.sh start, GET /health answers; the twin starts the same way and reads /health's JSON (gov_wait_sec 60), then drives the server | test_agent_city_server.py::TestCityScriptVerbs.test_start_passes_the_wait_and_the_log_path |
| test_agent_runtime.py::TestLaunchWithOrca.test_a_title_with_spaces_stays_one_argument | same launch: "TM alpha" is one argument; the twin asserts the exact argument list, which holds "TM alpha" as one element | test_agent_runtime.py::TestLaunchWithOrca.test_the_exact_argument_list |
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

Same machine (pc2, 8 cores, 8 GB), same runner, back to back on 2026-11-25: before = main 2e10fb7, after = this branch.

| | Before | After | Change |
|---|---|---|---|
| Test files | 104 | 58 | -46 |
| Tests (unittest ids) | 4191 | 4169 | -45 removed with twins, +23 new tests of the two bin tools |
| Lines in tests/*.py | 59,116 | 53,145 | -5,971 (-10%) |
| Seconds, all files added up (each file alone, 6 at a time) | 3201 | 2612 | -18% |
| Wall, each file alone, 6 at a time | 580 | 531 | |
| Wall, normal run (run2.py, 6 processes, split by tests/timings.txt) | 571 | 548 | -4%: the machine is CPU-bound at 6 processes, so the wall follows the total work |
| Wall, the old way (one process, unittest discover) | 2833 (laptop, main 08eb27e, the main manager's table) | not run | the new runner alone takes the old suite from about 47 min to under 10 min |

Audit: `bin/agent_test_audit.py --before <main ids> --after <branch ids> --table requirements/test-slim.md`: before 4191, kept 2441, moved 1705, removed with twin 45, AUDIT PASS.

Slowest 10, each file alone, 6 at a time (seconds):

| Before | s | After | s |
|---|---|---|---|
| test_comment_shape | 252 | test_agent_watch (5 files) | 279 |
| test_agent_cleanup | 205 | test_agent_cleanup | 197 |
| test_agent_start | 190 | test_agent_city_server (about 12 files) | 179 |
| test_agent_housekeep | 159 | test_comment_shape | 170 |
| test_watch_all | 154 | test_agent_start | 167 |
| test_agent_cloud_pack | 129 | test_agent_housekeep | 130 |
| test_agent_resume | 128 | test_agent_resume | 111 |
| test_risk_levels | 96 | test_agent_cleanfiles | 87 |
| test_two_roots | 95 | test_agent_estimate (2 files) | 81 |
| test_agent_city_interact | 90 | test_agent_file (4 files) | 80 |

Left for the follow-up task (check-blocks still changes them): test_agent_board, test_agent_cleanup, test_agent_init, test_agent_release, test_agent_start, test_board_trust, test_board_waiting, test_bypass_mode, test_comment_shape, test_decider_floor, test_output_rules, test_plugin_layout, test_risk_levels, test_settings_configure (in this branch, untouched), plus test_check_blocks, test_check_cleanup, test_check_init, test_check_net, test_check_results, test_check_rules, test_check_warnings (only on the check-blocks branch). Waiting on their module files: test_five_fixes, test_guard_var_path, test_output_hook, test_owner_relay_text, test_permission_setting, test_settings_readers, test_statusline_refresh, test_statusline_vertical, test_statusline_wide, test_watch_board, test_watch_report, test_agent_progress, test_agent_city_add_agent. The plan for them: the "Speed levers" table above (comment_shape batching: 211.6 s -> 94.3 s on a copy) and the target layout.
