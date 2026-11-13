"""Failing tests for housekeep-2h. Written by the task manager, before any code.

OWNER ASK (2026-11-13): "every 2 hour check update the worktree and todo and
ideas doc. then clean up those unused resource. to keep the environment clean."
D1 ideas: the script finds suspects at no token cost; the main manager judges
them at its next activity and removes only the ones done or voided.
D2 scope: own repo only; a repo named by an open cross-repo todo line of this
repo is read too (read only).

CONTRACT the workers implement.

1. CONFIG
   bin/agent.conf.default   housekeep_interval_min=120, the LAST line (newer
                            keys are appended, never inserted)
   bin/agent_conf.py        NUMBER_BOUNDS (0, 1440); a hint that says 0 = off;
                            group "limits", after stall_min
   bin/agent-settings.sh    sets and syncs it like every other key (generic)

2. MONITOR LOOP (bin/agent-monitor.sh)
   The forked loop, after each of ITS sweeps (never the first sweep that
   `start` runs itself, never `once`), runs
       <plugin>/bin/agent-housekeep.sh --apply
   once, when all of these hold:
     a. role_read at `start` said main (the session that started the loop is
        the main manager). spawned, second, closed, takeover at start: the
        loop never runs it, for its whole life
     b. housekeep_interval_min from agent.conf, read again every round
        (missing: 120; 0: never)
     c. "<git dir>/agent_main.lock" names a pid that is alive, read again every
        round (a new main manager after a restart is picked up)
     d. "<git dir>/agent_housekeep.last" is missing, does not read, or its first
        field (epoch seconds) is interval*60 seconds ago or more
   The call: CLAUDE_PID=<that lock pid>, AGENT_ROLE unset, stdin /dev/null,
   output not shown. It is a child the loop waits on: `stop` and a plain TERM
   to the loop end it too, nothing left behind.
   The loop never writes the stamp; agent-housekeep.sh --apply does.
   status: one more line
       "housekeep: every <n> minutes, last <date time of the stamp>"
       "housekeep: every <n> minutes, last (none)"      no stamp
       "housekeep: off"                                 interval 0
   -h names housekeep_interval_min and agent-housekeep.sh, and says plain and
   cloud have no loop (run agent-housekeep.sh --apply by hand there).

3. bin/agent-housekeep.sh (bash entry, executable) + bin/agent_housekeep.py
   (the logic, python3 stdlib; may import agent_cleanup.py and agent_conf.py)
       agent-housekeep.sh           list mode: print the block, change nothing,
                                    no stamp, nothing written to agent_state.txt
       agent-housekeep.sh --apply   do it, write the block, print it
       agent-housekeep.sh -h        help, exit 0
       anything else                usage on stderr, exit 2
   Main manager only, same as agent-cleanup.sh: role spawned, second or closed
   -> one stderr line with "REFUSED" and "main manager only", exit 1, before
   any orca or git call, nothing written.
   --apply first writes "<git dir>/agent_housekeep.last":
       "<epoch seconds> <YYYY-MM-DD HH:MM>"
   AGENT_FAKE_NOW="YYYY-MM-DD HH:MM" replaces the clock (stamp, header, ages).
   Exit 0 after the role check, always (an internal error is a note line).

   THE BLOCK (main repo agent_state.txt, PROJECT_ROOT):
       === HOUSEKEEP <YYYY-MM-DD HH:MM> ===
         <body line>            every body line starts with two spaces
   Body lines, in this order:
       removed: worktree line <path> (folder gone, no live pane)
       removed: idea <n>, a duplicate of idea <m>: <first 80 chars of its text>
       flag: worktree line <path>: folder gone, line says <working|final|human-direct>
       flag: worktree line <path>: <working|final>, no live agent pane
       flag: todo <name>: merged into origin/main (branch <b>)
       flag: todo <name>: merged into origin/main (commit <sha> <subject>)
       flag: todo <name>: stale, no worktree line and no open wait for <n>m
       suspect: idea <n>: <first 80 chars of its text> | <reason>[; <reason>]
       related: <repo> (<path>): task <name> not open there (done <date>)
       related: <repo> (<path>): task <name> not open there (dropped <date>)
       related: <repo> (<path>): task <name> not open there
       related: <repo> (<path>): task <name> open there, no worktree line there
       related: <repo>: not found on this machine, skipped
       note: <text>
       cleanup: <a --short line of agent-cleanup.sh, "CLEANUP: " cut off>
   List mode says "would remove:" where --apply says "removed:".
   Nothing at all -> the one line "HOUSEKEEP <YYYY-MM-DD HH:MM>: clean".
   Written atomically (tmp next to it + mv). The old block (its header and the
   two-space lines right after it) or the old clean line is replaced in place;
   none -> appended at the end (file made when missing). Every other line is
   kept byte for byte. One block in the file, ever.

   a. agent_worktree.txt ("<path> | <module> | <status> | since <date>")
      present    local: a `git worktree list` path whose folder exists;
                 orca: also a row path of a reachable paired machine (same
                 projectId as the main checkout's local row)
      live pane  orca: any agent (any state) at that path in `orca worktree ps`
                 (local, or that machine's)
      not present, no live pane, status not working/final, module not
          human-direct  -> agent-file.sh worktree rm <path>; "removed: ..."
      not present, status working/final, or a human-direct line -> flag
          "folder gone, line says <status|human-direct>", never removed
      present, status working/final, no live pane (orca only) -> flag
      orca: local `orca worktree ps` fails -> no line removed or flagged,
          note "orca not answering: worktree lines not checked"
      a paired machine unreachable (or `environment list` fails) -> a line
          that is not present locally is not removed; note
          "<name> unreachable, not checked"; never hangs (AGENT_CLEANUP_TIMEOUT)
      plain/cloud: local git only, no orca call, no "no live agent pane" flag
   b. agent_todo.txt: never changed (todo done needs work and wait facts)
      merged: after `git fetch --prune origin`; a branch (local or origin) that
          is the branch of the task's worktree, or is named <name>, or ends in
          "/<name>", whose tip is an ancestor of origin/main and not on its
          first-parent line -> "(branch <b>)"; else a first-parent commit of
          origin/main whose subject is "Merge <name>" or starts "Merge <name> "
          -> "(commit <short sha> <subject>)". No origin/main: not checked
      stale: no worktree line for the task (module == name, or the folder name
          == name, or the path of its "on <machine> <path>" field), no
          "waiting ..." field, and more than T minutes from the later of
          "opened <dt>" and "stage <s> since <dt>" to now.
          T = housekeep_interval_min (0 or missing: 120)
   c. agent_ideas.txt ("<text> | <YYYY-MM-DD HH:MM> | by <who>")
      text = the line without that tail (no tail: the whole line, trimmed)
      duplicates: a line whose text equals an earlier line's text -> removed
          with agent-file.sh idea rm <n>, highest n first; the first stays
      suspects, never removed, one line per idea, numbers as the file is after
          this run's removals:
          "names task <t>, done <date>" / "names task <t>, dropped <date>":
              a line "<date> | <t> | ..." of agent_completed.txt, date >= the
              idea's day, <t> in the text as a whole word (case does not
              matter; a word char is a letter, digit, "_" or "-")
          "names <word>, no such file": a word (letters, digits, _ . / ~ -;
              trailing . , : ; ) cut) ending in .sh .py .md .txt .json .js
              .mjs .html .conf .default, URLs (scheme://...) skipped; found
              when it exists (absolute, ~, or under PROJECT_ROOT) or, a bare
              name, when `git ls-files` of PROJECT_ROOT has a file of that name
   d. related repos (read only, never written)
      an open todo line names another repo by its "by <x>" field (written by
      todo add) or its "cross <x>" field (new: agent-file.sh todo cross)
      known repos = agent-file.sh repos (new verb, the lookup data uses)
      x matches a known repo by folder name; this repo itself is skipped;
      "by <x>" with no match is ignored (by is mostly main or a role);
      "cross <x>" with no match -> "related: <x>: not found on this machine, skipped"
      a match R: R/agent_todo.txt has a line named <name>? then
      R/agent_worktree.txt has a line for it (module or folder name)? else the
      R/agent_completed.txt line of that name gives done/dropped <date>
   e. <plugin>/bin/agent-cleanup.sh --apply --short (list mode: --short), same
      environment; it runs agent-resources.sh stop-leftovers itself (--apply)

4. bin/agent-file.sh, two new verbs
   todo cross "<name>" <repo>   field " | cross <repo>" (replaced in place,
                                once, else at the end), atomic. Prints
                                "todo cross: <name> -> <repo>". Refused (stderr,
                                exit 1, nothing written): no such todo line, no
                                repo, a repo with a space, " | " or a line break
   repos                        read only, no file touched: one real path per
                                line, this repo first, then world.json
                                territories, then joined-repos.txt, each once;
                                a missing folder is not printed

5. DOCS + RELEASE: PRINCIPLES.md R5 R6 R7 W8 W12 (+ S8 or W8 for the block),
   README tree, .claude-plugin/plugin.json 0.33.0.

DEFAULTS TAKEN BY THE TASK MANAGER (logged in agent_state.txt):
   - working/final/human-direct lines are never removed, even with the folder
     gone: flagged (same safe rule as the cleanup sweep)
   - stale threshold T = housekeep_interval_min (owner said 2 h; default 120)
   - housekeep runs agent-cleanup.sh --apply only: that already runs
     agent-resources.sh stop-leftovers (agent_cleanup.py do_processes)
   - the loop impersonates the live lock owner through CLAUDE_PID, the
     mechanism role_read already has; no new bypass for any other caller
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
BIN = os.path.join(os.path.dirname(HERE), "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import agent_conf  # noqa: E402
import test_agent_cleanup as tc  # noqa: E402  (the module only: its tests stay in their own module)
from scripthelp import ROOT, ScriptCase, children_of  # noqa: E402

NOW = "2026-11-13 12:00"
REAL_SLEEP = shutil.which("sleep") or "/bin/sleep"

git = tc.git

FAKE_CLEANUP = r"""#!/usr/bin/env bash
printf '%s\t%s\t%s\n' "$*" "${CLAUDE_PID:-}" "${AGENT_ROLE:-}" >> "@LOG@"
[ -f "@OUT@" ] && cat "@OUT@"
exit 0
"""

FAKE_FILE = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "@LOG@"
exec "$(dirname "$0")/agent-file-real.sh" "$@"
"""

