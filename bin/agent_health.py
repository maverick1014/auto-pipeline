#!/usr/bin/env python3
"""agent_health.py - machine-health (requirements/machine-health.md): who watches the whole machine.

  agent_health.py health            read only table: memory, swap, CPU idle, the 5 biggest processes, TMPDIR by kind
  agent_health.py limits            the refusal line of rule 2 ("CPU idle 2% (< 20%)"), nothing when within the limits
  agent_health.py sweep [--apply] [--hours N]   this repo's own temp kinds older than N hours (default 3) and not
                                    in use by a live process: list, or remove with --apply
  agent_health.py ... --token T     (remote) the answer as ONE line "HEALTH <T> <json lines>", for a connected machine

Standard library only and one file: a connected machine gets this file's text through an Orca terminal
(remote_exec), so it needs nothing of this repo to be there. Never touches another repo's files.
Test seams: AGENT_FAKE_RAM / AGENT_FAKE_RAM_FILE (percent, shared with agent-room), AGENT_FAKE_SWAP (<used MB>/<total MB>),
AGENT_FAKE_CPU_IDLE (percent). With a fake RAM and no fake swap or CPU, those two read as unknown (never refuse).
"""

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zlib

CPU_MIN_IDLE = 20     # rule 2: refuse under this CPU idle percent
SWAP_MAX = 90         # rule 2: refuse over this swap used percent
SWEEP_HOURS = 3       # rule 3
# This repo's own temp kinds: (name prefix, owner). Everything else in TMPDIR is "other" and never touched.
KINDS = (("check-blocks-demo.", "this repo (tests/test_check_blocks_demo.py)"),
         ("auto_pipeline_", "this repo (tests/scripthelp.py, tests/scriptequiv.py)"),
         ("cloud_pack_", "this repo (tests/test_agent_cloud_pack.py)"),
         ("run2_", "this repo (tests/run2.py)"),
         ("agent_test_tools_", "this repo (tests/fasttools.py)"))


def sh(argv, timeout=30):
    try:
        return subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              universal_newlines=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def faked_ram():
    if os.environ.get("AGENT_FAKE_RAM") or os.environ.get("AGENT_FAKE_RAM_FILE"):
        return True
    return False


# ------------------------------------------------------------------ the numbers

def ram_pct():
    """Percent of RAM in use, or None."""
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
            return None
    if sys.platform == "darwin":
        m = re.search(r"free percentage:\s*(\d+)", sh(["memory_pressure"], 20))
        return 100 - int(m.group(1)) if m else None
    try:
        total = avail = 0
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable"):
                    avail = int(line.split()[1])
        return (total - avail) * 100 // total if total else None
    except (OSError, ValueError):
        return None


def swap_mb():
    """(used MB, total MB), or None."""
    fake = os.environ.get("AGENT_FAKE_SWAP", "")
    if fake:
        try:
            used, total = fake.split("/")
            return float(used), float(total)
        except ValueError:
            return None
    if faked_ram():
        return None
    if sys.platform == "darwin":
        text = sh(["sysctl", "-n", "vm.swapusage"], 10)
        vals = {}
        for key, num, unit in re.findall(r"(total|used)\s*=\s*([\d.]+)([KMG])", text):
            vals[key] = float(num) * {"K": 1 / 1024, "M": 1, "G": 1024}[unit]
        return (vals["used"], vals["total"]) if "used" in vals and "total" in vals else None
    try:
        info = {}
        with open("/proc/meminfo") as fh:
            for line in fh:
                k, _, v = line.partition(":")
                info[k] = int(v.split()[0]) // 1024 if v.split() else 0
        return float(info["SwapTotal"] - info["SwapFree"]), float(info["SwapTotal"])
    except (OSError, ValueError, KeyError):
        return None


def swap_pct():
    s = swap_mb()
    if s is None:
        return None
    return 0 if s[1] <= 0 else int(round(s[0] * 100.0 / s[1]))


