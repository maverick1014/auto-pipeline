#!/usr/bin/env python3
"""agent_share.py: where the agent files live, and how the ones in git are shared (requirements/agent-files.md).

CLI: agent_share.py <project root> <cmd> ...
  show                       files: task_files=<v> task_take=<v> place=<ap-data|tree>, then one line per agent file
  commit "<message>"         the in-git files that differ from the tip of ap-data go into one commit on it, then push
  sync                       fetch origin ap-data, 3-way merge into the working copies, commit, push
  set <key> <value> [--no-commit] [--no-move]    task_files | task_take | task_place | data_branch
  ignore                     the five .gitignore lines by the place (data: present, tree: absent)
  move                       take the agent files out of the code branch, put the in-git ones on ap-data
  name                       the git user name of the project root ("" when none)
  place                      "data <branch>" or "tree"
  may-work <task>            the refusal text (exit 1) when the person may not work the task of a shared todo
  pull                       quiet sync before a decision (shared todo only)
  take <task> | assign <task> <name>    todo take / todo assign (the todo in git)

Facts live in agent_repo.conf ("key=value", "key = value" reads the same):
  task_files = local (default) | ideas | ideas,todo      task_take = owner (default) | anyone
  task_place = data (default) | tree                     tree: the files stay in the code tree (the cloud pack)
  data_branch = ap-data (default) | <a branch name>      a name git refuses, or a branch that holds code, is not used
Each of task_files, task_take, data_branch: the repo value wins, else the person's Configure setting, else the default.
files set task_files ideas|ideas,todo and files move (a Configure that shares, no repo task_files) write the missing
three values into agent_repo.conf, one code-branch commit, one line. The repo's own commit hooks run.
The in-git files: agent_completed.txt and agent_estimate.txt always; agent_ideas.txt and agent_todo.txt when
task_files names them; agent_worktree.txt never. Python 3.9, stdlib only. Git's own words never reach the output.
"""

import contextlib
import datetime
import os
import re
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agent_conf  # noqa: E402

AGENT_FILES = ("agent_todo.txt", "agent_ideas.txt", "agent_worktree.txt", "agent_completed.txt",
               "agent_estimate.txt")
UNION_FILES = ("agent_completed.txt", "agent_ideas.txt")
CONF = "agent_repo.conf"
TASK_FILES_VALUES = ("local", "ideas", "ideas,todo")
TASK_TAKE_VALUES = ("owner", "anyone")
TASK_PLACE_VALUES = ("data", "tree")
FALLBACK = "auto-pipeline"
MOVED = re.compile(r"\[rejected\].*\((?:non-fast-forward|fetch first)\)|^hint: .*fetch first", re.M)
ROUNDS = 4
DIR = ".ap-data/"          # where the files in git live on a branch that holds code (never at the root)


DEFAULT_BRANCH = "ap-data"
TEAM_KEYS = ("task_files", "task_take", "data_branch")


def timeout_s():
    """The one network timeout: share_net_timeout_s; AGENT_SHARE_TIMEOUT overrides it only under AGENT_TESTING=1."""
    value = agent_conf.CONSTANTS.get("share_net_timeout_s", 15)
    if os.environ.get("AGENT_TESTING") == "1":
        try:
            value = int(os.environ.get("AGENT_SHARE_TIMEOUT", value))
        except ValueError:
            pass
    return max(1, int(value))


# ------------------------------------------------------------------ git


class Res:
    def __init__(self, rc, out, err):
        self.rc, self.out, self.err = rc, out, err

    @property
    def ok(self):
        return self.rc == 0


def base_env():
    env = dict(os.environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_OBJECT_DIRECTORY",
                "GIT_COMMON_DIR"):
        env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["LC_ALL"] = "C"
    return env


_IDENT = {}


def ident_env(root):
    """The environment for a command that makes a commit: a fallback identity when the clone has none."""
    env = base_env()
    if root not in _IDENT:
        name = run(root, "config", "user.name").out.strip()
        email = run(root, "config", "user.email").out.strip()
        extra = {}
        if not name:
            extra["GIT_AUTHOR_NAME"] = extra["GIT_COMMITTER_NAME"] = FALLBACK
        if not email:
            extra["GIT_AUTHOR_EMAIL"] = extra["GIT_COMMITTER_EMAIL"] = FALLBACK + "@localhost"
        _IDENT[root] = extra
    env.update(_IDENT[root])
    return env


