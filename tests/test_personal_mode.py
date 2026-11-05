"""Failing tests for personal-mode (owner, 2026-11-04: "bypass only for my own
sessions, not the project base"; agent.conf is git-tracked and shared).
Written by the task manager, before any code.

CONTRACT

1. bin/agent_conf.py, the user-wide file
   USER_CONF_ENV = "AUTO_PIPELINE_USER_CONF"
   USER_KEYS = ("permission_mode", "cloud_permission_mode", "auto_update")
     (auto_update is part C, auto-update; it is never an agent.conf key)
   user_conf_path() -> $AUTO_PIPELINE_USER_CONF when set and not empty, else
     ~/.claude/auto-pipeline.conf ($HOME read at call time). One per machine,
     never in a repo.
   display_path(path) -> "~/<rest>" when PATH is under $HOME, else PATH.
   validate_value("auto_update", v) -> None for on / off exactly, else a
     message.
   read_user_conf(path=None) -> (values, ignored)
     values: {key: value} for a USER_KEYS key whose value validate_value()
     accepts. ignored: "key=value" strings, file order, for a refused value
     or a key outside USER_KEYS. Same file shape as agent.conf (load()):
     blank and # lines skipped, lines without "=" skipped, spaces around key
     and value stripped. PATH None -> user_conf_path(). Missing file, a
     directory, unreadable or undecodable -> ({}, []). Never raises.
   effective(key, conf, user_path=None) -> (value, source)
     CONF is a dict as load() returns. The user file's value first:
     (value, display_path(user file)). Else CONF[key] when validate_value()
     accepts it: (value, "agent.conf"). Else (None, None). auto_update never
     reads CONF. Never raises.
   CLI: `agent_conf.py effective <key> <agent.conf path>` -> stdout
     "<value>\t<source>\n", exit 0; nothing set -> no stdout, exit 1. A
     missing agent.conf path counts as empty. No traceback ever.

2. bin/agent-settings.sh
   get <key>   exactly ONE stdout line "<value> (from <source>)", exit 0, from
               effective(): the user file, else agent.conf. Not set anywhere:
               permission_mode / cloud_permission_mode -> "auto (default)",
               auto_update -> "on (default)", any other key -> nothing on
               stdout, a message on stderr, exit 1. Run from a worktree: still
               one line (no main-repo note), so its first word is the value.
   --user <key> <value>
               writes the user file, validated: only USER_KEYS (else exit 1,
               "not saved", file not created), value through validate_value
               (refused -> exit 1, "not saved", file unchanged). Creates the
               file and its folder; replaces that key's line or appends it;
               every other line kept. stdout: "saved: <key>=<value> in
               <display path>". Works with no agent.conf in the project.
               Never writes agent.conf.
   show        as before, then, only when the user file has an entry
               (honoured or ignored): a line starting "user file: <display
               path>", then one row per honoured key ("  <key>  <value>", the
               show column format), then "  ignored: <key>=<value>" per ignored
               entry. No user file -> output exactly as before.

3. Launch points use the effective value (user file, else agent.conf, else
   today's fallback)
   bin/agent_city.py agent_command(name, folder, city_dir=None, cloud=False):
     local: effective permission_mode, none -> no --permission-mode;
     cloud: effective cloud_permission_mode, none -> --permission-mode auto.
     The user file's permission_mode never decides a cloud line, its
     cloud_permission_mode never a local one. Never raises.
   bin/agent-resume.sh: --permission-mode is effective permission_mode, none
     -> auto.
   skills/dispatch/SKILL.md: <mode> comes from
     `${CLAUDE_PLUGIN_ROOT}/bin/agent-settings.sh get permission_mode`.
   PRINCIPLES.md W10: the "- Open a second session" line takes <mode> from
     `agent-settings.sh get permission_mode`; the "- New terminals" line names
     ~/.claude/auto-pipeline.conf (this machine's own, wins over agent.conf).
     S1 names ~/.claude/auto-pipeline.conf and `--user`.

4. Start text (bin/agent-start.sh), every role, not on the compact path:
   exactly one line
     "PERMISSION: <m> (from <src>), cloud page <c> (from <src>)"
   with "auto (default)" in place of "<v> (from <src>)" for a part not set
   anywhere. User file entries that are ignored -> exactly one line
     "USER CONF: ignored in <display path>: <key>=<value>, <key>=<value>"
   none ignored -> no USER CONF line.

5. Quiz Q35, rule W10, answer B: the user file wins over agent.conf for a new
   terminal (see test_decider_floor.TestQuiz36 for the full answer string).

6. bin/agent-init.sh keeps its 0.29.0 permission question (no change for A).
"""

