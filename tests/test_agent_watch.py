"""Tests of bin/agent-watch.sh and agent_watch.py: the single and --all watch, wake words,
stalls, remote panes, tell, the housekeep timer.

requirements/one-watcher.md. One class per feature. Older task contracts: git log -p of this file.
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase  # noqa: E402
import json
import signal
import subprocess
import time
from watchhelp import (ENV, EXITED, LOGIN_TEXTS, STILL, AllCase, dead_pid, frame, idle,  # noqa: E402
                       moving, now_text, sh_quote)
from watchhelp import ENV, AllCase, now_text, sha8  # noqa: E402
import tempfile  # noqa: E402
from scripthelp import BIN  # noqa: E402

WATCH_STUB = r'''#!/usr/bin/env python3
"""Fake orca for agent-watch tests. Never talks to the real app."""
import json, os, subprocess, sys

args = sys.argv[1:]
with open(os.environ["ORCA_STUB_LOG"], "a") as fh:
    fh.write("CALL" + "".join("\t" + a for a in args) + "\n")


def opt(name):
    for i, a in enumerate(args[:-1]):
        if a == name:
            return args[i + 1]
    return None


D = os.environ["ORCA_STUB_DIR"]
env = opt("--environment")
term = opt("--terminal") or ""
verb = " ".join(args[:2])
if env and os.path.exists(os.path.join(D, "env", env, "down")):
    sys.stderr.write("orca: environment %s is not reachable\n" % env)
    sys.exit(1)
if verb == "worktree ps":
    sys.stdout.write(open(os.environ["ORCA_STUB_PS"]).read())
    sys.exit(0)
screens = os.path.join(D, "screens", term)
shell = os.path.join(D, "shell", term)


def answer(tail, cursor):
    print(json.dumps({"ok": True, "result": {"terminal": {
        "handle": term, "status": "running", "tail": tail,
        "latestCursor": str(cursor), "nextCursor": str(cursor),
        "source": "screen"}}}))


if verb == "terminal read" and os.path.isdir(screens):
    count_file = os.path.join(screens, "count")
    n = int(open(count_file).read()) + 1 if os.path.exists(count_file) else 1
    with open(count_file, "w") as fh:
        fh.write(str(n))
    frames = sorted(int(x) for x in os.listdir(screens) if x.isdigit())
    frame = open(os.path.join(screens, str(min(n, frames[-1])))).read()
    hook = os.path.join(screens, "hook.sh")
    if os.path.exists(hook):
        subprocess.run(["bash", hook, str(n)])
    if frame.startswith("FAIL"):
        sys.stderr.write("orca: terminal read failed\n")
        sys.exit(1)
    answer(frame.splitlines(), n)
elif verb == "terminal read" and os.path.isdir(shell):
    buf = os.path.join(shell, "buf")
    lines = open(buf).read().splitlines()
    cursor = opt("--cursor")
    answer(lines[int(cursor):] if cursor else lines[-40:], len(lines))
elif verb == "terminal send" and os.path.isdir(shell):
    text = opt("--text") or ""
    run = subprocess.run(["bash", "-c", text], capture_output=True, text=True)
    with open(os.path.join(shell, "buf"), "a") as fh:
        fh.write("$ " + text + "\n" + run.stdout + run.stderr)
    print(json.dumps({"ok": True, "result": {}}))
elif verb == "terminal send" and os.path.isdir(screens):
    print(json.dumps({"ok": True, "result": {}}))
elif verb.startswith("terminal"):
    # real orca: a gone handle is a JSON error on stdout, exit 1
    print(json.dumps({"ok": False, "error": {"code": "terminal_handle_stale",
                                             "message": "terminal_handle_stale"}}))
    sys.exit(1)
else:
    print(json.dumps({"ok": True, "result": {}}))
'''

TM = "term_tm1"
SHELL = "term_sh1"
ENV = "maverick-pc2"

STATE_HEAD = (
    "[Opus 5.5 xhigh] Brief from the main manager: you are the task manager for \"feat\".\n"
    "REPORT: append under \"=== REPORT ===\" here. First line \"DONE PASS feat\".\n"
    "ASK: append \"QUESTION: ...\" under \"=== QUESTIONS ===\" here.\n"
    "=== QUESTIONS ===\n"
    "=== HEARTBEAT ===\n"
)

SWEEP = re.compile(r"^\d\d:\d\d\b.*\bsame=\d+.*\bfile=\d+")


def frame(n, extra=()):
    """A Claude Code screen that moves: the ✻ line changes with n."""
    return ([
        "⏺ Bash(python3 -m unittest tests.test_x)",
        "  ⎿  Ran 4 tests in 0.%ds" % n,
        "",
    ] + list(extra) + [
        "✻ Working… (%ds · esc to interrupt)" % (10 + n),
        "",
        "❯ ",
        "  ⏵⏵ bypass permissions on (shift+tab to cycle)",
    ])


STILL = frame(0)


class WatchCase(ScriptCase):
    script = "agent-watch.sh"

    def setUp(self):
        super().setUp()
        self.repo.stub_tool("orca", WATCH_STUB)
        self.wt = self.repo.make_worktree("feat", as_repo=False)
        self.state = os.path.join(self.wt, "agent_state.txt")
        with open(self.state, "w") as fh:
            fh.write(STATE_HEAD)

    # ---- fixture ----

    def screens(self, frames, handle=TM):
        folder = os.path.join(self.repo.orca_dir, "screens", handle)
        os.makedirs(folder, exist_ok=True)
        for i, lines in enumerate(frames, 1):
            with open(os.path.join(folder, str(i)), "w") as fh:
                fh.write("\n".join(lines) + "\n")

    def moving(self, n=40, extra_at=None, extra=()):
        """n frames that all differ; frame number extra_at gets extra lines."""
        return [frame(i, extra if i == extra_at else ()) for i in range(1, n + 1)]

    def hook(self, body, handle=TM):
        """Bash run after each read of the TM pane, $1 = read number."""
        folder = os.path.join(self.repo.orca_dir, "screens", handle)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "hook.sh"), "w") as fh:
            fh.write(body)

    def append_on_read(self, k, line):
        self.hook('[ "$1" = "%d" ] && printf "%%s\\n" %s >> %s\n'
                  % (k, sh_quote(line), sh_quote(self.state)))

    def append_state(self, *lines):
        with open(self.state, "a") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def shell_pane(self, handle=SHELL):
        folder = os.path.join(self.repo.orca_dir, "shell", handle)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "buf"), "w") as fh:
            fh.write("Last login: Wed Nov  4 16:00:00\n$ \n")

    def down(self, env=ENV):
        self.repo.set_orca_env_state(env, "down")

    # ---- running ----

    def watch(self, *extra, env=None, name="feat", remote=False, max_sweeps="8",
              timeout=60):
        args = ["--terminal", TM, "--worktree", self.wt]
        if remote:
            args += ["--environment", ENV, "--shell", SHELL]
        if name:
            args += ["--name", name]
        if max_sweeps:
            args += ["--max", max_sweeps]
        run_env = {"AGENT_RUNTIME": "orca", "AGENT_WATCH_INTERVAL_S": "0"}
        run_env.update(env or {})
        result = self.repo.run("agent-watch.sh", *(args + list(extra)),
                               env=run_env, timeout=timeout)
        self.assertNoSendToTm()
        return result

    def out(self, result):
        """stdout + stderr of a finished WATCH run, exit 0 required."""
        self.assertOk(result)
        return result.stdout + result.stderr

    def watch_line(self, text):
        hits = [l for l in self.lines(text) if l.startswith("WATCH ")]
        self.assertEqual(len(hits), 1, "want one WATCH line:\n" + text)
        return hits[0]

    def after_watch(self, text):
        lines = self.lines(text)
        i = next(i for i, l in enumerate(lines) if l.startswith("WATCH "))
        return lines[i + 1:]

    def sweeps(self, text):
        return [l for l in self.lines(text) if SWEEP.match(l)]

    # ---- what orca saw ----

    def terminal_calls(self, verb):
        return [c for c in self.repo.calls() if c[:2] == ["terminal", verb]]

    def opt(self, call, name):
        return call[call.index(name) + 1] if name in call else None

    def assertNoSendToTm(self):
        for call in self.terminal_calls("send"):
            self.assertNotEqual(self.opt(call, "--terminal"), TM,
                                "sent to the TM pane: %r" % call)


def sh_quote(text):
    return "'" + text.replace("'", "'\\''") + "'"


class TestRuntimeAndArgs(WatchCase):
    def test_no_terminal_is_a_usage_error(self):
        result = self.repo.run("agent-watch.sh", "--worktree", self.wt,
                               env={"AGENT_RUNTIME": "orca",
                                    "AGENT_WATCH_INTERVAL_S": "0"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage", (result.stdout + result.stderr).lower())
        self.assertEqual(self.terminal_calls("read"), [])

    def test_no_worktree_is_a_usage_error(self):
        result = self.repo.run("agent-watch.sh", "--terminal", TM,
                               env={"AGENT_RUNTIME": "orca",
                                    "AGENT_WATCH_INTERVAL_S": "0"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage", (result.stdout + result.stderr).lower())

    def test_environment_needs_a_shell_pane(self):
        result = self.repo.run("agent-watch.sh", "--terminal", TM, "--worktree",
                               self.wt, "--environment", ENV,
                               env={"AGENT_RUNTIME": "orca",
                                    "AGENT_WATCH_INTERVAL_S": "0"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--shell", result.stdout + result.stderr)
        self.assertEqual(self.terminal_calls("read"), [])

    def test_interval_env_wins_over_minutes(self):
        self.screens(self.moving())
        result = self.watch("--interval-min", "5", max_sweeps="2", timeout=30)
        self.assertEqual(self.watch_line(self.out(result)), "WATCH MAX feat")


class TestFileSignal(WatchCase):
    def test_baseline_lines_do_not_fire(self):
        self.append_state("DONE PASS feat", "QUESTION: an old one?",
                          "CLOSE CASE feat: unfinished", "DONE FAIL feat: old",
                          "MOCK READY feat: mock/feat-mock.html")
        self.screens([STILL])
        text = self.out(self.watch())
        self.assertNotIn("WATCH SIGNAL", text)
        self.assertEqual(self.watch_line(text), "WATCH STALL feat")

    def test_a_new_line_of_each_kind_fires(self):
        for line in ("QUESTION: which port, 8080 or 9090?", "DONE PASS feat",
                     "DONE FAIL feat: 2 tests red", "CLOSE CASE feat: finished",
                     "MOCK READY feat: mock/feat-mock.html"):
            with self.subTest(line=line):
                self.setUp()
                self.screens(self.moving())
                self.append_on_read(2, line)
                text = self.out(self.watch())
                self.assertEqual(self.watch_line(text), "WATCH SIGNAL feat: " + line)

    def test_local_reads_the_file_with_no_shell_pane(self):
        self.screens(self.moving())
        self.append_on_read(2, "QUESTION: local?")
        text = self.out(self.watch())
        self.assertEqual(self.watch_line(text), "WATCH SIGNAL feat: QUESTION: local?")
        self.assertEqual(self.terminal_calls("send"), [])
        for call in self.terminal_calls("read"):
            self.assertEqual(self.opt(call, "--terminal"), TM)
            self.assertNotIn("--environment", call)

    def test_a_signal_word_mid_line_does_not_fire(self):
        self.screens(self.moving())
        self.hook('[ "$1" = "2" ] && echo "note: DONE PASS comes after the suite" >> %s\n'
                  '[ "$1" = "3" ] && echo "  QUESTION: indented" >> %s\n'
                  '[ "$1" = "4" ] && echo "next: MOCK READY when the page is up" >> %s\n'
                  % (sh_quote(self.state), sh_quote(self.state), sh_quote(self.state)))
        text = self.out(self.watch(max_sweeps="5"))
        self.assertNotIn("WATCH SIGNAL", text)
        self.assertEqual(self.watch_line(text), "WATCH MAX feat")

    def test_a_trim_that_lowers_the_count_does_not_hide_the_next_signal(self):
        # state-trim (2026-11-20, reviewer finding 3): `state trim` can move old answered QUESTION
        # lines; a count below the baseline becomes the new baseline, so the next new line still fires
        self.append_state("QUESTION: old one? | 2026-11-10 09:00", "ANSWER: yes | 2026-11-10 09:10",
                          "QUESTION: older one? | 2026-11-09 09:00", "ANSWER: no | 2026-11-09 09:10")
        self.screens(self.moving())
        self.hook('[ "$1" = "2" ] && printf "%%s" %s > %s\n[ "$1" = "4" ] && echo "DONE PASS feat" >> %s\n'
                  % (sh_quote(STATE_HEAD), sh_quote(self.state), sh_quote(self.state)))
        text = self.out(self.watch())
        self.assertEqual(self.watch_line(text), "WATCH SIGNAL feat: DONE PASS feat")

    def test_the_signal_ends_the_watch_at_once(self):
        self.screens(self.moving())
        self.append_on_read(2, "DONE PASS feat")
        text = self.out(self.watch(max_sweeps="20"))
        self.assertLessEqual(len(self.sweeps(text)), 3, text)


class TestScreenNeverFires(WatchCase):
    """SCOPE ADD 1: only file lines fire. The screen feeds the stall and the
    sweep line, nothing else."""

    DONE = ["⏺ DONE PASS feat", "", "  Result: 42 tests OK"]

    def test_no_screen_word_fires(self):
        for word in ("DONE PASS feat", "DONE FAIL feat: red", "QUESTION: port?",
                     "CLOSE CASE feat: finished", "MOCK READY feat: mock/x.html"):
            with self.subTest(word=word):
                self.setUp()
                self.screens(self.moving(extra_at=2, extra=["⏺ " + word]))
                text = self.out(self.watch(max_sweeps="4"))
                self.assertNotIn("WATCH SIGNAL", text)
                self.assertEqual(self.watch_line(text), "WATCH MAX feat")

    def test_a_plan_line_on_screen_does_not_fire(self):
        """The 17:39 case: a plan, not a report."""
        plan = ["⏺ Next: run the suite, then write DONE PASS remote-watch into "
                "agent_state.txt."]
        self.screens(self.moving(extra_at=2, extra=plan))
        text = self.out(self.watch(max_sweeps="4"))
        self.assertNotIn("WATCH SIGNAL", text)

    def test_the_file_line_still_fires_with_a_done_screen(self):
        self.screens(self.moving(extra_at=2, extra=self.DONE))
        self.append_on_read(4, "DONE PASS feat")
        text = self.out(self.watch())
        self.assertEqual(self.watch_line(text), "WATCH SIGNAL feat: DONE PASS feat")

    def test_a_done_line_already_on_screen_at_start_does_not_fire(self):
        self.screens([frame(0, self.DONE)])
        text = self.out(self.watch())
        self.assertNotIn("WATCH SIGNAL", text)
        self.assertEqual(self.watch_line(text), "WATCH STALL feat")

    def test_done_pass_without_the_marker_does_not_fire(self):
        noise = [
            "DONE PASS feat",
            "  ⎿  DONE PASS feat",
            "test_done_pass_fires (tests.test_agent_watch.TestX) ... ok",
            "    QUESTION: inside a tool result",
            "✻ CLOSE CASE is a keyword",
        ]
        self.screens([frame(i, noise) for i in range(1, 9)])
        text = self.out(self.watch(max_sweeps="5"))
        self.assertNotIn("WATCH SIGNAL", text)
        self.assertEqual(self.watch_line(text), "WATCH MAX feat")

    def test_stall_evidence_is_the_last_15_screen_lines(self):
        body = ["line %02d" % i for i in range(1, 22)]
        self.screens([body])
        text = self.out(self.watch(max_sweeps="10"))
        self.assertEqual(self.watch_line(text), "WATCH STALL feat")
        after = "\n".join(self.after_watch(text))
        self.assertIn("line 21", after)
        self.assertIn("line 07", after)
        self.assertNotIn("line 06", after)


class TestStallLostMax(WatchCase):
    def test_three_same_screens_is_a_stall(self):
        self.screens([STILL])
        text = self.out(self.watch(max_sweeps="10"))
        self.assertEqual(self.watch_line(text), "WATCH STALL feat")
        self.assertLessEqual(len(self.sweeps(text)), 4, text)
        self.assertGreaterEqual(len(self.sweeps(text)), 3, text)
        self.assertIn("✻ Working… (10s · esc to interrupt)",
                      "\n".join(self.after_watch(text)))

    def test_shell_still_running_is_not_a_stall(self):
        self.screens([frame(0, ["✻ Waiting… (shell still running)"])])
        text = self.out(self.watch(max_sweeps="6"))
        self.assertEqual(self.watch_line(text), "WATCH MAX feat")

    def test_plural_shells_still_running_is_not_a_stall(self):
        self.screens([frame(0, ["✻ Baked for 11s · 2 shells still running"])])
        text = self.out(self.watch(max_sweeps="6"))
        self.assertEqual(self.watch_line(text), "WATCH MAX feat")

    def test_waiting_for_background_agent_is_not_a_stall(self):
        self.screens([frame(0, ["✻ Waiting for 1 background agent to finish"])])
        text = self.out(self.watch(max_sweeps="6"))
        self.assertEqual(self.watch_line(text), "WATCH MAX feat")

    def test_a_file_change_is_not_a_stall(self):
        self.screens([STILL])
        self.hook('echo "HEARTBEAT feat: step 4 of 7, work $1m" >> %s\n'
                  % sh_quote(self.state))
        text = self.out(self.watch(max_sweeps="6"))
        self.assertEqual(self.watch_line(text), "WATCH MAX feat")

    def test_three_failed_reads_is_lost(self):
        self.screens([["FAIL"]])
        text = self.out(self.watch(max_sweeps="10"))
        self.assertEqual(self.watch_line(text), "WATCH LOST feat")
        self.assertLessEqual(len(self.terminal_calls("read")), 5)

    def test_lost_names_the_orca_error(self):
        """Real orca puts the error on stdout as JSON ({"ok": false, "error":
        {"code": ...}}), not on stderr. The evidence names it, so the main
        manager can tell a gone pane from an unreachable machine."""
        self.screens(self.moving(), handle="term_other")
        text = self.out(self.watch(max_sweeps="10"))
        self.assertEqual(self.watch_line(text), "WATCH LOST feat")
        self.assertIn("terminal_handle_stale", "\n".join(self.after_watch(text)))

    def test_a_good_read_resets_the_lost_count(self):
        bad = ["FAIL"]
        self.screens([frame(1), bad, bad, frame(2), bad, bad, frame(3), frame(4)])
        text = self.out(self.watch(max_sweeps="7"))
        self.assertEqual(self.watch_line(text), "WATCH MAX feat")

    def test_max_sweeps(self):
        self.screens(self.moving())
        text = self.out(self.watch(max_sweeps="3"))
        self.assertEqual(self.watch_line(text), "WATCH MAX feat")
        self.assertEqual(len(self.sweeps(text)), 3, text)

    def test_name_defaults_to_the_worktree_folder(self):
        self.screens(self.moving())
        text = self.out(self.watch(name=None, max_sweeps="1"))
        self.assertEqual(self.watch_line(text),
                         "WATCH MAX " + os.path.basename(self.wt))

    def test_the_watch_line_comes_after_the_sweeps(self):
        self.screens(self.moving())
        self.append_on_read(3, "QUESTION: last?")
        text = self.out(self.watch())
        self.assertEqual([l for l in self.after_watch(text) if SWEEP.match(l)], [])


class TestSweepLine(WatchCase):
    def test_one_line_per_sweep_with_counts_and_the_last_screen_line(self):
        long_line = "⏺ " + "x" * 300
        self.screens([frame(i, [long_line]) for i in range(1, 6)])
        text = self.out(self.watch(max_sweeps="2"))
        sweeps = self.sweeps(text)
        self.assertEqual(len(sweeps), 2, text)
        for line in sweeps:
            self.assertIn(" | ", line)
            tail = line.split(" | ", 1)[1]
            self.assertLessEqual(len(tail), 110, line)
            self.assertTrue(tail.startswith("✻ Working") or tail.startswith("⏺"),
                            line)

    def test_the_time_comes_from_date(self):
        real = "/bin/date" if os.path.exists("/bin/date") else "/usr/bin/date"
        self.repo.stub_tool(
            "date", '#!/usr/bin/env bash\n'
            'case "$*" in *%%H:%%M*) echo "09:41";; *) exec %s "$@";; esac\n' % real)
        self.screens(self.moving())
        text = self.out(self.watch(max_sweeps="1"))
        self.assertTrue(self.sweeps(text)[0].startswith("09:41"), text)


class TestRemote(WatchCase):
    def setUp(self):
        super().setUp()
        self.shell_pane()

    def test_a_new_question_fires_through_the_shell_pane(self):
        self.screens(self.moving())
        self.append_on_read(2, "QUESTION: remote port?")
        text = self.out(self.watch(remote=True))
        self.assertEqual(self.watch_line(text),
                         "WATCH SIGNAL feat: QUESTION: remote port?")

    def test_a_new_mock_ready_fires_through_the_shell_pane(self):
        self.screens(self.moving())
        self.append_on_read(2, "MOCK READY feat: mock/feat-mock.html")
        text = self.out(self.watch(remote=True))
        self.assertEqual(self.watch_line(text),
                         "WATCH SIGNAL feat: MOCK READY feat: mock/feat-mock.html")

    def test_remote_sends_one_short_command_and_reads_with_cursor(self):
        self.screens(self.moving())
        self.append_on_read(3, "DONE PASS feat")
        self.out(self.watch(remote=True))
        sends = self.terminal_calls("send")
        self.assertTrue(sends, "no command sent to the shell pane")
        for call in sends:
            self.assertEqual(self.opt(call, "--terminal"), SHELL, call)
            # progress-bar: the one command also reads the last STAGE line (was 300)
            self.assertLess(len(self.opt(call, "--text") or ""), 400, call)
        shell_reads = [c for c in self.terminal_calls("read")
                       if self.opt(c, "--terminal") == SHELL]
        self.assertTrue([c for c in shell_reads if "--cursor" in c],
                        "the shell answer was not read with --cursor")
        for call in self.terminal_calls("read") + sends:
            self.assertEqual(self.opt(call, "--environment"), ENV, call)

    def test_remote_baseline_does_not_fire(self):
        self.append_state("DONE PASS feat", "QUESTION: an old one?")
        self.screens([STILL])
        text = self.out(self.watch(remote=True))
        self.assertNotIn("WATCH SIGNAL", text)
        self.assertEqual(self.watch_line(text), "WATCH STALL feat")

    def test_an_old_marker_line_in_the_shell_is_not_read(self):
        """Marker lines printed before this watch began are not its answers:
        the answer is read with --cursor, so an old one neither fires nor
        becomes the baseline."""
        with open(os.path.join(self.repo.orca_dir, "shell", SHELL, "buf"), "a") as fh:
            fh.write("FSIG 9 99 DONE PASS somebody-else FEND\n"
                     "FSIG 9 99 DONE PASS somebody-else\n")
        self.screens(self.moving())
        self.append_on_read(3, "QUESTION: after the old marker?")
        text = self.out(self.watch(remote=True))
        self.assertEqual(self.watch_line(text),
                         "WATCH SIGNAL feat: QUESTION: after the old marker?")

    def test_unreachable_machine_is_lost(self):
        self.screens(self.moving())
        self.down()
        text = self.out(self.watch(remote=True, max_sweeps="10"))
        self.assertEqual(self.watch_line(text), "WATCH LOST feat")

    def test_a_path_with_spaces(self):
        spaced = os.path.join(self.repo.base, "wt with space")
        os.mkdir(spaced)
        with open(os.path.join(spaced, "agent_state.txt"), "w") as fh:
            fh.write(STATE_HEAD)
        self.wt, self.state = spaced, os.path.join(spaced, "agent_state.txt")
        self.screens(self.moving())
        self.append_on_read(2, "QUESTION: spaced?")
        text = self.out(self.watch(remote=True))
        self.assertEqual(self.watch_line(text), "WATCH SIGNAL feat: QUESTION: spaced?")


class TestStageCarry(WatchCase):
    """progress-bar (owner 2026-11-11): a task manager on another machine writes
    its stage into its own checkout, so the laptop board never sees it. The
    watch carries it.

    Each sweep (and the first read) the watch also reads the last line that
    starts "STAGE <name>: " in the worktree's agent_state.txt (local: the file;
    another machine: the same one shell command, still one send per sweep).
    Its value is "<stage>[ <i>/<m>]", the text up to " | since". When the value
    differs from the last one carried, the watch runs this machine's
    bin/agent-file.sh todo stage "<name>" <stage> [<i>/<m>] (the main repo of
    the watch's working folder) and prints one line
    "<HH:MM> stage <name>: <stage>[ <i>/<m>]". The same value is carried once.
    A STAGE line is never a signal and never ends the watch. A refused carry
    (no todo line of that name here) prints one line and the watch goes on.
    """

    def setUp(self):
        super().setUp()
        self.assertOk(self.repo.run("agent-file.sh", "todo", "add", "feat", "big", "the feature", "60"))

    def todo_line(self):
        for line in (self.repo.read("agent_todo.txt") or "").splitlines():
            if line.split(" | ")[0] == "feat":
                return line
        return None

    def on_reads(self, mapping):
        body = "".join('[ "$1" = "%d" ] && printf "%%s\\n" %s >> %s\n'
                       % (k, sh_quote(line), sh_quote(self.state))
                       for k, line in sorted(mapping.items()))
        self.hook(body)

    def stage_lines(self, text):
        return [l for l in self.lines(text) if re.match(r"^\d\d:\d\d stage feat: ", l)]

    def check_carry(self, remote):
        self.append_state("STAGE feat: tests | since 2026-11-11 10:00")
        self.screens(self.moving())
        self.on_reads({2: "STAGE feat: workers 1/2 | since 2026-11-11 10:30",
                       5: "DONE PASS feat"})
        text = self.out(self.watch(remote=remote))
        self.assertEqual(self.watch_line(text), "WATCH SIGNAL feat: DONE PASS feat")
        self.assertEqual([l[6:] for l in self.stage_lines(text)],
                         ["stage feat: tests", "stage feat: workers 1/2"])
        line = self.todo_line()
        self.assertIn(" | stage workers 1/2 since ", line)
        self.assertEqual(len(re.findall(r" \| stage (?!log )", line)), 1, line)   # estimate-improve: the stage log is another field
        return text

    def test_local_stage_is_carried_to_the_todo_line(self):
        self.check_carry(remote=False)

    def test_remote_stage_is_carried_to_the_todo_line(self):
        self.shell_pane()
        self.check_carry(remote=True)
        for call in self.terminal_calls("send"):
            self.assertEqual(self.opt(call, "--terminal"), SHELL, call)
            self.assertLess(len(self.opt(call, "--text") or ""), 400, call)

    def test_the_same_stage_is_carried_once(self):
        self.append_state("STAGE feat: verify | since 2026-11-11 10:00")
        self.screens(self.moving())
        self.append_on_read(4, "DONE PASS feat")
        text = self.out(self.watch())
        self.assertEqual(len(self.stage_lines(text)), 1, text)
        self.assertIn(" | stage verify since ", self.todo_line())

    def test_a_stage_line_never_fires(self):
        self.screens([STILL])
        self.append_on_read(2, "STAGE feat: push | since 2026-11-11 11:00")
        text = self.out(self.watch(max_sweeps="10"))
        self.assertNotIn("WATCH SIGNAL", text)
        self.assertEqual(self.watch_line(text), "WATCH STALL feat")
        self.assertIn(" | stage push since ", self.todo_line())

    def test_another_tasks_stage_line_is_not_carried(self):
        self.append_state("STAGE other: verify | since 2026-11-11 10:00")
        self.screens(self.moving())
        self.append_on_read(3, "DONE PASS feat")
        text = self.out(self.watch())
        self.assertEqual(self.stage_lines(text), [])
        self.assertNotIn(" | stage ", self.todo_line())

    def test_no_todo_line_here_the_watch_goes_on(self):
        self.assertOk(self.repo.run("agent-file.sh", "todo", "drop", "feat", "gone", "-"))
        self.append_state("STAGE feat: tests | since 2026-11-11 10:00")
        self.screens(self.moving())
        self.append_on_read(3, "DONE PASS feat")
        text = self.out(self.watch())
        self.assertEqual(self.watch_line(text), "WATCH SIGNAL feat: DONE PASS feat")


HHMM = r"\d\d:\d\d"


class TestTargets(AllCase):
    def test_a1_working_and_final_lines_are_targets_done_idle_and_helper_are_not(self):
        self.task("alpha", "working")
        self.task("beta", "final")
        self.task("gamma", "done")
        self.task("delta", "idle")
        helper = os.path.join(self.repo.base, "helper")
        os.makedirs(helper)
        self.rows.append((helper, "task manager, human-direct", "task: Fix the login"))
        self.write_rows()
        text = self.text(self.run_all(max_sweeps="1"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")
        self.assertEqual(sorted(self.status()["tasks"]), ["alpha", "beta"])
        sweep = self.sweeps(text)[-1]
        self.assertIn("alpha ", sweep)
        self.assertIn("beta ", sweep)
        for name in ("gamma", "delta", "human-direct"):
            self.assertNotIn(name, sweep)

    def test_a1_a_todo_line_with_an_on_field_and_no_worktree_line_is_a_target(self):
        self.task("alpha")
        real = self.map_env(ENV)
        os.makedirs(os.path.join(real, "wt_far"))
        with open(os.path.join(real, "wt_far", "agent_state.txt"), "w") as fh:
            fh.write("far brief\n")
        self.todo("far", ENV, "/remote/%s/wt_far" % ENV)
        self.todo("near")                      # no on field: not a target
        self.todo("alpha", ENV, "/x/alpha")    # has a worktree line: one target, not two
        self.run_all(max_sweeps="1")
        tasks = self.status()["tasks"]
        self.assertEqual(sorted(tasks), ["alpha", "far"])
        self.assertEqual(tasks["far"]["path"], "/remote/%s/wt_far" % ENV)
        self.assertEqual(tasks["far"]["env"], ENV)
        self.assertEqual(tasks["alpha"]["path"], self.tasks["alpha"]["path"])

    def test_a2_a_new_line_is_watched_from_the_next_sweep(self):
        a = self.task("alpha")
        b = self.task("beta", row=False)
        line = "%s | beta | working | since 2026-11-24 10:02" % b["path"]
        self.hook(a["pane"], '[ "$1" = "2" ] && printf "%%s\\n" %s >> %s\n'
                  % (sh_quote(line), sh_quote(self.repo.path("agent_worktree.txt"))))
        self.hook(b["pane"], '[ "$1" = "2" ] && printf "%%s\\n" %s >> %s\n'
                  % (sh_quote("QUESTION: beta port?"), sh_quote(b["state"])))
        text = self.text(self.run_all(max_sweeps="8"))
        self.assertTrue([l for l in self.lines(text) if re.match(r"^%s watch: \+ beta$" % HHMM, l)], text)
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL beta: QUESTION: beta port?")

    def test_a2_a_line_that_leaves_is_dropped_with_no_exit(self):
        a = self.task("alpha")
        self.task("beta")
        keep = "%s | alpha | working | since 2026-09-21 10:00\n" % a["path"]
        self.hook(a["pane"], '[ "$1" = "2" ] && printf "%%s" %s > %s\n'
                  % (sh_quote(keep), sh_quote(self.repo.path("agent_worktree.txt"))))
        text = self.text(self.run_all(max_sweeps="4"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")
        self.assertEqual(sorted(self.status()["tasks"]), ["alpha"])
        self.assertNotIn("beta", self.sweeps(text)[-1])

    def test_a3_a_folder_here_is_local(self):
        a = self.task("alpha")
        self.on_task_read("alpha", {3: "DONE PASS alpha"})
        text = self.text(self.run_all())
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: DONE PASS alpha")
        self.assertEqual(self.terminal_calls("send"), [])
        for call in self.repo.calls():
            self.assertNotIn("--environment", call)
        self.assertIn(self.status()["tasks"]["alpha"]["env"], (None, ""))
        self.assertEqual(self.status()["tasks"]["alpha"]["pane"], a["pane"])

    def test_a3_remote_env_from_the_launch_record(self):
        self.task("alpha", env=ENV)
        self.on_task_read("alpha", {2: "QUESTION: remote?"})
        text = self.text(self.run_all())
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: QUESTION: remote?")
        self.assertEqual(self.status()["tasks"]["alpha"]["env"], ENV)

    def test_a3_remote_env_from_the_todo_on_field(self):
        t = self.task("alpha", env=ENV, launch=False)
        self.todo("alpha", ENV, t["path"])
        self.terminals([{"handle": t["pane"], "title": "◑ alpha Task Manager", "worktreePath": t["path"],
                         "agentIdentity": "claude"},
                        {"handle": t["shell"], "title": "alpha shell", "worktreePath": t["path"]}], env=ENV)
        self.on_task_read("alpha", {2: "DONE PASS alpha"})
        text = self.text(self.run_all())
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: DONE PASS alpha")
        st = self.status()["tasks"]["alpha"]
        self.assertEqual((st["env"], st["pane"], st["shell"]), (ENV, t["pane"], t["shell"]))

    def test_a3_folder_not_here_and_no_machine_known_is_not_watched(self):
        self.rows.append(("/nowhere/ghost", "ghost", "working"))
        self.write_rows()
        text = self.text(self.run_all(max_sweeps="2"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")
        st = self.status()["tasks"]["ghost"]
        self.assertFalse(st["watched"])
        self.assertEqual(st["why"], "folder not here and no machine known")
        hits = [l for l in self.lines(text)
                if re.match(r"^%s watch: ghost not watched: folder not here and no machine known$" % HHMM, l)]
        self.assertEqual(len(hits), 1, text)

    def test_a4_the_newest_launch_record_wins(self):
        t = self.task("alpha", pane="term_new", launch=False)
        self.screens("term_old", moving())
        self.launch("tm-pane", "alpha", "term_old", since="2026-11-24 07:00")
        self.launch("tm-pane", "alpha", "term_new", since="2026-11-24 08:00")
        self.on_read("term_new", t["state"], {2: "DONE PASS alpha"})
        text = self.text(self.run_all())
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: DONE PASS alpha")
        self.assertEqual([c for c in self.terminal_calls("read") if self.opt(c, "--terminal") == "term_old"], [])

    def test_a4_from_the_list_the_title_with_task_manager(self):
        t = self.task("alpha", pane="term_t", launch=False)
        self.screens("term_c", moving())
        self.terminals([{"handle": "term_sh", "title": "zsh", "worktreePath": t["path"]},
                        {"handle": "term_c", "title": "✳ Claude Code", "worktreePath": t["path"],
                         "agentIdentity": "claude"},
                        {"handle": "term_t", "title": "◑ alpha Task Manager", "worktreePath": t["path"],
                         "agentIdentity": "claude"}])
        self.on_read("term_t", t["state"], {2: "QUESTION: listed?"})
        text = self.text(self.run_all())
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: QUESTION: listed?")
        self.assertEqual(self.status()["tasks"]["alpha"]["pane"], "term_t")
        lists = self.terminal_calls("list")
        self.assertTrue([c for c in lists if self.opt(c, "--worktree") == "path:" + t["path"]], lists)

    def test_a4_from_the_list_the_only_claude_pane(self):
        t = self.task("alpha", pane="term_c", launch=False)
        self.terminals([{"handle": "term_sh", "title": "zsh", "worktreePath": t["path"]},
                        {"handle": "term_c", "title": "✳ Claude Code", "worktreePath": t["path"],
                         "agentIdentity": "claude"}])
        self.on_task_read("alpha", {2: "DONE PASS alpha"})
        text = self.text(self.run_all())
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: DONE PASS alpha")

    def test_a4_two_claude_panes_and_no_title_is_no_pane(self):
        t = self.task("alpha", pane="term_c1", launch=False)
        self.screens("term_c2", moving())
        self.terminals([{"handle": "term_c1", "title": "✳ Claude Code", "worktreePath": t["path"],
                         "agentIdentity": "claude"},
                        {"handle": "term_c2", "title": "✳ Claude Code", "worktreePath": t["path"],
                         "agentIdentity": "claude"}])
        self.run_all(max_sweeps="1")
        st = self.status()["tasks"]["alpha"]
        self.assertEqual((st["watched"], st["why"]), (False, "no task manager pane"))

    def test_a4_no_pane_is_not_watched(self):
        self.task("alpha", launch=False)
        text = self.text(self.run_all(max_sweeps="2"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")
        st = self.status()["tasks"]["alpha"]
        self.assertEqual((st["watched"], st["why"]), (False, "no task manager pane"))
        self.assertEqual(self.terminal_calls("read"), [])

    def test_a5_shell_from_the_list_a_terminal_with_no_agent_identity(self):
        t = self.task("alpha", env=ENV, launch=False, shell="sh_listed")
        self.launch("tm-pane", "alpha", t["pane"], env=ENV)
        self.terminals([{"handle": t["pane"], "title": "◑ alpha Task Manager", "worktreePath": t["path"],
                         "agentIdentity": "claude"},
                        {"handle": "sh_listed", "title": "alpha shell", "worktreePath": t["path"]}], env=ENV)
        self.on_task_read("alpha", {2: "QUESTION: via the listed shell?"})
        text = self.text(self.run_all())
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: QUESTION: via the listed shell?")
        sends = self.terminal_calls("send")
        self.assertTrue(sends)
        for call in sends:
            self.assertEqual(self.opt(call, "--terminal"), "sh_listed", call)

    def test_a5_the_shell_record_must_have_the_same_env(self):
        t = self.task("alpha", env=ENV, launch=False)
        self.launch("tm-pane", "alpha", t["pane"], env=ENV)
        self.shell_pane("sh_other", env="laptop2")
        self.launch("shell-pane", "alpha", "sh_other", env="laptop2")
        self.run_all(max_sweeps="1")
        st = self.status()["tasks"]["alpha"]
        self.assertFalse(st["watched"])
        self.assertTrue(st["why"].startswith("no shell pane on %s" % ENV), st["why"])

    def test_a5_no_shell_pane_says_how_to_open_one(self):
        t = self.task("alpha", env=ENV, launch=False)
        self.launch("tm-pane", "alpha", t["pane"], env=ENV)
        text = self.text(self.run_all(max_sweeps="1"))
        why = ('no shell pane on %s; open one: orca terminal create --environment %s --worktree path:%s '
               '--title "alpha shell"' % (ENV, ENV, t["path"]))
        st = self.status()["tasks"]["alpha"]
        self.assertEqual((st["watched"], st["why"]), (False, why))
        self.assertIn("watch: alpha not watched: " + why, text)

    def test_a6_a_gone_handle_is_resolved_once_more_before_it_counts(self):
        t = self.task("alpha", pane="term_new", launch=False)
        self.launch("tm-pane", "alpha", "term_gone")          # no such pane: terminal_handle_stale
        self.terminals([{"handle": "term_new", "title": "◑ alpha Task Manager", "worktreePath": t["path"],
                         "agentIdentity": "claude"}])
        self.on_read("term_new", t["state"], {3: "DONE PASS alpha"})
        text = self.text(self.run_all(max_sweeps="8"))
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: DONE PASS alpha")
        self.assertNotIn("WATCH LOST", text)
        self.assertEqual(self.status()["tasks"]["alpha"]["pane"], "term_new")

    def test_a7_a_signed_wake_line_fires(self):
        for line in ("[Opus 5.5 xhigh] QUESTION: rules yes?", "[Opus 5.5 xhigh] DONE PASS alpha",
                     "[Sonnet 5 high] MOCK READY alpha: mock/alpha-mock.html"):
            with self.subTest(line=line):
                self.setUp()
                self.task("alpha")
                self.on_task_read("alpha", {2: line})
                text = self.text(self.run_all())
                self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: " + line)

    def test_a7_a_signed_line_with_no_wake_word_does_not_fire(self):
        self.task("alpha")
        self.on_task_read("alpha", {2: "[Opus 5.5 xhigh] Brief from the main manager: you are the task manager"})
        text = self.text(self.run_all(max_sweeps="4"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")

    def test_a8_indented_mid_line_and_two_groups_do_not_fire(self):
        self.task("alpha")
        self.on_task_read("alpha", {2: "  QUESTION: indented", 3: "note: DONE PASS later",
                                    4: "[a] [b] DONE PASS alpha", 5: "\tDONE PASS tabbed"})
        text = self.text(self.run_all(max_sweeps="6"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")

    def test_a9_not_watched_is_printed_once_and_never_ends_the_watch(self):
        self.task("alpha")
        self.task("ghost", launch=False)
        text = self.text(self.run_all(max_sweeps="4"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")
        hits = [l for l in self.lines(text) if "watch: ghost not watched:" in l]
        self.assertEqual(len(hits), 1, text)
        self.assertRegex(hits[0], r"^%s watch: ghost not watched: no task manager pane$" % HHMM)
        self.assertEqual(len(self.sweeps(text)), 4, text)
        for sweep in self.sweeps(text):
            self.assertIn("ghost not watched", sweep)

    def test_a9_printed_again_when_the_why_changes(self):
        a = self.task("alpha")
        g = self.task("ghost", launch=False)
        self.hook(a["pane"], '[ "$1" = "2" ] && rm -rf %s\n' % sh_quote(g["real"]))
        text = self.text(self.run_all(max_sweeps="4"))
        hits = [l for l in self.lines(text) if "watch: ghost not watched:" in l]
        self.assertEqual([h[6:] for h in hits],
                         ["watch: ghost not watched: no task manager pane",
                          "watch: ghost not watched: folder not here and no machine known"], text)


class TestSweepAndWake(AllCase):
    def test_b1_remote_one_short_command_per_sweep_read_with_cursor(self):
        t = self.task("alpha", env=ENV)
        self.on_task_read("alpha", {4: "DONE PASS alpha"})
        text = self.text(self.run_all(max_sweeps="8"))
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: DONE PASS alpha")
        sends = self.terminal_calls("send")
        tm_reads = [c for c in self.terminal_calls("read") if self.opt(c, "--terminal") == t["pane"]]
        self.assertTrue(sends)
        self.assertLessEqual(len(sends), len(tm_reads))
        for call in sends:
            self.assertEqual(self.opt(call, "--terminal"), t["shell"], call)
            self.assertLess(len(self.opt(call, "--text") or ""), 500, call)
        shell_reads = [c for c in self.terminal_calls("read") if self.opt(c, "--terminal") == t["shell"]]
        self.assertTrue([c for c in shell_reads if "--cursor" in c], shell_reads)
        for call in self.terminal_calls("read") + sends:
            self.assertEqual(self.opt(call, "--environment"), ENV, call)

    def test_b2_the_signal_then_the_last_15_screen_lines_of_that_tm(self):
        self.task("alpha", frames=[["line %02d of %d" % (i, k) for i in range(1, 22)] for k in range(1, 9)])
        self.on_task_read("alpha", {2: "QUESTION: RULES READY alpha: requirements/alpha.md, rules yes?"})
        text = self.text(self.run_all())
        watch = self.one_watch(text)
        self.assertEqual(watch, "WATCH SIGNAL alpha: QUESTION: RULES READY alpha: requirements/alpha.md, rules yes?")
        after = "\n".join(self.after(text, watch))
        self.assertIn("line 21 of ", after)
        self.assertIn("line 07 of ", after)
        self.assertNotIn("line 06 of ", after)

    def test_b2_every_wake_word_fires(self):
        for line in ("DONE PASS alpha", "DONE FAIL alpha: 2 red", "CLOSE CASE alpha: finished",
                     "QUESTION: port?", "MOCK READY alpha: mock/alpha-mock.html"):
            with self.subTest(line=line):
                self.setUp()
                self.task("alpha")
                self.on_task_read("alpha", {2: line})
                self.assertEqual(self.one_watch(self.text(self.run_all())), "WATCH SIGNAL alpha: " + line)

    def test_b3_heartbeat_ack_stage_answer_tell_never_wake_and_count_as_a_change(self):
        self.todo("alpha")
        t = self.task("alpha", frames=[STILL])
        extra = {2: "ACK alpha: brief read", 3: "STAGE alpha: workers 1/2 | since 2026-11-24 09:00",
                 4: "ANSWER: 8080 | 2026-11-24 09:05", 5: "TELL 1234abcd [Opus 5.5 xhigh] | 2026-11-24 09:10",
                 6: "  QUESTION: a told line"}
        body = 'printf "%%s\\n" "HEARTBEAT alpha: step 4 of 7, work ${1}m, worker 1" >> %s\n' % sh_quote(t["state"])
        body += "".join('[ "$1" = "%d" ] && printf "%%s\\n" %s >> %s\n' % (k, sh_quote(v), sh_quote(t["state"]))
                        for k, v in sorted(extra.items()))
        self.hook(t["pane"], body)
        text = self.text(self.run_all(max_sweeps="7"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")
        self.assertIn(" | stage workers 1/2 since ", self.todo_line("alpha"))
        self.assertTrue([l for l in self.lines(text) if re.match(r"^%s stage alpha: workers 1/2$" % HHMM, l)], text)

    def test_a_wake_points_to_the_watch_rules_once_per_session(self):
        # md-slim-principles C 9, C 10: a watch signal -> rules/watch.md, one line after the events
        point = "Handle it: rules/watch.md (W15). The watch only points."
        for n, want in ((1, True), (2, False)):
            with self.subTest(run=n):
                self.setUp()
                self.task("alpha")
                self.on_task_read("alpha", {2: "DONE PASS alpha"})
                env = {"CLAUDE_CODE_SESSION_ID": "s-watch"}
                if n == 2:
                    marker = os.path.join(self.repo.dir, ".git", "agent_point_s-watch_watch")
                    open(marker, "w").close()
                text = self.text(self.run_all(env=env))
                self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: DONE PASS alpha")
                self.assertEqual(point in self.lines(text), want, text)

    def test_b4_two_events_in_one_sweep_two_watch_lines_in_target_order_one_exit(self):
        self.task("zeta")
        self.task("alpha")
        self.on_task_read("zeta", {2: "DONE PASS zeta"})
        self.on_task_read("alpha", {2: "QUESTION: port?"})
        text = self.text(self.run_all())
        self.assertEqual(self.watch_lines(text), ["WATCH SIGNAL zeta: DONE PASS zeta",
                                                  "WATCH SIGNAL alpha: QUESTION: port?"])
        self.assertEqual(len(self.sweeps(text)), 1, text)
        self.assertTrue(self.after(text, "WATCH SIGNAL zeta: DONE PASS zeta"))
        lines = self.lines(text)
        self.assertLess(lines.index(self.sweeps(text)[0]), lines.index("WATCH SIGNAL zeta: DONE PASS zeta"))

    def test_b4_a_lost_and_a_signal_in_one_sweep(self):
        self.task("alpha")
        self.task("beta")
        self.exited("term_alpha", from_read=2)
        self.on_task_read("beta", {2: "DONE PASS beta"})
        text = self.text(self.run_all())
        self.assertEqual(self.watch_lines(text), ["WATCH LOST alpha: pane exited (operator_close, exit 0)",
                                                  "WATCH SIGNAL beta: DONE PASS beta"])

    def test_b5_a_reported_line_does_not_fire_again_after_a_restart(self):
        self.task("alpha")
        self.on_task_read("alpha", {2: "DONE PASS alpha"})
        self.assertEqual(self.one_watch(self.text(self.run_all())), "WATCH SIGNAL alpha: DONE PASS alpha")
        text = self.text(self.run_all(max_sweeps="3"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")

    def test_b5_a_line_written_while_no_watch_ran_fires_at_the_next_start(self):
        self.task("alpha")
        self.task("beta")
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="1"))), "WATCH MAX all")
        self.append_state("beta", "QUESTION: written between two watches?")
        text = self.text(self.run_all(max_sweeps="5"))
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL beta: QUESTION: written between two watches?")
        self.assertLessEqual(len(self.sweeps(text)), 1, text)

    def test_b5_first_sight_old_lines_are_the_baseline(self):
        self.task("alpha")
        self.append_state("alpha", "DONE PASS alpha", "QUESTION: an old one?", "ANSWER: yes",
                          "CLOSE CASE alpha: unfinished", "MOCK READY alpha: mock/x.html", "DONE FAIL alpha: old")
        text = self.text(self.run_all(max_sweeps="3"))
        self.assertNotIn("WATCH SIGNAL", text)
        self.assertEqual(self.status()["tasks"]["alpha"]["signals"], 5)

    def test_b5_a_count_below_the_saved_one_is_the_new_baseline(self):
        t = self.task("alpha")
        self.append_state("alpha", "QUESTION: one? | 2026-11-10 09:00", "ANSWER: yes",
                          "QUESTION: two? | 2026-11-10 09:00", "ANSWER: no")
        self.run_all(max_sweeps="1")
        self.assertEqual(self.status()["tasks"]["alpha"]["signals"], 2)
        with open(t["state"], "w") as fh:                       # a state trim moved them out
            fh.write("brief\n")
        self.reset_reads(t["pane"])
        self.on_task_read("alpha", {3: "DONE PASS alpha"})
        text = self.text(self.run_all())
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: DONE PASS alpha")

    def test_b6_busy_screen_the_same_3_sweeps_is_a_stall(self):
        self.task("alpha", frames=[STILL])
        text = self.text(self.run_all(max_sweeps="10"))
        watch = self.one_watch(text)
        self.assertEqual(watch, "WATCH STALL alpha: no change")
        self.assertGreaterEqual(len(self.sweeps(text)), 3, text)
        self.assertLessEqual(len(self.sweeps(text)), 4, text)
        self.assertIn("✻ Working… (10s · esc to interrupt)", "\n".join(self.after(text, watch)))

    def test_b6_shell_still_running_is_not_a_stall(self):
        self.task("alpha", frames=[frame(0, ["✻ Waiting… (shell still running)"])])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_b6_plural_shells_still_running_is_not_a_stall(self):
        self.task("alpha", frames=[frame(0, ["✻ Baked for 11s · done 11:40 AM · 2 shells still running"])])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_b7_idle_prompt_with_plural_shells_still_running_is_not_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["✻ Baked for 11s · done 11:40 AM · 2 shells still running"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_b7_idle_prompt_waiting_for_background_agent_is_not_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["✻ Waiting for 1 background agent to finish", "  ⏺ main"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_b7_idle_prompt_waiting_for_two_background_agents_is_not_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["✻ Waiting for 2 background agents to finish"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_b7_idle_prompt_with_only_main_panel_row_is_still_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["  ⏺ main"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH STALL alpha: idle prompt")

    def test_b7_idle_prompt_with_running_subagent_row_is_not_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["  ⏺ main", "  ◯ auto-pipeline:worker  review the diff   2m 45s · ↓ 136.0k tokens"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_b7_idle_prompt_without_shell_line_is_still_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["✻ Baked for 11s · done 11:40 AM"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH STALL alpha: idle prompt")

    def test_b7_two_sweeps_at_an_idle_prompt_is_a_stall(self):
        self.task("alpha", frames=[idle(i) for i in range(1, 12)])
        text = self.text(self.run_all(max_sweeps="10"))
        self.assertEqual(self.one_watch(text), "WATCH STALL alpha: idle prompt")
        self.assertLessEqual(len(self.sweeps(text)), 3, text)

    def test_b7_an_idle_prompt_with_a_file_change_is_not_a_stall(self):
        t = self.task("alpha", frames=[idle(i) for i in range(1, 12)])
        self.hook(t["pane"], 'printf "%%s\\n" "HEARTBEAT alpha: work ${1}m" >> %s\n' % sh_quote(t["state"]))
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_b8_login_expired_is_a_stall_on_the_first_sweep_that_sees_it(self):
        # review fix R22: the words count on a screen that is not busy, in its last 10 lines
        for words in LOGIN_TEXTS:
            with self.subTest(words=words):
                self.setUp()
                self.task("alpha", frames=[frame(1), ["⏺ API call failed", "  ⎿  " + words] + idle(0)] + moving()[2:])
                text = self.text(self.run_all(max_sweeps="8"))
                self.assertEqual(self.one_watch(text), "WATCH STALL alpha: login expired")
                self.assertEqual(len(self.sweeps(text)), 1, text)

    def test_b9_waiting_by_design_never_stalls(self):
        for last in ("QUESTION: port?", "[Opus 5.5 xhigh] QUESTION: rules yes?", "MOCK READY alpha: mock/a.html",
                     "DONE PASS alpha", "DONE FAIL alpha: red", "CLOSE CASE alpha: finished"):
            for screen in ([STILL], [idle(0)]):
                with self.subTest(last=last, idle=screen[0] != STILL):
                    self.setUp()
                    self.task("alpha", frames=screen)
                    self.append_state("alpha", "HEARTBEAT alpha: old", last, "HEARTBEAT alpha: still waiting")
                    text = self.text(self.run_all(max_sweeps="6"))
                    self.assertEqual(self.one_watch(text), "WATCH MAX all")
                    self.assertIn("alpha waiting", self.sweeps(text)[-1])

    def test_b9_an_answered_question_is_not_waiting(self):
        for answer in ("ANSWER: 8080 | 2026-11-24 09:00", "[Opus 5.5 xhigh] ANSWER: 8080",
                       "TELL 1234abcd [Opus 5.5 xhigh] | 2026-11-24 09:10\n  ANSWER: 8080\nEND TELL 1234abcd"):
            with self.subTest(answer=answer):
                self.setUp()
                self.task("alpha", frames=[STILL])
                self.append_state("alpha", "QUESTION: port?", answer)
                text = self.text(self.run_all(max_sweeps="8"))
                self.assertEqual(self.one_watch(text), "WATCH STALL alpha: no change")

    def test_b9_login_expired_still_fires_while_waiting(self):
        self.task("alpha", frames=[frame(1), ["API Error: 401 · Please run /login"] + idle(0)])
        self.append_state("alpha", "QUESTION: port?")
        text = self.text(self.run_all(max_sweeps="6"))
        self.assertEqual(self.one_watch(text), "WATCH STALL alpha: login expired")

    def test_b10_a_stall_is_reported_once(self):
        self.task("alpha", frames=[STILL])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="10"))), "WATCH STALL alpha: no change")
        self.assertTrue(self.status()["tasks"]["alpha"]["stall"])
        text = self.text(self.run_all(max_sweeps="5"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")

    def test_b10_a_change_clears_the_reported_stall(self):
        t = self.task("alpha", frames=[STILL])
        self.run_all(max_sweeps="10")
        self.screens(t["pane"], [frame(7)])
        text = self.text(self.run_all(max_sweeps="10"))
        self.assertEqual(self.one_watch(text), "WATCH STALL alpha: no change")

    def test_b11_an_exited_pane_is_lost_at_once_with_its_cause(self):
        self.task("alpha", frames=[STILL])
        self.exited("term_alpha", from_read=2)
        text = self.text(self.run_all(max_sweeps="10"))
        self.assertEqual(self.one_watch(text), "WATCH LOST alpha: pane exited (operator_close, exit 0)")
        self.assertNotIn("STALL", text)
        self.assertEqual(len(self.sweeps(text)), 1, text)
        waits = self.terminal_calls("wait")
        self.assertTrue(waits)
        for call in waits:
            self.assertEqual(self.opt(call, "--terminal"), "term_alpha")
            self.assertEqual(self.opt(call, "--for"), "exit")
            self.assertEqual(self.opt(call, "--timeout-ms"), "2000")

    def test_b11_another_exit_cause_and_code(self):
        self.task("alpha")
        self.exited("term_alpha", from_read=2)
        cause = dict(EXITED, exitCode=137, exitCause={"kind": "signal"})
        self.write(os.path.join(self.d, "pane", "term_alpha", "exit.json"), json.dumps(cause))
        text = self.text(self.run_all())
        self.assertEqual(self.one_watch(text), "WATCH LOST alpha: pane exited (signal, exit 137)")

    def test_b11_no_cause_says_cause_unknown(self):
        self.task("alpha")
        self.exited("term_alpha", from_read=2, cause=False)
        text = self.text(self.run_all())
        self.assertEqual(self.one_watch(text), "WATCH LOST alpha: pane exited (cause unknown)")

    def test_b11_exited_at_the_first_read(self):
        self.task("alpha")
        self.exited("term_alpha", from_read=1)
        text = self.text(self.run_all(max_sweeps="10"))
        self.assertEqual(self.one_watch(text), "WATCH LOST alpha: pane exited (operator_close, exit 0)")
        self.assertLessEqual(len(self.sweeps(text)), 1, text)

    def test_b12_three_failed_reads_is_lost_with_the_orca_error(self):
        self.task("alpha", frames=[["FAIL"]])
        text = self.text(self.run_all(max_sweeps="10"))
        self.assertEqual(self.one_watch(text), "WATCH LOST alpha: orca: terminal read failed")
        self.assertLessEqual(len(self.sweeps(text)), 4, text)

    def test_b12_an_unreachable_machine_is_lost(self):
        self.task("alpha", env=ENV)
        self.repo.set_orca_env_state(ENV, "down")
        text = self.text(self.run_all(max_sweeps="10"))
        self.assertEqual(self.one_watch(text), "WATCH LOST alpha: orca: environment %s is not reachable" % ENV)

    def test_b12_a_good_read_resets_the_count(self):
        bad = ["FAIL"]
        self.task("alpha", frames=[frame(1), bad, bad, frame(2), bad, bad, frame(3), frame(4)])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="7"))), "WATCH MAX all")

    def test_b13_one_sweep_line_with_every_state(self):
        self.task("alpha")
        self.task("beta")
        self.append_state("beta", "QUESTION: port?")
        self.task("gamma", frames=[STILL])
        self.task("delta", launch=False)
        self.task("eps", frames=[frame(1), ["FAIL"]])
        self.task("zeta", frames=[idle(i) for i in range(1, 9)])
        text = self.text(self.run_all(max_sweeps="1"))
        sweeps = self.sweeps(text)
        self.assertEqual(len(sweeps), 1, text)
        line = sweeps[0]
        self.assertRegex(line, r"^%s sweep: alpha ok, " % HHMM)
        for part in ("alpha ok", "beta waiting", "gamma same 1", "delta not watched", "eps fail 1/3", "zeta idle 1"):
            self.assertIn(part, line)
        self.assertLess(line.index("alpha"), line.index("beta"))
        self.assertLess(line.index("eps"), line.index("zeta"))

    def test_b13_the_time_comes_from_date(self):
        real = "/bin/date" if os.path.exists("/bin/date") else "/usr/bin/date"
        self.repo.stub_tool("date", '#!/usr/bin/env bash\n'
                            'case "$*" in *%%H:%%M*) echo "09:41";; *) exec %s "$@";; esac\n' % real)
        self.task("alpha")
        text = self.text(self.run_all(max_sweeps="1"))
        self.assertTrue(self.sweeps(text)[0].startswith("09:41 sweep: "), text)

    def test_b14_max_and_zero_targets_keep_sweeping(self):
        text = self.text(self.run_all(max_sweeps="3"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")
        self.assertEqual(len(self.sweeps(text)), 3, text)

    def test_b15_a_new_all_watch_stops_an_older_live_one(self):
        old = subprocess.Popen(["bash", "-c", 'exec -a "agent-watch.sh --all" sleep 60'])
        self.addCleanup(self.kill, old)
        time.sleep(0.3)
        self.write_status({"pid": old.pid, "started": now_text(10), "sweep": now_text(0), "interval_min": 5,
                           "tasks": {}, "orphans": []})
        text = self.text(self.run_all(max_sweeps="1"))
        self.assertIn("watch --all: replaced pid %d" % old.pid, text)
        for _ in range(30):
            if old.poll() is not None:
                break
            time.sleep(0.1)
        self.assertIsNotNone(old.poll(), "the older watch still runs")

    def test_b15_never_stops_a_pid_that_is_not_an_all_watch(self):
        for name in ("sleep-helper", "agent-watch.sh --terminal term_1"):
            with self.subTest(name=name):
                self.setUp()
                other = subprocess.Popen(["bash", "-c", 'exec -a "%s" sleep 60' % name])
                self.addCleanup(self.kill, other)
                time.sleep(0.3)
                self.write_status({"pid": other.pid, "started": now_text(10), "sweep": now_text(0),
                                   "interval_min": 5, "tasks": {}, "orphans": []})
                text = self.text(self.run_all(max_sweeps="1"))
                self.assertNotIn("replaced pid", text)
                self.assertIsNone(other.poll(), "a pid that is not an --all watch was stopped")

    def test_b15_a_dead_pid_in_the_status_file_is_not_replaced(self):
        self.write_status({"pid": dead_pid(), "started": now_text(10), "sweep": now_text(0), "interval_min": 5,
                           "tasks": {}, "orphans": []})
        self.assertNotIn("replaced pid", self.text(self.run_all(max_sweeps="1")))

    def kill(self, proc):
        if proc.poll() is None:
            proc.send_signal(signal.SIGKILL)
            proc.wait()

    def test_b17_a_tm_pane_is_only_read(self):
        self.task("alpha")
        self.task("beta", env=ENV)
        self.on_task_read("alpha", {4: "DONE PASS alpha"})
        self.run_all(max_sweeps="8")          # run_all asserts no send to any TM pane
        for call in self.terminal_calls("send"):
            self.assertEqual(self.opt(call, "--terminal"), self.tasks["beta"]["shell"], call)

    def test_b18_the_status_file_fields(self):
        self.task("alpha")
        self.task("ghost", launch=False)
        self.run_all("--interval-min", "5", max_sweeps="2")
        st = self.status()
        for key in ("pid", "started", "sweep", "interval_min", "tasks", "orphans"):
            self.assertIn(key, st)
        self.assertIsInstance(st["pid"], int)
        self.assertRegex(st["sweep"], r"^\d{4}-\d\d-\d\d \d\d:\d\d")
        self.assertRegex(st["started"], r"^\d{4}-\d\d-\d\d \d\d:\d\d")
        self.assertIsInstance(st["orphans"], list)
        for name in ("alpha", "ghost"):
            for key in ("path", "env", "pane", "shell", "watched", "why", "signals", "confirmed", "changed",
                        "stall"):
                self.assertIn(key, st["tasks"][name], (name, key))
        a = st["tasks"]["alpha"]
        self.assertEqual((a["path"], a["pane"], a["watched"], a["signals"]),
                         (self.tasks["alpha"]["path"], "term_alpha", True, 0))
        self.assertRegex(a["confirmed"], r"^\d{4}-\d\d-\d\d \d\d:\d\d")
        self.assertFalse(st["tasks"]["ghost"]["watched"])


class TestAllReviewFixes(AllCase):
    """requirements/one-watcher.md section R: what the Opus review found that the first tests did not catch."""

    LONG_NAME = "v4plus-ledger-rollout-final-ab"     # 30 chars, a real-size name

    def test_r1_the_remote_read_command_stays_under_500_for_real_sizes(self):
        self.task(self.LONG_NAME, env=ENV, sub="orca/workspaces/v4-plus")
        self.on_task_read(self.LONG_NAME, {3: "[Opus 5.5 xhigh] DONE PASS %s" % self.LONG_NAME})
        text = self.text(self.run_all(max_sweeps="6"))
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL %s: [Opus 5.5 xhigh] DONE PASS %s"
                         % (self.LONG_NAME, self.LONG_NAME))
        for call in self.terminal_calls("send"):
            self.assertLess(len(self.opt(call, "--text") or ""), 500, call)

    def test_r1_a_command_that_would_be_500_or_more_is_never_sent(self):
        self.task("alpha", env=ENV, sub="x" * 120 + "/" + "y" * 120)
        text = self.text(self.run_all(max_sweeps="2"))
        st = self.status()["tasks"]["alpha"]
        self.assertFalse(st["watched"])
        self.assertTrue(st["why"].startswith("read command too long"), st["why"])
        self.assertIn("watch: alpha not watched: read command too long", text)
        for call in self.terminal_calls("send"):
            self.assertLess(len(self.opt(call, "--text") or ""), 500, call)

    def test_r2_a_task_not_baselined_in_a_run_keeps_its_saved_count(self):
        self.task("alpha")
        self.append_state("alpha", "[Opus 5.5 xhigh] DONE PASS alpha")
        self.run_all(max_sweeps="1")
        self.assertEqual(self.status()["tasks"]["alpha"]["signals"], 1)
        records = self.main_state_text()
        self.main_state("")                                  # run 2: no pane known, not watched
        self.run_all(max_sweeps="1")
        self.assertFalse(self.status()["tasks"]["alpha"]["watched"])
        self.assertIn(self.status()["tasks"]["alpha"]["signals"], (1, None))
        self.main_state(records)                             # run 3: watched again
        text = self.text(self.run_all(max_sweeps="3"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")

    def test_r3_a_wake_line_written_just_before_the_pane_exits_still_fires(self):
        self.task("alpha")
        self.on_task_read("alpha", {2: "DONE PASS alpha"})
        self.exited("term_alpha", from_read=2)
        text = self.text(self.run_all())
        self.assertEqual(self.watch_lines(text), ["WATCH SIGNAL alpha: DONE PASS alpha",
                                                  "WATCH LOST alpha: pane exited (operator_close, exit 0)"])

    def test_r3_lost_is_reported_once_per_pane(self):
        self.task("alpha")
        self.exited("term_alpha", from_read=2)
        self.assertEqual(self.one_watch(self.text(self.run_all())),
                         "WATCH LOST alpha: pane exited (operator_close, exit 0)")
        text = self.text(self.run_all(max_sweeps="3"))
        self.assertEqual(self.one_watch(text), "WATCH MAX all")
        self.assertIn("alpha lost", self.sweeps(text)[-1])
        self.screens("term_alpha2", moving())                # a relaunched TM: a new pane
        self.launch("tm-pane", "alpha", "term_alpha2", since="2026-11-24 09:00")
        self.on_read("term_alpha2", self.tasks["alpha"]["state"], {2: "QUESTION: back?"})
        self.assertEqual(self.one_watch(self.text(self.run_all())), "WATCH SIGNAL alpha: QUESTION: back?")

    def test_r4_an_idle_stall_is_reported_once_while_the_file_stays_the_same(self):
        self.task("alpha", frames=[idle(i) for i in range(1, 60)])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH STALL alpha: idle prompt")
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="4"))), "WATCH MAX all")
        self.append_state("alpha", "HEARTBEAT alpha: step 4 of 7, work 50m, waiting on worker 2")
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH STALL alpha: idle prompt")

    def test_r4_a_login_stall_is_reported_once_while_the_file_stays_the_same(self):
        self.task("alpha", frames=[["API Error: 401 · Please run /login"] + idle(i) for i in range(1, 60)])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH STALL alpha: login expired")
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="4"))), "WATCH MAX all")

    def test_r22_login_words_in_tool_output_on_a_busy_screen_are_no_stall(self):
        self.task("alpha", frames=[frame(i, ["  ⎿  AssertionError: 'API Error: 401 · Please run /login' != ''"])
                                   for i in range(1, 30)])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="5"))), "WATCH MAX all")

    def test_r8_the_sweeps_keep_their_cadence(self):
        self.task("alpha")
        self.write(os.path.join(self.d, "slow"), "1.5")
        start = time.time()
        text = self.text(self.run_all(env={"AGENT_WATCH_INTERVAL_S": "3"}, max_sweeps="3"))
        took = time.time() - start
        self.assertEqual(self.one_watch(text), "WATCH MAX all")
        self.assertLess(took, 14, "sleeping the whole interval after every sweep drifts (%.1f s)" % took)

    def test_r9_a_replaced_watch_says_so_and_exits_0(self):
        self.task("alpha")
        old = self.repo.popen("agent-watch.sh", "--all", "--max", "200",
                              env={"AGENT_RUNTIME": "orca", "AGENT_WATCH_INTERVAL_S": "1"}, cwd=self.repo.dir)
        self.addCleanup(lambda: old.poll() is None and old.kill())
        for _ in range(100):
            if os.path.exists(self.status_path) and self.status().get("pid") == old.pid:
                break
            time.sleep(0.1)
        self.assertEqual(self.status().get("pid"), old.pid, "the first watch never wrote its status file")
        new = self.text(self.run_all(max_sweeps="1"))
        self.assertIn("watch --all: replaced pid %d" % old.pid, new)
        out, err = old.communicate(timeout=15)
        self.assertEqual(old.returncode, 0, out + err)
        self.assertTrue([l for l in out.splitlines()
                         if re.match(r"^WATCH REPLACED all: a newer watch runs \(pid \d+\); do not restart$", l)], out)

    def test_r10_a_disconnected_or_orphaned_terminal_is_skipped(self):
        t = self.task("alpha", pane="term_new", launch=False)
        self.screens("term_old", moving())
        self.screens("term_orph", moving())
        self.terminals([{"handle": "term_old", "title": "◑ alpha Task Manager", "worktreePath": t["path"],
                         "agentIdentity": "claude", "connected": False},
                        {"handle": "term_orph", "title": "◑ alpha Task Manager", "worktreePath": t["path"],
                         "agentIdentity": "claude", "orphaned": True},
                        {"handle": "term_new", "title": "◑ alpha Task Manager", "worktreePath": t["path"],
                         "agentIdentity": "claude", "connected": True}])
        self.on_read("term_new", t["state"], {2: "DONE PASS alpha"})
        self.assertEqual(self.one_watch(self.text(self.run_all())), "WATCH SIGNAL alpha: DONE PASS alpha")
        self.assertEqual(self.status()["tasks"]["alpha"]["pane"], "term_new")

    def test_r10_the_shell_titled_for_the_task_wins(self):
        t = self.task("alpha", env=ENV, launch=False, shell="sh_alpha2")
        self.launch("tm-pane", "alpha", t["pane"], env=ENV)
        self.shell_pane("sh_dev", env=ENV)
        self.terminals([{"handle": "sh_dev", "title": "npm run dev", "worktreePath": t["path"]},
                        {"handle": "sh_alpha2", "title": "alpha shell", "worktreePath": t["path"]}], env=ENV)
        self.on_task_read("alpha", {2: "QUESTION: shell?"})
        self.assertEqual(self.one_watch(self.text(self.run_all())), "WATCH SIGNAL alpha: QUESTION: shell?")
        self.assertEqual({self.opt(c, "--terminal") for c in self.terminal_calls("send")}, {"sh_alpha2"})

    def test_r10_an_exited_shell_pane_is_resolved_again(self):
        t = self.task("alpha", env=ENV, launch=False, shell="sh_live")
        self.launch("tm-pane", "alpha", t["pane"], env=ENV)
        self.shell_pane("sh_dead", env=ENV)
        self.write(os.path.join(self.d, "shell", "sh_dead", "exited"), "")
        self.launch("shell-pane", "alpha", "sh_dead", env=ENV)
        self.terminals([{"handle": "sh_live", "title": "alpha shell", "worktreePath": t["path"]}], env=ENV)
        self.on_task_read("alpha", {3: "DONE PASS alpha"})
        text = self.text(self.run_all())
        self.assertEqual(self.one_watch(text), "WATCH SIGNAL alpha: DONE PASS alpha")
        self.assertEqual({self.opt(c, "--terminal") for c in self.terminal_calls("send")}, {"sh_live"})

    def test_r11_a_tell_after_the_last_wake_line_ends_waiting(self):
        self.task("alpha", frames=[STILL])
        self.append_state("alpha", "DONE FAIL alpha: 2 red", "TELL 1234abcd [Opus 5.5 xhigh] | 2026-11-24 09:10",
                          "  fix the 2 red tests, then report again", "END TELL 1234abcd", "")
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="8"))), "WATCH STALL alpha: no change")

    def test_r12_two_new_wake_lines_of_a_local_task_both_fire(self):
        self.task("alpha")
        t = self.tasks["alpha"]
        self.hook(t["pane"], '[ "$1" = "2" ] && printf "%%s\\n%%s\\n" "QUESTION: first?" "DONE FAIL alpha: second" >> %s\n'
                  % sh_quote(t["state"]))
        self.assertEqual(self.watch_lines(self.text(self.run_all())),
                         ["WATCH SIGNAL alpha: QUESTION: first?", "WATCH SIGNAL alpha: DONE FAIL alpha: second"])

    def test_r12_a_remote_task_says_how_many_came_before(self):
        self.task("alpha", env=ENV)
        t = self.tasks["alpha"]
        self.hook(t["pane"], '[ "$1" = "2" ] && printf "%%s\\n%%s\\n" "QUESTION: first?" "DONE FAIL alpha: second" >> %s\n'
                  % sh_quote(t["state"]))
        text = self.text(self.run_all())
        watch = self.one_watch(text)
        self.assertEqual(watch, "WATCH SIGNAL alpha: DONE FAIL alpha: second")
        self.assertEqual(self.after(text, watch)[0], "+1 earlier new wake line: read agent_state.txt")

    def test_r13_a_trim_and_a_new_line_in_one_interval_still_fires(self):
        t = self.task("alpha")
        self.append_state("alpha", "QUESTION: old? | 2026-11-10 09:00", "ANSWER: yes",
                          "QUESTION: older? | 2026-11-10 09:00", "ANSWER: no")
        after = "QUESTION: older? | 2026-11-10 09:00\nANSWER: no\nDONE PASS alpha\n"
        self.hook(t["pane"], '[ "$1" = "2" ] && printf "%%s" %s > %s\n' % (sh_quote(after), sh_quote(t["state"])))
        self.assertEqual(self.one_watch(self.text(self.run_all())), "WATCH SIGNAL alpha: DONE PASS alpha")

    # ---- bounce 2 (the reviewer's second look)

    def test_r4b_a_held_idle_stall_does_not_hide_a_login_stall(self):
        t = self.task("alpha", frames=[idle(i) for i in range(1, 60)])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH STALL alpha: idle prompt")
        self.screens(t["pane"], [["⏺ Worker 2 is done.", "  ⎿  API Error: 401 · Please run /login"] + idle(i)
                                 for i in range(1, 60)])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH STALL alpha: login expired")

    def test_r22b_login_words_above_a_tall_input_area_count(self):
        screen = (["⏺ Bash(git push)", "  ⎿  API Error: 401 · Please run /login", ""] + idle(0)[2:5] +
                  [""] + ["row %d of the status line" % i for i in range(1, 6)] +
                  ["  ⏵⏵ bypass permissions on (shift+tab to cycle)"])
        self.task("alpha", frames=[frame(1), screen])
        text = self.text(self.run_all(max_sweeps="4"))
        self.assertEqual(self.one_watch(text), "WATCH STALL alpha: login expired")

    def test_r3b_after_a_lost_a_listed_new_pane_is_watched(self):
        t = self.task("alpha")
        self.exited("term_alpha", from_read=2)
        self.assertEqual(self.one_watch(self.text(self.run_all())),
                         "WATCH LOST alpha: pane exited (operator_close, exit 0)")
        self.screens("term_new", moving())                   # relaunched from the Orca UI: no new LAUNCH record
        self.terminals([{"handle": "term_alpha", "title": "◑ alpha Task Manager", "worktreePath": t["path"],
                         "agentIdentity": "claude"},
                        {"handle": "term_new", "title": "◑ alpha Task Manager", "worktreePath": t["path"],
                         "agentIdentity": "claude"}])
        self.on_read("term_new", t["state"], {2: "QUESTION: back from the UI?"})
        self.assertEqual(self.one_watch(self.text(self.run_all())), "WATCH SIGNAL alpha: QUESTION: back from the UI?")
        self.assertEqual(self.status()["tasks"]["alpha"]["pane"], "term_new")

    def test_r9b_a_plain_sigterm_before_the_first_status_write_is_not_a_replace(self):
        self.task("alpha")
        self.write_status({"pid": dead_pid(), "started": now_text(30), "sweep": now_text(0), "interval_min": 5,
                           "tasks": {}, "orphans": []})
        self.write(os.path.join(self.d, "slow"), "3")
        proc = self.repo.popen("agent-watch.sh", "--all", "--max", "5",
                               env={"AGENT_RUNTIME": "orca", "AGENT_WATCH_INTERVAL_S": "1"}, cwd=self.repo.dir)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        time.sleep(1.5)
        proc.terminate()
        out, err = proc.communicate(timeout=20)
        self.assertNotIn("WATCH REPLACED", out + err)
        self.assertNotEqual(proc.returncode, 0)

    def test_r6b_a_failing_shell_read_names_the_orca_error(self):
        t = self.task("alpha", env=ENV)
        self.write(os.path.join(self.d, "shell", t["shell"], "fail"), "")
        text = self.text(self.run_all(max_sweeps="8"))
        self.assertEqual(self.one_watch(text), "WATCH LOST alpha: orca: terminal read failed")

    def test_r19_interval_min_must_be_above_0(self):
        for value in ("0", "-1", "x"):
            with self.subTest(value=value):
                r = self.repo.run("agent-watch.sh", "--all", "--interval-min", value, "--max", "1",
                                  env={"AGENT_RUNTIME": "orca"}, cwd=self.repo.dir, timeout=30)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("usage", (r.stdout + r.stderr).lower())


class TestOrphans(AllCase):
    def setUp(self):
        super().setUp()
        self.a = self.task("alpha")
        self.main = os.path.realpath(self.repo.dir)

    def run_orphans(self, terms, sweeps="3"):
        self.terminals(terms)
        return self.text(self.run_all(max_sweeps=sweeps))

    def orphan_lines(self, text):
        return [l for l in self.lines(text) if "watch: live pane with no task line:" in l]

    def test_b16_a_claude_pane_of_this_repo_with_no_task_line_is_an_orphan(self):
        self.todo("far", ENV, "/x/far")
        text = self.run_orphans([
            {"handle": "term_m0", "title": "Terminal 1", "worktreePath": self.main, "worktreeId": "R1::" + self.main},
            {"handle": "term_m1", "title": "✳ project Manager", "worktreePath": self.main,
             "worktreeId": "R1::" + self.main, "agentIdentity": "claude"},
            {"handle": "term_alpha", "title": "◑ alpha Task Manager", "worktreePath": self.a["path"],
             "worktreeId": "R1::" + self.a["path"], "agentIdentity": "claude"},
            {"handle": "term_far", "title": "◑ far Task Manager", "worktreePath": "/x/far",
             "worktreeId": "R1::/x/far", "agentIdentity": "claude"},
            {"handle": "term_sh", "title": "zsh", "worktreePath": "/x/ghost2", "worktreeId": "R1::/x/ghost2"},
            {"handle": "term_g", "title": "◑ ghost Task Manager", "worktreePath": "/x/ghost",
             "worktreeId": "R1::/x/ghost", "agentIdentity": "claude"},
        ])
        self.assertEqual(self.one_watch(text), "WATCH MAX all")
        hits = self.orphan_lines(text)
        self.assertEqual(len(hits), 1, text)
        self.assertRegex(hits[0], r"^%s watch: live pane with no task line: /x/ghost \(◑ ghost Task Manager\)$" % HHMM)
        self.assertEqual(self.status()["orphans"],
                         [{"path": "/x/ghost", "title": "◑ ghost Task Manager", "handle": "term_g"}])

    def test_b16_a_live_pane_of_another_repo_is_never_an_orphan(self):
        """SCOPE CHANGE 2026-11-24: each repo watches only itself."""
        text = self.run_orphans([
            {"handle": "term_m0", "title": "Terminal 1", "worktreePath": self.main, "worktreeId": "R1::" + self.main},
            {"handle": "term_p", "title": "✳ v4-pospro Manager", "worktreePath": "/Users/x/v4-pospro",
             "worktreeId": "R2::/Users/x/v4-pospro", "agentIdentity": "claude"},
            {"handle": "term_q", "title": "◑ city-tier Task Manager", "worktreePath": "/Users/x/orca/v4/city-tier",
             "worktreeId": "R2::/Users/x/orca/v4/city-tier", "agentIdentity": "claude"},
        ])
        self.assertEqual(self.orphan_lines(text), [])
        self.assertEqual(self.status()["orphans"], [])

    def test_b16_the_repo_id_from_the_worktree_list(self):
        self.worktree_list([{"id": "R1::" + self.main, "repoId": "R1", "path": self.main}])
        text = self.run_orphans([
            {"handle": "term_g", "title": "◑ ghost Task Manager", "worktreePath": "/x/ghost",
             "worktreeId": "R1::/x/ghost", "agentIdentity": "claude"},
            {"handle": "term_p", "title": "✳ v4-pospro Manager", "worktreePath": "/Users/x/v4-pospro",
             "worktreeId": "R2::/Users/x/v4-pospro", "agentIdentity": "claude"},
        ])
        self.assertEqual([o["path"] for o in self.status()["orphans"]], ["/x/ghost"])
        self.assertEqual(len(self.orphan_lines(text)), 1, text)

    def test_b16_a_path_under_the_repo_or_a_git_worktree_of_it_is_this_repo(self):
        subprocess.run(["git", "-C", self.repo.dir, "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo.dir, "commit", "-q", "-m", "seed2", "--allow-empty"], check=True,
                       capture_output=True)
        wt = os.path.join(self.repo.base, "stray-wt")
        subprocess.run(["git", "-C", self.repo.dir, "worktree", "add", "-q", "-b", "stray", wt], check=True,
                       capture_output=True)
        wt = os.path.realpath(wt)
        sub = os.path.join(self.main, "sub")
        text = self.run_orphans([
            {"handle": "term_w", "title": "✳ stray", "worktreePath": wt, "agentIdentity": "claude"},
            {"handle": "term_s", "title": "✳ sub", "worktreePath": sub, "agentIdentity": "claude"},
            {"handle": "term_p", "title": "✳ other", "worktreePath": "/Users/x/v4-pospro", "agentIdentity": "claude"},
        ])
        self.assertEqual(sorted(o["path"] for o in self.status()["orphans"]), sorted([wt, sub]))
        self.assertEqual(len(self.orphan_lines(text)), 2, text)

    def test_r10b_a_disconnected_or_orphaned_claude_pane_is_no_orphan(self):
        text = self.run_orphans([
            {"handle": "term_m0", "title": "Terminal 1", "worktreePath": self.main, "worktreeId": "R1::" + self.main},
            {"handle": "term_d", "title": "◑ old Task Manager", "worktreePath": "/x/old", "worktreeId": "R1::/x/old",
             "agentIdentity": "claude", "connected": False},
            {"handle": "term_o", "title": "◑ older Task Manager", "worktreePath": "/x/older",
             "worktreeId": "R1::/x/older", "agentIdentity": "claude", "orphaned": True},
        ])
        self.assertEqual(self.orphan_lines(text), [])
        self.assertEqual(self.status()["orphans"], [])

    def test_b16_printed_once_never_a_wake(self):
        text = self.run_orphans([
            {"handle": "term_m0", "title": "Terminal 1", "worktreePath": self.main, "worktreeId": "R1::" + self.main},
            {"handle": "term_g", "title": "◑ ghost Task Manager", "worktreePath": "/x/ghost",
             "worktreeId": "R1::/x/ghost", "agentIdentity": "claude"}], sweeps="5")
        self.assertEqual(len(self.orphan_lines(text)), 1, text)
        self.assertEqual(self.one_watch(text), "WATCH MAX all")


class TestProbe(AllCase):
    NOT = "watch: orca did not answer 3 times; a watch needs orca; not watching"

    def probe_run(self, *args, ps_fail=0, extra_env=None):
        if ps_fail:
            self.ps_fail(ps_fail)
        env = {"AGENT_WATCH_INTERVAL_S": "0", "AGENT_WATCH_RETRY_S": "0"}
        env.update(extra_env or {})
        return self.repo.run("agent-watch.sh", *args, env=env, timeout=60, cwd=self.repo.dir)

    def single_args(self):
        t = self.tasks["alpha"]
        return ["--terminal", t["pane"], "--worktree", t["real"], "--name", "alpha", "--max", "1"]

    def test_c1_plain_or_cloud_is_not_used_in_both_modes(self):
        self.task("alpha")
        for env, kind in (({"AGENT_RUNTIME": "plain"}, "plain"), ({"AGENT_RUNTIME": "cloud"}, "cloud"),
                          ({"CLAUDE_CODE_REMOTE": "true"}, "cloud")):
            for args in (["--all", "--max", "1"], self.single_args()):
                with self.subTest(env=env, args=args[0]):
                    self.repo.clear_calls()
                    result = self.probe_run(*args, extra_env=env)
                    self.assertOk(result)
                    self.assertEqual(result.stdout.strip(), "watch: not used in %s mode" % kind)
                    self.assertEqual([c for c in self.repo.calls() if c[:1] == ["terminal"]], [])

    def test_c1_agent_conf_runtime_plain(self):
        self.task("alpha")
        self.repo.set_conf("runtime", "plain")
        result = self.probe_run("--all", "--max", "1")
        self.assertOk(result)
        self.assertEqual(result.stdout.strip(), "watch: not used in plain mode")

    def test_c2_one_or_two_failed_probes_are_tried_again(self):
        for fails in (1, 2):
            with self.subTest(fails=fails):
                self.setUp()
                self.task("alpha")
                result = self.probe_run("--all", "--max", "1", ps_fail=fails)
                self.assertOk(result)
                self.assertIn("WATCH MAX all", result.stdout)
                self.assertNotIn("not used in plain mode", result.stdout)

    def test_c2_a_flaky_probe_never_makes_a_single_watch_exit_0_as_plain(self):
        self.task("alpha")
        result = self.probe_run(*self.single_args(), ps_fail=1)
        self.assertOk(result)
        self.assertIn("WATCH MAX alpha", result.stdout)

    def test_c2_three_failed_probes_exit_1_in_both_modes(self):
        self.task("alpha")
        for args in (["--all", "--max", "1"], self.single_args()):
            with self.subTest(args=args[0]):
                self.repo.clear_calls()
                result = self.probe_run(*args, ps_fail=9)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(self.NOT, result.stdout + result.stderr)
                self.assertNotIn("not used in plain mode", result.stdout + result.stderr)
                self.assertEqual(len([c for c in self.repo.calls() if c[:2] == ["worktree", "ps"]]), 3)
                self.assertEqual([c for c in self.repo.calls() if c[:1] == ["terminal"]], [])

    def test_c2_no_orca_at_all_is_three_tries_too(self):
        self.task("alpha")
        self.repo.no_orca()
        result = self.probe_run("--all", "--max", "1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(self.NOT, result.stdout + result.stderr)


class TestSingleModeAdditions(AllCase):
    """C3: the single mode keeps every rule of tests/test_agent_watch.py, plus B11 and A7/A8."""

    def single(self, name="alpha", max_sweeps="8"):
        t = self.tasks[name]
        result = self.repo.run("agent-watch.sh", "--terminal", t["pane"], "--worktree", t["real"], "--name", name,
                               "--max", max_sweeps,
                               env={"AGENT_RUNTIME": "orca", "AGENT_WATCH_INTERVAL_S": "0"}, timeout=60)
        self.assertNoSendToTm()
        self.assertOk(result)
        return result.stdout + result.stderr

    def test_c3_an_exited_pane_is_lost_at_once_never_a_stall(self):
        self.task("alpha", frames=[STILL])
        self.exited("term_alpha", from_read=2)
        text = self.single(max_sweeps="10")
        self.assertEqual(self.one_watch(text), "WATCH LOST alpha: pane exited (operator_close, exit 0)")
        self.assertNotIn("STALL", text)

    def test_c3_no_cause_says_cause_unknown(self):
        self.task("alpha")
        self.exited("term_alpha", from_read=2, cause=False)
        self.assertEqual(self.one_watch(self.single()), "WATCH LOST alpha: pane exited (cause unknown)")

    def test_c3_a_signed_line_fires(self):
        self.task("alpha")
        self.on_task_read("alpha", {2: "[Opus 5.5 xhigh] QUESTION: rules yes?"})
        self.assertEqual(self.one_watch(self.single()), "WATCH SIGNAL alpha: [Opus 5.5 xhigh] QUESTION: rules yes?")

    def test_c3_two_groups_or_a_signed_line_without_a_wake_word_do_not_fire(self):
        self.task("alpha")
        self.on_task_read("alpha", {2: "[a] [b] DONE PASS alpha", 3: "[Opus 5.5 xhigh] Brief from the main manager"})
        self.assertEqual(self.one_watch(self.single(max_sweeps="5")), "WATCH MAX alpha")


NOW = "2026-11-24 09:30"


SIG = "[Opus 5.5 xhigh]"


REFUSED = "tell: the message must start with [<model> <effort>]"


def pointer(s):
    return "%s TELL %s: read the TELL %s block at the end of agent_state.txt and act on it" % (SIG, s, s)


class TellCase(AllCase):
    def setUp(self):
        super().setUp()
        self.t = self.task("alpha", echo=True, git=True)

    def tell(self, task, msg, env=None):
        run_env = {"AGENT_RUNTIME": "orca", "AGENT_FAKE_NOW": NOW, "AGENT_TELL_ECHO_S": "1"}
        run_env.update(env or {})
        return self.repo.run("agent-file.sh", "tell", task, msg, env=run_env, timeout=90, cwd=self.repo.dir)

    def sends_to(self, handle):
        return [c for c in self.terminal_calls("send") if self.opt(c, "--terminal") == handle]

    def block_lines(self, text, s):
        lines = text.split("\n")
        i = next(i for i, l in enumerate(lines) if l.startswith("TELL %s " % s))
        j = lines.index("END TELL %s" % s, i)
        return lines[i:j + 1]


def hold_lock(path, seconds):
    """A process that holds an fcntl lock on path for seconds; returns once it holds it."""
    holder = subprocess.Popen(
        [sys.executable, "-c", "import fcntl, sys, time\nf = open(sys.argv[1], 'a')\n"
         "fcntl.flock(f, fcntl.LOCK_EX)\nprint('locked', flush=True)\ntime.sleep(float(sys.argv[2]))\n",
         path, str(seconds)], stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "locked"
    return holder


class TestTellRefusals(TellCase):
    def test_d1_an_unsigned_message_is_refused(self):
        before = self.state_text("alpha")
        for msg in ("rules yes", SIG, SIG + " ", "[Opus] hi", " [Opus 5.5 xhigh] hi", "ANSWER: [Opus 5.5 xhigh] x"):
            with self.subTest(msg=msg):
                self.repo.clear_calls()
                r = self.tell("alpha", msg)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertEqual(r.stderr.strip(), REFUSED)
                self.assertEqual(self.state_text("alpha"), before)
                self.assertEqual([c for c in self.repo.calls() if c[:1] == ["terminal"]], [])

    def test_d2_no_pane_is_refused_and_nothing_is_written(self):
        self.task("ghost", launch=False)
        before = self.state_text("ghost")
        r = self.tell("ghost", SIG + " hello")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(r.stderr.strip(), "tell: no pane for ghost: no task manager pane")
        self.assertEqual(self.state_text("ghost"), before)
        self.assertEqual(self.terminal_calls("send"), [])

    def test_d2_a_task_with_no_line_is_refused(self):
        r = self.tell("nobody", SIG + " hello")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertTrue(r.stderr.strip().startswith("tell: no pane for nobody: "), r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertEqual(self.terminal_calls("send"), [])

    def test_d2_the_status_file_comes_first(self):
        self.echo_pane("term_s")
        self.write_status({"pid": 1, "started": now_text(5), "sweep": now_text(0), "interval_min": 5, "orphans": [],
                           "tasks": {"alpha": {"path": self.t["path"], "env": None, "pane": "term_s", "shell": None,
                                               "watched": True, "why": "", "signals": 0, "confirmed": now_text(0),
                                               "changed": now_text(0), "stall": None}}})
        s = sha8(SIG + " hello")
        r = self.tell("alpha", SIG + " hello")
        self.assertOk(r)
        self.assertEqual(len(self.sends_to("term_s")), 1)
        self.assertEqual(self.sends_to(self.t["pane"]), [])
        self.assertIn("TELL OK alpha %s" % s, r.stdout)


class TestTellBlock(TellCase):
    def test_d3_the_block_exactly(self):
        msg = SIG + " ANSWER: rules yes"
        s = sha8(msg)
        self.assertEqual(s, "564b1788")
        before = self.state_text("alpha")
        r = self.tell("alpha", msg)
        self.assertOk(r)
        self.assertEqual(r.stdout.strip().splitlines()[-1], "TELL OK alpha 564b1788")
        self.assertEqual(self.state_text("alpha"),
                         before + "TELL 564b1788 [Opus 5.5 xhigh] | 2026-11-24 09:30\n"
                                  "  ANSWER: rules yes\nEND TELL 564b1788\n\n")

    def test_d3_every_message_line_is_indented(self):
        msg = SIG + " ANSWER: rules yes\n=== REPORT ===\nQUESTION: told?\n\nDONE PASS alpha\nlast line"
        s = sha8(msg)
        self.assertOk(self.tell("alpha", msg))
        text = self.state_text("alpha")
        block = self.block_lines(text, s)
        self.assertEqual(block[0], "TELL %s %s | %s" % (s, SIG, NOW))
        body = block[1:-1]
        for line in body:
            self.assertTrue(line == "" or line.startswith("  "), line)
        self.assertEqual([l[2:] for l in body], msg[len(SIG) + 1:].split("\n"))
        self.assertTrue(text.endswith("END TELL %s\n\n" % s), text[-80:])
        self.assertNotIn("\n=== REPORT ===\n", text)
        self.assertNotIn("\nQUESTION: told?", text)

    def test_d3_the_sha_is_of_the_utf8_message_as_given(self):
        msg = SIG + " 规则通过 ✓"
        r = self.tell("alpha", msg)
        self.assertOk(r)
        s = sha8(msg)
        self.assertIn("TELL OK alpha %s" % s, r.stdout)
        self.assertIn("TELL %s %s | %s\n  规则通过 ✓\nEND TELL %s\n" % (s, SIG, NOW, s), self.state_text("alpha"))

    def test_d3_a_file_without_a_last_newline_still_gets_the_block_on_its_own_line(self):
        with open(self.t["state"], "w") as fh:
            fh.write("brief line")
        s = sha8(SIG + " hello")
        self.assertOk(self.tell("alpha", SIG + " hello"))
        self.assertIn("TELL %s %s | %s" % (s, SIG, NOW), self.state_text("alpha").split("\n"))

    def test_d4_a_told_line_never_wakes_the_watch(self):
        self.assertOk(self.tell("alpha", SIG + " QUESTION: told?\nDONE PASS alpha\nMOCK READY alpha: x"))
        self.repo.clear_calls()
        text = self.text(self.run_all(max_sweeps="1"))
        self.assertNotIn("WATCH SIGNAL", text)

    def test_d4_an_indented_answer_still_answers_the_open_question(self):
        self.append_state("alpha", "QUESTION: which port? | 2026-11-24 09:00")

        def open_ones():
            r = self.repo.run("agent-file.sh", "questions", "--json", env={"AGENT_FAKE_NOW": NOW}, cwd=self.repo.dir)
            self.assertOk(r)
            return [q for q in json.loads(r.stdout)["questions"] if "which port" in q.get("title", "")]

        self.assertTrue(open_ones())
        self.assertOk(self.tell("alpha", SIG + " ANSWER: 8080"))
        self.assertEqual(open_ones(), [])


class TestTellWrite(TellCase):
    def test_d5_local_append_waits_for_the_state_lock(self):
        lock = os.path.join(self.t["real"], ".git", "agent_state.lock")
        holder = subprocess.Popen(
            [sys.executable, "-c", "import fcntl, sys, time\nf = open(sys.argv[1], 'a')\n"
             "fcntl.flock(f, fcntl.LOCK_EX)\nprint('locked', flush=True)\ntime.sleep(4)\n", lock],
            stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.wait)
        self.assertEqual(holder.stdout.readline().strip(), "locked")
        start = time.time()
        r = self.tell("alpha", SIG + " hello")
        took = time.time() - start
        self.assertOk(r)
        self.assertGreaterEqual(took, 3.0, "the block was written while the state lock was held")
        self.assertEqual(self.state_text("alpha").count("END TELL %s" % sha8(SIG + " hello")), 1)

    def test_d5_remote_chunks_through_the_shell_pane(self):
        r_t = self.task("rem", env=ENV, echo=True)
        msg = SIG + " " + "\n".join("line %03d %s" % (i, "x" * 60) for i in range(60))
        self.assertGreater(len(msg), 4000)
        s = sha8(msg)
        r = self.tell("rem", msg)
        self.assertOk(r)
        self.assertIn("TELL OK rem %s" % s, r.stdout)
        block = "TELL %s %s | %s\n" % (s, SIG, NOW) + "".join("  " + l + "\n" for l in msg[len(SIG) + 1:].split("\n")) \
            + "END TELL %s\n\n" % s
        self.assertTrue(self.state_text("rem").endswith(block))
        shell_sends = self.sends_to(r_t["shell"])
        self.assertGreaterEqual(len(shell_sends), 15, "a 4 KB block goes in many short sends")
        for call in shell_sends:
            self.assertLess(len(self.opt(call, "--text") or ""), 400, call)
            self.assertEqual(self.opt(call, "--environment"), ENV, call)
        tm = self.sends_to(r_t["pane"])
        self.assertEqual([self.opt(c, "--text") for c in tm], [pointer(s)])
        self.assertEqual(self.opt(tm[0], "--environment"), ENV)

    def test_d6_a_block_that_does_not_read_back_fails_with_no_pointer(self):
        os.remove(self.t["state"])
        os.symlink("/dev/null", self.t["state"])
        s = sha8(SIG + " hello")
        r = self.tell("alpha", SIG + " hello")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("TELL FAIL alpha %s: file check" % s, r.stdout + r.stderr)
        self.assertEqual(self.sends_to(self.t["pane"]), [])

    def test_d6_remote_a_block_that_does_not_read_back_fails(self):
        r_t = self.task("rem", env=ENV, echo=True)
        os.remove(r_t["state"])
        os.symlink("/dev/null", r_t["state"])
        s = sha8(SIG + " hello")
        r = self.tell("rem", SIG + " hello")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("TELL FAIL rem %s: file check" % s, r.stdout + r.stderr)
        self.assertEqual(self.sends_to(r_t["pane"]), [])


class TestTellPointer(TellCase):
    def test_d7_one_pointer_line_after_a_tui_idle_wait(self):
        s = sha8(SIG + " hello")
        self.assertOk(self.tell("alpha", SIG + " hello"))
        calls = self.repo.calls()
        sends = [i for i, c in enumerate(calls) if c[:2] == ["terminal", "send"] and self.opt(c, "--terminal") == "term_alpha"]
        self.assertEqual(len(sends), 1)
        send = calls[sends[0]]
        self.assertEqual(self.opt(send, "--text"), pointer(s))
        self.assertIn("--enter", send)
        waits = [i for i, c in enumerate(calls) if c[:2] == ["terminal", "wait"] and self.opt(c, "--for") == "tui-idle"]
        self.assertTrue(waits and waits[0] < sends[0], calls)
        self.assertEqual(self.opt(calls[waits[0]], "--timeout-ms"), "120000")
        self.assertEqual(self.opt(calls[waits[0]], "--terminal"), "term_alpha")

    def test_d7_a_tui_idle_timeout_still_sends(self):
        self.write(os.path.join(self.d, "pane", "term_alpha", "idle_timeout"), "")
        s = sha8(SIG + " hello")
        r = self.tell("alpha", SIG + " hello")
        self.assertOk(r)
        self.assertIn("TELL OK alpha %s" % s, r.stdout)
        self.assertEqual(len(self.sends_to("term_alpha")), 1)

    def test_d8_seen_on_screen_is_ok_read_with_cursor(self):
        s = sha8(SIG + " hello")
        r = self.tell("alpha", SIG + " hello")
        self.assertOk(r)
        self.assertEqual(r.stdout.strip().splitlines()[-1], "TELL OK alpha %s" % s)
        self.assertIn("TELL %s" % s, self.echo_buf("term_alpha"))
        reads = [c for c in self.terminal_calls("read") if self.opt(c, "--terminal") == "term_alpha"]
        self.assertTrue([c for c in reads if "--cursor" in c], reads)

    def test_d8_a_lost_pointer_is_sent_once_more(self):
        self.echo_pane("term_alpha", drop=1)
        s = sha8(SIG + " hello")
        r = self.tell("alpha", SIG + " hello")
        self.assertOk(r)
        self.assertIn("TELL OK alpha %s" % s, r.stdout)
        self.assertEqual(len(self.sends_to("term_alpha")), 2)
        idle_waits = [c for c in self.terminal_calls("wait") if self.opt(c, "--for") == "tui-idle"]
        self.assertEqual(len(idle_waits), 2)

    def test_d8_lost_twice_fails_and_the_block_stays_in_the_file(self):
        self.echo_pane("term_alpha", drop=2)
        s = sha8(SIG + " hello")
        r = self.tell("alpha", SIG + " hello")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("TELL FAIL alpha %s: pointer not seen (block is in the file)" % s, r.stdout + r.stderr)
        self.assertEqual(len(self.sends_to("term_alpha")), 2)
        self.assertEqual(self.state_text("alpha").count("END TELL %s" % s), 1)


class TestTellReviewFixes(TellCase):
    def test_r15_a_stale_pane_in_the_status_file_is_resolved_again(self):
        self.write_status({"pid": 1, "started": now_text(5), "sweep": now_text(0), "interval_min": 5, "orphans": [],
                           "tasks": {"alpha": {"path": self.t["path"], "env": "", "pane": "term_gone", "shell": "",
                                               "watched": True, "why": "", "signals": 0, "confirmed": now_text(0),
                                               "changed": now_text(0), "stall": ""}}})
        s = sha8(SIG + " hello")
        r = self.tell("alpha", SIG + " hello")
        self.assertOk(r)
        self.assertIn("TELL OK alpha %s" % s, r.stdout)
        self.assertEqual([self.opt(c, "--text") for c in self.sends_to("term_alpha")], [pointer(s)])

    def test_r15b_a_closed_shell_pane_in_the_status_file_is_resolved_again(self):
        r_t = self.task("rem", env=ENV, echo=True)
        self.shell_pane("sh_dead", env=ENV)
        self.write(os.path.join(self.d, "shell", "sh_dead", "exited"), "")
        self.write_status({"pid": 1, "started": now_text(5), "sweep": now_text(0), "interval_min": 5, "orphans": [],
                           "tasks": {"rem": {"path": r_t["path"], "env": ENV, "pane": r_t["pane"], "shell": "sh_dead",
                                             "watched": True, "why": "", "signals": 0, "confirmed": now_text(0),
                                             "changed": now_text(0), "stall": ""}}})
        s = sha8(SIG + " hello")
        r = self.tell("rem", SIG + " hello")
        self.assertOk(r)
        self.assertIn("TELL OK rem %s" % s, r.stdout)
        self.assertEqual(self.sends_to("sh_dead"), [])
        self.assertTrue(self.sends_to(r_t["shell"]))

    def test_r16_a_remote_tell_waits_for_the_shell_pane_lock(self):
        r_t = self.task("rem", env=ENV, echo=True)
        lock = self.repo.path(".git", "agent_shell_%s.lock" % r_t["shell"])
        holder = hold_lock(lock, 4)
        self.addCleanup(holder.wait)
        start = time.time()
        r = self.tell("rem", SIG + " hello")
        self.assertOk(r)
        self.assertGreaterEqual(time.time() - start, 3.0, "the shell pane was used while its lock was held")

    def test_r16_the_watch_remote_read_waits_for_the_shell_pane_lock(self):
        r_t = self.task("rem", env=ENV)
        lock = self.repo.path(".git", "agent_shell_%s.lock" % r_t["shell"])
        holder = hold_lock(lock, 4)
        self.addCleanup(holder.wait)
        start = time.time()
        self.repo.clear_calls()
        self.run_all(max_sweeps="1")
        self.assertGreaterEqual(time.time() - start, 3.0, "the watch sent to the shell pane while its lock was held")


class TestTellTuiPane(TellCase):
    """A real Claude TUI pane: the cursor read after the send has no "TELL <sha8>" line (the TUI repaints), the
    full screen has it. tell must say TELL OK and never send the pointer a second time while the first is on
    the screen (2026-11-24: the TM got it twice, tell said TELL FAIL)."""

    def test_r23_a_pointer_seen_only_on_the_full_screen_is_ok_and_sent_once(self):
        self.echo_pane("term_alpha", tui=True)
        s = sha8(SIG + " hello")
        r = self.tell("alpha", SIG + " hello")
        self.assertOk(r)
        self.assertEqual(r.stdout.strip().splitlines()[-1], "TELL OK alpha %s" % s)
        self.assertEqual(len(self.sends_to("term_alpha")), 1)
        self.assertEqual(self.echo_buf("term_alpha").count(pointer(s)), 1)   # the pointer line, once

    def test_r23_a_lost_first_pointer_on_a_tui_pane_is_sent_once_more(self):
        self.echo_pane("term_alpha", tui=True, drop=1)
        s = sha8(SIG + " hello")
        r = self.tell("alpha", SIG + " hello")
        self.assertOk(r)
        self.assertIn("TELL OK alpha %s" % s, r.stdout)
        self.assertEqual(len(self.sends_to("term_alpha")), 2)

    def test_r23_lost_twice_on_a_tui_pane_still_fails(self):
        self.echo_pane("term_alpha", tui=True, drop=2)
        s = sha8(SIG + " hello")
        r = self.tell("alpha", SIG + " hello")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("TELL FAIL alpha %s: pointer not seen (block is in the file)" % s, r.stdout + r.stderr)


STEP_NAMES = ["brief", "register", "mock", "tests", "workers", "verify", "push", "report"]


HB = "HEARTBEAT alpha: step 5 of 7, work 160m, full suite running | 2026-11-25 12:00"


class CarryCase(AllCase):
    def setUp(self):
        super().setUp()

    def carry(self, env=None, lines=(), on_read=None, name="alpha"):
        self.todo(name)
        t = self.task(name, env=env, frames=moving())
        self.append_state(name, *lines)
        self.on_task_read(name, on_read or {2: "ACK %s: still here" % name})
        return t, self.text(self.run_all(max_sweeps="4"))


class TestNewestLineDecidesTheStage(CarryCase):
    def test_a_heartbeat_newer_than_the_last_stage_line_wins(self):
        for env in (None, ENV):
            with self.subTest(env=env):
                self.setUp()
                self.carry(env, ["STAGE alpha: tests | since 2026-11-25 09:00", HB])
                self.assertIn(" | stage verify since ", self.todo_line("alpha"))

    def test_an_older_heartbeat_does_not_win(self):
        for env in (None, ENV):
            with self.subTest(env=env):
                self.setUp()
                self.carry(env, [HB, "STAGE alpha: push | since 2026-11-25 12:05"])
                line = self.todo_line("alpha")
                self.assertIn(" | stage push since ", line)
                self.assertNotIn(" | beat ", line)

    def test_a_step_line_is_a_stage_too(self):
        self.carry(None, ["STAGE alpha: tests | since 2026-11-25 09:00", "STEP 6 push: pushed the branch"])
        self.assertIn(" | stage push since ", self.todo_line("alpha"))

    def test_step_numbers_map_to_the_stage_names(self):
        for n, name in enumerate(STEP_NAMES):
            with self.subTest(step=n):
                self.setUp()
                self.carry(None, ["HEARTBEAT alpha: step %d of 7, work 5m, x | 2026-11-25 12:00" % n])
                self.assertIn(" | stage %s since " % name, self.todo_line("alpha"))

    def test_another_tasks_heartbeat_is_not_carried(self):
        self.carry(None, ["HEARTBEAT beta: step 5 of 7, work 9m, x | 2026-11-25 12:00"])
        self.assertNotIn(" | stage ", self.todo_line("alpha"))

    def test_a_heartbeat_of_the_same_stage_keeps_the_workers_fraction(self):
        self.carry(None, ["STAGE alpha: workers 1/2 | since 2026-11-25 09:00",
                          "HEARTBEAT alpha: step 4 of 7, work 30m, workers run | 2026-11-25 09:30"])
        line = self.todo_line("alpha")
        self.assertIn(" | stage workers 1/2 since ", line)
        self.assertIn(" | beat 30m workers run", line)

    def test_the_printed_line_names_the_stage(self):
        _, text = self.carry(None, [HB])
        self.assertTrue([l for l in self.lines(text) if re.match(r"^%s stage alpha: verify$" % HHMM, l)], text)
        self.assertTrue([l for l in self.lines(text) if re.match(r"^%s beat alpha: 160m full suite running$" % HHMM, l)], text)


class TestRunningWorkIsNotAStall(AllCase):
    STALL = "WATCH STALL alpha: idle prompt"

    def test_idle_prompt_with_a_shell_and_a_monitor_count_is_not_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["  ⏵⏵ bypass permissions on · 1 shell, 1 monitor"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_idle_prompt_with_only_a_shell_count_is_not_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["  1 shell"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_idle_prompt_with_a_zero_count_is_a_stall(self):
        self.task("alpha", frames=[idle(0) + ["  0 shells"]])
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), self.STALL)

    def test_a_started_line_holds_the_stall(self):
        for env in (None, ENV):
            with self.subTest(env=env):
                self.setUp()
                self.task("alpha", env=env, frames=[idle(0)])
                self.append_state("alpha", "STEP 5 verify: full suite started on pc2, about 30m")
                self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), "WATCH MAX all")

    def test_a_started_line_holds_only_for_watch_quiet_min(self):
        t = self.task("alpha", frames=[idle(0)])
        self.append_state("alpha", "STEP 5 verify: full suite started on pc2, about 30m")
        old = os.path.getmtime(t["state"]) - 3600
        os.utime(t["state"], (old, old))
        self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), self.STALL)

    def test_a_real_idle_prompt_still_stalls(self):
        for env in (None, ENV):
            with self.subTest(env=env):
                self.setUp()
                self.task("alpha", env=env, frames=[idle(0)])
                self.append_state("alpha", "STEP 5 verify: suite finished, 0 failures")
                self.assertEqual(self.one_watch(self.text(self.run_all(max_sweeps="6"))), self.STALL)


FAKE_HK = r"""#!/usr/bin/env bash
printf '%s\t%s\t%s\n' "$*" "${CLAUDE_PID:-}" "${AGENT_ROLE:-}" >> "@LOG@"
if [ -f "@LOG@.stamp" ]; then
  printf '%s %s\n' "$(date +%s)" "$(date '+%Y-%m-%d %H:%M')" > "@STAMP@"
fi
exit 0
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


class HkCase(AllCase):
    def setUp(self):
        super().setUp()
        r = self.repo
        r.set_conf("runtime", "orca")
        r.set_conf("housekeep_interval_min", "120")
        self.hk_log = os.path.join(r.base, "hk_calls.log")
        open(self.hk_log, "w").close()
        self.stamp = r.path(".git", "agent_housekeep.last")
        r.write_bin_script("agent-housekeep.sh", FAKE_HK.replace("@LOG@", self.hk_log)
                           .replace("@STAMP@", self.stamp))
        self.task("alpha", "working")

    def lock(self, pid):
        write(self.repo.path(".git", "agent_main.lock"), "%d 2026-11-13 10:00 - -\n" % pid)

    def set_stamp(self, minutes_ago):
        when = time.time() - minutes_ago * 60
        write(self.stamp, "%d %s\n" % (when, time.strftime("%Y-%m-%d %H:%M", time.localtime(when))))

    def hk_calls(self):
        with open(self.hk_log) as fh:
            return [l.rstrip("\n").split("\t") for l in fh if l.strip()]

    def watch(self, **env):
        return self.run_all(max_sweeps="4", env=env)


class TestHousekeepTimerRuns(HkCase):
    def test_due_with_no_stamp_runs_once_as_the_lock_owner(self):
        self.lock(os.getpid())
        open(self.hk_log + ".stamp", "w").close()   # the fake writes the stamp like the real one
        self.watch()
        self.assertEqual(self.hk_calls(), [["--apply", str(os.getpid()), ""]])

    def test_an_old_stamp_is_due(self):
        self.lock(os.getpid())
        self.set_stamp(121)
        self.watch()
        self.assertTrue(self.hk_calls())

    def test_a_stamp_that_does_not_read_is_due(self):
        self.lock(os.getpid())
        write(self.stamp, "garbage\n")
        self.watch()
        self.assertTrue(self.hk_calls())

    def test_a_missing_key_means_120(self):
        self.lock(os.getpid())
        self.repo.unset_conf("housekeep_interval_min")
        self.set_stamp(100)
        self.watch()
        self.assertEqual(self.hk_calls(), [])
        self.set_stamp(125)
        self.watch()
        self.assertTrue(self.hk_calls())

    def test_the_interval_is_the_conf_value(self):
        self.lock(os.getpid())
        self.repo.set_conf("housekeep_interval_min", "30")
        self.set_stamp(31)
        self.watch()
        self.assertTrue(self.hk_calls())

    def test_the_pass_does_not_end_the_watch(self):
        self.lock(os.getpid())
        out = self.text(self.watch())
        self.assertEqual(self.one_watch(out), "WATCH MAX all")
        self.assertTrue(self.hk_calls())


class TestHousekeepTimerDoesNotRun(HkCase):
    def test_a_fresh_stamp_is_not_due(self):
        self.lock(os.getpid())
        self.set_stamp(30)
        self.watch()
        self.assertEqual(self.hk_calls(), [])

    def test_interval_zero_is_off(self):
        self.lock(os.getpid())
        self.repo.set_conf("housekeep_interval_min", "0")
        self.watch()
        self.assertEqual(self.hk_calls(), [])

    def test_no_lock_no_pass(self):
        self.watch()
        self.assertEqual(self.hk_calls(), [])

    def test_a_dead_lock_owner_no_pass(self):
        self.lock(999999)
        self.watch()
        self.assertEqual(self.hk_calls(), [])

    def test_a_watch_of_a_spawned_agent_never_runs_it(self):
        self.lock(os.getpid())
        self.watch(AGENT_ROLE="task-manager")
        self.assertEqual(self.hk_calls(), [])


class TestNewestValidLine(unittest.TestCase):
    """C50: a malformed newest heartbeat must not hide the valid STAGE line before it."""

    def run_remote(self, lines):
        sys.path.insert(0, BIN)
        import agent_watch
        d = tempfile.mkdtemp(prefix="cb_remote_")
        self.addCleanup(subprocess.run, ["rm", "-rf", d])
        with open(os.path.join(d, "agent_state.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))
        out = subprocess.run(["bash", "-c", agent_watch.remote_command(d)], capture_output=True, text=True).stdout
        m = re.search(r"FSIG \S* \S+ \S* [01] (.*)\|", out)
        self.assertTrue(m, out)
        return m.group(1)

    def test_a_malformed_heartbeat_is_skipped(self):
        got = self.run_remote(["STAGE test-slim: workers | since 2026-11-25 12:00",
                               "HEARTBEAT step 4. building the slim pack"])
        self.assertTrue(got.startswith("STAGE test-slim: workers"), got)

    def test_a_valid_heartbeat_wins_when_newest(self):
        got = self.run_remote(["STAGE test-slim: tests | since 2026-11-25 12:00",
                               "HEARTBEAT test-slim: step 4 of 7, work 40m, workers 1 of 2 | 2026-11-25 13:00"])
        self.assertTrue(got.startswith("HEARTBEAT test-slim: step 4 of 7"), got)


class TestTellReminder(TellCase):
    """C53: the tell text reminds the main manager to add minutes when the message adds work."""

    def test_the_line_before_tell_ok(self):
        msg = SIG + " one more section for you"
        r = self.tell("alpha", msg)
        self.assertOk(r)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(lines[-1], "TELL OK alpha %s" % sha8(msg))
        self.assertEqual(lines[-2], 'if this message adds work: agent-file.sh todo est "alpha" +<minutes>')


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
        self.assertEqual(self.one_watch(text), "WATCH ROOM q: can start (run agent-file.sh next)")
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


class TestHeartbeatBeat(CarryCase):
    def test_work_minutes_and_text_are_carried(self):
        for env in (None, ENV):
            with self.subTest(env=env):
                self.setUp()
                self.carry(env, [HB])
                self.assertIn(" | beat 160m full suite running", self.todo_line("alpha"))

    def test_a_newer_heartbeat_replaces_the_beat_in_place(self):
        self.carry(None, [HB], on_read={2: "HEARTBEAT alpha: step 5 of 7, work 175m, suite done | 2026-11-25 12:15"})
        line = self.todo_line("alpha")
        self.assertEqual(line.count(" | beat "), 1, line)
        self.assertIn(" | beat 175m suite done", line)

    def test_the_board_shows_the_beat_after_the_bar(self):
        self.carry(None, [HB])
        board = self.repo.run("agent-file.sh", "board")
        self.assertIn("160m full suite running", board.stdout, board.stdout + board.stderr)

    def test_the_remote_command_is_one_call_per_sweep_under_500(self):
        t, _ = self.carry(ENV, [HB])
        sends = [c for c in self.terminal_calls("send") if self.opt(c, "--terminal") == t["shell"]]
        self.assertTrue(sends)
        for call in sends:
            self.assertLess(len(self.opt(call, "--text") or ""), 500, call)
        reads = [c for c in self.terminal_calls("read")
                 if self.opt(c, "--terminal") == t["shell"] and "--cursor" in c]
        self.assertLessEqual(len(reads), len(sends) * 20)
        tm_reads = [c for c in self.terminal_calls("read") if self.opt(c, "--terminal") == t["pane"]]
        self.assertLessEqual(len(sends), len(tm_reads))

    def test_the_remote_command_fits_paths_of_80_110_and_140_chars(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
        import agent_watch
        for n in (80, 110, 140):
            with self.subTest(path=n):
                path = ("/home/maverick/orca/workspaces/" + "x" * 200)[:n - len("/agent_state.txt")]
                cmd = agent_watch.remote_command(path)
                self.assertEqual(len(path + "/agent_state.txt"), n)
                self.assertLess(len(cmd), agent_watch.REMOTE_CMD_MAX)
                print("path %d: command %d chars, headroom %d" % (n, len(cmd), agent_watch.REMOTE_CMD_MAX - 1 - len(cmd)))

    def test_a_long_path_is_watched_remotely(self):
        self.todo("alpha")
        t = self.task("alpha", env=ENV, sub="a" * 60)
        self.assertGreaterEqual(len(t["path"]), 80)
        self.append_state("alpha", HB)
        text = self.text(self.run_all(max_sweeps="3"))
        self.assertTrue(self.status()["tasks"]["alpha"]["watched"], text)
        self.assertIn(" | stage verify since ", self.todo_line("alpha"))


if __name__ == "__main__":
    unittest.main()
