"""Failing tests for check-blocks, slice 1: the one table and the blocks the tool
prints from the real diff. Written by the task manager before any code.

Rules: requirements/check-blocks.md, sections 1 (blocks), 5 (acceptance examples,
the owner's use cases first) and 9 C1, C2 (contract).

    bin/agent_blocks.py        the ONE table of blocks and triggers (data + `table`, `names`)
    bin/agent-level.sh check   prints the triggered blocks of the diff (agent_level.py)

Run: python3 -m unittest tests.test_check_blocks
"""

import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scripthelp import ROOT, BIN, ScriptCase  # noqa: E402

# owner 1A 2026-11-25 (requirement section 15): FULL SUITE is gone, MODULE TESTS is the largest per-task check
TOOL = ["DIFF SCAN", "BUILD", "RELATED TESTS", "MODULE TESTS", "GUARD TESTS", "DB CHECK", "DATA CHECK",
        "CORE REVIEW"]
BRIEF = ["DIFF READ", "EXAMPLES TEST", "FLOW CHECK", "UI CHECK", "REAL DATA COUNT"]
FILE_LINE = re.compile(r"^FILE (\S+): (\S+) \((.*)\)$")


def blocks_module():
    sys.path.insert(0, BIN)
    import importlib
    import agent_blocks  # noqa: F401
    return importlib.reload(agent_blocks)


# ---------------------------------------------------------------- C1. the one table


class TestTheTable(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(os.path.join(BIN, "agent_blocks.py")):
            self.fail("bin/agent_blocks.py does not exist yet. Write it.")
        self.mod = blocks_module()

    def test_thirteen_blocks_in_table_order(self):
        self.assertEqual([b["name"] for b in self.mod.BLOCKS], TOOL + BRIEF)

    def test_who_picks_each_block(self):
        picked = {b["name"]: b["picked"] for b in self.mod.BLOCKS}
        self.assertEqual({n for n, p in picked.items() if p == "tool"}, set(TOOL))
        self.assertEqual({n for n, p in picked.items() if p == "brief"}, set(BRIEF))

    def test_every_row_has_trigger_runs_and_sign(self):
        for b in self.mod.BLOCKS:
            with self.subTest(block=b["name"]):
                self.assertEqual(set(b), {"name", "picked", "trigger", "runs", "sign"})
                for key in ("trigger", "runs", "sign"):
                    self.assertTrue(b[key].strip(), key)
                self.assertNotIn("|", b["trigger"] + b["runs"] + b["sign"])

    def test_who_signs(self):
        sign = {b["name"]: b["sign"] for b in self.mod.BLOCKS}
        self.assertEqual(sign["DATA CHECK"], "yes")
        self.assertEqual(sign["MODULE TESTS"], "a dependency, lockfile, CI or test-config change")
        self.assertIn("changes or removes data or columns", sign["DB CHECK"])
        self.assertIn("permission", sign["CORE REVIEW"])
        for name in ("DIFF SCAN", "BUILD", "RELATED TESTS", "GUARD TESTS") + tuple(BRIEF):
            self.assertEqual(sign[name], "no", name)

    def test_triggers_say_what_the_requirement_says(self):
        trig = {b["name"]: b["trigger"] for b in self.mod.BLOCKS}
        self.assertEqual(trig["DIFF SCAN"], "every task")
        self.assertEqual(trig["BUILD"], "code changed")
        self.assertEqual(trig["RELATED TESTS"], "code, text or rule files changed")
        self.assertEqual(trig["GUARD TESTS"], "code or text changed")
        self.assertEqual(trig["DB CHECK"], "a migration or schema file is in the diff")
        self.assertEqual(trig["DATA CHECK"], "a script that changes live data")
        self.assertEqual(trig["MODULE TESTS"],
                         "code used by other modules changed, or dependencies, lockfile, CI or test config changed")
        self.assertNotIn("API change", {b["name"]: b["runs"] for b in self.mod.BLOCKS}["RELATED TESTS"])
        self.assertNotIn("FULL SUITE", [b["name"] for b in self.mod.BLOCKS])
        self.assertIn("core path", trig["CORE REVIEW"])
        self.assertIn("posting rule", trig["CORE REVIEW"])

    def test_the_net_is_outside_tasks(self):
        self.assertEqual([n["name"] for n in self.mod.NET], ["NIGHTLY RUN", "RELEASE SMOKE"])
        for n in self.mod.NET:
            self.assertTrue(n["runs"].strip())

    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(BIN, "agent_blocks.py")] + list(args),
                              capture_output=True, text=True, timeout=30)

    def test_names_cli(self):
        r = self.run_cli("names")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), TOOL + BRIEF)

    def test_table_cli_prints_one_markdown_row_per_block(self):
        r = self.run_cli("table")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "| Block | Picked | Trigger | What runs | Owner signs |")
        self.assertRegex(lines[1], r"^\|(-+\|){5}$")
        self.assertEqual(len(lines), 2 + 13)
        for b, line in zip(self.mod.BLOCKS, lines[2:]):
            self.assertEqual(line, "| %s | %s | %s | %s | %s |"
                             % (b["name"], b["picked"], b["trigger"], b["runs"], b["sign"]))

    def test_usage_error(self):
        r = self.run_cli("nope")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)


# ---------------------------------------------------------------- C2. the tool


