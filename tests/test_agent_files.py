"""agent-files: local by default, shared by choice, a name on every record (requirements/agent-files.md).

The contract the workers build to. One class per feature; the examples of section 7 are the classes named Ex<n>.

Facts, in the committed agent_repo.conf ("key=value"; "key = value" reads the same; a missing key = the default):
  task_files=local (default) | ideas | ideas,todo      which task files are in git besides the history
  task_take=owner (default) | anyone                    who may work a task of a todo in git

Where a file lives (section 2):
  agent_state.txt, agent_monitor.txt, agent_worktree.txt   local, always
  agent_todo.txt                                           local, unless task_files names todo
  agent_ideas.txt                                          local, unless task_files names ideas
  agent_completed.txt, agent_estimate.txt                  in git, always
  Local  = an exact line "<file>" in .gitignore, and the file is not tracked.
  In git = no such line; whatever script writes the file commits that change at once: one commit that holds that file
           only (`git commit --only`), in the main checkout, on its current branch. Other staged or changed files are
           never part of it. No git identity: a fallback identity is used, nothing asks who you are.
  .gitattributes (written by init and files move, never committed by init): agent_todo.txt merge=agent-todo,
           agent_ideas.txt and agent_completed.txt merge=agent-lines, agent_estimate.txt merge=agent-keep. The drivers
           are set in the clone's .git/config by init, files move and before every pull a script makes:
           agent-todo   one line per task name: a removal by either side wins, a line both sides changed takes theirs
           agent-lines  every new line of both sides stays, a removal by either side wins
           agent-keep   ours (the estimate model is trained again after a pull that brought new records)

The name (section 3) = `git config user.name` of the clone, trimmed. Empty: no name.
  idea add      "<text> | <date> | by <name>"   (no name: "by <role>" as before)
  park add      "PARKED: ... | by <name>"        (the last field; no name: no field)
  todo line     " | owner <name>" (written by todo add, task estimate-improve), " | assignee <name>", " | taken <name>"
  idea list, board, questions   "[<name>]" beside the record

Commands (bin/agent-file.sh):
  files show                    "files: task_files=<v> task_take=<v>", then one line per agent file: "<file>: local" or
                                "<file>: in git"
  files move                    in the main checkout only. (1) Upstream ahead: keep the agent files' content, pull
                                (merge), put a local file's content back (a local file removed upstream keeps it).
                                (2) Settle by the mode: a local file that is tracked is copied to
                                <git common dir>/agent-files-kept/ and taken out of git (git rm --cached), content kept;
                                its ignore line is added. An in-git file loses its ignore line and is committed when it
                                is untracked or changed. .gitattributes and the drivers are written. Turning the todo
                                into git gives every open todo line with no owner field " | owner <name>".
                                One commit holds what the move changed (.gitignore, .gitattributes, the removals, the
                                in-git files). Refused (exit 1, nothing moves): run outside the main checkout ("run it
                                in the main checkout"), a staged change of any other file ("the index has staged
                                changes").
                                One line per file ("<file>: local (...)" / "<file>: in git (...)"; "(already)" when
                                nothing changed for it); last line "files move: done" or "files move: nothing changed".
                                Run twice, the second run changes nothing. It never pushes.
  files set task_files <local|ideas|ideas,todo>    the fact in agent_repo.conf (committed), then files move
  files set task_take <owner|anyone>               the fact in agent_repo.conf (committed)
  todo assign <task> <name>     todo in git, the owner only: " | assignee <name>", commit, push at once
  todo take <task>              todo in git, task_take=anyone: pull, refuse when someone took it, " | taken <name>",
                                commit, push at once; a push refused because the upstream moved = pull, check again;
                                any other refusal is reported ("refused"), never forced, and the take does not stand:
                                the local line is as before it. Success: "todo take: <task> is yours"
  todo add, todo done           todo in git: commit, push at once
  next                          todo in git: pulls first

Who may work a task (section 4), only when the todo is in git ("work" = a dispatch through the board guard,
todo stage, todo done, the merge gate, and the approval words: todo target, todo checks --remove):
  taken <x>     only x                     else "<task> was taken by <x>"
  assignee <x>  only x                     else "<task> is assigned to <x>"
  owner <x>     task_take=owner: only x    else "<task> belongs to <x>; ask them to assign it"
                task_take=anyone: free     a dispatch or a stage of a free task: "<task> is free: take it first
                                           (agent-file.sh todo take <task>)"
  no owner      no check
A local todo: no check, no name asked. The logic lives in bin/agent_share.py (python3, stdlib only).
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

LOCAL = ("agent_todo.txt", "agent_ideas.txt", "agent_worktree.txt")
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


class OldRepoCase(FilesCase):
    """A repo that tracks every agent file (the state before this task), with real lines in them."""

    def setUp(self):
        super().setUp()
        with open(os.path.join(self.dir, ".gitignore")) as fh:
            keep = [l for l in fh.read().splitlines() if l not in LOCAL]
        write(os.path.join(self.dir, ".gitignore"), "".join(l + "\n" for l in keep))
        write(os.path.join(self.dir, "agent_todo.txt"), todo_line("t0") + "\n")
        write(os.path.join(self.dir, "agent_ideas.txt"), "an old idea | 2026-11-01 10:00 | by main\n")
        write(os.path.join(self.dir, "agent_worktree.txt"), "/tmp/wt | t0 | working | since 2026-11-26 09:00\n")
        write(os.path.join(self.dir, "agent_completed.txt"), "2026-11-01 | old | the old task | est 5m actual 5m\n")
        write(os.path.join(self.dir, "agent_estimate.txt"), '{"version": 1}\n')
        git(self.dir, "add", "-f", "--", *(list(LOCAL) + ["agent_completed.txt", "agent_estimate.txt"]))
        self.commit_all(msg="old style: the agent files tracked")
        for name in LOCAL:
            self.assertTrue(tracked(self.dir, name), name)


# ---------------------------------------------------------------- section 2 and 7: setup in a new repo


class Ex1SetupInANewRepo(FilesCase):
    def test_the_local_files_are_ignored_and_not_listed(self):
        status = porcelain(self.dir)
        for name in LOCAL:
            with self.subTest(name=name):
                self.assertNotIn(name, status)
                self.assertTrue(ignored(self.dir, name), "%s is not ignored" % name)

    def test_the_history_is_not_ignored(self):
        self.assertFalse(ignored(self.dir, "agent_completed.txt"))
        self.assertFalse(ignored(self.dir, "agent_estimate.txt"))

    def test_the_default_facts_are_written(self):
        conf = self.conf()
        self.assertEqual(conf.get("task_files"), "local")
        self.assertEqual(conf.get("task_take"), "owner")

    def test_the_merge_lines_are_written(self):
        text = read(os.path.join(self.dir, ".gitattributes"))
        self.assertIn("agent_todo.txt merge=agent-todo", text)
        self.assertIn("agent_completed.txt merge=agent-lines", text)
        self.assertIn("agent_ideas.txt merge=agent-lines", text)
        self.assertIn("agent_estimate.txt merge=agent-keep", text)

    def test_init_twice_changes_nothing(self):
        before = {n: read(os.path.join(self.dir, n)) for n in (".gitignore", ".gitattributes", "agent_repo.conf")}
        self.assertOk(self.repo.run("agent-init.sh", "--no-measure", "--no-branch"))
        after = {n: read(os.path.join(self.dir, n)) for n in before}
        self.assertEqual(before, after)

    def test_files_show_names_where_each_file_lives(self):
        out = self.af("files", "show").stdout
        self.assertIn("files: task_files=local task_take=owner", out)
        for name in LOCAL:
            self.assertIn("%s: local" % name, out)
        self.assertIn("agent_completed.txt: in git", out)
        self.assertIn("agent_estimate.txt: in git", out)

    def test_a_spaced_fact_reads_the_same(self):
        path = os.path.join(self.dir, "agent_repo.conf")
        text = read(path).replace("task_files=local", "task_files = ideas")
        write(path, text)
        out = self.af("files", "show").stdout
        self.assertIn("task_files=ideas", out)
        self.assertIn("agent_ideas.txt: in git", out)


# ---------------------------------------------------------------- section 5 and 7: the move command


class Ex2MoveARepoThatTracksTheTodo(OldRepoCase):
    def setUp(self):
        super().setUp()
        self.lines = [todo_line("a"), todo_line("b"), todo_line("c")]
        with open(os.path.join(self.dir, "agent_todo.txt"), "a") as fh:
            fh.write("".join(l + "\n" for l in self.lines))
        self.before = read(os.path.join(self.dir, "agent_todo.txt"))
        self.out = self.af("files", "move").stdout

    def test_the_file_keeps_its_lines(self):
        self.assertEqual(read(os.path.join(self.dir, "agent_todo.txt")), self.before)

    def test_it_is_out_of_git(self):
        self.assertEqual(git(self.dir, "ls-files", "agent_todo.txt").strip(), "")
        self.assertTrue(ignored(self.dir, "agent_todo.txt"))
        self.assertNotIn("agent_todo.txt", porcelain(self.dir))

    def test_a_new_worktree_has_no_todo(self):
        wt = os.path.join(self.repo.base, "wt_new")
        git(self.dir, "worktree", "add", "-q", "-b", "new-task", wt)
        self.assertFalse(os.path.exists(os.path.join(wt, "agent_todo.txt")))
        self.assertFalse(os.path.exists(os.path.join(wt, "agent_ideas.txt")))
        self.assertFalse(os.path.exists(os.path.join(wt, "agent_worktree.txt")))
        self.assertTrue(os.path.exists(os.path.join(wt, "agent_completed.txt")))

    def test_a_copy_goes_into_the_git_folder(self):
        gd = git(self.dir, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        copies = glob.glob(os.path.join(gd, "agent-files-kept", "agent_todo.txt*"))
        self.assertTrue(copies, "no copy under %s/agent-files-kept" % gd)
        self.assertIn(self.before, [read(c) for c in copies])

    def test_every_local_file_moves_and_the_history_stays(self):
        for name in LOCAL:
            with self.subTest(name=name):
                self.assertFalse(tracked(self.dir, name))
                self.assertTrue(os.path.exists(os.path.join(self.dir, name)))
        self.assertTrue(tracked(self.dir, "agent_completed.txt"))
        self.assertTrue(tracked(self.dir, "agent_estimate.txt"))

    def test_it_says_what_it_did_per_file(self):
        for name in LOCAL:
            self.assertIn("%s: local" % name, self.out)
        self.assertIn("agent_completed.txt: in git", self.out)
        self.assertIn("files move: done", self.out)

    def test_the_tree_is_clean_after_it(self):
        self.assertEqual(porcelain(self.dir).strip(), "", porcelain(self.dir))

    def test_a_second_run_changes_nothing(self):
        sha = head(self.dir)
        files = {n: read(os.path.join(self.dir, n)) for n in LOCAL + (".gitignore", "agent_completed.txt")}
        out = self.af("files", "move").stdout
        self.assertEqual(head(self.dir), sha)
        self.assertEqual({n: read(os.path.join(self.dir, n)) for n in files}, files)
        self.assertIn("files move: nothing changed", out)
        for name in LOCAL:
            self.assertIn("%s: local (already)" % name, out)


class TestMoveCommitsTheHistory(OldRepoCase):
    def test_a_changed_history_is_committed(self):
        with open(os.path.join(self.dir, "agent_completed.txt"), "a") as fh:
            fh.write("2026-11-26 | new | a new record | est 5m actual 5m\n")
        self.af("files", "move")
        self.assertEqual(porcelain(self.dir, "agent_completed.txt"), "")
        self.assertIn("a new record", git(self.dir, "show", "HEAD:agent_completed.txt"))

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

    def test_it_runs_only_in_the_main_checkout(self):
        wt = os.path.join(self.repo.base, "wt_side")
        git(self.dir, "worktree", "add", "-q", "-b", "side", wt)
        r = self.af("files", "move", cwd=wt, ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("main checkout", r.stderr)


class TestFilesSet(FilesCase):
    def test_sharing_the_ideas_puts_them_in_git(self):
        self.commit_all()
        out = self.af("files", "set", "task_files", "ideas").stdout
        self.assertIn("agent_ideas.txt: in git", out)
        self.assertEqual(self.conf().get("task_files"), "ideas")
        self.assertIn("task_files=ideas", git(self.dir, "show", "HEAD:agent_repo.conf"))
        self.assertTrue(tracked(self.dir, "agent_ideas.txt"))
        self.assertFalse(ignored(self.dir, "agent_ideas.txt"))
        self.assertTrue(ignored(self.dir, "agent_todo.txt"))
        self.assertEqual(porcelain(self.dir).strip(), "", porcelain(self.dir))

    def test_back_to_local_takes_them_out_again(self):
        self.commit_all()
        self.af("files", "set", "task_files", "ideas,todo")
        self.af("files", "set", "task_files", "local")
        self.assertFalse(tracked(self.dir, "agent_ideas.txt"))
        self.assertFalse(tracked(self.dir, "agent_todo.txt"))
        self.assertTrue(ignored(self.dir, "agent_todo.txt"))

    def test_turning_the_todo_on_names_the_unnamed_open_lines(self):
        self.commit_all()
        write(os.path.join(self.dir, "agent_todo.txt"),
              todo_line("old") + "\n" + todo_line("kept", owner="King Lun") + "\n")
        self.af("files", "set", "task_files", "ideas,todo")
        lines = read(os.path.join(self.dir, "agent_todo.txt")).splitlines()
        self.assertTrue(lines[0].endswith(" | owner Maverick"), lines[0])
        self.assertEqual(lines[1].count(" | owner "), 1, lines[1])
        self.assertIn(" | owner King Lun", lines[1])
        self.assertEqual(porcelain(self.dir).strip(), "", porcelain(self.dir))

    def test_a_bad_value_is_refused(self):
        r = self.af("files", "set", "task_files", "everything", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.conf().get("task_files"), "local")
        r = self.af("files", "set", "task_take", "boss", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.conf().get("task_take"), "owner")

    def test_task_take_is_committed(self):
        self.commit_all()
        self.af("files", "set", "task_take", "anyone")
        self.assertEqual(self.conf().get("task_take"), "anyone")
        self.assertEqual(head_files(self.dir), ["agent_repo.conf"])


# ---------------------------------------------------------------- section 2 and 7: the writers commit


class Ex3TodoDoneCommitsTheHistory(FilesCase):
    def test_the_record_is_committed_alone(self):
        self.commit_all()
        with open(os.path.join(self.dir, "seed.txt"), "a") as fh:
            fh.write("a product change in progress\n")
        git(self.dir, "add", "seed.txt")
        with open(os.path.join(self.dir, "seed.txt"), "a") as fh:
            fh.write("and an unstaged one\n")
        self.af("todo", "add", "t", "small", "the t task", "30")
        sha = head(self.dir)
        self.af("todo", "done", "t", "--work", "20", "--type", "script", "--lane", "fast")
        self.assertNotEqual(head(self.dir), sha, "todo done made no commit")
        self.assertEqual(head_files(self.dir), ["agent_completed.txt"])
        self.assertIn("| t |", git(self.dir, "show", "HEAD:agent_completed.txt"))
        self.assertEqual(porcelain(self.dir, "agent_completed.txt"), "")
        self.assertEqual(git(self.dir, "diff", "--cached", "--name-only").split(), ["seed.txt"])
        self.assertIn("and an unstaged one", read(os.path.join(self.dir, "seed.txt")))

    def test_the_local_todo_is_never_committed(self):
        self.commit_all()
        sha = head(self.dir)
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.af("todo", "stage", "t", "brief")
        self.assertEqual(head(self.dir), sha)
        self.assertFalse(tracked(self.dir, "agent_todo.txt"))


class Ex4SharedIdeasOnly(FilesCase):
    def setUp(self):
        super().setUp()
        self.commit_all()
        self.af("files", "set", "task_files", "ideas")

    def test_idea_add_commits_the_ideas(self):
        sha = head(self.dir)
        self.af("idea", "add", "a shared idea")
        self.assertNotEqual(head(self.dir), sha)
        self.assertEqual(head_files(self.dir), ["agent_ideas.txt"])
        self.assertIn("a shared idea", git(self.dir, "show", "HEAD:agent_ideas.txt"))
        self.assertEqual(porcelain(self.dir, "agent_ideas.txt"), "")

    def test_idea_rm_commits_too(self):
        self.af("idea", "add", "one")
        self.af("idea", "add", "two")
        self.af("idea", "rm", "1")
        self.assertNotIn("one", git(self.dir, "show", "HEAD:agent_ideas.txt"))
        self.assertEqual(porcelain(self.dir, "agent_ideas.txt"), "")

    def test_todo_add_commits_nothing(self):
        sha = head(self.dir)
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.assertEqual(head(self.dir), sha)


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
        r = subprocess.run([os.path.join(self.src, "bin", "agent-cloud-pack.sh"), self.target], cwd=self.base,
                           env=env, capture_output=True, text=True, input="", timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.out = r.stdout

    def test_the_pack_leaves_both_shared(self):
        conf = read(os.path.join(self.target, "agent_repo.conf"))
        self.assertIn("task_files=ideas,todo", conf.splitlines())

    def test_todo_and_ideas_are_not_ignored_the_worktree_file_is(self):
        self.assertFalse(ignored(self.target, "agent_todo.txt"))
        self.assertFalse(ignored(self.target, "agent_ideas.txt"))
        self.assertTrue(ignored(self.target, "agent_worktree.txt"))

    def test_the_printed_add_line_works(self):
        line = [l.strip() for l in self.out.splitlines() if l.strip().startswith("git add ")]
        self.assertEqual(len(line), 1, self.out)
        self.assertNotIn("agent_*.txt", line[0])
        for name in ("agent_todo.txt", "agent_ideas.txt", "agent_completed.txt", "agent_repo.conf"):
            self.assertIn(name, line[0])
        self.assertNotIn("agent_worktree.txt", line[0])
        r = subprocess.run(line[0], shell=True, cwd=self.target, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_second_pack_changes_nothing(self):
        before = read(os.path.join(self.target, "agent_repo.conf")), read(os.path.join(self.target, ".gitignore"))
        r = subprocess.run([os.path.join(self.src, "bin", "agent-cloud-pack.sh"), self.target], cwd=self.base,
                           env=self.env, capture_output=True, text=True, input="", timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
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
        out = self.af("idea", "list").stdout
        self.assertNotIn("[main]", out)

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
        out = self.af("questions").stdout
        self.assertIn("[Maverick]", out)
        data = json.loads(self.af("questions", "--json").stdout)
        q = [x for x in data["questions"] if x["title"] == "which DB for reports?"][0]
        self.assertEqual(q.get("by"), "Maverick")

    def test_no_name_no_field(self):
        git(self.dir, "config", "--unset", "user.name")
        env = self.no_identity()
        self.af("park", "add", "a question?", env=env)
        line = [l for l in read(os.path.join(self.dir, "agent_state.txt")).splitlines()
                if l.startswith("PARKED: a question?")][0]
        self.assertNotIn(" | by ", line)

    def no_identity(self):
        home = os.path.join(self.repo.base, "empty_home")
        os.makedirs(home, exist_ok=True)
        return {"HOME": home, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                "XDG_CONFIG_HOME": home}


class Ex11TheBoardShowsTheOwner(FilesCase):
    def test_the_board_shows_the_owner_beside_the_task(self):
        write(os.path.join(self.dir, "agent_todo.txt"), todo_line("t", owner="Maverick") + "\n")
        out = self.af("board").stdout
        row = [l for l in out.splitlines() if l.startswith("|") and " t " in l + " "]
        self.assertTrue(row, out)
        self.assertIn("[Maverick]", row[0])

    def test_an_unnamed_task_shows_no_bracket(self):
        write(os.path.join(self.dir, "agent_todo.txt"), todo_line("t") + "\n")
        out = self.af("board").stdout
        self.assertNotIn("[main]", out)


class Ex10ALocalTodoNeverAsksWhoYouAre(FilesCase):
    def test_no_command_asks(self):
        self.commit_all()
        git(self.dir, "config", "--unset", "user.name")
        git(self.dir, "config", "--unset", "user.email")
        home = os.path.join(self.repo.base, "empty_home")
        os.makedirs(home)
        env = {"HOME": home, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "XDG_CONFIG_HOME": home}
        outs = []
        for args in (("idea", "add", "x"), ("todo", "add", "t", "small", "the t task", "30"),
                     ("todo", "stage", "t", "brief"), ("park", "add", "q?"),
                     ("todo", "done", "t", "--work", "5", "--type", "script", "--lane", "fast")):
            r = self.af(*args, env=env)
            outs.append(r.stdout + r.stderr)
        text = "\n".join(outs).lower()
        for word in ("user.name", "who you are", "identity", "user.email"):
            self.assertNotIn(word, text)
        self.assertEqual(porcelain(self.dir, "agent_completed.txt"), "", "the record was left uncommitted")


# ---------------------------------------------------------------- section 4: two clones of one bare repo


class PairCase(FilesCase):
    """Maverick's clone (self.dir) and King Lun's clone (self.b) of one bare repo, the todo and ideas in git."""

    take = "owner"

    def setUp(self):
        super().setUp()
        git(self.dir, "config", "user.email", "maverick@example.invalid")
        self.af("files", "set", "task_files", "ideas,todo")
        if self.take != "owner":
            self.af("files", "set", "task_take", self.take)
        self.commit_all()
        self.bare = os.path.join(self.repo.base, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", self.bare], check=True, capture_output=True)
        git(self.dir, "remote", "add", "origin", self.bare)
        self.branch = git(self.dir, "symbolic-ref", "--short", "HEAD").strip()
        git(self.dir, "push", "-q", "-u", "origin", self.branch)
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

    def put_line(self, line):
        """A todo line written straight into Maverick's clone, committed and pushed; King Lun pulls."""
        with open(os.path.join(self.dir, "agent_todo.txt"), "a") as fh:
            fh.write(line + "\n")
        git(self.dir, "commit", "-q", "-m", "fixture line", "--", "agent_todo.txt")
        git(self.dir, "push", "-q")
        git(self.b, "pull", "-q", "--no-rebase", "--no-edit")

    def remote_todo(self):
        return git(self.bare, "show", "%s:agent_todo.txt" % self.branch, check=False)

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


