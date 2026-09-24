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
     desc and q: at most 200 bytes, always a valid JSON string.
     Nothing else from the payload is ever written: not tool_input,
     tool_response, prompt, message or last_assistant_message.
     No hook_event_name in the input: write nothing.
  3. Bash builtins only. It works with PATH pointing at an empty folder, so it
     never starts python, jq, curl, date or cat.
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
KEYS = {"ev", "sid", "aid", "at", "tool", "nt", "proj", "role", "desc", "sub", "q", "klen"}

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

    def test_exactly_the_twelve_keys_all_strings(self):
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
        ours.shutdown(socket.SHUT_WR)
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
