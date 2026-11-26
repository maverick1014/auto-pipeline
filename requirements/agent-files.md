# agent-files: local by default, shared by choice, a name on every record

Owner, 2026-11-26, his words:
- "actually initially i plan these all is local only. so that it will not have conflict ya ... is that the agent_xxx file is all local only and not commit to github in default, except the user want then can uplaod the ideas,todo to the repo. becasue worktree actually is purelly local ya. then for cloud session then it will be a must to push those ideeas and todo to the repo ya. if not cannot sync between cloud session also"
- On the finished-task records and the time estimate model: "this one i think default git will do, becaue is like a history. then we can know each of the person chanegs also."
- "When multiple people use a repo ... normally the repo will define who is the one can merge the thing ... according to the task is created by who. example today i created a task in todo. then without me assign to others. they cannot do ya. except i set in the setting that the todo list and ideas can be change or take by anyone."
- "for each of the record beside we add a bracket to write the owner name or the people who make this changes."
- "1. For local confirm no issues at all. 2. ... the todo and ideas is at git ... if it setting is only the owner can do, then simple. others all block will do. elseif the user assigned another developer. example maverick assigned this task to king lun, so king lun can do this task. 3. what if the setting is anyone can do. then at the moment you take the task then you need to update the git status. so that it can be a cross collobrate space also. as long as the user pull from the base repo and know what is the latest status now."

## 1. Today (checked 2026-11-26)

- Setup (`bin/agent-init.sh`) git-ignores only `agent_state.txt`, `agent_monitor.txt`, `.secrets/`, `.auto-pipeline/`.
- `agent_todo.txt`, `agent_completed.txt`, `agent_ideas.txt`, `agent_worktree.txt` are plain files in the repo root. No script commits them; nothing keeps them out of a commit. The cloud pack prints a `git add ... agent_*.txt` line.
- In this repo they are tracked, with `agent_estimate.txt`. The copies in git are days old; the real content sits uncommitted in the main checkout. So every worktree holds a stale copy, and a `git reset --hard` in the main checkout would wipe the real ones.
- No record says which person wrote it. A todo line has `by main` (the role), not a name.

## 2. Where each file lives

| File | Default | By choice |
|---|---|---|
| `agent_state.txt`, `agent_monitor.txt` | local, always | - |
| `agent_worktree.txt` | local, always | - |
| `agent_todo.txt` | local | in git |
| `agent_ideas.txt` | local | in git |
| `agent_completed.txt`, `agent_estimate.txt` | in git (the history) | - |
| `agent_repo.conf` | in git (facts of the repo) | - |

- The choice is one fact of the repo, the same for everyone in it, so it lives in the committed `agent_repo.conf`: `task_files = local` (default), `ideas`, or `ideas,todo`.
- A cloud repo must share both: the cloud pack sets `task_files = ideas,todo`.
- No agent file is tracked on a code branch (cloud is the one exception, below). In the main checkout every agent file is git-ignored and untracked: no worktree gets a copy, no merge touches it, a reset cannot wipe it.
- "Local" = it stays only there.
- "In git" = the script that writes the file also commits it to the DATA BRANCH `ap-data` of the repo and pushes it at once. The data branch holds only agent files; it is written with git plumbing (as `bin/agent_release.py` writes the release branch), never checked out, never merged into a code branch, so it causes no merge conflict with code, no deploy and no stale copy. `git log ap-data` is the history: who finished, added, took or assigned what.
- Why not the code branch: each person works on his own working branch (`ap-main-<name>`), so a todo committed there is seen by the others only after a publish; and a commit on the production branch starts a deploy. The owner's case 3 needs the status the moment a task is taken.
- A push that fails (offline, refused) never blocks the work: the commit stays, the next write pushes it; the command says so in one line.
- Before a file in git is read for a decision (offer a task, take, assign, start, the board in a shared repo) the data branch is fetched and merged into the local file: finished records and ideas by union (no line is lost), todo lines by task name (the newest change of a task wins; a finished task is dropped).
- Cloud: a cloud session can push only its own branch, so there the pack keeps the task files tracked in the tree and committed with the work, as today.

Settings (owner 2026-11-26: "for this setting is able to set in configure right ?"; "default ap-data will be better. then othres can refer to tht one also. then at the configure there also able to switch brnach will do. if the user want it be main also can ya"):
- Three settings in /plugin Configure, the person's default for his repos: "Task files in git" (`local` | `ideas` | `ideas,todo`, default `local`), "Who may take a task" (`owner` | `anyone`, default `owner`), "Data branch" (a branch name, default `ap-data`).
- The repo value wins: a value in the committed `agent_repo.conf` is used whatever a member's Configure says, because every member of a repo must see the same. The command that turns sharing on writes the three values there. A member whose Configure differs gets one line at start naming the repo's value.
- "Data branch" may name any branch, the production branch too ("main"). Then the files in git are written straight onto that branch and pushed at once, so everyone who pulls it sees them; the command that sets it says once that a commit on a production branch can start a deploy in that repo. The local working copies and the copies on that branch must never fight (a pull, a merge of production into the working branch, a new worktree): tests prove it for `ap-data` and for `main`.

