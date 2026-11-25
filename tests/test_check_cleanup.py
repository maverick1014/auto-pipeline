"""Failing tests for check-blocks slice 8: cleanup (requirements/check-blocks.md section 10,
TELL 101f0c46; owner 2026-11-25: fix it by the best design "that will not affect user workflow").
Written by the task manager before any code. Module -> feature:

    the guard (bin/agent_guard.py)     (d) a pane closed through agent-runtime.sh close drops its LAUNCH record
    the sweep (bin/agent_cleanup.py)   (d) prunes LAUNCH records whose pid is dead or whose pane is gone
                                       (e) never lists main or the release branch; a live LAUNCH record = live agent
                                       (c) closes a pane that never got a prompt and is idle over unused_pane_min
                                       (g) the list says what --apply would do, --apply does it
    the rule text                      (a) (b) (f) merge deputy, merge skill, W8

Sweep output lines (list mode / --apply), one per item:
    would prune LAUNCH <key> (pid dead|pane gone)       pruned LAUNCH <key> (pid dead|pane gone)
    would close pane <handle> (<title>) in <path>: never got a prompt, idle <n>m
    closed pane <handle> (<title>) in <path>: never got a prompt, idle <n>m

Never got a prompt: a shell pane (no agentIdentity) whose preview holds only shell prompt lines
(each non-blank line ends with %, $ or #, or starts with "Last login:"); a Claude pane no LAUNCH
record names, whose title has no "Helper". Only in a task worktree (never the main folder), never
the main manager's own pane (its handle in agent_main.lock).

Run: python3 -m unittest tests.test_check_cleanup
"""

import json
import os
import re
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_agent_cleanup as tc  # noqa: E402
import test_board_trust as bt  # noqa: E402
from scripthelp import BIN, ROOT  # noqa: E402

LIVE = os.getpid()


def dead_pid():
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def ago_ms(minutes):
    return int(time.time() * 1000) - minutes * 60000


# ---------------------------------------------------------------- the guard


class TestGuardDropsAClosedPane(bt.GuardCase):

    def test_agent_runtime_close_drops_the_record(self):
        self.put_todo("board-waiting")
        self.put_launch("LAUNCH toolu_x: tm-pane | task board-waiting | board-waiting Task Manager | since "
                        "2026-11-20 16:40 | pid %d | by main | pane term_a | worktree /w/board-waiting" % LIVE)
        self.put_launch("LAUNCH toolu_y: tm-pane | task other | other Task Manager | since "
                        "2026-11-20 16:40 | pid %d | by main | pane term_b | worktree /w/other" % LIVE)
        for cmd in ('"/p/bin/agent-runtime.sh" close term_a', "/p/bin/agent-runtime.sh close term_a"):
            with self.subTest(cmd=cmd):
                r = self.pre_bash(cmd)
                self.assertAllowed(r)
                self.assertAllowed(self.post_bash(cmd, r.tid, ""))
                self.assertEqual([l.split(":")[0] for l in self.launches()], ["LAUNCH toolu_y"])
                self.put_launch("LAUNCH toolu_x: tm-pane | task board-waiting | board-waiting Task Manager | "
                                "since 2026-11-20 16:40 | pid %d | by main | pane term_a | worktree "
                                "/w/board-waiting" % LIVE)


# ---------------------------------------------------------------- the sweep


class SweepCase(tc.CleanupCase):

    def state(self, folder, *lines):
        with open(os.path.join(folder, "agent_state.txt"), "a") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def state_lines(self, folder):
        path = os.path.join(folder, "agent_state.txt")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return fh.read().splitlines()

    def launch(self, key, kind="tm-pane", task="t", pid=LIVE, pane=None, agent=None, worktree=None):
        line = "LAUNCH %s: %s | task %s | %s | since 2026-11-25 10:00 | pid %d | by main" % (
            key, kind, task, "%s Task Manager" % task if kind == "tm-pane" else "%s Worker 1: x" % task, pid)
        if agent:
            line += " | agent " + agent
        if pane:
            line += " | pane " + pane
        if worktree:
            line += " | worktree " + worktree
        return line


