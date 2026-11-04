"""Failing tests for decider-floor (owner, 2026-11-04, law 6 of his
~/.claude/CLAUDE.md): a decision maker runs Opus 5.5 or above, or any Fable,
at effort medium or above. Sonnet and Haiku never decide. Written by the task
manager, before any code.

CONTRACT

1. bin/agent_conf.py refuses a deciding role below the floor
   validate_value(key, value) for key main_manager or task_manager: the
   existing shape check first, then the floor. Model part (before ":"), an
   optional "claude-" prefix dropped:
     fable, fable-<anything>                         -> ok (any Fable)
     opus (the CLI alias, the newest Opus)           -> ok
     opus-<major>[.|-<minor>][-<anything>] with (major, minor) >= (5, 5);
       minor is 1 or 2 digits, a longer number (a date) is not a minor, so
       claude-opus-5-20260101 is Opus 5.0                -> ok / refused
     anything else (sonnet*, haiku*, an unknown name)  -> refused
   Effort low -> refused; medium, high, xhigh, max -> ok.
   The message names "Opus 5.5" and "Fable" and "medium". Worker and deputy
   keys keep the shape check only. HINTS[main_manager] and
   HINTS[task_manager] name the floor ("Opus 5.5", "Fable", "medium").

2. bin/agent_conf.py, own model and effort (the YOU line)
   you_line(args, env, settings, conf, role_key) -> str, never raises:
     "YOU: <model> <effort> (model: <src>, effort: <src>)"
   ARGS: the claude process's argv (list of str). ENV: a dict. SETTINGS: the
   parsed settings.json (anything not a dict counts as none). CONF: a dict as
   load() returns. ROLE_KEY: main_manager, task_manager, ...
   Model, first found:  --model X / --model=X in ARGS (last one wins) "flag";
     ENV ANTHROPIC_MODEL (not empty) "env"; SETTINGS["model"] "settings.json";
     the model part of CONF[ROLE_KEY] (shape model:effort) "agent.conf
     <role_key>"; else "unknown" / "unknown".
   Effort, first found: --effort X / --effort=X "flag";
     ENV CLAUDE_CODE_EFFORT_LEVEL "env";
     SETTINGS["modelSettings"][<id>]["effortLevel"] "settings.json", where
       <id> is the model found above when it is a key there, else, when that
       model is a bare family word (opus, sonnet, haiku, fable; a "[..]"
       suffix ignored), the "claude-<family>-..." key with the highest
       version numbers;
     SETTINGS["effortLevel"] "settings.json";
     the effort part of CONF[ROLE_KEY] "agent.conf <role_key>"; else
     "unknown" / "unknown".
   Empty strings count as not set.
   CLI: `agent_conf.py you <role_key> <agent.conf path> <pid>`: ARGS from
     `ps -o args= -p <pid>` split on white space, ENV = os.environ, SETTINGS
     from ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json (missing or
     broken -> none). Prints the line, exit 0, never a traceback.

3. Start text (bin/agent-start.sh), not on the compact path: exactly one
   line starting "YOU: ", the CLI above for this session's pid ($CLAUDE_PID,
   else the claude ancestor) and its role: main manager (main, takeover) ->
   main_manager; AGENT_ROLE set -> AGENT_ROLE with "-" as "_" when that is a
   role key, else task_manager; human-direct -> task_manager.

4. Quiz: 36 questions. Q35 (rule W10, answer B): the user file wins over
   agent.conf for a new terminal. Q36 (rule W17, answer C): an order marked
   "[Sonnet 5 medium]" -> do not act, ask the sender, tell the human.

5. Text
   PRINCIPLES.md "W17. Decider floor": one line per rule, "- " lines, each
   200 characters or fewer. Says: who decides (main manager, task manager,
   reviewer, any session whose order, decision or approval another agent
   acts on); the floor (Opus 5.5 or above, or any Fable, effort medium or
   above); Sonnet and Haiku never decide; sending: every order, decision or
   approval states the sender's model and effort first, e.g.
   "[Opus 5.5 xhigh] ..."; reports, heartbeats and questions are not orders;
   receiving: act only when it states both and both meet the floor, else do
   not act, ask the sender, tell the human; human messages are exempt; task
   managers and Helpers too; own values come from the YOU: line;
   agent_conf.py refuses a deciding role below the floor.
   W12 "- Send the brief" line: first line
   "[<model> <effort>] CROSS-REPO TASK <name> from <repo>".
   skills/dispatch: both brief blocks start with "[<model> <effort>]"; step 4
   (workers) says every worker brief starts with it; the fast-lane deputy
   "Brief:" too; says where the values come from (the YOU: line).
   skills/merge: the merge deputy brief block starts with "[<model>
   <effort>]"; names the YOU: line.
   skills/close-case: "[<model> <effort>] close case"; the finish-first order
   starts with it; names the YOU: line.
   agents/worker.md, merge-deputy.md, fast-lane-deputy.md: one line with the
   receiving check ("model and effort", "Opus 5.5", "Fable", "medium"); the
   file says do not act and to tell the human.
"""

