"""Read, validate and write agent.conf.

agent.conf is a simple key=value text file. Order and unknown keys are kept.
"""

import json
import os
import re

NUMBER_BOUNDS = {
    "max_usage_percent": (1, 100),
    "heavy_test_slots": (1, 8),
    "max_agents": (1, 16),
    "monitor_interval_min": (1, 60),
    "stall_min": (1, 120),
    "city_port": (1024, 65535),
    "city_idle_min": (1, 240),
    "city_governor_wait_sec": (5, 3600),
    "city_relay_sec": (2, 60),
}

ROLE_KEYS = [
    "main_manager",
    "fast_lane_deputy",
    "merge_deputy",
    "task_manager",
    "worker",
]

EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]
PERMISSION_MODES = ["acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan"]
YES_NO = ["yes", "no"]
ON_OFF = ["on", "off"]
RUNTIME_VALUES = ["auto", "orca", "plain", "cloud"]

ROLE_VALUE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9.\-]*):(low|medium|high|xhigh|max)$")
LANGUAGE_RE = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")

HINTS = {
    "max_usage_percent": "How much RAM or CPU may be used before agents wait. Whole number, 1 to 100.",
    "heavy_test_slots": "How many heavy test runs may run at once. Whole number, 1 to 8.",
    "max_agents": "How many agents may run at once on this machine. Whole number, 1 to 16.",
    "monitor_interval_min": "How often the monitor checks every worktree. Whole number, 1 to 60.",
    "stall_min": "How long all three signals may stay quiet before a worktree is called stalled. Whole number, 1 to 120.",
    "main_manager": "Model and effort for the main manager. Form: model-name:effort. Floor: Opus 5.5 or above, or any Fable, effort medium or above.",
    "fast_lane_deputy": "Model and effort for the fast-lane deputy. Form: model-name:effort.",
    "merge_deputy": "Model and effort for the merge deputy. Form: model-name:effort.",
    "task_manager": "Model and effort for a task manager. Form: model-name:effort. Floor: Opus 5.5 or above, or any Fable, effort medium or above.",
    "worker": "Model and effort for a worker. Form: model-name:effort.",
    "permission_mode": "How much an agent may do without asking. One of: " + ", ".join(PERMISSION_MODES) + ".",
    "cloud_permission_mode": "Permission mode of a session started from the Agent City cloud page. One of: " + ", ".join(PERMISSION_MODES) + ". Missing or refused means auto.",
    "auto_resume": "Run agent-resume.sh by itself when a main manager starts. yes or no.",
    "language": "Language for talking to the human, e.g. en, zh, ms. Code and rules stay English.",
    "adhd": "Shape replies for a reader with ADHD (PRINCIPLES.md section E). on or off.",
    "runtime": "How this machine runs agents. One of: auto, orca, plain, cloud.",
    "city_port": "Port the agent city listens on, on 127.0.0.1 only. Whole number, 1024 to 65535.",
    "city_idle_min": "Minutes the agent city keeps running with no browser open, then it stops by itself. Whole number, 1 to 240.",
    "city_governor_wait_sec": "Seconds the governor has to answer an agent's question before the owner gets it in the city page. Whole number, 5 to 3600.",
    "city_relay_sec": "Seconds between syncs with a joined team relay. Whole number, 2 to 60.",
}

GROUPS = [
    ("limits", ["max_usage_percent", "heavy_test_slots", "max_agents",
                "monitor_interval_min", "stall_min"]),
    ("roles", list(ROLE_KEYS)),
    ("permission", ["permission_mode", "cloud_permission_mode", "auto_resume", "language", "adhd"]),
    ("runtime", ["runtime"]),
    ("city", ["city_port", "city_idle_min", "city_governor_wait_sec", "city_relay_sec"]),
]

_GROUP_OF = {}
for _group_name, _keys in GROUPS:
    for _key in _keys:
        _GROUP_OF[_key] = _group_name


def load(path):
    """Read a conf file into an ordered dict of str -> str."""
    conf = {}
    with open(path, "r") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            conf[key.strip()] = value.strip()
    return conf


def dumps(conf):
    """Render a conf dict back to file text, ending with one newline."""
    lines = ["%s=%s" % (key, value) for key, value in conf.items()]
    return "\n".join(lines) + "\n"


