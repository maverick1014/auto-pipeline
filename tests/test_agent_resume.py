"""Tests of bin/agent-resume.sh: relaunch rules, the launch command, the agent cap, plain and cloud.

One class per feature. Older task contracts: git log -p of this file.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase
import shlex
import shutil
import stat
import subprocess


from sharedrepo import REPO_BASE, shared_fixture  # noqa: E402


class ResumeCase(ScriptCase):
    script = "agent-resume.sh"

    def resume(self, *args, **kwargs):
        return self.repo.run("agent-resume.sh", *args, **kwargs)

    def rows(self, out):
        """The table rows, as (path, status, relaunched) tuples."""
        found, rows = False, []
        for line in out.splitlines():
            line = line.rstrip()
            if line.startswith("worktree | status | relaunched"):
                found = True
                continue
            if not found or not line:
                continue
            if " | " not in line:
                break
            parts = [p.strip() for p in line.split(" | ")]
            rows.append(tuple(parts[:3]))
        return rows

    def relaunched_for(self, out, path):
        for row in self.rows(out):
            if row[0] == path:
                return row[2]
        self.fail("no table row for %s in:\n%s" % (path, out))


@shared_fixture(guard=REPO_BASE, remember_repo=True)   # one repo, each resume call once; the tests only read
class TestResourcesLine(ResumeCase):
    def test_resources_line_comes_first(self):
        out = self.assertOk(self.resume("--dry-run"))
        first = [l for l in out.splitlines() if l.strip()][0]
        self.assertTrue(first.startswith("RESOURCES:"), first)
        self.assertIn("RAM", first)
        self.assertIn("CPU", first)
        self.assertIn("cap", first)

    def test_resources_line_says_ok_when_under_the_cap(self):
        out = self.assertOk(self.resume("--dry-run",
                                        env={"AGENT_FAKE_RAM": "10",
                                             "AGENT_FAKE_CPU": "20"}))
        self.assertIn("RESOURCES: RAM 10% CPU 20% (cap 80%) -> OK", out)

    def test_resources_line_says_over_cap(self):
        out = self.assertOk(self.resume("--dry-run",
                                        env={"AGENT_FAKE_RAM": "95",
                                             "AGENT_FAKE_CPU": "20"}))
        self.assertIn("-> OVER CAP", out)


class TestRelaunch(ResumeCase):
    def test_relaunches_a_working_line_with_no_live_pane(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        self.repo.set_panes([{"path": path, "agents": []}])
        out = self.assertOk(self.resume())
        self.assertEqual(self.relaunched_for(out, path), "yes")
        self.assertEqual(len(self.repo.create_calls()), 1)

    def test_relaunches_a_final_line_too(self):
        path = self.repo.make_worktree("beta")
        self.repo.set_worktree_lines([(path, "beta", "final")])
        self.repo.set_panes([])
        out = self.assertOk(self.resume())
        self.assertEqual(self.relaunched_for(out, path), "yes")
        self.assertEqual(len(self.repo.create_calls()), 1)

    def test_a_pane_in_any_state_counts_as_live(self):
        for state in ("working", "done", "permission"):
            with self.subTest(state=state):
                self.repo.clear_calls()
                path = self.repo.make_worktree("s_" + state)
                self.repo.set_worktree_lines([(path, "s_" + state, "working")])
                self.repo.set_panes([{"path": path, "agents": [state]}])
                out = self.assertOk(self.resume())
                self.assertEqual(self.relaunched_for(out, path), "no, pane is live")
                self.assertEqual(self.repo.create_calls(), [])

    def test_does_not_relaunch_an_idle_line(self):
        path = self.repo.make_worktree("delta")
        self.repo.set_worktree_lines([(path, "delta", "idle")])
        self.repo.set_panes([])
        out = self.assertOk(self.resume())
        self.assertEqual(self.relaunched_for(out, path), "no, status is idle")
        self.assertEqual(self.repo.create_calls(), [])

    def test_does_not_relaunch_when_the_path_is_gone(self):
        path = os.path.join(self.repo.dir, "wt_gone")
        self.repo.set_worktree_lines([(path, "gone", "working")])
        self.repo.set_panes([])
        out = self.assertOk(self.resume())
        self.assertEqual(self.relaunched_for(out, path), "no, path is gone")
        self.assertEqual(self.repo.create_calls(), [])

    def test_relaunches_only_the_lines_that_need_it(self):
        live = self.repo.make_worktree("live")
        dead = self.repo.make_worktree("dead")
        idle = self.repo.make_worktree("idle")
        self.repo.set_worktree_lines([
            (live, "live", "working"),
            (dead, "dead", "working"),
            (idle, "idle", "idle"),
        ])
        self.repo.set_panes([{"path": live, "agents": ["working"]}])
        out = self.assertOk(self.resume())
        calls = self.repo.create_calls()
        self.assertEqual(len(calls), 1)
        self.assertIn("path:" + dead, " ".join(calls[0]))
        self.assertEqual(self.relaunched_for(out, live), "no, pane is live")
        self.assertEqual(self.relaunched_for(out, dead), "yes")
        self.assertEqual(self.relaunched_for(out, idle), "no, status is idle")

    def test_launches_nothing_when_over_the_cap(self):
        path = self.repo.make_worktree("capped")
        self.repo.set_worktree_lines([(path, "capped", "working")])
        self.repo.set_panes([])
        out = self.assertOk(self.resume(env={"AGENT_FAKE_RAM": "95"}))
        self.assertEqual(self.relaunched_for(out, path), "no, over cap")
        self.assertEqual(self.repo.create_calls(), [])


class TestLaunchCommand(ResumeCase):
    # settings-configure: the Task manager model setting must meet the decider floor
    # (Opus 5.5+ or Fable, effort medium+); a value below it reads as the default opus-5.5:high
    def launch_args(self, task_manager="opus-5.5:xhigh", permission_mode="auto",
                    module="alpha"):
        path = self.repo.make_worktree(module)
        self.repo.set_conf("task_manager", task_manager)
        self.repo.set_conf("permission_mode", permission_mode)
        self.repo.set_worktree_lines([(path, module, "working")])
        self.repo.set_panes([])
        self.assertOk(self.resume())
        calls = self.repo.create_calls()
        self.assertEqual(len(calls), 1, calls)
        return path, calls[0]

    def test_full_argument_list(self):
        path, args = self.launch_args()
        self.assertEqual(args, [
            "terminal", "create",
            "--worktree", "path:" + path,
            "--title", "TM alpha",
            "--command",
            "AGENT_ROLE=task-manager claude --model opus --effort xhigh "
            "--permission-mode auto",
            "--json",
        ])

    def test_title_uses_the_module_name(self):
        _, args = self.launch_args(module="pospro")
        self.assertIn("TM pospro", args)

    def test_model_comes_from_the_setting(self):
        for value, expected in (
            ("opus-5.5:xhigh", "opus"),
            ("fable-5.1:xhigh", "fable"),
            ("sonnet-5:medium", "opus"),     # below the floor: the default opus-5.5:high
        ):
            with self.subTest(value=value):
                self.repo.clear_calls()
                _, args = self.launch_args(task_manager=value,
                                           module="m" + value.replace(":", "-").replace(".", "-"))
                command = args[args.index("--command") + 1]
                self.assertIn("--model %s " % expected, command + " ")

    def test_a_model_below_the_floor_falls_back_to_the_default(self):
        self.repo.clear_calls()
        _, args = self.launch_args(task_manager="mystery-7:high", module="mm")
        command = args[args.index("--command") + 1]
        self.assertIn("--model opus --effort high", command)
        self.assertNotIn("mystery-7", command)

    def test_effort_comes_from_the_setting(self):
        for value, expected in (
            ("opus-5.5:xhigh", "xhigh"),
            ("opus-5.5:medium", "medium"),
            ("opus-5.5:low", "high"),        # below the floor: the default
            ("fable-5.1:high", "high"),
            ("opus-5.5:max", "max"),
        ):
            with self.subTest(value=value):
                self.repo.clear_calls()
                _, args = self.launch_args(task_manager=value,
                                           module="e" + value.replace(":", "-").replace(".", "-"))
                command = args[args.index("--command") + 1]
                self.assertIn("--effort %s " % expected, command + " ")

    def test_permission_mode_comes_from_agent_conf(self):
        self.repo.clear_calls()
        _, args = self.launch_args(permission_mode="acceptEdits", module="pm")
        command = args[args.index("--command") + 1]
        self.assertIn("--permission-mode acceptEdits", command)

    def test_bypass_mode_reaches_the_relaunched_terminal(self):
        """bypass-mode (owner, 2026-11-04): a resumed task manager opens in
        permission_mode, bypassPermissions too."""
        self.repo.clear_calls()
        _, args = self.launch_args(permission_mode="bypassPermissions", module="bp")
        command = args[args.index("--command") + 1]
        self.assertIn("--permission-mode bypassPermissions", command)
        self.assertNotIn("plan", command)


class TestDryRun(ResumeCase):
    def test_dry_run_still_shows_the_reasons(self):
        live = self.repo.make_worktree("live")
        idle = self.repo.make_worktree("idle")
        self.repo.set_worktree_lines([(live, "live", "working"),
                                      (idle, "idle", "idle")])
        self.repo.set_panes([{"path": live, "agents": ["working"]}])
        out = self.assertOk(self.resume("--dry-run"))
        self.assertEqual(self.relaunched_for(out, live), "no, pane is live")
        self.assertEqual(self.relaunched_for(out, idle), "no, status is idle")


class TestTable(ResumeCase):
    def test_table_header(self):
        out = self.assertOk(self.resume("--dry-run"))
        self.assertIn("=== resume ===", out)
        self.assertIn("worktree | status | relaunched", out)

    def test_empty_worktree_file_says_so(self):
        out = self.assertOk(self.resume("--dry-run"))
        self.assertIn("(no live worktrees)", out)
        self.assertEqual(self.rows(out), [])

    def test_rows_keep_file_order(self):
        first = self.repo.make_worktree("one")
        second = self.repo.make_worktree("two")
        self.repo.set_worktree_lines([(first, "one", "idle"),
                                      (second, "two", "idle")])
        out = self.assertOk(self.resume("--dry-run"))
        self.assertEqual([r[0] for r in self.rows(out)], [first, second])

    def test_row_shows_the_status_from_the_file(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "final")])
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        out = self.assertOk(self.resume("--dry-run"))
        self.assertEqual(self.rows(out)[0][1], "final")

    def test_counts_todo_and_ideas(self):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("a | small | x\nb | big | y\n")
        with open(self.repo.path("agent_ideas.txt"), "w") as fh:
            fh.write("idea one\nidea two\nidea three\n")
        out = self.assertOk(self.resume("--dry-run"))
        self.assertIn("todo: 2 open", out)
        self.assertIn("ideas: 3 waiting", out)

    def test_counts_are_zero_when_the_files_are_empty(self):
        out = self.assertOk(self.resume("--dry-run"))
        self.assertIn("todo: 0 open", out)
        self.assertIn("ideas: 0 waiting", out)


class TestAgentCap(ResumeCase):
    """S6: max_agents is a machine limit. Resume must not blow past it."""

    def setup_cap(self, max_agents, dead, live_elsewhere=0, main_managers=0):
        """`dead` worktrees needing a relaunch, plus panes busy somewhere else."""
        self.repo.set_conf("max_agents", str(max_agents))
        paths = [self.repo.make_worktree("dead%d" % i) for i in range(dead)]
        self.repo.set_worktree_lines([(p, "dead%d" % i, "working")
                                      for i, p in enumerate(paths)])
        panes = [{"path": p, "agents": []} for p in paths]
        for i in range(live_elsewhere):
            panes.append({"path": "/elsewhere/%d" % i, "agents": ["working"]})
        for i in range(main_managers):
            panes.append({"path": "/other-repo/%d" % i, "agents": ["working"],
                          "is_main": True})
        self.repo.set_panes(panes)
        return paths

    def test_stops_relaunching_at_the_cap(self):
        paths = self.setup_cap(max_agents=3, dead=3, live_elsewhere=2)
        out = self.assertOk(self.resume())
        self.assertEqual(len(self.repo.create_calls()), 1, out)
        self.assertEqual(self.relaunched_for(out, paths[0]), "yes")
        self.assertEqual(self.relaunched_for(out, paths[1]), "no, cap reached")
        self.assertEqual(self.relaunched_for(out, paths[2]), "no, cap reached")

    def test_relaunches_count_towards_the_cap(self):
        paths = self.setup_cap(max_agents=2, dead=3, live_elsewhere=0)
        out = self.assertOk(self.resume())
        self.assertEqual(len(self.repo.create_calls()), 2, out)
        self.assertEqual(self.relaunched_for(out, paths[2]), "no, cap reached")

    def test_done_and_idle_agents_do_not_count(self):
        paths = self.setup_cap(max_agents=2, dead=1)
        self.repo.set_panes([{"path": paths[0], "agents": []},
                             {"path": "/elsewhere/a", "agents": ["done"]},
                             {"path": "/elsewhere/b", "agents": ["done", "idle"]},
                             {"path": "/elsewhere/c", "agents": ["idle"]}])
        out = self.assertOk(self.resume())
        self.assertEqual(self.relaunched_for(out, paths[0]), "yes")

    def test_working_and_permission_agents_count(self):
        paths = self.setup_cap(max_agents=2, dead=1)
        self.repo.set_panes([{"path": paths[0], "agents": []},
                             {"path": "/elsewhere/a", "agents": ["working"]},
                             {"path": "/elsewhere/b", "agents": ["permission", "done"]}])
        out = self.assertOk(self.resume())
        self.assertEqual(self.relaunched_for(out, paths[0]), "no, cap reached")
        self.assertIn("cap reached (2/2), not relaunching %s" % paths[0], out)

    def test_a_full_cap_relaunches_nothing(self):
        paths = self.setup_cap(max_agents=1, dead=2, live_elsewhere=1)
        out = self.assertOk(self.resume())
        self.assertEqual(self.repo.create_calls(), [])
        for path in paths:
            self.assertEqual(self.relaunched_for(out, path), "no, cap reached")

    def test_the_cap_line_names_the_numbers_and_the_path(self):
        paths = self.setup_cap(max_agents=3, dead=2, live_elsewhere=3)
        out = self.assertOk(self.resume())
        for path in paths:
            self.assertIn("cap reached (3/3), not relaunching %s" % path, out)

    def test_the_cap_line_counts_the_relaunches_it_made(self):
        paths = self.setup_cap(max_agents=2, dead=3, live_elsewhere=0)
        out = self.assertOk(self.resume())
        self.assertIn("cap reached (2/2), not relaunching %s" % paths[2], out)

    def test_no_cap_line_when_nothing_is_capped(self):
        self.setup_cap(max_agents=4, dead=1, live_elsewhere=0)
        out = self.assertOk(self.resume())
        self.assertNotIn("cap reached", out)

    def test_panes_in_worktrees_that_are_not_in_the_file_still_count(self):
        paths = self.setup_cap(max_agents=2, dead=1, live_elsewhere=2)
        out = self.assertOk(self.resume())
        self.assertEqual(self.repo.create_calls(), [])
        self.assertEqual(self.relaunched_for(out, paths[0]), "no, cap reached")

    def test_dry_run_respects_the_cap_and_launches_nothing(self):
        paths = self.setup_cap(max_agents=2, dead=3, live_elsewhere=0)
        out = self.assertOk(self.resume("--dry-run"))
        self.assertEqual(self.repo.create_calls(), [])
        self.assertEqual(self.relaunched_for(out, paths[0]), "would")
        self.assertEqual(self.relaunched_for(out, paths[1]), "would")
        self.assertEqual(self.relaunched_for(out, paths[2]), "no, cap reached")

    def test_the_resource_cap_is_checked_first(self):
        paths = self.setup_cap(max_agents=1, dead=1, live_elsewhere=1)
        out = self.assertOk(self.resume(env={"AGENT_FAKE_RAM": "95"}))
        self.assertEqual(self.relaunched_for(out, paths[0]), "no, over cap")

    def test_a_live_pane_is_not_a_cap_problem(self):
        """A worktree that still has its own pane is skipped for that reason."""
        self.repo.set_conf("max_agents", "1")
        path = self.repo.make_worktree("alive")
        self.repo.set_worktree_lines([(path, "alive", "working")])
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        out = self.assertOk(self.resume())
        self.assertEqual(self.relaunched_for(out, path), "no, pane is live")
        self.assertNotIn("cap reached", out)

    def test_the_cap_lines_come_after_the_table(self):
        self.setup_cap(max_agents=1, dead=2, live_elsewhere=1)
        out = self.assertOk(self.resume())
        self.assertLess(out.index("worktree | status | relaunched"),
                        out.index("cap reached"))
        self.assertLess(out.index("cap reached"), out.index("todo:"))


class TestMainManagersDoNotCount(ResumeCase):
    """S6: the cap counts spawned agents. A main manager is not one of them.

    This is the real shape of the machine: `orca worktree ps --json` reports
    every repo Orca manages, and most of those panes are other repos' main
    managers. Counting them fills the cap before resume even starts.
    """

    def setup_cap(self, **kwargs):
        return TestAgentCap.setup_cap(self, **kwargs)

    def test_a_main_manager_pane_does_not_fill_a_slot(self):
        paths = self.setup_cap(max_agents=1, dead=1, main_managers=3)
        out = self.assertOk(self.resume())
        self.assertEqual(self.relaunched_for(out, paths[0]), "yes")
        self.assertEqual(len(self.repo.create_calls()), 1)

    def test_the_real_shape_of_this_laptop(self):
        """Three other repos' main managers, one spawned agent, cap 4."""
        paths = self.setup_cap(max_agents=4, dead=2, live_elsewhere=1,
                               main_managers=3)
        out = self.assertOk(self.resume())
        self.assertEqual(len(self.repo.create_calls()), 2, out)
        self.assertNotIn("cap reached", out)

    def test_spawned_panes_still_count(self):
        paths = self.setup_cap(max_agents=2, dead=2, live_elsewhere=2,
                               main_managers=5)
        out = self.assertOk(self.resume())
        self.assertEqual(self.repo.create_calls(), [])
        self.assertEqual(self.relaunched_for(out, paths[0]), "no, cap reached")

    def test_the_cap_line_leaves_main_managers_out_of_the_count(self):
        self.setup_cap(max_agents=2, dead=1, live_elsewhere=2, main_managers=4)
        out = self.assertOk(self.resume())
        self.assertIn("cap reached (2/2), not relaunching", out)

    def test_a_worktree_of_this_repo_that_is_also_the_main_repo(self):
        """The main repo can carry a worktree line. Its pane is a main manager."""
        self.repo.set_conf("max_agents", "1")
        dead = self.repo.make_worktree("dead")
        self.repo.set_worktree_lines([(dead, "dead", "working")])
        self.repo.set_panes([
            {"path": dead, "agents": []},
            {"path": self.repo.dir, "agents": ["working"], "is_main": True},
        ])
        out = self.assertOk(self.resume())
        self.assertEqual(self.relaunched_for(out, dead), "yes")


