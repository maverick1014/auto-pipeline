"""Failing tests for plugin-slim: the release script. Written by the task
manager, before any code. Rules: requirements/plugin-slim.md, section 5 (rules
table) and 5b (exact output).

CONTRACT
  bin/agent-release.sh      thin bash entry (executable), runs the logic:
  bin/agent_release.py      Python 3.9, standard library only

  agent-release.sh --list                 the ship set, one per line, in order
  agent-release.sh --dry-run [--from R]   prints the plan, writes no ref
  agent-release.sh [--from R]             builds; local branch `release` moves
  agent-release.sh --push [--from R]      fetch origin release, build, push

  The repo is the folder above the script's own bin/ (never the cwd). The
  release tree is built from a commit (default HEAD), never from the work
  tree. Release tip = refs/remotes/origin/release when it exists, else
  refs/heads/release, else none.

Every fixture is a throwaway git repo with the two script files copied into
its bin/, and HOME pointing at an empty folder (no global git config, no
signing). Nothing here touches this repo's refs: the one test that runs on the
real repo uses --dry-run and compares every ref before and after.
"""

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "bin", "agent-release.sh")
LOGIC = os.path.join(ROOT, "bin", "agent_release.py")

SHIP = [".claude-plugin", "hooks", "bin", "skills", "agents", "PRINCIPLES.md"]


# ---------------------------------------------------------------- helpers

def write(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = text.encode("utf-8") if isinstance(text, str) else text
    with open(path, "wb") as fh:
        fh.write(data)
    if mode is not None:
        os.chmod(path, mode)


def plugin_json(version):
    return json.dumps({"name": "auto-pipeline", "version": version}, indent=2) + "\n"


BASE_FILES = {
    ".claude-plugin/plugin.json": plugin_json("0.40.0"),
    ".claude-plugin/marketplace.json": json.dumps({
        "name": "auto-pipeline", "owner": {"name": "t"},
        "plugins": [{"name": "auto-pipeline", "source": {
            "source": "url", "url": "https://example.invalid/r.git", "ref": "release"}}]}) + "\n",
    # JSON-escaped quote form, exactly as the real hooks.json writes it
    "hooks/hooks.json": json.dumps({"hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}\"/bin/agent-start.sh"}]}]}},
        indent=2) + "\n",
    "bin/agent-roots.sh": 'PLUGIN_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)\n',
    "bin/agent.conf.default": "x=1\n",
    "bin/tool.py": (
        "import os\n"
        "HERE = os.path.dirname(os.path.abspath(__file__))\n"
        "CONF = os.path.join(HERE, \"agent.conf.default\")\n"
        "PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), \"agent-city-assets\")\n"),
    "skills/demo/SKILL.md": (
        "---\nname: demo\n---\n"
        "Run `${CLAUDE_PLUGIN_ROOT}/bin/agent-start.sh` first.\n"
        "Then run ${CLAUDE_PLUGIN_ROOT}/bin/agent-start.sh.\n"
        "# rules: requirements/r.md, tests/t.txt and README.md say why\n"),
    "agents/worker.md": "Use ${CLAUDE_PLUGIN_ROOT}/bin/agent-start.sh\n",
    "PRINCIPLES.md": "# PRINCIPLES\n",
    "README.md": "# readme\n",
    "CLAUDE.md": "Run ./bin/agent-start.sh first.\n",
    "AGENTS.md": "Run ./bin/agent-start.sh first.\n",
    "agent.conf": "language=en\n",
    "agent_todo.txt": "",
    "tests/t.txt": "t\n",
    "mock/m.html": "<p>m</p>\n",
    "requirements/r.md": "# r\n",
    ".gitignore": "__pycache__/\n",
}
EXEC_FILES = {
    "bin/agent-start.sh": (
        "#!/usr/bin/env bash\n"
        ". \"$(dirname \"$0\")/agent-roots.sh\"\n"
        "cat \"$PLUGIN_ROOT/PRINCIPLES.md\"\n"
        "cp \"$PLUGIN_ROOT/bin/agent.conf.default\" /dev/null\n"
        "ls \"$PLUGIN_ROOT/bin/agent-city-assets\"\n"),
}
# a binary file that happens to hold a plugin-root path: never scanned
BINARY = ("bin/agent-city-assets/a.glb", b"glTF\x00\x01\x02$PLUGIN_ROOT/README.md\x00")