def save(conf, path):
    with open(path, "w") as fh:
        fh.write(dumps(conf))


def hint_for(key):
    hint = HINTS.get(key)
    if hint:
        return hint
    return "A setting from agent.conf."


def group_of(key):
    return _GROUP_OF.get(key, "other")


def _validate_number(key, value):
    low, high = NUMBER_BOUNDS[key]
    if not re.match(r"^-?\d+$", value.strip()):
        return "Must be a whole number, %d to %d." % (low, high)
    number = int(value)
    if number < low or number > high:
        return "Must be between %d and %d." % (low, high)
    return None


def _validate_role(value):
    if not ROLE_VALUE_RE.match(value):
        return "Must look like model-name:effort, effort one of low, medium, high, xhigh, max."
    return None


DECIDER_KEYS = ("main_manager", "task_manager")
FLOOR_MESSAGE = ("A deciding role must run Opus 5.5 or above, or any Fable, "
                 "at effort medium or above.")
_OPUS_RE = re.compile(r"^opus-(\d+)(?:[.-](\d{1,2})(?!\d))?(?:[-.].*)?$")


def _meets_model_floor(model):
    """True for any Fable, the opus alias, or Opus 5.5 and above."""
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


def _validate_permission_mode(value):
    if value not in PERMISSION_MODES:
        return "Must be one of: " + ", ".join(PERMISSION_MODES) + "."
    return None


def _validate_runtime(value):
    if value not in RUNTIME_VALUES:
        return "Must be one of: auto, orca, plain, cloud."
    return None


def _validate_yes_no(value):
    if value not in YES_NO:
        return "Must be yes or no."
    return None


def _validate_language(value):
    if not LANGUAGE_RE.match(value):
        return "Must be a 2-letter lowercase language code, optionally with a region, e.g. en, zh, en-us."
    return None


def _validate_on_off(value):
    if value not in ON_OFF:
        return "Must be on or off."
    return None


def validate_value(key, value):
    if key in NUMBER_BOUNDS:
        return _validate_number(key, value)
    if key in DECIDER_KEYS:
        return _validate_decider(value)
    if key in ROLE_KEYS:
        return _validate_role(value)
    if key in ("permission_mode", "cloud_permission_mode"):
        return _validate_permission_mode(value)
    if key == "auto_resume":
        return _validate_yes_no(value)
    if key == "language":
        return _validate_language(value)
    if key == "runtime":
        return _validate_runtime(value)
    if key in ("adhd", "auto_update"):
        return _validate_on_off(value)
    return None


def validate(conf):
    errors = {}
    for key, value in conf.items():
        message = validate_value(key, value)
        if message:
            errors[key] = message
    return errors


MODEL_FAMILIES = ("opus", "sonnet", "haiku", "fable")


USER_CONF_ENV = "AUTO_PIPELINE_USER_CONF"
USER_KEYS = ("permission_mode", "cloud_permission_mode", "auto_update")


def user_conf_path():
    """The user-wide conf file: $AUTO_PIPELINE_USER_CONF, else ~/.claude/auto-pipeline.conf."""
    env = os.environ.get(USER_CONF_ENV)
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), ".claude", "auto-pipeline.conf")


def display_path(path):
    """PATH as ~/<rest> when it is under $HOME, else unchanged."""
    try:
        home = os.path.expanduser("~").rstrip("/")
        if home and path.startswith(home + "/"):
            return "~/" + path[len(home) + 1:]
    except Exception:
        pass
    return path


