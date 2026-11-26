"""Structure of the rule files (requirements/md-slim-principles.md, D 12 and section 4).

The core is PRINCIPLES.md at the plugin root; beside it rules/*.md (22 files),
GLOSSARY.md and NOTICE.md. Each test names the file it reads; no helper glues
the files together.

    core          at most 100 lines and 1,300 words (wc -w)
    rule file     at most 70 lines, one "Read when:" line
    Read when     the core's "## Read when" list names every rules/*.md file,
                  and every file it names exists
    codes         each of the 44 rule codes is an anchor ("<code>. " opening a
                  line, after "#... " or "- ") in exactly one file of the core,
                  rules/ and GLOSSARY.md
    glossary      a term (**Term**:) is defined once
    proof folder  requirements/md-slim-principles/ keeps only the proof
                  material: proof.md, codes.md, compare.md, compare2.md, report.md
    cited codes   no skill, agent file, hook or script cites PRINCIPLES.md <code>
                  for a code whose anchor is in a rules file; a cited
                  rules/<file>.md <code> names the file that anchors the code
    two skills    close-case part C 3: a task manager reports into agent_state.txt;
                  dispatch: the two options when an urgent task needs a
                  non-urgent task's code (rules/routing.md, W9)
"""

import collections
import glob
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from scripthelp import ROOT  # noqa: E402

CORE_MAX_LINES = 100
CORE_MAX_WORDS = 1300
RULE_MAX_LINES = 70

CODES = ("P1 R1 R2 R3 R4 R5 R6 R7 R8 W1 W2 W3 W4 W5 W6 W7 W8 W9 W10 W11 W12 W13 W14 W15 "
         "W16 W17 W18 H1 H2 H3 H4 S1 S2 S3 S4 S5 S6 S7 S8 S9 E1 E2 E3 E4").split()

RULE_FILES = ["approval.md", "board.md", "branches.md", "checks.md", "close-case.md", "context.md",
              "cross-repo.md", "files.md", "human.md", "map.md", "output.md", "questions.md",
              "resources.md", "roles.md", "routing.md", "setup.md", "tests.md", "time.md",
              "traps.md", "ui.md", "watch.md", "worktrees.md"]

PROOF_FILES = ["codes.md", "compare.md", "compare2.md", "proof.md", "report.md"]

ANCHOR = re.compile(r"^(?:#+ |- )?([PRWHSE]\d+)\. ")
TERM = re.compile(r"^\*\*(.+?)\*\*:")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def core_problems(text):
    """What is wrong with a core text; [] when it fits."""
    out = []
    lines = len(text.splitlines())
    words = len(text.split())
    if lines > CORE_MAX_LINES:
        out.append("core has %d lines, at most %d" % (lines, CORE_MAX_LINES))
    if words > CORE_MAX_WORDS:
        out.append("core has %d words, at most %d" % (words, CORE_MAX_WORDS))
    return out


def rule_file_problems(name, text):
    out = []
    lines = text.splitlines()
    if len(lines) > RULE_MAX_LINES:
        out.append("%s has %d lines, at most %d" % (name, len(lines), RULE_MAX_LINES))
    if not any(line.startswith("Read when:") for line in lines):
        out.append("%s has no 'Read when:' line" % name)
    return out


def read_when_names(core_text):
    """The rules/<file>.md names in the core's "## Read when" section."""
    lines = core_text.splitlines()
    start = lines.index("## Read when")
    body = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    return set(re.findall(r"rules/[a-z0-9-]+\.md", "\n".join(body)))


def anchors(texts):
    """{code: [(file, line number)]} over {file: text}."""
    out = collections.defaultdict(list)
    for name, text in texts.items():
        for i, line in enumerate(text.splitlines(), 1):
            m = ANCHOR.match(line)
            if m:
                out[m.group(1)].append((name, i))
    return out


def anchor_problems(texts):
    found = anchors(texts)
    out = []
    for code in CODES:
        if len(found.get(code, [])) != 1:
            out.append("%s anchored %d times: %s" % (code, len(found.get(code, [])), found.get(code, [])))
    return out


