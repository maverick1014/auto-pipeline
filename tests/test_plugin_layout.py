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
  - The repo's own .claude/settings.json keeps its six Bash permission rules (a
    plugin cannot add permissions) and does NOT repeat the SessionStart hook:
    the installed plugin already runs it, and two copies fire it twice.
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

# Scripts a human or a hook runs. These must carry the execute bit.
SHELL_SCRIPTS = [
    "agent-start.sh",
    "agent-file.sh",
    "agent-settings.sh",
    "agent-resume.sh",
    "agent-monitor.sh",
    "agent-init.sh",
    "agent-runtime.sh",
    "agent-cloud-pack.sh",
]
# Sourced only, never run. agent-runtime.sh is in the list above instead,
# because it is both: sourced by its callers and run by a skill.
SOURCED_ONLY = [
    "agent-roots.sh",
    "agent-resources.sh",
]
BIN_FILES = SHELL_SCRIPTS + SOURCED_ONLY + ["agent_conf.py", "agent.conf.default"]

AGENT_FILES = ["fast-lane-deputy.md", "merge-deputy.md", "worker.md"]
SKILL_DIRS = ["dispatch", "merge", "init", "cloud-pack"]

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

    def test_a_sourced_file_is_not_advertised_as_runnable(self):
        """agent-roots.sh and agent-resources.sh say so in their own header."""
        for name in SOURCED_ONLY:
            with self.subTest(name=name):
                with open(os.path.join(ROOT, "bin", name)) as fh:
                    head = "".join(fh.readlines()[:6]).lower()
                self.assertIn("sourced", head)

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
        # The number is the releaser's call, so only the shape is pinned here.
        self.assertRegex(data["version"], r"^\d+\.\d+\.\d+$")


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
    """The repo still works on itself, with no install.

    The installed plugin already runs the SessionStart hook from
    hooks/hooks.json. A second copy in the repo's own settings.json would fire
    it twice, so the repo must not carry one.
    """

    def settings(self):
        return load_json(".claude", "settings.json")

    def test_the_repo_does_not_duplicate_the_session_start_hook(self):
        self.assertEqual(self.settings().get("hooks", {}).get("SessionStart"),
                         None)

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


class TestPrinciplesS8(unittest.TestCase):
    """S8 clears instead of restarting."""

    def s8(self):
        text = read("PRINCIPLES.md")
        start = text.index("S8.")
        end = text.index("S9.")
        return text[start:end]

    def test_it_mentions_clear(self):
        self.assertIn("/clear", self.s8())


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


class TestCloudPackSkill(unittest.TestCase):
    """/auto-pipeline:cloud-pack does for a local plugin user what the
    one-sentence install does in a cloud session."""

    def text(self):
        return read("skills", "cloud-pack", "SKILL.md")

    def test_it_runs_the_pack_script_from_the_plugin_root(self):
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-cloud-pack.sh",
                      self.text())

    def test_it_passes_the_language(self):
        self.assertIn("--language", self.text())

    def test_it_knows_the_update_flag(self):
        self.assertIn("--update", self.text())

    def test_it_shows_the_output_unchanged(self):
        self.assertIn("unchanged", self.text().lower())


class TestReadmeShowsThePack(unittest.TestCase):
    def test_it_names_the_script(self):
        self.assertIn("bin/agent-cloud-pack.sh", read("README.md"))

    def test_it_shows_where_the_pack_lands(self):
        self.assertIn(".claude/auto-pipeline/", read("README.md"))

    def test_it_gives_the_one_sentence_install(self):
        self.assertIn(
            "git clone https://github.com/maverick1014/auto-pipeline /tmp/ap"
            " && /tmp/ap/bin/agent-cloud-pack.sh .", read("README.md"))

    def test_it_names_the_github_app(self):
        self.assertIn("Claude GitHub App", read("README.md"))


