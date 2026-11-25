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
        self.put({"agent_repo.conf": "version=1\nfull_cmd=python3 -m unittest discover -s tests -t .\n",
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
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "a") as fh:
            fh.write("working_branch=dev\n")
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

    def test_not_due_while_a_heavy_run_holds_a_slot(self):
        slots = os.path.join(self.gitdir(), "agent_heavy_slots")
        os.makedirs(slots, exist_ok=True)
        with open(os.path.join(slots, str(os.getpid())), "w") as fh:
            fh.write("group.src\n")
        self.assertEqual(self.nightly("--due", env={"AGENT_FAKE_NOW": "2026-11-25 23:00"}).returncode, 1)

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


class TestTestRun(NetCase):
    script = "agent-test-run.sh"

    def run_test(self, key, *cmd, env=None):
        e = {"AGENT_TEST_RUN_WAIT_S": "1"}
        e.update(env or {})
        return self.repo.run("agent-test-run.sh", "--key", key, "--", *cmd, env=e, timeout=60)

    def weight(self, key):
        """Core review re-check defect C: measured weights live per machine in
        <git common dir>/agent_test_weights.json ({key: "<s> s <mb> MB"}), never in the tracked repo file."""
        path = os.path.join(self.gitdir(), "agent_test_weights.json")
        if not os.path.exists(path):
            return None
        with open(path) as fh:
            return json.load(fh).get(key)

    def test_a_run_never_writes_the_tracked_repo_file(self):
        with open(os.path.join(self.repo.dir, "agent_repo.conf")) as fh:
            before = fh.read()
        self.run_test("related", "true")
        self.run_test("related", "true")
        with open(os.path.join(self.repo.dir, "agent_repo.conf")) as fh:
            self.assertEqual(fh.read(), before)
        self.assertEqual(self.git("status", "--porcelain", "--", "agent_repo.conf"), "")

    def test_peak_mb_is_the_whole_process_tree(self):
        # re-check defect F: ru_maxrss is one process; 3 children of ~60 MB each are ~180 MB together
        child = "b = bytearray(60 * 1024 * 1024); import time; time.sleep(3)"
        cmd = ("import subprocess, sys; ps = [subprocess.Popen([sys.executable, '-c', %r]) for _ in range(3)]; "
               "[p.wait() for p in ps]" % child)
        self.assertEqual(self.run_test("tree", "python3", "-c", cmd).returncode, 0)
        mb = int(self.weight("tree").split()[2])
        self.assertGreaterEqual(mb, 150, self.weight("tree"))

    def test_unknown_ram_fails_closed(self):
        r = self.run_test("related", "true", env={"AGENT_FAKE_RAM": "-1"})
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("RAM unknown", r.stdout + r.stderr)

    def test_unknown_weight_is_heavy_the_first_time_then_measured(self):
        r = self.run_test("related", "python3", "-c", "print('hi')")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "TEST RUN related: heavy (unknown weight)")
        self.assertIn("hi", r.stdout)
        self.assertRegex(self.weight("related") or "", r"^\d+ s \d+ MB$")
        r = self.run_test("related", "python3", "-c", "print('hi')")
        self.assertRegex(r.stdout.splitlines()[0], r"^TEST RUN related: light \(\d+ s, \d+ MB\)$")

    def test_measured_heavy(self):
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "a") as fh:
            fh.write("weight.group.src=300 s 2048 MB\n")
        r = self.run_test("group.src", "true")
        self.assertEqual(r.stdout.splitlines()[0], "TEST RUN group.src: heavy (300 s, 2048 MB)")

    def test_the_exit_code_is_the_commands(self):
        r = self.run_test("related", "python3", "-c", "import sys; sys.exit(5)")
        self.assertEqual(r.returncode, 5)

    def test_heavy_waits_for_a_free_slot(self):
        slots = os.path.join(self.gitdir(), "agent_heavy_slots")
        os.makedirs(slots, exist_ok=True)
        holders = [subprocess.Popen(["sleep", "30"]) for _ in range(2)]
        for p in holders:
            self.addCleanup(p.kill)
            with open(os.path.join(slots, str(p.pid)), "w") as fh:
                fh.write("full\n")
        r = self.run_test("new", "true")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("no heavy slot free (2 of 2 held)", r.stdout + r.stderr)

    def test_a_dead_holder_frees_its_slot(self):
        slots = os.path.join(self.gitdir(), "agent_heavy_slots")
        os.makedirs(slots, exist_ok=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        for pid in (dead.pid, dead.pid + 100000):
            with open(os.path.join(slots, str(pid)), "w") as fh:
                fh.write("full\n")
        self.assertEqual(self.run_test("new", "true").returncode, 0)

    def test_the_second_heavy_run_needs_half_the_ram_free(self):
        slots = os.path.join(self.gitdir(), "agent_heavy_slots")
        os.makedirs(slots, exist_ok=True)
        holder = subprocess.Popen(["sleep", "30"])
        self.addCleanup(holder.kill)
        with open(os.path.join(slots, str(holder.pid)), "w") as fh:
            fh.write("full\n")
        r = self.run_test("new", "true", env={"AGENT_FAKE_RAM": "60"})
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("RAM 60% used", r.stdout + r.stderr)
        self.assertEqual(self.run_test("new", "true", env={"AGENT_FAKE_RAM": "40"}).returncode, 0)

    def test_light_runs_need_no_slot_but_the_ram_guard(self):
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "a") as fh:
            fh.write("weight.related=3 s 100 MB\n")
        slots = os.path.join(self.gitdir(), "agent_heavy_slots")
        os.makedirs(slots, exist_ok=True)
        holders = [subprocess.Popen(["sleep", "30"]) for _ in range(2)]
        for p in holders:
            self.addCleanup(p.kill)
            with open(os.path.join(slots, str(p.pid)), "w") as fh:
                fh.write("full\n")
        self.assertEqual(self.run_test("related", "true").returncode, 0)
        r = self.run_test("related", "true", env={"AGENT_FAKE_RAM": "95"})
        self.assertEqual(r.returncode, 3)
        self.assertIn("RAM 95% over the 80% cap", r.stdout + r.stderr)

    def test_the_slot_file_goes_after_the_run(self):
        self.run_test("new", "true")
        slots = os.path.join(self.gitdir(), "agent_heavy_slots")
        self.assertEqual(os.listdir(slots) if os.path.isdir(slots) else [], [])

    def test_constants(self):
        sys.path.insert(0, BIN)
        import agent_conf
        self.assertEqual((agent_conf.CONSTANTS["light_test_s"], agent_conf.CONSTANTS["light_test_mb"]), (120, 1024))


if __name__ == "__main__":
    unittest.main()
