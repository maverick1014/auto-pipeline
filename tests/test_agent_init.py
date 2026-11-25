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
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import getpass  # noqa: E402
import re  # noqa: E402
from scripthelp import BIN  # noqa: E402
import test_agent_checks as tcr  # noqa: E402
import pty  # noqa: E402

MADE_FILES = ["agent_todo.txt", "agent_completed.txt",
              "agent_ideas.txt", "agent_worktree.txt", "AGENTS.md",
              "agent_repo.conf"]   # check-blocks: the repo facts, tests/test_agent_init.py

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


class TestInitNamesThePushRule(ScriptCase):
    script = "agent-init.sh"

    def setUp(self):
        self.repo = ScriptRepo(init_project=False)
        self.addCleanup(self.repo.cleanup)
        self.repo.git_init(self.repo.dir)

    def test_optional_line_after_the_block(self):
        out = self.assertOk(self.repo.run("agent-init.sh"))
        start, end = out.index("{"), out.rindex("}")
        block = json.loads(out[start:end + 1])
        self.assertNotIn("Bash(git push origin main)", block["permissions"]["allow"])
        after = out[end + 1:]
        # check-blocks section 37 F3: the merge push goes to the person's working branch, never to main
        self.assertNotIn("git push origin main", after)
        line = [l for l in after.splitlines() if "Bash(git push origin ap-main-t)" in l]
        self.assertTrue(line, after)
        self.assertIn("optional", line[0].lower())


HEADER = ("# agent_repo.conf: this repo's own facts (check-blocks). Written by agent-init.sh, "
          "kept up to date by agents; a human may edit it, never has to.")


GENERIC = ["empty value", "more than one page", "deleted rows", "invalid input",
           "day boundary in local time", "double submit", "large size"]


class WorkingInitCase(ScriptCase):
    script = "agent-init.sh"

    def setUp(self):
        super().setUp()
        self.p = self.repo.dir

    def put(self, files):
        for rel, body in files.items():
            full = os.path.join(self.p, rel)
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            with open(full, "w") as fh:
                fh.write(body)

    def git(self, *args, env=None):
        e = dict(os.environ, **(env or {}))
        return subprocess.run(["git", "-C", self.p] + list(args), check=True, capture_output=True,
                              text=True, env=e).stdout

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)

    def init(self, *args, env=None):
        r = self.repo.run("agent-init.sh", *args, env=env)
        self.assertEqual(r.returncode, 0, "exit %d\n%s\n%s" % (r.returncode, r.stdout, r.stderr))
        return r

    def conf_text(self):
        with open(os.path.join(self.p, "agent_repo.conf")) as fh:
            return fh.read()

    def conf(self):
        """key -> value (last wins), plus 'edge' -> list and 'fix' -> list of # fix: subjects."""
        out = {"edge": [], "fix": [], "comments": []}
        for line in self.conf_text().splitlines():
            if line.startswith("# fix: "):
                out["fix"].append(line[len("# fix: "):])
            elif line.startswith("#"):
                out["comments"].append(line)
            elif "=" in line:
                k, v = line.split("=", 1)
                if k == "edge":
                    out["edge"].append(v)
                else:
                    out[k] = v
        return out


