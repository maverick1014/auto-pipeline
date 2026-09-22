"""Failing tests for the two roots. Written by the task manager, before any code.

CONTRACT. Every script in bin/ is started by its absolute path, from any
directory, and must tell two roots apart:

  PLUGIN root   = the folder above the script, $(dirname "$0")/..
                  PRINCIPLES.md, the quiz, agent_conf.py, bin/agent.conf.default.
                  Read only. A script never writes here.

  PROJECT       = the repo being worked on. Found in this order:
                    1. "cwd" from the hook's stdin JSON (SessionStart)
                    2. $CLAUDE_PROJECT_DIR
                    3. the current directory
                  PROJECT ROOT is the main worktree of `git worktree list` run
                  from there, so a script started inside a git worktree still
                  writes the shared files into the project's main repo.

  Per-project files, in the PROJECT ROOT:
      agent.conf, agent_todo.txt, agent_completed.txt, agent_ideas.txt,
      agent_worktree.txt, agent_monitor.txt, .secrets/
  In the project's shared git dir: the main-manager lock, the monitor pid.
  agent_state.txt is per working directory: the git toplevel of the directory
  the agent is in, so a worktree keeps its own state file.

The same plugin serves any number of projects and never mixes them up.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase

PRINCIPLES_MARK = "PLUGIN-PRINCIPLES-MARKER"


class RootsCase(ScriptCase):
    script = "agent-start.sh"

    def mark_principles(self):
        """Put a marker in the plugin's PRINCIPLES.md so we can spot it."""
        path = self.repo.plugin_path("PRINCIPLES.md")
        with open(path, "a") as fh:
            fh.write("\n%s\n" % PRINCIPLES_MARK)

    def second_project(self, name="other", cap=None):
        """A second project, its own git repo, with its own agent files."""
        path = self.repo.make_project(name)
        for txt in ("agent_todo.txt", "agent_completed.txt", "agent_ideas.txt",
                    "agent_worktree.txt"):
            open(os.path.join(path, txt), "w").close()
        with open(os.path.join(path, "agent.conf"), "w") as fh:
            fh.write("max_usage_percent=%d\n" % (cap if cap else 80))
        with open(os.path.join(path, "agent_todo.txt"), "w") as fh:
            fh.write("only-in-%s | big | marker line\n" % name)
        self.repo.git_init(path)
        return path

    def start(self, *args, **kwargs):
        return self.repo.run("agent-start.sh", *args, **kwargs)


class TestPluginRoot(RootsCase):
    def test_principles_comes_from_the_plugin(self):
        self.mark_principles()
        out = self.assertOk(self.start())
        self.assertIn("=== PRINCIPLES.md ===", out)
        self.assertIn(PRINCIPLES_MARK, out)

    def test_it_works_when_the_project_has_no_principles(self):
        self.assertFalse(os.path.exists(self.repo.path("PRINCIPLES.md")))
        out = self.assertOk(self.start())
        self.assertIn("=== QUIZ", out)

    def test_the_plugin_is_never_written_to(self):
        before = sorted(os.listdir(self.repo.plugin))
        self.assertOk(self.start())
        self.assertOk(self.repo.run("agent-file.sh", "idea", "add", "x"))
        self.assertOk(self.repo.run("agent-monitor.sh", "once"))
        self.assertEqual(sorted(os.listdir(self.repo.plugin)), before)

    def test_no_agent_txt_file_lands_in_the_plugin(self):
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add", "a", "big", "x"))
        left = [n for n in os.listdir(self.repo.plugin) if n.startswith("agent_")]
        self.assertEqual(left, [])


class TestProjectFromCwd(RootsCase):
    def test_the_project_files_are_printed(self):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("alpha | big | the open task\n")
        out = self.assertOk(self.start())
        self.assertIn("alpha | big | the open task", out)

    def test_the_cap_comes_from_the_project_conf(self):
        self.repo.set_conf("max_usage_percent", "30")
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "40"}))
        self.assertIn("(cap 30%) -> OVER CAP", out)

    def test_a_subdirectory_still_finds_the_project(self):
        sub = self.repo.path("src", "deep")
        os.makedirs(sub)
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("alpha | big | the open task\n")
        out = self.assertOk(self.start(cwd=sub))
        self.assertIn("alpha | big | the open task", out)

    def test_the_lock_lands_in_the_project_git_dir(self):
        self.assertOk(self.start())
        self.assertTrue(os.path.exists(self.repo.path(".git", "agent_main.lock")))
        self.assertFalse(os.path.exists(
            self.repo.plugin_path(".git", "agent_main.lock")))


class TestProjectFromHookStdin(RootsCase):
    def hook_json(self, cwd, source="startup"):
        return json.dumps({"cwd": cwd, "session_id": "s1", "source": source})

    def test_stdin_cwd_picks_the_project(self):
        other = self.second_project()
        out = self.assertOk(self.start(cwd=self.repo.plugin,
                                       stdin=self.hook_json(other)))
        self.assertIn("only-in-other", out)

    def test_the_other_project_files_are_not_touched(self):
        other = self.second_project()
        self.assertOk(self.start(cwd=self.repo.plugin,
                                 stdin=self.hook_json(other)))
        self.assertTrue(os.path.exists(os.path.join(other, ".git",
                                                    "agent_main.lock")))
        self.assertFalse(os.path.exists(self.repo.path(".git",
                                                       "agent_main.lock")))

    def test_the_conf_of_that_project_is_used(self):
        other = self.second_project(cap=25)
        out = self.assertOk(self.start(cwd=self.repo.plugin,
                                       stdin=self.hook_json(other),
                                       env={"AGENT_FAKE_RAM": "40"}))
        self.assertIn("(cap 25%) -> OVER CAP", out)

    def test_claude_project_dir_is_used_when_there_is_no_stdin_cwd(self):
        other = self.second_project()
        out = self.assertOk(self.start(cwd=self.repo.plugin,
                                       env={"CLAUDE_PROJECT_DIR": other}))
        self.assertIn("only-in-other", out)

    def test_stdin_cwd_wins_over_claude_project_dir(self):
        first = self.second_project("one")
        second = self.second_project("two")
        out = self.assertOk(self.start(cwd=self.repo.plugin,
                                       stdin=self.hook_json(second),
                                       env={"CLAUDE_PROJECT_DIR": first}))
        self.assertIn("only-in-two", out)
        self.assertNotIn("only-in-one", out)

    def test_bad_stdin_json_falls_back_to_the_cwd(self):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("alpha | big | the open task\n")
        out = self.assertOk(self.start(stdin="not json at all"))
        self.assertIn("alpha | big | the open task", out)


