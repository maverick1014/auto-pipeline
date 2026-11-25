"""Tests of rules-text, one class per feature."""

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
        # test-levels (2026-11-20): Q38 and Q39 (R8)
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", text)), 39)


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
        # dispatch text no longer names --environment/--shell or "until merged" (tests/test_watch_board.py)
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
        self.assertRegex(text, r"(?i)16 settings|sixteen settings")

    def test_r8_is_main_s_text(self):
        # owner 3A 2026-11-25: the level rules are frozen; R8 stays exactly as on main (85b99de)
        main = subprocess.run(["git", "-C", ROOT, "show", "85b99de:PRINCIPLES.md"],
                              capture_output=True, text=True).stdout
        if not main:
            self.skipTest("85b99de not in this clone")
        def r8(text):
            return text[text.index("R8. Risk types"):text.index("## B. Work")]
        self.assertEqual(r8(read("PRINCIPLES.md")), r8(main))

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

    def test_release(self):
        ver = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        # test-levels (2026-11-20) released 0.36.0 on top: at least 0.35.0, like the other release tests
        self.assertGreaterEqual(tuple(int(x) for x in ver.split(".")), (0, 35, 0))


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
        for wait in ("mock gate", "owner question", "review", "hold", "suite slot"):
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
        step2 = text_between(self.text(), "\n2. ", "\n3. ")
        self.assertIn("todo done", step2)
        self.assertIn("--lane fast", step2)
        self.assertIn("--work", step2)

    def test_the_brief_report_has_the_new_time_line(self):
        self.assertIn(TIME_LINE, self.brief())

    def test_the_old_human_minutes_are_gone(self):
        self.assertNotIn("human <n>m", self.text())

    def test_the_brief_says_what_counts_as_wait(self):
        report = [l for l in self.brief().splitlines() if l.startswith("REPORT:")][0]
        for phrase in ("agent work only", "mock gate", "suite slot"):
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

    def test_release_0_37_0(self):
        data = json.loads(read(".claude-plugin", "plugin.json"))
        # board-waiting ships 0.38.0 (2026-11-20): 0.37.0 or later
        self.assertGreaterEqual(tuple(int(n) for n in data["version"].split(".")), (0, 37, 0))


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

    def test_the_release(self):
        ver = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        self.assertGreaterEqual(tuple(int(x) for x in ver.split(".")), (0, 34, 0))


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
