"""nightly-on-machine: the full run of a repo on a connected machine, through Orca only (Orca is a stub here).

Requirement: requirements/nightly-on-machine.md. The stub makes a real git worktree for `worktree create`, runs the
text sent to its terminal with bash, and answers `terminal read` with what that printed, so the real remote script runs.
"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
from test_agent_room import NetCase  # noqa: E402

ENV = "box-one"          # a made-up environment name: no real machine name in any test

STUB = r'''#!/usr/bin/env python3
"""Fake orca for the remote full run. State: $ORCA_STUB_DIR/remote/<env>/ (down, create_fail, ran, garbage, hang)."""
import json, os, subprocess, sys

args = sys.argv[1:]
D = os.environ["ORCA_STUB_DIR"]
with open(os.environ["ORCA_STUB_LOG"], "a") as fh:
    fh.write("CALL" + "".join("\t" + a for a in args) + "\n")


def opt(name):
    for i, a in enumerate(args[:-1]):
        if a == name:
            return args[i + 1]
    return None


def ok(result):
    print(json.dumps({"ok": True, "result": result}))
    sys.exit(0)


def fail(text):
    print(json.dumps({"ok": False, "error": {"code": "x", "message": text}}))
    sys.exit(1)


env = opt("--environment")
R = os.path.join(D, "remote", env or "local")
os.makedirs(os.path.join(R, "wts"), exist_ok=True)
if os.path.exists(os.path.join(R, "down")):
    sys.stderr.write("orca: environment %s is not reachable\n" % env)
    sys.exit(1)
verb = " ".join(args[:2])
repo = open(os.path.join(D, "repo")).read().strip()


def wts():
    out = []
    for name in sorted(os.listdir(os.path.join(R, "wts"))):
        out.append({"id": "R::" + os.path.join(R, "wts", name), "path": os.path.join(R, "wts", name),
                    "displayName": name})
    return out


def handle_of(path):
    return "term_" + os.path.basename(path)


if verb == "terminal list":
    sel = opt("--worktree")
    rows = []
    for w in wts():
        if sel is None or sel in ("path:" + w["path"], w["id"]):
            rows.append({"handle": handle_of(w["path"]), "worktreePath": w["path"], "worktreeId": w["id"]})
    ok({"terminals": rows})
elif verb == "worktree list":
    ok({"worktrees": wts()})
elif verb == "worktree create":
    if os.path.exists(os.path.join(R, "create_fail")):
        fail("cannot create the worktree")
    name, base = opt("--name"), opt("--base-branch")
    path = os.path.join(R, "wts", name)
    res = subprocess.run(["git", "-C", repo, "worktree", "add", "--detach", path, base],
                         capture_output=True, text=True)
    if res.returncode != 0:
        fail(res.stderr.strip() or "git worktree add failed")
    head = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    ok({"worktree": {"id": "R::" + path, "path": path, "head": head, "displayName": name,
                     "branch": "refs/heads/x/" + name}})
elif verb == "terminal send":
    path = None
    for w in wts():
        if handle_of(w["path"]) == opt("--terminal"):
            path = w["path"]
    if path is None:
        fail("terminal_handle_stale")
    buf = os.path.join(R, "buf-" + os.path.basename(path))
    if args and "--interrupt" in args:
        with open(os.path.join(R, "interrupted"), "w") as fh:
            fh.write("1")
        ok({})
    if os.path.exists(os.path.join(R, "hang")):
        ok({})
    ran = os.path.join(R, "ran")
    if os.path.exists(ran):
        want = open(ran).read().strip()
        subprocess.run(["git", "-C", path, "checkout", "-q", "--detach", want], capture_output=True)
    run = subprocess.run(["bash", "-c", opt("--text")], cwd=path, capture_output=True, text=True)
    out = run.stdout
    if os.path.exists(os.path.join(R, "garbage")):
        out = "\x1b[31m%%%% nothing you can read\n"
    if os.path.exists(os.path.join(R, "double")):
        extra = [l.replace("exit=1", "exit=0") for l in out.splitlines() if "-RESULT " in l]
        out += "\n".join(extra) + "\n"
    with open(buf, "a") as fh:
        fh.write(out)
    ok({})
elif verb == "terminal read":
    path = None
    for w in wts():
        if handle_of(w["path"]) == opt("--terminal"):
            path = w["path"]
    if path is None:
        fail("terminal_handle_stale")
    buf = os.path.join(R, "buf-" + os.path.basename(path))
    lines = open(buf).read().splitlines() if os.path.exists(buf) else []
    ok({"terminal": {"handle": opt("--terminal"), "status": "running", "tail": lines[-int(opt("--limit") or 120):]}})
elif verb == "terminal close":
    ok({})
elif verb == "worktree rm":
    sel = opt("--worktree") or ""
    path = sel[len("path:"):] if sel.startswith("path:") else sel.split("::", 1)[-1]
    subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", path], capture_output=True)
    ok({"removed": True})
elif verb == "worktree ps":
    for w in wts():
        print(w["displayName"])
    sys.exit(0)
else:
    ok({})
'''


class RemoteCase(NetCase):
    def setUp(self):
        super().setUp()
        self.git("config", "--local", "auto-pipeline.workingbranch", "ap-main-t")
        self.git("checkout", "-q", "-b", "ap-main-t")
        self.repo.stub_tool("orca", STUB)
        with open(os.path.join(self.repo.orca_dir, "repo"), "w") as fh:
            fh.write(self.repo.dir)
        self.where("remote")
        self.addCleanup(self.drop_stub_worktrees)

    def drop_stub_worktrees(self):
        subprocess.run(["git", "-C", self.repo.dir, "worktree", "prune"], capture_output=True)

    def where(self, value, commit=True):
        conf = os.path.join(self.repo.dir, "agent_repo.conf")
        with open(conf) as fh:
            lines = [l for l in fh.read().splitlines() if not l.startswith("full_run_where")]
        if value:
            lines.append("full_run_where=" + value)
        with open(conf, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        if commit:
            self.git("add", "-A")
            self.git("commit", "-q", "-m", "where " + (value or "default"), "--allow-empty")

    def machine(self, name=ENV):
        self.repo.set_conf("full_run_machine", name)

    def remote_dir(self, name=ENV):
        path = os.path.join(self.repo.orca_dir, "remote", name)
        os.makedirs(path, exist_ok=True)
        return path

    def flag(self, name, text="1", env=ENV):
        with open(os.path.join(self.remote_dir(env), name), "w") as fh:
            fh.write(text)

    def nightly(self, *args, env=None):
        extra = {"AGENT_NIGHTLY_POLL_S": "0.1"}
        extra.update(env or {})
        return self.repo.run("agent-nightly.sh", *args, env=extra, timeout=120)

    def status_file(self):
        with open(os.path.join(self.gitdir(), "agent_nightly.json")) as fh:
            return json.load(fh)

    def calls(self):
        try:
            with open(self.repo.orca_log) as fh:
                return [l.rstrip("\n").split("\t")[1:] for l in fh if l.startswith("CALL")]
        except OSError:
            return []

    def verbs(self):
        return [" ".join(c[:2]) for c in self.calls()]

    def left_over(self, env=ENV):
        folder = os.path.join(self.remote_dir(env), "wts")
        return os.listdir(folder) if os.path.isdir(folder) else []


class TestRemoteFullRun(RemoteCase):

    def test_green_on_the_connected_machine(self):
        self.machine()
        head = self.git("rev-parse", "HEAD")
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertEqual((st["result"], st["commit"], st["failed"]), ("green", head, []))
        self.assertEqual(st.get("where"), "connected machine")
        creates = [c for c in self.calls() if c[:2] == ["worktree", "create"]]
        self.assertEqual(len(creates), 1, self.calls())
        self.assertIn(ENV, creates[0])
        self.assertIn(head, creates[0])
        verbs = self.verbs()
        self.assertLess(verbs.index("worktree create"), verbs.index("terminal send"))
        self.assertIn("terminal close", verbs)
        self.assertEqual(verbs[-1], "worktree rm")
        self.assertEqual(self.left_over(), [], "the remote worktree is removed")
        self.assertEqual(self.nightly("--release-ok").returncode, 0)
        self.assertIn("connected machine", self.nightly("--status").stdout)
        self.assertEqual(os.listdir(os.path.join(self.gitdir(), "worktrees")) if os.path.isdir(
            os.path.join(self.gitdir(), "worktrees")) else [], [])

    def test_red_names_the_failing_test_and_publish_is_refused(self):
        self.machine()
        self.put({"src/x.txt": "broken\n"})
        self.git("commit", "-qam", "break")
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertEqual(st["result"], "red")
        self.assertEqual(len(st["failed"]), 1, st)
        self.assertIn("test_x_txt", st["failed"][0])
        out = self.nightly("--failures").stdout
        self.assertIn("test_x_txt", out)
        rel = self.nightly("--release-ok")
        self.assertEqual(rel.returncode, 1, rel.stdout)
        self.assertEqual(self.left_over(), [])

    def test_a_different_commit_is_a_failed_run_never_green(self):
        self.machine()
        asked = self.git("rev-parse", "HEAD")
        self.put({"src/y.txt": "y\n"})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "another")
        other = self.git("rev-parse", "HEAD")
        self.git("reset", "-q", "--hard", asked)
        self.flag("ran", other)
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertEqual(st["result"], "red")
        self.assertEqual(st["failed"], ["the connected machine ran %s, not %s" % (other[:7], asked[:7])])
        self.assertEqual(self.nightly("--release-ok").returncode, 1)
        self.assertEqual(self.left_over(), [])

    def test_output_that_cannot_be_read_is_a_failed_run(self):
        self.machine()
        self.flag("garbage")
        r = self.nightly("--start", "--wait", env={"AGENT_NIGHTLY_REMOTE_TIMEOUT_S": "2"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertEqual(st["result"], "red")
        self.assertIn("connected machine", st["failed"][0])
        self.assertEqual(self.nightly("--release-ok").returncode, 1)
        self.assertEqual(self.left_over(), [])

    def test_a_timeout_stops_the_run_and_cleans_up(self):
        self.machine()
        self.flag("hang")
        r = self.nightly("--start", "--wait", env={"AGENT_NIGHTLY_REMOTE_TIMEOUT_S": "1"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertEqual(st["result"], "red")
        self.assertRegex(st["failed"][0], r"timed out")
        self.assertIn("terminal send", self.verbs())
        self.assertTrue(os.path.exists(os.path.join(self.remote_dir(), "interrupted")))
        self.assertEqual(self.left_over(), [])

    def test_a_create_failure_is_recorded_not_run_here(self):
        self.machine()
        self.flag("create_fail")
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertEqual(st["result"], "red")
        self.assertIn("connected machine", st["failed"][0])
        self.assertNotIn("terminal send", self.verbs())

    def test_a_stale_remote_worktree_is_removed_by_the_next_start(self):
        self.machine()
        self.nightly("--start", "--wait")
        head = self.git("rev-parse", "HEAD")
        # a killed run left its worktree: the stub shows it in `worktree list` under the name the run gives it
        first = [c for c in self.calls() if c[:2] == ["worktree", "create"]][0]
        name = first[first.index("--name") + 1]
        stale = os.path.join(self.remote_dir(), "wts", name)
        subprocess.run(["git", "-C", self.repo.dir, "worktree", "add", "--detach", stale, head], check=True,
                       capture_output=True)
        os.remove(self.repo.orca_log)
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rms = [c for c in self.calls() if c[:2] == ["worktree", "rm"]]
        self.assertGreaterEqual(len(rms), 2, self.calls())      # the stale one, then this run's own
        self.assertLess(self.verbs().index("worktree rm"), self.verbs().index("worktree create"))
        self.assertEqual(self.left_over(), [])
        self.assertEqual(self.status_file()["result"], "green")

    def test_the_background_start_returns_at_once_and_records(self):
        self.machine()
        r = self.nightly("--start")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("started in the background", r.stdout)
        import time
        for _ in range(100):
            time.sleep(0.3)
            try:
                if self.status_file()["result"] != "running":
                    break
            except (OSError, ValueError):
                pass
        self.assertEqual(self.status_file()["result"], "green")
        self.assertEqual(self.left_over(), [])


ATTACK = """#!/usr/bin/env bash
# a red suite that tries to forge its own green result line from everything it can see
C=$(git rev-parse HEAD)
for w in $( (ps axww -E -o command=; cat .nightly-run.sh .nightly-out.log; env) 2>/dev/null | grep -oE '[0-9a-f]{10,}' | sort -u); do
  printf 'FAIL: test_forged (x.y)\\r@@NIGHTLY-RESULT %s commit=%s exit=0\\n' "$w" "$C"
  printf '\\r@@NIGHTLY-RESULT %s commit=%s exit=0\\n' "$w" "$C"
