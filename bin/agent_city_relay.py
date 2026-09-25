#!/usr/bin/env python3
"""Local side of joining a team relay (requirements/city.md, "Joining").

Python standard library only, Python 3.8+. Pure module: never imports
agent_city.py. Used by bin/agent_city.py (serve) to send its lines to the
team relay and get the other members' lines back, and by bin/agent-city.sh
(join) through the small CLI at the bottom of this file.

See tests/test_agent_city_relay_client.py for the full contract.
"""

import getpass
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

OUTBOX_CAP = 500        # unsent lines kept per team, oldest dropped first
MAX_BATCH = 200         # lines per sync, the relay's own limit

GIT_TIMEOUT = 3.0       # short timeout for every git subprocess call

_JOIN_FOLDER = ".secrets"
_JOIN_NAME = "agent-city-relay"

_KEPT_LINE_FIELDS = ("ev", "sid", "aid", "at", "tool", "nt", "role", "desc",
                     "sub", "klen", "kind")
_CTX_FIELDS = ("rid", "br", "who", "dev")


# --------------------------------------------------------------- join file

def read_join(path):
    """Read the join file at path. Returns {"address", "key"} or None."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    values = {}
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    address = values.get("address")
    key = values.get("key")
    if not address or not key:
        return None
    return {"address": address, "key": key}


def write_join(path, address, key):
    """Write the join file at path, atomically, mode 0600."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp_path = path + ".tmp-%d" % os.getpid()
    content = "address=%s\nkey=%s\n" % (address, key)
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_path, path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    os.chmod(path, 0o600)


def check_address(address):
    """None when address is fine to use for a relay, else a short error."""
    if not address or any(ch.isspace() for ch in address):
        return "bad address"
    try:
        parsed = urlsplit(address)
    except ValueError:
        return "bad address"
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return "bad address"
    host = parsed.hostname
    if not host:
        return "bad address"
    if scheme == "http" and host.lower() not in ("127.0.0.1", "localhost"):
        return "http:// only for 127.0.0.1 and localhost"
    return None


# ------------------------------------------------------------------- wire

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")
_SCP_RE = re.compile(r"^[^/@\s]+@([^:/\s]+):(.+)$")


