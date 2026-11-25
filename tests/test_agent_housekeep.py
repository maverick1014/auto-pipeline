"""Tests of bin/agent-housekeep.sh and agent_housekeep.py: the housekeep pass, its HOUSEKEEP block,
worktree, todo and idea rows, related repos, file rows.

requirements/clean-up.md. One class per feature. Older task contracts: git log -p of this file.
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
BIN = os.path.join(os.path.dirname(HERE), "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import agent_conf  # noqa: E402
import test_agent_cleanup as tc  # noqa: E402  (the module only: its tests stay in their own module)
from scripthelp import ROOT, ScriptCase, children_of  # noqa: E402

NOW = "2026-11-13 12:00"
REAL_SLEEP = shutil.which("sleep") or "/bin/sleep"

git = tc.git

FAKE_CLEANUP = r"""#!/usr/bin/env bash
printf '%s\t%s\t%s\n' "$*" "${CLAUDE_PID:-}" "${AGENT_ROLE:-}" >> "@LOG@"
[ -f "@OUT@" ] && cat "@OUT@"
exit 0
"""

FAKE_FILE = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "@LOG@"
exec "$(dirname "$0")/agent-file-real.sh" "$@"
"""

FAKE_HK = r"""#!/usr/bin/env bash
printf '%s\t%s\t%s\n' "$*" "${CLAUDE_PID:-}" "${AGENT_ROLE:-}" >> "@LOG@"
if [ -f "@LOG@.stamp" ]; then
  printf '%s %s\n' "$(date +%s)" "$(date '+%Y-%m-%d %H:%M')" > "@STAMP@"
fi
if [ -f "@LOG@.hold" ]; then
  echo $$ > "@LOG@.pid"
  exec python3 -c 'import time; time.sleep(30)'
fi
exit 0
"""


def epoch_of(text):
    return int(time.mktime(time.strptime(text, "%Y-%m-%d %H:%M")))


def read_root(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def principles_section(code):
    """The lines of one PRINCIPLES.md rule, e.g. "W8", heading included."""
    out = []
    inside = False
    for line in read_root("PRINCIPLES.md").splitlines():
        if re.match(r"^[A-Z]\d+\. ", line) or line.startswith("## "):
            inside = line.startswith(code + ". ")
            if inside:
                out.append(line)
            continue
        if inside:
            out.append(line)
    return out


# ================================================================ the pass


class HousekeepCase(tc.CleanupCase):
    """A project with a bare origin and Orca knowing the repo; the cleanup
    sweep is a fake that logs its call, so each test sees only housekeep."""

    script = "agent-housekeep.sh"

    def setUp(self):
        super().setUp()
        r = self.repo
        r.set_conf("runtime", "orca")
        self.cleanup_log = os.path.join(r.base, "cleanup_calls.log")
        self.cleanup_out = os.path.join(r.base, "cleanup_out.txt")
        open(self.cleanup_log, "w").close()
        r.write_bin_script("agent-cleanup.sh", FAKE_CLEANUP
                           .replace("@LOG@", self.cleanup_log)
                           .replace("@OUT@", self.cleanup_out))
        self.gone = os.path.join(self.wts, "gone-one")

    # ---- running

    # test-slim: the Python pass runs in this process (repo.run_py). The wrapper's own work
    # (usage, roles, roots from a worktree) keeps real starts: TestUsage, TestMainManagerOnly*,
    # TestBlockInStateFile, and every call with a folder or a role. The runtime kind is still
    # asked of the real agent-runtime.sh each time.
    IN_PROCESS = True

    def hk(self, *args, **kwargs):
        env = {"AGENT_FAKE_NOW": NOW}
        env.update(kwargs.pop("env", None) or {})
        if (self.IN_PROCESS and not kwargs and set(args) <= {"--apply"}
                and "AGENT_ROLE" not in env and "CLAUDE_PID" not in env):
            kind = self.repo.run("agent-runtime.sh", "kind", env=env).stdout.strip()
            argv = ["--root", self.repo.dir, "--plugin", self.repo.plugin,
                    "--gitdir", os.path.join(self.repo.dir, ".git"), "--kind", kind] + list(args)
            return self.repo.run_py("agent_housekeep", *argv, env=env)
        return self.repo.run("agent-housekeep.sh", *args, env=env, **kwargs)

    def apply(self, **kwargs):
        return self.assertOk(self.hk("--apply", **kwargs))

    def listing(self, **kwargs):
        return self.assertOk(self.hk(**kwargs))

    # ---- files

    def state(self):
        return self.repo.read("agent_state.txt") or ""

    def set_file(self, name, lines):
        write(self.repo.path(name), "".join(l + "\n" for l in lines))

    def file_lines(self, name):
        return [l for l in (self.repo.read(name) or "").splitlines() if l.strip()]

    @staticmethod
    def body_of(text):
        """The body lines of the HOUSEKEEP block, the two spaces cut off."""
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("=== HOUSEKEEP "):
                body = []
                for nxt in lines[i + 1:]:
                    if not nxt.startswith("  "):
                        break
                    body.append(nxt[2:])
                return body
        return []

    def body(self):
        return self.body_of(self.state())

    def todo(self, name, opened="2026-11-13 11:30", extra=""):
        return "%s | big | build %s | est 30m | opened %s | by main%s" % (
            name, name, opened, extra)

    def lock_me(self):
        write(self.repo.path(".git", "agent_main.lock"),
              "%d 2026-11-13 10:00 - -\n" % os.getpid())
        return {"CLAUDE_PID": str(os.getpid())}

    def cleanup_calls(self):
        with open(self.cleanup_log) as fh:
            return [l.rstrip("\n").split("\t") for l in fh if l.strip()]

    def paired(self, name="pc2", rows=(), ps_rows=()):
        self.repo.set_orca_answer(
            "envs.json", {"ok": True, "result": {"environments": [{"name": name}]}})
        self.repo.set_orca_answer(
            "list.json", {"ok": True, "result": {"worktrees": list(rows)}}, env=name)
        self.repo.set_orca_answer(
            "ps.json", {"ok": True, "result": {"worktrees": list(ps_rows)}}, env=name)
        self.repo.set_orca_answer(
            "terminals.json", {"ok": True, "result": {"terminals": []}}, env=name)


# ---------------------------------------------------------------- usage, role


from sharedrepo import REPO_BASE, shared_fixture  # noqa: E402


@shared_fixture(guard=REPO_BASE, remember_repo=True)   # one repo per class, each run once; the tests only read
class TestUsage(HousekeepCase):
    IN_PROCESS = False   # test-slim: real starts through agent-housekeep.sh
    def test_help(self):
        out = self.assertOk(self.hk("-h"))
        for word in ("--apply", "main manager only", "housekeep_interval_min",
                     "plain", "cloud"):
            with self.subTest(word=word):
                self.assertIn(word, out)

    def test_an_unknown_argument_is_refused(self):
        result = self.hk("--force")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.strip())

    def test_the_script_is_executable(self):
        self.assertTrue(os.access(os.path.join(ROOT, "bin", "agent-housekeep.sh"), os.X_OK))

    def test_the_logic_lives_in_python(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, "bin", "agent_housekeep.py")))


class _TestMainManagerOnlyFixture:
    def fixture(self):
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.set_file("agent_ideas.txt", ["same | 2026-11-10 10:00 | by main",
                                          "same | 2026-11-11 10:00 | by main"])
        self.before = {n: self.repo.read(n) for n in ("agent_worktree.txt", "agent_ideas.txt")}
        self.repo.clear_calls()

    def assertRefused(self, result):
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("REFUSED", result.stderr)
        self.assertIn("main manager only", result.stderr)
        for name, text in self.before.items():
            self.assertEqual(self.repo.read(name), text, name)
        self.assertNotIn("HOUSEKEEP", self.state())
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_housekeep.last")))
        self.assertEqual(self.repo.calls(), [])
        self.assertEqual(self.cleanup_calls(), [])


@shared_fixture(guard=REPO_BASE, remember_repo=True)
class TestMainManagerOnly(_TestMainManagerOnlyFixture, HousekeepCase):
    IN_PROCESS = False   # test-slim: real starts through agent-housekeep.sh
    """One fixture for the class: these tests only read (tests/sharedrepo.py)."""

    def setUp(self):
        super().setUp()
        self.fixture()

    def test_a_task_manager_is_refused(self):
        self.assertRefused(self.hk("--apply", env={"AGENT_ROLE": "task-manager"}))

    def test_a_worker_is_refused_even_in_list_mode(self):
        self.assertRefused(self.hk(env={"AGENT_ROLE": "worker"}))


