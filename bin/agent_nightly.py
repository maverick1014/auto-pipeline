#!/usr/bin/env python3
"""agent_nightly.py: the nightly run, selection misses, the memory gate and the monitored test run
(requirements/check-blocks.md sections 15, 17, 24, 25). Called by agent-nightly.sh, agent-test-run.sh, agent-room.sh.

Files in the git common dir: agent_nightly.json, agent_selection_misses.txt, agent_test_weights.json (measured
weights, per machine), agent_nightly_wt (the nightly's scratch worktree). The reservation list is one file per
machine ($AGENT_RESERVE_FILE). Test hooks: AGENT_FAKE_NOW ("YYYY-MM-DD HH:MM"), AGENT_FAKE_RAM, AGENT_FAKE_RAM_FILE,
AGENT_FAKE_RAM_TOTAL_MB, AGENT_FAKE_CPU, AGENT_FAKE_CORES, AGENT_FAKE_HOST, AGENT_TEST_RUN_WAIT_S.
"""

import base64
import datetime
import fcntl
import json
import math
import os
import re
import resource
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agent_conf  # noqa: E402

FMT = "%Y-%m-%d %H:%M"
STATUS = "agent_nightly.json"
MISSES = "agent_selection_misses.txt"
WEIGHTS = "agent_test_weights.json"
SCRATCH = "agent_nightly_wt"


# ------------------------------------------------------------------ small helpers

def now():
    try:
        return datetime.datetime.strptime(os.environ.get("AGENT_FAKE_NOW", "").strip(), FMT)
    except ValueError:
        return datetime.datetime.now()


def parse(text):
    try:
        return datetime.datetime.strptime(str(text).strip(), FMT)
    except (ValueError, TypeError):
        return None


