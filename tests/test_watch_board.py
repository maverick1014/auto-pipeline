"""Failing tests for one-watcher part 5 and the rule text (requirements/one-watcher.md E, F, G; owner rules
yes 2026-11-24; SCOPE CHANGE 2026-11-24: orphans of this repo only). Written by the task manager first.

CONTRACT (short; the table is the full rule)

    status file   <git common dir of the main repo>/agent_watch.json, written by agent-watch.sh --all:
                  {"pid", "started", "sweep", "interval_min", "tasks": {name: {"path", "env", "pane", "shell",
                  "watched", "why", "signals", "confirmed", "changed", "stall"}}, "orphans": [{"path", "title",
                  "handle"}]}; times "YYYY-MM-DD HH:MM". Live = kill -0 pid and sweep at most
                  2 x interval_min + 2 minutes before now.
    targets       A1: agent_worktree.txt lines working|final, plus open todo lines with "on <machine> <path>"
                  and no worktree line.
    F1/F2         agent-start.sh (main manager, orca) and agent-resume.sh print one line:
                    WATCH: running (pid <p>), <n> tasks, last sweep <HH:MM>
                    WATCH: not running, <n> tasks to watch (<names>). Start it now with Bash run_in_background,
                           timeout 7200000: <plugin>/bin/agent-watch.sh --all
                  no targets, plain or cloud, a spawned role: no line.
    F3/F4         board status cell of a target row: " · 未确认 <n>m" / " · not confirmed <n>m" when no live
                  watch, or the status file says not watched, or (running row, no open wait) the file has
                  not changed for watch_quiet_min (agent.conf, default 15). n = since changed, else
                  confirmed, else the todo line's started, else opened.
                  Scope add 1 (task manager default, 2026-11-24, in the report): agent.conf or AGENT_RUNTIME
                  runtime plain or cloud -> no warning (no watch runs there, as F2).
    F5            orphans of a live status file -> a note line under the table.
    F6            status line: first line "看板可能不准：<k> 个未确认" | "…：看守未运行" | "…：有窗格无任务行"
                  (en "board may be wrong: <k> not confirmed" | "… watch not running" | "… a pane has no task
                  line"); inside the 5-line limit.
    F7            the board and the status line never call orca for this.
"""

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_agent_board as tb  # noqa: E402  (the module only)
import test_agent_statusline as ts  # noqa: E402  (the module only)
import test_board_waiting as bw  # noqa: E402  (the module only)
from scripthelp import ROOT, ScriptCase  # noqa: E402
from watchhelp import dead_pid, now_text  # noqa: E402

NOW = tb.NOW   # "2026-11-02 15:00"
ZH_WARN = "看板可能不准："
EN_WARN = "board may be wrong: "


def status_file(repo):
    return repo.path(".git", "agent_watch.json")


def write_watch(repo, pid=None, sweep=NOW, interval=5, tasks=None, orphans=()):
    data = {"pid": os.getpid() if pid is None else pid, "started": "2026-11-02 13:00", "sweep": sweep,
            "interval_min": interval, "tasks": tasks or {}, "orphans": list(orphans)}
    with open(status_file(repo), "w") as fh:
        json.dump(data, fh)


def task_entry(path, watched=True, why="", changed=None, confirmed=None, pane="term_x"):
    return {"path": path, "env": None, "pane": pane, "shell": None, "watched": watched, "why": why,
            "signals": 0, "confirmed": confirmed, "changed": changed, "stall": None}


# ---------------------------------------------------------------- F3, F4, F5, F7: the board


