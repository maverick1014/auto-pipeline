"""Tests of agent-room, one class per feature."""

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
from scripthelp import ScriptCase  # noqa: E402
import glob  # noqa: E402
import signal  # noqa: E402
import time  # noqa: E402


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


def lstart(pid):
    # section 46 C14: the start time does not depend on locale or TZ
    env = dict(os.environ, LC_ALL="C", LANG="C", TZ="UTC")
    return subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True,
                          env=env).stdout.strip()


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


class Room(RoomCase):
    def room(self, *args, ram="40", **env):
        return self.repo.run("agent-room.sh", *args, env=self.env(ram=ram, **env))

    def name(self):
        return os.path.basename(self.git("rev-parse", "--show-toplevel"))

    def write_jobs(self, jobs):
        with open(self.reserve, "w") as fh:
            json.dump({"jobs": jobs}, fh)

    def sleeper(self, secs="30"):
        p = subprocess.Popen(["sleep", secs])
        self.addCleanup(p.kill)
        return p

    def runner(self, marker):
        p = self.repo.popen("agent-test-run.sh", "--key", "c-" + marker.replace(".", "-"), "--", "sleep", marker,
                            env=self.env())
        self.addCleanup(lambda: p.poll() is None and p.kill())
        self.assertTrue(wait_until(lambda: any(j.get("pid") == p.pid for j in self.jobs())), self.jobs())
        return p


class TestC1Relief(Room):
    def test_a_hand_reserved_process_is_never_signalled(self):
        p = self.hold(1500, "related", "--kind", "test", "--unmeasured")
        self.room("relief", ram="90")
        time.sleep(1)
        self.assertIsNone(p.poll(), "relief signalled a process the runner did not start")

    def test_a_reused_pid_is_pruned_never_signalled(self):
        p = self.sleeper()
        self.write_jobs([{"pid": p.pid, "mb": 1500, "what": "related", "repo": self.name(), "since": "x",
                          "started": time.time(), "kind": "test", "measured": False, "by": "runner",
                          "start": "Thu Jan  1 00:00:00 2015"}])
        self.room("relief", ram="90")
        time.sleep(1)
        self.assertIsNone(p.poll(), "relief signalled a pid that now belongs to another process")
        self.assertEqual(self.jobs(), [], "the stale entry is pruned")

    def test_another_repos_run_is_never_signalled(self):
        p = self.sleeper()
        self.write_jobs([{"pid": p.pid, "mb": 1500, "what": "related", "repo": "some-other-repo", "since": "x",
                          "started": time.time(), "kind": "test", "measured": False, "by": "runner",
                          "start": lstart(p.pid)}])
        self.room("relief", ram="90")
        time.sleep(1)
        self.assertIsNone(p.poll())

    def test_this_repos_runner_is_stopped(self):
        p = self.runner("33.1")
        entry = [j for j in self.jobs() if j.get("pid") == p.pid][0]
        self.assertEqual(entry.get("by"), "runner")
        self.assertEqual(entry.get("start"), lstart(p.pid))
        r = self.room("relief", ram="90", AGENT_FAKE_HOST="pc2")
        self.assertIn("stopped 1 test runs (%d)" % p.pid, r.stdout)
        self.assertTrue(wait_until(lambda: p.poll() is not None, 6))
        self.assertTrue(gone("sleep 33.1"), "the runner's child was left running")


class TestC4TestRunSignals(Room):
    def test_sigint_and_sighup_stop_the_child_group(self):
        for sig, marker in ((signal.SIGINT, "34.2"), (signal.SIGHUP, "34.4")):
            with self.subTest(sig=sig):
                p = self.runner(marker)
                os.kill(p.pid, sig)
                self.assertTrue(wait_until(lambda: p.poll() is not None, 6))
                self.assertTrue(gone("sleep " + marker), "the child kept running")
                self.assertFalse([j for j in self.jobs() if j.get("pid") == p.pid])