class TestMainManagerOnlyWrites(_TestMainManagerOnlyFixture, HousekeepCase):
    IN_PROCESS = False   # test-slim: real starts through agent-housekeep.sh
    """The tests of TestMainManagerOnly that write: one repo each."""

    def setUp(self):
        super().setUp()
        self.fixture()

    def test_the_main_manager_runs(self):
        env = self.lock_me()
        self.apply(env=env)
        self.assertEqual(self.file_lines("agent_worktree.txt"), [])

    def test_no_lock_at_all_runs(self):
        self.apply()
        self.assertEqual(self.file_lines("agent_worktree.txt"), [])

    def test_a_human_direct_helper_is_refused(self):
        self.lock_me()   # writes the lock: one repo of its own, not the shared one
        self.assertRefused(self.hk("--apply", env={"CLAUDE_PID": "999999"}))


# ---------------------------------------------------------------- stamp, block, file


class TestStamp(HousekeepCase):
    def test_apply_writes_the_stamp_in_the_git_dir(self):
        self.apply()
        text = open(self.repo.path(".git", "agent_housekeep.last")).read().strip()
        self.assertEqual(text, "%d %s" % (epoch_of(NOW), NOW))

    def test_list_mode_writes_no_stamp(self):
        self.listing()
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_housekeep.last")))


class TestClean(HousekeepCase):
    def test_nothing_found_is_one_line(self):
        out = self.apply()
        self.assertIn("HOUSEKEEP %s: clean" % NOW, out)
        self.assertEqual([l for l in self.state().splitlines() if "HOUSEKEEP" in l],
                         ["HOUSEKEEP %s: clean" % NOW])
        self.assertNotIn("=== HOUSEKEEP", self.state())

    def test_plain_mode_runs_too_with_no_orca_call(self):
        self.repo.set_conf("runtime", "plain")
        self.repo.clear_calls()
        out = self.apply()
        self.assertIn("HOUSEKEEP %s: clean" % NOW, out)
        self.assertEqual(self.repo.calls(), [])


class TestBlockInStateFile(HousekeepCase):
    IN_PROCESS = False   # test-slim: real starts through agent-housekeep.sh
    def setUp(self):
        super().setUp()
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])

    def test_the_block_is_printed_and_written(self):
        out = self.apply()
        self.assertIn("=== HOUSEKEEP %s ===" % NOW, out)
        self.assertIn("=== HOUSEKEEP %s ===" % NOW, self.state())
        self.assertIn("removed: worktree line %s (folder gone, no live pane)" % self.gone,
                      self.body())

    def test_every_body_line_starts_with_two_spaces(self):
        self.apply()
        lines = self.state().splitlines()
        i = lines.index("=== HOUSEKEEP %s ===" % NOW)
        self.assertTrue(lines[i + 1].startswith("  "))

    def test_a_missing_state_file_is_made(self):
        self.assertIsNone(self.repo.read("agent_state.txt"))
        self.apply()
        self.assertTrue(self.state().startswith("=== HOUSEKEEP %s ===\n" % NOW))

    def test_appended_at_the_end_the_rest_kept_byte_for_byte(self):
        old = "=== BRIEF ===\nkeep me | as is\n\n=== REPORT ===\nPARKED: q | t | since x\n"
        write(self.repo.path("agent_state.txt"), old)
        self.apply()
        self.assertTrue(self.state().startswith(old))

    def test_an_old_block_is_replaced_in_place(self):
        before = "=== BRIEF ===\nline one\n"
        old_block = ("=== HOUSEKEEP 2026-11-13 08:00 ===\n"
                     "  removed: worktree line /x (folder gone, no live pane)\n"
                     "  flag: todo y: stale, no worktree line and no open wait for 999m\n")
        after = "PARKED: a question | t | since 2026-11-13 09:00\n=== REPORT ===\nend\n"
        write(self.repo.path("agent_state.txt"), before + old_block + after)
        self.apply()
        text = self.state()
        self.assertTrue(text.startswith(before + "=== HOUSEKEEP %s ===\n" % NOW))
        self.assertTrue(text.endswith(after))
        self.assertNotIn("08:00", text)
        self.assertNotIn("999m", text)
        self.assertEqual(text.count("HOUSEKEEP"), 1)

    def test_an_old_clean_line_is_replaced_in_place(self):
        write(self.repo.path("agent_state.txt"),
              "top\nHOUSEKEEP 2026-11-13 08:00: clean\nbottom\n")
        self.apply()
        text = self.state()
        self.assertTrue(text.startswith("top\n=== HOUSEKEEP %s ===\n" % NOW))
        self.assertTrue(text.endswith("\nbottom\n"))
        self.assertNotIn("08:00", text)

    def test_a_clean_run_replaces_an_old_block(self):
        write(self.repo.path("agent_state.txt"),
              "top\n=== HOUSEKEEP 2026-11-13 08:00 ===\n  note: old\nbottom\n")
        self.repo.set_worktree_lines([])
        self.apply()
        self.assertEqual(self.state(), "top\nHOUSEKEEP %s: clean\nbottom\n" % NOW)

    def test_two_runs_leave_one_block(self):
        self.apply()
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.apply()
        self.assertEqual(self.state().count("=== HOUSEKEEP"), 1)

    def test_written_by_tmp_and_mv(self):
        write(self.repo.path("agent_state.txt"), "top\n")
        first = os.stat(self.repo.path("agent_state.txt")).st_ino
        self.apply()
        self.assertNotEqual(os.stat(self.repo.path("agent_state.txt")).st_ino, first)
        left = [n for n in os.listdir(self.repo.dir)
                if n.startswith("agent_state.txt") and n != "agent_state.txt"]
        self.assertEqual(left, [])

    def test_list_mode_prints_and_writes_nothing(self):
        write(self.repo.path("agent_state.txt"), "top\n")
        before_wt = self.repo.read("agent_worktree.txt")
        out = self.listing()
        self.assertIn("would remove: worktree line %s (folder gone, no live pane)" % self.gone,
                      self.body_of(out))
        self.assertEqual(self.state(), "top\n")
        self.assertEqual(self.repo.read("agent_worktree.txt"), before_wt)

    def test_from_a_worktree_it_writes_the_main_repo_state_file(self):
        path, _branch = self.worktree("here", orca=False)
        self.assertOk(self.repo.run("agent-housekeep.sh", "--apply", cwd=path,
                                    env={"AGENT_FAKE_NOW": NOW}))
        self.assertIn("=== HOUSEKEEP %s ===" % NOW, self.state())
        self.assertFalse(os.path.exists(os.path.join(path, "agent_state.txt")))


# ---------------------------------------------------------------- a. worktree lines


