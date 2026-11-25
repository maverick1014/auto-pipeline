"""Tests of bin/agent_test_audit.py: after a test merge, every test of before is still there
(kept or moved) or removed with a twin named in the removed-checks table (the test-slim
skill, steps 4-6); and `ids` lists a folder's Python unittest ids, now or at a git ref.

requirements/test-slim.md. One class per feature.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "bin", "agent_test_audit.py")

HEAD = "| Old file::test | Why it is a duplicate | Twin file::test that still checks it |\n|---|---|---|\n"


class AuditCase(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(TOOL):
            self.fail("bin/agent_test_audit.py does not exist yet. Write it.")
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="test_audit_"))
        self.addCleanup(shutil.rmtree, self.base, True)

    def write(self, name, text):
        path = os.path.join(self.base, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
        return path

    def ids(self, name, *ids):
        return self.write(name, "".join(i + "\n" for i in ids))

    def audit(self, before, after, table=None):
        args = ["--before", before, "--after", after] + (["--table", table] if table else [])
        return self.tool(*args)

    def tool(self, *args, cwd=None):
        return subprocess.run([sys.executable, TOOL] + list(args), cwd=cwd or self.base,
                              capture_output=True, text=True, timeout=60)


class TestKeptAndMoved(AuditCase):
    def test_all_kept_is_a_pass(self):
        b = self.ids("b.txt", "test_a.py::TestX.test_one", "test_a.py::TestX.test_two")
        r = self.audit(b, b)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("AUDIT PASS", r.stdout)
        self.assertIn("before 2", r.stdout)
        self.assertIn("kept 2", r.stdout)

    def test_a_test_moved_to_another_file_and_class_is_moved(self):
        b = self.ids("b.txt", "test_task.py::TestOld.test_one", "test_a.py::TestX.test_two")
        a = self.ids("a.txt", "test_module.py::TestFeature.test_one", "test_a.py::TestX.test_two")
        r = self.audit(b, a)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("moved 1", r.stdout)

    def test_two_tests_of_one_name_need_two_after(self):
        b = self.ids("b.txt", "test_a.py::TestX.test_same", "test_b.py::TestY.test_same")
        a = self.ids("a.txt", "test_m.py::TestZ.test_same")
        r = self.audit(b, a)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("test_same", r.stdout)
        self.assertIn("AUDIT FAIL", r.stdout)


class TestRemoved(AuditCase):
    def test_a_lost_test_fails_by_name(self):
        b = self.ids("b.txt", "test_a.py::TestX.test_one", "test_a.py::TestX.test_two")
        a = self.ids("a.txt", "test_a.py::TestX.test_one")
        r = self.audit(b, a)
        self.assertEqual(r.returncode, 1)
        self.assertIn("test_a.py::TestX.test_two", r.stdout)
        self.assertIn("AUDIT FAIL", r.stdout)

    def test_a_removed_test_with_a_living_twin_passes(self):
        b = self.ids("b.txt", "test_a.py::TestX.test_one", "test_a.py::TestX.test_two")
        a = self.ids("a.txt", "test_a.py::TestX.test_one")
        t = self.write("removed.md", HEAD +
                       "| test_a.py::TestX.test_two | same call, same pin as the twin | test_a.py::TestX.test_one |\n")
        r = self.audit(b, a, t)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("removed with twin 1", r.stdout)

    def test_a_twin_that_is_gone_fails(self):
        b = self.ids("b.txt", "test_a.py::TestX.test_one", "test_a.py::TestX.test_two")
        a = self.ids("a.txt", "test_a.py::TestX.test_one")
        t = self.write("removed.md", HEAD +
                       "| test_a.py::TestX.test_two | same pin | test_a.py::TestX.test_gone |\n")
        r = self.audit(b, a, t)
        self.assertEqual(r.returncode, 1)
        self.assertIn("test_a.py::TestX.test_gone", r.stdout)

    def test_a_row_without_a_reason_fails(self):
        b = self.ids("b.txt", "test_a.py::TestX.test_one", "test_a.py::TestX.test_two")
        a = self.ids("a.txt", "test_a.py::TestX.test_one")
        t = self.write("removed.md", HEAD + "| test_a.py::TestX.test_two |  | test_a.py::TestX.test_one |\n")
        self.assertEqual(self.audit(b, a, t).returncode, 1)

    def test_a_row_for_a_test_that_never_was_fails(self):
        b = self.ids("b.txt", "test_a.py::TestX.test_one")
        t = self.write("removed.md", HEAD +
                       "| test_a.py::TestX.test_ghost | same pin as the twin | test_a.py::TestX.test_one |\n")
        r = self.audit(b, b, t)
        self.assertEqual(r.returncode, 1)
        self.assertIn("test_ghost", r.stdout)

    def test_other_tables_in_the_document_are_ignored(self):
        b = self.ids("b.txt", "test_a.py::TestX.test_one")
        t = self.write("plan.md", "| Target file | Module |\n|---|---|\n| test_a.py | a.sh |\n\n" + HEAD)
        self.assertEqual(self.audit(b, b, t).returncode, 0)


SRC = '''import unittest


class Base(unittest.TestCase):
    def helper(self):
        return 1


class TestOne(Base):
    def test_a(self):
        pass

    def test_b(self):
        pass

    def not_a_test(self):
        pass


def test_top_level():
    pass
'''


class TestIds(AuditCase):
    def test_ids_of_a_folder(self):
        self.write("tests/test_m.py", SRC)
        self.write("tests/helper.py", "def test_like():\n    pass\n")
        r = self.tool("ids", "tests")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), ["test_m.py::TestOne.test_a", "test_m.py::TestOne.test_b"])

    def test_ids_at_a_git_ref(self):
        repo = os.path.join(self.base, "repo")
        os.makedirs(repo)
        git = ["git", "-C", repo, "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(["git", "init", "-q", repo], check=True)
        self.write("repo/tests/test_m.py", SRC)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "one"], check=True)
        os.remove(os.path.join(repo, "tests", "test_m.py"))
        r = self.tool("ids", "tests", "--ref", "HEAD", cwd=repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), ["test_m.py::TestOne.test_a", "test_m.py::TestOne.test_b"])

    def test_usage_errors_exit_2(self):
        b = self.ids("b.txt", "x::Y.test_z")
        for args in ([], ["--before", b], ["--after", b], ["ids"], ["--nope"]):
            with self.subTest(args=args):
                self.assertEqual(self.tool(*args).returncode, 2)


if __name__ == "__main__":
    unittest.main()
