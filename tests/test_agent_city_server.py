"""Failing tests for the city server (bin/agent_city.py serve) and bin/agent-city.sh.

CONTRACT: the server

  python3 bin/agent_city.py serve --dir DIR --port PORT
          [--idle-min N | --idle-sec S] [--max-log-kb K] [--page PATH] [--assets DIR]

  --port 0 picks a free port. --idle-sec wins over --idle-min (default 30 min).
  --max-log-kb default 256. --page default: agent-city.html next to the script.
  Python standard library only.

  Listens on 127.0.0.1 only. Once listening, writes DIR/on = "<pid> <port>\\n".
  Removes DIR/on when it exits for any reason it can catch (idle, SIGTERM,
  SIGINT).

  GET /         200 text/html, the page
  GET /assets/<path>  the file <assets>/<path>, where <assets> is --assets or,
                by default, agent-city-assets next to the script. Content-Type
                by extension: .js application/javascript, .glb
                model/gltf-binary, .png image/png, .txt text/plain.
                Cache-Control: no-cache (a versioned ?v= URL is cached
                long: tests/test_agent_city_balance.py). A path that leaves <assets>
                (.., %2e%2e, an absolute path, a symlink out) or a missing
                file: 404.
  GET /health   200 application/json {"ok": true, "lines": <good lines read
                since start>, "agents": <alive now>, "clients": <open /events>}
  GET /events   200 text/event-stream. First message: data: {"type":"snapshot",
                "gov":..., "agents":[...]} (the Reducer snapshot plus the type).
                Then one "data: <json>" message per city event made from lines
                appended to DIR/events.jsonl after the server started. Lines that
                were there before it started are skipped. Bad lines are skipped.
                At most 4 open at once: the 5th gets 503.
  anything else 404

  DIR/events.jsonl past --max-log-kb: moved to events.jsonl.1 (replacing any
  older one) and read to its end, so no line is lost and the folder never holds
  more than on, token, roster.json, events.jsonl and events.jsonl.1.
  five-fixes S4 (2026-11-05): a writer (the hook's `>>`) that opened
  events.jsonl before the rename and writes after it writes into the moved
  file. The server keeps reading the moved file for a while after the rename
  (at least 3 s), so those lines are read too: once each, none lost, none
  twice. The rotation test waits up to 60 s (a full suite on a loaded machine
  is slow; a lost line still fails it).
  (Interaction: token, the control API and the extra /health fields are in
  tests/test_agent_city_interact.py.)

  No /events client for the idle time -> exit 0. One open client keeps it alive.
  DIR/on already names a live pid -> print "already running" and exit 0 without
  starting a second server.
  After 20000 lines its memory (VmRSS) stays under 40 MB.

CONTRACT: bin/agent-city.sh start | stop | status | demo

  City dir is $AGENT_CITY_DIR, default $HOME/.cache/agent-city, same as the hook.
  start   reads city_port and city_idle_min from the project's agent.conf
          (template value when the key is missing), checks RAM and CPU against
          max_usage_percent with agent-resources.sh. Over the cap: prints a line
          with "OVER CAP" plus a warning line, then starts anyway. Starts the server in
          the background, waits for DIR/on, prints
            CITY: http://127.0.0.1:<port>
            CITY: stops by itself after <city_idle_min> min with no browser open
          exit 0. Already running: prints the same first line, exit 0.
  demo    same as start, but the URL ends with #demo.
  status  "CITY: running http://127.0.0.1:<port>" or "CITY: not running". Exit 0.
  stop    "CITY: stopped" (server gone, DIR/on gone) or "CITY: not running". Exit 0.
"""

import http.client
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from cityhelp import HERE, ROOT, SERVER, free_port, pid_alive, wait_for, SSE, ServerCase  # noqa: E402,F401  (test-slim: shared helpers)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase  # noqa: E402
import agent_city as ac  # noqa: E402
from cityhelp import QS  # noqa: E402
from cityhelp import SHOP  # noqa: E402
from cityhelp import q_body  # noqa: E402
from cityhelp import InteractCase as _InteractCase  # noqa: E402
from cityhelp import AskHookCase as _AskHookCase  # noqa: E402
from cityhelp import ServerCase as _ServerCase  # noqa: E402
from cityhelp import stop_payload  # noqa: E402
import re  # noqa: E402
from cityhelp import world_make_repo as make_repo  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402
from cityhelp import Mains  # noqa: E402
from cityhelp import A_REPO  # noqa: E402
from cityhelp import B_REPO  # noqa: E402
from cityhelp import TalkServerCase as ServerCase_rail_tree  # noqa: E402
from cityhelp import TALK_TA as TA  # noqa: E402
from cityhelp import TALK_TB as TB  # noqa: E402
import cityhelp as interact  # noqa: E402
from cityhelp import lock_file  # noqa: E402
from cityhelp import TALK_TA  # noqa: E402
from cityhelp import TALK_TB  # noqa: E402
from cityhelp import TalkServerCase  # noqa: E402
import shlex  # noqa: E402
from unittest import mock  # noqa: E402
from cityhelp import PROMPT  # noqa: E402
from cityhelp import line as line_aa  # noqa: E402
from cityhelp import configure_text  # noqa: E402
from cityhelp import AddCase  # noqa: E402


class _KillAtOnce:
    """test-slim-3: a server started by a test is killed at the end of the test, not asked to stop:
    the graceful stop waits for serve_forever's 0.2 s poll, about 0.2 s per test. The test folder is
    removed right after, so nothing of the server's exit is read by any test."""

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
        super().tearDown()


class ServerCase(_KillAtOnce, _ServerCase):
    pass


class InteractCase(_KillAtOnce, _InteractCase):
    pass


class AskHookCase(_KillAtOnce, _AskHookCase):
    pass


def line(ev, sid="s1", aid="", at="", tool="", nt="", role="", desc="", sub="", q=""):
    return json.dumps({"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": nt,
                       "proj": "shop", "role": role, "desc": desc, "sub": sub, "q": q}) + "\n"


class TestServe(ServerCase):
    def test_switch_file_names_pid_and_port(self):
        proc = self.start()
        pid, port = self.on()
        self.assertEqual(pid, proc.pid)
        self.assertGreater(port, 0)

    def test_page(self):
        self.start()
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn(b"<title>Agent City</title>", body)

    def test_health(self):
        self.start()
        status, headers, body = self.get("/health")
        self.assertEqual(status, 200)
        data = json.loads(body)
        # Interaction adds asks, gov_wait_sec and governors
        # (tests/test_agent_city_interact.py); nothing else.
        base = {k: data.get(k) for k in ("ok", "lines", "agents", "clients")}
        self.assertEqual(base, {"ok": True, "lines": 0, "agents": 0, "clients": 0})
        self.assertLessEqual(set(data), {"ok", "lines", "agents", "clients",
                                         "asks", "gov_wait_sec", "governors"})

    def test_unknown_path_is_404(self):
        self.start()
        self.assertEqual(self.get("/nope")[0], 404)
        self.assertEqual(self.get("/../../etc/passwd")[0], 404)

    def test_only_loopback(self):
        self.start()
        if not os.path.exists("/proc/net/tcp"):
            self.skipTest("no /proc/net/tcp here")
        port_hex = "%04X" % self.port
        with open("/proc/net/tcp") as fh:
            rows = [r.split() for r in fh.readlines()[1:]]
        listening = [r[1] for r in rows if r[1].endswith(":" + port_hex) and r[3] == "0A"]
        self.assertEqual(listening, ["0100007F:" + port_hex])

    def test_snapshot_first_then_live_events(self):
        self.start()
        client = self.sse()
        self.assertEqual(client.messages[0]["type"], "snapshot")
        self.assertEqual(client.messages[0]["agents"], [])
        self.assertIn("text/event-stream", client.headers.get("Content-Type", ""))
        self.append(line("PreToolUse", tool="Agent", desc="设置页表单", sub="worker"))
        self.append(line("SubagentStart", aid="a1", at="worker"))
        self.append(line("PostToolUse", aid="a1", at="worker", tool="Edit"))
        self.assertTrue(wait_for(lambda: client.events("tool")))
        spawn, tool = client.events("spawn")[0], client.events("tool")[0]
        self.assertIn("terr", spawn, "growth: a spawn names its territory (tests/test_agent_city_world.py)")
        # city-people adds lead/office/relay to every spawn (tests/test_agent_city_chain.py),
        # city-talk adds "from", who sent it (tests/test_agent_city_talk.py),
        # city-rail-tree adds "up", its parent (tests/test_agent_city_rail_tree.py)
        spawn = {k: v for k, v in spawn.items() if k not in ("terr", "lead", "office", "relay", "from", "up")}
        self.assertEqual(spawn, {"type": "spawn", "id": "a1", "role": "worker",
                                 "label": "worker", "task": "设置页表单"})
        self.assertEqual(tool, {"type": "tool", "id": "a1", "tool": "Edit", "name": "Edit"})

    def test_lines_from_before_the_start_are_skipped(self):
        os.makedirs(self.dir, exist_ok=True)
        self.append(line("SubagentStart", aid="old", at="worker"))
        self.start()
        client = self.sse()
        self.append(line("SubagentStart", aid="new", at="worker"))
        self.assertTrue(wait_for(lambda: client.events()))
        self.assertEqual([e["id"] for e in client.events("spawn")], ["new"])

    def test_snapshot_for_a_late_client(self):
        self.start()
        self.append(line("SubagentStart", aid="a1", at="worker"))
        self.assertTrue(wait_for(lambda: self.health()["agents"] == 1))
        client = self.sse()
        snap = client.messages[0]
        self.assertEqual([a["id"] for a in snap["agents"]], ["a1"])
        self.assertIn("gov", snap)

    def test_bad_lines_are_skipped(self):
        self.start()
        client = self.sse()
        self.append("not json\n{\"half\":\n")
        self.append(line("SubagentStart", aid="a1", at="worker"))
        self.assertTrue(wait_for(lambda: client.events()))
        self.assertEqual(self.health()["lines"], 1)

    def test_a_half_written_line_waits_for_its_end(self):
        self.start()
        client = self.sse()
        full = line("SubagentStart", aid="a1", at="worker")
        self.append(full[:20])
        time.sleep(0.8)
        self.append(full[20:])
        self.assertTrue(wait_for(lambda: client.events("spawn")))
        self.assertEqual(client.events("spawn")[0]["id"], "a1")

    def test_fifth_client_is_refused(self):
        self.start()
        for _ in range(4):
            self.assertEqual(self.sse().status, 200)
        self.assertTrue(wait_for(lambda: self.health()["clients"] == 4))
        self.assertEqual(self.sse().status, 503)

    def test_a_closed_client_frees_its_seat(self):
        self.start()
        client = self.sse()
        self.assertTrue(wait_for(lambda: self.health()["clients"] == 1))
        client.close()
        self.assertTrue(wait_for(lambda: self.health()["clients"] == 0, timeout=20))