class BlocksCase(ScriptCase):
    script = "agent-level.sh"

    def git(self, *args, cwd=None):
        return subprocess.run(["git", "-C", cwd or self.repo.dir] + list(args), check=True,
                              capture_output=True, text=True).stdout.strip()

    def put(self, files, cwd=None):
        for rel, body in files.items():
            full = os.path.join(cwd or self.repo.dir, rel)
            if body is None:
                os.remove(full)
                continue
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            with open(full, "wb" if isinstance(body, bytes) else "w") as fh:
                fh.write(body)

    def repo_conf(self, text):
        self.put({"agent_repo.conf": text})

    def base(self, files=None, conf=None):
        if conf is not None:
            self.repo_conf(conf)
        self.put(files or {})
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "base")
        self.git("tag", "-f", "base")

    def check(self, *extra):
        r = self.repo.run("agent-level.sh", "check", "--base", "base", *extra)
        self.assertEqual(r.returncode, 0, "exit %d\n%s\n%s" % (r.returncode, r.stdout, r.stderr))
        return r

    def blocks(self, r):
        first = r.stdout.splitlines()[0]
        self.assertTrue(first.startswith("BLOCKS: "), r.stdout)
        return first[len("BLOCKS: "):].split(", ")

    def files(self, r):
        out = {}
        for line in r.stdout.splitlines():
            m = FILE_LINE.match(line)
            if m:
                out[m.group(1)] = (m.group(2), m.group(3))
        return out

    def detail(self, r, block):
        for line in r.stdout.splitlines():
            if line.startswith(block + ": "):
                return line[len(block) + 2:]
        self.fail("no %s line in:\n%s" % (block, r.stdout))

    def not_triggered(self, r):
        for line in r.stdout.splitlines():
            if line.startswith("NOT TRIGGERED: "):
                return line[len("NOT TRIGGERED: "):].split(", ")
        return []

    def run_case(self, before, after, conf=None, extra=()):
        self.base(before, conf)
        self.put(after)
        return self.check(*extra)


CONF_JS = ("guard_tests=tests/tree.test.js\n"
           "build_cmd=npm run lint && npx tsc --noEmit\n"
           "related_cmd=npx jest --maxWorkers=2 {tests}\n"
           "full_cmd=npx jest --maxWorkers=2\n")


class TestOutputShape(BlocksCase):

    def test_no_changes(self):
        self.base({"src/a.js": "x()\n"})
        r = self.check()
        self.assertEqual(r.stdout.splitlines()[0], "BLOCKS: DIFF SCAN")
        self.assertIn("no changes", r.stdout.splitlines())

    def test_line_order(self):
        r = self.run_case({"src/a.js": "x()\n", "tests/a.test.js": "require('../src/a')\n"},
                          {"src/a.js": "y()\n"}, conf=CONF_JS)
        lines = r.stdout.splitlines()
        self.assertTrue(lines[0].startswith("BLOCKS: "))
        self.assertTrue(lines[1].startswith("FILE "), r.stdout)
        tags = [l.split(":")[0] for l in lines]
        self.assertLess(tags.index("DIFF SCAN"), tags.index("NOT TRIGGERED"))
        self.assertEqual(lines[-1], "BRIEF PICKS: DIFF READ, EXAMPLES TEST, FLOW CHECK, UI CHECK, "
                                    "REAL DATA COUNT (dispatch picks them from the brief)")

    def test_blocks_are_in_table_order_and_brief_blocks_never_in_it(self):
        r = self.run_case({"src/a.js": "x()\n", "tests/a.test.js": "require('../src/a')\n",
                           "package-lock.json": '{"a": 1}\n'},
                          {"src/a.js": "y()\n", "package-lock.json": '{"a": 2}\n'}, conf=CONF_JS)
        got = self.blocks(r)
        names = [b for b in got if b != "OWNER SIGN"]
        self.assertEqual(names, [b for b in TOOL if b in names])
        for b in BRIEF:
            self.assertNotIn(b, got)
        self.assertEqual(got[-1], "OWNER SIGN")

    def test_not_triggered_lists_the_rest_of_the_tool_blocks(self):
        r = self.run_case({"docs/a.md": "x\n"}, {"docs/a.md": "y\n"})
        got, rest = self.blocks(r), self.not_triggered(r)
        self.assertEqual(sorted(got + rest), sorted(TOOL))

    def test_declared_is_ignored_with_one_note(self):
        self.base({"src/a.js": "x()\n"})
        self.put({"src/a.js": "y()\n"})
        r = self.check("--declared", "A")
        self.assertIn("note: --declared is ignored: levels are gone, blocks only", r.stdout.splitlines())
        self.assertNotIn("RAISE", r.stdout)
        self.assertNotIn("REQUIRED TYPE", r.stdout)

    def test_no_level_words_in_the_output(self):
        r = self.run_case({"src/a.js": "x()\n", "src/b.css": "a{}\n"},
                          {"src/a.js": "y()\n", "src/b.css": "b{}\n"})
        for word in ("REQUIRED TYPE", "PART ", "RAISE", "built-in D", "level"):
            self.assertNotIn(word, r.stdout)

    def test_usage_errors_exit_2(self):
        self.base({"src/a.js": "x\n"})
        for args in (["check"], ["check", "--base"], ["check", "--base", "no-such-ref"],
                     ["lower", "--base", "base"], []):
            with self.subTest(args=args):
                r = self.repo.run("agent-level.sh", *args)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertEqual(r.stdout, "")
                self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)

    def test_json(self):
        r = self.run_case({"src/a.js": "x()\n"}, {"src/a.js": "y()\n"}, extra=("--json",))
        data = json.loads(r.stdout)
        self.assertIn("BUILD", data["blocks"])
        self.assertEqual(data["files"]["src/a.js"]["kinds"], ["code"])
        for key in ("blocks", "sign", "files", "findings", "related", "guard"):
            self.assertIn(key, data)


