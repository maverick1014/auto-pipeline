"""Tests of bin/agent_cleanfiles.py (agent-cleanup.sh --files): rubbish docs, old state copies,
finished mocks, outdated agent_* lines; agent_completed.txt is never touched.

requirements/clean-up.md. One class per feature. Older task contracts: git log -p of this file.
"""

import glob
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import BIN, ROOT, ScriptCase

NOW = "2026-11-24 12:00"
TABLE_HEAD = "id | what | where | why | how removed"
KEPT_HEAD = "what | why kept"
FOOTER = ("To remove: agent-cleanup.sh --files --yes <ids>|all|none. "
          "Nothing is removed without --yes.")
WHY_DOC = "doc not allowed by the docs rule"


def git(path, *args, **kw):
    res = subprocess.run(["git", "-C", path] + list(args),
                         capture_output=True, text=True)
    if kw.get("check", True) and res.returncode != 0:
        raise AssertionError("git %s: %s" % (" ".join(args), res.stderr))
    return res.stdout.strip()


class FilesCase(ScriptCase):
    """A project with a bare origin and main pushed, plain runtime."""

    script = "agent-cleanup.sh"

    def setUp(self):
        super().setUp()
        r = self.repo
        r.set_conf("runtime", "plain")
        self.origin = os.path.join(r.base, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", self.origin],
                       check=True, capture_output=True)
        git(r.dir, "add", "-A")
        git(r.dir, "commit", "-q", "-m", "conf", check=False)
        git(r.dir, "branch", "-M", "main")
        git(r.dir, "remote", "add", "origin", self.origin)
        git(r.dir, "push", "-q", "-u", "origin", "main")
        self.gitdir = os.path.join(r.dir, ".git")

    # ---- fixture ----

    def p(self, rel):
        return os.path.join(self.repo.dir, rel)

    def write(self, rel, text="x\n"):
        full = self.p(rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(text)
        return full

    def commit_all(self, msg="plant", push=True):
        git(self.repo.dir, "add", "-A")
        git(self.repo.dir, "commit", "-q", "-m", msg)
        if push:
            git(self.repo.dir, "push", "-q", "origin", "main")

    def set_file(self, rel, lines):
        with open(self.p(rel), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def read(self, rel):
        with open(self.p(rel)) as fh:
            return fh.read()

    def head(self):
        return git(self.repo.dir, "rev-parse", "HEAD")

    def status(self):
        return git(self.repo.dir, "status", "--porcelain", "--untracked-files=all")

    def snapshot(self):
        """Every file under the project (not .git) with its bytes."""
        snap = {}
        for dirpath, dirnames, filenames in os.walk(self.repo.dir):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, self.repo.dir)
                if os.path.islink(full):
                    snap[rel] = "link:" + os.readlink(full)
                    continue
                with open(full, "rb") as fh:
                    snap[rel] = fh.read()
        return snap

    # ---- running ----

    def files(self, *args, **kw):
        env = dict(kw.pop("env", None) or {})
        env.setdefault("AGENT_FAKE_NOW", NOW)
        return self.repo.run("agent-cleanup.sh", "--files", *args, env=env, **kw)

    def dry(self, **kw):
        return self.assertOk(self.files(**kw))

    def yes(self, ids, **kw):
        return self.files("--yes", ids, **kw)

    def rows(self, out):
        """id -> [what, where, why, how]."""
        lines = self.lines(out)
        if TABLE_HEAD not in lines:
            return {}
        rows = {}
        for line in lines[lines.index(TABLE_HEAD) + 1:]:
            if not re.match(r"^[DSMITW]\d+ \| ", line):
                break
            parts = line.split(" | ")
            self.assertEqual(len(parts), 5, line)
            rows[parts[0]] = parts[1:]
        return rows

    def by_what(self, out):
        return {v[0]: (k, v) for k, v in self.rows(out).items()}

    def kept(self, out):
        lines = self.lines(out)
        if KEPT_HEAD not in lines:
            return {}
        kept = {}
        for line in lines[lines.index(KEPT_HEAD) + 1:]:
            if " | " not in line:
                break
            what, why = line.split(" | ", 1)
            kept[what] = why
        return kept

    def id_of(self, out, what):
        found = self.by_what(out)
        self.assertIn(what, found, "no row for %r in:\n%s" % (what, out))
        return found[what][0]


# ---------------------------------------------------------------- A. command


class TestCommand(FilesCase):

    def test_a1_dry_run_prints_the_table_and_changes_nothing(self):
        self.write("notes.md")
        self.commit_all()
        before, head = self.snapshot(), self.head()
        out = self.dry()
        lines = self.lines(out)
        self.assertEqual(lines[0], "=== clean-up files (dry run, nothing removed) ===")
        self.assertIn(TABLE_HEAD, lines)
        self.assertEqual(lines[-1], FOOTER)
        rows = self.rows(out)
        self.assertEqual(rows["D1"], ["notes.md", "repo, tracked", WHY_DOC,
                                      "git rm, one commit"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.head(), head)
        self.assertTrue(os.path.isfile(os.path.join(self.gitdir,
                                                    "agent-cleanup-files.last")))

    def test_a1_nothing_to_clean(self):
        out = self.dry()
        self.assertEqual(self.lines(out), ["=== clean-up files ===",
                                           "nothing to clean"])

    def test_a2_yes_removes_exactly_the_picked_rows(self):
        self.write("a.md")
        self.write("b.md")
        self.write("c.md")
        self.commit_all()
        out = self.dry()
        a, c = self.id_of(out, "a.md"), self.id_of(out, "c.md")
        res = self.yes("%s,%s" % (a, c))
        self.assertOk(res)
        self.assertFalse(os.path.exists(self.p("a.md")))
        self.assertTrue(os.path.exists(self.p("b.md")))
        self.assertFalse(os.path.exists(self.p("c.md")))

    def test_a3_yes_all_removes_every_row_of_the_saved_table(self):
        self.write("a.md")
        self.write("b.md")
        self.commit_all()
        self.dry()
        self.assertOk(self.yes("all"))
        self.assertFalse(os.path.exists(self.p("a.md")))
        self.assertFalse(os.path.exists(self.p("b.md")))

    def test_a4_yes_none_changes_nothing(self):
        self.write("a.md")
        self.commit_all()
        self.dry()
        before, head = self.snapshot(), self.head()
        out = self.assertOk(self.yes("none"))
        self.assertIn("nothing removed", out)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.head(), head)

    def test_a5_bad_calls_are_usage_errors_and_change_nothing(self):
        self.write("a.md")
        self.commit_all()
        self.dry()
        before, head = self.snapshot(), self.head()
        env = {"AGENT_FAKE_NOW": NOW}
        for args in (["--files", "--apply"], ["--files", "--yes"],
                     ["--yes", "D1"], ["--files", "--yes", "all,D1"]):
            with self.subTest(args=args):
                res = self.repo.run("agent-cleanup.sh", *args, env=env)
                self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
                self.assertTrue(res.stderr.strip())
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.head(), head)

    def test_a6_main_manager_only(self):
        self.write("a.md")
        self.commit_all()
        before, head = self.snapshot(), self.head()
        for args in (["--files"], ["--files", "--yes", "all"]):
            with self.subTest(args=args):
                res = self.repo.run("agent-cleanup.sh", *args,
                                    env={"AGENT_ROLE": "task-manager",
                                         "AGENT_FAKE_NOW": NOW})
                self.assertEqual(res.returncode, 1)
                self.assertIn("REFUSED", res.stderr)
                self.assertIn("main manager only", res.stderr)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.head(), head)

    def test_a7_the_automatic_sweep_never_touches_files_or_lines(self):
        self.write("notes.md")
        self.write("mock/old-mock.html")
        self.commit_all()
        self.write("agent_state.trim-2026-10-01.txt", "old\n")
        self.set_file("agent_todo.txt", [
            "quiet | big | something | est 30m | opened 2026-11-01 08:00 | by main"])
        before, head = self.snapshot(), self.head()
        for args in (["--apply"], ["--apply", "--short"], []):
            with self.subTest(args=args):
                res = self.repo.run("agent-cleanup.sh", *args,
                                    env={"AGENT_FAKE_NOW": NOW})
                self.assertOk(res)
                self.assertNotIn("clean-up files", res.stdout)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.head(), head)

    def test_usage_names_the_new_flags(self):
        out = self.assertOk(self.repo.run("agent-cleanup.sh", "-h"))
        self.assertIn("--files", out)
        self.assertIn("--yes", out)

    def test_the_logic_lives_in_its_own_module_and_reuses_housekeep(self):
        path = os.path.join(BIN, "agent_cleanfiles.py")
        self.assertTrue(os.path.isfile(path), "bin/agent_cleanfiles.py")
        with open(path) as fh:
            src = fh.read()
        self.assertIn("import agent_housekeep", src)
        with open(os.path.join(BIN, "agent-cleanup.sh")) as fh:
            self.assertIn("agent_cleanfiles.py", fh.read())