class TestWorktreeLines(HousekeepCase):
    def test_a_gone_idle_line_is_removed(self):
        keep, _ = self.worktree("keep")
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle"), (keep, "keep", "idle")])
        self.apply()
        self.assertEqual([l.split(" | ")[0] for l in self.file_lines("agent_worktree.txt")], [keep])
        self.assertIn("removed: worktree line %s (folder gone, no live pane)" % self.gone, self.body())

    def test_a_deleted_folder_git_still_lists_counts_as_gone(self):
        path, _ = self.worktree("deleted")
        shutil.rmtree(path)
        self.repo.set_worktree_lines([(path, "deleted", "idle")])
        self.apply()
        self.assertEqual(self.file_lines("agent_worktree.txt"), [])

    def test_a_gone_working_line_is_flagged_never_removed(self):
        for status in ("working", "final"):
            with self.subTest(status=status):
                self.repo.set_worktree_lines([(self.gone, "gone-one", status)])
                self.apply()
                self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
                self.assertIn("flag: worktree line %s: folder gone, line says %s"
                              % (self.gone, status), self.body())

    def test_a_gone_human_direct_line_is_flagged_never_removed(self):
        self.repo.set_worktree_lines([(self.gone, "task manager, human-direct", "task: Fix It")])
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertIn("flag: worktree line %s: folder gone, line says human-direct" % self.gone,
                      self.body())

    def test_a_gone_line_with_a_live_pane_stays(self):
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.repo.set_panes([{"path": self.gone, "agents": ["done"]}])
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertFalse([l for l in self.body() if l.startswith("removed: worktree line")])

    def test_a_working_line_with_no_agent_pane_is_flagged(self):
        path, _ = self.worktree("busy")
        self.repo.set_worktree_lines([(path, "busy", "working")])
        self.repo.set_panes([])
        self.apply()
        self.assertIn("flag: worktree line %s: working, no live agent pane" % path, self.body())
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)

    def test_a_working_line_with_a_done_pane_is_fine(self):
        path, _ = self.worktree("idlepane")
        self.repo.set_worktree_lines([(path, "idlepane", "final")])
        self.repo.set_panes([{"path": path, "agents": ["done"]}])
        self.apply()
        self.assertFalse([l for l in self.body() if path in l])

    def test_a_present_idle_line_is_left_to_the_cleanup(self):
        path, _ = self.worktree("quiet")
        self.repo.set_worktree_lines([(path, "quiet", "idle")])
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertFalse([l for l in self.body() if path in l])

    def test_a_line_on_a_paired_machine_is_present(self):
        far = os.path.join(self.repo.base, "pc2-only", "far")
        self.paired(rows=[self.list_row(far, "feat/far", host="pc2")])
        self.repo.set_worktree_lines([(far, "far", "idle")])
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)

    def test_a_working_line_on_a_paired_machine_with_its_agent_is_fine(self):
        far = os.path.join(self.repo.base, "pc2-only", "far")
        self.paired(rows=[self.list_row(far, "feat/far", host="pc2")],
                    ps_rows=[{"path": far, "agents": [{"state": "working"}]}])
        self.repo.set_worktree_lines([(far, "far", "working")])
        self.apply()
        self.assertFalse([l for l in self.body() if far in l])

    def test_a_paired_machine_down_keeps_the_line_and_says_so(self):
        self.paired()
        self.repo.set_orca_env_state("pc2", "down")
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertIn("note: pc2 unreachable, not checked", self.body())

    def test_a_hanging_paired_machine_never_hangs_the_pass(self):
        self.paired()
        self.repo.set_orca_env_state("pc2", "hang")
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        started = time.time()
        self.apply(env={"AGENT_CLEANUP_TIMEOUT": "1"})
        self.assertLess(time.time() - started, 40)
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertIn("note: pc2 unreachable, not checked", self.body())

    def test_orca_down_changes_no_line(self):
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.repo.stub_orca_down()
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertTrue([l for l in self.body()
                         if l.startswith("note: ") and "orca not answering" in l], self.body())

    def test_plain_mode_removes_a_gone_line_with_no_orca_call(self):
        self.repo.set_conf("runtime", "plain")
        path, _ = self.worktree("busyplain")
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle"), (path, "busyplain", "working")])
        self.repo.clear_calls()
        self.apply()
        self.assertEqual([l.split(" | ")[0] for l in self.file_lines("agent_worktree.txt")], [path])
        self.assertEqual(self.repo.calls(), [])
        self.assertFalse([l for l in self.body() if "no live agent pane" in l])

    def test_it_goes_through_agent_file(self):
        log = os.path.join(self.repo.base, "file_calls.log")
        real = os.path.join(self.repo.plugin_bin, "agent-file.sh")
        shutil.copy2(real, os.path.join(self.repo.plugin_bin, "agent-file-real.sh"))
        self.repo.write_bin_script("agent-file.sh", FAKE_FILE.replace("@LOG@", log))
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.set_file("agent_ideas.txt", ["twice | 2026-11-10 10:00 | by main",
                                          "twice | 2026-11-11 10:00 | by main"])
        self.apply()
        calls = open(log).read().splitlines()
        self.assertIn("worktree rm %s" % self.gone, calls)
        self.assertIn("idea rm 2", calls)


# ---------------------------------------------------------------- b. todo lines


class TestTodoMerged(HousekeepCase):
    def test_a_merged_branch_of_that_name_is_flagged(self):
        branch = self.branch_only("alpha", merge=True)
        self.set_file("agent_todo.txt", [self.todo("alpha")])
        self.apply()
        self.assertIn("flag: todo alpha: merged into origin/main (branch %s)" % branch, self.body())

    def test_the_todo_file_is_never_changed(self):
        self.branch_only("alpha", merge=True)
        self.set_file("agent_todo.txt", [self.todo("alpha"), self.todo("old", opened="2026-11-12 08:00")])
        before = self.repo.read("agent_todo.txt")
        self.apply()
        self.assertEqual(self.repo.read("agent_todo.txt"), before)

    def test_an_unmerged_branch_is_not_flagged(self):
        self.branch_only("beta", merge=False)
        self.set_file("agent_todo.txt", [self.todo("beta")])
        self.apply()
        self.assertFalse([l for l in self.body() if "merged" in l])

    def test_a_new_branch_with_no_own_commit_is_not_flagged(self):
        git(self.repo.dir, "branch", "feat/epsilon", "main")
        git(self.repo.dir, "push", "-q", "origin", "feat/epsilon")
        self.set_file("agent_todo.txt", [self.todo("epsilon")])
        self.apply()
        self.assertFalse([l for l in self.body() if "merged" in l])

    def merge_commit(self, subject):
        r = self.repo
        git(r.dir, "checkout", "-q", "-b", "tmp/side")
        self.commit_in(r.dir, "side_%d.txt" % len(subject))
        git(r.dir, "checkout", "-q", "main")
        git(r.dir, "merge", "-q", "--no-ff", "-m", subject, "tmp/side")
        git(r.dir, "branch", "-D", "tmp/side")
        git(r.dir, "push", "-q", "origin", "main")
        return git(r.dir, "rev-parse", "HEAD")

    def test_a_merge_commit_of_that_name_is_flagged_when_the_branch_is_gone(self):
        sha = self.merge_commit("Merge gamma (W8)")
        self.set_file("agent_todo.txt", [self.todo("gamma")])
        self.apply()
        hits = [l for l in self.body() if l.startswith("flag: todo gamma: merged into origin/main (commit ")]
        self.assertEqual(len(hits), 1, self.body())
        m = re.match(r"flag: todo gamma: merged into origin/main \(commit ([0-9a-f]{7,}) Merge gamma \(W8\)\)$",
                     hits[0])
        self.assertIsNotNone(m, hits[0])
        self.assertTrue(sha.startswith(m.group(1)))

    def test_a_merge_commit_of_a_longer_name_is_not_flagged(self):
        self.merge_commit("Merge gammaray (W8)")
        self.set_file("agent_todo.txt", [self.todo("gamma")])
        self.apply()
        self.assertFalse([l for l in self.body() if "merged" in l])

    def test_the_branch_of_its_worktree_counts(self):
        r = self.repo
        path = os.path.join(self.wts, "deltawt")
        git(r.dir, "worktree", "add", "-q", "-b", "work/zzz", path, "main")
        self.commit_in(path, "d.txt")
        git(path, "push", "-q", "-u", "origin", "work/zzz")
        git(r.dir, "merge", "-q", "--no-ff", "-m", "Merge work/zzz", "work/zzz")
        git(r.dir, "push", "-q", "origin", "main")
        self.repo.set_worktree_lines([(path, "delta", "final")])
        self.set_file("agent_todo.txt", [self.todo("delta")])
        self.apply()
        self.assertIn("flag: todo delta: merged into origin/main (branch work/zzz)", self.body())

    def test_no_origin_means_no_merged_check(self):
        git(self.repo.dir, "remote", "remove", "origin")
        self.set_file("agent_todo.txt", [self.todo("alpha")])
        out = self.apply()
        self.assertIn("HOUSEKEEP %s: clean" % NOW, out)


class TestTodoStale(HousekeepCase):
    def stale_line(self, name):
        return [l for l in self.body() if l.startswith("flag: todo %s: stale" % name)]

    def test_three_hours_with_no_worktree_and_no_wait_is_stale(self):
        self.set_file("agent_todo.txt", [self.todo("s1", opened="2026-11-13 09:00")])
        self.apply()
        self.assertEqual(self.stale_line("s1"),
                         ["flag: todo s1: stale, no worktree line and no open wait for 180m"])

    def test_one_hour_is_not_stale(self):
        self.set_file("agent_todo.txt", [self.todo("s2", opened="2026-11-13 11:00")])
        self.apply()
        self.assertEqual(self.stale_line("s2"), [])

    def test_exactly_the_threshold_is_not_stale(self):
        self.set_file("agent_todo.txt", [self.todo("s3", opened="2026-11-13 10:00")])
        self.apply()
        self.assertEqual(self.stale_line("s3"), [])

    def test_an_open_wait_is_not_stale(self):
        self.set_file("agent_todo.txt", [self.todo(
            "s4", opened="2026-11-13 08:00", extra=" | waiting question since 2026-11-13 08:30")])
        self.apply()
        self.assertEqual(self.stale_line("s4"), [])

    def test_a_worktree_line_of_that_module_is_not_stale(self):
        path, _ = self.worktree("s5wt")
        self.repo.set_worktree_lines([(path, "s5", "working")])
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        self.set_file("agent_todo.txt", [self.todo("s5", opened="2026-11-13 08:00")])
        self.apply()
        self.assertEqual(self.stale_line("s5"), [])

    def test_a_worktree_folder_of_that_name_is_not_stale(self):
        path, _ = self.worktree("s6")
        self.repo.set_worktree_lines([(path, "something else", "working")])
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        self.set_file("agent_todo.txt", [self.todo("s6", opened="2026-11-13 08:00")])
        self.apply()
        self.assertEqual(self.stale_line("s6"), [])

    def test_the_path_of_its_on_field_is_not_stale(self):
        path, _ = self.worktree("s7wt")
        self.repo.set_worktree_lines([(path, "other", "working")])
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        self.set_file("agent_todo.txt", [self.todo(
            "s7", opened="2026-11-13 08:00", extra=" | on pc2 %s" % path)])
        self.apply()
        self.assertEqual(self.stale_line("s7"), [])

    def test_a_newer_stage_since_counts(self):
        self.set_file("agent_todo.txt", [self.todo(
            "s8", opened="2026-11-13 08:00", extra=" | stage tests since 2026-11-13 11:30")])
        self.apply()
        self.assertEqual(self.stale_line("s8"), [])

    def test_the_threshold_is_the_interval(self):
        self.repo.set_conf("housekeep_interval_min", "30")
        self.set_file("agent_todo.txt", [self.todo("s9", opened="2026-11-13 11:00")])
        self.apply()
        self.assertEqual(self.stale_line("s9"),
                         ["flag: todo s9: stale, no worktree line and no open wait for 60m"])

    def test_interval_off_still_uses_two_hours(self):
        self.repo.set_conf("housekeep_interval_min", "0")
        self.set_file("agent_todo.txt", [self.todo("s10", opened="2026-11-13 11:00"),
                                         self.todo("s11", opened="2026-11-13 09:30")])
        self.apply()
        self.assertEqual(self.stale_line("s10"), [])
        self.assertEqual(len(self.stale_line("s11")), 1)