class TestAssetsRoute(ServerCase):
    def setUp(self):
        super().setUp()
        self.assets = os.path.join(self.base, "assets")
        os.makedirs(os.path.join(self.assets, "vendor"))
        os.makedirs(os.path.join(self.assets, "pets", "Textures"))
        self.files = {
            "vendor/three.min.js": (b"var THREE={};", "application/javascript"),
            "pets/animal-cat.glb": (b"glTF\x02\x00\x00\x00fake", "model/gltf-binary"),
            "pets/Textures/colormap.png": (b"\x89PNG fake", "image/png"),
            "pets/License.txt": (b"CC0", "text/plain"),
        }
        for rel, (data, _) in self.files.items():
            with open(os.path.join(self.assets, rel), "wb") as fh:
                fh.write(data)
        with open(os.path.join(self.base, "secret.txt"), "w") as fh:
            fh.write("SECRET")
        os.symlink(os.path.join(self.base, "secret.txt"), os.path.join(self.assets, "link.txt"))
        self.start("--idle-sec", "60", "--assets", self.assets)

    def test_files_and_types(self):
        for rel, (data, kind) in self.files.items():
            with self.subTest(rel=rel):
                status, headers, body = self.get("/assets/" + rel)
                self.assertEqual(status, 200)
                self.assertEqual(body, data)
                self.assertIn(kind, headers.get("Content-Type", ""))
                self.assertEqual(headers.get("Cache-Control"), "no-cache", "no ?v=: never a stale day-long cache")

    def test_nothing_outside_the_folder(self):
        for path in ("/assets/../secret.txt", "/assets/%2e%2e/secret.txt", "/assets/..%2fsecret.txt",
                     "/assets//etc/passwd", "/assets/link.txt", "/assets/pets/../../secret.txt",
                     "/assets/missing.glb", "/assets/", "/assets/pets"):
            with self.subTest(path=path):
                status, _, body = self.get(path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"SECRET", body)

    def test_default_folder_is_next_to_the_script(self):
        proc = subprocess.Popen([sys.executable, SERVER, "serve", "--dir", os.path.join(self.base, "c2"),
                                 "--port", "0", "--idle-sec", "30"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(proc)
        on = os.path.join(self.base, "c2", "on")
        self.assertTrue(wait_for(lambda: os.path.exists(on)))
        with open(on) as fh:
            port = int(fh.read().split()[1])
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", "/assets/vendor/three.min.js")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertIn(b"SPDX-License-Identifier: MIT", body[:400])


class TestLifecycle(ServerCase):
    def test_idle_exit_removes_the_switch(self):
        proc = self.start("--idle-sec", "1.5")
        self.assertEqual(proc.wait(10), 0)
        self.assertIsNone(self.on())

    def test_an_open_client_keeps_it_alive(self):
        proc = self.start("--idle-sec", "1.5")
        client = self.sse()
        time.sleep(3.5)
        self.assertIsNone(proc.poll(), "server quit while a browser was open")
        client.close()
        self.assertEqual(proc.wait(15), 0)
        self.assertIsNone(self.on())

    def test_sigterm_removes_the_switch(self):
        proc = self.start()
        proc.send_signal(signal.SIGTERM)
        proc.wait(10)
        self.assertIsNone(self.on())

    def test_second_server_does_not_start(self):
        first = self.start()
        before = self.on()
        second = self.start(wait=False)
        out, _ = second.communicate(timeout=10)
        self.assertEqual(second.returncode, 0)
        self.assertIn("already running", out)
        self.assertEqual(self.on(), before)
        self.assertIsNone(first.poll())

    def test_stale_switch_is_taken_over(self):
        os.makedirs(self.dir, exist_ok=True)
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        with open(os.path.join(self.dir, "on"), "w") as fh:
            fh.write("%d 1\n" % dead.pid)
        proc = self.start()
        self.assertEqual(self.on()[0], proc.pid)


class TestBudget(ServerCase):
    def test_log_is_rotated_and_no_line_is_lost(self):
        self.start("--idle-sec", "60", "--max-log-kb", "4")
        client = self.sse()
        self.append(line("SubagentStart", aid="a1", at="worker"))
        for i in range(10):
            self.append("".join(line("PostToolUse", aid="a1", at="worker", tool="Edit")
                                for _ in range(30)))
            # was sleep(0.15): the next batch goes in once the city has read this one (60 s: a loaded run)
            wait_for(lambda: len(client.events("tool")) >= 30 * (i + 1), timeout=60)
        # five-fixes S4: 60 s, not 15: under a loaded full suite the lines come late, never lost
        self.assertTrue(wait_for(lambda: len(client.events("tool")) == 300, timeout=60),
                        "got %d tool events" % len(client.events("tool")))
        size = os.path.getsize(os.path.join(self.dir, "events.jsonl"))
        self.assertLess(size, 4096 + 30 * 200)
        # token: the per-start control token (tests/test_agent_city_interact.py)
        # roster.json: the live sessions, for a restart (tests/test_agent_city_roster.py)
        # history.jsonl: each person's history lines (city-data, tests/test_agent_city_data.py)
        self.assertLessEqual(set(os.listdir(self.dir)),
                             {"on", "token", "events.jsonl", "events.jsonl.1", "roster.json", "history.jsonl"})

    def test_a_write_through_a_handle_from_before_the_rename_is_read(self):
        """five-fixes S4: the hook's `>>` opened the log before the rename and
        writes after it, into the moved file: read anyway, once."""
        self.start("--idle-sec", "60", "--max-log-kb", "4")
        client = self.sse()
        path = os.path.join(self.dir, "events.jsonl")
        self.append(line("SubagentStart", aid="a1", at="worker"))
        batch = "".join(line("PostToolUse", aid="a1", at="worker", tool="Edit") for _ in range(30))
        held = open(path, "a")                       # opened before the rename
        ino = os.stat(path).st_ino
        self.append(batch)                           # 30 lines, past 4 KB: the server renames
        self.assertTrue(wait_for(lambda: os.path.exists(path) and os.stat(path).st_ino != ino, timeout=15),
                        "the log was never renamed")
        self.assertTrue(wait_for(lambda: len(client.events("tool")) == 30, timeout=15))
        self.append(batch[:len(batch) // 30 * 2])    # 2 lines into the new log
        time.sleep(1.0)
        held.write(batch)                            # 30 lines into the moved file, 1 s after the rename
        held.close()
        self.assertTrue(wait_for(lambda: len(client.events("tool")) == 62, timeout=15),
                        "got %d of 62 tool events: lines written after the rename were lost"
                        % len(client.events("tool")))
        time.sleep(1.0)
        self.assertEqual(len(client.events("tool")), 62, "a line was read twice")
        self.assertLessEqual(set(os.listdir(self.dir)),
                             {"on", "token", "events.jsonl", "events.jsonl.1", "roster.json", "history.jsonl"})

    def test_memory_stays_small(self):
        if not os.path.exists("/proc/self/status"):
            self.skipTest("no /proc here")
        proc = self.start("--idle-sec", "120")
        rows = []
        for i in range(20000):
            aid = "a%d" % (i % 100)
            if i % 50 == 0:
                rows.append(line("SubagentStart", aid=aid, at="worker"))
            elif i % 97 == 0:
                rows.append(line("SubagentStop", aid=aid, at="worker"))
            else:
                rows.append(line("PostToolUse", aid=aid, at="worker", tool="Edit"))
        for start in range(0, 20000, 2000):
            self.append("".join(rows[start:start + 2000]))
            time.sleep(0.1)
        self.assertTrue(wait_for(lambda: self.health()["lines"] == 20000, timeout=60),
                        "server read %d lines" % self.health()["lines"])
        with open("/proc/%d/status" % proc.pid) as fh:
            rss_kb = int([l for l in fh if l.startswith("VmRSS:")][0].split()[1])
        self.assertLess(rss_kb, 40 * 1024, "server uses %d MB" % (rss_kb // 1024))
        self.assertLessEqual(self.health()["agents"], 40)


class TestCityScript(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.city = os.path.join(self.repo.base, "city")
        self.port = free_port()
        self.repo.set_conf("city_port", str(self.port))
        self.repo.set_conf("city_idle_min", "7")

    def tearDown(self):
        on = os.path.join(self.city, "on")
        if os.path.exists(on):
            try:
                with open(on) as fh:
                    os.kill(int(fh.read().split()[0]), signal.SIGTERM)
            except (OSError, ValueError, IndexError):
                pass
        super().tearDown()

    def city_run(self, *args, env=None):
        full = {"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": os.path.join(self.repo.base, "cityhome")}
        full.update(env or {})
        return self.repo.run("agent-city.sh", *args, env=full, timeout=30)

    def test_start_prints_the_url_and_the_idle_time(self):
        result = self.city_run("start")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CITY: http://127.0.0.1:%d" % self.port, result.stdout)
        self.assertIn("7 min", result.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.city, "on")))

    def test_start_twice_runs_one_server(self):
        self.city_run("start")
        with open(os.path.join(self.city, "on")) as fh:
            first = fh.read()
        result = self.city_run("start")
        self.assertEqual(result.returncode, 0)
        self.assertIn("CITY: http://127.0.0.1:%d" % self.port, result.stdout)
        with open(os.path.join(self.city, "on")) as fh:
            self.assertEqual(fh.read(), first)

    def test_over_cap_warns_and_still_starts(self):
        result = self.city_run("start", env={"AGENT_FAKE_RAM": "95"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OVER CAP", result.stdout + result.stderr)
        self.assertIn("warning: over the resource cap; the city is small, starting anyway", result.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.city, "on")))

    def test_status_and_stop(self):
        self.assertIn("CITY: not running", self.city_run("status").stdout)
        self.city_run("start")
        with open(os.path.join(self.city, "on")) as fh:
            pid = int(fh.read().split()[0])
        self.assertIn("CITY: running http://127.0.0.1:%d" % self.port, self.city_run("status").stdout)
        result = self.city_run("stop")
        self.assertEqual(result.returncode, 0)
        self.assertIn("CITY: stopped", result.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.city, "on")))
        self.assertTrue(wait_for(lambda: not pid_alive(pid)))
        self.assertIn("CITY: not running", self.city_run("stop").stdout)

    def test_demo_url(self):
        result = self.city_run("demo")
        self.assertEqual(result.returncode, 0)
        self.assertIn("CITY: http://127.0.0.1:%d/#demo" % self.port, result.stdout)


def wait_for_anywhere(check, timeout=8.0, step=0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(step)
    return check()


def free_port_anywhere():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def server_pid(city_dir):
    try:
        with open(os.path.join(city_dir, "on")) as fh:
            return int(fh.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def server_args(city_dir):
    pid = server_pid(city_dir)
    if pid is None:
        return ""
    return wait_for_anywhere(lambda: subprocess.run(["ps", "-o", "args=", "-p", str(pid)],
                                           capture_output=True, text=True).stdout.strip())


def stop_server(city_dir):
    pid = server_pid(city_dir)
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGKILL)   # test-slim-3: at the end of a test, no graceful stop to wait for
    except OSError:
        return
    wait_for_anywhere(lambda: not _alive(pid), timeout=5)


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def write_text(path, text):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


class OutsideCase(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.city = os.path.join(self.repo.base, "city")
        self.cityhome = os.path.join(self.repo.base, "cityhome")
        self.plain = os.path.join(self.repo.base, "plain")
        os.makedirs(self.plain)
        self.port = free_port_anywhere()
        self.set_default("city_port", str(self.port))
        self.addCleanup(stop_server, self.city)

    def set_default(self, key, value):
        """settings-configure: the settings are user level (Configure), inside a repo or not."""
        self.repo.set_conf(key, value)

    def city_env(self, extra=None):
        env = {"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.cityhome,
               "AGENT_CITY_LANG": ""}
        env.update(extra or {})
        return env

    def city_run(self, *args, cwd=None, extra=None, stdin=None):
        return self.repo.run("agent-city.sh", *args, env=self.city_env(extra),
                             cwd=cwd or self.plain, stdin=stdin, timeout=30)


class TestStartOutsideARepo(OutsideCase):
    def test_the_settings_apply_outside_a_repo(self):
        # settings-configure: Language is a user-level setting (default en)
        result = self.city_run("start")
        self.assertOk(result)
        self.assertIn("CITY: http://127.0.0.1:%d" % self.port, result.stdout)
        args = server_args(self.city)
        self.assertIn("--port %d" % self.port, args)
        self.assertIn("--lang en", args)
        self.repo.set_conf("language", "zh")
        self.assertOk(self.city_run("stop"))
        self.assertOk(self.city_run("start"))
        self.assertIn("--lang zh", server_args(self.city))

    def test_an_agent_conf_in_a_plain_folder_is_never_read(self):
        write_text(os.path.join(self.plain, "agent.conf"),
                   "city_port=%d\nlanguage=zh\n" % free_port_anywhere())
        self.assertOk(self.city_run("start"))
        args = server_args(self.city)
        self.assertIn("--port %d" % self.port, args)
        self.assertIn("--lang en", args)

    def test_agent_city_lang_en(self):
        self.assertOk(self.city_run("start", extra={"AGENT_CITY_LANG": "en"}))
        self.assertIn("--lang en", server_args(self.city))

    def test_agent_city_lang_unknown_is_the_setting(self):
        self.assertOk(self.city_run("start", extra={"AGENT_CITY_LANG": "fr"}))
        self.assertIn("--lang en", server_args(self.city))

    def test_demo_is_the_same(self):
        result = self.city_run("demo")
        self.assertOk(result)
        self.assertIn("CITY: http://127.0.0.1:%d/#demo" % self.port, result.stdout)
        args = server_args(self.city)
        self.assertIn("--lang en", args)

    def test_inside_a_repo_agent_city_lang_overrides_too(self):
        # settings-configure: one user-level Language, so AGENT_CITY_LANG overrides it everywhere
        self.repo.set_conf("language", "en")
        self.assertOk(self.city_run("start", cwd=self.repo.dir, extra={"AGENT_CITY_LANG": "zh"}))
        self.assertIn("--lang zh", server_args(self.city))


class TestPort(OutsideCase):
    def test_agent_city_port_outside_a_repo(self):
        port = free_port_anywhere()
        result = self.city_run("start", extra={"AGENT_CITY_PORT": str(port)})
        self.assertOk(result)
        self.assertIn("CITY: http://127.0.0.1:%d" % port, result.stdout)
        self.assertIn("--port %d" % port, server_args(self.city))

    def test_agent_city_port_wins_over_the_setting_inside_a_repo(self):
        port = free_port_anywhere()
        self.repo.set_conf("city_port", str(free_port_anywhere()))
        result = self.city_run("start", cwd=self.repo.dir, extra={"AGENT_CITY_PORT": str(port)})
        self.assertOk(result)
        self.assertIn("--port %d" % port, server_args(self.city))

    def test_empty_agent_city_port_is_unset(self):
        self.assertOk(self.city_run("start", extra={"AGENT_CITY_PORT": ""}))
        self.assertIn("--port %d" % self.port, server_args(self.city))

    def test_bad_agent_city_port(self):
        for bad in ("abc", "80", "70000", "47 77", "-1"):
            with self.subTest(value=bad):
                result = self.city_run("start", extra={"AGENT_CITY_PORT": bad})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("AGENT_CITY_PORT", result.stdout + result.stderr)
                self.assertIsNone(server_pid(self.city), "nothing may be started")

    def test_port_held_by_another_program(self):
        busy = socket.socket()
        busy.bind(("127.0.0.1", self.port))
        busy.listen(1)
        self.addCleanup(busy.close)
        result = self.city_run("start")
        out = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already in use", out)
        self.assertIn(str(self.port), out)
        self.assertIn("AGENT_CITY_PORT", out)
        pid = server_pid(self.city)
        self.assertFalse(pid is not None and _alive(pid), "no city may be left running")

    def test_a_city_already_running_says_so(self):
        self.assertOk(self.city_run("start"))
        again = self.city_run("start")
        self.assertOk(again)
        self.assertIn("CITY: http://127.0.0.1:%d" % self.port, again.stdout)
        self.assertIn("already running", again.stdout)
        self.assertIn("stop", again.stdout.split("already running", 1)[1])


class TestAssetVersion(ServerCase):
    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.base, "cityhome")
        self.world = os.path.join(self.home, "world.json")
        self.assets = os.path.join(self.base, "assets")
        os.makedirs(os.path.join(self.assets, "pets"))
        with open(os.path.join(self.assets, "pets", "a.glb"), "wb") as fh:
            fh.write(b"glTF")

    def test_version_follows_the_files(self):
        v1 = ac.asset_version(self.assets)
        self.assertRegex(v1, r"^[0-9a-f]{8,}$")
        self.assertEqual(ac.asset_version(self.assets), v1)
        with open(os.path.join(self.assets, "pets", "b.glb"), "wb") as fh:
            fh.write(b"x")
        v2 = ac.asset_version(self.assets)
        self.assertNotEqual(v2, v1)
        with open(os.path.join(self.assets, "pets", "a.glb"), "wb") as fh:
            fh.write(b"glTF-2")
        self.assertNotEqual(ac.asset_version(self.assets), v2)

    def test_page_and_cache_headers(self):
        page = os.path.join(self.base, "page.html")
        with open(page, "w") as fh:
            fh.write("<script src=\"assets/pets/a.glb?v=__CITY_ASSET_V__\"></script>")
        self.start("--idle-sec", "60", "--world", self.world, "--assets", self.assets, "--page", page)
        status, headers, body = self.get("/")
        v = ac.asset_version(self.assets)
        self.assertIn(("?v=" + v).encode(), body)
        self.assertNotIn(b"__CITY_ASSET_V__", body)
        status, headers, body = self.get("/assets/pets/a.glb?v=" + v)
        self.assertEqual((status, body), (200, b"glTF"))
        self.assertEqual(headers.get("Cache-Control"), "max-age=31536000, immutable")
        for path in ("/assets/pets/a.glb", "/assets/pets/a.glb?v=old"):
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertEqual(headers.get("Cache-Control"), "no-cache")


BIN = os.path.join(ROOT, "bin")


SERVER_chat = os.path.join(BIN, "agent_city.py")


REPO = "/r/shop/.git"


def line_chat(ev, sid, aid="", role="", tool="Read", at="", repo=REPO):
    return {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": "shop", "role": role,
            "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}


class SayCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_say_")
        self.dir = os.path.join(self.base, "city")
        os.makedirs(self.dir)
        with open(os.path.join(self.dir, "on"), "w") as fh:
            fh.write("1 1\n")
        self.chat = os.path.join(self.dir, "chat.jsonl")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def say(self, payload, **env_extra):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE"}
        env.update(AGENT_CITY_DIR=self.dir, HOME=self.base)
        env.update(env_extra)
        data = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
        if isinstance(data, str):
            data = data.encode("utf-8")
        return subprocess.run([sys.executable, SERVER_chat, "say"], input=data, capture_output=True, env=env,
                              timeout=20)

    def lines(self):
        try:
            with open(self.chat, encoding="utf-8") as fh:
                return [json.loads(x) for x in fh if x.strip()]
        except FileNotFoundError:
            return []


class ChatServerCase(ServerCase):
    def token(self):
        with open(os.path.join(self.dir, "token")) as fh:
            return fh.read().strip()

    def call(self, method, path, body=None, token=True, origin=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        headers = {}
        if token:
            headers["X-City-Token"] = self.token()
        if origin:
            headers["Origin"] = "http://127.0.0.1:%d" % self.port
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(raw or b"null")
        except ValueError:
            return resp.status, None

    def chat_line(self, obj):
        with open(os.path.join(self.dir, "chat.jsonl"), "a") as fh:
            fh.write(json.dumps(obj) + "\n")

    def tm_session(self, sid="tm1"):
        ev = {"ev": "UserPromptSubmit", "sid": sid, "aid": "", "at": "", "tool": "", "nt": "", "proj": "shop",
              "role": "task-manager", "desc": "", "sub": "", "q": "", "klen": "", "repo": REPO, "kind": ""}
        self.append(json.dumps(ev) + "\n")
        ev["ev"] = "Stop"
        self.append(json.dumps(ev) + "\n")


class TestSay(SayCase):
    def test_prompt_reply_and_subagent_reply(self):
        r1 = self.say({"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "修一下 <b>登录</b>",
                       "transcript_path": "/nope"})
        r2 = self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "修好了"})
        r3 = self.say({"hook_event_name": "SubagentStop", "session_id": "s1", "agent_id": "a9",
                       "last_assistant_message": "slice done"})
        for r in (r1, r2, r3):
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, b"", "say must print nothing on stdout")
        got = [(x["sid"], x["aid"], x["kind"], x["text"]) for x in self.lines()]
        self.assertEqual(got, [("s1", "", "prompt", "修一下 <b>登录</b>"), ("s1", "", "reply", "修好了"),
                               ("s1", "a9", "reply", "slice done")])
        for x in self.lines():
            self.assertIsInstance(x["at"], (int, float))
            self.assertGreater(x["at"], time.time() - 60)

    def test_long_text_is_cut(self):
        self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "x" * 10000})
        text = self.lines()[0]["text"]
        self.assertEqual(text, "x" * ac.CHAT_TEXT_MAX + "…")

    def test_nothing_written(self):
        cases = {
            "blank": {"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "   "},
            "missing": {"hook_event_name": "Stop", "session_id": "s1"},
            "other event": {"hook_event_name": "PreToolUse", "session_id": "s1", "prompt": "x"},
            "no sid": {"hook_event_name": "Stop", "last_assistant_message": "x"},
        }
        for name, payload in cases.items():
            with self.subTest(case=name):
                r = self.say(payload)
                self.assertEqual((r.returncode, r.stdout), (0, b""))
        for raw in (b"", b"not json", b"[1, 2]"):
            with self.subTest(raw=raw):
                r = self.say(raw)
                self.assertEqual((r.returncode, r.stdout), (0, b""))
        self.assertEqual(self.lines(), [])

    def test_city_off_or_cloud_writes_nothing(self):
        r = self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "x"},
                     CLAUDE_CODE_REMOTE="true")
        self.assertEqual((r.returncode, r.stdout), (0, b""))
        os.remove(os.path.join(self.dir, "on"))
        r = self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "x"})
        self.assertEqual((r.returncode, r.stdout), (0, b""))
        self.assertEqual(self.lines(), [])

    def test_the_file_is_private_and_appended_in_one_write(self):
        self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "ok"})
        self.assertEqual(os.stat(self.chat).st_mode & 0o777, 0o600)
        import inspect
        # session-cleanup S1: the hook writes through the one locked writer, chat_append
        self.assertIn("chat_append(", inspect.getsource(ac._cmd_say_impl))
        src = inspect.getsource(ac.chat_append) + inspect.getsource(ac._append_private_jsonl)
        self.assertIn("os.O_APPEND", src)
        self.assertIn("os.write(", src)

    def test_never_reads_the_transcript(self):
        tpath = os.path.join(self.base, "t.jsonl")
        with open(tpath, "w") as fh:
            fh.write('{"message": "SECRET-TRANSCRIPT-7731"}\n')
        self.say({"hook_event_name": "Stop", "session_id": "s1", "last_assistant_message": "ok",
                  "transcript_path": tpath})
        with open(self.chat, encoding="utf-8") as fh:
            self.assertNotIn("SECRET-TRANSCRIPT-7731", fh.read())
        import inspect
        self.assertNotIn("transcript_path", inspect.getsource(ac.cmd_say))


