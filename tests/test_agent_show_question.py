"""Failing tests for 'show question', the hook part. Written by the task manager first.

Owner, 2026-11-04: a new keyword, like "show todo". It lists every question that
waits on the owner. More than 10: an Artifact page, the owner answers one by one.
10 or fewer: a plain numbered list in chat. Scope = this repo only. Page answers:
the owner answers all, then says so in chat; the session reads all answers at once.

CONTRACT. bin/agent-show-question.sh is a UserPromptSubmit hook (hooks.json, the
entry right after agent-show-todo.sh, timeout 10), built like
bin/agent-show-todo.sh (tests/test_agent_show_todo.py): the prompt comes as JSON
on stdin, stdout is added to the session's context.

    cheap      a prompt with none of the stems "question", "decide", "decision",
               问题, 回答, 决定 never starts python; neither does a done word or
               an answer list (below) while the session's agent_state.txt has no
               "QUESTIONS PAGE:" line
    never      blocks: always exit 0, nothing on stderr, writes no file
    silent     no keyword, empty or bad stdin, a project with no agent.conf

ANYWHERE in the prompt (any case, any white space between the words, ASCII word
edges, so a Chinese character right next to the words does not hide them):
    show question(s), show pending question(s), list question(s),
    list the question(s), pending question(s), open question(s),
    questions for me, question list, pending decision(s), show decision(s),
    what do I need to decide, what do I have to decide, what needs my decision,
    显示问题, 列出问题, 问题列表, 待回答, 待决定, 要我决定, 要我回答,
    待我决定, 待我回答, 我要决定什么
THE WHOLE PROMPT only (only spaces and punctuation around it):
    question(s), any question(s), 有问题吗, 还有问题吗, 有什么问题, 有没有问题, 问题
NEVER: 这段代码有什么问题 (what is wrong with this code), a question inside a
sentence ("I have a question about the API", "question: why does it fail?"),
the task's name (show-question, showquestion, show_question), and a quoted
mention: a quote mark or backtick right before the words (" ' ` “ ” ‘ ’ « » 「 」 『 』).

Roles, name and project come exactly like show todo (role_read in
agent-roots.sh; AGENT_ROLE=task-manager is a task manager; any other AGENT_ROLE
is a spawned helper agent and gets nothing):
    main manager  -> <plugin>/bin/agent-file.sh questions          (whole repo)
    task manager, Helper, no live main manager
                  -> <plugin>/bin/agent-file.sh questions --self   (own task)

What it prints (<= 1600 bytes): "SHOW QUESTION" first, the role and the name,
"PRINCIPLES.md W18", "only a mention" -> ignore this, the one command, then:
its first line is the count; 10 or fewer -> a numbered list in chat under the
decide heading (zh "## 要你决定", en "## To decide"): each a decide item with the
title, the sub line, the facts and the lettered options, the recommended one
marked (zh "(建议)", en "(recommended)"); nothing dropped; the owner answers like
"1A 2B — note". More than 10 -> the same command with "--page <file>" (a file in
your scratchpad), publish that file with the Artifact tool (capabilities db and
user); the "QUESTIONS PAGE" line of agent_state.txt has the url: publish with
that url (redeploy); a first publish: record the new url with
"agent-file.sh questions --url <url>"; then one chat line: the count, the link,
answer all, then tell me (zh 答完了). No Artifact tool -> the chat list of all,
nothing dropped.

DONE FLOW (the same hook). Fires only when the session's own agent_state.txt
(the git toplevel of the cwd; the main repo for the main manager) has a
"QUESTIONS PAGE: <url> | <page file> | <map file> | since <date>" line AND the
page still has an open question: an id in the map file (JSON, "questions":
[{"n", "id", ...}]) that `agent-file.sh questions --json` (--self for every role
but the main manager) still lists; no map file: any open question at all.
    done words, the whole prompt: done, all done, answered, finished, ok done,
        i'm done, 好了, 完成, 完成了, 答好了, 选好了, 都答了, 答完, 答完了
    anywhere, unquoted: 答完了, answered all, all answered
    an answer list: the prompt starts with "<n><letter>" (1A, 12b) or with
        "<n> —" (the note of a question without options)
What it prints (<= 1600 bytes): "QUESTIONS ANSWERED" first, "PRINCIPLES.md W18",
the url of the page, read every answer at once with ArtifactData (list, the
"answers" collection), the map file (pasted lines go by number through it),
one table (question, answer), then for each answered question
<plugin>/bin/agent-file.sh questions answer <id> "<answer>" and carry on; an
unpicked question is still open.

The rule is W18 "Show question" in PRINCIPLES.md, right after W17 (nothing is
renumbered). H3 gets one line: every question the main manager puts to the owner
is recorded with park add (fields filled when known) and removed when answered.
The quiz gets Q37 (W18, answer C), text below (QUIZ_Q37).
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

HOOK_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-show-question.sh'
HOOK_ENTRY = {"hooks": [{"type": "command", "command": HOOK_COMMAND, "timeout": 10}]}
TODO_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-show-todo.sh'
MAX_BYTES = 1600
NOBODY = "999999"   # a CLAUDE_PID no lock ever names
NOW = "2026-11-04 18:00"

# Q37 as the quiz prints it (the worker writes it into bin/agent-start.sh as is).
QUIZ_Q37 = """Q37. You are the main manager. The owner types show question; agent-file.sh questions says 14. You:
  A. Show the first 10 in chat and drop the rest
  B. Ask the owner which ones he wants to see
  C. Run agent-file.sh questions --page, publish the page with the Artifact tool, then one line: the count, the link, "answer all, then tell me"
  D. Read every agent_state.txt and write your own summary"""

ANYWHERE = ["show question", "show questions", "Show Questions please", "SHOW   QUESTION",
            "show pending questions", "show pending question", "list questions",
            "list the questions", "list question", "pending questions", "any pending question?",
            "open questions", "what are the open questions?", "questions for me",
            "any questions for me?", "question list", "pending decisions", "show decisions",
            "what do I need to decide", "What do I have to decide?", "what needs my decision?",
            "先 show question 一下", "show\nquestions", "显示问题", "列出问题", "问题列表",
            "还有哪些待回答", "待决定的事", "有什么要我决定的", "要我回答什么", "待我决定",
            "待我回答的", "我要决定什么"]
WHOLE = ["question", "questions", "Questions?", " QUESTIONS ", "any question", "any questions?",
         "Any questions", "有问题吗", "还有问题吗？", "有什么问题", "有什么问题?", "有没有问题",
         "问题", "问题？", "\n问题\n", "- questions"]
NEVER = ["这段代码有什么问题", "这段代码有什么问题？", "what is wrong with this code?",
         "I have a question about the API", "question: why does it fail?",
         "the question is how to cache it", "how is show-question going?", "showquestion",
         "show_question", "the show-question branch is pushed", "这个问题怎么修", "问题出在哪里",
         "有问题", "ask me a question later", "the decision log is long", "decide later"]
QUOTED = ['the brief says "show question" works now', "on 'show questions' print the list",
          "run `show question` later", "“show question” is the keyword", "‘list questions’",
          '"questions"', "'question'", "`questions`", "“问题”", "「显示问题」是关键词",
          "『待决定』", "«pending questions»"]
DONE_WHOLE = ["done", "Done.", "all done", "answered", "finished!", "ok done", "I'm done",
              "好了", "好了。", "完成", "完成了", "答好了", "选好了", "都答了", "答完", "答完了！"]
DONE_ANYWHERE = ["我答完了，你看一下", "answered all of them", "all answered, go on"]
ANSWER_LISTS = ["1A 2B 3A", "1A — keep it\n2B", "12b", "3 — 先不做", "1A, 2C — 晚点再说"]
NOT_DONE = ["done with the login page?", "it is done", "好了没有，测试跑完了吗", "not finished yet",
            "the answer is 1A", "A1 sauce"]

# This task's own brief quotes every keyword, so pasting it never fires the hook.
OWNER_BRIEF = (
    'OWNER ASK 2026-11-04: new keyword "show question", like show todo, plus related words. '
    'It lists every question pending on the owner. More than 10: an Artifact page.\n'
    'Fires anywhere, any case, unquoted: "show question(s)", "show pending question(s)", '
    '"list (the) question(s)", "what needs my decision", "显示问题", "列出问题".\n'
    'Fires only when the whole prompt is it: "question(s)", "有问题吗", "问题".\n'
    'Must NOT fire: "这段代码有什么问题" (what is wrong with this code).\n'
    'Answer flow: the owner says he is done ("done", "答完了").\n')


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
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


class ShowQuestionCase(ScriptCase):
    script = "agent-show-question.sh"

    def payload(self, prompt, cwd=None):
        return json.dumps({
            "session_id": "s-question",
            "transcript_path": "/tmp/none.jsonl",
            "cwd": cwd or self.repo.cwd,
            "permission_mode": "auto",
            "hook_event_name": "UserPromptSubmit",
            "prompt": prompt,
        })

    def set_lock(self, pid):
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%s 2026-11-04 10:00\n" % pid)

    def hook(self, prompt, env=None, stdin=None, cwd=None):
        """Run the hook; exit 0 and an empty stderr, always. Returns stdout."""
        env = dict(env or {})
        env.setdefault("AGENT_FAKE_NOW", NOW)
        result = self.repo.run("agent-show-question.sh", env=env,
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

    def cmd(self):
        return os.path.join(os.path.realpath(self.repo.plugin), "bin", "agent-file.sh") + " questions"

    def assertMain(self, out):
        self.assertTrue(out.startswith("SHOW QUESTION"), out)
        self.assertIn("main manager", out)
        self.assertIn("whole repo", out)
        self.assertIn(self.cmd(), out)
        self.assertNotIn("--self", out)
        self.assertCommon(out)

    def assertSelf(self, out, name="project"):
        self.assertTrue(out.startswith("SHOW QUESTION"), out)
        self.assertIn('"%s"' % name, out)
        self.assertIn(self.cmd() + " --self", out)
        self.assertIn("own task", out)
        self.assertNotIn("whole repo", out)
        self.assertCommon(out)

    def assertCommon(self, out):
        low = out.lower()
        for phrase in ("only a mention", "PRINCIPLES.md W18", "count", "10 or fewer",
                       "more than 10", "--page", "scratchpad", "Artifact", "db", "user",
                       "QUESTIONS PAGE", "--url", "nothing dropped", "1A 2B",
                       "answer all"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), low)
        self.assertLessEqual(len(out.encode()), MAX_BYTES)


# ---------------------------------------------------------------- quiet


class TestItStaysQuiet(ShowQuestionCase):
    def test_no_keyword_prints_nothing(self):
        self.assertEqual(self.as_main("please fix the login page"), "")
        self.assertEqual(self.as_task_manager("please fix the login page"), "")

    def test_empty_stdin_prints_nothing(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.hook("", env={"CLAUDE_PID": str(os.getpid())}, stdin=""), "")

    def test_bad_json_prints_nothing(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.hook("", env={"CLAUDE_PID": str(os.getpid())},
                                   stdin='{"prompt": "show question'), "")

    def test_a_repo_that_is_not_set_up_stays_silent(self):
        os.remove(self.repo.path("agent.conf"))
        self.assertEqual(self.as_main("show question"), "")
        self.assertEqual(self.as_task_manager("问题"), "")

    def test_never_words(self):
        for prompt in NEVER:
            with self.subTest(prompt=prompt):
                self.assertEqual(self.as_main(prompt), "")
                self.assertEqual(self.as_task_manager(prompt), "")

    def test_a_quoted_mention_never_fires(self):
        for prompt in QUOTED:
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
                self.assertEqual(self.hook("show question", env={"AGENT_ROLE": role,
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
        self.assertIn("SHOW QUESTION", self.hook("show question", env={"CLAUDE_PID": str(os.getpid())}))
        self.assertIn("SHOW QUESTION", self.hook("问题", env={"AGENT_ROLE": "task-manager",
                                                             "CLAUDE_PID": NOBODY}))
        self.assertEqual(self.hook("答完了", env={"CLAUDE_PID": str(os.getpid())}), "")
        self.assertEqual(snapshot(), before)

    def stub_python(self):
        marker = os.path.join(self.repo.base, "python-ran")
        real = subprocess.run(["sh", "-c", "command -v python3"], capture_output=True,
                              text=True).stdout.strip()
        self.repo.stub_tool("python3", "#!/bin/sh\n: > '%s'\nexec '%s' \"$@\"\n" % (marker, real))
        return marker

    def test_a_prompt_without_the_stems_never_starts_python(self):
        marker = self.stub_python()
        self.assertEqual(self.as_main("please fix the login page, then close the case"), "")
        self.assertFalse(os.path.exists(marker), "python ran for a prompt with no stem")
        self.assertIn("SHOW QUESTION", self.as_main("show question"))   # the stub is really on PATH

    def test_a_done_word_without_a_page_line_never_starts_python(self):
        marker = self.stub_python()
        for prompt in ("done", "答完了", "1A 2B"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.as_main(prompt), "")
                self.assertFalse(os.path.exists(marker), "python ran for %r with no page" % prompt)


# ---------------------------------------------------------------- fires


class TestItFires(ShowQuestionCase):
    def test_anywhere_words(self):
        for prompt in ANYWHERE:
            with self.subTest(prompt=prompt):
                self.assertMain(self.as_main(prompt))

    def test_whole_prompt_words(self):
        for prompt in WHOLE:
            with self.subTest(prompt=prompt):
                self.assertMain(self.as_main(prompt))

    def test_a_huge_prompt_still_fires(self):
        # bigger than ARG_MAX (1 MB on macOS): never in env or argv
        self.assertMain(self.as_main("x" * 1200000 + "\nshow question"))

    def test_one_unquoted_use_is_enough(self):
        self.assertMain(self.as_main('the "show question" rule is in. now show questions'))

    def test_the_cwd_comes_from_the_hook_input(self):
        elsewhere = self.repo.make_project("elsewhere")
        self.set_lock(os.getpid())
        result = self.repo.run(
            "agent-show-question.sh", cwd=elsewhere,
            env={"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY},
            stdin=self.payload("show question", cwd=self.repo.dir))
        self.assertOk(result)
        self.assertSelf(result.stdout, "project")


# ---------------------------------------------------------------- roles


class TestRoles(ShowQuestionCase):
    def test_the_main_manager_gets_the_whole_repo(self):
        self.assertMain(self.as_main("show question"))

    def test_no_lock_is_the_main_manager_too(self):
        self.assertMain(self.hook("问题", env={"CLAUDE_PID": NOBODY}))

    def test_a_task_manager_gets_its_own_task(self):
        out = self.as_task_manager("show question")
        self.assertSelf(out)
        self.assertIn("task manager", out)

    def test_the_name_is_the_worktree_folder(self):
        wt = self.repo.detach_scripts_to_worktree()
        self.set_lock(os.getpid())
        out = self.hook("questions", cwd=wt, env={"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY})
        self.assertSelf(out, os.path.basename(wt))

    def test_a_helper_gets_its_own_task(self):
        out = self.as_helper("show question")
        self.assertSelf(out)
        self.assertIn("human-direct", out)

    def test_no_live_main_manager_still_its_own_task(self):
        self.assertSelf(self.as_orphan("show question"))


class TestLanguage(ShowQuestionCase):
    def test_zh(self):
        self.repo.set_conf("language", "zh")
        for out in (self.as_main("show question"), self.as_task_manager("问题")):
            self.assertIn("## 要你决定", out)
            self.assertIn("(建议)", out)
            self.assertIn("答完了", out)

    def test_en(self):
        self.repo.set_conf("language", "en")
        out = self.as_main("show question")
        self.assertIn("## To decide", out)
        self.assertIn("(recommended)", out)
        self.assertNotIn("要你决定", out)


# ---------------------------------------------------------------- the done flow


class DoneCase(ShowQuestionCase):
    """A page made by the real script: park add, then questions --page."""

    def af(self, *args, cwd=None, role=None):
        env = {"AGENT_FAKE_NOW": NOW}
        if role:
            env["AGENT_ROLE"] = role
        return self.assertOk(self.repo.run("agent-file.sh", *args, env=env, cwd=cwd))

    def make_page(self, cwd=None, role=None, count=1):
        for i in range(count):
            self.af("park", "add", "keep the old API %d?" % i, "alpha", cwd=cwd, role=role)
        page = os.path.join(self.repo.base, "pages", "questions.html")
        os.makedirs(os.path.dirname(page), exist_ok=True)
        args = ["questions", "--page", page] + (["--self"] if role else [])
        self.af(*args, cwd=cwd, role=role)
        self.af("questions", "--url", "https://claude.ai/artifact/abc123", cwd=cwd, role=role)
        return page

    def state(self, folder=None):
        with open(os.path.join(folder or self.repo.dir, "agent_state.txt"), encoding="utf-8") as fh:
            return fh.read()

    def assertDone(self, out):
        self.assertTrue(out.startswith("QUESTIONS ANSWERED"), out)
        for phrase in ("PRINCIPLES.md W18", "https://claude.ai/artifact/abc123", "ArtifactData",
                       "answers", "questions.json", "table", "still open",
                       os.path.join(os.path.realpath(self.repo.plugin), "bin", "agent-file.sh")
                       + " questions answer"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, out)
        self.assertLessEqual(len(out.encode()), MAX_BYTES)


class TestDoneWords(DoneCase):
    def test_the_page_line_is_there(self):
        self.make_page()
        line = [l for l in self.state().splitlines() if l.startswith("QUESTIONS PAGE: ")]
        self.assertEqual(len(line), 1, self.state())
        self.assertIn("https://claude.ai/artifact/abc123 | ", line[0])
        self.assertIn("questions.html | ", line[0])
        self.assertIn("questions.json | since ", line[0])

    def test_done_words_fire_with_an_open_page(self):
        self.make_page()
        for prompt in DONE_WHOLE + DONE_ANYWHERE + ANSWER_LISTS:
            with self.subTest(prompt=prompt):
                self.assertDone(self.as_main(prompt))

    def test_other_prompts_stay_quiet_with_an_open_page(self):
        self.make_page()
        for prompt in NOT_DONE + ['"答完了"', "`done`", "please fix the login page"]:
            with self.subTest(prompt=prompt):
                self.assertEqual(self.as_main(prompt), "")

    def test_no_page_line_never_fires(self):
        self.af("park", "add", "keep the old API?", "alpha")
        for prompt in ("done", "答完了", "1A 2B"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.as_main(prompt), "")

    def test_all_answered_never_fires(self):
        self.make_page()
        self.af("park", "rm", "1")
        for prompt in ("done", "答完了", "1A"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.as_main(prompt), "")

    def test_one_left_open_still_fires(self):
        self.make_page(count=2)
        self.af("park", "rm", "1")
        self.assertDone(self.as_main("答完了"))

    def test_no_map_file_any_open_question_counts(self):
        page = self.make_page()
        os.remove(page[:-len(".html")] + ".json")
        self.assertTrue(self.as_main("done").startswith("QUESTIONS ANSWERED"))
        self.af("park", "rm", "1")
        self.assertEqual(self.as_main("done"), "")

    def test_a_task_manager_reads_its_own_page(self):
        wt = self.repo.detach_scripts_to_worktree()
        self.make_page(cwd=wt, role="task-manager")
        self.set_lock(os.getpid())
        out = self.hook("答完了", cwd=wt, env={"AGENT_ROLE": "task-manager", "CLAUDE_PID": NOBODY})
        self.assertDone(out)
        # the main manager has no page line of its own
        self.assertEqual(self.as_main("答完了"), "")

    def test_a_spawned_helper_agent_never_gets_it(self):
        self.make_page()
        self.set_lock(os.getpid())
        self.assertEqual(self.hook("done", env={"AGENT_ROLE": "worker", "CLAUDE_PID": NOBODY}), "")


# ---------------------------------------------------------------- hooks.json


class TestHooksJson(ShowQuestionCase):
    def hooks(self):
        return json.loads(read("hooks", "hooks.json"))["hooks"]

    def test_user_prompt_submit_runs_it_right_after_show_todo(self):
        entries = self.hooks()["UserPromptSubmit"]
        self.assertEqual(entries.count(HOOK_ENTRY), 1)
        commands = [h["command"] for e in entries for h in e["hooks"]]
        self.assertEqual(commands.index(HOOK_COMMAND), commands.index(TODO_COMMAND) + 1)

    def test_no_other_event_runs_it(self):
        for event, entries in self.hooks().items():
            if event == "UserPromptSubmit":
                continue
            with self.subTest(event=event):
                self.assertNotIn("agent-show-question.sh", json.dumps(entries))

    def test_the_command_runs_for_real_with_the_city_off(self):
        self.set_lock(os.getpid())
        env = self.repo._env({"CLAUDE_PLUGIN_ROOT": self.repo.plugin,
                              "AGENT_CITY_DIR": os.path.join(self.repo.base, "no-city"),
                              "CLAUDE_PID": str(os.getpid())})
        result = subprocess.run(["sh", "-c", HOOK_COMMAND], input=self.payload("show question"),
                                env=env, cwd=self.repo.dir, capture_output=True, text=True,
                                timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertTrue(result.stdout.startswith("SHOW QUESTION"), result.stdout)


# ---------------------------------------------------------------- the rules


class TestTheRule(unittest.TestCase):
    """PRINCIPLES.md W18, short lines, same style as W14."""

    def rule(self):
        return section(read("PRINCIPLES.md"), "W18. Show question", "## C. Human")

    def test_it_sits_right_after_w17_and_nothing_is_renumbered(self):
        text = read("PRINCIPLES.md")
        order = [text.index(h) for h in ("W14. Show todo", "W15. Watch", "W16. Known traps",
                                         "W17. Decider floor", "W18. Show question",
                                         "## C. Human")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(text.count("W18. "), 1)

    def test_one_short_line_per_rule(self):
        lines = self.rule().splitlines()
        bullets = [l for l in lines if l.startswith("- ")]
        self.assertGreaterEqual(len(bullets), 6)
        self.assertLessEqual(len(bullets), 14)
        for line in lines[1:]:
            with self.subTest(line=line[:40]):
                self.assertTrue(line.startswith("- ") or not line.strip(), line)
                self.assertLessEqual(len(line), 200)

    def test_it_says_what_the_owner_decided(self):
        rule = self.rule()
        for phrase in ("show question", "bin/agent-show-question.sh", "UserPromptSubmit",
                       "quoted", "这段代码有什么问题", "bin/agent-file.sh questions", "--self",
                       "whole repo", "own task", "Subagents never", "PARKED:", "todo wait",
                       "mock", "review", "QUESTION:", "ANSWER:", "not read", "stable id",
                       "10 or fewer", "More than 10", "--page", "Artifact", "db", "user",
                       "QUESTIONS PAGE", "one url per repo", "答完了", "ArtifactData",
                       "another machine", "not read: <path> on <machine>",
                       "answers", "questions answer", "still open", "1A 2B", "nothing dropped"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)

    def test_h3_records_every_owner_question(self):
        h3 = section(read("PRINCIPLES.md"), "H3. Report", "H4. Tables")
        line = next((l for l in h3.splitlines() if "park add" in l), "")
        self.assertTrue(line.startswith("- "), h3)
        self.assertLessEqual(len(line), 200)
        for phrase in ("decide section", "park add", "--why", "--evidence", "--options", "--rec",
                       "answered"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, line)
        # the questions OF the decide section are the ones recorded (owner brief point 4)
        self.assertNotIn("outside", line)
        self.assertRegex(line, r"(in|of) (a|the|its) decide section")

    def test_an_answered_question_line_is_named_plainly(self):
        rule = self.rule()
        self.assertNotIn("is not read", rule)
        line = next((l for l in rule.splitlines() if "ANSWER:" in l), "")
        self.assertIn("QUESTION:", line)
        self.assertIn("before the next", line)


# ---------------------------------------------------------------- the quiz


class TestTheQuiz(ScriptCase):
    script = "agent-start.sh"
    ANSWERS = ("1A 2D 3C 4B 5D 6D 7A 8C 9A 10D 11A 12C 13D 14C 15B 16C 17C "
               "18D 19B 20A 21D 22C 23B 24D 25A 26D 27A 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C")

    def quiz(self):
        return self.assertOk(self.repo.run("agent-start.sh", "--quiz"))

    def test_question_37_is_show_question(self):
        out = self.quiz()
        q = out[out.index("Q37. "):]
        self.assertEqual("\n".join(q.splitlines()[:5]), QUIZ_Q37)

    def test_the_quiz_says_37(self):
        out = self.quiz()
        self.assertIn("=== QUIZ — answer all 37 before any work ===", out)
        self.assertIn('--answer "1A 2B 3C ... 37D"', out)
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", out)), 37)

    def test_c_passes(self):
        out = self.assertOk(self.repo.run("agent-start.sh", "--answer", self.ANSWERS))
        self.assertIn("QUIZ RESULT: 37/37 PASS", out)

    def test_another_letter_fails_and_names_w18(self):
        for wrong in ("37A", "37B", "37D"):
            with self.subTest(wrong=wrong):
                result = self.repo.run("agent-start.sh", "--answer",
                                       self.ANSWERS.replace("37C", wrong))
                self.assertEqual(result.returncode, 1)
                self.assertIn("Q37(W18)", result.stdout)

    def test_the_old_36_answers_no_longer_pass(self):
        result = self.repo.run("agent-start.sh", "--answer", self.ANSWERS.replace(" 37C", ""))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Q37(W18)", result.stdout)

    def test_the_usage_says_37(self):
        src = read("bin", "agent-start.sh")
        self.assertIn("print the 37 quiz questions", src)
        self.assertEqual(src.count('--answer "1A 2D ... 37C"'), 2, "the header and the usage line")
        self.assertNotIn("... 36C", src)


# ---------------------------------------------------------------- docs


class TestTheDocs(unittest.TestCase):
    def test_the_readme_names_the_new_files(self):
        text = read("README.md")
        for phrase in ("bin/agent-show-question.sh", "bin/agent_questions.py",
                       "bin/agent-questions-page.html", "bin/agent-file.sh questions",
                       "37-question quiz"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_agent_file_usage_names_the_new_commands(self):
        head = read("bin", "agent-file.sh").split("\nset -eu", 1)[0]
        for phrase in ("questions [--self] [--json]", "questions [--self] --page", "questions --url",
                       "questions answer", "--why", "--evidence", "--fact", "--sub", "--options",
                       "--rec", "park rm --id", "QUESTIONS PAGE:", "ANSWER:"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, head)


if __name__ == "__main__":
    unittest.main()