class TestLaunchPrune(SweepCase):

    def setUp(self):
        super().setUp()
        self.dead = dead_pid()
        self.state(self.repo.dir, "NOTE keep me",
                   self.launch("k_dead", kind="worker 1", pid=self.dead, agent="a1"),
                   self.launch("k_gone", pane="term_gone"),
                   self.launch("k_live", task="u", pane="term_live"),
                   self.launch("k_paneold", task="v", pid=self.dead, pane="term_v"))
        self.terminals = [self.term("term_live", self.repo.dir), self.term("term_v", self.repo.dir)]
        self.save_orca()

    def keys(self):
        return [l.split(":")[0][len("LAUNCH "):] for l in self.state_lines(self.repo.dir) if l.startswith("LAUNCH ")]

    def test_the_list_says_what_would_go_and_changes_nothing(self):
        before = self.state_lines(self.repo.dir)
        out = self.ok()
        lines = self.lines(out)
        self.assertIn("would prune LAUNCH k_dead (pid dead)", lines)
        self.assertIn("would prune LAUNCH k_gone (pane gone)", lines)
        self.assertFalse([l for l in lines if "k_live" in l or "k_paneold" in l], out)
        self.assertEqual(self.state_lines(self.repo.dir), before)

    def test_apply_prunes(self):
        out = self.ok("--apply")
        lines = self.lines(out)
        self.assertIn("pruned LAUNCH k_dead (pid dead)", lines)
        self.assertIn("pruned LAUNCH k_gone (pane gone)", lines)
        self.assertEqual(self.keys(), ["k_live", "k_paneold"])
        self.assertIn("NOTE keep me", self.state_lines(self.repo.dir))

    def test_a_worktrees_own_records_too(self):
        path, _ = self.worktree("wip")
        self.state(path, self.launch("k_wdead", kind="worker 1", pid=dead_pid(), agent="a2"))
        self.ok("--apply")
        self.assertEqual([l for l in self.state_lines(path) if l.startswith("LAUNCH ")], [])

    def test_plain_mode_never_says_pane_gone(self):
        self.repo.set_conf("runtime", "plain")
        out = self.ok("--apply")
        self.assertIn("pruned LAUNCH k_dead (pid dead)", self.lines(out))
        self.assertNotIn("k_gone", out)


class TestNeverMainOrRelease(SweepCase):

    def test_release_and_main_are_never_rows(self):
        r = self.repo.dir
        tc.git(r, "checkout", "-q", "--orphan", "release")
        tc.git(r, "rm", "-rq", "--cached", ".")
        with open(os.path.join(r, "ship.txt"), "w") as fh:
            fh.write("ship\n")
        tc.git(r, "add", "ship.txt")
        tc.git(r, "commit", "-q", "-m", "release 0.1.0")
        tc.git(r, "push", "-q", "origin", "release")
        tc.git(r, "checkout", "-q", "-f", "main")
        out = self.ok("--apply")
        for row in self.rows(out):
            self.assertNotIn("release", row[0], row)
            self.assertNotIn("branch main", row[0], row)
        self.assertTrue(self.has_local("release"))
        self.assertTrue(self.has_origin("release"))


class TestLiveLaunchIsLiveAgent(tc.KeptCase, SweepCase):

    def test_a_live_record_in_the_worktree(self):
        path, branch = self.merged_worktree(dirty=True)
        self.state(path, self.launch("k_w", kind="worker 1", task="done", agent="a1"))
        out = self.assertKept(path, branch, "live agent")
        row = self.row_for(out, "worktree " + path)
        self.assertTrue(row[2].startswith("live agent"), row)
        self.assertEqual(row[3], "wait for the agent to stop, then run the sweep again")

    def test_a_live_record_in_the_main_state_naming_the_worktree(self):
        path, branch = self.merged_worktree(dirty=True)
        self.state(self.repo.dir, self.launch("k_m", task="done", pane="term_x", worktree=path))
        self.terminals = [self.term("term_x", path)]
        self.save_orca()
        row = self.row_for(self.assertKept(path, branch, "live agent"), "worktree " + path)
        self.assertTrue(row[2].startswith("live agent"), row)

    def test_a_dead_record_is_no_live_agent(self):
        path, branch = self.merged_worktree(dirty=True)
        self.state(path, self.launch("k_w", kind="worker 1", task="done", pid=dead_pid(), agent="a1"))
        row = self.row_for(self.assertKept(path, branch, "uncommitted changes"), "worktree " + path)
        self.assertNotIn("live agent", row[2])


