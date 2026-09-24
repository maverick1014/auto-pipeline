"""Agent City: a tiny localhost playground that shows spawned agents as people
in a city while a pipeline runs.

Two parts, in one file so the server never imports anything but the stdlib:

  Reducer  Pure. Turns hook lines (one JSON object per line, written by
           bin/agent-city-hook.sh into <dir>/events.jsonl) into city events
           a browser page can animate. No clock, no files, no network.

  Server   python3 agent_city.py serve --dir DIR --port PORT
                   [--idle-min N | --idle-sec S] [--max-log-kb K] [--page PATH]
                   [--assets DIR]
           Tails <dir>/events.jsonl, feeds each line to a Reducer, and streams
           the resulting events to a browser over Server-Sent Events at
           /events. Stays cheap: bounded queues, a bounded log file, an idle
           timeout, at most a handful of browser tabs.

Python standard library only. Runs on Python 3.8+.
"""

import argparse
import json
import os
import queue
import shutil
import signal
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote


# --------------------------------------------------------------------------
# Reducer
# --------------------------------------------------------------------------

KNOWN_ROLES = ("task-manager", "worker", "fast-lane-deputy", "merge-deputy")

TOOL_MAP = {
    "Edit": "Edit", "MultiEdit": "Edit", "NotebookEdit": "Edit",
    "Write": "Write",
    "Bash": "Bash",
    "Read": "Read", "Grep": "Read", "Glob": "Read", "LS": "Read",
    "WebFetch": "Read", "WebSearch": "Read",
}

GOV_BUSY_EVENTS = ("PostToolUse", "PreToolUse", "UserPromptSubmit")
STUCK_NOTIFICATIONS = ("permission_prompt", "idle_prompt")


def _trim(value, limit):
    return value[:limit] if len(value) > limit else value


