"""Failing tests for the city's Balance: 5 kinds of code, eras, the era show,
and versioned assets (requirements/city.md, "Balance"). Approved mock:
mock/city-balance-mock.html (2D stand-in; the real page is the 3D Kenney
page). Page side: tests/test_agent_city_page.py, the Balance classes.

CONTRACT (bin/agent_city.py, Python standard library only)

  Constants  KINDS = ("build", "rules", "beauty", "knowledge", "infra")
             KIND_ZH = {build: 建设, rules: 规则, beauty: 美化, knowledge: 知识,
               infra: 基建}
             ERAS = ("village", "town", "city"), TOWN_LINES = 2000,
             CITY_LINES = 20000, SHOW_SEC = 60

  file_kind(path, rules=()) -> one of KINDS or None
        None when counts_as_code(path) is False: binaries, vendor, lock,
        generated files never count, whatever a rule says.
        Then the first (glob, kind) of RULES whose glob matches the path
        (fnmatch.fnmatchcase, "*" crosses "/"); kind "none" -> None.
        Then the built-in rules, first match wins:
          rules      a folder named test tests __tests__ spec specs e2e
                     integration_test cypress playwright qa; or a file named
                     test_*.x, *_test.x, *.test.x, *.spec.x, *_spec.rb,
                     *Test.x / *Tests.x (x = any extension)
          infra      under .github/ .circleci/ .gitlab/; Makefile, Jenkinsfile,
                     Procfile, Dockerfile*, docker-compose*, .gitlab-ci.yml;
                     .sh .bash .zsh .ps1 .bat .sql .tf .yml .yaml .toml .ini
                     .cfg .conf; a folder named migrations migrate schema
                     prisma scripts ci deploy infra; a .json at the repo root
          knowledge  .md .mdx .rst .adoc
          beauty     .jsx .tsx .vue .svelte .html .css .scss .sass .less .styl;
                     a source file under a folder named components widgets ui
                     views screens pages styles theme
          build      any other source file: .py .js .mjs .cjs .ts .go .rs
                     .java .kt .kts .swift .dart .rb .php .c .h .cc .cpp .hpp
                     .cs .m .mm .scala .lua .ex .exs .clj .hs .erl .r .jl .fs
                     .groovy .pl
          None       everything else (data .json below the root, .txt, ...)

  parse_rules(text) -> {"rules": [(glob, kind)], "na": [kinds], "bad": [line
        numbers, 1-based]}. One rule per line: "<glob> = <kind>" (kind in
        KINDS or "none") or "na = <kind>[, <kind> ...]". Blank lines and
        "# ..." are skipped. Anything else is bad: listed, never silent.

  score_balance(files, rules_text="", reuse=None) -> {"kinds", "files", "bad"}
        files: iterable of (path, added lines). Each file gets file_kind.
        "files": {kind: sorted paths} for all 5 kinds. "bad": parse_rules bad.
        "kinds": {kind: {"state", "value", "n", "text"}} for all 5 kinds.
          n = files of that kind. state healthy | low | missing | na.
          A kind listed under na -> "na", text "这个仓库不用这一类".
          n == 0 (and not na) -> "missing", text "还没有".
          Components = beauty files with .jsx .tsx .vue .svelte .html, or any
          beauty source file under components widgets ui views screens pages.
          Source files = build files + components.
          build      value = lines of build files; healthy when > 0.
                     text "<lines with , thousands> 行代码".
          rules      value = share (0..1) of source files with a matching
                     test: a rules file whose name, without extension and
                     without test_ / _test / _spec / .test / .spec / Test /
                     Tests, lower-case with - as _, equals the source file's
                     name (no extension, same normalising) or starts with it
                     plus "_". healthy share >= 0.5, or no source files at
                     all; else low. text "<round(share*100)>% 源文件有测试".
          beauty     value = component count. reuse: {component path: files
                     that use it} (None -> 0 each). healthy when components >=
                     max(3, ceil(build files / 20)) and mean reuse >= 2.0;
                     else low. text "<n> 个组件，平均复用 <mean, 1 decimal> 次".
          knowledge  value = share of modules with a doc. A module = the
                     folder of a source file after dropping leading src lib
                     app apps packages modules internal pkg cmd services
                     folders: the first folder left (its full path), or the
                     dropped path itself when none is left, or "." for a root
                     file. A module has a doc when a knowledge file is inside
                     its folder, or a knowledge file's name (no extension,
                     lower-case) equals the module's own folder name; "." has
                     one when a knowledge file sits at the root. healthy share
                     >= 0.5, or no modules; else low.
                     text "<with doc>/<modules> 个模块有文档".
          infra      value = file count. healthy when n >= max(2, ceil(build
                     files / 25)); else low. text "<n> 个文件".

  balance_of(identity, rules_text="") -> the same shape, from git only:
        `git --git-dir=<identity> diff --numstat <empty tree> HEAD` for paths
        and lines (binary "-" rows never count), and one `git grep` over HEAD
        for component reuse (a component's name = its file name without
        extension; index.* uses its folder's name; files that use it = other
        tracked files that contain that name as a word). Not a git dir, no
        commit, a git error or timeout -> every kind "missing", never raises.
        Never runs anything but git.

  era_for(peak, kinds, current="village") -> era. kinds = the "kinds" dict.
        missing = any state "missing"; ok(k) = state healthy or na.
        city when peak >= CITY_LINES, nothing missing, ok(rules), ok(beauty);
        town when peak >= TOWN_LINES and nothing missing; else village.
        Never earlier than CURRENT (eras never go back). {} kinds -> CURRENT.
  next_needs(peak, kinds, era) -> what the next era still needs, Chinese
        words in this order: "规模" when the size is short, then KIND_ZH of
        each kind in KINDS order that blocks it (village: missing; town:
        missing, or rules/beauty not ok). city -> []. {} kinds -> [].

  World record per territory (world.json, "v" stays 1): "era" (village at
        birth), "balance" (the "kinds" dict of the last count, {} before),
        "rules_bad" (bad line numbers of the last count), "show" while an era
        show is waiting or running: {"from", "to", "start"}; start = the
        time.time() the first page saw it, None while no page was open.
  layout view per territory adds "era", "balance", "next" (next_needs of
        peak, balance, era) and "rules_note" ("" or a Chinese line naming the
        rules file and its bad line numbers).

  CityState(..., balance_fn=FN): FN(identity, rules_text) -> the
        balance_of shape; default balance_of. recount(now) calls it next to
        count_fn (same due rule, outside the lock), with the text of
        <folder of world.json>/rules/<repo name>.conf ("" when missing or no
        world path). Then stores balance and rules_bad, keeps the file lists
        in memory, and sets the era by era_for(peak, balance, era). A raised
        era: "show" = {"from": old, "to": new, "start": now or None}; when a
        page is open an {"type": "era", "terr", "from", "to", "left": 60}
        event goes out BEFORE the world event; world.json saved at once.
        The /events snapshot carries "shows": [{"terr", "from", "to",
        "left"}] for every show with time left (left = SHOW_SEC - seconds
        since start, > 0); a waiting show (start None) starts when that
        snapshot is sent, and is saved. A finished show is never sent again,
        after any restart.
  GET /api/balance?terr=<territory id>&kind=<kind>  (X-City-Token required,
        403 without) -> 200 {"terr", "kind", "state", "files" (at most 500
        paths), "total", "rules" (the rules file path)}. Checked in this
        order: token 403, unknown kind 400, unknown territory 404. After a restart (no list in memory) the list
        is counted once for that territory, then kept.

  Assets: asset_version(folder) -> a hex string (>= 8 chars) that changes
        when a file is added, removed or changed (size or mtime), and is the
        same otherwise. The served page has __CITY_ASSET_V__ replaced by it.
        GET /assets/<path>?v=<that version> -> Cache-Control
        "max-age=31536000, immutable"; without ?v= or with another value ->
        "no-cache". (Was max-age=86400: an update kept old models a day.)

  demo_world() territories carry era and balance too: at least one village
        with a missing kind and a non-empty "next", one town, one city.

  No test here touches the real ~/.claude/agent-city: every server gets
  AGENT_CITY_HOME and HOME in a temp folder.
"""

