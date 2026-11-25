"""Tests of bin/agent-autoclear.sh (the auto /clear waiter) and the STATE LONG / compaction lines of agent-start.sh.

requirements/state-trim.md. One class per feature. Older task contracts: git log -p of this file.
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
from scripthelp import pointer_part  # noqa: E402
import datetime  # noqa: E402
import test_agent_owner_order as oo  # noqa: E402

NOW = "2026-11-20 12:00"
HANDLE = "term_t1"
SAVE = "AUTO CLEAR: save agent_state.txt now (S8), nothing else. /clear comes next."
CONT = "CLEARED: continue from agent_state.txt (S8)."
GOAL = ("task manager goal-x: done when DONE PASS or DONE FAIL is written under === REPORT === in "
        "agent_state.txt and the branch is pushed, or a QUESTION:, MOCK READY or CLOSE CASE line waits "
        "for an answer, or you saved agent_state.txt after an AUTO CLEAR notice")
# check-blocks section 36 (owner 2026-11-25): the clear waits until no human typed for clear_quiet_min (30)
LIMIT_PANE = ("LIMIT: compacted %d times. Save agent_state.txt now. This pane gets a save prompt "
              "and /clear at its next idle prompt once no human has typed for 30 minutes (S8).")
LIMIT_PANE_NO_WAIT = ("LIMIT: compacted %d times. Save agent_state.txt now, then stop. This pane gets a save prompt "
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
        # section 43 C9: these runs stand for a spawned task manager's pane (cleared without a transcript)
        return self.repo.run("agent-autoclear.sh", HANDLE, sid, "--spawned", env=full, timeout=60)

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
        proc = self.repo.popen("agent-autoclear.sh", HANDLE, "s1", "--spawned", env={"AGENT_FAKE_NOW": NOW})
        try:
            self.assertTrue(self.wait_for(lambda: os.path.exists(self.pid_file()), 5))
            with open(self.pid_file()) as fh:
                self.assertEqual(int(fh.read().split()[0]), proc.pid)
        finally:
            # section 48 C22: a pane whose every turn waits is never typed into; end the waiter instead
            proc.terminate()
            proc.wait(timeout=20)
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
        proc = self.repo.popen("agent-autoclear.sh", HANDLE, "s1", "--spawned", env={"AGENT_FAKE_NOW": NOW})
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


T0 = datetime.datetime(2026, 11, 20, 12, 0)


def ago(minutes):
    return T0 - datetime.timedelta(minutes=minutes)


def tell_pointer(dt):
    """A tell pointer typed into the pane by the main manager: signed, so agent-typed."""
    return oo.owner("[Fable 5.2 xhigh] TELL 1a2b3c4d: read the TELL 1a2b3c4d block at the end of agent_state.txt "
                    "and act on it", dt)


class Transcript:
    """<CLAUDE_CONFIG_DIR>/projects/<folder name of the repo>/<session>.jsonl"""

    def __init__(self, case, repo_dir):
        # the same config home the settings live in (scripthelp's default CLAUDE_CONFIG_DIR), so set_conf is read
        self.cfg = os.path.join(case.repo.base, "no-claude-config")
        self.dir = os.path.join(self.cfg, "projects", oo.folder_name(repo_dir))
        os.makedirs(self.dir, exist_ok=True)

    def write(self, lines, session="s1"):
        with open(os.path.join(self.dir, session + ".jsonl"), "w") as fh:
            fh.write("".join(json.dumps(l) + "\n" for l in lines))

    def append(self, line, session="s1"):
        with open(os.path.join(self.dir, session + ".jsonl"), "a") as fh:
            fh.write(json.dumps(line) + "\n")


class TestHumanQuiet(ScriptCase):
    script = "agent-owner-order.sh"

    def setUp(self):
        super().setUp()
        self.t = Transcript(self, self.repo.dir)

    def quiet(self, minutes="30", session="s1"):
        return self.repo.run("agent-owner-order.sh", "human-quiet", "--session", session, "--minutes", minutes,
                             "--repo", self.repo.dir,
                             env={"CLAUDE_CONFIG_DIR": self.t.cfg, "TZ": "UTC", "AGENT_FAKE_NOW": NOW},
                             cwd=self.repo.dir)

    def test_a_human_10_minutes_ago(self):
        self.t.write([oo.owner("wait, one more thing about the board", ago(10))])
        r = self.quiet()
        self.assertEqual((r.returncode, r.stdout.strip()), (1, "typed 2026-11-20 11:50"), r.stderr)

    def test_40_minutes_ago_is_quiet(self):
        self.t.write([oo.owner("ok go", ago(40))])
        r = self.quiet()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "quiet"), r.stderr)

    def test_exactly_n_minutes_is_quiet(self):
        self.t.write([oo.owner("ok go", ago(30))])
        self.assertEqual(self.quiet().returncode, 0)

    def test_no_transcript_is_unknown(self):
        # section 43 C9: unreadable is not quiet
        r = self.quiet()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertTrue(r.stdout.strip().startswith("unknown: "), r.stdout)

    def test_only_a_typed_human_prompt_counts(self):
        self.t.write([
            oo.owner("ok go", ago(40)),
            oo.notification("worker done", ago(9)),
            oo.peer("Worker B: PASS", ago(8)),
            tell_pointer(ago(7)),
            oo.owner(SAVE, ago(6)),
            oo.owner("/clear", ago(5)),
            oo.owner("/goal " + GOAL, ago(4)),
            oo.owner(CONT, ago(4)),
            oo.meta("a hook said something", ago(3)),
            oo.tool_result("Ran 3 tests", ago(2)),
            oo.assistant("done", ago(1)),
        ])
        r = self.quiet()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "quiet"), r.stdout)

    def test_a_queued_prompt_is_a_human_too(self):
        self.t.write([oo.owner("and the board?", ago(2), source="queued")])
        self.assertEqual(self.quiet().returncode, 1)

    def test_zero_minutes_is_always_quiet(self):
        self.t.write([oo.owner("still here", ago(0))])
        self.assertEqual(self.quiet("0").returncode, 0)

    def test_another_session_does_not_count(self):
        self.t.write([oo.owner("ok go", ago(40))])                # s1 has its own transcript (C9: none = unknown)
        self.t.write([oo.owner("I talk to the other pane", ago(1))], session="s2")
        self.assertEqual(self.quiet().returncode, 0)


def only_own(cls):
    """A subclass of a test class with tests: keep only the tests written in the subclass itself."""
    own = set(vars(cls))
    for name in dir(cls):
        if name.startswith("test") and name not in own:
            setattr(cls, name, None)
    return cls


@only_own
class TestF9ASessionStartedInASubfolder(TestHumanQuiet):
    def test_the_session_file_is_found_in_another_project_folder(self):
        other = os.path.join(self.t.cfg, "projects", oo.folder_name(os.path.join(self.repo.dir, "sub")))
        os.makedirs(other, exist_ok=True)
        with open(os.path.join(other, "s1.jsonl"), "w") as fh:
            fh.write(json.dumps(oo.owner("wait, one more thing", ago(5))) + "\n")
        r = self.quiet()
        self.assertEqual((r.returncode, r.stdout.strip()), (1, "typed 2026-11-20 11:55"), r.stderr)


class TestWaiterWaitsForTheHuman(ClearCase):
    script = "agent-autoclear.sh"

    def setUp(self):
        super().setUp()
        self.repo.stub_tool("sleep", '#!/bin/bash\n[ "$1" = 30 ] && exec /bin/sleep 1\nexec /bin/sleep "$@"\n')
        self.t = Transcript(self, self.repo.dir)
        self.write_state(["ROLE: main manager", ""])

    def env(self):
        return {"AGENT_FAKE_NOW": NOW, "CLAUDE_CONFIG_DIR": self.t.cfg, "TZ": "UTC"}

    def waiting_line(self):
        return [l for l in self.state_lines() if l.startswith("AUTO CLEAR waiting: a human typed at ")]

    def start(self):
        proc = self.repo.popen("agent-autoclear.sh", HANDLE, "s1", env=self.env())
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        return proc

    def test_a_human_10_minutes_ago_holds_it(self):
        self.t.write([oo.owner("let us talk about the flow", ago(10))])
        self.start()
        self.assertTrue(self.wait_for(lambda: self.waiting_line(), 15), self.state_lines())
        self.assertEqual(self.waiting_line(), [
            "AUTO CLEAR waiting: a human typed at 11:50; the clear waits for 30 quiet minutes | %s" % NOW])
        time.sleep(3)
        self.assertEqual(self.sends(), [], "nothing is typed while the human is talking")
        self.assertEqual(len(self.waiting_line()), 1, "one line per wait")

    def test_a_human_40_minutes_ago_clears_as_today(self):
        self.t.write([oo.owner("ok go", ago(40))])
        self.assertOk(self.waiter(env=self.env()))
        self.assertEqual(self.sends(), [SAVE, "/clear", CONT])

    def test_agents_and_notifications_do_not_hold_it(self):
        # a task manager nobody types into is cleared as today
        self.t.write([oo.notification("worker done", ago(3)), tell_pointer(ago(2)), oo.peer("PASS", ago(1))])
        self.assertOk(self.waiter(env=self.env()))
        self.assertEqual(self.sends(), [SAVE, "/clear", CONT])

    def test_zero_clears_without_waiting(self):
        self.repo.set_conf("clear_quiet_min", "0")
        self.t.write([oo.owner("still here", ago(1))])
        self.assertOk(self.waiter(env=self.env()))
        self.assertEqual(self.sends(), [SAVE, "/clear", CONT])

    def test_a_human_after_the_save_prompt_starts_it_again(self):
        self.t.write([oo.owner("ok go", ago(40))])
        human_now = json.dumps(oo.owner("no wait, I am not done", T0))
        marker = os.path.join(self.repo.base, "typed_once")
        self.stub_file("send_hook.sh",
                       '[ "$1" = %s ] && [ ! -f %s ] && { printf "%%s\\n" %s >> %s; touch %s; }\nexit 0\n'
                       % (json.dumps(SAVE), marker, "'" + human_now + "'",
                          os.path.join(self.t.dir, "s1.jsonl"), marker))
        proc = self.start()
        self.assertTrue(self.wait_for(lambda: self.waiting_line(), 20), (self.sends(), self.state_lines()))
        self.assertEqual(self.sends(), [SAVE], "no /clear while the human talks")
        # the talk ends: 40 minutes later the newest human prompt is old (the fake clock stands still)
        self.t.write([oo.owner("no wait, I am not done", ago(40))])
        self.assertTrue(self.wait_for(lambda: proc.poll() is not None, 30), self.sends())
        self.assertEqual(self.sends(), [SAVE, SAVE, "/clear", CONT], "back to the save prompt first")
        self.assertEqual(self.state_lines()[-1], "AUTO CLEAR done | %s" % NOW)


class TestLimitLine(ClearCase):
    def setUp(self):
        super().setUp()
        self.stub_file("wait_sleep", "30")

    def test_the_line_names_the_wait(self):
        self.write_state(["ROLE: x", ""])
        self.assertOk(self.hook("compact"))
        out = self.assertOk(self.hook("compact"))
        self.assertIn(LIMIT_PANE % 2, out.splitlines())

    def test_zero_keeps_the_old_line(self):
        self.repo.set_conf("clear_quiet_min", "0")
        self.write_state(["ROLE: x", ""])
        self.assertOk(self.hook("compact"))
        out = self.assertOk(self.hook("compact"))
        self.assertIn(LIMIT_PANE_NO_WAIT % 2, out.splitlines())


ROOT = os.path.dirname(HERE)


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def wait_until(check, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        if check():
            return True
        time.sleep(0.2)
    return check()


class TestC8GateBeforeReady(ClearCase):
    script = "agent-autoclear.sh"

    def test_the_gate_comes_before_each_ready(self):
        self.repo.stub_tool("sleep", '#!/bin/bash\n[ "$1" = 30 ] && exec /bin/sleep 1\nexec /bin/sleep "$@"\n')
        self.repo.write_bin_script("agent-owner-order.sh",
                                   "#!/usr/bin/env bash\nprintf 'CALL\\thuman-quiet\\n' >> \"$ORCA_STUB_LOG\"\n"
                                   "echo quiet\nexit 0\n")
        self.write_state(["ROLE: x", ""])
        self.assertOk(self.waiter())
        seq = [c[1] if c[0] == "terminal" else c[0] for c in self.calls()]
        # section 46 C13: the gate also runs before /goal; the order per typed text is gate, ready, type
        self.assertEqual(seq, ["human-quiet", "wait", "read", "send"] * 3)


@only_own
class TestC9UnknownIsNotQuiet(TestHumanQuiet):
    def test_no_transcript_is_unknown(self):
        r = self.quiet()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertTrue(r.stdout.strip().startswith("unknown: "), r.stdout)


@only_own
class TestC9TheWaiter(TestWaiterWaitsForTheHuman):
    def test_a_human_session_waits_on_unknown(self):
        proc = self.start()                                               # no --spawned, no transcript
        line = "AUTO CLEAR waiting: the transcript of this session cannot be read"
        self.assertTrue(wait_until(lambda: any(l.startswith(line) for l in self.state_lines()), 15),
                        self.state_lines())
        time.sleep(2)
        self.assertEqual(self.sends(), [])

    def test_a_spawned_task_manager_is_cleared_as_today(self):
        r = self.repo.run("agent-autoclear.sh", HANDLE, "s1", "--spawned", env=self.env(), timeout=60)
        self.assertOk(r)
        self.assertEqual(self.sends(), [SAVE, "/clear", CONT])

    def test_the_start_passes_spawned_for_a_task_manager(self):
        self.assertIn("--spawned", read("bin", "agent-start.sh"))


def waiter_stub_with_wait_hook():
    """The waiter's orca stub, plus $ORCA_STUB_DIR/wait_hook.sh run with the number of each wait call."""
    a = '''  "terminal wait")\n'''
    assert WAITER_STUB.count(a) == 1
    return WAITER_STUB.replace(a, a + '''    wn=$(cat "$d/wait_n" 2>/dev/null || echo 0); wn=$((wn+1)); echo "$wn" > "$d/wait_n"
    [ -f "$d/wait_hook.sh" ] && bash "$d/wait_hook.sh" "$wn"
''')


