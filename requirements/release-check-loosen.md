# release-check-loosen: a small change after a green full run needs no second full run

Owner, 2026-11-26: "err why rename the doc need to run full suit again ?". His answer to the proposal: "1a". Then: "for the rlease check loosen can do first ya".

## Today

- A publish needs a green full run on the tip of the working branch (`bin/agent_nightly.py` `release_ok`, read by `bin/agent_promote.py`).
- One exception: the tip may be one commit that changes only `.claude-plugin/plugin.json` (`released_commits`).
- Any other commit after the green run, also one that changes a line of text, makes the check refuse: the full suite must run again (about 8 minutes on a free machine, 18 on a loaded one).

## The rule

After a green full run on commit G, the commits G..tip are "small" when every file they change is one of:
- text: a `.md` file anywhere (rule text, skills, agent files, requirement docs, README);
- a mock page: a file under `mock/`;
- a test file: a `test_*.py` under the tests folder of `agent_repo.conf`;
- the version line of `.claude-plugin/plugin.json` (as today).

Everything else is code and needs the full run: any other file under `bin/`, `hooks/`, `.claude-plugin/`, `agent_repo.conf`, a test helper that is not a `test_*.py`, any other path.

When the commits since the last green run are all small, `agent-nightly.sh --start` runs a TOP-UP instead of the full suite:
- the repo's guard tests (`guard_tests` of `agent_repo.conf`: here the rule-text tests), because text changed;
- every test file that changed or was added since G;
- through the same runner and the same memory gate as the full run.

A green top-up is recorded on the tip together with the full run it stands on ("green <tip>, top-up over <G>"). `--release-ok` and the publish accept it like a full green run on the tip. A red top-up is a red run: `--failures` names the tests.

## What stays

- A commit that changes code after G: the full run, as today.
- No green full run yet, or the last full run was red: the full run.
- A top-up never stands on a top-up for more than the code allows to verify: the chain must end at a green FULL run whose commit is an ancestor of the tip; the check walks every commit between that full run and the tip.
- A merge commit counts by the files it brings in against the green commit (`git diff --name-only G tip`), so a merge of a text-only branch is small and a merge that brings code is not.
- `--status` says which kind the last run was.

## Main manager's decisions (2026-11-26, after the first build)

- The automatic nightly stays a FULL run, always (it is the net): its callers (the watch's housekeep pass, the session start) call `agent-nightly.sh --start --nightly`; `--nightly` can only make a run full, never smaller. A `--start` without it (the release path) picks top-up or full by the rule.
- The frontmatter of a `.md` under `agents/` or `skills/` (the lines between the first two `---` lines) is configuration Claude Code reads: a change inside it is code, a change only below it is text; adding or deleting such a file is code.
- Review fixes (2026-11-26, the reviewer's attacks on dd5aa00):
  - A. A test file is small only with a plain name (`tests/test_<letters, digits, _>.py`); any other name is code. The top-up runs each planned file as its own command, every path one shell-quoted word, and a planned file that did not run or ran no test makes it red.
  - B. The top-up runs the guard tests + the changed test files + the light related tests of every changed file, picked by the RELATED TESTS picker (`agent_level.py check --base <G> --json`); `tests/test_rules_structure.py` joins `guard_tests` here.
  - C. `--due` counts FULL runs only: a top-up never stands in for the night's full run.
  - D. The version-only tip counts as its parent only when plugin.json changes the version alone (the same version check).
  - E. A selection miss is a finding of a full run only; a red top-up is a red run with its failing tests.
- Second attack pass (2026-11-26, on 4c39713):
  - 1. Before a planned test file runs, the tool loads it itself (unittest discovery on that one file, in the scratch tree) and needs its own line back: a nonce sent on stdin, read after the load, plus the test count; no line, a load failure or 0 tests: red (`could not be loaded`, `holds no test`). The test's own output is never the proof.
  - 2. Every picker tree `agent_nightly_wt_pick_<pid>` whose pid is dead is removed before a pick and on `--status`; `--start --nightly` never runs the picker.
  - 3. The top-up also runs every tests/test_*.py whose source names a changed text file (its path, its base name, `<folder>/*<ext>`, `<parent>/*/<base name>`); plain text search, and the record check needs this set too.
- Decision (c) on the speed (2026-11-26):
  - One run in parallel: after the per-file probe, the top-up runs every planned file in ONE `related_cmd` call, each path one quoted word; the exit code decides, the failing tests are read from the output.
  - This repo's `related_cmd` is the parallel runner (`python3 tests/run2.py {tests}`), the same one the full run uses; the failing tests are read from its indented FAIL/ERROR lines.
  - Never slower than the full run: with `tests/timings.txt`, planned seconds above half (`TOPUP_MAX_SHARE`) of the summed seconds of every file: no top-up, "the full run is needed: the top-up would not be faster (<n> of <m> s)"; no timing data: no such check.

## Examples (the failing tests come from these)

- Green full run on G; one commit changes `README.md` and `rules/time.md`: `--release-ok` refuses and says a top-up is enough; `--start` runs the guard tests only; green: `--release-ok` passes on the tip.
- The same with a commit under `mock/`: a top-up with the guard tests.
- A commit changes `tests/test_x.py`: the top-up runs the guard tests and `tests/test_x.py`; a failing `test_x.py` makes it red and the publish is refused.
- A commit changes `bin/agent-file.sh` (one line): not small: `--start` runs the full suite; `--release-ok` before it names the file.
- A commit changes `hooks/hooks.json`, `agent_repo.conf`, `tests/sharedrepo.py`, or anything in `.claude-plugin/plugin.json` beyond the version: not small.
- Text commit, top-up green, then a second text commit: a new top-up on the new tip is enough (the chain still ends at the full run on G).
- Text commit, top-up green, then a code commit: the full run.
- The last full run was red: a text commit does not make a top-up possible.
- A merge commit of a branch that changed only `.md` files: small. A merge that brings a `bin/` change: not small.
- The version-only tip keeps working as today (green on its parent counts).

## Not in this task

Which tests a task runs. The nightly's timing. Any change of who may publish.

## Outcome (2026-11-26)

The top-up was built, attacked in four reviews and DROPPED (main manager's stop rule: a real hole in the final review drops it). Each round found one more way a partial run could stand in for the full run and be wrong:
- Shell characters in test file names (`;`, a space, `$(...)`) reached the runner's shell: a failing test was skipped and the top-up was green.
- A test file that exits at import (`sys.exit(0)`, `os._exit(0)`) or prints its own "Ran 1 test / OK" was taken as run and green.
- Tests that read a changed .md by its name (a base name like SKILL.md, a path in parts) were not picked: green top-up, red full run.
- With this repo's single-process related runner the top-up was slower than the full run (661 s against 460 s).
- Tests that run only in the full run (`skipUnless(AGENT_FULL_RUN == "1")`) are skipped by run2.py when files are named: green top-up, red full run on the same tip.

Kept, because each is proven and useful on its own:
- The version-only tip counts as its parent only when its single change is a version-only edit of `.claude-plugin/plugin.json` (before, any plugin.json change passed).
- The failure reader accepts run2.py's indented FAIL/ERROR lines, so a red full run records its failing tests and `--failures` names them (before: only "full_cmd exit 1").
- This repo's `related_cmd` is `python3 tests/run2.py {tests}` (what every brief already runs) and `tests/test_rules_structure.py` joins `guard_tests` (a rule file over 70 lines passed the old guard).