class Fixture(unittest.TestCase):
    """A throwaway plugin repo on branch main, pushed to a bare origin."""

    def setUp(self):
        if not os.path.exists(SCRIPT):
            self.fail("bin/agent-release.sh does not exist yet. Write it.")
        if not os.path.exists(LOGIC):
            self.fail("bin/agent_release.py does not exist yet. Write it.")
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="agent_release_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.home = os.path.join(self.base, "home")
        os.makedirs(self.home)
        self.repo = os.path.join(self.base, "repo")
        self.origin = os.path.join(self.base, "origin.git")
        os.makedirs(self.repo)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@t.t")
        self.git("config", "user.name", "t")
        self.git("config", "commit.gpgsign", "false")
        for rel, text in BASE_FILES.items():
            write(self.p(rel), text, 0o644)
        for rel, text in EXEC_FILES.items():
            write(self.p(rel), text, 0o755)
        write(self.p(BINARY[0]), BINARY[1], 0o644)
        self.install_script(self.repo)
        self.commit("seed")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.origin], check=True,
                       capture_output=True, env=self.env())
        self.git("remote", "add", "origin", self.origin)
        self.git("push", "-q", "origin", "main")

    # ---- fixture helpers ----

    def env(self):
        env = dict(os.environ)
        for key in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "AGENT_ROLE",
                    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            env.pop(key, None)
        env["HOME"] = getattr(self, "home", env.get("HOME", ""))
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        return env

    def p(self, *parts):
        return os.path.join(self.repo, *parts)

    def git(self, *args, cwd=None, check=True):
        r = subprocess.run(["git", "-C", cwd or self.repo] + list(args),
                           capture_output=True, text=True, env=self.env())
        if check and r.returncode != 0:
            self.fail("git %s failed: %s" % (" ".join(args), r.stderr))
        return r.stdout.strip()

    def install_script(self, root):
        for src in (SCRIPT, LOGIC):
            dst = os.path.join(root, "bin", os.path.basename(src))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def short(self, ref):
        return self.git("rev-parse", "--short", ref)

    def set_version(self, version):
        write(self.p(".claude-plugin", "plugin.json"), plugin_json(version))

    def refs(self, cwd=None):
        return self.git("for-each-ref", "--format=%(refname) %(objectname)", cwd=cwd)

    def run_release(self, *args, root=None):
        root = root or self.repo
        # cwd is the temp base, never the repo: the script finds its repo itself
        return subprocess.run([os.path.join(root, "bin", "agent-release.sh")] + list(args),
                              cwd=self.base, capture_output=True, text=True,
                              env=self.env(), input="", timeout=120)

    def assertExit(self, result, code):
        self.assertEqual(result.returncode, code,
                         "exit %s, want %s\nstdout:\n%s\nstderr:\n%s"
                         % (result.returncode, code, result.stdout, result.stderr))

    def ship_tree(self, ref):
        """{path: (mode, blob)} of the ship set in a commit."""
        out = {}
        listing = self.git("ls-tree", "-r", ref, "--", *SHIP)
        for line in listing.splitlines():
            meta, path = line.split("\t", 1)
            mode, _kind, blob = meta.split()
            out[path] = (mode, blob)
        return out

    def full_tree(self, ref):
        out = {}
        for line in self.git("ls-tree", "-r", ref).splitlines():
            meta, path = line.split("\t", 1)
            mode, _kind, blob = meta.split()
            out[path] = (mode, blob)
        return out

    def build(self, *args):
        r = self.run_release(*args)
        self.assertExit(r, 0)
        return r


# ---------------------------------------------------------------- rule 1

class TestShipList(unittest.TestCase):
    def test_list_prints_the_six_paths_in_order(self):
        if not os.path.exists(SCRIPT):
            self.fail("bin/agent-release.sh does not exist yet. Write it.")
        r = subprocess.run([SCRIPT, "--list"], cwd=HERE, capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), SHIP)

    def test_the_entry_is_executable_and_tracked_as_such(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK), "bin/agent-release.sh is not executable")
        mode = subprocess.run(["git", "-C", ROOT, "ls-files", "-s", "bin/agent-release.sh"],
                              capture_output=True, text=True).stdout.split(" ")[0]
        if mode:  # tracked once committed
            self.assertEqual(mode, "100755")


# ---------------------------------------------------------------- rules 2-8, 10-12