@only_own
class TestC13GateAgainAfterAWait(TestWaiterWaitsForTheHuman):
    def setUp(self):
        super().setUp()
        with open(self.stub, "w") as fh:
            fh.write(waiter_stub_with_wait_hook())

    def test_a_human_prompt_during_the_save_turn_stops_the_clear(self):
        self.t.write([oo.owner("ok go", ago(40))])
        human_now = json.dumps(oo.owner("wait, one more thing", T0))
        # the 2nd wait is the save turn: the human types during it, and it takes 3 s (ready waited)
        self.stub_file("wait_hook.sh", '[ "$1" = 2 ] && { printf "%%s\\n" %s >> %s; /bin/sleep 3; }\nexit 0\n'
                       % ("'" + human_now + "'", os.path.join(self.t.dir, "s1.jsonl")))
        self.start()
        self.assertTrue(wait_until(lambda: self.waiting_line(), 20), (self.sends(), self.state_lines()))
        time.sleep(2)
        self.assertEqual(self.sends(), [SAVE], "no /clear after a human prompt in the save turn")

    def test_a_humans_pane_is_cleared_when_quiet(self):
        # C21: the whole waiter on a human's pane (no --spawned)
        self.t.write([oo.owner("ok go", ago(40))])
        r = self.repo.run("agent-autoclear.sh", HANDLE, "s1", env=self.env(), timeout=60)
        self.assertOk(r)
        self.assertEqual(self.sends(), [SAVE, "/clear", CONT])