import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_conf  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402

ANSWERS = ("1A 2D 3C 4B 5D 6D 7A 8C 9A 10D 11A 12C 13D 14C 15B 16C 17C "
           "18D 19B 20A 21D 22C 23B 24D 25A 26D 27A 28B 29B 30B 31B 32C 33B 34B 35B 36C 37C")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def rule(text, head):
    lines = text.splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith(head))
    out = []
    for l in lines[i + 1:]:
        if l.startswith("## ") or re.match(r"^[A-Z]\d+\. ", l):
            break
        if l.strip():
            out.append(l)
    return out


def block_after(text, marker):
    """The first ``` code block after the line holding MARKER, as lines."""
    lines = text.splitlines()
    i = next(n for n, l in enumerate(lines) if marker in l)
    j = next(n for n in range(i + 1, len(lines)) if lines[n].strip().startswith("```"))
    k = next(n for n in range(j + 1, len(lines)) if lines[n].strip().startswith("```"))
    return [l.strip() for l in lines[j + 1:k]]


# ------------------------------------------------------------ 1: the floor

class TestFloor(unittest.TestCase):
    OK_MODELS = ("fable-5.1", "fable", "fable-6", "claude-fable-5-1", "opus", "opus-5.5", "opus-5.6",
                 "opus-6", "opus-6.0", "opus-5.10", "claude-opus-5-5", "claude-opus-6",
                 "claude-opus-5-5-20261101")
    LOW_MODELS = ("opus-5", "opus-5.4", "opus-4.7", "claude-opus-4-1", "claude-opus-5-20260101",
                  "sonnet-5", "sonnet-5.5", "sonnet", "haiku-4.5", "claude-sonnet-5-5", "mystery-7", "gpt-5")

    def test_deciding_roles_at_or_above(self):
        for key in ("main_manager", "task_manager"):
            for model in self.OK_MODELS:
                for effort in ("medium", "high", "xhigh", "max"):
                    with self.subTest(key=key, value=model + ":" + effort):
                        self.assertIsNone(agent_conf.validate_value(key, model + ":" + effort))

    def test_deciding_roles_below_the_model_floor(self):
        for key in ("main_manager", "task_manager"):
            for model in self.LOW_MODELS:
                with self.subTest(key=key, model=model):
                    msg = agent_conf.validate_value(key, model + ":xhigh")
                    self.assertTrue(msg)
                    for word in ("Opus 5.5", "Fable", "medium"):
                        self.assertIn(word, msg)

    def test_deciding_roles_below_the_effort_floor(self):
        for key in ("main_manager", "task_manager"):
            for model in ("opus-5.5", "fable-5.1"):
                with self.subTest(key=key, model=model):
                    self.assertTrue(agent_conf.validate_value(key, model + ":low"))

    def test_bad_shapes_still_refused(self):
        for value in ("opus-5.5", "fable-5.1:ultra", ":high", ""):
            with self.subTest(value=value):
                self.assertTrue(agent_conf.validate_value("task_manager", value))

    def test_executing_roles_unchanged(self):
        for key in ("worker", "fast_lane_deputy", "merge_deputy"):
            for value in ("sonnet-5:low", "haiku-4.5:low", "mystery-7:medium", "opus-5.5:xhigh"):
                with self.subTest(key=key, value=value):
                    self.assertIsNone(agent_conf.validate_value(key, value))

    def test_hints_name_the_floor(self):
        for key in ("main_manager", "task_manager"):
            with self.subTest(key=key):
                for word in ("Opus 5.5", "Fable", "medium"):
                    self.assertIn(word, agent_conf.HINTS[key])

    def test_the_shipped_confs_pass(self):
        for path in (os.path.join(ROOT, "agent.conf"), os.path.join(BIN, "agent.conf.default")):
            with self.subTest(path=path):
                self.assertEqual(agent_conf.validate(agent_conf.load(path)), {})


