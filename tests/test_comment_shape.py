"""Failing tests for comment-shape: a comment-only change is a fifth A shape (R8).

check-blocks (2026-11-25): the shapes stay; a comment-only file is now kind "text" (no BUILD),
read back as the old letter A by tests/test_risk_levels.py old_letter(). The R8 line test moved
to tests/test_check_rules.py.

Written by the task manager before any code. The rules: requirements/comment-shape.md
(owner rules yes 2026-11-24: all 6 families of table B, decisions D1-D7). "rN" in a test
name is row N of its table A, C1-C5 its table C (directives).

CONTRACT (bin/agent_level.py; PRINCIPLES.md R8 level 0 line)

  Applies to a modified file (not new, deleted, binary or a symlink) whose extension is in
  table B, after the path rules (built-in L4, level4_paths, level3_paths) and the style,
  asset and text file rules. Lex old (merge base) and new (working tree):
      same code view, plain comments differ    -> "<path>: L0 comment only"
      same code view, only blank lines or trailing white space differ -> "<path>: L0 whitespace only"
      else, or the lexer is unsure              -> today's level (the rules before this task)
  Code view: plain comments removed (an inline block comment becomes one space), trailing
  white space dropped, blank lines dropped; a line that starts inside a multi-line string,
  heredoc or block scalar stays as it is; directive comments (C1-C5) stay in it.
  Guards, today's level: a comment or blank line right after a code line ending in "\"
  (old or new); a comment ending in "\"; a .go file with import "C".
  PRINCIPLES.md R8 "- 0 wording:" line names "comment-only change", <= 200 chars.

Worker 1 (core, py sh yaml conf, R8):
    TestHashShape TestHashStrings TestHashDirectives TestHashGuards TestScope TestTheRuleLine
Worker 2 (slash, markup):
    TestSlashShape TestSlashStrings TestSlashDirectives TestMarkup
Both keep tests/test_risk_levels.py green.
"""

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptRepo  # noqa: E402
import test_risk_levels as trl  # noqa: E402

CO = "comment only"
WS = "whitespace only"
CODE = ("C", "code change")
COMPONENT = ("B", "component file")   # a UI component file is B at most, never C (R8)
COMPONENT_EXT = (".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte")


class ShapeCase(trl.LevelCase):

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
        """want: (level, reason); cases: (path, before, after) each in a fresh project."""
        for i, (path, before, after) in enumerate(cases):
            with self.subTest(path=path, before=before[:60], after=after[:60]):
                if i:
                    self.fresh()
                exp = COMPONENT if want == CODE and path.endswith(COMPONENT_EXT) else want
                self.assertEqual(self.got(path, before, after), exp)

    def swap(self, want, path, plain, directives, head="", tail=""):
        """Each directive in place of the plain comment: head + plain + tail -> head + d + tail."""
        self.each(want, [(path, head + plain + "\n" + tail, head + d + "\n" + tail) for d in directives])


# ================================================================ worker 1: # families


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
        self.each(("A", "text change"), [
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
        self.each(("A", "text change"), [("bin/a.sh", 'echo "a \\" # b"\n', 'echo "a \\" # c"\n')])
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
        self.each(("A", "text change"), [
            ("ci/a.yml", 'a: ["x # y", 1]\n', 'a: ["x # z", 1]\n'),
            ("ci/a.yml", "b: 'x # y'\n", "b: 'x # z'\n"),
            # the apostrophe in a plain value opens no string, so the next quote still does
            ("ci/a.yml", "a: it's here\nb: 'x # y'\n", "a: it's here\nb: 'x # z'\n"),
        ])

    def test_yaml_an_apostrophe_inside_a_plain_value(self):
        self.each(("A", CO), [("ci/a.yml", "a: it's here\n# note\nb: 1\n", "a: it's here\n# note 2\nb: 1\n")])


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


# ================================================================ worker 2: slash and markup families


SLASH_EXT = [".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx", ".dart", ".java", ".kt",
             ".kts", ".swift", ".go", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh"]


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
        self.each(("A", "text change"), [("src/a.js", 'const u = "a // b";\n', 'const u = "a // c";\n')])
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


MARKUP_DIRECTIVES = [
    "<!--[if IE]><p>x</p><![endif]-->", '<!--#include file="a"-->', "<!--more-->",
    "<!-- ko if: x -->", "<!-- /ko -->", "<!-- build:js a.js -->", "<!-- endbuild -->",
    "<!-- inject:js -->", "<!-- endinject -->", "<!-- htmlmin:ignore -->",
    "<!-- prettier-ignore -->", "<!-- Copyright 2026 Acme -->",
]


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


# ================================================================ after review (bounce 1)
# The Opus reviewer proved false L0 cases (requirements/comment-shape.md section G, f1-f15).
# Worker 1: TestReviewCore. Worker 2: TestReviewSlash TestReviewMarkup.


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
        # the hidden part is string text: today's level is a text change, never "comment only"
        self.each(("A", "text change"), [
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
        self.each(("A", "text change"), [
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


# ================================================================ after re-review (bounce 2)
# requirements/comment-shape.md section G rows g1-g5. Worker 1: TestReview2Core. Worker 2: TestReview2Slash.


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


# ================================================================ final check (bounce 3)
# requirements/comment-shape.md section G rows h1-h2. Worker 1: test_h1. Worker 2: test_h2.


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


if __name__ == "__main__":
    unittest.main()
