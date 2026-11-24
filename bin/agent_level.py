#!/usr/bin/env python3
"""agent_level.py - the risk level a diff needs (R8). Python 3.9, stdlib only.

Started by agent-level.sh:  agent_level.py <agent.conf path> <cwd> check --base <ref> [--declared <n>]
"""

import fnmatch
import io
import json
import os
import re
import subprocess
import sys
import tokenize

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

    def comment_shape(self, path):
        """"comment only", "whitespace only" or None: do old and new differ in comments or blanks only?"""
        family = COMMENT_FAMILIES.get(ext_of(path))
        if family is None:
            return None
        lexer, own = family
        full = os.path.join(self.top, path)
        if os.path.islink(full):
            return None
        tree = git(self.top, "ls-tree", self.mb, "--", path, check=False)
        mode = text_of(tree.stdout).split(" ", 1)[0]
        if tree.returncode != 0 or not mode or mode == "120000":
            return None
        old = git(self.top, "show", "%s:%s" % (self.mb, path), check=False)
        if old.returncode != 0:
            return None
        try:
            with open(full, "rb") as fh:
                new = fh.read()
        except OSError:
            return None
        a, b = text_of(old.stdout), text_of(new)
        if a == b:
            return None
        views = []
        for text in (a, b):
            segs = lexer(text)
            view = code_view(segs, own) if segs is not None else None
            if view is None:
                return None
            views.append(view)
        if views[0][0] != views[1][0]:
            return None
        return "comment only" if views[0][1] != views[1][1] else "whitespace only"

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


# ------------------------------------------------------------------ comment-only shape
# A lexer: lex_x(text) -> [(kind, text)] with kind "code", "str" or "comment" (joined = the input),
# or None when unsure. COMMENT_FAMILIES maps an extension to (lexer, own marker chars).

class Segs(object):
    """Builds the segment list of a text from (kind, start, end) spans in order."""

    def __init__(self, text):
        self.text, self.out, self.pos = text, [], 0

    def add(self, kind, start, end):
        if start > self.pos:
            self.out.append(("code", self.text[self.pos:start]))
        if end > start:
            self.out.append((kind, self.text[start:end]))
        self.pos = max(self.pos, end)

    def done(self):
        if self.pos < len(self.text):
            self.out.append(("code", self.text[self.pos:]))
        return self.out


def lex_py(text):
    starts, pos = [], 0
    for piece in text.split("\n"):
        starts.append(pos)
        pos += len(piece) + 1

    def off(rc):
        return starts[rc[0] - 1] + rc[1] if 0 < rc[0] <= len(starts) else len(text)

    fstart, fend = getattr(tokenize, "FSTRING_START", None), getattr(tokenize, "FSTRING_END", None)
    segs, depth, begin = Segs(text), 0, 0
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            kind = tok.type
            if kind == tokenize.ERRORTOKEN:
                return None
            if fstart is not None and kind == fstart:
                if depth == 0:
                    begin = off(tok.start)
                depth += 1
            elif fend is not None and kind == fend:
                depth -= 1
                if depth == 0:
                    segs.add("str", begin, off(tok.end))
            elif depth > 0:
                continue
            elif kind == tokenize.COMMENT:
                segs.add("comment", off(tok.start), off(tok.end))
            elif kind == tokenize.STRING:
                segs.add("str", off(tok.start), off(tok.end))
    except (tokenize.TokenError, SyntaxError, ValueError):
        return None
    return segs.done()


def escaped_end(text, k, quote):
    """Index of the closing quote from k on (backslash escapes), or -1."""
    n = len(text)
    while k < n:
        if text[k] == "\\":
            k += 2
        elif text[k] == quote:
            return k
        else:
            k += 1
    return -1


