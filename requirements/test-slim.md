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

## Follow-up: test-slim-2 (done)

Base main b4392c7 (check-blocks merged, 81 test files). Folded: the 21 test_check_*.py files, the 14 files check-blocks kept editing, the 13 task-named files that waited for them, and test_agent_main_seat + test_agent_session_clean (target table: test_agent_start). Every row of the target layout above is done: 42 test files, one per script or module, rule-text pins in test_rules_text.py.

New module files: test_agent_level.py (agent-level.sh, agent_level.py, agent_blocks.py), test_agent_checks.py (agent_checks.py: todo checks, check lines, gate, next, edge add), test_agent_promote.py, test_agent_room.py (agent-room.sh, agent-test-run.sh), test_agent_nightly.py, test_agent_guard.py.

Speed levers applied:

| Lever | Where | Gain (seconds of the file alone) |
|---|---|---|
| Batching the cases of one test in one project, one commit, one check; a case whose kind a c<i>/ prefix could change runs alone (AGENT_TEST_SHAPE_ONE_BY_ONE=1 = the old way) | test_agent_level ShapeCase | comment_shape + risk_levels + check_blocks 258.8 -> test_agent_level 105.2 (with the next row) |
| In-process agent_level.run(); the first check of each class still starts the real agent-level.sh (AGENT_TEST_LEVEL_REAL=1 = every check real) | test_agent_level | about 17 s of the above |
| One BoardCase helper for the board and the status line, agent_board.py in-process; the wrapper tests keep real starts, two tests compare the wrapper output with the in-process output | test_agent_board, test_agent_statusline | 119 -> 68 and 96 -> 66 (measured under load) |
| @only_own on Nightly: its subclasses ran the 17 tests of TestNightly again | test_agent_nightly | 34 test runs less |

Helper fixes: SharedScriptCase fails on a missing script (no SkipTest); a subclass of a @shared_fixture class is refused (TypeError); run2.py checks the count per file (a file the loader cannot list skips only its own check); TestRailCss.test_phone asserts the exact top value (as strict as the removed TestPanelCss.test_phone_sheet_stays). agent_repo.conf guard_tests follows the plugin layout pins to tests/test_rules_text.py.

Trap: the move tool prunes a class that has no test method of its own (it only runs inherited tests, e.g. TestStartWiringLongPath); the ids audit cannot see that. Check the loader too: classes and test counts the loader runs, before and after (4800 -> 4769 here = -34 @only_own, -5 removed, +8 new).

### Removed checks (test-slim-2)

| Old file::test | Why it is a duplicate | Twin file::test that still checks it |
|---|---|---|
| test_board_waiting.py::TestRuleTexts.test_release_0_38_0 | plugin version floor 0.38.0 is weaker than the floor 0.44.0 | test_rules_text.py::TestSettingsTexts.test_plugin_version_is_bumped |
| test_rules_text.py::TestRuleAndReleaseVersion.test_release | plugin version floor 0.35.0 is weaker than the floor 0.44.0 | test_rules_text.py::TestSettingsTexts.test_plugin_version_is_bumped |
| test_rules_text.py::TestReadmeAndReleaseTrim.test_release_0_37_0 | plugin version floor 0.37.0 is weaker than the floor 0.44.0 | test_rules_text.py::TestSettingsTexts.test_plugin_version_is_bumped |
| test_rules_text.py::TestWiredInBlend.test_the_release | plugin version floor 0.34.0 is weaker than the floor 0.44.0 | test_rules_text.py::TestSettingsTexts.test_plugin_version_is_bumped |
| test_board_trust.py::TestRuleText.test_release | plugin version floor 0.39.0 is weaker than the floor 0.44.0 (the x.y.z shape is pinned by TestPluginManifest.test_required_and_chosen_fields) | test_rules_text.py::TestSettingsTexts.test_plugin_version_is_bumped |

### Before and after (test-slim-2)