class WatchBoardCase(tb.BoardCase):
    def setUp(self):
        super().setUp()
        self.alpha = self.repo.make_worktree("alpha", as_repo=False)
        self.add("alpha", "the login form", 60, opened="2026-11-02 14:30")
        self.worktree_lines((self.alpha, "alpha", "working"))

    def watch(self, **kw):
        tasks = kw.pop("tasks", None)
        if tasks is None:
            tasks = {"alpha": task_entry(self.alpha, **{k: kw.pop(k) for k in list(kw)
                                                       if k in ("watched", "why", "changed", "confirmed")})}
        write_watch(self.repo, tasks=tasks, **kw)

    def status_of(self, task="alpha", **kw):
        return self.row(self.rows(**kw), task=task)["Status"]

    def warn(self, n):
        return " · 未确认 %dm" % n if self.lang == "zh" else " · not confirmed %dm" % n


class TestBoardRow(WatchBoardCase):
    def test_f3a_no_status_file_warns_from_the_started_time(self):
        self.assertEqual(self.status_of(), self.st("running") + self.warn(30))

    def test_f3_a_live_watched_task_with_a_recent_change_has_no_warning(self):
        self.watch(changed="2026-11-02 14:50", confirmed="2026-11-02 14:59")
        self.assertEqual(self.status_of(), self.st("running"))

    def test_f3c_a_quiet_file_for_15_minutes_warns_from_changed(self):
        self.watch(changed="2026-11-02 14:40", confirmed="2026-11-02 14:59")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(20))

    def test_f3c_exactly_15_minutes_warns(self):
        self.watch(changed="2026-11-02 14:45", confirmed="2026-11-02 14:59")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(15))

    def test_f3c_watch_quiet_min_from_agent_conf(self):
        self.repo.set_conf("watch_quiet_min", "30")
        self.watch(changed="2026-11-02 14:40", confirmed="2026-11-02 14:59")
        self.assertEqual(self.status_of(), self.st("running"))

    def test_f3b_not_watched_warns(self):
        self.watch(watched=False, why="no task manager pane")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(30))

    def test_f3a_a_dead_pid_warns_from_changed(self):
        self.watch(pid=dead_pid(), changed="2026-11-02 14:52", confirmed="2026-11-02 14:58")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(8))

    def test_f4_no_changed_falls_back_to_confirmed(self):
        self.watch(pid=dead_pid(), changed=None, confirmed="2026-11-02 14:48")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(12))

    def test_f4_no_started_falls_back_to_opened(self):
        beta = self.repo.make_worktree("beta", as_repo=False)
        self.add("beta", "bank recon", 60, opened="2026-11-02 14:20", started=False)
        self.worktree_lines((self.alpha, "alpha", "working"), (beta, "beta", "working"))
        self.assertEqual(self.status_of("beta"), self.st("not_started") + self.warn(40))

    def test_live_means_a_sweep_at_most_2_intervals_plus_2_minutes_old(self):
        self.watch(sweep="2026-11-02 14:48", changed="2026-11-02 14:55")
        self.assertEqual(self.status_of(), self.st("running"))
        self.watch(sweep="2026-11-02 14:47", changed="2026-11-02 14:55")
        self.assertEqual(self.status_of(), self.st("running") + self.warn(5))

    def test_f3c_a_waiting_row_is_not_warned_for_a_quiet_file(self):
        self.wait("alpha", "on", "question", now="2026-11-02 14:35")
        self.watch(changed="2026-11-02 14:35", confirmed="2026-11-02 14:59")
        self.assertNotIn("未确认", self.status_of())

    def test_f3a_a_waiting_row_is_warned_when_no_watch_runs(self):
        self.wait("alpha", "on", "question", now="2026-11-02 14:35")
        self.assertTrue(self.status_of().endswith(self.warn(30)), self.status_of())

    def test_a_row_that_is_not_a_target_is_never_warned(self):
        self.add("beta", "bank recon", 60, opened="2026-11-02 14:00")
        self.assertEqual(self.status_of("beta"), self.st("running"))
        self.worktree_lines((self.alpha, "alpha", "done"))
        self.assertEqual(self.status_of("alpha"), self.st("running"))

    def test_a_todo_line_with_an_on_field_is_a_target(self):
        self.add("gamma", "stock page", 60, opened="2026-11-02 14:50")
        self.af("todo", "where", "gamma", "pc2", "/x/gamma")
        self.assertEqual(self.status_of("gamma"), self.st("running") + self.warn(10))

    def test_scope_add_1_plain_or_cloud_runtime_has_no_warning(self):
        for value in ("plain", "cloud"):
            with self.subTest(runtime=value):
                self.repo.set_conf("runtime", value)
                self.assertEqual(self.status_of(), self.st("running"))

    def test_f5_orphans_of_a_live_watch_are_one_note_line(self):
        self.watch(changed="2026-11-02 14:58", orphans=[{"path": "/x/ghost", "title": "◑ ghost Task Manager",
                                                         "handle": "term_g"}])
        out = self.board()
        self.assertIn("看板可能不准：/x/ghost 有活动窗格但没有任务行", out.splitlines())

    def test_f5_orphans_of_a_dead_watch_are_not_shown(self):
        self.watch(pid=dead_pid(), changed="2026-11-02 14:58",
                   orphans=[{"path": "/x/ghost", "title": "◑ ghost", "handle": "term_g"}])
        self.assertNotIn("/x/ghost", self.board())

    def test_f7_the_board_never_calls_orca_for_the_watch(self):
        self.watch(changed="2026-11-02 14:40", orphans=[{"path": "/x/ghost", "title": "g", "handle": "term_g"}])
        self.repo.clear_calls()
        self.board()
        self.assertEqual(self.repo.calls(), [])