class Reducer:
    """Pure state machine: hook lines in, city events out.

    .pending  dict sid -> deque of (sub, desc) waiting to be claimed by the
              next SubagentStart in that session, at most 20 per session.
    .sessions dict sid -> {"citizen": id or None} for every session whose
              main agent has been resolved (governor or citizen).
    .agents   dict id -> record, for every citizen (subagent or session-main)
              currently alive in the city.
    """

    def __init__(self, max_agents=40, done_ttl=600):
        self.max_agents = max_agents
        self.done_ttl = done_ttl
        self.pending = {}
        self.sessions = {}
        self.agents = {}
        self.gov_sid = None
        self.gov_state = "idle"
        self._seq = 0

    # -- public API ---------------------------------------------------

    def feed(self, raw, now):
        if not isinstance(raw, dict):
            return []
        ev = raw.get("ev")
        if not isinstance(ev, str) or ev == "":
            return []

        def field(key):
            value = raw.get(key, "")
            return value if isinstance(value, str) else ""

        sid = field("sid")
        aid = field("aid")
        at = field("at")
        tool = field("tool")
        nt = field("nt")
        proj = field("proj")
        role = field("role")
        desc = field("desc")
        sub = field("sub")
        q = field("q")

        if aid:
            events = self._handle_subagent_event(ev, sid, aid, at, tool, q, now)
        else:
            events = self._handle_session_event(ev, sid, role, proj, tool, nt, desc, sub, q, now)

        events.extend(self._sweep(now))
        return events

    def snapshot(self):
        agents = []
        for aid, a in self.agents.items():
            agents.append({
                "id": aid, "role": a["role"], "label": a["label"], "task": a["task"],
                "stuck": a["stuck"], "done": a["done"], "tools": dict(a["tools"]),
            })
        return {"gov": {"state": self.gov_state}, "agents": agents}

    # -- session-main (no aid): governor or citizen --------------------

    def _handle_session_event(self, ev, sid, role, proj, tool, nt, desc, sub, q, now):
        if sid == "":
            return []
        # A bare "about to spawn" PreToolUse is only a queue entry: it must
        # not, by itself, make a never-seen session the governor or a
        # citizen. If the session is already known, it still moves that
        # session's state along like any other event.
        is_queue_pretool = ev == "PreToolUse" and tool in ("Agent", "Task")
        if is_queue_pretool and sid not in self.sessions:
            self._enqueue(sid, sub, desc)
            return []

        events = []
        cid, spawned = self._resolve_session(sid, role, proj)
        events.extend(spawned)
        if ev == "SessionEnd":
            events.extend(self._end_session(sid))
            return events
        if cid is None:
            events.extend(self._governor_event(ev, tool, nt))
        else:
            events.extend(self._citizen_event(ev, cid, tool, nt, q))
            self._touch(cid, now)
        if is_queue_pretool:
            self._enqueue(sid, sub, desc)
        return events

    def _resolve_session(self, sid, role, proj):
        if sid in self.sessions:
            return self.sessions[sid]["citizen"], []
        if role == "" and self.gov_sid is None:
            self.gov_sid = sid
            self.sessions[sid] = {"citizen": None}
            return None, []
        if role != "":
            norm_role = self._normalize_role(role)
            label = role
        else:
            norm_role = "task-manager"
            label = "session"
        task = proj if proj else label
        label = _trim(label, 30)
        task = _trim(task, 40)
        cid = "s:" + sid
        self.sessions[sid] = {"citizen": cid}
        self._create_agent(cid, norm_role, label, task, owner=sid, kind="session")
        return cid, [{"type": "spawn", "id": cid, "role": norm_role, "label": label, "task": task}]

    def _governor_event(self, ev, tool, nt):
        new_state = None
        if ev in GOV_BUSY_EVENTS:
            new_state = "busy"
        elif ev == "Notification" and nt in STUCK_NOTIFICATIONS:
            new_state = "waiting"
        elif ev == "Stop":
            new_state = "idle"
        if new_state is None or new_state == self.gov_state:
            return []
        self.gov_state = new_state
        return [{"type": "gov", "state": new_state}]

    def _citizen_event(self, ev, cid, tool, nt, q):
        agent = self.agents.get(cid)
        if agent is None or agent["done"]:
            return []
        if ev == "PreToolUse" and tool == "AskUserQuestion":
            return self._make_stuck(cid, _trim(q, 60), tool)
        if ev == "PermissionRequest":
            return self._make_stuck(cid, "", tool)
        if ev == "Notification" and nt in STUCK_NOTIFICATIONS:
            return self._make_stuck(cid, "", "")
        if ev == "PermissionDenied":
            return self._make_answer_if_stuck(cid, False)
        if ev in ("PostToolUse", "UserPromptSubmit"):
            out = self._make_answer_if_stuck(cid, True)
            if ev == "PostToolUse" and tool:
                out = out + self._tool_event(cid, tool)
            return out
        return []

    def _end_session(self, sid):
        events = []
        owned = [aid for aid, a in self.agents.items()
                 if a["kind"] == "subagent" and a["owner"] == sid]
        for aid in owned:
            events.extend(self._finish_and_leave(aid))
        info = self.sessions.pop(sid, None)
        if info is not None and info["citizen"] is not None:
            events.extend(self._finish_and_leave(info["citizen"]))
        if self.gov_sid == sid:
            self.gov_sid = None
            if self.gov_state != "idle":
                self.gov_state = "idle"
                events.append({"type": "gov", "state": "idle"})
        self.pending.pop(sid, None)
        return events

    def _finish_and_leave(self, aid):
        agent = self.agents.get(aid)
        if agent is None:
            return []
        events = []
        if not agent["done"]:
            events.append({"type": "done", "id": aid})
        events.append({"type": "leave", "id": aid})
        del self.agents[aid]
        return events

    # -- subagents (aid set) -------------------------------------------

    def _handle_subagent_event(self, ev, sid, aid, at, tool, q, now):
        agent = self.agents.get(aid)
        events = []
        if agent is None:
            if ev == "SubagentStop":
                return []
            if ev == "SubagentStart":
                events.extend(self._spawn_subagent(sid, aid, at))
                self._touch(aid, now)
                return events
            events.extend(self._auto_spawn_subagent(sid, aid, at))
            agent = self.agents[aid]
        elif ev == "SubagentStart":
            return []

        if agent["done"]:
            return events

        if ev == "PostToolUse":
            events.extend(self._make_answer_if_stuck(aid, True))
            if tool:
                events.extend(self._tool_event(aid, tool))
        elif ev == "PermissionRequest":
            events.extend(self._make_stuck(aid, "", tool))
        elif ev == "PermissionDenied":
            events.extend(self._make_answer_if_stuck(aid, False))
        elif ev == "PreToolUse" and tool == "AskUserQuestion":
            events.extend(self._make_stuck(aid, _trim(q, 60), tool))
        elif ev == "UserPromptSubmit":
            events.extend(self._make_answer_if_stuck(aid, True))
        elif ev == "SubagentStop":
            events.extend(self._mark_done(aid, now))

        self._touch(aid, now)
        return events

    def _spawn_subagent(self, sid, aid, at):
        role = self._normalize_role(at)
        label = _trim(at, 30)
        desc = self._take_queued(sid, at)
        task = _trim(desc, 40) if desc is not None else _trim(at, 40)
        self._create_agent(aid, role, label, task, owner=sid, kind="subagent")
        return [{"type": "spawn", "id": aid, "role": role, "label": label, "task": task}]

    def _auto_spawn_subagent(self, sid, aid, at):
        role = self._normalize_role(at)
        label = _trim(at, 30)
        task = _trim(at, 40)
        self._create_agent(aid, role, label, task, owner=sid, kind="subagent")
        return [{"type": "spawn", "id": aid, "role": role, "label": label, "task": task}]

    # -- shared helpers --------------------------------------------------

    def _normalize_role(self, value):
        return value if value in KNOWN_ROLES else "other"

    def _create_agent(self, aid, role, label, task, owner, kind):
        self._seq += 1
        self.agents[aid] = {
            "role": role, "label": label, "task": task,
            "stuck": False, "done": False, "done_at": 0.0,
            "tools": {"Edit": 0, "Write": 0, "Bash": 0, "Read": 0, "Other": 0},
            "seq": self._seq, "owner": owner, "kind": kind,
        }

    def _touch(self, aid, now):
        self._seq += 1
        if aid in self.agents:
            self.agents[aid]["seq"] = self._seq

    def _tool_event(self, aid, tool):
        kind = TOOL_MAP.get(tool, "Other")
        self.agents[aid]["tools"][kind] += 1
        return [{"type": "tool", "id": aid, "tool": kind}]

    def _make_stuck(self, aid, question, tool):
        agent = self.agents.get(aid)
        if agent is None or agent["stuck"] or agent["done"]:
            return []
        agent["stuck"] = True
        return [{"type": "stuck", "id": aid, "question": question, "tool": tool}]

    def _make_answer_if_stuck(self, aid, ok):
        agent = self.agents.get(aid)
        if agent is None or not agent["stuck"]:
            return []
        agent["stuck"] = False
        return [{"type": "answer", "id": aid, "ok": ok}]

    def _mark_done(self, aid, now):
        agent = self.agents.get(aid)
        if agent is None or agent["done"]:
            return []
        agent["done"] = True
        agent["done_at"] = now
        return [{"type": "done", "id": aid}]

    def _enqueue(self, sid, sub, desc):
        q = self.pending.get(sid)
        if q is None:
            q = deque(maxlen=20)
            self.pending[sid] = q
        q.append((sub, desc))

    def _take_queued(self, sid, at):
        q = self.pending.get(sid)
        if not q:
            return None
        for i, (sub, desc) in enumerate(q):
            if sub == at:
                del q[i]
                return desc
        for i, (sub, desc) in enumerate(q):
            if sub == "":
                del q[i]
                return desc
        return None

    def _forget_citizen(self, aid):
        agent = self.agents.get(aid)
        if agent is not None and agent["kind"] == "session":
            sid = agent["owner"]
            if self.sessions.get(sid, {}).get("citizen") == aid:
                self.sessions.pop(sid, None)

    def _sweep(self, now):
        events = []
        expired = [aid for aid, a in self.agents.items()
                   if a["done"] and (now - a["done_at"]) > self.done_ttl]
        for aid in expired:
            events.append({"type": "leave", "id": aid})
            self._forget_citizen(aid)
            del self.agents[aid]
        while len(self.agents) > self.max_agents:
            oldest = min(self.agents, key=lambda k: self.agents[k]["seq"])
            events.append({"type": "leave", "id": oldest})
            self._forget_citizen(oldest)
            del self.agents[oldest]
        return events