class TestOrcaDown(ResumeCase):
    """Orca is not always running.

    This is the FAULT path, and it only exists when agent.conf pins
    runtime=orca: the human said Orca is the runtime, so Orca being down is a
    fault and gets said out loud. On `auto` the same machine is simply not an
    Orca machine, which is the normal plain path, not a fault -- see
    TestOrcaDownOnAuto below.
    """

    def setUp(self):
        super(TestOrcaDown, self).setUp()
        self.repo.set_conf("runtime", "orca")

    def test_orca_down_still_exits_zero(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        self.repo.stub_orca_down()
        out = self.assertOk(self.resume())
        self.assertIn("orca is not answering", out)

    def test_orca_down_relaunches_nothing(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        self.repo.stub_orca_down()
        out = self.assertOk(self.resume())
        self.assertEqual(self.relaunched_for(out, path), "no, orca is down")
        self.assertEqual(self.repo.create_calls(), [])

    def test_orca_down_still_prints_the_counts(self):
        self.repo.stub_orca_down()
        out = self.assertOk(self.resume())
        self.assertIn("todo: 0 open", out)
        self.assertIn("ideas: 0 waiting", out)


@shared_fixture(guard=REPO_BASE, remember_repo=True)   # one repo, each resume call once; the tests only read
class TestOrcaDownOnAuto(ResumeCase):
    """orca on PATH but not answering, with no runtime pinned, is plain."""

    def setUp(self):
        super(TestOrcaDownOnAuto, self).setUp()
        self.repo.set_conf("runtime", "auto")
        self.repo.stub_orca_down()
        self.path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(self.path, "alpha", "working")])

    def test_it_is_plain_mode_not_a_fault(self):
        self.assertEqual(
            self.relaunched_for(self.assertOk(self.resume()), self.path),
            "no, plain mode")

    def test_it_does_not_blame_orca(self):
        self.assertNotIn("orca is not answering", self.assertOk(self.resume()))