def term_problems(text):
    terms = [TERM.match(line).group(1) for line in text.splitlines() if TERM.match(line)]
    return ["%s defined %d times" % (t, n) for t, n in collections.Counter(terms).items() if n > 1]


def rule_texts():
    """{"PRINCIPLES.md": text, "rules/<f>.md": text, ..., "GLOSSARY.md": text}."""
    out = {"PRINCIPLES.md": read("PRINCIPLES.md")}
    for path in sorted(glob.glob(os.path.join(ROOT, "rules", "*.md"))):
        out["rules/" + os.path.basename(path)] = read("rules", os.path.basename(path))
    out["GLOSSARY.md"] = read("GLOSSARY.md")
    return out


class TestTheFilesAreInPlace(unittest.TestCase):

    def test_the_core_and_its_neighbours(self):
        for name in ("PRINCIPLES.md", "GLOSSARY.md", "NOTICE.md"):
            with self.subTest(name=name):
                self.assertTrue(os.path.isfile(os.path.join(ROOT, name)), name)

    def test_the_22_rule_files(self):
        have = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "rules", "*.md")))
        self.assertEqual(have, RULE_FILES)

    def test_the_core_starts_with_its_heading(self):
        self.assertEqual(read("PRINCIPLES.md").splitlines()[0], "# PRINCIPLES")

    def test_the_notice_keeps_the_mit_text(self):
        text = read("NOTICE.md")
        self.assertIn("Section E is adapted from i-have-adhd (https://github.com/ayghri/i-have-adhd) "
                      "under the MIT License.", text)
        self.assertIn("Copyright (c) 2026 Ayoub Ghriss", text)
        self.assertIn("THE SOFTWARE IS PROVIDED \"AS IS\"", text)


class TestTheCore(unittest.TestCase):

    def test_the_core_fits(self):
        self.assertEqual(core_problems(read("PRINCIPLES.md")), [])

    def test_a_core_of_101_lines_fails(self):
        self.assertEqual(core_problems("\n".join(["- x"] * 101) + "\n"),
                         ["core has 101 lines, at most 100"])

    def test_a_core_of_100_lines_passes(self):
        self.assertEqual(core_problems("\n".join(["- x"] * 100) + "\n"), [])

    def test_a_core_of_1301_words_fails(self):
        self.assertEqual(core_problems(" ".join(["word"] * 1301) + "\n"),
                         ["core has 1301 words, at most 1300"])


# answer bd1ecc18 (1): the rules block the start prints (the core, the output rules
# from "E1. Shape", the PATHS line, the longest READ NOW line) stays under 9,500
# characters with a 120-character plugin path; tests/test_agent_start.py
# TestTheRealSizes measures the real output.
BLOCK_CAP = 9500
LONGEST_PATH = "/" + "p" * 119
READ_LINES = [  # the READ NOW lines of tests/test_agent_start.py
    "READ NOW (main manager): rules/human.md, rules/routing.md, rules/approval.md, rules/checks.md, "
    "rules/branches.md, rules/worktrees.md, rules/watch.md",
    "READ NOW (task manager): rules/tests.md, rules/checks.md, rules/watch.md, rules/context.md, rules/resources.md",
    "READ NOW (human-direct session): rules/roles.md, then rules/tests.md, rules/checks.md, rules/watch.md, "
    "rules/context.md, rules/resources.md",
    "READ NOW: the quiz already passed in this session; a worker, deputy or reviewer reads nothing "
    "at start: its brief and its agent file name what to read"]
BLOCK_LINES = ["=== rules/output.md ===",
               "PATHS: rules/*.md, GLOSSARY.md and NOTICE.md are under %s/" % LONGEST_PATH,
               max(READ_LINES, key=len)]


def block_problems(core, output):
    body = output[output.index("E1. Shape"):]
    size = len(core) + len(body) + sum(len(l) + 1 for l in BLOCK_LINES)
    return [] if size <= BLOCK_CAP else ["rules block is %d characters, at most %d" % (size, BLOCK_CAP)]


