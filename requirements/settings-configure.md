# settings-configure

Owner principle (2026-11-25, "1A"): this plugin is a developer workflow, not a per-repo tool. Its settings live only in `/plugin` -> Installed -> auto-pipeline -> Configure, at user level. No `agent.conf` in a repo, no `~/.claude/auto-pipeline.conf` on a machine.

## 1. How a script reads a Configure value (checked on Claude Code 2.1.331)

| Question | Answer | Proof |
|---|---|---|
| Where are the values stored | `~/.claude/settings.json` (or `$CLAUDE_CONFIG_DIR/settings.json`) -> `pluginConfigs["auto-pipeline@auto-pipeline"].options.<key>`. User or managed scope only; project and local entries are ignored by Claude Code | docs settings-reference `pluginConfigs`; `pluginConfigs` in the binary; `claude plugin configure auto-pipeline@auto-pipeline --json` |
| `CLAUDE_PLUGIN_OPTION_<KEY>` env | hook processes only, key upper-cased | docs manifest-reference; binary text "$CLAUDE_PLUGIN_OPTION_<KEY> from the hook's environment" |
| In Claude's Bash tool | not there | this session's Bash env has no `CLAUDE_PLUGIN_OPTION_*` |
| In a subagent's Bash | not documented, treated as absent | docs list hooks only |
| Skill and agent text | `${user_config.KEY}` is substituted (non-sensitive only) | docs manifest-reference |
| Field types | `string`, `number`, `boolean`, `directory`, `file`; `options` on a string = a picker; `min`/`max` on a number; an unknown field key is an error | docs manifest-reference |
| Groups, sections, sort | none; `configure --json` keeps the plugin.json key order | docs; `configure --json` output |
| A script writes a value | supported: `claude plugin configure auto-pipeline@auto-pipeline --values-stdin` (JSON object of strings; left-out keys keep their value; "restart to apply") | `claude plugin configure --help` |
| A change reaches a running session | hook env: from the next session; a file read: at once | CLI text "Restart Claude Code to apply it" |

Pick: one reader, `bin/agent_conf.py`. Order: settings.json `pluginConfigs` -> `CLAUDE_PLUGIN_OPTION_<KEY>` env -> the plugin.json default. Hooks, Bash calls and subagents get the same answer. No plugin (cloud session, `cloud-pack`) -> the defaults. A stored value that fails its check -> the default, and one warning line; never silent.

## 2. The 17 settings (plugin.json `userConfig`, in this order)

Groups cannot show, so the group is the first word of the title.

| # | key | title | type | default | old agent.conf key |
|---|---|---|---|---|---|
| 1 | language | Basic: Language | string | en | language |
| 2 | runtime | Basic: Runtime | string, picker auto orca plain cloud | auto | runtime |
| 3 | auto_update | Basic: Auto update | boolean | true | auto_update (user file) |
| 4 | main_manager | Models: Main manager model | string, picker | opus-5.5:high | main_manager |
| 5 | task_manager | Models: Task manager model | string, picker | opus-5.5:high | task_manager |
| 6 | helper_model | Models: Helper model | string, picker | sonnet-5:medium | fast_lane_deputy, merge_deputy, worker |
| 7 | max_agents | Load: Max agents | number 1-16 | 4 | max_agents |
| 8 | max_usage_percent | Load: Max memory % | number 1-100 | 80 | max_usage_percent |
| 9 | heavy_test_slots | Load: Heavy test slot/time | number 1-8 | 1 | heavy_test_slots |
| 10 | permission_mode | Permissions: Permission mode | string, picker | auto | permission_mode (user file wins) |
| 11 | auto_resume | Permissions: Auto resume | boolean | true | auto_resume |
| 12 | todo_before_agent | Rules: Todo before agent | boolean | true | board_guard (on = true; record, off = false) |
| 13 | watch_quiet_min | Stuck: Consider stuck after (min) | number 1-240 | 15 | watch_quiet_min |
| 14 | housekeep_interval_min | Stuck: Tidy every (min) | number 0-1440 | 120 | housekeep_interval_min |
| 15 | city_port | City: City port | number 1024-65535 | 4777 | city_port |
| 16 | city_idle_min | City: City auto close (min) | number 1-240 | 30 | city_idle_min |
| 17 | danger_paths | Risk: Danger paths (D) | string, comma-separated globs | .claude-plugin/,hooks/,PRINCIPLES.md,skills/,agents/,bin/agent_conf.py | level3_paths + level4_paths |

Rules and examples:

