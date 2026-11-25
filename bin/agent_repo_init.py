#!/usr/bin/env python3
"""agent_repo_init.py: write or complete agent_repo.conf (v1) in a project root.

    agent_repo_init.py <root> [--no-measure] [--cap <percent>] [--resources <agent-resources.sh>]

Called by agent-init.sh. Scans the tracked files (git ls-files) and the NAMES in .secrets/
(never their contents). Missing file: writes version 1 with every key, the edge= lines that
fit and the last 20 "# fix:" subjects. Present file: adds only the missing keys at the end,
never changes a value that is set, never adds edge= or "# fix:" lines. One stdout line per
thing done. Python 3.9, stdlib only. See requirements/check-blocks.md section 3, C4, and the
"C4 measure" line of section 11.
"""

import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import time

HEADER = ("# agent_repo.conf: this repo's own facts (check-blocks). Written by agent-init.sh, "
          "kept up to date by agents; a human may edit it, never has to.")
KEYS = ["version", "core_paths", "guard_tests", "build_cmd", "related_cmd", "full_cmd", "test_config",
        "data_scripts", "real_data"]
MEASURED = ["build_seconds", "build_mb", "guard_seconds"]
CODE_EXT = (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".dart", ".rb", ".java", ".kt",
            ".php", ".cs", ".swift", ".rs", ".sql", ".vue", ".svelte", ".sh")
TEST_DIRS = ("tests", "test", "__tests__", "spec", "specs", "e2e")
TEST_FILE = re.compile(r"(^test_.*\.py$)|(_test\.(py|go|dart|rb)$)|(\.(test|spec)\.[cm]?[jt]sx?$)|(_spec\.rb$)")
GUARD = re.compile(r"os\.walk|\.rglob\(|glob[^\n]*\*\*|git['\",\s]+ls-files|readdirSync[^\n]*recursive")
CORE_NAMES = {"auth", "permission", "permissions", "acl", "role", "roles", "money", "payment", "payments",
              "billing", "ledger", "journal", "invoice", "invoices", "migrations"}
EDGES = [
    ("empty value", None),
    ("more than one page", re.compile(r"paginat|page_?size|per_?page|next_?page|\boffset\b|\blimit\b|cursor", re.I)),
    ("deleted rows", re.compile(r"deleted_?at|is_?deleted|soft.?delete|paranoid", re.I)),
    ("invalid input", None),
    ("day boundary in local time", re.compile(
        r"timezone|\btz\b|tzinfo|zoneinfo|pytz|utcOffset|toLocale|Intl\.DateTimeFormat|dayjs|moment|date-fns"
        r"|new Date\(|Asia/|America/|Europe/|Africa/|Australia/", re.I)),
    ("double submit", re.compile(r"onsubmit|<form\b|type=.submit|\.submit\(|handlesubmit", re.I)),
    ("large size", re.compile(r"export_\w|export[A-Z]\w|csv|xlsx|upload|download|bulk", re.I)),
]


def run(args, cwd, timeout=60):
    try:
        r = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def tracked(root):
    out = run(["git", "ls-files", "-z"], root)
    return sorted(p for p in out.split("\0") if p and os.path.isfile(os.path.join(root, p)))


def read(root, rel, limit=200000):
    try:
        with open(os.path.join(root, rel), "rb") as fh:
            return fh.read(limit).decode("utf-8", "replace")
    except OSError:
        return ""


def is_test(path):
    parts = path.split("/")
    return any(p in TEST_DIRS for p in parts[:-1]) or bool(TEST_FILE.search(parts[-1]))


def py_module(path):
    return path[:-3].replace("/", ".")