class TestUserConfig(unittest.TestCase):
    """Claude Code asks these three at enable time, so setup needs no editing.

    Values reach a hook as CLAUDE_PLUGIN_OPTION_<KEY uppercased>.
    """

    KEYS = {"runtime": "string", "language": "string", "max_agents": "number"}
    DEFAULTS = {"runtime": "auto", "language": "en", "max_agents": 4}

    def config(self):
        return load_json(".claude-plugin", "plugin.json")["userConfig"]

    def test_the_three_keys_are_there(self):
        self.assertEqual(sorted(self.config()), sorted(self.KEYS))

    def test_each_key_has_its_type(self):
        config = self.config()
        for key, kind in self.KEYS.items():
            with self.subTest(key=key):
                self.assertEqual(config[key]["type"], kind)

    def test_each_key_has_a_title_and_a_description(self):
        config = self.config()
        for key in self.KEYS:
            with self.subTest(key=key):
                self.assertTrue(config[key]["title"].strip())
                self.assertTrue(config[key]["description"].strip())

    def test_each_key_has_its_default(self):
        config = self.config()
        for key, value in self.DEFAULTS.items():
            with self.subTest(key=key):
                self.assertEqual(config[key]["default"], value)

    def test_runtime_offers_the_four_choices(self):
        self.assertEqual(self.config()["runtime"]["options"],
                         ["auto", "orca", "plain", "cloud"])

    def test_nothing_here_is_a_secret(self):
        for key, entry in self.config().items():
            with self.subTest(key=key):
                self.assertFalse(entry.get("sensitive", False))

    def test_max_agents_keeps_the_same_bounds_as_agent_conf(self):
        entry = self.config()["max_agents"]
        self.assertEqual((entry["min"], entry["max"]), (1, 16))


class TestRuntimeReachesEveryCaller(unittest.TestCase):
    """No skill or agent may call orca without going through the runtime."""

    RUNTIME = "${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh"

    def markdown_files(self):
        out = []
        for folder in ("agents", "skills"):
            for dirpath, _, names in os.walk(os.path.join(ROOT, folder)):
                out += [os.path.join(dirpath, n) for n in names
                        if n.endswith(".md")]
        return out

    def test_every_file_that_says_orca_also_asks_the_runtime(self):
        for path in self.markdown_files():
            with open(path) as fh:
                text = fh.read()
            if "orca " not in text:
                continue
            with self.subTest(path=os.path.relpath(path, ROOT)):
                self.assertIn("agent-runtime.sh", text,
                              "calls orca straight out, with no plain branch")

    def test_dispatch_step_seven_asks_the_runtime_first(self):
        text = read("skills", "dispatch", "SKILL.md")
        self.assertIn(self.RUNTIME + " kind", text)

    def test_dispatch_has_a_branch_without_terminals(self):
        text = read("skills", "dispatch", "SKILL.md").lower()
        self.assertIn("plain", text)
        self.assertIn("cloud", text)
        self.assertIn("agent", text)

    def test_the_merge_deputy_closes_through_the_runtime(self):
        text = read("agents", "merge-deputy.md")
        self.assertIn(self.RUNTIME + " close", text)

    def test_the_merge_deputy_has_a_branch_without_terminals(self):
        text = read("agents", "merge-deputy.md").lower()
        self.assertIn("plain", text)


class TestMergeSkillBrowserBranches(unittest.TestCase):
    """Step 2 may never pass a click path nobody drove."""

    def text(self):
        return read("skills", "merge", "SKILL.md")

    def test_it_asks_the_runtime_which_browser(self):
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh browser",
                      self.text())

    def test_all_three_answers_get_a_branch(self):
        text = self.text()
        for answer in ("chrome", "headless", "none"):
            with self.subTest(answer=answer):
                self.assertIn(answer, text)

    def test_chrome_still_means_claude_in_chrome(self):
        self.assertIn("Claude in Chrome", self.text())

    def test_headless_means_playwright_with_a_screenshot_each_step(self):
        text = self.text().lower()
        self.assertIn("playwright", text)
        self.assertIn("screenshot", text)

    def test_none_stops_and_asks_the_human(self):
        self.assertIn("NEEDS HUMAN E2E", self.text())

    def test_it_forbids_calling_an_undriven_path_verified(self):
        self.assertIn("verified", self.text().lower())


