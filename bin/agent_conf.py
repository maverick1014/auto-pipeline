"""The one reader of the 16 auto-pipeline settings.

The settings live only in Claude Code: /plugin -> Installed -> auto-pipeline -> Configure.
They are stored in <claude config dir>/settings.json under
pluginConfigs["auto-pipeline@auto-pipeline"].options.<key>. Order of a read: that file,
then the hook env CLAUDE_PLUGIN_OPTION_<KEY>, then the default in SETTINGS. A stored
value that fails its check gives the default and one warning line (warnings()).

CLI: agent_conf.py get <key> | show | migrate <project root> | cli-model <spec>
     | you <role_key> <pid>

The old key=value files (a repo agent.conf, the user file) are read only by migrate(),
to move their values into Configure once.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess

PLUGIN_ID = "auto-pipeline@auto-pipeline"
CHANGE_LINE = "change: /plugin -> Installed -> auto-pipeline -> Configure"
REPO_FILE = "agent_repo.conf"
REPO_KEYS = ("level3_paths", "level4_paths")
CORE_LINE = "core paths of this repo: agent_repo.conf"
PERMISSION_MODES = ["acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan"]
RUNTIME_VALUES = ["auto", "orca", "plain", "cloud"]
EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]
MANAGER_PICKS = ["opus-5.5:high", "opus-5.5:xhigh"]
HELPER_PICKS = ["sonnet-5:medium", "sonnet-5:low", "sonnet-5:high", "opus-5.5:medium"]


def _s(key, title, kind, default, description, **extra):
    item = {"key": key, "title": title, "type": kind, "description": description,
            "default": default}
    item.update(extra)
    return item


SETTINGS = [
    _s("language", "Basic: Language", "string", "en",
       "Language to talk to you in, e.g. en, zh, ms. Code, file names and rule text stay English."),
    _s("runtime", "Basic: Runtime", "string", "auto",
       "How this machine runs agents. auto works it out, orca uses Orca terminals, plain and cloud use subagents only.",
       options=RUNTIME_VALUES),
    _s("auto_update", "Basic: Auto update", "boolean", True,
       "Install a newer auto-pipeline by itself at the next start. Off: you run claude plugin update yourself."),
    _s("main_manager", "Models: Main manager model", "string", "opus-5.5:high",
       "Model and effort of the main manager. Floor: Opus 5.5 or above, or any Fable, effort medium or above.",
       options=MANAGER_PICKS),
    _s("task_manager", "Models: Task manager model", "string", "opus-5.5:high",
       "Model and effort of a task manager. Floor: Opus 5.5 or above, or any Fable, effort medium or above.",
       options=MANAGER_PICKS),
    _s("helper_model", "Models: Helper model", "string", "sonnet-5:medium",
       "Model and effort of the fast-lane deputy, the merge deputy and every worker. Form: model-name:effort.",
       options=HELPER_PICKS),
    _s("max_agents", "Load: Max agents", "number", 4,
       "How many agents may run at once on this machine. Whole number, 1 to 16.", min=1, max=16),
    _s("max_usage_percent", "Load: Max memory %", "number", 80,
       "How much RAM or CPU may be used before agents wait. Whole number, 1 to 100.", min=1, max=100),
    _s("heavy_test_slots", "Load: Heavy test slot/time", "number", 1,
       "How many heavy test runs may run at once. Whole number, 1 to 8.", min=1, max=8),
    _s("permission_mode", "Permissions: Permission mode", "string", "bypassPermissions",
       "How much an agent may do without asking. bypassPermissions asks nothing; auto lets the model judge.",
       options=PERMISSION_MODES),
    _s("auto_resume", "Permissions: Auto resume", "boolean", True,
       "Resume the agents that were running by themselves when a main manager starts."),
    _s("todo_before_agent", "Rules: Todo before agent", "boolean", True,
       "On: a launch naming no open todo task is refused. Off: launches are only recorded on the board."),
    _s("watch_quiet_min", "Stuck: Consider stuck after (min)", "number", 15,
       "Minutes a running task's state file may stay unchanged before the board marks it not confirmed. 1 to 240.",
       min=1, max=240),
    _s("housekeep_interval_min", "Stuck: Tidy every (min)", "number", 120,
       "Minutes between housekeep passes that tidy leftovers. 0 = off. Whole number, 0 to 1440.",
       min=0, max=1440),
    _s("city_port", "City: City port", "number", 4777,
       "Port the agent city listens on, on 127.0.0.1 only. Whole number, 1024 to 65535.",
       min=1024, max=65535),
    _s("city_idle_min", "City: City auto close (min)", "number", 30,
       "Minutes the agent city keeps running with no browser open, then it stops by itself. 1 to 240.",
       min=1, max=240),
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
}

BY_KEY = {s["key"]: s for s in SETTINGS}
HELPER_ROLES = ("fast_lane_deputy", "merge_deputy", "worker", "interior_designer")   # city-office: the designer is a helper
DECIDER_KEYS = ("main_manager", "task_manager")
ROLE_KEYS = ["main_manager", "fast_lane_deputy", "merge_deputy", "task_manager", "worker", "interior_designer"]

ROLE_VALUE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9.\-]*)(?:\[1m\])?:(low|medium|high|xhigh|max)$")
LANGUAGE_RE = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")
MODEL_FAMILIES = ("opus", "sonnet", "haiku", "fable")
FLOOR_MESSAGE = ("A deciding role must run Opus 5.5 or above, or any Fable, "
                 "at effort medium or above.")
_OPUS_RE = re.compile(r"^opus-(\d+)(?:[.-](\d{1,2})(?!\d))?(?:[-.].*)?$")
TRUE_WORDS = ("true", "on", "yes", "1")
FALSE_WORDS = ("false", "off", "no", "0")


def user_config():
    """The plugin.json userConfig object, built from SETTINGS (same order)."""
    out = {}
    for s in SETTINGS:
        field = {"type": s["type"], "title": s["title"], "description": s["description"]}
        for name in ("options", "min", "max"):
            if name in s:
                field[name] = s[name]
        field["default"] = s["default"]
        out[s["key"]] = field
    return out


def text(value):
    """on/off for a bool, str() for the rest."""
    if isinstance(value, bool):
        return "on" if value else "off"
    return str(value)


def _wire(value):
    """A value as the string `claude plugin configure --values-stdin` takes."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def config_dir(env=None):
    env = os.environ if env is None else env
    return env.get("CLAUDE_CONFIG_DIR") or os.path.join(env.get("HOME") or os.path.expanduser("~"), ".claude")


