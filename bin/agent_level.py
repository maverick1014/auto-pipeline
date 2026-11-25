#!/usr/bin/env python3
"""agent_level.py - the check blocks a diff triggers (R8, requirements/check-blocks.md C2). Python 3.9, stdlib only.

Started by agent-level.sh:  agent_level.py <cwd> check --base <ref> [--scope "<globs>"] [--json] [--declared <x>]
The names and the order of the blocks come from agent_blocks.py (the one table).
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
import agent_blocks  # noqa: E402
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


def builtin_kind(path):
    """(kind, label) of a built-in path, or None (package.json is judged apart)."""
    name = os.path.basename(path)
    if name in LOCK_NAMES or name.endswith(".lock"):
        return "deps", "lockfile"
    if name in PUBSPEC_NAMES:
        return "deps", "pubspec"
    if (name.startswith("requirements") and name.endswith(".txt")) or name in DEP_NAMES:
        return "deps", "dependency list"
    if any(part in MIGRATION_DIRS for part in path.split("/")[:-1]):
        return "migration", "migration"
    if is_schema_name(name):
        return "schema", "schema"
    return None


def is_schema_name(name):
    return (fnmatch.fnmatchcase(name, "schema.*") or fnmatch.fnmatchcase(name, "*.schema.*")
            or name.endswith(".prisma") or name.endswith(".sql"))


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
        """(kinds, reason) of a modified code file from its -U0 hunks."""
        ext = ext_of(path)
        markup = ext in MARKUP_EXT
        if not hunks:
            return "code", "code change"
        if os.path.basename(path) == "package.json":
            return "code", "code change"
        removed = [r for h in hunks for r in h[0]]
        added = [a for h in hunks for a in h[1]]
        if (ext in MOVE_EXT and removed and sorted(removed) == sorted(added) and any(h[0] != h[1] for h in hunks)):
            return "style", "line move (manager: check responsive)"
        found = set()
        for rem, add in hunks:
            if not rem or not add or len(rem) != len(add):
                return "code", "code change"
            for old, new in zip(rem, add):
                if not self.pair(old, new, markup, found):
                    return "code", "code change"
        order = ["text change", "colour change", "existing prop value", "new prop value"]
        reasons = [r for r in order if r in found]
        if not reasons:
            return "text", "whitespace only"
        kinds = []
        if "text change" in found:
            kinds.append("text")
        if found - {"text change"}:
            kinds.append("style")
        return "+".join(kinds), ", ".join(reasons)

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
        try:
            if bool(int(mode, 8) & 0o111) != bool(os.stat(full).st_mode & 0o111):
                return None
        except (OSError, ValueError):
            return None
        old = git(self.top, "show", "%s:%s" % (self.mb, path), check=False)
        if old.returncode != 0:
            return None
        try:
            with open(full, "rb") as fh:
                new = fh.read()
        except OSError:
            return None
        try:
            a, b = old.stdout.decode("utf-8"), new.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if a == b:
            return None
        views, edges = [], []
        for text in (a, b):
            segs = lexer(text)
            edge = {}
            view = (code_view(segs, own, ext_of(path) in (".yaml", ".yml"), edge)
                    if segs is not None else None)
            if view is None:
                return None
            views.append(view)
            edges.append(edge)
        if views[0][0] != views[1][0]:
            return None
        e1, e2 = edges
        if e1["l1"] != e2["l1"] and (e1["l1s"] or e2["l1s"]):
            return None
        if e1["l2"] != e2["l2"] and (e1["l2d"] or e2["l2d"]):
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


PEP723 = re.compile(r"^[ \t]*#[ \t]*///[ \t]*[A-Za-z0-9-]+", re.M)


def lex_py(text):
    if PEP723.search(text):
        return None
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


def sh_dq_end(text, k, quote):
    """Index of the closing quote (" or `) from k on; $(...), ${...} and quotes nest. -1 if open."""
    n = len(text)
    while k < n:
        c = text[k]
        if c == "\\":
            k += 2
            continue
        if c == quote:
            return k
        j = k
        if c == "$" and text[k + 1:k + 2] == "(":
            j = sh_skip(text, k + 2, ")")
        elif c == "$" and text[k + 1:k + 2] == "{":
            j = sh_skip(text, k + 2, "}", quote == '"')
        elif c == "`" and quote == '"':
            j = sh_dq_end(text, k + 1, "`")
        elif quote == "`" and c == "'":
            j = text.find("'", k + 1)
        elif quote == "`" and c == '"':
            j = sh_dq_end(text, k + 1, '"')
        elif quote == "`" and c == "$" and text[k + 1:k + 2] == "'":
            j = escaped_end(text, k + 2, "'")
        if j < 0:
            return -1
        k = j + 1 if j != k else k + 1
    return -1


def sh_skip(text, k, closer, in_dq=False):
    """Index of the closer that ends a $(...) or ${...} body started before k, or -1.

    in_dq: a ${...} inside "...": a quote ' there is read differently by sh and bash, so -1."""
    n, depth = len(text), 1
    while k < n:
        c = text[k]
        j = k
        if c == "\\":
            k += 2
            continue
        if in_dq and closer == "}" and (c == "'" or (c == "$" and text[k + 1:k + 2] == "'")):
            return -1
        if c == "'":
            j = text.find("'", k + 1)
        elif c == '"' or c == "`":
            j = sh_dq_end(text, k + 1, c)
        elif c == "$" and text[k + 1:k + 2] == "'":
            j = escaped_end(text, k + 2, "'")
        elif c == "$" and text[k + 1:k + 2] == "(":
            j = sh_skip(text, k + 2, ")")
        elif c == "$" and text[k + 1:k + 2] == "{":
            j = sh_skip(text, k + 2, "}", in_dq and closer == "}")
        elif closer == ")" and c == "(":
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return k
        if j < 0:
            return -1
        k = j + 1 if j != k else k + 1
    return -1


def lex_zsh(text):
    return lex_sh(text, True)


def lex_sh(text, zsh=False):
    n, segs, i, pend, esc = len(text), Segs(text), 0, [], -1
    starters = ";&|)<>" if zsh else ";&|()<>"
    while i < n:
        c = text[i]
        if c == "\\":
            esc = i + 1
            i += 2
        elif c == "'":
            j = text.find("'", i + 1)
            if j < 0:
                return None
            segs.add("str", i, j + 1)
            i = j + 1
        elif c in "\"`" or (c == "$" and text.startswith("$'", i)):
            j = escaped_end(text, i + 2, "'") if c == "$" else sh_dq_end(text, i + 1, c)
            if j < 0:
                return None
            segs.add("str", i, j + 1)
            i = j + 1
        elif c == "$" and text.startswith("${", i):
            j = sh_skip(text, i + 2, "}")
            if j < 0:
                return None
            segs.add("str", i, j + 1)
            i = j + 1
        elif c == "$" and text.startswith("$((", i):
            j = sh_skip(text, i + 2, ")")
            if j < 0:
                return None
            segs.add("str", i, j + 1)
            i = j + 1
        elif c == "#" and (i == 0 or text[i - 1] == "\n" or (text[i - 1] in " \t" + starters and i - 1 != esc)):
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


YAML_BLOCK = re.compile(r"(?:^[ \t]*|[:\-?][ \t]+)(?:[!&][^ \t]*[ \t]+)*[|>][1-9+\-]{0,2}$")


def yaml_value_start(text, pos, base, ls):
    """Does a value start at pos? 2 after a flow char [ { , (that string must close on its line)."""
    k, ws = pos - 1, False
    while True:
        while k >= base and text[k] in " \t":
            k, ws = k - 1, True
        if k < base:
            return base == ls
        r = k
        while r >= base and text[r] not in " \t":
            r -= 1
        t = r + 1
        while t <= k and text[t] in "[{,":
            t += 1
        if ws and t <= k and text[t] in "!&":
            k, ws = (t - 1 if t > r + 1 else r), False
            continue
        break
    ch = text[k]
    if ch in "[{,":
        return 2
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
            start = yaml_value_start(text, pos, base, ls) if c in "'\"" else False
            if start:
                end = yaml_string_end(text, pos)
                if end < 0 or (start == 2 and "\n" in text[pos:end]):
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


JAVA_UNICODE = re.compile(r"\\u+[0-9a-fA-F]{4}")
SWIFT_RAW = re.compile(r'#"')
CPP_RAW = re.compile(r'(?<![A-Za-z0-9_$])(?:u8|u|U|L)?R"')
GO_OUTPUT = re.compile(r"//[ \t]*(?:unordered[ \t]+)?output:", re.I)


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
    if ext == ".java" and JAVA_UNICODE.search(text):
        return None
    if ext == ".swift" and SWIFT_RAW.search(text):
        return None
    if ext in (".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh") and CPP_RAW.search(text):
        return None
    if ext == ".go" and GO_OUTPUT.search(text):
        return None
    n, segs = len(text), Segs(text)
    js, go = ext in SLASH_JS, ext == ".go"
    triple_dq = ext in (".java", ".swift", ".dart", ".kt", ".kts")
    triple_sq = ext == ".dart"
    esc3 = ext not in (".kt", ".kts")

    lone = [-1]
    guard = js or ext == ".swift"

    def unsure_comment(i, e):
        body = text[i:e]
        if js and ("</" in body or "/>" in body or "{" in body or "}" in body):
            raise Unsure()
        if guard and lone[0] >= text.rfind("\n", 0, i) + 1 and lone[0] >= 0:
            raise Unsure()

    def lone_on_line(i):
        return guard and lone[0] >= 0 and lone[0] >= text.rfind("\n", 0, i) + 1

    def scan(i, expr):
        depth = 0
        while i < n:
            c = text[i]
            if c == "/":
                if text.startswith("/*", i):
                    e = text.find("*/", i + 2)
                    if e < 0:
                        raise Unsure()
                    unsure_comment(i, e + 2)
                    segs.add("comment", i, e + 2)
                    i = e + 2
                elif text.startswith("//", i) and (i == 0 or text[i - 1] in " \t\n"):
                    e = text.find("\n", i)
                    e = n if e < 0 else e
                    unsure_comment(i, e)
                    segs.add("comment", i, e)
                    i = e
                else:
                    if text[i + 1:i + 2] not in ("/", "*") and text[i - 1:i] not in ("/", "*"):
                        lone[0] = i
                    i += 1
            elif (c == "r" and ext == ".dart" and text[i + 1:i + 2] in ("'", '"') and
                  (i == 0 or not (text[i - 1].isalnum() or text[i - 1] in "_$"))):
                q = text[i + 1]
                if text.startswith(q * 3, i + 1):
                    e = text.find(q * 3, i + 4)
                else:
                    e = text.find(q, i + 2)
                    nl = text.find("\n", i + 2)
                    if 0 <= nl < e:
                        e = -1
                if e < 0:
                    raise Unsure()
                e += 3 if text.startswith(q * 3, i + 1) else 1
                segs.add("str", i, e)
                i = e
            elif c in "\"'":
                if text.startswith(c * 3, i) and (triple_dq if c == '"' else triple_sq):
                    e = slash_triple_end(text, i + 3, c, esc3)
                    if e < 0:
                        raise Unsure()
                    if lone_on_line(i) and "\n" in text[i:e + 3]:
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
                s, k, was_lone = i, i + 1, lone_on_line(i)
                while True:
                    if k >= n:
                        raise Unsure()
                    if text[k] == "\\":
                        k += 2
                    elif text[k] == "`":
                        if was_lone and "\n" in text[i:k + 1]:
                            raise Unsure()
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


MARKUP_RAW = re.compile(r"<(script|style|textarea|title|noscript|xmp|iframe|noembed|noframes|plaintext)(?![\w:.\-])", re.I)


def lex_markup(text):
    n, segs, i = len(text), Segs(text), 0
    while i < n:
        i = text.find("<", i)
        if i < 0:
            break
        if text.startswith("<!--", i):
            if text.startswith("<!-->", i):
                e = i + 5
            elif text.startswith("<!--->", i):
                e = i + 6
            else:
                ends = [x for x in (text.find("-->", i + 4), text.find("--!>", i + 4)) if x >= 0]
                if not ends:
                    return None
                m = min(ends)
                e = m + (3 if text.startswith("-->", m) else 4)
            segs.add("comment", i, e)
            i = e
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
            if raw and raw.group(1).lower() == "plaintext":
                break
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
    COMMENT_FAMILIES[_ext] = ({".py": lex_py, ".yaml": lex_yaml, ".yml": lex_yaml, ".conf": lex_conf,
                               ".zsh": lex_zsh}.get(_ext, lex_sh), "#")


# ---- directives (table C)

C2_WORDS = (
    "type:", "noqa", "nolint", "pylint:", "pyright:", "mypy:", "pragma", "isort:", "fmt:", "ruff:",
    "flake8:", "nosec", "cython:", "coding:", "coding=", "vim:", "vi:", "ex:", "shellcheck",
    "yamllint", "yaml-language-server", "renovate:", "eslint", "global ", "globals ", "exported ",
    "prettier-ignore", "istanbul", "c8 ", "v8 ", "biome-ignore", "deno-", "tslint:", "jshint",
    "jscs:", "swiftlint:", "ignore:", "ignore_for_file:", "go:", "+build", "<reference", "<amd-",
    "clang-format", "noinspection", "checkstyle:", "$", "webpack", "ko ", "/ko", "build:",
    "endbuild", "inject:", "endinject", "htmlmin:", "[if", "[endif", "<![endif", "swift-tools-version")
C3_WORDS = ("noqa", "nolint", "pragma", "type: ignore", "eslint-", "@ts-", "-*-", "coding:", "coding=",
            "prettier-ignore", "fallthrough", "fall through", "falls through", "fallthru")
C4_AT = re.compile(r"(?:^|[\s*])@[^\W\d_]")
C5_WORDS = ("licen", "copyright", "©", "spdx")
TEMPLATE_MARKS = ("{{", "{%", "{#", "<%", "${", "<?")
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
    if any(w in comment for w in TEMPLATE_MARKS):
        return True
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


def sticky_ok(text, own, first):
    """May the line after this whole-line directive comment be pinned (f12)?"""
    low = comment_body(text).lower()
    head = low.lstrip(HEAD_STRIP)
    if first and text.startswith("#!"):
        return False
    if any(w in low for w in C5_WORDS) or "coding:" in low or "coding=" in low or "-*-" in low:
        return False
    return not head.startswith(("vim:", "vi:", "ex:"))


ODD_BREAKS = re.compile("[\u0085\u2028\u2029]|\r(?!\n)")


def code_view(segments, own, keep_blank=False, edge=None):
    """(lines, plain_comments), or None when a guard (17, 18, f6) says today's level.

    plain_comments: (code-view lines before it, text). edge (a dict) gets the first lines for f2."""
    otext = "".join(t for _, t in segments)
    # pass 1: kinds per original character, the sticky lines (f12)
    okind, info, sticky, off, ln = [], [], set(), 0, 0
    for kind, text in segments:
        if kind == "comment":
            if text.rstrip().endswith("\\"):
                return None
            for m in ODD_BREAKS.finditer(text):
                if m.group() == "\r" and otext[off + m.end():off + m.end() + 1] == "\n":
                    continue
                return None
            direct = is_directive(text, own)
            okind.append(("m" if direct else "p") * len(text))
            if direct and sticky_ok(text, own, ln == 0):
                end = off + len(text)
                nl = otext.find("\n", end)
                rest = otext[end:len(otext) if nl < 0 else nl]
                if rest.strip() == "" and otext[otext.rfind("\n", 0, off) + 1:off].strip() == "":
                    sticky.add(ln + text.count("\n") + 1)
        else:
            direct = False
            okind.append(("s" if kind == "str" else "c") * len(text))
        info.append((kind, text, direct, ln))
        off += len(text)
        ln += text.count("\n")
    okind = "".join(okind)
    olines = otext.split("\n")
    # guard 17: a comment or blank line right after a code line ending in a backslash
    pos, cont = 0, False
    for line in olines:
        ks = okind[pos:pos + len(line)]
        if cont:
            blank = all(k in "mp" or (k == "c" and ch.isspace()) for ch, k in zip(line, ks))
            if blank and not (line == "" and okind[pos:pos + 1] == "s"):
                return None
        cont = "".join(ch for ch, k in zip(line, ks) if k == "c").rstrip().endswith("\\")
        pos += len(line) + 1
    if edge is not None:
        ks = okind[:len(olines[0])]
        edge["l1s"] = "m" in ks or olines[0].lstrip().lower().startswith(("<?", "<!doctype"))
        second = olines[1] if len(olines) > 1 else ""
        start = len(olines[0]) + 1
        edge["l2d"] = "m" in okind[start:start + len(second)]
    # pass 2: the code text, a plain comment gone but its line breaks kept (f7)
    out, kinds, plain = [], [], []
    for kind, text, direct, ln in info:
        if kind == "comment" and not direct and ln not in sticky:
            breaks = text.count("\n")
            out.append("\n" * breaks if breaks else " ")
            kinds.append("c" * max(breaks, 1))
            plain.append((ln, text))
        else:
            out.append(text)
            kinds.append(("s" if kind == "str" else "c") * len(text))
    text, kinds = "".join(out), "".join(kinds)
    pieces = text.split("\n")
    if edge is not None:
        edge["l1"] = pieces[0].rstrip()
        edge["l2"] = pieces[1].rstrip() if len(pieces) > 1 else ""
    lines, before, pos = [], [], 0
    for idx, line in enumerate(pieces):
        before.append(len(lines))
        last = idx == len(pieces) - 1
        inside = pos > 0 and pos < len(kinds) and kinds[pos - 1] == "s" and kinds[pos] == "s"
        if last and line == "":
            pass
        elif idx in sticky or inside:
            lines.append(line)
        elif line.strip() != "":
            lines.append(line.rstrip())
        elif keep_blank and idx < len(olines) and olines[idx].strip() == "":
            lines.append("")
        pos += len(line) + 1
    return lines, [(before[min(ln, len(before) - 1)], t) for ln, t in plain]




# ------------------------------------------------------------------ the kind of a file

CODE_EXT = SLASH_EXT + (".py", ".rb", ".php", ".sh", ".bash", ".zsh", ".cs", ".rs", ".scala", ".ex", ".exs",
                        ".lua", ".pl", ".vue", ".svelte", ".m", ".mm")
CI_NAMES = (".gitlab-ci.yml", ".travis.yml", "Jenkinsfile", "azure-pipelines.yml", "bitbucket-pipelines.yml",
            "pytest.ini", "tox.ini", "conftest.py", "dart_test.yaml")
CI_GLOBS = ("jest.config.*", "vitest.config.*", "karma.conf.*", "playwright.config.*", "cypress.config.*",
            ".mocharc*", "phpunit.xml*")
SCRIPT_DIRS = ("scripts", "script", "oneoff", "datafix", "data-fix", "backfill")
DATA_WRITE = re.compile(r"\bUPDATE\b.*\bSET\b|\bDELETE\s+FROM\b|\bINSERT\s+INTO\b|\bTRUNCATE\b", re.I)
RULE_NAMES = ("PRINCIPLES.md", "CLAUDE.md", "AGENTS.md")
HEADING = re.compile(r"^([A-Z]\d+)\. ")


def is_ci(path):
    name = os.path.basename(path)
    if name in CI_NAMES or any(fnmatch.fnmatchcase(name, g) for g in CI_GLOBS):
        return True
    parts = path.split("/")
    return (parts[0] == ".github" and len(parts) > 2 and parts[1] == "workflows") or \
        (parts[0] == ".circleci" and len(parts) > 1)


def is_rule(path):
    if os.path.basename(path) in RULE_NAMES:
        return True
    parts = path.split("/")
    if parts[0] == "skills" and len(parts) > 1:
        return True
    if parts[0] == "agents" and len(parts) == 2 and parts[1].endswith(".md"):
        return True
    return parts[0] == ".claude" and len(parts) > 2 and parts[1] in ("skills", "agents")


class Repo(object):
    """Facts of one run: the repo file, the working-tree files, the changed lines of each file."""

    def __init__(self, top, mb, conf):
        self.top, self.mb, self.conf = top, mb, conf
        self.chk = Checker(top, mb)
        self._changes, self._content, self._files = {}, {}, None

    def globs(self, key):
        return split_globs(self.conf.get(key, ""))

    def content(self, path):
        if path not in self._content:
            try:
                with open(os.path.join(self.top, path), "rb") as fh:
                    raw = fh.read()
                self._content[path] = None if b"\0" in raw[:4096] else text_of(raw)
            except OSError:
                self._content[path] = None
        return self._content[path]

    def old_content(self, path):
        proc = git(self.top, "show", "%s:%s" % (self.mb, path), check=False)
        return text_of(proc.stdout) if proc.returncode == 0 and b"\0" not in proc.stdout[:4096] else None

    def files(self):
        """Every file of the working tree (tracked and untracked, not ignored) that still exists."""
        if self._files is None:
            names = set()
            for args in (("ls-files", "-z"), ("ls-files", "--others", "--exclude-standard", "-z")):
                for item in git(self.top, *args).stdout.split(b"\0"):
                    item = text_of(item)
                    if item and os.path.isfile(os.path.join(self.top, item)):
                        names.add(item)
            self._files = sorted(names)
        return self._files

    def changes(self, path, status):
        """([(old line no, text)], [(new line no, text)]) of the file against the merge base."""
        key = (path, status)
        if key in self._changes:
            return self._changes[key]
        removed, added = [], []
        if status == "A":
            body = self.content(path)
            added = [(n + 1, t) for n, t in enumerate((body or "").split("\n")[:-1] if body and body.endswith("\n")
                                                      else (body or "").split("\n"))] if body else []
        else:
            proc = git(self.top, "diff", "--no-renames", "--no-color", "--no-ext-diff", "-U0", self.mb, "--", path)
            old_no = new_no = 0
            for line in text_of(proc.stdout).split("\n"):
                m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                if m:
                    old_no, new_no = int(m.group(1)), int(m.group(3))
                    continue
                if old_no == 0 and new_no == 0:
                    continue
                if line.startswith("-"):
                    removed.append((old_no, line[1:]))
                    old_no += 1
                elif line.startswith("+"):
                    added.append((new_no, line[1:]))
                    new_no += 1
        self._changes[key] = (removed, added)
        return removed, added

    def kinds(self, path, status):
        """(kinds joined by +, reason) of one changed file."""
        kinds, why = self._kinds(path, status)
        if first_glob(self.globs("core_paths"), path) is not None:
            kinds += "+core"
        return kinds, why

    def _kinds(self, path, status):
        name, ext = os.path.basename(path), ext_of(path)
        if name == "package.json":
            if package_deps_changed(self.top, self.mb, path, status):
                return "deps", "built-in: package.json deps"
        else:
            built = builtin_kind(path)
            if built and built[0] == "deps":
                return "deps", "built-in: %s" % built[1]
        glob = first_glob(self.globs("test_config"), path)
        if glob is not None:
            return "ci", "test_config %s" % glob
        if is_ci(path):
            return "ci", "built-in: ci"
        built = builtin_kind(path)
        if built and built[0] == "migration":
            kinds = ["migration"]
            if is_schema_name(name):
                kinds.append("schema")
            if ext in CODE_EXT:
                kinds.append("code")
            return "+".join(kinds), "built-in: migration"
        if built:
            return built[0], "built-in: %s" % built[1]
        glob = first_glob(self.globs("data_scripts"), path)
        if glob is not None:
            return "data-script", "data_scripts %s" % glob
        if (ext not in TEXT_EXT and ext not in ASSET_EXT and status != "D"
                and any(part in SCRIPT_DIRS for part in path.split("/")[:-1])):
            if any(DATA_WRITE.search(t) for _, t in self.changes(path, status)[1]):
                return "data-script", "built-in: data-script"
        if is_rule(path):
            return "rule", "rule file"
        if ext in TEXT_EXT:
            return "text", "text file"
        if ext in STYLE_EXT:
            return "style", "style file"
        if ext in ASSET_EXT:
            return "asset", "asset file"
        if ext in MARKUP_EXT:
            return self.component(path, status)
        if status == "A":
            return "code", "new file"
        if status == "D":
            return "code", "deleted file"
        hunks, binary = self.chk.hunks(path)
        if binary:
            return "code", "binary file"
        shape = self.chk.comment_shape(path)
        if shape:
            return "text", shape
        return self.chk.code(path, hunks)

    def component(self, path, status):
        if status == "A":
            return "code", "new component file"
        if status == "D":
            return "code", "deleted component file"
        hunks, binary = self.chk.hunks(path)
        if not binary:
            shape = self.chk.comment_shape(path)
            if shape:
                return "text", shape
            kinds, why = self.chk.code(path, hunks)
            if kinds != "code":
                return kinds, why
        return "code", "component file"


# ------------------------------------------------------------------ DIFF SCAN

TEST_DIRS = ("tests", "test", "__tests__", "spec", "e2e")
TEST_NAME = re.compile(r"^(test_.*|.*_test\..*|.*\.test\..*|.*\.spec\..*|.*Tests?\.[A-Za-z]+|.*_spec\..*)$")
SKIP_MARKS = ("unittest.skip", "skipTest(", "pytest.mark.skip", "xit(", "it.skip(", "describe.skip(",
              "test.skip(", "xdescribe(", "@Disabled")
SKIP_TRUE = re.compile(r"\bskip:\s*true\b")
DEBUG_MARKS = (("console.log(", re.compile(r"console\.log\(")), ("debugger", re.compile(r"\bdebugger\b")),
               ("breakpoint()", re.compile(r"\bbreakpoint\(\)")), ("pdb.set_trace", re.compile(r"pdb\.set_trace")),
               ("binding.pry", re.compile(r"binding\.pry")), ("var_dump(", re.compile(r"\bvar_dump\(")))
SECRETS = (("aws access key", re.compile(r"\bA(?:KIA|SIA)[0-9A-Z]{16}\b")),
           ("private key", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
           ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
           ("slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
           ("google api key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
           ("api key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
           ("hardcoded credential", re.compile(
               r"""(?i)\b(?:password|passwd|secret|token|api[_-]?key|private[_-]?key)\w*["']?\s*[:=]\s*["'][^"'\s]{8,}["']""")))
TEST_DEF = (re.compile(r"^\s*(?:async\s+)?def\s+(test\w*)\s*\("),
            re.compile(r"""\b(?:it|test|describe)(?:\.\w+)?\s*\(\s*(['"`])(.+?)\1"""))


def is_test_file(path):
    return bool(TEST_NAME.match(os.path.basename(path))) and ext_of(path) in CODE_EXT


def in_test_place(path):
    return is_test_file(path) or any(part in TEST_DIRS for part in path.split("/")[:-1])


def secret_file(path):
    name = os.path.basename(path)
    return (name.startswith(".env") or path.startswith(".secrets/") or "/.secrets/" in path
            or name.endswith(".pem") or name.startswith("id_rsa"))


def test_names(lines):
    names = set()
    for _, text in lines:
        m = TEST_DEF[0].match(text)
        if m:
            names.add(m.group(1))
            continue
        m = TEST_DEF[1].search(text)
        if m:
            names.add(m.group(2))
    return names


def code_lines(repo, path):
    """{line no: the line with strings and comments blanked} of the file, or None without a lexer."""
    family = COMMENT_FAMILIES.get(ext_of(path))
    if family is None:
        return None
    body = repo.content(path)
    if not body:
        return None
    try:
        segs = family[0](body)
    except Exception:
        return None
    if segs is None:
        return None
    text = "".join(t if k == "code" else re.sub(r"[^\n]", " ", t) for k, t in segs)
    if len(text) != len(body):
        return None
    return dict((n + 1, t) for n, t in enumerate(text.split("\n")))


def diff_scan(repo, changed, kinds, scope):
    out = []
    for path in sorted(changed):
        status = changed[path]
        if scope and first_glob(scope, path) is None:
            out.append("outside scope: %s" % path)
        removed, added = repo.changes(path, status)
        if is_test_file(path):
            if status == "D":
                out.append("deleted test: %s" % path)
            else:
                gone = test_names(removed) - test_names(added)
                for name in sorted(gone):
                    out.append("removed test: %s: %s" % (path, name))
            masked = code_lines(repo, path) if status != "D" else None
            for no, text in added:
                text = (masked or {}).get(no, text)
                if any(m in text for m in SKIP_MARKS) or SKIP_TRUE.search(text):
                    out.append("skipped test: %s:%d" % (path, no))
        if status != "D" and secret_file(path):
            out.append("secret file: %s" % path)
        if status != "D":
            for no, text in added:
                for kind, rx in SECRETS:
                    if rx.search(text):
                        out.append("secret: %s:%d %s" % (path, no, kind))
                        break
        if status != "D" and not in_test_place(path) and "code" in kinds[path][0].split("+"):
            masked = code_lines(repo, path)
            for no, text in added:
                text = (masked or {}).get(no, text)
                for mark, rx in DEBUG_MARKS:
                    if rx.search(text):
                        out.append("debug leftover: %s:%d %s" % (path, no, mark))
    return out


# ------------------------------------------------------------------ RELATED TESTS and groups

def needle(text):
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(text) + r"(?![A-Za-z0-9_])")


def name_needles(path):
    name = os.path.basename(path)
    stem = os.path.splitext(name)[0]
    out = [needle(path), needle(name)]
    if len(stem) >= 4:
        out.append(needle(stem))
    return out


def section_codes(repo, path, status):
    """The section codes (R8, W4 ...) of the headings above each changed line of a rule file."""
    codes = set()

    def nearest(lines, no):
        for i in range(min(no, len(lines)) - 1, -1, -1):
            m = HEADING.match(lines[i])
            if m:
                return m.group(1)
        return None

    new = repo.content(path) if status != "D" else None
    old = repo.old_content(path) if status != "A" else None
    if status in ("A", "D"):
        for body in (new, old):
            for line in (body or "").split("\n"):
                m = HEADING.match(line)
                if m:
                    codes.add(m.group(1))
        return codes
    removed, added = repo.changes(path, status)
    for lines, items, body in ((new, added, new), (old, removed, old)):
        if body is None:
            continue
        rows = body.split("\n")
        for no, _ in items:
            code = nearest(rows, no)
            if code:
                codes.add(code)
    return codes


def changed_strings(repo, path, status):
    """Quoted or markup texts of 4 chars or more that differ between old and new lines of a file."""
    removed, added = repo.changes(path, status)

    def strings(items):
        got = set()
        for _, text in items:
            for m in re.finditer(r"\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)'|`([^`]*)`", text):
                got.add(m.group(1) or m.group(2) or m.group(3) or "")
            for m in MARKUP_TEXT.finditer(text):
                got.add(m.group(1).strip())
        return set(s for s in got if len(s) >= 4)
    a, b = strings(removed), strings(added)
    return sorted(a ^ b)


def fill(cmd, tests):
    """The related_cmd with {tests} and {modules} filled; the paths are added when it has no slot."""
    paths = " ".join(tests)
    modules = " ".join(os.path.splitext(t)[0].replace("/", ".") for t in tests)
    if "{tests}" not in cmd and "{modules}" not in cmd:
        return (cmd + " " + paths).strip()
    return cmd.replace("{tests}", paths).replace("{modules}", modules)


def related_tests(repo, changed, kinds):
    tests = [p for p in repo.files() if is_test_file(p)]
    found = set()
    for path in changed:
        ks = set(kinds[path][0].split("+"))
        if changed[path] != "D" and is_test_file(path) and ks & {"code", "style", "text"}:
            found.add(path)
    for path in sorted(changed):
        status = changed[path]
        ks = set(kinds[path][0].split("+")) - {"core"}
        if not ks & {"code", "style", "text", "rule"} or is_test_file(path):
            continue
        if "rule" in ks:
            codes = sorted(section_codes(repo, path, status))
            needles = [needle(path)] + [needle(c) for c in codes]
            for t in tests:
                body = repo.content(t) or ""
                if any(n.search(body) for n in needles):
                    found.add(t)
            continue
        if ks == {"style"}:
            stem = os.path.splitext(os.path.basename(path))[0]
            for t in tests:
                if stem and stem in os.path.basename(t):
                    found.add(t)
            continue
        needles = name_needles(path)
        strings = []
        if "text" in ks and ext_of(path) not in TEXT_EXT:
            strings = changed_strings(repo, path, status)
        for t in tests:
            body = repo.content(t) or ""
            if any(n.search(body) for n in needles) or any(s in body for s in strings):
                found.add(t)
    return sorted(found)


def groups_for(repo, changed, kinds):
    """[(module, cmd)] of the group.<module> keys whose folder holds a file that names a changed code file."""
    out = []
    code_files = [p for p in sorted(changed) if "code" in kinds[p][0].split("+")]
    if not code_files:
        return out
    for module, cmd in repo.conf.get("groups", []):
        prefix = module.rstrip("/") + "/"
        members = [p for p in repo.files() if p.startswith(prefix) and ext_of(p) in CODE_EXT + MARKUP_EXT]
        hit = False
        for path in code_files:
            needles = name_needles(path)
            for m in members:
                if m == path:
                    continue
                body = repo.content(m) or ""
                if any(n.search(body) for n in needles):
                    hit = True
                    break
            if hit:
                break
        if hit:
            out.append((module, cmd))
    return out


# ------------------------------------------------------------------ DB CHECK sign

SIGN_WORDS = re.compile(
    r"\b(?:UPDATE|DELETE|DROP|TRUNCATE|RENAME)\b|\bALTER\s+COLUMN\b|remove_column|drop_table|rename_column"
    r"|change_column|RemoveField|DeleteModel|AlterField|RenameField|RunSQL|RunPython|op\.drop_|op\.alter_column"
    r"|dropColumn|dropTable|renameColumn", re.I)


def db_sign(repo, path, status):
    """Why this migration or schema file needs the owner's sign, or None (adds only)."""
    removed, added = repo.changes(path, status)
    if any(t.strip() for _, t in removed):
        return "removed line in %s" % path
    for _, text in added:
        m = SIGN_WORDS.search(text)
        if m:
            return "%s in %s" % (m.group(0).upper() if m.group(0).isalpha() else m.group(0), path)
    return None


# ------------------------------------------------------------------ main

USAGE = 'usage: agent-level.sh check --base <ref> [--scope "<globs>"] [--json] [--declared <x>]'
BRIEF_LINE = "BRIEF PICKS: %s (dispatch picks them from the brief)" % ", ".join(agent_blocks.BRIEF_NAMES)
NO_BUILD = "syntax or type check of the touched app (no build_cmd in agent_repo.conf)"


def parse(argv):
    if not argv or argv[0] != "check":
        raise Stop(USAGE)
    base, scope, as_json, declared, i = None, [], False, False, 1
    while i < len(argv):
        opt = argv[i]
        if opt == "--json":
            as_json = True
            i += 1
            continue
        if opt not in ("--base", "--declared", "--scope"):
            raise Stop("unknown argument: %s" % opt)
        if i + 1 >= len(argv):
            raise Stop("%s needs a value" % opt)
        value = argv[i + 1]
        if opt == "--base":
            if not value:
                raise Stop("--base needs a ref")
            base = value
        elif opt == "--scope":
            scope = split_globs(value)
            if any(not g for g in scope):
                raise Stop("--scope: empty item in the globs")
        else:
            declared = True
        i += 2
    if base is None:
        raise Stop("--base <ref> is required")
    return base, scope, as_json, declared


def main_root(top):
    """The main repo root: the parent of the common git dir (a worktree gives its main repo)."""
    proc = git(top, "rev-parse", "--path-format=absolute", "--git-common-dir", check=False)
    common = text_of(proc.stdout).strip()
    if proc.returncode == 0 and common.endswith("/.git"):
        return common[:-len("/.git")]
    return top


def seconds(conf, key):
    try:
        return int(conf.get(key, "").strip())
    except ValueError:
        return None


def run(argv):
    if len(argv) < 1:
        raise Stop("usage: agent_level.py <cwd> check --base <ref> [--scope \"<globs>\"] [--json] [--declared <x>]")
    cwd = argv[0]
    base, scope, as_json, declared = parse(argv[1:])

    proc = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise Stop("not in a git repo: %s" % cwd)
    top = text_of(proc.stdout).strip()
    conf, warns = agent_conf.repo_conf(main_root(top))
    for line in warns:
        sys.stderr.write(line + "\n")
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

    repo = Repo(top, mb, conf)
    kinds = {}
    for path in sorted(changed):
        kinds[path] = repo.kinds(path, changed[path])
    has = {}
    for path, (ks, _) in kinds.items():
        for k in ks.split("+"):
            has.setdefault(k, []).append(path)

    def of(*names):
        return sorted(set(p for n in names for p in has.get(n, [])))

    budget = agent_conf.CONSTANTS["check_budget_s"]
    guard_listed = [g.strip() for g in conf.get("guard_tests", "").split(",") if g.strip()]
    related_cmd = conf.get("related_cmd", "")
    triggered = {}      # block -> detail text (after "<BLOCK>: ")
    extra = {}          # block -> lines after its detail
    notes, heavy = [], []
    if declared:
        notes.append("note: --declared is ignored: levels are gone, blocks only")
    if not changed:
        notes.append("no changes")

    findings = diff_scan(repo, changed, kinds, scope)
    triggered["DIFF SCAN"] = "%d findings" % len(findings)

    built = of("code", "style")
    if built:
        n = seconds(conf, "build_seconds")
        if n is not None and n > budget:
            heavy.append(("BUILD", n, "nightly or pre-release, queued like a heavy test"))
        else:
            triggered["BUILD"] = "%s | run: %s" % (", ".join(built), conf.get("build_cmd") or NO_BUILD)

    related, groups = [], []
    if of("code", "style", "text", "rule"):
        related = related_tests(repo, changed, kinds)
        if related:
            run_cmd = fill(related_cmd, related) if related_cmd else "-"
            triggered["RELATED TESTS"] = "%s | run: %s" % (", ".join(related), run_cmd)
        else:
            triggered["RELATED TESTS"] = "none found | run: -"
        groups = groups_for(repo, changed, kinds)
        extra["RELATED TESTS"] = ["group %s: %s" % g for g in groups]

    guard = []
    if of("code", "style", "text", "rule"):
        if not guard_listed:
            notes.append("GUARD TESTS: none listed in agent_repo.conf (init writes them)")
        else:
            n = seconds(conf, "guard_seconds")
            if n is not None and n > budget:
                heavy.append(("GUARD TESTS", n, "nightly or pre-release"))
            else:
                guard = guard_listed
                run_cmd = fill(related_cmd, guard) if related_cmd else "-"
                triggered["GUARD TESTS"] = "%s | run: %s" % (", ".join(guard), run_cmd)

    signs = []
    db = of("migration", "schema")
    if db:
        whys = [(p, db_sign(repo, p, changed[p])) for p in db]
        yes = [(p, w) for p, w in whys if w]
        if yes:
            triggered["DB CHECK"] = "%s | owner signs: yes (%s)" % (", ".join(db), "; ".join(w for _, w in yes))
            signs.append(("DB CHECK", [p for p, _ in yes]))
        else:
            triggered["DB CHECK"] = "%s | owner signs: no (adds only)" % ", ".join(db)
    if of("data-script"):
        triggered["DATA CHECK"] = ", ".join(of("data-script"))
        signs.append(("DATA CHECK", of("data-script")))
    if of("deps", "ci"):
        files = of("deps", "ci")
        triggered["FULL SUITE"] = "%s | run: %s" % (", ".join(files), conf.get("full_cmd") or "-")
        signs.append(("FULL SUITE", files))
    if of("core"):
        triggered["CORE REVIEW"] = ", ".join(of("core"))
    if signs:
        order = agent_blocks.NAMES
        signs.sort(key=lambda s: order.index(s[0]))
        triggered["OWNER SIGN"] = "; ".join("%s (%s)" % (b, ", ".join(f)) for b, f in signs)

    blocks = [n for n in agent_blocks.TOOL_NAMES if n in triggered]
    heavy_names = [h[0] for h in heavy]
    rest = [n for n in agent_blocks.TOOL_NAMES if n not in triggered and n not in heavy_names]

    if as_json:
        data = {"blocks": blocks, "sign": ["%s (%s)" % (b, ", ".join(f)) for b, f in signs],
                "files": dict((p, {"kinds": kinds[p][0].split("+"), "reason": kinds[p][1]}) for p in sorted(kinds)),
                "findings": findings, "related": related, "guard": guard, "net": heavy_names}
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
        return 0

    out = ["BLOCKS: %s" % ", ".join(blocks + (["OWNER SIGN"] if signs else []))]
    for path in sorted(kinds):
        out.append("FILE %s: %s (%s)" % (path, kinds[path][0], kinds[path][1]))
    for name in agent_blocks.TOOL_NAMES:
        if name in triggered:
            out.append("%s: %s" % (name, triggered[name]))
            if name == "DIFF SCAN":
                out += ["  " + f for f in findings]
            out += extra.get(name, [])
    if "OWNER SIGN" in triggered:
        out.append("OWNER SIGN: %s" % triggered["OWNER SIGN"])
    out += notes
    if rest:
        out.append("NOT TRIGGERED: %s" % ", ".join(rest))
    for name, n, how in heavy:
        out.append("NET: %s (heavy, %d s over the %d s budget): %s" % (name, n, budget, how))
    out.append(BRIEF_LINE)
    sys.stdout.write("\n".join(out) + "\n")
    return 0


def main():
    try:
        return run(sys.argv[1:])
    except Stop as err:
        sys.stderr.write("agent-level: %s\n" % str(err).replace("\n", " "))
        return 2


if __name__ == "__main__":
    sys.exit(main())
