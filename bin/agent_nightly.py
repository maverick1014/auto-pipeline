#!/usr/bin/env python3
"""agent_nightly.py: the nightly run, selection misses, the memory gate and the monitored test run
(requirements/check-blocks.md sections 15, 17, 24, 25). Called by agent-nightly.sh, agent-test-run.sh, agent-room.sh.

Files in the git common dir: agent_nightly.json, agent_selection_misses.txt, agent_test_weights.json (measured
weights, per machine), agent_nightly_wt (the nightly's scratch worktree). The reservation list is one file per
machine ($AGENT_RESERVE_FILE). Test hooks: AGENT_FAKE_NOW ("YYYY-MM-DD HH:MM"), AGENT_FAKE_RAM, AGENT_FAKE_RAM_FILE,
AGENT_FAKE_RAM_TOTAL_MB, AGENT_FAKE_CPU, AGENT_FAKE_CORES, AGENT_FAKE_HOST, AGENT_TEST_RUN_WAIT_S.
"""

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
    if res == "running":
        res, when = ("running" if running(st) else "none"), st.get("started", "")
        if res == "none":
            return "NIGHTLY: none"
    else:
        when = st.get("finished", "")
    kind = ""
    if st.get("kind") == "top-up":
        kind = " top-up over %s" % str(st.get("full_green", ""))[:7]
    elif st.get("kind") == "full":
        kind = " full run"
    return "NIGHTLY: %s %s %s%s" % (res, str(st.get("commit", ""))[:7], when, kind)


def needed_line(root, st):
    """The second --status line: which kind of run the tip needs now, and why."""
    if running(st):
        return "NEEDED: wait for the run going on"
    if st and st.get("result") == "green" and not invalid(root, st) and st.get("commit") in released_commits(root):
        return "NEEDED: nothing: green on the tip (%s)" % kind_of(st)
    return "NEEDED: " + need_line(plan(root, st))


def full_cmd(root):
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
    if st and st.get("result") == "stopped":
        st = None                                       # a stopped run is not done (C20)
    t, last = now(), last_stamp(st)
    hour_at = t.replace(hour=number("nightly_hour", 22), minute=0, second=0, microsecond=0)
    if t >= hour_at and (last is None or last < hour_at):
        return True
    if not watch_alive(root) and (last is None or (t - last).total_seconds() >= 24 * 3600):
        return True
    return False


# ------------------------------------------------------------------ the run

UNITTEST = re.compile(r"^(?:FAIL|ERROR): (\S.*)$")
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
        if test in old or test.startswith(("full_cmd exit", "top-up exit")):
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


