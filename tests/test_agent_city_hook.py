"""Failing tests for bin/agent-city-hook.sh, the hook that feeds the agent city.

CONTRACT

  Where
    city dir   $AGENT_CITY_DIR, default $HOME/.cache/agent-city
    switch     <dir>/on, one line "<pid> <port>", written by the city server
    output     <dir>/events.jsonl, one JSON object per line, appended

  1. Off costs nothing. No <dir>/on, or its pid is not a number, or that
     process is dead: write nothing, print nothing, exit 0.
  2. On: read the hook JSON from stdin and append ONE line with exactly these
     keys (16), in this order, all strings, "" when absent:
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
       (no "kind": idea-city C4 -- the server decides the building from "file"
        with its own rules, tests/test_agent_city_idea_server.py)
       ask   city-people (tests/test_agent_city_chain.py): "q" for a
             SubagentStop whose last_assistant_message starts with
             "QUESTION:" and a PostToolUse of SendMessage whose
             tool_input.message starts with "QUESTION:"; else "". Only the
             flag, never the text or the recipient.
       wt    city-worktrees (tests/test_agent_city_worktrees.py): the physical
             path of the folder holding .git when that .git is a file (a
             linked worktree); else "".
       file  city-quality (tests/test_agent_city_quality.py): the edited
             file's path relative to the folder holding .git; else "".
       tp    session-names N5 (tests/test_agent_city_session_names.py): the
             payload's transcript_path, JSON-escaped as given; "" when it is
             missing or longer than 1024 bytes. The server reads the
             session's real name from it; the relay never sends it.
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

from cityhelp import ROOT, HOOK, BASH, HookCase  # noqa: E402,F401  (test-slim: shared helpers)
KEYS = {"ev", "sid", "aid", "at", "tool", "nt", "proj", "role", "desc", "sub", "q", "klen", "repo", "to", "ask", "wt",
        "file", "tp", "pid"}   # city-talk: "to", the recipient of a SendMessage (tests/test_agent_city_talk.py)

CITY_COMMAND = ('[ -f "${AGENT_CITY_DIR:-$HOME/.cache/agent-city}/on" ] && '
                '"${CLAUDE_PLUGIN_ROOT}/bin/agent-city-hook.sh"; exit 0')


from cityhelp import payload  # noqa: E402,F401  (test-slim: shared helpers)
from cityhelp import make_repo  # noqa: E402


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

    def test_the_transcript_path(self):
        row = self.one(payload("PostToolUse", tool_name="Read", tool_input={"file_path": "/x"}))
        self.assertEqual(row["tp"], "/home/u/.claude/projects/shop/sess-1.jsonl")

    def test_a_too_long_transcript_path_is_dropped(self):
        stdin = payload("PostToolUse", tool_name="Read", tool_input={"file_path": "/x"})
        stdin = stdin.replace(b"/home/u/.claude/projects/shop/sess-1.jsonl",
                              b"/home/u/" + b"d" * 1100 + b"/sess-1.jsonl")
        self.assertEqual(self.one(stdin)["tp"], "")

    def test_exactly_the_keys_all_strings(self):
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


class TestRepoAndKind(HookCase):
    """Growth: which territory (repo), never the path; the server picks the building (idea-city C4)."""

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

    def test_the_path_is_written_only_as_the_repo_relative_file_key(self):
        # city-quality (requirements/city.md, Quality): buildings remember their
        # files, so the repo-relative path goes in "file" -- never the absolute
        # path, and never in any other key. It stays on this computer.
        marker = "zz_private_marker_9431"
        rels = ("%s/tests/test_q.py" % marker, "src/%s.py" % marker, "docs/%s.md" % marker)
        for rel in rels:
            self.edit(rel)
        with open(self.events, "rb") as fh:
            raw = fh.read()
        self.assertNotIn(self.shop.encode(), raw.replace(self.common.encode(), b""))
        rows = self.lines()
        self.assertNotIn("kind", rows[0])
        self.assertEqual([r["file"] for r in rows], list(rels))
        for r in rows:
            self.assertFalse([k for k, v in r.items() if k != "file" and marker in v])

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


class TestHookAskFlag(unittest.TestCase):
    """The hook writes ask=q for a question passed up the chain, never its text."""

    def setUp(self):
        import cityhelp as th  # noqa: E402
        self.th = th
        self.case = th.HookCase("run_hook")
        self.case.setUp()
        self.case.switch_on()

    def tearDown(self):
        self.case.tearDown()

    def row(self, stdin):
        result = self.case.run_hook(stdin)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.case.lines()
        self.assertTrue(rows, "no line written")
        raw = open(self.case.events, "rb").read()
        return rows[-1], raw

    def stop(self, text):
        return self.th.payload("SubagentStop", agent=("w-1", "worker"), stop_hook_active=False,
                               agent_transcript_path="/home/u/t.jsonl", last_assistant_message=text,
                               background_tasks=[])

    def send(self, message, event="PostToolUse"):
        return self.th.payload(event, tool_name="SendMessage",
                               tool_input={"to": "auto-pipeline-88", "summary": "ask", "message": message},
                               tool_response={"success": True, "message": "queued"})

    def test_ask_key_is_last_and_a_string(self):
        # city-worktrees added "wt" after it, city-quality "file" after that,
        # session-names "tp" after that, city-roles "pid" last (tests/test_agent_city_worktrees.py,
        # tests/test_agent_city_quality.py, tests/test_agent_city_session_names.py,
        # tests/test_agent_city_roles.py)
        row, _ = self.row(self.stop("PASS\nall green"))
        self.assertEqual(list(row)[-5:], ["ask", "wt", "file", "tp", "pid"])
        self.assertEqual(row["ask"], "")

    def test_worker_question_sets_the_flag_not_the_text(self):
        row, raw = self.row(self.stop("QUESTION: which port, 4791 or 4777?\nWhat changed: nothing"))
        self.assertEqual(row["ask"], "q")
        self.assertNotIn(b"4791", raw)
        self.assertNotIn(b"which port", raw)

    def test_only_a_first_line_question_counts(self):
        for text in ("FAIL: tests\nQUESTION: x", "question: lower case", "PASS"):
            with self.subTest(text=text):
                row, _ = self.row(self.stop(text))
                self.assertEqual(row["ask"], "")

    def test_lead_question_to_the_governor(self):
        row, raw = self.row(self.send("QUESTION: port 4791 or 4777?\nDefault 4791 after 10 min."))
        self.assertEqual(row["ask"], "q")
        self.assertEqual(row["tool"], "SendMessage")
        self.assertNotIn(b"4791", raw)
        self.assertNotIn(b"auto-pipeline-88", raw)

    def test_other_messages_are_no_question(self):
        for msg in ("DONE PASS city-people", "HEARTBEAT city-people: step 4", "MOCK READY"):
            with self.subTest(msg=msg):
                row, _ = self.row(self.send(msg))
                self.assertEqual(row["ask"], "")

    def test_only_post_tool_use_counts(self):
        row, _ = self.row(self.send("QUESTION: x", event="PreToolUse"))
        self.assertEqual(row["ask"], "")

    def test_a_session_stop_is_never_a_chain_question(self):
        row, _ = self.row(self.th.payload("Stop", stop_hook_active=False, last_assistant_message="QUESTION: x"))
        self.assertEqual(row["ask"], "")

    def test_long_message_still_flagged(self):
        row, _ = self.row(self.send("QUESTION: " + "x" * 20000))
        self.assertEqual(row["ask"], "q")


HERE = os.path.dirname(os.path.abspath(__file__))


BIN = os.path.join(ROOT, "bin")


class TestHookHasNoPathRules(unittest.TestCase):
    def test_no_classify_path(self):
        with open(os.path.join(BIN, "agent-city-hook.sh"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("classify_path", text)
        self.assertNotIn('"kind":', text)


HOOK_quality = os.path.join(ROOT, "bin", "agent-city-hook.sh")


BASH_quality = shutil.which("bash") or "/bin/bash"


class TestHookFile(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_q_hook_")
        self.city = os.path.join(self.base, "city")
        os.mkdir(self.city)
        with open(os.path.join(self.city, "on"), "w") as fh:
            fh.write("%s 4777\n" % os.getpid())
        self.empty = os.path.join(self.base, "emptybin")
        os.mkdir(self.empty)
        self.root, self.wt = make_repo(self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def row(self, cwd, tool="Edit", path=None, event="PostToolUse", key="file_path"):
        data = {"session_id": "s1", "cwd": cwd, "hook_event_name": event, "tool_name": tool}
        if path is not None:
            data["tool_input"] = {key: path, "old_string": "a", "new_string": "b"}
        env = {"AGENT_CITY_DIR": self.city, "PATH": self.empty, "HOME": self.base}
        res = subprocess.run([BASH_quality, HOOK_quality], input=json.dumps(data).encode(), env=env,
                             capture_output=True, timeout=20)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(self.city, "events.jsonl"), encoding="utf-8") as fh:
            lines = [json.loads(x) for x in fh if x.strip()]
        os.remove(os.path.join(self.city, "events.jsonl"))
        return lines[-1]

    def test_edit_in_the_main_checkout(self):
        row = self.row(self.root, path=os.path.join(self.root, "src", "app.py"))
        self.assertEqual(row["file"], "src/app.py")
        self.assertNotIn("kind", row)  # idea-city C4: the server picks the building

    def test_edit_in_a_worktree_is_relative_to_the_worktree(self):
        row = self.row(self.wt, tool="Write", path=os.path.join(self.wt, "tests", "test_a.py"))
        self.assertEqual(row["file"], "tests/test_a.py")

    def test_notebook(self):
        row = self.row(self.root, tool="NotebookEdit", path=os.path.join(self.root, "nb", "a.ipynb"),
                       key="notebook_path")
        self.assertEqual(row["file"], "nb/a.ipynb")

    def test_outside_the_repo_is_empty(self):
        self.assertEqual(self.row(self.root, path="/etc/hosts")["file"], "")

    def test_pre_tool_use_and_other_tools_are_empty(self):
        self.assertEqual(self.row(self.root, event="PreToolUse",
                                  path=os.path.join(self.root, "a.py"))["file"], "")
        self.assertEqual(self.row(self.root, tool="Read", path=os.path.join(self.root, "a.py"))["file"], "")

    def test_a_long_path_is_empty(self):
        long = os.path.join(self.root, "d" * 320 + ".py")
        self.assertEqual(self.row(self.root, path=long)["file"], "")

    def test_quotes_stay_valid_json(self):
        row = self.row(self.root, path=os.path.join(self.root, 'we"ird.py'))
        self.assertEqual(row["file"], 'we"ird.py')

    def test_file_is_the_third_last_key(self):
        # idea-city C4: the hook line has no "kind" any more; session-names
        # added "tp" after "file" (tests/test_agent_city_session_names.py),
        # city-roles "pid" after "tp" (tests/test_agent_city_roles.py),
        # city-talk "to" right before "ask" (tests/test_agent_city_talk.py)
        row = self.row(self.root, path=os.path.join(self.root, "a.py"))
        self.assertEqual(len(row), 19)
        self.assertEqual(list(row)[-5:], ["ask", "wt", "file", "tp", "pid"])


HOOK_roles = os.path.join(ROOT, "bin", "agent-city-hook.sh")


BASH_roles = shutil.which("bash") or "/bin/bash"   # PATH is empty inside the hook, as in a real hook run


class TestHookPid(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_roles_hook_")
        self.city = os.path.join(self.base, "city")
        os.mkdir(self.city)
        self.empty = os.path.join(self.base, "emptybin")
        os.mkdir(self.empty)
        with open(os.path.join(self.city, "on"), "w") as fh:
            fh.write("%d 4777\n" % os.getpid())

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def row(self, env):
        full = {"AGENT_CITY_DIR": self.city, "PATH": self.empty, "HOME": self.base}
        full.update(env)
        stdin = json.dumps({"session_id": "s1", "transcript_path": "/t.jsonl", "cwd": self.base,
                            "hook_event_name": "PostToolUse", "tool_name": "Read",
                            "tool_input": {"file_path": "/x"}}).encode("utf-8")
        subprocess.run([BASH_roles, HOOK_roles], input=stdin, env=full, capture_output=True, timeout=10)
        with open(os.path.join(self.city, "events.jsonl")) as fh:
            rows = [json.loads(l, object_pairs_hook=lambda kv: kv) for l in fh if l.strip()]
        os.remove(os.path.join(self.city, "events.jsonl"))
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_pid_is_the_last_key(self):
        row = self.row({"CLAUDE_PID": "4242"})
        self.assertEqual(row[-1], ("pid", "4242"))
        self.assertEqual([k for k, _ in row][-5:], ["ask", "wt", "file", "tp", "pid"])

    def test_no_or_bad_pid_is_empty(self):
        for env in ({}, {"CLAUDE_PID": ""}, {"CLAUDE_PID": "12a"}, {"CLAUDE_PID": "1 2"},
                    {"CLAUDE_PID": '1"}'}):
            with self.subTest(env=env):
                self.assertEqual(dict(self.row(env))["pid"], "")


class TestHookSendsTheRecipientT3(unittest.TestCase):

    def setUp(self):
        import cityhelp as th  # noqa: E402
        self.th = th
        self.case = th.HookCase("run_hook")
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.case.switch_on()

    def row(self, stdin):
        result = self.case.run_hook(stdin)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.case.lines()
        self.assertTrue(rows, "no line written")
        with open(self.case.events, "rb") as fh:
            return rows[-1], fh.read()

    def send(self, to, message="DONE PASS city-talk\nResult: 12 tests", event="PostToolUse"):
        return self.th.payload(event, tool_name="SendMessage",
                               tool_input={"to": to, "summary": "report", "message": message},
                               tool_response={"success": True, "message": "queued"})

    def test_the_recipient_is_on_the_line(self):
        row, raw = self.row(self.send("city-talk Task Manager"))
        self.assertEqual(row["to"], "city-talk Task Manager")
        self.assertEqual(row["tool"], "SendMessage")
        self.assertNotIn(b"DONE PASS", raw, "never the message")
        self.assertNotIn(b"12 tests", raw)
        self.assertNotIn(b"report", raw, "never the summary")

    def test_the_key_sits_right_before_ask(self):
        row, _ = self.row(self.send("app Manager"))
        self.assertEqual(list(row)[-6:], ["to", "ask", "wt", "file", "tp", "pid"])
        for value in row.values():
            self.assertIsInstance(value, str)

    def test_a_question_carries_no_recipient(self):
        row, raw = self.row(self.send("auto-pipeline-88", "QUESTION: port 4791 or 4777?"))
        self.assertEqual((row["ask"], row["to"]), ("q", ""))
        self.assertNotIn(b"auto-pipeline-88", raw)

    def test_a_long_name_is_cut_to_80(self):
        row, _ = self.row(self.send("n" * 300))
        self.assertEqual(row["to"], "n" * 80)

    def test_a_name_with_quotes_stays_valid_json(self):
        row, _ = self.row(self.send('say "hi" \\ now'))
        self.assertEqual(row["to"], 'say "hi" \\ now')

    def test_a_chinese_name(self):
        row, _ = self.row(self.send("城市 任务经理"))
        self.assertEqual(row["to"], "城市 任务经理")

    def test_only_post_tool_use_send_message(self):
        row, _ = self.row(self.send("city-talk Task Manager", event="PreToolUse"))
        self.assertEqual(row["to"], "")
        row, _ = self.row(self.th.payload("PostToolUse", tool_name="Bash", tool_input={"command": "ls", "to": "x"},
                                          tool_response={"stdout": ""}))
        self.assertEqual(row["to"], "")

    def test_a_message_that_names_a_recipient_inside_its_text_is_not_read(self):
        row, _ = self.row(self.th.payload("PostToolUse", tool_name="SendMessage",
                                          tool_input={"message": 'see "to": "evil"', "summary": "x", "to": "app Helper"},
                                          tool_response={"success": True}))
        self.assertEqual(row["to"], "app Helper")


HOOK_worktrees = os.path.join(ROOT, "bin", "agent-city-hook.sh")


BASH_worktrees = shutil.which("bash") or "/bin/bash"


class TestHookWt(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_wt_hook_")
        self.city = os.path.join(self.base, "city")
        os.mkdir(self.city)
        with open(os.path.join(self.city, "on"), "w") as fh:
            fh.write("%s 4777\n" % os.getpid())
        self.empty = os.path.join(self.base, "emptybin")
        os.mkdir(self.empty)
        self.root, self.wt = make_repo(self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def row(self, cwd):
        data = json.dumps({"session_id": "s1", "cwd": cwd, "hook_event_name": "PostToolUse",
                           "tool_name": "Read", "tool_input": {"file_path": "/x"}}).encode()
        env = {"AGENT_CITY_DIR": self.city, "PATH": self.empty, "HOME": self.base}
        res = subprocess.run([BASH_worktrees, HOOK_worktrees], input=data, env=env, capture_output=True, timeout=20)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(self.city, "events.jsonl"), encoding="utf-8") as fh:
            lines = [json.loads(x, object_pairs_hook=lambda p: dict(p)) for x in fh if x.strip()]
        os.remove(os.path.join(self.city, "events.jsonl"))
        return lines[-1]

    def test_linked_worktree_gives_its_physical_folder(self):
        row = self.row(self.wt)
        self.assertEqual(row["wt"], self.wt)
        self.assertEqual(row["repo"], os.path.join(self.root, ".git"))

    def test_a_subfolder_of_the_worktree_gives_the_same(self):
        sub = os.path.join(self.wt, "deep", "er")
        os.makedirs(sub)
        self.assertEqual(self.row(sub)["wt"], self.wt)

    def test_a_symlinked_path_is_made_physical(self):
        link = os.path.join(self.base, "link-to-wt")
        os.symlink(self.wt, link)
        self.assertEqual(self.row(link)["wt"], self.wt)

    def test_main_checkout_gives_empty(self):
        self.assertEqual(self.row(self.root)["wt"], "")

    def test_outside_git_gives_empty(self):
        plain = os.path.join(self.base, "plain")
        os.mkdir(plain)
        self.assertEqual(self.row(plain)["wt"], "")

    def test_missing_cwd_gives_empty(self):
        self.assertEqual(self.row(os.path.join(self.base, "nope"))["wt"], "")

    def test_wt_is_the_key_right_after_ask(self):
        # city-quality appends "file" after it (tests/test_agent_city_quality.py); idea-city C4 dropped
        # "kind", so wt moved up one; city-talk put "to" before "ask", so both moved down one
        row = self.row(self.wt)
        keys = list(row)
        self.assertEqual(keys.index("wt"), 15)
        self.assertEqual(keys[13:16], ["to", "ask", "wt"])


if __name__ == "__main__":
    unittest.main()
