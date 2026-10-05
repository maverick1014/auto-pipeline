"""Failing tests: join once per computer (requirements/city.md, "Joining";
city-device-join, owner 2026-10-05: "the setup so complicated. it need 1 repo
1 repo do ... what i want is just set for the device ya, for each repo").

The device join: <AGENT_CITY_HOME>/team-relay. The same two lines as a repo's
own join file ("address=<url>", "key=<team key>"), mode 0600, never inside a
repo, written only after the relay took the key.

  bin/agent_city_relay.py
    effective_join(root, device)
        The join that counts for the repo whose folder is ROOT, on a computer
        whose device join file is DEVICE (a path, or None): a dict with
        "address", "key" and "path" (the file it came from), or None.
          ROOT's own <root>/.secrets/agent-city-relay, when read_join takes it
          and (DEVICE gives no join, or its relay host is not the device's)
                                                         -> that file
          else DEVICE, when read_join takes it            -> the device file
          else                                            -> None
        Relay host = urlsplit(address).netloc. Same host = the device's key.
    RelayHub(..., device_join=PATH)       (default None: exactly as before)
        offer(), seed() and the joined-list seed take a repo's team from
        effective_join(): a line of a repo with no join file of its own goes
        to the device relay with the device key. A team made from the device
        file leaves when that file goes (next tick). env_join (a cloud
        session's AGENT_CITY_RELAY) wins: the device file is never used then.
        With joined_list=PATH: a repo whose line went to the team through the
        device file is added to that list by itself (realpath, once, never a
        key). A repo sending on its own other-relay join file is not added.

  bin/agent_city.py
    serve --device-join PATH              -> RelayHub(device_join=PATH)
    CityState.device_join (attribute; None by default): when it names a file
        read_join takes, health()["not_joined"] is [] (every repo is in).

  bin/agent-city.sh, not in a cloud session (CLAUDE_CODE_REMOTE unset)
    join    From any folder: a plain folder, a repo with no origin, a repo
            whose .secrets/ is not git-ignored, a worktree. Asks the address,
            then the team key hidden (prompts on stderr); the key goes to the
            relay check on stdin only. Relay ok -> <home>/team-relay (0600),
            "JOINED: this device -> <host> (all repos)", exit 0; inside a repo
            with a shared origin its main root also goes into the joined list.
            Never a repo's .secrets file. Bad address, no key, refused, down:
            exit 1, a reason, nothing saved. The key is never shown.
            Moving up: no device file, and a listed repo (joined-repos.txt,
            list order) whose folder and own join file are there -> before
            anything else one question line naming that relay host and
            "[Y/n]".
            Enter / y / yes: the relay checks THAT key (one sync with it), the
            device file gets its address and key, the same JOINED line; the
            key is never typed or shown. n / no: it asks as usual.
            A device that is already joined: asks as usual, an accepted new
            address and key replace the old ones.
    leave   From any folder: <home>/team-relay goes, the own join file of every
            listed repo and of the repo it runs in goes, the list keeps no
            path. "LEFT: ..." exit 0, also when nothing was joined. The talk
            and start files stay as they are.
    status  Device joined: "TEAM: joined <host> (this device, all repos)",
            inside or outside a repo. Outside a repo a listed repo whose own
            file names another relay adds "TEAM: joined <host> (<repo>)" after
            it; inside such a repo its line is "TEAM: joined <host>". The
            CLOUD, CLOUD TALK and CLOUD START lines work from any folder with
            the device host. Never the key.
    cloud-talk on|off, cloud-start on|off   From any folder with the device
            join (inside a repo: that repo's join). Nothing joined at all ->
            refused with a line that says to join, nothing asked or saved.
            off outside a repo with the device join tells the relay first,
            then the whole file goes.
    start   Always passes --device-join <home>/team-relay; with the device
            join there it also passes --joined-list <home>/joined-repos.txt.
    autostart / login-start run   A folder with a join counts: outside a
            repo, or in a repo with no join file of its own, the device join.
  hooks/hooks.json   The SessionStart gate also passes on <home>/team-relay.

  A cloud session (CLAUDE_CODE_REMOTE set) has no device: the device file is
  never read or written there; join and leave stay per repo, as before.

  tests/scripthelp.py: a run with the real $HOME gets an AGENT_CITY_HOME under
  the test's own temp tree (unless the test sets one), so the owner's real
  device join can never reach a test.

Never the real ~/.claude/agent-city, never a real key or relay (FakeRelay on
127.0.0.1, temp AGENT_CITY_HOME and AGENT_CITY_DIR, a free port).

Run: python3 -m unittest tests.test_agent_city_device_join
"""

import json
import os
import pty
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

from relayhelp import FAKE_KEY, FakeRelay, add_worktree, hook_line, make_repo, wait_for  # noqa: E402
from relayhelp import join as join_by_hand  # noqa: E402
from scripthelp import ScriptCase, args_of  # noqa: E402
from test_agent_city_anywhere import free_port, list_paths, read_text, server_pid, stop_server, team_lines, write_text  # noqa: E402
from test_agent_city_add_agent import AddCase, line  # noqa: E402
from test_agent_city_server import ServerCase  # noqa: E402
import agent_city as ac  # noqa: E402
import agent_city_relay as rl  # noqa: E402