FAKE_HK = r"""#!/usr/bin/env bash
printf '%s\t%s\t%s\n' "$*" "${CLAUDE_PID:-}" "${AGENT_ROLE:-}" >> "@LOG@"
if [ -f "@LOG@.stamp" ]; then
  printf '%s %s\n' "$(date +%s)" "$(date '+%Y-%m-%d %H:%M')" > "@STAMP@"
fi
if [ -f "@LOG@.hold" ]; then
  echo $$ > "@LOG@.pid"
  exec python3 -c 'import time; time.sleep(30)'
fi
exit 0
"""


def epoch_of(text):
    return int(time.mktime(time.strptime(text, "%Y-%m-%d %H:%M")))


def read_root(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def principles_section(code):
    """The lines of one PRINCIPLES.md rule, e.g. "W8", heading included."""
    out = []
    inside = False
    for line in read_root("PRINCIPLES.md").splitlines():
        if re.match(r"^[A-Z]\d+\. ", line) or line.startswith("## "):
            inside = line.startswith(code + ". ")
            if inside:
                out.append(line)
            continue
        if inside:
            out.append(line)
    return out


# ================================================================ the pass


class HousekeepCase(tc.CleanupCase):
    """A project with a bare origin and Orca knowing the repo; the cleanup
    sweep is a fake that logs its call, so each test sees only housekeep."""

    script = "agent-housekeep.sh"

    def setUp(self):
        super().setUp()
        r = self.repo
        r.set_conf("runtime", "orca")
        self.cleanup_log = os.path.join(r.base, "cleanup_calls.log")
        self.cleanup_out = os.path.join(r.base, "cleanup_out.txt")
        open(self.cleanup_log, "w").close()
        r.write_bin_script("agent-cleanup.sh", FAKE_CLEANUP
                           .replace("@LOG@", self.cleanup_log)
                           .replace("@OUT@", self.cleanup_out))
        self.gone = os.path.join(self.wts, "gone-one")

    # ---- running

    def hk(self, *args, **kwargs):
        env = {"AGENT_FAKE_NOW": NOW}
        env.update(kwargs.pop("env", None) or {})
        return self.repo.run("agent-housekeep.sh", *args, env=env, **kwargs)

    def apply(self, **kwargs):
        return self.assertOk(self.hk("--apply", **kwargs))

    def listing(self, **kwargs):
        return self.assertOk(self.hk(**kwargs))

    # ---- files

    def state(self):
        return self.repo.read("agent_state.txt") or ""

    def set_file(self, name, lines):
        write(self.repo.path(name), "".join(l + "\n" for l in lines))

    def file_lines(self, name):
        return [l for l in (self.repo.read(name) or "").splitlines() if l.strip()]

    @staticmethod
    def body_of(text):
        """The body lines of the HOUSEKEEP block, the two spaces cut off."""
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("=== HOUSEKEEP "):
                body = []
                for nxt in lines[i + 1:]:
                    if not nxt.startswith("  "):
                        break
                    body.append(nxt[2:])
                return body
        return []

    def body(self):
        return self.body_of(self.state())

    def todo(self, name, opened="2026-11-13 11:30", extra=""):
        return "%s | big | build %s | est 30m | opened %s | by main%s" % (
            name, name, opened, extra)

    def lock_me(self):
        write(self.repo.path(".git", "agent_main.lock"),
              "%d 2026-11-13 10:00 - -\n" % os.getpid())
        return {"CLAUDE_PID": str(os.getpid())}

    def cleanup_calls(self):
        with open(self.cleanup_log) as fh:
            return [l.rstrip("\n").split("\t") for l in fh if l.strip()]

    def paired(self, name="pc2", rows=(), ps_rows=()):
        self.repo.set_orca_answer(
            "envs.json", {"ok": True, "result": {"environments": [{"name": name}]}})
        self.repo.set_orca_answer(
            "list.json", {"ok": True, "result": {"worktrees": list(rows)}}, env=name)
        self.repo.set_orca_answer(
            "ps.json", {"ok": True, "result": {"worktrees": list(ps_rows)}}, env=name)
        self.repo.set_orca_answer(
            "terminals.json", {"ok": True, "result": {"terminals": []}}, env=name)


# ---------------------------------------------------------------- usage, role


class TestUsage(HousekeepCase):
    def test_help(self):
        out = self.assertOk(self.hk("-h"))
        for word in ("--apply", "main manager only", "housekeep_interval_min",
                     "plain", "cloud"):
            with self.subTest(word=word):
                self.assertIn(word, out)

    def test_an_unknown_argument_is_refused(self):
        result = self.hk("--force")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.strip())

    def test_the_script_is_executable(self):
        self.assertTrue(os.access(os.path.join(ROOT, "bin", "agent-housekeep.sh"), os.X_OK))

    def test_the_logic_lives_in_python(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, "bin", "agent_housekeep.py")))


class TestMainManagerOnly(HousekeepCase):
    def setUp(self):
        super().setUp()
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.set_file("agent_ideas.txt", ["same | 2026-11-10 10:00 | by main",
                                          "same | 2026-11-11 10:00 | by main"])
        self.before = {n: self.repo.read(n) for n in ("agent_worktree.txt", "agent_ideas.txt")}
        self.repo.clear_calls()

    def assertRefused(self, result):
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("REFUSED", result.stderr)
        self.assertIn("main manager only", result.stderr)
        for name, text in self.before.items():
            self.assertEqual(self.repo.read(name), text, name)
        self.assertNotIn("HOUSEKEEP", self.state())
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_housekeep.last")))
        self.assertEqual(self.repo.calls(), [])
        self.assertEqual(self.cleanup_calls(), [])

    def test_a_task_manager_is_refused(self):
        self.assertRefused(self.hk("--apply", env={"AGENT_ROLE": "task-manager"}))

    def test_a_worker_is_refused_even_in_list_mode(self):
        self.assertRefused(self.hk(env={"AGENT_ROLE": "worker"}))

    def test_a_human_direct_helper_is_refused(self):
        self.lock_me()
        self.assertRefused(self.hk("--apply", env={"CLAUDE_PID": "999999"}))

    def test_the_main_manager_runs(self):
        env = self.lock_me()
        self.apply(env=env)
        self.assertEqual(self.file_lines("agent_worktree.txt"), [])

    def test_no_lock_at_all_runs(self):
        self.apply()
        self.assertEqual(self.file_lines("agent_worktree.txt"), [])


