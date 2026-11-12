"""Failing tests for statusline-vertical. Written by the task manager first.

Owner, 2026-11-12 (answers final): the status line shows one task per line; it
refreshes by itself; the bar moves inside a stage too (it sat at 66% for hours
through the full suite); the main manager default is Opus 5.5.

CONTRACT

1. Status line (bin/agent-statusline.sh -> agent_board.py --statusline)
    One line per task with a stage, in the board's order (waiting on the owner,
    running, held or queued; oldest first in a group). Columns, joined by two
    spaces:
        name    fixed 24 display columns: shorter -> spaces after it; longer ->
                its first 23 columns and "…"
        bar     the board's progress cell: "███████░░░  71%"
        stage   the stage word in the agent.conf language, " <i>/<m>" after
                workers when it has one; padded with spaces to the widest
                stage text of the lines shown
                    zh  简报 登记 样稿 写测试 写代码 验证 推送 报告 浏览器验收 合并
                    en  brief register mock tests workers verify push report e2e merge
                (agent.conf language zh -> zh, anything else -> en)
        done by as on the board; "-" -> left out (with its two spaces)
    Trailing spaces cut. A CJK character (east asian width W or F) is 2 display
    columns, everything else 1.
    At most 5 task lines. More tasks -> one more line "+<N> 个" (zh) or
    "+<N> more" (en), N = the tasks not shown.
    No task with a stage -> nothing (as before). Always exit 0.
    The header comment of bin/agent-statusline.sh says one line per task.

2. Auto refresh (agent-settings.sh statusline on|refresh)
    The statusLine object gets "refreshInterval": <n> (Claude Code: seconds,
    re-runs the command every n s). n = statusline_refresh_sec: the main repo's
    agent.conf, a missing or bad value -> the template bin/agent.conf.default
    of this plugin; never a number in the code. No agent.conf -> the template.
        on       {"type": "command", "command": <ours>, "refreshInterval": n}
        refresh  ours -> command pointed at this plugin and refreshInterval = n;
                 nothing to change -> the file byte for byte the same; silent
        off      the whole statusLine goes (as before)
    agent_conf.py: statusline_refresh_sec, whole number 1 to 3600, a hint,
    group "progress" (after progress_eta_min_pct). Template value 60.

3. Progress inside a stage (board column, done by, status line: one function)
    start = (weights of the stages before) / total, end = start + weight / total.
    share = est x weight / total (minutes). No est or weight 0 -> no time part.
    t = minutes from the stage's since to now, minus "waited in stage"; an open
        wait stops the clock at max(since, the wait's since); never below 0.
    time part p_t = start + (end - start) x min(1, t / share), but the percent
        it gives stops one point below the next stage's start: at most
        ceil(100 x end) - 1, never below the stage's start percent.
    workers i/m: p = the larger of start + (end - start) x i/m (may reach end,
        2/2 = 66% as before) and p_t. Other stages: p = p_t.
    Done by uses this same p (progress_eta_min_pct included).
    The stage's since: a new stage name -> now; a new <i>/<m> of the same stage
        keeps since (todo line and STAGE line alike).
    "waited in stage <n>m" on the todo line: todo wait (off, or on while
        waiting) adds the minutes of the closed wait that fall inside the
        current stage (from max(wait since, stage since) to now); a new stage
        name drops the field; a line with no stage never gets it. "waited <m>m"
        stays the sum of every closed wait.
    --self with its stage from its STAGE line: the since of that line.

4. Main manager default: bin/agent.conf.default main_manager=opus-5.5:xhigh;
    PRINCIPLES.md W6 "Main manager (Opus 5.5, xhigh)"; README.md line 11 Opus 5.5.
5. Release: .claude-plugin/plugin.json version 0.32.0 or later.
"""

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
BIN = os.path.join(os.path.dirname(HERE), "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import test_agent_board as tb  # noqa: E402  (the module only)
from scripthelp import ROOT, ScriptCase  # noqa: E402

NOW = tb.NOW   # "2026-11-02 15:00"
ZH = {"brief": "简报", "register": "登记", "mock": "样稿", "tests": "写测试", "workers": "写代码",
      "verify": "验证", "push": "推送", "report": "报告", "e2e": "浏览器验收", "merge": "合并"}


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class Case(tb.BoardCase):
    lang = "zh"

    def stage(self, name, *args, now=NOW, cwd=None):
        return self.af("todo", "stage", name, *args, now=now, cwd=cwd)

    def board_row(self, name, *args, now=NOW, cwd=None):
        return self.row(self.rows(*args, now=now, cwd=cwd), task=name)

    def progress(self, name, **kw):
        return self.board_row(name, **kw)["Progress"]

    def done_by(self, name, **kw):
        return self.board_row(name, **kw)["Done by"]

    def clear_todo(self):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("")

    @staticmethod
    def stage_col(line):
        """The stage column of a one-task status line: the text after "%  ", up to two spaces or the end."""
        m = re.search(r"%  (.+?)(?:  |$)", line)
        assert m, line
        return m.group(1).strip()

    def line(self, folder=None, now=NOW):
        folder = folder or self.repo.dir
        stdin = json.dumps({"session_id": "s1", "cwd": folder,
                            "workspace": {"current_dir": folder, "project_dir": folder}})
        result = self.repo.run("agent-statusline.sh", cwd=self.repo.base, stdin=stdin,
                               env={"AGENT_FAKE_NOW": now}, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.rstrip("\n")


# ---------------------------------------------------------------- 3. the records


class TestStageSince(Case):
    def test_a_new_slice_keeps_the_since(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "workers", now="2026-11-02 14:10")
        self.stage("alpha", "workers", "1/3", now="2026-11-02 14:30")
        self.assertIn(" | stage workers 1/3 since 2026-11-02 14:10", self.todo_line("alpha"))
        self.stage("alpha", "workers", "2/3", now="2026-11-02 14:40")
        line = self.todo_line("alpha")
        self.assertIn(" | stage workers 2/3 since 2026-11-02 14:10", line)
        self.assertEqual(line.count(" | stage "), 1, line)
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.assertIn(" | stage verify since 2026-11-02 14:50", self.todo_line("alpha"))

    def test_the_stage_line_keeps_it_too(self):
        alpha = self.task_worktree("alpha")
        self.stage("alpha", "workers", now="2026-11-02 14:10", cwd=alpha)
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:30", cwd=alpha)
        self.assertIn("STAGE alpha: workers 1/2 | since 2026-11-02 14:10\n", self.state_text(alpha))
        self.stage("alpha", "verify", now="2026-11-02 14:50", cwd=alpha)
        self.assertIn("STAGE alpha: verify | since 2026-11-02 14:50\n", self.state_text(alpha))


class TestWaitedInStage(Case):
    def test_a_closed_wait_inside_the_stage(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.wait("alpha", "on", "question", now="2026-11-02 14:52")
        self.wait("alpha", "off", now="2026-11-02 14:58")
        line = self.todo_line("alpha")
        self.assertIn(" | waited 6m", line)
        self.assertIn(" | waited in stage 6m", line)
        self.assertEqual(line.count("waited in stage"), 1, line)
        self.assertIn(" | stage verify since 2026-11-02 14:50", line)

    def test_two_waits_add_up(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:30")
        self.wait("alpha", "on", "question", now="2026-11-02 14:32")
        self.wait("alpha", "on", "review", now="2026-11-02 14:35")   # closes the first: 3m
        self.wait("alpha", "off", now="2026-11-02 14:40")             # 5m
        line = self.todo_line("alpha")
        self.assertIn(" | waited 8m", line)
        self.assertIn(" | waited in stage 8m", line)
        self.assertEqual(line.count("waited in stage"), 1, line)

    def test_only_the_part_inside_the_stage(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "tests", now="2026-11-02 14:30")
        self.wait("alpha", "on", "hold", now="2026-11-02 14:40")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.wait("alpha", "off", now="2026-11-02 14:56")
        line = self.todo_line("alpha")
        self.assertIn(" | waited 16m", line)
        self.assertIn(" | waited in stage 6m", line)

    def test_a_new_stage_drops_it(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.wait("alpha", "on", "question", now="2026-11-02 14:52")
        self.wait("alpha", "off", now="2026-11-02 14:58")
        self.stage("alpha", "push", now="2026-11-02 15:00")
        line = self.todo_line("alpha")
        self.assertNotIn("waited in stage", line)
        self.assertIn(" | waited 6m", line)

    def test_a_new_slice_keeps_it(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "workers", now="2026-11-02 14:10")
        self.wait("alpha", "on", "queue", now="2026-11-02 14:20")
        self.wait("alpha", "off", now="2026-11-02 14:24")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:40")
        self.assertIn(" | waited in stage 4m", self.todo_line("alpha"))

    def test_no_stage_no_field(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.wait("alpha", "on", "mock", now="2026-11-02 14:10")
        self.wait("alpha", "off", now="2026-11-02 14:30")
        line = self.todo_line("alpha")
        self.assertIn(" | waited 20m", line)
        self.assertNotIn("waited in stage", line)

    def test_done_still_reads_the_line(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.wait("alpha", "on", "question", now="2026-11-02 14:52")
        self.wait("alpha", "off", now="2026-11-02 14:58")
        self.assertIn("work left", self.af("eta", "alpha", "--step", "5").stdout)
        self.af("todo", "done", "alpha", "--work", "50")
        self.assertIn(" | alpha | the login form | data ", self.repo.read("agent_completed.txt"))
        self.assertIsNone(self.todo_line("alpha"))


# ---------------------------------------------------------------- 3. the board


class TestGrowth(Case):
    def test_it_grows_with_time_in_the_stage(self):
        # est 60, verify share 9m; 3 minutes in -> 66 + 15 x 3/9 = 71
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:57")
        self.assertEqual(self.progress("alpha"), "███████░░░  71%")
        self.assertEqual(self.progress("alpha", now="2026-11-02 14:57"), "██████░░░░  66%")

    def test_it_stops_below_the_next_stage(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:00")
        self.assertEqual(self.progress("alpha"), "████████░░  80%")
        self.assertEqual(self.progress("alpha", now="2026-11-02 23:00"), "████████░░  80%")
        self.stage("alpha", "push", now="2026-11-02 15:00")
        self.assertEqual(self.progress("alpha"), "████████░░  81%")

    def test_an_open_wait_freezes_it(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:54")
        self.wait("alpha", "on", "question", now="2026-11-02 14:57")
        self.assertEqual(self.progress("alpha"), "███████░░░  71%")
        self.assertEqual(self.progress("alpha", now="2026-11-02 15:30"), "███████░░░  71%")

    def test_a_wait_opened_before_the_stage_freezes_it_at_the_start(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "tests", now="2026-11-02 14:30")
        self.wait("alpha", "on", "hold", now="2026-11-02 14:40")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.assertEqual(self.progress("alpha"), "██████░░░░  66%")

    def test_a_closed_wait_is_taken_off(self):
        # 10 minutes in verify, 6 of them waited -> 4/9 -> 72.6
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.wait("alpha", "on", "question", now="2026-11-02 14:52")
        self.wait("alpha", "off", now="2026-11-02 14:58")
        self.assertEqual(self.progress("alpha"), "███████░░░  72%")

    def test_workers_the_larger_of_slices_and_time(self):
        # est 60, workers share 24m
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "workers", now="2026-11-02 14:50")
        self.stage("alpha", "workers", "1/2", now="2026-11-02 14:55")
        self.assertEqual(self.progress("alpha"), "████░░░░░░  46%")                         # 10/24 < 1/2
        self.assertEqual(self.progress("alpha", now="2026-11-02 15:08"), "█████░░░░░  56%")  # 18/24
        self.assertEqual(self.progress("alpha", now="2026-11-02 16:00"), "██████░░░░  65%")  # time capped
        self.stage("alpha", "workers", "2/2", now="2026-11-02 16:00")
        self.assertEqual(self.progress("alpha", now="2026-11-02 16:00"), "██████░░░░  66%")  # slices reach the end

    def test_no_estimate_no_time_part(self):
        self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:00")
        self.assertEqual(self.progress("alpha"), "██████░░░░  66%")

    def test_a_weight_of_0_no_time_part(self):
        self.repo.set_conf("stage_verify", "0")
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:00")
        # (1 + 1 + 4 + 20 + 40) / 85 = 77.6
        self.assertEqual(self.progress("alpha"), "███████░░░  77%")

    def test_self_reads_the_since_of_its_stage_line(self):
        # est 120, verify share 18m; 10 minutes in -> 66 + 15 x 10/18 = 74.3
        alpha = self.task_worktree("alpha")
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.state("STAGE alpha: verify | since 2026-11-02 14:50\n", folder=alpha)
        r = self.board_row("alpha", "--self", cwd=alpha)
        self.assertEqual((r["Progress"], r["Done by"]), ("███████░░░  74%", "16:00"))

    def test_self_on_another_machine(self):
        alpha = self.task_worktree("alpha")
        self.state("TODO LINE: alpha | big | the login form | est 60m | opened 2026-11-02 14:00 | by main\n",
                   folder=alpha)
        self.stage("alpha", "verify", now="2026-11-02 14:57", cwd=alpha)
        self.assertEqual(self.board_row("alpha", "--self", cwd=alpha)["Progress"], "███████░░░  71%")


class TestGrowthDoneBy(Case):
    def test_over_the_estimate_uses_the_grown_progress(self):
        # work 60 > est 40; verify share 6m, 3 in -> p = 73.5/100: 60 x 26.5/73.5 = 21.6 -> 22
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:57")
        r = self.board_row("alpha")
        self.assertEqual((r["Progress"], r["Done by"]), ("███████░░░  73%", "15:22"))

    def test_the_minimum_percent_uses_the_grown_progress(self):
        # tests share 8m: 5 in -> 18.5 < 20 -> over; 7 in -> 23.5: 60 x 76.5/23.5 = 195.3 -> 196
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "tests", now="2026-11-02 14:55")
        self.assertEqual(self.done_by("alpha"), "超出 20m")
        self.add("beta", "bank recon match", 40, opened="2026-11-02 14:00")
        self.stage("beta", "tests", now="2026-11-02 14:53")
        self.assertEqual(self.done_by("beta"), "18:16")

    def test_capped(self):
        # verify capped (80%): 60 x 20/80 = 15
        self.add("alpha", "the login form", 40, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:00")
        self.assertEqual(self.done_by("alpha"), "15:15")

    def test_under_the_estimate_still_the_estimate(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:50")
        self.assertEqual(self.done_by("alpha"), "16:00")


# ---------------------------------------------------------------- 1. the status line


class TestVertical(Case):
    def test_the_owner_look(self):
        self.add("pospro-device", "device page", 120, opened="2026-11-02 14:00")
        self.stage("pospro-device", "verify", now=NOW)
        self.add("doc-follows-invoice-edit", "doc follows invoice", 120, opened="2026-11-02 14:00")
        self.stage("doc-follows-invoice-edit", "verify", now="2026-11-02 14:57")
        self.add("release-train-1112", "release train", 120, opened="2026-11-02 14:30")
        self.stage("release-train-1112", "workers", "1/3", now=NOW)
        self.assertEqual(self.line(), "\n".join([
            "pospro-device             ██████░░░░  66%  验证        16:00",
            "doc-follows-invoice-edit  ██████░░░░  68%  验证        16:00",
            "release-train-1112        ███░░░░░░░  39%  写代码 1/3  16:30",
        ]))

    def test_one_task(self):
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.assertEqual(self.line(), "alpha                     ██████░░░░  66%  验证  16:00")

    def test_no_done_by_and_no_trailing_space(self):
        self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
        self.stage("alpha", "brief")
        self.assertEqual(self.line(), "alpha                     ░░░░░░░░░░   0%  简报")

    def test_a_long_name_is_cut(self):
        name = "a-really-long-task-name-for-the-cut"
        self.add(name, "long", 120, opened="2026-11-02 14:00")
        self.stage(name, "verify")
        self.assertEqual(self.line(), "a-really-long-task-name…  ██████░░░░  66%  验证  16:00")

    def test_every_stage_word(self):
        for stage, word in ZH.items():
            with self.subTest(stage=stage):
                self.clear_todo()
                self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
                self.stage("alpha", stage)
                self.assertEqual(self.stage_col(self.line()), word)

    def test_workers_with_and_without_slices(self):
        self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
        self.stage("alpha", "workers")
        self.assertEqual(self.stage_col(self.line()), "写代码")
        self.stage("alpha", "workers", "2/5")
        self.assertEqual(self.stage_col(self.line()), "写代码 2/5")

    def test_six_or_more_tasks_show_five_and_the_rest(self):
        for i in range(1, 8):
            self.add("t%d" % i, "task %d" % i, 120, opened="2026-11-02 14:%02d" % i)
            self.stage("t%d" % i, "tests")
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 6, lines)
        self.assertEqual([l.split()[0] for l in lines[:5]], ["t1", "t2", "t3", "t4", "t5"])
        self.assertEqual(lines[5], "+2 个")

    def test_five_tasks_no_extra_line(self):
        for i in range(1, 6):
            self.add("t%d" % i, "task %d" % i, 120, opened="2026-11-02 14:%02d" % i)
            self.stage("t%d" % i, "tests")
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)

    def test_the_board_order(self):
        # waiting on the owner first, then running, then held; oldest first in a group
        self.add("held", "held one", 120, opened="2026-11-02 14:01")
        self.stage("held", "tests")
        self.wait("held", "on", "hold", now="2026-11-02 14:30")
        self.add("run-late", "running late", 120, opened="2026-11-02 14:20")
        self.stage("run-late", "tests")
        self.add("run-early", "running early", 120, opened="2026-11-02 14:10")
        self.stage("run-early", "tests")
        self.add("mock-wait", "waits on the mock", 120, opened="2026-11-02 14:40")
        self.stage("mock-wait", "mock")
        self.wait("mock-wait", "on", "mock", now="2026-11-02 14:45")
        self.add("no-stage", "not shown", 120, opened="2026-11-02 14:00")
        lines = self.line().split("\n")
        self.assertEqual([l.split()[0] for l in lines], ["mock-wait", "run-early", "run-late", "held"])

    def test_the_line_grows_with_time(self):
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:00")
        self.stage("alpha", "verify", now="2026-11-02 14:57")
        self.assertIn("███████░░░  71%", self.line())
        self.assertIn("████████░░  80%", self.line(now="2026-11-02 15:30"))

    def test_nothing_with_a_stage_prints_nothing(self):
        self.add("alpha", "the login form", 60)
        self.assertEqual(self.line(), "")

    def test_the_header_comment(self):
        text = read("bin", "agent-statusline.sh")
        head = "\n".join(l for l in text.splitlines() if l.startswith("#"))
        self.assertIn("one line per task", head)
        self.assertNotIn("one line with the progress bar", head)
        self.assertNotIn("prints one line or nothing", head)


class TestVerticalEnglish(Case):
    lang = "en"

    def test_words_and_more(self):
        for i in range(1, 7):
            self.add("t%d" % i, "task %d" % i, 120, opened="2026-11-02 14:%02d" % i)
        self.stage("t1", "workers", "1/3")
        for i in range(2, 7):
            self.stage("t%d" % i, "e2e")
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 6, lines)
        self.assertEqual(lines[0], "t1                        ███░░░░░░░  39%  workers 1/3  16:01")
        self.assertEqual(lines[1], "t2                        ████████░░  85%  e2e          16:02")
        self.assertEqual(lines[5], "+1 more")

    def test_every_stage_word(self):
        for stage in ZH:
            with self.subTest(stage=stage):
                self.clear_todo()
                self.add("alpha", "the login form", None, opened="2026-11-02 14:00")
                self.stage("alpha", stage)
                self.assertEqual(self.stage_col(self.line()), stage)


# ---------------------------------------------------------------- 2. auto refresh


OURS_OLD = '"/old/plugin/0.29.0/bin/agent-statusline.sh"'
FOREIGN = {"type": "command", "command": "~/.claude/buddy/statusline.sh"}


class RefreshCase(ScriptCase):
    script = "agent-settings.sh"

    def setUp(self):
        super().setUp()
        self.home = self.repo.fake_home()
        self.settings = os.path.join(self.home, ".claude", "settings.json")
        self.cmd = '"%s/bin/agent-statusline.sh"' % self.repo.plugin

    def ours(self, n=60):
        return {"type": "command", "command": self.cmd, "refreshInterval": n}

    def write(self, data):
        os.makedirs(os.path.dirname(self.settings), exist_ok=True)
        with open(self.settings, "w") as fh:
            fh.write(json.dumps(data, indent=2) + "\n")

    def raw(self):
        with open(self.settings, "rb") as fh:
            return fh.read()

    def load(self):
        with open(self.settings) as fh:
            return json.load(fh)

    def run_settings(self, *args):
        return self.repo.run("agent-settings.sh", "statusline", *args, timeout=30)


class TestRefreshInterval(RefreshCase):
    def test_on_writes_the_template_value(self):
        self.repo.unset_conf("statusline_refresh_sec")
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load(), {"statusLine": self.ours(60)})

    def test_on_takes_agent_conf(self):
        self.repo.set_conf("statusline_refresh_sec", "15")
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load()["statusLine"], self.ours(15))

    def test_a_bad_value_is_the_template_value(self):
        for bad in ("0", "abc", "1.5", "-3"):
            with self.subTest(value=bad):
                self.repo.set_conf("statusline_refresh_sec", bad)
                self.assertOk(self.run_settings("on"))
                self.assertEqual(self.load()["statusLine"]["refreshInterval"], 60)

    def test_the_number_comes_from_the_template_not_the_code(self):
        self.repo.unset_conf("statusline_refresh_sec")
        path = self.repo.plugin_path("bin", "agent.conf.default")
        with open(path) as fh:
            text = fh.read()
        self.assertIn("statusline_refresh_sec=60\n", text)
        with open(path, "w") as fh:
            fh.write(text.replace("statusline_refresh_sec=60\n", "statusline_refresh_sec=45\n"))
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load()["statusLine"]["refreshInterval"], 45)

    def test_no_agent_conf(self):
        os.remove(self.repo.path("agent.conf"))
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load()["statusLine"], self.ours(60))

    def test_on_again_with_nothing_to_change_keeps_the_file(self):
        self.write({"statusLine": self.ours(60), "theme": "dark"})
        before = self.raw()
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.raw(), before)

    def test_on_adds_it_to_an_install_from_before(self):
        # bounce 1 (task manager): ours, same command, no refreshInterval -> on must still add it
        self.write({"statusLine": {"type": "command", "command": self.cmd}, "theme": "dark"})
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load(), {"statusLine": self.ours(60), "theme": "dark"})
        self.repo.set_conf("statusline_refresh_sec", "30")
        self.assertOk(self.run_settings("on"))
        self.assertEqual(self.load()["statusLine"], self.ours(30))

    def test_refresh_adds_it_to_ours(self):
        self.write({"statusLine": {"type": "command", "command": self.cmd}, "theme": "dark"})
        result = self.run_settings("refresh")
        self.assertOk(result)
        self.assertEqual(result.stdout + result.stderr, "")
        self.assertEqual(self.load(), {"statusLine": self.ours(60), "theme": "dark"})

    def test_refresh_points_and_sets(self):
        self.repo.set_conf("statusline_refresh_sec", "30")
        self.write({"statusLine": {"type": "command", "command": OURS_OLD, "refreshInterval": 60}})
        self.assertOk(self.run_settings("refresh"))
        self.assertEqual(self.load(), {"statusLine": self.ours(30)})

    def test_refresh_with_nothing_to_change_keeps_the_file(self):
        self.write({"statusLine": self.ours(60), "theme": "dark"})
        before = self.raw()
        self.assertOk(self.run_settings("refresh"))
        self.assertEqual(self.raw(), before)

    def test_refresh_never_touches_a_foreign_one(self):
        self.write({"statusLine": FOREIGN})
        before = self.raw()
        self.assertOk(self.run_settings("refresh"))
        self.assertEqual(self.raw(), before)

    def test_off_takes_it_all_away(self):
        self.write({"statusLine": self.ours(60), "theme": "dark"})
        self.assertOk(self.run_settings("off"))
        self.assertEqual(self.load(), {"theme": "dark"})


