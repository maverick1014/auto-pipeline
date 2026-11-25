"""Failing tests for test-levels (risk level per task). Written by the task manager, before any code.

WHY (owner 2026-11-20, decisions 1A 2A 3A, final): today the lane is picked by
task size only (R1). A second axis: a risk level per task, picked at dispatch,
that fixes the pre-publish checks. Size still picks fast or full lane; level 3
and 4 always take the full lane.

    L0 wording / tiny visual   gate: the main manager reads the diff and approves. No test, staging, E2E, mock
    L1 UI only                 gate: lint + type-check, before/after screenshots by a non-builder at desktop
                               and phone width, console clean, owner OK (away: main manager, "owner not seen")
    L2 simple logic            gate: failing test first, touched-module tests + lint/type-check, E2E happy + 1 error path
    L3 heavy logic/principles  gate: rules table with examples in the requirement doc, owner yes before code,
                               tests cover its edges, Opus reviewer, touched module + core group, full suite once,
                               E2E several paths incl. a failure path, real-data count first (H1)
    L4 danger                  gate: all of L3 + migration dry-run on a data copy + rollback plan + owner signs

CONTRACT

1. bin/agent-level.sh (new, executable, bash 3.2) + bin/agent_level.py (new, python 3.9, stdlib only)

   agent-level.sh check --base <ref> [--declared <n>]

   The diff: the working tree of the git toplevel of the cwd (tracked files, staged
   or not, plus untracked files that are not ignored, as new files) against
   `git merge-base <ref> HEAD`. No rename detection (a rename = a deleted file + a
   new file). A change that came in on <ref> after the merge base is not in it.

   stdout, in this order:
       REQUIRED LEVEL <n>                    always the first line
       <path>: L<k> <reason>                 one line per changed file, sorted by path
       no changes                            when nothing changed
       no agent.conf: built-in D paths only when the project has no agent.conf
       RAISE: declared <d>, needs <m>        last line, only when d < m (see below)
   exit 0; RAISE -> exit 1. Usage or setup error (no --base, a ref git does not know,
   --declared not one of 0 1 2 3 4, another verb, an invalid level3_paths or
   level4_paths in agent.conf) -> one line on stderr (naming the bad part),
   nothing on stdout, exit 2.

   <n> = the highest <k> of all files, 0 when there is none; with --declared <d>:
   max(d, that). A level only goes up, never down: declared 3 with an L0 diff
   prints REQUIRED LEVEL 3, exit 0.

   The level of one file = the highest that applies:
     L4  a built-in L4 path (reasons: "built-in L4: <kind>"):
           lockfile         basename package-lock.json, npm-shrinkwrap.json, pnpm-lock.yaml,
                            bun.lockb, go.sum, or *.lock (yarn.lock, pubspec.lock, Podfile.lock,
                            Gemfile.lock, poetry.lock, Cargo.lock, composer.lock ...)
           package.json deps  a package.json whose dependencies, devDependencies,
                            peerDependencies, optionalDependencies, bundleDependencies,
                            bundledDependencies, overrides or resolutions differ (as JSON)
                            between the merge base and now; new, deleted or unreadable
                            JSON counts. Any other package.json change -> L2.
           pubspec          basename pubspec.yaml or pubspec.yml
           dependency list  basename requirements*.txt, go.mod, Gemfile, Podfile, Pipfile,
                            Cargo.toml, pyproject.toml, build.gradle, build.gradle.kts, pom.xml
           migration        a folder of the path named migrations, migration, migrate or alembic
           schema           basename schema.*, *.schema.*, *.prisma or *.sql
         or a level4_paths glob     (reason "level4_paths <glob>")
     L3  a level3_paths glob        (reason "level3_paths <glob>")
     L1  a style file  .css .scss .sass .less .styl .pcss            (reason "style file")
         an asset file .png .jpg .jpeg .gif .webp .avif .bmp .ico .svg
                       .woff .woff2 .ttf .otf .eot                   (reason "asset file")
     L0  a text file   .md .markdown .txt .rst .adoc                 (reason "text file")
     code: every other file. New -> L2 "new file", deleted -> L2 "deleted file",
         binary -> L2 "binary file". Else L0 when every hunk is an L0 shape (below),
         L1 "new prop value" when the only non-L0 change is a prop value that is
         not used anywhere else, else L2 "code change".

   agent.conf keys (the main repo's agent.conf, also when run from a worktree):
     level3_paths, level4_paths: comma-separated globs, spaces around a comma
     ignored, empty or missing = none. A glob with no "/" at all matches when
     any folder or the file name of the path matches it (fnmatch): "core",
     "*.rules". Any other glob, a trailing "/" too, is anchored at the repo root
     (the trailing "/" is dropped) and matches when the path or a leading part
     of it matches (fnmatch, "*" also crosses "/", "**" is the same): "api/"
     matches api/x.py and api/v1/y.py, not src/api/x.py; "src/*/ledger" matches
     src/a/ledger/x.ts.

   L0 shapes. Lines are compared without trailing white space. In one hunk the
   removed and added lines pair up in order, the same count; a hunk that only
   adds or only removes is code. In each pair, first every colour literal is
   masked (also inside a string), then string literals and markup text; the
   masked lines must be the same, and each part that differs is:
     colour change       old and new are colour literals: #rgb #rgba #rrggbb #rrggbbaa,
                         rgb() rgba() hsl() hsla(), Color(0xAARRGGBB), Colors.<name>
                         with [<n>] or .shade<n> (Flutter)
     text change         a quoted string ("", '', ``); in a markup file (.html .htm .jsx
                         .tsx .vue .svelte) also the text between ">" and the next "<"
                         on the line (no { } ( ) = && || in it), and the value of a text
                         attribute: alt, title, placeholder, label, aria-label
     existing prop value in a markup file, the value of any other attribute,
                         name="v" name='v' or name={v}: L0 when that exact attribute
                         text (either quote) is found in a tracked file at the merge
                         base; else "new prop value" (L1)
   Never L0 (code): a string holding "${", "$" + a letter, or "{" after an f/F
   prefix; an unclosed quote; an import line (starts with import, from, export ...
   from, #include, @import, use; or holds require( or import( ).
     line move           a markup file or .dart whose removed lines are exactly its
                         added lines (as a multiset, at least one): reason
                         "line move (manager: check responsive)". In any other code
                         file a move is code (statement order).
   The reasons of one L0 file are joined with ", " (e.g. "text change, colour change").

2. agent.conf: level3_paths= and level4_paths= in bin/agent.conf.default (empty),
   validated by agent_conf.py (HINTS, a "levels" group, the last group). A bad
   glob is refused: an empty item, white space inside an item, a leading "/", a
   ".." part. agent-settings.sh <key> <value> saves a good value (also ""),
   refuses a bad one and saves nothing; sync adds both keys, empty.

3. The level on the todo line (bin/agent-file.sh):
   todo add ... --level <n>   n one of 0 1 2 3 4, anywhere after "todo add" (like
       --guess). The field " | level <n>" goes right after guess (else est, else
       the what). Bad or no value -> refused, one stderr line naming --level, exit 1.
   todo level "<name>" <n>    sets it in place (a missing field goes where todo add
       puts it; every other field stays). Higher: prints "todo level: <name> <old> -> <n>"
       ("-" for none). Same: "todo level: <name> already level <n>", nothing written.
       Lower: refused, the stderr line says "only goes up". No such line, a bad n:
       refused. Refused = one stderr line, exit 1, nothing written.
   todo done: the data block gets one more key, the last: level=<n> from the todo
       line's "level <n>" field, else level=-. A "level 9" word inside the what is
       not the level. The data table (agent-file.sh data) keeps its columns.
   board: one more column, zh 级别 / en Level, right after 位置 / Where: "L<n>" from
       the task's todo line, "-" when it has none and for every other row.

4. Rules: PRINCIPLES.md "R8. Risk types" after R7, before "## B. Work", one terse
   "- " line per rule (<= 200 chars). R1, W2, W4, W5 name R8. skills/dispatch picks
   the level (todo add --level, a LEVEL: line in the task manager brief, the level
   in the deputy brief; level 3 or 4 never takes the fast lane). skills/merge,
   agents/merge-deputy.md, agents/fast-lane-deputy.md run agent-level.sh check
   --declared before the E2E or the merge; RAISE -> bounce; level 0 skips the E2E.

5. Quiz: 39 questions. Q38 (R8, answer B) and Q39 (R8, answer D), text below.
   README: the tree lists bin/agent-level.sh, the routing section names the level,
   "39-question quiz". Release: plugin.json 0.36.0.
"""

