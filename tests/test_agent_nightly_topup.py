"""release-check-loosen (requirements/release-check-loosen.md): after a green FULL run on G, the commits G..tip
that change only text (.md), mock pages (mock/), test files (tests/test_*.py) or the version line need a TOP-UP
(the guard tests + the changed test files), not a second full run. Every example of the requirement is one test."""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import test_agent_nightly as tn  # noqa: E402
from scripthelp import BIN  # noqa: E402
from test_agent_room import x_test  # noqa: E402

if BIN not in sys.path:
    sys.path.insert(0, BIN)
import agent_nightly  # noqa: E402

PASSING = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n"
FAILING = "import unittest\n\n\nclass X(unittest.TestCase):\n    def test_x_red(self):\n        self.fail('red')\n"


@tn.only_own
class TopUpCase(tn.Nightly):
    def setUp(self):
        super().setUp()
        self.mark = os.path.join(self.repo.base, "full.mark")
        self.commit({"agent_repo.conf": "version=1\nfull_cmd=python3 -m unittest discover -s tests -t .\n"
                                        "related_cmd=python3 -m unittest {modules}\nguard_tests=tests/test_a.py\n",
                     # runs only in the full suite: never a guard test, never changed after G
                     "tests/test_mark.py": "import unittest\n\n\nclass M(unittest.TestCase):\n"
                                           "    def test_mark(self):\n        open(%r, 'a').close()\n" % self.mark,
                     "README.md": "# r\n", "rules/time.md": "# t\n", "bin/agent-file.sh": "echo 1\n"}, "setup")

    def commit(self, files, msg, delete=()):
        self.put(files)
        for rel in delete:
            self.git("rm", "-q", rel)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def full_green(self):
        r = self.nightly("--start", "--wait", env=self.env())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.status()
        self.assertEqual((st.get("result"), st.get("kind")), ("green", "full"), st)
        self.assertTrue(os.path.exists(self.mark), "the full suite ran")
        os.remove(self.mark)
        return st["commit"]

    def start(self):
        r = self.nightly("--start", "--wait", env=self.env())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return self.status()

    def release_ok(self):
        return self.nightly("--release-ok", env=self.env())

    def write_status(self, st):
        with open(os.path.join(self.gitdir(), "agent_nightly.json"), "w") as fh:
            json.dump(st, fh)

    def small(self, base, tip="HEAD"):
        return agent_nightly.small_since(self.repo.dir, base, self.git("rev-parse", tip))


