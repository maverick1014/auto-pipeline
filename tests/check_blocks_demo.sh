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
printf '{"task": "t", "type": "reviewer", "by": "main", "at": "%s"}\n' "$(date -v-1M '+%Y-%m-%d %H:%M' 2>/dev/null || date -d '-1 min' '+%Y-%m-%d %H:%M')" \
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

say "done: everything above ran in $T (delete it when read)"
