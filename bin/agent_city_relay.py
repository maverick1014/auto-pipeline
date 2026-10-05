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
import ipaddress
import json
import os
import platform
import re
import signal
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

TAIL_INTERVAL = 0.25    # cloud sender: how often it polls events.jsonl
RELAY_POLL_SEC = 0.1    # cloud sender: how often it calls hub.tick()

TALK_SOON_SEC = 1.0     # cloud-city-2: a team with talk to hand up syncs again this soon
SLOW_SEC = 15.0         # cloud-city-3: a team with nobody to show, waiting only for a start order, syncs this often

_JOIN_FOLDER = ".secrets"
_JOIN_NAME = "agent-city-relay"

_KEPT_LINE_FIELDS = ("ev", "sid", "aid", "at", "tool", "nt", "role", "desc",
                     "sub", "klen", "ask")
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


def effective_join(root, device):
    """The join that counts for the repo whose folder is ROOT, on a computer
    whose device join file is DEVICE (a path, or None). {"address", "key",
    "path"} (path = the file it came from) or None.
    ROOT's own <root>/.secrets/agent-city-relay wins when read_join takes it
    and the device gives no join or names another relay host; on the device's
    relay host the device key counts. Else the device file, when read_join
    takes it. Else None. Relay host = urlsplit(address).netloc."""
    own_path = os.path.join(root, _JOIN_FOLDER, _JOIN_NAME)
    own = read_join(own_path)
    dev = read_join(device) if device else None
    if own is not None and (dev is None or _relay_host(own["address"]) != _relay_host(dev["address"])):
        return {"address": own["address"], "key": own["key"], "path": own_path}
    if dev is not None:
        return {"address": dev["address"], "key": dev["key"], "path": device}
    return None


def _relay_host(address):
    try:
        return urlsplit(address).netloc
    except ValueError:
        return address


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


def _write_lines_atomic(path, lines):
    """Write lines (one per line, "\\n" appended) atomically: a temp file
    in the same folder, then os.replace. Same pattern as write_join()."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp_path = path + ".tmp-%d" % os.getpid()
    content = "".join(line + "\n" for line in lines)
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_path, path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def read_joined_list(path):
    """User-level list of joined repos: one absolute repo path per line,
    "#" comments, paths only (never keys). Absolute paths in file order;
    blank, "#" comment and relative lines skipped; a later line whose
    os.path.realpath equals an earlier one is dropped. Missing file -> []."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return []
    seen = set()
    out = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not os.path.isabs(line):
            continue
        real = os.path.realpath(line)
        if real in seen:
            continue
        seen.add(real)
        out.append(line)
    return out


def add_joined(path, repo):
    """Add os.path.realpath(repo) to the joined list at path, unless a
    line with the same realpath is already there. Makes the folder, keeps
    every other line and comment as is, written atomically."""
    real = os.path.realpath(repo)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        lines = []
    for raw_line in lines:
        line = raw_line.strip()
        if line and not line.startswith("#") and os.path.isabs(line) \
                and os.path.realpath(line) == real:
            return
    lines.append(real)
    _write_lines_atomic(path, lines)


def remove_joined(path, repo):
    """Drop the lines of the joined list at path whose realpath equals
    repo's (works for a folder that no longer exists); keeps the rest and
    the comments. Missing file -> no error, create nothing."""
    real = os.path.realpath(repo)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return
    kept = []
    for raw_line in lines:
        line = raw_line.strip()
        if line and not line.startswith("#") and os.path.isabs(line) \
                and os.path.realpath(line) == real:
            continue
        kept.append(raw_line)
    _write_lines_atomic(path, kept)


_LAN_NETS = tuple(ipaddress.ip_network(n) for n in
                  ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def _is_lan_ipv4(host):
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in net for net in _LAN_NETS)


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
    if scheme == "http" and host.lower() not in ("127.0.0.1", "localhost") \
            and not _is_lan_ipv4(host):
        return "http:// only for 127.0.0.1, localhost, or a LAN address"
    return None


def parse_env(value):
    """Parse AGENT_CITY_RELAY="<address> <key>" (one space between, a cloud
    session's only source of its team relay). {"address", "key"} on exactly
    two whitespace-separated parts whose address passes check_address() and
    whose key is not empty, else None."""
    if not value:
        return None
    parts = value.split()
    if len(parts) != 2:
        return None
    address, key = parts
    if check_address(address):
        return None
    if not key:
        return None
    return {"address": address, "key": key}


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
    """The line as sent to the relay: _KEPT_LINE_FIELDS of line (ev sid aid
    at tool nt role desc sub klen ask -- no "kind", nobody reads it; idea-
    city C4), plus ctx's rid/br/who/dev. Every value a string of at most
    200 characters."""
    out = {}
    for field in _KEPT_LINE_FIELDS:
        value = line.get(field) if isinstance(line, dict) else None
        value = _shorten_paths(_wire_str(value))
        out[field] = value[:200]
    for field in _CTX_FIELDS:
        value = _wire_str(ctx.get(field) if ctx else None)
        out[field] = value[:200]
    if not out["who"].strip():
        out["who"] = out["dev"]
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