def lex_sh(text):
    n, segs, i, pend = len(text), Segs(text), 0, []
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
        elif c == "'":
            j = text.find("'", i + 1)
            if j < 0:
                return None
            segs.add("str", i, j + 1)
            i = j + 1
        elif c in "\"`" or (c == "$" and text.startswith("$'", i)):
            quote, k = (c, i + 1) if c != "$" else ("'", i + 2)
            j = escaped_end(text, k, quote)
            if j < 0:
                return None
            segs.add("str", i, j + 1)
            i = j + 1
        elif c == "#" and (i == 0 or text[i - 1] in " \t\n"):
            e = text.find("\n", i)
            e = n if e < 0 else e
            segs.add("comment", i, e)
            i = e
        elif c == "<" and text.startswith("<<", i):
            if text.startswith("<<<", i):
                i += 3
                continue
            j, strip = i + 2, False
            if j < n and text[j] == "-":
                strip, j = True, j + 1
            while j < n and text[j] in " \t":
                j += 1
            if j >= n:
                return None
            if text[j] in "'\"":
                e = text.find(text[j], j + 1)
                if e < 0:
                    return None
                word, j = text[j + 1:e], e + 1
            else:
                if text[j] == "\\":
                    j += 1
                k = j
                while k < n and text[k] not in " \t\r\n;&|<>()":
                    k += 1
                word, j = text[j:k], k
            if word == "":
                return None
            pend.append((word, strip))
            i = j
        elif c == "\n" and pend:
            p = i + 1
            for word, strip in pend:
                while True:
                    if p >= n:
                        return None
                    e = text.find("\n", p)
                    e = n if e < 0 else e
                    line = text[p:e]
                    p = e + 1
                    if (line.lstrip("\t") if strip else line) == word:
                        break
            p = min(p, n)
            segs.add("str", i, p)
            i, pend = p, []
        else:
            i += 1
    if pend:
        return None
    return segs.done()


YAML_BLOCK = re.compile(r"(?:^[ \t]*|[:\-?][ \t]+)[|>][1-9+\-]{0,2}$")


def yaml_value_start(text, pos, base, ls):
    """Does a value start at pos? (base: where the scan of this line began)"""
    k, ws = pos - 1, False
    while k >= base and text[k] in " \t":
        k, ws = k - 1, True
    if k < base:
        return base == ls
    ch = text[k]
    if ch in "[{,":
        return True
    if ch == ":":
        return ws
    if ch in "-?":
        return ws and (k == base or text[k - 1] in " \t")
    return False


def yaml_string_end(text, pos):
    """Index after the closing quote of the string opened at pos, or -1."""
    n, k = len(text), pos + 1
    if text[pos] == '"':
        j = escaped_end(text, k, '"')
        return j + 1 if j >= 0 else -1
    while k < n:
        if text[k] == "'":
            if text[k + 1:k + 2] == "'":
                k += 2
                continue
            return k + 1
        k += 1
    return -1


def lex_yaml(text):
    n, segs, i = len(text), Segs(text), 0
    while i < n:
        ls = i
        le = text.find("\n", i)
        le = n if le < 0 else le
        base, pos, code_end = ls, ls, None
        while pos < le:
            c = text[pos]
            if c == "#" and (pos == ls or text[pos - 1] in " \t"):
                segs.add("comment", pos, le)
                code_end = pos
                break
            if c in "'\"" and yaml_value_start(text, pos, base, ls):
                end = yaml_string_end(text, pos)
                if end < 0:
                    return None
                segs.add("str", pos, end)
                pos = base = end
                ls = text.rfind("\n", 0, pos) + 1
                le = text.find("\n", pos)
                le = n if le < 0 else le
                continue
            pos += 1
        if code_end is None:
            code_end = le
        nxt = le + 1
        if le < n and YAML_BLOCK.search(text[base:code_end].rstrip()):
            head = text[ls:le]
            indent = len(head) - len(head.lstrip(" \t"))
            p = nxt
            while p < n:
                e = text.find("\n", p)
                e = n if e < 0 else e
                ln = text[p:e]
                if ln.strip() != "" and len(ln) - len(ln.lstrip(" \t")) <= indent:
                    break
                p = e + 1
            p = min(p, n)
            if p > nxt:
                segs.add("str", le, p)
            nxt = max(nxt, p)
        i = nxt
    return segs.done()


def lex_conf(text):
    segs, pos = Segs(text), 0
    for line in text.split("\n"):
        st = len(line) - len(line.lstrip(" \t"))
        if line[st:st + 1] == "#":
            segs.add("comment", pos + st, pos + len(line))
        pos += len(line) + 1
    return segs.done()


SLASH_JS = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx")
SLASH_EXT = SLASH_JS + (".dart", ".java", ".kt", ".kts", ".swift", ".go", ".c", ".h", ".cc", ".cpp",
                        ".cxx", ".hpp", ".hh")
GO_IMPORT_C = re.compile(r'^[ \t]*import[ \t]*"C"', re.M)
GO_GROUP = re.compile(r"^[ \t]*import[ \t]*\(", re.M)
GO_GROUP_C = re.compile(r'^[ \t]*(?:[\w.]+[ \t]+)?"C"', re.M)


class Unsure(Exception):
    pass


