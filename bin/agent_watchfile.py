#!/usr/bin/env python3
"""agent_watchfile.py - read the watch status file and the watch targets (requirements/one-watcher.md A1, B18, F1-F7).
Python 3.9, standard library only. Read only: it writes nothing and never calls orca.

    status file   <git common dir of the main repo>/agent_watch.json, written by `agent-watch.sh --all`
    live          the pid answers kill -0 (a PermissionError counts as alive) and the last sweep is at most
                  2 x interval_min + 2 minutes before now
    targets       A1: every agent_worktree.txt line with status working or final (name = field 2, path = field 1;
                  the human-direct line is never one), plus every todo line with an "on <machine> <path>" field and
                  no worktree line of that name

    agent_watchfile.py start-line <main repo> <plugin root>
        prints the F1/F2 line (WATCH: running ... / WATCH: not running ...) or nothing; the caller checks the
        runtime kind (only orca prints it)
"""

import datetime
import json
import os
import re
import subprocess
import sys

FMT = "%Y-%m-%d %H:%M"
HELPER_ROLE = "task manager, human-direct"
STATUS_NAME = "agent_watch.json"
DEFAULT_INTERVAL_MIN = 5


def parse_time(text):
    try:
        return datetime.datetime.strptime(str(text).strip(), FMT)
    except (ValueError, TypeError):
        return None


def clock_now():
    """AGENT_FAKE_NOW when set (tests), else the machine clock."""
    return parse_time(os.environ.get("AGENT_FAKE_NOW", "")) or datetime.datetime.now()


def read_lines(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return []


def git_common_dir(root):
    """The git common dir of the main repo; "" when it cannot be found."""
    dot = os.path.join(root, ".git")
    if os.path.isdir(dot):
        return dot
    try:
        out = subprocess.run(["git", "-C", root, "rev-parse", "--git-common-dir"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, universal_newlines=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    path = out.stdout.strip() if out.returncode == 0 else ""
    if not path:
        return ""
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(root, path))


def status_path(root):
    gd = git_common_dir(root)
    return os.path.join(gd, STATUS_NAME) if gd else ""


def read_status(root):
    """The status file as a dict; None when it is missing, broken or not an object."""
    path = status_path(root)
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def tasks_of(status):
    tasks = status.get("tasks") if isinstance(status, dict) else None
    return tasks if isinstance(tasks, dict) else {}


def pid_alive(pid):
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def live(status, now=None):
    """True when the status file's pid is alive and its last sweep is at most 2 x interval + 2 minutes old."""
    if not isinstance(status, dict) or not pid_alive(status.get("pid")):
        return False
    sweep = parse_time(status.get("sweep"))
    if sweep is None:
        return False
    interval = status.get("interval_min")
    if isinstance(interval, bool) or not isinstance(interval, (int, float)) or interval <= 0:
        interval = DEFAULT_INTERVAL_MIN
    now = now or clock_now()
    return (now - sweep).total_seconds() / 60.0 <= 2 * interval + 2


def todo_on(line):
    """(machine, path) of the first "on <machine> <path>" field of a todo line, else None."""
    fields = line.split(" | ")
    for field in fields[3:]:
        m = re.match(r"on (\S+)(?: (.*))?$", field)
        if m:
            return m.group(1), (m.group(2) or "").strip()
    return None


def targets(root):
    """A1: [{"name", "path"}] in order: worktree lines first, then todo lines with an on field."""
    out, seen, names = [], set(), set()
    for line in read_lines(os.path.join(root, "agent_worktree.txt")):
        f = line.split(" | ")
        if len(f) < 2 or not f[1].strip():
            continue
        names.add(f[1].strip())
        if f[1].strip() == HELPER_ROLE:
            continue
        if len(f) > 2 and f[2].strip() in ("working", "final") and f[1].strip() not in seen:
            seen.add(f[1].strip())
            out.append({"name": f[1].strip(), "path": f[0].strip()})
    for line in read_lines(os.path.join(root, "agent_todo.txt")):
        name = line.split(" | ")[0].strip()
        if not name or name in names or name in seen:
            continue
        on = todo_on(line)
        if on and on[1]:
            seen.add(name)
            out.append({"name": name, "path": on[1]})
    return out


def conf_value(root, key):
    value = ""
    for line in read_lines(os.path.join(root, "agent.conf")):
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            if k.strip() == key:
                value = v.strip()
    return value


def no_watch_runtime(root):
    """True when the runtime is plain or cloud by AGENT_RUNTIME, agent.conf runtime or CLAUDE_CODE_REMOTE (no watch
    runs there). The orca probe is never made here."""
    env = os.environ.get("AGENT_RUNTIME", "")
    if env in ("orca", "plain", "cloud"):
        return env != "orca"
    value = conf_value(root, "runtime")
    if value in ("orca", "plain", "cloud"):
        return value != "orca"
    return os.environ.get("CLAUDE_CODE_REMOTE", "") == "true"


def start_line(root, plugin_root, now=None):
    status = read_status(root)
    if live(status, now):
        sweep = parse_time(status.get("sweep"))
        return "WATCH: running (pid %d), %d tasks, last sweep %s" % (status["pid"], len(tasks_of(status)),
                                                                     sweep.strftime("%H:%M"))
    found = targets(root)
    if not found:
        return ""
    return ("WATCH: not running, %d tasks to watch (%s). Start it now with Bash run_in_background, timeout 7200000: "
            "%s/bin/agent-watch.sh --all" % (len(found), ", ".join(t["name"] for t in found),
                                             plugin_root.rstrip("/")))


def main(argv):
    if len(argv) == 3 and argv[0] == "start-line":
        try:
            line = start_line(argv[1], argv[2])
        except Exception:
            line = ""
        if line:
            print(line)
        return 0
    sys.stderr.write("usage: agent_watchfile.py start-line <main repo> <plugin root>\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