@tn.only_own
class TestExamples(TopUpCase):
    def test_text_commit_needs_a_top_up_with_the_guard_tests_only(self):
        g = self.full_green()
        tip = self.commit({"README.md": "# r2\n", "rules/time.md": "# t2\n"}, "text")
        r = self.release_ok()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("a top-up is enough", r.stdout)
        st = self.start()
        self.assertEqual((st["result"], st["kind"], st["commit"], st["full_green"]), ("green", "top-up", tip, g), st)
        self.assertEqual(st["tests"], ["tests/test_a.py"])
        self.assertFalse(os.path.exists(self.mark), "the full suite did not run")
        r = self.release_ok()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("top-up over %s" % g[:7], r.stdout)
        out = self.nightly("--status", env=self.env()).stdout
        self.assertIn("top-up over %s" % g[:7], out)
        self.assertIn("NEEDED: nothing", out)

    def test_a_mock_page_is_a_top_up(self):
        self.full_green()
        self.commit({"mock/a-mock.html": "<p>x</p>\n"}, "mock")
        st = self.start()
        self.assertEqual((st["kind"], st["result"], st["tests"]), ("top-up", "green", ["tests/test_a.py"]), st)

    def test_a_changed_test_file_runs_in_the_top_up_and_a_red_one_refuses_the_publish(self):
        self.full_green()
        self.commit({"tests/test_x.py": x_test("ok") + "# more\n"}, "test change")
        st = self.start()
        self.assertEqual((st["kind"], st["result"], st["tests"]),
                         ("top-up", "green", ["tests/test_a.py", "tests/test_x.py"]), st)
        self.commit({"tests/test_x.py": FAILING}, "red test")
        st = self.start()
        self.assertEqual((st["kind"], st["result"]), ("top-up", "red"), st)
        self.assertTrue(any("test_x_red" in f for f in st["failed"]), st)
        self.assertEqual(self.release_ok().returncode, 1)
        self.assertIn("test_x_red", self.nightly("--failures", env=self.env()).stdout)

    def test_a_code_line_needs_the_full_run_and_the_refusal_names_the_file(self):
        self.full_green()
        self.commit({"bin/agent-file.sh": "echo 2\n"}, "code")
        r = self.release_ok()
        self.assertEqual(r.returncode, 1)
        self.assertIn("the full run is needed", r.stdout)
        self.assertIn("bin/agent-file.sh", r.stdout)
        self.assertIn("bin/agent-file.sh", self.nightly("--status", env=self.env()).stdout)
        st = self.start()
        self.assertEqual((st["kind"], st["result"]), ("full", "green"), st)
        self.assertTrue(os.path.exists(self.mark))

    def test_hooks_conf_helpers_and_plugin_json_beyond_the_version_are_code(self):
        g = self.git("rev-parse", "HEAD")
        cases = {"hooks/hooks.json": "{}\n", "agent_repo.conf": "version=1\nfull_cmd=true\n",
                 "tests/sharedrepo.py": "x = 1\n", ".claude-plugin/plugin.json": '{"name": "q", "version": "0.1.0"}\n'}
        for rel, body in cases.items():
            with self.subTest(rel=rel):
                self.git("reset", "-q", "--hard", g)
                self.commit({rel: body}, "change " + rel)
                ok, why, _ = self.small(g)
                self.assertFalse(ok, rel)
                self.assertIn(rel, why)
        self.git("reset", "-q", "--hard", g)
        self.commit({".claude-plugin/plugin.json": '{"name": "p", "version": "0.2.0"}\n'}, "bump")
        self.assertEqual(self.small(g)[0], True, "the version line alone is small")

    def test_a_second_text_commit_after_a_top_up_is_a_new_top_up_over_the_same_full_run(self):
        g = self.full_green()
        self.commit({"README.md": "# a\n"}, "text 1")
        self.start()
        tip = self.commit({"rules/time.md": "# b\n"}, "text 2")
        st = self.start()
        self.assertEqual((st["kind"], st["result"], st["commit"], st["full_green"]), ("top-up", "green", tip, g), st)
        self.assertEqual(self.release_ok().returncode, 0)

    def test_a_code_commit_after_a_top_up_needs_the_full_run(self):
        self.full_green()
        self.commit({"README.md": "# a\n"}, "text")
        self.start()
        self.commit({"bin/agent-file.sh": "echo 3\n"}, "code")
        self.assertIn("the full run is needed", self.release_ok().stdout)
        st = self.start()
        self.assertEqual(st["kind"], "full", st)
        self.assertTrue(os.path.exists(self.mark))

    def test_a_red_full_run_makes_no_top_up_possible(self):
        self.commit({"tests/test_x.py": FAILING}, "red")
        st = self.start()
        self.assertEqual((st["kind"], st["result"]), ("full", "red"), st)
        self.commit({"README.md": "# a\n"}, "text")
        r = self.release_ok()
        self.assertIn("the full run is needed", r.stdout)
        self.assertIn("red", r.stdout)
        self.assertEqual(self.start()["kind"], "full")

    def test_merges_count_by_the_files_they_bring(self):
        g = self.full_green()
        self.merge("docs", {"docs/a.md": "a\n", "rules/x.md": "x\n"}, "Merge docs (W8)")
        self.assertTrue(self.small(g)[0], self.small(g))
        st = self.start()
        self.assertEqual(st["kind"], "top-up", st)
        self.merge("code", {"bin/x.py": "x = 1\n"}, "Merge code (W8)")
        ok, why, _ = self.small(g)
        self.assertFalse(ok)
        self.assertIn("bin/x.py", why)
        self.assertEqual(self.start()["kind"], "full")

    def test_the_version_only_tip_still_counts_as_its_parent(self):
        self.full_green()
        self.commit({".claude-plugin/plugin.json": '{"name": "p", "version": "0.2.0"}\n'}, "bump 0.2.0")
        r = self.release_ok()
        self.assertEqual(r.returncode, 0, r.stdout)