# --------------------------------------------------------------------------
# Server
# --------------------------------------------------------------------------

MAX_CLIENTS = 4
QUEUE_MAXSIZE = 500
PING_INTERVAL = 2.0
TAIL_INTERVAL = 0.25

FALLBACK_PAGE = (
    b"<!doctype html><html><head><meta charset=\"utf-8\">"
    b"<title>Agent City</title></head><body></body></html>"
)

ASSET_PREFIX = "/assets/"
ASSET_CONTENT_TYPES = {
    ".js": "application/javascript",
    ".glb": "model/gltf-binary",
    ".png": "image/png",
    ".txt": "text/plain; charset=utf-8",
}
ASSET_DEFAULT_TYPE = "application/octet-stream"

_DROP = object()  # sentinel put in a client's queue to tell it to disconnect


def _encode_event(obj):
    return ("data: " + json.dumps(obj) + "\n\n").encode("utf-8")


class _Client:
    """One open /events connection: just its outgoing queue."""

    def __init__(self):
        self.queue = queue.Queue(maxsize=QUEUE_MAXSIZE)


class CityState:
    """Thread-safe home for the Reducer, health counters and SSE clients."""

    def __init__(self, max_agents=40, done_ttl=600):
        self.lock = threading.Lock()
        self.reducer = Reducer(max_agents=max_agents, done_ttl=done_ttl)
        self.lines = 0
        self.clients = []
        self.idle_since = time.monotonic()

    def add_client(self):
        with self.lock:
            if len(self.clients) >= MAX_CLIENTS:
                return None
            client = _Client()
            snap = self.reducer.snapshot()
            snap = {"type": "snapshot", "gov": snap["gov"], "agents": snap["agents"]}
            client.queue.put_nowait(_encode_event(snap))
            self.clients.append(client)
            return client

    def remove_client(self, client):
        with self.lock:
            if client in self.clients:
                self.clients.remove(client)
            if not self.clients:
                self.idle_since = time.monotonic()

    def client_count(self):
        with self.lock:
            return len(self.clients)

    def health(self):
        with self.lock:
            return {
                "ok": True,
                "lines": self.lines,
                "agents": len(self.reducer.agents),
                "clients": len(self.clients),
            }

    def feed_line(self, obj, now):
        with self.lock:
            self.lines += 1
            events = self.reducer.feed(obj, now)
            for ev in events:
                data = _encode_event(ev)
                dead = []
                for client in self.clients:
                    try:
                        client.queue.put_nowait(data)
                    except queue.Full:
                        dead.append(client)
                for client in dead:
                    self._drop(client)

    def _drop(self, client):
        """A slow client fell behind its queue; disconnect it."""
        if client in self.clients:
            self.clients.remove(client)
        try:
            while True:
                client.queue.get_nowait()
        except queue.Empty:
            pass
        try:
            client.queue.put_nowait(_DROP)
        except queue.Full:
            pass