class TestBoardRowEnglish(WatchBoardCase):
    lang = "en"

    def test_f3_english_words(self):
        self.assertEqual(self.status_of(), "running · not confirmed 30m")

    def test_f5_english_note(self):
        self.watch(changed="2026-11-02 14:58", orphans=[{"path": "/x/ghost", "title": "g", "handle": "term_g"}])
        self.assertIn("board may be wrong: /x/ghost has a live pane but no task line", self.board().splitlines())


# ---------------------------------------------------------------- F6, F7: the status line


class StatusLineCase(ts.LineCase):
    def setUp(self):
        super().setUp()
        self.alpha = self.repo.make_worktree("alpha", as_repo=False)
        self.add("alpha", "the login form", 120, opened="2026-11-02 14:00")
        self.stage("alpha", "verify")
        self.worktree_lines((self.alpha, "alpha", "working"))

    def first(self):
        return self.line(self.repo.dir).split("\n")[0]


class TestStatusLine(StatusLineCase):
    def test_f6_no_live_watch_says_watch_not_running(self):
        self.assertEqual(self.first(), ZH_WARN + "看守未运行")

    def test_f6_unconfirmed_tasks_are_counted(self):
        beta = self.repo.make_worktree("beta", as_repo=False)
        self.add("beta", "bank recon", 40, opened="2026-11-02 14:00")
        self.stage("beta", "workers", "1/2")
        self.worktree_lines((self.alpha, "alpha", "working"), (beta, "beta", "working"))
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:30"),
                                      "beta": task_entry(beta, watched=False, why="no task manager pane")})
        self.assertEqual(self.first(), ZH_WARN + "2 个未确认")

    def test_f6_orphans_only(self):
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:58")},
                    orphans=[{"path": "/x/ghost", "title": "g", "handle": "term_g"}])
        self.assertEqual(self.first(), ZH_WARN + "有窗格无任务行")

    def test_f6_all_confirmed_has_no_warning_line(self):
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:58")})
        self.assertFalse(self.first().startswith(ZH_WARN), self.first())
        self.assertTrue(self.first().startswith("alpha "), self.first())

    def test_f6_the_warning_counts_in_the_5_line_limit(self):
        rows = [(self.alpha, "alpha", "working")]
        for name in ("b1", "b2", "b3", "b4", "b5"):
            path = self.repo.make_worktree(name, as_repo=False)
            self.add(name, "task " + name, 60, opened="2026-11-02 14:00")
            self.stage(name, "tests")
            rows.append((path, name, "working"))
        self.worktree_lines(*rows)
        lines = self.line(self.repo.dir).split("\n")
        self.assertLessEqual(len(lines), 5, lines)
        self.assertEqual(lines[0], ZH_WARN + "看守未运行")

    def test_scope_add_1_plain_runtime_has_no_warning_line(self):
        self.repo.set_conf("runtime", "plain")
        self.assertFalse(self.first().startswith(ZH_WARN), self.first())

    def test_f7_the_status_line_never_calls_orca(self):
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:30")})
        self.repo.clear_calls()
        self.line(self.repo.dir)
        self.assertEqual(self.repo.calls(), [])


