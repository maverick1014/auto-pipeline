#!/usr/bin/env python3
"""agent_share.py: where the agent files live, and how the ones in git are shared (requirements/agent-files.md).

CLI: agent_share.py <project root> <cmd> ...
  show                       files: task_files=<v> task_take=<v> place=<ap-data|tree>, then one line per agent file
  commit "<message>"         the in-git files that differ from the tip of ap-data go into one commit on it, then push
  sync                       fetch origin ap-data, 3-way merge into the working copies, commit, push
  set <key> <value> [--no-commit] [--no-move]    task_files | task_take | task_place
  ignore                     the five .gitignore lines by the place (data: present, tree: absent)
  move                       take the agent files out of the code branch, put the in-git ones on ap-data
  name                       the git user name of the project root ("" when none)
  place                      "data <branch>" or "tree"

Facts live in agent_repo.conf ("key=value", "key = value" reads the same):
  task_files = local (default) | ideas | ideas,todo      task_take = owner (default) | anyone
  task_place = data (default) | tree                     tree: the files stay in the code tree (the cloud pack)
The in-git files: agent_completed.txt and agent_estimate.txt always; agent_ideas.txt and agent_todo.txt when
task_files names them; agent_worktree.txt never. Python 3.9, stdlib only. Git's own words never reach the output.
"""

import datetime
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

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


def data_branch():
    try:
        import agent_conf
        return str(agent_conf.CONSTANTS.get("data_branch") or "ap-data")
    except Exception:
        return "ap-data"


BRANCH = data_branch()
LOCAL_REF = "refs/heads/" + BRANCH
REMOTE_REF = "refs/remotes/origin/" + BRANCH


def timeout_s():
    try:
        return max(1, int(os.environ.get("AGENT_SHARE_TIMEOUT", "40")))
    except ValueError:
        return 40


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


def tip(root, ref=LOCAL_REF):
    r = run(root, "rev-parse", "-q", "--verify", ref + "^{commit}")
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


def place(root):
    """Where the files in git go: ("data", <data branch>) or ("tree", None). The one place that says it."""
    if facts(root)["task_place"] == "tree":
        return ("tree", None)
    return ("data", BRANCH)


def in_git_files(root):
    shared = facts(root)["task_files"]
    names = ["agent_completed.txt", "agent_estimate.txt"]
    if shared in ("ideas", "ideas,todo"):
        names.append("agent_ideas.txt")
    if shared == "ideas,todo":
        names.append("agent_todo.txt")
    return [n for n in AGENT_FILES if n in names]


def name(root):
    """The one name of the person: git user.name (spaces kept), else the login name."""
    given = run(root, "config", "user.name").out.strip()
    if given:
        return given
    try:
        import getpass
        return getpass.getuser().strip()
    except Exception:
        return ""


def active(root):
    return place(root)[0] == "data" and is_repo(root)


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
    return run(root, "update-ref", LOCAL_REF, new, old or "0" * 40).ok


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


def publish(root):
    """Push ap-data. A push refused because origin moved: sync, push again. Any other failure: one line."""
    if not has_origin(root) or not tip(root):
        return
    for turn in range(ROUNDS):
        r = run(root, "push", "-q", "origin", "%s:refs/heads/%s" % (LOCAL_REF, BRANCH), timeout=timeout_s())
        if r.ok:
            return
        if MOVED.search(r.err) and turn < ROUNDS - 1:
            sync_core(root, "sync")
            continue
        say("%s: not pushed (%s); the next write pushes it" % (BRANCH, why_text(r)))
        return


def commit(root, message):
    if not active(root):
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
    return run(root, "fetch", "-q", "origin", "+%s:%s" % (LOCAL_REF, REMOTE_REF), timeout=timeout_s()).ok


def sync_core(root, message):
    """Fetch, merge into the working copies, commit. Returns True when new finished-task lines came in."""
    if not active(root):
        return False
    fetch(root)
    local, remote = tip(root), tip(root, REMOTE_REF)
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
    return new_done