class TestFresh(WorkingInitCase):

    def test_an_empty_project_gets_version_1(self):
        r = self.init("--no-measure")
        text = self.conf_text()
        self.assertEqual(text.splitlines()[0], HEADER)
        c = self.conf()
        self.assertEqual(c["version"], "1")
        for key in ("core_paths", "guard_tests", "build_cmd", "related_cmd", "full_cmd", "test_config",
                    "data_scripts"):
            self.assertEqual(c[key], "", key)
        self.assertEqual(c["real_data"], "none")
        self.assertEqual(c["edge"], ["empty value", "invalid input"])
        self.assertIn("agent_repo.conf: written (version 1)", r.stdout.splitlines())

    def test_key_order(self):
        self.init("--no-measure")
        keys = [l.split("=", 1)[0] for l in self.conf_text().splitlines() if "=" in l and not l.startswith("#")]
        order = ["version", "core_paths", "guard_tests", "build_cmd", "related_cmd", "full_cmd", "test_config",
                 "data_scripts", "real_data"]
        self.assertEqual([k for k in keys if k in order], order)
        self.assertGreater(keys.index("edge"), keys.index("real_data"))
        self.assertNotIn("working_branch", keys)   # a setting now (owner 2026-11-25, section 28)

    def test_it_is_meant_to_be_committed(self):
        self.init("--no-measure")
        self.assertNotIn("agent_repo.conf", self.repo.read(".gitignore") or "")

    def test_a_second_run_changes_nothing(self):
        self.init("--no-measure")
        before = self.conf_text()
        r = self.init("--no-measure")
        self.assertEqual(self.conf_text(), before)
        self.assertIn("agent_repo.conf: kept", r.stdout.splitlines())


class TestDetect(WorkingInitCase):

    def test_python_unittest(self):
        self.put({"bin/tool.py": "x = 1\n", "tests/test_tool.py": "import unittest\nclass T(unittest.TestCase):\n    pass\n"})
        self.commit("py")
        self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["build_cmd"], "python3 -m compileall -q bin tests")
        self.assertEqual(c["related_cmd"], "python3 -m unittest {modules}")
        self.assertEqual(c["full_cmd"], "python3 -m unittest discover -s tests -t .")

    def test_pytest(self):
        self.put({"app/a.py": "x = 1\n", "tests/test_a.py": "import pytest\n\ndef test_a():\n    pass\n",
                  "pytest.ini": "[pytest]\n"})
        self.commit("pytest")
        self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["related_cmd"], "python3 -m pytest {tests}")
        self.assertEqual(c["full_cmd"], "python3 -m pytest")

    def test_jest_with_lint_and_typecheck_scripts(self):
        pkg = {"scripts": {"test": "jest", "lint": "eslint .", "typecheck": "tsc --noEmit"},
               "devDependencies": {"jest": "29"}}
        self.put({"package.json": json.dumps(pkg), "src/a.test.js": "it('a', () => {})\n"})
        self.commit("jest")
        self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["build_cmd"], "npm run lint && npm run typecheck")
        self.assertEqual(c["related_cmd"], "npx jest --maxWorkers=2 {tests}")
        self.assertEqual(c["full_cmd"], "npx jest --maxWorkers=2")

    def test_tsconfig_without_a_typecheck_script(self):
        pkg = {"scripts": {"lint": "eslint ."}, "devDependencies": {"vitest": "1"}}
        self.put({"package.json": json.dumps(pkg), "tsconfig.json": "{}\n"})
        self.commit("vitest")
        self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["build_cmd"], "npm run lint && npx tsc --noEmit")
        self.assertEqual(c["related_cmd"], "npx vitest run {tests}")
        self.assertEqual(c["full_cmd"], "npx vitest run")

    def test_flutter(self):
        self.put({"pubspec.yaml": "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n",
                  "test/a_test.dart": "void main() {}\n"})
        self.commit("flutter")
        self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["build_cmd"], "flutter analyze")
        self.assertEqual(c["related_cmd"], "flutter test -j 2 {tests}")
        self.assertEqual(c["full_cmd"], "flutter test -j 2")

    def test_go(self):
        self.put({"go.mod": "module x\n", "a.go": "package x\n"})
        self.commit("go")
        self.init("--no-measure")
        self.assertEqual(self.conf()["build_cmd"], "go vet ./...")

    def test_guard_tests_are_the_tests_that_read_the_tree(self):
        self.put({"tests/test_layout.py": "import os\nfor d, _, f in os.walk(ROOT):\n    pass\n",
                  "tests/test_files.py": "out = subprocess.run(['git', 'ls-files'])\n",
                  "tests/test_glob.py": "import glob\nglob.glob('**/*.md', recursive=True)\n",
                  "tests/test_plain.py": "def test_a():\n    assert 1\n",
                  "bin/walker.py": "import os\nos.walk('.')\n"})
        self.commit("tests")
        self.init("--no-measure")
        self.assertEqual(self.conf()["guard_tests"],
                         "tests/test_files.py,tests/test_glob.py,tests/test_layout.py")

    def test_core_paths_are_proposed(self):
        self.put({"src/auth/login.js": "x\n", "src/billing/pay.js": "x\n", "app/permissions.py": "x\n",
                  "db/migrations/0001.sql": "x\n", "src/ui/button.js": "x\n", "lib/ledger/post.rb": "x\n"})
        self.commit("tree")
        self.init("--no-measure")
        core = self.conf()["core_paths"].split(",")
        for glob in ("src/auth/", "src/billing/", "app/permissions.py", "db/migrations/", "lib/ledger/"):
            self.assertIn(glob, core)
        self.assertFalse([g for g in core if "ui" in g], core)

    def test_generic_edges_that_fit(self):
        self.put({"src/list.js": "const rows = paginate(q, { limit: 50, offset })\n",
                  "src/model.py": "deleted_at = Column(DateTime)\n",
                  "src/form.jsx": "<form onSubmit={save}>\n",
                  "src/export.py": "def export_csv(rows):\n    pass\n",
                  "src/day.js": "const d = new Date(); tz = 'Asia/Kuala_Lumpur'\n"})
        self.commit("code")
        self.init("--no-measure")
        self.assertEqual(self.conf()["edge"], GENERIC)

    def test_the_last_fix_commits_are_listed(self):
        for msg in ("feat: a page", "fix: refund larger than the invoice", "Bug: empty list crashes",
                    "hotfix: day boundary in KL time", "chore: tidy"):
            self.commit(msg)
        self.init("--no-measure")
        self.assertEqual(self.conf()["fix"], ["hotfix: day boundary in KL time", "Bug: empty list crashes",
                                              "fix: refund larger than the invoice"])

    def test_only_20_fix_commits(self):
        for i in range(25):
            self.commit("fix: bug %d" % i)
        self.init("--no-measure")
        fixes = self.conf()["fix"]
        self.assertEqual(len(fixes), 20)
        self.assertEqual(fixes[0], "fix: bug 24")

    def test_real_data_names_a_read_only_secret(self):
        os.makedirs(os.path.join(self.p, ".secrets"), exist_ok=True)
        self.put({".secrets/db_readonly.env": "URL=x\n", ".secrets/admin.env": "URL=y\n"})
        r = self.init("--no-measure")
        self.assertEqual(self.conf()["real_data"], ".secrets/db_readonly.env")
        self.assertNotIn("URL=", r.stdout + self.conf_text())