def read_json(root, rel):
    import json
    try:
        data = json.loads(read(root, rel, 2000000))
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def detect_commands(root, files):
    """-> (build_cmd, related_cmd, full_cmd)"""
    names = set(files)
    has = lambda n: n in names  # noqa: E731
    if has("pubspec.yaml") and "flutter" in read(root, "pubspec.yaml"):
        return "flutter analyze", "flutter test -j 2 {tests}", "flutter test -j 2"
    if has("go.mod"):
        return "go vet ./...", "go test ./...", "go test ./..."
    if has("package.json"):
        pkg = read_json(root, "package.json")
        scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
        deps = {}
        for k in ("dependencies", "devDependencies"):
            if isinstance(pkg.get(k), dict):
                deps.update(pkg[k])
        test_script = str(scripts.get("test", ""))
        build = []
        if "lint" in scripts:
            build.append("npm run lint")
        if "typecheck" in scripts:
            build.append("npm run typecheck")
        elif has("tsconfig.json"):
            build.append("npx tsc --noEmit")
        related = full = ""
        if "vitest" in deps or "vitest" in test_script:
            related, full = "npx vitest run {tests}", "npx vitest run"
        elif "jest" in deps or "jest" in test_script:
            related, full = "npx jest --maxWorkers=2 {tests}", "npx jest --maxWorkers=2"
        elif test_script:
            full = "npm test"
        if build or related or full:
            return " && ".join(build), related, full
    pys = [f for f in files if f.endswith(".py")]
    if pys:
        dirs = set()
        for f in pys:
            top = f.split("/")[0]
            if "/" in f and not top.startswith(".") and top not in ("node_modules", "venv", "env"):
                dirs.add(top)
            elif "/" not in f:
                dirs.add(f)
        build = "python3 -m compileall -q " + " ".join(sorted(dirs))
        pytest = any(has(n) for n in ("pytest.ini", "conftest.py", "tests/conftest.py"))
        for n in ("pyproject.toml", "setup.cfg", "tox.ini", "requirements.txt", "requirements-dev.txt"):
            if not pytest and has(n) and "pytest" in read(root, n):
                pytest = True
        if not pytest:
            pytest = any(re.search(r"^\s*(import|from)\s+pytest\b", read(root, f), re.M)
                         for f in pys if is_test(f))
        if pytest:
            return build, "python3 -m pytest {tests}", "python3 -m pytest"
        if any(f.startswith("tests/") for f in pys):
            full = "python3 -m unittest discover -s tests -t ."
        else:
            full = "python3 -m unittest discover"
        return build, "python3 -m unittest {modules}", full
    return "", "", ""


def detect_guards(root, files):
    out = []
    for f in files:
        if is_test(f) and f.endswith(CODE_EXT) and GUARD.search(read(root, f)):
            out.append(f)
    return sorted(out)


def detect_core(files):
    out = []
    for f in files:
        if is_test(f):
            continue
        parts = f.split("/")
        for i, part in enumerate(parts):
            last = i == len(parts) - 1
            stem = os.path.splitext(part)[0] if last else part
            if stem.lower() in CORE_NAMES:
                glob = f if last else "/".join(parts[:i + 1]) + "/"
                if not any(glob.startswith(g) for g in out if g.endswith("/")):
                    out = [g for g in out if not (g.startswith(glob) and glob.endswith("/"))]
                    if glob not in out:
                        out.append(glob)
                break
    return sorted(out)[:30]


def detect_edges(root, files):
    code = [f for f in files if f.endswith(CODE_EXT) and not is_test(f)][:3000]
    texts = None
    out = []
    for name, rx in EDGES:
        if rx is None:
            out.append(name)
            continue
        if texts is None:
            texts = [read(root, f) for f in code]
        if any(rx.search(t) for t in texts):
            out.append(name)
    return out


def detect_real_data(root):
    d = os.path.join(root, ".secrets")
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return "none"
    for n in names:
        if os.path.isfile(os.path.join(d, n)) and re.search(r"readonly|read_only|_ro(?![a-z0-9])", n, re.I):
            return ".secrets/" + n
    return "none"


def fix_subjects(root):
    out = run(["git", "log", "--format=%s", "-n", "2000"], root)
    subs = [s.strip() for s in out.splitlines() if re.match(r"(fix|bug|hotfix)\b", s.strip(), re.I)]
    return subs[:20]


def parse(text):
    """-> dict of the keys present (last value wins)."""
    have = {}
    for line in text.splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        have[k.strip()] = v
    return have


def over_cap(resources, cap):
    """-> a 'RAM 95% over the 80% cap' string, or ''."""
    if not resources or not os.path.exists(resources):
        return ""
    script = '. "$1"; RAM_USED=$(ram_used); CPU_USED=$(cpu_used); echo "$RAM_USED $CPU_USED"'
    try:
        r = subprocess.run(["bash", "-c", script, "bash", resources], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=60)
        ram, cpu = [int(x) for x in r.stdout.decode().split()[:2]]
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    if ram > cap:
        return "RAM %d%% over the %d%% cap" % (ram, cap)
    if cpu > cap:
        return "CPU %d%% over the %d%% cap" % (cpu, cap)
    return ""