| Case | Example | Result |
|---|---|---|
| Nothing set | fresh install | every default above |
| A number stored as text | `"max_agents": "6"` | 6 |
| A number out of range | `"max_agents": 40` | 4 + `SETTINGS: max_agents=40 is out of range 1-16, default 4 used` |
| A boolean stored as text | `"auto_resume": "false"` | false |
| A manager below the decider floor | `main_manager = sonnet-5:high` | refused, default opus-5.5:high + one warning line |
| Helper model | `helper_model = sonnet-5:high` | fast-lane deputy, merge deputy and worker all run sonnet-5:high |
| Todo before agent off | false | launches are recorded, never refused (old `board_guard=record`) |
| Danger path missing in a repo | `bin/agent_conf.py` in a product repo | matches nothing, no error |
| Hook env and file disagree | env 4 (session start), file 6 (changed now) | 6: the file wins |

## 3. Fixed constants (not shown anywhere)

`stage_brief=1 stage_register=1 stage_mock=4 stage_tests=20 stage_workers=40 stage_verify=15 stage_push=2 stage_report=2 stage_e2e=10 stage_merge=5 board_watch_sec=60 progress_eta_min_pct=20 statusline_refresh_sec=60 city_governor_wait_sec=60 estimate_target_pct=50 estimate_bias_min=5 estimate_big_min=120 state_keep_hours=24 state_warn_lines=300 state_header_lines=40 state_trim_auto=on compact_clear_at=2 compact_clear_check_sec=30 cleanup_days=14 docs_keep= owner_order_hours=24 owner_order_min_chars=20`

27 keys (the brief said 26; its own list names 27). They live in `bin/agent_conf.py` `CONSTANTS`, read by name.

## 4. Migration from the old files (owner answer Q1, 2026-11-25)

- Start and init look for `agent.conf` (repo top) and `~/.claude/auto-pipeline.conf`; the user file wins for permission_mode and auto_update (the old rule)
- A value that differs from the default and is still unset in Configure is written with `claude plugin configure auto-pipeline@auto-pipeline --values-stdin`, once, before the start reads any setting
- A value the human already set in Configure is never overwritten: `kept <key>=<now> in Configure, skipped <key>=<old> from <file>`
- Lines: a `SETTINGS MOVED: <file> is not read any more ...` header, `moved <key>=<value> from <file> to Configure`, `fixed: <key>=<v> ... is now fixed at <c>` for a changed constant, `dropped: <key>=<v> ... is not a setting any more` for an unknown key
- Once = marker `<config dir>/auto-pipeline-migrated.json` (real path -> sha256 of the text); the same text again prints nothing
- The write fails: `SETTINGS MOVE FAILED: <why>. Run: <the exact command>`, no marker, tried again next start. Never silent
- The old files are never changed or deleted by a script

## 5. `/auto-pipeline:settings`

- One table by group: name, value, plain meaning; a value that is not the default is marked
- Last line: `change: /plugin -> Installed -> auto-pipeline -> Configure`
- It never changes a setting. `agent-settings.sh` keeps only `show` (and `get <key>` for scripts)

## 6. init and cloud

- init asks no setting and writes no settings file (no agent.conf, no user file)
- Cloud (no plugin): the defaults. `cloud-pack` still packs and runs

## 7. Risk types (owner 2A, 2026-11-25, replaces the path rule)

- The type is judged from the brief: what changes and how much other code depends on it, never from file paths alone
- Doc or text only (.md, comments, rule text, PRINCIPLES.md wording) = A, even in PRINCIPLES.md
- A new feature is normally C; D only for core code many other things depend on
- `danger_paths` ("Risk: Danger paths (D)") is a hint: `agent-level.sh` prints `touches core path <file>: judge from the brief whether it is D`; it never raises, never raises a doc-only diff
- The built-in D kinds stay D: lockfile, dependency lists, migrations, schema
- A second agent (read-only, given the brief and the code, not the manager's answer) reviews the picked type; a disagreement goes to the owner

| Diff | Type | Line |
|---|---|---|
| PRINCIPLES.md wording | A | touches core path PRINCIPLES.md: ... |
| logic in bin/agent_conf.py | C (from the code) | touches core path bin/agent_conf.py: ... |
| yarn.lock | D (built-in) | - |
| skills/x/SKILL.md text | A | touches core path skills/x/SKILL.md: ... |

## 8. plugin-scope-sync (owner answer Q2, 3A 2026-11-25)

- `installed_plugins.json` holds one entry per scope: user, and a project entry per folder (each worktree folder gets its own)
- Start (every role) and init: the scopes this folder uses (user, and the project or local entries whose path is this folder or the main repo) older than the newest installed version are updated with `claude plugin update auto-pipeline@auto-pipeline --scope <s>`, run in that folder
- One line per scope: `updated <scope> <path>: <old> -> <new>, restart to apply`
- Failed, Auto update off, or another start holding the lock (`<config dir>/plugins/.auto-pipeline-update.lock`, fresh under 10 min): `STALE SCOPE: ... <why>: <the exact command>`
- Entries of other repos and of folders that are gone are never touched; the script never writes `installed_plugins.json` itself
