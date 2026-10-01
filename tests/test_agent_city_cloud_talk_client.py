"""Failing tests, cloud-city-2 slice S3: the machine's side of the sync and
the switch (requirements/city.md, "Cloud page", step 2; approved design in
agent_state.txt).

bin/agent_city_relay.py
  The talk file: <AGENT_CITY_HOME>/cloud-talk, one line "<relay host> <talk
  key>" per relay this machine takes messages from. Mode 0600. It is a secret:
  never printed, never sent anywhere but as the X-City-Talk header to that host.
      read_talk(path) -> {host: key}. Missing or broken file -> {}.
      set_talk(path, host, key) -> writes HOST with KEY (key None = remove
          HOST), the whole file at once (tmp + mv), mode 0600; the file is
          removed when the last host goes. Never raises.
      TALK_SOON_SEC = 1.0
  sync(address, key, dev, after, lines, timeout=10.0, view=None, talk=None, talk_key=None)
      talk_key given -> the header "X-City-Talk: <talk_key>" and the body key
      "talk" (TALK, or {} when TALK is None). No talk_key -> neither (the
      request is byte for byte the one of before). The ok data gains "talk":
      the reply's "talk" when it is a dict, else None.
  RelayHub(..., talk_file=None)
      Before every sync of a team the hub reads the talk file (so on / off
      works with the next sync, no restart). The team's host has a key and
      the hub has a view_source with talk_take:
          talk = view_source.talk_take(host, rids, now)      a dict, or None
          the sync carries talk_key and talk
          view_source.talk_sent(host, <the reply's talk dict, or None when the
              relay was down or refused the team key>, now)
          view_source.talk_soon(host) is True -> the team's NEXT sync is due
              TALK_SOON_SEC after this one, not relay_sec (an answer for a
              cloud message must not wait 5 s). Only after a sync the relay
              ANSWERED: a relay that is down is asked again after relay_sec,
              never every second.
      No key for that host, no talk file, or no view_source: the sync of
      before, and talk_take is never called.
      The view (take / sent) and the lines are untouched by all of this.
  CLI   python3 agent_city_relay.py talk --secret <join file> --talk-file <path> on | off | status
      prints ONE line. The talk key is the first line of stdin (on only):
      never argv, never printed.
        status  "on <host>" | "off <host>" (from the file, no network), exit 0;
                no join file -> "none", exit 0
        on      one sync (no lines) with the key as X-City-Talk:
                  the relay says talk on     -> the file gets the host, "on <host>", exit 0
                  the relay says refused     -> "refused <host>", exit 3, nothing saved
                  the relay says off / says nothing about talk -> "no-talk <host>", exit 4, nothing saved
                  the relay is down or refuses the team key    -> "down <host>", exit 5, nothing saved
                  no key on stdin            -> "no-key", exit 2;  no join file -> "none", exit 1
        off     when the file has the host: one sync with talk {"off": true}
                (whatever it answers, also when it is down), the host leaves
                the file. "off <host>", exit 0. No join file -> "none", exit 1.

bin/agent-city.sh
  cloud-talk on    for the owner, in his own terminal, inside a joined repo.
      stdin is not a terminal -> exit 2, "CLOUD TALK: run this yourself in
      your own terminal ...", nothing is asked, sent or saved (an agent can
      never turn it on). Outside a repo, or the repo has not joined -> exit 1
      with a line that says so. Else it asks "Talk key (hidden): " with echo
      off, hands the key to the CLI above on stdin, and prints
          CLOUD TALK: on <host>                                              exit 0
          CLOUD TALK: the relay did not take this key; nothing was saved     exit 1
          CLOUD TALK: the relay has no TALK_KEY (or its cloud page is off); nothing was saved   exit 1
          CLOUD TALK: cannot reach the relay; nothing was saved              exit 1
  cloud-talk off   needs no terminal. "CLOUD TALK: off", exit 0. It must
      always work (it is the way to stop): outside a repo, or in a repo that
      has not joined, it removes the whole talk file (every relay host) with
      no request to anybody; that machine's copy on Cloudflare then ages out
      (inside the joined repo it is deleted at once, as above).
  status           in a joined repo, after the CLOUD line: "CLOUD TALK: on
      <host>" or "CLOUD TALK: off". Not joined: no such line. It never talks
      to the relay. Outside a repo (like the CLOUD lines there): one "CLOUD
      TALK: on <host>" per joined relay host the talk file names (each host
      once), else one "CLOUD TALK: off" when a repo is joined.

Every test uses a fake relay on 127.0.0.1 and temp folders. Never a real key.

Run: python3 -m unittest tests.test_agent_city_cloud_talk_client
"""

