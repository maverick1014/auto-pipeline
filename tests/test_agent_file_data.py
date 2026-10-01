"""Tests for the time data in bin/agent-file.sh (task estimate-data).

WHY (owner, 2026-09-30). An estimate means AGENT WORK minutes only. Waiting
(mock gate, owner question or review, holds, suite slot) is recorded apart and
never counted as work. Every finished task leaves one data line, so a later
task can train an estimate skill from 30 of them. Nothing is invented.

CONTRACT (the clock of every command)
    AGENT_FAKE_NOW="YYYY-MM-DD HH:MM" replaces the machine's clock (tests
    only, same idea as AGENT_FAKE_RAM). Unset or empty -> the machine's clock.

CONTRACT (E1, E2: todo done)
    agent-file.sh todo done <name> ["<result>"] [--work <m>] [--wait <m>]
        [--bounces <n>] [--workers <n>] [--mock yes|no] [--lane fast|full]
        [--type <t>] [--tests <n>] [--adds <n>]
        [--merge <commit> | --range <a>..<b>]

    Every option is optional; the old calls (`todo done <name>` and
    `todo done <name> "<result>"`) keep working. The result text is accepted
    and not stored, as before.

    The line leaves agent_todo.txt and lands in agent_completed.txt as

        <date> | <name> | <what> | data repo=<r> type=<t> lane=<l> mock=<yes|no> est=<m> work=<m> wait=<m> clock=<m> bounces=<n> workers=<n> files=<n> lines=<n> tests=<n> adds=<n>

    Keys always in that order, one space between them, "-" for a value that
    is not known. Computed by the script itself:
        repo    the folder name of the project's main repo
        est     from the todo line ("est <n>m")
        clock   minutes from "opened" on the todo line to now (work + wait)
        files, lines   only when asked for:
            --merge <commit>    git diff --shortstat <commit>^1 <commit>
                                (what the merge brought into the main branch)
            --range <a>..<b>    git diff --shortstat <merge-base a b> <b>
                                (what b changed since it left a)
            lines = lines added + lines deleted.
            Neither given -> files=- lines=- and stdout says "not counted".
            Both given, or a commit git does not know -> refused.
    <t> is one word of: page server script docs cloud app data mixed.

    Refused (negative, not a number, unknown word, unknown option, a missing
    value): ONE plain line on stderr naming the option, exit 1, nothing moves.

    stdout keeps "todo done: <name>" and adds "TIME DATA: <n> of 30", n = the
    finished tasks of this repo that have a work number.

CONTRACT (E3: time)
    agent-file.sh time -> table, columns: name est work wait clock ratio
    ratio = work / est, one decimal. A line with no work number shows "-" for
    work and ratio; its minutes stay under clock. An old line
    ("est <n>m actual <n>m") is read as est + clock. Dropped lines are skipped.

CONTRACT (E4: backfill)
    agent-file.sh backfill [--dry-run]
    One-time. For every old line (no data block, not dropped) it looks in the
    line's text for the work the result already says:
        "Work 67m + bounce 10m = 77m"  -> work 77 (the total)
        "work 108", "est 150 work 108" -> work 108
        "wait 45m", "wait 45"          -> wait 45
    (letter case does not matter, the "m" is optional). A line with a work
    number is rewritten with a data block: est and clock from its old
    "est <n>m actual <n>m", work and wait as found, repo as above, every
    other key "-". The text of the line stays. Every line is named on
    stdout: "took: <name> work <n> wait <n|->" or "skipped: <name> (<why>)",
    then "backfill: took <n>, skipped <n>". --dry-run prints the same and
    writes nothing. A second run takes nothing.

CONTRACT (E4b: backfill one old line by name; main manager, 2026-10-01)
    agent-file.sh backfill <name> [--dry-run] [--force] <the todo done options>
    The main manager knows the real work and wait of past tasks. This sets
    the data of ONE finished line by name, with the same options and the
    same refusals as `todo done` (--work --wait --bounces --workers --mock
    --lane --type --tests --adds, --merge | --range).
    - The line = the last line of agent_completed.txt named <name> that is
      not dropped. Only that line is rewritten; its text stays.
    - An old line: est and clock from its "est <n>m actual <n>m", the given
      facts, repo as in todo done, every other key "-".
    - A line that already has data: refused, the line names --force. With
      --force the given facts replace, every other key keeps its value.
    - Refused, one plain line on stderr, exit 1, nothing written: no line of
      that name ("no completed line named: <name>"), only a dropped line
      (the line says "dropped"), no fact given, nonsense.
    - stdout: "wrote: <the new line>", then "TIME DATA: <n> of 30".
      --dry-run: "would write: <the new line>" and nothing is written.

CONTRACT (E5: data, all repos on this machine, read-only)
    agent-file.sh data [<repo path>...]
    One table: repo name date type lane mock est work wait clock bounces
    workers files lines tests adds. One row per finished task (dropped lines
    skipped). Repos, in this order, the same repo (real path) once:
        1. this repo
        2. the keys of "territories" in world.json under the city home
           ($AGENT_CITY_HOME, default $HOME/.claude/agent-city); a key
           "<repo>/.git" names <repo>
        3. the lines of joined-repos.txt under the city home (absolute
           paths, "#" comments)
        4. the paths given as arguments
    It reads <repo>/agent_completed.txt and no other file of another repo,
    and writes nothing there. A repo without that file is skipped, one line
    on stderr naming its path. A missing or broken world.json is not an
    error. The repo column of a row is its data block's repo, else the
    folder name of the repo.

CONTRACT (E6: eta)
    agent-file.sh eta <name> [--step <n>] [--work-so-far <m>] [--wait <m>]
    ONE line on stdout with a duration and a clock time:
        about <n> min of work left, done around <HH:MM>; owner needed next: <mock ready|review> about <HH:MM>
    Rule (also in the usage text):
        est            from the open todo line <name>
        work so far    --work-so-far, else est x step / 7 (no step = 0)
        work left      est - work so far
          over the estimate (work so far >= est):
                       work so far x (7 - step) / step, the pace so far;
                       over with no step (or step 0) -> one plain line on
                       stderr that names --step, exit 1
        done           now + work left + wait (--wait = known waiting still
                       ahead, minutes; it is said in the line, never added
                       to the work)
        owner needed next
                       the todo text says "mock" (and not "no mock") and
                       step <= 2 -> "mock ready", at now + work left x
                       (3 - step) / (7 - step); else "review", at done
        A clock time that is not today: "<HH:MM> tomorrow", later
        "<HH:MM> on <YYYY-MM-DD>". Minutes round up.
    step is 0..7. Unknown name, no estimate on the line, a bad value or an
    unknown option: one plain line on stderr, exit 1. eta writes nothing.
"""

