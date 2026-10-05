"""Failing tests, cloud-city-3 slice W4: the switch on the machine and its
setup section (requirements/city.md, "Cloud page", "Start"; approved design
D6, D7 and the two adds of the gate in agent_state.txt).

Needs slice W3 (bin/agent_city_relay.py: read_start, set_start).

bin/agent_city_relay.py
  CLI   python3 agent_city_relay.py start --secret <join file> --talk-file <path> --start-file <path> on | off | status
      prints ONE line. No new secret: the key is the talk key. For `on` it is
      the first line of stdin (typed again by the owner: never argv, never
      printed, never saved by this command).
        status  "on <host>" when the start file has the host AND the talk
                file has a key for it (start needs talk), else "off <host>";
                no network; exit 0. No join file -> "none", exit 0.
        on      no join file                 -> "none", exit 1
                no key on stdin              -> "no-key", exit 2
                the talk file has no key for this host (talk is off on this
                    machine)                 -> "no-talk-here <host>", exit 7, nothing sent
                else ONE sync (no lines) with the typed key as X-City-Talk
                and the talk {"start": {}}:
                  the relay says talk refused   -> "refused <host>", exit 3
                  the relay says talk off, or says nothing about talk -> "no-talk <host>", exit 4
                  the relay is down or refuses the team key          -> "down <host>", exit 5
                  talk on, but its talk has no "start" with state "on"
                      (an old relay code)       -> "old-relay <host>", exit 8
                  talk on and start on          -> the start file gets the
                      host, "on <host>", exit 0 (cannot write it -> "no-write", exit 6)
                Nothing is saved unless the last one. The start file never holds a key.
        off     when the start file has the host: one sync with the talk
                {"start": {"off": true}} and the talk file's key (no key
                there: no request); whatever the relay answers, also when it
                is down, the host leaves the file. "off <host>", exit 0. No
                join file -> "none", exit 1.

bin/agent-city.sh
  cloud-start on   for the owner, in his own terminal, inside a joined repo.
      stdin is not a terminal -> exit 2, "CLOUD START: run this yourself in
      your own terminal ...", nothing is asked, sent or saved (an agent can
      never turn it on). Outside a repo, or the repo has not joined -> exit 1
      with a line that says so. Else it asks "Talk key (hidden): " with echo
      off, hands the key to the CLI above on stdin, and prints
          CLOUD START: on <host>                                                       exit 0
          CLOUD START: turn talking on first (agent-city cloud-talk on); nothing was saved   exit 1
          CLOUD START: the relay did not take this key; nothing was saved              exit 1
          CLOUD START: the relay has no TALK_KEY (or its cloud page is off); nothing was saved   exit 1
          CLOUD START: cannot reach the relay; nothing was saved                       exit 1
          CLOUD START: the relay does not know starting yet; put the new relay code on Cloudflare
              (skills/city/setup.md), then run this again; nothing was saved           exit 1
  cloud-start off  needs no terminal. "CLOUD START: off", exit 0. It must
      always work (it is the way to stop): outside a repo, or in a repo that
      has not joined, it removes the whole start file with no request.
  cloud-talk off   also turns starting off: in a joined repo the start host
      leaves the start file (and the relay is told, BEFORE talk is turned
      off there: it needs the key); outside a repo both files go. Its
      "CLOUD TALK: off" line stays. cloud-talk on never turns starting on.
  status           in a joined repo, right after the CLOUD TALK line: "CLOUD
      START: on <host>" or "CLOUD START: off" (on only when talk is on too).
      Not joined: no such line. It never talks to the relay. Outside a repo
      (like the CLOUD TALK lines there): one "CLOUD START: on <host>" per
      joined relay host that is on, else one "CLOUD START: off" when a repo
      is joined.

  start            typed INSIDE a repo, while the start file names a host:
      the server gets --joined-list too (as autostart and a start outside a
      repo already do), so a machine that takes start orders syncs every
      repo it has joined from the first moment, with no session line: the
      cloud page then shows every joined repo of that machine with its
      button, also one where nobody works yet (found in the E2E, 2026-10-02:
      a server started by hand inside a repo, with nobody there, was not
      seen by the cloud at all). No start file: as before.

skills/city/setup.md: two more numbered sections, 18 "Turn starting agents
  on" and 19 "Turn starting agents off" (see TestSetupSteps), and the cost
  line names starting.

Every test uses a fake relay on 127.0.0.1 and temp folders. Never a real key.

Run: python3 -m unittest tests.test_agent_city_cloud_start_client
"""

