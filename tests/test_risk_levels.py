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
       no agent.conf: built-in L4 paths only when the project has no agent.conf
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
     ignored, empty or missing = none. A glob with no "/" (a trailing "/" does
     not count) matches when any folder or the file name of the path matches it
     (fnmatch): "core", "*.rules". Any other glob is anchored at the repo root
     and matches when the path or a leading part of it matches (fnmatch, "*"
     also crosses "/", "**" is the same): "api/" matches api/x.py and
     api/v1/y.py, not src/api/x.py; "src/*/ledger" matches src/a/ledger/x.ts.

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

4. Rules: PRINCIPLES.md "R8. Risk levels" after R7, before "## B. Work", one terse
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
FILE_LINE = re.compile(r"^(\S+): L([0-4]) (.+)$")

ANSWERS = ("1A 2D 3C 4B 5D 6D 7A 8C 9A 10D 11A 12C 13D 14C 15B 16C 17C "
           "18D 19B 20A 21D 22C 23B 24D 25A 26D 27A 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C 38B 39D")

# Q38 and Q39 as the quiz prints them (the worker writes them into bin/agent-start.sh as is).
QUIZ_Q38 = """Q38. A task changes one colour value in one component: #1e88e5 becomes #43a047. Its risk level:
  A. 2: simple logic, failing test first
  B. 0: wording or tiny visual, the main manager reads the diff
  C. 1: UI only, screenshots at desktop and phone width
  D. 4: danger, the owner signs before merge"""