Same machine (pc2, 8 cores, 8 GB), same runner (tests/run2.py --time -j 6, each file alone), back to back on 2026-11-25: before = the changed files at main b4392c7, after = this branch.

| | Before | After | Change |
|---|---|---|---|
| Test files, whole tests/ | 81 | 42 | -39 |
| Test files this task changed | 67 | 28 | -39 |
| Tests (ids) in those files | 4066 | 4069 | -5 removed with twins, +8 new (helper fixes 6, board wrapper 2) |
| Tests run (unittest) in those files | 4112 | 4081 | -34 duplicate inherited runs (@only_own), -5, +8 |
| Lines in those files | 49,064 | 47,009 | -2,055 (-4%) |
| Seconds, files added up | 2310 | 1972 | -338 (-15%) |
| Wall, each file alone, 6 at a time | 446 | 475 | the longest single file bounds it (test_agent_start 260 s); a normal run2.py run deals a big file out class by class |

Slowest after: test_agent_start 260, test_agent_watch 232, test_agent_city_server 164, test_agent_cleanup 155, test_agent_checks 127, test_agent_housekeep 122, test_agent_autoclear 108, test_agent_level 105.

Audit: `bin/agent_test_audit.py --before <ids of main b4392c7> --after <ids of this branch> --table <the "Removed checks (test-slim-2)" table>`: before 4754, kept 3052, moved 1697, removed with twin 5, AUDIT PASS. (The earlier table above names tests that were already gone at b4392c7; give the audit this section only.)

## Follow-up: test-slim-3 (done, target missed)