import json
import os
import shlex
import subprocess
import sys
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
from scripthelp import ScriptCase, ScriptRepo  # noqa: E402

ENV = "AUTO_PIPELINE_USER_CONF"


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def section(text, start):
    """The lines of one rule: from the line starting START to the next rule head."""
    lines = text.splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith(start))
    out = [lines[i]]
    for l in lines[i + 1:]:
        if l.startswith("## ") or (l[:1] in "WSRHE" and len(l) > 2 and l[1].isdigit()):
            break
        out.append(l)
    return out


class TmpCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="personal_mode_"))
        import shutil
        self.addCleanup(shutil.rmtree, self.base, True)
        self.user = os.path.join(self.base, "u", "auto-pipeline.conf")
        patcher = mock.patch.dict(os.environ, {ENV: self.user})
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_user(self, text):
        os.makedirs(os.path.dirname(self.user), exist_ok=True)
        with open(self.user, "w") as fh:
            fh.write(text)


# ------------------------------------------------------------ 1: agent_conf

class TestUserConfPath(TmpCase):
    def test_constants(self):
        self.assertEqual(agent_conf.USER_CONF_ENV, ENV)
        self.assertEqual(tuple(agent_conf.USER_KEYS),
                         ("permission_mode", "cloud_permission_mode", "auto_update"))

    def test_the_env_var_wins(self):
        self.assertEqual(agent_conf.user_conf_path(), self.user)

    def test_unset_or_empty_is_the_home_file(self):
        home = os.path.join(self.base, "home")
        for env in ({ENV: "", "HOME": home}, {"HOME": home}):
            with self.subTest(env=sorted(env)):
                with mock.patch.dict(os.environ, env):
                    if ENV not in env:
                        os.environ.pop(ENV, None)
                    self.assertEqual(agent_conf.user_conf_path(),
                                     os.path.join(home, ".claude", "auto-pipeline.conf"))

    def test_display_path(self):
        home = os.path.join(self.base, "home")
        with mock.patch.dict(os.environ, {"HOME": home}):
            self.assertEqual(agent_conf.display_path(os.path.join(home, ".claude", "auto-pipeline.conf")),
                             "~/.claude/auto-pipeline.conf")
            self.assertEqual(agent_conf.display_path("/elsewhere/x.conf"), "/elsewhere/x.conf")
            self.assertEqual(agent_conf.display_path(home + "x/y.conf"), home + "x/y.conf",
                             "a sibling folder that only starts with the same letters is not under HOME")

    def test_auto_update_values(self):
        for value in ("on", "off"):
            with self.subTest(value=value):
                self.assertIsNone(agent_conf.validate_value("auto_update", value))
        for value in ("", "yes", "ON", " on", "true", "1"):
            with self.subTest(value=value):
                self.assertTrue(agent_conf.validate_value("auto_update", value))


class TestReadUserConf(TmpCase):
    def test_missing_file_is_empty(self):
        self.assertEqual(agent_conf.read_user_conf(), ({}, []))

    def test_honoured_keys(self):
        self.write_user("permission_mode=bypassPermissions\ncloud_permission_mode=plan\nauto_update=off\n")
        values, ignored = agent_conf.read_user_conf()
        self.assertEqual(values, {"permission_mode": "bypassPermissions",
                                  "cloud_permission_mode": "plan", "auto_update": "off"})
        self.assertEqual(ignored, [])

    def test_refused_values_and_other_keys_are_ignored_and_named(self):
        self.write_user("# mine\n\npermission_mode=yolo\nworker=sonnet-5:low\n"
                        "cloud_permission_mode = auto \nnot a line\nlanguage=zh\n")
        values, ignored = agent_conf.read_user_conf()
        self.assertEqual(values, {"cloud_permission_mode": "auto"})
        self.assertEqual(ignored, ["permission_mode=yolo", "worker=sonnet-5:low", "language=zh"])

    def test_an_explicit_path(self):
        other = os.path.join(self.base, "other.conf")
        with open(other, "w") as fh:
            fh.write("permission_mode=plan\n")
        self.assertEqual(agent_conf.read_user_conf(other), ({"permission_mode": "plan"}, []))

    def test_never_raises(self):
        os.makedirs(self.user)  # a directory where the file should be
        self.assertEqual(agent_conf.read_user_conf(), ({}, []))
        bad = os.path.join(self.base, "bad.conf")
        with open(bad, "wb") as fh:
            fh.write(b"\xff\xfe\x00permission_mode=\xc3\x28\n")
        values, ignored = agent_conf.read_user_conf(bad)
        self.assertIsInstance(values, dict)
        self.assertIsInstance(ignored, list)