class TestSettingsRefuse(ScriptCase):
    script = "agent-settings.sh"

    def test_below_the_floor_is_not_saved(self):
        before = open(self.repo.path("agent.conf")).read()
        for value in ("sonnet-5:high", "opus-5.5:low", "haiku-4.5:max"):
            with self.subTest(value=value):
                r = self.repo.run("agent-settings.sh", "task_manager", value)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("not saved", r.stdout + r.stderr)
                self.assertIn("Opus 5.5", r.stdout + r.stderr)
                self.assertEqual(open(self.repo.path("agent.conf")).read(), before)

    def test_at_the_floor_is_saved(self):
        self.assertOk(self.repo.run("agent-settings.sh", "task_manager", "fable-5.1:medium"))
        self.assertOk(self.repo.run("agent-settings.sh", "main_manager", "opus-5.5:high"))
        self.assertOk(self.repo.run("agent-settings.sh", "worker", "sonnet-5:low"))
        conf = agent_conf.load(self.repo.path("agent.conf"))
        self.assertEqual((conf["task_manager"], conf["main_manager"], conf["worker"]),
                         ("fable-5.1:medium", "opus-5.5:high", "sonnet-5:low"))


# --------------------------------------------------------- 2: the YOU line

def you(args=(), env=None, settings=None, conf=None, role="task_manager"):
    return agent_conf.you_line(list(args), dict(env or {}), settings, dict(conf or {}), role)


MODEL_SETTINGS = {"claude-opus-5": {"effortLevel": "high"},
                  "claude-opus-5-5": {"effortLevel": "xhigh"},
                  "claude-sonnet-5-5": {"effortLevel": "medium"},
                  "claude-sonnet-5": {"effortLevel": "low"}}


class TestYouLine(unittest.TestCase):
    def test_flags(self):
        self.assertEqual(you(["claude", "--name", "x Task Manager", "--model", "opus", "--effort", "xhigh",
                              "--permission-mode", "bypassPermissions"]),
                         "YOU: opus xhigh (model: flag, effort: flag)")

    def test_equals_form(self):
        self.assertEqual(you(["claude", "--model=sonnet", "--effort=low"]),
                         "YOU: sonnet low (model: flag, effort: flag)")

    def test_env(self):
        self.assertEqual(you(["claude"], {"ANTHROPIC_MODEL": "claude-opus-5-5", "CLAUDE_CODE_EFFORT_LEVEL": "high"}),
                         "YOU: claude-opus-5-5 high (model: env, effort: env)")

    def test_flag_beats_env_and_settings(self):
        self.assertEqual(you(["claude", "--model", "fable", "--effort", "max"],
                             {"ANTHROPIC_MODEL": "opus", "CLAUDE_CODE_EFFORT_LEVEL": "low"},
                             {"model": "sonnet", "effortLevel": "low"}),
                         "YOU: fable max (model: flag, effort: flag)")

    def test_env_beats_settings(self):
        self.assertEqual(you(["claude"], {"ANTHROPIC_MODEL": "opus"}, {"model": "sonnet", "effortLevel": "high"}),
                         "YOU: opus high (model: env, effort: settings.json)")

    def test_settings_alias_takes_the_newest_family_entry(self):
        self.assertEqual(you(["claude", "--dangerously-skip-permissions"], {},
                             {"model": "opus", "modelSettings": MODEL_SETTINGS}),
                         "YOU: opus xhigh (model: settings.json, effort: settings.json)")
        self.assertEqual(you(["claude"], {}, {"model": "sonnet[1m]", "modelSettings": MODEL_SETTINGS}),
                         "YOU: sonnet[1m] medium (model: settings.json, effort: settings.json)")

    def test_settings_exact_entry(self):
        self.assertEqual(you(["claude", "--model", "claude-opus-5"], {}, {"modelSettings": MODEL_SETTINGS}),
                         "YOU: claude-opus-5 high (model: flag, effort: settings.json)")

    def test_model_entry_beats_the_plain_effort_level(self):
        self.assertEqual(you(["claude"], {}, {"model": "opus", "effortLevel": "low",
                                              "modelSettings": MODEL_SETTINGS}),
                         "YOU: opus xhigh (model: settings.json, effort: settings.json)")

    def test_plain_effort_level(self):
        self.assertEqual(you(["claude"], {}, {"model": "sonnet", "effortLevel": "max"}),
                         "YOU: sonnet max (model: settings.json, effort: settings.json)")

    def test_agent_conf_last_and_marked(self):
        conf = {"task_manager": "opus-5.5:xhigh", "main_manager": "fable-5.1:high"}
        self.assertEqual(you(["claude", "--dangerously-skip-permissions"], {}, {}, conf, "main_manager"),
                         "YOU: fable-5.1 high (model: agent.conf main_manager, effort: agent.conf main_manager)")
        self.assertEqual(you(["claude", "--effort", "max"], {}, None, conf, "task_manager"),
                         "YOU: opus-5.5 max (model: agent.conf task_manager, effort: flag)")

    def test_unknown(self):
        self.assertEqual(you(["claude"]), "YOU: unknown unknown (model: unknown, effort: unknown)")
        self.assertEqual(you(["claude"], {}, None, {"task_manager": "opus"}),
                         "YOU: unknown unknown (model: unknown, effort: unknown)")

    def test_empty_and_junk_count_as_not_set(self):
        self.assertEqual(you(["claude"], {"ANTHROPIC_MODEL": "", "CLAUDE_CODE_EFFORT_LEVEL": ""},
                             ["not", "a", "dict"], {"task_manager": "opus-5.5:high"}),
                         "YOU: opus-5.5 high (model: agent.conf task_manager, effort: agent.conf task_manager)")
        self.assertEqual(you(["claude"], {}, {"model": "", "effortLevel": "", "modelSettings": {"x": 1}}),
                         "YOU: unknown unknown (model: unknown, effort: unknown)")
        self.assertEqual(you(["claude"], {}, {"model": "opus", "modelSettings": {"claude-opus-5-5": "xhigh"}}),
                         "YOU: opus unknown (model: settings.json, effort: unknown)")