class TestStdinIsSafe(ResumeCase):
    def test_a_launch_that_reads_stdin_does_not_eat_the_worktree_file(self):
        """The orca call sits inside a `while read` loop. It must not steal its input."""
        paths = [self.repo.make_worktree("m%d" % i) for i in range(3)]
        self.repo.set_worktree_lines([(p, "m%d" % i, "working")
                                      for i, p in enumerate(paths)])
        self.repo.set_panes([])
        self.repo.stub_orca_reads_stdin()
        out = self.assertOk(self.resume())
        self.assertEqual(len(self.repo.create_calls()), 3,
                         "the launch swallowed agent_worktree.txt:\n" + out)
        for path in paths:
            self.assertEqual(self.relaunched_for(out, path), "yes")


class TestRunsFromItsOwnDirectory(ResumeCase):
    """The main repo does not carry a copy of the scripts. A worktree does."""

    def test_works_when_the_main_repo_has_no_scripts(self):
        worktree = self.repo.detach_scripts_to_worktree()
        self.assertFalse(os.path.exists(os.path.join(self.repo.dir,
                                                     "agent-resources.sh")))
        out = self.assertOk(self.resume("--dry-run"))
        self.assertIn("RESOURCES:", out)
        self.assertIn("=== resume ===", out)
        self.assertTrue(worktree)

