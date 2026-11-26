"""Tests of bin/agent-file.sh: todo add/done/drop, data, time, backfill, eta, idea keep, stage.

One class per feature. Older task contracts: git log -p of this file.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase
import json
import re
import subprocess
import test_agent_board as tb  # noqa: E402  (the module only: its tests stay in their own module)


def todo_text(repo):
    with open(os.path.join(repo.dir, "agent_todo.txt")) as fh:
        return fh.read()


def completed_text(repo):
    with open(os.path.join(repo.dir, "agent_completed.txt")) as fh:
        return fh.read()


class TestTodoAddBy(ScriptCase):
    script = "agent-file.sh"

    def test_fifth_arg_sets_by(self):
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add",
                                    "cross-repo-task", "big", "one line",
                                    "30", "v4-pospro"))
        self.assertIn("| by v4-pospro", todo_text(self.repo))
        self.assertNotIn("| by main", todo_text(self.repo))

    def test_todo_done_moves_a_default_by_line(self):
        self.repo.run("agent-file.sh", "todo", "add", "a", "small", "x", "5")
        self.assertOk(self.repo.run("agent-file.sh", "todo", "done", "a"))
        self.assertNotIn("a |", todo_text(self.repo))
        self.assertIn("a |", completed_text(self.repo))

    def test_todo_done_moves_a_peer_by_line(self):
        self.repo.run("agent-file.sh", "todo", "add", "b", "big", "y", "20",
                      "v4-plus")
        self.assertOk(self.repo.run("agent-file.sh", "todo", "done", "b"))
        self.assertNotIn("b |", todo_text(self.repo))
        self.assertIn("b |", completed_text(self.repo))


class TestTodoDrop(ScriptCase):
    script = "agent-file.sh"

    def add(self, name="old-task", est="15"):
        args = ["todo", "add", name, "small", "a thing we no longer need"]
        if est:
            args.append(est)
        self.assertOk(self.repo.run("agent-file.sh", *args))

    def drop(self, *args):
        return self.repo.run("agent-file.sh", "todo", "drop", *args)

    def test_the_line_leaves_the_todo_file(self):
        self.add()
        self.assertOk(self.drop("old-task", "moot after the plugin update"))
        self.assertNotIn("old-task |", todo_text(self.repo))

    def test_the_line_lands_in_completed_with_actual_dash_and_the_reason(self):
        self.add()
        self.assertOk(self.drop("old-task", "moot after the plugin update"))
        lines = [l for l in completed_text(self.repo).splitlines()
                 if "| old-task |" in l]
        self.assertEqual(len(lines), 1, completed_text(self.repo))
        self.assertRegex(
            lines[0],
            r"^\d{4}-\d\d-\d\d \| old-task \| a thing we no longer need \| "
            r"est 15m actual - \| dropped: moot after the plugin update$")

    def test_a_todo_with_no_estimate_drops_with_est_dash(self):
        self.add(est=None)
        self.assertOk(self.drop("old-task", "not needed"))
        self.assertIn("| est - actual - | dropped: not needed",
                      completed_text(self.repo))

    def test_it_says_what_it_did(self):
        self.add()
        out = self.assertOk(self.drop("old-task", "not needed"))
        self.assertIn("todo dropped: old-task", out)

    def test_an_unknown_name_fails_and_changes_nothing(self):
        self.add()
        before = (todo_text(self.repo), completed_text(self.repo))
        result = self.drop("no-such-task", "why")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no todo line named: no-such-task", result.stderr)
        self.assertEqual((todo_text(self.repo), completed_text(self.repo)),
                         before)

    def test_no_reason_is_usage_and_changes_nothing(self):
        self.add()
        result = self.drop("old-task")
        self.assertEqual(result.returncode, 2)
        self.assertIn("old-task |", todo_text(self.repo))
        self.assertNotIn("old-task", completed_text(self.repo))

    def test_the_other_todo_lines_stay(self):
        self.add("keep-me")
        self.add("old-task")
        self.assertOk(self.drop("old-task", "not needed"))
        self.assertIn("keep-me |", todo_text(self.repo))

    def test_time_skips_a_dropped_line(self):
        self.add("real-work")
        self.assertOk(self.repo.run("agent-file.sh", "todo", "done",
                                    "real-work"))
        self.add("old-task")
        self.assertOk(self.drop("old-task", "not needed"))
        out = self.assertOk(self.repo.run("agent-file.sh", "time"))
        self.assertIn("real-work", out)
        self.assertNotIn("old-task", out)


KEYS = ["repo", "type", "lane", "mock", "est", "work", "wait", "clock",
        "bounces", "workers", "files", "lines", "tests", "adds",
        "guess",   # estimate-blend (2026-11-13): the manager's guess
        "level",   # test-levels (2026-11-20): the risk level of the todo line
        # estimate-improve (2026-11-26): typed work, the first estimate, added minutes, builder done, stage and
        # slice minutes (tests/test_agent_estimate_inputs.py holds the contract)
        "typed", "est0", "added", "built", "stages", "slices",
        "by"]   # scope add (owner 2026-11-26): the name of the clone that ran todo done; backfill writes "-"


TYPES = ["page", "server", "script", "docs", "cloud", "app", "data", "mixed"]


NOW = "2026-10-01 20:30"


def block(**known):
    """The data block: every key in order, "-" unless given."""
    return "data " + " ".join("%s=%s" % (k, known.get(k, "-")) for k in KEYS)


class DataCase(ScriptCase):
    script = "agent-file.sh"

    def path(self, name):
        return os.path.join(self.repo.dir, name)

    def read(self, name):
        with open(self.path(name)) as fh:
            return fh.read()

    def write(self, name, text):
        with open(self.path(name), "w") as fh:
            fh.write(text)

    def todo(self, *lines):
        self.write("agent_todo.txt", "".join(l + "\n" for l in lines))

    def completed(self, *lines):
        self.write("agent_completed.txt", "".join(l + "\n" for l in lines))

    def completed_lines(self):
        return [l for l in self.read("agent_completed.txt").splitlines() if l]

    def af(self, *args, **kwargs):
        env = {"AGENT_FAKE_NOW": kwargs.pop("now", NOW)}
        env.update(kwargs.pop("env", None) or {})
        return self.repo.run("agent-file.sh", *args, env=env, **kwargs)

    def git(self, *args):
        return subprocess.run(["git", "-C", self.repo.dir] + list(args),
                              check=True, capture_output=True,
                              text=True).stdout.strip()

    AGENT_TXT = ("agent_todo.txt", "agent_completed.txt", "agent_ideas.txt",
                 "agent_worktree.txt")

    def stamps(self):
        """name -> (bytes, mtime) of the four agent files; None when missing."""
        seen = {}
        for name in self.AGENT_TXT:
            full = self.path(name)
            if os.path.exists(full):
                with open(full, "rb") as fh:
                    seen[name] = (fh.read(), os.stat(full).st_mtime_ns)
            else:
                seen[name] = None
        return seen

    def feat_history(self):
        """A branch "feat" that changed 3 files (7 lines) and a main branch
        that moved on after feat left it. Returns the main branch's name."""
        main = self.git("rev-parse", "--abbrev-ref", "HEAD")
        self.git("checkout", "-q", "-b", "feat")
        self.write("a.txt", "1\n2\n3\n")            # 3 lines added
        self.write("b.txt", "1\n2\n")               # 2 lines added
        self.write("seed.txt", "y\n")               # 1 added, 1 deleted
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "feat work")
        self.git("checkout", "-q", main)
        self.write("c.txt", "main moved on\n")      # not the task's work
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "main moves on")
        return main

    def merge_feat(self):
        self.git("merge", "-q", "--no-ff", "feat", "-m", "Merge feat (W8)")
        return self.git("rev-parse", "HEAD")

    def assertRefused(self, result, *words):
        """One plain line on stderr, exit 1, nothing on stdout."""
        self.assertEqual(result.returncode, 1,
                         "exit %d\nSTDOUT:\n%s\nSTDERR:\n%s"
                         % (result.returncode, result.stdout, result.stderr))
        lines = [l for l in result.stderr.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        for word in words:
            self.assertIn(word, lines[0])


T1 = "t1 | big | build the thing | est 90m | opened 2026-10-01 18:00 | by main"


OLD_A = ("2026-09-20 | a-task | did a thing. Work 67m + bounce 10m = 77m "
         "(est 120m), wait 45m | est 120m actual 300m")


OLD_B = "2026-09-21 | b-task | other thing, work 108 | est 150m actual 400m"


OLD_C = "2026-09-22 | c-task | third thing: est 150 work 108 | est 150m actual 200m"


OLD_D = "2026-09-23 | d-task | nothing said here about minutes | est 30m actual 41m"


OLD_E = "2026-09-24 | e-task | has data already, work 999 | " + block(
    repo="project", type="page", est=120, work=96, wait=45, clock=300)


OLD_F = "2026-09-25 | f-task | dropped, work 50 | est 60m actual - | dropped: not needed"


OLD_G = ("2026-09-26 | g-task | split work vs wait (waits = mock gate), "
         "work and wait apart | est 60m actual 70m")


OLD_H = "2026-09-27 | h-task | WORK 30M, WAIT 12 | est - actual 55m"


TWICE_DROPPED = "2026-09-10 | twice | first try | est 60m actual - | dropped: rescoped"


TWICE_DONE = "2026-09-12 | twice | second try | est 45m actual 80m"


# test-levels (2026-11-20): level is in the data block, not a column of the table
HEADER = ["repo", "name", "date"] + KEYS[1:KEYS.index("level")]   # plain `data`: up to guess


HERE_DATA = "2026-10-01 | here-new | a data line | " + block(
    repo="project", type="script", lane="full", mock="no", est=90, work=85,
    wait=45, clock=150, bounces=1, workers=3, files=7, lines=412, tests=38,
    adds=2)


HERE_ROW = ["project", "here-new", "2026-10-01", "script", "full", "no", "90",
            "85", "45", "150", "1", "3", "7", "412", "38", "2", "-"]


SHOP_OLD = "2026-09-01 | shop-old | a legacy line of the shop | est 60m actual 75m"


SHOP_ROW = ["shop", "shop-old", "2026-09-01", "-", "-", "-", "60", "-", "-",
            "75", "-", "-", "-", "-", "-", "-", "-"]


SHOP_DROPPED = "2026-09-02 | shop-gone | dropped | est 60m actual - | dropped: no"


API_DATA = "2026-09-03 | api-new | a data line of the api | " + block(
    repo="api", type="server", lane="fast", mock="no", est=15, work=9, wait=0,
    clock=11, bounces=0, workers=0, files=2, lines=31, tests=1, adds=0)


API_ROW = ["api", "api-new", "2026-09-03", "server", "fast", "no", "15", "9",
           "0", "11", "0", "0", "2", "31", "1", "0", "-"]


EXTRA_OLD = "2026-09-04 | extra-old | given by hand | est 20m actual 33m"


EXTRA_ROW = ["extra", "extra-old", "2026-09-04", "-", "-", "-", "20", "-", "-",
             "33", "-", "-", "-", "-", "-", "-", "-"]


ETA_NOW = "2026-10-01 20:00"


ETA_LINE = re.compile(
    r"^about (\d+) min of work left.*, done around (\d\d:\d\d)"
    r"( tomorrow| on \d{4}-\d\d-\d\d)?; "
    r"owner needed next: (mock ready|review) about (\d\d:\d\d)"
    r"( tomorrow| on \d{4}-\d\d-\d\d)?$")


class TestTodoDoneData(DataCase):

    def setUp(self):
        super().setUp()
        self.todo(T1)

    def test_all_the_facts_land_on_one_line(self):
        self.assertOk(self.af(
            "todo", "done", "t1", "--work", "85", "--wait", "45",
            "--bounces", "1", "--workers", "3", "--mock", "no",
            "--lane", "full", "--type", "script", "--tests", "38",
            "--adds", "2"))
        self.assertEqual(self.completed_lines(), [
            "2026-10-01 | t1 | build the thing | " + block(
                repo="project", type="script", lane="full", mock="no",
                est=90, work=105, wait=45, clock=150, bounces=1, workers=3,
                tests=38, adds=2, typed=85, est0=90, by="t")])     # estimate-improve A1: work = clock 150 - wait 45
        self.assertNotIn("t1 |", self.read("agent_todo.txt"))

    def test_the_old_call_still_works_and_knows_what_it_can(self):
        out = self.assertOk(self.af("todo", "done", "t1"))
        self.assertIn("todo done: t1", out)
        self.assertEqual(self.completed_lines(), [      # estimate-improve A1: the work is measured
            "2026-10-01 | t1 | build the thing | "
            + block(repo="project", est=90, work=150, wait=0, clock=150, est0=90, by="t")])

    def test_the_old_call_with_a_result_text_still_works(self):
        self.assertOk(self.af("todo", "done", "t1", "merged abc123, 38 tests OK"))
        self.assertEqual(self.completed_lines(), [
            "2026-10-01 | t1 | build the thing | "
            + block(repo="project", est=90, work=150, wait=0, clock=150, est0=90, by="t")])

    def test_facts_after_a_result_text(self):
        self.assertOk(self.af("todo", "done", "t1", "merged abc123",
                              "--work", "85", "--lane", "full"))
        self.assertEqual(self.completed_lines(), [
            "2026-10-01 | t1 | build the thing | "
            + block(repo="project", lane="full", est=90, work=150, wait=0, clock=150, typed=85, est0=90, by="t")])

    def test_zero_is_a_number(self):
        self.assertOk(self.af("todo", "done", "t1", "--work", "12",
                              "--wait", "0", "--bounces", "0", "--adds", "0"))
        self.assertIn(block(repo="project", est=90, work=150, wait=0,
                            clock=150, bounces=0, adds=0, typed=12, est0=90, by="t"),
                      self.completed_lines()[0])

    def test_no_estimate_and_no_opened_time_are_a_dash(self):
        self.todo("t2 | small | a thing | by main")
        self.assertOk(self.af("todo", "done", "t2", "--work", "5"))
        self.assertEqual(self.completed_lines(), [
            "2026-10-01 | t2 | a thing | " + block(repo="project", work=5, typed=5, by="t")])

    def test_the_other_todo_lines_stay(self):
        self.todo(T1, "keep | big | stays | est 10m | opened 2026-10-01 19:00 | by main")
        self.assertOk(self.af("todo", "done", "t1", "--work", "85"))
        self.assertIn("keep | big | stays", self.read("agent_todo.txt"))
        self.assertEqual(len(self.completed_lines()), 1)

    def test_every_type_of_the_list_is_taken(self):
        for i, kind in enumerate(TYPES):
            name = "k%d" % i
            self.todo("%s | big | x | est 10m | opened 2026-10-01 20:00 | by main" % name)
            with self.subTest(type=kind):
                self.assertOk(self.af("todo", "done", name, "--type", kind))
                self.assertIn(" type=%s " % kind, self.completed_lines()[-1])

    def test_repo_is_the_main_repo_even_from_a_worktree(self):
        wt = os.path.join(self.repo.base, "wt_feature")
        self.git("worktree", "add", "-q", "-b", "feature", wt)
        self.assertOk(self.af("todo", "done", "t1", "--work", "85", cwd=wt))
        self.assertIn(" data repo=project ", self.completed_lines()[0])

    # ---- TIME DATA: <n> of 30 ----

    def test_it_prints_time_data_one_of_30(self):
        out = self.assertOk(self.af("todo", "done", "t1", "--work", "85"))
        self.assertIn("TIME DATA: 1 of 30", out)

    def test_time_data_counts_only_lines_with_a_work_number(self):
        self.completed(
            "2026-09-30 | old | legacy line | est 180m actual 1240m",
            "2026-09-30 | a | x | " + block(repo="project", est=60, work=50, clock=70),
            "2026-09-30 | b | x | " + block(repo="project", est=60, work=40, wait=5, clock=70),
            "2026-09-30 | c | x | " + block(repo="project", est=60, clock=70),
            "2026-09-30 | d | work 55 in the text only | est 60m actual - | dropped: no")
        out = self.assertOk(self.af("todo", "done", "t1", "--work", "85"))
        self.assertIn("TIME DATA: 3 of 30", out)

    def test_time_data_counts_a_task_done_without_typed_work(self):
        # estimate-improve A1: the work is measured from the line's times, so it counts with no --work
        self.completed(
            "2026-09-30 | a | x | " + block(repo="project", est=60, work=50, clock=70))
        out = self.assertOk(self.af("todo", "done", "t1"))
        self.assertIn("TIME DATA: 2 of 30", out)

    def test_time_data_does_not_count_a_task_with_no_time_and_no_work(self):
        self.completed(
            "2026-09-30 | a | x | " + block(repo="project", est=60, work=50, clock=70))
        self.todo("t2 | small | a thing | by main")
        out = self.assertOk(self.af("todo", "done", "t2"))
        self.assertIn("TIME DATA: 1 of 30", out)

    # ---- refused ----

    def assertNothingMoved(self):
        self.assertIn("t1 | big | build the thing", self.read("agent_todo.txt"))
        self.assertEqual(self.completed_lines(), [])

    def test_nonsense_is_refused_with_one_plain_line(self):
        bad = [("--work", "-5"), ("--work", "abc"), ("--work", "1.5"),
               ("--wait", "-1"), ("--wait", "soon"), ("--bounces", "-1"),
               ("--bounces", "x"), ("--workers", "two"), ("--tests", "-3"),
               ("--adds", "many"), ("--mock", "maybe"), ("--lane", "slow"),
               ("--type", "banana")]
        for option, value in bad:
            with self.subTest(option=option, value=value):
                self.assertRefused(self.af("todo", "done", "t1", option, value),
                                   option)
                self.assertNothingMoved()

    def test_a_bad_fact_after_good_ones_moves_nothing(self):
        self.assertRefused(self.af("todo", "done", "t1", "--work", "85",
                                   "--wait", "45", "--bounces", "-2"),
                           "--bounces")
        self.assertNothingMoved()

    def test_an_unknown_option_is_refused(self):
        self.assertRefused(self.af("todo", "done", "t1", "--speed", "9"),
                           "--speed")
        self.assertNothingMoved()

    def test_an_option_with_no_value_is_refused(self):
        self.assertRefused(self.af("todo", "done", "t1", "--work"), "--work")
        self.assertNothingMoved()

    def test_an_unknown_name_still_fails_as_before(self):
        result = self.af("todo", "done", "nope", "--work", "5")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no todo line named: nope", result.stderr)
        self.assertNothingMoved()

    def test_the_refusal_of_a_type_lists_the_types(self):
        result = self.af("todo", "done", "t1", "--type", "banana")
        for kind in TYPES:
            self.assertIn(kind, result.stderr)


class TestFilesAndLines(DataCase):
    """files and lines come from git, only when the caller says which commits."""

    def setUp(self):
        super().setUp()
        self.main = self.feat_history()
        self.todo(T1)

    def merge(self):
        return self.merge_feat()

    def test_merge_counts_what_the_merge_brought_in(self):
        commit = self.merge()
        self.todo(T1)
        self.assertOk(self.af("todo", "done", "t1", "--work", "85",
                              "--merge", commit))
        self.assertIn(" files=3 lines=7 ", self.completed_lines()[0])

    def test_merge_takes_a_short_hash(self):
        commit = self.merge()[:10]
        self.todo(T1)
        self.assertOk(self.af("todo", "done", "t1", "--merge", commit))
        self.assertIn(" files=3 lines=7 ", self.completed_lines()[0])

    def test_range_counts_what_the_branch_changed_since_it_left(self):
        # main moved on after feat left it: c.txt is not counted
        self.assertOk(self.af("todo", "done", "t1", "--range",
                              "%s..feat" % self.main))
        self.assertIn(" files=3 lines=7 ", self.completed_lines()[0])

    def test_no_commit_given_says_not_counted(self):
        out = self.assertOk(self.af("todo", "done", "t1", "--work", "85"))
        self.assertIn(" files=- lines=- ", self.completed_lines()[0])
        self.assertIn("not counted", out)

    def test_a_count_is_not_said_to_be_missing(self):
        commit = self.merge()
        self.todo(T1)
        out = self.assertOk(self.af("todo", "done", "t1", "--merge", commit))
        self.assertNotIn("not counted", out)

    def test_an_unknown_commit_is_refused(self):
        self.assertRefused(self.af("todo", "done", "t1", "--merge", "deadbeef00"),
                           "--merge")
        self.assertIn("t1 | big", self.read("agent_todo.txt"))
        self.assertEqual(self.completed_lines(), [])

    def test_an_unknown_range_is_refused(self):
        self.assertRefused(self.af("todo", "done", "t1", "--range",
                                   "%s..no-such-branch" % self.main), "--range")
        self.assertIn("t1 | big", self.read("agent_todo.txt"))

    def test_a_range_without_two_dots_is_refused(self):
        self.assertRefused(self.af("todo", "done", "t1", "--range", "feat"),
                           "--range")
        self.assertIn("t1 | big", self.read("agent_todo.txt"))

    def test_merge_and_range_together_are_refused(self):
        commit = self.merge()
        self.todo(T1)
        result = self.af("todo", "done", "t1", "--merge", commit,
                         "--range", "%s..feat" % self.main)
        self.assertRefused(result, "--merge", "--range")
        self.assertIn("t1 | big", self.read("agent_todo.txt"))



from sharedrepo import SharedScriptCase  # noqa: E402


class SharedDataCase(SharedScriptCase, DataCase):
    """DataCase with one repo per class, for classes whose tests only read."""

class _TestTimeTableFixture:
    def fixture(self):
        self.completed(
            "2026-09-30 | old-one | a legacy line | est 180m actual 1240m",
            "2026-10-01 | new-one | a data line | " + block(
                repo="project", type="page", lane="full", mock="yes", est=120,
                work=96, wait=45, clock=300, bounces=1, workers=2, files=5,
                lines=200, tests=12, adds=0),
            "2026-10-01 | no-work | done the old way | "
            + block(repo="project", est=15, clock=7),
            "2026-10-01 | no-est | work but no estimate | "
            + block(repo="project", work=20, clock=30),
            "2026-10-01 | gone | a dropped line | est 60m actual - | dropped: not needed")

    def rows(self):
        out = self.assertOk(self.af("time"))
        return [l.split() for l in out.splitlines() if l.strip()]


class TestTimeTable(_TestTimeTableFixture, SharedDataCase):
    """One repo for the class: these tests only read (tests/sharedrepo.py)."""

    def test_the_header_names_work_wait_and_clock(self):
        self.assertEqual(self.rows()[0],
                         ["name", "est", "work", "wait", "clock", "ratio"])

    def test_a_data_line_shows_work_wait_clock_and_work_over_est(self):
        self.assertIn(["new-one", "120", "96", "45", "300", "0.8"], self.rows())

    def test_an_old_line_shows_its_minutes_as_clock_never_as_work(self):
        self.assertIn(["old-one", "180", "-", "-", "1240", "-"], self.rows())

    def test_a_line_with_no_work_number_has_no_ratio(self):
        self.assertIn(["no-work", "15", "-", "-", "7", "-"], self.rows())

    def test_work_with_no_estimate_has_no_ratio(self):
        self.assertIn(["no-est", "-", "20", "-", "30", "-"], self.rows())

    def test_one_row_per_finished_task(self):
        rows = self.rows()
        self.assertEqual(len(rows), 5)
        self.assertNotIn("gone", [r[0] for r in rows])   # dropped lines are skipped


class TestTimeTableWrites(_TestTimeTableFixture, DataCase):
    """The tests of TestTimeTable that write: one repo each."""

    def setUp(self):
        super().setUp()
        self.fixture()

    def test_an_empty_file_prints_the_header_only(self):
        self.completed()
        self.assertEqual(self.rows(),
                         [["name", "est", "work", "wait", "clock", "ratio"]])

    def test_a_task_done_now_shows_up(self):
        self.todo(T1)
        self.assertOk(self.af("todo", "done", "t1", "--work", "45", "--wait", "30"))
        self.assertIn(["t1", "90", "120", "30", "150", "1.3"], self.rows())     # A1: work 150 - 30


class TestBackfill(DataCase):

    def setUp(self):
        super().setUp()
        self.completed(OLD_A, OLD_B, OLD_C, OLD_D, OLD_E, OLD_F, OLD_G, OLD_H)

    def line(self, name):
        return [l for l in self.completed_lines() if "| %s |" % name in l][0]

    def test_the_total_of_work_plus_bounce_is_the_work(self):
        self.assertOk(self.af("backfill"))
        self.assertEqual(
            self.line("a-task"),
            "2026-09-20 | a-task | did a thing. Work 67m + bounce 10m = 77m "
            "(est 120m), wait 45m | "
            + block(repo="project", est=120, work=77, wait=45, clock=300))

    def test_plain_work_number(self):
        self.assertOk(self.af("backfill"))
        self.assertEqual(
            self.line("b-task"),
            "2026-09-21 | b-task | other thing, work 108 | "
            + block(repo="project", est=150, work=108, clock=400))

    def test_est_then_work(self):
        self.assertOk(self.af("backfill"))
        self.assertEqual(
            self.line("c-task"),
            "2026-09-22 | c-task | third thing: est 150 work 108 | "
            + block(repo="project", est=150, work=108, clock=200))

    def test_letter_case_does_not_matter_and_est_may_be_missing(self):
        self.assertOk(self.af("backfill"))
        self.assertEqual(
            self.line("h-task"),
            "2026-09-27 | h-task | WORK 30M, WAIT 12 | "
            + block(repo="project", work=30, wait=12, clock=55))

    def test_lines_that_say_no_work_stay_as_they_are(self):
        self.assertOk(self.af("backfill"))
        self.assertEqual(self.line("d-task"), OLD_D)
        self.assertEqual(self.line("g-task"), OLD_G)

    def test_a_line_with_data_and_a_dropped_line_stay_as_they_are(self):
        self.assertOk(self.af("backfill"))
        self.assertEqual(self.line("e-task"), OLD_E)
        self.assertEqual(self.line("f-task"), OLD_F)

    def test_the_order_of_the_lines_stays(self):
        self.assertOk(self.af("backfill"))
        names = [l.split(" | ")[1] for l in self.completed_lines()]
        self.assertEqual(names, ["a-task", "b-task", "c-task", "d-task",
                                 "e-task", "f-task", "g-task", "h-task"])

    def test_it_prints_what_it_took(self):
        out = self.assertOk(self.af("backfill"))
        lines = out.splitlines()
        self.assertIn("took: a-task work 77 wait 45", lines)
        self.assertIn("took: b-task work 108 wait -", lines)
        self.assertIn("took: c-task work 108 wait -", lines)
        self.assertIn("took: h-task work 30 wait 12", lines)

    def test_it_prints_what_it_skipped_and_why(self):
        out = self.assertOk(self.af("backfill"))
        for name in ("d-task", "e-task", "f-task", "g-task"):
            with self.subTest(name=name):
                self.assertRegex(out, r"(?m)^skipped: %s \(.+\)$" % name)

    def test_the_last_line_counts_both(self):
        out = self.assertOk(self.af("backfill"))
        self.assertEqual(out.strip().splitlines()[-1],
                         "backfill: took 4, skipped 4")

    def test_dry_run_prints_the_same_and_writes_nothing(self):
        before = self.read("agent_completed.txt")
        dry = self.assertOk(self.af("backfill", "--dry-run"))
        self.assertEqual(self.read("agent_completed.txt"), before)
        self.assertIn("took: a-task work 77 wait 45", dry.splitlines())
        self.assertIn("backfill: took 4, skipped 4", dry)

    def test_a_second_run_takes_nothing(self):
        self.assertOk(self.af("backfill"))
        after_first = self.read("agent_completed.txt")
        out = self.assertOk(self.af("backfill"))
        self.assertEqual(out.strip().splitlines()[-1],
                         "backfill: took 0, skipped 8")
        self.assertEqual(self.read("agent_completed.txt"), after_first)

    def test_time_shows_the_backfilled_work(self):
        self.assertOk(self.af("backfill"))
        rows = [l.split() for l in self.assertOk(self.af("time")).splitlines()]
        self.assertIn(["a-task", "120", "77", "45", "300", "0.6"], rows)
        self.assertIn(["d-task", "30", "-", "-", "41", "-"], rows)

    def test_an_empty_file_is_fine(self):
        self.completed()
        out = self.assertOk(self.af("backfill"))
        self.assertIn("backfill: took 0, skipped 0", out)


class TestBackfillByName(DataCase):

    def setUp(self):
        super().setUp()
        self.completed(OLD_D, OLD_E, OLD_F, TWICE_DROPPED, TWICE_DONE, OLD_H)
        self.before = self.read("agent_completed.txt")

    def line(self, name):
        return [l for l in self.completed_lines() if "| %s |" % name in l]

    def assertUnchanged(self):
        self.assertEqual(self.read("agent_completed.txt"), self.before)

    D_NEW = ("2026-09-23 | d-task | nothing said here about minutes | "
             + block(repo="project", type="script", lane="full", mock="no",
                     est=30, work=25, wait=10, clock=41, bounces=1, workers=2,
                     tests=9, adds=1))
    D_ARGS = ("--work", "25", "--wait", "10", "--bounces", "1", "--workers",
              "2", "--mock", "no", "--lane", "full", "--type", "script",
              "--tests", "9", "--adds", "1")

    def test_only_that_line_changes_and_the_order_stays(self):
        self.assertOk(self.af("backfill", "d-task", *self.D_ARGS))
        self.assertEqual(self.completed_lines(),
                         [self.D_NEW, OLD_E, OLD_F, TWICE_DROPPED, TWICE_DONE,
                          OLD_H])

    def test_only_the_given_facts_are_set(self):
        self.assertOk(self.af("backfill", "d-task", "--work", "25"))
        self.assertEqual(self.line("d-task"), [
            "2026-09-23 | d-task | nothing said here about minutes | "
            + block(repo="project", est=30, work=25, clock=41)])

    def test_an_old_line_with_no_estimate(self):
        self.assertOk(self.af("backfill", "h-task", "--work", "30", "--wait", "12"))
        self.assertEqual(self.line("h-task"), [
            "2026-09-27 | h-task | WORK 30M, WAIT 12 | "
            + block(repo="project", work=30, wait=12, clock=55)])

    def test_it_prints_what_it_wrote_and_the_count(self):
        out = self.assertOk(self.af("backfill", "d-task", *self.D_ARGS))
        self.assertIn("wrote: " + self.D_NEW, out.splitlines())
        self.assertIn("TIME DATA: 2 of 30", out)

    def test_dry_run_writes_nothing(self):
        out = self.assertOk(self.af("backfill", "d-task", "--dry-run", *self.D_ARGS))
        self.assertIn("would write: " + self.D_NEW, out.splitlines())
        self.assertNotIn("wrote: ", out)
        self.assertUnchanged()

    def test_an_unknown_name_is_refused(self):
        self.assertRefused(self.af("backfill", "nope", "--work", "5"),
                           "no completed line named: nope")
        self.assertUnchanged()

    def test_a_line_with_data_is_refused_without_force(self):
        self.assertRefused(self.af("backfill", "e-task", "--work", "80"),
                           "e-task", "--force")
        self.assertUnchanged()

    def test_force_replaces_the_given_facts_and_keeps_the_rest(self):
        self.assertOk(self.af("backfill", "e-task", "--force", "--work", "80",
                              "--lane", "full"))
        self.assertEqual(self.line("e-task"), [
            "2026-09-24 | e-task | has data already, work 999 | " + block(
                repo="project", type="page", lane="full", est=120, work=80,
                wait=45, clock=300)])

    def test_force_may_come_last(self):
        self.assertOk(self.af("backfill", "e-task", "--work", "80", "--force"))
        self.assertIn(" work=80 ", self.line("e-task")[0])

    def test_a_dropped_line_is_refused_even_with_force(self):
        self.assertRefused(self.af("backfill", "f-task", "--work", "50"),
                           "f-task", "dropped")
        self.assertRefused(self.af("backfill", "f-task", "--work", "50", "--force"),
                           "f-task", "dropped")
        self.assertUnchanged()

    def test_a_name_used_twice_means_the_line_that_is_not_dropped(self):
        self.assertOk(self.af("backfill", "twice", "--work", "50", "--wait", "20"))
        self.assertEqual(self.line("twice"), [
            TWICE_DROPPED,
            "2026-09-12 | twice | second try | "
            + block(repo="project", est=45, work=50, wait=20, clock=80)])

    def test_no_fact_given_is_refused(self):
        self.assertRefused(self.af("backfill", "d-task"), "d-task")
        self.assertRefused(self.af("backfill", "e-task", "--force"), "e-task")
        self.assertUnchanged()

    def test_nonsense_is_refused_like_in_todo_done(self):
        bad = [("--work", "-5"), ("--wait", "soon"), ("--bounces", "1.5"),
               ("--mock", "maybe"), ("--lane", "slow"), ("--type", "banana"),
               ("--speed", "9")]
        for option, value in bad:
            with self.subTest(option=option, value=value):
                self.assertRefused(self.af("backfill", "d-task", "--work", "25",
                                           option, value), option)
                self.assertUnchanged()

    def test_merge_counts_the_files_and_lines(self):
        # the fixture lines are committed first, so they are not feat's work
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "agent files")
        self.feat_history()
        commit = self.merge_feat()
        self.assertOk(self.af("backfill", "d-task", "--work", "25",
                              "--merge", commit))
        self.assertIn(" files=3 lines=7 ", self.line("d-task")[0])

    def test_an_unknown_commit_is_refused(self):
        self.assertRefused(self.af("backfill", "d-task", "--work", "25",
                                   "--merge", "deadbeef00"), "--merge")
        self.assertUnchanged()

    def test_the_text_scan_then_skips_the_line(self):
        self.assertOk(self.af("backfill", "d-task", "--work", "25"))
        out = self.assertOk(self.af("backfill"))
        self.assertRegex(out, r"(?m)^skipped: d-task \(.+\)$")

    def test_time_shows_the_numbers(self):
        self.assertOk(self.af("backfill", "twice", "--work", "36", "--wait", "20"))
        rows = [l.split() for l in self.assertOk(self.af("time")).splitlines()]
        self.assertIn(["twice", "45", "36", "20", "80", "0.8"], rows)

    def test_the_todo_file_is_not_touched(self):
        self.todo(T1)
        self.assertOk(self.af("backfill", "d-task", "--work", "25"))
        self.assertEqual(self.read("agent_todo.txt"), T1 + "\n")


