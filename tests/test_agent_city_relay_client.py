"""Failing tests for bin/agent_city_relay.py, the local side of joining a team
relay (requirements/city.md, "Joining").

Python standard library only, Python 3.8+. It never runs in the hook: the
local city server (bin/agent_city.py serve) uses it to send its lines to the
team relay and get the other members' lines back, and bin/agent-city.sh
join uses its CLI. The relay contract is in
tests/test_agent_city_relay_worker.py.

The join file, one per repo, written by the person, never by an agent:

    <repo>/.secrets/agent-city-relay     mode 0600
        address=https://<relay address>
        key=<team key>
    Blank lines and lines starting with # are ignored. Spaces around the
    value are stripped. A file without both values counts as not joined.

Module API:

    OUTBOX_CAP = 500        unsent lines kept per team, oldest dropped first
    MAX_BATCH = 200         lines per sync, the relay's own limit

    read_join(path) -> {"address": str, "key": str} or None
    write_join(path, address, key)
        makes the folder, writes atomically (tmp + rename, no tmp left
        behind), file mode 0600.
    check_address(address) -> None when fine, else a short error text.
        https://<host>[...] is fine. http:// only for 127.0.0.1, localhost
        and private LAN IPv4 addresses (10.0.0.0/8, 172.16.0.0/12,
        192.168.0.0/16: the dev relay of the two-machine LAN test).
    origin_id(url) -> "host/owner/repo", lower case, or None.
        Takes any git remote form, drops the scheme, user, password, port,
        ".git" and a trailing "/". A local path or file:// remote is None
        (not shared, stays local).
    to_wire(line, ctx) -> the line as sent to the relay.
        Keeps only ev sid aid at tool nt role desc sub klen kind (missing =
        ""), adds ctx's rid br who dev. An empty or blank who becomes the
        dev (owner decision: a machine with no git user.name is named by
        its device, never a blank name). Drops proj, repo and q (chat text).
        Every value a string of at most 200 characters. Inside the kept
        text, a word that is an absolute path (starts with "/" or "~/")
        becomes its last part: "fix /Users/ann/shop/api/login.py" ->
        "fix login.py". Never a full path.
    class Outbox(cap=OUTBOX_CAP)
        add(item); take(n) -> oldest n, removed; putback(items) -> back to
        the front, in order; len(box); box.dropped = lines dropped so far.
        Over cap, the oldest go first.
    sync(address, key, dev, after, lines, timeout=10.0) -> (state, data)
        POST <address>/v1/sync with Authorization: Bearer <key>.
        ("ok", {"seq": int, "lines": [...]}) on 200 with ok true.
        ("refused", None) on 401 or 403.
        ("down", None) on anything else: no answer, timeout, 5xx, not JSON,
        a redirect. A redirect is never followed: the key goes to the
        address the person gave and nowhere else.
    class RelayHub(relay_sec=5.0, dev_id=None, label=None, cap=OUTBOX_CAP,
                   join_ttl=30.0, timeout=10.0)
        One hub per city server. dev_id: this machine's id at the relay,
        default a stable id for this machine and user (same every start,
        never the key). label: the device tag other members see, default
        the short host name, or 云端 when CLAUDE_CODE_REMOTE is set.
        offer(line) -> True when the line was queued for a team.
            The line's "repo" is the git common dir (<root>/.git); the join
            file is <root>/.secrets/agent-city-relay, read at most every
            join_ttl seconds. Not joined, no origin, or no "repo" -> False.
            ctx: rid = origin_id(origin), who = the repo's git user.name,
            dev = label, br = the branch of the session's worktree. The hook
            keeps only the FOLDER NAME of the cwd in "proj" (never a path),
            so br is found by listing the repo's worktrees (git worktree
            list --porcelain, cached for join_ttl) and taking the one whose
            folder name is "proj". No match (e.g. the cwd was a subfolder)
            or a detached HEAD -> "".
        tick() -> [{"dev": <sender id>, "line": <their wire line>}, ...]
            Syncs every team that is due (relay_sec since its last sync;
            0 = always due), at most MAX_BATCH lines each. "after" is the
            seq of the team's last good sync. A team = one (address, key);
            two repos with the same address and key share one team.
            refused or down -> the lines go back to the front of the outbox.
            A team none of whose repos still has its join file (leave, or a
            new key) is dropped with its queue, at the next tick after
            join_ttl.
            A relay that answers with a seq LOWER than the team's "after"
            was made again (new database, or a dev relay restarted): the
            team's "after" goes back to 0 at once, so its new lines are
            not missed.
        status() -> {"joined": bool, "teams": [{"host": "<host[:port]>",
            "rids": [sorted], "state": "new" | "ok" | "off" | "refused",
            "queued": int, "dropped": int}]}
            Never the key, never the full address.
        joined() -> bool, same as status()["joined"].
        repo_for(rid) -> the real path of the git common dir of a joined
            local repo whose origin gives rid (any repo offer() has queued a
            line for), or None.
        identity() -> {"who": git user.name of the first joined repo seen,
            else the label (never blank), "device": label}.
        Safe to call from two threads: offer() from the file-tail thread,
        tick()/status()/joined() from others. tick() never holds the hub's
        lock while it waits for the relay.

CLI (the key is always read from the first line of stdin, never argv):

    python3 agent_city_relay.py check --address URL
    python3 agent_city_relay.py join  --address URL --file PATH
        check: tests the address and key with one empty sync.
        join:  the same, then write_join(PATH, URL, key) only when ok.
        exit 0  "RELAY: ok <host>"
        exit 2  bad address, or no key on stdin; nothing written
        exit 3  "RELAY: the relay refused the key"; nothing written
        exit 4  "RELAY: cannot reach <host>"; nothing written
        The key never appears in stdout or stderr.

Run: python3 -m unittest tests.test_agent_city_relay_client
"""

