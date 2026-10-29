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
terminal title, and the stored name (custom-title in the transcript).

Live check on pc2, Claude Code 2.1.285, 2026-09-30: the stored name becomes
the ListAgents / SendMessage address only from the NEXT start (a resume). A
fresh `claude` keeps the address "<folder>-<xx>" (folder name plus two hex
characters) for its whole run; SendMessage to the hook's name fails. The
address is right at once only with `claude --name <name>` at launch (the
dispatch skill does this for task managers) or a typed `/rename <name>`.

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
"<repo> Manager", or, when ListAgents has no row by that name, the
"<repo>-<xx>" row (a main manager started by hand, not yet renamed); a
human-direct session also how to pick one of two sessions with the same name
(the [ref] ListAgents prints). The main manager and the human-direct session
are told how to make their own address match: `claude --name`, or ask the
human once for `/rename <repo> Manager` (or `/rename <repo> Helper`).

HELPER TASK. Owner, 2026-10-28: "v4 Manager" stays; a Helper shows its
current task so /resume tells sessions apart. The agent names the task
itself. Owner change, 2026-10-29: " - " between, "<repo> Helper - <Task Name>"
(e.g. "v4 Helper - SST Invoice"); the repo part is the folder name as it is
(no case change).

    bin/agent-file.sh helper-task "<Task Name>"

sets the task of THIS session only. Keyed by the session id: the Bash tool
gets $CLAUDE_CODE_SESSION_ID, every hook gets the same id as stdin
"session_id" (Claude Code 2.1.312 keeps that env var current after /clear).
Two Helpers in one folder have two ids, so they never share a name; a
`claude --resume` keeps the id (the pid changes), so the resumed Helper keeps
its task. A fork is a new id: it starts with no task. Stored in the project's
shared git dir, never in a work tree. No $CLAUDE_CODE_SESSION_ID, or a session
that is not a Helper (role second): refused, exit 1, one line on stderr,
nothing written. It also sets field 3 of this folder's human-direct line in
agent_worktree.txt to "task: <Task Name>" (adds the line when there is none).

The task is cleaned: every character that is not an ASCII letter, digit or
hyphen is a space; hyphens at the ends of a word go; role words go, any
letter case (E2E 2026-10-29: the agent picked "SST Invoice Helper", title
"v4 Helper SST Invoice Helper"): the pair "Task Manager", then every
"Helper", "Manager", "Agent" ("Task" alone stays); then the first 4 words are
kept; each word gets a capital first letter, the rest as typed; then whole
words are dropped from the end while it is over 40 characters (one word alone
is cut to 40). Nothing left: refused.

Rule text (start text TASK line, PRINCIPLES W10): every new or switched
task, a plain question too, gets its name first, even before the quiz PASS
(E2E 2026-10-29: asked only to compute SST, the Helper answered and skipped
the quiz and the command, "no repo was touched"); name the work, not the
role; run the exact full-path command the start text prints, alone, from the
project folder, never cd, never chain it. The command finds the project from
its working folder. It never checks the quiz: it works before PASS.

    role second, task set     "<repo> Helper - <Task Name>"
    role second, no task      "<repo> Helper"
    any other role            as above, a task never changes it

UserPromptSubmit: `agent-name.sh --prompt` (hooks.json, timeout 5). Prints
exactly one JSON line

    {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                            "sessionTitle": "<repo> Helper - <Task Name>"}}