import os
import pty
import stat
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

from relayhelp import FAKE_KEY, hook_line, join  # noqa: E402
from test_agent_city_cloud_upload import ClientCase  # noqa: E402
from test_agent_city_cloud_autostart import CloudCase  # noqa: E402
import agent_city_relay as rl  # noqa: E402

TALK = "fake-talk-key-for-tests-0002"
MODULE = os.path.join(BIN, "agent_city_relay.py")


def need(case, name):
    case.assertTrue(hasattr(rl, name), "agent_city_relay.%s is missing" % name)
    return getattr(rl, name)


def talk_lines(text):
    return [l.strip() for l in text.splitlines() if l.strip().startswith("CLOUD TALK:")]


class TalkCase(ClientCase):
    def setUp(self):
        super().setUp()
        self.fake.talk_key = TALK
        self.talk_file = os.path.join(self.base, "cityhome", "cloud-talk")


class TestTalkFile(TalkCase):
    def test_set_and_read(self):
        read, put = need(self, "read_talk"), need(self, "set_talk")
        self.assertEqual(read(self.talk_file), {})
        put(self.talk_file, "b.example", "key-b")
        put(self.talk_file, "a.example:8787", "key-a")
        put(self.talk_file, "a.example:8787", "key-a2")
        self.assertEqual(read(self.talk_file), {"a.example:8787": "key-a2", "b.example": "key-b"})
        self.assertEqual(stat.S_IMODE(os.stat(self.talk_file).st_mode), 0o600, "the file holds a secret")
        put(self.talk_file, "b.example", None)
        self.assertEqual(read(self.talk_file), {"a.example:8787": "key-a2"})
        put(self.talk_file, "a.example:8787", None)
        self.assertFalse(os.path.exists(self.talk_file), "no host left: no file")
        put(self.talk_file, "zz.example", None)
        self.assertFalse(os.path.exists(self.talk_file))

    def test_broken_file_reads_empty(self):
        os.makedirs(os.path.dirname(self.talk_file))
        with open(self.talk_file, "wb") as fh:
            fh.write(b"\xff\xfe\x00")
        self.assertEqual(need(self, "read_talk")(self.talk_file), {})
        with open(self.talk_file, "w") as fh:
            fh.write("# a comment\nonlyhost\n\nhost.example key one two\nok.example thekey\n")
        self.assertEqual(rl.read_talk(self.talk_file), {"ok.example": "thekey"})


class TestSync(TalkCase):
    def test_the_key_is_a_header_and_talk_rides_in_the_body(self):
        talk = {"acks": [{"cid": "c1", "state": "delivered"}]}
        self.fake.say("c9", "s:tm1", "hello")
        state, data = rl.sync(self.fake.url, FAKE_KEY, "dev-me", 0, [], talk=talk, talk_key=TALK)
        self.assertEqual(state, "ok")
        self.assertEqual(self.fake.talk_headers(), [TALK])
        body = self.fake.sync_bodies()[0]
        self.assertEqual(body["talk"], talk)
        self.assertNotIn(TALK, repr(body), "the key is never in the body")
        self.assertEqual(data["talk"], {"state": "on", "msgs": [{"cid": "c9", "to": "s:tm1", "text": "hello", "age": 0}]})

    def test_a_key_without_talk_sends_an_empty_talk(self):
        state, data = rl.sync(self.fake.url, FAKE_KEY, "dev-me", 0, [], talk_key=TALK)
        self.assertEqual(self.fake.sync_bodies()[0]["talk"], {})
        self.assertEqual(data["talk"], {"state": "on", "msgs": []})

    def test_no_key_is_the_sync_of_before(self):
        state, data = rl.sync(self.fake.url, FAKE_KEY, "dev-me", 0, [], talk={"acks": []})
        self.assertEqual(set(self.fake.sync_bodies()[0]), {"dev", "after", "lines"})
        self.assertEqual(self.fake.talk_headers(), [None])
        self.assertIsNone(data["talk"])

    def test_refused_and_off_come_back_as_they_are(self):
        state, data = rl.sync(self.fake.url, FAKE_KEY, "dev-me", 0, [], talk_key="wrong")
        self.assertEqual((state, data["talk"]), ("ok", {"state": "refused"}))
        self.fake.talk_key = None
        state, data = rl.sync(self.fake.url, FAKE_KEY, "dev-me", 0, [], talk_key=TALK)
        self.assertEqual((state, data["talk"]), ("ok", {"state": "off"}))