# ---------------------------------------------------------------- c. ideas


class TestIdeaDuplicates(HousekeepCase):
    def test_later_copies_go_the_first_stays(self):
        self.set_file("agent_ideas.txt", [
            "add a todo est verb | 2026-11-10 10:00 | by main",
            "something else | 2026-11-10 11:00 | by main",
            "add a todo est verb | 2026-11-12 09:00 | by task-manager",
            "add a todo est verb | 2026-11-13 08:00 | by main",
        ])
        self.apply()
        self.assertEqual(self.file_lines("agent_ideas.txt"), [
            "add a todo est verb | 2026-11-10 10:00 | by main",
            "something else | 2026-11-10 11:00 | by main",
        ])
        body = self.body()
        self.assertIn("removed: idea 3, a duplicate of idea 1: add a todo est verb", body)
        self.assertIn("removed: idea 4, a duplicate of idea 1: add a todo est verb", body)
        self.assertLess(body.index("removed: idea 3, a duplicate of idea 1: add a todo est verb"),
                        body.index("removed: idea 4, a duplicate of idea 1: add a todo est verb"))

    def test_a_line_with_no_date_tail_still_compares_by_text(self):
        self.set_file("agent_ideas.txt", ["plain idea", "plain idea | 2026-11-12 09:00 | by main"])
        self.apply()
        self.assertEqual(self.file_lines("agent_ideas.txt"), ["plain idea"])

    def test_near_copies_stay(self):
        lines = ["Add a todo est verb | 2026-11-10 10:00 | by main",
                 "add a todo est verb | 2026-11-11 10:00 | by main",
                 "add a todo est verb soon | 2026-11-12 10:00 | by main"]
        self.set_file("agent_ideas.txt", lines)
        self.apply()
        self.assertEqual(self.file_lines("agent_ideas.txt"), lines)

    def test_list_mode_changes_nothing(self):
        self.set_file("agent_ideas.txt", ["x y | 2026-11-10 10:00 | by main",
                                          "x y | 2026-11-11 10:00 | by main"])
        before = self.repo.read("agent_ideas.txt")
        out = self.listing()
        self.assertIn("would remove: idea 2, a duplicate of idea 1: x y", self.body_of(out))
        self.assertEqual(self.repo.read("agent_ideas.txt"), before)

    def test_only_the_first_80_characters_are_shown(self):
        text = "a" * 80 + "TAILWORDS" + "b" * 30
        self.set_file("agent_ideas.txt", [text + " | 2026-11-10 10:00 | by main",
                                          text + " | 2026-11-11 10:00 | by main"])
        self.apply()
        self.assertIn("removed: idea 2, a duplicate of idea 1: " + "a" * 80, self.body())
        self.assertNotIn("TAILWORDS", self.state())