# ---------------------------------------------------------------- B1. docs


class TestDocs(FilesCase):

    LISTED_TRACKED = ["CHANGELOG.md", "CONTRIBUTING.md", "NOTES.MD",
                      "design-old.md", "docs/api/auth.md", "docs/setup.md",
                      "guide.rst", "manual.adoc", "packages/web/README.md",
                      "plan.markdown", "spec.pdf", "src/notes.md",
                      "mock/notes.md"]
    NEVER = ["README.md", "PRINCIPLES.md", "CLAUDE.md", "AGENTS.md",
             "requirements/pos.md", "tests/README.md", "test/how.md",
             "app/tests/fixture.md", "skills/s/SKILL.md", "skills/city/setup.md",
             "agents/worker.md", "hooks/h.md", "bin/b.md",
             ".claude-plugin/p.md", ".claude/commands/c.md",
             ".github/PULL_REQUEST_TEMPLATE.md", ".cursor/rules/r.md",
             "LICENSE", "LICENSE.md", "docs/LICENCE.md", "COPYING.rst",
             "NOTICE.md", "requirements.txt", "CMakeLists.txt", "robots.txt",
             # md-slim-principles A 1, section 4: the rule files beside the core are never offered
             "GLOSSARY.md", "rules/checks.md", "rules/ui.md",
             "page.html", "src/app.ts", "agent_estimate.txt", "notes.txt"]

    def plant(self):
        for rel in self.LISTED_TRACKED + self.NEVER:
            self.write(rel)
        self.write(".gitignore", "node_modules/\nbuild/\n.secrets/\n")
        self.write("node_modules/x/README.md")
        self.write("build/out.md")
        self.write(".secrets/keys.md")
        self.commit_all()
        self.write("TODO.md", "draft\n")          # untracked, not ignored
        self.write("meeting-2026.pdf", "pdf\n")   # untracked
        # a nested repo inside the project: never entered
        nested = self.p("vendor/lib")
        os.makedirs(nested)
        git(nested, "init", "-q")
        self.write("vendor/lib/README.md")
        self.write("vendor/lib/notes.md")

    def test_b1_exactly_the_docs_outside_the_rule_are_listed(self):
        self.plant()
        out = self.dry()
        found = self.by_what(out)
        listed = set(self.LISTED_TRACKED) | {"TODO.md", "meeting-2026.pdf"}
        self.assertEqual(set(w for w in found if found[w][0].startswith("D")),
                         listed)
        for rel in self.LISTED_TRACKED:
            with self.subTest(rel=rel):
                _id, v = found[rel]
                self.assertEqual(v[1:], ["repo, tracked", WHY_DOC,
                                         "git rm, one commit"])
        for rel in ("TODO.md", "meeting-2026.pdf"):
            with self.subTest(rel=rel):
                self.assertEqual(found[rel][1][1:], ["repo, untracked", WHY_DOC, "rm"])
        for rel in self.NEVER + ["node_modules/x/README.md", "build/out.md",
                                 ".secrets/keys.md", "vendor/lib/README.md",
                                 "vendor/lib/notes.md", "agent_completed.txt",
                                 "agent_ideas.txt", "agent_todo.txt",
                                 "agent_worktree.txt", "agent.conf"]:
            with self.subTest(never=rel):
                self.assertNotIn(rel, found)

    def test_b1_ids_follow_the_path_order(self):
        for rel in ("b.md", "a.md", "c/z.md"):
            self.write(rel)
        self.commit_all()
        rows = self.rows(self.dry())
        self.assertEqual([rows[i][0] for i in ("D1", "D2", "D3")],
                         ["a.md", "b.md", "c/z.md"])

    def test_no_note_when_no_doc_is_listed(self):
        self.write("mock/old-mock.html")
        self.commit_all()
        out = self.dry()
        self.assertFalse(any("docs_keep" in l for l in self.lines(out)), out)

    def test_no_docs_keep_note_ever(self):
        # settings-configure: docs_keep is a fixed constant (empty); no note asks to set it
        self.write("notes.md")
        self.commit_all()
        self.assertFalse(any("docs_keep" in l for l in self.lines(self.dry())))

    def test_n5_a_doc_in_use_is_kept_not_listed(self):
        self.write("used.md")
        self.write("bin/tool.sh", 'cat "used.md"\n')
        self.write("said.md")
        self.write("bin/other.sh", "# see said.md for why\n")
        self.commit_all()
        out = self.dry()
        found = self.by_what(out)
        self.assertNotIn("used.md", found)
        self.assertEqual(self.kept(out).get("used.md"), "in use: bin/tool.sh")
        self.assertIn("said.md", found)   # a comment mention is not use

    def test_n6_a_tracked_doc_with_uncommitted_changes_is_kept(self):
        self.write("design-old.md")
        self.commit_all()
        self.write("design-old.md", "edited\n")
        out = self.dry()
        self.assertNotIn("design-old.md", self.by_what(out))
        self.assertEqual(self.kept(out).get("design-old.md"), "uncommitted changes")


