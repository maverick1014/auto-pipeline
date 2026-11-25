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
cd "$R"
"$P/bin/agent-file.sh" todo add t small "banner to toast" 10 --checks "DIFF READ" --builder "t Deputy"
for b in "DIFF SCAN" "BUILD" "RELATED TESTS"; do "$P/bin/agent-file.sh" check t "$b" pass --by "t Deputy" --evidence demo; done
"$P/bin/agent-file.sh" checks gate t --dir "$R" --base base; echo "exit $?"
"$P/bin/agent-file.sh" check t "DIFF READ" pass --by "check deputy" --evidence "read the diff"
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
g add -A; g commit -q -m "fix: empty list crashes the report"
"$P/bin/agent-init.sh" "$R" | grep "agent_repo.conf"
cat "$R/agent_repo.conf"

say "done: everything above ran in $T (delete it when read)"
