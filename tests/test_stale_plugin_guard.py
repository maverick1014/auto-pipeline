"""Failing tests for stale-plugin-guard. Written by the task manager, before any code.

WHY (v4-plus audit, 2026-11-16): the v4-plus main manager ran 0.32.0 paths for
3 days after 0.34.1 was installed (never got housekeep or the new estimator);
its project scope is still 0.32.0; on 2026-11-13 an old 0.32.0 session's
`todo done` retrain rewrote agent_estimate.txt as v1 only (idea #119).

CONTRACT

1. bin/agent-version.sh (new, executable, bash 3.2, no python on the check path)
   RUNNING = the folder name above this script's own bin/ (pwd -P), when it is a
     version: dotted digits only ("0.34.1"). Any other name (a repo bin/ copy,
     a cloud pack's ".claude/auto-pipeline", a sha folder) -> no running version.
   CACHE   = <claude dir>/plugins/cache/auto-pipeline/auto-pipeline, where
     <claude dir> = $CLAUDE_CONFIG_DIR when set and not empty, else $HOME/.claude.
   NEWEST  = the highest version folder in CACHE that holds bin/agent-start.sh.
     Compare numeric per part (0.34.10 > 0.34.9; missing parts are 0). A folder
     with another name, or without bin/agent-start.sh, never counts.
   STALE   = RUNNING and NEWEST both known and RUNNING < NEWEST. The running
     folder may sit outside CACHE (claude --plugin-dir <copy>/0.34.9).
   agent-version.sh running   prints RUNNING, or nothing. Exit 0.
   agent-version.sh newest    prints "<NEWEST>\t<CACHE>/<NEWEST>", or nothing. Exit 0.
   agent-version.sh check     STALE -> prints "<RUNNING>\t<NEWEST>\t<CACHE>/<NEWEST>",
                              exit 0. Else nothing at all, exit 1.
   agent-version.sh scopes <dir>...   see 3. Exit 0.
   agent-version.sh hook      see 2. Exit 0.
   Anything else -> a usage line on stderr, exit 2.

2. UserPromptSubmit hook: hooks/hooks.json runs
   "${CLAUDE_PLUGIN_ROOT}"/bin/agent-version.sh hook   (timeout 5), in that event only.
   Stdin: the hook JSON (session_id, cwd, prompt ...). Always exit 0, nothing on
   stderr, never blocks a prompt.
   Not STALE -> no output, no file, no python started, well under a second.
   STALE, and the project (stdin "cwd", else $CLAUDE_PROJECT_DIR, else $PWD;
   agent-roots.sh) has agent.conf -> ONE line:
     STALE PLUGIN: this session runs <RUNNING>, <NEWEST> is installed. Call <CACHE>/<NEWEST>/bin/... for every script and in every subagent brief. Restart this session at the next quiet point (claude --resume <session_id>).
   Once per session per NEWEST: marker "$PROJECT_GITDIR/agent_stale_<session_id>"
   holds the NEWEST it told. Same session, same NEWEST -> silent. A newer NEWEST
   later -> told again (with the new one). Another session -> told.
   No session_id in stdin -> $CLAUDE_CODE_SESSION_ID; neither -> the line ends
   "(claude --resume)." and no marker is written.
   No agent.conf in the project (the pipeline is not on there) -> silent.
   Nothing is written into the project's working tree.
   agent-start.sh prunes agent_stale_* like its other session markers (7 days).

3. Start text (bin/agent-start.sh), main manager / takeover / human-direct
   only, never a spawned agent (AGENT_ROLE set): for each entry of
   <claude dir>/plugins/installed_plugins.json "plugins"["auto-pipeline@auto-pipeline"]
   whose "version" (dotted digits) is older than NEWEST:
     scope "user" ->
       OLD PLUGIN: the user scope runs <old>, <NEWEST> is installed. Update it: claude plugin update auto-pipeline@auto-pipeline --scope user, then restart the session.
     scope "project" or "local" whose "projectPath" (realpath) is this project
     (the main worktree) or the git toplevel of the starting directory ->
       OLD PLUGIN: the <scope> scope of <projectPath> runs <old>, <NEWEST> is installed. Update it: cd <projectPath> && claude plugin update auto-pipeline@auto-pipeline --scope <scope>, then restart the session.
   Entries of other repos, current entries, a missing or broken file, no
   NEWEST -> no line. `agent-version.sh scopes <dir>...` prints these lines
   (dirs = the project paths to match); agent-start.sh calls it.

4. Old-writer guard (bin/agent-file.sh): when `agent-version.sh check` says
   STALE (from the same bin/ as agent-file.sh):
     retrain [--force] -> exactly one line
       "retrain skipped: <RUNNING> is older than installed <NEWEST>",
       exit 0, agent_estimate.txt untouched (not created, not changed).
     todo done -> works as before (line moved, data block written), and the
       retrain inside it is replaced by that same one line.
   agent-version.sh missing or not STALE -> retrain exactly as before.

5. PRINCIPLES.md W16: one bullet with "STALE PLUGIN" (newest bin path, every
   brief, restart, an older version never retrains), <= 200 chars.
   README.md tree lists bin/agent-version.sh. Release: plugin.json 0.35.0.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ScriptCase  # noqa: E402
from test_agent_estimate import EstimateCase, steady, NOW, version  # noqa: E402

CACHE_REL = (".claude", "plugins", "cache", "auto-pipeline", "auto-pipeline")
KEY = "auto-pipeline@auto-pipeline"
HOOK_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-version.sh hook'


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def section(text, start, end):
    lines = text.splitlines()
    begin = next(i for i, l in enumerate(lines) if l.startswith(start))
    stop = next(i for i in range(begin + 1, len(lines)) if lines[i].startswith(end))
    return lines[begin:stop]


class Versions:
    """Put the test's plugin copy into a version folder, with neighbours."""

    def cache_dir(self, config_dir=None):
        if config_dir:
            return os.path.join(config_dir, *CACHE_REL[1:])
        return os.path.join(self.repo.fake_home(), *CACHE_REL)

    def add_version(self, cache, name, with_start=True):
        folder = os.path.join(cache, name)
        os.makedirs(os.path.join(folder, "bin"), exist_ok=True)
        if with_start:
            with open(os.path.join(folder, "bin", "agent-start.sh"), "w") as fh:
                fh.write("#!/usr/bin/env bash\nexit 0\n")
            os.chmod(os.path.join(folder, "bin", "agent-start.sh"), 0o755)
        return folder

    def run_from(self, folder):
        """The plugin copy moves to `folder` (its name is the running version)."""
        os.makedirs(os.path.dirname(folder), exist_ok=True)
        shutil.move(self.repo.plugin, folder)
        self.repo.plugin = folder
        self.repo.plugin_bin = os.path.join(folder, "bin")
        return folder

    def stale_setup(self, running="0.34.1", newest="0.35.0", config_dir=None):
        cache = self.cache_dir(config_dir)
        os.makedirs(cache, exist_ok=True)
        self.run_from(os.path.join(cache, running))
        if newest and newest != running:
            self.add_version(cache, newest)
        return cache

    def ver(self, *args, env=None, stdin=None, cwd=None):
        return self.repo.run("agent-version.sh", *args, env=env or {},
                             stdin=stdin, cwd=cwd)