class TestTheRulesBlockBudget(unittest.TestCase):

    def test_the_core_and_the_output_rules_fit_the_block(self):
        self.assertEqual(block_problems(read("PRINCIPLES.md"), read("rules", "output.md")), [])

    def test_a_longer_core_fails(self):
        core = read("PRINCIPLES.md") + "- " + "x" * 600 + "\n"
        self.assertEqual(len(block_problems(core, read("rules", "output.md"))), 1)


class TestTheRuleFiles(unittest.TestCase):

    def test_each_rule_file_fits_and_says_when_to_read_it(self):
        for name in RULE_FILES:
            with self.subTest(name=name):
                self.assertEqual(rule_file_problems("rules/" + name, read("rules", name)), [])

    def test_a_rule_file_of_71_lines_fails(self):
        text = "# X\nRead when: x.\n" + "\n".join(["- y"] * 69) + "\n"
        self.assertEqual(rule_file_problems("rules/x.md", text), ["rules/x.md has 71 lines, at most 70"])

    def test_a_rule_file_without_read_when_fails(self):
        self.assertEqual(rule_file_problems("rules/x.md", "# X\n- y\n"),
                         ["rules/x.md has no 'Read when:' line"])

    def test_the_glossary_says_when_to_read_it(self):
        self.assertTrue(any(l.startswith("Read when:") for l in read("GLOSSARY.md").splitlines()))


class TestTheReadWhenList(unittest.TestCase):

    def test_every_rule_file_is_named(self):
        named = read_when_names(read("PRINCIPLES.md"))
        for name in RULE_FILES:
            with self.subTest(name=name):
                self.assertIn("rules/" + name, named)

    def test_every_named_file_exists(self):
        for path in sorted(read_when_names(read("PRINCIPLES.md"))):
            with self.subTest(path=path):
                self.assertTrue(os.path.isfile(os.path.join(ROOT, path)), path)

    def test_a_missing_name_is_seen(self):
        core = "# P\n\n## Read when\n- a test: `rules/tests.md`\n\n## Next\n- `rules/ui.md`\n"
        self.assertEqual(read_when_names(core), {"rules/tests.md"})


class TestTheCodes(unittest.TestCase):

    def test_each_code_is_an_anchor_in_exactly_one_file(self):
        self.assertEqual(anchor_problems(rule_texts()), [])

    def test_there_are_44_codes(self):
        self.assertEqual(len(CODES), 44)
        self.assertEqual(len(set(CODES)), 44)

    def test_a_doubled_anchor_fails(self):
        texts = rule_texts()
        texts["rules/extra.md"] = "# X\nRead when: x.\n\nW13. Close case\n- y\n"
        self.assertEqual(anchor_problems(texts),
                         ["W13 anchored 2 times: [('rules/close-case.md', 4), ('rules/extra.md', 4)]"])

    def test_a_missing_anchor_fails(self):
        texts = rule_texts()
        texts["rules/close-case.md"] = texts["rules/close-case.md"].replace("W13. ", "W13: ")
        self.assertIn("W13 anchored 0 times: []", anchor_problems(texts))

    def test_the_anchors_sit_where_codes_md_says(self):
        # requirements/md-slim-principles/codes.md: the primary file of each code
        table = read("requirements", "md-slim-principles", "codes.md")
        found = anchors(rule_texts())
        for line in table.splitlines():
            m = re.match(r"^\| ([PRWHSE]\d+) \| ([^|]+?) \| (\d+) \|", line)
            if not m:
                continue
            with self.subTest(code=m.group(1)):
                self.assertEqual(found[m.group(1)][0][0], m.group(2))


class TestTheGlossary(unittest.TestCase):

    def test_a_term_is_defined_once(self):
        self.assertEqual(term_problems(read("GLOSSARY.md")), [])

    def test_a_doubled_term_fails(self):
        self.assertEqual(term_problems("**Owner**: a.\n**Owner**: b.\n"), ["Owner defined 2 times"])


class TestTheProofFolder(unittest.TestCase):

    def test_only_the_proof_material_stays(self):
        folder = os.path.join(ROOT, "requirements", "md-slim-principles")
        self.assertEqual(sorted(os.listdir(folder)), PROOF_FILES)


