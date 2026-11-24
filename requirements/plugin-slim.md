# plugin-slim — requirements (level 4 rules gate)

Status: rules draft 2026-11-24, waits for owner "rules yes". Base e90db3b (release 0.39.0).
Source: owner 2026-11-24: "those no need thing is no needed to give to end user". Todo line: ship only hooks/, bin/, PRINCIPLES.md, skills/, agents/, .claude-plugin/; plugin update and cloud-pack keep working; rollback plan (owner 2B).
Examples: real numbers of e90db3b and a probe run on pc2 at 2026-11-24 10:24 (Claude Code 2.1.331, temp HOME and CLAUDE_CONFIG_DIR, never the real ~/.claude).

## 0. Words

| Word | Meaning |
|---|---|
| ship set | the six paths users get: `.claude-plugin/`, `hooks/`, `bin/`, `skills/`, `agents/`, `PRINCIPLES.md` |
| cache | `<config>/plugins/cache/auto-pipeline/auto-pipeline/<version>/`: the copy every session loads (`CLAUDE_PLUGIN_ROOT`); one folder per version |
| clone | `<config>/plugins/marketplaces/auto-pipeline/`: the marketplace checkout (shallow, depth 1) |
| release branch | branch `release` of maverick1014/auto-pipeline: one commit per version, its tree = the ship set of a main commit, nothing else |
| release script | new `bin/agent-release.sh`: builds, checks and pushes the release branch |
| reads check | the release script's scan: every plugin-root path a shipped file names must be in the ship set |

## 1. Research (docs, quoted; probe facts measured)

