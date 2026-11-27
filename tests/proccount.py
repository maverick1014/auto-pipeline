"""Count the processes a script call starts (script-speed, requirements/script-speed.md).

Counted, never timed, so a test on a busy machine never flakes. Every command
name in COUNTED gets a small wrapper first on the run's PATH (the ScriptRepo's
stub folder): it writes one line to the log, then execs the program the name
would have found without it. The orca and claude stubs are wrapped the same
way. A program started by its absolute path is not seen (the scripts start
everything by name; the review checks new code does too).

    log = count_starts(repo)        # once, after the repo's own stubs are set
    starts = read_starts(log)       # [(name, [args...]), ...] in start order
    reset_starts(log)               # before the call you want to count

One log line: the name, then each argument, tab separated, a newline inside an
argument written as \\n. A start made by a test stub (orca, claude) is the stub's,
not the script's: it is not counted.
"""

import os
import shutil

# Every external command the start, file and resume scripts (and the Python they
# run) use today, plus the usual ones a rewrite could reach for.
COUNTED = (
    "python3", "python", "git", "bash", "sh", "zsh", "orca", "claude",
    "ps", "pgrep", "pkill", "kill", "lsof", "sysctl", "vm_stat", "top", "memory_pressure", "uptime",
    "shasum", "sha256sum", "md5", "md5sum", "base64", "od", "xxd",
    "awk", "sed", "grep", "egrep", "cut", "tr", "head", "tail", "wc", "sort", "uniq", "comm", "paste",
    "tee", "xargs", "find", "ls", "cat", "printf", "echo", "test", "expr", "seq", "rev", "fold", "column",
    "date", "sleep", "timeout", "gtimeout", "nohup", "env", "id", "whoami", "hostname", "uname", "scutil",
    "basename", "dirname", "readlink", "realpath", "stat", "touch", "mkdir", "rmdir", "rm", "mv", "cp", "ln",
    "chmod", "mktemp", "flock", "jq", "perl", "ruby", "node", "osascript", "open", "pbcopy",
    "nproc", "getconf", "sw_vers", "defaults", "curl", "tput", "stty", "script",
)

# The test stubs: their own starts (a cat, a git inside the orca stub) are not the script's.
STUBS = ("orca", "claude")

WRAPPER = r"""#!/bin/bash
[ -n "${PROCCOUNT_OFF:-}" ] && exec %(real)s "$@"
line=%(name)s
for a in "$@"; do a=${a//$'\n'/\\n}; line="$line"$'\t'"$a"; done
printf '%%s\n' "$line" >> %(log)s
%(off)sexec %(real)s "$@"
"""


def _quote(text):
    return "'" + text.replace("'", "'\"'\"'") + "'"


def count_starts(repo, log=None):
    """Wrap every COUNTED name on repo's run PATH. Returns the log path."""
    log = log or os.path.join(repo.base, "proc_starts.log")
    path = repo._path()
    for name in COUNTED:
        stub = os.path.join(repo.bin, name)
        if os.path.exists(stub):
            # one of the repo's own stubs (orca, claude, a stub_tool): keep it under a new name
            real = os.path.join(repo.bin, "_counted_" + name)
            os.rename(stub, real)
        else:
            rest = os.pathsep.join(p for p in path.split(os.pathsep) if p != repo.bin)
            real = shutil.which(name, path=rest)
            if not real:
                continue
        with open(stub, "w") as fh:
            fh.write(WRAPPER % {"name": name, "log": _quote(log), "real": _quote(real),
                                "off": "export PROCCOUNT_OFF=1; " if name in STUBS else ""})
        os.chmod(stub, 0o755)
    open(log, "w").close()
    return log


def reset_starts(log):
    open(log, "w").close()


def read_starts(log):
    with open(log) as fh:
        rows = [line.rstrip("\n").split("\t") for line in fh if line.strip()]
    return [(row[0], row[1:]) for row in rows]


def names(starts, name):
    return [args for n, args in starts if n == name]


def repeated(starts, name="git"):
    """The argument lists of `name` that were started more than once (asked twice for one value)."""
    seen, twice = set(), []
    for args in names(starts, name):
        key = tuple(args)
        if key in seen and list(key) not in twice:
            twice.append(list(key))
        seen.add(key)
    return twice


def summary(starts):
    """A short text for a failure message: the count per name, then every python3 and git start."""
    counts = {}
    for n, _ in starts:
        counts[n] = counts.get(n, 0) + 1
    head = ", ".join("%s %d" % kv for kv in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    lines = ["%d starts: %s" % (len(starts), head)]
    for n, args in starts:
        if n in ("python3", "git", "shasum", "sha256sum"):
            lines.append("  %s %s" % (n, " ".join(a[:60] for a in args)[:200]))
    return "\n".join(lines)
