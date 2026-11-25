"""Tests of agent-level, one class per feature."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import os  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))


from scripthelp import ROOT, BIN  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402
from scripthelp import ScriptRepo  # noqa: E402


class TestF10StringLiterals(unittest.TestCase):
    def level(self, files_before, files_after):
        d = tempfile.mkdtemp(prefix="f10_")
        self.addCleanup(subprocess.run, ["rm", "-rf", d])
        g = lambda *a: subprocess.run(["git", "-C", d] + list(a), check=True, capture_output=True, text=True).stdout
        g("init", "-q")
        g("config", "user.email", "t@t")
        g("config", "user.name", "t")
        for rel, body in files_before.items():
            os.makedirs(os.path.dirname(os.path.join(d, rel)) or d, exist_ok=True)
            with open(os.path.join(d, rel), "w") as fh:
                fh.write(body)
        g("add", "-A")
        g("commit", "-q", "-m", "base")
        g("tag", "base")
        for rel, body in files_after.items():
            with open(os.path.join(d, rel), "w") as fh:
                fh.write(body)
        r = run_level(self, ["check", "--base", "base"], d, dict(os.environ))
        return [l for l in r.stdout.splitlines() if l.startswith("FILE ")]

    def test_sql_role_and_url_strings_are_code(self):
        cases = [("app.py", 'QUERY = "SELECT * FROM users"\n', 'QUERY = "DELETE FROM users"\n'),
                 ("auth.js", "const ROLE = 'admin';\n", "const ROLE = 'guest';\n"),
                 ("api.py", 'URL = "https://api.example.com/v1"\n', 'URL = "https://evil.example.net/v1"\n')]
        for rel, before, after in cases:
            with self.subTest(file=rel):
                lines = self.level({rel: before}, {rel: after})
                self.assertTrue(lines and lines[0].startswith("FILE %s: code" % rel), lines)

    def test_a_comment_stays_text(self):
        lines = self.level({"app.py": "# list the users\nx = 1\n"}, {"app.py": "# list every user\nx = 1\n"})
        self.assertTrue(lines and lines[0].startswith("FILE app.py: text"), lines)


class TestG7(TestF10StringLiterals):
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


class TestG12LocaleFiles(TestF10StringLiterals):
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


# owner 1A 2026-11-25 (requirement section 15): FULL SUITE is gone, MODULE TESTS is the largest per-task check
# section 21 (owner, 2026-11-25): the PR-style review heads the table and is the main check of every task
TOOL = ["PR REVIEW", "DIFF SCAN", "BUILD", "RELATED TESTS", "MODULE TESTS", "GUARD TESTS", "DB CHECK",
        "DATA CHECK", "CORE REVIEW"]


BRIEF = ["EXAMPLES TEST", "FLOW CHECK", "UI CHECK", "REAL DATA COUNT"]


FILE_LINE = re.compile(r"^FILE (\S+): (\S+) \((.*)\)$")


def blocks_module():
    sys.path.insert(0, BIN)
    import importlib
    import agent_blocks  # noqa: F401
    return importlib.reload(agent_blocks)


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
        r = run_level(self, ["check", "--base", "base"] + list(extra), self.repo.cwd, self.repo._env(None))
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
        for name in ("PR REVIEW", "DIFF SCAN", "BUILD", "RELATED TESTS", "GUARD TESTS") + tuple(BRIEF):
            self.assertEqual(sign[name], "no", name)

    def test_triggers_say_what_the_requirement_says(self):
        trig = {b["name"]: b["trigger"] for b in self.mod.BLOCKS}
        self.assertEqual(trig["DIFF SCAN"], "every task")
        self.assertEqual(trig["PR REVIEW"], "every task")
        runs = {b["name"]: b["runs"] for b in self.mod.BLOCKS}
        for phrase in ("did not build it", "reads the diff against the approved requirement", "nothing else",
                       "edge list", "no check deleted", "no secret", "diff size"):
            self.assertIn(phrase, runs["PR REVIEW"])
        self.assertNotIn("runs the real thing", runs["PR REVIEW"])
        self.assertEqual(trig["FLOW CHECK"], "what a user does changes")
        self.assertTrue(trig["UI CHECK"].startswith("what a user sees changes"))
        for name in ("FLOW CHECK", "UI CHECK"):
            self.assertIn("15-minute time box", runs[name])
            self.assertIn("ideas file", runs[name])
        self.assertIn("LIGHT", runs["RELATED TESTS"])
        self.assertIn("release run or the nightly", runs["RELATED TESTS"])
        self.assertIn("release run or the nightly", runs["MODULE TESTS"])
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
        self.assertEqual([n["name"] for n in self.mod.NET], ["NIGHTLY RUN", "RELEASE RUN", "RELEASE SMOKE"])
        release = {n["name"]: n["runs"] for n in self.mod.NET}["RELEASE RUN"]
        for phrase in ("full suite once on the working branch", "new fixer agent", "never back to the builder",
                       "waits until it is green"):
            self.assertIn(phrase, release)   # owner 1A 2026-11-25 (section 17)
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


class TestOutputShape(BlocksCase):

    def test_no_changes(self):
        self.base({"src/a.js": "x()\n"})
        r = self.check()
        self.assertEqual(r.stdout.splitlines()[0], "BLOCKS: PR REVIEW, DIFF SCAN")
        self.assertIn("no changes", r.stdout.splitlines())

    def test_line_order(self):
        r = self.run_case({"src/a.js": "x()\n", "tests/a.test.js": "require('../src/a')\n"},
                          {"src/a.js": "y()\n"}, conf=CONF_JS)
        lines = r.stdout.splitlines()
        self.assertTrue(lines[0].startswith("BLOCKS: "))
        self.assertTrue(lines[1].startswith("FILE "), r.stdout)
        tags = [l.split(":")[0] for l in lines]
        self.assertLess(tags.index("DIFF SCAN"), tags.index("NOT TRIGGERED"))
        self.assertEqual(lines[-1], "BRIEF PICKS: EXAMPLES TEST, FLOW CHECK, UI CHECK, REAL DATA COUNT "
                                    "(dispatch picks them from the brief)")

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

    def test_a_string_value_in_code_is_code(self):   # check-blocks section 44 F10: a string literal in a code file is code
        k, why = self.kind({"src/a.js": 'const t = "Hello";\n'}, {"src/a.js": 'const t = "Hello there";\n'},
                           "src/a.js")
        self.assertEqual(k, "code")

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
                             # section 44 F10: a string literal in a code file is code, so it is built
                             (({"src/a.js": 'f("Hello")\n'}, {"src/a.js": 'f("Hello you")\n'}), True),
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
        self.assertEqual(self.blocks(r), ["PR REVIEW", "DIFF SCAN"])

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


class TestLightOnly(BlocksCase):
    """Owner principle (sections 19 and 21): a task runs only LIGHT related and module tests (measured); a heavy one
    goes to the release run or the nightly and never blocks a merge. Unmeasured: runs per task."""

    def weights(self, data):
        gd = subprocess.run(["git", "-C", self.repo.dir, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True, check=True).stdout.strip()
        with open(os.path.join(gd, "agent_test_weights.json"), "w") as fh:
            json.dump(data, fh)

    def test_the_pr_review_line(self):
        r = self.run_case({"src/a.js": "x()\n"}, {"src/a.js": "y()\n"})
        self.assertEqual(self.blocks(r)[0], "PR REVIEW")
        self.assertEqual(self.detail(r, "PR REVIEW"),
                         "an agent that did not build it reads the diff against the approved requirement")

    def test_heavy_related_tests_go_to_the_net(self):
        self.weights({"related": "300 s 2048 MB"})
        r = self.run_case({"src/a.js": "x()\n", "tests/a.test.js": "require('../src/a')\n"},
                          {"src/a.js": "y()\n"}, conf=CONF_JS)
        self.assertNotIn("RELATED TESTS", self.blocks(r))
        self.assertIn("NET: RELATED TESTS (heavy, 300 s, 2048 MB): the release run or the nightly",
                      r.stdout.splitlines())

    def test_light_related_tests_run_per_task(self):
        self.weights({"related": "20 s 300 MB"})
        r = self.run_case({"src/a.js": "x()\n", "tests/a.test.js": "require('../src/a')\n"},
                          {"src/a.js": "y()\n"}, conf=CONF_JS)
        self.assertIn("RELATED TESTS", self.blocks(r))

    def test_a_heavy_module_group_goes_to_the_net_and_the_sign_stays(self):
        self.weights({"full": "900 s 3000 MB"})
        r = self.run_case({"yarn.lock": "a\n"}, {"yarn.lock": "b\n"}, conf=CONF_JS)
        self.assertNotIn("MODULE TESTS", self.blocks(r))
        self.assertIn("OWNER SIGN", self.blocks(r))
        self.assertIn("NET: MODULE TESTS (heavy, 900 s, 3000 MB): the release run or the nightly",
                      r.stdout.splitlines())

    def test_the_verify_box_is_a_constant(self):
        sys.path.insert(0, BIN)
        import agent_conf
        self.assertEqual(agent_conf.CONSTANTS["verify_box_min"], 15)


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


class TestReviewDbSignAdds(TestReviewDbSign):
    """Re-check defect H: the owner signs only when a migration changes or removes data or columns.
    Comments are skipped first, down()/downgrade()/Down() bodies are ignored, common add forms are adds."""

    def test_generated_add_migrations_do_not_sign(self):
        for path, body in (
                ("prisma/migrations/20261125_add_email/migration.sql",
                 '-- AlterTable\nALTER TABLE "User" ADD COLUMN "email" TEXT;\n'),
                ("src/migrations/1700000000000-AddEmail.ts",
                 "export class AddEmail1700000000000 implements MigrationInterface {\n"
                 "    public async up(queryRunner: QueryRunner): Promise<void> {\n"
                 '        await queryRunner.query(`ALTER TABLE "user" ADD "email" character varying`);\n'
                 "    }\n"
                 "    public async down(queryRunner: QueryRunner): Promise<void> {\n"
                 '        await queryRunner.query(`ALTER TABLE "user" DROP COLUMN "email"`);\n'
                 "    }\n}\n"),
                ("app/migrations/0003_email.py",
                 "from django.db import migrations, models\n\n\nclass Migration(migrations.Migration):\n\n"
                 "    dependencies = [\n        ('app', '0002'),\n    ]\n\n    operations = [\n"
                 "        migrations.AddField(\n            model_name='user',\n            name='email',\n"
                 "            field=models.EmailField(blank=True, max_length=254),\n        ),\n    ]\n"),
                ("db/migrations/20261125_email.js",
                 "exports.up = function(knex) {\n  return knex.schema.alterTable('users', function(table) {\n"
                 "    table.string('email');\n  });\n};\n\nexports.down = function(knex) {\n"
                 "  return knex.schema.alterTable('users', function(table) {\n    table.dropColumn('email');\n"
                 "  });\n};\n"),
                ("Migrations/20261125_AddEmail.cs",
                 "public partial class AddEmail : Migration\n{\n    protected override void Up(MigrationBuilder migrationBuilder)\n"
                 "    {\n        migrationBuilder.AddColumn<string>(\n            name: \"Email\",\n"
                 "            table: \"Users\",\n            nullable: true);\n    }\n\n"
                 "    protected override void Down(MigrationBuilder migrationBuilder)\n    {\n"
                 "        migrationBuilder.DropColumn(\n            name: \"Email\",\n            table: \"Users\");\n"
                 "    }\n}\n")):
            with self.subTest(path=path):
                self.assertFalse(self.sign_of(path, body))

    def test_a_prisma_schema_field_add_does_not_sign(self):
        TestKinds.tearDown_repo(self)
        r = self.run_case({"prisma/schema.prisma": "model User {\n  id Int @id\n}\n"},
                          {"prisma/schema.prisma": "model User {\n  id Int @id\n  email String?\n}\n"})
        self.assertIn("DB CHECK", self.blocks(r))
        self.assertNotIn("OWNER SIGN", self.blocks(r))

    def test_a_drop_in_up_still_signs(self):
        body = ("exports.up = function(knex) {\n  return knex.schema.alterTable('users', function(table) {\n"
                "    table.dropColumn('email');\n  });\n};\n")
        self.assertTrue(self.sign_of("db/migrations/20261125_drop.js", body))


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


def old_letter(kinds, why):
    """A kind (and its reason) read as the old letter, for the shape tests only."""
    k = set(kinds.split("+")) - {"core"}
    if k & {"deps", "migration", "schema", "ci", "data-script"}:
        return "D"
    if "code" in k:
        return "B" if "component file" in why else "C"
    if "style" in k:
        return "B" if why == "style file" or "new prop value" in why else "A"
    if "asset" in k:
        return "B"
    return "A"


def core_paths_of(stdout):
    """The files the tool marks as core (kind ends with +core)."""
    out = set()
    for line in stdout.splitlines():
        m = FILE_LINE.match(line)
        if m and "core" in m.group(2).split("+"):
            out.add(m.group(1))
    return out


class LevelCase(ScriptCase):
    script = "agent-level.sh"

    def git(self, *args, cwd=None):
        return subprocess.run(["git", "-C", cwd or self.repo.dir] + list(args), check=True,
                              capture_output=True, text=True).stdout.strip()

    def put(self, files, cwd=None):
        """files: path -> text (str), bytes, or None (delete)."""
        for rel, body in files.items():
            full = os.path.join(cwd or self.repo.dir, rel)
            if body is None:
                os.remove(full)
                continue
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            mode = "wb" if isinstance(body, bytes) else "w"
            with open(full, mode) as fh:
                fh.write(body)

    def commit(self, msg="change", cwd=None):
        self.git("add", "-A", cwd=cwd)
        self.git("commit", "-q", "--allow-empty", "-m", msg, cwd=cwd)

    def base(self, files=None, conf=None):
        """The base commit, tagged "base". conf: agent.conf keys, set before it."""
        for key, value in (conf or {}).items():
            self.repo.set_conf(key, value)
        self.put(files or {})
        self.commit("base")
        self.git("tag", "-f", "base")

    def check(self, *extra, cwd=None, base="base"):
        args = ["check"] + (["--base", base] if base else []) + list(extra)
        return run_level(self, args, cwd or self.repo.cwd, self.repo._env(None))

    def ok(self, *extra, **kw):
        r = self.check(*extra, **kw)
        self.assertEqual(r.returncode, 0, "exit %d\n%s\n%s" % (r.returncode, r.stdout, r.stderr))
        return r

    def tearDown_repo(self):
        # a fresh project for the next subTest
        self.repo.cleanup()
        from scripthelp import ScriptRepo
        self.repo = ScriptRepo()
        self.addCleanup(self.repo.cleanup)

    def required(self, r):
        """The old letters of all files, joined like the old REQUIRED TYPE (A when none)."""
        first = r.stdout.splitlines()[0] if r.stdout else ""
        self.assertTrue(first.startswith("BLOCKS: "), r.stdout + r.stderr)
        return "+".join(sorted({v[0] for v in self.files(r).values()}) or ["A"])

    def files(self, r):
        """path -> (old letter, reason) of the FILE lines."""
        out = {}
        for line in r.stdout.splitlines()[1:]:
            m = FILE_LINE.match(line)
            if m:
                out[m.group(1)] = (old_letter(m.group(2), m.group(3)), m.group(3))
        return out

    def one(self, files_before, files_after, path, conf=None, extra=()):
        """Base, change, check: (required level, level of path, reason of path)."""
        self.base(files_before, conf)
        self.put(files_after)
        r = self.ok(*extra)
        got = self.files(r)
        self.assertIn(path, got, r.stdout)
        return self.required(r), got[path][0], got[path][1]


class TestTheScript(LevelCase):

    def test_both_files_exist_and_the_shell_one_runs(self):
        self.assertTrue(os.access(os.path.join(BIN, "agent-level.sh"), os.X_OK))
        self.assertTrue(os.path.exists(os.path.join(BIN, "agent_level.py")))

    def test_no_changes(self):
        self.base({"src/app.js": 'const a = "x";\n'})
        r = self.ok()
        self.assertEqual(r.stdout.splitlines()[0], "BLOCKS: PR REVIEW, DIFF SCAN")
        self.assertIn("no changes", r.stdout.splitlines())
        self.assertEqual(self.files(r), {})

    def test_one_line_per_file_sorted_after_the_type(self):
        self.base({"b/two.js": 'x("a");\n', "a/one.md": "hello\n", "c/s.css": "a{}\n"})
        self.put({"b/two.js": 'x("b");\n', "a/one.md": "hello you\n", "c/s.css": "b{}\n"})
        r = self.ok()
        lines = r.stdout.splitlines()
        self.assertEqual(self.required(r), "A+B+C")      # section 44 F10: x("a") -> x("b") in a .js file is code
        paths = [FILE_LINE.match(l).group(1) for l in lines[1:] if FILE_LINE.match(l)]
        self.assertEqual(paths, ["a/one.md", "b/two.js", "c/s.css"])

    def test_usage_errors_exit_2_with_one_stderr_line(self):
        self.base({"src/app.js": "x\n"})
        for args in (["check"], ["check", "--base"], ["check", "--base", "no-such-ref"],
                     ["check", "--base", "base", "--declared"],
                     ["lower", "--base", "base"], []):
            with self.subTest(args=args):
                r = self.repo.run("agent-level.sh", *args)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertEqual(r.stdout, "")
                self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)


class TestLevelZero(LevelCase):

    def test_a_string_literal(self):
        need, lvl, why = self.one({"src/app.js": 'const title = "Hello";\n'},
                                  {"src/app.js": 'const title = "Hello there";\n'}, "src/app.js")
        self.assertEqual((need, lvl), ("C", "C"))   # check-blocks section 44 F10: a string literal in a code file is code

    def test_a_single_quoted_string_in_python(self):
        need, lvl, why = self.one({"app/views.py": "def f():\n    flash('Saved')\n"},
                                  {"app/views.py": "def f():\n    flash('Stored, thanks')\n"},
                                  "app/views.py")
        self.assertEqual((need, lvl), ("C", "C"))   # check-blocks section 44 F10: a string literal in a code file is code

    def test_markup_text_between_tags(self):
        need, lvl, why = self.one({"src/Home.jsx": "export const Home = () => (\n  <h1>Welcome</h1>\n);\n"},
                                  {"src/Home.jsx": "export const Home = () => (\n  <h1>Welcome back</h1>\n);\n"},
                                  "src/Home.jsx")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("text change", why)

    def test_a_text_attribute(self):
        need, lvl, why = self.one({"src/Logo.jsx": '<img src={logo} alt="Logo" />\n'},
                                  {"src/Logo.jsx": '<img src={logo} alt="Company logo" />\n'},
                                  "src/Logo.jsx")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("text change", why)

    def test_a_hex_colour_in_a_string(self):
        need, lvl, why = self.one({"src/Badge.jsx": 'const tint = "#1e88e5";\n'},
                                  {"src/Badge.jsx": 'const tint = "#43a047";\n'}, "src/Badge.jsx")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("colour change", why)

    def test_a_colour_attribute_is_a_colour_not_a_prop(self):
        need, lvl, why = self.one({"src/Badge.jsx": '<Badge color="#1e88e5" />\n'},
                                  {"src/Badge.jsx": '<Badge color="#43a047" />\n'}, "src/Badge.jsx")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("colour change", why)

    def test_a_dart_colour(self):
        need, lvl, why = self.one({"lib/badge.dart": "final c = Container(color: Color(0xFF1E88E5));\n"},
                                  {"lib/badge.dart": "final c = Container(color: Color(0xFF43A047));\n"},
                                  "lib/badge.dart")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("colour change", why)

    def test_a_flutter_named_colour(self):
        need, lvl, why = self.one({"lib/badge.dart": "final c = Container(color: Colors.blue);\n"},
                                  {"lib/badge.dart": "final c = Container(color: Colors.green[700]);\n"},
                                  "lib/badge.dart")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("colour change", why)

    def test_rgb_and_rgba(self):
        need, lvl, why = self.one({"src/chart.js": "ctx.fillStyle = 'rgb(30, 136, 229)';\n"},
                                  {"src/chart.js": "ctx.fillStyle = 'rgba(67, 160, 71, 0.8)';\n"},
                                  "src/chart.js")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("colour change", why)

    def test_a_prop_value_already_used_in_the_repo(self):
        need, lvl, why = self.one(
            {"src/Save.jsx": '<Button variant="primary">Save</Button>\n',
             "src/Cancel.jsx": '<Button variant="secondary">Cancel</Button>\n'},
            {"src/Save.jsx": '<Button variant="secondary">Save</Button>\n'}, "src/Save.jsx")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("existing prop value", why)

    def test_a_prop_value_in_braces_already_used(self):
        need, lvl, why = self.one({"src/A.jsx": "<Gap size={3} />\n", "src/B.jsx": "<Gap size={2} />\n"},
                                  {"src/B.jsx": "<Gap size={3} />\n"}, "src/B.jsx")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("existing prop value", why)

    def test_a_line_move_in_markup_asks_for_responsive(self):
        before = "<nav>\n  <Home />\n  <About />\n  <Contact />\n</nav>\n"
        after = "<nav>\n  <About />\n  <Contact />\n  <Home />\n</nav>\n"
        need, lvl, why = self.one({"src/Nav.jsx": before}, {"src/Nav.jsx": after}, "src/Nav.jsx")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("line move", why)
        self.assertIn("manager: check responsive", why)

    def test_a_line_move_in_dart(self):
        before = "Column(children: [\n  title,\n  body,\n]);\n"
        after = "Column(children: [\n  body,\n  title,\n]);\n"
        need, lvl, why = self.one({"lib/page.dart": before}, {"lib/page.dart": after}, "lib/page.dart")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("manager: check responsive", why)

    def test_several_shapes_in_one_file(self):
        before = ('<h1>Welcome</h1>\n' + "".join("<p>line %d</p>\n" % i for i in range(12))
                  + '<Badge color="#1e88e5" />\n')
        after = ('<h1>Welcome back</h1>\n' + "".join("<p>line %d</p>\n" % i for i in range(12))
                 + '<Badge color="#43a047" />\n')
        need, lvl, why = self.one({"src/Home.jsx": before}, {"src/Home.jsx": after}, "src/Home.jsx")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("text change", why)
        self.assertIn("colour change", why)

    def test_a_text_file(self):
        need, lvl, why = self.one({"docs/guide.md": "# Guide\n\nRun it.\n"},
                                  {"docs/guide.md": "# Guide\n\nRun it twice.\n\nMore text.\n"},
                                  "docs/guide.md")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("text file", why)

    def test_a_new_text_file(self):
        need, lvl, why = self.one({"docs/guide.md": "x\n"}, {"docs/faq.txt": "Q and A\n"}, "docs/faq.txt")
        self.assertEqual((need, lvl), ("A", "A"))


class TestLevelOne(LevelCase):

    def test_a_css_change(self):
        need, lvl, why = self.one({"src/card.css": ".card { padding: 4px; }\n"},
                                  {"src/card.css": ".card { padding: 8px; }\n"}, "src/card.css")
        self.assertEqual((need, lvl), ("B", "B"))
        self.assertIn("style file", why)

    def test_a_colour_in_a_css_file_is_still_a_style_file(self):
        need, lvl, why = self.one({"src/card.css": ".card { color: #ffffff; }\n"},
                                  {"src/card.css": ".card { color: #000000; }\n"}, "src/card.css")
        self.assertEqual((need, lvl), ("B", "B"))
        self.assertIn("style file", why)

    def test_a_new_scss_file(self):
        need, lvl, why = self.one({"src/app.js": "x\n"}, {"src/theme.scss": "$primary: #fff;\n"},
                                  "src/theme.scss")
        self.assertEqual((need, lvl), ("B", "B"))
        self.assertIn("style file", why)

    def test_an_asset(self):
        need, lvl, why = self.one({"assets/logo.png": b"\x89PNG\r\n\x1a\n\x00\x01"},
                                  {"assets/logo.png": b"\x89PNG\r\n\x1a\n\x00\x02\x03"},
                                  "assets/logo.png")
        self.assertEqual((need, lvl), ("B", "B"))
        self.assertIn("asset file", why)

    def test_a_prop_value_not_used_anywhere(self):
        need, lvl, why = self.one(
            {"src/Save.jsx": '<Button variant="primary">Save</Button>\n',
             "src/Cancel.jsx": '<Button variant="secondary">Cancel</Button>\n'},
            {"src/Save.jsx": '<Button variant="ghost">Save</Button>\n'}, "src/Save.jsx")
        self.assertEqual((need, lvl), ("B", "B"))
        self.assertIn("new prop value", why)


class TestLevelTwo(LevelCase):

    def code(self, before, after, path="src/app.js"):
        need, lvl, why = self.one({path: before}, {path: after}, path)
        self.assertEqual((need, lvl), ("C", "C"), why)
        return why

    def test_a_logic_change(self):
        self.assertIn("code change", self.code("const n = a + 1;\n", "const n = a + 2;\n"))

    def test_a_string_next_to_new_code(self):
        self.code('const title = "Hello";\n', 'const title = "Hello" + name;\n')

    def test_an_interpolated_string(self):
        self.code("const t = `Hi ${name}`;\n", "const t = `Hi ${user.name}`;\n")

    def test_a_dart_interpolation(self):
        self.code("final t = 'Hi $name';\n", "final t = 'Hi $user';\n", path="lib/t.dart")

    def test_an_f_string(self):
        self.code('t = f"Hi {name}"\n', 't = f"Hi {user}"\n', path="app/t.py")

    def test_an_import_path(self):
        self.code('import x from "./a";\n', 'import x from "./b";\n')

    def test_a_require_path(self):
        self.code('const x = require("./a");\n', 'const x = require("./b");\n')

    def test_an_added_line(self):
        self.code('const a = "x";\n', 'const a = "x";\nconsole.log("y");\n')

    def test_a_removed_line(self):
        self.code('const a = "x";\nconsole.log("y");\n', 'const a = "x";\n')

    def test_a_statement_move_in_python(self):
        self.code("a = load()\nb = save()\nc = done()\n", "b = save()\na = load()\nc = done()\n",
                  path="app/run.py")

    def test_a_comparison_in_a_python_file_is_code(self):
        self.code("ok = a > b and c < d\n", "ok = a > b and c < e\n", path="app/x.py")

    def test_a_new_code_file(self):
        need, lvl, why = self.one({"src/app.js": "x\n"}, {"src/util.js": "export const u = 1;\n"},
                                  "src/util.js")
        self.assertEqual((need, lvl), ("C", "C"))
        self.assertIn("new file", why)

    def test_a_deleted_code_file(self):
        need, lvl, why = self.one({"src/app.js": "x\n", "src/old.js": "y\n"}, {"src/old.js": None},
                                  "src/old.js")
        self.assertEqual((need, lvl), ("C", "C"))
        self.assertIn("deleted file", why)

    def test_package_json_scripts_only(self):
        before = json.dumps({"name": "a", "scripts": {"t": "jest"}, "dependencies": {"x": "1.0.0"}}, indent=2)
        after = json.dumps({"name": "a", "scripts": {"t": "jest -i"}, "dependencies": {"x": "1.0.0"}}, indent=2)
        need, lvl, _ = self.one({"package.json": before + "\n"}, {"package.json": after + "\n"},
                                "package.json")
        self.assertEqual((need, lvl), ("C", "C"))


class TestBuiltInLevelFour(LevelCase):

    def danger(self, path, before, after, kind):
        need, lvl, why = self.one({path: before} if before is not None else {"seed2.txt": "x\n"},
                                  {path: after}, path)
        self.assertEqual((need, lvl), ("D", "D"), why)
        self.assertIn("built-in: %s" % kind, why)

    def test_lockfiles(self):
        for path in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "app/pubspec.lock",
                     "ios/Podfile.lock", "go.sum", "Cargo.lock"):
            with self.subTest(path=path):
                self.danger(path, "a\n", "b\n", "lockfile")
                self.tearDown_repo()

    def test_package_json_dependencies(self):
        for key in ("dependencies", "devDependencies", "peerDependencies", "overrides"):
            with self.subTest(key=key):
                before = json.dumps({"name": "a", key: {"x": "1.0.0"}}, indent=2) + "\n"
                after = json.dumps({"name": "a", key: {"x": "1.1.0"}}, indent=2) + "\n"
                self.danger("package.json", before, after, "package.json deps")
                self.tearDown_repo()

    def test_a_new_package_json(self):
        self.danger("web/package.json", None, json.dumps({"dependencies": {"x": "1"}}) + "\n",
                    "package.json deps")

    def test_pubspec(self):
        self.danger("pubspec.yaml", "name: app\n", "name: app\ndependencies:\n  http: ^1.0.0\n", "pubspec")

    def test_dependency_lists(self):
        for path in ("requirements.txt", "requirements-dev.txt", "go.mod", "Gemfile", "pyproject.toml"):
            with self.subTest(path=path):
                self.danger(path, "a\n", "b\n", "dependency list")
                self.tearDown_repo()

    def test_migrations(self):
        for path in ("db/migrations/001_init.py", "db/migrate/20240101_add.rb",
                     "supabase/migration/x.ts", "alembic/versions/abc.py"):
            with self.subTest(path=path):
                self.danger(path, "a = 1\n", "a = 2\n", "migration")
                self.tearDown_repo()

    def test_schema_files(self):
        for path in ("prisma/schema.prisma", "db/schema.rb", "src/user.schema.json", "db/seed.sql"):
            with self.subTest(path=path):
                self.danger(path, "a\n", "b\n", "schema")
                self.tearDown_repo()


class TestRepoPaths(LevelCase):
    """check-blocks: a core path (core_paths, old level3_paths and level4_paths of the committed
    agent_repo.conf at the main repo root, read from a worktree too) marks the file "+core" and
    triggers CORE REVIEW; the kind stays what the content gives. No file or no key: no core marks."""

    def test_a_core_path_keeps_the_kind_of_its_content(self):
        for key in ("level3_paths", "level4_paths", "core_paths"):
            with self.subTest(key=key):
                need, typ, why = self.one({"src/money/total.js": "a()\n"}, {"src/money/total.js": "b()\n"},
                                          "src/money/total.js", conf={key: "src/money/,lib/ledger/"})
                self.assertEqual((need, typ), ("C", "C"))
                self.assertNotIn("paths", why)
                self.tearDown_repo()

    def test_the_core_mark_names_the_file_only(self):
        self.base({"src/money/total.js": "a()\n", "src/other.js": "a()\n"}, {"level4_paths": "src/money/"})
        self.put({"src/money/total.js": "b()\n", "src/other.js": "b()\n"})
        r = self.ok()
        self.assertEqual(core_paths_of(r.stdout), {"src/money/total.js"})
        self.assertIn("CORE REVIEW: src/money/total.js", r.stdout.splitlines())

    def test_principles_wording_stays_rule_text_on_the_list(self):
        self.base({"PRINCIPLES.md": "- old rule\n"}, {"level3_paths": "PRINCIPLES.md,skills/"})
        self.put({"PRINCIPLES.md": "- new rule words\n"})
        r = self.ok()
        self.assertEqual(self.files(r)["PRINCIPLES.md"][0], "A")
        self.assertEqual(core_paths_of(r.stdout), {"PRINCIPLES.md"})

    def test_no_repo_file_no_core_marks(self):
        self.base({"yarn.lock": "a\n", "skills/a/SKILL.md": "x\n"})
        self.put({"yarn.lock": "b\n", "skills/a/SKILL.md": "y\n"})
        r = self.ok()
        got = self.files(r)
        self.assertEqual(got["yarn.lock"][0], "D")
        self.assertEqual(got["skills/a/SKILL.md"][0], "A")
        self.assertEqual(core_paths_of(r.stdout), set())

    def test_globs_match(self):
        conf = {"level3_paths": "api/,src/*/ledger", "level4_paths": "*.money.ts"}
        self.base({"api/v1/h.py": "a = 1\n", "src/api/h.py": "a = 1\n", "src/a/ledger/x.ts": "a\n",
                   "deep/b.money.ts": "a\n"}, conf)
        self.put({"api/v1/h.py": "a = 2\n", "src/api/h.py": "a = 2\n", "src/a/ledger/x.ts": "b\n",
                  "deep/b.money.ts": "b\n"})
        self.assertEqual(core_paths_of(self.ok().stdout), {"api/v1/h.py", "src/a/ledger/x.ts", "deep/b.money.ts"})

    def test_a_bad_value_is_left_out_and_said(self):
        self.base({"skills/a/SKILL.md": "x\n"}, {"level3_paths": "/etc/,src/", "level4_paths": "skills/"})
        self.put({"skills/a/SKILL.md": "y\n"})
        r = self.ok()
        self.assertEqual(core_paths_of(r.stdout), {"skills/a/SKILL.md"})
        self.assertIn("level3_paths", r.stderr)
        self.assertIn("agent_repo.conf", r.stderr)

    def test_an_old_agent_conf_is_not_read(self):
        self.base({"src/money/total.js": "a = 1\n"})
        self.repo.set_old_conf("level3_paths=src/money/\nlevel4_paths=src/money/\n")
        self.put({"src/money/total.js": "a = 2\n"})
        r = self.ok()
        self.assertEqual(self.files(r)["src/money/total.js"][0], "C")
        self.assertEqual(core_paths_of(r.stdout), set())

    def test_a_worktree_reads_the_main_repos_file(self):
        self.base({"src/money/total.js": "a = 1\n"})
        wt = os.path.join(self.repo.base, "wt_levels")
        self.git("worktree", "add", "-q", "-b", "feat", wt, "base")
        self.repo.set_conf("level4_paths", "src/money/")     # the main copy only, not committed
        self.put({"src/money/total.js": "a = 2\n"}, cwd=wt)
        self.assertEqual(core_paths_of(self.ok(cwd=wt).stdout), {"src/money/total.js"})

    def test_danger_paths_in_configure_is_ignored(self):
        self.base({"src/money/total.js": "a = 1\n"})
        self.repo._settings(lambda o: o.__setitem__("danger_paths", "src/money/"))
        self.put({"src/money/total.js": "a = 2\n"})
        self.assertEqual(core_paths_of(self.ok().stdout), set())


class TestDiffScope(LevelCase):

    def test_a_committed_change_on_the_branch_counts(self):
        self.base({"src/a.js": "a = 1\n"})
        self.put({"src/a.js": "a = 2\n"})
        self.commit()
        self.assertEqual(self.required(self.ok()), "C")

    def test_changes_that_came_in_on_the_base_do_not_count(self):
        self.base({"src/a.md": "hi\n", "yarn.lock": "a\n"})
        main = self.git("symbolic-ref", "--short", "HEAD")
        self.git("checkout", "-q", "-b", "feat")
        self.put({"src/a.md": "hi there\n"})
        self.commit("feat")
        self.git("checkout", "-q", main)
        self.put({"yarn.lock": "b\n"})
        self.commit("main moves on")
        self.git("checkout", "-q", "feat")
        r = self.ok(base=main)
        self.assertEqual(self.required(r), "A", r.stdout)
        self.assertEqual(list(self.files(r)), ["src/a.md"])

    def test_an_untracked_file_counts(self):
        self.base({"src/a.js": "x\n"})
        self.put({"src/new.js": "export const n = 1;\n"})
        got = self.files(self.ok())
        self.assertEqual(got["src/new.js"][0], "C")

    def test_an_ignored_file_does_not_count(self):
        self.base({".gitignore": "build/\n", "src/a.js": "x\n"})
        self.put({"build/out.js": "y\n"})
        r = self.ok()
        self.assertEqual(self.required(r), "A")
        self.assertEqual(self.files(r), {})


class TestTypesPerPart(LevelCase):
    """A kind per file; a component file change is code, its reason "component file" (old letter B)."""

    def test_a_component_file_is_b(self):
        for path, before, after in (
                ("src/Banner.tsx", "export const A = () => <b>hi</b>;\n",
                 "export const A = () => { const n = items.length; return <div>{n}</div>; };\n"),
                ("src/Card.vue", "<template><p>a</p></template>\n", "<template><p v-if=\"ok\">b</p></template>\n"),
                ("src/Nav.jsx", "const a = 1;\n", "const a = compute(1);\n")):
            with self.subTest(path=path):
                need, typ, why = self.one({path: before}, {path: after}, path)
                self.assertEqual((need, typ), ("B", "B"), why)
                self.assertIn("component file", why)
                self.tearDown_repo()

    def test_a_new_and_a_deleted_component_file_are_b(self):
        need, typ, why = self.one({"src/A.tsx": "x\n", "src/Old.tsx": "y\n"},
                                  {"src/New.tsx": "export const N = 1;\n", "src/Old.tsx": None}, "src/New.tsx")
        self.assertEqual((need, typ), ("B", "B"))
        self.assertIn("new component file", why)

    def test_a_component_file_in_a_danger_path_keeps_its_own_type(self):
        # owner 2A 2026-11-25: Danger paths is a hint, never a forced type
        need, typ, why = self.one({"src/money/Total.tsx": "const a = 1;\n"},
                                  {"src/money/Total.tsx": "const a = 2;\n"}, "src/money/Total.tsx",
                                  conf={"level4_paths": "src/money/"})
        self.assertNotEqual(typ, "D", why)

    def test_a_mixed_diff_is_per_part(self):
        self.base({"src/Banner.tsx": "export const A = () => <b>hi</b>;\n", "src/calc.py": "def f(a):\n    return a + 1\n",
                   "docs/a.md": "x\n", "yarn.lock": "a\n"})
        self.put({"src/Banner.tsx": "export const A = () => <div>{n}</div>;\n", "src/calc.py": "def f(a):\n    return a * 2\n",
                  "docs/a.md": "y\n", "yarn.lock": "b\n"})
        r = self.ok()
        self.assertEqual(self.required(r), "A+B+C+D")
        got = self.files(r)
        self.assertEqual({k: v[0] for k, v in got.items()},
                         {"docs/a.md": "A", "src/Banner.tsx": "B", "src/calc.py": "C", "yarn.lock": "D"})

    def test_a_core_path_marks_that_file_only(self):
        self.base({"db/seed.js": "x()\n", "docs/a.md": "x\n"}, {"level4_paths": "db/"})
        self.put({"db/seed.js": "y()\n", "docs/a.md": "y\n"})
        r = self.ok()
        self.assertEqual(self.required(r), "A+C")
        self.assertEqual(core_paths_of(r.stdout), {"db/seed.js"})

    def test_logic_outside_a_danger_path_is_c(self):
        need, typ, why = self.one({"src/money/total.js": "a()\n"}, {"src/money/total.js": "b()\n"},
                                  "src/money/total.js", conf={"level3_paths": ""})
        self.assertEqual((need, typ), ("C", "C"))


CO = "comment only"


WS = "whitespace only"


CODE = ("C", "code change")


COMPONENT = ("B", "component file")   # a UI component file is B at most, never C (R8)


COMPONENT_EXT = (".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte")


_LEVEL_MOD = []


def level_module():
    """bin/agent_level.py as a module, loaded once."""
    if not _LEVEL_MOD:
        import importlib.util
        spec = importlib.util.spec_from_file_location("agent_level__shape", os.path.join(BIN, "agent_level.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, BIN)
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path.remove(BIN)
        _LEVEL_MOD.append(mod)
    return _LEVEL_MOD[0]


_REAL_SEEN = set()


def run_level(case, args, cwd, env, script_dir=None):
    """agent-level.sh <args> run from cwd: a CompletedProcess.

    test-slim: agent-level.sh is roots + `exec python3 agent_level.py <cwd> <args>`; most tests only
    need the output of the Python part, and the process starts are most of their time. So the Python
    module runs in this process, with the environment and folder a script start gets. The first
    check of each test class (and every check when AGENT_TEST_LEVEL_REAL=1) still starts the real
    agent-level.sh, and the tests of the wrapper itself (arguments, exit codes) call repo.run."""
    key = type(case).__name__
    if os.environ.get("AGENT_TEST_LEVEL_REAL") or key not in _REAL_SEEN:
        _REAL_SEEN.add(key)
        return subprocess.run([os.path.join(BIN, "agent-level.sh")] + list(args), cwd=cwd, env=env,
                              capture_output=True, text=True, input="", timeout=90)
    import contextlib
    import io
    import traceback
    from unittest import mock
    mod = level_module()
    out, err = io.StringIO(), io.StringIO()
    here = os.getcwd()
    code = 0
    with mock.patch.dict(os.environ, env, clear=True), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        os.chdir(cwd)
        try:
            code = mod.run([os.path.realpath(cwd)] + list(args)) or 0
        except mod.Stop as exc:
            sys.stderr.write("agent-level: %s\n" % str(exc).replace("\n", " "))
            code = 2
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        except Exception:
            traceback.print_exc()
            code = 1
        finally:
            os.chdir(here)
    return subprocess.CompletedProcess(["agent-level.sh"] + list(args), code, out.getvalue(), err.getvalue())


def prefix_keeps_kind(path):
    """True when c0/<path> gets the kind <path> gets: every path predicate of agent_level.py
    that decides a FILE line agrees on both, and the path has no space (FILE lines split on it)."""
    if re.search(r"\s", path):
        return False
    m = level_module()
    probes = (m.builtin_kind, m.is_ci, m.is_rule, m.in_task_folder, m.is_locale_file)
    return all(f(path) == f("c0/" + path) for f in probes)


class ShapeCase(LevelCase):

    def fresh(self):
        """A new project for the next subTest."""
        self.repo.cleanup()
        self.repo = ScriptRepo()
        self.addCleanup(self.repo.cleanup)

    def got(self, path, before, after, conf=None, others=None):
        """(level, reason) of path after base -> change."""
        files = dict(others or {})
        files[path] = before
        self.base(files, conf)
        self.put({path: after})
        r = self.ok()
        lines = self.files(r)
        self.assertIn(path, lines, r.stdout)
        return lines[path]

    def each(self, want, cases):
        """want: (level, reason); cases: (path, before, after).

        test-slim: the cases of one test share one project, one base commit and one `check`:
        case i lives at c<i>/<path>. agent_level.py gives each changed file its FILE line from
        that file alone (run(): kinds[path] = repo.kinds(path, ...)), so a case has the line it
        had in a project of its own, as long as the c<i>/ prefix cannot change its kind. A path
        rule anchored at the repo root (skills/, agents/, .claude/, .github/, gradle/...) or a
        path with a space could: such a case runs alone in a fresh project, as before.
        AGENT_TEST_SHAPE_ONE_BY_ONE=1 runs every case in a fresh project, as before."""
        cases = list(cases)

        def exp_of(path):
            return COMPONENT if want == CODE and path.endswith(COMPONENT_EXT) else want

        one_by_one = bool(os.environ.get("AGENT_TEST_SHAPE_ONE_BY_ONE"))
        batch = [] if one_by_one else [c for c in cases if prefix_keeps_kind(c[0])]
        alone = [c for c in cases if one_by_one or not prefix_keeps_kind(c[0])]
        started = False
        if batch:
            where = ["c%d/%s" % (i, c[0]) for i, c in enumerate(batch)]
            self.base({w: c[1] for w, c in zip(where, batch)})
            self.put({w: c[2] for w, c in zip(where, batch)})
            r = self.ok()
            lines = self.files(r)
            started = True
            for w, (path, before, after) in zip(where, batch):
                with self.subTest(path=path, before=before[:60], after=after[:60]):
                    self.assertIn(w, lines, r.stdout)
                    self.assertEqual(lines[w], exp_of(path))
        for path, before, after in alone:
            with self.subTest(path=path, before=before[:60], after=after[:60]):
                if started:
                    self.fresh()
                started = True
                self.assertEqual(self.got(path, before, after), exp_of(path))

    def swap(self, want, path, plain, directives, head="", tail=""):
        """Each directive in place of the plain comment: head + plain + tail -> head + d + tail."""
        self.each(want, [(path, head + plain + "\n" + tail, head + d + "\n" + tail) for d in directives])


C2_WORDS = [
    "type:", "noqa", "nolint", "pylint:", "pyright:", "mypy:", "pragma", "isort:", "fmt:", "ruff:",
    "flake8:", "nosec", "cython:", "coding:", "coding=", "vim:", "vi:", "ex:", "shellcheck",
    "yamllint", "yaml-language-server", "renovate:", "eslint", "global ", "globals ", "exported ",
    "prettier-ignore", "istanbul", "c8 ", "v8 ", "biome-ignore", "deno-", "tslint:", "jshint",
    "jscs:", "swiftlint:", "ignore:", "ignore_for_file:", "go:", "+build", "<reference", "<amd-",
    "clang-format", "noinspection", "checkstyle:", "$", "webpack", "ko ", "/ko", "build:",
    "endbuild", "inject:", "endinject", "htmlmin:", "[if", "[endif", "<![endif",
]


C3_WORDS = ["noqa", "nolint", "pragma", "type: ignore", "eslint-", "@ts-", "-*-", "coding:", "coding=",
            "prettier-ignore", "fallthrough", "fall through", "falls through", "fallthru"]


SLASH_EXT = [".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx", ".dart", ".java", ".kt",
             ".kts", ".swift", ".go", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh"]


SLASH_DIRECTIVES = [
    ("src/a.ts", "// @ts-ignore"), ("src/a.ts", "// @ts-expect-error"),
    ("src/a.js", "// eslint-disable-next-line no-x"), ("src/a.js", "/* eslint-env node */"),
    ("src/a.js", "/* global x */"), ("src/a.js", "// prettier-ignore"),
    ("src/a.js", "/* istanbul ignore next */"), ("src/a.go", "//go:build linux"),
    ("src/a.go", "//nolint"), ("src/a.go", "// +build linux"), ("src/a.js", "/*#__PURE__*/"),
    ("src/a.js", "//# sourceMappingURL=a.map"), ("src/a.ts", '/// <reference types="node" />'),
    ("lib/a.dart", "// ignore: unused"), ("lib/a.dart", "// ignore_for_file: x"),
    ("lib/a.dart", "// @dart=2.9"), ("src/a.cpp", "// NOLINT"), ("src/a.cpp", "// clang-format off"),
    ("src/a.c", "/* falls through */"), ("src/A.java", "// noinspection X"),
    ("src/A.java", "// CHECKSTYLE:OFF"), ("src/A.java", "// $NON-NLS-1$"),
    ("src/a.js", "/** @type {Foo} */"), ("src/a.js", "/**\n * Sum.\n * @param x\n */"),
    ("src/a.swift", "// swiftlint:disable x"), ("src/a.js", "// Copyright 2026 Acme"),
    ("src/a.js", "/*! keep */"), ("src/a.js", '/* webpackChunkName: "x" */'),
    ("src/a.js", "// @flow"), ("src/a.jsx", "/** @jsx h */"),
]


MARKUP_DIRECTIVES = [
    "<!--[if IE]><p>x</p><![endif]-->", '<!--#include file="a"-->', "<!--more-->",
    "<!-- ko if: x -->", "<!-- /ko -->", "<!-- build:js a.js -->", "<!-- endbuild -->",
    "<!-- inject:js -->", "<!-- endinject -->", "<!-- htmlmin:ignore -->",
    "<!-- prettier-ignore -->", "<!-- Copyright 2026 Acme -->",
]


class TestHashShape(ShapeCase):

    def test_r1_a_whole_line_comment_in_each_hash_family(self):
        self.each(("A", CO), [
            ("bin/run.sh", "#!/bin/bash\n# retry twice\nrun\n", "#!/bin/bash\n# retry three times\nrun\n"),
            ("bin/run.bash", "# retry twice\nrun\n", "# retry three times\nrun\n"),
            ("bin/run.zsh", "# retry twice\nrun\n", "# retry three times\nrun\n"),
            ("app/run.py", "# retry twice\nrun()\n", "# retry three times\nrun()\n"),
            ("ci/build.yml", "steps:\n  # build it\n  - make\n", "steps:\n  # build it twice\n  - make\n"),
            ("ci/build.yaml", "steps:\n  # build it\n  - make\n", "steps:\n  # build it twice\n  - make\n"),
            ("etc/app.conf", "# port of the app\nport=80\n", "# the port of the app\nport=80\n"),
        ])

    def test_r2_a_comment_line_added_or_a_block_removed(self):
        self.each(("A", CO), [
            ("app/run.py", "def f():\n    run()\n", "def f():\n    # keep the order: R5\n    run()\n"),
            ("app/run.py", "# one\n# two\n# three\nrun()\n", "run()\n"),
            ("bin/run.sh", "run\n", "run\n# done\n"),
            ("ci/a.yml", "a: 1\nb: 2\n", "a: 1\n# the b part\nb: 2\n"),
        ])

    def test_r3_a_trailing_comment_with_the_same_code(self):
        self.each(("A", CO), [
            ("app/run.py", "n = 3  # tries\n", "n = 3  # max tries\n"),
            ("app/run.py", "n = 3  # tries\n", "n = 3 # max tries\n"),
            ("app/run.py", "n = 3  # don't\n", "n = 3  # do not\n"),
            ("bin/run.sh", "run --fast  # quick\n", "run --fast  # quickest\n"),
            ("bin/run.sh", "run  # don't\n", "run  # do not\n"),
            ("ci/a.yml", "port: 80 # http\n", "port: 80 # plain http\n"),
            ("app/run.py", "f(\n    a,  # first\n    b,\n)\n", "f(\n    a,  # the first\n    b,\n)\n"),
        ])

    def test_r4_blank_lines_only(self):
        self.each(("A", WS), [
            ("app/run.py", "def a():\n    pass\ndef b():\n    pass\n",
             "def a():\n    pass\n\n\ndef b():\n    pass\n"),
            ("bin/run.sh", "a\nb\n", "a\n\nb\n"),
            ("etc/app.conf", "a=1\nb=2\n", "a=1\n\nb=2\n"),
        ])

    def test_a_comment_and_a_blank_line_say_comment_only(self):
        self.each(("A", CO), [("app/run.py", "# a\nrun()\n", "# b\n\nrun()\n")])

    def test_r9_comment_and_code_on_one_line(self):
        self.each(CODE, [
            ("app/run.py", "n = 3  # tries\n", "n = 4  # max tries\n"),
            ("bin/run.sh", "run 1  # a\n", "run 2  # b\n"),
        ])

    def test_r10_code_commented_out_or_back(self):
        self.each(CODE, [
            ("app/run.py", "run()\nstop()\n", "# run()\nstop()\n"),
            ("app/run.py", "# run()\nstop()\n", "run()\nstop()\n"),
            ("bin/run.sh", "run\nstop\n", "# run\nstop\n"),
        ])

    def test_r11_no_mixing_with_another_shape_in_v1(self):
        self.each(CODE, [("app/views.py", '# say hi\nflash("Hi")\n', '# greet\nflash("Hello")\n')])

    def test_r25_code_spacing_changes_too(self):
        self.each(CODE, [("app/run.py", "x=1  # a\n", "x = 1  # b\n")])

    def test_r26_trailing_white_space_only(self):
        self.each(("A", WS), [("app/run.py", "run()  \n", "run()\n")])

    def test_conf_a_hash_after_code_is_code(self):
        self.each(CODE, [("etc/app.conf", "port=80 # http\n", "port=80 # https\n")])

    def test_conf_an_indented_comment_line(self):
        self.each(("A", CO), [("etc/app.conf", "[a]\n  # note\n  x=1\n", "[a]\n  # note 2\n  x=1\n")])

    def test_sh_a_hash_inside_a_word_is_code(self):
        self.each(CODE, [
            ("bin/run.sh", "echo ${#a} b\n", "echo ${#a} c\n"),
            ("bin/run.sh", "echo a#b\n", "echo a#c\n"),
            ("bin/run.sh", "test $# -gt 1\n", "test $# -gt 2\n"),
        ])

    def test_yaml_a_hash_without_a_space_before_is_code(self):
        self.each(CODE, [("ci/a.yml", "url: http://x/#frag\n", "url: http://x/#top\n")])


class TestHashStrings(ShapeCase):

    def test_r12_py_a_hash_line_inside_a_multi_line_string(self):
        self.each(CODE, [
            ("app/help.py", 'HELP = """\nUsage:\n# step 1\n"""\n', 'HELP = """\nUsage:\n# step 2\n"""\n'),
            ("app/help.py", "HELP = '''\n# step 1\n'''\n", "HELP = '''\n# step 2\n'''\n"),
        ])

    def test_py_a_blank_line_inside_a_multi_line_string(self):
        self.each(CODE, [("app/help.py", 'X = """a\n\nb"""\n', 'X = """a\nb"""\n')])

    def test_r13_a_hash_inside_a_one_line_string(self):
        self.each(CODE, [   # check-blocks section 44 F10: a string literal in a code file is code
            ("app/a.py", 's = "# a"\n', 's = "# b"\n'),
            ("bin/a.sh", 'echo "# a"\n', 'echo "# b"\n'),
        ])

    def test_r13_a_hash_inside_an_f_string(self):
        self.each(CODE, [("app/a.py", 't = f"{n} # a"\n', 't = f"{n} # b"\n')])

    def test_r14_docstrings_are_strings(self):
        self.each(("A", "text change"), [("app/a.py", 'def f():\n    """Old."""\n', 'def f():\n    """New."""\n')])
        self.fresh()
        self.each(CODE, [("app/a.py", 'def f():\n    """Old.\n\n    More.\n    """\n',
                          'def f():\n    """Old.\n\n    Much more.\n    """\n')])

    def test_r12_sh_heredoc_bodies_are_strings(self):
        self.each(CODE, [
            ("bin/a.sh", "cat <<EOF\n# step 1\nEOF\n", "cat <<EOF\n# step 2\nEOF\n"),
            ("bin/a.sh", "cat <<-EOF\n\t# step 1\n\tEOF\n", "cat <<-EOF\n\t# step 2\n\tEOF\n"),
            ("bin/a.sh", "cat <<'EOF'\n# step 1\nEOF\n", "cat <<'EOF'\n# step 2\nEOF\n"),
            ("bin/a.sh", 'cat <<"EOF"\n# step 1\nEOF\n', 'cat <<"EOF"\n# step 2\nEOF\n'),
            ("bin/a.sh", "cat <<\\EOF\n# step 1\nEOF\n", "cat <<\\EOF\n# step 2\nEOF\n"),
            ("bin/a.sh", "cat << EOF\n# step 1\nEOF\n", "cat << EOF\n# step 2\nEOF\n"),
            ("bin/a.sh", "python3 - <<'PY'\nx = 1  # step 1\nPY\n", "python3 - <<'PY'\nx = 1  # step 2\nPY\n"),
            ("bin/a.sh", "cat <<EOF\na\n\nb\nEOF\n", "cat <<EOF\na\nb\nEOF\n"),
        ])

    def test_sh_a_comment_after_the_heredoc_end(self):
        self.each(("A", CO), [
            ("bin/a.sh", "cat <<EOF\nhi\nEOF\n# after\n", "cat <<EOF\nhi\nEOF\n# later\n"),
            ("bin/a.sh", "cat <<-EOF\n\thi\n\tEOF\n# after\n", "cat <<-EOF\n\thi\n\tEOF\n# later\n"),
        ])

    def test_sh_a_here_string_is_no_heredoc(self):
        self.each(("A", CO), [("bin/a.sh", 'cat <<< "x"\n# note\n', 'cat <<< "x"\n# note 2\n')])

    def test_sh_quotes(self):
        # an escaped " inside "..." does not end it: the # is in the string (today: text change)
        self.each(CODE, [("bin/a.sh", 'echo "a \\" # b"\n', 'echo "a \\" # c"\n')])   # check-blocks section 44 F10: a string literal in a code file is code
        self.fresh()
        self.each(("A", CO), [
            # no escapes in '...': the string is a\ and the comment follows
            ("bin/a.sh", "echo 'a\\' # note\n", "echo 'a\\' # note 2\n"),
            # $'...' has escapes: the string is a'b
            ("bin/a.sh", "echo $'a\\'b' # note\n", "echo $'a\\'b' # note 2\n"),
            ("bin/a.sh", "x=`date` # now\n", "x=`date` # today\n"),
        ])
        self.fresh()
        self.each(CODE, [("bin/a.sh", 'echo "a\n# not a comment\nb"\n', 'echo "a\n# not one\nb"\n')])

    def test_r12_yaml_block_scalar_bodies_are_strings(self):
        self.each(CODE, [
            ("ci/a.yml", "run: |\n  echo hi\n  # step 1\nname: x\n", "run: |\n  echo hi\n  # step 2\nname: x\n"),
            ("ci/a.yml", "steps:\n  - >-\n    echo a\n    # step 1\n", "steps:\n  - >-\n    echo a\n    # step 2\n"),
            ("ci/a.yml", "run: |+\n  # step 1\n", "run: |+\n  # step 2\n"),
            ("ci/a.yml", "run: |\n  a\n\n  b\nx: 1\n", "run: |\n  a\n  b\nx: 1\n"),
        ])

    def test_yaml_after_the_block_a_comment_is_a_comment(self):
        self.each(("A", CO), [
            ("ci/a.yml", "run: |\n  echo hi\n# after\nname: x\n", "run: |\n  echo hi\n# later\nname: x\n"),
            ("ci/a.yml", "run: | # the script\n  echo a\n", "run: | # script\n  echo a\n"),
        ])

    def test_yaml_quoted_values(self):
        self.each(CODE, [("ci/a.yml", 'msg: "a\n  # b\n  c"\n', 'msg: "a\n  # d\n  c"\n')])
        self.fresh()
        self.each(CODE, [   # check-blocks section 47 G7: a changed value in a config file is code
            ("ci/a.yml", 'a: ["x # y", 1]\n', 'a: ["x # z", 1]\n'),
            ("ci/a.yml", "b: 'x # y'\n", "b: 'x # z'\n"),
            # the apostrophe in a plain value opens no string, so the next quote still does
            ("ci/a.yml", "a: it's here\nb: 'x # y'\n", "a: it's here\nb: 'x # z'\n"),
        ])

    def test_yaml_an_apostrophe_inside_a_plain_value(self):
        self.each(("A", CO), [("ci/a.yml", "a: it's here\n# note\nb: 1\n", "a: it's here\n# note 2\nb: 1\n")])