class TestExisting(WorkingInitCase):

    def test_only_missing_keys_are_added_and_set_values_stay(self):
        self.put({"agent_repo.conf": "level3_paths=src/money/\nbuild_cmd=make check\nedge=a refund\n",
                  "bin/a.py": "x = 1\n", "tests/test_a.py": "import unittest\n"})
        self.commit("old file")
        r = self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["level3_paths"], "src/money/")
        self.assertEqual(c["build_cmd"], "make check")
        self.assertEqual(c["related_cmd"], "python3 -m unittest {modules}")
        self.assertEqual(c["edge"], ["a refund"])
        lines = r.stdout.splitlines()
        self.assertIn("agent_repo.conf: added related_cmd", lines)
        self.assertNotIn("agent_repo.conf: added build_cmd", lines)
        self.assertNotIn("agent_repo.conf: added edge", lines)
        self.assertTrue(self.conf_text().startswith("level3_paths=src/money/\nbuild_cmd=make check\nedge=a refund\n"))


class TestMeasure(WorkingInitCase):

    def py_project(self, guard_sleep=0):
        files = {"bin/a.py": "x = 1\n", "tests/__init__.py": "",
                 "tests/test_tree.py": "import os, time, unittest\n\nclass T(unittest.TestCase):\n"
                                       "    def test_walk(self):\n        time.sleep(%d)\n"
                                       "        list(os.walk('.'))\n" % guard_sleep}
        self.put(files)
        self.commit("py")

    def test_build_and_guard_are_timed(self):
        self.py_project()
        r = self.init()
        c = self.conf()
        self.assertRegex(c["build_seconds"], r"^\d+$")
        self.assertLessEqual(int(c["build_seconds"]), 30)
        self.assertRegex(c["build_mb"], r"^\d+$")
        self.assertRegex(c["guard_seconds"], r"^\d+$")
        self.assertTrue(any(l.startswith("agent_repo.conf: measured build ") for l in r.stdout.splitlines()),
                        r.stdout)

    def test_no_measure_writes_no_numbers(self):
        self.py_project()
        self.init("--no-measure")
        c = self.conf()
        for key in ("build_seconds", "build_mb", "guard_seconds"):
            self.assertNotIn(key, c)

    def test_over_the_cap_is_not_measured(self):
        self.py_project()
        r = self.init(env={"AGENT_FAKE_RAM": "95"})
        self.assertNotIn("build_seconds", self.conf())
        self.assertIn("agent_repo.conf: not measured: RAM 95% over the 80% cap", r.stdout.splitlines())

    def test_a_run_that_hits_the_cap_is_heavy_and_not_retried(self):
        self.py_project(guard_sleep=4)
        r = self.init(env={"AGENT_INIT_MEASURE_CAP_S": "1"})
        lines = self.conf_text().splitlines()
        i = lines.index("guard_seconds=1")
        self.assertEqual(lines[i - 1], "# heavy: hit the 1 s cap")
        self.assertEqual(r.stdout.count("measured guard"), 1)
        r = self.init(env={"AGENT_INIT_MEASURE_CAP_S": "1"})
        self.assertNotIn("measured guard", r.stdout)