class TestProjectWorktree(RootsCase):
    """Started inside a git worktree of the project, the shared files still
    belong to the project's main repo. Only agent_state.txt is local."""

    def test_shared_files_come_from_the_main_repo(self):
        worktree = self.repo.detach_scripts_to_worktree()
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("alpha | big | the open task\n")
        out = self.assertOk(self.start(cwd=worktree))
        self.assertIn("alpha | big | the open task", out)

    def test_agent_file_writes_into_the_main_repo(self):
        worktree = self.repo.detach_scripts_to_worktree()
        self.assertOk(self.repo.run("agent-file.sh", "idea", "add", "from-wt",
                                    cwd=worktree))
        self.assertIn("from-wt", self.repo.read("agent_ideas.txt"))

    def test_state_file_is_the_worktrees_own(self):
        worktree = self.repo.detach_scripts_to_worktree()
        with open(os.path.join(worktree, "agent_state.txt"), "w") as fh:
            fh.write("STATE-OF-THE-WORKTREE\n")
        with open(self.repo.path("agent_state.txt"), "w") as fh:
            fh.write("STATE-OF-THE-MAIN-REPO\n")
        out = self.assertOk(self.start(cwd=worktree))
        self.assertIn("STATE-OF-THE-WORKTREE", out)
        self.assertNotIn("STATE-OF-THE-MAIN-REPO", out)

    def test_the_lock_is_shared_between_worktrees(self):
        """One main manager per repo (W10): the lock lives in the shared git dir."""
        worktree = self.repo.detach_scripts_to_worktree()
        self.assertOk(self.start(cwd=worktree))
        out = self.assertOk(self.start(cwd=self.repo.dir,
                                       env={"CLAUDE_PID": "999999"}))
        self.assertIn("ROLE: task manager, human-direct", out)

    def test_the_second_session_line_lands_in_the_project_root(self):
        self.assertOk(self.start())
        self.assertOk(self.start(env={"CLAUDE_PID": "999999"}))
        self.assertIn("human-direct", self.repo.read("agent_worktree.txt"))


class TestAgentFileFromAnywhere(RootsCase):
    script = "agent-file.sh"

    def test_writes_into_the_project_root_from_a_subdirectory(self):
        sub = self.repo.path("src")
        os.makedirs(sub)
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add",
                                    "beta", "big", "work", cwd=sub))
        self.assertIn("beta | big | work", self.repo.read("agent_todo.txt"))

    def test_it_serves_a_second_project(self):
        other = self.second_project()
        self.assertOk(self.repo.run("agent-file.sh", "idea", "add", "second",
                                    cwd=other))
        with open(os.path.join(other, "agent_ideas.txt")) as fh:
            self.assertIn("second", fh.read())
        self.assertNotIn("second", self.repo.read("agent_ideas.txt") or "")


class TestSettingsFromAnywhere(RootsCase):
    script = "agent-settings.sh"

    def test_show_reads_the_project_conf(self):
        self.repo.set_conf("max_agents", "7")
        out = self.assertOk(self.repo.run("agent-settings.sh"))
        self.assertIn("max_agents", out)
        self.assertIn("7", out)

    def test_set_writes_the_project_conf(self):
        self.assertOk(self.repo.run("agent-settings.sh", "max_agents", "6"))
        self.assertIn("max_agents=6", self.repo.read("agent.conf"))

    def test_the_template_in_the_plugin_is_not_touched(self):
        template = self.repo.plugin_path("bin", "agent.conf.default")
        with open(template) as fh:
            before = fh.read()
        self.assertOk(self.repo.run("agent-settings.sh", "max_agents", "6"))
        with open(template) as fh:
            self.assertEqual(fh.read(), before)


class TestMonitorFromAnywhere(RootsCase):
    script = "agent-monitor.sh"

    def test_the_monitor_file_lands_in_the_project(self):
        self.assertOk(self.repo.run("agent-monitor.sh", "once"))
        self.assertTrue(os.path.exists(self.repo.path("agent_monitor.txt")))
        self.assertFalse(os.path.exists(
            self.repo.plugin_path("agent_monitor.txt")))

    def test_the_pid_file_lands_in_the_project_git_dir(self):
        self.assertOk(self.repo.run("agent-monitor.sh", "start"))
        self.assertTrue(os.path.exists(self.repo.path(".git",
                                                      "agent_monitor.pid")))


class TestResumeFromAnywhere(RootsCase):
    script = "agent-resume.sh"

    def test_it_reads_the_project_worktree_file(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        out = self.assertOk(self.repo.run("agent-resume.sh", "--dry-run"))
        self.assertIn(path, out)


if __name__ == "__main__":
    unittest.main()