class CityHandler(BaseHTTPRequestHandler):
    # HTTP/1.1: without this, http.client treats a Content-Length-less
    # response (our /events stream) as "will close", and nulls out its
    # socket handle before a client can shut it down to disconnect.
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass  # health counters already track what matters; stay quiet

    def do_GET(self):
        if self.path == "/":
            self._send_page()
        elif self.path == "/health":
            self._send_health()
        elif self.path == "/events":
            self._send_events()
        elif self.path.startswith(ASSET_PREFIX):
            self._send_asset(self.path[len(ASSET_PREFIX):])
        else:
            self.send_error(404)

    def _send_page(self):
        body = self.server.page_bytes
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_health(self):
        body = json.dumps(self.server.city.health()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_asset(self, raw_rel):
        assets_root = self.server.assets_dir
        rel = unquote(raw_rel)
        full = os.path.realpath(os.path.join(assets_root, rel))
        if full != assets_root and not full.startswith(assets_root + os.sep):
            self.send_error(404)
            return
        if not os.path.isfile(full):
            self.send_error(404)
            return
        ext = os.path.splitext(full)[1].lower()
        content_type = ASSET_CONTENT_TYPES.get(ext, ASSET_DEFAULT_TYPE)
        try:
            size = os.path.getsize(full)
            with open(full, "rb") as fh:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(size))
                self.send_header("Cache-Control", "max-age=86400")
                self.end_headers()
                shutil.copyfileobj(fh, self.wfile)
        except OSError:
            self.send_error(404)

    def _send_events(self):
        city = self.server.city
        client = city.add_client()
        if client is None:
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self._stream(client)
        except Exception:
            pass
        finally:
            city.remove_client(client)

    def _stream(self, client):
        last_ping = time.monotonic()
        while True:
            try:
                msg = client.queue.get(timeout=0.5)
            except queue.Empty:
                if time.monotonic() - last_ping >= PING_INTERVAL:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    last_ping = time.monotonic()
                continue
            if msg is _DROP:
                return
            self.wfile.write(msg)
            self.wfile.flush()


def _read_on(path):
    try:
        with open(path) as fh:
            parts = fh.read().split()
        if len(parts) != 2:
            return None
        return int(parts[0]), int(parts[1])
    except (OSError, ValueError):
        return None