import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
CLIENT = os.path.join(BIN, "agent_city_relay.py")
WORKER = os.path.join(BIN, "agent-city-relay.js")
HARNESS = os.path.join(HERE, "relay_harness.mjs")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

from relayhelp import (FAKE_KEY, FakeRelay, add_worktree, hook_line, join,  # noqa: E402
                       make_repo, wait_for)

try:
    import agent_city_relay as rl  # noqa: E402
except ImportError:  # the module is not written yet: every test fails, none errors on import
    rl = None


def closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Case(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(rl, "bin/agent_city_relay.py is missing or does not import")
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_relay_"))
        self.relays = []

    def tearDown(self):
        for r in self.relays:
            r.stop()
        shutil.rmtree(self.base, ignore_errors=True)

    def relay(self, key=FAKE_KEY):
        r = FakeRelay(key)
        self.relays.append(r)
        return r


# ---------------------------------------------------------------- join file

class TestJoinFile(Case):
    def test_write_then_read(self):
        path = os.path.join(self.base, "repo", ".secrets", "agent-city-relay")
        rl.write_join(path, "https://relay.example.workers.dev", "k-123")
        self.assertEqual(rl.read_join(path),
                         {"address": "https://relay.example.workers.dev", "key": "k-123"})

    def test_written_file_is_0600_and_no_tmp_left(self):
        folder = os.path.join(self.base, ".secrets")
        path = os.path.join(folder, "agent-city-relay")
        rl.write_join(path, "https://r.example", "k")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(os.listdir(folder), ["agent-city-relay"])

    def test_overwrite_keeps_0600(self):
        path = os.path.join(self.base, ".secrets", "agent-city-relay")
        rl.write_join(path, "https://a.example", "k1")
        rl.write_join(path, "https://b.example", "k2")
        self.assertEqual(rl.read_join(path)["key"], "k2")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_missing_file_is_none(self):
        self.assertIsNone(rl.read_join(os.path.join(self.base, "nope")))

    def test_half_a_file_is_none(self):
        path = os.path.join(self.base, "f")
        for text in ("address=https://a.example\n", "key=k\n", "address=\nkey=k\n", "", "junk\n"):
            with self.subTest(text=text):
                with open(path, "w") as fh:
                    fh.write(text)
                self.assertIsNone(rl.read_join(path))

    def test_comments_blank_lines_and_spaces(self):
        path = os.path.join(self.base, "f")
        with open(path, "w") as fh:
            fh.write("# team relay\n\n  address = https://a.example  \nkey =  k-9 \n")
        self.assertEqual(rl.read_join(path), {"address": "https://a.example", "key": "k-9"})


class TestCheckAddress(Case):
    def test_good(self):
        for a in ("https://city.ann.workers.dev", "https://relay.example.com/",
                  "http://127.0.0.1:8787", "http://localhost:9000"):
            with self.subTest(a=a):
                self.assertIsNone(rl.check_address(a))

    def test_lan_http_for_the_dev_relay(self):
        # the two-machine LAN test (tests/test_agent_city_relay_dev.py)
        for a in ("http://192.168.1.20:8787", "http://10.0.0.5:8787", "http://172.16.0.9:8787",
                  "http://172.31.255.1"):
            with self.subTest(a=a):
                self.assertIsNone(rl.check_address(a))
        for a in ("http://8.8.8.8:8787", "http://172.32.0.1", "http://192.169.0.1",
                  "http://11.0.0.1"):
            with self.subTest(a=a):
                self.assertTrue(rl.check_address(a))

    def test_bad(self):
        for a in ("", "relay.example.com", "http://relay.example.com", "ftp://x",
                  "https://", "http://127.0.0.2:80", "https://a b.example"):
            with self.subTest(a=a):
                self.assertTrue(rl.check_address(a))


# ------------------------------------------------------------------ wire

class TestOriginId(Case):
    def test_forms(self):
        cases = {
            "git@github.com:Acme/Shop.git": "github.com/acme/shop",
            "https://github.com/acme/shop.git": "github.com/acme/shop",
            "https://github.com/acme/shop": "github.com/acme/shop",
            "https://github.com/acme/shop/": "github.com/acme/shop",
            "https://ann:tok3n@github.com/acme/shop.git": "github.com/acme/shop",
            "ssh://git@gitlab.example.com:2222/group/sub/app.git": "gitlab.example.com/group/sub/app",
            "git://example.org/acme/shop.git": "example.org/acme/shop",
        }
        for url, want in cases.items():
            with self.subTest(url=url):
                self.assertEqual(rl.origin_id(url), want)

    def test_not_shared(self):
        for url in (None, "", "/Users/ann/repos/shop", "../shop", "file:///Users/ann/shop.git"):
            with self.subTest(url=url):
                self.assertIsNone(rl.origin_id(url))

    def test_password_never_kept(self):
        self.assertNotIn("tok3n", rl.origin_id("https://ann:tok3n@github.com/acme/shop.git"))


CTX = {"rid": "github.com/acme/shop", "br": "feature/x", "who": "Ann", "dev": "mac-1"}


class TestToWire(Case):
    def line(self, **kw):
        base = {"ev": "PostToolUse", "sid": "s1", "aid": "a1", "at": "worker", "tool": "Bash",
                "nt": "", "proj": "/Users/ann/secret/shop", "role": "worker",
                "desc": "fix login", "sub": "worker", "q": "what is my password?",
                "klen": "12", "repo": "/Users/ann/secret/shop/.git", "kind": "test"}
        base.update(kw)
        return base

    def test_keys(self):
        wire = rl.to_wire(self.line(), CTX)
        self.assertEqual(set(wire), {"ev", "sid", "aid", "at", "tool", "nt", "role", "desc",
                                     "sub", "klen", "kind", "rid", "br", "who", "dev"})
        self.assertEqual(wire["rid"], "github.com/acme/shop")
        self.assertEqual(wire["br"], "feature/x")
        self.assertEqual(wire["who"], "Ann")
        self.assertEqual(wire["dev"], "mac-1")
        self.assertEqual(wire["tool"], "Bash")
        self.assertEqual(wire["desc"], "fix login")

    def test_no_full_path_no_chat_text(self):
        wire = rl.to_wire(self.line(), CTX)
        text = json.dumps(wire)
        self.assertNotIn("/Users/", text)
        self.assertNotIn("password", text)

    def test_paths_inside_text_become_their_last_part(self):
        wire = rl.to_wire(self.line(desc="fix /Users/ann/shop/api/login.py now",
                                    sub="~/.ssh/id_rsa"), CTX)
        self.assertEqual(wire["desc"], "fix login.py now")
        self.assertEqual(wire["sub"], "id_rsa")

    def test_missing_and_odd_values(self):
        wire = rl.to_wire({"ev": "Stop", "sid": None, "klen": 7}, CTX)
        self.assertEqual(wire["sid"], "")
        self.assertEqual(wire["klen"], "7")
        self.assertEqual(wire["tool"], "")
        self.assertTrue(all(isinstance(v, str) for v in wire.values()))

    def test_no_user_name_means_the_device_name(self):
        for who in ("", "   "):
            with self.subTest(who=who):
                self.assertEqual(rl.to_wire(self.line(), dict(CTX, who=who))["who"], "mac-1")

    def test_capped_at_200(self):
        wire = rl.to_wire(self.line(desc="x" * 500), CTX)
        self.assertEqual(len(wire["desc"]), 200)


# ------------------------------------------------------------------ outbox

class TestOutbox(Case):
    def test_order_and_take(self):
        box = rl.Outbox(cap=10)
        for i in range(4):
            box.add(i)
        self.assertEqual(len(box), 4)
        self.assertEqual(box.take(3), [0, 1, 2])
        self.assertEqual(box.take(3), [3])
        self.assertEqual(box.take(3), [])

    def test_oldest_dropped_over_cap(self):
        box = rl.Outbox(cap=3)
        for i in range(5):
            box.add(i)
        self.assertEqual(box.dropped, 2)
        self.assertEqual(box.take(10), [2, 3, 4])

    def test_putback_goes_to_front_and_respects_cap(self):
        box = rl.Outbox(cap=4)
        box.add("a")
        box.add("b")
        taken = box.take(2)
        box.add("c")
        box.add("d")
        box.add("e")
        box.putback(taken)
        self.assertEqual(len(box), 4)
        self.assertEqual(box.dropped, 1)
        self.assertEqual(box.take(10), ["b", "c", "d", "e"])

    def test_default_cap(self):
        self.assertEqual(rl.OUTBOX_CAP, 500)
        self.assertEqual(rl.MAX_BATCH, 200)


# ------------------------------------------------------------------ sync

class TestSync(Case):
    def test_ok(self):
        relay = self.relay()
        relay.push("other", {"ev": "Stop"})
        state, data = rl.sync(relay.url, FAKE_KEY, "me", 0, [{"ev": "PreToolUse"}])
        self.assertEqual(state, "ok")
        self.assertEqual(data["seq"], 2)
        self.assertEqual(data["lines"], [{"seq": 1, "dev": "other", "line": {"ev": "Stop"}}])
        req = relay.requests[0]
        self.assertEqual(req["auth"], "Bearer " + FAKE_KEY)
        self.assertEqual(req["body"], {"dev": "me", "after": 0, "lines": [{"ev": "PreToolUse"}]})

    def test_trailing_slash_in_address(self):
        relay = self.relay()
        state, _ = rl.sync(relay.url + "/", FAKE_KEY, "me", 0, [])
        self.assertEqual(state, "ok")
        self.assertEqual(relay.requests[0]["path"], "/v1/sync")

    def test_refused(self):
        relay = self.relay()
        self.assertEqual(rl.sync(relay.url, "wrong", "me", 0, []), ("refused", None))

    def test_down(self):
        self.assertEqual(rl.sync("http://127.0.0.1:%d" % closed_port(), FAKE_KEY, "me", 0, [],
                                 timeout=2.0), ("down", None))

    def test_redirect_is_down_and_never_followed(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                target = self.relay()
                src = self.relay()
                src.mode = "redirect"
                src.redirect_to = target.url
                src.redirect_code = code
                self.assertEqual(rl.sync(src.url, FAKE_KEY, "me", 0, [{"ev": "Stop"}]),
                                 ("down", None))
                self.assertEqual(target.requests, [], "the key followed a redirect")

    def test_server_error_and_garbage_are_down(self):
        relay = self.relay()
        for mode in ("error", "garbage"):
            with self.subTest(mode=mode):
                relay.mode = mode
                self.assertEqual(rl.sync(relay.url, FAKE_KEY, "me", 0, []), ("down", None))


# ------------------------------------------------------------------ hub

class HubCase(Case):
    def setUp(self):
        super().setUp()
        self.fake = self.relay()
        self.repo = make_repo(self.base)

    def hub(self, **kw):
        opts = dict(relay_sec=0, dev_id="dev-me", label="mac-1", join_ttl=0, timeout=3.0)
        opts.update(kw)
        return rl.RelayHub(**opts)


class TestHubNotJoined(HubCase):
    def test_not_joined_sends_nothing(self):
        hub = self.hub()
        self.assertFalse(hub.offer(hook_line(self.repo)))
        self.assertEqual(hub.tick(), [])
        self.assertEqual(self.fake.requests, [])
        self.assertEqual(hub.status(), {"joined": False, "teams": []})
        self.assertFalse(hub.joined())

    def test_no_origin_stays_local(self):
        local = make_repo(self.base, "local", origin=None)
        join(local, self.fake.url)
        hub = self.hub()
        self.assertFalse(hub.offer(hook_line(local)))
        hub.tick()
        self.assertEqual(self.fake.sent_lines(), [])

    def test_line_without_repo(self):
        join(self.repo, self.fake.url)
        hub = self.hub()
        no_repo = hook_line(self.repo)
        no_repo["repo"] = ""
        self.assertFalse(hub.offer(no_repo))
        self.assertFalse(hub.offer({"ev": "Stop"}))
        self.assertFalse(hub.offer("not a dict"))


class TestHubJoined(HubCase):
    def setUp(self):
        super().setUp()
        join(self.repo, self.fake.url)

    def test_sends_the_wire_line(self):
        hub = self.hub()
        self.assertTrue(hub.offer(hook_line(self.repo, desc="fix %s/api/x.py" % self.repo,
                                            q="secret question")))
        hub.tick()
        sent = self.fake.sent_lines()
        self.assertEqual(len(sent), 1)
        wire = sent[0]
        self.assertEqual(wire["rid"], "github.com/acme/shop")
        self.assertEqual(wire["br"], "main")
        self.assertEqual(wire["who"], "Ann")
        self.assertEqual(wire["dev"], "mac-1")
        self.assertEqual(wire["desc"], "fix x.py")
        body = json.dumps(self.fake.sync_bodies())
        self.assertNotIn(self.base, body)
        self.assertNotIn("secret question", body)
        self.assertEqual(self.fake.sync_bodies()[0]["dev"], "dev-me")

    def test_worktree_line_uses_main_repo_join_and_worktree_branch(self):
        wt = add_worktree(self.repo, "feature/relay")
        hub = self.hub()
        self.assertTrue(hub.offer(hook_line(self.repo, proj=wt)))
        hub.tick()
        self.assertEqual(self.fake.sent_lines()[0]["br"], "feature/relay")

    def test_subfolder_or_unknown_folder_gives_no_branch(self):
        hub = self.hub()
        hub.offer(hook_line(self.repo, proj=os.path.join(self.repo, "api")))
        hub.tick()
        self.assertEqual(self.fake.sent_lines()[0]["br"], "")

    def test_remote_lines_come_back_and_after_moves(self):
        hub = self.hub()
        hub.offer(hook_line(self.repo))
        self.fake.push("dev-other", {"ev": "Stop", "who": "Bo"})
        got = hub.tick()
        self.assertEqual(got, [{"dev": "dev-other", "line": {"ev": "Stop", "who": "Bo"}}])
        first_seq = self.fake.seq
        self.assertEqual(hub.tick(), [], "the same line is never handed out twice")
        self.assertEqual(self.fake.sync_bodies()[1]["after"], first_seq)
        self.assertEqual(hub.status()["teams"][0]["state"], "ok")

    def test_relay_made_again(self):
        hub = self.hub()
        hub.offer(hook_line(self.repo))
        for i in range(3):
            self.fake.push("dev-other", {"ev": "Stop", "n": i})
        self.assertEqual(len(hub.tick()), 3)
        self.fake.reset()
        self.fake.push("dev-other", {"ev": "Stop", "n": "after-reset"})
        got = hub.tick() + hub.tick()
        self.assertEqual([g["line"]["n"] for g in got], ["after-reset"],
                         "a line sent right after the relay was made again was missed")

    def test_syncs_to_receive_even_with_nothing_to_send(self):
        hub = self.hub()
        hub.offer(hook_line(self.repo))
        hub.tick()
        self.fake.push("dev-other", {"ev": "PreToolUse"})
        self.assertEqual(len(hub.tick()), 1)

    def test_batches_of_200(self):
        hub = self.hub()
        for i in range(450):
            hub.offer(hook_line(self.repo, sid="s%d" % i))
        hub.tick()
        hub.tick()
        hub.tick()
        sizes = [len(b["lines"]) for b in self.fake.sync_bodies()]
        self.assertEqual(sizes, [200, 200, 50])

    def test_down_keeps_lines_then_sends_them(self):
        hub = self.hub()
        self.fake.mode = "error"
        hub.offer(hook_line(self.repo, sid="a"))
        hub.offer(hook_line(self.repo, sid="b"))
        hub.tick()
        team = hub.status()["teams"][0]
        self.assertEqual((team["state"], team["queued"]), ("off", 2))
        self.fake.mode = "ok"
        hub.tick()
        self.assertEqual([l["sid"] for l in self.fake.sent_lines()], ["a", "b"])
        team = hub.status()["teams"][0]
        self.assertEqual((team["state"], team["queued"]), ("ok", 0))

    def test_relay_gone_is_off(self):
        hub = self.hub()
        hub.offer(hook_line(self.repo))
        self.fake.stop()
        hub.tick()
        self.assertEqual(hub.status()["teams"][0]["state"], "off")

    def test_refused(self):
        hub = self.hub()
        self.fake.mode = "refuse"
        hub.offer(hook_line(self.repo))
        hub.tick()
        team = hub.status()["teams"][0]
        self.assertEqual((team["state"], team["queued"]), ("refused", 1))

    def test_cap_drops_oldest(self):
        hub = self.hub(cap=3)
        self.fake.mode = "error"
        for i in range(5):
            hub.offer(hook_line(self.repo, sid="s%d" % i))
        hub.tick()
        team = hub.status()["teams"][0]
        self.assertEqual((team["queued"], team["dropped"]), (3, 2))
        self.fake.mode = "ok"
        hub.tick()
        self.assertEqual([l["sid"] for l in self.fake.sent_lines()], ["s2", "s3", "s4"])

    def test_status_shape_and_no_key(self):
        hub = self.hub()
        self.assertEqual(hub.status(), {"joined": False, "teams": []})
        hub.offer(hook_line(self.repo))
        st = hub.status()
        self.assertTrue(st["joined"])
        self.assertTrue(hub.joined())
        self.assertEqual(st["teams"], [{"host": self.fake.host, "rids": ["github.com/acme/shop"],
                                        "state": "new", "queued": 1, "dropped": 0}])
        self.assertNotIn(FAKE_KEY, json.dumps(st))

    def test_relay_sec_spaces_syncs(self):
        hub = self.hub(relay_sec=60)
        hub.offer(hook_line(self.repo))
        hub.tick()
        hub.tick()
        hub.tick()
        self.assertEqual(len(self.fake.sync_bodies()), 1)

    def test_two_repos_same_team_one_sync(self):
        other = make_repo(self.base, "api", origin="https://github.com/acme/api.git")
        join(other, self.fake.url)
        hub = self.hub()
        hub.offer(hook_line(self.repo))
        hub.offer(hook_line(other))
        hub.tick()
        self.assertEqual(len(self.fake.sync_bodies()), 1)
        self.assertEqual(sorted(l["rid"] for l in self.fake.sent_lines()),
                         ["github.com/acme/api", "github.com/acme/shop"])
        st = hub.status()
        self.assertEqual(len(st["teams"]), 1)
        self.assertEqual(st["teams"][0]["rids"], ["github.com/acme/api", "github.com/acme/shop"])

    def test_two_teams(self):
        second = self.relay(key="other-fake-key")
        other = make_repo(self.base, "api", origin="https://github.com/acme/api.git")
        join(other, second.url, key="other-fake-key")
        hub = self.hub()
        hub.offer(hook_line(self.repo))
        hub.offer(hook_line(other))
        hub.tick()
        self.assertEqual([l["rid"] for l in self.fake.sent_lines()], ["github.com/acme/shop"])
        self.assertEqual([l["rid"] for l in second.sent_lines()], ["github.com/acme/api"])
        self.assertEqual(len(hub.status()["teams"]), 2)

    def test_leave_drops_the_team(self):
        hub = self.hub()
        hub.offer(hook_line(self.repo))
        hub.tick()
        os.remove(os.path.join(self.repo, ".secrets", "agent-city-relay"))
        hub.tick()
        before = len(self.fake.requests)
        self.assertEqual(hub.status(), {"joined": False, "teams": []})
        self.assertFalse(hub.offer(hook_line(self.repo)))
        hub.tick()
        self.assertEqual(len(self.fake.requests), before, "no sync after leave")

    def test_join_file_is_cached_for_join_ttl(self):
        hub = self.hub(join_ttl=600)
        self.assertTrue(hub.offer(hook_line(self.repo)))
        os.remove(os.path.join(self.repo, ".secrets", "agent-city-relay"))
        self.assertTrue(hub.offer(hook_line(self.repo)), "read at most every join_ttl seconds")

    def test_repo_for_and_identity(self):
        hub = self.hub()
        self.assertEqual(hub.identity(), {"who": "mac-1", "device": "mac-1"})
        self.assertIsNone(hub.repo_for("github.com/acme/shop"))
        hub.offer(hook_line(self.repo))
        self.assertEqual(hub.repo_for("github.com/acme/shop"),
                         os.path.realpath(os.path.join(self.repo, ".git")))
        self.assertIsNone(hub.repo_for("github.com/other/thing"))
        self.assertEqual(hub.identity(), {"who": "Ann", "device": "mac-1"})

    def test_repo_without_user_name(self):
        env = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        with mock.patch.dict(os.environ, env):
            nameless = make_repo(self.base, "pc2repo", origin="git@github.com:Acme/Shop.git")
            subprocess.run(["git", "-C", nameless, "config", "--unset", "user.name"], check=True)
            join(nameless, self.fake.url)
            hub = self.hub(label="pc2")
            hub.offer(hook_line(nameless))
            hub.tick()
            self.assertEqual(self.fake.sent_lines()[-1]["who"], "pc2")
            self.assertEqual(hub.identity(), {"who": "pc2", "device": "pc2"})

    def test_default_ids(self):
        a = rl.RelayHub()
        b = rl.RelayHub()
        self.assertTrue(a.dev_id)
        self.assertEqual(a.dev_id, b.dev_id, "same machine, same id, every start")
        self.assertTrue(a.label)
        env = dict(os.environ, CLAUDE_CODE_REMOTE="true")
        out = subprocess.run(
            [sys.executable, "-c", "import sys; sys.path.insert(0, %r); import agent_city_relay as rl;"
             " print(rl.RelayHub().label)" % BIN],
            capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(out.stdout.strip(), "云端")


# ------------------------------------------------------------------ CLI

class TestCli(Case):
    def run_cli(self, *args, stdin=FAKE_KEY + "\n"):
        return subprocess.run([sys.executable, CLIENT] + list(args), input=stdin,
                              capture_output=True, text=True, timeout=30)

    def assert_no_key(self, proc, key=FAKE_KEY):
        self.assertNotIn(key, proc.stdout + proc.stderr)

    def test_check_ok(self):
        relay = self.relay()
        proc = self.run_cli("check", "--address", relay.url)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RELAY: ok " + relay.host, proc.stdout)
        self.assert_no_key(proc)
        self.assertEqual(relay.sync_bodies()[0]["lines"], [])

    def test_check_refused(self):
        relay = self.relay(key="another-key")
        proc = self.run_cli("check", "--address", relay.url)
        self.assertEqual(proc.returncode, 3)
        self.assertIn("refused", proc.stdout)
        self.assert_no_key(proc)

    def test_check_down(self):
        proc = self.run_cli("check", "--address", "http://127.0.0.1:%d" % closed_port())
        self.assertEqual(proc.returncode, 4)
        self.assertIn("cannot reach", proc.stdout)

    def test_check_bad_address_or_no_key(self):
        self.assertEqual(self.run_cli("check", "--address", "http://relay.example.com").returncode, 2)
        relay = self.relay()
        self.assertEqual(self.run_cli("check", "--address", relay.url, stdin="").returncode, 2)
        self.assertEqual(relay.requests, [])

    def test_join_writes_only_when_ok(self):
        relay = self.relay()
        path = os.path.join(self.base, "repo", ".secrets", "agent-city-relay")
        proc = self.run_cli("join", "--address", relay.url, "--file", path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assert_no_key(proc)
        self.assertEqual(rl.read_join(path), {"address": relay.url, "key": FAKE_KEY})
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_join_refused_or_down_writes_nothing(self):
        path = os.path.join(self.base, "repo", ".secrets", "agent-city-relay")
        relay = self.relay(key="another-key")
        self.assertEqual(self.run_cli("join", "--address", relay.url, "--file", path).returncode, 3)
        self.assertEqual(self.run_cli("join", "--address", "http://127.0.0.1:%d" % closed_port(),
                                      "--file", path).returncode, 4)
        self.assertEqual(self.run_cli("join", "--address", "https://", "--file", path).returncode, 2)
        self.assertFalse(os.path.exists(path))


# ------------------------------------------------- against the real Worker

@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestAgainstRealWorker(Case):
    """bin/agent-city-relay.js under Node (tests/relay_harness.mjs serve), so
    the client and the Worker are proven to speak the same contract."""

    def setUp(self):
        super().setUp()
        self.assertTrue(os.path.isfile(WORKER), "bin/agent-city-relay.js is missing")
        self.proc = subprocess.Popen(["node", HARNESS, WORKER, "serve", FAKE_KEY],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        port = self.proc.stdout.readline().strip()
        self.assertTrue(port.isdigit(), self.proc.stderr.read() if not port else port)
        self.url = "http://127.0.0.1:" + port

    def tearDown(self):
        self.proc.terminate()
        self.proc.wait(5)
        self.proc.stdout.close()
        self.proc.stderr.close()
        super().tearDown()

    def test_two_machines_through_the_worker(self):
        self.assertEqual(rl.sync(self.url, "wrong", "a", 0, [])[0], "refused")
        state, data = rl.sync(self.url, FAKE_KEY, "a", 0, [{"ev": "PreToolUse", "who": "Ann"}])
        self.assertEqual(state, "ok")
        state, data = rl.sync(self.url, FAKE_KEY, "b", 0, [])
        self.assertEqual(state, "ok")
        self.assertEqual([(x["dev"], x["line"]) for x in data["lines"]],
                         [("a", {"ev": "PreToolUse", "who": "Ann"})])

    def test_cli_check_against_the_worker(self):
        proc = subprocess.run([sys.executable, CLIENT, "check", "--address", self.url],
                              input=FAKE_KEY + "\n", capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_hub_through_the_worker(self):
        repo = make_repo(self.base)
        join(repo, self.url)
        me = rl.RelayHub(relay_sec=0, dev_id="dev-a", label="mac-a", join_ttl=0)
        them = rl.RelayHub(relay_sec=0, dev_id="dev-b", label="mac-b", join_ttl=0)
        me.offer(hook_line(repo, sid="mine"))
        me.tick()
        them.offer(hook_line(repo, sid="theirs"))
        got = them.tick()
        self.assertEqual([(g["dev"], g["line"]["sid"], g["line"]["dev"]) for g in got],
                         [("dev-a", "mine", "mac-a")])
        got = me.tick()
        self.assertEqual([g["line"]["sid"] for g in got], ["theirs"])


if __name__ == "__main__":
    unittest.main()
