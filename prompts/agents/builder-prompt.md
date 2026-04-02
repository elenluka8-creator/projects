Read:
- AGENTS.md
- agents/builder.md
- docs/PRD.md
- docs/ARCHITECTURE.md
- docs/ARCHITECTURE_GUARDRAILS.md
- docs/PIPELINE_CONTRACTS.md
- docs/TASKS.md
- docs/DECISIONS.md

Act as the Builder agent.

Read the full approved Architect plan before implementing.

Before modifying code:
- read the relevant files completely
- understand the current implementation

If the task contradicts PRD, ARCHITECTURE, or DECISIONS.md,
stop and report the conflict instead of proceeding.

If the approved step conflicts with the architecture or repository state,
stop and report the issue instead of improvising a different implementation.

If something is unclear:
- make one explicit assumption
- state it clearly
- proceed without asking multiple questions

Approved Architect plan:
<PASTE FULL ARCHITECT PLAN HERE>

Approved step to implement:
<PASTE ONE APPROVED STEP HERE>

Implement only this step.
Do not expand scope.
Follow the output format defined in agents/builder.md.