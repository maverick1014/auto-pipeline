"""Tests of agent-guard, one class per feature."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import unittest  # noqa: E402
import test_agent_board as tb  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))


ROOT = os.path.dirname(HERE)


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

    def put_unstarted(self, *names):
        """Todo lines with no stage: a live agent or pane under one makes the task running (board-one-row)."""
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("".join(todo(n, stage=False) + "\n" for n in names))

    def status_of(self, rows, task):
        """The Status cell of the task's row (an agent or pane under it shows there, never as a row: board-one-row)."""
        return rows[self.index(rows, task)]["Status"]

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


    def sync_cfg(self):
        """settings-configure: the hook and the status line run with CLAUDE_CONFIG_DIR=self.cfg;
        the Configure values set_conf wrote (repo.claude_dir()) go there too."""
        src = os.path.join(self.repo.claude_dir(), "settings.json")
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(self.cfg, "settings.json"))

    # ---- the hook

    def hook(self, payload, role=None, pid=LIVE, now=NOW, cwd=None, extra_env=None):
        cwd = cwd or self.repo.dir
        payload = dict({"session_id": "s1", "transcript_path": os.path.join(self.cfg, "t.jsonl"), "cwd": cwd,
                        "permission_mode": "bypassPermissions"}, **payload)
        self.sync_cfg()
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


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


