"""Tests of agent-nightly.sh and agent_nightly.py: the nightly run, its status, the selection misses."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from scripthelp import BIN  # noqa: E402
from test_agent_room import NetCase  # noqa: E402
import signal  # noqa: E402
import time  # noqa: E402
import glob  # noqa: E402


class TestNightly(NetCase):
    script = "agent-nightly.sh"

    def setUp(self):
        super().setUp()
        # section 37 F10: init or the start stores the name once per clone; the nightly only reads it
        self.git("config", "--local", "auto-pipeline.workingbranch", "ap-main-t")

    def nightly(self, *args, env=None):
        return self.repo.run("agent-nightly.sh", *args, env=env, timeout=120)

    def status_file(self):
        with open(os.path.join(self.gitdir(), "agent_nightly.json")) as fh:
            return json.load(fh)

    def misses_file(self):
        path = os.path.join(self.gitdir(), "agent_selection_misses.txt")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return fh.read().splitlines()

    def test_none_yet(self):
        r = self.nightly("--status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "NIGHTLY: none")

    def test_a_green_run(self):
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertEqual(st["result"], "green")
        self.assertEqual(st["commit"], self.git("rev-parse", "HEAD"))
        self.assertEqual(st["failed"], [])
        out = self.nightly("--status").stdout.strip()
        self.assertRegex(out, r"^NIGHTLY: green [0-9a-f]{7,} \d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_a_red_run_gates_nothing_and_says_which_test(self):
        self.put({"src/x.txt": "broken\n"})
        self.git("commit", "-qam", "break")
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, "the nightly gates nothing: %s" % r.stderr)
        st = self.status_file()
        self.assertEqual(st["result"], "red")
        self.assertEqual(len(st["failed"]), 1)
        self.assertIn("test_x_txt", st["failed"][0])

    def test_a_red_after_a_green_is_a_selection_miss_of_the_merge(self):
        self.nightly("--start", "--wait")
        self.merge("feat-doc", {"docs/a.md": "x\n"}, "Merge feat-doc (W8)")
        self.merge("feat-x", {"src/x.txt": "broken\n"}, "Merge feat-x (W8)")
        self.merge("feat-y", {"docs/b.md": "y\n"}, "Merge feat-y (W8)")
        self.nightly("--start", "--wait")
        lines = self.misses_file()
        self.assertEqual(len(lines), 1, lines)
        date, test, merge = lines[0].split(" | ")
        self.assertRegex(date, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertIn("test_x_txt", test)
        self.assertRegex(merge, r"^[0-9a-f]{7,} Merge feat-x \(W8\)$")
        out = self.nightly("--misses").stdout.splitlines()
        self.assertEqual(out[-1], "misses: 1 since %s" % date)

    def test_a_nightly_started_after_the_bump_lets_the_release_go(self):
        # final review defect D: merge skill step 8 bumps first, then --release-ok says no, then --start
        self.put({".claude-plugin/plugin.json": '{"name": "p", "version": "0.2.0"}\n'})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "bump 0.2.0")
        self.assertEqual(self.nightly("--release-ok").returncode, 1)
        self.nightly("--start", "--wait")
        r = self.nightly("--release-ok")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_nightly_tests_the_working_branch(self):
        # owner 1A (section 17): dev is the working branch; main (checked out here) moved on and is red
        self.git("branch", "dev")
        dev = self.git("rev-parse", "dev")
        self.put({"src/x.txt": "broken\n"})
        self.git("commit", "-qam", "main moves")
        self.git("config", "--local", "auto-pipeline.workingbranch", "dev")   # stored by init (section 37 F10)
        self.nightly("--start", "--wait")
        st = self.status_file()
        self.assertEqual((st["commit"], st["result"]), (dev, "green"), st)
        self.assertEqual(self.nightly("--release-ok").returncode, 0)

    def test_the_nightly_tests_the_commit_not_the_shared_checkout(self):
        # re-check defect G: merge deputies work in the main checkout at night
        self.put({"src/x.txt": "half merged\n"})                    # uncommitted, in the main checkout
        self.nightly("--start", "--wait")
        st = self.status_file()
        self.assertEqual(st["result"], "green", st)
        self.assertEqual(st["commit"], self.git("rev-parse", "HEAD"))
        self.assertEqual(len(self.git("worktree", "list").splitlines()), 1, "the scratch tree is gone")

    def test_the_scratch_tree_sees_the_installed_dependency_folders(self):
        # a clean scratch checkout has no node_modules or venv: the nightly links the main checkout's
        # ignored dependency folders (node_modules, .venv, venv, vendor, .dart_tool, Pods), top level and
        # one level down, into the scratch tree, read only by use; else every JS or Python repo is red
        self.put({".gitignore": "node_modules/\npackages/*/node_modules/\n",
                  "tests/test_dep.py": "import os, unittest\n\n\nclass D(unittest.TestCase):\n"
                                       "    def test_dep(self):\n"
                                       "        self.assertTrue(os.path.exists('node_modules/dep/index.js'))\n"
                                       "        self.assertTrue(os.path.exists('packages/a/node_modules/x.js'))\n"})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "needs deps")
        self.put({"node_modules/dep/index.js": "x\n", "packages/a/node_modules/x.js": "y\n"})
        self.nightly("--start", "--wait")
        self.assertEqual(self.status_file()["result"], "green", self.status_file())
        self.assertTrue(os.path.exists(os.path.join(self.repo.dir, "node_modules", "dep", "index.js")),
                        "the main checkout's folder stays")

    def test_failures_names_the_merge_by_running_the_test(self):
        # section 21 (4): the broken file is not named in the test's text, so only running finds the merge
        self.put({"tests/test_cfg.py": "import os, unittest\n\n\nclass C(unittest.TestCase):\n"
                                       "    def test_cfg(self):\n        name = 'co' + 'nf.txt'\n"
                                       "        with open(os.path.join('src', name)) as fh:\n"
                                       "            self.assertEqual(fh.read().strip(), 'on')\n",
                  "src/conf.txt": "on\n", "requirements/feat-c.md": "# feat-c\n"})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "cfg")
        self.nightly("--start", "--wait")
        self.merge("feat-a", {"docs/a.md": "a\n"}, "Merge feat-a (W8)")
        self.merge("feat-c", {"src/conf.txt": "off\n"}, "Merge feat-c (W8)")
        self.merge("feat-y", {"docs/b.md": "y\n"}, "Merge feat-y (W8)")
        self.nightly("--start", "--wait")
        r = self.nightly("--failures")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = [l for l in r.stdout.splitlines() if "test_cfg" in l]
        self.assertEqual(len(rows), 1, r.stdout)
        test, merge, task, req = rows[0].split(" | ")
        self.assertRegex(merge, r"^[0-9a-f]{7,} Merge feat-c \(W8\)$")
        self.assertEqual((task, req), ("feat-c", "requirements/feat-c.md"))
        misses = [l for l in self.misses_file() if "test_cfg" in l]
        self.assertTrue(misses and misses[-1].split(" | ")[2].endswith("Merge feat-c (W8)"), misses)

    def test_failures_with_no_green_run_before(self):
        self.put({"src/x.txt": "broken\n"})
        self.git("commit", "-qam", "break")
        self.nightly("--start", "--wait")
        rows = [l for l in self.nightly("--failures").stdout.splitlines() if "test_x_txt" in l]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].split(" | ")[1], "-")

    def test_a_red_first_run_is_no_miss(self):
        self.put({"src/x.txt": "broken\n"})
        self.git("commit", "-qam", "break")
        self.nightly("--start", "--wait")
        self.assertEqual(self.misses_file(), [])

    def test_release_ok_needs_a_green_run_on_the_commit_released(self):
        # re-check defect D: the release is built from local HEAD before main is pushed (merge skill step 8);
        # a commit that only bumps .claude-plugin/plugin.json counts as its parent
        r = self.nightly("--release-ok")
        self.assertEqual(r.returncode, 1)
        self.assertIn("agent-nightly.sh --start", r.stdout)
        self.nightly("--start", "--wait")
        self.assertEqual(self.nightly("--release-ok").returncode, 0)
        self.put({".claude-plugin/plugin.json": '{"name": "p", "version": "0.2.0"}\n'})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "bump 0.2.0")                 # local, not pushed
        self.assertEqual(self.nightly("--release-ok").returncode, 0, "a version bump alone is its parent")
        self.put({"src/x.txt": "ok\n", "docs/a.md": "x\n"})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "more code")
        self.assertEqual(self.nightly("--release-ok").returncode, 1, "HEAD moved after the nightly")

    def test_the_tip_counts_as_its_parent_only_for_a_version_only_bump(self):
        # release-check-loosen KEEP 1: a tip that changes another key of plugin.json is not its parent
        self.nightly("--start", "--wait")
        g = self.git("rev-parse", "HEAD")
        for body in ('{"name": "q", "version": "0.2.0"}\n', '{"name": "q", "version": "0.1.0"}\n'):
            with self.subTest(body=body):
                self.git("reset", "-q", "--hard", g)
                self.put({".claude-plugin/plugin.json": body})
                self.git("commit", "-q", "-am", "plugin.json")
                self.assertEqual(self.nightly("--release-ok").returncode, 1)
        self.git("reset", "-q", "--hard", g)
        self.put({".claude-plugin/plugin.json": '{"name": "p", "version": "0.2.0"}\n'})
        self.git("commit", "-q", "-am", "bump")
        self.assertEqual(self.nightly("--release-ok").returncode, 0)

    def test_a_red_full_run_through_run2_names_its_failing_test(self):
        # release-check-loosen KEEP 2: run2.py prints FAIL/ERROR lines indented
        with open(os.path.join(os.path.dirname(BIN), "tests", "run2.py")) as fh:
            runner = fh.read()
        self.put({"agent_repo.conf": "version=1\nfull_cmd=python3 tests/run2.py\n"
                                     "related_cmd=python3 tests/run2.py {tests}\n",
                  "tests/run2.py": runner,
                  "tests/test_q.py": "import unittest\n\n\nclass X(unittest.TestCase):\n"
                                     "    def test_x_red(self):\n        self.fail('red')\n"})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "run2 and a red test")
        self.nightly("--start", "--wait")
        st = self.status_file()
        self.assertEqual(st["result"], "red", st)
        self.assertTrue(any("test_x_red" in f for f in st["failed"]), st)
        self.assertIn("test_x_red", self.nightly("--failures").stdout)

    def test_due(self):
        late = {"AGENT_FAKE_NOW": "2026-11-25 23:00"}
        self.assertEqual(self.nightly("--due", env=late).returncode, 0)
        self.nightly("--start", "--wait", env={"AGENT_FAKE_NOW": "2026-11-25 22:30"})
        self.assertEqual(self.nightly("--due", env=late).returncode, 1, "one run a day")
        self.assertEqual(self.nightly("--due", env={"AGENT_FAKE_NOW": "2026-11-26 10:00"}).returncode, 1,
                         "under 24 hours old, before the hour")
        self.assertEqual(self.nightly("--due", env={"AGENT_FAKE_NOW": "2026-11-26 23:30"}).returncode, 0)

    def test_the_nightly_waits_for_room(self):
        # section 24: no slots; the nightly passes the same memory gate as any run
        env = {"AGENT_FAKE_RAM": "79", "AGENT_FAKE_RAM_TOTAL_MB": "10000", "AGENT_TEST_RUN_WAIT_S": "1",
               "AGENT_RESERVE_FILE": os.path.join(self.repo.base, "reserve.json")}
        holder = subprocess.Popen(["sleep", "30"])
        self.addCleanup(holder.kill)
        with open(env["AGENT_RESERVE_FILE"], "w") as fh:
            json.dump({"jobs": [{"pid": holder.pid, "mb": 500, "what": "x", "repo": "y",
                                 "since": "2026-11-25 15:00"}]}, fh)
        r = self.nightly("--start", "--wait", env=env)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("ROOM: no:", r.stdout + r.stderr)

    def test_the_nightly_hour_is_a_constant(self):
        sys.path.insert(0, BIN)
        import agent_conf
        self.assertEqual(agent_conf.CONSTANTS["nightly_hour"], 22)

    def test_a_normal_session_start_starts_a_due_nightly(self):
        # re-check defect E: the block sat inside the compaction branch
        import time
        r = self.repo.run("agent-start.sh", stdin='{"cwd": "%s", "source": "startup"}' % self.repo.dir,
                          env={"AGENT_FAKE_NOW": "2026-11-25 23:00", "CLAUDE_PID": str(os.getpid())})
        self.assertEqual(r.returncode, 0, r.stderr)
        path = os.path.join(self.gitdir(), "agent_nightly.json")
        for _ in range(100):
            if os.path.exists(path):
                break
            time.sleep(0.1)
        self.assertTrue(os.path.exists(path), "no nightly was started at a normal session start")
        for _ in range(300):                                      # let the background run end before cleanup
            with open(path) as fh:
                if json.load(fh).get("finished"):
                    break
            time.sleep(0.1)

    def test_who_starts_it(self):
        with open(os.path.join(BIN, "agent_housekeep.py")) as fh:
            hk = fh.read()
        self.assertIn("agent-nightly.sh", hk)
        self.assertIn("--due", hk)
        with open(os.path.join(BIN, "agent-start.sh")) as fh:
            start = fh.read()
        self.assertIn("agent-nightly.sh", start)


def only_own(cls):
    """A subclass of a test class with tests: keep only the tests written in the subclass itself."""
    own = set(vars(cls))
    for name in dir(cls):
        if name.startswith("test") and name not in own:
            setattr(cls, name, None)
    return cls


def gone(marker, seconds=6):
    end = time.time() + seconds
    while time.time() < end:
        if subprocess.run(["pgrep", "-f", marker], capture_output=True).returncode != 0:
            return True
        time.sleep(0.2)
    return False


def wait_until(check, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        if check():
            return True
        time.sleep(0.2)
    return check()


@only_own
class Nightly(TestNightly):
    def env(self, **extra):
        e = {"AGENT_RESERVE_FILE": os.path.join(self.repo.base, "reserve.json")}
        e.update(extra)
        return e

    def set_full(self, cmd):
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "w") as fh:
            fh.write("version=1\nfull_cmd=%s\nrelated_cmd=python3 -m unittest {modules}\n" % cmd)

    def status(self):
        p = os.path.join(self.gitdir(), "agent_nightly.json")
        if not os.path.exists(p):
            return {}
        with open(p) as fh:
            return json.load(fh)

    def weights(self):
        p = os.path.join(self.gitdir(), "agent_test_weights.json")
        if not os.path.exists(p):
            return {}
        with open(p) as fh:
            return json.load(fh)


@only_own
class TestC2NightlyIsMonitored(Nightly):
    def test_the_peak_is_recorded(self):
        # The measured process holds 60 MB (touched again and again, so it stays resident) until the monitor has
        # seen it: the test waits for the run's reservation to grow to the peak, then releases the process.
        hold = os.path.join(self.repo.base, "hold_60mb")
        open(hold, "w").close()
        holder = os.path.join(self.repo.base, "hold_60mb.py")
        with open(holder, "w") as fh:
            fh.write("import os, time\n"
                     "b = bytearray(os.urandom(60 * 1024 * 1024))\n"
                     "end = time.time() + 120\n"
                     "while os.path.exists(%r) and time.time() < end:\n"
                     "    b[::4096] = b'x' * len(b[::4096])\n"
                     "    time.sleep(0.05)\n" % hold)
        self.set_full("python3 %s" % holder)
        env = self.env()
        reserve = env["AGENT_RESERVE_FILE"]
        full_env = self.repo._env(env)
        proc = subprocess.Popen([self.repo.script_path("agent-nightly.sh"), "--start", "--wait"], cwd=self.repo.cwd,
                                env=full_env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())

        def seen():
            try:
                with open(reserve) as fh:
                    return any(int(j.get("mb", 0) or 0) >= 50 for j in json.load(fh).get("jobs", []))
            except (OSError, ValueError):
                return False
        self.assertTrue(wait_until(seen, 120), "the monitor never saw the 60 MB process")
        os.remove(hold)
        out, err = proc.communicate(timeout=120)
        self.assertEqual(proc.returncode, 0, out + err)
        self.assertEqual(self.status().get("result"), "green", self.status())
        w = self.weights().get("nightly", "")
        self.assertRegex(w, r"^\d+ s \d+ MB$")
        self.assertGreaterEqual(int(w.split()[2]), 50, w)


@only_own
class TestC4NightlyStopsItsChildren(Nightly):
    def test_sigterm_stops_the_suite_and_removes_the_scratch_tree(self):
        self.set_full("sleep 35.3")
        self.nightly("--start", env=self.env())
        self.assertTrue(wait_until(lambda: self.status().get("result") == "running" and self.status().get("pid")))
        self.assertTrue(wait_until(lambda: subprocess.run(["pgrep", "-f", "sleep 35.3"],
                                                          capture_output=True).returncode == 0))
        pid = int(self.status()["pid"])
        os.kill(pid, signal.SIGTERM)
        self.assertTrue(gone("sleep 35.3"), "the suite kept running")
        self.assertTrue(wait_until(lambda: not os.path.exists(os.path.join(self.gitdir(), "agent_nightly_wt"))))
        self.assertTrue(wait_until(lambda: self.status().get("result") == "stopped"), self.status())


@only_own
class TestC11OneFullRunAtATime(Nightly):
    def test_a_second_start_waits_for_none_and_touches_nothing(self):
        self.set_full("sleep 3")
        self.nightly("--start", env=self.env())
        self.assertTrue(wait_until(lambda: self.status().get("result") == "running"))
        began = time.time()
        r = self.nightly("--start", "--wait", env=self.env())
        self.assertLess(time.time() - began, 2.5)
        self.assertEqual(r.stdout.strip(), "NIGHTLY: already running")
        self.assertTrue(wait_until(lambda: self.status().get("result") == "green", 20), self.status())


@only_own
class TestC3NoRoomNoAutomaticNightly(Nightly):
    def test_the_start_hands_it_on(self):
        e = {"AGENT_FAKE_NOW": "2026-11-25 23:00", "CLAUDE_PID": str(os.getpid()), "AGENT_FAKE_RAM": "95",
             "AGENT_FAKE_RAM_TOTAL_MB": "10000", "AGENT_FAKE_HOST": "pc2"}
        e.update(self.env())
        r = self.repo.run("agent-start.sh", stdin='{"cwd": "%s", "source": "startup"}' % self.repo.dir, env=e)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("NIGHTLY: due, no room on pc2: start it where there is room (W7): agent-nightly.sh --start",
                      r.stdout)
        time.sleep(2)
        self.assertEqual(self.status(), {}, "nothing starts without room")


@only_own
class TestC5Failures(Nightly):
    def test_a_file_missing_at_a_merge_is_not_there(self):
        self.nightly("--start", "--wait", env=self.env())               # green on the base
        self.merge("feat-a", {"docs/a.md": "a\n"}, "Merge feat-a (W8)")
        self.merge("feat-n", {"tests/test_new.py": "import unittest\n\n\nclass N(unittest.TestCase):\n"
                                                   "    def test_new(self):\n        self.fail('red')\n"},
                   "Merge feat-n (W8)")
        self.nightly("--start", "--wait", env=self.env())
        r = self.nightly("--failures", env=self.env())
        rows = [l for l in r.stdout.splitlines() if "test_new" in l]
        self.assertTrue(rows, r.stdout)
        self.assertIn("Merge feat-n (W8)", rows[0])
        self.assertNotIn("feat-a", rows[0])

    def test_an_unknown_test_id_stays_unknown(self):
        self.nightly("--start", "--wait", env=self.env())
        green = self.git("rev-parse", "HEAD")
        self.merge("feat-a", {"docs/a.md": "a\n"}, "Merge feat-a (W8)")
        with open(os.path.join(self.gitdir(), "agent_nightly.json"), "w") as fh:
            json.dump({"started": "x", "commit": self.git("rev-parse", "HEAD"), "finished": "y", "result": "red",
                       "failed": ["mystery::thing"], "last_green": green}, fh)
        r = self.nightly("--failures", env=self.env())
        row = [l for l in r.stdout.splitlines() if l.startswith("mystery::thing")][0]
        self.assertEqual(row.split(" | ")[1], "unknown", row)

    def test_no_room_to_rerun_is_unknown(self):
        self.nightly("--start", "--wait", env=self.env())
        self.merge("feat-n", {"tests/test_new.py": "import unittest\n\n\nclass N(unittest.TestCase):\n"
                                                   "    def test_new(self):\n        self.fail('red')\n"},
                   "Merge feat-n (W8)")
        self.nightly("--start", "--wait", env=self.env())
        r = self.nightly("--failures", env=self.env(AGENT_FAKE_RAM="95", AGENT_FAKE_RAM_TOTAL_MB="10000",
                                                     AGENT_TEST_RUN_WAIT_S="1"))
        row = [l for l in r.stdout.splitlines() if "test_new" in l][0]
        self.assertEqual(row.split(" | ")[1], "unknown", row)


ROOT = os.path.dirname(HERE)


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


class TestG8NightlyScratchPerRun(unittest.TestCase):
    def test_every_scratch_name_has_the_pid(self):
        src = read("bin", "agent_nightly.py")
        # the --failures and record_misses scratch tree (the nightly's own run is one at a time: SCRATCH alone)
        lines = [l for l in src.splitlines() if '"_failures"' in l and "SCRATCH" in l and not l.strip().startswith("#")]
        self.assertTrue(lines)
        for l in lines:
            with self.subTest(line=l.strip()):
                self.assertIn("getpid", l)


@only_own
class TestC18ConnectedMachineFirst(Nightly):
    def test_with_a_connected_machine_nothing_runs_locally(self):
        # section 48 C23: the real answer's shape, and pc1 answers a terminal list
        with open(os.path.join(self.repo.orca_dir, "envs.json"), "w") as fh:
            json.dump(REAL_SHAPE, fh)
        os.makedirs(os.path.join(self.repo.orca_dir, "env", "pc1"), exist_ok=True)
        with open(os.path.join(self.repo.orca_dir, "env", "pc1", "terminals.json"), "w") as fh:
            json.dump({"id": "req-2", "ok": True, "result": {"terminals": []}, "_meta": {}}, fh)
        e = {"AGENT_FAKE_NOW": "2026-11-25 23:00", "CLAUDE_PID": str(os.getpid()), "AGENT_FAKE_HOST": "pc2"}
        e.update(self.env())
        r = self.repo.run("agent-start.sh", stdin='{"cwd": "%s", "source": "startup"}' % self.repo.dir, env=e)
        self.assertIn("NIGHTLY: due: a connected machine runs it (W7): agent-nightly.sh --start there", r.stdout)
        time.sleep(2)
        self.assertEqual(self.status(), {})


@only_own
class TestC19FailuresStop(Nightly):
    def test_sigterm_during_failures_cleans_up(self):
        self.nightly("--start", "--wait", env=self.env())
        self.merge("feat-n", {"tests/test_new.py": "import unittest\n\n\nclass N(unittest.TestCase):\n"
                                                   "    def test_new(self):\n        self.fail('red')\n"},
                   "Merge feat-n (W8)")
        self.nightly("--start", "--wait", env=self.env())
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "w") as fh:
            fh.write("version=1\nfull_cmd=python3 -m unittest discover -s tests -t .\n"
                     "related_cmd=sleep 37.7; python3 -m unittest {modules}\n")
        p = self.repo.popen("agent-nightly.sh", "--failures", env=self.env())
        self.addCleanup(lambda: p.poll() is None and p.kill())
        self.assertTrue(wait_until(lambda: subprocess.run(["pgrep", "-f", "sleep 37.7"], capture_output=True)
                                   .returncode == 0, 20))
        os.kill(p.pid, signal.SIGTERM)
        self.assertTrue(wait_until(lambda: p.poll() is not None, 6))
        self.assertTrue(gone("sleep 37.7"))
        self.assertEqual(glob.glob(os.path.join(self.gitdir(), "agent_nightly_wt_failures*")), [])


@only_own
class TestC20StoppedIsNotDone(Nightly):
    def test_a_stopped_run_is_due_again(self):
        with open(os.path.join(self.gitdir(), "agent_nightly.json"), "w") as fh:
            json.dump({"started": "2026-11-25 22:30", "commit": self.git("rev-parse", "HEAD"),
                       "finished": "2026-11-25 22:31", "result": "stopped", "failed": []}, fh)
        r = self.nightly("--due", env={"AGENT_FAKE_NOW": "2026-11-25 23:00"})
        self.assertEqual(r.returncode, 0, r.stdout)


REAL_SHAPE = {"id": "req-1", "ok": True,
              "result": {"environments": [{
                  "id": "env-1", "name": "pc1", "createdAt": "2026-11-20T10:00:00Z", "updatedAt": "2026-11-20T10:00:00Z",
                  "pairingRevision": 1, "pairedDeviceId": "dev-1", "lastUsedAt": "2026-11-25T19:00:00Z",
                  "runtimeId": "rt-1", "endpoints": [{"id": "ep-1", "kind": "lan", "label": "pc1",
                                                      "endpoint": "192.168.1.20:7777"}],
                  "preferredEndpointId": "ep-1"}]},
              "_meta": {"version": 1}}


class Machines(Nightly):
    def pair(self, reachable):
        with open(os.path.join(self.repo.orca_dir, "envs.json"), "w") as fh:
            json.dump(REAL_SHAPE, fh)
        d = os.path.join(self.repo.orca_dir, "env", "pc1")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "terminals.json"), "w") as fh:
            json.dump({"id": "req-2", "ok": True, "result": {"terminals": []}, "_meta": {}}, fh)
        if not reachable:
            open(os.path.join(d, "down"), "w").close()

    def start_session(self):
        e = {"AGENT_FAKE_NOW": "2026-11-25 23:00", "CLAUDE_PID": str(os.getpid()), "AGENT_FAKE_HOST": "pc2"}
        e.update(self.env())
        return self.repo.run("agent-start.sh", stdin='{"cwd": "%s", "source": "startup"}' % self.repo.dir, env=e)


@only_own
class TestC23(Machines):
    def test_a_reachable_paired_machine_runs_it(self):
        self.pair(reachable=True)
        r = self.start_session()
        self.assertIn("NIGHTLY: due: a connected machine runs it (W7): agent-nightly.sh --start there", r.stdout)
        time.sleep(2)
        self.assertEqual(self.status(), {})

    def test_a_paired_machine_that_does_not_answer(self):
        self.pair(reachable=False)
        r = self.start_session()
        self.assertIn("NIGHTLY: the paired machine pc1 did not answer; it runs here when there is room", r.stdout)
        self.assertTrue(wait_until(lambda: self.status() != {}, 10), "with room it runs here")

    def test_the_shared_function(self):
        self.pair(reachable=True)
        r = self.nightly("--machines", env=self.env())
        self.assertEqual(r.stdout.split(), ["pc1"])
        self.assertIn("machines(", read("bin", "agent_housekeep.py"))
        self.assertIn("--machines", read("bin", "agent-start.sh"))
