"""Failing tests: `agent-city` from any folder (requirements/city.md, "Anywhere").

WHY. In the owner's own plain terminal (not a Claude session) the plugin's
bin/ is not on PATH, so `agent-city.sh` is "command not found" there. The
owner wants `agent-city start|status|stop|join|leave|...` to work from any
folder, even outside a repo, as an all-machine monitor.

CONTRACT

  bin/agent-city-shim   the small command copied to ~/.local/bin/agent-city
    - An executable shell script with the marker line
      "# auto-pipeline agent-city shim".
    - Every run: AGENT_CITY_PLUGIN_ROOT set -> that plugin folder (for trying
      a checkout before it is released); it must hold bin/agent-city.sh,
      else a short stderr line naming the folder and exit 1.
      Unset -> the highest version folder under
      $HOME/.claude/plugins/cache/auto-pipeline/auto-pipeline/ whose name is
      a plain version (digits and dots only) and that holds
      bin/agent-city.sh. Sorted by version, never by name (0.10.0 > 0.9.0).
      Never a hard-coded version.
    - Runs that bin/agent-city.sh with bash, same args (spaces, empty args
      and glob characters untouched), in the caller's folder, and exits
      with its exit code.
    - Nothing installed: a stderr line with "not installed", exit 1.

  bin/agent-city.sh install-shim
    - Copies bin/agent-city-shim to $HOME/.local/bin/agent-city, mode 0755,
      folder made when missing, no temp file left. Prints
      "SHIM: installed <path>". Run again: same bytes, exit 0. An older
      shim of ours (marker line present) is replaced.
    - A file there without the marker line, a symlink or a folder is never
      touched: exit 1, message with "not ours".
    - $HOME/.local/bin not on PATH: a hint line naming ".local/bin" and
      PATH. On PATH: no line mentions PATH.
    - Works from any folder (it is the manual one-line install too).
  bin/agent-city.sh remove-shim
    - Ours -> removed, "SHIM: removed". Not ours -> left, exit 1,
      "not ours". Missing -> exit 0, "not installed".
  The usage text lists install-shim and remove-shim.

  bin/agent-city.sh, started outside a repo (cwd not inside a git work tree)
    - Plugin defaults only (bin/agent.conf.default): an agent.conf lying in
      that folder is never read.
    - start/demo pass --lang: AGENT_CITY_LANG when it is "en" or "zh", else
      "zh" (agent.conf.default says en; the city's own default is zh).
    - start/demo pass --joined-list $AGENT_CITY_HOME/joined-repos.txt: the
      city then syncs every team relay this machine joined, with no local
      line needed.
    - status: the CITY line as today, then one line per listed repo that
      still has its folder and join file: "TEAM: joined <host> (<repo>)";
      none -> "TEAM: not joined". Never the key.
    - join and leave work here (city-device-join, 2026-10-05: once per
      computer, tests/test_agent_city_device_join.py). Only a cloud session
      (CLAUDE_CODE_REMOTE set) keeps the old rule: they refuse (exit 1, a
      message with "repo"), nothing asked, nothing sent, the list untouched.
  bin/agent-city.sh start/demo, anywhere (inside or outside a repo)
    - AGENT_CITY_PORT, a whole number 1024-65535, wins over city_port
      (agent.conf or the plugin default). Any other non-empty value: a
      message naming AGENT_CITY_PORT, exit 1, nothing started. Empty or
      unset: as before.
    - The port is held by another program: exit 1 and a message naming
      the port, "already in use" and AGENT_CITY_PORT (never the bare
      "CITY: failed to start"). No city left running.
    - A city already runs in this city dir: exit 0, its URL line as today,
      plus a line with "already running" telling to stop it first to start
      it again from here (its own settings stay until then).
  Inside a repo: as today (agent.conf, --lang from it, no --joined-list,
  one TEAM line for this repo), plus
    - join adds the main repo root to $AGENT_CITY_HOME/joined-repos.txt
      after the relay said ok (once, never the key);
    - leave (a cloud session: per repo) removes this repo's line (other
      lines and comments kept), also when the join file was already gone;
      on a computer leave empties the list.

  bin/agent_city_relay.py
    read_joined_list(path)       absolute paths in file order, realpath
                                 duplicates dropped; blank, "#" comment and
                                 relative lines skipped; missing file -> []
    add_joined(path, repo)       adds realpath(repo) once; makes the folder;
                                 keeps every other line and comment;
                                 written atomically (tmp + replace)
    remove_joined(path, repo)    drops the lines whose realpath is repo's;
                                 keeps the rest; missing file -> no error
    RelayHub(..., joined_list=PATH)
      tick() also syncs every listed repo whose folder and join file are
      there and whose origin is shared, with no offer() needed; the list is
      re-read at most every join_ttl seconds. Gone or unjoined repos are
      skipped quietly. A local line of a listed repo joins the same team.
      repo_for(rid) knows a listed repo. Without joined_list: as today.

  bin/agent_city.py serve --joined-list PATH  -> RelayHub(joined_list=PATH)

  Docs: requirements/city.md "## Anywhere"; skills/init/SKILL.md asks for a
  yes, then runs install-shim; skills/city/SKILL.md names `agent-city start`
  for a plain terminal and install-shim; README.md lists agent-city-shim.

Never the real ~/.local/bin, ~/.claude or ~/.cache (HOME, AGENT_CITY_DIR and
AGENT_CITY_HOME are temp dirs), never a real key or relay (FakeRelay).

Run: python3 -m unittest tests.test_agent_city_anywhere
"""