def _write_on(path, pid, port):
    with open(path, "w") as fh:
        fh.write("%d %d\n" % (pid, port))


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _load_page(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return FALLBACK_PAGE


def _split_lines(data):
    parts = data.split(b"\n")
    return parts[:-1], parts[-1]


def _consume_line(raw_line, city):
    text = raw_line.decode("utf-8", errors="replace")
    try:
        obj = json.loads(text)
    except ValueError:
        return
    city.feed_line(obj, time.monotonic())


def _read_available(fh, offset, buf, city):
    fh.seek(0, os.SEEK_END)
    end = fh.tell()
    if end <= offset:
        return offset, buf
    fh.seek(offset)
    chunk = fh.read(end - offset)
    lines, buf = _split_lines(buf + chunk)
    for raw_line in lines:
        _consume_line(raw_line, city)
    return fh.tell(), buf


def tail_loop(directory, city, max_log_bytes, stop_event, request_shutdown,
              idle_seconds, initial_skip):
    """Watch DIR/events.jsonl, feed new lines to the city, rotate when big."""
    log_path = os.path.join(directory, "events.jsonl")
    rotated_path = log_path + ".1"
    fh = None
    offset = 0
    buf = b""
    skip = initial_skip

    while not stop_event.is_set():
        if city.client_count() == 0 and time.monotonic() - city.idle_since >= idle_seconds:
            request_shutdown()
            return

        if fh is None:
            try:
                fh = open(log_path, "rb")
            except OSError:
                time.sleep(TAIL_INTERVAL)
                continue
            size_now = os.fstat(fh.fileno()).st_size
            offset = min(skip, size_now)
            skip = 0
            buf = b""

        offset, buf = _read_available(fh, offset, buf, city)

        try:
            on_disk = os.path.getsize(log_path)
        except OSError:
            on_disk = 0

        if on_disk >= max_log_bytes:
            try:
                os.replace(log_path, rotated_path)
            except OSError:
                pass
            else:
                offset, buf = _read_available(fh, offset, buf, city)
                fh.close()
                fh = None
                # Leave a fresh, empty file at the original path: the next
                # writer append just re-creates it anyway, but a reader
                # (or a test) checking the path right after rotation should
                # still find it there.
                try:
                    open(log_path, "ab").close()
                except OSError:
                    pass
                offset = 0
                buf = b""

        time.sleep(TAIL_INTERVAL)


def _build_parser():
    parser = argparse.ArgumentParser(prog="agent_city.py")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve")
    serve.add_argument("--dir", required=True)
    serve.add_argument("--port", type=int, required=True)
    serve.add_argument("--idle-min", type=float, default=30.0)
    serve.add_argument("--idle-sec", type=float, default=None)
    serve.add_argument("--max-log-kb", type=float, default=256.0)
    serve.add_argument("--page", default=None)
    serve.add_argument("--assets", default=None)
    return parser


def cmd_serve(args):
    directory = os.path.abspath(args.dir)
    os.makedirs(directory, exist_ok=True)
    on_path = os.path.join(directory, "on")

    existing = _read_on(on_path)
    if existing is not None and _pid_alive(existing[0]):
        print("already running http://127.0.0.1:%d" % existing[1])
        return 0

    idle_seconds = args.idle_sec if args.idle_sec is not None else args.idle_min * 60.0
    max_log_bytes = int(args.max_log_kb * 1024)
    page_path = args.page or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "agent-city.html")
    page_bytes = _load_page(page_path)
    assets_dir = os.path.realpath(args.assets) if args.assets else os.path.realpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-city-assets"))

    log_path = os.path.join(directory, "events.jsonl")
    try:
        initial_skip = os.path.getsize(log_path)
    except OSError:
        initial_skip = 0

    city = CityState()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), CityHandler)
    server.daemon_threads = True
    server.city = city
    server.page_bytes = page_bytes
    server.assets_dir = assets_dir

    port = server.server_address[1]
    _write_on(on_path, os.getpid(), port)

    stop_event = threading.Event()

    def request_shutdown():
        if stop_event.is_set():
            return
        stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    def on_signal(signum, frame):
        request_shutdown()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    tail = threading.Thread(
        target=tail_loop,
        args=(directory, city, max_log_bytes, stop_event, request_shutdown,
              idle_seconds, initial_skip),
        daemon=True,
    )
    tail.start()

    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        try:
            os.remove(on_path)
        except OSError:
            pass
    return 0


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.command == "serve":
        return cmd_serve(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