import os
import pty
import re
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

from relayhelp import join  # noqa: E402
from test_agent_city_cloud_upload import ClientCase  # noqa: E402
from test_agent_city_cloud_autostart import CloudCase  # noqa: E402
import agent_city_relay as rl  # noqa: E402

TALK = "fake-talk-key-for-tests-0002"
MODULE = os.path.join(BIN, "agent_city_relay.py")
SETUP = os.path.join(ROOT, "skills", "city", "setup.md")
REQ = os.path.join(ROOT, "requirements", "city.md")


def start_lines(text):
    return [l.strip() for l in text.splitlines() if l.strip().startswith("CLOUD START:")]


def talk_lines(text):
    return [l.strip() for l in text.splitlines() if l.strip().startswith("CLOUD TALK:")]


def helpers(case):
    for name in ("read_start", "set_start"):
        case.assertTrue(hasattr(rl, name), "agent_city_relay.%s is missing (slice W3)" % name)


class CliCase(ClientCase):
    def setUp(self):
        super().setUp()
        self.fake.talk_key = TALK
        self.talk_file = os.path.join(self.base, "cityhome", "cloud-talk")
        self.start_file = os.path.join(self.base, "cityhome", "cloud-start")
        self.secret = join(self.repo, self.fake.url)

    def talk_on(self, key=TALK):
        rl.set_talk(self.talk_file, self.fake.host, key)

    def cli(self, verb, stdin="", secret=None):
        return subprocess.run([sys.executable, MODULE, "start", "--secret", secret or self.secret,
                               "--talk-file", self.talk_file, "--start-file", self.start_file, verb],
                              input=stdin, capture_output=True, text=True, timeout=30)

    def started(self):
        helpers(self)
        return rl.read_start(self.start_file)

    def start_bodies(self):
        return [b["talk"].get("start") for b in self.fake.sync_bodies() if isinstance(b.get("talk"), dict)]


