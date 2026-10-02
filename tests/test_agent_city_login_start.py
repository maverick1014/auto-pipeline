"""Failing tests, city-login-start: the city program comes back by itself after
a restart / login (requirements/city.md, "Cloud page", "Login start"; owner,
2026-10-02, on the first real Cloudflare run: after a restart of the computer
nothing ran until he opened a session, so the cloud page said the machine was
off).

  ./agent-city.sh login-start on
      The owner's, in his own terminal. In order:
        1. not macOS (`uname -s` is not Darwin) -> one plain line
           "LOGIN START: macOS only for now; nothing was changed", exit 1,
           nothing written, launchctl never called
        2. stdin is not a terminal -> exit 2, "LOGIN START: run this yourself
           in your own terminal ...", nothing written, launchctl never called
           (an agent, a hook and a plugin update can never install it)
        3. <city home>/login-start.sh = a byte copy of bin/agent-city-shim,
           mode 0755 (the stable launcher, outside the versioned plugin folder)
        4. $HOME/Library/LaunchAgents/com.auto-pipeline.agent-city.login.plist:
             Label                 com.auto-pipeline.agent-city.login
             ProgramArguments      /bin/sh, <city home>/login-start.sh, login-start, run
             RunAtLoad             true   (at once, and at every login)
             AbandonProcessGroup   true   (the city server outlives the launcher)
             EnvironmentVariables  PATH = the PATH of this terminal without the
                                   entries inside a plugin folder (the running
                                   plugin's own folder, or any .../plugins/cache/...);
                                   AGENT_CITY_HOME, AGENT_CITY_DIR, AGENT_CITY_PORT
                                   only when set. Never AGENT_CITY_PLUGIN_ROOT.
           No KeepAlive, no StartInterval: the server's own idle rule stays.
           No versioned plugin path anywhere in the file.
        5. `launchctl bootout gui/<uid>/<label>` (quiet; "not loaded" is fine),
           then `launchctl bootstrap gui/<uid> <plist>`. launchctl is found on
           PATH, never by an absolute path. A bootstrap that fails is tried
           again, at most 3 times in all, 1 s apart (on a real Mac the old copy
           can still be going away right after the bootout).
        6. loaded -> "LOGIN START: on", exit 0. Not loaded -> the plist and the
           launcher are removed again, a line starting "LOGIN START:" that
           names launchctl, exit 1.
      It works from any folder, joined or not. Twice is fine.

  ./agent-city.sh login-start off
      Needs no terminal, always works: bootout (quiet), the plist and the
      launcher are removed, "LOGIN START: off", exit 0. Nothing else in
      LaunchAgents or in the city home is touched. Not macOS: the line of 1.

  ./agent-city.sh login-start run
      What the login item runs (not for people; a login has no folder, and the
      session-start autostart does nothing outside a repo). It walks
      <city home>/joined-repos.txt in order: each repo whose folder and join
      file are there, each relay host once. For each it does today's autostart
      from that repo (tests/test_agent_city_cloud_autostart.py):
        a city server already runs -> nothing; a cloud session -> nothing;
        the marker names the repo's relay host -> start; no marker -> one quiet
        probe, on -> start; off or no answer -> the next host.
      It stops at the first start. start = today's start from that repo (its
      agent.conf: port, idle, language), with --joined-list, no browser. It
      works in the foreground: when it returns, the server is up or will not
      come. It prints nothing and exits 0. `autostart` itself is unchanged.

  ./agent-city.sh status
      One more line, the last one: "LOGIN START: on" (the plist is there) or
      "LOGIN START: off". From the file only: launchctl is never called. In and
      outside a repo, joined or not.

  skills/city/setup.md: section 20 (turn it on, check it, turn it off).
  requirements/city.md: "### Login start" under "Cloud page".

Every test uses a scratch HOME (so ~/Library/LaunchAgents is a temp folder), a
fake launchctl and a fake uname first on PATH, a temp city dir and city home, a
fake relay on 127.0.0.1 and a free port. Never the real LaunchAgents, never the
real launchctl, never the owner's city.

Run: python3 -m unittest tests.test_agent_city_login_start
"""

import os
import plistlib
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

from relayhelp import FAKE_KEY, make_repo  # noqa: E402
from relayhelp import join as join_by_hand  # noqa: E402
from scripthelp import args_of  # noqa: E402
from test_agent_city_join import free_port  # noqa: E402
from test_agent_city_cloud_autostart import CloudCase  # noqa: E402
import agent_city_relay as rl  # noqa: E402