class TestStatusLineEnglish(StatusLineCase):
    lang = "en"

    def test_f6_english_words(self):
        self.assertEqual(self.first(), EN_WARN + "watch not running")
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:30")})
        self.assertEqual(self.first(), EN_WARN + "1 not confirmed")
        write_watch(self.repo, tasks={"alpha": task_entry(self.alpha, changed="2026-11-02 14:58")},
                    orphans=[{"path": "/x/ghost", "title": "g", "handle": "term_g"}])
        self.assertEqual(self.first(), EN_WARN + "a pane has no task line")


# ---------------------------------------------------------------- K: status line rows (owner SCOPE ADD 2026-11-24)


def q(name, after=None, since="2026-11-20 11:00"):
    return "%s | big | w | est 30m | opened %s | by main | waiting queue since %s%s" % (
        name, since, since, " | after " + after if after else "")


def h(name, since="2026-11-20 12:01", note="later"):
    return "%s | big | w | est 30m | opened 2026-11-20 10:00 | by main | waiting hold since %s: %s" % (name, since, note)


def ns(name, opened="2026-11-20 11:35"):
    return "%s | big | w | est 30m | opened %s | by main" % (name, opened)


def run(name, minute):
    return ("%s | big | w | est 120m | opened 2026-11-20 12:%02d | by main | started 2026-11-20 12:%02d | "
            "stage tests since 2026-11-20 12:%02d" % (name, minute, minute, minute))


name_col = bw.name_col


