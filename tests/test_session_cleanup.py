"""session-cleanup, the script side: a session leaves nothing behind when it ends
(requirements/session-cleanup.md, rules 1, 2, 6; the city side: tests/test_session_cleanup_city.py).
Written by the task manager first.

CONTRACT

agent-file.sh session-end <sid>
    <sid>: letters, digits, "_" and "-" only, else refused (exit 1, one line on stderr, nothing removed).
    Removes, in the project's shared git dir, every file of that session:
        agent_started_<sid> agent_rules_<sid> agent_compact_<sid> agent_quiz_<sid> agent_stale_<sid>
        agent_autoclear_<sid> agent_helper_task_<sid> agent_helper_title_<sid> agent_point_<sid>_*
    and every human-direct line of agent_worktree.txt whose field "session <sid>" names it. Every other
    file and line stays as it was (byte for byte, in its order). Nothing found: exit 0.
agent-file.sh session-end --dead
    Every human-direct line with "pid <n>" and "host <this machine>" (AGENT_FAKE_HOST, else hostname -s)
    whose process <n> is gone: the line goes, and the files of its session (as session-end <sid>; a
    line with "session -" only loses the line). It prints one line per line it removed:
        human-direct line <path> (pid <n> gone)
    A live pid, another host, or an old line with no pid field: kept. --dead --dry-run prints the
    same lines and changes nothing.

The human-direct line a Helper's start writes (and helper-task adds when there is none):
    <path> | task manager, human-direct | task: <task> | since <YYYY-MM-DD HH:MM> | pid <pid> | host <host> | session <sid>
    pid: the session's pid (agent_pid), host: this machine, sid: the hook's session_id, else
    $CLAUDE_CODE_SESSION_ID; "-" when unknown. helper-task changes field 3 only.

bin/agent-session-end.sh  the SessionEnd hook (hooks/hooks.json, next to the city's entry)
    stdin {"session_id", "cwd", ...} -> agent-file.sh session-end <sid> for the repo of cwd. Prints
    nothing, nothing on stderr, exit 0 always: bad stdin, a bad sid, a repo not set up -> nothing.

Housekeep (--apply) and the start of a main manager run session-end --dead; housekeep writes each line
as "removed: <line>" ("would remove: <line>" without --apply) in its HOUSEKEEP block.

The interior designer's start (AGENT_ROLE=interior-designer), rule 6: the start entry prints ONE line,
starting "ROLE: interior designer" and naming agents/interior-designer.md; no QUIZ line, no READ NOW
line, no RULES line. The --rules entry prints nothing. No file in the git dir (no dedupe marker, no
compact count, no auto clear), no pane measuring (agent-room.sh is never called). Startup, compact and
a run by hand all give the same one line.
"""

import json
import os
import re
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase  # noqa: E402
import test_agent_housekeep as th  # noqa: E402  (the module only: its tests stay in their own module)

HOST = "pc-test"
SID = "5e55-end-1"
OTHER = "0th3r-sid-2"
MARKERS = ["agent_started_%s", "agent_rules_%s", "agent_compact_%s", "agent_quiz_%s", "agent_stale_%s",
           "agent_autoclear_%s", "agent_helper_task_%s", "agent_helper_title_%s", "agent_point_%s_watch",
           "agent_point_%s_merge"]
KEEP = ["agent_main.lock", "agent_test_weights.json", "agent_watch.json"]


def dead_pid():
    """A pid that ran and is gone."""
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


def helper_line(path, sid=SID, pid=None, host=HOST, task="(ask the human)"):
    line = "%s | task manager, human-direct | task: %s | since 2026-11-27 09:00" % (path, task)
    if pid is not None:
        line += " | pid %s | host %s | session %s" % (pid, host, sid)
    return line


