"""agent-files: local by default, shared by choice, a name on every record (requirements/agent-files.md).

The contract the workers build to. One class per feature; the examples of section 7 are the classes named Ex<n>.

Facts, in the committed agent_repo.conf ("key=value"; "key = value" reads the same). task_files and task_take are
also settings of the person (/plugin Configure: "Task files in git", "Who may take a task"): a repo value wins, no repo
value = the person's Configure, no setting = the default. init writes neither key:
  task_files=local (default) | ideas | ideas,todo      which task files are in git besides the history
  task_take=owner (default) | anyone                    who may work a task of a todo in git
  task_place=data (default) | tree                      where the files in git go: the data branch, or the code tree
                                                        (written by the cloud pack only)

The place is ONE function (bin/agent_share.py place()). The data branch name is a third value with the same rule as
task_files and task_take: agent_repo.conf data_branch= wins, else the Configure setting "Data branch", default
"ap-data" (bin/agent_conf.py SETTINGS). A change of the place or of a default costs one line. A branch that holds code
(the production or the working branch, or a branch with any file that is not an agent file) carries them under
".ap-data/" (tests/test_agent_files_codebranch.py); it needs an origin: without one `files set data_branch` exits 1
and a Configure or repo value that names one leaves the files on the default ap-data, every write says so in one line
("needs an origin").

Where a file lives (section 2), place data:
  Every agent file (agent_todo.txt, agent_ideas.txt, agent_worktree.txt, agent_completed.txt, agent_estimate.txt) is
  git-ignored (an exact line "<file>" in .gitignore) and untracked in the main checkout: no worktree gets a copy.
  In git: agent_completed.txt and agent_estimate.txt always, agent_ideas.txt / agent_todo.txt when task_files names
  them. Local: the others (agent_worktree.txt always).
  In git = whatever script writes the file commits the changed in-git files onto refs/heads/ap-data (git plumbing: a
  tree that holds only agent files, a commit on the local data branch; HEAD and the index of the checkout never move)
  and pushes `origin ap-data` at once. A push refused because the remote moved: fetch, merge (below), push again. Any
  other failure (offline, refused): the work goes on, the commit stays, the next write pushes it, one line says so
  ("ap-data: not pushed (<why>); the next write pushes it"). No remote: commit only, no line.
  Sync = fetch origin ap-data, then a 3-way merge into the working copy (base = the merge base, ours = the working
  copy, theirs = the remote tip), committed (both tips as parents) and pushed:
    agent_completed.txt, agent_ideas.txt   every new line of both sides stays; a line one side removed is removed
    agent_todo.txt                         per task name: removed by either side = dropped (a finished task never
                                           comes back); changed by one side = that change; changed by both = the
                                           side whose tip commit is newer
    agent_estimate.txt                     ours; after a sync that brought new records the model is trained again
  A sync runs before a file in git is read for a decision: files sync, next, todo take, todo assign, todo stage, board,
  the board guard's dispatch check, files move.
  No git identity: a fallback identity is used; nothing asks who you are, git's own words never reach the output.
Place tree (cloud): the task files stay tracked in the tree, nothing extra is ignored, committed with the work.

The name (section 3, TELL c4ec5b42) = `git config user.name` of the clone, trimmed, spaces kept ("King Lun"); git has
none: the login name. ONE function (estimate-improve's agent_conf.user_name once merged; until then this contract).
Stored and shown raw; two names are the same person when their cleaned forms are equal (lower case, every run of
other characters one "-"), so a stored "maverick" matches "Maverick". A field value ends at the next " | ".
  idea add      "<text> | <date> | by <name>"
  park add      "PARKED: ... | by <name>"        (the last field)
  todo line     " | owner <name>" (written by todo add, task estimate-improve), " | assignee <name>", " | taken <name>"
  idea list, board, questions   "[<name>]" beside the record (questions --json: "by")

Commands (bin/agent-file.sh):
  files show                    "files: task_files=<v> task_take=<v> place=<ap-data|tree>", then one line per agent
                                file: "<file>: local" or "<file>: in git"
  files sync                    the sync above, by hand
  files move                    in the main checkout only. (1) The code branch's upstream ahead: keep the agent files'
                                content, pull (merge), put the content back (a file removed upstream keeps it).
                                (2) Every tracked agent file is copied to <git common dir>/agent-files-kept/ and taken
                                out of the code branch (git rm --cached), content kept; the ignore lines are written;
                                one code-branch commit holds the removals and .gitignore. (3) The in-git files go onto
                                ap-data (synced with origin's, created when missing, pushed). (4) Turning the todo into
                                git gives every open todo line with no owner field " | owner <name>".
                                Refused (exit 1, nothing moves): run outside the main checkout ("run it in the main
                                checkout"), a staged change of any other file ("the index has staged changes").
                                One line per file ("<file>: local (...)" / "<file>: in git (...)"; "(already)" when
                                nothing changed for it); last line "files move: done" or "files move: nothing changed".
                                Run twice, the second run changes nothing. It never pushes the code branch.
  files set task_files <local|ideas|ideas,todo>    the fact in agent_repo.conf (one code-branch commit of that file),
                                then files move
  files set task_take <owner|anyone>               the fact in agent_repo.conf (one code-branch commit of that file)
  todo assign <task> <name>     todo in git, the owner only: " | assignee <name>"
  todo take <task>              todo in git, task_take=anyone: sync, refuse when someone took it, " | taken <name>",
                                commit, push; the push refused because the remote moved: sync and check again; the
                                remote holds another taker = refused, the local line becomes the remote's.
                                Success: "todo take: <task> is yours"

Who may work a task (section 4), only when the todo is in git ("work" = a dispatch through the board guard,
todo stage, todo done, the merge gate, and the approval words: todo target, todo checks --remove):
  taken <x>     only x                     else "<task> was taken by <x>"
  assignee <x>  only x                     else "<task> is assigned to <x>"
  owner <x>     task_take=owner: only x    else "<task> belongs to <x>; ask them to assign it"
                task_take=anyone: free     a dispatch or a stage of a free task: "<task> is free: take it first
                                           (agent-file.sh todo take <task>)"
  no owner      no check
  todo assign by another than the owner: "<task> belongs to <owner>; only the owner assigns"
  todo assign with a local todo: refused, the line says the todo is local
  todo take with task_take=owner: "todo take: task_take is owner; ask <owner> to assign it"
A local todo: no check, no name asked. The logic lives in bin/agent_share.py (python3, stdlib only).

The settings (owner 2026-11-26): files move with a Configure value that shares (task_files not local, or task_take
anyone) and no repo value writes that value into agent_repo.conf (one code-branch commit) and says so in one line
naming agent_repo.conf. agent-start.sh prints one line per fact when the person's Configure differs from the repo value:
it names the repo value ("task_files=<v>") and agent_repo.conf.
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripthelp import ROOT, ScriptCase, ScriptRepo  # noqa: E402

AGENT_FILES = ("agent_todo.txt", "agent_ideas.txt", "agent_worktree.txt", "agent_completed.txt",
               "agent_estimate.txt")
LOCAL = ("agent_todo.txt", "agent_ideas.txt", "agent_worktree.txt")
DATA = "ap-data"
NOW = "2026-11-26 10:00"


def git(path, *args, env=None, check=True):
    r = subprocess.run(["git", "-C", path] + list(args), capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise AssertionError("git %s failed in %s:\n%s%s" % (" ".join(args), path, r.stdout, r.stderr))
    return r.stdout


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def head(path):
    return git(path, "rev-parse", "HEAD").strip()


def head_files(path):
    """The paths the HEAD commit changed."""
    return sorted(git(path, "show", "--name-only", "--format=", "HEAD").split())


def tip(path, ref=DATA):
    """The commit of a ref, "" when there is none."""
    return git(path, "rev-parse", "-q", "--verify", ref + "^{commit}", check=False).strip()


def data_file(path, name, ref=DATA):
    """A file as the data branch holds it, None when it is not there."""
    r = subprocess.run(["git", "-C", path, "show", "%s:%s" % (ref, name)], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def tracked(path, name):
    return git(path, "ls-files", "--", name).strip() != ""


def ignored(path, name):
    return subprocess.run(["git", "-C", path, "check-ignore", "-q", "--", name]).returncode == 0


def porcelain(path, name=None):
    args = ["status", "--porcelain", "--untracked-files=all"]
    if name:
        args += ["--", name]
    return git(path, *args)


def todo_line(name, owner=None, extra=""):
    line = "%s | small | the %s task | est 30m | opened 2026-11-26 09:00 | by main" % (name, name)
    if owner:
        line += " | owner %s" % owner
    return line + extra


def no_identity(base):
    home = os.path.join(base, "empty_home")
    os.makedirs(home, exist_ok=True)
    return {"HOME": home, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "XDG_CONFIG_HOME": home}


class FilesCase(ScriptCase):
    """A project made by init in a fresh git repo (only seed.txt tracked before it)."""

    script = "agent-file.sh"
    name = "Maverick"

    def setUp(self):
        self.repo = ScriptRepo(init_project=False)
        self.addCleanup(self.repo.cleanup)
        self.dir = self.repo.dir
        self.repo.git_init(self.dir)
        git(self.dir, "config", "user.name", self.name)
        self.assertOk(self.repo.run("agent-init.sh", "--no-measure", "--no-branch"))

    def af(self, *args, cwd=None, ok=True, env=None):
        e = {"AGENT_FAKE_NOW": NOW}
        e.update(env or {})
        r = self.repo.run("agent-file.sh", *args, cwd=cwd or self.dir, env=e)
        self.assertNotIn("Traceback", r.stderr)
        if ok:
            self.assertOk(r)
        return r

    def conf(self, root=None):
        out = {}
        for line in read(os.path.join(root or self.dir, "agent_repo.conf")).splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
        return out

    def commit_all(self, path=None, msg="setup"):
        path = path or self.dir
        git(path, "add", "-A")
        git(path, "commit", "-q", "-m", msg, "--allow-empty")

    def make_remote(self):
        """A bare origin for this clone; the code branch pushed."""
        self.bare = os.path.join(self.repo.base, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", self.bare], check=True, capture_output=True)
        git(self.dir, "remote", "add", "origin", self.bare)
        self.branch = git(self.dir, "symbolic-ref", "--short", "HEAD").strip()
        git(self.dir, "push", "-q", "-u", "origin", self.branch)

    def refuse_data_pushes(self):
        hook = os.path.join(self.bare, "hooks", "pre-receive")
        write(hook, "#!/bin/sh\nwhile read old new ref; do\n  [ \"$ref\" = refs/heads/%s ] && "
                    "{ echo 'protected branch' >&2; exit 1; }\ndone\nexit 0\n" % DATA)
        os.chmod(hook, 0o755)
        return hook


class OldRepoCase(FilesCase):
    """A repo that tracks every agent file (the state before this task), with real lines in them."""

    def setUp(self):
        super().setUp()
        with open(os.path.join(self.dir, ".gitignore")) as fh:
            keep = [l for l in fh.read().splitlines() if l not in AGENT_FILES]
        write(os.path.join(self.dir, ".gitignore"), "".join(l + "\n" for l in keep))
        write(os.path.join(self.dir, "agent_todo.txt"), todo_line("t0") + "\n")
        write(os.path.join(self.dir, "agent_ideas.txt"), "an old idea | 2026-11-01 10:00 | by main\n")
        write(os.path.join(self.dir, "agent_worktree.txt"), "/tmp/wt | t0 | working | since 2026-11-26 09:00\n")
        write(os.path.join(self.dir, "agent_completed.txt"), "2026-11-01 | old | the old task | est 5m actual 5m\n")
        write(os.path.join(self.dir, "agent_estimate.txt"), '{"version": 1}\n')
        git(self.dir, "add", "-f", "--", *AGENT_FILES)
        self.commit_all(msg="old style: the agent files tracked")
        for name in AGENT_FILES:
            self.assertTrue(tracked(self.dir, name), name)


# ---------------------------------------------------------------- section 2 and 7: setup in a new repo


class Ex1SetupInANewRepo(FilesCase):
    def test_every_agent_file_is_ignored_and_not_listed(self):
        # section 2: in the main checkout every agent file is git-ignored and untracked (the history too: it lives
        # on ap-data; the example line "agent_completed.txt is not ignored" predates the data branch)
        status = porcelain(self.dir)
        for name in AGENT_FILES:
            with self.subTest(name=name):
                self.assertNotIn(name, status)
                self.assertTrue(ignored(self.dir, name), "%s is not ignored" % name)

    def test_init_writes_no_sharing_fact(self):
        # owner 2026-11-26 (TELL 3a14d2f4): the person's Configure is the default; only a repo value overrides it
        conf = self.conf()
        self.assertNotIn("task_files", conf)
        self.assertNotIn("task_take", conf)
        self.assertFalse(ignored(self.dir, "agent_repo.conf"))
        self.assertIn("files: task_files=local task_take=owner", self.af("files", "show").stdout)

    def test_init_twice_changes_nothing(self):
        before = {n: read(os.path.join(self.dir, n)) for n in (".gitignore", "agent_repo.conf")}
        self.assertOk(self.repo.run("agent-init.sh", "--no-measure", "--no-branch"))
        self.assertEqual({n: read(os.path.join(self.dir, n)) for n in before}, before)

    def test_files_show_names_where_each_file_lives(self):
        out = self.af("files", "show").stdout
        self.assertIn("files: task_files=local task_take=owner place=ap-data", out)
        for name in LOCAL:
            self.assertIn("%s: local" % name, out)
        self.assertIn("agent_completed.txt: in git", out)
        self.assertIn("agent_estimate.txt: in git", out)

    def test_a_spaced_fact_reads_the_same(self):
        path = os.path.join(self.dir, "agent_repo.conf")
        write(path, read(path) + "task_files = ideas\n")
        out = self.af("files", "show").stdout
        self.assertIn("task_files=ideas", out)
        self.assertIn("agent_ideas.txt: in git", out)

    def test_the_data_branch_is_one_setting_with_the_default_ap_data(self):
        sys.path.insert(0, self.repo.plugin_bin)
        try:
            import agent_conf
            row = [x for x in agent_conf.SETTINGS if x["key"] == "data_branch"]
            self.assertEqual(len(row), 1)
            self.assertEqual(row[0]["default"], DATA)
            self.assertNotIn("data_branch", agent_conf.CONSTANTS)
        finally:
            sys.path.remove(self.repo.plugin_bin)


class TestTheSettingsAreThePersonsDefault(FilesCase):
    """Owner 2026-11-26 (TELL 3a14d2f4): two settings in Configure are the person's default; the repo value wins."""

    def test_the_settings_table_shows_both(self):
        out = self.assertOk(self.repo.run("agent-settings.sh"))
        self.assertIn("Task files in git", out)
        self.assertIn("Who may take a task", out)
        manifest = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))["userConfig"]
        self.assertEqual(manifest["task_files"]["default"], "local")
        self.assertEqual(manifest["task_take"]["default"], "owner")
        self.assertEqual(manifest["task_files"]["options"], ["local", "ideas", "ideas,todo"])
        self.assertEqual(manifest["task_take"]["options"], ["owner", "anyone"])

    def test_no_repo_value_configure_decides(self):
        self.repo.set_conf("task_files", "ideas")
        self.repo.set_conf("task_take", "anyone")
        out = self.af("files", "show").stdout
        self.assertIn("task_files=ideas", out)
        self.assertIn("task_take=anyone", out)
        self.assertIn("agent_ideas.txt: in git", out)

    def test_the_repo_value_wins_and_the_start_says_so(self):
        self.commit_all()
        self.af("files", "set", "task_files", "local")
        self.repo.set_conf("task_files", "ideas,todo")
        self.assertIn("task_files=local", self.af("files", "show").stdout)
        out = self.repo.run("agent-start.sh").stdout
        said = [l for l in out.splitlines() if "task_files=local" in l and "agent_repo.conf" in l]
        self.assertEqual(len(said), 1, out)

    def test_no_line_at_start_when_they_agree(self):
        self.commit_all()
        self.af("files", "set", "task_take", "owner")
        out = self.repo.run("agent-start.sh").stdout
        self.assertEqual([l for l in out.splitlines() if "task_take=" in l], [], out)

    def test_the_move_writes_a_shared_default_into_the_repo(self):
        self.commit_all()
        self.repo.set_conf("task_files", "ideas,todo")
        out = self.af("files", "move").stdout
        self.assertEqual(self.conf().get("task_files"), "ideas,todo")
        # "the command that turns sharing on writes the three values there" (section 2, Settings)
        self.assertEqual(self.conf().get("task_take"), "owner")
        self.assertEqual(self.conf().get("data_branch"), DATA)
        self.assertIn("task_files=ideas,todo", git(self.dir, "show", "HEAD:agent_repo.conf"))
        said = [l for l in out.splitlines() if "agent_repo.conf" in l and "task_files=ideas,todo" in l]
        self.assertEqual(len(said), 1, out)
        self.assertIsNotNone(data_file(self.dir, "agent_todo.txt"))

    def test_a_repo_data_branch_wins(self):
        self.commit_all()
        path = os.path.join(self.dir, "agent_repo.conf")
        write(path, read(path) + "data_branch=team-data\n")
        self.repo.set_conf("data_branch", "mine-data")
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.af("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.assertIn("| t |", data_file(self.dir, "agent_completed.txt", ref="team-data") or "")
        self.assertEqual(tip(self.dir, "mine-data"), "")
        self.assertEqual(tip(self.dir, DATA), "")

    def test_a_configure_data_branch_is_used_when_the_repo_has_none(self):
        self.repo.set_conf("data_branch", "mine-data")
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.af("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.assertIn("| t |", data_file(self.dir, "agent_completed.txt", ref="mine-data") or "")
        self.assertIn("place=mine-data", self.af("files", "show").stdout)

    def test_a_code_branch_without_an_origin_is_refused_with_one_line(self):
        # TELL 50d02f90: a code branch carries the files under .ap-data/ on top of the remote tip
        # (tests/test_agent_files_codebranch.py); with no origin there is no remote tip: refused, the files stay on
        # the default ap-data and every write says so in one line
        self.commit_all()
        code = git(self.dir, "symbolic-ref", "--short", "HEAD").strip()
        self.repo.set_conf("data_branch", code)
        self.af("todo", "add", "t", "small", "the t task", "30")
        sha = head(self.dir)
        r = self.af("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")
        self.assertEqual(len([l for l in (r.stdout + r.stderr).splitlines() if "needs an origin" in l]), 1,
                         r.stdout + r.stderr)
        self.assertEqual(head(self.dir), sha)
        self.assertNotIn(".ap-data", git(self.dir, "ls-tree", "--name-only", code))
        self.assertIn("| t |", data_file(self.dir, "agent_completed.txt") or "")

    def test_the_settings_table_shows_the_data_branch(self):
        out = self.assertOk(self.repo.run("agent-settings.sh"))
        self.assertIn("Data branch", out)
        manifest = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))["userConfig"]
        self.assertEqual(manifest["data_branch"]["default"], DATA)

    def test_the_move_writes_nothing_for_the_local_default(self):
        self.commit_all()
        self.af("files", "move")
        self.assertNotIn("task_files", self.conf())