class TestCountsAlwaysPrint(ResumeCase):
    def test_counts_print_after_a_real_start(self):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("a | small | x\n")
        out = self.assertOk(self.resume())
        self.assertIn("todo: 1 open", out)
        self.assertIn("ideas: 0 waiting", out)


@shared_fixture(guard=REPO_BASE, remember_repo=True)   # one repo, each resume call once; the tests only read
class TestUsage(ResumeCase):
    def test_help_exits_zero(self):
        result = self.repo.run("agent-resume.sh", "-h")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agent-resume.sh", result.stdout)

    def test_unknown_argument_exits_two(self):
        result = self.repo.run("agent-resume.sh", "--wat")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_runs_from_any_directory(self):
        out = self.assertOk(self.repo.run("agent-resume.sh", "--dry-run",
                                          cwd=self.repo.bin))
        self.assertIn("=== resume ===", out)


class PlainCase(ResumeCase):
    """No terminals. Two worktrees that would be relaunched under Orca."""

    KIND = "plain"

    def setUp(self):
        super(PlainCase, self).setUp()
        self.repo.set_conf("runtime", self.KIND)
        self.alpha = self.repo.make_worktree("alpha")
        self.beta = self.repo.make_worktree("beta")
        self.repo.set_worktree_lines([
            (self.alpha, "alpha", "working"),
            (self.beta, "beta", "idle"),
        ])

    def out(self):
        return self.assertOk(self.resume())


