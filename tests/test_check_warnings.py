"""Failing tests for check-blocks section 12: the board warnings reach the main manager.
Written by the task manager before any code (TELL 315ae904, owner 2026-11-25).

    (1) agent-file.sh next prints every board warning with the reaction, after its NEXT/START/WAIT lines:
          WARN watch not running -> start it now: <plugin>/bin/agent-watch.sh --all (Bash run_in_background)
          WARN not confirmed <task> (<n>m) -> read its pane or its newest state line, then fix the record or the agent
          WARN pane without a task line <path> -> add the todo line or close the pane
        The same warnings as the board (same rules: targets, watch_quiet_min, plain or cloud = none).
    (2) bin/agent-board-warn.sh, a UserPromptSubmit and PostToolUse hook: main manager only; prints the WARN
        lines when the set is new or changed, at most once a minute; nothing else. UserPromptSubmit: plain
        lines; PostToolUse: {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ..}}.
        First line "Board warning for the main manager, act in this turn:". Exit 0, stderr empty, no orca.
    (3) rule text: tests/test_check_rules.py (W15).
    (2b) the watch wakes the main manager when a slot is free and a task is queued: WATCH SLOT <name>
    (4) the watch: a target task with no task manager pane is watched through the live pane of the
        human-direct Helper whose task names it (field 3 "task: <Task Name>", the name in lower case with
        runs of other characters as "-"); the pane is found in the Helper's folder by its title
        "Helper - <Task Name>".

Run: python3 -m unittest tests.test_check_warnings
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_agent_board as tb  # noqa: E402
import test_watch_board as twb  # noqa: E402
from scripthelp import ROOT  # noqa: E402
from watchhelp import AllCase, moving  # noqa: E402

NOW = tb.NOW            # "2026-11-02 15:00"
MAIN_PID = "424242"
FIRST = "Board warning for the main manager, act in this turn:"


def warn_watch(plugin):
    return "WARN watch not running -> start it now: %s/bin/agent-watch.sh --all (Bash run_in_background)" % plugin


def warn_quiet(task, n):
    return ("WARN not confirmed %s (%dm) -> read its pane or its newest state line, then fix the record or the agent"
            % (task, n))


def warn_orphan(path):
    return "WARN pane without a task line %s -> add the todo line or close the pane" % path


GHOST = {"path": "/x/ghost", "title": "◑ ghost Task Manager", "handle": "term_g"}


class TestNextWarns(twb.WatchBoardCase):
    lang = "en"

    def next_lines(self, now=NOW):
        return self.af("next", now=now).stdout.splitlines()

    def warns(self, lines):
        return [l for l in lines if l.startswith("WARN ")]

    def test_watch_not_running(self):
        self.assertEqual(self.warns(self.next_lines()), [warn_watch(self.repo.plugin)])

    def test_not_confirmed(self):
        self.watch(changed="2026-11-02 14:40", confirmed="2026-11-02 14:59")
        self.assertEqual(self.warns(self.next_lines()), [warn_quiet("alpha", 20)])

    def test_pane_without_a_task_line(self):
        self.watch(changed="2026-11-02 14:58", orphans=[GHOST])
        self.assertEqual(self.warns(self.next_lines()), [warn_orphan("/x/ghost")])

    def test_all_confirmed_no_warn(self):
        self.watch(changed="2026-11-02 14:58")
        self.assertEqual(self.warns(self.next_lines()), [])

    def test_warns_come_last(self):
        self.watch(changed="2026-11-02 14:40", orphans=[GHOST])
        lines = self.next_lines()
        self.assertTrue(lines[0].startswith("NEXT: "), lines)
        firsts = [i for i, l in enumerate(lines) if l.startswith("WARN ")]
        self.assertEqual(firsts, list(range(len(lines) - len(firsts), len(lines))))
        self.assertEqual(self.warns(lines), [warn_quiet("alpha", 20), warn_orphan("/x/ghost")])

    def test_plain_runtime_has_no_warn(self):
        self.repo.set_conf("runtime", "plain")
        self.assertEqual(self.warns(self.next_lines()), [])


class TestWarnHook(twb.WatchBoardCase):
    lang = "en"
    script = "agent-board-warn.sh"

    def setUp(self):
        super().setUp()
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%s 2026-11-02 13:00 s1 term_m\n" % MAIN_PID)

    def hook(self, event="UserPromptSubmit", now=NOW, main=True):
        env = {"AGENT_FAKE_NOW": now, "AGENT_FAKE_HOST": tb.HOST}
        env.update({"CLAUDE_PID": MAIN_PID} if main else {"CLAUDE_PID": "999999", "AGENT_ROLE": "task-manager"})
        payload = {"hook_event_name": event, "session_id": "s1", "cwd": self.repo.dir}
        if event == "UserPromptSubmit":
            payload["prompt"] = "go on"
        else:
            payload.update({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        r = self.repo.run("agent-board-warn.sh", stdin=json.dumps(payload), env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def test_a_new_warning_reaches_the_main_manager(self):
        out = self.hook()
        self.assertEqual(out.splitlines(), [FIRST, warn_watch(self.repo.plugin)])

    def test_post_tool_use_gives_additional_context(self):
        data = json.loads(self.hook("PostToolUse"))
        spec = data["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PostToolUse")
        self.assertEqual(spec["additionalContext"].splitlines(), [FIRST, warn_watch(self.repo.plugin)])

    def test_the_same_set_is_said_once(self):
        self.assertTrue(self.hook())
        self.assertEqual(self.hook(), "")
        self.assertEqual(self.hook("PostToolUse", now="2026-11-02 15:05"), "")

    def test_a_changed_set_is_said_again_at_most_once_a_minute(self):
        self.assertTrue(self.hook())
        self.watch(changed="2026-11-02 14:58", orphans=[GHOST])        # watch up: a new set
        self.assertEqual(self.hook(now=NOW), "")                       # same minute: held
        out = self.hook(now="2026-11-02 15:01")
        self.assertEqual(out.splitlines(), [FIRST, warn_orphan("/x/ghost")])

    def test_cleared_then_back_is_said_again(self):
        self.assertTrue(self.hook())
        self.watch(changed="2026-11-02 14:59")
        self.assertEqual(self.hook(now="2026-11-02 15:01"), "")
        self.watch(changed="2026-11-02 14:59", orphans=[GHOST])
        self.assertTrue(self.hook(now="2026-11-02 15:02"))

    def test_only_the_main_manager(self):
        self.assertEqual(self.hook(main=False), "")

    def test_not_a_subagent_of_the_main_manager(self):
        # core review defect 14: a deputy runs in the main manager's process; its payload has agent_id
        env = {"AGENT_FAKE_NOW": NOW, "AGENT_FAKE_HOST": tb.HOST, "CLAUDE_PID": MAIN_PID}
        payload = {"hook_event_name": "PostToolUse", "session_id": "s1", "cwd": self.repo.dir,
                   "agent_id": "a123", "agent_type": "auto-pipeline:merge-deputy",
                   "tool_name": "Bash", "tool_input": {"command": "ls"}}
        r = self.repo.run("agent-board-warn.sh", stdin=json.dumps(payload), env=env)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertTrue(self.hook(), "the subagent's call must not use up the main manager's warning")

    def test_a_growing_quiet_time_is_the_same_warning(self):
        self.watch(changed="2026-11-02 14:40", confirmed="2026-11-02 14:59")
        self.assertEqual(self.hook().splitlines(), [FIRST, warn_quiet("alpha", 20)])
        self.assertEqual(self.hook(now="2026-11-02 15:05"), "", "only the minutes changed")

    def test_no_orca_calls(self):
        self.repo.clear_calls()
        self.hook()
        self.assertEqual(self.repo.calls(), [])

    def test_registered_for_prompts_and_tool_calls(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json")) as fh:
            hooks = json.load(fh)["hooks"]
        for event in ("UserPromptSubmit", "PostToolUse"):
            with self.subTest(event=event):
                cmds = [h["command"] for group in hooks[event] for h in group["hooks"]]
                self.assertTrue([c for c in cmds if "bin/agent-board-warn.sh" in c], cmds)


class TestHelperPaneConfirms(AllCase):
    """(4): city-office-2 showed "not confirmed" because its Helper works from the main folder."""

    def test_a_helper_task_is_watched_through_the_helpers_own_pane(self):
        t = self.task("city-office-2", pane="term_gone", launch=False)
        self.rows.append((self.repo.dir, "task manager, human-direct", "task: City Office 2"))
        self.write_rows()
        self.screens("term_h", moving())
        self.terminals([{"handle": "term_m", "title": "✳ project Manager", "worktreePath": self.repo.dir,
                         "agentIdentity": "claude"},
                        {"handle": "term_h", "title": "◑ project Helper - City Office 2",
                         "worktreePath": self.repo.dir, "agentIdentity": "claude"}])
        self.run_all(max_sweeps="2")
        st = self.status()["tasks"]["city-office-2"]
        self.assertEqual((st["watched"], st["pane"]), (True, "term_h"), st)
        self.assertNotEqual(t["path"], self.repo.dir)

    def test_a_helper_of_another_task_does_not_count(self):
        self.task("city-office-2", pane="term_gone", launch=False)
        self.rows.append((self.repo.dir, "task manager, human-direct", "task: Bank Recon"))
        self.write_rows()
        self.screens("term_h", moving())
        self.terminals([{"handle": "term_h", "title": "◑ project Helper - Bank Recon",
                         "worktreePath": self.repo.dir, "agentIdentity": "claude"}])
        self.run_all(max_sweeps="2")
        self.assertFalse(self.status()["tasks"]["city-office-2"]["watched"])


class TestWatchSlot(AllCase):
    """Section 2: the watch wakes the main manager when a slot is free and a task is queued.
    Only a line with an open queue wait whose after-task is closed (or that has none) counts;
    each name is said once (the status file keeps "slots": [names said])."""

    def queued(self, name, after=None):
        self.todo(name)
        args = ["todo", "wait", name, "on", "queue"] + (["--after", after] if after else [])
        self.assertOk(self.repo.run("agent-file.sh", *args))

    def test_a_queued_task_that_can_start_wakes_the_manager(self):
        self.task("alpha")
        self.queued("q")
        text = self.text(self.run_all(max_sweeps="3"))
        self.assertEqual(self.one_watch(text), "WATCH SLOT q: can start (run agent-file.sh next)")
        self.assertEqual(self.status()["slots"], ["q"])

    def test_said_once(self):
        self.task("alpha")
        self.queued("q")
        self.run_all(max_sweeps="3")
        text = self.text(self.run_all(max_sweeps="2"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")

    def test_after_an_open_task_no_wake(self):
        self.task("alpha")
        self.todo("alpha-line")
        self.assertOk(self.repo.run("agent-file.sh", "todo", "stage", "alpha-line", "tests"))
        self.queued("q", after="alpha-line")
        text = self.text(self.run_all(max_sweeps="2"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")

    def test_a_line_that_never_queued_never_wakes(self):
        self.task("alpha")
        self.todo("plain")
        text = self.text(self.run_all(max_sweeps="2"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")


if __name__ == "__main__":
    unittest.main()
