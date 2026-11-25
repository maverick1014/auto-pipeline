"""One scratch repo per test CLASS, for tests that only read (test-slim).

ScriptCase (scripthelp) builds a fresh plugin copy and project for every test.
A class whose tests all look at one fixture and never change it can share one,
and run each script once instead of once per test:

    class TestBoardShowsTheWait(SharedScriptCase):
        script = "agent-file.sh"

        def fixture(self):             # once, before the first test of the class
            self.repo.set_worktree_lines([...])

        def test_names_the_task(self):
            out = self.repo.run("agent-file.sh", "board").stdout   # runs once
            self.assertIn("alpha", out)

- fixture() is an instance method, so the helpers of an existing case work in it.
  A classmethod prepare() is there too, for code that has no instance helpers.
- The shared repo's run() remembers each call (script, args, env, stdin, cwd):
  the same call in another test returns the same result without a new start.
- The guard: after every test the shared folder (plugin copy and project) must be
  exactly as the fixture left it. A test (or a script it ran) that changed, added
  or removed a file there fails; it belongs in a ScriptCase class.
"""

import hashlib
import json
import os
import unittest

from scripthelp import BIN, ScriptCase, ScriptRepo


def tree_state(base):
    """(path, size, content hash) of every file under base, for the read-only
    guard. Content, not mtime: a script that only touches a file changes nothing
    a later test can see."""
    rows = []
    for folder, dirs, files in os.walk(base):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(folder, name)
            try:
                if os.path.islink(full):
                    rows.append((os.path.relpath(full, base), -1, os.readlink(full)))
                    continue
                with open(full, "rb") as fh:
                    data = fh.read()
            except OSError:
                continue
            rows.append((os.path.relpath(full, base), len(data), hashlib.sha1(data).hexdigest()))
    return rows


def remember_runs(repo):
    """Make repo.run() answer a repeated call from memory."""
    real = repo.run
    seen = {}

    def run(script, *args, **kwargs):
        key = json.dumps([script, list(args), sorted((kwargs.get("env") or {}).items()),
                          kwargs.get("stdin"), kwargs.get("cwd")], default=str)
        if key not in seen:
            seen[key] = real(script, *args, **kwargs)
        return seen[key]

    repo.run = run
    return repo


class SharedScriptCase(ScriptCase):
    """Base case: one plugin copy and one project per class, read only."""

    script = None
    repo = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if cls.script and not os.path.exists(os.path.join(BIN, cls.script)):
            raise unittest.SkipTest("bin/%s does not exist" % cls.script)
        cls.repo = remember_runs(ScriptRepo())
        cls.addClassCleanup(cls.repo.cleanup)
        cls._shared_state = None
        cls.prepare()

    @classmethod
    def prepare(cls):
        """Class-level fixture, once. Override, or override fixture()."""

    def fixture(self):
        """Instance-level fixture, once, before the first test. Override."""

    @classmethod
    def run_ok(cls, script, *args, **kwargs):
        """Run a script (once) for the class; its stdout, or fail."""
        result = cls.repo.run(script, *args, **kwargs)
        if result.returncode != 0:
            raise AssertionError("%s %s: exit %d\nSTDOUT:\n%s\nSTDERR:\n%s" % (
                script, " ".join(args), result.returncode, result.stdout, result.stderr))
        return result.stdout

    def setUp(self):
        # no per-test repo: the class one is self.repo
        cls = type(self)
        if cls._shared_state is None:
            before = dict(vars(self))
            self.fixture()
            # what the fixture kept on self (paths, names) is there for every test
            for key, value in vars(self).items():
                if key not in before or before[key] is not value:
                    setattr(cls, key, value)
            cls._shared_state = tree_state(cls.repo.base)

    def tearDown(self):
        now = tree_state(self.repo.base)
        if now != self._shared_state:
            before = {r[0]: r for r in self._shared_state}
            after = {r[0]: r for r in now}
            changed = sorted(p for p in set(before) | set(after)
                             if before.get(p) != after.get(p))
            # reset, so one bad test does not fail the rest of the class
            type(self)._shared_state = now
            self.fail("this test changed the shared fixture (make it a ScriptCase test): %s"
                      % ", ".join(changed[:10]))