@shared_fixture(guard=REPO_BASE, remember_repo=True)   # one repo, each resume call once; the tests only read
class TestPlainRelaunchesNothing(PlainCase):
    def test_the_working_row_names_the_mode(self):
        self.assertEqual(self.relaunched_for(self.out(), self.alpha),
                         "no, %s mode" % self.KIND)

    def test_no_row_ever_says_yes(self):
        for row in self.rows(self.out()):
            with self.subTest(row=row):
                self.assertNotEqual(row[2], "yes")

    def test_it_calls_orca_never(self):
        self.out()
        self.assertEqual(self.repo.calls(), [])

    def test_it_never_blames_orca(self):
        self.assertNotIn("orca is not answering", self.out())

    def test_the_table_still_lists_every_line(self):
        rows = self.rows(self.out())
        self.assertEqual([row[0] for row in rows], [self.alpha, self.beta])

    def test_it_says_what_needs_starting_by_hand(self):
        out = self.out()
        after = out[out.index(self.beta):]
        self.assertIn(self.alpha, after,
                      "no line telling the reader what to start")

    def test_it_does_not_ask_for_an_idle_worktree_to_be_started(self):
        out = self.out()
        after = out[out.index("| idle |"):]
        self.assertNotIn(self.beta, after.replace("| idle |", "", 1))

    def test_the_counts_still_print(self):
        out = self.out()
        self.assertIn("todo: 0 open", out)
        self.assertIn("ideas: 0 waiting", out)

    def test_the_resources_line_still_comes_first(self):
        self.assertTrue(self.lines(self.out())[0].startswith("RESOURCES:"))