# ---------------------------------------------------------------- stamp, block, file


class TestStamp(HousekeepCase):
    def test_apply_writes_the_stamp_in_the_git_dir(self):
        self.apply()
        text = open(self.repo.path(".git", "agent_housekeep.last")).read().strip()
        self.assertEqual(text, "%d %s" % (epoch_of(NOW), NOW))

    def test_list_mode_writes_no_stamp(self):
        self.listing()
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_housekeep.last")))


class TestClean(HousekeepCase):
    def test_nothing_found_is_one_line(self):
        out = self.apply()
        self.assertIn("HOUSEKEEP %s: clean" % NOW, out)
        self.assertEqual([l for l in self.state().splitlines() if "HOUSEKEEP" in l],
                         ["HOUSEKEEP %s: clean" % NOW])
        self.assertNotIn("=== HOUSEKEEP", self.state())

    def test_plain_mode_runs_too_with_no_orca_call(self):
        self.repo.set_conf("runtime", "plain")
        self.repo.clear_calls()
        out = self.apply()
        self.assertIn("HOUSEKEEP %s: clean" % NOW, out)
        self.assertEqual(self.repo.calls(), [])


class TestBlockInStateFile(HousekeepCase):
    def setUp(self):
        super().setUp()
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])

    def test_the_block_is_printed_and_written(self):
        out = self.apply()
        self.assertIn("=== HOUSEKEEP %s ===" % NOW, out)
        self.assertIn("=== HOUSEKEEP %s ===" % NOW, self.state())
        self.assertIn("removed: worktree line %s (folder gone, no live pane)" % self.gone,
                      self.body())

    def test_every_body_line_starts_with_two_spaces(self):
        self.apply()
        lines = self.state().splitlines()
        i = lines.index("=== HOUSEKEEP %s ===" % NOW)
        self.assertTrue(lines[i + 1].startswith("  "))

    def test_a_missing_state_file_is_made(self):
        self.assertIsNone(self.repo.read("agent_state.txt"))
        self.apply()
        self.assertTrue(self.state().startswith("=== HOUSEKEEP %s ===\n" % NOW))

    def test_appended_at_the_end_the_rest_kept_byte_for_byte(self):
        old = "=== BRIEF ===\nkeep me | as is\n\n=== REPORT ===\nPARKED: q | t | since x\n"
        write(self.repo.path("agent_state.txt"), old)
        self.apply()
        self.assertTrue(self.state().startswith(old))

    def test_an_old_block_is_replaced_in_place(self):
        before = "=== BRIEF ===\nline one\n"
        old_block = ("=== HOUSEKEEP 2026-11-13 08:00 ===\n"
                     "  removed: worktree line /x (folder gone, no live pane)\n"
                     "  flag: todo y: stale, no worktree line and no open wait for 999m\n")
        after = "PARKED: a question | t | since 2026-11-13 09:00\n=== REPORT ===\nend\n"
        write(self.repo.path("agent_state.txt"), before + old_block + after)
        self.apply()
        text = self.state()
        self.assertTrue(text.startswith(before + "=== HOUSEKEEP %s ===\n" % NOW))
        self.assertTrue(text.endswith(after))
        self.assertNotIn("08:00", text)
        self.assertNotIn("999m", text)
        self.assertEqual(text.count("HOUSEKEEP"), 1)

    def test_an_old_clean_line_is_replaced_in_place(self):
        write(self.repo.path("agent_state.txt"),
              "top\nHOUSEKEEP 2026-11-13 08:00: clean\nbottom\n")
        self.apply()
        text = self.state()
        self.assertTrue(text.startswith("top\n=== HOUSEKEEP %s ===\n" % NOW))
        self.assertTrue(text.endswith("\nbottom\n"))
        self.assertNotIn("08:00", text)

    def test_a_clean_run_replaces_an_old_block(self):
        write(self.repo.path("agent_state.txt"),
              "top\n=== HOUSEKEEP 2026-11-13 08:00 ===\n  note: old\nbottom\n")
        self.repo.set_worktree_lines([])
        self.apply()
        self.assertEqual(self.state(), "top\nHOUSEKEEP %s: clean\nbottom\n" % NOW)

    def test_two_runs_leave_one_block(self):
        self.apply()
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.apply()
        self.assertEqual(self.state().count("=== HOUSEKEEP"), 1)

    def test_written_by_tmp_and_mv(self):
        write(self.repo.path("agent_state.txt"), "top\n")
        first = os.stat(self.repo.path("agent_state.txt")).st_ino
        self.apply()
        self.assertNotEqual(os.stat(self.repo.path("agent_state.txt")).st_ino, first)
        left = [n for n in os.listdir(self.repo.dir)
                if n.startswith("agent_state.txt") and n != "agent_state.txt"]
        self.assertEqual(left, [])

    def test_list_mode_prints_and_writes_nothing(self):
        write(self.repo.path("agent_state.txt"), "top\n")
        before_wt = self.repo.read("agent_worktree.txt")
        out = self.listing()
        self.assertIn("would remove: worktree line %s (folder gone, no live pane)" % self.gone,
                      self.body_of(out))
        self.assertEqual(self.state(), "top\n")
        self.assertEqual(self.repo.read("agent_worktree.txt"), before_wt)

    def test_from_a_worktree_it_writes_the_main_repo_state_file(self):
        path, _branch = self.worktree("here", orca=False)
        self.assertOk(self.repo.run("agent-housekeep.sh", "--apply", cwd=path,
                                    env={"AGENT_FAKE_NOW": NOW}))
        self.assertIn("=== HOUSEKEEP %s ===" % NOW, self.state())
        self.assertFalse(os.path.exists(os.path.join(path, "agent_state.txt")))


# ---------------------------------------------------------------- a. worktree lines


