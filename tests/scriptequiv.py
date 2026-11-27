"""Old and new script, same state, same result (script-speed rule 2, requirements/script-speed.md).

Off unless AGENT_EQUIV_OLD names a git ref (a commit before the change). Then every ScriptRepo.run
call of a test runs twice:

    1. the test's whole temp folder is copied aside (the snapshot)
    2. the plugin copy's bin/ files the test did not change are swapped for the old ref's, and the
       call runs: the OLD result (exit code, stdout, stderr, every file in the temp folder)
    3. the temp folder is put back from the snapshot, at the same path
    4. the call runs as usual with the new bin/: the NEW result, the one the test then checks

Old and new are compared after normalising only what may differ between two runs of the same
script: commit hashes (7-40 hex digits), clock times, temp names. A difference is one JSON line in
AGENT_EQUIV_LOG (when set) and fails that test, naming the call.

So the record set is the calls the tests really make: every verb, flag and exit code they use, each
on the very state its test built. Only in a proof run (it doubles every script call), never in the
normal suite:

    AGENT_EQUIV_OLD=78b565f AGENT_EQUIV_LOG=/tmp/equiv.jsonl python3 tests/run2.py tests/test_agent_start.py ...

AGENT_EQUIV_SCRIPTS (comma list of script names) limits the calls compared; unset: every script
started from the plugin's bin/. AGENT_EQUIV_SETTLE=<seconds> waits that long after each run before its
files are read (background jobs the script started); unset: read at once.
"""

import atexit
import difflib
import filecmp
import hashlib
import inspect
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest

OLD = os.environ.get("AGENT_EQUIV_OLD", "")
LOG = os.environ.get("AGENT_EQUIV_LOG", "")
ONLY = [s for s in os.environ.get("AGENT_EQUIV_SCRIPTS", "").split(",") if s]
# seconds to wait after each run before its files are read, so a job the script started in the
# background (nohup: nightly start, pane measure, the autoclear waiter, the estimate runner) is done
# in both runs; 0 (unset) = read at once
try:
    SETTLE = float(os.environ.get("AGENT_EQUIV_SETTLE") or 0)
except ValueError:
    SETTLE = 0.0

_STATE = {"bin": None}

# Files that differ between two runs of the very same script: inside a git dir the objects, the
# reflogs and the index (they hold times and stat data; the refs are compared), anywhere bytecode
# and the process-count log. Never compared.
GIT_SKIP_DIRS = {"objects", "logs"}
GIT_SKIP_FILES = {"index", "ORIG_HEAD", "FETCH_HEAD", "COMMIT_EDITMSG"}
SKIP_FILES = {"proc_starts.log"}
# Written by the detached estimate runner (agent-file.sh estimate-runner, started in the background by
# todo done): a background process of the old run may still write after the snapshot is put back.
SKIP_DIRS_ANY = {"agent_estimate.lock", "agent_estimate.queue"}
SKIP_FILES_ANY_GIT = {"agent_estimate.log"}

EPOCH = re.compile(r"\b1[6-9]\d{8}(\.\d+)?\b")          # a time.time() value
PIDKEY = re.compile(r'("key": "[a-z-]+)-\d+-(\d+")')        # a reservation key: <what>-<pid>-<n>
PANEMB = re.compile(r'("pane_recent": \[)[\d, ]*(\])')        # the measured MB of a live pane
STAMP = re.compile(r"\b\d{4}-\d\d-\d\d-\d{6}\b|\b\d{8}-\d{6}\b")   # archive / kept-copy names: <date>-<hhmmss>
WATCHPID = re.compile(r"(\(pid |\"pid\": |'pid': )\d+")       # a process's own pid (watch start line, status and job files)
WEIGHT = re.compile(r"\b(\d+ s )\d+( MB)")                      # a measured weight: "<seconds> s <peak> MB"
RAN = re.compile(r"\bRan (\d+) tests? in [\d.]+s\b")            # a unittest summary line of a run the script made
QUEUE = re.compile(r"<epoch>-\d+-\d+")                        # a queue file name: <epoch>-<pid>-<random>
HEX = re.compile(r"\b[0-9a-f]{7,40}\b")
CLOCK = re.compile(r"\b\d\d:\d\d(:\d\d)?\b")
TMPNAME = re.compile(r"(tmp|\.tmp)[._][A-Za-z0-9]{4,}|\.tmp\.\d+")