# ---------------------------------------------------------------- B2, B3


class TestStateCopies(FilesCase):

    def plant(self):
        with open(os.path.join(self.gitdir, "info", "exclude"), "a") as fh:
            fh.write("agent_state.*.txt\n")
        for name in ("agent_state.2026-11-01-101500.txt",   # 23 days
                     "agent_state.trim-2026-11-09.txt",      # 15 days
                     "agent_state.trim-2026-11-10.txt",      # 14 days
                     "agent_state.2026-11-10-235959.txt",    # 14 days
                     "agent_state.trim-bad.txt",
                     "agent_state.txt",
                     "agent_state.txt.tmp.12345",
                     "agent_monitor.txt.tmp.12345",
                     "sub/agent_state.trim-2026-01-01.txt"):
            self.write(name, "old\n")

    def test_b2_only_copies_older_than_cleanup_days(self):
        self.plant()
        found = self.by_what(self.dry())
        self.assertIn("agent_state.2026-11-01-101500.txt", found)
        self.assertIn("agent_state.trim-2026-11-09.txt", found)
        for name in ("agent_state.trim-2026-11-10.txt",
                     "agent_state.2026-11-10-235959.txt",
                     "agent_state.trim-bad.txt", "agent_state.txt",
                     "agent_state.txt.tmp.12345", "agent_monitor.txt.tmp.12345",
                     "sub/agent_state.trim-2026-01-01.txt"):
            with self.subTest(never=name):
                self.assertNotIn(name, found)
        sid, v = found["agent_state.trim-2026-11-09.txt"]
        self.assertTrue(sid.startswith("S"))
        self.assertEqual(v[1], "repo, untracked")
        self.assertIn("15 days old", v[2])
        self.assertIn("over 14", v[2])
        self.assertTrue(v[3].startswith("rm"))

    def test_b2_remove_a_state_copy(self):
        self.plant()
        out = self.dry()
        sid = self.id_of(out, "agent_state.trim-2026-11-09.txt")
        self.assertOk(self.yes(sid))
        self.assertFalse(os.path.exists(self.p("agent_state.trim-2026-11-09.txt")))
        self.assertTrue(os.path.exists(self.p("agent_state.txt")))
        self.assertTrue(os.path.exists(self.p("agent_state.2026-11-01-101500.txt")))

    MON = ["/x/city-device-join | city-device-join | pane done | commit 35m ago | "
           "activity 57m ago | STALL | 2026-10-05 15:35",
           "/x/city-tier | city-tier | pane working | commit 1m ago | "
           "activity 73m ago | OK | 2026-10-05 15:35"]

    def test_b3_a_monitor_file_is_a_leftover(self):
        self.set_file("agent_monitor.txt", self.MON)
        found = self.by_what(self.dry())
        self.assertIn("agent_monitor.txt", found)
        sid, v = found["agent_monitor.txt"]
        self.assertTrue(sid.startswith("S"))
        self.assertIn("monitor", v[2])
        self.assertTrue(v[3].startswith("rm"))

    def test_b3_a_young_monitor_file_is_listed_too(self):
        # nothing writes it since bin/agent-monitor.sh went (2026-11-24): any age
        self.set_file("agent_monitor.txt", [
            "/x/a | a | pane done | commit 1m ago | activity 1m ago | OK | 2026-11-20 10:00"])
        self.assertIn("agent_monitor.txt", self.by_what(self.dry()))

# ---------------------------------------------------------------- B4. mocks


class TestMocks(FilesCase):

    def plant(self):
        for name in ("done", "open", "orphan", "dropped", "used", "mentioned"):
            self.write("mock/%s-mock.html" % name, "<html></html>\n")
        self.write("mock/sub/deep-mock.html")
        self.write("mock/readme.html")
        self.write("tests/test_x.py",
                   'MOCK = os.path.join(ROOT, "mock", "used-mock.html")\n')
        self.write("tests/test_y.py",
                   '"""Approved mock mock/mentioned-mock.html (owner)."""\n'
                   "# see mock/mentioned-mock.html\n")
        self.write("requirements/r.md", "Mock: mock/mentioned-mock.html\n")
        self.commit_all()
        self.set_file("agent_completed.txt", [
            "2026-10-01 | done | built it | est 30m actual 40m",
            "2026-10-02 | dropped | gone | est 30m actual - | dropped: owner said no",
            "2026-10-03 | used | built | est 30m actual 20m",
            "2026-10-04 | mentioned | built | est 30m actual 20m"])
        self.set_file("agent_todo.txt", [
            "open | big | still going | est 60m | opened 2026-11-23 08:00 | by main"])

    def test_b4_mocks_of_no_open_task(self):
        self.plant()
        out = self.dry()
        found = self.by_what(out)
        rows = {w: v for w, (i, v) in found.items() if i.startswith("M")}
        self.assertEqual(set(rows), {"mock/done-mock.html", "mock/orphan-mock.html",
                                     "mock/dropped-mock.html",
                                     "mock/mentioned-mock.html"})
        self.assertIn("task done done 2026-10-01", rows["mock/done-mock.html"][2])
        self.assertIn("task dropped dropped 2026-10-02", rows["mock/dropped-mock.html"][2])
        self.assertIn("no task named orphan", rows["mock/orphan-mock.html"][2])
        self.assertEqual(rows["mock/done-mock.html"][1], "repo, tracked")
        self.assertEqual(rows["mock/done-mock.html"][3], "git rm, one commit")
        for rel in ("mock/open-mock.html", "mock/used-mock.html",
                    "mock/sub/deep-mock.html", "mock/readme.html"):
            with self.subTest(never=rel):
                self.assertNotIn(rel, found)
        self.assertEqual(self.kept(out).get("mock/used-mock.html"),
                         "in use: tests/test_x.py")

    def test_b4_an_untracked_mock_goes_by_rm(self):
        self.write("mock/scratch-mock.html")
        found = self.by_what(self.dry())
        self.assertEqual(found["mock/scratch-mock.html"][1][1:],
                         ["repo, untracked", "no task named scratch", "rm"])


