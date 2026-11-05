"""Failing tests for model-suffix (main manager brief, 2026-11-05): a role set
to a model with the 1M context suffix "[1m]" launches WITH it. Written by the
task manager, before any code.

CLI EVIDENCE (claude 2.1.318, 2026-11-05, one `claude -p --model <x>` call each):
  accepted: opus[1m], claude-opus-5-5[1m], fable[1m], claude-fable-5-1[1m],
            sonnet[1m]
  refused (unrecognized_model): opus-5.5[1m], fable-5.1[1m], opus[9z]
  zsh: an unquoted opus[1m] is a glob, "no matches found: opus[1m]".

CONTRACT

M1. bin/agent_conf.py cli_model(spec) keeps a trailing "[1m]" of the model
  part. The family rule is unchanged and the suffix goes back on after it:
    opus-5.5[1m]:xhigh -> opus[1m]      fable-5.1[1m]:high -> fable[1m]
    claude-opus-5-5[1m]:high -> claude-opus-5-5[1m]   (full id unchanged)
    mystery-7[1m] -> mystery-7[1m]      opus-5.5:xhigh -> opus (no suffix)
  `python3 bin/agent_conf.py cli-model <spec>` prints the same, one line.
  The decider floor is unchanged (tests/test_five_fixes.py S2).

M2. bin/agent-resume.sh: the relaunch --command is a shell line a zsh pane
  runs as is. A model word with shell-special characters is quoted, so zsh
  gives claude exactly "--model opus[1m]"; no "no matches found". A plain
  model word stays bare: "--model opus --effort xhigh" (tests/test_agent_resume.py
  pins that line). The fallback when python3 cannot answer is quoted too.

M3. bin/agent_city.py agent_command: the same line through zsh gives claude
  "--model opus[1m]" (main_manager=opus-5.5[1m]:high) and
  "--model claude-opus-5-5[1m]".

M4. skills/dispatch/SKILL.md: the typed launch line quotes the model,
  `--model '<model>'`, and says <model> is what
  `bin/agent_conf.py cli-model <task_manager value>` prints (the CLI refuses
  opus-5.5, takes opus). Every `--model <placeholder>` in skills/, agents/,
  PRINCIPLES.md and README.md is quoted the same way.

M5. The YOU line shows the model with its suffix, "YOU: opus[1m] xhigh
  (model: flag, effort: flag)", also through `agent_conf.py you` on a real
  process. The modelSettings effort lookup ignores the suffix: an exact key
  first ("claude-opus-5-5[1m]"), then the name without "[1m]"
  ("claude-opus-5-5"), then the family rule.
"""

import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin")
for p in (HERE, BIN):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent_conf  # noqa: E402
import agent_city as ac  # noqa: E402
from scripthelp import ScriptCase  # noqa: E402

ZSH = shutil.which("zsh")
ENV = "AUTO_PIPELINE_USER_CONF"


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def flag(words, name):
    return words[words.index(name) + 1] if name in words else None


