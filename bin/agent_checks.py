#!/usr/bin/env python3
"""agent_checks.py - the check-block commands of bin/agent-file.sh (python3 stdlib only).

Run by agent-file.sh, never by hand:

    agent_checks.py <project root> <state dir> <now> <command> [args...]

  project root  the main repo: agent_todo.txt
  state dir     the git toplevel of the cwd: agent_state.txt, agent_repo.conf
  now           "YYYY-MM-DD HH:MM"

Commands: norm, todo-checks, todo-builder, todo-est, check, gate, next, after-list, edge-add.
A refusal is one line on stderr and exit 1 (nothing written); a usage error is exit 2.
Rules: requirements/check-blocks.md, section 9 C3 and section 11.
"""

import fnmatch
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

FALLBACK = ["DIFF SCAN", "BUILD", "RELATED TESTS", "GUARD TESTS", "DB CHECK", "DATA CHECK", "FULL SUITE",
            "CORE REVIEW", "DIFF READ", "EXAMPLES TEST", "FLOW CHECK", "UI CHECK", "REAL DATA COUNT"]
SIGN = "OWNER SIGN"
BUILDER_BLOCKS = ("DIFF READ", "FLOW CHECK", "UI CHECK")
DATE_RE = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"


class Refuse(Exception):
    def __init__(self, msg, code=1):
        Exception.__init__(self, msg)
        self.code = code


def block_names():
    try:
        import agent_blocks
        names = [b["name"] for b in agent_blocks.BLOCKS]
        if names:
            return names
    except Exception:
        pass
    return list(FALLBACK)


def order_key(name):
    names = block_names() + [SIGN]
    return names.index(name) if name in names else len(names)


def parse_list(text, allow_sign=False):
    """A comma list of block names -> the names in table order, once. Refuses an unknown one."""
    names = block_names() + ([SIGN] if allow_sign else [])
    out = []
    for raw in text.split(","):
        b = raw.strip()
        if not b:
            continue
        if b not in names:
            raise Refuse("unknown block: %s (the blocks: %s)" % (b, ", ".join(names)))
        if b not in out:
            out.append(b)
    if not out:
        raise Refuse("no block named")
    return sorted(out, key=order_key)


def bad_text(s):
    return " | " in s or "\n" in s or "\r" in s


# ---------------------------------------------------------------- the todo file

class Todo(object):
    def __init__(self, root):
        self.path = os.path.join(root, "agent_todo.txt")
        try:
            with open(self.path, encoding="utf-8", errors="surrogateescape") as fh:
                self.lines = fh.read().split("\n")
        except IOError:
            self.lines = []
        if self.lines and self.lines[-1] == "":
            self.lines.pop()

    def index(self, name):
        for i, l in enumerate(self.lines):
            if l.split(" | ")[0] == name:
                return i
        return -1

    def fields(self, name):
        i = self.index(name)
        return None if i < 0 else self.lines[i].split(" | ")

    def set(self, name, fields):
        self.lines[self.index(name)] = " | ".join(fields)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write("\n".join(self.lines) + "\n")
        os.replace(tmp, self.path)

    def open_lines(self):
        return [l.split(" | ") for l in self.lines if l.strip()]


def field_of(fields, prefix):
    for f in fields[3:]:
        if f.startswith(prefix + " "):
            return f[len(prefix) + 1:]
    return None


def field_index(fields, prefix):
    for i in range(3, len(fields)):
        if fields[i].startswith(prefix + " "):
            return i
    return -1


def anchor(fields):
    """The index after which a new checks/scope/builder field goes: the last of est, guess, level (else the what)."""
    at = 2
    for i in range(3, len(fields)):
        if re.match(r"(est|guess) \d+m$|level ([0-9]+|[A-D])$", fields[i]):
            at = i
    return at


def need_line(todo, name):
    f = todo.fields(name)
    if f is None:
        raise Refuse("no todo line named: %s" % name)
    return f


# ---------------------------------------------------------------- commands

def cmd_norm(a):
    if len(a) != 1:
        raise Refuse("norm: one list", 2)
    print(", ".join(parse_list(a[0])))