import http.client
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_city as ac  # noqa: E402
from test_agent_city_server import ServerCase, wait_for  # noqa: E402
from test_agent_city_world import gline, make_repo, plans, world_of  # noqa: E402


def kinds_of(**states):
    """{kind: {"state": ...}} with every kind healthy unless named."""
    out = {k: {"state": "healthy", "value": 1, "n": 1, "text": ""} for k in ac.KINDS}
    for k, st in states.items():
        out[k] = dict(out[k], state=st)
    return out


def score(files, rules_text="", reuse=None):
    return ac.score_balance([(p, n) for p, n in files], rules_text, reuse)


# ---------------------------------------------------------------------------
# What kind is a file
# ---------------------------------------------------------------------------

class TestFileKind(unittest.TestCase):
    CASES = {
        "rules": ["tests/test_app.py", "test/foo.dart", "src/__tests__/a.js", "spec/models/user_spec.rb",
                  "e2e/login.spec.ts", "src/Button.test.tsx", "src/util_test.go", "app/src/FooTest.java",
                  "Sources/AppTests.swift", "qa/release-checklist.md", "cypress/e2e/a.cy.js",
                  "pkg/x/y_test.go", "integration_test/app_test.dart", "tests/fixtures/data.json"],
        "infra": [".github/workflows/ci.yml", ".circleci/config.yml", "Makefile", "Dockerfile",
                  "Dockerfile.dev", "docker-compose.yml", "scripts/seed.py", "bin/run.sh", "deploy/k8s.yaml",
                  "migrations/0001_init.sql", "db/schema.sql", "prisma/schema.prisma", "pyproject.toml",
                  "setup.cfg", "package.json", "tsconfig.json", "infra/main.tf", ".gitlab-ci.yml"],
        "knowledge": ["README.md", "docs/modules/auth.md", "requirements/city.md", "guide.rst", "a/b.mdx",
                      "manual.adoc"],
        "beauty": ["src/components/Button.tsx", "web/App.vue", "ui/Card.svelte", "bin/agent-city.html",
                   "src/styles/theme.css", "a.scss", "lib/widgets/money_input.dart", "src/screens/home.js",
                   "app/views/page.py", "Nav.jsx"],
        "build": ["src/app.py", "lib/money.dart", "server.go", "src/main.rs", "app/Main.kt", "x.swift",
                  "a.rb", "b.php", "c.c", "d.h", "e.cpp", "f.cs", "g.java", "index.ts", "tool.mjs"],
    }
    NONE = ["notes.txt", "data/cities.json", "LICENSE", "img/logo.png", "vendor/lib/a.py",
            "node_modules/x/index.js", "dist/app.js", "package-lock.json", "a.min.js", "x.generated.ts",
            "tests/snap.png", "docs/diagram.svg"]

    def test_built_in_rules(self):
        for kind, paths in self.CASES.items():
            for path in paths:
                with self.subTest(path=path):
                    self.assertEqual(ac.file_kind(path), kind)

    def test_what_never_counts(self):
        for path in self.NONE:
            with self.subTest(path=path):
                self.assertIsNone(ac.file_kind(path))

    def test_a_repo_rule_wins_over_the_built_in_rules(self):
        rules = ac.parse_rules("tests/fixtures/** = none\nlib/ui/*.dart = beauty\nsrc/*.py = infra\n")["rules"]
        self.assertIsNone(ac.file_kind("tests/fixtures/big/data.py", rules))
        self.assertEqual(ac.file_kind("lib/ui/card.dart", rules), "beauty")
        self.assertEqual(ac.file_kind("src/deep/job.py", rules), "infra", "* crosses /")
        self.assertEqual(ac.file_kind("tests/test_a.py", rules), "rules", "no rule matched: built-in")

    def test_first_matching_rule_wins(self):
        rules = ac.parse_rules("*.py = infra\nsrc/*.py = beauty\n")["rules"]
        self.assertEqual(ac.file_kind("src/a.py", rules), "infra")

    def test_a_rule_never_makes_vendor_or_binaries_count(self):
        rules = ac.parse_rules("vendor/** = build\n*.png = beauty\n*.min.js = build\n")["rules"]
        for path in ("vendor/x/a.py", "img/a.png", "a.min.js"):
            with self.subTest(path=path):
                self.assertIsNone(ac.file_kind(path, rules))


