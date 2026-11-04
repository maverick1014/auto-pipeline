"""Failing tests for 'show todo', the hook part. Written by the task manager first.

Owner, 2026-11-02: a new keyword, like "close case". The human types show todo
(or just todo) and the session shows one table of everything open, sorted,
with the times, then the decide section.

CONTRACT. bin/agent-show-todo.sh is a UserPromptSubmit hook (hooks.json, the
entry right after agent-close-case.sh, timeout 10). Claude Code gives it the
prompt as JSON on stdin; what it prints on stdout is added to the session's
context. It runs on every prompt in every repo, so:

    cheap      a prompt without the letters "todo" (any case) never starts
               python; the first check is one grep
    never      blocks: always exit 0, nothing on stderr, writes no file
    silent     no keyword, empty or bad stdin, a project with no agent.conf

    trigger    show todo (or show todos), any case, anywhere, any white space
               between the words (\\bshow\\s+todos?\\b)
    trigger    the WHOLE prompt is todo, any case, with only spaces and
               punctuation around it ("todo", " TODO ", "todo?", "todo？")
    no         todo inside a sentence ("add this to the todo list",
               "TODO: fix x", "todos", "to do")
    no         a quoted mention: a quote mark or backtick right before the
               words ("show todo", 'todo', `show todo`, curly quotes)
    no         show-todo (the task's name), showtodo, show todolist

The project, the name and the role come the same way as close case
(tests/test_agent_close_case.py): project from the stdin "cwd", name = folder
name of the git toplevel of that cwd, role by role_read (agent-roots.sh):

    no lock / our lock                main manager   -> the whole repo:
                                          <plugin>/bin/agent-file.sh board
    AGENT_ROLE=task-manager           task manager   -> its own task:
                                          <plugin>/bin/agent-file.sh board --self
    live lock, not ours               Helper (human-direct) -> board --self
    dead lock                         no live main manager  -> board --self
    any other AGENT_ROLE              a spawned helper agent (deputy, worker,
                                      reviewer): silent. Subagents never.

<plugin> is the real path of the plugin the hook runs from. What it prints:
SHOW TODO first, the role and the name, the one command, show its output as
printed (no row added, dropped or changed), no agent and no other file read,
then the decide section with its heading in the agent.conf language
(zh "## 要你决定", en "## To decide"), and "only a mention of the words ->
ignore this". Every text fits in 1000 bytes.

The rule is W14 "Show todo" in PRINCIPLES.md, right after W13; Watch becomes
W15 and Known traps W16. The quiz gets Q33 (W14, answer B).
"""

import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase

HOOK_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-show-todo.sh'
HOOK_ENTRY = {"hooks": [{"type": "command", "command": HOOK_COMMAND, "timeout": 10}]}
CLOSE_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-close-case.sh'
MAX_BYTES = 1000
NOBODY = "999999"   # a CLAUDE_PID no lock ever names

# The owner's brief for this very task explains the keyword. It quotes it, so
# pasting it into a session must never fire the hook.
OWNER_BRIEF = (
    'FEATURE (owner 2026-11-02, all choices decided):\n'
    '- New keyword, like "close case": a UserPromptSubmit hook fires when the prompt '
    'contains "show todo" (any case, anywhere) OR the whole prompt is just "todo" (any '
    'case, surrounding spaces/punctuation ok). "todo" inside a normal sentence ("add this '
    'to the todo list") never fires. A quoted mention is not an order (same as close case).\n'
    '- Table contents: every open task (running, held, queued), every task waiting on the '
    'owner, the owner\'s own OWNER TODO items from agent_state.txt.\n'
    'Then the E2E path for me: type "show todo", type "todo", type "add this to the todo '
    'list" (must not fire); expected output; how to restore.\n'
    'workers: Agent subagent_type worker, description "show-todo Worker <n>: <slice>"\n')


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def dead_pid():
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


def section(text, start, end):
    lines = text.splitlines()
    begin = next(i for i, line in enumerate(lines) if line.startswith(start))
    stop = next(i for i in range(begin + 1, len(lines)) if lines[i].startswith(end))
    return "\n".join(lines[begin:stop])


