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
    def test_the_rules_line_points_into_the_plugin(self):
        out = self.assertOk(self.start())
        self.assertIn("RULES: read %s/PRINCIPLES.md now (S8)." % self.repo.plugin,
                      out)

    def test_the_quiz_line_points_into_the_plugin(self):
        out = self.assertOk(self.start())
        self.assertIn("QUIZ: run %s/bin/agent-start.sh --quiz" % self.repo.plugin,
                      out)

    def test_it_works_when_the_project_has_no_principles(self):
        self.assertFalse(os.path.exists(self.repo.path("PRINCIPLES.md")))
        out = self.assertOk(self.start())
        self.assertIn("QUIZ:", out)

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
    def test_the_project_files_are_counted(self):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("alpha | big | the open task\n")
        out = self.assertOk(self.start())
        self.assertIn("PROJECT: %s | PLUGIN: %s" % (self.repo.dir,
                                                    self.repo.plugin), out)
        self.assertIn("agent_todo.txt: 1 lines", out)

    def test_the_cap_comes_from_the_project_conf(self):
        self.repo.set_conf("max_usage_percent", "30")
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "40"}))
        self.assertIn("(cap 30%) -> OVER CAP", out)

    def test_a_subdirectory_still_finds_the_project(self):
        sub = self.repo.path("src", "deep")
        os.makedirs(sub)
        out = self.assertOk(self.start(cwd=sub))
        self.assertIn("PROJECT: %s | " % self.repo.dir, out)

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
        self.assertIn("PROJECT: %s | " % other, out)

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
        self.assertIn("PROJECT: %s | " % other, out)

    def test_stdin_cwd_wins_over_claude_project_dir(self):
        first = self.second_project("one")
        second = self.second_project("two")
        out = self.assertOk(self.start(cwd=self.repo.plugin,
                                       stdin=self.hook_json(second),
                                       env={"CLAUDE_PROJECT_DIR": first}))
        self.assertIn("PROJECT: %s | " % second, out)
        self.assertNotIn(first, out)

    def test_bad_stdin_json_falls_back_to_the_cwd(self):
        out = self.assertOk(self.start(stdin="not json at all"))
        self.assertIn("PROJECT: %s | " % self.repo.dir, out)


class TestProjectWorktree(RootsCase):
    """Started inside a git worktree of the project, the shared files still
    belong to the project's main repo. Only agent_state.txt is local."""

    def test_shared_files_come_from_the_main_repo(self):
        worktree = self.repo.detach_scripts_to_worktree()
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("alpha | big | the open task\n")
        out = self.assertOk(self.start(cwd=worktree))
        self.assertIn("PROJECT: %s | " % self.repo.dir, out)
        self.assertIn("agent_todo.txt: 1 lines", out)

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
        self.assertIn("  STATE-OF-THE-WORKTREE", out)
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


class TestProjectWithoutAgentConf(RootsCase):
    """A project that has not run agent-init.sh yet is the first thing the
    plugin meets. Nothing may fail silently there: the scripts fall back to
    their built-in defaults, and the one script that needs a real file says so.
    """

    def setUp(self):
        super().setUp()
        os.remove(self.repo.path("agent.conf"))

    def test_agent_start_runs_on_the_built_in_defaults(self):
        out = self.assertOk(self.start(env={"AGENT_FAKE_RAM": "90"}))
        self.assertIn("(cap 80%) -> OVER CAP", out)
        self.assertIn("QUIZ:", out)

    def test_agent_monitor_runs(self):
        result = self.repo.run("agent-monitor.sh", "once")
        self.assertEqual(result.returncode, 0,
                         "exit %d, stdout %r, stderr %r"
                         % (result.returncode, result.stdout, result.stderr))
        self.assertTrue(result.stdout.strip(), "it printed nothing at all")

    def test_agent_resume_runs(self):
        result = self.repo.run("agent-resume.sh", "--dry-run")
        self.assertEqual(result.returncode, 0,
                         "exit %d, stdout %r, stderr %r"
                         % (result.returncode, result.stdout, result.stderr))
        self.assertIn("=== resume ===", result.stdout)

    def test_agent_file_still_writes(self):
        self.assertOk(self.repo.run("agent-file.sh", "idea", "add", "no-conf"))
        self.assertIn("no-conf", self.repo.read("agent_ideas.txt"))

    def test_agent_settings_says_what_is_missing(self):
        result = self.repo.run("agent-settings.sh")
        self.assertEqual(result.returncode, 2)
        message = result.stdout + result.stderr
        self.assertIn("agent.conf", message)
        self.assertIn("agent-init.sh", message)

    def test_nothing_fails_without_a_word(self):
        """A non-zero exit with an empty output is the worst case of all."""
        for script, args in (("agent-monitor.sh", ("once",)),
                             ("agent-resume.sh", ("--dry-run",)),
                             ("agent-settings.sh", ())):
            with self.subTest(script=script):
                result = self.repo.run(script, *args)
                if result.returncode != 0:
                    self.assertTrue((result.stdout + result.stderr).strip(),
                                    "%s exited %d and said nothing"
                                    % (script, result.returncode))


