"""Failing tests for session names. Written by the task manager first.

Owner, 2026-09-30: "Can the hook rename? When the agent opens and knows it is
the main manager, rename to '[Repo name] Manager'; a task manager is
'[Feature] Task Manager'; a worker is '[Feature] Worker'."

CONTRACT. bin/agent-name.sh is a second SessionStart hook (hooks.json), next
to agent-start.sh (which stays plain text: one hook cannot print both text
for the context and JSON). Claude Code gives it JSON on stdin
{"session_id", "transcript_path", "cwd", "hook_event_name", "source"}. It
prints nothing, or exactly one JSON object on one line:

    {"hookSpecificOutput": {"hookEventName": "SessionStart",
                            "sessionTitle": "<name>"}}

Claude Code sets the session's title from sessionTitle: the prompt box, the
/resume picker, the terminal title, and the name ListAgents shows and
SendMessage uses as the address.

Always exit 0, nothing on stderr, no file written.

    source startup, resume, fork        -> the name
    no stdin, bad JSON, no "source"     -> the name (a startup, the same way
                                           agent-start.sh reads it)
    source clear, compact, or any other -> nothing: the name stays as it is
    project with no agent.conf          -> nothing (the plugin is not on there)

Role: one copy of the logic, role_read in bin/agent-roots.sh, used by
agent-start.sh, agent-close-case.sh and agent-name.sh, so the name and the
role the start hook prints can never disagree.

    AGENT_ROLE=task-manager                  "<feature> Task Manager"
    AGENT_ROLE=<other>, e.g. merge-deputy    "<feature> Merge Deputy"
    no lock, or lock pid == this session     "<repo> Manager"
    lock pid dead                            "<repo> Manager" (takes over)
    lock pid alive, not this session         "<repo> Helper" (human-direct)

    repo    = folder name of the project's main worktree (PROJECT_ROOT)
    feature = folder name of the git toplevel of the stdin cwd (STATE_DIR);
              a task manager's worktree folder is its task name
    this session = $CLAUDE_PID, else the first claude ancestor (agent_pid)

Orca: $ORCA_TERMINAL_HANDLE not empty and orca on PATH -> also, once, only
when a name is printed:

    orca terminal rename --terminal <handle> --title <name> --json

A slow (over 2 s), failing or missing orca never changes stdout, stderr or the
exit code, and the hook still ends inside 5 s.

The start and close-case hooks name the main manager the same way: a spawned
task manager and a human-direct session are told to SendMessage
"<repo> Manager", and a human-direct session how to pick one of two sessions
with the same name (the [ref] ListAgents prints).
"""

import json
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase

NAME_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-name.sh'
NAME_ENTRY = {"hooks": [{"type": "command", "command": NAME_COMMAND, "timeout": 5}]}
NOBODY = "999999"   # a CLAUDE_PID no lock ever names
HANDLE = "term_test-1234"


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as fh:
        return fh.read()


def dead_pid():
    """A pid that surely belongs to nobody now: a reaped child's."""
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


class NameCase(ScriptCase):
    script = "agent-name.sh"

    def payload(self, source="startup", cwd=None):
        data = {
            "session_id": "s-name",
            "transcript_path": "/tmp/none.jsonl",
            "cwd": cwd or self.repo.cwd,
            "hook_event_name": "SessionStart",
        }
        if source is not None:
            data["source"] = source
        return json.dumps(data)

    def set_lock(self, pid):
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%s 2026-09-30 10:00\n" % pid)

    def worktree(self, name="session-names"):
        """A real git worktree of the project, folder `name`."""
        path = os.path.join(self.repo.base, name)
        branch = "wt-%d" % len(os.listdir(self.repo.base))
        subprocess.run(["git", "-C", self.repo.dir, "worktree", "add", "-q",
                        "-b", branch, path], check=True, capture_output=True)
        return os.path.realpath(path)

    def run_hook(self, source="startup", env=None, stdin=None, cwd=None,
                 payload_cwd=None, timeout=90):
        base = {"CLAUDE_PID": NOBODY}
        base.update(env or {})
        if stdin is None:
            stdin = self.payload(source, payload_cwd or cwd)
        return self.repo.run("agent-name.sh", env=base, stdin=stdin, cwd=cwd,
                             timeout=timeout)

    def hook(self, source="startup", **kw):
        """Run the hook: exit 0 and an empty stderr, always. Returns stdout."""
        result = self.run_hook(source, **kw)
        self.assertOk(result)
        self.assertEqual(result.stderr, "", result.stderr)
        return result.stdout

    def title(self, out):
        """The one JSON line, checked for its exact shape. Returns the name."""
        self.assertTrue(out.strip(), "the hook printed nothing")
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        data = json.loads(out)
        self.assertEqual(sorted(data), ["hookSpecificOutput"], data)
        inner = data["hookSpecificOutput"]
        self.assertEqual(sorted(inner), ["hookEventName", "sessionTitle"], inner)
        self.assertEqual(inner["hookEventName"], "SessionStart")
        return inner["sessionTitle"]

    def name(self, source="startup", **kw):
        return self.title(self.hook(source, **kw))