class TestIdeaSuspects(HousekeepCase):
    def suspects(self):
        return [l for l in self.body() if l.startswith("suspect: ")]

    def test_an_idea_naming_a_task_done_later(self):
        self.set_file("agent_completed.txt", [
            "2026-11-12 | todo-est | add todo est | data repo=project type=script"])
        idea = "teach todo-est to keep the reason | 2026-11-05 10:02 | by main"
        self.set_file("agent_ideas.txt", [idea])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: teach todo-est to keep the reason | names task todo-est, done 2026-11-12"])
        self.assertEqual(self.file_lines("agent_ideas.txt"), [idea])

    def test_the_same_day_does_not_count(self):
        # housekeep-suspects D: the task must be finished on a LATER day
        self.set_file("agent_completed.txt", ["2026-11-05 | five-fixes | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["more five-fixes work | 2026-11-05 10:02 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_the_next_day_counts(self):
        self.set_file("agent_completed.txt", ["2026-11-06 | five-fixes | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["more five-fixes work | 2026-11-05 23:50 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: more five-fixes work | names task five-fixes, done 2026-11-06"])

    def test_a_task_done_before_the_idea_is_not_a_suspect(self):
        self.set_file("agent_completed.txt", ["2026-11-01 | todo-est | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["more todo-est work | 2026-11-05 10:02 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_a_dropped_task_says_dropped(self):
        self.set_file("agent_completed.txt", [
            "2026-11-12 | old-thing | x | est 30m actual - | dropped: owner said no"])
        self.set_file("agent_ideas.txt", ["revive old-thing | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: revive old-thing | names task old-thing, dropped 2026-11-12"])

    def test_a_whole_word_only(self):
        self.set_file("agent_completed.txt", ["2026-11-12 | fix | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["prefix the names, a fixed thing | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_case_does_not_matter(self):
        self.set_file("agent_completed.txt", ["2026-11-12 | statusline-vertical | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["Statusline-Vertical follow up. | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(len(self.suspects()), 1)

    def test_a_missing_file_is_a_suspect(self):
        os.makedirs(self.repo.path("bin"), exist_ok=True)   # F1: the folder exists
        self.set_file("agent_ideas.txt", ["teach bin/agent-gone.sh to stop | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: teach bin/agent-gone.sh to stop | names bin/agent-gone.sh, no such file"])

    def test_files_that_exist_are_fine(self):
        r = self.repo
        write(r.path("docs", "notes.md"), "x\n")
        git(r.dir, "add", "docs/notes.md")
        git(r.dir, "commit", "-q", "-m", "notes")
        self.set_file("agent_ideas.txt", [
            "see seed.txt, docs/notes.md and notes.md; also agent_todo.txt. | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_urls_are_skipped(self):
        self.set_file("agent_ideas.txt", ["read https://example.com/x/readme.md first | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_two_reasons_on_one_line(self):
        os.makedirs(self.repo.path("bin"), exist_ok=True)
        self.set_file("agent_completed.txt", ["2026-11-12 | todo-est | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["todo-est in bin/nothere.py | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: todo-est in bin/nothere.py | names task todo-est, done 2026-11-12; "
            "names bin/nothere.py, no such file"])

    def test_numbers_are_after_this_runs_removals(self):
        self.set_file("agent_completed.txt", ["2026-11-12 | todo-est | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["dup | 2026-11-10 10:00 | by main",
                                          "dup | 2026-11-10 11:00 | by main",
                                          "more todo-est | 2026-11-10 12:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 2: more todo-est | names task todo-est, done 2026-11-12"])

    def test_list_mode_numbers_are_the_file_as_it_is(self):
        self.set_file("agent_completed.txt", ["2026-11-12 | todo-est | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["dup | 2026-11-10 10:00 | by main",
                                          "dup | 2026-11-10 11:00 | by main",
                                          "more todo-est | 2026-11-10 12:00 | by main"])
        out = self.listing()
        self.assertIn("suspect: idea 3: more todo-est | names task todo-est, done 2026-11-12",
                      self.body_of(out))


# ---------------------------------------------------------------- housekeep-suspects
# Fixture ideas copied from the real provenance shapes of agent_ideas.txt
# (2026-09-24 .. 2026-11-13). Every task below is done on 2026-11-12, every idea
# is from 2026-11-05: only the provenance rule (P) can keep them quiet.

LATER_TASKS = ("idea-city", "city-ux", "city-status", "city-rediscover", "city-relay",
               "idea-pipeline", "mode-and-floor", "five-fixes", "city-tier",
               "helper-task-title", "city-talk", "model-suffix", "todo-est",
               "city-polish", "close-case")

PROVENANCE_ONLY = [
    # P1: a "(...)" with a role word, at the end or in the middle
    "one shared helper would keep them in step (idea-city TM 2026-09-28)",
    "keep it on the server (city-ux TM 2026-09-28)",
    "show the idle word after a Stop (city-status TM, 2026-10-01)",
    "a session with no pid is not brought back at all (city-rediscover / city-status TMs, 2026-10-01)",
    "take the parent's pid (mode-and-floor bounce 1) when no claude process is above the run",
    "no test covers it (five-fixes S5 worker note, pc2)",
    "name it, like the USER CONF: ignored line (five-fixes S1, pc2)",
    "would keep the town readable. (from the city-tier TM on pc2)",
    "pop it there too (helper-task-title TM on pc2, 2026-10-29)",
    "a demo governor still walks to an empty hall (old demo behaviour, seen by the city-talk TM 2026-10-01)",
    "Add --model from agent_conf.py cli-model of main_manager (model-suffix TM, pc2)",
    "the words do fire it (Close-Case Task Manager 2026-09-28)",
    # P2: the last "(...)" ends the text, no role word in it
    "Pick a Node >= 22 from PATH or skip with a clear reason (seen merging idea-pipeline, 2026-09-28).",
    # P3: a From / Seen sentence
    "push over one WebSocket per machine instead of polling. From pc2 city-relay task manager 2026-09-25 14:26",
    "Pick a Node >= 22 or skip with a clear reason. Seen merging idea-pipeline 2026-09-28.",
    "stack or offset them. Seen in idea-city E2E 2026-09-28",
]


class SuspectCase(HousekeepCase):
    def suspects(self):
        return [l for l in self.body() if l.startswith("suspect: ")]

    def later_tasks(self):
        self.set_file("agent_completed.txt", [
            "2026-11-12 | %s | x | data repo=project type=script" % t for t in LATER_TASKS])

    def ideas(self, *texts, day="2026-11-05 10:02"):
        self.set_file("agent_ideas.txt", ["%s | %s | by main" % (t, day) for t in texts])


class TestIdeaProvenance(SuspectCase):
    def test_a_task_named_only_in_the_provenance_note_is_no_evidence(self):
        self.later_tasks()
        self.ideas(*PROVENANCE_ONLY)
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_a_name_outside_the_note_still_counts(self):
        self.later_tasks()
        self.ideas("teach idea-city to stop the chain (idea-city TM 2026-09-28)")
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: teach idea-city to stop the chain (idea-city TM 2026-09-28) | "
            "names task idea-city, done 2026-11-12"])

    def test_a_middle_parenthesis_without_a_role_word_counts(self):
        self.later_tasks()
        self.ideas("its first step (city-polish P1); an idle clip would read better")
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: its first step (city-polish P1); an idle clip would read better | "
            "names task city-polish, done 2026-11-12"])

    def test_a_lowercase_from_inside_a_sentence_counts(self):
        self.later_tasks()
        self.ideas("read the guess from todo-est first, then blend it")
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: read the guess from todo-est first, then blend it | "
            "names task todo-est, done 2026-11-12"])

    def test_the_sentence_after_a_seen_sentence_counts(self):
        self.later_tasks()
        self.ideas("Seen merging idea-pipeline 2026-09-28. Then todo-est should keep the reason")
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: Seen merging idea-pipeline 2026-09-28. Then todo-est should keep the reason | "
            "names task todo-est, done 2026-11-12"])

    def test_only_the_last_parenthesis_is_the_trailing_note(self):
        self.later_tasks()
        self.ideas("the labels are Chinese only (todo-est shows them) (main, 2026-10-29)")
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: the labels are Chinese only (todo-est shows them) (main, 2026-10-29) | "
            "names task todo-est, done 2026-11-12"])

    def test_a_note_task_finished_the_same_day_and_a_body_task_finished_later(self):
        self.set_file("agent_completed.txt", [
            "2026-11-05 | idea-city | x | data repo=project",
            "2026-11-12 | todo-est | x | data repo=project"])
        self.ideas("idea-city and todo-est share a helper (idea-city TM 2026-11-05)")
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: idea-city and todo-est share a helper (idea-city TM 2026-11-05) | "
            "names task todo-est, done 2026-11-12"])


class TestIdeaFileRule(SuspectCase):
    def test_bare_names_of_files_outside_the_repo_are_never_suspects(self):
        self.ideas("the territories in world.json and roster.json; installed_plugins.json "
                   "keeps old paths; scratchpad cdp.mjs worked; nothere.py and gone.sh too")
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_absolute_and_home_paths_are_never_suspects(self):
        self.ideas("read /nowhere/at/all/gone.json and ~/.claude/nowhere/gone.conf")
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_a_repo_path_under_a_listed_folder_that_exists(self):
        for folder in ("bin", "tests", "skills", "agents", "hooks", "requirements", "mock"):
            os.makedirs(self.repo.path(folder), exist_ok=True)
        self.ideas("bin/agent-gone.sh, tests/test_gone.py, skills/gone/SKILL.md, agents/gone.md, "
                   "hooks/gone.json, requirements/gone.md and mock/gone.html")
        self.apply()
        self.assertEqual(len(self.suspects()), 1, self.suspects())
        self.assertTrue(self.suspects()[0].endswith(
            " | names bin/agent-gone.sh, no such file; names tests/test_gone.py, no such file; "
            "names skills/gone/SKILL.md, no such file; names agents/gone.md, no such file; "
            "names hooks/gone.json, no such file; names requirements/gone.md, no such file; "
            "names mock/gone.html, no such file"), self.suspects()[0])

    def test_a_path_that_exists_under_a_listed_folder_is_fine(self):
        write(self.repo.path("bin", "agent-here.sh"), "x\n")
        self.ideas("teach bin/agent-here.sh to stop")
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_a_listed_folder_the_repo_does_not_have(self):
        self.assertFalse(os.path.exists(self.repo.path("mock")))
        self.ideas("the old mock/old-page.html had a hall")
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_a_folder_not_on_the_list(self):
        os.makedirs(self.repo.path("docs"), exist_ok=True)
        self.ideas("see docs/gone.md and scratchpad/gone.mjs")
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_a_leading_dot_slash_is_cut(self):
        os.makedirs(self.repo.path("bin"), exist_ok=True)
        self.ideas("run ./bin/agent-gone.sh first")
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: run ./bin/agent-gone.sh first | names bin/agent-gone.sh, no such file"])

    def test_a_missing_root_file_by_name_pattern(self):
        self.ideas("move it to agent_gone.txt and write GONE.md")
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: move it to agent_gone.txt and write GONE.md | "
            "names agent_gone.txt, no such file; names GONE.md, no such file"])

    def test_a_root_name_found_at_the_root_or_tracked_anywhere(self):
        r = self.repo
        write(r.path("skills", "x", "SKILL.md"), "x\n")
        git(r.dir, "add", "skills/x/SKILL.md")
        git(r.dir, "commit", "-q", "-m", "skill")
        write(r.path("agent_state.txt"), "x\n")   # git-ignored in real repos: at the root is enough
        self.ideas("SKILL.md, agent_state.txt and agent_ideas.txt stay")
        self.apply()
        self.assertEqual(self.suspects(), [])


class TestIdeaKept(SuspectCase):
    def test_a_kept_idea_is_never_a_suspect(self):
        os.makedirs(self.repo.path("bin"), exist_ok=True)
        self.set_file("agent_completed.txt", ["2026-11-12 | todo-est | x | data repo=project"])
        self.set_file("agent_ideas.txt", [
            "teach todo-est in bin/agent-gone.sh | 2026-11-05 10:02 | by main | kept 2026-11-06",
            "more todo-est | 2026-11-05 10:03 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 2: more todo-est | names task todo-est, done 2026-11-12"])

    def test_list_mode_skips_a_kept_idea_too(self):
        os.makedirs(self.repo.path("bin"), exist_ok=True)
        self.set_file("agent_completed.txt", ["2026-11-12 | todo-est | x | data repo=project"])
        self.set_file("agent_ideas.txt", [
            "more todo-est in bin/agent-gone.sh | 2026-11-05 10:02 | by main | kept 2026-11-06"])
        out = self.listing()
        self.assertEqual([l for l in self.body_of(out) if l.startswith("suspect: ")], [])

    def test_a_kept_line_with_no_date_tail(self):
        os.makedirs(self.repo.path("bin"), exist_ok=True)
        self.set_file("agent_ideas.txt", ["fix bin/agent-gone.sh | kept 2026-11-06"])
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_duplicates_ignore_the_kept_field(self):
        self.set_file("agent_ideas.txt", [
            "x y | 2026-11-10 10:00 | by main | kept 2026-11-12",
            "x y | 2026-11-11 10:00 | by main",
            "plain idea | kept 2026-11-12",
            "plain idea"])
        self.apply()
        self.assertEqual(self.file_lines("agent_ideas.txt"), [
            "x y | 2026-11-10 10:00 | by main | kept 2026-11-12",
            "plain idea | kept 2026-11-12"])
        body = self.body()
        self.assertIn("removed: idea 2, a duplicate of idea 1: x y", body)
        self.assertIn("removed: idea 4, a duplicate of idea 3: plain idea", body)

    def test_the_shown_text_never_has_the_field(self):
        # the first line stays, even when the later copy is the kept one
        self.set_file("agent_ideas.txt", [
            "same | 2026-11-10 10:00 | by main",
            "same | 2026-11-11 10:00 | by main | kept 2026-11-12"])
        self.apply()
        self.assertIn("removed: idea 2, a duplicate of idea 1: same", self.body())
        self.assertNotIn("kept 2026", "\n".join(self.body()))