CITE = re.compile(r"PRINCIPLES(?:\.md)? ((?:[PRWHSE]\d+)(?:, (?:[PRWHSE]\d+))*)")
PART = re.compile(r"^(?:#+ |- )?([PRWHSE]\d+) \(")
CITE_RULE = re.compile(r"(rules/[a-z0-9-]+\.md) ((?:[PRWHSE]\d+)(?:, (?:[PRWHSE]\d+))*)")


def cited_files():
    out = []
    for top in ("skills", "agents", "bin", "hooks"):
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, top)):
            for name in files:
                if name.endswith((".md", ".sh", ".py", ".json")):
                    out.append(os.path.relpath(os.path.join(dirpath, name), ROOT))
    return sorted(out)


class TestTheCitedCodes(unittest.TestCase):

    def homes(self):
        return {code: places[0][0] for code, places in anchors(rule_texts()).items()}

    def test_no_principles_cite_of_a_code_that_moved(self):
        homes = self.homes()
        bad = []
        for path in cited_files():
            for i, line in enumerate(read(path).splitlines(), 1):
                for m in CITE.finditer(line):
                    for code in m.group(1).split(", "):
                        if homes.get(code) != "PRINCIPLES.md":
                            bad.append("%s:%d %s (lives in %s)" % (path, i, code, homes.get(code)))
        self.assertEqual(bad, [])

    def parts(self):
        """{code: {files}}: the file of its anchor plus every file that opens a part of it
        ("R8 (owner approval)", "S8 (cont.)": codes.md, the "also" column)."""
        out = collections.defaultdict(set)
        for code, file in self.homes().items():
            out[code].add(file)
        for name, text in rule_texts().items():
            for line in text.splitlines():
                m = PART.match(line)
                if m:
                    out[m.group(1)].add(name)
        return out

    def test_a_rules_cite_names_a_file_of_its_code(self):
        parts = self.parts()
        bad = []
        for path in cited_files():
            for i, line in enumerate(read(path).splitlines(), 1):
                for m in CITE_RULE.finditer(line):
                    for code in m.group(2).split(", "):
                        if code in parts and m.group(1) not in parts[code]:
                            bad.append("%s:%d %s %s (lives in %s)" % (path, i, m.group(1), code,
                                                                      ", ".join(sorted(parts[code]))))
        self.assertEqual(bad, [])

    def test_a_part_of_a_code_counts(self):
        # rules/approval.md opens "R8 (owner approval)": a cite "rules/approval.md R8" is right
        self.assertIn("rules/approval.md", self.parts()["R8"])
        self.assertNotIn("rules/ui.md", self.parts()["R8"])

    def test_the_close_case_line_names_its_rule_file(self):
        # section 4: grep -rn 'PRINCIPLES.md W13' skills agents bin finds nothing
        for path in cited_files():
            with self.subTest(path=path):
                self.assertNotIn("PRINCIPLES.md W13", read(path))
        title = [l for l in read("skills", "close-case", "SKILL.md").splitlines() if l.startswith("# ")][0]
        self.assertIn("rules/close-case.md", title)


class TestTheTwoSkills(unittest.TestCase):

    def part(self, text, start, end):
        lines = text.splitlines()
        b = next(i for i, l in enumerate(lines) if l.startswith(start))
        e = next((i for i in range(b + 1, len(lines)) if lines[i].startswith(end)), len(lines))
        return "\n".join(lines[b:e])

    def test_close_case_part_c_reports_into_the_state_file(self):
        c = self.part(read("skills", "close-case", "SKILL.md"), "## C.", "## ")
        step3 = [l for l in c.splitlines() if l.startswith("3. ")][0]
        self.assertIn("agent_state.txt", step3)
        self.assertIn("agent-file.sh state add", step3)
        self.assertIn("task manager", step3)
        # a human-direct session keeps SendMessage (rules/close-case.md, W13)
        self.assertIn("human-direct", step3)
        self.assertIn("SendMessage", step3)

    def test_dispatch_names_the_two_options(self):
        text = read("skills", "dispatch", "SKILL.md")
        line = [l for l in text.splitlines() if "cannot ship alone" in l][0]
        self.assertIn("(ship them together, or move that part into the urgent task)", line)
        self.assertIn("never guess", line)


if __name__ == "__main__":
    unittest.main()