import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import BIN, ScriptCase  # noqa: E402
import test_agent_board as tb  # noqa: E402

sys.path.insert(0, BIN)
import agent_conf  # noqa: E402

NOW = "2026-11-20 10:00"
FILE_LINE = re.compile(r"^(\S+): ([A-D]) (.+)$")

ANSWERS = ("1A 2D 3C 4B 5D 6D 7C 8C 9A 10D 11C 12C 13D 14C 15D 16B 17C "
           "18D 19C 20A 21D 22C 23B 24D 25C 26D 27B 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C 38A 39C")

# Q38 and Q39 as the quiz prints them (the worker writes them into bin/agent-start.sh as is).
# owner 2A (2026-11-25, TELL 0d544056): the type comes from the brief; Danger paths is a hint
QUIZ_Q38 = """Q38. A diff only rewords two lines in PRINCIPLES.md, a path on the Danger paths list. Its risk type:
  A. A: doc or text only, even in PRINCIPLES.md; the main manager reads the diff
  B. B: UI, Chrome compare with the approved mock
  C. C: logic, failing tests first
  D. D: it is on the Danger paths list, the owner signs before merge"""

QUIZ_Q39 = """Q39. agent-level.sh prints "touches core path bin/agent_conf.py: judge from the brief whether it is D". The brief adds one new setting. You:
  A. Raise the task to D: the path is on the list
  B. Ignore the line: it is only a hint
  C. Judge from the brief: a new feature is normally C, D only when core code many things depend on changes; a second read-only agent checks the type, a disagreement goes to the owner
  D. Ask the owner before every task that touches the list"""


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def section(text, start, end):
    begin = text.index(start)
    return text[begin:text.index(end, begin + len(start))]


