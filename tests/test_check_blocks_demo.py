"""approval-design F (requirements/check-blocks.md section 53 F): the release run walks tests/check_blocks_demo.sh.

Heavy (it builds a dozen scratch repos and runs the real tools): it runs only when tests/run2.py runs the full
suite (no file named; run2 sets AGENT_FULL_RUN=1), i.e. the release run and the nightly, never in a task.
"""

import os
import re
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEMO = os.path.join(HERE, "check_blocks_demo.sh")

WALKS = ("===== 1 text only: one locale value =====",
         "===== 5 a merge refused for a missing result line =====",
         "===== 8 F1: the direct path to production is bound to the task =====",
         "===== walk 1: a small task from dispatch to todo done on the working branch =====",
         "===== walk 2: a task with target production =====",
         "===== walk 3: an urgent small production task",
         "===== walk 4: the owner's real state",
         "===== walk 5: the working branch published on his words =====",
         "===== walk 6: his yes comes after the task was added (a task of the working branch moves to production) =====",
         "===== 10 FIX ORDERS 6 and 10",
         "===== done: everything above ran in ")

OWNER_WORDS = ('OWNER WORDS publish: "2. need to publish direct after done" (typed ',
               ') read as: publish task 2 (p1) to production',
               'OWNER WORDS publish: "the urgent total fix can go live straight after it is done" (typed ',
               'OWNER WORDS publish ap-main-demo: "publish everything to production now" (typed ',
               'OWNER WORDS skip RELATED TESTS: "skip the related tests for g" (typed ',
               'OWNER WORDS skip BUILD: "1A" (typed ',
               '| question: "1. Leave out BUILD for g (a text-only change)? A. yes, leave it out B. no, run it"',
               'OWNER WORDS OWNER SIGN: "yes, drop the column legacy_note" (typed ',
               'OWNER WORDS publish ap-main-demo -> main ',
               'OWNER WORDS publish: "the footer one can go live straight after it is done" (typed ',
               'production has the footer and not the other task: footer = 2 / other-not-there')


class TestTheDemoRuns(unittest.TestCase):

    @unittest.skipUnless(os.environ.get("AGENT_FULL_RUN") == "1",
                         "heavy: runs in the release run and the nightly (tests/run2.py with no file named)")
    def test_it_exits_0_and_walks_every_path(self):
        env = dict(os.environ)
        for k in ("AGENT_ROLE", "CLAUDE_PID", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CONFIG_DIR"):
            env.pop(k, None)
        r = subprocess.run(["bash", DEMO, ROOT], capture_output=True, text=True, timeout=1500, env=env,
                           stdin=subprocess.DEVNULL)
        out = r.stdout + r.stderr
        m = re.search(r"everything above ran in (\S+) \(delete it when read\)", out)
        if m and os.path.basename(m.group(1)).startswith("check-blocks-demo."):
            shutil.rmtree(m.group(1), True)
        self.assertEqual(r.returncode, 0, out[-6000:])
        self.assertNotIn("DEMO FAILED", out)
        for walk in WALKS:
            with self.subTest(walk=walk):
                self.assertIn(walk, out)
        for line in OWNER_WORDS:
            with self.subTest(line=line):
                self.assertIn(line, out)
        self.assertIn("GATE PASS p1", out)
        self.assertIn("promote: p1 -> main", out)
        self.assertIn("promote: main -> ", out)


if __name__ == "__main__":
    unittest.main()