class TestRefreshKey(unittest.TestCase):
    def setUp(self):
        import agent_conf
        self.ac = agent_conf

    def test_bounds(self):
        self.assertEqual(self.ac.NUMBER_BOUNDS.get("statusline_refresh_sec"), (1, 3600))
        for good in ("1", "60", "3600"):
            self.assertIsNone(self.ac.validate_value("statusline_refresh_sec", good), good)
        for bad in ("0", "-1", "abc", "1.5", "", "3601"):
            self.assertTrue(self.ac.validate_value("statusline_refresh_sec", bad), bad)

    def test_hint_group_and_template(self):
        self.assertTrue(self.ac.HINTS.get("statusline_refresh_sec", "").strip())
        self.assertEqual(self.ac.group_of("statusline_refresh_sec"), "progress")
        keys = dict(self.ac.GROUPS)["progress"]
        self.assertEqual(keys[-1], "statusline_refresh_sec")
        self.assertEqual(keys[-2], "progress_eta_min_pct")
        conf = self.ac.load(os.path.join(ROOT, "bin", "agent.conf.default"))
        self.assertEqual(conf.get("statusline_refresh_sec"), "60")
        self.assertEqual(self.ac.validate(conf), {})


# ---------------------------------------------------------------- 4, 5. model default, release