class TestParseRules(unittest.TestCase):
    def test_rules_na_comments_and_bad_lines(self):
        text = ("# my repo\n"
                "\n"
                "tests/fixtures/** = none\n"
                "   scripts/*.py   =   build  \n"
                "na = knowledge\n"
                "na = beauty, infra\n"
                "this is not a rule\n"
                "x/** = weird\n"
                "na = nothing\n")
        got = ac.parse_rules(text)
        self.assertEqual(got["rules"], [("tests/fixtures/**", "none"), ("scripts/*.py", "build")])
        self.assertEqual(sorted(got["na"]), ["beauty", "infra", "knowledge"])
        self.assertEqual(got["bad"], [7, 8, 9])

    def test_empty(self):
        self.assertEqual(ac.parse_rules(""), {"rules": [], "na": [], "bad": []})


# ---------------------------------------------------------------------------
# Healthy / low / missing
# ---------------------------------------------------------------------------

class TestScore(unittest.TestCase):
    def test_shape_and_day_zero(self):
        got = score([])
        self.assertEqual(set(got), {"kinds", "files", "bad"})
        self.assertEqual(set(got["kinds"]), set(ac.KINDS))
        self.assertEqual(set(got["files"]), set(ac.KINDS))
        for k in ac.KINDS:
            with self.subTest(kind=k):
                self.assertEqual(got["kinds"][k]["state"], "missing")
                self.assertEqual(got["kinds"][k]["n"], 0)
                self.assertEqual(got["kinds"][k]["text"], "还没有")
                self.assertEqual(got["files"][k], [])

    def test_constants(self):
        self.assertEqual(ac.KINDS, ("build", "rules", "beauty", "knowledge", "infra"))
        self.assertEqual(ac.KIND_ZH, {"build": "建设", "rules": "规则", "beauty": "美化",
                                      "knowledge": "知识", "infra": "基建"})
        self.assertEqual(ac.ERAS, ("village", "town", "city"))
        self.assertEqual((ac.TOWN_LINES, ac.CITY_LINES, ac.SHOW_SEC), (2000, 20000, 60))

    def test_build_is_measured_in_lines(self):
        got = score([("src/a.py", 1200), ("src/b.py", 34), ("tests/test_a.py", 900), ("README.md", 50)])
        b = got["kinds"]["build"]
        self.assertEqual((b["state"], b["value"], b["n"]), ("healthy", 1234, 2))
        self.assertEqual(b["text"], "1,234 行代码")
        self.assertEqual(got["files"]["build"], ["src/a.py", "src/b.py"])

    def test_rules_share_of_source_files_with_a_test(self):
        src = [("src/a.py", 10), ("src/b.py", 10), ("src/c.py", 10), ("src/d.py", 10)]
        low = score(src + [("tests/test_a.py", 5)])["kinds"]["rules"]
        self.assertEqual(low["state"], "low")
        self.assertAlmostEqual(low["value"], 0.25)
        self.assertEqual(low["text"], "25% 源文件有测试")
        healthy = score(src + [("tests/test_a.py", 5), ("tests/b_test.py", 5)])["kinds"]["rules"]
        self.assertEqual(healthy["state"], "healthy", "2 of 4 = 50%")
        self.assertAlmostEqual(healthy["value"], 0.5)

    def test_test_names_match_in_every_style(self):
        pairs = [("lib/money_input.dart", "test/money_input_test.dart"),
                 ("src/Button.tsx", "src/Button.test.tsx"),
                 ("src/item.service.ts", "tests/item.service.spec.ts"),
                 ("app/Foo.java", "app/FooTest.java"),
                 ("bin/agent_city.py", "tests/test_agent_city_world.py"),
                 ("bin/agent-conf.py", "tests/test_agent_conf.py"),
                 ("app/user.rb", "spec/user_spec.rb")]
        for source, test in pairs:
            with self.subTest(source=source, test=test):
                got = score([(source, 10), (test, 10)])["kinds"]["rules"]
                self.assertEqual(got["state"], "healthy")
                self.assertAlmostEqual(got["value"], 1.0)

    def test_a_test_for_another_file_does_not_count(self):
        got = score([("src/agent.py", 10), ("tests/test_agents_list.py", 10)])["kinds"]["rules"]
        self.assertAlmostEqual(got["value"], 0.0)
        self.assertEqual(got["state"], "low", "tests exist, so rules is there, only low")

    def test_qa_docs_alone_are_low_rules(self):
        got = score([("src/a.py", 10), ("qa/checklist.md", 10)])["kinds"]["rules"]
        self.assertEqual((got["state"], got["n"]), ("low", 1))

    def test_rules_with_no_source_files_is_healthy(self):
        self.assertEqual(score([("tests/test_a.py", 3)])["kinds"]["rules"]["state"], "healthy")

    def test_beauty_count_and_reuse(self):
        comps = ["src/components/Button.tsx", "src/components/Table.tsx", "src/components/Modal.tsx"]
        base = [(c, 20) for c in comps] + [("src/styles/theme.css", 40), ("src/app.ts", 100)]
        good = score(base, reuse={comps[0]: 4, comps[1]: 2, comps[2]: 1})["kinds"]["beauty"]
        self.assertEqual((good["state"], good["value"], good["n"]), ("healthy", 3, 4))
        self.assertEqual(good["text"], "3 个组件，平均复用 2.3 次")
        little = score(base, reuse={comps[0]: 1, comps[1]: 1, comps[2]: 1})["kinds"]["beauty"]
        self.assertEqual(little["state"], "low", "mean reuse 1.0 < 2")
        few = score(base[:2] + base[3:], reuse={comps[0]: 9, comps[1]: 9})["kinds"]["beauty"]
        self.assertEqual(few["state"], "low", "2 components < 3")
        css_only = score([("site.css", 10), ("src/app.ts", 10)])["kinds"]["beauty"]
        self.assertEqual((css_only["state"], css_only["value"]), ("low", 0))
        no_reuse = score(base)["kinds"]["beauty"]
        self.assertEqual(no_reuse["state"], "low", "reuse None counts as 0")

    def test_beauty_needs_more_components_in_a_big_repo(self):
        comps = ["src/components/C%d.tsx" % i for i in range(3)]
        build = [("src/m%d.ts" % i, 10) for i in range(100)]
        got = score([(c, 5) for c in comps] + build, reuse={c: 5 for c in comps})["kinds"]["beauty"]
        self.assertEqual(got["state"], "low", "100 build files need max(3, 5) = 5 components")

    def test_knowledge_share_of_modules_with_a_doc(self):
        files = [("src/sales/invoice.ts", 10), ("src/stock/item.ts", 10), ("src/auth/token.ts", 10),
                 ("src/report/pnl.ts", 10), ("docs/sales.md", 5), ("src/stock/README.md", 5)]
        got = score(files)["kinds"]["knowledge"]
        self.assertEqual(got["state"], "healthy", "sales (docs/sales.md) + stock (its README) = 2/4")
        self.assertAlmostEqual(got["value"], 0.5)
        self.assertEqual(got["text"], "2/4 个模块有文档")
        low = score(files[:4] + [("docs/sales.md", 5)])["kinds"]["knowledge"]
        self.assertEqual((low["state"], low["text"]), ("low", "1/4 个模块有文档"))

    def test_modules_skip_container_folders(self):
        files = [("src/modules/sales/a.ts", 1), ("src/modules/sales/b.ts", 1), ("src/app.ts", 1),
                 ("main.py", 1), ("bin/tool.py", 1), ("README.md", 1)]
        got = score(files)["kinds"]["knowledge"]
        self.assertEqual(got["text"], "1/4 个模块有文档", "modules: src/modules/sales, src, ., bin; README covers '.'")

    def test_knowledge_with_no_modules_is_healthy(self):
        self.assertEqual(score([("README.md", 3)])["kinds"]["knowledge"]["state"], "healthy")

    def test_infra_file_count_against_build(self):
        build = [("src/m%d.py" % i, 10) for i in range(100)]
        one = score(build[:10] + [("Makefile", 5)])["kinds"]["infra"]
        self.assertEqual((one["state"], one["value"], one["text"]), ("low", 1, "1 个文件"))
        two = score(build[:10] + [("Makefile", 5), ("ci.yml", 5)])["kinds"]["infra"]
        self.assertEqual(two["state"], "healthy")
        big = score(build + [("Makefile", 5), ("ci.yml", 5), ("a.sh", 1)])["kinds"]["infra"]
        self.assertEqual(big["state"], "low", "100 build files need max(2, 4) = 4")

    def test_not_applicable(self):
        got = score([("src/a.py", 10)], "na = knowledge, beauty\n")
        for k in ("knowledge", "beauty"):
            with self.subTest(kind=k):
                self.assertEqual(got["kinds"][k]["state"], "na")
                self.assertEqual(got["kinds"][k]["text"], "这个仓库不用这一类")
        self.assertEqual(got["kinds"]["rules"]["state"], "missing")

    def test_rules_text_changes_the_kind_and_reports_bad_lines(self):
        files = [("src/a.py", 10), ("tools/gen.py", 10)]
        self.assertEqual(score(files)["files"]["infra"], [])
        got = score(files, "tools/** = infra\noops\n")
        self.assertEqual(got["files"]["infra"], ["tools/gen.py"])
        self.assertEqual(got["files"]["build"], ["src/a.py"])
        self.assertEqual(got["bad"], [2])

    def test_files_that_never_count_are_in_no_list(self):
        got = score([("vendor/a.py", 10), ("logo.png", 0), ("notes.txt", 3)])
        self.assertEqual(sum(len(v) for v in got["files"].values()), 0)


