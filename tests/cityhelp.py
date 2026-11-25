"""city-roles: a territory's governor is the live holder of its repo's main manager lock
(tests/test_agent_city_roles.py). A CityState test that wants a governor names it here instead of
writing lock files: CityState(..., main_fn=Mains({identity: sid})).
"""

import os
import http.client
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
ROOT_BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
if ROOT_BIN not in sys.path:
    sys.path.insert(0, ROOT_BIN)
import agent_city as ac  # noqa: E402
import agent_city  # noqa: E402
import queue


class Mains(dict):
    """identity -> sid of that territory's main manager; usable as CityState(main_fn=...).
    The pid is this test process (alive), so only the sid decides."""

    def __call__(self, identity):
        sid = self.get(identity)
        return (os.getpid(), sid) if sid else None


def lock_file(gitdir, sid, pid=None):
    """Write <gitdir>/agent_main.lock for SID (a server started as a process reads the file)."""
    os.makedirs(gitdir, exist_ok=True)
    with open(os.path.join(gitdir, "agent_main.lock"), "w") as fh:
        fh.write("%d 2026-09-30 10:00 %s -\n" % (os.getpid() if pid is None else pid, sid))


HERE = os.path.dirname(os.path.abspath(__file__))


ROOT = os.path.dirname(HERE)


SERVER = os.path.join(ROOT, "bin", "agent_city.py")


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


def git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    return subprocess.run(["git", "-C", cwd] + list(args), check=True, capture_output=True, env=env,
                          stdin=subprocess.DEVNULL, text=True).stdout.strip()


def make_repo(base):
    """A main checkout <base>/app on branch main with one commit, and a linked
    worktree <base>/wt-a on branch feat-a with one more commit."""
    root = os.path.join(base, "app")
    os.mkdir(root)
    git(root, "init", "-q", "-b", "main")
    with open(os.path.join(root, "a.txt"), "w") as fh:
        fh.write("a\n")
    git(root, "add", "a.txt")
    git(root, "commit", "-q", "-m", "one")
    wt = os.path.join(base, "wt-a")
    git(root, "worktree", "add", "-q", "-b", "feat-a", wt)
    with open(os.path.join(wt, "b.txt"), "w") as fh:
        fh.write("b\n")
    git(wt, "add", "b.txt")
    git(wt, "commit", "-q", "-m", "two")
    return os.path.realpath(root), os.path.realpath(wt)


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    # a later write in the same second must still look changed (size or mtime)
    st = os.stat(path)
    os.utime(path, (st.st_atime, st.st_mtime + write.bump))
    write.bump += 1


def drain(client):
    out = []
    while not client.queue.empty():
        out.append(json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1]))
    return out


def snapshot(st):
    client = st.add_client()
    return json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1]), client


HOOK = os.path.join(ROOT, "bin", "agent-city-hook.sh")


BASH = shutil.which("bash")


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


CONF = "main_manager=opus-5.5:high\npermission_mode=auto\n"


PROMPT = ("You were opened from the Agent City page. Do your start steps now, then stop and wait: "
          "the owner will talk to you from the city page.")


def line(ev, sid, repo, aid="", role=""):
    return {"ev": ev, "sid": sid, "aid": aid, "at": "", "tool": "Read", "nt": "", "proj": "shop", "role": role,
            "desc": "", "sub": "", "q": "", "klen": "", "repo": repo, "kind": ""}


def configure_text(conf):
    """Write old key=value lines as Configure options into $CLAUDE_CONFIG_DIR/settings.json."""
    cfg = os.environ["CLAUDE_CONFIG_DIR"]
    os.makedirs(cfg, exist_ok=True)
    path = os.path.join(cfg, "settings.json")
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:
        data = {}
    options = data.setdefault("pluginConfigs", {}).setdefault("auto-pipeline@auto-pipeline", {}).setdefault("options", {})
    for line in conf.splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = (x.strip() for x in line.split("=", 1))
        if key in ("worker", "fast_lane_deputy", "merge_deputy"):
            key = "helper_model"
        options[key] = value
    with open(path, "w") as fh:
        json.dump(data, fh)