class _TestDataAllReposFixture:
    def fixture(self):
        self.completed(HERE_DATA)
        self.shop = self.other("shop", SHOP_OLD, SHOP_DROPPED)
        self.api = self.other("api", API_DATA)
        self.extra = self.other("extra", EXTRA_OLD)
        self.empty = self.repo.make_project("no-pipeline")
        self.city = os.path.join(self.repo.base, "cityhome")
        os.mkdir(self.city)
        self.world({self.shop + "/.git": {"name": "shop"}, self.api + "/.git": {"name": "api"}})

    def other(self, name, *lines):
        path = self.repo.make_project(name)
        with open(os.path.join(path, "agent_completed.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))
        with open(os.path.join(path, "agent_todo.txt"), "w") as fh:
            fh.write("SECRETMARK-todo | big | never read | by main\n")
        os.mkdir(os.path.join(path, ".secrets"))
        with open(os.path.join(path, ".secrets", "key"), "w") as fh:
            fh.write("SECRETMARK-key\n")
        return path

    def world(self, territories):
        with open(os.path.join(self.city, "world.json"), "w") as fh:
            json.dump({"v": 1, "territories": territories,
                       "order": list(territories)}, fh)

    def data(self, *args, **kwargs):
        env = {"AGENT_CITY_HOME": self.city}
        env.update(kwargs.pop("env", None) or {})
        return self.af("data", *args, env=env, **kwargs)

    def rows(self, *args, **kwargs):
        out = self.assertOk(self.data(*args, **kwargs))
        return [l.split() for l in out.splitlines() if l.strip()]

    def snapshot(self, *paths):
        seen = {}
        for root in paths:
            for folder, _dirs, files in os.walk(root):
                for name in files:
                    full = os.path.join(folder, name)
                    with open(full, "rb") as fh:
                        seen[full] = (fh.read(), os.stat(full).st_mtime_ns)
        return seen


class TestDataAllRepos(_TestDataAllReposFixture, SharedDataCase):
    """One repo for the class: these tests only read (tests/sharedrepo.py)."""

    def test_the_header_has_the_repo_column_first(self):
        self.assertEqual(self.rows()[0], HEADER)

    def test_this_repo_and_the_city_world_are_read(self):
        rows = self.rows()
        self.assertEqual(rows[1:], [HERE_ROW, SHOP_ROW, API_ROW])

    def test_a_path_given_as_an_argument_is_read_too(self):
        self.assertEqual(self.rows(self.extra)[1:],
                         [HERE_ROW, SHOP_ROW, API_ROW, EXTRA_ROW])

    def test_a_missing_path_argument_is_skipped_and_said(self):
        gone = os.path.join(self.repo.base, "not-there")
        result = self.data(gone)
        self.assertOk(result)
        self.assertIn(gone, result.stderr)

    def test_no_city_home_still_prints_this_repo(self):
        rows = self.rows(env={"AGENT_CITY_HOME": os.path.join(self.repo.base, "nope")})
        self.assertEqual(rows, [HEADER, HERE_ROW])

    def test_it_never_writes_into_another_repo(self):
        others = (self.shop, self.api, self.extra, self.empty, self.city)
        before = self.snapshot(*others)
        self.assertOk(self.data(self.extra, self.empty))
        self.assertEqual(self.snapshot(*others), before)

    def test_it_writes_nothing_into_this_repos_data_either(self):
        before = self.read("agent_completed.txt")
        self.assertOk(self.data(self.extra))
        self.assertEqual(self.read("agent_completed.txt"), before)

    def test_nothing_of_another_repo_but_its_data_lines_is_printed(self):
        result = self.data(self.extra)
        self.assertNotIn("SECRETMARK", result.stdout + result.stderr)


class TestDataAllReposWrites(_TestDataAllReposFixture, DataCase):
    """The tests of TestDataAllRepos that write: one repo each."""

    def setUp(self):
        super().setUp()
        self.fixture()

    def test_the_same_repo_is_read_once(self):
        self.world({self.shop + "/.git": {"name": "shop"},
                    self.repo.dir + "/.git": {"name": "project"},
                    self.api + "/.git": {"name": "api"}})
        rows = self.rows(self.shop, self.api + "/", self.repo.dir)
        self.assertEqual(rows[1:], [HERE_ROW, SHOP_ROW, API_ROW])

    def test_a_repo_without_the_file_is_skipped_and_said(self):
        self.world({self.shop + "/.git": {"name": "shop"},
                    self.empty + "/.git": {"name": "no-pipeline"}})
        result = self.data()
        self.assertOk(result)
        self.assertRegex(result.stderr, r"(?m)^skipped.*%s" % re.escape(self.empty))
        self.assertFalse(os.path.exists(os.path.join(self.empty, "agent_completed.txt")))

    def test_a_broken_world_file_is_not_an_error(self):
        with open(os.path.join(self.city, "world.json"), "w") as fh:
            fh.write("{ not json")
        self.assertEqual(self.rows()[1:], [HERE_ROW])

    def test_a_territory_key_that_is_not_a_repo_folder_is_no_error(self):
        self.world({"dir:loose": {"name": "loose"},
                    self.shop + "/.git": {"name": "shop"},
                    self.api + "/.git": {"name": "api"}})
        self.assertEqual(self.rows()[1:], [HERE_ROW, SHOP_ROW, API_ROW])

    def test_the_default_city_home_is_under_home(self):
        home = self.repo.fake_home()
        default = os.path.join(home, ".claude", "agent-city")
        os.makedirs(default)
        with open(os.path.join(default, "world.json"), "w") as fh:
            json.dump({"v": 1, "territories": {self.extra + "/.git": {"name": "extra"}}}, fh)
        rows = self.rows(env={"AGENT_CITY_HOME": ""})
        self.assertEqual(rows[1:], [HERE_ROW, EXTRA_ROW])

    def test_it_does_not_touch_this_repos_agent_files(self):
        os.remove(self.path("agent_ideas.txt"))
        os.remove(self.path("agent_worktree.txt"))
        before = self.stamps()
        self.assertEqual(self.rows()[1:], [HERE_ROW, SHOP_ROW, API_ROW])
        self.assertEqual(self.stamps(), before)

    def test_a_repo_with_no_agent_files_gets_none(self):
        for name in self.AGENT_TXT:
            os.remove(self.path(name))
        result = self.data()
        self.assertOk(result)
        rows = [l.split() for l in result.stdout.splitlines() if l.strip()]
        self.assertEqual(rows, [HEADER, SHOP_ROW, API_ROW])
        self.assertRegex(result.stderr, r"(?m)^skipped.*%s" % re.escape(self.repo.dir))
        self.assertEqual(self.stamps(), dict.fromkeys(self.AGENT_TXT))

    def test_a_task_done_here_is_a_row(self):
        self.todo(T1)
        self.assertOk(self.af("todo", "done", "t1", "--work", "85", "--wait",
                              "45", "--type", "docs", "--lane", "full",
                              "--mock", "no"))
        self.assertIn(["project", "t1", "2026-10-01", "docs", "full", "no",     # work 150 - 45 (A1)
                       "90", "105", "45", "150", "-", "-", "-", "-", "-", "-", "-"],
                      self.rows())


class _TestEtaFixture:
    def fixture(self):
        self.todo(
            "plain | big | build the thing | est 70m | opened 2026-10-01 18:00 | by main",
            "paged | big | a new page, mock first | est 70m | opened 2026-10-01 18:00 | by main",
            "nomock | big | a script. No mock, no page | est 70m | opened 2026-10-01 18:00 | by main",
            "long | big | a very long one | est 3000m | opened 2026-10-01 18:00 | by main",
            "noest | small | no estimate here | opened 2026-10-01 18:00 | by main")

    def eta(self, *args, **kwargs):
        kwargs.setdefault("now", ETA_NOW)
        return self.af("eta", *args, **kwargs)

    def parts(self, *args, **kwargs):
        """(work left, done, done day, who, when, when day) of the one line."""
        out = self.assertOk(self.eta(*args, **kwargs))
        lines = out.splitlines()
        self.assertEqual(len(lines), 1, out)
        match = ETA_LINE.match(lines[0])
        self.assertIsNotNone(match, lines[0])
        left, done, done_day, who, when, when_day = match.groups()
        return (int(left), done, (done_day or "").strip(), who, when,
                (when_day or "").strip())


class TestEta(_TestEtaFixture, SharedDataCase):
    """One repo for the class: these tests only read (tests/sharedrepo.py)."""

    def test_no_numbers_given_the_whole_estimate_is_left(self):
        # estimate-improve C10: with no --step and no --work-so-far eta reads the line like the board
        # (tests/test_agent_forecast.py); --work-so-far 0 keeps today's math for these formatting tests
        self.assertEqual(self.parts("plain", "--work-so-far", "0"),
                         (70, "21:10", "", "review", "21:10", ""))

    def test_no_numbers_reads_the_line_like_the_board(self):
        # opened 18:00, now 20:00, no stage: 120 minutes of work on a 70 minute estimate, no pace to go by
        r = self.eta("plain")
        self.assertEqual(r.returncode, 1, (r.stdout, r.stderr))
        self.assertIn("--step", r.stderr)

    def test_the_step_says_how_much_is_done(self):
        # step 3 of 7: 30 of 70 done, 40 left
        self.assertEqual(self.parts("plain", "--step", "3"),
                         (40, "20:40", "", "review", "20:40", ""))

    def test_work_so_far_is_taken_from_the_estimate(self):
        self.assertEqual(self.parts("plain", "--work-so-far", "50"),
                         (20, "20:20", "", "review", "20:20", ""))

    def test_work_so_far_wins_over_the_step_while_under_the_estimate(self):
        self.assertEqual(self.parts("plain", "--step", "3", "--work-so-far", "50"),
                         (20, "20:20", "", "review", "20:20", ""))

    def test_over_the_estimate_the_pace_so_far_says_what_is_left(self):
        # 100 min for 5 steps -> 2 steps left = 40 min
        self.assertEqual(self.parts("plain", "--step", "5", "--work-so-far", "100"),
                         (40, "20:40", "", "review", "20:40", ""))

    def test_over_the_estimate_with_no_step_is_one_plain_line(self):
        self.assertRefused(self.eta("plain", "--work-so-far", "100"), "--step")
        self.assertRefused(self.eta("plain", "--step", "0", "--work-so-far", "100"),
                           "--step")

    def test_the_last_step_has_nothing_left(self):
        self.assertEqual(self.parts("plain", "--step", "7"),
                         (0, "20:00", "", "review", "20:00", ""))

    def test_a_known_wait_moves_the_clock_not_the_work(self):
        out = self.assertOk(self.eta("plain", "--step", "3", "--wait", "20"))
        self.assertEqual(self.parts("plain", "--step", "3", "--wait", "20"),
                         (40, "21:00", "", "review", "21:00", ""))
        self.assertRegex(out, r"20 min[^,;]*wait")

    def test_no_wait_given_no_wait_said(self):
        out = self.assertOk(self.eta("plain", "--step", "3"))
        self.assertNotIn("wait", out)

    def test_a_task_with_a_mock_needs_the_owner_at_the_mock(self):
        # step 2: 20 done, 50 left; the mock is ready after 50 x 1/5 = 10 min
        self.assertEqual(self.parts("paged", "--step", "2"),
                         (50, "20:50", "", "mock ready", "20:10", ""))

    def test_a_mock_task_with_no_step_given(self):
        # 70 left; the mock is ready after 70 x 3/7 = 30 min (today's math: --work-so-far 0, see above)
        self.assertEqual(self.parts("paged", "--work-so-far", "0"),
                         (70, "21:10", "", "mock ready", "20:30", ""))

    def test_after_the_mock_gate_the_owner_is_needed_at_the_review(self):
        self.assertEqual(self.parts("paged", "--step", "3"),
                         (40, "20:40", "", "review", "20:40", ""))

    def test_no_mock_in_the_text_means_no_mock(self):
        self.assertEqual(self.parts("nomock", "--step", "1"),
                         (60, "21:00", "", "review", "21:00", ""))

    def test_a_wait_is_not_added_before_the_mock(self):
        self.assertEqual(self.parts("paged", "--step", "2", "--wait", "30"),
                         (50, "21:20", "", "mock ready", "20:10", ""))

    def test_past_midnight_says_tomorrow(self):
        self.assertEqual(self.parts("plain", "--work-so-far", "0", now="2026-10-01 23:40"),
                         (70, "00:50", "tomorrow", "review", "00:50", "tomorrow"))

    def test_later_than_tomorrow_says_the_date(self):
        # 3000 min = 50 h after 2026-10-01 20:00
        self.assertEqual(self.parts("long", "--work-so-far", "0"),
                         (3000, "22:00", "on 2026-10-03", "review", "22:00",
                          "on 2026-10-03"))

    def test_an_unknown_name_is_one_plain_line(self):
        self.assertRefused(self.eta("nope"), "no todo line named: nope")

    def test_no_estimate_on_the_line_is_one_plain_line(self):
        self.assertRefused(self.eta("noest"), "no estimate", "noest")

    def test_no_name_is_usage(self):
        result = self.eta()
        self.assertEqual(result.returncode, 2)

    def test_bad_values_are_refused(self):
        bad = [("--step", "8"), ("--step", "-1"), ("--step", "x"),
               ("--step", "2.5"), ("--work-so-far", "-3"),
               ("--work-so-far", "soon"), ("--wait", "abc"), ("--wait", "-10")]
        for option, value in bad:
            with self.subTest(option=option, value=value):
                self.assertRefused(self.eta("plain", option, value), option)

    def test_an_unknown_option_is_refused(self):
        self.assertRefused(self.eta("plain", "--fast", "1"), "--fast")

    def test_an_option_with_no_value_is_refused(self):
        self.assertRefused(self.eta("plain", "--step"), "--step")

    def test_eta_writes_nothing(self):
        before = (self.read("agent_todo.txt"), self.read("agent_completed.txt"))
        self.assertOk(self.eta("plain", "--step", "3", "--wait", "5"))
        self.assertEqual((self.read("agent_todo.txt"),
                          self.read("agent_completed.txt")), before)

    def test_the_machine_clock_is_used_when_no_fake_clock_is_set(self):
        out = self.assertOk(self.repo.run("agent-file.sh", "eta", "plain", "--work-so-far", "0",
                                          env={"AGENT_FAKE_NOW": ""}))
        self.assertRegex(out.strip(), ETA_LINE)


class TestEtaWrites(_TestEtaFixture, DataCase):
    """The tests of TestEta that write: one repo each."""

    def setUp(self):
        super().setUp()
        self.fixture()

    def test_minutes_round_up(self):
        # step 1 of 7: 10 done, 60 left; step 2: 20 done; 70 x 4/7 = 40
        self.assertEqual(self.parts("plain", "--step", "1")[0], 60)
        self.todo("odd | big | build | est 100m | opened 2026-10-01 18:00 | by main")
        # 100 - 100 x 3/7 = 57.14.. -> 58
        self.assertEqual(self.parts("odd", "--step", "3")[:2], (58, "20:58"))

    def test_eta_does_not_touch_the_agent_files(self):
        os.remove(self.path("agent_ideas.txt"))
        os.remove(self.path("agent_worktree.txt"))
        before = self.stamps()
        self.assertOk(self.eta("plain", "--step", "3"))
        self.assertRefused(self.eta("nope"), "no todo line named: nope")
        self.assertEqual(self.stamps(), before)

    def test_eta_in_a_repo_with_no_agent_files_creates_none(self):
        for name in self.AGENT_TXT:
            os.remove(self.path(name))
        self.assertRefused(self.eta("plain"), "no todo line named: plain")
        self.assertEqual(self.stamps(), dict.fromkeys(self.AGENT_TXT))


class TestUsage(SharedDataCase):

    def usage(self):
        result = self.af()
        self.assertEqual(result.returncode, 2)
        return result.stdout + result.stderr

    def test_usage_lists_the_new_commands(self):
        text = self.usage()
        for phrase in ("todo done", "todo drop", "time", "backfill", "--dry-run",
                       "data", "eta", "idea add", "worktree set", "show"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_usage_lists_the_todo_done_facts(self):
        text = self.usage()
        for phrase in ("--work", "--wait", "--bounces", "--workers", "--mock",
                       "--lane", "--type", "--tests", "--adds", "--merge",
                       "--range"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_usage_lists_the_types(self):
        text = self.usage()
        for kind in TYPES:
            with self.subTest(type=kind):
                self.assertRegex(text, r"\b%s\b" % kind)

    def test_usage_says_how_files_and_lines_are_counted(self):
        text = self.usage()
        self.assertIn("--shortstat", text)
        self.assertIn("merge-base", text)

    def test_usage_says_how_the_repos_are_found(self):
        text = self.usage()
        for phrase in ("world.json", "AGENT_CITY_HOME"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_usage_says_the_eta_rule(self):
        text = self.usage()
        for phrase in ("--step", "--work-so-far", "--wait", "work left",
                       "work so far", "/ 7", "owner needed next", "mock"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_usage_lists_backfill_by_name(self):
        text = self.usage()
        self.assertIn("backfill <name>", text)
        self.assertIn("--force", text)

    def test_usage_says_the_data_line(self):
        text = self.usage()
        self.assertIn("data repo=", text)
        self.assertIn("TIME DATA", text)


IDEA_NOW = "2026-11-13 21:00"


A = "teach todo-est to keep the reason | 2026-11-05 10:02 | by main"


B = "a gap seen (five-fixes S1, pc2) | 2026-11-05 10:03 | by task-manager"


C = "plain idea with no tail"


class IdeaKeepCase(ScriptCase):
    script = "agent-file.sh"

    def set_ideas(self, lines):
        with open(self.repo.path("agent_ideas.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def ideas_raw(self):
        with open(self.repo.path("agent_ideas.txt")) as fh:
            return fh.read()

    def ideas(self):
        return self.ideas_raw().splitlines()

    def keep(self, *args, now=IDEA_NOW):
        return self.repo.run("agent-file.sh", "idea", "keep", *args,
                             env={"AGENT_FAKE_NOW": now})


class TestIdeaKeep(IdeaKeepCase):
    def test_the_field_goes_at_the_end_of_line_n(self):
        self.set_ideas([A, B, C])
        self.assertOk(self.keep("2"))
        self.assertEqual(self.ideas(), [A, B + " | kept 2026-11-13", C])

    def test_it_says_what_it_did(self):
        self.set_ideas([A, B])
        out = self.assertOk(self.keep("1"))
        self.assertIn("idea 1 kept: " + A[:60], out)

    def test_a_line_with_no_tail(self):
        self.set_ideas([A, C])
        self.assertOk(self.keep("2"))
        self.assertEqual(self.ideas(), [A, C + " | kept 2026-11-13"])

    def test_keep_again_replaces_the_date(self):
        self.set_ideas([A])
        self.assertOk(self.keep("1"))
        self.assertOk(self.keep("1", now="2026-11-14 08:00"))
        self.assertEqual(self.ideas(), [A + " | kept 2026-11-14"])

    def test_the_other_lines_stay_byte_for_byte(self):
        odd = "path a/b & c \\d 'q' $x  two spaces | 2026-11-05 10:04 | by main"
        self.set_ideas([odd, A, odd + " again"])
        before = self.ideas_raw()
        self.assertOk(self.keep("2"))
        after = self.ideas_raw()
        self.assertEqual(after, before.replace(A + "\n", A + " | kept 2026-11-13\n", 1))

    def test_a_special_line_itself_is_kept_as_it_is(self):
        odd = "path a/b & c \\d 'q' $x  two spaces | 2026-11-05 10:04 | by main"
        self.set_ideas([odd])
        self.assertOk(self.keep("1"))
        self.assertEqual(self.ideas(), [odd + " | kept 2026-11-13"])

    def test_no_tmp_file_is_left(self):
        self.set_ideas([A])
        self.assertOk(self.keep("1"))
        left = [n for n in os.listdir(self.repo.dir) if n.startswith("agent_ideas.txt.")]
        self.assertEqual(left, [])


class TestIdeaKeepRefusals(IdeaKeepCase):
    def test_bad_numbers_change_nothing(self):
        self.set_ideas([A, B])
        before = self.ideas_raw()
        for bad in ("0", "3", "x", "-1", "1x", ""):
            with self.subTest(n=bad):
                res = self.keep(bad)
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn("no idea number", res.stderr)
                self.assertEqual(self.ideas_raw(), before)

    def test_no_number_is_usage(self):
        self.set_ideas([A])
        before = self.ideas_raw()
        res = self.keep()
        self.assertEqual(res.returncode, 2)
        self.assertEqual(self.ideas_raw(), before)


class TestIdeaKeepWithTheOtherVerbs(IdeaKeepCase):
    def test_idea_list_shows_the_field(self):
        self.set_ideas([A, B])
        self.assertOk(self.keep("1"))
        out = self.assertOk(self.repo.run("agent-file.sh", "idea", "list"))
        self.assertIn("kept 2026-11-13", out)

    def test_idea_rm_removes_a_kept_line(self):
        self.set_ideas([A, B])
        self.assertOk(self.keep("1"))
        self.assertOk(self.repo.run("agent-file.sh", "idea", "rm", "1"))
        self.assertEqual(self.ideas(), [B])

    def test_idea_add_after_a_keep_appends_as_before(self):
        self.set_ideas([A])
        self.assertOk(self.keep("1"))
        self.assertOk(self.repo.run("agent-file.sh", "idea", "add", "new one",
                                    env={"AGENT_FAKE_NOW": IDEA_NOW}))
        self.assertEqual(self.ideas(), [A + " | kept 2026-11-13",
                                        "new one | 2026-11-13 21:00 | by t"])   # agent-files: the git name

    def test_usage_lists_idea_keep(self):
        res = self.repo.run("agent-file.sh")
        self.assertEqual(res.returncode, 2)
        lines = [l for l in (res.stdout + res.stderr).splitlines()
                 if "agent-file.sh idea keep <n>" in l]
        self.assertEqual(len(lines), 1, res.stdout + res.stderr)


STAGE_NOW = tb.NOW   # "2026-11-02 15:00"


STAGES = ["brief", "register", "mock", "tests", "workers", "verify", "push", "report", "e2e", "merge"]


DEFAULTS = {"stage_brief": "1", "stage_register": "1", "stage_mock": "4", "stage_tests": "20",
            "stage_workers": "40", "stage_verify": "15", "stage_push": "2", "stage_report": "2",
            "stage_e2e": "10", "stage_merge": "5", "board_watch_sec": "60",
            "progress_eta_min_pct": "20", "statusline_refresh_sec": "60"}


class StageCase(tb.BoardCase):
    lang = "zh"

    def stage(self, name, *args, now=STAGE_NOW, cwd=None):
        return self.af("todo", "stage", name, *args, now=now, cwd=cwd)

    def board_row(self, name, *args, now=STAGE_NOW, cwd=None):
        return self.row(self.rows(*args, now=now, cwd=cwd), task=name)

    def progress(self, name, **kw):
        return self.board_row(name, **kw)["Progress"]

    def done_by(self, name, **kw):
        return self.board_row(name, **kw)["Done by"]


class TestStageRecord(StageCase):
    def test_the_field_on_the_todo_line(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        before = self.todo_line("alpha")
        out = self.stage("alpha", "tests", now="2026-11-02 14:10").stdout
        line = self.todo_line("alpha")
        # estimate-improve A2: the stage log field sits right before started
        self.assertIn(" | stage log tests 10 | started ", line)
        line = line.replace(" | stage log tests 10", "")
        self.assertTrue(line.startswith(before), line)
        self.assertTrue(line.endswith(" | stage tests since 2026-11-02 14:10"), line)
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        self.assertTrue(out.startswith("todo stage: alpha -> tests"), out)

    def test_set_again_is_replaced_in_place_once(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "tests", now="2026-11-02 14:10")
        self.af("todo", "where", "alpha", "pc2", "/x/alpha")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:30")
        line = self.todo_line("alpha")
        self.assertEqual(len(re.findall(r" \| stage (?!log )", line)), 1, line)   # the stage log is another field
        self.assertIn(" | stage workers 1/2 since 2026-11-02 14:30 | on pc2 /x/alpha", line)

    def test_the_same_value_again_keeps_the_line(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:10")
        before = self.todo_line("alpha")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:40")
        self.assertEqual(self.todo_line("alpha"), before)
        self.stage("alpha", "workers", "2/2", now="2026-11-02 14:50")
        # statusline-vertical: a new slice of the same stage keeps the stage's since
        self.assertIn(" | stage workers 2/2 since 2026-11-02 14:10", self.todo_line("alpha"))

    def test_wait_where_eta_and_done_still_read_the_line(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 13:00")
        self.stage("alpha", "verify", now="2026-11-02 13:30")
        self.wait("alpha", "on", "review", now="2026-11-02 14:00")
        self.af("todo", "where", "alpha", "pc2", "/x/alpha")
        line = self.todo_line("alpha")
        self.assertIn(" | stage verify since 2026-11-02 13:30", line)
        self.assertIn(" | waiting review since 2026-11-02 14:00", line)
        self.wait("alpha", "off", now="2026-11-02 14:20")
        self.assertIn(" | stage verify since 2026-11-02 13:30", self.todo_line("alpha"))
        self.assertIn("work left", self.af("eta", "alpha", "--step", "5").stdout)
        self.af("todo", "done", "alpha", "--work", "70")
        done = self.repo.read("agent_completed.txt")
        self.assertIn(" | alpha | the login form | data ", done)
        self.assertIn(" est=120 ", done)
        self.assertIsNone(self.todo_line("alpha"))

    def test_every_stage_word_is_taken(self):
        self.add("alpha", "the login form", 60)
        for word in STAGES:
            with self.subTest(stage=word):
                self.stage("alpha", word)
                self.assertIn(" | stage %s since " % word, self.todo_line("alpha"))

    def test_refusals(self):
        self.add("alpha", "the login form", 60)
        self.stage("alpha", "tests", now="2026-11-02 14:10")
        for args in (("todo", "stage"),
                     ("todo", "stage", "alpha"),
                     ("todo", "stage", "nobody", "tests"),
                     ("todo", "stage", "alpha", "coffee"),
                     ("todo", "stage", "alpha", "Tests"),
                     ("todo", "stage", "alpha", "tests", "1/2"),
                     ("todo", "stage", "alpha", "workers", "3/2"),
                     ("todo", "stage", "alpha", "workers", "0/0"),
                     ("todo", "stage", "alpha", "workers", "a/b"),
                     ("todo", "stage", "alpha", "workers", "1"),
                     ("todo", "stage", "alpha", "workers", "-1/2"),
                     ("todo", "stage", "alpha", "workers", "1/2", "extra")):
            with self.subTest(args=args):
                self.refused(*args)


class TestStageInWorktree(StageCase):
    def setUp(self):
        super().setUp()
        self.alpha = self.task_worktree("alpha")

    def test_the_stage_line_in_its_own_state(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:30", cwd=self.alpha)
        self.assertIn(" | stage workers 1/2 since 2026-11-02 14:30", self.todo_line("alpha"))
        self.assertIn("STAGE alpha: workers 1/2 | since 2026-11-02 14:30\n", self.state_text(self.alpha))
        self.assertNotIn("STAGE ", self.state_text())

    def test_one_stage_line_replaced_in_place(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.state("brief line one\nHEARTBEAT alpha: step 3 of 7\n", folder=self.alpha)
        self.stage("alpha", "tests", now="2026-11-02 14:10", cwd=self.alpha)
        self.state("a line after\n", folder=self.alpha)
        self.stage("alpha", "verify", now="2026-11-02 14:50", cwd=self.alpha)
        # estimate-improve C11: the first stage also writes the WORK START line, once, right before it
        self.assertEqual(self.state_text(self.alpha),
                         "brief line one\nHEARTBEAT alpha: step 3 of 7\n"
                         "WORK START alpha | 2026-11-02 14:10\n"
                         "STAGE alpha: verify | since 2026-11-02 14:50\n"
                         "a line after\n")
        self.stage("alpha", "verify", now="2026-11-02 14:55", cwd=self.alpha)
        self.assertIn("STAGE alpha: verify | since 2026-11-02 14:50\n", self.state_text(self.alpha))

    def test_no_todo_line_here_writes_the_stage_line_only(self):
        """A task manager on another machine: its todo line is on the laptop."""
        before = self.repo.read("agent_todo.txt")
        result = self.stage("alpha", "tests", now="2026-11-02 14:10", cwd=self.alpha)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.repo.read("agent_todo.txt"), before)
        self.assertIn("STAGE alpha: tests | since 2026-11-02 14:10\n", self.state_text(self.alpha))

    def test_in_the_main_repo_no_stage_line(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "e2e", now="2026-11-02 14:10")
        self.assertIn(" | stage e2e since 2026-11-02 14:10", self.todo_line("alpha"))
        self.assertNotIn("STAGE ", self.state_text())


class TestSelfStage(StageCase):
    def setUp(self):
        super().setUp()
        self.alpha = self.task_worktree("alpha")

    def test_its_todo_line_without_a_stage_reads_its_stage_line(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.state("STAGE alpha: verify | since 2026-11-02 15:00\n", folder=self.alpha)
        r = self.board_row("alpha", "--self", cwd=self.alpha)
        self.assertEqual((r["Progress"], r["Done by"]), ("██████░░░░  66%", "16:00"))

    def test_on_another_machine_its_todo_line_and_stage_come_from_its_state(self):
        self.state("TODO LINE: alpha | big | the login form | est 60m | opened 2026-11-02 14:30 | by main\n",
                   folder=self.alpha)
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:50", cwd=self.alpha)
        r = self.board_row("alpha", "--self", cwd=self.alpha)
        # work 30 < est 60: the estimate, 15:30
        self.assertEqual((r["Progress"], r["Done by"]), ("████░░░░░░  46%", "15:30"))


class TestStageConfKeys(unittest.TestCase):
    """settings-configure: the stage weights and the board numbers are fixed constants."""

    def test_constants(self):
        import agent_conf
        for key, value in DEFAULTS.items():
            with self.subTest(key=key):
                self.assertEqual(str(agent_conf.CONSTANTS[key]), value)


NOW_NOV20_1000 = "2026-11-20 10:00"


class TodoCase(ScriptCase):
    script = "agent-file.sh"

    def af(self, *args, now=NOW_NOV20_1000):
        return self.repo.run("agent-file.sh", *args, env={"AGENT_FAKE_NOW": now, "AGENT_FAKE_HOST": "pc2"})

    def todo(self):
        return self.repo.read("agent_todo.txt") or ""

    def write_todo(self, *lines):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def refused(self, *args):
        before = self.todo()
        r = self.af(*args)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertEqual(self.todo(), before)
        return r


class TestTodoAddLevel(TodoCase):

    def test_after_the_guess(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70", "--guess", "35", "--level", "C"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | guess 35m | level C | opened %s | by main | owner t\n" % NOW_NOV20_1000)

    def test_it_may_stand_anywhere(self):
        self.assertOk(self.af("todo", "add", "--level", "D", "t1", "big", "build it", "70"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | level D | opened %s | by main | owner t\n" % NOW_NOV20_1000)

    def test_no_est(self):
        self.assertOk(self.af("todo", "add", "t1", "small", "fix it", "--level", "A"))
        self.assertEqual(self.todo(), "t1 | small | fix it | level A | opened %s | by main | owner t\n" % NOW_NOV20_1000)

    def test_no_level_is_as_before(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | opened %s | by main | owner t\n" % NOW_NOV20_1000)

    def test_an_old_number_is_stored_as_its_type(self):
        for old, typ in (("0", "A"), ("1", "B"), ("2", "C"), ("3", "C"), ("4", "D")):
            with self.subTest(old=old):
                self.write_todo()
                self.assertOk(self.af("todo", "add", "t1", "small", "fix it", "--level", old))
                self.assertEqual(self.todo(), "t1 | small | fix it | level %s | opened %s | by main | owner t\n" % (typ, NOW_NOV20_1000))

    def test_a_bad_level_is_refused(self):
        for bad in (["--level", "5"], ["--level", "E"], ["--level", "-1"], ["--level", "x"], ["--level", ""], ["--level"]):
            with self.subTest(bad=bad):
                r = self.refused("todo", "add", "t1", "big", "build it", "70", *bad)
                self.assertIn("--level", r.stderr)


class TestTodoLevel(TodoCase):
    LINE = "t1 | big | build it | est 70m | guess 35m | level B | opened 2026-11-20 09:00 | by main | stage tests since 2026-11-20 09:10"

    def test_a_raise_replaces_in_place(self):
        self.write_todo(self.LINE, "t2 | small | other | est 5m | opened 2026-11-20 09:00 | by main")
        r = self.af("todo", "level", "t1", "C")
        self.assertOk(r)
        self.assertIn("todo level: t1 B -> C", r.stdout)
        self.assertEqual(self.todo().splitlines(), [self.LINE.replace("level B", "level C"),
                                                    "t2 | small | other | est 5m | opened 2026-11-20 09:00 | by main"])

    def test_a_missing_level_goes_where_todo_add_puts_it(self):
        self.write_todo("t1 | big | build it | est 70m | opened 2026-11-20 09:00 | by main | stage tests since 2026-11-20 09:10")
        r = self.af("todo", "level", "t1", "C")
        self.assertOk(r)
        self.assertIn("todo level: t1 - -> C", r.stdout)
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | level C | opened 2026-11-20 09:00 | by main | stage tests since 2026-11-20 09:10\n")

    def test_after_the_guess_when_there_is_one(self):
        self.write_todo("t1 | big | build it | est 70m | guess 35m | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "level", "t1", "D"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | guess 35m | level D | opened 2026-11-20 09:00 | by main\n")

    def test_the_same_level_writes_nothing(self):
        self.write_todo(self.LINE)
        before = os.stat(self.repo.path("agent_todo.txt")).st_mtime_ns
        r = self.af("todo", "level", "t1", "B")
        self.assertOk(r)
        self.assertIn("todo level: t1 already type B", r.stdout)
        self.assertEqual(self.todo(), self.LINE + "\n")
        self.assertEqual(os.stat(self.repo.path("agent_todo.txt")).st_mtime_ns, before)

    def test_lower_is_refused(self):
        self.write_todo(self.LINE.replace("level B", "level D"))
        r = self.refused("todo", "level", "t1", "C")
        self.assertIn("only goes up", r.stderr)

    def test_an_old_number_line_stays_readable(self):
        self.write_todo(self.LINE.replace("level B", "level 3"))
        r = self.refused("todo", "level", "t1", "B")                 # old 3 = C: B is lower
        self.assertIn("only goes up", r.stderr)
        self.assertIn("already type C", self.af("todo", "level", "t1", "2").stdout)    # old 3 and 2 are both C
        self.assertOk(self.af("todo", "level", "t1", "D"))
        self.assertEqual(self.todo().splitlines(), [self.LINE.replace("level B", "level D")])

    def test_old_numbers_are_accepted_as_input(self):
        self.write_todo(self.LINE)
        self.assertOk(self.af("todo", "level", "t1", "4"))
        self.assertEqual(self.todo().splitlines(), [self.LINE.replace("level B", "level D")])

    def test_bad_input_is_refused(self):
        self.write_todo(self.LINE)
        for args in (["todo", "level", "nope", "2"], ["todo", "level", "t1", "5"],
                     ["todo", "level", "t1", "E"], ["todo", "level", "t1", "x"], ["todo", "level", "t1"]):
            with self.subTest(args=args):
                self.refused(*args)


class TestTodoDoneLevel(TodoCase):

    def done_line(self):
        rows = [l for l in (self.repo.read("agent_completed.txt") or "").splitlines() if l.strip()]
        self.assertEqual(len(rows), 1, rows)
        return rows[0]

    def test_the_level_is_the_last_key(self):
        self.write_todo("t1 | big | build it | est 70m | guess 35m | level C | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        # estimate-improve: the six new keys follow level
        self.assertIn(" adds=- guess=35 level=C typed=60 est0=70 ", self.done_line())

    def test_an_old_number_is_copied_as_it_is(self):
        self.write_todo("t1 | big | build it | est 70m | guess 35m | level 2 | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertIn(" level=2 typed=", self.done_line())
        self.assertIn(" | t1 | build it | data repo=", self.done_line())

    def test_no_level_is_a_dash(self):
        self.write_todo("t1 | big | build it | est 70m | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertIn(" guess=- level=- typed=", self.done_line())

    def test_a_level_word_in_the_what_is_not_the_level(self):
        self.write_todo("t1 | big | level 9 is a word here | est 70m | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertIn(" level=- typed=", self.done_line())

    def test_the_data_table_keeps_its_columns(self):
        with open(self.repo.path("agent_completed.txt"), "w") as fh:
            fh.write("2026-11-19 | old | an old line | data repo=project type=script lane=full mock=no "
                     "est=10 work=5 wait=0 clock=5 bounces=0 workers=0 files=- lines=- tests=- adds=- guess=-\n")
            fh.write("2026-11-20 | new | a new line | data repo=project type=script lane=full mock=no "
                     "est=10 work=5 wait=0 clock=5 bounces=0 workers=0 files=- lines=- tests=- adds=- guess=8 level=3\n")
        rows = [r.split() for r in self.assertOk(self.af("data")).splitlines()]
        self.assertEqual(rows[0][-2:], ["adds", "guess"])
        self.assertEqual([r[1] for r in rows[1:]], ["old", "new"])
        self.assertEqual(rows[2][-1], "8")


NOW_NOV20_1231 = "2026-11-20 12:31"


class TestTodoWaitCli(tb.WaitCase):
    def setUp(self):
        super().setUp()
        self.add("x", "the task", 60, opened="2026-11-20 11:00", started=False)

    def test_4_1_mock_writes_no_who(self):
        self.wait("x", "on", "mock", now=NOW_NOV20_1231)
        line = self.todo_line("x")
        self.assertTrue(line.endswith(" | waiting mock since 2026-11-20 12:31"), line)
        self.assertNotIn(" | who ", line)

    def test_4_2_who(self):
        self.wait("x", "on", "review", "--who", "v4-Manager", now=NOW_NOV20_1231)
        self.assertTrue(self.todo_line("x").endswith(" | waiting review since 2026-11-20 12:31 | who v4-Manager"),
                        self.todo_line("x"))

    def test_4_3_the_note_before_or_after_the_options(self):
        want = " | waiting hold since 2026-11-20 12:31: 回复插件更新和同步脚本 | who v4-Manager"
        self.wait("x", "on", "hold", "回复插件更新和同步脚本", "--who", "v4-Manager", now=NOW_NOV20_1231)
        self.assertTrue(self.todo_line("x").endswith(want), self.todo_line("x"))
        self.wait("x", "off", now=NOW_NOV20_1231)
        self.wait("x", "on", "hold", "--who", "v4-Manager", "回复插件更新和同步脚本", now=NOW_NOV20_1231)
        self.assertTrue(self.todo_line("x").endswith(want), self.todo_line("x"))

    def test_a_who_with_a_space(self):
        self.wait("x", "on", "hold", "--who", "v4-plus Manager", now=NOW_NOV20_1231)
        self.assertTrue(self.todo_line("x").endswith(" | who v4-plus Manager"), self.todo_line("x"))

    def test_4_4_after(self):
        self.wait("x", "on", "queue", "--after", "state-trim", now=NOW_NOV20_1231)
        self.assertTrue(self.todo_line("x").endswith(" | waiting queue since 2026-11-20 12:31 | after state-trim"),
                        self.todo_line("x"))
        self.wait("x", "on", "queue", "slot", "--after", "state-trim", now="2026-11-20 12:40")
        self.assertIn(" | waiting queue since 2026-11-20 12:40: slot | after state-trim", self.todo_line("x"))
        self.assertEqual(self.todo_line("x").count(" | after "), 1, self.todo_line("x"))

    def test_4_5_a_wait_over_an_open_wait(self):
        self.wait("x", "on", "review", "--who", "A", now="2026-11-20 12:00")
        self.wait("x", "on", "hold", "n", now=NOW_NOV20_1231)
        line = self.todo_line("x")
        self.assertIn(" | waiting hold since 2026-11-20 12:31: n | wait run since 2026-11-20 12:00", line)
        self.assertNotIn(" | who ", line)
        self.assertIn(" | waited 31m", line)
        self.wait("x", "on", "hold", "--who", "B", now="2026-11-20 12:40")
        line = self.todo_line("x")
        self.assertIn(" | waiting hold since 2026-11-20 12:40 | who B | wait run since 2026-11-20 12:00", line)
        self.assertEqual(line.count("wait run since"), 1, line)
        self.assertIn(" | waited 40m", line)
        r = self.row(self.rows(now="2026-11-20 12:50"), task="x")
        self.assertEqual(r["Status"], "等待 B · 已等 50分钟")

    def test_4_5c_a_wait_over_a_wait_with_a_note(self):
        # reviewer finding 1: the date of a waiting field with a note was read with the note's colon
        self.wait("x", "on", "mock", "看规则表", now="2026-11-20 12:00")
        self.wait("x", "on", "mock", "看规则表 v2", now="2026-11-20 12:21")
        line = self.todo_line("x")
        self.assertIn(" | waiting mock since 2026-11-20 12:21: 看规则表 v2 | wait run since 2026-11-20 12:00 | "
                      "waited 21m", line)
        self.assertNotIn("12:00:", line)
        r = self.row(self.rows(now=NOW_NOV20_1231), task="x")
        self.assertEqual(r["Status"], "等待 你 · 看规则表 v2 · 已等 31分钟")
        self.wait("x", "on", "hold", "下一个: 等 v4", "--who", "v4-Manager", now="2026-11-20 12:25")
        self.assertIn(" | who v4-Manager | wait run since 2026-11-20 12:00 | waited 25m", self.todo_line("x"))
        self.wait("x", "off", now=NOW_NOV20_1231)
        self.assertIn(" | waited 31m", self.todo_line("x"))

    def test_4_5b_the_field_order(self):
        self.wait("x", "on", "queue", "--after", "a", now="2026-11-20 12:00")
        self.wait("x", "on", "queue", "--after", "b", now=NOW_NOV20_1231)
        line = self.todo_line("x")
        self.assertIn(" | waiting queue since 2026-11-20 12:31 | after b | wait run since 2026-11-20 12:00", line)
        self.assertNotIn("after a", line)

    def test_4_6_off_takes_the_fields_away(self):
        self.wait("x", "on", "review", "--who", "A", now="2026-11-20 12:00")
        self.wait("x", "on", "queue", "--after", "b", now="2026-11-20 12:10")
        self.wait("x", "off", now=NOW_NOV20_1231)
        line = self.todo_line("x")
        for gone in ("waiting ", " | who ", " | after ", "wait run since"):
            self.assertNotIn(gone, line)
        self.assertIn(" | waited 31m", line)
        self.wait("x", "on", "hold", now="2026-11-20 12:40")
        self.assertNotIn("wait run since", self.todo_line("x"))

    def test_4_7_refusals(self):
        for args in (("on", "queue", "--who", "a"),
                     ("on", "mock", "--after", "a"),
                     ("on", "hold", "--after", "a"),
                     ("on", "hold", "--who"),
                     ("on", "hold", "--who", ""),
                     ("on", "hold", "--who", "a | b"),
                     ("on", "hold", "--who", " "),
                     ("on", "hold", "--who", "--after"),
                     ("on", "queue", "--after", "--who"),
                     ("on", "queue", "--after", "  "),
                     ("on", "review", "--who", "a\nb"),
                     ("on", "hold", "--who", "a", "--who", "b"),
                     ("on", "queue", "--after"),
                     ("on", "queue", "--after", ""),
                     ("on", "queue", "--after", "a\nb"),
                     ("on", "queue", "--after", "a", "--after", "b"),
                     ("on", "hold", "--x", "a"),
                     ("on", "hold", "a", "b"),
                     ("off", "--who", "a")):
            with self.subTest(args=args):
                self.refused("todo", "wait", "x", *args, now=NOW_NOV20_1231)


class TestTodoStageCli(tb.WaitCase):
    def stage(self, name, *args, now=NOW_NOV20_1231):
        self.af("todo", "stage", name, *args, now=now)

    def test_6_5_the_first_stage(self):
        self.add("x", "the task", 60, opened="2026-11-20 12:00", started=False)
        self.stage("x", "brief", now="2026-11-20 12:21")
        line = self.todo_line("x")
        self.assertIn(" | started 2026-11-20 12:21 | stage brief since 2026-11-20 12:21", line)
        self.assertNotIn(" after ", line)

    def test_6_6_after_closed_waits(self):
        self.add("x", "the task", 60, opened="2026-11-20 11:00", started=False)
        self.wait("x", "on", "queue", now="2026-11-20 11:35")
        self.wait("x", "off", now="2026-11-20 12:21")
        self.stage("x", "brief", now="2026-11-20 12:21")
        self.assertIn(" | started 2026-11-20 12:21 after 46m waited | stage brief since 2026-11-20 12:21",
                      self.todo_line("x"))

    def test_6_7_a_wait_still_open_at_the_start(self):
        self.add("x", "the task", 60, opened="2026-11-20 11:00", started=False)
        self.wait("x", "on", "queue", now="2026-11-20 11:41")
        self.wait("x", "off", now="2026-11-20 11:51")
        self.wait("x", "on", "hold", now="2026-11-20 11:51")
        self.stage("x", "brief", now="2026-11-20 12:21")
        self.assertIn(" | started 2026-11-20 12:21 after 40m waited", self.todo_line("x"))
        self.wait("x", "off", now="2026-11-20 12:41")
        r = self.row(self.rows(now="2026-11-20 12:51"), task="x")
        self.assertEqual((r["Status"], r["Work"], r["Wait"], r["Done by"]), ("进行中", "10m", "1h", "13:41"))

    def test_6_7b_an_open_wait_with_a_note_at_the_start(self):
        # reviewer finding 2: the open wait's since, read with the note's colon
        self.add("x", "the task", 60, opened="2026-11-20 11:00", started=False)
        self.wait("x", "on", "hold", "等: 槽位", now="2026-11-20 11:51")
        self.stage("x", "brief", now="2026-11-20 12:21")
        self.assertIn(" | started 2026-11-20 12:21 after 30m waited", self.todo_line("x"))

    def test_6_8_later_stages_never_change_it(self):
        self.add("x", "the task", 60, opened="2026-11-20 12:00", started=False)
        self.stage("x", "brief", now="2026-11-20 12:21")
        self.stage("x", "tests", now="2026-11-20 12:40")
        self.stage("x", "workers", "1/2", now="2026-11-20 12:45")
        line = self.todo_line("x")
        self.assertEqual(line.count(" | started "), 1, line)
        self.assertIn(" | started 2026-11-20 12:21 | ", line)

    def test_6_9_an_old_line_with_a_stage_gets_no_started(self):
        self.put("old | big | w | est 60m | opened 2026-11-20 10:31 | by main | stage tests since 2026-11-20 12:00")
        self.stage("old", "verify", now=NOW_NOV20_1231)
        self.assertNotIn("started", self.todo_line("old"))

    def test_6_10_a_worktree_with_no_todo_line(self):
        alpha = self.task_worktree("alpha")
        self.af("todo", "stage", "alpha", "brief", now=NOW_NOV20_1231, cwd=alpha)
        self.assertIn("STAGE alpha: brief | since 2026-11-20 12:31\n", self.state_text(alpha))
        self.assertNotIn("started", self.state_text(alpha))


class TestHeartbeatCommand(ScriptCase):
    """C51: the task manager writes its heartbeat with one command, so the form cannot be typed wrong."""
    script = "agent-file.sh"

    def state(self):
        p = os.path.join(self.repo.dir, "agent_state.txt")
        return open(p).read() if os.path.exists(p) else ""

    def test_the_line(self):
        r = self.repo.run("agent-file.sh", "heartbeat", "test-slim", "4", "35", "workers 2 of 3 running")
        self.assertEqual(r.returncode, 0, r.stderr)
        last = self.state().strip().splitlines()[-1]
        self.assertRegex(last, r"^HEARTBEAT test-slim: step 4 of 7, work 35m, workers 2 of 3 running \| "
                               r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_refusals(self):
        for args in (("t", "8", "35", "x"), ("t", "4", "ten", "x"), ("t", "4", "35", ""), ("t", "4")):
            with self.subTest(args=args):
                before = self.state()
                r = self.repo.run("agent-file.sh", "heartbeat", *args)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertEqual(self.state(), before)

    def test_the_brief_names_it(self):
        with open(os.path.join(os.path.dirname(HERE), "skills", "dispatch", "SKILL.md")) as fh:
            brief = fh.read()
        line = [l for l in brief.splitlines() if l.startswith("HEARTBEAT:")][0]
        self.assertIn("agent-file.sh heartbeat", line)


if __name__ == "__main__":
    unittest.main()
