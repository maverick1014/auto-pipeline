#!/usr/bin/env python3
"""agent_promote.py: publish the working branch (or one task branch) to production, and the sync of production into the
working branch (requirements/check-blocks.md sections 28-30 C36'/C42, 34 C48). Called by agent-promote.sh. Python 3.9 stdlib."""

import os
import glob
import json
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agent_conf  # noqa: E402
import agent_nightly  # noqa: E402

WT_NAME = "agent_promote_wt_%d"


def run(cwd, *args, timeout=300):
    """(returncode, stdout, stderr) of git in cwd."""
    try:
        r = subprocess.run(["git", "-C", cwd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", str(exc)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def out(text):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def last_line(text):
    lines = [l for l in text.splitlines() if l.strip()]
    return lines[-1].strip() if lines else ""


def is_ancestor(root, a, b):
    return run(root, "merge-base", "--is-ancestor", a, b)[0] == 0


def current_branch(root):
    return run(root, "symbolic-ref", "-q", "--short", "HEAD")[1]


def dirty(root):
    """The tracked changes of the checkout other than agent_*.txt (the board files); '' when none. Reads
    `status --porcelain -z` exactly: NUL-separated entries, a rename or copy carries its source as the next entry."""
    try:
        r = subprocess.run(["git", "-C", root, "status", "--porcelain", "-z", "--untracked-files=no"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return ""
    entries = r.stdout.decode("utf-8", "replace").split("\0")
    rows, i = [], 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        if e[0] in "RC" or e[1] in "RC":
            i += 1                                   # the source path of a rename or copy
        path = e[3:]
        if re.match(r"^agent_[^/]*\.txt$", path):
            continue
        rows.append(path)
    return ", ".join(rows[:3])


def merge_in_progress(root):
    return run(root, "rev-parse", "-q", "--verify", "MERGE_HEAD")[0] == 0


def verify(root, quote, when):
    cmd = [os.path.join(HERE, "agent-owner-order.sh"), "verify", "--repo", root, "--quote", quote]
    if when:
        cmd += ["--time", when]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        out("refused: the owner's words could not be verified (%s)" % exc)
        return False
    if r.returncode != 0:
        said = last_line(r.stdout) or last_line(r.stderr)
        out("refused: the owner's words were not verified%s" % (": " + said if said else ""))
        return False
    return True


def fetch(root):
    return run(root, "fetch", "-q", "origin", timeout=120)[0] == 0


def checked_out(root, prod):
    """The path of the worktree that has the local production branch checked out, else ''."""
    path = ""
    for line in run(root, "worktree", "list", "--porcelain")[1].splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line == "branch refs/heads/" + prod:
            return path
    return ""


def follow_local(root, prod, sha):
    """The local production ref follows the pushed commit: fast-forward only, never backward (P3); a ref checked out
    in a worktree is left alone."""
    if run(root, "rev-parse", "--verify", "-q", "refs/heads/" + prod)[0] != 0:
        return
    rc, text, _ = run(root, "worktree", "list", "--porcelain")
    if "branch refs/heads/%s" % prod in text.splitlines():
        return
    if not is_ancestor(root, "refs/heads/" + prod, sha):
        out("local %s not moved: not a fast-forward" % prod)
        return
    run(root, "update-ref", "refs/heads/" + prod, sha)


def release(cwd):
    """Run the release build when the repo has one. Returns 0, or the build's failing code."""
    script = os.path.join(cwd, "bin", "agent-release.sh")
    if not os.path.exists(script):
        out("release: no release build in this repo")
        return 0
    r = subprocess.run([script, "--push"], cwd=cwd, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        out("release: bin/agent-release.sh --push failed (exit %d)" % r.returncode)
        return r.returncode
    out("release: ran bin/agent-release.sh --push")
    return 0


def remove_worktree(root, wt):
    run(root, "worktree", "remove", "--force", wt)
    if os.path.exists(wt):
        shutil.rmtree(wt, ignore_errors=True)
    run(root, "worktree", "prune")


def own_worktree(root):
    """The path of this run's short-lived worktree (P6), free to be made."""
    wt = os.path.join(agent_nightly.common_dir(root), WT_NAME % os.getpid())
    if os.path.exists(wt):
        remove_worktree(root, wt)
    return wt


def remove_stale(root):
    """F14: leftover agent_promote_wt_<pid> worktrees of runs that are dead."""
    gitdir = agent_nightly.common_dir(root)
    for path in glob.glob(os.path.join(gitdir, "agent_promote_wt_*")):
        m = re.match(r"^agent_promote_wt_(\d+)$", os.path.basename(path))
        if m and not agent_nightly.pid_alive(m.group(1)):
            remove_worktree(root, path)


def release_not_run(prod, where):
    out("release: not run: local %s is checked out in %s; switch that checkout to the working branch "
        "(section 33), then run bin/agent-release.sh --push" % (prod, where))


def release_at(root, prod, sha):
    """The release build in a short-lived worktree at the published commit (F9), never the main checkout's HEAD.
    Local production checked out -> the G6 line, not run, 1."""
    where = checked_out(root, prod)
    if where:
        release_not_run(prod, where)
        return 1
    wt = own_worktree(root)
    rc, _, se = run(root, "worktree", "add", "-q", "--detach", wt, sha)
    if rc != 0:
        out("release: not run: could not make the short-lived worktree: %s" % last_line(se))
        return 1
    try:
        return release(wt)
    finally:
        remove_worktree(root, wt)


# ------------------------------------------------------------------ sync (C48)

def merge_production_in(root, wb, prod):
    """Merge origin/<prod> into the working branch in the main checkout and push it. ('merged', short) | ('in', '')
    | ('waits', why) | ('conflict', why). Nothing is pushed on anything but 'merged'."""
    ref = "origin/" + prod
    if run(root, "rev-parse", "--verify", "-q", "refs/remotes/%s^{commit}" % ref)[0] != 0:
        return "waits", "no %s to merge" % ref
    if run(root, "rev-parse", "--verify", "-q", "refs/heads/%s^{commit}" % wb)[0] != 0:
        return "waits", "no branch %s" % wb
    if is_ancestor(root, ref, "refs/heads/" + wb):
        return "in", ""
    cur = current_branch(root)
    if cur != wb:
        return "waits", "the main checkout is on %s, not on %s" % (cur or "no branch", wb)
    if merge_in_progress(root):
        return "waits", "a merge is in progress in %s (not started by this run)" % root
    d = dirty(root)
    if d:
        return "waits", "the main checkout has changes (%s)" % d
    rc, so, se = run(root, "merge", "--no-edit", ref)
    if rc != 0:
        run(root, "merge", "--abort")
        return "conflict", "merging %s into %s conflicts; merge aborted, nothing pushed" % (ref, wb)
    short = run(root, "rev-parse", "--short=7", "HEAD")[1]
    rc, _, se = run(root, "push", "-q", "origin", wb, timeout=300)
    if rc != 0:
        return "waits", "merged locally (%s) but the push of %s failed: %s" % (short, wb, last_line(se))
    return "merged", short


def sync(root, wb, prod):
    """The C48 sync; returns (exit code, result kind)."""
    fetch(root)
    kind, info = merge_production_in(root, wb, prod)
    if kind == "merged":
        out("sync: %s merged into %s (%s)" % (prod, wb, info))
        return 0, kind
    if kind == "in":
        out("sync: %s already has %s" % (wb, prod))
        return 0, kind
    out("sync waits: %s" % info)
    return (1 if kind == "conflict" else 0), kind


# ------------------------------------------------------------------ publish (C36')

def publish(root, wb, prod, quote, when):
    if not verify(root, quote, when):
        return 1
    rc, kind = sync(root, wb, prod)
    if kind == "merged":
        tip = run(root, "rev-parse", "--short=7", "refs/heads/" + wb)[1]
        out("refused: production moved on: merge production back into the working branch first (the sync above did it); "
            "the green run no longer covers the tip %s: run agent-nightly.sh --start, then publish again" % tip)
        return 1
    ref = "refs/remotes/origin/" + prod
    if kind != "in":
        if run(root, "rev-parse", "--verify", "-q", ref + "^{commit}")[0] == 0 \
                and not is_ancestor(root, ref, "refs/heads/" + wb):
            out("refused: production is not in %s: merge production back into the working branch first" % wb)
        else:
            out("refused: the sync did not finish; publish again when it does")
        return 1
    tip = run(root, "rev-parse", "refs/heads/" + wb)[1]          # the sha release_ok checks, and the one pushed (F8)
    if agent_nightly.release_ok(root) != 0:
        out("refused: the last nightly is not green on the tip of %s" % wb)
        return 1
    rc, _, se = run(root, "push", "origin", "%s:refs/heads/%s" % (tip, prod), timeout=300)
    if rc != 0:
        out("refused: the push to origin/%s failed: %s" % (prod, last_line(se)))
        return 1
    follow_local(root, prod, tip)
    subject = run(root, "log", "-1", "--format=%s", tip)[1]
    out("promote: %s -> %s (%s)" % (prod, tip[:7], subject))
    return release_at(root, prod, tip)


# ------------------------------------------------------------------ the direct path (C42)

def todo_fields(root, task):
    """The fields of the task's line in the main repo's agent_todo.txt, else None."""
    try:
        with open(os.path.join(root, "agent_todo.txt"), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                f = [x.strip() for x in line.rstrip("\n").split(" | ")]
                if f and f[0] == task:
                    return f
    except OSError:
        pass
    return None


def stored_words(root, task):
    try:
        with open(os.path.join(agent_nightly.common_dir(root), "agent_owner_words.json")) as fh:
            e = json.load(fh).get(task)
    except (OSError, ValueError, AttributeError):
        return None
    return e if isinstance(e, dict) and e.get("quote") and e.get("verified") is not False else None


def gate(root, task, branch, prod):
    """F1: the gate on a detached scratch worktree of origin/<branch>. True when it passes."""
    wt = own_worktree(root)
    rc, _, se = run(root, "worktree", "add", "-q", "--detach", wt, "origin/" + branch)
    if rc != 0:
        out("refused: could not make the scratch worktree for the gate: %s" % last_line(se))
        return False
    try:
        try:
            r = subprocess.run([os.path.join(HERE, "agent-file.sh"), "checks", "gate", task, "--dir", wt,
                                "--base", "origin/" + prod, "--branch", branch], cwd=root, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=1800)
        except (OSError, subprocess.SubprocessError) as exc:
            out("refused: the gate could not run: %s" % exc)
            return False
        text = (r.stdout.strip() + "\n" + r.stderr.strip()).strip()
        if r.returncode != 0 or "GATE REFUSED" in r.stdout:
            out(text if text else "GATE REFUSED %s: the gate failed (exit %d)" % (task, r.returncode))
            return False
        return True
    finally:
        remove_worktree(root, wt)


def direct(root, wb, prod, task, branch):
    fields = todo_fields(root, task)
    if fields is None or "target production" not in fields:
        out("refused: %s is not a production task (todo add --target production)" % task)
        return 1
    if not stored_words(root, task):
        out("refused: no owner words stored for %s" % task)
        return 1
    fetch(root)
    for ref in ("origin/" + prod, "origin/" + branch):
        if run(root, "rev-parse", "--verify", "-q", "refs/remotes/%s^{commit}" % ref)[0] != 0:
            out("refused: %s does not exist (is the branch pushed?)" % ref)
            return 1
    own = set(run(root, "rev-list", "origin/" + branch, "^origin/" + prod)[1].split())
    shared = own & set(run(root, "rev-list", "refs/heads/" + wb, "^origin/" + prod)[1].split())
    if shared:
        out("%s carries commits of %s that are not in %s: branch it from %s" % (branch, wb, prod, prod))
        return 1
    if not gate(root, task, branch, prod):
        return 1
    wt = own_worktree(root)
    rc, _, se = run(root, "worktree", "add", "-q", "--detach", wt, "origin/" + prod)
    if rc != 0:
        out("refused: could not make the short-lived worktree: %s" % last_line(se))
        return 1
    try:
        rc, _, _ = run(wt, "merge", "--no-ff", "origin/" + branch, "-m", "Merge %s (W8)" % task)
        if rc != 0:
            run(wt, "merge", "--abort")
            out("refused: origin/%s does not merge into origin/%s without a conflict; merge aborted, nothing pushed"
                % (branch, prod))
            return 1
        sha = run(wt, "rev-parse", "HEAD")[1]
        rc, _, se = run(wt, "push", "origin", "HEAD:refs/heads/" + prod, timeout=300)
        if rc != 0:
            out("refused: the push to origin/%s failed: %s" % (prod, last_line(se)))
            return 1
        out("promote: %s -> %s (%s)" % (task, prod, sha[:7]))
        follow_local(root, prod, sha)
        where = checked_out(root, prod)
        if where:
            release_not_run(prod, where)
            code = 1
        else:
            code = release(wt)
    finally:
        remove_worktree(root, wt)
    # production merged back into the working branch, in the main checkout
    kind, info = merge_production_in(root, wb, prod)
    if kind in ("merged", "in"):
        out("merged back: %s -> %s" % (prod, wb))
    else:
        out("merge back waits: %s" % info)
    return code


# ------------------------------------------------------------------ main

USAGE = ("usage: agent-promote.sh --owner-quote \"<words>\" [--time <t>] | --task \"<task>\" --branch <branch> "
         "| --sync\n")


def parse(argv):
    opts, i = {}, 0
    names = {"--owner-quote": "quote", "--time": "time", "--task": "task", "--branch": "branch"}
    while i < len(argv):
        a = argv[i]
        if a == "--sync":
            opts["sync"] = True
        elif a in names and i + 1 < len(argv):
            opts[names[a]] = argv[i + 1]
            i += 1
        else:
            return None
        i += 1
    return opts


def main(argv):
    opts = parse(argv)
    if not opts or not (opts.get("sync") or opts.get("quote") or "task" in opts) \
            or ("task" in opts) != ("branch" in opts) or (opts.get("sync") and len(opts) > 1):
        sys.stderr.write(USAGE)
        return 2
    if "task" in opts and ("quote" in opts or "time" in opts):
        out("refused: the owner's words come from the task (todo add --target production --owner-quote), "
            "not from promote")
        return 1
    cwd = os.getcwd()
    root = agent_nightly.main_root(cwd)
    remove_stale(root)
    wb = agent_nightly.need_stored(root)
    if not wb:
        return 1
    prod = agent_conf.production_branch(root)
    if opts.get("sync"):
        return sync(root, wb, prod)[0]
    if "task" in opts:
        return direct(root, wb, prod, opts["task"], opts["branch"])
    return publish(root, wb, prod, opts["quote"], opts.get("time"))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