## 3. A name on every record

- The name = the git user name of the clone (`git config user.name`; the working branch name uses the same source).
- A todo line: `owner <name>`; when given to someone: `assignee <name>`; when taken: `taken <name>`.
- A finished-task record: `by <name>` in its data block.
- An idea and a parked question: the author's name.
- Every list a human reads (the board, the todo and question skills, the ideas list) shows `[<name>]` beside the record.
- Old records have no name. In a local repo that changes nothing. When a repo turns sharing on, the command gives the unnamed open todo lines to the person who runs it.

## 4. Working together (only when the todo is in git)

One more fact in `agent_repo.conf`: `task_take = owner` (default) or `anyone`.

| Case | What happens |
|---|---|
| Local todo (default) | No check. Every task is yours |
| In git, `owner`, your own task | You work it |
| In git, `owner`, someone else's task | Refused: "<task> belongs to <name>; ask him to assign it" |
| In git, the owner ran `todo assign <task> <name>` | That person works it. Only the owner assigns |
| In git, `anyone`, a free task | `todo take <task>`: pull, refuse when someone took it meanwhile, write `taken <name>`, commit, push at once. A refused push = someone was faster: pull, check again |

- "Work it" = every step that starts or moves the task: a dispatch (the board guard), `todo stage`, `todo done`, a merge.
- Adding a task or an idea is always allowed; it carries the author's name.
- A change that others must see at once is pushed at once: add, assign, take, done. Before a task is offered or started, the newest todo is pulled.
- Approval words (publish, leave out a check, sign) count for a task only in the session of its owner or assignee.
- Who may merge or publish: the repo's own permissions. A push the repo refuses is reported, never worked around.
- Two people who add, take and finish different tasks never end in a conflict a human must resolve; a finished task never comes back into the todo; two finished-task records written at the same time both stay. The estimate model is never merged by hand: after a pull that brought new records it is trained again.

## 5. Moving an existing repo

- One command, run in the main checkout, takes a repo from "tracked and changed" to its mode: every agent file is taken out of the code branch with its content kept (a copy goes into the git folder first), the ignore lines are written, and the files that are in git by section 2 go onto the data branch (created when missing, pushed). It prints what it did per file. Run twice, the second run changes nothing.
- In another clone of that repo the same command settles the pull: a local file removed upstream keeps its content there too.
- Setup in a new repo writes the ignore lines for every agent file and no team facts: the person's Configure is the default (section 2, Settings); the command that turns sharing on writes them.
- THIS repo is moved by the main manager in the main checkout after the merge. The task branch must not delete, untrack or commit this repo's own `agent_*.txt` files: a merge into a checkout that has changed them would be refused.

## 6. Order and dependency

- The task estimate-improve is rewriting the writers of the todo line and of the finished-task record right now. The name fields of section 3 on those two records are built THERE (the main manager sent it that order). This task reads them.
- Start with what does not need them: where the files live (section 2), the move command (section 5), the two facts in `agent_repo.conf`, the cloud pack, the names on ideas and parked questions. Then, after merging main with estimate-improve's result: assign, take and the refusals (section 4).

## 7. Examples (the failing tests come from these)

- Setup in a new repo: `git status` does not list any agent file; `git check-ignore` names `agent_todo.txt`, `agent_ideas.txt`, `agent_worktree.txt`, `agent_completed.txt` and `agent_estimate.txt` (section 2: every agent file is git-ignored in the main checkout; the files in git live on the data branch).
- A repo that tracks `agent_todo.txt` with 3 uncommitted lines: after the move command the file still has those lines, `git ls-files agent_todo.txt` is empty, and a new worktree has no `agent_todo.txt`.
- `todo done` in a default repo: `agent_completed.txt` has the new record, `git status` of the code branch is clean, and the tip of `ap-data` holds the same file content; HEAD and the index of the checkout did not move.
- `task_files = ideas`: `idea add` puts a new commit on `ap-data`; `todo add` puts none.
- The remote refuses the push of `ap-data`: `todo done` still succeeds and prints one line; the next write pushes both commits.
- The cloud pack leaves `task_files = ideas,todo`.
- Todo in git, `task_take = owner`: Maverick adds task t. In King Lun's clone a dispatch of t is refused and the line names Maverick. After Maverick runs `todo assign t "King Lun"` and King Lun pulls, it is allowed.
- King Lun runs `todo assign t x` on Maverick's task: refused.
- `task_take = anyone`: A and B both run `todo take t` from the same state: one gets it, the other is told who took it.
- A finishes task a while B finishes task b: after both pull, the finished-task file has both records and the todo has neither task.
- Local todo: no command asks who you are.
- The board shows `[Maverick]` beside a task; the ideas list beside an idea.

## 8. Not in this task

- How the estimate is computed (estimate-improve).
- The structure of the rule files (md-slim-principles-2); only the lines on the task files change, in whatever file holds them when this task merges.
- Roles or permissions inside GitHub.