# ---------------------------------------------------------------- 1. the check script


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
        return self.repo.run("agent-level.sh", *args, cwd=cwd)

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
        first = r.stdout.splitlines()[0] if r.stdout else ""
        m = re.match(r"^REQUIRED TYPE ([A-D](?:\+[A-D])*)$", first)
        self.assertTrue(m, r.stdout + r.stderr)
        return m.group(1)

    def files(self, r):
        """path -> (type, reason) of the file lines."""
        out = {}
        for line in r.stdout.splitlines()[1:]:
            m = FILE_LINE.match(line)
            if m:
                out[m.group(1)] = (m.group(2), m.group(3))
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
        self.assertEqual(r.stdout.splitlines()[0], "REQUIRED TYPE A")
        self.assertIn("no changes", r.stdout.splitlines())
        self.assertEqual(self.files(r), {})

    def test_one_line_per_file_sorted_after_the_type(self):
        self.base({"b/two.js": 'x("a");\n', "a/one.md": "hello\n", "c/s.css": "a{}\n"})
        self.put({"b/two.js": 'x("b");\n', "a/one.md": "hello you\n", "c/s.css": "b{}\n"})
        r = self.ok()
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "REQUIRED TYPE A+B")
        paths = [FILE_LINE.match(l).group(1) for l in lines[1:] if FILE_LINE.match(l)]
        self.assertEqual(paths, ["a/one.md", "b/two.js", "c/s.css"])

    def test_usage_errors_exit_2_with_one_stderr_line(self):
        self.base({"src/app.js": "x\n"})
        for args in (["check"], ["check", "--base"], ["check", "--base", "no-such-ref"],
                     ["check", "--base", "base", "--declared", "5"],
                     ["check", "--base", "base", "--declared", "E"],
                     ["check", "--base", "base", "--declared", "x"],
                     ["check", "--base", "base", "--declared", ""],
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
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("text change", why)

    def test_a_single_quoted_string_in_python(self):
        need, lvl, why = self.one({"app/views.py": "def f():\n    flash('Saved')\n"},
                                  {"app/views.py": "def f():\n    flash('Stored, thanks')\n"},
                                  "app/views.py")
        self.assertEqual((need, lvl), ("A", "A"))
        self.assertIn("text change", why)

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
        self.assertIn("built-in D: %s" % kind, why)

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


HINT = "touches core path %s: judge from the brief whether it is D"


class TestRepoPaths(LevelCase):
    """Owner 2A (2026-11-25, TELL 0d544056): the risk type is judged from the BRIEF, never from
    file paths alone. The "Risk: Danger paths (D)" setting (danger_paths) is a HINT: a file on it
    keeps the type its content gives and the check prints one line per such file,
    "touches core path <file>: judge from the brief whether it is D". It never raises, and a
    doc/text-only diff (.md, comments, rule text) is A even in PRINCIPLES.md. The built-in D kinds
    (lockfile, dependency lists, migrations, schema) stay D."""

    def test_a_danger_path_is_a_hint_not_a_type(self):
        need, typ, why = self.one({"src/money/total.js": "a()\n"}, {"src/money/total.js": "b()\n"},
                                  "src/money/total.js", conf={"danger_paths": "src/money/,lib/ledger/"})
        self.assertEqual((need, typ), ("C", "C"))
        self.assertNotIn("danger_paths", why)

    def test_the_hint_line_names_the_file(self):
        self.base({"src/money/total.js": "a()\n", "src/other.js": "a()\n"}, {"danger_paths": "src/money/"})
        self.put({"src/money/total.js": "b()\n", "src/other.js": "b()\n"})
        lines = self.ok().stdout.splitlines()
        self.assertIn(HINT % "src/money/total.js", lines)
        self.assertNotIn(HINT % "src/other.js", lines)

    def test_principles_wording_is_a_even_on_the_default_list(self):
        self.base({"PRINCIPLES.md": "- old rule\n"})
        self.put({"PRINCIPLES.md": "- new rule words\n"})
        r = self.ok("--declared", "A")
        self.assertEqual(self.required(r), "A")
        self.assertEqual(self.files(r)["PRINCIPLES.md"][0], "A")
        self.assertIn(HINT % "PRINCIPLES.md", r.stdout.splitlines())
        self.assertNotIn("RAISE", r.stdout)

    def test_a_doc_only_diff_on_the_list_never_raises(self):
        self.base({"skills/a/SKILL.md": "x\n", "agents/w.md": "x\n"})
        self.put({"skills/a/SKILL.md": "y\n", "agents/w.md": "y\n"})
        r = self.ok("--declared", "A")
        self.assertEqual(self.required(r), "A")
        self.assertNotIn("RAISE", r.stdout)

    def test_logic_on_the_list_is_c_and_raises_only_as_c(self):
        self.base({"bin/agent_conf.py": "def f(a):\n    return a + 1\n"})
        self.put({"bin/agent_conf.py": "def f(a):\n    return a * 2\n"})
        r = self.check("--declared", "B")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(r.stdout.splitlines()[-1], "RAISE: declared B, needs C (bin/agent_conf.py)")
        self.assertEqual(self.ok("--declared", "C").stdout.splitlines()[0], "REQUIRED TYPE C")

    def test_built_in_danger_kinds_stay_d(self):
        self.base({"yarn.lock": "a\n", "skills/a/SKILL.md": "x\n"}, {"danger_paths": ""})
        self.put({"yarn.lock": "b\n", "skills/a/SKILL.md": "y\n"})
        got = self.files(self.ok())
        self.assertEqual(got["yarn.lock"][0], "D")
        self.assertEqual(got["skills/a/SKILL.md"][0], "A")

    def test_globs_still_match_for_the_hint(self):
        conf = {"danger_paths": "api/,src/*/ledger,*.money.ts"}
        self.base({"api/v1/h.py": "a = 1\n", "src/api/h.py": "a = 1\n", "src/a/ledger/x.ts": "a\n",
                   "deep/b.money.ts": "a\n"}, conf)
        self.put({"api/v1/h.py": "a = 2\n", "src/api/h.py": "a = 2\n", "src/a/ledger/x.ts": "b\n",
                  "deep/b.money.ts": "b\n"})
        lines = self.ok().stdout.splitlines()
        for hit in ("api/v1/h.py", "src/a/ledger/x.ts", "deep/b.money.ts"):
            self.assertIn(HINT % hit, lines)
        self.assertNotIn(HINT % "src/api/h.py", lines)

    def test_a_bad_stored_value_uses_the_default_and_says_so(self):
        self.base({"skills/a/SKILL.md": "x\n"}, {"danger_paths": "/etc/,src/"})
        self.put({"skills/a/SKILL.md": "y\n"})
        r = self.ok()
        self.assertIn(HINT % "skills/a/SKILL.md", r.stdout.splitlines())
        self.assertIn("danger_paths", r.stderr)

    def test_an_old_agent_conf_is_not_read(self):
        self.base({"src/money/total.js": "a = 1\n"})
        self.repo.set_old_conf("level3_paths=src/money/\nlevel4_paths=src/money/\n")
        self.put({"src/money/total.js": "a = 2\n"})
        r = self.ok()
        self.assertEqual(self.files(r)["src/money/total.js"][0], "C")
        self.assertNotIn(HINT % "src/money/total.js", r.stdout.splitlines())


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


class TestDeclared(LevelCase):

    def ui_touching_api(self):
        self.base({"api/handler.py": "def h():\n    return 1\n", "src/card.css": "a{}\n"})
        self.put({"api/handler.py": "def h():\n    return 2\n", "src/card.css": "b{}\n"})

    def test_a_c_file_above_the_declared_type_raises(self):
        self.ui_touching_api()
        r = self.check("--declared", "B")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "REQUIRED TYPE B+C")
        self.assertEqual(lines[-1], "RAISE: declared B, needs C (api/handler.py)")

    def test_old_numbers_are_read_as_types(self):
        self.ui_touching_api()
        self.assertEqual(self.check("--declared", "1").returncode, 1)      # 1 = B
        for old in ("2", "3", "C", "D", "4"):
            with self.subTest(declared=old):
                self.ok("--declared", old)
        r = self.check("--declared", "1")
        self.assertEqual(r.stdout.splitlines()[-1], "RAISE: declared B, needs C (api/handler.py)")

    def test_declared_equal_passes(self):
        self.ui_touching_api()
        r = self.ok("--declared", "C")
        self.assertEqual(self.required(r), "B+C")
        self.assertNotIn("RAISE", r.stdout)

    def test_a_declared_type_does_not_change_the_required_parts(self):
        self.base({"docs/a.md": "x\n"})
        self.put({"docs/a.md": "y\n"})
        r = self.ok("--declared", "D")
        self.assertEqual(self.required(r), "A")
        self.assertNotIn("RAISE", r.stdout)

    def test_a_and_b_files_never_raise(self):
        self.base({"docs/a.md": "x\n", "src/card.css": "a{}\n"})
        self.put({"docs/a.md": "y\n", "src/card.css": "b{}\n"})
        r = self.ok("--declared", "A")
        self.assertEqual(self.required(r), "A+B")
        self.assertNotIn("RAISE", r.stdout)

    def test_no_declared_never_raises(self):
        self.base({"yarn.lock": "a\n"})
        self.put({"yarn.lock": "b\n"})
        r = self.ok()
        self.assertEqual(self.required(r), "D")
        self.assertNotIn("RAISE", r.stdout)

    def test_declared_a_with_a_lockfile(self):
        self.base({"yarn.lock": "a\n"})
        self.put({"yarn.lock": "b\n"})
        r = self.check("--declared", "0")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.splitlines()[-1], "RAISE: declared A, needs D (yarn.lock)")