class TestReviewInit(WorkingInitCase):
    """Core review defect 11: init never proposes a core path with a space (it would be refused)."""

    def test_no_core_path_with_a_space(self):
        self.put({"Payment Service/pay.js": "x\n", "src/auth/login.js": "x\n"})
        self.commit("tree")
        self.init("--no-measure")
        core = self.conf()["core_paths"].split(",")
        self.assertIn("src/auth/", core)
        self.assertFalse([c for c in core if " " in c], core)


class TestWorkingBranch(WorkingInitCase):
    """Owner 2026-11-25 (sections 28, 29): every repo keeps the working branch (setting "Flow: Working
    branch"); init creates it from the production branch and switches the main checkout to it. No worktree."""

    def setUp(self):
        super().setUp()
        # section 44 F4: a repo that never used the plugin has no agent file at HEAD (the fixture commits them)
        tracked = [f for f in self.git("ls-files").split() if f.startswith("agent_")]
        if tracked:
            self.git("rm", "-q", "--cached", *tracked)
            self.git("commit", "-q", "-m", "not yet a plugin repo")

    def branch(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        import agent_conf
        return "ap-main-t"   # section 34: per person; the fixture's git user.name is t

    def head(self):
        return self.git("rev-parse", "--abbrev-ref", "HEAD").strip()

    def test_init_creates_the_branch_and_switches_the_checkout(self):
        prod = self.head()
        b = self.branch()
        r = self.init("--no-measure")
        lines = r.stdout.splitlines()
        self.assertIn("working branch: created %s from %s" % (b, prod), lines)
        self.assertIn("checkout: switched to %s" % b, lines)
        self.assertEqual(self.head(), b)
        self.assertEqual(self.git("rev-parse", b).strip(), self.git("rev-parse", prod).strip())
        self.assertEqual(self.git("worktree", "list").strip().count("\n"), 0, "no extra worktree")

    def test_a_second_run_keeps_it(self):
        self.init("--no-measure")
        r = self.init("--no-measure")
        self.assertIn("working branch: kept %s" % self.branch(), r.stdout.splitlines())
        self.assertIn("checkout: on %s" % self.branch(), r.stdout.splitlines())

    def test_local_changes_are_carried(self):
        self.put({"notes.txt": "mine\n"})
        self.init("--no-measure")
        self.assertEqual(self.head(), self.branch())
        with open(os.path.join(self.p, "notes.txt")) as fh:
            self.assertEqual(fh.read(), "mine\n")

    def test_the_setting_names_the_branch(self):
        self.repo.set_conf("working_branch", "trunk")
        r = self.init("--no-measure")
        self.assertIn("checkout: switched to trunk", r.stdout.splitlines())


class TestWorkingBranchPushed(WorkingInitCase):
    """Section 34: the branch is pushed to origin (other machines need it)."""

    def test_init_pushes_it(self):
        origin = os.path.join(self.repo.base, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", origin], check=True, capture_output=True)
        self.git("remote", "add", "origin", origin)
        self.init("--no-measure")
        out = subprocess.run(["git", "-C", origin, "branch", "--list", "ap-main-t"], capture_output=True,
                             text=True).stdout
        self.assertIn("ap-main-t", out)


CHANGE = "/plugin -> Installed -> auto-pipeline -> Configure"


class TestInit(ScriptCase):
    script = "agent-init.sh"

    def init(self, *args):
        return self.repo.run("agent-init.sh", self.repo.dir, *args, stdin="")

    def test_init_writes_no_settings_file_and_asks_nothing(self):
        for name in ("agent_todo.txt", "agent_completed.txt", "agent_ideas.txt", "agent_worktree.txt"):
            path = self.repo.path(name)
            if os.path.exists(path):
                os.remove(path)
        r = self.init()
        self.assertOk(r)
        self.assertFalse(os.path.exists(self.repo.path("agent.conf")))
        self.assertFalse(os.path.exists(self.repo.user_conf))
        self.assertFalse(os.path.exists(os.path.join(self.repo.claude_dir(), "settings.json")))
        for name in ("agent_todo.txt", "agent_completed.txt", "agent_ideas.txt", "agent_worktree.txt"):
            self.assertTrue(os.path.exists(self.repo.path(name)), name)
        self.assertNotIn("?", "\n".join(l for l in r.stdout.splitlines() if "auto_update" in l or "language" in l.lower()))
        self.assertIn("settings: " + CHANGE, r.stdout)

    def test_init_moves_an_old_agent_conf(self):
        self.repo.set_old_conf("language=zh\n")
        r = self.init()
        self.assertOk(r)
        self.assertIn("moved language=zh from", r.stdout)


class TestF4AlreadyUsesThePlugin(WorkingInitCase):
    def head(self):
        return self.git("rev-parse", "--abbrev-ref", "HEAD").strip()

    def test_a_clone_of_a_plugin_repo_is_not_switched(self):
        self.assertIn("agent_todo.txt", self.git("ls-files"))              # committed: the repo uses the plugin
        r = self.init("--no-measure")
        self.assertNotEqual(self.head(), "ap-main-t")
        self.assertTrue([l for l in r.stdout.splitlines() if l.startswith("WORKING BRANCH: ")], r.stdout)

    def test_a_new_repo_with_a_local_state_file_is_switched(self):
        tracked = [f for f in self.git("ls-files").split() if f.startswith("agent_")]
        self.git("rm", "-q", "--cached", *tracked)
        self.git("commit", "-q", "-m", "not yet a plugin repo")
        self.put({"agent_state.txt": "ROLE: main manager\n"})              # a local file decides nothing
        self.init("--no-measure")
        self.assertEqual(self.head(), "ap-main-t")


class TestF6RemoteWorkingBranch(WorkingInitCase):
    def origin_with(self, extra_commit):
        origin = os.path.join(self.repo.base, "origin6.git")
        subprocess.run(["git", "init", "-q", "--bare", origin], check=True, capture_output=True)
        self.git("remote", "add", "origin", origin)
        other = tempfile.mkdtemp(prefix="f6_")
        self.addCleanup(subprocess.run, ["rm", "-rf", other])
        self.git("push", "-q", "origin", "HEAD:refs/heads/ap-main-t")
        subprocess.run(["git", "clone", "-q", origin, other], check=True, capture_output=True)
        if extra_commit:
            subprocess.run(["git", "-C", other, "switch", "-q", "ap-main-t"], check=True, capture_output=True)
            with open(os.path.join(other, "theirs.txt"), "w") as fh:
                fh.write("unreleased work\n")
            subprocess.run(["git", "-C", other, "add", "-A"], check=True, capture_output=True)
            subprocess.run(["git", "-C", other, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                            "-m", "unreleased"], check=True, capture_output=True)
            subprocess.run(["git", "-C", other, "push", "-q", "origin", "ap-main-t"], check=True, capture_output=True)
        return origin

    def test_tracks_the_remote_branch(self):
        self.origin_with(extra_commit=True)
        self.git("fetch", "-q", "origin")
        r = self.init("--no-measure")
        self.assertIn("working branch: tracking origin/ap-main-t", r.stdout.splitlines())
        self.assertEqual(self.git("rev-parse", "ap-main-t").strip(), self.git("rev-parse", "origin/ap-main-t").strip())

    def test_a_rejected_push_says_why(self):
        self.origin_with(extra_commit=True)
        self.git("branch", "ap-main-t")                                    # a local branch without their commit
        self.git("switch", "-q", "ap-main-t")
        self.put({"mine.txt": "mine\n"})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "mine")
        r = self.init("--no-measure")
        self.assertIn("working branch: not pushed: the remote has commits this clone does not have "
                      "(fetch and merge origin/ap-main-t first)", r.stdout.splitlines())


ROOT = os.path.dirname(HERE)


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def rule(start, end):
    text = read("PRINCIPLES.md")
    return text[text.index(start):text.index(end)]


class TestF3NoStandingPushToProduction(WorkingInitCase):
    def test_init_names_the_working_branch_never_main(self):
        out = self.init("--no-measure").stdout
        self.assertNotIn("git push origin main", out)
        self.assertNotIn("integration branch", out)
        self.assertIn('allow "Bash(git push origin ap-main-t)"', out)

    def test_w16_and_clean_up(self):
        w16 = rule("W16. ", "W17. ")
        self.assertNotIn("integration branch", w16)
        self.assertIn("working branch", w16)
        cu = read("skills", "clean-up", "SKILL.md")
        self.assertNotIn("git push origin main", cu)
        self.assertIn("push the branch the main checkout is on", cu)


class TestF10DerivedOnlyByInitAndTheStart(unittest.TestCase):
    def setUp(self):
        self.repo = ScriptRepo()
        self.addCleanup(self.repo.cleanup)
        sys.path.insert(0, BIN)
        import agent_conf
        self.ac = agent_conf

    def stored(self):
        return subprocess.run(["git", "-C", self.repo.dir, "config", "--local", "--get", "auto-pipeline.workingbranch"],
                              capture_output=True, text=True).stdout.strip()

    def test_a_reader_stores_nothing(self):
        old = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(old)))
        os.environ.update(self.repo._env(None))
        self.assertIsNone(self.ac.working_branch(self.repo.dir))
        self.assertEqual(self.stored(), "")
        self.assertEqual(self.ac.working_branch(self.repo.dir, derive=True), "ap-main-t")
        self.assertEqual(self.stored(), "ap-main-t")
        self.assertEqual(self.ac.working_branch(self.repo.dir), "ap-main-t")

    def test_an_empty_user_name_takes_the_login_name(self):
        old = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(old)))
        os.environ.update(self.repo._env(None))
        os.environ.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
        subprocess.run(["git", "-C", self.repo.dir, "config", "--local", "--unset", "user.name"], capture_output=True)
        want = re.sub(r"[^a-z0-9-]+", "-", getpass.getuser().lower()).strip("-") or "user"
        self.assertEqual(self.ac.working_branch(self.repo.dir, derive=True), "ap-main-" + want)

    def test_the_gate_with_nothing_stored_says_so(self):
        c = tcr.TestGate("test_the_check_deputy_is_no_builder")
        c.setUp()
        self.addCleanup(c.tearDown)
        c.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        c.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "read it")
        subprocess.run(["git", "-C", c.repo.dir, "config", "--local", "--unset", "auto-pipeline.workingbranch"],
                       capture_output=True)
        r = c.af("checks", "gate", "t", "--dir", c.repo.dir)       # no --base: the default base is worked out
        self.assertIn("note: no working branch stored in this clone: give --base origin/<working branch> "
                      "(the brief names it)", r.stdout.splitlines())
        r = c.gate()                                                    # --base given (the brief named it): no note
        self.assertNotIn("no working branch stored", r.stdout)

    def test_promote_with_nothing_stored_is_refused(self):
        r = self.repo.run("agent-promote.sh", "--sync")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no working branch stored in this clone: run agent-init.sh or start the main manager here",
                      r.stdout + r.stderr)


