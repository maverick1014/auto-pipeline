"""Failing tests for bin/agent-init.sh. Written by the task manager, before any code.

CONTRACT:

    bin/agent-init.sh              set up the current project
    bin/agent-init.sh <dir>        set up that project
    bin/agent-init.sh -h           usage, exit 0
    a directory that is not there  exit 2, message on stderr

It is idempotent. It creates, only when missing, in the PROJECT ROOT:

    agent.conf                 a copy of the plugin's bin/agent.conf.default
    agent_todo.txt             empty
    agent_completed.txt        empty
    agent_ideas.txt            empty
    agent_worktree.txt         empty
    .secrets/                  empty directory
    AGENTS.md                  one line:
        Run <plugin>/bin/agent-start.sh first. No work until the quiz says PASS.

and adds these lines to .gitignore when they are not already there:

    .secrets/
    agent_state.txt
    agent_monitor.txt
    agent_monitor.txt.tmp.*
    .auto-pipeline/            where the private files go when there is no git dir

It never overwrites a file that is already there. It prints one line per file,
saying created or kept, and ends with the permissions block for the human to
paste into the project's .claude/settings.json, plus one line saying why a
plugin cannot add it itself.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase, ScriptRepo

MADE_FILES = ["agent.conf", "agent_todo.txt", "agent_completed.txt",
              "agent_ideas.txt", "agent_worktree.txt", "AGENTS.md"]

GITIGNORE_LINES = [".secrets/", "agent_state.txt", "agent_monitor.txt",
                   "agent_monitor.txt.tmp.*", ".auto-pipeline/"]

ALLOW_RULES = [
    "Bash(git push origin --delete *)",
    "Bash(git branch -d *)",
    "Bash(git worktree remove *)",
    "Bash(git worktree prune)",
    "Bash(orca worktree rm *)",
    "Bash(orca terminal close *)",
]


class InitCase(ScriptCase):
    script = "agent-init.sh"

    def setUp(self):
        if not os.path.exists(os.path.join(
                os.path.dirname(HERE), "bin", "agent-init.sh")):
            self.fail("bin/agent-init.sh does not exist yet. Write it.")
        self.repo = ScriptRepo(init_project=False)
        self.addCleanup(self.repo.cleanup)
        self.project = self.repo.dir
        self.repo.git_init(self.project)

    def init(self, *args, **kwargs):
        return self.repo.run("agent-init.sh", *args, **kwargs)

    def read(self, *parts):
        with open(os.path.join(self.project, *parts)) as fh:
            return fh.read()

    def gitignore_lines(self):
        if not os.path.exists(os.path.join(self.project, ".gitignore")):
            return []
        return [line.strip() for line in self.read(".gitignore").splitlines()]


class TestCreatesTheFiles(InitCase):
    def test_every_file_is_made(self):
        self.assertOk(self.init())
        for name in MADE_FILES:
            with self.subTest(name=name):
                self.assertTrue(os.path.exists(os.path.join(self.project, name)),
                                "%s is missing" % name)

    def test_the_four_task_files_start_empty(self):
        self.assertOk(self.init())
        for name in ("agent_todo.txt", "agent_completed.txt",
                     "agent_ideas.txt", "agent_worktree.txt"):
            with self.subTest(name=name):
                self.assertEqual(self.read(name), "")

    def test_secrets_is_a_directory(self):
        self.assertOk(self.init())
        self.assertTrue(os.path.isdir(os.path.join(self.project, ".secrets")))

    def test_agent_conf_is_the_template(self):
        self.assertOk(self.init())
        with open(self.repo.plugin_path("bin", "agent.conf.default")) as fh:
            template = fh.read()
        self.assertEqual(self.read("agent.conf"), template)

    def test_it_makes_nothing_else(self):
        self.assertOk(self.init())
        made = sorted(n for n in os.listdir(self.project) if n != ".git")
        self.assertEqual(
            made,
            sorted(MADE_FILES + [".secrets", ".gitignore", "seed.txt", "stubbin"]))


class TestAgentsMd(InitCase):
    def test_it_points_at_this_plugin_by_absolute_path(self):
        self.assertOk(self.init())
        expected = ("Run %s/bin/agent-start.sh first. "
                    "No work until the quiz says PASS." % self.repo.plugin)
        self.assertEqual(self.read("AGENTS.md").strip(), expected)

    def test_it_is_one_line(self):
        self.assertOk(self.init())
        self.assertEqual(len(self.read("AGENTS.md").strip().splitlines()), 1)

    def test_an_existing_agents_md_keeps_its_own_text(self):
        with open(os.path.join(self.project, "AGENTS.md"), "w") as fh:
            fh.write("House rules: never force push.\n")
        self.assertOk(self.init())
        text = self.read("AGENTS.md")
        self.assertIn("House rules: never force push.", text)
        self.assertIn("bin/agent-start.sh", text)


class TestGitignore(InitCase):
    def test_all_four_lines_are_added(self):
        self.assertOk(self.init())
        for line in GITIGNORE_LINES:
            with self.subTest(line=line):
                self.assertIn(line, self.gitignore_lines())

    def test_an_existing_gitignore_keeps_its_lines(self):
        with open(os.path.join(self.project, ".gitignore"), "w") as fh:
            fh.write("node_modules/\n.secrets/\n")
        self.assertOk(self.init())
        lines = self.gitignore_lines()
        self.assertIn("node_modules/", lines)
        self.assertEqual(lines.count(".secrets/"), 1)

    def test_no_line_is_added_twice(self):
        self.assertOk(self.init())
        self.assertOk(self.init())
        lines = self.gitignore_lines()
        for line in GITIGNORE_LINES:
            with self.subTest(line=line):
                self.assertEqual(lines.count(line), 1)


class TestIdempotent(InitCase):
    def snapshot(self):
        out = {}
        for dirpath, dirnames, names in os.walk(self.project):
            if ".git" in dirnames:
                dirnames.remove(".git")
            for name in names:
                full = os.path.join(dirpath, name)
                with open(full, "rb") as fh:
                    out[os.path.relpath(full, self.project)] = fh.read()
        return out

    def test_a_second_run_changes_nothing(self):
        self.assertOk(self.init())
        before = self.snapshot()
        self.assertOk(self.init())
        self.assertEqual(self.snapshot(), before)

    def test_an_existing_conf_is_kept(self):
        with open(os.path.join(self.project, "agent.conf"), "w") as fh:
            fh.write("max_agents=9\n")
        self.assertOk(self.init())
        self.assertEqual(self.read("agent.conf"), "max_agents=9\n")

    def test_existing_task_lines_are_kept(self):
        with open(os.path.join(self.project, "agent_todo.txt"), "w") as fh:
            fh.write("alpha | big | keep me\n")
        self.assertOk(self.init())
        self.assertIn("keep me", self.read("agent_todo.txt"))

    def test_the_second_run_says_kept(self):
        self.assertOk(self.init())
        out = self.assertOk(self.init())
        self.assertIn("kept", out)
        self.assertIn("agent.conf", out)


class TestWhereItRuns(InitCase):
    def test_it_takes_a_directory_argument(self):
        other = self.repo.make_project("elsewhere")
        self.assertOk(self.init(other, cwd=self.repo.plugin))
        self.assertTrue(os.path.exists(os.path.join(other, "agent.conf")))
        self.assertFalse(os.path.exists(os.path.join(self.project, "agent.conf")))

    def test_it_uses_the_project_root_from_a_subdirectory(self):
        sub = os.path.join(self.project, "src", "deep")
        os.makedirs(sub)
        self.assertOk(self.init(cwd=sub))
        self.assertTrue(os.path.exists(os.path.join(self.project, "agent.conf")))
        self.assertFalse(os.path.exists(os.path.join(sub, "agent.conf")))

    def test_it_works_in_a_plain_directory_that_is_not_a_repo(self):
        plain = self.repo.make_project("plain")
        self.assertOk(self.init(plain, cwd=self.repo.plugin))
        self.assertTrue(os.path.exists(os.path.join(plain, "agent_todo.txt")))

    def test_a_missing_directory_exits_two(self):
        result = self.init(os.path.join(self.repo.base, "nope"),
                           cwd=self.repo.plugin)
        self.assertEqual(result.returncode, 2)
        self.assertTrue((result.stderr + result.stdout).strip())


class TestPermissionBlock(InitCase):
    def block(self):
        out = self.assertOk(self.init())
        start = out.index("{")
        end = out.rindex("}")
        return out, json.loads(out[start:end + 1])

    def test_the_block_is_valid_json(self):
        _, data = self.block()
        self.assertIsInstance(data, dict)

    def test_it_holds_the_six_rules(self):
        _, data = self.block()
        self.assertEqual(data["permissions"]["allow"], ALLOW_RULES)

    def test_it_says_why_the_human_must_paste_it(self):
        out, _ = self.block()
        lowered = out.lower()
        self.assertIn("permission", lowered)
        self.assertIn("plugin", lowered)
        self.assertIn("settings.json", lowered)

    def test_it_names_the_file_to_paste_into(self):
        out, _ = self.block()
        self.assertIn(".claude/settings.json", out)


class TestUsage(InitCase):
    def test_help_exits_zero(self):
        result = self.init("-h")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agent-init.sh", result.stdout)

    def test_help_creates_nothing(self):
        self.init("-h")
        self.assertFalse(os.path.exists(os.path.join(self.project, "agent.conf")))


class TestTemplate(InitCase):
    """bin/agent.conf.default is the one place the defaults live."""

    def test_the_template_has_every_key(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        import agent_conf

        conf = agent_conf.load(self.repo.plugin_path("bin", "agent.conf.default"))
        for key in list(agent_conf.NUMBER_BOUNDS) + agent_conf.ROLE_KEYS \
                + ["permission_mode"]:
            with self.subTest(key=key):
                self.assertIn(key, conf)

    def test_the_template_is_valid(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        import agent_conf

        conf = agent_conf.load(self.repo.plugin_path("bin", "agent.conf.default"))
        self.assertEqual(agent_conf.validate(conf), {})


if __name__ == "__main__":
    unittest.main()
