"""Tests of Rule text pins: PRINCIPLES.md, skills, agents, hooks.json, README. Each class pins one
rule or skill for one feature; a pin lives in one place only.

One class per feature. Older task contracts: git log -p of this file.
"""

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from scripthelp import ROOT  # noqa: E402
from scripthelp import ROOT, ScriptCase  # noqa: E402
import subprocess
import shutil
import stat
import tempfile
from scripthelp import BIN  # noqa: E402


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def section(text, start, end):
    """The text from the line starting with `start` up to the line starting with `end`."""
    lines = text.splitlines()
    begin = next(i for i, line in enumerate(lines) if line.startswith(start))
    stop = next(i for i in range(begin + 1, len(lines)) if lines[i].startswith(end))
    return "\n".join(lines[begin:stop])


class TestPrinciplesW6Names(unittest.TestCase):

    def setUp(self):
        self.text = read("PRINCIPLES.md")

    def naming_lines(self):
        return [line for line in self.text.splitlines()
                if "<repo> Manager" in line and "<feature> Task Manager" in line]

    def test_one_naming_rule(self):
        self.assertEqual(len(self.naming_lines()), 1, self.naming_lines())

    def test_the_rule_names_every_role(self):
        line = self.naming_lines()[0]
        for word in ("<repo> Manager", "<feature> Task Manager", "<repo> Helper",
                     "<feature> Worker <n>", "Deputy", "Merge", "bin/agent-name.sh"):
            with self.subTest(word=word):
                self.assertIn(word, line)

    def test_the_rule_is_short(self):
        self.assertLessEqual(len(self.naming_lines()[0]), 320)

    def test_the_rule_shows_the_helper_task(self):
        self.assertIn("<repo> Helper - <Task Name>", self.naming_lines()[0])

    def test_one_helper_task_rule(self):
        lines = [l for l in self.text.splitlines() if "helper-task" in l]
        self.assertEqual(len(lines), 1, lines)
        line = lines[0]
        for word in ('helper-task "<Task Name>"', "<repo> Helper - <Task Name>",
                     "2-4 English words", "Title Case",
                     "next prompt", "the work, not the role", "full-path", "alone",
                     "project folder", "never cd", "never chain",
                     "a plain question too", "before the quiz PASS"):
            with self.subTest(word=word):
                self.assertIn(word, line)
        self.assertLessEqual(len(line), 400)

    def test_the_rule_says_when_the_name_is_the_address(self):
        line = self.naming_lines()[0]
        for word in ("--name", "/rename", "resume"):
            with self.subTest(word=word):
                self.assertIn(word, line)

    def talk_line(self):
        return next(l for l in self.text.splitlines()
                    if l.startswith("- Talk between sessions"))

    def test_talk_between_sessions_handles_a_shared_name(self):
        self.assertIn("[ref]", self.talk_line())

    def test_talk_between_sessions_falls_back_to_the_folder_row(self):
        self.assertIn("<folder>-<xx>", self.talk_line())

    def test_the_second_session_is_opened_with_its_name(self):
        line = next(l for l in self.text.splitlines()
                    if l.startswith("- Open a second session"))
        self.assertIn("--name '<repo> Helper'", line)

    def test_cross_repo_peer_is_found_by_manager_name(self):
        w12 = section(self.text, "W12.", "W13.")
        self.assertNotIn("named after the other repo's folder", w12)
        self.assertIn("Manager", w12)
        self.assertIn("-<xx>", w12)


class TestDispatchSkillNames(unittest.TestCase):

    def setUp(self):
        self.text = read("skills", "dispatch", "SKILL.md")

    def test_task_manager_session_gets_its_name(self):
        self.assertRegex(self.text, r"claude --name ['\"]<name> Task Manager['\"]")

    def test_the_orca_tab_gets_the_same_name(self):
        self.assertIn('--title "<name> Task Manager"', self.text)
        self.assertNotIn('"TM <name>"', self.text)

    def test_fast_lane_deputy_name(self):
        step2 = next(l for l in self.text.splitlines() if l.startswith("2. "))
        self.assertIn("<task> Deputy", step2)

    def test_worker_names_in_the_brief(self):
        brief = section(self.text, "## Task manager brief", "## Cross-repo brief")
        step4 = next(l for l in brief.splitlines() if l.startswith(" 4 "))
        self.assertIn("<name> Worker <n>: <slice>", step4)


class TestMergeSkillNames(unittest.TestCase):

    def test_merge_deputy_name(self):
        text = read("skills", "merge", "SKILL.md")
        step4 = next(l for l in text.splitlines() if l.startswith("4. "))
        self.assertIn("<name> Merge", step4)


class TestCloseCaseSkillNames(unittest.TestCase):

    def test_sessions_are_found_by_name(self):
        text = section(read("skills", "close-case", "SKILL.md"), "## B.", "5.")
        self.assertTrue(re.search(r"<(feature|name)> Task Manager", text), text)
        self.assertIn("<repo> Helper", text)
        self.assertIn("<repo>-<xx>", text)

    def test_the_helper_is_found_by_its_task_name(self):
        text = section(read("skills", "close-case", "SKILL.md"), "## B.", "5.")
        self.assertIn("<repo> Helper - <Task Name>", text)


class TestNoOldHelperFormat(unittest.TestCase):
    """Owner change, 2026-10-29: "<repo> Helper - <Task Name>". The old form
    "<repo> Helper <Task Name>" is gone from every rule text and script."""

    FILES = (("PRINCIPLES.md",), ("README.md",), ("skills", "close-case", "SKILL.md"),
             ("bin", "agent-start.sh"), ("bin", "agent-roots.sh"),
             ("bin", "agent-file.sh"), ("bin", "agent-name.sh"))

    def test_no_old_form_left(self):
        for parts in self.FILES:
            with self.subTest(file="/".join(parts)):
                self.assertNotIn("Helper <Task Name>", read(*parts))


NAME_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-name.sh'


NAME_ENTRY = {"hooks": [{"type": "command", "command": NAME_COMMAND, "timeout": 5}]}


PROMPT_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-name.sh --prompt'


PROMPT_ENTRY = {"hooks": [{"type": "command", "command": PROMPT_COMMAND, "timeout": 5}]}


class TestHooksJsonNameHook(unittest.TestCase):

    def test_session_start_runs_both_hooks(self):
        # the city starts by /auto-pipeline:city: no SessionStart entry for it
        entries = json.loads(read("hooks", "hooks.json"))["hooks"]["SessionStart"]
        self.assertEqual(len(entries), 2, entries)
        self.assertIn("/bin/agent-start.sh", json.dumps(entries[0]))
        self.assertEqual(entries[1], NAME_ENTRY)

    def test_the_script_can_run(self):
        path = os.path.join(ROOT, "bin", "agent-name.sh")
        self.assertTrue(os.access(path, os.X_OK), "bin/agent-name.sh has no execute bit")

    def test_readme_names_the_script(self):
        self.assertIn("bin/agent-name.sh", read("PRINCIPLES.md"))


class TestPromptHookJson(unittest.TestCase):

    def test_user_prompt_submit_runs_the_prompt_hook_once(self):
        entries = json.loads(read("hooks", "hooks.json"))["hooks"]["UserPromptSubmit"]
        self.assertEqual(entries.count(PROMPT_ENTRY), 1, entries)
        self.assertIn("agent-close-case.sh", json.dumps(entries))

    def test_no_other_event_runs_the_prompt_mode(self):
        for event, entries in json.loads(read("hooks", "hooks.json"))["hooks"].items():
            if event != "UserPromptSubmit":
                with self.subTest(event=event):
                    self.assertNotIn("--prompt", json.dumps(entries))

    def test_readme_says_it_names_the_helper_task(self):
        line = next(l for l in read("PRINCIPLES.md").splitlines() if l.startswith("  bin/agent-name.sh"))
        self.assertIn("UserPromptSubmit", line)
        self.assertIn("<repo> Helper - <Task Name>", line)


class TestPrinciplesW13Clean(unittest.TestCase):
    def w13(self):
        text = read("PRINCIPLES.md")
        return text[text.index("W13."):text.index("W14.")]

    def s8(self):
        text = read("PRINCIPLES.md")
        return text[text.index("S8."):text.index("S9.")]

    def test_w13_asks_cleans_and_keeps_the_seat(self):
        rule = self.w13()
        for phrase in ("yes or no", "`agent-start.sh --clean`", "`/clear`",
                       "`! agent-start.sh --release`", "never runs it"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)
        self.assertNotIn("Last line of the final table", rule)
        self.assertLess(rule.index("--clean"), rule.index("--release"))

    def test_w13_stays_one_short_line_per_rule(self):
        bullets = [l for l in self.w13().splitlines() if l.startswith("- ")]
        self.assertLessEqual(len(bullets), 14)
        for line in bullets:
            with self.subTest(line=line[:40]):
                self.assertLessEqual(len(line), 200)
        self.assertEqual(len([l for l in bullets if "--release" in l]), 1)
        self.assertEqual(len([l for l in bullets if "--clean" in l]), 1)

    def test_s8_says_the_main_manager_clears_its_own_pane(self):
        # state-trim (2026-11-20): the auto clear line names the own pane too; this is the close case line
        rows = [l for l in self.s8().splitlines() if "own pane" in l and "close case" in l]
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("main manager", rows[0])
        self.assertLessEqual(len(rows[0]), 200)


class TestCloseCaseSkillClean(unittest.TestCase):
    def part_b(self):
        text = read("skills", "close-case", "SKILL.md")
        return text[text.index("## B."):]

    def test_the_question_then_the_clean_then_the_clear(self):
        part = self.part_b()
        for phrase in ("yes or no", "nothing changes",
                       "${CLAUDE_PLUGIN_ROOT}/bin/agent-start.sh --clean", "LEFT RUNNING",
                       "NEXT", "/clear", "own pane", "last action"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, part)
        self.assertLess(part.index("final table"), part.index("yes or no"))
        self.assertLess(part.index("yes or no"), part.index("--clean"))

    def test_release_is_one_line_the_other_choice(self):
        part = self.part_b()
        rows = [line for line in part.splitlines() if "--release" in line]
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("never run it yourself", rows[0])
        self.assertIn("hook", rows[0])
        self.assertLess(part.index("--clean"), part.index("--release"))
        self.assertEqual(rows[0], part.rstrip("\n").splitlines()[-1], "nothing comes after it")

    def test_the_skill_carries_no_release_path(self):
        text = read("skills", "close-case", "SKILL.md")
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-start.sh --release", text)
        self.assertNotIn("Last step: the final table ends with this line", text)


def dispatch_brief():
    """The task manager brief template of the dispatch skill."""
    return section(read("skills", "dispatch", "SKILL.md"),
                   "## Task manager brief", "## Cross-repo brief")


class TestPrinciplesW13CloseCase(unittest.TestCase):
    """PRINCIPLES.md W13, short lines, same style as the other rules."""

    def rule(self):
        return section(read("PRINCIPLES.md"), "W13. Close case", "W14.")

    def test_it_sits_after_w12_in_the_work_section(self):
        text = read("PRINCIPLES.md")
        self.assertLess(text.index("W12. Cross-repo"), text.index("W13. Close case"))
        self.assertLess(text.index("W13. Close case"), text.index("## C. Human"))

    def test_one_short_line_per_rule(self):
        bullets = [l for l in self.rule().splitlines() if l.startswith("- ")]
        self.assertGreaterEqual(len(bullets), 5)
        self.assertLessEqual(len(bullets), 14)   # session-clean: question, clean, release
        for line in bullets:
            with self.subTest(line=line[:40]):
                self.assertLessEqual(len(line), 200)

    def test_it_says_what_the_owner_decided(self):
        rule = self.rule()
        for phrase in ("close case", "/auto-pipeline:close-case",
                       "CLOSE CASE <name>: finished", "CLOSE CASE <name>: unfinished",
                       "WIP", "push", "next steps", "click path", "ideas", "TIME",
                       "finish first", "close now", "owner not seen", "whole repo",
                       "agent_worktree.txt", "table"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)

    def test_the_idea_rule_allows_ideas_in_the_close_case_report(self):
        w1 = section(read("PRINCIPLES.md"), "W1. ", "W2. ")
        self.assertIn("CLOSE CASE", w1)

    def test_the_quiz_still_has_twenty_nine_questions(self):
        text = read("bin", "agent-start.sh")
        # test-levels (2026-11-20): Q38 and Q39 (R8); approval-design: Q40-Q44
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", text)), 36)   # S5 + T4