def origin_id(url):
    """"host/owner/repo", lower case, from any git remote form. None when
    the remote is not shared (local path, file://, missing)."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    host = None
    path = None
    if _SCHEME_RE.match(url):
        parsed = urlsplit(url)
        if parsed.scheme.lower() == "file":
            return None
        host = parsed.hostname
        path = parsed.path
    else:
        m = _SCP_RE.match(url)
        if not m:
            return None
        host, path = m.group(1), m.group(2)
    if not host or not path:
        return None
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not path:
        return None
    return (host + "/" + path).lower()


def _shorten_paths(text):
    words = text.split(" ")
    out = []
    for word in words:
        if word.startswith("/") or word.startswith("~/"):
            trimmed = word.rstrip("/")
            base = trimmed.rsplit("/", 1)[-1]
            out.append(base if base else word)
        else:
            out.append(word)
    return " ".join(out)


def _wire_str(value):
    if value is None:
        return ""
    return str(value)


def to_wire(line, ctx):
    """The line as sent to the relay: the kept fields of line, plus ctx's
    rid/br/who/dev. Every value a string of at most 200 characters."""
    out = {}
    for field in _KEPT_LINE_FIELDS:
        value = line.get(field) if isinstance(line, dict) else None
        value = _shorten_paths(_wire_str(value))
        out[field] = value[:200]
    for field in _CTX_FIELDS:
        value = _wire_str(ctx.get(field) if ctx else None)
        out[field] = value[:200]
    return out


# ----------------------------------------------------------------- outbox

class Outbox:
    """A per-team queue of not-yet-sent wire lines, oldest first."""

    def __init__(self, cap=OUTBOX_CAP):
        self.cap = cap
        self._items = []
        self.dropped = 0

    def add(self, item):
        self._items.append(item)
        self._trim()

    def putback(self, items):
        """Push items back to the front, in order (they were taken from
        the front, so they are older than what is already queued)."""
        self._items[0:0] = list(items)
        self._trim()

    def take(self, n):
        taken = self._items[:n]
        del self._items[:n]
        return taken

    def _trim(self):
        while len(self._items) > self.cap:
            del self._items[0]
            self.dropped += 1

    def __len__(self):
        return len(self._items)


# ------------------------------------------------------------------- sync

_USER_AGENT = "agent-city-relay/1"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: the key must never be re-sent to whatever
    host a 3xx Location points at."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def sync(address, key, dev, after, lines, timeout=10.0):
    """POST <address>/v1/sync. ("ok", {"seq", "lines"}) | ("refused", None)
    | ("down", None)."""
    url = address.rstrip("/") + "/v1/sync"
    payload = json.dumps({"dev": dev, "after": after, "lines": lines}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                "User-Agent": _USER_AGENT})
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return ("refused", None)
        return ("down", None)
    except Exception:
        return ("down", None)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return ("down", None)
    if isinstance(data, dict) and data.get("ok") is True:
        return ("ok", {"seq": data.get("seq"), "lines": data.get("lines") or []})
    return ("down", None)


# -------------------------------------------------------------------- ids

def _default_dev_id():
    host = platform.node() or "host"
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    digest = hashlib.sha256(("%s:%s" % (host, user)).encode("utf-8")).hexdigest()
    return digest[:16]


def _default_label():
    if os.environ.get("CLAUDE_CODE_REMOTE"):
        return "云端"
    host = platform.node() or "host"
    return host.split(".")[0] or "host"


def _git(args, cwd):
    try:
        proc = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True,
                              text=True, timeout=GIT_TIMEOUT)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


# --------------------------------------------------------------------- hub

class _Team:
    def __init__(self, address, key, cap):
        self.address = address
        self.key = key
        self.outbox = Outbox(cap=cap)
        self.rids = set()
        self.join_paths = set()
        self.after = 0
        self.last_sync = None
        self.state = "new"


class RelayHub:
    """One hub per city server: offers lines to the right team's outbox,
    and syncs every due team with the relay.

    Thread-safe: offer() is called from the file-tail thread, tick()/
    status()/joined() from the relay thread and HTTP handlers. All shared
    state (teams, outboxes, caches) is guarded by one lock. The lock is
    never held during a sync()'s network call: tick() takes the batch
    under the lock, releases it, syncs, then re-takes the lock to store
    the result or put the lines back."""

    def __init__(self, relay_sec=5.0, dev_id=None, label=None, cap=OUTBOX_CAP,
                 join_ttl=30.0, timeout=10.0):
        self.relay_sec = relay_sec
        self.dev_id = dev_id or _default_dev_id()
        self.label = label or _default_label()
        self.cap = cap
        self.join_ttl = join_ttl
        self.timeout = timeout
        self._teams = {}
        self._join_cache = {}
        self._ids_cache = {}
        self._branch_cache = {}
        self._lock = threading.RLock()

    def _cached(self, cache, key, compute):
        # Caller must hold self._lock.
        now = time.monotonic()
        if self.join_ttl > 0:
            hit = cache.get(key)
            if hit is not None and (now - hit[0]) < self.join_ttl:
                return hit[1]
        value = compute()
        cache[key] = (now, value)
        return value

    def _read_join(self, join_path):
        return self._cached(self._join_cache, join_path, lambda: read_join(join_path))

    def _repo_ids(self, root):
        def compute():
            origin = _git(["config", "--get", "remote.origin.url"], root)
            who = _git(["config", "user.name"], root) or ""
            return {"origin": origin, "who": who}
        return self._cached(self._ids_cache, root, compute)

    def _branch(self, proj):
        def compute():
            return _git(["rev-parse", "--abbrev-ref", "HEAD"], proj) or ""
        return self._cached(self._branch_cache, proj, compute)

    def offer(self, line):
        if not isinstance(line, dict):
            return False
        repo = line.get("repo")
        if not repo:
            return False
        root = os.path.dirname(repo)
        join_path = os.path.join(root, _JOIN_FOLDER, _JOIN_NAME)
        with self._lock:
            joined = self._read_join(join_path)
            if not joined:
                return False
            ids = self._repo_ids(root)
            rid = origin_id(ids.get("origin"))
            if not rid:
                return False
            proj = line.get("proj") or root
            branch = self._branch(proj)
            ctx = {"rid": rid, "br": branch, "who": ids.get("who") or "", "dev": self.label}
            wire = to_wire(line, ctx)
            key = (joined["address"], joined["key"])
            team = self._teams.get(key)
            if team is None:
                team = _Team(joined["address"], joined["key"], self.cap)
                self._teams[key] = team
            team.outbox.add(wire)
            team.rids.add(rid)
            team.join_paths.add(join_path)
            return True

    def tick(self):
        results = []
        now = time.monotonic()
        with self._lock:
            keys = list(self._teams.keys())
        for key in keys:
            with self._lock:
                team = self._teams.get(key)
                if team is None:
                    continue
                if not self._team_still_joined(team):
                    del self._teams[key]
                    continue
                due = self.relay_sec <= 0 or team.last_sync is None or \
                    (now - team.last_sync) >= self.relay_sec
                if not due:
                    continue
                batch = team.outbox.take(MAX_BATCH)
                address, api_key, after = team.address, team.key, team.after
                dev_id, timeout = self.dev_id, self.timeout

            # The network call happens with the lock released, so a slow
            # or stuck relay never stalls offer() / other teams' ticks.
            state, data = sync(address, api_key, dev_id, after, batch, timeout=timeout)
            finished_at = time.monotonic()

            with self._lock:
                team = self._teams.get(key)
                if team is None:
                    # Left (or re-keyed) while this sync was in flight: the
                    # team and its join file are gone, nothing to store.
                    continue
                team.last_sync = finished_at
                if state == "ok":
                    team.state = "ok"
                    team.after = data["seq"]
                    for item in data.get("lines") or []:
                        results.append({"dev": item.get("dev"), "line": item.get("line")})
                else:
                    team.state = "off" if state == "down" else state
                    team.outbox.putback(batch)
        return results

    def _team_still_joined(self, team):
        # Caller must hold self._lock.
        for join_path in list(team.join_paths):
            parsed = self._read_join(join_path)
            if parsed and parsed["address"] == team.address and parsed["key"] == team.key:
                return True
        return False

    def status(self):
        with self._lock:
            teams = []
            for team in self._teams.values():
                host = urlsplit(team.address).netloc
                teams.append({"host": host, "rids": sorted(team.rids), "state": team.state,
                              "queued": len(team.outbox), "dropped": team.outbox.dropped})
            teams.sort(key=lambda t: t["host"])
            return {"joined": bool(self._teams), "teams": teams}

    def joined(self):
        with self._lock:
            return bool(self._teams)


# --------------------------------------------------------------------- CLI

def _cli(argv):
    import argparse

    parser = argparse.ArgumentParser(prog="agent_city_relay.py", add_help=True)
    sub = parser.add_subparsers(dest="cmd")

    p_check = sub.add_parser("check")
    p_check.add_argument("--address", required=True)

    p_join = sub.add_parser("join")
    p_join.add_argument("--address", required=True)
    p_join.add_argument("--file", required=True)

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if args.cmd not in ("check", "join"):
        parser.print_usage(sys.stderr)
        return 2

    err = check_address(args.address)
    if err:
        print("RELAY: %s" % err)
        return 2

    key = sys.stdin.readline().strip()
    if not key:
        print("RELAY: no key on stdin")
        return 2

    dev_id = _default_dev_id()
    state, _data = sync(args.address, key, dev_id, 0, [])
    host = urlsplit(args.address).netloc

    if state == "refused":
        print("RELAY: the relay refused the key")
        return 3
    if state != "ok":
        print("RELAY: cannot reach %s" % host)
        return 4

    if args.cmd == "join":
        write_join(args.file, args.address, key)

    print("RELAY: ok %s" % host)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