DEVICE_NAME = "team-relay"
LIST_NAME = "joined-repos.txt"
TALK = "fake-talk-key-for-tests-0002"
JOINED = "JOINED: this device -> %s (all repos)"
DEVICE_TEAM = "TEAM: joined %s (this device, all repos)"
SETUP = os.path.join(ROOT, "skills", "city", "setup.md")
REQ = os.path.join(ROOT, "requirements", "city.md")


def write_device(path, address, key=FAKE_KEY):
    write_text(path, "address=%s\nkey=%s\n" % (address, key))
    os.chmod(path, 0o600)
    return path


def read_pairs(path):
    with open(path) as fh:
        rows = dict(l.strip().split("=", 1) for l in fh if "=" in l)
    return {k.strip(): v.strip() for k, v in rows.items()}


def lines_of(text, head):
    return [l.strip() for l in text.splitlines() if l.strip().startswith(head)]


# ===================================================================== module

class ModuleCase(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_device_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.relays = []
        self.fake = self.relay()
        self.device = os.path.join(self.base, "cityhome", DEVICE_NAME)
        self.list_path = os.path.join(self.base, "cityhome", LIST_NAME)
        self.shop = make_repo(self.base, "shop")

    def tearDown(self):
        for r in self.relays:
            r.stop()

    def relay(self, key=FAKE_KEY):
        r = FakeRelay(key)
        self.relays.append(r)
        return r

    def need(self, name):
        self.assertTrue(hasattr(rl, name), "agent_city_relay.%s is missing" % name)
        return getattr(rl, name)


class TestEffectiveJoin(ModuleCase):
    def test_nothing_joined_is_none(self):
        eff = self.need("effective_join")
        self.assertIsNone(eff(self.shop, None))
        self.assertIsNone(eff(self.shop, self.device), "a device file that is not there gives nothing")

    def test_the_device_join_covers_a_repo_with_no_file(self):
        write_device(self.device, self.fake.url)
        got = self.need("effective_join")(self.shop, self.device)
        self.assertEqual(got, {"address": self.fake.url, "key": FAKE_KEY, "path": self.device})

    def test_the_repos_own_file_without_a_device_join(self):
        own = join_by_hand(self.shop, self.fake.url)
        got = self.need("effective_join")(self.shop, self.device)
        self.assertEqual(got, {"address": self.fake.url, "key": FAKE_KEY, "path": own})
        self.assertEqual(self.need("effective_join")(self.shop, None)["path"], own)

    def test_a_repo_on_another_relay_wins(self):
        other = self.relay()
        own = join_by_hand(self.shop, other.url, key="other-team-key")
        write_device(self.device, self.fake.url)
        got = self.need("effective_join")(self.shop, self.device)
        self.assertEqual(got, {"address": other.url, "key": "other-team-key", "path": own})

    def test_a_repo_on_the_same_relay_uses_the_device_key(self):
        join_by_hand(self.shop, self.fake.url + "/", key="an-old-team-key")
        write_device(self.device, self.fake.url)
        got = self.need("effective_join")(self.shop, self.device)
        self.assertEqual(got, {"address": self.fake.url, "key": FAKE_KEY, "path": self.device})

    def test_a_broken_device_file_is_no_join(self):
        write_text(self.device, "nothing useful\n")
        self.assertIsNone(self.need("effective_join")(self.shop, self.device))
        own = join_by_hand(self.shop, self.fake.url)
        self.assertEqual(self.need("effective_join")(self.shop, self.device)["path"], own)


class HubCase(ModuleCase):
    def hub(self, **kw):
        opts = dict(relay_sec=0, dev_id="dev-me", label="mac-1", join_ttl=0, timeout=3.0)
        opts.update(kw)
        return rl.RelayHub(**opts)


class TestHubDeviceJoin(HubCase):
    def test_no_device_join_is_as_before(self):
        write_device(self.device, self.fake.url)
        hub = self.hub()
        self.assertFalse(hub.offer(hook_line(self.shop)), "no device_join given: the file is never read")
        hub.tick()
        self.assertEqual(self.fake.requests, [])

    def test_a_repo_with_no_file_sends_to_the_device_relay(self):
        write_device(self.device, self.fake.url)
        hub = self.hub(device_join=self.device)
        self.assertTrue(hub.offer(hook_line(self.shop, sid="s1")))
        hub.tick()
        sent = self.fake.sent_lines()
        self.assertEqual([l["sid"] for l in sent], ["s1"])
        self.assertEqual(sent[0]["rid"], "github.com/acme/shop")
        self.assertEqual(self.fake.requests[0]["auth"], "Bearer " + FAKE_KEY)
        self.assertTrue(hub.joined())
        self.assertEqual(hub.repos_for(self.fake.host), [os.path.realpath(os.path.join(self.shop, ".git"))])

    def test_a_new_repo_needs_no_step(self):
        write_device(self.device, self.fake.url)
        hub = self.hub(device_join=self.device)
        docs = make_repo(self.base, "docs", origin="git@github.com:Acme/Docs.git")
        self.assertTrue(hub.offer(hook_line(docs, sid="d1")))
        hub.tick()
        self.assertEqual([l["rid"] for l in self.fake.sent_lines()], ["github.com/acme/docs"])

    def test_a_worktree_line_uses_the_device_join(self):
        write_device(self.device, self.fake.url)
        wt = add_worktree(self.shop, "feature/device")
        hub = self.hub(device_join=self.device)
        self.assertTrue(hub.offer(hook_line(self.shop, proj=wt)))
        hub.tick()
        self.assertEqual(self.fake.sent_lines()[0]["br"], "feature/device")

    def test_no_shared_origin_stays_local(self):
        write_device(self.device, self.fake.url)
        local = make_repo(self.base, "local", origin=None)
        hub = self.hub(device_join=self.device)
        self.assertFalse(hub.offer(hook_line(local)))
        hub.tick()
        self.assertEqual(self.fake.requests, [])

    def test_a_repo_on_another_relay_keeps_it(self):
        other = self.relay()
        join_by_hand(self.shop, other.url)
        write_device(self.device, self.fake.url)
        hub = self.hub(device_join=self.device)
        self.assertTrue(hub.offer(hook_line(self.shop, sid="s1")))
        hub.tick()
        self.assertEqual([l["sid"] for l in other.sent_lines()], ["s1"])
        self.assertEqual(self.fake.sent_lines(), [])

    def test_a_repo_on_the_same_relay_with_an_old_key_uses_the_device_key(self):
        join_by_hand(self.shop, self.fake.url, key="an-old-team-key")
        write_device(self.device, self.fake.url)
        hub = self.hub(device_join=self.device)
        self.assertTrue(hub.offer(hook_line(self.shop, sid="s1")))
        hub.tick()
        self.assertEqual([l["sid"] for l in self.fake.sent_lines()], ["s1"])
        self.assertEqual({r["auth"] for r in self.fake.requests}, {"Bearer " + FAKE_KEY})

    def test_leaving_the_device_drops_the_team(self):
        write_device(self.device, self.fake.url)
        hub = self.hub(device_join=self.device)
        hub.offer(hook_line(self.shop))
        hub.tick()
        self.assertTrue(hub.joined())
        os.remove(self.device)
        hub.tick()
        self.assertFalse(hub.joined(), "the device left: its team is gone with the next tick")
        before = len(self.fake.requests)
        self.assertFalse(hub.offer(hook_line(self.shop)))
        hub.tick()
        self.assertEqual(len(self.fake.requests), before)

    def test_a_cloud_session_never_uses_the_device_file(self):
        other = self.relay()
        write_device(self.device, self.fake.url)
        hub = self.hub(device_join=self.device, env_join={"address": other.url, "key": FAKE_KEY},
                       send_only=True)
        self.assertTrue(hub.offer(hook_line(self.shop, sid="s1")))
        hub.tick()
        self.assertEqual([l["sid"] for l in other.sent_lines()], ["s1"])
        self.assertEqual(self.fake.requests, [])

    def test_the_joined_list_grows_by_itself(self):
        write_device(self.device, self.fake.url)
        hub = self.hub(device_join=self.device, joined_list=self.list_path)
        docs = make_repo(self.base, "docs", origin="git@github.com:Acme/Docs.git")
        for _ in range(3):
            hub.offer(hook_line(self.shop))
            hub.offer(hook_line(docs))
            hub.tick()
        self.assertEqual(sorted(rl.read_joined_list(self.list_path)),
                         sorted([os.path.realpath(self.shop), os.path.realpath(docs)]))
        text = read_text(self.list_path)
        self.assertNotIn(FAKE_KEY, text)
        self.assertNotIn("key", text)
        self.assertEqual(len(list_paths(self.list_path)), 2, "each repo once")

    def test_the_list_keeps_what_was_there(self):
        write_text(self.list_path, "# my note\n/some/other/repo\n")
        write_device(self.device, self.fake.url)
        hub = self.hub(device_join=self.device, joined_list=self.list_path)
        hub.offer(hook_line(self.shop))
        hub.tick()
        self.assertIn("# my note", read_text(self.list_path))
        self.assertEqual(list_paths(self.list_path), ["/some/other/repo", os.path.realpath(self.shop)])

    def test_no_list_growth_without_the_device_join(self):
        other = self.relay()
        join_by_hand(self.shop, other.url)
        write_device(self.device, self.fake.url)
        hub = self.hub(device_join=self.device, joined_list=self.list_path)
        hub.offer(hook_line(self.shop))
        local = make_repo(self.base, "local", origin=None)
        hub.offer(hook_line(local))
        hub.tick()
        self.assertEqual(list_paths(self.list_path), [],
                         "a repo on its own other-relay file, or one that stays local, is not added")

    def test_a_listed_repo_with_no_file_is_seeded(self):
        write_device(self.device, self.fake.url)
        write_text(self.list_path, "%s\n" % self.shop)
        hub = self.hub(device_join=self.device, joined_list=self.list_path)
        hub.tick()
        self.assertEqual(len(self.fake.sync_bodies()), 1, "a listed repo syncs with no line sent")
        self.assertEqual(hub.repos_for(self.fake.host), [os.path.realpath(os.path.join(self.shop, ".git"))])

    def test_seed_uses_the_device_join(self):
        write_device(self.device, self.fake.url)
        hub = self.hub(device_join=self.device)
        hub.seed(self.shop)
        hub.tick()
        self.assertEqual(len(self.fake.sync_bodies()), 1)
        self.assertTrue(hub.joined())


# ===================================================================== server

class TestServerDeviceJoin(ServerCase):
    def setUp(self):
        super().setUp()
        self.fake = FakeRelay()
        self.addCleanup(self.fake.stop)
        self.repo = make_repo(self.base)
        self.device = write_device(os.path.join(self.base, "cityhome", DEVICE_NAME), self.fake.url)

    def add(self, **fields):
        self.append(json.dumps(hook_line(self.repo, **fields)) + "\n")

    def test_a_line_of_a_repo_with_no_file_reaches_the_relay(self):
        self.start("--idle-sec", "60", "--relay-sec", "0.2", "--join-ttl-sec", "0.2",
                   "--device-join", self.device)
        self.add(sid="s1")
        self.assertTrue(wait_for(lambda: self.fake.sent_lines()), "nothing reached the relay")
        wire = self.fake.sent_lines()[0]
        self.assertEqual((wire["sid"], wire["rid"]), ("s1", "github.com/acme/shop"))
        self.assertEqual(self.fake.requests[0]["auth"], "Bearer " + FAKE_KEY)

    def test_without_the_flag_nothing_leaves(self):
        self.start("--idle-sec", "60", "--relay-sec", "0.2")
        self.add(sid="s1")
        self.assertTrue(wait_for(lambda: self.health()["lines"] == 1))
        time.sleep(1.0)
        self.assertEqual(self.fake.requests, [])


class TestHealthOnAJoinedComputer(AddCase):
    def test_no_repo_is_not_joined(self):
        device = write_device(os.path.join(self.base, "cityhome", DEVICE_NAME), "https://relay.example.test")
        other = self.repo("v4-plus")
        self.feed(line("UserPromptSubmit", "s1", self.shop), line("UserPromptSubmit", "p1", other))
        self.assertEqual(self.state.health().get("not_joined"), ["shop", "v4-plus"], "as before: no device join")
        self.state.device_join = device
        self.assertEqual(self.state.health().get("not_joined"), [], "a joined computer: every repo is in")

    def test_a_broken_device_file_changes_nothing(self):
        device = os.path.join(self.base, "cityhome", DEVICE_NAME)
        write_text(device, "nothing useful\n")
        self.state.device_join = device
        self.feed(line("UserPromptSubmit", "s1", self.shop))
        self.assertEqual(self.state.health().get("not_joined"), ["shop"])


# ====================================================================== shell

class DeviceCase(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.fake = FakeRelay()
        self.addCleanup(self.fake.stop)
        self.city = os.path.join(self.repo.base, "city")
        self.home = os.path.join(self.repo.base, "cityhome")
        self.device = os.path.join(self.home, DEVICE_NAME)
        self.list_path = os.path.join(self.home, LIST_NAME)
        self.marker = os.path.join(self.home, "cloud")
        self.talk_file = os.path.join(self.home, "cloud-talk")
        self.start_file = os.path.join(self.home, "cloud-start")
        self.plain = os.path.join(self.repo.base, "plain")
        os.makedirs(self.plain)
        self.port = free_port()
        self.addCleanup(stop_server, self.city)
        # the project repo: no origin and no .gitignore -- a device join needs neither
        self.open_log = os.path.join(self.repo.base, "open.log")
        for name in ("open", "xdg-open"):
            stub = os.path.join(self.repo.bin, name)
            with open(stub, "w") as fh:
                fh.write("#!/bin/sh\necho \"$@\" >> '%s'\n" % self.open_log)
            os.chmod(stub, 0o755)

    def env(self, extra=None):
        env = {"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.home,
               "AGENT_CITY_PORT": str(self.port), "AGENT_CITY_LANG": ""}
        env.update(extra or {})
        return env

    def city_run(self, *args, cwd=None, stdin=None, extra=None):
        return self.repo.run("agent-city.sh", *args, env=self.env(extra), cwd=cwd or self.plain,
                             stdin=stdin, timeout=30)

    def in_a_terminal(self, *args, key=TALK, cwd=None):
        """agent-city.sh ARGS with a real (pseudo) terminal on stdin; KEY is typed into it."""
        master, slave = pty.openpty()
        try:
            proc = subprocess.Popen([self.repo.script_path("agent-city.sh")] + list(args),
                                    cwd=cwd or self.plain, env=self.repo._env(self.env()), stdin=slave,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.8)
            os.write(master, (key + "\n").encode())
            out, err = proc.communicate(timeout=30)
        finally:
            os.close(master)
            os.close(slave)
        return proc.returncode, out, err

    def join(self, address=None, key=FAKE_KEY, cwd=None, answer=None, extra=None):
        address = self.fake.url if address is None else address
        stdin = "%s\n%s\n" % (address, key)
        if answer is not None:
            stdin = answer + "\n" + stdin
        return self.city_run("join", cwd=cwd, stdin=stdin, extra=extra)

    def joined_repo(self, name, relay=None, key=FAKE_KEY):
        path = make_repo(self.repo.base, name, origin="git@github.com:Acme/%s.git" % name.capitalize())
        join_by_hand(path, (relay or self.fake).url, key=key)
        return path

    def assert_no_key(self, result, key=FAKE_KEY):
        self.assertNotIn(key, result.stdout + result.stderr)

    def assert_no_device(self):
        self.assertFalse(os.path.exists(self.device), "nothing may be saved")

    def pid(self):
        pid = server_pid(self.city)
        if pid is None:
            return None
        try:
            os.kill(pid, 0)
            return pid
        except OSError:
            return None


class TestJoinOnce(DeviceCase):
    def test_from_a_plain_folder(self):
        result = self.join()
        self.assertOk(result)
        self.assertIn(JOINED % self.fake.host, result.stdout)
        self.assertEqual(read_pairs(self.device), {"address": self.fake.url, "key": FAKE_KEY})
        self.assertEqual(stat.S_IMODE(os.stat(self.device).st_mode), 0o600)
        self.assertIn("Team key (hidden)", result.stderr)
        self.assert_no_key(result)
        self.assertEqual(len(self.fake.sync_bodies()), 1, "the relay checked the key first")
        self.assertEqual(self.fake.requests[0]["auth"], "Bearer " + FAKE_KEY)
        self.assertFalse(os.path.exists(os.path.join(self.plain, ".secrets")))

    def test_inside_any_repo_it_is_the_device_join(self):
        """No origin, no .gitignore: a device join needs neither, and no repo file is written."""
        result = self.join(cwd=self.repo.dir)
        self.assertOk(result)
        self.assertIn(JOINED % self.fake.host, result.stdout)
        self.assertTrue(os.path.exists(self.device))
        self.assertFalse(os.path.exists(self.repo.path(".secrets", "agent-city-relay")))

    def test_inside_a_shared_repo_it_goes_on_the_list(self):
        shop = make_repo(self.repo.base, "shop")
        self.assertOk(self.join(cwd=shop))
        self.assertEqual(list_paths(self.list_path), [os.path.realpath(shop)])
        self.assertFalse(os.path.exists(os.path.join(shop, ".secrets", "agent-city-relay")))

    def test_from_a_worktree(self):
        shop = make_repo(self.repo.base, "shop")
        wt = add_worktree(shop, "feature/x")
        self.assertOk(self.join(cwd=wt))
        self.assertTrue(os.path.exists(self.device))
        self.assertEqual(list_paths(self.list_path), [os.path.realpath(shop)])

    def test_refused_key(self):
        result = self.join(key="not-the-team-key")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("refused", result.stdout + result.stderr)
        self.assert_no_key(result, "not-the-team-key")
        self.assert_no_device()

    def test_relay_down(self):
        result = self.join(address="http://127.0.0.1:%d" % free_port())
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot reach", result.stdout + result.stderr)
        self.assert_no_key(result)
        self.assert_no_device()

    def test_bad_address_or_no_key(self):
        for address, key in (("http://relay.example.com", FAKE_KEY), ("", FAKE_KEY), (None, "")):
            with self.subTest(address=address, key=key):
                result = self.join(address=address, key=key)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assert_no_device()
        self.assertEqual(self.fake.requests, [])

    def test_joining_again_replaces_it(self):
        self.assertOk(self.join())
        other = FakeRelay(key="second-team-key")
        self.addCleanup(other.stop)
        result = self.join(address=other.url, key="second-team-key")
        self.assertOk(result)
        self.assertIn(JOINED % other.host, result.stdout)
        self.assertEqual(read_pairs(self.device), {"address": other.url, "key": "second-team-key"})
        self.assert_no_key(result, "second-team-key")

    def test_a_cloud_session_keeps_the_per_repo_join(self):
        shop = make_repo(self.repo.base, "shop")
        result = self.join(cwd=shop, extra={"CLAUDE_CODE_REMOTE": "true"})
        self.assertOk(result)
        self.assertIn("JOINED: github.com/acme/shop -> " + self.fake.host, result.stdout)
        self.assertTrue(os.path.exists(os.path.join(shop, ".secrets", "agent-city-relay")))
        self.assert_no_device()
        outside = self.join(extra={"CLAUDE_CODE_REMOTE": "true"})
        self.assertNotEqual(outside.returncode, 0)
        self.assertIn("repo", (outside.stdout + outside.stderr).lower())
        self.assert_no_device()

    def test_usage_says_once_per_computer(self):
        result = self.city_run("-h")
        self.assertOk(result)
        join_lines = [l for l in result.stdout.splitlines() if re.match(r"\s*\./agent-city\.sh join\b", l)]
        self.assertTrue(join_lines, result.stdout)
        self.assertNotIn("this repo", join_lines[0])
        self.assertRegex(join_lines[0], r"(?i)computer|device")


class TestMoveUp(DeviceCase):
    """A computer that joined repos the old way moves up with no key typed."""

    def setUp(self):
        super().setUp()
        self.shop = self.joined_repo("shop")
        write_text(self.list_path, "%s\n" % self.shop)

    def test_enter_takes_the_relay_of_the_joined_repo(self):
        result = self.city_run("join", stdin="\n")
        self.assertOk(result)
        out = result.stdout + result.stderr
        question = [l for l in out.splitlines() if "[Y/n]" in l]
        self.assertTrue(question, "one question line with [Y/n]")
        self.assertIn(self.fake.host, question[0], "the question names that relay")
        self.assertIn(JOINED % self.fake.host, result.stdout)
        self.assertEqual(read_pairs(self.device), {"address": self.fake.url, "key": FAKE_KEY})
        self.assertEqual(stat.S_IMODE(os.stat(self.device).st_mode), 0o600)
        self.assertNotIn("Team key", result.stderr, "no key is asked")
        self.assert_no_key(result)
        self.assertEqual([r["auth"] for r in self.fake.requests], ["Bearer " + FAKE_KEY],
                         "the relay checked that same key once")

    def test_yes_words(self):
        for word in ("y", "Y", "yes"):
            with self.subTest(word=word):
                if os.path.exists(self.device):
                    os.remove(self.device)
                self.assertOk(self.city_run("join", stdin=word + "\n"))
                self.assertEqual(read_pairs(self.device), {"address": self.fake.url, "key": FAKE_KEY})

    def test_no_asks_as_usual(self):
        other = FakeRelay(key="second-team-key")
        self.addCleanup(other.stop)
        result = self.join(address=other.url, key="second-team-key", answer="n")
        self.assertOk(result)
        self.assertIn("Team key (hidden)", result.stderr)
        self.assertEqual(read_pairs(self.device), {"address": other.url, "key": "second-team-key"})

    def test_a_relay_that_no_longer_takes_the_key_saves_nothing(self):
        self.fake.key = "the-key-was-changed"
        result = self.city_run("join", stdin="\n")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assert_no_device()
        self.assert_no_key(result)

    def test_the_first_listed_repo_with_a_join_file(self):
        other = FakeRelay()
        self.addCleanup(other.stop)
        docs = self.joined_repo("docs", relay=other)
        gone = os.path.join(self.repo.base, "gone")
        write_text(self.list_path, "%s\n%s\n%s\n" % (gone, docs, self.shop))
        self.assertOk(self.city_run("join", stdin="\n"))
        self.assertEqual(read_pairs(self.device)["address"], other.url)

    def test_no_offer_once_the_device_joined(self):
        self.assertOk(self.city_run("join", stdin="\n"))
        result = self.join()
        self.assertOk(result)
        self.assertNotIn("[Y/n]", result.stdout + result.stderr)
        self.assertIn("Team key (hidden)", result.stderr)

    def test_the_old_files_keep_working(self):
        self.assertOk(self.city_run("join", stdin="\n"))
        self.assertTrue(os.path.exists(os.path.join(self.shop, ".secrets", "agent-city-relay")))


class TestLeave(DeviceCase):
    def test_this_computer_leaves(self):
        other = FakeRelay()
        self.addCleanup(other.stop)
        shop = self.joined_repo("shop")
        docs = self.joined_repo("docs", relay=other)
        write_text(self.list_path, "# my note\n%s\n%s\n" % (shop, docs))
        write_device(self.device, self.fake.url)
        write_text(self.talk_file, "%s %s\n" % (self.fake.host, TALK))
        result = self.city_run("leave")
        self.assertOk(result)
        self.assertIn("LEFT", result.stdout)
        self.assert_no_device()
        for repo in (shop, docs):
            self.assertFalse(os.path.exists(os.path.join(repo, ".secrets", "agent-city-relay")),
                             "every repo stops sending")
        self.assertEqual(list_paths(self.list_path), [])
        self.assertEqual(read_text(self.talk_file), "%s %s\n" % (self.fake.host, TALK), "talk keeps its file")
        self.assert_no_key(result)
        again = self.city_run("leave")
        self.assertOk(again)
        self.assertIn("LEFT", again.stdout)

    def test_from_inside_a_repo_its_own_file_goes_too(self):
        shop = self.joined_repo("shop")
        write_device(self.device, self.fake.url)
        self.assertOk(self.city_run("leave", cwd=shop))
        self.assert_no_device()
        self.assertFalse(os.path.exists(os.path.join(shop, ".secrets", "agent-city-relay")))

    def test_status_after_leave(self):
        self.assertOk(self.join())
        self.assertOk(self.city_run("leave"))
        self.assertEqual(team_lines(self.city_run("status").stdout), ["TEAM: not joined"])

    def test_a_cloud_session_leaves_only_its_repo(self):
        shop = self.joined_repo("shop")
        write_device(self.device, self.fake.url)
        self.assertOk(self.city_run("leave", cwd=shop, extra={"CLAUDE_CODE_REMOTE": "true"}))
        self.assertFalse(os.path.exists(os.path.join(shop, ".secrets", "agent-city-relay")))
        self.assertTrue(os.path.exists(self.device), "a cloud session never touches the device join")


class TestStatus(DeviceCase):
    def test_plainly_from_any_folder(self):
        self.assertOk(self.join())
        unjoined = make_repo(self.repo.base, "unjoined")
        for cwd in (self.plain, unjoined, self.repo.dir):
            with self.subTest(cwd=cwd):
                result = self.city_run("status", cwd=cwd)
                self.assertOk(result)
                self.assertEqual(team_lines(result.stdout), [DEVICE_TEAM % self.fake.host])
                self.assert_no_key(result)

    def test_a_repo_on_another_relay_keeps_its_line(self):
        other = FakeRelay()
        self.addCleanup(other.stop)
        docs = self.joined_repo("docs", relay=other)
        same = self.joined_repo("same")
        write_text(self.list_path, "%s\n%s\n" % (same, docs))
        write_device(self.device, self.fake.url)
        self.assertEqual(team_lines(self.city_run("status").stdout),
                         [DEVICE_TEAM % self.fake.host, "TEAM: joined %s (%s)" % (other.host, docs)])
        self.assertEqual(team_lines(self.city_run("status", cwd=docs).stdout), ["TEAM: joined " + other.host])
        self.assertEqual(team_lines(self.city_run("status", cwd=same).stdout), [DEVICE_TEAM % self.fake.host])

    def test_the_cloud_line_from_any_folder(self):
        self.assertOk(self.join())
        rl.set_cloud(self.marker, self.fake.host, True)
        unjoined = make_repo(self.repo.base, "unjoined")
        for cwd in (self.plain, unjoined):
            with self.subTest(cwd=cwd):
                self.assertEqual(lines_of(self.city_run("status", cwd=cwd).stdout, "CLOUD:"),
                                 ["CLOUD: on " + self.fake.host])

    def test_never_joined_is_as_before(self):
        result = self.city_run("status")
        self.assertEqual(team_lines(result.stdout), ["TEAM: not joined"])
        self.assertEqual(lines_of(result.stdout, "CLOUD"), [])

    def test_a_cloud_session_never_reads_the_device_join(self):
        write_device(self.device, self.fake.url)
        unjoined = make_repo(self.repo.base, "unjoined")
        result = self.city_run("status", cwd=unjoined, extra={"CLAUDE_CODE_REMOTE": "true"})
        self.assertEqual(team_lines(result.stdout), ["TEAM: not joined"])


class TestTalkAndStartFromAnyFolder(DeviceCase):
    def setUp(self):
        super().setUp()
        self.fake.city = True
        self.fake.talk_key = TALK
        self.assertOk(self.join())

    def test_talk_on_then_start_on_from_a_plain_folder(self):
        code, out, err = self.in_a_terminal("cloud-talk", "on")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(lines_of(out, "CLOUD TALK:"), ["CLOUD TALK: on " + self.fake.host])
        self.assertEqual(rl.read_talk(self.talk_file), {self.fake.host: TALK})
        self.assertNotIn(TALK, out + err)
        code, out, err = self.in_a_terminal("cloud-start", "on")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(lines_of(out, "CLOUD START:"), ["CLOUD START: on " + self.fake.host])
        self.assertEqual(rl.read_start(self.start_file), [self.fake.host])
        status = self.city_run("status")
        self.assertEqual(lines_of(status.stdout, "CLOUD TALK:"), ["CLOUD TALK: on " + self.fake.host])
        self.assertEqual(lines_of(status.stdout, "CLOUD START:"), ["CLOUD START: on " + self.fake.host])

    def test_talk_on_inside_a_repo_with_no_file(self):
        unjoined = make_repo(self.repo.base, "unjoined")
        code, out, err = self.in_a_terminal("cloud-talk", "on", cwd=unjoined)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(rl.read_talk(self.talk_file), {self.fake.host: TALK})

    def test_off_from_a_plain_folder_tells_the_relay(self):
        self.assertEqual(self.in_a_terminal("cloud-talk", "on")[0], 0)
        self.assertEqual(self.in_a_terminal("cloud-start", "on")[0], 0)
        result = self.city_run("cloud-start", "off")
        self.assertOk(result)
        self.assertEqual(lines_of(result.stdout, "CLOUD START:"), ["CLOUD START: off"])
        self.assertEqual(len(self.fake.start_offs), 1, "the relay was told, waiting orders are never opened")
        result = self.city_run("cloud-talk", "off")
        self.assertOk(result)
        self.assertEqual(lines_of(result.stdout, "CLOUD TALK:"), ["CLOUD TALK: off"])
        self.assertEqual(len(self.fake.offs), 1, "the relay was told, so the chat leaves Cloudflare")
        self.assertFalse(os.path.exists(self.talk_file))
        self.assertFalse(os.path.exists(self.start_file))


class TestTalkWithNoJoin(DeviceCase):
    def test_on_is_refused_with_a_word_to_join(self):
        self.fake.talk_key = TALK
        for verb in ("cloud-talk", "cloud-start"):
            with self.subTest(verb=verb):
                code, out, err = self.in_a_terminal(verb, "on")
                self.assertEqual(code, 1, out + err)
                self.assertRegex(out + err, r"(?i)join")
                self.assertNotIn("Talk key", err, "nothing is asked")
        self.assertFalse(os.path.exists(self.talk_file))
        self.assertFalse(os.path.exists(self.start_file))
        self.assertEqual(self.fake.requests, [])


class TestStartAndAutostart(DeviceCase):
    def server(self):
        pid = wait_for(self.pid, timeout=10)
        self.assertTrue(pid, "no city server came up")
        return args_of(pid)

    def test_start_always_names_the_device_join(self):
        self.assertOk(self.city_run("start", cwd=self.repo.dir))
        args = self.server()
        self.assertIn("--device-join %s" % self.device, args)
        self.assertNotIn("--joined-list", args, "a computer that never joined: as before")

    def test_start_on_a_joined_computer_passes_the_list(self):
        self.assertOk(self.join())
        self.assertOk(self.city_run("start", cwd=self.repo.dir))
        args = self.server()
        self.assertIn("--device-join %s" % self.device, args)
        self.assertIn("--joined-list %s" % self.list_path, args)

    def test_a_cloud_session_start_never_names_it(self):
        write_device(self.device, self.fake.url)
        self.assertOk(self.city_run("start", cwd=self.repo.dir, extra={"CLAUDE_CODE_REMOTE": "true"}))
        self.assertNotIn("--device-join", self.server())

    def autostart(self, cwd):
        result = self.city_run("autostart", cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_autostart_outside_a_repo(self):
        self.assertOk(self.join())
        rl.set_cloud(self.marker, self.fake.host, True)
        self.autostart(self.plain)
        args = self.server()
        self.assertIn("--device-join %s" % self.device, args)
        self.assertIn("--joined-list %s" % self.list_path, args)
        self.assertFalse(os.path.exists(self.open_log), "no browser is opened")

    def test_autostart_in_a_repo_with_no_file(self):
        self.assertOk(self.join())
        rl.set_cloud(self.marker, self.fake.host, True)
        self.autostart(make_repo(self.repo.base, "unjoined"))
        self.server()

    def test_autostart_probes_the_device_relay(self):
        self.assertOk(self.join())
        if os.path.exists(self.marker):
            os.remove(self.marker)
        self.fake.city = True
        self.autostart(self.plain)
        self.server()
        self.assertEqual(rl.read_cloud(self.marker), [self.fake.host])

    def test_never_joined_never_starts(self):
        rl.set_cloud(self.marker, self.fake.host, True)
        self.autostart(self.plain)
        time.sleep(1.0)
        self.assertIsNone(self.pid())
        self.assertEqual(self.fake.requests, [])

    def test_login_run_with_only_the_device_join(self):
        self.assertOk(self.join())
        rl.set_cloud(self.marker, self.fake.host, True)
        result = self.city_run("login-start", "run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((result.stdout + result.stderr).strip(), "")
        self.assertTrue(self.pid(), "the login item brings the city up on a joined computer")
        self.assertIn("--device-join %s" % self.device, self.server())


class TestHookGate(unittest.TestCase):
    def test_the_device_join_passes_the_gate(self):
        from test_agent_city_cloud_autostart import TestHookLine as hook_case
        case = hook_case("test_shape")
        try:
            got = case.run_hook({DEVICE_NAME: "address=https://relay.example.test\nkey=<key>\n"})
        finally:
            case.doCleanups()
        self.assertEqual(got, ["autostart"])


class TestTestsNeverSeeTheRealHome(ScriptCase):
    script = "agent-city.sh"

    def test_a_city_home_of_its_own(self):
        env = self.repo._env(None)
        self.assertTrue(env.get("AGENT_CITY_HOME", "").startswith(self.repo.base),
                        "a run with the real HOME must get a temp AGENT_CITY_HOME")
        self.assertEqual(self.repo._env({"AGENT_CITY_HOME": "/x"})["AGENT_CITY_HOME"], "/x",
                         "a test that sets its own keeps it")


# ======================================================================= docs

class TestSetupSteps(unittest.TestCase):
    def setUp(self):
        with open(SETUP) as fh:
            self.text = fh.read()
        self.sections = re.findall(r"(?ms)^## (\d+)\. ([^\n]+)\n(.*?)(?=^## |\Z)", self.text)

    def section(self, number):
        hits = [(title, body) for n, title, body in self.sections if int(n) == number]
        self.assertTrue(hits, "no section %d" % number)
        return hits[0]

    def test_join_is_one_step_per_computer(self):
        title, body = self.section(6)
        self.assertEqual(title.strip(), "Join this computer")
        self.assertRegex(body, r"(?i)once")
        self.assertRegex(body, r"(?i)any folder")
        self.assertIn("JOINED: this device", body)
        self.assertIn("[Y/n]", body, "the move-up question, so nobody types the key again")
        self.assertNotIn(".secrets", body)
        self.assertNotRegex(body, r"(?i)inside the repo")

    def test_talk_and_start_from_any_folder(self):
        for n in (16, 17, 18, 19):
            with self.subTest(section=n):
                _, body = self.section(n)
                self.assertNotRegex(body, r"(?i)inside (a|the) repo")
        for n in (16, 18):
            with self.subTest(section=n):
                _, body = self.section(n)
                self.assertRegex(body, r"(?i)any folder")
                self.assertRegex(body, r"(?i)once")

    def test_leave_is_once_per_computer(self):
        _, body = self.section(10)
        self.assertIn("leave", body)
        self.assertNotRegex(body, r"(?i)every joined repo")


class TestRequirementLines(unittest.TestCase):
    def setUp(self):
        with open(REQ) as fh:
            self.text = fh.read()
        self.joining = self.text[self.text.index("## Joining"):self.text.index("## Cloud page")]

    def test_joining_is_per_computer(self):
        for word in ("Joining is per computer", "team-relay", "(this device, all repos)", "[Y/n]",
                     "CLAUDE_CODE_REMOTE", "hide", "wins when it names a different relay"):
            self.assertIn(word, self.joining, word)
        self.assertNotIn("- Joining is per repo:", self.text)

    def test_talk_and_start_from_any_folder(self):
        talk = self.text[self.text.index("### Talk"):self.text.index("### Start")]
        start = self.text[self.text.index("### Start"):self.text.index("### Login start")]
        for body in (talk, start):
            switch = [l for l in body.splitlines() if l.startswith("- The switch")]
            self.assertEqual(len(switch), 1)
            self.assertIn("from any folder", switch[0])
            self.assertNotIn("in a joined repo:", switch[0])


if __name__ == "__main__":
    unittest.main()
