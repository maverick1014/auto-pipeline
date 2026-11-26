"""tests/citydesks_demo.py, the click path helper of city-agents-at-desks, never touches a real folder (PR REVIEW
2026-11-26, blocker: `stop --base X` deleted any folder, `start` let designs land in ~/.claude/agent-city/floors).

Every test runs the helper with HOME set to a temp folder, so ~/.claude and ~/.cache/agent-city are temp stand-ins; the
repo stand-in is a temp git repo holding a copy of the helper. A broken guard can only touch temp folders."""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "citydesks_demo.py")
ROOT = os.path.dirname(HERE)
MARKER = ".citydesks-demo"


class HelperCase(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="cdtest-"))
        self.home = os.path.join(self.tmp, "home")
        self.claude = os.path.join(self.home, ".claude", "agent-city")
        self.cache = os.path.join(self.home, ".cache", "agent-city")
        for d in (os.path.join(self.claude, "floors"), self.cache):
            os.makedirs(d)
            self.keep(d)
        tmpdir = os.path.join(self.tmp, "t")
        os.makedirs(tmpdir)
        self.env = dict(os.environ, HOME=self.home, TMPDIR=tmpdir)
        self.env.pop("CITYDESKS_PROTECT", None)
        self.env.pop("AGENT_CITY_HOME", None)
        self.env.pop("AGENT_CITY_DIR", None)
        self.pids = []

    def tearDown(self):
        for pid in self.pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def keep(self, folder):
        with open(os.path.join(folder, "keep.txt"), "w") as fh:
            fh.write("real data\n")

    def kept(self, folder):
        return os.path.isfile(os.path.join(folder, "keep.txt"))

    def marked(self, folder):
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, MARKER), "w") as fh:
            fh.write("x\n")
        self.keep(folder)
        return folder

    def helper(self, *args, script=SCRIPT, env=None):
        return subprocess.run([sys.executable, script] + list(args), env=env or self.env, capture_output=True, text=True,
                              timeout=60, stdin=subprocess.DEVNULL)

    def assertRefused(self, r):
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("REFUSED", r.stderr)


class TestStopRefuses(HelperCase):
    def test_a_folder_without_the_marker(self):
        other = os.path.join(self.tmp, "other")
        os.makedirs(other)
        self.keep(other)
        self.assertRefused(self.helper("stop", "--base", other))
        self.assertTrue(self.kept(other))

    def test_the_cache_stand_in_even_when_marked(self):
        self.marked(self.cache)
        self.assertRefused(self.helper("stop", "--base", self.cache))
        self.assertTrue(self.kept(self.cache))

    def test_a_folder_under_claude_even_when_marked(self):
        inner = self.marked(os.path.join(self.claude, "x"))
        self.assertRefused(self.helper("stop", "--base", inner))
        self.assertTrue(self.kept(inner))

    def test_a_link_to_a_real_folder(self):
        self.marked(self.cache)
        link = os.path.join(self.tmp, "link")
        os.symlink(self.cache, link)
        self.assertRefused(self.helper("stop", "--base", link))
        self.assertTrue(self.kept(self.cache))

    def test_a_folder_that_holds_a_real_one(self):
        self.marked(self.home)
        self.assertRefused(self.helper("stop", "--base", self.home))
        self.assertTrue(self.kept(self.home) and self.kept(self.cache))

    def test_the_extra_protect_list(self):
        precious = self.marked(os.path.join(self.tmp, "precious", "x"))
        env = dict(self.env, CITYDESKS_PROTECT=os.path.join(self.tmp, "precious"))
        self.assertRefused(self.helper("stop", "--base", precious, env=env))
        self.assertTrue(self.kept(precious))

    def test_no_base(self):
        self.assertRefused(self.helper("stop"))