def go_imports_c(text):
    if GO_IMPORT_C.search(text):
        return True
    for m in GO_GROUP.finditer(text):
        end = re.compile(r"\n[ \t]*\)").search(text, m.end())
        if GO_GROUP_C.search(text[m.end():end.start() if end else len(text)]):
            return True
    return False


def slash_triple_end(text, k, quote, esc):
    """Index of the closing triple quote from k on, or -1."""
    if not esc:
        return text.find(quote * 3, k)
    n = len(text)
    while k < n:
        if text[k] == "\\":
            k += 2
        elif text.startswith(quote * 3, k):
            return k
        else:
            k += 1
    return -1


def lex_slash(text, ext):
    if ext == ".go" and go_imports_c(text):
        return None
    n, segs = len(text), Segs(text)
    js, go = ext in SLASH_JS, ext == ".go"
    triple_dq = ext in (".java", ".swift", ".dart", ".kt", ".kts")
    triple_sq = ext == ".dart"
    esc3 = ext not in (".kt", ".kts")

    def scan(i, expr):
        depth = 0
        while i < n:
            c = text[i]
            if c == "/":
                if text.startswith("/*", i):
                    e = text.find("*/", i + 2)
                    if e < 0:
                        raise Unsure()
                    segs.add("comment", i, e + 2)
                    i = e + 2
                elif text.startswith("//", i) and (i == 0 or text[i - 1] in " \t\n"):
                    e = text.find("\n", i)
                    e = n if e < 0 else e
                    segs.add("comment", i, e)
                    i = e
                else:
                    i += 1
            elif c in "\"'":
                if text.startswith(c * 3, i) and (triple_dq if c == '"' else triple_sq):
                    e = slash_triple_end(text, i + 3, c, esc3)
                    if e < 0:
                        raise Unsure()
                    segs.add("str", i, e + 3)
                    i = e + 3
                else:
                    j = i + 1
                    while True:
                        if j >= n or text[j] == "\n":
                            raise Unsure()
                        if text[j] == "\\":
                            j += 2
                        elif text[j] == c:
                            break
                        else:
                            j += 1
                    segs.add("str", i, j + 1)
                    i = j + 1
            elif c == "`" and js:
                s, k = i, i + 1
                while True:
                    if k >= n:
                        raise Unsure()
                    if text[k] == "\\":
                        k += 2
                    elif text[k] == "`":
                        segs.add("str", s, k + 1)
                        i = k + 1
                        break
                    elif text.startswith("${", k):
                        segs.add("str", s, k + 2)
                        s = scan(k + 2, True)
                        k = s + 1
                    else:
                        k += 1
            elif c == "`" and go:
                e = text.find("`", i + 1)
                if e < 0:
                    raise Unsure()
                segs.add("str", i, e + 1)
                i = e + 1
            elif expr and c == "{":
                depth += 1
                i += 1
            elif expr and c == "}":
                if depth == 0:
                    return i
                depth -= 1
                i += 1
            else:
                i += 1
        if expr:
            raise Unsure()
        return n

    try:
        scan(0, False)
    except Unsure:
        return None
    return segs.done()


MARKUP_RAW = re.compile(r"<(script|style)(?![\w:.\-])", re.I)


def lex_markup(text):
    n, segs, i = len(text), Segs(text), 0
    while i < n:
        i = text.find("<", i)
        if i < 0:
            break
        if text.startswith("<!--", i):
            e = text.find("-->", i + 4)
            if e < 0:
                return None
            segs.add("comment", i, e + 3)
            i = e + 3
        elif text.startswith("<![CDATA[", i):
            e = text.find("]]>", i + 9)
            if e < 0:
                return None
            segs.add("str", i, e + 3)
            i = e + 3
        elif i + 1 < n and (text[i + 1].isalpha() or text[i + 1] in "/!?"):
            j = i + 1
            while True:
                if j >= n:
                    return None
                c = text[j]
                if c in "\"'":
                    e = text.find(c, j + 1)
                    if e < 0:
                        return None
                    segs.add("str", j, e + 1)
                    j = e + 1
                elif c == ">":
                    break
                else:
                    j += 1
            raw = MARKUP_RAW.match(text, i)
            i = j + 1
            if raw:
                e = text.lower().find("</" + raw.group(1).lower(), i)
                if e < 0:
                    return None
                i = e
        else:
            i += 1
    return segs.done()


COMMENT_FAMILIES = {}
for _ext in SLASH_EXT:
    COMMENT_FAMILIES[_ext] = ((lambda t, e=_ext: lex_slash(t, e)), "/*")
