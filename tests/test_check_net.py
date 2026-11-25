"""Failing tests for check-blocks section 15 (owner 1A, 2026-11-25): no task runs the full suite.
Written by the task manager before any code. Contract: requirements/check-blocks.md section 15, C6 and C7.

    bin/agent-nightly.sh (bin/agent_nightly.py)   the nightly run: gates nothing, records selection misses,
                                                  says whether a release may go (--release-ok)
    bin/agent-test-run.sh                         a test run is light or heavy by measured weight

Status file: <git common dir>/agent_nightly.json. Misses: <git common dir>/agent_selection_misses.txt.
Heavy slots: <git common dir>/agent_heavy_slots/<pid> (one file per running heavy run, holding its key).
Test hooks: --wait runs the nightly in the foreground; AGENT_TEST_RUN_WAIT_S caps a wait (default 3600),
after which agent-test-run.sh exits 3 with the reason.

Run: python3 -m unittest tests.test_check_net
"""

import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scripthelp import BIN, ROOT, ScriptCase  # noqa: E402

PASSING = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n"


def x_test(expect):
    return ("import os, unittest\n\n\nclass X(unittest.TestCase):\n    def test_x_txt(self):\n"
            "        with open(os.path.join('src', 'x.txt')) as fh:\n"
            "            self.assertEqual(fh.read().strip(), %r)\n" % expect)


class NetCase(ScriptCase):

    def git(self, *args):
        return subprocess.run(["git", "-C", self.repo.dir] + list(args), check=True, capture_output=True,
                              text=True).stdout.strip()

    def put(self, files):
        for rel, body in files.items():
            full = os.path.join(self.repo.dir, rel)
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            with open(full, "w") as fh:
                fh.write(body)

    def gitdir(self):
        return self.git("rev-parse", "--path-format=absolute", "--git-common-dir")

    def setUp(self):
        super().setUp()
        self.git("branch", "-M", "main")
        self.put({"agent_repo.conf": "version=1\nfull_cmd=python3 -m unittest discover -s tests -t .\n"
                                     "related_cmd=python3 -m unittest {modules}\n",
                  ".claude-plugin/plugin.json": '{"name": "p", "version": "0.1.0"}\n',
                  "tests/__init__.py": "", "tests/test_a.py": PASSING, "tests/test_x.py": x_test("ok"),
                  "src/x.txt": "ok\n"})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.origin = os.path.join(self.repo.base, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", self.origin], check=True, capture_output=True)
        self.git("remote", "add", "origin", self.origin)
        self.git("push", "-q", "-u", "origin", "main")

    def merge(self, branch, files, subject):
        self.git("checkout", "-q", "-b", branch)
        self.put(files)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "work on " + branch)
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", subject, branch)
        self.git("push", "-q", "origin", "main")


# ---------------------------------------------------------------- C6 the nightly run


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


# ---------------------------------------------------------------- C7 light or heavy by measured weight


class RoomCase(NetCase):
    """Section 24 (owner 2026-11-25): a run starts when memory in use + its known need fits under the
    Max memory % limit; one reservation list per machine; unknown weight starts alone."""

    def setUp(self):
        super().setUp()
        self.reserve = os.path.join(self.repo.base, "reserve.json")

    def env(self, ram="40", total="10000", **extra):
        e = {"AGENT_FAKE_RAM": ram, "AGENT_FAKE_RAM_TOTAL_MB": total, "AGENT_RESERVE_FILE": self.reserve,
             "AGENT_TEST_RUN_WAIT_S": "1"}
        e.update(extra)
        return e

    def hold(self, mb, what="other run", *extra):
        p = subprocess.Popen(["sleep", "30"])
        self.addCleanup(p.kill)
        r = self.repo.run("agent-room.sh", "reserve", str(p.pid), str(mb), what, *extra, env=self.env())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return p

    def jobs(self):
        if not os.path.exists(self.reserve):
            return []
        with open(self.reserve) as fh:
            return json.load(fh).get("jobs", [])