class FakeClaude:
    """A live process whose argv carries the given flags, for CLAUDE_PID."""

    def __init__(self, *flags):
        self.proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"] + list(flags))

    def stop(self):
        self.proc.kill()
        self.proc.wait()


class TestYouCli(ScriptCase):
    def cli(self, pid, role="task_manager", env=None):
        e = self.repo._env(env)
        return subprocess.run([sys.executable, os.path.join(BIN, "agent_conf.py"), "you", role,
                               self.repo.path("agent.conf"), str(pid)],
                              capture_output=True, text=True, env=e, timeout=30)

    def fake(self, *flags):
        f = FakeClaude(*flags)
        self.addCleanup(f.stop)
        return f.proc.pid

    def test_flags_of_the_process(self):
        r = self.cli(self.fake("--model", "opus", "--effort", "xhigh"))
        self.assertEqual((r.returncode, r.stdout), (0, "YOU: opus xhigh (model: flag, effort: flag)\n"))

    def test_settings_of_the_home(self):
        home = self.repo.fake_home()
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "settings.json"), "w") as fh:
            fh.write('{"model": "opus", "modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}}')
        r = self.cli(self.fake())
        self.assertEqual(r.stdout, "YOU: opus xhigh (model: settings.json, effort: settings.json)\n")

    def test_claude_config_dir(self):
        cfg = os.path.join(self.repo.base, "cfg")
        os.makedirs(cfg)
        with open(os.path.join(cfg, "settings.json"), "w") as fh:
            fh.write('{"model": "fable", "effortLevel": "high"}')
        self.repo.fake_home()
        r = self.cli(self.fake(), env={"CLAUDE_CONFIG_DIR": cfg})
        self.assertEqual(r.stdout, "YOU: fable high (model: settings.json, effort: settings.json)\n")

    def test_agent_conf_and_broken_settings(self):
        home = self.repo.fake_home()
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "settings.json"), "w") as fh:
            fh.write("{broken")
        self.repo.set_conf("main_manager", "fable-5.1:xhigh")
        r = self.cli(self.fake(), role="main_manager")
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.stdout, "YOU: fable-5.1 xhigh (model: agent.conf main_manager, "
                                   "effort: agent.conf main_manager)\n")

    def test_a_dead_pid(self):
        f = FakeClaude()
        pid = f.proc.pid
        f.stop()
        self.repo.fake_home()
        self.repo.set_conf("task_manager", "opus-5.5:high")
        r = self.cli(pid)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "YOU: opus-5.5 high (model: agent.conf task_manager, "
                                   "effort: agent.conf task_manager)\n")


