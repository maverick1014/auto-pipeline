"""One scratch repo per test CLASS, for tests that only read (test-slim).

ScriptCase (scripthelp) builds a fresh plugin copy and project for every test.
A class whose tests all look at one fixture and never change it can share one,
and run each script once instead of once per test:

    class TestBoardShowsTheWait(SharedScriptCase):
        script = "agent-file.sh"

        @classmethod
        def prepare(cls):              # once per class: build, then run
            cls.repo.set_worktree_lines([...])
            cls.out = cls.run_ok("agent-file.sh", "board")

        def test_names_the_task(self):
            self.assertIn("alpha", self.out)

The guard: after every test the shared folder (plugin copy and project) must be
exactly as prepare() left it. A test that changed, added or removed a file
there fails; it belongs in a ScriptCase class (one repo per test).
"""

import os
import unittest

from scripthelp import BIN, ScriptCase, ScriptRepo


def tree_state(base):
    """(path, size, mtime) of every file under base, for the read-only guard."""
    rows = []
    for folder, dirs, files in os.walk(base):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(folder, name)
            try:
                st = os.lstat(full)
            except OSError:
                continue
            rows.append((os.path.relpath(full, base), st.st_size, st.st_mtime_ns))
    return rows


class SharedScriptCase(ScriptCase):
    """Base case: one plugin copy and one project per class, read only."""

    script = None
    repo = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if cls.script and not os.path.exists(os.path.join(BIN, cls.script)):
            raise unittest.SkipTest("bin/%s does not exist" % cls.script)
        cls.repo = ScriptRepo()
        cls.addClassCleanup(cls.repo.cleanup)
        cls.prepare()
        cls._shared_state = tree_state(cls.repo.base)

    @classmethod
    def prepare(cls):
        """Build the fixture and run the scripts, once. Override."""

    @classmethod
    def run_ok(cls, script, *args, **kwargs):
        """Run a script once for the class; its stdout, or fail the class."""
        result = cls.repo.run(script, *args, **kwargs)
        if result.returncode != 0:
            raise AssertionError("%s %s: exit %d\nSTDOUT:\n%s\nSTDERR:\n%s" % (
                script, " ".join(args), result.returncode, result.stdout, result.stderr))
        return result.stdout

    def setUp(self):
        # no per-test repo: the class one is self.repo
        pass

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