QUIZ_Q39 = """Q39. The todo line says level 1 (UI only). Before merge, agent-level.sh check --declared 1 prints REQUIRED LEVEL 2 and RAISE: the diff touches api/. You:
  A. Merge: the dispatch said UI only
  B. Undo the api/ change yourself, then merge
  C. Run the check again without --declared
  D. Raise the todo line to level 2, bounce it back, run the level 2 gate before merge"""


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

    def required(self, r):
        first = r.stdout.splitlines()[0] if r.stdout else ""
        m = re.match(r"^REQUIRED LEVEL ([0-4])$", first)
        self.assertTrue(m, r.stdout + r.stderr)
        return int(m.group(1))

    def files(self, r):
        """path -> (level, reason) of the file lines."""
        out = {}
        for line in r.stdout.splitlines()[1:]:
            m = FILE_LINE.match(line)
            if m:
                out[m.group(1)] = (int(m.group(2)), m.group(3))
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
        self.assertEqual(r.stdout.splitlines()[0], "REQUIRED LEVEL 0")
        self.assertIn("no changes", r.stdout.splitlines())
        self.assertEqual(self.files(r), {})

    def test_one_line_per_file_sorted_after_the_level(self):
        self.base({"b/two.js": 'x("a");\n', "a/one.md": "hello\n", "c/s.css": "a{}\n"})
        self.put({"b/two.js": 'x("b");\n', "a/one.md": "hello you\n", "c/s.css": "b{}\n"})
        r = self.ok()
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "REQUIRED LEVEL 1")
        paths = [FILE_LINE.match(l).group(1) for l in lines[1:] if FILE_LINE.match(l)]
        self.assertEqual(paths, ["a/one.md", "b/two.js", "c/s.css"])

    def test_usage_errors_exit_2_with_one_stderr_line(self):
        self.base({"src/app.js": "x\n"})
        for args in (["check"], ["check", "--base"], ["check", "--base", "no-such-ref"],
                     ["check", "--base", "base", "--declared", "5"],
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
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("text change", why)

    def test_a_single_quoted_string_in_python(self):
        need, lvl, why = self.one({"app/views.py": "def f():\n    flash('Saved')\n"},
                                  {"app/views.py": "def f():\n    flash('Stored, thanks')\n"},
                                  "app/views.py")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("text change", why)

    def test_markup_text_between_tags(self):
        need, lvl, why = self.one({"src/Home.jsx": "export const Home = () => (\n  <h1>Welcome</h1>\n);\n"},
                                  {"src/Home.jsx": "export const Home = () => (\n  <h1>Welcome back</h1>\n);\n"},
                                  "src/Home.jsx")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("text change", why)

    def test_a_text_attribute(self):
        need, lvl, why = self.one({"src/Logo.jsx": '<img src={logo} alt="Logo" />\n'},
                                  {"src/Logo.jsx": '<img src={logo} alt="Company logo" />\n'},
                                  "src/Logo.jsx")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("text change", why)

    def test_a_hex_colour_in_a_string(self):
        need, lvl, why = self.one({"src/Badge.jsx": 'const tint = "#1e88e5";\n'},
                                  {"src/Badge.jsx": 'const tint = "#43a047";\n'}, "src/Badge.jsx")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("colour change", why)

    def test_a_colour_attribute_is_a_colour_not_a_prop(self):
        need, lvl, why = self.one({"src/Badge.jsx": '<Badge color="#1e88e5" />\n'},
                                  {"src/Badge.jsx": '<Badge color="#43a047" />\n'}, "src/Badge.jsx")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("colour change", why)

    def test_a_dart_colour(self):
        need, lvl, why = self.one({"lib/badge.dart": "final c = Container(color: Color(0xFF1E88E5));\n"},
                                  {"lib/badge.dart": "final c = Container(color: Color(0xFF43A047));\n"},
                                  "lib/badge.dart")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("colour change", why)

    def test_a_flutter_named_colour(self):
        need, lvl, why = self.one({"lib/badge.dart": "final c = Container(color: Colors.blue);\n"},
                                  {"lib/badge.dart": "final c = Container(color: Colors.green[700]);\n"},
                                  "lib/badge.dart")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("colour change", why)

    def test_rgb_and_rgba(self):
        need, lvl, why = self.one({"src/chart.js": "ctx.fillStyle = 'rgb(30, 136, 229)';\n"},
                                  {"src/chart.js": "ctx.fillStyle = 'rgba(67, 160, 71, 0.8)';\n"},
                                  "src/chart.js")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("colour change", why)

    def test_a_prop_value_already_used_in_the_repo(self):
        need, lvl, why = self.one(
            {"src/Save.jsx": '<Button variant="primary">Save</Button>\n',
             "src/Cancel.jsx": '<Button variant="secondary">Cancel</Button>\n'},
            {"src/Save.jsx": '<Button variant="secondary">Save</Button>\n'}, "src/Save.jsx")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("existing prop value", why)

    def test_a_prop_value_in_braces_already_used(self):
        need, lvl, why = self.one({"src/A.jsx": "<Gap size={3} />\n", "src/B.jsx": "<Gap size={2} />\n"},
                                  {"src/B.jsx": "<Gap size={3} />\n"}, "src/B.jsx")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("existing prop value", why)

    def test_a_line_move_in_markup_asks_for_responsive(self):
        before = "<nav>\n  <Home />\n  <About />\n  <Contact />\n</nav>\n"
        after = "<nav>\n  <About />\n  <Contact />\n  <Home />\n</nav>\n"
        need, lvl, why = self.one({"src/Nav.jsx": before}, {"src/Nav.jsx": after}, "src/Nav.jsx")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("line move", why)
        self.assertIn("manager: check responsive", why)

    def test_a_line_move_in_dart(self):
        before = "Column(children: [\n  title,\n  body,\n]);\n"
        after = "Column(children: [\n  body,\n  title,\n]);\n"
        need, lvl, why = self.one({"lib/page.dart": before}, {"lib/page.dart": after}, "lib/page.dart")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("manager: check responsive", why)

    def test_several_shapes_in_one_file(self):
        before = ('<h1>Welcome</h1>\n' + "".join("<p>line %d</p>\n" % i for i in range(12))
                  + '<Badge color="#1e88e5" />\n')
        after = ('<h1>Welcome back</h1>\n' + "".join("<p>line %d</p>\n" % i for i in range(12))
                 + '<Badge color="#43a047" />\n')
        need, lvl, why = self.one({"src/Home.jsx": before}, {"src/Home.jsx": after}, "src/Home.jsx")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("text change", why)
        self.assertIn("colour change", why)

    def test_a_text_file(self):
        need, lvl, why = self.one({"docs/guide.md": "# Guide\n\nRun it.\n"},
                                  {"docs/guide.md": "# Guide\n\nRun it twice.\n\nMore text.\n"},
                                  "docs/guide.md")
        self.assertEqual((need, lvl), (0, 0))
        self.assertIn("text file", why)

    def test_a_new_text_file(self):
        need, lvl, why = self.one({"docs/guide.md": "x\n"}, {"docs/faq.txt": "Q and A\n"}, "docs/faq.txt")
        self.assertEqual((need, lvl), (0, 0))


class TestLevelOne(LevelCase):

    def test_a_css_change(self):
        need, lvl, why = self.one({"src/card.css": ".card { padding: 4px; }\n"},
                                  {"src/card.css": ".card { padding: 8px; }\n"}, "src/card.css")
        self.assertEqual((need, lvl), (1, 1))
        self.assertIn("style file", why)

    def test_a_colour_in_a_css_file_is_still_a_style_file(self):
        need, lvl, why = self.one({"src/card.css": ".card { color: #ffffff; }\n"},
                                  {"src/card.css": ".card { color: #000000; }\n"}, "src/card.css")
        self.assertEqual((need, lvl), (1, 1))
        self.assertIn("style file", why)

    def test_a_new_scss_file(self):
        need, lvl, why = self.one({"src/app.js": "x\n"}, {"src/theme.scss": "$primary: #fff;\n"},
                                  "src/theme.scss")
        self.assertEqual((need, lvl), (1, 1))
        self.assertIn("style file", why)

    def test_an_asset(self):
        need, lvl, why = self.one({"assets/logo.png": b"\x89PNG\r\n\x1a\n\x00\x01"},
                                  {"assets/logo.png": b"\x89PNG\r\n\x1a\n\x00\x02\x03"},
                                  "assets/logo.png")
        self.assertEqual((need, lvl), (1, 1))
        self.assertIn("asset file", why)

    def test_a_prop_value_not_used_anywhere(self):
        need, lvl, why = self.one(
            {"src/Save.jsx": '<Button variant="primary">Save</Button>\n',
             "src/Cancel.jsx": '<Button variant="secondary">Cancel</Button>\n'},
            {"src/Save.jsx": '<Button variant="ghost">Save</Button>\n'}, "src/Save.jsx")
        self.assertEqual((need, lvl), (1, 1))
        self.assertIn("new prop value", why)


class TestLevelTwo(LevelCase):

    def code(self, before, after, path="src/app.js"):
        need, lvl, why = self.one({path: before}, {path: after}, path)
        self.assertEqual((need, lvl), (2, 2), why)
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

    def test_a_comparison_in_markup_is_not_text(self):
        self.code("const ok = a > b && c < d;\n", "const ok = a > b && c < e;\n", path="src/X.jsx")

    def test_a_new_code_file(self):
        need, lvl, why = self.one({"src/app.js": "x\n"}, {"src/util.js": "export const u = 1;\n"},
                                  "src/util.js")
        self.assertEqual((need, lvl), (2, 2))
        self.assertIn("new file", why)

    def test_a_deleted_code_file(self):
        need, lvl, why = self.one({"src/app.js": "x\n", "src/old.js": "y\n"}, {"src/old.js": None},
                                  "src/old.js")
        self.assertEqual((need, lvl), (2, 2))
        self.assertIn("deleted file", why)

    def test_package_json_scripts_only(self):
        before = json.dumps({"name": "a", "scripts": {"t": "jest"}, "dependencies": {"x": "1.0.0"}}, indent=2)
        after = json.dumps({"name": "a", "scripts": {"t": "jest -i"}, "dependencies": {"x": "1.0.0"}}, indent=2)
        need, lvl, _ = self.one({"package.json": before + "\n"}, {"package.json": after + "\n"},
                                "package.json")
        self.assertEqual((need, lvl), (2, 2))


class TestBuiltInLevelFour(LevelCase):

    def danger(self, path, before, after, kind):
        need, lvl, why = self.one({path: before} if before is not None else {"seed2.txt": "x\n"},
                                  {path: after}, path)
        self.assertEqual((need, lvl), (4, 4), why)
        self.assertIn("built-in L4: %s" % kind, why)

    def test_lockfiles(self):
        for path in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "app/pubspec.lock",
                     "ios/Podfile.lock", "go.sum", "Cargo.lock"):
            with self.subTest(path=path):
                self.danger(path, "a\n", "b\n", "lockfile")
                self.tearDown_repo()

    def tearDown_repo(self):
        # a fresh project for the next subTest
        self.repo.cleanup()
        from scripthelp import ScriptRepo
        self.repo = ScriptRepo()
        self.addCleanup(self.repo.cleanup)

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

    def test_a_level3_folder_beats_an_l0_shape(self):
        need, lvl, why = self.one({"src/money/total.js": 'const t = "Total";\n'},
                                  {"src/money/total.js": 'const t = "Sum";\n'}, "src/money/total.js",
                                  conf={"level3_paths": "src/money/,lib/ledger/"})
        self.assertEqual((need, lvl), (3, 3))
        self.assertIn("level3_paths src/money/", why)

    def test_a_level3_css_file_is_3(self):
        need, lvl, _ = self.one({"src/money/m.css": "a{}\n"}, {"src/money/m.css": "b{}\n"},
                                "src/money/m.css", conf={"level3_paths": "src/money/"})
        self.assertEqual((need, lvl), (3, 3))

    def test_level4_globs(self):
        need, lvl, why = self.one({"firestore.rules": "allow read;\n", "db/seed.js": "x\n"},
                                  {"firestore.rules": "allow write;\n"}, "firestore.rules",
                                  conf={"level4_paths": "*.rules, db/"})
        self.assertEqual((need, lvl), (4, 4))
        self.assertIn("level4_paths *.rules", why)

    def test_level4_beats_level3(self):
        need, lvl, why = self.one({"src/money/pay.js": "x()\n"}, {"src/money/pay.js": "y()\n"},
                                  "src/money/pay.js",
                                  conf={"level3_paths": "src/money/", "level4_paths": "src/money/pay.js"})
        self.assertEqual((need, lvl), (4, 4))

    def test_anchored_globs(self):
        conf = {"level3_paths": "api/,src/*/ledger"}
        self.base({"api/v1/h.py": "a = 1\n", "src/api/h.py": "a = 1\n", "src/a/ledger/x.ts": "a\n"}, conf)
        self.put({"api/v1/h.py": "a = 2\n", "src/api/h.py": "a = 2\n", "src/a/ledger/x.ts": "b\n"})
        got = self.files(self.ok())
        self.assertEqual(got["api/v1/h.py"][0], 3)
        self.assertEqual(got["src/a/ledger/x.ts"][0], 3)
        self.assertEqual(got["src/api/h.py"][0], 2)

    def test_a_glob_with_no_slash_matches_any_folder_or_name(self):
        conf = {"level3_paths": "core,*.money.ts"}
        self.base({"lib/core/x.py": "a = 1\n", "src/deep/a.money.ts": "a\n", "src/corex/y.py": "a = 1\n"}, conf)
        self.put({"lib/core/x.py": "a = 2\n", "src/deep/a.money.ts": "b\n", "src/corex/y.py": "a = 2\n"})
        got = self.files(self.ok())
        self.assertEqual(got["lib/core/x.py"][0], 3)
        self.assertEqual(got["src/deep/a.money.ts"][0], 3)
        self.assertEqual(got["src/corex/y.py"][0], 2)

    def test_an_invalid_conf_value_stops_the_check(self):
        self.base({"src/a.js": "x\n"}, {"level3_paths": "/etc/,src/"})
        self.put({"src/a.js": "y\n"})
        r = self.check()
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("level3_paths", r.stderr)

    def test_no_agent_conf_uses_the_built_ins_only(self):
        self.base({"yarn.lock": "a\n", "src/a.js": "x\n"})
        os.remove(self.repo.path("agent.conf"))
        self.put({"yarn.lock": "b\n"})
        r = self.ok()
        self.assertEqual(self.required(r), 4)
        self.assertIn("no agent.conf: built-in L4 paths only", r.stdout.splitlines())

    def test_a_worktree_reads_the_main_repos_agent_conf(self):
        self.base({"src/money/total.js": "a = 1\n"})
        wt = os.path.join(self.repo.base, "wt_levels")
        self.git("worktree", "add", "-q", "-b", "feat", wt, "base")
        self.repo.set_conf("level3_paths", "src/money/")     # the main copy only, not committed
        self.put({"src/money/total.js": "a = 2\n"}, cwd=wt)
        r = self.ok(cwd=wt)
        self.assertEqual(self.required(r), 3)