class TestInitSkillTellsTheHumanWhatOnlyHeCanDo(unittest.TestCase):
    def text(self):
        return read("skills", "init", "SKILL.md")

    def test_it_keeps_the_permission_sentence(self):
        lowered = self.text().lower()
        self.assertIn("cannot add permission", lowered)

    def test_it_says_a_cloud_session_has_no_plugin_command(self):
        lowered = self.text().lower()
        self.assertIn("/plugin", lowered)
        self.assertIn("cloud", lowered)
        self.assertIn(".claude/settings.json", lowered)


class TestPrinciplesRuntimeShape(unittest.TestCase):
    """W5 and W7 stop assuming Orca and a second terminal."""

    def rule(self, name, nxt):
        text = read("PRINCIPLES.md")
        return text[text.index(name):text.index(nxt)]

    def w5(self):
        return self.rule("W5.", "W6.")

    def w7(self):
        return self.rule("W7.", "W8.")

    def test_w5_keeps_claude_in_chrome_for_a_local_machine(self):
        self.assertIn("Claude in Chrome", self.w5())

    def test_w5_names_the_runtime_check(self):
        self.assertIn("agent-runtime.sh browser", self.w5())

    def test_w5_names_all_three_browser_answers(self):
        block = self.w5()
        for answer in ("chrome", "headless", "none"):
            with self.subTest(answer=answer):
                self.assertIn(answer, block)

    def test_w5_sends_the_cloud_to_headless_playwright(self):
        block = self.w5().lower()
        self.assertIn("cloud", block)
        self.assertIn("playwright", block)

    def test_w5_forbids_writing_verified_without_driving_it(self):
        self.assertIn("NEEDS HUMAN E2E", self.w5())

    def test_w7_says_a_worktree_needs_orca(self):
        block = self.w7().lower()
        self.assertIn("orca", block)

    def test_w7_gives_the_shape_without_terminals(self):
        block = self.w7().lower()
        self.assertIn("plain", block)
        self.assertIn("cloud", block)

    def test_w7_says_subagents_do_the_work_there(self):
        self.assertIn("Agent", self.w7())

    def test_no_new_doc_file_was_added(self):
        """R3 allows requirement, test and main idea docs. Nothing else."""
        allowed = {"PRINCIPLES.md", "README.md", "CLAUDE.md", "AGENTS.md"}
        found = {n for n in os.listdir(ROOT) if n.endswith(".md")}
        self.assertEqual(found - allowed, set())


class TestPrinciplesW12CrossRepo(unittest.TestCase):
    """W12 lets main managers pass work to each other, called side first."""

    def w12(self):
        text = read("PRINCIPLES.md")
        start = text.index("W12.")
        end = text.index("## C. Human")
        return text[start:end]

    def test_w12_exists_after_w11(self):
        text = read("PRINCIPLES.md")
        self.assertIn("W11.", text)
        self.assertIn("W12. Cross-repo", text)
        self.assertLess(text.index("W11."), text.index("W12."))

    def test_w12_names_called_side_first(self):
        self.assertIn("Called side first", self.w12())

    def test_w12_names_send_message(self):
        self.assertIn("SendMessage", self.w12())

    def test_dispatch_skill_mentions_w12(self):
        text = read("skills", "dispatch", "SKILL.md")
        self.assertIn("W12", text)

    def test_dispatch_skill_has_a_cross_repo_brief_template(self):
        text = read("skills", "dispatch", "SKILL.md")
        self.assertIn("Cross-repo brief", text)
        self.assertIn("CROSS-REPO TASK <name> from <repo>", text)

    def test_readme_names_w12_in_routing(self):
        text = read("README.md")
        start = text.index("How a task is routed")
        end = text.index("## One real day")
        self.assertIn("W12", text[start:end])


class TestPrinciplesS4NamesRelief(unittest.TestCase):
    """S4 (usage cap) must tell an over-cap agent to run relief first."""

    def s4(self):
        text = read("PRINCIPLES.md")
        start = text.index("S4.")
        end = text.index("S5.")
        return text[start:end]

    def test_s4_mentions_relief(self):
        self.assertIn("relief", self.s4())


if __name__ == "__main__":
    unittest.main()
