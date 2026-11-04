"""Failing tests for 'show question', the collector, park and page part. Written by the task manager first.

CONTRACT. `agent-file.sh questions` lists every question that waits on the
owner. Read only, except --page, --url and answer, which write what they say.
The work is done by bin/agent_questions.py (python3, standard library only, no
sibling imports, like bin/agent_board.py); the page comes from the template
bin/agent-questions-page.html (the approved mock/show-question-mock.html without
its MOCK bar and fake db).

    agent-file.sh questions [--self] [--json]
    agent-file.sh questions [--self] --page <file>
    agent-file.sh questions --url <url>
    agent-file.sh questions answer <id> "<answer>"
    agent-file.sh park add "<question>" ["<task>"] [--sub "<line>"] [--why "<text>"]
        [--evidence "<text>"] [--fact "<key>: <value>"]... [--options "A text|B text"]
        [--rec <letter or option text>]
    agent-file.sh park rm <n> | park rm --id <id>

SOURCES, in this collection order:
  (b) agent_todo.txt lines with an open wait ("waiting <kind> since <date>[: <note>]")
      whose kind is mock, question or review (hold and queue are not questions)
  (c) "QUESTION: <text>" lines (the line starts with it) of agent_state.txt with no
      answer: an answer is a line starting with "ANSWER:" after it, before the next
      "QUESTION:" line and before the next "=== " header line
  (a) "PARKED:" lines of agent_state.txt
  The agent_state.txt files: the main repo's, then every agent_worktree.txt folder
  on this machine (in that file's order, once per real path). A folder that is not
  on this machine: one line "not read: <path> on <machine>", <machine> from the
  "on <machine>" field of the todo line named like the worktree's module, else
  "another machine".
  --self (task manager, Helper): its own todo line (named like the folder of the
  git toplevel of the cwd, the board's rule) and its own agent_state.txt only; in
  the main repo folder itself no state lines (a Helper never shows the main state).

ORDER: grouped by task, the groups in the order their task first comes in the
collection order, inside a group the collection order; numbered 1..N after that.
Task: (b) the todo name, (c) the module of the worktree line (the main repo, or a
folder not in agent_worktree.txt (--self): its folder name), (a) the PARKED task field.

IDS (stable, a valid db document id, letters digits _ . ~ : @ + - only):
  parked    "p-" + sha1(task + "\\n" + question + "\\n" + since)[:10]
  todo      "t-" + name (any other character -> "-") + "-" + kind + "-" + since digits (YYYYMMDDHHMM)
  worktree  "w-" + sha1(module + "\\n" + question text)[:10]
  the same id twice: the later ones get "-2", "-3", ...

FIELDS of a question: n, id, source (parked | todo | worktree), kind (mock |
question | review for todo, else ""), task, title, sub, facts ([[key, value]...]),
options ([{letter, text, rec}...]), since ("YYYY-MM-DD HH:MM" or ""), file (the
absolute path of the file it lives in).
  parked: title = the question; sub, facts, options and rec from the new fields;
     an old line has sub "", facts [], options [].
  todo: title = the note, else zh "看一下 <task> 的 mock" / "<task> 有一个问题等你回答" /
     "验收 <task>", en "Check the <task> mock" / "<task> has a question for you" /
     "Review <task>"; sub ""; facts [["内容" | "What", <what>]] plus
     [["位置" | "Where", "<machine>[ <path>]"]] when the line has an "on" field;
     options mock: zh 可以，继续 | 要改（写在备注里）, en Yes, go on | Change it (say
     how in the note); review: zh 验收通过 | 有问题（写在备注里）, en Passed |
     Something is wrong (say what in the note); question: none. No rec.
  worktree: title = the text; sub ""; facts [["来自" | "From",
     "<module> 任务经理" | "the <module> task manager"]]; options none; since "".
  Language: `language` of agent.conf, zh (or zh-*) else en.

TEXT (--json not given):
    QUESTIONS: <N>
    <blank>
    <n>. [<id>] <task> · <parked | todo <kind> | task manager question>[ · since <since>]
       <title>
       — <sub>                       (only when there is one)
       <key>: <value>                (one per fact)
       <letter>. <text>[ (建议)]      (one per option; en: " (recommended)")
    <blank between questions>
    not read: <path> on <machine>    (after one blank line, one per folder)
JSON: {"count": N, "questions": [...], "not_read": [{"path", "machine"}],
       "intros": {<task>: <the what field of its todo line>}} (only tasks of the list
       that have a todo line)

PARK ADD, new form: stored as one line, every field " | "-separated, in this order:
    PARKED: <question> | <task> | since <now> | sub <line> | fact <key>: <value> ...
        | option A: <text> | option B: <text> ... | rec <letter>
  --why = fact 为什么现在 (en Why now), --evidence = fact 依据 (en Evidence), --fact
  "<key>: <value>" as given; the facts keep the order of the command line.
  --options "A text|B text": lettered A, B, C ... (at most 8). --rec: a letter or the
  exact text of an option (any case) -> "rec <letter>"; --rec with no --options ->
  fact 建议: <text> (en Recommendation). The task may be left out (the folder name).
  Prints "parked: <question>" then "id: <id>". Refused (one stderr line, exit 1,
  nothing written): an empty value, " | " or a line break in any value, an unknown
  option, a flag with no value, --fact without ": " or with an empty key, an empty
  option, more than 8 options, a --rec that is no option.
PARK RM --id <id>: removes that PARKED line (the id as `questions` gives it, own
  agent_state.txt); every other line stays byte for byte. No such id: refused.

QUESTIONS --page <file>: writes the page to <file> (a relative path is taken from
  the cwd), the map to the same path with ".json" instead of ".html" (no ".html":
  "<file>.json"), and the line "QUESTIONS PAGE: <url> | <page> | <map> | since <now>"
  in the session's own agent_state.txt (url kept from the line before, else "-";
  one such line only). Prints "page: <abs page>", "map: <abs map>", "questions:
  <N>", "url: <url or ->". The page = the template with "__SQ_DATA__" replaced by
  JSON {"lang", "repo", "generated", "intros", "questions"} where "<", ">", "&",
  U+2028 and U+2029 are written as \\u003c \\u003e \\u0026 \\u2028 \\u2029 (any other
  character as is, Chinese too); a page question has every field but "file" (no
  local path goes into a published page). The map: {"page", "generated", "questions":
  [{"n", "id", "task", "title", "options": [<letters>]}]}.
QUESTIONS --url <url>: https://claude.ai/artifact/<id> or
  https://claude.ai/code/artifact/<id> (<id> letters, digits, "-", "_") sets the url
  of that line (a missing line: "QUESTIONS PAGE: <url> | - | - | since <now>").
  Anything else refused.
QUESTIONS ANSWER <id> "<answer>": parked -> the PARKED line goes (in whichever
  local agent_state.txt holds it); todo -> that wait closes (as `todo wait <name>
  off`); worktree -> "ANSWER: <answer>" is written right after its QUESTION line.
  Prints one line "answered <id>: ...". Refused: an id `questions` (whole repo)
  does not list, an empty answer, a line break in it.

THE PAGE (template contract, checked on the written page):
  <!doctype html>, a viewport meta, a <title> of 1-4 words, colour tokens on
  :root, dark mode under @media (prefers-color-scheme: dark) guarded by
  :root:not([data-theme="light"]) and again :root[data-theme="dark"], a body
  rule with a background, no <script src>, stylesheets only from
  fonts.googleapis.com, claude.use("db"), claude.use("user"),
  collection("answers"), no localStorage, no MOCK bar, no fake db; elements with
  the ids count, all-rec, clear, copy, copyrow, copybox, h1, intro, b-nodb, b-ro,
  groups, toast; the labels block id="sq-labels" with the same keys for zh and en.
  It runs in tests/questions_page_harness.js (node, stub DOM, its header lists
  what the stub has): cards <section id="q<n>" class="q[ done]">, option buttons
  class "opt" (first child = the letter, aria-checked), a <textarea> per card;
  answers/<id> = {pick, option, note, answeredAt}; never a write on load; saved
  picks come back; 全部按建议 fills only unpicked questions that have a
  recommended option; 清空 takes two clicks and deletes the docs; a note on a
  question with no options is its answer; 复制我的答案 -> #copybox lines
  "<n><letter>[ — <note>]" / "<n> — <note>"; db null -> #b-nodb shown and nothing
  written; user.can("data.write") false -> the options disabled, #b-ro shown.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import BIN, ROOT, ScriptCase

NOW = "2026-11-04 18:00"
HOST = "pc2"
ID_OK = re.compile(r"^[A-Za-z0-9_.~:@+-]+$")
HARNESS = os.path.join(HERE, "questions_page_harness.js")


def pid(task, question, since):
    return "p-" + hashlib.sha1(("%s\n%s\n%s" % (task, question, since)).encode()).hexdigest()[:10]


def wid(module, text):
    return "w-" + hashlib.sha1(("%s\n%s" % (module, text)).encode()).hexdigest()[:10]


def tid(name, kind, since):
    return "t-%s-%s-%s" % (re.sub(r"[^A-Za-z0-9_.~:@+-]", "-", name), kind, re.sub(r"\D", "", since))


def page_data(html):
    m = re.findall(r'<script type="application/json" id="sq-data">(.*?)</script>', html, re.S)
    assert len(m) == 1, len(m)
    return m[0]


class QCase(ScriptCase):
    script = "agent-file.sh"
    lang = "zh"

    def setUp(self):
        super().setUp()
        self.repo.set_conf("language", self.lang)

    def af(self, *args, now=NOW, cwd=None, ok=True, role=None):
        env = {"AGENT_FAKE_NOW": now, "AGENT_FAKE_HOST": HOST}
        if role:
            env["AGENT_ROLE"] = role
        result = self.repo.run("agent-file.sh", *args, cwd=cwd, env=env)
        if ok:
            self.assertOk(result)
        return result

    def snapshot(self, folders=()):
        files = [self.repo.path("agent_todo.txt"), self.repo.path("agent_state.txt")]
        files += [os.path.join(f, "agent_state.txt") for f in folders]
        out = {}
        for f in files:
            out[f] = open(f, encoding="utf-8").read() if os.path.exists(f) else None
        return out

    def refused(self, *args, folders=(), cwd=None, role=None):
        before = self.snapshot(folders)
        result = self.af(*args, ok=False, cwd=cwd, role=role)
        self.assertEqual(result.returncode, 1, (args, result.stdout, result.stderr))
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, (args, result.stderr))
        self.assertEqual(self.snapshot(folders), before, args)
        return result

    def state(self, text, folder=None):
        with open(os.path.join(folder or self.repo.dir, "agent_state.txt"), "a", encoding="utf-8") as fh:
            fh.write(text if text.endswith("\n") else text + "\n")

    def state_text(self, folder=None):
        full = os.path.join(folder or self.repo.dir, "agent_state.txt")
        if not os.path.exists(full):
            return ""
        with open(full, encoding="utf-8") as fh:
            return fh.read()

    def add(self, name, what, est=60, opened="2026-11-04 14:00"):
        self.af("todo", "add", name, "big", what, str(est), now=opened)

    def wait(self, name, *rest, now=NOW):
        self.af("todo", "wait", name, *rest, now=now)

    def todo_line(self, name):
        for line in (self.repo.read("agent_todo.txt") or "").splitlines():
            if line.split(" | ")[0] == name:
                return line
        return None

    def task_worktree(self, name):
        subprocess.run(["git", "-C", self.repo.dir, "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo.dir, "commit", "-q", "-m", "seed2", "--allow-empty"],
                       check=True, capture_output=True)
        path = os.path.join(self.repo.base, name)
        subprocess.run(["git", "-C", self.repo.dir, "worktree", "add", "-q", "-b", name, path],
                       check=True, capture_output=True)
        return os.path.realpath(path)

    def qjson(self, *args, cwd=None, role=None, now=NOW):
        return json.loads(self.af("questions", "--json", *args, cwd=cwd, role=role, now=now).stdout)

    def qtext(self, *args, cwd=None, role=None, now=NOW):
        return self.af("questions", *args, cwd=cwd, role=role, now=now).stdout

    def by_title(self, data, title):
        for q in data["questions"]:
            if q["title"] == title:
                return q
        self.fail("no question %r in %r" % (title, [q["title"] for q in data["questions"]]))


# ---------------------------------------------------------------- park add, old and new form


class TestParkOldForm(QCase):
    def test_the_old_form_is_unchanged(self):
        out = self.af("park", "add", "which DB for reports?").stdout
        self.assertEqual(out.splitlines()[0], "parked: which DB for reports?")
        self.assertEqual(out.splitlines()[1], "id: " + pid("project", "which DB for reports?", NOW))
        self.assertEqual(self.state_text(), "PARKED: which DB for reports? | project | since %s\n" % NOW)
        self.af("park", "add", "keep the old API?", "alpha")
        self.assertIn("PARKED: keep the old API? | alpha | since %s\n" % NOW, self.state_text())

    def test_an_old_line_is_a_question_with_no_fields(self):
        self.state("PARKED: 城市要不要做夜景模式？ | city-polish | since 2026-10-28 10:15")
        q = self.qjson()["questions"][0]
        self.assertEqual((q["id"], q["source"], q["kind"], q["task"], q["title"], q["sub"],
                          q["facts"], q["options"], q["since"]),
                         (pid("city-polish", "城市要不要做夜景模式？", "2026-10-28 10:15"), "parked",
                          "", "city-polish", "城市要不要做夜景模式？", "", [], [], "2026-10-28 10:15"))
        self.assertEqual(q["file"], os.path.join(self.repo.dir, "agent_state.txt"))


class TestParkNewForm(QCase):
    def test_every_field_is_stored_in_order(self):
        out = self.af("park", "add", "merge both PRs?", "beta", "--sub", "2 PRs · both green",
                      "--why", "两个都过了浏览器检查", "--evidence", "#305 #306 绿",
                      "--fact", "现在: 都在等合并", "--options", "两个都合并|只合并 #305|都不合并",
                      "--rec", "A").stdout
        self.assertEqual(out.splitlines()[0], "parked: merge both PRs?")
        self.assertEqual(self.state_text(),
                         "PARKED: merge both PRs? | beta | since %s | sub 2 PRs · both green"
                         " | fact 为什么现在: 两个都过了浏览器检查 | fact 依据: #305 #306 绿"
                         " | fact 现在: 都在等合并 | option A: 两个都合并 | option B: 只合并 #305"
                         " | option C: 都不合并 | rec A\n" % NOW)
        q = self.qjson()["questions"][0]
        self.assertEqual(q["title"], "merge both PRs?")
        self.assertEqual(q["sub"], "2 PRs · both green")
        self.assertEqual(q["facts"], [["为什么现在", "两个都过了浏览器检查"], ["依据", "#305 #306 绿"],
                                      ["现在", "都在等合并"]])
        self.assertEqual(q["options"], [{"letter": "A", "text": "两个都合并", "rec": True},
                                        {"letter": "B", "text": "只合并 #305", "rec": False},
                                        {"letter": "C", "text": "都不合并", "rec": False}])
        self.assertEqual(q["id"], pid("beta", "merge both PRs?", NOW))

    def test_facts_keep_the_command_line_order(self):
        self.af("park", "add", "q?", "t", "--fact", "例子: 1", "--evidence", "e", "--why", "w")
        self.assertEqual(self.qjson()["questions"][0]["facts"],
                         [["例子", "1"], ["依据", "e"], ["为什么现在", "w"]])

    def test_rec_by_option_text_and_the_task_left_out(self):
        self.af("park", "add", "poll every?", "--options", "30 s|60 s", "--rec", "60 S")
        self.assertTrue(self.state_text().rstrip("\n").endswith(" | option A: 30 s | option B: 60 s | rec B"),
                        self.state_text())
        q = self.qjson()["questions"][0]
        self.assertEqual(q["task"], "project")
        self.assertEqual([o["rec"] for o in q["options"]], [False, True])

    def test_rec_without_options_is_a_fact(self):
        self.af("park", "add", "6 digits or 8?", "join", "--rec", "6 digits")
        self.assertIn(" | fact 建议: 6 digits\n", self.state_text())
        q = self.qjson()["questions"][0]
        self.assertEqual((q["facts"], q["options"]), ([["建议", "6 digits"]], []))

    def test_board_still_shows_the_question(self):
        self.af("park", "add", "merge both PRs?", "beta", "--why", "w", "--options", "a|b", "--rec", "a")
        board = self.af("board").stdout
        row = [l for l in board.splitlines() if "merge both PRs?" in l]
        self.assertEqual(len(row), 1, board)
        self.assertNotIn("option A", row[0])
        self.assertIn("| beta |", row[0])

    def test_refusals(self):
        self.af("park", "add", "already here?")
        for args in (("--why", ""), ("--why", "a | b"), ("--sub", "a\nb"), ("--fact", "no colon"),
                     ("--fact", ": value"), ("--fact", "key: "), ("--options", "a||b"),
                     ("--options", "|".join("abcdefghi")), ("--options", "a|b", "--rec", "Z"),
                     ("--options", "a|b", "--rec", "nope"), ("--foo", "x"), ("--why",),
                     ("--options", "")):
            with self.subTest(args=args):
                self.refused("park", "add", "new question?", "alpha", *args)
        self.refused("park", "add", "", "--why", "w")


class TestParkNewFormEnglish(QCase):
    lang = "en"

    def test_english_keys(self):
        self.af("park", "add", "q?", "t", "--why", "w", "--evidence", "e")
        self.af("park", "add", "r?", "t", "--rec", "go")
        data = self.qjson()
        self.assertEqual(self.by_title(data, "q?")["facts"], [["Why now", "w"], ["Evidence", "e"]])
        self.assertEqual(self.by_title(data, "r?")["facts"], [["Recommendation", "go"]])


class TestParkRmId(QCase):
    def test_rm_by_id(self):
        self.state("Brief: you are the task manager.\nSTEP 3 done.")
        self.af("park", "add", "first?", "alpha", now="2026-11-04 10:00")
        self.af("park", "add", "second?", "alpha", "--why", "w", now="2026-11-04 11:00")
        out = self.af("park", "rm", "--id", pid("alpha", "second?", "2026-11-04 11:00")).stdout
        self.assertTrue(out.startswith("parked 2 removed: second?"), out)
        self.assertEqual(self.state_text(), "Brief: you are the task manager.\nSTEP 3 done.\n"
                         "PARKED: first? | alpha | since 2026-11-04 10:00\n")
        self.af("park", "rm", "1")
        self.assertEqual(self.state_text(), "Brief: you are the task manager.\nSTEP 3 done.\n")

    def test_refusals(self):
        self.af("park", "add", "first?", "alpha")
        for args in (("--id",), ("--id", "p-0000000000"), ("--id", "x", "y")):
            with self.subTest(args=args):
                self.refused("park", "rm", *args)


# ---------------------------------------------------------------- the collector


class SourcesCase(QCase):
    """Three todo waits, two open worktree questions, three parked questions,
    two folders that are not here."""

    def setUp(self):
        super().setUp()
        self.add("alpha", "the login form")
        self.add("beta", "bank recon")
        self.add("gamma", "held task")
        self.add("delta", "closed wait")
        self.add("epsilon", "phone build")
        self.wait("alpha", "on", "mock", "看登录页 mock", now="2026-11-04 14:30")
        self.wait("beta", "on", "question", now="2026-11-04 15:00")
        self.wait("gamma", "on", "hold", now="2026-11-04 15:00")
        self.wait("delta", "on", "question", now="2026-11-04 15:00")
        self.wait("delta", "off", now="2026-11-04 15:10")
        self.wait("epsilon", "on", "review", now="2026-11-04 16:00")
        self.af("todo", "where", "beta", "laptop", "/nowhere/beta")
        self.state("PARKED: which DB for reports? | project | since 2026-11-04 10:00")
        self.af("park", "add", "merge both PRs?", "beta", "--why", "两个都过了浏览器检查",
                "--evidence", "#305 #306 绿", "--options", "两个都合并|只合并 #305|都不合并",
                "--rec", "A")
        self.wt = self.repo.make_worktree("alpha", as_repo=False)
        self.state('Brief. ASK: append "QUESTION: ..." under === QUESTIONS === here.\n'
                   "=== QUESTIONS ===\n"
                   "QUESTION: poll every 30 s or 60 s?\n"
                   "ANSWER: 60 s\n"
                   "QUESTION: 6 digits or 8?\n"
                   "\n"
                   "  ANSWER: 6\n"
                   "QUESTION: keep the cap?\n"
                   "=== HEARTBEAT ===\n"
                   "ANSWER: this is not under the question\n"
                   "QUESTION: drop the old flag?\n"
                   "PARKED: keep the old API? | alpha | since 2026-11-04 11:00\n", folder=self.wt)
        self.repo.set_worktree_lines([(self.wt, "alpha", "working"),
                                      ("/nowhere/beta", "beta", "working"),
                                      ("/nowhere/zeta", "zeta", "idle")])

    EXPECTED = [("alpha", "看登录页 mock"), ("alpha", "keep the cap?"), ("alpha", "drop the old flag?"),
                ("alpha", "keep the old API?"), ("beta", "beta 有一个问题等你回答"),
                ("beta", "merge both PRs?"), ("epsilon", "验收 epsilon"),
                ("project", "which DB for reports?")]


class TestSources(SourcesCase):
    def test_every_source_in_task_groups(self):
        data = self.qjson()
        self.assertEqual(data["count"], 8)
        self.assertEqual([(q["task"], q["title"]) for q in data["questions"]], self.EXPECTED)
        self.assertEqual([q["n"] for q in data["questions"]], list(range(1, 9)))
        self.assertEqual(data["not_read"], [{"path": "/nowhere/beta", "machine": "laptop"},
                                            {"path": "/nowhere/zeta", "machine": "another machine"}])
        self.assertEqual(data["intros"], {"alpha": "the login form", "beta": "bank recon",
                                          "epsilon": "phone build"})

    def test_the_fields_of_each_kind(self):
        data = self.qjson()
        todo = os.path.join(self.repo.dir, "agent_todo.txt")
        mock = self.by_title(data, "看登录页 mock")
        self.assertEqual((mock["id"], mock["source"], mock["kind"], mock["sub"], mock["facts"],
                          mock["options"], mock["since"], mock["file"]),
                         (tid("alpha", "mock", "2026-11-04 14:30"), "todo", "mock", "",
                          [["内容", "the login form"]],
                          [{"letter": "A", "text": "可以，继续", "rec": False},
                           {"letter": "B", "text": "要改（写在备注里）", "rec": False}],
                          "2026-11-04 14:30", todo))
        ask = self.by_title(data, "beta 有一个问题等你回答")
        self.assertEqual((ask["kind"], ask["facts"], ask["options"]),
                         ("question", [["内容", "bank recon"], ["位置", "laptop /nowhere/beta"]], []))
        review = self.by_title(data, "验收 epsilon")
        self.assertEqual([o["text"] for o in review["options"]], ["验收通过", "有问题（写在备注里）"])
        cap = self.by_title(data, "keep the cap?")
        self.assertEqual((cap["id"], cap["source"], cap["kind"], cap["facts"], cap["options"],
                          cap["since"], cap["file"]),
                         (wid("alpha", "keep the cap?"), "worktree", "", [["来自", "alpha 任务经理"]],
                          [], "", os.path.join(self.wt, "agent_state.txt")))
        old = self.by_title(data, "keep the old API?")
        self.assertEqual((old["id"], old["file"]), (pid("alpha", "keep the old API?", "2026-11-04 11:00"),
                                                    os.path.join(self.wt, "agent_state.txt")))
        self.assertEqual(set(mock), {"n", "id", "source", "kind", "task", "title", "sub", "facts",
                                     "options", "since", "file"})

    def test_answered_and_closed_ones_are_not_listed(self):
        titles = [q["title"] for q in self.qjson()["questions"]]
        for gone in ("poll every 30 s or 60 s?", "6 digits or 8?", "gamma 有一个问题等你回答",
                     "delta 有一个问题等你回答", "..."):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, titles)
        self.assertFalse(any("held task" in json.dumps(q, ensure_ascii=False) for q in self.qjson()["questions"]))

    def test_the_text_form(self):
        out = self.qtext()
        lines = out.splitlines()
        self.assertEqual(lines[0], "QUESTIONS: 8")
        self.assertEqual(lines[1], "")
        heads = [l for l in lines if re.match(r"^\d+\. \[", l)]
        self.assertEqual(len(heads), 8, out)
        self.assertEqual(heads[0], "1. [%s] alpha · todo mock · since 2026-11-04 14:30"
                         % tid("alpha", "mock", "2026-11-04 14:30"))
        self.assertEqual(heads[1], "2. [%s] alpha · task manager question" % wid("alpha", "keep the cap?"))
        six = lines[lines.index(heads[5]):]
        self.assertEqual(six[:7], [
            "6. [%s] beta · parked · since %s" % (pid("beta", "merge both PRs?", NOW), NOW),
            "   merge both PRs?",
            "   为什么现在: 两个都过了浏览器检查",
            "   依据: #305 #306 绿",
            "   A. 两个都合并 (建议)",
            "   B. 只合并 #305",
            "   C. 都不合并"])
        self.assertEqual(lines[-2:], ["not read: /nowhere/beta on laptop",
                                      "not read: /nowhere/zeta on another machine"])
        self.assertEqual(lines[-3], "")

    def test_a_sub_line(self):
        self.af("park", "add", "with a sub?", "omega", "--sub", "2 repos")
        out = self.qtext()
        at = out.splitlines().index("   with a sub?")
        self.assertEqual(out.splitlines()[at + 1], "   — 2 repos")

    def test_it_writes_nothing(self):
        def snap():
            rows = []
            for dirpath, _, names in os.walk(self.repo.base):
                for name in names:
                    full = os.path.join(dirpath, name)
                    st = os.stat(full)
                    rows.append((full, st.st_size, st.st_mtime_ns))
            return sorted(rows)
        before = snap()
        self.qtext()
        self.qjson()
        self.qjson("--self", role="task-manager", cwd=self.wt)
        self.assertEqual(snap(), before)


class TestSourcesEnglish(SourcesCase):
    lang = "en"

    def test_english_words(self):
        data = self.qjson()
        mock = self.by_title(data, "看登录页 mock")
        self.assertEqual(mock["facts"], [["What", "the login form"]])
        self.assertEqual([o["text"] for o in mock["options"]], ["Yes, go on", "Change it (say how in the note)"])
        self.assertEqual(self.by_title(data, "beta has a question for you")["facts"][1],
                         ["Where", "laptop /nowhere/beta"])
        self.assertEqual([o["text"] for o in self.by_title(data, "Review epsilon")["options"]],
                         ["Passed", "Something is wrong (say what in the note)"])
        self.assertEqual(self.by_title(data, "keep the cap?")["facts"], [["From", "the alpha task manager"]])
        self.assertIn("   A. 两个都合并 (recommended)", self.qtext().splitlines())


class TestIds(QCase):
    def test_stable_and_valid(self):
        self.add("my task/x", "odd name")
        self.wait("my task/x", "on", "question", now="2026-11-04 15:00")
        self.af("park", "add", "same?", "alpha", now="2026-11-04 10:00")
        self.af("park", "add", "same?", "alpha", now="2026-11-04 10:00")
        self.state("QUESTION: dup?\nQUESTION: dup?")
        one, two = self.qjson(), self.qjson()
        self.assertEqual(one, two)
        ids = [q["id"] for q in one["questions"]]
        self.assertEqual(len(set(ids)), len(ids), ids)
        for i in ids:
            with self.subTest(id=i):
                self.assertRegex(i, ID_OK)
        self.assertIn(tid("my task/x", "question", "2026-11-04 15:00"), ids)
        self.assertEqual(tid("my task/x", "question", "2026-11-04 15:00"), "t-my-task-x-question-202611041500")
        p = pid("alpha", "same?", "2026-11-04 10:00")
        w = wid("project", "dup?")
        self.assertEqual([i for i in ids if i.startswith(p)], [p, p + "-2"])
        self.assertEqual([i for i in ids if i.startswith(w)], [w, w + "-2"])

    def test_a_new_question_changes_no_other_id(self):
        self.af("park", "add", "first?", "alpha")
        before = {q["title"]: q["id"] for q in self.qjson()["questions"]}
        self.af("park", "add", "second?", "beta")
        after = {q["title"]: q["id"] for q in self.qjson()["questions"]}
        self.assertEqual(after["first?"], before["first?"])

    def test_nothing_open(self):
        self.assertEqual(self.qjson(), {"count": 0, "questions": [], "not_read": [], "intros": {}})
        self.assertEqual(self.qtext(), "QUESTIONS: 0\n")


class TestSelf(QCase):
    def test_a_task_manager_gets_its_own_task_only(self):
        alpha = self.task_worktree("alpha")
        self.add("alpha", "the login form")
        self.add("beta", "bank recon")
        self.wait("alpha", "on", "mock", now="2026-11-04 14:30")
        self.wait("beta", "on", "question", now="2026-11-04 15:00")
        self.state("PARKED: main's own question | project | since 2026-11-04 10:00")
        self.af("park", "add", "keep the old API?", cwd=alpha, role="task-manager")
        self.state("QUESTION: poll every 30 s?", folder=alpha)
        data = self.qjson("--self", cwd=alpha, role="task-manager")
        self.assertEqual([(q["task"], q["title"]) for q in data["questions"]],
                         [("alpha", "看一下 alpha 的 mock"), ("alpha", "poll every 30 s?"),
                          ("alpha", "keep the old API?")])
        whole = self.qjson()   # the main manager: not in agent_worktree.txt, so not read
        self.assertEqual([q["title"] for q in whole["questions"]],
                         ["看一下 alpha 的 mock", "beta 有一个问题等你回答", "main's own question"])

    def test_a_helper_in_the_main_repo_never_shows_the_main_state(self):
        self.state("PARKED: main's own question | project | since 2026-11-04 10:00\nQUESTION: main q?")
        self.assertEqual(self.qjson("--self")["count"], 0)

    def test_refusals(self):
        for args in (("--foo",), ("--page",), ("--json", "--page", "x.html"), ("extra",),
                     ("--url",), ("answer",), ("answer", "p-0000000000")):
            with self.subTest(args=args):
                self.refused("questions", *args)


# ---------------------------------------------------------------- answer and url


class TestAnswer(SourcesCase):
    def test_a_parked_question_goes(self):
        text_before = self.state_text(self.wt)
        i = pid("alpha", "keep the old API?", "2026-11-04 11:00")
        out = self.af("questions", "answer", i, "keep it").stdout
        self.assertTrue(out.startswith("answered %s: " % i), out)
        self.assertEqual(self.state_text(self.wt),
                         text_before.replace("PARKED: keep the old API? | alpha | since 2026-11-04 11:00\n", ""))
        self.assertNotIn("keep the old API?", [q["title"] for q in self.qjson()["questions"]])

    def test_a_todo_wait_closes(self):
        i = tid("alpha", "mock", "2026-11-04 14:30")
        self.af("questions", "answer", i, "MOCK YES", now="2026-11-04 15:00")
        line = self.todo_line("alpha")
        self.assertNotIn("waiting", line)
        self.assertIn("waited 30m", line)
        self.refused("questions", "answer", i, "again")

    def test_a_worktree_question_gets_its_answer_line(self):
        i = wid("alpha", "keep the cap?")
        self.af("questions", "answer", i, "yes, a pointer")
        lines = self.state_text(self.wt).splitlines()
        at = lines.index("QUESTION: keep the cap?")
        self.assertEqual(lines[at + 1], "ANSWER: yes, a pointer")
        self.assertEqual(lines[at + 2], "=== HEARTBEAT ===")
        self.assertNotIn("keep the cap?", [q["title"] for q in self.qjson()["questions"]])

    def test_refusals(self):
        i = wid("alpha", "keep the cap?")
        for args in (("answer", "p-0000000000", "x"), ("answer", i, ""), ("answer", i, "a\nb"),
                     ("answer", i), ("answer",)):
            with self.subTest(args=args):
                self.refused("questions", *args, folders=(self.wt,))


class TestUrl(QCase):
    URL = "https://claude.ai/artifact/abc-123_x"

    def page_lines(self, folder=None):
        return [l for l in self.state_text(folder).splitlines() if l.startswith("QUESTIONS PAGE: ")]

    def test_a_url_without_a_page_line_makes_one(self):
        self.af("questions", "--url", self.URL)
        self.assertEqual(self.page_lines(), ["QUESTIONS PAGE: %s | - | - | since %s" % (self.URL, NOW)])

    def test_page_then_url_then_page_keeps_one_line_and_the_url(self):
        self.af("park", "add", "q?", "t")
        page = os.path.join(self.repo.base, "out", "questions.html")
        os.makedirs(os.path.dirname(page))
        self.af("questions", "--page", page)
        self.assertEqual(self.page_lines(), ["QUESTIONS PAGE: - | %s | %s | since %s"
                                             % (page, page[:-5] + ".json", NOW)])
        self.af("questions", "--url", "https://claude.ai/code/artifact/0f8e2c1a-77aa")
        self.af("questions", "--page", page, now="2026-11-04 19:00")
        self.assertEqual(self.page_lines(), ["QUESTIONS PAGE: https://claude.ai/code/artifact/0f8e2c1a-77aa"
                                             " | %s | %s | since 2026-11-04 19:00" % (page, page[:-5] + ".json")])

    def test_bad_urls(self):
        for url in ("", "http://claude.ai/artifact/x", "https://evil.com/artifact/x",
                    "https://claude.ai/artifact/a b", "https://claude.ai/artifact/x | y",
                    "https://claude.ai/artifact/", "https://claude.ai/chat/abc"):
            with self.subTest(url=url):
                self.refused("questions", "--url", url)


# ---------------------------------------------------------------- the page writer


class PageCase(QCase):
    def setUp(self):
        super().setUp()
        self.out = os.path.join(self.repo.base, "out")
        os.makedirs(self.out)

    def write_page(self, *args, name="questions.html", cwd=None, role=None):
        page = os.path.join(self.out, name)
        res = self.af("questions", "--page", page, *args, cwd=cwd, role=role).stdout
        with open(page, encoding="utf-8") as fh:
            html = fh.read()
        return page, html, res

    def park_many(self, n):
        for i in range(n):
            self.af("park", "add", "question %02d?" % i, "task%d" % (i % 3),
                    "--options", "yes|no", "--rec", "yes")


class TestPageWriter(PageCase):
    def test_the_page_the_map_and_the_output(self):
        self.park_many(3)
        page, html, out = self.write_page()
        mapf = page[:-5] + ".json"
        self.assertEqual(out.splitlines(), ["page: " + page, "map: " + mapf, "questions: 3", "url: -"])
        data = json.loads(page_data(html))
        listed = self.qjson()
        self.assertEqual(set(data), {"lang", "repo", "generated", "intros", "questions"})
        self.assertEqual((data["lang"], data["repo"], data["generated"]), ("zh", "project", NOW))
        self.assertEqual([(q["n"], q["id"], q["title"], q["options"]) for q in data["questions"]],
                         [(q["n"], q["id"], q["title"], q["options"]) for q in listed["questions"]])
        self.assertEqual(data["questions"], [{k: v for k, v in q.items() if k != "file"}
                                             for q in listed["questions"]])
        with open(mapf, encoding="utf-8") as fh:
            m = json.load(fh)
        self.assertEqual(m["page"], page)
        self.assertEqual(m["generated"], NOW)
        self.assertEqual(m["questions"], [{"n": q["n"], "id": q["id"], "task": q["task"], "title": q["title"],
                                           "options": [o["letter"] for o in q["options"]]}
                                          for q in listed["questions"]])

    def test_escaping(self):
        nasty = '</script><b>x</b> & "q" \'q\' <img src=x onerror=alert(1)>'
        self.af("park", "add", nasty, "t", "--fact", "代码: a b </SCRIPT> &amp;",
                "--options", "<i>A</i>|B & C", "--rec", "B & C")
        _, html, _ = self.write_page()
        raw = page_data(html)
        for ch in ("<", ">", "&", " ", " "):
            with self.subTest(ch=repr(ch)):
                self.assertNotIn(ch, raw)
        for esc in ("\\u003c", "\\u003e", "\\u0026", "\\u2028"):
            self.assertIn(esc, raw)
        q = json.loads(raw)["questions"][0]
        self.assertEqual(q["title"], nasty)
        self.assertEqual(q["facts"], [["代码", "a b </SCRIPT> &amp;"]])
        self.assertEqual([o["text"] for o in q["options"]], ["<i>A</i>", "B & C"])
        self.assertEqual(html.lower().count("</script>"), html.lower().count("<script"))
        self.assertNotIn("__SQ_DATA__", html)

    def test_chinese_is_kept_as_is(self):
        self.af("park", "add", "要不要整理 agent_ideas.txt？", "auto-pipeline", "--why", "每次启动都会读它")
        _, html, _ = self.write_page()
        raw = page_data(html)
        self.assertIn("要不要整理 agent_ideas.txt？", raw)
        self.assertIn("每次启动都会读它", raw)

    def test_counts_0_1_11_40(self):
        made = 0
        for n in (0, 1, 11, 40):
            with self.subTest(n=n):
                self.park_many(n - made)
                made = n
                page, html, out = self.write_page(name="q%d.html" % n)
                data = json.loads(page_data(html))
                self.assertEqual(len(data["questions"]), n)
                self.assertEqual([q["n"] for q in data["questions"]], list(range(1, n + 1)))
                self.assertIn("questions: %d" % n, out.splitlines())
                with open(page[:-5] + ".json", encoding="utf-8") as fh:
                    self.assertEqual(len(json.load(fh)["questions"]), n)
                self.assertLess(len(html.encode()), 2 * 1024 * 1024)

    def test_english_page(self):
        self.repo.set_conf("language", "en")
        self.park_many(1)
        _, html, _ = self.write_page()
        self.assertEqual(json.loads(page_data(html))["lang"], "en")

    def test_a_relative_path_and_no_html_suffix(self):
        self.park_many(1)
        res = self.af("questions", "--page", "rel/page", cwd=self.repo.dir, ok=False)
        os.makedirs(self.repo.path("rel"))
        out = self.af("questions", "--page", "rel/page").stdout
        self.assertIn("page: " + self.repo.path("rel", "page"), out.splitlines())
        self.assertIn("map: " + self.repo.path("rel", "page.json"), out.splitlines())
        self.assertTrue(os.path.exists(self.repo.path("rel", "page.json")))
        self.assertNotEqual(res.returncode, 0, "a folder that does not exist: refused")

    def test_a_task_manager_writes_its_own_page_line(self):
        wt = self.task_worktree("alpha")
        self.af("park", "add", "mine?", cwd=wt, role="task-manager")
        self.af("park", "add", "main's?")
        _, html, _ = self.write_page("--self", cwd=wt, role="task-manager")
        self.assertEqual([q["title"] for q in json.loads(page_data(html))["questions"]], ["mine?"])
        self.assertTrue(any(l.startswith("QUESTIONS PAGE: ") for l in self.state_text(wt).splitlines()))
        self.assertFalse(any(l.startswith("QUESTIONS PAGE: ") for l in self.state_text().splitlines()))

    def test_it_writes_only_the_page_the_map_and_the_state(self):
        self.park_many(2)

        def snap():
            rows = {}
            for dirpath, _, names in os.walk(self.repo.base):
                for name in names:
                    full = os.path.join(dirpath, name)
                    with open(full, "rb") as fh:
                        rows[full] = fh.read()
            return rows
        before = snap()
        page, _, _ = self.write_page()
        after = snap()
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        self.assertEqual(changed, sorted([page, page[:-5] + ".json", self.repo.path("agent_state.txt")]))


class TestTheTemplate(PageCase):
    IDS = ("count", "all-rec", "clear", "copy", "copyrow", "copybox", "h1", "intro", "b-nodb",
           "b-ro", "groups", "toast")

    def test_the_template_has_one_data_slot(self):
        with open(os.path.join(BIN, "agent-questions-page.html"), encoding="utf-8") as fh:
            tpl = fh.read()
        self.assertEqual(tpl.count("__SQ_DATA__"), 1)
        self.assertIn('<script type="application/json" id="sq-data">__SQ_DATA__</script>', tpl)

    def test_the_artifact_page_contract(self):
        self.park_many(2)
        _, html, _ = self.write_page()
        low = html.lower()
        self.assertTrue(low.lstrip().startswith("<!doctype html>"))
        self.assertRegex(html, r'<meta name="viewport" content="width=device-width,initial-scale=1')
        titles = re.findall(r"<title>(.*?)</title>", html, re.S)
        self.assertEqual(len(titles), 1)
        self.assertTrue(1 <= len(titles[0].split()) <= 4, titles)
        self.assertRegex(html, r":root\s*\{[^}]*--[a-z-]+\s*:")
        self.assertIn("@media (prefers-color-scheme: dark)", html)
        self.assertIn(':root:not([data-theme="light"])', html)
        self.assertRegex(html, r':root\[data-theme="dark"\]\s*\{')
        self.assertRegex(html, r"(?s)\bbody\s*\{[^}]*background")
        self.assertNotRegex(low, r"<script[^>]*\ssrc=")
        for href in re.findall(r'<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"', html):
            self.assertTrue(href.startswith("https://fonts.googleapis.com/"), href)
        for needle in ('claude.use("db")', 'claude.use("user")', 'collection("answers")'):
            self.assertIn(needle, html)
        for banned in ("localStorage", "mockbar", "MOCK", "fakeDb", "mockUse"):
            self.assertNotIn(banned, html)
        for i in self.IDS:
            with self.subTest(id=i):
                self.assertEqual(len(re.findall(r'\sid="%s"' % re.escape(i), html)), 1)
        labels = json.loads(re.search(r'<script type="application/json" id="sq-labels">(.*?)</script>',
                                      html, re.S).group(1))
        self.assertEqual(set(labels), {"zh", "en"})
        self.assertEqual(set(labels["zh"]), set(labels["en"]))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestPageInNode(PageCase):
    """The page's script, run by tests/questions_page_harness.js on a stub DOM."""

    def setUp(self):
        super().setUp()
        self.af("park", "add", "keep the old API?", "alpha", "--options", "keep|drop", "--rec", "keep")
        self.af("park", "add", "夜景模式要不要做？", "alpha")
        self.af("park", "add", "6 digits or 8?", "beta", "--options", "6 digits|8 digits", "--rec", "B")
        self.page, _, _ = self.write_page()
        self.ids = [q["id"] for q in self.qjson()["questions"]]

    def run_page(self, db="on", saved=None, actions=()):
        scenario = {"db": db, "saved": saved or {}, "actions": list(actions)}
        res = subprocess.run(["node", HARNESS, self.page, json.dumps(scenario)],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    def saved_pick(self, letter="B", option="drop"):
        return {self.ids[0]: {"pick": letter, "option": option, "note": "",
                              "answeredAt": "2026-11-04T10:00:00.000Z"}}

    def test_load_shows_saved_picks_and_never_writes(self):
        r = self.run_page(saved=self.saved_pick())
        self.assertEqual(r["cards"], 3)
        self.assertEqual(r["writesOnLoad"], 0)
        self.assertEqual(r["checked"], {"1": "B"})
        self.assertEqual(r["done"], [1])
        self.assertRegex(r["count"], r"1\D+3")
        self.assertIn("3", r["h1"])
        self.assertFalse(r["nodb"])

    def test_a_pick_is_saved_at_once(self):
        r = self.run_page(actions=[["pick", 1, "A"]])
        self.assertEqual(len(r["writes"]), 1, r["writes"])
        w = r["writes"][0]
        self.assertEqual((w["op"], w["id"]), ("set", self.ids[0]))
        self.assertEqual(set(w["body"]), {"pick", "option", "note", "answeredAt"})
        self.assertEqual((w["body"]["pick"], w["body"]["option"], w["body"]["note"]), ("A", "keep", ""))
        self.assertRegex(w["body"]["answeredAt"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(r["checked"], {"1": "A"})

    def test_all_rec_fills_only_the_unpicked(self):
        r = self.run_page(saved=self.saved_pick(), actions=[["all-rec"]])
        self.assertEqual([(w["op"], w["id"], w["body"]["pick"]) for w in r["writes"]],
                         [("set", self.ids[2], "B")])
        self.assertEqual(r["checked"], {"1": "B", "3": "B"})

    def test_a_note_is_the_answer_without_options(self):
        r = self.run_page(actions=[["note", 2, "先不做"], ["blur", 2]])
        sets = [w for w in r["writes"] if w["id"] == self.ids[1]]
        self.assertEqual(len(sets), 1, r["writes"])
        self.assertEqual((sets[0]["body"]["pick"], sets[0]["body"]["note"]), ("", "先不做"))
        self.assertEqual(r["done"], [2])

    def test_copy_my_answers(self):
        r = self.run_page(actions=[["pick", 1, "A"], ["note", 2, "先不做"], ["pick", 3, "B"],
                                   ["note", 3, "以后再说"], ["copy"]])
        self.assertEqual(r["copy"], "1A\n2 — 先不做\n3B — 以后再说")

    def test_clear_takes_two_clicks(self):
        one = self.run_page(saved=self.saved_pick(), actions=[["clear"]])
        self.assertEqual((one["writes"], one["checked"]), ([], {"1": "B"}))
        two = self.run_page(saved=self.saved_pick(), actions=[["clear"], ["clear"]])
        self.assertEqual([(w["op"], w["id"]) for w in two["writes"]], [("delete", self.ids[0])])
        self.assertEqual(two["checked"], {})

    def test_no_db_shows_the_banner_and_keeps_the_picks_in_the_page(self):
        r = self.run_page(db="off", actions=[["pick", 1, "A"], ["copy"]])
        self.assertTrue(r["nodb"])
        self.assertEqual(r["writes"], [])
        self.assertEqual((r["checked"], r["copy"]), ({"1": "A"}, "1A"))

    def test_read_only(self):
        r = self.run_page(db="ro")
        self.assertTrue(r["disabled"])
        self.assertTrue(r["ro"])


if __name__ == "__main__":
    unittest.main()