class TestEffective(TmpCase):
    CONF = {"permission_mode": "auto", "cloud_permission_mode": "default", "auto_update": "off"}

    def test_user_file_wins(self):
        self.write_user("permission_mode=bypassPermissions\n")
        self.assertEqual(agent_conf.effective("permission_mode", self.CONF),
                         ("bypassPermissions", agent_conf.display_path(self.user)))
        self.assertEqual(agent_conf.effective("cloud_permission_mode", self.CONF),
                         ("default", "agent.conf"))

    def test_agent_conf_next(self):
        self.assertEqual(agent_conf.effective("permission_mode", self.CONF), ("auto", "agent.conf"))

    def test_a_refused_user_value_falls_back(self):
        self.write_user("permission_mode=yolo\n")
        self.assertEqual(agent_conf.effective("permission_mode", self.CONF), ("auto", "agent.conf"))

    def test_a_refused_agent_conf_value_is_not_set(self):
        self.assertEqual(agent_conf.effective("permission_mode", {"permission_mode": "yolo"}), (None, None))
        self.assertEqual(agent_conf.effective("permission_mode", {}), (None, None))

    def test_auto_update_never_reads_agent_conf(self):
        self.assertEqual(agent_conf.effective("auto_update", self.CONF), (None, None))
        self.write_user("auto_update=on\n")
        self.assertEqual(agent_conf.effective("auto_update", self.CONF),
                         ("on", agent_conf.display_path(self.user)))

    def test_an_explicit_user_path(self):
        other = os.path.join(self.base, "o.conf")
        with open(other, "w") as fh:
            fh.write("permission_mode=plan\n")
        self.assertEqual(agent_conf.effective("permission_mode", self.CONF, other)[0], "plan")

    def test_cli(self):
        conf = os.path.join(self.base, "agent.conf")
        with open(conf, "w") as fh:
            fh.write("permission_mode=auto\n")
        self.write_user("cloud_permission_mode=bypassPermissions\n")

        def run(*args):
            return subprocess.run([sys.executable, os.path.join(BIN, "agent_conf.py"), "effective"] + list(args),
                                  capture_output=True, text=True, env=dict(os.environ), timeout=30)

        r = run("permission_mode", conf)
        self.assertEqual((r.returncode, r.stdout), (0, "auto\tagent.conf\n"))
        r = run("cloud_permission_mode", conf)
        self.assertEqual((r.returncode, r.stdout),
                         (0, "bypassPermissions\t%s\n" % agent_conf.display_path(self.user)))
        r = run("auto_update", conf)
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        r = run("permission_mode", os.path.join(self.base, "missing.conf"))
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertNotIn("Traceback", r.stderr)


# ----------------------------------------------------- 2: agent-settings.sh

class SettingsCase(ScriptCase):
    script = "agent-settings.sh"

    def settings(self, *args, **kw):
        return self.repo.run("agent-settings.sh", *args, **kw)

    def user_text(self):
        with open(self.repo.user_conf) as fh:
            return fh.read()