def dispatch_brief():
    return section(read("skills", "dispatch", "SKILL.md"),
                   "## Task manager brief", "## Cross-repo brief")


class ShowTodoCase(ScriptCase):
    script = "agent-show-todo.sh"

    def payload(self, prompt, cwd=None):
        return json.dumps({
            "session_id": "s-todo",
            "transcript_path": "/tmp/none.jsonl",
            "cwd": cwd or self.repo.cwd,
            "permission_mode": "auto",
            "hook_event_name": "UserPromptSubmit",
            "prompt": prompt,
        })

    def set_lock(self, pid):
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%s 2026-11-02 10:00\n" % pid)

    def hook(self, prompt, env=None, stdin=None, cwd=None):
        """Run the hook; exit 0 and an empty stderr, always. Returns stdout."""
        result = self.repo.run("agent-show-todo.sh", env=env or {},
                               stdin=self.payload(prompt, cwd) if stdin is None else stdin,
                               cwd=cwd)
        self.assertOk(result)
        self.assertEqual(result.stderr, "", result.stderr)
        return result.stdout

    def as_main(self, prompt, **kw):
        self.set_lock(os.getpid())
        return self.hook(prompt, env={"CLAUDE_PID": str(os.getpid())}, **kw)

    def as_task_manager(self, prompt, **kw):
        self.set_lock(os.getpid())
        return self.hook(prompt, env={"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY}, **kw)

    def as_helper(self, prompt, **kw):
        self.set_lock(os.getpid())
        return self.hook(prompt, env={"CLAUDE_PID": NOBODY}, **kw)

    def as_orphan(self, prompt, **kw):
        self.set_lock(dead_pid())
        return self.hook(prompt, env={"CLAUDE_PID": NOBODY}, **kw)

    def board_cmd(self):
        return os.path.join(os.path.realpath(self.repo.plugin), "bin", "agent-file.sh") + " board"

    def assertMain(self, out):
        self.assertTrue(out.startswith("SHOW TODO"), out)
        self.assertIn("main manager", out)
        self.assertIn("whole repo", out)
        self.assertIn(self.board_cmd(), out)
        self.assertNotIn("--self", out)
        self.assertCommon(out)

    def assertSelf(self, out, name="project"):
        self.assertTrue(out.startswith("SHOW TODO"), out)
        self.assertIn('"%s"' % name, out)
        self.assertIn(self.board_cmd() + " --self", out)
        self.assertIn("own task", out)
        self.assertIn("workers", out)
        self.assertNotIn("whole repo", out)
        self.assertCommon(out)

    def assertCommon(self, out):
        low = out.lower()
        for phrase in ("as printed", "no agent", "decide section", "only a mention",
                       "PRINCIPLES.md W14"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), low)
        self.assertLessEqual(len(out.encode()), MAX_BYTES)


# ---------------------------------------------------------------- quiet


class TestItStaysQuiet(ShowTodoCase):
    def test_no_keyword_prints_nothing(self):
        self.assertEqual(self.as_main("please fix the login page"), "")
        self.assertEqual(self.as_task_manager("please fix the login page"), "")

    def test_empty_stdin_prints_nothing(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.hook("", env={"CLAUDE_PID": str(os.getpid())}, stdin=""), "")

    def test_bad_json_prints_nothing(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.hook("", env={"CLAUDE_PID": str(os.getpid())},
                                   stdin='{"prompt": "show todo'), "")

    def test_a_repo_that_is_not_set_up_stays_silent(self):
        os.remove(self.repo.path("agent.conf"))
        self.assertEqual(self.as_main("show todo"), "")
        self.assertEqual(self.as_task_manager("todo"), "")

    def test_todo_inside_a_sentence_never_fires(self):
        for prompt in ("add this to the todo list", "TODO: fix the login page",
                       "what is on the todo?", "todos", "to do", "todo list",
                       "the todo", "todo later please", "my todo"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.as_main(prompt), "")

    def test_the_task_name_and_other_words_never_fire(self):
        for prompt in ("how is show-todo going?", "showtodo", "show todolist",
                       "show_todo", "the show-todo branch is pushed"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.as_main(prompt), "")

    def test_a_quoted_mention_never_fires(self):
        for prompt in ('the brief says "show todo" works now',
                       "on 'show todo' print the board",
                       "run `show todo` later",
                       "“show todo” is the keyword",
                       "‘show todo’ is the keyword",
                       '"todo"', "'todo'", "`todo`", "“todo”", "‘Todo’"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.as_main(prompt), "")

    def test_the_owner_brief_never_fires(self):
        self.assertEqual(self.as_main(OWNER_BRIEF), "")
        self.assertEqual(self.as_task_manager(OWNER_BRIEF), "")

    def test_the_dispatch_brief_never_fires(self):
        self.assertEqual(self.as_task_manager(dispatch_brief()), "")

    def test_a_spawned_helper_agent_never_gets_it(self):
        self.set_lock(os.getpid())
        for role in ("worker", "fast-lane-deputy", "merge-deputy", "reviewer"):
            with self.subTest(role=role):
                self.assertEqual(self.hook("show todo", env={"AGENT_ROLE": role,
                                                             "CLAUDE_PID": NOBODY}), "")

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
        out = self.hook("show todo", env={"CLAUDE_PID": str(os.getpid())})
        self.assertIn("SHOW TODO", out)
        out = self.hook("todo", env={"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY})
        self.assertIn("SHOW TODO", out)
        self.assertEqual(snapshot(), before)

    def test_a_prompt_without_todo_never_starts_python(self):
        marker = os.path.join(self.repo.base, "python-ran")
        real = subprocess.run(["sh", "-c", "command -v python3"], capture_output=True,
                              text=True).stdout.strip()
        self.repo.stub_tool("python3", "#!/bin/sh\n: > '%s'\nexec '%s' \"$@\"\n" % (marker, real))
        self.assertEqual(self.as_main("please fix the login page, then close the case"), "")
        self.assertFalse(os.path.exists(marker), "python ran for a prompt with no todo")
        self.assertIn("SHOW TODO", self.as_main("show todo"))   # the stub is really on PATH


# ---------------------------------------------------------------- fires


class TestItFires(ShowTodoCase):
    def test_show_todo_any_case_anywhere_any_white_space(self):
        for prompt in ("show todo", "Show Todo", "SHOW TODO please",
                       "ok, before we go on: show   todo.", "can you show todo?",
                       "show todos", "show\ntodo", "\tshow todo\n", "先 show todo 一下"):
            with self.subTest(prompt=prompt):
                self.assertMain(self.as_main(prompt))

    def test_the_whole_prompt_is_todo(self):
        for prompt in ("todo", "TODO", "Todo", "  todo  ", "todo?", "todo!", "todo.",
                       "todo？", "todo。", "…todo", "\ntodo\n", "- todo", "todo!!"):
            with self.subTest(prompt=prompt):
                self.assertMain(self.as_main(prompt))

    def test_a_huge_prompt_still_fires(self):
        # bigger than ARG_MAX (1 MB on macOS): never in env or argv
        self.assertMain(self.as_main("x" * 1200000 + "\nshow todo"))

    def test_one_unquoted_use_is_enough(self):
        self.assertMain(self.as_main('the "show todo" rule is in. now show todo'))

    def test_the_cwd_comes_from_the_hook_input(self):
        elsewhere = self.repo.make_project("elsewhere")
        self.set_lock(os.getpid())
        result = self.repo.run(
            "agent-show-todo.sh", cwd=elsewhere,
            env={"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY},
            stdin=self.payload("show todo", cwd=self.repo.dir))
        self.assertOk(result)
        self.assertSelf(result.stdout, "project")


# ---------------------------------------------------------------- roles


class TestRoles(ShowTodoCase):
    def test_the_main_manager_gets_the_whole_repo(self):
        out = self.as_main("show todo")
        self.assertMain(out)

    def test_no_lock_is_the_main_manager_too(self):
        self.assertMain(self.hook("todo", env={"CLAUDE_PID": NOBODY}))

    def test_a_task_manager_gets_its_own_task(self):
        out = self.as_task_manager("show todo")
        self.assertSelf(out)
        self.assertIn("task manager", out)

    def test_the_name_is_the_worktree_folder(self):
        wt = self.repo.detach_scripts_to_worktree()
        self.set_lock(os.getpid())
        out = self.hook("todo", cwd=wt, env={"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY})
        self.assertSelf(out, os.path.basename(wt))

    def test_a_helper_gets_its_own_task(self):
        out = self.as_helper("show todo")
        self.assertSelf(out)
        self.assertIn("human-direct", out)

    def test_no_live_main_manager_still_its_own_task(self):
        out = self.as_orphan("show todo")
        self.assertSelf(out)


class TestDecideHeading(ShowTodoCase):
    def test_zh(self):
        self.repo.set_conf("language", "zh")
        self.assertIn("## 要你决定", self.as_main("show todo"))
        self.assertIn("## 要你决定", self.as_task_manager("todo"))

    def test_en(self):
        self.repo.set_conf("language", "en")
        out = self.as_main("show todo")
        self.assertIn("## To decide", out)
        self.assertNotIn("要你决定", out)


# ---------------------------------------------------------------- hooks.json


class TestHooksJson(ShowTodoCase):
    def hooks(self):
        return json.loads(read("hooks", "hooks.json"))["hooks"]

    def test_user_prompt_submit_runs_it_right_after_close_case(self):
        entries = self.hooks()["UserPromptSubmit"]
        self.assertEqual(entries.count(HOOK_ENTRY), 1)
        commands = [h["command"] for e in entries for h in e["hooks"]]
        self.assertEqual(commands.index(HOOK_COMMAND), commands.index(CLOSE_COMMAND) + 1)

    def test_no_other_event_runs_it(self):
        for event, entries in self.hooks().items():
            if event == "UserPromptSubmit":
                continue
            with self.subTest(event=event):
                self.assertNotIn("agent-show-todo.sh", json.dumps(entries))

    def test_the_command_runs_for_real_with_the_city_off(self):
        self.set_lock(os.getpid())
        env = self.repo._env({"CLAUDE_PLUGIN_ROOT": self.repo.plugin,
                              "AGENT_CITY_DIR": os.path.join(self.repo.base, "no-city"),
                              "CLAUDE_PID": str(os.getpid())})
        result = subprocess.run(["sh", "-c", HOOK_COMMAND], input=self.payload("show todo"),
                                env=env, cwd=self.repo.dir, capture_output=True, text=True,
                                timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertTrue(result.stdout.startswith("SHOW TODO"), result.stdout)


# ---------------------------------------------------------------- the rule


class TestTheRule(unittest.TestCase):
    """PRINCIPLES.md W14, short lines, same style as W13."""

    def rule(self):
        return section(read("PRINCIPLES.md"), "W14. Show todo", "W15.")

    def test_it_sits_right_after_w13(self):
        text = read("PRINCIPLES.md")
        order = [text.index(h) for h in ("W13. Close case", "W14. Show todo",
                                         "W15. Watch", "W16. Known traps", "## C. Human")]
        self.assertEqual(order, sorted(order))
        self.assertNotIn("W14. Watch", text)
        self.assertNotIn("W15. Known traps", text)

    def test_one_short_line_per_rule(self):
        bullets = [l for l in self.rule().splitlines() if l.startswith("- ")]
        self.assertGreaterEqual(len(bullets), 5)
        self.assertLessEqual(len(bullets), 12)
        for line in self.rule().splitlines()[1:]:
            with self.subTest(line=line[:40]):
                self.assertTrue(line.startswith("- ") or not line.strip(), line)
                self.assertLessEqual(len(line), 200)

    def test_it_says_what_the_owner_decided(self):
        rule = self.rule()
        for phrase in ("show todo", "todo", "bin/agent-show-todo.sh", "UserPromptSubmit",
                       "quoted", "bin/agent-file.sh board", "--self", "as printed",
                       "decide section", "whole repo", "own task", "workers",
                       "Subagents never", "mock check", "owner question", "owner review",
                       "held", "queued", "OWNER TODO", "PARKED", "few words", "where",
                       "oldest first", "never guessed", "todo wait", "todo where",
                       "park add", "worker on", "language"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)

    def test_the_sort_order(self):
        rule = self.rule()
        line = next(l for l in rule.splitlines() if "oldest first" in l)
        order = [line.index(w) for w in ("waiting on the owner", "running", "held",
                                         "OWNER TODO", "parked")]
        self.assertEqual(order, sorted(order), line)


# ---------------------------------------------------------------- the quiz


class TestTheQuiz(ScriptCase):
    script = "agent-start.sh"
    ANSWERS = ("1A 2D 3C 4B 5D 6D 7A 8C 9A 10D 11A 12C 13D 14C 15B 16C 17C "
               "18D 19B 20A 21D 22C 23B 24D 25A 26D 27A 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C")

    def quiz(self):
        return self.assertOk(self.repo.run("agent-start.sh", "--quiz"))

    def test_question_33_is_show_todo(self):
        out = self.quiz()
        q = out[out.index("Q33. "):]
        self.assertIn("show todo", q.splitlines()[0].lower())
        self.assertIn("task manager", q.splitlines()[0].lower())
        options = [l.strip() for l in q.splitlines()[1:5]]
        self.assertEqual([o[:2] for o in options], ["A.", "B.", "C.", "D."])
        self.assertIn("board --self", options[1])
        self.assertIn("as printed", options[1])

    def test_the_quiz_says_34(self):
        out = self.quiz()
        self.assertIn("=== QUIZ — answer all 37 before any work ===", out)
        self.assertIn('--answer "1A 2B 3C ... 37D"', out)
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", out)), 37)

    def test_b_passes(self):
        out = self.assertOk(self.repo.run("agent-start.sh", "--answer", self.ANSWERS))
        self.assertIn("QUIZ RESULT: 37/37 PASS", out)

    def test_another_letter_fails_and_names_w14(self):
        for wrong in ("33A", "33C", "33D"):
            with self.subTest(wrong=wrong):
                result = self.repo.run("agent-start.sh", "--answer",
                                       self.ANSWERS.replace("33B", wrong))
                self.assertEqual(result.returncode, 1)
                self.assertIn("Q33(W14)", result.stdout)

    def test_the_old_32_answers_no_longer_pass(self):
        result = self.repo.run("agent-start.sh", "--answer", self.ANSWERS.replace(" 33B", ""))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Q33(W14)", result.stdout)


# ---------------------------------------------------------------- docs, skills, pack


class TestTheDocs(unittest.TestCase):
    def test_the_readme_names_the_hook_and_the_board(self):
        text = read("README.md")
        for phrase in ("bin/agent-show-todo.sh", "bin/agent_board.py",
                       "bin/agent-file.sh board", "37-question quiz"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertNotIn("33-question quiz", text)

    def test_the_dispatch_skill_records_what_the_board_reads(self):
        text = read("skills", "dispatch", "SKILL.md")
        for phrase in ("agent-file.sh todo where", "agent-file.sh todo wait",
                       " on mock", " on question", " on review", " on hold", " off"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_the_task_manager_brief_records_workers_and_parked_questions(self):
        brief = dispatch_brief()
        for phrase in ("TODO LINE:", "agent-file.sh worker on", "agent-file.sh worker off",
                       "agent-file.sh park add"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, brief)

    def test_agent_file_usage_names_the_new_commands(self):
        head = read("bin", "agent-file.sh").split("\nset -eu", 1)[0]
        for phrase in ("todo wait", "todo where", "park add", "park list", "park rm",
                       "worker on", "worker off", "board"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, head)


if __name__ == "__main__":
    unittest.main()