class TestRoom(RoomCase):
    script = "agent-room.sh"

    def room(self, *args, ram="40", **env):
        return self.repo.run("agent-room.sh", *args, env=self.env(ram=ram, **env))

    def test_room_for_a_known_need(self):
        self.assertEqual(self.room("check", "3000").returncode, 0)       # 4000 + 0 + 3000 <= 8000

    def test_no_room(self):
        r = self.room("check", "5000")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ROOM: no: 4000 MB in use + 0 MB reserved + 5000 MB > 8000 MB", r.stdout)

    def test_reservations_count(self):
        self.hold(2000)
        r = self.room("check", "3000")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ROOM: no: 4000 MB in use + 2000 MB reserved + 3000 MB > 8000 MB", r.stdout)

    def test_a_dead_pid_frees_its_entry(self):
        dead = subprocess.Popen(["true"])
        dead.wait()
        self.room("reserve", str(dead.pid), "2000", "gone")
        self.assertEqual(self.room("check", "3000").returncode, 0)
        self.assertEqual(self.room("list").stdout.strip(), "")

    def test_unknown_starts_at_once_under_the_limit(self):
        # section 25 (E): an unmeasured run is not held back; the monitor watches it
        self.hold(100)
        self.assertEqual(self.room("check", "unknown").returncode, 0)
        r = self.room("check", "unknown", ram="85")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ROOM: no: 8500 MB in use + 100 MB reserved + 0 MB > 8000 MB", r.stdout)

    def test_relief_stops_the_newest_unmeasured_test_run_never_an_agent(self):
        import time
        older = self.hold(2000, "build")
        time.sleep(1.1)
        # section 43 C1: relief signals only a run the runner started (a hand reservation never)
        p = self.repo.popen("agent-test-run.sh", "--key", "related", "--", "sleep", "30", env=self.env())
        self.addCleanup(lambda: p.poll() is None and p.kill())
        for _ in range(50):
            if any(j.get("pid") == p.pid for j in self.jobs()):
                break
            time.sleep(0.2)
        pane = subprocess.Popen(["sleep", "30"])
        self.addCleanup(pane.kill)
        self.room("reserve", str(pane.pid), "600", "pane", "--kind", "pane")
        r = self.room("relief", ram="90", AGENT_FAKE_HOST="pc2")          # 9000 MB in use, limit 8000
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "OVER LIMIT pc2: 1000 MB over; stopped 1 test runs (%d); "
                                           "working agents left alone" % p.pid)
        self.assertIsNotNone(p.wait(timeout=5))
        self.assertIsNone(older.poll())
        self.assertIsNone(pane.poll())

    def test_relief_under_the_limit_stops_nothing(self):
        self.hold(500)
        r = self.room("relief")
        self.assertEqual(r.stdout.strip(), "ROOM: ok")

    def test_measure_pane_keeps_the_highest(self):
        # random bytes: the memory compressor cannot shrink them under load (zero pages it can)
        p = subprocess.Popen([sys.executable, "-c", "import os, time; b = os.urandom(120 * 1024 * 1024); time.sleep(20)"])
        self.addCleanup(p.kill)
        import time
        time.sleep(1.5)
        r = self.room("measure-pane", str(p.pid))
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.gitdir(), "agent_test_weights.json")) as fh:
            mb = int(json.load(fh)["pane"].split()[2])
        self.assertGreaterEqual(mb, 100)

    def test_release_and_list(self):
        p = self.hold(700, "the nightly")
        out = self.room("list").stdout
        self.assertIn(str(p.pid), out)
        self.assertIn("700 MB", out)
        self.room("release", str(p.pid))
        self.assertEqual(self.jobs(), [])

    def test_two_repos_share_the_list(self):
        self.hold(2000)
        other = self.repo.make_worktree("other_repo")
        r = self.repo.run("agent-room.sh", "check", "3000", env=self.env(), cwd=other)
        self.assertEqual(r.returncode, 1, "another repo must see the same reservations")