def sync(address, key, dev, after, lines, timeout=10.0, view=None, talk=None, talk_key=None):
    """POST <address>/v1/sync. ("ok", {"seq", "lines", "city", "gen", "talk"}) |
    ("refused", None) | ("down", None).

    cloud-city-1: view (a dict) rides in the body as "view", only when given.
    The ok data's "city" is True only when the reply says "city": true (an
    old relay says nothing: False); "gen" is the reply's gen, else 0.

    cloud-city-2: talk_key given -> the header X-City-Talk and the body key
    "talk" (talk, or {} when talk is None); without a talk_key the request is
    the one of before. The ok data's "talk" is the reply's talk when it is a
    dict, else None. The talk key is never in the body and never printed."""
    url = address.rstrip("/") + "/v1/sync"
    body = {"dev": dev, "after": after, "lines": lines}
    if view is not None:
        body["view"] = view
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json",
               "User-Agent": _USER_AGENT}
    if talk_key:
        body["talk"] = talk if talk is not None else {}
        headers["X-City-Talk"] = talk_key
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
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
        gen = data.get("gen")
        if isinstance(gen, bool) or not isinstance(gen, int):
            gen = 0
        reply_talk = data.get("talk")
        return ("ok", {"seq": data.get("seq"), "lines": data.get("lines") or [],
                       "city": data.get("city") is True, "gen": gen,
                       "talk": reply_talk if isinstance(reply_talk, dict) else None})
    return ("down", None)


# ------------------------------------------------------ cloud marker (cloud-city)

def read_cloud(path):
    """cloud-city-1: the sorted relay hosts in the marker file at path (one
    host per line, hosts only, never a key). Missing or broken file -> []."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, ValueError):
        return []
    hosts = set()
    for raw_line in text.splitlines():
        host = raw_line.strip()
        if host and not host.startswith("#") and not any(ch.isspace() for ch in host):
            hosts.add(host)
    return sorted(hosts)


_CLOUD_LOCK = threading.Lock()


def set_cloud(path, host, on):
    """cloud-city-1: add (on) or remove HOST in the marker file at path,
    written whole (a temp file, then os.replace); the file is removed when
    the last host goes. Hosts only. Never raises."""
    try:
        with _CLOUD_LOCK:
            _set_cloud(path, host, on)
    except OSError:
        pass


def _set_cloud(path, host, on):
    hosts = set(read_cloud(path))
    if (host in hosts) == bool(on) and (hosts or not os.path.exists(path)):
        return      # already as asked
    if on:
        hosts.add(host)
    else:
        hosts.discard(host)
    if not hosts:
        try:
            os.remove(path)
        except OSError:
            pass
        return
    _write_lines_atomic(path, sorted(hosts))


# ------------------------------------------------------ talk file (cloud-city-2)

def read_talk(path):
    """cloud-city-2: {relay host: talk key} from the talk file at path (one
    line "<host> <key>" each; blank, "#" and broken lines skipped). A secret:
    never print or log the values. Missing or broken file -> {}."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, ValueError):
        return {}
    held = {}
    for raw_line in text.splitlines():
        parts = raw_line.split()
        if len(parts) == 2 and not parts[0].startswith("#"):
            held[parts[0]] = parts[1]
    return held


_TALK_LOCK = threading.Lock()


def set_talk(path, host, key):
    """cloud-city-2: keep KEY for HOST in the talk file at path (key None =
    forget HOST), written whole (a temp file, then os.replace), mode 0600; the
    file is removed when the last host goes. Never raises."""
    try:
        with _TALK_LOCK:
            _set_talk(path, host, key)
    except OSError:
        pass


def _set_talk(path, host, key):
    held = read_talk(path)
    if key is None:
        if host not in held and (held or not os.path.exists(path)):
            return      # already as asked
        held.pop(host, None)
    else:
        if not host or not key or len(host.split()) != 1 or len(key.split()) != 1:
            return      # a line could not hold it
        held[host] = key
    if not held:
        try:
            os.remove(path)
        except OSError:
            pass
        return
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp_path = path + ".tmp-%d" % os.getpid()
    content = "".join("%s %s\n" % (h, held[h]) for h in sorted(held))
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


# ------------------------------------------------------ start file (cloud-city-3)