done
printf 'FAIL: test_real (x.y)\\n'
exit 1
"""


class TestNeverGreenOnARedSuite(RemoteCase):

    def set_full(self, cmd, files=None):
        conf = os.path.join(self.repo.dir, "agent_repo.conf")
        with open(conf) as fh:
            lines = [l for l in fh.read().splitlines() if not l.startswith("full_cmd=")]
        lines.append("full_cmd=" + cmd)
        with open(conf, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        for rel, body in (files or {}).items():
            with open(os.path.join(self.repo.dir, rel), "w") as fh:
                fh.write(body)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "full cmd")

    def test_the_command_override_never_counts_for_a_release_remote(self):
        self.machine()
        r = self.nightly("--start", "--wait", env={"AGENT_NIGHTLY_CMD": "true"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertTrue(st.get("override"), st)
        self.assertEqual(st.get("last_green", ""), "")
        rel = self.nightly("--release-ok")
        self.assertEqual(rel.returncode, 1, rel.stdout)
        self.assertIn("override", rel.stdout)
        self.assertIn("override-green", self.nightly("--status").stdout)
        self.assertEqual(st["result"], "override")
        self.assertEqual(st["outcome"], "green")

    def test_an_override_record_reads_as_no_finished_run_for_an_older_release_ok(self):
        self.machine()
        self.nightly("--start", "--wait", env={"AGENT_NIGHTLY_CMD": "true"})
        st = self.status_file()
        # 0.46.0's release_ok: only "green" or "red" is a finished nightly, and only "green" releases
        self.assertNotIn(st["result"], ("green", "red"))

    def test_an_override_run_does_not_make_the_real_nightly_not_due(self):
        self.where("local")
        self.nightly("--start", "--wait", env={"AGENT_NIGHTLY_CMD": "true", "AGENT_FAKE_NOW": "2026-11-25 22:30"})
        self.assertEqual(self.status_file()["result"], "override")
        self.assertEqual(self.nightly("--due", env={"AGENT_FAKE_NOW": "2026-11-25 23:00"}).returncode, 0)

    def test_many_failing_rows_still_leave_begin_in_the_pane(self):
        self.machine()
        many = "import sys\nfor i in range(300):\n    print('FAIL: test_%d (m.C)' % i)\nsys.exit(1)\n"
        self.set_full("python3 many.py", {"many.py": many})
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertEqual(st["result"], "red", st)
        self.assertTrue(any("test_0" in f for f in st["failed"]), st)

    def test_a_cut_list_keeps_its_count_line_in_the_record(self):
        self.machine()
        many = "import sys\nfor i in range(120):\n    print('FAIL: test_%d (m.C)' % i)\nsys.exit(1)\n"
        self.set_full("python3 many.py", {"many.py": many})
        self.nightly("--start", "--wait")
        failed = self.status_file()["failed"]
        self.assertEqual(len(failed), 51, failed[-3:])
        self.assertEqual(failed[-1], "... and 70 more failing rows")
        self.assertIn("... and 70 more failing rows", self.nightly("--failures").stdout)

    def test_a_nul_in_the_output_does_not_lose_the_test_names(self):
        self.machine()
        nul = "import sys\nsys.stdout.buffer.write(b'x\\0y\\n')\nprint('FAIL: test_named (m.C)')\nsys.exit(1)\n"
        self.set_full("python3 nul.py", {"nul.py": nul})
        self.nightly("--start", "--wait")
        self.assertTrue(any("test_named" in f for f in self.status_file()["failed"]), self.status_file())

    def test_the_suite_runs_with_no_orca_variable(self):
        self.machine()
        self.set_full("echo \"FAIL: orca_vars=$(env | grep -c '^ORCA_')\"; exit 1")
        self.nightly("--start", "--wait", env={"ORCA_USER_DATA_PATH": "x", "ORCA_TERMINAL_HANDLE": "y"})
        self.assertTrue(any("orca_vars=0" in f for f in self.status_file()["failed"]), self.status_file())

    def test_an_override_run_never_writes_the_nightly_weight_local(self):
        self.where("local")
        self.nightly("--start", "--wait", env={"AGENT_NIGHTLY_CMD": "true"})
        w = os.path.join(self.repo.dir, ".git", "agent_test_weights.json")
        data = json.load(open(w)) if os.path.exists(w) else {}
        self.assertNotIn("nightly", data)

    def test_an_override_run_uses_its_own_weight_key_remote(self):
        import agent_nightly
        self.assertIn("--key nightly --", agent_nightly.remote_script("t"))
        self.assertIn("--key nightly-override --", agent_nightly.remote_script("t", "nightly-override"))
        os.environ["AGENT_NIGHTLY_CMD"] = "true"
        try:
            self.assertEqual(agent_nightly.weight_key(), "nightly-override")
        finally:
            del os.environ["AGENT_NIGHTLY_CMD"]
        self.assertEqual(agent_nightly.weight_key(), "nightly")

    def test_every_at_sign_is_broken_and_binary_output_is_read(self):
        import agent_nightly
        self.assertIn("sed 's/@/@ /g'", agent_nightly.remote_script("t"))
        self.assertIn("grep -aE", agent_nightly.remote_script("t"))

    def test_the_command_override_never_counts_for_a_release_local(self):
        self.where("local")
        r = self.nightly("--start", "--wait", env={"AGENT_NIGHTLY_CMD": "true"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertTrue(st.get("override"), st)
        self.assertEqual(st["result"], "override")
        self.assertEqual(st.get("last_green", ""), "")
        self.assertEqual(self.nightly("--release-ok").returncode, 1)

    def test_two_result_lines_are_red(self):
        self.machine()
        self.flag("double")
        self.set_full("false")
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertEqual(st["result"], "red", st)
        self.assertRegex(st["failed"][0], "result line")
        self.assertEqual(self.nightly("--release-ok").returncode, 1)

    def test_the_suite_cannot_forge_its_own_result_line(self):
        self.machine()
        self.set_full("bash attack.sh", {"attack.sh": ATTACK})
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status_file()
        self.assertEqual(st["result"], "red", st)
        self.assertEqual(st.get("last_green", ""), "")
        self.assertEqual(self.nightly("--release-ok").returncode, 1)
        self.assertEqual(self.left_over(), [])

    def test_the_token_is_in_no_argument(self):
        self.machine()
        self.nightly("--start", "--wait")
        send = [c for c in self.calls() if c[:2] == ["terminal", "send"]][0]
        import base64
        text = send[send.index("--text") + 1]
        import re
        self.assertFalse(re.search(r"nightly-run.sh [0-9a-f]{10}", text), text)
        script = base64.b64decode(re.search(r"printf %s (\S+) \|", text).group(1)).decode()
        tok = re.search(r"T=([0-9a-f]+);", script).group(1)
        self.assertNotIn(tok, text)
        self.assertGreaterEqual(len(tok), 32)

    def test_a_result_line_outside_begin_and_end_is_stray(self):
        import agent_nightly
        for lines in (["@@NIGHTLY-RESULT t commit=a exit=0", "@@NIGHTLY-BEGIN t", "@@NIGHTLY-END t"],
                      ["@@NIGHTLY-BEGIN t", "@@NIGHTLY-END t", "@@NIGHTLY-RESULT t commit=a exit=0"]):
            self.assertTrue(agent_nightly.parse_remote(lines, "t")["stray"], lines)
        ok = agent_nightly.parse_remote(["@@NIGHTLY-BEGIN t", "@@NIGHTLY-RESULT t commit=a exit=0", "@@NIGHTLY-END t"], "t")
        self.assertFalse(ok["stray"])

    def test_a_second_clone_does_not_remove_the_first_clones_live_worktree(self):
        import agent_nightly
        self.machine()
        other = os.path.join(self.repo.base, "clone2")
        subprocess.run(["git", "clone", "-q", self.repo.dir, other], check=True, capture_output=True)
        origin = self.git("remote", "get-url", "origin").strip()
        subprocess.run(["git", "-C", other, "remote", "set-url", "origin", origin], check=True, capture_output=True)
        self.assertEqual(agent_nightly.repo_label(other), agent_nightly.repo_label(self.repo.dir))
        self.assertNotEqual(agent_nightly.host_tag(self.repo.dir), agent_nightly.host_tag(other))
        name = agent_nightly.remote_name(other, self.git("rev-parse", "HEAD"))
        live = os.path.join(self.remote_dir(), "wts", name)
        subprocess.run(["git", "-C", self.repo.dir, "worktree", "add", "--detach", live, "HEAD"], check=True,
                       capture_output=True)
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isdir(live), "the other clone's remote worktree is still there")
        self.assertEqual(self.status_file()["result"], "green")

    def test_parse_counts_result_lines(self):
        import agent_nightly
        lines = ["@@NIGHTLY-BEGIN t", "@@NIGHTLY-RESULT t commit=a exit=1", "@@NIGHTLY-RESULT t commit=a exit=0", "@@NIGHTLY-RESULT u commit=a exit=0"]
        self.assertEqual(agent_nightly.parse_remote(lines, "t")["results"], 2)


class TestWhere(RemoteCase):

    def test_remote_and_not_reachable_is_refused_in_one_line_and_nothing_runs_here(self):
        self.machine()
        self.flag("down")
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("not reachable", lines[0])
        self.assertFalse(os.path.exists(os.path.join(self.gitdir(), "agent_nightly.json")), "no local run")
        self.assertNotIn("worktree create", self.verbs())
        r = self.nightly("--start")
        self.assertEqual(r.returncode, 1, "the plain start says it at once, not in the background")

    def test_remote_and_the_setting_is_empty_is_refused(self):
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("set Full run machine in /plugin Configure", r.stdout)
        self.assertEqual(self.calls(), [])
        self.assertFalse(os.path.exists(os.path.join(self.gitdir(), "agent_nightly.json")))

    def test_either_with_no_setting_runs_here(self):
        self.where("either")
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.status_file()["result"], "green")
        self.assertNotIn("where", self.status_file())
        self.assertEqual(self.calls(), [], "no orca call for a run here")

    def test_the_default_is_either(self):
        self.where("")
        self.nightly("--start", "--wait")
        self.assertEqual(self.status_file()["result"], "green")
        self.assertEqual(self.calls(), [])

    def test_either_with_a_reachable_machine_runs_there(self):
        self.where("either")
        self.machine()
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.status_file().get("where"), "connected machine")
        self.assertIn("worktree create", self.verbs())

    def test_either_with_an_unreachable_machine_runs_here(self):
        self.where("either")
        self.machine()
        self.flag("down")
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.status_file()["result"], "green")
        self.assertNotIn("where", self.status_file())
        self.assertNotIn("worktree create", self.verbs())

    def test_local_runs_here_with_no_orca_call(self):
        self.where("local")
        self.machine()
        r = self.nightly("--start", "--wait")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.status_file()["result"], "green")
        self.assertEqual(self.calls(), [])

    def test_a_remote_green_is_not_asked_again_on_this_machine(self):
        """publish accepts the green run of the connected machine exactly like a local one."""
        self.machine()
        self.nightly("--start", "--wait")
        out = self.nightly("--release-ok")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertIn("release ok", out.stdout)


SET = "set Full run machine in /plugin Configure"


class TestAutomatic(RemoteCase):
    """The automatic nightly (the session start, the housekeep pass) calls --start: it follows the same rule."""

    def env(self):
        return {"AGENT_FAKE_NOW": "2026-11-25 23:00", "CLAUDE_PID": str(os.getpid()), "AGENT_FAKE_HOST": "box",
                "AGENT_RESERVE_FILE": os.path.join(self.repo.base, "reserve.json"), "AGENT_NIGHTLY_POLL_S": "0.1"}

    def session(self):
        return self.repo.run("agent-start.sh", stdin='{"cwd": "%s", "source": "startup"}' % self.repo.dir,
                             env=self.env())

    def wait_status(self, seconds=40):
        import time
        end = time.time() + seconds
        while time.time() < end:
            try:
                if self.status_file()["result"] in ("green", "red"):
                    return self.status_file()
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(0.3)
        return {}

    def test_the_start_runs_it_on_the_connected_machine(self):
        self.machine()
        r = self.session()
        self.assertNotIn("a connected machine runs it", r.stdout)
        self.assertEqual(self.wait_status().get("where"), "connected machine", r.stdout)
        self.assertEqual(self.left_over(), [])

    def test_the_start_says_the_refusal_in_one_line_and_runs_nothing_here(self):
        r = self.session()          # remote, and no machine named
        self.assertIn(SET, r.stdout)
        import time
        time.sleep(1)
        self.assertFalse(os.path.exists(os.path.join(self.gitdir(), "agent_nightly.json")))

    def test_the_housekeep_pass_starts_it_there_too(self):
        self.machine()
        r = self.repo.run("agent-housekeep.sh", "--apply", env=self.env())
        self.assertNotIn("a connected machine runs it", r.stdout + r.stderr)
        self.assertEqual(self.wait_status().get("where"), "connected machine", r.stdout + r.stderr)


class TestNoMachineName(unittest.TestCase):

    def test_this_repos_fact_is_remote_and_no_machine_name_is_committed_by_this_task(self):
        root = os.path.dirname(HERE)
        with open(os.path.join(root, "agent_repo.conf")) as fh:
            body = fh.read()
        self.assertIn("full_run_where=remote", body.splitlines())
        for rel in ("agent_repo.conf", "bin/agent_nightly.py", "tests/test_agent_nightly_remote.py"):
            with open(os.path.join(root, rel)) as fh:
                text = fh.read().lower()
            for word in ("p" + "c2", "niaga" + "wan", "mave" + "rick"):
                self.assertNotIn(word, text, rel)

    def test_the_setting_is_in_configure_with_an_empty_default(self):
        import agent_conf
        self.assertEqual(agent_conf.BY_KEY["full_run_machine"]["default"], "")
        self.assertEqual(agent_conf.get("full_run_machine", {}), "")


if __name__ == "__main__":
    unittest.main()