Owner 2026-11-26: "full test is good. but then slow"; on slimming the slowest files: "1. this forsure you can do it". Target: the full run (python3 tests/run2.py, 6 processes) under 5 minutes on pc2 with the same checks. Tests and test helpers only (main manager, TELL f8a2b798: script speed-ups are the next round's task; exactly 6 processes).

| | Before (base 2aae0b3) | After (this branch, base ea020e2 merged) |
|---|---|---|
| Wall, normal run2.py -j 6 | 683 s (processes 543-683 s) | 413 s (processes 402-412 s): -40% |
| Test seconds, all files | 3599 | 2444: -32% |
| Test files / tests run | 54 / 5230 | 57 / 5429 (+192 from the merged base, +7 new here) |

Both runs measured per test inside the normal run (a wrapper around run2.py's runner), Spotlight busy on one core in both. A first AFTER run (879 s) caught a defect of this task (below) and is not counted.

### Levers

| Lever | Where | Gain |
|---|---|---|
| git and python3 without the macOS xcrun shim; the CLT python's bytecode of temp projects in a per-run folder (tests/fasttools.py, from run2.py and scripthelp.py; AGENT_TEST_SHIMS=1 = old way) | every test that starts a script | 85.5 -> 70.2 s on 67 sample tests (-18%) |
| run2.py deals a big file out by its classes' measured seconds; --time writes a row per class | the split | processes end within 10 s of each other (were 543-683 s) |
| fixture built once per process, copied per test (absolute paths rewritten) | files family, checks, cleanup, housekeep, promote, cleanfiles, cloud_pack | files -60%, checks -56%, cloud_pack -77% |
| Python logic in-process (run_py, per repo), a REAL_SHELL set keeps one test per verb, flag and exit code on the command line | checks, promote, init, estimate, cleanfiles, watch (--all), cleanup, housekeep | estimate -58%, promote -52% |
| one run per class or per process for read-only tests (guard on: a test that changes the shared repo fails) | start, init, two_roots | start -14% (most start tests depend on an earlier run) |
| no cleanup sweep / no detached estimate runner where a test is not about them (their wiring stays in test_agent_cleanup and the estimate files), replay of an identical verb run on an identical state | file, resume, board, statusline, estimate | board -51%, statusline -40% |
| polls for sleeps that waited for a state; shorter fake pauses where the waits still cover as many rounds | city_server, autoclear, board, files_fix3 | city_server -26%, autoclear -32% |

### Per file (seconds in the full run)

| File | Slice | Tests before -> after | s before | s after | change |
|---|---|---|---|---|---|
| agent_start | 1 | 327 -> 327 | 357 | 308 | -14% |
| agent_watch | 3 | 211 -> 211 | 273 | 222 | -19% |
| agent_files | 2 | 79 -> 79 | 222 | 89 | -60% |
| agent_checks | 4 | 135 -> 135 | 197 | 88 | -56% |
| agent_cleanup | 5 | 137 -> 137 | 168 | 105 | -37% |
| agent_city_server | 6 | 267 -> 267 | 166 | 123 | -26% |
| agent_cloud_pack | 7 | 73 -> 73 | 132 | 30 | -77% |
| agent_file | 8 | 196 -> 196 | 123 | 78 | -37% |
| agent_housekeep | 5 | 145 -> 145 | 122 | 89 | -27% |
| agent_statusline | 11 | 158 -> 158 | 112 | 67 | -40% |
| agent_board | 11 | 155 -> 191 | 111 | 54 | -51% |
| agent_autoclear | 9 | 54 -> 54 | 108 | 74 | -32% |
| agent_level | 9 | 291 -> 291 | 107 | 74 | -30% |
| agent_promote | 10 | 57 -> 57 | 103 | 49 | -52% |
| agent_init | 10 | 104 -> 104 | 99 | 47 | -52% |
| agent_resume | 8 | 78 -> 78 | 97 | 63 | -35% |
| two_roots | 7 | 47 -> 47 | 96 | 58 | -39% |
| agent_estimate | 12 | 93 -> 93 | 79 | 33 | -58% |
| agent_cleanfiles | 12 | 70 -> 70 | 73 | 37 | -49% |
| agent_files_fix1 | 2 | 21 -> 21 | 68 | 42 | -37% |
| agent_files_codebranch | 2 | 11 -> 11 | 62 | 35 | -44% |
| agent_release | F | 52 -> 54 | 61 | 39 | -37% |
| agent_nightly | - | 31 -> 33 | 61 | 54 | -12% |
| agent_questions | - | 49 -> 49 | 55 | 51 | -8% |
| agent_owner_order | - | 128 -> 128 | 53 | 32 | -38% |
| check_blocks_demo | - | 1 -> 1 | 48 | 33 | -31% |
| agent_room | - | 45 -> 45 | 42 | 45 | +8% |
| agent_runtime | - | 75 -> 75 | 40 | 36 | -10% |
| agent_files_fix3 | 2 | 4 -> 4 | 25 | 5 | -80% |
| agent_files_fix2 | 2 | 8 -> 8 | 21 | 12 | -44% |
| run2 | L | 9 -> 14 | 2 | 2 | +0% |
| all files | | 5230 -> 5429 | 3599 | 2444 | -32% |

### Audit (no check lost)

- Ids: `bin/agent_test_audit.py --before <ids at ea020e2> --after <ids here>`: 5373 -> 5380, kept 5359, moved 14 (11 two_roots and 3 init tests into reader/writer classes, names unchanged), removed with twin 0, AUDIT PASS (also against the ids at 2aae0b3).
- Loader counts: 5422 -> 5429; +2 test_agent_release, +5 test_run2, every other file the same count.
- Assertions (AST of every assert call, per test method, against the merged base): 19 of 24 changed files identical. The five others:

| File::test | Before | After | Why |
|---|---|---|---|
| test_agent_files_fix1::TestDAHangingRemoteCostsOneTimeout.test_one_timeout_then_the_network_is_skipped | first command < 5 s, second < 2 s (red at 5.17 s under load) | the hanging remote is called exactly once by the first command and not by the second; the first ends in < 10 s at a 1 s timeout (below the 15 s default and the 60 s hang) | fragile test: same facts, not machine speed |
| test_agent_cleanup::TestUnreachable.test_a_hang_never_hangs_the_sweep | elapsed < 20 s at a 3 s cut-off | elapsed < 7 s at a 1 s cut-off | the bound scales with the cut-off (about 6 cut calls either way): see the table below |
| test_agent_level::TestKinds.test_rule_files, test_ci_and_test_config; TestTypesPerPart.test_a_component_file_is_b | one project and one check per path | one project and one check for all paths, each path's own FILE line asserted (same expected kind), plus "path is listed" | batching, as ShapeCase in test-slim-2 |
| test_agent_release (2 new) | - | TestBehindTheLiveRelease | fragile test, below |
| test_run2 (5 new) | - | TestDirectTools, TestClassSeconds | the two runner levers |

### The two fragile tests

- test_agent_release::TestRealRepo.test_dry_run_on_this_repo read the live origin/release: a release made during the run (or after the branch was cut) made a lower version red. Now (real_repo_verdict) a release tip built from a commit HEAD does not contain allows a lower version; one built from a commit HEAD contains is still red (2 fixture tests).
- test_agent_files_fix1 (above).

### Changed set-ups, waits and bounds (assert calls unchanged)

| File::test or class | Before | After | Why it still proves the same |
|---|---|---|---|
| test_agent_cleanup::TestUnreachable.test_a_hang_never_hangs_the_sweep | AGENT_CLEANUP_TIMEOUT 3 s, elapsed < 20 s | 1 s, elapsed < 7 s | the bound scales with the cut-off: about 6 cut calls either way (one call measured: 1.3 s) |
| test_agent_city_server::TestGovWatch.test_server_gone | watcher max wait 20 s | 3 s | it asserts exit 0 only: a watcher whose server is gone retries until its max wait, then ends |
| test_agent_city_server::TestBudget.test_log_is_rotated_and_no_line_is_lost | sleep 0.15 s x 10 between batches | poll until the client has seen each batch | the same batches in the same order; no line may be lost either way |
| test_agent_city_server (several) | sleeps waiting for a state (governors, terminal lines) | polls with the old sleep as deadline | the state is asserted as before; the waits that prove nothing happens stay |
| test_agent_autoclear::TestWaiter | the fake 30 s pause 0.3 s | 0.05 s | test_it_pauses_after_each_typed_text keeps 3 x 1 s with >= 2.0 |
| test_agent_autoclear (waiter classes) | fake pause 1 s; 'nothing happens' waits 3 s / 2 s; 'ready took >= 2 s' holds 3 s | 0.3 s; 1.5 s; 2.2 s | the waits cover at least as many waiter rounds as before (2.5 vs 2.3 and 1.5); whole-second SECONDS still sees 2 |
| test_agent_housekeep (in-process tests) | the real agent-nightly.sh after --apply | a stub that answers 'not due' (exit 1) | the real one also answers 'not due' in these fixtures; no housekeep test is about the nightly; @real_shell tests keep the real one |
| test_agent_file, test_agent_board, test_agent_statusline, test_agent_estimate (own classes), test_agent_resume | todo done / resume with the cleanup sweep and the detached estimate runner | AGENT_CLEANUP_DONE=1 and the runner's lock held by the test | none of these tests is about them; the wiring is tested in test_agent_cleanup (TestTodoDoneWiring, TestResumeWiring) and the runner in test_agent_estimate_learn and test_agent_files_fix1 |
| test_agent_files_fix3::RestoreCase | time.sleep(1.1) before a new saved copy | the existing copies and the todo made 2 s older (os.utime) | the order is by mtime (ns), names get a -n suffix on a clash |
| test_agent_file replay | - | an identical verb run on an identical state (project files, refs, .git/agent_* state files, arguments, env, fake clock) is replayed after the first real one | the same output, exit code and written files; a run that changed a ref is never replayed |

### Found and fixed on the way

- The first AFTER run: slice 12's EstimateCase speed-ups reached subclasses in test_agent_estimate_learn (4 tests waited 120 s for a background runner whose lock the test held) and test_agent_version (the stale-retrain guard skipped in-process): the speed-ups now apply to the file's own classes only. Every other changed base class was checked against its users in other files.
- Taken back from worker changes: threads inside a test (the runner's CPU cap), a lock hold cut from 4 s to 3.6 s against a >= 3.0 s assertion, a plugin folder linked to the per-minute template (can dangle), one production-path refusal moved off the real agent-promote.sh, a `sleep 3000` lock holder (now ends with its test process).
- The CLT python had written the bytecode of every temp project under ~/Library/Caches/com.apple.python (about 130,000 folders, 5.8 GB on pc2); test runs no longer add to it. The folder itself was not touched.

### Accepted: fast paths for the core scripts (main manager, FIX ORDER 1, TELL e425dcb8)

In-process calls, replays of identical runs and shared start runs are accepted for the core scripts, on one floor: for every verb, every flag and every exit code at least one test keeps the real command line (the REAL_SHELL / @real_shell / @real_command_line sets of each file). The PR REVIEW checked every fast path against the real command line in an instrumented run, and the files in reversed, shuffled and alone orders. A fast path that a base class gives its subclasses applies to the classes of its own file only.

### Left, and why

- About 160 start tests need their own agent-start.sh run (dedupe, locks, release, clean); agent-start.sh costs about 1 s a call under load.
- Waits that prove something does not happen (city_server, autoclear, watch cadence); the tell read-back loop (20 x 0.5 s, no env knob); single-mode watch starts.
- Not slimmed: nightly, questions, room, runtime, name, state, guard, leader_relay (each under 55 s).

### Follow-up: the scripts (next round)

Script calls of the AFTER run (ScriptRepo.run / run_py only): 4725 calls, 1654 s of the 2444 s.

| Script (verb) | Calls | Seconds | s a call | Files that pay most (s) |
|---|---|---|---|---|
| agent-start.sh | 468 | 453 | 0.97 | agent_start 280, two_roots 50, agent_cleanup 30 |
| agent-file.sh todo | 983 | 309 | 0.31 | agent_file 51, agent_statusline 35, agent_files 33 |
| agent_watch (in-process) | 174 | 97 | 0.56 | agent_watch 97 |
| agent_housekeep (in-process) | 106 | 62 | 0.59 | agent_housekeep 60, agent_state 2 |
| agent-resume.sh | 79 | 61 | 0.77 | agent_resume 51, agent_cleanup 4, agent_start 3 |
| agent-file.sh tell | 31 | 51 | 1.65 | agent_watch 51 |
| agent-watch.sh | 77 | 46 | 0.60 | agent_watch 46 |
| agent-init.sh | 89 | 43 | 0.48 | agent_init 33, agent_files 4, agent_files_fix1 4 |
| agent-owner-order.sh | 341 | 42 | 0.12 | agent_leader_relay 21, agent_owner_order 20, agent_autoclear 1 |
| agent-city.sh | 73 | 36 | 0.49 | agent_city_server 30, agent_city_script 6 |

- agent-start.sh: 27 python3 and about 35 git starts a call; --answer runs one shasum per question.
- agent-file.sh: a verb is bash plus 8-12 python3/git starts; todo done and agent-resume.sh sweep (0.3-0.45 s) unless AGENT_CLEANUP_DONE=1.
- agent-file.sh tell: the read-back loop waits 20 x 0.5 s when the block does not read back (a test env knob would cut it).
- Projected: halving agent-start.sh and a third off agent-file.sh todo, tell and resume removes about 390 s of test time, about 65 s of wall: about 350 s. 300 s needs more than the scripts (Spotlight indexing takes one of the 8 cores on pc2).
