"""Failing tests for the cleanup sweep. Written by the task manager first.

CONTRACT. bin/agent-cleanup.sh (bash entry, executable) + bin/agent_cleanup.py
(the logic, python3). One mechanical sweep, never an agent.

    agent-cleanup.sh              list: what --apply would do, then the kept
                                  table. Changes nothing (a git fetch is fine)
    agent-cleanup.sh --apply      remove the SAFE items, then the kept table
    agent-cleanup.sh --short      (with or without --apply) the hook form
    agent-cleanup.sh -h           usage (names --apply), exit 0
    anything else                 usage on stderr, exit 2

Main manager only. role_read (agent-roots.sh): spawned (AGENT_ROLE set),
second (human-direct Helper) and closed print one line on stderr with
"REFUSED" and "main manager only", exit 1, no orca call, no git change.
main and takeover run.

Own repo only: PROJECT_ROOT (roots_read) and the Orca rows of this repo.
Never another repo.

Base: origin/main after `git fetch --prune origin`. No origin remote or no
origin/main: worktrees and branches are not looked at at all (full mode says
"no origin/main", --short says nothing about it). Fetch fails or times out:
note "fetch failed, checked against the last known origin/main".

Runtime: bin/agent-runtime.sh runtime_kind. orca -> panes and paired
machines too. plain or cloud -> no orca call at all, and no worktree is ever
removed (why kept: "not orca"), branches still are.

Timeouts: AGENT_CLEANUP_TIMEOUT seconds (default 5) per orca call; git fetch
and git push 3x that. A call cut off kills its whole process group, so a hung
orca never hangs the sweep.

A local worktree (git worktree list, not the main checkout) is SAFE when all
hold, else it is KEPT with every failing reason, joined by ", ":
    runtime is orca                        else "not orca"
    on a branch                            else "no branch"
    no ps agent in state working or
      permission at that path              else "live agent"
    no agent_worktree.txt line for that
      path with status working or final,
      and no human-direct line             else "registered <status>" /
                                                "registered human-direct"
    `git status --porcelain` is empty      else "uncommitted changes"
    no commit missing from origin          else "unpushed"
    branch tip is an ancestor of
      origin/main                          else "unmerged"
    tip is not on origin/main's
      first-parent line (a new branch
      that never had a commit of its own)  else "no own commits"

--apply on a SAFE local worktree, in this order:
    orca terminal close --worktree path:<p> --all --json   (Orca-managed only)
    orca worktree rm --worktree path:<p> --json   Orca-managed (its path is a
        row of this repo in `orca worktree list --json`), never --force
    else git worktree remove <p>, never --force
    git branch -D <branch> (when it is still there)
    git push origin --delete <branch> (when origin has it; see branches)
    agent-file.sh worktree rm <p> (when agent_worktree.txt has its line)
    line: "removed: worktree <p> (branch <b>)"; list mode "would remove: ..."

Branches with no worktree (not main, not checked out anywhere):
    tip ancestor of origin/main -> delete local and origin copy
        "removed: branch <b> (<where>)", where = "local", "origin" or
        "local, origin"; list mode "would remove: ..."
    else -> KEPT, why "unmerged"
    An origin branch is never deleted while a paired machine is unreachable
    (KEPT, why names "unreachable") or while a paired machine has a worktree
    on it. main is never deleted.

Panes (orca only), this repo's terminals (worktreeId "<repoId>::<path>")
outside the main checkout:
    connected false -> "exited"; orphaned true -> "orphaned"; worktree no
    longer there -> "worktree gone"
    orca terminal close --terminal <handle> --json
    line: "closed: pane <handle> in <path> (<why>)"; list "would close: ..."
    Never a pane of the main checkout, of another repo, or a live one.

Done panes (orca only, scope add 2 of show-todo, owner 2026-11-02): a pane of
this repo in a local worktree the sweep keeps (not the main checkout), where
every ps agent at that path is in state "done" (finished and idle; "idle",
"working", "permission" are not), is closed when its task is finished:
    task name   the agent_worktree.txt line's module (field 2) for that path,
                else the folder name
    finished    no open agent_todo.txt line of that name, and either
                agent_completed.txt has a line of that name (done or
                dropped), or the path has no agent_worktree.txt line and its
                branch tip is merged into origin/main
    line        "closed: pane <handle> in <path> (done, task finished)";
                list mode "would close: ..."
    not finished, or a human-direct line for that path -> kept row
                "pane <handle>" | "this machine" | "done pane, task <name> not
                finished" (human-direct: "done pane, human-direct") |
                a suggestion. Never closed: it may wait on a merge, a
                question or a decision.

Paired machines (orca only): `orca environment list --json` ->
result.environments[].name. Per machine, every call adds --environment
<name>: worktree list, worktree ps, terminal list. A machine that fails or
times out: line "<name> unreachable, not checked", skipped, exit stays 0.
Its rows of this repo: projectId equal to this repo's (the local list row of
PROJECT_ROOT). Its worktrees are checked like local ones from their row
(path, branch, head), except uncommitted changes, which cannot be seen from
here: such a worktree is always KEPT; when nothing else fails, why
"changes on <name> not checked from here", suggestion
"orca worktree rm --environment <name> --worktree path:<path>".
Its panes: same rules, the close call adds --environment <name>.

Panes of a worktree being removed are closed by its --all call and get no
line of their own. A paired machine's "worktree no longer there" = its path
is not a row of that machine's worktree list.

Pipeline processes (--apply only): runs
`<plugin>/bin/agent-resources.sh stop-leftovers` (never sourced) with
AGENT_RELIEF_REPO set to PROJECT_ROOT; prints each of its lines that starts
with "stopped " as it is, except a "stopped 0 ..." line (not printed, not
counted). "stopped <N> ..." counts N, any other "stopped ..." line counts 1.

agent-resources.sh stop-leftovers (new verb, run directly like relief): the
pipeline's own leftovers only, no human table, no RESOURCES line, no RAM/CPU
reading:
    "stopped <n> finished test monitors": test monitor loops
        (auto_pipeline_*/plugin/bin/agent-monitor.sh) whose auto_pipeline_*
        folder no longer exists; a test still running keeps its loop
    then relief_kill_orphan_monitors, limited to monitors whose repo root is
        AGENT_RELIEF_REPO when that is set (another repo's monitor stays)
    AGENT_RELIEF_ONLY_UNDER scopes both, as for relief.

Full output:
    === cleanup ===
    removed / would remove / closed / would close / stopped lines
    "<name> unreachable, not checked" and other notes
    kept: <m>
    what | where | why kept | suggestion       (only when m > 0)
    <one row per KEPT item, 4 fields split by " | ">
        worktree rows: "worktree <path>", where "this machine" or <name>
        branch rows:   "branch <name>", where "local", "origin" or
                       "local, origin"
    Nothing removed, closed or stopped, nothing kept, no note:
    "=== cleanup ===" then "nothing to clean", nothing else.

--short (hooks): nothing removed, closed or stopped, nothing kept, no note ->
no output at all. Else:
    "CLEANUP: removed <n>, kept <m>."   (list mode: "would remove <n>")
    + " Table for the human: <plugin>/bin/agent-cleanup.sh" when m > 0
    then one "CLEANUP: <note>" line per note
    n = worktrees removed + branches removed + panes closed + processes
    stopped. A branch removed with its worktree is not counted again.

Wiring (main manager or takeover only; never compact, never clear):
    agent-start.sh    a session start runs --apply --short; its lines sit
                      before the state block, inside the 2000-byte cap; the
                      auto resume it starts gets AGENT_CLEANUP_DONE=1
    agent-resume.sh   runs --apply --short (--dry-run: --short, list mode)
                      before it reads agent_worktree.txt, unless
                      AGENT_CLEANUP_DONE=1; its lines print last
    agent-file.sh     todo done, when agent_todo.txt is then empty and
                      agent_worktree.txt has no working, final or
                      human-direct line: --apply --short after the TIME DATA
                      line. A failed sweep never fails todo done.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase
from test_output_hook import pointer_part

HEADER = "what | where | why kept | suggestion"
REPO_ID = "repo-1"
PROJECT_ID = "github:owner/project"
OTHER_REPO_ID = "repo-2"


def git(path, *args, **kwargs):
    result = subprocess.run(["git", "-C", path] + list(args),
                            capture_output=True, text=True)
    if kwargs.get("check", True) and result.returncode != 0:
        raise AssertionError("git %s failed: %s" % (" ".join(args),
                                                     result.stderr))
    return result.stdout.strip()


class CleanupCase(ScriptCase):
    """A project with a bare origin, main pushed, Orca knowing the repo."""

    script = "agent-cleanup.sh"

    def setUp(self):
        super().setUp()
        r = self.repo
        self.origin = os.path.join(r.base, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", self.origin],
                       check=True, capture_output=True)
        git(r.dir, "branch", "-M", "main")
        git(r.dir, "remote", "add", "origin", self.origin)
        git(r.dir, "push", "-q", "-u", "origin", "main")
        self.wts = os.path.join(r.base, "wts")
        os.mkdir(self.wts)
        self.list_rows = [self.list_row(r.dir, "main", main=True)]
        self.terminals = []
        self.save_orca()

    # ---- fixture ----

    def list_row(self, path, branch, main=False, head=None,
                 repo_id=REPO_ID, project_id=PROJECT_ID, host="local"):
        return {
            "id": "%s::%s" % (repo_id, path),
            "repoId": repo_id,
            "projectId": project_id,
            "hostId": host,
            "path": path,
            "branch": "refs/heads/%s" % branch if branch else None,
            "head": head or (git(path, "rev-parse", "HEAD")
                             if os.path.isdir(path) else "0" * 40),
            "isMainWorktree": main,
            "displayName": os.path.basename(path),
        }

    def term(self, handle, path, connected=True, orphaned=False,
             repo_id=REPO_ID, agent=None):
        row = {"handle": handle,
               "worktreeId": "%s::%s" % (repo_id, path),
               "worktreePath": path, "connected": connected,
               "orphaned": orphaned, "title": handle}
        if agent:
            row["agentIdentity"] = agent
        return row

    def save_orca(self):
        self.repo.set_orca_answer(
            "list.json", {"ok": True, "result": {"worktrees": self.list_rows}})
        self.repo.set_orca_answer(
            "terminals.json",
            {"ok": True, "result": {"terminals": self.terminals}})

    def commit_in(self, path, name):
        with open(os.path.join(path, name), "w") as fh:
            fh.write(name + "\n")
        git(path, "add", name)
        git(path, "commit", "-q", "-m", name)

    def worktree(self, name, commits=1, push=True, merge=False, orca=True,
                 dirty=False, unpushed=0):
        """A git worktree of the project on branch feat/<name>."""
        r = self.repo
        path = os.path.join(self.wts, name)
        branch = "feat/" + name
        git(r.dir, "worktree", "add", "-q", "-b", branch, path, "main")
        for i in range(commits):
            self.commit_in(path, "%s_%d.txt" % (name, i))
        if push:
            git(path, "push", "-q", "-u", "origin", branch)
        if merge:
            git(r.dir, "merge", "-q", "--no-ff", "-m", "Merge " + branch,
                branch)
            git(r.dir, "push", "-q", "origin", "main")
        for i in range(unpushed):
            self.commit_in(path, "%s_late_%d.txt" % (name, i))
        if dirty:
            with open(os.path.join(path, "notes.txt"), "w") as fh:
                fh.write("not committed\n")
        if orca:
            self.list_rows.append(self.list_row(path, branch))
            self.save_orca()
        return path, branch

    def merged_worktree(self, name="done", **kwargs):
        return self.worktree(name, merge=True, **kwargs)

    def branch_only(self, name, merge=True, push=True):
        """A branch with one commit and no worktree."""
        r = self.repo
        branch = "feat/" + name
        git(r.dir, "checkout", "-q", "-b", branch)
        self.commit_in(r.dir, name + ".txt")
        git(r.dir, "checkout", "-q", "main")
        if push:
            git(r.dir, "push", "-q", "origin", branch)
        if merge:
            git(r.dir, "merge", "-q", "--no-ff", "-m", "Merge " + branch,
                branch)
            if push:
                git(r.dir, "push", "-q", "origin", "main")
        return branch

    def has_local(self, branch):
        return bool(git(self.repo.dir, "branch", "--list", branch))

    def has_origin(self, branch):
        return bool(git(self.origin, "branch", "--list", branch))

    # ---- running ----

    def sweep(self, *args, **kwargs):
        return self.repo.run("agent-cleanup.sh", *args, **kwargs)

    def ok(self, *args, **kwargs):
        return self.assertOk(self.sweep(*args, **kwargs))

    def rows(self, out):
        lines = self.lines(out)
        if HEADER not in lines:
            return []
        rows = []
        for line in lines[lines.index(HEADER) + 1:]:
            if " | " not in line:
                break
            rows.append(line.split(" | "))
        return rows

    def row_for(self, out, what):
        for row in self.rows(out):
            if row[0] == what:
                return row
        self.fail("no kept row for %r in:\n%s" % (what, out))

    def orca_calls(self, verb):
        return [c for c in self.repo.calls() if c[:2] == verb]


# ---------------------------------------------------------------- usage


class TestUsage(CleanupCase):
    def test_help_names_apply(self):
        out = self.ok("-h")
        self.assertIn("--apply", out)

    def test_an_unknown_argument_is_refused(self):
        result = self.sweep("--force")
        self.assertEqual(result.returncode, 2)

    def test_list_mode_starts_with_the_header(self):
        out = self.ok()
        self.assertEqual(self.lines(out)[0], "=== cleanup ===")

    def test_nothing_at_all_says_so(self):
        out = self.ok("--apply")
        self.assertEqual([l for l in self.lines(out) if l],
                         ["=== cleanup ===", "nothing to clean"])


class TestMainManagerOnly(CleanupCase):
    def setUp(self):
        super().setUp()
        self.path, self.branch = self.merged_worktree()
        self.repo.clear_calls()

    def assertRefused(self, result):
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("REFUSED", result.stderr)
        self.assertIn("main manager only", result.stderr)
        self.assertTrue(os.path.isdir(self.path))
        self.assertTrue(self.has_local(self.branch))
        self.assertTrue(self.has_origin(self.branch))
        self.assertEqual(self.repo.calls(), [])

    def test_a_task_manager_is_refused(self):
        self.assertRefused(self.sweep("--apply",
                                      env={"AGENT_ROLE": "task-manager"}))

    def test_a_worker_is_refused_even_in_list_mode(self):
        self.assertRefused(self.sweep(env={"AGENT_ROLE": "worker"}))

    def test_a_human_direct_helper_is_refused(self):
        # a live main manager (this test process) holds the lock
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-11-02 10:00 - -\n" % os.getpid())
        self.assertRefused(self.sweep("--apply",
                                      env={"CLAUDE_PID": "999999"}))

    def test_the_main_manager_runs(self):
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-11-02 10:00 - -\n" % os.getpid())
        self.ok("--apply", env={"CLAUDE_PID": str(os.getpid())})
        self.assertFalse(os.path.exists(self.path))


# ---------------------------------------------------------------- list mode


class TestListChangesNothing(CleanupCase):
    def setUp(self):
        super().setUp()
        self.path, self.branch = self.merged_worktree()
        self.gone = self.branch_only("old")
        self.wip, _ = self.worktree("wip")
        self.terminals = [self.term("term_x", self.wip, connected=False)]
        self.save_orca()
        self.repo.clear_calls()
        self.out = self.ok()

    def test_it_says_what_it_would_remove(self):
        self.assertIn("would remove: worktree %s (branch %s)"
                      % (self.path, self.branch), self.lines(self.out))
        self.assertIn("would remove: branch %s (local, origin)" % self.gone,
                      self.lines(self.out))

    def test_it_says_what_it_would_close(self):
        self.assertIn("would close: pane term_x in %s (exited)" % self.wip,
                      self.lines(self.out))

    def test_everything_is_still_there(self):
        self.assertTrue(os.path.isdir(self.path))
        for branch in (self.branch, self.gone):
            self.assertTrue(self.has_local(branch))
            self.assertTrue(self.has_origin(branch))

    def test_no_orca_call_changes_anything(self):
        for call in self.repo.calls():
            self.assertNotIn(call[:2], (["worktree", "rm"],
                                        ["terminal", "close"]))


# ---------------------------------------------------------------- apply: safe


class TestApplyRemovesAMergedWorktree(CleanupCase):
    def setUp(self):
        super().setUp()
        self.path, self.branch = self.merged_worktree()
        self.repo.set_worktree_lines([(self.path, "done", "idle"),
                                      ("/elsewhere", "other", "working")])
        self.repo.clear_calls()
        self.out = self.ok("--apply")

    def test_the_worktree_is_gone(self):
        self.assertFalse(os.path.exists(self.path))

    def test_orca_closed_its_panes_then_removed_it(self):
        calls = self.repo.calls()
        close = ["terminal", "close", "--worktree", "path:" + self.path,
                 "--all", "--json"]
        rm = ["worktree", "rm", "--worktree", "path:" + self.path, "--json"]
        self.assertIn(close, calls)
        self.assertIn(rm, calls)
        self.assertLess(calls.index(close), calls.index(rm))

    def test_never_forced(self):
        for call in self.repo.calls():
            self.assertNotIn("--force", call)

    def test_the_branch_is_gone_here_and_on_origin(self):
        self.assertFalse(self.has_local(self.branch))
        self.assertFalse(self.has_origin(self.branch))

    def test_its_worktree_line_is_dropped_the_other_stays(self):
        text = self.repo.read("agent_worktree.txt")
        self.assertNotIn(self.path, text)
        self.assertIn("/elsewhere | other | working", text)

    def test_it_says_so(self):
        self.assertIn("removed: worktree %s (branch %s)"
                      % (self.path, self.branch), self.lines(self.out))

    def test_main_is_untouched(self):
        self.assertTrue(self.has_local("main"))
        self.assertTrue(self.has_origin("main"))
        self.assertTrue(os.path.isdir(self.repo.dir))


class TestApplyPlainGitWorktree(CleanupCase):
    def test_a_worktree_orca_does_not_know_is_removed_with_git(self):
        path, branch = self.merged_worktree(orca=False)
        self.repo.clear_calls()
        self.ok("--apply")
        self.assertFalse(os.path.exists(path))
        self.assertFalse(self.has_local(branch))
        self.assertEqual(self.orca_calls(["worktree", "rm"]), [])
        self.assertNotIn(path, git(self.repo.dir, "worktree", "list"))

    def test_an_idle_or_done_agent_does_not_keep_it(self):
        path, _ = self.merged_worktree()
        self.repo.set_panes([{"path": path, "agents": ["done", "idle"]}])
        self.ok("--apply")
        self.assertFalse(os.path.exists(path))


# ---------------------------------------------------------------- apply: kept


class KeptCase(CleanupCase):
    def assertKept(self, path, branch, why):
        out = self.ok("--apply")
        self.assertTrue(os.path.isdir(path), "removed, should be kept")
        self.assertTrue(self.has_local(branch))
        row = self.row_for(out, "worktree " + path)
        self.assertEqual(row[1], "this machine")
        self.assertIn(why, row[2])
        self.assertTrue(row[3].strip(), "no suggestion")
        self.assertEqual(self.orca_calls(["worktree", "rm"]), [])
        return out


class TestKept(KeptCase):
    def test_unmerged(self):
        path, branch = self.worktree("wip")
        self.assertKept(path, branch, "unmerged")
        self.assertTrue(self.has_origin(branch))

    def test_uncommitted_changes(self):
        path, branch = self.merged_worktree(dirty=True)
        self.assertKept(path, branch, "uncommitted changes")
        self.assertTrue(os.path.exists(os.path.join(path, "notes.txt")))

    def test_unpushed(self):
        path, branch = self.merged_worktree(unpushed=1)
        self.assertKept(path, branch, "unpushed")

    def test_never_pushed_at_all(self):
        path, branch = self.worktree("local", push=False)
        self.assertKept(path, branch, "unpushed")

    def test_a_working_agent(self):
        path, branch = self.merged_worktree()
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        self.assertKept(path, branch, "live agent")

    def test_an_agent_waiting_for_permission(self):
        path, branch = self.merged_worktree()
        self.repo.set_panes([{"path": path, "agents": ["idle", "permission"]}])
        self.assertKept(path, branch, "live agent")

    def test_a_working_line(self):
        path, branch = self.merged_worktree()
        self.repo.set_worktree_lines([(path, "done", "working")])
        self.assertKept(path, branch, "registered working")

    def test_a_final_line(self):
        path, branch = self.merged_worktree()
        self.repo.set_worktree_lines([(path, "done", "final")])
        self.assertKept(path, branch, "registered final")

    def test_a_human_direct_line(self):
        path, branch = self.merged_worktree()
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            fh.write("%s | task manager, human-direct | task: X | "
                     "since 2026-11-02 10:00\n" % path)
        self.assertKept(path, branch, "registered human-direct")

    def test_a_new_branch_with_no_commit_of_its_own(self):
        path, branch = self.worktree("fresh", commits=0)
        self.assertKept(path, branch, "no own commits")

    def test_a_detached_worktree(self):
        r = self.repo
        path = os.path.join(self.wts, "detached")
        git(r.dir, "worktree", "add", "-q", "--detach", path, "main")
        out = self.ok("--apply")
        self.assertTrue(os.path.isdir(path))
        self.assertIn("no branch", self.row_for(out, "worktree " + path)[2])

    def test_every_reason_is_named(self):
        path, branch = self.worktree("many", dirty=True, push=False)
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        out = self.assertKept(path, branch, "live agent")
        why = self.row_for(out, "worktree " + path)[2]
        for word in ("uncommitted changes", "unpushed", "unmerged"):
            self.assertIn(word, why)

    def test_plain_mode_never_removes_a_worktree(self):
        self.repo.set_conf("runtime", "plain")
        path, branch = self.merged_worktree()
        self.repo.clear_calls()
        self.assertKept(path, branch, "not orca")
        self.assertEqual(self.repo.calls(), [])

    def test_the_main_checkout_is_never_a_row(self):
        self.merged_worktree()
        out = self.ok("--apply")
        self.assertNotIn("worktree " + self.repo.dir,
                         [row[0] for row in self.rows(out)])


class TestTheTable(KeptCase):
    def setUp(self):
        super().setUp()
        self.wip, _ = self.worktree("wip")
        self.dirty, _ = self.merged_worktree("dirty", dirty=True)
        self.done, _ = self.merged_worktree("done")
        self.out = self.ok("--apply")

    def test_the_header(self):
        self.assertIn(HEADER, self.lines(self.out))

    def test_one_row_per_kept_item_four_fields(self):
        rows = self.rows(self.out)
        self.assertEqual(sorted(r[0] for r in rows),
                         sorted(["worktree " + self.wip,
                                 "worktree " + self.dirty]))
        for row in rows:
            self.assertEqual(len(row), 4, row)

    def test_the_kept_count(self):
        self.assertIn("kept: 2", self.lines(self.out))

    def test_the_removed_one_is_not_a_row(self):
        self.assertNotIn("worktree " + self.done,
                         [r[0] for r in self.rows(self.out)])


# ---------------------------------------------------------------- branches


class TestBranches(CleanupCase):
    def test_a_merged_branch_goes_here_and_on_origin(self):
        branch = self.branch_only("old")
        out = self.ok("--apply")
        self.assertFalse(self.has_local(branch))
        self.assertFalse(self.has_origin(branch))
        self.assertIn("removed: branch %s (local, origin)" % branch,
                      self.lines(out))

    def test_a_merged_local_only_branch(self):
        branch = self.branch_only("mine", push=False)
        # the branch was never pushed, its merge was
        git(self.repo.dir, "push", "-q", "origin", "main")
        out = self.ok("--apply")
        self.assertFalse(self.has_local(branch))
        self.assertIn("removed: branch %s (local)" % branch, self.lines(out))

    def test_a_merged_origin_only_branch(self):
        branch = self.branch_only("theirs")
        git(self.repo.dir, "branch", "-D", branch)
        out = self.ok("--apply")
        self.assertFalse(self.has_origin(branch))
        self.assertIn("removed: branch %s (origin)" % branch, self.lines(out))

    def test_an_unmerged_branch_is_kept(self):
        branch = self.branch_only("wip", merge=False)
        out = self.ok("--apply")
        self.assertTrue(self.has_local(branch))
        self.assertTrue(self.has_origin(branch))
        row = self.row_for(out, "branch " + branch)
        self.assertEqual(row[1], "local, origin")
        self.assertIn("unmerged", row[2])

    def test_main_is_never_deleted(self):
        self.branch_only("old")
        self.ok("--apply")
        self.assertTrue(self.has_local("main"))
        self.assertTrue(self.has_origin("main"))

    def test_plain_mode_still_removes_merged_branches(self):
        self.repo.set_conf("runtime", "plain")
        branch = self.branch_only("old")
        self.ok("--apply")
        self.assertFalse(self.has_local(branch))
        self.assertFalse(self.has_origin(branch))

    def test_no_origin_means_nothing_is_looked_at(self):
        git(self.repo.dir, "remote", "remove", "origin")
        branch = self.branch_only("old", push=False)
        path, _ = self.worktree("w", push=False)
        out = self.ok("--apply")
        self.assertTrue(self.has_local(branch))
        self.assertTrue(os.path.isdir(path))
        self.assertIn("no origin/main", out)
        self.assertEqual(self.ok("--apply", "--short"), "")


# ---------------------------------------------------------------- panes


class TestPanes(CleanupCase):
    def setUp(self):
        super().setUp()
        self.wip, _ = self.worktree("wip")
        self.gone = os.path.join(self.wts, "removed-long-ago")

    def run_with(self, terminals, *args):
        self.terminals = terminals
        self.save_orca()
        self.repo.clear_calls()
        return self.ok("--apply", *args)

    def closed(self):
        return [c[c.index("--terminal") + 1]
                for c in self.orca_calls(["terminal", "close"])
                if "--terminal" in c]

    def test_an_exited_pane_is_closed(self):
        out = self.run_with([self.term("t1", self.wip, connected=False)])
        self.assertEqual(self.closed(), ["t1"])
        self.assertIn(["terminal", "close", "--terminal", "t1", "--json"],
                      self.repo.calls())
        self.assertIn("closed: pane t1 in %s (exited)" % self.wip,
                      self.lines(out))

    def test_an_orphaned_pane_is_closed(self):
        out = self.run_with([self.term("t2", self.wip, orphaned=True)])
        self.assertEqual(self.closed(), ["t2"])
        self.assertIn("closed: pane t2 in %s (orphaned)" % self.wip,
                      self.lines(out))

    def test_a_pane_whose_worktree_is_gone_is_closed(self):
        out = self.run_with([self.term("t3", self.gone, agent="claude")])
        self.assertEqual(self.closed(), ["t3"])
        self.assertIn("closed: pane t3 in %s (worktree gone)" % self.gone,
                      self.lines(out))

    def test_a_live_pane_stays(self):
        self.run_with([self.term("t4", self.wip, agent="claude")])
        self.assertEqual(self.closed(), [])
        self.assertTrue(os.path.isdir(self.wip))

    def test_the_main_checkout_panes_are_never_touched(self):
        self.run_with([self.term("t5", self.repo.dir, connected=False),
                       self.term("t6", self.repo.dir, orphaned=True)])
        self.assertEqual(self.closed(), [])

    def test_another_repo_is_never_touched(self):
        self.run_with([self.term("t7", "/other/repo/wt", connected=False,
                                 repo_id=OTHER_REPO_ID),
                       self.term("t8", "/other/repo/gone",
                                 repo_id=OTHER_REPO_ID)])
        self.assertEqual(self.closed(), [])

    def test_plain_mode_has_no_panes(self):
        self.repo.set_conf("runtime", "plain")
        self.run_with([self.term("t9", self.wip, connected=False)])
        self.assertEqual(self.repo.calls(), [])


class TestDonePanes(CleanupCase):
    """A done pane is closed when its task is finished, else one kept row."""

    def setUp(self):
        super().setUp()
        self.path, self.branch = self.worktree("fin")   # pushed, not merged: kept

    def write(self, name, text):
        with open(self.repo.path(name), "w") as fh:
            fh.write(text)

    def finished(self, name="fin"):
        self.write("agent_completed.txt",
                   "2026-11-02 | %s | the login form | data repo=project type=script "
                   "lane=full mock=no est=60 work=50 wait=0 clock=70 bounces=0 workers=1 "
                   "files=2 lines=40 tests=5 adds=0\n" % name)

    def open_todo(self, name="fin"):
        self.write("agent_todo.txt", "%s | big | the login form | est 60m | "
                   "opened 2026-11-02 10:00 | by main\n" % name)

    def run_with(self, states, path=None, terminals=None, apply_=True):
        path = path or self.path
        self.repo.set_panes([{"path": path, "agents": states}])
        self.terminals = (terminals if terminals is not None
                          else [self.term("t1", path, agent="claude")])
        self.save_orca()
        self.repo.clear_calls()
        return self.ok("--apply") if apply_ else self.ok()

    def closed(self):
        return [c[c.index("--terminal") + 1]
                for c in self.orca_calls(["terminal", "close"])
                if "--terminal" in c]

    def test_a_done_pane_of_a_finished_task_is_closed(self):
        self.repo.set_worktree_lines([(self.path, "fin", "idle")])
        self.finished()
        out = self.run_with(["done"])
        self.assertEqual(self.closed(), ["t1"])
        self.assertIn(["terminal", "close", "--terminal", "t1", "--json"], self.repo.calls())
        self.assertIn("closed: pane t1 in %s (done, task finished)" % self.path,
                      self.lines(out))
        self.assertTrue(os.path.isdir(self.path), "the worktree itself stays (unmerged)")

    def test_a_dropped_task_is_finished_too(self):
        self.repo.set_worktree_lines([(self.path, "fin", "working")])
        self.write("agent_completed.txt", "2026-11-02 | fin | the login form | est 60m "
                   "actual - | dropped: the owner said no\n")
        self.run_with(["done"])
        self.assertEqual(self.closed(), ["t1"])

    def test_the_task_name_is_the_module_of_its_line(self):
        self.repo.set_worktree_lines([(self.path, "login-form", "idle")])
        self.finished("login-form")
        self.run_with(["done"])
        self.assertEqual(self.closed(), ["t1"])

    def test_a_done_pane_of_an_open_task_is_kept(self):
        self.repo.set_worktree_lines([(self.path, "fin", "final")])
        self.open_todo()
        out = self.run_with(["done"])
        self.assertEqual(self.closed(), [])
        row = self.row_for(out, "pane t1")
        self.assertEqual(row[1], "this machine")
        self.assertIn("done pane, task fin not finished", row[2])
        self.assertTrue(row[3].strip(), "no suggestion")

    def test_an_open_todo_line_wins_over_an_old_completed_one(self):
        self.repo.set_worktree_lines([(self.path, "fin", "working")])
        self.finished()
        self.open_todo()
        self.run_with(["done"])
        self.assertEqual(self.closed(), [])

    def test_no_line_and_not_merged_is_kept(self):
        # a task dispatched from another machine never has a line here: it may
        # wait on its merge
        out = self.run_with(["done"])
        self.assertEqual(self.closed(), [])
        self.assertIn("not finished", self.row_for(out, "pane t1")[2])

    def test_no_line_and_merged_is_finished(self):
        path, _ = self.merged_worktree("old", dirty=True)   # kept: uncommitted
        out = self.run_with(["done"], path=path)
        self.assertEqual(self.closed(), ["t1"])
        self.assertIn("closed: pane t1 in %s (done, task finished)" % path, self.lines(out))
        self.assertTrue(os.path.isdir(path))

    def test_a_human_direct_session_is_kept(self):
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            fh.write("%s | task manager, human-direct | task: Stock Lock Page | "
                     "since 2026-11-02 10:00\n" % self.path)
        self.finished()
        out = self.run_with(["done"])
        self.assertEqual(self.closed(), [])
        self.assertIn("done pane, human-direct", self.row_for(out, "pane t1")[2])

    def test_a_busy_or_idle_pane_is_never_closed(self):
        self.repo.set_worktree_lines([(self.path, "fin", "idle")])
        self.finished()
        for states in (["working"], ["permission"], ["done", "working"], ["idle"],
                       ["done", "permission"]):
            with self.subTest(states=states):
                out = self.run_with(states)
                self.assertEqual(self.closed(), [])
                self.assertNotIn("pane t1", [r[0] for r in self.rows(out)])

    def test_list_mode_only_says_it(self):
        self.repo.set_worktree_lines([(self.path, "fin", "idle")])
        self.finished()
        out = self.run_with(["done"], apply_=False)
        self.assertEqual(self.closed(), [])
        self.assertIn("would close: pane t1 in %s (done, task finished)" % self.path,
                      self.lines(out))

    def test_the_main_checkout_and_another_repo_are_never_touched(self):
        self.finished(os.path.basename(self.repo.dir))
        self.run_with(["done"], path=self.repo.dir,
                      terminals=[self.term("t5", self.repo.dir, agent="claude")])
        self.assertEqual(self.closed(), [])
        self.finished()
        self.run_with(["done"], terminals=[self.term("t7", self.path, agent="claude",
                                                     repo_id=OTHER_REPO_ID)])
        self.assertEqual(self.closed(), [])

    def test_a_removed_worktree_is_closed_once(self):
        path, _ = self.merged_worktree("gone")      # safe: removed with its panes
        self.repo.set_worktree_lines([(path, "gone", "idle")])
        self.finished("gone")
        self.run_with(["done"], path=path)
        self.assertFalse(os.path.exists(path))
        self.assertEqual(self.closed(), [])          # --worktree --all did it
        self.assertEqual(len(self.orca_calls(["terminal", "close"])), 1)


# ---------------------------------------------------------------- paired machines


class RemoteCase(CleanupCase):
    ENV = "pc2"
    REMOTE_MAIN = "/remote/auto/main"

    def setUp(self):
        super().setUp()
        self.repo.set_orca_answer(
            "envs.json", {"ok": True, "result": {"environments": [
                {"name": self.ENV}]}})
        self.remote_rows = [self.list_row(self.REMOTE_MAIN, "main", main=True,
                                          head="1" * 40, repo_id="r-remote")]
        self.remote_terms = []
        self.remote_ps = []
        self.save_remote()

    def save_remote(self):
        r = self.repo
        r.set_orca_answer("list.json", {"ok": True, "result": {
            "worktrees": self.remote_rows}}, env=self.ENV)
        r.set_orca_answer("terminals.json", {"ok": True, "result": {
            "terminals": self.remote_terms}}, env=self.ENV)
        rows = [{"path": p, "agents": [{"state": s, "agentType": "claude"}
                                       for s in states]}
                for p, states in self.remote_ps]
        r.set_orca_answer("ps.json", {"ok": True, "result": {
            "worktrees": rows}}, env=self.ENV)

    def remote_worktree(self, path, branch, head):
        self.remote_rows.append(self.list_row(path, branch, head=head,
                                              repo_id="r-remote"))
        self.save_remote()

    def merged_remote(self, name="rdone"):
        """A branch made and merged here, standing in for one made on pc2."""
        branch = self.branch_only(name)
        head = git(self.repo.dir, "rev-parse", branch)
        git(self.repo.dir, "branch", "-D", branch)
        path = "/remote/wts/" + name
        self.remote_worktree(path, branch, head)
        return path, branch


class TestRemote(RemoteCase):
    def test_every_remote_call_names_the_machine(self):
        self.ok("--apply")
        remote = [c for c in self.repo.calls() if "--environment" in c]
        verbs = sorted(" ".join(c[:2]) for c in remote)
        for verb in ("worktree list", "worktree ps", "terminal list"):
            self.assertIn(verb, verbs)
        for call in remote:
            self.assertEqual(call[call.index("--environment") + 1], self.ENV)

    def test_a_merged_remote_worktree_is_listed_never_removed(self):
        path, branch = self.merged_remote()
        out = self.ok("--apply")
        self.assertEqual(self.orca_calls(["worktree", "rm"]), [])
        row = self.row_for(out, "worktree " + path)
        self.assertEqual(row[1], self.ENV)
        self.assertIn("changes on %s not checked from here" % self.ENV, row[2])
        self.assertIn("orca worktree rm --environment %s --worktree path:%s"
                      % (self.ENV, path), row[3])

    def test_its_branch_stays_on_origin(self):
        _, branch = self.merged_remote()
        self.ok("--apply")
        self.assertTrue(self.has_origin(branch))

    def test_a_live_remote_agent(self):
        path, _ = self.merged_remote()
        self.remote_ps = [(path, ["working"])]
        self.save_remote()
        out = self.ok("--apply")
        self.assertIn("live agent", self.row_for(out, "worktree " + path)[2])

    def test_a_remote_head_origin_never_saw(self):
        path = "/remote/wts/secret"
        self.remote_worktree(path, "feat/secret", "ab" * 20)
        out = self.ok("--apply")
        self.assertIn("unpushed", self.row_for(out, "worktree " + path)[2])

    def test_another_repo_on_the_machine_is_ignored(self):
        self.remote_rows.append(self.list_row(
            "/remote/other/wt", "feat/x", head="2" * 40, repo_id="r-other",
            project_id="github:owner/other"))
        self.save_remote()
        out = self.ok("--apply")
        self.assertNotIn("/remote/other/wt", out)

    def test_an_exited_remote_pane_is_closed_there(self):
        path, _ = self.merged_remote()
        self.remote_terms = [self.term("rt1", path, connected=False,
                                       repo_id="r-remote"),
                             self.term("rt2", self.REMOTE_MAIN,
                                       connected=False, repo_id="r-remote")]
        self.save_remote()
        self.ok("--apply")
        closes = self.orca_calls(["terminal", "close"])
        self.assertEqual(len(closes), 1, closes)
        call = closes[0]
        self.assertEqual(call[call.index("--terminal") + 1], "rt1")
        self.assertEqual(call[call.index("--environment") + 1], self.ENV)


class TestUnreachable(RemoteCase):
    def test_down_is_one_line_and_the_rest_still_runs(self):
        self.repo.set_orca_env_state(self.ENV, "down")
        path, _ = self.merged_worktree()
        out = self.ok("--apply")
        self.assertIn("%s unreachable, not checked" % self.ENV,
                      self.lines(out))
        self.assertFalse(os.path.exists(path))

    def test_a_hang_never_hangs_the_sweep(self):
        self.repo.set_orca_env_state(self.ENV, "hang")
        started = time.time()
        out = self.ok("--apply", timeout=40)
        self.assertLess(time.time() - started, 20)
        self.assertIn("%s unreachable, not checked" % self.ENV,
                      self.lines(out))

    def test_an_origin_branch_waits_for_the_machine(self):
        self.repo.set_orca_env_state(self.ENV, "down")
        branch = self.branch_only("old")
        out = self.ok("--apply")
        self.assertFalse(self.has_local(branch))
        self.assertTrue(self.has_origin(branch))
        row = self.row_for(out, "branch " + branch)
        self.assertEqual(row[1], "origin")
        self.assertIn("unreachable", row[2])

    def test_short_form_line(self):
        self.repo.set_orca_env_state(self.ENV, "down")
        out = self.ok("--apply", "--short")
        self.assertIn("CLEANUP: %s unreachable, not checked" % self.ENV,
                      self.lines(out))


# ---------------------------------------------------------------- processes


FAKE_RESOURCES = """#!/usr/bin/env bash
echo "$* repo=${AGENT_RELIEF_REPO:-}" >> "%s"
[ "${1:-}" = stop-leftovers ] || exit 0
echo "stopped 2 finished test monitors"
echo "stopped 0 monitors of nothing"
echo "stopped monitor of project (no live main manager)"
"""


class TestProcesses(CleanupCase):
    def setUp(self):
        super().setUp()
        self.log = os.path.join(self.repo.base, "resources.log")
        self.repo.write_bin_script("agent-resources.sh",
                                   FAKE_RESOURCES % self.log)

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as fh:
            return [l.strip() for l in fh if l.strip()]

    def test_apply_stops_the_pipeline_leftovers_of_this_repo(self):
        out = self.ok("--apply")
        self.assertEqual(self.calls(),
                         ["stop-leftovers repo=%s" % self.repo.dir])
        self.assertIn("stopped 2 finished test monitors", self.lines(out))
        self.assertIn("stopped monitor of project (no live main manager)",
                      self.lines(out))
        self.assertNotIn("stopped 0 monitors of nothing", out)

    def test_they_count(self):
        out = self.ok("--apply", "--short")
        self.assertEqual(self.lines(out)[0], "CLEANUP: removed 3, kept 0.")

    def test_list_mode_stops_nothing(self):
        self.ok()
        self.assertEqual(self.calls(), [])


# ---------------------------------------------------------------- short form


class TestShort(CleanupCase):
    def test_nothing_to_do_prints_nothing(self):
        self.assertEqual(self.ok("--apply", "--short"), "")

    def test_removed_only(self):
        self.merged_worktree()
        out = self.ok("--apply", "--short")
        self.assertEqual(self.lines(out), ["CLEANUP: removed 1, kept 0."])

    def test_removed_and_kept_points_at_the_table(self):
        self.merged_worktree()
        self.worktree("wip")
        out = self.ok("--apply", "--short")
        self.assertEqual(
            self.lines(out)[0],
            "CLEANUP: removed 1, kept 1. Table for the human: "
            "%s/bin/agent-cleanup.sh" % self.repo.plugin)

    def test_a_branch_removed_with_its_worktree_counts_once(self):
        self.merged_worktree()
        self.branch_only("old")
        out = self.ok("--apply", "--short")
        self.assertEqual(self.lines(out)[0], "CLEANUP: removed 2, kept 0.")

    def test_list_mode_says_would(self):
        path, _ = self.merged_worktree()
        out = self.ok("--short")
        self.assertEqual(self.lines(out)[0],
                         "CLEANUP: would remove 1, kept 0.")
        self.assertTrue(os.path.isdir(path))


# ---------------------------------------------------------------- the relief verb


LOOP = """#!/usr/bin/env bash
trap 'exit 0' TERM
while true; do
  sleep 300 &
  wait $!