LABEL = "com.auto-pipeline.agent-city.login"
CACHE_PARTS = (".claude", "plugins", "cache", "auto-pipeline", "auto-pipeline")
SETUP = os.path.join(ROOT, "skills", "city", "setup.md")
REQ = os.path.join(ROOT, "requirements", "city.md")
MAC_ONLY = "LOGIN START: macOS only for now"

# Like the real one: bootstrap of a loaded label fails (5), bootout of one that
# is not loaded fails (3). LAUNCHCTL_FAIL=1: bootstrap always fails.
# LAUNCHCTL_SLOW=1: the first bootstrap after a bootout of a loaded label fails
# once (the old copy is still going away), the next one works.
LAUNCHCTL_STUB = r"""#!/bin/sh
{ printf 'CALL'; for a in "$@"; do printf '\t%s' "$a"; done; printf '\n'; } >> "$LAUNCHCTL_LOG"
case "${1:-}" in
  bootstrap)
    if [ -f "$LAUNCHCTL_STATE.busy" ]; then
      rm -f "$LAUNCHCTL_STATE.busy"
      echo "Bootstrap failed: 5: Input/output error" >&2
      exit 5
    fi
    if [ -n "${LAUNCHCTL_FAIL:-}" ] || [ -f "$LAUNCHCTL_STATE" ]; then
      echo "Bootstrap failed: 5: Input/output error" >&2
      exit 5
    fi
    : > "$LAUNCHCTL_STATE"
    exit 0 ;;
  bootout)
    if [ -f "$LAUNCHCTL_STATE" ]; then
      rm -f "$LAUNCHCTL_STATE"
      [ -z "${LAUNCHCTL_SLOW:-}" ] || : > "$LAUNCHCTL_STATE.busy"
      exit 0
    fi
    echo "Boot-out failed: 3: No such process" >&2
    exit 3 ;;
esac
exit 0
"""

UNAME_STUB = "#!/bin/sh\necho \"${FAKE_UNAME:-Darwin}\"\n"

VERSION_STUB = """#!/usr/bin/env bash
printf 'VERSION=%s\\n' "{ver}"
for a in "$@"; do printf 'ARG=[%s]\\n' "$a"; done
exit 0
"""


def login_lines(text):
    return [l.strip() for l in text.splitlines() if l.strip().startswith("LOGIN START:")]