def cmd_todo_checks(ctx, a):
    if not a or not a[0].strip():
        raise Refuse("todo checks: needs a todo name")
    name, rest = a[0], a[1:]
    todo = Todo(ctx["root"])
    f = need_line(todo, name)
    cur = field_of(f, "checks")
    old = [x.strip() for x in cur.split(",")] if cur else []
    if rest and rest[0] == "--remove":
        opts, i = {}, 0
        while i < len(rest):
            if rest[i] in ("--remove", "--owner-quote", "--time") and i + 1 < len(rest):
                if rest[i] in opts:
                    raise Refuse("todo checks: %s given twice" % rest[i])
                opts[rest[i]] = rest[i + 1]
                i += 2
            else:
                raise Refuse("todo checks: unknown or incomplete option: %s" % rest[i])
        block = parse_list(opts["--remove"])
        if len(block) != 1:
            raise Refuse("todo checks: --remove takes one block")
        block = block[0]
        quote = opts.get("--owner-quote", "")
        if not quote.strip():
            raise Refuse("todo checks: --remove needs --owner-quote with the owner's words")
        if block not in old:
            raise Refuse("todo checks: %s is not in the checks of %s" % (block, name))
        cmd = [os.path.join(HERE, "agent-owner-order.sh"), "verify", "--repo",
               os.path.basename(ctx["root"].rstrip("/")), "--quote", quote]
        if "--time" in opts:
            cmd += ["--time", opts["--time"]]
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               universal_newlines=True, stdin=subprocess.DEVNULL)
            code, out = p.returncode, p.stdout
        except OSError as e:
            code, out = 127, str(e)
        if code != 0:
            why = " ".join(out.split()) or "exit %d" % code
            raise Refuse("todo checks: owner order not verified, nothing changed: %s" % why[:300])
        new = [b for b in old if b != block]
        at = field_index(f, "checks")
        removed = "removed %s %s" % (block, ctx["now"])
        if at >= 0:
            f[at:at + 1] = (["checks " + ", ".join(new)] if new else []) + [removed]
        print("todo checks: %s %s -> %s (removed %s)" % (name, ", ".join(old) or "-", ", ".join(new) or "-", block))
        todo.set(name, f)
        return
    if len(rest) != 1:
        raise Refuse("todo checks: usage: todo checks \"<name>\" <BLOCK>[,<BLOCK>] | --remove <BLOCK> --owner-quote \"<words>\"")
    add = parse_list(rest[0])
    new = sorted(set(old) | set(add), key=order_key)
    field = "checks " + ", ".join(new)
    at = field_index(f, "checks")
    if at >= 0:
        f[at] = field
    else:
        f.insert(anchor(f) + 1, field)
    todo.set(name, f)
    print("todo checks: %s %s -> %s" % (name, ", ".join(old) or "-", ", ".join(new)))


def set_field(f, prefix, value):
    at = field_index(f, prefix)
    field = "%s %s" % (prefix, value)
    if at >= 0:
        f[at] = field
    else:
        pos = anchor(f) + 1
        for p in ("checks", "scope"):   # keep the order checks, scope, builder
            j = field_index(f, p)
            if j >= 0 and prefix != p and (prefix, p) in (("scope", "checks"), ("builder", "scope"), ("builder", "checks")):
                pos = max(pos, j + 1)
        f.insert(pos, field)


def cmd_todo_builder(ctx, a):
    if len(a) != 2:
        raise Refuse("todo builder: usage: todo builder \"<name>\" <who>")
    name, who = a
    if not who.strip() or bad_text(who):
        raise Refuse("todo builder: the name is empty or holds \" | \" or a line break")
    todo = Todo(ctx["root"])
    f = need_line(todo, name)
    set_field(f, "builder", who.strip())
    todo.set(name, f)
    print("todo builder: %s -> %s" % (name, who.strip()))