class AddCase(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_add_"))
        # the machine's own ~/.claude (auto-pipeline.conf, permission_mode) never decides a test
        fake_home = os.path.join(self.base, "_home")
        os.makedirs(fake_home)
        env = mock.patch.dict(os.environ, {"HOME": fake_home,
                                           "CLAUDE_CONFIG_DIR": os.path.join(fake_home, ".claude"),
                                           "AUTO_PIPELINE_USER_CONF": os.path.join(fake_home, "none.conf")})
        env.start()
        self.addCleanup(env.stop)
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
        """A repo folder <base>/<name> with a .git dir -> its identity. CONF (old key=value
        text): settings-configure 2026-11-25, the values go into Configure (user level, the
        fake CLAUDE_CONFIG_DIR, last write wins) and the folder gets its task file."""
        folder = os.path.join(self.base, name)
        os.makedirs(os.path.join(folder, ".git"))
        if conf is not None:
            open(os.path.join(folder, "agent_todo.txt"), "a").close()
            configure_text(conf)
        return os.path.join(folder, ".git")

    def opener(self, folder, title, command):
        self.calls.append((folder, title, command))
        return self.answer

    def make(self, **kw):
        args = dict(decisions_path=os.path.join(self.base, "decisions.jsonl"), world_path=None, token="tok",
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


QS = [{"question": "Which port?", "header": "Port",
       "options": [{"label": "4791", "description": "temp city"},
                   {"label": "4792", "description": "other"}],
       "multiSelect": False}]


# city-roles: the governor is the live holder of the repo's main manager lock, so the shop repo of
# these tests is a real folder whose lock names "gs" (the gov_next() default) with this test
# process as its live pid.
SHOP_BASE = os.path.realpath(tempfile.mkdtemp(prefix="city_shop_"))


SHOP = os.path.join(SHOP_BASE, "r", "shop", ".git")


def q_body(sid="s2", aid="", questions=None, repo=SHOP, role="worker"):
    return {"sid": sid, "aid": aid, "at": "worker" if aid else "", "role": role,
            "cwd": "/r/shop", "repo": repo, "tool": "AskUserQuestion",
            "input": {"questions": questions or QS}}


class InteractCase(ServerCase):
    GOV_WAIT = "60"

    def setUp(self):
        super().setUp()
        self.decisions = os.path.join(self.base, "home", "agent-city", "decisions.jsonl")

    def start(self, *extra, wait=True):
        args = list(extra) or ["--idle-sec", "60", "--gov-wait-sec", self.GOV_WAIT,
                               "--decisions", self.decisions]
        return super().start(*args, wait=wait)

    def token(self):
        with open(os.path.join(self.dir, "token")) as fh:
            return fh.read().strip()

    @property
    def origin(self):
        return "http://127.0.0.1:%d" % self.port

    def api(self, method, path, body=None, token=True, origin=None, host=None, raw=None,
            ctype="application/json", timeout=40):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        headers = {}
        if token is True:
            headers["X-City-Token"] = self.token()
        elif token:
            headers["X-City-Token"] = token
        if origin:
            headers["Origin"] = origin
        if host:
            headers["Host"] = host
        data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
        if data is not None:
            headers["Content-Type"] = ctype
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        text = resp.read()
        conn.close()
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = text
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, parsed

    def ask(self, body):
        status, _, out = self.api("POST", "/api/ask", body)
        self.assertEqual(status, 200, out)
        return out["id"]

    def asks(self):
        return self.api("GET", "/api/asks")[2]["asks"]

    def view(self, ask_id):
        return next((a for a in self.asks() if a["id"] == ask_id), None)

    def decide(self, body, origin=True):
        return self.api("POST", "/api/decide", body, origin=self.origin if origin is True else origin)

    def gov_next(self, sid="gs", repo=SHOP, watcher="w1", timeout=0):
        path = "/api/gov/next?sid=%s&repo=%s&watcher=%s&timeout=%s" % (sid, repo, watcher, timeout)
        return self.api("GET", path, timeout=timeout + 20)[2]

    def decisions_lines(self):
        if not os.path.exists(self.decisions):
            return []
        with open(self.decisions) as fh:
            return [json.loads(l) for l in fh if l.strip()]


class AskHookCase(InteractCase):
    def setUp(self):
        super().setUp()
        self.work = os.path.join(self.base, "work")
        os.makedirs(self.work)
        # city-roles: "gov-1" (stop_payload's default sid) holds the main manager lock of this
        # folder, so its gov-watch is the governor (tests/test_agent_city_roles.py)
        with open(os.path.join(self.work, "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-09-30 10:00 gov-1 -\n" % os.getpid())
        self.hooks = []

    def tearDown(self):
        for p in self.hooks:
            if p.poll() is None:
                p.kill()
        super().tearDown()

    def hook(self, stdin, *args, env=None):
        full = dict(os.environ, AGENT_CITY_DIR=self.dir, AGENT_ROLE="worker")
        full.pop("CLAUDE_CODE_REMOTE", None)
        full.update(env or {})
        proc = subprocess.Popen([sys.executable, SERVER, "ask"] + (list(args) or ["--max-wait-sec", "30"]),
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=full)
        proc.stdin.write(stdin)
        proc.stdin.close()
        self.hooks.append(proc)
        return proc

    def first_ask(self):
        found = wait_for(lambda: self.asks(), timeout=8)
        self.assertTrue(found, "the hook never filed its ask")
        return found[0]

    def finish(self, proc, timeout=15):
        out = proc.stdout.read()
        err = proc.stderr.read()
        proc.wait(timeout)
        return proc.returncode, out, err


def stop_payload(cwd, sid="gov-1"):
    return json.dumps({"session_id": sid, "transcript_path": "/x/t.jsonl", "cwd": cwd,
                       "permission_mode": "auto", "hook_event_name": "Stop",
                       "stop_hook_active": False}).encode("utf-8")


class BuildCase(unittest.TestCase):
    """A CityState with one repo whose main manager is "tm" (kept for tests/test_agent_city_idea_server.py)."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_q_state_")
        self.root, self.wt = make_repo(self.base)
        self.ident = os.path.join(self.root, ".git")
        self.terr = ac.territory_id(self.ident)
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"),
                               start_repo=self.ident,
                               main_fn=Mains({self.ident: "tm"}))   # city-roles: "tm" is the main manager
        self.snap, self.client = snapshot(self.st)
        self.st.feed_line(self.line("tm", tool="Read"), 1000.0)
        drain(self.client)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def line(self, sid, aid="", kind="", file="", tool="Edit", wt=""):
        return {"ev": "PostToolUse", "sid": sid, "aid": aid, "at": "worker" if aid else "", "tool": tool,
                "nt": "", "proj": "app", "role": "", "desc": "", "sub": "", "q": "", "klen": "",
                "repo": self.ident, "kind": kind, "ask": "", "wt": wt, "file": file}


EVENT_KEYS = {
    "spawn": {"type", "id", "role", "label", "task"},
    "tool": {"type", "id", "tool", "name"},  # city-work-anim bounce 1: + "file" / "desc" when known
    "stuck": {"type", "id", "question", "tool"},
    "answer": {"type", "id", "ok"},
    "done": {"type", "id"},
    "leave": {"type", "id"},
    "gov": {"type", "state"},
    # city-status (tests/test_agent_city_status.py): a session citizen's status events
    "waiting": {"type", "id"},
    "background": {"type", "id"},
    "idle": {"type", "id"},
    "resume": {"type", "id"},
}


# keys an event may carry only sometimes (tests/test_agent_city_steps.py)
OPTIONAL_KEYS = {"tool": {"file", "desc"}}


def R(ev, sid="s1", aid="", at="", tool="", nt="", proj="shop", role="", desc="", sub="", q=""):
    return {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": nt,
            "proj": proj, "role": role, "desc": desc, "sub": sub, "q": q}


class Case(unittest.TestCase):
    def setUp(self):
        self.r = agent_city.Reducer()
        self.t = 1000.0
        self.all = []

    def feed(self, raw, dt=1.0):
        self.t += dt
        out = self.r.feed(raw, self.t)
        self.assertIsInstance(out, list)
        for event in out:
            self.assertIn(event.get("type"), EVENT_KEYS, event)
            self.assertEqual(set(event) - OPTIONAL_KEYS.get(event["type"], set()), EVENT_KEYS[event["type"]], event)
        self.all.extend(out)
        return out

    def types(self, events):
        return [e["type"] for e in events]

    def govern(self, sid="s1"):
        """Make sid the governor session."""
        self.feed(R("UserPromptSubmit", sid=sid))

    def spawn(self, aid="a1", at="worker", sid="s1"):
        return self.feed(R("SubagentStart", sid=sid, aid=aid, at=at))


class RosterCase(unittest.TestCase):
    """CityState with a roster file, real lock files and real pids. restart() = a new CityState
    on the same world.json and roster.json, the old one thrown away: a server restart."""

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_roster_"))
        self.world = os.path.join(self.base, "world.json")
        self.city_dir = os.path.join(self.base, "city")
        os.makedirs(self.city_dir)
        self.roster = os.path.join(self.city_dir, "roster.json")
        self.repo = os.path.join(self.base, "repoA", ".git")
        self.repo_b = os.path.join(self.base, "repoB", ".git")
        os.makedirs(self.repo)
        os.makedirs(self.repo_b)
        self.procs = []
        self.client = None
        self.st = self.make_state()

    def make_state(self, **kw):
        kw.setdefault("roster_path", self.roster)
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.world,
                            start_repo=self.repo, **kw)

    def restart(self):
        if self.client is not None:
            self.st.remove_client(self.client)
            self.client = None
        self.st = self.make_state()

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
                p.wait()
        shutil.rmtree(self.base, ignore_errors=True)

    # -- helpers ---------------------------------------------------------

    def live(self):
        """A live process: a stand-in session."""
        proc = subprocess.Popen(["sleep", "120"])
        self.procs.append(proc)
        return proc

    def kill(self, proc):
        proc.kill()
        proc.wait()

    def write_lock(self, pid, sid="-", repo=None, old=False):
        path = os.path.join(self.repo if repo is None else repo, "agent_main.lock")
        with open(path, "w") as fh:
            if old:
                fh.write("%s 2026-09-30 20:03\n" % pid)
            else:
                fh.write("%s 2026-09-30 20:03 %s -\n" % (pid, sid))

    def drop_lock(self, repo=None):
        os.remove(os.path.join(self.repo if repo is None else repo, "agent_main.lock"))

    def line(self, ev, sid, now=100.0, repo=None, role="", tool="Read", pid=None, aid="", at=""):
        """pid None: an old hook's line, it has no "pid" key at all."""
        obj = {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": "p",
               "role": role, "desc": "", "sub": "", "q": "", "klen": "",
               "repo": self.repo if repo is None else repo, "ask": "", "wt": "", "file": "", "tp": ""}
        if pid is not None:
            obj["pid"] = str(pid)
        self.st.feed_line(obj, now)

    def act(self, sid, now=100.0, **kw):
        self.line("PostToolUse", sid, now, **kw)

    def holder(self, repo=None):
        reducer = self.st.reducers.get(self.repo if repo is None else repo)
        return None if reducer is None else reducer.gov_sid

    def snapshot(self):
        client = self.st.add_client()
        try:
            data = client.queue.get_nowait().decode("utf-8")
        finally:
            self.st.remove_client(client)
        return json.loads(data.split("data:", 1)[1])

    def agents(self):
        return {a["id"]: a for a in self.snapshot()["agents"]}

    def govs(self):
        return [(g["terr"], g["state"]) for g in self.snapshot()["govs"]]

    def terr(self, repo=None):
        return ac.territory_id(self.repo if repo is None else repo)

    def roster_text(self):
        with open(self.roster, encoding="utf-8") as fh:
            return fh.read()

    def listen(self):
        self.client = self.st.add_client()
        self.client.queue.get_nowait()  # the snapshot

    def heard(self):
        out = []
        while True:
            try:
                raw = self.client.queue.get_nowait()
            except queue.Empty:
                return out
            if not isinstance(raw, bytes):
                continue
            text = raw.decode("utf-8")
            if "data:" in text:
                out.append(json.loads(text.split("data:", 1)[1]))

    def a_governor(self, sid="sid-gov", repo=None, with_pid=True):
        """A live main manager: holds the lock by sid, has acted, is idle now."""
        proc = self.live()
        self.write_lock(proc.pid, sid, repo=repo)
        self.act(sid, repo=repo, pid=proc.pid if with_pid else None)
        self.line("Stop", sid, repo=repo, pid=proc.pid if with_pid else None)
        self.assertEqual(self.holder(repo), sid)
        return proc

    def a_citizen(self, sid="sid-tm", role="task-manager", repo=None):
        """A live session that is not the main manager, idle now."""
        proc = self.live()
        self.act(sid, repo=repo, role=role, pid=proc.pid)
        self.line("Stop", sid, repo=repo, role=role, pid=proc.pid)
        self.assertIn("s:" + sid, self.agents())
        return proc


A_REPO, B_REPO = "/work/ta/app/.git", "/work/tb/shop/.git"


def gline(ev, sid="s1", aid="", at="", tool="", role="", repo="", kind="", proj="shop"):
    return json.dumps({"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "proj": proj,
                       "role": role, "desc": "", "sub": "", "q": "", "klen": "", "repo": repo,
                       "kind": kind}) + "\n"


TALK_TA, TALK_TB = ac.territory_id(A_REPO), ac.territory_id(B_REPO)


def world_git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    return subprocess.run(["git", "-C", cwd] + list(args), check=True, capture_output=True, text=True,
                          env=env, stdin=subprocess.DEVNULL).stdout.strip()


def world_make_repo(base, files):
    os.makedirs(base, exist_ok=True)
    world_git(base, "init", "-q", "-b", "main")
    for rel, content in files.items():
        path = os.path.join(base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(content if isinstance(content, bytes) else content.encode())
    world_git(base, "add", "-A")
    world_git(base, "commit", "-q", "-m", "init")
    return os.path.realpath(os.path.join(base, ".git"))


def title_line(value, sid):
    return json.dumps({"type": "custom-title", "customTitle": value, "sessionId": sid}) + "\n"


class TalkServerCase(unittest.TestCase):

    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_talk_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.root = os.path.join(self.base, "projects")
        os.makedirs(os.path.join(self.root, "-work-app"))
        self.mains = Mains()
        self.st = ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"),
                               world_path=os.path.join(self.base, "world.json"), main_fn=self.mains, titles=ac.TitleReader(root=self.root))
        self.client = self.st.add_client()
        self.client.queue.get_nowait()
        self.now = 1000.0

    def named(self, sid, name):
        """A transcript that names session SID."""
        path = os.path.join(self.root, "-work-app", sid + ".jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(title_line(name, sid))
        return path

    def line(self, ev, sid, repo=A_REPO, role="", aid="", at="", tool="", ask="", sub="", desc="", tp="", **more):
        self.now += 1.0
        obj = {"ev": ev, "sid": sid, "aid": aid, "at": at, "tool": tool, "nt": "", "role": role, "desc": desc,
               "sub": sub, "q": "", "klen": "", "repo": repo, "ask": ask, "wt": "", "file": "", "tp": tp,
               "proj": "shop" if repo == B_REPO else "app"}
        obj.update(more)
        self.st.feed_line(obj, self.now)

    def events(self):
        out = []
        while not self.client.queue.empty():
            raw = self.client.queue.get_nowait()
            if isinstance(raw, bytes) and b"data:" in raw:
                out.append(json.loads(raw.decode("utf-8").split("data:", 1)[1]))
        return out

    def spawn_of(self, cid):
        found = [e for e in self.events() if e.get("type") == "spawn" and e.get("id") == cid]
        self.assertEqual(len(found), 1, "one spawn event for " + cid)
        return found[0]

    def talks(self):
        return [e for e in self.events() if e.get("type") == "talk"]

    def governor(self, sid="g1", repo=A_REPO):
        self.mains.setdefault(repo, sid)
        self.line("UserPromptSubmit", sid, repo)

    def lead(self, sid="tm1", name="city-talk Task Manager", repo=A_REPO):
        self.line("PostToolUse", sid, repo, role="task-manager", tool="Bash", tp=self.named(sid, name))

    def helper(self, sid="h1", name="app Helper", repo=A_REPO):
        self.line("PostToolUse", sid, repo, tool="Bash", tp=self.named(sid, name))

    def sub(self, aid, sid, role="", kind="worker", repo=A_REPO):
        self.line("PreToolUse", sid, repo, role=role, tool="Agent", sub=kind, desc="slice")
        self.line("SubagentStart", sid, repo, role=role, aid=aid, at=kind)

    def send(self, sid, to, repo=A_REPO, role="", aid="", ask="", ev="PostToolUse", **more):
        self.line(ev, sid, repo, role=role, aid=aid, at="worker" if aid else "", tool="SendMessage", ask=ask, to=to,
                  **more)


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