class TestCli(CliCase):
    def test_on_with_the_right_key(self):
        self.talk_on()
        p = self.cli("on", TALK + "\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "on " + self.fake.host), p.stderr)
        self.assertEqual(self.started(), {self.fake.host})
        self.assertEqual(stat.S_IMODE(os.stat(self.start_file).st_mode), 0o600)
        with open(self.start_file) as fh:
            self.assertNotIn(TALK, fh.read(), "the start file never holds a key")
        self.assertNotIn(TALK, p.stdout + p.stderr)
        self.assertEqual(self.fake.talk_headers(), [TALK], "one sync, with the typed key as a header")
        self.assertEqual(self.fake.sync_bodies()[0]["lines"], [])
        self.assertEqual(self.start_bodies(), [{}], "it asks the relay about start")

    def test_on_needs_talk_on_here(self):
        p = self.cli("on", TALK + "\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (7, "no-talk-here " + self.fake.host), p.stderr)
        self.assertFalse(os.path.exists(self.start_file))
        self.assertEqual(self.fake.requests, [], "talk is off on this machine: nothing is sent")

    def test_on_with_a_wrong_key_saves_nothing(self):
        self.talk_on()
        p = self.cli("on", "not-the-key\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (3, "refused " + self.fake.host), p.stderr)
        self.assertFalse(os.path.exists(self.start_file))
        self.assertNotIn("not-the-key", p.stdout + p.stderr)

    def test_the_key_in_the_file_is_not_enough(self):
        self.talk_on()
        p = self.cli("on", "\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (2, "no-key"), "the owner types the key again: it is not read from the talk file")
        self.assertFalse(os.path.exists(self.start_file))
        self.assertEqual(self.fake.requests, [])

    def test_on_when_the_relay_has_no_talk(self):
        self.talk_on()
        self.fake.talk_key = None
        p = self.cli("on", TALK + "\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (4, "no-talk " + self.fake.host), p.stderr)
        self.assertFalse(os.path.exists(self.start_file))

    def test_on_when_the_relay_is_down(self):
        self.talk_on()
        self.fake.mode = "error"
        p = self.cli("on", TALK + "\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (5, "down " + self.fake.host), p.stderr)
        self.assertFalse(os.path.exists(self.start_file))

    def test_on_with_an_old_relay_code(self):
        self.talk_on()
        self.fake.start = False                      # the relay answers talk, and knows nothing of start
        p = self.cli("on", TALK + "\n")
        self.assertEqual((p.returncode, p.stdout.strip()), (8, "old-relay " + self.fake.host), p.stderr)
        self.assertFalse(os.path.exists(self.start_file), "an old relay would never hand an order down: say so, save nothing")

    def test_on_without_a_join(self):
        p = self.cli("on", TALK + "\n", secret=os.path.join(self.base, "nope"))
        self.assertEqual((p.returncode, p.stdout.strip()), (1, "none"))
        self.assertEqual(self.fake.requests, [])

    def test_status_never_calls_the_relay(self):
        helpers(self)
        p = self.cli("status")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "off " + self.fake.host))
        rl.set_start(self.start_file, self.fake.host, True)
        p = self.cli("status")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "off " + self.fake.host), "start needs talk: no talk key, not on")
        self.talk_on()
        p = self.cli("status")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "on " + self.fake.host))
        self.assertNotIn(TALK, p.stdout + p.stderr)
        p = self.cli("status", secret=os.path.join(self.base, "nope"))
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "none"))
        self.assertEqual(self.fake.requests, [])

    def test_off_tells_the_relay_and_forgets_the_host(self):
        helpers(self)
        self.talk_on()
        rl.set_start(self.start_file, self.fake.host, True)
        rl.set_start(self.start_file, "other.example", True)
        p = self.cli("off")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "off " + self.fake.host), p.stderr)
        self.assertEqual(self.started(), {"other.example"})
        self.assertEqual(self.fake.talk_headers(), [TALK])
        self.assertEqual(self.start_bodies(), [{"off": True}])
        self.assertEqual(len(self.fake.start_offs), 1)
        self.assertEqual(self.fake.offs, [], "talk stays on")
        self.assertEqual(rl.read_talk(self.talk_file), {self.fake.host: TALK})

    def test_off_with_the_relay_down_still_turns_it_off_here(self):
        helpers(self)
        self.talk_on()
        rl.set_start(self.start_file, self.fake.host, True)
        self.fake.mode = "error"
        p = self.cli("off")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "off " + self.fake.host), p.stderr)
        self.assertEqual(self.started(), set())

    def test_off_without_a_talk_key_sends_nothing(self):
        helpers(self)
        rl.set_start(self.start_file, self.fake.host, True)
        p = self.cli("off")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "off " + self.fake.host))
        self.assertEqual(self.started(), set())
        self.assertEqual(self.fake.requests, [])

    def test_off_when_it_was_never_on_sends_nothing(self):
        self.talk_on()
        p = self.cli("off")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "off " + self.fake.host))
        self.assertEqual(self.fake.requests, [])