class TestWorktreeLines(HousekeepCase):
    def test_a_gone_idle_line_is_removed(self):
        keep, _ = self.worktree("keep")
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle"), (keep, "keep", "idle")])
        self.apply()
        self.assertEqual([l.split(" | ")[0] for l in self.file_lines("agent_worktree.txt")], [keep])
        self.assertIn("removed: worktree line %s (folder gone, no live pane)" % self.gone, self.body())

    def test_a_deleted_folder_git_still_lists_counts_as_gone(self):
        path, _ = self.worktree("deleted")
        shutil.rmtree(path)
        self.repo.set_worktree_lines([(path, "deleted", "idle")])
        self.apply()
        self.assertEqual(self.file_lines("agent_worktree.txt"), [])

    def test_a_gone_working_line_is_flagged_never_removed(self):
        for status in ("working", "final"):
            with self.subTest(status=status):
                self.repo.set_worktree_lines([(self.gone, "gone-one", status)])
                self.apply()
                self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
                self.assertIn("flag: worktree line %s: folder gone, line says %s"
                              % (self.gone, status), self.body())

    def test_a_gone_human_direct_line_is_flagged_never_removed(self):
        self.repo.set_worktree_lines([(self.gone, "task manager, human-direct", "task: Fix It")])
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertIn("flag: worktree line %s: folder gone, line says human-direct" % self.gone,
                      self.body())

    def test_a_gone_line_with_a_live_pane_stays(self):
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.repo.set_panes([{"path": self.gone, "agents": ["done"]}])
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertFalse([l for l in self.body() if l.startswith("removed: worktree line")])

    def test_a_working_line_with_no_agent_pane_is_flagged(self):
        path, _ = self.worktree("busy")
        self.repo.set_worktree_lines([(path, "busy", "working")])
        self.repo.set_panes([])
        self.apply()
        self.assertIn("flag: worktree line %s: working, no live agent pane" % path, self.body())
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)

    def test_a_working_line_with_a_done_pane_is_fine(self):
        path, _ = self.worktree("idlepane")
        self.repo.set_worktree_lines([(path, "idlepane", "final")])
        self.repo.set_panes([{"path": path, "agents": ["done"]}])
        self.apply()
        self.assertFalse([l for l in self.body() if path in l])

    def test_a_present_idle_line_is_left_to_the_cleanup(self):
        path, _ = self.worktree("quiet")
        self.repo.set_worktree_lines([(path, "quiet", "idle")])
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertFalse([l for l in self.body() if path in l])

    def test_a_line_on_a_paired_machine_is_present(self):
        far = os.path.join(self.repo.base, "pc2-only", "far")
        self.paired(rows=[self.list_row(far, "feat/far", host="pc2")])
        self.repo.set_worktree_lines([(far, "far", "idle")])
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)

    def test_a_working_line_on_a_paired_machine_with_its_agent_is_fine(self):
        far = os.path.join(self.repo.base, "pc2-only", "far")
        self.paired(rows=[self.list_row(far, "feat/far", host="pc2")],
                    ps_rows=[{"path": far, "agents": [{"state": "working"}]}])
        self.repo.set_worktree_lines([(far, "far", "working")])
        self.apply()
        self.assertFalse([l for l in self.body() if far in l])

    def test_a_paired_machine_down_keeps_the_line_and_says_so(self):
        self.paired()
        self.repo.set_orca_env_state("pc2", "down")
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertIn("note: pc2 unreachable, not checked", self.body())

    def test_a_hanging_paired_machine_never_hangs_the_pass(self):
        self.paired()
        self.repo.set_orca_env_state("pc2", "hang")
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        started = time.time()
        self.apply(env={"AGENT_CLEANUP_TIMEOUT": "1"})
        self.assertLess(time.time() - started, 40)
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertIn("note: pc2 unreachable, not checked", self.body())

    def test_orca_down_changes_no_line(self):
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.repo.stub_orca_down()
        self.apply()
        self.assertEqual(len(self.file_lines("agent_worktree.txt")), 1)
        self.assertTrue([l for l in self.body()
                         if l.startswith("note: ") and "orca not answering" in l], self.body())

    def test_plain_mode_removes_a_gone_line_with_no_orca_call(self):
        self.repo.set_conf("runtime", "plain")
        path, _ = self.worktree("busyplain")
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle"), (path, "busyplain", "working")])
        self.repo.clear_calls()
        self.apply()
        self.assertEqual([l.split(" | ")[0] for l in self.file_lines("agent_worktree.txt")], [path])
        self.assertEqual(self.repo.calls(), [])
        self.assertFalse([l for l in self.body() if "no live agent pane" in l])

    def test_it_goes_through_agent_file(self):
        log = os.path.join(self.repo.base, "file_calls.log")
        real = os.path.join(self.repo.plugin_bin, "agent-file.sh")
        shutil.copy2(real, os.path.join(self.repo.plugin_bin, "agent-file-real.sh"))
        self.repo.write_bin_script("agent-file.sh", FAKE_FILE.replace("@LOG@", log))
        self.repo.set_worktree_lines([(self.gone, "gone-one", "idle")])
        self.set_file("agent_ideas.txt", ["twice | 2026-11-10 10:00 | by main",
                                          "twice | 2026-11-11 10:00 | by main"])
        self.apply()
        calls = open(log).read().splitlines()
        self.assertIn("worktree rm %s" % self.gone, calls)
        self.assertIn("idea rm 2", calls)


# ---------------------------------------------------------------- b. todo lines


class TestTodoMerged(HousekeepCase):
    def test_a_merged_branch_of_that_name_is_flagged(self):
        branch = self.branch_only("alpha", merge=True)
        self.set_file("agent_todo.txt", [self.todo("alpha")])
        self.apply()
        self.assertIn("flag: todo alpha: merged into origin/main (branch %s)" % branch, self.body())

    def test_the_todo_file_is_never_changed(self):
        self.branch_only("alpha", merge=True)
        self.set_file("agent_todo.txt", [self.todo("alpha"), self.todo("old", opened="2026-11-12 08:00")])
        before = self.repo.read("agent_todo.txt")
        self.apply()
        self.assertEqual(self.repo.read("agent_todo.txt"), before)

    def test_an_unmerged_branch_is_not_flagged(self):
        self.branch_only("beta", merge=False)
        self.set_file("agent_todo.txt", [self.todo("beta")])
        self.apply()
        self.assertFalse([l for l in self.body() if "merged" in l])

    def test_a_new_branch_with_no_own_commit_is_not_flagged(self):
        git(self.repo.dir, "branch", "feat/epsilon", "main")
        git(self.repo.dir, "push", "-q", "origin", "feat/epsilon")
        self.set_file("agent_todo.txt", [self.todo("epsilon")])
        self.apply()
        self.assertFalse([l for l in self.body() if "merged" in l])

    def merge_commit(self, subject):
        r = self.repo
        git(r.dir, "checkout", "-q", "-b", "tmp/side")
        self.commit_in(r.dir, "side_%d.txt" % len(subject))
        git(r.dir, "checkout", "-q", "main")
        git(r.dir, "merge", "-q", "--no-ff", "-m", subject, "tmp/side")
        git(r.dir, "branch", "-D", "tmp/side")
        git(r.dir, "push", "-q", "origin", "main")
        return git(r.dir, "rev-parse", "HEAD")

    def test_a_merge_commit_of_that_name_is_flagged_when_the_branch_is_gone(self):
        sha = self.merge_commit("Merge gamma (W8)")
        self.set_file("agent_todo.txt", [self.todo("gamma")])
        self.apply()
        hits = [l for l in self.body() if l.startswith("flag: todo gamma: merged into origin/main (commit ")]
        self.assertEqual(len(hits), 1, self.body())
        m = re.match(r"flag: todo gamma: merged into origin/main \(commit ([0-9a-f]{7,}) Merge gamma \(W8\)\)$",
                     hits[0])
        self.assertIsNotNone(m, hits[0])
        self.assertTrue(sha.startswith(m.group(1)))

    def test_a_merge_commit_of_a_longer_name_is_not_flagged(self):
        self.merge_commit("Merge gammaray (W8)")
        self.set_file("agent_todo.txt", [self.todo("gamma")])
        self.apply()
        self.assertFalse([l for l in self.body() if "merged" in l])

    def test_the_branch_of_its_worktree_counts(self):
        r = self.repo
        path = os.path.join(self.wts, "deltawt")
        git(r.dir, "worktree", "add", "-q", "-b", "work/zzz", path, "main")
        self.commit_in(path, "d.txt")
        git(path, "push", "-q", "-u", "origin", "work/zzz")
        git(r.dir, "merge", "-q", "--no-ff", "-m", "Merge work/zzz", "work/zzz")
        git(r.dir, "push", "-q", "origin", "main")
        self.repo.set_worktree_lines([(path, "delta", "final")])
        self.set_file("agent_todo.txt", [self.todo("delta")])
        self.apply()
        self.assertIn("flag: todo delta: merged into origin/main (branch work/zzz)", self.body())

    def test_no_origin_means_no_merged_check(self):
        git(self.repo.dir, "remote", "remove", "origin")
        self.set_file("agent_todo.txt", [self.todo("alpha")])
        out = self.apply()
        self.assertIn("HOUSEKEEP %s: clean" % NOW, out)