class TestDiffScope(LevelCase):

    def test_a_committed_change_on_the_branch_counts(self):
        self.base({"src/a.js": "a = 1\n"})
        self.put({"src/a.js": "a = 2\n"})
        self.commit()
        self.assertEqual(self.required(self.ok()), 2)

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
        self.assertEqual(self.required(r), 0, r.stdout)
        self.assertEqual(list(self.files(r)), ["src/a.md"])

    def test_an_untracked_file_counts(self):
        self.base({"src/a.js": "x\n"})
        self.put({"src/new.js": "export const n = 1;\n"})
        got = self.files(self.ok())
        self.assertEqual(got["src/new.js"][0], 2)

    def test_an_ignored_file_does_not_count(self):
        self.base({".gitignore": "build/\n", "src/a.js": "x\n"})
        self.put({"build/out.js": "y\n"})
        r = self.ok()
        self.assertEqual(self.required(r), 0)
        self.assertEqual(self.files(r), {})


class TestDeclared(LevelCase):

    def ui_touching_api(self):
        self.base({"api/handler.py": "def h():\n    return 1\n", "src/card.css": "a{}\n"})
        self.put({"api/handler.py": "def h():\n    return 2\n", "src/card.css": "b{}\n"})

    def test_declared_lower_raises_and_bounces(self):
        self.ui_touching_api()
        r = self.check("--declared", "1")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "REQUIRED LEVEL 2")
        self.assertEqual(lines[-1], "RAISE: declared 1, needs 2")

    def test_declared_equal_passes(self):
        self.ui_touching_api()
        r = self.ok("--declared", "2")
        self.assertEqual(self.required(r), 2)
        self.assertNotIn("RAISE", r.stdout)

    def test_a_level_never_goes_down(self):
        self.base({"docs/a.md": "x\n"})
        self.put({"docs/a.md": "y\n"})
        r = self.ok("--declared", "3")
        self.assertEqual(self.required(r), 3)
        self.assertNotIn("RAISE", r.stdout)

    def test_no_declared_never_raises(self):
        self.base({"yarn.lock": "a\n"})
        self.put({"yarn.lock": "b\n"})
        r = self.ok()
        self.assertEqual(self.required(r), 4)
        self.assertNotIn("RAISE", r.stdout)

    def test_declared_zero_with_a_lockfile(self):
        self.base({"yarn.lock": "a\n"})
        self.put({"yarn.lock": "b\n"})
        r = self.check("--declared", "0")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.splitlines()[-1], "RAISE: declared 0, needs 4")