def do_run(cwd, nightly=False):
    """The foreground run: lock, gate, command (monitored), status, misses. Exit 0 whatever the result.
    nightly: started by the automatic nightly path: always the full run (it can only make a run bigger)."""
    root, gitdir = main_root(cwd), common_dir(cwd)
    cmd = full_cmd(root)
    if not cmd:
        sys.stdout.write("NIGHTLY: no full_cmd in agent_repo.conf of %s, nothing to run\n" % root)
        return 0
    lock = RunLock(gitdir)
    if not lock.take():
        print("NIGHTLY: already running")
        return 0
    st = read_status(gitdir) or {}
    prev = st.get("prev") if st.get("result") == "running" else st
    commit = tip_of(root)
    p = plan(root, prev, commit)                       # full or top-up: from git and the last record alone
    if nightly:
        p = {"kind": "full", "base": "", "tests": [], "why": "the automatic nightly is always the full run"}
    carry = p["base"] if p["kind"] == "top-up" else full_base(prev)[0]
    base = {"started": now().strftime(FMT), "commit": commit, "finished": "", "result": "running", "failed": [],
            "last_green": (prev or {}).get("last_green", ""), "pid": os.getpid(), "prev": prev,
            "kind": p["kind"], "full_green": carry}
    if p["kind"] == "top-up":
        base["tests"] = p["tests"]
        cmd = fill(conf_at(root, commit).get("related_cmd", ""), p["tests"])
    print("NIGHTLY: %s on %s: %s" % ("top-up" if p["kind"] == "top-up" else "full run", commit[:7], p["why"]))
    sys.stdout.flush()
    atomic_write(status_path(gitdir), json.dumps(base))
    wkey = "topup" if p["kind"] == "top-up" else "nightly"
    weight, measured = weight_of(gitdir, os.path.join(root, "agent_repo.conf"), wkey)
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
                                                      "failed": [], "last_green": base["last_green"],
                                                      "kind": base["kind"], "full_green": carry}))
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
                            write_weight(gitdir, wkey, int(round(time.time() - began)), mb)
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
    exit_name = "top-up exit %d" if p["kind"] == "top-up" else "full_cmd exit %d"
    failed = [] if code == 0 else (failed_tests(output) or [exit_name % code])
    stamp = now().strftime(FMT)
    final = {"started": base["started"], "commit": commit, "finished": stamp,
             "result": "green" if code == 0 else "red", "failed": failed,
             "last_green": commit if code == 0 else base["last_green"], "kind": p["kind"]}
    if p["kind"] == "top-up":
        final.update(full_green=p["base"], tests=p["tests"])  # a red top-up still stands on the green full run
    else:
        final["full_green"] = commit if code == 0 else ""     # a red full run ends the chain
    if code != 0:
        try:
            record_misses(root, gitdir, prev, failed, commit, stamp)
        except Exception:
            pass
    atomic_write(status_path(gitdir), json.dumps(final))
    return 0


def start(cwd, wait, nightly=False):
    root, gitdir = main_root(cwd), common_dir(cwd)
    if not full_cmd(root):
        print("NIGHTLY: no full_cmd in agent_repo.conf of %s, nothing to run" % root)
        return 0
    if wait:
        return do_run(cwd, nightly)
    if running(read_status(gitdir)):
        print("NIGHTLY: already running")
        return 0
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "run"] + (["--nightly"] if nightly else []), cwd=cwd, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    p = plan(root, read_status(gitdir))
    if nightly:
        p = {"kind": "full", "why": "the automatic nightly is always the full run"}
    print("NIGHTLY: started in the background (%s: %s)" % ("top-up" if p["kind"] == "top-up" else "full run", p["why"]))
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


def released_commits(root):
    """The commits a green nightly may have run on for a release: the tip of the working branch, and its parent
    when the tip only bumps the plugin version (a nightly started after the bump runs on the tip)."""
    tip = tip_of(root)
    if not tip:
        return []
    files = git(root, "diff", "--name-only", tip + "^", tip).splitlines()
    if files == [".claude-plugin/plugin.json"]:
        parent = git(root, "rev-parse", tip + "^")
        return [tip] + ([parent] if parent else [])
    return [tip]


# ------------------------------------------------------------------ the top-up (requirements/release-check-loosen.md)
# After a green FULL run on G, the commits G..tip are small when every file they change is text (.md), a mock page
# (mock/), a test file (tests/test_*.py) or the version line of .claude-plugin/plugin.json. Decided from git alone:
# no option, no environment variable, no caller can make a change small. Anything not named is code.

SHA = re.compile(r"^[0-9a-f]{40}$")
TEST_FILE = re.compile(r"^tests/test_[^/]+\.py$")
PLUGIN_JSON = ".claude-plugin/plugin.json"
NO_FILE = "0" * 6


def git_rc(root, *args):
    """(ok, stdout) of one git call; ok is False on any failure (never read as "no change")."""
    try:
        res = subprocess.run(["git", "-C", root] + list(args), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=120)
    except (OSError, subprocess.SubprocessError):
        return False, ""
    return res.returncode == 0, res.stdout.decode("utf-8", "surrogateescape")