# ---------------------------------------------------------------- d. related repos


class RelatedCase(HousekeepCase):
    def setUp(self):
        super().setUp()
        self.city = os.path.join(self.repo.base, "cityhome-default")
        os.makedirs(self.city, exist_ok=True)
        self.peer = os.path.realpath(self.repo.make_project("peer"))
        for name in ("agent_todo.txt", "agent_completed.txt", "agent_ideas.txt", "agent_worktree.txt"):
            write(os.path.join(self.peer, name), "")
        self.join(self.peer)

    def join(self, *paths):
        write(os.path.join(self.city, "world.json"),
              json.dumps({"territories": {p + "/.git": {} for p in paths}}))

    def peer_file(self, name, lines):
        write(os.path.join(self.peer, name), "".join(l + "\n" for l in lines))

    def related(self):
        return [l for l in self.body() if l.startswith("related: ")]


class TestRelated(RelatedCase):
    def test_done_on_the_other_side(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.peer_file("agent_completed.txt", ["2026-11-12 | shared | x | data repo=peer"])
        self.apply()
        self.assertEqual(self.related(), [
            "related: peer (%s): task shared not open there (done 2026-11-12)" % self.peer])

    def test_dropped_on_the_other_side(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.peer_file("agent_completed.txt", ["2026-11-12 | shared | x | est 30m actual - | dropped: no"])
        self.apply()
        self.assertEqual(self.related(), [
            "related: peer (%s): task shared not open there (dropped 2026-11-12)" % self.peer])

    def test_no_line_at_all_on_the_other_side(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.apply()
        self.assertEqual(self.related(), [
            "related: peer (%s): task shared not open there" % self.peer])

    def test_open_with_a_worktree_line_there_is_fine(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.peer_file("agent_todo.txt", ["shared | big | x | est 30m | opened 2026-11-13 11:00 | by project"])
        self.peer_file("agent_worktree.txt", ["/far/away/shared | shared | working | since 2026-11-13 11:00"])
        out = self.apply()
        self.assertEqual(self.related(), [])
        self.assertIn("HOUSEKEEP %s: clean" % NOW, out)

    def test_open_with_no_worktree_line_there(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.peer_file("agent_todo.txt", ["shared | big | x | est 30m | opened 2026-11-13 11:00 | by project"])
        self.apply()
        self.assertEqual(self.related(), [
            "related: peer (%s): task shared open there, no worktree line there" % self.peer])

    def test_the_called_side_reads_its_by_field(self):
        line = "shared | big | x | est 30m | opened 2026-11-13 11:30 | by peer"
        self.set_file("agent_todo.txt", [line])
        self.peer_file("agent_completed.txt", ["2026-11-12 | shared | x | data repo=peer"])
        self.apply()
        self.assertEqual(self.related(), [
            "related: peer (%s): task shared not open there (done 2026-11-12)" % self.peer])

    def test_by_main_is_not_a_repo(self):
        self.set_file("agent_todo.txt", [self.todo("solo")])
        out = self.apply()
        self.assertEqual(self.related(), [])
        self.assertIn("HOUSEKEEP %s: clean" % NOW, out)

    def test_an_unknown_cross_repo_is_one_line(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross nowhere")])
        self.apply()
        self.assertEqual(self.related(), ["related: nowhere: not found on this machine, skipped"])

    def test_a_territory_folder_that_is_gone_is_not_found(self):
        shutil.rmtree(self.peer)
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.apply()
        self.assertEqual(self.related(), ["related: peer: not found on this machine, skipped"])

    def test_a_repo_from_world_json_is_found_too(self):
        other = os.path.realpath(self.repo.make_project("worldpeer"))
        write(os.path.join(other, "agent_todo.txt"), "")
        write(os.path.join(other, "agent_completed.txt"), "2026-11-12 | shared | x | data repo=worldpeer\n")
        write(os.path.join(self.city, "world.json"),
              json.dumps({"territories": {other + "/.git": {}}}))
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross worldpeer")])
        self.apply()
        self.assertEqual(self.related(), [
            "related: worldpeer (%s): task shared not open there (done 2026-11-12)" % other])

    def test_this_repo_itself_is_skipped(self):
        me = os.path.basename(self.repo.dir)
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross %s" % me)])
        self.apply()
        self.assertEqual(self.related(), [])

    def test_the_other_repo_is_never_written(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.peer_file("agent_todo.txt", ["shared | big | x | est 30m | opened 2026-11-13 11:00 | by project"])
        self.peer_file("agent_worktree.txt", ["/gone/for/good | other | idle | since 2026-11-01 10:00"])
        self.peer_file("agent_ideas.txt", ["dup | 2026-11-10 10:00 | by main", "dup | 2026-11-11 10:00 | by main"])
        before = {}
        for name in sorted(os.listdir(self.peer)):
            with open(os.path.join(self.peer, name)) as fh:
                before[name] = fh.read()
        self.apply()
        after = {}
        for name in sorted(os.listdir(self.peer)):
            with open(os.path.join(self.peer, name)) as fh:
                after[name] = fh.read()
        self.assertEqual(after, before)


class TestFileVerbs(RelatedCase):
    script = "agent-file.sh"   # these need only agent-file.sh, not the pass

    def af(self, *args, **kwargs):
        return self.repo.run("agent-file.sh", *args, **kwargs)

    def test_todo_cross_adds_the_field(self):
        self.set_file("agent_todo.txt", [self.todo("shared")])
        out = self.assertOk(self.af("todo", "cross", "shared", "peer"))
        self.assertIn("todo cross: shared -> peer", out)
        self.assertEqual(self.file_lines("agent_todo.txt"), [self.todo("shared") + " | cross peer"])

    def test_todo_cross_again_replaces_it_in_place(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer | stage tests since 2026-11-13 11:40")])
        self.assertOk(self.af("todo", "cross", "shared", "other"))
        self.assertEqual(self.file_lines("agent_todo.txt"), [
            self.todo("shared", extra=" | cross other | stage tests since 2026-11-13 11:40")])

    def test_todo_cross_refusals(self):
        self.set_file("agent_todo.txt", [self.todo("shared")])
        before = self.repo.read("agent_todo.txt")
        for args in (("nosuch", "peer"), ("shared",), ("shared", "two words"),
                     ("shared", "a | b"), ("shared", "a\nb")):
            with self.subTest(args=args):
                result = self.af("todo", "cross", *args)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertTrue(result.stderr.strip())
                self.assertEqual(self.repo.read("agent_todo.txt"), before)

    def test_the_board_still_reads_a_cross_field(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        out = self.assertOk(self.af("board"))
        self.assertIn("shared", out)

    def test_repos_lists_this_repo_first_then_the_territories(self):
        out = self.assertOk(self.af("repos"))
        self.assertEqual(out.splitlines(), [os.path.realpath(self.repo.dir), self.peer])

    def test_repos_each_once(self):
        other = os.path.realpath(self.repo.make_project("worldpeer"))
        self.join(other, self.peer, self.repo.dir)
        out = self.assertOk(self.af("repos"))
        self.assertEqual(out.splitlines(), [os.path.realpath(self.repo.dir), other, self.peer])

    def test_repos_skips_a_missing_folder(self):
        self.join(self.peer, os.path.join(self.repo.base, "not-here"))
        out = self.assertOk(self.af("repos"))
        self.assertEqual(out.splitlines(), [os.path.realpath(self.repo.dir), self.peer])

    def test_repos_touches_no_file(self):
        for name in ("agent_todo.txt", "agent_ideas.txt"):
            os.remove(self.repo.path(name))
        self.assertOk(self.af("repos"))
        for name in ("agent_todo.txt", "agent_ideas.txt"):
            self.assertFalse(os.path.exists(self.repo.path(name)), name)

    def test_the_header_documents_both_verbs(self):
        head = read_root("bin", "agent-file.sh").split("\nset -eu", 1)[0]
        self.assertIn("todo cross", head)
        self.assertIn("agent-file.sh repos", head)


# ---------------------------------------------------------------- e. the cleanup sweep


class TestCleanupStep(HousekeepCase):
    def test_apply_runs_the_sweep_with_apply_and_short(self):
        self.apply()
        calls = self.cleanup_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(sorted(calls[0][0].split()), ["--apply", "--short"])

    def test_list_mode_runs_it_in_list_mode(self):
        self.listing()
        calls = self.cleanup_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0].split(), ["--short"])

    def test_it_runs_as_the_main_manager_too(self):
        env = self.lock_me()
        self.apply(env=env)
        self.assertEqual(self.cleanup_calls()[0][1], str(os.getpid()))

    def test_its_lines_go_into_the_block(self):
        write(self.cleanup_out, "CLEANUP: removed 2, kept 1. Table for the human: x\n"
                                "CLEANUP: pc2 unreachable, not checked\n")
        self.apply()
        body = self.body()
        self.assertIn("cleanup: removed 2, kept 1. Table for the human: x", body)
        self.assertIn("cleanup: pc2 unreachable, not checked", body)
        self.assertEqual(body[-2:], ["cleanup: removed 2, kept 1. Table for the human: x",
                                     "cleanup: pc2 unreachable, not checked"])


class TestCleanupReal(tc.CleanupCase):
    """The real sweep, from the pass, as the main manager."""

    script = "agent-housekeep.sh"

    def test_a_merged_worktree_goes_and_the_block_says_so(self):
        self.repo.set_conf("runtime", "orca")
        path, _branch = self.merged_worktree()
        write(self.repo.path(".git", "agent_main.lock"), "%d 2026-11-13 10:00 - -\n" % os.getpid())
        out = self.assertOk(self.repo.run("agent-housekeep.sh", "--apply",
                                          env={"AGENT_FAKE_NOW": NOW, "CLAUDE_PID": str(os.getpid())}))
        self.assertFalse(os.path.exists(path))
        self.assertIn("  cleanup: removed 1, kept 0.", out.splitlines())


# ================================================================ config


class TestConfKey(unittest.TestCase):
    """settings-configure: "Stuck: Tidy every (min)" in Configure (housekeep_interval_min)."""

    def test_the_setting(self):
        by = {x["key"]: x for x in agent_conf.SETTINGS}
        field = by["housekeep_interval_min"]
        self.assertEqual((field["title"], field["default"], field["min"], field["max"]),
                         ("Stuck: Tidy every (min)", 120, 0, 1440))
        self.assertIn("0 = off", field["description"])
        for good in ("0", "1", "120", "1440"):
            self.assertIsNone(agent_conf.validate_value("housekeep_interval_min", good), good)
        for bad in ("-1", "1441", "abc", "1.5", ""):
            self.assertTrue(agent_conf.validate_value("housekeep_interval_min", bad), bad)


class TestSettingsKey(ScriptCase):
    """The value comes from Configure; agent-settings.sh never writes it."""
    script = "agent-settings.sh"

    def test_get_and_refuse(self):
        self.repo.set_conf("housekeep_interval_min", 30)
        self.assertEqual(self.assertOk(self.repo.run("agent-settings.sh", "get", "housekeep_interval_min")),
                         "30 (from Configure)\n")
        self.assertEqual(self.repo.run("agent-settings.sh", "housekeep_interval_min", "0").returncode, 1)


# ================================================================ docs, release


class TestDocs(unittest.TestCase):
    def assertSectionHas(self, code, *words):
        text = "\n".join(principles_section(code))
        self.assertTrue(text, "no %s section" % code)
        for word in words:
            self.assertIn(word, text, "%s does not say %r" % (code, word))

    def test_r5_r6_r7_say_what_housekeep_does(self):
        for code in ("R5", "R6", "R7"):
            with self.subTest(code=code):
                lines = [l for l in principles_section(code) if "housekeep" in l.lower()]
                self.assertEqual(len(lines), 1, "%s needs one housekeep line" % code)

    def test_w8_runs_it_from_the_watch_loop(self):
        self.assertSectionHas("W8", "housekeep_interval_min", "agent-housekeep.sh", "agent-watch.sh --all")

    def test_w12_names_todo_cross(self):
        self.assertSectionHas("W12", "todo cross")

    def test_one_line_per_rule(self):
        # the same 200-character cap test_agent_cleanup.TestTheRules keeps on W8
        for code in ("R5", "R6", "R7", "W8", "W12"):
            for line in principles_section(code):
                if line.startswith("- ") and ("housekeep" in line.lower() or "todo cross" in line):
                    self.assertLessEqual(len(line), 200, line)

    def test_the_main_manager_removes_or_keeps_each_suspect(self):
        # housekeep-suspects: one W8 line, <= 200 chars
        lines = [l for l in principles_section("W8")
                 if l.startswith("- ") and "idea rm" in l and "idea keep" in l]
        self.assertEqual(len(lines), 1, "W8: one line names idea rm and idea keep")
        line = lines[0]
        for word in ("HOUSEKEEP", "suspect", "owner decision", "still wanted"):
            self.assertIn(word, line)
        self.assertLessEqual(len(line), 200, line)

    def test_release_housekeep_suspects(self):
        ver = json.loads(read_root(".claude-plugin", "plugin.json"))["version"]
        self.assertGreaterEqual(tuple(int(x) for x in ver.split(".")), (0, 34, 1))

    def test_readme_lists_the_script(self):
        self.assertIn("bin/agent-housekeep.sh", read_root("PRINCIPLES.md"))


ROWS_NOW = "2026-11-24 12:00"


DAYS14 = 14 * 1440


IDEAS = [
    "city-ux: make the rail wider | 2026-11-01 10:00 | by main",
    "add dark mode | 2026-11-01 10:00 | by main",
    "city-ux: fix colors | 2026-11-01 10:00 | by main | kept 2026-11-05",
    "add dark mode | 2026-11-02 11:00 | by main",
    "see bin/gone-tool.sh for it | 2026-11-20 10:00 | by main",
]


def run_git(path, *args):
    res = subprocess.run(["git", "-C", path] + list(args),
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError("git %s: %s" % (" ".join(args), res.stderr))
    return res.stdout.strip()


class RowsCase(ScriptCase):

    def setUp(self):
        super().setUp()
        r = self.repo
        self.origin = os.path.join(r.base, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", self.origin],
                       check=True, capture_output=True)
        os.makedirs(os.path.join(r.dir, "bin"), exist_ok=True)
        with open(os.path.join(r.dir, "bin", "tool.sh"), "w") as fh:
            fh.write("true\n")
        run_git(r.dir, "add", "-A")
        run_git(r.dir, "commit", "-q", "-m", "bin")
        run_git(r.dir, "branch", "-M", "main")
        run_git(r.dir, "remote", "add", "origin", self.origin)
        run_git(r.dir, "push", "-q", "-u", "origin", "main")
        old = os.environ.get("AGENT_FAKE_NOW")
        os.environ["AGENT_FAKE_NOW"] = ROWS_NOW
        self.addCleanup(self.restore_now, old)
        import agent_housekeep
        self.hk = agent_housekeep

    @staticmethod
    def restore_now(old):
        if old is None:
            os.environ.pop("AGENT_FAKE_NOW", None)
        else:
            os.environ["AGENT_FAKE_NOW"] = old

    def set_file(self, name, lines):
        with open(os.path.join(self.repo.dir, name), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def rows(self, kind="plain", stale=DAYS14):
        r = self.repo
        return self.hk.file_rows(r.dir, r.plugin, os.path.join(r.dir, ".git"),
                                 kind, stale)

    def merged_task(self, name, keep_branch):
        d = self.repo.dir
        branch = "feat/" + name
        run_git(d, "checkout", "-q", "-b", branch)
        with open(os.path.join(d, name + ".txt"), "w") as fh:
            fh.write(name + "\n")
        run_git(d, "add", "-A")
        run_git(d, "commit", "-q", "-m", name)
        run_git(d, "push", "-q", "origin", branch)
        run_git(d, "checkout", "-q", "main")
        run_git(d, "merge", "-q", "--no-ff", "-m", "Merge " + name, branch)
        run_git(d, "push", "-q", "origin", "main")
        sha = run_git(d, "rev-parse", "--short=7", "HEAD")
        if not keep_branch:
            run_git(d, "branch", "-q", "-D", branch)
            run_git(d, "push", "-q", "origin", "--delete", branch)
        return sha


class TestFileRows(RowsCase):

    def test_ideas(self):
        self.set_file("agent_ideas.txt", IDEAS)
        self.set_file("agent_completed.txt", [
            "2026-11-10 | city-ux | rail | est 30m actual 40m"])
        ideas = self.rows()["ideas"]
        self.assertEqual([i["n"] for i in ideas], [1, 4, 5])
        self.assertEqual(ideas[0]["line"], IDEAS[0])
        self.assertEqual(ideas[0]["why"], "names task city-ux, done 2026-11-10")
        self.assertEqual(ideas[1]["line"], IDEAS[3])
        self.assertEqual(ideas[1]["why"], "a duplicate of idea 2")
        self.assertEqual(ideas[2]["why"], "names bin/gone-tool.sh, no such file")

    def test_todos_merged_and_stale(self):
        self.merged_task("old", keep_branch=True)
        sha = self.merged_task("older", keep_branch=False)
        lines = [
            "old | big | x | est 30m | opened 2026-11-20 08:00 | by main",
            "older | big | x | est 30m | opened 2026-11-01 08:00 | by main",
            "quiet | big | x | est 30m | opened 2026-11-01 08:00 | by main",
            "young | big | x | est 30m | opened 2026-11-20 08:00 | by main",
            "waits | big | x | est 30m | opened 2026-11-01 08:00 | by main | "
            "waiting question since 2026-11-01 09:00",
        ]
        self.set_file("agent_todo.txt", lines)
        todos = self.rows()["todos"]
        self.assertEqual([t["name"] for t in todos], ["old", "older", "quiet"])
        old, older, quiet = todos
        self.assertEqual(old["kind"], "merged")
        self.assertEqual(old["why"], "merged into origin/main (branch feat/old)")
        self.assertIsNone(old["sha"])
        self.assertEqual(old["line"], lines[0])
        self.assertEqual(older["kind"], "merged")   # merged wins over stale
        self.assertEqual(older["sha"], sha)
        self.assertEqual(older["why"],
                         "merged into origin/main (commit %s Merge older)" % sha)
        self.assertEqual(quiet["kind"], "stale")
        self.assertEqual(quiet["days"], 23)
        self.assertEqual(quiet["why"],
                         "stale: no worktree line and no open wait for 23d")
        self.assertEqual(quiet["line"], lines[2])

    def test_stale_limit_is_the_argument(self):
        self.set_file("agent_todo.txt", [
            "quiet | big | x | est 30m | opened 2026-11-01 08:00 | by main"])
        self.assertEqual(self.rows(stale=30 * 1440)["todos"], [])
        self.assertEqual(len(self.rows(stale=DAYS14)["todos"]), 1)

    def test_worktree_lines(self):
        live = os.path.join(self.repo.base, "wt-live")
        run_git(self.repo.dir, "worktree", "add", "-q", "-b", "feat/live", live, "main")
        g1 = os.path.join(self.repo.base, "gone-a")
        g2 = os.path.join(self.repo.base, "gone-b")
        g3 = os.path.join(self.repo.base, "gone-c")
        lines = ["%s | gone-a | working | since 2026-11-20 10:00" % g1,
                 "%s | gone-b | idle | since 2026-11-20 10:00" % g2,
                 "%s | live | working | since 2026-11-20 10:00" % live,
                 "%s | gone-c (human-direct) | human-direct | since 2026-11-20 10:00" % g3]
        self.set_file("agent_worktree.txt", lines)
        wts = self.rows()["worktrees"]
        self.assertEqual([w["path"] for w in wts], [g1, g2, g3])
        self.assertEqual(wts[0]["why"], "folder gone, no live pane (line says working)")
        self.assertEqual(wts[1]["why"], "folder gone, no live pane")
        self.assertEqual(wts[2]["why"], "folder gone, no live pane (line says human-direct)")
        self.assertEqual(wts[0]["line"], lines[0])
        self.assertEqual(wts[1]["status"], "idle")

    def test_orca_not_answering_note_and_no_worktree_rows(self):
        self.repo.stub_orca_down()
        g = os.path.join(self.repo.base, "gone")
        self.set_file("agent_worktree.txt", ["%s | gone | idle | since 2026-11-20 10:00" % g])
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = self.repo._path()
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        rows = self.rows(kind="orca")
        self.assertEqual(rows["worktrees"], [])
        self.assertIn("orca not answering: worktree lines not checked", rows["notes"])

    def test_read_only(self):
        self.merged_task("old", keep_branch=True)
        self.set_file("agent_ideas.txt", IDEAS)
        self.set_file("agent_todo.txt", [
            "old | big | x | est 30m | opened 2026-11-20 08:00 | by main"])
        g = os.path.join(self.repo.base, "gone")
        self.set_file("agent_worktree.txt", ["%s | gone | idle | since 2026-11-20 10:00" % g])
        names = ("agent_ideas.txt", "agent_todo.txt", "agent_worktree.txt",
                 "agent_completed.txt")
        before = {}
        for n in names:
            with open(os.path.join(self.repo.dir, n)) as fh:
                before[n] = fh.read()
        self.rows()
        for n in names:
            with open(os.path.join(self.repo.dir, n)) as fh:
                self.assertEqual(fh.read(), before[n], n)
        self.assertFalse(os.path.exists(os.path.join(self.repo.dir, "agent_state.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.repo.dir, ".git",
                                                     "agent_housekeep.last")))
        self.assertTrue(run_git(self.repo.dir, "branch", "--list", "feat/old"))


class TestFileRowsBounce1(RowsCase):
    """Reviewer findings 2, 3, 6 and the E2E finding (2026-11-24)."""

    def test_line_numbers_count_newlines_only(self):
        with open(os.path.join(self.repo.dir, "agent_ideas.txt"), "w", newline="") as fh:
            fh.write("progress 10%\r100% done | 2026-11-01 10:00 | by main\n"
                     "add dark mode | 2026-11-01 10:00 | by main\n"
                     "add dark mode | 2026-11-02 11:00 | by main\n")
        ideas = self.rows()["ideas"]
        self.assertEqual([(i["n"], i["why"]) for i in ideas], [(3, "a duplicate of idea 2")])

    def test_a_kept_duplicate_is_no_row(self):
        self.set_file("agent_ideas.txt", [
            "add dark mode | 2026-11-01 10:00 | by main",
            "add dark mode | 2026-11-02 11:00 | by main | kept 2026-11-05"])
        self.assertEqual(self.rows()["ideas"], [])

    def test_an_existing_folder_is_no_worktree_row(self):
        folder = os.path.join(self.repo.base, "not-a-worktree")
        os.mkdir(folder)
        self.set_file("agent_worktree.txt", [
            "%s | live-task | working | since 2026-11-20 10:00" % folder])
        self.assertEqual(self.rows()["worktrees"], [])

    def test_per_machine_agent_files_are_never_gone(self):
        self.assertFalse(os.path.exists(os.path.join(self.repo.dir, "agent_state.txt")))
        self.set_file("agent_ideas.txt", [
            "grep the worktree agent_state.txt for DONE | 2026-11-20 10:00 | by main",
            "agent_monitor.txt keeps old lines | 2026-11-20 10:00 | by main",
            "see agent_gone.txt for it | 2026-11-20 10:00 | by main"])
        ideas = self.rows()["ideas"]
        self.assertEqual([(i["n"], i["why"]) for i in ideas],
                         [(3, "names agent_gone.txt, no such file")])


class TestCrlfBounce2(RowsCase):
    """Reviewer re-check N1: a CRLF ideas file reads as before bounce 1."""

    CRLF = ("add dark mode | 2026-11-01 10:00 | by main\r\n"
            "add dark mode | 2026-11-02 11:00 | by main\r\n"
            "city-ux: wider rail | 2026-11-01 10:00 | by main\r\n")

    def plant(self):
        with open(os.path.join(self.repo.dir, "agent_ideas.txt"), "w", newline="") as fh:
            fh.write(self.CRLF)
        self.set_file("agent_completed.txt", [
            "2026-11-10 | city-ux | rail | est 30m actual 40m"])

    def test_rows_of_a_crlf_file_keep_the_raw_line(self):
        self.plant()
        ideas = self.rows()["ideas"]
        self.assertEqual([(i["n"], i["why"]) for i in ideas],
                         [(2, "a duplicate of idea 1"),
                          (3, "names task city-ux, done 2026-11-10")])
        self.assertEqual(ideas[0]["line"], "add dark mode | 2026-11-02 11:00 | by main\r")

    def test_the_housekeep_block_of_a_crlf_file(self):
        self.plant()
        res = self.repo.run("agent-housekeep.sh", env={"AGENT_FAKE_NOW": ROWS_NOW,
                                                       "AGENT_RUNTIME": "plain"})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("would remove: idea 2, a duplicate of idea 1", res.stdout)
        self.assertIn("suspect: idea 3:", res.stdout)


if __name__ == "__main__":
    unittest.main()
