#!/usr/bin/env bash
# agent-promote.sh — the working branch to production, only on the owner's verified words (check-blocks sections 28-30, 34).
#
#   agent-promote.sh --owner-quote "<words>" --means "<action>" [--question "<q>"] [--time <t>]
#       publish: verify the words, sync (production into the working branch), the last nightly must be green on the working
#       branch tip, production must be an ancestor; then push the tip to origin/<production>, the local production ref follows,
#       the checkout stays on the working branch; the release build (bin/agent-release.sh --push) runs right after.
#   agent-promote.sh --task "<task>" --branch <branch> [--results <file>]
#       the direct path: first the task's CHECK lines are gathered from its worktree (agent_worktree.txt);
#       --results <file> (a task on another machine: the CHECK lines of its REPORT) goes on to the gate; the words are the ones stored at `todo add --target production --owner-quote` (no quote here);
#       the gate runs first (agent-file.sh checks gate), nothing is pushed on GATE REFUSED; then <branch> is merged (--no-ff) into origin/<production> in a short-lived worktree and pushed, the
#       release build runs, then production is merged back into the working branch and pushed.
#   agent-promote.sh --sync
#       in the main checkout (on the working branch): merge origin/<production> into the working branch when it is not in
#       yet, push the working branch.
#
# Production branch: production_branch in agent_repo.conf, else the target of origin/HEAD, else main.
# One refusal = one line, exit 1, nothing changes. Logic: agent_promote.py.
exec python3 "$(cd "$(dirname "$0")" && pwd -P)/agent_promote.py" "$@"