# ------------------------------------------------------ 3: the start text

class TestStartYou(ScriptCase):
    script = "agent-start.sh"

    def you_lines(self, env):
        out = self.assertOk(self.repo.run("agent-start.sh", env=env))
        return [l for l in out.splitlines() if l.startswith("YOU: ")]

    def fake(self, *flags):
        f = FakeClaude(*flags)
        self.addCleanup(f.stop)
        return str(f.proc.pid)

    def test_spawned_task_manager_with_flags(self):
        self.repo.fake_home()
        lines = self.you_lines({"AGENT_ROLE": "task-manager",
                                "CLAUDE_PID": self.fake("--model", "opus", "--effort", "xhigh")})
        self.assertEqual(lines, ["YOU: opus xhigh (model: flag, effort: flag)"])

    def test_spawned_task_manager_falls_back_to_its_role(self):
        self.repo.fake_home()
        self.repo.set_conf("task_manager", "opus-5.5:xhigh")
        lines = self.you_lines({"AGENT_ROLE": "task-manager", "CLAUDE_PID": self.fake()})
        self.assertEqual(lines, ["YOU: opus-5.5 xhigh (model: agent.conf task_manager, "
                                 "effort: agent.conf task_manager)"])

    def test_main_manager_falls_back_to_main_manager(self):
        self.repo.fake_home()
        self.repo.set_conf("main_manager", "fable-5.1:xhigh")
        lines = self.you_lines({"CLAUDE_PID": self.fake("--dangerously-skip-permissions")})
        self.assertEqual(lines, ["YOU: fable-5.1 xhigh (model: agent.conf main_manager, "
                                 "effort: agent.conf main_manager)"])

    def test_settings_json_of_the_home(self):
        home = self.repo.fake_home()
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "settings.json"), "w") as fh:
            fh.write('{"model": "opus", "effortLevel": "high"}')
        lines = self.you_lines({"AGENT_ROLE": "task-manager", "CLAUDE_PID": self.fake()})
        self.assertEqual(lines, ["YOU: opus high (model: settings.json, effort: settings.json)"])


# ------------------------------------------------------------- 4: the quiz

class TestQuiz36(ScriptCase):
    def quiz(self):
        return self.assertOk(self.repo.run("agent-start.sh", "--quiz"))

    def question(self, out, n):
        q = out[out.index("Q%d. " % n):]
        lines = q.splitlines()
        options = [l.strip() for l in lines[1:5]]
        self.assertEqual([o[:2] for o in options], ["A.", "B.", "C.", "D."])
        return lines[0], options

    def test_36_questions(self):
        out = self.quiz()
        self.assertIn("=== QUIZ — answer all 37 before any work ===", out)
        self.assertIn('--answer "1A 2B 3C ... 37D"', out)
        self.assertEqual(len(re.findall(r"(?m)^Q\d+\. ", out)), 37)

    def test_q35_is_the_user_file(self):
        head, options = self.question(self.quiz(), 35)
        self.assertIn("auto-pipeline.conf", head)
        self.assertIn("agent.conf", head)
        self.assertIn("auto-pipeline.conf", options[1])

    def test_q36_is_the_floor(self):
        head, options = self.question(self.quiz(), 36)
        self.assertIn("[Sonnet 5 medium]", head)
        self.assertIn("do not act", options[2].lower())
        self.assertIn("human", options[2])

    def test_all_pass(self):
        out = self.assertOk(self.repo.run("agent-start.sh", "--answer", ANSWERS))
        self.assertIn("QUIZ RESULT: 37/37 PASS", out)

    def test_wrong_letters_name_the_rule(self):
        for good, rule_code, wrongs in (("35B", "W10", ("35A", "35C", "35D")),
                                        ("36C", "W17", ("36A", "36B", "36D"))):
            for wrong in wrongs:
                with self.subTest(wrong=wrong):
                    r = self.repo.run("agent-start.sh", "--answer", ANSWERS.replace(good, wrong))
                    self.assertEqual(r.returncode, 1)
                    self.assertIn("Q%s(%s)" % (good[:2], rule_code), r.stdout)

    def test_the_old_34_answers_no_longer_pass(self):
        r = self.repo.run("agent-start.sh", "--answer", ANSWERS[:-8])
        self.assertEqual(r.returncode, 1)

    def test_usage_and_readme_say_36(self):
        src = read("bin", "agent-start.sh")
        self.assertIn("print the 37 quiz questions", src)
        self.assertIn('--answer "1A 2D ... 37C"', src)
        self.assertIn("37-question quiz", read("README.md"))


