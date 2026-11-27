# gate-self-check: a change to the gate never passes itself, and the fast lane is the real fast lane

Owner, 2026-11-27, on the self-audit: "for the fast lane gate issues also need to fix".

## Today

- fast-lane-simple changed the gate (bin/agent_checks.py: the fast-lane exception) and passed its own merge gate with the branch's new code and the main manager's own PR REVIEW.
- Its builder was a human-direct Helper, but the todo line said `fast-lane-simple Deputy`, and `is_fast_lane` reads the todo builder name, so the gate took it as fast lane.
- reopen-keeps-checks (also a gate change) was built by the main manager itself and committed with no review; a late review passed it afterwards.

## The rule

1. A diff that touches the gate, the guard or promote (the code behind `agent-file.sh checks gate`, `agent-guard.sh`, `agent-promote.sh`; the gate's list is `GATE_FILES`: bin/agent_checks.py, agent-file.sh, agent_guard.py, agent-guard.sh, agent_promote.py, agent-promote.sh, agent_level.py, agent-level.sh, agent-owner-order.sh, agent_owner_order.py, agent_blocks.py, hooks/hooks.json) is never fast lane at the gate: PR REVIEW and CORE REVIEW must come from a reviewer the main manager launched; a PR REVIEW by the main manager does not count for it.
2. The gate that decides a merge is the base's gate, never the branch's own: the merge skill and the merge deputy run the gate from the main checkout (in this repo its `bin/`; elsewhere the installed plugin), never `<scratch>/bin/` of the branch.
3. Fast lane at the gate only when the guard's launch records show a fast-lane deputy launched by the main manager for this task; a task built by a Helper, a task manager or the main manager itself is full lane there (the todo builder name alone decides nothing).
4. A task the main manager built itself: PR REVIEW from a launched reviewer, and every block but OWNER SIGN (taken from the block table) written by someone other than the main manager; a builder named `main` or `<repo> Manager` is the main manager.

## Examples

- A fast-lane deputy changes bin/agent_checks.py; the main manager writes PR REVIEW pass: the gate refuses `PR REVIEW: a gate change needs a launched reviewer`.
- A branch that adds a new exception to the gate: the merge deputy's gate runs from the main checkout's bin, so the exception does not apply to its own merge.
- Todo builder `x Deputy`, but the launch records show no fast-lane deputy for x (a Helper built it): the main manager's PR REVIEW is refused as for the full lane.
- Builder `main`: a DIFF SCAN pass `--by auto-pipeline Manager` is refused as by the builder.

## Not in this task

The merge step of an isolated fast-lane deputy (task deputy-merge-text).