class TestChatHttp(ChatServerCase):
    def test_view_send_and_next(self):
        self.start()
        self.tm_session()
        self.chat_line({"sid": "tm1", "aid": "", "kind": "reply", "text": "hello from tm1", "at": time.time()})
        self.assertTrue(wait_for(lambda: self.call("GET", "/api/chat?to=s:tm1")[0] == 200
                                 and self.call("GET", "/api/chat?to=s:tm1")[1]["entries"]),
                        "the chat.jsonl line never reached the server")
        status, body = self.call("GET", "/api/chat?to=s:tm1")
        self.assertEqual([e["text"] for e in body["entries"]], ["hello from tm1"])
        status, body = self.call("POST", "/api/chat/send", {"to": "s:tm1", "text": "go on"})
        self.assertEqual((status, body["state"]), (200, "queued"))
        status, got = self.call("GET", "/api/chat/next?sid=tm1&watcher=w1&timeout=2")
        self.assertEqual((status, got["state"], got["text"]), (200, "message", "go on"))

    def test_gates(self):
        self.start()
        self.tm_session()
        self.assertEqual(self.call("GET", "/api/chat?to=s:tm1", token=False)[0], 403)
        self.assertEqual(self.call("POST", "/api/chat/send", {"to": "s:tm1", "text": "x"}, token=False)[0], 403)
        self.assertEqual(self.call("POST", "/api/chat/send", {"to": "s:tm1", "text": "x"}, origin=False)[0], 403)
        self.assertEqual(self.call("GET", "/api/chat/next?sid=tm1&watcher=w&timeout=0", token=False)[0], 403)


class TestWaitingSessionsKeepTheCityUp(ChatServerCase):
    def test_a_waiting_session_keeps_the_server_up(self):
        proc = self.start("--idle-sec", "2")
        self.tm_session()
        env = dict(os.environ, AGENT_CITY_DIR=self.dir, AGENT_ROLE="task-manager",
                   AGENT_CITY_HOME=os.path.join(self.base, "cityhome"))
        path = os.path.join(self.base, "hook-idle.json")
        with open(path, "w") as fh:
            json.dump({"hook_event_name": "Stop", "session_id": "tm1"}, fh)
        with open(path, "rb") as stdin:
            watcher = subprocess.Popen([sys.executable, SERVER_chat, "chat-watch", "--max-wait-sec", "7"],
                                       stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        time.sleep(5)
        self.assertIsNone(proc.poll(), "the server stopped while a session waited to be talked to")
        watcher.communicate(timeout=30)
        self.assertTrue(wait_for(lambda: proc.poll() is not None, timeout=20),
                        "no page and no waiting session: the server must still stop by itself")

    def test_delivered_owner_lines_are_private_too(self):
        base = tempfile.mkdtemp(prefix="city_chatmode_")
        try:
            path = os.path.join(base, "chat.jsonl")
            st = ac.CityState(decisions_path=os.path.join(base, "d.jsonl"), world_path=None, chat_path=path)
            st.feed_line(line_chat("UserPromptSubmit", "tm1", role="task-manager"), time.monotonic())
            st.feed_line(line_chat("Stop", "tm1", role="task-manager"), time.monotonic())
            st.chat_send("s:tm1", "hi", 0)
            self.assertEqual(st.chat_next("tm1", "w1", 0)["state"], "message")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        finally:
            shutil.rmtree(base, ignore_errors=True)


class TestChatWatch(ChatServerCase):
    def watch(self, sid="tm1", wait="3"):
        # The hook input comes from a file: closing a stdin PIPE by hand and
        # then calling communicate() raises "flush of closed file" on 3.11.
        env = dict(os.environ, AGENT_CITY_DIR=self.dir, AGENT_ROLE="task-manager",
                   AGENT_CITY_HOME=os.path.join(self.base, "cityhome"))
        path = os.path.join(self.base, "hook-%s.json" % sid)
        with open(path, "w") as fh:
            json.dump({"hook_event_name": "Stop", "session_id": sid}, fh)
        with open(path, "rb") as stdin:
            return subprocess.Popen([sys.executable, SERVER_chat, "chat-watch", "--max-wait-sec", wait],
                                    stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

    def test_wakes_the_session_with_the_owner_text(self):
        self.start()
        self.tm_session()
        self.assertTrue(wait_for(lambda: self.call("GET", "/api/chat?to=s:tm1")[0] == 200))
        proc = self.watch(wait="20")
        time.sleep(0.5)
        self.call("POST", "/api/chat/send", {"to": "s:tm1", "text": "请先跑一下测试 7731"})
        out, err = proc.communicate(timeout=25)
        self.assertEqual(proc.returncode, 2, err)
        self.assertIn("请先跑一下测试 7731", err.decode())
        self.assertIn("city page", err.decode())

    def test_no_message_no_wake(self):
        self.start()
        self.tm_session()
        proc = self.watch(wait="2")
        out, err = proc.communicate(timeout=20)
        self.assertEqual((proc.returncode, err), (0, b""))

    def test_no_server_no_wake(self):
        os.makedirs(self.dir, exist_ok=True)
        proc = self.watch(wait="2")
        out, err = proc.communicate(timeout=20)
        self.assertEqual((proc.returncode, err), (0, b""))


def line_delivery(ev, sid, role="", repo=REPO):
    return {"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "Read", "nt": "", "proj": "shop",
            "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "ask": "",
            "wt": "", "file": "", "tp": "", "pid": ""}


class TestServerDecisionsHome(ServerCase):
    def test_a_server_without_decisions_writes_under_agent_city_home(self):
        fake_home = os.path.join(self.base, "fakehome")
        os.makedirs(fake_home)
        city_home = os.path.join(self.base, "cityhome")
        env = dict(os.environ, HOME=fake_home, AGENT_CITY_HOME=city_home)
        proc = subprocess.Popen([sys.executable, SERVER, "serve", "--dir", self.dir, "--port", "0",
                                 "--idle-sec", "60"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=env, cwd=self.base)
        self.procs.append(proc)
        self.assertTrue(wait_for(lambda: (self.on() or (0,))[0] == proc.pid), "the server never came up")
        token = open(os.path.join(self.dir, "token")).read().strip()
        for ev in ("UserPromptSubmit", "Stop"):
            self.append(json.dumps(dict(line_delivery(ev, "tm1", "task-manager"), repo="")) + "\n")
        import http.client

        def call(method, path, body=None):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
            headers = {"X-City-Token": token, "Origin": "http://127.0.0.1:%d" % self.port}
            data = json.dumps(body).encode() if body is not None else None
            if data:
                headers["Content-Type"] = "application/json"
            conn.request(method, path, body=data, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            conn.close()
            return resp.status, json.loads(raw or b"null")

        self.assertTrue(wait_for(lambda: call("GET", "/api/chat?to=s:tm1")[0] == 200), "tm1 never showed up")
        waiter = {}
        t = threading.Thread(target=lambda: waiter.update(r=call("GET", "/api/chat/next?sid=tm1&watcher=w&timeout=5")))
        t.start()
        time.sleep(0.3)
        call("POST", "/api/chat/send", {"to": "s:tm1", "text": "home check"})
        t.join(10)
        self.assertEqual(waiter["r"][1].get("text"), "home check")
        self.assertTrue(wait_for(lambda: os.path.exists(os.path.join(city_home, "decisions.jsonl"))))
        self.assertFalse(os.path.exists(os.path.join(fake_home, ".claude")), "nothing under HOME")


class TestLangFlag(ServerCase):
    def test_default_is_zh(self):
        self.start()
        body = self.get("/")[2].decode("utf-8")
        self.assertNotIn("__CITY_LANG__", body)
        self.assertRegex(body, r"const LANG = 'zh'")

    def test_en(self):
        self.start("--idle-sec", "60", "--lang", "en")
        self.assertRegex(self.get("/")[2].decode("utf-8"), r"const LANG = 'en'")

    def test_unknown_counts_as_zh(self):
        self.start("--idle-sec", "60", "--lang", "fr")
        self.assertRegex(self.get("/")[2].decode("utf-8"), r"const LANG = 'zh'")


class TestLangFromConf(unittest.TestCase):
    def test_start_passes_language(self):
        with open(os.path.join(BIN, "agent-city.sh"), encoding="utf-8") as fh:
            text = fh.read()
        serve = text[text.index('"$SERVER" serve'):]
        serve = serve[:serve.index("&\n")]
        self.assertIn('--lang "$language"', serve)  # conf_read sets every agent.conf key, language too


QS2 = QS + [{"question": "Which scope?", "header": "Scope",
             "options": [{"label": "Questions", "description": "first"},
                         {"label": "Both", "description": "all"}],
             "multiSelect": False}]


def perm_body(sid="s1", aid="", tool="Bash", command="rm -rf build/", repo=SHOP,
              role="worker", **extra):
    inp = {"command": command, "description": "clean the build"} if tool == "Bash" else extra.pop("input")
    return {"sid": sid, "aid": aid, "at": "worker" if aid else "", "role": role,
            "cwd": "/r/shop", "repo": repo, "tool": tool, "input": inp}


def hook_payload(cwd, tool="Bash", tool_input=None, sid="sess-9", aid=None):
    data = {"session_id": sid, "transcript_path": "/x/t.jsonl", "cwd": cwd,
            "permission_mode": "default"}
    if aid:
        data["agent_id"] = aid
        data["agent_type"] = "worker"
    data.update({"hook_event_name": "PermissionRequest", "tool_name": tool,
                 "tool_input": tool_input or {"command": "touch a.txt", "description": "make a file"},
                 "permission_suggestions": []})
    return json.dumps(data).encode("utf-8")


class TestConnection(InteractCase):
    def test_token_compare_is_constant_time(self):
        with open(SERVER) as fh:
            self.assertTrue("hmac.compare_digest" in fh.read(), "use hmac.compare_digest for the token")

    def test_a_refused_body_does_not_spoil_the_next_request(self):
        self.start()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        body = json.dumps(perm_body()).encode("utf-8")
        conn.request("POST", "/api/ask", body=body, headers={"Content-Type": "application/json"})
        first = conn.getresponse()
        first.read()
        self.assertEqual(first.status, 403)
        conn.request("GET", "/api/asks", headers={"X-City-Token": self.token()})
        second = conn.getresponse()
        self.assertEqual(second.status, 200, second.read())
        conn.close()


class TestPermission(InteractCase):
    def test_goes_to_the_owner_at_once(self):
        self.start()
        sse = self.sse()
        self.gov_next()  # a governor is around: still not its job
        ask_id = self.ask(perm_body())
        v = self.view(ask_id)
        self.assertEqual((v["kind"], v["phase"], v["why"]), ("permission", "owner", "permission"))
        self.assertEqual(v["tool"], "Bash")
        self.assertEqual(v["what"], "rm -rf build/")
        self.assertEqual(v["detail"]["command"], "rm -rf build/")
        self.assertEqual(v["detail"]["description"], "clean the build")
        self.assertEqual(v["detail"]["cwd"], "/r/shop")
        self.assertEqual(v["agent"], "s:s1")
        self.assertTrue(wait_for(lambda: sse.events("ask")))
        self.assertEqual(sse.events("ask")[0]["id"], ask_id)

    def test_never_given_to_the_governor(self):
        self.start()
        self.gov_next()
        self.ask(perm_body())
        self.assertEqual(self.gov_next(timeout=1)["state"], "none")

    def test_owner_allows(self):
        self.start()
        sse = self.sse()
        ask_id = self.ask(perm_body())
        status, _, out = self.decide({"id": ask_id, "verb": "allow"})
        self.assertEqual((status, out), (200, {"ok": True}))
        self.assertIsNone(self.view(ask_id))
        closed = wait_for(lambda: sse.events("ask_closed"))
        self.assertEqual({k: closed[0][k] for k in ("id", "by", "verb", "tool", "what", "kind")},
                         {"id": ask_id, "by": "owner", "verb": "allow", "tool": "Bash",
                          "what": "rm -rf build/", "kind": "permission"})
        wait = self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2]
        self.assertEqual((wait["state"], wait["by"], wait["verb"]), ("closed", "owner", "allow"))

    def test_owner_denies_with_a_reason(self):
        self.start()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.decide({"id": ask_id, "verb": "deny", "reason": "keep dist/"})[0], 200)
        wait = self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2]
        self.assertEqual((wait["verb"], wait["reason"]), ("deny", "keep dist/"))

    def test_first_answer_wins(self):
        self.start()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.decide({"id": ask_id, "verb": "deny"})[0], 200)
        status, _, out = self.decide({"id": ask_id, "verb": "allow"})
        self.assertEqual(status, 409)
        self.assertEqual(out["by"], "owner")
        self.assertEqual(self.api("POST", "/api/closed", {"id": ask_id})[0], 409)
        self.assertEqual(len(self.decisions_lines()), 1)
        self.assertEqual(self.decisions_lines()[0]["verb"], "deny")

    def test_bad_decisions(self):
        self.start()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.decide({"id": ask_id, "verb": "maybe"})[0], 400)
        self.assertEqual(self.decide({"id": ask_id, "verb": "deny", "reason": "x" * 501})[0], 400)
        self.assertEqual(self.decide({"id": "nope", "verb": "allow"})[0], 404)
        self.assertIsNotNone(self.view(ask_id))

    def test_what_for_files_and_urls(self):
        self.start()
        e = self.ask(perm_body(tool="Edit", input={"file_path": "/r/shop/a.py", "old_string": "a",
                                                   "new_string": "b"}))
        w = self.ask(perm_body(tool="WebFetch", input={"url": "https://example.com/x", "prompt": "p"}))
        self.assertEqual(self.view(e)["what"], "/r/shop/a.py")
        self.assertEqual(self.view(e)["detail"]["file_path"], "/r/shop/a.py")
        self.assertEqual(self.view(w)["what"], "https://example.com/x")

    def test_long_texts_are_cut(self):
        self.start()
        ask_id = self.ask(perm_body(command="echo " + "x" * 5000))
        v = self.view(ask_id)
        self.assertLessEqual(len(v["what"]), 200)
        self.assertLessEqual(len(v["detail"]["command"]), 2000)
        self.assertTrue(v["detail"]["command"].startswith("echo xxx"))

    def test_at_most_fifty_open(self):
        self.start()
        for i in range(50):
            self.ask(perm_body(sid="s%d" % i))
        self.assertEqual(self.api("POST", "/api/ask", perm_body(sid="s99"))[0], 429)


