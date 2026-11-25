"""Failing tests for check-blocks section 46: FIX ORDER 5 of the main manager (TELL ed67796b), C13-C21.
Written by the task manager before any fix.

Run: python3 -m unittest tests.test_check_fix_order5
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
BIN = os.path.join(ROOT, "bin")
import test_agent_autoclear as ac  # noqa: E402
import test_check_clear as tcc  # noqa: E402
import test_check_fix_order2 as fo2  # noqa: E402
import test_agent_owner_order as oo  # noqa: E402
import test_agent_resume as tr  # noqa: E402

only_own = fo2.only_own
wait_until = fo2.wait_until
gone = fo2.gone


def waiter_stub_with_wait_hook():
    """The waiter's orca stub, plus $ORCA_STUB_DIR/wait_hook.sh run with the number of each wait call."""
    a = '''  "terminal wait")\n'''
    assert ac.WAITER_STUB.count(a) == 1
    return ac.WAITER_STUB.replace(a, a + '''    wn=$(cat "$d/wait_n" 2>/dev/null || echo 0); wn=$((wn+1)); echo "$wn" > "$d/wait_n"
    [ -f "$d/wait_hook.sh" ] && bash "$d/wait_hook.sh" "$wn"
''')


# ====================================================================== C13 the gate runs again when ready waited


@only_own
class TestC13GateAgainAfterAWait(tcc.TestWaiterWaitsForTheHuman):
    def setUp(self):
        super().setUp()
        with open(self.stub, "w") as fh:
            fh.write(waiter_stub_with_wait_hook())

    def test_a_human_prompt_during_the_save_turn_stops_the_clear(self):
        self.t.write([oo.owner("ok go", tcc.ago(40))])
        human_now = json.dumps(oo.owner("wait, one more thing", tcc.T0))
        # the 2nd wait is the save turn: the human types during it, and it takes 3 s (ready waited)
        self.stub_file("wait_hook.sh", '[ "$1" = 2 ] && { printf "%%s\\n" %s >> %s; /bin/sleep 3; }\nexit 0\n'
                       % ("'" + human_now + "'", os.path.join(self.t.dir, "s1.jsonl")))
        self.start()
        self.assertTrue(wait_until(lambda: self.waiting_line(), 20), (self.sends(), self.state_lines()))
        time.sleep(2)
        self.assertEqual(self.sends(), [ac.SAVE], "no /clear after a human prompt in the save turn")

    def test_a_humans_pane_is_cleared_when_quiet(self):
        # C21: the whole waiter on a human's pane (no --spawned)
        self.t.write([oo.owner("ok go", tcc.ago(40))])
        r = self.repo.run("agent-autoclear.sh", ac.HANDLE, "s1", env=self.env(), timeout=60)
        self.assertOk(r)
        self.assertEqual(self.sends(), [ac.SAVE, "/clear", ac.CONT])


class TestC13PinnedOrder(ac.ClearCase):
    script = "agent-autoclear.sh"

    def test_gate_and_ready_before_every_typed_text(self):
        self.repo.stub_tool("sleep", '#!/bin/bash\n[ "$1" = 30 ] && exec /bin/sleep 1\nexec /bin/sleep "$@"\n')
        self.repo.write_bin_script("agent-owner-order.sh",
                                   "#!/usr/bin/env bash\nprintf 'CALL\\thuman-quiet\\n' >> \"$ORCA_STUB_LOG\"\n"
                                   "echo quiet\nexit 0\n")
        self.write_state(["ROLE: x", ""])
        self.assertOk(self.waiter())
        seq = [c[1] if c[0] == "terminal" else c[0] for c in self.calls()]
        self.assertEqual(seq, ["human-quiet", "wait", "read", "send"] * 3)


# ====================================================================== C14-C16 relief


class TestC14C15C16(fo2.Room):
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


# ====================================================================== C17 one step, and a task manager measures


class TestC17PaneReservation(fo2.Room):
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


@only_own
class TestC17ResumeReserves(tr.TestRoomForPanes):
    def test_a_relaunched_pane_is_reserved_by_its_handle(self):
        paths = self.setup_room(dead=1)
        out = self.assertOk(self.resume(env=self.env()))
        self.assertEqual(self.relaunched_for(out, paths[0]), "yes")
        path = self.env()["AGENT_RESERVE_FILE"]
        jobs = json.load(open(path)).get("jobs", []) if os.path.exists(path) else []
        self.assertTrue([j for j in jobs if j.get("handle") and j.get("kind") == "pane"], jobs)


# ====================================================================== C18-C20 the nightly


@only_own
class TestC18ConnectedMachineFirst(fo2.Nightly):
    def test_with_a_connected_machine_nothing_runs_locally(self):
        with open(os.path.join(self.repo.orca_dir, "envs.json"), "w") as fh:
            json.dump({"environments": [{"name": "pc1"}]}, fh)
        e = {"AGENT_FAKE_NOW": "2026-11-25 23:00", "CLAUDE_PID": str(os.getpid()), "AGENT_FAKE_HOST": "pc2"}
        e.update(self.env())
        r = self.repo.run("agent-start.sh", stdin='{"cwd": "%s", "source": "startup"}' % self.repo.dir, env=e)
        self.assertIn("NIGHTLY: due: a connected machine runs it (W7): agent-nightly.sh --start there", r.stdout)
        time.sleep(2)
        self.assertEqual(self.status(), {})


@only_own
class TestC19FailuresStop(fo2.Nightly):
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
class TestC20StoppedIsNotDone(fo2.Nightly):
    def test_a_stopped_run_is_due_again(self):
        with open(os.path.join(self.gitdir(), "agent_nightly.json"), "w") as fh:
            json.dump({"started": "2026-11-25 22:30", "commit": self.git("rev-parse", "HEAD"),
                       "finished": "2026-11-25 22:31", "result": "stopped", "failed": []}, fh)
        r = self.nightly("--due", env={"AGENT_FAKE_NOW": "2026-11-25 23:00"})
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