@tn.only_own
class TestStrict(TopUpCase):
    def test_file_classes(self):
        g = self.git("rev-parse", "HEAD")
        code = {"docs/a.txt": "x\n", "tests/helper.py": "x\n", "tests/sub/test_y.py": PASSING,
                "bin/README": "x\n", "mock.html": "x\n", "a.MD.sh": "x\n"}
        for rel, body in code.items():
            with self.subTest(rel=rel):
                self.git("reset", "-q", "--hard", g)
                self.commit({rel: body}, "add " + rel)
                ok, why, _ = self.small(g)
                self.assertFalse(ok, rel)
                self.assertIn(rel, why)
        self.git("reset", "-q", "--hard", g)
        self.commit({"docs/new.md": "x\n", "mock/x/y.css": "x\n", "tests/test_new.py": PASSING}, "small")
        self.assertEqual(self.small(g), (True, "", ["tests/test_new.py"]))

    def test_a_deleted_test_file_needs_the_full_run(self):
        g = self.git("rev-parse", "HEAD")
        self.commit({}, "drop", delete=["tests/test_x.py"])
        ok, why, _ = self.small(g)
        self.assertFalse(ok)
        self.assertIn("tests/test_x.py", why)
        self.assertIn("deleted", why)

    def test_deleted_or_renamed_code_is_code(self):
        g = self.git("rev-parse", "HEAD")
        self.commit({}, "drop", delete=["bin/agent-file.sh"])
        self.assertFalse(self.small(g)[0])
        self.git("reset", "-q", "--hard", g)
        self.git("mv", "bin/agent-file.sh", "bin/agent-file.md")
        self.git("commit", "-q", "-m", "rename")
        ok, why, _ = self.small(g)
        self.assertFalse(ok)
        self.assertIn("bin/agent-file.sh", why)

    def test_a_mode_change_a_symlink_and_a_submodule_are_code(self):
        g = self.git("rev-parse", "HEAD")
        os.chmod(os.path.join(self.repo.dir, "README.md"), 0o755)
        self.commit({}, "chmod")
        ok, why, _ = self.small(g)
        self.assertFalse(ok)
        self.assertIn("README.md", why)
        self.git("reset", "-q", "--hard", g)
        os.symlink("bin/agent-file.sh", os.path.join(self.repo.dir, "link.md"))
        self.commit({}, "symlink")
        ok, why, _ = self.small(g)
        self.assertFalse(ok)
        self.assertIn("link.md", why)
        self.git("reset", "-q", "--hard", g)
        self.git("update-index", "--add", "--cacheinfo", "160000,%s,sub.md" % g)
        self.git("commit", "-q", "-m", "submodule")
        ok, why, _ = self.small(g)
        self.assertFalse(ok)
        self.assertIn("sub.md", why)

    def test_every_commit_is_walked(self):
        g = self.git("rev-parse", "HEAD")
        self.commit({"bin/agent-file.sh": "echo 9\n"}, "code")
        self.commit({"bin/agent-file.sh": "echo 1\n"}, "revert by hand")
        ok, why, _ = self.small(g)
        self.assertFalse(ok, "a code change in between, even undone, is code")
        self.assertIn("bin/agent-file.sh", why)

    def test_no_option_forces_a_top_up(self):
        self.full_green()
        self.commit({"bin/agent-file.sh": "echo 2\n"}, "code")
        for extra in ("--top-up", "--topup", "--small"):
            r = self.nightly("--start", "--wait", extra, env=self.env())
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotEqual(self.status().get("kind"), "top-up")

    def test_the_same_commit_again_is_the_full_run(self):
        self.full_green()
        self.assertEqual(self.start()["kind"], "full")

    def test_a_forged_or_half_written_record_refuses(self):
        g = self.full_green()
        tip = self.commit({"README.md": "# a\n"}, "text")
        self.start()
        good = self.status()
        self.assertEqual(self.release_ok().returncode, 0)
        other = subprocess.run(["git", "-C", self.repo.dir, "commit-tree", "-m", "orphan",
                                self.git("rev-parse", "HEAD^{tree}")], capture_output=True, text=True).stdout.strip()
        forged = [dict(good, full_green=other),                    # not an ancestor of the tip
                  dict(good, full_green="f" * 40),                 # no such commit
                  dict(good, full_green=""),                       # stands on nothing
                  dict(good, full_green=tip),                      # stands on itself
                  dict(good, tests=[]),                            # the guard tests did not run
                  dict(good, kind="quick"),                        # unknown kind
                  dict(good, commit=tip[:7])]                      # not a full sha
        for st in forged:
            with self.subTest(st=st):
                self.write_status(st)
                r = self.release_ok()
                self.assertEqual(r.returncode, 1, r.stdout)
        with open(os.path.join(self.gitdir(), "agent_nightly.json"), "w") as fh:
            fh.write(json.dumps(good)[:40])
        self.assertEqual(self.release_ok().returncode, 1)
        # a top-up record over a code commit is refused even when it claims green
        self.write_status(good)
        code = self.commit({"bin/agent-file.sh": "echo 5\n"}, "code")
        self.write_status(dict(good, commit=code))
        r = self.release_ok()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("bin/agent-file.sh", r.stdout)
        self.assertEqual(g, good["full_green"])

    def test_the_top_up_waits_for_room(self):
        g = self.full_green()
        self.commit({"README.md": "# a\n"}, "text")
        env = self.env(AGENT_FAKE_RAM="79", AGENT_FAKE_RAM_TOTAL_MB="10000", AGENT_TEST_RUN_WAIT_S="1")
        holder = subprocess.Popen(["sleep", "30"])
        self.addCleanup(holder.kill)
        with open(env["AGENT_RESERVE_FILE"], "w") as fh:
            json.dump({"jobs": [{"pid": holder.pid, "mb": 500, "what": "x", "repo": "y",
                                 "since": "2026-11-25 15:00"}]}, fh)
        r = self.nightly("--start", "--wait", env=env)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("ROOM: no:", r.stdout)
        self.assertEqual((self.status()["commit"], self.status()["kind"]), (g, "full"), "the full record stays")


