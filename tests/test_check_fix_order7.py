"""Failing tests for check-blocks section 48: FIX ORDER 7 of the main manager (TELL a677e9c8), C22-C27.
Written by the task manager before any fix.

Run: python3 -m unittest tests.test_check_fix_order7
"""

import json
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import test_agent_autoclear as ac  # noqa: E402
import test_check_clear as tcc  # noqa: E402
import test_check_fix_order2 as fo2  # noqa: E402
import test_check_fix_order5 as fo5  # noqa: E402
import test_agent_owner_order as oo  # noqa: E402

only_own = fo2.only_own
wait_until = fo2.wait_until
read = fo2.read

REAL_SHAPE = {"id": "req-1", "ok": True,
              "result": {"environments": [{
                  "id": "env-1", "name": "pc1", "createdAt": "2026-11-20T10:00:00Z", "updatedAt": "2026-11-20T10:00:00Z",
                  "pairingRevision": 1, "pairedDeviceId": "dev-1", "lastUsedAt": "2026-11-25T19:00:00Z",
                  "runtimeId": "rt-1", "endpoints": [{"id": "ep-1", "kind": "lan", "label": "pc1",
                                                      "endpoint": "192.168.1.20:7777"}],
                  "preferredEndpointId": "ep-1"}]},
              "_meta": {"version": 1}}


# ====================================================================== C22 every pane


@only_own
class TestC22EveryPane(fo5.TestC13GateAgainAfterAWait):
    def test_a_task_manager_pane_is_not_cleared_after_a_human_prompt(self):
        self.t.write([oo.owner("ok go", tcc.ago(40))])
        human_now = json.dumps(oo.owner("wait, keep going on the report", tcc.T0))
        self.stub_file("wait_hook.sh", '[ "$1" = 2 ] && { printf "%%s\\n" %s >> %s; /bin/sleep 3; }\nexit 0\n'
                       % ("'" + human_now + "'", os.path.join(self.t.dir, "s1.jsonl")))
        proc = self.repo.popen("agent-autoclear.sh", ac.HANDLE, "s1", "--spawned", env=self.env())
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.assertTrue(wait_until(lambda: self.waiting_line(), 20), (self.sends(), self.state_lines()))
        time.sleep(2)
        self.assertEqual(self.sends(), [ac.SAVE], "no /clear after the owner's prompt in a task manager pane")


# ====================================================================== C23 paired and reachable


class Machines(fo2.Nightly):
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


# ====================================================================== C24 counted once


class TestC24ReserveBeforeCreate(fo2.Room):
    def test_pending_then_named(self):
        self.assertEqual(self.room("reserve-pane", "--pending", "k1", "550").returncode, 0)
        self.assertIn("k1", self.room("list").stdout)
        self.assertEqual(self.room("reserve-pane", "--name", "k1", "term_a").returncode, 0)
        out = self.room("list").stdout
        self.assertIn("term_a", out)
        self.assertNotIn("k1", out)

    def test_no_room_before_the_create(self):
        r = self.room("reserve-pane", "--pending", "k2", "550", ram="95")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertNotIn("k2", self.room("list").stdout)

    def test_a_failed_create_releases_it(self):
        self.room("reserve-pane", "--pending", "k3", "550")
        self.assertEqual(self.room("release-pane", "k3").returncode, 0)
        self.assertNotIn("k3", self.room("list").stdout)

    def test_resume_and_dispatch_reserve_before_the_create(self):
        resume = read("bin", "agent-resume.sh")
        self.assertLess(resume.index("reserve-pane --pending"), resume.index("terminal create"))
        self.assertIn("reserve-pane --name", resume)
        d = read("skills", "dispatch", "SKILL.md")
        self.assertLess(d.index("reserve-pane --pending"), d.index("orca terminal create"))


# ====================================================================== C25 the machine the pane runs on


class TestC25RemotePanes(unittest.TestCase):
    def test_texts(self):
        self.assertIn("a pane on another machine is not reserved in the local list", read("skills", "dispatch", "SKILL.md"))
        resume = read("bin", "agent-resume.sh")
        i = resume.index("reserve-pane --pending")
        self.assertRegex(resume[max(0, i - 400):i], r"(env|machine)")


# ====================================================================== C26 measured once, recent weight


class TestC26PaneWeight(fo2.Room):
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


# ====================================================================== C27 unverifiable entries expire


class TestC27Expiry(fo2.Room):
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


if __name__ == "__main__":
    unittest.main()