class TestUnusedPanes(SweepCase):

    def setUp(self):
        super().setUp()
        self.wip, _ = self.worktree("wip")          # unmerged: the folder stays, its panes are judged

    def pane(self, handle, path, minutes, preview="maverick@host wip %", agent=None, title=None):
        row = self.term(handle, path, agent=agent)
        row.update({"title": title or ("Terminal 1" if not agent else "✳ wip Task Manager"),
                    "lastOutputAt": ago_ms(minutes), "preview": preview})
        return row

    def run_with(self, terminals, *args, env=None):
        self.terminals = terminals
        self.save_orca()
        self.repo.clear_calls()
        return self.ok(*args, env=env)

    def closed(self):
        return [c[c.index("--terminal") + 1] for c in self.orca_calls(["terminal", "close"]) if "--terminal" in c]

    def test_an_unused_shell_idle_40m_is_closed_and_named(self):
        out = self.run_with([self.pane("t_sh", self.wip, 40)], "--apply")
        self.assertEqual(self.closed(), ["t_sh"])
        self.assertIn("closed pane t_sh (Terminal 1) in %s: never got a prompt, idle 40m" % self.wip,
                      self.lines(out))

    def test_the_list_only_says_it(self):
        out = self.run_with([self.pane("t_sh", self.wip, 40)])
        self.assertEqual(self.closed(), [])
        self.assertIn("would close pane t_sh (Terminal 1) in %s: never got a prompt, idle 40m" % self.wip,
                      self.lines(out))

    def test_an_idle_claude_pane_with_no_record_is_listed_not_closed(self):
        # core review defect 12: no record is no proof it never got a prompt (a default task manager pane,
        # a human's own session): the sweep never closes a Claude pane, it lists it
        out = self.run_with([self.pane("t_c", self.wip, 45, preview="", agent="claude")], "--apply")
        self.assertEqual(self.closed(), [])
        row = self.row_for(out, "pane t_c")
        self.assertEqual(row[1], self.wip)
        self.assertEqual(row[2], "idle agent pane, no task record, idle 45m")
        self.assertEqual(row[3], "close it by hand if nobody uses it")

    def test_a_truncated_terminal_list_closes_and_prunes_nothing(self):
        # core review defect 13: a truncated list is no proof a pane is gone or unused
        self.state(self.repo.dir, self.launch("k_gone", pane="term_gone"))
        self.terminals = [self.pane("t_sh", self.wip, 40)]
        self.repo.set_orca_answer("terminals.json", {"ok": True, "result": {
            "terminals": self.terminals, "truncated": True, "totalCount": 9}})
        self.repo.clear_calls()
        out = self.ok("--apply")
        self.assertEqual(self.closed(), [])
        self.assertNotIn("k_gone", out)
        self.assertIn("k_gone", "\n".join(self.state_lines(self.repo.dir)))

    def test_panes_that_stay(self):
        self.state(self.repo.dir, self.launch("k_l", task="wip", pane="t_launched"))
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-11-25 10:00 s-main t_main\n" % LIVE)
        terms = [self.pane("t_used", self.wip, 40, preview="$ ls\nfile.txt\nmaverick@host wip %"),
                 self.pane("t_launched", self.wip, 40, preview="", agent="claude"),
                 self.pane("t_helper", self.wip, 40, preview="", agent="claude",
                           title="◑ project Helper - Wip"),
                 self.pane("t_recent", self.wip, 10),
                 self.pane("t_mainfolder", self.repo.dir, 90),
                 self.pane("t_main", self.wip, 90, preview="", agent="claude")]
        self.run_with(terms, "--apply", env={"CLAUDE_PID": str(LIVE)})     # this session holds the lock
        self.assertEqual(self.closed(), [])

    def test_the_constant(self):
        sys.path.insert(0, BIN)
        import agent_conf
        self.assertEqual(agent_conf.CONSTANTS["unused_pane_min"], 30)


# ---------------------------------------------------------------- the rule text