class TestHashDirectives(ShapeCase):

    def test_r15_c1_tight_comments(self):
        self.each(CODE, [
            ("bin/a.sh", "#!/bin/sh\nrun\n", "#!/bin/bash\nrun\n"),
            ("bin/a.sh", "run\n# plain note\n", "run\n#SBATCH --time=1\n"),
            ("bin/a.zsh", "run\n# plain note\n", "run\n#compdef git\n"),
            ("ci/a.yml", "a: 1\n# plain note\n", "a: 1\n#cloud-config\n"),
            ("app/a.py", "run()\n# plain note\n", "run()\n#print(x)\n"),
            ("etc/a.conf", "x=1\n# plain note\n", "x=1\n#x=2\n"),
        ])

    def test_r15_a_directive_added_edited_or_moved(self):
        self.each(CODE, [
            ("app/a.py", "x = f()\n", "x = f()  # noqa: E501\n"),
            ("app/a.py", "x = f()  # noqa: E501\n", "x = f()  # noqa: E302\n"),
            ("app/a.py", "a = 1  # type: int\nb = 2\n", "a = 1\nb = 2  # type: int\n"),
            ("app/a.py", "x = f()  # noqa: E501\n", "x = f()\n"),
        ])

    def test_c1_not_tight_comments_are_plain(self):
        self.each(("A", CO), [
            ("app/a.py", "## Part 2\nrun()\n", "## Part 3\nrun()\n"),
            ("bin/a.sh", "#----\nrun\n", "#====\nrun\n"),
            ("bin/a.sh", "#~~~\nrun\n", "#~~~~~\nrun\n"),
            ("app/a.py", "#\nrun()\n", "# note\nrun()\n"),
        ])

    def test_c2_tool_words_at_the_head(self):
        self.swap(CODE, "app/a.py", "# plain note", ["# %s x" % w for w in C2_WORDS], head="run()\n")

    def test_c2_any_case(self):
        self.swap(CODE, "app/a.py", "# plain note",
                  ["# NOQA", "# Pylint: disable=x", "# SHELLCHECK disable=SC1", "# Type: ignore"], head="run()\n")

    def test_c3_words_anywhere(self):
        self.swap(CODE, "app/a.py", "n = f()  # long", ["n = f()  # long, %s x" % w for w in C3_WORDS])

    def test_c4_an_at_word(self):
        self.swap(CODE, "app/a.py", "# note", ["# see @alice", "# @package _global_"], tail="run()\n")
        self.fresh()
        self.each(("A", CO), [("app/a.py", "# mail a@b.io\nrun()\n", "# mail c@d.io\nrun()\n")])

    def test_r16_c5_license(self):
        self.each(CODE, [
            ("app/a.py", "# Copyright 2025 Acme\nrun()\n", "# Copyright 2026 Acme\nrun()\n"),
            ("bin/a.sh", "# SPDX-License-Identifier: MIT\nrun\n", "# SPDX-License-Identifier: Apache-2.0\nrun\n"),
            ("app/a.py", "# Licensed under MIT\nrun()\n", "# Licenced under MIT\nrun()\n"),
            ("app/a.py", "# \u00a9 2025 Acme\nrun()\n", "# \u00a9 2026 Acme\nrun()\n"),
            ("app/a.py", "# note\nrun()\n", "# copyright Acme\nrun()\n"),
        ])