only for a Helper with a task, and only when that name differs from the last
one this hook printed for this session id; otherwise nothing, so a human
/rename is never overridden for no reason. The title changes at the human's
next prompt after the command. Orca tab rename only when it prints, with the
same 2 s cut. Runs on every prompt in every repo: no network, fast (target
under 300 ms), always exit 0, nothing on stderr; it writes only its own
last-title marker in the shared git dir. SessionStart (startup, resume, fork)
uses the task the same way.
"""

import json
import os
import re
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
PROMPT_COMMAND = '"${CLAUDE_PLUGIN_ROOT}"/bin/agent-name.sh --prompt'
PROMPT_ENTRY = {"hooks": [{"type": "command", "command": PROMPT_COMMAND, "timeout": 5}]}
SID_A = "11111111-aaaa-4aaa-8aaa-000000000001"
SID_B = "22222222-bbbb-4bbb-8bbb-000000000002"
SID_C = "33333333-cccc-4ccc-8ccc-000000000003"


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
        # cloud-city-1 (owner, 2026-10-01): a third entry starts the local city by itself
        # (tests/test_agent_city_cloud_autostart.py); the first two stay as they were.
        entries = json.loads(read("hooks", "hooks.json"))["hooks"]["SessionStart"]
        self.assertEqual(len(entries), 3, entries)
        self.assertIn("/bin/agent-start.sh", json.dumps(entries[0]))
        self.assertEqual(entries[1], NAME_ENTRY)
        self.assertIn("agent-city.sh autostart", json.dumps(entries[2]))

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
        self.assertIn('"project-<xx>"', out.splitlines()[0])

    def test_human_direct_session_finds_repo_manager(self):
        self.set_lock(os.getpid())
        out = self.start({})
        self.assertIn("ROLE: task manager, human-direct", out)
        self.assertIn('"project Manager"', out)
        self.assertIn('"project-<xx>"', out)
        self.assertIn("[ref]", out)

    def test_human_direct_session_learns_to_fix_its_own_address(self):
        self.set_lock(os.getpid())
        self.assertIn("/rename project Helper", self.start({}))

    def test_main_manager_learns_to_fix_its_own_address(self):
        out = self.start({})
        self.assertIn("ROLE: main manager", out)
        self.assertIn("/rename project Manager", out)
        self.assertIn("claude --name", out)


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
        out = self.close_case({"AGENT_ROLE": "task-manager"})
        self.assertIn('"project Manager"', out)
        self.assertIn('"project-<xx>"', out)

    def test_human_direct(self):
        out = self.close_case({})
        self.assertIn('"project Manager"', out)
        self.assertIn('"project-<xx>"', out)


# ---------------------------------------------------------------------------
# Helper task (owner, 2026-10-28): "<repo> Helper - <Task Name>"
# ---------------------------------------------------------------------------

class HelperCase(NameCase):
    """A second session: the lock is held by this live test process, and the
    session (CLAUDE_PID=NOBODY) is not it."""

    def setUp(self):
        super().setUp()
        self.set_lock(os.getpid())

    def helper_task(self, text, sid=SID_A, env=None, cwd=None):
        base = {"CLAUDE_PID": NOBODY}
        if sid is not None:
            base["CLAUDE_CODE_SESSION_ID"] = sid
        base.update(env or {})
        return self.repo.run("agent-file.sh", "helper-task", text, env=base, cwd=cwd)

    def set_task(self, text, sid=SID_A, **kw):
        result = self.helper_task(text, sid, **kw)
        self.assertOk(result)
        return result.stdout

    def refused(self, text, sid=SID_A, **kw):
        """The command says no: exit 1, a reason on stderr, not one file changed."""
        before = self.snapshot()
        result = self.helper_task(text, sid, **kw)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(result.stderr.strip(), "a refusal says why on stderr")
        self.assertEqual(self.snapshot(), before)
        return result

    def snapshot(self):
        found = {}
        for dirpath, _dirs, files in os.walk(self.repo.base):
            for name in files:
                full = os.path.join(dirpath, name)
                if full == self.repo.orca_log:
                    continue
                with open(full, "rb") as fh:
                    found[full] = fh.read()
        return found

    def start_name(self, sid=SID_A, source="startup", env=None):
        data = json.loads(self.payload(source))
        data["session_id"] = sid
        return self.name(source, stdin=json.dumps(data), env=env)

    def prompt_payload(self, sid=SID_A, prompt="go on"):
        return json.dumps({"session_id": sid, "transcript_path": "/tmp/none.jsonl",
                           "cwd": self.repo.cwd, "permission_mode": "auto",
                           "hook_event_name": "UserPromptSubmit", "prompt": prompt})

    def run_prompt(self, sid=SID_A, env=None, stdin=None, prompt="go on", timeout=90):
        base = {"CLAUDE_PID": NOBODY}
        base.update(env or {})
        if stdin is None:
            stdin = self.prompt_payload(sid, prompt)
        return self.repo.run("agent-name.sh", "--prompt", env=base, stdin=stdin,
                             timeout=timeout)

    def prompt(self, sid=SID_A, **kw):
        """The prompt hook: exit 0 and an empty stderr, always. Returns stdout."""
        result = self.run_prompt(sid, **kw)
        self.assertOk(result)
        self.assertEqual(result.stderr, "", result.stderr)
        return result.stdout

    def prompt_title(self, out):
        """The one UserPromptSubmit JSON line, exact shape. Returns the name."""
        self.assertTrue(out.strip(), "the prompt hook printed nothing")
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        data = json.loads(out)
        self.assertEqual(sorted(data), ["hookSpecificOutput"], data)
        inner = data["hookSpecificOutput"]
        self.assertEqual(sorted(inner), ["hookEventName", "sessionTitle"], inner)
        self.assertEqual(inner["hookEventName"], "UserPromptSubmit")
        return inner["sessionTitle"]

    def untracked(self):
        out = subprocess.run(["git", "-C", self.repo.dir, "status", "--porcelain",
                              "--untracked-files=all"], capture_output=True,
                             text=True, check=True).stdout
        return [l for l in out.splitlines() if l.startswith("??")]


class TestHelperTaskCommand(HelperCase):

    def test_sets_the_name_of_this_session(self):
        self.set_task("SST Calculation")
        self.assertEqual(self.start_name(), "project Helper - SST Calculation")

    def test_works_before_the_quiz_pass(self):
        gitdir = self.repo.path(".git")
        self.assertEqual([f for f in os.listdir(gitdir) if f.startswith("agent_quiz_")], [])
        self.set_task("SST Invoice")
        self.assertEqual(self.start_name(), "project Helper - SST Invoice")

    def test_says_the_name_and_when_it_shows(self):
        out = self.set_task("SST Calculation")
        self.assertIn("project Helper - SST Calculation", out)
        self.assertIn("next prompt", out)

    def test_a_new_task_replaces_the_old_one(self):
        self.set_task("SST Calculation")
        self.set_task("Login Page")
        self.assertEqual(self.start_name(), "project Helper - Login Page")

    def test_two_helpers_in_one_folder_keep_their_own_names(self):
        self.set_task("Alpha Report", SID_A)
        self.set_task("Beta Fix", SID_B)
        self.assertEqual(self.start_name(SID_A), "project Helper - Alpha Report")
        self.assertEqual(self.start_name(SID_B), "project Helper - Beta Fix")
        self.assertEqual(self.start_name(SID_C), "project Helper")

    def test_a_resumed_helper_keeps_its_task(self):
        self.set_task("SST Calculation")
        self.assertEqual(self.start_name(source="resume", env={"CLAUDE_PID": "888888"}),
                         "project Helper - SST Calculation")

    def test_a_fork_is_a_new_session_with_no_task(self):
        self.set_task("SST Calculation")
        self.assertEqual(self.start_name(SID_C, source="fork"), "project Helper")

    def test_clear_and_compact_still_print_nothing(self):
        self.set_task("SST Calculation")
        for source in ("clear", "compact"):
            with self.subTest(source=source):
                data = json.loads(self.payload(source))
                data["session_id"] = SID_A
                self.assertEqual(self.hook(source, stdin=json.dumps(data)), "")

    def test_the_name_is_cleaned(self):
        cases = [
            ("SST Calculation", "SST Calculation"),
            ("sst calculation", "Sst Calculation"),
            ('fix "login"\npage', "Fix Login Page"),
            ("one two three four five six", "One Two Three Four"),
            ("Internationalization Localization Accessibility Work",
             "Internationalization Localization"),
            ("a" * 60, "A" + "a" * 39),
            ("--rm -rf", "Rm Rf"),
            ("登录 page fix", "Page Fix"),
            ('back\\slash {json} it', "Back Slash Json It"),
            ("  log-in\tpage  ", "Log-in Page"),
            ("SST Invoice Helper", "SST Invoice"),
            ("helper for sst invoices", "For Sst Invoices"),
            ("Task Manager Login Page", "Login Page"),
            ("task queue fix", "Task Queue Fix"),
            ("Agent City Fix", "City Fix"),
            ("Manager Report", "Report"),
            ("HELPER sst AGENT", "Sst"),
            ("SST Invoice Helper Fix Now", "SST Invoice Fix Now"),
        ]
        for i, (raw, want) in enumerate(cases):
            sid = "44444444-dddd-4ddd-8ddd-%012d" % i
            with self.subTest(raw=raw):
                self.set_task(raw, sid)
                got = self.start_name(sid)
                self.assertEqual(got, "project Helper - " + want)
                self.assertLessEqual(len(got) - len("project Helper - "), 40)

    def test_no_english_words_is_refused(self):
        for raw in ("登录页面", "   ", '""', "--", "", "Helper", "Task Manager",
                    "helper agent manager"):
            with self.subTest(raw=raw):
                self.refused(raw)
        self.assertEqual(self.start_name(), "project Helper")

    def test_no_session_id_is_refused(self):
        self.refused("SST Calculation", sid=None)

    def test_the_main_manager_is_refused(self):
        os.remove(self.repo.path(".git", "agent_main.lock"))
        self.refused("SST Calculation")
        self.assertEqual(self.start_name(), "project Manager")

    def test_the_lock_owner_is_refused(self):
        self.refused("SST Calculation", env={"CLAUDE_PID": str(os.getpid())})

    def test_a_spawned_agent_is_refused(self):
        self.refused("SST Calculation", env={"AGENT_ROLE": "task-manager"})

    def test_a_task_never_renames_another_role(self):
        self.set_task("SST Calculation")
        self.assertEqual(self.start_name(env={"AGENT_ROLE": "task-manager"}),
                         "project Task Manager")
        self.assertEqual(self.start_name(env={"CLAUDE_PID": str(os.getpid())}),
                         "project Manager")
        self.set_lock(dead_pid())
        self.assertEqual(self.start_name(), "project Manager")

    def test_stored_outside_the_work_tree(self):
        self.set_task("SST Calculation")
        self.assertEqual(self.untracked(), [])

    def test_usage_names_the_command(self):
        result = self.repo.run("agent-file.sh")
        self.assertIn("helper-task", result.stdout)


class TestHelperTaskWorktreeLine(HelperCase):
    """The task field of this folder's human-direct line in agent_worktree.txt."""

    OTHER = "/somewhere/else | other-module | working | since 2026-10-28 08:00"

    def seed(self):
        line = "%s | task manager, human-direct | task: (ask the human) | since 2026-10-28 09:00" \
            % self.repo.dir
        with open(self.repo.path("agent_worktree.txt"), "w") as fh:
            fh.write(self.OTHER + "\n" + line + "\n")

    def rows(self):
        return [l for l in self.repo.read("agent_worktree.txt").splitlines() if l.strip()]

    def test_fills_the_task_field(self):
        self.seed()
        self.set_task("SST Calculation")
        self.assertEqual(sorted(self.rows()), sorted([
            self.OTHER,
            "%s | task manager, human-direct | task: SST Calculation | since 2026-10-28 09:00"
            % self.repo.dir]))

    def test_a_new_task_replaces_the_field_in_the_same_line(self):
        self.seed()
        self.set_task("SST Calculation")
        self.set_task("Login Page")
        mine = [r for r in self.rows() if r.startswith(self.repo.dir + " | ")]
        self.assertEqual(mine, [
            "%s | task manager, human-direct | task: Login Page | since 2026-10-28 09:00"
            % self.repo.dir])

    def test_no_line_yet_adds_one(self):
        self.set_task("SST Calculation")
        mine = [r for r in self.rows() if r.startswith(self.repo.dir + " | ")]
        self.assertEqual(len(mine), 1, self.rows())
        self.assertRegex(mine[0], r"^%s \| task manager, human-direct \| task: SST Calculation"
                         r" \| since \d{4}-\d\d-\d\d \d\d:\d\d$" % re.escape(self.repo.dir))