class TestCommand(CloudCase):
    """bin/agent-city.sh cloud-start on | off, the status line, and what cloud-talk off does to it."""

    def setUp(self):
        super().setUp()
        self.fake.city = True
        self.fake.talk_key = TALK
        self.talk_file = os.path.join(self.home, "cloud-talk")
        self.start_file = os.path.join(self.home, "cloud-start")

    def talk_on(self):
        rl.set_talk(self.talk_file, self.fake.host, TALK)

    def start_set(self, host=None):
        helpers(self)
        rl.set_start(self.start_file, host or self.fake.host, True)

    def started(self):
        helpers(self)
        return rl.read_start(self.start_file)

    def on_in_a_terminal(self, key=TALK, cwd=None, word="cloud-start"):
        """`cloud-start on` with a real (pseudo) terminal on stdin; KEY is typed into it."""
        env = self.repo._env({"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.home,
                              "AGENT_CITY_PORT": str(self.port)})
        master, slave = pty.openpty()
        try:
            proc = subprocess.Popen([self.repo.script_path("agent-city.sh"), word, "on"],
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
        self.talk_on()
        before = len(self.fake.requests)
        result = self.city_run("cloud-start", "on", stdin=TALK + "\n")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("CLOUD START: run this yourself in your own terminal", result.stdout + result.stderr)
        self.assertFalse(os.path.exists(self.start_file), "nothing may be saved without a terminal")
        self.assertEqual(len(self.fake.requests), before, "nothing may be sent without a terminal")

    def test_the_owner_turns_it_on_in_his_terminal(self):
        self.assertOk(self.join())
        self.talk_on()
        code, out, err = self.on_in_a_terminal()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(start_lines(out), ["CLOUD START: on " + self.fake.host])
        self.assertIn("Talk key (hidden)", err)
        self.assertNotIn(TALK, out + err, "the key is never shown")
        self.assertEqual(self.started(), {self.fake.host})
        self.assertEqual(stat.S_IMODE(os.stat(self.start_file).st_mode), 0o600)
        with open(self.start_file) as fh:
            self.assertNotIn(TALK, fh.read())

    def test_talk_must_be_on_first(self):
        self.assertOk(self.join())
        code, out, err = self.on_in_a_terminal()
        self.assertEqual(code, 1, out + err)
        self.assertIn("CLOUD START: turn talking on first (agent-city cloud-talk on); nothing was saved", out + err)
        self.assertFalse(os.path.exists(self.start_file))

    def test_a_wrong_key_saves_nothing(self):
        self.assertOk(self.join())
        self.talk_on()
        code, out, err = self.on_in_a_terminal(key="not-the-key")
        self.assertEqual(code, 1, out + err)
        self.assertIn("CLOUD START: the relay did not take this key; nothing was saved", out + err)
        self.assertFalse(os.path.exists(self.start_file))

    def test_an_old_relay_is_said_in_plain_words(self):
        self.assertOk(self.join())
        self.talk_on()
        self.fake.start = False
        code, out, err = self.on_in_a_terminal()
        self.assertEqual(code, 1, out + err)
        self.assertIn("CLOUD START: the relay does not know starting yet", out + err)
        self.assertIn("nothing was saved", out + err)
        self.assertFalse(os.path.exists(self.start_file))

    def test_the_relay_is_down(self):
        self.assertOk(self.join())
        self.talk_on()
        self.fake.mode = "error"
        code, out, err = self.on_in_a_terminal()
        self.assertEqual(code, 1, out + err)
        self.assertIn("CLOUD START: cannot reach the relay; nothing was saved", out + err)

    def test_not_joined_is_refused(self):
        code, out, err = self.on_in_a_terminal()
        self.assertEqual(code, 1, out + err)
        self.assertIn("CLOUD START:", out + err)
        self.assertRegex(out + err, r"(?i)join")
        self.assertFalse(os.path.exists(self.start_file))

    def test_on_outside_a_repo_is_refused(self):
        outside = tempfile.mkdtemp(prefix="city_out_", dir=self.repo.base)
        code, out, err = self.on_in_a_terminal(cwd=outside)
        self.assertEqual(code, 1, out + err)
        # city-device-join: outside a repo on a computer that never joined, the line says to join
        self.assertRegex(out + err, r"CLOUD START: .*join")
        self.assertFalse(os.path.exists(self.start_file))

    def test_off_is_one_command_and_needs_no_terminal(self):
        self.assertOk(self.join())
        self.talk_on()
        self.assertEqual(self.on_in_a_terminal()[0], 0)
        result = self.city_run("cloud-start", "off")
        self.assertOk(result)
        self.assertEqual(start_lines(result.stdout), ["CLOUD START: off"])
        self.assertEqual(self.started(), set())
        self.assertEqual(len(self.fake.start_offs), 1, "the relay was told, so a waiting order is not opened")
        self.assertEqual(rl.read_talk(self.talk_file), {self.fake.host: TALK}, "talk stays on: two switches")
        again = self.city_run("cloud-start", "off")
        self.assertOk(again)
        self.assertEqual(start_lines(again.stdout), ["CLOUD START: off"])

    def test_off_always_works(self):
        self.assertOk(self.join())
        outside = tempfile.mkdtemp(prefix="city_out_", dir=self.repo.base)
        for cwd in (outside, None):
            self.start_set()
            self.start_set("other.example")
            if cwd is None:
                os.remove(self.repo.path(".secrets", "agent-city-relay"))   # a repo that has not joined (any more)
            before = len(self.fake.requests)
            result = self.city_run("cloud-start", "off", cwd=cwd)
            self.assertOk(result)
            self.assertEqual(start_lines(result.stdout), ["CLOUD START: off"])
            self.assertFalse(os.path.exists(self.start_file), "every host is off: the stop must never be refused")
            self.assertEqual(len(self.fake.requests), before)

    def test_talk_off_turns_starting_off_too(self):
        self.assertOk(self.join())
        self.talk_on()
        self.assertEqual(self.on_in_a_terminal()[0], 0)
        result = self.city_run("cloud-talk", "off")
        self.assertOk(result)
        self.assertEqual(talk_lines(result.stdout), ["CLOUD TALK: off"])
        self.assertEqual(self.started(), set(), "talk off: starting is off too")
        self.assertEqual(len(self.fake.start_offs), 1, "the relay was told about start while the key was still there")
        self.assertEqual(len(self.fake.offs), 1)
        with self.fake.lock:
            kinds = ["start-off" if (b.get("talk") or {}).get("start") == {"off": True} else
                     "talk-off" if (b.get("talk") or {}).get("off") else "other"
                     for b in (r["body"] for r in self.fake.requests if r["path"] == "/v1/sync") if isinstance(b, dict)]
        self.assertLess(kinds.index("start-off"), kinds.index("talk-off"), "start off first: it needs the key")

    def test_talk_on_again_never_turns_starting_on(self):
        self.assertOk(self.join())
        self.talk_on()
        self.assertEqual(self.on_in_a_terminal()[0], 0)
        self.assertOk(self.city_run("cloud-talk", "off"))
        code, out, err = self.on_in_a_terminal(word="cloud-talk")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.started(), set())
        self.assertEqual(start_lines(self.city_run("status").stdout), ["CLOUD START: off"])

    def test_talk_off_outside_a_repo_removes_both(self):
        self.assertOk(self.join())
        outside = tempfile.mkdtemp(prefix="city_out_", dir=self.repo.base)
        self.talk_on()
        self.start_set()
        self.assertOk(self.city_run("cloud-talk", "off", cwd=outside))
        self.assertFalse(os.path.exists(self.talk_file))
        self.assertFalse(os.path.exists(self.start_file))

    def test_the_status_line(self):
        result = self.city_run("status")
        self.assertEqual(start_lines(result.stdout), [], "not joined: no line")
        self.assertOk(self.join())
        self.assertEqual(start_lines(self.city_run("status").stdout), ["CLOUD START: off"])
        self.start_set()
        self.assertEqual(start_lines(self.city_run("status").stdout), ["CLOUD START: off"],
                         "the host is in the start file but talk is off: a machine that takes no order says off")
        self.talk_on()
        before = len(self.fake.requests)
        result = self.city_run("status")
        self.assertOk(result)
        self.assertEqual(start_lines(result.stdout), ["CLOUD START: on " + self.fake.host])
        self.assertNotIn(TALK, result.stdout + result.stderr)
        self.assertEqual(len(self.fake.requests), before, "status never talks to the relay")
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        talk = [i for i, l in enumerate(lines) if l.startswith("CLOUD TALK:")]
        self.assertTrue(talk and lines[talk[-1] + 1].startswith("CLOUD START:"), "right after the CLOUD TALK line")

    def test_the_status_line_outside_a_repo(self):
        self.assertOk(self.join())
        outside = tempfile.mkdtemp(prefix="city_out_", dir=self.repo.base)
        self.assertEqual(start_lines(self.city_run("status", cwd=outside).stdout), ["CLOUD START: off"])
        self.talk_on()
        self.start_set()
        result = self.city_run("status", cwd=outside)
        self.assertEqual(start_lines(result.stdout), ["CLOUD START: on " + self.fake.host])

    def test_a_bad_word_is_refused(self):
        self.assertOk(self.join())
        result = self.city_run("cloud-start", "maybe")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cloud-start on", result.stdout + result.stderr)

    def test_help_names_it(self):
        with open(os.path.join(BIN, "agent-city.sh")) as fh:
            src = fh.read()
        self.assertIn("cloud-start on", src)
        self.assertIn("cloud-start off", src)
        result = self.city_run("--help")
        self.assertIn("cloud-start on", result.stdout + result.stderr)

    def syncs(self):
        with self.fake.lock:
            return [r for r in self.fake.requests if r["path"] == "/v1/sync"]

    def stop_city(self):
        self.city_run("stop")

    def test_a_start_inside_a_repo_syncs_the_joined_repos_when_starting_is_on(self):
        from relayhelp import wait_for
        self.assertOk(self.join())
        self.talk_on()
        self.start_set()
        before = len(self.syncs())
        self.addCleanup(self.stop_city)
        self.assertOk(self.city_run("start"))
        got = wait_for(lambda: [r for r in self.syncs()[before:]
                                if isinstance(r["body"], dict) and isinstance(r["body"].get("talk"), dict)
                                and "start" in r["body"]["talk"]], timeout=15)
        self.assertTrue(got, "nobody works there and no line was sent: the machine must still ask for its orders")
        self.assertEqual(got[0]["talk_header"], TALK)

    def test_a_start_inside_a_repo_with_starting_off_is_as_before(self):
        import time as _time
        self.assertOk(self.join())
        self.talk_on()
        before = len(self.syncs())
        self.addCleanup(self.stop_city)
        self.assertOk(self.city_run("start"))
        _time.sleep(4.0)
        self.assertEqual(len(self.syncs()), before, "starting off, no session line: nothing is sent, as before")

    def test_the_local_switches_are_as_before(self):
        self.assertOk(self.join())
        result = self.city_run("status")
        self.assertEqual(talk_lines(result.stdout), ["CLOUD TALK: off"])
        self.assertEqual([l.strip() for l in result.stdout.splitlines() if l.strip().startswith("CLOUD:")],
                         ["CLOUD: on " + self.fake.host], "the fake relay of this case has the cloud page on")