class TestCleanupRules(unittest.TestCase):

    def test_merge_deputy_steps_for_every_case(self):
        text = read("agents", "merge-deputy.md")
        for phrase in ("task manager pane", "subagent", "git worktree unlock", "git worktree remove",
                       "git worktree prune", "worktree-agent-", "git push origin --delete",
                       "human-direct Helper", "its own pane always stays", "the folder stays",
                       "another machine", "--environment"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_the_worktree_line_always_goes_or_is_rewritten(self):
        text = read("agents", "merge-deputy.md")
        self.assertIn("agent-file.sh worktree rm", text)
        self.assertIn("also when the folder stays", text)

    def test_the_sweep_runs_after_every_merge(self):
        merge = read("skills", "merge", "SKILL.md")
        self.assertIn("agent-cleanup.sh --apply", merge)
        self.assertLess(merge.index("MERGE PASS"), merge.index("agent-cleanup.sh --apply"))
        w8 = read("PRINCIPLES.md").split("W8. ")[1].split("W9. ")[0]
        self.assertIn("after every merge", w8)
        self.assertIn("human-direct protects only the human's own session pane", w8)
        self.assertIn("never got a prompt", w8)

    def test_the_constant_is_pinned_with_the_others(self):
        text = read("tests", "test_settings_configure.py")
        self.assertIn('"unused_pane_min": 30', text)


if __name__ == "__main__":
    unittest.main()


class TestWorkingBranchStays(SweepCase):
    """Section 28 (2): the sweep never removes, and never lists, the working branch (setting Flow: Working
    branch), local or on origin, even when it holds no commit of its own."""

    def test_the_working_branch_is_never_a_row_and_never_removed(self):
        sys.path.insert(0, BIN)
        import agent_conf
        wb = agent_conf.WORKING_BRANCH_DEFAULT
        tc.git(self.repo.dir, "branch", wb)
        tc.git(self.repo.dir, "push", "-q", "origin", wb)
        out = self.ok("--apply")
        self.assertFalse([row for row in self.rows(out) if wb in row[0]], out)
        self.assertTrue(self.has_local(wb))
        self.assertTrue(self.has_origin(wb))


class TestRemoteListsToo(unittest.TestCase):
    """Re-check defect I: a paired machine's terminal list is checked for truncation like the local one."""

    def test_gather_machine_checks_the_list(self):
        src = read("bin", "agent_cleanup.py")
        body = src[src.index("    def gather_machine("):]
        body = body[:body.index("\n    def ", 10)]
        self.assertIn("list_complete(", body)


# ---------------------------------------------------------------- section 23: a Helper that joined

import test_agent_name as tn  # noqa: E402


class TestHelperJoin(tn.HelperCase):
    """Owner 2026-11-25: a human-direct session keeps its protection only while the human alone drives it."""

    def join(self, task, env=None, sid=tn.SID_A):
        base = {"CLAUDE_PID": tn.NOBODY, "ORCA_TERMINAL_HANDLE": "term_helper"}
        if sid is not None:
            base["CLAUDE_CODE_SESSION_ID"] = sid
        base.update(env or {})
        return self.repo.run("agent-file.sh", "helper-join", task, env=base)

    def rows(self):
        return [l for l in self.repo.read("agent_worktree.txt").splitlines() if l.strip()]

    def test_the_protected_line_becomes_a_normal_task_line(self):
        self.set_task("City Office 2")
        r = self.join("city-office-2")
        self.assertOk(r)
        mine = [l for l in self.rows() if l.startswith(self.repo.dir + " | ")]
        self.assertEqual(len(mine), 1, self.rows())
        self.assertRegex(mine[0], r"^%s \| city-office-2 \| working \| since \d{4}-\d{2}-\d{2} \d{2}:\d{2} \| "
                                  r"pane term_helper \| session %s$" % (re.escape(self.repo.dir), re.escape(tn.SID_A)))
        self.assertNotIn("human-direct", mine[0])
        self.assertIn("helper-join: city-office-2 (pane term_helper, session %s)" % tn.SID_A, r.stdout)

    def test_only_a_helper_may_join(self):
        before = self.repo.read("agent_worktree.txt")
        r = self.repo.run("agent-file.sh", "helper-join", "x", env={"CLAUDE_PID": str(os.getpid())})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        r = self.repo.run("agent-file.sh", "helper-join", "x", env={"AGENT_ROLE": "task-manager",
                                                                    "CLAUDE_PID": tn.NOBODY})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self.repo.read("agent_worktree.txt"), before)


class TestHelperJoinRules(unittest.TestCase):

    def test_w10(self):
        w10 = read("PRINCIPLES.md").split("W10. ")[1].split("W11. ")[0]
        for phrase in ("keeps its protection only while the human alone drives it", "agent-file.sh helper-join",
                       "takes a task from the main manager or reports DONE to it", "claude --resume <session id>"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w10)

    def test_merge_deputy_closes_a_joined_helper(self):
        text = read("agents", "merge-deputy.md")
        for phrase in ("helper-join", "like a task manager", "claude --resume <session id>"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_merge_and_dispatch_skills(self):
        self.assertIn("only while the human alone drives it", read("skills", "merge", "SKILL.md"))
        self.assertIn("helper-join", read("skills", "dispatch", "SKILL.md"))
