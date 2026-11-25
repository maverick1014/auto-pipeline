"""Failing tests for check-blocks, slice 4: init writes the repo facts.
Written by the task manager before any code.

Rules: requirements/check-blocks.md section 3 (repo facts, fully handled by the agent),
9 C4 and 11 (measure). agent-init.sh writes agent_repo.conf v1 when missing, adds only
missing keys when present, never changes a value that is set.

    # agent_repo.conf: this repo's own facts (check-blocks). Written by agent-init.sh, kept by agents.
    version=1
    core_paths=<globs>      guard_tests=<files>   build_cmd=<cmd>    related_cmd=<cmd>
    full_cmd=<cmd>          test_config=<globs>   data_scripts=<globs>   real_data=<.secrets/file | none>
    build_seconds=<n>       build_mb=<n>          guard_seconds=<n>  (measured; --no-measure skips)
    edge=<text>             (repeated: the generic edges that fit)
    # fix: <subject>        (the last 20 fix commits, candidates the agent turns into edge= lines)

Run: python3 -m unittest tests.test_check_init
"""

import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scripthelp import ScriptCase, ScriptRepo  # noqa: E402

HEADER = ("# agent_repo.conf: this repo's own facts (check-blocks). Written by agent-init.sh, "
          "kept up to date by agents; a human may edit it, never has to.")
GENERIC = ["empty value", "more than one page", "deleted rows", "invalid input",
           "day boundary in local time", "double submit", "large size"]


class InitCase(ScriptCase):
    script = "agent-init.sh"

    def setUp(self):
        super().setUp()
        self.p = self.repo.dir

    def put(self, files):
        for rel, body in files.items():
            full = os.path.join(self.p, rel)
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            with open(full, "w") as fh:
                fh.write(body)

    def git(self, *args, env=None):
        e = dict(os.environ, **(env or {}))
        return subprocess.run(["git", "-C", self.p] + list(args), check=True, capture_output=True,
                              text=True, env=e).stdout

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)

    def init(self, *args, env=None):
        r = self.repo.run("agent-init.sh", *args, env=env)
        self.assertEqual(r.returncode, 0, "exit %d\n%s\n%s" % (r.returncode, r.stdout, r.stderr))
        return r

    def conf_text(self):
        with open(os.path.join(self.p, "agent_repo.conf")) as fh:
            return fh.read()

    def conf(self):
        """key -> value (last wins), plus 'edge' -> list and 'fix' -> list of # fix: subjects."""
        out = {"edge": [], "fix": [], "comments": []}
        for line in self.conf_text().splitlines():
            if line.startswith("# fix: "):
                out["fix"].append(line[len("# fix: "):])
            elif line.startswith("#"):
                out["comments"].append(line)
            elif "=" in line:
                k, v = line.split("=", 1)
                if k == "edge":
                    out["edge"].append(v)
                else:
                    out[k] = v
        return out


class TestFresh(InitCase):

    def test_an_empty_project_gets_version_1(self):
        r = self.init("--no-measure")
        text = self.conf_text()
        self.assertEqual(text.splitlines()[0], HEADER)
        c = self.conf()
        self.assertEqual(c["version"], "1")
        for key in ("core_paths", "guard_tests", "build_cmd", "related_cmd", "full_cmd", "test_config",
                    "data_scripts"):
            self.assertEqual(c[key], "", key)
        self.assertEqual(c["real_data"], "none")
        self.assertEqual(c["edge"], ["empty value", "invalid input"])
        self.assertIn("agent_repo.conf: written (version 1)", r.stdout.splitlines())

    def test_key_order(self):
        self.init("--no-measure")
        keys = [l.split("=", 1)[0] for l in self.conf_text().splitlines() if "=" in l and not l.startswith("#")]
        order = ["version", "core_paths", "guard_tests", "build_cmd", "related_cmd", "full_cmd", "test_config",
                 "data_scripts", "real_data", "working_branch"]
        self.assertEqual([k for k in keys if k in order], order)
        self.assertGreater(keys.index("edge"), keys.index("working_branch"))

    def test_it_is_meant_to_be_committed(self):
        self.init("--no-measure")
        self.assertNotIn("agent_repo.conf", self.repo.read(".gitignore") or "")

    def test_a_second_run_changes_nothing(self):
        self.init("--no-measure")
        before = self.conf_text()
        r = self.init("--no-measure")
        self.assertEqual(self.conf_text(), before)
        self.assertIn("agent_repo.conf: kept", r.stdout.splitlines())