class ZshRun:
    """Run a launch line in a real zsh (no rc files) with a fake `claude` first
    on PATH that prints each argument on its own line, then ROLE=$AGENT_ROLE."""

    def __init__(self, base):
        self.bin = os.path.join(base, "fakebin")
        os.makedirs(self.bin, exist_ok=True)
        exe = os.path.join(self.bin, "claude")
        with open(exe, "w") as fh:
            fh.write('#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done\nprintf "ROLE=%s\\n" "$AGENT_ROLE"\n')
        os.chmod(exe, os.stat(exe).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def __call__(self, line):
        env = dict(os.environ)
        env["PATH"] = self.bin + os.pathsep + env.get("PATH", "")
        env.pop("AGENT_ROLE", None)
        done = subprocess.run([ZSH, "-f", "-c", line], capture_output=True, text=True, env=env,
                              timeout=30, stdin=subprocess.DEVNULL)
        return done.returncode, done.stdout.splitlines(), done.stderr


# ===================================================================== M1

class TestCliModelKeepsTheSuffix(unittest.TestCase):
    TABLE = (("opus-5.5[1m]:xhigh", "opus[1m]"), ("opus-5.5[1m]", "opus[1m]"),
             ("fable-5.1[1m]:high", "fable[1m]"), ("fable[1m]", "fable[1m]"), ("opus[1m]:max", "opus[1m]"),
             ("sonnet-5[1m]:medium", "sonnet[1m]"), ("haiku-4.5[1m]:low", "haiku[1m]"),
             ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]"), ("claude-opus-5-5[1m]", "claude-opus-5-5[1m]"),
             ("claude-fable-5-1[1m]", "claude-fable-5-1[1m]"), ("mystery-7[1m]:high", "mystery-7[1m]"),
             ("opus-5.5:xhigh", "opus"), ("fable-5.1", "fable"), ("claude-opus-5-5:high", "claude-opus-5-5"),
             ("mystery-7:high", "mystery-7"))

    def test_the_rule(self):
        for spec, want in self.TABLE:
            with self.subTest(spec=spec):
                self.assertEqual(agent_conf.cli_model(spec), want)

    def test_the_command_line_says_the_same(self):
        for spec, want in self.TABLE:
            with self.subTest(spec=spec):
                done = subprocess.run([sys.executable, os.path.join(BIN, "agent_conf.py"), "cli-model", spec],
                                      capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
                self.assertEqual((done.returncode, done.stdout), (0, want + "\n"), done.stderr)

    def test_every_accepted_output_is_a_form_the_cli_takes(self):
        """Only the forms the CLI evidence accepted: <family>[1m] or claude-...[1m]."""
        accepted = re.compile(r"^(opus|sonnet|haiku|fable)(\[1m\])?$|^claude-[a-z0-9-]+(\[1m\])?$")
        for spec in ("opus-5.5[1m]:xhigh", "fable-5.1[1m]:xhigh", "claude-opus-5-5[1m]:xhigh",
                     "claude-fable-5-1[1m]:max", "opus[1m]:high"):
            with self.subTest(spec=spec):
                self.assertRegex(agent_conf.cli_model(spec), accepted)


# ===================================================================== M2

class TestResumeLineRunsInZsh(ScriptCase):
    script = "agent-resume.sh"

    def command(self, task_manager, module="alpha"):
        self.repo.clear_calls()
        path = self.repo.make_worktree(module)
        self.repo.set_conf("task_manager", task_manager)
        self.repo.set_conf("permission_mode", "auto")
        self.repo.set_worktree_lines([(path, module, "working")])
        self.repo.set_panes([])
        self.assertOk(self.repo.run("agent-resume.sh"))
        calls = self.repo.create_calls()
        self.assertEqual(len(calls), 1, calls)
        return calls[0][calls[0].index("--command") + 1]

    def test_the_words_keep_the_suffix(self):
        for spec, want, module in (("opus-5.5[1m]:xhigh", "opus[1m]", "a1"),
                                   ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]", "a2")):
            with self.subTest(spec=spec):
                words = shlex.split(self.command(spec, module))
                self.assertEqual(flag(words, "--model"), want)
                self.assertEqual(flag(words, "--effort"), spec.rsplit(":", 1)[1])

    @unittest.skipUnless(ZSH, "no zsh on PATH")
    def test_zsh_runs_the_line_without_a_glob_error(self):
        run = ZshRun(self.repo.path())
        for spec, want, effort, module in (("opus-5.5[1m]:xhigh", "opus[1m]", "xhigh", "z1"),
                                           ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]", "high", "z2"),
                                           ("fable-5.1[1m]:max", "fable[1m]", "max", "z3")):
            with self.subTest(spec=spec):
                code, out, err = run(self.command(spec, module))
                self.assertNotIn("no matches found", err)
                self.assertEqual((code, out), (0, ["--model", want, "--effort", effort,
                                                   "--permission-mode", "auto", "ROLE=task-manager"]), err)

    def test_a_plain_model_word_stays_bare(self):
        command = self.command("opus-5.5:xhigh", "p1")
        self.assertEqual(command, "AGENT_ROLE=task-manager claude --model opus --effort xhigh --permission-mode auto")

    @unittest.skipUnless(ZSH, "no zsh on PATH")
    def test_the_fallback_without_python_answer_is_quoted_too(self):
        """python3 cannot answer cli-model: the raw model part is used, and it
        must still survive zsh."""
        self.repo.write_bin_script("agent_conf.py", "import sys\nsys.exit(3)\n")
        command = self.command("mystery-7[1m]:high", "f1")
        code, out, err = ZshRun(self.repo.path())(command)
        self.assertNotIn("no matches found", err)
        self.assertEqual(code, 0, err)
        self.assertEqual(flag(out, "--model"), "mystery-7[1m]")