class TestKinds(BlocksCase):

    def kind(self, before, after, path, conf=None):
        r = self.run_case(before, after, conf)
        got = self.files(r)
        self.assertIn(path, got, r.stdout)
        return got[path]

    def test_code(self):
        self.assertEqual(self.kind({"src/a.py": "x = 1\n"}, {"src/a.py": "x = 2 + y\n"}, "src/a.py")[0], "code")

    def test_text_value_in_code_is_text(self):
        k, why = self.kind({"src/a.js": 'const t = "Hello";\n'}, {"src/a.js": 'const t = "Hello there";\n'},
                           "src/a.js")
        self.assertEqual(k, "text")
        self.assertIn("text change", why)

    def test_comment_only_is_text(self):
        k, why = self.kind({"app/run.py": "# a\nrun()\n"}, {"app/run.py": "# b\nrun()\n"}, "app/run.py")
        self.assertEqual((k, why), ("text", "comment only"))

    def test_docs_are_text(self):
        self.assertEqual(self.kind({"docs/a.md": "x\n"}, {"docs/a.md": "y\n"}, "docs/a.md"), ("text", "text file"))

    def test_rule_files(self):
        for path in ("PRINCIPLES.md", "CLAUDE.md", "AGENTS.md", "skills/merge/SKILL.md", "agents/worker.md",
                     ".claude/skills/x/SKILL.md", ".claude/agents/w.md"):
            with self.subTest(path=path):
                self.tearDown_repo()
                self.assertEqual(self.kind({path: "- a\n"}, {path: "- b\n"}, path)[0], "rule")

    def tearDown_repo(self):
        self.repo.cleanup()
        from scripthelp import ScriptRepo
        self.repo = ScriptRepo()
        self.addCleanup(self.repo.cleanup)

    def test_style(self):
        self.assertEqual(self.kind({"src/a.css": "a{}\n"}, {"src/a.css": "b{}\n"}, "src/a.css"), ("style", "style file"))

    def test_a_colour_value_in_code_is_style(self):
        k, why = self.kind({"src/B.jsx": '<Badge color="#1e88e5" />\n'}, {"src/B.jsx": '<Badge color="#43a047" />\n'},
                           "src/B.jsx")
        self.assertEqual(k, "style")
        self.assertIn("colour change", why)

    def test_a_markup_change_is_code(self):
        k, _ = self.kind({"src/P.jsx": "<Banner text={t} />\n"}, {"src/P.jsx": "{toast(t)}\n"}, "src/P.jsx")
        self.assertEqual(k, "code")

    def test_asset(self):
        self.assertEqual(self.kind({"img/a.png": b"\x89PNG1"}, {"img/a.png": b"\x89PNG2"}, "img/a.png")[0], "asset")

    def test_deps(self):
        for path, before, after in (("package-lock.json", '{"a":1}\n', '{"a":2}\n'),
                                    ("yarn.lock", "a\n", "b\n"),
                                    ("requirements.txt", "flask==2.0\n", "flask==2.1\n"),
                                    ("pubspec.yaml", "a: 1\n", "a: 2\n"),
                                    ("package.json", '{"dependencies": {"a": "1"}}\n',
                                     '{"dependencies": {"a": "2"}}\n')):
            with self.subTest(path=path):
                self.tearDown_repo()
                k, why = self.kind({path: before}, {path: after}, path)
                self.assertEqual(k, "deps")
                self.assertTrue(why.startswith("built-in: "), why)

    def test_package_json_scripts_only_is_code(self):
        k, _ = self.kind({"package.json": '{"scripts": {"a": "x"}}\n'}, {"package.json": '{"scripts": {"a": "y"}}\n'},
                         "package.json")
        self.assertEqual(k, "code")

    def test_ci_and_test_config(self):
        for path in (".github/workflows/ci.yml", ".gitlab-ci.yml", "jest.config.js", "pytest.ini", "tox.ini",
                     "conftest.py", "vitest.config.ts", "playwright.config.ts", "Jenkinsfile"):
            with self.subTest(path=path):
                self.tearDown_repo()
                self.assertEqual(self.kind({path: "a: 1\n"}, {path: "a: 2\n"}, path)[0], "ci")

    def test_test_config_globs_of_the_repo_file(self):
        k, _ = self.kind({"tests/setup_env.py": "A = 1\n"}, {"tests/setup_env.py": "A = 2\n"}, "tests/setup_env.py",
                         conf="test_config=tests/setup_env.py\n")
        self.assertEqual(k, "ci")

    def test_migration_code_file_is_migration_and_code(self):
        k, _ = self.kind({"db/migrations/0001_a.py": "ops = []\n"},
                         {"db/migrations/0001_a.py": "ops = [AddField('note')]\n"}, "db/migrations/0001_a.py")
        self.assertEqual(k, "migration+code")

    def test_sql_in_a_migration_folder(self):
        k, _ = self.kind({}, {"db/migrations/0002.sql": "ALTER TABLE o ADD COLUMN n text;\n"}, "db/migrations/0002.sql")
        self.assertEqual(set(k.split("+")), {"migration", "schema"})

    def test_schema(self):
        self.assertEqual(self.kind({"prisma/schema.prisma": "model A {}\n"},
                                   {"prisma/schema.prisma": "model A { id Int }\n"}, "prisma/schema.prisma")[0],
                         "schema")

    def test_data_script_by_folder_and_write_sql(self):
        k, _ = self.kind({}, {"scripts/fix_balances.py": 'cur.execute("UPDATE accounts SET balance = 0 WHERE id = 5")\n'},
                         "scripts/fix_balances.py")
        self.assertEqual(k, "data-script")

    def test_a_script_that_only_reads_is_code(self):
        k, _ = self.kind({}, {"scripts/count.py": 'cur.execute("SELECT count(*) FROM accounts")\n'},
                         "scripts/count.py")
        self.assertEqual(k, "code")

    def test_data_scripts_globs_of_the_repo_file(self):
        k, _ = self.kind({}, {"ops/repair.rb": "Account.where(x: 1).update_all(y: 2)\n"}, "ops/repair.rb",
                         conf="data_scripts=ops/**\n")
        self.assertEqual(k, "data-script")

    def test_core_path_mark(self):
        k, _ = self.kind({"src/auth/login.py": "x = 1\n"}, {"src/auth/login.py": "x = 2\n"}, "src/auth/login.py",
                         conf="core_paths=src/auth/**\n")
        self.assertEqual(k, "code+core")

    def test_old_level_paths_still_read_as_core(self):
        k, _ = self.kind({"money/calc.py": "x = 1\n"}, {"money/calc.py": "x = 2\n"}, "money/calc.py",
                         conf="level3_paths=money/\n")
        self.assertEqual(k, "code+core")