def timed(cmd, root, cap_s):
    """Run cmd once. -> (seconds, max_mb or None, hit_cap)"""
    tfile = tempfile.mktemp(prefix="agent-repo-time-")
    wrapped = ["sh", "-c", cmd]
    flag = "-l" if sys.platform == "darwin" else "-v"
    if os.path.exists("/usr/bin/time"):
        wrapped = ["/usr/bin/time", flag, "-o", tfile, "sh", "-c", cmd]
    start = time.time()
    hit = False
    proc = subprocess.Popen(wrapped, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        proc.wait(timeout=cap_s)
    except subprocess.TimeoutExpired:
        hit = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        proc.wait()
    secs = time.time() - start
    mb = None
    if not hit:
        try:
            with open(tfile) as fh:
                text = fh.read()
            m = re.search(r"(\d+)\s+maximum resident set size", text)
            if m:
                mb = int(m.group(1)) / 1048576.0
            else:
                m = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", text)
                if m:
                    mb = int(m.group(1)) / 1024.0
        except OSError:
            pass
    try:
        os.unlink(tfile)
    except OSError:
        pass
    return secs, (max(1, int(round(mb))) if mb is not None else None), hit


def module_cmd(related, guards):
    mods = " ".join(py_module(g) if g.endswith(".py") else g for g in guards)
    return related.replace("{modules}", mods).replace("{tests}", " ".join(guards))


def measure(root, have, no_measure, cap, resources, cap_s, out):
    """-> list of lines to add (keys not in have). Prints its own stdout lines into out."""
    need_build = bool(have.get("build_cmd", "").strip()) and "build_seconds" not in have
    need_mb = bool(have.get("build_cmd", "").strip()) and "build_mb" not in have and "build_seconds" not in have
    guards = [g for g in have.get("guard_tests", "").split(",") if g.strip()]
    need_guard = bool(guards) and bool(have.get("related_cmd", "").strip()) and "guard_seconds" not in have
    if no_measure or not (need_build or need_guard):
        return []
    why = over_cap(resources, cap)
    if why:
        out.append("agent_repo.conf: not measured: " + why)
        return []
    lines = []
    if need_build:
        secs, mb, hit = timed(have["build_cmd"], root, cap_s)
        if hit:
            lines += ["# heavy: hit the %d s cap" % cap_s, "build_seconds=%d" % cap_s]
            out.append("agent_repo.conf: measured build %d s (hit the cap)" % cap_s)
        else:
            n = int(math.ceil(secs))
            lines.append("build_seconds=%d" % n)
            if mb is not None and need_mb:
                lines.append("build_mb=%d" % mb)
            out.append("agent_repo.conf: measured build %d s" % n)
    if need_guard:
        secs, _mb, hit = timed(module_cmd(have["related_cmd"], guards), root, cap_s)
        if hit:
            lines += ["# heavy: hit the %d s cap" % cap_s, "guard_seconds=%d" % cap_s]
            out.append("agent_repo.conf: measured guard %d s (hit the cap)" % cap_s)
        else:
            n = int(math.ceil(secs))
            lines.append("guard_seconds=%d" % n)
            out.append("agent_repo.conf: measured guard %d s" % n)
    return lines


def main(argv):
    if not argv:
        sys.stderr.write("usage: agent_repo_init.py <root> [--no-measure] [--cap <pct>] [--resources <file>]\n")
        return 2
    root = argv[0]
    no_measure = "--no-measure" in argv
    cap, resources = 80, ""
    if "--cap" in argv:
        try:
            cap = int(argv[argv.index("--cap") + 1])
        except (IndexError, ValueError):
            pass
    if "--resources" in argv:
        try:
            resources = argv[argv.index("--resources") + 1]
        except IndexError:
            pass
    try:
        cap_s = int(os.environ.get("AGENT_INIT_MEASURE_CAP_S", "120"))
    except ValueError:
        cap_s = 120
    cap_s = max(cap_s, 1)

    path = os.path.join(root, "agent_repo.conf")
    exists = os.path.exists(path)
    old = ""
    if exists:
        with open(path) as fh:
            old = fh.read()
    have = parse(old)

    files = tracked(root)
    build, related, full = detect_commands(root, files)
    guards = detect_guards(root, files)
    values = {
        "version": "1",
        "core_paths": ",".join(detect_core(files)),
        "guard_tests": ",".join(guards),
        "build_cmd": build,
        "related_cmd": related,
        "full_cmd": full,
        "test_config": "",
        "data_scripts": "",
        "real_data": detect_real_data(root),
    }
    # one scan serves both: the keys the file lacks, then the measure of the keys it still lacks
    added = [k for k in KEYS if k not in have]
    merged = dict(have)
    for k in added:
        merged[k] = values[k]
    out = []
    extra = measure(root, merged, no_measure, cap, resources, cap_s, out)
    key_lines = ["%s=%s" % (k, values[k]) for k in added]

    if not exists:
        lines = [HEADER] + key_lines + extra
        lines += ["edge=" + e for e in detect_edges(root, files)]
        lines += ["# fix: " + s for s in fix_subjects(root)]
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        out.insert(0, "agent_repo.conf: written (version 1)")
    else:
        add_lines = key_lines + extra
        if add_lines:
            with open(path, "a") as fh:
                if old and not old.endswith("\n"):
                    fh.write("\n")
                fh.write("\n".join(add_lines) + "\n")
        for k in added:
            out.append("agent_repo.conf: added " + k)
        for l in extra:
            if not l.startswith("#"):
                out.append("agent_repo.conf: added " + l.split("=", 1)[0])
        if not add_lines:
            out.append("agent_repo.conf: kept")
    for line in out:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