# ---------------------------------------------------------------- 2. agent.conf keys


class TestConfKeys(unittest.TestCase):
    KEYS = ("level3_paths", "level4_paths")

    def test_the_template_has_both_empty(self):
        conf = agent_conf.load(os.path.join(ROOT, "bin", "agent.conf.default"))
        for key in self.KEYS:
            with self.subTest(key=key):
                self.assertIn(key, conf)
                self.assertEqual(conf[key], "")

    def test_good_values(self):
        for value in ("", "src/core/", "src/core/,lib/money/**", "*.sql", " api/ , db/ ",
                      "core", "src/*/ledger"):
            for key in self.KEYS:
                with self.subTest(key=key, value=value):
                    self.assertIsNone(agent_conf.validate_value(key, value))

    def test_bad_values(self):
        for value in ("/etc/", "src/../x", "a b", "api/,,db/", ",", "api/, /db"):
            for key in self.KEYS:
                with self.subTest(key=key, value=value):
                    self.assertTrue(agent_conf.validate_value(key, value))

    def test_hints_and_the_levels_group(self):
        for key in self.KEYS:
            with self.subTest(key=key):
                self.assertTrue(agent_conf.HINTS.get(key, "").strip())
                self.assertEqual(agent_conf.group_of(key), "levels")
        self.assertEqual(agent_conf.GROUPS[-1], ("levels", ["level3_paths", "level4_paths"]))