class TestSettingsGet(SettingsCase):
    def test_from_agent_conf(self):
        self.repo.set_conf("permission_mode", "acceptEdits")
        out = self.assertOk(self.settings("get", "permission_mode"))
        self.assertEqual(out, "acceptEdits (from agent.conf)\n")

    def test_from_the_user_file(self):
        self.repo.set_conf("permission_mode", "auto")
        self.repo.set_user_conf("permission_mode=bypassPermissions\n")
        out = self.assertOk(self.settings("get", "permission_mode"))
        self.assertEqual(out, "bypassPermissions (from %s)\n" % self.repo.user_conf)

    def test_the_home_file_shows_with_a_tilde(self):
        home = self.repo.fake_home()
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "auto-pipeline.conf"), "w") as fh:
            fh.write("cloud_permission_mode=plan\n")
        out = self.assertOk(self.settings("get", "cloud_permission_mode", env={ENV: ""}))
        self.assertEqual(out, "plan (from ~/.claude/auto-pipeline.conf)\n")

    def test_not_set_anywhere(self):
        self.repo.unset_conf("permission_mode")
        self.repo.unset_conf("cloud_permission_mode")
        self.assertEqual(self.assertOk(self.settings("get", "permission_mode")), "auto (default)\n")
        self.assertEqual(self.assertOk(self.settings("get", "cloud_permission_mode")), "auto (default)\n")
        self.assertEqual(self.assertOk(self.settings("get", "auto_update")), "on (default)\n")

    def test_another_key(self):
        self.repo.set_conf("language", "ms")
        self.assertEqual(self.assertOk(self.settings("get", "language")), "ms (from agent.conf)\n")
        r = self.settings("get", "no_such_key")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertTrue(r.stderr.strip())

    def test_from_a_worktree_still_one_line(self):
        self.repo.git_init(self.repo.dir)
        wt = os.path.join(self.repo.base, "wt")
        subprocess.run(["git", "-C", self.repo.dir, "worktree", "add", "-q", wt, "-b", "wtb"],
                       check=True, capture_output=True)
        self.repo.set_conf("permission_mode", "plan")
        out = self.assertOk(self.settings("get", "permission_mode", cwd=wt))
        self.assertEqual(out, "plan (from agent.conf)\n")


class TestSettingsUser(SettingsCase):
    def test_writes_the_user_file(self):
        before = open(self.repo.path("agent.conf")).read()
        out = self.assertOk(self.settings("--user", "permission_mode", "bypassPermissions"))
        self.assertIn("saved: permission_mode=bypassPermissions in %s" % self.repo.user_conf, out)
        self.assertEqual(agent_conf.load(self.repo.user_conf), {"permission_mode": "bypassPermissions"})
        self.assertEqual(open(self.repo.path("agent.conf")).read(), before, "agent.conf is never written")

    def test_replaces_one_line_and_keeps_the_rest(self):
        self.repo.set_user_conf("# mine\npermission_mode=auto\ncloud_permission_mode=plan\n")
        self.assertOk(self.settings("--user", "permission_mode", "manual"))
        self.assertEqual(self.user_text(), "# mine\npermission_mode=manual\ncloud_permission_mode=plan\n")
        self.assertOk(self.settings("--user", "cloud_permission_mode", "bypassPermissions"))
        self.assertEqual(agent_conf.load(self.repo.user_conf),
                         {"permission_mode": "manual", "cloud_permission_mode": "bypassPermissions"})

    def test_only_the_user_keys(self):
        for key, value in (("worker", "sonnet-5:high"), ("language", "zh"), ("max_agents", "3")):
            with self.subTest(key=key):
                r = self.settings("--user", key, value)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("not saved", r.stdout + r.stderr)
                self.assertFalse(os.path.exists(self.repo.user_conf))

    def test_a_refused_value_changes_nothing(self):
        self.repo.set_user_conf("permission_mode=auto\n")
        r = self.settings("--user", "permission_mode", "yolo")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not saved", r.stdout + r.stderr)
        self.assertEqual(self.user_text(), "permission_mode=auto\n")

    def test_works_without_agent_conf(self):
        os.remove(self.repo.path("agent.conf"))
        self.assertOk(self.settings("--user", "permission_mode", "plan"))
        self.assertEqual(agent_conf.load(self.repo.user_conf), {"permission_mode": "plan"})
        self.assertFalse(os.path.exists(self.repo.path("agent.conf")))


class TestSettingsShow(SettingsCase):
    def test_no_user_file_is_unchanged(self):
        out = self.assertOk(self.settings())
        self.assertNotIn("user file", out)
        self.assertIn("permission_mode", out)

    def test_lists_the_overrides(self):
        self.repo.set_user_conf("permission_mode=bypassPermissions\nworker=x:low\n")
        out = self.assertOk(self.settings())
        lines = out.splitlines()
        i = next(n for n, l in enumerate(lines) if l.startswith("user file: %s" % self.repo.user_conf))
        rest = lines[i + 1:]
        self.assertTrue(any(l.split() == ["permission_mode", "bypassPermissions"] for l in rest), rest)
        self.assertIn("  ignored: worker=x:low", rest)
        self.assertTrue(any(l.split()[:1] == ["max_agents"] for l in lines[:i]),
                        "the agent.conf rows come first")


# ------------------------------------------------------- 3: launch points