class TestTriggers(BlocksCase):

    def test_build_on_code_and_style_only(self):
        for files, build in ((({"src/a.js": "x()\n"}, {"src/a.js": "y()\n"}), True),
                             (({"src/a.css": "a{}\n"}, {"src/a.css": "b{}\n"}), True),
                             (({"docs/a.md": "x\n"}, {"docs/a.md": "y\n"}), False),
                             (({"src/a.js": 'f("Hello")\n'}, {"src/a.js": 'f("Hello you")\n'}), False),
                             (({"img/a.png": b"\x89PNG1"}, {"img/a.png": b"\x89PNG2"}), False)):
            with self.subTest(files=files[1]):
                TestKinds.tearDown_repo(self)
                r = self.run_case(*files)
                self.assertEqual("BUILD" in self.blocks(r), build, r.stdout)

    def test_build_line_names_the_files_and_the_command(self):
        r = self.run_case({"src/a.js": "x()\n"}, {"src/a.js": "y()\n"}, conf=CONF_JS)
        self.assertEqual(self.detail(r, "BUILD"), "src/a.js | run: npm run lint && npx tsc --noEmit")

    def test_build_line_without_a_build_cmd(self):
        r = self.run_case({"src/a.js": "x()\n"}, {"src/a.js": "y()\n"})
        self.assertIn("no build_cmd in agent_repo.conf", self.detail(r, "BUILD"))

    def test_guard_on_code_text_or_rule_when_listed(self):
        r = self.run_case({"docs/a.md": "x\n", "tests/tree.test.js": "walk()\n"}, {"docs/a.md": "y\n"}, conf=CONF_JS)
        self.assertIn("GUARD TESTS", self.blocks(r))
        self.assertEqual(self.detail(r, "GUARD TESTS"),
                         "tests/tree.test.js | run: npx jest --maxWorkers=2 tests/tree.test.js")

    def test_guard_none_listed_is_said_and_not_triggered(self):
        r = self.run_case({"src/a.js": "x()\n"}, {"src/a.js": "y()\n"})
        self.assertNotIn("GUARD TESTS", self.blocks(r))
        self.assertIn("GUARD TESTS: none listed in agent_repo.conf (init writes them)", r.stdout.splitlines())

    def test_an_asset_alone_runs_only_the_diff_scan(self):
        r = self.run_case({"img/a.png": b"\x89PNG1"}, {"img/a.png": b"\x89PNG2"}, conf=CONF_JS)
        self.assertEqual(self.blocks(r), ["DIFF SCAN"])

    def test_ci_config_is_every_module_and_owner_sign(self):
        r = self.run_case({".github/workflows/ci.yml": "a: 1\n"}, {".github/workflows/ci.yml": "a: 2\n"}, conf=CONF_JS)
        got = self.blocks(r)
        self.assertIn("MODULE TESTS", got)
        self.assertIn("OWNER SIGN", got)
        self.assertEqual(self.detail(r, "MODULE TESTS"),
                         "every module (.github/workflows/ci.yml) | run: npx jest --maxWorkers=2")

    def test_every_module_runs_each_group_when_the_repo_has_groups(self):
        conf = CONF_JS + "group.src/a=npm run test:a\ngroup.src/b=npm run test:b\n"
        r = self.run_case({"yarn.lock": "a\n"}, {"yarn.lock": "b\n"}, conf=conf)
        self.assertEqual(self.detail(r, "MODULE TESTS"),
                         "every module (yarn.lock) | run: npm run test:a ; npm run test:b")
        self.assertIn("MODULE TESTS (yarn.lock)", self.detail(r, "OWNER SIGN"))

    def test_core_review(self):
        r = self.run_case({"src/auth/login.py": "x = 1\n"}, {"src/auth/login.py": "x = 2\n"},
                          conf="core_paths=src/auth/**\n")
        self.assertIn("CORE REVIEW", self.blocks(r))
        self.assertEqual(self.detail(r, "CORE REVIEW"), "src/auth/login.py")
        self.assertNotIn("OWNER SIGN", self.blocks(r))


class TestBudget(BlocksCase):
    """Kick-off answer 6: a measured BUILD or GUARD TESTS over the 60 s budget is heavy:
    not a task block, it runs in the nightly or pre-release net; unmeasured runs per task."""

    FILES = ({"src/a.js": "x()\n", "tests/tree.test.js": "walk()\n"}, {"src/a.js": "y()\n"})

    def test_budget_is_a_fixed_constant_of_60_seconds(self):
        sys.path.insert(0, BIN)
        import agent_conf
        self.assertEqual(agent_conf.CONSTANTS["check_budget_s"], 60)

    def test_under_the_budget_runs_per_task(self):
        r = self.run_case(*self.FILES, conf=CONF_JS + "build_seconds=59\nguard_seconds=60\n")
        self.assertIn("BUILD", self.blocks(r))
        self.assertIn("GUARD TESTS", self.blocks(r))

    def test_a_heavy_build_goes_to_the_net(self):
        r = self.run_case(*self.FILES, conf=CONF_JS + "build_seconds=95\n")
        self.assertNotIn("BUILD", self.blocks(r))
        self.assertIn("NET: BUILD (heavy, 95 s over the 60 s budget): nightly or pre-release, "
                      "queued like a heavy test", r.stdout.splitlines())
        self.assertNotIn("BUILD", self.not_triggered(r))

    def test_a_heavy_guard_set_goes_to_the_net(self):
        r = self.run_case(*self.FILES, conf=CONF_JS + "guard_seconds=300\n")
        self.assertNotIn("GUARD TESTS", self.blocks(r))
        self.assertIn("NET: GUARD TESTS (heavy, 300 s over the 60 s budget): nightly or pre-release",
                      r.stdout.splitlines())

    def test_unmeasured_runs_per_task(self):
        r = self.run_case(*self.FILES, conf=CONF_JS)
        self.assertIn("BUILD", self.blocks(r))
        self.assertIn("GUARD TESTS", self.blocks(r))

    def test_json_names_the_net(self):
        r = self.run_case(*self.FILES, conf=CONF_JS + "build_seconds=95\n", extra=("--json",))
        self.assertEqual(json.loads(r.stdout)["net"], ["BUILD"])


