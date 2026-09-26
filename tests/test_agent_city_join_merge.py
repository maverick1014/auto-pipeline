"""Failing tests for bringing city-join (the relay branch) together with
city-worktrees and city-quality (requirements/city.md, Joining, Worktrees,
Quality).

CONTRACT

  Relay client (bin/agent_city_relay.py)
    The hook's newer keys never leave the machine: a line carrying "file"
    (a repo-relative path) and "wt" (a full worktree path) is sent without
    either; no part of the wt path or the file name appears in what the
    relay receives.
    Branch: when the line carries "wt" (the linked worktree's folder), the
    branch is that worktree's branch, even when the session's cwd was a
    subfolder of it (proj is then only the subfolder's name). Without "wt"
    the old rule stays (match proj against the worktree folder names).

  Page (bin/agent-city.html)
    topCounts() counts only this machine's own people: another member's
    person (c.remote) never adds to 干活 / 找总督 / 休息.
    renderStats() draws topCounts() and, while joined, the relay chip and
    the member legend (both halves kept).
    The demo seeds the sites, the quality demo and the other members.

Run: python3 -m unittest tests.test_agent_city_join_merge </dev/null
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from relayhelp import add_worktree, hook_line, join  # noqa: E402
from test_agent_city_relay_client import HubCase  # noqa: E402
from test_agent_city_people import function_source, plan_views, run_sim  # noqa: E402


class TestNewHookKeysStayHome(HubCase):

    def setUp(self):
        super().setUp()
        join(self.repo, self.fake.url)

    def test_file_and_wt_are_never_sent(self):
        wt = add_worktree(self.repo, "feature/private-name")
        line = hook_line(self.repo, proj=wt, file="src/zz_private_file_7731.py", wt=wt,
                         kind="other", tool="Edit")
        hub = self.hub()
        self.assertTrue(hub.offer(line))
        hub.tick()
        sent = self.fake.sent_lines()
        self.assertEqual(len(sent), 1)
        self.assertNotIn("file", sent[0])
        self.assertNotIn("wt", sent[0])
        body = json.dumps(self.fake.sync_bodies())
        self.assertNotIn("zz_private_file_7731", body)
        self.assertNotIn(wt, body)
        self.assertNotIn(self.base, body)

    def test_wt_gives_the_branch_from_a_subfolder(self):
        wt = add_worktree(self.repo, "feature/sub")
        sub = os.path.join(wt, "api")
        os.makedirs(sub, exist_ok=True)
        hub = self.hub()
        self.assertTrue(hub.offer(hook_line(self.repo, proj=sub, wt=wt)))
        hub.tick()
        self.assertEqual(self.fake.sent_lines()[0]["br"], "feature/sub")

    def test_without_wt_the_folder_name_rule_stays(self):
        wt = add_worktree(self.repo, "feature/old")
        hub = self.hub()
        self.assertTrue(hub.offer(hook_line(self.repo, proj=wt)))
        hub.tick()
        self.assertEqual(self.fake.sent_lines()[0]["br"], "feature/old")


COUNT_DRIVER = r"""
const V = __payload.view, T = V.territories[0], tid = T.id;
function buildLand(view){ landState(view); }
apply({ type: 'snapshot', world: V, gov: { state: 'idle', terr: tid }, govs: [], governors: 0, asks: [],
        shows: [], agents: [
          { id: 'a1', role: 'worker', label: 'worker', task: 'x', stuck: false, done: false, tools: {}, terr: tid } ] });
const before = topCounts();
apply({ type: 'remote', who: 'Ann', device: 'ann-laptop', dev: 'dev-ann', rid: 'acme/shop', br: 'main',
        ev: { type: 'spawn', id: 'r:dev-ann:s:1', role: 'worker', label: 'worker', task: 'y', terr: tid } });
apply({ type: 'remote', who: 'Bo', device: '云端', dev: 'dev-bo', rid: 'acme/shop', br: 'main',
        ev: { type: 'spawn', id: 'r:dev-bo:s:1', role: 'worker', label: 'worker', task: 'z', terr: tid } });
for (let i = 0; i < 30; i++) update(.1);
const remotes = citizens.filter(c => c.remote).length;
__out = { before, after: topCounts(), remotes };
"""


class TestPageCountsAndStats(unittest.TestCase):

    def test_other_members_never_count(self):
        views = plan_views()
        out = run_sim(COUNT_DRIVER, {"view": views[sorted(views)[0]]},
                      ("apply", "update", "topCounts", "citizens", "landState"))
        self.assertEqual(out["remotes"], 2, "the two remote people exist in the page")
        self.assertEqual(out["after"], out["before"])

    def test_render_stats_keeps_both_halves(self):
        src = function_source("renderStats") or ""
        self.assertIn("topCounts()", src)
        self.assertIn("remoteChip(", src)
        self.assertIn("memberLegend(", src)

    def test_demo_seeds_all_three(self):
        src = function_source("seed") or ""
        for name in ("seedSites()", "seedQualityDemo()", "seedDemoRemote()"):
            self.assertIn(name, src)


if __name__ == "__main__":
    unittest.main()
