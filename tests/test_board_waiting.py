"""Failing tests for board-waiting. Written by the task manager first.

The rules, with every example used here: requirements/board-waiting.md
(main manager "rules yes" 2026-11-20: Q1 B, Q2 A, Q3 A, rule 6.3 = not started).

Short:
    waiting row   todo wait on mock|question|review (owner by default), or hold WITH --who:
                  status `等待 <who> · <what> · 已等 <n>` (en `waiting <who> · <what> · waited <n>`)
    hold row      hold without who: `暂缓 · <what> · 已等 <n>` (en `hold · <what> · waited <n>`)
    queue row     `排队 · 在 <task> 之后` (en `queue · after <task>`), no waited time
    not started   no stage, no started, no wait: `未开始` (en `not started`)
    these rows    进度 已工作 已等待 预计完成 are "-"; 估时 is "-" too, except a not started row;
                  位置 and 级别 as today
    sort          owner waits, running, waits on others, queue + not started, hold, OWNER TODO, parked
    status line   at most 5 lines in all; queue, hold and not started rows fold into `+N 排队/暂缓`
                  (en `+N queued/held`)
    todo wait     --who <name>, --after <task> (queue only); fields ` | who <name>`, ` | after <task>`,
                  ` | wait run since <date>` (a wait over an open wait), right after the waiting field
    todo stage    the first stage writes ` | started <date>[ after <n>m waited]`
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

import test_agent_board as tb  # noqa: E402  (the module only)

NOW = "2026-11-20 12:31"
P = "/x/orca/workspaces/auto-pipeline/state-trim"
WHERE_ST = "maverick-pc2, " + P

ST_RUN = ("state-trim | big | State file trim + auto clear at compact_clear_at | est 70m | guess 70m | level 4 | "
          "opened 2026-11-20 11:20 | by main | on maverick-pc2 %s | started 2026-11-20 11:24 | waited 38m | "
          "stage tests since 2026-11-20 12:21" % P)
ST_REVIEW = ("state-trim | big | State file trim + auto clear at compact_clear_at | est 70m | guess 70m | level 4 | "
             "opened 2026-11-20 11:20 | by main | on maverick-pc2 %s | started 2026-11-20 11:24 | waited 38m | "
             "stage verify since 2026-11-20 12:10 | waiting review since 2026-11-20 12:26" % P)
V4 = ("v4plus-followups | small | Cross-repo asks to the v4-plus Manager | est 5m | guess 5m | "
      "opened 2026-11-16 15:46 | by main | cross v4-plus | "
      "waiting hold since 2026-11-16 15:47: 回复插件更新和同步脚本 | who v4-Manager")
PC2 = ("pc2-plugin-update | small | Update auto-pipeline user-scope plugin on pc2 | est 5m | guess 5m | "
       "opened 2026-11-17 17:21 | by main | on maverick-pc2 | cross v4-plus | waited 895m | "
       "waiting hold since 2026-11-18 08:16: pc2 空闲时更新 plugin | who v4-Manager")
UT = ("usage-track | big | Track tied repos | est 49m | guess 50m | opened 2026-11-16 17:31 | by main | "
      "waiting hold since 2026-11-16 17:31: 你说合并监控之后再做")
BW = ("board-waiting | big | Board waiting status | est 39m | guess 40m | level 3 | opened 2026-11-20 11:35 | "
      "by main | waiting queue since 2026-11-20 11:35 | after state-trim")

# pc2's real agent_todo.txt of 2026-11-20 (old lines: no who, no after, no started)
REAL = [
    "v4plus-followups | small | Cross-repo asks to the v4-plus Manager (owner 2A 4A 2026-11-16): update v4-plus "
    "project scope to plugin 0.34.1 + restart at a quiet point; consider the 15-min production sync as a plain "
    "script (agent only on failure); idle v4-plus-sync sessions pile up | est 5m | guess 5m | opened 2026-11-16 "
    "15:46 | by main | cross v4-plus | waiting hold since 2026-11-16 15:47: v4-Manager: not now, ledger rollout "
    "final suite + staging; update after owner confirms in its chat; sync script = later task for owner",
    "usage-track | big | Track tied repos (v4-plus first): housekeep prints a USAGE block per repo (plugin scope "
    "version, state file size, monitor alive, completed data gaps) at no agent cost, and flags the weekly deep "
    "audit as due (next 2026-11-23). Owner 3A 2026-11-16 | est 49m | guess 50m | opened 2026-11-16 17:31 | by "
    "main | waiting hold since 2026-11-16 17:31: owner close case 2026-11-16: after one-watcher",
    "pc2-plugin-update | small | Update auto-pipeline user-scope plugin on pc2 from 0.23.1 to 0.35.0 (owner "
    "2026-11-17) when no v4-plus task manager is working on pc2; running sessions keep their copy until restart | "
    "est 5m | guess 5m | opened 2026-11-17 17:21 | by main | on maverick-pc2 | cross v4-plus | waited 895m | "
    "waiting hold since 2026-11-18 08:16: handed to v4-Manager 2026-11-18 (owner); its todo, its quiet point",
    "one-watcher | big | One watcher for every task manager (agent-watch.sh --all, pane + remote state file, LOST "
    "on exited pane, no signature filter) + agent-file.sh tell with receipt; heartbeats to file only. Fix 3 of 3 "
    "from the v4-plus audit (ideas 123-125, 141-142). PLUS owner 2026-11-17: at main manager start or resume, "
    "rebuild every watch from agent_worktree.txt (today only agent-monitor.sh restarts) | est 114m | guess 135m | "
    "level 3 | opened 2026-11-18 08:16 | by main | waiting hold since 2026-11-18 08:16: owner close case "
    "2026-11-18: next round, run in order, one at a time on pc2",
    "owner-relay | big | OWNER ORDER relay between repo managers: sender prints the OWNER ORDER line (owner "
    "quote, repo, time); receiver runs one command that verifies the quote is a typed owner prompt in the "
    "sender's transcript (not peer, not meta, not tool_result, 24h, same machine); W12 rule + dispatch skill. "
    "Owner 3A 2026-11-20: after one-watcher. Rule text already in ~/.claude/CLAUDE.md | est 42m | guess 45m | "
    "level 3 | opened 2026-11-20 11:35 | by main",
    "comment-shape | small | agent-level.sh: a comment-only change becomes a fifth level 0 shape; R8 line + tests "
    "(owner 4A 2026-11-20, later; level 3 = full lane) | est 28m | guess 20m | level 3 | opened 2026-11-20 11:35 "
    "| by main",
]
OW, OR, CS = REAL[3], REAL[4], REAL[5]
FIXTURE_F = [V4, UT, PC2, OW, OR, CS, ST_RUN, BW]

# a running task opened long before every wait below (rule 5.0: its waits never fill the time from opened)
BASE = ("x | big | the task | est 60m | level 2 | opened 2026-11-10 09:00 | by main | "
        "started 2026-11-10 09:05 | stage tests since 2026-11-10 09:05")
DASH = {"Progress": "-", "Est": "-", "Work": "-", "Wait": "-", "Done by": "-"}


def name_col(name):
    """A status line name: 24 columns, then two spaces (today's layout)."""
    return name + " " * (24 - len(name)) + "  "


class Case(tb.BoardCase):
    lang = "zh"

    def setUp(self):
        super().setUp()
        # one-watcher (2026-11-24): a target row with no live watch gets " · 未确认 <n>m" and the status line a
        # warning line (tests/test_watch_board.py); runtime plain has no watch, so these wait tests stay as they are
        self.repo.set_conf("runtime", "plain")

    def put(self, *lines):
        with open(self.repo.path("agent_todo.txt"), "w") as fh:
            fh.write("".join(l + "\n" for l in lines))

    def one(self, fields, base=BASE):
        """The board row of the one line base + fields."""
        self.put(base + (" | " + fields if fields else ""))
        return self.row(self.rows(now=NOW), task="x")

    def status(self, fields, base=BASE):
        return self.one(fields, base)["Status"]

    def assertDash(self, r, est="-"):
        want = dict(DASH, Est=est)
        self.assertEqual({k: r[k] for k in want}, want, r)

    def line(self, folder=None, now=NOW):
        folder = folder or self.repo.dir
        stdin = json.dumps({"session_id": "s1", "cwd": folder,
                            "workspace": {"current_dir": folder, "project_dir": folder}})
        result = self.repo.run("agent-statusline.sh", cwd=self.repo.base, stdin=stdin,
                               env={"AGENT_FAKE_NOW": now}, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result.stdout.rstrip("\n")


# ---------------------------------------------------------------- rule 1: waiting rows


class TestWaitingRow(Case):
    def test_1_1_mock_on_the_owner_default_what(self):
        r = self.one("waiting mock since 2026-11-20 12:21")
        self.assertEqual(r["Status"], "等待 你 · 确认样稿或规则表 · 已等 10分钟")
        self.assertDash(r)
        self.assertEqual((r["Where"], r["Level"]), ("-", "L2"))

    def test_1_2_question_default_what(self):
        self.assertEqual(self.status("waiting question since 2026-11-20 10:21"),
                         "等待 你 · 回答问题 · 已等 2小时10分")

    def test_1_3_review_default_what_keeps_where_and_level(self):
        self.put(ST_REVIEW)
        r = self.row(self.rows(now=NOW), task="state-trim")
        self.assertEqual(r["Status"], "等待 你 · 合并前签字 · 已等 5分钟")
        self.assertDash(r)
        self.assertEqual((r["Where"], r["Level"]), (WHERE_ST, "L4"))

    def test_1_4_a_note_wins_over_the_default(self):
        self.assertEqual(self.status("waiting mock since 2026-11-20 12:21: 看规则表 v2"),
                         "等待 你 · 看规则表 v2 · 已等 10分钟")

    def test_1_5_someone_else(self):
        r = self.one("waiting hold since 2026-11-16 15:47: 回复插件更新和同步脚本 | who v4-Manager")
        self.assertEqual(r["Status"], "等待 v4-Manager · 回复插件更新和同步脚本 · 已等 3天20小时")
        self.assertDash(r)

    def test_1_6_review_by_someone_else(self):
        self.assertEqual(self.status("waiting review since 2026-11-20 12:01 | who v4-Manager"),
                         "等待 v4-Manager · 合并前签字 · 已等 30分钟")

    def test_1_7_who_you_is_the_owner(self):
        for who in ("you", "你", "owner", "Owner", "YOU"):
            with self.subTest(who=who):
                self.assertEqual(self.status("waiting hold since 2026-11-20 12:01: 选一个方案 | who " + who),
                                 "等待 你 · 选一个方案 · 已等 30分钟")

    def test_1_8_hold_with_who_no_note(self):
        self.assertEqual(self.status("waiting hold since 2026-11-20 12:01 | who v4-Manager"),
                         "等待 v4-Manager · 已等 30分钟")

    def test_a_long_note_is_cut_to_40_columns(self):
        self.assertEqual(
            self.status("waiting mock since 2026-11-20 12:21: 回复插件更新和同步脚本回复插件更新和同步脚本"),
            "等待 你 · 回复插件更新和同步脚本回复插件更新和同… · 已等 10分钟")
        self.assertEqual(
            self.status("waiting hold since 2026-11-20 12:21: v4-Manager: not now, ledger rollout final suite "
                        "+ staging | who v4-Manager"),
            "等待 v4-Manager · v4-Manager: not now, ledger rollout… · 已等 10分钟")


# ---------------------------------------------------------------- rule 2: hold rows


class TestHoldRow(Case):
    def test_2_1_hold_no_who(self):
        r = self.one("waiting hold since 2026-11-16 17:31: 你说合并监控之后再做")
        self.assertEqual(r["Status"], "暂缓 · 你说合并监控之后再做 · 已等 3天19小时")
        self.assertDash(r)
        self.assertEqual(r["Level"], "L2")

    def test_2_2_hold_no_note(self):
        self.assertEqual(self.status("waiting hold since 2026-11-20 12:01"), "暂缓 · 已等 30分钟")

    def test_2_3_long_note(self):
        self.assertEqual(
            self.status("waiting hold since 2026-11-16 17:31: owner close case 2026-11-16: after one-watcher"),
            "暂缓 · owner close case 2026-11-16: after… · 已等 3天19小时")


# ---------------------------------------------------------------- rule 3: queue rows


class TestQueueRow(Case):
    def test_3_1_queue_with_after(self):
        r = self.one("waiting queue since 2026-11-20 11:35 | after state-trim")
        self.assertEqual(r["Status"], "排队 · 在 state-trim 之后")
        self.assertDash(r)
        self.assertEqual((r["Where"], r["Level"]), ("-", "L2"))

    def test_3_2_old_note_after_task(self):
        self.assertEqual(self.status("waiting queue since 2026-11-20 11:35: after one-watcher"),
                         "排队 · 在 one-watcher 之后")
        self.assertEqual(self.status("waiting queue since 2026-11-20 11:35: After one-watcher, then the rest"),
                         "排队 · 在 one-watcher 之后")

    def test_3_3_after_wins_over_a_note(self):
        self.assertEqual(self.status("waiting queue since 2026-11-20 11:35: slot on pc2 | after state-trim"),
                         "排队 · 在 state-trim 之后")

    def test_3_4_neither(self):
        for fields in ("waiting queue since 2026-11-20 11:35",
                       "waiting queue since 2026-11-20 11:35: slot on pc2",
                       "waiting queue since 2026-11-20 11:35: after"):
            with self.subTest(fields=fields):
                self.assertEqual(self.status(fields), "排队")


# ---------------------------------------------------------------- rule 5: waited


class TestWaited(Case):
    def test_5_1_short_form(self):
        for since, want in (("2026-11-20 12:31", "0分钟"), ("2026-11-20 12:26", "5分钟"),
                            ("2026-11-20 10:21", "2小时10分"), ("2026-11-20 10:31", "2小时"),
                            ("2026-11-16 15:47", "3天20小时"), ("2026-11-19 12:31", "1天")):
            with self.subTest(since=since):
                self.assertEqual(self.status("waiting hold since " + since), "暂缓 · 已等 " + want)

    def test_5_0_the_run_field(self):
        self.assertEqual(
            self.status("waited 30m | waiting hold since 2026-11-20 12:01: x | who v4-Manager | "
                        "wait run since 2026-11-20 10:31"),
            "等待 v4-Manager · x · 已等 2小时")

    def test_5_0_waits_that_fill_the_time_from_opened(self):
        base = "x | big | the task | est 5m | opened 2026-11-20 10:00 | by main"
        self.assertEqual(self.status("waited 60m | waiting hold since 2026-11-20 11:00", base=base),
                         "暂缓 · 已等 2小时31分")
        self.assertEqual(self.status("waited 59m | waiting hold since 2026-11-20 11:00", base=base),
                         "暂缓 · 已等 1小时31分")

    def test_5_0_pc2_plugin_update_as_the_simulation(self):
        self.put(PC2)
        r = self.row(self.rows(now=NOW), task="pc2-plugin-update")
        self.assertEqual(r["Status"], "等待 v4-Manager · pc2 空闲时更新 plugin · 已等 2天19小时")
        self.assertEqual(r["Where"], "maverick-pc2")
        self.assertDash(r)


# ---------------------------------------------------------------- rule 6: work from the first stage


class TestWork(Case):
    def test_6_1_state_trim(self):
        self.put(ST_RUN)
        r = self.row(self.rows(now=NOW), task="state-trim")
        self.assertEqual([r[k] for k in tb.HEAD["en"]],
                         ["state-trim", "State file trim + auto clear at compact_clear_at", "进行中",
                          "██░░░░░░░░  20%", WHERE_ST, "L4", "1h 10m", "29m", "38m", "13:12"])

    def test_6_2_time_before_the_first_stage_is_no_work(self):
        r = self.one("", base="x | big | w | est 39m | opened 2026-11-20 11:35 | by main | "
                              "started 2026-11-20 12:21 | stage brief since 2026-11-20 12:21")
        self.assertEqual((r["Status"], r["Work"], r["Wait"], r["Done by"]), ("进行中", "10m", "0m", "13:00"))

    def test_6_2b_waits_before_the_start_do_not_count_twice(self):
        r = self.one("", base="x | big | w | est 39m | opened 2026-11-20 10:00 | by main | "
                              "started 2026-11-20 12:21 after 46m waited | waited 46m | "
                              "stage brief since 2026-11-20 12:21")
        self.assertEqual((r["Status"], r["Work"], r["Wait"], r["Done by"]), ("进行中", "10m", "46m", "13:00"))

    def test_waits_after_the_start_are_taken_off(self):
        r = self.one("", base="x | big | w | est 60m | opened 2026-11-20 10:00 | by main | "
                              "started 2026-11-20 11:31 after 20m waited | waited 50m | "
                              "stage tests since 2026-11-20 11:31")
        self.assertEqual((r["Progress"], r["Work"], r["Wait"], r["Done by"]),
                         ("██░░░░░░░░  25%", "30m", "50m", "13:01"))

    def test_6_3_not_started(self):
        self.put(OR)
        r = self.row(self.rows(now=NOW), task="owner-relay")
        self.assertEqual(r["Status"], "未开始")
        self.assertDash(r, est="42m")
        self.assertEqual((r["Where"], r["Level"]), ("-", "L3"))

    def test_6_3_not_started_is_never_over_its_estimate(self):
        r = self.one("", base="x | big | w | est 30m | opened 2026-11-20 08:00 | by main")
        self.assertEqual((r["Status"], r["Work"], r["Done by"]), ("未开始", "-", "-"))

    def test_6_4_old_line_with_a_stage_and_no_started(self):
        r = self.one("", base="x | big | w | est 60m | opened 2026-11-20 10:31 | by main | waited 30m | "
                              "stage workers since 2026-11-20 12:00")
        self.assertEqual((r["Status"], r["Progress"], r["Work"], r["Wait"], r["Done by"]),
                         ("进行中", "██████░░░░  65%", "1h 30m", "30m", "13:20"))

    def test_a_started_field_with_no_stage_field_counts(self):
        r = self.one("", base="x | big | w | est 60m | opened 2026-11-20 10:00 | by main | started 2026-11-20 12:00")
        self.assertEqual((r["Status"], r["Progress"], r["Work"], r["Done by"]), ("进行中", "-", "31m", "13:00"))

    def test_a_stray_who_field_on_a_running_line(self):
        r = self.one("who v4-Manager")
        self.assertEqual(r["Status"], "进行中")


# ---------------------------------------------------------------- rule 7: the wait ends


class TestWaitEnds(Case):
    def test_7_1_back_to_a_running_row(self):
        self.put(ST_REVIEW)
        self.wait("state-trim", "off", now=NOW)
        line = self.todo_line("state-trim")
        self.assertIn(" | waited 43m", line)
        self.assertIn(" | waited in stage 5m", line)
        self.assertNotIn("waiting ", line)
        r = self.row(self.rows(now=NOW), task="state-trim")
        self.assertEqual([r[k] for k in tb.HEAD["en"][2:]],
                         ["进行中", "████████░░  80%", WHERE_ST, "L4", "1h 10m", "24m", "43m", "13:17"])


# ---------------------------------------------------------------- rule 8: sort


class TestSort(Case):
    def test_8_the_groups(self):
        b = "big | w | est 60m | level 2 | opened 2026-11-10 09:00 | by main | started 2026-11-10 09:05 | stage tests since 2026-11-10 09:05"
        self.put(
            "h-1 | " + b + " | waiting hold since 2026-11-20 08:00",
            "q-1 | " + b + " | waiting queue since 2026-11-20 11:00",
            "ns-1 | big | w | est 60m | opened 2026-11-20 10:30 | by main",
            "oth-1 | " + b + " | waiting review since 2026-11-20 11:00 | who v4-Manager",
            "oth-2 | " + b + " | waiting hold since 2026-11-20 09:30 | who someone",
            "run-b | big | w | est 60m | opened 2026-11-20 10:00 | by main | started 2026-11-20 10:00 | stage tests since 2026-11-20 10:00",
            "run-a | big | w | est 60m | opened 2026-11-20 09:00 | by main | started 2026-11-20 09:00 | stage tests since 2026-11-20 09:00",
            "om-m | " + b + " | waiting mock since 2026-11-20 12:21",
            "om-h | " + b + " | waiting hold since 2026-11-20 12:01 | who you",
            "om-q | " + b + " | waiting question since 2026-11-20 10:21",
        )
        self.state("OWNER TODO: check the phone build\n")
        self.af("park", "add", "which DB for reports?", now="2026-11-20 12:00")
        got = [r["Task"] for r in self.rows(now=NOW)]
        self.assertEqual(got, ["om-q", "om-h", "om-m", "run-a", "run-b", "oth-2", "oth-1",
                               "ns-1", "q-1", "h-1", "-", "project"])


# ---------------------------------------------------------------- fixture F (the owner's simulation)


class TestSimulation(Case):
    ORDER = ["state-trim", "v4plus-followups", "pc2-plugin-update", "owner-relay", "comment-shape",
             "board-waiting", "usage-track", "one-watcher"]

    def test_the_board(self):
        self.put(*FIXTURE_F)
        rows = self.rows(now=NOW)
        self.assertEqual([r["Task"] for r in rows], self.ORDER)
        got = {r["Task"]: r for r in rows}
        self.assertEqual(got["v4plus-followups"]["Status"], "等待 v4-Manager · 回复插件更新和同步脚本 · 已等 3天20小时")
        self.assertEqual(got["pc2-plugin-update"]["Status"], "等待 v4-Manager · pc2 空闲时更新 plugin · 已等 2天19小时")
        self.assertEqual(got["board-waiting"]["Status"], "排队 · 在 state-trim 之后")
        self.assertEqual(got["usage-track"]["Status"], "暂缓 · 你说合并监控之后再做 · 已等 3天19小时")
        self.assertEqual(got["one-watcher"]["Status"], "暂缓 · owner close case 2026-11-18: next… · 已等 2天4小时")
        for name in ("owner-relay", "comment-shape"):
            self.assertEqual(got[name]["Status"], "未开始")
        self.assertEqual((got["owner-relay"]["Est"], got["comment-shape"]["Est"]), ("42m", "28m"))
        for name in ("v4plus-followups", "pc2-plugin-update", "board-waiting", "usage-track", "one-watcher"):
            self.assertDash(got[name])
        self.assertEqual(got["board-waiting"]["Level"], "L3")
        self.assertEqual(got["state-trim"]["Done by"], "13:12")

    def test_the_status_line(self):
        self.put(*FIXTURE_F)
        self.assertEqual(self.line(), "\n".join([
            name_col("state-trim") + "██░░░░░░░░  20%  写测试  13:12",
            name_col("v4plus-followups") + "等待 v4-Manager · 已等 3天20小时",
            name_col("pc2-plugin-update") + "等待 v4-Manager · 已等 2天19小时",
            name_col("owner-relay") + "未开始",   # one-watcher K: an own row while there is room
            "+4 排队/暂缓"]))

    def test_the_owner_moment(self):
        self.put(*[ST_REVIEW if l is ST_RUN else l for l in FIXTURE_F])
        rows = self.rows(now=NOW)
        top = rows[0]
        self.assertEqual([top[k] for k in tb.HEAD["en"][:1] + tb.HEAD["en"][2:]],
                         ["state-trim", "等待 你 · 合并前签字 · 已等 5分钟", "-", WHERE_ST, "L4", "-", "-", "-", "-"])
        self.assertEqual(self.line(), "\n".join([
            name_col("state-trim") + "等待 你 · 合并前签字 · 已等 5分钟",
            name_col("v4plus-followups") + "等待 v4-Manager · 已等 3天20小时",
            name_col("pc2-plugin-update") + "等待 v4-Manager · 已等 2天19小时",
            name_col("owner-relay") + "未开始",   # one-watcher K: an own row while there is room
            "+4 排队/暂缓"]))


class TestSimulationEnglish(Case):
    lang = "en"

    def test_the_words(self):
        self.put(*FIXTURE_F)
        got = {r["Task"]: r["Status"] for r in self.rows(now=NOW)}
        self.assertEqual(got, {
            "state-trim": "running",
            "v4plus-followups": "waiting v4-Manager · 回复插件更新和同步脚本 · waited 3d 20h",
            "pc2-plugin-update": "waiting v4-Manager · pc2 空闲时更新 plugin · waited 2d 19h",
            "owner-relay": "not started",
            "comment-shape": "not started",
            "board-waiting": "queue · after state-trim",
            "usage-track": "hold · 你说合并监控之后再做 · waited 3d 19h",
            "one-watcher": "hold · owner close case 2026-11-18: next… · waited 2d 4h",
        })

    def test_the_status_line(self):
        self.put(*FIXTURE_F)
        self.assertEqual(self.line(), "\n".join([
            name_col("state-trim") + "██░░░░░░░░  20%  tests  13:12",
            name_col("v4plus-followups") + "waiting v4-Manager · waited 3d 20h",
            name_col("pc2-plugin-update") + "waiting v4-Manager · waited 2d 19h",
            name_col("owner-relay") + "not started",   # one-watcher K
            "+4 queued/held"]))

    def test_the_owner_moment_and_defaults(self):
        self.put(*[ST_REVIEW if l is ST_RUN else l for l in FIXTURE_F])
        self.assertEqual(self.line().split("\n")[0], name_col("state-trim") + "waiting you · sign off before merge · waited 5m")
        self.assertEqual(self.status("waiting mock since 2026-11-20 12:21"),
                         "waiting you · check mock or rules table · waited 10m")
        self.assertEqual(self.status("waiting question since 2026-11-20 10:21"),
                         "waiting you · answer a question · waited 2h 10m")
        self.assertEqual(self.status("waiting hold since 2026-11-20 12:01"), "hold · waited 30m")
        self.assertEqual(self.status("waiting queue since 2026-11-20 11:35"), "queue")
        for since, want in (("2026-11-20 12:31", "0m"), ("2026-11-20 10:31", "2h"), ("2026-11-19 12:31", "1d")):
            self.assertEqual(self.status("waiting hold since " + since), "hold · waited " + want)


# ---------------------------------------------------------------- rule 9: the status line


class TestStatusLine(Case):
    def running(self, n, first=1):
        return ["t%d | big | w | est 120m | opened 2026-11-20 12:%02d | by main | started 2026-11-20 12:%02d | "
                "stage tests since 2026-11-20 12:%02d" % (i, i, i, i) for i in range(first, first + n)]

    def test_9_5_more_than_five_lines_fold(self):
        self.put(*(self.running(7) + ["h | big | w | est 5m | opened 2026-11-20 10:00 | by main | "
                                      "waiting hold since 2026-11-20 11:00"]))
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual([l.split()[0] for l in lines[:4]], ["t1", "t2", "t3", "t4"])
        self.assertEqual(lines[4], "+4 排队/暂缓")

    def test_9_5_six_running_no_fold_rows(self):
        self.put(*self.running(6))
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertEqual(lines[4], "+2 排队/暂缓")

    def test_9_6_five_lines_no_fold_line(self):
        self.put(*self.running(5))
        lines = self.line().split("\n")
        self.assertEqual(len(lines), 5, lines)
        self.assertNotIn("+", lines[4][:1])

    def test_9_6_nothing_prints_nothing(self):
        self.put()
        self.assertEqual(self.line(), "")

    def test_9_4_only_rows_that_fold(self):
        # one-watcher K (owner 2026-11-24): they fit, so each gets its own row, board order
        self.put(OR, CS, BW)
        self.assertEqual(self.line(), "\n".join([name_col("owner-relay") + "未开始", name_col("comment-shape") + "未开始",
                                                 name_col("board-waiting") + "排队 · 在 state-trim 之后"]))

    def test_9_7_helpers_workers_owner_todo_parked_are_not_counted(self):
        self.put(BW)
        self.state("OWNER TODO: check the phone build\n")
        self.af("park", "add", "which DB?", now=NOW)
        self.af("worker", "on", "1", "a slice", now=NOW)
        self.assertEqual(self.line(), name_col("board-waiting") + "排队 · 在 state-trim 之后")   # one-watcher K

    def test_owner_what_is_cut_to_24_columns(self):
        self.put(BASE + " | waiting mock since 2026-11-20 12:21: please check the rules table and the simulation")
        self.assertEqual(self.line(), name_col("x") + "等待 你 · please check the rules… · 已等 10分钟")

    def test_others_waits_drop_the_what(self):
        self.put(BASE + " | waiting review since 2026-11-20 12:01: plugin sign-off | who v4-Manager")
        self.assertEqual(self.line(), name_col("x") + "等待 v4-Manager · 已等 30分钟")

    def test_9_8_a_worktree_shows_its_own_row(self):
        alpha = self.task_worktree("alpha")
        self.put("alpha | big | w | est 60m | opened 2026-11-20 10:00 | by main | started 2026-11-20 10:00 | "
                 "stage mock since 2026-11-20 12:00 | waiting mock since 2026-11-20 12:21", BW)
        self.assertEqual(self.line(alpha), name_col("alpha") + "等待 你 · 确认样稿或规则表 · 已等 10分钟")
        self.put("alpha | big | w | est 60m | opened 2026-11-20 10:00 | by main | "
                 "waiting queue since 2026-11-20 11:00 | after state-trim")
        self.assertEqual(self.line(alpha), name_col("alpha") + "排队 · 在 state-trim 之后")   # one-watcher K6


# ---------------------------------------------------------------- rule 10: old lines


class TestOldLines(Case):
    def test_10_pc2_real_lines_render(self):
        self.put(*REAL)
        result = self.af("board", now=NOW)
        self.assertNotIn("Traceback", result.stderr)
        got = {r["Task"]: r["Status"] for r in self.table(result.stdout)}
        self.assertEqual(got, {
            "v4plus-followups": "暂缓 · v4-Manager: not now, ledger rollout… · 已等 3天20小时",
            "usage-track": "暂缓 · owner close case 2026-11-16: after… · 已等 3天19小时",
            "pc2-plugin-update": "暂缓 · handed to v4-Manager 2026-11-18… · 已等 2天19小时",
            "one-watcher": "暂缓 · owner close case 2026-11-18: next… · 已等 2天4小时",
            "owner-relay": "未开始",
            "comment-shape": "未开始",
        })
        # one-watcher K: 6 rows, 5 lines: 4 own rows by board order, the rest fold
        self.assertEqual(self.line(), "\n".join([
            name_col("owner-relay") + "未开始", name_col("comment-shape") + "未开始",
            name_col("v4plus-followups") + "暂缓 · 已等 3天20小时", name_col("usage-track") + "暂缓 · 已等 3天19小时",
            "+2 排队/暂缓"]))

    def test_10_odd_lines_never_crash(self):
        self.put("bare",
                 "two | fields",
                 "w | big | w | waiting hold since 2026-11-20 12:01: x | who",
                 "u | big | w | waiting queue since 2026-11-20 12:01 | after",
                 "s | big | w | started 2026-13-40 99:99 after xm waited | stage tests since 2026-11-20 12:00",
                 "r | big | w | waiting hold since 2026-11-20 12:01 | wait run since not-a-date")
        result = self.af("board", now=NOW)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(len(self.table(result.stdout)), 6)
        self.line()

    def test_10_a_wait_since_that_is_no_real_time(self):
        # verify finding (Worker 2 bounce 1): the date pattern matches, the date does not exist -> no crash,
        # the row keeps its kind and leaves the waited part out
        self.put("a | big | w | opened 2026-11-20 10:00 | by main | waiting hold since 2026-13-40 99:99: x",
                 "c | big | w | opened 2026-11-20 10:00 | by main | waiting review since 2026-02-30 10:00 | who v4-Manager")
        result = self.af("board", now=NOW)
        self.assertNotIn("Traceback", result.stderr)
        got = {r["Task"]: r["Status"] for r in self.table(result.stdout)}
        self.assertEqual(got, {"a": "暂缓 · x", "c": "等待 v4-Manager · 合并前签字"})
        # one-watcher K: the hold gets its own row; no real time -> no waited part
        self.assertEqual(self.line(), name_col("c") + "等待 v4-Manager\n" + name_col("a") + "暂缓")


# ---------------------------------------------------------------- rule 4: todo wait --who --after


class TestTodoWaitCli(Case):
    def setUp(self):
        super().setUp()
        self.add("x", "the task", 60, opened="2026-11-20 11:00", started=False)

    def test_4_1_mock_writes_no_who(self):
        self.wait("x", "on", "mock", now=NOW)
        line = self.todo_line("x")
        self.assertTrue(line.endswith(" | waiting mock since 2026-11-20 12:31"), line)
        self.assertNotIn(" | who ", line)

    def test_4_2_who(self):
        self.wait("x", "on", "review", "--who", "v4-Manager", now=NOW)
        self.assertTrue(self.todo_line("x").endswith(" | waiting review since 2026-11-20 12:31 | who v4-Manager"),
                        self.todo_line("x"))

    def test_4_3_the_note_before_or_after_the_options(self):
        want = " | waiting hold since 2026-11-20 12:31: 回复插件更新和同步脚本 | who v4-Manager"
        self.wait("x", "on", "hold", "回复插件更新和同步脚本", "--who", "v4-Manager", now=NOW)
        self.assertTrue(self.todo_line("x").endswith(want), self.todo_line("x"))
        self.wait("x", "off", now=NOW)
        self.wait("x", "on", "hold", "--who", "v4-Manager", "回复插件更新和同步脚本", now=NOW)
        self.assertTrue(self.todo_line("x").endswith(want), self.todo_line("x"))

    def test_a_who_with_a_space(self):
        self.wait("x", "on", "hold", "--who", "v4-plus Manager", now=NOW)
        self.assertTrue(self.todo_line("x").endswith(" | who v4-plus Manager"), self.todo_line("x"))

    def test_4_4_after(self):
        self.wait("x", "on", "queue", "--after", "state-trim", now=NOW)
        self.assertTrue(self.todo_line("x").endswith(" | waiting queue since 2026-11-20 12:31 | after state-trim"),
                        self.todo_line("x"))
        self.wait("x", "on", "queue", "slot", "--after", "state-trim", now="2026-11-20 12:40")
        self.assertIn(" | waiting queue since 2026-11-20 12:40: slot | after state-trim", self.todo_line("x"))
        self.assertEqual(self.todo_line("x").count(" | after "), 1, self.todo_line("x"))

    def test_4_5_a_wait_over_an_open_wait(self):
        self.wait("x", "on", "review", "--who", "A", now="2026-11-20 12:00")
        self.wait("x", "on", "hold", "n", now=NOW)
        line = self.todo_line("x")
        self.assertIn(" | waiting hold since 2026-11-20 12:31: n | wait run since 2026-11-20 12:00", line)
        self.assertNotIn(" | who ", line)
        self.assertIn(" | waited 31m", line)
        self.wait("x", "on", "hold", "--who", "B", now="2026-11-20 12:40")
        line = self.todo_line("x")
        self.assertIn(" | waiting hold since 2026-11-20 12:40 | who B | wait run since 2026-11-20 12:00", line)
        self.assertEqual(line.count("wait run since"), 1, line)
        self.assertIn(" | waited 40m", line)
        r = self.row(self.rows(now="2026-11-20 12:50"), task="x")
        self.assertEqual(r["Status"], "等待 B · 已等 50分钟")

    def test_4_5c_a_wait_over_a_wait_with_a_note(self):
        # reviewer finding 1: the date of a waiting field with a note was read with the note's colon
        self.wait("x", "on", "mock", "看规则表", now="2026-11-20 12:00")
        self.wait("x", "on", "mock", "看规则表 v2", now="2026-11-20 12:21")
        line = self.todo_line("x")
        self.assertIn(" | waiting mock since 2026-11-20 12:21: 看规则表 v2 | wait run since 2026-11-20 12:00 | "
                      "waited 21m", line)
        self.assertNotIn("12:00:", line)
        r = self.row(self.rows(now=NOW), task="x")
        self.assertEqual(r["Status"], "等待 你 · 看规则表 v2 · 已等 31分钟")
        self.wait("x", "on", "hold", "下一个: 等 v4", "--who", "v4-Manager", now="2026-11-20 12:25")
        self.assertIn(" | who v4-Manager | wait run since 2026-11-20 12:00 | waited 25m", self.todo_line("x"))
        self.wait("x", "off", now=NOW)
        self.assertIn(" | waited 31m", self.todo_line("x"))

    def test_4_5b_the_field_order(self):
        self.wait("x", "on", "queue", "--after", "a", now="2026-11-20 12:00")
        self.wait("x", "on", "queue", "--after", "b", now=NOW)
        line = self.todo_line("x")
        self.assertIn(" | waiting queue since 2026-11-20 12:31 | after b | wait run since 2026-11-20 12:00", line)
        self.assertNotIn("after a", line)

    def test_4_6_off_takes_the_fields_away(self):
        self.wait("x", "on", "review", "--who", "A", now="2026-11-20 12:00")
        self.wait("x", "on", "queue", "--after", "b", now="2026-11-20 12:10")
        self.wait("x", "off", now=NOW)
        line = self.todo_line("x")
        for gone in ("waiting ", " | who ", " | after ", "wait run since"):
            self.assertNotIn(gone, line)
        self.assertIn(" | waited 31m", line)
        self.wait("x", "on", "hold", now="2026-11-20 12:40")
        self.assertNotIn("wait run since", self.todo_line("x"))

    def test_4_7_refusals(self):
        for args in (("on", "queue", "--who", "a"),
                     ("on", "mock", "--after", "a"),
                     ("on", "hold", "--after", "a"),
                     ("on", "hold", "--who"),
                     ("on", "hold", "--who", ""),
                     ("on", "hold", "--who", "a | b"),
                     ("on", "hold", "--who", " "),
                     ("on", "hold", "--who", "--after"),
                     ("on", "queue", "--after", "--who"),
                     ("on", "queue", "--after", "  "),
                     ("on", "review", "--who", "a\nb"),
                     ("on", "hold", "--who", "a", "--who", "b"),
                     ("on", "queue", "--after"),
                     ("on", "queue", "--after", ""),
                     ("on", "queue", "--after", "a\nb"),
                     ("on", "queue", "--after", "a", "--after", "b"),
                     ("on", "hold", "--x", "a"),
                     ("on", "hold", "a", "b"),
                     ("off", "--who", "a")):
            with self.subTest(args=args):
                self.refused("todo", "wait", "x", *args, now=NOW)


# ---------------------------------------------------------------- rule 6: todo stage writes started


class TestTodoStageCli(Case):
    def stage(self, name, *args, now=NOW):
        self.af("todo", "stage", name, *args, now=now)

    def test_6_5_the_first_stage(self):
        self.add("x", "the task", 60, opened="2026-11-20 12:00", started=False)
        self.stage("x", "brief", now="2026-11-20 12:21")
        line = self.todo_line("x")
        self.assertIn(" | started 2026-11-20 12:21 | stage brief since 2026-11-20 12:21", line)
        self.assertNotIn(" after ", line)

    def test_6_6_after_closed_waits(self):
        self.add("x", "the task", 60, opened="2026-11-20 11:00", started=False)
        self.wait("x", "on", "queue", now="2026-11-20 11:35")
        self.wait("x", "off", now="2026-11-20 12:21")
        self.stage("x", "brief", now="2026-11-20 12:21")
        self.assertIn(" | started 2026-11-20 12:21 after 46m waited | stage brief since 2026-11-20 12:21",
                      self.todo_line("x"))

    def test_6_7_a_wait_still_open_at_the_start(self):
        self.add("x", "the task", 60, opened="2026-11-20 11:00", started=False)
        self.wait("x", "on", "queue", now="2026-11-20 11:41")
        self.wait("x", "off", now="2026-11-20 11:51")
        self.wait("x", "on", "hold", now="2026-11-20 11:51")
        self.stage("x", "brief", now="2026-11-20 12:21")
        self.assertIn(" | started 2026-11-20 12:21 after 40m waited", self.todo_line("x"))
        self.wait("x", "off", now="2026-11-20 12:41")
        r = self.row(self.rows(now="2026-11-20 12:51"), task="x")
        self.assertEqual((r["Status"], r["Work"], r["Wait"], r["Done by"]), ("进行中", "10m", "1h", "13:41"))

    def test_6_7b_an_open_wait_with_a_note_at_the_start(self):
        # reviewer finding 2: the open wait's since, read with the note's colon
        self.add("x", "the task", 60, opened="2026-11-20 11:00", started=False)
        self.wait("x", "on", "hold", "等: 槽位", now="2026-11-20 11:51")
        self.stage("x", "brief", now="2026-11-20 12:21")
        self.assertIn(" | started 2026-11-20 12:21 after 30m waited", self.todo_line("x"))

    def test_6_8_later_stages_never_change_it(self):
        self.add("x", "the task", 60, opened="2026-11-20 12:00", started=False)
        self.stage("x", "brief", now="2026-11-20 12:21")
        self.stage("x", "tests", now="2026-11-20 12:40")
        self.stage("x", "workers", "1/2", now="2026-11-20 12:45")
        line = self.todo_line("x")
        self.assertEqual(line.count(" | started "), 1, line)
        self.assertIn(" | started 2026-11-20 12:21 | ", line)

    def test_6_9_an_old_line_with_a_stage_gets_no_started(self):
        self.put("old | big | w | est 60m | opened 2026-11-20 10:31 | by main | stage tests since 2026-11-20 12:00")
        self.stage("old", "verify", now=NOW)
        self.assertNotIn("started", self.todo_line("old"))

    def test_6_10_a_worktree_with_no_todo_line(self):
        alpha = self.task_worktree("alpha")
        self.af("todo", "stage", "alpha", "brief", now=NOW, cwd=alpha)
        self.assertIn("STAGE alpha: brief | since 2026-11-20 12:31\n", self.state_text(alpha))
        self.assertNotIn("started", self.state_text(alpha))


# ---------------------------------------------------------------- the rule texts


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class TestRuleTexts(unittest.TestCase):
    def test_principles_w14(self):
        text = read("PRINCIPLES.md")
        w14 = text[text.index("W14. Show todo"):text.index("W15.")]
        for word in ("--who", "--after", "not started", "waiting on others", "first stage"):
            with self.subTest(word=word):
                self.assertIn(word, w14)

    def test_dispatch_board_records(self):
        text = read("skills", "dispatch", "SKILL.md")
        part = text[text.index("## Board records"):text.index("## Time question")]
        for word in ("--who", "--after"):
            with self.subTest(word=word):
                self.assertIn(word, part)

    def test_release_0_38_0(self):
        # main manager bounce 2026-11-20: board-waiting ships as release 0.38.0
        version = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        self.assertGreaterEqual(tuple(int(n) for n in version.split(".")), (0, 38, 0))

    def test_agent_file_header(self):
        head = "\n".join(l for l in read("bin", "agent-file.sh").splitlines()[:200] if l.startswith("#"))
        for word in ("--who", "--after", "wait run since", "started"):
            with self.subTest(word=word):
                self.assertIn(word, head)


if __name__ == "__main__":
    unittest.main()