class TestDetect(InitCase):

    def test_python_unittest(self):
        self.put({"bin/tool.py": "x = 1\n", "tests/test_tool.py": "import unittest\nclass T(unittest.TestCase):\n    pass\n"})
        self.commit("py")
        self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["build_cmd"], "python3 -m compileall -q bin tests")
        self.assertEqual(c["related_cmd"], "python3 -m unittest {modules}")
        self.assertEqual(c["full_cmd"], "python3 -m unittest discover -s tests -t .")

    def test_pytest(self):
        self.put({"app/a.py": "x = 1\n", "tests/test_a.py": "import pytest\n\ndef test_a():\n    pass\n",
                  "pytest.ini": "[pytest]\n"})
        self.commit("pytest")
        self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["related_cmd"], "python3 -m pytest {tests}")
        self.assertEqual(c["full_cmd"], "python3 -m pytest")

    def test_jest_with_lint_and_typecheck_scripts(self):
        pkg = {"scripts": {"test": "jest", "lint": "eslint .", "typecheck": "tsc --noEmit"},
               "devDependencies": {"jest": "29"}}
        self.put({"package.json": json.dumps(pkg), "src/a.test.js": "it('a', () => {})\n"})
        self.commit("jest")
        self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["build_cmd"], "npm run lint && npm run typecheck")
        self.assertEqual(c["related_cmd"], "npx jest --maxWorkers=2 {tests}")
        self.assertEqual(c["full_cmd"], "npx jest --maxWorkers=2")

    def test_tsconfig_without_a_typecheck_script(self):
        pkg = {"scripts": {"lint": "eslint ."}, "devDependencies": {"vitest": "1"}}
        self.put({"package.json": json.dumps(pkg), "tsconfig.json": "{}\n"})
        self.commit("vitest")
        self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["build_cmd"], "npm run lint && npx tsc --noEmit")
        self.assertEqual(c["related_cmd"], "npx vitest run {tests}")
        self.assertEqual(c["full_cmd"], "npx vitest run")

    def test_flutter(self):
        self.put({"pubspec.yaml": "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n",
                  "test/a_test.dart": "void main() {}\n"})
        self.commit("flutter")
        self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["build_cmd"], "flutter analyze")
        self.assertEqual(c["related_cmd"], "flutter test -j 2 {tests}")
        self.assertEqual(c["full_cmd"], "flutter test -j 2")

    def test_go(self):
        self.put({"go.mod": "module x\n", "a.go": "package x\n"})
        self.commit("go")
        self.init("--no-measure")
        self.assertEqual(self.conf()["build_cmd"], "go vet ./...")

    def test_guard_tests_are_the_tests_that_read_the_tree(self):
        self.put({"tests/test_layout.py": "import os\nfor d, _, f in os.walk(ROOT):\n    pass\n",
                  "tests/test_files.py": "out = subprocess.run(['git', 'ls-files'])\n",
                  "tests/test_glob.py": "import glob\nglob.glob('**/*.md', recursive=True)\n",
                  "tests/test_plain.py": "def test_a():\n    assert 1\n",
                  "bin/walker.py": "import os\nos.walk('.')\n"})
        self.commit("tests")
        self.init("--no-measure")
        self.assertEqual(self.conf()["guard_tests"],
                         "tests/test_files.py,tests/test_glob.py,tests/test_layout.py")

    def test_core_paths_are_proposed(self):
        self.put({"src/auth/login.js": "x\n", "src/billing/pay.js": "x\n", "app/permissions.py": "x\n",
                  "db/migrations/0001.sql": "x\n", "src/ui/button.js": "x\n", "lib/ledger/post.rb": "x\n"})
        self.commit("tree")
        self.init("--no-measure")
        core = self.conf()["core_paths"].split(",")
        for glob in ("src/auth/", "src/billing/", "app/permissions.py", "db/migrations/", "lib/ledger/"):
            self.assertIn(glob, core)
        self.assertFalse([g for g in core if "ui" in g], core)

    def test_generic_edges_that_fit(self):
        self.put({"src/list.js": "const rows = paginate(q, { limit: 50, offset })\n",
                  "src/model.py": "deleted_at = Column(DateTime)\n",
                  "src/form.jsx": "<form onSubmit={save}>\n",
                  "src/export.py": "def export_csv(rows):\n    pass\n",
                  "src/day.js": "const d = new Date(); tz = 'Asia/Kuala_Lumpur'\n"})
        self.commit("code")
        self.init("--no-measure")
        self.assertEqual(self.conf()["edge"], GENERIC)

    def test_the_last_fix_commits_are_listed(self):
        for msg in ("feat: a page", "fix: refund larger than the invoice", "Bug: empty list crashes",
                    "hotfix: day boundary in KL time", "chore: tidy"):
            self.commit(msg)
        self.init("--no-measure")
        self.assertEqual(self.conf()["fix"], ["hotfix: day boundary in KL time", "Bug: empty list crashes",
                                              "fix: refund larger than the invoice"])

    def test_only_20_fix_commits(self):
        for i in range(25):
            self.commit("fix: bug %d" % i)
        self.init("--no-measure")
        fixes = self.conf()["fix"]
        self.assertEqual(len(fixes), 20)
        self.assertEqual(fixes[0], "fix: bug 24")

    def test_real_data_names_a_read_only_secret(self):
        os.makedirs(os.path.join(self.p, ".secrets"), exist_ok=True)
        self.put({".secrets/db_readonly.env": "URL=x\n", ".secrets/admin.env": "URL=y\n"})
        r = self.init("--no-measure")
        self.assertEqual(self.conf()["real_data"], ".secrets/db_readonly.env")
        self.assertNotIn("URL=", r.stdout + self.conf_text())