def on():
    return bool(OLD)


def old_bin(root):
    """The old ref's bin/, extracted once per test process."""
    if _STATE["bin"] is None:
        folder = tempfile.mkdtemp(prefix="agent_equiv_old_")
        atexit.register(shutil.rmtree, folder, True)
        arch = subprocess.run(["git", "-C", root, "archive", OLD, "bin"], capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", folder], input=arch, check=True, capture_output=True)
        _STATE["bin"] = os.path.join(folder, "bin")
    return _STATE["bin"]


def wanted(repo, argv):
    script = argv[0]
    if os.path.dirname(script) != repo.plugin_bin:
        return False
    return not ONLY or os.path.basename(script) in ONLY


def swap_to_old(repo, new_bin, old):
    """Every plugin bin/ file the test left as the repo has it becomes the old ref's (or goes, when the
    old ref has none); a file the change removed comes back from the old ref."""
    have = set(os.listdir(repo.plugin_bin))
    for name in have:
        cur = os.path.join(repo.plugin_bin, name)
        new_src = os.path.join(new_bin, name)
        if not (os.path.isfile(cur) and os.path.isfile(new_src) and filecmp.cmp(cur, new_src, shallow=False)):
            continue   # the test's own file, or one it changed: both runs get it
        old_src = os.path.join(old, name)
        if os.path.isfile(old_src):
            shutil.copy2(old_src, cur)
        else:
            os.remove(cur)
    from scripthelp import COPY_BIN
    for name in COPY_BIN:
        if name not in have and not os.path.exists(os.path.join(new_bin, name)) \
                and os.path.isfile(os.path.join(old, name)):
            shutil.copy2(os.path.join(old, name), os.path.join(repo.plugin_bin, name))


def norm(text, base):
    text = text.replace(base, "<BASE>")
    text = STAMP.sub("<stamp>", text)
    text = WATCHPID.sub(r"\1<pid>", text)
    text = WEIGHT.sub(r"\1<mb>\2", text)
    text = RAN.sub(r"Ran \1 tests in <s>", text)
    text = EPOCH.sub("<epoch>", text)
    text = QUEUE.sub("<queue>", text)
    text = PIDKEY.sub(r"\1-<pid>-\2", text)
    text = PANEMB.sub(r"\1<mb>\2", text)
    text = HEX.sub("<sha>", text)
    text = CLOCK.sub("<hh:mm>", text)
    return TMPNAME.sub("<tmp>", text)


def tree(repo):
    """normalised relative path -> normalised content (text) or a sha256 (binary), for every file of
    the temp folder except the plugin's bin/ (it was swapped) and SKIP_*. Files whose names normalise
    to one name (queue files) are joined, sorted."""
    out = {}
    base = repo.base
    for top, dirs, files in os.walk(base):
        rel_top = os.path.relpath(top, base)
        gitdir = os.path.isfile(os.path.join(top, "HEAD")) and (os.path.isdir(os.path.join(top, "refs"))
                                                              or os.path.isfile(os.path.join(top, "commondir")))
        dirs[:] = sorted(d for d in dirs if d != "__pycache__" and d not in SKIP_DIRS_ANY
                         and not (gitdir and d in GIT_SKIP_DIRS)
                         and os.path.normpath(os.path.join(rel_top, d)) != os.path.join("plugin", "bin"))
        for f in files:
            if f in SKIP_FILES or f.endswith(".pyc") or (gitdir and (f in GIT_SKIP_FILES or f in SKIP_FILES_ANY_GIT)):
                continue
            full = os.path.join(top, f)
            rel = os.path.normpath(os.path.join(rel_top, f))
            key = norm(rel, base)
            if os.path.islink(full):
                out.setdefault(key, []).append("-> " + norm(os.readlink(full), base))
                continue
            try:
                with open(full, "rb") as fh:
                    data = fh.read()
            except OSError as exc:
                out.setdefault(key, []).append("unreadable: %s" % exc.__class__.__name__)
                continue
            try:
                out.setdefault(key, []).append(norm(data.decode("utf-8"), base))
            except UnicodeDecodeError:
                out.setdefault(key, []).append("sha256 " + hashlib.sha256(data).hexdigest())
    return {k: "\n<next file>\n".join(sorted(v)) for k, v in out.items()}


def _procs_under(base):
    """pids whose command line names the test's temp folder (a background job a script started there)."""
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,args="], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    me = os.getpid()
    found = set()
    for line in out.splitlines():
        pid, _, args = line.strip().partition(" ")
        if pid.isdigit() and int(pid) != me and base in args:
            found.add(int(pid))
    return found


def _stop(pids):
    import signal
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def run_old(repo, argv, cwd, env, stdin, timeout, new_bin, root):
    """Steps 1-3. Returns the old (returncode, stdout, stderr, tree), or None for a call not compared."""
    if not wanted(repo, argv):
        return None
    snap = repo.base + ".equiv-snap"
    shutil.rmtree(snap, ignore_errors=True)
    shutil.copytree(repo.base, snap, symlinks=True)
    _STATE["new"] = new_bin
    try:
        swap_to_old(repo, new_bin, old_bin(root))
        before = _procs_under(repo.base)
        try:
            r = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                               input=stdin if stdin is not None else "", timeout=timeout)
            if SETTLE:
                time.sleep(SETTLE)
            old = (r.returncode, r.stdout, r.stderr, tree(repo))
        except subprocess.TimeoutExpired:
            old = ("timeout", "", "", {})
        # the old run's background jobs (a city server, a nightly, a waiter) end here: they would hold a
        # port or write into the folder the new run gets
        _stop(_procs_under(repo.base) - before)
    finally:
        shutil.rmtree(repo.base, ignore_errors=True)
        os.rename(snap, repo.base)
    return old