@shared_fixture(guard=REPO_BASE, remember_repo=True)   # one repo, each resume call once; the tests only read
class TestNoMonitorAnyMore(PlainCase):
    """bin/agent-monitor.sh is gone (2026-11-24): resume prints no monitor line and starts no loop."""

    def test_no_monitor_line(self):
        self.assertNotIn("monitor:", self.out())

    def test_no_pid_file_appears(self):
        self.out()
        self.assertFalse(os.path.exists(os.path.join(
            self.repo.dir, ".git", "agent_monitor.pid")))


class TestCloudIsTheSameShape(PlainCase):
    KIND = "cloud"

    def setUp(self):
        super(TestCloudIsTheSameShape, self).setUp()
        self.repo.set_conf("runtime", "cloud")

    def test_the_row_names_the_cloud(self):
        self.assertEqual(self.relaunched_for(self.out(), self.alpha),
                         "no, cloud mode")

    def test_the_remote_marker_alone_is_enough(self):
        self.repo.set_conf("runtime", "auto")
        out = self.assertOk(self.resume(env={"CLAUDE_CODE_REMOTE": "true"}))
        self.assertEqual(self.relaunched_for(out, self.alpha), "no, cloud mode")


class TestAutoStillPicksOrca(ResumeCase):
    def test_a_machine_with_orca_relaunches_as_before(self):
        self.repo.set_conf("runtime", "auto")
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        self.repo.set_panes([])
        self.assertEqual(self.relaunched_for(self.assertOk(self.resume()), path),
                         "yes")

    def test_a_machine_without_orca_falls_back_to_plain(self):
        self.repo.set_conf("runtime", "auto")
        self.repo.no_orca()
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        self.assertEqual(self.relaunched_for(self.assertOk(self.resume()), path),
                         "no, plain mode")