class TestExisting(InitCase):

    def test_only_missing_keys_are_added_and_set_values_stay(self):
        self.put({"agent_repo.conf": "level3_paths=src/money/\nbuild_cmd=make check\nedge=a refund\n",
                  "bin/a.py": "x = 1\n", "tests/test_a.py": "import unittest\n"})
        self.commit("old file")
        r = self.init("--no-measure")
        c = self.conf()
        self.assertEqual(c["level3_paths"], "src/money/")
        self.assertEqual(c["build_cmd"], "make check")
        self.assertEqual(c["related_cmd"], "python3 -m unittest {modules}")
        self.assertEqual(c["edge"], ["a refund"])
        lines = r.stdout.splitlines()
        self.assertIn("agent_repo.conf: added related_cmd", lines)
        self.assertNotIn("agent_repo.conf: added build_cmd", lines)
        self.assertNotIn("agent_repo.conf: added edge", lines)
        self.assertTrue(self.conf_text().startswith("level3_paths=src/money/\nbuild_cmd=make check\nedge=a refund\n"))


class TestMeasure(InitCase):

    def py_project(self, guard_sleep=0):
        files = {"bin/a.py": "x = 1\n", "tests/__init__.py": "",
                 "tests/test_tree.py": "import os, time, unittest\n\nclass T(unittest.TestCase):\n"
                                       "    def test_walk(self):\n        time.sleep(%d)\n"
                                       "        list(os.walk('.'))\n" % guard_sleep}
        self.put(files)
        self.commit("py")

    def test_build_and_guard_are_timed(self):
        self.py_project()
        r = self.init()
        c = self.conf()
        self.assertRegex(c["build_seconds"], r"^\d+$")
        self.assertLessEqual(int(c["build_seconds"]), 30)
        self.assertRegex(c["build_mb"], r"^\d+$")
        self.assertRegex(c["guard_seconds"], r"^\d+$")
        self.assertTrue(any(l.startswith("agent_repo.conf: measured build ") for l in r.stdout.splitlines()),
                        r.stdout)

    def test_no_measure_writes_no_numbers(self):
        self.py_project()
        self.init("--no-measure")
        c = self.conf()
        for key in ("build_seconds", "build_mb", "guard_seconds"):
            self.assertNotIn(key, c)

    def test_over_the_cap_is_not_measured(self):
        self.py_project()
        r = self.init(env={"AGENT_FAKE_RAM": "95"})
        self.assertNotIn("build_seconds", self.conf())
        self.assertIn("agent_repo.conf: not measured: RAM 95% over the 80% cap", r.stdout.splitlines())

    def test_a_run_that_hits_the_cap_is_heavy_and_not_retried(self):
        self.py_project(guard_sleep=4)
        r = self.init(env={"AGENT_INIT_MEASURE_CAP_S": "1"})
        lines = self.conf_text().splitlines()
        i = lines.index("guard_seconds=1")
        self.assertEqual(lines[i - 1], "# heavy: hit the 1 s cap")
        self.assertEqual(r.stdout.count("measured guard"), 1)
        r = self.init(env={"AGENT_INIT_MEASURE_CAP_S": "1"})
        self.assertNotIn("measured guard", r.stdout)


