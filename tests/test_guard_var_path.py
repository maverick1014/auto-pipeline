"""guard-var-path: a worktree path given as $NAME / ${NAME} is expanded, taken from the response, or left out."""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_board_trust as t  # noqa: E402

TITLE = "one-watcher Task Manager"
PANE = "term_bc68aaf3-5722-4519-b334-5b19d9d2661e"
W = "/Users/maverick/orca/workspaces/auto-pipeline/one-watcher"


def create(opt="path:$W"):
    return 'orca terminal create --environment pc2 --worktree %s --title "%s" --command "zsh" --json' % (opt, TITLE)


class VarPath(t.GuardCase):
    def setUp(self):
        super().setUp()
        self.put_todo("one-watcher")

    def launch(self, cmd, stdout=None):
        r = self.pre_bash(cmd)
        self.assertAllowed(r)
        if stdout is not None:
            self.assertAllowed(self.post_bash(cmd, r.tid, stdout))
        rows = self.launches()
        self.assertEqual(len(rows), 1, rows)
        self.assertNotIn("$", rows[0])
        return rows[0]

    def test_a_assignment_earlier(self):
        row = self.launch("W=%s\n%s" % (W, create()))
        self.assertEqual(self.fields(row)["worktree"], W)

    def test_a_export_and_quotes(self):
        row = self.launch("export W='%s'; %s" % (W, create()))
        self.assertEqual(self.fields(row)["worktree"], W)
        self.assertEqual(self.fields(row)["env"], "pc2")

    def test_b_braces(self):
        row = self.launch('W="%s"\n%s' % (W, create("path:${W}")))
        self.assertEqual(self.fields(row)["worktree"], W)

    def test_c_from_response_worktree_id(self):
        out = json.dumps({"result": {"terminal": {"handle": PANE, "worktreeId": "repo-1::" + W}}})
        row = self.launch(create(), out)
        f = self.fields(row)
        self.assertEqual((f["worktree"], f["pane"]), (W, PANE))

    def test_c_from_response_path(self):
        out = json.dumps({"result": {"handle": PANE, "worktree": {"path": W}}})
        row = self.launch(create(), out)
        self.assertEqual(self.fields(row)["worktree"], W)

    def test_d_no_path_anywhere(self):
        out = '"handle": "%s"' % PANE
        row = self.launch(create() + " 2>&1 | grep -o '\"handle\": \"[^\"]*\"'", out)
        f = self.fields(row)
        self.assertNotIn("worktree", f)
        self.assertEqual(f["pane"], PANE)

    def test_e_command_substitution_not_expanded(self):
        row = self.launch("W=$(pwd)\n" + create())
        self.assertNotIn("worktree", self.fields(row))

    def test_e_quoted_substitution_not_expanded(self):
        row = self.launch('W="$(pwd)"\n' + create())
        self.assertNotIn("worktree", self.fields(row))

    def test_f_rm_with_assignment_removes(self):
        self.put_launch("LAUNCH toolu_x: tm-pane | task one-watcher | %s | since 2026-11-20 16:40 | pid %d | by main "
                        "| pane term_a | worktree %s" % (TITLE, t.LIVE, W))
        rm = "W=%s\norca worktree rm --worktree path:$W --json" % W
        r = self.pre_bash(rm)
        self.assertAllowed(r)
        self.assertAllowed(self.post_bash(rm, r.tid, '{"ok":true}'))
        self.assertEqual(self.launches(), [])

    def test_f_rm_without_assignment_removes_nothing(self):
        self.put_launch("LAUNCH toolu_x: tm-pane | task one-watcher | %s | since 2026-11-20 16:40 | pid %d | by main "
                        "| pane term_a | worktree %s" % (TITLE, t.LIVE, W))
        rm = "orca worktree rm --worktree path:$W --json"
        r = self.pre_bash(rm)
        self.assertAllowed(r)
        self.assertAllowed(self.post_bash(rm, r.tid, '{"ok":true}'))
        self.assertEqual(len(self.launches()), 1)


if __name__ == "__main__":
    unittest.main()