class TestRoles(NameCase):
    """The name follows the role, the same way agent-start.sh decides it."""

    def test_main_manager_with_no_lock(self):
        self.assertEqual(self.name(), "project Manager")

    def test_main_manager_whose_own_lock_it_is(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.name(env={"CLAUDE_PID": str(os.getpid())}),
                         "project Manager")

    def test_dead_lock_is_taken_over_by_a_manager(self):
        self.set_lock(dead_pid())
        self.assertEqual(self.name(), "project Manager")

    def test_second_session_by_hand_is_a_helper(self):
        self.set_lock(os.getpid())          # alive, and not this session
        self.assertEqual(self.name(), "project Helper")

    def test_task_manager_is_named_after_its_worktree(self):
        wt = self.worktree("session-names")
        self.set_lock(os.getpid())
        self.assertEqual(self.name(env={"AGENT_ROLE": "task-manager"}, cwd=wt),
                         "session-names Task Manager")

    def test_the_stdin_cwd_picks_the_worktree(self):
        wt = self.worktree("login-page")
        out = self.name(env={"AGENT_ROLE": "task-manager"}, cwd=self.repo.dir,
                        payload_cwd=wt)
        self.assertEqual(out, "login-page Task Manager")

    def test_agent_role_wins_over_a_live_lock(self):
        self.set_lock(os.getpid())
        self.assertEqual(self.name(env={"AGENT_ROLE": "task-manager"}),
                         "project Task Manager")

    def test_other_agent_role_words_are_capitalised(self):
        wt = self.worktree("session-names")
        self.assertEqual(self.name(env={"AGENT_ROLE": "merge-deputy"}, cwd=wt),
                         "session-names Merge Deputy")

    def test_manager_started_inside_a_worktree_keeps_the_repo_name(self):
        wt = self.worktree("session-names")
        self.assertEqual(self.name(cwd=wt), "project Manager")

    def test_odd_folder_names_stay_valid_json(self):
        odd = 'odd "wt" \\ x'
        wt = self.worktree(odd)
        self.assertEqual(self.name(env={"AGENT_ROLE": "task-manager"}, cwd=wt),
                         odd + " Task Manager")


class TestSources(NameCase):
    """Name on a new, resumed or forked session; never on clear or compact."""

    def test_startup_resume_and_fork_get_the_name(self):
        for source in ("startup", "resume", "fork"):
            with self.subTest(source=source):
                self.assertEqual(self.name(source), "project Manager")

    def test_clear_and_compact_print_nothing(self):
        for source in ("clear", "compact"):
            with self.subTest(source=source):
                self.assertEqual(self.hook(source), "")

    def test_an_unknown_source_prints_nothing(self):
        self.assertEqual(self.hook("something-new"), "")

    def test_no_source_field_counts_as_startup(self):
        self.assertEqual(self.name(None), "project Manager")

    def test_no_stdin_counts_as_startup(self):
        self.assertEqual(self.name(stdin=""), "project Manager")

    def test_bad_json_counts_as_startup(self):
        self.assertEqual(self.name(stdin="not json {"), "project Manager")


class TestQuietAndHarmless(NameCase):

    def test_no_agent_conf_prints_nothing(self):
        os.remove(self.repo.path("agent.conf"))
        self.assertEqual(self.hook(env={"ORCA_TERMINAL_HANDLE": HANDLE}), "")
        self.assertEqual(self.repo.calls(), [])

    def test_writes_no_file(self):
        def tree():
            found = set()
            for dirpath, _dirs, files in os.walk(self.repo.base):
                for name in files:
                    found.add(os.path.join(dirpath, name))
            found.discard(self.repo.orca_log)
            return found
        before = tree()
        self.hook()
        self.set_lock(os.getpid())
        before.add(self.repo.path(".git", "agent_main.lock"))
        self.hook(env={"AGENT_ROLE": "task-manager"})
        self.assertEqual(tree(), before)

    def test_never_writes_the_main_manager_lock(self):
        self.hook()
        self.assertFalse(os.path.exists(self.repo.path(".git", "agent_main.lock")))