def is_commit(root, sha):
    return isinstance(sha, str) and bool(SHA.match(sha)) and git_rc(root, "cat-file", "-e", sha + "^{commit}")[0]


def is_ancestor(root, a, b):
    return git_rc(root, "merge-base", "--is-ancestor", a, b)[0]


def raw_diff(root, a, b):
    """[(old mode, new mode, old blob, new blob, status, path)] of a..b, renames split into a delete and an add;
    None when git cannot compare them."""
    ok, out = git_rc(root, "diff", "--raw", "-z", "--no-renames", "--no-abbrev", "--no-ext-diff", a, b)
    if not ok:
        return None
    parts, found, i = out.split("\0"), [], 0
    while i + 1 < len(parts):
        head = parts[i].lstrip(":").split()
        if len(head) != 5:
            return None
        found.append(tuple(head) + (parts[i + 1],))
        i += 2
    return found


def version_only(root, old_blob, new_blob):
    """True when two plugin.json blobs differ only in the "version" value (the JSON and every changed line)."""
    texts = []
    for blob in (old_blob, new_blob):
        ok, body = git_rc(root, "cat-file", "blob", blob)
        if not ok:
            return False
        texts.append(body)
    try:
        old, new = json.loads(texts[0]), json.loads(texts[1])
    except ValueError:
        return False
    if not (isinstance(old, dict) and isinstance(new, dict)
            and isinstance(old.pop("version", None), str) and isinstance(new.pop("version", None), str)):
        return False
    import difflib
    changed = [l for l in difflib.ndiff(texts[0].splitlines(), texts[1].splitlines()) if l[:2] in ("- ", "+ ")]
    return old == new and all('"version"' in l for l in changed)


def frontmatter(root, blob):
    """The frontmatter block of a .md blob (the lines from the first line --- to the next ---), None when unreadable."""
    ok, body = git_rc(root, "cat-file", "blob", blob)
    if not ok:
        return None
    lines = body.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[:i + 1]
    return lines                                   # no closing line: the whole file counts as frontmatter


def not_small(root, change):
    """"" when one changed file is small, else why it is code."""
    old_mode, new_mode, old_blob, new_blob, status, path = change
    modes = {old_mode, new_mode} - {NO_FILE}
    if status not in ("A", "M", "D"):
        return "%s is code (git status %s)" % (path, status)
    if modes != {"100644"}:
        if "120000" in modes:
            return "%s is a symlink (code)" % path
        if "160000" in modes:
            return "%s is a submodule (code)" % path
        return "%s has a file mode change (%s -> %s, code)" % (path, old_mode, new_mode)
    if path.endswith(".md") and path.startswith(("agents/", "skills/")):
        if status != "M":                    # an agent or a skill that comes or goes is configuration
            return "%s is %s (an agent or skill file: code)" % (path, "added" if status == "A" else "deleted")
        if frontmatter(root, old_blob) != frontmatter(root, new_blob):
            return "%s changes its frontmatter (configuration Claude Code reads: code)" % path
        return ""
    if path.endswith(".md") or path.startswith("mock/"):
        return ""
    if TEST_FILE.match(path):
        return "%s was deleted (a check went away)" % path if status == "D" else ""
    if path == PLUGIN_JSON:
        if status == "M" and version_only(root, old_blob, new_blob):
            return ""
        return "%s changes more than the version line (code)" % path
    return "%s is code" % path


