#!/usr/bin/env python3
"""agent_cleanfiles.py - the --files part of bin/agent-cleanup.sh (python3 stdlib only).

Run by the bash entry, never by hand:

    agent_cleanfiles.py --root <PROJECT_ROOT> --plugin <PLUGIN_ROOT>
                        --gitdir <PROJECT_GITDIR> --kind orca|plain|cloud
                        [--yes <ids>|all|none]

No --yes: the dry run. It lists rubbish docs (D), old state copies and the
leftover monitor file (S), mocks of no open task (M), and the idea (I), todo (T)
and worktree (W) lines the housekeep pass calls outdated. It changes nothing
and saves the table to <git dir>/agent-cleanup-files.last.

--yes: the rows are worked out again, every picked id is checked against the
saved table and the current rows, then the rows go (requirements/clean-up.md
section C). Lines go through agent-file.sh, files through rm or one git
commit. Nothing is pushed.

The todo, idea and worktree-line checks are agent_housekeep.file_rows, never
copied here. Errors never print a traceback: one line, exit 1.
"""

import argparse
import datetime
import fnmatch
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agent_conf
import agent_cleanup

try:
    import agent_housekeep
    HOUSEKEEP_ERROR = None
except Exception as _exc:  # reported as one line when the rows are needed
    agent_housekeep = None
    HOUSEKEEP_ERROR = _exc

SAVED = "agent-cleanup-files.last"
KINDS = "DSMITW"
LINE_FILES = {"I": "agent_ideas.txt", "T": "agent_todo.txt",
              "W": "agent_worktree.txt"}

DOC_EXTS = (".md", ".markdown", ".mdx", ".rst", ".adoc", ".asciidoc", ".org",
            ".pdf", ".doc", ".docx", ".rtf", ".odt")
TOP_KEEP_FILES = ("README.md", "PRINCIPLES.md", "CLAUDE.md", "AGENTS.md")
TOP_KEEP_DIRS = (".claude-plugin", "agents", "skills", "hooks", "bin")
LICENSE_PREFIXES = ("license", "licence", "copying", "notice")

STATE_STAMP = re.compile(r"^agent_state\.(\d{4}-\d\d-\d\d)-\d{6}\.txt$")
STATE_TRIM = re.compile(r"^agent_state\.trim-(\d{4}-\d\d-\d\d)\.txt$")
MOCK = re.compile(r"^mock/([^/]+)-mock\.html$")

DEFAULT_DAYS = 14
DOCS_KEEP_NOTE = ("docs_keep not set: a product repo keeps its real docs with "
                  "agent-settings.sh docs_keep <list>")
FOOTER = ("To remove: agent-cleanup.sh --files --yes <ids>|all|none. "
          "Nothing is removed without --yes.")


class Fail(Exception):
    """A one-line error: printed, exit 1."""


# ---------------------------------------------------------------- helpers


def now_text():
    return os.environ.get("AGENT_FAKE_NOW") or time.strftime("%Y-%m-%d %H:%M")


def parse_day(text):
    try:
        return datetime.datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def today():
    day = parse_day(now_text())
    return day or datetime.date.today()


