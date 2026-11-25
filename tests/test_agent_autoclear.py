"""state-trim: the start-text warning and the auto /clear at the 2nd compaction (level 4).

The rules are requirements/state-trim.md, sections A4, A5, A6 (G4), A7 (owner "rules yes" 2026-11-20).

CONTRACT (short; the doc wins where this is shorter):
  agent-start.sh, every branch that prints the state block (normal start, compaction, clear):
    more than state_warn_lines (300) non-empty lines -> one line right before the state block:
    "STATE LONG: agent_state.txt has <n> lines (over <w>). Trim: <plugin>/bin/agent-file.sh state trim --dry-run, then state trim"
  agent-start.sh, compaction branch (SessionStart source compact):
    count >= compact_clear_at (2), runtime orca, ORCA_TERMINAL_HANDLE set, orca on PATH:
      "LIMIT: compacted <n> times. Save agent_state.txt now, then stop. This pane gets a save prompt and /clear at its next idle prompt (S8)."
      appends "AUTO CLEAR queued: compacted <n> times | <date>" to the state file and starts
      <plugin>/bin/agent-autoclear.sh <handle> <session id> detached (cwd = the state folder,
      output to /dev/null), unless the pid file <git dir>/agent_autoclear_<session id> names a live process
    no pane (plain, cloud, no handle, no orca):
      "LIMIT: compacted <n> times. No pane to type into: save agent_state.txt, then tell the human to type /clear."
    compact_clear_at=0: today's line "LIMIT: compacted <n> times. Write agent_state.txt, end this session, restart from the file (S8, S2)."
  agent-start.sh, clear branch: the compaction count of that session starts again at 0.
  agent-autoclear.sh <handle> <session id>   (foreground; the hook detaches it)
    writes its pid to <git dir>/agent_autoclear_<session id>, removes it when it ends
    before each typed text: `orca terminal wait --terminal <h> --for tui-idle ...` (an error whose
    code holds "timeout": wait again; any other error: failed), then `orca terminal read --terminal <h> --json`:
    the last tail line starting with "❯" must have nothing after the "❯" but spaces; else (text, or
    no "❯" line) wait compact_clear_check_sec, check again, and append once
    "AUTO CLEAR waiting: input box not empty | <date>"
    types, each with `orca terminal send --terminal <h> --text <text> --enter`:
      2 "AUTO CLEAR: save agent_state.txt now (S8), nothing else. /clear comes next."
      4 "/clear"
      6 "/goal <text of the last GOAL: line>"  or, with no GOAL: line,  "CLEARED: continue from agent_state.txt (S8)."
    then appends "AUTO CLEAR done | <date>"
    a failed orca call: appends "AUTO CLEAR failed at step <n>: <error code> | <date>" and stops
    (steps: 1 wait, 2 save prompt, 3 wait, 4 /clear, 5 wait, 6 goal or continue)
    AGENT_FAKE_NOW replaces the clock.
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase, children_of  # noqa: E402
from test_output_hook import pointer_part  # noqa: E402

NOW = "2026-11-20 12:00"
HANDLE = "term_t1"
SAVE = "AUTO CLEAR: save agent_state.txt now (S8), nothing else. /clear comes next."
CONT = "CLEARED: continue from agent_state.txt (S8)."
GOAL = ("task manager goal-x: done when DONE PASS or DONE FAIL is written under === REPORT === in "
        "agent_state.txt and the branch is pushed, or a QUESTION:, MOCK READY or CLOSE CASE line waits "
        "for an answer, or you saved agent_state.txt after an AUTO CLEAR notice")
LIMIT_PANE = ("LIMIT: compacted %d times. Save agent_state.txt now, then stop. This pane gets a save prompt "
              "and /clear at its next idle prompt (S8).")
LIMIT_NO_PANE = ("LIMIT: compacted %d times. No pane to type into: save agent_state.txt, then tell the "
                 "human to type /clear.")
LIMIT_OLD = "LIMIT: compacted %d times. Write agent_state.txt, end this session, restart from the file (S8, S2)."
STAMP = r"\d{4}-\d\d-\d\d \d\d:\d\d"

# A stub orca for the waiter: logs every call; answers from files in $ORCA_STUB_DIR:
#   wait_sleep (seconds), wait_fail_once (JSON, used once), wait_fail (JSON, every time),
#   read1.json read2.json ... (the n-th read), read_default.json (every later read),
#   send_fail (JSON, every send fails)
WAITER_STUB = r"""#!/usr/bin/env bash
{ printf 'CALL'; for a in "$@"; do printf '\t%s' "$a"; done; printf '\n'; } >> "$ORCA_STUB_LOG"
d="$ORCA_STUB_DIR"
case "${1:-} ${2:-}" in
  "terminal wait")
    [ -f "$d/wait_sleep" ] && sleep "$(cat "$d/wait_sleep")"
    if [ -f "$d/wait_fail_once" ]; then cat "$d/wait_fail_once"; rm -f "$d/wait_fail_once"; exit 1; fi
    if [ -f "$d/wait_fail" ]; then cat "$d/wait_fail"; exit 1; fi
    printf '{"ok":true,"result":{"terminal":{"handle":"x","status":"running"}}}\n';;
  "terminal read")
    n=$(cat "$d/read_n" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$d/read_n"
    if [ -f "$d/read$n.json" ]; then cat "$d/read$n.json"; else cat "$d/read_default.json"; fi;;
  "terminal send")
    if [ -f "$d/send_fail" ]; then cat "$d/send_fail"; exit 1; fi
    t=""; prev=""; for a in "$@"; do [ "$prev" = "--text" ] && t=$a; prev=$a; done
    [ -f "$d/send_hook.sh" ] && bash "$d/send_hook.sh" "$t"
    printf '{"ok":true,"result":{}}\n';;
  *) printf '{"ok":true,"result":{}}\n';;
