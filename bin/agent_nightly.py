#!/usr/bin/env python3
"""agent_nightly.py: the nightly run, selection misses, and the light or heavy test run
(requirements/check-blocks.md section 15, C6 and C7). Called by agent-nightly.sh and agent-test-run.sh.

Files in the git common dir: agent_nightly.json, agent_selection_misses.txt, agent_heavy_slots/<pid>,
agent_test_weights.json (measured weights, per machine), agent_nightly_wt (the nightly's scratch worktree).
AGENT_FAKE_NOW ("YYYY-MM-DD HH:MM"), AGENT_FAKE_RAM and AGENT_TEST_RUN_WAIT_S are test hooks.
"""

import datetime
import json
import math
import os
import re
import resource
import shutil
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
SLOTS = "agent_heavy_slots"
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
    fake = os.environ.get("AGENT_FAKE_RAM", "")
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


# ------------------------------------------------------------------ heavy slots (C7)

def live_holders(gitdir, drop_pid=None):
    """pids of the live slot holders; a dead holder's file is removed."""
    slots = os.path.join(gitdir, SLOTS)
    found = []
    try:
        names = os.listdir(slots)
    except OSError:
        return found
    for name in names:
        if not name.isdigit():
            continue
        pid = int(name)
        if pid_alive(pid):
            if pid != drop_pid:
                found.append(pid)
        elif pid != drop_pid:
            try:
                os.remove(os.path.join(slots, name))
            except OSError:
                pass
    return found


def heavy_held(gitdir):
    return bool(live_holders(gitdir))


def try_take(gitdir, key, heavy):
    """(ok, why). Heavy: take the slot file when a slot is free and, for a second or later run, RAM is
    under 50%. Light: only the RAM cap."""
    ram = ram_used()
    if ram < 0:
        return False, "RAM unknown"
    if not heavy:
        cap = number("max_usage_percent", 80)
        if ram > cap:
            return False, "RAM %d%% over the %d%% cap" % (ram, cap)
        return True, ""
    slots = number("heavy_test_slots", 2)
    held = len(live_holders(gitdir, drop_pid=os.getpid()))
    if held >= slots:
        return False, "no heavy slot free (%d of %d held)" % (held, slots)
    if held >= 1 and ram >= 50:
        return False, "RAM %d%% used, a second heavy run needs more than 50%% free" % ram
    os.makedirs(os.path.join(gitdir, SLOTS), exist_ok=True)
    path = os.path.join(gitdir, SLOTS, str(os.getpid()))
    with open(path, "w") as fh:
        fh.write(key + "\n")
    if len(live_holders(gitdir, drop_pid=os.getpid())) >= slots:     # lost a race: give it back
        os.remove(path)
        return False, "no heavy slot free (%d of %d held)" % (slots, slots)
    return True, ""


def wait_for(gitdir, key, heavy, announce=None):
    """(ok, why): wait for the slot or the RAM guard, capped by AGENT_TEST_RUN_WAIT_S."""
    try:
        cap = float(os.environ.get("AGENT_TEST_RUN_WAIT_S", "3600"))
    except ValueError:
        cap = 3600.0
    end = time.time() + cap
    said = False
    while True:
        ok, why = try_take(gitdir, key, heavy)
        if ok:
            return True, ""
        if time.time() >= end:
            return False, why
        if not said and announce:
            announce("waiting: " + why)
            said = True
        time.sleep(max(0.1, min(2.0, end - time.time())))


def release(gitdir):
    try:
        os.remove(os.path.join(gitdir, SLOTS, str(os.getpid())))
    except OSError:
        pass


# ------------------------------------------------------------------ test run (C7)

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
    """The measured weight of <key>: the per-machine json wins; weight.<key>= in agent_repo.conf is a seed."""
    got = parse_weight(read_weights(gitdir).get(key, ""))
    if got:
        return got
    try:
        with open(conf, encoding="utf-8") as fh:
            for line in fh.read().splitlines():
                if line.startswith("weight.%s=" % key):
                    return parse_weight(line.split("=", 1)[1])
    except OSError:
        pass
    return None


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


