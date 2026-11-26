"""idle-task-flag (owner, 2026-11-26): a task added to the board and not started for 10 minutes or more, with no
wait, no live agent and no live task manager pane, reads `not started · idle 25m` on the board and the status
line, and the main manager is warned (WARN idle <task> (25m) -> ...). Fixed numbers: 10 minutes, 24 hours.

Every example runs in zh and en (the English classes at the end)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import importlib.util
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from test_agent_board import BoardCase, NOW, HOST  # noqa: E402
from scripthelp import ROOT  # noqa: E402

BASE_REF = "origin/ap-main-maverick"
MAIN_PID = "424242"
FIRST = "Board warning for the main manager, act in this turn:"
MARK = {"zh": "未开始 · 闲置 %d分钟", "en": "not started · idle %dm"}
PLAIN = {"zh": "未开始", "en": "not started"}
RUNNING = {"zh": "进行中", "en": "running"}


def warn_idle(task, n):
    return ('WARN idle %s (%dm) -> start it now, or record why it waits: agent-file.sh todo wait "%s" on queue '
            '--after <other task> | on hold "<why>"' % (task, n, task))


class IdleCase(BoardCase):
    lang = "zh"

    def mark(self, n):
        return MARK[self.lang] % n

    def plain(self):
        return PLAIN[self.lang]

    def todo(self, name, opened, **kw):
        self.add(name, "the task " + name, 20, opened=opened, started=False, **kw)

    def launch(self, kind, task, since="2026-11-02 14:50", agent="a1"):
        line = "LAUNCH k_%s_%s: %s | task %s | title of %s | since %s | pid %d | by main" % (
            kind, task, kind, task, kind, since, os.getpid())
        if agent:
            line += " | agent " + agent
        self.state(line)

    def status_of(self, name):
        return self.row(self.rows(), name)["Status"]

    def warns(self, now=NOW):
        return [l for l in self.af("next", now=now).stdout.splitlines() if l.startswith("WARN ")]

    # ---- the examples ----

    def test_25_minutes_not_started_is_idle_on_the_board_and_warned(self):
        self.todo("t", "2026-11-02 14:35")
        self.assertEqual(self.status_of("t"), self.mark(25))
        self.assertEqual(self.warns(), [warn_idle("t", 25)])

    def test_5_minutes_is_plain_not_started_and_no_warning(self):
        self.todo("t", "2026-11-02 14:55")
        self.assertEqual(self.status_of("t"), self.plain())
        self.assertEqual(self.warns(), [])

    def test_exactly_10_minutes_is_idle_and_9_is_not(self):
        self.todo("ten", "2026-11-02 14:50")
        self.todo("nine", "2026-11-02 14:51")
        rows = self.rows()
        self.assertEqual(self.row(rows, "ten")["Status"], self.mark(10))
        self.assertEqual(self.row(rows, "nine")["Status"], self.plain())

    def test_a_queue_wait_is_no_idle(self):
        self.todo("t", "2026-11-02 14:35")
        self.wait("t", "on", "queue", "--after", "x", now="2026-11-02 14:36")
        self.assertEqual(self.status_of("t"), self.st("queue") + (" · 在 x 之后" if self.lang == "zh" else " · after x"))
        self.assertEqual(self.warns(), [])

    def test_a_hold_wait_is_no_idle(self):
        self.todo("t", "2026-11-02 14:35")
        self.wait("t", "on", "hold", "later", now="2026-11-02 14:36")
        self.assertNotIn(self.word_idle(), self.status_of("t"))
        self.assertTrue(self.status_of("t").startswith(self.st("hold")), self.status_of("t"))
        self.assertEqual(self.warns(), [])

    def test_a_question_wait_is_no_idle(self):
        self.todo("t", "2026-11-02 14:35")
        self.wait("t", "on", "question", "which one", now="2026-11-02 14:36")
        self.assertNotIn(self.word_idle(), self.status_of("t"))
        self.assertEqual(self.warns(), [])

    def word_idle(self):
        return "闲置" if self.lang == "zh" else "idle"

    def test_a_live_agent_is_running_never_idle(self):
        self.todo("t", "2026-11-02 14:35")
        self.launch("deputy", "t")
        status = self.status_of("t")
        self.assertTrue(status.startswith(RUNNING[self.lang]), status)
        self.assertNotIn(self.word_idle(), status)
        self.assertEqual(self.warns(), [])

    def test_a_live_task_manager_pane_alone_is_running_never_idle(self):
        self.todo("t", "2026-11-02 14:35")
        self.launch("tm-pane", "t", agent=None)
        status = self.status_of("t")
        self.assertTrue(status.startswith(RUNNING[self.lang]), status)
        self.assertNotIn(self.word_idle(), status)
        self.assertEqual(self.warns(), [])

    def test_30_hours_old_is_backlog_plain_and_no_warning(self):
        self.todo("t", "2026-11-01 09:00")
        self.assertEqual(self.status_of("t"), self.plain())
        self.assertEqual(self.warns(), [])

    def test_a_stage_set_is_never_idle(self):
        self.todo("t", "2026-11-02 14:35")
        self.af("todo", "stage", "t", "brief", now="2026-11-02 14:50")
        self.assertNotIn(self.word_idle(), self.status_of("t"))
        self.assertEqual(self.warns(), [])

    def test_a_line_with_no_added_time_is_plain_and_does_not_crash(self):
        self.repo.write("agent_todo.txt", "t | big | no time here | est 20m\n")
        self.assertEqual(self.status_of("t"), self.plain())
        self.assertEqual(self.warns(), [])

    def test_two_idle_tasks_are_both_named_oldest_first(self):
        self.todo("younger", "2026-11-02 14:40")
        self.todo("older", "2026-11-02 14:20")
        self.assertEqual(self.warns(), [warn_idle("older", 40), warn_idle("younger", 20)])

    # ---- the status line ----

    def line(self, width, base=False):
        stdin = json.dumps({"session_id": "s1", "cwd": self.repo.dir,
                            "workspace": {"current_dir": self.repo.dir, "project_dir": self.repo.dir}})
        env = {"AGENT_FAKE_NOW": NOW, "AGENT_STATUSLINE_WIDTH": str(width)}
        if not base:
            r = self.statusline_py(stdin, env=env)
        else:
            self.repo._board_module = self.base_module()
            try:
                r = self.statusline_py(stdin, env=env)
            finally:
                self.repo._board_module = None
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def base_module(self):
        here = os.path.realpath(ROOT)
        ok = subprocess.run(["git", "-C", here, "rev-parse", "--verify", "-q", BASE_REF], capture_output=True)
        if ok.returncode:
            self.skipTest("no %s here" % BASE_REF)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tar = subprocess.run(["git", "-C", here, "archive", BASE_REF, "bin"], capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", tmp], input=tar, check=True)
        spec = importlib.util.spec_from_file_location("agent_board__base_%x" % id(self),
                                                      os.path.join(tmp, "bin", "agent_board.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_the_status_line_marks_an_idle_task_at_every_width(self):
        self.todo("idler", "2026-11-02 14:35")
        for width in (0, 70, 200):
            out = self.line(width)
            rows = [l for l in out.splitlines() if "idler" in l]
            self.assertEqual(len(rows), 1, (width, out))
            self.assertIn(self.mark(25), rows[0], (width, out))

    def test_the_status_line_marks_only_the_idle_one(self):
        self.todo("idler", "2026-11-02 14:35")
        self.todo("fresh", "2026-11-02 14:57")
        out = self.line(200)
        self.assertEqual(out.count(self.word_idle()), 1, out)
        self.assertIn(self.plain(), [l for l in out.splitlines() if "fresh" in l][0])

    def test_a_repo_with_no_idle_task_prints_what_the_base_prints(self):
        self.todo("fresh", "2026-11-02 14:57")
        self.todo("old", "2026-11-01 09:00")
        self.todo("q", "2026-11-02 14:00")
        self.wait("q", "on", "queue", "--after", "fresh", now="2026-11-02 14:10")
        self.add("run", "running one", 30, opened="2026-11-02 14:00")
        self.af("todo", "stage", "run", "workers", "1/2", now="2026-11-02 14:30")
        for width in (0, 70, 200):
            self.assertEqual(self.line(width), self.line(width, base=True), width)

    # ---- the warning is said once (the existing hook limit) ----

    def hook(self, now=NOW):
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%s 2026-11-02 13:00 s1 term_m\n" % MAIN_PID)
        env = {"AGENT_FAKE_NOW": now, "AGENT_FAKE_HOST": HOST, "CLAUDE_PID": MAIN_PID}
        payload = {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "cwd": self.repo.dir, "prompt": "go"}
        r = self.repo.run("agent-board-warn.sh", stdin=json.dumps(payload), env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_the_hook_says_it_once_while_the_set_is_the_same(self):
        self.todo("t", "2026-11-02 14:35")
        self.assertEqual(self.hook().splitlines(), [FIRST, warn_idle("t", 25)])
        self.assertEqual(self.hook(now="2026-11-02 15:05"), "", "only the minutes changed")


class IdleCaseEnglish(IdleCase):
    lang = "en"


if __name__ == "__main__":
    unittest.main()