GUARD = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-guard.sh'


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
        self.assertNotIn("state-trim 合并", [x["Task"] for x in rows])      # board-one-row: no row of its own
        self.assertTrue(self.status_of(rows, "state-trim").endswith(" · 1 代理"), rows)
        self.assertAllowed(self.sub("SubagentStop", "a038d8ee18e4ea335", "auto-pipeline:merge-deputy"))
        self.assertEqual(self.launches(), [])
        self.assertNotIn("代理", self.status_of(self.rows(), "state-trim"))

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
        self.put_unstarted("board-waiting")
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
        # board-one-row: a live pane alone makes its task running, no count, no row of its own
        self.assertNotIn("board-waiting 窗格", [x["Task"] for x in rows])
        self.assertEqual(self.status_of(rows, "board-waiting"), "进行中")
        close = "orca terminal close --terminal term_bc68aaf3-5722-4519-b334-5b19d9d2661e --environment pc2 --json"
        c = self.pre_bash(close)
        self.assertAllowed(c)
        self.assertAllowed(self.post_bash(close, c.tid, '{"ok":true}'))
        self.assertEqual(self.launches(), [])

    def test_8_pane_gone_from_orca_list_is_not_shown_orca_down_is_shown(self):
        self.put_unstarted("board-waiting")
        self.put_launch("LAUNCH toolu_x: shell-pane | task board-waiting | %s | since 2026-11-20 16:40 | pid %d | "
                        "by main | pane term_gone | env pc2 | worktree /w/board-waiting" % (SHELL_TITLE, LIVE))
        self.repo.set_orca_answer("terminals.json", {"ok": True, "result": {"terminals": [{"handle": "term_other"}]}},
                                  env="pc2")
        # board-one-row: a pane that is shown makes its task running; one gone from the list leaves it not started
        self.assertTrue(self.status_of(self.rows(), "board-waiting").startswith("未开始"))
        self.repo.set_orca_env_state("pc2", "down")
        self.assertEqual(self.status_of(self.rows(), "board-waiting"), "进行中")

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
        self.assertNotIn("代理", self.status_of(self.rows(now=NOW), "state-trim"))
        self.assertTrue(self.status_of(self.rows(now="2026-11-20 16:48"), "state-trim").endswith(" · 1 代理"))

    def test_17_subagent_start_links_a_foreground_launch(self):
        r = self.pre_agent("state-trim Worker 1: trim engine", bg=False)
        self.assertAllowed(self.sub("SubagentStart", "afg1", "auto-pipeline:worker"))
        self.assertEqual(self.one_launch()["agent"], "afg1")
        self.assertTrue(self.status_of(self.rows(now="2026-11-20 16:59"), "state-trim").endswith(" · 1 代理"))
        self.assertAllowed(self.post_agent(r.tid, "afg1", status="completed"))
        self.assertEqual(self.launches(), [])

    def test_18_hand_worker_line_and_record_give_one_row(self):
        wt = self.task_worktree("state-trim")
        self.worktree_lines((wt, "state-trim", "working"))
        self.af("worker", "on", "1", "trim engine", cwd=wt, now="2026-11-20 16:40")
        self.put_launch("LAUNCH toolu_w: worker 1 | task state-trim | trim engine | since 2026-11-20 16:40 | "
                        "pid %d | by tm | type auto-pipeline:worker | agent a1" % LIVE, folder=wt)
        rows = self.rows()
        tasks = [x["Task"] for x in rows]
        # board-one-row: the hand line goes, the record adds no row; the task's row counts the one worker
        self.assertEqual(tasks.count("state-trim 工人 1"), 0, tasks)
        self.assertTrue(self.status_of(rows, "state-trim").endswith(" · 1 代理"), rows)

    def test_title_has_no_field_break(self):
        self.assertAllowed(self.pre_agent("state-trim Worker 3: a | b\nc"))
        self.assertEqual(self.one_launch()["title"], "a / b c")

    def test_run_in_background_as_a_string(self):
        self.assertAllowed(self.pre_agent("state-trim Worker 1: x", bg="true"))
        self.assertEqual(len(self.launches()), 1)


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
                # board-one-row: no row of its own; the task's row carries the count
                self.assertEqual([r["Task"] for r in rows].count("board-waiting 工人 1"), 0, rows)
                self.assertTrue(rows[self.index(rows, "board-waiting")]["Status"].endswith(" · 1 代理"), rows)

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
        os.remove(self.repo.path("agent_todo.txt"))   # settings-configure: the set-up mark
        r = self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertFalse(os.path.exists(self.repo.path("agent_state.txt")))

    def test_no_git_repo_is_silent(self):
        plain = self.repo.make_project("plain")
        r = self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy", cwd=plain)
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_missing_todo_file(self):
        # settings-configure: no agent_todo.txt = not a set-up repo, so silent (was a loud allow)
        os.remove(self.repo.path("agent_todo.txt"))
        r = self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy")
        self.assertEqual((r.returncode, r.stderr), (0, ""))

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

    def assertRecordsOnly(self):
        for desc, stype in (("old-task Merge", "auto-pipeline:merge-deputy"),
                            ("Find hook payload fields", "general-purpose")):
            r = self.pre_agent(desc, stype)
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([self.fields(l)["task"] for l in self.launches()], ["old-task", "project Manager"])

    # settings-configure (owner 2026-11-25): "Todo before agent (on = old board_guard)", user level
    def test_the_default_is_on(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import agent_conf
        self.assertIs(agent_conf.get("todo_before_agent", {"HOME": self.repo.base}), True)

    def test_nothing_set_refuses_a_launch_naming_no_open_task(self):
        self.assertBlocked(self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy"))

    def test_on_refuses(self):
        self.repo.set_conf("todo_before_agent", True)
        self.assertBlocked(self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy"))
        self.assertAllowed(self.pre_agent("board-trust Worker 1: x"))

    def test_off_records_and_never_blocks(self):
        self.repo.set_conf("todo_before_agent", False)
        self.assertRecordsOnly()

    def test_off_stored_as_text_records_and_never_blocks(self):
        self.repo.set_conf("todo_before_agent", "false")
        self.assertRecordsOnly()

    def test_a_bad_value_falls_back_to_the_default_on(self):
        self.repo._settings(lambda o: o.__setitem__("todo_before_agent", "maybe"))
        self.assertBlocked(self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy"))

    def test_an_old_agent_conf_board_guard_is_not_read(self):
        self.repo.set_old_conf("board_guard=record\n")
        self.assertBlocked(self.pre_agent("old-task Merge", "auto-pipeline:merge-deputy"))

    def test_settings_script_never_changes_it(self):
        r = self.repo.run("agent-settings.sh", "todo_before_agent", "false")
        self.assertEqual(r.returncode, 1)


# md-slim-principles C 9, C 10: the hook that already runs at the moment adds one
# short pointer line to the agent's context (PreToolUse additionalContext JSON on
# stdout, exit 0), at most once per session and moment. A pointer is never a gate:
# what was allowed stays allowed, what was refused stays refused.
POINT_DISPATCH = ("Dispatch: route it by rules/routing.md (W9); its blocks (--checks) by rules/checks.md (R8). "
                  "The hook only points.")
POINT_MERGE = ("Merge: the gate by rules/checks.md (R8); the merge and the cleanup by rules/worktrees.md (W8). "
               "The hook only points.")
POINT_PUSH = "Push: a push that is denied: rules/traps.md (W16). The hook only points."


class TestMomentPointers(GuardCase):

    def context(self, r):
        self.assertAllowed(r)
        if not r.stdout.strip():
            return None
        data = json.loads(r.stdout)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertNotIn("permissionDecision", data["hookSpecificOutput"])
        return data["hookSpecificOutput"]["additionalContext"]

    def test_a_todo_add_points_to_routing(self):
        self.make_main()
        r = self.pre_bash('"/p/bin/agent-file.sh" todo add "t" small "x" 10 --checks "PR REVIEW"')
        self.assertEqual(self.context(r), POINT_DISPATCH)

    def test_once_per_session_and_moment(self):
        self.make_main()
        self.assertEqual(self.context(self.pre_bash("bin/agent-file.sh todo add a small x 5")), POINT_DISPATCH)
        self.assertIsNone(self.context(self.pre_bash("bin/agent-file.sh todo add b small x 5")))
        # another session: again
        r = self.hook({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "s2",
                       "tool_input": {"command": "bin/agent-file.sh todo add c small x 5", "description": "x"},
                       "tool_use_id": self.tid()})
        self.assertEqual(self.context(r), POINT_DISPATCH)

    def test_a_deputy_launch_points_to_routing(self):
        self.make_main()
        self.put_todo("t")
        r = self.pre_agent("t Deputy", stype="auto-pipeline:fast-lane-deputy")
        self.assertEqual(self.context(r), POINT_DISPATCH)

    def test_a_merge_deputy_launch_points_to_the_gate_and_cleanup(self):
        self.make_main()
        self.put_todo("t")
        r = self.pre_agent("t Merge", stype="auto-pipeline:merge-deputy")
        self.assertEqual(self.context(r), POINT_MERGE)

    def test_a_gate_call_points_to_the_gate_and_cleanup(self):
        self.make_main()
        r = self.pre_bash('bin/agent-file.sh checks gate "t" --dir /x --branch b')
        self.assertEqual(self.context(r), POINT_MERGE)

    def test_the_two_moments_are_counted_apart(self):
        self.make_main()
        self.assertEqual(self.context(self.pre_bash("bin/agent-file.sh todo add a small x 5")), POINT_DISPATCH)
        self.assertEqual(self.context(self.pre_bash("bin/agent-file.sh checks gate a --dir /x")), POINT_MERGE)

    def test_a_push_points_to_the_traps(self):
        for role in (None, "task-manager"):
            with self.subTest(role=role):
                sid = "s-push-%s" % role
                r = self.hook({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": sid,
                               "tool_input": {"command": "git push origin feat", "description": "x"},
                               "tool_use_id": self.tid()}, role=role)
                self.assertEqual(self.context(r), POINT_PUSH)

    def test_a_worker_launch_or_a_plain_command_gets_nothing(self):
        self.make_main()
        self.put_todo("t")
        self.assertIsNone(self.context(self.pre_agent("t Worker 1: slice", stype="auto-pipeline:worker")))
        self.assertIsNone(self.context(self.pre_bash("ls -la")))
        self.assertIsNone(self.context(self.pre_bash("git status")))

    def test_a_refused_launch_stays_refused(self):
        self.make_main()
        r = self.pre_agent("nope Deputy", stype="auto-pipeline:fast-lane-deputy")
        self.assertEqual(r.returncode, 2, r.stderr)

    def test_never_after_the_call(self):
        self.make_main()
        tid = self.tid()
        r = self.post_bash("bin/agent-file.sh todo add a small x 5", tid)
        self.assertAllowed(r)
        self.assertNotIn("additionalContext", r.stdout)


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
        self.assertNotIn("state-trim 工人", [x["Task"] for x in rows])     # board-one-row: counted on its task's row
        self.assertTrue(self.status_of(rows, "state-trim").endswith(" · 1 代理"), rows)

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
        self.put_unstarted("board-waiting")
        self.repo.set_orca_env_state("pc2", "down")
        for key, pid, running in (("dead", dead_pid(), False), ("live", LIVE, True)):
            self.put_launch("LAUNCH toolu_%s: shell-pane | task board-waiting | %s | since 2026-11-20 16:40 | pid %d | "
                            "by main | pane term_%s | env pc2" % (key, key, pid, key))
            # board-one-row: a pane that shows makes its task running; a dead session's pane does not
            status = self.status_of(self.rows(now=NOW), "board-waiting")
            self.assertEqual(status == "进行中", running, (key, status))

    def test_r14_a_cut_orca_list_shows_the_pane(self):
        self.put_unstarted("board-waiting")
        self.put_launch("LAUNCH toolu_x: shell-pane | task board-waiting | t | since 2026-11-20 16:40 | pid %d | "
                        "by main | pane term_far | env pc2" % LIVE)
        self.repo.set_orca_answer("terminals.json", {"ok": True, "result": {
            "terminals": [{"handle": "term_other"}], "truncated": True, "totalCount": 300}}, env="pc2")
        self.assertEqual(self.status_of(self.rows(now=NOW), "board-waiting"), "进行中")   # board-one-row

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

    def test_stale_a_worktree_subagent_stop_removes_the_record_of_the_launching_folder(self):
        r = self.pre_agent("state-trim Worker 1: slice a")
        self.assertAllowed(self.post_agent(r.tid, "agWT"))
        wt = os.path.join(self.cfg, "wt")
        subprocess.run(["git", "-C", self.repo.dir, "worktree", "add", "-q", "-b", "wt-b", wt], check=True)
        self.assertAllowed(self.sub("SubagentStart", "agWT", cwd=wt))
        self.assertEqual(self.one_launch()["agent"], "agWT")
        self.assertAllowed(self.sub("SubagentStop", "agWT", cwd=wt))
        self.assertEqual(self.launches(), [])

    def test_stale_a_worktree_subagent_start_links_the_record_of_the_launching_folder(self):
        r = self.pre_agent("state-trim Worker 1: slice a", bg=False)
        wt = os.path.join(self.cfg, "wt")
        subprocess.run(["git", "-C", self.repo.dir, "worktree", "add", "-q", "-b", "wt-b", wt], check=True)
        self.assertAllowed(self.sub("SubagentStart", "agWT", cwd=wt))
        self.assertEqual(self.one_launch()["agent"], "agWT")

    def test_stale_a_record_of_a_finished_task_is_not_shown(self):
        self.put_launch("LAUNCH toolu_old: deputy | task old-one | old | since 2026-11-20 16:00 | pid %d | by main | "
                        "type auto-pipeline:fast-lane-deputy | agent agOLD" % LIVE)
        self.put_launch("LAUNCH toolu_new: deputy | task state-trim | new | since 2026-11-20 16:00 | pid %d | by main | "
                        "type auto-pipeline:fast-lane-deputy | agent agNEW" % LIVE)
        with open(self.repo.path("agent_completed.txt"), "a") as fh:
            fh.write("2026-11-20 | old-one | x | est 10m actual 10m\n2026-11-19 | state-trim | x | est 10m actual 10m\n")
        rows = self.rows(now=NOW)
        self.assertNotIn("old-one 副手", [x["Task"] for x in rows])
        # a reopened name (open in agent_todo.txt) stays shown: counted on its task's row (board-one-row)
        self.assertTrue(self.status_of(rows, "state-trim").endswith(" · 1 代理"), rows)

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


class TestStatusLine(BoardOnly):
    def line(self, folder=None):
        folder = folder or self.repo.dir
        stdin = json.dumps({"session_id": "s1", "cwd": folder,
                            "workspace": {"current_dir": folder, "project_dir": folder}})
        self.sync_cfg()
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
        self.put_todo()      # board-one-row: only an agent of a task with no todo row keeps its own row, named by its kind word
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
        self.put_todo()      # no todo row: the kind words label the agents' own rows
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


class TestHooks(unittest.TestCase):
    def entries(self, event):
        hooks = json.loads(read("hooks", "hooks.json"))["hooks"]
        return [e for e in hooks.get(event, []) if "agent-guard.sh" in json.dumps(e)]

    def test_wired_once_per_event(self):
        for event, matcher in (("PreToolUse", "Agent|Task|Bash|SendMessage"), ("PostToolUse", "Agent|Task|Bash"),
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


TITLE = "one-watcher Task Manager"


PANE = "term_bc68aaf3-5722-4519-b334-5b19d9d2661e"


W = "/Users/maverick/orca/workspaces/auto-pipeline/one-watcher"


def create(opt="path:$W"):
    return 'orca terminal create --environment pc2 --worktree %s --title "%s" --command "zsh" --json' % (opt, TITLE)


class VarPath(GuardCase):
    def setUp(self):
        super().setUp()
        self.put_todo("one-watcher")

    def launch(self, cmd, stdout=None):
        r = self.pre_bash(cmd)
        self.assertAllowed(r)
        if stdout is not None:
            self.assertAllowed(self.post_bash(cmd, r.tid, stdout))
        rows = self.launches()
        self.assertEqual(len(rows), 1, rows)
        self.assertNotIn("$", rows[0])
        return rows[0]

    def test_a_assignment_earlier(self):
        row = self.launch("W=%s\n%s" % (W, create()))
        self.assertEqual(self.fields(row)["worktree"], W)

    def test_a_export_and_quotes(self):
        row = self.launch("export W='%s'; %s" % (W, create()))
        self.assertEqual(self.fields(row)["worktree"], W)
        self.assertEqual(self.fields(row)["env"], "pc2")

    def test_b_braces(self):
        row = self.launch('W="%s"\n%s' % (W, create("path:${W}")))
        self.assertEqual(self.fields(row)["worktree"], W)

    def test_c_from_response_worktree_id(self):
        out = json.dumps({"result": {"terminal": {"handle": PANE, "worktreeId": "repo-1::" + W}}})
        row = self.launch(create(), out)
        f = self.fields(row)
        self.assertEqual((f["worktree"], f["pane"]), (W, PANE))

    def test_c_from_response_path(self):
        out = json.dumps({"result": {"handle": PANE, "worktree": {"path": W}}})
        row = self.launch(create(), out)
        self.assertEqual(self.fields(row)["worktree"], W)

    def test_d_no_path_anywhere(self):
        out = '"handle": "%s"' % PANE
        row = self.launch(create() + " 2>&1 | grep -o '\"handle\": \"[^\"]*\"'", out)
        f = self.fields(row)
        self.assertNotIn("worktree", f)
        self.assertEqual(f["pane"], PANE)

    def test_e_command_substitution_not_expanded(self):
        row = self.launch("W=$(pwd)\n" + create())
        self.assertNotIn("worktree", self.fields(row))

    def test_e_quoted_substitution_not_expanded(self):
        row = self.launch('W="$(pwd)"\n' + create())
        self.assertNotIn("worktree", self.fields(row))

    def test_f_rm_with_assignment_removes(self):
        self.put_launch("LAUNCH toolu_x: tm-pane | task one-watcher | %s | since 2026-11-20 16:40 | pid %d | by main "
                        "| pane term_a | worktree %s" % (TITLE, LIVE, W))
        rm = "W=%s\norca worktree rm --worktree path:$W --json" % W
        r = self.pre_bash(rm)
        self.assertAllowed(r)
        self.assertAllowed(self.post_bash(rm, r.tid, '{"ok":true}'))
        self.assertEqual(self.launches(), [])

    def test_f_rm_without_assignment_removes_nothing(self):
        self.put_launch("LAUNCH toolu_x: tm-pane | task one-watcher | %s | since 2026-11-20 16:40 | pid %d | by main "
                        "| pane term_a | worktree %s" % (TITLE, LIVE, W))
        rm = "orca worktree rm --worktree path:$W --json"
        r = self.pre_bash(rm)
        self.assertAllowed(r)
        self.assertAllowed(self.post_bash(rm, r.tid, '{"ok":true}'))
        self.assertEqual(len(self.launches()), 1)


class TestF2TheGuardWritesTheRecord(GuardCase):
    def records(self):
        gd = subprocess.run(["git", "-C", self.repo.dir, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True, check=True).stdout.strip()
        path = os.path.join(gd, "agent_launches.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def test_a_fast_lane_deputy_launched_by_the_main_manager(self):
        # gate-self-check rule 3: the gate reads this record to know a task is fast lane
        self.make_main()
        self.put_todo("t")
        self.pre_agent("t Deputy", stype="auto-pipeline:fast-lane-deputy")
        recs = [r for r in self.records() if r.get("task") == "t"]
        self.assertEqual([(r["type"], r["by"]) for r in recs], [("fast-lane-deputy", "main")])

    def test_a_reviewer_launched_by_the_main_manager(self):
        self.make_main()
        self.put_todo("t")
        self.pre_agent("t Review", stype="auto-pipeline:reviewer")
        recs = [r for r in self.records() if r.get("task") == "t"]
        self.assertEqual([(r["type"], r["by"]) for r in recs], [("reviewer", "main")])

    def test_a_check_deputy_launched_by_a_task_manager_is_not_the_main_managers(self):
        self.put_todo("t")
        self.pre_agent("t Check", stype="auto-pipeline:check-deputy", role="task-manager")
        recs = [r for r in self.records() if r.get("task") == "t"]
        self.assertTrue(recs)
        self.assertNotEqual(recs[-1]["by"], "main")


class TestGuardDropsAClosedPane(GuardCase):

    def test_agent_runtime_close_drops_the_record(self):
        self.put_todo("board-waiting")
        self.put_launch("LAUNCH toolu_x: tm-pane | task board-waiting | board-waiting Task Manager | since "
                        "2026-11-20 16:40 | pid %d | by main | pane term_a | worktree /w/board-waiting" % LIVE)
        self.put_launch("LAUNCH toolu_y: tm-pane | task other | other Task Manager | since "
                        "2026-11-20 16:40 | pid %d | by main | pane term_b | worktree /w/other" % LIVE)
        for cmd in ('"/p/bin/agent-runtime.sh" close term_a', "/p/bin/agent-runtime.sh close term_a"):
            with self.subTest(cmd=cmd):
                r = self.pre_bash(cmd)
                self.assertAllowed(r)
                self.assertAllowed(self.post_bash(cmd, r.tid, ""))
                self.assertEqual([l.split(":")[0] for l in self.launches()], ["LAUNCH toolu_y"])
                self.put_launch("LAUNCH toolu_x: tm-pane | task board-waiting | board-waiting Task Manager | "
                                "since 2026-11-20 16:40 | pid %d | by main | pane term_a | worktree "
                                "/w/board-waiting" % LIVE)