class TestRefusals(Fixture):
    def test_not_a_checkout(self):
        plain = os.path.join(self.base, "cache", "0.39.0")
        self.install_script(plain)
        r = self.run_release("--dry-run", root=plain)
        self.assertExit(r, 2)
        self.assertIn("agent-release.sh: not a git checkout: %s" % plain, r.stderr)

    def test_unknown_option(self):
        r = self.run_release("--bogus")
        self.assertExit(r, 2)
        self.assertIn("unknown option --bogus", r.stderr)

    def test_unknown_from_ref(self):
        before = self.refs()
        r = self.run_release("--dry-run", "--from", "no-such-ref")
        self.assertExit(r, 1)
        self.assertIn("agent-release.sh: unknown ref no-such-ref", r.stderr)
        self.assertEqual(self.refs(), before)

    def test_a_missing_ship_path(self):
        shutil.rmtree(self.p("hooks"))
        sha = self.commit("drop hooks")
        r = self.run_release("--dry-run")
        self.assertExit(r, 1)
        self.assertIn("agent-release.sh: hooks is missing in %s" % self.short(sha), r.stderr)

    def test_no_valid_version(self):
        for bad in ("v1", "", "1.x"):
            with self.subTest(version=bad):
                self.set_version(bad)
                self.commit("bad version %r" % bad)
                r = self.run_release("--dry-run")
                self.assertExit(r, 1)
                self.assertIn("agent-release.sh: no valid version in .claude-plugin/plugin.json of",
                              r.stderr)

    def test_a_version_that_is_not_higher_is_refused(self):
        self.build()
        tip = self.git("rev-parse", "release")
        write(self.p("bin", "agent.conf.default"), "x=2\n")
        self.commit("change, no bump")
        r = self.run_release()
        self.assertExit(r, 1)
        self.assertIn("agent-release.sh: version 0.40.0 is not higher than release 0.40.0: "
                      "bump .claude-plugin/plugin.json first", r.stderr)
        self.assertEqual(self.git("rev-parse", "release"), tip)

    def test_a_lower_version_is_refused(self):
        self.build()
        self.set_version("0.39.9")
        self.commit("lower")
        r = self.run_release("--dry-run")
        self.assertExit(r, 1)
        self.assertIn("version 0.39.9 is not higher than release 0.40.0", r.stderr)

    def test_versions_compare_as_numbers(self):
        self.set_version("0.40.9")
        self.commit("0.40.9")
        self.build()
        self.set_version("0.40.10")
        self.commit("0.40.10")
        r = self.build()
        self.assertIn("release 0.40.10:", r.stdout)


class TestDryRun(Fixture):
    def test_first_release_plan(self):
        before = self.refs()
        r = self.run_release("--dry-run")
        self.assertExit(r, 0)
        out = r.stdout.splitlines()
        self.assertIn("from %s version 0.40.0" % self.short("HEAD"), out)
        self.assertIn("release tip: none", out)
        files = self.git("ls-tree", "-r", "-l", "HEAD", "--", *SHIP).splitlines()
        size = sum(int(line.split("\t")[0].split()[3]) for line in files)
        self.assertIn("ship: %d files, %d bytes" % (len(files), size), out)
        top = self.git("ls-tree", "--name-only", "HEAD").splitlines()
        left = sorted(n for n in top if n not in SHIP)
        self.assertIn("left out: " + " ".join(left), out)
        self.assertTrue(any(re.fullmatch(r"reads check: \d+ ok, \d+ skipped \(variable\)", l)
                            for l in out), r.stdout)
        self.assertIn("would commit release 0.40.0", out)
        self.assertEqual(self.refs(), before, "--dry-run wrote a ref")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_plan_names_the_tip(self):
        self.build()
        tip = self.short("release")
        self.set_version("0.40.1")
        self.commit("bump")
        r = self.run_release("--dry-run")
        self.assertExit(r, 0)
        self.assertIn("release tip: %s version 0.40.0" % tip, r.stdout.splitlines())
        self.assertIn("would commit release 0.40.1", r.stdout.splitlines())

    def test_nothing_left_out(self):
        for name in ("README.md", "CLAUDE.md", "AGENTS.md", "agent.conf", "agent_todo.txt",
                     ".gitignore"):
            os.remove(self.p(name))
        for name in ("tests", "mock", "requirements"):
            shutil.rmtree(self.p(name))
        self.commit("ship set only")
        r = self.run_release("--dry-run")
        self.assertExit(r, 0)
        self.assertIn("left out: none", r.stdout.splitlines())