def cmd_todo_est(ctx, a):
    if len(a) < 2:
        raise Refuse("todo est: usage: todo est \"<name>\" <minutes> [--guess <m>]")
    name, mins, rest = a[0], a[1], a[2:]
    guess = None
    if rest:
        if len(rest) != 2 or rest[0] != "--guess":
            raise Refuse("todo est: only --guess <m> may follow")
        guess = rest[1]
        if not (guess.isdigit() and len(guess) <= 9 and int(guess) >= 1):
            raise Refuse("todo est: --guess wants a whole number, 1 or more (got: %s)" % guess)
    todo = Todo(ctx["root"])
    f = need_line(todo, name)
    if not (mins.isdigit() and len(mins) <= 9 and int(mins) >= 1):
        raise Refuse("todo est: the minutes are a whole number, 1 or more (got: %s)" % mins)
    mins = str(int(mins))
    old = field_of(f, "est")
    at = field_index(f, "est")
    if at >= 0:
        f[at] = "est %sm" % mins
    else:
        f.insert(3, "est %sm" % mins)
        at = 3
    if guess is not None:
        g = field_index(f, "guess")
        if g >= 0:
            f[g] = "guess %sm" % int(guess)
        else:
            f.insert(at + 1, "guess %sm" % int(guess))
    todo.set(name, f)
    print("todo est: %s %s -> %sm" % (name, old or "-", mins))


def cmd_check(ctx, a):
    if len(a) < 3:
        raise Refuse("check: usage: check \"<task>\" \"<BLOCK>\" pass|fail --by <who> --evidence \"<text>\"")
    task, block, verdict, rest = a[0], a[1], a[2], a[3:]
    if not task.strip() or bad_text(task):
        raise Refuse("check: the task name is empty or holds \" | \" or a line break")
    if block not in block_names() + [SIGN]:
        raise Refuse("check: unknown block: %s" % block)
    if verdict not in ("pass", "fail"):
        raise Refuse("check: the result is pass or fail (got: %s)" % verdict)
    opts, i = {}, 0
    while i < len(rest):
        if rest[i] in ("--by", "--evidence") and i + 1 < len(rest):
            opts[rest[i]] = rest[i + 1]
            i += 2
        else:
            raise Refuse("check: unknown or incomplete option: %s" % rest[i])
    for k in ("--by", "--evidence"):
        v = opts.get(k, "")
        if not v.strip():
            raise Refuse("check: %s is needed" % k)
        if "\n" in v or "\r" in v:
            raise Refuse("check: %s must not hold a line break" % k)
    if " | " in opts["--by"]:
        raise Refuse("check: --by must not hold \" | \"")
    import agent_state
    text = "CHECK %s %s: %s | by %s | %s" % (task, block, verdict, opts["--by"].strip(), opts["--evidence"].strip())
    saved = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        agent_state.add(ctx["state"], ctx["now"], [text])
    except Exception as e:
        sys.stdout = saved
        raise Refuse("check: %s" % e)
    finally:
        sys.stdout = saved
    print("check: %s %s %s (by %s)" % (task, block, verdict, opts["--by"].strip()))


# -- gate

def read_results(path, task):
    """block -> (verdict, who): the last CHECK line of the task wins."""
    res = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().split("\n")
    except IOError:
        return res
    head = "CHECK %s " % task
    names = block_names() + [SIGN]
    for l in lines:
        if not l.startswith(head):
            continue
        rest = l[len(head):]
        m = re.match(r"(.+?): (pass|fail) \| by (.*?)(?: \| |$)", rest)
        if m and m.group(1) in names:
            res[m.group(1)] = (m.group(2), m.group(3).strip())
    return res


def launch_builders(path, task):
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().split("\n")
    except IOError:
        return out
    for l in lines:
        if not l.startswith("LAUNCH "):
            continue
        head, sep, rest = l[7:].partition(": ")
        parts = rest.split(" | ")
        if not sep or len(parts) < 3:
            continue
        kind = parts[0]
        t = parts[1][5:] if parts[1].startswith("task ") else parts[1]
        if t == task and (re.match(r"worker \d+$", kind) or kind == "tm-pane"):
            out.append(parts[2].strip())
    return out


def tool_blocks(dirpath, base):
    """(blocks, sign) of `agent-level.sh check --base <base> --json` run in dirpath."""
    script = os.path.join(HERE, "agent-level.sh")
    try:
        p = subprocess.run([script, "check", "--base", base, "--json"], cwd=dirpath, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, stdin=subprocess.DEVNULL)
    except OSError as e:
        raise Refuse("checks gate: cannot run agent-level.sh: %s" % e, 2)
    if p.returncode != 0:
        why = " ".join(p.stderr.split()) or "exit %d" % p.returncode
        raise Refuse("checks gate: agent-level.sh check failed: %s" % why[:300], 2)
    try:
        d = json.loads(p.stdout)
        blocks = [b for b in d.get("blocks", [])]
        sign = d.get("sign") or []
        return blocks, bool(sign)
    except ValueError:
        pass
    for l in p.stdout.splitlines():   # the text form, when --json is not there yet
        if l.startswith("BLOCKS: "):
            blocks = [b.strip() for b in l[8:].split(",") if b.strip()]
            return blocks, SIGN in blocks
    raise Refuse("checks gate: agent-level.sh printed no BLOCKS", 2)


