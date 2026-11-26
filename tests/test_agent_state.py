"""Tests of bin/agent_state.py through agent-file.sh: state add, state trim, the day archive.

requirements/state-trim.md. One class per feature. Older task contracts: git log -p of this file.
"""

import fcntl
import glob
import json
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase  # noqa: E402

NOW = "2026-11-20 12:00"
TODAY = "2026-11-20"
OLD = "2026-11-18 09:00"      # 51 h before NOW
YOUNG = "2026-11-20 10:00"    # 2 h before NOW
OPEN = ["state-trim", "one-watcher", "owner-relay"]
CLOSED = ["goal-probe", "test-levels", "plugin"]
HEAD = ["ROLE: test state file", ""]
DAY_FILE = "agent_state.trim-%s.txt" % TODAY


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def read(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def todo_line(name):
    return "%s | big | build %s | est 30m | opened 2026-11-18 08:00 | by main" % (name, name)


def done_line(name):
    return ("2026-11-19 | %s | build %s | data repo=project type=script lane=full mock=no est=30 "
            "work=30 wait=0 clock=60 bounces=0 workers=1 files=- lines=- tests=1 adds=0 guess=- level=-"
            % (name, name))


class TrimCase(ScriptCase):
    script = "agent-file.sh"

    def setUp(self):
        super().setUp()
        self.set_todo(*OPEN)
        self.set_done(*CLOSED)

    # ---- fixture

    def set_todo(self, *names):
        write(self.repo.path("agent_todo.txt"), "".join(todo_line(n) + "\n" for n in names))

    def set_done(self, *names):
        write(self.repo.path("agent_completed.txt"), "".join(done_line(n) + "\n" for n in names))

    @property
    def state_path(self):
        return self.repo.path("agent_state.txt")

    def write_state(self, lines, head=True, end="\n", folder=None):
        rows = (HEAD if head else []) + list(lines)
        path = os.path.join(folder, "agent_state.txt") if folder else self.state_path
        write(path, "\n".join(rows) + end)
        return rows

    def state_lines(self, folder=None):
        text = read(os.path.join(folder, "agent_state.txt") if folder else self.state_path)
        return [] if text is None else text.splitlines()

    def day_path(self, day=TODAY, folder=None):
        return os.path.join(folder or self.repo.dir, "agent_state.trim-%s.txt" % day)

    def day_lines(self, day=TODAY, folder=None):
        text = read(self.day_path(day, folder))
        return [] if text is None else text.splitlines()

    # ---- running

    def af(self, *args, env=None, cwd=None):
        full = {"AGENT_FAKE_NOW": NOW}
        full.update(env or {})
        return self.repo.run("agent-file.sh", *args, env=full, cwd=cwd)

    def trim(self, *args, env=None, cwd=None):
        return self.assertOk(self.af("state", "trim", *args, env=env, cwd=cwd))

    def verdict(self, lines, env=None):
        """Write HEAD + lines, trim, return (kept body lines, moved lines)."""
        if os.path.exists(self.day_path()):
            os.remove(self.day_path())
        self.write_state(lines)
        self.trim(env=env)
        kept = self.state_lines()
        self.assertEqual(kept[:len(HEAD)], HEAD, "the header stays first")
        return kept[len(HEAD):], self.day_lines()

    def assertSplit(self, lines, keep, env=None):
        """keep: the lines of `lines` that must stay; every other one must move."""
        kept, moved = self.verdict(lines, env=env)
        self.assertEqual(kept, [l for l in lines if l in keep], "kept")
        self.assertEqual(moved, [l for l in lines if l not in keep], "moved")

    def open_questions(self):
        """Titles of the open QUESTION: lines of the main repo's state file (show question)."""
        out = self.assertOk(self.af("questions", "--json"))
        rows = json.loads(out)["questions"]
        return sorted(r["title"] for r in rows if r.get("source") == "worktree")


# =============================================================== A1 state add


class TestStateAdd(TrimCase):
    def test_appends_the_line_with_a_stamp_at_the_end(self):
        self.write_state(["first"])
        out = self.assertOk(self.af("state", "add", "DECIDED state-trim: one archive per day"))
        self.assertEqual(self.state_lines()[-1],
                         "DECIDED state-trim: one archive per day | %s" % NOW)
        self.assertEqual(out.strip(), "state add: DECIDED state-trim: one archive per day")

    def test_prints_the_first_60_chars(self):
        text = "x" * 80
        out = self.assertOk(self.af("state", "add", text))
        self.assertEqual(out.strip(), "state add: " + "x" * 60)

    def test_a_question_keeps_its_line_start(self):
        self.write_state([])
        self.assertOk(self.af("state", "add", "QUESTION: keep HEARTBEAT lines of open tasks?"))
        last = self.state_lines()[-1]
        self.assertEqual(last, "QUESTION: keep HEARTBEAT lines of open tasks? | %s" % NOW)
        self.assertTrue(last.startswith("QUESTION:"))

    def test_fields_inside_the_text_are_allowed(self):
        self.assertOk(self.af("state", "add", "LIVE: city-tier | pc2 | term_15ce"))
        self.assertEqual(self.state_lines()[-1], "LIVE: city-tier | pc2 | term_15ce | %s" % NOW)

    def test_refusals_write_nothing(self):
        self.write_state(["first"])
        before = read(self.state_path)
        for args in (("",), ("   ",), ("two\nlines",), ("two", "words")):
            with self.subTest(args=args):
                r = self.af("state", "add", *args)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
                self.assertEqual(read(self.state_path), before)

    def test_no_text_at_all_is_refused(self):
        r = self.af("state", "add")
        self.assertNotEqual(r.returncode, 0)
        self.assertIsNone(read(self.state_path))

    def test_a_missing_file_is_made(self):
        self.assertOk(self.af("state", "add", "hello"))
        self.assertEqual(read(self.state_path), "hello | %s\n" % NOW)

    def test_a_missing_last_newline_is_added_first(self):
        write(self.state_path, "ROLE: x\nlast line")
        self.assertOk(self.af("state", "add", "next"))
        self.assertEqual(read(self.state_path), "ROLE: x\nlast line\nnext | %s\n" % NOW)

    def test_in_a_worktree_it_writes_the_own_file(self):
        wt = self.repo.detach_scripts_to_worktree()
        self.assertOk(self.af("state", "add", "from the worktree"))
        self.assertEqual(read(os.path.join(wt, "agent_state.txt")),
                         "from the worktree | %s\n" % NOW)
        self.assertIsNone(read(self.state_path))

    def test_usage_lists_state_add_and_trim(self):
        r = self.af()
        self.assertIn("agent-file.sh state add", r.stdout + r.stderr)
        self.assertIn("agent-file.sh state trim", r.stdout + r.stderr)

    def test_an_unknown_state_verb_is_refused(self):
        r = self.af("state", "shrink")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


class TestGuessedTime(TrimCase):
    """approval-design G (requirements/check-blocks.md section 53 G): a guessed clock time in the text gets one
    warning line; the line is still stored (never a refusal)."""

    def add(self, text):
        r = self.af("state", "add", text)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return [l for l in (r.stdout + r.stderr).splitlines() if "the stamp is the time" in l]

    def test_a_digit_replaced_by_x_warns_once_and_is_stored(self):
        for text, guess in (("DECIDED at 18:0x: merge first", "18:0x"), ("owner said 1x:45 go", "1x:45"),
                            ("seen 18:xx today", "18:xx"), ("two guesses 09:3x and ~11:45", "09:3x")):
            with self.subTest(text=text):
                warns = self.add(text)
                self.assertEqual(warns, ['state add: warning: "%s" looks guessed; the stamp is the time' % guess])
                self.assertEqual(self.state_lines()[-1], "%s | %s" % (text, NOW))

    def test_a_tilde_clock_warns(self):
        for text, guess in (("finished ~11:45", "~11:45"), ("finished ~ 11:45", "~ 11:45")):
            with self.subTest(text=text):
                self.assertEqual(self.add(text), ['state add: warning: "%s" looks guessed; the stamp is the time' % guess])

    def test_a_real_time_or_other_x_does_not_warn(self):
        for text in ("the run ended at 18:05", "mask 0x1f is fine", "HEARTBEAT t: step 3 of 7, work 24m, 2x faster",
                     "est 30m x 2 = 60m"):
            with self.subTest(text=text):
                self.assertEqual(self.add(text), [])


class TestAnswerStamp(TrimCase):
    def test_questions_answer_stamps_its_answer_line(self):
        self.write_state(["QUESTION: rules ok? | %s" % YOUNG])
        rows = json.loads(self.assertOk(self.af("questions", "--json")))["questions"]
        ids = [r["id"] for r in rows if "rules ok?" in r.get("title", "")]
        self.assertEqual(len(ids), 1, rows)
        self.assertOk(self.af("questions", "answer", ids[0], "rules yes"))
        lines = self.state_lines()
        i = lines.index("QUESTION: rules ok? | %s" % YOUNG)
        self.assertEqual(lines[i + 1], "ANSWER: rules yes | %s" % NOW)


# =============================================================== A2.1 stamps


class TestStamps(TrimCase):
    def test_a_trailing_stamp(self):
        self.assertSplit(["note a | %s" % OLD, "note b | %s" % YOUNG], keep=["note b | %s" % YOUNG])

    def test_a_leading_stamp_date_time_date_only_and_bullets(self):
        lines = ["2026-11-18 09:00 note b", "- 2026-11-18 note c", "* 2026-11-17 note e",
                 "  2026-11-20 10:00 note d"]
        self.assertSplit(lines, keep=["  2026-11-20 10:00 note d"])

    def test_a_since_field(self):
        self.assertSplit(["something | since %s" % OLD, "other | since %s" % YOUNG],
                         keep=["other | since %s" % YOUNG])

    def test_a_header_stamp(self):
        lines = ["=== NOTES %s ===" % OLD, "=== NOTES %s ===" % YOUNG]
        self.assertSplit(lines, keep=["=== NOTES %s ===" % YOUNG])

    def test_a_date_in_the_text_is_not_a_stamp(self):
        # no stamp and nothing stamped below: its time is now
        self.assertSplit(["tested 2026-11-17 on pc2"], keep=["tested 2026-11-17 on pc2"])

    def test_the_trailing_stamp_wins_over_a_leading_date(self):
        line = "2026-11-10 09:00 fixed later | %s" % YOUNG
        self.assertSplit([line], keep=[line])

    def test_an_unstamped_line_takes_the_next_stamped_line_below(self):
        self.assertSplit(["legacy one", "legacy two", "note | %s" % OLD], keep=[])
        self.assertSplit(["legacy one", "note | %s" % YOUNG],
                         keep=["legacy one", "note | %s" % YOUNG])

    def test_an_unstamped_line_at_the_end_is_now(self):
        self.assertSplit(["note | %s" % OLD, "legacy at the end"], keep=["legacy at the end"])


# =============================================================== A2.2 keep rules


class TestHeader(TrimCase):
    def test_the_header_runs_to_the_first_blank_line(self):
        rows = ["ROLE: main manager", "DATE: 2026-11-01 09:00", "", "old | %s" % OLD]
        write(self.state_path, "\n".join(rows) + "\n")
        self.trim()
        self.assertEqual(self.state_lines(), rows[:3])
        self.assertEqual(self.day_lines(), rows[3:])

    def test_the_header_stops_before_the_first_section_line(self):
        rows = ["head one | %s" % OLD, "=== REPORT ===", "DONE PASS goal-probe", "end | %s" % OLD]
        write(self.state_path, "\n".join(rows) + "\n")
        self.trim()
        self.assertEqual(self.state_lines(), rows[:1])
        self.assertEqual(self.day_lines(), rows[1:])

    def test_the_header_is_at_most_40_lines(self):
        rows = ["brief line %d | %s" % (i, OLD) for i in range(1, 46)]
        write(self.state_path, "\n".join(rows) + "\n")
        self.trim()
        self.assertEqual(self.state_lines(), rows[:40])
        self.assertEqual(self.day_lines(), rows[40:])

    def test_a_brief_is_kept_whole(self):
        brief = ["[Opus 5.5 xhigh] Brief from the main manager: you are the task manager for \"goal-probe\".",
                 "TODO LINE: goal-probe | big | Test /goal | est 30m",
                 "STEPS: 0 brief 1 register", ""]
        rows = brief + ["DECIDED goal-probe: no second probe | %s" % OLD]
        write(self.state_path, "\n".join(rows) + "\n")
        self.trim()
        self.assertEqual(self.state_lines(), brief)


class TestMachineLines(TrimCase):
    KEEP = [
        "RULE: pc2 full suite only under /tmp/pc2-heavy.lock | 2026-11-12 09:00",
        "RULE pc2 max 3 task managers | %s" % OLD,
        "2026-11-12 09:00 RULE: a leading stamp is fine",
        "CARRY: decide the logo | %s" % OLD,
        "PARKED: keep LIVE lines? | goal-probe | since 2026-11-17 10:00",
        "QUESTIONS PAGE: https://claude.ai/artifact/x | page.html | map.json | since 2026-11-17 10:00",
        "STAGE goal-probe: report | since 2026-11-17 10:00",
        "WORKER 1: goal-probe slice one | since 2026-11-17 10:00",
        "TODO LINE: goal-probe | big | Test /goal | est 30m",
        "GOAL: task manager goal-probe: done when DONE PASS or DONE FAIL is written",
        "2026-11-10 OWNER TODO: sign the Apple form",
        "check this OWNER TODO: renew the domain | %s" % OLD,
    ]
    MOVE = [
        "RULES: read PRINCIPLES.md | %s" % OLD,
        "CARRYING on with goal-probe | %s" % OLD,
        'he said "OWNER TODO: x" | %s' % OLD,
        "STAGES are fine | %s" % OLD,
    ]

    def test_machine_lines_stay_whatever_their_age(self):
        self.assertSplit(self.KEEP + self.MOVE, keep=self.KEEP)


class TestLiveLines(TrimCase):
    """Review change 1: LIVE is kept only by naming an open task (K6) or by age (K7)."""

    def test_live_lines(self):
        open_one = "LIVE: one-watcher | laptop | term_a1b2 | 2026-11-18 09:00"
        closed_old = "LIVE: test-levels | pc2 | term_9f3e | 2026-11-19 08:00"
        closed_young = "LIVE: test-levels | pc2 | term_9f3e | %s" % YOUNG
        self.assertSplit([open_one, closed_old, closed_young], keep=[open_one, closed_young])


class TestQuestions(TrimCase):
    def test_an_open_question_stays(self):
        q = "QUESTION: keep HEARTBEAT lines of open tasks? | 2026-11-18 10:00"
        self.assertSplit([q, "note | %s" % OLD], keep=[q])

    def test_an_old_answered_pair_moves_together(self):
        lines = ["QUESTION: level 4 for goal-probe? | 2026-11-17 10:00", "ANSWER: no | 2026-11-17 10:20",
                 "note | %s" % OLD]
        self.assertSplit(lines, keep=[])

    def test_a_pair_with_lines_between_and_an_indented_answer(self):
        lines = ["QUESTION: a? | %s" % OLD, "work line | %s" % OLD, "  ANSWER: yes | %s" % OLD]
        self.assertSplit(lines, keep=[])

    def test_a_young_answer_keeps_its_question(self):
        lines = ["QUESTION: b? | 2026-11-17 10:00", "ANSWER: yes | %s" % YOUNG]
        self.assertSplit(lines, keep=lines)

    def test_a_question_that_names_an_open_task_keeps_its_answer(self):
        lines = ["QUESTION: one-watcher scope? | %s" % OLD, "ANSWER: all | %s" % OLD]
        self.assertSplit(lines, keep=lines)

    def test_an_answer_that_names_an_open_task_keeps_its_question(self):
        lines = ["QUESTION: which task first? | %s" % OLD, "ANSWER: state-trim | %s" % OLD]
        self.assertSplit(lines, keep=lines)

    def test_k3b_a_section_line_after_an_open_question_stays(self):
        q = "QUESTION: open one? | %s" % OLD
        lines = [q, "=== REPORT ===", "DONE PASS goal-probe", "TIME: est 30m | %s" % OLD,
                 "ANSWER: late | %s" % YOUNG]
        self.write_state(lines)
        before = self.open_questions()
        self.assertEqual(len(before), 1, before)
        kept, moved = self.verdict(lines)
        self.assertEqual(kept, [q, "=== REPORT ===", "ANSWER: late | %s" % YOUNG])
        self.assertEqual(moved, ["DONE PASS goal-probe", "TIME: est 30m | %s" % OLD])
        self.assertEqual(self.open_questions(), before)

    def test_k3b_a_question_after_an_open_question_stays_with_its_answer(self):
        lines = ["QUESTION: open two? | %s" % OLD, "QUESTION: answered? | %s" % OLD,
                 "ANSWER: yes | %s" % OLD, "ANSWER: late | %s" % YOUNG]
        self.write_state(lines)
        before = self.open_questions()
        kept, moved = self.verdict(lines)
        self.assertEqual(kept, lines)
        self.assertEqual(moved, [])
        self.assertEqual(self.open_questions(), before)


class TestHousekeepBlock(TrimCase):
    def test_the_block_stays_whole(self):
        block = ["=== HOUSEKEEP 2026-11-18 08:00 ===",
                 "  removed: worktree line /x (folder gone, no live pane)",
                 "  flag: todo y: stale, no worktree line and no open wait for 999m"]
        after = ["note | %s" % OLD, "  indented but after the block | %s" % OLD]
        self.assertSplit(block + after, keep=block)

    def test_the_clean_line_stays(self):
        line = "HOUSEKEEP 2026-11-18 08:00: clean"
        self.assertSplit([line, "note | %s" % OLD], keep=[line])


class TestReportBlocks(TrimCase):
    def test_a_block_that_names_an_open_task_stays_whole_to_the_next_section_line(self):
        # the block runs to the line before the next "=== " line, stamped lines included (K5)
        block = ["=== REPORT ===", "DONE PASS one-watcher", "Result: 12 tests", "TIME: est 30m",
                 "a later old line still in the block | %s" % OLD]
        self.assertSplit(block + ["=== NOTES ===", "after | %s" % OLD], keep=block)

    def test_a_block_to_the_end_of_the_file(self):
        block = ["=== REPORT ===", "DONE PASS one-watcher", "old line | %s" % OLD]
        self.assertSplit(block, keep=block)

    def test_a_later_line_naming_an_open_task_is_enough(self):
        block = ["=== REPORT ===", "DONE FAIL goal-probe: blocked", "next: hand it to state-trim"]
        self.assertSplit(block + ["=== NOTES ===", "after | %s" % OLD], keep=block)

    def test_a_block_of_a_closed_task_moves(self):
        lines = ["=== REPORT ===", "DONE PASS goal-probe", "Result: 3 tests", "after | %s" % OLD]
        self.assertSplit(lines, keep=[])

    def test_the_block_ends_at_the_next_section_line(self):
        block = ["=== REPORT ===", "DONE PASS one-watcher"]
        rest = ["=== NOTES ===", "plain note", "after | %s" % OLD]
        self.assertSplit(block + rest, keep=block)


class TestOpenTaskNames(TrimCase):
    def test_whole_word_names(self):
        keep = ["DECIDED one-watcher: --all reads agent_worktree.txt | 2026-11-16 14:00",
                "see one-watcher, then go | %s" % OLD,
                "(one-watcher) | %s" % OLD,
                "owner-relay: done soon | %s" % OLD]
        move = ["one-watcher-2 is a new idea | %s" % OLD,
                "xone-watcher | %s" % OLD,
                "one_watcher | %s" % OLD,
                "DECIDED test-levels: R8 levels 0-4 | 2026-11-19 09:00",
                "merged stale-plugin-guard, worktree removed | %s" % OLD]
        self.assertSplit(keep + move, keep=keep)

    def test_open_means_a_line_of_agent_todo_txt(self):
        self.set_todo("state-trim")
        line = "DECIDED one-watcher: --all | %s" % OLD
        self.assertSplit([line], keep=[])


class TestAge(TrimCase):
    def test_exactly_24_hours_is_old(self):
        self.assertSplit(["edge | 2026-11-19 12:00", "edge2 | 2026-11-19 12:01"],
                         keep=["edge2 | 2026-11-19 12:01"])

    def test_a_stamp_in_the_future_is_young(self):
        self.assertSplit(["future | 2026-11-21 09:00"], keep=["future | 2026-11-21 09:00"])


class TestOwnerLines(TrimCase):
    """Review change 2: a standing owner decision stays forever."""

    def test_owner_lines(self):
        keep = ["OWNER 2026-11-13: ideas -> script finds suspects, owner decides each",
                "2026-11-13 OWNER decided: no more city work this month",
                "OWNER 2026-11-16: one-watcher first"]
        move = ["OWNER 2026-11-17: goal-probe answers are enough, no second probe",
                "OWNER 2026-11-14: plugin updates stay manual on pc2",
                "OWNERS meeting notes | %s" % OLD]
        self.assertSplit(keep + move, keep=keep)


class TestHeartbeats(TrimCase):
    """Owner Q1 A: an open task keeps only its last old heartbeat; young ones stay."""

    def test_an_open_task_keeps_its_last_old_heartbeat_and_the_young_ones(self):
        lines = ["HEARTBEAT one-watcher: step 2 of 7, work 20m | 2026-11-18 14:00",
                 "HEARTBEAT one-watcher: step 3 of 7, work 35m | 2026-11-18 15:45",
                 "HEARTBEAT one-watcher: step 4 of 7, work 50m | 2026-11-18 16:00",
                 "HEARTBEAT one-watcher: step 5 of 7, work 70m | %s" % YOUNG]
        self.assertSplit(lines, keep=lines[2:])

    def test_each_open_task_keeps_its_own_last_one(self):
        lines = ["HEARTBEAT one-watcher: step 2 | 2026-11-18 14:00",
                 "2026-11-18 14:05 HEARTBEAT owner-relay: step 2",
                 "HEARTBEAT one-watcher: step 3 | 2026-11-18 15:00",
                 "2026-11-18 15:05 HEARTBEAT owner-relay: step 3",
                 "note | %s" % OLD]
        self.assertSplit(lines, keep=lines[2:4])

    def test_a_closed_task_keeps_none(self):
        lines = ["HEARTBEAT goal-probe: step 3 of 7, work 20m | 2026-11-17 15:00",
                 "HEARTBEAT goal-probe: step 4 of 7, work 30m | 2026-11-17 15:15"]
        self.assertSplit(lines, keep=[])

    def test_naming_another_open_task_does_not_keep_a_heartbeat(self):
        lines = ["HEARTBEAT goal-probe: waiting on state-trim | %s" % OLD]
        self.assertSplit(lines, keep=[])

    def test_a_heartbeat_with_no_task_word_follows_the_normal_rules(self):
        lines = ["HEARTBEAT: still here | %s" % OLD, "HEARTBEAT: still here | %s" % YOUNG]
        self.assertSplit(lines, keep=lines[1:])


# =============================================================== A3 mechanics


class TestTheDayArchive(TrimCase):
    def test_the_output_line_and_the_day_file(self):
        self.write_state(["old one | %s" % OLD, "young | %s" % YOUNG, "old two | %s" % OLD])
        out = self.trim()
        self.assertEqual(out.strip(),
                         "state trim: kept 3, moved 2 of 5 -> %s (checked)" % DAY_FILE)
        self.assertEqual(self.day_lines(), ["old one | %s" % OLD, "old two | %s" % OLD])

    def test_lines_move_byte_for_byte(self):
        odd = ["trailing spaces   | %s" % OLD, "需要 主人 决定 | %s" % OLD, "tab\there | %s" % OLD]
        original = self.write_state(odd + ["young | %s" % YOUNG])
        self.trim()
        self.assertEqual(self.day_lines(), odd)
        self.assertEqual(sorted(self.state_lines() + self.day_lines()), sorted(original))

    def test_a_second_trim_the_same_day_appends(self):
        self.write_state(["first old | %s" % OLD])
        self.trim()
        with open(self.state_path, "a") as fh:
            fh.write("second old | %s\n" % OLD)
        self.trim()
        self.assertEqual(self.day_lines(), ["first old | %s" % OLD, "second old | %s" % OLD])

    def test_another_day_gets_its_own_file(self):
        self.write_state(["old | %s" % OLD])
        self.trim(env={"AGENT_FAKE_NOW": "2026-11-21 12:00"})
        self.assertEqual(self.day_lines("2026-11-21"), ["old | %s" % OLD])
        self.assertIsNone(read(self.day_path()))

    def test_nothing_to_move_touches_nothing(self):
        self.write_state(["young | %s" % YOUNG])
        before = read(self.state_path)
        out = self.trim()
        self.assertEqual(out.strip(), "state trim: nothing to move (3 lines)")
        self.assertEqual(read(self.state_path), before)
        self.assertIsNone(read(self.day_path()))

    def test_no_state_file(self):
        out = self.trim()
        self.assertEqual(out.strip(), "state trim: nothing to move (0 lines)")
        self.assertIsNone(read(self.state_path))

    def test_a_missing_last_newline(self):
        write(self.state_path, "ROLE: x\n\nold | %s" % OLD)
        self.trim()
        self.assertEqual(read(self.state_path), "ROLE: x\n\n")
        self.assertEqual(read(self.day_path()), "old | %s\n" % OLD)

    def test_written_by_tmp_and_mv_nothing_left_over(self):
        self.write_state(["old | %s" % OLD])
        first = os.stat(self.state_path).st_ino
        self.trim()
        self.assertNotEqual(os.stat(self.state_path).st_ino, first)
        left = sorted(n for n in os.listdir(self.repo.dir) if n.startswith("agent_state"))
        self.assertEqual(left, ["agent_state.trim-%s.txt" % TODAY, "agent_state.txt"])

    def test_the_day_file_is_git_ignored(self):
        self.write_state(["old | %s" % OLD])
        self.trim()
        r = subprocess.run(["git", "-C", self.repo.dir, "check-ignore", "-q", DAY_FILE])
        self.assertEqual(r.returncode, 0, "%s is not ignored" % DAY_FILE)
        with open(self.repo.path(".git", "info", "exclude")) as fh:
            rows = [l.strip() for l in fh]
        self.assertEqual(rows.count("agent_state.*.txt"), 1, rows)
        self.trim()
        with open(self.repo.path(".git", "info", "exclude")) as fh:
            self.assertEqual([l.strip() for l in fh].count("agent_state.*.txt"), 1)

    def test_kept_plus_moved_is_the_original(self):
        lines = (["LIVE: test-levels | pc2 | t | %s" % OLD, "QUESTION: open? | %s" % OLD]
                 + ["HEARTBEAT one-watcher: n %d | %s" % (i, OLD) for i in range(5)]
                 + ["legacy", "DECIDED one-watcher: x | %s" % OLD, "young | %s" % YOUNG])
        original = self.write_state(lines)
        self.trim()
        self.assertEqual(sorted(self.state_lines() + self.day_lines()), sorted(original))


class TestDryRun(TrimCase):
    def test_counts_rules_and_first_lines_and_writes_nothing(self):
        long_line = "y" * 150 + " | %s" % OLD
        lines = ["DECIDED one-watcher: keep | %s" % OLD, "old a | %s" % OLD, long_line]
        self.write_state(lines)
        before = read(self.state_path)
        mtime = os.stat(self.state_path).st_mtime_ns
        out = self.trim("--dry-run")
        rows = out.splitlines()
        self.assertEqual(rows[0], "state trim (dry run): keep 3, move 2 of 5")
        self.assertEqual(rows[1], "by rule: K1 2, K2 0, K3 0, K3b 0, K4 0, K5 0, K6 1, K7 0, K8 0, H 0, P 0")
        self.assertEqual(rows[2], "first kept:")
        self.assertEqual(rows[3:6], ["  ROLE: test state file", "  ", "  DECIDED one-watcher: keep | %s" % OLD])
        self.assertEqual(rows[6], "first moved:")
        self.assertEqual(rows[7:9], ["  old a | %s" % OLD, "  " + long_line[:100]])
        self.assertEqual(read(self.state_path), before)
        self.assertEqual(os.stat(self.state_path).st_mtime_ns, mtime)
        self.assertIsNone(read(self.day_path()))

    def test_at_most_five_lines_each(self):
        self.write_state(["old %d | %s" % (i, OLD) for i in range(8)])
        rows = self.trim("--dry-run").splitlines()
        i = rows.index("first moved:")
        self.assertEqual(len(rows[i + 1:]), 5, rows)

    def test_a_line_counts_under_the_first_rule_only(self):
        # young AND names an open task: K6 comes first
        self.write_state(["DECIDED one-watcher: x | %s" % YOUNG, "RULE: a | %s" % YOUNG])
        rows = self.trim("--dry-run").splitlines()
        self.assertEqual(rows[1], "by rule: K1 2, K2 1, K3 0, K3b 0, K4 0, K5 0, K6 1, K7 0, K8 0, H 0, P 0")

    def test_an_unknown_option_is_refused(self):
        self.write_state(["old | %s" % OLD])
        r = self.af("state", "trim", "--bogus")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIsNone(read(self.day_path()))


class TestRaceAndReadBack(TrimCase):
    def test_a_line_appended_meanwhile_starts_it_over_and_is_kept(self):
        self.write_state(["old | %s" % OLD])
        self.trim(env={"AGENT_FAKE_TRIM_RACE": "1"})
        self.assertEqual(self.state_lines(), HEAD + ["RACE 1"])
        self.assertEqual(self.day_lines(), ["old | %s" % OLD])

    def test_more_than_three_restarts_is_refused_and_nothing_is_lost(self):
        original = self.write_state(["old | %s" % OLD])
        r = self.af("state", "trim", env={"AGENT_FAKE_TRIM_RACE": "4"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("state trim: refused", r.stderr)
        self.assertEqual(self.state_lines(), original + ["RACE 1", "RACE 2", "RACE 3", "RACE 4"])
        self.assertIsNone(read(self.day_path()))

    def test_a_refusal_gives_an_existing_day_file_its_old_bytes(self):
        write(self.day_path(), "earlier trim | %s\n" % OLD)
        self.write_state(["old | %s" % OLD])
        r = self.af("state", "trim", env={"AGENT_FAKE_TRIM_RACE": "4"})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(read(self.day_path()), "earlier trim | %s\n" % OLD)

    def test_a_failed_read_back_restores_both_files(self):
        write(self.day_path(), "earlier trim | %s\n" % OLD)
        self.write_state(["old | %s" % OLD])
        before = read(self.state_path)
        r = self.af("state", "trim", env={"AGENT_FAKE_TRIM_BAD_READBACK": "1"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("state trim: refused", r.stderr)
        self.assertEqual(read(self.state_path), before)
        self.assertEqual(read(self.day_path()), "earlier trim | %s\n" % OLD)

    def test_a_failed_read_back_with_no_day_file_before(self):
        self.write_state(["old | %s" % OLD])
        before = read(self.state_path)
        r = self.af("state", "trim", env={"AGENT_FAKE_TRIM_BAD_READBACK": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(read(self.state_path), before)
        self.assertIsNone(read(self.day_path()))


class TestOwnFileOnly(TrimCase):
    def test_a_worktree_trims_its_own_file_with_the_main_repo_todo(self):
        main_rows = self.write_state(["main old | %s" % OLD])
        wt = self.repo.detach_scripts_to_worktree()
        self.write_state(["wt old | %s" % OLD, "DECIDED one-watcher: x | %s" % OLD], folder=wt)
        self.trim()
        self.assertEqual(self.state_lines(wt), HEAD + ["DECIDED one-watcher: x | %s" % OLD])
        self.assertEqual(self.day_lines(folder=wt), ["wt old | %s" % OLD])
        self.assertEqual(self.state_lines(), main_rows)
        self.assertIsNone(read(self.day_path()))


# =============================================================== reviewer findings (verify, 2026-11-20)


class TestOneTrimAtATime(TrimCase):
    """Finding 1: two trims at once lost the moved lines. A lock holds the whole trim and every state add.
    AGENT_FAKE_TRIM_HOLD=<sec> (tests only): the trim sleeps that long right after it read the day file."""

    def lock_held(self, path):
        """True while another process holds the trim's flock (a try that gets it lets go at once)."""
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        finally:
            os.close(fd)

    def start_held_trim(self, sec="2"):
        env = {"AGENT_FAKE_NOW": NOW, "AGENT_FAKE_TRIM_HOLD": sec}
        gitdir = subprocess.run(["git", "-C", self.repo.dir, "rev-parse", "--absolute-git-dir"],
                                capture_output=True, text=True, check=True).stdout.strip()
        lock = os.path.join(gitdir, "agent_state.lock")
        t0 = time.time()
        proc = self.repo.popen("agent-file.sh", "state", "trim", env=env)
        # batch-fix: wait until the first trim holds the lock (was a fixed 0.5 s: on a loaded machine the first
        # trim had not reached its lock yet and the second one took it first)
        end = time.time() + 30
        while not self.lock_held(lock):
            self.assertIsNone(proc.poll(), "the held trim ended before it took the lock")
            self.assertLess(time.time(), end, "the held trim never took the lock")
            time.sleep(0.05)
        return proc, t0

    def test_two_trims_at_once_lose_nothing(self):
        original = self.write_state(["old note one | 2026-11-10 10:00", "old note two | 2026-11-10 11:00"])
        proc, t0 = self.start_held_trim()
        t1 = time.time()
        second = self.af("state", "trim")
        waited = time.time() - t1
        out_a, err_a = proc.communicate(timeout=60)
        self.assertGreaterEqual(time.time() - t0, 1.5, "the hold did not hold")
        self.assertEqual(proc.returncode, 0, out_a + err_a)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertGreaterEqual(waited, 1.0, "the second trim did not wait for the lock")
        self.assertEqual(self.day_lines(), ["old note one | 2026-11-10 10:00", "old note two | 2026-11-10 11:00"])
        self.assertEqual(sorted(self.state_lines() + self.day_lines()), sorted(original))

    def test_state_add_waits_for_a_running_trim_and_its_line_stays(self):
        self.write_state(["old | %s" % OLD])
        proc, t0 = self.start_held_trim()
        t1 = time.time()
        self.assertOk(self.af("state", "add", "added meanwhile"))
        waited = time.time() - t1
        proc.communicate(timeout=60)
        self.assertGreaterEqual(waited, 1.0, "state add did not wait for the lock")
        self.assertEqual(self.state_lines(), HEAD + ["added meanwhile | %s" % NOW])
        self.assertEqual(self.day_lines(), ["old | %s" % OLD])


class TestLateAppends(TrimCase):
    """Finding 2: a line appended by another writer right around the swap must survive.
    Tests only: AGENT_FAKE_TRIM_LATE_NEW=<line> appends it to agent_state.txt right after the trim wrote it;
    AGENT_FAKE_TRIM_LATE_OLD=<line> appends it, right after the swap, through a handle opened on the old file."""

    def test_a_line_appended_right_after_the_write_survives(self):
        self.write_state(["old | %s" % OLD, "young | %s" % YOUNG])
        out = self.trim(env={"AGENT_FAKE_TRIM_LATE_NEW": "QUESTION: new one"})
        self.assertIn("(checked)", out)
        self.assertEqual(self.state_lines(), HEAD + ["young | %s" % YOUNG, "QUESTION: new one"])
        self.assertEqual(self.day_lines(), ["old | %s" % OLD])

    def test_a_line_written_to_the_old_file_during_the_swap_survives(self):
        self.write_state(["old | %s" % OLD, "young | %s" % YOUNG])
        self.trim(env={"AGENT_FAKE_TRIM_LATE_OLD": "late line"})
        self.assertEqual(self.state_lines(), HEAD + ["young | %s" % YOUNG, "late line"])
        self.assertEqual(self.day_lines(), ["old | %s" % OLD])


class TestHousekeepBlockEnd(TrimCase):
    """Finding 4: the line that ends a HOUSEKEEP block stays (K4), so an indented line never joins the block."""

    def test_the_line_after_the_block_stays(self):
        lines = ["older | %s" % OLD, "=== HOUSEKEEP 2026-11-18 08:00 ===", "  stale: 1 worktree",
                 "old note | %s" % OLD, "  - detail of the next step", "young note | %s" % YOUNG]
        self.assertSplit(lines, keep=lines[1:])

    def test_the_dry_run_counts_it_under_k4(self):
        lines = ["older | %s" % OLD, "=== HOUSEKEEP 2026-11-18 08:00 ===", "  stale: 1 worktree",
                 "old note | %s" % OLD, "  - detail of the next step", "young note | %s" % YOUNG]
        self.write_state(lines)
        rows = self.trim("--dry-run").splitlines()
        self.assertEqual(rows[0], "state trim (dry run): keep 7, move 1 of 8")
        self.assertEqual(rows[1], "by rule: K1 2, K2 0, K3 0, K3b 0, K4 3, K5 0, K6 0, K7 2, K8 0, H 0, P 0")


class TestLeadingDatesAreNoBound(TrimCase):
    """Finding 5: a leading date can be a content date, so it dates only its own line, never the lines above."""

    def test_a_note_above_an_owner_todo_with_an_old_date_stays(self):
        lines = ["waiting for CI on the cert fix", "2026-11-01 OWNER TODO: renew the cert", "young | %s" % YOUNG]
        self.assertSplit(lines, keep=lines)

    def test_an_unstamped_line_above_only_leading_dates_is_now(self):
        lines = ["legacy at the top", "2026-11-01 09:00 note b"]
        self.assertSplit(lines, keep=["legacy at the top"])


class TestIndentedTodoLine(TrimCase):
    """Finding 6: the board and show question read an indented TODO LINE:, so trim keeps it too."""

    def test_an_indented_todo_line_stays(self):
        line = "  TODO LINE: goal-probe | big | Test /goal | est 30m | %s" % OLD
        self.assertSplit([line, "old | %s" % OLD], keep=[line])


# =============================================================== callers (T10, T11)


class TestTodoDone(TrimCase):
    def setUp(self):
        super().setUp()
        self.set_todo(*(OPEN + ["goal-x"]))

    def done(self, env=None):
        return self.af("todo", "done", "goal-x", "--type", "script", "--lane", "full", env=env)

    def test_todo_done_trims_after_the_line_moved(self):
        self.write_state(["DECIDED goal-x: ship it | %s" % OLD, "DECIDED one-watcher: x | %s" % OLD])
        out = self.assertOk(self.done())
        self.assertIn("state trim: kept 3, moved 1 of 4 -> %s (checked)" % DAY_FILE, out)
        self.assertEqual(self.day_lines(), ["DECIDED goal-x: ship it | %s" % OLD])
        self.assertNotIn("goal-x |", read(self.repo.path("agent_todo.txt")))

    def test_nothing_to_move_prints_nothing(self):
        self.write_state(["young | %s" % YOUNG])
        out = self.assertOk(self.done())
        self.assertNotIn("state trim", out)

    def test_a_refused_trim_never_fails_todo_done(self):
        self.write_state(["DECIDED goal-x: ship it | %s" % OLD])
        r = self.done(env={"AGENT_FAKE_TRIM_RACE": "9"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("state trim: refused", r.stderr)
        self.assertIn("goal-x", read(self.repo.path("agent_completed.txt")))

# =============================================================== config keys (A7)


class TestConfigKeys(unittest.TestCase):
    """settings-configure: the state numbers are fixed constants now, never set anywhere."""

    DEFAULTS = {"state_keep_hours": 24, "state_warn_lines": 300, "state_header_lines": 40,
                "state_trim_auto": "on", "compact_clear_at": 2, "compact_clear_check_sec": 30}

    def test_the_constants(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        import agent_conf
        for key, value in self.DEFAULTS.items():
            with self.subTest(key=key):
                self.assertEqual(agent_conf.CONSTANTS[key], value)


# =============================================================== housekeep (T10)

from test_agent_housekeep import HousekeepCase, NOW as HK_NOW  # noqa: E402

HK_DAY = "agent_state.trim-%s.txt" % HK_NOW[:10]


class TestHousekeepTrims(HousekeepCase):
    def test_apply_trims_first_and_notes_it(self):
        write(self.repo.path("agent_state.txt"), "ROLE: main\n\nold note | 2026-11-10 09:00\n")
        self.apply()
        self.assertTrue(os.path.exists(self.repo.path(HK_DAY)), "no day file after housekeep --apply")
        with open(self.repo.path(HK_DAY)) as fh:
            self.assertEqual(fh.read(), "old note | 2026-11-10 09:00\n")
        self.assertIn("note: state trim moved 1 of 3 lines -> %s" % HK_DAY, self.body())
        self.assertNotIn("old note", self.state())
        self.assertTrue(self.state().startswith("ROLE: main\n\n"))

    def test_an_old_block_is_kept_then_replaced(self):
        write(self.repo.path("agent_state.txt"),
              "ROLE: main\n\n=== HOUSEKEEP 2026-11-10 08:00 ===\n  note: old\nold | 2026-11-10 09:00\n")
        self.apply()
        self.assertEqual(self.state().count("HOUSEKEEP"), 1)
        self.assertNotIn("2026-11-10 08:00", self.state())

    def test_list_mode_trims_nothing(self):
        write(self.repo.path("agent_state.txt"), "ROLE: main\n\nold note | 2026-11-10 09:00\n")
        self.listing()
        self.assertFalse(os.path.exists(self.repo.path(HK_DAY)))
        self.assertIn("old note", self.state())

# =============================================================== --clean (T9, A8)


if __name__ == "__main__":
    unittest.main()