class TestRelated(BlocksCase):

    def test_tests_that_import_or_name_the_file(self):
        r = self.run_case({"src/orders.js": "x()\n",
                           "tests/orders.test.js": "const o = require('../src/orders')\n",
                           "tests/users.test.js": "const u = require('../src/users')\n"},
                          {"src/orders.js": "y()\n"}, conf=CONF_JS)
        self.assertEqual(self.detail(r, "RELATED TESTS"),
                         "tests/orders.test.js | run: npx jest --maxWorkers=2 tests/orders.test.js")

    def test_a_changed_test_file_is_related_to_itself(self):
        r = self.run_case({"tests/a.test.js": "it('a')\n"}, {"tests/a.test.js": "it('a', f)\n"}, conf=CONF_JS)
        self.assertTrue(self.detail(r, "RELATED TESTS").startswith("tests/a.test.js | run: "))

    def test_modules_slot_for_unittest(self):
        r = self.run_case({"bin/tool.py": "x = 1\n", "tests/test_tool.py": "import tool\n"},
                          {"bin/tool.py": "x = 2\n"}, conf="related_cmd=python3 -m unittest {modules}\n")
        self.assertEqual(self.detail(r, "RELATED TESTS"),
                         "tests/test_tool.py | run: python3 -m unittest tests.test_tool")

    def test_none_found(self):
        r = self.run_case({"src/lonely.js": "x()\n"}, {"src/lonely.js": "y()\n"}, conf=CONF_JS)
        self.assertEqual(self.detail(r, "RELATED TESTS"), "none found | run: -")

    def test_a_short_stem_is_not_a_name(self):
        r = self.run_case({"src/ab.js": "x()\n", "tests/x.test.js": "const ab = 1\n"},
                          {"src/ab.js": "y()\n"}, conf=CONF_JS)
        self.assertEqual(self.detail(r, "RELATED TESTS"), "none found | run: -")

    def test_a_rule_file_takes_the_tests_that_name_the_changed_section(self):
        before = "# P\n\nW3. TDD\n- a\n\nW4. Tests\n- run the touched tests\n\nW5. UI\n- c\n"
        after = before.replace("- run the touched tests", "- run the related tests")
        r = self.run_case({"PRINCIPLES.md": before,
                           "tests/test_w4.py": "assert 'W4' in text\n",
                           "tests/test_w5.py": "assert 'W5' in text\n"},
                          {"PRINCIPLES.md": after}, conf="related_cmd=python3 -m unittest {modules}\n")
        self.assertEqual(self.detail(r, "RELATED TESTS"), "tests/test_w4.py | run: python3 -m unittest tests.test_w4")
        self.assertNotIn("BUILD", self.blocks(r))

    def test_style_only_change_takes_the_components_own_tests(self):
        r = self.run_case({"src/components/Button.css": ".b{color:red}\n",
                           "src/components/Button.test.jsx": "render(<Button />)\n",
                           "src/pages/Home.test.jsx": "render(<Home><Button /></Home>)\n"},
                          {"src/components/Button.css": ".b{color:blue}\n"}, conf=CONF_JS)
        self.assertTrue(self.detail(r, "RELATED TESTS").startswith("src/components/Button.test.jsx | run: "),
                        r.stdout)
        self.assertNotIn("Home.test.jsx", self.detail(r, "RELATED TESTS"))

    def test_a_text_change_takes_the_tests_that_name_the_string(self):
        r = self.run_case({"src/locales/en.json": '{"save": "Save draft"}\n',
                           "tests/labels.test.js": "expect(label).toBe('Save draft')\n",
                           "tests/other.test.js": "expect(1).toBe(1)\n"},
                          {"src/locales/en.json": '{"save": "Save as draft"}\n'}, conf=CONF_JS)
        self.assertEqual(self.files(r)["src/locales/en.json"][0], "text")
        self.assertTrue(self.detail(r, "RELATED TESTS").startswith("tests/labels.test.js | run: "), r.stdout)
        self.assertNotIn("other.test.js", self.detail(r, "RELATED TESTS"))

    def test_integration_groups_of_the_importing_modules(self):
        conf = CONF_JS + ("group.src/orders=npm run test:orders\n"
                          "group.src/users=npm run test:users\n"
                          "group.src/billing=npm run test:billing\n")
        r = self.run_case({"src/lib/validate.js": "module.exports = v\n",
                           "src/orders/form.js": "const v = require('../lib/validate')\n",
                           "src/users/form.js": "import { v } from '../lib/validate'\n",
                           "src/billing/pay.js": "pay()\n",
                           "src/lib/validate.test.js": "require('./validate')\n"},
                          {"src/lib/validate.js": "module.exports = v2\n"}, conf=conf)
        # section 15: the importing modules' groups are MODULE TESTS now, no sign for a code change
        self.assertIn("MODULE TESTS", self.blocks(r))
        self.assertEqual(self.detail(r, "MODULE TESTS"),
                         "src/orders, src/users | run: npm run test:orders ; npm run test:users")
        self.assertNotIn("OWNER SIGN", self.blocks(r))
        self.assertFalse([l for l in r.stdout.splitlines() if l.startswith("group ")], r.stdout)

    def test_no_groups_for_a_style_change(self):
        conf = CONF_JS + "group.src/pages=npm run test:pages\n"
        r = self.run_case({"src/components/Button.css": ".b{}\n",
                           "src/pages/Home.jsx": "import './../components/Button.css'\n"},
                          {"src/components/Button.css": ".c{}\n"}, conf=conf)
        self.assertNotIn("MODULE TESTS", self.blocks(r))