class TestQuestion(InteractCase):
    def test_no_governor_goes_to_the_owner(self):
        self.start()
        ask_id = self.ask(q_body())
        v = self.view(ask_id)
        self.assertEqual((v["kind"], v["phase"], v["why"]), ("question", "owner", "no-governor"))
        self.assertEqual(v["questions"], QS)
        self.assertEqual(v["what"], "Which port?")

    def test_governor_of_another_repo_does_not_count(self):
        self.start()
        self.gov_next(repo="/r/other/.git")
        self.assertEqual(self.view(self.ask(q_body()))["phase"], "owner")

    def test_the_governor_asking_goes_to_the_owner(self):
        self.start()
        self.gov_next(sid="gs")
        self.assertEqual(self.view(self.ask(q_body(sid="gs", role="")))["why"], "no-governor")

    def test_governor_gets_it_and_answers(self):
        self.start()
        sse = self.sse()
        self.gov_next()
        ask_id = self.ask(q_body())
        v = self.view(ask_id)
        self.assertEqual((v["phase"], v["why"], v["wait"]), ("governor", "", 60))
        self.assertGreater(v["left"], 50)
        got = self.gov_next(timeout=5)
        self.assertEqual(got["state"], "ask")
        self.assertEqual(got["ask"]["id"], ask_id)
        self.assertEqual(got["ask"]["questions"], QS)
        self.assertEqual(self.gov_next(timeout=1)["state"], "none", "given twice")
        status, _, _ = self.api("POST", "/api/gov/answer", {"id": ask_id, "texts": ["4791"]})
        self.assertEqual(status, 200)
        closed = wait_for(lambda: sse.events("ask_closed"))[0]
        self.assertEqual((closed["by"], closed["verb"], closed["text"]), ("governor", "answer", "4791"))
        wait = self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2]
        self.assertEqual(wait["answers"], {"Which port?": "4791"})
        line = self.decisions_lines()[0]
        self.assertEqual((line["by"], line["verb"], line["text"]), ("governor", "answer", "4791"))

    def test_governor_answer_count_must_match(self):
        self.start()
        self.gov_next()
        ask_id = self.ask(q_body(questions=QS2))
        self.assertEqual(self.api("POST", "/api/gov/answer", {"id": ask_id, "texts": ["4791"]})[0], 400)
        self.assertEqual(self.api("POST", "/api/gov/answer",
                                  {"id": ask_id, "texts": ["4791", "Both"]})[0], 200)
        wait = self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2]
        self.assertEqual(wait["text"], "4791；Both")

    def test_governor_can_pass(self):
        self.start()
        sse = self.sse()
        self.gov_next()
        ask_id = self.ask(q_body())
        self.assertEqual(self.api("POST", "/api/gov/pass", {"id": ask_id})[0], 200)
        v = self.view(ask_id)
        self.assertEqual((v["phase"], v["why"], v["left"]), ("owner", "pass", 0))
        phase = wait_for(lambda: sse.events("ask_phase"))[0]
        self.assertEqual((phase["id"], phase["why"]), (ask_id, "pass"))
        self.assertEqual(self.api("POST", "/api/gov/pass", {"id": ask_id})[0], 409)
        self.assertEqual(self.decisions_lines()[0]["verb"], "pass")

    def test_owner_answers_every_question(self):
        self.start()
        ask_id = self.ask(q_body(questions=QS2))
        self.assertEqual(self.decide({"id": ask_id, "answers": {"Which port?": "4791"}})[0], 400)
        self.assertEqual(self.decide({"id": ask_id, "answers": {"Which port?": "4791",
                                                                "Which scope?": " "}})[0], 400)
        self.assertIsNotNone(self.view(ask_id))
        ok = self.decide({"id": ask_id, "answers": {"Which port?": "4791", "Which scope?": "only questions"}})
        self.assertEqual(ok[0], 200)
        wait = self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2]
        self.assertEqual((wait["by"], wait["verb"]), ("owner", "answer"))
        self.assertEqual(wait["answers"], {"Which port?": "4791", "Which scope?": "only questions"})

    def test_the_owner_may_answer_during_the_governor_time(self):
        self.start()
        self.gov_next()
        ask_id = self.ask(q_body())
        self.assertEqual(self.decide({"id": ask_id, "answers": {"Which port?": "4792"}})[0], 200)
        self.assertEqual(self.api("POST", "/api/gov/answer", {"id": ask_id, "texts": ["4791"]})[0], 409)

    def test_governor_never_touches_a_permission(self):
        self.start()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.api("POST", "/api/gov/answer", {"id": ask_id, "texts": ["yes"]})[0], 403)
        self.assertEqual(self.api("POST", "/api/gov/pass", {"id": ask_id})[0], 403)
        self.assertIsNotNone(self.view(ask_id))
        self.assertEqual(self.decisions_lines(), [])


class TestGovernorTimeout(InteractCase):
    GOV_WAIT = "1"

    def test_no_answer_in_time_goes_to_the_owner(self):
        self.start()
        sse = self.sse()
        self.gov_next()
        ask_id = self.ask(q_body())
        self.assertEqual(self.view(ask_id)["phase"], "governor")
        phase = wait_for(lambda: sse.events("ask_phase"), timeout=5)
        self.assertTrue(phase, "never left the governor")
        self.assertEqual((phase[0]["id"], phase[0]["phase"], phase[0]["why"], phase[0]["wait"]),
                         (ask_id, "owner", "timeout", 1))
        self.assertEqual(self.view(ask_id)["why"], "timeout")
        self.assertEqual(self.decisions_lines(), [], "a timeout is not a decision")


class TestGovernorsCount(InteractCase):
    def test_count_in_the_snapshot_and_on_change(self):
        self.start()
        sse = self.sse()
        self.assertEqual(sse.messages[0]["governors"], 0)
        self.gov_next(sid="gs")
        got = wait_for(lambda: sse.events("governors"))
        self.assertTrue(got, "no governors event when a governor showed up")
        self.assertEqual(got[-1]["count"], 1)
        self.gov_next(sid="gs")
        time.sleep(0.5)
        self.assertEqual(len(sse.events("governors")), 1, "same governor again is no change")
        self.append(json.dumps({"ev": "SessionEnd", "sid": "gs", "aid": "", "at": "", "tool": "",
                                "nt": "", "proj": "shop", "role": "", "desc": "", "sub": "",
                                "q": "", "klen": ""}) + "\n")
        self.assertTrue(wait_for(lambda: len(sse.events("governors")) == 2))
        self.assertEqual(sse.events("governors")[-1]["count"], 0)
        late = self.sse()
        self.assertEqual(late.messages[0]["governors"], 0)


class TestTerminal(InteractCase):
    def event(self, ev="PostToolUse", sid="s1", aid="", tool="Bash", klen=""):
        self.append(json.dumps({"ev": ev, "sid": sid, "aid": aid, "at": "worker" if aid else "",
                                "tool": tool, "nt": "", "proj": "shop", "role": "worker",
                                "desc": "", "sub": "", "q": "", "klen": klen}) + "\n")

    def test_hook_says_closed(self):
        self.start()
        sse = self.sse()
        ask_id = self.ask(perm_body())
        self.assertEqual(self.api("POST", "/api/closed", {"id": ask_id})[0], 200)
        closed = wait_for(lambda: sse.events("ask_closed"))[0]
        self.assertEqual((closed["by"], closed["verb"]), ("terminal", "closed"))
        self.assertEqual(self.decide({"id": ask_id, "verb": "allow"})[0], 409)
        self.assertEqual(self.decisions_lines()[0]["by"], "terminal")

    def test_terminal_approved_first(self):
        self.start()
        sse = self.sse()
        ask_id = self.ask(perm_body(sid="s1", aid="a1"))
        self.event(sid="s1", aid="a1", tool="Bash", klen=str(len("rm -rf build/")))
        closed = wait_for(lambda: sse.events("ask_closed"))
        self.assertTrue(closed, "PostToolUse did not close it")
        self.assertEqual((closed[0]["id"], closed[0]["by"], closed[0]["verb"]), (ask_id, "terminal", "allow"))

    def test_other_command_does_not_close_it(self):
        self.start()
        ask_id = self.ask(perm_body(sid="s1", aid="a1"))
        self.event(sid="s1", aid="a1", tool="Bash", klen="3")
        self.event(sid="s1", aid="a2", tool="Bash", klen=str(len("rm -rf build/")))
        self.event(sid="s1", aid="a1", tool="Edit")
        # was sleep(1.0): the city has read all three lines (feed_line counts under the same lock)
        wait_for(lambda: self.health()["lines"] == 3, timeout=10)
        self.assertIsNotNone(self.view(ask_id))

    def test_escaped_length_is_compared(self):
        self.start()
        cmd = 'echo "hé"'
        ask_id = self.ask(perm_body(sid="s1", command=cmd))
        escaped = json.dumps(cmd, ensure_ascii=False)[1:-1].encode("utf-8")
        self.event(sid="s1", tool="Bash", klen=str(len(escaped)))
        self.assertTrue(wait_for(lambda: self.view(ask_id) is None), "same escaped length did not match")

    def test_terminal_answered_a_question(self):
        self.start()
        sse = self.sse()
        ask_id = self.ask(q_body(sid="s2"))
        self.event(sid="s2", tool="AskUserQuestion")
        closed = wait_for(lambda: sse.events("ask_closed"))
        self.assertTrue(closed)
        self.assertEqual((closed[0]["id"], closed[0]["by"], closed[0]["verb"], closed[0]["text"]),
                         (ask_id, "terminal", "answer", ""))


class TestWaitAndViews(InteractCase):
    def test_wait_open_then_unknown(self):
        self.start()
        ask_id = self.ask(perm_body())
        start = time.monotonic()
        self.assertEqual(self.api("GET", "/api/wait?id=%s&timeout=1" % ask_id)[2], {"state": "open"})
        self.assertGreaterEqual(time.monotonic() - start, 0.8)
        self.assertEqual(self.api("GET", "/api/wait?id=zz&timeout=1")[0], 404)

    def test_wait_returns_as_soon_as_it_is_decided(self):
        self.start()
        ask_id = self.ask(perm_body())
        threading.Timer(0.5, lambda: self.decide({"id": ask_id, "verb": "allow"})).start()
        start = time.monotonic()
        out = self.api("GET", "/api/wait?id=%s&timeout=20" % ask_id)[2]
        self.assertEqual(out["state"], "closed")
        self.assertLess(time.monotonic() - start, 5)

    def test_snapshot_and_health_carry_the_open_asks(self):
        self.start()
        ask_id = self.ask(perm_body())
        sse = self.sse()
        snap = sse.messages[0]
        self.assertEqual(snap["type"], "snapshot")
        self.assertEqual([a["id"] for a in snap["asks"]], [ask_id])
        health = self.health()
        self.assertEqual((health["asks"], health["gov_wait_sec"], health["governors"]), (1, 60, 0))
        self.gov_next()
        self.assertEqual(self.health()["governors"], 1)

    def test_known_agent_gets_its_city_name(self):
        self.start()
        self.append(json.dumps({"ev": "SubagentStart", "sid": "s1", "aid": "a7", "at": "worker",
                                "tool": "", "nt": "", "proj": "shop", "role": "", "desc": "",
                                "sub": "", "q": ""}) + "\n")
        self.assertTrue(wait_for(lambda: self.health()["agents"] == 1))
        v = self.view(self.ask(perm_body(sid="s1", aid="a7")))
        self.assertEqual((v["agent"], v["label"]), ("a7", "worker"))


class TestAskHookOff(AskHookCase):
    def test_no_city_no_output_at_once(self):
        start = time.monotonic()
        proc = self.hook(hook_payload(self.work))
        code, out, err = self.finish(proc)
        self.assertEqual((code, out, err), (0, b"", b""))
        self.assertLess(time.monotonic() - start, 2.0)

    def test_dead_pid(self):
        os.makedirs(self.dir)
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        with open(os.path.join(self.dir, "on"), "w") as fh:
            fh.write("%d %d\n" % (dead.pid, free_port()))
        with open(os.path.join(self.dir, "token"), "w") as fh:
            fh.write("x" * 40)
        code, out, err = self.finish(self.hook(hook_payload(self.work)))
        self.assertEqual((code, out, err), (0, b"", b""))

    def test_nobody_listening(self):
        os.makedirs(self.dir)
        with open(os.path.join(self.dir, "on"), "w") as fh:
            fh.write("%d %d\n" % (os.getpid(), free_port()))
        with open(os.path.join(self.dir, "token"), "w") as fh:
            fh.write("x" * 40)
        start = time.monotonic()
        code, out, err = self.finish(self.hook(hook_payload(self.work)))
        self.assertEqual((code, out, err), (0, b"", b""))
        self.assertLess(time.monotonic() - start, 3.0)


