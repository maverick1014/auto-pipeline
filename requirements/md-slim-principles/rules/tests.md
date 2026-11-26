# Tests
Read when: you write, pick or run a test, or fix a bug a review or check found.

R8 (tests)
- Tests stay as a cheap guard: light related tests in every task; a bug that a review or check finds gets a small test with its fix (W3)

W3. TDD
- Task manager writes the failing tests → worker writes code → tests pass
- Task managers never write product code; workers never write tests: PRINCIPLES.md (Roles)
- No test = not started
- Full lane only; fast lane → R1

W4. Multi-agent tests
- Tests are organised module → feature
- Which tests run follows the blocks (R8): the light RELATED TESTS and GUARD TESTS per task; MODULE TESTS only when its trigger fires, light ones only; a heavy one goes to the release run or the nightly
- Every test run goes through `agent-test-run.sh` (S5)
- The main manager and the merge deputy never re-run tests the task manager already passed. Only on a merge conflict: test the conflicted part
- After a bounce: re-run only the tests that failed, not the suite

S5. Test runs
- Every test run goes through `agent-test-run.sh`: it reserves its measured peak MB while it runs, and the monitor watches it
- One small shared reservation list per machine (every running job: pid, reserved MB; a dead pid frees its entry): two agents, also of different repos, never count the same free memory
- Measured weights live per machine (`agent_test_weights.json` in the git common dir); `agent_repo.conf` `weight.<key>` lines are seeds only
- Every test run caps its own parallelism, e.g. `jest --maxWorkers=2`, `flutter test -j 2`
- Every test run that can run in the background runs in the background by default (Bash `run_in_background`)