class Source:
    def __init__(self):
        self.takes, self.sents, self.talk_takes, self.talk_sents = [], [], [], []
        self.next = None
        self.next_talk = None
        self.soon = False

    def take(self, host, rids, now):
        self.takes.append((host, list(rids)))
        return self.next

    def sent(self, host, data, now):
        self.sents.append((host, data))

    def talk_take(self, host, rids, now):
        self.talk_takes.append((host, list(rids)))
        return self.next_talk

    def talk_sent(self, host, talk, now):
        self.talk_sents.append((host, talk))

    def talk_soon(self, host):
        return self.soon


class ViewOnlySource:
    """A source of step 1: no talk methods at all."""

    def take(self, host, rids, now):
        return None

    def sent(self, host, data, now):
        pass


class TestHub(TalkCase):
    def setUp(self):
        super().setUp()
        join(self.repo, self.fake.url)
        self.src = Source()

    def hub_on(self, **kw):
        need(self, "set_talk")(self.talk_file, self.fake.host, TALK)
        hub = self.hub(view_source=self.src, talk_file=self.talk_file, **kw)
        hub.offer(hook_line(self.repo))
        return hub

    def test_the_source_is_asked_and_told(self):
        self.src.next_talk = {"chat": [{"k": "k1", "to": "s:tm1", "kind": "reply", "text": "hi", "at": 1.0}]}
        self.fake.say("c1", "s:tm1", "go on")
        hub = self.hub_on()
        hub.tick()
        self.assertEqual(self.src.talk_takes, [(self.fake.host, ["github.com/acme/shop"])])
        body = self.fake.sync_bodies()[0]
        self.assertEqual(body["talk"], self.src.next_talk)
        self.assertEqual(len(body["lines"]), 1, "the line and the talk share one request")
        self.assertEqual(len(self.fake.requests), 1)
        self.assertEqual(self.src.talk_sents, [(self.fake.host, {"state": "on", "msgs": [
            {"cid": "c1", "to": "s:tm1", "text": "go on", "age": 0}]})])
        self.assertEqual(len(self.src.sents), 1, "the view source hears of the sync as before")

    def test_no_talk_file_is_today(self):
        hub = self.hub(view_source=self.src, talk_file=self.talk_file)
        hub.offer(hook_line(self.repo))
        hub.tick()
        self.assertEqual(set(self.fake.sync_bodies()[0]), {"dev", "after", "lines"})
        self.assertEqual(self.fake.talk_headers(), [None])
        self.assertEqual((self.src.talk_takes, self.src.talk_sents), ([], []))

    def test_a_key_for_another_relay_is_never_sent_here(self):
        need(self, "set_talk")(self.talk_file, "other.example", TALK)
        hub = self.hub(view_source=self.src, talk_file=self.talk_file)
        hub.offer(hook_line(self.repo))
        hub.tick()
        self.assertEqual(self.fake.talk_headers(), [None])
        self.assertEqual(self.src.talk_takes, [])

    def test_on_and_off_work_with_the_next_sync(self):
        hub = self.hub(view_source=self.src, talk_file=self.talk_file)
        hub.offer(hook_line(self.repo))
        hub.tick()
        rl.set_talk(self.talk_file, self.fake.host, TALK)
        hub.tick()
        rl.set_talk(self.talk_file, self.fake.host, None)
        hub.tick()
        self.assertEqual(self.fake.talk_headers(), [None, TALK, None])
        self.assertEqual(len(self.src.talk_takes), 1)

    def test_down_or_refused_is_told_as_none(self):
        hub = self.hub_on()
        self.fake.mode = "error"
        hub.tick()
        self.fake.mode = "refuse"
        hub.tick()
        self.assertEqual([t for _, t in self.src.talk_sents], [None, None])

    def test_a_wrong_talk_key_is_told_as_refused(self):
        hub = self.hub_on()
        self.fake.talk_key = "another-key"
        hub.tick()
        self.assertEqual(self.src.talk_sents, [(self.fake.host, {"state": "refused"})])
        self.assertEqual(len(self.fake.sent_lines()), 1, "the lines still went: only talk is refused")

    def test_a_source_of_step_1_still_works(self):
        rl.set_talk(self.talk_file, self.fake.host, TALK) if hasattr(rl, "set_talk") else self.fail("set_talk is missing")
        hub = self.hub(view_source=ViewOnlySource(), talk_file=self.talk_file)
        hub.offer(hook_line(self.repo))
        hub.tick()
        self.assertEqual(self.fake.talk_headers(), [None], "no talk source: no talk")
        self.assertEqual(len(self.fake.sent_lines()), 1)

    def test_an_error_in_the_source_never_stops_the_lines(self):
        def boom(host, rids, now):
            raise RuntimeError("boom")
        self.src.talk_take = boom
        hub = self.hub_on()
        hub.tick()
        self.assertEqual(len(self.fake.sent_lines()), 1)

    def test_a_relay_that_is_down_is_not_asked_every_second(self):
        self.src.soon = True
        hub = self.hub_on(relay_sec=30)
        self.fake.mode = "error"
        hub.tick()
        before = len(self.fake.requests)
        time.sleep(1.3)
        hub.tick()
        self.assertEqual(len(self.fake.requests), before, "down: the next try comes after relay_sec, not after 1 s")

    def test_soon_means_the_next_sync_comes_in_a_second(self):
        self.assertEqual(need(self, "TALK_SOON_SEC"), 1.0)
        hub = self.hub_on(relay_sec=30)
        hub.tick()
        hub.tick()
        self.assertEqual(len(self.fake.requests), 1, "not due: relay_sec is 30")
        self.src.soon = True
        hub2 = self.hub_on(relay_sec=30)
        before = len(self.fake.requests)
        hub2.tick()
        self.assertEqual(len(self.fake.requests), before + 1)
        time.sleep(0.4)
        hub2.tick()
        self.assertEqual(len(self.fake.requests), before + 1, "not before a second has passed")
        time.sleep(0.8)
        hub2.tick()
        self.assertEqual(len(self.fake.requests), before + 2, "an answer for a cloud message goes up after 1 s")
        self.src.soon = False
        time.sleep(1.2)
        hub2.tick()
        hub2.tick()
        self.assertEqual(len(self.fake.requests), before + 3, "that sync was a soon one too; after it relay_sec again")
        time.sleep(1.2)
        hub2.tick()
        self.assertEqual(len(self.fake.requests), before + 3)


