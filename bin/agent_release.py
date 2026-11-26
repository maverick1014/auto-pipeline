#!/usr/bin/env python3
"""Release script logic (Python 3.9, standard library only).

Builds the branch `release`: one commit per version, whose tree is exactly the
ship set of a commit of main. Uses git plumbing only; never touches HEAD, the
index or the work tree. Contract: requirements/plugin-slim.md, section 5b.
"""

import json
import os
import re
import subprocess
import sys

NAME = "agent-release.sh"
SHIP = [".claude-plugin", "hooks", "bin", "skills", "agents", "PRINCIPLES.md",
        "rules", "GLOSSARY.md", "NOTICE.md"]
VERSION_FILE = ".claude-plugin/plugin.json"
VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+)*$")


class Fail(Exception):
    def __init__(self, message, code=1):
        Exception.__init__(self, message)
        self.message = message
        self.code = code


def err(message):
    sys.stderr.write("%s: %s\n" % (NAME, message))
    sys.stderr.flush()


# ---------------------------------------------------------------- git

class Git(object):
    def __init__(self, repo):
        self.repo = repo
        self.env = dict(os.environ, LC_ALL="C")
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            self.env.pop(key, None)

    def run(self, *args, **kw):
        data = kw.get("input")
        return subprocess.run(["git", "-C", self.repo] + list(args), input=data,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env)

    def out(self, *args, **kw):
        r = self.run(*args, **kw)
        if r.returncode != 0:
            raise Fail("git %s failed: %s" % (" ".join(args), r.stderr.decode("utf-8", "replace").strip()))
        return r.stdout

    def text(self, *args, **kw):
        return self.out(*args, **kw).decode("utf-8", "replace").strip()

    def verify(self, ref):
        r = self.run("rev-parse", "--verify", "-q", ref)
        return r.stdout.decode().strip() if r.returncode == 0 else None

    def short(self, sha):
        return self.text("rev-parse", "--short", sha)


def ls_tree(git, commit, paths, recursive=False):
    """[(mode, type, blob, size, path)] for the given paths of a commit."""
    args = ["ls-tree", "-z", "-l"]
    if recursive:
        args.append("-r")
    raw = git.out(*(args + [commit, "--"] + paths))
    rows = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        mode, kind, blob, size = meta.decode().split()
        rows.append((mode, kind, blob, size, path.decode("utf-8", "surrogateescape")))
    return rows


def read_blobs(git, shas):
    """{sha: bytes} through one cat-file --batch process."""
    shas = sorted(set(shas))
    if not shas:
        return {}
    r = git.run("cat-file", "--batch", input=("\n".join(shas) + "\n").encode())
    if r.returncode != 0:
        raise Fail("git cat-file failed: %s" % r.stderr.decode("utf-8", "replace").strip())
    buf = r.stdout
    pos = 0
    result = {}
    while pos < len(buf):
        end = buf.index(b"\n", pos)
        head = buf[pos:end].decode().split()
        if len(head) != 3:
            raise Fail("git cat-file: unexpected answer %r" % buf[pos:end])
        size = int(head[2])
        result[head[0]] = buf[end + 1:end + 1 + size]
        pos = end + 1 + size + 1
    return result


# ---------------------------------------------------------------- versions

def parse_version(text):
    return tuple(int(p) for p in text.split("."))


def version_of(git, commit):
    r = git.run("show", "%s:%s" % (commit, VERSION_FILE))
    if r.returncode != 0:
        return None
    try:
        value = json.loads(r.stdout.decode("utf-8")).get("version")
    except (ValueError, AttributeError):
        return None
    if isinstance(value, str) and VERSION_RE.match(value):
        return value
    return None


# ---------------------------------------------------------------- reads check

TRAIL = r'(?:\\?")?'
BASH_RE = re.compile(
    r'(?P<root>\$(?:\{(?:CLAUDE_)?PLUGIN_ROOT\}|(?:CLAUDE_)?PLUGIN_ROOT))' + TRAIL + r'/'
    r'|(?P<self>\$\(dirname "(?:\$0|\$\{BASH_SOURCE\[0\]\})"\)|\$(?:\{SELF_DIR\}|SELF_DIR))' + TRAIL + r'/'
)
RUN_RE = re.compile(r"[A-Za-z0-9._/-]*")
PY_JOIN_RE = re.compile(
    r"os\.path\.join\(\s*(?:HERE|bin_dir|script_dir"
    r"|os\.path\.dirname\(os\.path\.abspath\(__file__\)\))\s*")