class TestOrcaTab(NameCase):
    """Inside Orca the tab gets the same name."""

    RENAME = ["terminal", "rename", "--terminal", HANDLE, "--title"]

    def test_renames_the_tab_when_orca_and_a_handle_are_there(self):
        self.assertEqual(self.name(env={"ORCA_TERMINAL_HANDLE": HANDLE}),
                         "project Manager")
        self.assertEqual(self.repo.calls(),
                         [self.RENAME + ["project Manager", "--json"]])

    def test_task_manager_tab(self):
        wt = self.worktree("session-names")
        self.name(env={"ORCA_TERMINAL_HANDLE": HANDLE, "AGENT_ROLE": "task-manager"},
                  cwd=wt)
        self.assertEqual(self.repo.calls(),
                         [self.RENAME + ["session-names Task Manager", "--json"]])

    def test_no_handle_no_call(self):
        self.name()
        self.name(env={"ORCA_TERMINAL_HANDLE": ""})
        self.assertEqual(self.repo.calls(), [])

    def test_no_rename_on_clear_or_compact(self):
        for source in ("clear", "compact"):
            self.hook(source, env={"ORCA_TERMINAL_HANDLE": HANDLE})
        self.assertEqual(self.repo.calls(), [])

    def test_no_orca_on_path_still_names_the_session(self):
        self.repo.no_orca()
        self.assertEqual(self.name(env={"ORCA_TERMINAL_HANDLE": HANDLE}),
                         "project Manager")

    def test_a_failing_orca_changes_nothing(self):
        self.repo.stub_orca_down()
        self.assertEqual(self.name(env={"ORCA_TERMINAL_HANDLE": HANDLE}),
                         "project Manager")
        self.assertEqual(len(self.repo.calls()), 1)

    def test_a_slow_orca_is_cut_off(self):
        start = time.time()
        out = self.name(env={"ORCA_TERMINAL_HANDLE": HANDLE, "ORCA_STUB_SLEEP": "20"},
                        timeout=30)
        self.assertLess(time.time() - start, 5)
        self.assertEqual(out, "project Manager")


class TestHooksJson(unittest.TestCase):

    def test_session_start_runs_both_hooks(self):
        entries = json.loads(read("hooks", "hooks.json"))["hooks"]["SessionStart"]
        self.assertEqual(len(entries), 2, entries)
        self.assertIn("/bin/agent-start.sh", json.dumps(entries[0]))
        self.assertEqual(entries[1], NAME_ENTRY)

    def test_the_script_can_run(self):
        path = os.path.join(ROOT, "bin", "agent-name.sh")
        self.assertTrue(os.access(path, os.X_OK), "bin/agent-name.sh has no execute bit")

    def test_readme_names_the_script(self):
        self.assertIn("bin/agent-name.sh", read("README.md"))


class TestRoleLogicOnce(unittest.TestCase):
    """One copy of the role logic: role_read in agent-roots.sh."""

    def test_roots_defines_role_read(self):
        self.assertRegex(read("bin", "agent-roots.sh"), r"(?m)^role_read\(\)")

    def test_every_hook_uses_it(self):
        for name in ("agent-start.sh", "agent-close-case.sh", "agent-name.sh"):
            with self.subTest(script=name):
                self.assertIn("role_read", read("bin", name))

    def test_no_second_copy_of_the_lock_check(self):
        for name in ("agent-start.sh", "agent-close-case.sh", "agent-name.sh"):
            with self.subTest(script=name):
                self.assertNotIn('kill -0 "$lpid"', read("bin", name))
        self.assertNotIn("agent_main.lock", read("bin", "agent-name.sh"))


class TestStartNamesTheManager(ScriptCase):
    """agent-start.sh tells a spawned or human-direct session the address."""

    script = "agent-start.sh"

    def set_lock(self, pid):
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%s 2026-09-30 10:00\n" % pid)

    def start(self, env):
        env = dict({"CLAUDE_PID": NOBODY}, **env)
        result = self.repo.run("agent-start.sh", env=env)
        self.assertOk(result)
        return result.stdout

    def test_spawned_task_manager_reports_to_repo_manager(self):
        self.set_lock(os.getpid())
        out = self.start({"AGENT_ROLE": "task-manager"})
        self.assertIn('"project Manager"', out.splitlines()[0])

    def test_human_direct_session_finds_repo_manager(self):
        self.set_lock(os.getpid())
        out = self.start({})
        self.assertIn("ROLE: task manager, human-direct", out)
        self.assertIn('"project Manager"', out)
        self.assertIn("[ref]", out)


class TestCloseCaseNamesTheManager(ScriptCase):
    """The close-case report goes to "<repo> Manager"."""

    script = "agent-close-case.sh"

    def close_case(self, env):
        with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
            fh.write("%s 2026-09-30 10:00\n" % os.getpid())
        stdin = json.dumps({"session_id": "s", "transcript_path": "/tmp/n.jsonl",
                            "cwd": self.repo.cwd, "permission_mode": "auto",
                            "hook_event_name": "UserPromptSubmit",
                            "prompt": "close case"})
        result = self.repo.run("agent-close-case.sh", env=dict({"CLAUDE_PID": NOBODY}, **env),
                               stdin=stdin)
        self.assertOk(result)
        return result.stdout

    def test_task_manager(self):
        self.assertIn('"project Manager"', self.close_case({"AGENT_ROLE": "task-manager"}))

    def test_human_direct(self):
        self.assertIn('"project Manager"', self.close_case({}))


if __name__ == "__main__":
    unittest.main()