def read_start(path):
    """cloud-city-3: the set of relay hosts in the start file at path (one
    host per line, hosts only, never a key: the key is the talk key). The
    machine takes start orders from these relays. Blank, "#" and broken
    lines are skipped, and so is a line with more than one word (never read
    as on). Missing or broken file -> set()."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, ValueError):
        return set()
    hosts = set()
    for raw_line in text.splitlines():
        parts = raw_line.split()
        if len(parts) == 1 and not parts[0].startswith("#"):
            hosts.add(parts[0])
    return hosts


_START_LOCK = threading.Lock()


def set_start(path, host, on):
    """cloud-city-3: put HOST in the start file at path (on true) or take it
    out, written whole (a temp file, then os.replace), mode 0600; the file is
    removed when the last host goes. Hosts only. Never raises."""
    try:
        with _START_LOCK:
            _set_start(path, host, on)
    except OSError:
        pass


def _set_start(path, host, on):
    hosts = read_start(path)
    if on:
        if not host or len(host.split()) != 1 or host.startswith("#"):
            return      # a line could not hold it
        hosts.add(host)
    elif host not in hosts and (hosts or not os.path.exists(path)):
        return          # already as asked
    else:
        hosts.discard(host)
    if not hosts:
        try:
            os.remove(path)
        except OSError:
            pass
        return
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp_path = path + ".tmp-%d" % os.getpid()
    content = "".join(h + "\n" for h in sorted(hosts))
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


# -------------------------------------------------------------------- ids

def _default_dev_id():
    host = platform.node() or "host"
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    digest = hashlib.sha256(("%s:%s" % (host, user)).encode("utf-8")).hexdigest()
    return digest[:16]


def _default_label(lang="zh"):
    """idea-city C1: a cloud session's tag follows LANG -- "cloud" for
    "en", "云端" for anything else (the default, "zh")."""
    if os.environ.get("CLAUDE_CODE_REMOTE"):
        return "cloud" if lang == "en" else "云端"
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


def _parse_worktrees(text):
    """Parse `git worktree list --porcelain` into
    [{"path": str, "branch": str}, ...]. branch is "" for a detached HEAD."""
    entries = []
    cur = None
    for raw_line in (text or "").splitlines():
        if raw_line.startswith("worktree "):
            cur = {"path": raw_line[len("worktree "):], "branch": ""}
            entries.append(cur)
        elif cur is None:
            continue
        elif raw_line.startswith("branch "):
            ref = raw_line[len("branch "):]
            cur["branch"] = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        elif raw_line == "":
            cur = None
    return entries


# --------------------------------------------------------------------- hub

class _Team:
    def __init__(self, address, key, cap):
        self.address = address
        self.key = key
        self.outbox = Outbox(cap=cap)
        self.rids = set()
        self.repos = set()      # cloud-city: real paths of the joined repos seen (offer / joined list)
        self.join_paths = set()
        self.listed = set()     # device-join: real paths of the repos already put in the joined list for this team
        self.after = 0
        self.last_sync = None
        self.soon = False       # cloud-city-2: the source has talk to hand up: sync again in TALK_SOON_SEC
        self.state = "new"
        self.env = False    # True for a RelayHub(env_join=...) team: no join
                            # file, lives as long as the process does.


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
                 join_ttl=30.0, timeout=10.0, env_join=None, send_only=False,
                 joined_list=None, cloud_file=None, view_source=None, talk_file=None,
                 start_file=None, slow_fn=None, slow_sec=SLOW_SEC, join_dir=None,
                 device_join=None):
        self.relay_sec = relay_sec
        self.dev_id = dev_id or _default_dev_id()
        self.label = label or _default_label()
        self.cap = cap
        self.join_ttl = join_ttl
        self.timeout = timeout
        # env_join {"address", "key"}: a cloud session's fixed team, read
        # from AGENT_CITY_RELAY, never from a join file (see parse_env()).
        self.env_join = env_join
        # send_only: tick() still syncs and still moves "after", but always
        # returns [] -- a cloud session shows no one.
        self.send_only = send_only
        # joined_list: path to a user-level list of repos (read_joined_list)
        # this machine has joined; tick() seeds a team per listed repo, no
        # offer() (no local line) needed. None -> today's behaviour.
        self.joined_list = joined_list
        # cloud-city-1: cloud_file = the marker (read_cloud / set_cloud) this
        # hub keeps after every ANSWERED sync of a team. view_source = an
        # object with take(host, rids, now) -> a view dict or None, and
        # sent(host, data, now) (data = the ok data, or None when the relay
        # was down or refused); both are called with the hub's lock released.
        self.cloud_file = cloud_file
        self.view_source = view_source
        # cloud-city-2: talk_file = the talk file (read_talk): re-read before
        # every sync of a team, so `cloud-talk on / off` works with the next
        # sync. When the team's host has a key there and view_source has
        # talk_take(host, rids, now) -> a dict or None, talk_sent(host, talk,
        # now) (talk = the reply's talk dict, or None when the relay was down
        # or refused the team key) and talk_soon(host) -> bool, the sync
        # carries the key and what talk_take gave; talk_soon true makes the
        # team's next sync due in TALK_SOON_SEC. All called with the lock
        # released; an error in any of them never stops the lines.
        self.talk_file = talk_file
        # cloud-city-3: start_file = the start file (read_start): the hosts
        # this machine takes start orders from. The hub only keeps the path;
        # the view source reads it before every sync, so on / off works with
        # the next sync. slow_fn() true -> a team's next sync is due slow_sec
        # after the last one instead of relay_sec (talk_soon still wins); no
        # slow_fn, a false answer or an error: relay_sec as before.
        self.start_file = start_file
        self.slow_fn = slow_fn
        self.slow_sec = slow_sec
        # join_dir (TEST ONLY, never set by agent-city.sh): the join file of a
        # repo is join_dir/<its folder's name>, and the repo's own
        # .secrets/agent-city-relay is not read at all.
        self.join_dir = join_dir
        # device_join (city-device-join): path to this computer's join file
        # (<home>/team-relay). A repo with no join file of its own, or one on
        # the device's relay host, joins through it. None -> today's
        # behaviour: the file is never read. Never used with env_join.
        self.device_join = device_join
        self._teams = {}
        self._join_cache = {}
        self._ids_cache = {}
        self._worktree_cache = {}
        self._list_cache = {}
        self._common_cache = {}
        self._repo_by_rid = {}
        self._who = ""
        self._who_set = False
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

    def _join_path(self, root):
        # The join file of the repo whose folder is ROOT.
        if self.join_dir:
            return os.path.join(self.join_dir, os.path.basename(root.rstrip("/")))
        return os.path.join(root, _JOIN_FOLDER, _JOIN_NAME)

    def _pick_join(self, root):
        # Caller must hold self._lock. The same choice effective_join() makes,
        # read through the join_ttl cache: (joined, path) for the repo whose
        # folder is ROOT, or (None, None). With no device_join this is the
        # repo's own file, as before.
        own_path = self._join_path(root)
        own = self._read_join(own_path)
        dev_path = self.device_join
        dev = self._read_join(dev_path) if dev_path else None
        if own and (not dev or _relay_host(own["address"]) != _relay_host(dev["address"])):
            return own, own_path
        if dev:
            return dev, dev_path
        return None, None

    def _list_device_repo(self, team, root):
        # Caller must hold self._lock. A line of ROOT went to the team through
        # the device file: ROOT joins the joined list (realpath, once, never a
        # key). The team remembers the repos it handled, so a busy session
        # does not touch the list per line.
        if self.joined_list is None:
            return
        real = os.path.realpath(root)
        if real in team.listed:
            return
        try:
            listed = self._cached(self._list_cache, self.joined_list,
                                  lambda: read_joined_list(self.joined_list))
            if not any(os.path.realpath(p) == real for p in listed):
                add_joined(self.joined_list, real)
        except OSError:
            return
        team.listed.add(real)

    def _repo_ids(self, root):
        def compute():
            origin = _git(["config", "--get", "remote.origin.url"], root)
            who = _git(["config", "user.name"], root) or ""
            return {"origin": origin, "who": who}
        return self._cached(self._ids_cache, root, compute)

    def _git_common_dir(self, root):
        # Cached like _repo_ids(): a listed repo must cost at most one
        # "git rev-parse --git-common-dir" per join_ttl, not one per tick
        # (tick() calls this under self._lock, and RELAY_POLL_SEC is 0.1s).
        return self._cached(self._common_cache, root,
                            lambda: _git(["rev-parse", "--git-common-dir"], root))

    def _repo_worktrees(self, root):
        def compute():
            text = _git(["worktree", "list", "--porcelain"], root) or ""
            return _parse_worktrees(text)
        return self._cached(self._worktree_cache, root, compute)

    def _branch(self, root, proj, wt=None):
        # With "wt" (the hook's own linked-worktree path, its 16th key):
        # the branch is that worktree's branch, matched by real path, even
        # when the session's cwd was a subfolder of it (proj is then only
        # the subfolder's name and is not used).
        if wt:
            wt_real = os.path.realpath(wt)
            for entry in self._repo_worktrees(root):
                if os.path.realpath(entry["path"].rstrip("/")) == wt_real:
                    return entry["branch"]
            return ""
        # Without "wt": the hook keeps only the folder name of the
        # session's cwd in "proj" (bin/agent-city-hook.sh: proj=${cwd##*/}),
        # never a path, so the branch is found by listing the repo's
        # worktrees and matching that folder name. No match (e.g. the cwd
        # was a subfolder) or a detached HEAD -> "".
        for entry in self._repo_worktrees(root):
            if os.path.basename(entry["path"].rstrip("/")) == proj:
                return entry["branch"]
        return ""

    def _seed_from_list(self):
        # Caller must hold self._lock. The list itself, re-read at most
        # every join_ttl seconds (join_ttl=0: every tick), same _cached()
        # as _read_join()/_repo_ids() below.
        if self.joined_list is None:
            return
        repos = self._cached(self._list_cache, self.joined_list,
                             lambda: read_joined_list(self.joined_list))
        for repo in repos:
            self._seed_team(repo)

    def _seed_team(self, repo):
        # Caller must hold self._lock. Local-only work (join file, a couple
        # of short git calls) -- same "under the lock" pattern offer() uses;
        # only the relay sync itself in tick() ever runs unlocked. A gone
        # folder, a gone join file or a local-only origin: skip quietly,
        # same as offer() returning False.
        joined, join_path = self._pick_join(repo)
        if not joined:
            return
        ids = self._repo_ids(repo)
        rid = origin_id(ids.get("origin"))
        if not rid:
            return
        common = self._git_common_dir(repo)
        if not common:
            return
        if not os.path.isabs(common):
            common = os.path.join(repo, common)
        key = (joined["address"], joined["key"])
        team = self._teams.get(key)
        if team is None:
            team = _Team(joined["address"], joined["key"], self.cap)
            self._teams[key] = team
        team.rids.add(rid)
        team.join_paths.add(join_path)
        team.repos.add(os.path.realpath(common))
        self._repo_by_rid[rid] = os.path.realpath(common)
        if not self._who_set:
            self._who = ids.get("who") or ""
            self._who_set = True

    def seed(self, repo):
        # cloud-city-2: the hub knows REPO (the repo's own folder, not its
        # .git) as a joined repo with no line sent: what a first hook line of
        # that repo does (offer()), minus the line. Used at start for the
        # repos of the sessions the roster brought back, so the first syncs
        # carry the picture and talk. A repo that is not joined: nothing.
        with self._lock:
            self._seed_team(repo)

    def offer(self, line):
        if not isinstance(line, dict):
            return False
        repo = line.get("repo")
        if not repo:
            return False
        root = os.path.dirname(repo)
        join_path = None
        with self._lock:
            if self.env_join is not None:
                joined = self.env_join
            else:
                joined, join_path = self._pick_join(root)
                if not joined:
                    return False
            ids = self._repo_ids(root)
            rid = origin_id(ids.get("origin"))
            if not rid:
                return False
            proj = line.get("proj") or os.path.basename(root)
            wt = line.get("wt") or None
            branch = self._branch(root, proj, wt)
            ctx = {"rid": rid, "br": branch, "who": ids.get("who") or "", "dev": self.label}
            wire = to_wire(line, ctx)
            key = (joined["address"], joined["key"])
            team = self._teams.get(key)
            if team is None:
                team = _Team(joined["address"], joined["key"], self.cap)
                team.env = self.env_join is not None
                self._teams[key] = team
            team.outbox.add(wire)
            team.rids.add(rid)
            team.repos.add(os.path.realpath(repo))
            if join_path is not None:
                team.join_paths.add(join_path)
                if self.device_join and join_path == self.device_join:
                    self._list_device_repo(team, root)
            self._repo_by_rid[rid] = os.path.realpath(repo)
            if not self._who_set:
                self._who = ids.get("who") or ""
                self._who_set = True
            return True

    def tick(self):
        results = []
        now = time.monotonic()
        # cloud-city-3: slow_fn is asked with the lock released (it takes the
        # city's and the source's locks), once per tick.
        slow = self._slow()
        with self._lock:
            self._seed_from_list()
            keys = list(self._teams.keys())
        for key in keys:
            with self._lock:
                team = self._teams.get(key)
                if team is None:
                    continue
                if not self._team_still_joined(team):
                    del self._teams[key]
                    continue
                wait = self.slow_sec if slow else self.relay_sec
                if team.soon:
                    wait = min(wait, TALK_SOON_SEC)
                due = self.relay_sec <= 0 or team.last_sync is None or \
                    (now - team.last_sync) >= wait
                if not due:
                    continue
                batch = team.outbox.take(MAX_BATCH)
                address, api_key, after = team.address, team.key, team.after
                dev_id, timeout = self.dev_id, self.timeout
                rids = sorted(team.rids)

            # cloud-city-1: the view source is asked with the lock released
            # (it takes its own lock), once per sync, before the network call.
            host = urlsplit(address).netloc
            view = None
            if self.view_source is not None:
                try:
                    view = self.view_source.take(host, rids, now)
                except Exception:
                    view = None

            # cloud-city-2: talk. Only when this host has a key in the talk
            # file (read now, so on / off works with this very sync) and the
            # source can take talk; a source error never stops the lines.
            talk_key, talk = self._talk_before_sync(host, rids, now)

            # The network call happens with the lock released, so a slow
            # or stuck relay never stalls offer() / other teams' ticks.
            state, data = sync(address, api_key, dev_id, after, batch, timeout=timeout,
                               view=view, talk=talk, talk_key=talk_key)
            extra_state, extra_data = None, None
            if state == "ok" and after > 0 and data.get("seq") is not None \
                    and data["seq"] < after:
                # The relay was made again (new database, or a dev relay
                # restarted): its seq went backwards. Resync from scratch
                # right away, so a line sent just after the reset is not
                # missed.
                extra_state, extra_data = sync(address, api_key, dev_id, 0, [],
                                               timeout=timeout)
            finished_at = time.monotonic()
            # cloud-city-1: tell the source what came back (lock released).
            self._cloud_after_sync(host, state, data, finished_at)
            soon = self._talk_after_sync(host, talk_key, state, data, finished_at)

            with self._lock:
                team = self._teams.get(key)
                if team is None:
                    # Left (or re-keyed) while this sync was in flight: the
                    # team and its join file are gone, nothing to store.
                    continue
                team.last_sync = finished_at
                team.soon = soon
                if state == "ok":
                    team.state = "ok"
                    new_after, lines = data["seq"], data.get("lines") or []
                    if extra_state is not None:
                        if extra_state == "ok":
                            new_after = extra_data["seq"]
                            lines = extra_data.get("lines") or []
                        else:
                            new_after = 0
                    team.after = new_after
                    for item in lines:
                        results.append({"dev": item.get("dev"), "line": item.get("line")})
                else:
                    team.state = "off" if state == "down" else state
                    team.outbox.putback(batch)
        # send_only (a cloud session): still synced above, "after" still
        # moved, but a cloud session shows no one.
        return [] if self.send_only else results

    def _slow(self):
        # cloud-city-3: True while slow_fn says the syncs may be slow. No
        # slow_fn, or one that raises: not slow.
        if self.slow_fn is None:
            return False
        try:
            return bool(self.slow_fn())
        except Exception:
            return False

    def _cloud_after_sync(self, host, state, data, now):
        # cloud-city-1: an ANSWERED sync sets the marker (the reply said
        # city, or not); a relay that is down or refuses leaves it as it is.
        # The view source hears of every sync: the ok data, or None.
        if state == "ok" and self.cloud_file:
            set_cloud(self.cloud_file, host, bool(data.get("city")))
        if self.view_source is not None:
            try:
                self.view_source.sent(host, data if state == "ok" else None, now)
            except Exception:
                pass

    def _talk_before_sync(self, host, rids, now):
        # cloud-city-2: (talk key, talk) for this team's next sync, or
        # (None, None) -- the sync of before. Lock released. The key stays
        # in memory for the one request: never printed, never logged.
        source = self.view_source
        if not self.talk_file or source is None or not callable(getattr(source, "talk_take", None)):
            return None, None
        talk_key = read_talk(self.talk_file).get(host)
        if not talk_key:
            return None, None
        try:
            talk = source.talk_take(host, rids, now)
        except Exception:
            talk = None
        return talk_key, talk if isinstance(talk, dict) else None

    def _talk_after_sync(self, host, talk_key, state, data, now):
        # cloud-city-2: tell the source what talk came back (the reply's talk
        # dict, or None when the relay was down or refused the team key) and
        # ask whether the next sync should come soon (only after a sync the
        # relay answered). Lock released.
        if not talk_key:
            return False
        try:
            self.view_source.talk_sent(host, data.get("talk") if state == "ok" else None, now)
        except Exception:
            pass
        if state != "ok":
            return False    # a relay that is down or refuses is asked again after relay_sec
        try:
            return bool(self.view_source.talk_soon(host))
        except Exception:
            return False

    def _team_still_joined(self, team):
        # Caller must hold self._lock.
        if team.env:
            return True
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

    def repo_for(self, rid):
        """The real path of the git common dir of a joined local repo whose
        origin gives rid (any repo offer() has queued a line for), or None."""
        with self._lock:
            return self._repo_by_rid.get(rid)

    def repos_for(self, host):
        """cloud-city: the real paths (git common dir) of every repo joined
        to the team at HOST (netloc) that offer() or the joined list has
        seen, sorted. [] for an unknown host."""
        with self._lock:
            out = set()
            for team in self._teams.values():
                if urlsplit(team.address).netloc == host:
                    out |= team.repos
            return sorted(out)

    def identity(self):
        """{"who": git user.name of the first joined repo seen, else the
        label (never blank), "device": label}."""
        with self._lock:
            return {"who": self._who or self.label, "device": self.label}


# --------------------------------------------------------------- cloud send

def _read_switch(path):
    """(pid, port) from DIR/on, or None. Same file bin/agent_city.py serve
    writes; the cloud sender writes port 0 (no page)."""
    try:
        with open(path) as fh:
            parts = fh.read().split()
        if len(parts) != 2:
            return None
        return int(parts[0]), int(parts[1])
    except (OSError, ValueError):
        return None


def _write_switch(path, pid, port):
    with open(path, "w") as fh:
        fh.write("%d %d\n" % (pid, port))


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _split_bytes(data):
    parts = data.split(b"\n")
    return parts[:-1], parts[-1]


def cmd_send(args):
    """The cloud sender: reads AGENT_CITY_RELAY, writes DIR/on, tails
    DIR/events.jsonl from its end and syncs offered lines on its own
    thread, until idle-sec with no new line or SIGTERM. --lang (default
    "zh") only picks this device's own label, _default_label(lang) --
    idea-city C1. See tests/test_agent_city_relay_send.py for the full
    contract."""
    value = os.environ.get("AGENT_CITY_RELAY")
    if not value:
        print("SEND: AGENT_CITY_RELAY is not set")
        return 1
    joined = parse_env(value)
    if joined is None:
        print("SEND: AGENT_CITY_RELAY must be '<address> <key>'")
        return 2

    directory = os.path.abspath(args.dir)
    os.makedirs(directory, exist_ok=True)
    on_path = os.path.join(directory, "on")

    existing = _read_switch(on_path)
    if existing is not None and _pid_alive(existing[0]):
        print("SEND: already running")
        return 0

    my_pid = os.getpid()
    log_path = os.path.join(directory, "events.jsonl")
    try:
        initial_skip = os.path.getsize(log_path)
    except OSError:
        initial_skip = 0

    hub = RelayHub(relay_sec=args.relay_sec, env_join=joined, send_only=True,
                   label=_default_label(getattr(args, "lang", "zh")))

    stop_event = threading.Event()
    last_activity = [time.monotonic()]

    def on_term(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGTERM, on_term)

    def tail_loop():
        fh = None
        offset = 0
        buf = b""
        skip = initial_skip
        while not stop_event.is_set():
            if fh is None:
                try:
                    fh = open(log_path, "rb")
                except OSError:
                    stop_event.wait(TAIL_INTERVAL)
                    continue
                size_now = os.fstat(fh.fileno()).st_size
                offset = min(skip, size_now)
                skip = 0
                buf = b""
            fh.seek(0, os.SEEK_END)
            end = fh.tell()
            if end > offset:
                fh.seek(offset)
                chunk = fh.read(end - offset)
                lines, buf = _split_bytes(buf + chunk)
                for raw_line in lines:
                    last_activity[0] = time.monotonic()
                    try:
                        obj = json.loads(raw_line.decode("utf-8", errors="replace"))
                    except ValueError:
                        continue
                    hub.offer(obj)
                offset = fh.tell()
            stop_event.wait(TAIL_INTERVAL)
        if fh is not None:
            fh.close()

    def relay_loop():
        while not stop_event.is_set():
            hub.tick()
            stop_event.wait(RELAY_POLL_SEC)

    _write_switch(on_path, my_pid, 0)
    threading.Thread(target=tail_loop, daemon=True).start()
    threading.Thread(target=relay_loop, daemon=True).start()

    try:
        while not stop_event.is_set():
            if time.monotonic() - last_activity[0] >= args.idle_sec:
                stop_event.set()
                break
            stop_event.wait(TAIL_INTERVAL)
    finally:
        current = _read_switch(on_path)
        if current is not None and current[0] == my_pid:
            try:
                os.remove(on_path)
            except OSError:
                pass
    return 0


# ------------------------------------------------------------ cloud (cloud-city)

def cmd_cloud(args):
    """cloud-city-1: `cloud --secret <join file> --cloud-file <path> [--probe]`
    prints ONE line, exit 0: "on <host>" | "off <host>" | "none" (no join
    file). Without --probe: from the marker only, no network. With --probe:
    one sync (no lines, no view); its reply sets the marker and decides the
    line; a relay that is down or refuses -> the marker decides. The key is
    never printed."""
    joined = read_join(args.secret)
    if joined is None:
        print("none")
        return 0
    host = urlsplit(joined["address"]).netloc
    if args.probe and not check_address(joined["address"]):
        state, data = sync(joined["address"], joined["key"], _default_dev_id(), 0, [])
        if state == "ok":
            set_cloud(args.cloud_file, host, bool(data.get("city")))
    on = host in read_cloud(args.cloud_file)
    print("%s %s" % ("on" if on else "off", host))
    return 0


def cmd_talk(args):
    """cloud-city-2: `talk --secret <join file> --talk-file <path> on|off|status`
    prints ONE line. status: "on <host>" | "off <host>" from the talk file (no
    network), exit 0; no join file -> "none" (exit 0 for status, else 1).
    on: the talk key is the first line of stdin (never argv, never printed);
    one sync (no lines) carries it as X-City-Talk: the relay says on -> saved,
    "on <host>", 0; refused -> "refused <host>", 3; off or nothing about talk ->
    "no-talk <host>", 4; down or the team key refused -> "down <host>", 5;
    could not save -> "not-saved <host>", 6; no key -> "no-key", 2. Nothing is
    saved unless the relay said on. off: one sync with {"off": true} when the
    file had the host (whatever it answers), the host leaves the file, "off
    <host>", 0."""
    joined = read_join(args.secret)
    if joined is None:
        print("none")
        return 0 if args.verb == "status" else 1
    address = joined["address"]
    host = urlsplit(address).netloc
    held = read_talk(args.talk_file)

    if args.verb == "status":
        print("%s %s" % ("on" if host in held else "off", host))
        return 0

    if args.verb == "off":
        if host in held and not check_address(address):
            sync(address, joined["key"], _default_dev_id(), 0, [],
                 talk={"off": True}, talk_key=held[host])
        set_talk(args.talk_file, host, None)
        print("off %s" % host)
        return 0

    key = sys.stdin.readline().strip()
    if not key:
        print("no-key")
        return 2
    if len(key.split()) != 1:
        # no line of the talk file could hold it: the relay has no such key
        print("refused %s" % host)
        return 3
    if check_address(address):
        print("down %s" % host)
        return 5
    state, data = sync(address, joined["key"], _default_dev_id(), 0, [], talk_key=key)
    if state != "ok":
        print("down %s" % host)
        return 5
    talk = data.get("talk")
    answer = talk.get("state") if isinstance(talk, dict) else None
    if answer == "refused":
        print("refused %s" % host)
        return 3
    if answer != "on":
        print("no-talk %s" % host)
        return 4
    set_talk(args.talk_file, host, key)
    if read_talk(args.talk_file).get(host) != key:
        print("not-saved %s" % host)
        return 6
    print("on %s" % host)
    return 0