def git(cwd, *args, timeout=60):
    try:
        res = subprocess.run(["git", "-C", cwd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             universal_newlines=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return res.stdout.strip() if res.returncode == 0 else ""


def main_root(cwd):
    for line in git(cwd, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            return line[len("worktree "):]
    return git(cwd, "rev-parse", "--show-toplevel") or cwd


def common_dir(cwd):
    return git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir") or os.path.join(cwd, ".git")


def number(key, default):
    try:
        return int(float(agent_conf.get(key)))
    except Exception:
        return default


def pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def ram_used():
    """Percent of RAM in use, -1 when unknown. AGENT_FAKE_RAM_FILE (tests only) is re-read on every sample."""
    fake = os.environ.get("AGENT_FAKE_RAM", "")
    path = os.environ.get("AGENT_FAKE_RAM_FILE", "")
    if path:
        try:
            with open(path) as fh:
                fake = fh.read().strip() or fake
        except OSError:
            pass
    if fake:
        try:
            return int(float(fake))
        except ValueError:
            return -1
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["memory_pressure"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 universal_newlines=True, timeout=20).stdout
            m = re.search(r"free percentage:\s*(\d+)", out)
            return 100 - int(m.group(1)) if m else -1
        total = avail = 0
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable"):
                    avail = int(line.split()[1])
        return (total - avail) * 100 // total if total else -1
    except Exception:
        return -1


def atomic_write(path, text):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


# ------------------------------------------------------------------ memory gate and reservation list (C23, C24, C27)


def reserve_path():
    return os.environ.get("AGENT_RESERVE_FILE") or os.path.join(os.path.expanduser("~"), ".claude",
                                                                "auto-pipeline-reservations.json")


class locked:
    """Exclusive lock on a file next to the reservation list, for every read-modify-write.
    blocking=False (a signal handler, C10): a few non-blocking tries; .ok is False when the lock was not got."""

    def __init__(self, blocking=True):
        self.blocking, self.ok, self.fh = blocking, True, None

    def __enter__(self):
        path = reserve_path() + ".lock"
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self.fh = open(path, "a")
            if self.blocking:
                fcntl.flock(self.fh, fcntl.LOCK_EX)
            else:
                for _ in range(20):
                    try:
                        fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        time.sleep(0.05)
                else:
                    self.ok = False
                    self.fh.close()
                    self.fh = None
        except (OSError, ImportError):
            self.fh = None
        return self

    def __exit__(self, *exc):
        if self.fh:
            try:
                fcntl.flock(self.fh, fcntl.LOCK_UN)
                self.fh.close()
            except OSError:
                pass
        return False


PANE_FLOOR_MB = 550            # the stored pane weight is never below what a pane needs while unmeasured (H7)
UNVERIFIED_HOLD_S = 6 * 3600   # an entry whose start time is unknown or empty expires after 6 hours (C27)
PANE_HOLD_S = 15 * 60       # a pane reserved at launch is dropped after 15 minutes when it never measured itself (C7)


def proc_start(pid):
    """The process start time (`ps -o lstart=`), "" when the pid is gone."""
    try:
        env = dict(os.environ, LC_ALL="C", LANG="C", TZ="UTC")
        return subprocess.run(["ps", "-o", "lstart=", "-p", str(int(pid))], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, universal_newlines=True, timeout=10,
                              env=env).stdout.strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""


def move_aside(path):
    """A reservation file that is not valid JSON is moved aside, never overwritten silently (C10)."""
    target = "%s.corrupt-%s" % (path, time.strftime("%Y%m%d-%H%M%S"))
    n = 1
    while os.path.exists(target):
        n += 1
        target = "%s.corrupt-%s-%d" % (path, time.strftime("%Y%m%d-%H%M%S"), n)
    try:
        os.replace(path, target)
    except OSError:
        return
    sys.stderr.write("RESERVATIONS: %s could not be read; moved to %s\n" % (path, target))
    sys.stderr.flush()


def still_live(j):
    """A reservation is live while its pid runs with the start time stored with it (a reused pid is not it);
    a handle entry (a pane reserved at launch, no pid yet) lives 15 minutes."""
    if not j.get("pid") and (j.get("handle") or j.get("key")):
        return time.time() - float(j.get("started", 0) or 0) < PANE_HOLD_S
    if not pid_alive(j.get("pid")):
        return False
    stored = j.get("start")
    if not stored:                                       # it cannot be verified: expires after 6 hours (C27)
        if not j.get("started"):
            return True                                  # no time to count from: kept
        return time.time() - float(j["started"]) < UNVERIFIED_HOLD_S
    now_start = proc_start(j["pid"])
    return not now_start or now_start == stored          # unknown ("") is never pruned


def load_jobs():
    """Live entries only (a dead pid, a reused pid or an old handle is dropped); the caller holds the lock when it
    writes back."""
    path = reserve_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
    except ValueError:
        move_aside(path)
        return [], False
    except OSError:
        return [], False
    live = [j for j in jobs if isinstance(j, dict) and still_live(j)]
    return live, len(live) != len(jobs)


def save_jobs(jobs):
    path = reserve_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    atomic_write(path, json.dumps({"jobs": jobs}, indent=1) + "\n")


def live_jobs():
    """Every live reservation; dead pids are dropped from the file on every read."""
    with locked():
        jobs, changed = load_jobs()
        if changed:
            try:
                save_jobs(jobs)
            except OSError:
                pass
    return jobs


def total_mb():
    fake = os.environ.get("AGENT_FAKE_RAM_TOTAL_MB", "")
    if fake:
        try:
            return int(float(fake))
        except ValueError:
            return 0
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 universal_newlines=True, timeout=10).stdout
            return int(out.strip()) // 1048576
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 0


def limit_pct():
    return number("max_usage_percent", 80)


def machine():
    """(total MB, used MB, limit MB); used is -1 when RAM cannot be read."""
    total, pct = total_mb(), ram_used()
    if total <= 0 or pct < 0:
        return total, -1, 0
    return total, total * pct // 100, total * limit_pct() // 100


def repo_name():
    """The repo's identity in a reservation: the main root path (the parent of the git common dir), so a run
    started in a task worktree is this repo's and another repo with the same folder name is not (C15)."""
    cwd = os.getcwd()
    gitdir = git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    root = os.path.dirname(gitdir.rstrip("/")) if gitdir else (git(cwd, "rev-parse", "--show-toplevel") or cwd)
    return os.path.realpath(root)


def same_repo(stored):
    try:
        return os.path.realpath(str(stored)) == repo_name()
    except (OSError, ValueError):
        return False


def entry(pid, mb, what, kind, measured, by="runner"):
    """One reservation. by: "runner" (agent-test-run.sh, the nightly: relief may stop it) or "hand" (never stopped);
    start: the process start time, so a reused pid is never taken for it (C1)."""
    return {"pid": int(pid), "mb": int(mb), "what": what, "repo": repo_name(), "since": now().strftime(FMT),
            "started": time.time(), "kind": kind, "measured": bool(measured), "by": by,
            "start": proc_start(pid)}


def trees_mb(jobs):
    """The memory (MB) the reserved jobs' process trees hold now: counted by their reservation instead (C6)."""
    kb = 0
    for j in jobs:
        if j.get("pid"):
            kb += tree_kb(j["pid"])
    return kb // 1024


def room(need, reserve_as=None):
    """(ok, line). need is MB (0 for unknown). With reserve_as = an entry, it is stored in the same locked step,
    so two agents never count the same free memory. Fails closed when RAM or the total cannot be read."""
    with locked():
        jobs, _ = load_jobs()
        me = reserve_as.get("pid") if reserve_as else None
        handle = reserve_as.get("handle") if reserve_as else None
        key = reserve_as.get("key") if reserve_as else None
        if key and any(j.get("key") == key for j in jobs):      # H8: a pending key that exists is refused
            return False, "reserve-pane: the key %s already exists; nothing replaced" % key
        others = [j for j in jobs if not ((me is not None and j.get("pid") == me)
                                          or (handle and j.get("handle") == handle)
                                          or (key and j.get("key") == key))]
        total, used, limit = machine()
        if used < 0:
            return False, "ROOM: no: RAM unknown"
        reserved = sum(int(j.get("mb", 0) or 0) for j in others)
        used = max(0, used - trees_mb(others))
        if used + reserved + need > limit:
            return False, "ROOM: no: %d MB in use + %d MB reserved + %d MB > %d MB" % (used, reserved, need, limit)
        if reserve_as:
            try:
                save_jobs(others + [reserve_as])
            except OSError:
                pass
    return True, "ROOM: ok"


def wait_room(need, reserve_as=None, announce=None):
    """(ok, line): wait for room, capped by AGENT_TEST_RUN_WAIT_S."""
    try:
        cap = float(os.environ.get("AGENT_TEST_RUN_WAIT_S", "3600"))
    except ValueError:
        cap = 3600.0
    end = time.time() + cap
    said = False
    while True:
        ok, line = room(need, reserve_as)
        if ok:
            return True, line
        if time.time() >= end:
            return False, line
        if not said and announce:
            announce("waiting: " + line)
            said = True
        time.sleep(max(0.1, min(1.0, end - time.time())))


def update_reservation(pid, **fields):
    with locked():
        jobs, _ = load_jobs()
        for j in jobs:
            if j.get("pid") == pid:
                j.update(fields)
        try:
            save_jobs(jobs)
        except OSError:
            pass


def drop_reservation(pid, blocking=True):
    """Drop a reservation. A signal handler passes blocking=False: no second blocking lock there (C10); when the
    lock is busy the stale entry is pruned later (its pid is gone)."""
    with locked(blocking) as lk:
        if not lk.ok:
            return
        jobs, _ = load_jobs()
        try:
            save_jobs([j for j in jobs if j.get("pid") != pid])
        except OSError:
            pass


def pick_of(jobs):
    """The job the monitor stops first: the newest unmeasured live test or build run, else the newest."""
    cands = [j for j in jobs if j.get("kind", "test") in ("test", "build") and j.get("by") == "runner"]
    if not cands:
        return None
    unmeasured = [j for j in cands if not j.get("measured", True)]
    return max(unmeasured or cands, key=lambda j: j.get("started", 0))


def host():
    return os.environ.get("AGENT_FAKE_HOST") or socket.gethostname().split(".")[0]


def pane_need(gitdir):
    got = parse_weight(read_weights(gitdir).get("pane", ""))
    return got[1] if got else 550


def room_main(argv, cwd):
    cmd = argv[0] if argv else ""
    if cmd == "check" and len(argv) == 2:
        if argv[1] == "unknown":
            need = 0
        else:
            try:
                need = int(float(argv[1]))
            except ValueError:
                sys.stderr.write("agent-room.sh check <mb>|unknown\n")
                return 2
        ok, line = room(need)
        print(line)
        return 0 if ok else 1
    if cmd == "reserve" and len(argv) >= 4:
        kind, measured, rest = "test", True, argv[1:]
        pos = []
        i = 0
        while i < len(rest):
            if rest[i] == "--kind" and i + 1 < len(rest):
                kind = rest[i + 1]
                i += 2
            elif rest[i] == "--unmeasured":
                measured = False
                i += 1
            else:
                pos.append(rest[i])
                i += 1
        if len(pos) < 3 or kind not in ("test", "build", "pane"):
            sys.stderr.write('agent-room.sh reserve <pid> <mb> "<what>" [--kind test|build|pane] [--unmeasured]\n')
            return 2
        try:
            new = entry(pos[0], pos[1], pos[2], kind, measured, by="hand")
        except ValueError:
            sys.stderr.write("agent-room.sh reserve: pid and mb are numbers\n")
            return 2
        with locked():
            jobs, _ = load_jobs()
            save_jobs([j for j in jobs if j.get("pid") != new["pid"]] + [new])
        return 0
    if cmd == "reserve-pane" and len(argv) == 4 and argv[1] == "--name":
        # the pending reservation takes the new handle (no check, C24)
        key, handle = argv[2], argv[3]
        with locked():
            jobs, _ = load_jobs()
            found = [j for j in jobs if j.get("key") == key]
            rest = [j for j in jobs if j.get("key") != key and j.get("handle") != handle]
            if found:
                new = dict(found[0])
                new.pop("key", None)
            else:
                new = {"mb": pane_need(common_dir(cwd)), "repo": repo_name(), "since": now().strftime(FMT),
                       "kind": "pane", "measured": False, "by": "launch"}
            new.update({"handle": handle, "what": "pane " + handle, "started": time.time()})
            save_jobs(rest + [new])
        return 0
    if cmd == "reserve-pane" and len(argv) in (3, 4):
        pending = len(argv) == 4 and argv[1] == "--pending"
        if len(argv) == 4 and not pending:
            sys.stderr.write("agent-room.sh reserve-pane <handle> <mb> | --pending <key> <mb> | --name <key> <handle>\n")
            return 2
        ident, size = (argv[2], argv[3]) if pending else (argv[1], argv[2])
        try:
            mb = int(float(size))
        except ValueError:
            sys.stderr.write("agent-room.sh reserve-pane <handle> <mb>\n")
            return 2
        new = {"mb": mb, "what": "pane being created" if pending else "pane " + ident, "repo": repo_name(),
               "since": now().strftime(FMT), "started": time.time(), "kind": "pane", "measured": False,
               "by": "launch", ("key" if pending else "handle"): ident}
        ok, line = room(mb, new)               # the check and the reservation in one locked step
        if not ok:
            print(line)
            return 1
        return 0
    if cmd == "release-pane" and len(argv) == 2:
        with locked():
            jobs, _ = load_jobs()
            save_jobs([j for j in jobs if argv[1] not in (j.get("key"), j.get("handle"))])
        return 0
    if cmd == "release" and len(argv) == 2:
        try:
            drop_reservation(int(argv[1]))
        except ValueError:
            return 2
        return 0
    if cmd == "list":
        for j in sorted(live_jobs(), key=lambda j: j.get("started", 0)):
            print("%s | %s MB | %s%s | %s | %s | %s" % (j.get("pid") or j.get("handle") or j.get("key"), j.get("mb"), j.get("kind", "test"),
                                                       "" if j.get("measured", True) else " (unmeasured)",
                                                       j.get("what", ""), os.path.basename(str(j.get("repo", ""))), j.get("since", "")))
        return 0
    if cmd == "numbers":
        total, used, limit = machine()
        if used < 0:
            print("ROOM: no: RAM unknown")
            return 1
        jobs = live_jobs()
        reserved = sum(int(j.get("mb", 0) or 0) for j in jobs)
        print("%d %d %d %d" % (max(0, used - trees_mb(jobs)), reserved, limit, pane_need(common_dir(cwd))))
        return 0
    if cmd == "relief":
        return relief()
    if cmd == "measure-pane" and len(argv) == 2:
        return measure_pane(argv[1], cwd)
    sys.stderr.write("usage: agent-room.sh check <mb>|unknown | reserve <pid> <mb> \"<what>\" [--kind test|build|pane] "
                     "[--unmeasured] | reserve-pane <handle> <mb> | reserve-pane --pending <key> <mb> | "
                     "reserve-pane --name <key> <handle> | release-pane <key> | release <pid> | list | relief | measure-pane <pid>\n")
    return 2


def relief():
    """Over the limit: stop live test and build jobs, newest unmeasured first, until the freed MB brings it under.
    Never a pane or another kind."""
    total, used, limit = machine()
    if used < 0 or used <= limit:
        print("ROOM: ok" if used >= 0 else "ROOM: no: RAM unknown")
        return 0
    over = used - limit
    cands = [j for j in live_jobs() if j.get("kind", "test") in ("test", "build") and j.get("by") == "runner"
             and j.get("repo") and same_repo(j.get("repo")) and j.get("pid") and j.get("start")
             and proc_start(j["pid"]) == j["start"]]
    cands.sort(key=lambda j: (bool(j.get("measured", True)), -j.get("started", 0)))
    stopped, freed = [], 0
    for j in cands:
        if freed >= over:
            break
        try:
            os.kill(int(j["pid"]), signal.SIGTERM)
        except OSError:
            continue
        stopped.append(str(j["pid"]))
        freed += int(j.get("mb", 0) or 0)
        drop_reservation(j["pid"])
    print("OVER LIMIT %s: %d MB over; stopped %d test runs (%s); working agents left alone"
          % (host(), over, len(stopped), ", ".join(stopped)))
    return 0


def tree_kb(root_pid):
    """Summed RSS (KB) of a process and everything below it."""
    try:
        out = subprocess.run(["ps", "-axo", "pid=,ppid=,rss="], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             universal_newlines=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    rows, kids = {}, {}
    for line in out.splitlines():
        p = line.split()
        if len(p) == 3 and all(x.isdigit() for x in p):
            rows[int(p[0])] = int(p[2])
            kids.setdefault(int(p[1]), []).append(int(p[0]))
    total, todo, seen = 0, [int(root_pid)], set()
    while todo:
        pid = todo.pop()
        if pid in seen:
            continue
        seen.add(pid)
        total += rows.get(pid, 0)
        todo.extend(kids.get(pid, []))
    return total


def measure_pane(pid, cwd):
    try:
        kb = tree_kb(int(pid))
    except ValueError:
        return 2
    if kb <= 0:
        sys.stderr.write("agent-room.sh measure-pane: no such process %s\n" % pid)
        return 1
    mb = int(math.ceil(kb / 1024.0))
    gitdir = common_dir(cwd)
    with locked():
        data = read_weights(gitdir)
        recent = [int(x) for x in (data.get("pane_recent") or []) if isinstance(x, (int, float))][-4:] + [mb]
        data["pane_recent"] = recent
        data["pane"] = "0 s %d MB" % max(max(recent), PANE_FLOOR_MB)      # the highest of the last 5 measurements, not of all time
        try:
            atomic_write(weights_path(gitdir), json.dumps(data, sort_keys=True) + "\n")
        except OSError:
            pass
        handle = os.environ.get("ORCA_TERMINAL_HANDLE", "")
        if handle:
            jobs, _ = load_jobs()
            try:
                save_jobs([j for j in jobs if j.get("handle") != handle])
            except OSError:
                pass
    return 0


# ------------------------------------------------------------------ test run (C25, C28)

WEIGHT = re.compile(r"^\s*(\d+)\s*s\s+(\d+)\s*MB\s*$")


def parse_weight(text):
    m = WEIGHT.match(str(text))
    return (int(m.group(1)), int(m.group(2))) if m else None


def weights_path(gitdir):
    return os.path.join(gitdir, WEIGHTS)


def read_weights(gitdir):
    try:
        with open(weights_path(gitdir), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def weight_of(gitdir, conf, key):
    """(weight, measured): the per-machine json wins (measured); weight.<key>= in agent_repo.conf is only a seed
    and is never written."""
    got = parse_weight(read_weights(gitdir).get(key, ""))
    if got:
        return got, True
    try:
        with open(conf, encoding="utf-8") as fh:
            for line in fh.read().splitlines():
                if line.startswith("weight.%s=" % key):
                    seed = parse_weight(line.split("=", 1)[1])
                    if seed:
                        return seed, False
    except OSError:
        pass
    return None, False


def write_weight(gitdir, key, secs, mb):
    data = read_weights(gitdir)
    data[key] = "%d s %d MB" % (secs, mb)
    atomic_write(weights_path(gitdir), json.dumps(data, sort_keys=True) + "\n")


def child_mb():
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return int(math.ceil(peak / (1048576.0 if sys.platform == "darwin" else 1024.0)))


def group_kb(pgid):
    """Summed RSS (KB) of every process in the process group."""
    try:
        out = subprocess.run(["ps", "-axo", "pgid=,rss="], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             universal_newlines=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    total = 0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == str(pgid) and parts[1].isdigit():
            total += int(parts[1])
    return total


def kill_group(proc):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except OSError:
            pass
        try:
            proc.wait(timeout=2)
            break
        except subprocess.TimeoutExpired:
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


ACTIVE = []
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def run_monitored(cmd, reserved_mb, **popen):
    """(exit code, peak MB of the whole process tree, stop) with stop None or (used MB, limit MB).
    Every 0.5 s: the tree's memory and the machine's; over the limit and this runner is the pick: stop the group.
    popen: shell, cwd, stdout ... for the nightly's suite."""
    proc = subprocess.Popen(cmd, start_new_session=True, **popen)
    ACTIVE[:] = [proc]
    me, peak, stop = os.getpid(), 0, None
    while True:
        peak = max(peak, group_kb(proc.pid), tree_kb(proc.pid))
        if int(math.ceil(peak / 1024.0)) > reserved_mb:
            reserved_mb = int(math.ceil(peak / 1024.0))
            update_reservation(me, mb=reserved_mb)
        try:
            proc.wait(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            pass
        total, used, limit = machine()
        if used > limit > 0:
            mine = pick_of(live_jobs())
            if mine and mine.get("pid") == me:
                stop = (used, limit)
                kill_group(proc)
                break
    ACTIVE[:] = []
    mb = max(int(math.ceil(peak / 1024.0)), child_mb())
    return proc.returncode, mb, stop


def exit_code(rc):
    return 128 - rc if rc < 0 else rc


def cpu_in_use():
    fake = os.environ.get("AGENT_FAKE_CPU", "")
    if fake:
        try:
            return int(float(fake))
        except ValueError:
            return 50
    script = os.path.join(HERE, "agent-resources.sh")
    try:
        out = subprocess.run(["bash", "-c", '. "$1"; cpu_used', "x", script], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, universal_newlines=True, timeout=30).stdout
        value = int(out.strip().split()[-1])
        return value if value >= 0 else 50
    except Exception:
        return 50


def workers():
    """{workers}: the process count that keeps CPU under the limit: floor(cores x (limit - CPU in use) / 100), at least 1."""
    try:
        cores = int(os.environ.get("AGENT_FAKE_CORES") or os.cpu_count() or 1)
    except ValueError:
        cores = os.cpu_count() or 1
    return max(1, int(cores * (limit_pct() - cpu_in_use()) // 100))


def testrun(argv):
    key, cmd = None, []
    if len(argv) >= 2 and argv[0] == "--key":
        key = argv[1]
        rest = argv[2:]
        if rest and rest[0] == "--":
            cmd = rest[1:]
    if not key or not cmd:
        sys.stderr.write("usage: agent-test-run.sh --key <key> -- <command...>\n")
        return 2
    top = git(os.getcwd(), "rev-parse", "--show-toplevel") or os.getcwd()
    conf = os.path.join(top, "agent_repo.conf")
    gitdir = common_dir(os.getcwd())
    known, measured = weight_of(gitdir, conf, key)
    if known is None:
        print("TEST RUN %s: unknown weight, starts at once, monitored" % key)
        need = 0
    else:
        print("TEST RUN %s: %d MB known (%d s)" % (key, known[1], known[0]))
        need = known[1]
    sys.stdout.flush()
    if any("{workers}" in a for a in cmd):
        count = str(workers())
        cmd = [a.replace("{workers}", count) for a in cmd]
    me = os.getpid()

    def on_term(signum, frame):
        for proc in ACTIVE:
            kill_group(proc)
        drop_reservation(me, blocking=False)
        os._exit(128 + signum)

    for sig in STOP_SIGNALS:
        signal.signal(sig, on_term)
    announce = lambda t: (print("TEST RUN %s: %s" % (key, t)), sys.stdout.flush())
    what = ("%s: %s" % (key, " ".join(cmd)))[:120]
    try:
        while True:
            ok, line = wait_room(need, entry(me, need, what, "test", measured), announce)
            if not ok:
                print(line)
                return 3
            start = time.time()
            try:
                rc, mb, stop = run_monitored(cmd, need)
            except OSError as exc:
                sys.stderr.write("agent-test-run.sh: cannot run %s: %s\n" % (cmd[0], exc))
                rc, mb, stop = 127, child_mb(), None
            secs = int(round(time.time() - start))
            try:
                with locked():
                    write_weight(gitdir, key, secs, mb)
            except OSError:
                pass
            if stop is None:
                return exit_code(rc)
            print("TEST RUN %s: stopped over the limit (%d MB > %d MB), peak %d MB recorded"
                  % (key, stop[0], stop[1], mb))
            sys.stdout.flush()
            drop_reservation(me)
            need, measured = mb, True
    finally:
        drop_reservation(me)


# ------------------------------------------------------------------ nightly status (C6)

def status_path(gitdir):
    return os.path.join(gitdir, STATUS)


def read_status(gitdir):
    try:
        with open(status_path(gitdir), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def running(st):
    return bool(st) and st.get("result") == "running" and pid_alive(st.get("pid"))


def last_stamp(st):
    return parse((st or {}).get("finished")) or parse((st or {}).get("started"))


def status_line(st):
    if not st:
        return "NIGHTLY: none"
    res = st.get("result", "")
    if res == "override":
        res = "override-%s" % st.get("outcome", "?")      # shown, but not green or red for any reader
    if res == "running":
        res, when = ("running" if running(st) else "none"), st.get("started", "")
        if res == "none":
            return "NIGHTLY: none"
    else:
        when = st.get("finished", "")
    return "NIGHTLY: %s %s %s%s" % (res, str(st.get("commit", ""))[:7], when,
                                  (" on a %s" % st["where"] if st.get("where") else ""))


def overridden():
    """True when the command comes from AGENT_NIGHTLY_CMD, not from agent_repo.conf: such a run never counts for a release."""
    return bool(os.environ.get("AGENT_NIGHTLY_CMD"))


def full_cmd(root):
    if os.environ.get("AGENT_NIGHTLY_CMD"):         # a short command for a proof of the mechanics, never the real run
        return os.environ["AGENT_NIGHTLY_CMD"]
    try:
        return agent_conf.repo_conf(root)[0].get("full_cmd", "")
    except Exception:
        return ""


def watch_alive(root):
    try:
        import agent_watchfile
        return agent_watchfile.live(agent_watchfile.read_status(root))
    except Exception:
        return False


def due(cwd):
    root, gitdir = main_root(cwd), common_dir(cwd)
    if not full_cmd(root):
        return False
    st = read_status(gitdir)
    if running(st):
        return False
    if st and st.get("result") in ("stopped", "override"):
        st = None                                       # a stopped run is not done (C20); an override run is no nightly
    t, last = now(), last_stamp(st)
    hour_at = t.replace(hour=number("nightly_hour", 22), minute=0, second=0, microsecond=0)
    if t >= hour_at and (last is None or last < hour_at):
        return True
    if not watch_alive(root) and (last is None or (t - last).total_seconds() >= 24 * 3600):
        return True
    return False


# ------------------------------------------------------------------ the run

UNITTEST = re.compile(r"^\s*(?:FAIL|ERROR): (\S.*)$")     # run2.py prints them indented
PYTEST = re.compile(r"^(?:FAILED|ERROR) (\S*(?:::|\.py)\S*)")


def failed_tests(output):
    found = []
    for line in output.splitlines():
        m = UNITTEST.match(line) or PYTEST.match(line)
        if m and m.group(1) not in found:
            found.append(m.group(1))
    return found


def test_file(root, test_id):
    """The repo file a failing test lives in, or ""."""
    cands = []
    m = re.search(r"\(([\w.]+)\)", test_id)
    if m:
        parts = m.group(1).split(".")
        while parts:
            cands.append(os.path.join(*parts) + ".py")
            parts = parts[:-1]
    path = re.split(r"::", test_id)[0]
    if "::" in test_id:
        cands.insert(0, path)
    for rel in cands:
        if os.path.isfile(os.path.join(root, rel)):
            return rel
    return ""


def names(body, path):
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0]
    return path in body or base in body or (len(stem) >= 4 and stem in body)


def fill(cmd, tests):
    """related_cmd with {tests} and {modules} filled; the paths are added when it has no slot."""
    paths = " ".join(tests)
    modules = " ".join(os.path.splitext(t)[0].replace("/", ".") for t in tests)
    if "{tests}" not in cmd and "{modules}" not in cmd:
        return (cmd + " " + paths).strip()
    return cmd.replace("{tests}", paths).replace("{modules}", modules)


def related_cmd(root):
    try:
        return agent_conf.repo_conf(root)[0].get("related_cmd", "")
    except Exception:
        return ""


MAX_RERUN_MERGES = 20
SCRATCH_TREES = []          # (root, scratch tree) of a --failures rerun going on: a stop signal removes them (C19)


def first_failing_merge(root, gitdir, rel, merges):
    """The first merge (oldest first) at which the test file fails: the file is run in a scratch worktree
    (related_cmd with {tests} and {modules}). A merge where the file does not exist yet is "not there": skipped.
    Each rerun waits for room with the related weight and holds a reservation; at most 20 merges are rerun.
    None when the command is missing, no merge fails, or there is no room."""
    base = related_cmd(root)
    if not base or not rel or not merges:
        return None
    merges = merges[:MAX_RERUN_MERGES]
    cmd = fill(base, [rel])
    weight, measured = weight_of(gitdir, os.path.join(root, "agent_repo.conf"), "related")
    need = weight[1] if weight else 0
    me = os.getpid()
    ok, _ = wait_room(need, entry(me, need, "the failures rerun", "test", measured))
    if not ok:
        return None
    wt = os.path.join(gitdir, SCRATCH + "_failures" + "_%d" % os.getpid())
    found = None
    SCRATCH_TREES.append((root, wt))
    try:
        drop_scratch(root, wt)
        added = subprocess.run(["git", "-C", root, "worktree", "add", "--detach", wt, merges[0][0]],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if added.returncode != 0:
            return None
        link_deps(root, wt)
        for sha, subject in merges:
            moved = subprocess.run(["git", "-C", wt, "checkout", "-q", "--detach", sha],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if moved.returncode != 0 or not os.path.isfile(os.path.join(wt, rel)):
                continue                                    # not there yet at this merge: never a failure
            try:
                code, mb, stop = run_monitored(cmd, need, shell=True, cwd=wt, stdin=subprocess.DEVNULL,
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                continue
            if stop is not None:
                return None                                 # stopped over the limit: no answer, never a guess
            if code != 0:
                found = (sha, subject)
                break
    except OSError:
        found = None
    finally:
        drop_scratch(root, wt)
        drop_reservation(me)
        SCRATCH_TREES[:] = [t for t in SCRATCH_TREES if t[1] != wt]
    return found


def find_merge(root, test_id, green, head, gitdir=None):
    """(short, subject) of the merge that caused the miss: found by running the test file at each first-parent
    merge since the last green commit (at most 20); else by the files the test names; else "unknown" (never the
    newest merge as a guess)."""
    merges = []
    if green:
        out = git(root, "log", "--first-parent", "--merges", "--reverse", "--format=%H\t%s", "%s..%s" % (green, head))
        merges = [line.split("\t", 1) for line in out.splitlines() if "\t" in line]
    pick = None
    rel = test_file(root, test_id)
    if merges and gitdir:
        pick = first_failing_merge(root, gitdir, rel, merges)
    if pick is None and rel and merges:
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            body = ""
        for sha, subject in merges:
            files = git(root, "diff", "--name-only", sha + "^1", sha).splitlines()
            if any(f != rel and names(body, f) for f in files):
                pick = (sha, subject)
                break
    if pick is None and merges:
        return "unknown", ""
    if pick is None:
        out = git(root, "log", "-1", "--format=%H\t%s", head)
        pick = tuple(out.split("\t", 1)) if "\t" in out else (head, "")
    return git(root, "rev-parse", "--short", pick[0]) or pick[0][:7], pick[1]


def record_misses(root, gitdir, prev, failed, commit, stamp):
    green = (prev or {}).get("last_green", "")
    if not green or green == commit:
        return
    old = set((prev or {}).get("failed", [])) if (prev or {}).get("result") == "red" else set()
    lines = []
    for test in failed:
        if test in old or test.startswith("full_cmd exit"):
            continue
        short, subject = find_merge(root, test, green, commit, gitdir)
        lines.append("%s | %s | %s %s" % (stamp, test, short, subject))
    if lines:
        with open(os.path.join(gitdir, MISSES), "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


DEP_DIRS = ("node_modules", ".venv", "venv", "vendor", ".dart_tool", "Pods")


def dep_places(base, depth=2, rel=""):
    """Relative paths of the dependency folders under base: top level, and down into plain folders
    (packages/<x>/node_modules is two folders down)."""
    found = []
    here = os.path.join(base, rel)
    try:
        names = sorted(os.listdir(here))
    except OSError:
        return found
    for name in names:
        path = os.path.join(here, name)
        if name in DEP_DIRS:
            found.append(os.path.join(rel, name))
        elif depth > 0 and name != ".git" and os.path.isdir(path) and not os.path.islink(path):
            found.extend(dep_places(base, depth - 1, os.path.join(rel, name)))
    return found


def link_deps(root, wt):
    """Symlink the main checkout's dependency folders into the scratch tree (never copies)."""
    for rel in dep_places(root):
        src, dst = os.path.join(root, rel), os.path.join(wt, rel)
        if not os.path.isdir(src) or os.path.lexists(dst):
            continue
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.symlink(src, dst)
        except OSError:
            pass


def unlink_deps(wt):
    """Drop the dependency symlinks first, so removing the scratch tree can never reach the main checkout."""
    for rel in dep_places(wt):
        path = os.path.join(wt, rel)
        if os.path.islink(path):
            try:
                os.unlink(path)
            except OSError:
                pass


def drop_scratch(root, wt):
    """Remove the nightly's scratch worktree and its registration, whatever state it is in."""
    if os.path.lexists(wt):
        unlink_deps(wt)
        git(root, "worktree", "remove", "--force", wt)
        shutil.rmtree(wt, ignore_errors=True)
    git(root, "worktree", "prune")


class RunLock:
    """One non-blocking lock around a full run (C11): <git common dir>/agent_nightly.lock."""

    def __init__(self, gitdir):
        self.path, self.fh = os.path.join(gitdir, "agent_nightly.lock"), None

    def take(self):
        try:
            self.fh = open(self.path, "a")
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, ImportError):
            if self.fh:
                self.fh.close()
                self.fh = None
            return False


# ------------------------------------------------------------------ the full run on a connected machine (nightly-on-machine)
# Where it runs: the repo fact full_run_where (either | remote | local, agent_repo.conf) and the person's setting
# "Full run machine" (an Orca environment name, never in a repo file). Orca only, never ssh.

WHERE_VALUES = ("either", "remote", "local")
WHERE_LABEL = "connected machine"
NOTE_PREFIXES = ("full_cmd exit", "the connected machine", "no room on the connected machine", "... and ")   # a failed row that is not a test name
SET_LINE = "set Full run machine in /plugin Configure"
REMOTE = {}                     # the remote run going on (env, path, handle): a stop signal removes it


def full_where(root):
    try:
        value = agent_conf.repo_conf(root)[0].get("full_run_where", "").strip().lower()
    except Exception:
        value = ""
    return value if value in WHERE_VALUES else "either"


def machine_name():
    try:
        return str(agent_conf.get("full_run_machine") or "").strip()
    except Exception:
        return ""


def reachable(env):
    return orca_json(["terminal", "list", "--environment", env, "--json"], 15) is not None


def plan(root):
    """("local", "") | ("remote", <environment>) | ("refuse", <one line>) for the full run of this repo."""
    where, env = full_where(root), machine_name()
    if where == "local":
        return "local", ""
    if where == "either":
        return ("remote", env) if env and reachable(env) else ("local", "")
    if not env:
        return "refuse", "NIGHTLY: refused: full_run_where=remote and no machine is named: %s" % SET_LINE
    if not reachable(env):
        return "refuse", ("NIGHTLY: refused: full_run_where=remote and the connected machine %s is not reachable; "
                          "the run never falls back to this machine" % env)
    return "remote", env


def is_note(test):
    return str(test).startswith(NOTE_PREFIXES)


def orca_call(args, timeout=60):
    """(data, why): the parsed JSON when orca answered ok, else None and a short reason."""
    try:
        res = subprocess.run(["orca"] + args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc) or exc.__class__.__name__
    try:
        data = json.loads(res.stdout)
    except ValueError:
        data = None
    if res.returncode == 0 and isinstance(data, dict) and data.get("ok") is not False:
        return data, ""
    why = ""
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        why = str(data["error"].get("message") or data["error"].get("code") or "")
    err = (res.stderr or "").strip().splitlines()
    return None, (why or (err[-1] if err else "") or "orca failed")[:160]


def result_of(data):
    inner = data.get("result") if isinstance(data, dict) else None
    return inner if isinstance(inner, dict) else {}


def repo_label(root):
    url = git(root, "config", "--get", "remote.origin.url") or root
    name = re.sub(r"\.git$", "", url.rstrip("/").replace("\\", "/").rsplit("/", 1)[-1].rsplit(":", 1)[-1])
    return re.sub(r"[^A-Za-z0-9._-]", "-", name) or "repo"


def host_tag(root=None):
    """A short tag of THIS machine and THIS clone (its git common dir): a start never removes the live run of
    another machine, or of another clone of the same repo, on the same remote."""
    import hashlib
    key = socket.gethostname() + "|" + (common_dir(root) if root else "")
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:6]


def remote_name(root, commit):
    return "nightly-%s-%s-%s" % (repo_label(root), commit[:7], host_tag(root))


def conf_at(root, commit, key):
    """A single value of agent_repo.conf as committed in COMMIT (the remote runs that file's full_cmd)."""
    body = git(root, "show", "%s:agent_repo.conf" % commit)
    return agent_conf._parse_old(body).get(key, "") if body else ""


def remote_cleanup(env, path, handle):
    """Close the terminal and remove the worktree on the connected machine. A note when that did not work."""
    if handle:
        orca_call(["terminal", "close", "--terminal", handle, "--environment", env, "--json"], 30)
    data, why = orca_call(["worktree", "rm", "--worktree", "path:" + path, "--force", "--delete-branch",
                           "--environment", env, "--json"], 90)
    if data is None:
        return "the remote worktree %s was not removed (%s); the next --start removes it" % (path, why)
    return ""


def remote_stale(env, root):
    """Remove the worktrees an earlier run of this repo from this machine left there (a killed run)."""
    data, _ = orca_call(["worktree", "list", "--environment", env, "--json"], 60)
    rows = result_of(data).get("worktrees") or []
    mine, tag = "nightly-%s-" % repo_label(root), "-" + host_tag(root)
    for row in rows if isinstance(rows, list) else []:
        path = row.get("path") if isinstance(row, dict) else None
        base = os.path.basename(str(path or "").rstrip("/"))
        if path and base.startswith(mine) and base.endswith(tag):
            remote_cleanup(env, str(path), None)


def weight_key():
    """An override run is not the repo's full run: its time and memory never replace the 'nightly' weight."""
    return "nightly-override" if overridden() else "nightly"


def remote_script(token, key="nightly"):
    """The one line the connected machine runs in its worktree. Markers carry the commit it ran and the result;
    the output itself stays in a file inside the worktree, so a long run never has to be read back.
    What is closed: the token is in this text only (never an argument, never exported, the file removes itself
    first) and every echoed line of the suite's output is cleaned of control characters and of "@", so printed
    output can never form a marker. The ORCA_* variables are unset for the suite (harmless, not a guarantee).
    Out of scope (a deliberately hostile suite): the open script, the shell history, and its own pane through
    the orca CLI, found by folder."""
    lines = [
        'rm -f "$0"; T=%s; F=$(printf %%s "$1" | base64 -d); O=$PWD/.nightly-out.log; B=$(git symbolic-ref -q --short HEAD)' % token,
        "printf '@@NIGHTLY-%s %s\\n' BEGIN \"$T\"",
        'R=$(git rev-parse HEAD)',
        '[ -n "$B" ] && git checkout -q --detach HEAD && git branch -q -D "$B"',
        'G=./bin/agent-test-run.sh',
        '[ -x "$G" ] || G=$(ls -d "$HOME"/.claude/plugins/cache/*/auto-pipeline/*/bin/agent-test-run.sh 2>/dev/null '
        '| sort -V | tail -n 1)',
        'for V in $(env | sed -n "s/^\\(ORCA_[A-Za-z0-9_]*\\)=.*/\\1/p"); do unset "$V"; done',
        'if [ -n "$G" ] && [ -x "$G" ]; then "$G" --key %s --' % key + ' bash -c "$F" >"$O" 2>&1; '
        'else bash -c "$F" >"$O" 2>&1; fi; X=$?',
        'W=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get(\\"%s\\",\\"\\"))" '
        '"$(git rev-parse --git-common-dir)/agent_test_weights.json" 2>/dev/null)' % key,
        "printf '@@NIGHTLY-%s %s commit=%s exit=%s\\n' RESULT \"$T\" \"$R\" \"$X\"",
        "printf '@@NIGHTLY-%s %s %s\\n' WEIGHT \"$T\" \"$W\"",
        "grep -aE '^[[:space:]]*(FAIL|ERROR): |^(FAILED|ERROR) ' \"$O\" > \"$O.f\"; "
        "head -n 50 \"$O.f\" | "
        "while IFS= read -r L; do L=$(printf %s \"$L\" | LC_ALL=C tr -cd ' -~' | sed 's/@/@ /g'); "
        "printf '@@NIGHTLY-FAIL %s %s\\n' \"$T\" \"$L\"; done",
        "N=$(wc -l < \"$O.f\" | tr -d ' '); [ \"$N\" -gt 50 ] && printf '@@NIGHTLY-FAIL %s ... and %s more failing rows\\n' \"$T\" \"$((N-50))\"; rm -f \"$O.f\"",
        "tail -n 3 \"$O\" | while IFS= read -r L; do L=$(printf %s \"$L\" | LC_ALL=C tr -cd ' -~' | sed 's/@/@ /g'); "
        "printf '@@NIGHTLY-TAIL %s %s\\n' \"$T\" \"$L\"; done",
        "printf '@@NIGHTLY-%s %s\\n' END \"$T\"",
    ]
    return "; ".join(lines)


MARK = re.compile(r"^@@NIGHTLY-([A-Z]+) (\S+)(?: (.*))?$")
RESULT = re.compile(r"^commit=(\S*) exit=(-?\d+)$")


def parse_remote(lines, token):
    """What the markers of this run's token say: begin, end, commit, exit, weight, fail rows, tail rows."""
    out = {"stray": False, "results": 0, "begin": False, "end": False, "commit": None, "exit": None, "weight": "", "fail": [], "tail": []}
    for line in lines:
        m = MARK.match(str(line).strip())
        if not m or m.group(2) != token:
            continue
        kind, rest = m.group(1), m.group(3) or ""
        if kind == "BEGIN":
            out["begin"] = True
        elif kind == "END":
            if out["begin"]:
                out["end"] = True
        elif kind == "RESULT":
            if not out["begin"] or out["end"]:
                out["stray"] = True         # a result line outside BEGIN..END is never the wrapper's
            out["results"] += 1
            r = RESULT.match(rest)
            if r:
                out["commit"], out["exit"] = r.group(1), int(r.group(2))
        elif kind == "WEIGHT":
            out["weight"] = rest
        elif kind == "FAIL":
            out["fail"].append(rest)
        elif kind == "TAIL":
            out["tail"].append(rest)
    return out


def read_terminal(env, handle):
    data, _ = orca_call(["terminal", "read", "--terminal", handle, "--limit", "400", "--environment", env,
                         "--json"], 60)
    tail = (result_of(data).get("terminal") or {}).get("tail") if data else None
    return tail if isinstance(tail, list) else None


def remote_run(root, env, commit, cmd):
    """Run CMD at COMMIT on the connected machine ENV: a worktree of that commit, one terminal, markers read back.
    {"state": ok | failed | noroom | nocreate, "failed": [...], "note": ..., "weight": ...}. Always cleans up."""
    out = {"state": "failed", "failed": [], "note": "", "weight": ""}
    try:
        remote_stale(env, root)
    except Exception:
        pass
    data, why = orca_call(["worktree", "create", "--environment", env, "--repo", "name:" + repo_label(root),
                           "--name", remote_name(root, commit), "--base-branch", commit, "--no-parent",
                           "--setup", "skip", "--json"], 180)
    wt = result_of(data).get("worktree") if data else None
    path = wt.get("path") if isinstance(wt, dict) else None
    if not path:
        out.update(state="nocreate", failed=["the connected machine could not make the worktree of %s: %s"
                                             % (commit[:7], why or "no path in the answer")])
        return out
    handle = None
    REMOTE.update(env=env, path=path, handle=None)
    try:
        data, _ = orca_call(["terminal", "list", "--environment", env, "--worktree", "path:" + path, "--json"], 60)
        rows = result_of(data).get("terminals") or []
        if rows and isinstance(rows[0], dict):
            handle = rows[0].get("handle")
        if not handle:
            data, _ = orca_call(["terminal", "create", "--environment", env, "--worktree", "path:" + path,
                                 "--json"], 60)
            handle = (result_of(data).get("terminal") or {}).get("handle") or result_of(data).get("handle")
        REMOTE["handle"] = handle
        if not handle:
            out["failed"] = ["the connected machine gave no terminal for the run"]
            return out
        token = uuid.uuid4().hex
        # only letters, digits, + / = are typed into the remote shell: no quote of any shell can break the line
        b64 = lambda text: base64.b64encode(text.encode("utf-8")).decode("ascii")
        line = "printf %%s %s | base64 -d > .nightly-run.sh && bash .nightly-run.sh %s" % (
            b64(remote_script(token, weight_key())),
            b64(os.environ.get("AGENT_NIGHTLY_CMD") or conf_at(root, commit, "full_cmd") or cmd))
        sent, why = orca_call(["terminal", "send", "--environment", env, "--terminal", handle, "--text", line,
                               "--enter", "--json"], 60)
        if sent is None:
            out["failed"] = ["the connected machine did not take the command (%s)" % why]
            return out
        try:
            limit = float(os.environ.get("AGENT_NIGHTLY_REMOTE_TIMEOUT_S", "10800"))
            poll = float(os.environ.get("AGENT_NIGHTLY_POLL_S", "5"))
        except ValueError:
            limit, poll = 10800.0, 5.0
        end, bad, got = time.time() + limit, 0, None
        while True:
            lines = read_terminal(env, handle)
            if lines is None:
                bad += 1
                if bad >= 3:
                    out["failed"] = ["the connected machine: the terminal output cannot be read"]
                    return out
            else:
                bad = 0
                got = parse_remote(lines, token)
                if got["end"]:
                    break
            if time.time() >= end:
                orca_call(["terminal", "send", "--environment", env, "--terminal", handle, "--interrupt", "--json"], 30)
                half = got is not None and got["begin"]
                out["failed"] = ["the connected machine: %s after %d s"
                                 % ("the run stopped half way, timed out" if half else
                                    "timed out without a readable result", limit)]
                return out
            time.sleep(poll)
        if got["stray"]:
            out["failed"] = ["the connected machine: a result line outside the run's begin and end"]
        elif got["results"] > 1:
            out["failed"] = ["the connected machine: more than one result line for the run"]
        elif got["commit"] is None or got["exit"] is None:
            out["failed"] = ["the connected machine: the result line is missing or unreadable"]
        elif got["commit"] != commit:
            out["failed"] = ["the connected machine ran %s, not %s" % ((got["commit"] or "no commit")[:7], commit[:7])]
        elif got["exit"] == 3 and any("ROOM" in t for t in got["tail"]):
            out.update(state="noroom", failed=["no room on the connected machine: " + (got["tail"] or [""])[-1]])
        else:
            names = failed_tests("\n".join(got["fail"]))
            names += [r for r in got["fail"] if r.startswith("... and ")][:1]     # the count line after a cut list stays
            out.update(state="ok", weight=got["weight"],
                       failed=[] if got["exit"] == 0 else (names or ["full_cmd exit %d" % got["exit"]]))
        return out
    finally:
        out["note"] = remote_cleanup(env, path, handle)
        REMOTE.clear()


def write_final(root, gitdir, base, prev, commit, result, failed, extra=None):
    stamp = now().strftime(FMT)
    final = {"started": base["started"], "commit": commit, "finished": stamp, "result": result, "failed": failed,
             "last_green": commit if result == "green" and not overridden() else base["last_green"]}
    if overridden():
        final.update(result="override", outcome=result, override=True)   # neither green nor red: older readers see no finished run
    final.update(extra or {})
    names = [f for f in failed if not f.startswith("... and ")]     # the count line of a cut list is no test
    if result != "green" and not any(is_note(f) for f in names):
        try:
            record_misses(root, gitdir, prev, names, commit, stamp)
        except Exception:
            pass
    atomic_write(status_path(gitdir), json.dumps(final))


def do_remote(root, gitdir, env, commit, cmd, base, prev, either):
    """The run on the connected machine, recorded here. 0 when recorded, 3 when there was no room (status put back),
    None when the run is to go on here instead (full_run_where=either: no room, no worktree there)."""

    def on_stop(signum, frame):
        if REMOTE:
            try:
                remote_cleanup(REMOTE.get("env", env), REMOTE.get("path", ""), REMOTE.get("handle"))
            except Exception:
                pass
        atomic_write(status_path(gitdir), json.dumps({"started": base["started"], "commit": commit,
                                                      "finished": now().strftime(FMT), "result": "stopped",
                                                      "failed": [], "last_green": base["last_green"]}))
        os._exit(128 + signum)

    for sig in STOP_SIGNALS:
        signal.signal(sig, on_stop)
    try:
        res = remote_run(root, env, commit, cmd)
    except Exception as exc:
        res = {"state": "failed", "failed": ["the connected machine: the run broke (%s)" % exc], "note": "",
               "weight": ""}
    if res["state"] in ("noroom", "nocreate") and either:
        return None
    if res["state"] == "noroom":
        if prev:
            atomic_write(status_path(gitdir), json.dumps(prev))
        else:
            try:
                os.remove(status_path(gitdir))
            except OSError:
                pass
        sys.stdout.write("NIGHTLY: %s\n" % res["failed"][0])
        return 3
    got = parse_weight(res.get("weight", ""))
    if got:
        try:
            with locked():
                write_weight(gitdir, weight_key(), got[0], got[1])
        except OSError:
            pass
    ok = res["state"] == "ok" and not res["failed"]
    extra = {"where": WHERE_LABEL}
    if res.get("note"):
        extra["note"] = res["note"]
    write_final(root, gitdir, base, prev, commit, "green" if ok else "red", [] if ok else res["failed"], extra)
    return 0


def do_run(cwd):
    """The foreground run: lock, gate, command (monitored), status, misses. Exit 0 whatever the result."""
    root, gitdir = main_root(cwd), common_dir(cwd)
    cmd = full_cmd(root)
    if not cmd:
        sys.stdout.write("NIGHTLY: no full_cmd in agent_repo.conf of %s, nothing to run\n" % root)
        return 0
    mode, env = plan(root)
    if mode == "refuse":
        print(env)
        return 1
    lock = RunLock(gitdir)
    if not lock.take():
        print("NIGHTLY: already running")
        return 0
    st = read_status(gitdir) or {}
    prev = st.get("prev") if st.get("result") == "running" else st
    commit = tip_of(root)
    base = {"started": now().strftime(FMT), "commit": commit, "finished": "", "result": "running", "failed": [],
            "last_green": (prev or {}).get("last_green", ""), "pid": os.getpid(), "prev": prev}
    atomic_write(status_path(gitdir), json.dumps(base))
    if mode == "remote":
        done = do_remote(root, gitdir, env, commit, cmd, base, prev, full_where(root) == "either")
        if done is not None:
            return done
        print("NIGHTLY: the connected machine could not take the run; it runs here")
        sys.stdout.flush()
    weight, measured = weight_of(gitdir, os.path.join(root, "agent_repo.conf"), "nightly")
    me = os.getpid()
    wt = os.path.join(gitdir, SCRATCH)
    log = os.path.join(gitdir, "agent_nightly.log")

    def on_stop(signum, frame):
        for proc in ACTIVE:
            kill_group(proc)
        try:
            drop_scratch(root, wt)
        except Exception:
            pass
        drop_reservation(me, blocking=False)
        atomic_write(status_path(gitdir), json.dumps({"started": base["started"], "commit": commit,
                                                      "finished": now().strftime(FMT), "result": "stopped",
                                                      "failed": [], "last_green": base["last_green"]}))
        os._exit(128 + signum)

    for sig in STOP_SIGNALS:
        signal.signal(sig, on_stop)
    need = weight[1] if weight else 0
    code, output = 0, ""
    try:
        while True:
            ok, why = wait_room(need, entry(me, need, "the nightly", "test", measured))
            if not ok:
                if prev:
                    atomic_write(status_path(gitdir), json.dumps(prev))
                else:
                    try:
                        os.remove(status_path(gitdir))
                    except OSError:
                        pass
                sys.stdout.write("%s\n" % why)
                return 3
            stop = None
            try:
                drop_scratch(root, wt)
                added = subprocess.run(["git", "-C", root, "worktree", "add", "--detach", wt, commit],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                if added.returncode != 0:
                    output, code = "cannot make the scratch worktree: " + added.stdout, 128
                else:
                    link_deps(root, wt)
                    began = time.time()
                    with open(log, "wb") as out_fh:
                        code, mb, stop = run_monitored(cmd, need, shell=True, cwd=wt, stdin=subprocess.DEVNULL,
                                                       stdout=out_fh, stderr=subprocess.STDOUT)
                    try:
                        with locked():
                            write_weight(gitdir, weight_key(), int(round(time.time() - began)), mb)
                    except OSError:
                        pass
                    with open(log, encoding="utf-8", errors="replace") as fh:
                        output = fh.read()
                    if code is not None and code < 0:
                        code = exit_code(code)
            except OSError as exc:
                output, code = str(exc), 127
            finally:
                drop_scratch(root, wt)
                drop_reservation(me)
            if stop is None:
                break
            need, measured = mb, True           # stopped over the limit: peak recorded, wait for room, run again
    finally:
        drop_scratch(root, wt)
        drop_reservation(me)
    try:
        with open(log, "w", encoding="utf-8") as fh:
            fh.write(output[-200000:])
    except OSError:
        pass
    failed = [] if code == 0 else (failed_tests(output) or ["full_cmd exit %d" % code])
    stamp = now().strftime(FMT)
    final = {"started": base["started"], "commit": commit, "finished": stamp,
             "result": "green" if code == 0 else "red", "failed": failed,
             "last_green": commit if code == 0 and not overridden() else base["last_green"]}
    if overridden():
        final.update(result="override", outcome="green" if code == 0 else "red", override=True)
    if code != 0:
        try:
            record_misses(root, gitdir, prev, failed, commit, stamp)
        except Exception:
            pass
    atomic_write(status_path(gitdir), json.dumps(final))
    return 0


def start(cwd, wait):
    root, gitdir = main_root(cwd), common_dir(cwd)
    if not full_cmd(root):
        print("NIGHTLY: no full_cmd in agent_repo.conf of %s, nothing to run" % root)
        return 0
    if wait:
        return do_run(cwd)
    mode, line = plan(root)
    if mode == "refuse":
        print(line)
        return 1
    if running(read_status(gitdir)):
        print("NIGHTLY: already running")
        return 0
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "run"], cwd=cwd, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    print("NIGHTLY: started in the background")
    return 0


NOT_STORED = "no working branch stored in this clone: run agent-init.sh or start the main manager here"


def working_branch(root):
    """The working branch stored in this clone (section 34, F10): None when nothing is stored; never derived here."""
    return agent_conf.working_branch(root)


def production_branch(root):
    """The production branch of this repo (F13): the one function agent_conf.production_branch."""
    return agent_conf.production_branch(root)


def orca_json(args, timeout):
    """The parsed JSON of one orca call, or None (not installed, a failure, not ok, timeout)."""
    try:
        res = subprocess.run(["orca"] + args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, universal_newlines=True, timeout=timeout)
        data = json.loads(res.stdout) if res.returncode == 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if isinstance(data, dict) and data.get("ok") is False:
        return None
    return data


def machines(cwd=None):
    """(paired, reachable): the names of the paired machines (`orca environment list --json` ->
    result.environments) and those that answer `orca terminal list --environment <name> --json` within 10 s."""
    data = orca_json(["environment", "list", "--json"], 30)
    rows = []
    if isinstance(data, dict):
        inner = data.get("result") if isinstance(data.get("result"), dict) else data
        rows = inner.get("environments") or []
    elif isinstance(data, list):
        rows = data
    paired = []
    for row in rows if isinstance(rows, list) else []:
        name = row.get("name") if isinstance(row, dict) else None
        if name and name not in paired:
            paired.append(str(name))
    reachable = [n for n in paired if orca_json(["terminal", "list", "--environment", n, "--json"], 10) is not None]
    return paired, reachable


def machines_cli(cwd):
    paired, reachable = machines(cwd)
    for name in reachable:
        print(name)
    down = [n for n in paired if n not in reachable]
    if down:
        print("NIGHTLY: the paired machine %s did not answer; it runs here when there is room" % ", ".join(down))
    return 0


def need_stored(root):
    """The stored working branch, or print the one refusal line and return None."""
    wb = working_branch(root)
    if not wb:
        print(NOT_STORED)
    return wb


def tip_of(root):
    """The tip of the working branch (local branch), else HEAD."""
    wb = working_branch(root)
    return ((wb and git(root, "rev-parse", "--verify", "-q", "refs/heads/" + wb + "^{commit}"))
            or git(root, "rev-parse", "HEAD"))


def version_only(root, old, new):
    """True when two versions of plugin.json (commits old and new) differ only in the "version" value: the JSON
    and every changed line."""
    texts = [git(root, "show", "%s:.claude-plugin/plugin.json" % c) for c in (old, new)]
    try:
        a, b = json.loads(texts[0]), json.loads(texts[1])
    except ValueError:
        return False
    if not (isinstance(a, dict) and isinstance(b, dict)
            and isinstance(a.pop("version", None), str) and isinstance(b.pop("version", None), str)):
        return False
    import difflib
    changed = [l for l in difflib.ndiff(texts[0].splitlines(), texts[1].splitlines()) if l[:2] in ("- ", "+ ")]
    return a == b and all('"version"' in l for l in changed)


def released_commits(root):
    """The commits a green nightly may have run on for a release: the tip of the working branch, and its parent
    when the tip only bumps the plugin version (a nightly started after the bump runs on the tip)."""
    tip = tip_of(root)
    if not tip:
        return []
    files = git(root, "diff", "--name-only", tip + "^", tip).splitlines()
    if files == [".claude-plugin/plugin.json"] and version_only(root, tip + "^", tip):
        parent = git(root, "rev-parse", tip + "^")
        return [tip] + ([parent] if parent else [])
    return [tip]


def release_ok(cwd):
    root, gitdir = main_root(cwd), common_dir(cwd)
    fix = "run %s/agent-nightly.sh --start" % HERE
    accept = released_commits(root)
    target = accept[-1] if accept else ""
    st = read_status(gitdir)
    if not target:
        print("NIGHTLY: release not ok: no commit to release; %s" % fix)
        return 1
    if st and st.get("result") == "override":
        print("NIGHTLY: release not ok: the last run used a command override (AGENT_NIGHTLY_CMD), not the repo's full_cmd; %s" % fix)
        return 1
    if not st or st.get("result") not in ("green", "red"):
        print("NIGHTLY: release not ok: no finished nightly; %s" % fix)
        return 1
    if st.get("commit") not in accept:
        print("NIGHTLY: release not ok: the last nightly ran on %s, the commit released is %s; %s"
              % (str(st.get("commit"))[:7], target[:7], fix))
        return 1
    target = st.get("commit")
    if st.get("override"):
        print("NIGHTLY: release not ok: the last run on %s used a command override (AGENT_NIGHTLY_CMD), not the repo's full_cmd; %s"
              % (target[:7], fix))
        return 1
    if st.get("result") != "green":
        print("NIGHTLY: release not ok: the nightly on %s is red (%s); fix it, then %s"
              % (target[:7], ", ".join(st.get("failed", [])[:3]), fix))
        return 1
    print("NIGHTLY: release ok: green on the commit released %s" % target[:7])
    return 0


def failures(cwd):
    """C17: one row per failing test of the last red run: <test> | <merge short> <subject> | <task> | <requirement>."""
    root, gitdir = main_root(cwd), common_dir(cwd)
    st = read_status(gitdir)
    if not st or st.get("result") != "red":
        print("NIGHTLY: no red run, no failures")
        return 0

    def on_stop(signum, frame):
        for proc in ACTIVE:
            kill_group(proc)
        for tree_root, tree in list(SCRATCH_TREES):
            try:
                drop_scratch(tree_root, tree)
            except Exception:
                pass
        drop_reservation(os.getpid(), blocking=False)
        os._exit(128 + signum)

    for sig in STOP_SIGNALS:
        signal.signal(sig, on_stop)
    green, head = st.get("last_green", ""), st.get("commit", "")
    for test in st.get("failed", []):
        merge, task, req = "-", "-", "-"
        if green and green != head and not is_note(test):
            short, subject = find_merge(root, test, green, head, gitdir)
            merge = ("%s %s" % (short, subject)).strip()
            m = re.match(r"^Merge (?:branch |pull request )?'?([^\s']+)", subject)
            if m:
                task = m.group(1)
                path = "requirements/%s.md" % task
                if git(root, "cat-file", "-t", "%s:%s" % (head, path)):
                    req = path
        print(" | ".join([test, merge, task, req]))
    return 0


def misses(cwd):
    path = os.path.join(common_dir(cwd), MISSES)
    try:
        with open(path, encoding="utf-8") as fh:
            lines = [l for l in fh.read().splitlines() if l.strip()]
    except OSError:
        lines = []
    for line in lines:
        print(line)
    print("misses: %d since %s" % (len(lines), lines[0].split(" | ")[0] if lines else "-"))
    return 0


def main(argv):
    cwd = os.getcwd()
    if os.environ.get("AGENT_ROOM_CLI") and argv and argv[0] not in ("testrun",):
        return room_main(argv, cwd)
    if argv and argv[0] == "testrun":
        return testrun(argv[1:])
    if argv and argv[0] in ("check", "reserve", "reserve-pane", "release-pane", "release", "list", "numbers", "relief", "measure-pane"):
        return room_main(argv, cwd)
    if argv and argv[0] in ("run", "--start", "--release-ok", "--failures") and not need_stored(main_root(cwd)):
        return 1
    if argv and argv[0] == "run":
        return do_run(cwd)
    if not argv or argv[0] == "--status":
        print(status_line(read_status(common_dir(cwd))))
        return 0
    if argv[0] == "--start":
        return start(cwd, "--wait" in argv[1:])
    if argv[0] == "--due":
        return 0 if due(cwd) else 1
    if argv[0] == "--release-ok":
        return release_ok(cwd)
    if argv[0] == "--machines":
        return machines_cli(cwd)
    if argv[0] == "--where":
        print({"local": "local", "remote": "remote", "refuse": "refused"}[plan(main_root(cwd))[0]])
        return 0
    if argv[0] == "--misses":
        return misses(cwd)
    if argv[0] == "--failures":
        return failures(cwd)
    sys.stderr.write("usage: agent-nightly.sh --start [--wait] | --status | --due | --release-ok | --misses | "
                     "--failures | --where\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
