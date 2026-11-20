#!/usr/bin/env python3
"""agent_level.py - the risk level a diff needs (R8). Python 3.9, stdlib only.

Started by agent-level.sh:  agent_level.py <agent.conf path> <cwd> check --base <ref> [--declared <n>]
"""

import fnmatch
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_conf  # noqa: E402


class Stop(Exception):
    """Usage or setup error: one stderr line, exit 2."""


# ------------------------------------------------------------------ git

def git(top, *args, **kw):
    cmd = ["git", "-C", top] + list(args)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if kw.get("check", True) and proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise Stop("git %s failed: %s" % (args[0], err[0] if err else "exit %d" % proc.returncode))
    return proc


def text_of(raw):
    return raw.decode("utf-8", "replace")


# ------------------------------------------------------------------ the path rules

LOCK_NAMES = ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "bun.lockb", "go.sum")
PUBSPEC_NAMES = ("pubspec.yaml", "pubspec.yml")
DEP_NAMES = ("go.mod", "Gemfile", "Podfile", "Pipfile", "Cargo.toml", "pyproject.toml",
             "build.gradle", "build.gradle.kts", "pom.xml")
MIGRATION_DIRS = ("migrations", "migration", "migrate", "alembic")
DEP_KEYS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies",
            "bundleDependencies", "bundledDependencies", "overrides", "resolutions")
STYLE_EXT = (".css", ".scss", ".sass", ".less", ".styl", ".pcss")
ASSET_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".ico", ".svg",
             ".woff", ".woff2", ".ttf", ".otf", ".eot")
TEXT_EXT = (".md", ".markdown", ".txt", ".rst", ".adoc")
MARKUP_EXT = (".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte")
MOVE_EXT = MARKUP_EXT + (".dart",)
TEXT_ATTRS = ("alt", "title", "placeholder", "label", "aria-label")


def ext_of(path):
    return os.path.splitext(path)[1].lower()


def builtin_l4(path):
    """The kind of the built-in L4 path, or None (package.json is judged apart)."""
    name = os.path.basename(path)
    if name in LOCK_NAMES or name.endswith(".lock"):
        return "lockfile"
    if name in PUBSPEC_NAMES:
        return "pubspec"
    if (name.startswith("requirements") and name.endswith(".txt")) or name in DEP_NAMES:
        return "dependency list"
    if any(part in MIGRATION_DIRS for part in path.split("/")[:-1]):
        return "migration"
    if (fnmatch.fnmatchcase(name, "schema.*") or fnmatch.fnmatchcase(name, "*.schema.*")
            or name.endswith(".prisma") or name.endswith(".sql")):
        return "schema"
    return None


def glob_match(glob, path):
    parts = path.split("/")
    if "/" not in glob:
        return any(fnmatch.fnmatchcase(p, glob) for p in parts)
    pat = glob.rstrip("/")
    for i in range(1, len(parts) + 1):
        if fnmatch.fnmatchcase("/".join(parts[:i]), pat):
            return True
    return False


def first_glob(globs, path):
    for glob in globs:
        if glob_match(glob, path):
            return glob
    return None


def split_globs(value):
    if value.strip() == "":
        return []
    return [item.strip() for item in value.split(",")]


# ------------------------------------------------------------------ package.json

def deps_of(blob):
    """The dependency sections of a package.json text, or None when unreadable."""
    try:
        data = json.loads(blob)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    return dict((k, data.get(k)) for k in DEP_KEYS if k in data)


def package_deps_changed(top, mb, path, status):
    if status in ("A", "D"):
        return True
    old = git(top, "show", "%s:%s" % (mb, path), check=False)
    if old.returncode != 0:
        return True
    try:
        with open(os.path.join(top, path), "rb") as fh:
            new = fh.read()
    except OSError:
        return True
    a, b = deps_of(text_of(old.stdout)), deps_of(text_of(new))
    if a is None or b is None:
        return True
    return a != b


# ------------------------------------------------------------------ the L0 shapes

COLOUR = re.compile(
    r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z_])"
    r"|\b(?:rgba?|hsla?)\([^()]*\)"
    r"|\bColor\(0x[0-9a-fA-F]{8}\)"
    r"|\bColors\.[A-Za-z]+(?:\[\d+\]|\.shade\d+)?")
IMPORT_LINE = re.compile(r"^\s*(?:import\b|from\b|export\b.*\bfrom\b|#include|@import|use\b)")
MARKUP_TEXT = re.compile(r">([^<>{}()=&|]*)<")
ATTR = re.compile(r"(?<![\w:.\-@$])([A-Za-z_@:][\w:.\-@]*)=(?=[\"'{])")
F_PREFIX = re.compile(r"(?<![\w])[rRbBuU]?[fF][rRbBuU]?$")

TOK = "\x00"


def is_import(line):
    return bool(IMPORT_LINE.match(line)) or "require(" in line or "import(" in line