def display_path(path):
    """PATH as ~/<rest> when it is under $HOME, else unchanged."""
    try:
        home = os.path.expanduser("~").rstrip("/")
        if home and path.startswith(home + "/"):
            return "~/" + path[len(home) + 1:]
    except Exception:
        pass
    return path


# ------------------------------------------------------------------ checks

def _strip_context_suffix(name):
    """Drop a trailing "[1m]" (the 1M context marker) from a model name."""
    return name[:-4] if name.endswith("[1m]") else name


def _validate_role(value):
    if not isinstance(value, str) or not ROLE_VALUE_RE.match(value):
        return "Must look like model-name:effort, effort one of low, medium, high, xhigh, max."
    return None


def _meets_model_floor(model):
    """True for any Fable, the opus alias, or Opus 5.5 and above."""
    model = _strip_context_suffix(model)
    name = model[7:] if model.startswith("claude-") else model
    if name == "fable" or name.startswith("fable-") or name == "opus":
        return True
    match = _OPUS_RE.match(name)
    if not match:
        return False
    minor = int(match.group(2)) if match.group(2) else 0
    return (int(match.group(1)), minor) >= (5, 5)


def _validate_decider(value):
    message = _validate_role(value)
    if message:
        return message
    model, effort = value.rsplit(":", 1)
    if not _meets_model_floor(model) or effort == "low":
        return FLOOR_MESSAGE
    return None


def _validate_picker(setting, value):
    if value not in setting["options"]:
        return "Must be one of: " + ", ".join(setting["options"]) + "."
    return None


def _validate_language(value):
    if not isinstance(value, str) or not LANGUAGE_RE.match(value):
        return "Must be a 2-letter lowercase language code, optionally with a region, e.g. en, zh, en-us."
    return None


