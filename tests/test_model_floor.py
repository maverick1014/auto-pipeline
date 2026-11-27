"""requirements/model-floor.md: the five examples, then the edges.

The sender's model and effort are read from the same sources as the YOU line (here: the env sources
ANTHROPIC_MODEL and CLAUDE_CODE_EFFORT_LEVEL), never copied from the start text.
"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import test_agent_guard as tg  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402

ROOT = os.path.dirname(HERE)

OPUS = {"ANTHROPIC_MODEL": "opus-5.5", "CLAUDE_CODE_EFFORT_LEVEL": "xhigh"}
SONNET = {"ANTHROPIC_MODEL": "sonnet-5.5", "CLAUDE_CODE_EFFORT_LEVEL": "medium"}
VERIFIED = ("#!/usr/bin/env bash\n"
            "echo 'OWNER ORDER verified ~/.claude/projects/-r/s1.jsonl 2026-11-27 16:10'\n"
            "echo 'match: \"intended, usage\"'\nexit 0\n")


class HookCase(ScriptCase):
    def prompt(self, env, text="merge cost-rules", sid="s1", **extra):
        payload = dict({"hook_event_name": "UserPromptSubmit", "session_id": sid, "cwd": self.repo.dir,
                        "prompt": text}, **extra)
        r = self.repo.run("agent_model.py", "hook", stdin=json.dumps(payload), env=env)
        self.assertEqual((r.returncode, r.stderr), (0, ""), r.stderr)
        return r.stdout

    def ok(self, env, *more):
        return self.repo.run("agent-file.sh", "model", "ok", "--owner-quote", "intended, for usage reasons",
                             "--means", "the owner confirms the model change", *more, env=env)

    def check(self, env, model, effort):
        return self.repo.run("agent-file.sh", "model", "check", model, effort, env=env)


class TestExamples(HookCase):
    def setUp(self):
        super().setUp()
        self.repo.write_bin_script("agent-owner-order.sh", VERIFIED)

    def test_1_the_hook_says_changed_and_below_floor(self):
        self.assertEqual(self.prompt(OPUS), "")          # first prompt of a session: stored, silent
        self.assertEqual(self.prompt(OPUS), "")          # same again: silent
        out = self.prompt(SONNET)
        self.assertEqual(out.splitlines(), ["MODEL CHANGED: opus-5.5 xhigh -> sonnet-5.5 medium",
                                            "BELOW FLOOR: ask the owner first"])

    def test_2_intended_is_stored_and_the_receiver_accepts_the_header(self):
        self.prompt(OPUS)
        self.prompt(SONNET)
        self.assertEqual(self.check(SONNET, "sonnet-5.5", "medium").returncode, 1)   # 3: no record yet
        r = self.ok(SONNET)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("MODEL OK sonnet-5.5 medium", r.stdout)
        c = self.check(SONNET, "sonnet-5.5", "medium")
        self.assertEqual((c.returncode, c.stdout.strip()), (0, "MODEL OK sonnet-5.5 medium"))
        # the record holds for that model and effort only
        self.assertEqual(self.check(SONNET, "sonnet-5.5", "high").returncode, 1)
        self.assertEqual(self.check(SONNET, "haiku-5", "medium").returncode, 1)
        # an unverified quote stores nothing
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho 'no such prompt'\nexit 1\n")
        r2 = self.ok(dict(SONNET, CLAUDE_CODE_EFFORT_LEVEL="high"))
        self.assertEqual(r2.returncode, 1)
        self.assertEqual(self.check(dict(SONNET, CLAUDE_CODE_EFFORT_LEVEL="high"), "sonnet-5.5", "high").returncode, 1)

    def test_3_no_record_a_below_floor_header_is_not_accepted(self):
        r = self.check(SONNET, "sonnet-5.5", "medium")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MODEL OK", r.stdout + r.stderr)

    def test_5_switching_back_ends_the_record_and_asks_nothing(self):
        self.prompt(OPUS)
        self.prompt(SONNET)
        self.assertEqual(self.ok(SONNET).returncode, 0)
        out = self.prompt(OPUS)
        self.assertEqual(out.splitlines(), ["MODEL CHANGED: sonnet-5.5 medium -> opus-5.5 xhigh"])
        self.assertEqual(self.check(SONNET, "sonnet-5.5", "medium").returncode, 1)

    def test_a_change_above_the_floor_asks_nothing(self):
        self.prompt(OPUS)
        out = self.prompt(dict(OPUS, CLAUDE_CODE_EFFORT_LEVEL="high"))
        self.assertEqual(out.splitlines(), ["MODEL CHANGED: opus-5.5 xhigh -> opus-5.5 high"])

    def test_low_effort_is_below_the_floor(self):
        self.prompt(OPUS)
        out = self.prompt(dict(OPUS, CLAUDE_CODE_EFFORT_LEVEL="low"))
        self.assertIn("BELOW FLOOR: ask the owner first", out.splitlines())

    def test_sessions_are_kept_apart_and_an_agent_prompt_is_ignored(self):
        self.prompt(OPUS, sid="a")
        self.assertEqual(self.prompt(SONNET, sid="b"), "")        # b's first prompt
        self.assertEqual(self.prompt(SONNET, sid="a", agent_id="x"), "")
        self.assertIn("MODEL CHANGED", self.prompt(SONNET, sid="a"))

    def test_unreadable_model_says_nothing_and_never_fails(self):
        self.prompt(OPUS)
        self.assertEqual(self.prompt({"ANTHROPIC_MODEL": "", "CLAUDE_CODE_EFFORT_LEVEL": ""}), "")

    def test_a_model_name_with_the_claude_id_reads_as_the_short_name(self):
        self.prompt({"ANTHROPIC_MODEL": "claude-opus-5-5", "CLAUDE_CODE_EFFORT_LEVEL": "xhigh"})
        out = self.prompt(SONNET)
        self.assertIn("MODEL CHANGED: opus-5.5 xhigh -> sonnet-5.5 medium", out)


class TestGuardHeader(tg.GuardCase):
    def setUp(self):
        super().setUp()
        self.put_todo("t")
        self.make_main()

    def launch(self, prompt, env):
        inp = {"description": "t Deputy: go", "prompt": prompt, "subagent_type": "auto-pipeline:fast-lane-deputy"}
        return self.hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": inp,
                          "tool_use_id": self.tid()}, role=None, extra_env=env)

    def test_4_on_sonnet_an_opus_header_is_refused(self):
        r = self.launch("[opus-5.5 xhigh] merge it", SONNET)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("header [opus-5.5 xhigh] is not your model [sonnet-5.5 medium]: write [sonnet-5.5 medium]",
                      r.stderr)

    def ok_record(self):
        gd = subprocess.run(["git", "-C", self.repo.dir, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True, check=True).stdout.strip()
        with open(os.path.join(gd, "agent_model_ok.json"), "w") as fh:
            json.dump({"model": "sonnet-5.5", "effort": "medium"}, fh)

    def test_2_the_honest_header_goes_through_once_the_owner_said_it_is_intended(self):
        self.ok_record()
        r = self.launch("[sonnet-5.5 medium] merge it", SONNET)
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_below_the_floor_without_the_owner_s_yes_the_main_manager_sends_nothing(self):
        r = self.launch("[sonnet-5.5 medium] merge it", SONNET)
        self.assertEqual(r.returncode, 2)
        self.assertIn("below the floor", r.stderr)

    def test_above_the_floor_the_honest_header_goes_through(self):
        r = self.launch("[opus-5.5 xhigh] merge it", OPUS)
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_a_wrong_effort_is_refused_too(self):
        r = self.launch("[opus-5.5 high] go", OPUS)
        self.assertEqual(r.returncode, 2)
        self.assertIn("header [opus-5.5 high] is not your model [opus-5.5 xhigh]", r.stderr)

    def test_a_bare_family_matches_a_versioned_header(self):
        r = self.launch("[opus-5.5 xhigh] go", {"ANTHROPIC_MODEL": "opus", "CLAUDE_CODE_EFFORT_LEVEL": "xhigh"})
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_no_header_is_not_this_rules_business(self):
        r = self.launch("brief without a header", SONNET)
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_unreadable_current_value_is_one_note_not_a_refusal(self):
        r = self.launch("[opus-5.5 xhigh] go", {"ANTHROPIC_MODEL": "", "CLAUDE_CODE_EFFORT_LEVEL": ""})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertIn("not checked", r.stderr)

    def test_a_subagent_s_own_call_is_not_checked(self):
        inp = {"description": "t Worker 1: go", "prompt": "[opus-5.5 xhigh] go", "subagent_type": "auto-pipeline:worker"}
        r = self.hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": inp,
                       "tool_use_id": self.tid(), "agent_id": "a1"}, extra_env=SONNET)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_an_orchestration_message_is_checked(self):
        cmd = 'orca orchestration send --to term_1 --subject go --body "[opus-5.5 xhigh] go"'
        r = self.pre_bash(cmd, extra_env=SONNET)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("is not your model [sonnet-5.5 medium]", r.stderr)
        self.ok_record()
        cmd = 'orca terminal send --terminal term_1 --text "[sonnet-5.5 medium] go" --enter'
        self.assertEqual(self.pre_bash(cmd, extra_env=SONNET).returncode, 0)


class TestRuleText(unittest.TestCase):
    def read(self, *p):
        with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
            return fh.read()

    def test_w17_names_the_header_and_the_model_ok_record(self):
        text = self.read("PRINCIPLES.md")
        w17 = text[text.index("## W17."):text.index("## Read when")]
        self.assertIn("MODEL OK", w17)
        self.assertRegex(w17, r"never copied|read it now|current")

    def test_the_hook_is_registered(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json")) as fh:
            hooks = json.load(fh)
        cmds = [h["command"] for g in hooks["hooks"]["UserPromptSubmit"] for h in g["hooks"]]
        self.assertTrue(any("agent_model.py" in c and "hook" in c for c in cmds), cmds)

    def test_the_detail_is_in_a_rule_file(self):
        self.assertIn("MODEL OK", self.read("rules", "roles.md"))


if __name__ == "__main__":
    unittest.main()