class TestHashGuards(ShapeCase):

    def test_r17_a_comment_or_blank_line_after_a_continued_line(self):
        self.each(CODE, [
            ("bin/a.sh", "docker run \\\n  img\n", "docker run \\\n  # -v a:b\n  img\n"),
            ("bin/a.sh", "a \\\n  b\n", "a \\\n\n  b\n"),
            ("bin/a.sh", "a \\\n# note\n  b\n", "a \\\n  b\n"),
            ("app/a.py", "x = 1 + \\\n    2\n", "x = 1 + \\\n# c\n    2\n"),
        ])

    def test_r18_a_comment_ending_in_a_backslash(self):
        self.each(CODE, [
            ("bin/a.sh", "# see C:\\\nrun\n", "# see D:\\\nrun\n"),
            ("app/a.py", "# a\nrun()\n", "# a \\\nrun()\n"),
        ])

    def test_r19_the_lexer_is_unsure(self):
        self.each(CODE, [
            ("bin/a.sh", "echo 'a\n# note\n", "echo 'a\n# note 2\n"),
            ("bin/a.sh", "cat <<EOF\n# note\n", "cat <<EOF\n# note 2\n"),
            ("app/a.py", 'x = """a\n# note\n', 'x = """a\n# note 2\n'),
            ("ci/a.yml", 'a: "x\n# note\n', 'a: "x\n# note 2\n'),
        ])