esac
"""

RULE = "─" * 60


def pane(box=None, extra_top=()):
    """A pane read: box None = empty input box, else the text typed in it."""
    tail = list(extra_top) + ["⏺ Done.", "", RULE + " goal-x Task",
                              "❯" if box is None else "❯ " + box, RULE,
                              "  ⏵⏵ bypass permissions on (shift+tab to cycle) · esc to interrupt"]
    return {"ok": True, "result": {"terminal": {"handle": HANDLE, "status": "running", "tail": tail}}}


class ClearCase(ScriptCase):
    script = "agent-start.sh"

    def setUp(self):
        super().setUp()
        self.stub = os.path.join(self.repo.bin, "orca")
        with open(self.stub, "w") as fh:
            fh.write(WAITER_STUB)
        os.chmod(self.stub, 0o755)
        self.set_read_default(pane())
        self.addCleanup(self.kill_waiters)

    # ---- stub control

    def stub_file(self, name, data):
        with open(os.path.join(self.repo.orca_dir, name), "w") as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False))

    def set_read_default(self, data):
        self.stub_file("read_default.json", data)

    def set_reads(self, *datas):
        for i, data in enumerate(datas, 1):
            self.stub_file("read%d.json" % i, data)

    def calls(self):
        return self.repo.calls()

    def sends(self):
        out = []
        for c in self.calls():
            if c[:2] == ["terminal", "send"]:
                self.assertIn("--terminal", c)
                self.assertEqual(c[c.index("--terminal") + 1], HANDLE)
                self.assertIn("--enter", c)
                out.append(c[c.index("--text") + 1])
        return out

    def verbs(self):
        return [c[1] for c in self.calls() if c and c[0] == "terminal"]

    # ---- files

    @property
    def state_path(self):
        return self.repo.path("agent_state.txt")

    def write_state(self, lines):
        with open(self.state_path, "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def state_lines(self):
        if not os.path.exists(self.state_path):
            return []
        with open(self.state_path) as fh:
            return fh.read().splitlines()

    def pid_file(self, sid="s1"):
        return self.repo.path(".git", "agent_autoclear_%s" % sid)

    def kill_waiters(self):
        for name in os.listdir(self.repo.path(".git")):
            if not name.startswith("agent_autoclear_"):
                continue
            try:
                with open(self.repo.path(".git", name)) as fh:
                    pid = int(fh.read().split()[0])
            except (ValueError, IndexError, OSError):
                continue
            for victim in children_of(pid) + [pid]:
                try:
                    os.kill(victim, signal.SIGTERM)
                except OSError:
                    pass

    # ---- running

    def waiter(self, sid="s1", env=None):
        full = {"AGENT_FAKE_NOW": NOW}
        full.update(env or {})
        return self.repo.run("agent-autoclear.sh", HANDLE, sid, env=full, timeout=60)

    def hook(self, source, sid="s1", env=None, runtime="orca", handle=HANDLE):
        full = {"AGENT_ROLE": "task-manager", "AGENT_START_DEDUPE_SEC": "0"}
        if runtime:
            full["AGENT_RUNTIME"] = runtime
        if handle:
            full["ORCA_TERMINAL_HANDLE"] = handle
        full.update(env or {})
        stdin = json.dumps({"cwd": self.repo.dir, "session_id": sid, "source": source})
        return self.repo.run("agent-start.sh", stdin=stdin, env=full, timeout=30)

    def wait_for(self, check, seconds=10):
        end = time.time() + seconds
        while time.time() < end:
            if check():
                return True
            time.sleep(0.2)
        return check()


# =============================================================== A4 the start warning


class TestStartWarning(ClearCase):
    def warn(self, n, w=300):
        return ("STATE LONG: agent_state.txt has %d lines (over %d). Trim: %s/bin/agent-file.sh state trim "
                "--dry-run, then state trim" % (n, w, self.repo.plugin))

    def lines_file(self, n):
        self.write_state(["line %d" % i for i in range(1, n + 1)])

    def test_301_lines_warn_right_before_the_state_block(self):
        self.lines_file(301)
        out = self.assertOk(self.repo.run("agent-start.sh", env={"AGENT_ROLE": "task-manager"}))
        rows = out.splitlines()
        self.assertIn(self.warn(301), rows)
        i = rows.index(self.warn(301))
        self.assertTrue(rows[i + 1].startswith("agent_state.txt: 301 lines"), rows[i + 1])

    def test_300_lines_do_not(self):
        self.lines_file(300)
        out = self.assertOk(self.repo.run("agent-start.sh", env={"AGENT_ROLE": "task-manager"}))
        self.assertNotIn("STATE LONG", out)

    def test_blank_lines_do_not_count(self):
        with open(self.state_path, "w") as fh:
            fh.write("".join("line %d\n\n" % i for i in range(1, 301)))
        out = self.assertOk(self.repo.run("agent-start.sh", env={"AGENT_ROLE": "task-manager"}))
        self.assertNotIn("STATE LONG", out)

    def test_compaction_and_clear_warn_too(self):
        self.lines_file(301)
        for source in ("compact", "clear"):
            with self.subTest(source=source):
                out = self.assertOk(self.hook(source, sid="w-" + source, runtime="plain", handle=None))
                self.assertIn(self.warn(301), out.splitlines())

    def test_it_still_fits_the_preview(self):
        self.lines_file(1500)
        out = pointer_part(self.assertOk(self.repo.run("agent-start.sh", env={"AGENT_ROLE": "task-manager"})))
        self.assertLess(len(out.encode()), 2048, out)
        self.assertIn("STATE LONG: agent_state.txt has 1500 lines", out)


# =============================================================== A5 the compaction branch


class TestCompactionBranch(ClearCase):
    def setUp(self):
        super().setUp()
        self.stub_file("wait_sleep", "30")   # a started waiter blocks in its first wait

    def test_the_first_compaction_starts_nothing(self):
        out = self.assertOk(self.hook("compact"))
        self.assertIn("COMPACTED 1 time(s) this session", out)
        self.assertNotIn("LIMIT", out)
        time.sleep(1)
        self.assertFalse(os.path.exists(self.pid_file()))
        self.assertEqual(self.calls(), [])

    def test_the_second_compaction_queues_the_clear_and_returns_at_once(self):
        self.write_state(["ROLE: x", ""])
        self.assertOk(self.hook("compact"))
        t0 = time.time()
        out = self.assertOk(self.hook("compact"))
        self.assertLess(time.time() - t0, 10, "the hook must not wait for the waiter")
        self.assertIn(LIMIT_PANE % 2, out.splitlines())
        self.assertRegex(self.state_lines()[-1], r"^AUTO CLEAR queued: compacted 2 times \| %s$" % STAMP)
        self.assertTrue(self.wait_for(lambda: os.path.exists(self.pid_file())), "no waiter pid file")
        self.assertTrue(self.wait_for(lambda: "wait" in self.verbs()), "the waiter never waited")
        call = [c for c in self.calls() if c[:2] == ["terminal", "wait"]][0]
        self.assertEqual(call[call.index("--terminal") + 1], HANDLE)
        self.assertEqual(call[call.index("--for") + 1], "tui-idle")
        with open(self.pid_file()) as fh:
            pid = int(fh.read().split()[0])
        os.kill(pid, 0)   # alive

    def test_a_third_compaction_with_a_live_waiter_starts_no_second_one(self):
        self.assertOk(self.hook("compact"))
        self.assertOk(self.hook("compact"))
        self.assertTrue(self.wait_for(lambda: "wait" in self.verbs()))
        with open(self.pid_file()) as fh:
            first = fh.read()
        out = self.assertOk(self.hook("compact"))
        self.assertIn(LIMIT_PANE % 3, out.splitlines())
        time.sleep(1.5)
        with open(self.pid_file()) as fh:
            self.assertEqual(fh.read(), first)
        self.assertEqual(self.verbs().count("wait"), 1, self.calls())

    def test_no_pane_gets_the_tell_the_human_line(self):
        cases = {"plain": dict(runtime="plain"), "cloud": dict(runtime="cloud"),
                 "no handle": dict(runtime="orca", handle=None)}
        for label, kw in cases.items():
            with self.subTest(label=label):
                sid = "np-" + label.replace(" ", "-")
                self.assertOk(self.hook("compact", sid=sid, **kw))
                out = self.assertOk(self.hook("compact", sid=sid, **kw))
                self.assertIn(LIMIT_NO_PANE % 2, out.splitlines())
                self.assertNotIn(LIMIT_PANE % 2, out)
                time.sleep(0.5)
                self.assertFalse(os.path.exists(self.pid_file(sid)))
        self.assertEqual(self.sends(), [])

    def test_no_orca_on_path_gets_the_tell_the_human_line(self):
        self.repo.no_orca()
        self.assertOk(self.hook("compact"))
        out = self.assertOk(self.hook("compact"))
        self.assertIn(LIMIT_NO_PANE % 2, out.splitlines())
        self.assertFalse(os.path.exists(self.pid_file()))

    def test_a_clear_starts_the_count_again(self):
        self.assertOk(self.hook("compact", runtime="plain", handle=None))
        self.assertOk(self.hook("compact", runtime="plain", handle=None))
        self.assertOk(self.hook("clear", runtime="plain", handle=None))
        out = self.assertOk(self.hook("compact", runtime="plain", handle=None))
        self.assertIn("COMPACTED 1 time(s) this session", out)
        self.assertNotIn("LIMIT", out)

    def test_old_waiter_pid_files_are_cleaned_like_the_other_markers(self):
        old = self.pid_file("ancient")
        with open(old, "w") as fh:
            fh.write("999999\n")
        when = time.time() - 9 * 86400
        os.utime(old, (when, when))
        self.assertOk(self.repo.run("agent-start.sh", env={"AGENT_ROLE": "task-manager"}))
        self.assertFalse(os.path.exists(old))


# =============================================================== A5 C3, C4, C10 the waiter


class TestWaiter(ClearCase):
    script = "agent-autoclear.sh"

    def setUp(self):
        super().setUp()
        # settings-configure: compact_clear_check_sec is a fixed 30 s; a `sleep` stub on PATH
        # keeps the waiter fast (was: set_conf compact_clear_check_sec 1)
        # only the waiter's own 30 s pause shrinks (to 0.3 s; test-slim, was 1 s); any other sleep stays real
        self.pause(0.3)

    def pause(self, seconds):
        self.repo.stub_tool("sleep", '#!/bin/bash\n[ "$1" = 30 ] && exec /bin/sleep %s\nexec /bin/sleep "$@"\n' % seconds)

    def test_the_whole_run_with_a_goal_line(self):
        self.write_state(["ROLE: x", "GOAL: an older goal", "GOAL: " + GOAL, ""])
        self.assertOk(self.waiter())
        self.assertEqual(self.verbs(), ["wait", "read", "send", "wait", "read", "send", "wait", "read", "send"])
        self.assertEqual(self.sends(), [SAVE, "/clear", "/goal " + GOAL])
        for c in self.calls():
            self.assertEqual(c[c.index("--terminal") + 1], HANDLE, c)
            if c[1] == "wait":
                self.assertEqual(c[c.index("--for") + 1], "tui-idle")
            if c[1] == "read":
                self.assertIn("--json", c)
        self.assertEqual(self.state_lines()[-1], "AUTO CLEAR done | %s" % NOW)
        self.assertFalse(os.path.exists(self.pid_file()))

    def test_a_goal_line_written_by_state_add_loses_its_stamp(self):
        self.write_state(["ROLE: x", "", "GOAL: %s | 2026-11-20 11:00" % GOAL, "LIVE: a | b | c"])
        self.assertOk(self.waiter())
        self.assertEqual(self.sends()[-1], "/goal " + GOAL)

    def test_no_goal_line_sends_the_continue_prompt(self):
        self.write_state(["ROLE: main manager", ""])
        self.assertOk(self.waiter())
        self.assertEqual(self.sends(), [SAVE, "/clear", CONT])

    def test_text_in_the_input_box_is_never_typed_over(self):
        self.write_state(["ROLE: x", ""])
        self.set_reads(pane("rules yes, and one more"), pane("rules yes, and one more thing"))
        self.assertOk(self.waiter())
        verbs = self.verbs()
        self.assertEqual(verbs[:7], ["wait", "read", "wait", "read", "wait", "read", "send"], verbs)
        self.assertEqual(self.sends(), [SAVE, "/clear", CONT])
        waiting = [l for l in self.state_lines() if l.startswith("AUTO CLEAR waiting")]
        self.assertEqual(waiting, ["AUTO CLEAR waiting: input box not empty | %s" % NOW])

    def test_no_prompt_line_on_screen_is_not_empty(self):
        self.write_state(["ROLE: x", ""])
        menu = {"ok": True, "result": {"terminal": {"handle": HANDLE, "tail": [
            "Do you trust the files in this folder?", "❯ 1. Yes, proceed", "  2. No, exit"]}}}
        nothing = {"ok": True, "result": {"terminal": {"handle": HANDLE, "tail": ["working..."]}}}
        self.set_reads(menu, nothing)
        self.assertOk(self.waiter())
        self.assertEqual(self.verbs()[:7], ["wait", "read", "wait", "read", "wait", "read", "send"])

    def test_only_the_last_prompt_line_counts(self):
        self.write_state(["ROLE: x", ""])
        self.set_read_default(pane(None, extra_top=["❯ an old prompt in the scroll", "⏺ answer"]))
        self.assertOk(self.waiter())
        self.assertEqual(self.sends(), [SAVE, "/clear", CONT])

    def test_spaces_and_a_no_break_space_are_empty(self):
        self.write_state(["ROLE: x", ""])
        self.set_read_default(pane(" \u00a0 "))
        self.assertOk(self.waiter())
        self.assertEqual(self.sends(), [SAVE, "/clear", CONT])

    def test_a_wait_timeout_waits_again(self):
        self.write_state(["ROLE: x", ""])
        self.stub_file("wait_fail_once", {"ok": False, "error": {"code": "timeout"}})
        self.assertOk(self.waiter())
        self.assertEqual(self.verbs()[:3], ["wait", "wait", "read"])
        self.assertEqual(self.sends(), [SAVE, "/clear", CONT])

    def test_a_gone_pane_stops_it_with_a_line(self):
        self.write_state(["ROLE: x", ""])
        self.stub_file("wait_fail", {"ok": False, "error": {"code": "terminal_not_found"}})
        self.waiter()
        self.assertEqual(self.sends(), [])
        self.assertEqual(self.state_lines()[-1],
                         "AUTO CLEAR failed at step 1: terminal_not_found | %s" % NOW)
        self.assertFalse(os.path.exists(self.pid_file()))

    def test_a_refused_send_stops_it_with_a_line(self):
        self.write_state(["ROLE: x", ""])
        self.stub_file("send_fail", {"ok": False, "error": {"code": "send_refused"}})
        self.waiter()
        self.assertEqual(self.verbs().count("send"), 1)
        self.assertEqual(self.state_lines()[-1], "AUTO CLEAR failed at step 2: send_refused | %s" % NOW)
        self.assertNotIn("AUTO CLEAR done", "\n".join(self.state_lines()))
        self.assertFalse(os.path.exists(self.pid_file()))

    def test_it_writes_its_pid_file_while_it_runs(self):
        self.write_state(["ROLE: x", ""])
        self.stub_file("wait_sleep", "3")
        proc = self.repo.popen("agent-autoclear.sh", HANDLE, "s1", env={"AGENT_FAKE_NOW": NOW})
        try:
            self.assertTrue(self.wait_for(lambda: os.path.exists(self.pid_file()), 5))
            with open(self.pid_file()) as fh:
                self.assertEqual(int(fh.read().split()[0]), proc.pid)
        finally:
            proc.wait(timeout=60)
        self.assertFalse(os.path.exists(self.pid_file()))

    # ---- reviewer findings (verify, 2026-11-20)

    def test_it_pauses_after_each_typed_text(self):
        # finding 7: tui-idle can come back before the pane went busy; a pause of
        # compact_clear_check_sec after each typed text lets the save turn start first
        self.pause(1)   # three pauses of 1 s: at least 2 s in all
        self.write_state(["ROLE: x", ""])
        t0 = time.time()
        self.assertOk(self.waiter())
        self.assertGreaterEqual(time.time() - t0, 2.0, "no pause after the save prompt and /clear")
        self.assertEqual(self.sends(), [SAVE, "/clear", CONT])

    def test_the_goal_line_is_read_when_it_is_typed(self):
        self.write_state(["ROLE: x", "GOAL: the old goal", ""])
        self.stub_file("send_hook.sh", 'case "$1" in "AUTO CLEAR: save"*) echo "GOAL: the new goal" >> %s;; esac\n'
                       % self.state_path)
        self.assertOk(self.waiter())
        self.assertEqual(self.sends()[-1], "/goal the new goal")

    def test_an_empty_prompt_outside_the_box_is_not_empty(self):
        self.write_state(["ROLE: x", ""])
        bare = {"ok": True, "result": {"terminal": {"handle": HANDLE, "tail": ["⏺ x", "❯", "no rule lines here"]}}}
        self.set_reads(bare)
        self.assertOk(self.waiter())
        self.assertEqual(self.verbs()[:5], ["wait", "read", "wait", "read", "send"])

    def test_a_term_signal_leaves_a_line_at_once(self):
        self.write_state(["ROLE: x", ""])
        self.stub_file("wait_sleep", "40")
        proc = self.repo.popen("agent-autoclear.sh", HANDLE, "s1", env={"AGENT_FAKE_NOW": NOW})
        self.assertTrue(self.wait_for(lambda: "wait" in self.verbs(), 10))
        time.sleep(0.5)
        t0 = time.time()
        proc.terminate()
        proc.wait(timeout=20)
        self.assertLess(time.time() - t0, 5, "the trap waited for the orca call")
        self.assertEqual(self.state_lines()[-1], "AUTO CLEAR failed at step 1: stopped by a signal | %s" % NOW)
        self.assertFalse(os.path.exists(self.pid_file()))

    def test_missing_arguments_are_usage(self):
        r = self.repo.run("agent-autoclear.sh", HANDLE)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
