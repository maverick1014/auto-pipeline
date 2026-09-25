"""Failing tests for bin/agent-city-hook.sh, the hook that feeds the agent city.

CONTRACT

  Where
    city dir   $AGENT_CITY_DIR, default $HOME/.cache/agent-city
    switch     <dir>/on, one line "<pid> <port>", written by the city server
    output     <dir>/events.jsonl, one JSON object per line, appended

  1. Off costs nothing. No <dir>/on, or its pid is not a number, or that
     process is dead: write nothing, print nothing, exit 0.
  2. On: read the hook JSON from stdin and append ONE line with exactly these
     keys, in this order, all strings, "" when absent:
       ev    hook_event_name
       sid   session_id
       aid   agent_id     } only from the part of the payload before
       at    agent_type   } "tool_input", so a tool's own input or output
       tool  tool_name    } can never fake them
       nt    notification_type
       proj  last part of cwd
       role  $AGENT_ROLE, only the characters [A-Za-z0-9._-] kept
       desc  tool_input.description    only when tool is Agent or Task
       sub   tool_input.subagent_type  only when tool is Agent or Task
       q     first "question" in tool_input, only when tool is AskUserQuestion
       klen  the byte length (a number, as a string) of the JSON-escaped
             tool_input.command (Bash), tool_input.file_path (Edit, Write,
             MultiEdit) or tool_input.url (WebFetch), found in the first 4096
             bytes; "" for other tools or when not found there. Only the
             length, never the text: it lets the city tell which request a
             terminal answer closed (tests/test_agent_city_interact.py).
       repo  growth (requirements/city.md): the physical path of the git
             common dir of cwd, so a linked worktree gives its main repo's
             .git. Found with builtins only: walk up from cwd to the first
             folder holding .git; a .git folder is the answer; a .git file
             ("gitdir: <path>") points at the worktree's git dir, whose
             "commondir" file (relative to it) points at the common dir.
             Physical path through `cd -P` and `pwd -P`. JSON-escaped.
             "" outside git or when cwd does not exist.
       kind  growth: the kind of work of a file edit, only for PostToolUse of
             Edit, Write, MultiEdit (tool_input.file_path) and NotebookEdit
             (tool_input.notebook_path), found in the first 4096 bytes; else
             "". The path is taken relative to the folder holding .git (a
             file outside it: its own name), then the first rule that fits:
               test    a folder test, tests, __tests__, spec, e2e; or a name
                       test_*, *_test.*, *.test.*, *.spec.*, *_spec.*, *Test.*
               doc     a name *.md *.markdown *.mdx *.rst *.adoc *.txt; or a
                       folder docs, doc, requirements
               ui      a name *.html *.htm *.css *.scss *.sass *.less *.jsx
                       *.tsx *.vue *.svelte; or a folder components, ui,
                       views, pages, widgets, screens
               script  a name *.sh *.bash *.zsh *.fish *.ps1 *.bat *.cmd *.mk,
                       Makefile, Dockerfile; or a folder bin, scripts, .github
               other   anything else
             Only the kind is written, never the path (privacy).
     desc and q: at most 200 bytes, always a valid JSON string.
     Nothing else from the payload is ever written: not tool_input,
     tool_response, prompt, message or last_assistant_message.
     No hook_event_name in the input: write nothing.
  3. Bash builtins only. It works with PATH pointing at an empty folder, so it
     never starts python, jq, curl, date, cat or git. Works on bash 3.2
     (macOS /bin/bash): no ${x,,}, no declare -A, no mapfile.
  4. It reads at most the first 4096 bytes of stdin, except for Agent, Task
     and AskUserQuestion, so a 1 MB Write payload costs no more than a small one.
  5. Never prints to stdout or stderr. Always exits 0, even on garbage.
  6. stdin may be a socket, not a pipe: Node and Bun (which run Claude Code)
     hand a child its stdin as a socketpair, and /dev/stdin cannot be opened
     on a socket. Everything above still holds then.

  hooks/hooks.json runs it through CITY_COMMAND (below). With the city off that
  command is one `test -f` inside the shell Claude Code already starts: the
  hook script itself is not even started.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "bin", "agent-city-hook.sh")
BASH = shutil.which("bash")
KEYS = {"ev", "sid", "aid", "at", "tool", "nt", "proj", "role", "desc", "sub", "q", "klen", "repo", "kind"}

CITY_COMMAND = ('[ -f "${AGENT_CITY_DIR:-$HOME/.cache/agent-city}/on" ] && '
                '"${CLAUDE_PLUGIN_ROOT}/bin/agent-city-hook.sh"; exit 0')


def payload(event, agent=None, ascii_only=False, **rest):
    """Build a hook payload in the key order Claude Code uses.

    Common fields first (agent_id and agent_type only inside a subagent), then
    hook_event_name, then the event's own fields in the order given.
    """
    data = {
        "session_id": "sess-1",
        "transcript_path": "/home/u/.claude/projects/shop/sess-1.jsonl",
        "cwd": "/work/shop-app",
        "permission_mode": "auto",
    }
    if agent:
        data["agent_id"] = agent[0]
        data["agent_type"] = agent[1]
    data["hook_event_name"] = event
    data.update(rest)
    return json.dumps(data, ensure_ascii=ascii_only).encode("utf-8")


class HookCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_hook_")
        self.city = os.path.join(self.base, "city")
        os.mkdir(self.city)
        self.empty = os.path.join(self.base, "emptybin")
        os.mkdir(self.empty)
        self.events = os.path.join(self.city, "events.jsonl")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def switch_on(self, pid=None):
        with open(os.path.join(self.city, "on"), "w") as fh:
            fh.write("%s 4777\n" % (os.getpid() if pid is None else pid))

    def run_hook(self, stdin, env=None):
        full = {"AGENT_CITY_DIR": self.city, "PATH": self.empty, "HOME": self.base}
        full.update(env or {})
        return subprocess.run([BASH, HOOK], input=stdin, env=full,
                              capture_output=True, timeout=20)

    def lines(self):
        if not os.path.exists(self.events):
            return []
        with open(self.events, "rb") as fh:
            raw = fh.read()
        return [json.loads(l.decode("utf-8", "replace"))
                for l in raw.split(b"\n") if l.strip()]

    def one(self, stdin, env=None):
        result = self.run_hook(stdin, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.lines()
        self.assertEqual(len(rows), 1, rows)
        return rows[0]

    def assert_silent(self, result):
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")


class TestOff(HookCase):
    def test_no_switch_writes_nothing(self):
        result = self.run_hook(payload("PostToolUse", ("a1", "worker"), tool_name="Edit"))
        self.assert_silent(result)
        self.assertFalse(os.path.exists(self.events))

    def test_dead_pid_writes_nothing(self):
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        self.switch_on(proc.pid)
        result = self.run_hook(payload("PostToolUse", ("a1", "worker"), tool_name="Edit"))
        self.assert_silent(result)
        self.assertFalse(os.path.exists(self.events))

    def test_pid_that_is_not_a_number_writes_nothing(self):
        self.switch_on("abc")
        result = self.run_hook(payload("PostToolUse", ("a1", "worker"), tool_name="Edit"))
        self.assert_silent(result)
        self.assertFalse(os.path.exists(self.events))

    def test_empty_switch_file_writes_nothing(self):
        open(os.path.join(self.city, "on"), "w").close()
        result = self.run_hook(payload("Stop"))
        self.assert_silent(result)
        self.assertFalse(os.path.exists(self.events))


class TestOn(HookCase):
    def setUp(self):
        super().setUp()
        self.switch_on()

    def test_post_tool_use_inside_a_subagent(self):
        row = self.one(payload(
            "PostToolUse", ("a1", "worker"), tool_name="Edit",
            tool_input={"file_path": "/x", "old_string": "SECRET_TOKEN_123", "new_string": "y"},
            tool_response={"filePath": "/x", "text": "SECRET_TOKEN_123"},
            tool_use_id="toolu_1"))
        self.assertEqual(row["ev"], "PostToolUse")
        self.assertEqual(row["sid"], "sess-1")
        self.assertEqual(row["aid"], "a1")
        self.assertEqual(row["at"], "worker")
        self.assertEqual(row["tool"], "Edit")
        self.assertEqual(row["proj"], "shop-app")

    def test_exactly_the_fourteen_keys_all_strings(self):
        row = self.one(payload("PostToolUse", ("a1", "worker"), tool_name="Read",
                               tool_input={"file_path": "/x"}))
        self.assertEqual(set(row), KEYS)
        for key, value in row.items():
            with self.subTest(key=key):
                self.assertIsInstance(value, str)

    def test_nothing_from_tool_input_or_output_reaches_the_file(self):
        self.run_hook(payload(
            "PostToolUse", ("a1", "worker"), tool_name="Bash",
            tool_input={"command": "deploy --token SECRET_TOKEN_123", "description": "deploy"},
            tool_response={"stdout": "SECRET_TOKEN_123"}))
        with open(self.events, "rb") as fh:
            text = fh.read()
        self.assertNotIn(b"SECRET_TOKEN_123", text)
        self.assertNotIn(b"deploy", text)

    def test_klen_is_the_escaped_length_of_the_command(self):
        cmd = 'deploy --token "SECRET_TOKEN_123" é'
        row = self.one(payload("PostToolUse", ("a1", "worker"), tool_name="Bash",
                               tool_input={"command": cmd, "description": "deploy"},
                               tool_response={"stdout": "x"}))
        escaped = json.dumps(cmd, ensure_ascii=False)[1:-1].encode("utf-8")
        self.assertEqual(row["klen"], str(len(escaped)))

    def test_klen_for_files_and_urls(self):
        for tool, key in (("Edit", "file_path"), ("Write", "file_path"), ("MultiEdit", "file_path"),
                          ("WebFetch", "url")):
            with self.subTest(tool=tool):
                open(self.events, "w").close()
                row = self.one(payload("PermissionRequest", tool_name=tool,
                                       tool_input={key: "/r/shop/a b.py"}))
                self.assertEqual(row["klen"], str(len("/r/shop/a b.py")))

    def test_klen_empty_for_other_tools(self):
        for tool in ("Read", "AskUserQuestion", "Agent", "mcp__x__y"):
            with self.subTest(tool=tool):
                open(self.events, "w").close()
                row = self.one(payload("PostToolUse", tool_name=tool,
                                       tool_input={"command": "x", "file_path": "/y", "questions": []}))
                self.assertEqual(row["klen"], "")

    def test_main_agent_has_empty_aid_and_at(self):
        row = self.one(payload("PostToolUse", tool_name="Edit", tool_input={"file_path": "/x"}))
        self.assertEqual(row["aid"], "")
        self.assertEqual(row["at"], "")

    def test_tool_input_keys_cannot_fake_the_agent(self):
        row = self.one(payload(
            "PostToolUse", tool_name="mcp__x__y",
            tool_input={"agent_id": "evil", "agent_type": "evil", "hook_event_name": "Stop"},
            tool_response={"agent_id": "evil2", "tool_name": "evil3"}))
        self.assertEqual(row["aid"], "")
        self.assertEqual(row["at"], "")
        self.assertEqual(row["ev"], "PostToolUse")
        self.assertEqual(row["tool"], "mcp__x__y")

    def test_agent_tool_gives_desc_and_sub(self):
        row = self.one(payload(
            "PreToolUse", tool_name="Agent",
            tool_input={"description": "设置页表单", "prompt": "long brief SECRET_PROMPT " * 50,
                        "subagent_type": "worker"}))
        self.assertEqual(row["desc"], "设置页表单")
        self.assertEqual(row["sub"], "worker")
        with open(self.events, "rb") as fh:
            self.assertNotIn(b"SECRET_PROMPT", fh.read())

    def test_agent_tool_with_ascii_escaped_json(self):
        row = self.one(payload(
            "PreToolUse", ascii_only=True, tool_name="Agent",
            tool_input={"description": "设置页表单", "prompt": "p", "subagent_type": "worker"}))
        self.assertEqual(row["desc"], "设置页表单")

    def test_subagent_type_far_after_a_long_prompt(self):
        row = self.one(payload(
            "PreToolUse", tool_name="Agent",
            tool_input={"description": "big brief", "prompt": "x" * 20000,
                        "subagent_type": "merge-deputy"}))
        self.assertEqual(row["sub"], "merge-deputy")

    def test_task_tool_is_read_the_same_way(self):
        row = self.one(payload(
            "PreToolUse", tool_name="Task",
            tool_input={"description": "look around", "prompt": "p", "subagent_type": "Explore"}))
        self.assertEqual(row["desc"], "look around")
        self.assertEqual(row["sub"], "Explore")

    def test_desc_only_for_agent_tools(self):
        row = self.one(payload(
            "PostToolUse", ("a1", "worker"), tool_name="Bash",
            tool_input={"command": "ls", "description": "list files"}))
        self.assertEqual(row["desc"], "")
        self.assertEqual(row["sub"], "")

    def test_ask_user_question_gives_q(self):
        row = self.one(payload(
            "PreToolUse", ("a1", "worker"), tool_name="AskUserQuestion",
            tool_input={"questions": [{"question": "API 路径用哪个？", "header": "API",
                                       "options": [{"label": "A", "description": "a"}],
                                       "multiSelect": False}]}))
        self.assertEqual(row["q"], "API 路径用哪个？")

    def test_q_only_for_ask_user_question(self):
        row = self.one(payload(
            "PostToolUse", ("a1", "worker"), tool_name="mcp__x__y",
            tool_input={"question": "not this"}))
        self.assertEqual(row["q"], "")

    def test_notification_type_but_not_the_message(self):
        row = self.one(payload("Notification", message="Claude needs your permission SECRET_MSG",
                               title="Claude Code", notification_type="permission_prompt"))
        self.assertEqual(row["nt"], "permission_prompt")
        with open(self.events, "rb") as fh:
            self.assertNotIn(b"SECRET_MSG", fh.read())

    def test_user_prompt_is_never_written(self):
        row = self.one(payload("UserPromptSubmit", prompt="my password is SECRET_PW"))
        self.assertEqual(row["ev"], "UserPromptSubmit")
        with open(self.events, "rb") as fh:
            self.assertNotIn(b"SECRET_PW", fh.read())

    def test_subagent_start_and_stop(self):
        self.run_hook(payload("SubagentStart", ("a1", "worker")))
        self.run_hook(payload("SubagentStop", ("a1", "worker"), stop_hook_active=False,
                              agent_transcript_path="/t", last_assistant_message="SECRET_LAST"))
        rows = self.lines()
        self.assertEqual([r["ev"] for r in rows], ["SubagentStart", "SubagentStop"])
        self.assertEqual([r["aid"] for r in rows], ["a1", "a1"])
        with open(self.events, "rb") as fh:
            self.assertNotIn(b"SECRET_LAST", fh.read())

    def test_role_comes_from_agent_role(self):
        row = self.one(payload("Stop"), env={"AGENT_ROLE": "task-manager"})
        self.assertEqual(row["role"], "task-manager")

    def test_role_is_cleaned(self):
        row = self.one(payload("Stop"), env={"AGENT_ROLE": 'x"; rm -rf /'})
        self.assertEqual(row["role"], "xrm-rf")

    def test_two_calls_append_two_lines(self):
        self.run_hook(payload("Stop"))
        self.run_hook(payload("Stop"))
        self.assertEqual(len(self.lines()), 2)

    def test_no_event_name_writes_nothing(self):
        result = self.run_hook(b'{"session_id":"s"}')
        self.assert_silent(result)
        self.assertEqual(self.lines(), [])

    def test_garbage_is_silent(self):
        for stdin in (b"", b"not json {{{", b"\x00\xff\xfe", b'{"hook_event_name":'):
            with self.subTest(stdin=stdin):
                self.assert_silent(self.run_hook(stdin))

    def test_on_output_is_silent_too(self):
        self.assert_silent(self.run_hook(payload("PostToolUse", ("a1", "worker"), tool_name="Edit")))


class TestLongText(HookCase):
    def setUp(self):
        super().setUp()
        self.switch_on()

    def check(self, desc, ascii_only=False):
        row = self.one(payload("PreToolUse", ascii_only=ascii_only, tool_name="Agent",
                               tool_input={"description": desc, "prompt": "p",
                                           "subagent_type": "worker"}))
        self.assertLessEqual(len(row["desc"].encode("utf-8")), 200 * 3)
        with open(self.events, "rb") as fh:
            raw = fh.read().split(b"\n")[0]
        match = raw.split(b'"desc":"', 1)[1]
        self.assertLessEqual(len(match.split(b'","sub"', 1)[0]), 200)
        return row

    def test_long_plain_text(self):
        row = self.check("a" * 1000)
        self.assertTrue(row["desc"].startswith("aaaa"))

    def test_long_multibyte_text(self):
        self.check("é" * 400)

    def test_long_escaped_quotes(self):
        self.check('"' * 400)

    def test_long_backslashes(self):
        self.check("\\" * 400)

    def test_long_unicode_escapes(self):
        self.check("设" * 200, ascii_only=True)

    def test_newlines_and_tabs(self):
        row = self.check("line1\nline2\tend" * 40)
        self.assertTrue(row["desc"].startswith("line1\nline2"))


class TestSocketStdin(HookCase):
    """Claude Code runs on Node/Bun, which give a hook a socketpair as stdin."""

    def run_socket(self, data):
        import socket
        ours, theirs = socket.socketpair()
        env = {"AGENT_CITY_DIR": self.city, "PATH": self.empty, "HOME": self.base}
        proc = subprocess.Popen([BASH, HOOK], stdin=theirs, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env)
        theirs.close()
        try:
            ours.sendall(data)
        except OSError:
            pass
        try:
            ours.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        out, err = proc.communicate(timeout=20)
        ours.close()
        return proc.returncode, out, err

    def setUp(self):
        super().setUp()
        self.switch_on()

    def test_agent_tool_with_a_long_prompt(self):
        code, out, err = self.run_socket(payload(
            "PreToolUse", tool_name="Agent",
            tool_input={"description": "设置页表单", "prompt": "x" * 20000, "subagent_type": "worker"}))
        self.assertEqual((code, out, err), (0, b"", b""))
        row = self.lines()[0]
        self.assertEqual(row["desc"], "设置页表单")
        self.assertEqual(row["sub"], "worker")

    def test_ask_user_question(self):
        code, out, err = self.run_socket(payload(
            "PreToolUse", ("a1", "worker"), tool_name="AskUserQuestion",
            tool_input={"questions": [{"question": "用哪个？", "header": "h", "options": []}]}))
        self.assertEqual((code, out, err), (0, b"", b""))
        self.assertEqual(self.lines()[0]["q"], "用哪个？")

    def test_plain_event(self):
        code, out, err = self.run_socket(payload("PostToolUse", ("a1", "worker"), tool_name="Edit",
                                                 tool_input={"content": "y" * 100000}))
        self.assertEqual((code, out, err), (0, b"", b""))
        self.assertEqual(self.lines()[0]["tool"], "Edit")


def git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    subprocess.run(["git", "-C", cwd] + list(args), check=True, capture_output=True, env=env,
                   stdin=subprocess.DEVNULL)


KIND_TABLE = [
    ("tests/test_page.py", "test"), ("src/__tests__/a.js", "test"), ("spec/models/user_spec.rb", "test"),
    ("pkg/foo_test.go", "test"), ("web/app.test.tsx", "test"), ("web/app.spec.ts", "test"),
    ("test_util.py", "test"), ("test/helper.js", "test"), ("e2e/login.js", "test"), ("src/FooTest.java", "test"),
    ("tests/fixtures/page.html", "test"),
    ("README.md", "doc"), ("docs/guide.html", "doc"), ("requirements/city.md", "doc"), ("notes.txt", "doc"),
    ("CHANGELOG.rst", "doc"), ("doc/api.adoc", "doc"), ("site/intro.mdx", "doc"),
    ("bin/agent-city.html", "ui"), ("src/components/Button.js", "ui"), ("styles/site.css", "ui"),
    ("app/views/home.erb", "ui"), ("lib/ui/theme.dart", "ui"), ("App.vue", "ui"), ("Page.svelte", "ui"),
    ("a.scss", "ui"), ("src/pages/index.tsx", "ui"), ("lib/screens/login.dart", "ui"),
    ("bin/agent-city.sh", "script"), ("scripts/deploy.py", "script"), ("Makefile", "script"),
    ("Dockerfile", "script"), ("tools/x.bash", "script"), (".github/workflows/ci.yml", "script"),
    ("bin/agent_city.py", "script"), ("build.ps1", "script"),
    ("src/app.py", "other"), ("lib/x.ts", "other"), ("agent.conf", "other"), ("package.json", "other"),
    ("db/schema.sql", "other"), ("main.go", "other"), ("latest.py", "other"), ("contest.py", "other"),
]


class TestRepoAndKind(HookCase):
    """Growth: which territory (repo) and which building (kind), never the path."""

    def setUp(self):
        super().setUp()
        self.switch_on()
        self.shop = os.path.join(self.base, "code", "shop")
        os.makedirs(os.path.join(self.shop, "src", "deep", "er"))
        git(self.shop, "init", "-q", "-b", "main")
        with open(os.path.join(self.shop, "a.py"), "w") as fh:
            fh.write("x\n")
        git(self.shop, "add", "a.py")
        git(self.shop, "commit", "-q", "-m", "init")
        self.common = os.path.realpath(os.path.join(self.shop, ".git"))
        self.wt = os.path.join(self.base, "code", "shop-wt")
        git(self.shop, "worktree", "add", "-q", "-b", "side", self.wt)

    def at(self, cwd, event="UserPromptSubmit", **rest):
        open(self.events, "w").close()
        return self.one(payload(event, cwd=cwd, **rest))

    def edit(self, rel, tool="Edit", cwd=None, root=None):
        key = "notebook_path" if tool == "NotebookEdit" else "file_path"
        path = rel if rel.startswith("/") else os.path.join(root or self.shop, rel)
        self.run_hook(payload("PostToolUse", ("a1", "worker"), cwd=cwd or self.shop, tool_name=tool,
                              tool_input={key: path, "old_string": "a", "new_string": "b"},
                              tool_response={"filePath": path}))
        return self.lines()[-1]

    def test_repo_is_the_git_common_dir(self):
        self.assertEqual(self.at(self.shop)["repo"], self.common)

    def test_a_subfolder_walks_up(self):
        self.assertEqual(self.at(os.path.join(self.shop, "src", "deep", "er"))["repo"], self.common)

    def test_a_worktree_lands_on_its_main_repo(self):
        self.assertEqual(self.at(self.wt)["repo"], self.common)
        self.assertEqual(self.at(self.wt)["proj"], "shop-wt")

    def test_a_symlinked_cwd_gives_the_physical_path(self):
        link = os.path.join(self.base, "link")
        os.symlink(self.shop, link)
        self.assertEqual(self.at(link)["repo"], self.common)

    def test_outside_git_or_missing_folder_is_empty(self):
        plain = os.path.join(self.base, "plain")
        os.makedirs(plain)
        self.assertEqual(self.at(plain)["repo"], "")
        self.assertEqual(self.at(os.path.join(self.base, "gone", "x"))["repo"], "")

    def test_odd_folder_names_stay_valid_json(self):
        odd = os.path.join(self.base, 'we"ird \\ name')
        os.makedirs(odd)
        git(odd, "init", "-q")
        self.assertEqual(self.at(odd)["repo"], os.path.realpath(os.path.join(odd, ".git")))

    def test_kind_of_every_file(self):
        for rel, kind in KIND_TABLE:
            with self.subTest(path=rel):
                self.assertEqual(self.edit(rel)["kind"], kind)

    def test_every_edit_tool(self):
        for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            with self.subTest(tool=tool):
                self.assertEqual(self.edit("tests/test_x.py", tool=tool)["kind"], "test")

    def test_the_path_inside_the_repo_decides(self):
        inner = os.path.join(self.base, "tests", "proj")
        os.makedirs(os.path.join(inner, "src"))
        git(inner, "init", "-q")
        self.assertEqual(self.edit("src/a.py", cwd=inner, root=inner)["kind"], "other",
                         "a repo that lives under a folder named tests is not all tests")

    def test_a_file_outside_the_repo_goes_by_its_name(self):
        self.assertEqual(self.edit(os.path.join(self.base, "elsewhere", "notes.md"))["kind"], "doc")
        self.assertEqual(self.edit(os.path.join(self.base, "tests", "x.py"))["kind"], "other")

    def test_worktree_edits_classify_inside_the_worktree(self):
        self.assertEqual(self.edit("tests/test_a.py", cwd=self.wt, root=self.wt)["kind"], "test")
        self.assertEqual(self.edit("ui/a.js", cwd=self.wt, root=self.wt)["kind"], "ui")

    def test_kind_only_for_a_finished_file_edit(self):
        cases = [("PostToolUse", "Bash", {"command": "vi tests/test_a.py"}),
                 ("PostToolUse", "Read", {"file_path": os.path.join(self.shop, "tests/test_a.py")}),
                 ("PermissionRequest", "Edit", {"file_path": os.path.join(self.shop, "tests/test_a.py")}),
                 ("PostToolUse", "Edit", {"old_string": "no path here"})]
        for ev, tool, ti in cases:
            with self.subTest(ev=ev, tool=tool):
                self.run_hook(payload(ev, ("a1", "worker"), cwd=self.shop, tool_name=tool, tool_input=ti))
                self.assertEqual(self.lines()[-1]["kind"], "")

    def test_the_path_is_never_written(self):
        marker = "zz_private_marker_9431"
        for rel in ("%s/tests/test_q.py" % marker, "src/%s.py" % marker, "docs/%s.md" % marker):
            self.edit(rel)
        with open(self.events, "rb") as fh:
            raw = fh.read()
        self.assertNotIn(marker.encode(), raw)
        self.assertEqual([r["kind"] for r in self.lines()], ["test", "other", "doc"])

    def test_still_cheap_deep_in_a_repo(self):
        deep = os.path.join(self.shop, *["d%d" % i for i in range(12)])
        os.makedirs(deep)
        stdin = payload("PostToolUse", ("a1", "worker"), cwd=deep, tool_name="Edit",
                        tool_input={"file_path": os.path.join(deep, "x.py")})
        start = time.monotonic()
        for _ in range(20):
            self.assert_silent(self.run_hook(stdin))
        took = time.monotonic() - start
        self.assertLess(took, 3.0, "20 runs took %.2fs" % took)
        self.assertEqual(self.lines()[-1]["repo"], self.common)


class TestCost(HookCase):
    def test_builtins_only(self):
        self.switch_on()
        result = self.run_hook(payload("PostToolUse", ("a1", "worker"), tool_name="Edit"),
                               env={"PATH": "/nonexistent-folder"})
        self.assert_silent(result)
        self.assertEqual(len(self.lines()), 1)

    def test_a_1mb_payload_is_cheap(self):
        self.switch_on()
        big = payload("PostToolUse", ("a1", "worker"), tool_name="Write",
                      tool_input={"file_path": "/x", "content": "y" * 1_000_000},
                      tool_response={"type": "create"})
        start = time.monotonic()
        result = self.run_hook(big)
        took = time.monotonic() - start
        self.assert_silent(result)
        self.assertEqual(self.lines()[0]["tool"], "Write")
        self.assertLess(took, 1.0, "a 1 MB payload took %.2fs" % took)

    def test_the_off_path_through_the_hooks_json_command_is_fast(self):
        env = dict(os.environ, AGENT_CITY_DIR=self.city, CLAUDE_PLUGIN_ROOT=ROOT, HOME=self.base)
        stdin = payload("PostToolUse", ("a1", "worker"), tool_name="Edit")
        start = time.monotonic()
        for _ in range(30):
            result = subprocess.run(["sh", "-c", CITY_COMMAND], input=stdin, env=env,
                                    capture_output=True, timeout=20)
            self.assert_silent(result)
        took = time.monotonic() - start
        self.assertFalse(os.path.exists(self.events))
        self.assertLess(took, 3.0, "30 off runs took %.2fs" % took)

    def test_the_hooks_json_command_runs_the_hook_when_on(self):
        self.switch_on()
        env = dict(os.environ, AGENT_CITY_DIR=self.city, CLAUDE_PLUGIN_ROOT=ROOT, HOME=self.base)
        result = subprocess.run(["sh", "-c", CITY_COMMAND],
                                input=payload("SubagentStart", ("a1", "worker")),
                                env=env, capture_output=True, timeout=20)
        self.assert_silent(result)
        self.assertEqual(self.lines()[0]["ev"], "SubagentStart")

    def test_default_city_dir_is_under_home(self):
        home = os.path.join(self.base, "home")
        city = os.path.join(home, ".cache", "agent-city")
        os.makedirs(city)
        with open(os.path.join(city, "on"), "w") as fh:
            fh.write("%d 4777\n" % os.getpid())
        result = subprocess.run([BASH, HOOK], input=payload("Stop"),
                                env={"PATH": self.empty, "HOME": home},
                                capture_output=True, timeout=20)
        self.assert_silent(result)
        self.assertTrue(os.path.exists(os.path.join(city, "events.jsonl")))


if __name__ == "__main__":
    unittest.main()
