"""Failing tests for `bin/agent-file.sh tell <task> "<msg>"` (requirements/one-watcher.md D1-D8, owner
rules yes 2026-11-24). Written by the task manager first.

CONTRACT (short; the table is the full rule)

    agent-file.sh tell <task> "[<model> <effort>] <text>"
        1. refuse an unsigned message (D1) or a task with no pane (D2): one stderr line, exit 1,
           nothing written, nothing sent
        2. pane, env, shell: the status file (<git common dir>/agent_watch.json), else the all-mode
           rules A3-A5 (LAUNCH records, orca terminal list)
        3. append the block to the task's worktree agent_state.txt (D3): local under the state lock
           (D5), remote in base64 chunks of at most 300 characters through the shell pane, then one
           command decodes and appends
               TELL <sha8> <signature> | <YYYY-MM-DD HH:MM>
                 <message line 1 after the signature>
                 <message line 2>
               END TELL <sha8>
               <one blank line>
           sha8 = first 8 hex of sha256(<msg> as given, UTF-8)
        4. read the block back (D6); wrong twice -> "TELL FAIL <task> <sha8>: file check", exit 1
        5. orca terminal wait --for tui-idle --timeout-ms 120000 (a timeout still sends), then one line
           into the TM pane (D7):
               <signature> TELL <sha8>: read the TELL <sha8> block at the end of agent_state.txt and act on it
        6. read the TM pane with --cursor up to AGENT_TELL_ECHO_S seconds (default 10; tests use 1) for
           "TELL <sha8>" (D8); not seen -> one more wait + send; seen -> "TELL OK <task> <sha8>", exit 0;
           still not -> "TELL FAIL <task> <sha8>: pointer not seen (block is in the file)", exit 1
    AGENT_FAKE_NOW gives the date (as every agent-file.sh verb).
"""

import json
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from watchhelp import ENV, AllCase, now_text, sha8  # noqa: E402

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


# ---------------------------------------------------------------- D1, D2: refusals


class TestRefusals(TellCase):
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


# ---------------------------------------------------------------- D3, D4: the block


class TestBlock(TellCase):
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


# ---------------------------------------------------------------- D5, D6: write and read back


class TestWrite(TellCase):
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


# ---------------------------------------------------------------- D7, D8: pointer and echo


class TestPointer(TellCase):
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



# ---------------------------------------------------------------- R: review fixes (Opus review 2026-11-24)


def hold_lock(path, seconds):
    """A process that holds an fcntl lock on path for seconds; returns once it holds it."""
    holder = subprocess.Popen(
        [sys.executable, "-c", "import fcntl, sys, time\nf = open(sys.argv[1], 'a')\n"
         "fcntl.flock(f, fcntl.LOCK_EX)\nprint('locked', flush=True)\ntime.sleep(float(sys.argv[2]))\n",
         path, str(seconds)], stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "locked"
    return holder


class TestReviewFixes(TellCase):
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


if __name__ == "__main__":
    unittest.main()
