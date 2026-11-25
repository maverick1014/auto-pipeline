# clean-up — requirements (level 3 rules gate)

Status: draft for the owner's "rules yes". Nothing is coded before it.
Task: `clean-up` (todo line, level 3). Base 8d584c1 (release 0.40.0).
Owner words 2026-11-24: "do a skill also call clean-up, to clean those rubbish document. and also the agent_xxx files info that is outdated or not using anymore" + "for the clean-up understanding is correct ya".

## 0. Words

| Word | Meaning |
|---|---|
| repo | PROJECT_ROOT of the main manager (`agent-roots.sh`): the main checkout. Never a worktree, never another repo |
| seen files | `git ls-files -co --exclude-standard`: tracked files plus untracked files git does not ignore. `node_modules/`, `build/`, `.secrets/` and every ignored file are never seen. A nested repo or worktree folder is never entered |
| doc | a seen file whose extension (any case) is `.md .markdown .mdx .rst .adoc .asciidoc .org .pdf .doc .docx .rtf .odt`. `.txt` and `.html` are not docs |
| open task | first field of a line of `agent_todo.txt` |
| done task | second field of a line of `agent_completed.txt` (done or dropped) |
| days old | today minus the date, in whole days |
| in use | some other tracked file holds the file's name inside one quoted string: `"…/<name>"` or `'<name>'` (`os.path.join(ROOT, "mock", "city-growth-mock.html")` counts; a comment or docstring mention does not) |
| row | one candidate in the table: id, what, where, why, how removed |
| yes | the ids the human picked, passed as `--yes`. Nothing else is a yes |

Config (new keys, `agent-settings.sh`, group `cleanup`):

| Key | Default | Meaning |
|---|---|---|
| `docs_keep` | empty | extra docs a repo keeps. Comma list; an entry ending in `/` keeps that folder, any other entry is a glob on the path from the repo top (`*` crosses folders). Example product repo: `docs_keep=docs/,CHANGELOG.md,*/README.md` |
| `cleanup_days` | 14 | days after which a state copy, the monitor file or a quiet todo line is old. Whole number 1 to 3650 |

## A. Command

One entry: `bin/agent-cleanup.sh` (it already sweeps worktrees, branches, panes, processes). New flags; the logic is a new `bin/agent_cleanfiles.py`, called by the entry; the todo, idea and worktree-line checks are the housekeep pass's own functions (`agent_housekeep.py`), called, never copied.