class TestBuild(Fixture):
    def test_first_release_is_a_root_commit_of_the_ship_set(self):
        head = self.git("rev-parse", "HEAD")
        r = self.build()
        rel = self.git("rev-parse", "release")
        self.assertIn("release 0.40.0: %s (from %s)" % (self.short(rel), self.short(head)),
                      r.stdout.splitlines())
        self.assertIn("git push origin release", r.stdout)
        self.assertEqual(self.git("log", "-1", "--format=%s", "release"),
                         "release 0.40.0 from %s" % self.short(head))
        self.assertEqual(self.git("log", "-1", "--format=%P", "release"), "", "not a root commit")
        self.assertEqual(sorted(self.git("ls-tree", "--name-only", "release").splitlines()),
                         sorted(SHIP))
        # main, the index and the work tree are untouched
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), "main")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_the_release_tree_is_the_ship_set_of_the_commit_byte_for_byte(self):
        self.build()
        self.assertEqual(self.full_tree("release"), self.ship_tree("HEAD"))

    def test_exec_bits_are_kept(self):
        self.build()
        tree = self.full_tree("release")
        self.assertEqual(tree["bin/agent-start.sh"][0], "100755")
        self.assertEqual(tree["bin/agent-release.sh"][0], "100755")
        self.assertEqual(tree["bin/agent.conf.default"][0], "100644")

    def test_local_edits_untracked_and_ignored_files_never_ship(self):
        committed = self.ship_tree("HEAD")["bin/agent-start.sh"]
        with open(self.p("bin", "agent-start.sh"), "a") as fh:
            fh.write('cat "$PLUGIN_ROOT/README.md"\n')     # a bad read, not committed
        write(self.p("bin", "new.sh"), "echo new\n", 0o755)  # untracked
        write(self.p("bin", "__pycache__", "x.pyc"), b"\x00pyc")  # ignored
        r = self.build()
        self.assertNotIn("which is not shipped", r.stderr)
        tree = self.full_tree("release")
        self.assertEqual(tree["bin/agent-start.sh"], committed)
        self.assertNotIn("bin/new.sh", tree)
        self.assertNotIn("bin/__pycache__/x.pyc", tree)

    def test_next_release_sits_on_the_previous_one(self):
        self.build()
        first = self.git("rev-parse", "release")
        write(self.p("PRINCIPLES.md"), "# PRINCIPLES\nmore\n")
        self.set_version("0.40.1")
        head = self.commit("0.40.1")
        self.build()
        self.assertEqual(self.git("log", "-1", "--format=%P", "release"), first)
        self.assertEqual(self.git("log", "-1", "--format=%s", "release"),
                         "release 0.40.1 from %s" % self.short(head))
        self.assertEqual(self.full_tree("release"), self.ship_tree("HEAD"))

    def test_up_to_date(self):
        self.build()
        tip = self.git("rev-parse", "release")
        write(self.p("README.md"), "# readme, changed\n")   # not shipped: tree is the same
        self.commit("readme only")
        for args in ((), ("--dry-run",)):
            with self.subTest(args=args):
                r = self.build(*args)
                self.assertIn("release up to date: 0.40.0 (%s)" % self.short(tip),
                              r.stdout.splitlines())
                self.assertEqual(self.git("rev-parse", "release"), tip)

    def test_from_an_older_commit(self):
        old = self.git("rev-parse", "HEAD")
        write(self.p("PRINCIPLES.md"), "# newer\n")
        self.set_version("0.41.0")
        self.commit("newer")
        r = self.build("--from", old)
        self.assertIn("from %s version 0.40.0" % self.short(old), r.stdout.splitlines())
        self.assertEqual(self.full_tree("release"), self.ship_tree(old))

    def test_the_tip_is_origins_release_when_it_exists(self):
        self.build("--push")
        pushed = self.git("rev-parse", "release")
        self.git("branch", "-D", "release")
        self.set_version("0.40.1")
        self.commit("bump")
        self.build()
        self.assertEqual(self.git("log", "-1", "--format=%P", "release"), pushed)


