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

OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"
VERIFIED = ("#!/usr/bin/env bash\n"
            "echo 'OWNER ORDER verified ~/.claude/projects/-r/s1.jsonl 2026-11-27 16:10'\n"
            "echo 'match: \"intended, usage\"'\nexit 0\n")


def transcript(path, model, extra=()):
    """A session transcript whose latest assistant message ran MODEL."""
    lines = [{"type": "user", "message": {"role": "user", "content": "hi"}}]
    lines += [{"type": "assistant", "message": {"role": "assistant", "model": m, "content": "x"}}
              for m in ([model] if model else [])]
    lines += list(extra)
    with open(path, "w") as fh:
        for obj in lines:
            fh.write(json.dumps(obj) + "\n")


class HookCase(ScriptCase):
    def prompt(self, model, text="merge cost-rules", sid="s1", **extra):
        path = os.path.join(self.repo.base, "t_%s.jsonl" % sid)
        transcript(path, model)
        payload = dict({"hook_event_name": "UserPromptSubmit", "session_id": sid, "cwd": self.repo.dir,
                        "prompt": text, "transcript_path": path}, **extra)
        r = self.repo.run("agent_model.py", "hook", stdin=json.dumps(payload))
        self.assertEqual((r.returncode, r.stderr), (0, ""), r.stderr)
        return r.stdout

    def ok(self, sid="s1"):
        return self.repo.run("agent-file.sh", "model", "ok", "--owner-quote", "intended, for usage reasons",
                             "--means", "the owner confirms the model change",
                             env={"CLAUDE_CODE_SESSION_ID": sid})

    def check(self, model, effort=None):
        return self.repo.run("agent-file.sh", "model", "check", model, *([effort] if effort else []))


