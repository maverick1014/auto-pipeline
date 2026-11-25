"""settings-configure: the 17 settings live only in /plugin -> auto-pipeline -> Configure.

Written by the task manager before any code (requirements/settings-configure.md).

CONTRACT for bin/agent_conf.py:

    PLUGIN_ID                 "auto-pipeline@auto-pipeline"
    SETTINGS                  list of 16 dicts, in display order (owner 1A 2026-11-25: Danger
                              paths left Configure; core paths are agent_repo.conf, a repo file). Each: key, title, type
                              ("string" | "number" | "boolean"), description, default;
                              optional options (list of str), min, max (numbers)
    user_config()             the plugin.json "userConfig" object built from SETTINGS
                              (same key order; fields type, title, description, default,
                              options / min / max only when set)
    CONSTANTS                 the 33 fixed internal values, by old agent.conf key
    get(key, env=None)        the value: Configure (settings.json pluginConfigs), else
                              CLAUDE_PLUGIN_OPTION_<KEY> env, else the default. A
                              constant key gives its constant. An old role key
                              (main_manager, task_manager, fast_lane_deputy,
                              merge_deputy, worker) gives its model:effort. Unknown key:
                              KeyError. Types: str, int, bool. Never reads agent.conf or
                              ~/.claude/auto-pipeline.conf
    source(key, env=None)     "Configure" | "env" | "default" | "constant"
    text(value)               on/off for a bool, str() for the rest
    warnings(env=None)        one line per stored value that failed its check
    migrate(project_root, env=None)  owner Q1 (2026-11-25): moves the old values into
                              Configure, once, with `claude plugin configure
                              auto-pipeline@auto-pipeline --values-stdin` (JSON object of
                              strings). Only keys still unset in Configure and different
                              from the default; a key the human set is never overwritten.
                              Returns the lines to print, [] when nothing to say:
                                SETTINGS MOVED: <file> is not read any more ...  (header)
                                moved <key>=<value> from <file> to Configure
                                kept <key>=<now> in Configure, skipped <key>=<old> from <file>
                                fixed: <old key>=<old> in <file> is now fixed at <constant>
                                dropped: <key>=<value> in <file> is not a setting any more
                                SETTINGS MOVE FAILED: <why>. Run: claude plugin configure
                                  auto-pipeline@auto-pipeline --values-stdin <<< '<json>'
                              Old level3_paths / level4_paths (not empty) go into
                              <project root>/agent_repo.conf (key=value, created when missing,
                              a key already there is never overwritten: "kept <key>=<now> in
                              agent_repo.conf, skipped <key>=<old> from <file>"; same value:
                              nothing), one line "moved <keys, comma+space> to agent_repo.conf
                              (repo file, commit it)"; never into Configure.
                              Once = marker <config dir>/auto-pipeline-migrated.json (real
                              path of the old file -> sha256 of its text); a failed write
                              leaves no marker, so the next start tries again.
CONTRACT for bin/agent_update.py (plugin-scope-sync; replaces agent-version.sh scopes):

    sync_scopes(folders, env=None)  owner Q2 / 3A (2026-11-25): the scopes this repo uses
                              (user, and project or local entries whose projectPath is one of
                              FOLDERS) older than the newest installed version are updated
                              with `claude plugin update auto-pipeline@auto-pipeline --scope
                              <s>` run in that folder (user: in FOLDERS[0]). Lines:
                                updated <scope> <path>: <old> -> <new>, restart to apply
                                updated user: <old> -> <new>, restart to apply
                                STALE SCOPE: <scope> <path> runs <old>, newest <new>; <why>:
                                  cd <path> && claude plugin update auto-pipeline@auto-pipeline --scope <s>
                                STALE SCOPE: user runs <old>, newest <new>; <why>:
                                  claude plugin update auto-pipeline@auto-pipeline --scope user
                              (each one line; <why> = the error text, "auto update is off" or
                              "another session is updating")
                              Auto update off -> no run, the STALE SCOPE line only. A fresh
                              lock dir <config dir>/plugins/.auto-pipeline-update.lock
                              (under 10 min) -> no run, STALE SCOPE line. Other entries are
                              never touched. installed_plugins.json is never written here.
                              Newest = the highest version among the plugin's entries and
                              the cache folders <config dir>/plugins/cache/auto-pipeline/
                              auto-pipeline/<v> that hold .claude-plugin/plugin.json.
                              CLI: python3 bin/agent_update.py sync <folder>...

    env: a dict like os.environ. The Claude config dir is env CLAUDE_CONFIG_DIR, else
    <env HOME>/.claude. The old user file is env AUTO_PIPELINE_USER_CONF, else
    <env HOME>/.claude/auto-pipeline.conf (only read for the migration). `claude` is
    looked up on env PATH; stdin closed, timeout 120 s.

CLI: python3 bin/agent_conf.py get <key> | show | migrate <project root>
     show ends with "change: /plugin -> Installed -> auto-pipeline -> Configure" and then
     "core paths of this repo: agent_repo.conf".
     repo_paths(project_root) -> (dict of level3_paths/level4_paths text, [warning lines]):
     the main repo's agent_repo.conf; missing file or key -> not in the dict; a bad glob list
     -> left out + one "SETTINGS: <key>=<v> in agent_repo.conf ..." warning.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import agent_conf  # noqa: E402
import agent_update  # noqa: E402

ORDER = [
    ("language", "Basic: Language", "string", "en"),
    ("runtime", "Basic: Runtime", "string", "auto"),
    ("auto_update", "Basic: Auto update", "boolean", True),
    ("main_manager", "Models: Main manager model", "string", "opus-5.5:high"),
    ("task_manager", "Models: Task manager model", "string", "opus-5.5:high"),
    ("reviewer_model", "Models: Reviewer model", "string", "opus-5.5:high"),   # owner 2A 2026-11-25: new
    ("helper_model", "Models: Helper model", "string", "sonnet-5:medium"),
    # max_agents: gone (owner 2026-11-25, TELL bd4e87ee): no count caps, the memory rule admits a pane
    ("max_usage_percent", "Load: Max memory %", "number", 80),
    # heavy_test_slots: gone (owner 2026-11-25, TELL 076c1faf): no slots, a memory gate (tests/test_check_net.py)
    ("permission_mode", "Permissions: Permission mode", "string", "bypassPermissions"),   # owner order 2026-11-25
    ("auto_resume", "Permissions: Auto resume", "boolean", True),
    ("todo_before_agent", "Rules: Todo before agent", "boolean", True),
    # owner 2026-11-25 (TELL 76bfcc8f): new; the name is not final: one constant (TELL 84fbcf51)
    ("working_branch", "Flow: Working branch", "string", agent_conf.WORKING_BRANCH_DEFAULT),
    ("watch_quiet_min", "Stuck: Consider stuck after (min)", "number", 15),
    ("housekeep_interval_min", "Stuck: Tidy every (min)", "number", 120),
    # owner order 2026-11-25 (TELL 9bb87b13): the auto clear waits until no human typed for this long
    ("clear_quiet_min", "Context: Auto clear after quiet (min)", "number", 30),
    ("city_port", "City: City port", "number", 4777),
    ("city_idle_min", "City: City auto close (min)", "number", 30),
]

CONSTANTS = {
    "stage_brief": 1, "stage_register": 1, "stage_mock": 4, "stage_tests": 20,
    "stage_workers": 40, "stage_verify": 15, "stage_push": 2, "stage_report": 2,
    "stage_e2e": 10, "stage_merge": 5, "board_watch_sec": 60, "progress_eta_min_pct": 20,
    "statusline_refresh_sec": 60, "city_governor_wait_sec": 60, "estimate_target_pct": 50,
    "estimate_bias_min": 5, "estimate_big_min": 120, "state_keep_hours": 24,
    "state_warn_lines": 300, "state_header_lines": 40, "state_trim_auto": "on",
    "compact_clear_at": 2, "compact_clear_check_sec": 30, "cleanup_days": 14,
    "docs_keep": "", "owner_order_hours": 24, "owner_order_min_chars": 20,
    "check_budget_s": 60,   # check-blocks: BUILD and GUARD TESTS per task only under it
    "unused_pane_min": 30,  # check-blocks slice 8: the sweep closes a pane that never got a prompt, idle over it
    "nightly_hour": 22, "light_test_s": 120, "light_test_mb": 1024,   # check-blocks section 15 (owner 1A)
    "verify_box_min": 15,   # check-blocks section 19/21: the run or browser check time box
}

CHANGE_LINE = "change: /plugin -> Installed -> auto-pipeline -> Configure"
CORE_LINE = "core paths of this repo: agent_repo.conf"   # owner 1A 2026-11-25
MOVED_BOTH = "moved level3_paths, level4_paths to agent_repo.conf (repo file, commit it)"

# A fake `claude` on PATH. Every call appends {"args", "cwd", "stdin"} to calls.jsonl.
# mode file "ok": `plugin configure <id> --values-stdin` merges the JSON into
# settings.json pluginConfigs[<id>].options (like the real one); `plugin update` exits 0.
# mode file "fail": prints "boom" on stderr, exit 1.
CLAUDE_STUB = r'''#!%(py)s
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
data = sys.stdin.read() if "--values-stdin" in sys.argv else ""
with open(os.path.join(here, "calls.jsonl"), "a") as fh:
    fh.write(json.dumps({"args": sys.argv[1:], "cwd": os.getcwd(), "stdin": data}) + "\n")
mode = open(os.path.join(here, "mode")).read().strip()
if mode != "ok":
    sys.stderr.write("boom\n"); sys.exit(1)
if sys.argv[1:3] == ["plugin", "configure"] and "--values-stdin" in sys.argv:
    cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.environ["HOME"], ".claude")
    path = os.path.join(cfg, "settings.json")
    try:
        settings = json.load(open(path))
    except Exception:
        settings = {}
    opts = settings.setdefault("pluginConfigs", {}).setdefault(sys.argv[3], {}).setdefault("options", {})
    opts.update(json.loads(data))
    json.dump(settings, open(path, "w"))
    print("Configuration saved. Restart Claude Code to apply it.")
'''


class Home:
    """A throwaway HOME with its own .claude dir; env() is what a script sees."""

    def __init__(self):
        self.base = tempfile.mkdtemp(prefix="settings_configure_")
        self.home = os.path.join(self.base, "home")
        self.cfg = os.path.join(self.home, ".claude")
        os.makedirs(os.path.join(self.cfg, "plugins"))
        self.repo = os.path.join(self.base, "repo")
        os.makedirs(self.repo)
        self.stub = os.path.join(self.base, "stubbin")
        os.makedirs(self.stub)
        path = os.path.join(self.stub, "claude")
        with open(path, "w") as fh:
            fh.write(CLAUDE_STUB % {"py": sys.executable})
        os.chmod(path, 0o755)
        self.claude_mode("ok")

    def close(self):
        shutil.rmtree(self.base, True)

    def claude_mode(self, mode):
        with open(os.path.join(self.stub, "mode"), "w") as fh:
            fh.write(mode)

    def calls(self):
        path = os.path.join(self.stub, "calls.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("CLAUDE_PLUGIN_OPTION_")
               and k not in ("CLAUDE_CONFIG_DIR", "AUTO_PIPELINE_USER_CONF")}
        env["HOME"] = self.home
        env["PATH"] = self.stub + os.pathsep + env.get("PATH", "/usr/bin:/bin")
        env.update(extra)
        return env

    def options(self):
        try:
            with open(os.path.join(self.cfg, "settings.json")) as fh:
                return json.load(fh)["pluginConfigs"]["auto-pipeline@auto-pipeline"]["options"]
        except Exception:
            return {}

    def configure(self, options, plugin_id="auto-pipeline@auto-pipeline", other=None):
        data = {"theme": "dark", "pluginConfigs": {plugin_id: {"options": options}}}
        if other:
            data["pluginConfigs"].update(other)
        with open(os.path.join(self.cfg, "settings.json"), "w") as fh:
            json.dump(data, fh)

    def write(self, rel, text):
        path = os.path.join(self.base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
        return path

    def installed(self, entries):
        with open(os.path.join(self.cfg, "plugins", "installed_plugins.json"), "w") as fh:
            json.dump({"version": 2, "plugins": {
                "auto-pipeline@auto-pipeline": entries,
                "other@other": [{"scope": "project", "projectPath": self.repo, "version": "0.1.0"}],
            }}, fh)


def run_cli(args, env, script="agent_conf.py"):
    return subprocess.run([sys.executable, os.path.join(BIN, script)] + args,
                          capture_output=True, text=True, env=env, timeout=30)


class TestSchema(unittest.TestCase):
    def test_plugin_id(self):
        self.assertEqual(agent_conf.PLUGIN_ID, "auto-pipeline@auto-pipeline")

    def test_sixteen_settings_in_the_brief_order(self):
        got = [(s["key"], s["title"], s["type"], s["default"]) for s in agent_conf.SETTINGS]
        self.assertEqual(got, ORDER)

    def test_every_setting_has_a_plain_description(self):
        for s in agent_conf.SETTINGS:
            self.assertTrue(s["description"].strip(), s["key"])
            self.assertLessEqual(len(s["description"]), 200, s["key"])

    def test_pickers(self):
        by = {s["key"]: s for s in agent_conf.SETTINGS}
        self.assertEqual(by["runtime"]["options"], ["auto", "orca", "plain", "cloud"])
        self.assertIn("auto", by["permission_mode"]["options"])
        self.assertIn("bypassPermissions", by["permission_mode"]["options"])
        for key in ("main_manager", "task_manager"):
            opts = by[key]["options"]
            self.assertEqual(opts[0], "opus-5.5:high", key)
            self.assertIn("opus-5.5:xhigh", opts, key)
            for spec in opts:
                self.assertIsNone(agent_conf.validate_value("main_manager", spec), spec)
        self.assertEqual(by["helper_model"]["options"][0], "sonnet-5:medium")

    def test_number_bounds(self):
        by = {s["key"]: s for s in agent_conf.SETTINGS}
        self.assertEqual((by["max_usage_percent"]["min"], by["max_usage_percent"]["max"]), (1, 100))
        self.assertEqual((by["housekeep_interval_min"]["min"], by["housekeep_interval_min"]["max"]), (0, 1440))
        self.assertEqual((by["city_port"]["min"], by["city_port"]["max"]), (1024, 65535))
        self.assertEqual((by["clear_quiet_min"]["min"], by["clear_quiet_min"]["max"]), (0, 1440))

    def test_plugin_json_user_config_is_built_from_settings(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest["userConfig"], agent_conf.user_config())
        self.assertEqual(list(manifest["userConfig"]), [k for k, _, _, _ in ORDER])

    def test_user_config_uses_only_fields_claude_code_knows(self):
        known = {"type", "title", "description", "default", "options", "min", "max"}
        for key, field in agent_conf.user_config().items():
            self.assertLessEqual(set(field), known, key)
            if "options" in field:
                self.assertEqual(field["type"], "string", key)
                self.assertIn(field["default"], field["options"], key)
            if "min" in field:
                self.assertEqual(field["type"], "number", key)

    def test_constants(self):
        self.assertEqual(agent_conf.CONSTANTS, CONSTANTS)

    def test_no_constant_is_a_setting(self):
        keys = {s["key"] for s in agent_conf.SETTINGS}
        self.assertFalse(keys & set(agent_conf.CONSTANTS))

    def test_template_file_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(BIN, "agent.conf.default")))

    def test_repo_has_no_agent_conf(self):
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "agent.conf"],
                             capture_output=True, text=True).stdout
        self.assertEqual(out.strip(), "")


class TestGet(unittest.TestCase):
    def setUp(self):
        self.h = Home()

    def tearDown(self):
        self.h.close()

    def test_nothing_set_gives_every_default(self):
        env = self.h.env()
        for key, _, _, default in ORDER:
            self.assertEqual(agent_conf.get(key, env), default, key)
            self.assertEqual(agent_conf.source(key, env), "default", key)

    def test_configure_value_wins(self):
        self.h.configure({"language": "zh", "max_usage_percent": 60, "auto_resume": False})
        env = self.h.env()
        self.assertEqual(agent_conf.get("language", env), "zh")
        self.assertEqual(agent_conf.get("max_usage_percent", env), 60)
        self.assertIs(agent_conf.get("auto_resume", env), False)
        self.assertEqual(agent_conf.source("language", env), "Configure")

    def test_numbers_and_booleans_stored_as_text(self):
        self.h.configure({"max_usage_percent": "60", "auto_update": "false", "todo_before_agent": "true"})
        env = self.h.env()
        self.assertEqual(agent_conf.get("max_usage_percent", env), 60)
        self.assertIs(agent_conf.get("auto_update", env), False)
        self.assertIs(agent_conf.get("todo_before_agent", env), True)

    def test_claude_config_dir_is_used(self):
        other = os.path.join(self.h.base, "cfg2")
        os.makedirs(other)
        with open(os.path.join(other, "settings.json"), "w") as fh:
            json.dump({"pluginConfigs": {"auto-pipeline@auto-pipeline": {"options": {"city_port": 5000}}}}, fh)
        self.h.configure({"city_port": 6000})
        self.assertEqual(agent_conf.get("city_port", self.h.env(CLAUDE_CONFIG_DIR=other)), 5000)

    def test_env_option_when_configure_has_none(self):
        env = self.h.env(CLAUDE_PLUGIN_OPTION_LANGUAGE="ms", CLAUDE_PLUGIN_OPTION_MAX_USAGE_PERCENT="30")
        self.assertEqual(agent_conf.get("language", env), "ms")
        self.assertEqual(agent_conf.get("max_usage_percent", env), 30)
        self.assertEqual(agent_conf.source("language", env), "env")

    def test_file_beats_env(self):
        self.h.configure({"max_usage_percent": 60})
        env = self.h.env(CLAUDE_PLUGIN_OPTION_MAX_USAGE_PERCENT="40")
        self.assertEqual(agent_conf.get("max_usage_percent", env), 60)

    def test_other_plugins_options_are_not_read(self):
        self.h.configure({}, other={"x@y": {"options": {"language": "zh"}}})
        self.assertEqual(agent_conf.get("language", self.h.env()), "en")

    def test_bad_settings_json_gives_defaults_and_a_warning(self):
        with open(os.path.join(self.h.cfg, "settings.json"), "w") as fh:
            fh.write("{not json")
        env = self.h.env()
        self.assertEqual(agent_conf.get("max_usage_percent", env), 80)
        self.assertTrue(any("settings.json" in w for w in agent_conf.warnings(env)))

    def test_out_of_range_gives_default_and_warning(self):
        self.h.configure({"max_usage_percent": 400})
        env = self.h.env()
        self.assertEqual(agent_conf.get("max_usage_percent", env), 80)
        self.assertEqual(agent_conf.source("max_usage_percent", env), "default")
        lines = agent_conf.warnings(env)
        self.assertEqual(len(lines), 1)
        self.assertIn("max_usage_percent=400", lines[0])
        self.assertIn("1-100", lines[0])
        self.assertIn("default 80", lines[0])

    def test_bad_picker_value_gives_default(self):
        self.h.configure({"runtime": "docker", "permission_mode": "yolo"})
        env = self.h.env()
        self.assertEqual(agent_conf.get("runtime", env), "auto")
        self.assertEqual(agent_conf.get("permission_mode", env), "bypassPermissions")
        self.assertEqual(len(agent_conf.warnings(env)), 2)

    def test_manager_below_the_decider_floor_is_refused(self):
        self.h.configure({"main_manager": "sonnet-5:high", "task_manager": "opus-5.5:low"})
        env = self.h.env()
        self.assertEqual(agent_conf.get("main_manager", env), "opus-5.5:high")
        self.assertEqual(agent_conf.get("task_manager", env), "opus-5.5:high")
        self.assertEqual(len(agent_conf.warnings(env)), 2)

    def test_manager_value_outside_the_picker_but_above_the_floor_is_kept(self):
        self.h.configure({"main_manager": "fable-5.2:max"})
        self.assertEqual(agent_conf.get("main_manager", self.h.env()), "fable-5.2:max")

    def test_helper_model_drives_the_three_helper_roles(self):
        self.h.configure({"helper_model": "sonnet-5:high"})
        env = self.h.env()
        for role in ("fast_lane_deputy", "merge_deputy", "worker"):
            self.assertEqual(agent_conf.get(role, env), "sonnet-5:high", role)
        self.assertEqual(agent_conf.get("main_manager", env), "opus-5.5:high")

    def test_bad_language_and_bad_paths(self):
        self.h.configure({"language": "Chinese"})
        self.assertEqual(agent_conf.get("language", self.h.env()), "en")

    def test_danger_paths_is_no_setting_any_more(self):
        # owner 1A 2026-11-25: core paths are facts of one repo (agent_repo.conf), not a user setting
        self.h.configure({"danger_paths": "src/"})
        with self.assertRaises(KeyError):
            agent_conf.get("danger_paths", self.h.env())
        self.assertNotIn("danger_paths", agent_conf.user_config())

    def test_constant_keys(self):
        env = self.h.env(CLAUDE_PLUGIN_OPTION_STAGE_TESTS="99")
        for key, value in CONSTANTS.items():
            self.assertEqual(agent_conf.get(key, env), value, key)
            self.assertEqual(agent_conf.source(key, env), "constant", key)

    def test_unknown_key(self):
        with self.assertRaises(KeyError):
            agent_conf.get("level3_paths", self.h.env())

    def test_old_files_are_never_read_for_a_value(self):
        with open(os.path.join(self.h.repo, "agent.conf"), "w") as fh:
            fh.write("language=zh\nmax_usage_percent=90\n")
        user = self.h.write("home/.claude/auto-pipeline.conf", "permission_mode=bypassPermissions\n")
        old_cwd = os.getcwd()
        os.chdir(self.h.repo)
        try:
            env = self.h.env(AUTO_PIPELINE_USER_CONF=user)
            self.assertEqual(agent_conf.get("language", env), "en")
            self.assertEqual(agent_conf.get("max_usage_percent", env), 80)
            self.assertEqual(agent_conf.get("permission_mode", env), "bypassPermissions")   # the default, not the old file's
        finally:
            os.chdir(old_cwd)

    def test_text(self):
        self.assertEqual(agent_conf.text(True), "on")
        self.assertEqual(agent_conf.text(False), "off")
        self.assertEqual(agent_conf.text(4), "4")
        self.assertEqual(agent_conf.text("zh"), "zh")


class TestCli(unittest.TestCase):
    def setUp(self):
        self.h = Home()

    def tearDown(self):
        self.h.close()

    def test_get_prints_the_text_value(self):
        self.h.configure({"language": "zh", "auto_resume": False})
        env = self.h.env()
        self.assertEqual(run_cli(["get", "language"], env).stdout, "zh\n")
        self.assertEqual(run_cli(["get", "auto_resume"], env).stdout, "off\n")
        self.assertEqual(run_cli(["get", "max_usage_percent"], env).stdout, "80\n")
        self.assertEqual(run_cli(["get", "worker"], env).stdout, "sonnet-5:medium\n")
        self.assertEqual(run_cli(["get", "stage_tests"], env).stdout, "20\n")

    def test_get_unknown_key_exits_2(self):
        res = run_cli(["get", "nope"], self.h.env())
        self.assertEqual(res.returncode, 2)
        self.assertEqual(res.stdout, "")
        self.assertIn("nope", res.stderr)

    def test_show_is_a_table_by_group_with_the_change_line_last(self):
        self.h.configure({"language": "zh"})
        res = run_cli(["show"], self.h.env())
        self.assertEqual(res.returncode, 0, res.stderr)
        lines = res.stdout.rstrip("\n").splitlines()
        self.assertEqual(lines[-2:], [CHANGE_LINE, CORE_LINE])
        body = res.stdout
        self.assertNotIn("Danger paths", body)
        for group in ("Basic", "Models", "Load", "Permissions", "Rules", "Stuck", "City"):
            self.assertIn(group, body)
        last = -1
        for _, title, _, _ in ORDER:
            name = title.split(": ", 1)[1]
            pos = body.find(name)
            self.assertGreater(pos, last, name)
            last = pos
        zh_line = [l for l in lines if "Language" in l][0]
        self.assertIn("zh", zh_line)
        self.assertIn("*", zh_line)  # not the default
        port_line = [l for l in lines if "City port" in l][0]
        self.assertNotIn("*", port_line)
        self.assertNotIn("stage_tests", body)

    def test_show_names_a_bad_stored_value(self):
        self.h.configure({"max_usage_percent": 999})
        res = run_cli(["show"], self.h.env())
        self.assertIn("max_usage_percent=999", res.stdout)

    def test_show_never_writes(self):
        self.h.configure({"language": "zh"})
        path = os.path.join(self.h.cfg, "settings.json")
        before = open(path).read()
        run_cli(["show"], self.h.env())
        self.assertEqual(open(path).read(), before)
        self.assertEqual(sorted(os.listdir(self.h.cfg)), ["plugins", "settings.json"])


class TestRepoPathsFile(unittest.TestCase):
    """owner 1A 2026-11-25: agent_repo.conf at the main repo root holds level3_paths and level4_paths."""

    def setUp(self):
        self.h = Home()

    def tearDown(self):
        self.h.close()

    def write(self, text):
        with open(os.path.join(self.h.repo, "agent_repo.conf"), "w") as fh:
            fh.write(text)

    def test_no_file_is_built_ins_only(self):
        self.assertEqual(agent_conf.repo_paths(self.h.repo), ({}, []))

    def test_both_keys(self):
        self.write("# core paths of this repo\nlevel3_paths=PRINCIPLES.md,skills/\nlevel4_paths=.claude-plugin/,hooks/\n")
        self.assertEqual(agent_conf.repo_paths(self.h.repo),
                         ({"level3_paths": "PRINCIPLES.md,skills/", "level4_paths": ".claude-plugin/,hooks/"}, []))

    def test_an_empty_value_and_other_keys(self):
        self.write("level3_paths=\nlanguage=zh\n")
        values, warnings = agent_conf.repo_paths(self.h.repo)
        self.assertEqual(values.get("level3_paths", ""), "")
        self.assertNotIn("language", values)

    def test_a_bad_glob_list_is_left_out_and_said(self):
        self.write("level3_paths=/etc/,src/\nlevel4_paths=db/\n")
        values, warnings = agent_conf.repo_paths(self.h.repo)
        self.assertEqual(values, {"level4_paths": "db/"})
        self.assertEqual(len(warnings), 1, warnings)
        self.assertTrue(warnings[0].startswith("SETTINGS: level3_paths=/etc/,src/ in agent_repo.conf"), warnings)

    def test_never_raises(self):
        os.mkdir(os.path.join(self.h.repo, "agent_repo.conf"))
        values, warnings = agent_conf.repo_paths(self.h.repo)
        self.assertEqual(values, {})


class TestMigration(unittest.TestCase):
    def setUp(self):
        self.h = Home()
        self.user = os.path.join(self.h.cfg, "auto-pipeline.conf")
        self.conf = os.path.join(os.path.realpath(self.h.repo), "agent.conf")

    def tearDown(self):
        self.h.close()

    def migrate(self, **extra):
        return agent_conf.migrate(self.h.repo, self.h.env(**extra))

    def old_conf(self, text):
        with open(os.path.join(self.h.repo, "agent.conf"), "w") as fh:
            fh.write(text)

    def configure_calls(self):
        return [c for c in self.h.calls() if c["args"][:2] == ["plugin", "configure"]]

    def test_no_old_files_no_lines_no_call(self):
        self.assertEqual(self.migrate(), [])
        self.assertEqual(self.h.calls(), [])

    def test_differing_values_are_moved_with_the_official_command(self):
        self.old_conf("language=zh\nmax_usage_percent=60\nauto_resume=no\nboard_guard=record\n"
                      "worker=sonnet-5:high\nfast_lane_deputy=sonnet-5:high\nmerge_deputy=sonnet-5:high\n")
        out = self.migrate()
        calls = self.configure_calls()
        self.assertEqual(len(calls), 1, self.h.calls())
        self.assertEqual(calls[0]["args"], ["plugin", "configure", "auto-pipeline@auto-pipeline", "--values-stdin"])
        self.assertEqual(json.loads(calls[0]["stdin"]), {
            "language": "zh", "max_usage_percent": "60", "auto_resume": "false",
            "todo_before_agent": "false", "helper_model": "sonnet-5:high"})
        self.assertEqual(self.h.options()["language"], "zh")
        self.assertIn("moved language=zh from %s to Configure" % self.conf, out)
        self.assertIn("moved max_usage_percent=60 from %s to Configure" % self.conf, out)
        self.assertIn("moved auto_resume=false from %s to Configure" % self.conf, out)
        self.assertTrue(out[0].startswith("SETTINGS MOVED: %s" % self.conf), out)
        self.assertIn("not read any more", out[0])

    def test_values_equal_to_the_default_are_not_moved(self):
        self.old_conf("language=en\nmax_usage_percent=80\nboard_guard=on\nauto_resume=yes\n")
        out = self.migrate()
        self.assertEqual(self.configure_calls(), [])
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith("SETTINGS MOVED:"))

    def test_a_value_the_human_set_is_never_overwritten(self):
        self.old_conf("language=zh\nmax_usage_percent=60\ncity_port=4777\n")
        self.h.configure({"language": "ms", "city_port": 5000})
        out = self.migrate()
        self.assertEqual(json.loads(self.configure_calls()[0]["stdin"]), {"max_usage_percent": "60"})
        self.assertEqual(self.h.options()["language"], "ms")
        self.assertIn("kept language=ms in Configure, skipped language=zh from %s" % self.conf, out)
        self.assertFalse([l for l in out if "city_port" in l], out)  # old value = default, nothing to say

    def test_same_value_already_in_configure_says_nothing(self):
        self.old_conf("language=zh\n")
        self.h.configure({"language": "zh"})
        out = self.migrate()
        self.assertEqual(self.configure_calls(), [])
        self.assertFalse([l for l in out if "language" in l], out)

    # owner 1A 2026-11-25: the old level paths go into the repo's own agent_repo.conf, never Configure
    def repo_conf(self):
        path = os.path.join(self.h.repo, "agent_repo.conf")
        return open(path).read() if os.path.exists(path) else None

    def test_level_paths_move_into_agent_repo_conf(self):
        self.old_conf("level3_paths=src/money/\nlevel4_paths=db/,hooks/\nlanguage=zh\n")
        out = self.migrate()
        self.assertEqual(self.repo_conf(), "level3_paths=src/money/\nlevel4_paths=db/,hooks/\n")
        self.assertIn(MOVED_BOTH, out)
        payload = json.loads(self.configure_calls()[0]["stdin"])
        self.assertEqual(payload, {"language": "zh"})
        for key in ("level3_paths", "level4_paths", "danger_paths"):
            self.assertNotIn(key, self.h.options())

    def test_only_the_keys_there_are_moved(self):
        self.old_conf("level4_paths=db/\n")
        out = self.migrate()
        self.assertEqual(self.repo_conf(), "level4_paths=db/\n")
        self.assertIn("moved level4_paths to agent_repo.conf (repo file, commit it)", out)
        self.assertEqual(self.configure_calls(), [])

    def test_empty_level_paths_are_not_moved(self):
        self.old_conf("level3_paths=\nlevel4_paths=\n")
        out = self.migrate()
        self.assertIsNone(self.repo_conf())
        self.assertFalse([l for l in out if "agent_repo.conf" in l], out)

    def test_a_key_already_in_agent_repo_conf_is_never_overwritten(self):
        with open(os.path.join(self.h.repo, "agent_repo.conf"), "w") as fh:
            fh.write("# core paths\nlevel4_paths=infra/\n")
        self.old_conf("level3_paths=src/money/\nlevel4_paths=db/\n")
        out = self.migrate()
        text = self.repo_conf()
        self.assertIn("level4_paths=infra/\n", text)
        self.assertNotIn("db/", text)
        self.assertIn("level3_paths=src/money/\n", text)
        self.assertTrue(text.startswith("# core paths\n"), text)
        self.assertIn("moved level3_paths to agent_repo.conf (repo file, commit it)", out)
        self.assertTrue([l for l in out if l.startswith("kept level4_paths=infra/ in agent_repo.conf")], out)

    def test_the_level_move_happens_once(self):
        self.old_conf("level3_paths=src/money/\n")
        self.migrate()
        os.remove(os.path.join(self.h.repo, "agent_repo.conf"))
        self.assertEqual(self.migrate(), [])
        self.assertIsNone(self.repo_conf())

    def test_once_the_same_file_is_quiet(self):
        self.old_conf("language=zh\n")
        self.assertTrue(self.migrate())
        self.assertEqual(self.migrate(), [])
        self.assertEqual(len(self.configure_calls()), 1)
        marker = os.path.join(self.h.cfg, "auto-pipeline-migrated.json")
        with open(marker) as fh:
            self.assertIn(self.conf, json.load(fh))

    def test_a_changed_old_file_is_read_again(self):
        self.old_conf("language=zh\n")
        self.migrate()
        self.old_conf("language=zh\nmax_usage_percent=70\n")
        out = self.migrate()
        self.assertIn("moved max_usage_percent=70 from %s to Configure" % self.conf, out)

    def test_a_failed_write_prints_the_exact_command_and_tries_again(self):
        self.old_conf("language=zh\n")
        self.h.claude_mode("fail")
        out = "\n".join(self.migrate())
        self.assertIn("SETTINGS MOVE FAILED:", out)
        self.assertIn("boom", out)
        self.assertIn("claude plugin configure auto-pipeline@auto-pipeline --values-stdin <<< '{\"language\": \"zh\"}'", out)
        self.assertNotIn("moved language", out)
        self.assertFalse(os.path.exists(os.path.join(self.h.cfg, "auto-pipeline-migrated.json")))
        self.h.claude_mode("ok")
        self.assertIn("moved language=zh from %s to Configure" % self.conf, self.migrate())

    def test_no_claude_on_path_is_said(self):
        self.old_conf("language=zh\n")
        out = "\n".join(self.migrate(PATH="/nonexistent"))
        self.assertIn("SETTINGS MOVE FAILED:", out)
        self.assertIn("--values-stdin", out)

    def test_a_changed_constant_is_named_as_fixed(self):
        self.old_conf("stage_tests=33\nstate_keep_hours=24\n")
        out = self.migrate()
        self.assertIn("fixed: stage_tests=33 in %s is now fixed at 20" % self.conf, out)
        self.assertFalse([l for l in out if "state_keep_hours" in l], out)
        self.assertEqual(self.configure_calls(), [])

    def test_an_unknown_key_is_named_as_dropped(self):
        self.old_conf("adhd=off\n")
        out = self.migrate()
        self.assertIn("dropped: adhd=off in %s is not a setting any more" % self.conf, out)

    def test_the_user_file_moves_too_and_wins_for_its_keys(self):
        self.old_conf("permission_mode=acceptEdits\n")
        with open(self.user, "w") as fh:
            fh.write("permission_mode=plan\nauto_update=off\n")   # plan: not the default (bypassPermissions)
        out = "\n".join(self.migrate())
        payload = {}
        for call in self.configure_calls():
            payload.update(json.loads(call["stdin"]))
        self.assertEqual(payload, {"permission_mode": "plan", "auto_update": "false"})
        self.assertIn("auto-pipeline.conf", out)

    def test_the_user_file_path_can_come_from_the_env(self):
        other = self.h.write("elsewhere/u.conf", "permission_mode=plan\n")
        self.migrate(AUTO_PIPELINE_USER_CONF=other)
        self.assertEqual(self.h.options().get("permission_mode"), "plan")

    def test_a_user_file_bypass_is_the_default_and_not_moved(self):
        # owner order 2026-11-25: bypassPermissions is the default, so nothing to write
        with open(self.user, "w") as fh:
            fh.write("permission_mode=bypassPermissions\n")
        self.migrate()
        self.assertEqual(self.configure_calls(), [])

    def test_retired_settings_are_ignored_not_moved(self):
        # check-blocks (owner 2026-11-25): Max agents and Heavy test slot/time are gone; an old value is
        # ignored, never moved, never an error (pc2 printed "plugin has no options heavy_test_slots")
        self.old_conf("max_agents=6\nheavy_test_slots=3\nlanguage=zh\n")
        out = "\n".join(self.migrate())
        self.assertEqual(json.loads(self.configure_calls()[0]["stdin"]), {"language": "zh"})
        self.assertNotIn("max_agents", out)
        self.assertNotIn("heavy_test_slots", out)
        self.assertNotIn("FAILED", out)

    def test_a_bad_old_value_is_not_moved(self):
        self.old_conf("max_usage_percent=999\nlanguage=zh\n")
        out = "\n".join(self.migrate())
        self.assertEqual(json.loads(self.configure_calls()[0]["stdin"]), {"language": "zh"})
        self.assertIn("max_usage_percent=999", out)

    def test_unreadable_old_file_is_said(self):
        os.mkdir(os.path.join(self.h.repo, "agent.conf"))
        out = "\n".join(self.migrate())
        self.assertIn("SETTINGS MOVED:", out)
        self.assertIn("cannot read", out)

    def test_the_old_file_is_never_changed(self):
        self.old_conf("language=zh\n")
        self.migrate()
        self.assertEqual(open(os.path.join(self.h.repo, "agent.conf")).read(), "language=zh\n")

    def test_cli(self):
        self.old_conf("language=zh\n")
        res = run_cli(["migrate", self.h.repo], self.h.env())
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("moved language=zh", res.stdout)


class TestScopes(unittest.TestCase):
    def setUp(self):
        self.h = Home()
        self.repo = os.path.realpath(self.h.repo)
        self.wt = os.path.join(self.h.base, "wt")
        os.makedirs(self.wt)
        self.wt = os.path.realpath(self.wt)

    def tearDown(self):
        self.h.close()

    def sync(self, folders, **extra):
        return agent_update.sync_scopes(folders, self.h.env(**extra))

    def updates(self):
        return [c for c in self.h.calls() if c["args"][:2] == ["plugin", "update"]]

    def test_all_on_the_newest_no_lines_no_call(self):
        self.h.installed([{"scope": "user", "version": "0.44.0"},
                          {"scope": "project", "projectPath": self.repo, "version": "0.44.0"}])
        self.assertEqual(self.sync([self.repo]), [])
        self.assertEqual(self.h.calls(), [])

    def test_stale_project_scope_of_this_folder_is_updated_in_that_folder(self):
        self.h.installed([{"scope": "user", "version": "0.44.0"},
                          {"scope": "project", "projectPath": self.wt, "version": "0.43.0"}])
        out = self.sync([self.wt, self.repo])
        calls = self.updates()
        self.assertEqual(len(calls), 1, self.h.calls())
        self.assertEqual(calls[0]["args"], ["plugin", "update", "auto-pipeline@auto-pipeline", "--scope", "project"])
        self.assertEqual(os.path.realpath(calls[0]["cwd"]), self.wt)
        self.assertEqual(out, ["updated project %s: 0.43.0 -> 0.44.0, restart to apply" % self.wt])

    def test_stale_user_scope(self):
        self.h.installed([{"scope": "user", "version": "0.43.0"},
                          {"scope": "project", "projectPath": self.repo, "version": "0.44.0"}])
        out = self.sync([self.repo])
        self.assertEqual(self.updates()[0]["args"][-2:], ["--scope", "user"])
        self.assertEqual(out, ["updated user: 0.43.0 -> 0.44.0, restart to apply"])

    def test_versions_compare_as_numbers(self):
        self.h.installed([{"scope": "user", "version": "0.9.0"},
                          {"scope": "project", "projectPath": self.repo, "version": "0.10.0"}])
        self.sync([self.repo])
        self.assertEqual([c["args"][-1] for c in self.updates()], ["user"])

    def test_other_folders_and_other_plugins_are_never_touched(self):
        gone = os.path.join(self.h.base, "gone")
        self.h.installed([{"scope": "user", "version": "0.44.0"},
                          {"scope": "project", "projectPath": gone, "version": "0.26.0"},
                          {"scope": "project", "projectPath": "/somewhere/else", "version": "0.30.0"}])
        self.assertEqual(self.sync([self.repo, self.wt]), [])
        self.assertEqual(self.h.calls(), [])

    def test_local_scope(self):
        self.h.installed([{"scope": "user", "version": "0.44.0"},
                          {"scope": "local", "projectPath": self.repo, "version": "0.40.0"}])
        self.sync([self.repo])
        self.assertEqual(self.updates()[0]["args"][-2:], ["--scope", "local"])

    def test_a_failed_update_prints_the_exact_command(self):
        self.h.installed([{"scope": "user", "version": "0.44.0"},
                          {"scope": "project", "projectPath": self.wt, "version": "0.43.0"}])
        self.h.claude_mode("fail")
        out = self.sync([self.wt])
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith("STALE SCOPE: project %s runs 0.43.0, newest 0.44.0" % self.wt), out)
        self.assertIn("boom", out[0])
        self.assertIn("cd %s && claude plugin update auto-pipeline@auto-pipeline --scope project" % self.wt, out[0])

    def test_auto_update_off_prints_the_command_and_runs_nothing(self):
        self.h.installed([{"scope": "user", "version": "0.43.0"},
                          {"scope": "project", "projectPath": "/somewhere/else", "version": "0.44.0"}])
        self.h.configure({"auto_update": False})
        out = self.sync([self.repo])
        self.assertEqual(self.h.calls(), [])
        self.assertEqual(len(out), 1, out)
        self.assertIn("STALE SCOPE: user", out[0])
        self.assertIn("claude plugin update auto-pipeline@auto-pipeline --scope user", out[0])

    def test_a_fresh_lock_means_another_start_is_updating(self):
        self.h.installed([{"scope": "user", "version": "0.43.0"},
                          {"scope": "project", "projectPath": "/somewhere/else", "version": "0.44.0"}])
        os.mkdir(os.path.join(self.h.cfg, "plugins", ".auto-pipeline-update.lock"))
        out = self.sync([self.repo])
        self.assertEqual(self.h.calls(), [])
        self.assertIn("STALE SCOPE: user", out[0])

    def test_an_old_lock_is_taken_over_and_removed_after(self):
        self.h.installed([{"scope": "user", "version": "0.43.0"},
                          {"scope": "project", "projectPath": "/somewhere/else", "version": "0.44.0"}])
        lock = os.path.join(self.h.cfg, "plugins", ".auto-pipeline-update.lock")
        os.mkdir(lock)
        old = time.time() - 3600
        os.utime(lock, (old, old))
        self.sync([self.repo])
        self.assertEqual(len(self.updates()), 1)
        self.assertFalse(os.path.exists(lock))

    def test_no_file_or_bad_file_no_lines_no_raise(self):
        self.assertEqual(self.sync([self.repo]), [])
        with open(os.path.join(self.h.cfg, "plugins", "installed_plugins.json"), "w") as fh:
            fh.write("[[")
        self.assertEqual(self.sync([self.repo]), [])
        self.assertEqual(self.h.calls(), [])

    def test_installed_plugins_json_is_never_written_here(self):
        self.h.installed([{"scope": "user", "version": "0.43.0"},
                          {"scope": "project", "projectPath": self.repo, "version": "0.44.0"}])
        path = os.path.join(self.h.cfg, "plugins", "installed_plugins.json")
        before = open(path).read()
        self.sync([self.repo])
        self.assertEqual(open(path).read(), before)

    def test_cli(self):
        self.h.installed([{"scope": "user", "version": "0.43.0"},
                          {"scope": "project", "projectPath": self.repo, "version": "0.44.0"}])
        res = run_cli(["sync", self.repo], self.h.env(), script="agent_update.py")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("updated user", res.stdout)

    def test_a_newer_cache_folder_counts_as_newest(self):
        self.h.installed([{"scope": "user", "version": "0.44.0"}])
        folder = os.path.join(self.h.cfg, "plugins", "cache", "auto-pipeline", "auto-pipeline", "0.45.0")
        os.makedirs(os.path.join(folder, ".claude-plugin"))
        open(os.path.join(folder, ".claude-plugin", "plugin.json"), "w").write("{}")
        os.makedirs(os.path.join(self.h.cfg, "plugins", "cache", "auto-pipeline", "auto-pipeline", "0.99.0"))
        out = self.sync([self.repo])
        self.assertEqual(out, ["updated user: 0.44.0 -> 0.45.0, restart to apply"])


if __name__ == "__main__":
    unittest.main()
