"""Tests of agent-start.sh --clean: the main manager's clean after a whole-repo close case.

One class per feature. Older task contracts: git log -p of this file.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT  # noqa: E402
from test_agent_main_seat import NOBODY, SeatCase  # noqa: E402

ARCHIVE_RE = re.compile(r"^agent_state\.\d{4}-\d\d-\d\d-\d{6}\.txt$")
CLEAR_LINE = 'orca terminal send --terminal %s --text "/clear" --enter'
MAX_BYTES = 1200


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


class CleanCase(SeatCase):
    """A main manager that holds the lock by a lock line, with nothing else running."""

    OLD = "OLD STATE of the closed case\ndecision: ship it\nhandle term_task-9\n"

    def main(self, term="term_main-1", sid="sid-before"):
        me = self.live()
        self.set_lock("%d 2026-10-01 09:00 %s %s\n" % (me, sid, term or "-"))
        return me

    def clean(self, *carry, pid, kind="orca", env=None):
        full = {}
        if kind:
            full["AGENT_RUNTIME"] = kind
        full.update(env or {})
        return self.start("--clean", *carry, pid=pid, env=full)

    @property
    def state_path(self):
        return self.repo.path("agent_state.txt")

    def write_state(self, text=None):
        with open(self.state_path, "w") as fh:
            fh.write(self.OLD if text is None else text)

    def state_lines(self):
        with open(self.state_path) as fh:
            return [line.rstrip("\n") for line in fh if line.strip()]

    def archives(self):
        names = [os.path.basename(p) for p in glob.glob(self.repo.path("agent_state.*.txt"))]
        return sorted(names)

    def lock_text(self):
        with open(self.lock_path) as fh:
            return fh.read()

    def write_todo(self, *rows):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("".join(row + "\n" for row in rows))

    def next_lines(self, out):
        return [line for line in out.splitlines() if line.startswith("NEXT")]


# -- K2: only the main manager, and nothing moves for anyone else ---------------------------

class TestOnlyTheMainManager(CleanCase):
    def assertRefused(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout + result.stderr)
        self.assertEqual(self.archives(), [])
        with open(self.state_path) as fh:
            self.assertEqual(fh.read(), self.OLD)

    def test_a_second_session_is_refused(self):
        main = self.main()
        self.write_state()
        before = self.lock_text()
        result = self.clean(pid=5151)
        self.assertRefused(result)
        self.assertIn(str(main), result.stdout + result.stderr)
        self.assertEqual(self.lock_text(), before)

    def test_a_spawned_agent_is_refused(self):
        me = self.main()
        self.write_state()
        self.assertRefused(self.clean(pid=me, env={"AGENT_ROLE": "task-manager"}))

    def test_no_lock_is_refused_and_no_lock_is_written(self):
        self.write_state()
        self.assertRefused(self.clean(pid=5151))
        self.assertIsNone(self.lock_words())

    def test_a_released_session_is_refused(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.start("--release", pid=me))
        self.assertRefused(self.clean(pid=me))
        self.assertIsNone(self.lock_words())


# -- K2 (b): what is left running is checked, not guessed -----------------------------------

class TestLeftRunning(CleanCase):
    def assertStopped(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("LEFT RUNNING:", result.stdout)
        refused = [l for l in result.stdout.splitlines() if l.startswith("REFUSED")]
        self.assertEqual(len(refused), 1, result.stdout)
        self.assertIn("Nothing changed", refused[0])
        self.assertEqual(self.next_lines(result.stdout), [])
        self.assertEqual(self.archives(), [])
        with open(self.state_path) as fh:
            self.assertEqual(fh.read(), self.OLD)

    def test_a_live_worktree_line_stops_it(self):
        me = self.main()
        self.write_state()
        self.repo.set_worktree_lines([("/tmp/wt/alpha", "alpha", "working")])
        result = self.clean(pid=me)
        self.assertStopped(result)
        left = [l for l in result.stdout.splitlines() if l.startswith("LEFT RUNNING:")]
        self.assertEqual(len(left), 1, result.stdout)
        self.assertIn("/tmp/wt/alpha", left[0])
        self.assertIn("alpha", left[0])
        self.assertIn("agent-file.sh worktree rm", left[0])

    def test_every_left_thing_gets_its_own_line(self):
        me = self.main()
        self.write_state()
        self.repo.set_worktree_lines([("/tmp/wt/alpha", "alpha", "working"),
                                      ("/tmp/wt/beta", "beta", "idle")])
        result = self.clean(pid=me)
        self.assertStopped(result)
        left = [l for l in result.stdout.splitlines() if l.startswith("LEFT RUNNING:")]
        self.assertEqual(len(left), 2, result.stdout)

    def test_after_the_stop_the_same_command_goes_through(self):
        me = self.main()
        self.write_state()
        self.repo.set_worktree_lines([("/tmp/wt/alpha", "alpha", "working")])
        self.assertStopped(self.clean(pid=me))
        self.repo.set_worktree_lines([])
        self.assertOk(self.clean(pid=me))
        self.assertEqual(len(self.archives()), 1)

    def test_crons_are_named_because_a_script_cannot_see_them(self):
        me = self.main()
        self.write_state()
        out = self.assertOk(self.clean(pid=me))
        check = [l for l in out.splitlines() if l.startswith("CHECK")]
        self.assertEqual(len(check), 1, out)
        self.assertIn("CronList", check[0])


# -- K2 (a): the archive and the fresh short state ------------------------------------------

class TestTheArchive(CleanCase):
    def test_the_old_state_moves_next_to_it_same_bytes(self):
        me = self.main()
        self.write_state()
        out = self.assertOk(self.clean(pid=me))
        names = self.archives()
        self.assertEqual(len(names), 1, names)
        self.assertRegex(names[0], ARCHIVE_RE)
        with open(self.repo.path(names[0])) as fh:
            self.assertEqual(fh.read(), self.OLD)
        self.assertIn(names[0], out)

    def test_the_archive_is_git_ignored_and_no_tracked_file_changes(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        name = self.archives()[0]
        ignored = subprocess.run(["git", "-C", self.repo.dir, "check-ignore", "-q", name])
        self.assertEqual(ignored.returncode, 0, "%s is not ignored" % name)
        self.assertFalse(os.path.exists(self.repo.path(".gitignore")))
        status = subprocess.run(["git", "-C", self.repo.dir, "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        self.assertNotIn("agent_state.2", status)

    def test_the_exclude_line_is_added_once(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        self.assertOk(self.clean(pid=me))
        with open(self.repo.path(".git", "info", "exclude")) as fh:
            rows = [line.strip() for line in fh]
        self.assertEqual(rows.count("agent_state.*.txt"), 1, rows)

    def test_the_newest_five_stay(self):
        me = self.main()
        self.write_state()
        old = ["agent_state.2026-09-0%d-100000.txt" % day for day in range(1, 7)]
        for name in old:
            with open(self.repo.path(name), "w") as fh:
                fh.write(name + "\n")
        self.assertOk(self.clean(pid=me))
        names = self.archives()
        self.assertEqual(len(names), 5, names)
        self.assertEqual(names[:4], old[2:], "the two oldest go, the rest stay")
        with open(self.repo.path(names[4])) as fh:
            self.assertEqual(fh.read(), self.OLD)

    def test_no_state_file_means_no_archive(self):
        me = self.main()
        out = self.assertOk(self.clean(pid=me))
        self.assertEqual(self.archives(), [])
        self.assertIn("PREVIOUS: case closed", "\n".join(self.state_lines()))
        self.assertRegex(self.state_lines()[2], r"^PREVIOUS: case closed \d{4}-\d\d-\d\d, archive none$")
        self.assertEqual(len(self.next_lines(out)), 1)

    def test_a_second_clean_never_overwrites_the_first_archive(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me, env={}))
        first = self.archives()
        self.assertOk(self.clean(pid=me))
        names = self.archives()
        self.assertEqual(len(names), 2, names)
        with open(self.repo.path(first[0])) as fh:
            self.assertEqual(fh.read(), self.OLD)
        other = [n for n in names if n != first[0]][0]
        with open(self.repo.path(other)) as fh:
            self.assertTrue(fh.read().startswith("ROLE: main manager"))


class TestTheFreshState(CleanCase):
    def test_exactly_the_five_lines_and_the_carry(self):
        me = self.main()
        self.write_state()
        self.write_todo("alpha | big | build the alpha thing; next: tests | est 30m",
                        "beta-two | small | fix the beta label | est 10m")
        self.assertOk(self.clean("decide: keep the old logo?",
                                 "owner: answer the pricing question", pid=me))
        lines = self.state_lines()
        self.assertEqual(lines[0], 'ROLE: main manager of "project" (lock: pid %d). '
                                   'Same seat, clean session.' % me)
        self.assertRegex(lines[1], r"^DATE: \d{4}-\d\d-\d\d \d\d:\d\d$")
        archive = self.archives()[0]
        self.assertRegex(lines[2], r"^PREVIOUS: case closed \d{4}-\d\d-\d\d, archive %s$"
                         % re.escape(archive))
        self.assertEqual(lines[2].split()[3].rstrip(","), archive[len("agent_state."):][:10],
                         "the closed date is the day of the archive")
        self.assertEqual(lines[3], "TODO open (2): alpha, beta-two")
        self.assertEqual(lines[4:], ["CARRY: decide: keep the old logo?",
                                     "CARRY: owner: answer the pricing question"])

    def test_nothing_of_the_old_state_stays(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        text = "\n".join(self.state_lines())
        self.assertNotIn("OLD STATE", text)
        self.assertNotIn("term_task-9", text)

    def test_no_todo_and_no_carry(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        lines = self.state_lines()
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual(lines[3], "TODO open (0): none")
        self.assertEqual(lines[4], "CARRY: none")

    def test_a_carry_with_a_newline_stays_one_line(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean("first half\nsecond half", pid=me))
        self.assertEqual(self.state_lines()[4:], ["CARRY: first half second half"])

    def test_the_lock_and_the_closed_list_are_untouched(self):
        me = self.main()
        self.write_state()
        before = self.lock_text()
        self.assertOk(self.clean(pid=me))
        self.assertEqual(self.lock_text(), before)
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_main.closed")))

    def test_it_prints_no_start_output(self):
        me = self.main()
        self.write_state()
        out = self.assertOk(self.clean(pid=me))
        for word in ("QUIZ", "RESOURCES", "auto resume", "RULES:"):
            with self.subTest(word=word):
                self.assertNotIn(word, out)


# -- K3: how the session clears itself, per runtime kind -------------------------------------

class TestTheNextLine(CleanCase):
    def one_next(self, out):
        lines = self.next_lines(out)
        self.assertEqual(len(lines), 1, out)
        return lines[0]

    def sends(self):
        return [c for c in self.repo.calls() if c[:2] == ["terminal", "send"]]

    def test_orca_gets_the_exact_line_with_the_handle_of_the_lock(self):
        me = self.main(term="term_main-1")
        self.write_state()
        out = self.assertOk(self.clean(pid=me, kind="orca"))
        line = self.one_next(out)
        self.assertIn(CLEAR_LINE % "term_main-1", line)
        self.assertIn("last action", line)
        self.assertIn("human", out[out.index("NEXT"):], "what to do when it is not cleared")

    def test_the_command_never_types_it_itself(self):
        me = self.main(term="term_main-1")
        self.write_state()
        self.assertOk(self.clean(pid=me, kind="orca"))
        self.assertEqual(self.sends(), [])

    def test_orca_takes_the_handle_of_the_session_when_the_lock_has_none(self):
        me = self.main(term=None)
        self.write_state()
        out = self.assertOk(self.clean(pid=me, kind="orca",
                                       env={"ORCA_TERMINAL_HANDLE": "term_env-4"}))
        self.assertIn(CLEAR_LINE % "term_env-4", self.one_next(out))

    def test_orca_is_found_by_the_runtime_probe(self):
        self.repo.set_conf("runtime", "auto")
        me = self.main(term="term_main-1")
        self.write_state()
        out = self.assertOk(self.clean(pid=me, kind=None))
        self.assertIn(CLEAR_LINE % "term_main-1", self.one_next(out))

    def test_plain_and_cloud_ask_the_human(self):
        for kind in ("plain", "cloud"):
            with self.subTest(kind=kind):
                me = self.main(term="term_main-1")
                self.write_state()
                line = self.one_next(self.assertOk(self.clean(pid=me, kind=kind)))
                self.assertIn("/clear", line)
                self.assertIn("human", line)
                self.assertNotIn("orca terminal send", line)

    def test_no_orca_on_the_machine_asks_the_human(self):
        self.repo.set_conf("runtime", "auto")
        self.repo.no_orca()
        me = self.main(term="term_main-1")
        self.write_state()
        line = self.one_next(self.assertOk(self.clean(pid=me, kind=None)))
        self.assertIn("human", line)
        self.assertNotIn("orca terminal send", line)

    def test_orca_with_no_handle_asks_the_human(self):
        me = self.main(term=None)
        self.write_state()
        line = self.one_next(self.assertOk(self.clean(pid=me, kind="orca")))
        self.assertIn("/clear", line)
        self.assertIn("human", line)
        self.assertNotIn("orca terminal send", line)


class TestAfterTheClear(CleanCase):
    """The start hook on source "clear": the same main manager, the fresh state."""

    def cleared(self, me):
        return self.assertOk(self.start(pid=me, source="clear", sid="sid-after",
                                        env={"ORCA_TERMINAL_HANDLE": "term_main-1"}))

    def test_the_same_pid_holds_the_lock(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean("decide: keep the old logo?", pid=me))
        self.cleared(me)
        words = self.lock_words()
        self.assertEqual(words[0], str(me))
        self.assertEqual(words[3:], ["sid-after", "term_main-1"])
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_main.closed")))

    def test_the_start_text_says_main_manager_and_shows_the_fresh_state(self):
        me = self.main()
        self.write_state()
        self.write_todo("alpha | big | build the alpha thing | est 30m")
        self.assertOk(self.clean("decide: keep the old logo?", pid=me))
        out = self.cleared(me)
        self.assertIn("ROLE: main manager (lock: pid %d)" % me, out)
        self.assertIn("CLEARED.", out)
        self.assertIn("agent_state.txt: 5 lines", out)
        for line in self.state_lines():
            with self.subTest(line=line[:30]):
                self.assertIn("  " + line, out)
        self.assertIn("  CARRY: decide: keep the old logo?", out)
        for never in ("is dead", "human-direct", "Helper", "no longer the main manager",
                      "QUIZ:", "OLD STATE", "(truncated"):
            with self.subTest(never=never):
                self.assertNotIn(never, out)

    def test_no_second_seat_and_no_helper_line(self):
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        self.cleared(me)
        self.assertNotIn("human-direct", self.repo.read("agent_worktree.txt"))

    def test_a_new_session_is_still_the_helper(self):
        """The seat was never given up: nobody has to find the main manager again."""
        me = self.main()
        self.write_state()
        self.assertOk(self.clean(pid=me))
        self.cleared(me)
        out = self.assertOk(self.start(pid=NOBODY, source="startup", sid="sid-new"))
        self.assertIn("ROLE: task manager, human-direct", out)
        self.assertIn("Main manager already running: pid %d" % me, out)
        self.assertEqual(self.lock_words()[0], str(me))


# -- K1, K4, K5: the whole-repo hook text ------------------------------------------------------


class TestTheReleasePathIsThePluginInstalledNow(CleanCase):
    """K4: a session started on 0.14.0 printed a 0.14.0 path while 0.18.0 was installed."""

    def cache(self, *versions, bare=()):
        folder = os.path.join(self.repo.base, "cache", "auto-pipeline", "auto-pipeline")
        os.makedirs(folder)
        for version in versions:
            shutil.copytree(self.repo.plugin, os.path.join(folder, version))
        for name in bare:
            os.makedirs(os.path.join(folder, name))
        return folder

    def release_lines(self, plugin_root):
        self.set_lock("%d 2026-10-01 09:00 sid-me -\n" % os.getpid())
        result = subprocess.run([os.path.join(plugin_root, "bin", "agent-close-case.sh"), "--release-line"],
                                input="", env=self.repo._env({"CLAUDE_PID": str(os.getpid())}),
                                cwd=self.repo.cwd, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return [l for l in result.stdout.splitlines() if "--release" in l]

    def test_an_old_session_prints_the_newest_installed_path(self):
        folder = self.cache("0.14.0", "0.18.0")
        self.assertEqual(self.release_lines(os.path.join(folder, "0.14.0")),
                         ["! %s/0.18.0/bin/agent-start.sh --release" % folder])

    def test_versions_compare_number_by_number(self):
        folder = self.cache("0.9.0", "0.14.0")
        self.assertEqual(self.release_lines(os.path.join(folder, "0.9.0")),
                         ["! %s/0.14.0/bin/agent-start.sh --release" % folder])

    def test_the_newest_prints_itself(self):
        folder = self.cache("0.9.0", "0.14.0", "0.18.0")
        self.assertEqual(self.release_lines(os.path.join(folder, "0.18.0")),
                         ["! %s/0.18.0/bin/agent-start.sh --release" % folder])

    def test_a_folder_without_the_script_or_not_a_version_never_wins(self):
        folder = self.cache("0.14.0", bare=("0.20.0", "zz-backup"))
        self.assertEqual(self.release_lines(os.path.join(folder, "0.14.0")),
                         ["! %s/0.14.0/bin/agent-start.sh --release" % folder])

    def test_a_plugin_outside_a_version_folder_prints_itself(self):
        os.makedirs(os.path.join(self.repo.base, "9.9.9", "bin"))
        with open(os.path.join(self.repo.base, "9.9.9", "bin", "agent-start.sh"), "w") as fh:
            fh.write("#!/bin/sh\n")
        self.assertEqual(self.release_lines(self.repo.plugin),
                         ["! %s/bin/agent-start.sh --release" % self.repo.plugin])


# -- K5: the words the agents read --------------------------------------------------------------


class TestTheScriptHeader(unittest.TestCase):
    def header(self):
        return "\n".join(read("bin", "agent-start.sh").splitlines()[:20])

    def test_the_usage_block_lists_clean(self):
        self.assertIn("--clean", self.header())

    def test_release_is_no_longer_called_the_last_step(self):
        self.assertNotIn("last step", self.header())


class TestTheHookText(unittest.TestCase):
    """The whole-repo rule is the skill now (close-case part B); the hook is silent."""

    def part_b(self):
        return read("skills", "close-case", "SKILL.md").split("## B.", 1)[1]

    def test_it_asks_after_the_final_table(self):
        out = self.part_b()
        for phrase in ("whole repo", "/auto-pipeline:close-case", "agent_worktree.txt",
                       "final table", "yes or no", "language",
                       "nothing changes", "--clean", "/clear", "stay the main manager"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), out.lower())
        self.assertLess(out.index("final table"), out.index("yes or no"))

    def test_release_is_the_other_choice_not_the_last_step(self):
        out = self.part_b()
        self.assertLess(out.index("yes or no"), out.index("--release"))
        self.assertLess(out.index("--clean"), out.index("--release"))
        self.assertIn("never run it yourself", out)


if __name__ == "__main__":
    unittest.main()