def retrain(root):
    script = os.path.join(HERE, "agent-file.sh")
    try:
        subprocess.run([script, "retrain"], cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        pass


def sync(root, message="files sync", train=True):
    if not active(root):
        return
    new_done = sync_core(root, message)
    local = tip(root)
    if local and has_origin(root) and local != tip(root, REMOTE_REF):
        publish(root)
    if new_done and train:
        retrain(root)


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
    allowed = {"task_files": TASK_FILES_VALUES, "task_take": TASK_TAKE_VALUES, "task_place": TASK_PLACE_VALUES}
    return key in allowed and value in allowed[key]


def put_fact(root, key, value):
    """The line in agent_repo.conf: replaced in place, else appended. True when the file changed."""
    path = os.path.join(root, CONF)
    old = read_file(root, CONF)
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


def commit_conf(root, key, value):
    if not is_repo(root):
        return
    if not run(root, "status", "--porcelain", "--", CONF).out.strip():
        return
    run(root, "add", "--", CONF)
    r = run(root, "commit", "-q", "--no-verify", "--only", "-m", "agent-files: %s=%s" % (key, value), "--", CONF,
            env=ident_env(root))
    if not r.ok:
        say("%s: not committed (%s)" % (CONF, why_text(r)))


def cmd_set(root, args):
    flags = [a for a in args if a.startswith("--")]
    rest = [a for a in args if not a.startswith("--")]
    if len(rest) != 2 or any(f not in ("--no-commit", "--no-move") for f in flags):
        sys.stderr.write("files set: usage: files set <task_files|task_take|task_place> <value> [--no-commit] [--no-move]\n")
        return 1
    key, value = rest
    if not valid_value(key, value):
        sys.stderr.write("files set: %s cannot be %s (task_files: local, ideas, ideas,todo; task_take: owner, anyone; "
                         "task_place: data, tree)\n" % (key, value))
        return 1
    moves = key == "task_files" and "--no-move" not in flags
    if moves and place(root)[0] == "data" and is_repo(root) and not in_main_checkout(root):
        sys.stderr.write("files move: run it in the main checkout (%s)\n" % root)
        return 1
    put_fact(root, key, value)
    say("files set: %s=%s" % (key, value))
    if "--no-commit" not in flags:
        commit_conf(root, key, value)
    if moves:
        return move(root)
    return 0


# ------------------------------------------------------------------ move


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


def move(root):
    if place(root)[0] == "tree":
        say("files move: the task files stay in the code tree (task_place=tree), nothing moves")
        return 0
    if not is_repo(root):
        sys.stderr.write("files move: %s is not a git repository\n" % root)
        return 1
    if not in_main_checkout(root):
        sys.stderr.write("files move: run it in the main checkout (%s)\n" % root)
        return 1
    staged = [p for p in run(root, "diff", "--cached", "--name-only", "--no-renames", "-z").out.split("\0")
              if p and p not in AGENT_FILES]
    if staged:
        sys.stderr.write("files move: the index has staged changes (%s); commit or unstage them first, nothing moved\n"
                         % staged[0])
        return 1
    kept_dir = os.path.join(common_dir(root), "agent-files-kept")
    ts = stamp()
    changed = set()
    pulled = False

    # (1) the code branch's upstream is ahead: keep the content, pull, put the content back
    up = run(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if up.ok:
        run(root, "fetch", "-q", timeout=timeout_s())
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
            r = run(root, "pull", "--no-rebase", "--no-edit", "-q", timeout=timeout_s() * 3, env=ident_env(root))
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
    ignored_changed = ignore(root)
    if ignored_changed:
        run(root, "add", "--", ".gitignore")
    committed = False
    if run(root, "diff", "--cached", "--quiet").rc == 1:
        r = run(root, "commit", "-q", "--no-verify", "-m", "agent-files: the agent files leave the code branch",
                env=ident_env(root))
        if not r.ok:
            sys.stderr.write("files move: commit failed: %s\n" % why_text(r))
            return 1
        committed = True

    # (3) turning the todo into git: open lines with no owner get the name of the person who runs it
    shared = in_git_files(root)
    owner_note = ""
    if "agent_todo.txt" in shared:
        text = read_file(root, "agent_todo.txt") or ""
        who = name(root)
        todo = lines_of(text)
        open_lines = [l for l in todo if " | owner " not in l]
        if open_lines and not who:
            owner_note = "files move: no git user.name; %d open todo lines stay without an owner" % len(open_lines)
        elif open_lines:
            write_file(os.path.join(root, "agent_todo.txt"),
                       join_lines([l if " | owner " in l else "%s | owner %s" % (l, who) for l in todo]))
            changed.add("agent_todo.txt")

    # (4) the in-git files onto ap-data, synced with origin's, created when missing, pushed
    before = tree_entries(root, tip(root))
    sync(root, "files move")
    after = tree_entries(root, tip(root))
    for n in shared:
        if before.get(n) != after.get(n):
            changed.add(n)

    for n in AGENT_FILES:
        state = "in git" if n in shared else "local"
        if n in changed:
            if n in shared:
                say("%s: in git (on %s)" % (n, BRANCH))
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
    if cmd == "name":
        say(name(root))
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
