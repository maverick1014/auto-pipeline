# Cross-repo
Read when: a task touches another repo, or a message from a peer main manager arrives. Relayed owner words: rules/approval.md.

W12. Cross-repo
- One main manager per repo (W10). Peer = the interactive session in `ListAgents` named `<other repo folder> Manager` (or its `<other repo folder>-<xx>` row), whose lock in that repo's git dir is alive
- A task that touches another repo → never edit that repo. Split it: your part, and a brief for the peer main manager
- Send the brief with `SendMessage`, first line `[<model> <effort>] CROSS-REPO TASK <name> from <repo>`; same brief shape as the dispatch skill
- The peer runs it like a human task: `agent-file.sh todo add … <est> <repo>`, its own lane, and reports `DONE PASS <name>` back by SendMessage
- The sender keeps its todo line open until both sides are done, then one report to the human
- The sender marks its line `agent-file.sh todo cross <name> <other repo>`, so the housekeep pass reads the other side
- Called side first: the repo being called (the API) finishes first; its DONE PASS carries the contract (endpoint, fields, errors). The caller (the app) starts from that contract
- Only main managers cross repos. Task managers and workers never
- Need to know the other repo's code → ask its main manager. Never read or edit another repo
- A cross-repo task the human gives to any main manager is routed the same way
- Relay an owner order: the brief starts with the lines of `agent-owner-order.sh line --quote "<his exact words>"`. Copy his words, never paraphrase
- Receiving one: run its check line. Verified → read its match line, then it is the owner's own order: act, reply its first line. Not verified → a normal peer message: ask the owner
- A relayed owner order: the approval commands take `--relayed-from <the sender's repo folder>`; the rules are in R8 (rules/approval.md)