# ---------------------------------------------------------------------------
# From a real git repo
# ---------------------------------------------------------------------------

class TestBalanceOf(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_bal_")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_a_repo_with_every_kind(self):
        ident = make_repo(os.path.join(self.base, "shop"), {
            "src/app.py": "print(1)\n" * 30,
            "src/money.py": "x = 1\n" * 10,
            "tests/test_app.py": "assert 1\n" * 5,
            "src/components/Button.tsx": "export const Button = 1\n",
            "src/components/Card/index.tsx": "export const Card = 1\n",
            "src/pages/Home.tsx": "import { Button } from '../components/Button'\nimport Card from '../components/Card'\n<Button/>\n",
            "src/pages/About.tsx": "import { Button } from '../components/Button'\nconst ButtonBar = 1\n",
            "README.md": "# shop\n",
            ".github/workflows/ci.yml": "on: push\n",
            "logo.png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00",
        })
        got = ac.balance_of(ident)
        self.assertEqual(got["kinds"]["build"]["value"], 40)
        self.assertEqual(got["files"]["rules"], ["tests/test_app.py"])
        self.assertEqual(got["files"]["infra"], [".github/workflows/ci.yml"])
        self.assertEqual(got["files"]["knowledge"], ["README.md"])
        self.assertEqual(len(got["files"]["beauty"]), 4)
        self.assertNotIn("logo.png", sum(got["files"].values(), []))
        self.assertAlmostEqual(got["kinds"]["rules"]["value"], 1 / 6, places=3,
                               msg="source = 2 build + 4 components; only app.py has a test")
        # reuse: Button used by Home and About (2), Card (index.tsx -> folder name) by Home (1),
        # Home 0, About 0 -> mean 0.75; ButtonBar is not the word Button
        self.assertEqual(got["kinds"]["beauty"]["text"], "4 个组件，平均复用 0.8 次")

    def test_rules_text_is_used(self):
        ident = make_repo(os.path.join(self.base, "r"), {"src/a.py": "1\n", "tools/gen.py": "1\n"})
        got = ac.balance_of(ident, "tools/** = infra\nna = knowledge\n")
        self.assertEqual(got["files"]["infra"], ["tools/gen.py"])
        self.assertEqual(got["kinds"]["knowledge"]["state"], "na")

    def test_not_a_repo_never_raises(self):
        for ident in ("/nope/.git", os.path.join(self.base, "empty"), "dir:shop"):
            with self.subTest(ident=ident):
                got = ac.balance_of(ident)
                self.assertEqual({v["state"] for v in got["kinds"].values()}, {"missing"})

    def test_runs_git_only(self):
        import inspect
        src = inspect.getsource(ac.balance_of)
        for name in ("os.system", "shell=True", "Popen", "unittest", "pytest", "npm", "make"):
            with self.subTest(name=name):
                self.assertNotIn(name, src)


# ---------------------------------------------------------------------------
# Eras and the sign
# ---------------------------------------------------------------------------

class TestEras(unittest.TestCase):
    def test_village_to_town_needs_size_and_nothing_missing(self):
        self.assertEqual(ac.era_for(1999, kinds_of()), "village", "size short")
        self.assertEqual(ac.era_for(2000, kinds_of(rules="missing")), "village", "a kind missing")
        self.assertEqual(ac.era_for(2000, kinds_of(rules="low", beauty="low")), "town")
        self.assertEqual(ac.era_for(2000, kinds_of(knowledge="na")), "town", "na is never missing")

    def test_town_to_city_needs_size_and_rules_and_beauty_healthy(self):
        self.assertEqual(ac.era_for(19999, kinds_of()), "town")
        self.assertEqual(ac.era_for(20000, kinds_of(rules="low")), "town")
        self.assertEqual(ac.era_for(20000, kinds_of(beauty="low")), "town")
        self.assertEqual(ac.era_for(20000, kinds_of(knowledge="low", infra="low")), "city")
        self.assertEqual(ac.era_for(20000, kinds_of(beauty="na")), "city")
        self.assertEqual(ac.era_for(500000, kinds_of(infra="missing")), "village", "size alone never moves an era")

    def test_eras_never_go_back(self):
        self.assertEqual(ac.era_for(10, kinds_of(rules="missing"), "town"), "town")
        self.assertEqual(ac.era_for(10, kinds_of(), "city"), "city")
        self.assertEqual(ac.era_for(50000, kinds_of(), "village"), "city", "a jump is allowed")
        self.assertEqual(ac.era_for(50000, {}, "town"), "town", "no count yet: no change")

    def test_next_needs(self):
        self.assertEqual(ac.next_needs(4200, kinds_of(rules="missing"), "village"), ["规则"])
        self.assertEqual(ac.next_needs(100, kinds_of(rules="missing", infra="missing"), "village"),
                         ["规模", "规则", "基建"])
        self.assertEqual(ac.next_needs(9000, kinds_of(beauty="low"), "town"), ["规模", "美化"])
        self.assertEqual(ac.next_needs(30000, kinds_of(rules="low", knowledge="missing"), "town"), ["规则", "知识"])
        self.assertEqual(ac.next_needs(30000, kinds_of(), "city"), [])
        self.assertEqual(ac.next_needs(30000, {}, "village"), [])


# ---------------------------------------------------------------------------
# CityState: counted with the lines, era raised, show recorded once
# ---------------------------------------------------------------------------

class StateCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="city_balstate_")
        self.home = os.path.join(self.base, "cityhome")
        self.path = os.path.join(self.home, "world.json")
        self.lines = {"/a/.git": 12000}
        self.kinds = {"/a/.git": kinds_of(rules="missing")}
        self.calls = []

        def count(identity):
            return self.lines.get(identity, 0)

        def balance(identity, rules_text):
            self.calls.append((identity, rules_text))
            k = self.kinds.get(identity, {kk: {"state": "missing", "value": 0, "n": 0, "text": "还没有"}
                                          for kk in ac.KINDS})
            return {"kinds": k, "files": {kk: ["%s/%s.x" % (kk, identity)] for kk in ac.KINDS}, "bad": []}

        self.state = self.make(count, balance)

    def make(self, count, balance):
        return ac.CityState(decisions_path=os.path.join(self.base, "d.jsonl"), world_path=self.path,
                            plans=plans(), count_fn=count, balance_fn=balance)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def feed(self, repo, now):
        self.state.feed_line({"ev": "PostToolUse", "sid": "s1", "aid": "", "at": "", "tool": "Read", "nt": "",
                              "proj": "p", "role": "worker", "desc": "", "sub": "", "q": "", "klen": "",
                              "repo": repo, "kind": ""}, now)

    def terr(self, ident="/a/.git"):
        return self.state.world["territories"][ident]

    def view_terr(self, ident="/a/.git"):
        with self.state.lock:
            view = self.state._view()
        return next(t for t in view["territories"] if t["id"] == ac.territory_id(ident))