class TestCloseCaseSkill(unittest.TestCase):
    def test_the_close_case_skill(self):
        text = read("skills", "close-case", "SKILL.md")
        self.assertRegex(text, r"(?m)^name: close-case$")
        self.assertRegex(text, r"(?m)^description: Run when the human or the main manager says close case")
        for phrase in ("finish first", "close now", "owner not seen", "agent_worktree.txt",
                       "${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree rm",
                       "${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add",
                       "${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh close",
                       "CronDelete", "/merge", "final table",
                       "agent_state.txt"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_close_now_keeps_the_branch(self):
        self.assertNotIn("--delete", read("skills", "close-case", "SKILL.md"))

    def test_the_merge_skill_points_at_it(self):
        text = read("skills", "merge", "SKILL.md")
        self.assertIn("CLOSE CASE", text)
        self.assertIn("/close-case", text)

    def test_the_task_manager_brief_mentions_it(self):
        brief = dispatch_brief()
        self.assertIn("close case", brief.lower())
        self.assertIn("CLOSE CASE <name>: finished", brief)
        self.assertIn("CLOSE CASE <name>: unfinished", brief)

    def test_the_readme_names_the_hook_and_the_skill(self):
        text = read("PRINCIPLES.md")
        self.assertIn("agent-close-case.sh", text)
        self.assertIn("close-case", text)


class TestPrinciplesW15Report(unittest.TestCase):
    def w15(self):
        with open(os.path.join(os.path.dirname(HERE), "PRINCIPLES.md")) as fh:
            text = fh.read()
        return text[text.index("W15. Watch"):text.index("W16.")].splitlines()

    def test_the_stage_from_the_newest_heartbeat_line(self):
        hits = [l for l in self.w15() if "HEARTBEAT step" in l and "STAGE line" in l and "main repo" in l]
        self.assertEqual(len(hits), 1, self.w15())
        self.assertLess(len(hits[0]), 200)

    def test_a_manager_waiting_for_its_own_run_is_not_a_stall(self):
        hits = [l for l in self.w15() if "not a stall" in l and "watch_quiet_min" in l and "started" in l]
        self.assertEqual(len(hits), 1, self.w15())
        self.assertLess(len(hits[0]), 200)


class TestPrinciplesW15Watch(unittest.TestCase):
    def test_principles_watch_rule_names_the_script_and_the_report_block(self):
        w15 = section(read("PRINCIPLES.md"), "W15. Watch", "W16.")
        line = next((l for l in w15.splitlines() if "agent-watch.sh" in l), "")
        self.assertTrue(line, "W15 has no agent-watch.sh line")
        for word in ("=== REPORT ===", "agent_state.txt", "background",
                     "another machine"):
            self.assertIn(word, line)

    def test_dispatch_starts_the_watch_after_the_launch_check(self):
        text = read("skills", "dispatch", "SKILL.md")
        steps = section(text, "# /dispatch", "## Board records")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-watch.sh", steps)
        at = steps.index("agent-watch.sh")
        self.assertLess(steps.index("terminal wait"), at)
        near = steps[max(0, at - 300):at + 1200]
        # one-watcher (owner 2026-11-24): one --all watch for every task manager, local and remote, so the
        # dispatch text no longer names --environment/--shell or "until merged" (tests/test_agent_watch.py)
        for word in ("run_in_background", "--all", "again", "MOCK READY"):
            self.assertIn(word, near)
        # SCOPE ADD 1: the screen no longer fires
        block = steps[at:at + 600]
        self.assertNotIn("⏺", block)
        self.assertNotIn("on screen", block)

    def test_dispatch_brief_mock_step_names_mock_ready(self):
        brief = section(read("skills", "dispatch", "SKILL.md"),
                        "## Task manager brief", "## Cross-repo brief")
        mock = next(l for l in brief.splitlines() if l.startswith(" 2 mock"))   # progress-bar: the line now starts with its stage call
        self.assertIn("MOCK READY", mock)
        self.assertIn("agent_state.txt", mock)

    def test_dispatch_brief_names_the_report_block(self):
        brief = section(read("skills", "dispatch", "SKILL.md"),
                        "## Task manager brief", "## Cross-repo brief")
        report = next(l for l in brief.splitlines() if l.startswith("REPORT:"))
        self.assertIn("=== REPORT ===", report)
        self.assertIn("agent_state.txt", report)

    def test_map_names_the_watch_script(self):
        self.assertIn("bin/agent-watch.sh", read("PRINCIPLES.md"))


CHANGE = "/plugin -> Installed -> auto-pipeline -> Configure"


class TestSettingsTexts(unittest.TestCase):
    def test_principles(self):
        text = read("PRINCIPLES.md")
        self.assertNotIn("agent.conf", text)
        self.assertNotIn("auto-pipeline.conf", text)
        self.assertIn(CHANGE, text)
        self.assertRegex(text, r"(?i)settings live only in")
        # owner 1A 2026-11-25: core paths are repo facts in agent_repo.conf, not a setting
        self.assertIn("agent_repo.conf", text)
        self.assertRegex(text, r"(?i)20 settings|twenty settings")   # + Task files in git, Who may take a task, Data branch (agent-files, TELL 3a14d2f4, 50d02f90)

    # test_r8_is_main_s_text (R8 frozen as on main 85b99de) is gone: the owner approved check-blocks on
    # 2026-11-25, R8 is "Check blocks" now (TestPrinciplesR8 pins it)

    def test_readme_has_one_line_where_to_change_settings(self):
        lines = [l for l in read("README.md").splitlines() if CHANGE in l]
        self.assertEqual(len(lines), 1)
        self.assertNotIn("agent.conf", read("README.md"))

    def test_settings_skill(self):
        text = read("skills", "settings", "SKILL.md")
        self.assertIn(CHANGE, text)
        self.assertRegex(text, r"(?i)never changes")
        self.assertNotRegex(text, r"agent-settings\.sh <key> <value>")

    def test_init_skill_asks_no_setting(self):
        text = read("skills", "init", "SKILL.md")
        self.assertNotRegex(text, r"(?i)bypass or all auto|auto update on or off")
        self.assertNotIn("--mode", text)
        self.assertNotIn("--auto-update", text)
        self.assertIn(CHANGE, text)

    def test_plugin_version_is_bumped(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as fh:
            version = json.load(fh)["version"]
        self.assertGreater(tuple(int(x) for x in version.split(".")), (0, 44, 0))


ZSH = shutil.which("zsh")


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


class TestTypedLaunchLines(unittest.TestCase):
    def dispatch(self):
        return read("skills", "dispatch", "SKILL.md")

    def test_the_dispatch_line_quotes_the_model(self):
        lines = [l for l in self.dispatch().splitlines() if "orca terminal create" in l and "claude" in l]
        self.assertTrue(lines, "the dispatch skill has a typed launch line")
        for line in lines:
            with self.subTest(line=line):
                self.assertIn("--model '<model>'", line)

    def test_the_dispatch_model_comes_from_cli_model(self):
        text = self.dispatch()
        self.assertIn("cli-model", text, "<model> is what agent_conf.py cli-model prints, not the raw conf name")

    def cli_model_command(self):
        """The one backticked `... agent_conf.py cli-model ...` command of the dispatch skill."""
        found = re.findall(r"`([^`]*agent_conf\.py cli-model[^`]*)`", self.dispatch())
        self.assertEqual(len(found), 1, found)
        return found[0]

    @unittest.skipUnless(ZSH, "no zsh on PATH")
    def test_the_dispatch_cli_model_command_runs_in_zsh(self):
        """Bounce 1: agent_conf.py has no exec bit and no shebang (needs python3),
        and an unquoted opus-5.5[1m]:xhigh is a zsh glob."""
        command = self.cli_model_command().replace("<task_manager value>", "opus-5.5[1m]:xhigh")
        self.assertNotIn("<", command, command)
        env = dict(os.environ, CLAUDE_PLUGIN_ROOT=ROOT)
        done = subprocess.run([ZSH, "-f", "-c", command], capture_output=True, text=True, env=env,
                              timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual((done.returncode, done.stdout), (0, "opus[1m]\n"), done.stderr)

    @unittest.skipUnless(ZSH, "no zsh on PATH")
    def test_the_dispatch_launch_line_runs_in_zsh(self):
        """The typed --command, its placeholders filled the way the skill says, runs in zsh."""
        line = [l for l in self.dispatch().splitlines() if "orca terminal create" in l and "claude" in l][0]
        inner = re.search(r'--command "([^"]*)"', line).group(1)
        filled = (inner.replace("<name>", "demo").replace("<model>", "opus[1m]")
                  .replace("<effort>", "xhigh").replace("<mode>", "auto"))
        self.assertNotIn("<", filled, filled)
        base = os.path.realpath(tempfile.mkdtemp(prefix="model_suffix_"))
        self.addCleanup(shutil.rmtree, base, True)
        code, out, err = ZshRun(base)(filled)
        self.assertNotIn("no matches found", err)
        self.assertEqual((code, out), (0, ["--name", "demo Task Manager", "--model", "opus[1m]", "--effort", "xhigh",
                                           "--permission-mode", "auto", "ROLE=task-manager"]), err)

    def test_no_unquoted_model_placeholder_anywhere(self):
        files = [os.path.join(ROOT, "PRINCIPLES.md"), os.path.join(ROOT, "README.md")]
        for folder in ("skills", "agents"):
            for top, _dirs, names in os.walk(os.path.join(ROOT, folder)):
                files += [os.path.join(top, n) for n in names if n.endswith(".md")]
        for path in files:
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                for number, line in enumerate(fh, 1):
                    for match in re.finditer(r"--model[ =](\S+)", line):
                        word = match.group(1)
                        if word.startswith("<") or word.startswith("$"):
                            with self.subTest(file=os.path.relpath(path, ROOT), line=number):
                                self.fail("unquoted model word %r: write --model '%s'" % (word, word))


class TestLaunchTextPermission(unittest.TestCase):
    def test_dispatch_reads_the_setting(self):
        text = read("skills", "dispatch", "SKILL.md")
        line = next(l for l in text.splitlines() if "**orca**" in l and "<mode>" in l)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-settings.sh get permission_mode", line)
        self.assertIn("--permission-mode <mode>", text)

    def test_w10_helper_line(self):
        line = next(l for l in read("PRINCIPLES.md").splitlines() if l.startswith("- Open a second session"))
        self.assertIn("agent-settings.sh get permission_mode", line)
        self.assertIn("--permission-mode <mode>", line)

    def test_w10_new_terminals_line(self):
        line = next(l for l in read("PRINCIPLES.md").splitlines() if l.startswith("- New terminals"))
        self.assertIn("Permission mode", line)
        self.assertNotIn(".conf", line)


def text(path):
    with open(path) as fh:
        return fh.read()


class TestReleaseTextAutoUpdate(unittest.TestCase):
    def test_merge_skill_says_bump_the_version(self):
        text = read("skills", "merge", "SKILL.md")
        line = next((l for l in text.splitlines() if ".claude-plugin/plugin.json" in l), None)
        self.assertIsNotNone(line)
        self.assertIn("version", line)
        self.assertIn("release", line.lower())


HOOK_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-version.sh hook'


def section_version(text, start, end):
    lines = text.splitlines()
    begin = next(i for i, l in enumerate(lines) if l.startswith(start))
    stop = next(i for i in range(begin + 1, len(lines)) if lines[i].startswith(end))
    return lines[begin:stop]


class TestHooksJsonVersion(unittest.TestCase):
    def hooks(self):
        return json.loads(read("hooks", "hooks.json"))["hooks"]

    def entries(self, event):
        return [h for e in self.hooks().get(event, []) for h in e.get("hooks", [])
                if "agent-version.sh" in h.get("command", "")]

    def test_user_prompt_submit_runs_it(self):
        found = self.entries("UserPromptSubmit")
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["command"], HOOK_COMMAND)
        self.assertEqual(found[0].get("type"), "command")
        self.assertLessEqual(found[0].get("timeout", 600), 10)

    def test_no_other_event_runs_it(self):
        for event in self.hooks():
            if event != "UserPromptSubmit":
                with self.subTest(event=event):
                    self.assertEqual(self.entries(event), [])


class TestRuleAndReleaseVersion(unittest.TestCase):
    def test_one_w16_line(self):
        lines = [l for l in section_version(read("PRINCIPLES.md"), "W16. ", "W17. ")
                 if l.startswith("- ") and "STALE PLUGIN" in l]
        self.assertEqual(len(lines), 1, "W16: one bullet names STALE PLUGIN")
        line = lines[0]
        for word in ("newest", "brief", "restart", "retrain"):
            self.assertIn(word, line)
        self.assertLessEqual(len(line), 200, line)

    def test_readme_lists_the_script(self):
        self.assertIn("bin/agent-version.sh", read("PRINCIPLES.md"))

    def test_the_script_is_executable(self):
        self.assertTrue(os.access(os.path.join(ROOT, "bin", "agent-version.sh"), os.X_OK))


TIME_LINE = "TIME: est <n>m, actual <n>m, wait <n>m"


DATA_KEYS = ["repo", "type", "lane", "mock", "est", "work", "wait", "clock",
             "bounces", "workers", "files", "lines", "tests", "adds"]


DONE_FACTS = ["--work", "--wait", "--bounces", "--workers", "--mock", "--lane",
              "--type", "--tests", "--adds"]


def text_between(text, start, end):
    """The text from the line that starts with `start` up to `end`."""
    a = text.index(start)
    return text[a:text.index(end, a)]


class TestPrinciplesW11Time(unittest.TestCase):

    def w11(self):
        return text_between(read("PRINCIPLES.md"), "W11. Time", "W12.")

    def test_every_w11_rule_is_one_dash_line(self):
        lines = [l for l in self.w11().splitlines()[1:] if l.strip()]
        self.assertGreaterEqual(len(lines), 6)
        for line in lines:
            with self.subTest(line=line):
                self.assertTrue(line.startswith("- "), line)

    def test_w11_no_rule_line_is_long(self):
        for line in self.w11().splitlines():
            with self.subTest(line=line):
                self.assertLessEqual(len(line), 170, line)

    def test_w11_the_estimate_is_agent_work_only(self):
        self.assertRegex(self.w11().lower(), r"estimate = agent work")

    def test_w11_names_the_waits(self):
        text = self.w11().lower()
        for wait in ("mock gate", "owner question", "review", "hold", "suite run"):   # check-blocks section 39 (a): no slots
            with self.subTest(wait=wait):
                self.assertIn(wait, text)

    def test_w11_has_the_new_time_line(self):
        self.assertIn(TIME_LINE, self.w11())

    def test_w11_says_actual_is_agent_work(self):
        self.assertRegex(self.w11().lower(), r"actual = agent work")

    def test_the_old_human_minutes_are_gone(self):
        self.assertNotIn("human <n>m", read("PRINCIPLES.md"))

    def test_w11_the_main_manager_passes_the_numbers_to_todo_done(self):
        text = self.w11()
        self.assertIn("todo done", text)
        self.assertIn("main manager", text.lower())

    def test_w11_keeps_the_two_times_rule_on_work(self):
        self.assertRegex(self.w11(), r"(?i)work over 2× estimate")

    def test_w11_a_time_question_gets_a_duration_and_a_clock_time(self):
        text = self.w11().lower()
        for phrase in ("time question", "duration", "clock time", "needed next",
                       "agent-file.sh eta"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_w11_still_points_at_the_time_table(self):
        self.assertIn("bin/agent-file.sh time", self.w11())

    def test_r5_names_the_data_block_and_its_keys(self):
        r5 = text_between(read("PRINCIPLES.md"), "R5. Task files", "R6.")
        self.assertIn("`data`", r5)
        for key in DATA_KEYS:
            with self.subTest(key=key):
                self.assertRegex(r5, r"\b%s\b" % key)

    def test_r5_no_longer_says_est_slash_actual(self):
        r5 = text_between(read("PRINCIPLES.md"), "R5. Task files", "R6.")
        self.assertNotIn("est/actual", r5)

    def test_w8_the_deputy_passes_the_facts_and_the_merge_commit(self):
        w8 = text_between(read("PRINCIPLES.md"), "W8. Merge and cleanup", "W9.")
        self.assertIn("todo done", w8)
        self.assertIn("--merge", w8)
        self.assertIn("facts", w8.lower())


class TestDispatchSkillTime(unittest.TestCase):

    def text(self):
        return read("skills", "dispatch", "SKILL.md")

    def brief(self):
        return text_between(self.text(), "## Task manager brief", "## Cross-repo brief")

    def test_step_1_the_estimate_is_agent_work_only(self):
        step1 = text_between(self.text(), "\n1. ", "\n2. ")
        self.assertIn("agent work only", step1.lower())
        self.assertIn("wait", step1.lower())

    def test_step_1_still_reads_the_time_table(self):
        step1 = text_between(self.text(), "\n1. ", "\n2. ")
        self.assertIn("agent-file.sh time", step1)

    def test_a_fast_lane_task_is_closed_with_its_work_minutes(self):
        # check-blocks section 42 B5: closed once, by the merge deputy, with the task's real lane and work minutes
        step2 = text_between(self.text(), "\n2. ", "\n3. ")
        self.assertNotIn("todo done", step2)
        with open(os.path.join(ROOT, "skills", "merge", "SKILL.md")) as fh:
            merge = fh.read()
        self.assertIn("--lane <full|fast>", merge)
        self.assertIn("--work", merge)

    def test_the_brief_report_has_the_new_time_line(self):
        self.assertIn(TIME_LINE, self.brief())

    def test_the_old_human_minutes_are_gone(self):
        self.assertNotIn("human <n>m", self.text())

    def test_the_brief_says_what_counts_as_wait(self):
        report = [l for l in self.brief().splitlines() if l.startswith("REPORT:")][0]
        for phrase in ("agent work only", "mock gate", "suite run"):   # check-blocks section 39 (a): no slots
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, report.lower())

    def test_the_brief_report_has_a_facts_line(self):
        brief = self.brief()
        self.assertIn("FACTS:", brief)
        facts = brief[brief.index("FACTS:"):].splitlines()[0]
        for word in ("type", "lane", "mock", "bounces", "workers", "tests",
                     "scope adds"):
            with self.subTest(word=word):
                self.assertIn(word, facts)

    def test_the_brief_names_the_types(self):
        brief = self.brief()
        for kind in ("page", "server", "script", "docs", "cloud", "app", "data",
                     "mixed"):
            with self.subTest(type=kind):
                self.assertRegex(brief, r"\b%s\b" % kind)

    def test_the_heartbeat_carries_the_work_minutes(self):
        beat = [l for l in self.brief().splitlines() if l.startswith("HEARTBEAT:")][0]
        self.assertIn("step <n> of 7", beat)
        self.assertIn("work <m>m", beat)

    def test_the_heartbeat_still_starts_the_old_way(self):
        # the city reads "HEARTBEAT <name>: step <n>"
        self.assertIn('"HEARTBEAT <name>: step <n> of 7, ', self.brief())

    def test_a_time_question_is_answered_with_the_eta_line(self):
        text = self.text()
        self.assertIn("agent-file.sh eta", text)
        low = text.lower()
        for phrase in ("time question", "clock time", "needed next",
                       "--step", "--work-so-far"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, low)

    def test_the_eta_call_uses_the_plugin_root(self):
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh eta", self.text())


class TestMergeSkillTime(unittest.TestCase):

    def text(self):
        return read("skills", "merge", "SKILL.md")

    def test_a_report_with_no_time_line_bounces(self):
        step1 = text_between(self.text(), "\n1. ", "\n2. ")
        self.assertIn("TIME", step1)
        self.assertIn("wait", step1.lower())

    def test_the_deputy_brief_carries_the_todo_done_arguments(self):
        text = self.text()
        self.assertIn("todo done arguments:", text)
        line = text[text.index("todo done arguments:"):].splitlines()[0]
        for fact in DONE_FACTS:
            with self.subTest(fact=fact):
                self.assertIn(fact, line)

    def test_the_brief_no_longer_says_five_values(self):
        self.assertNotIn("all five values", self.text())

    def test_it_says_where_the_numbers_come_from(self):
        text = self.text()
        self.assertIn("FACTS", text)
        self.assertRegex(text, r"(?i)actual = agent work|agent work only")


class TestCloseCaseSkillTime(unittest.TestCase):

    def text(self):
        return read("skills", "close-case", "SKILL.md")

    def test_the_report_keeps_work_and_wait_apart(self):
        text = self.text()
        self.assertIn("TIME", text)
        self.assertRegex(text.lower(), r"work and wait apart")

    def test_close_now_keeps_the_work_so_far_on_the_todo_line(self):
        part = text_between(self.text(), "**close now**", "\n3. ")
        self.assertIn("work so far", part.lower())
        self.assertIn("wait", part.lower())

    def test_close_now_still_keeps_the_todo_line_open(self):
        part = text_between(self.text(), "**close now**", "\n3. ")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add", part)

    def test_no_old_human_minutes(self):
        self.assertNotIn("human <n>m", self.text())


class TestMergeDeputyTime(unittest.TestCase):

    def text(self):
        return read("agents", "merge-deputy.md")

    def test_the_brief_gives_the_todo_done_arguments(self):
        line = [l for l in self.text().splitlines() if l.startswith("Your brief gives")][0]
        self.assertIn("<todo done arguments>", line)

    def test_step_7_passes_them_and_the_merge_commit(self):
        step7 = [l for l in self.text().splitlines() if l.startswith("7. ")][0]
        self.assertIn('agent-file.sh todo done "<name>"', step7)
        self.assertIn("<todo done arguments>", step7)
        self.assertIn("--merge", step7)

    def test_step_7_still_removes_the_worktree_line(self):
        step7 = [l for l in self.text().splitlines() if l.startswith("7. ")][0]
        self.assertIn('agent-file.sh worktree rm "<worktree path>"', step7)


class TestCloseCaseHookTime(unittest.TestCase):

    def test_the_hook_asks_for_wait_not_human_minutes(self):
        text = read("skills", "close-case", "SKILL.md")
        self.assertIn("TIME: est <n>m, actual <n>m, wait <n>m", text)
        self.assertNotIn("human <n>m", text)


class TestReadmeTime(unittest.TestCase):

    def test_the_command_list_shows_the_time_commands(self):
        text = read("PRINCIPLES.md")
        for command in ("bin/agent-file.sh time", "bin/agent-file.sh data",
                        "bin/agent-file.sh eta"):
            with self.subTest(command=command):
                self.assertIn(command, text)

    def test_the_time_line_no_longer_says_estimate_vs_actual(self):
        self.assertNotIn("estimate vs actual", read("PRINCIPLES.md"))

    def test_the_files_table_says_the_completed_file_is_data_too(self):
        row = [l for l in read("PRINCIPLES.md").splitlines()
               if l.startswith("| `agent_completed.txt`")][0]
        self.assertRegex(row.lower(), r"data")


def section_lines(text, start, end):
    """Lines from the line starting with `start` up to (not incl.) the line starting with `end`."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith(start):
            inside = True
        elif inside and line.startswith(end):
            break
        if inside:
            out.append(line)
    return out


class TestPrinciplesS8Trim(unittest.TestCase):
    def setUp(self):
        self.text = read("PRINCIPLES.md")
        self.s8 = [l for l in section_lines(self.text, "S8.", "S9.") if l.startswith("- ")]

    def has(self, lines, *words):
        hits = [l for l in lines if all(w in l for w in words)]
        self.assertTrue(hits, "no line with %r in:\n%s" % (words, "\n".join(lines)))

    def test_s8_lines_are_terse(self):
        for line in self.s8:
            with self.subTest(line=line[:60]):
                self.assertLessEqual(len(line), 200, line)

    def test_s8_state_add(self):
        self.has(self.s8, "agent-file.sh state add")

    def test_s8_state_trim_and_the_day_archive(self):
        self.has(self.s8, "state trim", "agent_state.trim-")

    def test_s8_the_start_warning(self):
        self.has(self.s8, "Over 300 lines (fixed)", "STATE LONG")   # settings-configure: a constant

    def test_s8_the_auto_clear(self):
        self.has(self.s8, "Compacted 2 times (fixed)", "empty")

    def test_s8_goal(self):
        self.has(self.s8, "/goal", "GOAL:")

    def test_the_old_hand_clear_line_is_gone(self):
        self.assertNotIn("the main manager types it into the pane", self.text)

    def test_w8_housekeep_trims(self):
        self.has(section_lines(self.text, "W8.", "W9."), "housekeep", "state trim")

    def test_w14_state_add(self):
        self.has(section_lines(self.text, "W14.", "W15."), "state add")


class TestDispatchSkillTrim(unittest.TestCase):
    def setUp(self):
        self.text = read("skills", "dispatch", "SKILL.md")
        self.lines = self.text.splitlines()

    def test_the_brief_has_a_goal_line(self):
        goal = [l for l in self.lines if l.startswith("GOAL: task manager <name>: done when")]
        self.assertEqual(len(goal), 1, "one GOAL: line in the brief template")
        for word in ("DONE PASS", "DONE FAIL", "pushed", "QUESTION:", "MOCK READY", "CLOSE CASE", "AUTO CLEAR"):
            self.assertIn(word, goal[0])

    def test_the_brief_state_line_says_state_add(self):
        state = [l for l in self.lines if l.startswith("STATE:")]
        self.assertTrue(state)
        self.assertIn("agent-file.sh state add", state[0])

    def test_the_main_manager_types_goal_at_an_idle_prompt(self):
        hits = [l for l in self.lines if "/goal" in l and "tui-idle" in l]
        self.assertTrue(hits, "a step that waits for tui-idle and types /goal")

    def test_goal_again_after_an_answer(self):
        hits = [l for l in self.lines if "/goal" in l and "QUESTION" in l and ("mock yes" in l or "rules yes" in l)]
        self.assertTrue(hits, "a line: re-type /goal after a QUESTION answer and a mock or rules answer")


class TestReadmeAndReleaseTrim(unittest.TestCase):
    def test_readme_names_state_trim(self):
        self.assertIn("state trim", read("PRINCIPLES.md"))


class TestWiredInEstimate(unittest.TestCase):

    def test_the_dispatch_estimate_step_runs_the_estimator(self):
        step1 = text_between(read("skills", "dispatch", "SKILL.md"), "\n1. ", "\n2. ")
        for word in ("${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh estimate", "--lane", "--mock",
                     "--type", "agent-file.sh time", "range", "like"):
            with self.subTest(word=word):
                self.assertIn(word, step1)

    def test_the_rubric_numbers_left_the_skill(self):
        step1 = text_between(read("skills", "dispatch", "SKILL.md"), "\n1. ", "\n2. ")
        for old in ("45 to 60", "60 to 90", "90 to 120", "5 to 15"):
            with self.subTest(old=old):
                self.assertNotIn(old, step1)

    def test_the_time_rules_name_the_estimator(self):
        w11 = text_between(read("PRINCIPLES.md"), "W11. Time", "W12.")
        self.assertIn("bin/agent-file.sh estimate", w11)
        self.assertIn("bin/agent-file.sh time", w11)
        self.assertNotIn("pick a rubric row", w11)

    def test_the_readme_lists_it(self):
        text = read("PRINCIPLES.md")
        for word in ("bin/agent-file.sh estimate", "bin/agent-file.sh backtest",
                     "bin/agent-file.sh retrain", "bin/agent_estimate.py", "`agent_estimate.txt`"):
            with self.subTest(word=word):
                self.assertIn(word, text)

    def test_the_usage_of_agent_file_names_the_new_commands(self):
        head = read("bin", "agent-file.sh").split("\nset -eu")[0]
        for word in ("agent-file.sh estimate", "agent-file.sh backtest",
                     "agent-file.sh retrain", "data [--what]"):
            with self.subTest(word=word):
                self.assertTrue(word in head, "the usage block does not name: " + word)


class TestWiredInBlend(unittest.TestCase):

    def test_the_dispatch_step_writes_the_guess_first(self):
        skill = read("skills", "dispatch", "SKILL.md")
        step1 = text_between(skill, "\n1. ", "\n2. ")
        self.assertIn("--guess", step1)
        self.assertLess(step1.index("guess"), step1.index("agent-file.sh estimate"), step1)
        add = [l for l in skill.splitlines() if "agent-file.sh todo add" in l]
        self.assertTrue(add, "the skill shows the todo add line")
        self.assertTrue(all("--guess" in l for l in add), add)

    def test_the_time_rules_name_the_guess(self):
        w11 = text_between(read("PRINCIPLES.md"), "W11. Time", "W12.")
        self.assertIn("--guess", w11)

    def test_the_readme_and_the_usage_name_the_guess(self):
        self.assertIn("--guess", read("PRINCIPLES.md"))
        head = read("bin", "agent-file.sh").split("\nset -eu")[0]
        for word in ("--guess", "guess=", "warning"):
            with self.subTest(word=word):
                self.assertIn(word, head)


STAGES = ["brief", "register", "mock", "tests", "workers", "verify", "push", "report", "e2e", "merge"]


def brief_block(text):
    start = text.index("## Task manager brief")
    end = text.index("## Cross-repo brief")
    return text[start:end]


class TestSkillsProgress(unittest.TestCase):
    CMD = '${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo stage "<name>" '

    def test_the_brief_names_every_task_manager_stage(self):
        block = brief_block(read("skills", "dispatch", "SKILL.md"))
        for word in STAGES[:8]:
            with self.subTest(stage=word):
                self.assertIn(self.CMD + word, block)
        self.assertIn(self.CMD + "workers <i>/<m>", block)

    def test_the_merge_skill_names_e2e_and_merge(self):
        text = read("skills", "merge", "SKILL.md")
        self.assertIn(self.CMD + "e2e", text)
        self.assertIn(self.CMD + "merge", text)
        self.assertLess(text.index(self.CMD + "e2e"), text.index(self.CMD + "merge"))

    def test_principles_show_todo_names_the_stage_record(self):
        text = read("PRINCIPLES.md")
        w14 = text[text.index("W14. Todo board"):text.index("W15. Watch")]
        self.assertIn("todo stage", w14)
        self.assertIn("progress", w14.lower())


class TestAutoClearQuietRule(unittest.TestCase):
    def test_s8(self):
        with open(os.path.join(os.path.dirname(HERE), "PRINCIPLES.md")) as fh:
            text = fh.read()
        s8 = text[text.index("S8. "):text.index("S9. ")]
        for phrase in ("The auto clear fires only when no human has typed a prompt in that pane for the last N minutes",
                       '"Context: Auto clear after quiet (min)", default 30',
                       "Not a human prompt: a task notification, a tell pointer, a cross-session message, the watch "
                       "or the auto clear's own prompts",
                       "A task manager nobody types into is cleared as today"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, s8)


class TestPrinciplesW12OwnerRelay(unittest.TestCase):

    def setUp(self):
        self.w12 = text_between(read("PRINCIPLES.md"), "W12. Cross-repo", "W13. Close case")
        self.rules = [l for l in self.w12.splitlines() if l.startswith("- ")]

    def one(self, *words):
        hits = [l for l in self.rules if all(w.lower() in l.lower() for w in words)]
        self.assertEqual(len(hits), 1, "want one W12 line with %r, got %r" % (words, hits))
        return hits[0]

    def test_g1_relay_line(self):
        line = self.one("agent-owner-order.sh line --quote")
        self.assertIn("never paraphrase", line.lower())

    def test_g1_receiving_line(self):
        line = self.one("check line", "ask the owner")
        self.assertIn("verified", line.lower())
        self.assertIn("not verified", line.lower())
        self.assertIn("peer message", line.lower())
        self.assertIn("reply", line.lower())
        self.assertIn("match line", line.lower())   # L17 (review bounce 1)

    def test_g1_still_ask_line(self):
        line = self.one("verified owner words")
        # approval-design (section 53 E): he is read by the approval cases of R8, not by words that name the action
        for words in ("approval cases", "final yes", "production included", "one question"):
            with self.subTest(words=words):
                self.assertIn(words, line)
        self.assertNotIn("name the action", line)
        self.assertNotIn("name that action", line)

    def test_g1_floor_still_applies(self):
        self.assertIn("floor", self.w12.lower())

    def test_g1_the_three_new_lines_are_short(self):
        for line in (self.one("agent-owner-order.sh line --quote"), self.one("check line", "ask the owner"),
                     self.one("verified owner words")):
            with self.subTest(line=line[:40]):
                self.assertLessEqual(len(line), 200)

    def test_g1_send_the_brief_line_kept(self):
        line = next(l for l in self.rules if l.startswith("- Send the brief"))
        self.assertIn("[<model> <effort>] CROSS-REPO TASK <name> from <repo>", line)


class TestDispatchSkillOwnerRelay(unittest.TestCase):

    def test_g2_a_line_above_the_cross_repo_block(self):
        lines = read("skills", "dispatch", "SKILL.md").splitlines()
        i = next(n for n, l in enumerate(lines) if l.startswith("## Cross-repo brief"))
        j = next(n for n in range(i + 1, len(lines)) if lines[n].strip().startswith("```"))
        between = "\n".join(lines[i + 1:j])
        self.assertIn("agent-owner-order.sh line", between)
        self.assertIn("owner order", between.lower())
        self.assertTrue(lines[j + 1].strip().startswith("[<model> <effort>] CROSS-REPO TASK"))


class TestReadmeOwnerRelay(unittest.TestCase):

    def test_g3_map_lists_the_tool(self):
        hits = [l for l in read("PRINCIPLES.md").splitlines()
                if l.strip().startswith("bin/agent-owner-order.sh")]
        self.assertEqual(len(hits), 1, hits)
        self.assertIn("owner", hits[0].lower())


SECTION_CAP = 3000


MIT_NOTICE = """Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def section_e(text):
    """What the hook prints: "## E. Output" up to the next "## " line."""
    lines = text.splitlines()
    start = lines.index("## E. Output")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return "\n".join(lines[start:end]).rstrip() + "\n"


def rule(text, code, nxt):
    """The text of one rule, from its code ("W8.") to the next marker."""
    start = text.index(code)
    return text[start:text.index(nxt, start)]


class PrinciplesCase(unittest.TestCase):
    def setUp(self):
        self.text = read("PRINCIPLES.md")
        self.assertIn("## E. Output", self.text.splitlines(),
                      "PRINCIPLES.md has no '## E. Output' line yet")
        self.e = section_e(self.text)
        self.low = self.e.lower()

    def has(self, *phrases, where=None):
        block = (where if where is not None else self.e).lower()
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), block)