def _validate_globs(value):
    if not isinstance(value, str):
        return "Must be comma-separated globs."
    if value.strip() == "":
        return None
    for item in value.split(","):
        item = item.strip()
        if not item:
            return "Empty item. Use comma-separated globs, no empty item."
        if re.search(r"\s", item):
            return "No white space inside a glob: %s" % item
        if item.startswith("/"):
            return "A glob must not start with /: %s" % item
        if ".." in item.split("/"):
            return "A glob must not hold a .. part: %s" % item
    return None


def _to_number(value):
    """int from an int, a whole float or digits text; else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.match(r"^-?\d+$", value.strip()):
        return int(value.strip())
    return None


def _to_bool(value):
    if isinstance(value, bool):
        return value
    word = value.strip().lower() if isinstance(value, str) else None
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    return None


def _number_problem(setting, value):
    number = _to_number(value)
    low, high = setting["min"], setting["max"]
    if number is None:
        return "Must be a whole number, %d to %d." % (low, high)
    if number < low or number > high:
        return "out of range %d-%d" % (low, high)
    return None


def _string_problem(key, value):
    setting = BY_KEY.get(key)
    if key in DECIDER_KEYS:
        return _validate_decider(value)
    if key in ("helper_model",) + HELPER_ROLES:
        return _validate_role(value)
    if key == "language":
        return _validate_language(value)
    if key in REPO_KEYS:
        return _validate_globs(value)
    if setting is not None and "options" in setting:
        return _validate_picker(setting, value)
    return None


def validate_value(key, value):
    """None when VALUE is allowed for KEY, else the reason. Keys without a rule pass."""
    setting = BY_KEY.get(key)
    if setting is not None and setting["type"] == "number":
        return _number_problem(setting, value)
    if setting is not None and setting["type"] == "boolean":
        return None if _to_bool(value) is not None else "Must be true or false."
    if key in CONSTANTS:
        return None
    return _string_problem(key, value)


def _check(setting, raw):
    """(value, None) when RAW fits SETTING, else (None, reason)."""
    key = setting["key"]
    why = validate_value(key, raw)
    if why:
        return None, why
    if setting["type"] == "number":
        return _to_number(raw), None
    if setting["type"] == "boolean":
        return _to_bool(raw), None
    return raw, None


# ------------------------------------------------------------------ reading

def _read_options(env):
    """(options dict, problem line or None) from settings.json. Never raises."""
    path = os.path.join(config_dir(env), "settings.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}, None
    except Exception:
        return {}, "SETTINGS: %s cannot be read as JSON, defaults used" % display_path(path)
    try:
        options = data["pluginConfigs"][PLUGIN_ID]["options"]
    except Exception:
        return {}, None
    return (options, None) if isinstance(options, dict) else ({}, None)


def _resolve(key, env):
    """(value, source) for KEY. KeyError for an unknown key."""
    env = os.environ if env is None else env
    if key in CONSTANTS:
        return CONSTANTS[key], "constant"
    if key in HELPER_ROLES:
        key = "helper_model"
    setting = BY_KEY[key]
    options, _ = _read_options(env)
    if key in options:
        value, why = _check(setting, options[key])
        if why is None:
            return value, "Configure"
    raw = env.get("CLAUDE_PLUGIN_OPTION_" + key.upper())
    if raw:
        value, why = _check(setting, raw)
        if why is None:
            return value, "env"
    return setting["default"], "default"


def get(key, env=None):
    """The value of KEY: Configure, else the env, else the default. KeyError if unknown."""
    return _resolve(key, env)[0]


def source(key, env=None):
    """Where get() found KEY: Configure, env, default or constant."""
    return _resolve(key, env)[1]


def _warning(setting, raw, why):
    key = setting["key"]
    phrase = "is " + why if why.startswith("out of range") else "is not valid (%s)" % why
    return "SETTINGS: %s=%s %s, default %s used" % (key, raw, phrase, text(setting["default"]))


def warnings(env=None):
    """One line per stored value that failed its check."""
    env = os.environ if env is None else env
    options, problem = _read_options(env)
    lines = [problem] if problem else []
    for setting in SETTINGS:
        if setting["key"] in options:
            _, why = _check(setting, options[setting["key"]])
            if why:
                lines.append(_warning(setting, options[setting["key"]], why))
    return lines


# ------------------------------------------------------------------ repo file

def repo_paths(project_root):
    """(dict, warnings) from <project root>/agent_repo.conf: level3_paths and level4_paths.
    A missing file or key is not in the dict; a bad glob list is left out with one warning.
    Never raises."""
    found, notes = {}, []
    try:
        with open(os.path.join(project_root, REPO_FILE), "r", encoding="utf-8") as fh:
            values = _parse_old(fh.read())
    except Exception:
        return found, notes
    for key in REPO_KEYS:
        if key not in values:
            continue
        why = _validate_globs(values[key])
        if why:
            notes.append("SETTINGS: %s=%s in %s is not valid (%s), left out" % (key, values[key], REPO_FILE, why))
        else:
            found[key] = values[key]
    return found, notes


# ------------------------------------------------------------------ show

def show_lines(env=None):
    rows, last = [], None
    for s in SETTINGS:
        group, name = s["title"].split(": ", 1)
        value = get(s["key"], env)
        shown = text(value) + ("" if value == s["default"] else " *")
        rows.append((group if group != last else "", name, shown, s["description"]))
        last = group
    widths = [max(len(r[i]) for r in rows) for i in range(3)]
    widths[2] = min(widths[2], 24)
    lines = ["  ".join(r[i].ljust(widths[i]) for i in range(3)) + "  " + r[3] for r in rows]
    return lines + warnings(env) + [CHANGE_LINE, CORE_LINE]


# ------------------------------------------------------------------ migration

USER_KEYS = ("permission_mode", "auto_update")
OLD_MAPS = {
    "board_guard": ("todo_before_agent", {"on": True, "record": False, "off": False}),
    "auto_resume": ("auto_resume", {"yes": True, "no": False}),
    "auto_update": ("auto_update", {"on": True, "off": False}),
}


def user_conf_path(env=None):
    """The old user-wide file (read only by migrate): $AUTO_PIPELINE_USER_CONF, else ~/.claude/..."""
    env = os.environ if env is None else env
    if env.get("AUTO_PIPELINE_USER_CONF"):
        return env["AUTO_PIPELINE_USER_CONF"]
    return os.path.join(env.get("HOME") or os.path.expanduser("~"), ".claude", "auto-pipeline.conf")


def _parse_old(body):
    values = {}
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _split_items(value):
    return [i.strip() for i in value.split(",") if i.strip()]


def _helper_candidate(values):
    for old in ("worker", "fast_lane_deputy", "merge_deputy"):
        if old in values:
            return values[old]
    return None


def _candidates(values, path, claimed):
    """(key, wire value, old name) moves and note lines for one old file."""
    moves, notes = [], []
    for old, value in values.items():
        key, mapped = old, value
        if old in CONSTANTS:
            if str(CONSTANTS[old]) != value:
                notes.append("fixed: %s=%s in %s is now fixed at %s" % (old, value, path, CONSTANTS[old]))
            continue
        if old in OLD_MAPS:
            key, table = OLD_MAPS[old]
            if value not in table:
                notes.append("skipped %s=%s from %s: not a value it knew" % (old, value, path))
                continue
            mapped = _wire(table[value])
        elif old in HELPER_ROLES + REPO_KEYS:
            continue
        elif old not in BY_KEY:
            notes.append("dropped: %s=%s in %s is not a setting any more" % (old, value, path))
            continue
        if key in claimed:
            notes.append("skipped %s=%s from %s: the user file wins" % (old, value, path))
            continue
        moves.append((key, mapped, old))
    helper = _helper_candidate(values)
    if helper is not None:
        moves.append(("helper_model", helper, "worker"))
    return moves, notes


def _judge(moves, path, options):
    """Split MOVES into (payload dict, lines): moved later, kept/skipped now."""
    payload, lines = {}, []
    for key, wire, old in moves:
        setting = BY_KEY[key]
        why = validate_value(key, wire)
        if why:
            lines.append("skipped %s=%s from %s: %s" % (old, wire, path, why))
            continue
        value, _ = _check(setting, wire)
        if value == setting["default"]:
            continue
        if key in options:
            now, bad = _check(setting, options[key])
            if bad is None and now == value:
                continue
            shown = text(now) if bad is None else options[key]
            lines.append("kept %s=%s in Configure, skipped %s=%s from %s" % (key, shown, key, wire, path))
            continue
        payload[key] = wire
    return payload, lines


def _read_old(path):
    """(text, None) or (None, error)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read(), None
    except Exception as exc:
        return None, "%s" % (exc.strerror or exc.__class__.__name__)