PY_BIN_RE = re.compile(r"(?<!def )_bin_path\(\s*")
PY_ARG_RE = re.compile(r"""\s*,\s*(?:"([^"\n]*)"|'([^'\n]*)')""")
PY_ANY_RE = re.compile(r"\s*,\s*[^\s)]")
PY_LIT_RE = re.compile(r"""(?:"([^"\n]*)"|'([^'\n]*)')""")


def resolve(base, path):
    """Normalise base/path: '' is the plugin root, '../x' leaves it."""
    path = path.rstrip("/")
    last = path.rsplit("/", 1)[-1]
    if last not in ("", ".", ".."):
        path = path.rstrip(".") if not last.strip(".") == "" else path
    parts = base.split("/") if base else []
    for seg in path.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts and parts[-1] != "..":
                parts.pop()
            else:
                parts.append("..")
        else:
            parts.append(seg)
    return "/".join(parts)


def scan_line(line, own):
    """Yield (base, path or None): None means a variable path (skipped).

    own is the folder of the scanned file."""
    for m in BASH_RE.finditer(line):
        base = "" if m.group("root") else own
        if m.end() < len(line) and line[m.end()] == "$":
            yield (base, None)
            continue
        run = RUN_RE.match(line, m.end()).group(0)
        after = m.end() + len(run)
        if run and not run.endswith("/") and after < len(line) and line[after] == "$":
            yield (base, None)
            continue
        yield (base, run)
    for m in PY_JOIN_RE.finditer(line):
        pos = m.end()
        lits = []
        while True:
            a = PY_ARG_RE.match(line, pos)
            if not a:
                break
            lits.append(a.group(1) if a.group(1) is not None else a.group(2))
            pos = a.end()
        if not lits:
            if PY_ANY_RE.match(line, pos):
                yield (own, None)
            continue
        yield (own, "/".join(lits))
    for m in PY_BIN_RE.finditer(line):
        a = PY_LIT_RE.match(line, m.end())
        if a:
            yield ("bin", a.group(1) if a.group(1) is not None else a.group(2))
        elif m.end() < len(line) and line[m.end()] not in ")":
            yield ("bin", None)


def reads_check(git, rows):
    """Return (ok, skipped, [(file, lineno, path)]) for the shipped text files."""
    files = set(r[4] for r in rows)
    dirs = set()
    for p in files:
        parts = p.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    wanted = [r for r in rows if r[1] == "blob" and r[0] != "120000"]
    blobs = read_blobs(git, [r[2] for r in wanted])
    ok = 0
    skipped = 0
    bad = []
    for mode, kind, blob, size, path in sorted(wanted, key=lambda r: r[4]):
        data = blobs.get(blob, b"")
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.split("\n"), 1):
            if "$" not in line and "_bin_path" not in line and "os.path.join" not in line:
                continue
            for base, rel in scan_line(line, os.path.dirname(path)):
                if rel is None:
                    skipped += 1
                    continue
                target = resolve(base, rel)
                if target == "":
                    continue
                if target == ".." or target.startswith("../"):
                    bad.append((path, lineno, target))
                elif target in files or target in dirs:
                    ok += 1
                else:
                    bad.append((path, lineno, target))
    bad.sort(key=lambda b: (b[0], b[1]))
    return ok, skipped, bad


# ---------------------------------------------------------------- main flow

def usage_error(message):
    raise Fail(message, 2)


def parse_args(argv):
    opts = {"list": False, "dry": False, "push": False, "from": "HEAD"}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--list":
            opts["list"] = True
        elif a == "--dry-run":
            opts["dry"] = True
        elif a == "--push":
            opts["push"] = True
        elif a == "--from":
            i += 1
            if i >= len(argv):
                usage_error("--from needs a ref")
            opts["from"] = argv[i]
        elif a.startswith("--from="):
            opts["from"] = a[len("--from="):]
        else:
            usage_error("unknown option %s" % a)
        i += 1
    return opts