# ---------------------------------------------------------------- B5-B8 lines


IDEAS = [
    "city-ux: make the rail wider | 2026-11-01 10:00 | by main",          # 1 suspect
    "add dark mode | 2026-11-01 10:00 | by main",                         # 2
    "city-ux: fix colors | 2026-11-01 10:00 | by main | kept 2026-11-05",  # 3 kept
    "add dark mode | 2026-11-02 11:00 | by main",                         # 4 duplicate of 2
    "a plain idea | 2026-11-20 10:00 | by main",                          # 5
]


class TestLines(FilesCase):

    def plant_ideas(self):
        self.set_file("agent_ideas.txt", IDEAS)
        self.set_file("agent_completed.txt", [
            "2026-11-10 | city-ux | rail | est 30m actual 40m"])

    def test_b5_ideas_duplicates_and_suspects_never_kept_lines(self):
        self.plant_ideas()
        out = self.dry()
        rows = {i: v for i, v in self.rows(out).items() if i.startswith("I")}
        self.assertEqual(sorted(v[1] for v in rows.values()),
                         ["agent_ideas.txt line 1", "agent_ideas.txt line 4"])
        by_line = {v[1]: v for v in rows.values()}
        one = by_line["agent_ideas.txt line 1"]
        self.assertTrue(one[0].startswith("idea: city-ux: make the rail wider"))
        self.assertIn("city-ux", one[2])
        self.assertEqual(one[3], "idea rm, line backed up")
        self.assertIn("duplicate", by_line["agent_ideas.txt line 4"][2])
        self.assertEqual(self.rows(out)["I1"][1], "agent_ideas.txt line 1")

    def test_b5_remove_ideas_bottom_up_with_a_backup(self):
        self.plant_ideas()
        out = self.dry()
        self.assertOk(self.yes("I1,I2"))
        self.assertEqual(self.read("agent_ideas.txt").splitlines(),
                         [IDEAS[1], IDEAS[2], IDEAS[4]])
        backups = glob.glob(os.path.join(self.gitdir, "agent-cleanup", "*.txt"))
        self.assertEqual(len(backups), 1)
        with open(backups[0]) as fh:
            text = fh.read()
        self.assertIn("agent_ideas.txt | " + IDEAS[0], text)
        self.assertIn("agent_ideas.txt | " + IDEAS[3], text)
        self.assertTrue(out)

    def test_e15_an_idea_that_moved_up_still_matches_by_text(self):
        self.plant_ideas()
        out = self.dry()
        iid = [i for i, v in self.rows(out).items()
               if v[1] == "agent_ideas.txt line 4"][0]
        # line 3 (the kept idea) goes by hand: the duplicate is now line 3
        self.assertOk(self.repo.run("agent-file.sh", "idea", "rm", "3"))
        self.assertOk(self.yes(iid))
        self.assertEqual(self.read("agent_ideas.txt").splitlines(),
                         [IDEAS[0], IDEAS[1], IDEAS[4]])

    def merged_task(self, name, keep_branch):
        r = self.repo
        branch = "feat/" + name
        git(r.dir, "checkout", "-q", "-b", branch)
        self.write(name + ".txt")
        git(r.dir, "add", "-A")
        git(r.dir, "commit", "-q", "-m", name)
        git(r.dir, "push", "-q", "origin", branch)
        git(r.dir, "checkout", "-q", "main")
        git(r.dir, "merge", "-q", "--no-ff", "-m", "Merge " + name, branch)
        git(r.dir, "push", "-q", "origin", "main")
        sha = git(r.dir, "rev-parse", "--short=7", "HEAD")
        if not keep_branch:
            git(r.dir, "branch", "-q", "-D", branch)
            git(r.dir, "push", "-q", "origin", "--delete", branch)
        return sha

    def test_b6_merged_todo_by_branch_and_by_merge_commit(self):
        self.merged_task("old", keep_branch=True)
        sha = self.merged_task("older", keep_branch=False)
        self.set_file("agent_todo.txt", [
            "old | big | did it | est 30m | opened 2026-11-20 08:00 | by main",
            "older | big | did it | est 30m | opened 2026-11-20 08:00 | by main"])
        found = self.by_what(self.dry())
        tid, v = found["todo old"]
        self.assertTrue(tid.startswith("T"))
        self.assertEqual(v[1], "agent_todo.txt")
        self.assertIn("merged into origin/main", v[2])
        self.assertTrue(v[3].startswith("todo done"))
        self.assertTrue(v[3].endswith("line backed up"))
        v2 = found["todo older"][1]
        self.assertIn("merged into origin/main", v2[2])
        self.assertIn("todo done --merge " + sha, v2[3])

    def test_b6_apply_moves_the_line_with_todo_done(self):
        sha = self.merged_task("older", keep_branch=False)
        self.set_file("agent_todo.txt", [
            "older | big | did it | est 30m | opened 2026-11-20 08:00 | by main"])
        before = self.read("agent_completed.txt")
        out = self.dry()
        self.assertOk(self.yes(self.id_of(out, "todo older")))
        self.assertEqual(self.read("agent_todo.txt").strip(), "")
        after = self.read("agent_completed.txt")
        self.assertTrue(after.startswith(before))
        new = after[len(before):].strip().splitlines()
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].split(" | ")[1], "older")
        self.assertTrue(sha)

    def test_b7_stale_todo_lines(self):
        live = os.path.join(self.repo.base, "wt-live")
        git(self.repo.dir, "worktree", "add", "-q", "-b", "feat/live", live, "main")
        self.set_file("agent_todo.txt", [
            "quiet | big | x | est 30m | opened 2026-11-01 08:00 | by main",
            "young | big | x | est 30m | opened 2026-11-20 08:00 | by main",
            "waits | big | x | est 30m | opened 2026-11-01 08:00 | by main | "
            "waiting question since 2026-11-01 09:00",
            "live | big | x | est 30m | opened 2026-11-01 08:00 | by main",
            "moved | big | x | est 30m | opened 2026-11-01 08:00 | by main | "
            "stage workers since 2026-11-20 08:00"])
        self.set_file("agent_worktree.txt", ["%s | live | working | since 2026-11-01 08:00" % live])
        found = self.by_what(self.dry())
        todo = {w for w, (i, _v) in found.items() if i.startswith("T")}
        self.assertEqual(todo, {"todo quiet"})
        v = found["todo quiet"][1]
        self.assertIn("stale", v[2])
        self.assertIn("23d", v[2])
        self.assertTrue(v[3].startswith("todo drop"))

    def test_b7_apply_drops_the_line(self):
        self.set_file("agent_todo.txt", [
            "quiet | big | x | est 30m | opened 2026-11-01 08:00 | by main"])
        out = self.dry()
        self.assertOk(self.yes(self.id_of(out, "todo quiet")))
        self.assertEqual(self.read("agent_todo.txt").strip(), "")
        last = self.read("agent_completed.txt").strip().splitlines()[-1]
        self.assertIn("| quiet |", last)
        self.assertIn("dropped: clean-up: stale 23d", last)

    def test_b8_worktree_lines_whose_folder_is_gone(self):
        live = os.path.join(self.repo.base, "wt-live")
        git(self.repo.dir, "worktree", "add", "-q", "-b", "feat/live", live, "main")
        gone1 = os.path.join(self.repo.base, "gone-working")
        gone2 = os.path.join(self.repo.base, "gone-idle")
        self.set_file("agent_worktree.txt", [
            "%s | gone-working | working | since 2026-11-20 10:00" % gone1,
            "%s | gone-idle | idle | since 2026-11-20 10:00" % gone2,
            "%s | live | working | since 2026-11-20 10:00" % live])
        found = self.by_what(self.dry())
        w = {k: v for k, (i, v) in found.items() if i.startswith("W")}
        self.assertEqual(set(w), {"worktree line " + gone1, "worktree line " + gone2})
        self.assertIn("folder gone, no live pane", w["worktree line " + gone1][2])
        self.assertIn("line says working", w["worktree line " + gone1][2])
        self.assertEqual(w["worktree line " + gone2][1], "agent_worktree.txt")
        self.assertEqual(w["worktree line " + gone2][3], "worktree rm, line backed up")

    def test_b8_apply_removes_the_line(self):
        gone = os.path.join(self.repo.base, "gone-working")
        self.set_file("agent_worktree.txt", [
            "%s | gone-working | working | since 2026-11-20 10:00" % gone])
        out = self.dry()
        self.assertOk(self.yes(self.id_of(out, "worktree line " + gone)))
        self.assertEqual(self.read("agent_worktree.txt").strip(), "")

    def test_order_of_kinds_in_the_table(self):
        self.write("notes.md")
        self.write("mock/old-mock.html")
        self.commit_all()
        self.write("agent_state.trim-2026-10-01.txt", "old\n")
        self.plant_ideas()
        self.set_file("agent_todo.txt", [
            "quiet | big | x | est 30m | opened 2026-11-01 08:00 | by main"])
        self.set_file("agent_worktree.txt", [
            "%s | gone | idle | since 2026-11-20 10:00"
            % os.path.join(self.repo.base, "gone")])
        ids = list(self.rows(self.dry()))
        self.assertEqual([i[0] for i in ids], list("DSMIITW"))
        self.assertEqual(ids, ["D1", "S1", "M1", "I1", "I2", "T1", "W1"])