class TestSetupSteps(unittest.TestCase):
    def setUp(self):
        with open(SETUP) as fh:
            self.text = fh.read()
        self.sections = re.findall(r"(?ms)^## (\d+)\. ([^\n]+)\n(.*?)(?=^## |\Z)", self.text)

    def section(self, number):
        hits = [(title, body) for n, title, body in self.sections if int(n) == number]
        self.assertTrue(hits, "no section %d" % number)
        return hits[0]

    def test_two_more_sections(self):
        nums = [int(n) for n, _, _ in self.sections]
        self.assertEqual(nums[:19], list(range(1, 20)), "sections 1 to 19, 18 and 19 are new")
        on, _ = self.section(18)
        off, _ = self.section(19)
        self.assertRegex(on, r"(?i)^Turn starting agents on$")
        self.assertRegex(off, r"(?i)^Turn starting agents off$")
        for title in (on, off):
            self.assertNotRegex(title, r"(?i)talk", "tests of step 2 find the talk sections by that word")

    def test_on_steps(self):
        _, body = self.section(18)
        self.assertIn("You should see", body)
        self.assertIn("agent-city-relay.js", body, "the new relay code is pasted again")
        self.assertIn("cloud-deploy", body, "the new page code is deployed again")
        self.assertIn("cloud-start on", body)
        self.assertIn("CLOUD START: on", body)
        self.assertRegex(body, r"(?i)section 16", "talking must be on first")
        self.assertRegex(body, r"(?i)talk key")
        self.assertRegex(body, r"(?i)hidden")
        self.assertRegex(body, r"(?i)no new (key|secret)|same (talk )?key")
        self.assertRegex(body, r"(?i)each machine|every machine|on that machine")
        self.assertRegex(body, r"(?i)never .*(chat|agent)", "the key is never typed into a chat with an agent")
        self.assertRegex(body, r"(?i)off by default|stays off")
        self.assertIn("可开 agent", body, "what the page shows for a machine that takes orders")
        self.assertIn("加 agent", body)

    def test_on_says_the_new_risk_in_plain_words(self):
        """ADD 1 of the gate (2026-10-01)."""
        _, body = self.section(18)
        self.assertRegex(body, r"(?is)(whoever|anyone who) can log in as you.{0,200}(open|start).{0,80}(Manager|Helper)",
                         "who can log in as the owner can open a Manager or a Helper")
        self.assertIn("Manager", body)
        self.assertIn("Helper", body)
        self.assertRegex(body, r"(?is)(open|start).{0,300}(type|talk) to (it|them)", "and then type to it")
        self.assertRegex(body, r"(?i)joined", "only in a repo that joined")
        self.assertRegex(body, r"(?i)machines? with starting on|start(ing)?[- ]on machine")
        self.assertRegex(body, r"(?i)fixed", "the command is fixed: no choice of role, model, flag or folder")
        self.assertRegex(body, r"(?i)10 (an|per) hour")
        self.assertRegex(body, r"(?i)decisions\.jsonl")
        self.assertRegex(body, r"(?i)task manager", "a task manager is never made this way")
        self.assertRegex(body, r"(?is)keeps? .{0,60}(city|program).{0,60}running|stays? (up|running)",
                         "a machine with starting on keeps its small city program running")
        self.assertRegex(body, r"(?i)restart|reboot", "after a restart of the computer it comes back with the next session")

    def test_off_says_every_way_to_stop_it(self):
        """ADD 1 of the gate: how to stop it."""
        _, body = self.section(19)
        self.assertIn("You should see", body)
        self.assertIn("cloud-start off", body)
        self.assertIn("CLOUD START: off", body)
        self.assertIn("TALK_KEY", body)
        self.assertRegex(body, r"(?i)delete", "delete TALK_KEY: off for every machine")
        self.assertRegex(body, r"(?i)(end|revoke|log out|sign out).{0,80}(session|login)|(session|login).{0,80}(end|revoke)",
                         "end the Access session")
        self.assertRegex(body, r"(?i)one machine|that machine|this machine")
        self.assertRegex(body, r"(?i)all machines|every machine")
        self.assertIn("cloud-talk off", body, "turning talking off turns starting off too")

    def test_the_cloud_page_sections_point_to_it(self):
        title, body = self.section(16)
        self.assertRegex(body, r"(?i)section 18")

    def test_the_cost_line_names_starting(self):
        tail = self.text[self.text.rindex("free plan"):]
        self.assertRegex(tail, r"(?i)start")

    def test_no_real_address_or_key(self):
        for word in ("maverickleeweilin88", "gmail.com"):
            self.assertNotIn(word, self.text)