def mask_text(line):
    """Markup text between > and the next <: (masked line, [texts])."""
    texts = []

    def sub(m):
        if m.group(1).strip() == "":
            return m.group(0)
        texts.append(m.group(1))
        return ">" + TOK + "T" + TOK + "<"
    return MARKUP_TEXT.sub(sub, line), texts


def mask_attrs(line):
    """Attributes name="v" name='v' name={v}, but not the text ones: None when unbalanced."""
    out, attrs, pos = [], [], 0
    while True:
        m = ATTR.search(line, pos)
        if not m:
            out.append(line[pos:])
            break
        name = m.group(1)
        start = m.end()
        if name in TEXT_ATTRS and line[start] in "\"'":
            out.append(line[pos:start])
            pos = start
            continue
        if line[start] in "\"'":
            close = line.find(line[start], start + 1)
            if close < 0:
                return None
            end = close + 1
        else:
            depth, end = 0, start
            while end < len(line):
                if line[end] == "{":
                    depth += 1
                elif line[end] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                end += 1
            if depth != 0 or end >= len(line):
                return None
            end += 1
        out.append(line[pos:m.start()])
        out.append(TOK + "A:" + name + TOK)
        attrs.append(line[m.start():end])
        pos = end
    return "".join(out), attrs


def mask_strings(line):
    """String literals: (masked, [contents]) or None for an unclosed quote or an interpolation."""
    out, strs, i = [], [], 0
    while i < len(line):
        ch = line[i]
        if ch not in "\"'`":
            out.append(ch)
            i += 1
            continue
        j = i + 1
        while j < len(line) and line[j] != ch:
            j += 2 if line[j] == "\\" else 1
        if j >= len(line):
            return None
        body = line[i + 1:j]
        if "${" in body or re.search(r"\$[A-Za-z]", body):
            return None
        if "{" in body and F_PREFIX.search(line[:i]):
            return None
        strs.append(body)
        out.append(ch + TOK + "S" + TOK + ch)
        i = j + 1
    return "".join(out), strs


def analyse(line, markup):
    """Mask one line: (masked, cols, texts, attrs, strs) or None when it is code."""
    if is_import(line):
        return None
    cols = COLOUR.findall(line)
    work = COLOUR.sub(TOK + "C" + TOK, line)
    texts, attrs = [], []
    if markup:
        work, texts = mask_text(work)
        res = mask_attrs(work)
        if res is None:
            return None
        work, attrs = res
    res = mask_strings(work)
    if res is None:
        return None
    work, strs = res
    return work, cols, texts, attrs, strs


class Checker(object):
    def __init__(self, top, mb):
        self.top, self.mb, self.seen = top, mb, {}

    def used_at_base(self, attr):
        """Is this exact attribute text in a tracked file at the merge base?"""
        variants = [attr]
        m = re.match(r"^([^=]+)=([\"'])(.*)\2$", attr, re.S)
        if m and m.group(2) not in m.group(3):
            other = "'" if m.group(2) == '"' else '"'
            variants.append("%s=%s%s%s" % (m.group(1), other, m.group(3), other))
        for text in variants:
            if text not in self.seen:
                proc = git(self.top, "grep", "-F", "-q", "-e", text, self.mb, check=False)
                self.seen[text] = proc.returncode == 0
            if self.seen[text]:
                return True
        return False

    def pair(self, old, new, markup, found):
        """Compare one removed/added pair; add reasons to found. False when it is code."""
        a, b = analyse(old, markup), analyse(new, markup)
        if a is None or b is None or a[0] != b[0]:
            return False
        if a[1] != b[1]:
            found.add("colour change")
        if a[2] != b[2] or a[4] != b[4]:
            found.add("text change")
        for x, y in zip(a[3], b[3]):
            if x != y:
                if TOK in x or TOK in y or COLOUR.search(y):
                    return False
                found.add("existing prop value" if self.used_at_base(y) else "new prop value")
        return True

    def code(self, path, hunks):
        """(level, reason) of a modified code file from its -U0 hunks."""
        ext = ext_of(path)
        markup = ext in MARKUP_EXT
        if not hunks:
            return 2, "code change"
        if os.path.basename(path) == "package.json":
            return 2, "code change"
        removed = [r for h in hunks for r in h[0]]
        added = [a for h in hunks for a in h[1]]
        if (ext in MOVE_EXT and removed and sorted(removed) == sorted(added) and any(h[0] != h[1] for h in hunks)):
            return 0, "line move (manager: check responsive)"
        found = set()
        for rem, add in hunks:
            if not rem or not add or len(rem) != len(add):
                return 2, "code change"
            for old, new in zip(rem, add):
                if not self.pair(old, new, markup, found):
                    return 2, "code change"
        order = ["text change", "colour change", "existing prop value", "new prop value"]
        reasons = [r for r in order if r in found]
        if not reasons:
            return 0, "whitespace only"
        return (1 if "new prop value" in found else 0), ", ".join(reasons)

    def hunks(self, path):
        """(hunks, binary) from git diff -U0 against the merge base."""
        proc = git(self.top, "diff", "--no-renames", "--no-color", "--no-ext-diff", "-U0",
                   self.mb, "--", path)
        hunks, cur, binary = [], None, False
        for line in text_of(proc.stdout).split("\n"):
            if cur is None:
                if line.startswith("Binary files") or line.startswith("GIT binary patch"):
                    binary = True
                if line.startswith("@@"):
                    cur = ([], [])
                    hunks.append(cur)
                continue
            if line.startswith("@@"):
                cur = ([], [])
                hunks.append(cur)
            elif line.startswith("-"):
                cur[0].append(line[1:].rstrip())
            elif line.startswith("+"):
                cur[1].append(line[1:].rstrip())
        return hunks, binary