class TestTodoStale(HousekeepCase):
    def stale_line(self, name):
        return [l for l in self.body() if l.startswith("flag: todo %s: stale" % name)]

    def test_three_hours_with_no_worktree_and_no_wait_is_stale(self):
        self.set_file("agent_todo.txt", [self.todo("s1", opened="2026-11-13 09:00")])
        self.apply()
        self.assertEqual(self.stale_line("s1"),
                         ["flag: todo s1: stale, no worktree line and no open wait for 180m"])

    def test_one_hour_is_not_stale(self):
        self.set_file("agent_todo.txt", [self.todo("s2", opened="2026-11-13 11:00")])
        self.apply()
        self.assertEqual(self.stale_line("s2"), [])

    def test_exactly_the_threshold_is_not_stale(self):
        self.set_file("agent_todo.txt", [self.todo("s3", opened="2026-11-13 10:00")])
        self.apply()
        self.assertEqual(self.stale_line("s3"), [])

    def test_an_open_wait_is_not_stale(self):
        self.set_file("agent_todo.txt", [self.todo(
            "s4", opened="2026-11-13 08:00", extra=" | waiting question since 2026-11-13 08:30")])
        self.apply()
        self.assertEqual(self.stale_line("s4"), [])

    def test_a_worktree_line_of_that_module_is_not_stale(self):
        path, _ = self.worktree("s5wt")
        self.repo.set_worktree_lines([(path, "s5", "working")])
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        self.set_file("agent_todo.txt", [self.todo("s5", opened="2026-11-13 08:00")])
        self.apply()
        self.assertEqual(self.stale_line("s5"), [])

    def test_a_worktree_folder_of_that_name_is_not_stale(self):
        path, _ = self.worktree("s6")
        self.repo.set_worktree_lines([(path, "something else", "working")])
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        self.set_file("agent_todo.txt", [self.todo("s6", opened="2026-11-13 08:00")])
        self.apply()
        self.assertEqual(self.stale_line("s6"), [])

    def test_the_path_of_its_on_field_is_not_stale(self):
        path, _ = self.worktree("s7wt")
        self.repo.set_worktree_lines([(path, "other", "working")])
        self.repo.set_panes([{"path": path, "agents": ["working"]}])
        self.set_file("agent_todo.txt", [self.todo(
            "s7", opened="2026-11-13 08:00", extra=" | on pc2 %s" % path)])
        self.apply()
        self.assertEqual(self.stale_line("s7"), [])

    def test_a_newer_stage_since_counts(self):
        self.set_file("agent_todo.txt", [self.todo(
            "s8", opened="2026-11-13 08:00", extra=" | stage tests since 2026-11-13 11:30")])
        self.apply()
        self.assertEqual(self.stale_line("s8"), [])

    def test_the_threshold_is_the_interval(self):
        self.repo.set_conf("housekeep_interval_min", "30")
        self.set_file("agent_todo.txt", [self.todo("s9", opened="2026-11-13 11:00")])
        self.apply()
        self.assertEqual(self.stale_line("s9"),
                         ["flag: todo s9: stale, no worktree line and no open wait for 60m"])

    def test_interval_off_still_uses_two_hours(self):
        self.repo.set_conf("housekeep_interval_min", "0")
        self.set_file("agent_todo.txt", [self.todo("s10", opened="2026-11-13 11:00"),
                                         self.todo("s11", opened="2026-11-13 09:30")])
        self.apply()
        self.assertEqual(self.stale_line("s10"), [])
        self.assertEqual(len(self.stale_line("s11")), 1)


# ---------------------------------------------------------------- c. ideas


class TestIdeaDuplicates(HousekeepCase):
    def test_later_copies_go_the_first_stays(self):
        self.set_file("agent_ideas.txt", [
            "add a todo est verb | 2026-11-10 10:00 | by main",
            "something else | 2026-11-10 11:00 | by main",
            "add a todo est verb | 2026-11-12 09:00 | by task-manager",
            "add a todo est verb | 2026-11-13 08:00 | by main",
        ])
        self.apply()
        self.assertEqual(self.file_lines("agent_ideas.txt"), [
            "add a todo est verb | 2026-11-10 10:00 | by main",
            "something else | 2026-11-10 11:00 | by main",
        ])
        body = self.body()
        self.assertIn("removed: idea 3, a duplicate of idea 1: add a todo est verb", body)
        self.assertIn("removed: idea 4, a duplicate of idea 1: add a todo est verb", body)
        self.assertLess(body.index("removed: idea 3, a duplicate of idea 1: add a todo est verb"),
                        body.index("removed: idea 4, a duplicate of idea 1: add a todo est verb"))

    def test_a_line_with_no_date_tail_still_compares_by_text(self):
        self.set_file("agent_ideas.txt", ["plain idea", "plain idea | 2026-11-12 09:00 | by main"])
        self.apply()
        self.assertEqual(self.file_lines("agent_ideas.txt"), ["plain idea"])

    def test_near_copies_stay(self):
        lines = ["Add a todo est verb | 2026-11-10 10:00 | by main",
                 "add a todo est verb | 2026-11-11 10:00 | by main",
                 "add a todo est verb soon | 2026-11-12 10:00 | by main"]
        self.set_file("agent_ideas.txt", lines)
        self.apply()
        self.assertEqual(self.file_lines("agent_ideas.txt"), lines)

    def test_list_mode_changes_nothing(self):
        self.set_file("agent_ideas.txt", ["x y | 2026-11-10 10:00 | by main",
                                          "x y | 2026-11-11 10:00 | by main"])
        before = self.repo.read("agent_ideas.txt")
        out = self.listing()
        self.assertIn("would remove: idea 2, a duplicate of idea 1: x y", self.body_of(out))
        self.assertEqual(self.repo.read("agent_ideas.txt"), before)

    def test_only_the_first_80_characters_are_shown(self):
        text = "a" * 80 + "TAILWORDS" + "b" * 30
        self.set_file("agent_ideas.txt", [text + " | 2026-11-10 10:00 | by main",
                                          text + " | 2026-11-11 10:00 | by main"])
        self.apply()
        self.assertIn("removed: idea 2, a duplicate of idea 1: " + "a" * 80, self.body())
        self.assertNotIn("TAILWORDS", self.state())