class TestAConfWrittenBeforeRuntimeExisted(ResumeCase):
    """An agent.conf from an older release has no `runtime` line at all.

    Unset must read as auto, everywhere. These scripts run under `set -u`, so
    a bare $runtime would kill the whole run instead of defaulting.
    """

    def setUp(self):
        super(TestAConfWrittenBeforeRuntimeExisted, self).setUp()
        self.repo.unset_conf("runtime")
        self.path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(self.path, "alpha", "working")])
        self.repo.set_panes([])

    def test_it_says_nothing_about_an_unbound_variable(self):
        result = self.resume()
        self.assertNotIn("unbound", result.stderr.lower())

    def test_it_still_relaunches_through_orca(self):
        self.assertEqual(
            self.relaunched_for(self.assertOk(self.resume()), self.path), "yes")

    def test_it_falls_back_to_plain_with_no_orca(self):
        self.repo.no_orca()
        self.assertEqual(
            self.relaunched_for(self.assertOk(self.resume()), self.path),
            "no, plain mode")


class TestResumeRefusesDefault(ScriptCase):
    script = "agent-resume.sh"

    def command(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        self.repo.set_panes([])
        self.assertOk(self.repo.run("agent-resume.sh"))
        calls = self.repo.create_calls()
        self.assertEqual(len(calls), 1, calls)
        return calls[0][calls[0].index("--command") + 1]

    def test_default_relaunches_in_the_setting_default(self):
        self.repo.set_conf("permission_mode", "default")
        command = self.command()
        self.assertTrue(command.endswith("--permission-mode bypassPermissions"), command)
        self.assertNotIn("default", command)

    def test_dont_ask_reaches_the_relaunch(self):
        self.repo.set_conf("permission_mode", "dontAsk")
        self.assertTrue(self.command().endswith("--permission-mode dontAsk"))


ZSH = shutil.which("zsh")


def flag(words, name):
    return words[words.index(name) + 1] if name in words else None


class ZshRun:
    """Run a launch line in a real zsh (no rc files) with a fake `claude` first
    on PATH that prints each argument on its own line, then ROLE=$AGENT_ROLE."""

    def __init__(self, base):
        self.bin = os.path.join(base, "fakebin")
        os.makedirs(self.bin, exist_ok=True)
        exe = os.path.join(self.bin, "claude")
        with open(exe, "w") as fh:
            fh.write('#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done\nprintf "ROLE=%s\\n" "$AGENT_ROLE"\n')
        os.chmod(exe, os.stat(exe).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def __call__(self, line):
        env = dict(os.environ)
        env["PATH"] = self.bin + os.pathsep + env.get("PATH", "")
        env.pop("AGENT_ROLE", None)
        done = subprocess.run([ZSH, "-f", "-c", line], capture_output=True, text=True, env=env,
                              timeout=30, stdin=subprocess.DEVNULL)
        return done.returncode, done.stdout.splitlines(), done.stderr


class TestResumeLineRunsInZsh(ScriptCase):
    script = "agent-resume.sh"

    def command(self, task_manager, module="alpha"):
        self.repo.clear_calls()
        path = self.repo.make_worktree(module)
        self.repo.set_conf("task_manager", task_manager)
        self.repo.set_conf("permission_mode", "auto")
        self.repo.set_worktree_lines([(path, module, "working")])
        self.repo.set_panes([])
        self.assertOk(self.repo.run("agent-resume.sh"))
        calls = self.repo.create_calls()
        self.assertEqual(len(calls), 1, calls)
        return calls[0][calls[0].index("--command") + 1]

    def test_the_words_keep_the_suffix(self):
        for spec, want, module in (("opus-5.5[1m]:xhigh", "opus[1m]", "a1"),
                                   ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]", "a2")):
            with self.subTest(spec=spec):
                words = shlex.split(self.command(spec, module))
                self.assertEqual(flag(words, "--model"), want)
                self.assertEqual(flag(words, "--effort"), spec.rsplit(":", 1)[1])

    @unittest.skipUnless(ZSH, "no zsh on PATH")
    def test_zsh_runs_the_line_without_a_glob_error(self):
        run = ZshRun(self.repo.path())
        for spec, want, effort, module in (("opus-5.5[1m]:xhigh", "opus[1m]", "xhigh", "z1"),
                                           ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]", "high", "z2"),
                                           ("fable-5.1[1m]:max", "fable[1m]", "max", "z3")):
            with self.subTest(spec=spec):
                code, out, err = run(self.command(spec, module))
                self.assertNotIn("no matches found", err)
                self.assertEqual((code, out), (0, ["--model", want, "--effort", effort,
                                                   "--permission-mode", "auto", "ROLE=task-manager"]), err)

    def test_a_plain_model_word_stays_bare(self):
        command = self.command("opus-5.5:xhigh", "p1")
        self.assertEqual(command, "AGENT_ROLE=task-manager claude --model opus --effort xhigh --permission-mode auto")


class TestResumePermission(ScriptCase):
    script = "agent-resume.sh"

    def command(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        self.repo.set_panes([])
        self.assertOk(self.repo.run("agent-resume.sh"))
        calls = self.repo.create_calls()
        self.assertEqual(len(calls), 1, calls)
        return calls[0][calls[0].index("--command") + 1]

    def test_the_setting(self):
        self.repo.set_conf("permission_mode", "acceptEdits")
        self.assertTrue(self.command().endswith("--permission-mode acceptEdits"))

    def test_an_old_user_file_decides_nothing(self):
        self.repo.set_user_conf("permission_mode=plan\n")
        self.assertTrue(self.command().endswith("--permission-mode bypassPermissions"))

    def test_nothing_set_is_bypass(self):
        self.assertTrue(self.command().endswith("--permission-mode bypassPermissions"))


if __name__ == "__main__":
    unittest.main()