# ===================================================================== M3

class TestCityLineRunsInZsh(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="model_suffix_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        patcher = mock.patch.dict(os.environ, {ENV: os.path.join(self.base, "u", "auto-pipeline.conf")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def line(self, spec):
        folder = os.path.join(self.base, "f%d" % len(os.listdir(self.base)))
        os.makedirs(folder)
        with open(os.path.join(folder, "agent.conf"), "w") as fh:
            fh.write("main_manager=%s\npermission_mode=auto\n" % spec)
        return ac.agent_command("x Manager", folder)

    def test_the_model_word_keeps_the_suffix(self):
        for spec, want in (("opus-5.5[1m]:high", "opus[1m]"), ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]"),
                           ("fable-5.1[1m]:xhigh", "fable[1m]")):
            with self.subTest(spec=spec):
                words = shlex.split(self.line(spec))
                self.assertEqual(flag(words, "--model"), want)

    @unittest.skipUnless(ZSH, "no zsh on PATH")
    def test_zsh_runs_the_line_without_a_glob_error(self):
        run = ZshRun(self.base)
        for spec, want in (("opus-5.5[1m]:high", "opus[1m]"), ("claude-opus-5-5[1m]:high", "claude-opus-5-5[1m]")):
            with self.subTest(spec=spec):
                line = self.line(spec)
                code, out, err = run(line)
                self.assertNotIn("no matches found", err)
                self.assertEqual(code, 0, err)
                self.assertEqual(out[:-1], shlex.split(line)[1:])
                self.assertEqual(flag(out, "--model"), want)


# ===================================================================== M4

