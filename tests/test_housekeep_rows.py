"""Failing tests for agent_housekeep.file_rows (clean-up, requirements/clean-up.md
B5-B8). Written by the task manager first.

CONTRACT. bin/agent_housekeep.py gets one new read-only function, the line
part of clean-up. It reuses the pass's own checks (gather, worktree_lines,
todos, ideas with apply off), never copies them:

    file_rows(root, plugin, gitdir, kind, stale_minutes) -> dict
      "ideas":     [{"n": <line no>, "line": <whole line>, "why": <text>}]
                   exact duplicates (the later line): why "a duplicate of
                   idea <m>"; suspects: why = the pass's reasons joined by
                   "; " ("names task city-ux, done 2026-11-10", "names x.md,
                   no such file"). One entry per line (reasons of both kinds
                   joined by "; "), sorted by n. " | kept <date>" lines never.
      "todos":     [{"name", "line", "kind": "merged"|"stale", "why",
                     "sha": <7-char sha or None>, "days": <int or None>}]
                   in file order, one entry per todo line at most (merged
                   wins). merged: why "merged into origin/main (branch <b>)"
                   or "merged into origin/main (commit <sha7> Merge <name>)",
                   sha set only in the commit form. stale: the pass's stale
                   rule with stale_minutes as the limit; why "stale: no
                   worktree line and no open wait for <d>d", days = whole days.
      "worktrees": [{"path": <path, stripped>, "line": <whole line>,
                     "status", "why"}] in file order: lines whose folder is
                   gone and no live pane, every status. why "folder gone, no
                   live pane", plus " (line says <status>)" for working and
                   final and " (line says human-direct)" for a human-direct
                   line.
      "notes":     the pass's notes (["orca not answering: worktree lines
                   not checked"], ...), never the cleanup sweep's lines.

    Read only: no file written, no agent-file.sh call, no cleanup sweep, no
    agent_state.txt, no stamp. "Now" is AGENT_FAKE_NOW when set. The
    housekeep block of agent-housekeep.sh stays byte for byte
    (tests/test_agent_housekeep.py).
"""

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import BIN, ScriptCase

if BIN not in sys.path:
    sys.path.insert(0, BIN)

NOW = "2026-11-24 12:00"
DAYS14 = 14 * 1440

IDEAS = [
    "city-ux: make the rail wider | 2026-11-01 10:00 | by main",
    "add dark mode | 2026-11-01 10:00 | by main",
    "city-ux: fix colors | 2026-11-01 10:00 | by main | kept 2026-11-05",
    "add dark mode | 2026-11-02 11:00 | by main",
    "see bin/gone-tool.sh for it | 2026-11-20 10:00 | by main",
]