class TestScope(ShapeCase):

    def test_the_file_line_and_the_level(self):
        self.base({"app/run.py": "# a\nrun()\n"})
        self.put({"app/run.py": "# b\nrun()\n"})
        r = self.ok()
        lines = r.stdout.splitlines()
        # check-blocks: a comment-only change is text: no BUILD, the related tests still run
        self.assertIn("FILE app/run.py: text (comment only)", lines)
        self.assertNotIn("BUILD", lines[0])
        self.assertIn("RELATED TESTS", lines[0])

    def test_a_comment_only_file_next_to_a_style_file(self):
        self.base({"app/run.py": "# a\nrun()\n", "web/a.css": "a{}\n"})
        self.put({"app/run.py": "# b\nrun()\n", "web/a.css": "b{}\n"})
        r = self.ok()
        self.assertEqual(self.required(r), "A+B")
        self.assertEqual(self.files(r), {"app/run.py": ("A", CO), "web/a.css": ("B", "style file")})

    def test_r21_path_levels_stay(self):
        self.assertEqual(self.got("requirements.txt", "# pinned\nflask==2.0\n", "# pinned for py3.9\nflask==2.0\n"),
                         ("D", "built-in: dependency list"))
        self.fresh()
        self.assertEqual(self.got("db/seed.sql", "-- a\nselect 1;\n", "-- b\nselect 1;\n"), ("D", "built-in: schema"))
        self.fresh()
        # owner 2A 2026-11-25: Danger paths is a hint, a comment-only change stays A there
        self.assertEqual(self.got("src/money/calc.py", "# a\nrun()\n", "# b\nrun()\n",
                                  conf={"level3_paths": "src/money/"}), ("A", "comment only"))

    def test_r22_new_deleted_and_binary_files(self):
        self.base({"app/a.py": "x\n"})
        self.put({"bin/new.sh": "# only a comment\n"})
        self.assertEqual(self.files(self.ok())["bin/new.sh"], ("C", "new file"))
        self.fresh()
        self.base({"app/a.py": "x\n", "bin/old.sh": "# only a comment\n"})
        self.put({"bin/old.sh": None})
        self.assertEqual(self.files(self.ok())["bin/old.sh"], ("C", "deleted file"))
        self.fresh()
        self.assertEqual(self.got("app/b.py", b"\x00# a\n", b"\x00# b\n"), ("C", "binary file"))

    def test_r23_style_and_text_files_as_now(self):
        self.assertEqual(self.got("web/a.css", "/* a */\n.a{}\n", "/* b */\n.a{}\n"), ("B", "style file"))
        self.fresh()
        self.assertEqual(self.got("docs/a.md", "<!-- a -->\nHi\n", "<!-- b -->\nHi\n"), ("A", "text file"))

    def test_r24_extensions_not_in_v1(self):
        paths = ["lib/a.rb", "web/a.php", "conf/a.toml", "conf/a.ini", "conf/a.cfg", "app/a.pyi",
                 "Makefile", "Dockerfile", "bin/foo"]
        self.each(CODE, [(p, "# a\nrun\n", "# b\nrun\n") for p in paths] + [
            ("src/App.vue", "<!-- a -->\n<p>x</p>\n", "<!-- b -->\n<p>x</p>\n"),
            ("src/App.svelte", "<!-- a -->\n<p>x</p>\n", "<!-- b -->\n<p>x</p>\n"),
            ("src/a.rs", "// a\nrun();\n", "// b\nrun();\n"),
        ])

    def test_r24_a_symlink(self):
        self.base({"bin/t1.sh": "run\n"})
        os.symlink("t1.sh", self.repo.path("bin/link.sh"))
        self.commit("link")
        self.git("tag", "-f", "base")
        self.put({"bin/t2.sh": "t1.sh  # x\n"})
        os.remove(self.repo.path("bin/link.sh"))
        os.symlink("t2.sh", self.repo.path("bin/link.sh"))
        self.assertEqual(self.files(self.ok())["bin/link.sh"], CODE)

    def test_r24_a_symlink_that_became_a_file(self):
        self.base({"bin/t1.sh": "run\n"})
        os.symlink("t1.sh", self.repo.path("bin/link.sh"))
        self.commit("link")
        self.git("tag", "-f", "base")
        os.remove(self.repo.path("bin/link.sh"))
        self.put({"bin/link.sh": "t1.sh  # x\n"})
        self.assertEqual(self.files(self.ok())["bin/link.sh"], CODE)


