"""Failing tests for check-blocks, slice 2: agent-file.sh carries the blocks.
Written by the task manager before any code.

Rules: requirements/check-blocks.md, section 2 (process rules), section 7 (todo est)
and 9 C3 (contract).

    todo add --checks --scope     the planned brief blocks and the task's files on the todo line
    todo checks                   add blocks; --remove only on a verified owner order
    todo builder                  who built the task (the gate refuses a diff read, flow or UI check by them)
    todo est                      re-estimate in place
    check                         one result line per block (CHECK ... in agent_state.txt)
    checks gate                   the merge guard: refuses while a planned block has no pass line
    next                          the queued tasks that can start now
    todo done                     releases the tasks queued after it
    edge add                      one edge= line in agent_repo.conf

Run: python3 -m unittest tests.test_check_results
"""

import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scripthelp import ScriptCase  # noqa: E402

LINE_DATE = re.compile(r" \| \d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


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


# ---------------------------------------------------------------- todo add --checks --scope


class TestTodoAddChecks(Case):

    def test_checks_and_scope_fields_after_guess(self):
        self.ok("todo", "add", "toast", "small", "banner to toast", "10", "--guess", "8",
                "--checks", "DIFF READ", "--scope", "src/pages/Orders.jsx,src/pages/Orders.test.jsx")
        f = self.fields("toast")
        self.assertEqual(f[3:7], ["est 10m", "guess 8m", "checks DIFF READ",
                                  "scope src/pages/Orders.jsx,src/pages/Orders.test.jsx"])

    def test_checks_in_table_order_whatever_the_order_given(self):
        self.ok("todo", "add", "exp", "big", "export column", "60", "--checks", "FLOW CHECK,EXAMPLES TEST")
        self.assertIn("checks EXAMPLES TEST, FLOW CHECK", self.fields("exp"))

    def test_checks_after_est_without_guess(self):
        self.ok("todo", "add", "w", "small", "wording", "5", "--checks", "DIFF READ")
        self.assertEqual(self.fields("w")[3:5], ["est 5m", "checks DIFF READ"])

    def test_an_unknown_block_is_refused(self):
        r = self.refused("todo", "add", "x", "small", "x", "5", "--checks", "DIFF READ,SMOKE TEST")
        self.assertIn("SMOKE TEST", r.stderr)

    def test_owner_sign_may_be_planned(self):
        # core review defect 6: a permission change needs the owner's sign; dispatch plans it
        self.ok("todo", "add", "p", "big", "who can approve", "60", "--checks", "CORE REVIEW,OWNER SIGN")
        self.assertIn("checks CORE REVIEW, OWNER SIGN", self.fields("p"))
        self.ok("todo", "add", "q", "big", "x", "60")
        self.ok("todo", "checks", "q", "OWNER SIGN")
        self.assertIn("checks OWNER SIGN", self.fields("q"))

    def test_a_tool_block_may_be_planned_too(self):
        self.ok("todo", "add", "x", "small", "x", "5", "--checks", "CORE REVIEW,DIFF READ")
        self.assertIn("checks CORE REVIEW, DIFF READ", self.fields("x"))

    def test_old_level_still_works(self):
        self.ok("todo", "add", "old", "small", "x", "5", "--level", "B")
        self.assertIn("level B", self.fields("old"))


class TestTodoChecks(Case):

    def setUp(self):
        super().setUp()
        self.ok("todo", "add", "t", "big", "task", "60", "--checks", "DIFF READ")

    def test_add_is_a_union_in_table_order(self):
        r = self.ok("todo", "checks", "t", "UI CHECK,EXAMPLES TEST")
        self.assertEqual(r.stdout.strip(),
                         "todo checks: t DIFF READ -> DIFF READ, EXAMPLES TEST, UI CHECK")
        self.assertIn("checks DIFF READ, EXAMPLES TEST, UI CHECK", self.fields("t"))

    def test_first_checks_on_a_line_without_the_field(self):
        self.ok("todo", "add", "bare", "small", "x", "5")
        r = self.ok("todo", "checks", "bare", "DIFF READ")
        self.assertEqual(r.stdout.strip(), "todo checks: bare - -> DIFF READ")
        self.assertIn("checks DIFF READ", self.fields("bare"))

    def test_every_other_field_stays(self):
        self.ok("todo", "stage", "t", "tests")
        before = [f for f in self.fields("t") if not f.startswith("checks ")]
        self.ok("todo", "checks", "t", "FLOW CHECK")
        after = [f for f in self.fields("t") if not f.startswith("checks ")]
        self.assertEqual(before, after)

    def test_unknown_task_or_block_refused(self):
        self.refused("todo", "checks", "nope", "DIFF READ")
        self.refused("todo", "checks", "t", "LOOK AT IT")

    def test_remove_without_a_verified_owner_order_is_refused(self):
        self.repo.write_bin_script("agent-owner-order.sh",
                                   "#!/usr/bin/env bash\necho 'refused: no such owner prompt'\nexit 1\n")
        r = self.refused("todo", "checks", "t", "--remove", "DIFF READ", "--owner-quote", "drop the diff read")
        self.assertIn("no such owner prompt", r.stderr)

    def test_remove_with_a_verified_owner_order(self):
        log = os.path.join(self.repo.base, "order.log")
        self.repo.write_bin_script("agent-owner-order.sh",
                                   "#!/usr/bin/env bash\nprintf '%%s\\n' \"$@\" > %s\necho 'verified'\nexit 0\n" % log)
        self.ok("todo", "checks", "t", "--remove", "DIFF READ", "--owner-quote", "drop the diff read")
        f = self.fields("t")
        self.assertFalse(any(x.startswith("checks ") and "DIFF READ" in x for x in f), f)
        self.assertTrue(any(re.fullmatch(r"removed DIFF READ \d{4}-\d{2}-\d{2} \d{2}:\d{2}", x) for x in f), f)
        with open(log) as fh:
            args = fh.read().split("\n")
        self.assertEqual(args[0], "verify")
        self.assertIn("--quote", args)
        self.assertIn("drop the diff read", args)
        self.assertIn("--repo", args)
        # core review defect 1: agent-owner-order.sh verify wants an absolute folder
        repo_arg = args[args.index("--repo") + 1]
        self.assertTrue(os.path.isabs(repo_arg), repo_arg)
        self.assertEqual(os.path.realpath(repo_arg), os.path.realpath(self.repo.dir))


# ---------------------------------------------------------------- todo est


class TestTodoEst(Case):

    def test_est_and_guess_replaced_in_place_rest_stays(self):
        self.ok("todo", "add", "t", "big", "task", "60", "--guess", "50", "--checks", "DIFF READ")
        self.ok("todo", "stage", "t", "tests")
        self.ok("todo", "wait", "t", "on", "question")
        self.ok("todo", "wait", "t", "off")
        before = self.fields("t")
        r = self.ok("todo", "est", "t", "120", "--guess", "100")
        self.assertEqual(r.stdout.strip(), "todo est: t 60m -> 120m")
        after = self.fields("t")
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
        self.assertEqual(self.fields("t")[3:5], ["est 90m", "guess 50m"])

    def test_refusals(self):
        self.ok("todo", "add", "t", "big", "task", "60")
        self.refused("todo", "est", "nope", "10")
        self.refused("todo", "est", "t", "ten")
        self.refused("todo", "est", "t", "0")
        self.refused("todo", "est", "t")


# ---------------------------------------------------------------- check: one result line per block


class TestCheckLine(Case):

    def test_one_line_in_the_state_file_of_this_folder(self):
        r = self.ok("check", "toast", "DIFF READ", "pass", "--by", "check deputy", "--evidence", "diff read, 3 files")
        self.assertIn("toast", r.stdout)
        last = self.state().strip().splitlines()[-1]
        self.assertRegex(last, r"^CHECK toast DIFF READ: pass \| by check deputy \| diff read, 3 files \| "
                               r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertNotIn("CHECK", self.todo())

    def test_fail_and_owner_sign(self):
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")
        self.ok("check", "t", "BUILD", "fail", "--by", "tm", "--evidence", "tsc: 2 errors")
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes merge it")
        lines = self.state().strip().splitlines()
        self.assertTrue(lines[-2].startswith("CHECK t BUILD: fail | by tm | tsc: 2 errors | "))
        self.assertTrue(lines[-1].startswith("CHECK t OWNER SIGN: pass | by owner | owner order verified: "
                                             "yes merge it | "), lines[-1])

    def test_owner_sign_needs_a_verified_owner_quote(self):
        # core review defect 7: any agent could write an OWNER SIGN pass line
        before = self.state()
        r = self.af("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--evidence", "yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("--owner-quote", r.stderr)
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho 'refused: not typed'\nexit 1\n")
        r = self.af("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes merge it")
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


# ---------------------------------------------------------------- checks gate: the merge guard


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
        self.ok("todo", "add", "t", "small", "task", "10", "--checks", "DIFF READ")

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
        self.assertIn("DIFF READ: missing", lines)
        self.assertIn("BUILD: pass (by tm)", lines)
        self.assertEqual(lines[-1], "GATE REFUSED t: DIFF READ missing")

    def test_pass_when_every_planned_block_passed(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.splitlines()[-1], "GATE PASS t")

    def test_the_tool_blocks_come_from_the_diff_not_the_todo_line(self):
        self.passes("DIFF READ")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("BUILD: missing", r.stdout.splitlines())
        self.assertIn("DIFF SCAN: missing", r.stdout.splitlines())

    def test_the_last_line_of_a_block_wins(self):
        self.passes("DIFF SCAN", "RELATED TESTS", "DIFF READ")
        self.ok("check", "t", "BUILD", "pass", "--by", "tm", "--evidence", "ok")
        self.ok("check", "t", "BUILD", "fail", "--by", "check deputy", "--evidence", "lint red")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("BUILD: fail (by check deputy)", r.stdout.splitlines())
        self.assertEqual(r.stdout.splitlines()[-1], "GATE REFUSED t: BUILD fail")

    def test_another_tasks_lines_do_not_count(self):
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ"):
            self.ok("check", "other", b, "pass", "--by", "tm", "--evidence", "ok")
        self.assertEqual(self.gate().returncode, 1)

    def test_a_signing_block_plans_owner_sign(self):
        self.commit_push({"package-lock.json": '{"a": 2}\n'})
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ", "MODULE TESTS")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("OWNER SIGN: missing", r.stdout.splitlines())
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes, merge")
        self.assertEqual(self.gate().returncode, 0)

    def test_a_planned_owner_sign_is_gated(self):
        # core review defect 6
        self.ok("todo", "checks", "t", "OWNER SIGN")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("OWNER SIGN: missing", r.stdout.splitlines())

    # -- core review defect 4: the gate plans what merges

    def test_a_dirty_tree_is_refused(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ")
        self.write({"app.js": "z()\n"})
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(r.stdout.splitlines()[-1],
                         "GATE REFUSED t: uncommitted changes in %s (commit and push them, or drop them)" % self.repo.dir)

    def test_agent_files_do_not_make_it_dirty(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ")
        self.write({"agent_state.trim-2026-11-25.txt": "x\n"})
        self.assertEqual(self.gate().returncode, 0, self.gate().stdout)

    def test_an_unpushed_head_is_refused(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ")
        self.commit_push({"app.js": "w()\n"}, push=False)
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(r.stdout.splitlines()[-1], "GATE REFUSED t: HEAD is not its pushed branch origin/feat")

    def test_no_upstream_is_a_note(self):
        self.git("checkout", "-q", "-b", "local-only")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ")
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
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ", "MODULE TESTS")
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
        self.ok("check", "t", "DIFF READ", "pass", "--by", "t Check", "--evidence", "read it")
        r = self.gate(dirpath=wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # -- core review defect 5: builders by name

    def test_the_task_manager_worker_and_deputy_are_builders_by_name(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        for who in ("t Task Manager", "t Worker 2", "t Worker 1: toast", "t Deputy"):
            with self.subTest(who=who):
                self.ok("check", "t", "DIFF READ", "pass", "--by", who, "--evidence", "read it")
                r = self.gate()
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("DIFF READ: pass by the builder (%s), not accepted" % who, r.stdout.splitlines())

    def test_the_check_deputy_is_no_builder(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        self.ok("check", "t", "DIFF READ", "pass", "--by", "t Check", "--evidence", "read it")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_results_from_a_file(self):
        path = os.path.join(self.repo.base, "report.txt")
        with open(path, "w") as fh:
            for b in ("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ"):
                fh.write("CHECK t %s: pass | by tm | ok | 2026-11-25 13:00\n" % b)
        r = self.gate("--results", path)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_todo_line_needs_checks(self):
        r = self.af("checks", "gate", "ghost", "--dir", self.repo.dir, "--base", "base")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ"):
            self.ok("check", "ghost", b, "pass", "--by", "tm", "--evidence", "ok")
        r = self.af("checks", "gate", "ghost", "--dir", self.repo.dir, "--base", "base", "--checks", "DIFF READ")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_removed_brief_block_is_not_planned(self):
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")
        self.ok("todo", "checks", "t", "--remove", "DIFF READ", "--owner-quote", "no diff read for this one")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        self.assertEqual(self.gate().returncode, 0)

    def test_a_removed_tool_block_is_still_planned_when_the_diff_triggers_it(self):
        # a removal is recorded, but the gate recomputes the tool blocks from the diff
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho verified\nexit 0\n")
        self.ok("todo", "checks", "t", "BUILD")
        self.ok("todo", "checks", "t", "--remove", "BUILD", "--owner-quote", "skip the build")
        self.ok("todo", "checks", "t", "BUILD")
        self.passes("DIFF SCAN", "RELATED TESTS", "DIFF READ")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("BUILD: missing", r.stdout.splitlines())

    # -- the builder never accepts its own work (kick-off answer 2)

    def test_a_diff_read_by_the_builder_is_refused(self):
        self.ok("todo", "builder", "t", "t Deputy")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        self.ok("check", "t", "DIFF READ", "pass", "--by", "t Deputy", "--evidence", "read my own diff")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("DIFF READ: pass by the builder (t Deputy), not accepted", r.stdout.splitlines())
        self.assertEqual(r.stdout.splitlines()[-1], "GATE REFUSED t: DIFF READ by the builder")

    def test_the_builder_may_pass_the_tool_blocks(self):
        self.ok("todo", "builder", "t", "t Deputy")
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            self.ok("check", "t", b, "pass", "--by", "t Deputy", "--evidence", "ok")
        self.ok("check", "t", "DIFF READ", "pass", "--by", "check deputy", "--evidence", "read it")
        self.assertEqual(self.gate().returncode, 0)

    def test_a_worker_of_the_launch_records_is_a_builder(self):
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("LAUNCH a1: worker 1 | task t | t Worker 1: toast | since 2026-11-25 12:00 | pid 1 | by tm\n")
        self.ok("todo", "checks", "t", "FLOW CHECK")
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ")
        self.ok("check", "t", "FLOW CHECK", "pass", "--by", "t Worker 1: toast", "--evidence", "clicked it")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FLOW CHECK: pass by the builder (t Worker 1: toast), not accepted", r.stdout.splitlines())

    def test_unknown_builder_is_accepted_with_one_note(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS", "DIFF READ")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        notes = [l for l in r.stdout.splitlines() if l.startswith("note: builder unknown")]
        self.assertEqual(notes, ["note: builder unknown: DIFF READ by tm accepted"])

    def test_builder_field_on_the_todo_line(self):
        r = self.ok("todo", "builder", "t", "t Deputy")
        self.assertIn("builder t Deputy", self.fields("t"))
        self.ok("todo", "add", "u", "small", "x", "5", "--builder", "u Deputy")
        self.assertIn("builder u Deputy", self.fields("u"))


# ---------------------------------------------------------------- next + todo done release


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
        self.assertRegex(out[0], r"^NEXT: 1 can start \(slots \d+ of \d+, RAM 10% under \d+%\)$")
        self.assertIn("START b | est 10m | what b", out)

    def test_after_task_still_open_waits(self):
        self.add("a", "--scope", "src/a/**")
        self.ok("todo", "stage", "a", "tests")
        self.add("b", "--scope", "src/b/**")
        self.ok("todo", "wait", "b", "on", "queue", "--after", "a")
        out = self.next().stdout.splitlines()
        self.assertIn("WAIT b: after a still open", out)
        self.assertFalse(any(l.startswith("START b") for l in out), out)

    def test_a_clash_on_the_same_files_waits(self):
        self.add("a", "--scope", "bin/agent-file.sh,tests/**")
        self.ok("todo", "stage", "a", "workers")
        self.add("b", "--scope", "bin/agent-file.sh")
        out = self.next().stdout.splitlines()
        self.assertTrue(any(l.startswith("WAIT b: clashes with a on ") for l in out), out)

    def test_no_slot_starts_nothing(self):
        self.repo.set_conf("max_agents", 1)
        self.add("a", "--scope", "x/**")
        self.ok("todo", "stage", "a", "tests")
        self.add("b", "--scope", "y/**")
        out = self.next().stdout.splitlines()
        self.assertTrue(out[0].startswith("NEXT: 0 can start: "), out)
        self.assertIn("slot", out[0])

    def test_ram_over_the_cap_starts_nothing(self):
        self.add("b", "--scope", "y/**")
        out = self.next(ram="95").stdout.splitlines()
        self.assertTrue(out[0].startswith("NEXT: 0 can start: "), out)
        self.assertIn("RAM 95%", out[0])

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


# ---------------------------------------------------------------- edge add


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


if __name__ == "__main__":
    unittest.main()
