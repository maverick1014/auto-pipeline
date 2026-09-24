"""Read, validate and write agent.conf.

agent.conf is a simple key=value text file. Order and unknown keys are kept.
"""

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
}

ROLE_KEYS = [
    "main_manager",
    "fast_lane_deputy",
    "merge_deputy",
    "task_manager",
    "worker",
]

EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]
PERMISSION_MODES = ["default", "acceptEdits", "auto", "plan"]
YES_NO = ["yes", "no"]
RUNTIME_VALUES = ["auto", "orca", "plain", "cloud"]

ROLE_VALUE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9.\-]*):(low|medium|high|xhigh|max)$")
LANGUAGE_RE = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")

HINTS = {
    "max_usage_percent": "How much RAM or CPU may be used before agents wait. Whole number, 1 to 100.",
    "heavy_test_slots": "How many heavy test runs may run at once. Whole number, 1 to 8.",
    "max_agents": "How many agents may run at once on this machine. Whole number, 1 to 16.",
    "monitor_interval_min": "How often the monitor checks every worktree. Whole number, 1 to 60.",
    "stall_min": "How long all three signals may stay quiet before a worktree is called stalled. Whole number, 1 to 120.",
    "main_manager": "Model and effort for the main manager. Form: model-name:effort.",
    "fast_lane_deputy": "Model and effort for the fast-lane deputy. Form: model-name:effort.",
    "merge_deputy": "Model and effort for the merge deputy. Form: model-name:effort.",
    "task_manager": "Model and effort for a task manager. Form: model-name:effort.",
    "worker": "Model and effort for a worker. Form: model-name:effort.",
    "permission_mode": "How much an agent may do without asking. One of: default, acceptEdits, auto, plan.",
    "auto_resume": "Run agent-resume.sh by itself when a main manager starts. yes or no.",
    "language": "Language for talking to the human, e.g. en, zh, ms. Code and rules stay English.",
    "runtime": "How this machine runs agents. One of: auto, orca, plain, cloud.",
    "city_port": "Port the agent city listens on, on 127.0.0.1 only. Whole number, 1024 to 65535.",
    "city_idle_min": "Minutes the agent city keeps running with no browser open, then it stops by itself. Whole number, 1 to 240.",
    "city_governor_wait_sec": "Seconds the governor has to answer an agent's question before the owner gets it in the city page. Whole number, 5 to 3600.",
}

GROUPS = [
    ("limits", ["max_usage_percent", "heavy_test_slots", "max_agents",
                "monitor_interval_min", "stall_min"]),
    ("roles", list(ROLE_KEYS)),
    ("permission", ["permission_mode", "auto_resume", "language"]),
    ("runtime", ["runtime"]),
    ("city", ["city_port", "city_idle_min", "city_governor_wait_sec"]),
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


def _validate_permission_mode(value):
    if value not in PERMISSION_MODES:
        return "Must be one of: default, acceptEdits, auto, plan."
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


def validate_value(key, value):
    if key in NUMBER_BOUNDS:
        return _validate_number(key, value)
    if key in ROLE_KEYS:
        return _validate_role(value)
    if key == "permission_mode":
        return _validate_permission_mode(value)
    if key == "auto_resume":
        return _validate_yes_no(value)
    if key == "language":
        return _validate_language(value)
    if key == "runtime":
        return _validate_runtime(value)
    return None


def validate(conf):
    errors = {}
    for key, value in conf.items():
        message = validate_value(key, value)
        if message:
            errors[key] = message
    return errors