class TestRecountBalance(StateCase):
    def test_balance_is_counted_with_the_lines(self):
        self.feed("/a/.git", 1000.0)
        self.assertEqual(self.calls, [], "feed_line never counts")
        self.assertEqual(self.state.recount(1001.0), 1)
        self.assertEqual(self.calls, [("/a/.git", "")])
        self.assertEqual(self.terr()["balance"]["rules"]["state"], "missing")
        self.feed("/a/.git", 1010.0)
        self.state.recount(1100.0)
        self.assertEqual(len(self.calls), 1, "same cost rule as the lines: at most every 300 s")

    def test_view_carries_era_balance_next(self):
        self.feed("/a/.git", 1000.0)
        self.state.recount(1001.0)
        t = self.view_terr()
        self.assertEqual(t["era"], "village")
        self.assertEqual(t["balance"]["rules"]["state"], "missing")
        self.assertEqual(t["next"], ["规则"])
        self.assertEqual(t["rules_note"], "")

    def test_a_new_territory_has_empty_balance(self):
        self.feed("/b/.git", 1000.0)
        t = self.view_terr("/b/.git")
        self.assertEqual((t["era"], t["balance"], t["next"]), ("village", {}, []))

    def test_the_rules_file_is_read_per_repo(self):
        os.makedirs(os.path.join(self.home, "rules"))
        with open(os.path.join(self.home, "rules", "a.conf"), "w") as fh:
            fh.write("tools/** = infra\n")
        self.feed("/work/a/.git", 1000.0)
        self.state.recount(1001.0)
        self.assertEqual(self.calls, [("/work/a/.git", "tools/** = infra\n")])

    def test_bad_rules_lines_are_shown_never_silent(self):
        def balance(identity, rules_text):
            return {"kinds": kinds_of(), "files": {k: [] for k in ac.KINDS}, "bad": [2, 5]}
        self.state = self.make(lambda i: 100, balance)
        self.feed("/work/shop/.git", 1000.0)
        self.state.recount(1001.0)
        note = self.view_terr("/work/shop/.git")["rules_note"]
        self.assertIn("shop.conf", note)
        self.assertIn("2", note)
        self.assertIn("5", note)

    def test_saved_and_back_after_a_restart(self):
        self.feed("/a/.git", 1000.0)
        self.state.recount(1001.0)
        with open(self.path) as fh:
            saved = json.load(fh)
        self.assertEqual(saved["v"], 1)
        self.assertEqual(saved["territories"]["/a/.git"]["balance"]["rules"]["state"], "missing")
        again = self.make(lambda i: 0, lambda i, r: self.fail("a restart counts nothing"))
        self.assertEqual(again.world["territories"]["/a/.git"]["balance"]["rules"]["state"], "missing")