class TestTestRun(RoomCase):
    script = "agent-test-run.sh"

    def run_test(self, key, *cmd, env=None):
        return self.repo.run("agent-test-run.sh", "--key", key, "--", *cmd, env=env or self.env(), timeout=60)

    def weight(self, key):
        path = os.path.join(self.gitdir(), "agent_test_weights.json")
        if not os.path.exists(path):
            return None
        with open(path) as fh:
            return json.load(fh).get(key)

    def test_unknown_weight_starts_at_once_then_is_known(self):
        r = self.run_test("related", "python3", "-c", "print('hi')")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "TEST RUN related: unknown weight, starts at once, monitored")
        self.assertIn("hi", r.stdout)
        self.assertRegex(self.weight("related") or "", r"^\d+ s \d+ MB$")
        r = self.run_test("related", "python3", "-c", "print('hi')")
        self.assertRegex(r.stdout.splitlines()[0], r"^TEST RUN related: \d+ MB known \(\d+ s\)$")

    def test_unknown_starts_beside_another_job(self):
        self.hold(100)
        self.assertEqual(self.run_test("new", "true").returncode, 0)

    def ram_file(self, value):
        path = os.path.join(self.repo.base, "ram.txt")
        with open(path, "w") as fh:
            fh.write(value)
        return path

    def later(self, seconds, path, value):
        import threading
        def go():
            with open(path, "w") as fh:
                fh.write(value)
        t = threading.Timer(seconds, go)
        t.start()
        self.addCleanup(t.cancel)

    def test_the_monitor_stops_a_run_that_goes_over_and_records_its_peak(self):
        ram = self.ram_file("40")
        self.later(1.0, ram, "95")
        r = self.run_test("big", "python3", "-c", "import time; time.sleep(6)",
                          env=self.env(AGENT_FAKE_RAM_FILE=ram))
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"(?m)^TEST RUN big: stopped over the limit \(9500 MB > 8000 MB\), "
                                   r"peak \d+ MB recorded$")
        self.assertRegex(self.weight("big") or "", r"^\d+ s \d+ MB$")

    def test_a_stopped_run_is_tried_again_when_there_is_room(self):
        ram = self.ram_file("40")
        marker = os.path.join(self.repo.base, "tried")
        self.later(1.0, ram, "95")
        self.later(2.0, ram, "40")
        cmd = ("import os, time, sys; p = %r\n"
               "if os.path.exists(p): sys.exit(0)\n"
               "open(p, 'w').close(); time.sleep(6)" % marker)
        r = self.run_test("again", "python3", "-c", cmd, env=self.env(AGENT_FAKE_RAM_FILE=ram,
                                                                      AGENT_TEST_RUN_WAIT_S="10"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("stopped over the limit", r.stdout)

    def test_a_run_that_is_not_the_pick_goes_on(self):
        ram = self.ram_file("40")
        newer = []
        def add_newer():
            # section 46 C16: only a runner's run can be the pick, so the newer job is a runner's run
            # when its monitor stops it (it is the pick), its memory is freed: the fake RAM drops back
            p = self.repo.popen("agent-test-run.sh", "--key", "newer", "--", "sh", "-c",
                                "trap 'echo 40 > %s; exit 143' TERM; sleep 30 & wait" % ram,
                                env=self.env(AGENT_FAKE_RAM_FILE=ram))
            newer.append(p)
        import threading
        threading.Timer(0.5, add_newer).start()
        self.later(1.0, ram, "95")
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "a") as fh:
            fh.write("weight.mine=3 s 100 MB\n")
        r = self.run_test("mine", "python3", "-c", "import time; time.sleep(2.5)",
                          env=self.env(AGENT_FAKE_RAM_FILE=ram))
        for p in newer:
            p.kill()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("stopped over the limit", r.stdout)

    def test_a_known_run_reserves_while_it_runs_and_releases(self):
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "a") as fh:
            fh.write("weight.related=3 s 1500 MB\n")
        show = "import json, os; print('JOBS', json.load(open(os.environ['AGENT_RESERVE_FILE']))['jobs'])"
        r = self.run_test("related", "python3", "-c", show)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("'mb': 1500", r.stdout)
        self.assertEqual(self.jobs(), [])

    def test_no_room_waits_then_exit_3(self):
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "a") as fh:
            fh.write("weight.full=600 s 5000 MB\n")
        r = self.run_test("full", "true")
        self.assertEqual(r.returncode, 3)
        self.assertIn("ROOM: no: 4000 MB in use + 0 MB reserved + 5000 MB > 8000 MB", r.stdout + r.stderr)

    def test_long_but_light_just_goes(self):
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "a") as fh:
            fh.write("weight.full=3000 s 200 MB\n")
        self.hold(1000)
        self.assertEqual(self.run_test("full", "true").returncode, 0)

    def test_workers_keep_cpu_under_the_limit(self):
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "a") as fh:
            fh.write("weight.related=3 s 100 MB\n")
        r = self.run_test("related", "python3", "-c", "import sys; print('W=' + sys.argv[1])", "{workers}",
                          env=self.env(AGENT_FAKE_CPU="20", AGENT_FAKE_CORES="8"))
        self.assertIn("W=4", r.stdout)                                   # 8 x (80 - 20) / 100 = 4.8 -> 4

    def test_no_slot_files_any_more(self):
        self.run_test("related", "true")
        self.assertFalse(os.path.exists(os.path.join(self.gitdir(), "agent_heavy_slots")))

    def test_a_run_never_writes_the_tracked_repo_file(self):
        with open(os.path.join(self.repo.dir, "agent_repo.conf")) as fh:
            before = fh.read()
        self.run_test("related", "true")
        self.run_test("related", "true")
        with open(os.path.join(self.repo.dir, "agent_repo.conf")) as fh:
            self.assertEqual(fh.read(), before)

    def test_peak_mb_is_the_whole_process_tree(self):
        child = "import os, time; b = os.urandom(60 * 1024 * 1024); time.sleep(3)"
        cmd = ("import subprocess, sys; ps = [subprocess.Popen([sys.executable, '-c', %r]) for _ in range(3)]; "
               "[p.wait() for p in ps]" % child)
        self.assertEqual(self.run_test("tree", "python3", "-c", cmd).returncode, 0)
        self.assertGreaterEqual(int(self.weight("tree").split()[2]), 150, self.weight("tree"))

    def test_unknown_ram_fails_closed(self):
        r = self.run_test("related", "true", env=self.env(ram="-1"))
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("RAM unknown", r.stdout + r.stderr)

    def test_the_exit_code_is_the_commands(self):
        self.assertEqual(self.run_test("related", "python3", "-c", "import sys; sys.exit(5)").returncode, 5)

    def test_constants(self):
        sys.path.insert(0, BIN)
        import agent_conf
        self.assertEqual((agent_conf.CONSTANTS["light_test_s"], agent_conf.CONSTANTS["light_test_mb"]), (120, 1024))
        self.assertNotIn("heavy_test_slots", [x["key"] for x in agent_conf.SETTINGS])


if __name__ == "__main__":
    unittest.main()