class TestCityCommand(TmpCase):
    def repo_dir(self, conf):
        folder = os.path.join(self.base, "shop")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "agent.conf")
        if conf is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            with open(path, "w") as fh:
                fh.write(conf)
        return folder

    def mode(self, folder, cloud):
        words = shlex.split(ac.agent_command("shop Manager", folder, cloud=cloud))
        if "--permission-mode" not in words:
            return None
        return words[words.index("--permission-mode") + 1]

    def test_local_user_file_wins(self):
        folder = self.repo_dir("main_manager=opus-5.5:high\npermission_mode=auto\ncloud_permission_mode=auto\n")
        self.write_user("permission_mode=bypassPermissions\n")
        self.assertEqual(self.mode(folder, False), "bypassPermissions")
        self.assertEqual(self.mode(folder, True), "auto", "permission_mode never decides a cloud line")

    def test_cloud_user_file_wins(self):
        folder = self.repo_dir("main_manager=opus-5.5:high\npermission_mode=plan\ncloud_permission_mode=auto\n")
        self.write_user("cloud_permission_mode=bypassPermissions\n")
        self.assertEqual(self.mode(folder, True), "bypassPermissions")
        self.assertEqual(self.mode(folder, False), "plan", "cloud_permission_mode never decides a local line")

    def test_a_refused_user_value_falls_back(self):
        folder = self.repo_dir("main_manager=opus-5.5:high\npermission_mode=plan\n")
        self.write_user("permission_mode=yolo\ncloud_permission_mode=$(touch pwned)\n")
        self.assertEqual(self.mode(folder, False), "plan")
        self.assertEqual(self.mode(folder, True), "auto")
        self.assertFalse(os.path.exists(os.path.join(folder, "pwned")))

    def test_no_agent_conf_the_user_file_still_counts(self):
        folder = self.repo_dir(None)
        self.write_user("permission_mode=acceptEdits\n")
        self.assertEqual(self.mode(folder, False), "acceptEdits")
        self.write_user("")
        self.assertIsNone(self.mode(folder, False), "nothing set: as before, no flag")
        self.assertEqual(self.mode(folder, True), "auto")

    def test_the_rest_of_the_line_is_unchanged(self):
        folder = self.repo_dir("main_manager=opus-5.5:high\npermission_mode=auto\n")
        self.write_user("permission_mode=bypassPermissions\n")
        words = shlex.split(ac.agent_command("shop Manager", folder))
        self.assertEqual(words, ["claude", "--name", "shop Manager", "--model", "opus", "--effort", "high",
                                 "--permission-mode", "bypassPermissions", ac.FIRST_PROMPT])

    def test_never_raises(self):
        folder = self.repo_dir("main_manager=opus-5.5:high\npermission_mode=auto\n")
        os.makedirs(self.user)
        self.assertEqual(self.mode(folder, False), "auto")
        self.assertEqual(self.mode(folder, True), "auto")


class TestResume(ScriptCase):
    script = "agent-resume.sh"

    def command(self):
        path = self.repo.make_worktree("alpha")
        self.repo.set_worktree_lines([(path, "alpha", "working")])
        self.repo.set_panes([])
        self.assertOk(self.repo.run("agent-resume.sh"))
        calls = self.repo.create_calls()
        self.assertEqual(len(calls), 1, calls)
        return calls[0][calls[0].index("--command") + 1]

    def test_user_file_wins(self):
        self.repo.set_conf("permission_mode", "auto")
        self.repo.set_user_conf("permission_mode=bypassPermissions\ncloud_permission_mode=plan\n")
        self.assertTrue(self.command().endswith("--permission-mode bypassPermissions"))

    def test_agent_conf_without_a_user_file(self):
        self.repo.set_conf("permission_mode", "acceptEdits")
        self.assertTrue(self.command().endswith("--permission-mode acceptEdits"))

    def test_refused_user_value_falls_back(self):
        self.repo.set_conf("permission_mode", "plan")
        self.repo.set_user_conf("permission_mode=yolo\n")
        self.assertTrue(self.command().endswith("--permission-mode plan"))

    def test_only_cloud_in_the_user_file_does_not_count(self):
        self.repo.set_conf("permission_mode", "manual")
        self.repo.set_user_conf("cloud_permission_mode=bypassPermissions\n")
        self.assertTrue(self.command().endswith("--permission-mode manual"))

    def test_nothing_set_is_auto(self):
        self.repo.unset_conf("permission_mode")
        self.assertTrue(self.command().endswith("--permission-mode auto"))


