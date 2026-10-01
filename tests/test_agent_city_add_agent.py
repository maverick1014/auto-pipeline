"""Failing tests for city-add-agent (requirements/city.md, "Add agent"; owner,
2026-10-01; approved mock mock/city-add-agent-mock.html): start a new agent
session from the city page, no terminal needed. This file: the server side
(A1 "here", A3 the open itself, A4 page events, A5 over the cap, A6 no Orca,
A7 safety). The page: tests/test_agent_city_add_agent_page.py. No test here
ever opens a real session: the opener is always a fake.

CONTRACT, server (bin/agent_city.py, Python standard library only)

  ADD_WAIT_SEC = 60.0

  repo_folder(identity) -> the folder a new session starts in: the parent of
    a ".../.git" identity (the repo's main worktree), else the identity itself.

  FIRST_PROMPT = "You were opened from the Agent City page. Do your start
    steps now, then stop and wait: the owner will talk to you from the city
    page."  (one line, exactly this text). A new session sends the city no
    event before its first prompt, and the page can only talk to a session
    that has had a turn: so the fixed line ends with this fixed first
    message. The session takes its first turn at once, appears in the city,
    and can be talked to from the page.

  agent_command(name, folder, city_dir=None) -> str. The one fixed line a new
    terminal runs:
      [AGENT_CITY_DIR=<city_dir> ]claude --name <name> [--model <m> --effort
      <e>] [--permission-mode <p>] <FIRST_PROMPT>
    NAME, CITY_DIR and FIRST_PROMPT go in through shlex.quote. <m>:<e> =
    main_manager and <p> = permission_mode of <folder>/agent.conf (rule W10:
    a second session opens with the main manager's values); <m> goes through
    agent_conf.cli_model() first (bounce 1: `claude --model fable-5.1` is
    refused, the session's first turn dies). A missing file,
    a missing value or a value bin/agent_conf.py validate_value() refuses ->
    that part is left out; never raises. Nothing else ever goes into the
    line: no folder, no "cd", no AGENT_ROLE (task managers are never created
    here). city_dir None -> the line starts with "claude ".

  bin/agent_conf.py cli_model(spec) -> the model name the claude CLI takes
    (bounce 1, laptop E2E 2026-10-01: agent.conf names are not CLI names;
    fable-5.1, opus-5.5 and sonnet-5 are refused, the family alias works).
    SPEC is "model" or "model:effort" (the effort part is dropped). A name
    that starts with opus, sonnet, haiku or fable -> that family word;
    anything else (a full CLI id like claude-fable-5-1, an unknown name)
    goes through unchanged. THE one place with this rule:
      `python3 bin/agent_conf.py cli-model <spec>` prints it (one line, exit
      0); bin/agent-resume.sh's model_name asks that, and keeps no family
      list of its own (its behaviour stays as tests/test_agent_resume.py
      says); agent_command calls cli_model.

  pass_city_dir(directory) -> None when DIRECTORY is the default city dir
    (~/.cache/agent-city, compared by realpath), else its absolute path. A
    city that runs with its own dir passes it on, so the session it opens
    reports to THIS city and not to the default one. cmd_serve builds
    CityState(..., city_dir=pass_city_dir(directory)).

  open_session(folder, title, command, runtime=None) -> (ok, detail)
    THE opener, the only place that starts anything. Runs
      bash <runtime> launch <folder> <title> <command>
    as an argument list (never shell=True, never one joined string);
    runtime = bin/agent-runtime.sh next to this file when None. Exit 0 ->
    (True, ""); anything else (exit code, timeout, missing script) ->
    (False, <a short reason, the script's last stderr line when it has one>).
    Never raises.

  runtime_kind(folder, runtime=None) -> "orca" | "plain" | "cloud"
    What `bash <runtime> kind` prints (runtime = bin/agent-runtime.sh when
    None), run with cwd = FOLDER and CLAUDE_PROJECT_DIR = FOLDER, so that
    repo's own agent.conf `runtime` line counts. Any other output, an error
    or a timeout -> "plain". Never raises.

  machine_resources(folder, script=None) -> {"ram", "cpu", "max", "ok"}
    RAM and CPU percent as bin/agent-resources.sh reads them (its own
    resources_read, sourced, argument list only; AGENT_FAKE_RAM /
    AGENT_FAKE_CPU work as they do there); max = max_usage_percent of
    <folder>/agent.conf, else of bin/agent.conf.default (never a number
    written in the code); ok = ram <= max and cpu <= max. A number that
    cannot be read is -1 (and counts as ok). Never raises.

  CityState(..., open_fn=None, kind_fn=None, resources_fn=None, city_dir=None)
    city_dir: handed to agent_command (the opener's line and the "plain"
      command alike).
    open_fn(folder, title, command) -> (ok, detail); default open_session
      (CityState.open_fn). Tests pass a fake.
    kind_fn(folder) -> "orca" | "plain" | "cloud"; default runtime_kind
      (CityState.kind_fn). Raises -> counts as "plain".
    resources_fn(folder) -> {"ram", "cpu", "max", "ok"}; default
      machine_resources (CityState.resources_fn). Raises -> counts as ok.

  CityState.add_agent(terr, now, force=False) -> (code, body). NOW = monotonic.
    400 {"error": "bad"}       terr is not a str of 8 lowercase hex digits,
                               or force is not a bool
    404 {"error": "unknown"}   no territory with that id in the world
    409 {"error": "gone", "folder"}   its folder is not a directory any more
    409 {"error": "busy"}      an open for this repo is under way
    200 {"state": "plain", "name", "role", "command"}   A6: kind_fn(folder)
                               is not "orca": no terminal can be opened.
                               command = "cd " + shlex.quote(folder) + " && "
                               + agent_command(name, folder, city_dir), the one line to
                               run by hand. Shown, never run. Asked before the
                               cap; the repo is not held.
    200 {"state": "cap", "ram", "cpu", "max"}   A5: resources_fn(folder) is
                               not ok and force is false: nothing opens, the
                               repo is not held; the owner confirms (the page
                               asks again with force true) or cancels.
                               force true -> opens whatever the numbers say.
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
    open_fn(folder, name, agent_command(name, folder, city_dir)) is called ONCE, and
    never while self.lock is held (opening a terminal takes seconds); the
    same for kind_fn and resources_fn.
    One open at a time per repo: from the call that opens until (a) a session
    line (aid "") of that repo from a sid that had no line in it before the
    open, (b) ADD_WAIT_SEC later, or (c) the opener failing. Other repos are
    never held up.

  A4, page events (to every page, like "chat"):
    {"type": "adding", "terr", "state": "opening", "name", "role"}  the
      opener said yes
    {"type": "adding", "terr", "state": "done"}   (a): the new session's
      first line came (the person appears through the usual events)
    {"type": "adding", "terr", "state": "late"}   (b): ADD_WAIT_SEC passed
      with no new session. Sent by CityState.sweep_adding(now), which
      recount_loop calls every tick; once.
    A new session so fast that its first line comes while the opener is
      still running is the new session all the same: the repo is free when
      add_agent returns, and "opening" is followed by "done" (never left
      hanging until "late").
    A failed open, a "plain" or a "cap" answer: no event.
    The snapshot of a new page carries "adding": [{"terr", "name", "role"}],
      one per repo whose open is under way ([] when none).

  A1 / A2, "here": every territory in the page's world view (the snapshot's
    "world" and every "world" event) carries "here": true when
    repo_folder(identity) is a directory on this machine, else false. The
    page shows the add-agent button only for a territory that is here.

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
from unittest import mock

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
FLAGS = ["--model", "opus", "--effort", "high", "--permission-mode", "auto"]   # CONF's opus-5.5 as the CLI takes it
PROMPT = ("You were opened from the Agent City page. Do your start steps now, then stop and wait: "
          "the owner will talk to you from the city page.")


def line(ev, sid, repo, aid="", role=""):
    return {"ev": ev, "sid": sid, "aid": aid, "at": "", "tool": "Read", "nt": "", "proj": "shop", "role": role,
            "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}


class AddCase(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_add_"))
        self.calls = []                 # every call of the fake opener: (folder, title, command)
        self.answer = (True, "")        # what the fake opener says
        self.mains = Mains()            # identity -> sid of its live main manager
        self.kind = "orca"              # what the fake kind_fn says
        self.res = {"ram": 10, "cpu": 10, "max": 80, "ok": True}   # what the fake resources_fn says
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
                    main_fn=self.mains, open_fn=self.opener, kind_fn=lambda folder: self.kind,
                    resources_fn=lambda folder: dict(self.res))
        args.update(kw)
        return ac.CityState(decisions_path=args.pop("decisions_path"), **args)   # never the owner's real decisions file

    def feed(self, *lines, at=None):
        for obj in lines:
            self.state.feed_line(obj, self.now if at is None else at)

    def known(self, identity, sid="old1"):
        """The city knows IDENTITY: one session of it has had a turn."""
        self.feed(line("UserPromptSubmit", sid, identity), line("Stop", sid, identity))
        return ac.territory_id(identity)

    def add(self, identity, at=None, **kw):
        return self.state.add_agent(ac.territory_id(identity), self.now if at is None else at, **kw)

    def client(self, state=None):
        c = (state or self.state).add_client()
        while not c.queue.empty():
            c.queue.get_nowait()
        return c

    @staticmethod
    def events(client, kind="adding"):
        out = []
        while not client.queue.empty():
            raw = client.queue.get_nowait().decode("utf-8")
            if "data:" not in raw:
                continue
            msg = json.loads(raw.split("data:", 1)[1])
            if msg.get("type") == kind:
                out.append(msg)
        return out


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
        self.assertEqual(shlex.split(command), ["claude", "--name", "shop Manager"] + FLAGS + [PROMPT])

    def test_live_main_manager_opens_a_helper(self):
        self.mains[self.shop] = "g1"
        self.known(self.shop, "g1")
        code, body = self.add(self.shop)
        self.assertEqual(code, 200, body)
        self.assertEqual((body["state"], body["name"], body["role"]), ("opening", "shop Helper", "helper"))
        folder, title, command = self.calls[0]
        self.assertEqual(title, "shop Helper")
        self.assertEqual(shlex.split(command), ["claude", "--name", "shop Helper"] + FLAGS + [PROMPT],
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
                         ["claude", "--name", "bar Manager", "--model", "sonnet", "--effort", "medium",
                          "--permission-mode", "acceptEdits", PROMPT])

    def test_no_agent_conf_leaves_the_flags_out(self):
        bare = self.repo("bare", conf=None)
        self.known(bare)
        code, body = self.add(bare)
        self.assertEqual(code, 200, body)
        self.assertEqual(shlex.split(self.calls[0][2]), ["claude", "--name", "bare Manager", PROMPT])

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

    def test_the_defaults_are_the_real_ones(self):
        state = self.make(open_fn=None, kind_fn=None, resources_fn=None)
        self.assertIs(state.open_fn, ac.open_session)
        self.assertIs(state.kind_fn, ac.runtime_kind)
        self.assertIs(state.resources_fn, ac.machine_resources)


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
        self.assertEqual(shlex.split(command), ["claude", "--name", name + " Manager"] + FLAGS + [PROMPT],
                         "the name must reach claude as ONE quoted word")
        self.assertNotIn(os.path.join(self.base, name), command, "the folder is the opener's own argument, never in the line")

    def test_agent_conf_text_cannot_break_the_line(self):
        cases = {
            "both": ("main_manager=opus-5.5:high; touch pwned\npermission_mode=auto$(touch pwned)\n", []),
            "mode": ("main_manager=opus-5.5:high\npermission_mode=auto && touch pwned\n",
                     ["--model", "opus", "--effort", "high"]),
            "model": ("main_manager=`touch pwned`:high\npermission_mode=plan\n", ["--permission-mode", "plan"]),
            "effort": ("main_manager=opus-5.5:huge\npermission_mode=auto\n", ["--permission-mode", "auto"]),
        }
        for name, (conf, flags) in cases.items():
            with self.subTest(case=name):
                identity = self.repo(name, conf)
                folder = os.path.join(self.base, name)
                command = ac.agent_command(name + " Manager", folder)
                self.assertEqual(shlex.split(command), ["claude", "--name", name + " Manager"] + flags + [PROMPT])
                self.assertNotIn("pwned", command)
                self.assertEqual(ac.repo_folder(identity), folder)

    def test_the_line_ends_with_the_fixed_first_prompt(self):
        """A new session sends the city nothing before its first prompt: the line carries one."""
        self.assertEqual(ac.FIRST_PROMPT, PROMPT)
        self.assertNotIn("\n", ac.FIRST_PROMPT)
        self.known(self.shop)
        self.add(self.shop)
        command = self.calls[0][2]
        self.assertEqual(shlex.split(command)[-1], PROMPT, "the first prompt is the last word, one quoted word")
        self.assertTrue(command.endswith(shlex.quote(PROMPT)))

    def test_a_city_with_its_own_dir_passes_it_on(self):
        own = os.path.join(self.base, "my city")
        folder = os.path.join(self.base, "shop")
        self.assertEqual(shlex.split(ac.agent_command("shop Manager", folder, city_dir=own)),
                         ["AGENT_CITY_DIR=" + own, "claude", "--name", "shop Manager"] + FLAGS + [PROMPT])
        self.assertTrue(ac.agent_command("shop Manager", folder, own).startswith("AGENT_CITY_DIR=" + shlex.quote(own) + " claude "))
        self.assertTrue(ac.agent_command("shop Manager", folder).startswith("claude "))
        state = self.make(city_dir=own, start_repo=self.shop)
        state.add_agent(ac.territory_id(self.shop), self.now)
        self.assertEqual(shlex.split(self.calls[0][2])[:2], ["AGENT_CITY_DIR=" + own, "claude"],
                         "the session this city opens must report to this city")
        self.kind = "plain"
        code, body = state.add_agent(ac.territory_id(self.shop), self.now + ac.ADD_WAIT_SEC + 1)
        self.assertEqual(shlex.split(body["command"])[:5], ["cd", folder, "&&", "AGENT_CITY_DIR=" + own, "claude"])

    def test_the_default_city_dir_is_not_passed(self):
        default = os.path.expanduser("~/.cache/agent-city")
        self.assertIsNone(ac.pass_city_dir(default))
        self.assertIsNone(ac.pass_city_dir(default + "/"))
        own = os.path.join(self.base, "city")
        self.assertEqual(ac.pass_city_dir(own), own)
        import inspect
        self.assertRegex(inspect.getsource(ac.cmd_serve), r"city_dir=pass_city_dir\(directory\)")

    def test_the_model_is_a_name_the_cli_takes(self):
        """Bounce 1: `claude --model fable-5.1` is refused and the opened session's first turn dies."""
        for value, flags in (("fable-5.1:xhigh", ["--model", "fable", "--effort", "xhigh"]),
                             ("opus-5.5:high", ["--model", "opus", "--effort", "high"]),
                             ("sonnet-5:medium", ["--model", "sonnet", "--effort", "medium"]),
                             ("haiku-4.5:low", ["--model", "haiku", "--effort", "low"]),
                             ("claude-fable-5-1:max", ["--model", "claude-fable-5-1", "--effort", "max"]),
                             ("mystery-7:high", ["--model", "mystery-7", "--effort", "high"])):
            with self.subTest(main_manager=value):
                name = "m-" + value.split(":")[0].replace(".", "-")
                self.repo(name, "main_manager=%s\n" % value)
                command = ac.agent_command("x Manager", os.path.join(self.base, name))
                self.assertEqual(shlex.split(command), ["claude", "--name", "x Manager"] + flags + [PROMPT])
        with open(os.path.join(BIN, "agent.conf.default")) as fh:
            default = fh.read()
        self.repo("as-shipped", default)
        words = shlex.split(ac.agent_command("x Manager", os.path.join(self.base, "as-shipped")))
        self.assertIn(words[words.index("--model") + 1], ("fable", "opus", "sonnet", "haiku"),
                      "the conf this plugin ships must open a session that can run")

    def test_no_shell_anywhere(self):
        with open(SERVER, encoding="utf-8") as fh:
            src = fh.read()
        for bad in ("shell=True", "os.system(", "os.popen("):
            self.assertNotIn(bad, src)