# -------------------------------------------------------------- 5: text

class TestRuleText(unittest.TestCase):
    def setUp(self):
        self.text = read("PRINCIPLES.md")
        self.w17 = rule(self.text, "W17. Decider floor")
        self.body = "\n".join(self.w17)

    def test_one_line_per_rule(self):
        self.assertGreaterEqual(len(self.w17), 6)
        for line in self.w17:
            with self.subTest(line=line[:40]):
                self.assertTrue(line.startswith("- "))
                self.assertLessEqual(len(line), 200)

    def test_who_and_the_floor(self):
        for words in ("main manager", "task manager", "reviewer", "Opus 5.5", "Fable", "medium",
                      "Sonnet", "Haiku"):
            with self.subTest(words=words):
                self.assertIn(words, self.body)
        self.assertTrue(re.search(r"Sonnet and Haiku never decide", self.body))

    def test_sending(self):
        self.assertIn("[Opus 5.5 xhigh]", self.body)
        self.assertIn("model and effort", self.body)
        self.assertIn("not orders", self.body)
        for word in ("Reports", "heartbeats", "questions"):
            self.assertIn(word, self.body)

    def test_receiving(self):
        low = self.body.lower()
        for words in ("do not act", "ask the sender", "tell the human", "exempt", "helper"):
            with self.subTest(words=words):
                self.assertIn(words, low)

    def test_own_values_and_the_validator(self):
        self.assertIn("YOU:", self.body)
        self.assertIn("agent_conf.py", self.body)

    def test_w12_first_line(self):
        line = next(l for l in self.text.splitlines() if l.startswith("- Send the brief"))
        self.assertIn("[<model> <effort>] CROSS-REPO TASK <name> from <repo>", line)


class TestSkillText(unittest.TestCase):
    TAG = "[<model> <effort>]"

    def test_dispatch(self):
        text = read("skills", "dispatch", "SKILL.md")
        self.assertTrue(block_after(text, "## Task manager brief")[0].startswith(
            self.TAG + " Brief from the main manager"))
        self.assertTrue(block_after(text, "## Cross-repo brief")[0].startswith(
            self.TAG + " CROSS-REPO TASK <name> from <repo>"))
        brief = block_after(text, "## Task manager brief")
        step4 = next(l for l in brief if l.startswith("4 workers"))
        self.assertIn(self.TAG, step4)
        fast = next(l for l in text.splitlines() if l.startswith("2. Small task"))
        self.assertIn(self.TAG, fast)
        self.assertIn("YOU:", text)

    def test_merge(self):
        text = read("skills", "merge", "SKILL.md")
        self.assertTrue(block_after(text, "subagent_type: merge-deputy")[0].startswith(self.TAG))
        self.assertIn("YOU:", text)

    def test_close_case(self):
        text = read("skills", "close-case", "SKILL.md")
        self.assertIn(self.TAG + " close case", text)
        finish = next(l for l in text.splitlines() if "**finish first**" in l)
        self.assertIn(self.TAG, finish)
        self.assertIn("YOU:", text)


class TestAgentText(unittest.TestCase):
    def test_every_executing_agent_checks(self):
        for name in ("worker.md", "merge-deputy.md", "fast-lane-deputy.md"):
            with self.subTest(agent=name):
                text = read("agents", name)
                line = next((l for l in text.splitlines()
                             if "model and effort" in l and "Opus 5.5" in l), None)
                self.assertIsNotNone(line, "no receiving check line")
                for word in ("Fable", "medium"):
                    self.assertIn(word, line)
                self.assertIn("do not act", text.lower())
                self.assertIn("human", text.lower())



from test_agent_close_case import CloseCaseCase  # noqa: E402


class TestTaggedCloseCaseStillFires(CloseCaseCase):
    def test_the_model_tag_before_close_case(self):
        for prompt in ("[Fable 5.1 xhigh] close case", "[Opus 5.5 xhigh] close case"):
            with self.subTest(prompt=prompt):
                self.assertIn("CLOSE CASE project: unfinished", self.as_task_manager(prompt))


if __name__ == "__main__":
    unittest.main()