def run(root, *args, input=None, timeout=None, env=None):
    """git -C root args -> Res (text out). rc 124 on a timeout."""
    try:
        r = subprocess.run(["git", "-C", root] + list(args), input=input, capture_output=True,
                           env=env or base_env(), timeout=timeout)
    except subprocess.TimeoutExpired:
        return Res(124, "", "timed out")
    except OSError as exc:
        return Res(127, "", str(exc))
    return Res(r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace"))


def run_bytes(root, *args, input=None, env=None):
    try:
        r = subprocess.run(["git", "-C", root] + list(args), input=input, capture_output=True,
                           env=env or base_env(), timeout=timeout_s())
    except (subprocess.TimeoutExpired, OSError):
        return None
    return r.stdout if r.returncode == 0 else None


OFFLINE_FILE = "agent_share_offline"
NO_ANSWER = ("could not read from remote", "unable to access", "could not resolve host", "connection refused",
             "connection timed out", "network is unreachable", "does not appear to be a git repository",
             "operation timed out")
_NET = {"down": False, "said": False}


def offline_path(root):
    return os.path.join(common_dir(root), OFFLINE_FILE)


def hhmm(epoch):
    return datetime.datetime.fromtimestamp(epoch).strftime("%H:%M")


def no_answer(r):
    """True when the remote gave no answer (a timeout, or git could not reach it). A refusal is an answer."""
    low = r.err.lower()
    if r.rc == 124 or any(w in low for w in NO_ANSWER):
        return True
    return r.rc == 128 and "couldn't find remote ref" not in low


def net(root, *args, env=None, mult=1):
    """A network git call: its own process group (killed whole on the timeout), one timeout, and the offline rules:
    no call after a no-answer in this command, none while the marker is younger than share_offline_min. The
    result has .offline (no answer, or skipped for it)."""
    skipped = Res(125, "", "network skipped")
    skipped.offline = True
    if _NET["down"]:
        return skipped
    marker = offline_path(root)
    minutes = agent_conf.CONSTANTS.get("share_offline_min", 5)
    try:
        stamp_t = os.stat(marker).st_mtime
    except OSError:
        stamp_t = None
    if stamp_t is not None and datetime.datetime.now().timestamp() - stamp_t < minutes * 60:
        _NET["down"] = True
        if not _NET["said"]:
            _NET["said"] = True
            say("ap-data: origin did not answer at %s; the network is skipped until %s, the commits wait"
                % (hhmm(stamp_t), hhmm(stamp_t + minutes * 60)))
        return skipped
    limit = timeout_s() * mult
    try:
        p = subprocess.Popen(["git", "-C", root] + list(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=env or base_env(), start_new_session=True)
    except OSError as exc:
        r = Res(127, "", str(exc))
        r.offline = False
        return r
    try:
        out, err = p.communicate(timeout=limit)
        r = Res(p.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"))
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            p.communicate(timeout=3)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass
        r = Res(124, "", "timed out")
    r.offline = no_answer(r) if not r.ok else False
    if r.offline:
        _NET["down"] = True
        why = "timed out after %ds" % limit if r.rc == 124 else (first_line(r.err) or "no answer")
        try:
            with open(marker, "w") as fh:
                fh.write("%s\n" % hhmm(datetime.datetime.now().timestamp()))
            os.utime(marker, None)
        except OSError:
            pass
        if not _NET["said"]:
            _NET["said"] = True
            say("ap-data: no answer from origin (%s); the network is skipped for %d minutes, the commits wait"
                % (why, minutes))
    else:
        try:
            os.remove(marker)
        except OSError:
            pass
    return r


def first_line(text):
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return ""


def say(text):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def is_repo(root):
    return os.path.isdir(root) and run(root, "rev-parse", "--git-dir").ok


def has_origin(root):
    return run(root, "remote", "get-url", "origin").ok


def tip(root, ref=None):
    r = run(root, "rev-parse", "-q", "--verify", (ref or local_ref(root)) + "^{commit}")
    return r.out.strip() if r.ok else ""


def ancestor(root, a, b):
    return run(root, "merge-base", "--is-ancestor", a, b).ok


def commit_time(root, sha):
    if not sha:
        return 0
    try:
        return int(run(root, "log", "-1", "--format=%ct", sha).out.strip())
    except ValueError:
        return 0


def tree_entries(root, commit):
    """name -> blob sha of a flat tree."""
    out = {}
    if not commit:
        return out
    r = run(root, "ls-tree", "-z", commit)
    for rec in r.out.split("\0"):
        if not rec or "\t" not in rec:
            continue
        meta, name = rec.split("\t", 1)
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob":
            out[name] = parts[2]
    return out


def blob(root, commit, name):
    """The text of a file on a commit, None when it is not there."""
    if not commit:
        return None
    data = run_bytes(root, "show", "%s:%s" % (commit, name))
    return None if data is None else data.decode("utf-8", "surrogateescape")


# ------------------------------------------------------------------ facts


def read_conf(root):
    out = {}
    try:
        with open(os.path.join(root, CONF), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                out[key.strip()] = value.strip()
    except OSError:
        pass
    return out


def setting_fact(key, default):
    """The person's Configure setting for a fact, else the default (no such setting, or any error)."""
    try:
        import agent_conf
        value = agent_conf.get(key)
        if isinstance(value, tuple):
            value = value[0]
        return str(value).strip() if value not in (None, "") else default
    except Exception:
        return default


def fact(root, key, allowed, default):
    """ONE reader of a fact: the repo value (agent_repo.conf) when the key is there, else the Configure setting,
    else the default."""
    raw = read_conf(root).get(key)
    if raw is None:
        raw = setting_fact(key, default)
    raw = raw.replace(" ", "")
    return raw if raw in allowed else default


def facts(root):
    return {"task_files": fact(root, "task_files", TASK_FILES_VALUES, "local"),
            "task_take": fact(root, "task_take", TASK_TAKE_VALUES, "owner"),
            "task_place": read_conf(root).get("task_place", "") if read_conf(root).get("task_place") in TASK_PLACE_VALUES
            else "data"}


_BRANCH = {}
_KIND = {}
_SAID = set()
REMOTE_NS = "refs/auto-pipeline/remote/"
BASE_NS = "refs/auto-pipeline/data-base/"
PENDING_NS = "refs/auto-pipeline/data-pending/"


def reset_cache():
    _BRANCH.clear()
    _KIND.clear()
    _MOVED.clear()


def wanted_branch(root):
    """The data branch name asked for: agent_repo.conf data_branch=, else the Configure setting, else ap-data."""
    raw = read_conf(root).get("data_branch")
    if raw is None:
        raw = setting_fact("data_branch", DEFAULT_BRANCH)
    return raw.strip() or DEFAULT_BRANCH


def holds_code(root, b):
    """True when B is the production or the working branch, the current branch, or a branch (local or on origin)
    whose tree has a path that is not an agent file."""
    names = set()
    try:
        import agent_conf
        names.add(agent_conf.production_branch(root))
        names.add(agent_conf.working_branch(root) or "")
    except Exception:
        pass
    names.add(run(root, "symbolic-ref", "--short", "-q", "HEAD").out.strip())
    if b in names:
        return True
    for ref in ("refs/heads/" + b, "refs/remotes/origin/" + b, REMOTE_NS + b):
        if not run(root, "rev-parse", "-q", "--verify", ref + "^{commit}").ok:
            continue
        listing = run(root, "ls-tree", "-r", "--name-only", "-z", ref).out
        if any(p and p not in AGENT_FILES for p in listing.split("\0")):
            return True
    return False


def refusal(root, b):
    """"" when B may be the data branch, else the one line that says why not."""
    if b == DEFAULT_BRANCH or not is_repo(root):
        return ""
    if b.startswith("-") or b == "HEAD" or "@{" in b or not run(root, "check-ref-format", "--branch", b).ok:
        return "data branch %s is not a branch name: not used, the files in git stay on %s" % (b, DEFAULT_BRANCH)
    if holds_code(root, b) and not has_origin(root):
        return "data branch %s holds code and needs an origin: not used, the files in git stay on %s" % (
            b, DEFAULT_BRANCH)
    return ""


def data_branch(root):
    """(the data branch in use, the refusal line or ""). One rule: repo value, else Configure, else ap-data; a
    name git refuses or a branch that holds code is not used (the default is)."""
    if root not in _BRANCH:
        wanted = wanted_branch(root)
        why = refusal(root, wanted)
        _BRANCH[root] = (DEFAULT_BRANCH, why) if why else (wanted, "")
        code = not why and wanted != DEFAULT_BRANCH and is_repo(root) and holds_code(root, wanted)
        _KIND[root] = "code" if code else "own"
    return _BRANCH[root]


def on_code_branch(root):
    """True when the files in git live under .ap-data/ of a branch that holds code (place says so)."""
    return place(root)[0] == "data" and _KIND.get(root) == "code" and is_repo(root)


def branch(root):
    return data_branch(root)[0]


def local_ref(root):
    return "refs/heads/" + branch(root)


def remote_ref(root):
    return "refs/remotes/origin/" + branch(root)


def announce(root):
    """A command that writes says once that a refused data branch is not used."""
    why = data_branch(root)[1]
    if why and root not in _SAID:
        _SAID.add(root)
        say(why)


def place(root):
    """Where the files in git go: ("data", <data branch>) or ("tree", None). The one place that says it."""
    if facts(root)["task_place"] == "tree":
        return ("tree", None)
    return ("data", branch(root))


def in_git_files(root):
    shared = facts(root)["task_files"]
    names = ["agent_completed.txt", "agent_estimate.txt"]
    if shared in ("ideas", "ideas,todo"):
        names.append("agent_ideas.txt")
    if shared == "ideas,todo":
        names.append("agent_todo.txt")
    return [n for n in AGENT_FILES if n in names]


_MOVED = {}
IGNORE_MARK = "agent_completed.txt"


def moved(root):
    """True for a moved repo: the exact line agent_completed.txt in .gitignore (read first, cheap) and no agent file
    tracked in the main checkout. A repo that still tracks one behaves as before the data branch existed."""
    if root not in _MOVED:
        text = read_file(root, ".gitignore")
        ok = bool(text) and IGNORE_MARK in text.split("\n") and is_repo(root)
        if ok:
            ok = not run(root, "ls-files", "--", *AGENT_FILES).out.strip()
        _MOVED[root] = ok
    return _MOVED[root]


def active(root):
    return place(root)[0] == "data" and is_repo(root) and moved(root)


# ------------------------------------------------------------------ the kept copies


def kept_dir(root):
    return os.path.join(common_dir(root), "agent-files-kept")


def keep(root, *names):
    """Copy the working copies NAMES (default: the five) to <git common dir>/agent-files-kept/<file> in a moved
    repo. A file that is not there is skipped."""
    try:
        if not moved(root):
            return
        target = kept_dir(root)
        for n in names or AGENT_FILES:
            src = os.path.join(root, n)
            if os.path.isfile(src):
                os.makedirs(target, exist_ok=True)
                tmp = os.path.join(target, "%s.tmp.%d" % (n, os.getpid()))
                shutil.copyfile(src, tmp)
                os.replace(tmp, os.path.join(target, n))
    except OSError:
        pass


def saved_copies(root, name):
    """The saved copies of NAME as (mtime, file name, path), newest first."""
    out = []
    try:
        for n in os.listdir(kept_dir(root)):
            p = os.path.join(kept_dir(root), n)
            if n.startswith(name + ".before-") and os.path.isfile(p):
                out.append((os.path.getmtime(p), n, p))
    except OSError:
        pass
    return sorted(out, reverse=True)


def cmd_restore(root, name, arg=None):
    """A saved copy of NAME (the newest by default, or the one named, or --list) becomes the working copy and the
    kept copy; the current working copy is saved first as a new saved copy (never swept); committed like a write."""
    if name not in AGENT_FILES:
        sys.stderr.write("files restore: %s is not one of the agent files\n" % name)
        return 1
    if not moved(root):
        sys.stderr.write("files restore: this repo is not moved, there are no kept copies\n")
        return 1
    saved = saved_copies(root, name)
    if arg == "--list":
        for _, n, p in saved:
            try:
                with open(p, "rb") as f:
                    lines = len(f.read().splitlines())
            except OSError:
                lines = 0
            say("%s %d lines" % (n, lines))
        return 0
    if arg is not None:
        base = os.path.basename(arg)
        if os.path.dirname(arg) and os.path.realpath(os.path.dirname(arg)) != os.path.realpath(kept_dir(root)):
            base = ""
        hit = [x for x in saved if x[1] == base]
        if not hit:
            sys.stderr.write("files restore: no saved copy %s of %s\n" % (arg, name))
            return 1
        path = hit[0][2]
    elif saved:
        path = saved[0][2]
    else:
        sys.stderr.write("files restore: no saved copy of %s\n" % name)
        return 1
    work = os.path.join(root, name)
    new = None
    try:
        if os.path.isfile(work):
            os.makedirs(kept_dir(root), exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            new = os.path.join(kept_dir(root), "%s.before-%s" % (name, stamp))
            i = 0
            while os.path.exists(new):
                i += 1
                new = os.path.join(kept_dir(root), "%s.before-%s-%d" % (name, stamp, i))
            shutil.copy2(work, new)
        tmp = os.path.join(root, "%s.tmp.%d" % (name, os.getpid()))
        shutil.copyfile(path, tmp)
        os.replace(tmp, work)
    except OSError as e:
        sys.stderr.write("files restore: %s\n" % e)
        return 1
    keep(root, name)
    if new:
        say("restored %s from %s; the copy before it is saved as %s (undo: agent-file.sh files restore %s %s)"
            % (name, path, new, name, os.path.basename(new)))
    else:
        say("restored %s from %s; there was no working copy, nothing saved" % (name, path))
    try:
        commit(root, "files restore " + name)
    except Exception:
        pass
    return 0


# ------------------------------------------------------------------ who may work a shared task


def todo_shared(root):
    return facts(root)["task_files"] == "ideas,todo"


def field_value(line, prefix):
    """The value of the field "<prefix> <value>" after the third field of a todo line (it ends at the next " | ")."""
    for f in (line or "").split(" | ")[3:]:
        if f.startswith(prefix + " "):
            return f[len(prefix) + 1:].strip()
    return None


def may_work(root, line):
    """None when the person may work the task of this todo line, else the refusal text. A local todo: always None."""
    if not line or not todo_shared(root):
        return None
    task = task_name(line)
    me = agent_conf.user_name(root)
    taken, assignee, owner = field_value(line, "taken"), field_value(line, "assignee"), field_value(line, "owner")
    if taken:
        return None if agent_conf.same_person(me, taken) else "%s was taken by %s" % (task, taken)
    if assignee:
        return None if agent_conf.same_person(me, assignee) else "%s is assigned to %s" % (task, assignee)
    if owner:
        if facts(root)["task_take"] == "owner":
            return None if agent_conf.same_person(me, owner) else ("%s belongs to %s; ask them to assign it (your git name is %s; if %s was your name, set git user.name back to \"%s\", "
                                                                       "then todo assign your tasks to the new name)" % (task, owner, me, owner, owner))
        return "%s is free: take it first (agent-file.sh todo take %s)" % (task, task)
    return None


def todo_line(root, task):
    for line in lines_of(read_file(root, "agent_todo.txt")):
        if task_name(line) == task:
            return line
    return None


def quietly(fn, *args):
    with open(os.devnull, "w") as dn, contextlib.redirect_stdout(dn):
        return fn(*args)


def pull(root):
    """Before a decision: when the todo is in git, a quiet sync (short timeout). A failure = the local file."""
    try:
        if not todo_shared(root) or not active(root) or not has_origin(root):
            return
        quietly(sync, root, "files sync")
    except Exception:
        pass


def cmd_may_work(root, task):
    text = may_work(root, todo_line(root, task))
    if text:
        say(text)
        return 1
    return 0


def put_todo_line(root, task, new):
    parts = (read_file(root, "agent_todo.txt") or "").split("\n")
    for i, l in enumerate(parts):
        if task_name(l) == task and l != "":
            parts[i] = new
            break
    write_file(os.path.join(root, "agent_todo.txt"), "\n".join(parts))
    keep(root, "agent_todo.txt")


def with_field(line, prefix, value):
    """LINE with the field "<prefix> <value>" written (replaced after the third field, else appended)."""
    fields = line.split(" | ")
    for i in range(3, len(fields)):
        if fields[i].startswith(prefix + " "):
            fields[i] = "%s %s" % (prefix, value)
            return " | ".join(fields)
    return line + " | %s %s" % (prefix, value)


def refuse_todo(text):
    sys.stderr.write(text + "\n")
    return 1


def cmd_assign(root, task, who):
    if not todo_shared(root):
        return refuse_todo("todo assign: the todo is local (task_files is not ideas,todo): assign needs task_files=ideas,todo")
    if not who.strip() or " | " in who or "\n" in who:
        return refuse_todo("todo assign: the name must not be empty or hold \" | \" or a line break")
    pull(root)
    line = todo_line(root, task)
    if line is None:
        return refuse_todo("todo assign: no todo line named: %s" % task)
    owner = field_value(line, "owner")
    if owner and not agent_conf.same_person(agent_conf.user_name(root), owner):
        return refuse_todo("%s belongs to %s; only the owner assigns" % (task, owner))
    put_todo_line(root, task, with_field(line, "assignee", who.strip()))
    commit(root, "todo assign %s" % task)
    say("todo assign: %s -> %s" % (task, who.strip()))
    return 0


def take_guard(task, me, state):
    """Called with the remote tip before a sync of a failed push: another taker there = the local line becomes
    the remote's line. True when that happened."""
    def guard(root, remote):
        text = blob(root, remote, (DIR if on_code_branch(root) else "") + "agent_todo.txt")
        line = None
        for l in lines_of(text):
            if task_name(l) == task:
                line = l
                break
        who = field_value(line, "taken") if line else None
        if who and not agent_conf.same_person(who, me):
            state["lost"] = who
            put_todo_line(root, task, line)
            return True
        return False
    return guard


def cmd_take(root, task):
    if not todo_shared(root):
        return refuse_todo("todo take: the todo is local (task_files is not ideas,todo): take needs task_files=ideas,todo")
    pull(root)
    line = todo_line(root, task)
    if facts(root)["task_take"] == "owner":
        owner = field_value(line, "owner") if line else None
        return refuse_todo("todo take: task_take is owner; ask %s to assign it" % (owner or "the owner"))
    if line is None:
        return refuse_todo("todo take: no todo line named: %s" % task)
    me = agent_conf.user_name(root)
    taken, assignee = field_value(line, "taken"), field_value(line, "assignee")
    if taken:
        if agent_conf.same_person(me, taken):
            say("todo take: %s is already yours" % task)
            return 0
        return refuse_todo("todo take: %s was taken by %s" % (task, taken))
    if assignee and not agent_conf.same_person(me, assignee):
        return refuse_todo("todo take: %s is assigned to %s" % (task, assignee))
    put_todo_line(root, task, with_field(line, "taken", me))
    state = {}
    guard = take_guard(task, me, state)
    announce(root)
    if not active(root):
        pass
    elif on_code_branch(root):
        code_cycle(root, "todo take %s" % task, guard=guard)
    elif commit_core(root, "todo take %s" % task):
        publish(root, guard=guard)
    if state.get("lost"):
        return refuse_todo("todo take: %s was taken by %s" % (task, state["lost"]))
    say("todo take: %s is yours" % task)
    return 0


# ------------------------------------------------------------------ files


def read_file(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="surrogateescape", newline="") as fh:
            return fh.read()
    except OSError:
        return None


def write_file(path, text):
    tmp = "%s.tmp.%d" % (path, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
            fh.write(text)
        try:
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        except OSError:
            pass
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def put_blob(root, text):
    out = run_bytes(root, "hash-object", "-w", "--no-filters", "--stdin", input=text.encode("utf-8", "surrogateescape"))
    return out.decode().strip() if out else ""


def make_commit(root, entries, parents, message):
    lines = "".join("100644 blob %s\t%s\n" % (sha, n) for n, sha in sorted(entries.items()))
    env = ident_env(root)
    t = run(root, "mktree", input=lines.encode("utf-8"), env=env)
    if not t.ok:
        return ""
    args = ["commit-tree", t.out.strip(), "-m", message]
    for p in parents:
        args += ["-p", p]
    c = run(root, *args, env=env)
    return c.out.strip() if c.ok else ""


def move_ref(root, new, old):
    return run(root, "update-ref", local_ref(root), new, old or "0" * 40).ok


# ------------------------------------------------------------------ the commit


def commit_core(root, message):
    """The in-git working copies that differ from the local tip go into one new commit. True when made."""
    local = tip(root)
    ents = tree_entries(root, local)
    new, changed = dict(ents), False
    for n in in_git_files(root):
        text = read_file(root, n)
        if text is None or (text == "" and n not in ents):
            continue
        sha = put_blob(root, text)
        if sha and ents.get(n) != sha:
            new[n] = sha
            changed = True
    if not changed:
        return False
    made = make_commit(root, new, [local] if local else [], message)
    return bool(made) and move_ref(root, made, local)


def why_text(r):
    line = first_line(r.err) or first_line(r.out) or "push failed"
    low = line.lower()
    if "identity" in low or "user.name" in low or "user.email" in low:
        line = "push failed"
    return line


def remote_moved(root):
    """Fetch origin's data branch and compare: True when its tip holds something the local tip lacks."""
    if not fetch(root):
        return False
    remote, local = tip(root, remote_ref(root)), tip(root)
    return bool(remote) and remote != local and not ancestor(root, remote, local)


def publish(root, guard=None):
    """Push ap-data. A push that failed while a fetch shows the remote moved (git's words alone are not the test):
    sync, push again. Any other failure: one line. GUARD(root, remote tip) is asked before each sync; a true
    answer ends the loop after one sync and one push. True when the push went through."""
    if not has_origin(root) or not tip(root):
        return True
    for turn in range(ROUNDS):
        r = net(root, "push", "-q", "origin", "%s:refs/heads/%s" % (local_ref(root), branch(root)))
        if r.ok:
            return True
        if r.offline:
            return False
        if turn < ROUNDS - 1 and (remote_moved(root) or MOVED.search(r.err)):
            if guard and guard(root, tip(root, remote_ref(root))):
                sync_core(root, "sync")
                return publish(root)
            sync_core(root, "sync")
            continue
        say("%s: not pushed (%s); the next write pushes it" % (branch(root), why_text(r)))
        return False
    return False


def code_cycle(root, message, force=(), guard=None):
    new_done = _code_cycle(root, message, force, guard)
    if new_done:
        start_estimator(root)
    return new_done


def _code_cycle(root, message, force=(), guard=None):
    """A write or a sync on a branch that holds code. The remote tip is fetched (refs/auto-pipeline/remote/<b>);
    theirs = its .ap-data/ files, base = the data of the last remote commit this clone synced with or pushed
    (refs/auto-pipeline/data-base/<b>), ours = the working copies. The merge goes into the working copies; when it
    differs from the remote's data ONE commit is built on the remote tip (its whole tree, only .ap-data/ entries
    replaced, a temporary index) and pushed to refs/heads/<b>. refs/heads/<b>, HEAD and every index stay where they
    are. True when new finished-task lines came in."""
    b = branch(root)
    new_done = False
    if not has_origin(root):
        return False
    rref, bref, pref = REMOTE_NS + b, BASE_NS + b, PENDING_NS + b
    for turn in range(ROUNDS):
        if fetch_code(root).offline:
            return new_done
        remote = tip(root, rref)
        if not remote:
            say("%s: not pushed (origin has no %s yet); the next write pushes it" % (b, b))
            return new_done
        if guard:
            guard(root, remote)
        base = tip(root, bref)
        t_remote, t_base = commit_time(root, remote), commit_time(root, base)
        now = int(datetime.datetime.now().timestamp())
        ents_r = tree_entries(root, remote + ":" + DIR.rstrip("/"))
        replace = {}
        for n in in_git_files(root):
            work = read_file(root, n)
            r_text, b_text = blob(root, remote, DIR + n), blob(root, base, DIR + n)
            ours_time = now if (work or "") != (b_text or "") else t_base
            result = merge_file(n, b_text, work, r_text, ours_time, t_remote)
            if result != (work or "") and not (work is None and result == ""):
                write_file(os.path.join(root, n), result)
                keep(root, n)
                if n == "agent_completed.txt" and set(lines_of(result)) - set(lines_of(work)):
                    new_done = True
            if result != "" or n in ents_r or n in force:
                sha = put_blob(root, result)
                if sha and ents_r.get(n) != sha:
                    replace[n] = sha
        if not replace:
            run(root, "update-ref", bref, remote)
            run(root, "update-ref", "-d", pref)
            return new_done
        made = build_code_commit(root, remote, replace, message)
        if not made:
            say("%s: not pushed (the commit could not be built); the next write pushes it" % b)
            return new_done
        run(root, "update-ref", pref, made)
        r = net(root, "push", "-q", "origin", "%s:refs/heads/%s" % (made, b))
        if r.ok:
            run(root, "update-ref", bref, made)
            run(root, "update-ref", rref, made)
            run(root, "update-ref", "-d", pref)
            return new_done
        if r.offline:
            return new_done
        fetch_code(root)
        moved = tip(root, rref)
        if moved and moved != remote and turn < ROUNDS - 1:
            continue
        say("%s: not pushed (%s); the next write pushes it" % (b, why_text(r)))
        return new_done
    return new_done


def fetch_code(root):
    b = branch(root)
    return net(root, "fetch", "-q", "origin", "+refs/heads/%s:%s%s" % (b, REMOTE_NS, b))


def build_code_commit(root, parent, replace, message):
    """The tree of PARENT with only the .ap-data/ entries in REPLACE ({file: blob}) replaced, one commit on it."""
    tmp = os.path.join(common_dir(root), "ap-data-index.%d" % os.getpid())
    env = ident_env(root)
    env["GIT_INDEX_FILE"] = tmp
    try:
        if not run(root, "read-tree", parent, env=env).ok:
            return ""
        for n, sha in replace.items():
            if not run(root, "update-index", "--add", "--cacheinfo", "100644,%s,%s%s" % (sha, DIR, n), env=env).ok:
                return ""
        t = run(root, "write-tree", env=env)
        if not t.ok:
            return ""
        c = run(root, "commit-tree", t.out.strip(), "-p", parent, "-m", message, env=env)
        return c.out.strip() if c.ok else ""
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def data_entries(root):
    """The in-git files as the data branch holds them now: name -> blob."""
    if on_code_branch(root):
        r = tip(root, REMOTE_NS + branch(root))
        return tree_entries(root, r + ":" + DIR.rstrip("/")) if r else {}
    return tree_entries(root, tip(root))


def commit(root, message):
    if not active(root):
        return
    announce(root)
    if on_code_branch(root):
        code_cycle(root, message)
        return
    if commit_core(root, message):
        publish(root)


# ------------------------------------------------------------------ the merge


def lines_of(text):
    return [l for l in (text or "").split("\n") if l != ""]


def join_lines(lines):
    return "".join(l + "\n" for l in lines)


def union_merge(base, ours, theirs):
    b, o, t = lines_of(base), lines_of(ours), lines_of(theirs)
    gone = (set(b) - set(o)) | (set(b) - set(t))
    seen = set(o)
    out = [l for l in o if l not in (set(b) - set(t))]
    for l in t:
        if l not in seen and l not in gone and l not in set(b):
            out.append(l)
            seen.add(l)
    return join_lines(out)


def task_name(line):
    return line.split(" | ", 1)[0]


def todo_map(text):
    out = {}
    for line in lines_of(text):
        out.setdefault(task_name(line), line)
    return out


def todo_merge(base, ours, theirs, ours_time, theirs_time):
    b, o, t = todo_map(base), todo_map(ours), todo_map(theirs)
    newer = o if ours_time >= theirs_time else t
    got = {}
    for n in list(o) + [n for n in t if n not in o]:
        bl, ol, tl = b.get(n), o.get(n), t.get(n)
        if bl is not None and (ol is None or tl is None):
            continue
        if ol is not None and tl is not None:
            if ol == tl or tl == bl:
                got[n] = ol
            elif ol == bl:
                got[n] = tl
            else:
                got[n] = newer[n]
        else:
            got[n] = ol if ol is not None else tl
    order = [n for n in o if n in got] + [n for n in t if n in got and n not in o]
    return join_lines([got[n] for n in order])


def merge_file(file_name, base, ours, theirs, ours_time, theirs_time):
    base, ours, theirs = base or "", ours or "", theirs or ""
    if file_name == "agent_estimate.txt":
        return ours or theirs
    if ours == theirs or theirs == base:
        return ours
    if ours == base:
        return theirs
    if file_name == "agent_todo.txt":
        return todo_merge(base, ours, theirs, ours_time, theirs_time)
    if file_name in UNION_FILES:
        return union_merge(base, ours, theirs)
    return ours


def fetch(root):
    if not has_origin(root):
        return False
    return net(root, "fetch", "-q", "origin", "+%s:%s" % (local_ref(root), remote_ref(root))).ok


def sync_core(root, message):
    """Fetch, merge into the working copies, commit. Returns True when new finished-task lines came in."""
    if not active(root):
        return False
    fetch(root)
    local, remote = tip(root), tip(root, remote_ref(root))
    ents_l, ents_r = tree_entries(root, local), tree_entries(root, remote)
    base = ""
    if local and remote:
        if local == remote or ancestor(root, local, remote):
            base = local
        elif ancestor(root, remote, local):
            base = remote
        else:
            mb = run(root, "merge-base", local, remote)
            base = mb.out.strip() if mb.ok else ""
    t_local, t_remote = commit_time(root, local), commit_time(root, remote)
    now = int(datetime.datetime.now().timestamp())
    new = dict(ents_l)
    for n, sha in ents_r.items():
        new.setdefault(n, sha)
    new_done = False
    for n in in_git_files(root):
        work = read_file(root, n)
        l_text, r_text, b_text = blob(root, local, n), blob(root, remote, n), blob(root, base, n)
        ours_time = now if (work or "") != (l_text or "") else t_local
        result = merge_file(n, b_text, work, r_text, ours_time, t_remote)
        if result != (work or "") and not (work is None and result == ""):
            write_file(os.path.join(root, n), result)
            keep(root, n)
            if n == "agent_completed.txt" and set(lines_of(result)) - set(lines_of(work)):
                new_done = True
        if result != "" or n in new:
            sha = put_blob(root, result)
            if sha:
                new[n] = sha
    if remote and (not local or ancestor(root, local, remote)):
        if new == ents_r:
            if local != remote:
                move_ref(root, remote, local)
        else:
            made = make_commit(root, new, [remote], message)
            if made:
                move_ref(root, made, local)
    elif remote and ancestor(root, remote, local):
        if new != ents_l:
            made = make_commit(root, new, [local], message)
            if made:
                move_ref(root, made, local)
    elif remote:
        made = make_commit(root, new, [local, remote], message)
        if made:
            move_ref(root, made, local)
    elif local:
        if new != ents_l:
            made = make_commit(root, new, [local], message)
            if made:
                move_ref(root, made, local)
    elif new:
        made = make_commit(root, new, [], message)
        if made:
            move_ref(root, made, "")
    if new_done:
        start_estimator(root)
    return new_done


def start_estimator(root):
    """New finished records came in: the estimator's own background runner (agent-file.sh estimate-queue). Never waited for."""
    script = os.path.join(HERE, "agent-file.sh")
    try:
        subprocess.Popen([script, "estimate-queue"], cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def sync(root, message="files sync", force=()):
    if not active(root):
        return
    announce(root)
    if on_code_branch(root):
        code_cycle(root, message, force)
    else:
        sync_core(root, message)
        local = tip(root)
        if local and has_origin(root) and local != tip(root, remote_ref(root)):
            publish(root)


# ------------------------------------------------------------------ show, ignore, set


def cmd_show(root):
    f = facts(root)
    kind, branch = place(root)
    say("files: task_files=%s task_take=%s place=%s" % (f["task_files"], f["task_take"], branch if kind == "data" else "tree"))
    shared = in_git_files(root)
    for n in AGENT_FILES:
        say("%s: %s" % (n, "in git" if n in shared else "local"))
    return 0


def ignore(root):
    """The five agent-file lines of .gitignore by the place. True when the file changed."""
    path = os.path.join(root, ".gitignore")
    text = read_file(root, ".gitignore")
    kind = place(root)[0]
    if text is None:
        if kind == "tree":
            return False
        text = ""
    items = text.split("\n")
    if items and items[-1] == "":
        items.pop()
    if kind == "data":
        missing = [n for n in AGENT_FILES if n not in items]
        if not missing:
            return False
        items += missing
    else:
        kept = [l for l in items if l not in AGENT_FILES]
        if len(kept) == len(items):
            return False
        items = kept
    write_file(path, join_lines(items) if items else "")
    return True


def valid_value(key, value):
    if key == "data_branch":
        return bool(value.strip())
    allowed = {"task_files": TASK_FILES_VALUES, "task_take": TASK_TAKE_VALUES, "task_place": TASK_PLACE_VALUES}
    return key in allowed and value in allowed[key]


def put_fact(root, key, value):
    """The line in agent_repo.conf: replaced in place, else appended. True when the file changed."""
    path = os.path.join(root, CONF)
    old = read_file(root, CONF)
    reset_cache()
    pat = re.compile(r"^\s*%s\s*=.*$" % re.escape(key))
    new_line = "%s=%s" % (key, value)
    if old is None:
        text = new_line + "\n"
    else:
        parts = old.split("\n")
        hit = [i for i, l in enumerate(parts) if pat.match(l)]
        if hit:
            if parts[hit[0]] == new_line and len(hit) == 1:
                return False
            parts[hit[0]] = new_line
            for i in reversed(hit[1:]):
                del parts[i]
            text = "\n".join(parts)
        else:
            text = old + ("" if old == "" or old.endswith("\n") else "\n") + new_line + "\n"
    write_file(path, text)
    return True


def commit_conf(root, message):
    """One code-branch commit of agent_repo.conf; the repo's own hooks run. False (and one line) when refused."""
    if not is_repo(root):
        return True
    if not run(root, "status", "--porcelain", "--", CONF).out.strip():
        return True
    run(root, "add", "--", CONF)
    r = run(root, "commit", "-q", "--only", "-m", message, "--", CONF, env=ident_env(root))
    if not r.ok:
        run(root, "reset", "-q", "--", CONF)
        say("%s: not committed (%s)" % (CONF, why_text(r)))
        return False
    return True


def restore_conf(root, old):
    """Put agent_repo.conf back as it was (a commit was refused)."""
    path = os.path.join(root, CONF)
    reset_cache()
    if old is None:
        try:
            os.remove(path)
        except OSError:
            pass
    else:
        write_file(path, old)


def put_team(root, forced):
    """Write the team facts agent_repo.conf lacks (task_files, task_take, data_branch) with their effective values,
    FORCED ({key: value}) first. Returns the "key=value ..." text written ("" when nothing was missing)."""
    have = read_conf(root)
    f = facts(root)
    eff = {"task_files": f["task_files"], "task_take": f["task_take"], "data_branch": branch(root)}
    eff.update(forced)
    wrote = []
    for key in TEAM_KEYS:
        if key in have and key not in forced:
            continue
        if put_fact(root, key, eff[key]):
            wrote.append("%s=%s" % (key, eff[key]))
    return " ".join(wrote)


def team_line(wrote, reason):
    return "%s: %s written (%s)" % (CONF, wrote, reason)


def cmd_set(root, args):
    flags = [a for a in args if a.startswith("--")]
    rest = [a for a in args if not a.startswith("--")]
    if len(rest) != 2 or any(f not in ("--no-commit", "--no-move") for f in flags):
        sys.stderr.write("files set: usage: files set <task_files|task_take|task_place|data_branch> <value> [--no-commit] [--no-move]\n")
        return 1
    key, value = rest
    if not valid_value(key, value):
        sys.stderr.write("files set: %s cannot be %s (task_files: local, ideas, ideas,todo; task_take: owner, anyone; "
                         "task_place: data, tree; data_branch: a branch name)\n" % (key, value))
        return 1
    if key == "data_branch":
        why = refusal(root, value)
        if why:
            sys.stderr.write(why + "\n")
            return 1
    moves = key == "task_files" and "--no-move" not in flags
    if moves and place(root)[0] == "data" and is_repo(root) and not in_main_checkout(root):
        sys.stderr.write("files move: run it in the main checkout (%s)\n" % root)
        return 1
    old = read_file(root, CONF)
    wrote = ""
    if moves and value != "local":
        wrote = put_team(root, {"task_files": value})
    else:
        put_fact(root, key, value)
    if "--no-commit" not in flags and not commit_conf(root, "agent-files: %s=%s" % (key, value)):
        restore_conf(root, old)
        return 1
    say("files set: %s=%s" % (key, value))
    if key == "data_branch" and is_repo(root) and value == production_branch(root):
        say("files set: %s is the production branch of this repo: a commit on it can start a deploy" % value)
    if wrote and wrote != "task_files=%s" % value:
        say(team_line(wrote, "the repo had no value"))
    if moves:
        return move(root)
    return 0


# ------------------------------------------------------------------ move


def production_branch(root):
    try:
        import agent_conf
        return agent_conf.production_branch(root)
    except Exception:
        return ""


def in_main_checkout(root):
    top = run(os.getcwd(), "rev-parse", "--show-toplevel").out.strip()
    return bool(top) and os.path.realpath(top) == os.path.realpath(root)


def tracked(root, n):
    return bool(run(root, "ls-files", "--", n).out.strip())


def common_dir(root):
    return run(root, "rev-parse", "--path-format=absolute", "--git-common-dir").out.strip()


def stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def add_empty_task_files(root, shared):
    """A task file that is shared now, exists here and is empty has no line to carry it onto the data branch:
    create it there (the move creates what is missing)."""
    local = tip(root)
    ents = tree_entries(root, local)
    new = dict(ents)
    for n in ("agent_ideas.txt", "agent_todo.txt"):
        if n in shared and n not in ents and read_file(root, n) == "":
            sha = put_blob(root, "")
            if sha:
                new[n] = sha
    if new == ents:
        return
    made = make_commit(root, new, [local] if local else [], "files move")
    if made and move_ref(root, made, local):
        publish(root)


def move(root):
    if place(root)[0] == "tree":
        say("files move: the task files stay in the code tree (task_place=tree), nothing moves")
        return 0
    announce(root)
    if not is_repo(root):
        sys.stderr.write("files move: %s is not a git repository\n" % root)
        return 1
    if not in_main_checkout(root):
        sys.stderr.write("files move: run it in the main checkout (%s)\n" % root)
        return 1
    if os.path.exists(os.path.join(run(root, "rev-parse", "--path-format=absolute", "--git-dir").out.strip(), "MERGE_HEAD")):
        sys.stderr.write("files move: a merge is in progress; nothing moved\n")
        return 1
    staged = [p for p in run(root, "diff", "--cached", "--name-only", "--no-renames", "-z").out.split("\0")
              if p and p not in AGENT_FILES]
    if staged:
        sys.stderr.write("files move: the index has staged changes (%s); commit or unstage them first, nothing moved\n"
                         % staged[0])
        return 1
    if "task_files" not in read_conf(root):
        f = facts(root)
        if f["task_files"] != "local" or f["task_take"] == "anyone":
            old_conf = read_file(root, CONF)
            wrote = put_team(root, {})
            if wrote and not commit_conf(root, "agent-files: %s" % wrote):
                restore_conf(root, old_conf)
                return 1
            if wrote:
                say(team_line(wrote, "your Configure shares, the repo had no value"))
    kept_dir = os.path.join(common_dir(root), "agent-files-kept")
    was_moved = moved(root)
    ts = stamp()
    changed = set()
    pulled = False

    # (1) the code branch's upstream is ahead: keep the content, pull, put the content back
    up = run(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if up.ok:
        net(root, "fetch", "-q")
        ahead = run(root, "rev-list", "--count", "HEAD..@{upstream}").out.strip()
        if ahead.isdigit() and int(ahead) > 0:
            memory = {}
            for n in AGENT_FILES:
                data = read_bytes(os.path.join(root, n))
                if data is not None:
                    memory[n] = data
                    os.makedirs(kept_dir, exist_ok=True)
                    with open(os.path.join(kept_dir, "%s.%s-pull" % (n, ts)), "wb") as fh:
                        fh.write(data)
            for n in memory:
                if tracked(root, n):
                    run(root, "checkout", "HEAD", "--", n)
            r = net(root, "pull", "--no-rebase", "--no-edit", "-q", mult=3, env=ident_env(root))
            for n, data in memory.items():
                with open(os.path.join(root, n), "wb") as fh:
                    fh.write(data)
            if not r.ok:
                sys.stderr.write("files move: pull failed: %s\n" % (first_line(r.err) or first_line(r.out) or "git refused"))
                return 1
            pulled = True

    # (2) every tracked agent file leaves the code branch, content kept
    for n in AGENT_FILES:
        if not tracked(root, n):
            continue
        path = os.path.join(root, n)
        if os.path.isfile(path):
            os.makedirs(kept_dir, exist_ok=True)
            shutil.copy2(path, os.path.join(kept_dir, "%s.%s" % (n, ts)))
        run(root, "rm", "--cached", "-q", "-f", "--", n)
        changed.add(n)
    old_ignore = read_file(root, ".gitignore")
    ignored_changed = ignore(root)
    _MOVED.pop(root, None)
    if ignored_changed:
        run(root, "add", "--", ".gitignore")
    committed = False
    if run(root, "diff", "--cached", "--quiet").rc == 1:
        r = run(root, "commit", "-q", "-m", "agent-files: the agent files leave the code branch",
                env=ident_env(root))
        if not r.ok:
            # the repo's own hook refused: the move is not done, the index and .gitignore are put back
            run(root, "reset", "-q", "--", ".gitignore", *AGENT_FILES)
            if old_ignore is None:
                try:
                    os.remove(os.path.join(root, ".gitignore"))
                except OSError:
                    pass
            elif ignored_changed:
                write_file(os.path.join(root, ".gitignore"), old_ignore)
            _MOVED.pop(root, None)
            sys.stderr.write("files move: commit failed: %s\n" % why_text(r))
            return 1
        committed = True

    # (3) turning the todo into git: open lines with no owner get the name of the person who runs it
    shared = in_git_files(root)
    owner_note = ""
    if "agent_todo.txt" in shared:
        text = read_file(root, "agent_todo.txt") or ""
        who = agent_conf.user_name(root)
        todo = lines_of(text)
        open_lines = [l for l in todo if " | owner " not in l]
        if open_lines and not who:
            owner_note = "files move: no git user.name; %d open todo lines stay without an owner" % len(open_lines)
        elif open_lines:
            write_file(os.path.join(root, "agent_todo.txt"),
                       join_lines([l if " | owner " in l else "%s | owner %s" % (l, who) for l in todo]))
            changed.add("agent_todo.txt")

    # (4) the in-git files onto ap-data, synced with origin's, created when missing, pushed
    before = data_entries(root)
    force = [n for n in ("agent_ideas.txt", "agent_todo.txt") if n in shared and read_file(root, n) == ""]
    sync(root, "files move", force=force)
    if not on_code_branch(root):
        add_empty_task_files(root, shared)
    after = data_entries(root)
    for n in shared:
        if before.get(n) != after.get(n):
            changed.add(n)

    for n in (AGENT_FILES if not was_moved else sorted(changed)):
        keep(root, n)
    for n in AGENT_FILES:
        state = "in git" if n in shared else "local"
        if n in shared and n not in after and not os.path.exists(os.path.join(root, n)):
            say("%s: missing" % n)
        elif n in changed:
            if n in shared:
                say("%s: in git (on %s)" % (n, branch(root)))
            else:
                say("%s: local (out of the code branch; a copy is in agent-files-kept)" % n)
        else:
            say("%s: %s (already)" % (n, state))
    if owner_note:
        say(owner_note)
    if changed or pulled or ignored_changed or committed:
        say("files move: done")
    else:
        say("files move: nothing changed")
    return 0


# ------------------------------------------------------------------ main


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: agent_share.py <project root> show|commit|sync|set|ignore|move|name|place ...\n")
        return 2
    root, cmd, rest = os.path.realpath(argv[0]), argv[1], argv[2:]
    if cmd == "show":
        return cmd_show(root)
    if cmd == "commit":
        commit(root, rest[0] if rest else "agent-files")
        return 0
    if cmd == "sync":
        sync(root)
        return 0
    if cmd == "set":
        return cmd_set(root, rest)
    if cmd == "ignore":
        ignore(root)
        return 0
    if cmd == "move":
        return move(root)
    if cmd == "restore":
        return cmd_restore(root, rest[0], rest[1] if len(rest) == 2 else None) if len(rest) in (1, 2) else 2
    if cmd == "may-work":
        return cmd_may_work(root, rest[0]) if rest else 2
    if cmd == "pull":
        pull(root)
        return 0
    if cmd == "take":
        return cmd_take(root, rest[0]) if len(rest) == 1 else 2
    if cmd == "assign":
        return cmd_assign(root, rest[0], rest[1]) if len(rest) == 2 else 2
    if cmd == "name":
        say(agent_conf.user_name(root))
        return 0
    if cmd == "place":
        kind, branch = place(root)
        say("%s %s" % (kind, branch) if branch else kind)
        return 0
    sys.stderr.write("agent_share.py: unknown command %s\n" % cmd)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(1)