import os
import shutil
import signal
import socket
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

from scripthelp import ScriptCase  # noqa: E402


def wait_for(check, timeout=8.0, step=0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(step)
    return check()


SHIM = os.path.join(BIN, "agent-city-shim")
MARKER = "# auto-pipeline agent-city shim"
CACHE_PARTS = (".claude", "plugins", "cache", "auto-pipeline", "auto-pipeline")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def server_pid(city_dir):
    try:
        with open(os.path.join(city_dir, "on")) as fh:
            return int(fh.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def server_args(city_dir):
    pid = server_pid(city_dir)
    if pid is None:
        return ""
    return wait_for(lambda: subprocess.run(["ps", "-o", "args=", "-p", str(pid)],
                                           capture_output=True, text=True).stdout.strip())


def stop_server(city_dir):
    pid = server_pid(city_dir)
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    wait_for(lambda: not _alive(pid), timeout=5)


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_text(path):
    with open(path) as fh:
        return fh.read()


def write_text(path, text):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


STUB = """#!/usr/bin/env bash
printf 'VERSION=%s\\n' "{ver}"
for a in "$@"; do printf 'ARG=[%s]\\n' "$a"; done
printf 'PWD=%s\\n' "$(pwd -P)"
exit {code}
"""


# --------------------------------------------------------------------- shim

class ShimCase(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="city_anywhere_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.home = os.path.join(self.base, "home")
        self.plain = os.path.join(self.base, "plain")
        os.makedirs(self.home)
        os.makedirs(self.plain)
        self.cache = os.path.join(self.home, *CACHE_PARTS)

    def stub(self, folder, ver, code=0):
        path = os.path.join(folder, "bin", "agent-city.sh")
        write_text(path, STUB.format(ver=ver, code=code))
        os.chmod(path, 0o755)
        return path

    def version(self, ver, code=0):
        return self.stub(os.path.join(self.cache, ver), ver, code)

    def run_shim(self, *args, extra=None):
        self.assertTrue(os.path.isfile(SHIM), "bin/agent-city-shim does not exist yet. Write it.")
        self.assertTrue(os.access(SHIM, os.X_OK), "bin/agent-city-shim is not executable")
        env = dict(os.environ, HOME=self.home)
        env.pop("AGENT_CITY_PLUGIN_ROOT", None)
        env.update(extra or {})
        return subprocess.run([SHIM] + list(args), cwd=self.plain, env=env,
                              capture_output=True, text=True, timeout=30)

    def assertRan(self, result, ver):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("VERSION=%s\n" % ver, result.stdout)


class TestShim(ShimCase):
    def test_the_file_is_executable_with_the_marker(self):
        self.assertTrue(os.path.isfile(SHIM), "bin/agent-city-shim does not exist yet. Write it.")
        self.assertTrue(os.access(SHIM, os.X_OK))
        text = read_text(SHIM)
        self.assertTrue(text.startswith("#!"))
        self.assertIn(MARKER + "\n", text)
        self.assertNotRegex(text, r"auto-pipeline/\d+\.\d+", "never a hard-coded version")

    def test_highest_version_not_name_order(self):
        for ver in ("0.2.0", "0.9.0", "0.10.0", "0.9.10"):
            self.version(ver)
        self.assertRan(self.run_shim("status"), "0.10.0")

    def test_major_version_wins(self):
        for ver in ("0.10.0", "1.0.0", "0.99.0"):
            self.version(ver)
        self.assertRan(self.run_shim("status"), "1.0.0")

    def test_skips_folders_without_the_script_and_names_that_are_not_versions(self):
        self.version("0.9.0")
        os.makedirs(os.path.join(self.cache, "0.10.0"))       # half installed: no bin/
        self.version("zz-latest")                             # not a version name
        self.version("0.11.0-rc1")                            # not a plain version
        self.assertRan(self.run_shim("status"), "0.9.0")

    def test_args_unchanged_in_the_callers_folder(self):
        self.version("0.9.0")
        result = self.run_shim("answer", "Q1", "two words", "", "a*b")
        self.assertRan(result, "0.9.0")
        self.assertIn("ARG=[answer]\nARG=[Q1]\nARG=[two words]\nARG=[]\nARG=[a*b]\n", result.stdout)
        self.assertIn("PWD=%s\n" % self.plain, result.stdout)

    def test_exit_code_passes_through(self):
        self.version("0.9.0", code=3)
        self.assertEqual(self.run_shim("status").returncode, 3)

    def test_nothing_installed(self):
        result = self.run_shim("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not installed", result.stderr)
        os.makedirs(os.path.join(self.cache, "junk"))
        result = self.run_shim("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not installed", result.stderr)

    def test_a_version_installed_later_is_used_at_once(self):
        self.version("0.9.0")
        self.assertRan(self.run_shim("status"), "0.9.0")
        self.version("0.10.0")
        self.assertRan(self.run_shim("status"), "0.10.0")

    def test_plugin_root_override(self):
        self.version("0.9.0")
        dev = os.path.join(self.base, "checkout")
        self.stub(dev, "checkout")
        self.assertRan(self.run_shim("status", extra={"AGENT_CITY_PLUGIN_ROOT": dev}), "checkout")

    def test_plugin_root_override_without_the_script(self):
        self.version("0.9.0")
        empty = os.path.join(self.base, "empty")
        os.makedirs(empty)
        result = self.run_shim("status", extra={"AGENT_CITY_PLUGIN_ROOT": empty})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(empty, result.stderr)
        self.assertNotIn("VERSION=", result.stdout)


# ------------------------------------------------------ install / remove shim

class InstallCase(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.home = self.repo.fake_home()
        self.target_dir = os.path.join(self.home, ".local", "bin")
        self.target = os.path.join(self.target_dir, "agent-city")
        self.plain = os.path.join(self.repo.base, "plain")
        os.makedirs(self.plain)

    def city_run(self, *args, extra=None, cwd=None):
        env = {"AGENT_CITY_DIR": os.path.join(self.repo.base, "city"),
               "AGENT_CITY_HOME": os.path.join(self.repo.base, "cityhome")}
        env.update(extra or {})
        return self.repo.run("agent-city.sh", *args, env=env, cwd=cwd, timeout=30)

    def shim_text(self):
        path = self.repo.plugin_path("bin", "agent-city-shim")
        self.assertTrue(os.path.exists(path), "bin/agent-city-shim is missing (or not in COPY_BIN)")
        return read_text(path)

    def out(self, result):
        return result.stdout + result.stderr


class TestInstallShim(InstallCase):
    def test_install_writes_the_shim(self):
        result = self.city_run("install-shim")
        self.assertOk(result)
        self.assertIn("SHIM: installed " + self.target, result.stdout)
        self.assertEqual(read_text(self.target), self.shim_text())
        self.assertEqual(stat.S_IMODE(os.stat(self.target).st_mode), 0o755)

    def test_install_twice_is_fine(self):
        self.assertOk(self.city_run("install-shim"))
        self.assertOk(self.city_run("install-shim"))
        self.assertEqual(read_text(self.target), self.shim_text())
        self.assertEqual(os.listdir(self.target_dir), ["agent-city"], "no temp file left")

    def test_install_replaces_an_older_shim_of_ours(self):
        write_text(self.target, "#!/bin/sh\n%s\necho old\n" % MARKER)
        self.assertOk(self.city_run("install-shim"))
        self.assertEqual(read_text(self.target), self.shim_text())

    def test_install_from_a_plain_folder(self):
        self.assertOk(self.city_run("install-shim", cwd=self.plain))
        self.assertEqual(read_text(self.target), self.shim_text())

    def test_never_touches_a_file_that_is_not_ours(self):
        mine = "#!/bin/sh\necho mine\n"
        write_text(self.target, mine)
        result = self.city_run("install-shim")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not ours", self.out(result))
        self.assertEqual(read_text(self.target), mine)

    def test_never_touches_a_symlink(self):
        os.makedirs(self.target_dir)
        pointee = self.repo.plugin_path("bin", "agent-city-shim")
        os.symlink(pointee, self.target)
        result = self.city_run("install-shim")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not ours", self.out(result))
        self.assertTrue(os.path.islink(self.target))
        self.assertEqual(os.readlink(self.target), pointee)

    def test_never_touches_a_folder(self):
        os.makedirs(self.target)
        result = self.city_run("install-shim")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not ours", self.out(result))
        self.assertTrue(os.path.isdir(self.target))

    def test_hint_when_the_folder_is_not_on_path(self):
        result = self.city_run("install-shim")
        self.assertOk(result)
        self.assertIn(".local/bin", result.stdout)
        self.assertIn("PATH", result.stdout)

    def test_no_hint_when_the_folder_is_on_path(self):
        path = self.target_dir + os.pathsep + self.repo._path()
        result = self.city_run("install-shim", extra={"PATH": path})
        self.assertOk(result)
        self.assertNotIn("PATH", result.stdout)

    def test_usage_lists_install_and_remove(self):
        result = self.city_run("-h")
        self.assertOk(result)
        self.assertIn("install-shim", result.stdout)
        self.assertIn("remove-shim", result.stdout)


class TestRemoveShim(InstallCase):
    def test_remove_ours(self):
        self.assertOk(self.city_run("install-shim"))
        result = self.city_run("remove-shim")
        self.assertOk(result)
        self.assertIn("SHIM: removed", result.stdout)
        self.assertFalse(os.path.lexists(self.target))

    def test_remove_never_touches_a_file_that_is_not_ours(self):
        mine = "#!/bin/sh\necho mine\n"
        write_text(self.target, mine)
        result = self.city_run("remove-shim")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not ours", self.out(result))
        self.assertEqual(read_text(self.target), mine)

    def test_remove_when_missing(self):
        result = self.city_run("remove-shim")
        self.assertOk(result)
        self.assertIn("not installed", result.stdout)


# ------------------------------------------------------------ outside a repo

class OutsideCase(ScriptCase):
    script = "agent-city.sh"

    def setUp(self):
        super().setUp()
        self.city = os.path.join(self.repo.base, "city")
        self.cityhome = os.path.join(self.repo.base, "cityhome")
        self.plain = os.path.join(self.repo.base, "plain")
        os.makedirs(self.plain)
        self.port = free_port()
        self.set_default("city_port", str(self.port))
        self.addCleanup(stop_server, self.city)

    def set_default(self, key, value):
        """Change the plugin copy's own bin/agent.conf.default."""
        path = self.repo.plugin_path("bin", "agent.conf.default")
        rows = [l for l in read_text(path).splitlines() if l.split("=", 1)[0] != key]
        rows.append("%s=%s" % (key, value))
        write_text(path, "\n".join(rows) + "\n")

    def city_env(self, extra=None):
        env = {"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.cityhome,
               "AGENT_CITY_LANG": ""}
        env.update(extra or {})
        return env

    def city_run(self, *args, cwd=None, extra=None, stdin=None):
        return self.repo.run("agent-city.sh", *args, env=self.city_env(extra),
                             cwd=cwd or self.plain, stdin=stdin, timeout=30)

class TestStartOutsideARepo(OutsideCase):
    def test_plugin_defaults_and_zh(self):
        result = self.city_run("start")
        self.assertOk(result)
        self.assertIn("CITY: http://127.0.0.1:%d" % self.port, result.stdout)
        args = server_args(self.city)
        self.assertIn("--port %d" % self.port, args)
        self.assertIn("--lang zh", args)

    def test_an_agent_conf_in_a_plain_folder_is_never_read(self):
        write_text(os.path.join(self.plain, "agent.conf"),
                   "city_port=%d\nlanguage=en\n" % free_port())
        self.assertOk(self.city_run("start"))
        args = server_args(self.city)
        self.assertIn("--port %d" % self.port, args)
        self.assertIn("--lang zh", args)

    def test_agent_city_lang_en(self):
        self.assertOk(self.city_run("start", extra={"AGENT_CITY_LANG": "en"}))
        self.assertIn("--lang en", server_args(self.city))

    def test_agent_city_lang_unknown_is_zh(self):
        self.assertOk(self.city_run("start", extra={"AGENT_CITY_LANG": "fr"}))
        self.assertIn("--lang zh", server_args(self.city))

    def test_demo_is_the_same(self):
        result = self.city_run("demo")
        self.assertOk(result)
        self.assertIn("CITY: http://127.0.0.1:%d/#demo" % self.port, result.stdout)
        args = server_args(self.city)
        self.assertIn("--lang zh", args)

    def test_inside_a_repo_is_as_today(self):
        self.repo.set_conf("city_port", str(self.port))
        self.repo.set_conf("language", "en")
        self.assertOk(self.city_run("start", cwd=self.repo.dir, extra={"AGENT_CITY_LANG": "zh"}))
        args = server_args(self.city)
        self.assertIn("--lang en", args)

class TestPort(OutsideCase):
    def test_agent_city_port_outside_a_repo(self):
        port = free_port()
        result = self.city_run("start", extra={"AGENT_CITY_PORT": str(port)})
        self.assertOk(result)
        self.assertIn("CITY: http://127.0.0.1:%d" % port, result.stdout)
        self.assertIn("--port %d" % port, server_args(self.city))

    def test_agent_city_port_wins_over_agent_conf_inside_a_repo(self):
        port = free_port()
        self.repo.set_conf("city_port", str(free_port()))
        result = self.city_run("start", cwd=self.repo.dir, extra={"AGENT_CITY_PORT": str(port)})
        self.assertOk(result)
        self.assertIn("--port %d" % port, server_args(self.city))

    def test_empty_agent_city_port_is_unset(self):
        self.assertOk(self.city_run("start", extra={"AGENT_CITY_PORT": ""}))
        self.assertIn("--port %d" % self.port, server_args(self.city))

    def test_bad_agent_city_port(self):
        for bad in ("abc", "80", "70000", "47 77", "-1"):
            with self.subTest(value=bad):
                result = self.city_run("start", extra={"AGENT_CITY_PORT": bad})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("AGENT_CITY_PORT", result.stdout + result.stderr)
                self.assertIsNone(server_pid(self.city), "nothing may be started")

    def test_port_held_by_another_program(self):
        busy = socket.socket()
        busy.bind(("127.0.0.1", self.port))
        busy.listen(1)
        self.addCleanup(busy.close)
        result = self.city_run("start")
        out = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already in use", out)
        self.assertIn(str(self.port), out)
        self.assertIn("AGENT_CITY_PORT", out)
        pid = server_pid(self.city)
        self.assertFalse(pid is not None and _alive(pid), "no city may be left running")

    def test_a_city_already_running_says_so(self):
        self.assertOk(self.city_run("start"))
        again = self.city_run("start")
        self.assertOk(again)
        self.assertIn("CITY: http://127.0.0.1:%d" % self.port, again.stdout)
        self.assertIn("already running", again.stdout)
        self.assertIn("stop", again.stdout.split("already running", 1)[1])


class TestStatusOutsideARepo(OutsideCase):
    def test_not_running(self):
        result = self.city_run("status")
        self.assertOk(result)
        self.assertIn("CITY: not running", result.stdout)
        self.assertEqual(result.stdout.strip().splitlines(), ["CITY: not running"])

    def test_running_city(self):
        self.assertOk(self.city_run("start"))
        result = self.city_run("status")
        self.assertIn("CITY: running http://127.0.0.1:%d" % self.port, result.stdout)


class TestShimRunsTheRealCity(OutsideCase):
    def test_from_a_plain_folder(self):
        home = self.repo.fake_home()
        cache = os.path.join(home, *CACHE_PARTS)
        shutil.copytree(self.repo.plugin, os.path.join(cache, "0.99.0"))
        old = os.path.join(cache, "0.9.0", "bin", "agent-city.sh")
        write_text(old, STUB.format(ver="0.9.0", code=0))
        self.assertTrue(os.path.isfile(SHIM), "bin/agent-city-shim does not exist yet. Write it.")
        env = self.repo._env(self.city_env({"HOME": home}))
        env.pop("AGENT_CITY_PLUGIN_ROOT", None)

        def shim(*args):
            return subprocess.run([SHIM] + list(args), cwd=self.plain, env=env,
                                  capture_output=True, text=True, timeout=30)

        status = shim("status")
        self.assertOk(status)
        self.assertNotIn("VERSION=", status.stdout)
        self.assertIn("CITY: not running", status.stdout)
        start = shim("start")
        self.assertOk(start)
        self.assertIn("CITY: http://127.0.0.1:%d" % self.port, start.stdout)
        self.assertIn("--lang zh", server_args(self.city))
        self.assertIn("CITY: running", shim("status").stdout)
        self.assertOk(shim("stop"))
        self.assertIn("CITY: not running", shim("status").stdout)


# ------------------------------------------------------------- serve + docs

class TestDocs(unittest.TestCase):
    def text(self, *parts):
        return read_text(os.path.join(ROOT, *parts))

    def test_requirement(self):
        text = self.text("requirements", "city.md")
        self.assertIn("## Anywhere", text)
        section = text[text.index("## Anywhere"):]
        section = section[:section.index("\n## ", 1)] if "\n## " in section[1:] else section
        for word in ("~/.local/bin/agent-city", "install-shim",
                     "AGENT_CITY_LANG", "AGENT_CITY_PLUGIN_ROOT"):
            self.assertIn(word, section)

    def test_init_skill_asks_then_installs(self):
        text = self.text("skills", "init", "SKILL.md")
        self.assertIn("install-shim", text)
        self.assertIn("yes", text.lower())

    def test_city_skill_names_the_plain_terminal_command(self):
        text = self.text("skills", "city", "SKILL.md")
        self.assertIn("install-shim", text)
        self.assertIn("`agent-city start`", text)

    def test_readme_lists_the_shim(self):
        self.assertIn("bin/agent-city-shim", self.text("README.md"))


if __name__ == "__main__":
    unittest.main()
