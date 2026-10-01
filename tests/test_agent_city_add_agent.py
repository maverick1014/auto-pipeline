"""Failing tests for city-add-agent (requirements/city.md, "Add agent"; owner,
2026-10-01): start a new agent session from the city page, no terminal needed.
This file: the server side of A3 (the open itself) and A7 (safety). No test
here ever opens a real session: the opener is always a fake.

CONTRACT, server (bin/agent_city.py, Python standard library only)

  ADD_WAIT_SEC = 60.0

  repo_folder(identity) -> the folder a new session starts in: the parent of
    a ".../.git" identity (the repo's main worktree), else the identity itself.

  agent_command(name, folder) -> str. The one fixed line a new terminal runs:
      claude --name <name> [--model <m> --effort <e>] [--permission-mode <p>]
    NAME goes in through shlex.quote. <m>:<e> = main_manager and <p> =
    permission_mode of <folder>/agent.conf (rule W10: a second session opens
    with the main manager's values). A missing file, a missing value or a
    value bin/agent_conf.py validate_value() refuses -> that part is left
    out; never raises. Nothing else ever goes into the line: no folder, no
    "cd", no AGENT_ROLE (task managers are never created here).

  open_session(folder, title, command, runtime=None) -> (ok, detail)
    THE opener, the only place that starts anything. Runs
      bash <runtime> launch <folder> <title> <command>
    as an argument list (never shell=True, never one joined string);
    runtime = bin/agent-runtime.sh next to this file when None. Exit 0 ->
    (True, ""); anything else (exit code, timeout, missing script) ->
    (False, <a short reason, the script's last stderr line when it has one>).
    Never raises.

  CityState(..., open_fn=None, kind_fn=None, resources_fn=None)
    open_fn(folder, title, command) -> (ok, detail); default open_session
      (CityState.open_fn). Tests pass a fake.
    kind_fn() -> "orca" | "plain" | "cloud" (bin/agent-runtime.sh kind).
    resources_fn(folder) -> {"ram", "cpu", "max", "ok"} (A5).
    These tests always answer "orca" and ok; A5 / A6 get their own tests.

  CityState.add_agent(terr, now, force=False) -> (code, body). NOW = monotonic.
    400 {"error": "bad"}       terr is not a str of 8 lowercase hex digits,
                               or force is not a bool
    404 {"error": "unknown"}   no territory with that id in the world
    409 {"error": "gone", "folder"}   its folder is not a directory any more
    409 {"error": "busy"}      an open for this repo is under way
    502 {"error": "failed", "detail"}   the opener said no, or raised; the
                               repo is free again at once
    200 {"state": "opening", "name", "role"}   the opener ran and said yes
    The folder is repo_folder(<the territory's identity in the world>): the
    server's own data, never the request's. The role is never asked: the
    repo has no live main manager (main_fn(identity) is None: its
    agent_main.lock holder is absent or dead) -> role "main", name
    "<repo> Manager"; else role "helper", name "<repo> Helper" (repo = the
    folder's own name). The new session's bin/agent-start.sh still decides
    its real role from the lock; nothing here copies that.
    open_fn(folder, name, agent_command(name, folder)) is called ONCE, and
    never while self.lock is held (opening a terminal takes seconds).
    One open at a time per repo: from the call that opens until (a) a session
    line (aid "") of that repo from a sid that had no line in it before the
    open, (b) ADD_WAIT_SEC later, or (c) the opener failing. Other repos are
    never held up.

  POST /api/agent/add  {"terr": <territory id>[, "force": true|false]}
    -> add_agent(terr, time.monotonic(), force). The gate of POST
    /api/chat/send: Host (127.0.0.1 / localhost: the local page only), an
    Origin header that is this server's own, the X-City-Token header; else
    403. A body that is not one JSON object, or that carries any key besides
    "terr" and "force" (a path, a name, a command) -> 400: the request names
    a territory id, nothing else. GET never opens anything.

  Nowhere in bin/agent_city.py: shell=True, os.system, os.popen.
"""