class TestTheSection(PrinciplesCase):
    def test_it_comes_after_d(self):
        self.assertLess(self.text.index("## D. Auto setup"), self.text.index("## E. Output"))

    def test_it_fits_the_hook(self):
        size = len(self.e.encode())
        self.assertLessEqual(size, SECTION_CAP, "section E is %d bytes" % size)

    def test_terse_lines(self):
        for line in self.e.splitlines():
            with self.subTest(line=line[:60]):
                self.assertLessEqual(len(line), 160)

    def test_rule_codes(self):
        self.assertRegex(self.e, r"(?m)^E1\. ")

    def test_credit_line(self):
        self.has("i-have-adhd", "Ayoub Ghriss", "MIT", where=self.text)

    def test_no_owner_or_machine(self):
        for word in ("Maverick", "maverick", "laptop", "pc2"):
            with self.subTest(word=word):
                self.assertNotIn(word, self.e)


class TestF1TheRuleset(PrinciplesCase):
    def test_shape(self):
        self.has("next action", "number", "Step <n> of <m>", "tangent",
                 "estimate", "what now works", "Uh oh", "5 items")

    def test_no_padding(self):
        self.has("preamble", "recap", "closer")

    def test_overrides(self):
        self.has("explain", "destructive", "still broken", "ambiguous", "harness")

    def test_pre_send_check(self):
        self.has("pre-send", "first line", "last line", "hedge", "idiom")


class TestF2OwnerOverrides(PrinciplesCase):
    def test_never_fail_silently(self):
        self.has("fail silently", "blocked", "refused", "broken", "partial success")

    def test_tables_are_not_lists(self):
        self.has("tables and ledgers are not lists", "completeness")

    def test_verified_needs_evidence(self):
        self.has("verified", "evidence", "real device")

    def test_decide_section_stays(self):
        self.has("decide section", "H3")

    def test_language(self):
        self.has("H2")


class TestF3Concise(PrinciplesCase):
    def test_concise(self):
        self.has("lead with the result", "narration", "short by default",
                 "plainly", "full detail on request",
                 "never trade correctness for brevity")


class TestF4Switch(PrinciplesCase):
    def test_no_off_switch(self):
        for word in ("adhd=off", "stop adhd mode", "normal mode"):
            self.assertNotIn(word, self.low)


class TestTheNotice(PrinciplesCase):
    def test_copyright_line(self):
        self.assertIn("Copyright (c) 2026 Ayoub Ghriss", self.text)

    def test_the_whole_permission_notice(self):
        self.assertIn(squash(MIT_NOTICE), squash(self.text))

    def test_it_is_after_section_e_not_inside(self):
        self.assertNotIn("Permission is hereby granted", self.e)
        self.assertGreater(self.text.index("Permission is hereby granted"),
                           self.text.index("## E. Output"))


class TestGeneric(PrinciplesCase):
    def test_no_owner_or_machine_names_anywhere(self):
        for word in ("Maverick", "maverick-pc2", "this laptop"):
            with self.subTest(word=word):
                self.assertNotIn(word, self.text)


class TestF5ManagerLaws(PrinciplesCase):
    def test_test_parallelism_is_capped(self):
        self.has("maxWorkers=2", "-j 2", where=rule(self.text, "S5.", "S6."))

    def test_no_count_caps(self):
        # was test_reviewers_count_toward_the_cap: the caps are gone (check-blocks section 25, owner 2026-11-25)
        self.has("No count caps", where=rule(self.text, "S6.", "S7."))

    def test_push_at_every_stage_and_clean_after_a_verified_merge(self):
        self.has("push at every stage", where=self.text)
        self.has("merge is verified", where=rule(self.text, "W8.", "W9."))

    def test_watching_launches_and_stalls(self):
        self.has("2 min",
                 "nudge once", "salvage", "heartbeat", where=self.text)

    def test_only_owner_level_or_irreversible_stops_the_line(self):
        self.has("owner-level", "irreversible", where=rule(self.text, "W1.", "W2."))

    def test_model_by_kind_of_thinking(self):
        self.has("strongest", where=rule(self.text, "S9.", "## E. Output"))

    def test_tests_follow_the_blocks(self):
        # check-blocks 2026-11-25: the full gate per task is gone (no block backs it); FULL SUITE
        # (owner 1A: no task runs the full suite; MODULE TESTS only when its trigger fires)
        self.has("MODULE TESTS only when its trigger fires", where=rule(self.text, "W4.", "W5."))

    def test_e2e_is_the_proof(self):
        block = rule(self.text, "W5.", "W6.")
        self.has("unit tests are not proof", "never verify their own work",
                 "needs a real device", where=block)

    def test_ask_in_one_batch_and_the_return_table(self):
        self.has("one batch", "interim default", "recommendation",
                 where=rule(self.text, "H1.", "H2."))

    def test_collision(self):
        self.has("collision", "never route around", where=self.text)


class TestF6Lessons(PrinciplesCase):
    def test_time(self):
        block = rule(self.text, "W11.", "W12.")
        self.has("`date`", "drift", "re-estimate", where=block)

    def test_commands(self):
        self.has("classifier", "! git push", "Deliver", "4 KB", "--cursor",
                 "mid-turn", "screen locked", "headless Chrome", where=self.text)


def principles_between(start, end):
    text = read("PRINCIPLES.md")
    return text[text.index(start):text.index(end)]


DISPATCH = ("skills", "dispatch", "SKILL.md")


MERGE = ("skills", "merge", "SKILL.md")


DEPUTY = ("agents", "merge-deputy.md")


FAST = ("agents", "fast-lane-deputy.md")


CHECK = ("agents", "check-deputy.md")


class TestB1NoWorkerCap(unittest.TestCase):
    def test_dispatch(self):
        d = read(*DISPATCH)
        self.assertNotIn("max 2 at once", d)
        self.assertIn("as many at once as the memory rule admits (S3)", d)


class TestB2NoSuiteAtTheMerge(unittest.TestCase):
    def test_merge_and_deputy(self):
        self.assertNotIn("suite command:", read(*MERGE))
        dep = read(*DEPUTY)
        self.assertNotIn("<suite command>", dep)
        self.assertIn("No test run at the merge (W4: never re-run what passed; R8: no task runs the full suite)", dep)
        self.assertNotIn("ORIG_HEAD", dep)              # no test run, nothing to undo
        w8 = principles_between("W8. ", "W9. ")
        self.assertNotIn("ORIG_HEAD", w8)
        self.assertIn("Never `git reset --hard` in the main checkout", w8)


class TestB3StepOneChecksTheBuildersBlocks(unittest.TestCase):
    def test_merge_step_1(self):
        m = read(*MERGE)
        self.assertNotIn("a tool block with no pass line → bounce it", m)
        self.assertIn("a block the builder owns with no pass line", m)
        self.assertIn("PR REVIEW, CORE REVIEW, FLOW CHECK and UI CHECK are checked by the gate after the reviewer and "
                      "the check deputy ran", m)