class TestExamples(HookCase):
    def setUp(self):
        super().setUp()
        self.repo.write_bin_script("agent-owner-order.sh", VERIFIED)

    def test_1_the_hook_says_changed_and_below_floor(self):
        self.assertEqual(self.prompt(OPUS), "")          # first prompt of a session: stored, silent
        self.assertEqual(self.prompt(OPUS), "")          # same again: silent
        out = self.prompt(SONNET)
        self.assertEqual(out.splitlines(), ["MODEL CHANGED: opus-5.5 -> sonnet-5.5",
                                            "BELOW FLOOR: ask the owner first"])

    def test_2_intended_is_stored_and_the_receiver_accepts_the_header(self):
        self.prompt(OPUS)
        self.prompt(SONNET)
        self.assertEqual(self.check("sonnet-5.5", "medium").returncode, 1)   # 3: no record yet
        r = self.ok()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("MODEL OK sonnet-5.5", r.stdout)
        c = self.check("sonnet-5.5", "medium")
        self.assertEqual((c.returncode, c.stdout.strip()), (0, "MODEL OK sonnet-5.5 medium"))
        self.assertEqual(self.check("haiku-5", "medium").returncode, 1)     # the record is for that model only

    def test_an_unverified_quote_stores_nothing(self):
        self.prompt(OPUS)
        self.prompt(SONNET)
        self.repo.write_bin_script("agent-owner-order.sh", "#!/usr/bin/env bash\necho 'no such prompt'\nexit 1\n")
        self.assertEqual(self.ok().returncode, 1)
        self.assertEqual(self.check("sonnet-5.5", "medium").returncode, 1)

    def test_3_no_record_a_below_floor_header_is_not_accepted(self):
        r = self.check("sonnet-5.5", "medium")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MODEL OK", r.stdout + r.stderr)

    def test_5_switching_back_ends_the_record_and_asks_nothing(self):
        self.prompt(OPUS)
        self.prompt(SONNET)
        self.assertEqual(self.ok().returncode, 0)
        out = self.prompt(OPUS)
        self.assertEqual(out.splitlines(), ["MODEL CHANGED: sonnet-5.5 -> opus-5.5"])
        self.assertEqual(self.check("sonnet-5.5", "medium").returncode, 1)

    def test_a_change_above_the_floor_asks_nothing(self):
        self.prompt(OPUS)
        out = self.prompt("claude-fable-5-1")
        self.assertEqual(out.splitlines(), ["MODEL CHANGED: opus-5.5 -> fable-5.1"])

    def test_haiku_is_below_the_floor(self):
        self.prompt(OPUS)
        self.assertIn("BELOW FLOOR: ask the owner first", self.prompt("claude-haiku-4-5-20251001").splitlines())

    def test_a_session_started_with_a_flag_is_read_from_its_transcript(self):
        # Agent City and Orca start sessions with --model: an in-session /model is only in the transcript
        env = {"ANTHROPIC_MODEL": "opus-5.5", "CLAUDE_CODE_EFFORT_LEVEL": "xhigh"}
        path = os.path.join(self.repo.base, "t_s1.jsonl")
        payload = {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "cwd": self.repo.dir, "prompt": "x",
                   "transcript_path": path}
        out = []
        for model in (OPUS, SONNET):
            transcript(path, model)
            r = self.repo.run("agent_model.py", "hook", stdin=json.dumps(payload), env=env)
            out.append(r.stdout.splitlines())
        self.assertEqual(out, [[], ["MODEL CHANGED: opus-5.5 -> sonnet-5.5", "BELOW FLOOR: ask the owner first"]])

    def test_a_model_change_in_another_session_changes_nothing_here(self):
        self.prompt(OPUS, sid="a")
        self.prompt(OPUS, sid="b")
        self.assertIn("MODEL CHANGED", self.prompt(SONNET, sid="b"))
        self.assertEqual(self.prompt(OPUS, sid="a"), "")

    def test_the_settings_file_is_never_a_source(self):
        home = os.path.join(self.repo.base, "cfg")
        os.makedirs(home)
        with open(os.path.join(home, "settings.json"), "w") as fh:
            json.dump({"model": "sonnet", "effortLevel": "medium"}, fh)
        self.assertEqual(self.prompt(OPUS), "")
        path = os.path.join(self.repo.base, "t_s1.jsonl")
        r = self.repo.run("agent_model.py", "hook", env={"CLAUDE_CONFIG_DIR": home}, stdin=json.dumps(
            {"session_id": "s1", "cwd": self.repo.dir, "transcript_path": path}))
        self.assertEqual(r.stdout, "")

    def test_effort_is_not_tracked(self):
        self.prompt(OPUS)
        self.assertEqual(self.prompt(OPUS, text="x"), "")

    def test_sessions_are_kept_apart_and_an_agent_prompt_is_ignored(self):
        self.prompt(OPUS, sid="a")
        self.assertEqual(self.prompt(SONNET, sid="b"), "")        # b's first prompt
        self.assertEqual(self.prompt(SONNET, sid="a", agent_id="x"), "")
        self.assertIn("MODEL CHANGED", self.prompt(SONNET, sid="a"))

    def test_no_assistant_message_yet_says_nothing_and_never_fails(self):
        self.prompt(OPUS)
        self.assertEqual(self.prompt(None), "")

    def test_a_missing_transcript_says_nothing(self):
        r = self.repo.run("agent_model.py", "hook", stdin=json.dumps(
            {"session_id": "s1", "cwd": self.repo.dir, "transcript_path": "/nonexistent/t.jsonl"}))
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_only_the_tail_of_a_big_transcript_is_read(self):
        path = os.path.join(self.repo.base, "big.jsonl")
        transcript(path, SONNET)
        with open(path, "a") as fh:
            fh.write(json.dumps({"type": "user", "message": {"content": "x" * 900000}}) + "\n")
            fh.write(json.dumps({"type": "assistant", "message": {"model": OPUS}}) + "\n")
        sys.path.insert(0, os.path.join(ROOT, "bin"))
        import agent_model
        self.assertEqual(agent_model.current(path), "opus-5.5")