class TestCli(TalkCase):
    def setUp(self):
        super().setUp()
        self.secret = join(self.repo, self.fake.url)

    def cli(self, verb, stdin="", secret=None):
        return subprocess.run([sys.executable, MODULE, "talk", "--secret", secret or self.secret,
                               "--talk-file", self.talk_file, verb],
                              input=stdin, capture_output=True, text=True, timeout=30)

    def saved(self):
        return rl.read_talk(self.talk_file) if hasattr(rl, "read_talk") else None

    def test_on_with_the_right_key(self):
        p = self.cli("on", TALK + "\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "on " + self.fake.host), p.stderr)
        self.assertEqual(self.saved(), {self.fake.host: TALK})
        self.assertEqual(stat.S_IMODE(os.stat(self.talk_file).st_mode), 0o600)
        self.assertNotIn(TALK, p.stdout + p.stderr)
        self.assertEqual(self.fake.talk_headers(), [TALK], "one sync, with the key as a header")
        self.assertEqual(self.fake.sync_bodies()[0]["lines"], [])

    def test_on_with_a_wrong_key_saves_nothing(self):
        p = self.cli("on", "not-the-key\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (3, "refused " + self.fake.host), p.stderr)
        self.assertFalse(os.path.exists(self.talk_file))
        self.assertNotIn("not-the-key", p.stdout + p.stderr)

    def test_on_when_the_relay_has_no_talk(self):
        self.fake.talk_key = None
        p = self.cli("on", TALK + "\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (4, "no-talk " + self.fake.host), p.stderr)
        self.assertFalse(os.path.exists(self.talk_file))

    def test_on_when_the_relay_is_down(self):
        self.fake.mode = "error"
        p = self.cli("on", TALK + "\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (5, "down " + self.fake.host), p.stderr)
        self.assertFalse(os.path.exists(self.talk_file))

    def test_on_without_a_key_or_a_join(self):
        p = self.cli("on", "\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (2, "no-key"))
        p = self.cli("on", TALK + "\n", secret=os.path.join(self.base, "nope"))
        self.assertEqual((p.returncode, p.stdout.strip()), (1, "none"))
        self.assertEqual(self.fake.requests, [])

    def test_status_never_calls_the_relay(self):
        p = self.cli("status")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "off " + self.fake.host))
        need(self, "set_talk")(self.talk_file, self.fake.host, TALK)
        p = self.cli("status")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "on " + self.fake.host))
        self.assertNotIn(TALK, p.stdout + p.stderr)
        p = self.cli("status", secret=os.path.join(self.base, "nope"))
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "none"))
        self.assertEqual(self.fake.requests, [])

    def test_off_tells_the_relay_and_forgets_the_key(self):
        need(self, "set_talk")(self.talk_file, self.fake.host, TALK)
        rl.set_talk(self.talk_file, "other.example", "other-key")
        p = self.cli("off")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "off " + self.fake.host), p.stderr)
        self.assertEqual(self.saved(), {"other.example": "other-key"})
        self.assertEqual(self.fake.talk_headers(), [TALK])
        self.assertEqual(self.fake.sync_bodies()[0]["talk"], {"off": True})
        self.assertEqual(len(self.fake.offs), 1)

    def test_off_with_the_relay_down_still_turns_it_off_here(self):
        need(self, "set_talk")(self.talk_file, self.fake.host, TALK)
        self.fake.mode = "error"
        p = self.cli("off")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "off " + self.fake.host), p.stderr)
        self.assertEqual(self.saved(), {})

    def test_off_when_it_was_never_on_sends_nothing(self):
        p = self.cli("off")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "off " + self.fake.host))
        self.assertEqual(self.fake.requests, [])