import http.client
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
SERVER = os.path.join(BIN, "agent_city.py")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from cityhelp import Mains, lock_file  # noqa: E402

CONF = "main_manager=opus-5.5:high\npermission_mode=auto\n"
FLAGS = ["--model", "opus-5.5", "--effort", "high", "--permission-mode", "auto"]


def line(ev, sid, repo, aid="", role=""):
    return {"ev": ev, "sid": sid, "aid": aid, "at": "", "tool": "Read", "nt": "", "proj": "shop", "role": role,
            "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}


class AddCase(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_add_"))
        self.calls = []                 # every call of the fake opener: (folder, title, command)
        self.answer = (True, "")        # what the fake opener says
        self.mains = Mains()            # identity -> sid of its live main manager
        self.now = 1000.0               # one clock for lines and clicks (monotonic seconds)
        self.shop = self.repo("shop")
        self.state = self.make()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def repo(self, name, conf=CONF):
        """A repo folder <base>/<name> with a .git dir (and an agent.conf) -> its identity."""
        folder = os.path.join(self.base, name)
        os.makedirs(os.path.join(folder, ".git"))
        if conf is not None:
            with open(os.path.join(folder, "agent.conf"), "w") as fh:
                fh.write(conf)
        return os.path.join(folder, ".git")

    def opener(self, folder, title, command):
        self.calls.append((folder, title, command))
        return self.answer

    def make(self, **kw):
        args = dict(decisions_path=os.path.join(self.base, "decisions.jsonl"), world_path=None, token="tok",
                    count_fn=lambda i: 0, balance_fn=lambda i, r: {"kinds": {}, "files": {}, "bad": []},
                    main_fn=self.mains, open_fn=self.opener, kind_fn=lambda: "orca",
                    resources_fn=lambda folder: {"ram": 10, "cpu": 10, "max": 80, "ok": True})
        args.update(kw)
        return ac.CityState(**args)

    def feed(self, *lines, at=None):
        for obj in lines:
            self.state.feed_line(obj, self.now if at is None else at)

    def known(self, identity, sid="old1"):
        """The city knows IDENTITY: one session of it has had a turn."""
        self.feed(line("UserPromptSubmit", sid, identity), line("Stop", sid, identity))
        return ac.territory_id(identity)

    def add(self, identity, at=None, **kw):
        return self.state.add_agent(ac.territory_id(identity), self.now if at is None else at, **kw)


# ---------------------------------------------------------------------------
# A3: one new session in that repo, its role decided by the lock
# ---------------------------------------------------------------------------

class TestOpen(AddCase):
    def test_no_live_main_manager_opens_the_main_manager(self):
        self.known(self.shop)
        code, body = self.add(self.shop)
        self.assertEqual(code, 200, body)
        self.assertEqual((body["state"], body["name"], body["role"]), ("opening", "shop Manager", "main"))
        self.assertEqual(len(self.calls), 1, "one click = one session")
        folder, title, command = self.calls[0]
        self.assertEqual(folder, os.path.join(self.base, "shop"), "the new terminal opens in the repo's own folder")
        self.assertEqual(title, "shop Manager")
        self.assertEqual(shlex.split(command), ["claude", "--name", "shop Manager"] + FLAGS)

    def test_live_main_manager_opens_a_helper(self):
        self.mains[self.shop] = "g1"
        self.known(self.shop, "g1")
        code, body = self.add(self.shop)
        self.assertEqual(code, 200, body)
        self.assertEqual((body["state"], body["name"], body["role"]), ("opening", "shop Helper", "helper"))
        folder, title, command = self.calls[0]
        self.assertEqual(title, "shop Helper")
        self.assertEqual(shlex.split(command), ["claude", "--name", "shop Helper"] + FLAGS,
                         "a helper opens with the main manager's model, effort and permission mode (W10)")

    def test_the_role_follows_the_real_lock_file(self):
        """Default main_fn: <repo>/.git/agent_main.lock, its holder alive or not."""
        state = self.make(main_fn=None, start_repo=self.shop)
        tid = ac.territory_id(self.shop)
        lock_file(self.shop, "g1")                       # held by this test process: alive
        self.assertEqual(state.add_agent(tid, self.now)[1].get("role"), "helper")
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        gone.wait()
        lock_file(self.shop, "g1", pid=gone.pid)         # the holder is dead
        code, body = state.add_agent(tid, self.now + ac.ADD_WAIT_SEC + 1)
        self.assertEqual((code, body.get("role"), body.get("name")), (200, "main", "shop Manager"))

    def test_a_repo_with_nobody_online_opens_too(self):
        """A1: a territory the city knows, no session in it at all."""
        state = self.make(start_repo=self.shop)
        code, body = state.add_agent(ac.territory_id(self.shop), self.now)
        self.assertEqual((code, body.get("name")), (200, "shop Manager"))
        self.assertEqual(len(self.calls), 1)

    def test_never_a_task_manager(self):
        self.mains[self.shop] = "g1"
        self.known(self.shop, "g1")
        self.add(self.shop)
        folder, title, command = self.calls[0]
        self.assertNotIn("AGENT_ROLE", command, "main managers dispatch task managers; this button never does")
        self.assertTrue(command.startswith("claude "), command)

    def test_the_values_are_that_repos_own(self):
        bar = self.repo("bar", "main_manager=sonnet-5:medium\npermission_mode=acceptEdits\n")
        self.known(self.shop)
        self.known(bar, "old2")
        self.add(self.shop)
        self.add(bar)
        self.assertEqual([c[0] for c in self.calls], [os.path.join(self.base, "shop"), os.path.join(self.base, "bar")])
        self.assertEqual(shlex.split(self.calls[1][2]),
                         ["claude", "--name", "bar Manager", "--model", "sonnet-5", "--effort", "medium",
                          "--permission-mode", "acceptEdits"])

    def test_no_agent_conf_leaves_the_flags_out(self):
        bare = self.repo("bare", conf=None)
        self.known(bare)
        code, body = self.add(bare)
        self.assertEqual(code, 200, body)
        self.assertEqual(shlex.split(self.calls[0][2]), ["claude", "--name", "bare Manager"])

    def test_unknown_territory(self):
        self.known(self.shop)
        self.assertEqual(self.state.add_agent("0badc0de", self.now), (404, {"error": "unknown"}))
        self.assertEqual(self.calls, [])

    def test_folder_gone(self):
        self.known(self.shop)
        folder = os.path.join(self.base, "shop")
        shutil.rmtree(folder)
        code, body = self.add(self.shop)
        self.assertEqual((code, body), (409, {"error": "gone", "folder": folder}))
        self.assertEqual(self.calls, [], "nothing is started in a folder that is not there")

    def test_the_opener_says_no(self):
        self.known(self.shop)
        self.answer = (False, "orca: the app is not running")
        code, body = self.add(self.shop)
        self.assertEqual((code, body.get("error"), body.get("detail")), (502, "failed", "orca: the app is not running"))
        self.answer = (True, "")
        code, body = self.add(self.shop)
        self.assertEqual((code, body.get("state")), (200, "opening"), "a failed open never leaves the repo held")
        self.assertEqual(len(self.calls), 2)

    def test_the_opener_raises(self):
        def boom(folder, title, command):
            raise OSError("no such file")

        state = self.make(open_fn=boom, start_repo=self.shop)
        code, body = state.add_agent(ac.territory_id(self.shop), self.now)
        self.assertEqual((code, body.get("error")), (502, "failed"))
        state.open_fn = self.opener
        self.assertEqual(state.add_agent(ac.territory_id(self.shop), self.now)[0], 200)

    def test_the_city_is_not_frozen_while_a_terminal_opens(self):
        self.known(self.shop)
        free = []

        def slow(folder, title, command):
            got = self.state.lock.acquire(timeout=0.5)
            free.append(got)
            if got:
                self.state.lock.release()
            return True, ""

        self.state.open_fn = slow
        self.assertEqual(self.add(self.shop)[0], 200)
        self.assertEqual(free, [True], "add_agent held the city lock while the opener ran")

    def test_the_default_opener_is_open_session(self):
        state = self.make(open_fn=None)
        self.assertIs(state.open_fn, ac.open_session)


# ---------------------------------------------------------------------------
# A7: one open at a time per repo
# ---------------------------------------------------------------------------

class TestOneAtATime(AddCase):
    def test_a_second_click_opens_nothing(self):
        self.known(self.shop)
        self.assertEqual(self.add(self.shop)[0], 200)
        code, body = self.add(self.shop, at=self.now + 1)
        self.assertEqual((code, body.get("error")), (409, "busy"))
        self.assertEqual(len(self.calls), 1, "double click = one session")

    def test_two_clicks_at_the_same_moment(self):
        self.known(self.shop)

        def slow(folder, title, command):
            self.calls.append((folder, title, command))
            time.sleep(0.3)
            return True, ""

        self.state.open_fn = slow
        codes = []
        threads = [threading.Thread(target=lambda: codes.append(self.add(self.shop)[0])) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(sorted(codes), [200, 409])
        self.assertEqual(len(self.calls), 1)

    def test_another_repo_is_not_held_up(self):
        bar = self.repo("bar")
        self.known(self.shop)
        self.known(bar, "old2")
        self.assertEqual(self.add(self.shop)[0], 200)
        self.assertEqual(self.add(bar)[0], 200)
        self.assertEqual([c[1] for c in self.calls], ["shop Manager", "bar Manager"])

    def test_free_again_when_the_new_session_shows_up(self):
        self.known(self.shop, "old1")
        self.assertEqual(self.add(self.shop)[0], 200)
        self.feed(line("UserPromptSubmit", "old1", self.shop), at=self.now + 1)        # a session from before the open
        self.feed(line("PostToolUse", "old1", self.shop, aid="a1"), at=self.now + 1)   # and its subagent
        self.assertEqual(self.add(self.shop, at=self.now + 2)[0], 409, "an old session's line is not the new one")
        self.feed(line("UserPromptSubmit", "new1", self.shop), at=self.now + 3)        # the new session's first line
        self.assertEqual(self.add(self.shop, at=self.now + 4)[0], 200)
        self.assertEqual(len(self.calls), 2)

    def test_free_again_after_the_wait(self):
        self.known(self.shop)
        self.assertEqual(ac.ADD_WAIT_SEC, 60.0)
        self.assertEqual(self.add(self.shop)[0], 200)
        self.assertEqual(self.add(self.shop, at=self.now + ac.ADD_WAIT_SEC - 1)[0], 409)
        self.assertEqual(self.add(self.shop, at=self.now + ac.ADD_WAIT_SEC + 1)[0], 200,
                         "a session that never came online must not hold its repo for ever")
        self.assertEqual(len(self.calls), 2)


# ---------------------------------------------------------------------------
# A7: the request names a territory id, nothing else; a fixed command
# ---------------------------------------------------------------------------

class TestRequestShape(AddCase):
    def test_only_a_territory_id(self):
        self.known(self.shop)
        tid = ac.territory_id(self.shop)
        for bad in (None, 5, "", "shop", self.shop, os.path.join(self.base, "shop"), "../../etc", tid.upper() + "x",
                    tid + " ", tid + "; touch pwned", [tid], {"id": tid}):
            with self.subTest(terr=bad):
                self.assertEqual(self.state.add_agent(bad, self.now), (400, {"error": "bad"}))
        for bad in ("yes", 1, None, "true"):
            with self.subTest(force=bad):
                self.assertEqual(self.state.add_agent(tid, self.now, force=bad), (400, {"error": "bad"}))
        self.assertEqual(self.calls, [])


class TestCommand(AddCase):
    def test_a_folder_name_cannot_break_the_line(self):
        name = "sh op'; touch pwned; echo '"
        evil = self.repo(name)
        self.known(evil)
        code, body = self.add(evil)
        self.assertEqual((code, body.get("name")), (200, name + " Manager"))
        folder, title, command = self.calls[0]
        self.assertEqual(folder, os.path.join(self.base, name))
        self.assertEqual(title, name + " Manager")
        self.assertEqual(shlex.split(command), ["claude", "--name", name + " Manager"] + FLAGS,
                         "the name must reach claude as ONE quoted word")
        self.assertNotIn(os.path.join(self.base, name), command, "the folder is the opener's own argument, never in the line")

    def test_agent_conf_text_cannot_break_the_line(self):
        cases = {
            "both": ("main_manager=opus-5.5:high; touch pwned\npermission_mode=auto$(touch pwned)\n", []),
            "mode": ("main_manager=opus-5.5:high\npermission_mode=auto && touch pwned\n",
                     ["--model", "opus-5.5", "--effort", "high"]),
            "model": ("main_manager=`touch pwned`:high\npermission_mode=plan\n", ["--permission-mode", "plan"]),
            "effort": ("main_manager=opus-5.5:huge\npermission_mode=auto\n", ["--permission-mode", "auto"]),
        }
        for name, (conf, flags) in cases.items():
            with self.subTest(case=name):
                identity = self.repo(name, conf)
                folder = os.path.join(self.base, name)
                command = ac.agent_command(name + " Manager", folder)
                self.assertEqual(shlex.split(command), ["claude", "--name", name + " Manager"] + flags)
                self.assertNotIn("pwned", command)
                self.assertEqual(ac.repo_folder(identity), folder)

    def test_no_shell_anywhere(self):
        with open(SERVER, encoding="utf-8") as fh:
            src = fh.read()
        for bad in ("shell=True", "os.system(", "os.popen("):
            self.assertNotIn(bad, src)


# ---------------------------------------------------------------------------
# A3: the real opener, pointed at a fake runtime script (never a real session)
# ---------------------------------------------------------------------------

class TestOpenSession(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_open_"))
        self.out = os.path.join(self.base, "argv")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def runtime(self, body):
        path = os.path.join(self.base, "fake-runtime.sh")
        with open(path, "w") as fh:
            fh.write("#!/usr/bin/env bash\n" + body)
        return path

    def test_every_argument_is_its_own_word(self):
        fake = self.runtime("printf '%%s\\0' \"$@\" > %s\n" % shlex.quote(self.out))
        folder = os.path.join(self.base, "my repo")
        title = "sh op'; touch %s; echo ' Manager" % os.path.join(self.base, "pwned")
        command = "claude --name 'x $(touch %s) Manager' --effort high" % os.path.join(self.base, "pwned")
        self.assertEqual(ac.open_session(folder, title, command, runtime=fake), (True, ""))
        with open(self.out, "rb") as fh:
            argv = fh.read().decode("utf-8").split("\0")[:-1]
        self.assertEqual(argv, ["launch", folder, title, command])
        self.assertFalse(os.path.exists(os.path.join(self.base, "pwned")), "some text was run by a shell")

    def test_a_failed_launch_gives_the_reason(self):
        fake = self.runtime("echo 'noise' >&2\necho 'runtime: plain mode has no terminals' >&2\nexit 1\n")
        ok, detail = ac.open_session(self.base, "t", "claude", runtime=fake)
        self.assertFalse(ok)
        self.assertEqual(detail, "runtime: plain mode has no terminals")

    def test_never_raises(self):
        ok, detail = ac.open_session(self.base, "t", "claude", runtime=os.path.join(self.base, "missing.sh"))
        self.assertFalse(ok)
        self.assertIsInstance(detail, str)
        self.assertTrue(detail)


# ---------------------------------------------------------------------------
# A7: POST /api/agent/add -- the chat gate, the local page only
# ---------------------------------------------------------------------------

class TestHttp(AddCase):
    """An in-process server with the fake opener: even a broken gate opens nothing real."""

    def setUp(self):
        super().setUp()
        self.tid = self.known(self.shop)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ac.CityHandler)
        self.server.daemon_threads = True
        self.server.city = self.state
        self.server.hub = None
        self.server.page_bytes = b""
        self.server.assets_dir = self.base
        self.port = self.server.server_address[1]
        self.server.host_set = {"127.0.0.1:%d" % self.port, "localhost:%d" % self.port}
        self.server.origin_set = {"http://127.0.0.1:%d" % self.port, "http://localhost:%d" % self.port}
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        super().tearDown()

    def call(self, method="POST", body=None, token="tok", origin="own", host=None, raw=None, path="/api/agent/add"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        headers = {}
        if token is not None:
            headers["X-City-Token"] = token
        if origin is not None:
            headers["Origin"] = "http://127.0.0.1:%d" % self.port if origin == "own" else origin
        if host is not None:
            headers["Host"] = host
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        text = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(text or b"null")
        except ValueError:
            return resp.status, None

    def test_the_page_opens_one(self):
        code, body = self.call(body={"terr": self.tid})
        self.assertEqual(code, 200, body)
        self.assertEqual((body["state"], body["name"], body["role"]), ("opening", "shop Manager", "main"))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.call(body={"terr": self.tid})[0], 409, "the second click")
        self.assertEqual(len(self.calls), 1)

    def test_force_is_part_of_the_shape(self):
        code, body = self.call(body={"terr": self.tid, "force": True})
        self.assertEqual((code, body.get("state")), (200, "opening"))

    def test_the_gate(self):
        ok = {"terr": self.tid}
        self.assertEqual(self.call(body=ok, token=None)[0], 403, "no token")
        self.assertEqual(self.call(body=ok, token="wrong")[0], 403, "wrong token")
        self.assertEqual(self.call(body=ok, origin=None)[0], 403, "no Origin: not the page")
        self.assertEqual(self.call(body=ok, origin="http://evil.example")[0], 403, "another site's page")
        self.assertEqual(self.call(body=ok, host="evil.example")[0], 403, "not asked as 127.0.0.1")
        self.assertEqual(self.call(body=ok, host="192.168.1.5:%d" % self.port)[0], 403, "not asked as 127.0.0.1")
        self.assertEqual(self.calls, [], "a refused request must never open a session")

    def test_post_only(self):
        for method in ("GET", "PUT", "DELETE"):
            with self.subTest(method=method):
                code, _ = self.call(method=method, path="/api/agent/add?terr=" + self.tid)
                self.assertNotEqual(code // 100, 2)
        self.assertEqual(self.calls, [])

    def test_nothing_but_a_territory_id(self):
        for body in ({"terr": self.tid, "path": "/tmp/evil"}, {"terr": self.tid, "name": "x'; touch pwned; '"},
                     {"terr": self.tid, "command": "touch pwned"}, {"terr": self.tid, "role": "task-manager"},
                     {"path": os.path.join(self.base, "shop")}, {}, {"terr": self.shop}, {"terr": self.tid, "force": "yes"}):
            with self.subTest(body=body):
                self.assertEqual(self.call(body=body)[0], 400)
        self.assertEqual(self.call(raw=b"not json")[0], 400)
        self.assertEqual(self.call(raw=json.dumps([self.tid]).encode())[0], 400)
        self.assertEqual(self.call(body={"terr": "0badc0de"})[0], 404)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