class TestLaunchText(unittest.TestCase):
    def test_dispatch_reads_the_effective_mode(self):
        text = read("skills", "dispatch", "SKILL.md")
        line = next(l for l in text.splitlines() if "**orca**" in l and "<mode>" in l)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/agent-settings.sh get permission_mode", line)
        self.assertIn("--permission-mode <mode>", text)

    def test_w10_helper_line(self):
        text = read("PRINCIPLES.md")
        line = next(l for l in text.splitlines() if l.startswith("- Open a second session"))
        self.assertIn("agent-settings.sh get permission_mode", line)
        self.assertIn("--permission-mode <mode>", line)
        self.assertNotIn("--permission-mode auto", line)

    def test_w10_new_terminals_line(self):
        text = read("PRINCIPLES.md")
        line = next(l for l in text.splitlines() if l.startswith("- New terminals"))
        self.assertIn("~/.claude/auto-pipeline.conf", line)
        self.assertIn("cloud_permission_mode", line)
        self.assertIn("permission_mode", line)

    def test_s1_names_the_user_file(self):
        text = "\n".join(section(read("PRINCIPLES.md"), "S1. "))
        self.assertIn("~/.claude/auto-pipeline.conf", text)
        self.assertIn("--user", text)


# ------------------------------------------------------------ 4: start text

class StartCase(ScriptCase):
    script = "agent-start.sh"

    def start(self, env=None):
        env = dict(env or {})
        env.setdefault("AGENT_ROLE", "task-manager")
        return self.assertOk(self.repo.run("agent-start.sh", env=env))

    def lines_with(self, out, prefix):
        return [l for l in out.splitlines() if l.startswith(prefix)]


class TestStartPermissionLine(StartCase):
    def test_from_agent_conf(self):
        self.repo.set_conf("permission_mode", "acceptEdits")
        self.repo.set_conf("cloud_permission_mode", "auto")
        self.assertEqual(self.lines_with(self.start(), "PERMISSION:"),
                         ["PERMISSION: acceptEdits (from agent.conf), cloud page auto (from agent.conf)"])

    def test_from_the_home_user_file(self):
        home = self.repo.fake_home()
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "auto-pipeline.conf"), "w") as fh:
            fh.write("permission_mode=bypassPermissions\n")
        self.repo.set_conf("permission_mode", "auto")
        self.repo.set_conf("cloud_permission_mode", "auto")
        lines = self.lines_with(self.start(env={ENV: ""}), "PERMISSION:")
        self.assertEqual(lines, ["PERMISSION: bypassPermissions (from ~/.claude/auto-pipeline.conf), "
                                 "cloud page auto (from agent.conf)"])
        self.assertTrue(lines[0].startswith("PERMISSION: bypassPermissions (from ~/.claude/auto-pipeline.conf)"))

    def test_not_set(self):
        self.repo.unset_conf("permission_mode")
        self.repo.unset_conf("cloud_permission_mode")
        self.assertEqual(self.lines_with(self.start(), "PERMISSION:"),
                         ["PERMISSION: auto (default), cloud page auto (default)"])

    def test_the_main_manager_gets_it_too(self):
        out = self.assertOk(self.repo.run("agent-start.sh"))
        self.assertEqual(len(self.lines_with(out, "PERMISSION:")), 1)

    def test_ignored_entries_one_line(self):
        self.repo.set_conf("permission_mode", "plan")
        self.repo.set_user_conf("permission_mode=yolo\nworker=sonnet-5:low\ncloud_permission_mode=auto\n")
        out = self.start()
        self.assertEqual(self.lines_with(out, "USER CONF:"),
                         ["USER CONF: ignored in %s: permission_mode=yolo, worker=sonnet-5:low"
                          % self.repo.user_conf])
        self.assertEqual(self.lines_with(out, "PERMISSION:"),
                         ["PERMISSION: plan (from agent.conf), cloud page auto (from %s)" % self.repo.user_conf])

    def test_nothing_ignored_no_line(self):
        self.repo.set_user_conf("permission_mode=auto\n")
        self.assertEqual(self.lines_with(self.start(), "USER CONF:"), [])

    def test_still_under_the_cap(self):
        self.repo.set_user_conf("permission_mode=yolo\n")
        from test_output_hook import pointer_part
        out = pointer_part(self.start())
        self.assertLessEqual(len(out.encode()), 2000)


if __name__ == "__main__":
    unittest.main()