class TestTypedLaunchLines(unittest.TestCase):
    def dispatch(self):
        return read("skills", "dispatch", "SKILL.md")

    def test_the_dispatch_line_quotes_the_model(self):
        lines = [l for l in self.dispatch().splitlines() if "orca terminal create" in l and "claude" in l]
        self.assertTrue(lines, "the dispatch skill has a typed launch line")
        for line in lines:
            with self.subTest(line=line):
                self.assertIn("--model '<model>'", line)

    def test_the_dispatch_model_comes_from_cli_model(self):
        text = self.dispatch()
        self.assertIn("cli-model", text, "<model> is what agent_conf.py cli-model prints, not the raw conf name")

    def cli_model_command(self):
        """The one backticked `... agent_conf.py cli-model ...` command of the dispatch skill."""
        found = re.findall(r"`([^`]*agent_conf\.py cli-model[^`]*)`", self.dispatch())
        self.assertEqual(len(found), 1, found)
        return found[0]

    @unittest.skipUnless(ZSH, "no zsh on PATH")
    def test_the_dispatch_cli_model_command_runs_in_zsh(self):
        """Bounce 1: agent_conf.py has no exec bit and no shebang (needs python3),
        and an unquoted opus-5.5[1m]:xhigh is a zsh glob."""
        command = self.cli_model_command().replace("<task_manager value>", "opus-5.5[1m]:xhigh")
        self.assertNotIn("<", command, command)
        env = dict(os.environ, CLAUDE_PLUGIN_ROOT=ROOT)
        done = subprocess.run([ZSH, "-f", "-c", command], capture_output=True, text=True, env=env,
                              timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual((done.returncode, done.stdout), (0, "opus[1m]\n"), done.stderr)

    @unittest.skipUnless(ZSH, "no zsh on PATH")
    def test_the_dispatch_launch_line_runs_in_zsh(self):
        """The typed --command, its placeholders filled the way the skill says, runs in zsh."""
        line = [l for l in self.dispatch().splitlines() if "orca terminal create" in l and "claude" in l][0]
        inner = re.search(r'--command "([^"]*)"', line).group(1)
        filled = (inner.replace("<name>", "demo").replace("<model>", "opus[1m]")
                  .replace("<effort>", "xhigh").replace("<mode>", "auto"))
        self.assertNotIn("<", filled, filled)
        base = os.path.realpath(tempfile.mkdtemp(prefix="model_suffix_"))
        self.addCleanup(shutil.rmtree, base, True)
        code, out, err = ZshRun(base)(filled)
        self.assertNotIn("no matches found", err)
        self.assertEqual((code, out), (0, ["--name", "demo Task Manager", "--model", "opus[1m]", "--effort", "xhigh",
                                           "--permission-mode", "auto", "ROLE=task-manager"]), err)

    def test_no_unquoted_model_placeholder_anywhere(self):
        files = [os.path.join(ROOT, "PRINCIPLES.md"), os.path.join(ROOT, "README.md")]
        for folder in ("skills", "agents"):
            for top, _dirs, names in os.walk(os.path.join(ROOT, folder)):
                files += [os.path.join(top, n) for n in names if n.endswith(".md")]
        for path in files:
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                for number, line in enumerate(fh, 1):
                    for match in re.finditer(r"--model[ =](\S+)", line):
                        word = match.group(1)
                        if word.startswith("<") or word.startswith("$"):
                            with self.subTest(file=os.path.relpath(path, ROOT), line=number):
                                self.fail("unquoted model word %r: write --model '%s'" % (word, word))


# ===================================================================== M5

def you(args=(), env=None, settings=None, conf=None, role="task_manager"):
    return agent_conf.you_line(list(args), dict(env or {}), settings, dict(conf or {}), role)


MODEL_SETTINGS = {"claude-opus-5": {"effortLevel": "high"},
                  "claude-opus-5-5": {"effortLevel": "xhigh"},
                  "claude-sonnet-5-5": {"effortLevel": "medium"}}


class TestYouLineWithTheSuffix(unittest.TestCase):
    def test_flags_show_the_suffix(self):
        self.assertEqual(you(["claude", "--model", "opus[1m]", "--effort", "xhigh"]),
                         "YOU: opus[1m] xhigh (model: flag, effort: flag)")
        self.assertEqual(you(["claude", "--model=claude-opus-5-5[1m]", "--effort=high"]),
                         "YOU: claude-opus-5-5[1m] high (model: flag, effort: flag)")

    def test_the_full_id_effort_ignores_the_suffix(self):
        self.assertEqual(you(["claude", "--model", "claude-opus-5-5[1m]"], {}, {"modelSettings": MODEL_SETTINGS}),
                         "YOU: claude-opus-5-5[1m] xhigh (model: flag, effort: settings.json)")

    def test_an_exact_suffixed_entry_wins(self):
        table = dict(MODEL_SETTINGS, **{"claude-opus-5-5[1m]": {"effortLevel": "max"}})
        self.assertEqual(you(["claude", "--model", "claude-opus-5-5[1m]"], {}, {"modelSettings": table}),
                         "YOU: claude-opus-5-5[1m] max (model: flag, effort: settings.json)")

    def test_the_family_word_effort_ignores_the_suffix(self):
        self.assertEqual(you(["claude", "--model", "opus[1m]"], {}, {"modelSettings": MODEL_SETTINGS}),
                         "YOU: opus[1m] xhigh (model: flag, effort: settings.json)")


class TestYouCliWithTheSuffix(ScriptCase):
    def test_a_real_process(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)",
                                 "--model", "opus[1m]", "--effort", "xhigh"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        r = subprocess.run([sys.executable, os.path.join(BIN, "agent_conf.py"), "you", "task_manager",
                            self.repo.path("agent.conf"), str(proc.pid)],
                           capture_output=True, text=True, env=self.repo._env(None), timeout=30)
        self.assertEqual((r.returncode, r.stdout), (0, "YOU: opus[1m] xhigh (model: flag, effort: flag)\n"))


if __name__ == "__main__":
    unittest.main()