class TestPush(Fixture):
    def test_push_puts_the_release_on_origin(self):
        r = self.build("--push")
        local = self.git("rev-parse", "release")
        remote = self.git("rev-parse", "refs/heads/release", cwd=self.origin)
        self.assertEqual(remote, local)
        # main on origin is untouched: release goes first, main is pushed by the caller
        self.assertEqual(self.git("rev-parse", "refs/heads/main", cwd=self.origin),
                         self.git("rev-parse", "origin/main"))

    def test_push_fetches_origin_first(self):
        # another machine released 0.40.0 already
        other = os.path.join(self.base, "other")
        subprocess.run(["git", "clone", "-q", "-b", "main", self.origin, other], check=True,
                       capture_output=True, env=self.env())
        self.git("config", "user.email", "o@o.o", cwd=other)
        self.git("config", "user.name", "o", cwd=other)
        self.git("config", "commit.gpgsign", "false", cwd=other)
        r = subprocess.run([os.path.join(other, "bin", "agent-release.sh"), "--push"],
                           cwd=self.base, capture_output=True, text=True, env=self.env(),
                           timeout=120)
        self.assertExit(r, 0)
        theirs = self.git("rev-parse", "refs/heads/release", cwd=self.origin)
        # this clone never fetched; it bumps and pushes
        self.assertEqual(self.git("rev-parse", "--verify", "-q", "refs/remotes/origin/release",
                                  check=False), "")
        self.set_version("0.40.1")
        self.commit("bump")
        self.build("--push")
        mine = self.git("rev-parse", "refs/heads/release", cwd=self.origin)
        self.assertEqual(self.git("log", "-1", "--format=%P", mine, cwd=self.origin), theirs)

    def test_a_local_build_is_pushed_later(self):
        self.build()
        local = self.git("rev-parse", "release")
        r = self.build("--push")
        self.assertIn("release up to date: 0.40.0", r.stdout)
        self.assertEqual(self.git("rev-parse", "refs/heads/release", cwd=self.origin), local)

    def test_push_without_origin(self):
        self.git("remote", "remove", "origin")
        r = self.run_release("--push")
        self.assertExit(r, 1)
        self.assertIn("agent-release.sh: no remote origin", r.stderr)


# ---------------------------------------------------------------- rule 9

READ_FORMS = [
    # (file, line 2, the path reported)
    ("bin/probe.sh", 'cat "$PLUGIN_ROOT/README.md"', "README.md"),
    ("bin/probe.sh", 'cat "${PLUGIN_ROOT}/README.md"', "README.md"),
    ("bin/probe.sh", 'cat "$PLUGIN_ROOT"/README.md', "README.md"),
    ("bin/probe.sh", 'cat "${CLAUDE_PLUGIN_ROOT}/README.md"', "README.md"),
    ("bin/probe.sh", 'cat $CLAUDE_PLUGIN_ROOT/README.md', "README.md"),
    ("bin/probe.sh", 'cat "$(dirname "$0")/../README.md"', "README.md"),
    ("bin/probe.sh", 'cat "$(dirname "${BASH_SOURCE[0]}")/../tests/t.txt"', "tests/t.txt"),
    ("bin/probe.sh", 'cat "$SELF_DIR/../mock/m.html"', "mock/m.html"),
    ("bin/probe.sh", 'cat "$PLUGIN_ROOT/requirements/r.md"', "requirements/r.md"),
    ("bin/probe.sh", 'cat "$PLUGIN_ROOT/bin/gone.sh"', "bin/gone.sh"),
    ("bin/probe.sh", 'cat "$PLUGIN_ROOT/../outside.txt"', "../outside.txt"),
    ("hooks/probe.json", '{"command": "\\"${CLAUDE_PLUGIN_ROOT}\\"/bin/missing.sh"}', "bin/missing.sh"),
    ("skills/probe/SKILL.md", "Run `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` first.", "CLAUDE.md"),
    ("bin/probe.py", 'p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "t.txt")',
     "tests/t.txt"),
    ("bin/probe.py", 'p = os.path.join(HERE, "..", "README.md")', "README.md"),
    ("bin/probe.py", 'p = os.path.join(bin_dir, "gone.txt")', "bin/gone.txt"),
    ("bin/probe.py", 'p = os.path.join(script_dir, "..", "agent.conf")', "agent.conf"),
    ("bin/probe.py", 'p = _bin_path("nope.html")', "bin/nope.html"),
]


def skipped_count(stdout):
    m = re.search(r"^reads check: (\d+) ok, (\d+) skipped \(variable\)$", stdout, re.M)
    return None if m is None else (int(m.group(1)), int(m.group(2)))


