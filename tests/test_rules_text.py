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
