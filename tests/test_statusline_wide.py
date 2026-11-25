"""Failing tests for statusline-wide. Written first by the task manager.

Owner, 2026-11-25: "this one can be 3 column also if have enought space, but if like the width is less then reduce
the column automatically will do, same concept for col 2, if the screen too small we display 1 col only".

CONTRACT (bin/agent-statusline.sh -> agent_board.py --statusline)

1. Width. The status line command reads the terminal width, first hit wins:
       $AGENT_STATUSLINE_WIDTH (a whole number; 0 or junk = unknown, no further guess), $COLUMNS, then the window size
       of /dev/tty, then of stdin, stdout and stderr. Claude Code's session JSON has no width field.
   agent_board.terminal_width(environ) -> int or None. statusline_text(stdin_text, width=None): width None or 0 =
   unknown = ONE column, exactly the look from before (tests/test_statusline_vertical.py, tests/test_board_waiting.py,
   tests/test_watch_board.py keep passing; the tests run with AGENT_STATUSLINE_WIDTH=0).
2. Columns. usable = width - 2. A cell is at least 44 display columns, the separator " │ " is 3. 3 columns when
   usable holds three cells (138), else 2 when it holds two (91), else 1. Cells fill down a column first, then the
   next column. A CJK character is 2 columns. A cell longer than its width is cut with "…". The "│" of every row
   stands at the same display column. No line is wider than the width.
3. Every open task has a cell: waiting on the owner, running (with or without a stage), waiting on others,
   queued or held, not started. "+N 排队/暂缓" only when 3 columns of the line budget cannot hold them all
   (N = the tasks not shown; the fold takes one line, so the cells then fill the lines before it).
4. First line = the count line: "看板 <n> 个任务 · <k> 个等你" (en "board <n> tasks · <k> waiting on you", "1 task"; the
   second part is left out for k = 0). Second line, only when a task is unconfirmed: "看板可能不准：未确认 a, b" (en
   "board may be wrong: not confirmed a, b"), the names. The other two warnings keep their text.
5. A Helper is one row "<repo> Helper": a todo with no stage and no wait, that has a live pane LAUNCH record
   (a record of a pane kind, pid alive) under its task name, is not a second row when a Helper row exists.
6. Line budget 5 (STATUS_LINES), the count line and the warning line included.
"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
BIN = os.path.join(os.path.dirname(HERE), "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import test_agent_board as tb  # noqa: E402  (the module only)
import test_board_waiting as bw  # noqa: E402  (the module only)
import test_watch_board as tw  # noqa: E402  (the module only)
from test_watch_board import q, h, ns, run  # noqa: E402

NOW = bw.NOW   # "2026-11-20 12:31"


def dw(text):
    import agent_board
    return agent_board.display_width(text)


def owner(name, since="2026-11-20 12:20", note=""):
    return "%s | big | w | est 30m | opened 2026-11-20 10:00 | by main | waiting mock since %s%s" % (
        name, since, ": " + note if note else "")


def plain(name):
    """Running, no stage."""
    return "%s | big | w | est 30m | opened 2026-11-20 10:00 | by main | started 2026-11-20 10:05" % name


def eight():
    return [owner("city-office-2"), run("settings-configure", 5), run("plugin-scope-sync", 10), plain("dev-docs"),
            q("check-blocks", "settings-configure", "2026-11-20 11:00"),
            q("report-to-main-pc2", "settings-configure", "2026-11-20 11:01"),
            h("mode-match"), ns("fresh-one")]


class WideCase(bw.Case):
    def line(self, width=None, folder=None, now=NOW):
        folder = folder or self.repo.dir
        stdin = json.dumps({"session_id": "s1", "cwd": folder,
                            "workspace": {"current_dir": folder, "project_dir": folder}})
        env = {"AGENT_FAKE_NOW": now}
        if width is not None:
            env["AGENT_STATUSLINE_WIDTH"] = str(width)
        result = self.repo.run("agent-statusline.sh", cwd=self.repo.base, stdin=stdin, env=env, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result.stdout.rstrip("\n")

    def bars(self, lines):
        """Display column of every "│" per line."""
        return [[dw(l[:i]) for i, c in enumerate(l) if c == "│"] for l in lines]

    def names_in(self, text, names):
        return [n for n in names if n in text]


NAMES8 = ["city-office-2", "settings-configure", "plugin-scope-sync", "dev-docs", "check-blocks",
          "report-to-main-pc2", "mode-match", "fresh-one"]


class TestColumns(WideCase):
    def test_200_wide_three_columns(self):
        self.put(*eight())
        lines = self.line(200).split("\n")
        self.assertEqual(lines[0], "看板 8 个任务 · 1 个等你")
        body = lines[1:]
        self.assertEqual(len(body), 3, body)
        self.assertTrue(all(l.count("│") == 2 for l in body[:2]), body)
        self.assertEqual(len(self.names_in("\n".join(body), NAMES8)), 8)
        self.assertNotIn("排队/暂缓", "\n".join(lines))
        self.assertTrue(all(dw(l) <= 200 for l in lines))
        # the owner wait first, down the first column
        self.assertTrue(body[0].startswith("city-office-2"), body[0])
        self.assertIn(body[1].split()[0], ["dev-docs", "settings-configure", "plugin-scope-sync"])
        # aligned
        full = self.bars(body[:2])
        self.assertEqual(full[0], full[1])

    def test_120_wide_two_columns(self):
        self.put(*eight())
        lines = self.line(120).split("\n")
        self.assertEqual(lines[0], "看板 8 个任务 · 1 个等你")
        body = lines[1:]
        self.assertEqual(len(body), 4, body)
        self.assertTrue(all(l.count("│") == 1 for l in body), body)
        self.assertEqual(len(self.names_in("\n".join(body), NAMES8)), 8)
        self.assertEqual(len({tuple(b) for b in self.bars(body)}), 1)
        self.assertTrue(all(dw(l) <= 120 for l in lines))

    def test_70_wide_one_column_with_a_fold(self):
        self.put(*eight())
        lines = self.line(70).split("\n")
        self.assertEqual(lines[0], "看板 8 个任务 · 1 个等你")
        self.assertEqual(len(lines), 5, lines)
        self.assertNotIn("│", "\n".join(lines))
        self.assertTrue(lines[1].startswith("city-office-2"), lines[1])
        self.assertEqual(lines[4], "+5 排队/暂缓")
        self.assertTrue(all(dw(l) <= 70 for l in lines))

    def test_70_wide_a_few_tasks_all_shown(self):
        self.put(*eight()[:4])
        lines = self.line(70).split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertNotIn("排队/暂缓", "\n".join(lines))
        self.assertEqual(len(self.names_in("\n".join(lines), NAMES8[:4])), 4)

    def test_unknown_width_is_todays_one_column(self):
        self.put(*eight())
        for width in (None, 0):
            lines = self.line(width).split("\n")
            self.assertEqual(len(lines), 5, lines)
            self.assertNotIn("│", "\n".join(lines))
            self.assertFalse(lines[0].startswith("看板 "), lines[0])
            self.assertEqual(lines[-1], "+3 排队/暂缓")  # the run without a stage was never a line

    def test_three_columns_start_at_140(self):
        self.put(*eight())
        self.assertTrue(all(l.count("│") == 2 for l in self.line(140).split("\n")[1:3]))
        self.assertTrue(all(l.count("│") == 1 for l in self.line(139).split("\n")[1:]))

    def test_two_columns_start_at_93(self):
        self.put(*eight())
        self.assertTrue(all(l.count("│") == 1 for l in self.line(93).split("\n")[1:]))
        self.assertNotIn("│", self.line(92))

    def test_english_count_line(self):
        self.repo.set_conf("language", "en")
        self.put(*eight())
        self.assertEqual(self.line(200).split("\n")[0], "board 8 tasks · 1 waiting on you")

    def test_one_task_and_none_waiting(self):
        self.put(run("solo", 1))
        self.assertEqual(self.line(200).split("\n")[0], "看板 1 个任务")


class TestChineseCells(WideCase):
    def test_a_long_chinese_cell_is_cut_and_the_bars_stay(self):
        long = "确认这个很长很长很长很长很长很长很长很长很长很长很长很长的样稿说明"
        self.put(owner("alpha-task", note=long), run("beta", 3), q("gamma", "beta"), ns("delta"))
        lines = self.line(120).split("\n")
        body = lines[1:]
        self.assertIn("…", "\n".join(body))
        self.assertEqual(len({tuple(b) for b in self.bars(body)}), 1, body)
        self.assertTrue(all(dw(l) <= 120 for l in lines))

    def test_a_cjk_character_counts_two(self):
        self.put(owner("名字", note="好"), run("beta", 3), q("gamma", "beta"), ns("delta"))
        body = self.line(120).split("\n")[1:]
        self.assertEqual(len({tuple(b) for b in self.bars(body)}), 1, body)


class TestFold(WideCase):
    def many(self, n):
        return [q("t%02d" % i, "x", "2026-11-20 11:%02d" % i) for i in range(n)]

    def test_twelve_cells_fit_in_four_lines(self):
        self.put(*self.many(12))
        lines = self.line(200).split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertNotIn("排队/暂缓", "\n".join(lines))
        self.assertEqual(len(self.names_in("\n".join(lines), ["t%02d" % i for i in range(12)])), 12)

    def test_more_than_the_cells_fold_the_rest(self):
        self.put(*self.many(14))
        lines = self.line(200).split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual(lines[0], "看板 14 个任务")
        self.assertEqual(lines[4], "+5 排队/暂缓")
        self.assertEqual(len(self.names_in("\n".join(lines[1:4]), ["t%02d" % i for i in range(14)])), 9)


class TestOrder(WideCase):
    def test_owner_then_running_then_queued_then_not_started(self):
        self.put(ns("n1"), h("h1"), q("q1", "r1"), plain("r0"), run("r1", 2), owner("o1"))
        body = self.line(70).split("\n")[1:]
        self.assertEqual([l.split()[0] for l in body[:3]], ["o1", "r0", "r1"])
        self.assertEqual(self.line(70).split("\n")[-1], "+3 排队/暂缓")
        wide = self.line(200).split("\n")[1:]
        order = [l.split("│")[0].split()[0] for l in wide]
        self.assertEqual(order, ["o1", "r0"])  # two rows of three columns
        flat = " ".join(" ".join(l.split("│")) for l in wide).split()
        self.assertLess(flat.index("q1"), flat.index("n1"))


class TestHelper(WideCase):
    def pane(self, task):
        self.state("LAUNCH k1: helper-pane | task %s | talk | since 2026-11-20 12:00 | pid %d | by helper"
                   % (task, os.getpid()))

    def helper(self):
        self.repo.set_worktree_lines([(self.repo.dir, "task manager, human-direct", "task: Owner Talk")])

    def test_the_pane_keeper_todo_is_not_a_second_row(self):
        self.put(plain("keeper"), run("real", 3))
        self.helper()
        self.pane("keeper")
        text = self.line(200)
        self.assertNotIn("keeper", text)
        self.assertIn("Helper", text)
        self.assertEqual(text.count("Helper"), 1)
        self.assertEqual(text.split("\n")[0], "看板 2 个任务")

    def test_without_a_pane_record_it_stays(self):
        self.put(plain("keeper"), run("real", 3))
        self.helper()
        text = self.line(200)
        self.assertIn("keeper", text)
        self.assertEqual(text.split("\n")[0], "看板 3 个任务")

    def test_without_a_helper_row_it_stays(self):
        self.put(plain("keeper"), run("real", 3))
        self.pane("keeper")
        self.assertIn("keeper", self.line(200))

    def test_a_todo_with_a_stage_stays(self):
        self.put(run("keeper", 3))
        self.helper()
        self.pane("keeper")
        self.assertIn("keeper", self.line(200))


class TestUnconfirmed(WideCase):
    def test_the_line_names_the_tasks(self):
        self.repo.set_conf("runtime", "orca")
        a1 = self.repo.make_worktree("a1", as_repo=False)
        a2 = self.repo.make_worktree("a2", as_repo=False)
        a3 = self.repo.make_worktree("a3", as_repo=False)
        self.put(run("a1", 1), run("a2", 2), run("a3", 3))
        self.repo.set_worktree_lines([(a1, "a1", "working"), (a2, "a2", "working"), (a3, "a3", "working")])
        tw.write_watch(self.repo, sweep=NOW, tasks={
            "a1": tw.task_entry(a1, watched=False, why="no pane"),
            "a2": tw.task_entry(a2, watched=False, why="no pane"),
            "a3": tw.task_entry(a3, changed="2026-11-20 12:30", confirmed="2026-11-20 12:30")})
        lines = self.line(200).split("\n")
        self.assertEqual(lines[0], "看板 3 个任务")
        self.assertEqual(lines[1], "看板可能不准：未确认 a1, a2")
        self.assertEqual(len(lines), 3, lines)  # the count, the warning, one row of three cells

    def test_english(self):
        self.repo.set_conf("language", "en")
        self.repo.set_conf("runtime", "orca")
        a1 = self.repo.make_worktree("a1", as_repo=False)
        self.put(run("a1", 1))
        self.repo.set_worktree_lines([(a1, "a1", "working")])
        tw.write_watch(self.repo, sweep=NOW, tasks={"a1": tw.task_entry(a1, watched=False, why="no pane")})
        self.assertEqual(self.line(200).split("\n")[1], "board may be wrong: not confirmed a1")

    def test_the_budget_stays_five_with_the_warning(self):
        self.repo.set_conf("runtime", "orca")
        a1 = self.repo.make_worktree("a1", as_repo=False)
        self.put(run("a1", 1), *[q("q%02d" % i, "a1", "2026-11-20 11:%02d" % i) for i in range(12)])
        self.repo.set_worktree_lines([(a1, "a1", "working")])
        tw.write_watch(self.repo, sweep=NOW, tasks={"a1": tw.task_entry(a1, watched=False, why="no pane")})
        lines = self.line(200).split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual(lines[1], "看板可能不准：未确认 a1")
        self.assertEqual(lines[4], "+7 排队/暂缓")  # 13 tasks, 2 cell lines of 3 = 6 shown
        self.assertEqual(lines[2].count("│"), 2)


class TestWidthReading(unittest.TestCase):
    def width(self, env):
        import agent_board
        return agent_board.terminal_width(env)

    def test_the_override_wins(self):
        self.assertEqual(self.width({"AGENT_STATUSLINE_WIDTH": "150", "COLUMNS": "80"}), 150)

    def test_zero_means_unknown_and_stops_the_search(self):
        self.assertIsNone(self.width({"AGENT_STATUSLINE_WIDTH": "0", "COLUMNS": "80"}))

    def test_columns(self):
        self.assertEqual(self.width({"COLUMNS": "132"}), 132)

    def test_junk_columns_fall_through(self):
        # no tty in the test run: nothing else answers, or the real terminal does; either way no crash
        self.assertTrue(self.width({"COLUMNS": "abc"}) is None or self.width({"COLUMNS": "abc"}) > 0)

    def test_the_tty_window_size(self):
        import fcntl
        import pty
        import struct
        import termios
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 117, 0, 0))

        def ctty():
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        code = "import sys; sys.path.insert(0, %r); import agent_board; print(agent_board.terminal_width({}))" % BIN
        out = subprocess.run([sys.executable, "-c", code], stdin=slave, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True, preexec_fn=ctty, text=True, timeout=20)
        os.close(master)
        os.close(slave)
        self.assertEqual(out.stdout.strip(), "117", out.stderr)


class TestHeaders(unittest.TestCase):
    def test_the_script_comment_names_the_width(self):
        with open(os.path.join(os.path.dirname(HERE), "bin", "agent-statusline.sh"), encoding="utf-8") as fh:
            self.assertIn("column", fh.read())


if __name__ == "__main__":
    unittest.main()
