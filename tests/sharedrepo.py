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


def remember_runs(repo, after=None):
    """Make repo.run() answer a repeated call from memory. after(): called
    after each real (first) run."""
    real = repo.run
    seen = {}

    def run(script, *args, **kwargs):
        key = json.dumps([script, list(args), sorted((kwargs.get("env") or {}).items()),
                          kwargs.get("stdin"), kwargs.get("cwd")], default=str)
        if key not in seen:
            seen[key] = real(script, *args, **kwargs)
            if after:
                after()
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


def shared_fixture(guard=None, remember=(), remember_repo=False):
    """Class decorator: the class's setUp runs once, for its first test; the
    later tests reuse what it built (any TestCase, not only ScriptCase).

        @shared_fixture(guard="base", remember=("pack",))
        class TestEveryFileLands(PackCase): ...

    - cleanups the setUp registers (self.addCleanup) run when the class ends
    - attributes the setUp set on self are there for every test
    - remember: method names whose result is kept per arguments (a second
      call with the same arguments does not run again)
    - remember_repo: self.repo.run() remembers its calls too
    - guard: the attribute naming a folder (or a function of the test giving
      it, e.g. REPO_BASE); after every test its content must
      be what it was after the setUp (and the first calls), else the test fails
    """
    def deco(cls):
        setup = cls.setUp
        teardown = cls.tearDown

        def setUp(self):
            if "_once_done" not in cls.__dict__:
                before = dict(vars(self))
                self.addCleanup = cls.addClassCleanup
                try:
                    setup(self)
                finally:
                    del self.addCleanup
                if remember_repo and getattr(self, "repo", None) is not None:
                    remember_runs(self.repo, after=lambda: resnap(self))
                for key, value in vars(self).items():
                    if key not in before or before[key] is not value:
                        setattr(cls, key, value)
                cls._once_done = True
                resnap(self)

        def folder_of(self):
            return guard(self) if callable(guard) else getattr(self, guard)

        def resnap(self):
            # the fixture as it stands now: after the setUp, and after the
            # first real run of each remembered call
            cls._once_state = tree_state(folder_of(self)) if guard else None

        def tearDown(self):
            teardown(self)
            if not guard:
                return
            now = tree_state(folder_of(self))
            if now != cls._once_state:
                before = {r[0]: r for r in cls._once_state}
                after = {r[0]: r for r in now}
                changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
                cls._once_state = now
                self.fail("this test changed the shared fixture (give it its own setUp): %s"
                          % ", ".join(changed[:10]))

        for name in remember:
            real = getattr(cls, name)

            def make(real, name):
                def remembered(self, *args, **kwargs):
                    store = cls.__dict__.get("_remembered")
                    if store is None:
                        store = {}
                        cls._remembered = store
                    key = json.dumps([name, list(args), sorted(kwargs.items())], default=str)
                    if key not in store:
                        store[key] = real(self, *args, **kwargs)
                        resnap(self)
                    return store[key]
                return remembered

            setattr(cls, name, make(real, name))
        cls.setUp = setUp
        cls.tearDown = tearDown
        return cls

    return deco


def REPO_BASE(test):
    """guard= for a ScriptCase class: its repo folder (plugin copy and project)."""
    return test.repo.base