class TestSlashShape(ShapeCase):

    def test_r1_a_whole_line_comment_in_each_extension(self):
        self.each(("A", CO), [("src/a" + e, "// retry twice\nrun();\n", "// retry three times\nrun();\n")
                            for e in SLASH_EXT])

    def test_r3_a_trailing_comment(self):
        self.each(("A", CO), [
            ("src/a.js", "run(); // fast\n", "run(); // faster\n"),
            ("src/a.js", "run();\t// fast\n", "run();\t// faster\n"),
        ])

    def test_slash_slash_right_after_code_is_code(self):
        self.each(CODE, [("src/a.js", "run();// fast\n", "run();// faster\n")])

    def test_r5_a_block_comment_over_lines(self):
        self.each(("A", CO), [
            ("src/a.js", "/* a\n * b\n */\nrun();\n", "/* a\n * c\n */\nrun();\n"),
            ("src/a.c", "int a; /* a\n b */\n", "int a; /* a\n c */\n"),
        ])

    def test_an_inline_block_comment(self):
        self.each(("A", CO), [("src/a.js", "f(1/* a */);\n", "f(1/* bb */);\n")])

    def test_an_inline_block_comment_counts_as_one_space(self):
        self.each(CODE, [("src/a.js", "x = a/**/b;\n", "x = ab;\n")])

    def test_r6_a_jsx_comment(self):
        before = "export const A = () => (\n  <div>\n    {/* old */}\n    <p>Hi</p>\n  </div>\n);\n"
        self.each(("A", CO), [("src/A.tsx", before, before.replace("old", "new")),
                            ("src/A.jsx", before, before.replace("old", "new"))])

    def test_r4_blank_lines_only(self):
        self.each(("A", WS), [("src/a.js", "a();\nb();\n", "a();\n\nb();\n")])

    def test_moved_comment_lines_are_comment_only_not_a_line_move(self):
        self.each(("A", CO), [("lib/a.dart", "// a\n// b\nrun();\n", "// b\n// a\nrun();\n")])

    def test_r9_r10_code(self):
        self.each(CODE, [
            ("src/a.js", "run(1); // a\n", "run(2); // b\n"),
            ("src/a.js", "run();\n", "// run();\n"),
            ("src/a.go", "// run()\nstop()\n", "run()\nstop()\n"),
        ])

    def test_a_hash_line_is_code_in_slash_files(self):
        self.each(("A", CO), [
            ("src/a.c", "#define N 1 // n\n", "#define N 1 // count\n"),
            ("src/a.js", "#!/usr/bin/env node\n// a\nrun();\n", "#!/usr/bin/env node\n// b\nrun();\n"),
        ])

    def test_block_comments_do_not_nest(self):
        self.each(CODE, [("src/a.swift", "/* a /* b */ c */\nrun()\n", "/* a /* b */ d */\nrun()\n")])