_BIN_TEXT = {}


def _bin_text(folder, name, base):
    key = (folder, name, base)
    if key not in _BIN_TEXT:
        full = os.path.join(folder, name)
        try:
            with open(full, "rb") as fh:
                _BIN_TEXT[key] = norm(fh.read().decode("utf-8"), base)
        except (OSError, UnicodeDecodeError):
            _BIN_TEXT[key] = None
    return _BIN_TEXT[key]


def own_copy(rel, a, b, base):
    """A copy of one of the plugin's own bin/ files that the script (or a test stub it starts) made
    inside the temp folder, e.g. a fake plugin cache: the old run copies the old file, the new run the
    new one. Equal when old = the old ref's file and new = the new file of that name."""
    name = os.path.basename(rel)
    if a is None or b is None or _STATE["bin"] is None or _STATE.get("new") is None:
        return False
    return a == _bin_text(_STATE["bin"], name, base) and b == _bin_text(_STATE["new"], name, base)


def test_id():
    for frame in inspect.stack():
        obj = frame.frame.f_locals.get("self")
        if isinstance(obj, unittest.TestCase):
            return obj.id()
    return "?"


def compare(repo, argv, old, new):
    """Step 4's check: a difference is logged and fails the test."""
    base = repo.base
    o_rc, o_out, o_err, o_tree = old
    if SETTLE:
        time.sleep(SETTLE)
    n_tree = tree(repo)
    diffs = []
    if o_rc != new.returncode:
        diffs.append(("exit", str(o_rc), str(new.returncode)))
    for name, a, b in (("stdout", o_out, new.stdout), ("stderr", o_err, new.stderr)):
        a, b = norm(a, base), norm(b, base)
        if a != b:
            diffs.append((name, a, b))
    for rel in sorted(set(o_tree) | set(n_tree)):
        a, b = o_tree.get(rel), n_tree.get(rel)
        if a != b and not own_copy(rel, a, b, base):
            diffs.append(("file " + rel, a if a is not None else "<missing>", b if b is not None else "<missing>"))
    if not diffs:
        return
    call = [os.path.basename(argv[0])] + argv[1:]
    tid = test_id()
    if LOG:
        with open(LOG, "a") as fh:
            for what, a, b in diffs:
                fh.write(json.dumps({"test": tid, "call": call, "what": what, "old": a, "new": b}) + "\n")
    text = []
    for what, a, b in diffs[:5]:
        text.append("--- %s (old) / +++ new" % what)
        text.extend(list(difflib.unified_diff(str(a).splitlines(), str(b).splitlines(), lineterm="", n=1))[2:40])
    raise AssertionError("EQUIV %s: old and new differ in %s\n%s"
                         % (" ".join(call)[:200], ", ".join(d[0] for d in diffs[:10]), "\n".join(text)))