class TestC6CountedOnce(Room):
    def test_a_reserved_running_job_is_not_counted_twice(self):
        p = subprocess.Popen([sys.executable, "-c", "import os, time; b = os.urandom(300 * 1024 * 1024); "
                                                    "time.sleep(30)"])
        self.addCleanup(p.kill)
        time.sleep(2)
        self.room("reserve", str(p.pid), "300", "a build", "--kind", "build")
        r = self.room("check", "3900")                                   # 4000 - ~300 + 300 + 3900 <= 8000
        self.assertEqual(r.returncode, 0, r.stdout)
        used = int(self.room("numbers").stdout.split()[0])
        self.assertLessEqual(used, 3750)


class TestC10CorruptList(Room):
    def test_it_is_moved_aside_not_erased(self):
        with open(self.reserve, "w") as fh:
            fh.write("not json {")
        p = self.sleeper()
        r = self.room("reserve", str(p.pid), "100", "x")
        self.assertIn("RESERVATIONS: %s could not be read; moved to " % self.reserve, r.stdout + r.stderr)
        aside = glob.glob(self.reserve + ".corrupt-*")
        self.assertEqual(len(aside), 1)
        with open(aside[0]) as fh:
            self.assertEqual(fh.read(), "not json {")
        self.assertEqual([j.get("pid") for j in self.jobs()], [p.pid])


ROOT = os.path.dirname(HERE)


class TestC14C15C16(Room):
    def nightly(self):
        sys.path.insert(0, BIN)
        import agent_nightly
        return agent_nightly

    def test_c14_the_start_time_does_not_depend_on_locale_or_tz(self):
        an = self.nightly()
        p = self.sleeper()
        old = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(old)))
        os.environ.update({"LANG": "C", "LC_ALL": "C", "TZ": "UTC"})
        a = an.proc_start(p.pid)
        os.environ.update({"LANG": "fr_FR.UTF-8", "LC_ALL": "fr_FR.UTF-8", "TZ": "Asia/Tokyo"})
        b = an.proc_start(p.pid)
        self.assertTrue(a)
        self.assertEqual(a, b)

    def test_c14_unknown_is_never_pruned_nor_signalled(self):
        p = self.sleeper()
        root = self.git("rev-parse", "--show-toplevel")
        self.write_jobs([{"pid": p.pid, "mb": 1500, "what": "related", "repo": root, "since": "x",
                          "started": time.time(), "kind": "test", "measured": False, "by": "runner", "start": ""}])
        self.room("relief", ram="90")
        time.sleep(1)
        self.assertIsNone(p.poll())
        self.assertEqual([j.get("pid") for j in self.jobs()], [p.pid])

    def test_c15_a_run_in_a_task_worktree_is_this_repos(self):
        wt = os.path.join(self.repo.base, "task_wt")
        self.git("worktree", "add", "-q", "--detach", wt, "HEAD")
        p = self.repo.popen("agent-test-run.sh", "--key", "wt-run", "--", "sleep", "36.6", env=self.env(), cwd=wt)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        self.assertTrue(wait_until(lambda: any(j.get("pid") == p.pid for j in self.jobs())), self.jobs())
        self.room("relief", ram="90")
        self.assertTrue(wait_until(lambda: p.poll() is not None, 6), "the main manager's relief left it running")
        self.assertTrue(gone("sleep 36.6"))

    def test_c15_another_repo_with_the_same_folder_name_is_not(self):
        an = self.nightly()
        p = self.sleeper()
        name = os.path.basename(self.git("rev-parse", "--show-toplevel"))
        self.write_jobs([{"pid": p.pid, "mb": 1500, "what": "related", "repo": "/somewhere/else/" + name,
                          "since": "x", "started": time.time(), "kind": "test", "measured": False, "by": "runner",
                          "start": an.proc_start(p.pid)}])
        self.room("relief", ram="90")
        time.sleep(1)
        self.assertIsNone(p.poll())

    def test_c16_the_pick_is_a_run_that_can_be_stopped(self):
        an = self.nightly()
        jobs = [{"pid": 1, "kind": "test", "measured": False, "started": 2, "by": "hand"},
                {"pid": 2, "kind": "test", "measured": False, "started": 1, "by": "runner"}]
        self.assertEqual(an.pick_of(jobs)["pid"], 2)