class TestDb(BlocksCase):

    def test_adds_only_no_sign(self):
        r = self.run_case({"db/migrations/0001.sql": "CREATE TABLE o (id int);\n"},
                          {"db/migrations/0002.sql": "ALTER TABLE o ADD COLUMN note text;\n"})
        got = self.blocks(r)
        self.assertIn("DB CHECK", got)
        self.assertNotIn("OWNER SIGN", got)
        self.assertNotIn("MODULE TESTS", got)
        self.assertEqual(self.detail(r, "DB CHECK"), "db/migrations/0002.sql | owner signs: no (adds only)")

    def test_update_or_drop_signs(self):
        for body in ("UPDATE o SET note = '' WHERE note IS NULL;\n", "ALTER TABLE o DROP COLUMN old;\n",
                     "DELETE FROM o WHERE id = 1;\n", "class M: operations = [RemoveField('o', 'x')]\n",
                     "def change\n  remove_column :o, :x\nend\n"):
            with self.subTest(body=body):
                TestKinds.tearDown_repo(self)
                r = self.run_case({"db/migrations/0001.sql": "CREATE TABLE o (id int);\n"},
                                  {"db/migrations/0002.sql": body})
                self.assertIn("OWNER SIGN", self.blocks(r))
                self.assertTrue(self.detail(r, "DB CHECK").startswith("db/migrations/0002.sql | owner signs: yes ("))
                self.assertIn("DB CHECK (db/migrations/0002.sql)", self.detail(r, "OWNER SIGN"))

    def test_a_removed_line_in_a_schema_signs(self):
        r = self.run_case({"prisma/schema.prisma": "model A {\n  id Int\n  old String\n}\n"},
                          {"prisma/schema.prisma": "model A {\n  id Int\n}\n"})
        self.assertIn("OWNER SIGN", self.blocks(r))


class TestDiffScan(BlocksCase):

    def findings(self, r):
        lines = r.stdout.splitlines()
        i = next(k for k, l in enumerate(lines) if l.startswith("DIFF SCAN: "))
        n = int(re.match(r"DIFF SCAN: (\d+) findings?$", lines[i]).group(1))
        got = [l.strip() for l in lines[i + 1:i + 1 + n]]
        for l in lines[i + 1:i + 1 + n]:
            self.assertTrue(l.startswith("  "), l)
        return got

    def test_clean(self):
        r = self.run_case({"src/a.js": "x()\n"}, {"src/a.js": "y()\n"})
        self.assertEqual(self.findings(r), [])

    def test_outside_scope(self):
        r = self.run_case({"src/a.js": "x()\n", "lib/b.js": "x()\n"}, {"src/a.js": "y()\n", "lib/b.js": "y()\n"},
                          extra=("--scope", "src/**"))
        self.assertEqual(self.findings(r), ["outside scope: lib/b.js"])

    def test_no_scope_no_scope_finding(self):
        r = self.run_case({"lib/b.js": "x()\n"}, {"lib/b.js": "y()\n"})
        self.assertNotIn("outside scope", r.stdout)

    def test_deleted_and_removed_tests(self):
        r = self.run_case({"tests/test_a.py": "def test_one():\n    pass\n\ndef test_two():\n    pass\n",
                           "tests/test_b.py": "def test_b():\n    pass\n"},
                          {"tests/test_a.py": "def test_one():\n    pass\n", "tests/test_b.py": None})
        got = self.findings(r)
        self.assertIn("deleted test: tests/test_b.py", got)
        self.assertIn("removed test: tests/test_a.py: test_two", got)

    def test_skipped_tests(self):
        r = self.run_case({"tests/test_a.py": "def test_one():\n    pass\n", "src/a.test.js": "it('a', f)\n"},
                          {"tests/test_a.py": "@unittest.skip('later')\ndef test_one():\n    pass\n",
                           "src/a.test.js": "it.skip('a', f)\n"})
        got = self.findings(r)
        self.assertIn("skipped test: tests/test_a.py:1", got)
        self.assertIn("skipped test: src/a.test.js:1", got)

    def test_secrets_never_print_the_value(self):
        key = "AKIA" + "ABCDEFGHIJKLMNOP"
        r = self.run_case({"src/a.py": "x = 1\n"},
                          {"src/a.py": 'x = 1\naws = "%s"\n' % key, ".env": "TOKEN=abc\n"})
        got = self.findings(r)
        self.assertTrue(any(g.startswith("secret: src/a.py:2 ") for g in got), got)
        self.assertIn("secret file: .env", got)
        self.assertNotIn(key, r.stdout)

    def test_markers_inside_strings_or_comments_are_no_findings(self):
        # the scanner's own pattern table and a test's fixture text are data, not leftovers
        r = self.run_case({"bin/scan.py": "X = 1\n", "tests/test_x.py": "A = 1\n"},
                          {"bin/scan.py": 'X = 1\nMARKERS = ("console.log(", "debugger", "breakpoint()")\n'
                                          "# never leave a breakpoint() in\n",
                           "tests/test_x.py": "A = 1\nFIXTURE = \"it.skip('a', f)\"\n"})
        self.assertEqual(self.findings(r), [])

    def test_debug_leftovers_not_in_tests(self):
        r = self.run_case({"src/a.js": "x()\n", "src/a.test.js": "it('a')\n", "app/b.py": "x = 1\n"},
                          {"src/a.js": "x()\nconsole.log(x)\ndebugger\n", "src/a.test.js": "it('a')\nconsole.log(1)\n",
                           "app/b.py": "x = 1\nbreakpoint()\n"})
        got = self.findings(r)
        self.assertIn("debug leftover: src/a.js:2 console.log(", got)
        self.assertIn("debug leftover: src/a.js:3 debugger", got)
        self.assertIn("debug leftover: app/b.py:2 breakpoint()", got)
        self.assertFalse(any("a.test.js" in g for g in got), got)


# ---------------------------------------------------------------- core review defects 8-11


