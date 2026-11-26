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
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

FALLBACK = ["DIFF SCAN", "BUILD", "RELATED TESTS", "GUARD TESTS", "DB CHECK", "DATA CHECK", "FULL SUITE",
            "CORE REVIEW", "DIFF READ", "EXAMPLES TEST", "FLOW CHECK", "UI CHECK", "REAL DATA COUNT"]
SIGN = "OWNER SIGN"
BUILDER_BLOCKS = ("PR REVIEW", "CORE REVIEW", "FLOW CHECK", "UI CHECK")
NO_WB_NOTE = "note: no working branch stored in this clone: give --base origin/<working branch> (the brief names it)"
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


# ---------------------------------------------------------------- per-clone records (git common dir)

def common_dir(root):
    try:
        r = subprocess.run(["git", "-C", root, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
        out = r.stdout.decode(errors="replace").strip()
        return out if r.returncode == 0 and out else None
    except (OSError, subprocess.SubprocessError):
        return None


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (IOError, ValueError):
        return {}


def save_json(path, data):
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def block_record(root):
    gd = common_dir(root)
    return (os.path.join(gd, "agent_task_blocks.json") if gd else None)


def record_blocks(root, task, added=(), removed=()):
    """F11: blocks are only added. agent_task_blocks.json keeps per task the blocks ever planned and the
    verified removals; a block added again is no longer removed. -> (blocks, removed) now."""
    path = block_record(root)
    data = load_json(path) if path else {}
    rec = data.get(task) if isinstance(data.get(task), dict) else {}
    blocks = [b for b in rec.get("blocks", []) if isinstance(b, str)]
    gone = [b for b in rec.get("removed", []) if isinstance(b, str)]
    for b in added:
        if b not in blocks:
            blocks.append(b)
        if b in gone:
            gone.remove(b)
    for b in removed:
        if b not in gone:
            gone.append(b)
    blocks = sorted(blocks, key=order_key)
    if path and (added or removed):
        data[task] = {"blocks": blocks, "removed": gone}
        try:
            save_json(path, data)
        except OSError:
            pass
    return blocks, gone


# ---------------------------------------------------------------- commands

def cmd_norm(a):
    if len(a) != 1:
        raise Refuse("norm: one list", 2)
    print(", ".join(parse_list(a[0], True)))


def verify_owner(ctx, quote, when, prefix, question=None, repo=None):
    """Run agent-owner-order.sh verify with the main repo's absolute path; refuse unless it exits 0.
    Returns the typed minute of the prompt (first stdout line `OWNER ORDER verified <file> <date time>`), else ""."""
    cmd = [os.path.join(HERE, "agent-owner-order.sh"), "verify", "--repo",
           repo or os.path.abspath(ctx["root"]), "--quote", quote]
    if when:
        cmd += ["--time", when]
    if question:
        cmd += ["--question", question]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True, stdin=subprocess.DEVNULL)
        code, out = p.returncode, p.stdout
    except OSError as e:
        code, out = 127, str(e)
    if code != 0:
        why = " ".join(out.split()) or "exit %d" % code
        raise Refuse("%s%s" % (prefix, why[:300]))
    first = out.split("\n", 1)[0]
    m = re.match(r"OWNER ORDER verified \S+ (\d{4}-\d\d-\d\d \d\d:\d\d)\s*$", first)
    return m.group(1) if m else ""


def approval_values(cmd, quote, means, question):
    """The common approval options (section 53 A3): --owner-quote Q --means M [--question X]. -> (Q, M, X)."""
    quote, means = (quote or "").strip(), (means or "").strip()
    question = (question or "").strip() if question is not None else None
    if not quote:
        raise Refuse("%s: --owner-quote needs the owner's words" % cmd)
    if not means:
        raise Refuse("%s: --means \"<the action his words approve>\" is needed with --owner-quote" % cmd)
    for name, v in (("--owner-quote", quote), ("--means", means), ("--question", question)):
        if v is None:
            continue
        if "\n" in v or "\r" in v or " | " in v:
            raise Refuse("%s: %s must not hold a line break or \" | \"" % (cmd, name))
    if question is not None and not question:
        raise Refuse("%s: --question must not be empty" % cmd)
    return quote, means, question


def relay_value(cmd, folder):
    """--relayed-from <abs folder> (R3): the repo where the owner typed the words. -> the folder or None."""
    if folder is None:
        return None
    folder = folder.strip()
    if not folder or not os.path.isabs(folder):
        raise Refuse("%s: --relayed-from wants an absolute folder (got: %s)" % (cmd, folder or "nothing"))
    if "\n" in folder or "\r" in folder or " | " in folder:
        raise Refuse("%s: --relayed-from must not hold a line break or \" | \"" % cmd)
    why = relay_repo_refusal(folder)
    if why:
        raise Refuse("%s: %s" % (cmd, why))
    return folder


def relay_repo_refusal(folder):
    """S3: the folder must be a git repo whose main manager lock exists or existed (agent_main.lock or
    agent_main.closed in its git common dir). -> a refusal text or None."""
    try:
        r = subprocess.run(["git", "-C", folder, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True,
                           stdin=subprocess.DEVNULL, timeout=30)
        gd = r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        gd = ""
    if gd and any(os.path.exists(os.path.join(gd, m)) for m in ("agent_main.lock", "agent_main.closed")):
        return None
    return ("--relayed-from is not a repo with a main manager (no agent_main.lock or agent_main.closed "
            "in its git dir): %s" % folder)


def store_words(ctx, task, kind, block, quote, means, question, typed, when, relayed=None):
    gd = common_dir(ctx["root"])
    if not gd:
        return
    path = os.path.join(gd, "agent_owner_words.json")
    data = load_json(path)
    ent = data.get(task)
    if not isinstance(ent, dict) or "quote" in ent:     # an old flat record is not kept
        ent = {}
    rec = {"quote": quote, "means": means, "typed": typed, "time": when or ctx["now"], "verified": True}
    if question:
        rec["question"] = question
    if relayed:
        rec["relayed_from"] = relayed
    if kind == "publish":
        ent["publish"] = rec
    else:
        skip = ent.get("skip") if isinstance(ent.get("skip"), dict) else {}
        skip[block] = rec
        ent["skip"] = skip
    data[task] = ent
    save_json(path, data)


def cmd_owner_words(ctx, a):
    """owner-words <task> <quote> [<time> [<means> [<question>]]]: verify the owner's words at once; stored only
    when verified, with what the main manager read from them (F1, section 53)."""
    if len(a) < 2 or not a[0].strip() or not a[1].strip():
        raise Refuse("todo add: --target production needs --owner-quote \"<the owner's words>\" --means \"<the action>\" [--question \"<q>\"] [--time <t>]")
    task, when = a[0], (a[2] if len(a) > 2 else "")
    quote, means, question = approval_values("todo add", a[1], a[3] if len(a) > 3 else "",
                                             a[4] if len(a) > 4 and a[4] != "" else None)
    relayed = relay_value("todo add", a[5] if len(a) > 5 and a[5] != "" else None)
    typed = verify_owner(ctx, quote, when or None, "todo add: owner words not verified, nothing written: ", question, relayed)
    store_words(ctx, task, "publish", None, quote, means, question, typed, when, relayed)


def work_refusal(ctx, line):
    """The refusal text when this person may not work the task of this todo line (a shared todo), else None."""
    try:
        import agent_share
        return agent_share.may_work(ctx["root"], line if isinstance(line, str) else " | ".join(line))
    except ImportError:
        return None


def cmd_todo_target(ctx, a):
    """todo target <task> production --owner-quote Q --means M [--question X] [--time T] [--relayed-from <folder>]:
    the owner's yes after the task was added (FIX ORDER 1 R2). Same checks and record as todo add --target production."""
    if len(a) < 2 or not a[0].strip():
        raise Refuse("todo target: usage: todo target \"<task>\" production --owner-quote \"<words>\" --means \"<action>\" "
                     "[--question \"<q>\"] [--time <t>] [--relayed-from <folder>]")
    name, target, rest = a[0], a[1], a[2:]
    todo = Todo(ctx["root"])
    f = need_line(todo, name)
    why = work_refusal(ctx, f)
    if why:
        raise Refuse(why)
    if target != "production":
        raise Refuse("todo target: only production is set this way (got: %s)" % target)
    opts, i = {}, 0
    while i < len(rest):
        if rest[i] in ("--owner-quote", "--means", "--question", "--time", "--relayed-from") and i + 1 < len(rest):
            if rest[i] in opts:
                raise Refuse("todo target: %s given twice" % rest[i])
            opts[rest[i]] = rest[i + 1]
            i += 2
        else:
            raise Refuse("todo target: unknown or incomplete option: %s" % rest[i])
    if not opts.get("--owner-quote", "").strip():
        raise Refuse("todo target: production needs --owner-quote \"<the owner's words>\" and --means")
    quote, means, question = approval_values("todo target", opts.get("--owner-quote"), opts.get("--means"),
                                             opts.get("--question"))
    relayed = relay_value("todo target", opts.get("--relayed-from"))
    when = opts.get("--time")
    typed = verify_owner(ctx, quote, when, "todo target: owner words not verified, nothing written: ", question, relayed)
    at = field_index(f, "target")
    if at >= 0:
        f[at] = "target production"
    else:
        pos = anchor(f) + 1
        for p in ("checks", "scope", "builder"):
            j = field_index(f, p)
            if j >= 0:
                pos = max(pos, j + 1)
        f.insert(pos, "target production")
    store_words(ctx, name, "publish", None, quote, means, question, typed, when, relayed)
    todo.set(name, f)
    print("todo target: %s -> production" % name)
    import agent_conf
    prod = agent_conf.production_branch(ctx["root"])
    wb = agent_conf.working_branch(ctx["root"])
    print("next: a new fast-lane deputy makes a new branch from origin/%s with the task's own commits "
          "(git cherry-pick of git rev-list --reverse --no-merges origin/%s..origin/<branch>), every planned "
          "block runs again at its head, then agent-promote.sh --task %s --branch <new branch>"
          % (prod, wb or "<working branch>", name))


def cmd_task_end(ctx, a):
    """task-end done|drop <task> (G2, G4): the removals and the stored owner words end with the task instance;
    the brief blocks ever planned end at done only (a drop and a new add keep them, F11)."""
    kind, task = a[0], a[1]
    path = block_record(ctx["root"])
    if path:
        data = load_json(path)
        if task in data:
            if kind == "done":
                del data[task]
            elif isinstance(data[task], dict):
                data[task]["removed"] = []
            save_json(path, data)
    gd = common_dir(ctx["root"])
    if gd:
        wpath = os.path.join(gd, "agent_owner_words.json")
        words = load_json(wpath)
        if task in words:
            del words[task]
            save_json(wpath, words)


def cmd_plan_add(ctx, a):
    """plan-add <task> <checks>: the checks of a new todo line: the given ones plus the brief blocks this task
    name ever had, minus its verified removals (F11). Prints the list."""
    task = a[0]
    given = parse_list(a[1], True) if len(a) > 1 and a[1].strip() else []
    blocks, gone = record_blocks(ctx["root"], task, added=given)
    print(", ".join(b for b in blocks if b not in gone))


def cmd_todo_checks(ctx, a):
    if not a or not a[0].strip():
        raise Refuse("todo checks: needs a todo name")
    name, rest = a[0], a[1:]
    todo = Todo(ctx["root"])
    f = need_line(todo, name)
    cur = field_of(f, "checks")
    old = [x.strip() for x in cur.split(",")] if cur else []
    if rest and rest[0] == "--remove":
        why = work_refusal(ctx, f)
        if why:
            raise Refuse(why)
        opts, i = {}, 0
        while i < len(rest):
            if rest[i] in ("--remove", "--owner-quote", "--means", "--question", "--time", "--relayed-from") and i + 1 < len(rest):
                if rest[i] in opts:
                    raise Refuse("todo checks: %s given twice" % rest[i])
                opts[rest[i]] = rest[i + 1]
                i += 2
            else:
                raise Refuse("todo checks: unknown or incomplete option: %s" % rest[i])
        block = parse_list(opts["--remove"], True)
        if len(block) != 1:
            raise Refuse("todo checks: --remove takes one block")
        block = block[0]
        if not opts.get("--owner-quote", "").strip():
            raise Refuse("todo checks: --remove needs --owner-quote with the owner's words and --means")
        quote, means, question = approval_values("todo checks", opts.get("--owner-quote"), opts.get("--means"),
                                                 opts.get("--question"))
        if block in (SIGN, "PR REVIEW"):
            raise Refuse("todo checks: %s is never removed" % block)
        relayed = relay_value("todo checks", opts.get("--relayed-from"))
        typed = verify_owner(ctx, quote, opts.get("--time"), "todo checks: owner order not verified, nothing changed: ",
                             question, relayed)
        new = [b for b in old if b != block]
        at = field_index(f, "checks")
        removed = "removed %s %s" % (block, ctx["now"])
        if at >= 0:
            f[at:at + 1] = (["checks " + ", ".join(new)] if new else []) + [removed]
        else:       # a tool block (the diff plans it): only the removal is recorded
            f.insert(anchor(f) + 1, removed)
        record_blocks(ctx["root"], name, removed=[block])
        store_words(ctx, name, "skip", block, quote, means, question, typed, opts.get("--time"), relayed)
        print("todo checks: %s %s -> %s (removed %s)" % (name, ", ".join(old) or "-", ", ".join(new) or "-", block))
        todo.set(name, f)
        return
    if len(rest) != 1:
        raise Refuse("todo checks: usage: todo checks \"<name>\" <BLOCK>[,<BLOCK>] | --remove <BLOCK> --owner-quote \"<words>\" --means \"<action>\"")
    add = parse_list(rest[0], True)
    record_blocks(ctx["root"], name, added=add)
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
    add = mins.startswith("+")
    body = mins[1:] if add else mins
    if not (body.isdigit() and len(body) <= 9 and int(body) >= 1):
        raise Refuse("todo est: the minutes are a whole number, 1 or more (got: %s)" % mins)
    mins = str(int(body))
    old = field_of(f, "est")
    if add:     # added work: +<minutes> on top of the estimate now (guess stays)
        m = re.match(r"(\d+)m$", old or "")
        mins = str((int(m.group(1)) if m else 0) + int(mins))
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


def commit_of(folder, given=None):
    """F3: the commit a check saw, 12 hex digits: --commit <sha>, else HEAD of the folder the check runs in."""
    out = git_line(folder, "rev-parse", "--verify", "-q", "%s^{commit}" % (given or "HEAD"))
    if not out:
        if given:
            raise Refuse("check: %s is not a commit of this repo" % given)
        return ""
    return out[:12]


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
        if rest[i] in ("--by", "--evidence", "--owner-quote", "--means", "--question", "--time", "--commit", "--relayed-from") and i + 1 < len(rest):
            opts[rest[i]] = rest[i + 1]
            i += 2
        else:
            raise Refuse("check: unknown or incomplete option: %s" % rest[i])
    sign_pass = block == SIGN and verdict == "pass"
    if sign_pass:
        if not opts.get("--owner-quote", "").strip():
            raise Refuse("check: an OWNER SIGN pass needs --owner-quote \"<the owner's words>\" and --means")
        q, m, x = approval_values("check", opts.get("--owner-quote"), opts.get("--means"), opts.get("--question"))
        relayed = relay_value("check", opts.get("--relayed-from"))
        opts["--evidence"] = "owner order verified: %s | means: %s%s%s | typed: %s" % (
            q, m, " | question: " + x if x else "", " | relayed from: " + relayed if relayed else "", "@TYPED@")
    elif "--time" in opts:
        raise Refuse("check: --time belongs to an OWNER SIGN pass only")
    elif "--owner-quote" in opts:
        raise Refuse("check: --owner-quote belongs to an OWNER SIGN pass only")
    elif "--means" in opts or "--question" in opts or "--relayed-from" in opts:
        raise Refuse("check: --means, --question and --relayed-from belong to an OWNER SIGN pass only")
    for k in ("--by", "--evidence"):
        v = opts.get(k, "")
        if not v.strip():
            raise Refuse("check: %s is needed" % k)
        if "\n" in v or "\r" in v:
            raise Refuse("check: %s must not hold a line break" % k)
    if " | " in opts["--by"]:
        raise Refuse("check: --by must not hold \" | \"")
    if sign_pass:
        typed = verify_owner(ctx, opts["--owner-quote"].strip(), opts.get("--time"),
                             "check: owner order not verified, nothing written: ", (opts.get("--question") or "").strip() or None,
                             relay_value("check", opts.get("--relayed-from")))
        opts["--evidence"] = opts["--evidence"].replace("@TYPED@", typed or "-")
    import agent_state
    sha = commit_of(ctx["state"], opts.get("--commit"))
    at = " | at %s" % sha if sha else ""
    text = "CHECK %s %s: %s | by %s%s | %s" % (task, block, verdict, opts["--by"].strip(), at, opts["--evidence"].strip())
    saved = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        agent_state.add(ctx["state"], ctx["now"], [text], True)
    except Exception as e:
        sys.stdout = saved
        raise Refuse("check: %s" % e)
    finally:
        sys.stdout = saved
    print("check: %s %s %s (by %s)" % (task, block, verdict, opts["--by"].strip()))


# -- gate

def read_results(paths, task, since="", until=""):
    """block -> (verdict, who, evidence, at, date): the newest CHECK line of the task wins (the date at the end
    of the line; same minute: a fail wins; then the later file in paths, then the later line). A line dated
    before the day `since` (the todo line's opened date) is ignored."""
    best = {}
    for n, path in enumerate(paths):
        read_results_file(path, task, best, n, since, until)
    return dict((b, v[4:]) for b, v in best.items())


def read_results_file(path, task, best, n=0, since="", until=""):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().split("\n")
    except IOError:
        return best
    head = "CHECK %s " % task
    names = block_names() + [SIGN]
    for i, l in enumerate(lines):
        l = l.lstrip()                      # a REPORT carries its CHECK lines indented
        if not l.startswith(head):
            continue
        rest = l[len(head):]
        m = re.match(r"(.+?): (pass|fail) \| by (.*)$", rest)
        if m and m.group(1) in names:
            parts = m.group(3).split(" | ")
            who = parts[0].strip()
            at = ""
            if len(parts) >= 3 and re.match(r"at [0-9a-f]{7,40}$", parts[1].strip()):
                at = parts[1].strip()[3:]
                parts = [parts[0]] + parts[2:]
            if len(parts) >= 3:
                ev, date = " | ".join(parts[1:-1]), parts[-1].strip()
            else:
                ev, date = " | ".join(parts[1:]), ""
            if since and date and date < since:     # G9: before this task instance opened (to the minute)
                continue
            if until and date > until:      # G6: a line dated in the future is ignored
                continue
            key = (date, m.group(2) == "fail", n, i)
            old = best.get(m.group(1))
            if old is None or key >= old[:4]:
                best[m.group(1)] = key + (m.group(2), who, ev.strip(), at, date)
    return best


def cmd_gather(ctx, a):
    if not a or not a[0].strip():
        raise Refuse("checks gather: usage: checks gather \"<task>\" --dir <path>", 2)
    task, rest = a[0], a[1:]
    if len(rest) != 2 or rest[0] != "--dir":
        raise Refuse("checks gather: usage: checks gather \"<task>\" --dir <path>", 2)
    print("checks gather: %s %d lines" % (task, gather_lines(ctx, task, rest[1])))


def gather_lines(ctx, task, folder):
    """Append the task's CHECK lines of <folder>/agent_state.txt to the main repo's (lines there are skipped)."""
    src = os.path.join(folder, "agent_state.txt")
    dst = os.path.join(ctx["root"], "agent_state.txt")
    head = "CHECK %s " % task
    try:
        with open(src, encoding="utf-8", errors="replace") as fh:
            mine = [l for l in fh.read().split("\n") if l.startswith(head)]
    except IOError:
        mine = []
    try:
        with open(dst, encoding="utf-8", errors="replace") as fh:
            have = set(fh.read().split("\n"))
    except IOError:
        have = set()
    new = []
    for l in mine:
        if l not in have and l not in new:
            new.append(l)
    if new:
        with open(dst, "a", encoding="utf-8") as fh:
            try:
                if os.path.getsize(dst) > 0:
                    with open(dst, "rb") as rb:
                        rb.seek(-1, 2)
                        if rb.read(1) != b"\n":
                            fh.write("\n")
            except OSError:
                pass
            fh.write("\n".join(new) + "\n")
    return len(new)


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
        env = dict(os.environ)
        env.pop("CLAUDE_PROJECT_DIR", None)   # --dir decides, not a hook's or the watch's folder
        p = subprocess.run([script, "check", "--base", base, "--json"], cwd=dirpath, env=env, stdout=subprocess.PIPE,
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


def git_out(d, *args):
    p = subprocess.run(["git", "-C", d] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout


def tree_refusal(d):
    """A refusal text when d holds changes (tracked, or untracked and not ignored) other than agent_*.txt files."""
    code, out = git_out(d, "status", "--porcelain", "-z", "-uall")
    if code != 0:
        raise Refuse("checks gate: git status failed in %s" % d, 2)
    parts = out.split("\0")
    i = 0
    while i < len(parts):
        e = parts[i]
        i += 1
        if len(e) < 4:
            continue
        paths = [e[3:]]
        if e[0] in "RC" and i < len(parts):   # a rename lists the old path next
            paths.append(parts[i])
            i += 1
        for pth in paths:
            base = os.path.basename(pth)
            if not (base.startswith("agent_") and base.endswith(".txt")):
                return "uncommitted changes in %s (commit and push them, or drop them)" % d
    return None


def upstream_of(d):
    """(upstream name, upstream sha, HEAD sha), or None when the branch has no upstream."""
    code, name = git_out(d, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if code != 0:
        return None
    c1, up = git_out(d, "rev-parse", "@{u}")
    c2, head = git_out(d, "rev-parse", "HEAD")
    if c1 != 0 or c2 != 0:
        return None
    return name.strip(), up.strip(), head.strip()


def parse_sign(evidence):
    """owner order verified: <Q> | means: <M>[ | question: <X>] | typed: <minute or -> -> (Q, M, X, typed) or None."""
    pre = "owner order verified: "
    if not evidence.startswith(pre):
        return None
    parts = evidence[len(pre):].split(" | ")
    quote, means, question, typed, relayed = parts[0].strip(), None, None, "", None
    for p in parts[1:]:
        if p.startswith("means: "):
            means = p[7:].strip()
        elif p.startswith("question: "):
            question = p[10:].strip()
        elif p.startswith("relayed from: "):
            relayed = p[14:].strip()
        elif p.startswith("typed: "):
            typed = p[7:].strip()
    if not quote or not means:
        return None
    return quote, means, question or None, "" if typed == "-" else typed, relayed or None


def sign_believed(ctx, evidence):
    """An OWNER SIGN pass counts only with the means in its evidence and the quote that verify accepts again now,
    at the typed minute and with the question (section 53 A7)."""
    got = parse_sign(evidence)
    if not got:
        return False
    quote, _, question, typed, relayed = got
    try:
        verify_owner(ctx, quote, typed if re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d$", typed) else None, "", question, relayed)
    except Refuse:
        return False
    return True


def print_owner_words(ctx, task, d, opts, f):
    """A8: one OWNER WORDS line per stored approval of the task, before any GATE line."""
    def line(label, quote, typed, means, question, relayed=None):
        text = 'OWNER WORDS %s: "%s" (typed %s) read as: %s' % (label, quote, typed or "-", means)
        if question:
            text += ' | question: "%s"' % question
        if relayed:
            text += ' | relayed from %s' % relayed
        print(text)
    gd = common_dir(ctx["root"])
    ent = load_json(os.path.join(gd, "agent_owner_words.json")).get(task) if gd else None
    if isinstance(ent, dict):
        rec = ent.get("publish")
        if isinstance(rec, dict) and rec.get("quote") and rec.get("means"):
            line("publish", rec["quote"], rec.get("typed"), rec["means"], rec.get("question"), rec.get("relayed_from"))
        skip = ent.get("skip") if isinstance(ent.get("skip"), dict) else {}
        for block in sorted(skip, key=order_key):
            rec = skip[block]
            if isinstance(rec, dict) and rec.get("quote") and rec.get("means"):
                line("skip " + block, rec["quote"], rec.get("typed"), rec["means"], rec.get("question"), rec.get("relayed_from"))
    paths = [os.path.join(d, "agent_state.txt"), os.path.join(ctx["root"], "agent_state.txt")]
    if opts.get("--results"):
        paths.append(opts["--results"])
    opened = (field_of(f, "opened") or "") if f is not None else ""
    r = read_results(paths, task, opened, soon(ctx["now"])).get(SIGN)
    got = parse_sign(r[2]) if r and r[0] == "pass" else None
    if got:
        line(SIGN, got[0], got[3], got[1], got[2], got[4])


def git_line(d, *args):
    try:
        r = subprocess.run(["git", "-C", d] + list(args), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=30)
        return r.stdout.decode(errors="replace").strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def production_branch(root):
    """One function for everyone: agent_conf.production_branch (F13)."""
    import agent_conf
    return agent_conf.production_branch(root)


def default_base(root, d, f):
    """origin/<production> for a todo line with `target production`, else origin/<working branch>; when
    that does not exist, origin/<production>."""
    prod = "origin/" + production_branch(root)
    if f is not None and "target production" in [x.strip() for x in f]:
        return prod
    try:
        import agent_conf
        wb = agent_conf.working_branch(d)        # reads the stored name only (F10)
    except Exception:
        wb = None
    if not wb:
        print(NO_WB_NOTE)
        return prod
    if git_line(d, "rev-parse", "--verify", "-q", "refs/remotes/origin/%s^{commit}" % wb):
        return "origin/" + wb
    return prod


HEAD_BLOCKS = ("PR REVIEW", "FLOW CHECK", "UI CHECK", "OWNER SIGN", "DB CHECK", "DATA CHECK")
LAUNCH_KIND = {"PR REVIEW": ("reviewer", "reviewer"), "FLOW CHECK": ("check-deputy", "check deputy"),
               "UI CHECK": ("check-deputy", "check deputy")}


def read_launches(gd, task):
    """The guard's records of this task: [(type, by, at)] from <git common dir>/agent_launches.jsonl."""
    out = []
    if not gd:
        return out
    try:
        with open(os.path.join(gd, "agent_launches.jsonl"), encoding="utf-8", errors="replace") as fh:
            for l in fh:
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if isinstance(o, dict) and o.get("task") == task:
                    out.append((str(o.get("type", "")), str(o.get("by", "")), str(o.get("at", ""))))
    except IOError:
        pass
    return out


def launched(launches, kind, date):
    """A record of this kind by the main manager exists and the pass is dated at or after the newest."""
    ats = [at for (t, by, at) in launches if t == kind and by == "main"]
    return bool(ats) and bool(date) and date >= max(ats)


def clean_merge(d, shas):
    """G3: a two-parent merge is clean when its tree equals `git merge-tree --write-tree <p1> <p2>`."""
    if len(shas) != 3:
        return False
    try:
        r = subprocess.run(["git", "-C", d, "merge-tree", "--write-tree", shas[1], shas[2]],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    lines = r.stdout.decode(errors="replace").split("\n")
    return r.returncode == 0 and bool(lines[0]) and lines[0].strip() == git_line(d, "rev-parse", shas[0] + "^{tree}")


def on_branch(d, at, head, own):
    """G9: the commit of a pass is the head being merged or one of the branch's own commits (base..head)."""
    full = git_line(d, "rev-parse", "--verify", "-q", "%s^{commit}" % at)
    return bool(full) and (full == head or full in own)


def own_commits(d, head, base):
    """G9: the full shas of base..head (this branch's own commits)."""
    return set(git_line(d, "rev-list", "%s..%s" % (base, head)).split())


def at_head(d, at, head, base):
    """F3: the commit a pass saw is the head being merged, or every commit after it is a merge whose other
    parents are in the base and which is clean (G3). -> None when fine, else (reason, commit)."""
    full = git_line(d, "rev-parse", "--verify", "-q", "%s^{commit}" % at)
    if not full or not head:
        return ("stale", "")
    if full == head:
        return None
    stale = ("stale", "")
    try:
        if subprocess.run(["git", "-C", d, "merge-base", "--is-ancestor", full, head],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30).returncode != 0:
            return stale
    except (OSError, subprocess.SubprocessError):
        return stale
    if not git_line(d, "rev-parse", "--verify", "-q", "%s^{commit}" % base):
        return stale
    rows = git_line(d, "rev-list", "--parents", "%s..%s" % (full, head), "--not", base).splitlines()
    for row in rows:
        shas = row.split()
        if len(shas) < 3:
            return stale
        for p in shas[2:]:
            try:
                if subprocess.run(["git", "-C", d, "merge-base", "--is-ancestor", p, base],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  timeout=30).returncode != 0:
                    return stale
            except (OSError, subprocess.SubprocessError):
                return stale
        if not clean_merge(d, shas):
            return ("changed", shas[0][:12])
    return None


def soon(now):
    """The latest line date the gate believes: one minute after now."""
    try:
        import calendar
        t = calendar.timegm(time.strptime(now, "%Y-%m-%d %H:%M")) + 60
        return time.strftime("%Y-%m-%d %H:%M", time.gmtime(t))
    except ValueError:
        return ""


def shared_commits_line(ctx, f, d, branch):
    """S4a: a production task whose HEAD carries commits of the working branch (the test of agent_promote.direct)."""
    if f is None or "target production" not in [x.strip() for x in f]:
        return ""
    import agent_conf
    wb = agent_conf.working_branch(ctx["root"])
    if not wb:
        return ""
    prod = agent_conf.production_branch(ctx["root"])
    rc, o = git_out(d, "rev-list", "HEAD", "^origin/" + prod)
    if rc != 0:
        return ""
    own = set(o.split())
    rc, o = git_out(d, "rev-list", "refs/heads/" + wb, "^origin/" + prod)
    if rc != 0 or not own & set(o.split()):
        return ""
    name = branch or git_line(d, "rev-parse", "--abbrev-ref", "HEAD")
    return "%s carries commits of %s that are not in %s: branch it from %s" % (name, wb, prod, prod)


def cmd_gate(ctx, a):
    if not a:
        raise Refuse("checks gate: usage: checks gate \"<task>\" --dir <path> [--base <ref>] [--branch <b>] [--results <file>] [--checks \"<list>\"]", 2)
    task, rest = a[0], a[1:]
    opts, i = {}, 0
    while i < len(rest):
        if rest[i] in ("--dir", "--base", "--results", "--checks", "--branch") and i + 1 < len(rest):
            opts[rest[i]] = rest[i + 1]
            i += 2
        else:
            raise Refuse("checks gate: unknown or incomplete option: %s" % rest[i], 2)
    why = work_refusal(ctx, Todo(ctx["root"]).fields(task) or "")
    if why:
        print("GATE REFUSED %s: %s" % (task, why))
        sys.exit(1)
    print_owner_words(ctx, task, opts.get("--dir", ""), opts, Todo(ctx["root"]).fields(task))
    if "--dir" not in opts:
        raise Refuse("checks gate: --dir <path> is needed", 2)
    d = opts["--dir"]
    if not os.path.isdir(d):
        raise Refuse("checks gate: no such folder: %s" % d, 2)
    if opts.get("--branch"):
        want = git_line(d, "rev-parse", "--verify", "-q", "refs/remotes/origin/%s^{commit}" % opts["--branch"])
        if not want or want != git_line(d, "rev-parse", "HEAD"):
            print("GATE REFUSED %s: --dir is not on origin/%s" % (task, opts["--branch"]))
            sys.exit(1)
    f = Todo(ctx["root"]).fields(task)
    base = opts.get("--base") or default_base(ctx["root"], d, f)
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
    why = tree_refusal(d)
    if why:
        print("GATE REFUSED %s: %s" % (task, why))
        sys.exit(1)
    up = upstream_of(d)
    if up is None:
        print("note: no upstream: the gate plans this local HEAD")
    elif up[1] != up[2]:
        print("GATE REFUSED %s: HEAD is not its pushed branch %s" % (task, up[0]))
        sys.exit(1)
    tools, sign = tool_blocks(d, base)
    planned |= set(t for t in tools if t != SIGN)
    if sign or SIGN in tools:
        planned.add(SIGN)
    # F11: the brief blocks this task ever had come back; the verified removals are subtracted
    rec_blocks, gone = record_blocks(ctx["root"], task)
    planned |= set(rec_blocks)
    planned -= set(gone)
    if "--checks" in opts:
        planned |= set(parse_list(opts["--checks"], True))
    plan = sorted(planned, key=order_key)
    paths = [os.path.join(d, "agent_state.txt"), os.path.join(ctx["root"], "agent_state.txt")]
    if opts.get("--results"):
        paths.append(opts["--results"])
    if os.path.realpath(d) != os.path.realpath(ctx["root"]):
        gather_lines(ctx, task, d)      # A10: promote's own gate finds the lines of a task with no worktree line
    opened = (field_of(f, "opened") or "") if f is not None else ""
    res = read_results(paths, task, opened, soon(ctx["now"]))
    gd = common_dir(d) or common_dir(ctx["root"])
    launches = [x for x in read_launches(gd, task) if not opened or x[2] >= opened]
    head = git_line(d, "rev-parse", "HEAD")
    own = own_commits(d, head, base)
    for p in (os.path.join(d, "agent_state.txt"), os.path.join(ctx["root"], "agent_state.txt")):
        builders += launch_builders(p, task)
    lowb = set(b.lower() for b in builders)

    def is_builder(who):
        w = who.lower()
        t = task.lower()
        return w in lowb or w.startswith(t + " task manager") or w.startswith(t + " deputy") \
            or w.startswith(t + " worker")
    lines, refused, notes = [], [], []
    for b in plan:
        r = res.get(b)
        if r is None:
            lines.append("%s: missing" % b)
            refused.append("%s missing" % b)
        elif r[0] == "fail":
            lines.append("%s: fail (by %s)" % (b, r[1]))
            refused.append("%s fail" % b)
        elif b == SIGN and not sign_believed(ctx, r[2]):
            lines.append("%s: pass not verified, not accepted" % b)
            refused.append("%s not verified" % b)
        elif b in BUILDER_BLOCKS and is_builder(r[1]):
            lines.append("%s: pass by the builder (%s), not accepted" % (b, r[1]))
            refused.append("%s by the builder" % b)
        elif b in LAUNCH_KIND and not launched(launches, LAUNCH_KIND[b][0], r[4]):
            lines.append("%s: no %s launched by the main manager for %s, not accepted" % (b, LAUNCH_KIND[b][1], task))
            refused.append("%s not launched by the main manager" % b)
        elif not r[3]:
            lines.append("%s: pass with no commit, not accepted" % b)
            refused.append("%s no commit" % b)
        elif not on_branch(d, r[3], head, own):
            if b in HEAD_BLOCKS:
                lines.append("%s: pass at %s, not a commit of this branch (head %s), not accepted" % (b, r[3], head[:12]))
            else:
                lines.append("%s: the pass was at %s, not a commit of this branch, not accepted" % (b, r[3]))
            refused.append("%s not on this branch" % b)
        elif b in HEAD_BLOCKS and at_head(d, r[3], head, base) is not None:
            why = at_head(d, r[3], head, base)
            if why[0] == "changed":
                lines.append("%s: the merge after the review changed code (%s): review the new head" % (b, why[1]))
                refused.append("%s merge changed code" % b)
            else:
                lines.append("%s: pass at %s, not at the head %s, not accepted" % (b, r[3], head[:12]))
                refused.append("%s not at the head" % b)
        else:
            lines.append("%s: pass (by %s)" % (b, r[1]))
            if b in BUILDER_BLOCKS and not lowb:
                notes.append("note: builder unknown: %s by %s accepted" % (b, r[1]))
    if not own and git_line(d, "rev-parse", "--verify", "-q", "%s^{commit}" % base):
        notes.append("nothing to publish: %s has no commit on top of %s"
                     % (opts.get("--branch") or git_line(d, "rev-parse", "--abbrev-ref", "HEAD"), base))
        refused.append("nothing to publish")
    shared_line = shared_commits_line(ctx, f, d, opts.get("--branch"))
    if shared_line:
        notes.append(shared_line)
        refused.append("commits of the working branch")
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


def next_warns(ctx):
    """One WARN line per board warning (the board's own rules, agent_board.board_warnings)."""
    try:
        import agent_board
        plugin = os.path.dirname(HERE)
        for line in agent_board.board_warnings(ctx["root"], plugin, ctx["now"]):
            print(line)
    except Exception:
        pass


def cmd_next(ctx, a):
    next_lines(ctx, a)
    next_warns(ctx)


def next_lines(ctx, a):
    if len(a) == 1 and a[0] == "unknown":
        print("NEXT: 0 can start: RAM unknown")
        return
    if len(a) != 5:
        raise Refuse("next: internal: <used MB> <reserved MB> <limit MB> <pane MB> <limit %>", 2)
    used, reserved, limit, pane, pct = [int(x) for x in a]
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
    # the memory rule (section 25): in use + reserved + the panes planned here + one pane <= the limit
    room = limit - used - reserved
    free = max(0, room) // pane if pane > 0 else 0
    if free == 0:
        print("NEXT: 0 can start: no room: %d MB in use + %d MB reserved + %d MB for a pane > %d MB"
              % (used, reserved, pane, limit))
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
            waits.append("WAIT %s: no room for another pane" % name)
            continue
        est = field_of(f, "est")
        line = "START %s | est %s | %s" % (name, est or "-", f[2])
        if not sc:
            line += " | scope unknown: judge"
        starts.append(line)
        taken.append((name, sc))
    print("NEXT: %d can start (room %d MB under the %d%% limit)" % (len(starts), room, pct))
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
        elif cmd == "owner-words":
            cmd_owner_words(ctx, a)
        elif cmd == "todo-target":
            cmd_todo_target(ctx, a)
        elif cmd == "task-end":
            cmd_task_end(ctx, a)
        elif cmd == "plan-add":
            cmd_plan_add(ctx, a)
        elif cmd == "todo-builder":
            cmd_todo_builder(ctx, a)
        elif cmd == "todo-est":
            cmd_todo_est(ctx, a)
        elif cmd == "check":
            cmd_check(ctx, a)
        elif cmd == "gather":
            cmd_gather(ctx, a)
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
