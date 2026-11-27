---
name: flow-diagram
description: Draw an agent or process flow diagram as an Artifact page in the owner's approved style (role tags on top, one hand-drawn SVG, nothing below). Use when the human asks for a flow, a flow diagram or a flow chart.
---
# /flow-diagram — the owner-approved way (2026-11-27)

The page: `reference.html` in this folder (published as the Agent 派活流程 artifact). Copy it, change the content, keep the look. Words to the human: the Language setting.

1. Load the `artifact-design` skill first. Update an existing flow artifact in place (same `url`, same `<title>`); a new one gets a two to four word title and a one-sentence `description`.
2. Page = title and one intro sentence, then the role tags, then the diagram, then one caption line. Nothing below it: no step table, no role table, no "what is new" list, unless the owner asks for one.
3. Role tags: one chip per role (colour dot, bold role name, a few words: model and job). One colour per role, used for the chip, the box border, the tint and the role word inside the box. Define each colour as a light and a dark token pair on `:root`; red dashed = sent back; grey dashed = waiting.
4. Diagram: one inline SVG, `viewBox` 900 wide, `role="img"` with an `aria-label` that says what it shows. Arrows and labels only as below.
   - Box: 300x64, rx 10, tinted fill, role-coloured border. A numbered circle (r 12) at the left: a global number for the shared steps, `F1`, `L1` for a step inside a lane. Line 1: coloured role word, ` · `, the action (at most 18 characters). Line 2: one grey line (at most 19 characters).
   - Flow runs top to bottom; 30 px between boxes; a straight arrow with an arrowhead marker.
   - Decision: a diamond (240x84), a question of at most 8 characters; the arrows out are labelled yes and no (`是`/`否`).
   - A split: two lanes side by side, each with a small grey lane name; the lanes join again at one shared gate box. A failed gate: a red dashed arrow to a red dashed box, labelled with what happens.
   - Wait or park: a dashed grey box to the side.
5. Write short labels; the detail lives in the rules, not in the picture. No emoji, no gradients, no numbers that do not mean an order.
6. Publish with the Artifact tool, then give the owner the link. Look at it once only if the session offers a preview; he reviews the live page.
