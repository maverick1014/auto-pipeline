"""Failing tests for bin/agent-watch.sh. Written by the task manager first.

Owner, 2026-11-04 ("do it also"): a task manager's DONE PASS sat 19 minutes
unseen. The main manager's watch read only the pane; the report was in the
worktree's agent_state.txt. The watch becomes a plugin script, so every repo's
main manager catches both.

CONTRACT.

    bin/agent-watch.sh --terminal <TM handle> --worktree <path>
                       [--environment <env>] [--shell <shell handle>]
                       [--interval-min 5] [--max 36] [--name <task>]

    Foreground. The main manager starts it with Bash run_in_background and is
    woken when it exits. Every WATCH exit is exit code 0.
    Missing --terminal or --worktree, or --environment without --shell:
    a usage line, exit code not 0, no sweep.

    runtime    bin/agent-runtime.sh kind. plain or cloud: exactly one line
               "watch: not used in <kind> mode", exit 0, no orca terminal call.

    interval   --interval-min minutes between sweeps (default 5).
               AGENT_WATCH_INTERVAL_S (seconds) wins when set; tests use 0.

    signals    each sweep reads two things:
               (a) the TM pane: orca terminal read --terminal <TM> --json
               (b) agent_state.txt in the worktree: the lines that START with
                   "DONE PASS", "DONE FAIL", "CLOSE CASE", "QUESTION:" or
                   "MOCK READY".
                   Local (no --environment): read the file directly, no shell
                   pane, no orca terminal send at all.
                   Another machine: through the --shell pane. Read it first
                   for latestCursor, send ONE command shorter than 400 chars
                   that prints one marker line (count + last such line), read
                   the answer with --cursor. Every orca call carries
                   --environment <env>.
               The file count at start is the baseline: only new lines fire.
               The screen never fires a SIGNAL (SCOPE ADD 1, main manager
               17:41: a TM's plan line "⏺ ... then write DONE PASS ..." fired
               it). The screen is read for the stall and the sweep line only.

    exits      the WATCH line first, then the evidence:
               "WATCH SIGNAL <name>: <line>"  a new file line (the line itself)
               "WATCH STALL <name>"  3 sweeps, same screen, no file change
                   (file = signal count and line count), unless the screen
                   says "shell still running"; then the last 15 screen lines
               "WATCH LOST <name>"   3 failed reads in a row
               "WATCH MAX <name>"    --max sweeps done
               <name> = --name, else the worktree folder's name.

    sweep      each sweep prints one line: the time from `date` (HH:MM),
               same=<n>, file=<n>, then " | " and the last ⏺ or ✻ screen line
               cut to 110 characters.

    never      sends anything to the TM pane. The shell pane gets only the
               read command.

The fake orca below keeps state under $ORCA_STUB_DIR:
    screens/<handle>/1..n   the k-th read of a pane returns frame min(k, n);
                            a frame whose first line is FAIL makes the read fail
    screens/<handle>/hook.sh  run with k after the k-th read (appends lines to
                            agent_state.txt, the way a task manager does)
    shell/<handle>/buf      a shell pane: a send runs the text with bash and
                            appends "$ <text>" and its output; a read returns
                            the lines after --cursor, latestCursor = line count
    env/<env>/down          that machine is unreachable: every call fails
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase  # noqa: E402

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
    def test_plain_is_not_used(self):
        result = self.watch(env={"AGENT_RUNTIME": "plain"})
        self.assertOk(result)
        self.assertEqual(result.stdout.strip(), "watch: not used in plain mode")
        self.assertEqual([c for c in self.repo.calls() if c[:1] == ["terminal"]], [])

    def test_cloud_is_not_used(self):
        result = self.watch(env={"AGENT_RUNTIME": "cloud"})
        self.assertOk(result)
        self.assertEqual(result.stdout.strip(), "watch: not used in cloud mode")
        self.assertEqual([c for c in self.repo.calls() if c[:1] == ["terminal"]], [])

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

    def test_the_signal_ends_the_watch_at_once(self):
        self.screens(self.moving())
        self.append_on_read(2, "DONE PASS feat")
        text = self.out(self.watch(max_sweeps="20"))
        self.assertLessEqual(len(self.sweeps(text)), 3, text)


class TestScreenNeverFires(WatchCase):
    """SCOPE ADD 1: only file lines fire. The screen feeds the stall and the
    sweep line, nothing else."""

    DONE = ["⏺ DONE PASS feat", "", "  Result: 42 tests OK"]

    def test_a_new_done_line_on_screen_does_not_fire(self):
        self.screens(self.moving(extra_at=3, extra=self.DONE))
        text = self.out(self.watch(max_sweeps="5"))
        self.assertNotIn("WATCH SIGNAL", text)
        self.assertEqual(self.watch_line(text), "WATCH MAX feat")

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
        self.assertEqual(line.count(" | stage "), 1, line)
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


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def section(text, start, end):
    lines = text.splitlines()
    begin = next(i for i, line in enumerate(lines) if line.startswith(start))
    stop = next(i for i in range(begin + 1, len(lines)) if lines[i].startswith(end))
    return "\n".join(lines[begin:stop])


class TestText(unittest.TestCase):
    def test_principles_watch_rule_names_the_script_and_the_report_block(self):
        w15 = section(read("PRINCIPLES.md"), "W15. Watch", "W16.")
        line = next((l for l in w15.splitlines() if "agent-watch.sh" in l), "")
        self.assertTrue(line, "W15 has no agent-watch.sh line")
        for word in ("=== REPORT ===", "agent_state.txt", "background",
                     "another machine"):
            self.assertIn(word, line)

    def test_dispatch_starts_the_watch_after_the_launch_check(self):
        text = read("skills", "dispatch", "SKILL.md")
        steps = section(text, "# /dispatch", "## Board records")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-watch.sh", steps)
        at = steps.index("agent-watch.sh")
        self.assertLess(steps.index("terminal wait"), at)
        near = steps[max(0, at - 300):at + 1200]
        for word in ("run_in_background", "--environment", "--shell", "again",
                     "merged", "MOCK READY"):
            self.assertIn(word, near)
        # SCOPE ADD 1: the screen no longer fires
        block = steps[at:steps.index("ListAgents", at)]
        self.assertNotIn("⏺", block)
        self.assertNotIn("on screen", block)

    def test_dispatch_brief_mock_step_names_mock_ready(self):
        brief = section(read("skills", "dispatch", "SKILL.md"),
                        "## Task manager brief", "## Cross-repo brief")
        mock = next(l for l in brief.splitlines() if l.startswith(" 2 mock"))   # progress-bar: the line now starts with its stage call
        self.assertIn("MOCK READY", mock)
        self.assertIn("agent_state.txt", mock)

    def test_dispatch_brief_names_the_report_block(self):
        brief = section(read("skills", "dispatch", "SKILL.md"),
                        "## Task manager brief", "## Cross-repo brief")
        report = next(l for l in brief.splitlines() if l.startswith("REPORT:"))
        self.assertIn("=== REPORT ===", report)
        self.assertIn("agent_state.txt", report)

    def test_readme_names_the_watch_script(self):
        self.assertIn("bin/agent-watch.sh", read("README.md"))


if __name__ == "__main__":
    unittest.main()