class TestRequirementLines(unittest.TestCase):
    """The requirement lines of this step (written with these tests; a change needs the owner's yes)."""

    def setUp(self):
        with open(REQ) as fh:
            self.text = fh.read()

    def cloud(self):
        return self.text[self.text.index("## Cloud page"):self.text.index("## Relay setup")]

    def test_start_rules(self):
        self.assertIn("### Start", self.text)
        body = self.text[self.text.index("### Start"):self.text.index("## Relay setup")]
        for word in ("cloud-start on", "cloud-start off", "CLOUD START: on", "city_order", "/api/agent/add",
                     "X-City-Page", "TALK_KEY", "cloud-orders", "60 s", "3 min", "10 an hour", "40 a day",
                     "在路上", "已打开", "没打开", "那台电脑没开", "那台电脑不能自己开终端", "还是打开",
                     "可开 agent", "owner not seen", "never calls a machine", "team key alone", "decisions.jsonl",
                     "add_agent", "task manager", "15 s"):
            self.assertIn(word, body, word)
        self.assertRegex(body, r"(?i)no new secret|no second secret")
        self.assertRegex(body, r"(?i)never opened later|never opened again")

    def test_the_orders_line_names_both_kinds(self):
        orders = [l for l in self.text.splitlines() if l.startswith("- Orders")]
        self.assertEqual(len(orders), 1)
        self.assertRegex(orders[0], r"(?i)text for a session's chat queue only")
        self.assertRegex(orders[0], r"(?i)team key alone never makes a message")
        self.assertRegex(orders[0], r"(?i)start order")
        self.assertRegex(orders[0], r"(?i)territory id")
        self.assertNotIn("A message is the one kind of order", self.text)

    def test_old_rules_are_replaced_not_left(self):
        self.assertNotIn('no "add agent" button; these show as 以后开放', self.text)
        self.assertNotIn("the cloud page shows the button as 以后开放 (step 3 of the Cloud page)", self.text)
        self.assertNotIn("The relay carries no such order", self.text)
        self.assertNotIn("The demo and the cloud city have no button.", self.text)
        self.assertNotIn("Later, not built yet, never blocked by this: 3 start agents from the page", self.text)

    def test_the_limits_line_knows_starting(self):
        limits = self.text[self.text.index("## Limits"):self.text.index("## Joining")]
        self.assertRegex(limits, r"(?i)start(ing)? on")


if __name__ == "__main__":
    unittest.main()