class TestB4FastLaneReportHasTimeAndFacts(unittest.TestCase):
    def test_fast_lane(self):
        f = read(*FAST)
        report = f[f.index("Report (H3)"):]
        self.assertIn("TIME:", report)
        self.assertIn("FACTS:", report)


class TestB5TodoDoneOnce(unittest.TestCase):
    def test_dispatch_and_merge(self):
        step2 = [l for l in read(*DISPATCH).splitlines() if l.startswith("2. Small task")][0]
        self.assertNotIn("todo done", step2)
        m = read(*MERGE)
        self.assertNotIn("--lane full", m)
        self.assertIn("--lane <full|fast>", m)


class TestS1ProductionPathCleansUp(unittest.TestCase):
    def test_merge_and_deputy(self):
        self.assertIn("merged: <merge hash>", read(*MERGE))
        dep = read(*DEPUTY)
        self.assertIn("`merged: <merge hash>`", dep)
        self.assertIn("skips steps 1-4", dep)


class TestS2S3CheckDeputy(unittest.TestCase):
    def test_smoke_launch_is_the_main_managers(self):
        self.assertIn("the main manager does the one subagent launch", read(*CHECK))

    def test_resize_tool(self):
        tools = [l for l in read(*CHECK).splitlines() if l.startswith("tools:")][0]
        self.assertIn("mcp__claude-in-chrome__resize_window", tools)


class TestS4HeadlessIsTheCheckDeputys(unittest.TestCase):
    def test_merge(self):
        m = read(*MERGE)
        self.assertNotIn("Run the same click path with Playwright", m)
        self.assertIn("the check deputy runs the same click path with Playwright", m)


class TestS5SyncAtABatchStart(unittest.TestCase):
    def test_dispatch(self):
        self.assertIn("agent-promote.sh --sync", read(*DISPATCH))


class TestS6NotSwitchedYet(unittest.TestCase):
    def test_r8(self):
        self.assertIn("A repo whose working branch exists but whose main checkout is not switched yet: merges go into "
                      "the production branch as before", principles_between("R8. ", "W1. "))


class TestS7NoSlotNoLevel(unittest.TestCase):
    def test_texts(self):
        text = read("PRINCIPLES.md")
        self.assertNotIn("WATCH SLOT", text)
        self.assertIn("WATCH ROOM", principles_between("W15. ", "W16. "))
        self.assertIn("level (old tasks only, - for new ones)", principles_between("R5. ", "R6. "))
        d = read(*DISPATCH)
        self.assertNotIn("slot", d.lower())
        self.assertIn("Waiting for room or another task", d)

    def test_code(self):
        self.assertNotIn("WATCH SLOT", read("bin", "agent_watch.py"))
        self.assertIn("WATCH ROOM %s: can start", read("bin", "agent_watch.py"))
        af = read("bin", "agent-file.sh")
        self.assertNotIn("slots <free>", af)
        self.assertNotIn("suite slot", af)


