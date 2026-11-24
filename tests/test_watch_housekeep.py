"""The housekeep timer of `agent-watch.sh --all` (W8). It replaces the old monitor loop's timer
(bin/agent-monitor.sh is gone, owner decision 2026-11-24).

CONTRACT
    After each sweep the watch runs <plugin>/bin/agent-housekeep.sh --apply once, when all hold:
      a. AGENT_ROLE is not set (main manager only)
      b. housekeep_interval_min from agent.conf, read every sweep (missing: 120; 0: never)
      c. "<git dir>/agent_main.lock" names a pid that is alive, read every sweep
      d. "<git dir>/agent_housekeep.last" is missing, does not read, or its first field (epoch seconds)
         is interval*60 seconds ago or more
    The call: CLAUDE_PID=<that lock pid>, AGENT_ROLE unset, stdin /dev/null, output not shown.
    The watch never writes the stamp; agent-housekeep.sh --apply does.
"""

import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from watchhelp import AllCase  # noqa: E402

FAKE_HK = r"""#!/usr/bin/env bash
printf '%s\t%s\t%s\n' "$*" "${CLAUDE_PID:-}" "${AGENT_ROLE:-}" >> "@LOG@"
if [ -f "@LOG@.stamp" ]; then
  printf '%s %s\n' "$(date +%s)" "$(date '+%Y-%m-%d %H:%M')" > "@STAMP@"
fi
exit 0
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


class HkCase(AllCase):
    def setUp(self):
        super().setUp()
        r = self.repo
        r.set_conf("runtime", "orca")
        r.set_conf("housekeep_interval_min", "120")
        self.hk_log = os.path.join(r.base, "hk_calls.log")
        open(self.hk_log, "w").close()
        self.stamp = r.path(".git", "agent_housekeep.last")
        r.write_bin_script("agent-housekeep.sh", FAKE_HK.replace("@LOG@", self.hk_log)
                           .replace("@STAMP@", self.stamp))
        self.task("alpha", "working")

    def lock(self, pid):
        write(self.repo.path(".git", "agent_main.lock"), "%d 2026-11-13 10:00 - -\n" % pid)

    def set_stamp(self, minutes_ago):
        when = time.time() - minutes_ago * 60
        write(self.stamp, "%d %s\n" % (when, time.strftime("%Y-%m-%d %H:%M", time.localtime(when))))

    def hk_calls(self):
        with open(self.hk_log) as fh:
            return [l.rstrip("\n").split("\t") for l in fh if l.strip()]

    def watch(self, **env):
        return self.run_all(max_sweeps="4", env=env)


class TestRuns(HkCase):
    def test_due_with_no_stamp_runs_once_as_the_lock_owner(self):
        self.lock(os.getpid())
        open(self.hk_log + ".stamp", "w").close()   # the fake writes the stamp like the real one
        self.watch()
        self.assertEqual(self.hk_calls(), [["--apply", str(os.getpid()), ""]])

    def test_an_old_stamp_is_due(self):
        self.lock(os.getpid())
        self.set_stamp(121)
        self.watch()
        self.assertTrue(self.hk_calls())

    def test_a_stamp_that_does_not_read_is_due(self):
        self.lock(os.getpid())
        write(self.stamp, "garbage\n")
        self.watch()
        self.assertTrue(self.hk_calls())

    def test_a_missing_key_means_120(self):
        self.lock(os.getpid())
        self.repo.unset_conf("housekeep_interval_min")
        self.set_stamp(100)
        self.watch()
        self.assertEqual(self.hk_calls(), [])
        self.set_stamp(125)
        self.watch()
        self.assertTrue(self.hk_calls())

    def test_the_interval_is_the_conf_value(self):
        self.lock(os.getpid())
        self.repo.set_conf("housekeep_interval_min", "30")
        self.set_stamp(31)
        self.watch()
        self.assertTrue(self.hk_calls())

    def test_the_pass_does_not_end_the_watch(self):
        self.lock(os.getpid())
        out = self.text(self.watch())
        self.assertEqual(self.one_watch(out), "WATCH MAX all")
        self.assertTrue(self.hk_calls())


class TestDoesNotRun(HkCase):
    def test_a_fresh_stamp_is_not_due(self):
        self.lock(os.getpid())
        self.set_stamp(30)
        self.watch()
        self.assertEqual(self.hk_calls(), [])

    def test_interval_zero_is_off(self):
        self.lock(os.getpid())
        self.repo.set_conf("housekeep_interval_min", "0")
        self.watch()
        self.assertEqual(self.hk_calls(), [])

    def test_no_lock_no_pass(self):
        self.watch()
        self.assertEqual(self.hk_calls(), [])

    def test_a_dead_lock_owner_no_pass(self):
        self.lock(999999)
        self.watch()
        self.assertEqual(self.hk_calls(), [])

    def test_a_watch_of_a_spawned_agent_never_runs_it(self):
        self.lock(os.getpid())
        self.watch(AGENT_ROLE="task-manager")
        self.assertEqual(self.hk_calls(), [])


if __name__ == "__main__":
    unittest.main()
