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
    """Exclusive lock on a file next to the reservation list, for every read-modify-write."""

    def __enter__(self):
        path = reserve_path() + ".lock"
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self.fh = open(path, "a")
            fcntl.flock(self.fh, fcntl.LOCK_EX)
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


def load_jobs():
    """Live entries only (a dead pid is dropped); the caller holds the lock when it writes back."""
    try:
        with open(reserve_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
    except (OSError, ValueError):
        return [], False
    live = [j for j in jobs if isinstance(j, dict) and pid_alive(j.get("pid"))]
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
    return os.path.basename(git(os.getcwd(), "rev-parse", "--show-toplevel") or os.getcwd())


def entry(pid, mb, what, kind, measured):
    return {"pid": int(pid), "mb": int(mb), "what": what, "repo": repo_name(), "since": now().strftime(FMT),
            "started": time.time(), "kind": kind, "measured": bool(measured)}


def room(need, reserve_as=None):
    """(ok, line). need is MB (0 for unknown). With reserve_as = an entry, it is stored in the same locked step,
    so two agents never count the same free memory. Fails closed when RAM or the total cannot be read."""
    with locked():
        jobs, _ = load_jobs()
        me = reserve_as["pid"] if reserve_as else None
        others = [j for j in jobs if j.get("pid") != me]
        total, used, limit = machine()
        if used < 0:
            return False, "ROOM: no: RAM unknown"
        reserved = sum(int(j.get("mb", 0) or 0) for j in others)
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


def drop_reservation(pid):
    with locked():
        jobs, _ = load_jobs()
        try:
            save_jobs([j for j in jobs if j.get("pid") != pid])
        except OSError:
            pass


def pick_of(jobs):
    """The job the monitor stops first: the newest unmeasured live test or build run, else the newest."""
    cands = [j for j in jobs if j.get("kind", "test") in ("test", "build")]
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
            new = entry(pos[0], pos[1], pos[2], kind, measured)
        except ValueError:
            sys.stderr.write("agent-room.sh reserve: pid and mb are numbers\n")
            return 2
        with locked():
            jobs, _ = load_jobs()
            save_jobs([j for j in jobs if j.get("pid") != new["pid"]] + [new])
        return 0
    if cmd == "release" and len(argv) == 2:
        try:
            drop_reservation(int(argv[1]))
        except ValueError:
            return 2
        return 0
    if cmd == "list":
        for j in sorted(live_jobs(), key=lambda j: j.get("started", 0)):
            print("%s | %s MB | %s%s | %s | %s | %s" % (j.get("pid"), j.get("mb"), j.get("kind", "test"),
                                                       "" if j.get("measured", True) else " (unmeasured)",
                                                       j.get("what", ""), j.get("repo", ""), j.get("since", "")))
        return 0
    if cmd == "numbers":
        total, used, limit = machine()
        if used < 0:
            print("ROOM: no: RAM unknown")
            return 1
        reserved = sum(int(j.get("mb", 0) or 0) for j in live_jobs())
        print("%d %d %d %d" % (used, reserved, limit, pane_need(common_dir(cwd))))
        return 0
    if cmd == "relief":
        return relief()
    if cmd == "measure-pane" and len(argv) == 2:
        return measure_pane(argv[1], cwd)
    sys.stderr.write("usage: agent-room.sh check <mb>|unknown | reserve <pid> <mb> \"<what>\" [--kind test|build|pane] "
                     "[--unmeasured] | release <pid> | list | relief | measure-pane <pid>\n")
    return 2


def relief():
    """Over the limit: stop live test and build jobs, newest unmeasured first, until the freed MB brings it under.
    Never a pane or another kind."""
    total, used, limit = machine()
    if used < 0 or used <= limit:
        print("ROOM: ok" if used >= 0 else "ROOM: no: RAM unknown")
        return 0
    over = used - limit
    cands = [j for j in live_jobs() if j.get("kind", "test") in ("test", "build")]
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
        old = parse_weight(read_weights(gitdir).get("pane", ""))
        if not old or mb > old[1]:
            try:
                write_weight(gitdir, "pane", 0, mb)
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


def run_monitored(cmd, reserved_mb):
    """(exit code, peak MB of the whole process tree, stop) with stop None or (used MB, limit MB).
    Every 0.5 s: the tree's memory and the machine's; over the limit and this runner is the pick: stop the group."""
    proc = subprocess.Popen(cmd, start_new_session=True)
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
        drop_reservation(me)
        os._exit(128 + signum)

    signal.signal(signal.SIGTERM, on_term)
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
    return "NIGHTLY: %s %s %s" % (res, str(st.get("commit", ""))[:7], when)


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


def first_failing_merge(root, gitdir, rel, merges):
    """The first merge (oldest first) at which the test file fails: the file is run in a scratch worktree
    (related_cmd with {tests} and {modules}). None when the command is missing or no merge fails."""
    base = related_cmd(root)
    if not base or not rel or not merges:
        return None
    cmd = fill(base, [rel])
    wt = os.path.join(gitdir, SCRATCH + "_failures")
    found = None
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
            if moved.returncode != 0:
                continue
            res = subprocess.run(cmd, shell=True, cwd=wt, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            if res.returncode != 0:
                found = (sha, subject)
                break
    except OSError:
        found = None
    finally:
        drop_scratch(root, wt)
    return found


def find_merge(root, test_id, green, head, gitdir=None):
    """(short, subject) of the merge that caused the miss: found by running the test file at each first-parent
    merge since the last green commit; else by the files the test names; else the last merge."""
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
        pick = merges[-1]
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


def do_run(cwd):
    """The foreground run: gate, command, status, misses. Exit 0 whatever the result."""
    root, gitdir = main_root(cwd), common_dir(cwd)
    cmd = full_cmd(root)
    st = read_status(gitdir) or {}
    prev = st.get("prev") if st.get("result") == "running" else st
    commit = tip_of(root)
    if not cmd:
        sys.stdout.write("NIGHTLY: no full_cmd in agent_repo.conf of %s, nothing to run\n" % root)
        return 0
    base = {"started": now().strftime(FMT), "commit": commit, "finished": "", "result": "running", "failed": [],
            "last_green": (prev or {}).get("last_green", ""), "pid": os.getpid(), "prev": prev}
    atomic_write(status_path(gitdir), json.dumps(base))
    weight, measured = weight_of(gitdir, os.path.join(root, "agent_repo.conf"), "nightly")
    me = os.getpid()
    ok, why = wait_room(weight[1] if weight else 0,
                        entry(me, weight[1] if weight else 0, "the nightly", "test", measured))
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
    wt = os.path.join(gitdir, SCRATCH)
    try:
        drop_scratch(root, wt)
        added = subprocess.run(["git", "-C", root, "worktree", "add", "--detach", wt, commit],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        if added.returncode != 0:
            output, code = "cannot make the scratch worktree: " + added.stdout, 128
        else:
            link_deps(root, wt)
            res = subprocess.run(cmd, shell=True, cwd=wt, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 universal_newlines=True, errors="replace")
            output, code = res.stdout, res.returncode
    except OSError as exc:
        output, code = str(exc), 127
    finally:
        drop_scratch(root, wt)
        drop_reservation(me)
    try:
        with open(os.path.join(gitdir, "agent_nightly.log"), "w", encoding="utf-8") as fh:
            fh.write(output[-200000:])
    except OSError:
        pass
    failed = [] if code == 0 else (failed_tests(output) or ["full_cmd exit %d" % code])
    stamp = now().strftime(FMT)
    final = {"started": base["started"], "commit": commit, "finished": stamp,
             "result": "green" if code == 0 else "red", "failed": failed,
             "last_green": commit if code == 0 else base["last_green"]}
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
        print("NIGHTLY: release not ok: no finished nightly; %s" % fix)
        return 1
    if st.get("commit") not in accept:
        print("NIGHTLY: release not ok: the last nightly ran on %s, the commit released is %s; %s"
              % (str(st.get("commit"))[:7], target[:7], fix))
        return 1
    target = st.get("commit")
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
    green, head = st.get("last_green", ""), st.get("commit", "")
    for test in st.get("failed", []):
        merge, task, req = "-", "-", "-"
        if green and green != head and not test.startswith("full_cmd exit"):
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
    if argv and argv[0] == "testrun":
        return testrun(argv[1:])
    if argv and argv[0] in ("check", "reserve", "release", "list", "numbers", "relief", "measure-pane"):
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
    if argv[0] == "--misses":
        return misses(cwd)
    if argv[0] == "--failures":
        return failures(cwd)
    sys.stderr.write("usage: agent-nightly.sh --start [--wait] | --status | --due | --release-ok | --misses | "
                     "--failures\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