| # | Question | Doc line (quoted) | Conclusion |
|---|---|---|---|
| D1 | Exclude list? | Marketplace and plugin fields list no `files`, ignore file or exclude field; "`strict`" governs only component fields ([marketplace-reference](https://code.claude.com/docs/en/plugins/marketplace-reference.md#plugin-sources)) | no exclude list exists: option C is out |
| D2 | What a relative source copies | "Claude Code copies the plugin into `cache/<marketplace>/<plugin>/<version>/` at install and loads that copy. Files outside the plugin directory aren't copied" ([loading](https://code.claude.com/docs/en/plugins/loading.md)); "A plugin at the marketplace root, with `"source": "./"`, gets every submodule" | `"./"` = the whole repo. Probe: cache 0.39.0 = 357 files, 15 MB, every top-level item incl. tests/, mock/, agent_*.txt, CLAUDE.md, .claude/ |
| D3 | Source types | relative path; `github` (`repo`, `ref`, `sha`); `url` (`url`, `ref`, `sha`); `git-subdir` (`url`, `path`, `ref`, `sha`); `npm`; `archive`; `command`. "`ref`: a branch or tag. Defaults to the repository's default branch." | a `url` or `github` entry can point at a branch of the same repo |
| D4 | Subfolder | "Use a relative path for a plugin in a subdirectory of the marketplace repository itself." "If your repository has a large submodule that only your build uses, move the plugin into a subdirectory." | option B is the documented pattern; it moves files |
| D5 | Versions | "1. The `version` field in the plugin's manifest comes first 2. Then the `version` field in the plugin's marketplace entry"; "a manifest that pins `"version": "1.0.0"` keeps every user on the cached copy until its author changes the string." ([loading#versions-and-updates](https://code.claude.com/docs/en/plugins/loading.md#versions-and-updates)) | a new build needs a new version string |
| D6 | Old cache | "Claude Code writes an `.orphaned_at` marker into the previous version directory. It removes that directory in a background cleanup 14 days later." | a session mid-update keeps its old folder for 14 days |
| D7 | Clone size | `claude plugin marketplace add <source> --sparse <paths...>`: "Limit checkout to specific directories via git sparse-checkout (for monorepos)" (CLI help 2.1.331) | only the user can make the clone smaller; we cannot for existing users |
| D8 | Symlinks | "Within the plugin's own directory: the symlink is preserved"; "Outside the marketplace: the symlink is skipped" ([host-marketplace](https://code.claude.com/docs/en/plugins/host-marketplace.md#share-files-within-a-marketplace-with-symlinks)) | no symlink in the ship set today (`find bin -type l`: none) |

Probe (pc2, scratch bare repo served by `git http-backend`, `url` source):

| Step | Result |
|---|---|
| P1 install e90db3b as today (`"source":"./"`) | cache 0.39.0: 15 MB, whole repo, no `.git`; clone: 19 MB, shallow, 1 commit |
| P2 main: version 0.39.1 + entry `{"source":"url","url":…,"ref":"release"}`; release = ship set (git plumbing, no checkout) | `claude plugin update`: "updated from 0.39.0 to 0.39.1"; cache 0.39.1 = `.claude-plugin agents bin hooks PRINCIPLES.md skills`, 9.5 MB; 0.39.0 got `.orphaned_at` |
| P3 next release: only the release branch moves (0.39.2), main not pushed, no marketplace update | "updated from 0.39.1 to 0.39.2" |
| P4 entry ref points at a branch that does not exist | update: git "Remote branch no-such-ref not found", install stays 0.39.2; fresh install: "Failed to install", exit 1 |

## 2. Audit A: every top-level item of the repo

| Item | Size (git) | Ship | Why |
|---|---|---|---|
| `.claude-plugin/` | 2 files | yes | plugin.json: name, version, userConfig. marketplace.json rides along (harmless in the cache) |
| `hooks/` | 1 file | yes | hooks.json: every hook |
| `bin/` | 9.4 MB | yes | every script; `bin/agent-city-assets/` (7.5 MB) is read by the city page (agent_city.py `agent-city-assets`, agent-city.sh cloud upload) |
| `skills/` | 6 skills | yes | the slash commands |
| `agents/` | 3 files | yes | worker, deputies |
| `PRINCIPLES.md` | 35 KB | yes | start text prints it, cloud-pack copies it, holds the MIT notice of section E |
| `README.md` | 12 KB | no | for people reading the repo; GitHub shows it. No script reads it (only tests/test_plugin_layout.py) |
| `CLAUDE.md`, `AGENTS.md` | 85 B each | no | this repo's own entry files. agent-init.sh writes the user's AGENTS.md from a string, not from this file |
| `agent.conf` | 514 B | no | this repo's settings. Users get `bin/agent.conf.default` through init |
| `agent_todo.txt`, `agent_completed.txt`, `agent_ideas.txt`, `agent_worktree.txt`, `agent_estimate.txt` | 89 KB | no | this repo's task files. Every script reads them from PROJECT_ROOT (`ROOT="$PROJECT_ROOT"`, agent-file.sh:201) |
| `agent_state.txt`, `agent_monitor.txt` | - | no | git-ignored, never in a commit |
| `tests/` | 143 files, 3.9 MB | no | dev only |
| `mock/` | 25 files, 1.1 MB | no | UI mocks, dev only |
| `requirements/` | 5 files, 164 KB | no | dev docs. Code comments cite them (`requirements/city.md`), nothing opens them |
| `.claude/` | settings.json | no | this repo's own permissions and enabledPlugins |
| `.gitignore` | 87 B | no | git only |

Total: ship 173 files, 9.56 MB of 357 files, 14.81 MB (-35%).

## 3. Audit B: every plugin-root read in the ship set

Patterns searched: `$PLUGIN_ROOT/…`, `${CLAUDE_PLUGIN_ROOT}/…`, `$(dirname "$0")/…`, `$(dirname "${BASH_SOURCE[0]}")/…`, `$SELF_DIR/…`, python `os.path.dirname(os.path.abspath(__file__))` joins (`HERE`, `bin_dir`, `script_dir`, `_bin_path`).

| Reader | Reads | In ship set |
|---|---|---|
| hooks/hooks.json, skills/*/SKILL.md, agents/merge-deputy.md | `${CLAUDE_PLUGIN_ROOT}/bin/<script>` only | yes |
| bin/agent-start.sh | `PRINCIPLES.md`, `bin/agent.conf.default`, `bin/*` | yes |
| bin/agent-cloud-pack.sh | `bin/`, `skills/`, `agents/`, `PRINCIPLES.md`, `.claude-plugin/plugin.json`, `hooks/hooks.json` | yes |
| bin/agent-init.sh, agent-settings.sh, agent-autoclear.sh, agent_board.py, agent_state.py, agent-city.sh | `bin/agent.conf.default` | yes |
| bin/agent-city.sh, agent_city.py | `bin/agent-city.html`, `bin/agent-city-assets/`, `bin/agent-city-shim`, `bin/agent-city-cloud.js`, `bin/agent-city-relay-dev.mjs`, `bin/agent-city-plans.json`, `.claude-plugin/plugin.json`, `hooks/hooks.json` | yes |
| bin/agent_questions.py | `bin/agent-questions-page.html` | yes |
| bin/agent_update.py | own `.claude-plugin/plugin.json`; the clone's `.claude-plugin/plugin.json` (main, not the cache) | yes |
| bin/agent-version.sh, agent-close-case.sh | `<cache>/<version>/bin/agent-start.sh` | yes |
| everything else in bin/ | sibling files in bin/ | yes |

No shipped file reads README.md, CLAUDE.md, AGENTS.md, agent.conf, agent_*.txt, tests/, mock/ or requirements/ from the plugin root. agent_level.py (`requirements*.txt`) and agent_housekeep.py (`REPO_DIRS`) name those words for the user's own diff and ideas, in PROJECT_ROOT.

## 4. Design options

| | A release branch (recommended) | B subfolder `./plugin` | C exclude list | D separate slim repo |
|---|---|---|---|---|
| How | release script builds branch `release` = ship set of a main commit; marketplace entry `ref: release` | `git mv` the ship set into `plugin/`, `"source":"./plugin"` | - | a second GitHub repo holds the ship set, `"source":"./"` there |
| Cache per version | 9.5 MB (probe P2) | 9.5 MB | does not exist (D1) | 9.5 MB |
| Clone | stays 19 MB (shallow main) | stays 19 MB | - | 9.5 MB only for users who add the new repo; existing users keep the old clone |
| Moves files | none | every file: conflicts with one-watcher and comment-shape, every test path changes | - | none here, but a second repo to keep in step |
| Release step | yes: `agent-release.sh --push` | none | - | sync + push the second repo |
| 0.39.0 users | update works (P2) | expected to work, not probed | - | old marketplace must point at the new repo |
| Rollback | revert one commit + bump version | move every file back | - | point the entry back |
| Owner-level step | none | none | - | create a GitHub repo |

Does the big clone matter? It is one shallow copy, fetched once, then only deltas; no session loads it. The cache is what users run and what multiplies per version (kept 14 days each). A fixes the cache now with no file moves. The clone still downloads tests/ and mock/ once: making the clone small needs D, or a later switch of the GitHub default branch to `release` (owner setting, own dry-run). Both are outside this task (decide 2).

## 5. Rules table (A)

| # | Rule | Example (real or fixture) | Result |
|---|---|---|---|
| 1 | The ship set is exactly six paths, in one list inside `bin/agent-release.sh`; `--list` prints it, one per line, this order | `bin/agent-release.sh --list` | `.claude-plugin` `hooks` `bin` `skills` `agents` `PRINCIPLES.md` |
| 2 | The repo is the folder above the script's bin/; it must be a git work tree | run from the cache `…/0.39.0/bin/agent-release.sh --dry-run` | exit 2, stderr `agent-release.sh: not a git checkout: <dir>` |
| 3 | The release tree is built from a commit, never from the work tree (`git ls-tree <from> <ship set> \| git mktree`): local edits, `__pycache__`, git-ignored files never ship; modes (exec bits) kept | `--from` default `HEAD`; dirty `bin/x.sh` in the work tree | the tree has the committed bytes only |
| 4 | Every ship path must exist in that commit | commit without `hooks/` | exit 1, `agent-release.sh: hooks is missing in <sha>` |
| 5 | The version is `.claude-plugin/plugin.json` `version` of that commit, digits and dots | `"version": "0.40.0"` | release commit message `release 0.40.0 from <short sha>` |
| 6 | One release commit per version on branch `release`, parent = the previous release tip (none → root commit). Fast-forward only | tip `release 0.40.0`, main bumps to 0.40.1 | new commit `release 0.40.1 from …`, parent = old tip |
| 7 | Same tree as the tip | nothing changed since 0.40.0 | exit 0, `release up to date: 0.40.0 (<sha>)`, no new commit |
| 8 | Tree differs, version not higher than the tip's | bin changed, version still 0.40.0 | exit 1, `agent-release.sh: version 0.40.0 is not higher than release 0.40.0: bump .claude-plugin/plugin.json first` (users would never get it, D5) |
| 9 | Reads check before any write: in every shipped text file, a path after a plugin-root prefix (section 3 patterns; `$(dirname "$0")`, `HERE`, `bin_dir`, `script_dir`, `_bin_path` mean bin/; `..` resolved) must be a file or folder in the release tree | `bin/agent-start.sh: "$PLUGIN_ROOT/PRINCIPLES.md"` | ok |
| 9a | | fixture `bin/x.sh` line 3: `cat "$PLUGIN_ROOT/README.md"` | exit 1, `agent-release.sh: bin/x.sh:3 reads README.md, which is not shipped`, no ref written |
| 9b | | fixture `bin/y.py`: `os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "t.txt")` | exit 1, `bin/y.py:<n> reads tests/t.txt, which is not shipped` |
| 9c | a path that holds a variable after the prefix is skipped, counted | agent-cloud-pack.sh `"$PLUGIN_ROOT/$need"` | `reads check: <n> ok, 1 skipped (variable)` |
| 9d | a path with no plugin-root prefix is not a read | `# requirements/city.md, "Joining"` | ignored |
| 10 | `--dry-run` prints, writes no ref: from sha + version, release tip sha + version (or none), shipped files count + bytes, the left-out top-level items, the reads check line, then `would commit release <v>` or the refusal | `--dry-run` on e90db3b | `ship: 173 files, 9561985 bytes`, `left out: .claude .gitignore AGENTS.md CLAUDE.md README.md agent.conf agent_completed.txt … mock requirements tests` |
| 11 | No flag: build and move the local `release` branch, print `release <v>: <sha> (from <short sha>)` and the push line `git push origin release` | | local ref only |
| 12 | `--push`: build, then `git push origin release`; a push that is not fast-forward is refused by git, never forced | | exit = git's |
| 13 | Main's marketplace entry: `"source": {"source": "url", "url": "https://github.com/maverick1014/auto-pipeline.git", "ref": "release"}`; name and description unchanged. `url`, not `github`: the dry-run can test the very same source type with a local URL | `.claude-plugin/marketplace.json` | README install lines stay as they are (`/plugin marketplace add maverick1014/auto-pipeline`) |
| 14 | Order at every release: bump the version on main, `agent-release.sh --push`, then push main. Release first: a fresh install never meets a missing branch (P4), and the update notice (agent_update.py reads main's plugin.json) never announces a version the release does not have | first rollout: release 0.40.0 pushed at 12:00, main at 12:01 | users updating at 12:00:30 still see "./" and stay full until main lands |
| 15 | skills/merge gets one line under step 8, after "main merged": in the auto-pipeline repo only (it has `bin/agent-release.sh`), after the bump run `bin/agent-release.sh --push` before main is pushed | | other repos skip it |
| 16 | 0.39.0 users (user and project scope, autoUpdate on): the next marketplace update reads the new entry, the plugin update installs the slim cache; the old folder gets `.orphaned_at`, removed after 14 days | probe P2 | the running session keeps its old folder until restart |
| 17 | This repo's dev loop: its sessions run the installed plugin from the cache too, so they get the release branch like every user; tests keep running from the worktree (tests/ next to bin/) | `python3 -m unittest discover -s tests` in a worktree | unchanged |
| 18 | `release` is never merged into main and never gets other commits; only the release script writes it | | |

## 6. Dry-run (level 4 migration dry-run, step 5)

All in the scratchpad, `HOME` and `CLAUDE_CONFIG_DIR` point inside it; the real `~/.claude/plugins` files are only checked by mtime before/after.

```
S=<scratchpad>/dryrun; mkdir -p "$S/home" "$S/cgi-bin"
git clone -q --bare <worktree> "$S/remote.git"
git -C "$S/remote.git" update-ref refs/heads/main e90db3b9397ee7c23707f3fa9d4817c0d4c813e5
git -C "$S/remote.git" symbolic-ref HEAD refs/heads/main
printf '#!/bin/sh\nexport GIT_PROJECT_ROOT="%s" GIT_HTTP_EXPORT_ALL=1\nexec git http-backend\n' "$S" > "$S/cgi-bin/git"; chmod +x "$S/cgi-bin/git"
(cd "$S" && python3 -m http.server --cgi --bind 127.0.0.1 8766 &)
export HOME="$S/home" CLAUDE_CONFIG_DIR="$S/home/.claude"; C="$CLAUDE_CONFIG_DIR/plugins/cache/auto-pipeline/auto-pipeline"
claude plugin marketplace add http://127.0.0.1:8766/cgi-bin/git/remote.git
claude plugin install auto-pipeline@auto-pipeline -s user                       # 0.39.0 as today
(cd "$S/proj" && claude plugin install auto-pipeline@auto-pipeline -s project)  # project scope
find "$C/0.39.0" -maxdepth 1 | sort                                             # BEFORE list
# slim build: clone of the branch, merged onto main, version 0.40.0, entry url -> the local URL (only difference to production)
bin/agent-release.sh --dry-run; bin/agent-release.sh --push; git push origin main
claude plugin marketplace update auto-pipeline
claude plugin update auto-pipeline@auto-pipeline -s user; (cd "$S/proj" && claude plugin update auto-pipeline@auto-pipeline -s project)
find "$C/0.40.0" -maxdepth 1 | sort                                             # AFTER list
HOME="$S/fresh" CLAUDE_CONFIG_DIR="$S/fresh/.claude" claude plugin install …     # fresh install (after marketplace add)
(cd "$S/repo" && git init -q && CLAUDE_PROJECT_DIR="$S/repo" "$C/0.40.0/bin/agent-start.sh")   # start text, quiz line
"$C/0.40.0/bin/agent-init.sh" "$S/repo2"; "$C/0.40.0/bin/agent-cloud-pack.sh" "$S/cloud"    # init, cloud-pack
city: "$C/0.40.0/bin/agent-city.sh" start on a scratch port, page answers 200, assets served, stop
failure paths: entry ref missing (P4 again); fixture bin/x.sh reading README.md -> --dry-run exit 1
rollback: revert the entry commit, version 0.40.1, push main -> update -> cache 0.40.1 is the full tree again
after: stop the http server, the monitor and autoclear the scratch start left, compare real ~/.claude/plugins mtimes
```

## 7. Rollback (written plan)

| Step | Command / effect |
|---|---|
| 1 restore | on main: `git revert <commit that set the url entry>` → `"source":"./"` again; bump `version` above the last slim release (0.40.0 → 0.40.1); commit; `git push origin main` |
| 2 users | autoUpdate on: next start updates the marketplace, then the plugin to 0.40.1 (full tree). By hand: `claude plugin marketplace update auto-pipeline && claude plugin update auto-pipeline@auto-pipeline` (or `/plugin`, Update). Without the bump nobody moves (D5) |
| 3 mid-update user | a session started before the update keeps its folder (in use, then `.orphaned_at`, removed after 14 days); the next start runs the new folder. No mixed folder: each version is a whole copy |
| 4 release branch | keep it until every user is on 0.40.1 (a fresh install of an old marketplace state still needs it); delete later with `git push origin --delete release` |
| 5 last resort | `claude plugin uninstall auto-pipeline@auto-pipeline && claude plugin install auto-pipeline@auto-pipeline` |

## 8. Tests (step 3, failing first)

| Test | Covers rows |
|---|---|
| ship list from `--list` | 1 |
| fixture repo (temp git repo with the script copied in): not a checkout, missing path, version, parent, up to date, not higher, dry-run writes no ref, exec bits kept, local edits not shipped | 2-8, 10, 11 |
| reads check on fixtures (README.md, ../tests, variable path, comment) | 9, 9a-9d |
| the real repo: `--dry-run` passes the reads check, left-out list | 9, 10 |
| marketplace entry shape; README install lines | 13 |
| skills/merge line (after main merged) | 15 |
| test_plugin_layout.py: `"./"` assertion becomes rule 13 | 13 |