class TestStartRefuses(HelperCase):
    def test_a_folder_that_is_not_empty(self):
        full = os.path.join(self.tmp, "full")
        os.makedirs(full)
        self.keep(full)
        self.assertRefused(self.helper("start", "--base", full))
        self.assertEqual(sorted(os.listdir(full)), ["keep.txt"], "no marker, no city/ written")

    def test_a_folder_under_a_real_one(self):
        demo = os.path.join(self.claude, "demo")
        self.assertRefused(self.helper("start", "--base", demo))
        self.assertFalse(os.path.exists(demo))

    def test_port_4777(self):
        self.assertRefused(self.helper("start", "--base", os.path.join(self.tmp, "new"), "--port", "4777"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "new")))


class TestOtherCommandsRefuse(HelperCase):
    def test_an_unmarked_folder(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        for cmd in ("team", "crowd", "work", "stop-one", "end", "phone"):
            with self.subTest(cmd=cmd):
                self.assertRefused(self.helper(cmd, "--base", empty, "--seconds", "1"))
                self.assertEqual(os.listdir(empty), [], "no repos/, transcripts/ or city/ written")


class TestRepoStandIn(HelperCase):
    """The repo the helper lives in (its checkout) is protected: a copy of the helper in a temp git repo refuses it."""

    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, "tests"))
        subprocess.run(["git", "init", "-q", self.repo], check=True, env=self.env)
        self.copy = os.path.join(self.repo, "tests", "citydesks_demo.py")
        shutil.copy(SCRIPT, self.copy)

    def test_refused_in_the_repo(self):
        sub = self.marked(os.path.join(self.repo, "sub"))
        self.assertRefused(self.helper("team", "--base", sub, script=self.copy))
        self.assertRefused(self.helper("stop", "--base", sub, script=self.copy))
        self.assertTrue(self.kept(sub))
        self.assertFalse(os.path.exists(os.path.join(sub, "repos")))
        self.assertRefused(self.helper("start", "--base", os.path.join(self.repo, "new"), script=self.copy))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "new")))


class TestServerStaysInTheBase(unittest.TestCase):
    def test_every_place_it_writes_is_in_the_base(self):
        sys.path.insert(0, HERE)
        import citydesks_demo as d
        base = os.path.realpath(tempfile.gettempdir()) + "/cd-base"
        p = d.paths(base)
        argv, env = d.server_cmd(p, 5000, "zh", ROOT, os.path.join(base, "repos", "team-floor"))
        for flag in ("--dir", "--floors-dir", "--world", "--decisions"):
            with self.subTest(flag=flag):
                self.assertIn(flag, argv)
                self.assertTrue(argv[argv.index(flag) + 1].startswith(base + "/"), argv[argv.index(flag) + 1])
        self.assertTrue(env["AGENT_CITY_HOME"].startswith(base + "/"))
        self.assertTrue(env["AGENT_CITY_DIR"].startswith(base + "/"))


class TestRoundTrip(HelperCase):
    """start without --base makes a marked temp base; stop kills only the processes it started and removes the base;
    the real-folder stand-ins stay untouched."""

    def test_start_then_stop(self):
        before = sorted(os.listdir(self.claude)), sorted(os.listdir(self.cache))
        r = self.helper("start")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        base = next(l.split()[1] for l in r.stdout.splitlines() if l.startswith("BASE: "))
        self.assertTrue(base.startswith(self.env["TMPDIR"]), base)
        self.assertTrue(os.path.isfile(os.path.join(base, MARKER)))
        with open(os.path.join(base, "server.pid")) as fh:
            server = int(fh.read())
        self.pids.append(server)
        os.kill(server, 0)
        stranger = subprocess.Popen(["sleep", "60"])
        self.pids.append(stranger.pid)
        with open(os.path.join(base, "phone.pid"), "w") as fh:
            fh.write(str(stranger.pid))     # a pid that is not this base's: stop must leave it alone
        r = self.helper("stop", "--base", base)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(base))
        for _ in range(30):
            try:
                os.kill(server, 0)
            except OSError:
                break
            time.sleep(0.1)
        else:
            self.fail("the server it started is still running")
        self.assertIsNone(stranger.poll(), "the stranger still runs")
        self.assertEqual((sorted(os.listdir(self.claude)), sorted(os.listdir(self.cache))), before,
                         "nothing written into the real-folder stand-ins")


if __name__ == "__main__":
    unittest.main()