class TestSettings(ScriptCase):
    script = "agent-settings.sh"

    def value(self, key):
        for line in open(self.repo.path("agent.conf")):
            if line.split("=", 1)[0].strip() == key:
                return line.split("=", 1)[1].rstrip("\n")
        return None

    def test_a_good_value_is_saved(self):
        self.assertOk(self.repo.run("agent-settings.sh", "level3_paths", "src/money/,lib/ledger/"))
        self.assertEqual(self.value("level3_paths"), "src/money/,lib/ledger/")

    def test_an_empty_value_is_saved(self):
        self.repo.set_conf("level4_paths", "db/")
        self.assertOk(self.repo.run("agent-settings.sh", "level4_paths", ""))
        self.assertEqual(self.value("level4_paths"), "")

    def test_a_bad_value_is_refused_and_not_saved(self):
        before = self.repo.read("agent.conf")
        r = self.repo.run("agent-settings.sh", "level4_paths", "/etc/")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.repo.read("agent.conf"), before)

    def test_sync_adds_both_keys_empty(self):
        self.assertOk(self.repo.run("agent-settings.sh", "sync"))
        self.assertEqual(self.value("level3_paths"), "")
        self.assertEqual(self.value("level4_paths"), "")


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
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70", "--guess", "35", "--level", "2"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | guess 35m | level 2 | opened %s | by main\n" % NOW)

    def test_it_may_stand_anywhere(self):
        self.assertOk(self.af("todo", "add", "--level", "3", "t1", "big", "build it", "70"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | level 3 | opened %s | by main\n" % NOW)

    def test_no_est(self):
        self.assertOk(self.af("todo", "add", "t1", "small", "fix it", "--level", "0"))
        self.assertEqual(self.todo(), "t1 | small | fix it | level 0 | opened %s | by main\n" % NOW)

    def test_no_level_is_as_before(self):
        self.assertOk(self.af("todo", "add", "t1", "big", "build it", "70"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | opened %s | by main\n" % NOW)

    def test_a_bad_level_is_refused(self):
        for bad in (["--level", "5"], ["--level", "-1"], ["--level", "x"], ["--level", ""], ["--level"]):
            with self.subTest(bad=bad):
                r = self.refused("todo", "add", "t1", "big", "build it", "70", *bad)
                self.assertIn("--level", r.stderr)


class TestTodoLevel(TodoCase):
    LINE = "t1 | big | build it | est 70m | guess 35m | level 1 | opened 2026-11-20 09:00 | by main | stage tests since 2026-11-20 09:10"

    def test_a_raise_replaces_in_place(self):
        self.write_todo(self.LINE, "t2 | small | other | est 5m | opened 2026-11-20 09:00 | by main")
        r = self.af("todo", "level", "t1", "3")
        self.assertOk(r)
        self.assertIn("todo level: t1 1 -> 3", r.stdout)
        self.assertEqual(self.todo().splitlines(), [self.LINE.replace("level 1", "level 3"),
                                                    "t2 | small | other | est 5m | opened 2026-11-20 09:00 | by main"])

    def test_a_missing_level_goes_where_todo_add_puts_it(self):
        self.write_todo("t1 | big | build it | est 70m | opened 2026-11-20 09:00 | by main | stage tests since 2026-11-20 09:10")
        r = self.af("todo", "level", "t1", "2")
        self.assertOk(r)
        self.assertIn("todo level: t1 - -> 2", r.stdout)
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | level 2 | opened 2026-11-20 09:00 | by main | stage tests since 2026-11-20 09:10\n")

    def test_after_the_guess_when_there_is_one(self):
        self.write_todo("t1 | big | build it | est 70m | guess 35m | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "level", "t1", "4"))
        self.assertEqual(self.todo(), "t1 | big | build it | est 70m | guess 35m | level 4 | opened 2026-11-20 09:00 | by main\n")

    def test_the_same_level_writes_nothing(self):
        self.write_todo(self.LINE)
        before = os.stat(self.repo.path("agent_todo.txt")).st_mtime_ns
        r = self.af("todo", "level", "t1", "1")
        self.assertOk(r)
        self.assertIn("todo level: t1 already level 1", r.stdout)
        self.assertEqual(self.todo(), self.LINE + "\n")
        self.assertEqual(os.stat(self.repo.path("agent_todo.txt")).st_mtime_ns, before)

    def test_lower_is_refused(self):
        self.write_todo(self.LINE.replace("level 1", "level 3"))
        r = self.refused("todo", "level", "t1", "2")
        self.assertIn("only goes up", r.stderr)

    def test_bad_input_is_refused(self):
        self.write_todo(self.LINE)
        for args in (["todo", "level", "nope", "2"], ["todo", "level", "t1", "5"],
                     ["todo", "level", "t1", "x"], ["todo", "level", "t1"]):
            with self.subTest(args=args):
                self.refused(*args)


class TestTodoDoneLevel(TodoCase):

    def done_line(self):
        rows = [l for l in (self.repo.read("agent_completed.txt") or "").splitlines() if l.strip()]
        self.assertEqual(len(rows), 1, rows)
        return rows[0]

    def test_the_level_is_the_last_key(self):
        self.write_todo("t1 | big | build it | est 70m | guess 35m | level 2 | opened 2026-11-20 09:00 | by main")
        self.assertOk(self.af("todo", "done", "t1", "--work", "60", "--type", "script", "--lane", "full"))
        self.assertTrue(self.done_line().endswith(" adds=- guess=35 level=2"), self.done_line())
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
        self.af("todo", "add", "lv", "big", "with a level", "60", "--level", "3", now="2026-11-02 14:00")
        self.add("nolv", "an old line", est=30)
        self.state("PARKED: a question | lv | since 2026-11-02 14:10")
        rows = self.rows()
        self.assertEqual(self.row(rows, task="lv")["Level"], "L3")
        self.assertEqual(self.row(rows, task="nolv")["Level"], "-")
        for r in rows:
            if r["Task"] not in ("lv", "nolv"):
                self.assertEqual(r["Level"], "-", r)

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
        return section(self.text(), "R8. Risk levels", "## B. Work")

    def test_it_sits_after_r7_and_nothing_is_renumbered(self):
        text = self.text()
        order = [text.index(h) for h in ("R7. Worktree file", "R8. Risk levels", "## B. Work", "W1. ")]
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
        for phrase in ("0 wording", "1 ui only", "2 simple logic", "3 heavy logic", "4 danger",
                       "dispatch", "--level", "agent-level.sh check", "raise", "only goes up",
                       "level3_paths", "level4_paths", "full lane", "reads the diff", "e2e",
                       "screenshots", "phone", "console clean", "owner not seen",
                       "failing test first", "table", "owner yes", "opus", "full suite once",
                       "real-data count", "dry-run", "rollback plan", "owner signs",
                       "check responsive", "lockfile", "todo level"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)

    def test_the_other_rules_point_at_it(self):
        text = self.text()
        for start, end in (("R1. ", "R2. "), ("W2. ", "W3. "), ("W4. ", "W5. "), ("W5. ", "W6. ")):
            with self.subTest(rule=start):
                self.assertIn("R8", section(text, start, end))

    def test_r1_keeps_size_and_adds_the_full_lane_for_3_and_4(self):
        r1 = section(self.text(), "R1. ", "R2. ")
        self.assertIn("Task size picks the lane", r1)
        self.assertIn("full lane", r1)
        self.assertRegex(r1, r"3 (and|or) 4")


class TestDispatchSkill(unittest.TestCase):

    def text(self):
        return read("skills", "dispatch", "SKILL.md")

    def test_the_todo_add_line_carries_the_level(self):
        line = [l for l in self.text().splitlines() if "agent-file.sh todo add" in l][0]
        self.assertIn("--level <n>", line)

    def test_the_task_manager_brief_has_a_level_line(self):
        brief = section(self.text(), "## Task manager brief", "## Cross-repo brief")
        self.assertTrue([l for l in brief.splitlines() if l.startswith("LEVEL:")], brief)

    def test_the_deputy_brief_carries_the_level_and_3_or_4_is_never_fast(self):
        step2 = section(self.text(), "\n2. ", "\n3. ")
        self.assertIn("level", step2.lower())
        self.assertIn("3 or 4", step2)

    def test_it_names_the_rule(self):
        self.assertIn("R8", self.text())


class TestMergeSkill(unittest.TestCase):

    def text(self):
        return read("skills", "merge", "SKILL.md")

    def test_the_check_runs_before_the_e2e(self):
        text = self.text()
        self.assertIn("agent-level.sh check", text)
        self.assertLess(text.index("agent-level.sh check"), text.index("agent-runtime.sh browser"))

    def test_it_says_declared_raise_and_level_0(self):
        text = self.text()
        for words in ("--declared", "RAISE", "todo level", "gate"):
            with self.subTest(words=words):
                self.assertIn(words, text)
        self.assertRegex(text, r"(?i)level 0[^\n]*skip[^\n]*E2E")

    def test_the_deputy_brief_gives_the_level(self):
        block = section(self.text(), "name: <name>", "todo done arguments:")
        self.assertIn("level: <n>", block)


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
        for words in ("agent-level.sh check", "--declared", "RAISE", "REQUIRED LEVEL"):
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
        for good, wrongs in (("38B", ("38A", "38C", "38D")), ("39D", ("39A", "39B", "39C"))):
            for wrong in wrongs:
                with self.subTest(wrong=wrong):
                    r = self.repo.run("agent-start.sh", "--answer", ANSWERS.replace(good, wrong))
                    self.assertEqual(r.returncode, 1)
                    self.assertIn("Q%s(R8)" % good[:2], r.stdout)

    def test_the_old_37_answers_no_longer_pass(self):
        r = self.repo.run("agent-start.sh", "--answer", ANSWERS.replace(" 38B 39D", ""))
        self.assertEqual(r.returncode, 1)

    def test_the_usage_says_39(self):
        src = read("bin", "agent-start.sh")
        self.assertIn("print the 39 quiz questions", src)
        self.assertEqual(src.count('--answer "1A 2D ... 39D"'), 2, "the header and the usage line")
        self.assertNotIn("... 37C", src)


class TestReadmeAndRelease(unittest.TestCase):

    def test_the_tree_lists_the_script(self):
        self.assertIn("bin/agent-level.sh", read("README.md"))

    def test_the_routing_section_names_the_level(self):
        part = section(read("README.md"), "## How a task is routed", "## One real day")
        self.assertIn("level", part.lower())
        self.assertIn("agent-level.sh", part)

    def test_the_quiz_count(self):
        self.assertIn("39-question quiz", read("README.md"))

    def test_release(self):
        ver = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        self.assertGreaterEqual(tuple(int(x) for x in ver.split(".")), (0, 36, 0))


if __name__ == "__main__":
    unittest.main()