class TestReviewDbSign(BlocksCase):
    """Defect 8: unsure = sign. A migration signs unless it only adds."""

    def sign_of(self, path, body):
        TestKinds.tearDown_repo(self)
        r = self.run_case({"seed.txt": "x\n"}, {path: body})
        self.assertIn("DB CHECK", self.blocks(r), r.stdout)
        return "OWNER SIGN" in self.blocks(r)

    def test_removals_and_changes_sign(self):
        for path, body in (
                ("db/migrate/20261125_a.js", "await queryInterface.removeColumn('users', 'email')\n"),
                ("db/migrate/20261125_b.js", "await queryInterface.changeColumn('users', 'email', {})\n"),
                ("db/migrate/20261125_c.js", "await queryInterface.bulkDelete('users', null, {})\n"),
                ("database/migrations/2026_11_25_d.php", "Schema::dropIfExists('users');\n"),
                ("priv/repo/migrations/20261125_e.exs", "alter table(:users) do\n  remove :email\nend\n"),
                ("db/migrate/20261125_f.rb", "def change\n  remove_reference :orders, :user\nend\n"),
                ("db/migrate/20261125_g.rb", "def change\n  remove_timestamps :orders\nend\n"),
                ("migrations/20261125_h.js", "db.users.updateMany({}, {$set: {a: 1}})\n"),
                ("Migrations/20261125_DropEmail.cs", "migrationBuilder.DropColumn(name: \"Email\", table: \"Users\");\n")):
            with self.subTest(path=path):
                self.assertTrue(self.sign_of(path, body))

    def test_adds_only_do_not_sign(self):
        for path, body in (
                ("db/migrations/0002.sql", "ALTER TABLE o ADD COLUMN note text;\nCREATE INDEX o_note ON o (note);\n"),
                ("db/migrate/20261125_add_note.rb",
                 "class AddNote < ActiveRecord::Migration[7.0]\n  def change\n    add_column :orders, :note, :string\n"
                 "  end\nend\n"),
                ("app/migrations/0002_note.py",
                 "from django.db import migrations, models\n\nclass Migration(migrations.Migration):\n"
                 "    dependencies = [('app', '0001')]\n    operations = [\n"
                 "        migrations.AddField(model_name='order', name='note', field=models.TextField(null=True)),\n"
                 "    ]\n")):
            with self.subTest(path=path):
                self.assertFalse(self.sign_of(path, body))


class TestReviewDodges(BlocksCase):
    """Defects 9 and 10: dependency lists, a capitalised Migrations folder, data scripts."""

    def kind(self, before, after, path, conf=None):
        TestKinds.tearDown_repo(self)
        r = self.run_case(before, after, conf)
        return self.files(r)[path][0], r

    def test_more_dependency_lists(self):
        for path in ("requirements/prod.txt", "composer.json", "setup.py", "setup.cfg"):
            with self.subTest(path=path):
                k, r = self.kind({path: "a==1\n"}, {path: "a==2\n"}, path)
                self.assertEqual(k, "deps")
                self.assertIn("OWNER SIGN", self.blocks(r))

    def test_a_capitalised_migrations_folder(self):
        k, r = self.kind({"seed.txt": "x\n"}, {"Migrations/20261125_AddNote.cs": "migrationBuilder.AddColumn();\n"},
                         "Migrations/20261125_AddNote.cs")
        self.assertIn("migration", k.split("+"))
        self.assertIn("DB CHECK", self.blocks(r))

    def test_multi_line_sql_in_a_script(self):
        body = 'cur.execute("""\n    UPDATE accounts\n    SET balance = 0\n    WHERE id = 5\n""")\n'
        k, r = self.kind({"seed.txt": "x\n"}, {"scripts/fix_balance.py": body}, "scripts/fix_balance.py")
        self.assertEqual(k, "data-script")
        self.assertIn("OWNER SIGN", self.blocks(r))

    def test_orm_bulk_writes_in_task_folders(self):
        for path, body in (("lib/tasks/fix.rake", "Account.where(x: 1).update_all(balance: 0)\n"),
                           ("tools/clean.js", "await db.collection('a').deleteMany({})\n"),
                           ("app/management/commands/fix.py", "Order.objects.filter(a=1).delete()\n")):
            with self.subTest(path=path):
                k, _ = self.kind({"seed.txt": "x\n"}, {path: body}, path)
                self.assertEqual(k, "data-script")

    def test_a_dict_update_is_no_data_script(self):
        k, _ = self.kind({"seed.txt": "x\n"}, {"scripts/report.py": "rows.update({'a': 1})\nprint(rows)\n"},
                         "scripts/report.py")
        self.assertEqual(k, "code")


class TestReviewCorePaths(BlocksCase):
    """Defect 11: one bad core_paths item must not drop the others (fail closed)."""

    def test_the_good_items_stay(self):
        r = self.run_case({"src/auth/login.py": "x = 1\n"}, {"src/auth/login.py": "x = 2\n"},
                          conf="core_paths=src/auth/,Payment Service/\n")
        self.assertIn("CORE REVIEW", self.blocks(r))
        self.assertIn("Payment Service/", r.stderr)


# ---------------------------------------------------------------- section 5: the owner's use cases


