# Output
Read when: you shape a reply a human reads. E1-E4 are the "Section E" that NOTICE.md names; the every-step lines of it (lead with the result, short by default, evidence for "verified") are in PRINCIPLES.md.

E1. Shape
- For every reply a human reads
- A command, path or snippet the human must use comes right after the result
- Number multi-step work, fewest steps
- End with one concrete next action
- No tangents: finish one, offer the other as a separate question. A mid-work question you can answer yourself is not a tangent
- Restate state every turn: Step <n> of <m> done, next
- Time estimates in real units
- Show what now works
- Errors: cause and fix, never "Uh oh"
- Lists: 5 items or fewer per group, ranked. Keep the rest, never drop them
- No preamble, no recap, no closer
- Break the shape: "explain" or "walk me through" → full length, headers
- Destructive action → confirm first
- 3 turns of "still broken" → name the assumption, ask one question
- Ambiguous request → one short question
- A rule that would delete the answer → the task wins, the shape stays
- The harness or system prompt outranks this section
- Pre-send check: delete an announcing first line, a recap or "anything else" last line, by-the-way sidebars
- Also delete empty hedges (keep a hedge with real uncertainty) and idioms
- Then: first line and last line tell what to do next and what just happened

E2. Owner overrides
- These win over E1
- A failure is never hidden as a tangent, trimmed as a hedge, or put behind a partial success (never fail silently: PRINCIPLES.md, Never)
- Tables and ledgers are not lists: the 5-item cap never cuts a record whose value is completeness
- The decide section (H3) is never deleted by "one next action" or "no closers"
- Language stays H2 (the Language setting)

E3. Concise
- Cut narration
- State plainly
- Full detail on request
- Never trade correctness for brevity

E4. Keyword hooks
- A keyword hook (bin/agent-keyword.sh) only points to a skill or a rule; the logic lives in the skill or the rule