class TestPromptHook(HelperCase):
    """UserPromptSubmit: the title, once per change, only for a Helper with a task."""

    RENAME = ["terminal", "rename", "--terminal", HANDLE, "--title"]

    def test_no_task_prints_nothing(self):
        self.assertEqual(self.prompt(), "")

    def test_the_title_comes_once_after_the_task_is_set(self):
        self.set_task("SST Calculation")
        self.assertEqual(self.prompt_title(self.prompt()), "project Helper - SST Calculation")
        for _ in range(3):
            self.assertEqual(self.prompt(), "")   # a human /rename is kept

    def test_a_new_task_comes_once_more(self):
        self.set_task("SST Calculation")
        self.prompt()
        self.set_task("Login Page")
        self.assertEqual(self.prompt_title(self.prompt()), "project Helper - Login Page")
        self.assertEqual(self.prompt(), "")

    def test_each_session_gets_its_own_title(self):
        self.set_task("Alpha Report", SID_A)
        self.set_task("Beta Fix", SID_B)
        self.assertEqual(self.prompt_title(self.prompt(SID_A)), "project Helper - Alpha Report")
        self.assertEqual(self.prompt_title(self.prompt(SID_B)), "project Helper - Beta Fix")
        self.assertEqual(self.prompt(SID_A), "")
        self.assertEqual(self.prompt(SID_C), "")

    def test_other_roles_print_nothing(self):
        self.set_task("SST Calculation")
        self.assertEqual(self.prompt(env={"AGENT_ROLE": "task-manager"}), "")
        self.assertEqual(self.prompt(env={"CLAUDE_PID": str(os.getpid())}), "")
        self.set_lock(dead_pid())
        self.assertEqual(self.prompt(), "")
        os.remove(self.repo.path(".git", "agent_main.lock"))
        self.assertEqual(self.prompt(), "")

    def test_no_agent_conf_prints_nothing(self):
        self.set_task("SST Calculation")
        os.remove(self.repo.path("agent.conf"))
        self.assertEqual(self.prompt(env={"ORCA_TERMINAL_HANDLE": HANDLE}), "")
        self.assertEqual(self.repo.calls(), [])

    def test_bad_or_empty_stdin_prints_nothing(self):
        self.set_task("SST Calculation")
        for stdin in ("", "not json {"):
            with self.subTest(stdin=stdin):
                self.assertEqual(self.prompt(stdin=stdin), "")

    def test_the_prompt_text_cannot_pick_the_session(self):
        self.set_task("Beta Fix", SID_B)
        text = 'see {"session_id": "%s"} and "quotes"\nand \\ too' % SID_B
        self.assertEqual(self.prompt(SID_A, prompt=text), "")
        self.assertEqual(self.prompt_title(self.prompt(SID_B, prompt=text)),
                         "project Helper - Beta Fix")

    def test_a_resume_does_not_repeat_the_title(self):
        self.set_task("SST Calculation")
        self.prompt_title(self.prompt())
        self.start_name(source="resume", env={"CLAUDE_PID": "888888"})
        self.assertEqual(self.prompt(env={"CLAUDE_PID": "888888"}), "")

    def test_it_is_fast(self):
        # target under 300 ms; the bound is loose for a busy test machine
        self.set_task("SST Calculation")
        for _ in range(2):
            start = time.monotonic()
            self.prompt()
            self.assertLess(time.monotonic() - start, 1.0)

    def test_writes_nothing_in_the_work_tree(self):
        self.set_task("SST Calculation")
        self.prompt()
        self.prompt()
        self.assertEqual(self.untracked(), [])

    def test_the_tab_is_renamed_only_when_the_title_changes(self):
        env = {"ORCA_TERMINAL_HANDLE": HANDLE}
        self.set_task("SST Calculation")
        self.prompt(env=env)
        self.prompt(env=env)
        self.set_task("Login Page")
        self.prompt(env=env)
        self.assertEqual(self.repo.calls(), [
            self.RENAME + ["project Helper - SST Calculation", "--json"],
            self.RENAME + ["project Helper - Login Page", "--json"]])

    def test_no_title_no_tab_rename(self):
        self.prompt(env={"ORCA_TERMINAL_HANDLE": HANDLE})
        self.assertEqual(self.repo.calls(), [])

    def test_a_slow_orca_is_cut_off(self):
        self.set_task("SST Calculation")
        start = time.time()
        out = self.prompt(env={"ORCA_TERMINAL_HANDLE": HANDLE, "ORCA_STUB_SLEEP": "20"},
                          timeout=30)
        self.assertLess(time.time() - start, 5)
        self.assertEqual(self.prompt_title(out), "project Helper - SST Calculation")


