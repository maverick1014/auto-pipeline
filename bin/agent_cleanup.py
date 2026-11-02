#!/usr/bin/env python3
"""agent_cleanup.py - the logic of bin/agent-cleanup.sh (python3 stdlib only).

Run by the bash entry, never by hand:

    agent_cleanup.py --root <PROJECT_ROOT> --plugin <PLUGIN_ROOT>
                     --kind orca|plain|cloud [--apply] [--short]

One mechanical sweep: finished worktrees and branches, dead panes, leftover
pipeline processes. Every external call goes through run(): its own process
group, no stdin, a timeout, and a kill of the whole group when cut off. A
failed call is a result, never an exception out of this file.
"""

import json
import os
import re
import signal
import subprocess
import sys

BUSY = ("working", "permission")


# ---------------------------------------------------------------- calls


class Res(object):
    """What one external call gave back."""

    def __init__(self, rc=None, out="", err="", timed_out=False):
        self.rc = rc
        self.out = out
        self.err = err
        self.timed_out = timed_out

    @property
    def ok(self):
        return self.rc == 0 and not self.timed_out


def _dec(data):
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return data or ""


def _kill(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass


def run(argv, cwd=None, timeout=5.0, env=None):
    """Run argv in its own session; wait `timeout` seconds; never raise."""
    try:
        proc = subprocess.Popen(argv, cwd=cwd, env=env,
                                stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                start_new_session=True)
    except Exception as exc:  # missing program, bad cwd, ...
        return Res(None, "", str(exc))
    try:
        out, err = proc.communicate(timeout=timeout)
        return Res(proc.returncode, _dec(out), _dec(err))
    except subprocess.TimeoutExpired:
        _kill(proc)
        try:
            out, err = proc.communicate(timeout=2)
        except Exception:
            out = err = b""
            for pipe in (proc.stdout, proc.stderr):
                try:
                    pipe.close()
                except Exception:
                    pass
        return Res(None, _dec(out), _dec(err), True)
    except Exception as exc:
        _kill(proc)
        return Res(None, "", str(exc))


# ---------------------------------------------------------------- helpers


def real(path):
    return os.path.realpath(path) if path else ""


def items(data, key):
    """result.<key> of an orca answer, as a list of dicts (else empty)."""
    res = data.get("result") if isinstance(data, dict) else None
    val = res.get(key) if isinstance(res, dict) else None
    if not isinstance(val, list):
        return []
    return [x for x in val if isinstance(x, dict)]


def strip_heads(ref):
    if ref and ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):]
    return ref or None


def parse_worktrees(text):
    rows = []
    cur = None
    for line in text.splitlines():
        if line.startswith("worktree "):
            cur = {"path": line[len("worktree "):], "head": "", "branch": None,
                   "prunable": False}
            rows.append(cur)
        elif cur is None:
            continue
        elif line.startswith("HEAD "):
            cur["head"] = line[len("HEAD "):].strip()
        elif line.startswith("branch "):
            cur["branch"] = strip_heads(line[len("branch "):].strip())
        elif line.startswith("prunable"):
            cur["prunable"] = True
    return rows


SUGGEST = (
    ("not orca", "remove it by hand when the work is done"),
    ("no branch", "check out a branch in it, or remove it by hand"),
    ("live agent", "wait for the agent to stop, then run the sweep again"),
    ("registered", "finish the task, then agent-file.sh worktree rm <path>"),
    ("uncommitted changes", "commit or discard the changes"),
    ("unpushed", "push the branch"),
    ("unmerged", "merge it into main, or remove it by hand"),
    ("no own commits", "commit work on it, or remove it by hand"),
    ("orca unreachable", "start Orca, then run the sweep again"),
    ("folder missing", "git worktree prune"),
    ("remove failed", "remove it by hand: git worktree remove <path>"),
    ("check failed", "run the sweep again"),
)


def suggestion(reasons, path):
    first = reasons[0] if reasons else ""
    for key, text in SUGGEST:
        if first.startswith(key):
            return text.replace("<path>", path)
    return "look at it by hand"


# ---------------------------------------------------------------- the sweep