class TestTypesPerPart(LevelCase):
    """R8 (2026-11-24): a type per file and per task part, never one maximum; a component file is B at most."""

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
                                  conf={"danger_paths": "src/money/"})
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
        lines = r.stdout.splitlines()
        self.assertIn("PART A: docs/a.md", lines)
        self.assertIn("PART B: src/Banner.tsx", lines)
        self.assertIn("PART C: src/calc.py", lines)
        self.assertIn("PART D: yarn.lock", lines)

    def test_a_component_file_and_a_calc_file_exit_zero_when_declared_c_and_raise_when_declared_b(self):
        self.base({"src/Banner.tsx": "export const A = () => <b>hi</b>;\n", "src/calc.py": "def f(a):\n    return a + 1\n"})
        self.put({"src/Banner.tsx": "export const A = () => <div>{n}</div>;\n", "src/calc.py": "def f(a):\n    return a * 2\n"})
        self.assertEqual(self.ok("--declared", "C").stdout.splitlines()[0], "REQUIRED TYPE B+C")
        r = self.check("--declared", "B")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.splitlines()[-1], "RAISE: declared B, needs C (src/calc.py)")

    def test_the_component_file_alone_never_raises_a_declared_a(self):
        self.base({"src/Banner.tsx": "export const A = () => <b>hi</b>;\n"})
        self.put({"src/Banner.tsx": "export const A = () => <div>{n}</div>;\n"})
        r = self.ok("--declared", "A")
        self.assertEqual(self.required(r), "B")
        self.assertNotIn("RAISE", r.stdout)

    def test_a_danger_path_adds_a_hint_for_that_file_only(self):
        self.base({"db/seed.js": "x()\n", "docs/a.md": "x\n"}, {"danger_paths": "db/"})
        self.put({"db/seed.js": "y()\n", "docs/a.md": "y\n"})
        r = self.ok()
        self.assertEqual(self.required(r), "A+C")
        lines = r.stdout.splitlines()
        self.assertIn(HINT % "db/seed.js", lines)
        self.assertNotIn(HINT % "docs/a.md", lines)

    def test_logic_outside_a_danger_path_is_c(self):
        need, typ, why = self.one({"src/money/total.js": "a()\n"}, {"src/money/total.js": "b()\n"},
                                  "src/money/total.js", conf={"danger_paths": ""})
        self.assertEqual((need, typ), ("C", "C"))