class TestReadsCheck(Fixture):
    def test_the_base_fixture_passes(self):
        # trailing dot, a folder, a comment naming unshipped files, a binary
        # file holding a bad path, the JSON-escaped hooks form: none fail
        r = self.run_release("--dry-run")
        self.assertExit(r, 0)
        self.assertNotIn("which is not shipped", r.stderr)

    def test_every_prefix_form_is_caught(self):
        seed = self.git("rev-parse", "HEAD")
        for rel, line, target in READ_FORMS:
            with self.subTest(form=line):
                write(self.p(rel), "# probe\n%s\n" % line, 0o755 if rel.endswith(".sh") else 0o644)
                self.commit("probe")
                before = self.refs()
                r = self.run_release("--dry-run")
                self.assertExit(r, 1)
                self.assertIn("agent-release.sh: %s:2 reads %s, which is not shipped" % (rel, target),
                              r.stderr)
                self.assertEqual(self.refs(), before)
                self.git("reset", "-q", "--hard", seed)

    def test_a_bad_read_stops_the_build_too(self):
        write(self.p("bin", "x.sh"), '#!/bin/sh\n# reads the readme\ncat "$PLUGIN_ROOT/README.md"\n', 0o755)
        self.commit("bad read")
        r = self.run_release()
        self.assertExit(r, 1)
        self.assertIn("agent-release.sh: bin/x.sh:3 reads README.md, which is not shipped", r.stderr)
        self.assertEqual(self.git("rev-parse", "--verify", "-q", "refs/heads/release", check=False), "")

    def test_every_bad_read_is_listed_in_order(self):
        write(self.p("bin", "b.sh"), 'cat "$PLUGIN_ROOT/README.md"\ncat "$PLUGIN_ROOT/tests/t.txt"\n', 0o755)
        write(self.p("bin", "a.sh"), 'x\ncat "$PLUGIN_ROOT/mock/m.html"\n', 0o755)
        self.commit("three bad reads")
        r = self.run_release("--dry-run")
        self.assertExit(r, 1)
        lines = [l for l in r.stderr.splitlines() if "which is not shipped" in l]
        self.assertEqual(lines, [
            "agent-release.sh: bin/a.sh:2 reads mock/m.html, which is not shipped",
            "agent-release.sh: bin/b.sh:1 reads README.md, which is not shipped",
            "agent-release.sh: bin/b.sh:2 reads tests/t.txt, which is not shipped",
        ])

    def test_a_good_read_counts_ok(self):
        base = skipped_count(self.run_release("--dry-run").stdout)
        self.assertIsNotNone(base)
        write(self.p("bin", "good.sh"), 'cat "$PLUGIN_ROOT/PRINCIPLES.md"\n', 0o755)
        self.commit("good read")
        r = self.run_release("--dry-run")
        self.assertExit(r, 0)
        self.assertEqual(skipped_count(r.stdout), (base[0] + 1, base[1]))

    def test_a_variable_path_is_skipped_and_counted(self):
        base = skipped_count(self.run_release("--dry-run").stdout)
        self.assertIsNotNone(base)
        write(self.p("bin", "var.sh"), 'for need in a b; do [ -e "$PLUGIN_ROOT/$need" ]; done\n', 0o755)
        self.commit("variable read")
        r = self.run_release("--dry-run")
        self.assertExit(r, 0)
        self.assertEqual(skipped_count(r.stdout), (base[0], base[1] + 1))

    def test_reads_are_checked_on_the_commit_not_the_work_tree(self):
        write(self.p("bin", "x.sh"), 'cat "$PLUGIN_ROOT/README.md"\n', 0o755)   # not committed
        r = self.run_release("--dry-run")
        self.assertExit(r, 0)
        self.commit("now committed")
        r = self.run_release("--dry-run")
        self.assertExit(r, 1)


# ---------------------------------------------------------------- review bounce 1

def refuse_pushes(bare):
    """origin refuses every push (no credentials, protected branch, network)."""
    write(os.path.join(bare, "hooks", "pre-receive"), "#!/bin/sh\necho refused by test >&2\nexit 1\n", 0o755)