@tn.only_own
class TestOwnerPoints(TopUpCase):
    """Main manager 2026-11-26: the automatic nightly is always FULL; frontmatter of agents/ and skills/ is code."""

    def test_the_nightly_path_is_full_and_the_release_path_a_top_up(self):
        self.full_green()
        self.commit({"README.md": "# n\n"}, "text")
        r = self.nightly("--start", "--wait", "--nightly", env=self.env())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.status()["kind"], "full", self.status())
        self.assertTrue(os.path.exists(self.mark), "the nightly ran the full suite")
        os.remove(self.mark)
        self.commit({"README.md": "# n2\n"}, "text 2")
        self.assertEqual(self.start()["kind"], "top-up")
        self.assertFalse(os.path.exists(self.mark))

    def test_the_automatic_callers_say_nightly(self):
        with open(os.path.join(BIN, "agent_housekeep.py")) as fh:
            self.assertIn('[script, "--start", "--nightly"]', fh.read())
        with open(os.path.join(BIN, "agent-start.sh")) as fh:
            self.assertIn('agent-nightly.sh" --start --nightly', fh.read())

    def test_frontmatter_of_agents_and_skills_is_code(self):
        self.commit({"agents/x.md": "---\nname: x\nmodel: opus\n---\nbody\n",
                     "skills/y/SKILL.md": "---\nname: y\ndescription: d\n---\nbody\n"}, "agent files")
        g = self.git("rev-parse", "HEAD")
        self.commit({"agents/x.md": "---\nname: x\nmodel: sonnet\n---\nbody\n"}, "model")
        ok, why, _ = self.small(g)
        self.assertFalse(ok)
        self.assertIn("agents/x.md", why)
        self.assertIn("frontmatter", why)
        self.git("reset", "-q", "--hard", g)
        self.commit({"skills/y/SKILL.md": "---\nname: y\ndescription: d\n---\nbody 2\nmore\n"}, "body")
        self.assertEqual(self.small(g)[0], True, self.small(g))
        self.git("reset", "-q", "--hard", g)
        self.commit({"skills/z/SKILL.md": "---\nname: z\n---\nbody\n"}, "new skill")
        ok, why, _ = self.small(g)
        self.assertFalse(ok)
        self.assertIn("skills/z/SKILL.md", why)
        self.git("reset", "-q", "--hard", g)
        self.commit({}, "drop agent", delete=["agents/x.md"])
        self.assertFalse(self.small(g)[0])


