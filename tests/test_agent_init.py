"""UPDATE settings-configure (2026-11-25): init writes no agent.conf and reads no
CLAUDE_PLUGIN_OPTION_*; settings live in /plugin -> Installed -> auto-pipeline ->
Configure. The agent.conf and template lines below are history.

Failing tests for bin/agent-init.sh. Written by the task manager, before any code.

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
                               <plugin> is absolute, except for a plugin
                               packed inside the project (agent-cloud-pack.sh):
                               then it is relative to the project root, so the
                               line still works in any clone.

and adds these lines to .gitignore when they are not already there:

    .secrets/
    agent_state.txt
    agent_monitor.txt
    agent_monitor.txt.tmp.*
    .auto-pipeline/            where the private files go when there is no git dir

It never overwrites a file that is already there. It prints one line per file,
saying created or kept, then two blocks the human has to paste himself:

    1. the permissions block, for the project's .claude/settings.json, plus one
       line saying why a plugin cannot add it itself
    2. the cloud block, for the Setup script of a cloud environment:
           npx playwright install --with-deps chromium || true
       The default cloud image already ships Playwright and Chromium, so the
       block says to paste it only if <plugin>/bin/agent-runtime.sh browser
       prints none there, plus one line saying to skip it when this repo never
       runs in the cloud. That is not a repo file, so a plugin cannot set it.

Both blocks also show in `-h`, so the human can see them without creating
anything.

A fresh agent.conf is seeded from the plugin's bin/agent.conf.default, then the
three answers Claude Code collected at enable time are written over it when
they are set:

    CLAUDE_PLUGIN_OPTION_RUNTIME     -> runtime
    CLAUDE_PLUGIN_OPTION_LANGUAGE    -> language
    CLAUDE_PLUGIN_OPTION_MAX_AGENTS  -> max_agents

Unset means the template's own value stands. An agent.conf already in the
project is kept untouched, env or no env.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase, ScriptRepo

MADE_FILES = ["agent_todo.txt", "agent_completed.txt",
              "agent_ideas.txt", "agent_worktree.txt", "AGENTS.md",
              "agent_repo.conf"]   # check-blocks: the repo facts, tests/test_check_init.py

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

    def test_no_settings_file_is_made(self):
        # settings-configure 2026-11-25: settings live in Configure, never in the repo
        self.assertOk(self.init())
        self.assertFalse(os.path.exists(os.path.join(self.project, "agent.conf")))

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


class TestAgentsMdForAPackedPlugin(InitCase):
    """The pack puts the plugin inside the repo. An absolute path would be
    this machine's path, wrong in every other clone."""

    def setUp(self):
        super().setUp()
        import shutil
        self.inside = os.path.join(self.project, ".claude", "auto-pipeline")
        shutil.copytree(self.repo.plugin, self.inside)

    def test_it_names_the_plugin_relative_to_the_project(self):
        import subprocess
        result = subprocess.run(
            [os.path.join(self.inside, "bin", "agent-init.sh"), self.project],
            cwd=self.project, env=self.repo._env({}), capture_output=True,
            text=True, input="")
        self.assertOk(result)
        self.assertEqual(
            self.read("AGENTS.md").strip(),
            "Run .claude/auto-pipeline/bin/agent-start.sh first. "
            "No work until the quiz says PASS.")


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

    def test_an_old_conf_is_never_changed(self):
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
        self.assertIn("agent_todo.txt", out)