class TestGuardHeader(tg.GuardCase):
    def setUp(self):
        super().setUp()
        self.put_todo("t")
        self.make_main()

    def runs(self, model):
        transcript(os.path.join(self.cfg, "t.jsonl"), model)

    def launch(self, prompt, model, env=None):
        self.runs(model)
        inp = {"description": "t Deputy: go", "prompt": prompt, "subagent_type": "auto-pipeline:fast-lane-deputy"}
        return self.hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": inp,
                          "tool_use_id": self.tid()}, role=None, extra_env=env)

    def ok_record(self):
        gd = subprocess.run(["git", "-C", self.repo.dir, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True, check=True).stdout.strip()
        with open(os.path.join(gd, "agent_model_ok.json"), "w") as fh:
            json.dump({"model": "sonnet-5.5"}, fh)

    def test_4_on_sonnet_an_opus_header_is_refused(self):
        r = self.launch("[opus-5.5 xhigh] merge it", SONNET)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("header [opus-5.5 xhigh] is not your model [sonnet-5.5]: write [sonnet-5.5", r.stderr)

    def test_a_flag_session_that_ran_sonnet_takes_sonnet_and_refuses_opus(self):
        env = {"ANTHROPIC_MODEL": "opus-5.5", "CLAUDE_CODE_EFFORT_LEVEL": "xhigh"}
        self.ok_record()
        self.assertEqual(self.launch("[sonnet-5.5 medium] go", SONNET, env).returncode, 0)
        self.assertEqual(self.launch("[opus-5.5 xhigh] go", SONNET, env).returncode, 2)

    def test_another_session_s_model_in_settings_is_not_this_session(self):
        with open(os.path.join(self.cfg, "settings.json"), "w") as fh:
            json.dump({"model": "sonnet", "effortLevel": "medium"}, fh)
        r = self.launch("[opus-5.5 xhigh] go", OPUS)
        self.assertEqual((r.returncode, r.stderr), (0, ""))

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

    def test_the_effort_is_not_compared(self):
        r = self.launch("[opus-5.5 high] go", OPUS)
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_a_bare_family_matches_a_versioned_header(self):
        r = self.launch("[opus-5.5 xhigh] go", "opus")
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_no_header_is_not_this_rules_business(self):
        r = self.launch("brief without a header", SONNET)
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_unreadable_model_is_one_note_not_a_refusal(self):
        r = self.launch("[opus-5.5 xhigh] go", None)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertIn("not checked", r.stderr)

    def test_a_subagent_s_own_call_is_not_checked(self):
        self.runs(SONNET)
        inp = {"description": "t Worker 1: go", "prompt": "[opus-5.5 xhigh] go", "subagent_type": "auto-pipeline:worker"}
        r = self.hook({"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": inp,
                       "tool_use_id": self.tid(), "agent_id": "a1"})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_an_orchestration_message_is_checked(self):
        self.runs(SONNET)
        cmd = 'orca orchestration send --to term_1 --subject go --body "[opus-5.5 xhigh] go"'
        r = self.pre_bash(cmd)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("is not your model [sonnet-5.5]", r.stderr)
        self.ok_record()
        cmd = 'orca terminal send --terminal term_1 --text "[sonnet-5.5 medium] go" --enter'
        self.assertEqual(self.pre_bash(cmd).returncode, 0)


class TestRuleText(unittest.TestCase):
    def read(self, *p):
        with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
            return fh.read()

    def test_w17_names_the_header_and_the_model_ok_record(self):
        text = self.read("PRINCIPLES.md")
        w17 = text[text.index("## W17."):text.index("## Read when")]
        self.assertIn("MODEL OK", w17)
        self.assertRegex(w17, r"not the `YOU:` start text")

    def test_the_hook_is_registered(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json")) as fh:
            hooks = json.load(fh)
        cmds = [h["command"] for g in hooks["hooks"]["UserPromptSubmit"] for h in g["hooks"]]
        self.assertTrue(any("agent_model.py" in c and "hook" in c for c in cmds), cmds)

    def test_the_detail_is_in_a_rule_file(self):
        self.assertIn("MODEL OK", self.read("rules", "roles.md"))


if __name__ == "__main__":
    unittest.main()
