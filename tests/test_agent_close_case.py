"""Failing tests for 'close case'. Written by the task manager first.

Owner, 2026-09-28: "track the keyword 'close case': it does the settle-down
job, sends to its upper level to close it, and all of the summary passes to
the upper agent."

CONTRACT. bin/agent-close-case.sh is a UserPromptSubmit hook (hooks.json).
Claude Code gives it the prompt as JSON on stdin; what it prints on stdout is
added to the session's context. It never blocks a prompt: always exit 0,
nothing on stderr, and it writes no file.

    trigger   the words close case, any case, anywhere in the prompt, any
              white space between them (\\bclose\\s+case\\b)
    no        a quoted mention: a quote mark or backtick right before the
              words ("close case", 'close case', `close case`, curly quotes).
              A brief that explains the rule quotes it, so it never fires
    no        close-case (the task's name), closed case, close cases
    silent    no keyword, empty or bad stdin, a project with no agent.conf
              (the plugin is not on in that repo)

The project and the session's name come from the stdin JSON "cwd": project =
the main worktree (agent-roots.sh), name = the folder name of the git
toplevel of that cwd (a task manager's worktree folder = its task name).

Role, the same way agent-start.sh decides it:

    AGENT_ROLE set                        task manager (spawned)
    no lock, or lock pid == this session  main manager
    lock pid alive, not this session      task manager, human-direct
    lock pid dead, not this session       human-direct, no live main manager:
                                          print the report here, the human
                                          decides

    this session = $CLAUDE_PID, else the first claude ancestor (agent_pid,
    now in agent-roots.sh, shared with agent-start.sh)

What it prints:

    task manager / human-direct   the settle-down job: start nothing new, let
        workers finish or stop, save agent_state.txt, commit + push (WIP
        commit if unfinished), then the report to the main manager with
        SendMessage (another machine: print it here), first line
        CLOSE CASE <name>: finished | CLOSE CASE <name>: unfinished, then
        done, left + next steps, tests, E2E click path, new ideas, TIME
        line. Then wait for the decision. Never close yourself.
    main manager, prompt carries one or more report lines
        "CLOSE CASE <name>: finished|unfinished" -> each report named with
        its status, then: finished -> /auto-pipeline:merge; unfinished ->
        finish first or close now (/auto-pipeline:close-case), log the
        decision in agent_state.txt, human away -> "owner not seen"
    main manager, anything else -> the whole repo wraps up:
        /auto-pipeline:close-case, every live session in agent_worktree.txt,
        one final table

Every text also says: only a mention of the words -> ignore this. Every text
fits in 1200 bytes.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase

HOOK_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-close-case.sh'
HOOK_ENTRY = {"hooks": [{"type": "command", "command": HOOK_COMMAND, "timeout": 10}]}
MAX_BYTES = 1200
NOBODY = "999999"   # a CLAUDE_PID no lock ever names


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def dead_pid():
    """A pid that surely belongs to nobody now: a reaped child's."""
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


def section(text, start, end):
    """The text from the line starting with `start` up to the line starting with `end`."""
    lines = text.splitlines()
    begin = next(i for i, line in enumerate(lines) if line.startswith(start))
    stop = next(i for i in range(begin + 1, len(lines)) if lines[i].startswith(end))
    return "\n".join(lines[begin:stop])


def dispatch_brief():
    """The task manager brief template of the dispatch skill."""
    return section(read("skills", "dispatch", "SKILL.md"),
                   "## Task manager brief", "## Cross-repo brief")