# ------------------------------------------------------------ 1: the check

class TestCheck(Versions, ScriptCase):
    script = "agent-version.sh"

    def test_older_than_installed_is_stale(self):
        cache = self.stale_setup("0.34.1", "0.35.0")
        r = self.ver("check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "0.34.1\t0.35.0\t%s/0.35.0\n" % cache)

    def test_running_and_newest(self):
        cache = self.stale_setup("0.34.1", "0.35.0")
        self.assertEqual(self.assertOk(self.ver("running")), "0.34.1\n")
        self.assertEqual(self.assertOk(self.ver("newest")), "0.35.0\t%s/0.35.0\n" % cache)

    def test_the_newest_is_current(self):
        cache = self.stale_setup("0.35.0", None)
        self.add_version(cache, "0.34.1")
        self.add_version(cache, "0.26.1")
        r = self.ver("check")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", ""))

    def test_numeric_compare(self):
        cache = self.stale_setup("0.34.9", "0.34.10")
        r = self.ver("check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "0.34.9\t0.34.10\t%s/0.34.10\n" % cache)

    def test_a_sha_folder_and_a_half_folder_never_count(self):
        cache = self.stale_setup("0.34.1", None)
        self.add_version(cache, "6a95022a8f9b")
        self.add_version(cache, "0.99.0", with_start=False)
        self.add_version(cache, "0.34.0")
        r = self.ver("check")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertEqual(self.assertOk(self.ver("newest")), "0.34.1\t%s/0.34.1\n" % cache)

    def test_a_running_copy_outside_the_cache(self):
        cache = self.cache_dir()
        self.add_version(cache, "0.35.0")
        self.run_from(os.path.join(self.repo.base, "e2e", "0.34.9"))
        r = self.ver("check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "0.34.9\t0.35.0\t%s/0.35.0\n" % cache)

    def test_a_running_copy_newer_than_the_cache(self):
        cache = self.cache_dir()
        self.add_version(cache, "0.35.0")
        self.run_from(os.path.join(self.repo.base, "e2e", "0.36.0"))
        r = self.ver("check")
        self.assertEqual((r.returncode, r.stdout), (1, ""))

    def test_a_repo_copy_is_never_stale(self):
        # the plugin folder of the fixture is named "plugin", like a repo bin/ copy
        self.add_version(self.cache_dir(), "0.35.0")
        r = self.ver("check")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", ""))
        self.assertEqual(self.assertOk(self.ver("running")), "")

    def test_a_cloud_pack_is_never_stale(self):
        self.add_version(self.cache_dir(), "0.35.0")
        self.run_from(os.path.join(self.repo.dir, ".claude", "auto-pipeline"))
        r = self.ver("check")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", ""))

    def test_no_cache_folder_is_silent(self):
        self.run_from(os.path.join(self.repo.base, "e2e", "0.34.1"))
        r = self.ver("check")   # no fake home: CLAUDE_CONFIG_DIR points nowhere
        self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", ""))
        self.assertEqual(self.assertOk(self.ver("newest")), "")

    def test_claude_config_dir_wins(self):
        conf = os.path.join(self.repo.base, "conf")
        cache = self.stale_setup("0.34.1", "0.35.0", config_dir=conf)
        r = self.ver("check", env={"CLAUDE_CONFIG_DIR": conf})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "0.34.1\t0.35.0\t%s/0.35.0\n" % cache)

    def test_a_bad_argument(self):
        for args in ((), ("nope",)):
            with self.subTest(args=args):
                r = self.ver(*args)
                self.assertEqual(r.returncode, 2)
                self.assertIn("usage", r.stderr.lower())
                self.assertEqual(r.stdout, "")


# ------------------------------------------------------------ 2: the hook

class TestHook(Versions, ScriptCase):
    script = "agent-version.sh"

    def payload(self, sid="s-1", cwd=None, prompt="hello"):
        data = {"transcript_path": "/tmp/none.jsonl", "cwd": cwd or self.repo.cwd,
                "permission_mode": "auto", "hook_event_name": "UserPromptSubmit",
                "prompt": prompt}
        if sid is not None:
            data["session_id"] = sid
        return json.dumps(data)

    def hook(self, stdin, env=None, cwd=None):
        r = self.ver("hook", stdin=stdin, env=env, cwd=cwd)
        self.assertOk(r)
        self.assertEqual(r.stderr, "", r.stderr)
        return r.stdout

    def line(self, cache, sid="s-1", running="0.34.1", newest="0.35.0"):
        tail = "(claude --resume %s)." % sid if sid else "(claude --resume)."
        return ("STALE PLUGIN: this session runs %s, %s is installed. Call %s/%s/bin/... for "
                "every script and in every subagent brief. Restart this session at the next "
                "quiet point %s\n" % (running, newest, cache, newest, tail))

    def test_stale_prints_one_line(self):
        cache = self.stale_setup()
        self.assertEqual(self.hook(self.payload()), self.line(cache))

    def test_once_per_session(self):
        cache = self.stale_setup()
        self.assertEqual(self.hook(self.payload()), self.line(cache))
        self.assertEqual(self.hook(self.payload(prompt="again")), "")
        self.assertEqual(self.hook(self.payload(prompt="and again")), "")

    def test_another_session_is_told(self):
        cache = self.stale_setup()
        self.hook(self.payload("s-1"))
        self.assertEqual(self.hook(self.payload("s-2")), self.line(cache, "s-2"))

    def test_a_newer_install_is_told_again(self):
        cache = self.stale_setup()
        self.hook(self.payload())
        self.add_version(cache, "0.36.0")
        self.assertEqual(self.hook(self.payload()), self.line(cache, newest="0.36.0"))
        self.assertEqual(self.hook(self.payload()), "")

    def test_the_marker_lives_in_the_git_dir(self):
        self.stale_setup()
        before = subprocess.run(["git", "-C", self.repo.dir, "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        self.hook(self.payload())
        marker = self.repo.path(".git", "agent_stale_s-1")
        self.assertTrue(os.path.isfile(marker), "no marker at %s" % marker)
        with open(marker) as fh:
            self.assertEqual(fh.read().strip(), "0.35.0")
        after = subprocess.run(["git", "-C", self.repo.dir, "status", "--porcelain"],
                               capture_output=True, text=True).stdout
        self.assertEqual(after, before)

    def test_a_worktree_finds_the_project(self):
        cache = self.stale_setup()
        wt = self.repo.detach_scripts_to_worktree()
        self.assertEqual(self.hook(self.payload(cwd=wt), cwd=wt), self.line(cache))

    def test_session_id_from_the_environment(self):
        cache = self.stale_setup()
        out = self.hook(self.payload(sid=None), env={"CLAUDE_CODE_SESSION_ID": "s-env"})
        self.assertEqual(out, self.line(cache, "s-env"))
        self.assertEqual(self.hook(self.payload(sid=None), env={"CLAUDE_CODE_SESSION_ID": "s-env"}), "")

    def test_no_session_id_at_all(self):
        cache = self.stale_setup()
        self.assertEqual(self.hook(self.payload(sid=None)), self.line(cache, None))
        leftovers = [n for n in os.listdir(self.repo.path(".git")) if n.startswith("agent_stale_")]
        self.assertEqual(leftovers, [])

    def test_bad_stdin_never_breaks(self):
        cache = self.stale_setup()
        for stdin in ("", "not json", "{"):
            with self.subTest(stdin=stdin):
                out = self.hook(stdin)
                self.assertIn(out, ("", self.line(cache, None)))

    def test_no_agent_conf_is_silent(self):
        self.stale_setup()
        os.remove(self.repo.path("agent.conf"))
        self.assertEqual(self.hook(self.payload()), "")

    def test_current_is_silent_and_cheap(self):
        cache = self.stale_setup("0.35.0", None)
        self.add_version(cache, "0.34.1")
        log = os.path.join(self.repo.base, "python.log")
        self.repo.stub_tool("python3", "#!/usr/bin/env bash\necho called >> %s\nexit 1\n" % log)
        t = time.time()
        out = self.hook(self.payload())
        self.assertLess(time.time() - t, 2.0)
        self.assertEqual(out, "")
        self.assertFalse(os.path.exists(log), "python3 was started on the not-stale path")
        leftovers = [n for n in os.listdir(self.repo.path(".git")) if n.startswith("agent_stale_")]
        self.assertEqual(leftovers, [])

    def test_a_repo_copy_is_silent(self):
        self.add_version(self.cache_dir(), "0.35.0")
        self.assertEqual(self.hook(self.payload()), "")


class TestHooksJson(unittest.TestCase):
    def hooks(self):
        return json.loads(read("hooks", "hooks.json"))["hooks"]

    def entries(self, event):
        return [h for e in self.hooks().get(event, []) for h in e.get("hooks", [])
                if "agent-version.sh" in h.get("command", "")]

    def test_user_prompt_submit_runs_it(self):
        found = self.entries("UserPromptSubmit")
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["command"], HOOK_COMMAND)
        self.assertEqual(found[0].get("type"), "command")
        self.assertLessEqual(found[0].get("timeout", 600), 10)

    def test_no_other_event_runs_it(self):
        for event in self.hooks():
            if event != "UserPromptSubmit":
                with self.subTest(event=event):
                    self.assertEqual(self.entries(event), [])


# ------------------------------------------------------------ 3: start text

class TestStartText(Versions, ScriptCase):
    script = "agent-start.sh"

    def installed(self, entries, raw=None):
        folder = os.path.join(self.repo.fake_home(), ".claude", "plugins")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "installed_plugins.json"), "w") as fh:
            if raw is not None:
                fh.write(raw)
            else:
                json.dump({"version": 2, "plugins": {KEY: entries}}, fh, indent=2)

    def entry(self, scope, ver, path=None):
        e = {"scope": scope, "version": ver,
             "installPath": "/x/cache/auto-pipeline/auto-pipeline/%s" % ver}
        if path:
            e["projectPath"] = path
        return e

    def start(self, env=None, cwd=None):
        return self.assertOk(self.repo.run("agent-start.sh", env=env or {}, cwd=cwd))

    def old_lines(self, out):
        return [l for l in out.splitlines() if l.startswith("OLD PLUGIN:")]

    def project_line(self, path, old, new="0.35.0", scope="project"):
        return ("OLD PLUGIN: the %s scope of %s runs %s, %s is installed. Update it: cd %s && "
                "claude plugin update auto-pipeline@auto-pipeline --scope %s, then restart the "
                "session." % (scope, path, old, new, path, scope))

    def user_line(self, old, new="0.35.0"):
        return ("OLD PLUGIN: the user scope runs %s, %s is installed. Update it: claude plugin "
                "update auto-pipeline@auto-pipeline --scope user, then restart the session."
                % (old, new))

    def setUp(self):
        super().setUp()
        # the running plugin is the newest: only the scope entries are old
        self.cache = self.stale_setup("0.35.0", None)

    def test_an_old_project_scope(self):
        self.installed([self.entry("project", "0.32.0", self.repo.dir),
                        self.entry("user", "0.35.0")])
        self.assertEqual(self.old_lines(self.start()), [self.project_line(self.repo.dir, "0.32.0")])

    def test_an_old_user_scope(self):
        self.installed([self.entry("user", "0.34.1")])
        self.assertEqual(self.old_lines(self.start()), [self.user_line("0.34.1")])

    def test_both_old(self):
        self.installed([self.entry("user", "0.34.1"),
                        self.entry("project", "0.32.0", self.repo.dir)])
        self.assertEqual(sorted(self.old_lines(self.start())),
                         sorted([self.user_line("0.34.1"),
                                 self.project_line(self.repo.dir, "0.32.0")]))

    def test_a_local_scope(self):
        self.installed([self.entry("local", "0.31.0", self.repo.dir)])
        self.assertEqual(self.old_lines(self.start()),
                         [self.project_line(self.repo.dir, "0.31.0", scope="local")])

    def test_a_worktree_entry_counts_from_inside_it(self):
        wt = self.repo.detach_scripts_to_worktree()
        self.installed([self.entry("project", "0.29.0", wt)])
        self.assertEqual(self.old_lines(self.start(cwd=wt)), [self.project_line(wt, "0.29.0")])

    def test_other_repos_and_current_entries_say_nothing(self):
        other = self.repo.make_project("other")
        self.installed([self.entry("project", "0.32.0", other),
                        self.entry("project", "0.35.0", self.repo.dir),
                        self.entry("user", "0.35.0")])
        self.assertEqual(self.old_lines(self.start()), [])

    def test_a_broken_or_missing_file_says_nothing(self):
        self.assertEqual(self.old_lines(self.start()), [])
        self.installed(None, raw="{not json")
        self.assertEqual(self.old_lines(self.start()), [])

    def test_a_spawned_agent_is_never_told(self):
        self.installed([self.entry("user", "0.34.1"),
                        self.entry("project", "0.32.0", self.repo.dir)])
        self.assertEqual(self.old_lines(self.start({"AGENT_ROLE": "task-manager"})), [])

    def test_scopes_cli(self):
        self.installed([self.entry("project", "0.32.0", self.repo.dir)])
        out = self.assertOk(self.ver("scopes", self.repo.dir))
        self.assertEqual(out.splitlines(), [self.project_line(self.repo.dir, "0.32.0")])


# ------------------------------------------------------------ 4: old-writer guard

class TestRetrainGuard(Versions, EstimateCase):
    script = "agent-file.sh"

    SKIP = "retrain skipped: 0.34.1 is older than installed 0.35.0"

    def setUp(self):
        super().setUp()
        if not os.path.exists(os.path.join(ROOT, "bin", "agent-version.sh")):
            self.fail("bin/agent-version.sh does not exist yet. Write it.")

    def todo(self, name="t-new"):
        self.write("agent_todo.txt", "%s | big | one shell script | est 50m | opened 2026-10-05 15:00 | by main\n" % name)

    def done(self, name="t-new"):
        return self.assertOk(self.af("todo", "done", name, "--work", "25", "--wait", "0",
                                     "--lane", "full", "--mock", "no", "--type", "script"))

    def test_retrain_is_skipped_when_stale(self):
        self.stale_setup()
        self.completed(steady(30))
        for args in ((), ("--force",)):
            with self.subTest(args=args):
                out = self.assertOk(self.af("retrain", *args))
                self.assertEqual(self.lines(out), [self.SKIP])
                self.assertIsNone(self.model_text())

    def test_an_existing_model_is_untouched(self):
        self.stale_setup()
        self.completed(steady(40))
        self.model(versions=[version()])
        before = self.model_text()
        out = self.assertOk(self.af("retrain", "--force"))
        self.assertEqual(self.lines(out), [self.SKIP])
        self.assertEqual(self.model_text(), before)

    def test_todo_done_still_works_and_skips_the_retrain(self):
        self.stale_setup()
        self.completed(steady(29))
        self.todo()
        out = self.done()
        self.assertIn("todo done: t-new", out)
        self.assertIn(self.SKIP, self.lines(out))
        self.assertEqual(self.verdicts(out), [])
        self.assertIsNone(self.model_text())
        self.assertIn(" | t-new | ", self.repo.read("agent_completed.txt"))
        self.assertEqual(self.repo.read("agent_todo.txt").strip(), "")

    def test_the_newest_still_retrains(self):
        self.stale_setup("0.35.0", None)
        self.add_version(self.cache_dir(), "0.34.1")
        self.completed(steady(30))
        out = self.assertOk(self.af("retrain"))
        self.assertNotIn("retrain skipped", out)
        self.assertEqual(self.model_json()["current"], 1)

    def test_a_repo_copy_still_retrains(self):
        self.add_version(self.cache_dir(), "0.35.0")
        self.completed(steady(30))
        out = self.assertOk(self.af("retrain"))
        self.assertNotIn("retrain skipped", out)
        self.assertEqual(self.model_json()["current"], 1)

    def test_no_version_script_still_retrains(self):
        self.stale_setup()
        os.remove(os.path.join(self.repo.plugin_bin, "agent-version.sh"))
        self.completed(steady(30))
        out = self.assertOk(self.af("retrain"))
        self.assertNotIn("retrain skipped", out)
        self.assertEqual(self.model_json()["current"], 1)


# ------------------------------------------------------------ 5: rule, docs, release

class TestRuleAndRelease(unittest.TestCase):
    def test_one_w16_line(self):
        lines = [l for l in section(read("PRINCIPLES.md"), "W16. ", "W17. ")
                 if l.startswith("- ") and "STALE PLUGIN" in l]
        self.assertEqual(len(lines), 1, "W16: one bullet names STALE PLUGIN")
        line = lines[0]
        for word in ("newest", "brief", "restart", "retrain"):
            self.assertIn(word, line)
        self.assertLessEqual(len(line), 200, line)

    def test_readme_lists_the_script(self):
        self.assertIn("bin/agent-version.sh", read("README.md"))

    def test_the_script_is_executable(self):
        self.assertTrue(os.access(os.path.join(ROOT, "bin", "agent-version.sh"), os.X_OK))

    def test_release(self):
        ver = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        self.assertEqual(ver, "0.35.0")


if __name__ == "__main__":
    unittest.main()