class Sweep(object):
    def __init__(self, root, plugin, kind, apply_, short):
        self.root = root
        self.plugin = plugin
        self.kind = kind
        self.apply = apply_
        self.short = short
        try:
            t = float(os.environ.get("AGENT_CLEANUP_TIMEOUT") or 5)
        except ValueError:
            t = 5.0
        self.t = t if t > 0 else 5.0
        self.env = dict(os.environ, GIT_TERMINAL_PROMPT="0")

        self.lines = []      # removed / closed / stopped lines
        self.notes = []      # (text, quiet_in_short)
        self.kept = []       # (what, where, why, suggestion)
        self.n = 0           # removed + closed + stopped (would, in list mode)

        self.base_ok = False
        self.wts = []        # git worktree list rows, [0] is the main checkout
        self.wts_ok = False
        self.removed_paths = set()
        self.origin_refs = {}    # branch name -> tip, refs/remotes/origin
        self.local_refs = {}     # branch name -> tip, refs/heads
        self.merged = set()      # full refnames reachable from origin/main
        self.first_parent = None
        self.registered_lines = []

        self.list_ok = False
        self.ps_ok = False
        self.repo_id = None
        self.project_id = None
        self.managed = set()     # real paths of this repo's orca worktrees
        self.local_rows = []
        self.ps = {}
        self.terminals = []
        self.term_ok = False
        self.env_list_ok = True
        self.machines = []       # reachable paired machines
        self.unreachable = []

    # ---- calls

    def git(self, *args, **kw):
        t = self.t * (3 if kw.get("long") else 1)
        return run(["git"] + list(args), cwd=self.root, timeout=t,
                   env=self.env)

    def orca(self, args, machine=None):
        argv = ["orca"] + list(args)
        if machine:
            argv += ["--environment", machine]
        res = run(argv, cwd=self.root, timeout=self.t, env=self.env)
        data = None
        if res.out.strip():
            try:
                data = json.loads(res.out)
            except ValueError:
                data = None
        good = res.ok and not (isinstance(data, dict)
                               and data.get("ok") is False)
        return good, data

    def orca_read(self, args, machine=None):
        """The parsed answer of a read call, or None when it failed."""
        good, data = self.orca(args, machine)
        if not good or not isinstance(data, dict):
            return None
        return data

    def orca_act(self, args, machine=None):
        return self.orca(args, machine)[0]

    # ---- notes and rows

    def note(self, text, quiet=False):
        self.notes.append((text, quiet))

    def keep(self, what, where, why, sug):
        self.kept.append((what, where, why, sug))

    # ---- the base

    def base(self):
        if not self.git("remote", "get-url", "origin").ok:
            self.note("no origin/main: worktrees and branches not checked",
                      quiet=True)
            return
        fetched = self.git("fetch", "--prune", "origin", long=True)
        tip = self.git("rev-parse", "--verify", "-q",
                       "refs/remotes/origin/main^{commit}")
        if not tip.ok:
            self.note("no origin/main: worktrees and branches not checked",
                      quiet=True)
            return
        if not fetched.ok:
            self.note("fetch failed, checked against the last known "
                      "origin/main")
        self.base_ok = True

        refs = self.git("for-each-ref",
                        "--format=%(refname) %(objectname)",
                        "refs/heads", "refs/remotes/origin")
        if refs.ok:
            for line in refs.out.splitlines():
                parts = line.split()
                if len(parts) != 2:
                    continue
                name, sha = parts
                if name.startswith("refs/heads/"):
                    self.local_refs[name[len("refs/heads/"):]] = sha
                elif name.startswith("refs/remotes/origin/"):
                    short = name[len("refs/remotes/origin/"):]
                    if short != "HEAD":
                        self.origin_refs[short] = sha
        merged = self.git("for-each-ref", "--format=%(refname)",
                          "--merged=refs/remotes/origin/main",
                          "refs/heads", "refs/remotes/origin")
        if merged.ok:
            self.merged = set(merged.out.split())
        else:
            self.base_ok = False
            self.note("branch check failed: worktrees and branches not "
                      "checked")

    def first_parent_set(self):
        if self.first_parent is None:
            res = self.git("rev-list", "--first-parent",
                           "refs/remotes/origin/main", long=True)
            self.first_parent = set(res.out.split()) if res.ok else False
        return self.first_parent

    # ---- gathering

    def gather_git(self):
        res = self.git("worktree", "list", "--porcelain")
        if res.ok:
            self.wts = parse_worktrees(res.out)
            self.wts_ok = bool(self.wts)
        path = os.path.join(self.root, "agent_worktree.txt")
        try:
            with open(path) as fh:
                self.registered_lines = [l.rstrip("\n") for l in fh]
        except (OSError, UnicodeDecodeError):
            self.registered_lines = []

    def gather_orca(self):
        if self.kind != "orca":
            return
        lst = self.orca_read(["worktree", "list", "--json"])
        ps = self.orca_read(["worktree", "ps", "--json"])
        terms = self.orca_read(["terminal", "list", "--json"])
        self.list_ok = lst is not None
        self.ps_ok = ps is not None
        self.term_ok = terms is not None
        if lst is None:
            self.note("orca not answering: worktrees and panes not checked")
        root = real(self.root)
        self.local_rows = items(lst, "worktrees")
        for row in self.local_rows:
            if real(row.get("path")) == root:
                self.repo_id = row.get("repoId")
                self.project_id = row.get("projectId")
        for row in self.local_rows:
            if (self.repo_id and row.get("repoId") == self.repo_id
                    and not row.get("isMainWorktree")
                    and real(row.get("path")) != root):
                self.managed.add(real(row.get("path")))
        self.ps = self.states(ps, True)
        self.terminals = items(terms, "terminals")

        envs = self.orca_read(["environment", "list", "--json"])
        if envs is None:
            self.env_list_ok = False
            return
        for env in items(envs, "environments"):
            name = env.get("name")
            if name:
                self.gather_machine(str(name))

    @staticmethod
    def states(data, local):
        out = {}
        for row in items(data, "worktrees"):
            path = row.get("path")
            if not path:
                continue
            key = real(path) if local else os.path.normpath(path)
            for agent in row.get("agents") or []:
                state = agent.get("state") if isinstance(agent, dict) else agent
                out.setdefault(key, []).append(str(state))
        return out

    def gather_machine(self, name):
        lst = self.orca_read(["worktree", "list", "--json"], name)
        ps = self.orca_read(["worktree", "ps", "--json"], name) \
            if lst is not None else None
        terms = self.orca_read(["terminal", "list", "--json"], name) \
            if ps is not None else None
        if lst is None or ps is None or terms is None:
            self.unreachable.append(name)
            self.note("%s unreachable, not checked" % name)
            return
        rows = []
        repo_ids = set()
        for row in items(lst, "worktrees"):
            if (self.project_id
                    and row.get("projectId") == self.project_id):
                rows.append(row)
                if row.get("repoId"):
                    repo_ids.add(row.get("repoId"))
        self.machines.append({
            "name": name,
            "rows": rows,
            "repo_ids": repo_ids,
            "paths": set(os.path.normpath(r.get("path") or "") for r in rows),
            "mains": set(os.path.normpath(r.get("path") or "") for r in rows
                         if r.get("isMainWorktree")),
            "ps": self.states(ps, False),
            "terminals": items(terms, "terminals"),
            "branches": set(strip_heads(r.get("branch")) for r in rows
                            if r.get("branch")),
        })

    # ---- the reasons a worktree is kept

    def registered(self, path):
        """(reasons, literal first fields) of this path's agent_worktree.txt
        lines."""
        reasons = []
        literals = []
        want = real(path)
        for line in self.registered_lines:
            parts = line.split(" | ")
            if not parts or not parts[0] or real(parts[0]) != want:
                continue
            if parts[0] not in literals:
                literals.append(parts[0])
            second = parts[1] if len(parts) > 1 else ""
            status = parts[2].strip() if len(parts) > 2 else ""
            why = None
            if "human-direct" in second:
                why = "registered human-direct"
            elif status in ("working", "final"):
                why = "registered " + status
            if why and why not in reasons:
                reasons.append(why)
        return reasons, literals

    def git_reasons(self, head, branch, status_path=None):
        """unpushed / unmerged / no own commits for a tip, from the base."""
        reasons = []
        known = bool(head) and self.git("cat-file", "-e",
                                        head + "^{commit}").ok
        if status_path is not None:
            st = self.git("-C", status_path, "status", "--porcelain")
            if not st.ok:
                reasons.append("check failed")
            elif st.out.strip():
                reasons.append("uncommitted changes")
        if not known:
            reasons.append("unpushed")
            reasons.append("unmerged")
            return reasons
        count = self.git("rev-list", "--count", head, "--not",
                         "--remotes=origin")
        if not count.ok or not count.out.strip().isdigit() \
                or int(count.out.strip()) > 0:
            reasons.append("unpushed")
        anc = self.git("merge-base", "--is-ancestor", head,
                       "refs/remotes/origin/main")
        if anc.rc != 0:
            reasons.append("unmerged")
        else:
            fp = self.first_parent_set()
            if fp is False:
                reasons.append("check failed")
            elif head in fp:
                reasons.append("no own commits")
        return reasons

    def local_reasons(self, row):
        path = row["path"]
        branch = row.get("branch")
        reasons = []
        if self.kind != "orca":
            reasons.append("not orca")
        if not branch:
            reasons.append("no branch")
        if self.kind == "orca":
            if not (self.list_ok and self.ps_ok):
                reasons.append("orca unreachable")
            elif any(s in BUSY for s in self.ps.get(real(path), [])):
                reasons.append("live agent")
        reasons.extend(self.registered(path)[0])
        reasons.extend(self.git_reasons(row.get("head"), branch, path))
        return reasons

    # ---- origin branches wait for the paired machines

    def origin_hold(self, branch):
        if self.kind != "orca":
            return None
        why = []
        if not self.env_list_ok:
            why.append("paired machines unreachable")
        for name in self.unreachable:
            why.append("%s unreachable" % name)
        for machine in self.machines:
            if branch in machine["branches"]:
                why.append("worktree on %s" % machine["name"])
        return ", ".join(why) or None

    @staticmethod
    def hold_suggestion(hold):
        if "unreachable" in hold:
            return "run the sweep again when the machine answers"
        return "remove its worktree on the machine, then run the sweep again"

    # ---- worktrees

    def do_worktrees(self):
        if not (self.base_ok and self.wts_ok):
            return
        for row in self.wts[1:]:
            path = row["path"]
            if not os.path.isdir(path):
                self.keep("worktree " + path, "this machine", "folder missing",
                          suggestion(["folder missing"], path))
                continue
            reasons = self.local_reasons(row)
            if reasons:
                self.keep("worktree " + path, "this machine",
                          ", ".join(reasons), suggestion(reasons, path))
                continue
            self.safe_worktree(row)

    def safe_worktree(self, row):
        path = row["path"]
        branch = row["branch"]
        managed = self.kind == "orca" and real(path) in self.managed
        if not self.apply:
            self.lines.append("would remove: worktree %s (branch %s)"
                              % (path, branch))
            self.n += 1
            self.removed_paths.add(real(path))
            self.branch_after(branch, False)
            return
        if managed:
            self.orca_act(["terminal", "close", "--worktree", "path:" + path,
                           "--all", "--json"])
            self.removed_paths.add(real(path))
            done = self.orca_act(["worktree", "rm", "--worktree",
                                  "path:" + path, "--json"])
        else:
            done = self.git("worktree", "remove", path).ok
        if not done:
            self.keep("worktree " + path, "this machine", "remove failed",
                      suggestion(["remove failed"], path))
            return
        self.removed_paths.add(real(path))
        self.lines.append("removed: worktree %s (branch %s)" % (path, branch))
        self.n += 1
        self.branch_after(branch, True)
        literals = self.registered(path)[1]
        for literal in literals:
            run([os.path.join(self.plugin, "bin", "agent-file.sh"),
                 "worktree", "rm", literal], cwd=self.root,
                timeout=self.t, env=self.env)

    def branch_after(self, branch, apply_):
        """The branch of a removed worktree: local copy, then origin's."""
        has_origin = branch in self.origin_refs
        hold = self.origin_hold(branch) if has_origin else None
        if apply_:
            if not self.git("branch", "-D", branch).ok:
                self.keep("branch " + branch, "local", "delete failed",
                          "git branch -D " + branch)
            if has_origin and not hold:
                if not self.git("push", "origin", "--delete", branch,
                                long=True).ok:
                    self.keep("branch " + branch, "origin", "push failed",
                              "git push origin --delete " + branch)
        if hold:
            self.keep("branch " + branch, "origin", hold,
                      self.hold_suggestion(hold))

    # ---- paired machines' worktrees: listed, never removed

    def do_remote_worktrees(self):
        if not self.base_ok:
            return
        for machine in self.machines:
            name = machine["name"]
            for row in machine["rows"]:
                if row.get("isMainWorktree"):
                    continue
                path = row.get("path") or ""
                if not path:
                    continue
                branch = strip_heads(row.get("branch"))
                reasons = []
                if not branch:
                    reasons.append("no branch")
                states = machine["ps"].get(os.path.normpath(path), [])
                if any(s in BUSY for s in states):
                    reasons.append("live agent")
                reasons.extend(self.registered(path)[0])
                reasons.extend(self.git_reasons(row.get("head"), branch))
                if not reasons:
                    reasons = ["changes on %s not checked from here" % name]
                self.keep("worktree " + path, name, ", ".join(reasons),
                          "orca worktree rm --environment %s --worktree "
                          "path:%s" % (name, path))

    # ---- branches without a worktree

    def do_branches(self):
        if not self.base_ok:
            return
        checked = set(w["branch"] for w in self.wts if w.get("branch"))
        names = (set(self.local_refs) | set(self.origin_refs)) - checked
        names.discard("main")
        for name in sorted(names):
            copies = []
            if name in self.local_refs:
                copies.append("local")
            if name in self.origin_refs:
                copies.append("origin")
            refs = []
            if "local" in copies:
                refs.append("refs/heads/" + name)
            if "origin" in copies:
                refs.append("refs/remotes/origin/" + name)
            if not all(ref in self.merged for ref in refs):
                self.keep("branch " + name, ", ".join(copies), "unmerged",
                          "merge it into main, or delete it by hand")
                continue
            hold = self.origin_hold(name) if "origin" in copies else None
            plan = [c for c in copies if not (c == "origin" and hold)]
            done = []
            for copy in plan:
                if not self.apply:
                    done.append(copy)
                    continue
                if copy == "local":
                    ok = self.git("branch", "-D", name).ok
                else:
                    ok = self.git("push", "origin", "--delete", name,
                                  long=True).ok
                if ok:
                    done.append(copy)
                else:
                    self.keep("branch " + name, copy, "delete failed",
                              "git branch -D " + name if copy == "local"
                              else "git push origin --delete " + name)
            if done:
                self.lines.append("%s: branch %s (%s)"
                                  % ("removed" if self.apply
                                     else "would remove", name,
                                     ", ".join(done)))
                self.n += 1
            if hold:
                self.keep("branch " + name, "origin", hold,
                          self.hold_suggestion(hold))

    # ---- panes

    def close_pane(self, handle, path, why, machine=None):
        where = machine or "this machine"
        if not self.apply:
            self.lines.append("would close: pane %s in %s (%s)"
                              % (handle, path, why))
            self.n += 1
            return
        if self.orca_act(["terminal", "close", "--terminal", handle,
                          "--json"], machine):
            self.lines.append("closed: pane %s in %s (%s)"
                              % (handle, path, why))
            self.n += 1
        else:
            cmd = "orca terminal close --terminal " + handle
            if machine:
                cmd += " --environment " + machine
            self.keep("pane " + handle, where, "close failed", cmd)

    @staticmethod
    def pane_why(term, gone):
        if term.get("connected") is False:
            return "exited"
        if term.get("orphaned") is True:
            return "orphaned"
        if gone:
            return "worktree gone"
        return None

    def do_panes(self):
        if self.kind != "orca" or not self.term_ok or not self.repo_id:
            return
        root = real(self.root)
        known = None
        if self.wts_ok:
            known = set(real(w["path"]) for w in self.wts)
            known.update(real(r.get("path")) for r in self.local_rows
                         if r.get("repoId") == self.repo_id)
        prefix = self.repo_id + "::"
        for term in self.terminals:
            wid = str(term.get("worktreeId") or "")
            handle = term.get("handle")
            if not handle or not wid.startswith(prefix):
                continue
            path = term.get("worktreePath") or wid[len(prefix):]
            if real(path) == root or real(path) in self.removed_paths:
                continue
            gone = known is not None and (real(path) not in known
                                          or not os.path.isdir(path))
            why = self.pane_why(term, gone)
            if why:
                self.close_pane(str(handle), path, why)

    def do_remote_panes(self):
        for machine in self.machines:
            name = machine["name"]
            for term in machine["terminals"]:
                wid = str(term.get("worktreeId") or "")
                handle = term.get("handle")
                repo = wid.split("::", 1)[0]
                if (not handle or "::" not in wid
                        or repo not in machine["repo_ids"]):
                    continue
                path = os.path.normpath(
                    term.get("worktreePath") or wid.split("::", 1)[1])
                if path in machine["mains"]:
                    continue
                why = self.pane_why(term, path not in machine["paths"])
                if why:
                    self.close_pane(str(handle), path, why, name)

    # ---- processes

    def do_processes(self):
        if not self.apply:
            return
        script = os.path.join(self.plugin, "bin", "agent-resources.sh")
        env = dict(self.env, AGENT_RELIEF_REPO=self.root)
        res = run([script, "stop-leftovers"], cwd=self.root,
                  timeout=self.t * 3, env=env)
        for line in res.out.splitlines():
            line = line.rstrip()
            if not line.startswith("stopped "):
                continue
            m = re.match(r"stopped (\d+)(\s|$)", line)
            if m:
                count = int(m.group(1))
                if count == 0:
                    continue
            else:
                count = 1
            self.lines.append(line)
            self.n += count

    # ---- the whole sweep

    def sweep(self):
        self.gather_git()
        self.base()
        self.gather_orca()
        self.do_worktrees()
        self.do_remote_worktrees()
        self.do_branches()
        self.do_panes()
        self.do_remote_panes()
        self.do_processes()

    # ---- output

    def render(self):
        out = []
        m = len(self.kept)
        if self.short:
            loud = [t for t, quiet in self.notes if not quiet]
            if self.n == 0 and m == 0 and not loud:
                return out
            line = "CLEANUP: %s %d, kept %d." % (
                "removed" if self.apply else "would remove", self.n, m)
            if m:
                line += " Table for the human: %s/bin/agent-cleanup.sh" \
                    % self.plugin
            out.append(line)
            for text in loud:
                out.append("CLEANUP: " + text)
            return out
        out.append("=== cleanup ===")
        if not self.lines and not self.notes and m == 0:
            out.append("nothing to clean")
            return out
        out.extend(self.lines)
        for text, _quiet in self.notes:
            out.append(text)
        out.append("kept: %d" % m)
        if m:
            out.append("what | where | why kept | suggestion")
            for row in self.kept:
                out.append(" | ".join(row))
        return out


def main(argv):
    root = plugin = kind = ""
    apply_ = short = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--root" and i + 1 < len(argv):
            root = argv[i + 1]
            i += 1
        elif arg == "--plugin" and i + 1 < len(argv):
            plugin = argv[i + 1]
            i += 1
        elif arg == "--kind" and i + 1 < len(argv):
            kind = argv[i + 1]
            i += 1
        elif arg == "--apply":
            apply_ = True
        elif arg == "--short":
            short = True
        else:
            sys.stderr.write("agent_cleanup.py: run bin/agent-cleanup.sh\n")
            return 2
        i += 1
    if not root or not plugin:
        sys.stderr.write("agent_cleanup.py: run bin/agent-cleanup.sh\n")
        return 2
    sweep = Sweep(root, plugin, kind or "plain", apply_, short)
    try:
        sweep.sweep()
    except Exception as exc:  # a sweep never fails its caller
        sweep.note("internal error (%s)" % type(exc).__name__)
    for line in sweep.render():
        sys.stdout.write(line + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
