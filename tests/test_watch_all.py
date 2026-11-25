"""Failing tests for `bin/agent-watch.sh --all` (one watcher for every task manager), the probe retry and
the single mode additions. Written by the task manager first. Rules: requirements/one-watcher.md
(owner rules yes 2026-11-24; SCOPE CHANGE 2026-11-24 08:22: B16 this repo only). Row ids in test names.

CONTRACT (short; the table is the full rule)

    bin/agent-watch.sh --all [--interval-min 5] [--max <n>]
        run from the main repo (or any folder of it). Targets (A1) are re-read every sweep from the main
        repo's agent_worktree.txt (working, final) and agent_todo.txt (open line with "on <machine> <path>"
        and no worktree line). Pane and shell from LAUNCH records (tm-pane, shell-pane) in the main repo's
        agent_state.txt, else `orca terminal list`. One sweep reads every watched target, then prints one
        WATCH line per event in target order and exits 0:
            WATCH SIGNAL <name>: <line>        + the last 15 screen lines of that TM
            WATCH STALL <name>: no change | idle prompt | login expired
            WATCH LOST <name>: pane exited (<kind>, exit <code>) | pane exited (cause unknown) | <orca error>
            WATCH MAX all
        Lines: "<HH:MM> sweep: <name> <state>, ..." each sweep; "<HH:MM> watch: + <name>";
        "<HH:MM> watch: <name> not watched: <why>"; "<HH:MM> watch: live pane with no task line: <path> (<title>)";
        "watch --all: replaced pid <p>".
        Status file: <git common dir of the main repo>/agent_watch.json (B18).
    Probe (C2): AGENT_WATCH_RETRY_S (default 2) seconds between the 3 tries; tests use 0.
    AGENT_WATCH_INTERVAL_S wins over --interval-min (tests use 0).
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

from watchhelp import (ENV, EXITED, LOGIN_TEXTS, STILL, AllCase, dead_pid, frame, idle,  # noqa: E402
                       moving, now_text, sh_quote)

HHMM = r"\d\d:\d\d"


# ---------------------------------------------------------------- A. targets


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


# ---------------------------------------------------------------- B. sweep and wake


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


# ---------------------------------------------------------------- R: review fixes (Opus review 2026-11-24)


class TestReviewFixes(AllCase):
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


# ---------------------------------------------------------------- B16. orphans, this repo only


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


# ---------------------------------------------------------------- C. probe and single mode


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


if __name__ == "__main__":
    unittest.main()