class LoginCase(CloudCase):
    def setUp(self):
        super().setUp()
        self.userhome = self.repo.fake_home()
        self.agents = os.path.join(self.userhome, "Library", "LaunchAgents")
        self.plist = os.path.join(self.agents, LABEL + ".plist")
        self.launcher = os.path.join(self.home, "login-start.sh")
        self.cache = os.path.join(self.userhome, *CACHE_PARTS)
        self.ctl_log = os.path.join(self.repo.base, "launchctl.log")
        self.ctl_state = os.path.join(self.repo.base, "launchctl.loaded")
        self.repo.stub_tool("launchctl", LAUNCHCTL_STUB)
        self.repo.stub_tool("uname", UNAME_STUB)
        self.outside = tempfile.mkdtemp(prefix="city_out_", dir=self.repo.base)

    def env(self, extra=None, unset=()):
        env = self.repo._env({"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.home,
                              "AGENT_CITY_PORT": str(self.port),
                              "LAUNCHCTL_LOG": self.ctl_log, "LAUNCHCTL_STATE": self.ctl_state})
        env.pop("AGENT_CITY_PLUGIN_ROOT", None)
        env.pop("FAKE_UNAME", None)
        env.pop("LAUNCHCTL_FAIL", None)
        env.pop("LAUNCHCTL_SLOW", None)
        env.update(extra or {})
        for key in unset:
            env.pop(key, None)
        return env

    def city_run(self, *args, stdin=None, cwd=None, extra=None):
        more = {"LAUNCHCTL_LOG": self.ctl_log, "LAUNCHCTL_STATE": self.ctl_state}
        more.update(extra or {})
        return super().city_run(*args, stdin=stdin, cwd=cwd, extra=more)

    def on(self, cwd=None, extra=None, unset=()):
        """`login-start on` with a real (pseudo) terminal on stdin, as the owner types it."""
        master, slave = pty.openpty()
        try:
            proc = subprocess.Popen([self.repo.script_path("agent-city.sh"), "login-start", "on"],
                                    cwd=cwd or self.repo.cwd, env=self.env(extra, unset), stdin=slave,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out, err = proc.communicate(timeout=30)
        finally:
            os.close(master)
            os.close(slave)
        return proc.returncode, out, err

    def assertOn(self, got):
        code, out, err = got
        self.assertEqual(code, 0, out + err)
        self.assertEqual(login_lines(out), ["LOGIN START: on"], out + err)

    def calls(self):
        if not os.path.exists(self.ctl_log):
            return []
        with open(self.ctl_log) as fh:
            rows = [l.rstrip("\n").split("\t") for l in fh if l.strip()]
        return [r[1:] for r in rows if r and r[0] == "CALL"]

    def plist_data(self):
        self.assertTrue(os.path.isfile(self.plist), "no login item at %s" % self.plist)
        with open(self.plist, "rb") as fh:
            return plistlib.load(fh)

    def plist_text(self):
        with open(self.plist, "rb") as fh:
            return fh.read().decode("utf-8", "replace")

    def assert_nothing_installed(self):
        self.assertFalse(os.path.exists(self.plist), "a login item was written")
        self.assertFalse(os.path.exists(self.launcher), "a launcher was written")
        left = os.listdir(self.agents) if os.path.isdir(self.agents) else []
        self.assertEqual(left, [], "LaunchAgents must stay empty")

    def version(self, ver):
        """One installed plugin version in the scratch HOME's plugin cache: a stub that says who ran."""
        folder = os.path.join(self.cache, ver, "bin")
        os.makedirs(folder)
        path = os.path.join(folder, "agent-city.sh")
        with open(path, "w") as fh:
            fh.write(VERSION_STUB.format(ver=ver))
        os.chmod(path, 0o755)

    def launchd_env(self, extra=None):
        """What launchd gives the login item: HOME and the plist's own EnvironmentVariables."""
        env = {"HOME": self.userhome}
        env.update(self.plist_data().get("EnvironmentVariables", {}))
        env.update(extra or {})
        return env

    def run_login_item(self, extra=None):
        """Run the plist's program as launchd does at a login: its own arguments, from /."""
        return subprocess.run(self.plist_data()["ProgramArguments"], cwd="/", env=self.launchd_env(extra),
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)

    def run_verb(self, extra=None):
        """`login-start run` from a folder that is no repo, as at a login."""
        result = self.city_run("login-start", "run", cwd=self.outside, extra=extra)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((result.stdout + result.stderr).strip(), "", "login-start run prints nothing")
        return result

    def assert_never_starts(self, wait=0.5):
        time.sleep(wait)
        self.assertIsNone(self.pid(), "a city server was started")


# ------------------------------------------------------------------------ on

class TestOn(LoginCase):
    def test_an_agent_cannot_turn_it_on(self):
        result = self.city_run("login-start", "on")          # stdin is a pipe, not a terminal
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("LOGIN START: run this yourself in your own terminal", result.stdout + result.stderr)
        self.assert_nothing_installed()
        self.assertEqual(self.calls(), [], "launchctl must not be called without a terminal")

    def test_the_owner_turns_it_on(self):
        self.assertOn(self.on())
        data = self.plist_data()
        self.assertEqual(data.get("Label"), LABEL)
        self.assertEqual(data.get("ProgramArguments"), ["/bin/sh", self.launcher, "login-start", "run"])
        self.assertIs(data.get("RunAtLoad"), True, "it runs at once and at every login")
        self.assertIs(data.get("AbandonProcessGroup"), True,
                      "else launchd kills the city server when the launcher exits")
        for key in ("KeepAlive", "StartInterval", "StartCalendarInterval", "WatchPaths"):
            self.assertNotIn(key, data, "the server's own idle rule stays: nothing restarts it")
        self.assertIn(["bootstrap", "gui/%d" % os.getuid(), self.plist], self.calls())

    def test_the_launcher_is_the_shim_outside_the_plugin(self):
        self.assertOn(self.on())
        with open(self.launcher, "rb") as fh:
            got = fh.read()
        with open(self.repo.plugin_path("bin", "agent-city-shim"), "rb") as fh:
            self.assertEqual(got, fh.read(), "the launcher is a byte copy of bin/agent-city-shim")
        self.assertTrue(stat.S_IMODE(os.stat(self.launcher).st_mode) & 0o100, "the launcher is executable")
        self.assertFalse(os.path.realpath(self.launcher).startswith(self.repo.plugin + os.sep),
                         "the launcher lives outside the plugin folder")

    def test_from_any_folder_joined_or_not(self):
        self.assertOn(self.on(cwd=self.outside))
        self.assertTrue(os.path.isfile(self.plist))

    def test_twice_is_fine(self):
        self.assertOn(self.on())
        self.assertOn(self.on())
        self.assertEqual(os.listdir(self.agents), [LABEL + ".plist"])
        self.assertTrue(os.path.exists(self.ctl_state), "the login item is loaded after the second on")
        self.assertEqual(self.plist_data().get("Label"), LABEL)

    def test_a_slow_unload_is_tried_again(self):
        """Found in review: on a real Mac a bootstrap right after a bootout can fail
        (5) while the old copy is still going away. A second `on` must not end
        with the working login item removed."""
        self.assertOn(self.on())
        self.assertOn(self.on(extra={"LAUNCHCTL_SLOW": "1"}))
        self.assertTrue(os.path.exists(self.ctl_state), "loaded after the second try")
        self.assertTrue(os.path.isfile(self.plist))
        self.assertTrue(os.path.isfile(self.launcher))
        boots = [c for c in self.calls() if c and c[0] == "bootstrap"]
        self.assertEqual(len(boots), 3, "one for the first on, two for the second")

    def test_it_gives_up_after_three_tries(self):
        code, out, err = self.on(extra={"LAUNCHCTL_FAIL": "1"})
        self.assertEqual(code, 1, out + err)
        boots = [c for c in self.calls() if c and c[0] == "bootstrap"]
        self.assertEqual(len(boots), 3, "tried 3 times, then it gives up")
        self.assert_nothing_installed()

    def test_no_versioned_plugin_path_in_the_login_item(self):
        stale = os.path.join(self.cache, "0.18.0", "bin")
        base = self.env()
        path = os.pathsep.join([self.repo.plugin_bin, stale, base["PATH"]])
        self.assertOn(self.on(extra={"PATH": path, "AGENT_CITY_PLUGIN_ROOT": self.repo.plugin}))
        text = self.plist_text()
        self.assertNotIn(self.repo.plugin, text, "the running plugin's folder is in the login item")
        self.assertNotIn("plugins/cache", text, "a plugin cache path is in the login item")
        self.assertNotIn("AGENT_CITY_PLUGIN_ROOT", text)
        self.assertNotRegex(text, r"auto-pipeline/\d+\.\d+", "a version number is in the login item")
        kept = self.plist_data()["EnvironmentVariables"]["PATH"].split(os.pathsep)
        self.assertIn(self.repo.bin, kept, "the rest of the terminal's PATH is kept")
        self.assertIn("/usr/bin", kept)

    def test_environment_of_the_terminal(self):
        self.assertOn(self.on())
        env = self.plist_data().get("EnvironmentVariables", {})
        self.assertEqual(env.get("AGENT_CITY_HOME"), self.home)
        self.assertEqual(env.get("AGENT_CITY_DIR"), self.city)
        self.assertEqual(env.get("AGENT_CITY_PORT"), str(self.port))
        self.assertIn(self.repo.bin, env.get("PATH", "").split(os.pathsep),
                      "launchd's own PATH has no orca, python3 or claude: the terminal's PATH goes in")

    def test_environment_only_when_set(self):
        self.assertOn(self.on(unset=("AGENT_CITY_HOME", "AGENT_CITY_DIR", "AGENT_CITY_PORT")))
        data = self.plist_data()
        self.assertEqual(sorted(data.get("EnvironmentVariables", {})), ["PATH"])
        default = os.path.join(self.userhome, ".claude", "agent-city", "login-start.sh")
        self.assertEqual(data["ProgramArguments"], ["/bin/sh", default, "login-start", "run"])
        self.assertTrue(os.path.isfile(default))

    def test_launchctl_refuses_and_nothing_is_left(self):
        code, out, err = self.on(extra={"LAUNCHCTL_FAIL": "1"})
        self.assertEqual(code, 1, out + err)
        said = [l for l in (out + err).splitlines() if l.startswith("LOGIN START:")]
        self.assertTrue(said and "launchctl" in said[-1], out + err)
        self.assertNotIn("LOGIN START: on", out + err)
        self.assert_nothing_installed()
        self.assertEqual(login_lines(self.city_run("status").stdout), ["LOGIN START: off"])

    def test_a_wrong_word_changes_nothing(self):
        for words in (("login-start",), ("login-start", "maybe")):
            result = self.city_run(*words)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("LOGIN START: usage", result.stdout + result.stderr)
        self.assert_nothing_installed()
        self.assertEqual(self.calls(), [])

    def test_usage_lists_it(self):
        text = self.city_run("-h").stdout
        self.assertIn("login-start on", text)
        self.assertIn("login-start off", text)


class TestNeverTheRealMachine(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(BIN, "agent-city.sh")) as fh:
            self.text = fh.read()

    def test_launchctl_comes_from_path(self):
        self.assertIn("launchctl", self.text, "login-start is not written yet")
        self.assertNotRegex(self.text, r"/s?bin/launchctl", "launchctl by an absolute path cannot be faked by a test")

    def test_the_folder_comes_from_home(self):
        self.assertIn("$HOME/Library/LaunchAgents", self.text)

    def test_no_hook_installs_it(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json")) as fh:
            self.assertNotIn("login-start", fh.read(), "nothing is installed by a hook")


# ----------------------------------------------------------------------- off

class TestOff(LoginCase):
    def test_off_needs_no_terminal(self):
        self.assertOn(self.on())
        result = self.city_run("login-start", "off")
        self.assertOk(result)
        self.assertEqual(login_lines(result.stdout), ["LOGIN START: off"])
        self.assertFalse(os.path.exists(self.plist))
        self.assertFalse(os.path.exists(self.launcher))
        self.assertIn(["bootout", "gui/%d/%s" % (os.getuid(), LABEL)], self.calls())
        self.assertFalse(os.path.exists(self.ctl_state), "the login item is unloaded")

    def test_off_when_it_never_was_on(self):
        result = self.city_run("login-start", "off", cwd=self.outside)
        self.assertOk(result)
        self.assertEqual(login_lines(result.stdout), ["LOGIN START: off"])
        self.assert_nothing_installed()

    def test_off_touches_nothing_else(self):
        self.assertOk(self.join())
        self.mark()
        self.assertOn(self.on())
        other = os.path.join(self.agents, "com.example.other.plist")
        with open(other, "w") as fh:
            fh.write("<plist/>\n")
        self.assertOk(self.city_run("login-start", "off"))
        self.assertEqual(os.listdir(self.agents), ["com.example.other.plist"])
        self.assertEqual(rl.read_cloud(self.marker), [self.fake.host], "the cloud marker stays")
        self.assertTrue(os.path.exists(os.path.join(self.home, "joined-repos.txt")), "the joined list stays")
        self.assertTrue(os.path.exists(self.secret), "the repo stays joined")

    def test_on_again_after_off(self):
        self.assertOn(self.on())
        self.assertOk(self.city_run("login-start", "off"))
        self.assertOn(self.on())
        self.assertTrue(os.path.isfile(self.plist))


# -------------------------------------------------------------------- status

class TestStatus(LoginCase):
    def last_line(self, result):
        self.assertOk(result)
        self.assertEqual(len(login_lines(result.stdout)), 1, result.stdout)
        return [l.strip() for l in result.stdout.splitlines() if l.strip()][-1]

    def test_off_by_default(self):
        self.assertEqual(self.last_line(self.city_run("status")), "LOGIN START: off")
        self.assertEqual(self.last_line(self.city_run("status", cwd=self.outside)), "LOGIN START: off")
        self.assertOk(self.join())
        self.assertEqual(self.last_line(self.city_run("status")), "LOGIN START: off")
        self.assertEqual(self.last_line(self.city_run("status", cwd=self.outside)), "LOGIN START: off")

    def test_on(self):
        self.assertOk(self.join())
        self.assertOn(self.on())
        result = self.city_run("status")
        self.assertEqual(self.last_line(result), "LOGIN START: on")
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        self.assertLess(lines.index("CLOUD START: off"), lines.index("LOGIN START: on"),
                        "the LOGIN START line comes after the CLOUD START line")
        self.assertEqual(self.last_line(self.city_run("status", cwd=self.outside)), "LOGIN START: on")

    def test_off_again(self):
        self.assertOn(self.on())
        self.assertOk(self.city_run("login-start", "off"))
        self.assertEqual(self.last_line(self.city_run("status")), "LOGIN START: off")

    def test_status_never_calls_launchctl(self):
        self.assertOn(self.on())
        before = self.calls()
        self.city_run("status")
        self.city_run("status", cwd=self.outside)
        self.assertEqual(self.calls(), before, "status reads the file only")


# ------------------------------------------------------------- other systems

class TestOtherSystems(LoginCase):
    LINUX = {"FAKE_UNAME": "Linux"}

    def assert_mac_only(self, text):
        lines = [l for l in text.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1, "one plain line: %r" % text)
        self.assertIn(MAC_ONLY, lines[0])

    def test_on_in_a_terminal(self):
        code, out, err = self.on(extra=self.LINUX)
        self.assertEqual(code, 1, out + err)
        self.assert_mac_only(out + err)
        self.assert_nothing_installed()
        self.assertEqual(self.calls(), [], "launchctl is never called on another system")

    def test_on_without_a_terminal(self):
        result = self.city_run("login-start", "on", extra=self.LINUX)
        self.assertNotEqual(result.returncode, 0)
        self.assert_mac_only(result.stdout + result.stderr)
        self.assert_nothing_installed()
        self.assertEqual(self.calls(), [])

    def test_off(self):
        result = self.city_run("login-start", "off", extra=self.LINUX)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assert_mac_only(result.stdout + result.stderr)
        self.assert_nothing_installed()
        self.assertEqual(self.calls(), [])

    def test_status_says_off(self):
        result = self.city_run("status", extra=self.LINUX)
        self.assertOk(result)
        self.assertEqual(login_lines(result.stdout), ["LOGIN START: off"])
        self.assertEqual(self.calls(), [])


# ------------------------------------- the login item finds the newest plugin

class TestTheLoginItemFindsTheNewestPlugin(LoginCase):
    def ran(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ARG=[login-start]\nARG=[run]", result.stdout, "it runs `login-start run`")
        return re.findall(r"VERSION=(\S+)", result.stdout)

    def test_highest_version_at_run_time(self):
        self.version("0.9.0")
        self.version("0.10.0")
        self.assertOn(self.on())
        self.assertEqual(self.ran(self.run_login_item()), ["0.10.0"], "0.10.0 beats 0.9.0")

    def test_a_plugin_update_needs_no_new_on(self):
        self.version("0.18.0")
        self.assertOn(self.on())
        before = self.plist_text()
        self.assertEqual(self.ran(self.run_login_item()), ["0.18.0"])
        self.version("0.19.0")                                   # the plugin was updated
        __import__("shutil").rmtree(os.path.join(self.cache, "0.18.0"))   # and the old folder is gone
        self.assertEqual(self.ran(self.run_login_item()), ["0.19.0"], "no stale path: the new version runs")
        self.assertEqual(self.plist_text(), before, "the login item itself did not change")

    def test_no_plugin_installed_fails_quietly_enough(self):
        self.assertOn(self.on())
        result = self.run_login_item()
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(self.pid())


# ------------------------------------------------------------- login-start run

class TestRun(LoginCase):
    def test_marker_on_starts_the_server(self):
        self.assertOk(self.join())
        self.mark()
        self.run_verb()
        pid = self.pid()
        self.assertTrue(pid, "joined and the cloud is on: the city server is up when login-start run returns")
        args = args_of(pid)
        self.assertIn("serve", args)
        self.assertIn("--joined-list %s" % os.path.join(self.home, "joined-repos.txt"), args)
        self.assertIn("--port %d" % self.port, args)
        self.assertFalse(os.path.exists(self.open_log), "no browser is opened")

    def test_the_idle_rule_is_the_repos_own(self):
        self.repo.set_conf("city_idle_min", "7")
        self.assertOk(self.join())
        self.mark()
        self.run_verb()
        pid = self.pid()
        self.assertTrue(pid)
        self.assertIn("--idle-min 7", args_of(pid), "today's autostart from that repo: its agent.conf")

    def test_marker_on_needs_no_relay(self):
        self.assertOk(self.join())
        self.mark()
        self.fake.mode = "error"            # at a login the network is often not up yet
        before = len(self.fake.requests)
        self.run_verb()
        self.assertTrue(self.pid(), "the marker says on: no probe is needed")
        self.assertEqual(len(self.fake.requests), before)

    def test_no_marker_probes_once_and_starts(self):
        self.assertOk(self.join())
        self.fake.city = True
        if os.path.exists(self.marker):
            os.remove(self.marker)
        self.run_verb()
        self.assertTrue(self.pid(), "the relay says the cloud is on: start")
        self.assertEqual(rl.read_cloud(self.marker), [self.fake.host])

    def test_cloud_off_does_nothing(self):
        self.assertOk(self.join())
        before = len(self.fake.requests)
        self.run_verb()
        self.assert_never_starts()
        self.assertEqual(len(self.fake.requests) - before, 1, "one quiet question to the relay, no more")
        self.assertEqual(rl.read_cloud(self.marker), [])

    def test_relay_unreachable_no_start_quiet_exit(self):
        self.assertOk(self.join())
        self.fake.mode = "error"
        self.run_verb()
        self.assert_never_starts()

    def test_never_joined_does_nothing_at_all(self):
        self.fake.city = True
        self.mark()                         # a marker alone never starts anything
        self.run_verb()
        self.assert_never_starts()
        self.assertEqual(self.fake.requests, [])

    def test_cloud_session_does_nothing(self):
        self.assertOk(self.join())
        self.mark()
        before = len(self.fake.requests)
        self.run_verb(extra={"CLAUDE_CODE_REMOTE": "true"})
        self.assert_never_starts()
        self.assertEqual(len(self.fake.requests), before)

    def test_already_running_stays_the_same_server(self):
        self.assertOk(self.join())
        self.mark()
        self.run_verb()
        pid = self.pid()
        self.assertTrue(pid)
        self.run_verb()
        self.assertEqual(self.pid(), pid)
        others = subprocess.run(["pgrep", "-f", "serve --dir %s" % self.city],
                                capture_output=True, text=True).stdout.split()
        self.assertEqual(others, [str(pid)], "exactly one server for this city dir")

    def test_it_walks_the_joined_list(self):
        self.assertOk(self.join())
        self.mark()
        dead = make_repo(self.repo.base, "second", origin="git@github.com:Acme/Second.git")
        join_by_hand(dead, "http://127.0.0.1:%d" % free_port())      # nobody answers there, no marker
        left = make_repo(self.repo.base, "left", origin="git@github.com:Acme/Left.git")   # listed, not joined
        gone = os.path.join(self.repo.base, "gone")                   # listed, folder deleted
        with open(os.path.join(self.home, "joined-repos.txt"), "w") as fh:
            fh.write("%s\n%s\n%s\n%s\n" % (gone, left, dead, self.repo.dir))
        self.run_verb()
        pid = self.pid()
        self.assertTrue(pid, "the third repo's relay has the cloud on: it must start from there")
        self.assertIn("--start-dir %s" % self.repo.dir, args_of(pid))

    def test_each_relay_host_is_asked_once(self):
        self.assertOk(self.join())
        twin = make_repo(self.repo.base, "twin", origin="git@github.com:Acme/Twin.git")
        join_by_hand(twin, self.fake.url)
        with open(os.path.join(self.home, "joined-repos.txt"), "a") as fh:
            fh.write("%s\n" % twin)
        before = len(self.fake.requests)
        self.run_verb()
        self.assert_never_starts()
        self.assertEqual(len(self.fake.requests) - before, 1, "two repos on one relay: one question")

    def test_key_never_shows(self):
        self.assertOk(self.join())
        self.fake.city = True
        result = self.run_verb()
        self.assert_no_key(result)
        pid = self.pid()
        self.assertNotIn(FAKE_KEY, args_of(pid) if pid else "")

    def test_the_session_start_autostart_is_unchanged(self):
        self.assertOk(self.join())
        self.mark()
        self.autostart(cwd=self.outside)    # outside a repo it still does nothing
        self.assert_never_starts(wait=2.0)


class TestTheWholeWay(LoginCase):
    """on in the owner's terminal, then the login item as launchd runs it: the city is up."""

    def install_this_plugin(self, ver="9.9.9"):
        os.makedirs(self.cache)
        os.symlink(self.repo.plugin, os.path.join(self.cache, ver))

    def test_a_login_brings_the_city_up(self):
        self.assertOk(self.join())
        self.mark()
        self.install_this_plugin()
        self.assertOn(self.on(cwd=self.outside))
        result = self.run_login_item(extra={"AGENT_FAKE_RAM": "10", "AGENT_FAKE_CPU": "10"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((result.stdout + result.stderr).strip(), "")
        pid = self.pid()
        self.assertTrue(pid, "after a login the city server runs by itself")
        self.assertIn("--joined-list %s" % os.path.join(self.home, "joined-repos.txt"), args_of(pid))
        self.assertFalse(os.path.exists(self.open_log), "no browser is opened")

    def test_a_machine_with_the_cloud_off_does_nothing(self):
        self.assertOk(self.join())              # joined, the relay says the cloud is off
        self.install_this_plugin()
        self.assertOn(self.on())
        result = self.run_login_item(extra={"AGENT_FAKE_RAM": "10", "AGENT_FAKE_CPU": "10"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_never_starts()


# ---------------------------------------------------------------------- docs

class TestSetupSection(unittest.TestCase):
    def setUp(self):
        with open(SETUP) as fh:
            self.text = fh.read()
        self.sections = re.findall(r"(?ms)^## (\d+)\. ([^\n]+)\n(.*?)(?=^## |\Z)", self.text)

    def section(self, number):
        hits = [(title, body) for n, title, body in self.sections if int(n) == number]
        self.assertTrue(hits, "no section %d" % number)
        return hits[0]

    def test_one_more_section(self):
        nums = [int(n) for n, _, _ in self.sections]
        self.assertEqual(nums, list(range(1, 21)), "sections 1 to 20, 20 is new")
        title, _ = self.section(20)
        self.assertRegex(title, r"(?i)log ?in")
        self.assertNotRegex(title, r"(?i)talk|cloud page|deploy|starting agents",
                            "older tests find their sections by those words")

    def test_on_check_off(self):
        _, body = self.section(20)
        self.assertIn("login-start on", body)
        self.assertIn("login-start off", body)
        self.assertIn("LOGIN START: on", body)
        self.assertIn("LOGIN START: off", body)
        self.assertIn("You should see", body)
        self.assertRegex(body, r"agent-city\.sh\" status", "check it with the status command")
        self.assertEqual(len(re.findall(r"ls -d ~/\.claude/plugins/cache/auto-pipeline/auto-pipeline/\*/ \| sort -V \| tail -1",
                                        body)), 3, "on, status and off: the same newest-plugin command as the other sections")

    def test_plain_words(self):
        _, body = self.section(20)
        self.assertRegex(body, r"(?i)small city program")
        self.assertRegex(body, r"(?is)log in.{0,200}cloud page.{0,200}restart|restart.{0,200}cloud page",
                         "it lets the small city program start when you log in, so the cloud page sees this computer after a restart")
        self.assertRegex(body, r"(?i)optional")
        self.assertRegex(body, r"(?i)off by default|stays off")
        self.assertRegex(body, r"(?i)your own terminal")
        self.assertRegex(body, r"(?i)refuses when an agent runs it")
        self.assertRegex(body, r"(?i)only (on|for) (a )?mac|macOS only|Mac only")
        self.assertRegex(body, r"(?i)section 1[14]", "it only does something while the cloud page is on")
        self.assertRegex(body, r"(?i)log out|restart the computer", "how to check it for real")
        self.assertRegex(body, r"(?i)plugin update", "an update needs no new on")

    def test_the_starting_section_points_here(self):
        _, body = self.section(18)
        self.assertRegex(body, r"(?i)section 20")

    def test_no_real_address_or_key(self):
        for word in ("maverickleeweilin88", "gmail.com", "/Users/maverick"):
            self.assertNotIn(word, self.text)


class TestRequirementLines(unittest.TestCase):
    def setUp(self):
        with open(REQ) as fh:
            self.text = fh.read()
        self.cloud = self.text[self.text.index("## Cloud page"):self.text.index("## Relay setup")]

    def test_login_start_rules(self):
        self.assertIn("### Login start", self.cloud)
        body = self.cloud[self.cloud.index("### Login start"):]
        for word in ("2026-10-02", "login-start on", "login-start off", "LOGIN START: on", "LOGIN START: off",
                     "LaunchAgent", LABEL, "login-start.sh", "agent-city-shim", "RunAtLoad", "AbandonProcessGroup",
                     "PATH", "joined-repos.txt", "macOS only", "launchctl"):
            self.assertIn(word, body, word)
        self.assertRegex(body, r"(?i)off by default")
        self.assertRegex(body, r"(?i)refuses without a terminal")
        self.assertRegex(body, r"(?i)never .{0,60}(a plugin update|a hook|an agent)",
                         "nothing is installed by a plugin update, a hook or an agent")
        self.assertRegex(body, r"(?i)versioned", "the login item never holds a versioned plugin path")
        self.assertRegex(body, r"(?i)each relay host once")
        self.assertLess(len(body.splitlines()), 14, "terse")

    def test_the_restart_line_is_replaced_not_left(self):
        self.assertNotIn("After a restart of the computer the server comes back with the next session start "
                         "(or `agent-city start`).", self.text)
        line = [l for l in self.cloud.splitlines() if l.startswith("- Reachable with nobody there")]
        self.assertEqual(len(line), 1)
        self.assertRegex(line[0], r"(?i)login start")

    def test_the_limits_line_stays(self):
        self.assertIn("## Limits", self.text)
        self.assertIn("stops itself after `city_idle_min`", self.text)


if __name__ == "__main__":
    unittest.main()