# ---------------------------------------------------------------------------
# bounce 1: agent.conf model names -> CLI model names, in ONE place
# ---------------------------------------------------------------------------

class TestCliModel(unittest.TestCase):
    TABLE = (("fable-5.1:xhigh", "fable"), ("fable-5.1", "fable"), ("opus-5.5:xhigh", "opus"), ("opus-5:high", "opus"),
             ("sonnet-5:medium", "sonnet"), ("haiku-4.5:low", "haiku"), ("fable", "fable"), ("opus:max", "opus"),
             ("claude-fable-5-1", "claude-fable-5-1"), ("claude-opus-5-5:high", "claude-opus-5-5"),
             ("mystery-7:high", "mystery-7"), ("mystery-7", "mystery-7"))

    def test_the_rule(self):
        import agent_conf
        for spec, want in self.TABLE:
            with self.subTest(spec=spec):
                self.assertEqual(agent_conf.cli_model(spec), want)

    def test_the_command_line_says_the_same(self):
        for spec, want in self.TABLE:
            with self.subTest(spec=spec):
                done = subprocess.run([sys.executable, os.path.join(BIN, "agent_conf.py"), "cli-model", spec],
                                      capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
                self.assertEqual((done.returncode, done.stdout), (0, want + "\n"), done.stderr)

    def test_one_place(self):
        with open(os.path.join(BIN, "agent-resume.sh"), encoding="utf-8") as fh:
            resume = fh.read()
        self.assertIn("agent_conf.py", resume)
        self.assertIn("cli-model", resume, "agent-resume.sh's model_name must ask agent_conf.py cli-model")
        for family in ("opus*)", "sonnet*)", "haiku*)", "fable*)"):
            self.assertNotIn(family, resume, "no second copy of the family list")
        with open(SERVER, encoding="utf-8") as fh:
            server = fh.read()
        self.assertIn("cli_model(", server)


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
# A6: no Orca on this machine -> the one command to run by hand
# ---------------------------------------------------------------------------

class TestPlain(AddCase):
    def test_plain_gives_the_command_and_opens_nothing(self):
        self.known(self.shop)
        for kind in ("plain", "cloud"):
            with self.subTest(kind=kind):
                self.kind = kind
                code, body = self.add(self.shop)
                self.assertEqual(code, 200, body)
                self.assertEqual((body["state"], body["name"], body["role"]), ("plain", "shop Manager", "main"))
                self.assertEqual(shlex.split(body["command"]),
                                 ["cd", os.path.join(self.base, "shop"), "&&", "claude", "--name", "shop Manager"] + FLAGS + [PROMPT])
        self.assertEqual(self.calls, [], "no terminal can be opened here")
        self.kind = "orca"
        self.assertEqual(self.add(self.shop)[1].get("state"), "opening", "a plain answer never holds the repo")

    def test_a_helper_when_the_repo_has_a_main_manager(self):
        self.mains[self.shop] = "g1"
        self.known(self.shop, "g1")
        self.kind = "plain"
        code, body = self.add(self.shop)
        self.assertEqual((body["name"], body["role"]), ("shop Helper", "helper"))
        self.assertIn("'shop Helper'", body["command"])

    def test_the_folder_is_one_quoted_word(self):
        name = "my repo'; touch pwned; echo '"
        evil = self.repo(name)
        self.known(evil)
        self.kind = "plain"
        code, body = self.add(evil)
        words = shlex.split(body["command"])
        self.assertEqual(words[:3], ["cd", os.path.join(self.base, name), "&&"])
        self.assertEqual(words[3:6], ["claude", "--name", name + " Manager"])

    def test_plain_is_asked_before_the_cap(self):
        self.known(self.shop)
        self.kind = "plain"
        self.res = {"ram": 95, "cpu": 95, "max": 80, "ok": False}
        self.assertEqual(self.add(self.shop)[1].get("state"), "plain",
                         "a command the owner runs by hand needs no cap question")

    def test_a_broken_kind_reader_counts_as_plain(self):
        def boom(folder):
            raise OSError("no bash")

        state = self.make(kind_fn=boom, start_repo=self.shop)
        code, body = state.add_agent(ac.territory_id(self.shop), self.now)
        self.assertEqual((code, body.get("state")), (200, "plain"))
        self.assertEqual(self.calls, [])

    def test_the_kind_is_asked_for_that_repos_folder(self):
        asked = []
        state = self.make(kind_fn=lambda folder: asked.append(folder) or "orca", start_repo=self.shop)
        state.add_agent(ac.territory_id(self.shop), self.now)
        self.assertEqual(asked, [os.path.join(self.base, "shop")])


class TestRuntimeKind(unittest.TestCase):
    """runtime_kind against the real bin/agent-runtime.sh, with the answer pinned (it never probes Orca here)."""

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_kind_"))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_the_callers_override(self):
        for kind in ("plain", "orca", "cloud"):
            with self.subTest(kind=kind), mock.patch.dict(os.environ, {"AGENT_RUNTIME": kind}):
                self.assertEqual(ac.runtime_kind(self.base), kind)

    def test_that_repos_agent_conf_counts(self):
        with open(os.path.join(self.base, "agent.conf"), "w") as fh:
            fh.write("runtime=plain\n")
        env = {k: v for k, v in os.environ.items() if k not in ("AGENT_RUNTIME", "CLAUDE_PROJECT_DIR", "CLAUDE_CODE_REMOTE")}
        env["CLAUDE_PROJECT_DIR"] = ROOT      # where the server itself was started: must not win
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(ac.runtime_kind(self.base), "plain")

    def test_anything_else_is_plain(self):
        fake = os.path.join(self.base, "fake.sh")
        for body in ("echo banana\n", "exit 3\n", "echo orca; exit 1\n"):
            with self.subTest(body=body):
                with open(fake, "w") as fh:
                    fh.write("#!/usr/bin/env bash\n" + body)
                self.assertEqual(ac.runtime_kind(self.base, runtime=fake), "plain")
        self.assertEqual(ac.runtime_kind(self.base, runtime=os.path.join(self.base, "missing.sh")), "plain")
        with open(fake, "w") as fh:
            fh.write("#!/usr/bin/env bash\n[ \"$1\" = kind ] && echo orca\n")
        self.assertEqual(ac.runtime_kind(self.base, runtime=fake), "orca", "the script is asked for `kind`")


# ---------------------------------------------------------------------------
# A5: over the resource cap -> the owner confirms or cancels
# ---------------------------------------------------------------------------

class TestCap(AddCase):
    def test_over_the_cap_asks_first(self):
        self.known(self.shop)
        self.res = {"ram": 86, "cpu": 41, "max": 80, "ok": False}
        code, body = self.add(self.shop)
        self.assertEqual((code, body), (200, {"state": "cap", "ram": 86, "cpu": 41, "max": 80}))
        self.assertEqual(self.calls, [], "over the cap: never just start")
        code, body = self.add(self.shop)
        self.assertEqual(body.get("state"), "cap", "a cap answer never holds the repo")

    def test_the_owner_confirms(self):
        self.known(self.shop)
        self.res = {"ram": 86, "cpu": 41, "max": 80, "ok": False}
        self.add(self.shop)
        code, body = self.add(self.shop, force=True)
        self.assertEqual((code, body.get("state"), body.get("name")), (200, "opening", "shop Manager"))
        self.assertEqual(len(self.calls), 1, "it is his click")

    def test_under_the_cap_just_opens(self):
        self.known(self.shop)
        self.res = {"ram": 80, "cpu": 80, "max": 80, "ok": True}
        self.assertEqual(self.add(self.shop)[1].get("state"), "opening")

    def test_a_broken_reader_never_blocks(self):
        def boom(folder):
            raise OSError("no top")

        state = self.make(resources_fn=boom, start_repo=self.shop)
        code, body = state.add_agent(ac.territory_id(self.shop), self.now)
        self.assertEqual((code, body.get("state")), (200, "opening"))

    def test_the_numbers_are_read_for_that_repos_folder(self):
        asked = []

        def res(folder):
            asked.append(folder)
            return {"ram": 1, "cpu": 1, "max": 80, "ok": True}

        state = self.make(resources_fn=res, start_repo=self.shop)
        state.add_agent(ac.territory_id(self.shop), self.now)
        self.assertEqual(asked, [os.path.join(self.base, "shop")])


class TestMachineResources(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_res_"))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def conf(self, text):
        with open(os.path.join(self.base, "agent.conf"), "w") as fh:
            fh.write(text)

    def test_the_numbers_and_that_repos_cap(self):
        with mock.patch.dict(os.environ, {"AGENT_FAKE_RAM": "91", "AGENT_FAKE_CPU": "12"}):
            self.conf("max_usage_percent=80\n")
            self.assertEqual(ac.machine_resources(self.base), {"ram": 91, "cpu": 12, "max": 80, "ok": False})
            self.conf("max_usage_percent=95\n")
            self.assertEqual(ac.machine_resources(self.base), {"ram": 91, "cpu": 12, "max": 95, "ok": True})
        with mock.patch.dict(os.environ, {"AGENT_FAKE_RAM": "20", "AGENT_FAKE_CPU": "81"}):
            self.conf("max_usage_percent=80\n")
            self.assertEqual(ac.machine_resources(self.base), {"ram": 20, "cpu": 81, "max": 80, "ok": False})
            self.conf("max_usage_percent=81\n")
            self.assertTrue(ac.machine_resources(self.base)["ok"], "at the cap is not over it")

    def test_no_agent_conf_takes_the_default_files_cap(self):
        import agent_conf
        default = int(agent_conf.load(os.path.join(BIN, "agent.conf.default"))["max_usage_percent"])
        with mock.patch.dict(os.environ, {"AGENT_FAKE_RAM": "5", "AGENT_FAKE_CPU": "5"}):
            self.assertEqual(ac.machine_resources(self.base), {"ram": 5, "cpu": 5, "max": default, "ok": True})
            self.conf("max_usage_percent=lots\n")
            self.assertEqual(ac.machine_resources(self.base)["max"], default, "a bad value is not a cap")

    def test_never_raises(self):
        got = ac.machine_resources(self.base, script=os.path.join(self.base, "missing.sh"))
        self.assertEqual((got["ram"], got["cpu"], got["ok"]), (-1, -1, True))


# ---------------------------------------------------------------------------
# A4: what the pages are told
# ---------------------------------------------------------------------------

class TestPageEvents(AddCase):
    def setUp(self):
        super().setUp()
        self.tid = self.known(self.shop)
        self.page = self.client()

    def test_opening_then_done(self):
        self.add(self.shop)
        self.assertEqual(self.events(self.page),
                         [{"type": "adding", "terr": self.tid, "state": "opening", "name": "shop Manager", "role": "main"}])
        self.feed(line("UserPromptSubmit", "old1", self.shop), at=self.now + 1)
        self.assertEqual(self.events(self.page), [], "an old session's line ends nothing")
        self.feed(line("UserPromptSubmit", "new1", self.shop), at=self.now + 2)
        self.assertEqual(self.events(self.page), [{"type": "adding", "terr": self.tid, "state": "done"}])
        self.feed(line("Stop", "new1", self.shop), at=self.now + 3)
        self.assertEqual(self.events(self.page), [], "done is said once")

    def test_late_after_the_wait(self):
        self.add(self.shop)
        self.events(self.page)
        self.state.sweep_adding(self.now + ac.ADD_WAIT_SEC - 1)
        self.assertEqual(self.events(self.page), [])
        self.state.sweep_adding(self.now + ac.ADD_WAIT_SEC + 1)
        self.assertEqual(self.events(self.page), [{"type": "adding", "terr": self.tid, "state": "late"}])
        self.state.sweep_adding(self.now + ac.ADD_WAIT_SEC + 5)
        self.assertEqual(self.events(self.page), [], "late is said once")
        self.assertEqual(self.add(self.shop, at=self.now + ac.ADD_WAIT_SEC + 6)[0], 200, "and the repo is free")

    def test_the_tick_sweeps(self):
        import inspect
        self.assertIn("sweep_adding", inspect.getsource(ac.recount_loop))

    def test_a_session_faster_than_the_opener(self):
        def fast(folder, title, command):
            self.calls.append((folder, title, command))
            self.state.feed_line(line("UserPromptSubmit", "new1", self.shop), self.now)   # it is already here
            return True, ""

        self.state.open_fn = fast
        code, body = self.add(self.shop)
        self.assertEqual((code, body.get("state")), (200, "opening"))
        got = [e["state"] for e in self.events(self.page)]
        self.assertEqual(got, ["opening", "done"], "the page must not wait %d s for a session that is here" % ac.ADD_WAIT_SEC)
        self.assertEqual(self.add(self.shop, at=self.now + 1)[0], 200, "the repo is free")

    def test_no_event_when_nothing_opened(self):
        self.answer = (False, "orca: the app is not running")
        self.add(self.shop)
        self.answer = (True, "")
        self.kind = "plain"
        self.add(self.shop)
        self.kind = "orca"
        self.res = {"ram": 99, "cpu": 1, "max": 80, "ok": False}
        self.add(self.shop)
        self.add("0badc0de")
        self.assertEqual(self.events(self.page), [])

    def test_a_new_page_knows_what_is_opening(self):
        def snapshot():
            c = self.state.add_client()
            return json.loads(c.queue.get_nowait().decode("utf-8").split("data:", 1)[1])

        self.assertEqual(snapshot()["adding"], [])
        self.add(self.shop)
        self.assertEqual(snapshot()["adding"], [{"terr": self.tid, "name": "shop Manager", "role": "main"}])
        self.feed(line("UserPromptSubmit", "new1", self.shop), at=self.now + 2)
        self.assertEqual(snapshot()["adding"], [])


# ---------------------------------------------------------------------------
# A1 / A2: every territory says whether its folder is on this machine
# ---------------------------------------------------------------------------

class TestHere(AddCase):
    def test_the_world_view_says_here(self):
        state = self.make(start_repo=self.shop)
        page = self.client(state)
        state.feed_line(line("UserPromptSubmit", "s9", "/nowhere/ghost/.git"), self.now)   # a repo that is not on this machine
        worlds = self.events(page, "world")
        self.assertTrue(worlds, "a new territory is a world event")
        here = {t["id"]: t.get("here") for t in worlds[-1]["world"]["territories"]}
        self.assertEqual(here, {ac.territory_id(self.shop): True, ac.territory_id("/nowhere/ghost/.git"): False})
        c = state.add_client()
        snap = json.loads(c.queue.get_nowait().decode("utf-8").split("data:", 1)[1])
        self.assertEqual({t["id"]: t.get("here") for t in snap["world"]["territories"]}, here)

    def test_a_folder_that_is_not_here_never_opens(self):
        tid = self.known("/nowhere/ghost/.git")
        code, body = self.state.add_agent(tid, self.now)
        self.assertEqual((code, body), (409, {"error": "gone", "folder": "/nowhere/ghost"}))
        self.assertEqual(self.calls, [])


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
        self.res = {"ram": 86, "cpu": 41, "max": 80, "ok": False}
        self.assertEqual(self.call(body={"terr": self.tid}), (200, {"state": "cap", "ram": 86, "cpu": 41, "max": 80}))
        self.assertEqual(self.call(body={"terr": self.tid, "force": False})[1].get("state"), "cap")
        code, body = self.call(body={"terr": self.tid, "force": True})
        self.assertEqual((code, body.get("state")), (200, "opening"))
        self.assertEqual(len(self.calls), 1)

    def test_plain_over_http(self):
        self.kind = "plain"
        code, body = self.call(body={"terr": self.tid})
        self.assertEqual((code, body.get("state")), (200, "plain"))
        self.assertTrue(body["command"].startswith("cd "))
        self.assertEqual(self.calls, [])

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