class TestEraChange(StateCase):
    def raise_era(self):
        self.feed("/a/.git", 1000.0)
        self.state.recount(1001.0)
        self.assertEqual(self.terr()["era"], "village")
        self.kinds["/a/.git"] = kinds_of(rules="low")
        self.feed("/a/.git", 1400.0)
        self.state.recount(1401.0)

    def test_an_era_is_raised_and_recorded_with_a_waiting_show(self):
        self.raise_era()
        t = self.terr()
        self.assertEqual(t["era"], "town")
        self.assertEqual(t["show"], {"from": "village", "to": "town", "start": None},
                         "no page open: the show waits for one")
        with open(self.path) as fh:
            self.assertEqual(json.load(fh)["territories"]["/a/.git"]["show"]["to"], "town")

    def test_the_first_page_starts_a_waiting_show_once(self):
        self.raise_era()
        t0 = time.time()
        client = self.state.add_client()
        snap = json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1])
        self.assertEqual(len(snap["shows"]), 1)
        show = snap["shows"][0]
        self.assertEqual((show["terr"], show["from"], show["to"]), (ac.territory_id("/a/.git"), "village", "town"))
        self.assertGreater(show["left"], 55)
        self.assertLessEqual(show["left"], 60)
        start = self.terr()["show"]["start"]
        self.assertIsNotNone(start)
        self.assertGreaterEqual(start, t0 - 1)
        with open(self.path) as fh:
            self.assertEqual(json.load(fh)["territories"]["/a/.git"]["show"]["start"], start, "saved at once")

    def test_a_finished_show_is_never_sent_again(self):
        self.raise_era()
        self.state.add_client()
        self.terr()["show"]["start"] = time.time() - 61
        ac.save_world(self.path, self.state.world)
        again = self.make(lambda i: 0, lambda i, r: {"kinds": {}, "files": {}, "bad": []})
        client = again.add_client()
        snap = json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1])
        self.assertEqual(snap["shows"], [])
        self.assertEqual(again.world["territories"]["/a/.git"]["era"], "town", "era kept")

    def test_a_page_opened_mid_show_joins_it(self):
        self.raise_era()
        self.state.add_client()
        self.terr()["show"]["start"] = time.time() - 20
        client = self.state.add_client()
        snap = json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1])
        self.assertTrue(38 <= snap["shows"][0]["left"] <= 40.5)

    def test_era_event_comes_before_the_world_event(self):
        self.feed("/a/.git", 1000.0)
        self.state.recount(1001.0)
        client = self.state.add_client()
        client.queue.get_nowait()
        self.kinds["/a/.git"] = kinds_of(rules="low")
        self.feed("/a/.git", 1400.0)
        self.state.recount(1401.0)
        types = []
        while not client.queue.empty():
            msg = json.loads(client.queue.get_nowait().decode("utf-8").split("data:", 1)[1])
            types.append(msg.get("type"))
            if msg.get("type") == "era":
                self.assertEqual((msg["terr"], msg["from"], msg["to"], msg["left"]),
                                 (ac.territory_id("/a/.git"), "village", "town", 60))
        self.assertIn("era", types)
        self.assertIn("world", types)
        self.assertLess(types.index("era"), types.index("world"))
        self.assertIsNotNone(self.terr()["show"]["start"], "a page was open: the show starts now")

    def test_no_show_without_an_era_change(self):
        self.feed("/a/.git", 1000.0)
        self.state.recount(1001.0)
        self.assertNotIn("show", self.terr())
        self.feed("/a/.git", 1400.0)
        self.state.recount(1401.0)
        self.assertNotIn("show", self.terr())

    def test_an_era_never_goes_back(self):
        self.raise_era()
        self.kinds["/a/.git"] = kinds_of(rules="missing", beauty="missing")
        self.lines["/a/.git"] = 10
        self.feed("/a/.git", 1800.0)
        self.state.recount(1801.0)
        self.assertEqual(self.terr()["era"], "town")
        self.assertEqual(self.terr()["show"]["to"], "town", "no new show")