class EndCase(ScriptCase):
    def setUp(self):
        super().setUp()
        self.gitdir = self.repo.path(".git")
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
                p.wait()
        super().tearDown()

    def live_pid(self):
        proc = subprocess.Popen(["sleep", "120"])
        self.procs.append(proc)
        return proc.pid

    def make_markers(self, sid):
        for pattern in MARKERS:
            with open(os.path.join(self.gitdir, pattern % sid), "w") as fh:
                fh.write("x\n")

    def make_keep(self):
        for name in KEEP:
            with open(os.path.join(self.gitdir, name), "w") as fh:
                fh.write("keep\n")

    def present(self, sid):
        return sorted(p % sid for p in MARKERS if os.path.exists(os.path.join(self.gitdir, p % sid)))

    def set_lines(self, lines):
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def lines(self):
        return [l for l in (self.repo.read("agent_worktree.txt") or "").splitlines() if l.strip()]

    def end(self, *args, env=None):
        full = {"AGENT_FAKE_HOST": HOST}
        full.update(env or {})
        return self.repo.run("agent-file.sh", "session-end", *args, env=full)

    def hook(self, payload, env=None, cwd=None):
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        full = {"AGENT_FAKE_HOST": HOST}
        full.update(env or {})
        return self.repo.run("agent-session-end.sh", env=full, stdin=stdin, cwd=cwd)


class TestSessionEndCommand(EndCase):
    def test_every_file_of_the_session_goes(self):
        self.make_markers(SID)
        self.make_markers(OTHER)
        self.make_keep()
        self.assertOk(self.end(SID))
        self.assertEqual(self.present(SID), [])
        self.assertEqual(len(self.present(OTHER)), len(MARKERS), "another session's files stay")
        for name in KEEP:
            self.assertTrue(os.path.exists(os.path.join(self.gitdir, name)), name)

    def test_its_human_direct_line_goes_and_nothing_else(self):
        mine = helper_line(self.repo.dir, SID, pid=4242)
        twin = helper_line(self.repo.dir, OTHER, pid=4343, task="Other Work")
        task = "/x/wt | some-task | working | since 2026-11-27 08:00 | pane term_a-1 | session %s" % SID
        self.set_lines([twin, mine, task])
        self.assertOk(self.end(SID))
        self.assertEqual(self.lines(), [twin, task], "only the Helper line of that session")

    def test_nothing_to_remove_is_fine(self):
        self.set_lines([helper_line(self.repo.dir, OTHER, pid=4343)])
        self.assertOk(self.end(SID))
        self.assertEqual(len(self.lines()), 1)

    def test_a_bad_session_id_is_refused(self):
        self.make_markers(SID)
        self.set_lines([helper_line(self.repo.dir, SID, pid=4242)])
        for bad in ("", "*", "../x", "a b", "a|b", SID[:3] + "*"):
            with self.subTest(sid=bad):
                result = self.end(bad)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertTrue(result.stderr.strip(), "a refusal says why")
                self.assertEqual(len(self.present(SID)), len(MARKERS))
                self.assertEqual(len(self.lines()), 1)

    def test_listed_in_the_usage(self):
        self.assertIn("session-end", self.repo.run("agent-file.sh").stdout)


class TestSessionEndDead(EndCase):
    def test_a_gone_helper_goes_a_live_one_stays(self):
        gone, live = dead_pid(), self.live_pid()
        dead_line = helper_line(self.repo.dir, SID, pid=gone)
        live_line = helper_line(self.repo.dir, OTHER, pid=live, task="Live Work")
        self.set_lines([dead_line, live_line])
        self.make_markers(SID)
        self.make_markers(OTHER)
        out = self.assertOk(self.end("--dead"))
        self.assertEqual(self.lines(), [live_line])
        self.assertEqual(self.present(SID), [])
        self.assertEqual(len(self.present(OTHER)), len(MARKERS))
        self.assertIn("human-direct line %s (pid %d gone)" % (self.repo.dir, gone), out)

    def test_another_host_and_an_old_line_stay(self):
        far = helper_line("/far/wt", SID, pid=dead_pid(), host="other-pc")
        old = helper_line("/old/wt", SID)          # written before this task: no pid field
        self.set_lines([far, old])
        self.assertOk(self.end("--dead"))
        self.assertEqual(self.lines(), [far, old])

    def test_no_session_id_only_the_line_goes(self):
        gone = dead_pid()
        self.set_lines([helper_line(self.repo.dir, "-", pid=gone)])
        self.make_markers(SID)
        self.assertOk(self.end("--dead"))
        self.assertEqual(self.lines(), [])
        self.assertEqual(len(self.present(SID)), len(MARKERS))

    def test_dry_run_changes_nothing(self):
        gone = dead_pid()
        line = helper_line(self.repo.dir, SID, pid=gone)
        self.set_lines([line])
        self.make_markers(SID)
        out = self.assertOk(self.end("--dead", "--dry-run"))
        self.assertIn("human-direct line %s (pid %d gone)" % (self.repo.dir, gone), out)
        self.assertEqual(self.lines(), [line])
        self.assertEqual(len(self.present(SID)), len(MARKERS))