class TestSlashStrings(ShapeCase):

    def test_r12_a_template_literal_line(self):
        self.each(CODE, [
            ("src/a.js", "const t = `\n// step 1\n`;\n", "const t = `\n// step 2\n`;\n"),
            ("src/a.ts", "const t = `\n/* step 1 */\n`;\n", "const t = `\n/* step 2 */\n`;\n"),
            ("src/a.js", "const t = `a ${f(`b`)} c\n// x\n`;\n", "const t = `a ${f(`b`)} c\n// y\n`;\n"),
            ("src/a.js", "const t = `a\n\nb`;\n", "const t = `a\nb`;\n"),
        ])

    def test_after_a_template_a_comment_is_a_comment(self):
        self.each(("A", CO), [
            ("src/a.js", "const t = `a ${b} c`; // note\n", "const t = `a ${b} c`; // note 2\n"),
            ("src/a.js", 'const t = `a ${"`"} b`; // note\n', 'const t = `a ${"`"} b`; // note 2\n'),
        ])

    def test_go_raw_strings(self):
        self.each(CODE, [("src/a.go", "var s = `\n// x\n`\n", "var s = `\n// y\n`\n")])
        self.fresh()
        self.each(("A", CO), [("src/a.go", "var s = `a\\` // note\n", "var s = `a\\` // note 2\n")])

    def test_triple_quoted_strings(self):
        self.each(CODE, [
            ("src/A.java", 'String s = """\n  // x\n  """;\n', 'String s = """\n  // y\n  """;\n'),
            ("src/a.kt", 'val s = """\n// x\n"""\n', 'val s = """\n// y\n"""\n'),
            ("src/a.kts", 'val s = """\n// x\n"""\n', 'val s = """\n// y\n"""\n'),
            ("src/a.swift", 'let s = """\n// x\n"""\n', 'let s = """\n// y\n"""\n'),
            ("lib/a.dart", "var s = '''\n// x\n''';\n", "var s = '''\n// y\n''';\n"),
            ("lib/a.dart", 'var s = """\n// x\n""";\n', 'var s = """\n// y\n""";\n'),
        ])

    def test_kotlin_triple_quotes_have_no_escapes(self):
        self.each(("A", CO), [("src/a.kt", 'val s = """a\\""" // note\n', 'val s = """a\\""" // note 2\n')])

    def test_one_line_strings_hide_comment_markers(self):
        self.each(CODE, [("src/a.js", 'const u = "a // b";\n', 'const u = "a // c";\n')])   # check-blocks section 44 F10: a string literal in a code file is code
        self.fresh()
        self.each(CODE, [
            ("src/a.js", "const u = 'a /* b';\nrun(1);\nconst v = '*/';\n",
             "const u = 'a /* b';\nrun(2);\nconst v = '*/';\n"),
            ("src/a.js", 'const s = "a \\" // b"; run();\n', 'const s = "a \\" // b"; go();\n'),
        ])

    def test_a_char_literal(self):
        self.each(("A", CO), [("src/a.c", "char q = '\"'; // note\n", "char q = '\"'; // note 2\n")])

    def test_slash_slash_after_a_colon_is_code(self):
        self.each(CODE, [("src/A.jsx", "<p>See https://a.io/{p}</p>\n", "<p>See https://a.io/{q}</p>\n")])

    def test_r17_a_comment_line_inside_a_continued_macro(self):
        self.each(CODE, [("src/a.c", "#define X \\\n  a\n", "#define X \\\n  // c\n  a\n")])

    def test_r18_a_comment_ending_in_a_backslash(self):
        self.each(CODE, [
            ("src/a.c", "// see C:\\\nrun();\n", "// see D:\\\nrun();\n"),
            ("src/a.c", "// note\nrun();\n", "// note \\\nrun();\n"),
        ])

    def test_r19_the_lexer_is_unsure(self):
        self.each(CODE, [
            ("src/A.jsx", "export const A = () => <p>Don't stop</p>; // note\n",
             "export const A = () => <p>Don't stop</p>; // note 2\n"),
            ("src/a.js", "/* a\nrun();\n", "/* b\nrun();\n"),
            ("src/a.js", "const t = `a\n// x\n", "const t = `a\n// y\n"),
        ])

    def test_r20_cgo(self):
        self.each(CODE, [("src/a.go", 'package main\n\n// #include <stdio.h>\nimport "C"\n',
                          'package main\n\n// #include <stdlib.h>\nimport "C"\n')])
        self.fresh()
        self.each(("A", CO), [("src/a.go", 'package main\n\n// a note\nimport "fmt"\n',
                             'package main\n\n// a longer note\nimport "fmt"\n')])