class TestP4P5P8Init(WorkingInitCase):
    def head(self):
        return self.git("rev-parse", "--abbrev-ref", "HEAD").strip()

    def test_p4_a_repo_that_uses_the_plugin_is_not_switched(self):
        self.put({"agent_state.txt": "ROLE: main manager\n"})
        r = self.init("--no-measure")
        self.assertNotEqual(self.head(), "ap-main-t")
        self.assertTrue([l for l in r.stdout.splitlines() if l.startswith("WORKING BRANCH: ")
                         and "at a quiet point" in l], r.stdout)

    def test_p5_no_branch_step(self):
        r = self.init("--no-measure", "--no-branch")
        self.assertFalse([l for l in r.stdout.splitlines() if l.startswith(("working branch:", "checkout:"))])
        self.assertEqual(self.git("branch", "--list", "ap-main-t").strip(), "")

    def test_p5_the_start_and_cloud_pack_pass_it(self):
        self.assertIn('agent-init.sh" --no-measure --no-branch', read("bin", "agent-start.sh"))
        self.assertIn("--no-branch", read("bin", "agent-cloud-pack.sh"))

    def test_p8_a_failed_push_says_so(self):
        self.git("remote", "add", "origin", os.path.join(self.repo.base, "nowhere.git"))
        r = self.init("--no-measure")
        self.assertTrue([l for l in r.stdout.splitlines() if l.startswith("working branch: not pushed: ")], r.stdout)


