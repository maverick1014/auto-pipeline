"""Failing tests for board-trust (level 4). Written by the task manager first.

The rules, with every example used here: requirements/board-trust.md (rules table A, parse B, fail open C).

CONTRACT
    bin/agent-guard.sh     the hook entry (PreToolUse and PostToolUse matcher Agent|Task|Bash, SubagentStart,
                           SubagentStop). Reads the hook JSON on stdin. A Bash call whose command has no "orca"
                           exits 0 with bash builtins only (bin/agent_guard.py is never started). Anything else runs
                           python3 bin/agent_guard.py. Exit 2 = blocked (one stderr line); every other outcome is 0.
    bin/agent_guard.py     the logic. Never raises: any error = exit 0 + one stderr line "board guard: ...; allowed".
    env                    CLAUDE_PID (the session's claude pid; else the first claude process up the parent chain),
                           AGENT_ROLE, AGENT_FAKE_NOW ("YYYY-MM-DD HH:MM").
    repo                   main repo = the first `git worktree list` entry of the payload cwd; a pipeline repo has
                           agent.conf there; the record folder = git toplevel of the payload cwd.
    role                   main: <git common dir>/agent_main.lock names a live pid equal to the session pid.
                           tm: AGENT_ROLE=task-manager. free: everything else, and any payload with an agent_id.
    record                 LAUNCH <key>: <kind> | task <task> | <title> | since <date> | pid <pid> | by <role>
                           [ | type <subagent_type>][ | agent <agent_id>][ | pane <handle>][ | env <env>]
                           [ | worktree <path>]   (key = tool_use_id; kind: "worker <n>", deputy, merge, reviewer,
                           explore, plan, guide, agent, tm-pane, shell-pane, pane, helper-pane)
    board                  a record shows right under its task's row: "<task> <kind word>[ <n>]"; dead or stale
                           records are not shown; the status line adds " · <n> 代理" (en " · <n> agent(s)").
    switch                 agent.conf board_guard = on (default) | record | off, via agent-settings.sh.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

import test_agent_board as tb  # noqa: E402  (the module only)

NOW = "2026-11-20 16:50"
LIVE = os.getpid()
SHELL_TITLE = "[auto-pipeline] board-waiting pc2 shell · LIVE - do not close"


def dead_pid():
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


def todo(name, stage=True):
    line = "%s | big | the %s task | est 60m | level 4 | opened 2026-11-20 16:00 | by main" % (name, name)
    if stage:
        line += " | started 2026-11-20 16:00 | stage workers since 2026-11-20 16:30"
    return line


class GuardCase(tb.BoardCase):
    script = "agent-guard.sh"
    lang = "zh"

    def setUp(self):
        super().setUp()
        self.cfg = tempfile.mkdtemp(prefix="board_trust_cfg_")
        self.addCleanup(shutil.rmtree, self.cfg, True)
        self.n = 0

    # ---- the files

    def put_todo(self, *names):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("".join(todo(n) + "\n" for n in names))

    def make_main(self, pid=LIVE):
        """This session holds the main lock."""
        gd = subprocess.run(["git", "-C", self.repo.dir, "rev-parse", "--path-format=absolute",
                             "--git-common-dir"], capture_output=True, text=True, check=True).stdout.strip()
        with open(os.path.join(gd, "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-11-20 16:00 s-main term_main\n" % pid)

    def launches(self, folder=None):
        return [l for l in self.state_text(folder).splitlines() if l.startswith("LAUNCH ")]

    def put_launch(self, line, folder=None):
        self.state(line, folder)

    # ---- the hook

    def hook(self, payload, role=None, pid=LIVE, now=NOW, cwd=None, extra_env=None):
        cwd = cwd or self.repo.dir
        payload = dict({"session_id": "s1", "transcript_path": os.path.join(self.cfg, "t.jsonl"), "cwd": cwd,
                        "permission_mode": "bypassPermissions"}, **payload)
        env = {"AGENT_FAKE_NOW": now, "AGENT_FAKE_HOST": tb.HOST, "CLAUDE_PID": str(pid),
               "CLAUDE_CONFIG_DIR": self.cfg}
        if role:
            env["AGENT_ROLE"] = role
        env.update(extra_env or {})
        result = self.repo.run("agent-guard.sh", cwd=cwd, stdin=json.dumps(payload), env=env, timeout=30)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn(result.returncode, (0, 2), result.stderr)
        return result

    def tid(self):
        self.n += 1
        return "toolu_%02d" % self.n

    def pre_agent(self, desc, stype="auto-pipeline:worker", tid=None, bg=True, **kw):
        tid = tid or self.tid()
        inp = {"description": desc, "prompt": "brief", "subagent_type": stype, "run_in_background": bg}
        r = self.hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": inp,
                       "tool_use_id": tid}, **kw)
        r.tid = tid
        return r

    def post_agent(self, tid, agent_id, status="async_launched", desc="d", stype="auto-pipeline:worker", **kw):
        inp = {"description": desc, "prompt": "brief", "subagent_type": stype, "run_in_background": True}
        return self.hook({"hook_event_name": "PostToolUse", "tool_name": "Agent", "tool_input": inp,
                          "tool_use_id": tid, "tool_response": {"status": status, "agentId": agent_id}}, **kw)

    def sub(self, event, agent_id, stype="auto-pipeline:worker", **kw):
        return self.hook({"hook_event_name": event, "agent_id": agent_id, "agent_type": stype}, **kw)

    def pre_bash(self, command, tid=None, **kw):
        tid = tid or self.tid()
        r = self.hook({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                       "tool_input": {"command": command, "description": "x"}, "tool_use_id": tid}, **kw)
        r.tid = tid
        return r

    def post_bash(self, command, tid, stdout="", **kw):
        return self.hook({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                          "tool_input": {"command": command, "description": "x"}, "tool_use_id": tid,
                          "tool_response": {"stdout": stdout, "stderr": "", "interrupted": False}}, **kw)

    # ---- asserts

    def assertAllowed(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)

    def assertBlocked(self, r, *words):
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        lines = r.stderr.strip().splitlines()
        self.assertEqual(len(lines), 1, r.stderr)
        self.assertTrue(lines[0].startswith("board guard: "), lines[0])
        for w in words:
            self.assertIn(w, lines[0])

    def fields(self, line):
        """{"key", "kind", "task", "title", "since", "pid", "by", optional ...} of one LAUNCH line."""
        head, rest = line[len("LAUNCH "):].split(": ", 1)
        parts = rest.split(" | ")
        out = {"key": head, "kind": parts[0], "title": parts[2]}
        for p in parts[1:2] + parts[3:]:
            k, _, v = p.partition(" ")
            out[k] = v
        return out

    def one_launch(self, folder=None):
        rows = self.launches(folder)
        self.assertEqual(len(rows), 1, rows)
        return self.fields(rows[0])

    def index(self, rows, task):
        for i, r in enumerate(rows):
            if r["Task"] == task:
                return i
        self.fail("no row %r in %r" % (task, [r["Task"] for r in rows]))


class BoardOnly(GuardCase):
    """Board and status line tests: LAUNCH lines written by hand, the guard is not needed."""
    script = "agent-file.sh"


# ---------------------------------------------------------------- A. rules table, main manager


class TestMainManager(GuardCase):
    def setUp(self):
        super().setUp()
        self.make_main()
        self.put_todo("state-trim", "board-trust")

    def test_1_merge_deputy_recorded_shown_under_its_task_removed_at_stop(self):
        r = self.pre_agent("state-trim Merge", "auto-pipeline:merge-deputy")
        self.assertAllowed(r)
        f = self.one_launch()
        self.assertEqual((f["key"], f["kind"], f["task"], f["title"], f["since"], f["pid"], f["by"], f["type"]),
                         (r.tid, "merge", "state-trim", "state-trim Merge", NOW, str(LIVE), "main",
                          "auto-pipeline:merge-deputy"))
        self.assertAllowed(self.post_agent(r.tid, "a038d8ee18e4ea335"))
        self.assertEqual(self.one_launch()["agent"], "a038d8ee18e4ea335")
        rows = self.rows(now="2026-11-20 16:53")
        child = self.index(rows, "state-trim 合并")
        self.assertEqual(child, self.index(rows, "state-trim") + 1)
        c = rows[child]
        self.assertEqual((c["What"], c["Status"], c["Work"], c["Level"], c["Est"]),
                         ("state-trim Merge", "进行中", "3m", "-", "-"))
        self.assertAllowed(self.sub("SubagentStop", "a038d8ee18e4ea335", "auto-pipeline:merge-deputy"))
        self.assertEqual(self.launches(), [])
        self.assertNotIn("state-trim 合并", [x["Task"] for x in self.rows()])

    def test_2_merge_after_todo_done_is_blocked(self):
        self.put_todo("board-trust")
        r = self.pre_agent("state-trim Merge", "auto-pipeline:merge-deputy")
        self.assertBlocked(r, '"state-trim Merge"', "state-trim", "todo add")
        self.assertEqual(self.launches(), [])

    def test_6_explore_free_description_allowed_under_the_manager(self):
        self.assertAllowed(self.pre_agent("Find hook payload fields", "Explore"))
        f = self.one_launch()
        self.assertEqual((f["kind"], f["task"], f["title"]), ("explore", "project Manager", "Find hook payload fields"))
        self.assertEqual(self.row(self.rows(), task="project Manager 探查")["Status"], "进行中")

    def test_6_every_read_only_type_needs_no_task(self):
        kinds = {"Explore": "explore", "Plan": "plan", "claude-code-guide": "guide", "web-fetch": "agent",
                 "statusline-setup": "agent"}
        for stype, kind in kinds.items():
            with self.subTest(stype=stype):
                self.assertAllowed(self.pre_agent("look something up", stype))
                self.assertEqual(self.fields(self.launches()[-1])["kind"], kind)

    def test_7_a_type_that_can_write_must_name_a_task(self):
        for stype in ("general-purpose", "claude", "fork", "auto-pipeline:worker", "auto-pipeline:fast-lane-deputy",
                      "some-plugin:unknown"):
            with self.subTest(stype=stype):
                self.assertBlocked(self.pre_agent("Find hook payload fields", stype), "todo add")
        self.assertEqual(self.launches(), [])

    def test_7_the_same_type_naming_an_open_task_is_allowed(self):
        self.assertAllowed(self.pre_agent("board-trust Reviewer: hook logic vs rules table", "general-purpose"))
        f = self.one_launch()
        self.assertEqual((f["kind"], f["task"], f["title"]), ("reviewer", "board-trust", "hook logic vs rules table"))

    def test_8_shell_pane_recorded_with_handle_shown_removed_at_close(self):
        self.put_todo("board-waiting")
        cmd = ('orca terminal create --worktree path:/w/board-waiting --title "%s" --environment pc2 '
               '--command "zsh" --json' % SHELL_TITLE)
        r = self.pre_bash(cmd)
        self.assertAllowed(r)
        f = self.one_launch()
        self.assertEqual((f["kind"], f["task"], f["title"], f["env"], f["worktree"]),
                         ("shell-pane", "board-waiting", SHELL_TITLE, "pc2", "/w/board-waiting"))
        out = json.dumps({"ok": True, "result": {"terminal": {"handle": "term_bc68aaf3-5722-4519-b334-5b19d9d2661e"}}})
        self.assertAllowed(self.post_bash(cmd, r.tid, out))
        self.assertEqual(self.one_launch()["pane"], "term_bc68aaf3-5722-4519-b334-5b19d9d2661e")
        self.repo.set_orca_answer("terminals.json", {"ok": True, "result": {"terminals": [
            {"handle": "term_bc68aaf3-5722-4519-b334-5b19d9d2661e", "title": SHELL_TITLE}]}}, env="pc2")
        rows = self.rows()
        i = self.index(rows, "board-waiting 窗格")
        self.assertEqual(i, self.index(rows, "board-waiting") + 1)
        # the board cuts every What cell at 60 characters (WHAT_MAX), the record keeps the whole title
        self.assertEqual(rows[i]["What"], "[auto-pipeline] board-waiting pc2 shell · LIVE - do not…")
        close = "orca terminal close --terminal term_bc68aaf3-5722-4519-b334-5b19d9d2661e --environment pc2 --json"
        c = self.pre_bash(close)
        self.assertAllowed(c)
        self.assertAllowed(self.post_bash(close, c.tid, '{"ok":true}'))
        self.assertEqual(self.launches(), [])

    def test_8_pane_gone_from_orca_list_is_not_shown_orca_down_is_shown(self):
        self.put_todo("board-waiting")
        self.put_launch("LAUNCH toolu_x: shell-pane | task board-waiting | %s | since 2026-11-20 16:40 | pid %d | "
                        "by main | pane term_gone | env pc2 | worktree /w/board-waiting" % (SHELL_TITLE, LIVE))
        self.repo.set_orca_answer("terminals.json", {"ok": True, "result": {"terminals": [{"handle": "term_other"}]}},
                                  env="pc2")
        self.assertNotIn("board-waiting 窗格", [x["Task"] for x in self.rows()])
        self.repo.set_orca_env_state("pc2", "down")
        self.assertIn("board-waiting 窗格", [x["Task"] for x in self.rows()])

    def test_8_orca_worktree_rm_removes_its_panes(self):
        self.put_todo("board-waiting")
        self.put_launch("LAUNCH toolu_x: tm-pane | task board-waiting | board-waiting Task Manager | since "
                        "2026-11-20 16:40 | pid %d | by main | pane term_a | worktree /w/board-waiting" % LIVE)
        rm = "orca worktree rm --worktree path:/w/board-waiting --json"
        r = self.pre_bash(rm)
        self.assertAllowed(r)
        self.assertAllowed(self.post_bash(rm, r.tid, '{"ok":true}'))
        self.assertEqual(self.launches(), [])

    def test_9_shell_pane_for_a_closed_task_is_blocked(self):
        r = self.pre_bash('orca terminal create --worktree path:/w/bw --title "%s" --json' % SHELL_TITLE)
        self.assertBlocked(r, "board-waiting", "todo add")
        self.assertEqual(self.launches(), [])

    def test_10_task_manager_pane_by_title_or_by_name(self):
        r = self.pre_bash("orca terminal create --worktree path:/w/board-trust --title \"board-trust Task Manager\" "
                          "--command \"AGENT_ROLE=task-manager claude --name 'board-trust Task Manager' --model "
                          "'opus' --effort xhigh --permission-mode bypassPermissions\" --json")
        self.assertAllowed(r)
        f = self.one_launch()
        self.assertEqual((f["kind"], f["task"]), ("tm-pane", "board-trust"))
        r = self.pre_bash("orca terminal create --worktree path:/w/st --command \"AGENT_ROLE=task-manager claude "
                          "--name 'state-trim Task Manager' --effort xhigh\" --json")
        self.assertAllowed(r)
        self.assertEqual(self.fields(self.launches()[-1])["task"], "state-trim")
        self.assertBlocked(self.pre_bash("orca terminal create --worktree path:/w/x --title \"old-task Task Manager\" "
                                         "--json"), "old-task")

    def test_11_worktree_create_checked_not_recorded(self):
        self.assertAllowed(self.pre_bash("orca worktree create --name board-trust --repo path:/r --base-branch main "
                                         "--no-parent --json"))
        self.assertEqual(self.launches(), [])
        self.assertBlocked(self.pre_bash("orca worktree create --name old-task --repo path:/r --json"),
                           "old-task", "todo add")

    def test_12_helper_pane_needs_no_task(self):
        r = self.pre_bash("orca terminal create --worktree path:/r --command \"claude --name 'project Helper' "
                          "--permission-mode auto --effort xhigh\" --json")
        self.assertAllowed(r)
        f = self.one_launch()
        self.assertEqual((f["kind"], f["task"]), ("helper-pane", "project Helper"))

    def test_15_not_a_launch(self):
        self.put_todo()
        for cmd in ('grep -n "orca terminal create" skills/dispatch/SKILL.md',
                    "grep -n 'orca worktree create --name x' README.md",
                    "cat >> agent_state.txt <<'EOF'\nreport: orca terminal create --title x\nEOF",
                    "python3 - <<'EOF'\nimport os\nos.system('orca terminal create --title y')\nEOF",
                    "orca terminal list --json", "orca terminal read --terminal term_a --json",
                    "echo orca-terminal-create"):
            with self.subTest(cmd=cmd):
                r = self.pre_bash(cmd)
                self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.launches(), [])

    def test_15_command_positions_that_are_launches(self):
        self.put_todo()
        for cmd in ('H=$(orca terminal create --worktree path:/w --title "zz Task Manager" --json)',
                    'cd /w && orca terminal create --title "zz Task Manager" --json',
                    'ls; orca worktree create --name zz --repo path:/r --json',
                    'S=1 orca terminal create --title="zz Task Manager" --json',
                    # review 21: a full path, env / time prefixes, after then
                    '/opt/homebrew/bin/orca terminal create --title "zz Task Manager" --json',
                    'env X=1 orca terminal create --title "zz Task Manager" --json',
                    'time orca worktree create --name zz --repo path:/r --json',
                    'if true; then orca terminal create --title "zz Task Manager" --json; fi'):
            with self.subTest(cmd=cmd):
                self.assertBlocked(self.pre_bash(cmd), "zz")

    def test_16_dead_session_hidden_then_pruned_by_the_next_write(self):
        dead = dead_pid()
        self.put_launch("LAUNCH toolu_d: worker 1 | task state-trim | trim engine | since 2026-11-20 16:40 | "
                        "pid %d | by main | type auto-pipeline:worker | agent a1" % dead)
        self.assertNotIn("state-trim 工人 1", [x["Task"] for x in self.rows()])
        self.assertAllowed(self.pre_agent("state-trim Worker 2: housekeep", "auto-pipeline:worker"))
        rows = self.launches()
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("worker 2", rows[0])

    def test_17_never_linked_hidden_after_two_minutes(self):
        self.put_launch("LAUNCH toolu_n: worker 1 | task state-trim | trim engine | since 2026-11-20 16:47 | "
                        "pid %d | by main | type auto-pipeline:worker" % LIVE)
        self.assertNotIn("state-trim 工人 1", [x["Task"] for x in self.rows(now=NOW)])
        self.assertIn("state-trim 工人 1", [x["Task"] for x in self.rows(now="2026-11-20 16:48")])

    def test_17_subagent_start_links_a_foreground_launch(self):
        r = self.pre_agent("state-trim Worker 1: trim engine", bg=False)
        self.assertAllowed(self.sub("SubagentStart", "afg1", "auto-pipeline:worker"))
        self.assertEqual(self.one_launch()["agent"], "afg1")
        self.assertIn("state-trim 工人 1", [x["Task"] for x in self.rows(now="2026-11-20 16:59")])
        self.assertAllowed(self.post_agent(r.tid, "afg1", status="completed"))
        self.assertEqual(self.launches(), [])

    def test_18_hand_worker_line_and_record_give_one_row(self):
        wt = self.task_worktree("state-trim")
        self.worktree_lines((wt, "state-trim", "working"))
        self.af("worker", "on", "1", "trim engine", cwd=wt, now="2026-11-20 16:40")
        self.put_launch("LAUNCH toolu_w: worker 1 | task state-trim | trim engine | since 2026-11-20 16:40 | "
                        "pid %d | by tm | type auto-pipeline:worker | agent a1" % LIVE, folder=wt)
        tasks = [x["Task"] for x in self.rows()]
        self.assertEqual(tasks.count("state-trim 工人 1"), 1, tasks)

    def test_title_has_no_field_break(self):
        self.assertAllowed(self.pre_agent("state-trim Worker 3: a | b\nc"))
        self.assertEqual(self.one_launch()["title"], "a / b c")

    def test_run_in_background_as_a_string(self):
        self.assertAllowed(self.pre_agent("state-trim Worker 1: x", bg="true"))
        self.assertEqual(len(self.launches()), 1)


# ---------------------------------------------------------------- B. the parse


class TestParse(GuardCase):
    def setUp(self):
        super().setUp()
        self.make_main()
        self.put_todo("board-waiting", "state-trim", "board-trust")

    CASES = [
        ("board-waiting Worker 1: todo wait --who/--after, todo stage started, rule texts", "auto-pipeline:worker",
         "worker 1", "board-waiting", "todo wait --who/--after, todo stage started, rule texts"),
        ("board-waiting worker 12: board rows", "auto-pipeline:worker", "worker 12", "board-waiting", "board rows"),
        ("board-trust Worker 2", "auto-pipeline:worker", "worker 2", "board-trust", "board-trust Worker 2"),
        ("state-trim reviewer: trim and hook logic", "general-purpose", "reviewer", "state-trim",
         "trim and hook logic"),
        ("board-waiting Reviewer: board logic vs rules table", "general-purpose", "reviewer", "board-waiting",
         "board logic vs rules table"),
        ("board-trust Deputy", "auto-pipeline:fast-lane-deputy", "deputy", "board-trust", "board-trust Deputy"),
        ("state-trim Merge", "auto-pipeline:merge-deputy", "merge", "state-trim", "state-trim Merge"),
        ("board-trust: check hook fields", "Explore", "explore", "board-trust", "board-trust: check hook fields"),
        ("board-trust check the board", "auto-pipeline:worker", "worker", "board-trust",
         "board-trust check the board"),
        ("board-trust look", "claude-code-guide", "guide", "board-trust", "board-trust look"),
        ("board-trust plan it", "Plan", "plan", "board-trust", "board-trust plan it"),
        ("board-trust read", "general-purpose", "agent", "board-trust", "board-trust read"),
    ]

    def test_descriptions(self):
        for desc, stype, kind, task, title in self.CASES:
            with self.subTest(desc=desc):
                open(self.repo.path("agent_state.txt"), "w").close()
                self.assertAllowed(self.pre_agent(desc, stype))
                f = self.one_launch()
                self.assertEqual((f["kind"], f["task"], f["title"]), (kind, task, title))

    def test_a_role_word_inside_a_free_text_is_no_task(self):
        r = self.pre_agent("Fix the Worker 1 test", "general-purpose")
        self.assertBlocked(r)

    def test_pane_titles(self):
        for title, kind, task in (("[auto-pipeline] board-trust pc2 shell · LIVE - do not close", "shell-pane",
                                   "board-trust"),
                                  ("[auto-pipeline] board-trust Task Manager", "tm-pane", "board-trust"),
                                  ("[auto-pipeline] state-trim watch", "pane", "state-trim"),
                                  ("state-trim logs", "pane", "state-trim")):
            with self.subTest(title=title):
                open(self.repo.path("agent_state.txt"), "w").close()
                self.assertAllowed(self.pre_bash('orca terminal create --title "%s" --json' % title))
                f = self.one_launch()
                self.assertEqual((f["kind"], f["task"], f["title"]), (kind, task, title))

    def test_a_pane_with_no_title_and_no_name_is_blocked_for_main(self):
        self.assertBlocked(self.pre_bash("orca terminal create --worktree path:/w --json"), "todo add")


# ---------------------------------------------------------------- A. rules table, task manager


class TestTaskManager(GuardCase):
    def setUp(self):
        super().setUp()
        self.put_todo("board-waiting")
        self.wt = self.task_worktree("board-waiting")
        self.worktree_lines((self.wt, "board-waiting", "working"))

    def tm(self, desc, stype="auto-pipeline:worker", **kw):
        return self.pre_agent(desc, stype, role="task-manager", cwd=self.wt, **kw)

    def test_3_own_worker_recorded_in_the_worktree_and_shown_under_its_task(self):
        r = self.tm("board-waiting Worker 1: board rows")
        self.assertAllowed(r)
        self.assertEqual(self.launches(), [])
        f = self.one_launch(self.wt)
        self.assertEqual((f["kind"], f["task"], f["title"], f["by"]), ("worker 1", "board-waiting", "board rows", "tm"))
        self.assertAllowed(self.post_agent(r.tid, "ab1f05e4bdfa8ac7f", role="task-manager", cwd=self.wt))
        for args, cwd in ((("--self",), self.wt), ((), self.repo.dir)):
            with self.subTest(view=args):
                rows = self.rows(*args, cwd=cwd)
                i = self.index(rows, "board-waiting 工人 1")
                self.assertEqual(i, self.index(rows, "board-waiting") + 1)
                self.assertEqual(rows[i]["What"], "board rows")

    def test_4_a_worker_for_another_task_is_recorded_under_that_task(self):
        # rule 4 changed 2026-11-23 after the dry-run: 150 of 519 real v4-plus task manager launches name another
        # task (batch worktrees, short names, -2 folders); a task manager is never blocked. A name that is not an
        # open todo task (review 3: "Code Reviewer", "Backend Worker 1") is a role label: its own task
        self.put_todo("board-waiting", "state-trim", "utc-server-dates", "coa-v3")
        for desc, kind, task, title in (
                ("state-trim Worker 1: trim engine", "worker 1", "state-trim", "trim engine"),
                ("utc-server-dates Worker 1: four date fixes", "worker 1", "utc-server-dates", "four date fixes"),
                ("coa-v3 Worker 12: V3 tool required ledgers", "worker 12", "coa-v3", "V3 tool required ledgers"),
                ("Code Reviewer: slice 2 hook logic", "reviewer", "board-waiting", "slice 2 hook logic"),
                ("Backend Worker 1: api", "worker 1", "board-waiting", "api")):
            with self.subTest(desc=desc):
                r = self.tm(desc)
                self.assertEqual((r.returncode, r.stderr), (0, ""))
                f = self.fields(self.launches(self.wt)[-1])
                self.assertEqual((f["kind"], f["task"], f["title"], f["by"]), (kind, task, title, "tm"))

    def test_5_and_14_a_free_launch_is_its_own_task(self):
        for desc, stype, kind in (("Check /goal command semantics", "claude-code-guide", "guide"),
                                  ("W14 slice2 rules M26-M29", "auto-pipeline:worker", "worker"),
                                  ("Find hook payload fields", "general-purpose", "agent")):
            with self.subTest(desc=desc):
                self.assertAllowed(self.tm(desc, stype))
                f = self.fields(self.launches(self.wt)[-1])
                self.assertEqual((f["kind"], f["task"], f["title"]), (kind, "board-waiting", desc))

    def test_own_task_from_the_worktree_line_then_todo_line_then_folder(self):
        def free_task():
            self.assertAllowed(self.tm("look around", "general-purpose"))
            return self.fields(self.launches(self.wt)[-1])["task"]
        self.worktree_lines((self.wt, "alpha", "working"))
        self.assertEqual(free_task(), "alpha")
        self.assertAllowed(self.tm("board-waiting Worker 1: x"))
        self.assertEqual(self.fields(self.launches(self.wt)[-1])["task"], "board-waiting")
        self.worktree_lines()
        self.state("TODO LINE: beta | big | the beta task | est 48m", folder=self.wt)
        self.assertEqual(free_task(), "beta")
        open(os.path.join(self.wt, "agent_state.txt"), "w").close()
        self.assertEqual(free_task(), "board-waiting")

    def test_the_tm_task_need_not_be_in_this_machines_todo(self):
        self.put_todo()
        self.assertAllowed(self.tm("board-waiting Worker 1: board rows"))

    def test_a_tm_pane_for_another_task_is_recorded_under_that_task(self):
        self.put_todo("board-waiting", "state-trim")
        r = self.pre_bash('orca terminal create --title "[auto-pipeline] state-trim shell" --json',
                          role="task-manager", cwd=self.wt)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.fields(self.launches(self.wt)[-1])["task"], "state-trim")
        r = self.pre_bash('orca terminal create --title "e2e test pane" --json', role="task-manager", cwd=self.wt)
        self.assertAllowed(r)
        self.assertEqual(self.fields(self.launches(self.wt)[-1])["task"], "board-waiting")
        r = self.pre_bash('orca terminal create --title "[v4-plus] Backend shell" --json', role="task-manager",
                          cwd=self.wt)
        self.assertAllowed(r)
        f = self.fields(self.launches(self.wt)[-1])
        self.assertEqual((f["kind"], f["task"]), ("shell-pane", "board-waiting"))

    def test_a_task_manager_is_never_blocked(self):
        self.put_todo()
        for r in (self.tm("old-task Merge", "auto-pipeline:merge-deputy"), self.tm("Find hook payload fields"),
                  self.pre_bash('orca terminal create --title "old-task Task Manager" --json', role="task-manager",
                                cwd=self.wt),
                  self.pre_bash("orca worktree create --name old-task --repo path:/r --json", role="task-manager",
                                cwd=self.wt)):
            self.assertEqual((r.returncode, r.stderr), (0, ""))


# ---------------------------------------------------------------- A13. free roles never block


class TestFreeRoles(GuardCase):
    def setUp(self):
        super().setUp()
        self.put_todo()

    def test_no_lock(self):
        r = self.pre_agent("old-task Worker 1: x")
        self.assertAllowed(r)
        self.assertEqual(r.stderr, "")
        self.assertEqual((self.one_launch()["task"], self.one_launch()["by"]), ("old-task", "free"))

    def test_helper_lock_held_by_another_live_pid(self):
        self.make_main(pid=os.getppid())
        self.assertAllowed(self.pre_agent("Find hook payload fields", "general-purpose"))
        self.assertEqual(self.one_launch()["task"], "project")

    def test_dead_lock_holder(self):
        self.make_main(pid=dead_pid())
        self.assertAllowed(self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy"))

    def test_other_agent_role(self):
        self.assertAllowed(self.pre_agent("old-task Worker 1: x", role="reviewer"))

    def test_a_call_from_inside_a_subagent(self):
        self.make_main()
        inp = {"description": "old-task Worker 1: x", "prompt": "p", "subagent_type": "auto-pipeline:worker"}
        r = self.hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": inp,
                       "tool_use_id": "toolu_s", "agent_id": "a038d8ee18e4ea335", "agent_type": "general-purpose"})
        self.assertAllowed(r)


# ---------------------------------------------------------------- C. fail open, switch, speed


class TestFailOpen(GuardCase):
    def setUp(self):
        super().setUp()
        self.make_main()

    def assertLoudAllow(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stderr.strip().splitlines()
        self.assertEqual(len(lines), 1, r.stderr)
        self.assertTrue(lines[0].startswith("board guard: ") and lines[0].endswith("allowed"), lines[0])

    def test_not_a_pipeline_repo_is_silent(self):
        os.remove(self.repo.path("agent.conf"))
        r = self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertFalse(os.path.exists(self.repo.path("agent_state.txt")))

    def test_no_git_repo_is_silent(self):
        plain = self.repo.make_project("plain")
        r = self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy", cwd=plain)
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_missing_todo_file(self):
        os.remove(self.repo.path("agent_todo.txt"))
        self.assertLoudAllow(self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy"))

    def test_unreadable_todo_file(self):
        self.put_todo("board-trust")
        path = self.repo.path("agent_todo.txt")
        os.chmod(path, 0)
        self.addCleanup(os.chmod, path, 0o644)
        self.assertLoudAllow(self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy"))

    def test_bad_json(self):
        r = self.repo.run("agent-guard.sh", stdin='{"hook_event_name": "PreToolUse", "tool_name": "Agent", ',
                          env={"CLAUDE_PID": str(LIVE), "CLAUDE_CONFIG_DIR": self.cfg})
        self.assertLoudAllow(r)

    def test_python_part_missing(self):
        os.remove(os.path.join(self.repo.plugin_bin, "agent_guard.py"))
        self.assertLoudAllow(self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy"))

    def test_python_part_crashes(self):
        with open(os.path.join(self.repo.plugin_bin, "agent_guard.py"), "w") as fh:
            fh.write("raise SystemExit(7)\n")
        self.assertLoudAllow(self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy"))

    def hold_state_lock(self, seconds):
        """A child holds the flock that agent-file.sh state add / trim take (<git dir>/agent_state.lock)."""
        gd = subprocess.run(["git", "-C", self.repo.dir, "rev-parse", "--absolute-git-dir"],
                            capture_output=True, text=True, check=True).stdout.strip()
        code = ("import fcntl, os, sys, time\n"
                "fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o644)\n"
                "fcntl.flock(fd, fcntl.LOCK_EX)\n"
                "print('held', flush=True)\n"
                "time.sleep(float(sys.argv[2]))\n")
        p = subprocess.Popen([sys.executable, "-c", code, os.path.join(gd, "agent_state.lock"), str(seconds)],
                             stdout=subprocess.PIPE, text=True)
        self.addCleanup(p.wait)
        self.addCleanup(p.kill)
        self.assertEqual(p.stdout.readline().strip(), "held")
        return p

    def test_a_busy_lock_allows_and_writes_nothing(self):
        # review 7: the guard waits on the same flock as state add and trim, at most 2 s
        self.put_todo("board-trust")
        self.hold_state_lock(8)
        t = time.time()
        self.assertLoudAllow(self.pre_agent("board-trust Worker 1: x"))
        self.assertLess(time.time() - t, 4.5)
        self.assertEqual(self.launches(), [])

    def test_a_lock_freed_by_a_dead_holder_is_taken(self):
        self.put_todo("board-trust")
        p = self.hold_state_lock(30)
        p.kill()
        p.wait()
        self.assertAllowed(self.pre_agent("board-trust Worker 1: x"))
        self.assertEqual(len(self.launches()), 1)

    def test_a_leftover_guard_lock_directory_is_ignored(self):
        self.put_todo("board-trust")
        gd = subprocess.run(["git", "-C", self.repo.dir, "rev-parse", "--absolute-git-dir"],
                            capture_output=True, text=True, check=True).stdout.strip()
        os.mkdir(os.path.join(gd, "agent_guard.lock"))
        self.assertAllowed(self.pre_agent("board-trust Worker 1: x"))
        self.assertEqual(len(self.launches()), 1)

    def test_bash_without_orca_never_starts_python(self):
        os.remove(os.path.join(self.repo.plugin_bin, "agent_guard.py"))
        r = self.pre_bash("git status && ls -la")
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_other_tools_and_events_are_ignored(self):
        self.put_todo()
        for p in ({"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "/x"}},
                  {"hook_event_name": "Stop"},
                  {"hook_event_name": "SubagentStop", "agent_id": "unknown", "agent_type": "Explore"}):
            with self.subTest(p=p):
                r = self.hook(p)
                self.assertEqual((r.returncode, r.stderr), (0, ""))


class TestSwitch(GuardCase):
    def setUp(self):
        super().setUp()
        self.make_main()
        self.put_todo("board-trust")

    # owner 3A 2026-11-20 (bounce 3): every repo records only by default; only auto-pipeline blocks (its agent.conf)
    def test_default_is_record(self):
        with open(os.path.join(ROOT, "bin", "agent.conf.default")) as fh:
            self.assertIn("\nboard_guard=record\n", "\n" + fh.read())

    def test_this_repo_is_on(self):
        with open(os.path.join(ROOT, "agent.conf")) as fh:
            self.assertIn("\nboard_guard=on\n", "\n" + fh.read())

    def drop_key(self):
        path = self.repo.path("agent.conf")
        with open(path) as fh:
            lines = [l for l in fh.read().splitlines(True) if not l.startswith("board_guard")]
        with open(path, "w") as fh:
            fh.write("".join(lines))

    def assertRecordsOnly(self):
        for desc, stype in (("old-task Merge", "auto-pipeline:merge-deputy"),
                            ("Find hook payload fields", "general-purpose")):
            r = self.pre_agent(desc, stype)
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([self.fields(l)["task"] for l in self.launches()], ["old-task", "project Manager"])

    def test_a_repo_without_the_key_records_and_never_blocks(self):
        self.drop_key()
        self.assertRecordsOnly()

    def test_an_empty_value_records_and_never_blocks(self):
        self.repo.set_conf("board_guard", "")
        self.assertRecordsOnly()

    def test_an_unreadable_conf_records_and_never_blocks(self):
        path = self.repo.path("agent.conf")
        os.chmod(path, 0)
        self.addCleanup(os.chmod, path, 0o644)
        self.assertRecordsOnly()

    def test_off_records_nothing_blocks_nothing(self):
        self.repo.set_conf("board_guard", "off")
        r = self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertAllowed(self.pre_agent("board-trust Worker 1: x"))
        self.assertEqual(self.launches(), [])

    def test_record_records_and_never_blocks(self):
        self.repo.set_conf("board_guard", "record")
        r = self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.one_launch()["task"], "old-task")

    def test_a_bad_value_records_and_never_blocks(self):
        # bounce 3: only an explicit on blocks
        self.repo.set_conf("board_guard", "maybe")
        self.assertRecordsOnly()

    def test_settings_write_and_refuse(self):
        r = self.repo.run("agent-settings.sh", "board_guard", "off")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("board_guard=off", self.repo.read("agent.conf"))
        for v in ("record", "on"):
            self.assertEqual(self.repo.run("agent-settings.sh", "board_guard", v).returncode, 0)
        before = self.repo.read("agent.conf")
        r = self.repo.run("agent-settings.sh", "board_guard", "maybe")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.repo.read("agent.conf"), before)


# ---------------------------------------------------------------- reviewer findings (step 5, 2026-11-23)


class TestReviewFixes(GuardCase):
    def setUp(self):
        super().setUp()
        self.make_main()
        self.put_todo("state-trim", "board-waiting")

    def test_r1_a_worker_type_without_number_shows_as_a_worker_row(self):
        r = self.pre_agent("state-trim fix the hook", "auto-pipeline:worker")
        self.assertAllowed(r)
        self.assertEqual(self.one_launch()["kind"], "worker")
        self.assertAllowed(self.post_agent(r.tid, "aw1"))
        rows = self.rows(now="2026-11-20 16:52")
        self.assertEqual(self.index(rows, "state-trim 工人"), self.index(rows, "state-trim") + 1)

    def test_r2_a_last_line_without_newline_is_kept_whole(self):
        for stale in (True, False):
            with self.subTest(stale=stale):
                open(self.repo.path("agent_state.txt"), "w").close()
                if stale:  # a stale unlinked record: the guard rewrites the file (prune)
                    self.put_launch("LAUNCH toolu_old: worker 1 | task state-trim | x | since 2026-11-20 16:40 | "
                                    "pid %d | by main" % LIVE)
                with open(self.repo.path("agent_state.txt"), "a") as fh:
                    fh.write("OWNER TODO: call the bank | 2026-11-20 16:40")
                self.assertAllowed(self.pre_agent("state-trim Merge", "auto-pipeline:merge-deputy"))
                lines = self.state_text().splitlines()
                self.assertIn("OWNER TODO: call the bank | 2026-11-20 16:40", lines)
                self.assertEqual(len(self.launches()), 1, lines)
                self.assertTrue(self.state_text().endswith("\n"))

    def test_r4_an_old_pane_of_a_dead_session_is_pruned_a_young_one_kept(self):
        dead = dead_pid()
        old = ("LAUNCH toolu_p1: tm-pane | task state-trim | state-trim Task Manager | since 2026-11-19 10:00 | "
               "pid %d | by main | pane term_old" % dead)
        young = ("LAUNCH toolu_p2: tm-pane | task state-trim | state-trim Task Manager | since 2026-11-20 15:00 | "
                 "pid %d | by main | pane term_young" % dead)
        self.put_launch(old)
        self.put_launch(young)
        self.assertAllowed(self.pre_agent("state-trim Worker 1: x"))
        rows = self.launches()
        self.assertNotIn(old, rows)  # dead session, older than state_keep_hours (24)
        self.assertIn(young, rows)

    def test_r4_orca_down_falls_back_to_the_session_pid(self):
        for key, pid in (("live", LIVE), ("dead", dead_pid())):
            self.put_launch("LAUNCH toolu_%s: shell-pane | task board-waiting | %s | since 2026-11-20 16:40 | pid %d | "
                            "by main | pane term_%s | env pc2" % (key, key, pid, key))
        self.repo.set_orca_env_state("pc2", "down")
        self.assertEqual([r["What"] for r in self.rows(now=NOW) if r["Task"] == "board-waiting 窗格"], ["live"])

    def test_r14_a_cut_orca_list_shows_the_pane(self):
        self.put_launch("LAUNCH toolu_x: shell-pane | task board-waiting | t | since 2026-11-20 16:40 | pid %d | "
                        "by main | pane term_far | env pc2" % LIVE)
        self.repo.set_orca_answer("terminals.json", {"ok": True, "result": {
            "terminals": [{"handle": "term_other"}], "truncated": True, "totalCount": 300}}, env="pc2")
        self.assertIn("board-waiting 窗格", [x["Task"] for x in self.rows(now=NOW)])

    def test_r5_two_foreground_agents_of_one_type_keep_their_ids(self):
        a = self.pre_agent("state-trim Worker 1: slice a", bg=False)
        b = self.pre_agent("state-trim Worker 2: slice b", bg=False)
        self.assertAllowed(self.sub("SubagentStart", "agA"))
        self.assertAllowed(self.sub("SubagentStart", "agB"))
        agents = {self.fields(l)["key"]: self.fields(l).get("agent") for l in self.launches()}
        self.assertEqual(agents, {a.tid: "agA", b.tid: "agB"})
        self.assertAllowed(self.sub("SubagentStop", "agA"))
        self.assertAllowed(self.post_agent(a.tid, "agA", status="completed"))
        self.assertEqual([self.fields(l)["key"] for l in self.launches()], [b.tid])

    def test_r11_an_unknown_launch_status_keeps_the_record(self):
        r = self.pre_agent("state-trim Worker 1: x")
        self.assertAllowed(self.post_agent(r.tid, "ar1", status="remote_launched"))
        self.assertEqual(self.one_launch()["agent"], "ar1")

    def test_r6_every_orca_operation_of_one_command_counts(self):
        cmd = ('orca worktree create --name state-trim --repo path:/r --json && orca terminal create --worktree '
               'path:/w/st --title "state-trim Task Manager" --json')
        self.assertAllowed(self.pre_bash(cmd))
        f = self.one_launch()
        self.assertEqual((f["kind"], f["task"]), ("tm-pane", "state-trim"))
        self.assertBlocked(self.pre_bash(cmd + ' && orca terminal create --title "closed-task Task Manager" --json'),
                           "closed-task")
        self.assertEqual(len(self.launches()), 1)

    def test_r9_a_shell_variable_title_is_unknown_and_allowed(self):
        r = self.pre_bash('name=state-trim; orca terminal create --title "$name Task Manager" --json')
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.pre_bash('orca terminal create --title "`cat name` Task Manager" --json')
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_r9_punctuation_after_the_task_name(self):
        self.assertAllowed(self.pre_agent("state-trim, fix the hook", "general-purpose"))
        self.assertEqual(self.one_launch()["task"], "state-trim")

    def test_r12_a_commit_message_heredoc_is_not_a_launch(self):
        cmd = 'git commit -q -m "$(cat <<\'EOF\'\nboard-trust: the "guard\norca terminal create --title x\nEOF\n)"'
        r = self.pre_bash(cmd)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.launches(), [])

    def test_r13_an_unknown_session_pid_writes_no_record(self):
        r = self.pre_agent("state-trim Worker 1: x", extra_env={"CLAUDE_PID": "unknown"})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.launches(), [])

    def test_r17_the_same_launch_twice_is_one_record(self):
        self.assertAllowed(self.pre_agent("state-trim Worker 1: x", tid="toolu_dup"))
        self.assertAllowed(self.pre_agent("state-trim Worker 1: x", tid="toolu_dup"))
        self.assertEqual(len(self.launches()), 1)

    def test_r18_no_temp_file_is_left_in_the_folder(self):
        self.put_launch("LAUNCH toolu_old: worker 1 | task state-trim | x | since 2026-11-20 16:40 | pid %d | by main"
                        % LIVE)
        self.assertAllowed(self.pre_agent("state-trim Merge", "auto-pipeline:merge-deputy"))
        self.assertEqual([n for n in os.listdir(self.repo.dir) if "agent_state" in n], ["agent_state.txt"])


# ---------------------------------------------------------------- board and status line


class TestStatusLine(BoardOnly):
    def line(self, folder=None):
        folder = folder or self.repo.dir
        stdin = json.dumps({"session_id": "s1", "cwd": folder,
                            "workspace": {"current_dir": folder, "project_dir": folder}})
        r = self.repo.run("agent-statusline.sh", cwd=self.repo.base, stdin=stdin,
                          env={"AGENT_FAKE_NOW": NOW, "CLAUDE_CONFIG_DIR": self.cfg}, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.rstrip("\n")

    def rec(self, n, task="board-waiting", pid=LIVE, kind=None, folder=None):
        kind = kind or "worker %d" % n
        self.put_launch("LAUNCH toolu_%d: %s | task %s | slice %d | since 2026-11-20 16:40 | pid %d | by main | "
                        "type auto-pipeline:worker | agent a%d" % (n, kind, task, n, pid, n), folder=folder)

    def test_count_of_live_subagents_only(self):
        self.put_todo("board-waiting")
        before = self.line()
        self.assertTrue(before.startswith("board-waiting "), before)
        self.rec(1)
        self.rec(2)
        self.rec(3, pid=dead_pid())
        self.rec(4, kind="shell-pane")
        self.assertEqual(self.line(), before + " · 2 代理")

    def test_english_and_one(self):
        self.repo.set_conf("language", "en")
        self.put_todo("board-waiting")
        before = self.line()
        self.rec(1)
        self.assertEqual(self.line(), before + " · 1 agent")
        self.rec(2)
        self.assertEqual(self.line(), before + " · 2 agents")

    def test_count_per_task_line(self):
        # review 8: each task line counts its own records
        self.put_todo("board-waiting", "state-trim")
        pick = lambda text, task: [l for l in text.splitlines() if l.startswith(task + " ")][0]
        before = self.line()
        self.rec(1)
        self.rec(2)
        self.rec(3, task="state-trim")
        after = self.line()
        self.assertEqual(pick(after, "board-waiting"), pick(before, "board-waiting") + " · 2 代理")
        self.assertEqual(pick(after, "state-trim"), pick(before, "state-trim") + " · 1 代理")

    def test_off_shows_no_records(self):
        # review 15: board_guard=off is the rollback: the board and the status line ignore LAUNCH lines
        self.put_todo("board-waiting")
        before = self.line()
        self.rec(1)
        self.repo.set_conf("board_guard", "off")
        self.assertEqual(self.line(), before)
        self.assertNotIn("board-waiting 工人 1", [x["Task"] for x in self.rows(now=NOW)])

    def test_self_view_counts_its_worktree(self):
        self.put_todo("board-waiting")
        wt = self.task_worktree("board-waiting")
        self.worktree_lines((wt, "board-waiting", "working"))
        before = self.line(wt)
        self.rec(1, folder=wt)
        self.assertEqual(self.line(wt), before + " · 1 代理")


class TestBoardEnglish(BoardOnly):
    lang = "en"

    def test_kind_words(self):
        self.put_todo("t")
        words = {"worker 1": "t worker 1", "worker": "t worker", "deputy": "t deputy", "merge": "t merge", "reviewer": "t reviewer",
                 "explore": "t explore", "plan": "t plan", "guide": "t guide", "agent": "t agent",
                 "tm-pane": "t pane", "shell-pane": "t pane", "pane": "t pane"}
        for i, kind in enumerate(words):
            pane = " | pane term_%d" % i if kind.endswith("pane") else ""
            self.put_launch("LAUNCH toolu_%d: %s | task t | x%d | since 2026-11-20 16:40 | pid %d | by main | "
                            "agent a%d%s" % (i, kind, i, LIVE, i, pane))
        self.repo.stub_orca_down()
        tasks = [r["Task"] for r in self.rows()]
        for kind, label in words.items():
            with self.subTest(kind=kind):
                self.assertIn(label, tasks)

    def test_zh_kind_words(self):
        self.repo.set_conf("language", "zh")
        self.lang = "zh"
        self.put_todo("t")
        words = {"worker 1": "t 工人 1", "worker": "t 工人", "deputy": "t 副手", "merge": "t 合并", "reviewer": "t 审查",
                 "explore": "t 探查", "plan": "t 规划", "guide": "t 指南", "agent": "t 代理", "pane": "t 窗格"}
        for i, kind in enumerate(words):
            pane = " | pane term_%d" % i if kind == "pane" else ""
            self.put_launch("LAUNCH toolu_%d: %s | task t | x%d | since 2026-11-20 16:40 | pid %d | by main | "
                            "agent a%d%s" % (i, kind, i, LIVE, i, pane))
        self.repo.stub_orca_down()
        tasks = [r["Task"] for r in self.rows()]
        for kind, label in words.items():
            with self.subTest(kind=kind):
                self.assertIn(label, tasks)

    def test_a_record_with_no_task_row_is_in_the_running_group(self):
        self.put_todo()
        self.put_launch("LAUNCH toolu_1: explore | task project Manager | look | since 2026-11-20 16:40 | pid %d | "
                        "by main | agent a1" % LIVE)
        r = self.row(self.rows(now=NOW), task="project Manager explore")
        self.assertEqual((r["What"], r["Status"], r["Work"]), ("look", "running", "10m"))

    def test_a_broken_launch_line_never_crashes(self):
        self.put_todo("t")
        for line in ("LAUNCH x", "LAUNCH toolu_1: worker | task", "LAUNCH toolu_2: worker 1 | task t | y | since x"
                     " | pid abc | by main", "LAUNCH toolu_3:"):
            self.put_launch(line)
        r = self.af("board")
        self.assertNotIn("Traceback", r.stderr)


# ---------------------------------------------------------------- state trim keeps records


class TestTrimKeeps(BoardOnly):
    def test_launch_lines_survive_a_trim(self):
        line = ("LAUNCH toolu_1: worker 1 | task t | x | since 2026-11-01 10:00 | pid %d | by main | agent a1" % LIVE)
        self.state("header line")
        self.state("")
        self.state("old note | 2026-11-01 10:00")
        self.state(line)
        self.state("later old note | 2026-11-01 11:00")
        r = self.repo.run("agent-file.sh", "state", "trim", env={"AGENT_FAKE_NOW": NOW})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(line, self.state_text())
        self.assertNotIn("later old note", self.state_text())


# ---------------------------------------------------------------- hooks.json, rules text, release


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


GUARD = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-guard.sh'


class TestHooks(unittest.TestCase):
    def entries(self, event):
        hooks = json.loads(read("hooks", "hooks.json"))["hooks"]
        return [e for e in hooks.get(event, []) if "agent-guard.sh" in json.dumps(e)]

    def test_wired_once_per_event(self):
        for event, matcher in (("PreToolUse", "Agent|Task|Bash"), ("PostToolUse", "Agent|Task|Bash"),
                               ("SubagentStart", None), ("SubagentStop", None)):
            with self.subTest(event=event):
                e = self.entries(event)
                self.assertEqual(len(e), 1, e)
                self.assertEqual(e[0].get("matcher"), matcher)
                self.assertEqual(e[0]["hooks"], [{"type": "command", "command": GUARD, "timeout": 5}])

    def test_nowhere_else(self):
        hooks = json.loads(read("hooks", "hooks.json"))["hooks"]
        for event in hooks:
            if event not in ("PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop"):
                self.assertEqual(self.entries(event), [], event)

    def test_scripts_exist_and_run(self):
        self.assertTrue(os.access(os.path.join(ROOT, "bin", "agent-guard.sh"), os.X_OK))
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "bin", "agent_guard.py")))


def section(text, head):
    start = text.index("\n" + head + "\n")
    end = text.find("\n\n", start + len(head) + 2)
    return text[start:end if end > 0 else len(text)]


class TestRuleText(unittest.TestCase):
    def test_w14_launches_record_themselves(self):
        w14 = section(read("PRINCIPLES.md"), "W14. Todo board")
        self.assertIn("agent-guard.sh", w14)
        self.assertIn("no open todo task", w14)
        self.assertIn("board_guard", w14)
        self.assertNotIn("`worker on <n>` / `worker off <n>` for each worker;", w14)

    def test_dispatch_skill(self):
        s = read("skills", "dispatch", "SKILL.md")
        board = s[s.index("## Board records"):s.index("## Time question")]
        self.assertIn("agent-guard.sh", board)
        self.assertIn("todo add", board)
        self.assertNotIn("Record each worker: ${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh worker on", s)

    def test_fast_lane_adds_the_todo_line_first(self):
        # review 16: the guard refuses "<task> Deputy" for a task with no todo line
        s = read("skills", "dispatch", "SKILL.md")
        step2 = [l for l in s.splitlines() if l.startswith("2. Small task")][0]
        self.assertIn("todo add", step2)

    def test_merge_skill_keeps_the_line_open_for_the_launch(self):
        s = read("skills", "merge", "SKILL.md")
        self.assertIn("agent-guard.sh", s)

    def test_readme(self):
        self.assertIn("bin/agent-guard.sh", read("PRINCIPLES.md"))

    def test_the_texts_say_the_default_records_only(self):
        # bounce 3 (owner 3A 2026-11-20): record is the default, only board_guard=on refuses
        line = [l for l in read("PRINCIPLES.md").splitlines() if "bin/agent-guard.sh" in l][0]
        self.assertIn("board_guard=on", line)
        self.assertRegex(line, r"default.{0,30}record|record.{0,30}default")
        w14 = section(read("PRINCIPLES.md"), "W14. Todo board")
        self.assertRegex(w14, r"default.{0,30}record|record.{0,30}default")
        s = read("skills", "dispatch", "SKILL.md")
        board = s[s.index("## Board records"):s.index("## Time question")]
        self.assertIn("board_guard=on", board)
        self.assertIn("board_guard=on", read("skills", "merge", "SKILL.md"))

    def test_release(self):
        v = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        self.assertRegex(v, r"^\d+\.\d+\.\d+$")
        self.assertGreaterEqual(tuple(map(int, v.split("."))), (0, 39, 0))

    def test_settings_hint(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        try:
            import agent_conf
        finally:
            sys.path.pop(0)
        self.assertIn("board_guard", agent_conf.HINTS)
        self.assertIsNone(agent_conf.validate_value("board_guard", "record"))
        self.assertIsNotNone(agent_conf.validate_value("board_guard", "maybe"))


if __name__ == "__main__":
    unittest.main()