class TestSlashDirectives(ShapeCase):

    def test_c1_to_c5_in_slash_files(self):
        self.each(CODE, [(p, "run();\n// plain note\n", "run();\n%s\n" % d) for p, d in SLASH_DIRECTIVES])

    def test_a_directive_edited(self):
        self.each(CODE, [("src/a.js", "// eslint-disable-next-line a\nrun();\n",
                          "// eslint-disable-next-line b\nrun();\n")])

    def test_plain_slash_comments(self):
        self.each(("A", CO), [
            ("lib/a.dart", "/// doc\nrun();\n", "/// docs\nrun();\n"),
            ("src/a.js", "/** doc */\nrun();\n", "/** docs */\nrun();\n"),
            ("src/a.js", "//----\nrun();\n", "//====\nrun();\n"),
            ("src/a.js", "////\nrun();\n", "//////\nrun();\n"),
            ("src/a.js", "// mail a@b.io\nrun();\n", "// mail c@d.io\nrun();\n"),
        ])


class TestMarkup(ShapeCase):

    def test_r7_html_and_xml_comments(self):
        self.each(("A", CO), [
            ("web/a.html", "<!-- old -->\n<p>Hi</p>\n", "<!-- new -->\n<p>Hi</p>\n"),
            ("web/a.htm", "<!-- old -->\n<p>Hi</p>\n", "<!-- new -->\n<p>Hi</p>\n"),
            ("res/a.xml", "<a>\n  <!-- x -->\n  <b/>\n</a>\n", "<a>\n  <!-- y -->\n  <b/>\n</a>\n"),
            ("web/a.html", "<!--\n a\n-->\n<p>Hi</p>\n", "<!--\n b\n-->\n<p>Hi</p>\n"),
            ("web/a.html", "<p>a<!-- x -->b</p>\n", "<p>a<!-- y -->b</p>\n"),
            ("web/a.html", "<p>1 > 0</p>\n<!-- a -->\n", "<p>1 > 0</p>\n<!-- b -->\n"),
            ("web/a.html", "<p>Don't</p>\n<!-- a -->\n", "<p>Don't</p>\n<!-- b -->\n"),
            ("web/a.html", "<script>run();</script>\n<!-- a -->\n", "<script>run();</script>\n<!-- b -->\n"),
        ])

    def test_r4_blank_lines_only(self):
        self.each(("A", WS), [("web/a.html", "<p>a</p>\n<p>b</p>\n", "<p>a</p>\n\n<p>b</p>\n")])

    def test_an_attribute_value_is_no_comment(self):
        # a text attribute: today's level is a text change, never "comment only"
        self.each(("A", "text change"), [("web/a.html", '<a title="<!-- x -->">t</a>\n', '<a title="<!-- y -->">t</a>\n')])

    def test_script_style_and_cdata_bodies_are_code(self):
        self.each(CODE, [
            ("web/a.html", "<script>\n// a\nrun();\n</script>\n", "<script>\n// b\nrun();\n</script>\n"),
            ("web/a.html", "<script>\n<!-- a -->\nrun();\n</script>\n", "<script>\n<!-- b -->\nrun();\n</script>\n"),
            ("web/a.html", '<script type="module">\n<!-- a -->\n</script>\n',
             '<script type="module">\n<!-- b -->\n</script>\n'),
            ("web/a.html", "<SCRIPT>\n<!-- a -->\n</SCRIPT>\n", "<SCRIPT>\n<!-- b -->\n</SCRIPT>\n"),
            ("web/a.html", "<style>\n<!-- a -->\n</style>\n", "<style>\n<!-- b -->\n</style>\n"),
            ("res/a.xml", "<a><![CDATA[\n<!-- x -->\n]]></a>\n", "<a><![CDATA[\n<!-- y -->\n]]></a>\n"),
        ])

    def test_markup_directives(self):
        self.each(CODE, [("web/a.html", "<p>x</p>\n<!-- plain note -->\n", "<p>x</p>\n%s\n" % d)
                         for d in MARKUP_DIRECTIVES])

    def test_a_comment_open_at_the_end(self):
        self.each(CODE, [("web/a.html", "<!-- a\n<p>x</p>\n", "<!-- b\n<p>x</p>\n")])


class TestReviewCore(ShapeCase):

    def test_f1_sh_nested_quotes_and_parameter_expansions(self):
        self.each(CODE, [
            ("bin/a.sh", 'echo "$(printf "%s" "a # b")"; echo ok\n', 'echo "$(printf "%s" "a # b")"; rm -rf ~/tmp\n'),
            ("bin/a.sh", "cd ${DIR:-/srv #old}\nls\n", "cd ${DIR:-/srv #new}\nls\n"),
            ("bin/a.sh", 'v=${x:-a # }; echo "$v"\nls\n', 'v=${x:-a # }; rm -rf "$v"\nls\n'),
            ("bin/a.sh", 'echo "$(printf "%s" "a # b")"\n', 'echo "$(printf "%s" "a # c")"\n'),
            ("bin/a.sh", "echo a\\ #b\nls\n", "echo a\\ #c\nls\n"),
            ("bin/a.sh", "echo a\\;# b\nls\n", "echo a\\;# c\nls\n"),
            ("bin/a.sh", "echo a\\|# b\nls\n", "echo a\\|# c\nls\n"),
        ])
        self.fresh()
        # the hidden part is string text in a code file: code (section 44 F10), never "comment only"
        self.each(CODE, [
            ("bin/a.sh", "x=1;# don't\necho 'a' # c\necho \"it's # here\"\n",
             "x=1;# don't\necho 'a' # c\necho \"it's # there\"\n"),
        ])

    def test_f1_sh_a_hash_after_an_operator_is_a_comment(self):
        self.each(("A", CO), [("bin/a.sh", "x=1;# don't\nrun\n", "x=1;# do not\nrun\n")])

    def test_f2_the_first_lines_keep_their_place(self):
        self.each(CODE, [
            ("bin/a.sh", "#!/bin/bash\necho hi\n", "# helper script\n#!/bin/bash\necho hi\n"),
            ("bin/a.sh", "#!/bin/bash\necho hi\n", "\n#!/bin/bash\necho hi\n"),
            ("app/a.py", "# -*- coding: latin-1 -*-\ns = 'x'\n", "# a\n# b\n# -*- coding: latin-1 -*-\ns = 'x'\n"),
            ("app/a.py", "#!/usr/bin/env python\n# -*- coding: latin-1 -*-\nrun()\n",
             "#!/usr/bin/env python\n# note\n# -*- coding: latin-1 -*-\nrun()\n"),
            ("res/a.xml", '<?xml version="1.0"?>\n<root/>\n', '<!-- note -->\n<?xml version="1.0"?>\n<root/>\n'),
            ("ci/a.yml", "#cloud-config\nruncmd: []\n", "# note\n#cloud-config\nruncmd: []\n"),
        ])

    def test_f2_a_comment_after_the_shebang_is_fine(self):
        self.each(("A", CO), [
            ("bin/a.sh", "#!/bin/bash\necho hi\n", "#!/bin/bash\n# say hi\necho hi\n"),
            ("bin/a.sh", "# tool a\nrun\n", "# tool b\nrun\n"),
        ])

    def test_f3_yaml_tags_and_anchors_before_a_block(self):
        self.each(CODE, [
            ("ci/a.yml", 'Code: !Sub |\n  print("total # of items"); x = 1\n',
             'Code: !Sub |\n  print("total # of items"); x = 2\n'),
            ("ci/a.yml", 'base: &script |\n  echo "a # b"; x=1\n', 'base: &script |\n  echo "a # b"; x=2\n'),
            ("ci/a.yml", 'base: !!str &s |\n  echo "a # b"; x=1\n', 'base: !!str &s |\n  echo "a # b"; x=2\n'),
        ])

    def test_f3_yaml_tags_and_anchors_before_a_quote(self):
        self.each(CODE, [   # check-blocks section 47 G7: a changed value in a config file is code
            ("ci/a.yml", 'msg: !!str "a # b"\n', 'msg: !!str "a # c"\n'),
            ("ci/a.yml", 'msg: &m "a # b"\n', 'msg: &m "a # c"\n'),
        ])

    def test_f4_template_code_in_a_comment(self):
        self.each(CODE, [
            ("ci/a.yml", "spec:\n  # keep\n  replicas: 3\n", 'spec:\n  # keep {{- "" -}}\n  replicas: 3\n'),
            ("ci/a.yml", 'data:\n  # note\n  a: "1"\n', 'data:\n  # {{ .Values.extra }}\n  a: "1"\n'),
            ("web/a.html", "<body>\n<!-- build: {{ build_id }} -->\n</body>\n",
             "<body>\n<!-- build: {{ request.user.password }} -->\n</body>\n"),
            ("web/a.html", "<body>\n<!-- note -->\n</body>\n",
             '<body>\n<!-- {% include "admin_tools.html" %} -->\n</body>\n'),
            ("web/a.html", "<body>\n<!-- note -->\n</body>\n", "<body>\n<!-- {# x #} -->\n</body>\n"),
            ("web/a.html", "<body>\n<!-- note -->\n</body>\n", "<body>\n<!-- <%= user.secret %> -->\n</body>\n"),
            ("bin/a.sh", "# note\nrun\n", "# uses ${HOME}\nrun\n"),
        ])

    def test_f5_pep723_inline_dependencies(self):
        before = '# /// script\n# dependencies = [\n#   "requests<3",\n# ]\n# ///\nimport requests\n'
        # today's level: the old pair rule sees a quoted string change (L0 text change), never "comment only"
        self.each(("A", "text change"), [("app/a.py", before, before.replace("requests<3", "requests-evil"))])

    def test_f6_a_line_break_inside_a_comment(self):
        self.each(CODE, [
            ("app/a.py", "n = 1\n# note\nprint(n)\n", "n = 1\n# note\rn = 2\nprint(n)\n"),
            ("ci/a.yml", "a: 1\n# note\n", "a: 1\n# note\rb: 2\n"),
            ("ci/a.yml", "a: 1\n# note\n", "a: 1\n# note\x85b: 2\n"),
            ("src/a.js", "let n = 1;\n// note\nexport { n };\n", "let n = 1;\n// note\rn = 2;\nexport { n };\n"),
            ("src/a.js", "let n = 1;\n// note\nexport { n };\n", "let n = 1;\n// note\u2028n = 2;\nexport { n };\n"),
            ("src/a.js", "let n = 1;\n// note\nexport { n };\n", "let n = 1;\n// note\u2029n = 2;\nexport { n };\n"),
            ("src/a.c", "int n = 1;\n// note\n", "int n = 1;\n// note\rint m = 2;\n"),
        ])

    def test_f7_a_block_comment_keeps_its_line_breaks(self):
        self.each(CODE, [("src/a.js", "function f(x) {\n  return x;\n}\n", "function f(x) {\n  return/*\n*/x;\n}\n")])

    def test_f11_yaml_blank_lines_stay(self):
        self.each(CODE, [
            ("ci/a.yml", "description: first part\n  second part\n", "description: first part\n\n  second part\n"),
            ("ci/a.yml", "a: 1\nb: 2\n", "a: 1\n\nb: 2\n"),
        ])

    def test_f11_yaml_comment_lines_still_go(self):
        self.each(("A", CO), [("ci/a.yml", "a: 1\n# x\nb: 2\n", "a: 1\nb: 2\n")])

    def test_f12_the_line_after_a_whole_line_directive(self):
        self.each(CODE, [
            ("src/a.js", "// eslint-disable-next-line no-eval\neval(x);\n",
             "// eslint-disable-next-line no-eval\n// why we eval\neval(x);\n"),
            ("app/a.py", "# pylint: disable-next=eval-used\neval(x)\n",
             "# pylint: disable-next=eval-used\n# why\neval(x)\n"),
            ("src/a.js", "/* istanbul ignore next */\nf();\n", "/* istanbul ignore next */\n\nf();\n"),
            ("src/a.go", "//go:build linux\n\npackage x\n", "//go:build linux\npackage x\n"),
        ])

    def test_f12_other_comments_near_a_directive_are_fine(self):
        self.each(("A", CO), [
            ("src/a.js", '// @flow\n\nimport x from "y";\n// a\n', '// @flow\n\nimport x from "y";\n// b\n'),
            ("bin/a.sh", "# Copyright 2026 Acme\n# plain note\nrun\n", "# Copyright 2026 Acme\n# plain note 2\nrun\n"),
            ("src/a.go", "//go:build linux\n\npackage x\n// a\n", "//go:build linux\n\npackage x\n// b\n"),
            ("app/a.py", "# -*- coding: utf-8 -*-\n# a\nrun()\n", "# -*- coding: utf-8 -*-\n# b\nrun()\n"),
        ])

    def test_f12_swift_tools_version(self):
        self.each(CODE, [("Package.swift", "// swift-tools-version:5.5\nimport PackageDescription\n",
                          "// swift-tools-version:5.9\nimport PackageDescription\n")])

    def test_f13_an_exec_bit_change(self):
        self.base({"bin/hook.sh": "echo hi\n# a\n"})
        self.put({"bin/hook.sh": "echo hi\n# b\n"})
        os.chmod(self.repo.path("bin/hook.sh"), 0o755)
        self.assertEqual(self.files(self.ok())["bin/hook.sh"], CODE)

    def test_f14_bytes_that_are_not_utf8(self):
        self.each(CODE, [("bin/a.sh", b"# a\nrm -f caf\xe9\n", b"# b\nrm -f caf\xe8\n"),
                         ("app/a.py", b"# a\ns = 'caf\xe9'\n", b"# b\ns = 'caf\xe8'\n")])

    def test_f15_a_moved_comment_is_comment_only(self):
        self.each(("A", CO), [("app/a.py", "x = 1\n# keep sorted\ny = 2\nz = 3\n", "x = 1\ny = 2\n# keep sorted\nz = 3\n")])