# ---------------------------------------------------------------- 2. agent.conf keys


class TestDangerPathsSetting(unittest.TestCase):
    """danger_paths: comma-separated globs, checked like the old level paths."""

    def test_good_values(self):
        for value in ("", "src/core/", "src/core/,lib/money/**", "*.sql", " api/ , db/ ",
                      "core", "src/*/ledger"):
            with self.subTest(value=value):
                self.assertIsNone(agent_conf.validate_value("danger_paths", value))

    def test_bad_values(self):
        for value in ("/etc/", "src/../x", "a b", "api/,,db/", ",", "api/, /db"):
            with self.subTest(value=value):
                self.assertTrue(agent_conf.validate_value("danger_paths", value))

    def test_the_old_keys_are_gone(self):
        for key in ("level3_paths", "level4_paths"):
            with self.assertRaises(KeyError):
                agent_conf.get(key, {})


# ---------------------------------------------------------------- 3. the todo line, done, board


class TodoCase(ScriptCase):
    script = "agent-file.sh"

    def af(self, *args, now=NOW):
        return self.repo.run("agent-file.sh", *args, env={"AGENT_FAKE_NOW": now, "AGENT_FAKE_HOST": "pc2"})

    def todo(self):
        return self.repo.read("agent_todo.txt") or ""

    def write_todo(self, *lines):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def refused(self, *args):
        before = self.todo()
        r = self.af(*args)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertEqual(self.todo(), before)
        return r