def run_measured(cmd):
    """(exit code, peak MB of the whole process tree, sampled every ~0.5 s)."""
    proc = subprocess.Popen(cmd, start_new_session=True)
    peak = 0
    while True:
        peak = max(peak, group_kb(proc.pid))
        try:
            proc.wait(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            pass
    mb = max(int(math.ceil(peak / 1024.0)), child_mb())
    return proc.returncode, mb


def exit_code(rc):
    return 128 - rc if rc < 0 else rc


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
    known = weight_of(gitdir, conf, key)
    light_s, light_mb = number("light_test_s", 120), number("light_test_mb", 1024)
    if known is None:
        heavy, why = True, "unknown weight"
    else:
        heavy = not (known[0] < light_s and known[1] < light_mb)
        why = "%d s, %d MB" % known
    print("TEST RUN %s: %s (%s)" % (key, "heavy" if heavy else "light", why))
    sys.stdout.flush()
    ok, reason = wait_for(gitdir, key, heavy, announce=lambda t: (print("TEST RUN %s: %s" % (key, t)),
                                                                  sys.stdout.flush()))
    if not ok:
        print("TEST RUN %s: %s" % (key, reason))
        return 3
    try:
        start = time.time()
        try:
            rc, mb = run_measured(cmd)
        except OSError as exc:
            sys.stderr.write("agent-test-run.sh: cannot run %s: %s\n" % (cmd[0], exc))
            rc, mb = 127, child_mb()
        secs = int(round(time.time() - start))
        try:
            write_weight(gitdir, key, secs, mb)
        except OSError:
            pass
    finally:
        release(gitdir)
    return exit_code(rc)


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
    if not full_cmd(root) or heavy_held(gitdir):
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


def find_merge(root, test_id, green, head):
    """(short, subject) of the merge that caused the miss."""
    merges = []
    if green:
        out = git(root, "log", "--first-parent", "--merges", "--reverse", "--format=%H\t%s", "%s..%s" % (green, head))
        merges = [line.split("\t", 1) for line in out.splitlines() if "\t" in line]
    pick = None
    rel = test_file(root, test_id)
    if rel and merges:
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
        short, subject = find_merge(root, test, green, commit)
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
    """The foreground run: slot, command, status, misses. Exit 0 whatever the result."""
    root, gitdir = main_root(cwd), common_dir(cwd)
    cmd = full_cmd(root)
    st = read_status(gitdir) or {}
    prev = st.get("prev") if st.get("result") == "running" else st
    commit = git(root, "rev-parse", "HEAD")
    if not cmd:
        sys.stdout.write("NIGHTLY: no full_cmd in agent_repo.conf of %s, nothing to run\n" % root)
        return 0
    base = {"started": now().strftime(FMT), "commit": commit, "finished": "", "result": "running", "failed": [],
            "last_green": (prev or {}).get("last_green", ""), "pid": os.getpid(), "prev": prev}
    atomic_write(status_path(gitdir), json.dumps(base))
    ok, why = wait_for(gitdir, "nightly", True)
    if not ok:
        if prev:
            atomic_write(status_path(gitdir), json.dumps(prev))
        else:
            os.remove(status_path(gitdir))
        sys.stdout.write("NIGHTLY: not started: %s\n" % why)
        return 0
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
        release(gitdir)
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


def released_commit(root):
    """The commit a release is built from: local HEAD, or HEAD^ when HEAD only bumps the plugin version."""
    head = git(root, "rev-parse", "HEAD")
    if not head:
        return ""
    files = git(root, "diff", "--name-only", "HEAD^", "HEAD").splitlines()
    if files == [".claude-plugin/plugin.json"]:
        return git(root, "rev-parse", "HEAD^") or head
    return head


def release_ok(cwd):
    root, gitdir = main_root(cwd), common_dir(cwd)
    fix = "run %s/agent-nightly.sh --start" % HERE
    target = released_commit(root)
    st = read_status(gitdir)
    if not target:
        print("NIGHTLY: release not ok: no commit to release; %s" % fix)
        return 1
    if not st or st.get("result") not in ("green", "red"):
        print("NIGHTLY: release not ok: no finished nightly; %s" % fix)
        return 1
    if st.get("commit") != target:
        print("NIGHTLY: release not ok: the last nightly ran on %s, the commit released is %s; %s"
              % (str(st.get("commit"))[:7], target[:7], fix))
        return 1
    if st.get("result") != "green":
        print("NIGHTLY: release not ok: the nightly on %s is red (%s); fix it, then %s"
              % (target[:7], ", ".join(st.get("failed", [])[:3]), fix))
        return 1
    print("NIGHTLY: release ok: green on the commit released %s" % target[:7])
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
    sys.stderr.write("usage: agent-nightly.sh --start [--wait] | --status | --due | --release-ok | --misses\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