class TestG2NoBranchStoresNothing(WorkingInitCase):
    def test_init_no_branch(self):
        r = self.init("--no-measure", "--no-branch")
        stored = subprocess.run(["git", "-C", self.p, "config", "--local", "--get", "auto-pipeline.workingbranch"],
                                capture_output=True, text=True).stdout.strip()
        self.assertEqual(stored, "", "--no-branch stores no name")
        self.assertIn('allow "Bash(git push origin <your working branch>)"', r.stdout)

    def test_the_read_only_cli(self):
        cli = [sys.executable, os.path.join(self.repo.plugin, "bin", "agent_conf.py"), "stored-working-branch", self.p]
        r = subprocess.run(cli, capture_output=True, text=True, env=self.repo._env(None))
        self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))
        subprocess.run(["git", "-C", self.p, "config", "--local", "auto-pipeline.workingbranch", "ap-main-x"], check=True)
        r = subprocess.run(cli, capture_output=True, text=True, env=self.repo._env(None))
        self.assertEqual(r.stdout.strip(), "ap-main-x")


SKIP_KEY = '"skipDangerousModePermissionPrompt": true'


WARN = "new panes stop on the bypass warning screen"


class SkipWarningCase(ScriptCase):
    def setUp(self):
        self.repo = ScriptRepo(init_project=False)
        self.addCleanup(self.repo.cleanup)
        self.project = self.repo.dir
        self.repo.git_init(self.project)
        self.home = self.repo.fake_home()

    def init(self, *args, **kw):
        return self.repo.run("agent-init.sh", *args, **kw)

    def settings(self, data=None, raw=None):
        os.makedirs(os.path.join(self.home, ".claude"), exist_ok=True)
        path = os.path.join(self.home, ".claude", "settings.json")
        with open(path, "w") as fh:
            fh.write(raw if raw is not None else json.dumps(data, indent=2) + "\n")
        return path

    def warn_lines(self, out):
        return [l for l in out.splitlines() if WARN in l]

    def tty(self, answer, *args):
        """Run agent-init.sh with stdin a terminal; ANSWER is typed into it."""
        master, slave = pty.openpty()
        try:
            proc = subprocess.Popen([self.repo.script_path("agent-init.sh")] + list(args), cwd=self.project,
                                    env=self.repo._env(None), stdin=slave, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            os.close(slave)
            slave = None
            if answer is not None:
                # Questions in order: permission mode, auto update, add permissions.
                # ANSWER is the first; Enter (the default) is typed for the later ones
                # so a terminal run never waits on a prompt this test does not script.
                os.write(master, (answer + "\n\n\n").encode())
            out, err = proc.communicate(timeout=60)
        finally:
            if slave is not None:
                os.close(slave)
            os.close(master)
        return proc.returncode, out, err


class TestSkipWarning(SkipWarningCase):
    def assertOneWarning(self, out):
        lines = self.warn_lines(out)
        self.assertEqual(len(lines), 1, out)
        self.assertTrue(lines[0].rstrip().endswith(SKIP_KEY), lines[0])
        self.assertIn("~/.claude/settings.json", lines[0])
        self.assertNotIn("{", lines[0])
        self.assertNotIn("}", lines[0])

    def assertBlockStillParses(self, out):
        block = json.loads(out[out.index("{"):out.rindex("}") + 1])
        self.assertIn("permissions", block)

    def bypass(self):
        self.repo.set_conf("permission_mode", "bypassPermissions")

    def test_no_settings_file(self):
        self.bypass()
        out = self.assertOk(self.init())
        self.assertOneWarning(out)
        self.assertBlockStillParses(out)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude", "settings.json.bak-auto-pipeline")))

    def test_the_default_bypass_warns_too(self):
        # owner order 2026-11-25: the default is bypassPermissions, so init warns about the skip key
        self.assertOneWarning(self.assertOk(self.init()))

    def test_the_key_set_is_quiet(self):
        path = self.settings({"skipDangerousModePermissionPrompt": True, "theme": "dark"})
        self.bypass()
        before = open(path, "rb").read()
        out = self.assertOk(self.init())
        self.assertEqual(self.warn_lines(out), [])
        self.assertEqual(open(path, "rb").read(), before)

    def test_the_key_false_or_missing_warns_and_the_file_stays(self):
        for i, data in enumerate(({"skipDangerousModePermissionPrompt": False},
                                  {"skipDangerousModePermissionPrompt": "true"},
                                  {"permissions": {"allow": []}})):
            with self.subTest(data=data):
                path = self.settings(data)
                self.bypass()
                before = open(path, "rb").read()
                out = self.assertOk(self.init())
                self.assertOneWarning(out)
                self.assertEqual(open(path, "rb").read(), before, "never writes the user's settings file")

    def test_broken_json_warns(self):
        # a broken settings.json: the setting reads as its default (bypassPermissions), so it warns
        path = self.settings(raw="{not json")
        out = self.assertOk(self.init())
        self.assertOneWarning(out)
        self.assertEqual(open(path).read(), "{not json")

    def test_auto_is_quiet(self):
        self.repo.set_conf("permission_mode", "auto")
        out = self.assertOk(self.init())
        self.assertEqual(self.warn_lines(out), [])
        self.assertNotIn("skipDangerousModePermissionPrompt", out)

    def test_the_script_never_writes_home_settings(self):
        src = read("bin", "agent-init.sh")
        for bad in ("> \"$HOME/.claude", ">> \"$HOME/.claude", ">\"$HOME/.claude", "~/.claude/settings.json\" <<"):
            self.assertNotIn(bad, src)


