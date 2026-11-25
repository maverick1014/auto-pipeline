---
name: question
description: List every question that waits on the owner (chat list, or an Artifact page when many), and read his answers afterwards ("done", "1A 2B"). Use when the human asks for pending questions or says he answered the page.
---
# /question — list the questions, read the answers (PRINCIPLES.md W18)

Words to the human: the Language setting. Headings: `## To decide` (zh: `## 要你决定`), recommended mark `(recommended)` (zh: `(建议)`), done word `done` (zh: `答完了`). A spawned worker, deputy or reviewer never runs this: do nothing.

Your role, from the `YOU:` line of your start text: main manager (`<repo> Manager`) → `Q=""`, every question of the whole repo. Task manager, human-direct Helper, or no live main manager → `Q=" --self"`, the questions of your own task only. `AF=${CLAUDE_PLUGIN_ROOT}/bin/agent-file.sh`.

## A. List the questions

1. Run this one command from the project folder, nothing else: `$AF questions$Q`
2. Its first line is the count. 10 or fewer: show all as a numbered list in chat under the decide heading, each a decide item (title, sub line, facts, lettered options, the recommended one marked), nothing dropped. The owner answers like `1A 2B — note`.
3. More than 10: the same command with `--page <file>` (a file in your scratchpad); publish that file with the Artifact tool (capabilities db and user). The `QUESTIONS PAGE:` line of `agent_state.txt` holds the url: publish with that url (redeploy). A first publish: record the new url with `$AF questions --url <url>`. Then one chat line: the count, the link, answer all, then tell me (`done`).
4. No Artifact tool: the chat list of all, nothing dropped.

## B. The owner answers after the page

Do this when the owner says `done`, `answered`, `答完了` (or pastes `1A 2B` ...) and `agent_state.txt` has a `QUESTIONS PAGE: <url> | ... | <map file>` line. Check first that a question of the page is still open: `$AF questions$Q --json`; none open → nothing to read, say so.

1. The page is the url of that line. Read every answer at once with ArtifactData (list, the `answers` collection). Lines the owner pasted in chat go by number through the map file (the third field of the `QUESTIONS PAGE: <url> | <page file> | <map file> | since <date>` line).
2. Show one table: question, answer.
3. For each answered question run `$AF questions answer <id> "<answer>"` and carry on. An unpicked question is still open.
