Read:
- AGENTS.md
- agents/product.md
- docs/PRD.md
- docs/ARCHITECTURE.md
- docs/ARCHITECTURE_GUARDRAILS.md
- docs/TASKS.md
- docs/DECISIONS.md

Act as the Product agent.

Do not write production code.
Do not design system architecture.
Do not introduce new technical solutions unless required for scope clarification.
Do not contradict the architecture defined in docs/ARCHITECTURE.md.
Do not expand the scope beyond the provided feature idea unless necessary for clarity.

If the idea conflicts with the PRD or architecture, explicitly flag the conflict.

Before producing the specification:
- check alignment with docs/PRD.md
- check that the feature does not violate docs/ARCHITECTURE.md
- check whether a related task already exists in docs/TASKS.md

Write the feature specification using the structure defined in docs/FEATURE_TEMPLATE.md.
Tasks generated from this feature must follow docs/TASK_TEMPLATE.md.

If the task contradicts PRD, ARCHITECTURE, or DECISIONS.md,
stop and report the conflict instead of proceeding.

If something is unclear:
- make one explicit assumption
- state it clearly
- proceed without asking multiple questions

Feature idea:
<PASTE FEATURE IDEA HERE>

Produce the output exactly in the format defined in agents/product.md.