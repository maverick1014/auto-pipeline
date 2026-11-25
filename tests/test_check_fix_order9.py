"""Failing tests for check-blocks section 50: FIX ORDER 9 of the main manager (TELL ba09a48b), G9-G15.
Written by the task manager before any fix.

Run: python3 -m unittest tests.test_check_fix_order9
"""

import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import test_check_fix_order3 as fo3  # noqa: E402
import test_check_fix_order6 as fo6  # noqa: E402
import test_check_promote as tp  # noqa: E402
import test_check_results as tcr  # noqa: E402

only_own = fo3.only_own
read = fo3.read
ASK = "ask him one plain question and quote his answer"


# ====================================================================== G9 one task instance, own commits


@only_own
class TestG9(fo6.Gate):
    def test_old_passes_do_not_carry_to_a_new_instance(self):
        self.all_pass_but()
        self.ok("check", "t", "OWNER SIGN", "pass", "--by", "owner", "--owner-quote", "yes sign it")
        self.ok("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.ok("todo", "add", "t", "small", "another change", "10", "--checks", "PR REVIEW")
        tcr.main_launched(self.repo.dir, "t")
        self.git("checkout", "-q", "-b", "other", "base")
        self.commit_push({"app.js": "unrelated()\n"})
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Review", "--evidence", "read it")   # only a new review
        r = self.af("checks", "gate", "t", "--dir", self.repo.dir, "--base", "base")
        self.assertEqual(r.returncode, 1, r.stdout)
        for block in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            with self.subTest(block=block):
                self.assertNotIn("%s: pass" % block, r.stdout)

    def test_a_line_a_minute_before_the_task_opened_is_ignored(self):
        self.passes("DIFF SCAN", "BUILD", "RELATED TESTS")
        line = [l for l in open(os.path.join(self.repo.dir, "agent_todo.txt")) if l.startswith("t | ")][0]
        opened = line.split("opened ")[1][:16]
        t0 = time.mktime(time.strptime(opened, "%Y-%m-%d %H:%M"))
        before = time.strftime("%Y-%m-%d %H:%M", time.localtime(t0 - 60))
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("CHECK t PR REVIEW: pass | by t Review | at %s | ok | %s\n" % (self.head()[:12], before))
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: missing", r.stdout.splitlines())


# ====================================================================== G10 publish words, safe side


class TestG10PublishWords(tp.PromoteCase):
    def add(self, words):
        return self.repo.run("agent-file.sh", "todo", "add", "p", "small", "x", "10", "--target", "production",
                             "--owner-quote", words)

    def test_refusal_or_delay_words_are_refused(self):
        for words in ("do not publish yet, wait for my word", "这个功能先不要发布，等我确认",
                      "after the release we will look at the login page", "ship it without the banner"):
            with self.subTest(words=words):
                r = self.add(words)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("todo add: the owner's words do not clearly say publish now: " + ASK, r.stdout + r.stderr)

    def test_a_plain_publish_is_accepted(self):
        self.assertEqual(self.add("fix the total and publish it").returncode, 0)

    def test_the_list_lives_in_agent_conf(self):
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import agent_conf
        for w in ("not", "wait", "later", "yet", "without", "不", "先", "等"):
            self.assertIn(w, agent_conf.NEGATION_WORDS)


# ====================================================================== G11 the skip word before the block


@only_own
class TestG11Removals(fo6.Gate):
    def test_loose_words_are_refused(self):
        for block, words in (("BUILD", "no need to worry about the build server today"),
                             ("CORE REVIEW", "the review went fine yesterday, ship it without the banner"),
                             ("FLOW CHECK", "the flow on the screen looks good, no need to change it")):
            with self.subTest(block=block):
                r = self.af("todo", "checks", "t", "--remove", block, "--owner-quote", words)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(ASK, r.stdout + r.stderr)

    def test_the_skip_word_right_before_the_name(self):
        for block, words in (("BUILD", "skip the build check"), ("RELATED TESTS", "without the related tests"),
                             ("BUILD", "不用 build")):
            with self.subTest(words=words):
                r = self.af("todo", "checks", "t", "--remove", block, "--owner-quote", words)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


# ====================================================================== G12 real locale files only


class TestG12LocaleFiles(fo3.TestF10StringLiterals):
    test_sql_role_and_url_strings_are_code = None
    test_a_comment_stays_text = None

    def test_a_two_letter_config_stem_is_code(self):
        lines = self.level({"config/db.json": '{"host": "prod-db"}\n'}, {"config/db.json": '{"host": "staging-db"}\n'})
        self.assertTrue(lines and ": text" not in lines[0], lines)

    def test_real_locale_files_stay_text(self):
        for rel in ("src/locales/en.json", "lang/fr.json", "web/zh-CN.json"):
            with self.subTest(file=rel):
                lines = self.level({rel: '{"title": "Report"}\n'}, {rel: '{"title": "Monthly report"}\n'})
                self.assertTrue(lines and ": text" in lines[0], lines)


# ====================================================================== G13, G14 texts and the demo


class TestG13G14(unittest.TestCase):
    def test_g13_the_demo_uses_the_real_verify_and_the_owners_state(self):
        demo = read("tests", "check_blocks_demo.sh")
        self.assertNotIn("echo verified", demo)
        self.assertIn("CLAUDE_CONFIG_DIR", demo)
        self.assertIn("the owner's real state", demo)

    def test_g14_the_deputy_checks_before_force(self):
        dep = read("agents", "merge-deputy.md")
        self.assertIn("git -C <worktree path> log --oneline origin/<target>..HEAD", dep)
        i = dep.index("worktree remove --force")
        self.assertIn("clean", dep[max(0, i - 600):i])


# ====================================================================== G15 the words of two refusals


@only_own
class TestG15Refusal(fo6.Gate):
    def test_an_unclean_merge_says_so(self):
        self.all_pass_but()
        self.git("checkout", "-q", "-b", "trunk", "base")
        self.commit_push({"other.js": "o()\n"})
        self.git("checkout", "-q", "feat")
        self.git("merge", "-q", "--no-ff", "--no-commit", "trunk")
        self.write({"app.js": "y()\nextra()\n"})
        self.git("add", "app.js")
        self.git("commit", "-q", "-m", "Merge trunk into feat")
        self.git("push", "-q", "origin", "feat")
        r = self.af("checks", "gate", "t", "--dir", self.repo.dir, "--base", "origin/trunk")
        self.assertTrue([l for l in r.stdout.splitlines()
                         if l.startswith("PR REVIEW: the merge after the review changed code (")
                         and l.endswith("): review the new head")], r.stdout)


class TestG15Gather(tp.PromoteCase):
    def test_a_missing_worktree_is_named(self):
        self.git("fetch", "-q", "origin")
        self.git("switch", "-q", "-c", "g1", "origin/main")
        self.put("g.txt", "g\n")
        self.git("add", "g.txt")
        self.git("commit", "-q", "-m", "g1")
        self.git("push", "-q", "-u", "origin", "g1")
        self.git("switch", "-q", self.wb)
        self.ready_direct("g1", "g1")
        with open(os.path.join(self.repo.dir, "agent_worktree.txt"), "a") as fh:
            fh.write("/no/such/folder | g1 | final | since 2026-11-25 19:00\n")
        r = self.repo.run("agent-promote.sh", "--task", "g1", "--branch", "g1")
        self.assertIn("gather: skipped /no/such/folder: missing", r.stdout)


if __name__ == "__main__":
    unittest.main()