# ---------------------------------------------------------------------------
# Server: /api/balance, versioned assets, demo world
# ---------------------------------------------------------------------------

class BalanceServerCase(ServerCase):
    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.base, "cityhome")
        self.world = os.path.join(self.home, "world.json")
        self.repo = make_repo(os.path.join(self.base, "shop"), {
            "src/app.py": "x\n" * 50, "tests/test_app.py": "x\n", "README.md": "x\n", "tools/gen.py": "x\n"})

    def start(self, *extra, wait=True):
        return super().start(*(list(extra) or ["--idle-sec", "60", "--world", self.world]), wait=wait)

    def token(self):
        with open(os.path.join(self.dir, "token")) as fh:
            return fh.read().strip()

    def api(self, path, token=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path, headers={"X-City-Token": self.token()} if token else {})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, (json.loads(body) if body.strip().startswith(b"{") else body)

    def counted(self, client):
        self.append(gline("UserPromptSubmit", sid="g1", repo=self.repo))
        return wait_for(lambda: [e for e in client.events("world")
                                 if e["world"]["territories"] and e["world"]["territories"][0].get("balance")],
                        timeout=20)


class TestBalanceApi(BalanceServerCase):
    def test_file_list_of_a_kind(self):
        self.start()
        client = self.sse()
        self.assertTrue(self.counted(client), "balance never counted")
        terr = ac.territory_id(self.repo)
        status, body = self.api("/api/balance?terr=%s&kind=rules" % terr)
        self.assertEqual(status, 200)
        self.assertEqual((body["terr"], body["kind"], body["state"]), (terr, "rules", "healthy"))
        self.assertEqual(body["files"], ["tests/test_app.py"])
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["rules"], os.path.join(self.home, "rules", "shop.conf"))

    def test_guarded(self):
        self.start()
        terr = ac.territory_id(self.repo)
        self.assertEqual(self.api("/api/balance?terr=%s&kind=rules" % terr, token=False)[0], 403)
        self.assertEqual(self.api("/api/balance?terr=%s&kind=bogus" % terr)[0], 400)
        self.assertEqual(self.api("/api/balance?terr=ffffffff&kind=rules")[0], 404)

    def test_a_rules_line_changes_a_classification(self):
        os.makedirs(os.path.join(self.home, "rules"))
        with open(os.path.join(self.home, "rules", "shop.conf"), "w") as fh:
            fh.write("tools/** = infra\n")
        self.start()
        client = self.sse()
        self.assertTrue(self.counted(client))
        status, body = self.api("/api/balance?terr=%s&kind=infra" % ac.territory_id(self.repo))
        self.assertEqual(body["files"], ["tools/gen.py"])

    def test_after_a_restart_the_list_is_counted_once(self):
        self.start()
        client = self.sse()
        self.assertTrue(self.counted(client))
        client.close()
        for p in self.procs:
            p.terminate()
            p.wait(5)
        self.start()
        status, body = self.api("/api/balance?terr=%s&kind=knowledge" % ac.territory_id(self.repo))
        self.assertEqual(status, 200)
        self.assertEqual(body["files"], ["README.md"])