def level_of(path, status, chk, l3, l4):
    name = os.path.basename(path)
    if name == "package.json":
        if package_deps_changed(chk.top, chk.mb, path, status):
            return 4, "built-in L4: package.json deps"
    else:
        kind = builtin_l4(path)
        if kind:
            return 4, "built-in L4: %s" % kind
    glob = first_glob(l4, path)
    if glob is not None:
        return 4, "level4_paths %s" % glob
    glob = first_glob(l3, path)
    if glob is not None:
        return 3, "level3_paths %s" % glob
    ext = ext_of(path)
    if ext in STYLE_EXT:
        return 1, "style file"
    if ext in ASSET_EXT:
        return 1, "asset file"
    if ext in TEXT_EXT:
        return 0, "text file"
    if status == "A":
        return 2, "new file"
    if status == "D":
        return 2, "deleted file"
    hunks, binary = chk.hunks(path)
    if binary:
        return 2, "binary file"
    return chk.code(path, hunks)


# ------------------------------------------------------------------ main

def parse(argv):
    if not argv or argv[0] != "check":
        raise Stop("usage: agent-level.sh check --base <ref> [--declared <0-4>]")
    base, declared, i = None, None, 1
    while i < len(argv):
        opt = argv[i]
        if opt not in ("--base", "--declared"):
            raise Stop("unknown argument: %s" % opt)
        if i + 1 >= len(argv):
            raise Stop("%s needs a value" % opt)
        value = argv[i + 1]
        if opt == "--base":
            if not value:
                raise Stop("--base needs a ref")
            base = value
        else:
            if value not in ("0", "1", "2", "3", "4"):
                raise Stop("--declared must be one of 0 1 2 3 4, got: %s" % value)
            declared = int(value)
        i += 2
    if base is None:
        raise Stop("--base <ref> is required")
    return base, declared


def run(argv):
    if len(argv) < 2:
        raise Stop("usage: agent_level.py <agent.conf> <cwd> check --base <ref> [--declared <n>]")
    conf_path, cwd = argv[0], argv[1]
    base, declared = parse(argv[2:])

    l3, l4, notes = [], [], []
    if os.path.isfile(conf_path):
        conf = agent_conf.load(conf_path)
        for key in ("level3_paths", "level4_paths"):
            msg = agent_conf.validate_value(key, conf.get(key, ""))
            if msg:
                raise Stop("agent.conf %s is invalid: %s" % (key, msg))
        l3 = split_globs(conf.get("level3_paths", ""))
        l4 = split_globs(conf.get("level4_paths", ""))
    else:
        notes.append("no agent.conf: built-in L4 paths only")

    proc = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise Stop("not in a git repo: %s" % cwd)
    top = text_of(proc.stdout).strip()
    ok = git(top, "rev-parse", "--verify", "--quiet", base + "^{commit}", check=False)
    if ok.returncode != 0:
        raise Stop("git does not know the ref: %s" % base)
    mb = text_of(git(top, "merge-base", base, "HEAD").stdout).strip()

    changed = {}
    raw = git(top, "diff", "--no-renames", "--name-status", "-z", mb).stdout.split(b"\0")
    i = 0
    while i + 1 < len(raw):
        status, path = text_of(raw[i])[:1], text_of(raw[i + 1])
        changed[path] = "A" if status == "A" else ("D" if status == "D" else "M")
        i += 2
    for item in git(top, "ls-files", "--others", "--exclude-standard", "-z").stdout.split(b"\0"):
        path = text_of(item)
        if path and not path.endswith("/") and path not in changed:
            changed[path] = "A"

    chk = Checker(top, mb)
    lines, need = [], 0
    for path in sorted(changed):
        lvl, why = level_of(path, changed[path], chk, l3, l4)
        need = max(need, lvl)
        lines.append("%s: L%d %s" % (path, lvl, why))
    if not changed:
        notes.insert(0, "no changes")
    if declared is not None:
        need = max(need, declared)

    out = ["REQUIRED LEVEL %d" % need] + lines + notes
    code = 0
    if declared is not None and declared < need:
        out.append("RAISE: declared %d, needs %d" % (declared, need))
        code = 1
    sys.stdout.write("\n".join(out) + "\n")
    return code


def main():
    try:
        return run(sys.argv[1:])
    except Stop as err:
        sys.stderr.write("agent-level: %s\n" % str(err).replace("\n", " "))
        return 2


if __name__ == "__main__":
    sys.exit(main())