# ---------------------------------------------------------------- section 5 and 7: the move command


class Ex2MoveARepoThatTracksTheTodo(OldRepoCase):
    def setUp(self):
        super().setUp()
        with open(os.path.join(self.dir, "agent_todo.txt"), "a") as fh:
            fh.write("".join(todo_line(n) + "\n" for n in ("a", "b", "c")))
        self.before = {n: read(os.path.join(self.dir, n)) for n in AGENT_FILES}
        self.out = self.af("files", "move").stdout

    def test_the_file_keeps_its_lines(self):
        self.assertEqual(read(os.path.join(self.dir, "agent_todo.txt")), self.before["agent_todo.txt"])

    def test_it_is_out_of_git(self):
        self.assertEqual(git(self.dir, "ls-files", "agent_todo.txt").strip(), "")
        self.assertTrue(ignored(self.dir, "agent_todo.txt"))
        self.assertNotIn("agent_todo.txt", porcelain(self.dir))

    def test_a_new_worktree_has_no_agent_file(self):
        wt = os.path.join(self.repo.base, "wt_new")
        git(self.dir, "worktree", "add", "-q", "-b", "new-task", wt)
        for name in AGENT_FILES:
            self.assertFalse(os.path.exists(os.path.join(wt, name)), name)

    def test_a_copy_goes_into_the_git_folder(self):
        gd = git(self.dir, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        copies = glob.glob(os.path.join(gd, "agent-files-kept", "agent_todo.txt*"))
        self.assertTrue(copies, "no copy under %s/agent-files-kept" % gd)
        self.assertIn(self.before["agent_todo.txt"], [read(c) for c in copies])

    def test_every_file_keeps_its_content_and_leaves_the_code_branch(self):
        for name in AGENT_FILES:
            with self.subTest(name=name):
                self.assertFalse(tracked(self.dir, name))
                self.assertEqual(read(os.path.join(self.dir, name)), self.before[name])

    def test_the_history_goes_onto_the_data_branch(self):
        self.assertEqual(data_file(self.dir, "agent_completed.txt"), self.before["agent_completed.txt"])
        self.assertEqual(data_file(self.dir, "agent_estimate.txt"), self.before["agent_estimate.txt"])
        self.assertIsNone(data_file(self.dir, "agent_todo.txt"), "a local todo went onto the data branch")
        self.assertIsNone(data_file(self.dir, "agent_worktree.txt"))

    def test_it_says_what_it_did_per_file(self):
        for name in LOCAL:
            self.assertIn("%s: local" % name, self.out)
        self.assertIn("agent_completed.txt: in git", self.out)
        self.assertIn("files move: done", self.out)

    def test_the_tree_is_clean_after_it(self):
        self.assertEqual(porcelain(self.dir).strip(), "", porcelain(self.dir))
        self.assertEqual(set(head_files(self.dir)) - {".gitignore"}, set(AGENT_FILES))

    def test_a_second_run_changes_nothing(self):
        sha, data = head(self.dir), tip(self.dir)
        gd = git(self.dir, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        copies = sorted(os.listdir(os.path.join(gd, "agent-files-kept")))
        files = {n: read(os.path.join(self.dir, n)) for n in AGENT_FILES + (".gitignore",)}
        out = self.af("files", "move").stdout
        self.assertEqual((head(self.dir), tip(self.dir)), (sha, data))
        self.assertEqual(sorted(os.listdir(os.path.join(gd, "agent-files-kept"))), copies)
        self.assertEqual({n: read(os.path.join(self.dir, n)) for n in files}, files)
        self.assertIn("files move: nothing changed", out)
        for name in LOCAL:
            self.assertIn("%s: local (already)" % name, out)


class TestMoveRefusals(OldRepoCase):
    def test_a_staged_product_file_is_refused_and_nothing_moves(self):
        with open(os.path.join(self.dir, "seed.txt"), "a") as fh:
            fh.write("product change\n")
        git(self.dir, "add", "seed.txt")
        sha = head(self.dir)
        r = self.af("files", "move", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("staged", r.stderr)
        self.assertEqual(head(self.dir), sha)
        self.assertTrue(tracked(self.dir, "agent_todo.txt"))
        self.assertEqual(tip(self.dir), "")

    def test_it_runs_only_in_the_main_checkout(self):
        wt = os.path.join(self.repo.base, "wt_side")
        git(self.dir, "worktree", "add", "-q", "-b", "side", wt)
        r = self.af("files", "move", cwd=wt, ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("main checkout", r.stderr)


class TestTheMoveInTheOtherClone(OldRepoCase):
    """Both clones track the agent files; Maverick moves and pushes; King Lun's move settles the pull."""

    def setUp(self):
        super().setUp()
        self.make_remote()
        self.b = os.path.join(self.repo.base, "kinglun")
        subprocess.run(["git", "clone", "-q", self.bare, self.b], check=True, capture_output=True)
        git(self.b, "config", "user.name", "King Lun")
        git(self.b, "config", "user.email", "kinglun@example.invalid")
        with open(os.path.join(self.b, "agent_todo.txt"), "a") as fh:
            fh.write(todo_line("his-local-task") + "\n")
        self.b_files = {n: read(os.path.join(self.b, n)) for n in LOCAL}
        self.af("files", "move")
        git(self.dir, "push", "-q")
        self.out = self.af("files", "move", cwd=self.b).stdout

    def test_his_local_files_keep_their_content(self):
        for name in LOCAL:
            self.assertEqual(read(os.path.join(self.b, name)), self.b_files[name], name)

    def test_he_is_at_the_upstream_and_nothing_is_tracked(self):
        self.assertEqual(head(self.b), head(self.dir))
        for name in AGENT_FILES:
            self.assertFalse(tracked(self.b, name), name)
            self.assertTrue(ignored(self.b, name), name)
        self.assertEqual(porcelain(self.b).strip(), "", porcelain(self.b))

    def test_his_history_is_the_shared_one(self):
        self.assertEqual(tip(self.b), tip(self.dir))
        self.assertEqual(read(os.path.join(self.b, "agent_completed.txt")), data_file(self.dir, "agent_completed.txt"))


class TestFilesSet(FilesCase):
    def setUp(self):
        super().setUp()
        self.commit_all()

    def test_sharing_the_ideas_puts_them_on_the_data_branch(self):
        write(os.path.join(self.dir, "agent_ideas.txt"), "an idea | 2026-11-26 09:00 | by Maverick\n")
        out = self.af("files", "set", "task_files", "ideas").stdout
        self.assertIn("agent_ideas.txt: in git", out)
        self.assertEqual(self.conf().get("task_files"), "ideas")
        self.assertIn("task_files=ideas", git(self.dir, "show", "HEAD:agent_repo.conf"))
        self.assertEqual(data_file(self.dir, "agent_ideas.txt"), "an idea | 2026-11-26 09:00 | by Maverick\n")
        self.assertIsNone(data_file(self.dir, "agent_todo.txt"))
        self.assertTrue(ignored(self.dir, "agent_ideas.txt"))
        self.assertEqual(porcelain(self.dir).strip(), "", porcelain(self.dir))

    def test_back_to_local_stops_the_writes(self):
        self.af("files", "set", "task_files", "ideas,todo")
        self.af("files", "set", "task_files", "local")
        data = tip(self.dir)
        self.af("todo", "add", "x", "small", "the x task", "30")
        self.af("idea", "add", "a local idea")
        self.assertEqual(tip(self.dir), data)

    def test_turning_the_todo_on_names_the_unnamed_open_lines(self):
        write(os.path.join(self.dir, "agent_todo.txt"),
              todo_line("old") + "\n" + todo_line("kept", owner="King Lun") + "\n")
        self.af("files", "set", "task_files", "ideas,todo")
        lines = read(os.path.join(self.dir, "agent_todo.txt")).splitlines()
        self.assertTrue(lines[0].endswith(" | owner Maverick"), lines[0])
        self.assertEqual(lines[1].count(" | owner "), 1, lines[1])
        self.assertIn(" | owner King Lun", lines[1])
        self.assertEqual(data_file(self.dir, "agent_todo.txt"), read(os.path.join(self.dir, "agent_todo.txt")))

    def test_a_bad_value_is_refused(self):
        r = self.af("files", "set", "task_files", "everything", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("task_files", self.conf())
        r = self.af("files", "set", "task_take", "boss", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("task_take", self.conf())

    def test_task_take_is_committed(self):
        self.af("files", "set", "task_take", "anyone")
        self.assertEqual(self.conf().get("task_take"), "anyone")
        self.assertEqual(head_files(self.dir), ["agent_repo.conf"])


# ---------------------------------------------------------------- section 2 and 7: the writers commit to ap-data


class Ex3TodoDoneCommitsTheHistory(FilesCase):
    def test_the_record_goes_onto_the_data_branch_and_the_checkout_does_not_move(self):
        self.commit_all()
        with open(os.path.join(self.dir, "seed.txt"), "a") as fh:
            fh.write("a product change in progress\n")
        git(self.dir, "add", "seed.txt")
        with open(os.path.join(self.dir, "seed.txt"), "a") as fh:
            fh.write("and an unstaged one\n")
        self.af("todo", "add", "t", "small", "the t task", "30")
        sha, staged = head(self.dir), git(self.dir, "diff", "--cached")
        self.af("todo", "done", "t", "--work", "20", "--type", "script", "--lane", "fast")
        done = read(os.path.join(self.dir, "agent_completed.txt"))
        self.assertIn("| t |", done)
        self.assertEqual(data_file(self.dir, "agent_completed.txt"), done)
        self.assertEqual(head(self.dir), sha, "HEAD moved")
        self.assertEqual(git(self.dir, "diff", "--cached"), staged, "the index moved")
        self.assertIn("and an unstaged one", read(os.path.join(self.dir, "seed.txt")))
        self.assertNotIn("agent_completed.txt", porcelain(self.dir))
        self.assertEqual(sorted(git(self.dir, "ls-tree", "--name-only", DATA).split()), ["agent_completed.txt"])

    def test_the_local_todo_never_goes_there(self):
        self.commit_all()
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.af("todo", "stage", "t", "brief")
        self.assertEqual(tip(self.dir), "")

    def test_the_log_says_who_did_what(self):
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.af("todo", "done", "t", "--work", "20", "--type", "script", "--lane", "fast")
        log = git(self.dir, "log", "--format=%an %s", DATA)
        self.assertIn("Maverick", log)
        self.assertIn("todo done t", log)


class Ex4SharedIdeasOnly(FilesCase):
    def setUp(self):
        super().setUp()
        self.commit_all()
        self.af("files", "set", "task_files", "ideas")

    def test_idea_add_puts_a_commit_on_the_data_branch(self):
        before, sha = tip(self.dir), head(self.dir)
        self.af("idea", "add", "a shared idea")
        self.assertNotEqual(tip(self.dir), before)
        self.assertIn("a shared idea", data_file(self.dir, "agent_ideas.txt"))
        self.assertEqual(head(self.dir), sha)

    def test_idea_rm_too(self):
        self.af("idea", "add", "one")
        self.af("idea", "add", "two")
        self.af("idea", "rm", "1")
        self.assertNotIn("one", data_file(self.dir, "agent_ideas.txt"))
        self.assertIn("two", data_file(self.dir, "agent_ideas.txt"))

    def test_todo_add_puts_none(self):
        before = tip(self.dir)
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.assertEqual(tip(self.dir), before)


class Ex12AFailedPushNeverBlocks(FilesCase):
    def test_todo_done_succeeds_and_the_next_write_pushes_both(self):
        self.commit_all()
        self.make_remote()
        hook = self.refuse_data_pushes()
        self.af("todo", "add", "t", "small", "the t task", "30")
        r = self.af("todo", "done", "t", "--work", "20", "--type", "script", "--lane", "fast")
        said = [l for l in (r.stdout + r.stderr).splitlines() if "not pushed" in l]
        self.assertEqual(len(said), 1, r.stdout + r.stderr)
        self.assertIn("| t |", read(os.path.join(self.dir, "agent_completed.txt")))
        self.assertEqual(tip(self.bare), "")
        os.remove(hook)
        self.af("todo", "add", "t2", "small", "the t2 task", "30")
        self.af("todo", "done", "t2", "--work", "20", "--type", "script", "--lane", "fast")
        self.assertEqual(tip(self.bare), tip(self.dir))
        remote = data_file(self.bare, "agent_completed.txt")
        self.assertIn("| t |", remote)
        self.assertIn("| t2 |", remote)


class Ex5TheCloudPackSharesBoth(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="agent_files_pack_"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.src = os.path.join(self.base, "src")
        os.makedirs(self.src)
        for part in ("bin", "skills", "agents", "hooks", ".claude-plugin", "PRINCIPLES.md"):
            full = os.path.join(ROOT, part)
            if os.path.isdir(full):
                shutil.copytree(full, os.path.join(self.src, part),
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            elif os.path.exists(full):
                shutil.copy2(full, os.path.join(self.src, part))
        self.target = os.path.join(self.base, "target")
        os.makedirs(self.target)
        subprocess.run(["git", "init", "-q", self.target], check=True, capture_output=True)
        git(self.target, "config", "user.name", "t")
        git(self.target, "config", "user.email", "t@t.t")
        write(os.path.join(self.target, "seed.txt"), "x\n")
        git(self.target, "add", "-A")
        git(self.target, "commit", "-q", "-m", "seed")
        env = dict(os.environ)
        for key in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "AGENT_ROLE", "CLAUDE_CODE_REMOTE", "AGENT_RUNTIME",
                    "CLAUDE_CONFIG_DIR"):
            env.pop(key, None)
        env["HOME"] = os.path.join(self.base, "home")
        os.makedirs(env["HOME"])
        env["CLAUDE_CONFIG_DIR"] = os.path.join(self.base, "no-claude-config")
        env["AGENT_FAKE_RAM"] = "10"
        env["AGENT_FAKE_CPU"] = "10"
        self.env = env
        self.out = self.pack()

    def pack(self):
        r = subprocess.run([os.path.join(self.src, "bin", "agent-cloud-pack.sh"), self.target], cwd=self.base,
                           env=self.env, capture_output=True, text=True, input="", timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_the_pack_leaves_both_shared_in_the_tree(self):
        lines = read(os.path.join(self.target, "agent_repo.conf")).splitlines()
        self.assertIn("task_files=ideas,todo", lines)
        self.assertIn("task_place=tree", lines)

    def test_the_task_files_are_not_ignored(self):
        for name in ("agent_todo.txt", "agent_ideas.txt", "agent_completed.txt"):
            self.assertFalse(ignored(self.target, name), name)

    def test_the_printed_add_line_works(self):
        line = [l.strip() for l in self.out.splitlines() if l.strip().startswith("git add ")]
        self.assertEqual(len(line), 1, self.out)
        r = subprocess.run(line[0], shell=True, cwd=self.target, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        staged = git(self.target, "diff", "--cached", "--name-only").split()
        for name in ("agent_todo.txt", "agent_ideas.txt", "agent_completed.txt", "agent_repo.conf"):
            self.assertIn(name, staged)

    def test_a_write_in_the_tree_makes_no_data_branch(self):
        r = subprocess.run([os.path.join(self.target, ".claude", "auto-pipeline", "bin", "agent-file.sh"), "idea",
                            "add", "packed"], cwd=self.target, env=self.env, capture_output=True, text=True,
                           input="", timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("packed", read(os.path.join(self.target, "agent_ideas.txt")))
        self.assertEqual(tip(self.target), "")

    def test_a_second_pack_changes_nothing(self):
        before = read(os.path.join(self.target, "agent_repo.conf")), read(os.path.join(self.target, ".gitignore"))
        self.pack()
        after = read(os.path.join(self.target, "agent_repo.conf")), read(os.path.join(self.target, ".gitignore"))
        self.assertEqual(before, after)


# ---------------------------------------------------------------- section 3: a name on every record


class TestNamesOnIdeasAndQuestions(FilesCase):
    def test_an_idea_carries_the_name(self):
        self.af("idea", "add", "a named idea")
        self.assertEqual(read(os.path.join(self.dir, "agent_ideas.txt")),
                         "a named idea | %s | by Maverick\n" % NOW)

    def test_the_ideas_list_shows_the_name(self):
        self.af("idea", "add", "a named idea")
        out = self.af("idea", "list").stdout
        self.assertIn("[Maverick]", out)
        self.assertIn("a named idea", out)

    def test_an_old_idea_shows_no_role_as_a_name(self):
        write(os.path.join(self.dir, "agent_ideas.txt"), "an old idea | 2026-11-01 10:00 | by main\n")
        self.assertNotIn("[main]", self.af("idea", "list").stdout)

    def test_a_name_with_a_space_is_kept_whole(self):
        git(self.dir, "config", "user.name", "King Lun")
        self.af("idea", "add", "his idea")
        self.assertTrue(read(os.path.join(self.dir, "agent_ideas.txt")).endswith(" | by King Lun\n"))
        self.assertIn("[King Lun]", self.af("idea", "list").stdout)

    def test_a_parked_question_carries_the_name(self):
        self.af("park", "add", "which DB for reports?")
        state = read(os.path.join(self.dir, "agent_state.txt"))
        line = [l for l in state.splitlines() if l.startswith("PARKED: which DB")][0]
        self.assertTrue(line.endswith(" | by Maverick"), line)

    def test_the_question_list_shows_the_name(self):
        self.af("park", "add", "which DB for reports?")
        self.assertIn("[Maverick]", self.af("questions").stdout)
        data = json.loads(self.af("questions", "--json").stdout)
        q = [x for x in data["questions"] if x["title"] == "which DB for reports?"][0]
        self.assertEqual(q.get("by"), "Maverick")

    def test_no_git_name_takes_the_login_name(self):
        # TELL c4ec5b42: git has no name -> the login name; no prompt, no refusal
        import getpass
        git(self.dir, "config", "--unset", "user.name")
        env = no_identity(self.repo.base)
        self.af("park", "add", "a question?", env=env)
        line = [l for l in read(os.path.join(self.dir, "agent_state.txt")).splitlines()
                if l.startswith("PARKED: a question?")][0]
        self.assertTrue(line.endswith(" | by %s" % getpass.getuser()), line)
        self.af("idea", "add", "an idea", env=env)
        self.assertTrue(read(os.path.join(self.dir, "agent_ideas.txt")).endswith(" | by %s\n" % getpass.getuser()))

    def test_a_cleaned_name_is_the_same_person(self):
        # an old stored 'maverick' matches 'Maverick' (TELL c4ec5b42); shown raw as stored
        write(os.path.join(self.dir, "agent_ideas.txt"), "x | 2026-11-26 09:00 | by King Lun\n")
        self.assertIn("[King Lun]", self.af("idea", "list").stdout)


class Ex11TheBoardShowsTheOwner(FilesCase):
    def test_the_board_shows_the_owner_beside_the_task(self):
        write(os.path.join(self.dir, "agent_todo.txt"), todo_line("t", owner="Maverick") + "\n")
        out = self.af("board").stdout
        row = [l for l in out.splitlines() if l.startswith("|") and " t " in l + " "]
        self.assertTrue(row, out)
        self.assertIn("[Maverick]", row[0])

    def test_an_unnamed_task_shows_no_bracket(self):
        write(os.path.join(self.dir, "agent_todo.txt"), todo_line("t") + "\n")
        self.assertNotIn("[main]", self.af("board").stdout)


class Ex10ALocalTodoNeverAsksWhoYouAre(FilesCase):
    def test_no_command_asks(self):
        self.commit_all()
        git(self.dir, "config", "--unset", "user.name")
        git(self.dir, "config", "--unset", "user.email")
        env = no_identity(self.repo.base)
        outs = []
        for args in (("idea", "add", "x"), ("todo", "add", "t", "small", "the t task", "30"),
                     ("todo", "stage", "t", "brief"), ("park", "add", "q?"),
                     ("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")):
            r = self.af(*args, env=env)
            outs.append(r.stdout + r.stderr)
        text = "\n".join(outs).lower()
        for word in ("user.name", "who you are", "identity", "user.email"):
            self.assertNotIn(word, text)
        self.assertIn("| t |", data_file(self.dir, "agent_completed.txt") or "", "the record never reached ap-data")


# ---------------------------------------------------------------- section 4: two clones of one bare repo


class PairCase(FilesCase):
    """Maverick's clone (self.dir) and King Lun's clone (self.b) of one bare repo, the todo and ideas in git."""

    take = "owner"

    def setUp(self):
        super().setUp()
        git(self.dir, "config", "user.email", "maverick@example.invalid")
        self.commit_all()
        self.make_remote()
        self.af("files", "set", "task_files", "ideas,todo")
        if self.take != "owner":
            self.af("files", "set", "task_take", self.take)
        git(self.dir, "push", "-q")
        self.b = os.path.join(self.repo.base, "kinglun")
        subprocess.run(["git", "clone", "-q", self.bare, self.b], check=True, capture_output=True)
        git(self.b, "config", "user.name", "King Lun")
        git(self.b, "config", "user.email", "kinglun@example.invalid")
        self.af("files", "move", cwd=self.b)

    def todo_of(self, path):
        p = os.path.join(path, "agent_todo.txt")
        return read(p) if os.path.exists(p) else ""

    def line_of(self, path, task):
        for line in self.todo_of(path).splitlines():
            if line.split(" | ", 1)[0] == task:
                return line
        return None

    def sync(self, path):
        return self.af("files", "sync", cwd=path)

    def put_line(self, line):
        """A todo line written by hand into Maverick's working copy, synced to both clones."""
        with open(os.path.join(self.dir, "agent_todo.txt"), "a") as fh:
            fh.write(line + "\n")
        self.sync(self.dir)
        self.sync(self.b)
        self.assertEqual(self.line_of(self.b, line.split(" | ", 1)[0]), line)

    def remote_todo(self):
        return data_file(self.bare, "agent_todo.txt") or ""

    def dispatch(self, path, task):
        """The main manager of that clone launches '<task> Deputy' through the board guard."""
        gd = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        write(os.path.join(gd, "agent_main.lock"), "%d 2026-11-26 09:00 s-main term_main\n" % os.getpid())
        cfg = os.path.join(self.repo.base, "cfg")
        os.makedirs(cfg, exist_ok=True)
        payload = {"session_id": "s1", "transcript_path": os.path.join(cfg, "t.jsonl"), "cwd": path,
                   "permission_mode": "bypassPermissions", "hook_event_name": "PreToolUse", "tool_name": "Agent",
                   "tool_use_id": "toolu_%d" % len(os.listdir(cfg)),
                   "tool_input": {"description": "%s Deputy" % task, "prompt": "brief",
                                  "subagent_type": "auto-pipeline:fast-lane-deputy", "run_in_background": True}}
        r = self.repo.run("agent-guard.sh", cwd=path, stdin=json.dumps(payload),
                          env={"CLAUDE_PID": str(os.getpid()), "CLAUDE_CONFIG_DIR": cfg, "AGENT_FAKE_NOW": NOW})
        self.assertNotIn("Traceback", r.stderr)
        return r


class TestTheSharedSetup(PairCase):
    def test_his_clone_has_the_shared_files_and_tracks_none(self):
        self.assertEqual(tip(self.b), tip(self.dir))
        for name in AGENT_FILES:
            self.assertFalse(tracked(self.b, name), name)
        self.assertEqual(porcelain(self.b).strip(), "", porcelain(self.b))

    def test_every_write_is_pushed_at_once(self):
        self.af("idea", "add", "pushed at once")
        self.assertIn("pushed at once", data_file(self.bare, "agent_ideas.txt") or "")
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.assertIn("t | ", self.remote_todo())

    def test_two_new_ideas_at_the_end_both_stay(self):
        self.af("idea", "add", "hers")
        self.af("idea", "add", "his", cwd=self.b)
        self.sync(self.dir)
        for path in (self.dir, self.b):
            ideas = read(os.path.join(path, "agent_ideas.txt"))
            self.assertIn("hers", ideas)
            self.assertIn("his", ideas)
        self.assertEqual(tip(self.bare), tip(self.dir))


class Ex6AssignOnlyByTheOwner(PairCase):
    def test_a_dispatch_of_his_task_is_refused_until_he_assigns_it(self):
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.assertIn(" | owner Maverick", self.line_of(self.dir, "t") or "")
        r = self.dispatch(self.b, "t")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("t belongs to Maverick", r.stderr)
        self.af("todo", "assign", "t", "King Lun")
        self.sync(self.b)
        self.assertIn(" | assignee King Lun", self.line_of(self.b, "t"))
        r = self.dispatch(self.b, "t")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_he_may_not_assign_her_task(self):
        self.put_line(todo_line("t", owner="Maverick"))
        r = self.af("todo", "assign", "t", "x", cwd=self.b, ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("t belongs to Maverick; only the owner assigns", r.stderr)
        self.assertNotIn("assignee", self.line_of(self.b, "t"))


class TestWhoMayWorkIt(PairCase):
    def test_stage_and_done_of_her_task_are_refused(self):
        self.put_line(todo_line("t", owner="Maverick"))
        for args in (("todo", "stage", "t", "brief"), ("todo", "done", "t", "--work", "5")):
            with self.subTest(args=args):
                r = self.af(*args, cwd=self.b, ok=False)
                self.assertEqual(r.returncode, 1)
                self.assertIn("t belongs to Maverick; ask them to assign it", r.stderr)
        self.assertIsNotNone(self.line_of(self.b, "t"))

    def test_an_assigned_task_is_his_to_work(self):
        self.put_line(todo_line("t", owner="Maverick", extra=" | assignee King Lun"))
        self.af("todo", "stage", "t", "brief", cwd=self.b)
        r = self.af("todo", "stage", "t", "brief", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("t is assigned to King Lun", r.stderr)

    def test_the_dispatch_reads_the_newest_todo(self):
        self.put_line(todo_line("t", owner="Maverick"))
        self.af("todo", "assign", "t", "King Lun")
        r = self.dispatch(self.b, "t")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_merge_gate_refuses_her_task(self):
        self.put_line(todo_line("t", owner="Maverick", extra=" | checks PR REVIEW"))
        r = self.af("checks", "gate", "t", "--dir", self.b, cwd=self.b, ok=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("t belongs to Maverick", r.stdout + r.stderr)

    def test_approval_words_count_only_in_her_session(self):
        self.put_line(todo_line("t", owner="Maverick"))
        r = self.af("todo", "target", "t", "production", "--owner-quote", "publish t when it is done",
                    "--means", "publish t to production", cwd=self.b, ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("t belongs to Maverick", r.stderr)
        self.assertNotIn("target production", self.line_of(self.b, "t"))

    def test_an_unnamed_line_has_no_check(self):
        self.put_line(todo_line("t"))
        self.af("todo", "stage", "t", "brief", cwd=self.b)

    def test_take_needs_task_take_anyone(self):
        self.put_line(todo_line("t", owner="Maverick"))
        r = self.af("todo", "take", "t", cwd=self.b, ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ask Maverick to assign it", r.stderr)

    def test_next_reads_the_newest_todo(self):
        self.af("todo", "add", "fresh", "small", "a fresh task", "30")
        self.assertIsNone(self.line_of(self.b, "fresh"))
        self.af("next", cwd=self.b)
        self.assertIsNotNone(self.line_of(self.b, "fresh"))


class TestALocalTodoHasNoCheck(FilesCase):
    def test_someone_elses_line_is_yours_locally(self):
        write(os.path.join(self.dir, "agent_todo.txt"), todo_line("t", owner="King Lun") + "\n")
        self.af("todo", "stage", "t", "brief")
        r = self.af("todo", "assign", "t", "x", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("local", r.stderr)


class Ex8TakeWhenAnyoneMay(PairCase):
    take = "anyone"

    def test_the_second_taker_is_told_who_took_it(self):
        self.put_line(todo_line("t", owner="Maverick"))
        self.assertIn("t is yours", self.af("todo", "take", "t").stdout)
        self.assertIn(" | taken Maverick", self.remote_todo(), "todo take did not push at once")
        r = self.af("todo", "take", "t", cwd=self.b, ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("t was taken by Maverick", r.stderr)
        self.assertNotIn("taken King Lun", self.line_of(self.b, "t"))

    def test_from_the_same_state_one_gets_it(self):
        # King Lun's push meets the remote moved by Maverick's take in between (pre-push hook): sync, check again
        self.put_line(todo_line("t", owner="Maverick"))
        hook = os.path.join(self.b, ".git", "hooks", "pre-push")
        mark = os.path.join(self.repo.base, "raced")
        write(hook, "#!/bin/sh\n[ -e '%s' ] && exit 0\ntouch '%s'\nunset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE\n"
                    "cd '%s' && AGENT_FAKE_NOW='%s' '%s' todo take t >/dev/null 2>&1\nexit 0\n"
              % (mark, mark, self.dir, NOW, os.path.join(self.repo.plugin_bin, "agent-file.sh")))
        os.chmod(hook, 0o755)
        r = self.af("todo", "take", "t", cwd=self.b, ok=False)
        self.assertTrue(os.path.exists(mark), "the race hook never ran")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("t was taken by Maverick", r.stderr)
        self.assertIn(" | taken Maverick", self.remote_todo())
        self.assertNotIn("taken King Lun", self.remote_todo())
        self.assertNotIn("taken King Lun", self.line_of(self.b, "t"))

    def test_a_free_task_must_be_taken_before_it_is_worked(self):
        self.put_line(todo_line("t", owner="Maverick"))
        r = self.dispatch(self.b, "t")
        self.assertEqual(r.returncode, 2)
        self.assertIn("t is free: take it first", r.stderr)
        self.af("todo", "take", "t", cwd=self.b)
        self.assertEqual(self.dispatch(self.b, "t").returncode, 0)


class Ex9TwoPeopleFinishAtOnce(PairCase):
    take = "anyone"

    def test_both_records_stay_and_neither_task_comes_back(self):
        self.af("todo", "add", "a", "small", "the a task", "30")
        self.af("todo", "add", "b", "small", "the b task", "30")
        self.sync(self.b)
        self.af("todo", "take", "a")
        self.af("todo", "take", "b", cwd=self.b)
        self.af("todo", "done", "a", "--work", "10", "--type", "script", "--lane", "fast")
        self.af("todo", "done", "b", "--work", "10", "--type", "script", "--lane", "fast", cwd=self.b)
        for path in (self.dir, self.b):
            self.sync(path)
        for path in (self.dir, self.b):
            with self.subTest(clone=path):
                done = read(os.path.join(path, "agent_completed.txt"))
                self.assertIn("| a |", done)
                self.assertIn("| b |", done)
                self.assertIsNone(self.line_of(path, "a"))
                self.assertIsNone(self.line_of(path, "b"))
                self.assertEqual(porcelain(path).strip(), "", porcelain(path))
        self.assertEqual(tip(self.dir), tip(self.b))
        self.assertEqual(tip(self.bare), tip(self.dir))


if __name__ == "__main__":
    unittest.main()