def git(path, *args):
    res = subprocess.run(["git", "-C", path] + list(args),
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError("git %s: %s" % (" ".join(args), res.stderr))
    return res.stdout.strip()


class RowsCase(ScriptCase):

    def setUp(self):
        super().setUp()
        r = self.repo
        self.origin = os.path.join(r.base, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", self.origin],
                       check=True, capture_output=True)
        os.makedirs(os.path.join(r.dir, "bin"), exist_ok=True)
        with open(os.path.join(r.dir, "bin", "tool.sh"), "w") as fh:
            fh.write("true\n")
        git(r.dir, "add", "-A")
        git(r.dir, "commit", "-q", "-m", "bin")
        git(r.dir, "branch", "-M", "main")
        git(r.dir, "remote", "add", "origin", self.origin)
        git(r.dir, "push", "-q", "-u", "origin", "main")
        old = os.environ.get("AGENT_FAKE_NOW")
        os.environ["AGENT_FAKE_NOW"] = NOW
        self.addCleanup(self.restore_now, old)
        import agent_housekeep
        self.hk = agent_housekeep

    @staticmethod
    def restore_now(old):
        if old is None:
            os.environ.pop("AGENT_FAKE_NOW", None)
        else:
            os.environ["AGENT_FAKE_NOW"] = old

    def set_file(self, name, lines):
        with open(os.path.join(self.repo.dir, name), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def rows(self, kind="plain", stale=DAYS14):
        r = self.repo
        return self.hk.file_rows(r.dir, r.plugin, os.path.join(r.dir, ".git"),
                                 kind, stale)

    def merged_task(self, name, keep_branch):
        d = self.repo.dir
        branch = "feat/" + name
        git(d, "checkout", "-q", "-b", branch)
        with open(os.path.join(d, name + ".txt"), "w") as fh:
            fh.write(name + "\n")
        git(d, "add", "-A")
        git(d, "commit", "-q", "-m", name)
        git(d, "push", "-q", "origin", branch)
        git(d, "checkout", "-q", "main")
        git(d, "merge", "-q", "--no-ff", "-m", "Merge " + name, branch)
        git(d, "push", "-q", "origin", "main")
        sha = git(d, "rev-parse", "--short=7", "HEAD")
        if not keep_branch:
            git(d, "branch", "-q", "-D", branch)
            git(d, "push", "-q", "origin", "--delete", branch)
        return sha


class TestFileRows(RowsCase):

    def test_ideas(self):
        self.set_file("agent_ideas.txt", IDEAS)
        self.set_file("agent_completed.txt", [
            "2026-11-10 | city-ux | rail | est 30m actual 40m"])
        ideas = self.rows()["ideas"]
        self.assertEqual([i["n"] for i in ideas], [1, 4, 5])
        self.assertEqual(ideas[0]["line"], IDEAS[0])
        self.assertEqual(ideas[0]["why"], "names task city-ux, done 2026-11-10")
        self.assertEqual(ideas[1]["line"], IDEAS[3])
        self.assertEqual(ideas[1]["why"], "a duplicate of idea 2")
        self.assertEqual(ideas[2]["why"], "names bin/gone-tool.sh, no such file")

    def test_todos_merged_and_stale(self):
        self.merged_task("old", keep_branch=True)
        sha = self.merged_task("older", keep_branch=False)
        lines = [
            "old | big | x | est 30m | opened 2026-11-20 08:00 | by main",
            "older | big | x | est 30m | opened 2026-11-01 08:00 | by main",
            "quiet | big | x | est 30m | opened 2026-11-01 08:00 | by main",
            "young | big | x | est 30m | opened 2026-11-20 08:00 | by main",
            "waits | big | x | est 30m | opened 2026-11-01 08:00 | by main | "
            "waiting question since 2026-11-01 09:00",
        ]
        self.set_file("agent_todo.txt", lines)
        todos = self.rows()["todos"]
        self.assertEqual([t["name"] for t in todos], ["old", "older", "quiet"])
        old, older, quiet = todos
        self.assertEqual(old["kind"], "merged")
        self.assertEqual(old["why"], "merged into origin/main (branch feat/old)")
        self.assertIsNone(old["sha"])
        self.assertEqual(old["line"], lines[0])
        self.assertEqual(older["kind"], "merged")   # merged wins over stale
        self.assertEqual(older["sha"], sha)
        self.assertEqual(older["why"],
                         "merged into origin/main (commit %s Merge older)" % sha)
        self.assertEqual(quiet["kind"], "stale")
        self.assertEqual(quiet["days"], 23)
        self.assertEqual(quiet["why"],
                         "stale: no worktree line and no open wait for 23d")
        self.assertEqual(quiet["line"], lines[2])

    def test_stale_limit_is_the_argument(self):
        self.set_file("agent_todo.txt", [
            "quiet | big | x | est 30m | opened 2026-11-01 08:00 | by main"])
        self.assertEqual(self.rows(stale=30 * 1440)["todos"], [])
        self.assertEqual(len(self.rows(stale=DAYS14)["todos"]), 1)

    def test_worktree_lines(self):
        live = os.path.join(self.repo.base, "wt-live")
        git(self.repo.dir, "worktree", "add", "-q", "-b", "feat/live", live, "main")
        g1 = os.path.join(self.repo.base, "gone-a")
        g2 = os.path.join(self.repo.base, "gone-b")
        g3 = os.path.join(self.repo.base, "gone-c")
        lines = ["%s | gone-a | working | since 2026-11-20 10:00" % g1,
                 "%s | gone-b | idle | since 2026-11-20 10:00" % g2,
                 "%s | live | working | since 2026-11-20 10:00" % live,
                 "%s | gone-c (human-direct) | human-direct | since 2026-11-20 10:00" % g3]
        self.set_file("agent_worktree.txt", lines)
        wts = self.rows()["worktrees"]
        self.assertEqual([w["path"] for w in wts], [g1, g2, g3])
        self.assertEqual(wts[0]["why"], "folder gone, no live pane (line says working)")
        self.assertEqual(wts[1]["why"], "folder gone, no live pane")
        self.assertEqual(wts[2]["why"], "folder gone, no live pane (line says human-direct)")
        self.assertEqual(wts[0]["line"], lines[0])
        self.assertEqual(wts[1]["status"], "idle")

    def test_orca_not_answering_note_and_no_worktree_rows(self):
        self.repo.stub_orca_down()
        g = os.path.join(self.repo.base, "gone")
        self.set_file("agent_worktree.txt", ["%s | gone | idle | since 2026-11-20 10:00" % g])
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = self.repo._path()
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        rows = self.rows(kind="orca")
        self.assertEqual(rows["worktrees"], [])
        self.assertIn("orca not answering: worktree lines not checked", rows["notes"])

    def test_read_only(self):
        self.merged_task("old", keep_branch=True)
        self.set_file("agent_ideas.txt", IDEAS)
        self.set_file("agent_todo.txt", [
            "old | big | x | est 30m | opened 2026-11-20 08:00 | by main"])
        g = os.path.join(self.repo.base, "gone")
        self.set_file("agent_worktree.txt", ["%s | gone | idle | since 2026-11-20 10:00" % g])
        names = ("agent_ideas.txt", "agent_todo.txt", "agent_worktree.txt",
                 "agent_completed.txt")
        before = {}
        for n in names:
            with open(os.path.join(self.repo.dir, n)) as fh:
                before[n] = fh.read()
        self.rows()
        for n in names:
            with open(os.path.join(self.repo.dir, n)) as fh:
                self.assertEqual(fh.read(), before[n], n)
        self.assertFalse(os.path.exists(os.path.join(self.repo.dir, "agent_state.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.repo.dir, ".git",
                                                     "agent_housekeep.last")))
        self.assertTrue(git(self.repo.dir, "branch", "--list", "feat/old"))


class TestFileRowsBounce1(RowsCase):
    """Reviewer findings 2, 3, 6 and the E2E finding (2026-11-24)."""

    def test_line_numbers_count_newlines_only(self):
        with open(os.path.join(self.repo.dir, "agent_ideas.txt"), "w", newline="") as fh:
            fh.write("progress 10%\r100% done | 2026-11-01 10:00 | by main\n"
                     "add dark mode | 2026-11-01 10:00 | by main\n"
                     "add dark mode | 2026-11-02 11:00 | by main\n")
        ideas = self.rows()["ideas"]
        self.assertEqual([(i["n"], i["why"]) for i in ideas], [(3, "a duplicate of idea 2")])

    def test_a_kept_duplicate_is_no_row(self):
        self.set_file("agent_ideas.txt", [
            "add dark mode | 2026-11-01 10:00 | by main",
            "add dark mode | 2026-11-02 11:00 | by main | kept 2026-11-05"])
        self.assertEqual(self.rows()["ideas"], [])

    def test_an_existing_folder_is_no_worktree_row(self):
        folder = os.path.join(self.repo.base, "not-a-worktree")
        os.mkdir(folder)
        self.set_file("agent_worktree.txt", [
            "%s | live-task | working | since 2026-11-20 10:00" % folder])
        self.assertEqual(self.rows()["worktrees"], [])

    def test_per_machine_agent_files_are_never_gone(self):
        self.assertFalse(os.path.exists(os.path.join(self.repo.dir, "agent_state.txt")))
        self.set_file("agent_ideas.txt", [
            "grep the worktree agent_state.txt for DONE | 2026-11-20 10:00 | by main",
            "agent_monitor.txt keeps old lines | 2026-11-20 10:00 | by main",
            "see agent_gone.txt for it | 2026-11-20 10:00 | by main"])
        ideas = self.rows()["ideas"]
        self.assertEqual([(i["n"], i["why"]) for i in ideas],
                         [(3, "names agent_gone.txt, no such file")])

if __name__ == "__main__":
    unittest.main()