class TestAskHookOn(AskHookCase):
    def test_owner_allows(self):
        self.start()
        proc = self.hook(hook_payload(self.work))
        ask = self.first_ask()
        self.assertEqual(ask["what"], "touch a.txt")
        self.assertEqual(ask["label"], "worker")
        self.assertEqual(ask["repo"], os.path.realpath(self.work))
        self.decide({"id": ask["id"], "verb": "allow"})
        code, out, err = self.finish(proc)
        self.assertEqual((code, err), (0, b""))
        self.assertEqual(json.loads(out), {"hookSpecificOutput": {
            "hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}})
        self.assertEqual(out.count(b"\n"), 1)

    def test_owner_denies_with_a_reason(self):
        self.start()
        proc = self.hook(hook_payload(self.work))
        self.decide({"id": self.first_ask()["id"], "verb": "deny", "reason": "use tmp/ instead"})
        code, out, _ = self.finish(proc)
        decision = json.loads(out)["hookSpecificOutput"]["decision"]
        self.assertEqual(decision["behavior"], "deny")
        self.assertIn("use tmp/ instead", decision["message"])
        self.assertIn("owner", decision["message"])

    def test_owner_denies_without_a_reason(self):
        self.start()
        proc = self.hook(hook_payload(self.work))
        self.decide({"id": self.first_ask()["id"], "verb": "deny"})
        decision = json.loads(self.finish(proc)[1])["hookSpecificOutput"]["decision"]
        self.assertEqual(decision["behavior"], "deny")
        self.assertIn("owner", decision["message"])

    def test_a_question_gets_its_answers(self):
        self.start()
        proc = self.hook(hook_payload(self.work, tool="AskUserQuestion", tool_input={"questions": QS}))
        ask = self.first_ask()
        self.assertEqual(ask["kind"], "question")
        self.decide({"id": ask["id"], "answers": {"Which port?": "4791, but only today"}})
        decision = json.loads(self.finish(proc)[1])["hookSpecificOutput"]["decision"]
        self.assertEqual(decision["behavior"], "allow")
        self.assertEqual(decision["updatedInput"], {"questions": QS,
                                                    "answers": {"Which port?": "4791, but only today"}})

    def test_the_governor_answer_reaches_it(self):
        self.start()
        self.gov_next(sid="gov-1", repo=os.path.realpath(self.work))   # city-roles: gov-1 holds work's lock
        proc = self.hook(hook_payload(self.work, tool="AskUserQuestion", tool_input={"questions": QS}))
        ask = self.first_ask()
        self.assertEqual(ask["phase"], "governor")
        self.api("POST", "/api/gov/answer", {"id": ask["id"], "texts": ["4791"]})
        decision = json.loads(self.finish(proc)[1])["hookSpecificOutput"]["decision"]
        self.assertEqual(decision["updatedInput"]["answers"], {"Which port?": "4791"})

    def test_subagent_ask_names_the_subagent(self):
        self.start()
        self.hook(hook_payload(self.work, aid="a3"))
        self.assertEqual(self.first_ask()["agent"], "a3")

    def test_repo_is_the_git_common_dir(self):
        main = os.path.join(self.base, "main")
        os.makedirs(main)
        git = ["git", "-C", main, "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "x"], check=True)
        tree = os.path.join(self.base, "tree")
        subprocess.run(git + ["worktree", "add", "-q", tree], check=True)
        self.start()
        self.hook(hook_payload(tree))
        self.assertEqual(self.first_ask()["repo"], os.path.realpath(os.path.join(main, ".git")))

    def test_terminal_first_ends_it_quietly(self):
        self.start()
        proc = self.hook(hook_payload(self.work))
        self.api("POST", "/api/closed", {"id": self.first_ask()["id"]})
        code, out, err = self.finish(proc)
        self.assertEqual((code, out, err), (0, b"", b""))

    def test_sigterm_closes_it_in_the_city(self):
        self.start()
        sse = self.sse()
        proc = self.hook(hook_payload(self.work))
        ask_id = self.first_ask()["id"]
        proc.send_signal(signal.SIGTERM)
        code, out, err = self.finish(proc)
        self.assertEqual((code, out, err), (0, b"", b""))
        closed = wait_for(lambda: sse.events("ask_closed"))
        self.assertTrue(closed, "the city never heard the terminal took it")
        self.assertEqual((closed[0]["id"], closed[0]["by"], closed[0]["verb"]), (ask_id, "terminal", "closed"))

    def test_server_gone_ends_it_quietly(self):
        proc_srv = self.start()
        proc = self.hook(hook_payload(self.work))
        self.first_ask()
        proc_srv.terminate()
        start = time.monotonic()
        code, out, _ = self.finish(proc)
        self.assertEqual((code, out), (0, b""))
        self.assertLess(time.monotonic() - start, 10)

    def test_parent_gone_closes_it(self):
        self.start()
        sse = self.sse()
        env = dict(os.environ, AGENT_CITY_DIR=self.dir, AGENT_ROLE="worker")
        stdin_file = os.path.join(self.base, "req.json")
        with open(stdin_file, "wb") as fh:
            fh.write(hook_payload(self.work))
        # a parent that starts the hook and goes away, like a closed Claude Code
        parent = subprocess.Popen(["sh", "-c", '"$0" "$1" ask --max-wait-sec 60 <"$2" >/dev/null 2>&1 & sleep 1',
                                   sys.executable, SERVER, stdin_file], env=env)
        ask_id = self.first_ask()["id"]
        parent.wait(10)
        closed = wait_for(lambda: sse.events("ask_closed"), timeout=12)
        self.assertTrue(closed, "the hook outlived its parent")
        self.assertEqual((closed[0]["id"], closed[0]["by"], closed[0]["verb"]), (ask_id, "terminal", "closed"))

    def test_max_wait_gives_up_and_closes(self):
        self.start()
        proc = self.hook(hook_payload(self.work), "--max-wait-sec", "2")
        ask_id = self.first_ask()["id"]
        code, out, _ = self.finish(proc)
        self.assertEqual((code, out), (0, b""))
        self.assertIsNone(self.view(ask_id))


class TestGovWatch(AskHookCase):
    def watch(self, sid="gov-1", role=None, max_wait="20", cwd=None):
        env = dict(os.environ, AGENT_CITY_DIR=self.dir)
        env.pop("AGENT_ROLE", None)
        if role:
            env["AGENT_ROLE"] = role
        proc = subprocess.Popen([sys.executable, SERVER, "gov-watch", "--max-wait-sec", max_wait],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env)
        proc.stdin.write(stop_payload(cwd or self.work, sid))
        proc.stdin.close()
        self.hooks.append(proc)
        return proc

    def test_citizen_or_city_off_exits_at_once(self):
        code, out, err = self.finish(self.watch())
        self.assertEqual((code, out, err), (0, b"", b""))
        self.start()
        code, out, _ = self.finish(self.watch(role="worker"))
        self.assertEqual((code, out), (0, b""))

    def test_a_question_wakes_the_governor(self):
        self.start()
        proc = self.watch()
        self.assertTrue(wait_for(lambda: self.health()["governors"] == 1, timeout=5),
                        "the watcher never showed up as the governor")
        self.assertEqual(self.view(self.ask(q_body(repo=os.path.realpath(self.work))))["phase"], "governor")
        code, out, err = self.finish(proc)
        text = err.decode("utf-8")
        ask_id = self.asks()[0]["id"]
        self.assertEqual((code, out), (2, b""))
        self.assertIn("[agent-city]", text)
        self.assertIn(ask_id, text)
        self.assertIn("Which port?", text)
        self.assertIn("4791", text)
        self.assertIn("4792", text)
        self.assertIn("data", text)
        city_sh = os.path.join(ROOT, "bin", "agent-city.sh")
        self.assertIn("%s answer %s" % (city_sh, ask_id), text)
        self.assertIn("%s pass %s" % (city_sh, ask_id), text)
        self.assertNotIn("approve", text.lower())

    def test_permissions_never_wake_it(self):
        self.start()
        proc = self.watch(max_wait="3")
        wait_for(lambda: self.health()["governors"] == 1, timeout=5)   # was a sleep: the watcher is the governor now
        self.ask(perm_body(repo=os.path.realpath(self.work)))
        code, out, err = self.finish(proc)
        self.assertEqual((code, out, err), (0, b"", b""))

    def test_other_repo_questions_do_not_wake_it(self):
        self.start()
        proc = self.watch(max_wait="3")
        wait_for(lambda: self.health()["governors"] == 1, timeout=5)   # was a sleep: the watcher is the governor now
        self.ask(q_body(repo="/r/elsewhere/.git"))
        self.assertEqual(self.finish(proc)[0], 0)

    def test_second_watcher_replaces_the_first(self):
        self.start()
        first = self.watch()
        wait_for(lambda: self.health()["governors"] == 1, timeout=5)   # was a sleep: the watcher is the governor now
        second = self.watch()
        code, _, _ = self.finish(first, timeout=10)
        self.assertEqual(code, 0)
        self.assertIsNone(second.poll())

    def test_parent_gone_ends_the_watcher(self):
        self.start()
        env = dict(os.environ, AGENT_CITY_DIR=self.dir)
        env.pop("AGENT_ROLE", None)
        stdin_file = os.path.join(self.base, "stop.json")
        with open(stdin_file, "wb") as fh:
            fh.write(stop_payload(self.work, sid="gone-gov"))
        pid_file = os.path.join(self.base, "watcher.pid")
        parent = subprocess.Popen(["sh", "-c", '"$0" "$1" gov-watch --max-wait-sec 120 <"$2" >/dev/null 2>&1 & echo $! >"$3"; sleep 1',
                                   sys.executable, SERVER, stdin_file, pid_file], env=env)
        parent.wait(10)
        with open(pid_file) as fh:
            watcher_pid = int(fh.read())
        self.assertTrue(wait_for(lambda: not pid_alive(watcher_pid), timeout=12),
                        "the watcher outlived the governor session")

    def test_server_gone(self):
        srv = self.start()
        # max_wait 3, not the 20 of a plain watch: a watcher whose server is gone keeps looking for it
        # until its max wait is over (_watch_poll), and the test only needs it to end with 0
        proc = self.watch(max_wait="3")
        wait_for(lambda: self.health()["governors"] == 1, timeout=5)   # was a sleep: the watcher is the governor now
        srv.terminate()
        self.assertEqual(self.finish(proc)[0], 0)


class TestCityScriptVerbs(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.city = os.path.join(self.repo.base, "city")
        self.home = os.path.join(self.repo.base, "cityhome")
        self.port = free_port()
        self.repo.set_conf("city_port", str(self.port))
        # settings-configure: city_governor_wait_sec is a fixed constant (60)

    def tearDown(self):
        on = os.path.join(self.city, "on")
        if os.path.exists(on):
            try:
                with open(on) as fh:
                    os.kill(int(fh.read().split()[0]), signal.SIGTERM)
            except (OSError, ValueError, IndexError):
                pass
        super().tearDown()

    def city_run(self, *args):
        return self.repo.run("agent-city.sh", *args,
                             env={"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.home}, timeout=30)

    def api(self, method, path, body=None):
        with open(os.path.join(self.city, "token")) as fh:
            token = fh.read().strip()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        headers = {"X-City-Token": token}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        out = json.loads(resp.read())
        conn.close()
        return resp.status, out

    def started(self):
        result = self.city_run("start")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_start_passes_the_wait_and_the_log_path(self):
        self.started()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/health")
        self.assertEqual(json.loads(conn.getresponse().read())["gov_wait_sec"], 60)
        conn.close()
        ask_id = self.api("POST", "/api/ask", q_body())[1]["id"]
        self.assertEqual(self.city_run("answer", ask_id, "4791").returncode, 0)
        with open(os.path.join(self.home, "decisions.jsonl")) as fh:
            self.assertEqual(json.loads(fh.readline())["by"], "governor")

    def test_answer(self):
        self.started()
        ask_id = self.api("POST", "/api/ask", q_body(questions=QS2))[1]["id"]
        result = self.city_run("answer", ask_id, "4791", "only questions")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CITY: answered %s" % ask_id, result.stdout)
        again = self.city_run("answer", ask_id, "4792", "x")
        self.assertEqual(again.returncode, 1)
        self.assertIn("closed", again.stdout)
        self.assertIn("governor", again.stdout)

    def test_pass(self):
        self.started()
        self.api("GET", "/api/gov/next?sid=gs&repo=%s&watcher=w&timeout=0" % SHOP)
        ask_id = self.api("POST", "/api/ask", q_body())[1]["id"]
        result = self.city_run("pass", ask_id)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CITY: passed %s to the owner" % ask_id, result.stdout)
        self.assertEqual(self.api("GET", "/api/asks")[1]["asks"][0]["why"], "pass")

    def test_permissions_are_the_owners(self):
        self.started()
        ask_id = self.api("POST", "/api/ask", perm_body())[1]["id"]
        for verb in (["answer", ask_id, "yes"], ["pass", ask_id]):
            with self.subTest(verb=verb[0]):
                result = self.city_run(*verb)
                self.assertEqual(result.returncode, 1)
                self.assertIn("owner", result.stdout)
        self.assertEqual(len(self.api("GET", "/api/asks")[1]["asks"]), 1)

    def test_pending(self):
        self.started()
        self.assertIn("CITY: nothing waiting", self.city_run("pending").stdout)
        ask_id = self.api("POST", "/api/ask", perm_body())[1]["id"]
        out = self.city_run("pending").stdout
        self.assertIn(ask_id, out)
        self.assertIn("permission", out)
        self.assertIn("rm -rf build/", out)

    def test_unknown_id_and_not_running(self):
        result = self.city_run("answer", "a1", "x")
        self.assertEqual(result.returncode, 1)
        self.assertIn("CITY: not running", result.stdout)
        self.started()
        self.assertEqual(self.city_run("answer", "nope", "x").returncode, 1)

    def test_no_verb_approves(self):
        self.started()
        ask_id = self.api("POST", "/api/ask", perm_body())[1]["id"]
        for verb in ("approve", "allow", "deny"):
            with self.subTest(verb=verb):
                self.assertEqual(self.city_run(verb, ask_id).returncode, 2)
        help_text = self.city_run("-h").stdout.lower()
        for word in ("approve", "allow", "deny"):
            self.assertNotIn(word, help_text)
        self.assertEqual(len(self.api("GET", "/api/asks")[1]["asks"]), 1)


def tp_free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestServeStartDir(ServerCase):
    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.base, "cityhome")
        self.world = os.path.join(self.home, "world.json")

    def serve(self, start):
        self.start("--idle-sec", "60", "--world", self.world, "--start-dir", start)
        return self.sse().messages[0]

    def test_a_repo_dir_shows_its_territory_before_any_event(self):
        repo = make_repo(os.path.join(self.base, "shop"), {"a.py": "x\n" * 30})
        snap = self.serve(os.path.join(self.base, "shop"))
        self.assertEqual([t["name"] for t in snap["world"]["repos"]], ["shop"])
        self.assertEqual(snap["gov"]["terr"], ac.territory_id(repo))
        with open(self.world) as fh:
            self.assertEqual(list(json.load(fh)["territories"]), [repo])

    def test_a_plain_folder_shows_its_territory(self):
        plain = os.path.join(self.base, "notes")
        os.makedirs(plain)
        snap = self.serve(plain)
        self.assertEqual([t["name"] for t in snap["world"]["repos"]], ["notes"])
        with open(self.world) as fh:
            self.assertEqual(list(json.load(fh)["territories"]), [os.path.realpath(plain)])

    def test_no_start_dir_shows_nothing(self):
        snap = self.serve("")
        self.assertEqual(snap["world"]["repos"], [])


class TestCityScriptStartDir(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.city = os.path.join(self.repo.base, "city")
        self.home = os.path.join(self.repo.base, "cityhome")
        self.repo.set_conf("city_port", str(tp_free_port()))

    def tearDown(self):
        on = os.path.join(self.city, "on")
        if os.path.exists(on):
            try:
                with open(on) as fh:
                    os.kill(int(fh.read().split()[0]), 15)
            except (OSError, ValueError, IndexError):
                pass
        super().tearDown()

    def city_run(self, *args, cwd=None, extra=None):
        env = {"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.home}
        env.update(extra or {})
        kw = {"env": env, "timeout": 30}
        if cwd:
            kw["cwd"] = cwd
        return self.repo.run("agent-city.sh", *args, **kw)

    def territories(self):
        path = os.path.join(self.home, "world.json")
        if not wait_for(lambda: os.path.exists(path), timeout=5):
            return {}
        with open(path) as fh:
            return json.load(fh)["territories"]

    def test_start_from_a_repo(self):
        self.assertTrue(re.search(r"--start-dir\b", open(os.path.join(BIN, "agent-city.sh")).read()),
                        "agent-city.sh start must pass --start-dir")
        result = self.city_run("start")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.territories()), [os.path.realpath(os.path.join(self.repo.dir, ".git"))])

    def test_start_from_a_worktree_gives_the_main_repo(self):
        self.repo.detach_scripts_to_worktree()
        result = self.city_run("start")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.territories()), [os.path.realpath(os.path.join(self.repo.dir, ".git"))])

    def test_start_from_a_plain_folder(self):
        plain = os.path.join(self.repo.base, "plain")
        os.makedirs(plain)
        # Its own port: never the real city's 4777. Outside a repo no
        # agent.conf is read (requirements/city.md, "Anywhere"), so the port
        # comes from AGENT_CITY_PORT.
        result = self.city_run("start", cwd=plain, extra={"AGENT_CITY_PORT": str(tp_free_port())})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.territories()), [os.path.realpath(plain)])


SERVER_office = os.path.join(BIN, "agent_city.py")


CONF = "main_manager=opus-5.5:high\npermission_mode=auto\n"


GOOD = {"v": 1, "name": "收银台风格", "why": "POS 收银的 repo",
        "colors": {"accent": "#2E7D6B", "carpet": "#E4DCCB", "manager_floor": "#D9C2A0", "pantry_floor": "#EEEAE0",
                   "desk": "#EFDAB5", "desk_leg": "#BBA27C", "chair": "#3E4560", "meeting_rug": "#A9BCE0",
                   "manager_rug": "#C97B66"},
        "decor": ["cashier", "none", "goods"]}


def good(**kw):
    d = json.loads(json.dumps(GOOD))
    for k, v in kw.items():
        if k.startswith("c_"):
            d["colors"][k[2:]] = v
        else:
            d[k] = v
    return d


def line_office(ev, sid, repo, aid="", role="", at=""):
    return {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": "Read", "nt": "", "proj": "shop", "role": role,
            "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}


class OfficeCase(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_office_"))
        self.calls, self.closed = [], []
        self.answer = (True, "term_abc-1")
        self.mains = Mains()
        self.kind = "orca"
        self.res = {"ram": 10, "cpu": 10, "max": 80, "ok": True}
        self.now = 1000.0
        self.floors_dir = os.path.join(self.base, "floors")
        self.world_file = os.path.join(self.base, "world.json")
        self.shop = self.repo("shop")
        self.blog = self.repo("blog")
        self.state = self.make()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def repo(self, name, conf=CONF):
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
        args = dict(world_path=self.world_file, token="tok", floors_dir=self.floors_dir,
                    main_fn=self.mains, open_fn=self.opener, kind_fn=lambda folder: self.kind,
                    resources_fn=lambda folder: dict(self.res), close_fn=lambda h: self.closed.append(h) or True)
        args.update(kw)
        return ac.CityState(decisions_path=os.path.join(self.base, "decisions.jsonl"), **args)

    def feed(self, *lines, at=None):
        for obj in lines:
            self.state.feed_line(obj, self.now if at is None else at)

    def known(self, identity, sid=None):
        sid = sid or "s-" + os.path.basename(os.path.dirname(identity))
        self.feed(line_office("UserPromptSubmit", sid, identity), line_office("Stop", sid, identity))
        return ac.territory_id(identity)

    def client(self):
        c = self.state.add_client()
        while not c.queue.empty():
            c.queue.get_nowait()
        return c

    def snapshot(self):
        c = self.state.add_client()
        raw = c.queue.get_nowait().decode("utf-8")
        self.state.remove_client(c)
        return json.loads(raw.split("data:", 1)[1])

    @staticmethod
    def events(client, kind=None):
        out = []
        while not client.queue.empty():
            raw = client.queue.get_nowait().decode("utf-8")
            if "data:" not in raw:
                continue
            msg = json.loads(raw.split("data:", 1)[1])
            if kind is None or msg.get("type") == kind:
                out.append(msg)
        return out

    def saved_world(self):
        with open(self.world_file, encoding="utf-8") as fh:
            return json.load(fh)


class TestHttpOffice(OfficeCase):
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
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)   # test-slim-3: shutdown() waits one poll
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        super().tearDown()

    def call(self, path, body=None, method="POST", token="tok", origin="own"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        headers = {}
        if token is not None:
            headers["X-City-Token"] = token
        if origin is not None:
            headers["Origin"] = "http://127.0.0.1:%d" % self.port if origin == "own" else origin
        data = json.dumps(body).encode() if body is not None else None
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

    def test_floors(self):
        self.assertEqual(self.call("/api/floors", {"floors": [self.tid]}), (200, {"floors": [self.tid]}))
        self.assertEqual(self.call("/api/floors", {"floors": [self.tid], "x": 1})[0], 400)
        self.assertEqual(self.call("/api/floors", {"floors": [self.tid]}, token=None)[0], 403)
        self.assertEqual(self.call("/api/floors", {"floors": [self.tid]}, origin="http://evil.example")[0], 403)

    def test_design(self):
        self.assertEqual(self.call("/api/design", {"terr": self.tid, "design": GOOD}), (200, {"design": GOOD}))
        code, body = self.call("/api/design", {"terr": self.tid, "design": good(c_carpet="#000000")})
        self.assertEqual((code, body["error"]), (422, "bad"))
        self.assertEqual(self.call("/api/design", {"terr": self.tid, "undo": True}), (200, {"design": None}))
        self.assertEqual(self.call("/api/design", {"terr": self.tid, "skip": True}), (200, {}))
        for bad in ({"terr": self.tid}, {"terr": self.tid, "undo": 1}, {"terr": self.tid, "design": GOOD, "undo": True},
                    {"terr": self.tid, "design": GOOD, "path": "/etc"}):
            self.assertEqual(self.call("/api/design", bad)[0], 400, bad)
        self.assertEqual(self.call("/api/design", {"terr": self.tid, "design": GOOD}, token="no")[0], 403)

    def test_designer(self):
        code, body = self.call("/api/designer", {"terr": self.tid, "force": False})
        self.assertEqual((code, body["state"]), (200, "opening"))
        self.assertEqual(self.call("/api/designer", {"terr": self.tid, "force": False, "name": "x"})[0], 400)
        self.assertEqual(self.call("/api/designer/leave", {"terr": self.tid}), (404, {"error": "none"}))
        self.assertEqual(self.call("/api/designer", {"terr": self.tid, "force": False}, origin=None)[0], 403)

    def test_get_changes_nothing(self):
        for path in ("/api/floors", "/api/design", "/api/designer", "/api/designer/leave"):
            self.call(path, method="GET")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.state.floors(), [self.tid])


class TestCli(OfficeCase):
    def setUp(self):
        super().setUp()
        self.tid = self.known(self.shop)   # world.json now knows shop

    def run_cli(self, *args, stdin=None, cwd=None):
        env = dict(os.environ, AGENT_CITY_HOME=self.base)
        return subprocess.run([sys.executable, SERVER_office, "floor"] + list(args) +
                              ["--world", self.world_file, "--floors-dir", self.floors_dir],
                              input=stdin, capture_output=True, text=True, env=env, cwd=cwd or self.base, timeout=60)

    def test_rules(self):
        r = self.run_cli("rules")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), ac.FLOOR_RULES.strip())

    def test_set_and_show_by_name_id_and_dot(self):
        r = self.run_cli("show", "shop")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no design yet", r.stdout)
        r = self.run_cli("set", "shop", "-", stdin=json.dumps(GOOD))
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "saved"), r.stderr)
        self.assertEqual(json.loads(self.run_cli("show", self.tid).stdout), GOOD)
        r = self.run_cli("set", ".", "-", stdin=json.dumps(good(name="点")), cwd=os.path.dirname(self.shop))
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.floors_dir, self.tid + ".history.jsonl"), encoding="utf-8") as fh:
            self.assertEqual(json.loads(fh.readline())["name"], GOOD["name"])

    def test_set_refuses_and_names_the_fields(self):
        r = self.run_cli("set", "shop", "-", stdin=json.dumps(good(c_carpet="#000000", decor=["x"])))
        self.assertEqual(r.returncode, 1)
        self.assertIn("colors.carpet: ", r.stderr)
        self.assertIn("decor: ", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.floors_dir, self.tid + ".json")))
        r = self.run_cli("set", "shop", "-", stdin="{not json")
        self.assertEqual(r.returncode, 1)

    def test_unknown_repo(self):
        r = self.run_cli("show", "nope")
        self.assertEqual(r.returncode, 1)
        self.assertIn("shop", r.stdout + r.stderr, "says which repos it knows")

    def test_bye(self):
        r = self.run_cli("bye", "shop")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.floors_dir, self.tid + ".bye")))

    def test_shell_passes_floor_through(self):
        with open(os.path.join(BIN, "agent-city.sh"), encoding="utf-8") as fh:
            self.assertRegex(fh.read(), r"floor\)\s*shift;.*agent_city\.py\"? floor \"\$@\"")