def small_since(root, base, tip):
    """(small, why, changed test files) for the commits base..tip: the files base..tip bring (a merge counts by
    these), and every non-merge commit between, one by one. why names the first code file."""
    if not (is_commit(root, base) and is_commit(root, tip)):
        return False, "no green full run to stand on", []
    if not is_ancestor(root, base, tip):
        return False, "the green full run %s is not an ancestor of %s" % (base[:7], tip[:7]), []
    net = raw_diff(root, base, tip)
    if net is None:
        return False, "git cannot compare %s with %s" % (base[:7], tip[:7]), []
    for change in net:
        why = not_small(root, change)
        if why:
            return False, why, []
    ok, out = git_rc(root, "rev-list", "--reverse", "--parents", "%s..%s" % (base, tip))
    if not ok:
        return False, "git cannot list the commits %s..%s" % (base[:7], tip[:7]), []
    for line in out.splitlines():
        shas = line.split()
        if len(shas) > 2:
            continue                                        # a merge: counted by the files base..tip bring
        if len(shas) < 2:
            return False, "the commit %s has no parent (code)" % shas[0][:7], []
        each = raw_diff(root, shas[1], shas[0])
        if each is None:
            return False, "git cannot read the commit %s" % shas[0][:7], []
        for change in each:
            why = not_small(root, change)
            if why:
                return False, "%s in the commit %s" % (why, shas[0][:7]), []
    tests = sorted(c[5] for c in net if c[4] in ("A", "M") and TEST_FILE.match(c[5]))
    return True, "", tests


def conf_at(root, commit):
    """The key=value lines of agent_repo.conf as committed at commit (the last value of a key wins)."""
    ok, body = git_rc(root, "show", "%s:agent_repo.conf" % commit)
    found = {}
    for line in body.splitlines() if ok else []:
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            found[key.strip()] = value.strip()
    return found


def guard_tests(conf):
    return [g.strip() for g in conf.get("guard_tests", "").split(",") if g.strip()]


def full_base(st):
    """(G, why): the green FULL run the next top-up may stand on, from the last record; "" and why when none."""
    if st and st.get("result") == "running":
        st = st.get("prev") if isinstance(st.get("prev"), dict) else None
    none = "no green full run to stand on (the last full run was red, or none ran)"
    if not st:
        return "", none
    if "kind" not in st and "full_green" not in st:           # a record from before the top-up: a full run
        commit = st.get("commit")
        return (commit, "") if st.get("result") == "green" and isinstance(commit, str) and SHA.match(commit) \
            else ("", none)
    g = st.get("full_green")
    if not g:
        return "", none
    if not isinstance(g, str) or not SHA.match(g):
        return "", "the status file is not valid (full_green %r)" % (g,)
    return g, ""


def invalid(root, st):
    """"" when a finished record holds together, else why not. A forged or half-written record is refused."""
    commit = st.get("commit")
    if not is_commit(root, commit):
        return "the commit %r is not a full commit of this repo" % (commit,)
    kind = st.get("kind")
    if kind is None and "full_green" not in st:
        return ""                                            # a record from before the top-up: a full run
    if kind == "full":
        if st.get("result") == "green" and st.get("full_green") != commit:
            return "a green full run stands on its own commit, not %r" % (st.get("full_green"),)
        return ""
    if kind != "top-up":
        return "unknown kind %r" % (kind,)
    g = st.get("full_green")
    if not is_commit(root, g):
        return "the top-up names no green full run (%r)" % (g,)
    if g == commit:
        return "the top-up stands on itself"
    ok, why, tests = small_since(root, g, commit)
    if not ok:
        return "the top-up on %s stands on %s, but %s" % (commit[:7], g[:7], why)
    need = sorted(set(guard_tests(conf_at(root, commit)) + tests))
    ran = st.get("tests")
    if not isinstance(ran, list) or sorted(set(ran)) != need:
        return "the top-up ran %s, the rule needs %s" % (ran, need)
    return ""


