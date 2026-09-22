"""Failing tests for the plugin layout. Written by the task manager, before any code.

CONTRACT. The repo root IS the plugin. After the move it looks like this:

    .claude-plugin/plugin.json        name auto-pipeline, description, version
    .claude-plugin/marketplace.json   this repo as its own marketplace, source "./"
    hooks/hooks.json                  SessionStart -> ${CLAUDE_PLUGIN_ROOT}/bin/agent-start.sh
    agents/<name>.md                  was .claude/agents/<name>.md
    skills/<name>/SKILL.md            was .claude/skills/<name>/SKILL.md, adds init
    bin/agent-*.sh, bin/agent_conf.py was ./agent-*.sh, ./agent_conf.py
    bin/agent.conf.default            the template agent-init.sh copies into a project
    PRINCIPLES.md, README.md          stay at the root

  - Nothing named agent-*.sh is left at the root, and .claude/agents and
    .claude/skills are gone.
  - The repo's own .claude/settings.json keeps a SessionStart hook pointing at
    ./bin/agent-start.sh, so the repo works on itself without installing, and
    keeps its six Bash permission rules (a plugin cannot add permissions).
  - Every skill and agent file names scripts as ${CLAUDE_PLUGIN_ROOT}/bin/...,
    never ./agent-*.sh.
  - CLAUDE.md and AGENTS.md at the root point at ./bin/agent-start.sh.
"""

import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SHELL_SCRIPTS = [
    "agent-start.sh",
    "agent-file.sh",
    "agent-settings.sh",
    "agent-resume.sh",
    "agent-monitor.sh",
    "agent-resources.sh",
    "agent-init.sh",
]
BIN_FILES = SHELL_SCRIPTS + ["agent_conf.py", "agent.conf.default"]

AGENT_FILES = ["fast-lane-deputy.md", "merge-deputy.md", "worker.md"]
SKILL_DIRS = ["dispatch", "merge", "init"]

ALLOW_RULES = [
    "Bash(git push origin --delete *)",
    "Bash(git branch -d *)",
    "Bash(git worktree remove *)",
    "Bash(git worktree prune)",
    "Bash(orca worktree rm *)",
    "Bash(orca terminal close *)",
]


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def load_json(*parts):
    return json.loads(read(*parts))


def frontmatter(text):
    """Parse the --- block at the top of a SKILL.md or agent .md file."""
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    out = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


class TestBin(unittest.TestCase):
    def test_every_script_moved_into_bin(self):
        for name in BIN_FILES:
            with self.subTest(name=name):
                self.assertTrue(os.path.exists(os.path.join(ROOT, "bin", name)),
                                "bin/%s is missing" % name)

    def test_the_shell_scripts_are_executable(self):
        for name in SHELL_SCRIPTS:
            with self.subTest(name=name):
                self.assertTrue(os.access(os.path.join(ROOT, "bin", name), os.X_OK),
                                "bin/%s is not executable" % name)

    def test_nothing_is_left_at_the_root(self):
        left = [n for n in os.listdir(ROOT)
                if n.startswith("agent-") and n.endswith(".sh")]
        self.assertEqual(left, [], "these should have moved into bin/")

    def test_agent_conf_py_is_not_at_the_root(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "agent_conf.py")))


class TestPluginFolders(unittest.TestCase):
    def test_agents_moved(self):
        for name in AGENT_FILES:
            with self.subTest(name=name):
                self.assertTrue(os.path.exists(os.path.join(ROOT, "agents", name)),
                                "agents/%s is missing" % name)

    def test_skills_moved_and_init_added(self):
        for name in SKILL_DIRS:
            with self.subTest(name=name):
                self.assertTrue(
                    os.path.exists(os.path.join(ROOT, "skills", name, "SKILL.md")),
                    "skills/%s/SKILL.md is missing" % name)

    def test_the_old_claude_folders_are_gone(self):
        for old in (".claude/agents", ".claude/skills"):
            with self.subTest(old=old):
                self.assertFalse(os.path.exists(os.path.join(ROOT, old)),
                                 "%s should have moved" % old)

    def test_principles_and_readme_stay_at_the_root(self):
        for name in ("PRINCIPLES.md", "README.md"):
            with self.subTest(name=name):
                self.assertTrue(os.path.exists(os.path.join(ROOT, name)))


