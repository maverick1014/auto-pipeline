---
name: cloud-pack
description: Lay the pipeline into a repo as committed files, so cloud sessions (claude.ai/code), which never install plugins, get it too. Use to set up or refresh a repo for cloud use.
---
# /cloud-pack — pack this pipeline into a repo (PRINCIPLES.md S1)

1. Read `language` from this project's `agent.conf`.
2. Run:
   ```
   ${CLAUDE_PLUGIN_ROOT}/bin/agent-cloud-pack.sh "<repo path, default the current project>" --language <language from agent.conf>
   ```
3. If the output says to run with `--update`, run it again with `--update` added.
4. Show the output to the human unchanged.
5. Tell the human: commit and push so a cloud session can read it.
6. Tell the human: the Claude GitHub App must be installed on that repo, or the cloud clone has no remote to push to.