class TestCommand(CloudCase):
    """bin/agent-city.sh cloud-talk on | off, and the status line."""

    def setUp(self):
        super().setUp()
        self.fake.city = True
        self.fake.talk_key = TALK
        self.talk_file = os.path.join(self.home, "cloud-talk")

    def on_in_a_terminal(self, key=TALK, cwd=None):
        """`cloud-talk on` with a real (pseudo) terminal on stdin; KEY is typed into it."""
        env = self.repo._env({"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.home,
                              "AGENT_CITY_PORT": str(self.port)})
        master, slave = pty.openpty()
        try:
            proc = subprocess.Popen([self.repo.script_path("agent-city.sh"), "cloud-talk", "on"],
                                    cwd=cwd or self.repo.cwd, env=env, stdin=slave,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.8)
            os.write(master, (key + "\n").encode())
            out, err = proc.communicate(timeout=30)
        finally:
            os.close(master)
            os.close(slave)
        return proc.returncode, out, err

    def test_an_agent_cannot_turn_it_on(self):
        self.assertOk(self.join())
        before = len(self.fake.requests)
        result = self.city_run("cloud-talk", "on", stdin=TALK + "\n")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("CLOUD TALK: run this yourself in your own terminal", result.stdout + result.stderr)
        self.assertFalse(os.path.exists(self.talk_file), "nothing may be saved without a terminal")
        self.assertEqual(len(self.fake.requests), before, "nothing may be sent without a terminal")

    def test_the_owner_turns_it_on_in_his_terminal(self):
        self.assertOk(self.join())
        code, out, err = self.on_in_a_terminal()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(talk_lines(out), ["CLOUD TALK: on " + self.fake.host])
        self.assertIn("Talk key (hidden)", err)
        self.assertNotIn(TALK, out + err, "the key is never shown")
        self.assertEqual(rl.read_talk(self.talk_file), {self.fake.host: TALK})
        self.assertEqual(stat.S_IMODE(os.stat(self.talk_file).st_mode), 0o600)

    def test_a_wrong_key_saves_nothing(self):
        self.assertOk(self.join())
        code, out, err = self.on_in_a_terminal(key="not-the-key")
        self.assertEqual(code, 1, out + err)
        self.assertIn("CLOUD TALK: the relay did not take this key; nothing was saved", out + err)
        self.assertFalse(os.path.exists(self.talk_file))

    def test_a_relay_without_talk_says_so(self):
        self.assertOk(self.join())
        self.fake.talk_key = None
        code, out, err = self.on_in_a_terminal()
        self.assertEqual(code, 1, out + err)
        self.assertIn("CLOUD TALK: the relay has no TALK_KEY", out + err)
        self.assertFalse(os.path.exists(self.talk_file))

    def test_not_joined_is_refused(self):
        code, out, err = self.on_in_a_terminal()
        self.assertEqual(code, 1, out + err)
        self.assertIn("CLOUD TALK:", out + err)
        self.assertRegex(out + err, r"(?i)join")
        self.assertFalse(os.path.exists(self.talk_file))

    def test_off_is_one_command_and_needs_no_terminal(self):
        self.assertOk(self.join())
        self.assertEqual(self.on_in_a_terminal()[0], 0)
        result = self.city_run("cloud-talk", "off")
        self.assertOk(result)
        self.assertEqual(talk_lines(result.stdout), ["CLOUD TALK: off"])
        self.assertEqual(rl.read_talk(self.talk_file), {})
        self.assertEqual(len(self.fake.offs), 1, "the relay was told, so the machine's chat leaves Cloudflare")
        again = self.city_run("cloud-talk", "off")
        self.assertOk(again)
        self.assertEqual(talk_lines(again.stdout), ["CLOUD TALK: off"])

    def test_off_always_works(self):
        import tempfile
        self.assertOk(self.join())
        outside = tempfile.mkdtemp(prefix="city_out_", dir=self.repo.base)
        for cwd in (outside, None):
            rl.set_talk(self.talk_file, self.fake.host, TALK) if hasattr(rl, "set_talk") else self.fail("set_talk is missing")
            rl.set_talk(self.talk_file, "other.example", "other-key")
            if cwd is None:
                os.remove(self.repo.path(".secrets", "agent-city-relay"))   # a repo that has not joined (any more)
            before = len(self.fake.requests)
            result = self.city_run("cloud-talk", "off", cwd=cwd)
            self.assertOk(result)
            self.assertEqual(talk_lines(result.stdout), ["CLOUD TALK: off"])
            self.assertFalse(os.path.exists(self.talk_file), "every host is off: the stop must never be refused")
            self.assertEqual(len(self.fake.requests), before)
            self.assertNotIn(TALK, result.stdout + result.stderr)

    def test_the_status_line(self):
        result = self.city_run("status")
        self.assertEqual(talk_lines(result.stdout), [], "not joined: no line")
        self.assertOk(self.join())
        result = self.city_run("status")
        self.assertEqual(talk_lines(result.stdout), ["CLOUD TALK: off"])
        rl.set_talk(self.talk_file, self.fake.host, TALK) if hasattr(rl, "set_talk") else self.fail("set_talk is missing")
        before = len(self.fake.requests)
        result = self.city_run("status")
        self.assertOk(result)
        self.assertEqual(talk_lines(result.stdout), ["CLOUD TALK: on " + self.fake.host])
        self.assertNotIn(TALK, result.stdout + result.stderr)
        self.assertEqual(len(self.fake.requests), before, "status never talks to the relay")
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        cloud = [i for i, l in enumerate(lines) if l.startswith("CLOUD:")]
        self.assertTrue(cloud and lines[cloud[0] + 1].startswith("CLOUD TALK:"), "right after the CLOUD line")

    def test_the_status_line_outside_a_repo(self):
        import tempfile
        self.assertOk(self.join())
        outside = tempfile.mkdtemp(prefix="city_out_", dir=self.repo.base)
        self.assertEqual(talk_lines(self.city_run("status", cwd=outside).stdout), ["CLOUD TALK: off"])
        rl.set_talk(self.talk_file, self.fake.host, TALK) if hasattr(rl, "set_talk") else self.fail("set_talk is missing")
        result = self.city_run("status", cwd=outside)
        self.assertEqual(talk_lines(result.stdout), ["CLOUD TALK: on " + self.fake.host])
        self.assertNotIn(TALK, result.stdout + result.stderr)

    def test_on_outside_a_repo_is_refused(self):
        import tempfile
        outside = tempfile.mkdtemp(prefix="city_out_", dir=self.repo.base)
        code, out, err = self.on_in_a_terminal(cwd=outside)
        self.assertEqual(code, 1, out + err)
        self.assertRegex(out + err, r"CLOUD TALK: .*repo")
        self.assertFalse(os.path.exists(self.talk_file))

    def test_a_bad_word_is_refused(self):
        self.assertOk(self.join())
        result = self.city_run("cloud-talk", "maybe")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cloud-talk on", result.stdout + result.stderr)

    def test_help_names_it(self):
        with open(os.path.join(BIN, "agent-city.sh")) as fh:
            src = fh.read()
        self.assertIn("cloud-talk on", src)
        self.assertIn("cloud-talk off", src)


if __name__ == "__main__":
    unittest.main()