class TestC17PaneReservation(Room):
    def test_no_room_reserves_nothing(self):
        r = self.room("reserve-pane", "term_y", "550", ram="95")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("ROOM: no", r.stdout)
        self.assertNotIn("term_y", self.room("list").stdout)

    def test_a_task_managers_start_measures_and_drops_it(self):
        self.room("reserve-pane", "term_z", "550")
        self.assertIn("term_z", self.room("list").stdout)
        e = self.env()
        e.update({"AGENT_ROLE": "task-manager", "ORCA_TERMINAL_HANDLE": "term_z", "CLAUDE_PID": str(os.getpid()),
                  "AGENT_RUNTIME": "orca"})
        self.repo.run("agent-start.sh", stdin='{"cwd": "%s", "source": "startup"}' % self.repo.dir, env=e)
        self.assertTrue(wait_until(lambda: "term_z" not in self.room("list").stdout, 10))


class TestC26PaneWeight(Room):
    def weights_path(self):
        return os.path.join(self.gitdir(), "agent_test_weights.json")

    def test_the_weight_follows_recent_measurements(self):
        with open(self.weights_path(), "w") as fh:
            json.dump({"pane": "0 s 2000 MB", "pane_recent": [2000, 600, 600, 600, 600]}, fh)
        p = self.sleeper()
        self.room("measure-pane", str(p.pid))
        with open(self.weights_path()) as fh:
            w = json.load(fh)
        self.assertEqual(w["pane"], "0 s 600 MB")
        self.assertEqual(len(w["pane_recent"]), 5)

    def test_a_compaction_start_measures_nothing(self):
        with open(self.weights_path(), "w") as fh:
            json.dump({"pane": "0 s 2000 MB", "pane_recent": [2000]}, fh)
        e = self.env()
        e.update({"ORCA_TERMINAL_HANDLE": "term_c", "CLAUDE_PID": str(os.getpid()), "AGENT_RUNTIME": "orca"})
        self.repo.run("agent-start.sh", stdin='{"cwd": "%s", "source": "compact", "session_id": "s9"}'
                      % self.repo.dir, env=e)
        time.sleep(1)
        with open(self.weights_path()) as fh:
            self.assertEqual(json.load(fh)["pane_recent"], [2000])


class TestC27Expiry(Room):
    def test_an_unverifiable_entry_expires_after_6_hours(self):
        old, young = self.sleeper(), self.sleeper()
        root = self.git("rev-parse", "--show-toplevel")
        base = {"mb": 500, "what": "x", "repo": root, "since": "x", "kind": "test", "measured": True,
                "by": "runner", "start": ""}
        self.write_jobs([dict(base, pid=old.pid, started=time.time() - 7 * 3600),
                         dict(base, pid=young.pid, started=time.time() - 3600)])
        out = self.room("list").stdout
        self.assertNotIn(str(old.pid), out)
        self.assertIn(str(young.pid), out)
        self.assertIsNone(old.poll(), "expired, never signalled")


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


class TestH7ToH9(Room):
    def test_h7_never_below_550(self):
        with open(os.path.join(self.gitdir(), "agent_test_weights.json"), "w") as fh:
            json.dump({"pane_recent": [1, 1, 1, 1]}, fh)
        p = self.sleeper()
        self.room("measure-pane", str(p.pid))
        with open(os.path.join(self.gitdir(), "agent_test_weights.json")) as fh:
            self.assertEqual(json.load(fh)["pane"], "0 s 550 MB")

    def test_h8_a_pending_key_that_exists_is_refused(self):
        self.assertEqual(self.room("reserve-pane", "--pending", "task-a", "550").returncode, 0)
        r = self.room("reserve-pane", "--pending", "task-a", "550")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(self.room("list").stdout.count("task-a"), 1)
        self.assertIn("reserve-pane --pending <task name>", read("skills", "dispatch", "SKILL.md"))

    def test_h9_the_usage(self):
        head = read("bin", "agent-room.sh").split("\nexec ")[0]          # the usage comment of the script
        for phrase in ("reserve-pane --pending", "reserve-pane --name", "release-pane"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, head)
        r = self.repo.run("agent-room.sh", "frobnicate", env=self.env())   # a wrong command prints this script's usage
        out = r.stdout + r.stderr
        self.assertIn("agent-room.sh", out)
        self.assertNotIn("agent-nightly.sh --start", out)
        self.assertIn("reserve-pane --pending", out)