class TestPushFailures(Fixture):
    def test_a_failed_push_of_a_new_release_fails(self):
        refuse_pushes(self.origin)
        r = self.run_release("--push")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.git("rev-parse", "--verify", "-q", "refs/heads/release",
                                  cwd=self.origin, check=False), "")

    def test_a_failed_push_of_an_up_to_date_release_fails(self):
        # reviewer item 1: a local build, then --push while origin refuses
        self.build()
        refuse_pushes(self.origin)
        r = self.run_release("--push")
        self.assertNotEqual(r.returncode, 0,
                            "--push said success while origin has no release:\n" + r.stdout)

    def test_a_fetch_error_other_than_a_missing_branch_fails(self):
        self.git("remote", "set-url", "origin", os.path.join(self.base, "no-such-origin.git"))
        r = self.run_release("--push")
        self.assertExit(r, 1)
        self.assertIn("agent-release.sh: git fetch origin release failed", r.stderr)

    def test_a_stale_tracking_ref_is_dropped_when_origin_lost_the_branch(self):
        # reviewer item 2: origin's release deleted (rollback step 4), same tree again
        self.build("--push")
        subprocess.run(["git", "-C", self.origin, "update-ref", "-d", "refs/heads/release"],
                       check=True, capture_output=True, env=self.env())
        r = self.build("--push")
        self.assertEqual(self.git("rev-parse", "refs/heads/release", cwd=self.origin),
                         self.git("rev-parse", "release"), r.stdout)

    def test_the_fetch_does_not_depend_on_the_locale(self):
        with open(LOGIC) as fh:
            self.assertIn("LC_ALL", fh.read(), "git runs with LC_ALL=C (its messages are matched)")

    def test_push_is_never_forced(self):
        with open(LOGIC) as fh:
            for n, line in enumerate(fh, 1):
                if "push" in line and ("--force" in line or '"-f"' in line or "'-f'" in line
                                       or '"+release' in line or "+refs/heads/release:refs/heads" in line):
                    self.fail("bin/agent_release.py:%d forces a push: %s" % (n, line.strip()))


class TestTipAndFrom(Fixture):
    def test_origins_release_wins_over_a_different_local_one(self):
        self.build("--push")
        pushed = self.git("rev-parse", "release")
        self.set_version("0.40.1")
        self.commit("0.40.1")
        self.build()                                  # local only, never pushed
        self.assertNotEqual(self.git("rev-parse", "release"), pushed)
        self.set_version("0.40.2")
        self.commit("0.40.2")
        self.build()
        self.assertEqual(self.git("log", "-1", "--format=%P", "release"), pushed)

    def test_dry_run_with_push_fetches_nothing_and_writes_nothing(self):
        other = os.path.join(self.base, "other")
        subprocess.run(["git", "clone", "-q", "-b", "main", self.origin, other], check=True,
                       capture_output=True, env=self.env())
        for k, v in (("user.email", "o@o.o"), ("user.name", "o"), ("commit.gpgsign", "false")):
            self.git("config", k, v, cwd=other)
        subprocess.run([os.path.join(other, "bin", "agent-release.sh"), "--push"], cwd=self.base,
                       check=True, capture_output=True, env=self.env(), timeout=120)
        before = self.refs()
        r = self.run_release("--dry-run", "--push")
        self.assertExit(r, 0)
        self.assertEqual(self.refs(), before)
        self.assertIn("release tip: none", r.stdout.splitlines())

    def test_dry_run_writes_no_object(self):
        def loose():
            return [l for l in self.git("count-objects", "-v").splitlines()
                    if l.startswith(("count:", "size:"))]
        self.git("gc", "-q")
        before = loose()
        self.assertExit(self.run_release("--dry-run"), 0)
        self.assertEqual(loose(), before, "--dry-run wrote objects (git mktree?)")

    def test_build_and_push_refuse_a_commit_that_is_not_on_main(self):
        # reviewer item 4: --push from a feature branch would publish unmerged code
        self.git("checkout", "-q", "-b", "feature")
        write(self.p("PRINCIPLES.md"), "# unmerged\n")
        self.set_version("0.41.0")
        sha = self.commit("unmerged")
        for args in ((), ("--push",)):
            with self.subTest(args=args):
                before = self.refs(), self.refs(cwd=self.origin)
                r = self.run_release(*args)
                self.assertExit(r, 1)
                self.assertIn("agent-release.sh: %s is not on main: release only from main"
                              % self.short(sha), r.stderr)
                self.assertEqual((self.refs(), self.refs(cwd=self.origin)), before)

    def test_dry_run_only_warns_for_a_commit_that_is_not_on_main(self):
        self.git("checkout", "-q", "-b", "feature")
        self.set_version("0.41.0")
        sha = self.commit("unmerged")
        r = self.run_release("--dry-run")
        self.assertExit(r, 0)
        self.assertIn("warning: %s is not on main (build and --push refuse it)" % self.short(sha),
                      r.stdout.splitlines())

    def test_a_commit_on_main_behind_its_tip_is_fine(self):
        old = self.git("rev-parse", "HEAD")
        self.set_version("0.41.0")
        self.commit("newer")
        self.build("--from", old)