class TestSessionEndHook(EndCase):
    script = "agent-session-end.sh"

    def payload(self, sid=SID, cwd=None):
        return {"session_id": sid, "transcript_path": "/tmp/x.jsonl", "cwd": cwd or self.repo.dir,
                "hook_event_name": "SessionEnd", "reason": "prompt_input_exit"}

    def test_the_hook_cleans_the_session(self):
        self.make_markers(SID)
        self.make_markers(OTHER)
        self.set_lines([helper_line(self.repo.dir, SID, pid=4242)])
        result = self.hook(self.payload())
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertEqual(self.present(SID), [])
        self.assertEqual(self.lines(), [])
        self.assertEqual(len(self.present(OTHER)), len(MARKERS))

    def test_from_a_folder_inside_the_repo(self):
        sub = self.repo.path("src")
        os.makedirs(sub)
        self.make_markers(SID)
        result = self.hook(self.payload(cwd=sub), cwd=sub)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.present(SID), [])

    def test_bad_input_does_nothing(self):
        self.make_markers(SID)
        for stdin in ("", "not json", json.dumps([1]), json.dumps(self.payload(sid="*")),
                      json.dumps(self.payload(sid=""))):
            with self.subTest(stdin=stdin):
                result = self.hook(stdin)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
                self.assertEqual(len(self.present(SID)), len(MARKERS))

    def test_a_repo_not_set_up_is_left_alone(self):
        os.remove(self.repo.path("agent_todo.txt"))
        self.make_markers(SID)
        result = self.hook(self.payload())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.present(SID)), len(MARKERS))

    def test_registered_for_session_end(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as fh:
            entries = json.load(fh)["hooks"]["SessionEnd"]
        commands = [h["command"] for e in entries for h in e["hooks"]]
        mine = [c for c in commands if "agent-session-end.sh" in c]
        self.assertEqual(len(mine), 1, commands)
        self.assertEqual(mine[0], '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-session-end.sh')
        self.assertTrue([c for c in commands if "agent-city-hook.sh" in c], "the city's entry stays")
        timeouts = [h.get("timeout") for e in entries for h in e["hooks"] if "agent-session-end.sh" in h["command"]]
        self.assertTrue(isinstance(timeouts[0], int) and 0 < timeouts[0] <= 10, timeouts)


class SeatCase(EndCase):
    """A second session (a Helper): the lock is held by another live process."""

    def hold_lock(self):
        with open(os.path.join(self.gitdir, "agent_main.lock"), "w") as fh:
            fh.write("%d 2026-11-27 08:00 mm-1 -\n" % self.live_pid())

    def start(self, pid, sid, source="startup", env=None):
        full = {"CLAUDE_PID": str(pid), "AGENT_FAKE_HOST": HOST}
        full.update(env or {})
        stdin = json.dumps({"session_id": sid, "transcript_path": "/tmp/x.jsonl", "cwd": self.repo.dir,
                            "hook_event_name": "SessionStart", "source": source})
        return self.repo.run("agent-start.sh", env=full, stdin=stdin)


class TestHelperLine(SeatCase):
    def test_the_start_writes_pid_host_and_session(self):
        self.hold_lock()
        self.assertOk(self.start(5151, SID))
        mine = [l for l in self.lines() if "human-direct" in l]
        self.assertEqual(len(mine), 1, self.lines())
        self.assertRegex(mine[0], r"^%s \| task manager, human-direct \| task: \(ask the human\) \| since "
                                  r"\d{4}-\d\d-\d\d \d\d:\d\d \| pid 5151 \| host %s \| session %s$"
                         % (re.escape(self.repo.dir), HOST, SID))

    def test_helper_task_keeps_them(self):
        self.hold_lock()
        self.assertOk(self.start(5151, SID))
        self.assertOk(self.repo.run("agent-file.sh", "helper-task", "Fix Login",
                                    env={"CLAUDE_PID": "5151", "CLAUDE_CODE_SESSION_ID": SID,
                                         "AGENT_FAKE_HOST": HOST}))
        mine = [l for l in self.lines() if "human-direct" in l]
        self.assertEqual(len(mine), 1)
        self.assertIn(" | task: Fix Login | since ", mine[0])
        self.assertTrue(mine[0].endswith(" | pid 5151 | host %s | session %s" % (HOST, SID)), mine[0])

    def test_a_helper_session_ends_and_leaves_nothing(self):
        # requirement example: a Helper session ends: its human-direct line and its agent_helper_* files
        # are gone; the board has no Helper row
        self.hold_lock()
        self.assertOk(self.start(5151, SID))
        self.assertOk(self.repo.run("agent-file.sh", "helper-task", "Free Office Layout",
                                    env={"CLAUDE_PID": "5151", "CLAUDE_CODE_SESSION_ID": SID,
                                         "AGENT_FAKE_HOST": HOST}))
        title = os.path.join(self.gitdir, "agent_helper_title_" + SID)
        with open(title, "w") as fh:
            fh.write("project Helper - Free Office Layout\n")
        result = self.hook({"session_id": SID, "cwd": self.repo.dir, "hook_event_name": "SessionEnd",
                            "reason": "prompt_input_exit"}, env={"CLAUDE_PID": "5151"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([l for l in self.lines() if "human-direct" in l], [])
        left = [n for n in os.listdir(self.gitdir) if n.endswith(SID) or ("_%s_" % SID) in n]
        self.assertEqual(left, [])
        board = self.assertOk(self.repo.run("agent-file.sh", "board", env={"CLAUDE_PID": "5151"}))
        self.assertNotIn("Helper", board)

    def test_the_next_main_manager_drops_a_gone_helper(self):
        # rule 2: the start of the next main manager removes a human-direct line whose session no longer runs
        gone, live = dead_pid(), self.live_pid()
        dead_line = helper_line(self.repo.dir, SID, pid=gone)
        live_line = helper_line("/live/wt", OTHER, pid=live, task="Live Work")
        self.set_lines([dead_line, live_line])
        out = self.assertOk(self.start(4242, "mm-new"))
        self.assertIn("ROLE: main manager", out)
        self.assertEqual(self.lines(), [live_line])


class TestHousekeepDropsGoneHelpers(th.HousekeepCase):
    def setUp(self):
        super().setUp()
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
                p.wait()
        super().tearDown()

    def test_a_gone_helper_line_is_removed_a_live_one_stays(self):
        live = subprocess.Popen(["sleep", "120"])
        self.procs.append(live)
        gone = dead_pid()
        dead_line = helper_line(self.repo.dir, SID, pid=gone)
        live_line = helper_line(self.repo.dir, OTHER, pid=live.pid, task="Live Work")
        old_line = helper_line(self.repo.dir, "-")
        th.write(self.repo.path("agent_worktree.txt"), dead_line + "\n" + live_line + "\n" + old_line + "\n")
        with open(self.repo.path(".git", "agent_helper_task_" + SID), "w") as fh:
            fh.write("Old Work\n")
        self.apply(env={"AGENT_FAKE_HOST": HOST})
        self.assertEqual(self.file_lines("agent_worktree.txt"), [live_line, old_line])
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_helper_task_" + SID)))
        self.assertIn("removed: human-direct line %s (pid %d gone)" % (self.repo.dir, gone), self.body())

    def test_the_listing_only_says_it(self):
        gone = dead_pid()
        line = helper_line(self.repo.dir, SID, pid=gone)
        th.write(self.repo.path("agent_worktree.txt"), line + "\n")
        out = self.listing(env={"AGENT_FAKE_HOST": HOST})
        self.assertEqual(self.file_lines("agent_worktree.txt"), [line])
        self.assertIn("would remove: human-direct line %s (pid %d gone)" % (self.repo.dir, gone), out)


class DesignerCase(EndCase):
    script = "agent-start.sh"

    def setUp(self):
        super().setUp()
        self.room_log = os.path.join(self.repo.base, "room_calls.log")
        open(self.room_log, "w").close()
        self.repo.write_bin_script("agent-room.sh",
                                   "#!/usr/bin/env bash\nprintf '%%s\\n' \"$*\" >> %s\nexit 0\n" % self.room_log)

    def designer(self, *args, source="startup", sid="d1", hook=True):
        env = {"AGENT_ROLE": "interior-designer", "ORCA_TERMINAL_HANDLE": "term_d-1", "CLAUDE_PID": "6161"}
        stdin = None
        if hook:
            stdin = json.dumps({"session_id": sid, "transcript_path": "/tmp/x.jsonl", "cwd": self.repo.dir,
                                "hook_event_name": "SessionStart", "source": source})
        else:
            env["CLAUDE_CODE_SESSION_ID"] = sid
        return self.repo.run("agent-start.sh", *args, env=env, stdin=stdin)

    def files_of(self, sid):
        return [n for n in os.listdir(self.gitdir) if sid in n]

    def assertOneRoleLine(self, out):
        lines = [l for l in out.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1, out)
        self.assertTrue(lines[0].startswith("ROLE: interior designer"), lines[0])
        self.assertIn("agents/interior-designer.md", lines[0])
        self.assertLessEqual(len(lines[0].encode()), 300)
        for word in ("QUIZ", "READ NOW", "RULES:", "task manager", "agent_state.txt"):
            self.assertNotIn(word, out)


class TestDesignerStart(DesignerCase):
    def test_startup_is_one_line(self):
        # requirement example: the designer's start text has no QUIZ line and no reading list
        self.assertOneRoleLine(self.assertOk(self.designer()))

    def test_the_rules_entry_prints_nothing(self):
        self.assertEqual(self.assertOk(self.designer("--rules")), "")

    def test_compact_and_by_hand_are_the_same_line(self):
        first = self.assertOk(self.designer())
        self.assertEqual(self.assertOk(self.designer(source="compact")), first)
        self.assertEqual(self.assertOk(self.designer(hook=False)), first)

    def test_no_file_in_the_git_dir(self):
        self.designer()
        self.designer("--rules")
        self.designer(source="compact")
        self.designer(source="compact")
        self.assertEqual(self.files_of("d1"), [])
        self.assertNotIn("human-direct", self.repo.read("agent_worktree.txt") or "")

    def test_no_pane_measuring(self):
        # requirement example: agent_test_weights.json gets no pane weight from it
        self.designer()
        time.sleep(1.0)    # the measuring run is detached: give it time to show up
        with open(self.room_log) as fh:
            self.assertEqual(fh.read(), "")
        weights = os.path.join(self.gitdir, "agent_test_weights.json")
        if os.path.exists(weights):
            with open(weights) as fh:
                self.assertNotIn("pane", json.load(fh))

    def test_the_quiz_is_not_for_it(self):
        out = self.assertOk(self.designer("--quiz", hook=False))
        self.assertNotIn("Q1.", out)
        self.assertOneRoleLine(out)

    def test_a_task_manager_start_is_unchanged(self):
        env = {"AGENT_ROLE": "task-manager", "CLAUDE_PID": "6262"}
        out = self.assertOk(self.repo.run("agent-start.sh", env=env))
        self.assertIn("ROLE: task-manager", out)
        self.assertIn("QUIZ:", out)


if __name__ == "__main__":
    unittest.main()
