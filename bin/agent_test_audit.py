#!/usr/bin/env python3
"""Audit a test merge (the test-slim skill, steps 4-6). Python 3 stdlib only, any repo.

  agent_test_audit.py --before <ids.txt> --after <ids.txt> [--table <md>]
      Every before id (file::Class.test) must be kept (same id after), moved (same test name,
      the part after the last '.', present after; when several before tests share a name, after
      must have at least as many), or removed with a row of the removed-checks table in --table:
      | Old file::test | Why it is a duplicate | Twin file::test that still checks it |
      Exit 0 AUDIT PASS, 1 AUDIT FAIL, 2 usage error.
  agent_test_audit.py ids <dir> [--ref <git ref>]
      List file::Class.test for every def test* method of a class in a test*.py file in <dir>,
      now or at a git ref (read from the current folder's repo).
"""

import ast
import os
import subprocess
import sys

HEADER = ["old file::test", "why it is a duplicate", "twin file::test that still checks it"]


def usage(msg=""):
    if msg:
        print(msg, file=sys.stderr)
    print(__doc__, file=sys.stderr)
    return 2


def ids_of_source(name, src):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                    out.append("%s::%s.%s" % (name, node.name, item.name))
    return out


def cmd_ids(args):
    ref, rest, i = None, [], 0
    while i < len(args):
        if args[i] == "--ref":
            if i + 1 >= len(args):
                return usage("--ref needs a value")
            ref = args[i + 1]
            i += 2
        elif args[i].startswith("--"):
            return usage("unknown option " + args[i])
        else:
            rest.append(args[i])
            i += 1
    if len(rest) != 1:
        return usage("ids needs one folder")
    folder = rest[0].rstrip("/") or "."
    out = []
    if ref:
        r = subprocess.run(["git", "ls-tree", "--name-only", ref, folder + "/"], capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr.strip(), file=sys.stderr)
            return 2
        for path in sorted(r.stdout.splitlines()):
            base = os.path.basename(path)
            if base.startswith("test") and base.endswith(".py"):
                s = subprocess.run(["git", "show", "%s:./%s" % (ref, path.replace("\\", "/"))],
                                   capture_output=True, text=True)
                if s.returncode == 0:
                    out += ids_of_source(base, s.stdout)
    else:
        if not os.path.isdir(folder):
            return usage("not a folder: " + folder)
        for base in sorted(os.listdir(folder)):
            if base.startswith("test") and base.endswith(".py"):
                with open(os.path.join(folder, base), encoding="utf-8") as fh:
                    out += ids_of_source(base, fh.read())
    for line in out:
        print(line)
    return 0


def read_ids(path):
    with open(path, encoding="utf-8") as fh:
        return [l.strip() for l in fh if l.strip() and not l.startswith("#")]


def cells(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def read_table(path):
    rows, active = [], False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip().startswith("|"):
                active = False
                continue
            c = cells(line)
            if [x.lower() for x in c] == HEADER:
                active = True
            elif active and not all(set(x) <= set("-: ") for x in c):
                c += [""] * (3 - len(c))
                rows.append(c[:3])
    return rows


def name_of(i):
    return i.rsplit(".", 1)[-1]


def cmd_audit(args):
    opts, i = {}, 0
    while i < len(args):
        if args[i] in ("--before", "--after", "--table") and i + 1 < len(args):
            opts[args[i]] = args[i + 1]
            i += 2
        else:
            return usage("bad argument " + args[i])
    if "--before" not in opts or "--after" not in opts:
        return usage("--before and --after are required")
    try:
        before, after = read_ids(opts["--before"]), read_ids(opts["--after"])
        rows = read_table(opts["--table"]) if "--table" in opts else []
    except OSError as e:
        return usage(str(e))
    bset, aset = set(before), set(after)
    problems = []
    removed = set()
    for old, why, twin in rows:
        if old not in bset:
            problems.append("table row names a test that is not in before: %s" % old)
        elif not why:
            problems.append("table row has no reason: %s" % old)
        elif twin not in aset:
            problems.append("twin is not in after: %s (twin of %s)" % (twin, old))
        elif old not in aset:
            removed.add(old)
    kept = [b for b in before if b in aset]
    left = [b for b in before if b not in aset and b not in removed]
    spare = {}
    for a in after:
        if a not in bset:
            spare[name_of(a)] = spare.get(name_of(a), 0) + 1
    moved = 0
    for b in left:
        n = name_of(b)
        if spare.get(n, 0) > 0:
            spare[n] -= 1
            moved += 1
        else:
            problems.append("lost (not kept, not moved, no removed row with a twin): %s" % b)
    print("before %d" % len(before))
    print("kept %d" % len(kept))
    print("moved %d" % moved)
    print("removed with twin %d" % len(removed))
    for p in problems:
        print("PROBLEM: " + p)
    print("AUDIT FAIL" if problems else "AUDIT PASS")
    return 1 if problems else 0


def main(argv):
    if argv and argv[0] == "ids":
        return cmd_ids(argv[1:])
    if not argv or argv[0] in ("-h", "--help"):
        return usage() if argv == [] else (print(__doc__) or 0)
    return cmd_audit(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