def cmd_gate(ctx, a):
    if not a:
        raise Refuse("checks gate: usage: checks gate \"<task>\" --dir <path> [--base <ref>] [--results <file>] [--checks \"<list>\"]", 2)
    task, rest = a[0], a[1:]
    opts, i = {}, 0
    while i < len(rest):
        if rest[i] in ("--dir", "--base", "--results", "--checks") and i + 1 < len(rest):
            opts[rest[i]] = rest[i + 1]
            i += 2
        else:
            raise Refuse("checks gate: unknown or incomplete option: %s" % rest[i], 2)
    if "--dir" not in opts:
        raise Refuse("checks gate: --dir <path> is needed", 2)
    d = opts["--dir"]
    if not os.path.isdir(d):
        raise Refuse("checks gate: no such folder: %s" % d, 2)
    base = opts.get("--base", "origin/main")
    f = Todo(ctx["root"]).fields(task)
    planned = set()
    builders = []
    if f is not None:
        c = field_of(f, "checks")
        if c:
            planned |= set(x.strip() for x in c.split(",") if x.strip())
        b = field_of(f, "builder")
        if b:
            builders += [x.strip() for x in b.split(",") if x.strip()]
    elif "--checks" not in opts:
        raise Refuse("checks gate: no todo line named %s here and no --checks" % task, 2)
    if "--checks" in opts:
        planned |= set(parse_list(opts["--checks"]))
    tools, sign = tool_blocks(d, base)
    planned |= set(t for t in tools if t != SIGN)
    if sign or SIGN in tools:
        planned.add(SIGN)
    plan = sorted(planned, key=order_key)
    results_path = opts.get("--results") or os.path.join(d, "agent_state.txt")
    res = read_results(results_path, task)
    for p in (os.path.join(d, "agent_state.txt"), os.path.join(ctx["root"], "agent_state.txt")):
        builders += launch_builders(p, task)
    lowb = set(b.lower() for b in builders)
    lines, refused, notes = [], [], []
    for b in plan:
        r = res.get(b)
        if r is None:
            lines.append("%s: missing" % b)
            refused.append("%s missing" % b)
        elif r[0] == "fail":
            lines.append("%s: fail (by %s)" % (b, r[1]))
            refused.append("%s fail" % b)
        elif b in BUILDER_BLOCKS and r[1].lower() in lowb:
            lines.append("%s: pass by the builder (%s), not accepted" % (b, r[1]))
            refused.append("%s by the builder" % b)
        else:
            lines.append("%s: pass (by %s)" % (b, r[1]))
            if b in BUILDER_BLOCKS and not lowb:
                notes.append("note: builder unknown: %s by %s accepted" % (b, r[1]))
    for l in lines + notes:
        print(l)
    if refused:
        print("GATE REFUSED %s: %s" % (task, ", ".join(refused)))
        sys.exit(1)
    print("GATE PASS %s" % task)


# -- next

def glob_dir(g):
    m = re.search(r"[*?\[]", g)
    if not m:
        return None
    pre = g[:m.start()]
    return pre[:pre.rfind("/") + 1]


def clash(a, b):
    da, db = glob_dir(a), glob_dir(b)
    if da is None and db is None:
        return a == b
    if da is None:
        return fnmatch.fnmatchcase(a, b)
    if db is None:
        return fnmatch.fnmatchcase(b, a)
    return da.startswith(db) or db.startswith(da)


def scope_of(f):
    s = field_of(f, "scope")
    return [x.strip() for x in s.split(",") if x.strip()] if s else []


def clash_with(scope, other):
    for x in scope:
        for y in other:
            if clash(x, y):
                return y
    return None