class TestC13PinnedOrder(ClearCase):
    script = "agent-autoclear.sh"

    def test_gate_and_ready_before_every_typed_text(self):
        self.repo.stub_tool("sleep", '#!/bin/bash\n[ "$1" = 30 ] && exec /bin/sleep 1\nexec /bin/sleep "$@"\n')
        self.repo.write_bin_script("agent-owner-order.sh",
                                   "#!/usr/bin/env bash\nprintf 'CALL\\thuman-quiet\\n' >> \"$ORCA_STUB_LOG\"\n"
                                   "echo quiet\nexit 0\n")
        self.write_state(["ROLE: x", ""])
        self.assertOk(self.waiter())
        seq = [c[1] if c[0] == "terminal" else c[0] for c in self.calls()]
        self.assertEqual(seq, ["human-quiet", "wait", "read", "send"] * 3)


@only_own
class TestC22EveryPane(TestC13GateAgainAfterAWait):
    def test_a_task_manager_pane_is_not_cleared_after_a_human_prompt(self):
        self.t.write([oo.owner("ok go", ago(40))])
        human_now = json.dumps(oo.owner("wait, keep going on the report", T0))
        self.stub_file("wait_hook.sh", '[ "$1" = 2 ] && { printf "%%s\\n" %s >> %s; /bin/sleep 3; }\nexit 0\n'
                       % ("'" + human_now + "'", os.path.join(self.t.dir, "s1.jsonl")))
        proc = self.repo.popen("agent-autoclear.sh", HANDLE, "s1", "--spawned", env=self.env())
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.assertTrue(wait_until(lambda: self.waiting_line(), 20), (self.sends(), self.state_lines()))
        time.sleep(2)
        self.assertEqual(self.sends(), [SAVE], "no /clear after the owner's prompt in a task manager pane")


class TestH6Cap(ClearCase):
    script = "agent-autoclear.sh"

    def test_a_pane_that_never_settles_gets_a_line(self):
        self.repo.stub_tool("sleep", '#!/bin/bash\n[ "$1" = 30 ] && exec /bin/sleep 1\nexec /bin/sleep "$@"\n')
        self.write_state(["ROLE: x", ""])
        self.stub_file("wait_sleep", "3")                     # every turn takes 3 s: the pane never settles
        proc = self.repo.popen("agent-autoclear.sh", HANDLE, "s1", "--spawned", env={"AGENT_FAKE_NOW": NOW})
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        line = "AUTO CLEAR waiting: the pane did not settle in 3 rounds; trying again later"
        self.assertTrue(wait_until(lambda: any(l.startswith(line) for l in self.state_lines()), 40),
                        self.state_lines())
        proc.terminate()


if __name__ == "__main__":
    unittest.main()
