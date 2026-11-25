"""Failing tests for check-blocks section 43: FIX ORDER 2 of the main manager (TELL d6040ada), C1-C12.
Written by the task manager before any fix.

Run: python3 -m unittest tests.test_check_fix_order2
"""

import glob
import json
import os
import signal
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import test_check_net as tn  # noqa: E402
import test_agent_autoclear as ac  # noqa: E402
import test_check_clear as tcc  # noqa: E402
import test_agent_resume as tr  # noqa: E402
import test_agent_owner_order as oo  # noqa: E402


def only_own(cls):
    own = set(vars(cls))
    for name in dir(cls):
        if name.startswith("test") and name not in own:
            setattr(cls, name, None)
    return cls


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


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


class Room(tn.RoomCase):
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


# ====================================================================== C1 relief signals only its own runs


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


# ====================================================================== C2, C4, C11 the nightly


class Nightly(tn.TestNightly):
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
        self.set_full("python3 -c \"import os, time; b = os.urandom(60 * 1024 * 1024); time.sleep(1.5)\"")
        r = self.nightly("--start", "--wait", env=self.env())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
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


class TestC4TestRunSignals(Room):
    def test_sigint_and_sighup_stop_the_child_group(self):
        for sig, marker in ((signal.SIGINT, "34.2"), (signal.SIGHUP, "34.4")):
            with self.subTest(sig=sig):
                p = self.runner(marker)
                os.kill(p.pid, sig)
                self.assertTrue(wait_until(lambda: p.poll() is not None, 6))
                self.assertTrue(gone("sleep " + marker), "the child kept running")
                self.assertFalse([j for j in self.jobs() if j.get("pid") == p.pid])


# ====================================================================== C3 the automatic start needs room


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


# ====================================================================== C5 --failures


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


# ====================================================================== C6 counted once


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


# ====================================================================== C7 a new pane is reserved


class TestC7PaneReservation(Room):
    def test_reserve_pane_until_measured(self):
        self.assertEqual(self.room("reserve-pane", "term_x", "550").returncode, 0)
        self.assertIn("term_x", self.room("list").stdout)
        self.assertEqual(self.room("check", "3500").returncode, 1)       # 4000 + 550 + 3500 > 8000
        p = self.sleeper()
        self.room("measure-pane", str(p.pid), ORCA_TERMINAL_HANDLE="term_x")
        self.assertNotIn("term_x", self.room("list").stdout)

    def test_an_old_pane_reservation_expires(self):
        self.write_jobs([{"handle": "term_old", "mb": 3000, "kind": "pane", "by": "launch",
                          "started": time.time() - 16 * 60, "since": "x"}])
        self.assertEqual(self.room("check", "3500").returncode, 0)

    def test_resume_and_dispatch_reserve_their_panes(self):
        self.assertIn("reserve-pane", read("bin", "agent-resume.sh"))
        self.assertIn("agent-room.sh reserve-pane", read("skills", "dispatch", "SKILL.md"))


# ====================================================================== C8, C9 the auto clear


class TestC8GateBeforeReady(ac.ClearCase):
    script = "agent-autoclear.sh"

    def test_the_gate_comes_before_each_ready(self):
        self.repo.stub_tool("sleep", '#!/bin/bash\n[ "$1" = 30 ] && exec /bin/sleep 1\nexec /bin/sleep "$@"\n')
        self.repo.write_bin_script("agent-owner-order.sh",
                                   "#!/usr/bin/env bash\nprintf 'CALL\\thuman-quiet\\n' >> \"$ORCA_STUB_LOG\"\n"
                                   "echo quiet\nexit 0\n")
        self.write_state(["ROLE: x", ""])
        self.assertOk(self.waiter())
        seq = [c[1] if c[0] == "terminal" else c[0] for c in self.calls()]
        # section 46 C13: the gate also runs before /goal; the order per typed text is gate, ready, type
        self.assertEqual(seq, ["human-quiet", "wait", "read", "send"] * 3)


@only_own
class TestC9UnknownIsNotQuiet(tcc.TestHumanQuiet):
    def test_no_transcript_is_unknown(self):
        r = self.quiet()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertTrue(r.stdout.strip().startswith("unknown: "), r.stdout)


@only_own
class TestC9TheWaiter(tcc.TestWaiterWaitsForTheHuman):
    def test_a_human_session_waits_on_unknown(self):
        proc = self.start()                                               # no --spawned, no transcript
        line = "AUTO CLEAR waiting: the transcript of this session cannot be read"
        self.assertTrue(wait_until(lambda: any(l.startswith(line) for l in self.state_lines()), 15),
                        self.state_lines())
        time.sleep(2)
        self.assertEqual(self.sends(), [])

    def test_a_spawned_task_manager_is_cleared_as_today(self):
        r = self.repo.run("agent-autoclear.sh", ac.HANDLE, "s1", "--spawned", env=self.env(), timeout=60)
        self.assertOk(r)
        self.assertEqual(self.sends(), [ac.SAVE, "/clear", ac.CONT])

    def test_the_start_passes_spawned_for_a_task_manager(self):
        self.assertIn("--spawned", read("bin", "agent-start.sh"))


# ====================================================================== C10 a corrupt list


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


# ====================================================================== C12 memory unknown


@only_own
class TestC12MemoryUnknown(tr.TestRoomForPanes):
    def test_memory_unknown_relaunches_nothing(self):
        paths = self.setup_room(dead=1)
        out = self.assertOk(self.resume(env=self.env(ram="-1")))
        self.assertEqual(self.relaunched_for(out, paths[0]), "no, no room")
        self.assertIn("no room (memory unknown), not relaunching %s" % paths[0], out)
        self.assertEqual(self.repo.create_calls(), [])


if __name__ == "__main__":
    unittest.main()