def clean(text):
    """A table field never holds " | "."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text))
    while " | " in text:
        text = text.replace(" | ", " / ")
    return text


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as fh:
            return fh.read()
    except OSError:
        return ""


def read_lines(path):
    """Lines split on \\n only, like agent-file.sh (never splitlines())."""
    parts = read_text(path).split("\n")
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def first_field(line):
    """The raw first field, as agent-file.sh reads it (split on " | ")."""
    return line.split(" | ", 1)[0]


class Ctx(object):
    def __init__(self, root, plugin, gitdir, kind):
        self.root = root
        self.plugin = plugin
        self.gitdir = gitdir
        self.kind = kind

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def git(self, *args, **kw):
        argv = ["git", "--literal-pathspecs", "--no-optional-locks"] + list(args)
        return agent_cleanup.run(argv, cwd=self.root,
                                 timeout=kw.get("timeout", 60.0))

    def git_plain(self, *args, **kw):
        return agent_cleanup.run(["git", "--literal-pathspecs"] + list(args),
                                 cwd=self.root,
                                 timeout=kw.get("timeout", 60.0))

    def file_cmd(self, *args):
        script = os.path.join(self.plugin, "bin", "agent-file.sh")
        env = dict(os.environ)
        env["AGENT_CLEANUP_DONE"] = "1"
        return agent_cleanup.run([script] + list(args), cwd=self.root,
                                 timeout=180.0, env=env)


def first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return "no message"


def res_why(res):
    if res.timed_out:
        return "timed out"
    return first_line(res.err or res.out)


# ---------------------------------------------------------------- config


def read_conf(ctx):
    days, keep, problem = DEFAULT_DAYS, [], None
    conf = {}
    try:
        conf = agent_conf.load(ctx.path("agent.conf"))
    except Exception:
        conf = {}
    value = conf.get("cleanup_days")
    if value is not None and agent_conf.validate_value("cleanup_days", value) is None:
        days = int(value)
    value = conf.get("docs_keep", "")
    if value.strip():
        problem = agent_conf.validate_value("docs_keep", value)
        if problem is None:
            keep = [item.strip() for item in value.split(",") if item.strip()]
    return days, keep, problem, bool(value.strip())


# ---------------------------------------------------------------- git facts


def split_z(text):
    return [item for item in text.split("\0") if item]


def seen_files(ctx):
    """(tracked set, all seen paths sorted). A nested repo (entry ending in /) is skipped."""
    res = ctx.git("ls-files", "-z")
    if not res.ok:
        raise Fail("git ls-files failed: %s" % res_why(res))
    tracked = set(split_z(res.out))
    res = ctx.git("ls-files", "-o", "--exclude-standard", "-z")
    if not res.ok:
        raise Fail("git ls-files failed: %s" % res_why(res))
    untracked = set(split_z(res.out))
    seen = set(p for p in tracked | untracked if not p.endswith("/"))
    return tracked, sorted(seen)


def dirty_paths(ctx):
    res = ctx.git("status", "--porcelain", "-z", "--untracked-files=no")
    if not res.ok:
        raise Fail("git status failed: %s" % res_why(res))
    parts = res.out.split("\0")
    dirty = set()
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        dirty.add(entry[3:])
        if entry[0] in "RC" or entry[1] in "RC":
            if i < len(parts) and parts[i]:
                dirty.add(parts[i])
            i += 1
    return dirty


def in_use_map(ctx, rels):
    """rel -> the first other tracked file that holds its basename in one
    quoted string. One git grep for every name."""
    names = sorted(set(os.path.basename(r) for r in rels))
    if not names:
        return {}
    handle, patfile = tempfile.mkstemp(prefix="agent-cleanfiles-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write("".join(n + "\n" for n in names))
        res = ctx.git("grep", "-F", "-l", "-I", "-z", "-f", patfile, "--",
                      timeout=300.0)
    finally:
        try:
            os.unlink(patfile)
        except OSError:
            pass
    if res.rc not in (0, 1) or res.timed_out:
        raise Fail("git grep failed: %s" % res_why(res))
    patterns = dict((n, re.compile(r"([\"'])(?:[^\"'\s]*/)?" + re.escape(n) + r"\1"))
                    for n in names)
    holders = {}
    for other in sorted(split_z(res.out)):
        text = read_text(ctx.path(other))
        for name in names:
            if name in text and patterns[name].search(text):
                holders.setdefault(name, []).append(other)
    found = {}
    for rel in rels:
        for other in holders.get(os.path.basename(rel), []):
            if other != rel:
                found[rel] = other
                break
    return found


# ---------------------------------------------------------------- doc rules


def is_doc(rel):
    return rel.lower().endswith(DOC_EXTS)


def keep_doc(rel, docs_keep):
    parts = rel.split("/")
    name = parts[-1]
    if parts[0] == "requirements" and len(parts) > 1:
        return True
    if "tests" in parts[:-1] or "test" in parts[:-1]:
        return True
    if len(parts) == 1 and name in TOP_KEEP_FILES:
        return True
    if len(parts) > 1 and parts[0] in TOP_KEEP_DIRS:
        return True
    if parts[0].startswith("."):
        return True
    if name.lower().startswith(LICENSE_PREFIXES):
        return True
    for entry in docs_keep:
        if entry.endswith("/"):
            if rel.startswith(entry):
                return True
        elif fnmatch.fnmatchcase(rel, entry):
            return True
    return False


# ---------------------------------------------------------------- the rows


def file_row(kind, rel, tracked, why):
    return {"kind": kind, "key": rel, "what": rel, "path": rel,
            "tracked": rel in tracked, "why": why,
            "where": "repo, tracked" if rel in tracked else "repo, untracked",
            "how": "git rm, one commit" if rel in tracked else "rm"}


def doc_rows(seen, tracked, docs_keep):
    return [file_row("D", rel, tracked, "doc not allowed by the docs rule")
            for rel in seen
            if is_doc(rel) and not keep_doc(rel, docs_keep)]


def state_rows(ctx, tracked, days):
    rows = []
    now = today()
    try:
        names = sorted(os.listdir(ctx.root))
    except OSError:
        names = []
    for name in names:
        match = STATE_STAMP.match(name) or STATE_TRIM.match(name)
        if not match or not os.path.lexists(ctx.path(name)):
            continue
        day = parse_day(match.group(1))
        if day is None:
            continue
        age = (now - day).days
        if age > days:
            rows.append(file_row("S", name, tracked,
                                 "state copy %d days old (over %d)" % (age, days)))
    name = "agent_monitor.txt"
    if os.path.isfile(ctx.path(name)):
        rows.append(file_row("S", name, tracked,
                             "leftover monitor file, nothing writes it any more"))
    for row in rows:
        if row["tracked"]:
            row["how"] = "git rm, one commit"
        else:
            row["how"] = "rm, no copy"
    return rows


def task_facts(ctx):
    """(open task names, name -> (word, date)) for the mock rule."""
    opened = set()
    for line in read_lines(ctx.path("agent_todo.txt")):
        name = line.split(" | ", 1)[0].strip()
        if name:
            opened.add(name)
    finished = {}
    for line in read_lines(ctx.path("agent_completed.txt")):
        fields = [f.strip() for f in line.split(" | ")]
        if len(fields) < 2:
            continue
        dropped = any(f.startswith("dropped:") for f in fields[2:])
        finished[fields[1]] = ("dropped" if dropped else "done", fields[0][:10])
    return opened, finished


def mock_rows(ctx, seen, tracked):
    opened, finished = task_facts(ctx)
    rows = []
    for rel in seen:
        match = MOCK.match(rel)
        if not match:
            continue
        name = match.group(1)
        if name in opened:
            continue
        if name in finished:
            word, date = finished[name]
            why = "task %s %s %s" % (name, word, date)
        else:
            why = "no task named %s" % name
        rows.append(file_row("M", rel, tracked, why))
    return rows


def line_rows(ctx, days):
    if agent_housekeep is None:
        raise Fail("agent_housekeep.py does not load: %s" % HOUSEKEEP_ERROR)
    func = getattr(agent_housekeep, "file_rows", None)
    if func is None:
        raise Fail("agent_housekeep.file_rows is missing")
    got = func(ctx.root, ctx.plugin, ctx.gitdir, ctx.kind, days * 1440)
    rows = []
    for item in sorted(got.get("ideas", []), key=lambda i: i["n"]):
        cut = getattr(agent_housekeep, "idea_text", None)
        text = (cut(item["line"]) if cut else item["line"].split(" | ", 1)[0]).strip()
        rows.append({"kind": "I", "key": item["line"], "n": item["n"],
                     "what": "idea: " + text[:60],
                     "where": "agent_ideas.txt line %d" % item["n"],
                     "why": item["why"], "how": "idea rm, line backed up"})
    for item in got.get("todos", []):
        if item["kind"] == "merged":
            how = "todo done"
            if item.get("sha"):
                how += " --merge " + item["sha"]
        else:
            how = "todo drop"
        rows.append({"kind": "T", "key": item["line"], "name": item["name"],
                     "sha": item.get("sha"), "days": item.get("days"),
                     "merged": item["kind"] == "merged",
                     "what": "todo " + item["name"], "where": "agent_todo.txt",
                     "why": item["why"], "how": how + ", line backed up"})
    for item in got.get("worktrees", []):
        path = item["path"]
        rows.append({"kind": "W", "key": item["line"], "wpath": path,
                     "what": "worktree line " + path,
                     "where": "agent_worktree.txt", "why": item["why"],
                     "how": "worktree rm, line backed up"})
    return rows, list(got.get("notes", []))


def compute(ctx):
    """(rows with ids, kept [(what, why)], notes)."""
    days, docs_keep, keep_problem, keep_set = read_conf(ctx)
    tracked, seen = seen_files(ctx)
    candidates = (doc_rows(seen, tracked, docs_keep)
                  + state_rows(ctx, tracked, days)
                  + mock_rows(ctx, seen, tracked))
    dirty = dirty_paths(ctx)
    rows, kept = [], []
    used = in_use_map(ctx, [r["path"] for r in candidates if r["kind"] != "S"])
    for row in candidates:
        if row["kind"] != "S":
            other = used.get(row["path"])
            if other:
                kept.append((row["what"], "in use: " + other))
                continue
        if row["tracked"] and row["path"] in dirty:
            kept.append((row["what"], "uncommitted changes"))
            continue
        rows.append(row)
    notes = []
    if keep_problem:
        notes.append("docs_keep not valid: " + keep_problem)
    elif not keep_set and any(r["kind"] == "D" for r in rows):
        notes.append(DOCS_KEEP_NOTE)
    lines, line_notes = line_rows(ctx, days)
    rows += lines
    notes += [n for n in line_notes if n not in notes]
    ordered, count = [], {}
    for kind in KINDS:
        mine = [r for r in rows if r["kind"] == kind]
        if kind in "DSM":
            mine.sort(key=lambda r: r["path"])
        for row in mine:
            count[kind] = count.get(kind, 0) + 1
            row["id"] = "%s%d" % (kind, count[kind])
            ordered.append(row)
    return ordered, kept, notes


# ---------------------------------------------------------------- dry run


def save_table(ctx, rows):
    text = "# agent-cleanup-files.last %s\n" % now_text()
    text += "".join("%s\t%s\t%s\n" % (r["id"], r["kind"], r["key"]) for r in rows)
    try:
        os.makedirs(ctx.gitdir, exist_ok=True)
        path = os.path.join(ctx.gitdir, SAVED)
        tmp = "%s.tmp.%d" % (path, os.getpid())
        with open(tmp, "w", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError as exc:
        raise Fail("cannot save the table: %s" % exc)


def load_table(ctx):
    """[(id, kind, key)] or None when there is no saved table."""
    path = os.path.join(ctx.gitdir, SAVED)
    if not os.path.isfile(path):
        return None
    saved = []
    for line in read_lines(path):
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t", 2)
        if len(parts) == 3:
            saved.append((parts[0], parts[1], parts[2]))
    return saved


def dry_run(ctx):
    rows, kept, notes = compute(ctx)
    save_table(ctx, rows)
    out = []
    if not rows and not kept and not notes:
        out += ["=== clean-up files ===", "nothing to clean"]
    else:
        out.append("=== clean-up files (dry run, nothing removed) ===")
        if rows:
            out.append("id | what | where | why | how removed")
            for r in rows:
                out.append(" | ".join([r["id"]] + [clean(r[k]) for k in
                                                   ("what", "where", "why", "how")]))
        else:
            out.append("nothing to clean")
        if kept:
            out += ["kept: %d" % len(kept), "what | why kept"]
            out += ["%s | %s" % (clean(w), clean(y)) for w, y in kept]
        out += ["note: " + clean(n) for n in notes]
        if rows:
            out.append(FOOTER)
    sys.stdout.write("\n".join(out) + "\n")
    return 0


# ---------------------------------------------------------------- remove


def refuse(text):
    sys.stderr.write("REFUSED: %s\n" % text)
    return 1


def parse_ids(text):
    ids = []
    for tok in re.split(r"[,\s]+", text.strip().upper()):
        if tok and tok not in ids:
            ids.append(tok)
    return ids


def operation_in_progress(ctx):
    for name, what in (("MERGE_HEAD", "merge"), ("CHERRY_PICK_HEAD", "cherry-pick"),
                       ("REVERT_HEAD", "revert"), ("rebase-merge", "rebase"),
                       ("rebase-apply", "rebase")):
        if os.path.exists(os.path.join(ctx.gitdir, name)):
            return what
    return None


def backup_file(ctx):
    stamp = now_text()
    if os.environ.get("AGENT_FAKE_NOW"):
        stamp = stamp.replace(" ", "-").replace(":", "") + "00"
    else:
        stamp = time.strftime("%Y-%m-%d-%H%M%S")
    return os.path.join(ctx.gitdir, "agent-cleanup", stamp + ".txt")


def removal_key(row):
    """The first field agent-file.sh matches for a W or T row (raw, as in the file)."""
    return first_field(row["key"])


def backup_items(ctx, rows):
    """(file, line) of every line the calls will remove, each once. W and T
    calls remove every line with that first field."""
    items, seen = [], set()
    for row in rows:
        name = LINE_FILES[row["kind"]]
        if row["kind"] == "I":
            hits = [(row["n"] - 1, row["key"])]
        else:
            key = removal_key(row)
            hits = [(i, l) for i, l in enumerate(read_lines(ctx.path(name)))
                    if first_field(l) == key]
            if not hits:
                hits = [(-1, row["key"])]
        for index, line in hits:
            mark = (name, index, line)
            if mark not in seen:
                seen.add(mark)
                items.append((name, line))
    return items


def write_backup(ctx, rows):
    items = backup_items(ctx, [r for r in rows if r["kind"] in LINE_FILES])
    if not items:
        return None, 0
    path = backup_file(ctx)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8", errors="surrogateescape") as fh:
            for name, line in items:
                fh.write("%s | %s\n" % (name, line))
    except OSError as exc:
        raise Fail("FAILED at backup: %s. Nothing changed." % exc)
    return path, len(items)


def remove_line(ctx, row, gone):
    """None when it went, else the reason. `gone` holds the (kind, first
    field) of lines an earlier call already removed."""
    kind = row["kind"]
    if kind in "WT":
        mark = (kind, removal_key(row))
        if mark in gone:
            return None
        gone.add(mark)
    if kind == "W":
        res = ctx.file_cmd("worktree", "rm", removal_key(row))
    elif kind == "T":
        if row["merged"]:
            args = ["todo", "done", row["name"]]
            if row.get("sha"):
                args += ["--merge", row["sha"]]
        else:
            args = ["todo", "drop", row["name"],
                    "clean-up: stale %sd" % row["days"]]
        res = ctx.file_cmd(*args)
    else:
        lines = read_lines(ctx.path("agent_ideas.txt"))
        n = row["n"]
        if n < 1 or n > len(lines) or lines[n - 1] != row["key"]:
            return "the idea line changed meanwhile"
        res = ctx.file_cmd("idea", "rm", str(n))
    return None if res.ok else "agent-file.sh: " + res_why(res)


def do_yes(ctx, value):
    ids = parse_ids(value)
    if ids == ["NONE"]:
        sys.stdout.write("nothing removed\n")
        return 0
    saved = load_table(ctx)
    if saved is None:
        return refuse("run agent-cleanup.sh --files first. Nothing changed.")
    if ids == ["ALL"]:
        ids = [s[0] for s in saved]
    if "ALL" in ids or "NONE" in ids:
        return refuse("all and none stand alone. Nothing changed.")
    by_id = dict((s[0], s) for s in saved)
    for one in ids:
        if one not in by_id:
            return refuse("%s unknown. Nothing changed." % one)
    what = operation_in_progress(ctx)
    if what:
        return refuse("a %s is in progress in the repo. Nothing changed." % what)
    rows, _kept, _notes = compute(ctx)
    used = set()
    picked = []
    for one in ids:
        _id, kind, key = by_id[one]
        match = None
        for index, row in enumerate(rows):
            if index not in used and row["kind"] == kind and row["key"] == key:
                match = index
                break
        if match is None:
            return refuse("%s changed since the table: run agent-cleanup.sh "
                          "--files again. Nothing changed." % one)
        used.add(match)
        picked.append(dict(rows[match], id=one))
    if not picked:
        sys.stdout.write("nothing removed\n")
        return 0
    for row in picked:
        if row["kind"] not in "WT":
            continue
        group = (row["kind"], removal_key(row))
        missing = [r["id"] for i, r in enumerate(rows)
                   if i not in used and (r["kind"], removal_key(r)) == group]
        if missing:
            return refuse("%s shares its line key with %s: pick them together. "
                          "Nothing changed." % (row["id"], ", ".join(missing)))
    out = []
    removed = []

    def flush():
        if out:
            sys.stdout.write("\n".join(out) + "\n")
            sys.stdout.flush()
            del out[:]

    def failed(one, why):
        flush()
        sys.stderr.write("FAILED at %s: %s. Removed before it: %s.\n"
                         % (one, why, " ".join(removed) or "nothing"))
        return 1

    path, count = write_backup(ctx, picked)
    if path:
        out.append("backup: %s (%d lines)" % (path, count))

    def order(kind):
        mine = [r for r in picked if r["kind"] == kind]
        if kind == "I":
            mine.sort(key=lambda r: -r["n"])
        return mine

    gone = set()
    for kind in "WTI":
        for row in order(kind):
            why = remove_line(ctx, row, gone)
            if why:
                return failed(row["id"], why)
            removed.append(row["id"])
            out.append("removed: %s %s" % (row["id"], row["what"]))
    files = [r for r in picked if r["kind"] in "DSM"]
    for row in [r for r in files if not r["tracked"]]:
        try:
            os.unlink(ctx.path(row["path"]))
        except OSError as exc:
            return failed(row["id"], "rm: %s" % exc)
        removed.append(row["id"])
        out.append("removed: %s %s" % (row["id"], row["what"]))
    tracked = [r for r in files if r["tracked"]]
    if tracked:
        paths = [r["path"] for r in tracked]
        res = ctx.git_plain("rm", "-q", "--", *paths)
        if not res.ok:
            return failed(tracked[0]["id"], "git rm: " + res_why(res))
        message = "clean-up: %d files" % len(tracked)
        res = ctx.git_plain("commit", "-q", "-m", message, "--", *paths)
        if not res.ok:
            why = "git commit: " + res_why(res)
            ctx.git_plain("reset", "-q", "--", *paths)
            back = ctx.git_plain("checkout", "-q", "HEAD", "--", *paths)
            if not back.ok:
                why += " (and the files could not be put back: %s)" % res_why(back)
            return failed(tracked[0]["id"], why)
        removed += [r["id"] for r in tracked]
        out += ["removed: %s %s" % (r["id"], r["what"]) for r in tracked]
        sha = ctx.git_plain("rev-parse", "--short=7", "HEAD").out.strip()
        out.append("commit %s %s (not pushed)" % (sha, message))
    out.append("clean-up: removed %d of %d picked" % (len(removed), len(picked)))
    flush()
    return 0


# ---------------------------------------------------------------- main


def main(argv):
    parser = argparse.ArgumentParser(prog="agent_cleanfiles.py")
    parser.add_argument("--root", required=True)
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--gitdir", required=True)
    parser.add_argument("--kind", default="plain")
    parser.add_argument("--yes", default=None)
    args = parser.parse_args(argv)
    ctx = Ctx(args.root, args.plugin, args.gitdir, args.kind)
    try:
        if args.yes is None:
            return dry_run(ctx)
        return do_yes(ctx, args.yes)
    except Fail as exc:
        sys.stderr.write("clean-up: %s\n" % exc)
        return 1
    except BrokenPipeError:
        return 1
    except Exception as exc:
        sys.stderr.write("clean-up: error: %s: %s\n" % (type(exc).__name__, exc))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