done
"""


def alive(proc):
    return proc.poll() is None


def wait_until(fn, timeout=8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if fn():
            return True
        time.sleep(0.1)
    return fn()


class TestStopLeftovers(unittest.TestCase):
    """The real bin/agent-resources.sh, scoped to this test's own folder."""

    SCRIPT = os.path.join(ROOT, "bin", "agent-resources.sh")

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="leftover_"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def spawn(self, script, cwd=None):
        proc = subprocess.Popen(["bash", script, "start"], cwd=cwd,
                                stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                start_new_session=True)

        def reap():
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        self.addCleanup(reap)
        # running = its loop already has its `sleep` child, so bash has read
        # the script (a folder removed before that just makes bash fail)
        self.assertTrue(wait_until(lambda: alive(proc) and subprocess.run(
            ["pgrep", "-P", str(proc.pid)], capture_output=True).returncode == 0),
            "fake monitor loop never started")
        return proc

    def fake(self, *parts):
        path = os.path.join(self.base, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(LOOP)
        os.chmod(path, 0o755)
        return path

    def repo(self, name):
        path = os.path.join(self.base, name)
        os.makedirs(path)
        subprocess.run(["git", "init", "-q", path], check=True,
                       capture_output=True)
        return path

    def run_it(self, repo=""):
        with open(self.SCRIPT) as fh:
            if "AGENT_RELIEF_ONLY_UNDER" not in fh.read():
                self.fail("agent-resources.sh lost its scope guard")
        env = dict(os.environ, AGENT_FAKE_RAM="10", AGENT_FAKE_CPU="10",
                   AGENT_RELIEF_ONLY_UNDER=self.base, AGENT_RELIEF_REPO=repo)
        return subprocess.run([self.SCRIPT, "stop-leftovers"], env=env,
                              stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=60)

    def test_a_test_monitor_whose_folder_is_gone_is_stopped(self):
        script = self.fake("auto_pipeline_gone1", "plugin", "bin",
                           "agent-monitor.sh")
        proc = self.spawn(script)
        shutil.rmtree(os.path.join(self.base, "auto_pipeline_gone1"))
        result = self.run_it()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("stopped 1 finished test monitors", result.stdout)
        self.assertTrue(wait_until(lambda: not alive(proc)))

    def test_a_test_monitor_still_running_its_test_stays(self):
        script = self.fake("auto_pipeline_live1", "plugin", "bin",
                           "agent-monitor.sh")
        proc = self.spawn(script)
        result = self.run_it()
        self.assertIn("stopped 0 finished test monitors", result.stdout)
        time.sleep(0.3)
        self.assertTrue(alive(proc))

    def test_an_orphan_monitor_of_another_repo_stays(self):
        mine = self.repo("mine")
        other = self.repo("other")
        script = self.fake("tools", "agent-monitor.sh")
        proc = self.spawn(script, cwd=other)
        self.run_it(repo=mine)
        time.sleep(0.3)
        self.assertTrue(alive(proc), "another repo's monitor was stopped")

    def test_an_orphan_monitor_of_this_repo_is_stopped(self):
        mine = self.repo("mine")
        script = self.fake("tools", "agent-monitor.sh")
        proc = self.spawn(script, cwd=mine)
        result = self.run_it(repo=mine)
        self.assertIn("stopped monitor of mine", result.stdout)
        self.assertTrue(wait_until(lambda: not alive(proc)))

    def test_no_table_and_no_resources_line(self):
        result = self.run_it()
        self.assertNotIn("PROCESS | MB", result.stdout)
        self.assertNotIn("RESOURCES:", result.stdout)


# ---------------------------------------------------------------- wiring: start


class TestStartWiring(CleanupCase):
    def start(self, **kwargs):
        return self.repo.run("agent-start.sh", **kwargs)

    def test_a_main_manager_start_sweeps(self):
        path, _ = self.merged_worktree()
        out = self.assertOk(self.start())
        self.assertFalse(os.path.exists(path))
        lines = self.lines(out)
        clean = [i for i, l in enumerate(lines)
                 if l.startswith("CLEANUP: removed 1")]
        self.assertEqual(len(clean), 1, out)
        rules = next(i for i, l in enumerate(lines) if l.startswith("RULES:"))
        self.assertLess(clean[0], rules)

    def test_it_comes_before_the_state_block(self):
        self.merged_worktree()
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            fh.write("brief\n")
        lines = self.lines(self.assertOk(self.start()))
        clean = next(i for i, l in enumerate(lines) if l.startswith("CLEANUP:"))
        state = lines.index("agent_state.txt: 1 lines")
        self.assertLess(clean, state)

    def test_it_sweeps_once_even_with_auto_resume(self):
        self.merged_worktree()
        self.repo.set_conf("auto_resume", "yes")
        self.repo.clear_calls()
        self.assertOk(self.start())
        self.assertEqual(len(self.orca_calls(["environment", "list"])), 1)

    def test_a_spawned_agent_start_does_not(self):
        path, _ = self.merged_worktree()
        out = self.assertOk(self.start(env={"AGENT_ROLE": "task-manager"}))
        self.assertTrue(os.path.isdir(path))
        self.assertNotIn("CLEANUP:", out)

    def test_a_human_direct_start_does_not(self):
        path, _ = self.merged_worktree()
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-11-02 10:00 - -\n" % os.getpid())
        out = self.assertOk(self.start(env={"CLAUDE_PID": "999999"}))
        self.assertTrue(os.path.isdir(path))
        self.assertNotIn("CLEANUP:", out)

    def test_compact_and_clear_do_not(self):
        path, _ = self.merged_worktree()
        for source in ("compact", "clear"):
            with self.subTest(source=source):
                stdin = json.dumps({"cwd": self.repo.dir, "source": source,
                                    "session_id": "s-" + source})
                out = self.assertOk(self.start(stdin=stdin))
                self.assertTrue(os.path.isdir(path))
                self.assertNotIn("CLEANUP:", out)

    def test_nothing_to_clean_adds_no_line(self):
        out = self.assertOk(self.start())
        self.assertNotIn("CLEANUP:", out)

    def test_a_busy_start_still_fits_the_cap(self):
        self.repo.set_orca_answer(
            "envs.json", {"ok": True, "result": {"environments": [
                {"name": "pc2"}, {"name": "pc3"}]}})
        self.repo.set_orca_env_state("pc2", "down")
        self.repo.set_orca_env_state("pc3", "down")
        self.merged_worktree()
        self.worktree("wip")
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            for i in range(60):
                fh.write("%02d %s\n" % (i, "x" * 400))
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            for i in range(4):
                fh.write("/very/long/path/to/worktree/number_%d | module_%d | "
                         "working | since 2026-09-22 10:00\n" % (i, i))
        out = pointer_part(self.assertOk(self.start()))
        self.assertLessEqual(len(out.encode()), 2000,
                             "hook is %d bytes" % len(out.encode()))
        self.assertIn("CLEANUP: pc2 unreachable, not checked", out)
        self.assertIn("CLEANUP: pc3 unreachable, not checked", out)
        # kept: the unmerged worktree, and the merged one's origin branch,
        # which waits until every paired machine answers
        self.assertIn("CLEANUP: removed 1, kept 2.", out)


# ---------------------------------------------------------------- wiring: resume


class TestResumeWiring(CleanupCase):
    def resume(self, *args, **kwargs):
        return self.repo.run("agent-resume.sh", *args, **kwargs)

    def test_a_main_manager_resume_sweeps_and_prints_it_last(self):
        path, _ = self.merged_worktree()
        self.repo.set_worktree_lines([(path, "done", "idle")])
        out = self.assertOk(self.resume())
        self.assertFalse(os.path.exists(path))
        lines = [l for l in self.lines(out) if l]
        self.assertEqual(lines[-1], "CLEANUP: removed 1, kept 0.")
        # swept before the table was read: the removed line is not a row
        self.assertNotIn(path + " | idle", out)

    def test_dry_run_removes_nothing(self):
        path, _ = self.merged_worktree()
        out = self.assertOk(self.resume("--dry-run"))
        self.assertTrue(os.path.isdir(path))
        self.assertIn("CLEANUP: would remove 1, kept 0.", self.lines(out))

    def test_already_swept_by_the_start(self):
        path, _ = self.merged_worktree()
        out = self.assertOk(self.resume(env={"AGENT_CLEANUP_DONE": "1"}))
        self.assertTrue(os.path.isdir(path))
        self.assertNotIn("CLEANUP:", out)

    def test_a_spawned_agent_does_not(self):
        path, _ = self.merged_worktree()
        self.assertOk(self.resume(env={"AGENT_ROLE": "task-manager"}))
        self.assertTrue(os.path.isdir(path))


# ---------------------------------------------------------------- wiring: todo done


class TestTodoDoneWiring(CleanupCase):
    def todo(self, *args, **kwargs):
        return self.repo.run("agent-file.sh", "todo", *args, **kwargs)

    def setUp(self):
        super().setUp()
        self.path, _ = self.merged_worktree()
        self.assertOk(self.todo("add", "done", "big", "the work", "30"))

    def test_the_last_task_closing_sweeps(self):
        out = self.assertOk(self.todo("done", "done"))
        self.assertFalse(os.path.exists(self.path))
        lines = self.lines(out)
        time_data = next(i for i, l in enumerate(lines)
                         if l.startswith("TIME DATA:"))
        clean = lines.index("CLEANUP: removed 1, kept 0.")
        self.assertLess(time_data, clean)

    def test_an_open_task_left_does_not(self):
        self.assertOk(self.todo("add", "next", "big", "more work", "30"))
        out = self.assertOk(self.todo("done", "done"))
        self.assertTrue(os.path.isdir(self.path))
        self.assertNotIn("CLEANUP:", out)

    def test_a_live_worktree_line_does_not(self):
        for status in ("working", "final"):
            with self.subTest(status=status):
                self.repo.set_worktree_lines([("/x/live", "x", status)])
                self.assertOk(self.todo("add", "done", "big", "w", "30"))
                out = self.assertOk(self.todo("done", "done"))
                self.assertTrue(os.path.isdir(self.path))
                self.assertNotIn("CLEANUP:", out)

    def test_an_idle_line_does_not_stop_it(self):
        self.repo.set_worktree_lines([(self.path, "done", "idle")])
        self.assertOk(self.todo("done", "done"))
        self.assertFalse(os.path.exists(self.path))

    def test_a_task_manager_closing_a_task_does_not(self):
        out = self.assertOk(self.todo("done", "done",
                                      env={"AGENT_ROLE": "task-manager"}))
        self.assertTrue(os.path.isdir(self.path))
        self.assertNotIn("CLEANUP:", out)

    def test_a_failed_sweep_never_fails_todo_done(self):
        self.repo.write_bin_script("agent-cleanup.sh",
                                   "#!/usr/bin/env bash\necho boom >&2\n"
                                   "exit 1\n")
        result = self.todo("done", "done")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("todo done: done", result.stdout)
        self.assertEqual(self.repo.read("agent_todo.txt").strip(), "")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------- the rules


def section(code, nxt):
    """PRINCIPLES.md from the line "<code>. ..." up to the line "<nxt>. ..."."""
    with open(os.path.join(ROOT, "PRINCIPLES.md")) as fh:
        text = fh.read()
    start = text.index("\n%s. " % code)
    end = text.index("\n%s. " % nxt, start)
    return text[start:end]


class TestTheRules(unittest.TestCase):
    """One terse English line per rule, where they fit: W8 and S4."""

    def test_w8_names_the_sweep_and_when_it_runs(self):
        w8 = section("W8", "W9")
        for words in ("agent-cleanup.sh --apply", "session start",
                      "last open task closes", "no loop"):
            self.assertIn(words, w8)

    def test_w8_says_who_never_runs_it(self):
        w8 = section("W8", "W9")
        self.assertIn("Main manager only", w8)
        self.assertIn("never run it", w8)

    def test_w8_says_what_is_safe_and_what_is_never_deleted(self):
        w8 = section("W8", "W9")
        for words in ("origin/main", "live agent", "uncommitted",
                      "unpushed", "never deleted", "one table",
                      "why kept"):
            self.assertIn(words, w8)

    def test_w8_says_own_repo_and_every_paired_machine(self):
        w8 = section("W8", "W9")
        self.assertIn("own repo only", w8.lower())
        self.assertIn("paired", w8)
        self.assertIn("unreachable", w8)

    def test_s4_names_stop_leftovers(self):
        self.assertIn("stop-leftovers", section("S4", "S5"))

    def test_s6_counts_busy_agents_only(self):
        s6 = section("S6", "S7")
        for words in ("working or permission", "done", "not counted", "main manager"):
            self.assertIn(words, s6)
        self.assertNotIn("Counts spawned agents only", s6)

    def test_s6_says_who_closes_a_finished_pane_and_when_never(self):
        s6 = section("S6", "S7")
        for words in ("closes it", "merged, dropped or closed",
                      "waiting on a merge, a question or a decision",
                      "another repo"):
            self.assertIn(words, s6)

    def test_w8_names_the_done_pane(self):
        w8 = section("W8", "W9")
        self.assertIn("done pane", w8)
        self.assertIn("kept row", w8)

    def test_dispatch_step_6_counts_the_same_way(self):
        with open(os.path.join(ROOT, "skills", "dispatch", "SKILL.md")) as fh:
            step6 = next(l for l in fh.read().splitlines() if l.startswith("6. "))
        self.assertIn("working or permission", step6)
        self.assertIn("done", step6)
        self.assertIn("max_agents", step6)

    def test_w14_names_the_owner_todo_marker(self):
        self.assertIn("`OWNER TODO:`", section("W14", "W15"))

    def test_one_line_per_rule(self):
        for code, nxt in (("W8", "W9"), ("S4", "S5"), ("S6", "S7"), ("W14", "W15")):
            for line in section(code, nxt).splitlines():
                if line.startswith("- "):
                    self.assertLessEqual(len(line), 200, line)

    def test_the_readme_tree_names_the_script(self):
        with open(os.path.join(ROOT, "README.md")) as fh:
            self.assertIn("bin/agent-cleanup.sh", fh.read())


# ---------------------------------------------------------------- the quiz


class TestTheQuiz(ScriptCase):
    """W8 changed, and the quiz covers W8: question 32, answer C."""

    script = "agent-start.sh"
    ANSWERS = ("1A 2D 3C 4B 5D 6D 7A 8C 9A 10D 11A 12C 13D 14C 15B 16C 17C "
               "18D 19B 20A 21D 22C 23B 24D 25A 26D 27A 28B 29B 30B 31B 32C 33B")

    def quiz(self):
        return self.assertOk(self.repo.run("agent-start.sh", "--quiz"))

    def test_question_32_is_the_sweep(self):
        out = self.quiz()
        q = out[out.index("Q32. "):]
        self.assertIn("last open task", q)
        options = [l.strip() for l in q.splitlines()[1:5]]
        self.assertEqual([o[:2] for o in options], ["A.", "B.", "C.", "D."])
        self.assertIn("agent-cleanup.sh", options[2])
        self.assertIn("table", options[2])

    def test_the_quiz_says_33(self):
        out = self.quiz()
        self.assertIn("=== QUIZ — answer all 33 before any work ===", out)
        self.assertIn('--answer "1A 2B 3C ... 33D"', out)

    def test_c_passes(self):
        out = self.assertOk(self.repo.run("agent-start.sh", "--answer",
                                          self.ANSWERS))
        self.assertIn("QUIZ RESULT: 33/33 PASS", out)

    def test_another_letter_fails_and_names_w8(self):
        for wrong in ("32A", "32B", "32D"):
            with self.subTest(wrong=wrong):
                result = self.repo.run("agent-start.sh", "--answer",
                                       self.ANSWERS.replace("32C", wrong))
                self.assertEqual(result.returncode, 1)
                self.assertIn("Q32(W8)", result.stdout)