import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase

KEYS = ["repo", "type", "lane", "mock", "est", "work", "wait", "clock",
        "bounces", "workers", "files", "lines", "tests", "adds"]
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


# --------------------------------------------------------------------------
# E1, E2: todo done takes the facts and writes one data line
# --------------------------------------------------------------------------

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
                est=90, work=85, wait=45, clock=150, bounces=1, workers=3,
                tests=38, adds=2)])
        self.assertNotIn("t1 |", self.read("agent_todo.txt"))

    def test_the_old_call_still_works_and_knows_what_it_can(self):
        out = self.assertOk(self.af("todo", "done", "t1"))
        self.assertIn("todo done: t1", out)
        self.assertEqual(self.completed_lines(), [
            "2026-10-01 | t1 | build the thing | "
            + block(repo="project", est=90, clock=150)])

    def test_the_old_call_with_a_result_text_still_works(self):
        self.assertOk(self.af("todo", "done", "t1", "merged abc123, 38 tests OK"))
        self.assertEqual(self.completed_lines(), [
            "2026-10-01 | t1 | build the thing | "
            + block(repo="project", est=90, clock=150)])

    def test_facts_after_a_result_text(self):
        self.assertOk(self.af("todo", "done", "t1", "merged abc123",
                              "--work", "85", "--lane", "full"))
        self.assertEqual(self.completed_lines(), [
            "2026-10-01 | t1 | build the thing | "
            + block(repo="project", lane="full", est=90, work=85, clock=150)])

    def test_zero_is_a_number(self):
        self.assertOk(self.af("todo", "done", "t1", "--work", "12",
                              "--wait", "0", "--bounces", "0", "--adds", "0"))
        self.assertIn(block(repo="project", est=90, work=12, wait=0,
                            clock=150, bounces=0, adds=0),
                      self.completed_lines()[0])

    def test_no_estimate_and_no_opened_time_are_a_dash(self):
        self.todo("t2 | small | a thing | by main")
        self.assertOk(self.af("todo", "done", "t2", "--work", "5"))
        self.assertEqual(self.completed_lines(), [
            "2026-10-01 | t2 | a thing | " + block(repo="project", work=5)])

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

    def test_time_data_does_not_count_a_task_done_without_work(self):
        self.completed(
            "2026-09-30 | a | x | " + block(repo="project", est=60, work=50, clock=70))
        out = self.assertOk(self.af("todo", "done", "t1"))
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