class TestPluginManifest(unittest.TestCase):
    def test_it_is_valid_json(self):
        self.assertIsInstance(load_json(".claude-plugin", "plugin.json"), dict)

    def test_required_and_chosen_fields(self):
        data = load_json(".claude-plugin", "plugin.json")
        self.assertEqual(data["name"], "auto-pipeline")
        self.assertTrue(data["description"].strip())
        self.assertEqual(data["version"], "0.1.0")


class TestMarketplaceManifest(unittest.TestCase):
    def test_it_is_valid_json(self):
        self.assertIsInstance(load_json(".claude-plugin", "marketplace.json"), dict)

    def test_required_fields(self):
        data = load_json(".claude-plugin", "marketplace.json")
        self.assertTrue(data["name"].strip())
        self.assertTrue(data["owner"]["name"].strip())
        self.assertTrue(data["plugins"])

    def test_it_lists_this_repo_as_the_plugin(self):
        data = load_json(".claude-plugin", "marketplace.json")
        entry = [p for p in data["plugins"] if p.get("name") == "auto-pipeline"]
        self.assertEqual(len(entry), 1, "auto-pipeline is not listed once")
        self.assertEqual(entry[0]["source"], "./")


class TestHooksJson(unittest.TestCase):
    def command(self):
        data = load_json("hooks", "hooks.json")
        entries = data["hooks"]["SessionStart"]
        self.assertEqual(len(entries), 1, entries)
        hooks = entries[0]["hooks"]
        self.assertEqual(len(hooks), 1, hooks)
        self.assertEqual(hooks[0]["type"], "command")
        return hooks[0]["command"]

    def test_it_is_valid_json(self):
        self.assertIsInstance(load_json("hooks", "hooks.json"), dict)

    def test_session_start_runs_agent_start_from_the_plugin_root(self):
        command = self.command()
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", command)
        self.assertTrue(command.replace('"', "").endswith("/bin/agent-start.sh"),
                        command)

    def test_the_variable_is_spelled_exactly(self):
        command = self.command()
        self.assertNotIn("$CLAUDE_PLUGIN_ROOT/", command,
                         "use ${CLAUDE_PLUGIN_ROOT}, with the braces")


class TestRepoSettings(unittest.TestCase):
    """The repo still works on itself, with no install."""

    def settings(self):
        return load_json(".claude", "settings.json")

    def test_session_start_points_at_the_local_bin(self):
        hooks = self.settings()["hooks"]["SessionStart"][0]["hooks"]
        self.assertEqual(hooks[0]["command"], "./bin/agent-start.sh")

    def test_the_six_permission_rules_are_still_there(self):
        allow = self.settings()["permissions"]["allow"]
        for rule in ALLOW_RULES:
            with self.subTest(rule=rule):
                self.assertIn(rule, allow)


class TestEntryFiles(unittest.TestCase):
    def test_claude_md_points_at_bin(self):
        self.assertIn("./bin/agent-start.sh", read("CLAUDE.md"))

    def test_agents_md_points_at_bin(self):
        self.assertIn("./bin/agent-start.sh", read("AGENTS.md"))

    def test_they_are_still_one_line(self):
        for name in ("CLAUDE.md", "AGENTS.md"):
            with self.subTest(name=name):
                self.assertLessEqual(len(read(name).strip().splitlines()), 2)


class TestNoOldPathsLeft(unittest.TestCase):
    """A skill or agent that still says ./agent-file.sh breaks in any other repo."""

    def files(self):
        out = []
        for folder in ("agents", "skills"):
            for dirpath, _, names in os.walk(os.path.join(ROOT, folder)):
                out += [os.path.join(dirpath, n) for n in names if n.endswith(".md")]
        return out

    def test_no_dot_slash_script_calls(self):
        for path in self.files():
            with self.subTest(path=os.path.relpath(path, ROOT)):
                with open(path) as fh:
                    text = fh.read()
                self.assertNotRegex(text, r"(?<!\S)\./agent-[a-z]+\.sh",
                                    "still calls a script by ./, needs "
                                    "${CLAUDE_PLUGIN_ROOT}/bin/")

    def test_script_calls_use_the_plugin_root(self):
        found = False
        for path in self.files():
            with open(path) as fh:
                if "${CLAUDE_PLUGIN_ROOT}/bin/" in fh.read():
                    found = True
        self.assertTrue(found, "no skill or agent names ${CLAUDE_PLUGIN_ROOT}/bin/")