class TestStatusLineRows(bw.Case):
    """bw.Case: NOW 2026-11-20 12:31, runtime plain (no watch warning) unless a test says orca."""

    def test_k1_k2_a_queued_task_gets_its_own_row(self):
        self.put(q("plugin-slim", "one-watcher"))
        self.assertEqual(self.line(), name_col("plugin-slim") + "排队 · 在 one-watcher 之后")

    def test_k2_a_queue_with_no_task(self):
        self.put(q("plugin-slim"))
        self.assertEqual(self.line(), name_col("plugin-slim") + "排队")

    def test_k2_a_hold_drops_the_what(self):
        self.put(h("held", note="after the release"))
        self.assertEqual(self.line(), name_col("held") + "暂缓 · 已等 30分钟")

    def test_k2_a_hold_with_no_real_time(self):
        self.put(h("held", since="2026-13-40 99:99"))
        self.assertEqual(self.line(), name_col("held") + "暂缓")

    def test_k2_not_started(self):
        self.put(ns("fresh"))
        self.assertEqual(self.line(), name_col("fresh") + "未开始")

    def test_k3_board_order(self):
        self.put(h("held"), ns("fresh"), q("queued", "x"), run("busy", 10))
        self.assertEqual([l.split()[0] for l in self.line().split("\n")], ["busy", "queued", "fresh", "held"])

    def test_k4_rows_that_do_not_fit_fold(self):
        self.put(run("r1", 1), run("r2", 2), *[q("q%d" % i, "r1", since="2026-11-20 11:%02d" % i) for i in range(1, 6)])
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual([l.split()[0] for l in lines[:4]], ["r1", "r2", "q1", "q2"])
        self.assertEqual(lines[4], "+3 排队/暂缓")

    def test_k4_five_rows_fit_no_fold_line(self):
        self.put(run("r1", 1), q("q1", "r1"), q("q2", "r1", since="2026-11-20 11:01"), ns("n1"), h("h1"))
        lines = self.line().split("\n")
        self.assertEqual([l.split()[0] for l in lines], ["r1", "q1", "q2", "n1", "h1"])

    def test_k4_the_watch_warning_line_counts(self):
        self.repo.set_conf("runtime", "orca")
        self.repo.set_worktree_lines([("/nowhere/r1", "r1", "working")])
        self.put(run("r1", 1), q("q1", "r1"), q("q2", "r1", since="2026-11-20 11:01"), ns("n1"), h("h1"))
        lines = self.line().split("\n")
        self.assertEqual(lines[0], "看板可能不准：看守未运行")
        self.assertEqual([l.split()[0] for l in lines[1:4]], ["r1", "q1", "q2"])
        self.assertEqual(lines[4], "+2 排队/暂缓")
        self.put(run("r1", 1), q("q1", "r1"), ns("n1"), h("h1"))
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual([l.split()[0] for l in lines[1:]], ["r1", "q1", "n1", "h1"])

    def test_k5_a_running_row_with_no_stage_is_not_counted(self):
        self.put("r | big | w | est 30m | opened 2026-11-20 10:00 | by main | started 2026-11-20 10:00", q("q1", "r"))
        self.assertEqual(self.line(), name_col("q1") + "排队 · 在 r 之后")

    def test_k6_a_worktree_shows_its_own_queued_row(self):
        alpha = self.task_worktree("alpha")
        self.put(q("alpha", "state-trim"), q("other", "alpha"))
        self.assertEqual(self.line(alpha), name_col("alpha") + "排队 · 在 state-trim 之后")


class TestStatusLineRowsEnglish(bw.Case):
    lang = "en"

    def test_k2_english_words(self):
        self.put(q("plugin-slim", "one-watcher"), h("held"), ns("fresh"))
        self.assertEqual(self.line(), "\n".join([name_col("plugin-slim") + "queue · after one-watcher",
                                                 name_col("fresh") + "not started",
                                                 name_col("held") + "hold · waited 30m"]))


# ---------------------------------------------------------------- F1, F2: start and resume


class StartResumeCase(ScriptCase):
    script = "agent-start.sh"

    def setUp(self):
        super().setUp()
        self.repo.set_conf("auto_resume", "no")

    def start(self, **env):
        run_env = {"AGENT_RUNTIME": "orca", "CLAUDE_PID": str(os.getpid())}
        run_env.update(env)
        return self.assertOk(self.repo.run("agent-start.sh", env=run_env))

    def resume(self, **env):
        run_env = {"AGENT_RUNTIME": "orca"}
        run_env.update(env)
        return self.assertOk(self.repo.run("agent-resume.sh", env=run_env))

    def watch_lines(self, out):
        return [l for l in self.lines(out) if l.startswith("WATCH: ")]

    def not_running(self, n, names):
        return ("WATCH: not running, %d tasks to watch (%s). Start it now with Bash run_in_background, "
                "timeout 7200000: %s/bin/agent-watch.sh --all" % (n, names, self.repo.plugin))

    def targets(self):
        self.repo.set_worktree_lines([("/nowhere/alpha", "alpha", "working"), ("/nowhere/beta", "beta", "final"),
                                      ("/nowhere/gamma", "gamma", "done")])