# ---------------------------------------------------------------- C. remove


class TestRemove(FilesCase):

    def test_c1_no_saved_table_is_refused(self):
        self.write("a.md")
        self.commit_all()
        before, head = self.snapshot(), self.head()
        res = self.yes("D1")
        self.assertEqual(res.returncode, 1)
        self.assertIn("REFUSED: run agent-cleanup.sh --files first", res.stdout + res.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.head(), head)

    def test_c2_an_unknown_id_refuses_all(self):
        self.write("a.md")
        self.commit_all()
        self.dry()
        before, head = self.snapshot(), self.head()
        res = self.yes("D1,D9")
        self.assertEqual(res.returncode, 1)
        self.assertIn("REFUSED: D9 unknown", res.stdout + res.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.head(), head)

    def test_c2_a_row_that_changed_since_the_table_refuses_all(self):
        self.write("a.md")
        self.write("b.md")
        self.commit_all()
        self.dry()
        os.remove(os.path.join(self.repo.dir, "a.md"))   # D1 is no row any more
        self.commit_all()
        before, head = self.snapshot(), self.head()
        res = self.yes("D1,D2")
        self.assertEqual(res.returncode, 1)
        self.assertIn("REFUSED: D1 changed since the table", res.stdout + res.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.head(), head)

    def test_c2_an_edited_idea_line_refuses(self):
        self.set_file("agent_ideas.txt", IDEAS[:2] + [IDEAS[1]])
        self.dry()
        self.set_file("agent_ideas.txt", IDEAS[:2] + ["add dark mode now | 2026-11-02 11:00 | by main"])
        before = self.snapshot()
        res = self.yes("I1")
        self.assertEqual(res.returncode, 1)
        self.assertIn("REFUSED", res.stdout + res.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_e14_a_forged_saved_table_cannot_name_agent_completed(self):
        self.set_file("agent_completed.txt", ["2026-10-01 | done | x | est 30m actual 40m"])
        self.write("a.md")
        self.commit_all()
        self.dry()
        last = os.path.join(self.gitdir, "agent-cleanup-files.last")
        with open(last) as fh:
            text = fh.read()
        with open(last, "w") as fh:
            fh.write(text.replace("a.md", "agent_completed.txt"))
        before, head = self.snapshot(), self.head()
        res = self.yes("D1")
        self.assertEqual(res.returncode, 1)
        self.assertIn("REFUSED", res.stdout + res.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.head(), head)

    def test_c3_ids_any_case_spaces_and_repeats(self):
        self.write("a.md")
        self.write("mock/old-mock.html")
        self.commit_all()
        self.dry()
        out = self.assertOk(self.yes("d1, m1 M1"))
        self.assertFalse(os.path.exists(self.p("a.md")))
        self.assertFalse(os.path.exists(self.p("mock/old-mock.html")))
        self.assertEqual(self.lines(out)[-1], "clean-up: removed 2 of 2 picked")

    def test_c4_a_merge_in_progress_refuses(self):
        self.write("a.md")
        self.commit_all()
        self.dry()
        with open(os.path.join(self.gitdir, "MERGE_HEAD"), "w") as fh:
            fh.write(self.head() + "\n")
        before, head = self.snapshot(), self.head()
        res = self.yes("D1")
        self.assertEqual(res.returncode, 1)
        self.assertIn("REFUSED", res.stdout + res.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.head(), head)

    def test_c6_c8_one_commit_for_tracked_files_only_those_paths(self):
        self.write("a.md")
        self.write("docs/b.md")
        self.write("mock/old-mock.html")
        self.commit_all()
        self.write("TODO.md", "draft\n")             # untracked doc
        self.write("staged.py", "print(1)\n")
        git(self.repo.dir, "add", "staged.py")       # someone's staged work
        out = self.dry()
        head = self.head()
        out = self.assertOk(self.yes("all"))
        self.assertEqual(git(self.repo.dir, "rev-list", "--count", head + "..HEAD"), "1")
        self.assertEqual(git(self.repo.dir, "log", "-1", "--format=%s"),
                         "clean-up: 3 files")
        changed = git(self.repo.dir, "show", "--name-status", "--format=", "HEAD").splitlines()
        self.assertEqual(sorted(changed), ["D\ta.md", "D\tdocs/b.md",
                                           "D\tmock/old-mock.html"])
        self.assertIn("A  staged.py", self.status())
        self.assertFalse(os.path.exists(self.p("TODO.md")))
        sha7 = git(self.repo.dir, "rev-parse", "--short=7", "HEAD")
        lines = self.lines(out)
        self.assertIn("commit %s clean-up: 3 files (not pushed)" % sha7, lines)
        self.assertIn("removed: D1 TODO.md", lines)
        self.assertEqual(lines[-1], "clean-up: removed 4 of 4 picked")

    def test_c7_never_pushes(self):
        self.write("a.md")
        self.commit_all()
        origin_head = git(self.origin, "rev-parse", "main")
        self.dry()
        self.assertOk(self.yes("D1"))
        self.assertEqual(git(self.origin, "rev-parse", "main"), origin_head)

    def test_untracked_only_makes_no_commit(self):
        self.write("TODO.md")
        self.dry()
        head = self.head()
        out = self.assertOk(self.yes("D1"))
        self.assertEqual(self.head(), head)
        self.assertFalse(any(l.startswith("commit ") for l in self.lines(out)))

    def test_a_symlink_doc_goes_as_a_link_only(self):
        target = os.path.join(self.repo.base, "outside.md")
        with open(target, "w") as fh:
            fh.write("keep me\n")
        os.symlink(target, self.p("link.md"))
        out = self.dry()
        self.assertOk(self.yes(self.id_of(out, "link.md")))
        self.assertFalse(os.path.lexists(self.p("link.md")))
        self.assertTrue(os.path.isfile(target))

    def test_c5_c8_backup_of_every_removed_line(self):
        self.set_file("agent_ideas.txt", IDEAS[:2] + [IDEAS[1]])
        quiet = "quiet | big | x | est 30m | opened 2026-11-01 08:00 | by main"
        gone = os.path.join(self.repo.base, "gone")
        wline = "%s | gone | idle | since 2026-11-20 10:00" % gone
        self.set_file("agent_todo.txt", [quiet])
        self.set_file("agent_worktree.txt", [wline])
        self.dry()
        out = self.assertOk(self.yes("all"))
        backups = glob.glob(os.path.join(self.gitdir, "agent-cleanup", "*.txt"))
        self.assertEqual(len(backups), 1)
        with open(backups[0]) as fh:
            text = fh.read().splitlines()
        self.assertIn("agent_todo.txt | " + quiet, text)
        self.assertIn("agent_worktree.txt | " + wline, text)
        self.assertIn("agent_ideas.txt | " + IDEAS[1], text)
        self.assertIn("backup: %s (3 lines)" % backups[0], self.lines(out))

    def test_c9_a_failing_step_stops_and_says_what_went(self):
        self.set_file("agent_ideas.txt", IDEAS[:2] + [IDEAS[1]])
        self.write("a.md")
        self.commit_all()
        self.dry()
        open(os.path.join(self.gitdir, "index.lock"), "w").close()
        res = self.yes("all")
        self.assertEqual(res.returncode, 1)
        self.assertIn("FAILED at D1", res.stdout + res.stderr)
        self.assertTrue(os.path.exists(self.p("a.md")))
        self.assertEqual(self.read("agent_ideas.txt").splitlines(), IDEAS[:2])

    def test_n1_agent_completed_is_never_a_row_and_only_grows(self):
        done = ["2026-10-01 | city-ux | rail | est 30m actual 40m",
                "2026-10-01 | city-ux | rail | est 30m actual 40m",
                "add dark mode | 2026-11-01 10:00 | by main"]
        self.set_file("agent_completed.txt", done)
        self.set_file("agent_todo.txt", [
            "quiet | big | x | est 30m | opened 2026-11-01 08:00 | by main"])
        self.write("mock/city-ux-mock.html")
        self.commit_all()
        out = self.dry()
        for v in self.rows(out).values():
            self.assertNotIn("agent_completed.txt", " ".join(v))
        self.assertOk(self.yes("all"))
        after = self.read("agent_completed.txt").splitlines()
        self.assertEqual(after[:3], done)
        self.assertEqual(len(after), 4)   # the dropped todo line, appended


# ---------------------------------------------------------------- E. edges


class TestEdges(FilesCase):

    def test_e11_no_origin_main_still_lists_files(self):
        r = self.repo
        git(r.dir, "remote", "remove", "origin")
        git(r.dir, "checkout", "-q", "-b", "feat/old")
        self.write("old.txt")
        self.commit_all("old", push=False)
        git(r.dir, "checkout", "-q", "main")
        git(r.dir, "merge", "-q", "--no-ff", "-m", "Merge old", "feat/old")
        self.write("a.md")
        self.commit_all(push=False)
        self.set_file("agent_todo.txt", [
            "old | big | x | est 30m | opened 2026-11-20 08:00 | by main"])
        found = self.by_what(self.dry())
        self.assertIn("a.md", found)
        self.assertNotIn("todo old", found)

    def test_e10_orca_not_answering_lists_no_worktree_lines(self):
        self.repo.set_conf("runtime", "orca")
        self.repo.stub_orca_down()
        gone = os.path.join(self.repo.base, "gone")
        self.set_file("agent_worktree.txt", ["%s | gone | idle | since 2026-11-20 10:00" % gone])
        self.write("a.md")
        self.commit_all()
        out = self.dry()
        found = self.by_what(out)
        self.assertNotIn("worktree line " + gone, found)
        self.assertIn("a.md", found)
        self.assertIn("note: orca not answering: worktree lines not checked",
                      self.lines(out))


# ---------------------------------------------------------------- bounce 1
# reviewer (Opus xhigh) findings 1-9, 11 and the E2E finding, 2026-11-24


class TestBounce1(FilesCase):

    def test_r1_a_name_with_pathspec_magic_removes_only_itself(self):
        self.write(":x.md")
        self.write("x.md")
        self.commit_all()
        out = self.dry()
        self.assertOk(self.yes(self.id_of(out, ":x.md")))
        self.assertFalse(os.path.exists(self.p(":x.md")))
        self.assertTrue(os.path.exists(self.p("x.md")))
        self.assertEqual(git(self.repo.dir, "ls-files", "x.md"), "x.md")

    def test_r2_line_numbers_count_newlines_only(self):
        ideas = ["progress 10%\r100% done | 2026-11-01 10:00 | by main",
                 "add dark mode | 2026-11-01 10:00 | by main",
                 "add dark mode | 2026-11-02 11:00 | by main",
                 "KEEP ME | 2026-11-03 10:00 | by main"]
        with open(self.p("agent_ideas.txt"), "w", newline="") as fh:
            fh.write("".join(l + "\n" for l in ideas))
        out = self.dry()
        rows = [v for i, v in self.rows(out).items() if i.startswith("I")]
        self.assertEqual([v[1] for v in rows], ["agent_ideas.txt line 3"])
        self.assertOk(self.yes("I1"))
        with open(self.p("agent_ideas.txt"), newline="") as fh:
            left = fh.read().split("\n")[:-1]
        self.assertEqual(left, [ideas[0], ideas[1], ideas[3]])

    def test_r3_a_kept_duplicate_is_never_listed(self):
        self.set_file("agent_ideas.txt", [
            "add dark mode | 2026-11-01 10:00 | by main",
            "add dark mode | 2026-11-02 11:00 | by main | kept 2026-11-05"])
        self.assertEqual([i for i in self.rows(self.dry()) if i.startswith("I")], [])

    def test_r4_a_failing_commit_puts_the_files_back(self):
        self.write("a.md")
        self.write("b.md")
        self.commit_all()
        hook = os.path.join(self.gitdir, "hooks", "pre-commit")
        os.makedirs(os.path.dirname(hook), exist_ok=True)
        with open(hook, "w") as fh:
            fh.write("#!/bin/sh\necho lint failed >&2\nexit 1\n")
        os.chmod(hook, 0o755)
        self.dry()
        head = self.head()
        res = self.yes("all")
        self.assertEqual(res.returncode, 1)
        self.assertIn("FAILED at D1", res.stdout + res.stderr)
        self.assertTrue(os.path.exists(self.p("a.md")))
        self.assertTrue(os.path.exists(self.p("b.md")))
        self.assertEqual(self.head(), head)
        self.assertEqual(self.status(), "")

    def test_r5_a_padded_worktree_path_line_goes(self):
        gone = os.path.join(self.repo.base, "gone-a")
        self.set_file("agent_worktree.txt", ["%s  | gone-a | idle | since 2026-11-20 10:00" % gone])
        out = self.dry()
        wid = [i for i in self.rows(out) if i.startswith("W")][0]
        self.assertOk(self.yes(wid))
        self.assertEqual(self.read("agent_worktree.txt").strip(), "")

    def test_r5_every_line_that_goes_is_backed_up(self):
        gone = os.path.join(self.repo.base, "gone-b")
        lines = ["%s | gone-b | idle | since 2026-11-20 10:00" % gone,
                 "%s | gone-b | idle | since 2026-11-21 10:00" % gone]
        self.set_file("agent_worktree.txt", lines)
        self.dry()
        self.assertOk(self.yes("W1,W2"))
        self.assertEqual(self.read("agent_worktree.txt").strip(), "")
        backups = glob.glob(os.path.join(self.gitdir, "agent-cleanup", "*.txt"))
        with open(backups[0]) as fh:
            text = fh.read().splitlines()
        for line in lines:
            self.assertIn("agent_worktree.txt | " + line, text)

    def test_r5_two_rows_of_one_path_both_picked(self):
        gone = os.path.join(self.repo.base, "gone-c")
        self.set_file("agent_worktree.txt", [
            "%s | gone-c | idle | since 2026-11-20 10:00" % gone,
            "%s | gone-c | idle | since 2026-11-21 10:00" % gone])
        self.dry()
        out = self.assertOk(self.yes("all"))
        self.assertEqual(self.read("agent_worktree.txt").strip(), "")
        self.assertEqual(self.lines(out)[-1], "clean-up: removed 2 of 2 picked")

    def test_r6_an_existing_folder_is_never_a_worktree_row(self):
        folder = os.path.join(self.repo.base, "not-a-worktree")
        os.mkdir(folder)
        self.set_file("agent_worktree.txt", ["%s | live-task | working | since 2026-11-20 10:00" % folder])
        self.assertEqual([i for i in self.rows(self.dry()) if i.startswith("W")], [])

    def test_r7_in_use_with_many_candidates(self):
        for n in range(30):
            self.write("old/n%02d.md" % n)
        self.write("bin/tool.sh", 'cat "old/n07.md"\ncat "n21.md"\n')
        self.commit_all()
        out = self.dry()
        kept = self.kept(out)
        self.assertEqual(kept.get("old/n07.md"), "in use: bin/tool.sh")
        self.assertEqual(kept.get("old/n21.md"), "in use: bin/tool.sh")
        self.assertEqual(len([i for i in self.rows(out) if i.startswith("D")]), 28)

    def test_r8_removing_the_last_todo_line_runs_no_sweep(self):
        r = self.repo
        git(r.dir, "checkout", "-q", "-b", "feat/old")
        self.write("old.txt")
        self.commit_all("old", push=False)
        git(r.dir, "push", "-q", "origin", "feat/old")
        git(r.dir, "checkout", "-q", "main")
        git(r.dir, "merge", "-q", "--no-ff", "-m", "Merge old", "feat/old")
        git(r.dir, "push", "-q", "origin", "main")
        self.set_file("agent_todo.txt", [
            "old | big | x | est 30m | opened 2026-11-20 08:00 | by main"])
        out = self.dry()
        self.assertOk(self.yes(self.id_of(out, "todo old")))
        self.assertEqual(self.read("agent_todo.txt").strip(), "")
        self.assertTrue(git(r.dir, "branch", "--list", "feat/old"))
        self.assertTrue(git(self.origin, "branch", "--list", "feat/old"))

    def test_r11_the_idea_what_keeps_the_whole_text(self):
        self.set_file("agent_ideas.txt", [
            "use a | b pipe | 2026-11-01 10:00 | by main",
            "use a | b pipe | 2026-11-02 10:00 | by main"])
        rows = self.rows(self.dry())
        self.assertEqual(rows["I1"][0], "idea: use a / b pipe")

    def test_e2e_per_machine_agent_files_are_never_gone(self):
        self.assertFalse(os.path.exists(self.p("agent_state.txt")))
        self.set_file("agent_ideas.txt", [
            "grep the worktree agent_state.txt for DONE | 2026-11-20 10:00 | by main",
            "agent_monitor.txt keeps old lines | 2026-11-20 10:00 | by main"])
        self.assertEqual([i for i in self.rows(self.dry()) if i.startswith("I")], [])


class TestBounce2(FilesCase):
    """Reviewer re-check N2, N3 (2026-11-24)."""

    def test_n2_rows_sharing_a_path_are_picked_together_or_refused(self):
        gone = os.path.join(self.repo.base, "gone-d")
        lines = ["%s | gone-d | idle | since 2026-11-20 10:00" % gone,
                 "%s | d2 | working | since 2026-11-21 10:00" % gone]
        self.set_file("agent_worktree.txt", lines)
        self.dry()
        before = self.snapshot()
        res = self.yes("W1")
        self.assertEqual(res.returncode, 1)
        self.assertIn("REFUSED", res.stdout + res.stderr)
        self.assertIn("W2", res.stdout + res.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(glob.glob(os.path.join(self.gitdir, "agent-cleanup", "*.txt")))
        self.assertOk(self.yes("W1,W2"))
        self.assertEqual(self.read("agent_worktree.txt").strip(), "")

    def test_n2_todo_rows_sharing_a_name_too(self):
        self.set_file("agent_todo.txt", [
            "quiet | big | x | est 30m | opened 2026-11-01 08:00 | by main",
            "quiet | big | y | est 30m | opened 2026-11-02 08:00 | by main"])
        self.dry()
        res = self.yes("T1")
        self.assertEqual(res.returncode, 1)
        self.assertIn("REFUSED", res.stdout + res.stderr)
        self.assertEqual(len(self.read("agent_todo.txt").strip().splitlines()), 2)

    def test_n3_no_control_character_in_a_printed_row(self):
        with open(self.p("agent_ideas.txt"), "w", newline="") as fh:
            fh.write("progress 10%\r100%\tdone | 2026-11-01 10:00 | by main\n"
                     "progress 10%\r100%\tdone | 2026-11-02 10:00 | by main\n")
        out = self.dry()
        for line in out.split("\n"):
            self.assertFalse(re.search(r"[\x00-\x08\x0b-\x1f\x7f]", line), repr(line))
        self.assertEqual(self.rows(out)["I1"][0], "idea: progress 10% 100% done")


# ---------------------------------------------------------------- conf, skill


class TestConfKeys(unittest.TestCase):
    """settings-configure: cleanup_days and docs_keep are fixed constants."""

    def test_the_constants(self):
        sys.path.insert(0, BIN)
        import agent_conf
        self.assertEqual(agent_conf.CONSTANTS["cleanup_days"], 14)
        self.assertEqual(agent_conf.CONSTANTS["docs_keep"], "")


def read_root(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


class TestSkillAndDocs(unittest.TestCase):

    def test_f_skill(self):
        text = read_root("skills", "clean-up", "SKILL.md")
        head = text.split("---")[1]
        self.assertIn("name: clean-up", head)
        self.assertIn("Main manager only", head)
        body = text.split("---", 2)[2]
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-cleanup.sh --files", body)
        self.assertIn("--yes", body)
        self.assertIn("every row", body)
        self.assertIn("all", body)
        self.assertIn("none", body)
        # 8a7e007: push the branch the main checkout is on, not always main
        self.assertIn("git branch --show-current", body)
        self.assertIn("git push origin <that branch>", body)
        self.assertNotIn("git push origin main", body)
        self.assertRegex(body, r"[Nn]ever .*--yes")

    def test_readme_lists_the_skill(self):
        self.assertIn("clean-up", read_root("README.md"))

    def test_principles_r3_names_clean_up_and_the_no(self):
        # settings-configure: docs_keep is a fixed constant; a product repo keeps its docs by a no
        text = read_root("rules", "files.md")
        r3 = text[text.index("R3. Docs"):text.index("R4. ")]
        self.assertIn("clean-up", r3)
        self.assertIn("real docs stay by a no", r3)


DONE_LINES = [
    "2026-01-02 | old-task | an old finished task | data repo=x work=5",
    "2026-02-03 | dropped-task | dropped long ago | est 10m actual - | dropped: x",
    "2026-11-20 | recent-task | a recent one | data repo=x work=7",
    "2026-11-20 | dup-idea | same text | data repo=x work=7",
    "2026-11-20 | dup-idea | same text | data repo=x work=7",
]


class TestCompletedKept(FilesCase):

    def plant(self):
        self.set_file("agent_completed.txt", DONE_LINES)
        self.write("notes.md")
        self.write("mock/old-task-mock.html")
        self.commit_all()
        self.set_file("agent_ideas.txt", ["same idea", "same idea"])
        self.set_file("agent_todo.txt", [
            "quiet | big | something | est 30m | opened 2026-11-01 08:00 | by main"])
        return self.bytes()

    def bytes(self):
        with open(self.p("agent_completed.txt"), "rb") as fh:
            return fh.read()

    def test_files_table_never_lists_it_and_removal_keeps_it(self):
        before = self.plant()
        out = self.dry()
        self.assertNotIn("agent_completed", out)
        self.assertEqual(self.bytes(), before)
        self.assertOk(self.yes("all"))
        # closing a stale todo may append a dropped line; no line goes
        self.assertTrue(self.bytes().startswith(before))

    def test_sweep_and_housekeep_keep_it(self):
        before = self.plant()
        for script, args in (("agent-cleanup.sh", ["--apply"]),
                             ("agent-cleanup.sh", []),
                             ("agent-housekeep.sh", ["--apply"]),
                             ("agent-housekeep.sh", [])):
            with self.subTest(script=script, args=args):
                self.repo.run(script, *args, env={"AGENT_FAKE_NOW": NOW})
                self.assertEqual(self.bytes(), before)

    def test_line_removal_table_never_names_it(self):
        bin_dir = os.path.join(os.path.dirname(HERE), "bin")
        with open(os.path.join(bin_dir, "agent_cleanfiles.py")) as fh:
            src = fh.read()
        start = src.index("LINE_FILES")
        self.assertNotIn("completed", src[start:src.index("}", start)])


if __name__ == "__main__":
    unittest.main()