class TestSkillFrontmatter(unittest.TestCase):
    def test_name_matches_the_folder(self):
        for name in SKILL_DIRS:
            with self.subTest(name=name):
                data = frontmatter(read("skills", name, "SKILL.md"))
                self.assertEqual(data.get("name"), name)
                self.assertTrue(data.get("description", "").strip())


class TestInitSkill(unittest.TestCase):
    def test_it_runs_agent_init(self):
        text = read("skills", "init", "SKILL.md")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-init.sh", text)


class TestPrinciplesR3(unittest.TestCase):
    """R3 lists the plugin folders now, not the old .claude paths."""

    def r3(self):
        text = read("PRINCIPLES.md")
        start = text.index("R3.")
        end = text.index("R4.")
        return text[start:end]

    def test_it_names_every_plugin_folder(self):
        block = self.r3()
        for folder in (".claude-plugin/", "agents/", "skills/", "hooks/", "bin/"):
            with self.subTest(folder=folder):
                self.assertIn(folder, block)

    def test_the_old_config_line_is_gone(self):
        self.assertNotIn(".claude/agents/*.md", self.r3())

    def test_nothing_else_moved(self):
        text = read("PRINCIPLES.md")
        for rule in ("R1.", "R2.", "R4.", "R5.", "R6.", "R7.", "W10.", "S9."):
            with self.subTest(rule=rule):
                self.assertIn(rule, text)


class TestEffortIsAlwaysPassed(unittest.TestCase):
    """Every launch of a claude session names the effort, read from agent.conf.

    `claude --effort` takes low, medium, high, xhigh, max. Nothing is
    hard-coded: the dispatch skill reads task_manager, the W10 line in
    PRINCIPLES.md reads main_manager.
    """

    def dispatch(self):
        return read("skills", "dispatch", "SKILL.md")

    def w10(self):
        text = read("PRINCIPLES.md")
        return text[text.index("W10."):text.index("## C. Human")]

    def test_the_dispatch_launch_line_passes_effort(self):
        text = self.dispatch()
        self.assertIn("--effort", text)
        self.assertIn("--model", text)
        self.assertIn("--permission-mode", text)

    def test_the_dispatch_effort_comes_from_the_task_manager_key(self):
        self.assertIn("task_manager", self.dispatch())

    def test_the_w10_second_session_line_passes_effort(self):
        self.assertIn("--effort", self.w10())

    def test_the_w10_effort_comes_from_the_main_manager_key(self):
        self.assertIn("main_manager", self.w10())

    def test_no_launch_line_hard_codes_a_model_and_effort_pair(self):
        """opus-5:xhigh belongs in agent.conf, never in a launch line."""
        for text in (self.dispatch(), self.w10()):
            with self.subTest():
                self.assertNotIn(":xhigh", text)


class TestReadmeInstall(unittest.TestCase):
    def test_there_is_an_install_section(self):
        self.assertIn("## Install", read("README.md"))

    def test_it_gives_the_three_commands(self):
        text = read("README.md")
        self.assertIn("/plugin marketplace add maverick1014/auto-pipeline", text)
        self.assertIn("/plugin install auto-pipeline", text)
        self.assertIn("/auto-pipeline:init", text)

    def test_it_says_to_paste_the_allow_block(self):
        text = read("README.md")
        self.assertIn("permission", text.lower())
        self.assertIn(ALLOW_RULES[0], text)

    def test_the_tree_shows_the_new_paths(self):
        text = read("README.md")
        self.assertIn("bin/agent-start.sh", text)


if __name__ == "__main__":
    unittest.main()