| # | Call | Result |
|---|---|---|
| A1 | `agent-cleanup.sh --files` | dry run: the table (B), changes nothing (a git fetch is fine), saves the table to `<git dir>/agent-cleanup-files.last`, exit 0 |
| A2 | `agent-cleanup.sh --files --yes D1,M3` | removes exactly those rows (C), exit 0 |
| A3 | `agent-cleanup.sh --files --yes all` | removes every row of the saved table (the human said all) |
| A4 | `agent-cleanup.sh --files --yes none` | `nothing removed`, exit 0, nothing changes |
| A5 | `--files --apply`, `--files --yes` with no value, `--yes` without `--files`, `--yes all,D1` | usage on stderr, exit 2, nothing changes |
| A6 | role spawned, second (Helper) or closed | `REFUSED: cleanup is main manager only (role <r>).`, exit 1 (today's check) |
| A7 | `agent-cleanup.sh`, `--apply`, `--short` (no `--files`) | today's sweep, byte for byte. The automatic sweeps (start, resume, todo done, housekeep) never touch files or lines of this doc |

Dry-run output (the shape; the rows are made up, the real counts are in G):

```
=== clean-up files (dry run, nothing removed) ===
id | what | where | why | how removed
D1 | notes.md | repo, tracked | doc not allowed by the docs rule | git rm, one commit
S1 | agent_state.2026-10-01-101500.txt | repo, untracked | state copy 54 days old (over 14) | rm, no copy
M1 | mock/city-ux-mock.html | repo, tracked | task city-ux done 2026-09-28 | git rm, one commit
I1 | idea: agent-city top bar wraps to a second row… | agent_ideas.txt line 11 | names task city-ux, done 2026-09-28 | idea rm, line backed up
T1 | todo one-watcher | agent_todo.txt | merged into origin/main (commit 6f162a7) | todo done --merge 6f162a7, line backed up
W1 | worktree line /…/old-wt | agent_worktree.txt | folder gone, no live pane (line says working) | worktree rm, line backed up
kept: 1
what | why kept
mock/city-growth-mock.html | in use: tests/test_agent_city_world.py
note: docs_keep not set: a product repo keeps its real docs with agent-settings.sh docs_keep <list>
To remove: agent-cleanup.sh --files --yes <ids>|all|none. Nothing is removed without --yes.
```

Nothing found: `=== clean-up files ===` then `nothing to clean`. Ids: kind letter + number, numbered in table order (files by path, lines by line number). The `docs_keep` note shows only when the key is empty and at least one D row is listed.

## B. What is listed (one row per candidate)

| # | Kind (id) | Listed when | Real example (pc2 main checkout, 2026-11-24) | How removed |
|---|---|---|---|---|
| B1 | doc (D) | a doc that no keep rule (B1a) covers | none in this repo (0). Product layout: `notes.md`, `TODO.md`, `design-old.md`, `meeting-2026.pdf` | tracked: git rm; untracked: rm |
| B1a | keep rules for docs | `requirements/…`; any path part `tests` or `test`; top files `README.md PRINCIPLES.md CLAUDE.md AGENTS.md`; top folders `.claude-plugin/ agents/ skills/ hooks/ bin/`; any path whose first part starts with `.` (`.claude/`, `.github/`, tool config); name starting `LICENSE`, `LICENCE`, `COPYING`, `NOTICE` (any case, any folder); a `docs_keep` entry | `skills/city/setup.md` kept (config folder); `tests/estimate_real.txt` not a doc; `PRINCIPLES.md` kept | — |
| B2 | state copy (S) | top-level `agent_state.YYYY-MM-DD-HHMMSS.txt` (`agent-start.sh --clean`) or `agent_state.trim-YYYY-MM-DD.txt` (`state trim`) whose name date is more than `cleanup_days` days old | pc2: none (0). On 2026-11-24: `agent_state.trim-2026-11-09.txt` (15 days) listed, `…-2026-11-10.txt` (14) not | rm (git-ignored), no copy |
| B3 | monitor file (S) | (2026-11-24: the monitor is gone, nothing writes the file: listed whenever present; the rule below is the old one) top-level `agent_monitor.txt` while no monitor runs (`<git dir>/agent_monitor.pid` missing or its pid dead) and its newest `YYYY-MM-DD HH:MM` is more than `cleanup_days` days old, or it has no date | pc2: listed, 2 lines dated 2026-10-05 (50 days) naming gone worktrees `city-device-join`, `city-tier`; the start text still prints them as STALL | rm; the next monitor sweep writes it new |
| B4 | mock (M) | `mock/<name>-mock.html` (top `mock/` only) where `<name>` is not an open task. Why: `task <name> done <date>`, `dropped <date>`, or `no task named <name>` | 24 of 25: 23 done tasks (`city-ux`, `cloud-polish`, `show-question`, …) minus 1 in use, plus `agent-city-3d` and `idea-city-labels` (no task) | tracked: git rm; untracked: rm |
| B5 | idea (I) | an `agent_ideas.txt` line the housekeep pass would remove (exact duplicate, the later line) or call a suspect (names a task finished after it, or names a file that is gone). A line with ` \| kept <date>` is never listed | 0 (no duplicate; 0 suspects with `agent_state.txt` present). The file has no "done" or "voided" mark today (0 lines), so none is added | `agent-file.sh idea rm <n>`, bottom line first, line backed up |
| B6 | todo, merged (T) | the housekeep pass's merged flag: the task's branch is merged into origin/main, or origin/main has a first-parent commit `Merge <name>` | pc2: `one-watcher` (commit 6f162a7 `Merge one-watcher (W8)`; its line is still in pc2's agent_todo.txt) | `agent-file.sh todo done <name> --merge <sha>` (no sha known: without `--merge`); line backed up |
| B7 | todo, stale (T) | housekeep's stale rule with `cleanup_days` instead of `housekeep_interval_min`: no worktree line, no open wait, newest of `opened` and `stage … since` more than `cleanup_days` days old | 0: `owner-relay` has a worktree line, `comment-shape` waits (queue) | `agent-file.sh todo drop <name> "clean-up: stale <n>d"`; line backed up |
| B8 | worktree line (W) | an `agent_worktree.txt` line whose folder is gone on this machine and on every paired machine, with no live pane: housekeep's "folder gone" rule. Unlike housekeep, a working, final or human-direct line is listed too; the why says `line says <status>` | 0: both lines (`clean-up`, `owner-relay`) have their folder | `agent-file.sh worktree rm <path>`; line backed up |

## C. Remove (`--yes`)

| # | Rule | Example |
|---|---|---|
| C1 | no saved table → `REFUSED: run agent-cleanup.sh --files first. Nothing changed.`, exit 1 | first call is `--yes D1` |
| C2 | the list is worked out again now. Every picked id must be in the saved table AND its row (kind + path, line text, task name or worktree path) must still be a row now. Else `REFUSED: <id> unknown` or `REFUSED: <id> changed since the table: run agent-cleanup.sh --files again. Nothing changed.`, exit 1, nothing changes | `--yes D9` with no D9; an idea line edited between the two calls |
| C3 | ids: comma or space separated, any case (`d1` = `D1`), a repeated id once | `--yes "d1, M2 M2"` = D1, M2 |
| C4 | refused before any change when a merge, rebase or cherry-pick is in progress in the repo, or a tracked row's file has uncommitted changes | `MERGE_HEAD` present |
| C5 | backup first: every line that goes (I, T, W) is appended to `<git dir>/agent-cleanup/<YYYY-MM-DD-HHMMSS>.txt` as `<file> \| <the whole line>` before the first change | `agent_todo.txt \| one-watcher \| big \| …` |
| C6 | order: lines (W, then T, then I bottom up, each idea line's text checked again just before its `idea rm`), then untracked files (rm; a symlink: the link only), then tracked files: `git rm -q -- <paths>`, then ONE commit `clean-up: <n> files` limited to those paths (`git commit -m … -- <paths>`), so other staged work is never in it | D1 + M1 + M2 tracked → one commit `clean-up: 3 files` |
| C7 | no push. The main manager pushes main with the next merge or hands the owner one `! git push origin main` line | — |
| C8 | output: one `removed: <id> <what>` line per row; `commit <sha7> clean-up: <n> files (not pushed)` when files went; `backup: <path> (<k> lines)` when lines went; last line `clean-up: removed <n> of <m> picked` | — |
| C9 | a step fails in the middle → stop there: `FAILED at <id>: <why>. Removed before it: <ids>.`, exit 1; the backup and the commit of what went stay | git rm refused |
| C10 | restore: tracked files `git revert <sha>` (or `git checkout <sha>^ -- <path>`); lines from the backup file through `agent-file.sh` (`idea add`, `todo add`, `worktree set`) or by hand; untracked state copies and the monitor file are gone (the table said "no copy") | — |

## D. Never listed, never removed

| # | Never | Why / how it is sure |
|---|---|---|
| N1 | `agent_completed.txt` | estimate data. No kind reads it as a candidate; `todo done`/`todo drop` only append to it |
| N2 | `agent_estimate.txt`, `agent.conf`, `agent_state.txt` (the live one), `agent_todo.txt` / `agent_ideas.txt` / `agent_worktree.txt` as files | not docs; only single lines of the last three are rows |
| N3 | `.secrets/`, anything under `.git`, every ignored file except B2/B3 names | not seen files; dot folders are keep rules too |
| N4 | untracked user files outside the kinds above (code, data, images, `.txt`, `.html` outside `mock/`) | only B kinds are ever rows |
| N5 | a file in use | kept row `in use: <file>` |
| N6 | a tracked row file with uncommitted changes | kept row `uncommitted changes` |
| N7 | another repo, a worktree folder, a paired machine's files | only the repo top is scanned |
| N8 | anything without a yes | `--files` alone never changes a file; the automatic sweeps never pass `--files` |

## E. Edge cases

| # | Case | Result |
|---|---|---|
| E1 | `docs_keep=docs/` and `docs/old.md` | kept (not listed) |
| E2 | `docs_keep=*/README.md`, `packages/web/README.md` | kept; without it: D row |
| E3 | `requirements.txt`, `CMakeLists.txt`, `robots.txt` in a product repo | never listed (`.txt` is not a doc) |
| E4 | `node_modules/x/README.md` (ignored) | never listed |
| E5 | untracked `notes.md` the human just wrote | D row, "repo, untracked", "rm" — the human says no |
| E6 | a mock of an open task (`mock/owner-relay-mock.html` while `owner-relay` is open) | never listed |
| E7 | mock named in `requirements/city.md` and in a test docstring only | listed (a mention is not use); the why says the task |
| E8 | `agent_state.trim-2026-11-10.txt` on 2026-11-24, `cleanup_days=14` | not listed (14, not more) |
| E9 | (old, the monitor is gone) monitor running, `agent_monitor.txt` 50 days old | not listed |
| E10 | orca not answering (orca runtime) | no W rows; note `orca not answering: worktree lines not checked` (housekeep's rule) |
| E11 | no origin/main | no T merged rows; D S M I rows still listed |
| E12 | leftover `agent_monitor.txt.tmp.<pid>` / `agent_state.txt.tmp.<pid>` | not listed (count 0 on pc2; housekeep and the monitor clean their own) |
| E13 | `--yes` names a row the human did not see because the table changed | C2 refuses all |
| E14 | the saved table names `agent_completed.txt` (hand edited) | C2: not a row now → refused |
| E15 | the idea at line 80 moved to line 79 (an idea rm ran in between) | C2: the row key is the line text, so I-id still matches; the rm uses the new line number |
| E16 | an idea naming `agent_state.txt` or `agent_monitor.txt` on a machine without that file (both git-ignored, one per machine) | never a suspect, in the housekeep block too (E2E on pc2: 8 valid ideas were offered for removal) |
| E17 | two W lines with one path, or two T lines with one name (only after a hand edit) | their rows go together: `--yes` with one of them is refused, naming the others |
| E18 | a CRLF `agent_ideas.txt` | parsed without the `\r`, removed by its raw line |

## F. Skill `skills/clean-up/SKILL.md` (`/auto-pipeline:clean-up`)

| # | Rule |
|---|---|
| F1 | any repo with the plugin; main manager only (a task manager or Helper: refuse in one line) |
| F2 | step 1: run `${CLAUDE_PLUGIN_ROOT}/bin/agent-cleanup.sh --files`, show the table as printed, every row, then the decide section: remove which rows — all, some ids, or none — with a recommendation |
| F3 | step 2: only after the human's answer: `--yes <ids>` / `--yes all` / `--yes none`. A refusal → run step 1 again and ask again. Never `--yes` without the human's answer in this session |
| F4 | after: show the output lines; files went → push main or hand the owner `! git push origin main` |
| F5 | language of agent.conf for the words to the human; ids and commands stay as printed |

PRINCIPLES.md R3 gets one line: rubbish docs and outdated agent_* lines are listed by `/auto-pipeline:clean-up`, removed only after the human's yes; `docs_keep` keeps a product repo's docs. README skills list gets one line.

## G. Real-data count (H1)

| Source | D docs | S state copies | S monitor file | M mocks | I ideas | T todo | W worktree lines |
|---|---|---|---|---|---|---|---|
| pc2 main checkout `/Users/maverick/auto-pipeline` (HEAD 8d584c1 = origin/main, read only; housekeep checks run on a scratch clone with pc2's agent files) | 0 | 0 (no archive on pc2) | 1 (2 lines, 50 days) | 24 listed, 1 kept (in use) | 0 | 1 (one-watcher, merged) | 0 |
| laptop main checkout | not read: ignored files (state copies) live only there; the tracked files are the same as pc2 after a pull | | | | | | |
| product-like layout (scratch, 21 files: docs/, CHANGELOG.md, CONTRIBUTING.md, LICENSE, .github/, node_modules/, packages/web/README.md, requirements.txt, stray notes) | 10 with `docs_keep` empty; 6 with `docs_keep=docs/,CHANGELOG.md` | — | — | 2 | — | — | — |

The real product repos (v4-plus, v4-pospro) were not read: a repo never reads another repo.

## H. Decisions taken (defaults, owner may change)

| # | Decision | Other choice |
|---|---|---|
| H1 | `docs_keep` default empty: this repo needs strict R3; a product repo sees its docs listed (never removed without yes) plus the note how to keep them | default `docs/` (fewer rows in product repos, but this repo would silently keep a `docs/` folder) |
| H2 | mocks: listed when no open task has the name (covers the 2 mocks of no task), not only "task in agent_completed.txt" | only done tasks (2 mocks stay forever) |
| H3 | ideas: the housekeep pass's duplicate and suspect checks, no new done/voided mark (count 0) | add `idea done <n>` / `idea void <n>` marks |
| H4 | `agent_monitor.txt` added (owner: "agent_xxx info that is outdated"), scope add 1 | leave it out |
| H5 | `--yes all` allowed: "all" is the human's explicit word for every row of the saved table | ids only |
| H6 | untracked state copies and the monitor file are removed with no copy; lines get a backup; tracked files are in git history | copy everything first |
| H7 | one key `cleanup_days` for state copies, monitor file and quiet todo lines | three keys |