def cpu_idle():
    """CPU idle percent from the SECOND sample of top (the first is the average since boot), or None."""
    fake = os.environ.get("AGENT_FAKE_CPU_IDLE", "")
    if fake:
        try:
            return int(float(fake))
        except ValueError:
            return None
    if faked_ram():
        return None
    argv = ["top", "-l", "2", "-n", "0", "-s", "1"] if sys.platform == "darwin" else ["top", "-bn2", "-d1"]
    hits = re.findall(r"([\d.]+)%?\s*(?:idle|id)\b", "\n".join(
        l for l in sh(argv, 30).splitlines() if "CPU" in l or "Cpu" in l))
    return int(round(float(hits[-1]))) if hits else None


def top_procs(n=5):
    rows = []
    for line in sh(["ps", "-Ao", "pid=,rss=,comm="], 20).splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(.*\S)", line)
        if m:
            rows.append((int(m.group(2)), int(m.group(1)), os.path.basename(m.group(3))))
    rows.sort(reverse=True)
    return [(name, pid, kb // 1024) for kb, pid, name in rows[:n]]


def limits_line(cpu=None, swap=None):
    """The one refusal line of rule 2, or "" (both within the limits, or unknown)."""
    cpu = cpu_idle() if cpu is None else cpu
    swap = swap_pct() if swap is None else swap
    why = []
    if cpu is not None and cpu < CPU_MIN_IDLE:
        why.append("CPU idle %d%% (< %d%%)" % (cpu, CPU_MIN_IDLE))
    if swap is not None and swap > SWAP_MAX:
        why.append("swap %d%% used (> %d%%)" % (swap, SWAP_MAX))
    return "; ".join(why)


# ------------------------------------------------------------------ TMPDIR

def tmp_root():
    """TMPDIR as it is now (tempfile caches its first answer)."""
    return os.environ.get("TMPDIR") or tempfile.gettempdir()


def kind_of(name):
    for prefix, owner in KINDS:
        if name.startswith(prefix):
            return prefix + "*", owner
    return name, "other"


def tree_stats(path):
    files = size = 0
    for root, dirs, names in os.walk(path):
        files += len(names)
        for n in names:
            try:
                size += os.lstat(os.path.join(root, n)).st_size
            except OSError:
                pass
    return files, size


def tmp_rows(tmpdir):
    """[(kind, owner, entries, files, bytes)] biggest file count first."""
    kinds = {}
    try:
        names = os.listdir(tmpdir)
    except OSError:
        return []
    for name in names:
        path = os.path.join(tmpdir, name)
        kind, owner = kind_of(name)
        if os.path.islink(path) or not os.path.isdir(path):
            files, size = 1, 0
            try:
                size = os.lstat(path).st_size
            except OSError:
                pass
        else:
            files, size = tree_stats(path)
        row = kinds.setdefault(kind, [owner, 0, 0, 0])
        row[1] += 1
        row[2] += files
        row[3] += size
    rows = [(k, v[0], v[1], v[2], v[3]) for k, v in kinds.items()]
    rows.sort(key=lambda r: -r[3])
    return rows


def human(nbytes):
    for unit, div in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if nbytes >= div:
            return "%.1f %s" % (nbytes / float(div), unit)
    return "%d B" % nbytes


def health_lines(tmpdir=None):
    tmpdir = tmpdir or tmp_root()
    ram, swap, cpu = ram_pct(), swap_mb(), cpu_idle()
    out = ["=== machine health (%s) ===" % os.uname()[1].split(".")[0]]
    out.append("memory in use: %s" % ("unknown" if ram is None else "%d%%" % ram))
    if swap is None:
        out.append("swap used: unknown")
    else:
        out.append("swap used: %d / %d MB (%d%%)" % (swap[0], swap[1], swap_pct()))
    out.append("CPU idle: %s" % ("unknown" if cpu is None else "%d%%" % cpu))
    out.append("biggest processes (MB):")
    for name, pid, mb in top_procs(5):
        out.append("  %-28s pid %-7d %6d MB" % (name[:28], pid, mb))
    rows = tmp_rows(tmpdir)
    out.append("TMPDIR %s: %d files" % (tmpdir, sum(r[3] for r in rows)))
    out.append("  kind | owner | entries | files | size")
    for kind, owner, entries, files, size in rows[:12]:
        out.append("  %s | %s | %d | %d | %s" % (kind, owner, entries, files, human(size)))
    line = limits_line(cpu, None if swap is None else swap_pct())
    out.append("limits: " + (line if line else "within (CPU idle >= %d%%, swap <= %d%%)" % (CPU_MIN_IDLE, SWAP_MAX)))
    return out


# ------------------------------------------------------------------ the sweep (rule 3)

def newest_mtime(path, cutoff):
    """The newest mtime in a tree, stopping at the first one newer than CUTOFF."""
    try:
        newest = os.lstat(path).st_mtime
    except OSError:
        return time.time()
    if newest > cutoff:
        return newest
    for root, dirs, names in os.walk(path):
        for n in dirs + names:
            try:
                newest = max(newest, os.lstat(os.path.join(root, n)).st_mtime)
            except OSError:
                continue
            if newest > cutoff:
                return newest
    return newest


def busy_paths():
    """Text of every process command line and the working folders of live processes."""
    text = sh(["ps", "-Ao", "args="], 20)
    cwds = [l[1:] for l in sh(["lsof", "-w", "-d", "cwd", "-Fn"], 30).splitlines() if l.startswith("n/")]
    return text, cwds


def spellings(path):
    """The path as given and as the system reports it (lsof and ps show /private/var for /var on macOS)."""
    out = [path]
    real = os.path.realpath(path)
    if real != path:
        out.append(real)
    return out


def run2_owner(path):
    """For a run2_* folder: "none" (no readable marker: owner unknown), "live" or "dead" (the marker's pid)."""
    try:
        with open(os.path.join(path, ".run2_owner")) as fh:
            pid = int(json.load(fh)["pid"])
        if pid <= 0:
            return "none"
        os.kill(pid, 0)
        return "live"
    except ProcessLookupError:
        return "dead"
    except PermissionError:
        return "live"                     # the process exists, it is not ours to signal
    except (OSError, ValueError, KeyError, TypeError):
        return "none"


def in_use(path, busy):
    text, cwds = busy
    for p in spellings(path):
        if p in text or any(c == p or c.startswith(p + "/") for c in cwds):
            return True
    return False


def sweep(tmpdir=None, apply=False, hours=SWEEP_HOURS):
    """Lines: one per removed (or, without apply, would-be removed) entry, then a count line."""
    tmpdir = tmpdir or tmp_root()
    cutoff = time.time() - hours * 3600
    busy, found, n = None, [], 0
    try:
        names = sorted(os.listdir(tmpdir))
    except OSError:
        return ["tmp sweep: %s not readable" % tmpdir]
    for name in names:
        if not any(name.startswith(p) for p, _ in KINDS):
            continue
        path = os.path.join(tmpdir, name)
        if os.path.islink(path) or not os.path.isdir(path):
            continue
        age = newest_mtime(path, cutoff)
        if age > cutoff:
            continue
        owner = run2_owner(path) if name.startswith("run2_") else ""
        if owner == "none":                  # runner-integrity: a run2 folder with no marker is not ours to remove
            found.append("kept %s (no run2 marker: owner unknown)" % name)
            continue
        if owner == "live":
            found.append("kept %s (its run2 process is alive)" % name)
            continue
        busy = busy or busy_paths()
        if in_use(path, busy):
            found.append("kept %s (in use by a live process)" % name)
            continue
        if apply:
            shutil.rmtree(path, ignore_errors=True)
        n += 1
        found.append("%s %s (%.1f h old)" % ("removed" if apply else "would remove", name, (time.time() - age) / 3600))
    found.append("tmp sweep: %s %d of this repo's temp folders older than %g h in %s"
                 % ("removed" if apply else "would remove", n, hours, tmpdir))
    return found


# ------------------------------------------------------------------ a connected machine (through Orca)

def orca_call(args, timeout=60):
    try:
        res = subprocess.run(["orca"] + args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, universal_newlines=True, timeout=timeout)
        data = json.loads(res.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if res.returncode != 0 or not isinstance(data, dict) or data.get("ok") is False:
        return None
    inner = data.get("result")
    return inner if isinstance(inner, dict) else {}


def environments():
    """The names of the connected machines (`orca environment list`), [] without Orca."""
    data = orca_call(["environment", "list", "--json"], 30) or {}
    rows = data.get("environments") or []
    return [str(r["name"]) for r in rows if isinstance(r, dict) and r.get("name")]


def project_id(root):
    for row in (orca_call(["worktree", "list", "--json"], 30) or {}).get("worktrees") or []:
        if isinstance(row, dict) and row.get("projectId") and os.path.realpath(str(row.get("path"))) == os.path.realpath(root):
            return row["projectId"]
    return None


def payload(argv, token):
    """One shell line: this file, compressed, runs with ARGV on the connected machine. Letters, digits and + / =
    only, so no quote of any shell breaks it."""
    with open(os.path.abspath(__file__), "rb") as fh:
        b64 = base64.b64encode(zlib.compress(fh.read(), 9)).decode("ascii")
    run = "import sys,zlib;exec(zlib.decompress(sys.stdin.buffer.read()))"
    return "printf %%s %s | base64 -d | python3 -c '%s' %s --token %s" % (b64, run, " ".join(argv), token)


def remote_exec(env, root, argv, wait_s=120):
    """(ok, lines): run `agent_health.py ARGV` on the connected machine ENV in a fresh shell terminal of this
    repo's main checkout there, read the one answer line back, close the terminal. ok False: lines hold one why."""
    pid = project_id(root)
    rows = (orca_call(["worktree", "list", "--environment", env, "--json"], 60) or {}).get("worktrees") or []
    main = [r for r in rows if isinstance(r, dict) and r.get("isMainWorktree") and r.get("path")
            and (not pid or r.get("projectId") == pid)]
    if not main:
        return False, ["%s: no checkout of this repo to open a shell in" % env]
    made = orca_call(["terminal", "create", "--environment", env, "--worktree", "path:" + main[0]["path"], "--json"], 60) or {}
    handle = (made.get("terminal") or {}).get("handle") or made.get("handle")
    if not handle:
        return False, ["%s: no shell terminal" % env]
    token = uuid.uuid4().hex[:12]
    try:
        sent = orca_call(["terminal", "send", "--environment", env, "--terminal", handle, "--text",
                          payload(argv, token), "--enter", "--json"], 60)
        if sent is None:
            return False, ["%s: the machine did not take the command" % env]
        end = time.time() + wait_s
        while time.time() < end:
            tail = (orca_call(["terminal", "read", "--terminal", handle, "--limit", "400", "--environment", env,
                               "--json"], 60) or {}).get("terminal", {}).get("tail") or []
            for line in tail:
                m = re.match(r"HEALTH %s (.*)$" % token, str(line).strip())
                if m:
                    try:
                        return True, json.loads(m.group(1))
                    except ValueError:
                        return False, ["%s: unreadable answer" % env]
            time.sleep(1)
        return False, ["%s: no answer in %d s" % (env, wait_s)]
    finally:
        orca_call(["terminal", "close", "--terminal", handle, "--environment", env, "--json"], 30)


# ------------------------------------------------------------------ command line

def main(argv):
    token = None
    if "--token" in argv:
        i = argv.index("--token")
        token = argv[i + 1] if i + 1 < len(argv) else ""
        argv = argv[:i] + argv[i + 2:]
    cmd = argv[0] if argv else ""
    if cmd == "health":
        lines = health_lines()
    elif cmd == "limits":
        lines = [l for l in [limits_line()] if l]
    elif cmd == "sweep":
        hours = SWEEP_HOURS
        if "--hours" in argv:
            try:
                hours = float(argv[argv.index("--hours") + 1])
            except (ValueError, IndexError):
                sys.stderr.write("agent-room.sh sweep [--apply] [--hours N]\n")
                return 2
        lines = sweep(apply="--apply" in argv, hours=hours)
    else:
        sys.stderr.write("usage: agent_health.py health | limits | sweep [--apply] [--hours N]\n")
        return 2
    if token is not None:
        sys.stdout.write("HEALTH %s %s\n" % (token, json.dumps(lines)))
    else:
        for line in lines:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