class Case(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_clean_"))
        self.world_file = os.path.join(self.base, "world.json")
        self.shop = os.path.join(self.base, "shop", ".git")
        self.blog = os.path.join(self.base, "blog", ".git")
        for g in (self.shop, self.blog):
            os.makedirs(g)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def make(self, **kw):
        return ac.CityState(decisions_path=os.path.join(self.base, "decisions.jsonl"), world_path=self.world_file,
                            floors_dir=os.path.join(self.base, "floors"), main_fn=Mains(), **kw)

    def saved(self):
        with open(self.world_file, encoding="utf-8") as fh:
            return json.load(fh)


class TestRoutesAreGone(Case):
    def test_layout_and_balance_404(self):
        st = self.make(token="tok")
        server = ThreadingHTTPServer(("127.0.0.1", 0), ac.CityHandler)
        server.daemon_threads = True
        server.city, server.hub, server.page_bytes, server.assets_dir = st, None, b"", self.base
        port = server.server_address[1]
        server.host_set = {"127.0.0.1:%d" % port}
        server.origin_set = {"http://127.0.0.1:%d" % port}
        t = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True)
        t.start()
        try:
            for method, path in (("POST", "/api/layout"), ("GET", "/api/balance?terr=x&kind=build")):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                conn.request(method, path, body=b"{}" if method == "POST" else None,
                             headers={"X-City-Token": "tok", "Origin": "http://127.0.0.1:%d" % port,
                                      "Content-Type": "application/json"})
                resp = conn.getresponse()
                resp.read()
                conn.close()
                self.assertEqual(resp.status, 404, path)
        finally:
            server.shutdown()
            server.server_close()
            t.join(5)


class TestDemoWorld(unittest.TestCase):
    def test_demo_is_an_office(self):
        w = ac.demo_world()
        self.assertEqual(set(w), {"v", "repos", "floors", "designs", "asked"})
        self.assertEqual(w["v"], 2)
        self.assertGreaterEqual(len(w["floors"]), 3)
        ids = {r["id"] for r in w["repos"]}
        self.assertTrue(set(w["floors"]) <= ids)
        self.assertTrue(w["designs"])
        for d in w["designs"].values():
            self.assertEqual(ac.check_design(d), [])
        self.assertTrue([f for f in w["floors"] if f not in w["designs"]], "one floor shows the base look")

    def test_cli_prints_it(self):
        r = subprocess.run([sys.executable, SERVER_office, "demo-world"], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), ac.demo_world())


class TestUpOnSpawnS1(ServerCase_rail_tree):

    def test_a_task_manager_hangs_on_its_governor(self):
        self.governor()
        self.events()
        self.lead()
        self.assertEqual(self.spawn_of("s:tm1")["up"], "gov:" + TA)

    def test_a_task_manager_without_a_governor_still_names_it(self):
        self.lead()
        ev = self.spawn_of("s:tm1")
        self.assertEqual(ev["up"], "gov:" + TA, "the page puts it under the repo while there is no governor")
        self.assertEqual(ev["from"], "", "from is unchanged")

    def test_a_worker_hangs_on_its_task_manager(self):
        self.governor()
        self.lead()
        self.events()
        self.sub("w1", "tm1", role="task-manager")
        self.assertEqual(self.spawn_of("w1")["up"], "s:tm1")

    def test_a_governors_deputy_hangs_on_the_governor(self):
        self.governor()
        self.events()
        self.sub("d1", "g1", kind="fast-lane-deputy")
        self.assertEqual(self.spawn_of("d1")["up"], "gov:" + TA)

    def test_a_helper_hangs_on_the_area_manager_and_its_subagent_on_it(self):
        # city-office O2 (2026-11-24): the tree is 区经理 > 设计师, 助理, 经理 (was: a helper right under the repo)
        self.governor()
        self.events()
        self.helper()
        self.assertEqual(self.spawn_of("s:h1")["up"], "gov:" + TA)
        self.sub("e1", "h1", kind="Explore")
        self.assertEqual(self.spawn_of("e1")["up"], "s:h1")

    def test_another_repos_task_manager_names_its_own_governor(self):
        self.governor("g1", A_REPO)
        self.events()
        self.line("PostToolUse", "tm9", B_REPO, role="task-manager", tool="Bash")
        self.assertEqual(self.spawn_of("s:tm9")["up"], "gov:" + TB)


class TestUpInTheSnapshotS2(ServerCase_rail_tree):

    def snap_agents(self):
        client = self.st.add_client()
        try:
            data = client.queue.get_nowait().decode("utf-8")
        finally:
            self.st.remove_client(client)
        return {a["id"]: a for a in json.loads(data.split("data:", 1)[1])["agents"]}

    def test_every_agent_carries_its_up(self):
        self.governor()
        self.lead()
        self.helper()
        self.sub("w1", "tm1", role="task-manager")
        self.sub("d1", "g1", kind="fast-lane-deputy")
        agents = self.snap_agents()
        for cid, want in (("s:tm1", "gov:" + TA), ("s:h1", "gov:" + TA), ("w1", "s:tm1"), ("d1", "gov:" + TA)):
            self.assertIn(cid, agents)
            self.assertIn("up", agents[cid], cid)
            self.assertEqual(agents[cid]["up"], want, cid)

    def test_up_stays_after_later_lines(self):
        self.governor()
        self.lead()
        self.sub("w1", "tm1", role="task-manager")
        for _ in range(3):
            self.line("PostToolUse", "tm1", role="task-manager", aid="w1", at="worker", tool="Read")
        self.assertEqual(self.snap_agents()["w1"]["up"], "s:tm1")


