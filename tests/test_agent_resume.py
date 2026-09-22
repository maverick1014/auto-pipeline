"""Failing tests for agent-resume.sh (rule S2). Written by the task manager, before any code.

CONTRACT the worker must implement in agent-resume.sh (repo root, executable):

    ./agent-resume.sh              resume the pipeline
    ./agent-resume.sh --dry-run    print the plan, launch nothing
    ./agent-resume.sh -h           usage, exit 0

It prints, in this order:

  1. the RESOURCES line, the same words agent-start.sh prints:
       "RESOURCES: RAM <n>% CPU <n>% (cap <n>%) -> OK"   or "... -> OVER CAP"
  2. a blank line
  3. "=== resume ==="
  4. "worktree | status | relaunched"
  5. one row per line of agent_worktree.txt (main repo), in file order:
       "<path> | <status> | <relaunched>"
     <relaunched> is exactly one of:
       "yes"                  a task manager was launched there just now
       "would"                --dry-run, and it would be launched
       "no, pane is live"     an Orca pane with an agent is already there
       "no, path is gone"     the directory is not there any more
       "no, status is idle"   status is neither working nor final
       "no, over cap"         RAM or CPU at or over max_usage_percent
     when agent_worktree.txt is empty, print "(no live worktrees)" instead of rows
  6. the monitor line, one of:
       "monitor: started (pid <n>)"
       "monitor: already running (pid <n>)"
       "monitor: would start"          (--dry-run only)
  7. "todo: <n> open"
  8. "ideas: <n> waiting"

Relaunch, one orca call per worktree, with exactly these arguments:

    orca terminal create
         --worktree path:<path>
         --title "TM <module>"
         --command "AGENT_ROLE=task-manager claude --model <model> --effort <effort> --permission-mode <mode>"
         --json

    <model>  = agent.conf task_manager without the ":effort" part, cut down to the
               family word when it starts with opus, sonnet, haiku or fable
               (opus-5:xhigh -> opus). Anything else is passed through as it is.
    <effort> = agent.conf task_manager after the ":". `claude --effort` takes
               low, medium, high, xhigh, max.
    <mode>   = agent.conf permission_mode

A live pane = the worktree is in `orca worktree ps --json` with a non-empty agents list.
An empty agents list means the pane is gone, even when a plain shell is still open.

The agent cap (S6). Before each relaunch, count every live agent pane in
`orca worktree ps --json`, across every worktree and every repo, plus the
relaunches this run has already made. The cap is per device, so panes in other
repos count. A pane in a worktree the JSON marks "isMainWorktree": true is a
main manager and does NOT count -- S6 counts spawned agents only. At or over max_agents from agent.conf:
  - the row reads "no, cap reached"
  - and one plain line prints after the table, one per skipped worktree:
        cap reached (<n>/<max>), not relaunching <path>
A --dry-run "would" takes a slot too, so the plan it prints is honest.
The resource cap is checked first: "no, over cap" wins over "no, cap reached".

Resources come from agent-resources.sh, which honours AGENT_FAKE_RAM and AGENT_FAKE_CPU
so tests never have to measure the real machine.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase


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

    def test_does_not_relaunch_when_a_pane_is_live(self):
        path = self.repo.make_worktree("gamma")
        self.repo.set_worktree_lines([(path, "gamma", "working")])
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        out = self.assertOk(self.resume())
        self.assertEqual(self.relaunched_for(out, path), "no, pane is live")
        self.assertEqual(self.repo.create_calls(), [])

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
    def launch_args(self, task_manager="opus-5:xhigh", permission_mode="auto",
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

    def test_model_comes_from_agent_conf(self):
        for value, expected in (
            ("opus-5:xhigh", "opus"),
            ("sonnet-5:medium", "sonnet"),
            ("haiku-4.5:low", "haiku"),
            ("fable-5.1:xhigh", "fable"),
        ):
            with self.subTest(value=value):
                self.repo.clear_calls()
                _, args = self.launch_args(task_manager=value,
                                           module="m" + expected)
                command = args[args.index("--command") + 1]
                self.assertIn("--model %s " % expected, command + " ")

    def test_unknown_model_name_is_passed_through_without_the_effort(self):
        self.repo.clear_calls()
        _, args = self.launch_args(task_manager="mystery-7:high", module="mm")
        command = args[args.index("--command") + 1]
        self.assertIn("--model mystery-7 ", command + " ")
        self.assertNotIn("mystery-7:high", command)

    def test_effort_comes_from_agent_conf(self):
        for value, expected in (
            ("opus-5:xhigh", "xhigh"),
            ("sonnet-5:medium", "medium"),
            ("haiku-4.5:low", "low"),
            ("opus-5:high", "high"),
            ("opus-5:max", "max"),
        ):
            with self.subTest(value=value):
                self.repo.clear_calls()
                _, args = self.launch_args(task_manager=value,
                                           module="e" + expected)
                command = args[args.index("--command") + 1]
                self.assertIn("--effort %s " % expected, command + " ")

    def test_the_effort_flag_comes_after_the_model_flag(self):
        _, args = self.launch_args()
        command = args[args.index("--command") + 1]
        self.assertLess(command.index("--model"), command.index("--effort"))

    def test_permission_mode_comes_from_agent_conf(self):
        self.repo.clear_calls()
        _, args = self.launch_args(permission_mode="acceptEdits", module="pm")
        command = args[args.index("--command") + 1]
        self.assertIn("--permission-mode acceptEdits", command)

    def test_command_sets_the_task_manager_role(self):
        _, args = self.launch_args()
        command = args[args.index("--command") + 1]
        self.assertTrue(command.startswith("AGENT_ROLE=task-manager claude "), command)


class TestDryRun(ResumeCase):
    def test_dry_run_launches_nothing(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        self.repo.set_panes([])
        out = self.assertOk(self.resume("--dry-run"))
        self.assertEqual(self.repo.create_calls(), [])
        self.assertEqual(self.relaunched_for(out, path), "would")

    def test_dry_run_starts_no_monitor(self):
        self.assertOk(self.resume("--dry-run"))
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_monitor.pid")))

    def test_dry_run_says_the_monitor_would_start(self):
        out = self.assertOk(self.resume("--dry-run"))
        self.assertIn("monitor: would start", out)

    def test_dry_run_still_shows_the_reasons(self):
        live = self.repo.make_worktree("live")
        idle = self.repo.make_worktree("idle")
        self.repo.set_worktree_lines([(live, "live", "working"),
                                      (idle, "idle", "idle")])
        self.repo.set_panes([{"path": live, "agents": ["working"]}])
        out = self.assertOk(self.resume("--dry-run"))
        self.assertEqual(self.relaunched_for(out, live), "no, pane is live")
        self.assertEqual(self.relaunched_for(out, idle), "no, status is idle")


class TestMonitorHandover(ResumeCase):
    def test_starts_the_monitor_when_it_is_not_running(self):
        out = self.assertOk(self.resume())
        self.assertRegex(out, r"monitor: started \(pid \d+\)")
        self.assertTrue(os.path.exists(self.repo.path(".git", "agent_monitor.pid")))

    def test_does_not_start_a_second_monitor(self):
        self.assertOk(self.resume())
        out = self.assertOk(self.resume())
        self.assertRegex(out, r"monitor: already running \(pid \d+\)")

    def test_starts_the_monitor_even_when_over_the_cap(self):
        out = self.assertOk(self.resume(env={"AGENT_FAKE_RAM": "95"}))
        self.assertRegex(out, r"monitor: (started|already running) \(pid \d+\)")


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
        self.assertLess(out.index("cap reached"), out.index("monitor:"))


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
    """Orca is not always running. The script must say so in plain English, not crash."""

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
        self.assertIn("monitor: would start", out)
        self.assertTrue(worktree)

    def test_starts_the_monitor_next_to_itself(self):
        self.repo.detach_scripts_to_worktree()
        out = self.assertOk(self.resume())
        self.assertRegex(out, r"monitor: started \(pid \d+\)")


class TestCountsAlwaysPrint(ResumeCase):
    def test_counts_print_after_a_real_start(self):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("a | small | x\n")
        out = self.assertOk(self.resume())
        self.assertIn("todo: 1 open", out)
        self.assertIn("ideas: 0 waiting", out)


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


if __name__ == "__main__":
    unittest.main()
