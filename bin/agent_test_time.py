#!/usr/bin/env python3
"""Run one test command per test file, N at a time, and report seconds, peak MB and exit code
per file, slowest first (the slim-test-case skill, step 1). Python 3 stdlib only, any repo."""

import argparse
import glob
import os
import re
import subprocess
import sys
import threading
import time

RAM_CAP = 80
PER_PROCESS_MB = 30
HELP = """Run one test command per test file, N at a time. Per file: wall seconds, peak MB of the
started process, exit code.

  --cmd "<command>"  required; {file} in it is replaced by the file path. Run with the shell,
                     in the current folder.
  files              positional paths, and/or --files <glob> (recursive ** allowed, repeatable).
  -j N               processes at once (default: CPU cores x 80%%, at least 1). A new process
                     starts only while memory in use + 30 MB stays under 80%% of RAM, else it waits.
  --out <tsv>        write rows seconds<TAB>peak_mb<TAB>exit<TAB>file, slowest first.
  --top N            print the N slowest rows (default 20).

Exit 0 all files passed, 1 a file failed, 2 usage error."""


def total_ram_mb():
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5).stdout
            return int(out.strip()) / 1048576
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024
    except Exception:
        pass
    return None


def ram_used_percent():
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r"free percentage:\s*(\d+)%", out)
            return 100 - int(m.group(1)) if m else None
        with open("/proc/meminfo") as fh:
            info = dict(line.split(":", 1) for line in fh)
        total = int(info["MemTotal"].split()[0])
        return round(100 * (total - int(info["MemAvailable"].split()[0])) / total)
    except Exception:
        return None


def room_for_one_more(total):
    used = ram_used_percent()
    if used is None or not total:
        return True
    return used + 100.0 * PER_PROCESS_MB / total < RAM_CAP


def run_one(cmd, path):
    start = time.time()
    proc = subprocess.Popen(cmd.replace("{file}", path), shell=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _, status, usage = os.wait4(proc.pid, 0)
    secs = time.time() - start
    proc.returncode = 0  # reaped by wait4 above
    code = os.waitstatus_to_exitcode(status)
    if code < 0:
        code = 128 - code
    peak = usage.ru_maxrss / (1048576.0 if sys.platform == "darwin" else 1024.0)
    return secs, peak, code


def main(argv):
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("-h", "--help", action="store_true")
    p.add_argument("--cmd")
    p.add_argument("--files", action="append", default=[])
    p.add_argument("-j", type=int)
    p.add_argument("--out")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("paths", nargs="*")
    try:
        args = p.parse_args(argv)
    except SystemExit:
        return 2
    if args.help:
        print(HELP.replace("%%", "%"))
        return 0
    if not args.cmd or "{file}" not in args.cmd:
        print("usage error: --cmd \"<command with {file}>\" is required", file=sys.stderr)
        return 2
    files = []
    for f in args.paths:
        if f not in files:
            files.append(f)
    for pattern in args.files:
        for f in sorted(glob.glob(pattern, recursive=True)):
            if os.path.isfile(f) and f not in files:
                files.append(f)
    if not files:
        print("usage error: no files", file=sys.stderr)
        return 2
    jobs = args.j if args.j and args.j > 0 else max(1, int((os.cpu_count() or 2) * 0.8))
    total = total_ram_mb()

    results, lock = [], threading.Lock()
    queue = list(files)
    running = [0]

    def worker():
        while True:
            with lock:
                if not queue:
                    return
            # start only while memory allows; the first running process never waits forever
            while True:
                with lock:
                    if not queue:
                        return
                    if running[0] == 0 or room_for_one_more(total):
                        path = queue.pop(0)
                        running[0] += 1
                        break
                time.sleep(1)
            res = run_one(args.cmd, path)
            with lock:
                running[0] -= 1
                results.append((res[0], res[1], res[2], path))

    wall = time.time()
    threads = [threading.Thread(target=worker) for _ in range(min(jobs, len(files)))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.time() - wall
    results.sort(key=lambda r: -r[0])
    rows = ["%.2f\t%.1f\t%d\t%s" % r for r in results]
    if args.out:
        with open(args.out, "w") as fh:
            fh.write("# seconds\tpeak_mb\texit\tfile\n")
            fh.write("".join(r + "\n" for r in rows))
    for r in rows[:max(0, args.top)]:
        print(r)
    failed = [r for r in results if r[2] != 0]
    print("files %d  failed %d  sum %.1fs  wall %.1fs" % (len(results), len(failed), sum(r[0] for r in results), wall))
    for r in failed:
        print("FAILED (exit %d): %s" % (r[2], r[3]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