# --------------------------------------------------------------------------
# E3: time
# --------------------------------------------------------------------------

class TestTimeTable(DataCase):

    def setUp(self):
        super().setUp()
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

    def test_dropped_lines_are_skipped(self):
        self.assertNotIn("gone", [r[0] for r in self.rows()])

    def test_one_row_per_finished_task(self):
        self.assertEqual(len(self.rows()), 5)

    def test_an_empty_file_prints_the_header_only(self):
        self.completed()
        self.assertEqual(self.rows(),
                         [["name", "est", "work", "wait", "clock", "ratio"]])

    def test_a_task_done_now_shows_up(self):
        self.todo(T1)
        self.assertOk(self.af("todo", "done", "t1", "--work", "45", "--wait", "30"))
        self.assertIn(["t1", "90", "45", "30", "150", "0.5"], self.rows())


# --------------------------------------------------------------------------
# E4: backfill
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# E4b: backfill one old line by name
# --------------------------------------------------------------------------

TWICE_DROPPED = "2026-09-10 | twice | first try | est 60m actual - | dropped: rescoped"
TWICE_DONE = "2026-09-12 | twice | second try | est 45m actual 80m"


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

    def test_it_sets_the_facts_of_an_old_line(self):
        self.assertOk(self.af("backfill", "d-task", *self.D_ARGS))
        self.assertEqual(self.line("d-task"), [self.D_NEW])

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


# --------------------------------------------------------------------------
# E5: data, all repos on this machine
# --------------------------------------------------------------------------

HEADER = ["repo", "name", "date"] + KEYS[1:]

HERE_DATA = "2026-10-01 | here-new | a data line | " + block(
    repo="project", type="script", lane="full", mock="no", est=90, work=85,
    wait=45, clock=150, bounces=1, workers=3, files=7, lines=412, tests=38,
    adds=2)
HERE_ROW = ["project", "here-new", "2026-10-01", "script", "full", "no", "90",
            "85", "45", "150", "1", "3", "7", "412", "38", "2"]
SHOP_OLD = "2026-09-01 | shop-old | a legacy line of the shop | est 60m actual 75m"
SHOP_ROW = ["shop", "shop-old", "2026-09-01", "-", "-", "-", "60", "-", "-",
            "75", "-", "-", "-", "-", "-", "-"]