class CloseCaseCase(ScriptCase):
    script = "agent-close-case.sh"

    def payload(self, prompt, cwd=None):
        return json.dumps({
            "session_id": "s-close",
            "transcript_path": "/tmp/none.jsonl",
            "cwd": cwd or self.repo.cwd,
            "permission_mode": "auto",
            "hook_event_name": "UserPromptSubmit",
            "prompt": prompt,
        })

    def set_lock(self, pid):
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%s 2026-09-28 10:00\n" % pid)

    def hook(self, prompt, env=None, stdin=None, cwd=None):
        """Run the hook; exit 0 and an empty stderr, always. Returns stdout."""
        result = self.repo.run("agent-close-case.sh", env=env or {},
                               stdin=self.payload(prompt, cwd) if stdin is None else stdin,
                               cwd=cwd)
        self.assertOk(result)
        self.assertEqual(result.stderr, "", result.stderr)
        return result.stdout

    # ---- the four roles ----

    def as_task_manager(self, prompt, **kw):
        self.set_lock(os.getpid())
        return self.hook(prompt, env={"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY}, **kw)

    def as_human_direct(self, prompt, **kw):
        self.set_lock(os.getpid())
        return self.hook(prompt, env={"CLAUDE_PID": NOBODY}, **kw)

    def as_orphan(self, prompt, **kw):
        self.set_lock(dead_pid())
        return self.hook(prompt, env={"CLAUDE_PID": NOBODY}, **kw)

    def as_main(self, prompt, **kw):
        self.set_lock(os.getpid())
        return self.hook(prompt, env={"CLAUDE_PID": str(os.getpid())}, **kw)

    def assertReportAsk(self, out, name):
        """The settle-down job of a task manager or a human-direct session."""
        for phrase in ("CLOSE CASE %s: finished" % name,
                       "CLOSE CASE %s: unfinished" % name,
                       "agent_state.txt", "WIP", "push", "next steps",
                       "click path", "ideas", "TIME:", "Never close yourself",
                       "only a mention"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), out.lower())
        self.assertNotIn("whole repo", out)
        self.assertLessEqual(len(out.encode()), MAX_BYTES)


class TestItStaysQuiet(CloseCaseCase):
    def test_no_keyword_prints_nothing(self):
        self.assertEqual(self.as_task_manager("please fix the login page"), "")

    def test_empty_stdin_prints_nothing(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.hook("", env={"AGENT_ROLE": "task-manager"}, stdin=""), "")

    def test_bad_json_prints_nothing(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.hook("", env={"AGENT_ROLE": "task-manager"},
                                   stdin='{"prompt": "close case'), "")

    def test_a_repo_that_is_not_set_up_stays_silent(self):
        os.remove(self.repo.path("agent.conf"))
        self.assertEqual(self.as_task_manager("close case"), "")
        self.assertEqual(self.as_main("close case"), "")

    def test_a_quoted_mention_never_triggers(self):
        for prompt in ('the brief says "close case" works now',
                       "on 'close case' do the settle-down job",
                       "run `close case` later",
                       "“close case” is the keyword",
                       "‘close case’ is the keyword",
                       '"CLOSE CASE <name>: finished" is the first line'):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.as_task_manager(prompt), "")

    def test_the_task_name_and_other_words_never_trigger(self):
        for prompt in ("how is close-case going?", "a closed case", "close cases fast",
                       "enclose case notes", "close caseload"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.as_task_manager(prompt), "")

    def test_it_writes_nothing(self):
        def snapshot():
            rows = []
            for dirpath, _, names in os.walk(self.repo.base):
                for name in names:
                    full = os.path.join(dirpath, name)
                    st = os.stat(full)
                    rows.append((full, st.st_size, st.st_mtime_ns))
            return sorted(rows)
        self.set_lock(os.getpid())
        before = snapshot()
        out = self.hook("close case", env={"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY})
        self.assertIn("CLOSE CASE", out)
        self.assertEqual(snapshot(), before)


class TestItTriggers(CloseCaseCase):
    def test_any_case_anywhere_any_white_space(self):
        for prompt in ("close case", "Close Case", "CLOSE CASE please",
                       "ok, we are done for today. close   case.",
                       "wrap it up and close\ncase", "\tclose case\n"):
            with self.subTest(prompt=prompt):
                self.assertIn("CLOSE CASE project: unfinished", self.as_task_manager(prompt))

    def test_one_unquoted_use_is_enough(self):
        out = self.as_task_manager('the "close case" rule is in. now close case')
        self.assertIn("CLOSE CASE project: unfinished", out)

    def test_the_cwd_comes_from_the_hook_input(self):
        elsewhere = self.repo.make_project("elsewhere")
        self.set_lock(os.getpid())
        result = self.repo.run(
            "agent-close-case.sh", cwd=elsewhere,
            env={"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY},
            stdin=self.payload("close case", cwd=self.repo.dir))
        self.assertOk(result)
        self.assertIn("CLOSE CASE project: unfinished", result.stdout)


class TestTaskManager(CloseCaseCase):
    def test_it_gets_the_settle_down_job(self):
        out = self.as_task_manager("close case")
        self.assertReportAsk(out, "project")
        self.assertIn("task manager", out)
        self.assertIn("SendMessage", out)
        self.assertIn("another machine", out)

    def test_the_name_is_the_worktree_folder(self):
        wt = self.repo.detach_scripts_to_worktree()
        self.set_lock(os.getpid())
        out = self.hook("close case", cwd=wt,
                        env={"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY})
        self.assertReportAsk(out, os.path.basename(wt))

    def test_a_report_line_in_its_prompt_is_still_its_own_job(self):
        out = self.as_task_manager("CLOSE CASE alpha: finished")
        self.assertReportAsk(out, "project")

    def test_it_never_gets_the_main_manager_text(self):
        out = self.as_task_manager("close case")
        self.assertNotIn("/auto-pipeline:close-case", out)
        self.assertNotIn("every live", out)


class TestHumanDirect(CloseCaseCase):
    def test_it_gets_the_settle_down_job(self):
        out = self.as_human_direct("close case")
        self.assertReportAsk(out, "project")
        self.assertIn("human-direct", out)
        self.assertIn("SendMessage", out)

    def test_no_live_main_manager_means_print_it_here(self):
        out = self.as_orphan("close case")
        self.assertReportAsk(out, "project")
        self.assertIn("no live main manager", out.lower())
        self.assertIn("human decides", out.lower())


class TestMainManagerFromTheHuman(CloseCaseCase):
    def check(self, out):
        for phrase in ("main manager", "whole repo", "/auto-pipeline:close-case",
                       "agent_worktree.txt", "final table", "only a mention"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), out.lower())
        self.assertNotIn("Never close yourself", out)
        self.assertNotIn("CLOSE CASE project:", out)
        self.assertLessEqual(len(out.encode()), MAX_BYTES)

    def test_the_whole_repo_wraps_up(self):
        self.check(self.as_main("close case"))

    def test_no_lock_is_the_main_manager_too(self):
        self.check(self.hook("close case", env={"CLAUDE_PID": NOBODY}))


class TestMainManagerGetsAReport(CloseCaseCase):
    REPORT = ("CLOSE CASE %s: %s\nDone: login form.\nLeft: the reset link, "
              "next: write its test.\nTests: 12 run, 12 OK.\nTIME: est 60m, actual 40m, human 0m")

    def check(self, out):
        for phrase in ("main manager", "/auto-pipeline:merge", "finish first",
                       "close now", "/auto-pipeline:close-case", "agent_state.txt",
                       "owner not seen", "only a mention"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), out.lower())
        self.assertNotIn("whole repo", out)
        self.assertLessEqual(len(out.encode()), MAX_BYTES)

    def test_an_unfinished_report(self):
        out = self.as_main(self.REPORT % ("alpha", "unfinished"))
        self.check(out)
        self.assertRegex(out, r"alpha\W+unfinished")

    def test_a_finished_report(self):
        out = self.as_main(self.REPORT % ("beta", "finished"))
        self.check(out)
        self.assertRegex(out, r"beta\W+finished")
        self.assertNotRegex(out, r"beta\W+unfinished")

    def test_two_reports_in_one_prompt(self):
        out = self.as_main(self.REPORT % ("alpha", "unfinished") + "\n\n"
                           + self.REPORT % ("beta", "finished"))
        self.check(out)
        self.assertRegex(out, r"alpha\W+unfinished")
        self.assertRegex(out, r"beta\W+finished")

    def test_a_report_inside_a_message_envelope(self):
        out = self.as_main('<message from="TM alpha">' + self.REPORT % ("alpha", "unfinished")
                           + "</message>")
        self.check(out)
        self.assertRegex(out, r"alpha\W+unfinished")


class TestHooksJson(CloseCaseCase):
    def hooks(self):
        return json.loads(read("hooks", "hooks.json"))["hooks"]

    def test_user_prompt_submit_runs_it(self):
        self.assertIn(HOOK_ENTRY, self.hooks()["UserPromptSubmit"])

    def test_no_other_event_runs_it(self):
        for event, entries in self.hooks().items():
            if event == "UserPromptSubmit":
                self.assertEqual(entries.count(HOOK_ENTRY), 1)
                continue
            with self.subTest(event=event):
                self.assertNotIn("agent-close-case.sh", json.dumps(entries))

    def test_the_command_runs_for_real_with_the_city_off(self):
        self.set_lock(os.getpid())
        env = self.repo._env({"CLAUDE_PLUGIN_ROOT": self.repo.plugin,
                              "AGENT_CITY_DIR": os.path.join(self.repo.base, "no-city"),
                              "AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY})
        result = subprocess.run(["sh", "-c", HOOK_COMMAND], input=self.payload("close case"),
                                env=env, cwd=self.repo.dir, capture_output=True, text=True,
                                timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CLOSE CASE project: unfinished", result.stdout)


class TestOnePidHelper(unittest.TestCase):
    """agent-start.sh and the hook find "this session" the same way."""

    def test_agent_pid_lives_in_the_roots_helper(self):
        self.assertRegex(read("bin", "agent-roots.sh"), r"(?m)^agent_pid\(\)")

    def test_agent_start_no_longer_has_its_own_copy(self):
        self.assertNotRegex(read("bin", "agent-start.sh"), r"(?m)^agent_pid\(\)")

    def test_the_hook_uses_it(self):
        text = read("bin", "agent-close-case.sh")
        self.assertIn("agent-roots.sh", text)
        self.assertIn("agent_pid", text)


class TestTheRule(unittest.TestCase):
    """PRINCIPLES.md W13, short lines, same style as the other rules."""

    def rule(self):
        return section(read("PRINCIPLES.md"), "W13. Close case", "## C.")

    def test_it_sits_after_w12_in_the_work_section(self):
        text = read("PRINCIPLES.md")
        self.assertLess(text.index("W12. Cross-repo"), text.index("W13. Close case"))
        self.assertLess(text.index("W13. Close case"), text.index("## C. Human"))

    def test_one_short_line_per_rule(self):
        bullets = [l for l in self.rule().splitlines() if l.startswith("- ")]
        self.assertGreaterEqual(len(bullets), 5)
        self.assertLessEqual(len(bullets), 12)
        for line in bullets:
            with self.subTest(line=line[:40]):
                self.assertLessEqual(len(line), 200)

    def test_it_says_what_the_owner_decided(self):
        rule = self.rule()
        for phrase in ("close case", "bin/agent-close-case.sh", "UserPromptSubmit",
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
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", text)), 29)


class TestTheSkills(unittest.TestCase):
    def test_the_close_case_skill(self):
        text = read("skills", "close-case", "SKILL.md")
        self.assertRegex(text, r"(?m)^name: close-case$")
        self.assertRegex(text, r"(?m)^description: Main manager only\.")
        for phrase in ("finish first", "close now", "owner not seen", "agent_worktree.txt",
                       "${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worktree rm",
                       "${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh todo add",
                       "${CLAUDE_PLUGIN_ROOT}/bin/agent-runtime.sh close",
                       "agent-monitor.sh stop", "CronDelete", "/merge", "final table",
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
        text = read("README.md")
        self.assertIn("agent-close-case.sh", text)
        self.assertIn("close-case", text)


class TestTheBriefIsQuiet(CloseCaseCase):
    """The dispatch brief explains 'close case' but never fires it."""

    def test_the_brief_itself_never_fires_the_hook(self):
        self.assertEqual(self.as_task_manager(dispatch_brief()), "")


if __name__ == "__main__":
    unittest.main()