class TestStartLine(StartResumeCase):
    def test_f2_no_watch_prints_the_command(self):
        self.targets()
        self.assertEqual(self.watch_lines(self.start()), [self.not_running(2, "alpha, beta")])

    def test_f2_a_todo_on_line_is_a_target_too(self):
        self.targets()
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add", "far", "big", "far task", "60"))
        self.assertOk(self.repo.run("agent-file.sh", "todo", "where", "far", "pc2", "/x/far"))
        self.assertEqual(self.watch_lines(self.start()), [self.not_running(3, "alpha, beta, far")])

    def test_f1_a_live_watch_is_named(self):
        self.targets()
        sweep = now_text(1)
        write_watch(self.repo, sweep=sweep, tasks={"alpha": {}, "beta": {}})
        self.assertEqual(self.watch_lines(self.start()),
                         ["WATCH: running (pid %d), 2 tasks, last sweep %s" % (os.getpid(), sweep[11:16])])

    def test_f2_a_dead_watch_is_not_running(self):
        self.targets()
        write_watch(self.repo, pid=dead_pid(), sweep=now_text(1), tasks={"alpha": {}, "beta": {}})
        self.assertEqual(self.watch_lines(self.start()), [self.not_running(2, "alpha, beta")])

    def test_f2_no_targets_no_line(self):
        self.repo.set_worktree_lines([("/nowhere/gamma", "gamma", "done")])
        self.assertEqual(self.watch_lines(self.start()), [])

    def test_f2_plain_or_cloud_no_line(self):
        self.targets()
        for kind in ("plain", "cloud"):
            with self.subTest(kind=kind):
                self.assertEqual(self.watch_lines(self.start(AGENT_RUNTIME=kind)), [])

    def test_a_spawned_task_manager_gets_no_line(self):
        self.targets()
        self.assertEqual(self.watch_lines(self.start(AGENT_ROLE="task-manager")), [])

    def test_with_auto_resume_still_one_line(self):
        self.repo.set_conf("auto_resume", "yes")
        self.targets()
        self.assertEqual(len(self.watch_lines(self.start())), 1)


class TestResumeLine(StartResumeCase):
    script = "agent-resume.sh"

    def test_f2_no_watch_prints_the_command(self):
        self.targets()
        self.assertEqual(self.watch_lines(self.resume()), [self.not_running(2, "alpha, beta")])

    def test_f1_a_live_watch_is_named(self):
        self.targets()
        sweep = now_text(1)
        write_watch(self.repo, sweep=sweep, tasks={"alpha": {}, "beta": {}})
        self.assertEqual(self.watch_lines(self.resume()),
                         ["WATCH: running (pid %d), 2 tasks, last sweep %s" % (os.getpid(), sweep[11:16])])

    def test_f2_plain_no_line(self):
        self.targets()
        self.assertEqual(self.watch_lines(self.resume(AGENT_RUNTIME="plain")), [])

    def test_f2_no_targets_no_line(self):
        self.assertEqual(self.watch_lines(self.resume()), [])


# ---------------------------------------------------------------- G. agent.conf key