SHOP_DROPPED = "2026-09-02 | shop-gone | dropped | est 60m actual - | dropped: no"
API_DATA = "2026-09-03 | api-new | a data line of the api | " + block(
    repo="api", type="server", lane="fast", mock="no", est=15, work=9, wait=0,
    clock=11, bounces=0, workers=0, files=2, lines=31, tests=1, adds=0)
API_ROW = ["api", "api-new", "2026-09-03", "server", "fast", "no", "15", "9",
           "0", "11", "0", "0", "2", "31", "1", "0"]
EXTRA_OLD = "2026-09-04 | extra-old | given by hand | est 20m actual 33m"
EXTRA_ROW = ["extra", "extra-old", "2026-09-04", "-", "-", "-", "20", "-", "-",
             "33", "-", "-", "-", "-", "-", "-"]


class TestDataAllRepos(DataCase):

    def setUp(self):
        super().setUp()
        self.completed(HERE_DATA)
        self.shop = self.other("shop", SHOP_OLD, SHOP_DROPPED)
        self.api = self.other("api", API_DATA)
        self.extra = self.other("extra", EXTRA_OLD)
        self.empty = self.repo.make_project("no-pipeline")
        self.city = os.path.join(self.repo.base, "cityhome")
        os.mkdir(self.city)
        self.world({self.shop + "/.git": {"name": "shop"}})
        self.joined(self.api)

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

    def joined(self, *paths):
        with open(os.path.join(self.city, "joined-repos.txt"), "w") as fh:
            fh.write("# joined repos, one path per line\n\n")
            fh.write("".join(p + "\n" for p in paths))

    def data(self, *args, **kwargs):
        env = {"AGENT_CITY_HOME": self.city}
        env.update(kwargs.pop("env", None) or {})
        return self.af("data", *args, env=env, **kwargs)

    def rows(self, *args, **kwargs):
        out = self.assertOk(self.data(*args, **kwargs))
        return [l.split() for l in out.splitlines() if l.strip()]

    def test_the_header_has_the_repo_column_first(self):
        self.assertEqual(self.rows()[0], HEADER)

    def test_this_repo_the_city_world_and_the_joined_list_are_read(self):
        rows = self.rows()
        self.assertEqual(rows[1:], [HERE_ROW, SHOP_ROW, API_ROW])

    def test_a_path_given_as_an_argument_is_read_too(self):
        self.assertEqual(self.rows(self.extra)[1:],
                         [HERE_ROW, SHOP_ROW, API_ROW, EXTRA_ROW])

    def test_the_same_repo_is_read_once(self):
        self.world({self.shop + "/.git": {"name": "shop"},
                    self.repo.dir + "/.git": {"name": "project"},
                    self.api + "/.git": {"name": "api"}})
        self.joined(self.api, self.shop)
        rows = self.rows(self.shop, self.api + "/", self.repo.dir)
        self.assertEqual(rows[1:], [HERE_ROW, SHOP_ROW, API_ROW])

    def test_dropped_lines_are_not_rows(self):
        self.assertNotIn("shop-gone", [r[1] for r in self.rows()])

    def test_a_repo_without_the_file_is_skipped_and_said(self):
        self.world({self.shop + "/.git": {"name": "shop"},
                    self.empty + "/.git": {"name": "no-pipeline"}})
        result = self.data()
        self.assertOk(result)
        self.assertRegex(result.stderr, r"(?m)^skipped.*%s" % re.escape(self.empty))
        self.assertFalse(os.path.exists(os.path.join(self.empty, "agent_completed.txt")))

    def test_a_missing_path_argument_is_skipped_and_said(self):
        gone = os.path.join(self.repo.base, "not-there")
        result = self.data(gone)
        self.assertOk(result)
        self.assertIn(gone, result.stderr)

    def test_no_city_home_still_prints_this_repo(self):
        rows = self.rows(env={"AGENT_CITY_HOME": os.path.join(self.repo.base, "nope")})
        self.assertEqual(rows, [HEADER, HERE_ROW])

    def test_a_broken_world_file_is_not_an_error(self):
        with open(os.path.join(self.city, "world.json"), "w") as fh:
            fh.write("{ not json")
        self.assertEqual(self.rows()[1:], [HERE_ROW, API_ROW])

    def test_a_territory_key_that_is_not_a_repo_folder_is_no_error(self):
        self.world({"dir:loose": {"name": "loose"},
                    self.shop + "/.git": {"name": "shop"}})
        self.assertEqual(self.rows()[1:], [HERE_ROW, SHOP_ROW, API_ROW])

    def test_the_default_city_home_is_under_home(self):
        home = self.repo.fake_home()
        default = os.path.join(home, ".claude", "agent-city")
        os.makedirs(default)
        with open(os.path.join(default, "joined-repos.txt"), "w") as fh:
            fh.write(self.extra + "\n")
        rows = self.rows(env={"AGENT_CITY_HOME": ""})
        self.assertEqual(rows[1:], [HERE_ROW, EXTRA_ROW])

    def snapshot(self, *paths):
        seen = {}
        for root in paths:
            for folder, _dirs, files in os.walk(root):
                for name in files:
                    full = os.path.join(folder, name)
                    with open(full, "rb") as fh:
                        seen[full] = (fh.read(), os.stat(full).st_mtime_ns)
        return seen

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

    def test_a_task_done_here_is_a_row(self):
        self.todo(T1)
        self.assertOk(self.af("todo", "done", "t1", "--work", "85", "--wait",
                              "45", "--type", "docs", "--lane", "full",
                              "--mock", "no"))
        self.assertIn(["project", "t1", "2026-10-01", "docs", "full", "no",
                       "90", "85", "45", "150", "-", "-", "-", "-", "-", "-"],
                      self.rows())