def _marker_path(env):
    return os.path.join(config_dir(env), "auto-pipeline-migrated.json")


def _marker(env):
    try:
        with open(_marker_path(env), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_marker(env, seen):
    data = _marker(env)
    data.update(seen)
    try:
        os.makedirs(config_dir(env), exist_ok=True)
        with open(_marker_path(env), "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


def _run_configure(payload, env):
    """None on success, else the reason text."""
    claude = shutil.which("claude", path=env.get("PATH"))
    if not claude:
        return "claude was not found on PATH"
    try:
        res = subprocess.run([claude, "plugin", "configure", PLUGIN_ID, "--values-stdin"],
                             input=json.dumps(payload), capture_output=True, text=True,
                             env=dict(env), timeout=120)
    except Exception as exc:
        return "claude plugin configure failed: %s" % exc.__class__.__name__
    if res.returncode != 0:
        detail = (res.stderr or res.stdout or "").strip().splitlines()
        return detail[0] if detail else "claude plugin configure exited %d" % res.returncode
    return None


def _old_files(project_root, env):
    """[(real path, kind)] of the old files that exist: repo file first."""
    found = []
    repo = os.path.join(os.path.realpath(project_root), "agent.conf")
    user = user_conf_path(env)
    for path, kind in ((repo, "repo"), (user, "user")):
        if os.path.lexists(path):
            found.append((os.path.realpath(path), kind))
    return found


def _header(path):
    return ("SETTINGS MOVED: %s is not read any more. Settings live only in "
            "/plugin -> Installed -> auto-pipeline -> Configure" % path)


def _plan_file(path, kind, env, options, claimed):
    """(payload, lines, digest or None) for one old file."""
    body, err = _read_old(path)
    lines = [_header(path)]
    if body is None:
        return {}, lines + ["cannot read %s: %s" % (path, err)], None
    values = _parse_old(body)
    if kind == "user":
        extra = [k for k in values if k not in USER_KEYS]
        values = {k: v for k, v in values.items() if k in USER_KEYS}
        lines += ["dropped: %s=%s in %s is not read from the user file" % (k, _parse_old(body)[k], path)
                  for k in extra]
    moves, notes = _candidates(values, path, claimed if kind == "repo" else ())
    payload, judged = _judge(moves, path, options)
    return payload, lines + notes + judged, hashlib.sha256(body.encode("utf-8")).hexdigest()


def _user_claims(files, env):
    for path, kind in files:
        body, _ = _read_old(path)
        if kind == "user" and body is not None:
            return {k for k in _parse_old(body) if k in USER_KEYS}
    return set()


def _move_levels(project_root, old_path, body):
    """Old level3_paths / level4_paths into <project root>/agent_repo.conf. (lines, ok)."""
    old = _parse_old(body)
    lines, new = [], []
    target = os.path.join(project_root, REPO_FILE)
    try:
        with open(target, "r", encoding="utf-8") as fh:
            current = fh.read()
    except FileNotFoundError:
        current = ""
    except Exception as exc:
        return ["cannot read %s: %s" % (target, exc.strerror or exc.__class__.__name__)], False
    have = _parse_old(current)
    for key in REPO_KEYS:
        value = old.get(key, "")
        if not value:
            continue
        why = _validate_globs(value)
        if why:
            lines.append("skipped %s=%s from %s: %s" % (key, value, old_path, why))
        elif key not in have:
            new.append((key, value))
        elif have[key] != value:
            lines.append("kept %s=%s in %s, skipped %s=%s from %s" % (key, have[key], REPO_FILE, key, value, old_path))
    if new:
        text_out = current + ("" if not current or current.endswith("\n") else "\n")
        text_out += "".join("%s=%s\n" % kv for kv in new)
        try:
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(text_out)
        except Exception as exc:
            return lines + ["cannot write %s: %s" % (target, exc.strerror or exc.__class__.__name__)], False
        lines.append("moved %s to %s (repo file, commit it)" % (", ".join(k for k, _ in new), REPO_FILE))
    return lines, True


def migrate(project_root, env=None):
    """Move the old files' values into Configure, once. Returns the lines to print."""
    env = dict(os.environ if env is None else env)
    files = _old_files(project_root, env)
    marker = _marker(env)
    claimed = _user_claims(files, env)
    options, _ = _read_options(env)
    lines, payload, seen, moved = [], {}, {}, []
    for path, kind in files:
        part, part_lines, digest = _plan_file(path, kind, env, options, claimed)
        if digest is not None and marker.get(path) == digest:
            continue
        lines += part_lines
        if digest is not None:
            seen[path] = digest
        if kind == "repo" and digest is not None:
            body, _ = _read_old(path)
            level_lines, level_ok = _move_levels(project_root, path, body or "")
            lines += level_lines
            if not level_ok:
                seen.pop(path, None)
        for key, wire in part.items():
            payload[key] = wire
            moved.append("moved %s=%s from %s to Configure" % (key, wire, path))
    if payload:
        failed = _run_configure(payload, env)
        if failed:
            return lines + ["SETTINGS MOVE FAILED: %s. Run: claude plugin configure %s --values-stdin <<< '%s'"
                            % (failed, PLUGIN_ID, json.dumps(payload))]
        lines += moved
    if seen:
        _write_marker(env, seen)
    return lines


# ------------------------------------------------------------------ own model (YOU line)

def _text(value):
    return value if isinstance(value, str) and value else None


def _flag(args, name):
    """The value of --NAME X or --NAME=X in ARGS, the last one."""
    found = None
    for i, arg in enumerate(args):
        if not isinstance(arg, str):
            continue
        if arg == name and i + 1 < len(args):
            found = _text(args[i + 1]) or found
        elif arg.startswith(name + "="):
            found = _text(arg[len(name) + 1:]) or found
    return found


def _family_effort(model, model_settings):
    """The effortLevel of the newest claude-<family>-... entry for a bare family word."""
    family = re.sub(r"\[.*\]$", "", model)
    if family not in MODEL_FAMILIES:
        return None
    best, best_version = None, None
    for key, entry in model_settings.items():
        if not isinstance(key, str) or not key.startswith("claude-%s-" % family):
            continue
        effort = _text(entry.get("effortLevel")) if isinstance(entry, dict) else None
        if not effort:
            continue
        version = tuple(int(n) for n in re.findall(r"-(\d{1,2})(?=-|$)", key))
        if best_version is None or version > best_version:
            best, best_version = effort, version
    return best


def _role_value(env, role_key):
    """(value, where) of the role's model:effort from Configure/env/default."""
    try:
        return get(role_key, env), "%s %s" % (source(role_key, env), role_key)
    except Exception:
        return "", "unknown"


def _model_part(args, env, settings, role_model, where):
    model, src = _flag(args, "--model"), "flag"
    if not model:
        model, src = _text(env.get("ANTHROPIC_MODEL")), "env"
    if not model:
        model, src = _text(settings.get("model")), "settings.json"
    if not model:
        model, src = _text(role_model), where
    return (model, src) if model else ("unknown", "unknown")


def _effort_part(args, env, settings, model, role_effort, where):
    effort, src = _flag(args, "--effort"), "flag"
    if not effort:
        effort, src = _text(env.get("CLAUDE_CODE_EFFORT_LEVEL")), "env"
    if not effort:
        src = "settings.json"
        table = settings.get("modelSettings")
        if isinstance(table, dict) and model != "unknown":
            for key in (model, _strip_context_suffix(model)):
                entry = table.get(key)
                if isinstance(entry, dict) and _text(entry.get("effortLevel")):
                    effort = entry["effortLevel"]
                    break
            else:
                effort = _family_effort(model, table)
    if not effort:
        effort = _text(settings.get("effortLevel"))
    if not effort:
        effort, src = _text(role_effort), where
    return (effort, src) if effort else ("unknown", "unknown")


def _you(args, env, settings, conf, role_key):
    settings = settings if isinstance(settings, dict) else {}
    role, where = _role_value(env, role_key)
    role_model, role_effort = role.split(":", 1) if ":" in role else ("", "")
    model, model_src = _model_part(args, env, settings, role_model, where)
    effort, effort_src = _effort_part(args, env, settings, model, role_effort, where)
    return "YOU: %s %s (model: %s, effort: %s)" % (model, effort, model_src, effort_src)


def you_line(args, env, settings, conf, role_key):
    """The YOU line: own model and effort and where each came from. Never raises.
    CONF is kept for old callers and ignored: the role value comes from get()."""
    try:
        return _you(args, env, settings, conf, role_key)
    except Exception:
        return "YOU: unknown unknown (model: unknown, effort: unknown)"


def _you_cli(role_key, pid):
    try:
        out = subprocess.run(["ps", "-o", "args=", "-p", str(pid)], capture_output=True,
                             text=True, timeout=10).stdout
        args = out.split()
    except Exception:
        args = []
    settings = None
    try:
        with open(os.path.join(config_dir(), "settings.json"), "r", encoding="utf-8") as fh:
            settings = json.load(fh)
    except Exception:
        settings = None
    return you_line(args, dict(os.environ), settings, {}, role_key)


def cli_model(spec):
    """The model name the claude CLI takes, from a role value like
    opus-5.5:high or a bare model name. The ":effort" part is dropped. A
    trailing "[1m]" (1M context) of the model part is kept: the family rule
    runs first, then the suffix goes back on (opus-5.5[1m]:xhigh gives
    opus[1m], claude-opus-5-5[1m] stays as it is). A name
    that starts with opus, sonnet, haiku or fable becomes that family word
    (the CLI refuses fable-5.1, it takes fable); anything else, a full id like
    claude-fable-5-1 or a name this file has never seen, goes through
    unchanged. The one place with this rule: agent_city.py calls it and
    agent-resume.sh asks it with `agent_conf.py cli-model <spec>`."""
    head = spec.split(":", 1)[0]
    base = _strip_context_suffix(head)
    suffix = head[len(base):]
    for family in MODEL_FAMILIES:
        if base.startswith(family):
            return family + suffix
    return base + suffix


# ------------------------------------------------------------------ CLI

USAGE = ("usage: agent_conf.py get <key> | show | migrate <project root> "
         "| cli-model <model[:effort]> | you <role_key> <pid>\n")


def _cmd_get(key):
    import sys
    try:
        sys.stdout.write(text(get(key)) + "\n")
        return 0
    except KeyError:
        sys.stderr.write("unknown setting: %s\n" % key)
        return 2


def _cmd_you(args):
    import sys
    try:
        line = _you_cli(args[0], args[-1])
    except Exception:
        line = "YOU: unknown unknown (model: unknown, effort: unknown)"
    sys.stdout.write(line + "\n")
    return 0


def _cmd_lines(make):
    import sys
    try:
        lines = make()
    except Exception as exc:
        lines = ["SETTINGS: %s" % exc.__class__.__name__]
    for line in lines:
        sys.stdout.write(line + "\n")
    return 0


def main(argv):
    import sys
    if len(argv) == 2 and argv[0] == "cli-model":
        sys.stdout.write(cli_model(argv[1]) + "\n")
        return 0
    if len(argv) == 2 and argv[0] == "get":
        return _cmd_get(argv[1])
    if argv == ["show"]:
        return _cmd_lines(show_lines)
    if len(argv) == 2 and argv[0] == "migrate":
        return _cmd_lines(lambda: migrate(argv[1]))
    if len(argv) in (3, 4) and argv[0] == "you":
        return _cmd_you(argv[1:])
    sys.stderr.write(USAGE)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
