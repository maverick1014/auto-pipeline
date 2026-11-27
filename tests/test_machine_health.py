"""machine-health (requirements/machine-health.md): the four examples, plus the remote path and the watch line.

Every test works in its own temp folder (TMPDIR points at it); nothing here reads or removes real temp files.
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
ROOM = os.path.join(BIN, "agent-room.sh")
sys.path.insert(0, BIN)


def age(path, hours):
    t = time.time() - hours * 3600
    for root, dirs, names in os.walk(path, topdown=False):
        for n in names + dirs:
            os.utime(os.path.join(root, n), (t, t), follow_symlinks=False)
    os.utime(path, (t, t))


class Case(unittest.TestCase):

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="mh_fixture_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.procs = []
        self.addCleanup(self.stop)

    def stop(self):
        for p in self.procs:
            p.kill()
            p.wait()

    def env(self, **extra):
        e = dict(os.environ, TMPDIR=self.tmp, AGENT_RESERVE_FILE=os.path.join(self.tmp, "reserve.json"),
                 AGENT_FAKE_RAM="10", AGENT_FAKE_RAM_TOTAL_MB="8192")
        e.update(extra)
        return e

    def room(self, *args, **extra):
        return subprocess.run([ROOM] + list(args), env=self.env(**extra), capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=60)

    def folder(self, name, files=3, hours=0):
        path = os.path.join(self.tmp, name)
        os.makedirs(path)
        for i in range(files):
            with open(os.path.join(path, "f%d" % i), "w") as fh:
                fh.write("x" * 100)
        if hours:
            age(path, hours)
        return path


class TestHealth(Case):

    def test_health_names_swap_cpu_biggest_processes_and_tmpdir_by_kind(self):
        self.folder("jest_dy", files=40)
        self.folder("check-blocks-demo.x", files=5)
        r = self.room("health", AGENT_FAKE_SWAP="4608/5120", AGENT_FAKE_CPU_IDLE="2")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertIn("memory in use: 10%", out)
        self.assertIn("swap used: 4608 / 5120 MB (90%)", out)
        self.assertIn("CPU idle: 2%", out)
        self.assertIn("biggest processes", out)
        self.assertEqual(len([l for l in out.splitlines() if " pid " in l]), 5)
        rows = [l for l in out.splitlines() if l.startswith("  jest_dy") or l.startswith("  check-blocks-demo.*")]
        self.assertTrue(rows[0].startswith("  jest_dy | other | 1 | 40 |"), rows)       # most files first, owner other
        self.assertIn("check-blocks-demo.* | this repo", rows[1])
        self.assertIn("TMPDIR %s: 45 files" % self.tmp, out)

    def test_health_changes_nothing(self):
        self.folder("check-blocks-demo.old", hours=9)
        before = sorted(os.listdir(self.tmp))
        self.room("health")
        self.assertEqual(sorted(os.listdir(self.tmp)), before)


class TestCheckLimits(Case):

    def test_cpu_idle_under_20_refuses_and_names_it(self):
        r = self.room("check", "600", AGENT_FAKE_CPU_IDLE="2", AGENT_FAKE_SWAP="100/5120")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), "ROOM: no: CPU idle 2% (< 20%)")

    def test_swap_over_90_refuses_and_names_it(self):
        r = self.room("check", "600", AGENT_FAKE_CPU_IDLE="80", AGENT_FAKE_SWAP="4800/5120")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), "ROOM: no: swap 94% used (> 90%)")

    def test_both_named_on_one_line(self):
        r = self.room("check", "600", AGENT_FAKE_CPU_IDLE="1", AGENT_FAKE_SWAP="5000/5120")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), "ROOM: no: CPU idle 1% (< 20%); swap 98% used (> 90%)")

    def test_within_the_limits_is_ok(self):
        r = self.room("check", "600", AGENT_FAKE_CPU_IDLE="20", AGENT_FAKE_SWAP="4608/5120")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "ROOM: ok"))

    def test_no_swap_at_all_is_not_over_the_limit(self):
        r = self.room("check", "600", AGENT_FAKE_CPU_IDLE="50", AGENT_FAKE_SWAP="0/0")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_memory_refusal_keeps_its_own_line(self):
        r = self.room("check", "600", AGENT_FAKE_RAM="95", AGENT_FAKE_CPU_IDLE="2")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MB in use", r.stdout)
        self.assertNotIn("CPU idle", r.stdout)

    def test_unreadable_cpu_and_swap_do_not_refuse(self):
        r = self.room("check", "600")          # a fake RAM and no fake CPU or swap: unknown, never refuses
        self.assertEqual(r.returncode, 0, r.stdout)


class TestSweep(Case):

    def sweep(self, *args):
        return self.room("sweep", *args)

    def test_old_unused_kind_removed_young_one_and_other_kept(self):
        old = self.folder("check-blocks-demo.x", hours=4)
        young = self.folder("check-blocks-demo.y", hours=1)
        other = self.folder("jest_dy", hours=4)
        r = self.sweep("--apply")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.isdir(young))
        self.assertTrue(os.path.isdir(other))
        self.assertIn("removed check-blocks-demo.x", r.stdout)

    def test_every_kind_of_this_repo_is_swept(self):
        names = ["check-blocks-demo.a", "auto_pipeline_a", "auto_pipeline_b.equiv-snap", "cloud_pack_a",
                 "run2_a", "agent_test_tools_a"]
        paths = [self.folder(n, hours=5) for n in names]
        self.sweep("--apply")
        self.assertEqual([p for p in paths if os.path.exists(p)], [])

    def test_without_apply_it_only_lists(self):
        old = self.folder("auto_pipeline_old", hours=4)
        r = self.sweep()
        self.assertTrue(os.path.isdir(old))
        self.assertIn("would remove auto_pipeline_old", r.stdout)

    def test_a_folder_a_live_process_works_in_is_kept(self):
        old = self.folder("cloud_pack_busy", hours=4)
        self.procs.append(subprocess.Popen(["sleep", "60"], cwd=old))
        gone = self.folder("cloud_pack_idle", hours=4)
        time.sleep(0.3)
        r = self.sweep("--apply")
        self.assertTrue(os.path.isdir(old), r.stdout)
        self.assertFalse(os.path.exists(gone))
        self.assertIn("kept cloud_pack_busy", r.stdout)

    def test_a_folder_named_in_a_live_command_line_is_kept(self):
        old = self.folder("auto_pipeline_args", hours=4)
        self.procs.append(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", old + "/x"], cwd="/"))
        time.sleep(0.3)
        self.sweep("--apply")
        self.assertTrue(os.path.isdir(old))

    def test_a_run2_folder_of_a_live_run_is_kept(self):
        old = self.folder("run2_live", hours=4)
        p = subprocess.Popen(["sleep", "60"], cwd="/")
        self.procs.append(p)
        with open(os.path.join(old, ".run2_owner"), "w") as fh:
            fh.write('{"pid": %d, "start": "x"}' % p.pid)
        age(old, 4)
        self.sweep("--apply")
        self.assertTrue(os.path.isdir(old))

    def test_a_young_file_deep_inside_keeps_the_folder(self):
        old = self.folder("auto_pipeline_deep", hours=4)
        os.makedirs(os.path.join(old, "a", "b"))
        with open(os.path.join(old, "a", "b", "fresh"), "w") as fh:
            fh.write("now")
        self.sweep("--apply")
        self.assertTrue(os.path.isdir(old))

    def test_a_link_is_never_followed_or_removed(self):
        target = self.folder("jest_dy", hours=4)
        link = os.path.join(self.tmp, "cloud_pack_link")
        os.symlink(target, link)
        os.utime(link, (time.time() - 5 * 3600,) * 2, follow_symlinks=False)
        self.sweep("--apply")
        self.assertTrue(os.path.islink(link))
        self.assertTrue(os.path.isdir(target))

    def test_hours_can_be_set(self):
        young = self.folder("cloud_pack_one_hour", hours=1)
        self.sweep("--apply", "--hours", "0.5")
        self.assertFalse(os.path.exists(young))


class TestTestsCleanUp(Case):
    """test_check_blocks_demo, green or red, leaves no check-blocks-demo.* folder."""

    def run_test(self, demo_body):
        demo = os.path.join(self.tmp, "fake_demo.sh")
        with open(demo, "w") as fh:
            fh.write("#!/usr/bin/env bash\nT=$(mktemp -d \"${TMPDIR:-/tmp}/check-blocks-demo.XXXXXX\")\n"
                     "echo filler > $T/file\n" + demo_body)
        os.chmod(demo, stat.S_IRWXU)
        run_tmp = os.path.join(self.tmp, "run")
        os.makedirs(run_tmp)
        r = subprocess.run([sys.executable, "-m", "unittest", "tests.test_check_blocks_demo"], cwd=ROOT,
                           env=dict(os.environ, AGENT_FULL_RUN="1", AGENT_DEMO_SCRIPT=demo, TMPDIR=run_tmp),
                           capture_output=True, text=True, timeout=120)
        return r, [n for n in os.listdir(run_tmp) if n.startswith("check-blocks-demo")]

    def test_green_run_leaves_nothing(self):
        r, left = self.run_test('say() { echo "$@"; }\necho "===== done: everything above ran in $T (delete it when read)"\nexit 1\n')
        self.assertEqual(left, [], r.stderr[-800:])

    def test_red_run_with_no_done_line_leaves_nothing(self):
        r, left = self.run_test("exit 3\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(left, [], r.stderr[-800:])

    def test_a_timeout_leaves_nothing(self):
        demo = os.path.join(self.tmp, "slow.sh")
        with open(demo, "w") as fh:
            fh.write("#!/usr/bin/env bash\nmkdir \"${TMPDIR}/check-blocks-demo.slow\"\nsleep 30\n")
        os.chmod(demo, stat.S_IRWXU)
        run_tmp = os.path.join(self.tmp, "run")
        os.makedirs(run_tmp)
        code = ("import os, sys, unittest, subprocess\n"
                "import tests.test_check_blocks_demo as m\n"
                "real = subprocess.run\n"
                "m.subprocess.run = lambda *a, **k: real(*a, **dict(k, timeout=2))\n"
                "unittest.main(module=m, argv=['x'])\n")
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, AGENT_FULL_RUN="1", AGENT_DEMO_SCRIPT=demo, TMPDIR=run_tmp))
        self.assertEqual([n for n in os.listdir(run_tmp) if n.startswith("check-blocks-demo")], [])


class FakeOrca(Case):
    """An `orca` that answers the calls remote_exec makes and RUNS the line sent to the terminal here, so the
    real payload (this file's text, compressed) is what runs."""

    def setUp(self):
        super().setUp()
        self.bin = os.path.join(self.tmp, "stub")
        os.makedirs(self.bin)
        self.out = os.path.join(self.tmp, "term.out")
        self.log = os.path.join(self.tmp, "orca.log")
        with open(os.path.join(self.bin, "orca"), "w") as fh:
            fh.write(FAKE_ORCA)
        os.chmod(os.path.join(self.bin, "orca"), stat.S_IRWXU)
        self.remote_tmp = os.path.join(self.tmp, "remote_tmp")
        os.makedirs(self.remote_tmp)

    def env(self, **extra):
        e = super().env(**extra)
        e.update(PATH=self.bin + os.pathsep + os.environ["PATH"], FAKE_OUT=self.out, FAKE_LOG=self.log,
                 FAKE_REMOTE_TMP=self.remote_tmp, FAKE_ROOT=ROOT)
        return e

    def calls(self):
        with open(self.log) as fh:
            return [l.strip() for l in fh]


FAKE_ORCA = r'''#!/usr/bin/env python3
import json, os, subprocess, sys
a = sys.argv[1:]
open(os.environ["FAKE_LOG"], "a").write(" ".join(a[:2]) + " " + " ".join(x for x in a if x.startswith("--environment") or x == "pc2") + "\n")
def ok(r): print(json.dumps({"ok": True, "result": r})); sys.exit(0)
if a[:2] == ["environment", "list"]:
    ok({"environments": [{"name": "pc2"}]})
if a[:2] == ["worktree", "list"]:
    if os.environ.get("FAKE_NOMAIN") and "--environment" in a:
        ok({"worktrees": []})
    ok({"worktrees": [{"path": os.environ["FAKE_ROOT"], "isMainWorktree": True, "projectId": "p1"}]})
if a[:2] == ["terminal", "create"]:
    ok({"terminal": {"handle": "term_1"}})
if a[:2] == ["terminal", "send"]:
    text = a[a.index("--text") + 1]
    env = dict(os.environ, TMPDIR=os.environ["FAKE_REMOTE_TMP"])
    r = subprocess.run(["bash", "-c", text], capture_output=True, text=True, env=env)
    open(os.environ["FAKE_OUT"], "w").write(text[:60] + "\n" + r.stdout + r.stderr)
    ok({})
if a[:2] == ["terminal", "read"]:
    lines = open(os.environ["FAKE_OUT"]).read().splitlines() if os.path.exists(os.environ["FAKE_OUT"]) else []
    ok({"terminal": {"tail": lines}})
if a[:2] == ["terminal", "close"]:
    ok({})
sys.stderr.write("fake orca: " + " ".join(a) + "\n"); sys.exit(1)
'''


class TestRemote(FakeOrca):

    def test_remote_sweep_runs_this_file_on_the_connected_machine(self):
        import agent_health
        old = os.path.join(self.remote_tmp, "check-blocks-demo.far")
        os.makedirs(old)
        age(old, 6)
        keep = os.path.join(self.remote_tmp, "jest_dy")
        os.makedirs(keep)
        age(keep, 6)
        os.environ.update(self.env())
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in ("FAKE_OUT", "FAKE_LOG", "FAKE_REMOTE_TMP", "FAKE_ROOT")])
        self.assertEqual(agent_health.environments(), ["pc2"])
        ok, lines = agent_health.remote_exec("pc2", ROOT, ["sweep", "--apply"], wait_s=20)
        self.assertTrue(ok, lines)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.isdir(keep))
        self.assertTrue(any("removed 1 of this repo's temp folders" in l for l in lines), lines)
        self.assertTrue(any(c.startswith("terminal close") for c in self.calls()))

    def test_remote_without_a_checkout_says_so(self):
        import agent_health
        os.environ.update(self.env(FAKE_NOMAIN="1"))
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in ("FAKE_OUT", "FAKE_LOG", "FAKE_REMOTE_TMP", "FAKE_ROOT", "FAKE_NOMAIN")])
        ok, lines = agent_health.remote_exec("pc2", ROOT, ["limits"], wait_s=5)
        self.assertFalse(ok)
        self.assertIn("no checkout of this repo", lines[0])
        self.assertFalse(any(c.startswith("terminal") for c in self.calls()))


if __name__ == "__main__":
    unittest.main()