class TestSkillAndRule(unittest.TestCase):

    def read(self, *parts):
        with open(os.path.join(os.path.dirname(HERE), *parts)) as fh:
            return fh.read()

    def test_the_init_skill_turns_fix_lines_into_edges(self):
        text = self.read("skills", "init", "SKILL.md")
        self.assertIn("agent_repo.conf", text)
        self.assertIn("# fix:", text)
        self.assertIn("edge=", text)
        self.assertIn("commit", text.lower())

    def test_after_a_bug_fix_the_fixer_adds_an_edge(self):
        for path in (("PRINCIPLES.md",), ("agents", "worker.md"), ("agents", "fast-lane-deputy.md")):
            with self.subTest(path=path):
                text = self.read(*path)
                self.assertIn("which example would have shown it", text)
                self.assertIn("agent-file.sh edge add", text)


if __name__ == "__main__":
    unittest.main()


class TestReviewInit(InitCase):
    """Core review defect 11: init never proposes a core path with a space (it would be refused)."""

    def test_no_core_path_with_a_space(self):
        self.put({"Payment Service/pay.js": "x\n", "src/auth/login.js": "x\n"})
        self.commit("tree")
        self.init("--no-measure")
        core = self.conf()["core_paths"].split(",")
        self.assertIn("src/auth/", core)
        self.assertFalse([c for c in core if " " in c], core)


class TestWorkingBranch(InitCase):
    """Owner 1A 2026-11-25 (section 17): the working branch is the one that does not reach users;
    main when a release branch exists (users install release), else dev. Init asks nothing."""

    def test_no_release_branch_is_dev(self):
        self.init("--no-measure")
        self.assertEqual(self.conf()["working_branch"], "dev")

    def test_a_release_branch_makes_main_the_working_branch(self):
        self.git("branch", "release")
        self.init("--no-measure")
        self.assertEqual(self.conf()["working_branch"], "main")

    def test_an_existing_value_stays(self):
        self.put({"agent_repo.conf": "working_branch=trunk\n"})
        self.git("branch", "release")
        self.init("--no-measure")
        self.assertEqual(self.conf()["working_branch"], "trunk")