for _ext in (".html", ".htm", ".xml"):
    COMMENT_FAMILIES[_ext] = (lex_markup, "-")
for _ext in (".py", ".sh", ".bash", ".zsh", ".yaml", ".yml", ".conf"):
    COMMENT_FAMILIES[_ext] = ({".py": lex_py, ".yaml": lex_yaml, ".yml": lex_yaml,
                               ".conf": lex_conf}.get(_ext, lex_sh), "#")


# ---- directives (table C)

C2_WORDS = (
    "type:", "noqa", "nolint", "pylint:", "pyright:", "mypy:", "pragma", "isort:", "fmt:", "ruff:",
    "flake8:", "nosec", "cython:", "coding:", "coding=", "vim:", "vi:", "ex:", "shellcheck",
    "yamllint", "yaml-language-server", "renovate:", "eslint", "global ", "globals ", "exported ",
    "prettier-ignore", "istanbul", "c8 ", "v8 ", "biome-ignore", "deno-", "tslint:", "jshint",
    "jscs:", "swiftlint:", "ignore:", "ignore_for_file:", "go:", "+build", "<reference", "<amd-",
    "clang-format", "noinspection", "checkstyle:", "$", "webpack", "ko ", "/ko", "build:",
    "endbuild", "inject:", "endinject", "htmlmin:", "[if", "[endif", "<![endif")
C3_WORDS = ("noqa", "nolint", "pragma", "type: ignore", "eslint-", "@ts-", "-*-", "coding:", "coding=",
            "prettier-ignore", "fallthrough", "fall through", "falls through", "fallthru")
C4_AT = re.compile(r"(?:^|[\s*])@[^\W\d_]")
C5_WORDS = ("licen", "copyright", "©", "spdx")
HEAD_STRIP = "#/*-" + " \t\r\n\f\v"


def comment_body(comment):
    if comment.startswith("<!--"):
        body = comment[4:]
        return body[:-3] if body.endswith("-->") else body
    if comment.startswith("/*"):
        body = comment[2:]
        return body[:-2] if body.endswith("*/") and len(comment) >= 4 else body
    if comment.startswith("//"):
        return comment[2:]
    if comment.startswith("#"):
        return comment[1:]
    return comment


def is_directive(comment, own):
    """Table C rules C1-C5: does this comment stay in the code view?"""
    body = comment_body(comment)
    if body and not body[0].isspace() and body[0] not in own and body[0] not in "=-~":
        return True
    low = body.lower()
    head = low.lstrip(HEAD_STRIP)
    if any(head.startswith(w) for w in C2_WORDS):
        return True
    if any(w in low for w in C3_WORDS):
        return True
    if C4_AT.search(body):
        return True
    return any(w in low for w in C5_WORDS)


def code_view(segments, own):
    """(lines, plain_comments), or None when a guard (17, 18) says today's level."""
    orig, okind, out, kinds, plain = [], [], [], [], []
    for kind, text in segments:
        orig.append(text)
        if kind == "comment":
            if text.rstrip().endswith("\\"):
                return None
            okind.append("m" * len(text))
            if is_directive(text, own):
                out.append(text)
                kinds.append("c" * len(text))
            else:
                out.append(" ")
                kinds.append("c")
                plain.append(text)
        else:
            mark = "s" if kind == "str" else "c"
            okind.append(mark * len(text))
            out.append(text)
            kinds.append(mark * len(text))
    otext, okind = "".join(orig), "".join(okind)
    pos, cont = 0, False
    for line in otext.split("\n"):
        ks = okind[pos:pos + len(line)]
        if cont:
            blank = all(k == "m" or (k == "c" and ch.isspace()) for ch, k in zip(line, ks))
            if blank and not (line == "" and okind[pos:pos + 1] == "s"):
                return None
        cont = "".join(ch for ch, k in zip(line, ks) if k == "c").rstrip().endswith("\\")
        pos += len(line) + 1
    text, kinds = "".join(out), "".join(kinds)
    lines, pos = [], 0
    for line in text.split("\n"):
        inside = pos > 0 and pos < len(kinds) and kinds[pos - 1] == "s" and kinds[pos] == "s"
        if inside:
            lines.append(line)
        elif line.strip() != "":
            lines.append(line.rstrip())
        pos += len(line) + 1
    return lines, plain


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
    shape = chk.comment_shape(path)
    if shape:
        return 0, shape
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