def cmd_next(ctx, a):
    if len(a) != 3:
        raise Refuse("next: internal: <max agents> <ram> <cap>", 2)
    mx, ram, cap = int(a[0]), int(a[1]), int(a[2])
    todo = Todo(ctx["root"])
    rows = [f for f in todo.open_lines() if len(f) >= 3]
    names_open = set(f[0] for f in rows)
    running = []     # open lines with a stage and no open wait
    staged = []      # open lines with a stage (wait or not): their files are taken
    cands = []
    for f in rows:
        stage = field_of(f, "stage") is not None
        waiting = field_of(f, "waiting")
        if stage:
            staged.append(f)
            if waiting is None:
                running.append(f)
            continue
        if waiting is not None:
            if not waiting.startswith("queue "):
                continue
        cands.append(f)
    free = max(0, mx - len(running))
    if free == 0:
        print("NEXT: 0 can start: no free slot (slots 0 of %d)" % mx)
        return
    if ram >= cap:
        print("NEXT: 0 can start: RAM %d%% is not under the cap %d%%" % (ram, cap))
        return
    starts, waits = [], []
    taken = [(f[0], scope_of(f)) for f in staged]
    for f in cands:
        name = f[0]
        w = field_of(f, "waiting")
        after = field_of(f, "after")
        if w is not None and after and after in names_open:
            waits.append("WAIT %s: after %s still open" % (name, after))
            continue
        sc = scope_of(f)
        hit = None
        for tname, tscope in taken:
            g = clash_with(sc, tscope) if sc and tscope else None
            if g:
                hit = (tname, g)
                break
        if hit:
            waits.append("WAIT %s: clashes with %s on %s" % (name, hit[0], hit[1]))
            continue
        if len(starts) >= free:
            waits.append("WAIT %s: no free slot" % name)
            continue
        est = field_of(f, "est")
        line = "START %s | est %s | %s" % (name, est or "-", f[2])
        if not sc:
            line += " | scope unknown: judge"
        starts.append(line)
        taken.append((name, sc))
    print("NEXT: %d can start (slots %d of %d, RAM %d%% under %d%%)" % (len(starts), free, mx, ram, cap))
    for l in starts + waits:
        print(l)


def cmd_after_list(ctx, a):
    """The open lines with a queue wait whose after is a[0]."""
    for f in Todo(ctx["root"]).open_lines():
        w = field_of(f, "waiting")
        if w is not None and w.startswith("queue ") and field_of(f, "after") == a[0]:
            print(f[0])


def cmd_edge_add(ctx, a):
    if len(a) != 1 or not a[0].strip():
        raise Refuse("edge add: needs one text in quotes")
    text = a[0].strip()
    if "\n" in text or "\r" in text:
        raise Refuse("edge add: the text must not hold a line break")
    path = os.path.join(ctx["state"], "agent_repo.conf")
    try:
        with open(path, encoding="utf-8", errors="surrogateescape") as fh:
            old = fh.read()
    except IOError:
        old = ""
    line = "edge=" + text
    if line in old.split("\n"):
        print("edge add: already listed")
        return
    if old and not old.endswith("\n"):
        old += "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(old + line + "\n")
    os.replace(tmp, path)
    print("edge add: %s" % text)


def main(argv):
    if len(argv) < 5:
        sys.stderr.write("agent_checks.py: internal use only\n")
        return 2
    ctx = {"root": argv[1], "state": argv[2], "now": argv[3]}
    cmd, a = argv[4], argv[5:]
    try:
        if cmd == "norm":
            cmd_norm(a)
        elif cmd == "todo-checks":
            cmd_todo_checks(ctx, a)
        elif cmd == "todo-builder":
            cmd_todo_builder(ctx, a)
        elif cmd == "todo-est":
            cmd_todo_est(ctx, a)
        elif cmd == "check":
            cmd_check(ctx, a)
        elif cmd == "gate":
            cmd_gate(ctx, a)
        elif cmd == "next":
            cmd_next(ctx, a)
        elif cmd == "after-list":
            cmd_after_list(ctx, a)
        elif cmd == "edge-add":
            cmd_edge_add(ctx, a)
        else:
            raise Refuse("unknown command: %s" % cmd, 2)
    except Refuse as e:
        sys.stderr.write(" ".join(str(e).split()) + "\n")
        return e.code
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