class TestAcceptanceExamples(BlocksCase):
    """Section 5 of the requirement. The trigger table wins: a row's Blocks are a subset
    of what the tool prints (DIFF SCAN and GUARD run whenever they trigger), its Not run
    column is never printed."""

    def assert_case(self, r, need, never):
        got = self.blocks(r)
        for b in need:
            self.assertIn(b, got, r.stdout)
        for b in never:
            self.assertNotIn(b, got, r.stdout)
        for b in BRIEF:
            self.assertNotIn(b, got)

    def test_banner_to_toast_on_one_page(self):
        r = self.run_case({"src/pages/Orders.jsx": "<div>\n  <Banner text={saved} />\n</div>\n",
                           "src/pages/Orders.test.jsx": "render(<Orders />)\n",
                           "src/pages/Users.test.jsx": "render(<Users />)\n"},
                          {"src/pages/Orders.jsx": "<div>\n  {toast(saved)}\n</div>\n"}, conf=CONF_JS)
        self.assert_case(r, ["DIFF SCAN", "BUILD", "RELATED TESTS"], ["MODULE TESTS", "DB CHECK", "OWNER SIGN"])
        self.assertTrue(self.detail(r, "RELATED TESTS").startswith("src/pages/Orders.test.jsx | run: "))

    def test_style_change_of_a_shared_component(self):
        r = self.run_case({"src/components/Card.css": ".card{padding:4px}\n",
                           "src/components/Card.test.jsx": "render(<Card />)\n",
                           "src/pages/Home.test.jsx": "render(<Card />)\n"},
                          {"src/components/Card.css": ".card{padding:8px}\n"}, conf=CONF_JS)
        self.assert_case(r, ["DIFF SCAN", "BUILD", "RELATED TESTS"], ["MODULE TESTS", "OWNER SIGN"])
        self.assertNotIn("Home.test.jsx", self.detail(r, "RELATED TESTS"))

    def test_wording_in_locale_values(self):
        r = self.run_case({"src/locales/en.json": '{"title": "Monthly report"}\n',
                           "tests/tree.test.js": "walk()\n",
                           "tests/report.test.js": "expect(t).toBe('Monthly report')\n"},
                          {"src/locales/en.json": '{"title": "Report of the month"}\n'}, conf=CONF_JS)
        self.assert_case(r, ["DIFF SCAN", "RELATED TESTS", "GUARD TESTS"], ["BUILD", "MODULE TESTS"])

    def test_new_export_column_one_feature(self):
        r = self.run_case({"src/export/csv.js": "cols = ['a']\n",
                           "src/export/csv.test.js": "require('./csv')\n"},
                          {"src/export/csv.js": "cols = ['a', 'b']\nrow.b = total(x)\n"}, conf=CONF_JS)
        self.assert_case(r, ["BUILD", "RELATED TESTS"], ["MODULE TESTS", "OWNER SIGN"])

    def test_a_shared_validator_changes(self):
        conf = CONF_JS + "group.src/orders=npm run test:orders\n"
        r = self.run_case({"src/lib/validator.js": "max = 10\n",
                           "src/lib/validator.test.js": "require('./validator')\n",
                           "src/orders/form.js": "require('../lib/validator')\n"},
                          {"src/lib/validator.js": "max = 20\n"}, conf=conf)
        self.assert_case(r, ["BUILD", "RELATED TESTS", "MODULE TESTS"], ["OWNER SIGN"])
        self.assertEqual(self.detail(r, "MODULE TESTS"), "src/orders | run: npm run test:orders")

    def test_migration_that_only_adds_a_column(self):
        r = self.run_case({}, {"db/migrations/0002.sql": "ALTER TABLE o ADD COLUMN note text;\n"}, conf=CONF_JS)
        self.assert_case(r, ["DB CHECK"], ["OWNER SIGN", "MODULE TESTS"])

    def test_migration_with_update_or_drop(self):
        r = self.run_case({}, {"db/migrations/0003.sql": "UPDATE o SET a = 1;\nALTER TABLE o DROP COLUMN b;\n"},
                          conf=CONF_JS)
        self.assert_case(r, ["DB CHECK", "OWNER SIGN"], [])

    def test_script_that_fixes_live_data(self):
        r = self.run_case({}, {"scripts/fix_totals.py": 'db.execute("UPDATE invoices SET total = 0 WHERE id = 7")\n'},
                          conf=CONF_JS)
        self.assert_case(r, ["DATA CHECK", "OWNER SIGN"], ["RELATED TESTS", "GUARD TESTS"])

    def test_a_new_validation_limit_is_a_brief_pick(self):
        r = self.run_case({"src/a.js": "x()\n"}, {"src/a.js": "y()\n"})
        self.assertIn("REAL DATA COUNT", r.stdout.splitlines()[-1])

    def test_rule_text_in_principles(self):
        before = "# P\n\nR8. Blocks\n- a rule\n"
        r = self.run_case({"PRINCIPLES.md": before, "tests/tree.test.js": "walk()\n",
                           "tests/r8.test.js": "has('R8')\n"},
                          {"PRINCIPLES.md": before.replace("a rule", "a better rule")}, conf=CONF_JS)
        self.assert_case(r, ["RELATED TESTS", "GUARD TESTS"], ["MODULE TESTS", "BUILD"])
        self.assertTrue(self.detail(r, "RELATED TESTS").startswith("tests/r8.test.js | run: "))

    def test_banner_to_toast_stays_a_five_minute_task_on_the_budget(self):
        # kick-off answer 6: BUILD and GUARD TESTS run per task only under the 60 s budget
        files = ({"src/pages/Orders.jsx": "<Banner text={saved} />\n", "tests/tree.test.js": "walk()\n",
                  "src/pages/Orders.test.jsx": "render(<Orders />)\n"},
                 {"src/pages/Orders.jsx": "{toast(saved)}\n"})
        r = self.run_case(*files, conf=CONF_JS + "build_seconds=20\nguard_seconds=30\n")
        self.assert_case(r, ["DIFF SCAN", "BUILD", "RELATED TESTS", "GUARD TESTS"], ["MODULE TESTS"])
        self.assertFalse(any(l.startswith("NET: ") for l in r.stdout.splitlines()), r.stdout)

    def test_dependency_bump(self):
        r = self.run_case({"package.json": '{"dependencies": {"left-pad": "1.0.0"}}\n'},
                          {"package.json": '{"dependencies": {"left-pad": "1.3.0"}}\n'}, conf=CONF_JS)
        self.assert_case(r, ["MODULE TESTS", "OWNER SIGN"], [])
        self.assertIn("MODULE TESTS (package.json)", self.detail(r, "OWNER SIGN"))


if __name__ == "__main__":
    unittest.main()