class TestTheMoveInTheOtherClone(OldRepoCase):
    """A repo where both clones track the todo; Maverick moves and pushes; King Lun's move settles the pull."""

    def setUp(self):
        super().setUp()
        self.bare = os.path.join(self.repo.base, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", self.bare], check=True, capture_output=True)
        git(self.dir, "remote", "add", "origin", self.bare)
        branch = git(self.dir, "symbolic-ref", "--short", "HEAD").strip()
        git(self.dir, "push", "-q", "-u", "origin", branch)
        self.b = os.path.join(self.repo.base, "kinglun")
        subprocess.run(["git", "clone", "-q", self.bare, self.b], check=True, capture_output=True)
        git(self.b, "config", "user.name", "King Lun")
        git(self.b, "config", "user.email", "kinglun@example.invalid")
        with open(os.path.join(self.b, "agent_todo.txt"), "a") as fh:
            fh.write(todo_line("his-local-task") + "\n")
        self.b_todo = read(os.path.join(self.b, "agent_todo.txt"))
        self.b_ideas = read(os.path.join(self.b, "agent_ideas.txt"))
        self.af("files", "move")
        git(self.dir, "push", "-q")
        self.out = self.af("files", "move", cwd=self.b).stdout

    def test_his_files_keep_their_content(self):
        self.assertEqual(read(os.path.join(self.b, "agent_todo.txt")), self.b_todo)
        self.assertEqual(read(os.path.join(self.b, "agent_ideas.txt")), self.b_ideas)

    def test_he_is_at_the_upstream_and_the_files_are_local(self):
        self.assertEqual(head(self.b), head(self.dir))
        for name in ("agent_todo.txt", "agent_ideas.txt"):
            self.assertFalse(tracked(self.b, name))
            self.assertTrue(ignored(self.b, name))
        self.assertEqual(porcelain(self.b).strip(), "", porcelain(self.b))


class Ex6AssignOnlyByTheOwner(PairCase):
    def test_a_dispatch_of_his_task_is_refused_until_he_assigns_it(self):
        self.af("todo", "add", "t", "small", "the t task", "30")
        self.assertIn(" | owner Maverick", self.line_of(self.dir, "t") or "")
        self.assertIn("t | ", self.remote_todo(), "todo add did not push at once")
        git(self.b, "pull", "-q", "--no-rebase", "--no-edit")
        r = self.dispatch(self.b, "t")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("t belongs to Maverick", r.stderr)
        self.af("todo", "assign", "t", "King Lun")
        git(self.b, "pull", "-q", "--no-rebase", "--no-edit")
        self.assertIn(" | assignee King Lun", self.line_of(self.b, "t"))
        r = self.dispatch(self.b, "t")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_he_may_not_assign_her_task(self):
        self.put_line(todo_line("t", owner="Maverick"))
        r = self.af("todo", "assign", "t", "x", cwd=self.b, ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("t belongs to Maverick", r.stderr)
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

    def test_next_pulls_the_newest_todo(self):
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
        out = self.af("todo", "take", "t").stdout
        self.assertIn("t is yours", out)
        self.assertIn(" | taken Maverick", self.remote_todo(), "todo take did not push at once")
        r = self.af("todo", "take", "t", cwd=self.b, ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("t was taken by Maverick", r.stderr)
        self.assertNotIn("taken King Lun", self.line_of(self.b, "t"))

    def test_from_the_same_state_one_gets_it(self):
        # King Lun's push meets the remote moved by Maverick's take in between (pre-push hook): pull, check again
        self.put_line(todo_line("t", owner="Maverick"))
        hook = os.path.join(self.b, ".git", "hooks", "pre-push")
        mark = os.path.join(self.repo.base, "raced")
        write(hook, "#!/bin/sh\n[ -e '%s' ] && exit 0\ntouch '%s'\nunset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE\n"
                    "cd '%s' && AGENT_FAKE_NOW='%s' '%s' todo take t "
                    ">/dev/null 2>&1\nexit 0\n"
              % (mark, mark, self.dir, NOW, os.path.join(self.repo.plugin_bin, "agent-file.sh")))
        os.chmod(hook, 0o755)
        r = self.af("todo", "take", "t", cwd=self.b, ok=False)
        self.assertTrue(os.path.exists(mark), "the race hook never ran")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("t was taken by Maverick", r.stderr)
        self.assertIn(" | taken Maverick", self.remote_todo())
        self.assertNotIn("taken King Lun", self.remote_todo())
        self.assertNotIn("<<<<<<<", self.todo_of(self.b))

    def test_a_free_task_must_be_taken_before_it_is_worked(self):
        self.put_line(todo_line("t", owner="Maverick"))
        r = self.dispatch(self.b, "t")
        self.assertEqual(r.returncode, 2)
        self.assertIn("t is free: take it first", r.stderr)
        self.af("todo", "take", "t", cwd=self.b)
        self.assertEqual(self.dispatch(self.b, "t").returncode, 0)

    def test_a_push_the_repo_refuses_is_reported(self):
        self.put_line(todo_line("t", owner="Maverick"))
        hook = os.path.join(self.bare, "hooks", "pre-receive")
        write(hook, "#!/bin/sh\necho 'protected branch' >&2\nexit 1\n")
        os.chmod(hook, 0o755)
        r = self.af("todo", "take", "t", cwd=self.b, ok=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("refused", (r.stdout + r.stderr).lower())
        self.assertNotIn("taken King Lun", self.remote_todo())
        self.assertNotIn("taken King Lun", self.line_of(self.b, "t"))


class Ex9TwoPeopleFinishAtOnce(PairCase):
    take = "anyone"

    def test_both_records_stay_and_neither_task_comes_back(self):
        self.af("todo", "add", "a", "small", "the a task", "30")
        self.af("todo", "add", "b", "small", "the b task", "30")
        git(self.b, "pull", "-q", "--no-rebase", "--no-edit")
        self.af("todo", "take", "a")
        self.af("todo", "take", "b", cwd=self.b)
        git(self.dir, "pull", "-q", "--no-rebase", "--no-edit")
        self.af("todo", "done", "a", "--work", "10", "--type", "script", "--lane", "fast")
        self.af("todo", "done", "b", "--work", "10", "--type", "script", "--lane", "fast", cwd=self.b)
        for path in (self.dir, self.b):
            git(path, "pull", "-q", "--no-rebase", "--no-edit")
        for path in (self.dir, self.b):
            with self.subTest(clone=path):
                done = read(os.path.join(path, "agent_completed.txt"))
                self.assertIn("| a |", done)
                self.assertIn("| b |", done)
                self.assertNotIn("<<<<<<<", done)
                self.assertIsNone(self.line_of(path, "a"))
                self.assertIsNone(self.line_of(path, "b"))
                self.assertEqual(porcelain(path, "agent_completed.txt"), "")
                self.assertEqual(porcelain(path, "agent_todo.txt"), "")


class TestTheMergeDrivers(PairCase):
    def test_two_new_ideas_at_the_end_both_stay(self):
        self.af("idea", "add", "hers")
        self.af("idea", "add", "his", cwd=self.b)
        git(self.dir, "push", "-q")
        r = subprocess.run(["git", "-C", self.b, "pull", "-q", "--no-rebase", "--no-edit"], capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ideas = read(os.path.join(self.b, "agent_ideas.txt"))
        self.assertIn("hers", ideas)
        self.assertIn("his", ideas)
        self.assertNotIn("<<<<<<<", ideas)


if __name__ == "__main__":
    unittest.main()