class TestTodoAddLevel(TodoCase):

    def test_after_the_guess(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70", "--guess", "35", "--level", "C"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | guess 35m | level C | opened %s | by main\n" % NOW)

    def test_it_may_stand_anywhere(self):
        self.assertOk(self.af("todo", "add", "--level", "D", "t1", "big", "build it", "70"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | level D | opened %s | by main\n" % NOW)

    def test_no_est(self):
        self.assertOk(self.af("todo", "add", "t1", "small", "fix it", "--level", "A"))
        self.assertEqual(self.todo(), "t1 | small | fix it | level A | opened %s | by main\n" % NOW)

    def test_no_level_is_as_before(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | opened %s | by main\n" % NOW)

    def test_an_old_number_is_stored_as_its_type(self):
        for old, typ in (("0", "A"), ("1", "B"), ("2", "C"), ("3", "C"), ("4", "D")):
            with self.subTest(old=old):
                self.write_todo()
                self.assertOk(self.af("todo", "add", "t1", "small", "fix it", "--level", old))
                self.assertEqual(self.todo(), "t1 | small | fix it | level %s | opened %s | by main\n" % (typ, NOW))

    def test_a_bad_level_is_refused(self):
        for bad in (["--level", "5"], ["--level", "E"], ["--level", "-1"], ["--level", "x"], ["--level", ""], ["--level"]):
            with self.subTest(bad=bad):
                r = self.refused("todo", "add", "t1", "big", "build it", "70", *bad)
                self.assertIn("--level", r.stderr)


class TestTodoLevel(TodoCase):
    LINE = "t1 | big | build it | est 70m | guess 35m | level B | opened 2026-11-20 09:00 | by main | stage tests since 2026-11-20 09:10"

    def test_a_raise_replaces_in_place(self):
        self.write_todo(self.LINE, "t2 | small | other | est 5m | opened 2026-11-20 09:00 | by main")
        r = self.af("todo", "level", "t1", "C")
        self.assertOk(r)
        self.assertIn("todo level: t1 B -> C", r.stdout)
        self.assertEqual(self.todo().splitlines(), [self.LINE.replace("level B", "level C"),
                                                    "t2 | small | other | est 5m | opened 2026-11-20 09:00 | by main"])

    def test_a_missing_level_goes_where_todo_add_puts_it(self):
        self.write_todo("t1 | big | build it | est 70m | opened 2026-11-20 09:00 | by main | stage tests since 2026-11-20 09:10")
        r = self.af("todo", "level", "t1", "C")
        self.assertOk(r)
        self.assertIn("todo level: t1 - -> C", r.stdout)
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | level C | opened 2026-11-20 09:00 | by main | stage tests since 2026-11-20 09:10\n")

    def test_after_the_guess_when_there_is_one(self):
        self.write_todo("t1 | big | build it | est 70m | guess 35m | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "level", "t1", "D"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | guess 35m | level D | opened 2026-11-20 09:00 | by main\n")

    def test_the_same_level_writes_nothing(self):
        self.write_todo(self.LINE)
        before = os.stat(self.repo.path("agent_todo.txt")).st_mtime_ns
        r = self.af("todo", "level", "t1", "B")
        self.assertOk(r)
        self.assertIn("todo level: t1 already type B", r.stdout)
        self.assertEqual(self.todo(), self.LINE + "\n")
        self.assertEqual(os.stat(self.repo.path("agent_todo.txt")).st_mtime_ns, before)

    def test_lower_is_refused(self):
        self.write_todo(self.LINE.replace("level B", "level D"))
        r = self.refused("todo", "level", "t1", "C")
        self.assertIn("only goes up", r.stderr)

    def test_an_old_number_line_stays_readable(self):
        self.write_todo(self.LINE.replace("level B", "level 3"))
        r = self.refused("todo", "level", "t1", "B")                 # old 3 = C: B is lower
        self.assertIn("only goes up", r.stderr)
        self.assertIn("already type C", self.af("todo", "level", "t1", "2").stdout)    # old 3 and 2 are both C
        self.assertOk(self.af("todo", "level", "t1", "D"))
        self.assertEqual(self.todo().splitlines(), [self.LINE.replace("level B", "level D")])

    def test_old_numbers_are_accepted_as_input(self):
        self.write_todo(self.LINE)
        self.assertOk(self.af("todo", "level", "t1", "4"))
        self.assertEqual(self.todo().splitlines(), [self.LINE.replace("level B", "level D")])

    def test_bad_input_is_refused(self):
        self.write_todo(self.LINE)
        for args in (["todo", "level", "nope", "2"], ["todo", "level", "t1", "5"],
                     ["todo", "level", "t1", "E"], ["todo", "level", "t1", "x"], ["todo", "level", "t1"]):
            with self.subTest(args=args):
                self.refused(*args)


class TestTodoDoneLevel(TodoCase):

    def done_line(self):
        rows = [l for l in (self.repo.read("agent_completed.txt") or "").splitlines() if l.strip()]
        self.assertEqual(len(rows), 1, rows)
        return rows[0]

    def test_the_level_is_the_last_key(self):
        self.write_todo("t1 | big | build it | est 70m | guess 35m | level C | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertTrue(self.done_line().endswith(" adds=- guess=35 level=C"), self.done_line())

    def test_an_old_number_is_copied_as_it_is(self):
        self.write_todo("t1 | big | build it | est 70m | guess 35m | level 2 | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertTrue(self.done_line().endswith(" level=2"), self.done_line())
        self.assertIn(" | t1 | build it | data repo=", self.done_line())

    def test_no_level_is_a_dash(self):
        self.write_todo("t1 | big | build it | est 70m | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertTrue(self.done_line().endswith(" guess=- level=-"), self.done_line())

    def test_a_level_word_in_the_what_is_not_the_level(self):
        self.write_todo("t1 | big | level 9 is a word here | est 70m | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertTrue(self.done_line().endswith(" level=-"), self.done_line())

    def test_the_data_table_keeps_its_columns(self):
        with open(self.repo.path("agent_completed.txt"), "w") as fh:
            fh.write("2026-11-19 | old | an old line | data repo=project type=script lane=full mock=no "
                     "est=10 work=5 wait=0 clock=5 bounces=0 workers=0 files=- lines=- tests=- adds=- guess=-\n")
            fh.write("2026-11-20 | new | a new line | data repo=project type=script lane=full mock=no "
                     "est=10 work=5 wait=0 clock=5 bounces=0 workers=0 files=- lines=- tests=- adds=- guess=8 level=3\n")
        rows = [r.split() for r in self.assertOk(self.af("data")).splitlines()]
        self.assertEqual(rows[0][-2:], ["adds", "guess"])
        self.assertEqual([r[1] for r in rows[1:]], ["old", "new"])
        self.assertEqual(rows[2][-1], "8")


class TestBoardLevel(tb.BoardCase):
    lang = "en"

    def test_the_column_sits_after_where(self):
        self.assertEqual(tb.HEAD["zh"][4:7], ["位置", "级别", "估时"])
        self.assertEqual(tb.HEAD["en"][4:7], ["Where", "Level", "Est"])

    def test_the_cells(self):
        self.af("todo", "add", "lv", "big", "with a level", "60", "--level", "C", now="2026-11-02 14:00")
        self.add("nolv", "an old line", est=30)
        self.state("PARKED: a question | lv | since 2026-11-02 14:10")
        rows = self.rows()
        self.assertEqual(self.row(rows, task="lv")["Level"], "C")
        self.assertEqual(self.row(rows, task="nolv")["Level"], "-")
        for r in rows:
            if r["Task"] not in ("lv", "nolv"):
                self.assertEqual(r["Level"], "-", r)

    def test_an_old_number_line_shows_its_type(self):
        for old, typ in (("0", "A"), ("1", "B"), ("3", "C"), ("4", "D")):
            with self.subTest(old=old):
                self.af("todo", "add", "o" + old, "big", "an old line", "60", now="2026-11-02 14:00")
                path = self.repo.path("agent_todo.txt")
                with open(path) as fh:
                    text = fh.read()
                with open(path, "w") as fh:
                    fh.write(text.replace("est 60m |", "est 60m | level %s |" % old))
                self.assertEqual(self.row(self.rows(), task="o" + old)["Level"], typ)

    def test_zh_header(self):
        self.repo.set_conf("language", "zh")
        self.add("nolv", "an old line", est=30)
        head = [l for l in self.board().splitlines() if l.startswith("|")][0]
        self.assertEqual(tb.cells(head), tb.HEAD["zh"])


# ---------------------------------------------------------------- 4. rules, skills, agents


class TestTheRule(unittest.TestCase):

    def text(self):
        return read("PRINCIPLES.md")

    def rule(self):
        return section(self.text(), "R8. Risk types", "## B. Work")

    def test_it_sits_after_r7_and_nothing_is_renumbered(self):
        text = self.text()
        order = [text.index(h) for h in ("R7. Worktree file", "R8. Risk types", "## B. Work", "W1. ")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(text.count("R8. "), 1)

    def test_one_short_line_per_rule(self):
        lines = self.rule().rstrip().splitlines()
        bullets = [l for l in lines if l.startswith("- ")]
        self.assertGreaterEqual(len(bullets), 8)
        self.assertLessEqual(len(bullets), 20)
        for line in lines[1:]:
            with self.subTest(line=line[:40]):
                self.assertTrue(line.startswith("- ") or not line.strip(), line)
                self.assertLessEqual(len(line), 200)

    def test_it_says_what_the_owner_decided(self):
        rule = self.rule().lower()
        for phrase in ("a = text, style, simple move", "b = ui", "c = logic", "d = danger",
                       "dispatch", "--level", "agent-level.sh check", "raise", "only goes up",
                       "danger paths (d)", "reads the diff", "e2e",
                       # owner 2A 2026-11-25, R8 text from main 85b99de
                       "judge the type from the brief, never from file paths alone", "docs only",
                       "a new feature = normally c", "core code that many other things depend on",
                       "second opinion", "read-only agent", "not the manager's answer", "the owner decides",
                       "a hint, not a verdict", "lowering a type needs the owner",
                       "mock", "phone", "console clean", "owner not seen",
                       "failing tests first", "touched features", "full suite only when really needed",
                       "dry-run", "rollback plan", "owner signs",
                       "check responsive", "lockfile", "todo level",
                       "mixed task", "own type", "component or style file is b at most", "never auto-raised",
                       "acceptance criterion", "0=a 1=b 2,3=c 4=d"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)

    def test_the_other_rules_point_at_it(self):
        text = self.text()
        for start, end in (("R1. ", "R2. "), ("W2. ", "W3. "), ("W4. ", "W5. "), ("W5. ", "W6. ")):
            with self.subTest(rule=start):
                self.assertIn("R8", section(text, start, end))

    def test_no_old_level_words_are_left(self):
        text = self.text()
        self.assertNotRegex(text, r"(?i)\blevel [0-4]\b")
        self.assertNotIn("Risk levels", text)

    def test_w4_runs_tests_by_touched_feature(self):
        w4 = section(self.text(), "W4. ", "W5. ")
        self.assertIn("module → feature", w4)
        self.assertIn("touched feature", w4)
        self.assertIn("Full suite only when really needed", w4)

    def test_r1_keeps_size_and_adds_the_full_lane_for_d(self):
        r1 = section(self.text(), "R1. ", "R2. ")
        self.assertIn("Task size picks the lane", r1)
        self.assertIn("full lane", r1)
        self.assertIn("D always takes the full lane", r1)


class TestDispatchSkill(unittest.TestCase):

    def text(self):
        return read("skills", "dispatch", "SKILL.md")

    def test_the_todo_add_line_carries_the_level(self):
        line = [l for l in self.text().splitlines() if "agent-file.sh todo add" in l][0]
        self.assertIn("--level <A-D>", line)

    def test_the_task_manager_brief_has_a_level_line(self):
        brief = section(self.text(), "## Task manager brief", "## Cross-repo brief")
        self.assertTrue([l for l in brief.splitlines() if l.startswith("LEVEL:")], brief)

    def test_the_deputy_brief_carries_the_type_and_d_is_never_fast(self):
        step2 = section(self.text(), "\n2. ", "\n3. ")
        self.assertIn("level: <A-D>", step2)
        self.assertIn("Type D never takes the fast lane", step2)

    def test_it_names_the_rule(self):
        self.assertIn("R8", self.text())

    def test_the_type_is_picked_from_the_brief_and_a_second_agent_checks_it(self):
        # owner 2A 2026-11-25: a read-only second agent, given the brief and the code but not the
        # manager's answer, reviews the type; a disagreement goes to the owner
        text = self.text().lower()
        for phrase in ("from the brief", "second agent", "read-only", "not the", "disagree", "owner",
                       "touches core path"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


class TestMergeSkill(unittest.TestCase):

    def text(self):
        return read("skills", "merge", "SKILL.md")

    def test_the_check_runs_before_the_e2e(self):
        text = self.text()
        self.assertIn("agent-level.sh check", text)
        self.assertLess(text.index("agent-level.sh check"), text.index("agent-runtime.sh browser"))

    def test_it_says_declared_raise_and_level_0(self):
        text = self.text()
        for words in ("--declared", "RAISE", "todo level", "own type"):
            with self.subTest(words=words):
                self.assertIn(words, text)
        self.assertRegex(text, r"(?i)type A[^\n]*skip[^\n]*E2E")
        self.assertIn("by its own type", text)

    def test_the_deputy_brief_gives_the_level(self):
        block = section(self.text(), "name: <name>", "todo done arguments:")
        self.assertIn("level: <A-D>", block)


class TestDeputies(unittest.TestCase):

    def test_the_merge_deputy_checks_before_it_merges(self):
        text = read("agents", "merge-deputy.md")
        given = [l for l in text.splitlines() if l.startswith("Your brief gives")][0]
        self.assertIn("<level>", given)
        self.assertIn("agent-level.sh check", text)
        self.assertLess(text.index("agent-level.sh check"), text.index("git merge --no-ff"))
        for words in ("--declared", "RAISE", "MERGE FAIL"):
            with self.subTest(words=words):
                self.assertIn(words, text)
        step7 = [l for l in text.splitlines() if l.startswith("7. ")][0]
        self.assertIn('agent-file.sh todo done "<name>"', step7)

    def test_the_fast_lane_deputy_checks_its_diff(self):
        text = read("agents", "fast-lane-deputy.md")
        for words in ("agent-level.sh check", "--declared", "RAISE", "REQUIRED TYPE"):
            with self.subTest(words=words):
                self.assertIn(words, text)


# ---------------------------------------------------------------- 5. quiz, README, release


class TestTheQuiz(ScriptCase):
    script = "agent-start.sh"

    def quiz(self):
        return self.assertOk(self.repo.run("agent-start.sh", "--quiz"))

    def test_q38_and_q39(self):
        out = self.quiz()
        self.assertEqual("\n".join(out[out.index("Q38. "):].splitlines()[:5]), QUIZ_Q38)
        self.assertEqual("\n".join(out[out.index("Q39. "):].splitlines()[:5]), QUIZ_Q39)

    def test_the_quiz_says_39(self):
        out = self.quiz()
        self.assertIn("=== QUIZ — answer all 39 before any work ===", out)
        self.assertIn('--answer "1A 2B 3C ... 39D"', out)
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", out)), 39)

    def test_b_and_d_pass(self):
        out = self.assertOk(self.repo.run("agent-start.sh", "--answer", ANSWERS))
        self.assertIn("QUIZ RESULT: 39/39 PASS", out)

    def test_another_letter_fails_and_names_r8(self):
        for good, wrongs in (("38A", ("38B", "38C", "38D")), ("39C", ("39A", "39B", "39D"))):
            for wrong in wrongs:
                with self.subTest(wrong=wrong):
                    r = self.repo.run("agent-start.sh", "--answer", ANSWERS.replace(good, wrong))
                    self.assertEqual(r.returncode, 1)
                    self.assertIn("Q%s(R8)" % good[:2], r.stdout)

    def test_the_old_37_answers_no_longer_pass(self):
        r = self.repo.run("agent-start.sh", "--answer", ANSWERS.replace(" 38A 39C", ""))
        self.assertEqual(r.returncode, 1)

    def test_the_usage_says_39(self):
        src = read("bin", "agent-start.sh")
        self.assertIn("print the 39 quiz questions", src)
        self.assertEqual(src.count('--answer "1A 2D ... 39D"'), 2, "the header and the usage line")
        self.assertNotIn("... 37C", src)


class TestReadmeAndRelease(unittest.TestCase):

    def test_the_tree_lists_the_script(self):
        self.assertIn("bin/agent-level.sh", read("PRINCIPLES.md"))

    def test_the_quiz_count(self):
        self.assertIn("39-question quiz", read("PRINCIPLES.md"))

    def test_release(self):
        ver = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        self.assertGreaterEqual(tuple(int(x) for x in ver.split(".")), (0, 36, 0))


if __name__ == "__main__":
    unittest.main()
