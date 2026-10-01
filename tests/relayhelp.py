"""Test helpers for the city relay: a fake relay and throwaway joined repos.

FakeRelay speaks the same contract as bin/agent-city-relay.js
(tests/test_agent_city_relay_worker.py), in-process, on 127.0.0.1, so the
client and server tests never touch Cloudflare, the network or a real key.

    relay = FakeRelay(key)          started at once; relay.url, relay.host
    relay.push(dev, line)           another machine sends one line
    relay.reset()                   the relay was made again: empty, seq 0
    relay.talk_key = "..."          cloud-city-2: the relay has this TALK_KEY (None = none);
    relay.say(cid, to, text)        a message waits for the machine (handed down until acked)
    relay.acks_of(cid), relay.chat_rows(), relay.talk_log, relay.offs, relay.talk_headers()
    relay.order(oid, terr, force=False, age=0, **more)   cloud-city-3: an order waits for the machine; it is
                                    handed down with every sync whose talk carries "start" (not off) until
                                    an ack names its oid. relay.start = False: an OLD relay code, it says
                                    nothing about start. relay.force_start = True: orders go down although
                                    the sync carried no start. relay.order_acks, relay.order_acks_of(oid),
                                    relay.start_log, relay.start_offs
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
                  "ua": self.headers.get("User-Agent"), "body": body, "status": None,
                  "talk_header": self.headers.get("X-City-Talk"), "t": time.monotonic()}
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
            reply = {"ok": True, "seq": seq, "lines": out}
            if relay.city:
                # cloud-city-1: the relay keeps this machine's picture (the
                # rules of bin/agent-city-relay.js, tests/test_agent_city_cloud_relay.py).
                view = body.get("view")
                if isinstance(view, dict):
                    relay.view_log.append((dev, view))
                    held = relay.views.get(dev)
                    if "snap" in view:
                        held = relay.views[dev] = {"gen": view.get("gen"), "label": view.get("label"),
                                                   "counts": view.get("counts"),
                                                   "snap": view["snap"], "batches": []}
                    if held is not None and held["gen"] == view.get("gen"):
                        held["label"] = view.get("label")
                        held["counts"] = view.get("counts")
                        if view.get("events"):
                            held["batches"].append(view["events"])
                reply["city"] = True
                reply["gen"] = (relay.views.get(dev) or {}).get("gen", 0)
            # cloud-city-2: talk (the rules of bin/agent-city-relay.js,
            # tests/test_agent_city_cloud_talk_relay.py). Only with the header.
            header = self.headers.get("X-City-Talk")
            if header is not None:
                talk = body.get("talk") if isinstance(body.get("talk"), dict) else {}
                if relay.talk_key is None:
                    reply["talk"] = {"state": "off"}
                elif header != relay.talk_key:
                    reply["talk"] = {"state": "refused"}
                else:
                    relay.talk_log.append((dev, talk))
                    for ack in talk.get("acks") or []:
                        relay.acks.append(ack)
                        relay.talk_msgs = [m for m in relay.talk_msgs if m.get("cid") != ack.get("cid")]
                    for row in talk.get("chat") or []:
                        relay.chat_log.append(row)
                        relay.chat[row.get("k")] = row
                    if talk.get("off"):
                        relay.offs.append(dev)
                        reply["talk"] = {"state": "off"}
                    else:
                        reply["talk"] = {"state": "on", "msgs": [dict(m) for m in relay.talk_msgs[:10]]}
                        # cloud-city-3: start (the rules of bin/agent-city-relay.js,
                        # tests/test_agent_city_cloud_start_relay.py). Only when the talk carries "start".
                        start = talk.get("start")
                        if relay.force_start and not isinstance(start, dict):
                            reply["talk"]["start"] = {"state": "on", "orders": [dict(o) for o in relay.orders[:3]]}
                        if isinstance(start, dict) and relay.start:
                            relay.start_log.append((dev, start))
                            if start.get("off"):
                                relay.start_offs.append(dev)
                                reply["talk"]["start"] = {"state": "off"}
                            else:
                                for ack in start.get("acks") or []:
                                    relay.order_acks.append(ack)
                                    relay.orders = [o for o in relay.orders if o.get("oid") != ack.get("oid")]
                                reply["talk"]["start"] = {"state": "on", "orders": [dict(o) for o in relay.orders[:3]]}
        self._send(200, reply)


class FakeRelay:
    def __init__(self, key=FAKE_KEY):
        self.key = key
        self.lock = threading.Lock()
        self.requests = []
        self.items = []
        self.seq = 0
        self.mode = "ok"
        self.city = False      # cloud-city-1: True = the relay says the cloud page is on
        self.views = {}        # dev -> {"gen", "label", "counts", "snap", "batches": [[msg, ...], ...]}
        self.view_log = []     # every (dev, view) a sync carried while city is on, in order
        # cloud-city-2: talk. talk_key None = the relay has no TALK_KEY.
        self.talk_key = None
        self.talk_msgs = []    # messages handed down with every talk-on sync, until an ack names their cid
        self.talk_log = []     # every (dev, talk body) of a talk-on sync, in order
        self.acks = []         # every ack, in order
        self.chat = {}         # k -> the last row sent with that key (first-seen order)
        self.chat_log = []     # every chat row sent, in order (a row sent twice is here twice)
        self.offs = []         # the devs that said {"off": true}
        # cloud-city-3: start. start False = an old relay code that knows nothing of it.
        self.start = True
        self.force_start = False   # True: orders go down in every talk reply, also when the sync carried no start
        self.orders = []       # orders handed down with every start sync, until an ack names their oid
        self.start_log = []    # every (dev, start body) of a talk-on sync that carried "start", in order
        self.order_acks = []   # every order ack, in order
        self.start_offs = []   # the devs that said start {"off": true}
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

    def say(self, cid, to, text, age=0, **more):
        """cloud-city-2: the owner typed TEXT to window TO on the cloud page."""
        msg = {"cid": cid, "to": to, "text": text, "age": age}
        msg.update(more)
        with self.lock:
            self.talk_msgs.append(msg)

    def order(self, oid, terr, force=False, age=0, **more):
        """cloud-city-3: the owner clicked add agent for territory TERR on the cloud page."""
        order = {"oid": oid, "terr": terr, "force": force, "age": age}
        order.update(more)
        with self.lock:
            self.orders.append(order)

    def order_acks_of(self, oid):
        with self.lock:
            return [a for a in self.order_acks if a.get("oid") == oid]

    def acks_of(self, cid):
        with self.lock:
            return [a for a in self.acks if a.get("cid") == cid]

    def chat_rows(self):
        with self.lock:
            return list(self.chat.values())

    def talk_headers(self):
        with self.lock:
            return [r.get("talk_header") for r in self.requests if r["path"] == "/v1/sync"]

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

    def lose_views(self):
        """The relay lost its pictures (a new database): the next reply says gen 0."""
        with self.lock:
            self.views = {}

    def view_of(self, dev=None):
        """The picture held for DEV (or for the only machine that sent one), or None."""
        with self.lock:
            if dev is None:
                return next(iter(self.views.values()), None)
            return self.views.get(dev)

    def view_events(self, dev=None):
        held = self.view_of(dev)
        return [m for batch in (held or {}).get("batches", []) for m in batch]

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