class TestIdeaSuspects(HousekeepCase):
    def suspects(self):
        return [l for l in self.body() if l.startswith("suspect: ")]

    def test_an_idea_naming_a_task_done_later(self):
        self.set_file("agent_completed.txt", [
            "2026-11-12 | todo-est | add todo est | data repo=project type=script"])
        idea = "teach todo-est to keep the reason | 2026-11-05 10:02 | by main"
        self.set_file("agent_ideas.txt", [idea])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: teach todo-est to keep the reason | names task todo-est, done 2026-11-12"])
        self.assertEqual(self.file_lines("agent_ideas.txt"), [idea])

    def test_the_same_day_counts(self):
        self.set_file("agent_completed.txt", ["2026-11-05 | five-fixes | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["a gap seen (five-fixes S1, pc2) | 2026-11-05 10:02 | by main"])
        self.apply()
        self.assertEqual(len(self.suspects()), 1)
        self.assertIn("names task five-fixes, done 2026-11-05", self.suspects()[0])

    def test_a_task_done_before_the_idea_is_not_a_suspect(self):
        self.set_file("agent_completed.txt", ["2026-11-01 | todo-est | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["more todo-est work | 2026-11-05 10:02 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_a_dropped_task_says_dropped(self):
        self.set_file("agent_completed.txt", [
            "2026-11-12 | old-thing | x | est 30m actual - | dropped: owner said no"])
        self.set_file("agent_ideas.txt", ["revive old-thing | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: revive old-thing | names task old-thing, dropped 2026-11-12"])

    def test_a_whole_word_only(self):
        self.set_file("agent_completed.txt", ["2026-11-12 | fix | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["prefix the names, a fixed thing | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_case_does_not_matter(self):
        self.set_file("agent_completed.txt", ["2026-11-12 | statusline-vertical | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["Statusline-Vertical follow up. | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(len(self.suspects()), 1)

    def test_a_missing_file_is_a_suspect(self):
        self.set_file("agent_ideas.txt", ["teach bin/agent-gone.sh to stop | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: teach bin/agent-gone.sh to stop | names bin/agent-gone.sh, no such file"])

    def test_files_that_exist_are_fine(self):
        r = self.repo
        write(r.path("docs", "notes.md"), "x\n")
        git(r.dir, "add", "docs/notes.md")
        git(r.dir, "commit", "-q", "-m", "notes")
        self.set_file("agent_ideas.txt", [
            "see seed.txt, docs/notes.md and notes.md; also agent_todo.txt. | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_urls_are_skipped(self):
        self.set_file("agent_ideas.txt", ["read https://example.com/x/readme.md first | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [])

    def test_two_reasons_on_one_line(self):
        self.set_file("agent_completed.txt", ["2026-11-12 | todo-est | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["todo-est in nothere.py | 2026-11-10 10:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 1: todo-est in nothere.py | names task todo-est, done 2026-11-12; "
            "names nothere.py, no such file"])

    def test_numbers_are_after_this_runs_removals(self):
        self.set_file("agent_completed.txt", ["2026-11-12 | todo-est | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["dup | 2026-11-10 10:00 | by main",
                                          "dup | 2026-11-10 11:00 | by main",
                                          "more todo-est | 2026-11-10 12:00 | by main"])
        self.apply()
        self.assertEqual(self.suspects(), [
            "suspect: idea 2: more todo-est | names task todo-est, done 2026-11-12"])

    def test_list_mode_numbers_are_the_file_as_it_is(self):
        self.set_file("agent_completed.txt", ["2026-11-12 | todo-est | x | data repo=project"])
        self.set_file("agent_ideas.txt", ["dup | 2026-11-10 10:00 | by main",
                                          "dup | 2026-11-10 11:00 | by main",
                                          "more todo-est | 2026-11-10 12:00 | by main"])
        out = self.listing()
        self.assertIn("suspect: idea 3: more todo-est | names task todo-est, done 2026-11-12",
                      self.body_of(out))


# ---------------------------------------------------------------- d. related repos


class RelatedCase(HousekeepCase):
    def setUp(self):
        super().setUp()
        self.city = os.path.join(self.repo.base, "cityhome-default")
        os.makedirs(self.city, exist_ok=True)
        self.peer = os.path.realpath(self.repo.make_project("peer"))
        for name in ("agent_todo.txt", "agent_completed.txt", "agent_ideas.txt", "agent_worktree.txt"):
            write(os.path.join(self.peer, name), "")
        self.join(self.peer)

    def join(self, *paths):
        write(os.path.join(self.city, "joined-repos.txt"), "".join(p + "\n" for p in paths))

    def peer_file(self, name, lines):
        write(os.path.join(self.peer, name), "".join(l + "\n" for l in lines))

    def related(self):
        return [l for l in self.body() if l.startswith("related: ")]


class TestRelated(RelatedCase):
    def test_done_on_the_other_side(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.peer_file("agent_completed.txt", ["2026-11-12 | shared | x | data repo=peer"])
        self.apply()
        self.assertEqual(self.related(), [
            "related: peer (%s): task shared not open there (done 2026-11-12)" % self.peer])

    def test_dropped_on_the_other_side(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.peer_file("agent_completed.txt", ["2026-11-12 | shared | x | est 30m actual - | dropped: no"])
        self.apply()
        self.assertEqual(self.related(), [
            "related: peer (%s): task shared not open there (dropped 2026-11-12)" % self.peer])

    def test_no_line_at_all_on_the_other_side(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.apply()
        self.assertEqual(self.related(), [
            "related: peer (%s): task shared not open there" % self.peer])

    def test_open_with_a_worktree_line_there_is_fine(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.peer_file("agent_todo.txt", ["shared | big | x | est 30m | opened 2026-11-13 11:00 | by project"])
        self.peer_file("agent_worktree.txt", ["/far/away/shared | shared | working | since 2026-11-13 11:00"])
        out = self.apply()
        self.assertEqual(self.related(), [])
        self.assertIn("HOUSEKEEP %s: clean" % NOW, out)

    def test_open_with_no_worktree_line_there(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.peer_file("agent_todo.txt", ["shared | big | x | est 30m | opened 2026-11-13 11:00 | by project"])
        self.apply()
        self.assertEqual(self.related(), [
            "related: peer (%s): task shared open there, no worktree line there" % self.peer])

    def test_the_called_side_reads_its_by_field(self):
        line = "shared | big | x | est 30m | opened 2026-11-13 11:30 | by peer"
        self.set_file("agent_todo.txt", [line])
        self.peer_file("agent_completed.txt", ["2026-11-12 | shared | x | data repo=peer"])
        self.apply()
        self.assertEqual(self.related(), [
            "related: peer (%s): task shared not open there (done 2026-11-12)" % self.peer])

    def test_by_main_is_not_a_repo(self):
        self.set_file("agent_todo.txt", [self.todo("solo")])
        out = self.apply()
        self.assertEqual(self.related(), [])
        self.assertIn("HOUSEKEEP %s: clean" % NOW, out)

    def test_an_unknown_cross_repo_is_one_line(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross nowhere")])
        self.apply()
        self.assertEqual(self.related(), ["related: nowhere: not found on this machine, skipped"])

    def test_a_joined_folder_that_is_gone_is_not_found(self):
        shutil.rmtree(self.peer)
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.apply()
        self.assertEqual(self.related(), ["related: peer: not found on this machine, skipped"])

    def test_a_repo_from_world_json_is_found_too(self):
        other = os.path.realpath(self.repo.make_project("worldpeer"))
        write(os.path.join(other, "agent_todo.txt"), "")
        write(os.path.join(other, "agent_completed.txt"), "2026-11-12 | shared | x | data repo=worldpeer\n")
        write(os.path.join(self.city, "world.json"),
              json.dumps({"territories": {other + "/.git": {}}}))
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross worldpeer")])
        self.apply()
        self.assertEqual(self.related(), [
            "related: worldpeer (%s): task shared not open there (done 2026-11-12)" % other])

    def test_this_repo_itself_is_skipped(self):
        me = os.path.basename(self.repo.dir)
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross %s" % me)])
        self.apply()
        self.assertEqual(self.related(), [])

    def test_the_other_repo_is_never_written(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        self.peer_file("agent_todo.txt", ["shared | big | x | est 30m | opened 2026-11-13 11:00 | by project"])
        self.peer_file("agent_worktree.txt", ["/gone/for/good | other | idle | since 2026-11-01 10:00"])
        self.peer_file("agent_ideas.txt", ["dup | 2026-11-10 10:00 | by main", "dup | 2026-11-11 10:00 | by main"])
        before = {}
        for name in sorted(os.listdir(self.peer)):
            with open(os.path.join(self.peer, name)) as fh:
                before[name] = fh.read()
        self.apply()
        after = {}
        for name in sorted(os.listdir(self.peer)):
            with open(os.path.join(self.peer, name)) as fh:
                after[name] = fh.read()
        self.assertEqual(after, before)


class TestFileVerbs(RelatedCase):
    def af(self, *args, **kwargs):
        return self.repo.run("agent-file.sh", *args, **kwargs)

    def test_todo_cross_adds_the_field(self):
        self.set_file("agent_todo.txt", [self.todo("shared")])
        out = self.assertOk(self.af("todo", "cross", "shared", "peer"))
        self.assertIn("todo cross: shared -> peer", out)
        self.assertEqual(self.file_lines("agent_todo.txt"), [self.todo("shared") + " | cross peer"])

    def test_todo_cross_again_replaces_it_in_place(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer | stage tests since 2026-11-13 11:40")])
        self.assertOk(self.af("todo", "cross", "shared", "other"))
        self.assertEqual(self.file_lines("agent_todo.txt"), [
            self.todo("shared", extra=" | cross other | stage tests since 2026-11-13 11:40")])

    def test_todo_cross_refusals(self):
        self.set_file("agent_todo.txt", [self.todo("shared")])
        before = self.repo.read("agent_todo.txt")
        for args in (("nosuch", "peer"), ("shared",), ("shared", "two words"),
                     ("shared", "a | b"), ("shared", "a\nb")):
            with self.subTest(args=args):
                result = self.af("todo", "cross", *args)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertTrue(result.stderr.strip())
                self.assertEqual(self.repo.read("agent_todo.txt"), before)

    def test_the_board_still_reads_a_cross_field(self):
        self.set_file("agent_todo.txt", [self.todo("shared", extra=" | cross peer")])
        out = self.assertOk(self.af("board"))
        self.assertIn("shared", out)

    def test_repos_lists_this_repo_first_then_the_joined_ones(self):
        out = self.assertOk(self.af("repos"))
        self.assertEqual(out.splitlines(), [os.path.realpath(self.repo.dir), self.peer])

    def test_repos_world_json_before_joined_each_once(self):
        other = os.path.realpath(self.repo.make_project("worldpeer"))
        write(os.path.join(self.city, "world.json"),
              json.dumps({"territories": {other + "/.git": {}, self.peer + "/.git": {}}}))
        self.join(self.peer, other, self.repo.dir)
        out = self.assertOk(self.af("repos"))
        self.assertEqual(out.splitlines(), [os.path.realpath(self.repo.dir), other, self.peer])

    def test_repos_skips_a_missing_folder(self):
        self.join(self.peer, os.path.join(self.repo.base, "not-here"))
        out = self.assertOk(self.af("repos"))
        self.assertEqual(out.splitlines(), [os.path.realpath(self.repo.dir), self.peer])

    def test_repos_touches_no_file(self):
        for name in ("agent_todo.txt", "agent_ideas.txt"):
            os.remove(self.repo.path(name))
        self.assertOk(self.af("repos"))
        for name in ("agent_todo.txt", "agent_ideas.txt"):
            self.assertFalse(os.path.exists(self.repo.path(name)), name)

    def test_the_header_documents_both_verbs(self):
        head = read_root("bin", "agent-file.sh").split("\nset -eu", 1)[0]
        self.assertIn("todo cross", head)
        self.assertIn("agent-file.sh repos", head)


# ---------------------------------------------------------------- e. the cleanup sweep


class TestCleanupStep(HousekeepCase):
    def test_apply_runs_the_sweep_with_apply_and_short(self):
        self.apply()
        calls = self.cleanup_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(sorted(calls[0][0].split()), ["--apply", "--short"])

    def test_list_mode_runs_it_in_list_mode(self):
        self.listing()
        calls = self.cleanup_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0].split(), ["--short"])

    def test_it_runs_as_the_main_manager_too(self):
        env = self.lock_me()
        self.apply(env=env)
        self.assertEqual(self.cleanup_calls()[0][1], str(os.getpid()))

    def test_its_lines_go_into_the_block(self):
        write(self.cleanup_out, "CLEANUP: removed 2, kept 1. Table for the human: x\n"
                                "CLEANUP: pc2 unreachable, not checked\n")
        self.apply()
        body = self.body()
        self.assertIn("cleanup: removed 2, kept 1. Table for the human: x", body)
        self.assertIn("cleanup: pc2 unreachable, not checked", body)
        self.assertEqual(body[-2:], ["cleanup: removed 2, kept 1. Table for the human: x",
                                     "cleanup: pc2 unreachable, not checked"])


class TestCleanupReal(tc.CleanupCase):
    """The real sweep, from the pass, as the main manager."""

    script = "agent-housekeep.sh"

    def test_a_merged_worktree_goes_and_the_block_says_so(self):
        self.repo.set_conf("runtime", "orca")
        path, _branch = self.merged_worktree()
        write(self.repo.path(".git", "agent_main.lock"), "%d 2026-11-13 10:00 - -\n" % os.getpid())
        out = self.assertOk(self.repo.run("agent-housekeep.sh", "--apply",
                                          env={"AGENT_FAKE_NOW": NOW, "CLAUDE_PID": str(os.getpid())}))
        self.assertFalse(os.path.exists(path))
        self.assertIn("  cleanup: removed 1, kept 0.", out.splitlines())


# ================================================================ config


class TestConfKey(unittest.TestCase):
    def test_bounds(self):
        self.assertEqual(agent_conf.NUMBER_BOUNDS.get("housekeep_interval_min"), (0, 1440))
        for good in ("0", "1", "120", "1440"):
            self.assertIsNone(agent_conf.validate_value("housekeep_interval_min", good), good)
        for bad in ("-1", "1441", "abc", "1.5", ""):
            self.assertTrue(agent_conf.validate_value("housekeep_interval_min", bad), bad)

    def test_hint_says_zero_is_off(self):
        hint = agent_conf.HINTS.get("housekeep_interval_min", "")
        self.assertIn("0", hint)
        self.assertIn("off", hint)

    def test_it_sits_in_limits_after_stall_min(self):
        keys = dict(agent_conf.GROUPS)["limits"]
        self.assertEqual(keys[-2:], ["stall_min", "housekeep_interval_min"])

    def test_the_template_has_it_last_on_by_default(self):
        lines = [l for l in read_root("bin", "agent.conf.default").splitlines() if l.strip()]
        self.assertEqual(lines[-1], "housekeep_interval_min=120")
        conf = agent_conf.load(os.path.join(ROOT, "bin", "agent.conf.default"))
        self.assertEqual(agent_conf.validate(conf), {})


class TestSettingsKey(ScriptCase):
    script = "agent-settings.sh"

    def value(self):
        for line in (self.repo.read("agent.conf") or "").splitlines():
            if line.startswith("housekeep_interval_min="):
                return line.split("=", 1)[1]
        return None

    def test_set_and_off(self):
        for v in ("30", "0"):
            self.assertOk(self.repo.run("agent-settings.sh", "housekeep_interval_min", v))
            self.assertEqual(self.value(), v)

    def test_bad_values_are_refused(self):
        self.assertOk(self.repo.run("agent-settings.sh", "housekeep_interval_min", "45"))
        for v in ("-1", "1441", "abc"):
            with self.subTest(v=v):
                self.assertNotEqual(self.repo.run("agent-settings.sh", "housekeep_interval_min", v).returncode, 0)
                self.assertEqual(self.value(), "45")

    def test_sync_adds_it(self):
        self.repo.unset_conf("housekeep_interval_min")
        out = self.assertOk(self.repo.run("agent-settings.sh", "sync"))
        self.assertIn("added housekeep_interval_min=120", out)
        self.assertEqual(self.value(), "120")


# ================================================================ the monitor loop


class LoopCase(ScriptCase):
    script = "agent-monitor.sh"

    def setUp(self):
        super().setUp()
        r = self.repo
        r.set_conf("runtime", "orca")
        r.set_conf("monitor_interval_min", "1")
        r.set_conf("housekeep_interval_min", "120")
        self.hk_log = os.path.join(r.base, "hk_calls.log")
        open(self.hk_log, "w").close()
        self.stamp = r.path(".git", "agent_housekeep.last")
        r.write_bin_script("agent-housekeep.sh", FAKE_HK.replace("@LOG@", self.hk_log)
                           .replace("@STAMP@", self.stamp))
        # a worktree line, so every sweep calls `orca worktree ps`: the count of
        # those calls proves the loop went round
        wt = r.make_worktree("loopwt")
        r.set_worktree_lines([(wt, "loopwt", "working")])
        r.set_panes([{"path": wt, "agents": ["working"]}])
        self.helpers = []
        self.addCleanup(self.stop_helpers)

    def stop_helpers(self):
        for proc in self.helpers:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass

    def live_pid(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        self.helpers.append(proc)
        return proc.pid

    def fast_sleep(self):
        self.repo.stub_tool("sleep", "#!/bin/bash\nexec %s 0.2\n" % REAL_SLEEP)

    def lock(self, pid):
        write(self.repo.path(".git", "agent_main.lock"), "%d 2026-11-13 10:00 - -\n" % pid)

    def set_stamp(self, minutes_ago):
        when = time.time() - minutes_ago * 60
        write(self.stamp, "%d %s\n" % (when, time.strftime("%Y-%m-%d %H:%M", time.localtime(when))))

    def start(self, **env):
        env.setdefault("CLAUDE_PID", str(os.getpid()))
        out = self.assertOk(self.repo.run("agent-monitor.sh", "start", env=env))
        self.assertRegex(out, r"monitor: started \(pid \d+\)")
        return int(open(self.repo.path(".git", "agent_monitor.pid")).read().split()[0])

    def hk_calls(self):
        with open(self.hk_log) as fh:
            return [l.rstrip("\n").split("\t") for l in fh if l.strip()]

    def ps_calls(self):
        return [c for c in self.repo.calls() if c[:2] == ["worktree", "ps"]]

    @staticmethod
    def wait_for(cond, timeout=20):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if cond():
                return True
            time.sleep(0.1)
        return False

    def rounds(self, n=4):
        base = len(self.ps_calls())
        self.assertTrue(self.wait_for(lambda: len(self.ps_calls()) >= base + n),
                        "the loop did not go round")

    def assertNeverCalled(self):
        self.rounds()
        self.assertEqual(self.hk_calls(), [])

    def assertGone(self, pid, what):
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                return
            time.sleep(0.1)
        self.fail("%s (pid %d) is still alive" % (what, pid))


class TestLoopRuns(LoopCase):
    def test_due_with_no_stamp_runs_once_as_the_lock_owner(self):
        self.fast_sleep()
        self.lock(os.getpid())
        open(self.hk_log + ".stamp", "w").close()   # the fake writes the stamp like the real one
        self.start()
        self.assertTrue(self.wait_for(lambda: self.hk_calls()), "the pass never ran")
        self.rounds()
        calls = self.hk_calls()
        self.assertEqual(len(calls), 1, calls)
        self.assertEqual(calls[0], ["--apply", str(os.getpid()), ""])

    def test_the_lock_and_the_stamp_are_read_again_every_round(self):
        self.fast_sleep()
        self.lock(os.getpid())
        self.set_stamp(0)
        self.start()
        self.rounds(2)
        self.assertEqual(self.hk_calls(), [])
        new_owner = self.live_pid()      # a new main manager after a restart
        self.lock(new_owner)
        self.set_stamp(24 * 60)
        self.assertTrue(self.wait_for(lambda: self.hk_calls()), "the pass never ran")
        self.assertEqual(self.hk_calls()[0], ["--apply", str(new_owner), ""])

    def test_an_old_stamp_is_due(self):
        self.fast_sleep()
        self.lock(os.getpid())
        self.set_stamp(121)
        self.start()
        self.assertTrue(self.wait_for(lambda: self.hk_calls()), "the pass never ran")

    def test_a_stamp_that_does_not_read_is_due(self):
        self.fast_sleep()
        self.lock(os.getpid())
        write(self.stamp, "garbage\n")
        self.start()
        self.assertTrue(self.wait_for(lambda: self.hk_calls()), "the pass never ran")

    def test_a_missing_key_means_120(self):
        self.fast_sleep()
        self.lock(os.getpid())
        self.repo.unset_conf("housekeep_interval_min")
        self.set_stamp(100)
        self.start()
        self.assertNeverCalled()
        self.set_stamp(125)
        self.assertTrue(self.wait_for(lambda: self.hk_calls()), "the pass never ran")

    def test_the_interval_is_read_again_every_round(self):
        self.fast_sleep()
        self.lock(os.getpid())
        self.repo.set_conf("housekeep_interval_min", "0")
        self.start()
        self.rounds(2)
        self.assertEqual(self.hk_calls(), [])
        self.repo.set_conf("housekeep_interval_min", "120")
        self.assertTrue(self.wait_for(lambda: self.hk_calls()), "the pass never ran")


class TestLoopDoesNotRun(LoopCase):
    def test_a_fresh_stamp_is_not_due(self):
        self.fast_sleep()
        self.lock(os.getpid())
        self.set_stamp(30)
        self.start()
        self.assertNeverCalled()

    def test_interval_zero_is_off(self):
        self.fast_sleep()
        self.lock(os.getpid())
        self.repo.set_conf("housekeep_interval_min", "0")
        self.start()
        self.assertNeverCalled()

    def test_no_lock_no_pass(self):
        self.fast_sleep()
        self.start()
        self.assertNeverCalled()

    def test_a_dead_lock_owner_no_pass(self):
        self.fast_sleep()
        self.lock(999999)
        self.start(CLAUDE_PID="999999")
        self.assertNeverCalled()

    def test_a_loop_started_by_a_spawned_agent_never_runs_it(self):
        self.fast_sleep()
        self.lock(os.getpid())
        self.start(AGENT_ROLE="task-manager")
        self.assertNeverCalled()

    def test_a_loop_started_by_a_helper_never_runs_it(self):
        self.fast_sleep()
        self.lock(os.getpid())
        self.start(CLAUDE_PID="999999")
        self.assertNeverCalled()

    def test_once_never_runs_it(self):
        self.lock(os.getpid())
        self.assertOk(self.repo.run("agent-monitor.sh", "once", env={"CLAUDE_PID": str(os.getpid())}))
        self.assertEqual(self.hk_calls(), [])

    def test_the_first_sweep_of_start_never_runs_it(self):
        self.lock(os.getpid())          # real sleep: the loop's first round is a minute away
        self.start()
        time.sleep(1.5)
        self.assertEqual(self.hk_calls(), [])


class TestLoopLeavesNothing(LoopCase):
    def running_pass(self):
        self.fast_sleep()
        self.lock(os.getpid())
        open(self.hk_log + ".hold", "w").close()
        loop = self.start()
        pidfile = self.hk_log + ".pid"
        self.assertTrue(self.wait_for(lambda: os.path.exists(pidfile) and open(pidfile).read().strip()),
                        "the pass never started")
        return loop, int(open(pidfile).read().strip())

    def test_stop_ends_a_running_pass(self):
        loop, hk = self.running_pass()
        self.assertOk(self.repo.run("agent-monitor.sh", "stop"))
        self.assertGone(loop, "the loop after stop")
        self.assertGone(hk, "the pass after stop")

    def test_a_term_to_the_loop_ends_a_running_pass(self):
        loop, hk = self.running_pass()
        os.kill(loop, signal.SIGTERM)
        self.assertGone(loop, "the loop after TERM")
        self.assertGone(hk, "the pass after TERM")
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_monitor.pid")))


class TestLoopStatusAndHelp(LoopCase):
    def status(self):
        return self.assertOk(self.repo.run("agent-monitor.sh", "status"))

    def test_status_with_a_stamp(self):
        write(self.stamp, "1763000000 2026-11-13 11:00\n")
        self.assertIn("housekeep: every 120 minutes, last 2026-11-13 11:00", self.status())

    def test_status_with_no_stamp(self):
        self.assertIn("housekeep: every 120 minutes, last (none)", self.status())

    def test_status_when_off(self):
        self.repo.set_conf("housekeep_interval_min", "0")
        self.assertIn("housekeep: off", self.status())

    def test_help(self):
        out = self.assertOk(self.repo.run("agent-monitor.sh", "-h"))
        self.assertIn("housekeep_interval_min", out)
        self.assertIn("agent-housekeep.sh", out)
        lines = [l for l in out.splitlines() if "plain" in l and "cloud" in l]
        self.assertTrue(lines, "the help does not say plain and cloud have no loop")


# ================================================================ docs, release


class TestDocs(unittest.TestCase):
    def assertSectionHas(self, code, *words):
        text = "\n".join(principles_section(code))
        self.assertTrue(text, "no %s section" % code)
        for word in words:
            self.assertIn(word, text, "%s does not say %r" % (code, word))

    def test_r5_r6_r7_say_what_housekeep_does(self):
        for code in ("R5", "R6", "R7"):
            with self.subTest(code=code):
                lines = [l for l in principles_section(code) if "housekeep" in l.lower()]
                self.assertEqual(len(lines), 1, "%s needs one housekeep line" % code)

    def test_w8_runs_it_from_the_monitor_loop(self):
        self.assertSectionHas("W8", "housekeep_interval_min", "agent-housekeep.sh")

    def test_the_main_manager_reads_the_block(self):
        lines = [l for code in ("W8", "S8") for l in principles_section(code)
                 if "HOUSEKEEP" in l and "idea rm" in l]
        self.assertTrue(lines, "W8 or S8: the main manager reads the HOUSEKEEP block, judges suspects (idea rm)")

    def test_w12_names_todo_cross(self):
        self.assertSectionHas("W12", "todo cross")

    def test_one_line_per_rule(self):
        for code in ("R5", "R6", "R7", "W8"):
            for line in principles_section(code):
                if "housekeep" in line.lower():
                    self.assertLess(len(line), 260, line)

    def test_readme_lists_the_script(self):
        self.assertIn("bin/agent-housekeep.sh", read_root("README.md"))

    def test_release(self):
        self.assertEqual(json.loads(read_root(".claude-plugin", "plugin.json"))["version"], "0.33.0")


if __name__ == "__main__":
    unittest.main()