class TestPlainDirectory(RootsCase):
    """A directory that is not a git repo at all.

    roots_read documents a fallback for it: PROJECT_ROOT becomes the directory
    itself. The fallback has to actually be reached, so the two git lookups
    that have no `| awk` after them must not let git's exit 128 escape under
    `set -eu`.
    """

    def plain(self):
        return self.repo.make_project("plain")

    def test_roots_read_returns_and_falls_back(self):
        plain = self.plain()
        probe = self.repo.write_bin_script("probe.sh", (
            "#!/usr/bin/env bash\nset -eu\n"
            '. "$(dirname "$0")/agent-roots.sh"\n'
            'roots_read "$1"\n'
            'echo "REACHED $PROJECT_ROOT $STATE_DIR"\n'))
        self.assertTrue(probe)
        result = self.repo.run("probe.sh", plain)
        self.assertEqual(result.returncode, 0,
                         "exit %d, stderr %r" % (result.returncode, result.stderr))
        self.assertIn("REACHED %s %s" % (plain, plain), result.stdout)

    def test_agent_file_works_there(self):
        plain = self.plain()
        result = self.repo.run("agent-file.sh", "idea", "add", "plain-dir",
                               cwd=plain)
        self.assertEqual(result.returncode, 0,
                         "exit %d, stdout %r, stderr %r"
                         % (result.returncode, result.stdout, result.stderr))
        with open(os.path.join(plain, "agent_ideas.txt")) as fh:
            self.assertIn("plain-dir", fh.read())

    def test_agent_start_works_there(self):
        plain = self.plain()
        out = self.assertOk(self.start(cwd=plain))
        self.assertIn("QUIZ:", out)
        self.assertIn("PROJECT: %s | " % plain, out)

    def test_agent_monitor_works_there(self):
        plain = self.plain()
        result = self.repo.run("agent-monitor.sh", "once", cwd=plain)
        self.assertEqual(result.returncode, 0,
                         "exit %d, stdout %r, stderr %r"
                         % (result.returncode, result.stdout, result.stderr))

    def test_no_fake_git_directory_is_made(self):
        """`.git` is a name git owns. An empty one makes git call the folder
        a broken repo, so no script may create it."""
        plain = self.plain()
        self.assertOk(self.repo.run("agent-monitor.sh", "once", cwd=plain))
        self.assertOk(self.start(cwd=plain))
        self.assertOk(self.repo.run("agent-resume.sh", "--dry-run", cwd=plain))
        self.assertFalse(os.path.exists(os.path.join(plain, ".git")),
                         "a .git directory was invented in a plain folder")

    def test_the_private_files_go_in_a_folder_of_our_own(self):
        plain = self.plain()
        self.assertOk(self.repo.run("agent-monitor.sh", "once", cwd=plain))
        self.assertTrue(
            os.path.exists(os.path.join(plain, ".auto-pipeline",
                                        "agent_monitor.lastsweep")),
            "no git dir here, so the pid and sweep files belong in "
            ".auto-pipeline/")

    def test_the_lock_goes_there_too(self):
        plain = self.plain()
        self.assertOk(self.start(cwd=plain))
        self.assertTrue(os.path.exists(os.path.join(plain, ".auto-pipeline",
                                                    "agent_main.lock")))

    def test_nothing_complains_about_a_missing_path(self):
        plain = self.plain()
        for script, args in (("agent-start.sh", ()),
                             ("agent-monitor.sh", ("once",)),
                             ("agent-resume.sh", ("--dry-run",))):
            with self.subTest(script=script):
                result = self.repo.run(script, *args, cwd=plain)
                self.assertNotIn("No such file", result.stderr)

    def test_agent_init_needs_no_workaround_of_its_own(self):
        """agent-init.sh must not have to turn `set -e` off around roots_read."""
        with open(self.repo.plugin_path("bin", "agent-init.sh")) as fh:
            text = fh.read()
        self.assertNotIn("set +e", text,
                         "the fallback belongs in agent-roots.sh, not here")


class TestResumeFromAnywhere(RootsCase):
    script = "agent-resume.sh"

    def test_it_reads_the_project_worktree_file(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        out = self.assertOk(self.repo.run("agent-resume.sh", "--dry-run"))
        self.assertIn(path, out)


if __name__ == "__main__":
    unittest.main()