class TestGovWatchRoles(AskHookCase):
    def setUp(self):
        super().setUp()
        self.repo_id = os.path.realpath(self.work)      # not a git dir: _repo_id() gives the folder

    def lock(self, sid):
        with open(os.path.join(self.work, "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-09-30 10:00 %s -\n" % (os.getpid(), sid))

    def watch(self, sid, max_wait="20"):
        env = dict(os.environ, AGENT_CITY_DIR=self.dir)
        env.pop("AGENT_ROLE", None)
        env.pop("CLAUDE_PID", None)
        proc = subprocess.Popen([sys.executable, interact.SERVER, "gov-watch", "--max-wait-sec", max_wait],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env)
        proc.stdin.write(interact.stop_payload(self.work, sid))
        proc.stdin.close()
        self.hooks.append(proc)
        return proc

    def session_line(self, ev, sid):
        self.append(json.dumps({"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "", "nt": "",
                                "proj": "work", "role": "", "desc": "", "sub": "", "q": "",
                                "klen": "", "repo": self.repo_id, "ask": "", "wt": "", "file": "",
                                "tp": "", "pid": ""}) + "\n")

    def send(self, to, text):
        status, _, out = self.api("POST", "/api/chat/send", {"to": to, "text": text}, origin=self.origin)
        self.assertEqual(status, 200, out)
        return out

    def test_a_helper_is_never_asked_as_governor(self):
        self.lock("main-1")
        self.start()
        proc = self.watch("helper-1", max_wait="4")
        time.sleep(1.0)
        self.assertEqual(self.health()["governors"], 0, "a helper never shows up as a governor")
        self.assertEqual(self.view(self.ask(interact.q_body(repo=self.repo_id)))["phase"], "owner")
        code, out, err = self.finish(proc)
        self.assertEqual((code, out, err), (0, b"", b""))

    def test_a_helper_hears_its_own_message(self):
        self.lock("main-1")
        self.start()
        self.session_line("UserPromptSubmit", "helper-1")
        self.session_line("Stop", "helper-1")
        self.assertTrue(interact.wait_for(lambda: self.api("GET", "/api/chat?to=s:helper-1")[0] == 200,
                                          timeout=5), "the helper never showed up as a citizen")
        proc = self.watch("helper-1")
        self.send("s:helper-1", "hello helper")
        code, out, err = self.finish(proc)
        self.assertEqual((code, out), (2, b""))
        self.assertIn("hello helper", err.decode("utf-8"))

    def test_the_holder_hears_the_owner(self):
        self.lock("main-1")
        self.start()
        self.session_line("UserPromptSubmit", "main-1")
        self.session_line("Stop", "main-1")
        gov_page = "gov:" + ac.territory_id(self.repo_id)
        self.assertTrue(interact.wait_for(lambda: self.api("GET", "/api/chat?to=" + gov_page)[0] == 200,
                                          timeout=5), "the main manager never showed up as the governor")
        proc = self.watch("main-1")
        self.assertTrue(interact.wait_for(lambda: self.health()["governors"] == 1, timeout=5))
        self.send(gov_page, "today do A first")
        code, out, err = self.finish(proc)
        self.assertEqual((code, out), (2, b""))
        self.assertIn("today do A first", err.decode("utf-8"))


def hook_line(ev, sid, repo, pid, role=""):
    return json.dumps({"ev": ev, "sid": sid, "aid": "", "at": "", "tool": "Read", "nt": "", "proj": "shop",
                       "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "ask": "",
                       "wt": "", "file": "", "tp": "", "pid": str(pid)}) + "\n"


class TestServerRestart(ServerCase):
    def setUp(self):
        super().setUp()
        self.repo = os.path.join(os.path.realpath(self.base), "shop", ".git")
        os.makedirs(self.repo)
        self.sessions = []

    def tearDown(self):
        for p in self.sessions:
            if p.poll() is None:
                p.kill()
                p.wait()
        super().tearDown()

    def live(self):
        proc = subprocess.Popen(["sleep", "120"])
        self.sessions.append(proc)
        return proc

    def stop(self, proc):
        proc.send_signal(signal.SIGTERM)
        proc.wait(10)
        self.assertIsNone(self.on(), "DIR/on is gone with the server")

    def first_run(self):
        """A main manager and a task manager, both seen, both idle; then the server stops."""
        self.gov, self.tm = self.live(), self.live()
        lock_file(self.repo, "sid-gov", pid=self.gov.pid)
        server = self.start()
        for sid, proc, role in (("sid-gov", self.gov, ""), ("sid-tm", self.tm, "task-manager")):
            self.append(hook_line("PostToolUse", sid, self.repo, proc.pid, role))
            self.append(hook_line("Stop", sid, self.repo, proc.pid, role))
        self.assertTrue(wait_for(lambda: self.health()["lines"] == 4), "the 4 lines were never read")
        self.assertTrue(os.path.exists(os.path.join(self.dir, "roster.json")), "serve keeps DIR/roster.json")
        self.stop(server)

    def look(self):
        return self.sse().messages[0]

    def test_both_are_shown_at_once_with_no_new_event(self):
        self.first_run()
        self.start()
        snap = self.look()
        self.assertEqual([(g["terr"], g["state"]) for g in snap["govs"]], [(ac.territory_id(self.repo), "idle")])
        self.assertEqual([(a["id"], a["role"], a["terr"]) for a in snap["agents"]],
                         [("s:sid-tm", "task-manager", ac.territory_id(self.repo))])
        self.assertEqual(self.health()["lines"], 0, "nothing new was read: they came from the roster")

    def test_a_killed_session_is_gone_after_the_restart(self):
        self.first_run()
        self.tm.kill()
        self.tm.wait()
        self.start()
        snap = self.look()
        self.assertEqual(snap["agents"], [])
        self.assertEqual([g["state"] for g in snap["govs"]], ["idle"], "the main manager is still there")


SERVER_status = os.path.join(ROOT, "bin", "agent_city.py")


def task(kind, **kw):
    out = {"id": "t1", "type": kind, "status": "running", "description": "d"}
    out.update(kw)
    return out


class TestSayWritesTheNote(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_status_say_")
        self.dir = os.path.join(self.base, "city")
        os.makedirs(self.dir)
        with open(os.path.join(self.dir, "on"), "w") as fh:
            fh.write("1 1\n")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def say(self, payload, **env_extra):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE"}
        env.update(AGENT_CITY_DIR=self.dir, HOME=self.base)
        env.update(env_extra)
        r = subprocess.run([sys.executable, SERVER_status, "say"], input=json.dumps(payload).encode("utf-8"),
                           capture_output=True, env=env, timeout=20)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, b"", b""))

    def read(self, name):
        try:
            with open(os.path.join(self.dir, name), encoding="utf-8") as fh:
                return [json.loads(x) for x in fh if x.strip()]
        except FileNotFoundError:
            return []

    def stop(self, text, tasks=None, **kw):
        payload = {"session_id": "s1", "transcript_path": "/t/s1.jsonl", "cwd": "/w",
                   "hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": text}
        if tasks is not None:
            payload["background_tasks"] = tasks
            payload["session_crons"] = []
        payload.update(kw)
        return payload

    def test_report_only(self):
        self.say(self.stop("合并已经在 pc2 上开始了，11:00 左右完成。", tasks=[]))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "", "bg": ""}])

    def test_reply_that_asks(self):
        self.say(self.stop("结果：通过\n\n要你决定\n- 现在合并吗", tasks=[]))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "1", "bg": ""}])

    def test_background_shell(self):
        self.say(self.stop("Started the build.", tasks=[task("shell", command="sleep 60")]))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "", "bg": "1"}])

    def test_asks_and_background(self):
        self.say(self.stop("Merge now?", tasks=[task("subagent", agent_type="worker")]))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "1", "bg": "1"}])

    def test_old_claude_code_has_no_task_list(self):
        self.say(self.stop("Done."))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "", "bg": ""}])

    def test_empty_reply_still_writes_the_note(self):
        self.say(self.stop("", tasks=[task("shell")]))
        self.assertEqual(self.read("events.jsonl"), [{"ev": "StopNote", "sid": "s1", "need": "", "bg": "1"}])
        self.assertEqual(self.read("chat.jsonl"), [])

    def test_flags_only(self):
        self.say(self.stop("secret reply text?", tasks=[task("shell", command="curl https://secret.example",
                                                             description="secret description")]))
        with open(os.path.join(self.dir, "events.jsonl"), encoding="utf-8") as fh:
            raw = fh.read()
        self.assertEqual(raw.count("\n"), 1)
        for leak in ("secret", "curl", "/t/s1.jsonl"):
            self.assertNotIn(leak, raw)

    def test_chat_row_as_before(self):
        self.say(self.stop("Merge now?", tasks=[]))
        rows = self.read("chat.jsonl")
        self.assertEqual([(r["sid"], r["aid"], r["kind"], r["text"]) for r in rows],
                         [("s1", "", "reply", "Merge now?")])

    def test_only_the_sessions_own_stop(self):
        self.say({"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "go?"})
        self.say({"session_id": "s1", "hook_event_name": "SubagentStop", "agent_id": "a1",
                  "last_assistant_message": "QUESTION: which?", "background_tasks": [task("shell")]})
        self.assertEqual(self.read("events.jsonl"), [])

    def test_city_off_or_cloud(self):
        self.say(self.stop("Merge now?", tasks=[]), CLAUDE_CODE_REMOTE="true")
        os.remove(os.path.join(self.dir, "on"))
        self.say(self.stop("Merge now?", tasks=[]))
        self.assertEqual(self.read("events.jsonl"), [])


class TestSpawnSaysWhoSentItT1(TalkServerCase):

    def test_a_workers_sender_is_its_lead(self):
        self.governor()
        self.lead()
        self.events()
        self.sub("w1", "tm1", role="task-manager")
        self.assertEqual(self.spawn_of("w1")["from"], "s:tm1")

    def test_the_governors_subagent_comes_from_the_governor(self):
        self.governor()
        self.events()
        self.sub("d1", "g1", kind="fast-lane-deputy")
        self.assertEqual(self.spawn_of("d1")["from"], "gov:" + TALK_TA)

    def test_a_helpers_subagent_comes_from_the_helper(self):
        self.governor()
        self.helper()
        self.events()
        self.sub("e1", "h1", kind="Explore")
        self.assertEqual(self.spawn_of("e1")["from"], "s:h1")

    def test_a_task_manager_session_comes_from_the_governor(self):
        self.governor()
        self.events()
        self.lead()
        self.assertEqual(self.spawn_of("s:tm1")["from"], "gov:" + TALK_TA)

    def test_a_session_the_owner_opened_has_no_sender(self):
        self.governor()
        self.events()
        self.helper()
        self.assertEqual(self.spawn_of("s:h1")["from"], "")

    def test_another_repos_governor_is_not_the_sender(self):
        self.governor("g1", A_REPO)
        self.events()
        self.line("PostToolUse", "tm9", B_REPO, role="task-manager", tool="Bash")
        self.assertEqual(self.spawn_of("s:tm9")["from"], "")


class TestSendMessageBecomesATalkT3(TalkServerCase):

    def setUp(self):
        super().setUp()
        self.governor()
        self.lead("tm1", "city-talk Task Manager")
        self.lead("tm2", "city-rail Task Manager")
        self.helper("h1", "app Helper")
        self.sub("w1", "tm1", role="task-manager")
        self.events()

    def one(self):
        found = self.talks()
        self.assertEqual(len(found), 1, "one talk event")
        return found[0]

    def test_session_to_session_by_its_name(self):
        self.send("h1", "city-talk Task Manager")
        self.assertEqual(self.one(), {"type": "talk", "from": "s:h1", "to": "s:tm1", "terr": TALK_TA})

    def test_the_name_matches_in_any_case(self):
        self.send("tm1", "  CITY-RAIL task manager ", role="task-manager")
        self.assertEqual(self.one()["to"], "s:tm2")

    def test_to_the_governor_by_the_repo_name(self):
        for name in ("app Manager", "app-7f", "app"):
            with self.subTest(to=name):
                self.send("tm2", name, role="task-manager")
                self.assertEqual(self.one(), {"type": "talk", "from": "s:tm2", "to": "gov:" + TALK_TA, "terr": TALK_TA})

    def test_a_session_name_wins_over_the_repo_name(self):
        self.send("tm1", "app Helper", role="task-manager")
        self.assertEqual(self.one()["to"], "s:h1")

    def test_only_a_whole_repo_name_means_the_governor(self):
        self.send("tm1", "application team", role="task-manager")
        self.assertEqual(self.one()["to"], "")

    def test_from_the_governor(self):
        self.send("g1", "city-rail Task Manager")
        self.assertEqual(self.one(), {"type": "talk", "from": "gov:" + TALK_TA, "to": "s:tm2", "terr": TALK_TA})

    def test_the_governor_never_talks_to_himself(self):
        self.send("g1", "app Manager")
        self.assertEqual(self.one()["to"], "")

    def test_to_a_subagent_by_its_id(self):
        self.send("tm1", "w1", role="task-manager")
        self.assertEqual(self.one(), {"type": "talk", "from": "s:tm1", "to": "w1", "terr": TALK_TA})

    def test_from_a_subagent(self):
        self.send("tm1", "app Helper", role="task-manager", aid="w1")
        self.assertEqual(self.one()["from"], "w1")

    def test_not_recognised_is_an_empty_recipient(self):
        self.send("h1", "somebody else")
        self.assertEqual(self.one(), {"type": "talk", "from": "s:h1", "to": "", "terr": TALK_TA})

    def test_another_repos_governor(self):
        self.governor("g2", B_REPO)
        self.events()
        self.send("h1", "shop Manager")
        self.assertEqual(self.one(), {"type": "talk", "from": "s:h1", "to": "gov:" + TALK_TB, "terr": TALK_TA})

    # bounce 1 (real sessions on pc2, 2026-10-01): the manager's REPLY went out with
    # to = "uds:/tmp/cc-socks/41216.sock" (41216 = the helper's pid), so the answer had no walk-over

    def test_a_reply_to_a_socket_address_means_the_session_with_that_pid(self):
        self.line("PostToolUse", "h1", tool="Bash", pid="41216")
        self.events()
        self.send("g1", "uds:/tmp/cc-socks/41216.sock")
        self.assertEqual(self.one(), {"type": "talk", "from": "gov:" + TALK_TA, "to": "s:h1", "terr": TALK_TA})

    def test_any_socket_folder(self):
        self.line("PostToolUse", "tm2", role="task-manager", tool="Bash", pid="5150")
        self.events()
        self.send("tm1", "uds:/var/folders/hl/9td/T/cc-socks/5150.sock", role="task-manager")
        self.assertEqual(self.one()["to"], "s:tm2")

    def test_a_socket_address_of_the_governor(self):
        self.line("UserPromptSubmit", "g1", pid=str(os.getpid()))
        self.events()
        self.send("h1", "uds:/tmp/cc-socks/%d.sock" % os.getpid())
        self.assertEqual(self.one(), {"type": "talk", "from": "s:h1", "to": "gov:" + TALK_TA, "terr": TALK_TA})

    def test_a_socket_address_nobody_has(self):
        self.line("PostToolUse", "h1", tool="Bash", pid="41216")
        self.events()
        for name in ("uds:/tmp/cc-socks/99999.sock", "uds:/tmp/cc-socks/abc.sock", "uds:/tmp/cc-socks/41216.sock.bak",
                     "/tmp/cc-socks/41216.sock", "uds:41216"):
            with self.subTest(to=name):
                self.send("g1", name)
                self.assertEqual(self.one()["to"], "")

    def test_its_own_socket_address_is_nobody(self):
        self.line("PostToolUse", "h1", tool="Bash", pid="41216")
        self.events()
        self.send("h1", "uds:/tmp/cc-socks/41216.sock", pid="41216")
        self.assertEqual(self.one()["to"], "")

    def test_the_latest_pid_of_a_session_counts(self):
        self.line("PostToolUse", "h1", tool="Bash", pid="41216")
        self.line("PostToolUse", "h1", tool="Bash", pid="41300")
        self.events()
        self.send("g1", "uds:/tmp/cc-socks/41216.sock")
        self.assertEqual(self.one()["to"], "", "the old pid is nobody's now")
        self.send("g1", "uds:/tmp/cc-socks/41300.sock")
        self.assertEqual(self.one()["to"], "s:h1")

    def test_a_session_id_means_that_session(self):
        self.send("g1", "h1")
        self.assertEqual(self.one(), {"type": "talk", "from": "gov:" + TALK_TA, "to": "s:h1", "terr": TALK_TA})
        self.send("tm1", "TM2", role="task-manager")
        self.assertEqual(self.one()["to"], "s:tm2")

    def test_the_governors_session_id_means_the_governor(self):
        self.send("h1", "g1")
        self.assertEqual(self.one(), {"type": "talk", "from": "s:h1", "to": "gov:" + TALK_TA, "terr": TALK_TA})

    def test_its_own_session_id_is_nobody(self):
        self.send("h1", "h1")
        self.assertEqual(self.one()["to"], "")
        self.send("g1", "g1")
        self.assertEqual(self.one()["to"], "")

    def test_a_session_that_ended_is_nobody(self):
        self.line("PostToolUse", "h1", tool="Bash", pid="41216")
        self.line("SessionEnd", "h1", pid="41216")
        self.events()
        self.send("g1", "uds:/tmp/cc-socks/41216.sock")
        self.assertEqual(self.one()["to"], "")
        self.send("g1", "h1")
        self.assertEqual(self.one()["to"], "")

    def test_old_hook_lines_make_no_talk(self):
        self.line("PostToolUse", "h1", tool="SendMessage")
        self.send("h1", "")
        self.assertEqual(self.talks(), [])

    def test_a_question_is_a_relay_not_a_talk(self):
        self.send("tm1", "app Manager", role="task-manager", ask="q")
        ev = self.events()
        self.assertEqual([e for e in ev if e.get("type") == "talk"], [])
        self.assertEqual([(e["id"], e["to"]) for e in ev if e.get("type") == "relay"], [("s:tm1", "governor")])

    def test_an_answer_that_closes_a_relay_is_no_talk(self):
        self.line("SubagentStop", "tm1", role="task-manager", aid="w1", at="worker", ask="q")
        self.events()
        self.send("tm1", "w1", role="task-manager")
        ev = self.events()
        self.assertEqual([(e["id"], e["by"]) for e in ev if e.get("type") == "relay_end"], [("w1", "lead")])
        self.assertEqual([e for e in ev if e.get("type") == "talk"], [], "relay_end already shows the answer")

    def test_only_post_tool_use(self):
        self.send("h1", "city-talk Task Manager", ev="PreToolUse")
        self.assertEqual(self.talks(), [])

    def test_other_tools_never_talk(self):
        self.line("PostToolUse", "h1", tool="Bash", to="city-talk Task Manager")
        self.assertEqual(self.talks(), [])

    def test_a_talk_is_not_kept_in_the_snapshot(self):
        self.send("h1", "city-talk Task Manager")
        raw = self.st.add_client().queue.get_nowait()
        self.assertNotIn(b'"talk"', raw)


FLAGS = ["--model", "opus", "--effort", "high", "--permission-mode", "auto"]   # CONF's opus-5.5 as the CLI takes it


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
        bar = self.repo("bar", "main_manager=fable-5.1:medium\npermission_mode=acceptEdits\n")
        self.known(self.shop)
        self.known(bar, "old2")
        self.add(self.shop)
        self.add(bar)
        self.assertEqual([c[0] for c in self.calls], [os.path.join(self.base, "shop"), os.path.join(self.base, "bar")])
        self.assertEqual(shlex.split(self.calls[1][2]),
                         ["claude", "--name", "bar Manager", "--model", "fable", "--effort", "medium",
                          "--permission-mode", "acceptEdits", PROMPT])

    def test_nothing_set_gives_the_default_flags(self):
        # settings-configure: the settings always have a value (Configure, else the default)
        os.remove(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "settings.json"))
        bare = self.repo("bare", conf=None)
        self.known(bare)
        code, body = self.add(bare)
        self.assertEqual(code, 200, body)
        self.assertEqual(shlex.split(self.calls[0][2]), ["claude", "--name", "bare Manager"] + ["--model", "opus", "--effort", "high", "--permission-mode", "bypassPermissions"] + [PROMPT])

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
        self.feed(line_aa("UserPromptSubmit", "old1", self.shop), at=self.now + 1)        # a session from before the open
        self.feed(line_aa("PostToolUse", "old1", self.shop, aid="a1"), at=self.now + 1)   # and its subagent
        self.assertEqual(self.add(self.shop, at=self.now + 2)[0], 409, "an old session's line is not the new one")
        self.feed(line_aa("UserPromptSubmit", "new1", self.shop), at=self.now + 3)        # the new session's first line
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
            # settings-configure: a refused value reads as the setting default
            "both": ("main_manager=opus-5.5:high; touch pwned\npermission_mode=auto$(touch pwned)\n", ["--model", "opus", "--effort", "high", "--permission-mode", "bypassPermissions"]),
            "mode": ("main_manager=opus-5.5:xhigh\npermission_mode=auto && touch pwned\n",
                     ["--model", "opus", "--effort", "xhigh", "--permission-mode", "bypassPermissions"]),
            "model": ("main_manager=`touch pwned`:high\npermission_mode=plan\n",
                      ["--model", "opus", "--effort", "high", "--permission-mode", "plan"]),
            "effort": ("main_manager=opus-5.5:huge\npermission_mode=auto\n", ["--model", "opus", "--effort", "high", "--permission-mode", "auto"]),
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
                             # decider-floor: a main manager below Opus 5.5 / Fable /
                             # effort medium is refused: the setting default opus-5.5:high
                             ("sonnet-5:medium", ["--model", "opus", "--effort", "high"]),
                             ("haiku-4.5:low", ["--model", "opus", "--effort", "high"]),
                             ("claude-fable-5-1:max", ["--model", "claude-fable-5-1", "--effort", "max"]),
                             ("mystery-7:high", ["--model", "opus", "--effort", "high"])):
            with self.subTest(main_manager=value):
                name = "m-" + value.split(":")[0].replace(".", "-")
                self.repo(name, "main_manager=%s\n" % value)
                command = ac.agent_command("x Manager", os.path.join(self.base, name))
                words = shlex.split(command)
                self.assertEqual(words[:3 + len(flags)], ["claude", "--name", "x Manager"] + flags)
        os.remove(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "settings.json"))
        self.repo("as-shipped", None)
        words = shlex.split(ac.agent_command("x Manager", os.path.join(self.base, "as-shipped")))
        self.assertIn(words[words.index("--model") + 1], ("fable", "opus", "sonnet", "haiku"),
                      "the conf this plugin ships must open a session that can run")

    def test_no_shell_anywhere(self):
        with open(SERVER, encoding="utf-8") as fh:
            src = fh.read()
        for bad in ("shell=True", "os.system(", "os.popen("):
            self.assertNotIn(bad, src)


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
        # script-speed: agent-resume.sh hands the spec to its one python3 start (agent_nightly.py resume-prep
        # --model), which asks agent_conf.cli_model; before, it ran agent_conf.py cli-model itself
        self.assertIn("agent_nightly.py", resume)
        self.assertIn("--model", resume, "agent-resume.sh's model word must come from agent_conf's cli_model")
        with open(os.path.join(BIN, "agent_nightly.py"), encoding="utf-8") as fh:
            nightly = fh.read()
        self.assertIn("agent_conf.cli_model(", nightly)
        for family in ("opus*)", "sonnet*)", "haiku*)", "fable*)"):
            self.assertNotIn(family, resume, "no second copy of the family list")
            self.assertNotIn(family, nightly, "no second copy of the family list")
        with open(SERVER, encoding="utf-8") as fh:
            server = fh.read()
        self.assertIn("cli_model(", server)


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

    def test_the_runtime_setting_counts(self):
        cfg = os.path.join(self.base, "cfg")
        os.makedirs(cfg)
        with open(os.path.join(cfg, "settings.json"), "w") as fh:
            json.dump({"pluginConfigs": {"auto-pipeline@auto-pipeline": {"options": {"runtime": "plain"}}}}, fh)
        env = {k: v for k, v in os.environ.items() if k not in ("AGENT_RUNTIME", "CLAUDE_PROJECT_DIR", "CLAUDE_CODE_REMOTE")}
        env["CLAUDE_CONFIG_DIR"] = cfg
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
        env = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": os.path.join(self.base, "cfg")})
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def conf(self, text):
        """settings-configure: the Max memory % setting (Configure, user level)."""
        configure_text(text)

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

    def test_nothing_set_takes_the_default_cap(self):
        default = 80   # the Max memory % default
        with mock.patch.dict(os.environ, {"AGENT_FAKE_RAM": "5", "AGENT_FAKE_CPU": "5"}):
            self.assertEqual(ac.machine_resources(self.base), {"ram": 5, "cpu": 5, "max": default, "ok": True})
            self.conf("max_usage_percent=lots\n")
            self.assertEqual(ac.machine_resources(self.base)["max"], default, "a bad value is not a cap")

    def test_never_raises(self):
        got = ac.machine_resources(self.base, script=os.path.join(self.base, "missing.sh"))
        self.assertEqual((got["ram"], got["cpu"], got["ok"]), (-1, -1, True))