class TestWhereItRuns(InitCase):
    def test_it_takes_a_directory_argument(self):
        other = self.repo.make_project("elsewhere")
        self.assertOk(self.init(other, cwd=self.repo.plugin))
        self.assertTrue(os.path.exists(os.path.join(other, "agent_todo.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.project, "agent_todo.txt")))

    def test_it_uses_the_project_root_from_a_subdirectory(self):
        sub = os.path.join(self.project, "src", "deep")
        os.makedirs(sub)
        self.assertOk(self.init(cwd=sub))
        self.assertTrue(os.path.exists(os.path.join(self.project, "agent_todo.txt")))
        self.assertFalse(os.path.exists(os.path.join(sub, "agent_todo.txt")))

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



class TestCloudBlock(InitCase):
    """A cloud session needs a headless browser, and only its Setup script
    can install one. A plugin cannot reach that field."""

    PLAYWRIGHT = "npx playwright install --with-deps chromium"

    def test_a_real_run_prints_the_playwright_line(self):
        self.assertIn(self.PLAYWRIGHT, self.assertOk(self.init()))

    def test_help_prints_it_too(self):
        result = self.init("-h")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.PLAYWRIGHT, result.stdout)

    def test_it_says_where_to_paste_it(self):
        lowered = self.assertOk(self.init()).lower()
        self.assertIn("setup script", lowered)
        self.assertIn("cloud", lowered)

    def test_it_says_when_to_skip_it(self):
        self.assertIn("Skip this if you never run this repo in a cloud session.",
                      self.assertOk(self.init()))

    def test_it_says_the_default_image_already_has_a_browser(self):
        lowered = self.assertOk(self.init()).lower()
        self.assertIn("already", lowered)
        self.assertIn("playwright", lowered)

    def test_it_says_to_paste_it_only_when_no_browser_is_found(self):
        out = self.assertOk(self.init())
        self.assertIn("only if", out.lower())
        self.assertIn("bin/agent-runtime.sh browser prints none", out)

    def test_help_says_only_when_no_browser_is_found_too(self):
        result = self.init("-h")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agent-runtime.sh browser prints none", result.stdout)

    def test_it_comes_after_the_permission_block(self):
        out = self.assertOk(self.init())
        self.assertLess(out.index("permissions"), out.index(self.PLAYWRIGHT))

    def test_the_permission_block_is_still_the_only_json(self):
        out = self.assertOk(self.init())
        block = json.loads(out[out.index("{"):out.rindex("}") + 1])
        self.assertEqual(block["permissions"]["allow"], ALLOW_RULES)





class TestEndLines(InitCase):
    def test_it_ends_with_how_to_change_and_the_main_commands(self):
        out = self.assertOk(self.init())
        lines = out.strip().splitlines()
        self.assertIn("settings: /plugin -> Installed -> auto-pipeline -> Configure", lines)
        self.assertIn("/auto-pipeline:todo", lines[-1])
        self.assertIn("/auto-pipeline:question", lines[-1])

    def test_it_points_at_add_permissions(self):
        self.assertIn("--add-permissions", self.assertOk(self.init()))


class TestAddPermissions(InitCase):
    def path(self):
        return os.path.join(self.project, ".claude", "settings.json")

    def put(self, text):
        os.makedirs(os.path.dirname(self.path()), exist_ok=True)
        with open(self.path(), "w") as fh:
            fh.write(text)

    def load(self):
        with open(self.path()) as fh:
            return json.load(fh)

    def test_it_creates_the_file_when_missing(self):
        self.assertOk(self.init("--add-permissions"))
        self.assertEqual(self.load()["permissions"]["allow"], ALLOW_RULES)

    def test_it_merges_without_losing_keys_or_entries(self):
        self.put(json.dumps({"model": "opus", "env": {"A": "1"},
                             "permissions": {"allow": ["Bash(ls)"], "deny": ["Bash(rm *)"]}}))
        self.assertOk(self.init("--add-permissions"))
        data = self.load()
        self.assertEqual(data["model"], "opus")
        self.assertEqual(data["env"], {"A": "1"})
        self.assertEqual(data["permissions"]["deny"], ["Bash(rm *)"])
        self.assertEqual(data["permissions"]["allow"], ["Bash(ls)"] + ALLOW_RULES)
        self.assertNotIn("allow", data)

    def test_it_is_idempotent(self):
        self.put(json.dumps({"x": 1}))
        self.assertOk(self.init("--add-permissions"))
        with open(self.path()) as fh:
            first = fh.read()
        self.assertOk(self.init("--add-permissions"))
        with open(self.path()) as fh:
            self.assertEqual(fh.read(), first)
        self.assertEqual(self.load()["permissions"]["allow"], ALLOW_RULES)

    def test_it_refuses_invalid_json_and_writes_nothing(self):
        self.put("{ not json")
        result = self.init("--add-permissions")
        self.assertNotEqual(result.returncode, 0)
        with open(self.path()) as fh:
            self.assertEqual(fh.read(), "{ not json")

    def test_it_refuses_a_wrong_shape(self):
        self.put(json.dumps({"permissions": {"allow": "oops"}}))
        with open(self.path()) as fh:
            before = fh.read()
        self.assertNotEqual(self.init("--add-permissions").returncode, 0)
        with open(self.path()) as fh:
            self.assertEqual(fh.read(), before)

    def test_it_creates_no_other_project_file(self):
        self.assertOk(self.init("--add-permissions"))
        self.assertFalse(os.path.exists(os.path.join(self.project, "agent.conf")))


KEY = "auto-pipeline@auto-pipeline"


class TestScope(InitCase):
    def setUp(self):
        super().setUp()
        self.cfg = os.path.join(self.repo.base, "fake-config")
        os.makedirs(self.cfg)
        self.user = os.path.join(self.cfg, "settings.json")
        self.repo2 = os.path.join(self.repo.base, "repo2")
        os.makedirs(self.repo2)

    def scope(self, *args):
        return self.init("--scope", *args, env={"CLAUDE_CONFIG_DIR": self.cfg})

    def put(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data))

    def load(self, path):
        with open(path) as fh:
            return json.load(fh)

    def repo_file(self, repo=None):
        return os.path.join(repo or self.project, ".claude", "settings.json")

    def test_selected_writes_repo_true_and_user_false_keeping_keys(self):
        self.put(self.repo_file(), {"model": "opus", "enabledPlugins": {"x@y": True}})
        self.put(self.user, {"theme": "dark", "enabledPlugins": {KEY: True, "x@y": True}})
        result = self.scope("selected", self.project, self.repo2)
        self.assertOk(result)
        self.assertEqual(self.load(self.repo_file()),
                         {"model": "opus", "enabledPlugins": {"x@y": True, KEY: True}})
        self.assertEqual(self.load(self.repo_file(self.repo2)), {"enabledPlugins": {KEY: True}})
        self.assertEqual(self.load(self.user),
                         {"theme": "dark", "enabledPlugins": {KEY: False, "x@y": True}})
        self.assertEqual(self.load(self.user + ".bak")["enabledPlugins"][KEY], True)
        self.assertEqual(len(result.stdout.strip().splitlines()), 3)

    def test_selected_is_idempotent(self):
        self.put(self.user, {"enabledPlugins": {KEY: True}})
        self.assertOk(self.scope("selected", self.project))
        with open(self.user) as fh:
            first = fh.read()
        with open(self.repo_file()) as fh:
            first_repo = fh.read()
        result = self.scope("selected", self.project)
        self.assertOk(result)
        self.assertNotIn("updated", result.stdout)
        with open(self.user) as fh:
            self.assertEqual(fh.read(), first)
        with open(self.repo_file()) as fh:
            self.assertEqual(fh.read(), first_repo)

    def test_invalid_json_is_refused_and_nothing_is_written(self):
        self.put(self.repo_file(), "{ not json")
        self.put(self.user, {"enabledPlugins": {KEY: True}})
        result = self.scope("selected", self.repo2, self.project)
        self.assertNotEqual(result.returncode, 0)
        with open(self.repo_file()) as fh:
            self.assertEqual(fh.read(), "{ not json")
        self.assertEqual(self.load(self.user), {"enabledPlugins": {KEY: True}})
        self.assertFalse(os.path.exists(self.repo_file(self.repo2)))

    def test_invalid_user_json_is_refused(self):
        self.put(self.user, "oops")
        self.assertNotEqual(self.scope("selected", self.project).returncode, 0)
        self.assertFalse(os.path.exists(self.repo_file()))

    def test_config_dir_is_honoured(self):
        self.assertOk(self.scope("selected", self.project))
        self.assertEqual(self.load(self.user), {"enabledPlugins": {KEY: False}})

    def test_all_sets_user_true_and_leaves_repo_files(self):
        self.put(self.user, {"theme": "dark", "enabledPlugins": {KEY: False}})
        self.put(self.repo_file(), {"enabledPlugins": {KEY: True}})
        self.assertOk(self.scope("all"))
        self.assertEqual(self.load(self.user), {"theme": "dark", "enabledPlugins": {KEY: True}})
        self.assertEqual(self.load(self.repo_file()), {"enabledPlugins": {KEY: True}})

    def test_selected_needs_a_repo_and_a_real_directory(self):
        self.assertEqual(self.scope("selected").returncode, 2)
        self.assertEqual(self.scope("selected", "/no/such/dir").returncode, 2)
        self.assertFalse(os.path.exists(self.user))

    def test_bad_scope_value(self):
        self.assertEqual(self.scope("nope").returncode, 2)
