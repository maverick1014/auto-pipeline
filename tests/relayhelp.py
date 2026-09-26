"""Test helpers for the city relay: a fake relay and throwaway joined repos.

FakeRelay speaks the same contract as bin/agent-city-relay.js
(tests/test_agent_city_relay_worker.py), in-process, on 127.0.0.1, so the
client and server tests never touch Cloudflare, the network or a real key.

    relay = FakeRelay(key)          started at once; relay.url, relay.host
    relay.push(dev, line)           another machine sends one line
    relay.reset()                   the relay was made again: empty, seq 0
    relay.requests                  every POST it got: {"path", "auth", "body", "status"}
    relay.sent_lines()              lines of the syncs it accepted (200) only
    relay.mode = "ok" | "refuse" | "error" | "garbage" | "redirect"
    relay.redirect_to = url, relay.redirect_code = 302   (mode "redirect")
    relay.delay = seconds           wait this long before answering a sync
    relay.stop()                    down: the port stops answering

make_repo(base, name, origin=..., ignore_secrets=True, user="Ann")
    a git repo with one commit, an origin remote and .secrets/ ignored.
join(repo, address, key)
    write <repo>/.secrets/agent-city-relay by hand, the way a person would.
hook_line(repo, proj=None, **fields)
    one events.jsonl line the way bin/agent-city-hook.sh writes it
    ("proj" is only the folder name of the cwd, as the real hook writes it).
"""

import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FAKE_KEY = "fake-team-key-for-tests-0001"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, obj=None, raw=None):
        record = getattr(self, "record", None)
        if record is not None:
            record["status"] = code
        data = raw if raw is not None else json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        relay = self.server.relay
        self.record = {"path": self.path, "auth": self.headers.get("Authorization"),
                       "body": None, "status": None, "method": "GET"}
        with relay.lock:
            relay.requests.append(self.record)
        if self.path == "/":
            self._send(200, {"ok": True, "relay": "agent-city", "v": 1})
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        relay = self.server.relay
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else None
        except ValueError:
            body = None
        record = {"path": self.path, "auth": self.headers.get("Authorization"),
                  "ua": self.headers.get("User-Agent"), "body": body, "status": None}
        with relay.lock:
            relay.requests.append(record)
            mode = relay.mode
            delay = relay.delay
        if delay:
            time.sleep(delay)
        self.record = record
        if self.path != "/v1/sync":
            self._send(404, {"ok": False, "error": "not found"})
            return
        if mode == "redirect":
            self.record["status"] = relay.redirect_code
            self.send_response(relay.redirect_code)
            self.send_header("Location", relay.redirect_to + self.path)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if mode == "error":
            self._send(500, {"ok": False, "error": "boom"})
            return
        if mode == "garbage":
            self._send(200, raw=b"<html>not json</html>")
            return
        if mode == "refuse" or self.headers.get("Authorization") != "Bearer " + relay.key:
            self._send(401, {"ok": False, "error": "wrong key"})
            return
        if not isinstance(body, dict):
            self._send(400, {"ok": False, "error": "bad body"})
            return
        dev = body.get("dev")
        after = body.get("after", 0)
        with relay.lock:
            if body.get("lines"):
                relay.seq += 1
                for line in body["lines"]:
                    relay.items.append((relay.seq, dev, line))
            out = [{"seq": s, "dev": d, "line": l}
                   for (s, d, l) in relay.items if s > after and d != dev]
            seq = relay.seq
        self._send(200, {"ok": True, "seq": seq, "lines": out})


class FakeRelay:
    def __init__(self, key=FAKE_KEY):
        self.key = key
        self.lock = threading.Lock()
        self.requests = []
        self.items = []
        self.seq = 0
        self.mode = "ok"
        self.delay = 0
        self.redirect_to = ""
        self.redirect_code = 302
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.daemon_threads = True
        self.server.relay = self
        self.port = self.server.server_address[1]
        self.host = "127.0.0.1:%d" % self.port
        self.url = "http://" + self.host
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        self.stopped = False

    def push(self, dev, line):
        with self.lock:
            self.seq += 1
            self.items.append((self.seq, dev, line))
            return self.seq

    def reset(self):
        """The relay was made again (new database, or a dev relay restarted):
        empty store, seq back to 0."""
        with self.lock:
            self.items = []
            self.seq = 0

    def sync_bodies(self):
        with self.lock:
            return [r["body"] for r in self.requests if r["path"] == "/v1/sync"]

    def sent_lines(self):
        """Lines the relay accepted (answered 200). A refused or failed sync
        is still in self.requests, but its lines were not delivered."""
        with self.lock:
            bodies = [r["body"] for r in self.requests
                      if r["path"] == "/v1/sync" and r["status"] == 200
                      and isinstance(r["body"], dict)]
        return [line for body in bodies for line in body.get("lines") or []]

    def stop(self):
        if not self.stopped:
            self.stopped = True
            self.server.shutdown()
            self.server.server_close()


def _git(*args, cwd=None):
    return subprocess.run(["git"] + list(args), cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def make_repo(base, name="shop", origin="git@github.com:Acme/Shop.git",
              ignore_secrets=True, user="Ann"):
    path = os.path.realpath(os.path.join(base, name))
    os.makedirs(path)
    _git("init", "-q", "-b", "main", path)
    _git("-C", path, "config", "user.email", "ann@example.com")
    _git("-C", path, "config", "user.name", user)
    if ignore_secrets:
        with open(os.path.join(path, ".gitignore"), "w") as fh:
            fh.write(".secrets/\n")
    with open(os.path.join(path, "seed.txt"), "w") as fh:
        fh.write("x\n")
    _git("-C", path, "add", "-A")
    _git("-C", path, "commit", "-q", "-m", "seed")
    if origin:
        _git("-C", path, "remote", "add", "origin", origin)
    return path


def add_worktree(repo, branch="feature/relay"):
    path = repo + "_wt"
    _git("-C", repo, "worktree", "add", "-q", "-b", branch, path)
    return os.path.realpath(path)


def join(repo, address, key=FAKE_KEY):
    folder = os.path.join(repo, ".secrets")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "agent-city-relay")
    with open(path, "w") as fh:
        fh.write("address=%s\nkey=%s\n" % (address, key))
    os.chmod(path, 0o600)
    return path


def hook_line(repo, proj=None, **fields):
    """proj: the session's cwd. Like the real hook, the line keeps only its
    folder name (bin/agent-city-hook.sh: proj=${cwd##*/})."""
    line = {"ev": "PostToolUse", "sid": "s1", "aid": "", "at": "", "tool": "Bash",
            "nt": "", "proj": os.path.basename(proj or repo), "role": "", "desc": "",
            "sub": "", "q": "", "klen": "12", "repo": os.path.join(repo, ".git"), "kind": ""}
    line.update(fields)
    return line


def wait_for(check, timeout=8.0, step=0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(step)
    return check()