class TestPageEvents(AddCase):
    def setUp(self):
        super().setUp()
        self.tid = self.known(self.shop)
        self.page = self.client()

    def test_opening_then_done(self):
        self.add(self.shop)
        self.assertEqual(self.events(self.page),
                         [{"type": "adding", "terr": self.tid, "state": "opening", "name": "shop Manager", "role": "main"}])
        self.feed(line_aa("UserPromptSubmit", "old1", self.shop), at=self.now + 1)
        self.assertEqual(self.events(self.page), [], "an old session's line ends nothing")
        self.feed(line_aa("UserPromptSubmit", "new1", self.shop), at=self.now + 2)
        self.assertEqual(self.events(self.page), [{"type": "adding", "terr": self.tid, "state": "done"}])
        self.feed(line_aa("Stop", "new1", self.shop), at=self.now + 3)
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
            self.state.feed_line(line_aa("UserPromptSubmit", "new1", self.shop), self.now)   # it is already here
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
        self.feed(line_aa("UserPromptSubmit", "new1", self.shop), at=self.now + 2)
        self.assertEqual(snapshot()["adding"], [])


class TestHere(AddCase):
    def test_the_world_view_says_here(self):
        state = self.make(start_repo=self.shop)
        page = self.client(state)
        state.feed_line(line_aa("UserPromptSubmit", "s9", "/nowhere/ghost/.git"), self.now)   # a repo that is not on this machine
        worlds = self.events(page, "world")
        self.assertTrue(worlds, "a new territory is a world event")
        here = {t["id"]: t.get("here") for t in worlds[-1]["world"]["repos"]}
        self.assertEqual(here, {ac.territory_id(self.shop): True, ac.territory_id("/nowhere/ghost/.git"): False})
        c = state.add_client()
        snap = json.loads(c.queue.get_nowait().decode("utf-8").split("data:", 1)[1])
        self.assertEqual({t["id"]: t.get("here") for t in snap["world"]["repos"]}, here)

    def test_a_folder_that_is_not_here_never_opens(self):
        tid = self.known("/nowhere/ghost/.git")
        code, body = self.state.add_agent(tid, self.now)
        self.assertEqual((code, body), (409, {"error": "gone", "folder": "/nowhere/ghost"}))
        self.assertEqual(self.calls, [])


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
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)   # test-slim-3: shutdown() waits one poll
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


MODEL = ["--model", "opus", "--effort", "high"]


def conf_text(**keys):
    text = "main_manager=opus-5.5:high\n"
    for key, value in keys.items():
        text += "%s=%s\n" % (key, value)
    return text


class LineCase(AddCase):
    def folder(self, name, conf):
        """conf: old key=value text, written into Configure (settings-configure)."""
        self.repo(name, conf)
        return os.path.join(self.base, name)

    def words(self, name, conf, **kw):
        return shlex.split(ac.agent_command("x Manager", self.folder(name, conf), **kw))


class TestLaunchLine(LineCase):
    def test_the_signature(self):
        import inspect
        params = inspect.signature(ac.agent_command).parameters
        # city-office O6: the interior designer's line takes its own model key, prompt and AGENT_ROLE
        # session-cleanup rule 7: and the city home, so the designer's `floor bye` lands where the server looks
        self.assertEqual(list(params), ["name", "folder", "city_dir", "model_key", "prompt", "role", "city_home"])

    def test_local_uses_permission_mode(self):
        conf = conf_text(permission_mode="bypassPermissions")
        self.assertEqual(self.words("loc", conf),
                         ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "bypassPermissions", PROMPT])

    def test_nothing_set_is_the_defaults(self):
        os.remove(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "settings.json"))
        folder = self.folder("bare", None)
        self.assertEqual(shlex.split(ac.agent_command("x Manager", folder)),
                         ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "bypassPermissions", PROMPT])

    def test_the_old_cloud_key_decides_nothing(self):
        conf = conf_text(cloud_permission_mode="bypassPermissions")
        self.assertEqual(self.words("only-cloud", conf),
                         ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "auto", PROMPT])

    def test_the_city_dir_is_kept(self):
        own = os.path.join(self.base, "my city")
        folder = self.folder("cd", conf_text(permission_mode="bypassPermissions"))
        words = shlex.split(ac.agent_command("x Manager", folder, own))
        self.assertEqual(words, ["AGENT_CITY_DIR=" + own, "claude", "--name", "x Manager"] + MODEL
                         + ["--permission-mode", "bypassPermissions", PROMPT])

    def test_both_keys_broken(self):
        conf = ("main_manager=opus-5.5:high; touch pwned\npermission_mode=bypassPermissions$(touch pwned)\n"
                "cloud_permission_mode=auto`touch pwned`\n")
        folder = self.folder("both", conf)
        command = ac.agent_command("x Manager", folder)
        self.assertEqual(shlex.split(command),
                         ["claude", "--name", "x Manager"] + MODEL + ["--permission-mode", "bypassPermissions", PROMPT])
        self.assertNotIn("pwned", command)

    def test_the_shipped_default_is_bypass(self):
        # owner order 2026-11-25: the default stays bypassPermissions (as since 2026-11-04)
        os.remove(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "settings.json"))
        folder = self.folder("shipped", None)
        local = shlex.split(ac.agent_command("x Manager", folder))
        self.assertEqual(local[local.index("--permission-mode") + 1], "bypassPermissions")


class TestAddAgent(LineCase):
    CONF = conf_text(permission_mode="bypassPermissions")

    def setUp(self):
        super().setUp()
        from cityhelp import configure_text
        configure_text(self.CONF)
        self.known(self.shop)

    def mode(self, command):
        words = shlex.split(command)
        return words[words.index("--permission-mode") + 1]

    def test_a_local_click_is_permission_mode(self):
        code, body = self.add(self.shop)
        self.assertEqual(code, 200, body)
        self.assertEqual(self.mode(self.calls[0][2]), "bypassPermissions")


class TestHttpNeverACloudStart(unittest.TestCase):
    def test_the_local_route_takes_no_cloud_key(self):
        """POST /api/agent/add: terr and force only (the existing key check); "cloud" is not one of them."""
        import inspect
        src = inspect.getsource(ac.CityHandler._api_agent_add)
        self.assertIn('("terr", "force")', src)
        self.assertNotIn("cloud", src)


if __name__ == "__main__":
    unittest.main()
