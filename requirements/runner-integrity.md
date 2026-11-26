# runner-integrity: tests/run2.py never reports green for a file that did not really run

Found by the release-check-loosen reviews (2026-11-26). No test file does this today, but the full run gates every release, so a hole here would let a red suite publish.

## Today

- A test file that calls `sys.exit(0)` at import cannot be listed by the loader; run2.py skips its per-file count check for a file it cannot list, so the full run reports GREEN.
- A file whose tests are all skipped counts as passed: the full run reports GREEN with 0 tests run from that file.
- Each run leaves one `run2_*` folder in TMPDIR (about 218 had piled up). An earlier evening a run lost its own log folder mid-run because another agent removed `run2_*` folders it believed were its own.

## The rule

1. A test file the loader cannot list (any exit, exception or zero test ids at import) makes the run RED, with one line naming the file and the reason.
2. A file where every test was skipped makes the run RED, with one line naming the file, unless the file is listed in a repo fact `all_skip_ok` in `agent_repo.conf` (empty for this repo; a file is added only with the reason next to it).
3. run2.py removes its own temp folder when it ends: green, red, error or Ctrl-C.
4. At start it removes old `run2_*` folders only when it can prove they are its own and dead: a marker file inside names the process id and start time, and that process no longer runs. A folder without a marker, or with a live process, is never touched.
5. The per-file count check, the FAIL line format and the exit codes of a normal run stay as today.

## Examples (the failing tests come from these)

- A fixture file whose import does `sys.exit(0)`: the run exits non-zero; the output names the file and "could not be listed".
- A fixture file whose only test is skipped: the run exits non-zero, naming the file; the same file listed in `all_skip_ok`: green.
- A normal green run: its temp folder is gone afterwards; a red run and a run stopped with SIGINT: the same.
- A stale `run2_*` folder whose marker names a dead pid: removed at the next start; one whose marker names a live pid: kept; one without a marker: kept.
- A normal run of today's suite: the same counts and the same result as before.

## Not in this task

The selection of related tests (release-check-loosen). The nightly record (nightly-on-machine).