class TestModelAndRelease(unittest.TestCase):
    def test_the_template_main_manager(self):
        import agent_conf
        conf = agent_conf.load(os.path.join(ROOT, "bin", "agent.conf.default"))
        self.assertEqual(conf["main_manager"], "opus-5.5:xhigh")
        self.assertEqual(conf["task_manager"], "opus-5.5:xhigh")
        self.assertEqual(conf["worker"], "sonnet-5:medium")
        self.assertEqual(conf["fast_lane_deputy"], "sonnet-5:medium")
        self.assertEqual(conf["merge_deputy"], "sonnet-5:medium")

    def test_the_rule_text(self):
        text = read("PRINCIPLES.md")
        w6 = text[text.index("W6. Roles"):text.index("W7. ")]
        self.assertIn("- Main manager (Opus 5.5, xhigh) = the main chat.", w6)
        self.assertNotIn("Fable 5.1", w6)

    def test_the_readme(self):
        line = read("README.md").splitlines()[10]
        self.assertTrue(line.startswith("Main manager"), line)
        self.assertIn("Opus 5.5", line)
        self.assertNotIn("Fable", line)

    def test_the_version(self):
        version = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        self.assertGreaterEqual(tuple(int(n) for n in version.split(".")), (0, 32, 0))


if __name__ == "__main__":
    unittest.main()