def find_repo():
    here = os.path.dirname(os.path.realpath(__file__))
    repo = os.path.dirname(here)
    r = subprocess.run(["git", "-C", repo, "rev-parse", "--show-toplevel"],
                       env=dict(os.environ, LC_ALL="C"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    top = r.stdout.decode("utf-8", "replace").strip() if r.returncode == 0 else ""
    if not top or os.path.realpath(top) != repo:
        raise Fail("not a git checkout: %s" % repo, 2)
    return repo


def release(opts):
    repo = find_repo()
    git = Git(repo)

    ref = opts["from"]
    frm = git.verify(ref + "^{commit}")
    if not frm:
        raise Fail("unknown ref %s" % ref)
    short_from = git.short(frm)

    on_main = False
    if git.verify("refs/heads/main"):
        on_main = git.run("merge-base", "--is-ancestor", frm, "refs/heads/main").returncode == 0
    if not on_main and not opts["dry"]:
        raise Fail("%s is not on main: release only from main" % short_from)

    if opts["push"] and not opts["dry"]:
        if git.run("remote", "get-url", "origin").returncode != 0:
            raise Fail("no remote origin")
        r = git.run("fetch", "-q", "origin", "+refs/heads/release:refs/remotes/origin/release")
        if r.returncode != 0:
            msg = r.stderr.decode("utf-8", "replace")
            if "couldn't find remote ref" not in msg:
                raise Fail("git fetch origin release failed: %s" % msg.strip())
            git.run("update-ref", "-d", "refs/remotes/origin/release")

    for path in SHIP:
        if not git.text("ls-tree", frm, "--", path):
            raise Fail("%s is missing in %s" % (path, short_from))

    version = version_of(git, frm)
    if not version:
        raise Fail("no valid version in %s of %s" % (VERSION_FILE, short_from))

    tip = git.verify("refs/remotes/origin/release") or git.verify("refs/heads/release")
    tip_version = None
    if tip:
        tip_version = version_of(git, tip) or "0"

    rows = ls_tree(git, frm, SHIP, recursive=True)
    nbytes = sum(int(r[3]) for r in rows if r[3].isdigit())
    top = git.text("ls-tree", "--name-only", frm).splitlines()
    left = sorted(n for n in top if n not in SHIP)

    print("from %s version %s" % (short_from, version))
    if not on_main:
        print("warning: %s is not on main (build and --push refuse it)" % short_from)
    if tip:
        print("release tip: %s version %s" % (git.short(tip), tip_version))
    else:
        print("release tip: none")
    print("ship: %d files, %d bytes" % (len(rows), nbytes))
    print("left out: %s" % (" ".join(left) if left else "none"))

    ok, skipped, bad = reads_check(git, rows)
    print("reads check: %d ok, %d skipped (variable)" % (ok, skipped))
    sys.stdout.flush()
    if bad:
        for path, lineno, target in bad:
            err("%s:%d reads %s, which is not shipped" % (path, lineno, target))
        return 1

    listing = git.out("ls-tree", "-z", frm, "--", *SHIP)

    if tip and git.out("ls-tree", "-z", tip) == listing:
        print("release up to date: %s (%s)" % (tip_version, git.short(tip)))
        if not opts["dry"]:
            git.out("update-ref", "refs/heads/release", tip)
            if opts["push"]:
                return push_release(git)
        return 0

    if tip and parse_version(version) <= parse_version(tip_version):
        raise Fail("version %s is not higher than release %s: bump %s first"
                   % (version, tip_version, VERSION_FILE))

    if opts["dry"]:
        print("would commit release %s" % version)
        return 0

    tree = git.text("mktree", "-z", input=listing)
    message = "release %s from %s" % (version, short_from)
    args = ["commit-tree", tree, "-m", message]
    if tip:
        args += ["-p", tip]
    new = git.text(*args)
    git.out("update-ref", "refs/heads/release", new)
    print("release %s: %s (from %s)" % (version, git.short(new), short_from))
    if opts["push"]:
        return push_release(git)
    print("to publish: git push origin release")
    return 0


def push_release(git):
    local = git.verify("refs/heads/release")
    remote = git.verify("refs/remotes/origin/release")
    if local == remote:
        return 0
    r = subprocess.run(["git", "-C", git.repo, "push", "origin", "release"], env=git.env)
    return r.returncode


def main(argv):
    try:
        opts = parse_args(argv)
        if opts["list"]:
            for path in SHIP:
                print(path)
            return 0
        return release(opts)
    except Fail as exc:
        err(exc.message)
        return exc.code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