class TestS8ModelsBySetting(unittest.TestCase):
    def test_w6_and_tree(self):
        text = read("PRINCIPLES.md")
        self.assertNotIn("Sonnet 5, medium", text)
        w6 = principles_between("W6. ", "W7. ")
        for role in ("Fast-lane deputy", "Merge deputy", "Check deputy", "Worker"):
            line = [l for l in w6.splitlines() if l.startswith("- %s (" % role)][0]
            self.assertIn("Helper model", line)

    def test_the_setting_names_the_check_deputy(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import agent_conf
        desc = [s for s in agent_conf.SETTINGS if s["key"] == "helper_model"][0]
        self.assertIn("check deputy", json.dumps(desc))
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as fh:
            self.assertIn("check deputy", json.load(fh)["userConfig"]["helper_model"]["description"])


class TestS9OneWording(unittest.TestCase):
    def test_r8(self):
        r8 = principles_between("R8. ", "W1. ")
        self.assertNotIn("never by the user", r8)
        self.assertIn("a human may edit it, never has to", r8)


class TestS10StatusFinal(unittest.TestCase):
    def test_dispatch(self):
        d = read(*DISPATCH)
        self.assertNotIn("set status done", d)
        self.assertIn("set status final (R7)", d)


class TestS11PermissionModeDefault(unittest.TestCase):
    def test_s1(self):
        s1 = principles_between("S1. ", "S2. ")
        self.assertIn('"Permissions: Permission mode" setting, default bypassPermissions', s1)


class TestD1MockRule(unittest.TestCase):
    def test_r1_and_dispatch(self):
        r1 = principles_between("R1. ", "R2. ")
        self.assertNotIn("Mock if the task has UI", r1)
        self.assertIn("2. Mock for a new page or a whole-page re-layout (W2)", r1)
        self.assertIn("a new page or a whole-page re-layout", read(*DISPATCH))


class TestD2CleanupOrder(unittest.TestCase):
    def test_w8(self):
        w8 = principles_between("W8. ", "W9. ")
        self.assertNotIn("Clean up only after the merge is verified", w8)
        self.assertIn("Delete the branch and close the todo line only after the merge is verified", w8)
        self.assertIn("the pane and the worktree may go while waiting for the owner's yes; the pushed branch stays", w8)


class TestD3ResultFirst(unittest.TestCase):
    def test_e1(self):
        e1 = principles_between("E1. ", "E2. ")
        self.assertNotIn("Lead with the next action", e1)
        self.assertIn("Lead with the result", e1)
        self.assertIn("A command, path or snippet the human must use comes right after the result", e1)
        self.assertIn("End with one concrete next action", e1)


class TestD4WaitExceptions(unittest.TestCase):
    def test_w1(self):
        w1 = principles_between("W1. ", "W2. ")
        self.assertIn("Never wait for the human, except: the kick-off round, a mock yes, an OWNER SIGN, NEEDS HUMAN E2E",
                      w1)
        self.assertNotIn("kick-off round only", w1)


NAMES = ["DIFF SCAN", "BUILD", "RELATED TESTS", "MODULE TESTS", "GUARD TESTS", "DB CHECK", "DATA CHECK",
         "CORE REVIEW", "PR REVIEW", "EXAMPLES TEST", "FLOW CHECK", "UI CHECK",
         "REAL DATA COUNT"]


def text_between_after_start(text, start, end):
    begin = text.index(start)
    return text[begin:text.index(end, begin + len(start))]


def table_rows():
    r = subprocess.run([sys.executable, os.path.join(BIN, "agent_blocks.py"), "table"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise AssertionError("agent_blocks.py table failed: %s" % r.stderr)
    return r.stdout.splitlines()


LEVEL_WORDS = re.compile(r"(?i)(\brisk types?\b|\btype [A-D]\b|\b[A-D] = (?:text|ui|logic|danger)\b|--level\b|"
                         r"\btodo level\b|--declared\b|\bRAISE\b|REQUIRED TYPE|\blevel [0-4]\b|\(R8 check)")


class TestPrinciplesR8(unittest.TestCase):

    def r8(self):
        return text_between_after_start(read("PRINCIPLES.md"), "R8. Check blocks", "## B. Work")

    def test_r8_is_check_blocks_in_its_place(self):
        text = read("PRINCIPLES.md")
        order = [text.index(h) for h in ("R7. Worktree file", "R8. Check blocks", "## B. Work")]
        self.assertEqual(order, sorted(order))
        self.assertNotIn("R8. Risk types", text)
        self.assertEqual(text.count("\nR8. "), 1)

    def test_r8_holds_the_one_table_exactly(self):
        rows = table_rows()
        lines = self.r8().splitlines()
        i = lines.index(rows[0])
        self.assertEqual(lines[i:i + len(rows)], rows)

    def test_the_table_is_in_principles_only_once(self):
        self.assertEqual(read("PRINCIPLES.md").count(table_rows()[0]), 1)

    def test_r8_says_the_owner_goal_and_the_process(self):
        r8 = self.r8()
        for phrase in ("only do the necessary thing when needed", "No levels", "bin/agent_blocks.py",
                       "agent-level.sh check", "todo add", "--checks", "only added",
                       "verified owner order", "--remove", "--owner-quote", "agent-file.sh check",
                       "checks gate", "no pass line", "OWNER SIGN", "not the builder",
                       "check_budget_s", "60 s", "the net", "NIGHTLY RUN", "RELEASE SMOKE",
                       # owner 1A 2026-11-25 (section 15)
                       "No task runs the full suite", "MODULE TESTS", "gates nothing", "selection miss",
                       "agent-nightly.sh", "the last nightly on that commit", "agent-nightly.sh --release-ok",
                       "agent_repo.conf", "edge add", "which example would have shown it",
                       "Refactor", "Urgent fix", "Rollback", "Research only",
                       "skipped with one printed line", "second agent's opinion only for CORE REVIEW",
                       "copies its defaults from the released", "every changed default"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r8)

    def test_r8_lines_are_short_bullets_or_table_rows(self):
        for line in self.r8().rstrip().splitlines()[1:]:
            with self.subTest(line=line[:50]):
                if not line.strip() or line.startswith("|"):
                    continue
                self.assertTrue(line.startswith("- ") or line.startswith("  - "), line)
                self.assertLessEqual(len(line), 220)

    def test_every_block_name_in_principles_is_in_the_table(self):
        # never a rule line that the table of blocks does not back
        text = read("PRINCIPLES.md").split("## Notice")[0]
        found = set(re.findall(r"\b([A-Z]{2,}(?: [A-Z]{2,})+)\b", text))
        extra = {"OWNER SIGN", "NIGHTLY RUN", "RELEASE RUN", "RELEASE SMOKE", "TEST RUN", "URGENT FIX", "WORKING BRANCH",   # a start line, not a block (section 41 G9)
                   # sign, net, runner
                 "DONE PASS", "DONE FAIL", "CLOSE CASE", "NEEDS HUMAN", "MOCK READY", "STALE PLUGIN",
                 "STATE LONG", "OWNER TODO", "QUESTIONS PAGE", "OWNER ORDER", "REPO TASK",   # report words
                 "GATE PASS", "GATE REFUSED", "CHECK PASS", "CHECK FAIL", "MERGE PASS", "MERGE FAIL",
                 "WATCH SIGNAL", "WATCH STALL", "WATCH LOST", "WATCH ROOM", "AUTO CLEAR",
                 "MODE MISMATCH",                                               # mode-match, W16
                 "OWNER WORDS"}                                                 # approval-design: the gate's stored pair lines
        unknown = sorted(n for n in found if n not in NAMES and n not in extra)
        self.assertEqual(unknown, [], "names in PRINCIPLES.md that are no block: %s" % unknown)


class TestPrinciplesOtherRules(unittest.TestCase):

    def text(self):
        return read("PRINCIPLES.md")

    def rule(self, start, end):
        return text_between_after_start(self.text(), start, end)

    def test_no_level_words_left_in_the_rules(self):
        body = self.text().split("## Notice")[0]
        self.assertEqual(LEVEL_WORDS.findall(body), [])

    def test_r1_lane_by_size_checks_by_triggers(self):
        r1 = self.rule("R1. ", "R2. ")
        for phrase in ("small task = one subagent", "own git worktree", "over 2 hours", "task manager",
                       "Which checks run follows the triggers only (R8)",
                       "A small logic task never opens a task manager just because it needs a test",
                       "past 2x its estimate", "second slice", "goes on from its branch"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r1)
        self.assertNotIn("TDD", r1)

    def test_w4_tests_follow_the_blocks(self):
        w4 = self.rule("W4. ", "W5. ")
        for phrase in ("RELATED TESTS", "GUARD TESTS", "MODULE TESTS", "only when its trigger fires",
                       "never re-run tests the task manager already passed", "re-run only the tests that failed"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w4)
        self.assertNotIn("Full suite only when really needed", w4)
        self.assertNotIn("FULL SUITE", w4)
        self.assertIn("No task runs the full suite", w4)

    def test_w5_the_check_deputy_drives_the_browser(self):
        w5 = self.rule("W5. ", "W6. ")
        for phrase in ("check deputy", "one at a time", "FLOW CHECK", "UI CHECK", "never verify their own work"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w5)
        self.assertNotIn("Main manager only", w5)

    def test_w6_roles(self):
        w6 = self.rule("W6. ", "W7. ")
        for phrase in ("Check deputy", "agents/check-deputy.md", "verdict with evidence",
                       "The main manager stays free for the human", "runs no long check itself",
                       "own git worktree", "pushes a branch"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w6)

    def test_w8_merge_gate_and_cleanup(self):
        w8 = self.rule("W8. ", "W9. ")
        # section 42 B2: no run at the merge, so no undo line; the --hard warning stays in its own words
        for phrase in ("checks gate", "after every merge", "Never `git reset --hard` in the main checkout"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w8)

    def test_w9_small_tasks_and_self_assignment(self):
        w9 = self.rule("W9. ", "W10. ")
        for phrase in ("own git worktree", "never share a checkout", "agent-file.sh next",
                       "at every wake", "needs no new question", "todo done",
                       "room under the Max memory % limit (S3)"):   # section 37 F5: room, not slots
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w9)
        self.assertNotIn("free slot under the machine caps", w9)
        self.assertNotIn("Never spawn a worktree for a small task", w9)

    def test_w15_restart_the_watch_first(self):
        w15 = self.rule("W15. ", "W16. ")
        self.assertIn("the first action is to start the watch again, then handle the signal", w15)
        self.assertIn("when there is room for a queued task (WATCH ROOM)", w15)   # section 42 S7   # section 37 F5: room, not slots
        self.assertNotIn("slot is free", w15)
        self.assertIn("board warning", w15)

    def test_the_map_names_the_new_pieces(self):
        f = self.text().split("## F. Map")[1]
        for phrase in ("bin/agent_blocks.py", "bin/agent-level.sh", "Check deputy", "agent_repo.conf",
                       "36-question quiz", "agent-file.sh next", "checks gate"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, f)


class TestDispatchSkill(unittest.TestCase):

    def text(self):
        return read("skills", "dispatch", "SKILL.md")

    def test_no_level_words(self):
        self.assertEqual(LEVEL_WORDS.findall(self.text()), [])

    def test_it_picks_the_brief_blocks(self):
        text = self.text()
        for name in ("PR REVIEW", "EXAMPLES TEST", "FLOW CHECK", "UI CHECK", "REAL DATA COUNT", "CORE REVIEW"):
            self.assertIn(name, text)
        adds = [l for l in text.splitlines() if "agent-file.sh todo add" in l]
        self.assertTrue(adds)
        for l in adds:
            self.assertIn("--checks", l)

    def test_the_brief_runs_the_blocks_never_full_suite_once(self):
        brief = text_between_after_start(self.text(), "## Task manager brief", "## Cross-repo brief")
        self.assertTrue([l for l in brief.splitlines() if l.startswith("CHECKS:")], brief)
        self.assertFalse([l for l in brief.splitlines() if l.startswith("LEVEL:")])
        self.assertIn("run the blocks of the task", brief)
        self.assertNotIn("Full suite once", brief)
        self.assertNotIn("Full suite twice", brief)

    def test_next_at_every_wake(self):
        self.assertIn("agent-file.sh next", self.text())

    def test_small_task_subagent_in_its_own_worktree(self):
        step2 = text_between_after_start(self.text(), "\n2. ", "\n3. ")
        for phrase in ('isolation: "worktree"', "--builder", "EXAMPLES TEST", "merge-deputy"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, step2)

    def test_default_pane_of_orca_worktree_create(self):
        # slice 8 (c): use the default agent pane for the brief or close it, never a second one
        text = self.text()
        self.assertIn("default", text)
        self.assertIn("never open a second", text)

    def test_requirement_defaults_from_the_released_template(self):
        text = self.text()
        self.assertIn("released template", text)
        self.assertIn("every changed default", text)


class TestMergeSkill(unittest.TestCase):

    def text(self):
        return read("skills", "merge", "SKILL.md")

    def test_no_level_words(self):
        self.assertEqual(LEVEL_WORDS.findall(self.text()), [])

    def test_gate_and_check_deputy(self):
        text = self.text()
        for phrase in ("checks gate", "check-deputy", "GATE REFUSED", "PR REVIEW", "FLOW CHECK", "UI CHECK"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertLess(text.index("checks gate"), text.index("merge-deputy"))

    def test_the_deputy_brief_has_no_level(self):
        block = text_between_after_start(self.text(), "name: <name>", "todo done arguments:")
        self.assertNotIn("level:", block)
        self.assertIn("session:", block)
        self.assertIn("machine:", block)


class TestAgents(unittest.TestCase):

    def test_check_deputy(self):
        text = read("agents", "check-deputy.md")
        head = text.split("---")[1]
        self.assertIn("name: check-deputy", head)
        self.assertIn("model: sonnet", head)
        tools = [l for l in head.splitlines() if l.startswith("tools:")][0]
        for tool in ("Read", "Grep", "Glob", "Bash", "mcp__claude-in-chrome__"):
            self.assertIn(tool, tools)
        self.assertNotIn("Edit", tools)
        self.assertNotIn("Write", tools)
        body = text.split("---", 2)[2]
        for phrase in ("FLOW CHECK", "UI CHECK", "RELEASE SMOKE", "one at a time", "15-minute",
                       "agent-file.sh idea add",
                       "agent-file.sh check", "CHECK PASS", "CHECK FAIL", "never edit", "floor"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_fast_lane_deputy(self):
        text = read("agents", "fast-lane-deputy.md")
        self.assertEqual(LEVEL_WORDS.findall(text), [])
        for phrase in ("own git worktree", "EXAMPLES TEST", "example tests first", "agent-level.sh check",
                       "agent-file.sh check", "push", "2x its estimate", "second slice"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertNotIn("No worktree, no TDD", text)

    def test_merge_deputy(self):
        text = read("agents", "merge-deputy.md")
        self.assertEqual(LEVEL_WORDS.findall(text), [])
        self.assertIn("checks gate", text)
        self.assertLess(text.index("checks gate"), text.index("git merge --no-ff"))
        self.assertNotIn("ORIG_HEAD", text)             # section 42 B2: no test run at the merge, nothing to undo
        self.assertNotIn("reset --hard", text)
        given = [l for l in text.splitlines() if l.startswith("Your brief gives")][0]
        self.assertNotIn("<level>", given)
        self.assertIn("<session>", given)
        self.assertIn("<machine>", given)

    def test_worker_adds_an_edge_after_a_fix(self):
        self.assertIn("agent-file.sh edge add", read("agents", "worker.md"))


class TestThisRepo(unittest.TestCase):

    def conf(self):
        out = {}
        for line in read("agent_repo.conf").splitlines():
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out.setdefault(k, v)
        return out

    def test_version_1_with_the_test_commands(self):
        c = self.conf()
        self.assertEqual(c["version"], "1")
        self.assertEqual(c["related_cmd"], "python3 -m unittest {modules}")
        self.assertEqual(c["full_cmd"], "python3 tests/run2.py")   # approval-design F: 7.6 min, not 47
        # FIX ORDER 1 R5: the full run is heavy by a seeded weight, so MODULE TESTS of a deps change goes to the net
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import agent_level
        m = agent_level.WEIGHT_RE.match(c.get("weight.full", ""))
        self.assertTrue(m, c.get("weight.full"))
        self.assertTrue(agent_level.is_heavy((int(m.group(1)), int(m.group(2)))))
        self.assertTrue(c["build_cmd"].startswith("python3 -m compileall -q"))
        # test-slim-2: the plugin layout pins (TestPluginFolders, TestPluginManifest, ...) live in test_rules_text.py
        self.assertIn("tests/test_rules_text.py", c["guard_tests"].split(","))

    def test_core_paths_are_permission_and_owner_orders_not_rule_text(self):
        core = self.conf()["core_paths"].split(",")
        for path in ("bin/agent_guard.py", "bin/agent_owner_order.py", "hooks/", ".claude-plugin/"):
            self.assertIn(path, core)
        for path in ("PRINCIPLES.md", "skills/", "agents/"):
            self.assertNotIn(path, core)
        self.assertNotIn("level3_paths", self.conf())
        self.assertNotIn("level4_paths", self.conf())


class TestAgentFileHeader(unittest.TestCase):
    """Kick-off answer 4: --level and todo level still work for old callers; no doc names them as
    the way to work. The usage header of agent-file.sh says so on every line that names them."""

    def header(self):
        lines = []
        for line in read("bin", "agent-file.sh").splitlines():
            if not line.startswith("#"):
                break
            lines.append(line)
        return lines

    def test_level_lines_say_old_callers_only(self):
        hits = [l for l in self.header() if "--level" in l or "todo level" in l]
        self.assertTrue(hits)
        for l in hits:
            with self.subTest(line=l[:60]):
                self.assertIn("old callers", l)
                self.assertNotIn("risk type", l)

    def test_the_header_names_the_blocks_commands(self):
        text = "\n".join(self.header())
        for cmd in ("--checks", "todo checks", "todo est", "checks gate", "agent-file.sh next", "edge add",
                    "agent-file.sh check "):
            with self.subTest(cmd=cmd):
                self.assertIn(cmd, text)


class TestMemoryGate(unittest.TestCase):
    """Owner 2026-11-25 (TELL 076c1faf, section 24): no slots; a memory gate with a per-machine reservation
    list; CPU soft; jobs go to a connected machine first; what is sent away is cleaned up there."""

    def text(self):
        return read("PRINCIPLES.md")

    def test_s3_to_s6(self):
        s = text_between_after_start(self.text(), "S3. ", "S7. ")
        for phrase in ("memory in use now + the memory this run is known to need", "Load: Max memory %",
                       "measured peak MB", "never measured", "starts at once with a monitor on its memory",
                       "the newest, unmeasured one first", "records its peak MB", "tried again when there is room",
                       "Only test and build runs are stopped", "a Claude pane counts too",
                       "reservation list", "a dead pid frees its entry", "CPU", "the soft one", "the hard gate",
                       "Long but light runs just go", "agent-room.sh"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, s)

    def test_no_slots_and_no_special_machine_anywhere(self):
        for path in (("PRINCIPLES.md",), ("skills", "dispatch", "SKILL.md"), ("skills", "merge", "SKILL.md"),
                     ("agents", "merge-deputy.md"), ("agents", "fast-lane-deputy.md"), ("agents", "worker.md")):
            with self.subTest(path=path):
                text = read(*path).lower()
                for word in ("heavy-test slot", "heavy test slot", "heavy-test machine", "heavy_test_slots"):
                    self.assertNotIn(word, text)

    def test_placement(self):
        for start, end in (("W7. ", "W8. "), ("W9. ", "W10. ")):
            with self.subTest(rule=start):
                self.assertIn("connected machine first", text_between_after_start(self.text(), start, end))
        disp = read("skills", "dispatch", "SKILL.md")
        self.assertIn("connected machine first", disp)
        self.assertIn("agent-room.sh check", disp)

    def test_remote_cleanup(self):
        w8 = text_between_after_start(self.text(), "W8. ", "W9. ")
        for phrase in ("cleaned up there", "scratch clones", "temp test folders", "its reservation"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w8)
        self.assertIn("scratch clones", read("agents", "merge-deputy.md"))

    def test_s4_over_the_limit(self):
        s4 = text_between_after_start(self.text(), "S4. ", "S5. ")
        for phrase in ("start nothing new", "close done and idle panes first", "stop test runs before anything else",
                       "never stop a working agent", "tell the main manager", "agent-room.sh relief"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, s4)

    def test_s6_no_count_caps(self):
        s6 = text_between_after_start(self.text(), "S6. ", "S7. ")
        self.assertIn("No count caps", s6)
        self.assertIn("a new agent pane is admitted by the same rule", s6)
        self.assertNotIn("Max agents", self.text())
        self.assertNotIn("max_agents", read("skills", "dispatch", "SKILL.md"))

    def test_plugin_json_has_no_slot_setting(self):
        import json
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as fh:
            conf = json.load(fh)["userConfig"]
        self.assertNotIn("heavy_test_slots", conf)
        self.assertNotIn("max_agents", conf)
        self.assertEqual(len(conf), 17)   # + Reviewer model (owner 2A), Working branch, Auto clear after quiet


class TestKeepTheResultLines(unittest.TestCase):
    """Core review re-check defect A (b, c): a verified task's worktree is removed before the owner's yes
    (W8): its CHECK lines go to the main repo first; the REPORT carries them; the gate then runs on a
    scratch copy of the pushed branch."""

    def test_dispatch_step_8_gathers_first(self):
        text = read("skills", "dispatch", "SKILL.md")
        step8 = text_between_after_start(text, "\n8. ", "\n9. ")
        self.assertIn("agent-file.sh checks gather", step8)
        self.assertLess(step8.index("checks gather"), step8.index("remove its worktree"))

    def test_the_report_carries_the_check_lines(self):
        brief = text_between_after_start(read("skills", "dispatch", "SKILL.md"), "## Task manager brief", "## Cross-repo brief")
        report = [l for l in brief.splitlines() if l.startswith("REPORT:")][0]
        self.assertIn("CHECK lines", report)
        self.assertIn("indented", report)   # state add refuses a line that starts with CHECK

    def test_merge_runs_the_gate_on_a_scratch_copy_when_the_worktree_is_gone(self):
        text = read("skills", "merge", "SKILL.md")
        self.assertIn("scratch", text)
        self.assertIn("checks gather", text)

    def test_w8_says_so(self):
        w8 = text_between_after_start(read("PRINCIPLES.md"), "W8. ", "W9. ")
        self.assertIn("checks gather", w8)


class TestWorkingBranchRules(unittest.TestCase):
    """Owner 2026-11-25 (sections 28-29): one working-branch model for every repo."""

    def test_r1_target_from_the_request(self):
        r1 = text_between_after_start(read("PRINCIPLES.md"), "R1. ", "R2. ")
        for phrase in ("Merge into the target branch + cleanup", "the user's request decides",
                       "publish or merge to main", "straight into the production branch", "the deploy follows by itself",
                       "ap-main-<name>", "nothing goes to production by itself"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r1)

    def test_r8_the_model(self):
        r8 = text_between_after_start(read("PRINCIPLES.md"), "R8. Check blocks", "## B. Work")
        for phrase in ("Flow: Working branch", "the main checkout is switched to the working branch",
                       "never on the production branch by accident",
                       "when the last one of the batch is merged, ONE full suite runs on the working branch",
                       "per person", "ap-main-<name>", "worked out once per clone and stored", "every brief names the branch",
                       "never derives it again", "nobody else merges into it", "the sweep never deletes it",
                       "merged into the working branch at the start of a batch and again before a publish",
                       "agent-promote.sh --sync",
                       "only on the owner's approval", "only from a green commit",
                       "agent-promote.sh", "merged to production = published", "new fixer agent",
                       "never back to the builder"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r8)

    def test_w8_and_w9(self):
        w8 = text_between_after_start(read("PRINCIPLES.md"), "W8. ", "W9. ")
        for phrase in ("working branch", "agent-promote.sh --task", "a short-lived worktree of the production branch",
                       "production is merged back into the working branch at once"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w8)
        w9 = text_between_after_start(read("PRINCIPLES.md"), "W9. ", "W10. ")
        for phrase in ("branches from the production branch", "branches from the working branch", "--batch",
                       "may also wait until the working branch is tested and published",
                       "The target is per task, not per request",
                       "does an urgent task need code that only a non-urgent one brings",
                       "tell the owner at once", "never guess"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w9)

    def test_merge_deputy_merges_into_the_working_branch(self):
        text = read("agents", "merge-deputy.md")
        given = [l for l in text.splitlines() if l.startswith("Your brief gives")][0]
        self.assertIn("<working branch>", given)
        self.assertIn("git push origin <working branch>", text)
        self.assertNotIn("git push origin main", text)
        self.assertIn("agent-promote.sh --task", text)
        self.assertNotIn("--after-merge", text)

    def test_merge_skill(self):
        text = read("skills", "merge", "SKILL.md")
        for phrase in ("working branch", "new fixer agent", "never back to the builder", "agent-promote.sh"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn("working branch:", text_between_after_start(text, "name: <name>", "todo done arguments:"))

    def test_dispatch_and_init_skills(self):
        disp = read("skills", "dispatch", "SKILL.md")
        for phrase in ("--target production", "--batch", "--base-branch <base branch>", "publish or merge to main"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, disp)
        self.assertIn("working branch", read("skills", "init", "SKILL.md"))


class TestReviewIsTheMainCheck(unittest.TestCase):
    """Section 21 (owner and main manager, 2026-11-25; corrects section 19), for every repo on the plugin."""

    def r8(self):
        return text_between_after_start(read("PRINCIPLES.md"), "R8. Check blocks", "## B. Work")

    def test_r8_head(self):
        r8 = self.r8()
        head = r8[:r8.index("| Block |")]
        for phrase in ("let other agents verify the outcome of the code instead of letting test cases do it",
                       "PR REVIEW", "did not build it", "reads the diff against the approved requirement",
                       "the main check of every task", "its cost follows the diff size",
                       "only when what the user sees or does changed", "15-minute time box", "ideas file",
                       "light related tests", "a bug that a review or check finds gets a small test with its fix",
                       "The full suite is the safety net only", "URGENT FIX", "branch from the production branch",
                       "merge production back into the working branch"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, head)
        self.assertNotIn("runs the real thing once", r8)

    def test_r8_release_run_failures(self):
        r8 = self.r8()
        for phrase in ("agent-nightly.sh --failures", "test out of date", "real break",
                       "No check is deleted without a twin", "a table of these labels"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r8)

    def test_the_old_urgent_line_is_gone(self):
        self.assertNotIn("a verified owner order may move a block to right after the release", self.r8())

    def test_dispatch(self):
        text = read("skills", "dispatch", "SKILL.md")
        for phrase in ("PR REVIEW", "every task", "URGENT FIX", "branch from the production branch"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_merge_skill(self):
        text = read("skills", "merge", "SKILL.md")
        for phrase in ("URGENT FIX", "agent-promote.sh", "merge production back into the working branch",
                       "agent-nightly.sh --failures", "test out of date", "real break", "new fixer agent"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_check_deputy(self):
        # owner 2A: the PR REVIEW is the reviewer's (agents/reviewer.md); the check deputy runs FLOW and UI CHECK
        text = read("agents", "check-deputy.md")
        for phrase in ("FLOW CHECK", "UI CHECK", "15-minute", "only the approved items", "agent-file.sh idea add"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_no_retired_block_names_left(self):
        for path in (("PRINCIPLES.md",), ("skills", "dispatch", "SKILL.md"), ("skills", "merge", "SKILL.md"),
                     ("agents", "check-deputy.md"), ("agents", "fast-lane-deputy.md"), ("agents", "merge-deputy.md")):
            with self.subTest(path=path):
                text = read(*path)
                self.assertNotIn("DIFF READ", text)
                self.assertNotIn("OUTCOME CHECK", text)


class TestReviewer(unittest.TestCase):
    """Owner 2A 2026-11-25 (TELL 173d8a8b): "Models: Reviewer model" (default opus-5.5:high) runs the PR REVIEW
    of every task and the CORE REVIEW; R1 states the fixed sequence."""

    def test_the_setting(self):
        sys.path.insert(0, BIN)
        import agent_conf
        by = {x["key"]: x for x in agent_conf.SETTINGS}
        self.assertEqual((by["reviewer_model"]["title"], by["reviewer_model"]["default"]),
                         ("Models: Reviewer model", "opus-5.5:high"))
        self.assertTrue(agent_conf.validate_value("reviewer_model", "sonnet-5:high"), "a reviewer decides: floor")
        self.assertIsNone(agent_conf.validate_value("reviewer_model", "opus-5.5:high"))

    def test_the_reviewer_agent(self):
        text = read("agents", "reviewer.md")
        head = text.split("---")[1]
        self.assertIn("name: reviewer", head)
        self.assertIn("model: opus", head)
        tools = [l for l in head.splitlines() if l.startswith("tools:")][0]
        for tool in ("Read", "Grep", "Glob", "Bash"):
            self.assertIn(tool, tools)
        for tool in ("Edit", "Write"):
            self.assertNotIn(tool, tools)
        body = text.split("---", 2)[2]
        for phrase in ("Reviewer model", "PR REVIEW", "CORE REVIEW", "approved requirement", "nothing else",
                       "edge list", "no check deleted", "no secret", "agent-file.sh check", "fix order", "floor"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_r1_fixed_sequence(self):
        r1 = text_between_after_start(read("PRINCIPLES.md"), "R1. ", "R2. ")
        for phrase in ("builder reports done", "reviewer reads the diff against the approved requirement",
                       "check deputy only when what the user sees or does changed (15 min box)", "merge deputy",
                       "A fail at review or check goes back to the builder as a fix order", "Reviewer model"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r1)

    def test_merge_skill_sends_the_reviewer(self):
        text = read("skills", "merge", "SKILL.md")
        self.assertIn("subagent_type: reviewer", text)
        self.assertIn("reviewer_model", text)
        self.assertLess(text.index("subagent_type: reviewer"), text.index("subagent_type: check-deputy"))


# Scripts a human or a hook runs. These must carry the execute bit.
SHELL_SCRIPTS = [
    "agent-start.sh",
    "agent-file.sh",
    "agent-settings.sh",
    "agent-resume.sh",
    "agent-init.sh",
    "agent-runtime.sh",
    "agent-cloud-pack.sh",
    "agent-city.sh",
    "agent-city-hook.sh",
    "agent-name.sh",
    "agent-cleanup.sh",
    "agent-watch.sh",
    "agent-statusline.sh",   # progress-bar: the Claude Code status line
    "agent-housekeep.sh",    # housekeep-2h: the pass the watch loop runs
    "agent-version.sh",      # stale-plugin-guard: running vs installed, UserPromptSubmit hook
    "agent-level.sh",        # test-levels: the risk level a diff needs
    "agent-release.sh",      # plugin-slim: builds the release branch users install
]


# Sourced only, never run. agent-runtime.sh is in the list above instead,
# because it is both: sourced by its callers and run by a skill.
SOURCED_ONLY = [
    "agent-roots.sh",
    "agent-resources.sh",
]


BIN_FILES = SHELL_SCRIPTS + SOURCED_ONLY + ["agent_conf.py",
                                            "agent_city.py", "agent-city.html",
                                            "agent_estimate.py",
                                            "agent_cleanup.py",
                                            "agent_housekeep.py",
                                            "agent_level.py",
                                            "agent_release.py"]


AGENT_FILES = ["fast-lane-deputy.md", "interior-designer.md", "merge-deputy.md", "worker.md"]


SKILL_DIRS = ["dispatch", "merge", "init", "cloud-pack", "city", "close-case", "clean-up"]


ALLOW_RULES = [
    "Bash(git push origin --delete *)",
    "Bash(git branch -d *)",
    "Bash(git worktree remove *)",
    "Bash(git worktree prune)",
    "Bash(orca worktree rm *)",
    "Bash(orca terminal close *)",
]


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
        # plugin-slim (requirements/plugin-slim.md rule 13): users install the
        # release branch (the ship set only), never the whole repo ("./")
        self.assertEqual(entry[0]["source"], {
            "source": "url",
            "url": "https://github.com/maverick1014/auto-pipeline.git",
            "ref": "release",
        })
        self.assertEqual(entry[0]["description"],
                         "Agent pipeline rules, scripts, agents, skills and a startup quiz gate for any repo")


class TestHooksJson(unittest.TestCase):
    def command(self):
        data = load_json("hooks", "hooks.json")
        # the naming hook (tests/test_agent_name.py) is the second entry
        entries = [e for e in data["hooks"]["SessionStart"]
                   if "agent-name.sh" not in json.dumps(e)]
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


class TestCityHooks(unittest.TestCase):
    """The agent city listens to these events, all through one guarded command.

    With the city off, the guard is one `test -f` in the shell Claude Code
    starts anyway, so the hook script itself never runs.
    """

    COMMAND = ('[ -f "${AGENT_CITY_DIR:-$HOME/.cache/agent-city}/on" ] && '
               '"${CLAUDE_PLUGIN_ROOT}/bin/agent-city-hook.sh"; exit 0')
    EVENTS = ["PreToolUse", "PostToolUse", "PermissionRequest", "PermissionDenied",
              "SubagentStart", "SubagentStop", "Notification", "UserPromptSubmit",
              "Stop", "SessionEnd"]

    def hooks(self):
        """The city's entries only: the close-case hook
        (UserPromptSubmit, not the city's, tests/test_agent_close_case.py) and the naming hook
        (SessionStart, tests/test_agent_name.py) are left out."""
        hooks = load_json("hooks", "hooks.json")["hooks"]
        return {event: [e for e in entries
                        if "agent-close-case.sh" not in json.dumps(e)
                        and "agent-name.sh" not in json.dumps(e)
                        and "agent-keyword.sh" not in json.dumps(e)
                        # stale-plugin-guard: UserPromptSubmit, tests/test_agent_version.py
                        and "agent-version.sh" not in json.dumps(e)
                        # board-trust: the launch guard, tests/test_agent_guard.py
                        and "agent-guard.sh" not in json.dumps(e)
                        # check-blocks: the board warning hook, tests/test_agent_board.py
                        and "agent-board-warn.sh" not in json.dumps(e)]
                for event, entries in hooks.items()}

    # Interaction (tests/test_agent_city_interact.py): PermissionRequest also
    # runs the ask hook, which waits for the owner or the governor while the
    # terminal dialog stays usable; Stop also runs the governor watcher, in the
    # background, waking the governor session (no AGENT_ROLE) with exit 2.
    ASK_COMMAND = ('[ -f "${AGENT_CITY_DIR:-$HOME/.cache/agent-city}/on" ] && '
                   'python3 "${CLAUDE_PLUGIN_ROOT}/bin/agent_city.py" ask; exit 0')
    GOV_COMMAND = ('[ -z "${AGENT_ROLE:-}" ] && [ -f "${AGENT_CITY_DIR:-$HOME/.cache/agent-city}/on" ] && '
                   'exec python3 "${CLAUDE_PLUGIN_ROOT}/bin/agent_city.py" gov-watch; exit 0')
    # Talking (tests/test_agent_city_chat.py, owner 2026-09-27): the prompt
    # and each turn's last text go to chat.jsonl (say); a session with
    # AGENT_ROLE waits for the owner's message in the background (chat-watch).
    SAY_COMMAND = ('[ -f "${AGENT_CITY_DIR:-$HOME/.cache/agent-city}/on" ] && '
                   'python3 "${CLAUDE_PLUGIN_ROOT}/bin/agent_city.py" say; exit 0')
    CHAT_COMMAND = ('[ -n "${AGENT_ROLE:-}" ] && [ -f "${AGENT_CITY_DIR:-$HOME/.cache/agent-city}/on" ] && '
                    'exec python3 "${CLAUDE_PLUGIN_ROOT}/bin/agent_city.py" chat-watch; exit 0')
    SAY = {"hooks": [{"type": "command", "command": SAY_COMMAND, "timeout": 5}]}
    EXTRA = {
        "PermissionRequest": [{"hooks": [{"type": "command", "command": ASK_COMMAND, "timeout": 3660}]}],
        "Stop": [SAY,
                 {"hooks": [{"type": "command", "command": GOV_COMMAND, "async": True, "asyncRewake": True}]},
                 {"hooks": [{"type": "command", "command": CHAT_COMMAND, "async": True, "asyncRewake": True}]}],
        "UserPromptSubmit": [SAY],
        "SubagentStop": [SAY],
    }

    def test_each_event_has_one_city_entry(self):
        hooks = self.hooks()
        for event in self.EVENTS:
            with self.subTest(event=event):
                entries = hooks.get(event, [])
                self.assertEqual(len(entries), 1 + len(self.EXTRA.get(event, [])), entries)
                inner = entries[0]["hooks"]
                self.assertEqual(inner, [{"type": "command", "command": self.COMMAND,
                                          "timeout": 5}])

    def test_the_other_city_entries(self):
        hooks = self.hooks()
        for event, extra in self.EXTRA.items():
            with self.subTest(event=event):
                self.assertEqual(hooks[event][1:], extra)

    def test_the_off_path_of_the_new_commands_starts_nothing(self):
        base = tempfile.mkdtemp(prefix="layout_city_")
        self.addCleanup(shutil.rmtree, base, True)
        env = dict(os.environ, AGENT_CITY_DIR=os.path.join(base, "city"),
                   CLAUDE_PLUGIN_ROOT=os.path.join(base, "no-plugin"), HOME=base)
        env.pop("AGENT_ROLE", None)
        role_env = dict(env, AGENT_ROLE="task-manager")
        for command, e in ((self.ASK_COMMAND, env), (self.GOV_COMMAND, env), (self.SAY_COMMAND, env),
                           (self.CHAT_COMMAND, env), (self.CHAT_COMMAND, role_env)):
            with self.subTest(command=command, role=e.get("AGENT_ROLE", "")):
                result = subprocess.run(["sh", "-c", command], input=b"{}", env=e,
                                        capture_output=True, timeout=20)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))

    def test_pre_tool_use_only_for_the_three_tools(self):
        self.assertEqual(self.hooks()["PreToolUse"][0].get("matcher"),
                         "Agent|Task|AskUserQuestion")

    def test_the_other_events_have_no_matcher(self):
        hooks = self.hooks()
        for event in self.EVENTS[1:]:
            with self.subTest(event=event):
                self.assertNotIn("matcher", hooks[event][0])

    def test_session_start_has_no_city_hook(self):
        # The city is local and starts by /auto-pipeline:city; no SessionStart hook
        # touches it (no autostart probe, no event hook).
        entries = self.hooks()["SessionStart"]
        self.assertEqual(len(entries), 1, "agent-start only (hooks() leaves the naming hook out)")
        self.assertIn("agent-start.sh", json.dumps(entries[0]))
        self.assertNotIn("agent-city", json.dumps(entries))

    def test_nothing_else_is_hooked(self):
        self.assertEqual(sorted(self.hooks()), sorted(["SessionStart"] + self.EVENTS))

    def test_readme_names_the_city_script(self):
        self.assertIn("bin/agent-city.sh", read("PRINCIPLES.md"))


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


class TestCitySkill(unittest.TestCase):
    """/auto-pipeline:city starts the agent city in one step.

    The human never types the plugin's install path: the skill runs the
    start script and hands back the URL, and says how to stop it.
    """

    def text(self):
        return read("skills", "city", "SKILL.md")

    def test_it_runs_the_start_script_from_the_plugin_root(self):
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh start", self.text())

    def test_it_says_how_to_stop_and_the_demo(self):
        text = self.text()
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-city.sh stop", text)
        self.assertIn("#demo", text)

    def test_it_says_a_new_session_picks_up_the_hooks(self):
        self.assertIn("new session", self.text().lower())

    def test_readme_lists_the_command(self):
        self.assertIn("/auto-pipeline:city", read("README.md"))


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

    def test_the_w10_effort_comes_from_the_main_manager_setting(self):
        self.assertIn("Main manager model", self.w10())

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
        text = read("PRINCIPLES.md")
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
        self.assertIn("bin/agent-cloud-pack.sh", read("PRINCIPLES.md"))

    def test_it_shows_where_the_pack_lands(self):
        self.assertIn(".claude/auto-pipeline/", read("PRINCIPLES.md"))

    def test_it_gives_the_one_sentence_install(self):
        self.assertIn(
            "git clone https://github.com/maverick1014/auto-pipeline /tmp/ap"
            " && /tmp/ap/bin/agent-cloud-pack.sh .", read("PRINCIPLES.md"))

    def test_it_names_the_github_app(self):
        self.assertIn("Claude GitHub App", read("PRINCIPLES.md"))


class TestUserConfig(unittest.TestCase):
    """Claude Code asks these three at enable time, so setup needs no editing.

    Values reach a hook as CLAUDE_PLUGIN_OPTION_<KEY uppercased>.
    """

    # settings-configure (owner 1A 2026-11-25): the settings, the only settings source; check-blocks
    # (owner 2026-11-25): Max agents and Heavy test slot/time are gone, 14 settings
    KEYS = {"language": "string", "runtime": "string", "auto_update": "boolean",
            "main_manager": "string", "task_manager": "string", "reviewer_model": "string", "helper_model": "string",
            "max_usage_percent": "number",
            "permission_mode": "string", "auto_resume": "boolean", "todo_before_agent": "boolean", "working_branch": "string",
            "watch_quiet_min": "number", "housekeep_interval_min": "number", "clear_quiet_min": "number",
            "city_port": "number", "city_idle_min": "number"}   # owner 1A: no Danger paths
    DEFAULTS = {"runtime": "auto", "language": "en",
                "main_manager": "opus-5.5:high", "max_usage_percent": 80}

    def config(self):
        return load_json(".claude-plugin", "plugin.json")["userConfig"]

    def test_the_sixteen_keys_are_there_in_order(self):
        self.assertEqual(list(self.config()), list(self.KEYS))

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

    def test_manager_models_offer_high_and_xhigh(self):
        for key in ("main_manager", "task_manager"):
            self.assertEqual(self.config()[key]["options"][:2], ["opus-5.5:high", "opus-5.5:xhigh"])

    def test_nothing_here_is_a_secret(self):
        for key, entry in self.config().items():
            with self.subTest(key=key):
                self.assertFalse(entry.get("sensitive", False))

    def test_no_count_cap_setting(self):
        self.assertNotIn("max_agents", self.config())
        self.assertNotIn("heavy_test_slots", self.config())


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

    def test_principles_names_w12(self):
        self.assertIn("W12. Cross-repo", read("PRINCIPLES.md"))


class TestPrinciplesS4NamesRelief(unittest.TestCase):
    """S4 (usage cap) must tell an over-cap agent to run relief first."""

    def s4(self):
        text = read("PRINCIPLES.md")
        start = text.index("S4.")
        end = text.index("S5.")
        return text[start:end]

    def test_s4_mentions_relief(self):
        self.assertIn("relief", self.s4())


class TestThreatModel(unittest.TestCase):
    def test_r8_and_the_requirement(self):
        line = "the gate guards against mistakes and shortcuts made through the documented commands"
        self.assertIn(line, principles_between("R8. ", "W1. "))
        self.assertIn(line, read("requirements", "check-blocks.md"))


class TestRuleTexts(unittest.TestCase):
    def test_principles_w14(self):
        text = read("PRINCIPLES.md")
        w14 = text[text.index("W14. Todo board"):text.index("W15.")]
        for word in ("--who", "--after", "not started", "waiting on others", "first stage"):
            with self.subTest(word=word):
                self.assertIn(word, w14)

    def test_dispatch_board_records(self):
        text = read("skills", "dispatch", "SKILL.md")
        part = text[text.index("## Board records"):text.index("## Time question")]
        for word in ("--who", "--after"):
            with self.subTest(word=word):
                self.assertIn(word, part)

    def test_agent_file_header(self):
        head = "\n".join(l for l in read("bin", "agent-file.sh").splitlines()[:200] if l.startswith("#"))
        for word in ("--who", "--after", "wait run since", "started"):
            with self.subTest(word=word):
                self.assertIn(word, head)


class TestTheHookText(unittest.TestCase):
    """The whole-repo rule is the skill now (close-case part B); the hook is silent."""

    def part_b(self):
        return read("skills", "close-case", "SKILL.md").split("## B.", 1)[1]

    def test_it_asks_after_the_final_table(self):
        out = self.part_b()
        for phrase in ("whole repo", "/auto-pipeline:close-case", "agent_worktree.txt",
                       "final table", "yes or no", "language",
                       "nothing changes", "--clean", "/clear", "stay the main manager"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), out.lower())
        self.assertLess(out.index("final table"), out.index("yes or no"))

    def test_release_is_the_other_choice_not_the_last_step(self):
        out = self.part_b()
        self.assertLess(out.index("yes or no"), out.index("--release"))
        self.assertLess(out.index("--clean"), out.index("--release"))
        self.assertIn("never run it yourself", out)


class TestSkillAndRule(unittest.TestCase):

    def read(self, *parts):
        with open(os.path.join(os.path.dirname(HERE), *parts)) as fh:
            return fh.read()

    def test_the_init_skill_turns_fix_lines_into_edges(self):
        text = self.read("skills", "init", "SKILL.md")
        self.assertIn("agent_repo.conf", text)
        self.assertIn("# fix:", text)
        self.assertIn("edge=", text)
        self.assertIn("commit", text.lower())

    def test_after_a_bug_fix_the_fixer_adds_an_edge(self):
        for path in (("PRINCIPLES.md",), ("agents", "worker.md"), ("agents", "fast-lane-deputy.md")):
            with self.subTest(path=path):
                text = self.read(*path)
                self.assertIn("which example would have shown it", text)
                self.assertIn("agent-file.sh edge add", text)


class TestRuleText(unittest.TestCase):
    def w15(self):
        return section(read("PRINCIPLES.md"), "W15. Watch", "W16.").splitlines()

    def line_with(self, lines, *words):
        hits = [l for l in lines if all(w in l for w in words)]
        self.assertTrue(hits, "no line with %r in:\n%s" % (words, "\n".join(lines)))
        return hits[0]

    def test_g_w15_one_all_watch_for_every_task_manager(self):
        self.line_with(self.w15(), "agent-watch.sh --all", "agent_state.txt", "another machine", "background",
                       "=== REPORT ===")

    def test_e1_e2_w15_heartbeats_to_the_file_and_the_six_wakes(self):
        line = self.line_with(self.w15(), "HEARTBEAT", "ACK", "agent_state.txt", "SendMessage")
        for word in ("DONE PASS", "DONE FAIL", "QUESTION:", "MOCK READY", "CLOSE CASE", "STALL", "LOST"):
            self.assertIn(word, line)

    def test_g_w15_tell_start_resume_and_the_board(self):
        lines = self.w15()
        self.line_with(lines, "agent-file.sh tell")
        self.line_with(lines, "resume", "agent-watch.sh --all")
        self.line_with(lines, "not confirmed")

    def test_k_w14_status_line_rows(self):
        w14 = section(read("PRINCIPLES.md"), "W14. Todo board", "W15.").splitlines()
        line = self.line_with(w14, "statusline", "5 lines")
        for word in ("own row", "+N tasks", "warning"):
            self.assertIn(word, line)

    def test_g_dispatch_starts_or_restarts_one_all_watch(self):
        text = read("skills", "dispatch", "SKILL.md")
        steps = section(text, "# /dispatch", "## Board records")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-watch.sh --all", steps)
        self.assertNotIn("agent-watch.sh --terminal", text)
        at = steps.index("agent-watch.sh --all")
        near = steps[max(0, at - 300):at + 900]
        for word in ("run_in_background", "again", "MOCK READY", "STALL", "LOST"):
            self.assertIn(word, near)

    def test_e4_dispatch_sends_text_with_tell(self):
        steps = section(read("skills", "dispatch", "SKILL.md"), "# /dispatch", "## Board records")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh tell", steps)

    def test_e4_the_brief_template_reports_into_the_file(self):
        brief = section(read("skills", "dispatch", "SKILL.md"), "## Task manager brief", "## Cross-repo brief")
        for head in ("REPORT:", "ASK:", "HEARTBEAT:", "CLOSE:"):
            line = next(l for l in brief.splitlines() if l.startswith(head))
            self.assertIn("agent_state.txt", line, head)
            self.assertNotIn("SendMessage", line, head)

    def test_g_merge_skill_names_the_all_watch(self):
        self.assertTrue([l for l in read("skills", "merge", "SKILL.md").splitlines() if "agent-watch.sh --all" in l])

    def test_g_map_names_the_all_watch_and_tell(self):
        text = read("PRINCIPLES.md")
        self.assertIn("agent-watch.sh --all", text)
        self.assertIn("agent-file.sh tell", text)


def principles_code_between(code, nxt):
    """PRINCIPLES.md from the line "<code>. ..." up to the line "<nxt>. ..."."""
    with open(os.path.join(ROOT, "PRINCIPLES.md")) as fh:
        text = fh.read()
    start = text.index("\n%s. " % code)
    end = text.index("\n%s. " % nxt, start)
    return text[start:end]


class TestTheRules(unittest.TestCase):
    """One terse English line per rule, where they fit: W8 and S4."""

    def test_w8_names_the_sweep_and_when_it_runs(self):
        w8 = principles_code_between("W8", "W9")
        for words in ("agent-cleanup.sh --apply", "session start",
                      "last open task closes", "no loop"):
            self.assertIn(words, w8)

    def test_w8_says_who_never_runs_it(self):
        w8 = principles_code_between("W8", "W9")
        self.assertIn("Main manager only", w8)
        self.assertIn("never run it", w8)

    def test_w8_says_what_is_safe_and_what_is_never_deleted(self):
        w8 = principles_code_between("W8", "W9")
        for words in ("origin/main", "live agent", "uncommitted",
                      "unpushed", "never deleted", "one table",
                      "why kept"):
            self.assertIn(words, w8)

    def test_w8_says_own_repo_and_every_paired_machine(self):
        w8 = principles_code_between("W8", "W9")
        self.assertIn("own repo only", w8.lower())
        self.assertIn("paired", w8)
        self.assertIn("unreachable", w8)

    def test_s4_names_stop_leftovers(self):
        self.assertIn("stop-leftovers", principles_code_between("S4", "S5"))

    def test_s6_counts_busy_agents_only(self):
        s6 = principles_code_between("S6", "S7")
        for words in ("working or permission", "done", "not counted", "main manager"):
            self.assertIn(words, s6)
        self.assertNotIn("Counts spawned agents only", s6)

    def test_s6_says_who_closes_a_finished_pane_and_when_never(self):
        s6 = principles_code_between("S6", "S7")
        for words in ("closes it", "merged, dropped or closed",
                      "waiting on a merge, a question or a decision",
                      "another repo"):
            self.assertIn(words, s6)

    def test_w8_names_the_done_pane(self):
        w8 = principles_code_between("W8", "W9")
        self.assertIn("done pane", w8)
        self.assertIn("kept row", w8)

    def test_dispatch_step_6_counts_the_same_way(self):
        with open(os.path.join(ROOT, "skills", "dispatch", "SKILL.md")) as fh:
            step6 = next(l for l in fh.read().splitlines() if l.startswith("6. "))
        # check-blocks section 25 (owner 2026-11-25): no count cap; a new pane passes the memory rule
        self.assertIn("agent-room.sh check", step6)
        self.assertIn("done", step6)
        self.assertNotIn("max_agents", step6)

    def test_w14_names_the_owner_todo_marker(self):
        self.assertIn("`OWNER TODO:`", principles_code_between("W14", "W15"))

    def test_one_line_per_rule(self):
        for code, nxt in (("W8", "W9"), ("S4", "S5"), ("S6", "S7"), ("W14", "W15")):
            for line in principles_code_between(code, nxt).splitlines():
                if line.startswith("- "):
                    self.assertLessEqual(len(line), 200, line)

    def test_the_map_names_the_script(self):
        with open(os.path.join(ROOT, "PRINCIPLES.md")) as fh:
            self.assertIn("bin/agent-cleanup.sh", fh.read())


def block_after_head(text, head):
    start = text.index("\n" + head + "\n")
    end = text.find("\n\n", start + len(head) + 2)
    return text[start:end if end > 0 else len(text)]


class TestGuardRuleText(unittest.TestCase):
    def test_w14_launches_record_themselves(self):
        w14 = block_after_head(read("PRINCIPLES.md"), "W14. Todo board")
        self.assertIn("agent-guard.sh", w14)
        self.assertIn("no open todo task", w14)
        self.assertIn("Todo before agent", w14)
        self.assertNotIn("`worker on <n>` / `worker off <n>` for each worker;", w14)

    def test_dispatch_skill(self):
        s = read("skills", "dispatch", "SKILL.md")
        board = s[s.index("## Board records"):s.index("## Time question")]
        self.assertIn("agent-guard.sh", board)
        self.assertIn("todo add", board)
        self.assertNotIn("Record each worker: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worker on", s)

    def test_fast_lane_adds_the_todo_line_first(self):
        # review 16: the guard refuses "<task> Deputy" for a task with no todo line
        s = read("skills", "dispatch", "SKILL.md")
        step2 = [l for l in s.splitlines() if l.startswith("2. Small task")][0]
        self.assertIn("todo add", step2)

    def test_merge_skill_keeps_the_line_open_for_the_launch(self):
        s = read("skills", "merge", "SKILL.md")
        self.assertIn("agent-guard.sh", s)

    def test_readme(self):
        self.assertIn("bin/agent-guard.sh", read("PRINCIPLES.md"))

    def test_the_texts_name_the_setting(self):
        # settings-configure (owner 1A 2026-11-25): "Rules: Todo before agent", on by default,
        # replaces board_guard (old default record, owner 3A 2026-11-20)
        line = [l for l in read("PRINCIPLES.md").splitlines() if "bin/agent-guard.sh" in l][0]
        self.assertIn("Todo before agent", line)
        self.assertIn("off records only", line)
        w14 = block_after_head(read("PRINCIPLES.md"), "W14. Todo board")
        self.assertRegex(w14, r"on \(default\)")
        s = read("skills", "dispatch", "SKILL.md")
        board = s[s.index("## Board records"):s.index("## Time question")]
        self.assertIn("Todo before agent", board)
        self.assertIn("Todo before agent", read("skills", "merge", "SKILL.md"))

    def test_settings_hint(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        try:
            import agent_conf
        finally:
            sys.path.pop(0)
        by = {x["key"]: x for x in agent_conf.SETTINGS}
        self.assertEqual(by["todo_before_agent"]["title"], "Rules: Todo before agent")
        self.assertIsNone(agent_conf.validate_value("todo_before_agent", True))
        self.assertIsNotNone(agent_conf.validate_value("todo_before_agent", "maybe"))


class TestA1Texts(unittest.TestCase):
    def test_reviewer_and_check_deputy_pass_the_commit(self):
        for f in (("agents", "reviewer.md"), ("agents", "check-deputy.md")):
            with self.subTest(file=f[1]):
                line = [l for l in read(*f).splitlines() if "agent-file.sh check" in l][0]
                self.assertIn("--commit <head>", line)

    def test_merge_gives_the_head(self):
        self.assertIn("head: <sha>", read("skills", "merge", "SKILL.md"))

    def test_r8(self):
        self.assertIn("pass --commit <the head they looked at>", principles_between("R8. ", "W1. "))


class TestA2FastLaneBrief(unittest.TestCase):
    def test_dispatch_and_deputy(self):
        step2 = [l for l in read("skills", "dispatch", "SKILL.md").splitlines() if l.startswith("2. Small task")][0]
        for field in ("target:", "base:", "working branch:", "production branch:"):
            with self.subTest(field=field):
                self.assertIn(field, step2)
        dep = read("agents", "fast-lane-deputy.md")
        self.assertIn("`base:`", dep)
        self.assertIn("never derive", dep)


class TestA3FastLaneClickPath(unittest.TestCase):
    def test_report(self):
        report = read("agents", "fast-lane-deputy.md").split("Report (H3)")[1]
        self.assertIn("click path when FLOW CHECK or UI CHECK is planned", report)


class TestA4CreateThenReserve(unittest.TestCase):
    def test_dispatch(self):
        d = read("skills", "dispatch", "SKILL.md")
        self.assertNotIn("before `orca terminal create`", d.lower())
        # section 48 C24 changed the order again: reserve (pending) before the create, name it after
        self.assertLess(d.index("reserve-pane --pending"), d.index("orca terminal create"))
        self.assertLess(d.index("orca terminal create"), d.index("reserve-pane --name"))


class TestA6OneMeaning(unittest.TestCase):
    def test_deputy(self):
        dep = read("agents", "merge-deputy.md")
        self.assertNotIn("is not your job", dep)
        desc = [l for l in dep.splitlines() if l.startswith("description:")][0]
        self.assertNotIn("test command", desc)                    # B2: no test run at the merge
        self.assertIn("merged by `agent-promote.sh --task` (not by you)", dep)


class TestA7WatchRoom(unittest.TestCase):
    def test_dispatch_signals(self):
        self.assertIn("WATCH ROOM", read("skills", "dispatch", "SKILL.md"))


class TestA8Reviewer(unittest.TestCase):
    def test_tree_and_merge(self):
        tree = read("PRINCIPLES.md").split("## F. Map")[1]
        self.assertNotIn("Reviewer (Opus 5.5, high)", tree)
        self.assertIn("Reviewer model setting", tree)
        m = read("skills", "merge", "SKILL.md")
        self.assertIn("the model and the effort of the Reviewer model setting", m)


class TestA9NoSecondYes(unittest.TestCase):
    def test_three_places(self):
        for text in (principles_between("R8. ", "W1. "), read("skills", "dispatch", "SKILL.md"), read("skills", "merge", "SKILL.md")):
            self.assertNotIn("the owner's yes", text)
        self.assertIn("his verified words at dispatch, read as the publish of that task, are his final yes", principles_between("R8. ", "W1. "))   # approval-design


class TestWalks(unittest.TestCase):
    def test_the_demo_walks_both_flows(self):
        demo = read("tests", "check_blocks_demo.sh")
        self.assertIn("walk 1: a small task from dispatch to todo done", demo)
        self.assertIn("walk 2: a task with target production", demo)
        self.assertGreaterEqual(demo.count("--commit"), 2)


class TestA11ToA18Texts(unittest.TestCase):
    def test_a11_reviewer_and_check_deputy(self):
        rev = read("agents", "reviewer.md")
        self.assertIn("git diff <base>...<head>", rev)
        self.assertIn("no worktree needed", rev)
        self.assertIn("where the app runs", read("agents", "check-deputy.md"))

    def test_a12_three_session_values(self):
        self.assertIn("task manager | helper | fast-lane", read(*MERGE))
        self.assertIn("**a fast-lane subagent**", read(*DEPUTY))

    def test_a14_the_reviewer_model_mapping(self):
        self.assertIn("agent_conf.py cli-model", read(*MERGE))

    def test_a15_dispatch_template(self):
        step2 = [l for l in read("skills", "dispatch", "SKILL.md").splitlines() if l.startswith("2. Small task")][0]
        self.assertIn('--target production --owner-quote "<his words>" --means "publish <task> to production"', step2)   # approval-design: no fixed sentence

    def test_a16_no_diff_read(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import agent_checks
        self.assertNotIn("DIFF READ", agent_checks.BUILDER_BLOCKS)

    def test_a17_production_task_branch(self):
        dep = read(*DEPUTY)
        self.assertIn("git merge-base --is-ancestor origin/<branch> origin/<production branch>", dep)

    def test_a18_remote_gate_and_reservation(self):
        m = read(*MERGE)
        step4 = m[m.index("\n4. "):m.index("\n5. ")]
        self.assertIn("git worktree add --detach <scratch> origin/<branch>", step4)
        self.assertIn("goes by itself when its process ends", m + read(*DEPUTY))


class TestG13G14(unittest.TestCase):
    def test_g13_the_demo_uses_the_real_verify_and_the_owners_state(self):
        demo = read("tests", "check_blocks_demo.sh")
        self.assertNotIn("echo verified", demo)
        self.assertIn("CLAUDE_CONFIG_DIR", demo)
        self.assertIn("the owner's real state", demo)

    def test_g14_the_deputy_checks_before_force(self):
        dep = read("agents", "merge-deputy.md")
        self.assertIn("git -C <worktree path> log --oneline origin/<working branch>..HEAD", dep)   # approval-design E: <target> is no brief field
        i = dep.index("worktree remove --force")
        self.assertIn("clean", dep[max(0, i - 600):i])


class TestF1MergeDeputyChecksTheBranch(unittest.TestCase):
    def test_the_deputy_reads_the_branch_first(self):
        text = read("agents", "merge-deputy.md")
        for phrase in ("git branch --show-current", "push the branch the main checkout is on",
                       "still on the production branch", "merges go on as before", "any other branch: FAIL"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


class TestF6AndF7Texts(unittest.TestCase):
    def test_second_opinion_line(self):
        line = "Beyond the reviewer's PR REVIEW, a second agent's opinion only for CORE REVIEW"
        self.assertIn(line, principles_between("R8. ", "W1. "))
        self.assertIn(line, read("skills", "dispatch", "SKILL.md"))

    def test_merge_skill(self):
        merge = read("skills", "merge", "SKILL.md")
        self.assertNotIn("run the browser E2E", merge)
        self.assertNotIn("run the browser E2E", read("PRINCIPLES.md"))
        self.assertIn("send the reviewer and the check deputy", merge.split("\n---")[0])
        self.assertIn("No click path while FLOW CHECK or UI CHECK is planned", merge)
        for f in (merge, read("skills", "dispatch", "SKILL.md")):
            self.assertNotIn("merge main back into your branch", f)
            self.assertIn("merge its base branch back into your branch", f)


class TestP8LostTwin(unittest.TestCase):
    """The twin of a removed levels test, test_this_repo_has_its_file (removed with the levels)."""

    def test_this_repo_has_its_file(self):
        tracked = subprocess.run(["git", "-C", ROOT, "ls-files", "agent_repo.conf"], capture_output=True,
                                 text=True).stdout.strip()
        self.assertEqual(tracked, "agent_repo.conf")
        core = [l for l in read("agent_repo.conf").splitlines() if l.startswith("core_paths=")][0]
        for p in ("hooks/", ".claude-plugin/", "bin/agent_conf.py", "bin/agent_owner_order.py"):
            self.assertIn(p, core.split("=", 1)[1].split(","))


class TestAfterDoneFailAndLost(unittest.TestCase):
    """Section 38 (owner order 16:4x, TELL 10b4d922): what the main manager does after DONE FAIL and LOST."""

    def test_w15(self):
        w15 = principles_between("W15. ", "W16. ")
        lines = w15.splitlines()
        for phrase in ("DONE FAIL → the main manager reviews the report, then sends the task manager a fix order "
                       "(where, what is seen, what is expected, evidence). Never merged, never closed silently",
                       "LOST (the watch cannot reach a machine or a pane) → wait one more sweep; still lost → tell the "
                       "owner in one line with the machine and the task",
                       "Never redispatch a LOST task on another machine by itself"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, w15)
        signals = [i for i, l in enumerate(lines) if "wake the main manager" in l and "LOST" in l][0]
        self.assertTrue(lines[signals + 1].startswith("- DONE FAIL → "), lines[signals + 1])


class TestLeftoversTexts(unittest.TestCase):
    """Section 39 (TELL d2d93d25): what a newcomer reading PRINCIPLES.md still found."""

    def test_a_no_slots(self):
        text = read("PRINCIPLES.md")
        self.assertNotIn("suite slot", text)
        self.assertNotIn("free slot", text)
        self.assertNotIn("slot is free", text)

    def test_b_merged_means_either_branch(self):
        text = read("PRINCIPLES.md")
        self.assertNotIn("merged into origin/main", text)
        r5 = principles_between("R5. ", "R6. ")
        self.assertIn("merged into the working branch or the production branch", r5)
        sweep = [l for l in text.splitlines() if l.startswith("- Removes only safe items")][0]
        self.assertIn("merged into the working branch or the production branch", sweep)
        self.assertNotIn("merged into origin/main", read("bin", "agent-cleanup.sh"))

    def test_c_old_names(self):
        text = read("PRINCIPLES.md")
        self.assertNotIn("(E2E, then merge deputy)", text)
        self.assertIn("(the reviewer and the check deputy, then the merge deputy)", text)
        self.assertIn("Main manager: e2e (the review and the checks), merge", text)

    def test_d_agent_paths(self):
        w6 = principles_between("W6. ", "W7. ")
        self.assertNotIn(".claude/agents/", w6)
        for name in ("merge-deputy", "worker"):
            self.assertIn("`agents/%s.md`" % name, w6)


class TestSlimPassFacts(unittest.TestCase):
    """Section 40 (TELL e2fd5575): rule text that the code contradicts."""

    def test_1_models_by_setting(self):
        w6 = principles_between("W6. ", "W7. ")
        for role in ("Main manager", "Task manager"):
            line = [l for l in w6.splitlines() if l.startswith("- %s (" % role)][0]
            self.assertNotIn("xhigh", line, line)
            self.assertIn("%s model" % role, line)

    def test_2_start_runs_release_ok_checks(self):
        r8 = principles_between("R8. ", "W1. ")
        self.assertIn("`agent-nightly.sh --release-ok` only checks", r8)
        self.assertIn("`agent-nightly.sh --start` runs the full suite in the background", r8)

    def test_3_the_real_path(self):
        self.assertNotIn("./agent-file.sh", read("PRINCIPLES.md"))

    def test_4_r5_fields(self):
        r5 = principles_between("R5. ", "R6. ")
        for field in ("guess", "level"):
            self.assertIn(field, r5)

    def test_5_the_map_names_every_script(self):
        f = read("PRINCIPLES.md").split("## F. Map")[1]
        for name in ("agent-promote", "agent-runtime", "agent-resources", "agent-autoclear", "agent-release",
                     "agent-statusline", "agent-roots"):
            with self.subTest(name=name):
                self.assertIn(name, f)


class TestG3TheDeputyKnowsProduction(unittest.TestCase):
    def test_the_brief_names_it(self):
        dep = read("agents", "merge-deputy.md")
        self.assertIn("`<production branch>`", dep.split("Steps, in order")[0])
        self.assertIn("any other branch (release, master ...): FAIL", dep)
        self.assertIn("production branch:", read("skills", "merge", "SKILL.md"))


class TestG5DispatchCondition(unittest.TestCase):
    def test_step_9(self):
        line = [l for l in read("skills", "dispatch", "SKILL.md").splitlines() if l.startswith("9. Early merge")][0]
        self.assertNotIn("merged into main", line)
        self.assertIn("merged into its target branch", line)


class TestG9AndG10Texts(unittest.TestCase):
    def test_r8_names_both_switches(self):
        self.assertIn("init switches the main checkout of a new repo to the working branch; in a repo that already "
                      "uses the plugin the main manager switches it at a quiet point after the start's WORKING BRANCH "
                      "line", principles_between("R8. ", "W1. "))

    def test_dispatch_says_suite_run(self):
        d = read("skills", "dispatch", "SKILL.md")
        self.assertNotIn("suite slot", d)
        self.assertIn("suite run", d)


def rule_body_lines(text, head):
    lines = text.splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith(head))
    out = []
    for l in lines[i + 1:]:
        if l.startswith("## ") or re.match(r"^[A-Z]\d+\. ", l):
            break
        if l.strip():
            out.append(l)
    return out


def block_after(text, marker):
    """The first ``` code block after the line holding MARKER, as lines."""
    lines = text.splitlines()
    i = next(n for n, l in enumerate(lines) if marker in l)
    j = next(n for n in range(i + 1, len(lines)) if lines[n].strip().startswith("```"))
    k = next(n for n in range(j + 1, len(lines)) if lines[n].strip().startswith("```"))
    return [l.strip() for l in lines[j + 1:k]]


class TestDeciderFloorRuleText(unittest.TestCase):
    def setUp(self):
        self.text = read("PRINCIPLES.md")
        self.w17 = rule_body_lines(self.text, "W17. Decider floor")
        self.body = "\n".join(self.w17)

    def test_one_line_per_rule(self):
        self.assertGreaterEqual(len(self.w17), 6)
        for line in self.w17:
            with self.subTest(line=line[:40]):
                self.assertTrue(line.startswith("- "))
                self.assertLessEqual(len(line), 200)

    def test_who_and_the_floor(self):
        for words in ("main manager", "task manager", "reviewer", "Opus 5.5", "Fable", "medium",
                      "Sonnet", "Haiku"):
            with self.subTest(words=words):
                self.assertIn(words, self.body)
        self.assertTrue(re.search(r"Sonnet and Haiku never decide", self.body))

    def test_sending(self):
        self.assertIn("[Opus 5.5 xhigh]", self.body)
        self.assertIn("model and effort", self.body)
        self.assertIn("not orders", self.body)
        for word in ("Reports", "heartbeats", "questions"):
            self.assertIn(word, self.body)

    def test_receiving(self):
        low = self.body.lower()
        for words in ("do not act", "ask the sender", "tell the human", "exempt", "helper"):
            with self.subTest(words=words):
                self.assertIn(words, low)

    def test_own_values_and_the_validator(self):
        self.assertIn("YOU:", self.body)
        self.assertIn("agent_conf.py", self.body)

    def test_w12_first_line(self):
        line = next(l for l in self.text.splitlines() if l.startswith("- Send the brief"))
        self.assertIn("[<model> <effort>] CROSS-REPO TASK <name> from <repo>", line)


class TestSkillText(unittest.TestCase):
    TAG = "[<model> <effort>]"

    def test_dispatch(self):
        text = read("skills", "dispatch", "SKILL.md")
        self.assertTrue(block_after(text, "## Task manager brief")[0].startswith(
            self.TAG + " Brief from the main manager"))
        self.assertTrue(block_after(text, "## Cross-repo brief")[0].startswith(
            self.TAG + " CROSS-REPO TASK <name> from <repo>"))
        brief = block_after(text, "## Task manager brief")
        step4 = next(l for l in brief if l.startswith("4 workers"))
        self.assertIn(self.TAG, step4)
        fast = next(l for l in text.splitlines() if l.startswith("2. Small task"))
        self.assertIn(self.TAG, fast)
        self.assertIn("YOU:", text)

    def test_merge(self):
        text = read("skills", "merge", "SKILL.md")
        self.assertTrue(block_after(text, "subagent_type: merge-deputy")[0].startswith(self.TAG))
        self.assertIn("YOU:", text)

    def test_close_case(self):
        text = read("skills", "close-case", "SKILL.md")
        self.assertIn(self.TAG + " close case", text)
        finish = next(l for l in text.splitlines() if "**finish first**" in l)
        self.assertIn(self.TAG, finish)
        self.assertIn("YOU:", text)


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
        text = read("tests", "test_agent_settings.py")
        self.assertIn('"unused_pane_min": 30', text)


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


class TestBypassRuleText(unittest.TestCase):
    def w10(self):
        text = read("PRINCIPLES.md")
        return text[text.index("W10. "):text.index("W11. ")]

    def test_w10_launch_line_reads_the_mode(self):
        w10 = self.w10()
        self.assertIn("--permission-mode <mode>", w10)
        self.assertNotIn("--permission-mode auto", w10)

    def test_w10_says_which_key_for_which_terminal(self):
        w10 = self.w10()
        self.assertIn("Permission mode", w10)
        self.assertNotIn("cloud_permission_mode", w10)
        self.assertNotIn("cloud page", w10)

    def test_no_literal_auto_launch_anywhere_in_the_rules(self):
        self.assertNotIn("--permission-mode auto", read("PRINCIPLES.md"))

    def test_the_local_click_line_keeps_permission_mode(self):
        text = read("requirements", "city.md")
        line = next(l for l in text.splitlines() if l.startswith("- Click → the local server opens ONE new session"))
        self.assertIn("`permission_mode`", line)


class TestMergeSkillLine(unittest.TestCase):
    """Written now, passes only after "main merged" (skills/merge belongs to
    one-watcher until then)."""

    def test_the_merge_skill_names_the_release_step(self):
        with open(os.path.join(ROOT, "skills", "merge", "SKILL.md")) as fh:
            lines = fh.read().splitlines()
        hits = [l for l in lines if "bin/agent-release.sh --push" in l]
        self.assertEqual(len(hits), 1, "one line with bin/agent-release.sh --push")
        # check-blocks section 28 (owner 2026-11-25): the publish is agent-promote.sh, the release build right after
        self.assertIn("agent-promote.sh --owner-quote", hits[0])
        self.assertIn("--means", hits[0])   # approval-design: what the main manager read from his words
        self.assertIn("right after", hits[0])
        self.assertIn("auto-pipeline", hits[0])


class TestAgentText(unittest.TestCase):
    def test_every_executing_agent_checks(self):
        for name in ("worker.md", "merge-deputy.md", "fast-lane-deputy.md"):
            with self.subTest(agent=name):
                text = read("agents", name)
                line = next((l for l in text.splitlines()
                             if "model and effort" in l and "Opus 5.5" in l), None)
                self.assertIsNotNone(line, "no receiving check line")
                for word in ("Fable", "medium"):
                    self.assertIn(word, line)
                self.assertIn("do not act", text.lower())
                self.assertIn("human", text.lower())


class TestH2Texts(unittest.TestCase):
    def test_no_fixed_sentence_is_left(self):
        # approval-design (section 53 A1): the owner picked C, the interim sentences of section 51 H2 go
        texts = [("PRINCIPLES.md",), DISPATCH, MERGE, DEPUTY, ("README.md",), ("agents", "reviewer.md"),
                 ("agents", "fast-lane-deputy.md"), ("skills", "close-case", "SKILL.md")]
        for parts in texts:
            text = read(*parts)
            for gone in ("yes, publish", "yes, skip", "type exactly", "types exactly", "the one sentence"):
                with self.subTest(file="/".join(parts), gone=gone):
                    self.assertNotIn(gone, text)

    def test_the_open_design_section(self):
        req = read("requirements", "check-blocks.md")
        self.assertIn("## 52. Approval design, open for the owner", req)
        self.assertIn("## 53. Approval design: the owner picked C", req)


class TestApprovalCases(unittest.TestCase):
    """approval-design (requirements/check-blocks.md section 53 B, owner 2026-11-26): the agent reads his words;
    the cases are written once in R8, R1, W9, W12 and skills/dispatch agree."""

    def r8(self):
        return principles_between("R8. ", "## B. Work")

    def test_r8_holds_the_rule(self):
        r8 = self.r8()
        for phrase in ("reads his words", "no fixed sentence", "no word list", "--owner-quote", "--means",
                       "--question", "under 20 characters", "whole prompt", "OWNER WORDS",
                       "PR REVIEW and OWNER SIGN are never removed"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r8)

    def test_r8_holds_the_five_cases(self):
        r8 = self.r8()
        for phrase in ("numbered batch", "2. publish direct after done, others wait for my review",
                       "by its description", "exactly one fits", "two similar tasks", "check first",
                       "one question that names both", "is it ready to publish?", "publish next week",
                       "a refusal", "publish after the tests pass", "short answer to a numbered question"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r8)

    def test_the_cases_are_written_once(self):
        self.assertEqual(read("PRINCIPLES.md").count("is it ready to publish?"), 1)

    def test_r1_w9_w12_point_to_the_cases(self):
        for start, end in (("R1. ", "R2. "), ("W9. ", "W10. "), ("W12. ", "W13. ")):
            with self.subTest(rule=start):
                self.assertIn("approval cases", principles_between(start, end))
        self.assertNotIn("that name the action", principles_between("W12. ", "W13. "))

    def test_r8_promote_line_takes_means(self):
        self.assertIn('agent-promote.sh --owner-quote "<his words>" --means "<what you read>"', self.r8())

    def test_r8_says_who_launches_the_reviewer(self):
        r8 = self.r8()
        self.assertIn("PR REVIEW, FLOW CHECK and UI CHECK count only from a reviewer or check deputy the main manager launched", r8)

    def test_dispatch_agrees(self):
        d = read(*DISPATCH)
        for phrase in ("approval cases", "--means", "--question", "numbered batch", "by its description",
                       "two similar tasks", "publish next week"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, d)

    def test_merge_repeats_the_owner_words(self):
        self.assertIn("OWNER WORDS", read(*MERGE))

    def test_the_deputy_fast_lane_case(self):
        dep = read(*DEPUTY)
        self.assertNotIn("origin/<target>", dep)
        line = next(l for l in dep.splitlines() if "**a fast-lane subagent**" in l)
        self.assertIn("origin/<working branch>..HEAD", line)
        self.assertIn("origin/<production branch>..HEAD", line)
        self.assertIn("git branch -D <branch>", line)

    def test_section_f_names_md_slim(self):
        line = next(l for l in read("PRINCIPLES.md").splitlines() if l.startswith("Agent skills:"))
        self.assertIn("/auto-pipeline:slim-markdown", line)   # S6: md-slim renamed
        self.assertIn("/auto-pipeline:teacher-teach-me", line)   # TELL 9594c165: the skill main got in e198fbe


class TestH3ToH5(unittest.TestCase):
    def test_h3_the_fixer_is_a_normal_task(self):
        m = read("skills", "merge", "SKILL.md")
        line = [l for l in m.splitlines() if "fixer" in l][0]
        for phrase in ("todo add", "target", "base", "PR REVIEW", "gate", "agent-nightly.sh --start"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, line)

    def test_h4_where_the_app_runs(self):
        self.assertIn("where the app runs:", read("skills", "merge", "SKILL.md"))

    def test_h5_the_local_branch_before_minus_d(self):
        self.assertIn("git merge-base --is-ancestor <branch> origin/<production branch>", read("agents", "merge-deputy.md"))


class TestFixOrder1Texts(unittest.TestCase):
    """FIX ORDER 1 (TELL cdacc0c5) R2, R3, R6: the rule text of the late yes, the relayed order and the wording."""

    def r8(self):
        return principles_between("R8. ", "## B. Work")

    def test_r2_the_late_yes_case(self):
        r8 = self.r8()
        # FIX ORDER 2 S1: no rebase, no force push: a new fast-lane deputy cherry-picks onto a new branch
        for phrase in ("todo target <task> production", "a new fast-lane deputy", "a new branch from the production branch",
                       "cherry-pick", "every planned block runs again at its head", "<task>-publish",
                       "depends on other unreleased work"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, r8)
        self.assertNotIn("rebase --onto", read("PRINCIPLES.md"))
        self.assertNotIn("force", r8.lower().replace("enforce", ""))
        self.assertIn("todo target", read(*DISPATCH))

    def test_r3_the_relayed_order(self):
        self.assertIn("--relayed-from", principles_between("W12. ", "W13. "))
        self.assertIn("--relayed-from", self.r8())

    def test_r6_no_words_that_name_the_publish(self):
        for parts in (DISPATCH, MERGE, ("PRINCIPLES.md",)):
            with self.subTest(file="/".join(parts)):
                self.assertNotIn("name the publish", read(*parts))

    def test_r6_the_others_wait_on_the_working_branch(self):
        self.assertIn("the others merge into the working branch and wait there for his review", self.r8())

    def test_r6_publish_next_week_is_parked(self):
        line = next(l for l in self.r8().splitlines() if "publish next week" in l)
        self.assertIn("OWNER TODO", line)

    def test_r6_a_hook_points_to_a_skill_or_a_rule(self):
        text = read("PRINCIPLES.md")
        self.assertIn("only points to a skill or a rule", text)
        line = next(l for l in text.splitlines() if "bin/agent-keyword.sh" in l and "UserPromptSubmit" in l)
        self.assertIn("skill or rule", line)

    def test_r6_the_check_usage_names_the_approval_options(self):
        head = read("bin", "agent-file.sh").split("\nset ")[0]
        line = next(l for l in head.splitlines() if "agent-file.sh check " in l)
        for opt in ("--owner-quote", "--means", "--question"):
            with self.subTest(opt=opt):
                self.assertIn(opt, line)


class TestFixOrder2Texts(unittest.TestCase):
    """FIX ORDER 2 (TELL f68297ca) S1-S4: the rule text."""

    def r8(self):
        return principles_between("R8. ", "## B. Work")

    def test_s1_the_fast_lane_deputy_case(self):
        dep = read("agents", "fast-lane-deputy.md")
        for phrase in ("cherry-pick", "git switch -c <new branch> origin/<production branch>",
                       "git rev-list --reverse --no-merges origin/<working branch>..origin/<branch>",
                       "<task>-publish", "conflict",
                       # an already merged task: its own commits are the second parent side of its merge commit
                       "git rev-list --reverse --no-merges <merge commit>^1..<merge commit>^2"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, dep)
        self.assertNotIn("rebase", dep)

    def test_s1_the_merge_deputy_deletes_the_old_branch(self):
        self.assertIn("old branch", read(*DEPUTY))

    def test_s2_where_the_question_stands(self):
        self.assertIn("the question stands in the assistant message right before his prompt", self.r8())
        self.assertIn("a whole line or sentence", self.r8())

    def test_s3_another_machine_goes_to_the_owner(self):
        # T3 (TELL 7ae473b6): the relay lines stand once, in R8; W12 points to them
        line = next(l for l in self.r8().splitlines() if "another machine" in l and "cannot be verified here" in l)
        self.assertIn("owner", line)
        self.assertIn("main manager lock", self.r8())
        text = read("PRINCIPLES.md")
        self.assertEqual(text.count("cannot be verified here"), 1)
        self.assertEqual(text.count("must be a repo with a main manager lock"), 1)
        w12 = next(l for l in principles_between("W12. ", "W13. ").splitlines() if "--relayed-from" in l)
        self.assertIn("R8", w12)

    def test_s4_usage_shows_relayed_from(self):
        head = read("bin", "agent-file.sh").split("\nset ")[0]
        for start in ("agent-file.sh todo checks", "todo add also takes"):
            with self.subTest(line=start):
                line = next(l for l in head.splitlines() if start in l and "--owner-quote" in l)
                self.assertIn("--relayed-from", line)


class TestS6SkillRename(unittest.TestCase):
    """FIX ORDER 2 S6 (TELL 7e677c4d, owner 2026-11-26 "test-slim and md-slim rename abit to slim-test-case to
    slim-markdown"): the two skills carry their new names everywhere; task names in history stay."""

    NEW = {"slim-test-case": "test-slim", "slim-markdown": "md-slim"}

    def test_s6_the_folders_and_frontmatter(self):
        for new, old in self.NEW.items():
            with self.subTest(skill=new):
                self.assertFalse(os.path.exists(os.path.join(ROOT, "skills", old)), old)
                text = read("skills", new, "SKILL.md")
                self.assertIn("\nname: %s\n" % new, "\n" + text)
                self.assertIn("\n# /%s" % new, text)
                self.assertNotIn("/auto-pipeline:%s" % old, text)

    def test_s6_principles_and_readme_name_the_new_skills(self):
        line = next(l for l in read("PRINCIPLES.md").splitlines() if l.startswith("Agent skills:"))
        readme = read("README.md")
        for new, old in self.NEW.items():
            with self.subTest(skill=new):
                self.assertIn("/auto-pipeline:%s" % new, line)
                self.assertIn("| `/auto-pipeline:%s` |" % new, readme)
                self.assertNotIn("/auto-pipeline:%s" % old, line + readme)

    def test_s6_the_tools_name_the_new_skill(self):
        for f in ("agent_test_audit.py", "agent_test_time.py"):
            with self.subTest(tool=f):
                text = read("bin", f)
                self.assertIn("slim-test-case skill", text)
                self.assertNotIn("test-slim skill", text)

    def test_s6_no_old_skill_name_is_left(self):
        pat = re.compile(r"auto-pipeline:(test-slim|md-slim)\b|skills/(test-slim|md-slim)\b|\b(test-slim|md-slim) skill\b")
        files = subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True, text=True, check=True).stdout.split()
        hits = []
        for f in files:
            if not f.endswith((".md", ".py", ".sh", ".json")) or f.startswith("requirements/") \
                    or f == "tests/test_rules_text.py" or not os.path.exists(os.path.join(ROOT, f)):
                continue
            for n, line in enumerate(read(f).splitlines(), 1):
                if pat.search(line):
                    hits.append("%s:%d" % (f, n))
        self.assertEqual(hits, [])


class TestParallelDefault(unittest.TestCase):
    def test_p1_tasks_run_in_parallel_two_cases_only(self):
        text = read("PRINCIPLES.md")
        block = text.split("P1. Fastest correct way", 1)[1].split("\n\n", 1)[0]
        for phrase in (
            "- Parallel first: tasks run on their own branches; the one that merges second resolves the conflict. For an agent that is minutes, cheaper than waiting",
            "- Parallel also for the same module in a different part, and for a conflict in text that is not logic (docs, lists, wording)",
            "- One exception: a follow-up on the logic an agent is changing right now goes to that agent. Two agents changing the same logic is a disaster",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, block)
        for gone in (
            "only when resolving would cost more than waiting",
            "one moves or renames many files the other edits",
        ):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, text)
        self.assertNotIn("only when that check shows a real overlap", text)

    def test_w9_follow_up_goes_to_the_task_manager(self):
        text = read("PRINCIPLES.md")
        block = text.split("W9. Task routing", 1)[1].split("\n\n", 1)[0]
        self.assertIn("must go to that task manager (P1), never to a second agent", block)
        for path in ("PRINCIPLES.md", "skills/dispatch/SKILL.md"):
            with self.subTest(path=path):
                self.assertNotIn("in the two cases of P1", read(path))


class TestT2T3Texts(unittest.TestCase):
    """TELL 7ae473b6 T2: the late-yes brief fields are named where the deputies are briefed."""

    def test_t2_the_merge_brief_template_has_the_fields(self):
        m = read(*MERGE)
        for field in ("late yes of:", "old branch:"):
            with self.subTest(field=field):
                self.assertIn(field, m)

    def test_t2_dispatch_step_2_and_r8_name_them(self):
        step2 = next(l for l in read(*DISPATCH).splitlines() if l.startswith("2. Small task"))
        r8 = principles_between("R8. ", "## B. Work")
        for field in ("late yes of:", "old branch:"):
            with self.subTest(field=field):
                self.assertIn(field, step2)
                self.assertIn(field, r8)

    def test_t2_a_publish_line_copies_the_planned_blocks(self):
        r8 = principles_between("R8. ", "## B. Work")
        line = next(l for l in r8.splitlines() if "<task>-publish" in l)
        self.assertIn("--checks", line)