class TestReadsCheckMore(Fixture):
    def test_a_partial_name_then_a_variable_is_skipped(self):
        base = skipped_count(self.run_release("--dry-run").stdout)
        write(self.p("bin", "part.sh"), 'cat "$PLUGIN_ROOT/bin/agent-$x.sh"\n', 0o755)
        self.commit("partial variable")
        r = self.run_release("--dry-run")
        self.assertExit(r, 0)
        self.assertEqual(skipped_count(r.stdout), (base[0], base[1] + 1))

    def test_own_folder_prefixes_resolve_against_the_files_own_folder(self):
        # reviewer item 6: bin/sub/x.sh, $(dirname "$0") is bin/sub
        write(self.p("bin", "sub", "x.sh"),
              '#!/bin/sh\n. "$(dirname "$0")/../agent-roots.sh"\ncat "$(dirname "$0")/nope.sh"\n', 0o755)
        write(self.p("bin", "sub", "y.py"),
              'import os\nHERE = os.path.dirname(os.path.abspath(__file__))\n'
              'p = os.path.join(HERE, "..", "agent.conf.default")\n'
              'q = os.path.join(HERE, "gone.txt")\n')
        self.commit("sub folder")
        r = self.run_release("--dry-run")
        self.assertExit(r, 1)
        bad = [l for l in r.stderr.splitlines() if "which is not shipped" in l]
        self.assertEqual(bad, [
            "agent-release.sh: bin/sub/x.sh:3 reads bin/sub/nope.sh, which is not shipped",
            "agent-release.sh: bin/sub/y.py:4 reads bin/sub/gone.txt, which is not shipped",
        ])

    def test_not_a_checkout_when_the_folder_sits_inside_another_repo(self):
        nested = self.p("cache", "0.39.0")
        self.install_script(nested)
        r = self.run_release("--dry-run", root=nested)
        self.assertExit(r, 2)
        self.assertIn("agent-release.sh: not a git checkout: %s" % nested, r.stderr)


# ---------------------------------------------------------------- the real repo

class TestRealRepo(unittest.TestCase):
    def test_dry_run_on_this_repo(self):
        if not os.path.exists(SCRIPT):
            self.fail("bin/agent-release.sh does not exist yet. Write it.")
        refs = lambda: subprocess.run(
            ["git", "-C", ROOT, "for-each-ref", "--format=%(refname) %(objectname)"],
            capture_output=True, text=True).stdout
        before = refs()
        home = tempfile.mkdtemp(prefix="agent_release_home_")
        self.addCleanup(shutil.rmtree, home, True)
        env = dict(os.environ, HOME=home, GIT_CONFIG_NOSYSTEM="1")
        r = subprocess.run([SCRIPT, "--dry-run"], cwd=HERE, capture_output=True, text=True,
                           env=env, timeout=180)
        self.assertEqual(r.returncode, 0, "stdout:\n%s\nstderr:\n%s" % (r.stdout, r.stderr))
        self.assertNotIn("which is not shipped", r.stderr)
        self.assertRegex(r.stdout, r"(?m)^ship: \d+ files, \d+ bytes$")
        self.assertRegex(r.stdout, r"(?m)^(would commit release \d+(\.\d+)*|release up to date: .*)$")
        left = re.search(r"(?m)^left out: (.*)$", r.stdout)
        self.assertIsNotNone(left, r.stdout)
        names = left.group(1).split()
        for name in ("tests", "mock", "requirements", "README.md", "CLAUDE.md", "AGENTS.md",
                     ".claude", ".gitignore", "agent_todo.txt",   # settings-configure: no agent.conf
                     "agent_completed.txt", "agent_ideas.txt", "agent_estimate.txt"):
            self.assertIn(name, names)
        for name in SHIP:
            self.assertNotIn(name, names)
        self.assertEqual(refs(), before, "--dry-run wrote a ref in this repo")


# ---------------------------------------------------------------- rule 15

class TestMergeSkillLine(unittest.TestCase):
    """Written now, passes only after "main merged" (skills/merge belongs to
    one-watcher until then)."""

    def test_the_merge_skill_names_the_release_step(self):
        with open(os.path.join(ROOT, "skills", "merge", "SKILL.md")) as fh:
            lines = fh.read().splitlines()
        hits = [l for l in lines if "bin/agent-release.sh --push" in l]
        self.assertEqual(len(hits), 1, "one line with bin/agent-release.sh --push")
        self.assertIn("before", hits[0])
        self.assertIn("main", hits[0])
        self.assertIn("auto-pipeline", hits[0])


if __name__ == "__main__":
    unittest.main()