# --------------------------------------------------------------------------
# E6: eta
# --------------------------------------------------------------------------

ETA_NOW = "2026-10-01 20:00"
ETA_LINE = re.compile(
    r"^about (\d+) min of work left.*, done around (\d\d:\d\d)"
    r"( tomorrow| on \d{4}-\d\d-\d\d)?; "
    r"owner needed next: (mock ready|review) about (\d\d:\d\d)"
    r"( tomorrow| on \d{4}-\d\d-\d\d)?$")


class TestEta(DataCase):

    def setUp(self):
        super().setUp()
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

    def test_no_numbers_given_the_whole_estimate_is_left(self):
        self.assertEqual(self.parts("plain"),
                         (70, "21:10", "", "review", "21:10", ""))

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

    def test_minutes_round_up(self):
        # step 1 of 7: 10 done, 60 left; step 2: 20 done; 70 x 4/7 = 40
        self.assertEqual(self.parts("plain", "--step", "1")[0], 60)
        self.todo("odd | big | build | est 100m | opened 2026-10-01 18:00 | by main")
        # 100 - 100 x 3/7 = 57.14.. -> 58
        self.assertEqual(self.parts("odd", "--step", "3")[:2], (58, "20:58"))

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
        # 70 left; the mock is ready after 70 x 3/7 = 30 min
        self.assertEqual(self.parts("paged"),
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
        self.assertEqual(self.parts("plain", now="2026-10-01 23:40"),
                         (70, "00:50", "tomorrow", "review", "00:50", "tomorrow"))

    def test_later_than_tomorrow_says_the_date(self):
        # 3000 min = 50 h after 2026-10-01 20:00
        self.assertEqual(self.parts("long"),
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
        out = self.assertOk(self.repo.run("agent-file.sh", "eta", "plain",
                                          env={"AGENT_FAKE_NOW": ""}))
        self.assertRegex(out.strip(), ETA_LINE)


# --------------------------------------------------------------------------
# the usage text says all of it
# --------------------------------------------------------------------------

class TestUsage(DataCase):

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
        for phrase in ("world.json", "joined-repos.txt", "AGENT_CITY_HOME"):
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


if __name__ == "__main__":
    unittest.main()