class TestReviewSlash(ShapeCase):

    def test_f6_java_unicode_escapes(self):
        self.each(CODE, [
            ("src/A.java", "class A { static int n() {\n  // note\n  return 1;\n} }\n",
             "class A { static int n() {\n  // note \\u000a if (true) return 2;\n  return 1;\n} }\n"),
            ("src/A.java", 'String s = "\\u0022"; // a\n', 'String s = "\\u0022"; // b\n'),
        ])

    def test_f8_raw_strings_swift_and_cpp(self):
        self.each(CODE, [
            ("src/a.swift", 'let s = #"say " // b"#; run(1)\n', 'let s = #"say " // b"#; run(2)\n'),
            ("src/a.cpp", 'auto s = R"(say " // b)"; run(1);\n', 'auto s = R"(say " // b)"; run(2);\n'),
            ("src/a.cc", 'auto s = u8R"x(a " // b)x"; run(1);\n', 'auto s = u8R"x(a " // b)x"; run(2);\n'),
        ])

    def test_f8_dart_raw_strings(self):
        self.each(CODE, [
            ("lib/a.dart", "f(r'C:\\', 'x // y'); run(1);\n", "f(r'C:\\', 'x // y'); run(2);\n"),
            ("lib/a.dart", 'var s = r"""\n// x\n""";\n', 'var s = r"""\n// y\n""";\n'),
        ])
        self.fresh()
        self.each(("A", CO), [("lib/a.dart", "f(r'C:\\'); // a\n", "f(r'C:\\'); // b\n")])

    def test_f10_jsx_text_with_comment_markers(self):
        before = ("export const Help = () => (\n  <div>\n    <p>Block comments start with /* and</p>\n"
                  "    <button onClick={save}>Go</button>\n    <p>end with */ in JS.</p>\n  </div>\n);\n")
        self.each(CODE, [("src/Help.js", before, before.replace("save", "wipeAll"))])
        self.fresh()
        # .jsx/.tsx are markup files: today's level for a changed {handler} is the old prop rule (L1)
        self.each(("B", "new prop value"), [
            ("src/Help.jsx", before, before.replace("save", "wipeAll")),
            ("src/Help.tsx", "const A = () => <p>a // b</p>;<Btn onClick={save} />\n",
             "const A = () => <p>a // b</p>;<Btn onClick={wipeAll} />\n"),
        ])

    def test_f12_go_example_output(self):
        self.each(CODE, [
            ("src/x_test.go", 'package x\nimport "fmt"\nfunc Example() {\n\tfmt.Println("hi")\n\t// Output: hi\n}\n',
             'package x\nimport "fmt"\nfunc Example() {\n\tfmt.Println("hi")\n\t// Output: bye\n}\n'),
            ("src/x_test.go", 'package x\nfunc Example() {\n\tf()\n\t// Output:\n\t// hi\n}\n',
             'package x\nfunc Example() {\n\tf()\n\t// Output:\n\t// bye\n}\n'),
            ("src/x_test.go", 'package x\nfunc Example() {\n\tf()\n\t// Unordered output:\n\t// a\n}\n',
             'package x\nfunc Example() {\n\tf()\n\t// Unordered output:\n\t// b\n}\n'),
        ])


class TestReviewMarkup(ShapeCase):

    def test_f9_other_comment_endings(self):
        self.each(CODE, [
            ("web/a.html", "<p>a</p>\n<!-- a --!>\n<!-- b -->\n",
             "<p>a</p>\n<!-- a --!>\n<script>steal()</script>\n<!-- b -->\n"),
            ("web/a.html", "<p>a</p>\n<!--->\n<!-- end -->\n",
             '<p>a</p>\n<!--->\n<script src="https://x.example/e.js"></script>\n<!-- end -->\n'),
            ("web/a.html", "<p>a</p>\n<!-->\n<!-- end -->\n",
             "<p>a</p>\n<!-->\n<script>steal()</script>\n<!-- end -->\n"),
        ])

    def test_f9_raw_text_elements(self):
        cases = [("web/a.html", "<textarea><!-- </textarea> --></textarea>\n",
                  "<textarea><!-- </textarea><script>steal()</script> --></textarea>\n")]
        for tag in ("textarea", "title", "noscript", "xmp", "iframe", "noembed", "noframes", "TITLE"):
            cases.append(("web/a.html", "<%s><!-- a --></%s>\n" % (tag, tag), "<%s><!-- b --></%s>\n" % (tag, tag)))
        cases.append(("web/a.html", "<plaintext><!-- a -->\n", "<plaintext><!-- b -->\n"))
        self.each(CODE, cases)

    def test_f9_after_a_raw_text_element(self):
        self.each(("A", CO), [("web/a.html", "<textarea>x</textarea>\n<!-- a -->\n", "<textarea>x</textarea>\n<!-- b -->\n")])


class TestReview2Core(ShapeCase):

    def test_g1_an_apostrophe_inside_a_quoted_parameter_expansion(self):
        before = 'echo "${greet:-it\'s}"\n# don\'t panic\nf() { :; }\necho "a # b"; run 1\n'
        self.each(CODE, [("bin/a.sh", before, before.replace("run 1", "rm -rf ~/x")),
                         ("bin/a.zsh", before, before.replace("run 1", "rm -rf ~/x"))])

    def test_g4_a_yaml_tag_right_after_a_flow_bracket(self):
        self.each(CODE, [("ci/a.yml", 'k: [!!str "a # b", 1]\n', 'k: [!!str "a # b", 2]\n'),
                         ("ci/a.yml", 'k: {a: &x "a # b", b: 1}\n', 'k: {a: &x "a # b", b: 2}\n')])

    def test_g5_php_in_an_html_comment(self):
        self.each(CODE, [("web/a.html", "<body>\n<!-- note -->\n</body>\n", "<body>\n<!-- <?php echo 1; ?> -->\n</body>\n")])


class TestReview2Slash(ShapeCase):

    def test_g2_a_js_comment_holding_a_brace(self):
        self.each(CODE, [
            ("src/A.jsx", "export const A = () => (\n  <p>\n    Home // {page.title}\n  </p>\n);\n",
             "export const A = () => (\n  <p>\n    Home // {deleteAll()}\n  </p>\n);\n"),
            ("src/A.jsx", "export const A = () => <p>a /* {save()} */ b</p>;\n",
             "export const A = () => <p>a /* {wipe()} */ b</p>;\n"),
        ])

    def test_g3_a_comment_after_a_lone_slash_on_its_line(self):
        self.each(CODE, [
            ("src/a.js", 'x.split(/"/).join(" // "); run(1);\n', 'x.split(/"/).join(" // "); run(2);\n'),
            ("src/a.js", 'x.split(/"/).join(" /* "); run(1); /* x */\n', 'x.split(/"/).join(" /* "); run(2); /* x */\n'),
            ("src/a.ts", 'x.split(/"/).join(" // "); run(1);\n', 'x.split(/"/).join(" // "); run(2);\n'),
            ("src/a.swift", 'let r = #/"/#; let s = " // "; run(1)\n', 'let r = #/"/#; let s = " // "; run(2)\n'),
            # the safe side: a division before a trailing comment also falls back
            ("src/a.js", "a = b / c; // note\n", "a = b / c; // note 2\n"),
        ])

    def test_g3_other_slash_files_keep_a_comment_after_a_division(self):
        self.each(("A", CO), [("src/a.go", "a := b / c // note\n", "a := b / c // note 2\n"),
                            ("src/a.js", "// a / b\nrun();\n", "// a / c\nrun();\n")])


class TestReview3(ShapeCase):

    def test_h1_a_yaml_quote_after_a_flow_char_open_at_the_line_end(self):
        self.each(CODE, [
            ("ci/a.yml", 'msg: see [!x "a # note\nk: ["b # c", 1]\n', 'msg: see [!x "a # note\nk: ["b # c", 2]\n'),
            ("ci/a.yml", 'msg: see, "a # note\nk: ["b # c", 1]\n', 'msg: see, "a # note\nk: ["b # c", 2]\n'),
        ])

    def test_h1_a_closed_flow_quote_still_works(self):
        self.each(("A", CO), [("ci/a.yml", 'k: ["b # c", 1] # x\n', 'k: ["b # c", 1] # y\n')])

    def test_h2_a_lone_slash_then_a_string_that_runs_past_the_line(self):
        self.each(CODE, [
            ("src/a.js", "const parts = s.split(/`/);\nconst t = `a // b`; run(1);\n",
             "const parts = s.split(/`/);\nconst t = `a // b`; run(2);\n"),
            ("src/a.ts", "const parts = s.split(/`/);\nconst t = `a // b`; run(1);\n",
             "const parts = s.split(/`/);\nconst t = `a // b`; run(2);\n"),
        ])

    def test_h2_a_template_after_a_division_on_another_line_is_fine(self):
        self.each(("A", CO), [("src/a.js", "const h = w / 2;\nconst t = `a\nb`; // x\n", "const h = w / 2;\nconst t = `a\nb`; // y\n")])