class TestPromptHookJson(unittest.TestCase):

    def test_user_prompt_submit_runs_the_prompt_hook_once(self):
        entries = json.loads(read("hooks", "hooks.json"))["hooks"]["UserPromptSubmit"]
        self.assertEqual(entries.count(PROMPT_ENTRY), 1, entries)
        self.assertIn("agent-close-case.sh", json.dumps(entries))

    def test_no_other_event_runs_the_prompt_mode(self):
        for event, entries in json.loads(read("hooks", "hooks.json"))["hooks"].items():
            if event != "UserPromptSubmit":
                with self.subTest(event=event):
                    self.assertNotIn("--prompt", json.dumps(entries))

    def test_readme_says_it_names_the_helper_task(self):
        line = next(l for l in read("README.md").splitlines() if "bin/agent-name.sh" in l)
        self.assertIn("UserPromptSubmit", line)
        self.assertIn("<repo> Helper - <Task Name>", line)


class TestStartTellsTheHelper(ScriptCase):
    """The human-direct start text says when and how to name the task."""

    script = "agent-start.sh"

    def start(self, env, lock=True):
        if lock:
            with open(self.repo.path(".git", "agent_main.lock"), "w") as fh:
                fh.write("%s 2026-10-28 10:00\n" % os.getpid())
        result = self.repo.run("agent-start.sh", env=dict({"CLAUDE_PID": NOBODY}, **env))
        self.assertOk(result)
        return result.stdout

    def test_the_helper_is_told_the_command(self):
        out = self.start({})
        lines = [l for l in out.splitlines() if "helper-task" in l]
        self.assertEqual(len(lines), 1, out)
        line = lines[0]
        self.assertIn(self.repo.plugin + '/bin/agent-file.sh helper-task "<Task Name>"', line)
        for word in ("2-4 English words", "Title Case", "next prompt",
                     '"project Helper - <Task Name>"', "the work, not the role",
                     "every new or switched task", "a plain question too",
                     "before the quiz PASS", "alone", "project folder",
                     "never cd", "never chain"):
            with self.subTest(word=word):
                self.assertIn(word, line)
        self.assertLessEqual(len(line.replace(self.repo.plugin, "<plugin>")), 400)

    def test_other_roles_are_not_told(self):
        self.assertNotIn("helper-task", self.start({}, lock=False))
        self.assertNotIn("helper-task", self.start({"AGENT_ROLE": "task-manager"}))


if __name__ == "__main__":
    unittest.main()