def read_user_conf(path=None):
    """(values, ignored) of the user file. Never raises."""
    values, ignored = {}, []
    try:
        with open(path or user_conf_path(), "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except Exception:
        return {}, []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key in USER_KEYS and validate_value(key, value) is None:
            values[key] = value
        else:
            ignored.append("%s=%s" % (key, value))
    return values, ignored


def effective(key, conf, user_path=None):
    """(value, source) for KEY: the user file, else agent.conf, else (None, None)."""
    try:
        if key in USER_KEYS:
            values, _ = read_user_conf(user_path)
            if key in values:
                return values[key], display_path(user_path or user_conf_path())
        if key != "auto_update":
            value = conf.get(key)
            if isinstance(value, str) and validate_value(key, value) is None:
                return value, "agent.conf"
    except Exception:
        pass
    return None, None


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


def _you(args, env, settings, conf, role_key):
    settings = settings if isinstance(settings, dict) else {}
    role = _text(conf.get(role_key)) or ""
    role_model, role_effort = (role.split(":", 1) + [""])[:2] if ":" in role else ("", "")
    where = "agent.conf " + role_key

    model, model_src = _flag(args, "--model"), "flag"
    if not model:
        model, model_src = _text(env.get("ANTHROPIC_MODEL")), "env"
    if not model:
        model, model_src = _text(settings.get("model")), "settings.json"
    if not model:
        model, model_src = _text(role_model), where
    if not model:
        model, model_src = "unknown", "unknown"

    effort, effort_src = _flag(args, "--effort"), "flag"
    if not effort:
        effort, effort_src = _text(env.get("CLAUDE_CODE_EFFORT_LEVEL")), "env"
    if not effort:
        effort_src = "settings.json"
        table = settings.get("modelSettings")
        if isinstance(table, dict) and model != "unknown":
            entry = table.get(model)
            if isinstance(entry, dict) and _text(entry.get("effortLevel")):
                effort = entry["effortLevel"]
            else:
                effort = _family_effort(model, table)
    if not effort:
        effort = _text(settings.get("effortLevel"))
    if not effort:
        effort, effort_src = _text(role_effort), where
    if not effort:
        effort, effort_src = "unknown", "unknown"
    return "YOU: %s %s (model: %s, effort: %s)" % (model, effort, model_src, effort_src)


def you_line(args, env, settings, conf, role_key):
    """The YOU line: own model and effort and where each came from. Never raises."""
    try:
        return _you(args, env, settings, conf, role_key)
    except Exception:
        return "YOU: unknown unknown (model: unknown, effort: unknown)"


def _you_cli(role_key, conf_path, pid):
    import subprocess
    try:
        out = subprocess.run(["ps", "-o", "args=", "-p", str(pid)], capture_output=True,
                             text=True, timeout=10).stdout
        args = out.split()
    except Exception:
        args = []
    try:
        conf = load(conf_path)
    except Exception:
        conf = {}
    settings = None
    try:
        cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
        with open(os.path.join(cfg, "settings.json"), "r", encoding="utf-8") as fh:
            settings = json.load(fh)
    except Exception:
        settings = None
    return you_line(args, dict(os.environ), settings, conf, role_key)



def cli_model(spec):
    """The model name the claude CLI takes, from a role value like
    opus-5.5:xhigh or a bare model name. The ":effort" part is dropped. A name
    that starts with opus, sonnet, haiku or fable becomes that family word
    (the CLI refuses fable-5.1, it takes fable); anything else, a full id like
    claude-fable-5-1 or a name this file has never seen, goes through
    unchanged. The one place with this rule: agent_city.py calls it and
    agent-resume.sh asks it with `agent_conf.py cli-model <spec>`."""
    base = spec.split(":", 1)[0]
    for family in MODEL_FAMILIES:
        if base.startswith(family):
            return family
    return base


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "cli-model":
        sys.stdout.write(cli_model(sys.argv[2]) + "\n")
        sys.exit(0)
    if len(sys.argv) == 4 and sys.argv[1] == "effective":
        try:
            try:
                conf = load(sys.argv[3])
            except Exception:
                conf = {}
            value, source = effective(sys.argv[2], conf)
        except Exception:
            value, source = None, None
        if value is None:
            sys.exit(1)
        sys.stdout.write("%s\t%s\n" % (value, source))
        sys.exit(0)
    if len(sys.argv) == 5 and sys.argv[1] == "you":
        try:
            line = _you_cli(sys.argv[2], sys.argv[3], sys.argv[4])
        except Exception:
            line = "YOU: unknown unknown (model: unknown, effort: unknown)"
        sys.stdout.write(line + "\n")
        sys.exit(0)
    sys.stderr.write("usage: agent_conf.py cli-model <model[:effort]> | effective <key> <agent.conf> "
                     "| you <role_key> <agent.conf> <pid>\n")
    sys.exit(2)