def cmd_start(args):
    """cloud-city-3: `start --secret <join file> --talk-file <path> --start-file
    <path> on|off|status` prints ONE line. No new secret: the key is the talk
    key. status: "on <host>" only when the start file has the host AND the talk
    file has a key for it (start needs talk), else "off <host>" (no network),
    exit 0; no join file -> "none" (exit 0 for status, else 1). on: the talk key
    is the first line of stdin (typed again by the owner: never argv, never
    printed, never saved); no key -> "no-key", 2; no key for this host in the
    talk file (talk is off here) -> "no-talk-here <host>", 7, nothing sent; else
    one sync (no lines) carries the typed key as X-City-Talk and the talk
    {"start": {}}: refused -> "refused <host>", 3; talk off or nothing about
    talk -> "no-talk <host>", 4; down or the team key refused -> "down <host>",
    5; talk on but no "start" with state "on" (an old relay code) -> "old-relay
    <host>", 8; talk on and start on -> the host goes into the start file, "on
    <host>", 0 (could not save -> "no-write", 6). Nothing is saved unless
    the last one; the start file never holds a key. off: one sync with {"start":
    {"off": true}} and the talk file's key when the start file had the host (no
    key there: no request); whatever it answers, the host leaves the file, "off
    <host>", 0."""
    joined = read_join(args.secret)
    if joined is None:
        print("none")
        return 0 if args.verb == "status" else 1
    address = joined["address"]
    host = urlsplit(address).netloc
    held = read_talk(args.talk_file)

    if args.verb == "status":
        on = host in read_start(args.start_file) and host in held
        print("%s %s" % ("on" if on else "off", host))
        return 0

    if args.verb == "off":
        if host in read_start(args.start_file) and host in held and not check_address(address):
            sync(address, joined["key"], _default_dev_id(), 0, [],
                 talk={"start": {"off": True}}, talk_key=held[host])
        set_start(args.start_file, host, False)
        print("off %s" % host)
        return 0

    key = sys.stdin.readline().strip()
    if not key:
        print("no-key")
        return 2
    if host not in held:
        print("no-talk-here %s" % host)
        return 7
    if len(key.split()) != 1:
        # no line of the talk file could hold it: the relay has no such key
        print("refused %s" % host)
        return 3
    if check_address(address):
        print("down %s" % host)
        return 5
    state, data = sync(address, joined["key"], _default_dev_id(), 0, [],
                       talk={"start": {}}, talk_key=key)
    if state != "ok":
        print("down %s" % host)
        return 5
    talk = data.get("talk")
    answer = talk.get("state") if isinstance(talk, dict) else None
    if answer == "refused":
        print("refused %s" % host)
        return 3
    if answer != "on":
        print("no-talk %s" % host)
        return 4
    start = talk.get("start")
    if not isinstance(start, dict) or start.get("state") != "on":
        print("old-relay %s" % host)
        return 8
    set_start(args.start_file, host, True)
    if host not in read_start(args.start_file):
        print("no-write")
        return 6
    print("on %s" % host)
    return 0


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

    p_join.add_argument("--cloud-file", default=None)

    p_cloud = sub.add_parser("cloud")
    p_cloud.add_argument("--secret", required=True)
    p_cloud.add_argument("--cloud-file", required=True)
    p_cloud.add_argument("--probe", action="store_true")

    p_talk = sub.add_parser("talk")
    p_talk.add_argument("--secret", required=True)
    p_talk.add_argument("--talk-file", required=True)
    p_talk.add_argument("verb", choices=("on", "off", "status"))

    p_start = sub.add_parser("start")
    p_start.add_argument("--secret", required=True)
    p_start.add_argument("--talk-file", required=True)
    p_start.add_argument("--start-file", required=True)
    p_start.add_argument("verb", choices=("on", "off", "status"))

    p_send = sub.add_parser("send")
    p_send.add_argument("--dir", required=True)
    p_send.add_argument("--relay-sec", type=float, default=5.0)
    p_send.add_argument("--idle-sec", type=float, default=1800.0)
    p_send.add_argument("--lang", default="zh")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if args.cmd not in ("check", "join", "send", "cloud", "talk", "start"):
        parser.print_usage(sys.stderr)
        return 2

    if args.cmd == "send":
        return cmd_send(args)
    if args.cmd == "cloud":
        return cmd_cloud(args)
    if args.cmd == "talk":
        return cmd_talk(args)
    if args.cmd == "start":
        return cmd_start(args)

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
        if args.cloud_file:
            # cloud-city-1: the accepted sync's reply tells whether the relay
            # has the cloud page on; the marker keeps it (hosts only).
            set_cloud(args.cloud_file, host, bool((_data or {}).get("city")))

    print("RELAY: ok %s" % host)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