@tn.only_own
class TestReviewFixes(TopUpCase):
    """The reviewer's attacks on dd5aa00: A (file names reach a shell), B (too few tests for text), C (--due),
    D (plugin.json beyond the version on the tip), E (a red top-up is no selection miss)."""

    def test_a_names_that_are_not_plain_are_code(self):
        g = self.git("rev-parse", "HEAD")
        made = os.path.join(self.repo.base, "made")
        for rel in ("tests/test_x;true.py", "tests/test_g .py", "tests/test_$(touch %s).py" % "made"):
            with self.subTest(rel=rel):
                self.git("reset", "-q", "--hard", g)
                self.commit({rel: FAILING}, "odd name")
                ok, why, _ = self.small(g)
                self.assertFalse(ok, rel)
                self.assertIn(rel, why)
        self.assertFalse(os.path.exists(made))

    def test_a_odd_names_get_no_green_top_up(self):
        self.full_green()
        self.commit({"tests/test_x;true.py": PASSING, "tests/test_y.py": FAILING}, "attack")
        r = self.release_ok()
        self.assertIn("the full run is needed", r.stdout)
        self.assertIn("tests/test_x;true.py", r.stdout)
        st = self.start()
        self.assertEqual((st["kind"], st["result"]), ("full", "red"), st)

    def test_a_each_path_is_one_shell_word(self):
        scratch = os.path.join(self.repo.base, "sh")
        os.makedirs(scratch)
        for name in ("tests/a;true.py", "tests/a b.py", "tests/$(touch made).py", "tests/a'b.py"):
            with self.subTest(name=name):
                for cmd in ("printf '%s\\n' {tests}", "printf '%s\\n' {modules}", "printf '%s\\n'"):
                    line = agent_nightly.fill_safe(cmd, [name])
                    out = subprocess.run(line, shell=True, cwd=scratch, capture_output=True, text=True).stdout
                    self.assertEqual(len(out.splitlines()), 1, (line, out))
        self.assertEqual(os.listdir(scratch), [], "nothing was executed")

    def test_a_a_planned_file_that_runs_no_test_makes_the_top_up_red(self):
        self.commit({"agent_repo.conf": "version=1\nfull_cmd=python3 -m unittest discover -s tests -t .\n"
                                        "related_cmd=python3 -m unittest {modules}\n"
                                        "guard_tests=tests/test_a.py,tests/test_none.py\n",
                     "tests/test_none.py": "import unittest\n"}, "a guard with no test")
        self.full_green()
        self.commit({"README.md": "# z\n"}, "text")
        st = self.start()
        self.assertEqual((st["kind"], st["result"]), ("top-up", "red"), st)
        self.assertTrue(any("tests/test_none.py" in f for f in st["failed"]), st)

    def test_b_the_related_tests_of_a_text_file_run_in_the_top_up(self):
        self.commit({"docs/guide.md": "a\n",
                     "tests/test_guide.py": "import unittest\n\n\nclass G(unittest.TestCase):\n"
                                            "    def test_short(self):\n"
                                            "        with open('docs/guide.md') as fh:\n"
                                            "            self.assertLessEqual(len(fh.read().splitlines()), 3)\n"},
                    "guide")
        self.full_green()
        self.commit({"docs/guide.md": "a\nb\nc\nd\ne\n"}, "longer guide")
        st = self.start()
        self.assertEqual((st["kind"], st["result"]), ("top-up", "red"), st)
        self.assertIn("tests/test_guide.py", st["tests"])
        self.assertEqual(self.release_ok().returncode, 1)

    def test_b_this_repo_guards_the_rule_structure(self):
        with open(os.path.join(HERE, "..", "agent_repo.conf")) as fh:
            line = [l for l in fh.read().splitlines() if l.startswith("guard_tests=")][-1]
        self.assertIn("tests/test_rules_structure.py", line.split("=", 1)[1].split(","))

    def test_c_due_counts_full_runs_only(self):
        self.nightly("--start", "--wait", env=self.env(AGENT_FAKE_NOW="2026-11-25 10:00"))
        os.remove(self.mark)
        self.commit({"README.md": "# d\n"}, "text")
        late = self.env(AGENT_FAKE_NOW="2026-11-25 22:30")
        self.nightly("--start", "--wait", env=late)
        self.assertEqual(self.status()["kind"], "top-up")
        self.assertEqual(self.nightly("--due", env=self.env(AGENT_FAKE_NOW="2026-11-25 23:00")).returncode, 0,
                         "a top-up after the hour is not that night's full run")

    def test_d_the_tip_counts_as_its_parent_only_for_the_version(self):
        self.full_green()
        g = self.git("rev-parse", "HEAD")
        for body in ('{"name": "q", "version": "0.2.0"}\n', '{"name": "q", "version": "0.1.0"}\n'):
            with self.subTest(body=body):
                self.git("reset", "-q", "--hard", g)
                self.commit({".claude-plugin/plugin.json": body}, "plugin.json")
                self.assertEqual(self.release_ok().returncode, 1)
        self.git("reset", "-q", "--hard", g)
        self.commit({".claude-plugin/plugin.json": '{"name": "p", "version": "0.2.0"}\n'}, "bump")
        self.assertEqual(self.release_ok().returncode, 0)

    def test_e_a_red_top_up_is_no_selection_miss(self):
        self.full_green()
        self.commit({"tests/test_x.py": FAILING}, "red test")
        st = self.start()
        self.assertEqual((st["kind"], st["result"]), ("top-up", "red"), st)
        self.assertEqual(self.misses_file(), [])


if __name__ == "__main__":
    unittest.main()
