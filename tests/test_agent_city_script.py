"""Tests of agent-city-script, one class per feature."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import os  # noqa: E402
import shutil  # noqa: E402
import signal  # noqa: E402
import socket  # noqa: E402
import stat  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import unittest  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402
import re  # noqa: E402
from scripthelp import ScriptRepo  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))


ROOT = os.path.dirname(HERE)


BIN = os.path.join(ROOT, "bin")


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
        """settings-configure: the settings are user level (Configure), inside a repo or not."""
        self.repo.set_conf(key, value)

    def city_env(self, extra=None):
        env = {"AGENT_CITY_DIR": self.city, "AGENT_CITY_HOME": self.cityhome,
               "AGENT_CITY_LANG": ""}
        env.update(extra or {})
        return env

    def city_run(self, *args, cwd=None, extra=None, stdin=None):
        return self.repo.run("agent-city.sh", *args, env=self.city_env(extra),
                             cwd=cwd or self.plain, stdin=stdin, timeout=30)


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
        self.set_default("city_port", str(self.port))   # Configure of the fake home
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
        self.assertIn("--lang en", server_args(self.city))
        self.assertIn("CITY: running", shim("status").stdout)
        self.assertOk(shim("stop"))
        self.assertIn("CITY: not running", shim("status").stdout)


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
        self.assertIn("bin/agent-city-shim", self.text("rules", "map.md"))   # md-slim-principles: the map moved to rules/map.md


class TestCityScriptWorld(unittest.TestCase):
    def test_start_passes_the_world_file(self):
        with open(os.path.join(BIN, "agent-city.sh")) as fh:
            text = fh.read()
        self.assertTrue(re.search(r'--world "\$CITY_HOME/world\.json"', text),
                        'agent-city.sh start must pass --world "$CITY_HOME/world.json"')


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


class TestF8ShortCityCommand(unittest.TestCase):
    def setUp(self):
        self.readme = read("rules", "map.md")   # md-slim-principles: the map moved to rules/map.md

    def test_readme_uses_the_short_command(self):
        self.assertIsNone(re.search(r"\./bin/agent-city\.sh [a-z]", self.readme))
        self.assertIsNone(re.search(r"(?m)^\s*\./agent-city\.sh [a-z]", self.readme))
        self.assertRegex(self.readme, r"(?m)^agent-city start\b")

    def test_readme_says_once_how_to_get_it(self):
        lines = [l for l in self.readme.splitlines() if "agent-city.sh install-shim" in l]
        self.assertEqual(len(lines), 1, lines)
        self.assertRegex(lines[0], r"(?i)once|one time")

    def test_readme_keeps_the_bin_list(self):
        for row in ("  bin/agent-city.sh       starts/stops the agent city visualiser",
                    "  bin/agent-city-shim     the ~/.local/bin/agent-city command",
                    "  bin/agent-city-hook.sh  hook that feeds the city"):
            with self.subTest(row=row):
                self.assertIn(row, self.readme)

    def help(self):
        repo = ScriptRepo()
        self.addCleanup(repo.cleanup)
        result = repo.run("agent-city.sh", "-h")
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_help_uses_the_short_command(self):
        out = self.help()
        self.assertIsNone(re.search(r"(?m)^\s*\./agent-city\.sh ", out), out)
        for verb in ("start", "stop", "status", "demo"):
            with self.subTest(verb=verb):
                self.assertRegex(out, r"(?m)^\s*agent-city %s\b" % re.escape(verb))

    def test_help_says_once_how_to_get_it(self):
        out = self.help()
        lines = [l for l in out.splitlines() if "agent-city.sh install-shim" in l]
        self.assertTrue(lines, out)
        self.assertRegex(" ".join(lines), r"(?i)once|one time|first")