class TestQuietKey(unittest.TestCase):
    def test_g_the_template_has_watch_quiet_min_15(self):
        with open(os.path.join(ROOT, "bin", "agent.conf.default")) as fh:
            self.assertIn("watch_quiet_min=15", fh.read().splitlines())

    def test_g_the_range_is_1_to_240_with_a_hint(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import agent_conf
        self.assertEqual(agent_conf.NUMBER_BOUNDS["watch_quiet_min"], (1, 240))
        self.assertIn("watch_quiet_min", agent_conf.HINTS)


class TestQuietKeySettings(ScriptCase):
    script = "agent-settings.sh"

    def test_g_settings_accepts_1_to_240_only(self):
        for bad in ("0", "241", "x"):
            with self.subTest(value=bad):
                self.assertNotEqual(self.repo.run("agent-settings.sh", "watch_quiet_min", bad).returncode, 0)
        self.assertOk(self.repo.run("agent-settings.sh", "watch_quiet_min", "30"))
        self.assertIn("watch_quiet_min=30", (self.repo.read("agent.conf") or "").splitlines())


# ---------------------------------------------------------------- E, G: the rule text


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def section(text, start, end):
    lines = text.splitlines()
    begin = next(i for i, line in enumerate(lines) if line.startswith(start))
    stop = next(i for i in range(begin + 1, len(lines)) if lines[i].startswith(end))
    return "\n".join(lines[begin:stop])


class TestRuleText(unittest.TestCase):
    def w15(self):
        return section(read("PRINCIPLES.md"), "W15. Watch", "W16.").splitlines()

    def line_with(self, lines, *words):
        hits = [l for l in lines if all(w in l for w in words)]
        self.assertTrue(hits, "no line with %r in:\n%s" % (words, "\n".join(lines)))
        return hits[0]

    def test_g_w15_one_all_watch_for_every_task_manager(self):
        self.line_with(self.w15(), "agent-watch.sh --all", "agent_state.txt", "another machine", "background",
                       "=== REPORT ===")

    def test_e1_e2_w15_heartbeats_to_the_file_and_the_six_wakes(self):
        line = self.line_with(self.w15(), "HEARTBEAT", "ACK", "agent_state.txt", "SendMessage")
        for word in ("DONE PASS", "DONE FAIL", "QUESTION:", "MOCK READY", "CLOSE CASE", "STALL", "LOST"):
            self.assertIn(word, line)

    def test_g_w15_tell_start_resume_and_the_board(self):
        lines = self.w15()
        self.line_with(lines, "agent-file.sh tell")
        self.line_with(lines, "resume", "agent-watch.sh --all")
        self.line_with(lines, "not confirmed")

    def test_k_w14_status_line_rows(self):
        w14 = section(read("PRINCIPLES.md"), "W14. Show todo", "W15.").splitlines()
        line = self.line_with(w14, "statusline", "5 lines")
        for word in ("own row", "+N queued/held", "warning"):
            self.assertIn(word, line)

    def test_g_dispatch_starts_or_restarts_one_all_watch(self):
        text = read("skills", "dispatch", "SKILL.md")
        steps = section(text, "# /dispatch", "## Board records")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-watch.sh --all", steps)
        self.assertNotIn("agent-watch.sh --terminal", text)
        at = steps.index("agent-watch.sh --all")
        near = steps[max(0, at - 300):at + 900]
        for word in ("run_in_background", "again", "MOCK READY", "STALL", "LOST"):
            self.assertIn(word, near)

    def test_e4_dispatch_sends_text_with_tell(self):
        steps = section(read("skills", "dispatch", "SKILL.md"), "# /dispatch", "## Board records")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh tell", steps)

    def test_e4_the_brief_template_reports_into_the_file(self):
        brief = section(read("skills", "dispatch", "SKILL.md"), "## Task manager brief", "## Cross-repo brief")
        for head in ("REPORT:", "ASK:", "HEARTBEAT:", "CLOSE:"):
            line = next(l for l in brief.splitlines() if l.startswith(head))
            self.assertIn("agent_state.txt", line, head)
            self.assertNotIn("SendMessage", line, head)

    def test_g_merge_skill_names_the_all_watch(self):
        self.assertTrue([l for l in read("skills", "merge", "SKILL.md").splitlines() if "agent-watch.sh --all" in l])

    def test_g_readme_names_the_all_watch_and_tell(self):
        text = read("README.md")
        self.assertIn("agent-watch.sh --all", text)
        self.assertIn("agent-file.sh tell", text)


class TestStartRoleLine(ScriptCase):
    script = "agent-start.sh"

    def test_e3_the_task_manager_role_line_says_report_into_agent_state(self):
        out = self.assertOk(self.repo.run("agent-start.sh", env={"AGENT_ROLE": "task-manager"}))
        role = next(l for l in self.lines(out) if l.startswith("ROLE: "))
        self.assertIn("agent_state.txt", role)
        self.assertIn("watch", role)
        self.assertNotIn("SendMessage", role)


if __name__ == "__main__":
    unittest.main()