class TestAssetVersion(BalanceServerCase):
    def setUp(self):
        super().setUp()
        self.assets = os.path.join(self.base, "assets")
        os.makedirs(os.path.join(self.assets, "pets"))
        with open(os.path.join(self.assets, "pets", "a.glb"), "wb") as fh:
            fh.write(b"glTF")

    def test_version_follows_the_files(self):
        v1 = ac.asset_version(self.assets)
        self.assertRegex(v1, r"^[0-9a-f]{8,}$")
        self.assertEqual(ac.asset_version(self.assets), v1)
        with open(os.path.join(self.assets, "pets", "b.glb"), "wb") as fh:
            fh.write(b"x")
        v2 = ac.asset_version(self.assets)
        self.assertNotEqual(v2, v1)
        with open(os.path.join(self.assets, "pets", "a.glb"), "wb") as fh:
            fh.write(b"glTF-2")
        self.assertNotEqual(ac.asset_version(self.assets), v2)

    def test_page_and_cache_headers(self):
        page = os.path.join(self.base, "page.html")
        with open(page, "w") as fh:
            fh.write("<script src=\"assets/pets/a.glb?v=__CITY_ASSET_V__\"></script>")
        self.start("--idle-sec", "60", "--world", self.world, "--assets", self.assets, "--page", page)
        status, headers, body = self.get("/")
        v = ac.asset_version(self.assets)
        self.assertIn(("?v=" + v).encode(), body)
        self.assertNotIn(b"__CITY_ASSET_V__", body)
        status, headers, body = self.get("/assets/pets/a.glb?v=" + v)
        self.assertEqual((status, body), (200, b"glTF"))
        self.assertEqual(headers.get("Cache-Control"), "max-age=31536000, immutable")
        for path in ("/assets/pets/a.glb", "/assets/pets/a.glb?v=old"):
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertEqual(headers.get("Cache-Control"), "no-cache")


class TestDemoBalance(unittest.TestCase):
    def test_demo_world_shows_every_era(self):
        view = ac.demo_world()
        eras = {t["era"] for t in view["territories"]}
        self.assertEqual(eras, {"village", "town", "city"})
        village = next(t for t in view["territories"] if t["era"] == "village")
        self.assertIn("missing", {v["state"] for v in village["balance"].values()})
        self.assertTrue(village["next"])
        for t in view["territories"]:
            with self.subTest(t=t["name"]):
                self.assertEqual(set(t["balance"]), set(ac.KINDS))
                self.assertNotIn("show", t)


if __name__ == "__main__":
    unittest.main()