def plan(root, st, tip=None):
    """{"kind": "full"|"top-up", "base": G, "tests": [...], "why": ...} for the tip of the working branch."""
    tip = tip or tip_of(root)
    rec = st.get("prev") if st and st.get("result") == "running" else st
    if isinstance(rec, dict) and rec.get("result") in ("green", "red"):
        bad = invalid(root, rec)
        if bad:
            return {"kind": "full", "base": "", "tests": [], "why": "the status file is not valid: " + bad}
    g, why = full_base(st)
    if not g:
        return {"kind": "full", "base": "", "tests": [], "why": why}
    if g == tip:
        return {"kind": "full", "base": "", "tests": [], "why": "nothing changed since the green full run on %s" % g[:7]}
    conf = conf_at(root, tip)
    if not conf.get("related_cmd"):
        return {"kind": "full", "base": "", "tests": [], "why": "no related_cmd in agent_repo.conf to run a top-up"}
    ok, why, tests = small_since(root, g, tip)
    if not ok:
        return {"kind": "full", "base": "", "tests": [], "why": why}
    run = []
    for t in guard_tests(conf) + tests:
        if t not in run:
            run.append(t)
    if not run:
        return {"kind": "full", "base": "", "tests": [], "why": "no guard tests and no changed test file to run"}
    return {"kind": "top-up", "base": g, "tests": run,
            "why": "only text, mock pages or tests changed since the green full run on %s" % g[:7]}


def need_line(p):
    if p["kind"] == "top-up":
        return "a top-up is enough (%s): it runs %s" % (p["why"], ", ".join(p["tests"]))
    return "the full run is needed: %s" % p["why"]


def kind_of(st):
    if st.get("kind") == "top-up":
        return "top-up over %s" % str(st.get("full_green"))[:7]
    return "full run"


def release_ok(cwd):
    root, gitdir = main_root(cwd), common_dir(cwd)
    fix = "run %s/agent-nightly.sh --start" % HERE
    accept = released_commits(root)
    target = accept[-1] if accept else ""
    st = read_status(gitdir)
    if not target:
        print("NIGHTLY: release not ok: no commit to release; %s" % fix)
        return 1
    if not st or st.get("result") not in ("green", "red"):
        print("NIGHTLY: release not ok: no finished nightly; %s; %s" % (need_line(plan(root, st)), fix))
        return 1
    bad = invalid(root, st)
    if bad:
        print("NIGHTLY: release not ok: the status file is not valid: %s; the full run is needed; %s" % (bad, fix))
        return 1
    if st.get("commit") not in accept:
        print("NIGHTLY: release not ok: the last nightly ran on %s, the commit released is %s; %s; %s"
              % (str(st.get("commit"))[:7], target[:7], need_line(plan(root, st)), fix))
        return 1
    target = st.get("commit")
    if st.get("result") != "green":
        print("NIGHTLY: release not ok: the nightly on %s is red (%s, %s); fix it, then %s"
              % (target[:7], kind_of(st), ", ".join(st.get("failed", [])[:3]), fix))
        return 1
    print("NIGHTLY: release ok: green on the commit released %s (%s)" % (target[:7], kind_of(st)))
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
        if green and green != head and not test.startswith(("full_cmd exit", "top-up exit")):
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
    if argv and argv[0] == "run" and all(a == "--nightly" for a in argv[1:]):
        return do_run(cwd, "--nightly" in argv[1:])
    if not argv or argv[0] == "--status":
        st = read_status(common_dir(cwd))
        print(status_line(st))
        print(needed_line(main_root(cwd), st))
        return 0
    if argv[0] == "--start" and all(a in ("--wait", "--nightly") for a in argv[1:]):
        # the one option is --nightly, and it can only make the run FULL; nothing makes a run smaller
        return start(cwd, "--wait" in argv[1:], "--nightly" in argv[1:])
    if argv[0] == "--due":
        return 0 if due(cwd) else 1
    if argv[0] == "--release-ok":
        return release_ok(cwd)
    if argv[0] == "--machines":
        return machines_cli(cwd)
    if argv[0] == "--misses":
        return misses(cwd)
    if argv[0] == "--failures":
        return failures(cwd)
    sys.stderr.write("usage: agent-nightly.sh --start [--wait] [--nightly] | --status | --due | --release-ok | --misses | "
                     "--failures\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
