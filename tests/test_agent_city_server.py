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
                Cache-Control: max-age=86400. A path that leaves <assets>
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
  more than on, token, events.jsonl and events.jsonl.1.
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
          with "OVER CAP", starts nothing, exit 1. Otherwise starts the server in
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SERVER = os.path.join(ROOT, "bin", "agent_city.py")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase  # noqa: E402


def line(ev, sid="s1", aid="", at="", tool="", nt="", role="", desc="", sub="", q=""):
    return json.dumps({"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": nt,
                       "proj": "shop", "role": role, "desc": desc, "sub": sub, "q": q}) + "\n"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def wait_for(check, timeout=8.0, step=0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(step)
    return check()


class SSE:
    """A tiny /events reader that collects messages on a thread."""

    def __init__(self, port):
        self.conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        self.conn.request("GET", "/events")
        # getresponse() drops conn.sock for a stream with no length, so keep
        # the socket here: close() must really hang up, like a closed tab.
        self.raw = self.conn.sock
        self.resp = self.conn.getresponse()
        self.messages = []
        self.status = self.resp.status
        self.headers = dict(self.resp.getheaders())
        self.done = False
        if self.status == 200:
            threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while True:
                raw = self.resp.fp.readline()
                if not raw:
                    break
                text = raw.decode("utf-8").rstrip("\n")
                if text.startswith("data:"):
                    self.messages.append(json.loads(text[5:].strip()))
        except Exception:
            pass
        self.done = True

    def events(self, kind=None):
        rows = [m for m in self.messages if m.get("type") != "snapshot"]
        return [m for m in rows if kind is None or m.get("type") == kind]

    def close(self):
        try:
            self.raw.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.raw.close()
        self.conn.close()


class ServerCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_srv_")
        self.dir = os.path.join(self.base, "city")
        self.procs = []
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    p.kill()
        shutil.rmtree(self.base, ignore_errors=True)

    def start(self, *extra, wait=True):
        args = [sys.executable, SERVER, "serve", "--dir", self.dir, "--port", "0"]
        args += list(extra) or ["--idle-sec", "60"]
        # Never the real ~/.claude/agent-city (world.json, decisions.jsonl).
        env = dict(os.environ, AGENT_CITY_HOME=os.path.join(self.base, "cityhome"))
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        self.procs.append(proc)
        if wait:
            self.assertTrue(wait_for(lambda: (self.on() or (0,))[0] == proc.pid),
                            "DIR/on never named the new server")
        return proc

    def on(self):
        try:
            with open(os.path.join(self.dir, "on")) as fh:
                pid, port = fh.read().split()
            return int(pid), int(port)
        except (OSError, ValueError):
            return None

    @property
    def port(self):
        return self.on()[1]

    def get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, dict(resp.getheaders()), body

    def health(self):
        return json.loads(self.get("/health")[2])

    def append(self, text):
        with open(os.path.join(self.dir, "events.jsonl"), "a") as fh:
            fh.write(text)

    def sse(self):
        client = SSE(self.port)
        self.clients.append(client)
        if client.status == 200:
            self.assertTrue(wait_for(lambda: client.messages), "no snapshot arrived")
        return client


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
        spawn = {k: v for k, v in spawn.items() if k != "terr"}
        self.assertEqual(spawn, {"type": "spawn", "id": "a1", "role": "worker",
                                 "label": "worker", "task": "设置页表单"})
        self.assertEqual(tool, {"type": "tool", "id": "a1", "tool": "Edit"})

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
                self.assertIn("max-age=86400", headers.get("Cache-Control", ""))

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
            time.sleep(0.15)
        self.assertTrue(wait_for(lambda: len(client.events("tool")) == 300, timeout=15),
                        "got %d tool events" % len(client.events("tool")))
        size = os.path.getsize(os.path.join(self.dir, "events.jsonl"))
        self.assertLess(size, 4096 + 30 * 200)
        # token: the per-start control token (tests/test_agent_city_interact.py)
        self.assertLessEqual(set(os.listdir(self.dir)),
                             {"on", "token", "events.jsonl", "events.jsonl.1"})

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

    def test_over_cap_starts_nothing(self):
        result = self.city_run("start", env={"AGENT_FAKE_RAM": "95"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("OVER CAP", result.stdout + result.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.city, "on")))

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

    def test_the_server_really_answers(self):
        self.city_run("start")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/health")
        self.assertEqual(conn.getresponse().status, 200)
        conn.close()


if __name__ == "__main__":
    unittest.main()
